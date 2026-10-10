"""BOX / 助战 与 竞技场 的网页端接口（首页「快捷入口」里那两个新入口的后端）。

这两组功能在 QQ 端分别由 `support_query`（精准助战）和 `jjckiller`（竞技场杀手）
提供。网页端这里刻意只做**薄封装**，不自己登录游戏：

- **BOX / 助战**：纯读本地缓存表（`PlayerUnit` / `SupportUnit`），一次游戏接口都不打
  —— 既不会顶号，也不要求出刀监控在跑。代价是数据新鲜度取决于上一次在群里发
  【刷新box缓存】/【刷新助战缓存】的时间。
  网页端**不复用** QQ 端那套 PIL 出图（`support_query.create_img`）：那边是一次把整个
  box 拼成一张大图，几百个角色又慢又费带宽；这边只返回结构化数据，头像走
  `/{group_id}/box/avatar/{unit_id}` 单独出 PNG，前端做「头像网格 + 点开详情」。
  两边数据源相同，只是呈现方式不同 —— QQ 群指令的行为一个字都没改。
- **竞技场**：排行榜 / 查防守 / 查 ID 都要打游戏接口，必须复用**正在运行的竞技场监控**
  已经登录好的 client（`arena_manager`）。没有监控在跑时一律提示去群里开，
  绝不自己 `query(account)` 登录 —— 那会把正在玩游戏的群友顶下线。
"""

import base64
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import FileResponse
from nonebot import logger
from PIL import Image

from ..basedata import FilePath
from ..database.dal import pcr_sqla
from ..database.models import ArenaSetting, CookieCache
from ..setting import WebSetting
from ..util.tools import name2id
from .util import call_in_main_loop, is_bot_owner, verify_group_access
from .web_model import (
    ArenaDefenceResult,
    ArenaMonitorActionForm,
    ArenaProfileResult,
    ArenaRankResult,
    ArenaRankRow,
    ArenaSettingForm,
    ArenaSolution,
    ArenaStatus,
    BoxCacheRefreshResult,
    BoxExEquip,
    BoxQueryResult,
    BoxUnit,
    GrandCacheRow,
    SupportChangeForm,
    SupportChangeResult,
)

router = APIRouter(prefix=WebSetting.api_base.value)

# 竞技场监控没在跑时的统一提示，避免每个接口各写一份
_NO_ARENA = (
    "当前没有正在运行的竞技场监控。竞技场查询要借用监控已登录的账号去打游戏接口，"
    "请在本页点【开启监控】，或在 QQ 群里发送【竞技场监控】（或【#竞技场监控】）后再来查询。"
)


def _img2data_url(img: Image.Image) -> str:
    """PIL 图片 -> data URL，前端直接塞进 <img :src>。"""
    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _resolve_ids(name: str):
    """角色名 -> 角色 ID 列表。返回 (ids, 错误信息)；ids 为 [-1] 表示「所有」。"""
    return name2id(name.strip())


# ============================ BOX / 助战 ============================
# 不复用 QQ 端整图出图（慢、费带宽），只给结构化数据 + 头像 PNG，前端自己画网格。


def _avatar_star(rarity: int) -> int:
    """真实星级 -> 头像档位。

    游戏只准备了 1 / 3 / 6 三档头像（与 `chara.Chara.get_icon` 的分档一致）：
    1~2 星用 1 档、3~5 星用 3 档、6 星用 6 档。星级未知（0）时给中档，
    别顺手猜成 6 星 —— 那会把一个没缓存的角色显示成满星。
    """
    if rarity >= 6:
        return 6
    if rarity >= 3:
        return 3
    if rarity >= 1:
        return 1
    return 3


_ICON_SRC = "https://redive.estertion.win/icon/unit/{unit_id}{star}1.webp"
# 图源会拦没有 UA 的请求（403），而 hoshino 的 `aiorequests` 不带 UA —— 服务器上
# 那 66 个新角色一直没有头像文件就是这个原因。这里自己带浏览器 UA 抓。
_ICON_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _local_avatar(unit_id: int, star: int):
    """本地已有的头像文件（按 star -> 3 -> 1 降级），没有返回 None。"""
    from hoshino import R

    for s in (star, 3, 1):
        res = R.img(f"priconne/unit/icon_unit_{unit_id}{s}1.png")
        if res.exist:
            return res.path
    return None


def _unknown_avatar():
    """最后的兜底：未知角色占位图（chara.UNKNOWN = 1000）。"""
    from hoshino import R

    res = R.img("priconne/unit/icon_unit_100031.png")
    return res.path if res.exist else None


async def _download_avatar(unit_id: int, star: int):
    """本地没有就去图源抓一张存下来（和 QQ 端出图时的行为一致），失败返回 None。

    只对「角色表里的 id」调用，免得被人拿随机 id 刷下载。
    """
    from hoshino import R

    for s in (star, 3, 1):
        res = R.img(f"priconne/unit/icon_unit_{unit_id}{s}1.png")
        if res.exist:
            return res.path
        try:
            async with httpx.AsyncClient(
                timeout=4.0, headers={"User-Agent": _ICON_UA}
            ) as client:
                rsp = await client.get(_ICON_SRC.format(unit_id=unit_id, star=s))
            if rsp.status_code != 200:
                continue
            Image.open(BytesIO(rsp.content)).convert("RGBA").save(res.path)
            logger.info(f"下载角色头像成功：unit_id={unit_id} star={s}")
            return res.path
        except Exception as e:
            logger.warning(f"下载角色头像失败 unit_id={unit_id} star={s}: {e}")
    return None


# ---- 头像上的星级 ----
# 与 QQ 端 BOX 出图同一套：金=战斗星级、亮蓝=被调星调下去的、淡蓝=没到；6★ 加粉标记。
_STAR_ASSETS = {
    "gold": "16px-星星.png",  # 战斗星级（金色）
    "lower": "16px-星星蓝.png",  # 调星调下去的部分（亮蓝）
    "empty": "16px-星星无.png",  # 还没到 / 没拥有（淡蓝灰）
    "six": "16px-星星6.png",  # 6★ 的第 6 颗（粉色）
}


def _starred_icon_dir() -> Path:
    """合成后的带头像星级缓存目录（别覆盖 `priconne/unit/` 下的原图，QQ 端也在用）。"""
    return FilePath.img.value / "support_query" / "starred_icon"


