import base64
import bisect
import contextlib
import functools
import gzip
import json
import time

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd
from hoshino.modules.priconne.chara import fromid
from nonebot import logger
from ..client.common import (
    ChangeRarityUnit,
    ExtraEquipChangeSlot,
    ExtraEquipChangeUnit,
    ExtraEquipInfo,
    ExtraEquipSlot,
    SupportUnitSetting,
    UnitDataForClanMember,
)
from ..database.models import Account, PlayerExEquip, PlayerUnit, SupportUnit
from ..login import query
from ..database.dal import pcr_sqla
from ..errorclass import ApiException
from ..basedata import EquipRankExp, FilePath, TALENT, UNIT_ROLE
from . import ex_equip_data
from ..client.response import (
    ClanBattleSupportUnitList2Response,
    InventoryInfo,
    LoadIndexResponse,
    ClanBattleSupportUnitLight,
    ProfileGetResponse,
    UnitData,
    UserChara,
)

unique_equipment_enhance_data = [
    [
        (0, 10),
        (90, 15),
        (240, 25),
        (490, 40),
        (890, 50),
        (1390, 60),
        (1990, 75),
        (2740, 100),
    ],
    [50, 60, 75, 95, 120, 150],
]
ex_equip_enhance_data = [
    (150, 400, 800),
    (150, 400, 800, 1300),
    (800, 1800, 3000, 4400, 6000),  # 后面一样了
]

# 刷新助战的人就是他自己时，游戏不给好感加成 —— 用这句占位，别当真正的加成用。
# （网页端 `webui.box_arena_api` 把它当成「没有加成」处理，两边要一致。）
SELF_SUPPORT_BONUS_TEXT = "刷新者本人，不显示加成"

bonus_dict = {
    "atk": "物理攻击力",
    "crt": "物理暴击率",
    "matk": "魔法攻击力",
    "mcrt": "魔法暴击率",
    "erec": "TP自动回复",
    "hp": "血量",
    "def": "物理防御力",
    "mdef": "魔法防御力",
    "hrec_rate": "回复量上升",
    "erec_rate": "TP上升",
}


def search_target(
    targets: List[int], units: List[Union[PlayerUnit, SupportUnit]]
) -> List[Union[PlayerUnit, SupportUnit]]:
    # 空参数（只发了【box查询】/【精确助战】没带名字）时 name2id 返回空列表，
    # 直接 targets[0] 会 IndexError，表现为指令毫无反应。
    if not targets:
        return []
    return (
        units
        if targets[0] == -1
        else [unit for unit in units if unit.unit_id in targets]
    )


async def get_support_list(
    info: str, account: Account
) -> Union[ClanBattleSupportUnitList2Response, LoadIndexResponse]:
    return await get_support_list_with_client(info, await query(account))


async def get_support_list_with_client(
    info: str, client
) -> Union[ClanBattleSupportUnitList2Response, LoadIndexResponse]:
    """同 `get_support_list`，但复用**已经登录好**的 client。

    已经手里有 client 的地方（更换支援、一次刷两份缓存）走这个，就**不会再 `query()`**
    —— `query` 里的 `check_client` 一旦失败就会 `login()`，那会把正在玩游戏的群友顶下线。
    """
    if info == "support_query":
        home_index = await client.home_index()
        return await client.support_unit_list_2(home_index.user_clan.clan_id)
    if info == "self_query":
        return await client.load_index()


async def get_clan_members_info(account: Account) -> List[ProfileGetResponse]:
    client = await query(account)
    home_index = await client.home_index()
    clan_info = await client.clan_info(home_index.user_clan.clan_id)
    return [
        await client.profile_get(member.viewer_id) for member in clan_info.clan.members
    ]


async def get_clan_members_info_with_client(
    client,
) -> Tuple[str, List[ProfileGetResponse]]:
    """深域查询专用：用一个**已经登录好**的 client 同时拿到公会名和成员档案。

    参数刻意收 client 而不是 Account：这条路径只允许在「出刀监控正在跑」时走
    （监控的 client 已经登录着，直接复用不会再登录一次）。绝不能在这里自己
    `query(account)` —— 监控没开、账号正被群友自己登录着的时候，`query` 里的
    `check_client` 一旦失败就会重新 `client.login()`，把人**顶下线**。

    比 get_clan_members_info 多返回一个公会名，出图要显示在标题条上。
    """
    home_index = await client.home_index()
    clan_info = await client.clan_info(home_index.user_clan.clan_id)
    members = [
        await client.profile_get(member.viewer_id) for member in clan_info.clan.members
    ]
    detail = clan_info.clan.detail
    clan_name = (detail.clan_name if detail else "") or ""
    return clan_name, members


def equip_exp2star(num: int, exp: int, rank: int) -> str:
    if num == 0:
        return "未装备"
    elif rank < 4:  # 没星
        return "已装备"
    elif 4 <= rank < 7:  # 3星
        return next(
            (
                str(i)
                for i in range(3)
                if EquipRankExp.sliver.value[i]
                <= exp
                < EquipRankExp.sliver.value[i + 1]
            ),
            "3",
        )
    elif 7 <= rank < 11:
        for i in range(5):
            if EquipRankExp.golden.value[i] <= exp < EquipRankExp.golden.value[i + 1]:
                return str(i)
    else:  # 以后都一样了
        for i in range(5):
            if EquipRankExp.purple.value[i] <= exp < EquipRankExp.purple.value[i + 1]:
                return str(i)
    return "5"


def ex_equip_exp2star(exp: int, equipment_id: int) -> int:
    if not equipment_id:
        return 0
    rank = equipment_id % 1000 // 100
    rank = 2 if rank > 3 else rank - 1
    exp_list = ex_equip_enhance_data[rank]
    return next(
        (i for i, star_exp in enumerate(exp_list) if exp < star_exp),
        len(exp_list),
    )


def get_unique_equip_level_from_pt(is_have: int, exp: int, slot_num=1) -> int:
    if is_have == 0:
        return -1
    if slot_num == 1:
        unquie_equip = unique_equipment_enhance_data[0]
        if exp <= unquie_equip[0][0]:  # z专武初始1级
            level = 1 + (exp / unquie_equip[0][1])
        elif exp <= unquie_equip[-1][0]:  # 一开始毫无规律，打表
            for index, stage in enumerate(unquie_equip):
                low = stage[0]
                if low < exp <= unquie_equip[index + 1][0]:
                    level = (exp - low) / stage[1] + index * 10
        else:  # 后面每升10级，升一级所需经验值+25，10级为一组，等差数列
            exp -= unquie_equip[-1][0]
            # 等差公式求出经验值多余多少个10级，向下取整
            n = int((-7 + (49 + 4 * exp / 125) ** 0.5) / 2)
            if n <= 7:  # 算出多多少级
                level = 70 + 10 * n + (exp - 875 * n - 125 * (n) ** 2) / (75 + 25 * n)
            else:  # 每次需要250经验值值时不再增长
                n = 7
                level = 70 + 10 * n + (exp - 875 * n - 125 * (n) ** 2) / 250
        return int(level)
    else:  # slot_num == 2
        unquie_equip = unique_equipment_enhance_data[1]
        return next(
            (index for index, stage in enumerate(unquie_equip) if exp <= stage),
            0,
        )


def letter2chinese(bonus_param: dict) -> str:
    bouns = ""
    for letter in list(bonus_param):
        if not bonus_param[letter]:
            continue
        if letter in bonus_dict:
            bouns += f"{bonus_dict[letter]}：{bonus_param[letter]}，"
    return bouns[:-1]


def parse_unit_data(unit_data: UnitData) -> dict:
    unit_info = {
        "unit_id": unit_data.id // 100,
        "rarity": unit_data.unit_rarity,
        "battle_rarity": unit_data.battle_rarity,
        "unique_level": -1,
        "unique_level2": -1,
        "level": unit_data.unit_level,
        "rank": unit_data.promotion_level,
        **{f"cb_ex_equip_{i}": None for i in range(1, 3 + 1)},
        **{f"cb_ex_equip_{i}_level": None for i in range(1, 3 + 1)},
    }

    if unit_data.unique_equip_slot:
        unique_level = get_unique_equip_level_from_pt(
            unit_data.unique_equip_slot[0].is_slot,
            unit_data.unique_equip_slot[0].enhancement_pt,
        )
        unit_info["unique_level"] = unique_level
        if len(unit_data.unique_equip_slot) > 1:
            unique_level2 = get_unique_equip_level_from_pt(
                unit_data.unique_equip_slot[1].is_slot,
                unit_data.unique_equip_slot[1].enhancement_pt,
                slot_num=2,
            )
            unit_info["unique_level2"] = unique_level2

    for equip_id in range(6):
        unit_info[f"equip_{equip_id+1}"] = equip_exp2star(
            unit_data.equip_slot[equip_id].is_slot,
            unit_data.equip_slot[equip_id].enhancement_pt,
            unit_data.promotion_level,
        )

    unit_info["union_burst"] = unit_data.union_burst[0].skill_level
    with contextlib.suppress(IndexError):
        unit_info["main_1"] = unit_data.main_skill[0].skill_level
        unit_info["main_2"] = unit_data.main_skill[1].skill_level
        unit_info["ex"] = unit_data.ex_skill[0].skill_level

    for i, ex_equip in enumerate(unit_data.cb_ex_equip_slot, 1):
        unit_info[f"cb_ex_equip_{i}"] = ex_equip.ex_equipment_id
        unit_info[f"cb_ex_equip_{i}_level"] = ex_equip_exp2star(
            ex_equip.enhancement_pt, ex_equip.ex_equipment_id
        )
    return unit_info


