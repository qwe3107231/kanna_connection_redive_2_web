from io import BytesIO
import itertools
from typing import List, Tuple, Union
from PIL import Image, ImageDraw, ImageFont, ImageColor
from dataclasses import dataclass

import httpx

from ..database.models import PlayerUnit, SupportUnit
from ..util.tools import cut_str, get_font_size
from hoshino.modules.priconne.chara import fromid
from ..basedata import FilePath, FontPath
import math

font_cn_path = str(FontPath.pcr_font.value)
res_path = FilePath.img.value / "support_query"

IMAGE_WIDTH = 593
IMAGE_HEIGHT = 788

star_list = [
    Image.open(res_path / "16px-星星.png").convert("RGBA"),
    Image.open(res_path / "16px-星星6.png").convert("RGBA"),
    Image.open(res_path / "16px-星星蓝.png").convert("RGBA"),
    Image.open(res_path / "16px-星星无.png").convert("RGBA"),
]

ex_star_list = [
    Image.open(res_path / "ex_star_white.png").convert("RGBA"),
    Image.open(res_path / "ex_star_grey.png").convert("RGBA"),
    Image.open(res_path / "ex_star_blue.png").convert("RGBA"),
    Image.open(res_path / "ex_star_red.png").convert("RGBA"),
]
im_frame = Image.open(res_path / "frame.png").convert("RGBA").resize((128, 128))


def get_ex_equip_max_star(equipment_id: int) -> int:
    rank = equipment_id % 1000 // 100
    return rank + 2 if rank < 3 else 5


@dataclass
class TextImageInfo:
    w: int
    h: int
    base_x: int
    base_y: int
    text: str