@lru_cache(maxsize=1)
def _load_star_assets():
    """加载 4 张星星素材（进程内缓存一次）。缺任何一张就整体放弃，调用方退回原图。"""
    base = FilePath.img.value / "support_query"
    imgs = {}
    for key, name in _STAR_ASSETS.items():
        path = base / name
        if not path.exists():
            logger.warning(f"星级素材缺失，头像将不带星星：{path}")
            return None
        imgs[key] = Image.open(path).convert("RGBA")
    return imgs


def _star_kinds(battle_rarity: int, rarity: int) -> tuple:
    """算出头像底部 5 个格子的星星种类，以及要不要补第 6 颗。

    判定**完全照抄** QQ 端 `create_img.draw_star(battle_star, star)`：
      - `star == 6` → 5 颗全金 + 第 6 颗粉色标记（调星不体现）
      - `battle_star` 为真 → 前 `battle_star` 颗金、其余亮蓝
      - `battle_star` 为假 → 前 `star` 颗金、其余淡蓝灰
    改这里之前先对一遍那边的代码。
    """
    rarity = int(rarity or 0)
    battle = int(battle_rarity or 0)
    if rarity >= 6:
        return ("gold",) * 5, True
    if battle:
        return tuple("gold" if i <= battle else "lower" for i in range(1, 6)), False
    return tuple("gold" if i <= rarity else "empty" for i in range(1, 6)), False


def _compose_starred_icon(
    icon_path: str, battle_rarity: int, rarity: int, out_path: Path
) -> Path | None:
    """把「头像 + 底部星级」合成一张图存到 `out_path`，成功返回路径。

    星星的**位置 / 大小**照抄 `hoshino.modules.priconne.chara.Chara.render_icon`：
    一颗 `size // 6`、间距 `round(l * 0.15)`、左右留 `(size - 6*l) // 2`、底部留
    `round(size * 0.05)`；**种类**照抄 QQ 端 `draw_star`（见 `_star_kinds`）。
    """
    if int(rarity or 0) <= 0:
        return None
    assets = _load_star_assets()
    if not assets:
        return None
    try:
        pic = Image.open(icon_path).convert("RGBA")
    except Exception as e:
        logger.warning(f"合成星级头像失败（读不到底图 {icon_path}）：{e}")
        return None

    kinds, need_six = _star_kinds(battle_rarity, rarity)
    size = pic.width
    l = size // 6
    star_lap = round(l * 0.15)
    margin_x = (size - 6 * l) // 2
    margin_y = round(size * 0.05)
    b = size - l - margin_y
    for i, kind in enumerate(kinds):
        a = i * (l - star_lap) + margin_x
        s = assets[kind].resize((l, l), Image.LANCZOS)
        pic.paste(s, (a, b, a + l, b + l), s)
    if need_six:
        a = 5 * (l - star_lap) + margin_x
        s = assets["six"].resize((l, l), Image.LANCZOS)
        pic.paste(s, (a, b, a + l, b + l), s)

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pic.save(out_path)
    except Exception as e:
        logger.warning(f"保存星级头像失败 {out_path}：{e}")
        return None
    return out_path


# 合成规则（星星素材 / 大小 / 位置 / 种类）改了就把这个版本号 +1 —— 缓存文件名带版本号，
# 老文件自然失效，不用手动去服务器上清目录。
_STARRED_ICON_VER = "v2"


def _starred_avatar(
    icon_path: str, unit_id: int, star: int, rarity: int, battle_rarity: int
) -> str | None:
    """「头像 + 底部星级」的缓存路径；不需要 / 合成失败时返回 None（调用方退回原图）。

    缓存按 `(unit_id, star, rarity, battle_rarity)` 落盘：同一个角色不同星级各一张，
    算一次就够，之后每次请求都是读文件。
    三个参数的职责别混：
      - `star` 只是**头像档位** 1/3/6（决定用哪张底图）
      - `rarity` 是**真实星级** 1~6（拥有到几星）
      - `battle_rarity` 是**战斗星级**（调星后的星级，0 = 没调过）
    """
    if int(rarity or 0) <= 0:
        return None
    if not _load_star_assets():
        return None
    out_path = (
        _starred_icon_dir()
        / f"{unit_id}_{star}_{rarity}_{int(battle_rarity or 0)}_{_STARRED_ICON_VER}.png"
    )
    if out_path.exists():
        return str(out_path)
    result = _compose_starred_icon(icon_path, battle_rarity, rarity, out_path)
    return str(result) if result is not None else None


# ---- EX 装备图标（普通 + 会战共用）----
# 本地 {id}.png 优先（autopcr 解包的原图，含彩装）；缺了才抓 pcredivewiki（无彩装）。
_EX_EQUIP_SRC = "https://pcredivewiki.tw/static/images/equipment/icon_equipment_{equipment_id}.png"

# 图源里确实没有的装备 id（进程内缓存）。pcredivewiki 用 **200 + HTML** 表示「没有」
# （彩装全是这样），属于永远不会有、不是网络问题；网络异常不进这里，下次仍会重试。
_MISSING_EX_EQUIP_ICONS: set = set()


def _ex_equip_dir() -> Path:
    return FilePath.img.value / "support_query" / "ex_equipment"


def _ex_equip_unknown() -> str | None:
    path = FilePath.img.value / "support_query" / "unknown.png"
    return str(path) if path.exists() else None


