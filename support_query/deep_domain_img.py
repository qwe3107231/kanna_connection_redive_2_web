"""公会深域查询的图片渲染。

数据来自游戏内公会成员档案（`support_query.util.get_clan_members_info`）。
本模块只负责把已经整理好的进度数据画成一张卡片图，不发起任何网络请求，
所以出图逻辑可以脱离 nonebot / 游戏客户端单独测试。

版式：深色标题条 + 表头 + 斑马纹数据行，一列到底（成员多时图片会变长，
这是刻意选择 —— 比拆成两栏更好对比同一列里的进度）。每个属性一列，
进度用对应元素颜色的胶囊标签展示（火红 / 水蓝 / 风绿 / 光金 / 暗紫），
未通关的显示灰色占位。

标题栏右侧标「数据时间」，底部可以带一句来源附注（缓存 / 抓取失败退回旧缓存）——
深域数据有本地缓存，不标时间就看不出手上这份有多旧。
"""

from __future__ import annotations

import base64
import io
import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

from ..basedata import TALENT, FontPath

__all__ = [
    "MemberDeepDomain",
    "format_talent_progress",
    "from_payload",
    "generate_deep_domain_img",
    "to_payload",
]

_FONT_PATH = str(FontPath.pcr_font.value)

# ---------------------------------------------------------------- 配色
CANVAS_BG = (237, 240, 246)
CARD_BG = (255, 255, 255)
HEADER_BG = (44, 56, 88)
HEADER_TITLE = (255, 255, 255)
HEADER_SUB = (172, 183, 207)
COL_HEADER_BG = (245, 247, 251)
COL_HEADER_FG = (112, 122, 142)
ROW_BG_A = (255, 255, 255)
ROW_BG_B = (245, 247, 252)
DIVIDER = (233, 237, 244)
NAME_FG = (42, 46, 53)
RANK_BG = (255, 247, 222)
RANK_FG = (152, 112, 22)
EMPTY_BG = (234, 237, 243)
EMPTY_FG = (148, 156, 170)
FOOTER_FG = (142, 152, 168)
PILL_FG = (255, 255, 255)

ELEMENT_COLORS: Dict[str, Tuple[int, int, int]] = {
    "火": (214, 69, 65),
    "水": (46, 134, 193),
    "风": (34, 153, 84),
    "光": (196, 158, 38),
    "暗": (124, 59, 151),
}
DEFAULT_ELEMENT_COLOR = (110, 120, 140)

# ---------------------------------------------------------------- 尺寸
PAD = 26
HEADER_H = 92
COL_HEADER_H = 46
ROW_H = 52
ROW_INNER_H = 48
FOOTER_H = 54
NAME_MIN_W = 172
NAME_MAX_W = 300
RANK_COL_W = 122
ELEM_COL_W = 96
PILL_H = 32
CORNER_RADIUS = 18

_font_cache: Dict[int, ImageFont.FreeTypeFont] = {}


def _font(size: int) -> ImageFont.FreeTypeFont:
    """按字号取字体（缓存，避免每行都重新加载字体文件）"""
    cached = _font_cache.get(size)
    if cached is None:
        cached = ImageFont.truetype(_FONT_PATH, size)
        _font_cache[size] = cached
    return cached


def format_talent_progress(clear_count: int) -> Optional[Tuple[int, int]]:
    """把深域通关次数换算成 (阶段, 层)。

    每 10 次通关升一个阶段。clear_count <= 0（一次都没打过）返回 None，
    交给渲染层显示「未通关」—— 直接套公式会算出 0-10 这种没有意义的结果。
    """
    if not clear_count or clear_count <= 0:
        return None
    return (clear_count - 1) // 10 + 1, (clear_count - 1) % 10 + 1


@dataclass
class MemberDeepDomain:
    """一个成员的深域进度（已从游戏数据整理好，供出图使用）"""

    name: str
    knight_rank: int = 0
    # 元素名 -> (阶段, 层)；缺项或 None 表示未通关
    progress: Dict[str, Optional[Tuple[int, int]]] = field(default_factory=dict)


def to_payload(members: Sequence[MemberDeepDomain], clan_name: str = "") -> str:
    """把出图数据序列化成能落库的 JSON。

    进度写成 "阶段-层" 字符串而不是数组 —— 直接看库里的内容就知道进度到哪了。
    """
    return json.dumps(
        {
            "clan_name": clan_name,
            "members": [
                {
                    "name": member.name,
                    "knight_rank": int(member.knight_rank),
                    "progress": {
                        element: (None if value is None else f"{value[0]}-{value[1]}")
                        for element, value in member.progress.items()
                    },
                }
                for member in members
            ],
        },
        ensure_ascii=False,
    )


