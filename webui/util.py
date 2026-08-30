import time
from typing import Dict, List, Tuple, Union
from nonebot import MessageSegment
from fastapi import Cookie, HTTPException, status

from ..basedata import NoticeType
from ..clanbattle.base import clan_boss_info, day_report
from ..database.dal import pcr_sqla
from ..database.models import CookieCache, RecordDao
from ..util.tools import daoflag2str
from .web_model import DaoInfo


async def verify_cookie(token: str = Cookie(None)) -> CookieCache:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "请先登录")
    if cookie := await pcr_sqla.web_query_cookie(token):
        if time.time() - cookie.time < 3600 * 7 * 24:
            return cookie
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录过期")


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