async def _ensure_ex_equip_icon(equipment_id: int) -> Path | None:
    """确保本地有这张 EX 装备图标；返回可用路径，抓不到返回 None。

    本地 `resource/img/support_query/ex_equipment/{id}.png` 优先。要补图去 autopcr 那边取：
    它用 UnityPy 从官方资源 CDN 解包（`autopcr/db/assetmgr.py: ex_equip_icon`），缓存成
    `cache/image/icon_icon_extra_equip_{id}.png`，拷过来改名成 `{id}.png` 即可。
    """
    path = _ex_equip_dir() / f"{equipment_id}.png"
    if path.exists():
        return path
    if equipment_id in _MISSING_EX_EQUIP_ICONS:
        return None
    try:
        async with httpx.AsyncClient(
            timeout=4.0, headers={"User-Agent": _ICON_UA}
        ) as client:
            rsp = await client.get(_EX_EQUIP_SRC.format(equipment_id=equipment_id))
        if rsp.status_code != 200:
            _MISSING_EX_EQUIP_ICONS.add(equipment_id)
            logger.warning(
                f"EX 装备图标图源没有这张（HTTP {rsp.status_code}）："
                f"equipment_id={equipment_id}"
            )
            return None
        try:
            image = Image.open(BytesIO(rsp.content)).convert("RGBA")
        except Exception:
            # 图源「没有这张」是用 200 + HTML 表达的（实测 5 星彩装全是这样），
            # 直接存下去会变成一个坏文件，所以这里必须当成失败。
            _MISSING_EX_EQUIP_ICONS.add(equipment_id)
            logger.warning(
                "EX 装备图标图源返回的不是图片（5 星彩装图源里没有，属正常）："
                f"equipment_id={equipment_id}"
            )
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path)
        logger.info(f"下载 EX 装备图标成功：equipment_id={equipment_id}")
        return path
    except Exception as e:
        # 网络抖动等：**不**记进 _MISSING_EX_EQUIP_ICONS，下次还能重试
        logger.warning(f"下载 EX 装备图标失败 equipment_id={equipment_id}: {e}")
    return None


def _ex_equip_icon_url(equipment_id: int, group_id: int) -> str:
    if not equipment_id:
        return ""
    return (
        f"{WebSetting.api_base.value}/{group_id}/box/ex_equip_icon/{equipment_id}"
    )


# ---- 助战位 -> 游戏「支援设定」界面的三栏 ----
# 与 save_player_units 存库口径一致（+2 偏移）：1/2 冒险、3/4 地下城、5/6 团队战。
SUPPORT_GROUPS = ("dungeon", "clan", "adventure")
_SUPPORT_POSITION_GROUP = {
    1: "adventure",
    2: "adventure",
    3: "dungeon",
    4: "dungeon",
    5: "clan",
    6: "clan",
}


def _support_group(position: int) -> str:
    """助战位 -> 分组 key（认不出来给空串，前端会归到「其他」）。"""
    return _SUPPORT_POSITION_GROUP.get(int(position or 0), "")


def _to_box_unit(unit, group_id: int, ex_rows=None, ex_editable: bool = False) -> BoxUnit:
    """缓存表的一行 -> 前端要的角色条目。

    两个表字段不完全一样（`PlayerUnit` 有 love_level / support_position，
    `SupportUnit` 有 special_attribute），所以缺的字段用 getattr 兜底。

    `ex_rows` 是该玩家 `PlayerExEquip` 缓存里的行（普通 EX 背包 + 穿戴关系），
    只影响详情弹窗里的「普通 EX 槽」；会战 EX（`cb_ex_equip_*`）完全不经过它。
    `ex_editable` 表示这条**是不是当前登录用户自己的**：换装是写操作、永远打在
    当前账号上，所以只有自己的条目才能点着换（见 `BoxUnit.ex_equip_editable`）。
    """
    from hoshino.modules.priconne.chara import fromid

    from ..support_query.util import SELF_SUPPORT_BONUS_TEXT

    unit_id = int(unit.unit_id or 0)
    try:
        chara_name = fromid(unit_id).name
    except Exception:
        chara_name = str(unit_id)

    # 好感：个人 BOX / 我的助战有真实等级，助战只有加成文字（游戏不给助战好感等级）。
    # 有什么显示什么、不去猜；完整加成文字点开才看。
    special_attribute = str(getattr(unit, "special_attribute", "") or "")
    if special_attribute == SELF_SUPPORT_BONUS_TEXT:
        # 刷新助战的人就是他自己时游戏不给加成，这句占位文案当「没有」处理
        special_attribute = ""

    support_position = int(getattr(unit, "support_position", 0) or 0)
    rarity = int(unit.rarity or 0)
    battle_rarity = int(unit.battle_rarity or 0)
    star = _avatar_star(rarity)
    # rarity / battle_rarity 都传给头像接口：它据此在头像底部叠出
    # 「战斗星级金色 + 被调下去的亮蓝 + 没到的淡蓝」（和 QQ 端 BOX 出图一致）
    return BoxUnit(
        unit_id=unit_id,
        chara_name=chara_name,
        player_name=str(unit.name or ""),
        pcrid=int(unit.pcrid or 0),
        avatar=(
            f"{WebSetting.api_base.value}/{group_id}/box/avatar/{unit_id}"
            f"?star={star}&rarity={rarity}&battle_rarity={battle_rarity}"
        ),
        star=star,
        rarity=rarity,
        battle_rarity=battle_rarity,
        level=int(unit.level or 0),
        rank=int(unit.rank or 0),
        # 专武等级 -1 表示「未装备」，要原样带过去（用 or 0 会把它变成 0）
        unique_level=int(unit.unique_level if unit.unique_level is not None else 0),
        unique_level2=int(unit.unique_level2 if unit.unique_level2 is not None else 0),
        love_level=int(getattr(unit, "love_level", 0) or 0),
        special_attribute=special_attribute,
        union_burst=int(unit.union_burst or 0),
        main_1=int(unit.main_1 or 0),
        main_2=int(unit.main_2 or 0),
        ex=int(unit.ex or 0),
        equip_1=str(unit.equip_1 or ""),
        equip_2=str(unit.equip_2 or ""),
        equip_3=str(unit.equip_3 or ""),
        equip_4=str(unit.equip_4 or ""),
        equip_5=str(unit.equip_5 or ""),
        equip_6=str(unit.equip_6 or ""),
        cb_ex_equip_1=int(unit.cb_ex_equip_1 or 0),
        cb_ex_equip_2=int(unit.cb_ex_equip_2 or 0),
        cb_ex_equip_3=int(unit.cb_ex_equip_3 or 0),
        cb_ex_equip_1_level=int(unit.cb_ex_equip_1_level or 0),
        cb_ex_equip_2_level=int(unit.cb_ex_equip_2_level or 0),
        cb_ex_equip_3_level=int(unit.cb_ex_equip_3_level or 0),
        cb_ex_equip_1_icon=_ex_equip_icon_url(int(unit.cb_ex_equip_1 or 0), group_id),
        cb_ex_equip_2_icon=_ex_equip_icon_url(int(unit.cb_ex_equip_2 or 0), group_id),
        cb_ex_equip_3_icon=_ex_equip_icon_url(int(unit.cb_ex_equip_3 or 0), group_id),
        support_position=support_position,
        support_group=_support_group(support_position),
        ex_equips=build_box_ex_equips(unit_id, group_id, ex_rows),
        # 没有缓存行 = 这个账号还没刷过【刷新box缓存】（或确实一件 EX 都没有）。
        # 前端据此提示「先刷新缓存」，而不是把三个空槽当成「你真的没穿装备」。
        ex_equip_known=bool(ex_rows),
        ex_equip_editable=bool(ex_editable),
    )