def from_payload(payload: str) -> Tuple[str, List[MemberDeepDomain]]:
    """`to_payload` 的逆操作：读缓存时把 JSON 还原成出图数据。

    脏数据一律兜底成「未通关」/ 0，不让一份坏缓存把【公会深域查询】整个打挂。
    """
    data = json.loads(payload)
    members: List[MemberDeepDomain] = []
    for item in data.get("members") or []:
        progress: Dict[str, Optional[Tuple[int, int]]] = {}
        for element, value in (item.get("progress") or {}).items():
            stage, _, level = str(value).partition("-") if value else ("", "", "")
            try:
                progress[element] = (int(stage), int(level))
            except ValueError:
                progress[element] = None
        members.append(
            MemberDeepDomain(
                name=str(item.get("name") or ""),
                knight_rank=int(item.get("knight_rank") or 0),
                progress=progress,
            )
        )
    return str(data.get("clan_name") or ""), members


def _ellipsize(font: ImageFont.FreeTypeFont, text: str, max_w: float) -> str:
    """超宽名字截断加省略号，避免顶穿列宽"""
    if font.getlength(text) <= max_w:
        return text
    trimmed = text
    while trimmed and font.getlength(trimmed + "…") > max_w:
        trimmed = trimmed[:-1]
    return trimmed + "…"


def _draw_pill(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int],
    fg: Tuple[int, int, int] = PILL_FG,
    height: int = PILL_H,
    pad_x: int = 14,
) -> None:
    """在 (cx, cy) 处画一个胶囊标签（两端半圆的圆角矩形 + 居中文字）"""
    width = max(font.getlength(text) + pad_x * 2, height + 12)
    x0, y0 = cx - width / 2, cy - height / 2
    draw.rounded_rectangle(
        (x0, y0, x0 + width, y0 + height), radius=height / 2, fill=fill
    )
    draw.text((cx, cy + 1), text, font=font, fill=fg, anchor="mm")


def _measure_name_col(members: Sequence[MemberDeepDomain]) -> int:
    """成员列宽度：按最长名字撑开，并夹在上下限之间"""
    font = _font(24)
    widest = max((font.getlength(m.name) for m in members), default=0.0)
    return int(max(NAME_MIN_W, min(NAME_MAX_W, widest + 34)))


def _draw_table(
    draw: ImageDraw.ImageDraw,
    members: Sequence[MemberDeepDomain],
    x: float,
    y: float,
    name_w: int,
) -> float:
    """画表格（表头 + 数据行），返回表格宽度"""
    block_w = name_w + RANK_COL_W + len(TALENT) * ELEM_COL_W

    col_x: List[float] = [x, x + name_w]
    for i in range(len(TALENT)):
        col_x.append(x + name_w + RANK_COL_W + i * ELEM_COL_W)

    # --- 表头 ---
    draw.rounded_rectangle(
        (x, y, x + block_w, y + COL_HEADER_H), radius=10, fill=COL_HEADER_BG
    )
    head_font = _font(21)
    head_cy = y + COL_HEADER_H / 2
    draw.text((x + 16, head_cy), "成员", font=head_font, fill=COL_HEADER_FG, anchor="lm")
    draw.text(
        (col_x[1] + RANK_COL_W / 2, head_cy),
        "骑士等级",
        font=head_font,
        fill=COL_HEADER_FG,
        anchor="mm",
    )
    for i, element in enumerate(TALENT):
        draw.text(
            (col_x[2 + i] + ELEM_COL_W / 2, head_cy),
            element,
            font=head_font,
            fill=ELEMENT_COLORS.get(element, DEFAULT_ELEMENT_COLOR),
            anchor="mm",
        )

    # --- 数据行 ---
    name_font = _font(24)
    rank_font = _font(21)
    pill_font = _font(21)
    empty_font = _font(19)
    row_y = y + COL_HEADER_H + 6

    for idx, member in enumerate(members):
        top = row_y + idx * ROW_H
        draw.rounded_rectangle(
            (x, top, x + block_w, top + ROW_INNER_H),
            radius=10,
            fill=ROW_BG_A if idx % 2 == 0 else ROW_BG_B,
        )
        cy = top + ROW_INNER_H / 2

        draw.text(
            (x + 16, cy),
            _ellipsize(name_font, member.name, name_w - 32),
            font=name_font,
            fill=NAME_FG,
            anchor="lm",
        )
        _draw_pill(
            draw,
            col_x[1] + RANK_COL_W / 2,
            cy,
            f"Lv.{member.knight_rank}",
            rank_font,
            RANK_BG,
            RANK_FG,
            height=30,
            pad_x=12,
        )
        for i, element in enumerate(TALENT):
            cx = col_x[2 + i] + ELEM_COL_W / 2
            progress = member.progress.get(element)
            if progress is None:
                _draw_pill(
                    draw, cx, cy, "未通关", empty_font, EMPTY_BG, EMPTY_FG,
                    height=30, pad_x=10,
                )
            else:
                stage, level = progress
                _draw_pill(
                    draw,
                    cx,
                    cy,
                    f"{stage}-{level}",
                    pill_font,
                    ELEMENT_COLORS.get(element, DEFAULT_ELEMENT_COLOR),
                )

    return block_w


