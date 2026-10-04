import base64
import contextlib
import functools
import gzip
import json
import time

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd
from hoshino.modules.priconne.chara import fromid
from nonebot import logger
from ..client.common import (
    ExtraEquipChangeSlot,
    ExtraEquipChangeUnit,
    ExtraEquipInfo,
    ExtraEquipSlot,
    SupportUnitSetting,
    UnitDataForClanMember,
)
from ..database.models import Account, PlayerUnit, SupportUnit
from ..login import query
from ..database.dal import pcr_sqla
from ..basedata import EquipRankExp, FilePath
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
        love_level = love_dict[unit_info["unit_id"]]
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
    support = await get_support_list_with_client("support_query", client)
    if "server_error" in support:
        raise SupportRefreshError("可能现在不是会战的时候或者网络异常")
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


# ---- 会战 EX 装备自动穿戴 ----
# 移植自 autopcr 的 `#挂会战支援`（`autopcr/module/modules/tools.py: set_cb_support`）：
# 挂上会战支援位之后，顺手把这个角色**空着的**会战 EX 槽补满。
#
# 主数据只需要一张槽位表（`resource/data/unit_ex_equipment_slot.json`，325 条 / 6.8KB）——
# 装备的类别 / 稀有度 / 是否会战专用都编码在 `ex_equipment_id` 里，不用另存一张装备表：
#     4101351 -> category=(4101351//1000)%1000=101, rarity=(4101351//100)%10=3, 51 结尾=会战专用
# 已用游戏主库 260 条装备全量验证过，0 条不符。
#
# 槽位表更新方法：从游戏主库（autopcr 的 `cache/db/<ver>.db`）导出
#     SELECT unit_id, slot_category_1, slot_category_2, slot_category_3 FROM unit_ex_equipment_slot
# 转成 `{str(unit_id // 100): [c1, c2, c3]}` 即可（unit_id 就是 chara_id*100+1）。


@functools.lru_cache(maxsize=1)
def _unit_ex_slot_table() -> Dict[str, List[int]]:
    """`chara_id -> [槽1类别, 槽2类别, 槽3类别]`。

    文件缺失就返回空表 —— 老部署没带这个 json 时自动降级成「不穿 EX」，不会报错。
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
    unit: Optional[PlayerUnit] = None  # 给 QQ 端出图用的完整数据


async def change_support_unit(
    account: Account,
    support_unit_id: int,
    mode: int,
    group_id: Optional[int] = None,
) -> SupportChangeResult:
    """把某个角色挂到指定栏位的助战。

    栏位满了就顶掉挂得最久的那个（游戏侧规则：挂满 30 分钟后才允许换）。
    挂**会战位**（mode=2）时还会顺手补满该角色空着的会战 EX 槽（`equip_clan_battle_ex`）。
    成功后会把**本地缓存的助战位和会战 EX 装备**一起改掉
    （`set_player_support_positions` / `set_player_unit_ex_equips`），
    这样网页端「我的助战」立刻是对的，不用再等一次【刷新box缓存】。

    传了 `group_id`（网页端会传）时，还会用**同一个已登录的 client** 把本群的
    **公会助战缓存**也重拉一次 —— 否则换完支援，公会助战页显示的还是旧的。
    只在 mode=2 做（公会助战缓存里只有团队战栏，见 `_self_clan_support_units`）。
    QQ 端不传 `group_id`，行为与耗时**完全不变**。

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

    for i in mode2str:
        for unit in current_support[i - 1]:
            if unit.unit_id == unit_id:
                return SupportChangeResult(
                    ok=False,
                    message=f"{support_unit_name}已经在{mode2str[i]}支援中",
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
    if unit_info.unit_level <= 10:
        return SupportChangeResult(
            ok=False,
            message=f"{support_unit_name}的等级过低(<=10级)，不可设置支援",
            mode=mode,
            unit_id=support_unit_id,
        )

    # 地下城：clan_support_units support_type=1 position=1/2 mode=1
    # 团队战/露娜塔：clan_support_units support_type=1 position=3/4 mode=2
    # 关卡：friend_support_units support_type=2 position=1/2 mode=3
    # "action": 1=上 2=下
    # "unit_id": xxxx01
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

    # 挂会战支援（团队战位）时顺手补满空着的会战 EX 槽 —— 移植自 autopcr 的 `#挂会战支援`。
    # 只处理 mode 2：会战 EX 槽本来就只对会战生效，地下城 / 关卡位没必要动。
    # 失败不影响「更换支援」本身（游戏侧已经改成功了），只记日志，别让用户以为换失败了。
    if mode == 2:
        try:
            filled = await equip_clan_battle_ex(client, player_info, unit_info)
            if filled:
                result += f"\n已为{support_unit_name}装备会战EX装（{'、'.join(filled)}）"
        except Exception as e:
            logger.warning(f"自动装备会战EX装失败：{e!r}")

    # ⚠️ 游戏侧 position 与本地库 support_position 不是同一套编号（别直接拿 try_position 写库）：
    #   地下城 / 团队战走 clan_support_units，库里存的是「游戏 position + 2」→ 3/4、5/6；
    #   关卡（冒险）走 friend_support_units，库里原样存 1/2。
    # 少了这个换算，网页端会按 3/4 去找地下城，而新角色被写进了 1/2 ——
    # 表现就是「换完支援，页面还显示上一个助战信息」。
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

    # 顺手把该角色的会战 EX 装备也写进缓存 —— 上面可能刚给它自动穿好 EX，
    # 缓存里还是旧的（空）值，网页端「我的助战」不点一次【刷新box缓存】就看不到
    # EX 图标。`unit_info` 这时已经是 `parse_unit_data` 的结果，EX 字段就是现成的。
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

    # 网页端（传了 group_id）：换完**团队战位**之后，本群的公会助战缓存就旧了 ——
    # 新挂上的角色不在里面、被顶掉的还留着。用**同一个已登录的 client** 顺手重拉一次
    # 写回缓存，不额外登录、不顶号。
    # 只在 mode == 2 做：公会助战缓存里只有团队战栏（线上库实测每人恰好 2 条 =
    # 游戏侧 clan 位 3/4），地下城 / 冒险栏的更换本来就不进这份缓存。
    # 失败只记日志 —— 游戏侧已经改成功了，缓存没跟上不该让用户以为「更换失败」。
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