def build_box_ex_equips(unit_id: int, group_id: int, ex_rows=None) -> List[BoxExEquip]:
    """某个角色的 3 个**普通 EX 槽**（带类别名，空槽也会返回）。

    槽位类别来自模块自带的 `resource/data/unit_ex_equipment_slot.json`
    （`support_query.util.unit_ex_slot_categories`），所以**不依赖缓存**也能显示
    「EX 1 · 拳套 · 未装备」；穿没穿装备则要看 `ex_rows`。

    `ex_rows` 是 `PlayerExEquip` 行（见 `support_query.util.build_player_ex_equips`），
    传空就只给空槽 —— 助战缓存里没有这份数据，属于正常情况。
    """
    # 函数内 import：web 插件可能早于 support_query 插件加载，本文件里其它
    # support_query 的东西也都是函数内 import 的（见 box_query 等处）。
    from ..support_query.ex_equip_data import (
        category_name,
        equipment_name,
        equipment_rarity,
        rarity_name,
        star_from_pt,
        sub_status_entries,
    )
    from ..support_query.util import unit_ex_slot_categories, unpack_sub_status

    categories = unit_ex_slot_categories(unit_id)
    if not categories:
        return []  # 槽位表里没有这个角色（新角色 / 老部署），前端会整块隐藏

    game_unit_id = int(unit_id) * 100 + 1
    by_slot = {}
    for row in ex_rows or []:
        if str(getattr(row, "slot_kind", "") or "") != "ex":
            continue  # 会战槽的装备不算普通 EX
        if int(row.unit_id or 0) != game_unit_id:
            continue  # 穿在别人身上的不显示在这个角色的槽里
        by_slot[int(row.slot or 0)] = row

    cells: List[BoxExEquip] = []
    for index, category in enumerate(categories, start=1):
        row = by_slot.get(index)
        equipment_id = int(row.ex_equipment_id or 0) if row is not None else 0
        rarity = equipment_rarity(equipment_id) if equipment_id else 0
        cells.append(
            BoxExEquip(
                slot=index,
                category=int(category),
                category_name=category_name(int(category)),
                equipped=bool(equipment_id),
                equipment_id=equipment_id,
                name=equipment_name(equipment_id) if equipment_id else "",
                rarity=rarity,
                rarity_name=rarity_name(rarity) if equipment_id else "",
                star=(
                    star_from_pt(equipment_id, int(row.enhancement_pt or 0))
                    if equipment_id
                    else 0
                ),
                # 会不会战专用直接从 id 判定（和 QQ 端 `is_clan_battle_ex_equip` 同口径）
                clan_battle=bool(equipment_id) and equipment_id % 100 == 51,
                icon=_ex_equip_icon_url(equipment_id, group_id) if equipment_id else "",
                # 5 星彩装的 4 条词条（1~4 星装备恒为空列表）
                sub_statuses=(
                    sub_status_entries(
                        equipment_id, unpack_sub_status(getattr(row, "sub_status", ""))
                    )
                    if equipment_id
                    else []
                ),
            )
        )
    return cells


@lru_cache(maxsize=1)
def _all_chara_ids() -> tuple:
    """游戏里全部可获取角色（排除 NPC / 未实装），给「未拥有」占位用。

    判定口径与 `chara.is_npc` 一致：`1000 < id < 1900` 且不在 `UnavailableChara` 里。
    注意 6 星**不是**另一个 id（线上库实测：6 星日和仍是 unit_id=1001、rarity=6），
    所以这里按 id 去重就够了，不会把同一角色的 6 星形态算成「缺一个」。

    结果缓存住（`lru_cache`）：角色表基本不变，每次请求都遍历 334 条没必要。
    `_pcr_data` 被 reload 时这份缓存可能略微滞后，重启进程即可。
    """
    from hoshino.modules.priconne import _pcr_data
    from hoshino.modules.priconne.chara import is_npc

    return tuple(sorted(i for i in _pcr_data.CHARA_NAME if not is_npc(i)))


def _empty_box_unit(unit_id: int, group_id: int) -> BoxUnit:
    """「未拥有」占位条目：只有 id / 角色名 / 头像，前端灰度显示。

    刻意**不带 `rarity`** —— 没拥有就不知道星级，头像上不画星星（画成全灰会让人
    以为是「0 星」，比不画更容易误会）。
    """
    from hoshino.modules.priconne.chara import fromid

    try:
        chara_name = fromid(unit_id).name
    except Exception:
        chara_name = str(unit_id)
    star = 3
    return BoxUnit(
        unit_id=unit_id,
        chara_name=chara_name,
        owned=False,
        avatar=f"{WebSetting.api_base.value}/{group_id}/box/avatar/{unit_id}?star={star}",
        star=star,
    )