def generate_deep_domain_img(
    members: Sequence[MemberDeepDomain],
    clan_name: str = "",
    generated_at: Optional[float] = None,
    footer_note: str = "",
) -> str:
    """把公会成员的深域进度画成一张图，返回 CQ 码（与 util.text2img.image_draw 一致）。

    :param generated_at: 这份数据的抓取时间，画在标题栏「数据时间」后面。
        深域有本地缓存（监控没开时读的是缓存），不把时间标出来就看不出来
        看到的是不是几天前的数据。
    :param footer_note: 底部附注，用来交代数据来源（缓存 / 抓取失败退回旧缓存）。
    :raises ValueError: members 为空 —— 让调用方走文字降级，而不是发一张空图。
    """
    members = list(members)
    if not members:
        raise ValueError("没有成员数据，无法生成深域进度图")

    name_w = _measure_name_col(members)
    block_w = name_w + RANK_COL_W + len(TALENT) * ELEM_COL_W

    table_h = COL_HEADER_H + 6 + len(members) * ROW_H
    width = PAD * 2 + block_w
    height = HEADER_H + 14 + table_h + FOOTER_H

    card = Image.new("RGBA", (width, height), CARD_BG + (255,))
    draw = ImageDraw.Draw(card)

    # --- 标题条 ---
    draw.rectangle((0, 0, width, HEADER_H), fill=HEADER_BG)
    title_font = _font(34)
    title = "公会深域进度"
    draw.text(
        (PAD, HEADER_H * 0.36), title, font=title_font, fill=HEADER_TITLE, anchor="lm"
    )
    draw.text(
        (PAD + title_font.getlength(title) + 18, HEADER_H * 0.36),
        f"共 {len(members)} 人",
        font=_font(22),
        fill=HEADER_SUB,
        anchor="lm",
    )
    small_font = _font(20)
    stamp = time.time() if generated_at is None else generated_at
    stamp_text = "数据时间 " + time.strftime("%m-%d %H:%M", time.localtime(stamp))
    if clan_name:
        # 公会名太长会盖住右边的时间戳，先按剩余宽度截断
        room = width - PAD * 2 - small_font.getlength(stamp_text) - 28
        draw.text(
            (PAD, HEADER_H * 0.74),
            _ellipsize(small_font, f"公会：{clan_name}", room),
            font=small_font,
            fill=HEADER_SUB,
            anchor="lm",
        )
    draw.text(
        (width - PAD, HEADER_H * 0.74),
        stamp_text,
        font=small_font,
        fill=HEADER_SUB,
        anchor="rm",
    )

    # --- 表格 ---
    table_y = HEADER_H + 14
    _draw_table(draw, members, PAD, table_y, name_w)

    # --- 底部说明 ---
    footer_y = table_y + table_h
    draw.line((PAD, footer_y, width - PAD, footer_y), fill=DIVIDER, width=2)
    footer = "进度格式「阶段-层」 · 数据来自游戏内公会档案"
    if footer_note:
        footer += f" · {footer_note}"
    footer_font = _font(19)
    draw.text(
        (PAD, footer_y + FOOTER_H / 2),
        # 附注是调用方给的，长度不可控 —— 顶出去就截断
        _ellipsize(footer_font, footer, width - PAD * 2),
        font=footer_font,
        fill=FOOTER_FG,
        anchor="lm",
    )

    # --- 整体圆角 ---
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, width - 1, height - 1), radius=CORNER_RADIUS, fill=255
    )
    canvas = Image.new("RGBA", (width, height), CANVAS_BG + (255,))
    canvas.paste(card, (0, 0), mask)

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="PNG")
    return f"[CQ:image,file=base64://{base64.b64encode(buf.getvalue()).decode()}]"
