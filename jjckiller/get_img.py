from typing import List, Optional, Union
from PIL import Image, ImageDraw, ImageFont
import copy
from hoshino.modules.priconne import chara
from hoshino import R
from loguru import logger
from ..basedata import FilePath, FontPath
from math import ceil
from hoshino.util import filt_message

try:
    thumb_up_i = (
        R.img("priconne/gadget/thumb-up-i.png").open().resize((16, 16), Image.LANCZOS)
    )
    thumb_up_a = (
        R.img("priconne/gadget/thumb-up-a.png").open().resize((16, 16), Image.LANCZOS)
    )
    thumb_down_i = (
        R.img("priconne/gadget/thumb-down-i.png").open().resize((16, 16), Image.LANCZOS)
    )
    thumb_down_a = (
        R.img("priconne/gadget/thumb-down-a.png").open().resize((16, 16), Image.LANCZOS)
    )
    # _im = Image.open(str(FilePath.resource.value / 'jjc' / 'bg_jjc.png'))
    _im_head = Image.open(str(FilePath.img.value / "jjc" / "head.png"))
    _im_body = Image.open(str(FilePath.img.value / "jjc" / "body.png"))
    _im_bottom = Image.open(str(FilePath.img.value / "jjc" / "bottom.png"))
    _im_player = Image.open(str(FilePath.img.value / "jjc" / "player.png"))
    font = ImageFont.truetype(str(FontPath.pcr_font.value), 14)
    set_font = ImageFont.truetype(str(FontPath.pcr_font.value), 40)
except Exception as e:
    logger.exception(e)


async def render_atk_def_teams(
    entries: List[Union[str, dict]],
    defences: List[List[int]],
    defence_name: str,
    defence_rank: int,
    border_pix: int = 30,
) -> Image.Image:
    """
    entries = [ {'atk': [int], 'up': int, 'down': int } ]
    """
    if not entries:
        entries = [
            {"atk": [chara.fromid(id) for id in defence],
             "team_type": "defence"}
            for defence in defences
        ]
    else:
        entries = (
            [
                {"atk": [chara.fromid(id) for id in defence],
                 "team_type": "defence"}
                for defence in defences
            ]
            + [{}]
            + entries
        )
    n = len(entries)
    icon_size = 64
    small_icon_size = 32
    # im = Image.new('RGBA', (5 * icon_size + 242, n * (icon_size + border_pix) - border_pix), (255, 255, 255, 255))
    im = await generate_canvas(n + len(defences) + 1)
    # font = ImageFont.truetype(str(working_dir / 'resources' / 'wqy.ttf'), 14)
    draw = ImageDraw.Draw(im)

    for i, e in enumerate(entries):
        if len(e) == 0:
            continue
        y1 = (i * (icon_size + 5)) + border_pix
        y2 = y1 + icon_size

        if e == "lossunit":
            e = {"atk": [chara.fromid(1701)
                         for _ in range(5)], "team_type": "any"}
        elif e == "placeholder":
            e = {"atk": [chara.fromid(1000)
                         for _ in range(5)], "team_type": "youshu"}
        # e此时只能是dict了
        for j, c in enumerate(e["atk"]):
            x1 = (j * icon_size) + border_pix
            x2 = x1 + icon_size
            # 如使用旧版hoshino（不返回结果），请去掉await
            icon = await c.render_icon(icon_size)
            im.paste(icon, (x1, y1, x2, y2), icon)

        x1 = 5 * icon_size + 10
        if e["team_type"] == "normal":
            x2 = x1 + 16
            try:
                im.paste(
                    thumb_up_a,
                    (x1 + border_pix, y1 + 12, x2 + border_pix, y1 + 28),
                    thumb_up_a,
                )
            except:
                draw.text((x1, y1 + 10), "赞", (0, 0, 0, 255), font)
            try:
                im.paste(
                    thumb_down_a,
                    (x1 + border_pix, y1 + 39, x2 + border_pix, y1 + 55),
                    thumb_down_a,
                )
            except:
                draw.text((x1, y1 + 35), "踩", (0, 0, 0, 255), font)
            draw.text(
                (x1 + 25 + border_pix, y1 +
                 10), f"{e['up']}", (0, 0, 0, 255), font
            )
            draw.text(
                (x1 + 25 + border_pix, y1 +
                 35), f"{e['down']}", (0, 0, 0, 255), font
            )
            try:
                draw.text(
                    (x1 + 96, y1 + 2),
                    comment_text_autolf(
                        f"{e['comment'][0]['nickname']}:{e['comment'][0]['msg']}"
                    ),
                    (0, 0, 0, 255),
                    font,
                )
            except:
                pass
        elif e["team_type"] == "approximation":
            draw.text((x1 + 22, y1 + 22), "近似解", (0, 0, 0, 255), font)
        elif "approximation" in e["team_type"]:
            _, uid_4_1_str, uid_4_2_str = e["team_type"].split(" ")
            draw.text((x1 + 22, y1 - 3), "近似解", (0, 0, 0, 255), font)

            chara_1 = chara.fromid(int(uid_4_1_str))
            icon_1 = await chara_1.render_icon(small_icon_size)
            im.paste(icon_1, (x1 + 22, y1 + 26), icon_1)

            draw.text((x1 + 55, y1 + 32), "→", (0, 0, 0, 255), font)

            try:
                draw.text(
                    (x1 + 110, y1 + 2),
                    comment_text_autolf(
                        f"{e['comment'][0]['nickname']}:{e['comment'][0]['msg']}"
                    ),
                    (0, 0, 0, 255),
                    font,
                )
            except:
                pass
            chara_2 = chara.fromid(int(uid_4_2_str))
            icon_2 = await chara_2.render_icon(small_icon_size)
            im.paste(icon_2, (x1 + 72, y1 + 26), icon_2)
        elif e["team_type"] == "frequency":
            draw.text((x1 + 22, y1 + 22), f"高频解", (0, 0, 0, 255), font)
            try:
                draw.text(
                    (x1 + 110, y1 + 2),
                    comment_text_autolf(
                        f"{e['comment'][0]['nickname']}:{e['comment'][0]['msg']}"
                    ),
                    (0, 0, 0, 255),
                    font,
                )
            except:
                pass
        elif e["team_type"] == "any":
            draw.text((x1 + 22, y1 + 22), "不足四人随便打", (0, 0, 0, 255), font)
        elif e["team_type"] == "defence":
            draw.text(
                (x1 + 22, y1 + 22), f"防守方：{defence_name}", (0, 0, 0, 255), font
            )
            draw.text(
                (x1 + 25 + border_pix, y1 + 35),
                f"排名：{defence_rank}",
                (0, 0, 0, 255),
                font,
            )
    return im