@router.get("/{group_id}/box/avatar/{unit_id}")
async def box_avatar(
    group_id: int,
    unit_id: int,
    star: int = 3,
    rarity: int = 0,
    battle_rarity: int = 0,
    token: CookieCache = Depends(verify_group_access),
) -> Response:
    """角色头像 PNG（网页端专用）。

    前端是 `<img :src>` 直接请求，浏览器会自带登录 cookie，所以沿用同一套群权限
    校验就行，不用另开一个免鉴权的口子。

    本地没有的（服务器上从没渲染过的新角色）会去图源抓一次存下来，和 QQ 端出图的
    行为一致；抓不到就退回「未知角色」占位图，不会把页面搞出一堆破图。

    星级（三个参数各管一段，别混）：
      - `star` 头像档位 1/3/6，决定用哪张底图
      - `rarity` 真实星级 1~6（拥有到几星）
      - `battle_rarity` 战斗星级（调星后的星级，0 = 没调过）
    传了 `rarity` 就在头像底部叠一排星星，画法与 QQ 端 BOX 出图一致：
    金色 = 战斗星级、亮蓝 = 拥有但被调星调下去的、淡蓝 = 没到。
    不传 / 传 0（未拥有的占位条目）就出不带星的原图。
    """
    path = _local_avatar(unit_id, star)
    if path is None and unit_id in _all_chara_ids():
        path = await _download_avatar(unit_id, star)

    if path is None:
        path = _unknown_avatar()
        if path is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "没有这个角色的头像资源")
        # 占位图只缓存 1 小时：以后真头像下下来了，别让浏览器一直用旧的
        return FileResponse(
            path, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"}
        )

    # 带星级的版本合成好会存成另一个文件，原来那张不带星的原图仍然可用
    # （`priconne/unit/` 下的原图是 QQ 端出图在用的，绝不能覆盖）。
    starred = _starred_avatar(path, unit_id, star, rarity, battle_rarity)
    if starred is not None:
        path = starred

    # 头像文件基本不变，让浏览器缓存一周，免得每次查询都把几十张图重拉一遍
    return FileResponse(
        path, media_type="image/png", headers={"Cache-Control": "public, max-age=604800"}
    )


@router.get("/{group_id}/box/ex_equip_icon/{equipment_id}")
async def box_ex_equip_icon(
    group_id: int,
    equipment_id: int,
    token: CookieCache = Depends(verify_group_access),
) -> Response:
    """EX 装备图标 PNG（网页端专用；普通 EX 槽和会战 EX 槽共用这一个接口）。

    和 QQ 端出图用的是**同一份资源**：模块自带的
    `resource/img/support_query/ex_equipment/{equipment_id}.png`；本地没有才按需下载
    （存回同一目录，等于顺手把 QQ 端的缓存也补上），最后退回 `unknown.png`。

    注意本地那 234 张是从 autopcr 解包的游戏原图（128×128），pcredivewiki 那个源
    只有铜/银/金/粉、没有 5 星彩装 —— 彩装请以本地文件为准，缺的会走占位图。
    """
    path = await _ensure_ex_equip_icon(equipment_id)
    if path is not None:
        return FileResponse(
            str(path), media_type="image/png",
            headers={"Cache-Control": "public, max-age=604800"},
        )

    unknown = _ex_equip_unknown()
    if unknown is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "没有这个 EX 装备的图标")
    # 占位图只缓存 1 小时：以后真图标下下来了，别让浏览器一直用旧的
    return FileResponse(
        unknown, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"}
    )


@router.get("/{group_id}/box/query", response_model=BoxQueryResult)
async def box_query(
    group_id: int,
    name: str = "",
    include_missing: bool = True,
    token: CookieCache = Depends(verify_group_access),
):
    """个人 BOX 查询。

    `include_missing=True`（默认）时，除了已拥有的角色，还会把**没拥有**的角色也作为
    占位条目带回来（`owned=False`，前端灰度显示）—— 这样「所有」一眼就能看出缺什么。
    传 `include_missing=false` 就是原来的行为（只列已拥有）。
    """
    from ..support_query.util import search_target

    user_id = int(token.user_id)
    if not name.strip():
        return BoxQueryResult(message="请输入要查询的角色名（输入「所有」可以看整个 box）")

    units = await pcr_sqla.get_player_units(user_id)
    if not units:
        return BoxQueryResult(
            message="还没有你的 BOX 缓存，请先在 QQ 群里发送【刷新box缓存】（会短暂顶号）"
        )

    ids, msg = _resolve_ids(name)
    if msg:
        return BoxQueryResult(message=msg)
    if not ids:
        return BoxQueryResult(message=f"无法识别「{name.strip()}」，换个角色名试试")

    owned_units = search_target(ids, units)
    # 详情弹窗里的「普通 EX 槽」要用它：背包清单 + 每件穿在谁身上
    ex_rows = await pcr_sqla.get_player_ex_equips(user_id)
    box_units = [_to_box_unit(u, group_id, ex_rows, True) for u in owned_units]
    owned_count = len(box_units)

    if include_missing:
        owned_ids = {int(u.unit_id) for u in units}
        if ids == [-1]:
            # 「所有」：整个 box + 全部没拥有的角色
            missing = [i for i in _all_chara_ids() if i not in owned_ids]
        else:
            # 指定角色：没拥有也回一条灰度占位，省得用户分不清「没这个角色」和「接口坏了」
            missing = [i for i in ids if i not in owned_ids]
        box_units += [_empty_box_unit(i, group_id) for i in missing]

    if not box_units:
        return BoxQueryResult(message=f"你的 BOX 里没有找到「{name.strip()}」")

    return BoxQueryResult(
        ok=True,
        count=len(box_units),
        owned_count=owned_count,
        missing_count=len(box_units) - owned_count,
        units=box_units,
    )


@router.get("/{group_id}/box/clan", response_model=BoxQueryResult)
async def box_clan_query(
    group_id: int, name: str = "", token: CookieCache = Depends(verify_group_access)
):
    """公会 BOX 查询：本群所有绑定过公会的成员里，谁有这个角色"""
    from ..support_query.util import search_target

    if not name.strip():
        return BoxQueryResult(message="请输入要查询的角色名")
    if name.strip() == "所有":
        return BoxQueryResult(message="不能一次查询所有角色（人太多会卡死），请输入具体角色名")

    ids, msg = _resolve_ids(name)
    if msg:
        return BoxQueryResult(message=msg)
    if not ids:
        return BoxQueryResult(message=f"无法识别「{name.strip()}」，换个角色名试试")

    members = await pcr_sqla.get_group_member(group_id)
    clan_units = []
    for member in members:
        units = await pcr_sqla.get_player_units(member.user_id)
        matched = search_target(ids, units)
        if not matched:
            continue
        # 普通 EX 槽按人算（每人搭配不同），所以每个成员单独取自己的缓存；只有自己那条
        # 能换装 —— 换装永远打在当前登录账号上，点别人那条会张冠李戴。
        ex_rows = await pcr_sqla.get_player_ex_equips(member.user_id)
        ex_editable = int(member.user_id) == int(token.user_id)
        clan_units += [
            _to_box_unit(u, group_id, ex_rows, ex_editable) for u in matched
        ]

    if not clan_units:
        return BoxQueryResult(message=f"本群没有成员的 BOX 里有「{name.strip()}」")

    return BoxQueryResult(
        ok=True,
        count=len(clan_units),
        owned_count=len(clan_units),
        units=clan_units,
    )


