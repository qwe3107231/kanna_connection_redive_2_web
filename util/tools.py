import contextlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple, Union

from hoshino.modules.priconne import chara
from hoshino.priv import ADMIN, check_priv
from hoshino.typing import CQEvent
from hoshino.util import filt_message
from nonebot import get_bot
from PIL import ImageFont
from ...multicq_send import group_send
from ..basedata import AllowLevel


def get_qid(ev: CQEvent) -> Tuple[int, bool]:
    return next(
        (
            (int(m.data["qq"]), True)
            for m in ev.message
            if m.type == "at" and m.data["qq"] != "all"
        ),
        (ev.user_id, False),
    )


def other_allow(ev: CQEvent, allow_level: int) -> bool:
    return bool(
        allow_level == AllowLevel.rbq.value
        or (allow_level == AllowLevel.adim.value and check_priv(ev, ADMIN))
    )


def cut_str(obj: str, sec: int) -> str:
    """
    按步长分割字符串
    """
    return [obj[i : i + sec] for i in range(0, len(obj), sec)]


def pcr_date(timeStamp: int) -> datetime:
    now = datetime.fromtimestamp(timeStamp, tz=timezone(timedelta(hours=8)))
    if now.hour < 5:
        now -= timedelta(days=1)
    return now.replace(hour=5, minute=0, second=0, microsecond=0)  # 用5点做基准


def load_config(path: str) -> Union[list, dict]:
    try:
        with open(path, encoding="utf8") as f:
            return json.load(f)
    except Exception:
        return []


def write_config(path: str, config: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False)


async def anywhere_send(msg: str, group_id: int, self_id: Optional[int] = None):
    if not msg or not group_id:
        return
    bot = get_bot()
    for _ in range(2):  # 试两遍
        with contextlib.suppress(Exception):
            if self_id:
                await bot.send_group_msg(
                    self_id=self_id, group_id=group_id, message=msg
                )
            else:
                await group_send(group_id, msg)
            return


def name2id(name: str) -> Tuple[List[int], str]:
    if name == "所有":
        return [-1], ""
    units, unknown = chara.roster.parse_team(re.sub(r"[?？，,_]", "", name))
    if unknown:
        _, name, score = chara.guess_id(unknown)
        if score < 70 and not units:
            unknown = filt_message(unknown)
            return (
                [],
                (
                    f'无法识别"{unknown}"'
                    if score < 70
                    else f'无法识别"{unknown}" 您说的有{score}%可能是{name}'
                ),
            )
    return units, ""


def daoflag2str(flag: int) -> str:
    return "完整刀" if not flag else "尾刀" if flag == 1 else "补偿"


def get_font_size(font: ImageFont.ImageFont, text: str) -> Tuple[int, int]:
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]