async def save_support_units(
    support_units: List[Union[ClanBattleSupportUnitLight, UnitData]],
    gid: int,
    name: str,
    viewer_id: int,
):
    temp_units = []
    for unit in support_units:
        if isinstance(unit, ClanBattleSupportUnitLight):
            unit_data = unit.unit_data
            unit_info = {
                "pcrid": unit.owner_viewer_id,
                "name": unit.owner_name,
            }
        else:
            unit_data = unit
            unit_info = {"pcrid": viewer_id, "name": name}
        unit_info.update(parse_unit_data(unit_data))
        unit_info.update(
            {
                "group_id": gid,
                "special_attribute": (
                    letter2chinese(unit_data.bonus_param.dict())
                    if unit_data.bonus_param
                    else SELF_SUPPORT_BONUS_TEXT
                ),
            }
        )
        temp_units.append(SupportUnit(**unit_info))
    await pcr_sqla.refresh_support_units(temp_units, gid)


async def save_player_units(
    units: List[UnitData],
    loves: List[UserChara],
    user_ex_equip: List[ExtraEquipInfo],
    qid: int,
    name: str,
    viewer_id: int,
    friend_support_list: List[SupportUnitSetting],
    support_list: List[UnitDataForClanMember],
):
    temp_units = []
    love_dict = {love.chara_id: love.love_level for love in loves}
    friend_support_ids = {
        support.unit_id: support.position for support in friend_support_list
    }
    clan_supposrt_ids = {support.unit_id: support.position for support in support_list}

    unit_ex_equip_dict = {
        equip.serial_id: (equip.ex_equipment_id, equip.enhancement_pt)
        for equip in user_ex_equip
    }
    for unit_data in units:
        for equip in unit_data.cb_ex_equip_slot:
            if equip.serial_id:
                equip.ex_equipment_id, equip.enhancement_pt = unit_ex_equip_dict.get(
                    equip.serial_id, (0, 0)
                )
        unit_info = parse_unit_data(unit_data)
        # `user_chara_info` 不一定覆盖 unit_list 里的每个角色（新角色 / 数据没同步全），
        # 裸下标会 KeyError 把整次【刷新box缓存】搞失败，缺的按 0 好感处理。
        love_level = love_dict.get(unit_info["unit_id"], 0)
        unit_info.update(
            {
                "love_level": love_level,
                "user_id": qid,
                "pcrid": viewer_id,
                "name": name,
                "support_position": friend_support_ids.get(unit_data.id, 0),
            }
        )
        if not unit_info["support_position"] and unit_data.id in clan_supposrt_ids:
            unit_info["support_position"] = clan_supposrt_ids[unit_data.id] + 2

        temp_units.append(PlayerUnit(**unit_info))
    await pcr_sqla.refresh_player_units(temp_units, qid)


class SupportRefreshError(Exception):
    """刷新缓存时的业务错误（例如「现在不是会战期间」）。

    QQ 端把它转成一句群消息，网页端把它转成 `ok=False` + message —— 两边提示不同，
    但**判定逻辑只有一份**。
    """


def _self_clan_support_units(self_support: LoadIndexResponse) -> List[UnitData]:
    """自己挂在**团队战位**的助战。

    游戏侧 clan 位 3/4 = 库口径 `support_position` 5/6（见 `save_player_units` 的 +2 偏移）。
    `support_unit_list_2`（会战支援列表）**不含自己**，所以公会助战缓存里自己那两条得从
    自己的 `load_index` 里补 —— 线上库实测：每个成员恰好 2 条 = 团队战栏两个格子，
    而测试号那两条的 `special_attribute` 正是这里写的占位文案。

    顺带把会战 EX 的真实数值补上 —— `load_index` 里只有 `serial_id`。
    """
    unit_ids = {
        unit.unit_id
        for unit in (self_support.dispatch_units or [])
        if unit.position in (3, 4)
    }
    units = [unit for unit in self_support.unit_list if unit.id in unit_ids]
    if units:
        unit_ex_equip_dict = {
            equip.serial_id: (equip.ex_equipment_id, equip.enhancement_pt)
            for equip in self_support.user_ex_equip
        }
        for unit in units:
            for equip in unit.cb_ex_equip_slot:
                if equip.serial_id:
                    equip.ex_equipment_id, equip.enhancement_pt = (
                        unit_ex_equip_dict.get(equip.serial_id, (0, 0))
                    )
    return units


async def save_clan_support(
    client, group_id: int, self_support: LoadIndexResponse
) -> int:
    """用**已经登录好**的 client 重拉本群公会助战并覆盖写缓存，返回写入条数。

    `self_support` 是同一账号的 `load_index()` 结果（用来补自己挂的团队战助战）。
    不在会战期间时抛 `SupportRefreshError`。

    刻意收 client 而不是 Account：调用方（更换支援、一次刷两份缓存）都已经登录过了，
    再 `query(account)` 一次纯属多余，而且 `check_client` 失败时还会重新登录顶号。
    """
    try:
        support = await get_support_list_with_client("support_query", client)
    except ApiException as e:
        # callapi 已经把 server_error 转成 ApiException 抛出来了；原来的
        # `if "server_error" in support` 是对 pydantic 模型做 `in` 判断，永远 False
        # （而且根本走不到），群里表现为「指令没有任何回复、只有后台报错」。
        # 带上原始 message：这里也会兜到会话过期/风控等其它 result_code，
        # 只说「可能不是会战期间」会把用户带偏。
        raise SupportRefreshError(f"可能现在不是会战的时候或者网络异常（{e}）") from e
    self_unit_list = _self_clan_support_units(self_support)
    await save_support_units(
        support.support_unit_list + self_unit_list,
        group_id,
        self_support.user_info.user_name,
        self_support.user_info.viewer_id,
    )
    return len(support.support_unit_list) + len(self_unit_list)


async def refresh_player_box(account: Account, qid: int) -> int:
    """刷新个人 BOX 缓存，返回写入的角色数。

    QQ 群【刷新box缓存】共用这一份逻辑。
    ⚠️ **会顶号**：`get_support_list` 里的 `query(account)` 会真正登录游戏账号，
    正在用这个号玩游戏的群友会被挤下线。
    """
    return await _save_player_box(await get_support_list("self_query", account), qid)


_TALENT_LEVEL_POINTS: Tuple[int, ...] = ()


def _talent_level_points() -> Tuple[int, ...]:
    """属性等级阈值表：`points[i]` = 升到 `i+1` 级所需的累计点数

    游戏主库的 `experience_talent_level` 表太大，网页端只导出了这一列
    （`resource/data/talent_level.json`，见 `.workbuddy-ai/export_talent_level.py`）。

    读不到就返回空元组（练度条显示成「未知」，不影响其它功能），但**不缓存失败结果**：
    以前用 `lru_cache` 会把「文件还没同步过来」那次失败一直记着，之后补上文件也得重启
    才能恢复。现在只有读成功才记，失败下次再试。
    """
    global _TALENT_LEVEL_POINTS
    if _TALENT_LEVEL_POINTS:
        return _TALENT_LEVEL_POINTS
    path = FilePath.data.value / "talent_level.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        points = payload.get("points") or []
    except Exception as e:
        logger.warning(f"读取属性等级表失败：{e!r}")
        return ()
    _TALENT_LEVEL_POINTS = tuple(int(point) for point in points)
    return _TALENT_LEVEL_POINTS


# 「属性技能」节点表：node_id -> (page_num, pos_x, 是否合流节点)
# 同样只在读成功时缓存（理由见 `_talent_level_points`）。
_TALENT_SKILL_NODES: Dict[int, Tuple[int, int, bool]] = {}

# 属性技能的三条主线（游戏 `talent_skill_node.pos_x`：2 左 / 5 中 / 8 右）
_SKILL_POS_LABELS = {2: "左", 5: "中", 8: "右"}

# 星幽碎片：点属性技能消耗的材料（游戏 Item 25021）
_XINYOU_ITEM_ID = 25021


def _talent_skill_nodes() -> Dict[int, Tuple[int, int, bool]]:
    """读「属性技能」节点表（`resource/data/talent_skill_node.json`）

    网页端要复现 autopcr 的「第N页 第M合流 左2[5级]/中1[3级]」，就得知道每个节点
    属于第几页、在哪条主线（左/中/右）、是不是合流节点 —— 这些都在游戏主库里，
    这里只导出这三列（638 个节点 ≈ 24KB）。读不到返回空字典，属性技能那一行就不画。
    """
    global _TALENT_SKILL_NODES
    if _TALENT_SKILL_NODES:
        return _TALENT_SKILL_NODES
    path = FilePath.data.value / "talent_skill_node.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        nodes = payload.get("nodes") or []
    except Exception as e:
        logger.warning(f"读取属性技能节点表失败：{e!r}")
        return {}
    _TALENT_SKILL_NODES = {
        int(node["id"]): (int(node["page"]), int(node["x"]), bool(node["join"]))
        for node in nodes
    }
    return _TALENT_SKILL_NODES


def _inventory_count(load_index: LoadIndexResponse, item_id: int) -> int:
    """背包里某个道具的数量（`load/index` 的 item_list + material_list 都翻一遍）"""
    for group in (
        getattr(load_index, "item_list", None) or [],
        getattr(load_index, "material_list", None) or [],
    ):
        for item in group:
            if int(getattr(item, "id", 0) or 0) == int(item_id):
                return int(getattr(item, "stock", 0) or 0)
    return 0