@router.get("/{group_id}/support/clan", response_model=BoxQueryResult)
async def support_clan_query(
    group_id: int, name: str = "", token: CookieCache = Depends(verify_group_access)
):
    """公会助战一览：本群缓存的公会战助战（对应 QQ 端【精确助战】）"""
    from ..support_query.util import search_target

    if not name.strip():
        return BoxQueryResult(message="请输入要查询的角色名（输入「所有」可以看全部助战）")

    units = await pcr_sqla.get_support_units(group_id)
    if not units:
        return BoxQueryResult(
            message="本群还没有助战缓存，请先在 QQ 群里发送【刷新助战缓存】（会短暂顶号）"
        )

    ids, msg = _resolve_ids(name)
    if msg:
        return BoxQueryResult(message=msg)
    if not ids:
        return BoxQueryResult(message=f"无法识别「{name.strip()}」，换个角色名试试")

    result = search_target(ids, units)
    if not result:
        return BoxQueryResult(message=f"本群助战里没有找到「{name.strip()}」")

    # 不传 ex_rows：公会助战读的是别的玩家的 SupportUnit，只有 pcrid、对不上 EX 缓存。
    # 也正因为是别人的数据，ex_equip_editable 保持 False（不给换装入口）。
    return BoxQueryResult(
        ok=True,
        count=len(result),
        owned_count=len(result),
        units=[_to_box_unit(u, group_id) for u in result],
    )


@router.get("/{group_id}/support/mine", response_model=BoxQueryResult)
async def support_mine(
    group_id: int, token: CookieCache = Depends(verify_group_access)
):
    """我的助战：当前登录用户挂着的助战（对应 QQ 端【我的助战】）"""
    units = await pcr_sqla.get_player_support_units(int(token.user_id))
    if not units:
        return BoxQueryResult(
            message="你还没有设置助战，或 BOX 缓存里没有助战信息（先在群里发【刷新box缓存】）"
        )

    # 按助战位排序，跟游戏里的支援界面顺序对得上（前端再按 support_group 分三栏）
    ordered = sorted(units, key=lambda u: int(getattr(u, "support_position", 0) or 0))
    # 「我的助战」读的是 `PlayerUnit`，user_id 是知道的，所以**能**带上普通 EX 槽
    ex_rows = await pcr_sqla.get_player_ex_equips(int(token.user_id))
    return BoxQueryResult(
        ok=True,
        count=len(ordered),
        owned_count=len(ordered),
        units=[_to_box_unit(u, group_id, ex_rows, True) for u in ordered],
    )


# ---- 刷新缓存：一个按钮把个人 BOX + 公会助战两份都刷了，共用一次登录（会顶号）----
# 逻辑复用 support_query.util.refresh_box_and_support，与 QQ 端两条指令同源。
_REFRESHING: set = set()


def _login_guard(user_id: int) -> tuple:
    return ("login", int(user_id))


async def _run_refresh(
    kind: str,
    key,
    coro_factory,
    owner: Optional[int] = None,
    to_result: Optional[Callable[[Any], "BoxCacheRefreshResult"]] = None,
) -> "BoxCacheRefreshResult":
    """跑一次刷新，统一处理「正在刷新 / 失败」的返回。`coro_factory` 返回新协程。

    `owner` 是这次登录用的游戏账号主人（QQ），传了就顺带占住账号级闸门。
    `to_result` 把协程的返回值翻成响应模型；不传时按「返回值就是写入条数」处理。
    """
    guards = {(kind, key)}
    if owner is not None:
        guards.add(_login_guard(owner))
    if guards & _REFRESHING:
        return BoxCacheRefreshResult(
            kind=kind, message="正在刷新中，请稍候…（同一时间只允许刷新一次）"
        )
    # 用 update/difference_update 原地改，别写 `_REFRESHING |= guards`
    # —— 那是**重新绑定**模块级名字，函数里会被当成局部变量直接 UnboundLocalError
    _REFRESHING.update(guards)
    try:
        value = await call_in_main_loop(coro_factory())
    except HTTPException as e:
        return BoxCacheRefreshResult(kind=kind, message=f"刷新失败：{e.detail}")
    except Exception as e:
        return BoxCacheRefreshResult(kind=kind, message=f"刷新失败：{e}")
    finally:
        _REFRESHING.difference_update(guards)
    if to_result is not None:
        return to_result(value)
    return BoxCacheRefreshResult(ok=True, kind=kind, count=value, message="刷新成功")


async def _require_account(user_id: int, group_id: int):
    """取当前登录用户绑定的游戏账号；没绑返回 None（调用方转成 ok=False + 提示）。"""
    return await pcr_sqla.query_account_for_group(int(user_id), int(group_id))


@router.post("/{group_id}/refresh", response_model=BoxCacheRefreshResult)
async def refresh_cache(
    group_id: int, token: CookieCache = Depends(verify_group_access)
):
    """一次刷新**个人 BOX + 本群公会助战**两份缓存。

    等价于在群里先后发【刷新box缓存】和【刷新助战缓存】，但**只登录一次**。
    ⚠️ 会顶号：拿你自己绑定的账号登录游戏，正在游戏的你会被挤下线。

    两份是分开写的：公会助战那份失败（例如现在不是会战期间）**不影响个人 BOX**，
    这时 `ok` 仍然是 True，具体原因在 `support_error` 里。
    """
    from ..support_query.util import refresh_box_and_support

    user_id = int(token.user_id)
    account = await _require_account(user_id, group_id)
    if account is None:
        return BoxCacheRefreshResult(
            kind="all",
            message="还没有绑定游戏账号，请先在网页端仪表盘绑定，或在 QQ 私聊我发送【绑定账号帮助】",
        )

    def _combine(value) -> "BoxCacheRefreshResult":
        box_count, support_count, support_error = value
        if support_error:
            message = (
                f"个人 BOX 已刷新（{box_count} 个角色）；"
                f"公会助战没刷成：{support_error}"
            )
        else:
            message = f"刷新成功：{box_count} 个角色 / {support_count} 条助战"
        return BoxCacheRefreshResult(
            ok=True,
            kind="all",
            count=box_count + support_count,
            box_count=box_count,
            support_count=support_count,
            support_error=support_error,
            message=message,
        )

    return await _run_refresh(
        "all",
        user_id,
        lambda: refresh_box_and_support(account, user_id, group_id),
        owner=user_id,
        to_result=_combine,
    )


