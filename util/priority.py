"""群内权限（QQ 端与网页端共用）。

这套逻辑原来只写在 `webui/util.py` 里。QQ 指令（【修正出刀】等）也要按**同一口径**
判权限，而 `clanbattle` 反向 import `webui` 会撞循环导入（`webui/__init__` → `api` →
`clanbattle`），所以把「群角色查询 + 权限等级计算」下沉到这里。
`webui/util.py` 只是 re-export，行为不变。

权限等级见 `basedata.GroupPriority`：
    0 普通成员 / 1 网页端管理员 / 2 群主·群管（仅本群） / 3 bot 主人（所有群）
能力：管理他人通知 >= 2；修正出刀 >= 1；取消他人监控、跨群查看 = 仅 bot 主人。
"""

import asyncio
import time
from typing import Dict, Optional, Tuple

from nonebot import logger

from ..basedata import GroupPriority
from ..database.dal import pcr_sqla
from ..database.models import ClanBattleMember


# nonebot 主循环引用：游戏 client / OneBot API 都绑在它上面。uvicorn 在独立线程、
# 有自己的 loop，跨 loop await 会报错并污染游戏会话；所以一律投递回主循环执行。
# 由 `webui/api.py: kanna_web` 在启动时写入 **本模块** 的全局（不是 webui.util 的）。
main_event_loop: asyncio.AbstractEventLoop = None


async def call_in_main_loop(coro, timeout: float = 90):
    """把涉及游戏 client / OneBot API 的协程投递回 nonebot 主循环执行"""
    from fastapi import HTTPException, status

    if main_event_loop is None or main_event_loop.is_closed():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "机器人主循环尚未就绪，请稍后再试"
        )
    future = asyncio.run_coroutine_threadsafe(coro, main_event_loop)
    try:
        return await asyncio.wrap_future(future)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"游戏接口调用失败：{e}")


# 群内角色缓存 {(group_id, user_id): (role, 过期时间)}：查角色要走 OneBot 请求，
# 而仪表盘有 3 秒一轮的 SSE，所以缓存 10 分钟（群主/群管变动是低频事件）。
_GROUP_ROLE_CACHE: Dict[Tuple[int, int], Tuple[str, float]] = {}
_GROUP_ROLE_TTL = 600
# 查询失败（机器人掉线等）时的短缓存，避免每个请求都卡在超时上
_GROUP_ROLE_FAIL_TTL = 60
# 缓存条数兜底：group_id 是从 URL 拿的，不设上限的话被遍历会一直涨
_GROUP_ROLE_CACHE_MAX = 4096
# 腾讯系协议端把群主/群管报成这几种 role
_OWNER_ROLES = ("owner", "admin", "administrator")


def is_bot_owner(user_id: int) -> bool:
    """是否是 bot 主人（hoshino.config.SUPERUSERS 里的 QQ）"""
    try:
        from hoshino import config

        superusers = getattr(config, "SUPERUSERS", None) or []
        return int(user_id) in {int(q) for q in superusers}
    except Exception:
        return False


async def fetch_group_role(group_id: int, user_id: int) -> str:
    """查询某人在某群里的角色：'owner' / 'admin' / 'member'；查不到返回空串。

    走 OneBot 的 get_group_member_info（aiocqhttp 用 Api.__getattr__ 动态挂载了
    这些 API，等价于 bot.call_action('get_group_member_info', ...)），必须投递回
    主循环。任何异常都按「查不到」处理 —— 权限查询失败时宁可降级成普通成员，
    也不要因为机器人掉线把整个页面打挂。
    """
    now = time.time()
    key = (int(group_id), int(user_id))
    if cached := _GROUP_ROLE_CACHE.get(key):
        role, expire = cached
        if now < expire:
            return role

    role = ""
    try:
        import nonebot

        bot = nonebot.get_bot()
        kwargs = {"group_id": int(group_id), "user_id": int(user_id)}
        # QQ 指令本来就在主循环里跑：直接 await，别再往同一个 loop 投递一次。
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if main_event_loop is not None and running is main_event_loop:
            info = await bot.call_action("get_group_member_info", **kwargs)
        else:
            info = await call_in_main_loop(
                bot.call_action("get_group_member_info", **kwargs)
            )
        role = str((info or {}).get("role") or "")
    except Exception as e:
        logger.warning(f"查询群成员角色失败 group={group_id} user={user_id}: {e}")

    if role in _OWNER_ROLES or role == "member":
        expire = now + _GROUP_ROLE_TTL
    else:
        # 查不到也缓存一小会儿，避免机器人掉线时每个请求都等一次超时
        role = ""
        expire = now + _GROUP_ROLE_FAIL_TTL

    # 满了就整体清掉重来 —— 角色数据本来就能重新查，不值得为淘汰策略增加复杂度
    if len(_GROUP_ROLE_CACHE) >= _GROUP_ROLE_CACHE_MAX:
        _GROUP_ROLE_CACHE.clear()
    _GROUP_ROLE_CACHE[key] = (role, expire)
    return role


async def is_group_manager_in(group_id: int, user_id: int) -> bool:
    """某人是不是这个群的群主 / 群管（用于自动发现「我管理的群」）"""
    return await fetch_group_role(group_id, user_id) in _OWNER_ROLES


async def get_member_row(user_id: int, group_id: int) -> Optional[ClanBattleMember]:
    """取该用户在该群的成员绑定记录（没发过【绑定本群公会】则返回 None）"""
    for member in await pcr_sqla.get_member_group(int(user_id)):
        if int(member.group_id) == int(group_id):
            return member
    return None


async def effective_group_priority(user_id: int, group_id: int) -> int:
    """算出某人在某个群里的实际权限等级（basedata.GroupPriority）

    取以下几项的最大值：
      - bot 主人                    → 3（对所有群生效）
      - WebAccount.priority         → 人工用【网页权限】授予的全局等级
      - ClanBattleMember.priority   → 人工授予的「本群」等级
      - 该群群主 / 群管理            → 2（自动识别，只对本群生效）

    QQ 端（【修正出刀】）和网页端（`require_group_priority`）都走这一份，保证两端口径一致。
    """
    user_id, group_id = int(user_id), int(group_id)
    if is_bot_owner(user_id):
        return GroupPriority.bot_owner.value

    level = GroupPriority.member.value
    if web_user := await pcr_sqla.web_query_user(str(user_id)):
        level = max(level, int(getattr(web_user, "priority", 0) or 0))
    if (member := await get_member_row(user_id, group_id)) is not None:
        level = max(level, int(getattr(member, "priority", 0) or 0))
    if await fetch_group_role(group_id, user_id) in _OWNER_ROLES:
        level = max(level, GroupPriority.group_admin.value)
    # 兜底夹一下，防止数据库里被写进超出定义的等级
    return min(level, GroupPriority.bot_owner.value)