def build_talent_skill_info(load_index: LoadIndexResponse) -> Optional[dict]:
    """「属性技能」进度 → 前端能直接画的结构（口径照 autopcr 的 `get_talent_skill_info`）

    游戏只给「最后一次强化的那一页」的节点列表（`talent_skill_last_enhanced_page_node_list`，
    每项 = node_id + enhance_level），所以显示成：

      - `page`：这一页是第几页（查节点表）
      - `joined_count`：这一页已经解锁到第几个合流节点（= 列表里合流节点的个数）
      - `branches`：最后一个合流节点**之后**的节点，按左/中/右三条线分组，
        每组给「点了几个」+「最高几级」（autopcr 的 `左2[5级]`）
      - `last_joined_level`：合流之后没有新节点时，显示最后一个合流节点的等级
        （autopcr 的 `第3页 第12合流[4级]`）
      - `leftover`：星幽碎片剩余（autopcr 的 `(余123)`）

    没点过属性技能（列表为空）或没有节点表时返回 None —— 前端整行不画。
    `raw_nodes` 只存在落库的 JSON 里（前端模型不解析），以后要改显示口径可以直接
    从库里重算，不用再让用户刷一次缓存。
    """
    knight = getattr(load_index, "princess_knight_info", None)
    if knight is None:
        return None
    nodes = getattr(knight, "talent_skill_last_enhanced_page_node_list", None) or []
    if not nodes:
        return None
    table = _talent_skill_nodes()
    if not table:
        return None

    def info(node) -> Tuple[int, int, bool]:
        return table.get(int(getattr(node, "node_id", 0) or 0), (0, 0, False))

    page = info(nodes[0])[0]
    joined = [node for node in nodes if info(node)[2]]
    # 与 autopcr 一致：没解锁任何合流节点时按 node_id=1 兜底
    max_joined = max(joined, key=lambda n: int(n.node_id), default=None)
    max_joined_id = int(max_joined.node_id) if max_joined is not None else 1

    groups: Dict[int, list] = {}
    for node in nodes:
        node_id = int(getattr(node, "node_id", 0) or 0)
        if node_id <= max_joined_id:
            continue
        groups.setdefault(info(node)[1], []).append(node)

    branches = [
        {
            "pos": _SKILL_POS_LABELS.get(pos_x, "未知"),
            "count": len(group),
            "level": max(int(getattr(n, "enhance_level", 0) or 0) for n in group),
        }
        for pos_x, group in sorted(groups.items())
    ]
    last_joined_level = (
        int(getattr(max_joined, "enhance_level", 0) or 0) if max_joined is not None else 0
    )

    return {
        "page": page,
        "joined_count": len(joined),
        "last_joined_level": last_joined_level,
        "branches": branches,
        "leftover": _inventory_count(load_index, _XINYOU_ITEM_ID),
        # 原始节点（前端不用），留着以后改口径时从库里重算
        "raw_nodes": [
            [int(getattr(n, "node_id", 0) or 0), int(getattr(n, "enhance_level", 0) or 0)]
            for n in nodes
        ],
    }


def talent_level_of(point: int) -> int:
    """属性累计点数 → 属性等级（1 级 = 0 点；阈值表缺失时返回 0）"""
    points = _talent_level_points()
    if not points:
        return 0
    return bisect.bisect_right(points, int(point or 0))


def build_player_enhance(load_index: LoadIndexResponse) -> dict:
    """把一份 `load_index` 快照里的练度整理成网页端能直接画的 dict

    只取网页端「个人 BOX」练度条要展示的三块（都在 `load_index` 里，不用额外打接口）：

      - **属性强化**：`princess_knight_info.talent_level_info_list` 里每个属性的累计点数，
        按阈值表换算成属性等级（火/水/风/光/暗）；
      - **MP 等级**：`princess_knight_info.team_skill_latest_node.node_id` ——
        社区说的「MP23」就是点到第 23 个大师技能节点；
      - **职介等级**：`unit_role_list` 里 8 个职阶、每个 4 个板块的等级 / 星级。

    刻意**只返回数据里真有的东西**：老号 / 还没开属性系统的区服可能整块是空的，
    前端看到空数组就整组不画，别凭空补 0（0 会被当成「练度为 0」误导人）。
    返回结构见 `webui.web_model.BoxPlayerEnhance`。
    """
    knight = getattr(load_index, "princess_knight_info", None)
    mp_level = 0
    talents = []
    if knight is not None:
        node = getattr(knight, "team_skill_latest_node", None)
        mp_level = int(getattr(node, "node_id", 0) or 0)
        for info in getattr(knight, "talent_level_info_list", None) or []:
            talent_id = int(getattr(info, "talent_id", 0) or 0)
            if talent_id <= 0:
                continue
            point = int(getattr(info, "total_point", 0) or 0)
            talents.append(
                {
                    "talent_id": talent_id,
                    # 名字按 basedata.TALENT（1 火 / 2 水 / 3 风 / 4 光 / 5 暗）取
                    "name": (
                        TALENT[talent_id - 1]
                        if talent_id <= len(TALENT)
                        else f"属性{talent_id}"
                    ),
                    "level": talent_level_of(point),
                    "point": point,
                }
            )
    talents.sort(key=lambda item: item["talent_id"])

    roles = []
    for info in getattr(load_index, "unit_role_list", None) or []:
        role_id = int(getattr(info, "unit_role_id", 0) or 0)
        if role_id <= 0:
            continue
        slots = []
        for slot in range(1, 5):
            level = int(getattr(info, f"slot_level_{slot}", 0) or 0)
            star = int(getattr(info, f"enhance_level_{slot}", 0) or 0)
            slots.append(
                {
                    "slot": slot,
                    "level": level,
                    "star": star,
                    # 板块等级 0 = 还没解锁（游戏里显示成「-」）
                    "unlocked": level > 0,
                }
            )
        roles.append(
            {
                "role_id": role_id,
                "name": (
                    UNIT_ROLE[role_id - 1]
                    if role_id <= len(UNIT_ROLE)
                    else f"职阶{role_id}"
                ),
                "slots": slots,
            }
        )
    roles.sort(key=lambda item: item["role_id"])

    return {
        "mp_level": mp_level,
        "talents": talents,
        "roles": roles,
        # 属性技能（第几页 / 第几合流 / 左中右三条线 / 余多少星幽碎片）
        "skill": build_talent_skill_info(load_index),
    }


async def _save_player_box(self_support: LoadIndexResponse, qid: int) -> int:
    """把一份 `load_index` 结果写进个人 BOX 缓存（`PlayerUnit`），返回角色数。"""
    await save_player_units(
        self_support.unit_list,
        self_support.user_chara_info,
        self_support.user_ex_equip,
        qid,
        self_support.user_info.user_name,
        self_support.user_info.viewer_id,
        friend_support_list=self_support.friend_support_units,
        support_list=self_support.dispatch_units,
    )
    # 顺带把 EX 装备背包也存一份：网页端 BOX 详情的「普通 EX 槽」靠它显示现在穿哪件。
    # 新功能，写失败只记日志，不能把【刷新box缓存】本身搞成失败。
    try:
        await pcr_sqla.refresh_player_ex_equips(
            qid,
            build_player_ex_equips(self_support, qid, self_support.user_info.viewer_id),
        )
    except Exception as e:
        logger.warning(f"写入 EX 装备缓存失败：{e!r}")
    # 再存一份「公主骑士强化 / 职阶」练度快照：网页端「个人 BOX」查询框下面的练度条靠它，
    # 查询时纯读库、不登录（这几项只有 load_index 里有，为了显示去登录就顶号了）。
    # 同样是新功能，写失败只记日志。
    try:
        await pcr_sqla.refresh_player_enhance(
            qid,
            json.dumps(build_player_enhance(self_support), ensure_ascii=False),
            pcrid=int(self_support.user_info.viewer_id or 0),
        )
    except Exception as e:
        logger.warning(f"写入练度快照失败：{e!r}")
    return len(self_support.unit_list)


async def refresh_clan_support(account: Account, group_id: int) -> int:
    """刷新公会助战缓存，返回写入的条目数；不在会战期间抛 `SupportRefreshError`。

    QQ 群【刷新助战缓存】共用这一份逻辑。
    ⚠️ **会顶号**（同 `refresh_player_box`）。
    """
    client = await query(account)
    self_support = await get_support_list_with_client("self_query", client)
    return await save_clan_support(client, group_id, self_support)


async def refresh_box_and_support(
    account: Account, qid: int, group_id: int
) -> Tuple[int, int, str]:
    """一次登录，把**个人 BOX** 和**本群公会助战**两份缓存一起刷新。

    网页端「刷新缓存」按钮用的就是它 —— 等价于在群里先后发【刷新box缓存】和
    【刷新助战缓存】，但**只登录一次**（两次取数复用同一个 client），不会多顶一次号。
    QQ 端那两条指令仍各走各的函数，行为一个字不变。

    返回 `(个人BOX角色数, 公会助战条数, 公会助战失败原因)`。
    「现在不是会战期间」这类错误只影响公会助战、**不影响个人 BOX**，所以用返回值带回、
    不抛异常（QQ 端那两条指令保持原来的抛异常语义）。
    """
    client = await query(account)
    self_support = await get_support_list_with_client("self_query", client)
    box_count = await _save_player_box(self_support, qid)

    try:
        support_count = await save_clan_support(client, group_id, self_support)
        support_error = ""
    except Exception as e:
        support_count, support_error = 0, str(e)
    return box_count, support_count, support_error