# ---- 我的助战 → 更换支援：复用 util.change_support_unit（与 QQ 指令同源）----
# ⚠️ 写操作，会登录游戏账号并真的改支援设定（顶号），前端必须先弹确认。


@router.post("/{group_id}/support/change", response_model=SupportChangeResult)
async def support_change(
    group_id: int,
    form: SupportChangeForm,
    token: CookieCache = Depends(verify_group_access),
):
    """把选中的角色挂到指定栏位的助战（对应 QQ 端【上XX支援】）"""
    from ..support_query.util import change_support_unit

    mode = int(form.mode)
    if mode not in (1, 2, 3):
        return SupportChangeResult(ok=False, message="栏位不对，无法更换支援")

    user_id = int(token.user_id)
    account = await _require_account(user_id, group_id)
    if account is None:
        return SupportChangeResult(
            ok=False,
            message="还没有绑定游戏账号，请先在网页端仪表盘绑定，或在 QQ 私聊我发送【绑定账号帮助】",
        )

    # 和刷新缓存共用同一把「同一时间只跑一个」的闸门：这两个操作都会登录游戏账号，
    # 撞在一起只会互相顶号。用户连点两下按钮不该触发两次登录。
    guards = {("support_change", user_id), _login_guard(user_id)}
    if guards & _REFRESHING:
        return SupportChangeResult(
            ok=False, message="正在更换中，请稍候…（同一时间只允许更换一次）"
        )
    _REFRESHING.update(guards)
    try:
        res = await call_in_main_loop(
            change_support_unit(account, int(form.unit_id), mode, group_id)
        )
    except HTTPException as e:
        return SupportChangeResult(ok=False, message=f"更换失败：{e.detail}")
    except Exception as e:
        return SupportChangeResult(ok=False, message=f"更换失败：{e}")
    finally:
        _REFRESHING.difference_update(guards)

    return SupportChangeResult(
        ok=res.ok,
        message=res.message,
        mode=res.mode,
        unit_id=res.unit_id,
        position=res.position,
        removed_unit_id=res.removed_unit_id,
    )


# ============================ 竞技场 ============================


def _get_arena(user_id: int, group_id: int):
    """拿当前可用的竞技场监控（本人开的，或本群的群监控）。

    `arena_manager.get_arena` 只看 `loop_check`，返回 None 就代表没有在跑的监控。
    """
    from ..jjckiller.model import arena_manager

    return arena_manager.get_arena(user_id, group_id)


@router.get("/{group_id}/arena/status", response_model=ArenaStatus)
async def arena_status(
    group_id: int, token: CookieCache = Depends(verify_group_access)
):
    """竞技场中心顶部状态：监控在不在跑 + 两个提醒开关"""
    user_id = int(token.user_id)
    setting = await pcr_sqla.get_jjc_setting(user_id)
    resp = ArenaStatus(
        jjc_notice=bool(setting.jjc_notice) if setting else True,
        grand_notice=bool(setting.grand_notice) if setting else True,
    )

    arena = _get_arena(user_id, group_id)
    if arena is not None:
        resp.running = True
        resp.jjc_rank = int(arena.jjc_rank)
        resp.jjc_group = int(arena.jjc_group)
        resp.grand_rank = int(arena.grand_rank)
        resp.grand_group = int(arena.grand_group)
        resp.loop_num = int(arena.loop_num)
        resp.monitor_user_id = int(arena.user_id)
        resp.is_monitor = resp.monitor_user_id == user_id
    return resp


@router.post("/{group_id}/arena/monitor")
async def arena_monitor_switch(
    group_id: int,
    form: ArenaMonitorActionForm,
    token: CookieCache = Depends(verify_group_access),
):
    """网页端「个人监控」开关：等价于在群里发【竞技场监控】/【取消竞技场监控】。

      - action='on'  ：用**当前登录用户自己绑定**的游戏账号启动监控（方案A硬约束）。
        起来之后本页面的排行榜 / 查防守 / 查 ID 才有账号可用去打游戏接口。
      - action='off' ：监控人本人或 bot 主人可取消。

    ⚠️ 开启会真的登录游戏账号，正在玩游戏的你会被顶下线，前端点击前须确认。
    """
    user_id = int(token.user_id)

    # 延迟导入：防止 web 插件先于 jjckiller 插件启动造成导入环
    try:
        from ..jjckiller import arena_pool
        from ..jjckiller.model import ArenaItem, PrioritizedQueryItem, arena_manager
        from ..login import query
    except Exception as e:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"竞技场插件尚未就绪，请稍后再试（{e}）",
        )

    # —— 关闭监控 ——
    if form.action == "off":
        arena = arena_manager.get_arena(user_id, group_id)
        if arena is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "当前没有在运行的竞技场监控")
        # 权限与 QQ 端一致：只有监控人本人或 bot 主人能取消
        if user_id != arena.user_id and not is_bot_owner(user_id):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "只有监控人本人或 bot 主人可以取消竞技场监控"
            )
        # 与 QQ【取消竞技场监控】等价：loop_num 自增让循环下一轮比对失败自行退出，
        # 同时把 loop_check 置 0，前端立刻能看到「未运行」。
        arena.loop_num += 1
        arena.loop_check = 0
        arena_manager.delete_arena(arena.user_id, None)
        return {"message": "已取消竞技场监控", "loop_num": arena.loop_num}

    if form.action != "on":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"未知 action: {form.action}")

    # —— 开启监控（方案A：只能用当前登录用户自己绑定的账号）——
    accounts = await pcr_sqla.query_account(user_id)
    account = accounts[0] if accounts else None
    if account is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "还没有绑定游戏账号，请先在仪表盘绑定（或私聊机器人发【绑定账号】）后再开启监控",
        )

    # bot_id 传 0（与出刀监控网页端启动一致）：web 请求没有 OneBot 事件、拿不到
    # self_id，而 nonebot 1.x 的 bot 也没有该属性，getattr 会拿到 partial、int() 报错。
    arena = arena_manager.generate_arena(user_id, None)
    bot_id = 0

    async def _init_monitor():
        client = await query(account)
        await arena.init(client, group_id, bot_id, account.platform)

    try:
        await call_in_main_loop(_init_monitor())
    except Exception as e:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "登录角色账号失败，请确认账号信息是否有效（密码 / token 可能已过期）；"
            "可在仪表盘重新绑定这个账号，或在QQ私聊机器人重发【绑定账号】。"
            f"原始错误：{e}",
        )

    loop_num = arena.loop_num

    # 丢进任务池异步起循环（队列在主循环创建，put 也要投递回主循环）
    async def _add_task():
        await arena_pool.add_task(
            PrioritizedQueryItem(data=ArenaItem(arena, loop_num))
        )

    await call_in_main_loop(_add_task())

    return {
        "message": f"已启动个人竞技场监控（编号HN100{loop_num}），请稍后刷新页面查看状态",
        "loop_num": loop_num,
    }