async def draw_star(
    im: Image.Image, battle_star: int, star: int, size: int, x: int, y: int
):
    start1 = star_list[0].resize((size, size), Image.LANCZOS)
    if star == 6:
        start2 = start1
        start3 = star_list[1].resize((size * 12 // 10, size * 12 // 10), Image.LANCZOS)
        im.paste(start3, (x + 6 * size, y - size // 10), mask=start3)
    elif battle_star:
        start2 = star_list[2].resize((size, size), Image.LANCZOS)
    else:
        start2 = star_list[3].resize((size, size), Image.LANCZOS)
        battle_star = star

    for i in range(1, 5 + 1):
        draw_star = start1 if i <= battle_star else start2
        im.paste(draw_star, (x + i * size, y), mask=draw_star)


async def draw_ex_equip_star(
    im: Image.Image, max_star: int, star: int, width: int, x: int, y: int
) -> Image.Image:
    height = width * 37 // 27
    for i in range(1, star + 1):
        draw_star = (
            ex_star_list[2].resize((width, height), Image.LANCZOS)
            if i <= 3
            else ex_star_list[3].resize((width, height), Image.LANCZOS)
        )
        im.paste(draw_star, (x + i * width, y), mask=draw_star)

    for i in range(star + 1, max_star + 1):
        draw_star = (
            ex_star_list[1].resize((width, height), Image.LANCZOS)
            if i <= 3
            else ex_star_list[0].resize((width, height), Image.LANCZOS)
        )
        im.paste(draw_star, (x + i * width, y), mask=draw_star)


async def get_ex_equipment_img(equipment_id, size) -> Image.Image:

    if not equipment_id:
        image = Image.open(res_path / "unknown.png")

    else:
        path = res_path / "ex_equipment" / f"{equipment_id}.png"
        if path.exists():
            image = Image.open(path)
        else:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://pcredivewiki.tw/static/images/equipment/icon_equipment_{equipment_id}.png"
                )
                response.raise_for_status()
                image = Image.open(BytesIO(response.content))
                image.save(path)

    return image.resize((size, size), Image.LANCZOS).convert("RGBA")


async def draw_unit_img(
    info: Union[PlayerUnit, SupportUnit],
    font: ImageFont.ImageFont,
    icon_size: int,
    font_color: Tuple[int, int, int, int],
) -> Image.Image:
    im = Image.open(res_path / "pcr_unit.png").convert("RGBA")

    icon = (
        (await fromid(info.unit_id).get_icon(info.rarity))
        .open()
        .convert("RGBA")
        .resize((icon_size, icon_size), Image.LANCZOS)
    )

    im.paste(icon, (220, 71), mask=icon)
    await draw_star(im, info.battle_rarity, info.rarity, 25, 195, 200)

    draw = ImageDraw.Draw(im)
    info.unique_level = str(info.unique_level) if info.unique_level != -1 else "未装备"
    if info.unique_level2 != -1:
        info.unique_level += f" / {info.unique_level2}"
    try:
        special_attribute = cut_str(f"{info.love_level}级", 20)
    except Exception:
        special_attribute = cut_str(info.special_attribute, 20)
    text = "好感加成：" + "\n                    ".join(special_attribute)
    for text_info in [
        TextImageInfo(*get_font_size(font, info.name), 320, 320, info.name),
        TextImageInfo(*get_font_size(font, str(info.level)), 320, 368, str(info.level)),
        TextImageInfo(*get_font_size(font, str(info.rank)), 320, 464, str(info.rank)),
        TextImageInfo(
            *get_font_size(font, info.unique_level), 320, 416, info.unique_level
        ),
        TextImageInfo(
            *get_font_size(font, str(info.union_burst)), 555, 320, str(info.union_burst)
        ),
        TextImageInfo(*get_font_size(font, str(info.ex)), 555, 464, str(info.ex)),
        TextImageInfo(
            *get_font_size(font, str(info.main_1)), 555, 368, str(info.main_1)
        ),
        TextImageInfo(
            *get_font_size(font, str(info.main_2)), 555, 416, str(info.main_2)
        ),
        TextImageInfo(0, 0, 72, 720, text),
    ]:
        draw.text(
            (text_info.base_x - text_info.w, text_info.base_y - text_info.h),
            text_info.text,
            font_color,
            font,
        )

    for index, equip in enumerate(
        [
            info.equip_1,
            info.equip_2,
            info.equip_3,
            info.equip_4,
            info.equip_5,
            info.equip_6,
        ]
    ):
        i = index % 2
        if equip.isdigit():
            await draw_star(im, 0, int(equip), 18, 95 + i * 370, 80 + 32 * (index - i))
        else:
            w, h = get_font_size(font, equip)
            draw.text(
                (190 + i * 383 - w, 95 + 32 * (index - i) - h), equip, font_color, font
            )

    for index, (equip_id, level) in enumerate(
        [
            (info.cb_ex_equip_1, info.cb_ex_equip_1_level),
            (info.cb_ex_equip_2, info.cb_ex_equip_2_level),
            (info.cb_ex_equip_3, info.cb_ex_equip_3_level),
        ]
    ):
        ex_icon = await get_ex_equipment_img(equip_id, 118)
        im.paste(ex_icon, (43 + 198 * index, 542), mask=ex_icon)
        if equip_id:
            await draw_ex_equip_star(
                im,
                get_ex_equip_max_star(equip_id),
                level,
                16,
                40 + 200 * index,
                630,
            )

    return im


async def generate_box_img(
    all_info: List[Union[PlayerUnit, SupportUnit]],
) -> Image.Image:

    num = len(all_info)
    IMAGE_COLUMN = math.isqrt(num)

    IMAGE_ROW = math.ceil(num / IMAGE_COLUMN)
    base = Image.new(
        "RGB", (IMAGE_COLUMN * IMAGE_WIDTH, IMAGE_ROW * IMAGE_HEIGHT), (0, 0, 0)
    )
    font = ImageFont.truetype(font_cn_path, 20)
    # (77, 76, 81, 255)
    img_list = [
        await draw_unit_img(info, font, 155, (0, 0, 0, 255)) for info in all_info
    ]
    for i, (y, x) in enumerate(
        itertools.product(range(1, IMAGE_ROW + 1), range(1, IMAGE_COLUMN + 1))
    ):
        if i >= num:
            break

        from_image = img_list[i]
        base.paste(from_image, ((x - 1) * IMAGE_WIDTH, (y - 1) * IMAGE_HEIGHT))
    return base


POSITION_LIST = [(1284, 156), (1284, 459), (43, 156), (43, 459), (665, 156), (665, 459)]


async def generate_self_support_img(data: List[PlayerUnit]):
    """
    支援界面图片合成
    """
    im = Image.open(res_path / "support.png").convert("RGBA")  # 支援图片模板
    font = ImageFont.truetype(font_cn_path, 30)
    rgb = ImageColor.getrgb("#4e4e4e")
    support_unit = Image.open(res_path / "support_unit.png").convert(
        "RGBA"
    )  # 一个支援ui模板

    for unit in data:
        bbox = POSITION_LIST[unit.support_position - 1]
        im_yuansu = support_unit.copy()
        c_format = fromid(unit.unit_id, unit.rarity, unit.unique_level)
        avatar = await c_format.render_icon(115)
        im_yuansu.paste(im=avatar, box=(28, 78), mask=avatar)
        im_yuansu.paste(im=im_frame, box=(22, 72), mask=im_frame)
        yuansu_draw = ImageDraw.Draw(im_yuansu)
        yuansu_draw.text(xy=(167, 36.86), text=c_format.name, font=font, fill=rgb)
        yuansu_draw.text(xy=(340, 101.8), text=str(unit.level), font=font, fill=rgb)
        yuansu_draw.text(xy=(340, 159.09), text=str(unit.rank), font=font, fill=rgb)
        im.paste(im=im_yuansu, box=bbox)

    return im
