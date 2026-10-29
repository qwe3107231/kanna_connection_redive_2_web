import time
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Union

from fastapi import Cookie, Depends, HTTPException, status
from nonebot import MessageSegment, logger

from ..basedata import GroupPriority, NoticeType
from ..clanbattle.base import clan_boss_info, day_report
from ..database.dal import pcr_sqla
from ..database.models import (
    CookieCache,
    RecordDao,
    is_overflow_capped,
    raw_damage_of,
)
# 群角色查询 / 权限等级计算已下沉到 util/priority.py（QQ 端也要用，反向 import
# webui 会撞循环导入）。这里 re-export，保持 `from .util import *` 的旧引用可用。
from ..util.priority import (  # noqa: F401
    _OWNER_ROLES,
    call_in_main_loop,
    effective_group_priority,
    fetch_group_role,
    get_member_row,
    is_bot_owner,
    is_group_manager_in,
)
from ..util.tools import daoflag2str
from .web_model import DaoInfo


async def verify_cookie(token: str = Cookie(None)) -> CookieCache:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "请先登录")
    if cookie := await pcr_sqla.web_query_cookie(token):
        if time.time() - cookie.time < 3600 * 7 * 24:
            return cookie
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录过期")


# ---- 群内权限：实现见 util/priority.py（QQ 端与网页端共用一份口径）----


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
            # 合刀尾刀：结算时被截到 BOSS 剩余血量，游戏里的原始伤害另外带上，
            # 前端在伤害格上做悬停提示（否则用户看到「266 万的刀变成 674 万」会困惑）
            damage_raw=raw_damage_of(player),
            score=int(clan_boss_info.get_boss_score(player.lap, player.boss, player.damage)),
            # 合刀尾刀虽然 flag=0（打满 90 秒、刀数仍算 1），但伤害不完整，类型显示「合刀尾刀」
            type=daoflag2str(player.flag, is_overflow_capped(player)),
            date=player.time,
            boss=player.boss,
            lap=player.lap,
            dao_id=player.battle_log_id,
        )
        for player in sorted_list[:limit]
    ]


def build_day_damage_rank(
    dao_data: List[RecordDao], limit: int = 10
) -> Tuple[List[dict], int, int]:
    """按玩家聚合「今日」伤害，返回 (Top N 排行, 全员总伤害, 全员总分数)。

    给仪表盘「今日伤害排行」卡片用。之前那张卡标题写「伤害占比」，实际算的却是
    「按刀数分组的人数占比」（`damageChartData` 里 `value: r.names.length`），
    和左栏「今日出刀分布」读的是同一份 `get_day_dao` 结果，等于把左栏又画了一遍。

    伤害和分数都算：不同 BOSS 的分数系数不同（`get_boss_rate`），打同样的伤害打不同
    的王分数差很多，只看伤害会误导 —— 而公会排名看的是分数。

    这里只聚合、不查库：`dao_data` 就是 dashboard 已经取到的今日 `RecordDao` 列表。

    分数口径与游戏一致：**每个成员累计后取一次整**（不是逐刀取整）。逐刀取整
    （`int(rate*damage)` 再相加）会比游戏内的个人分数少几分，所以这里必须按人
    累计、最后 `int()`；总分则按成员分数相加。
    """
    stat: Dict[int, dict] = {}
    exact_scores: Dict[int, Decimal] = {}
    total_damage = 0
    for record in dao_data:
        score = clan_boss_info.get_boss_score(record.lap, record.boss, record.damage)
        row = stat.setdefault(
            record.pcrid, {"name": record.name, "damage": 0, "score": 0, "dao": 0.0}
        )
        if record.name:
            row["name"] = record.name
        row["damage"] += record.damage
        exact_scores[record.pcrid] = exact_scores.get(record.pcrid, Decimal(0)) + score
        # 完整刀算 1 刀，尾刀 / 补偿刀算 0.5 刀（与 day_report 的口径一致）
        row["dao"] += 1 if record.flag == 0 else 0.5
        total_damage += record.damage

    # 逐人累计后取整；总分 = 每个成员分数相加（与战报/用户口径一致）
    for pcrid, row in stat.items():
        row["score"] = int(exact_scores.get(pcrid, Decimal(0)))
    total_score = sum(row["score"] for row in stat.values())

    rows = sorted(stat.values(), key=lambda r: r["damage"], reverse=True)[:limit]
    for row in rows:
        row["damage_rate"] = (
            round(row["damage"] / total_damage * 100, 2) if total_damage else 0.0
        )
        row["score_rate"] = round(row["score"] / total_score * 100, 2) if total_score else 0.0
    return rows, total_damage, total_score


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
    else:
        # 未知类型兜底：原代码 resp 未赋值就 `resp +=`，会 UnboundLocalError
        # → 接口 500，而且脏数据已经写进库了。调用方现在会先校验类型。
        return at_msg + "更新了通知"

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
    else:
        # 未知类型兜底（同 get_notice_msg）：resp 未赋值就拼接会 UnboundLocalError
        return operator_msg + MessageSegment.at(user_id) + "取消了通知"
    resp += f"{boss}王"
    return operator_msg + MessageSegment.at(user_id) + resp