@router.post("/{group_id}/arena/setting")
async def arena_setting(
    group_id: int,
    form: ArenaSettingForm,
    token: CookieCache = Depends(verify_group_access),
):
    """开关竞技场 / 公主竞技场的提醒（等价于 QQ 端【竞技场杀手 开启|关闭 竞技场】）"""
    user_id = int(token.user_id)
    values = {}
    if form.jjc_notice is not None:
        values["jjc_notice"] = bool(form.jjc_notice)
    if form.grand_notice is not None:
        values["grand_notice"] = bool(form.grand_notice)
    if not values:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "没有要修改的设置")

    # ArenaSetting 是开监控时才建的（QQ 端 init_jjc_setting）。网页端用户可能还没开过
    # 监控就想先关掉提醒，直接 update 会 0 行、看起来「设置了没生效」—— 先确保有一行。
    if await pcr_sqla.get_jjc_setting(user_id) is None:
        await pcr_sqla.init_jjc_setting(ArenaSetting(user_id=user_id))
    await pcr_sqla.update_jjc_setting(user_id, values)
    return {"ok": True, "message": "设置成功"}


@router.get("/{group_id}/arena/rank", response_model=ArenaRankResult)
async def arena_rank(
    group_id: int,
    page: int = 1,
    grand: bool = False,
    token: CookieCache = Depends(verify_group_access),
):
    """竞技场排行榜（每页 10 名，1~5 页）。返回结构化数据，由前端绘制。"""
    if not 1 <= page <= 5:
        return ArenaRankResult(message="排行榜页码范围为 1~5")

    arena = _get_arena(int(token.user_id), group_id)
    if arena is None:
        return ArenaRankResult(message=_NO_ARENA)

    try:
        rows = await call_in_main_loop(arena.get_rank_rows(page, grand))
    except HTTPException:
        raise
    except Exception as e:
        return ArenaRankResult(message=f"查询失败：{e}")

    return ArenaRankResult(
        ok=True,
        grand=grand,
        page=page,
        group=int(arena.grand_group if grand else arena.jjc_group),
        rows=[ArenaRankRow(**row) for row in rows],
    )


@router.get("/{group_id}/arena/defence", response_model=ArenaDefenceResult)
async def arena_defence(
    group_id: int,
    rank: int,
    grand: bool = False,
    token: CookieCache = Depends(verify_group_access),
):
    """查指定排名的防守阵容 / 作业（对应 QQ 端【竞技场查防守】）。返回结构化数据，由前端绘制。"""
    if not 1 <= rank <= 500:
        return ArenaDefenceResult(message="排名范围为 1~500")

    arena = _get_arena(int(token.user_id), group_id)
    if arena is None:
        return ArenaDefenceResult(message=_NO_ARENA)

    try:
        data = await call_in_main_loop(arena.get_defence_data(rank, grand))
    except HTTPException:
        raise
    except Exception as e:
        return ArenaDefenceResult(message=f"查询失败：{e}")

    return ArenaDefenceResult(
        ok=True,
        grand=grand,
        rank=int(data.get("rank", rank)),
        name=data.get("name", ""),
        defence=data.get("defence", []),
        solutions=[ArenaSolution(**s) for s in data.get("solutions", [])],
    )


@router.get("/{group_id}/arena/profile", response_model=ArenaProfileResult)
async def arena_profile(
    group_id: int,
    viewer_id: int,
    token: CookieCache = Depends(verify_group_access),
):
    """按游戏 ID 查玩家资料（对应 autopcr 的【查玩家资料】）。

    直接用 `viewer_id` 查（不再要求「竞技场某个排名」），需要本群有竞技场监控在跑
    —— 查询要借用监控已登录的账号去打 profile/get_profile 接口。
    """
    if viewer_id <= 0:
        return ArenaProfileResult(message="请输入有效的玩家 ID（纯数字）")

    arena = _get_arena(int(token.user_id), group_id)
    if arena is None:
        return ArenaProfileResult(message=_NO_ARENA)

    try:
        data = await call_in_main_loop(arena.get_profile_data(viewer_id))
    except HTTPException:
        raise
    except Exception as e:
        return ArenaProfileResult(message=f"查询失败：{e}")

    return ArenaProfileResult(ok=True, **data)


@router.get("/{group_id}/arena/cache", response_model=List[GrandCacheRow])
async def arena_cache(
    group_id: int, token: CookieCache = Depends(verify_group_access)
):
    """公主竞技场防守缓存：监控过程中记录下来的对手防守队伍（纯读库，不需要监控在跑）"""
    from hoshino.modules.priconne.chara import fromid

    from ..jjckiller.base import id_str2list

    rows = await pcr_sqla.list_grand_cache(int(token.user_id))
    result: List[GrandCacheRow] = []
    for row in rows:
        try:
            units = id_str2list(str(row.defence))
        except Exception:
            units = []
        names = []
        for unit_id in units:
            try:
                names.append(fromid(unit_id).name)
            except Exception:
                names.append(str(unit_id))
        result.append(
            GrandCacheRow(
                pcrid=int(row.pcrid),
                grand_id=int(row.grand_id),
                row=int(row.row),
                vs_time=int(row.vs_time or 0),
                units=units,
                names=names,
            )
        )
    return result