async def generate_canvas(entries_num: int) -> Image.Image:
    space_needed = entries_num * (69)
    body_height = 139
    body_parts_num = ceil(space_needed / body_height)
    im = Image.new(
        "RGBA", [622, (body_parts_num * body_height) +
                 47 + 60], (255, 255, 255, 255)
    )
    im.paste(_im_head, (0, 0))
    for i in range(body_parts_num):
        im.paste(_im_body, (0, 47 + (i * body_height)))
    im.paste(_im_bottom, (0, 47 + (body_parts_num * body_height)))
    return im


def comment_text_autolf(s: str) -> str:
    s = filt_message(s.strip().replace("\n", ""))
    return "\n".join(
        [s[i * 10: (i + 1) * 10] for i in range(min(4, ceil(len(s) / 10)))]
    )


async def generate_player_rank(
    name: str, unit_id: int, rank: int, pcr_id: int, win_num: Optional[int] = None
) -> Image.Image:
    img = _im_player.copy()
    draw = ImageDraw.Draw(img)

    win_num = "不适用" if win_num is None else str(win_num)
    draw.text((500, 15), name, font=set_font, fill="#4A515A")
    draw.text((280, 20), f"{rank}位", font=set_font, fill="white")
    draw.text((670, 75), str(pcr_id), font=set_font, fill="#4A515A")
    draw.text((850, 135), win_num, font=set_font, fill="#4A515A")
    img_unit = await chara.fromid(unit_id).render_icon(160)
    img.paste(img_unit, (17, 17))

    return img


async def general_img(images: List[Image.Image], vertical: bool = False) -> Image.Image:
    if vertical:
        # 竖直拼接
        max_width = max(img.size[0] for img in images)
        total_height = sum(img.size[1] for img in images)
        merged_image = Image.new("RGB", (max_width, total_height))
        x_offset = 0
        for img in images:
            merged_image.paste(img, (0, x_offset))
            x_offset += img.size[1]
    else:
        # 横向拼接
        max_height = max(img.size[1] for img in images)
        total_width = sum(img.size[0] for img in images)
        merged_image = Image.new("RGB", (total_width, max_height))
        y_offset = 0
        for img in images:
            merged_image.paste(img, (y_offset, 0))
            y_offset += img.size[0]

    return merged_image