def generate_unit2library(target_rank: float, target_units: List[UnitData]) -> list:
    return [
        {
            "e": "".join(["1" if equip.is_slot else "0" for equip in unit.equip_slot]),
            "p": unit.promotion_level,
            "r": str(unit.unit_rarity),
            "u": hex(unit.id // 100)[2:],
            "t": str(target_rank),
            "q": (
                str(unit.unique_equip_slot[0].enhancement_level)
                if unit.unique_equip_slot and unit.unique_equip_slot[0].rank > 0
                else "0"
            ),
            "b": "true" if unit.exceed_stage else "false",
            "f": False,
        }
        for unit in target_units
    ]


def get_library_equip_data(equip_list: List[InventoryInfo]) -> list:
    return [
        {
            "c": hex(equip.stock)[2:],
            "e": hex(equip.id)[2:],
            "a": "1",
        }
        for equip in equip_list
    ]


def get_library_memory_data(target_units: List[UnitData]) -> list:
    return [{"c": "0", "u": hex(unit.id)[2:]} for unit in target_units]


async def export_library(target_units: Dict[float, List[int]], account: Account) -> str:
    index = await get_support_list("self_query", account)
    query_units: Dict[float, List[UnitData]] = {
        target_rank: [] for target_rank in target_units
    }
    for unit in index.unit_list:
        if not target_units:
            break
        for target_rank in target_units:
            if unit.id // 100 in target_units[target_rank]:
                query_units[target_rank].append(unit)
                target_units[target_rank].remove(unit.id // 100)
                if not target_units[target_rank]:
                    del target_units[target_rank]
                break
    units = []
    all_units = []
    for rank in query_units:
        units += generate_unit2library(rank, query_units[rank])
        all_units += query_units[rank]

    json_str = json.dumps(
        [
            units,
            get_library_equip_data(index.user_equip),
            get_library_memory_data(all_units),
        ]
    )
    return base64.b64encode(gzip.compress(json_str.encode("utf-8"))).decode("utf-8")


mode2str = {1: "地下城", 2: "团队战/露娜塔", 3: "关卡"}
str2mode = {v: k for k, v in mode2str.items()}
str2mode.update({"公会": 2, "露娜": 2, "地下": 1, "工会": 2, "会战": 2})


# ---- 会战 EX 装备自动穿戴（移植自 autopcr `#挂会战支援`）：挂上支援后补满空槽 ----
# 类别 / 稀有度 / 会战专用都编码在 ex_equipment_id 里，只需一张槽位表（见 data 目录）。


@functools.lru_cache(maxsize=1)
def _unit_ex_slot_table() -> Dict[str, List[int]]:
    """`chara_id -> [槽1类别, 槽2类别, 槽3类别]`。

    文件缺失就返回空表 —— 老部署没带这个 json 时自动降级成「不穿 EX」，不会报错。

    类别 / 稀有度 / 会战专用都编码在 `ex_equipment_id` 里，不用另存装备表：
    `4101351 -> category=(4101351//1000)%1000=101, rarity=(4101351//100)%10=3, 51 结尾=会战专用`
    （已用游戏主库 260 条装备全量验证过，0 条不符）。重新导出：
    `SELECT unit_id, slot_category_1, slot_category_2, slot_category_3 FROM unit_ex_equipment_slot`
    转成 `{str(unit_id // 100): [c1, c2, c3]}` 即可（unit_id 就是 chara_id*100+1）。
    """
    path = FilePath.data.value / "unit_ex_equipment_slot.json"
    if not path.exists():
        logger.warning(f"缺少会战EX槽位表 {path}，跳过自动穿装")
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def ex_equip_category(equipment_id: int) -> int:
    """EX 装备的类别（101~110 / 201~204 / 301~305），编码在 id 里。"""
    return (equipment_id // 1000) % 1000


def ex_equip_rarity(equipment_id: int) -> int:
    """EX 装备的稀有度（1~5），编码在 id 里。"""
    return (equipment_id // 100) % 10


def is_clan_battle_ex_equip(equipment_id: int) -> bool:
    """是不是会战专用 EX 装（【行会】系列，id 以 51 结尾）。"""
    return equipment_id % 100 == 51


async def equip_clan_battle_ex(
    client, player_info: LoadIndexResponse, unit_data: UnitData
) -> List[str]:
    """给一个角色补满**空着的**会战 EX 槽，返回补了哪几个槽（没补就是空列表）。

    挑装规则照搬 autopcr：会战专用 > 稀有度 > 强化等级，且排除
      - 已经被别的角色装走的（所有角色 `cb_ex_equip_slot` 里出现过的 serial_id）
      - 会战冷却中的（`user_clan_battle_ex_equip_restriction`，刚卸下的装备一段时间内不能再用）

    **已经装了的槽绝不动** —— 这个函数只会「填空」，不会覆盖用户自己的搭配。
    """
    slot_categories = _unit_ex_slot_table().get(str(unit_data.id // 100))
    if not slot_categories:
        return []  # 槽位表里没这个角色（新角色），跳过

    occupied = {
        slot.serial_id
        for unit in player_info.unit_list
        for slot in (unit.cb_ex_equip_slot or [])
        if slot.serial_id
    } | {
        restriction.serial_id
        for restriction in (player_info.user_clan_battle_ex_equip_restriction or [])
    }
    owned = {
        equip.serial_id: equip
        for equip in (player_info.user_ex_equip or [])
        if equip.serial_id
    }

    current = unit_data.cb_ex_equip_slot or []
    changes: List[ExtraEquipChangeSlot] = []
    filled: List[str] = []
    for index, category in enumerate(slot_categories):
        if index < len(current) and current[index].serial_id:
            continue  # 这个槽已经装了，不动
        candidates = sorted(
            (
                equip
                for equip in owned.values()
                if ex_equip_category(equip.ex_equipment_id) == category
                and equip.serial_id not in occupied
            ),
            key=lambda equip: (
                is_clan_battle_ex_equip(equip.ex_equipment_id),
                ex_equip_rarity(equip.ex_equipment_id),
                equip.enhancement_pt or 0,
            ),
            reverse=True,
        )
        if not candidates:
            continue  # 这个类别没有可用装备
        best = candidates[0]
        occupied.add(best.serial_id)
        changes.append(ExtraEquipChangeSlot(slot=index + 1, serial_id=best.serial_id))
        filled.append(f"槽{index + 1}")

    if not changes:
        return []

    await client.unit_equip_ex(
        [
            ExtraEquipChangeUnit(
                unit_id=unit_data.id,
                ex_equip_slot=None,
                cb_ex_equip_slot=changes,
            )
        ]
    )

    # 本地这份 load_index 数据也同步更新，下面写缓存时才是刚穿好的状态
    if unit_data.cb_ex_equip_slot is None:
        unit_data.cb_ex_equip_slot = []
    while len(unit_data.cb_ex_equip_slot) < len(slot_categories):
        unit_data.cb_ex_equip_slot.append(ExtraEquipSlot())
    for change in changes:
        slot = unit_data.cb_ex_equip_slot[change.slot - 1]
        slot.serial_id = change.serial_id
        info = owned.get(change.serial_id)
        if info is not None:
            slot.ex_equipment_id = info.ex_equipment_id
            slot.enhancement_pt = info.enhancement_pt
    return filled


# ---- 普通 EX 装备（网页端「角色详情 → 普通 EX 槽」的换装）----
# 读走本地缓存 PlayerExEquip（不登录）；写走 unit_equip_ex（**顶号**，前端先弹确认）。


def unit_ex_slot_categories(chara_id: int) -> List[int]:
    """某个角色三个普通 EX 槽各自能穿的类别（`chara_id` 是 4 位角色 id）。

    数据源是模块自带的 `resource/data/unit_ex_equipment_slot.json`（见文件头的注释）；
    表里没有这个角色（新角色 / 老部署）时返回空列表，调用方要按「查不到」处理。
    """
    return list(_unit_ex_slot_table().get(str(int(chara_id))) or [])


def pack_sub_status(raw) -> str:
    """彩装词条 -> 存库用的紧凑 JSON（没有词条时存空串）。

    存的是**原始四元组**而不是算好的数值：数值由 (装备, 属性, step) 查表得到，
    表随 `resource/data/ex_equipment.json` 更新，存原始值以后换表也不用重刷缓存。
    """
    items = []
    for item in raw or []:
        items.append(
            [
                int(ex_equip_data.field_of(item, "slot_number") or 0),
                int(ex_equip_data.field_of(item, "status") or 0),
                int(ex_equip_data.field_of(item, "step") or 0),
                1 if ex_equip_data.field_of(item, "is_lock") else 0,
            ]
        )
    return json.dumps(items, separators=(",", ":")) if items else ""


def unpack_sub_status(text) -> List[Dict]:
    """存库的紧凑 JSON -> `ex_equip_data.sub_status_entries` 能吃的 dict 列表。

    脏数据 / 空串一律当「没有词条」，绝不因为一条坏记录把整个列表接口搞 500。
    """
    if not text:
        return []
    try:
        rows = json.loads(text)
    except Exception:
        return []
    result = []
    for row in rows or []:
        try:
            result.append(
                {
                    "slot_number": int(row[0]),
                    "status": int(row[1]),
                    "step": int(row[2]),
                    "is_lock": bool(row[3]),
                }
            )
        except Exception:
            continue
    return result


def build_player_ex_equips(
    self_support: LoadIndexResponse, qid: int, pcrid: int
) -> List[PlayerExEquip]:
    """`load_index` 快照 -> `PlayerExEquip` 行（背包清单 + 每件穿在谁身上）。

    **只在【刷新box缓存】时调用**：这是一份登录那一刻的快照，之后游戏里换装、
    强化都不会自动同步 —— 网页端展示的是它，真正换装时后端会重新登录拿实时数据。
    """
    wearers: Dict[int, Tuple[int, str, int]] = {}
    for unit in self_support.unit_list or []:
        for kind, slots in (
            ("ex", unit.ex_equip_slot),
            ("cb", unit.cb_ex_equip_slot),
        ):
            for index, slot in enumerate(slots or [], start=1):
                serial_id = int(slot.serial_id or 0)
                if serial_id:
                    wearers[serial_id] = (int(unit.id or 0), kind, index)

    rows: List[PlayerExEquip] = []
    for equip in self_support.user_ex_equip or []:
        serial_id = int(equip.serial_id or 0)
        if not serial_id:
            continue
        unit_id, slot_kind, slot = wearers.get(serial_id, (0, "", 0))
        rows.append(
            PlayerExEquip(
                user_id=int(qid),
                pcrid=int(pcrid or 0),
                serial_id=serial_id,
                ex_equipment_id=int(equip.ex_equipment_id or 0),
                enhancement_pt=int(equip.enhancement_pt or 0),
                rank=int(equip.rank or 0),
                unit_id=unit_id,
                slot_kind=slot_kind,
                slot=slot,
                # 5 星彩装的 4 条词条（1~4 星装备这里是空串）
                sub_status=pack_sub_status(equip.sub_status),
            )
        )
    return rows


def _wearer_label(row: PlayerExEquip, unit_id: int, slot: int) -> str:
    """一件装备的「现在在哪」文案（供网页端下拉选择那一份拷贝用）。"""
    owner = int(row.unit_id or 0)
    if not owner:
        return "空闲"
    owner_name = _unit_name(owner // 100)
    if owner == unit_id:
        return "当前穿戴" if int(row.slot or 0) == slot else f"本角色 槽{int(row.slot or 0)}"
    kind = "会战槽" if row.slot_kind == "cb" else "槽"
    return f"{owner_name} {kind}{int(row.slot or 0)}"


def _unit_name(chara_id: int) -> str:
    try:
        return fromid(int(chara_id)).name
    except Exception:
        return str(chara_id)


def _star_text(star: int) -> str:
    """给提示文案用的星级后缀。

    `star=0` 有**两种**含义：没强化过的 1~4 星装备，以及**永远没有星级**的 5 星彩装
    （彩装没有强化等级，见 `ex_equip_data.star_from_pt`）。两种情况都不该写成「★0」，
    直接不显示星级更准确。
    """
    return f"★{int(star)}" if star else ""


def build_ex_equip_options(
    rows: List[PlayerExEquip], chara_id: int, slot: int
) -> Optional[Dict]:
    """列某个角色某个普通 EX 槽的可选装备（**纯本地缓存，不打游戏接口**）。

    `rows` 是 `pcr_sqla.get_player_ex_equips(user_id)` 的结果。返回 None 表示
    「这个角色没有槽位数据 / 槽位号不对」，调用方转成一句提示。

    同一件装备（同 ID 同星级）会**合并成一组** —— 一个玩家手里同一件铜装可能有十几把，
    全部铺开既难看也没意义。组里带 `copies`，每份拷贝标明现在空闲 / 在谁身上；
    前端默认取第一份（空闲优先），也可以让用户自己挑要动谁的那一件。
    """
    categories = unit_ex_slot_categories(chara_id)
    unit_id = int(chara_id) * 100 + 1
    slot = int(slot)
    if not categories or not 1 <= slot <= len(categories):
        return None
    category = int(categories[slot - 1])

    grouped: Dict[Tuple[int, int], List[PlayerExEquip]] = {}
    current: Optional[PlayerExEquip] = None
    for row in rows:
        equipment_id = int(row.ex_equipment_id or 0)
        if ex_equip_category(equipment_id) != category:
            continue
        # 正穿在会战槽里的不列出来：挪到普通槽会破坏会战搭配，且刚卸下的会战装
        # 有冷却、换回去都换不回来。用户要求「会战EX保留现在的」，这里一刀切掉。
        if row.slot_kind == "cb":
            continue
        star = ex_equip_data.star_from_pt(equipment_id, row.enhancement_pt)
        subs = ex_equip_data.sub_status_entries(
            equipment_id, unpack_sub_status(row.sub_status)
        )
        # 合并规则：1~4 星按「装备 + 星级」合并（同一件几十把、等价）；5 星彩装
        # **一件一行**（词条逐件不同，合并了就没法挑词条、也没法只换点的那一件）。
        if ex_equip_data.equipment_rarity(equipment_id) >= 5:
            group_key = (equipment_id, star, int(row.serial_id))
        else:
            group_key = (equipment_id, star, 0)
        grouped.setdefault(group_key, []).append((row, subs))
        if (
            int(row.unit_id or 0) == unit_id
            and row.slot_kind == "ex"
            and int(row.slot or 0) == slot
        ):
            current = row

    candidates = []
    for key, entries in grouped.items():
        equipment_id, star, serial_key = int(key[0]), int(key[1]), int(key[2])
        payload = ex_equip_data.equipment_payload(equipment_id, star)
        # 前端用它判断「这行选中了没」。彩装一件一行所以带 serial_id，否则同装备
        # 同星级的几行共用一个 key，点一行会把同名那几行一起点亮（用户反馈过）。
        payload["candidate_key"] = f"{equipment_id}:{star}:{serial_key}"
        # 彩装一行就是一件，直接把 serial 带出去给界面显示（方便和 autopcr 的输出对号）
        payload["serial_id"] = serial_key
        copies = [row for row, _subs in entries]
        # 空闲的排最前面（优先用空闲的，没必要去动别人身上的），其次是本角色自己的
        copies.sort(
            key=lambda row: (
                0
                if not int(row.unit_id or 0)
                else (1 if int(row.unit_id or 0) == unit_id else 2),
                int(row.unit_id or 0),
                int(row.serial_id or 0),
            )
        )
        copy_list = [
            {
                "serial_id": int(row.serial_id),
                "rank": int(row.rank or 0),
                "enhancement_pt": int(row.enhancement_pt or 0),
                "wearer_unit_id": int(row.unit_id or 0),
                "wearer_name": (
                    _unit_name(int(row.unit_id or 0) // 100) if row.unit_id else ""
                ),
                "wearer_slot": int(row.slot or 0),
                "wearer_kind": str(row.slot_kind or ""),
                "label": _wearer_label(row, unit_id, slot),
            }
            for row in copies
        ]
        payload.update(
            {
                "count": len(copy_list),
                "free_count": sum(1 for c in copy_list if not c["wearer_unit_id"]),
                "copies": copy_list,
                # 彩装的 4 条词条（1~4 星装备恒为空列表）；同组内词条一致，取第一份即可
                "sub_statuses": entries[0][1],
                "equipped_here": any(
                    c["serial_id"] == int(current.serial_id) for c in copy_list
                )
                if current is not None
                else False,
            }
        )
        candidates.append(payload)

    # 稀有度 > 星级 > 装备ID，和 autopcr `#一键穿ex` 的排序一致；
    # 同装备同星级会有多行（词条不同）时再按词条签名兜一个稳定次序。
    candidates.sort(
        key=lambda c: (
            c["rarity"],
            c["star"],
            c["equipment_id"],
            c["candidate_key"],
        ),
        reverse=True,
    )

    current_payload = None
    if current is not None:
        current_equipment_id = int(current.ex_equipment_id)
        current_star = ex_equip_data.star_from_pt(
            current_equipment_id, int(current.enhancement_pt or 0)
        )
        current_payload = ex_equip_data.equipment_payload(
            current_equipment_id, current_star
        )
        current_payload["serial_id"] = int(current.serial_id)
        current_payload["rank"] = int(current.rank or 0)
        current_payload["sub_statuses"] = ex_equip_data.sub_status_entries(
            current_equipment_id, unpack_sub_status(current.sub_status)
        )
        # 和列表里的 key 规则一致（彩装带 serial，1~4 星装备不带）
        current_payload["candidate_key"] = (
            f"{current_equipment_id}:{current_star}:"
            f"{int(current.serial_id) if ex_equip_data.equipment_rarity(current_equipment_id) >= 5 else 0}"
        )

    return {
        "chara_id": int(chara_id),
        "unit_id": unit_id,
        "slot": slot,
        "category": category,
        "category_name": ex_equip_data.category_name(category),
        "slots": [
            {
                "slot": index,
                "category": int(cat),
                "category_name": ex_equip_data.category_name(int(cat)),
            }
            for index, cat in enumerate(categories, start=1)
        ],
        "current": current_payload,
        "candidates": candidates,
    }


@dataclass
class ExEquipSlotChangeResult:
    """批量换装里**一个槽**的结果。"""

    slot: int = 0
    serial_id: int = 0           # 换上去的（0 = 本槽是卸下）
    equipment_id: int = 0
    name: str = ""
    star: int = 0
    old_serial_id: int = 0       # 原来在这个槽里的（0 = 原来空着）
    swapped_chara_id: int = 0    # 与谁互换（0 = 没动别人）
    swapped_chara_name: str = ""


@dataclass
class ExEquipChangeResult:
    """普通 EX 装备换装的结果（网页端转成 JSON，字段都在这里判定）。

    ⚠️ 和 `SupportChangeResult` 一样是**写操作**的结果：调用方已经真的登录过游戏账号
    （顶号）并改过游戏里的 EX 槽了。

    `slots` 是本次真正改动的那几个槽（1~3 个）—— 网页端一次可以挑好三个槽一起提交，
    后端只登录一次、只发一批 `unit/equip_ex`。
    """

    ok: bool = False
    message: str = ""
    chara_id: int = 0            # 4 位角色 ID
    chara_name: str = ""
    slots: List[ExEquipSlotChangeResult] = field(default_factory=list)


async def change_normal_ex_equips(
    account: Account, chara_id: int, changes
) -> ExEquipChangeResult:
    """一次更换某个角色的**若干普通 EX 槽**（1~3 个），只登录一次、只提交一批。

    `changes` 是 `[(槽位, serial_id), ...]`：`serial_id=0` 表示卸下，没提到的槽不动。
    网页端弹窗里挑好 EX1/EX2/EX3 后一次提交，走的就是这里。

    动作顺序照搬 autopcr `#一键穿ex` 的**多槽**版本
    （`autopcr/module/modules/tools.py: one_click_ex_equip`）：
      1. 把选中的装备从**别人**身上卸下（穿在会战槽里的直接拒绝，见下）；
      2. **一次**清掉本角色要腾的槽（选中的槽原有的装备 + 本角色别的槽里正好穿着目标装备的）；
      3. **一次**把选中的装备全穿上；
      4. 把第 1 步卸下来的位置用第 2 步腾出来的旧装备补上（= **互换**，不把别人扒光）。
    少了第 1 步会「一件装备同时在两个地方」，少了第 4 步会把别人的装备凭空吞掉。

    几个刻意的取舍：
      - **不使用会战槽**：会战 EX 的自动穿搭保持原样，所以正在会战槽里的装备直接拒绝
        （前端也不会把它列出来）；
      - 判定全用**登录那一刻的实时数据**，不信任本地缓存的穿戴关系 ——
        缓存可能是一小时前的，拿它去算「谁身上有这件」会穿错；
      - 冷却中的会战装有 `user_clan_battle_ex_equip_restriction`，穿不上去，提前拦掉，
        免得白顶一次号；
      - 同一件装备不允许同时选进两个槽（会直接报错，而不是让游戏接口去撞）。
    """
    client = await query(account)
    player_info = await client.load_index()

    chara_id = int(chara_id)
    unit_id = chara_id * 100 + 1
    chara_name = _unit_name(chara_id)

    def fail(message: str) -> ExEquipChangeResult:
        return ExEquipChangeResult(
            ok=False, message=message, chara_id=chara_id, chara_name=chara_name
        )

    categories = unit_ex_slot_categories(chara_id)
    if not categories:
        return fail(f"找不到{chara_name}的 EX 槽位数据（新角色 / 数据表未更新）")

    unit = next(
        (u for u in (player_info.unit_list or []) if int(u.id or 0) == unit_id), None
    )
    if unit is None:
        return fail(f"没有找到{chara_name}的数据，可能是未解锁")

    owned = {
        int(equip.serial_id): equip
        for equip in (player_info.user_ex_equip or [])
        if equip.serial_id
    }
    restricted = {
        int(item.serial_id or 0)
        for item in (player_info.user_clan_battle_ex_equip_restriction or [])
    }
    current_slots = list(unit.ex_equip_slot or [])

    def current_serial(slot: int) -> int:
        return (
            int(current_slots[slot - 1].serial_id or 0)
            if slot - 1 < len(current_slots)
            else 0
        )

    # ---- 逐槽校验，攒出 planned ----
    planned: List[Tuple[int, int, int, int]] = []  # (槽, serial, 装备, 星)
    seen_slots: set = set()
    used_serials: Dict[int, int] = {}              # serial_id -> 先被哪个槽用了
    for raw_slot, raw_serial in changes:
        slot = int(raw_slot)
        serial_id = int(raw_serial or 0)
        if not 1 <= slot <= len(categories):
            return fail("EX 槽位编号不对")
        if slot in seen_slots:
            return fail(f"EX{slot} 槽重复提交了")
        seen_slots.add(slot)

        if serial_id == current_serial(slot):
            # 前端会把「没改的槽」过滤掉；真送来了就当没改，不算失败
            continue
        if not serial_id:
            planned.append((slot, 0, 0, 0))
            continue

        category = int(categories[slot - 1])
        target = owned.get(serial_id)
        if target is None:
            return fail("找不到这件 EX 装备（可能是缓存过期，请先点【刷新缓存】）")
        # 同一件装备不能出现在两个槽里：这条要**排在类别校验前面** ——
        # 真出现这种情况时，「重复选了同一件」比「类别不对」更接近用户实际做错的事。
        if serial_id in used_serials:
            return fail(
                f"同一件装备不能同时装在 EX{used_serials[serial_id]} 和 EX{slot} 两个槽上"
            )
        target_category = ex_equip_category(int(target.ex_equipment_id or 0))
        if target_category != category:
            return fail(
                f"这件装备属于「{ex_equip_data.category_name(target_category) or target_category}」，"
                f"不能装在{chara_name}的 EX{slot} 槽"
                f"（「{ex_equip_data.category_name(category) or category}」）"
            )
        if serial_id in restricted:
            return fail("这件 EX 装备刚被卸下，还在冷却中（会战冷却），暂时穿不上去")
        used_serials[serial_id] = slot
        planned.append(
            (
                slot,
                serial_id,
                int(target.ex_equipment_id or 0),
                ex_equip_data.star_from_pt(
                    int(target.ex_equipment_id), int(target.enhancement_pt or 0)
                ),
            )
        )

    if not planned:
        return fail("没有需要改动的 EX 槽")

    # ---- 登录那一刻的占用表：普通槽 + 会战槽一起算 ----
    worn: Dict[int, Tuple[int, str, int]] = {}
    for other in player_info.unit_list or []:
        for kind, slots in (
            ("ex", other.ex_equip_slot),
            ("cb", other.cb_ex_equip_slot),
        ):
            for index, s in enumerate(slots or [], start=1):
                if s.serial_id:
                    worn[int(s.serial_id)] = (int(other.id or 0), kind, index)

    new_serials = {serial for _, serial, _, _ in planned if serial}
    slots_to_change = {slot for slot, _, _, _ in planned}

    # 选中的装备现在在谁身上；在会战槽里的直接拒绝
    take_from: Dict[Tuple[int, int], int] = {}      # (unit, slot) -> 被拿走的 serial
    swap_back: List[Tuple[int, int, int]] = []      # (owner_unit, owner_slot, 还给他的旧装备)
    owners: Dict[int, Tuple[int, str, int]] = {}    # serial -> owner（后面写结果/缓存要用）
    for slot, serial_id, _, _ in planned:
        if not serial_id:
            continue
        owner = worn.get(serial_id)
        if owner is None:
            continue
        owners[serial_id] = owner
        if owner[1] == "cb":
            return fail(
                f"这件装备正穿在{_unit_name(owner[0] // 100)}的会战槽{owner[2]}里，"
                "网页端不动机器人自动搭的会战 EX，请先在游戏里处理"
            )
        if owner[0] == unit_id:
            continue  # 本角色别的槽，下面 clear 里会一起清掉
        take_from[(owner[0], owner[2])] = serial_id
        swap_back.append((owner[0], owner[2], current_serial(slot)))

    # ---- 写操作（1~4 步之间没有回滚）----
    # 中途失败时游戏侧可能停在「已经卸下、还没穿上」的状态，所以提示里必须写清楚，
    # 让用户回游戏里确认后再操作，不能只丢一句「更换失败」。
    try:
        # 1) 从别人身上取下选中的装备
        for (owner_unit, owner_slot), _serial in take_from.items():
            await client.unit_equip_ex(
                [
                    ExtraEquipChangeUnit(
                        unit_id=owner_unit,
                        ex_equip_slot=[
                            ExtraEquipChangeSlot(slot=owner_slot, serial_id=0)
                        ],
                        cb_ex_equip_slot=None,
                    )
                ]
            )

        # 2) 一次清掉本角色要腾的槽
        clear: List[ExtraEquipChangeSlot] = []
        for index, s in enumerate(current_slots, start=1):
            serial = int(s.serial_id or 0)
            if not serial:
                continue
            if index in slots_to_change or serial in new_serials:
                clear.append(ExtraEquipChangeSlot(slot=index, serial_id=0))
        if clear:
            await client.unit_equip_ex(
                [
                    ExtraEquipChangeUnit(
                        unit_id=unit_id, ex_equip_slot=clear, cb_ex_equip_slot=None
                    )
                ]
            )

        # 3) 一次把选中的装备穿上
        equip = [
            ExtraEquipChangeSlot(slot=slot, serial_id=serial_id)
            for slot, serial_id, _, _ in planned
            if serial_id
        ]
        if equip:
            await client.unit_equip_ex(
                [
                    ExtraEquipChangeUnit(
                        unit_id=unit_id, ex_equip_slot=equip, cb_ex_equip_slot=None
                    )
                ]
            )

        # 4) 互换：把本槽原来的装备还给第 1 步被拿走的那位。
        #    如果那件旧装备本身也被选进了别的槽（本批次里要穿到别处），就不再还回去。
        for owner_unit, owner_slot, old_serial in swap_back:
            if not old_serial or old_serial in new_serials:
                continue
            await client.unit_equip_ex(
                [
                    ExtraEquipChangeUnit(
                        unit_id=owner_unit,
                        ex_equip_slot=[
                            ExtraEquipChangeSlot(slot=owner_slot, serial_id=old_serial)
                        ],
                        cb_ex_equip_slot=None,
                    )
                ]
            )
    except Exception as e:
        logger.error(f"更换普通EX装失败 chara={chara_id}: {e!r}")
        return fail(
            f"更换 EX 过程中出错：{e}；装备可能停在「已卸下」状态，请回游戏检查后再试"
        )

    # ---- 结果 + 本地缓存 ----
    wearers: Dict[int, Tuple[int, str, int]] = {}
    results: List[ExEquipSlotChangeResult] = []
    for slot, serial_id, equipment_id, star in planned:
        old_serial_id = current_serial(slot)
        owner = owners.get(serial_id) if serial_id else None
        swapped_chara_id = 0
        if serial_id:
            wearers[serial_id] = (unit_id, "ex", slot)
        if old_serial_id and old_serial_id != serial_id:
            if (
                owner is not None
                and owner[0] != unit_id
                and old_serial_id not in new_serials
            ):
                wearers[old_serial_id] = (owner[0], "ex", owner[2])
                swapped_chara_id = owner[0] // 100
            else:
                wearers[old_serial_id] = (0, "", 0)
        results.append(
            ExEquipSlotChangeResult(
                slot=slot,
                serial_id=serial_id,
                equipment_id=equipment_id,
                name=ex_equip_data.equipment_name(equipment_id) if equipment_id else "",
                star=star,
                old_serial_id=old_serial_id,
                swapped_chara_id=swapped_chara_id,
                swapped_chara_name=(
                    _unit_name(swapped_chara_id) if swapped_chara_id else ""
                ),
            )
        )
    results.sort(key=lambda r: r.slot)

    parts = []
    for r in results:
        if not r.serial_id:
            parts.append(f"EX{r.slot} 卸下")
        elif r.swapped_chara_name:
            parts.append(f"EX{r.slot} {r.name}{_star_text(r.star)}（与{r.swapped_chara_name}互换）")
        else:
            parts.append(f"EX{r.slot} {r.name}{_star_text(r.star)}")
    message = f"已为{chara_name}更换 {len(results)} 个 EX 槽：" + "、".join(parts)

    try:
        await pcr_sqla.set_player_ex_equip_wearers(account.user_id, wearers)
    except Exception as e:
        # 游戏侧已经改成功了，缓存没跟上不该让用户以为「换装失败」
        logger.warning(f"换普通EX装后同步本地缓存失败：{e!r}")

    return ExEquipChangeResult(
        ok=True,
        message=message,
        chara_id=chara_id,
        chara_name=chara_name,
        slots=results,
    )


async def change_normal_ex_equip(
    account: Account, chara_id: int, slot: int, serial_id: int
) -> ExEquipChangeResult:
    """单槽版本（网页端现在走批量；留着方便单独换一个槽和测试）。"""
    return await change_normal_ex_equips(account, chara_id, [(slot, serial_id)])


@dataclass
class BattleRarityPlan:
    """「调战斗星级」的预检结果（纯数据，不碰游戏、不碰库）。

    `ok=False` 时 `message` 就是给用户看的原因；`ok=True` 时 `changed` 表示
    是否真的需要调（`False` = 已经是目标星级，不用发请求）。
    `old_star` / `new_star` 只在 `ok=True` 时有效。
    """

    ok: bool = True
    changed: bool = False
    old_star: int = 0
    new_star: int = 0
    message: str = ""


def _battle_rarity_field(unit_data, name: str) -> int:
    """从角色数据里取一个整数字段（`unit_rarity` / `battle_rarity`）。

    游戏侧给的是 `client.common.UnitData`（pydantic），单测里也可能直接传个 dict
    或 SimpleNamespace，所以两种都认；取不到就当 0。
    """
    if isinstance(unit_data, dict):
        value = unit_data.get(name)
    else:
        value = getattr(unit_data, name, None)
    return int(value or 0)


def plan_battle_rarity(
    unit_data, target_star: int, unit_name: str
) -> BattleRarityPlan:
    """判断「能不能把这个角色调到目标战斗星级」，返回预检结果（纯函数，便于单测）。

    规则照搬 autopcr 的【挂会战支援】（tools.py `set_cb_support`）：
      - 战斗星级只能 3 / 4 / 5（游戏里就是「战斗中的星级」，不影响觉醒稀有度）；
      - 只有 `unit_rarity == 5` 的角色能调 —— 6★ 角色 `unit_rarity` 已经是 6，
        游戏不允许再改战斗星级（只有「能开花到 5★」的角色才有这个开关）；
      - 当前星级 = `battle_rarity or unit_rarity`（`battle_rarity` 为 0 表示
        从来没调过，按觉醒星级算）；
      - 目标与当前相同就不用发请求。

    **必须在任何写操作（挂支援 / 补 EX / 调星）之前调用**：非 5 星或非法星级
    不能先把支援挂上去再失败，那样用户会得到一个「挂上去了但星级没变」的中间态。
    """
    if target_star not in (3, 4, 5):
        return BattleRarityPlan(ok=False, message="战斗星级只能选 3 / 4 / 5")
    if not unit_data:
        return BattleRarityPlan(
            ok=False, message=f"未找到{unit_name}的数据，可能是未解锁"
        )
    rarity = _battle_rarity_field(unit_data, "unit_rarity")
    if rarity != 5:
        return BattleRarityPlan(
            ok=False, message=f"{unit_name}不是5星角色，无法调整战斗星级"
        )
    now_star = _battle_rarity_field(unit_data, "battle_rarity") or rarity
    if now_star not in (3, 4, 5):
        return BattleRarityPlan(
            ok=False, message=f"{unit_name}当前星级{now_star}无法调整"
        )
    if target_star == now_star:
        return BattleRarityPlan(
            ok=True,
            changed=False,
            old_star=now_star,
            new_star=now_star,
            message=f"{unit_name}的战斗星级已经是{target_star}★",
        )
    return BattleRarityPlan(
        ok=True,
        changed=True,
        old_star=now_star,
        new_star=target_star,
        message=f"已将{unit_name}的战斗星级从{now_star}★调整为{target_star}★",
    )


@dataclass
class SupportChangeResult:
    """「更换助战」（QQ 端【上XX支援】/ 网页端「我的助战」→【更换支援】）的结果。

    刻意返回结构化数据而不是一句现成的话：QQ 端要把它拼成「文字 + 角色出图」，
    网页端要把它变成 `ok/message` 的 JSON —— **判定逻辑只有这一份**，两边只是
    呈现方式不同。
    """

    ok: bool = False
    message: str = ""
    mode: int = 0             # 1 地下城 / 2 团队战·露娜塔 / 3 关卡（冒险）
    unit_id: int = 0          # 本次挂上去的角色 ID
    position: int = 0         # 挂到了哪个助战位（本地库 support_position 口径，见下方换算）
    removed_unit_id: int = 0  # 被顶掉的角色 ID（0 = 没有顶掉谁）
    star: int = 0             # 本次实际调整到的战斗星级（0 = 没调）
    old_star: int = 0         # 调整前的战斗星级（0 = 没调）
    unit: Optional[PlayerUnit] = None  # 给 QQ 端出图用的完整数据


async def change_support_unit(
    account: Account,
    support_unit_id: int,
    mode: int,
    group_id: Optional[int] = None,
    star: Optional[int] = None,
) -> SupportChangeResult:
    """把某个角色挂到指定栏位的助战（可选顺手调它的**战斗星级**）。

    栏位满了就顶掉挂得最久的那个（游戏侧规则：挂满 30 分钟后才允许换）。
    挂**会战位**（mode=2）时还会顺手补满该角色空着的会战 EX 槽（`equip_clan_battle_ex`）。
    成功后会把**本地缓存的助战位和会战 EX 装备**一起改掉
    （`set_player_support_positions` / `set_player_unit_ex_equips`），
    这样网页端「我的助战」立刻是对的，不用再等一次【刷新box缓存】。

    传了 `group_id`（网页端会传）时，还会用**同一个已登录的 client** 把本群的
    **公会助战缓存**也重拉一次 —— 否则换完支援，公会助战页显示的还是旧的。
    只在 mode=2 做（公会助战缓存里只有团队战栏，见 `_self_clan_support_units`）。
    QQ 端不传 `group_id`，行为与耗时**完全不变**。

    `star`（3 / 4 / 5）是**网页端专用**的可选参数，QQ 端三条指令都不传：
      - 传了就在挂上支援之后顺手调成该战斗星级（顺序同 autopcr【挂会战支援】：
        挂支援 → 补 EX → 调星）；
      - 校验（`plan_battle_rarity`）在**任何写操作之前**做，非 5★ / 非法星级
        会直接返回失败，**不会**先把支援挂上去 —— 否则用户会看到「挂上了但
        星级没变」的中间态；
      - 角色**已经在这个支援位**时，只调星、不重复挂、也不动 EX（网页端
        「预选当前角色改星级」就靠这条）；已经在**别的**支援位则照旧拒绝。

    ⚠️ **会顶号**：`query(account)` 会真正登录游戏账号，正在玩游戏的群友会被挤下线。
    """
    client = await query(account)
    player_info = await client.load_index()
    support_unit_name = fromid(support_unit_id).name
    unit_id = support_unit_id * 100 + 1
    mode_str = mode2str[mode]

    support_info = await client.get_support_unit_setting()

    current_support: List[List[SupportUnitSetting]] = [[], [], []]
    for unit in support_info.clan_support_units:
        if unit.position <= 2:
            current_support[0].append(unit)
        else:
            current_support[1].append(unit)

    for unit in support_info.friend_support_units:
        current_support[2].append(unit)

    # 先只判断「已经在哪个支援位」，不立刻返回：带 star 时同一个位要允许「只调星」。
    # 按 mode 1→2→3 的顺序取第一个命中的，和原来的提示文案保持一致。
    already_mode = 0
    already_setting: Optional[SupportUnitSetting] = None
    for i in mode2str:
        for unit in current_support[i - 1]:
            if unit.unit_id == unit_id:
                already_mode = i
                already_setting = unit
                break
        if already_mode:
            break

    # QQ 端（不传 star）在这里就按**原来的顺序**结束：原来「已经在支援中」的判定
    # 排在「查 unit_list 找角色数据」之前，所以哪怕游戏侧有这条支援、`load_index`
    # 里却没有这个角色，提示也必须是「已经在…支援中」而不是「未找到…数据」。
    # 带 star 的网页端请求要继续往下走（预检 → 只调星 / 换位）。
    if already_mode and star is None:
        return SupportChangeResult(
            ok=False,
            message=f"{support_unit_name}已经在{mode2str[already_mode]}支援中",
            mode=mode,
            unit_id=support_unit_id,
        )

    unit_info = next(
        (unit for unit in player_info.unit_list if unit.id == unit_id),
        None,
    )
    if not unit_info:
        return SupportChangeResult(
            ok=False,
            message=f"未找到{support_unit_name}的数据，可能是未解锁",
            mode=mode,
            unit_id=support_unit_id,
        )

    # 调星预检必须排在**所有写操作之前**：不合法就直接失败，别先把支援挂上去。
    plan: Optional[BattleRarityPlan] = None
    if star is not None:
        plan = plan_battle_rarity(unit_info, star, support_unit_name)
        if not plan.ok:
            return SupportChangeResult(
                ok=False,
                message=plan.message,
                mode=mode,
                unit_id=support_unit_id,
            )

    if already_mode:
        if already_mode != mode:
            # 在别的栏位：保持原行为（即使带 star 也不调，避免用户以为改的是当前栏）
            return SupportChangeResult(
                ok=False,
                message=f"{support_unit_name}已经在{mode2str[already_mode]}支援中",
                mode=mode,
                unit_id=support_unit_id,
            )
        # 走到这里 star 一定不为 None（star is None 已在上面提前返回）。
        # 已经在这个支援位 + 传了星级 = **只调星**：不重复挂支援、也不动 EX，
        # 否则会白白触发一次「挂支援」的 30 分钟冷却。网页端预选当前角色改星级
        # 走的就是这条路径。
        if plan.changed:
            await client.unit_change_rarity(
                [ChangeRarityUnit(unit_id=unit_id, battle_rarity=star)]
            )
            try:
                await pcr_sqla.set_unit_battle_rarity(
                    account.user_id, account.viewer_id, support_unit_id, star
                )
            except Exception as e:
                # 游戏侧已经改成功了，缓存没跟上不该让用户以为「调星失败」
                logger.warning(f"调星后同步本地缓存失败：{e!r}")
        # 返回给前端 / QQ 端的角色数据按**目标星级**给（`battle_rarity` 为 0 时游戏
        # 按觉醒星级算，所以没真调过也要写成 star，否则前端拿到的还是旧值）。
        unit_info.battle_rarity = star
        # 支援位没动，库口径仍按原支援位换算（关卡原值，其余 position+2）。
        db_position = (
            already_setting.position if mode == 3 else already_setting.position + 2
        )
        star_unit_info = parse_unit_data(unit_info)
        star_unit_info["support_position"] = db_position
        star_unit_info["user_id"] = account.user_id
        star_unit_info["pcrid"] = account.viewer_id
        star_unit_info["name"] = account.name
        star_unit_info["love_level"] = next(
            (
                love.love_level
                for love in player_info.user_chara_info
                if love.chara_id == support_unit_id
            ),
            0,
        )
        return SupportChangeResult(
            ok=True,
            message=f"{support_unit_name}已经在{mode_str}支援中\n{plan.message}",
            mode=mode,
            unit_id=support_unit_id,
            position=db_position,
            star=plan.new_star,
            old_star=plan.old_star,
            unit=PlayerUnit(**star_unit_info),
        )

    if unit_info.unit_level <= 10:
        return SupportChangeResult(
            ok=False,
            message=f"{support_unit_name}的等级过低(<=10级)，不可设置支援",
            mode=mode,
            unit_id=support_unit_id,
        )

    # 支援位对照：地下城 clan_support_units position 1/2；团队战 3/4；关卡 friend 1/2。
    target_support = current_support[mode - 1]
    num_support = len(target_support)

    try_position = {1, 2} if mode != 2 else {3, 4}  # 查询目标支援是否有坑位。
    result = ""
    removed_unit_id = 0
    if num_support == 0:  # 若有坑位，记录坑位。
        try_position = try_position.pop()
    elif num_support == 1:
        try_position = (try_position - {target_support[0].position}).pop()
    else:  # 若无坑位，查询是否可终止原支援
        available_change = [
            x for x in target_support if time.time() - x.support_start_time > 1800
        ]
        if not available_change:  # 若无法终止原支援，程序终止
            return SupportChangeResult(
                ok=False,
                message=f"{mode_str}当前已挂满且均不足30分钟，无法结束支援",
                mode=mode,
                unit_id=support_unit_id,
            )
        # 若两个都可终止，终止挂的时间较早的那个
        try_change = min(available_change, key=lambda x: x.support_start_time)
        try_position = try_change.position

        await client.change_support_unit(
            support_type=2 if mode == 3 else 1,
            position=try_position,
            action=2,
            unit_id=try_change.unit_id,
        )
        removed_unit_id = try_change.unit_id // 100
        result += (
            f"成功终止{fromid(removed_unit_id).name}的{mode_str}支援\n"
        )

    await client.change_support_unit(
        support_type=2 if mode == 3 else 1,
        position=try_position,
        action=1,
        unit_id=unit_id,
    )
    result += f"成功将{support_unit_name}挂上{mode_str}支援"

    # 挂会战支援时顺手补满空着的会战 EX 槽（移植自 autopcr `#挂会战支援`）；只处理
    # mode 2，失败只记日志（游戏侧已改成功，别让用户以为换失败了）。
    if mode == 2:
        try:
            filled = await equip_clan_battle_ex(client, player_info, unit_info)
            if filled:
                result += f"\n已为{support_unit_name}装备会战EX装（{'、'.join(filled)}）"
        except Exception as e:
            logger.warning(f"自动装备会战EX装失败：{e!r}")

    # 调战斗星级放在「挂支援 + 补 EX」**之后**，顺序与 autopcr 的【挂会战支援】一致：
    # 先让角色站上支援位，再改星级，支援位上显示的就是新星级。
    # `unit_info.battle_rarity` 要在下面的 parse_unit_data 之前改掉，返回给前端的
    # PlayerUnit 与写回缓存的才是新星级。
    #
    # ⚠️ 这里**不能**把调星异常直接抛出去：支援位已经挂上了（上面的
    # `change_support_unit` 是写操作、不可回滚），抛出去网页端只会显示「更换失败」，
    # 用户会以为支援没换、反复重试。所以降级成「挂上了但调星失败」的部分成功。
    if plan is not None:
        if plan.changed:
            try:
                await client.unit_change_rarity(
                    [ChangeRarityUnit(unit_id=unit_id, battle_rarity=star)]
                )
            except Exception as e:
                logger.warning(f"挂上支援后调整战斗星级失败：{e!r}")
                result += f"\n已挂上支援，但调整战斗星级失败：{e}"
                # 本次并没有真的调星 → star/old_star 归 0、返回的 PlayerUnit 保持原星级
                plan = None
            else:
                unit_info.battle_rarity = star
                try:
                    await pcr_sqla.set_unit_battle_rarity(
                        account.user_id, account.viewer_id, support_unit_id, star
                    )
                except Exception as e:
                    # 游戏侧已经改成功了，缓存没跟上不该让用户以为「调星失败」
                    logger.warning(f"调星后同步本地缓存失败：{e!r}")
                result += f"\n{plan.message}"
        else:
            result += f"\n{plan.message}"

    # ⚠️ 游戏侧 position 与本地库 support_position 不是一套编号：地下城 / 团队战存
    # position+2（3/4、5/6），关卡原样存 1/2。少这步网页端会显示上一个助战。
    db_position = try_position if mode == 3 else try_position + 2

    unit_ex_equip_dict = {
        equip.serial_id: (equip.ex_equipment_id, equip.enhancement_pt)
        for equip in player_info.user_ex_equip
        if equip.serial_id
        in {equip.serial_id for equip in player_info.user_ex_equip}
    }
    for equip in unit_info.cb_ex_equip_slot:
        if equip.serial_id:
            equip.ex_equipment_id, equip.enhancement_pt = unit_ex_equip_dict.get(
                equip.serial_id, (0, 0)
            )
    unit_info = parse_unit_data(unit_info)
    unit_info["support_position"] = db_position
    unit_info["user_id"] = account.user_id
    unit_info["pcrid"] = account.viewer_id
    unit_info["name"] = account.name
    unit_info["love_level"] = next(
        (
            love.love_level
            for love in player_info.user_chara_info
            if love.chara_id == support_unit_id
        ),
        0,
    )

    # 同步本地缓存的助战位：刚挂上去的写新位置，被顶掉的清 0。
    # 失败只记日志 —— 游戏侧已经改成功了，缓存没跟上不该让用户以为「更换失败」。
    positions = {support_unit_id: db_position}
    if removed_unit_id:
        positions[removed_unit_id] = 0
    try:
        await pcr_sqla.set_player_support_positions(account.user_id, positions)
    except Exception as e:
        logger.warning(f"更换助战后同步本地助战位失败：{e!r}")

    # 顺手把该角色的会战 EX 写回缓存：上面可能刚自动穿好，缓存还是空的，不写网页端
    # 「我的助战」看不到 EX 图标（unit_info 已是 parse_unit_data 的结果）。
    try:
        await pcr_sqla.set_player_unit_ex_equips(
            account.user_id,
            support_unit_id,
            {
                slot: (
                    unit_info.get(f"cb_ex_equip_{slot}") or 0,
                    unit_info.get(f"cb_ex_equip_{slot}_level") or 0,
                )
                for slot in (1, 2, 3)
            },
        )
    except Exception as e:
        logger.warning(f"更换助战后同步本地EX装备失败：{e!r}")

    # 网页端换完**团队战位**后本群公会助战缓存就旧了，用同一个已登录的 client 重拉
    # 一次写回（不额外登录）；只在 mode == 2 做，失败只记日志。
    if group_id and mode == 2:
        try:
            fresh_self = await get_support_list_with_client("self_query", client)
            await save_clan_support(client, group_id, fresh_self)
        except Exception as e:
            logger.warning(f"更换助战后刷新公会助战缓存失败：{e!r}")

    return SupportChangeResult(
        ok=True,
        message=result,
        mode=mode,
        unit_id=support_unit_id,
        position=db_position,
        removed_unit_id=removed_unit_id,
        star=plan.new_star if plan else 0,
        old_star=plan.old_star if plan else 0,
        unit=PlayerUnit(**unit_info),
    )


@functools.lru_cache(maxsize=128)
def read_knight_exp_rank(target_value: int) -> int:
    df = pd.read_csv(FilePath.data.value / "rank_exp.csv")
    exp_values = df.iloc[:, 0].values  # 第一列是经验值
    rank_values = df.iloc[:, 1].values  # 第二列是等级

    # 找到所有满足条件的索引
    valid_indices = exp_values <= target_value

    return int(rank_values[valid_indices][-1]) if valid_indices.any() else 1
