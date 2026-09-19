import asyncio
import time
from typing import Dict, List, Optional, Tuple, Union

from fastapi import Cookie, Depends, HTTPException, status
from nonebot import MessageSegment, logger

from ..basedata import GroupPriority, NoticeType
from ..clanbattle.base import clan_boss_info, day_report
from ..database.dal import pcr_sqla
from ..database.models import ClanBattleMember, CookieCache, RecordDao
from ..util.tools import daoflag2str
from .web_model import DaoInfo


# nonebot 主事件循环引用：游戏 client / OneBot API 都绑定在该 loop 上。
# uvicorn 跑在独立线程、有自己的 loop，跨 loop 直接 await 会报
# "bound to a different event loop" 并污染游戏会话（请求正在处理中）。
# 网页端任何涉及游戏 client 或 OneBot API 的调用，都必须用
# run_coroutine_threadsafe 投递回主循环执行。
main_event_loop: asyncio.AbstractEventLoop = None


async def call_in_main_loop(coro, timeout: float = 90):
    """把涉及游戏 client / OneBot API 的协程投递回 nonebot 主循环执行"""
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


async def verify_cookie(token: str = Cookie(None)) -> CookieCache:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "请先登录")
    if cookie := await pcr_sqla.web_query_cookie(token):
        if time.time() - cookie.time < 3600 * 7 * 24:
            return cookie
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录过期")


# ---------------------------- 群内权限 ----------------------------
#
# 网页端权限是「按群」算的，不是全局一个值。等级定义见 basedata.GroupPriority：
#   0 普通成员（只读）
#   1 网页端管理员（bot 主人用【网页权限】人工授予）
#   2 群主 / 群管理（在群里自动识别，只对本群生效）
#   3 bot 主人（hoshino.config.SUPERUSERS），对所有群生效
#
# 能力对照：
#   预约 / 挂树 / 申请 / 记录 SL（只能给自己）  → 不限等级，0 级即可
#   管理他人的通知（替人发 / 替人取消）        → >= 2
#   修正出刀                                   → >= 1
#   取消他人的出刀监控                         → 仅 bot 主人（监控人本人随时可以取消自己的）
#   跨群查看                                   → 仅 bot 主人

# 群内角色缓存 {(group_id, user_id): (role, 过期时间)}
# 查角色要走 OneBot 网络请求，网页端每个请求都查一遍太慢（仪表盘还有 3 秒一轮的
# SSE），这里缓存 10 分钟；群主/群管变动是低频事件，这个新鲜度足够。
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
        info = await call_in_main_loop(
            bot.call_action(
                "get_group_member_info", group_id=int(group_id), user_id=int(user_id)
            )
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


async def ensure_group_access(user_id: int, group_id: int):
    """校验登录用户能否访问指定群的数据。

    规则（与「跨群查看仅 bot 主人」保持一致）：
      - bot 主人：任意群
      - 其他人：必须和该群有关系 —— 要么有成员绑定记录（在群里发过【绑定本群公会】），
        要么是该群的群主 / 群管理。

    原先所有 /{group_id}/... 路由只校验登录态，任何登录用户改一下地址栏里的群号
    就能看到别的群数据，这里补上归属校验。
    """
    user_id, group_id = int(user_id), int(group_id)
    if is_bot_owner(user_id):
        return
    if await get_member_row(user_id, group_id) is not None:
        return
    if await fetch_group_role(group_id, user_id) in _OWNER_ROLES:
        return
    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        "您不是该群成员，无权访问该群数据（请先在群里发送【绑定本群公会】）",
    )


async def require_group_priority(
    user_id: int, group_id: int, need: int, action: str
) -> int:
    """要求某人在某群里至少有 need 级权限，不够就 403；返回实际等级"""
    level = await effective_group_priority(user_id, group_id)
    if level < need:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"权限不足：{action}需要 {need} 级权限，您当前 {level} 级。"
            "群主 / 群管理会自动获得 2 级，其他情况请让 bot 主人用【网页权限】授权。",
        )
    return level


async def verify_group_access(
    group_id: int, token: CookieCache = Depends(verify_cookie)
) -> CookieCache:
    """带群归属校验的登录态依赖：/{group_id}/... 系列路由用它替代 verify_cookie。"""
    await ensure_group_access(int(token.user_id), group_id)
    return token


async def get_day_dao(
    dao_data: List[RecordDao], members: Dict[int, str] = None
) -> Tuple[int, list]:
    total = 0
    state = {3: [], 2.5: [], 2: [], 1.5: [], 1: [], 0.5: [], 0: []}
    # 传入完整公会名单（监控开启时）可统计出 0 刀（未出刀）成员
    report_info = await day_report(dao_data, members or {})
    for member in report_info:
        name = member[1]
        dao = min(member[2], 3)
        state[dao].append(name)
        total += dao

    return total, [{"dao_num": dao, "names": state[dao]} for dao in state if state[dao]]


def build_last_dao(dao_data: List[RecordDao], limit: int = 20) -> List[DaoInfo]:
    """把一组出刀记录按时间倒序、取最新 N 条，转成前端 Dashboard 用的 DaoInfo 列表。"""
    # 按时间倒序，最新的在最前面
    sorted_list = sorted(dao_data, key=lambda r: r.time, reverse=True)
    return [
        DaoInfo(
            name=player.name,
            damage=player.damage,
            score=int(clan_boss_info.get_boss_rate(player.lap, player.boss) * player.damage),
            type=daoflag2str(player.flag),
            date=player.time,
            boss=player.boss,
            lap=player.lap,
            dao_id=player.battle_log_id,
        )
        for player in sorted_list[:limit]
    ]


def get_notice_msg(type: int, user_id: int, boss: int, lap: int, msg: str) -> str:
    at_msg = MessageSegment.at(user_id)
    if type == NoticeType.subscribe.value:
        resp = "预约了"
    elif type == NoticeType.apply.value:
        resp = "申请了"
    elif type == NoticeType.tree.value:
        resp = "挂树在了"
    elif type == NoticeType.sl.value:
        return at_msg + "SL了" + (f"\n留言: {msg}" if msg else "")

    resp += f"第{lap}周目" if lap else "当前周目"
    resp += f"{boss}王"
    resp += f"\n留言: {msg}" if msg else ""
    return at_msg + resp


def cancel_notice_msg(
    type: int, user_id: int, boss: int, operator: int = 114514
) -> str:
    operator_msg = (MessageSegment.at(operator) + "使") if operator != user_id else ""
    if type == NoticeType.subscribe.value:
        resp = "取消预约了"
    elif type == NoticeType.apply.value:
        resp = "取消申请了"
    elif type == NoticeType.tree.value:
        resp = "取消挂树在了"
    resp += f"{boss}王"
    return operator_msg + MessageSegment.at(user_id) + resp
