"""EX 装备的静态数据（名称 / 类别 / 稀有度 / 属性上下限）与属性换算。

数据来自 ``resource/data/ex_equipment.json``，由 ``support_query/gen_ex_equipment_data.py``
从游戏主数据库导出（见那个脚本的说明）。运行时不依赖 autopcr，也不打任何网络请求。

**为什么需要它**：``ex_equipment_id`` 的编码只够判断「属于哪个槽 / 多稀有 / 会不会战专用」
（见 ``util.ex_equip_category`` 等），要让人在网页端看见属性再挑装备，就得有这张表。

几个口径都是照抄 autopcr 的 ``db.ExEquipmentDatum.get_unit_attribute``：

    star        = star_pt 里第一个大于 enhancement_pt 的档位下标（0 = 没强化）
    attr(key)   = default[key] + (max[key] - default[key]) * star / attr_max_star
                  （attr_max_star = 0 时直接取 default[key]，即 5 星彩装）
    is_present  = hp / atk / magic_str / def / magic_def / 物爆 / 法爆 这 7 项，
                  数值是「角色基础属性的万分比」（700 = 7%），其余是固定值

**不要**把这些口径和 ``util.ex_equip_exp2star`` 混用：那个是 QQ 端出图用的旧实现，
按 id 里的稀有度硬编码了三档表（对 5 星彩装会算出不存在的星级）。网页端一律走这里。
"""

import functools
import json
from typing import Dict, List, Optional

from nonebot import logger

from ..basedata import FilePath

# 属性键 -> (显示名, 是否万分比)，顺序就是界面上的展示顺序。
# 万分比的 7 项与 autopcr ``UnitAttribute.is_present`` 一致；写全 17 项免得顺序随机。
ATTRIBUTE_LABELS: List[tuple] = [
    ("hp", "血量", True),
    ("atk", "物攻", True),
    ("magic_str", "魔攻", True),
    ("def", "物防", True),
    ("magic_def", "魔防", True),
    ("physical_critical", "物爆", True),
    ("magic_critical", "法爆", True),
    ("dodge", "闪避", False),
    ("physical_penetrate", "物穿", False),
    ("magic_penetrate", "魔穿", False),
    ("life_steal", "吸血", False),
    ("wave_hp_recovery", "每波回血", False),
    ("wave_energy_recovery", "每波回TP", False),
    ("hp_recovery_rate", "回复量上升", False),
    ("energy_recovery_rate", "TP上升", False),
    ("energy_reduce_rate", "TP减轻", False),
    ("accuracy", "命中", False),
]

# 稀有度 -> 中文（与 autopcr ``db.ex_rarity_name`` 一致）
RARITY_NAMES = {1: "铜", 2: "银", 3: "金", 4: "粉", 5: "彩"}

# 词条的属性编号 -> 属性键。编号是游戏 ``eParamType``；实测彩装只用到 1~17 这批。
# 注意顺序和 ``ATTRIBUTE_LABELS`` 的展示顺序**不一样**，别按序号猜。
PARAM_KEYS = {
    1: "hp",
    2: "atk",
    3: "def",
    4: "magic_str",
    5: "magic_def",
    6: "physical_critical",
    7: "magic_critical",
    8: "dodge",
    9: "life_steal",
    10: "wave_hp_recovery",
    11: "wave_energy_recovery",
    12: "physical_penetrate",
    13: "magic_penetrate",
    14: "energy_recovery_rate",
    15: "hp_recovery_rate",
    16: "energy_reduce_rate",
    17: "accuracy",
}

_LABEL_BY_KEY = {key: (label, percent) for key, label, percent in ATTRIBUTE_LABELS}


def rarity_name(rarity: int) -> str:
    return RARITY_NAMES.get(int(rarity or 0), "")


def _empty() -> dict:
    return {
        "star_pt": {},
        "max_star_by_rank": {},
        "max_rank": {},
        "attr_max_star": {},
        "categories": {},
        "sub_status_group": {},
        "sub_status": {},
        "equipments": {},
    }


@functools.lru_cache(maxsize=1)
def _data() -> dict:
    """读一次 ``ex_equipment.json`` 并缓存（进程内只读一次）。

    文件缺失时返回空壳：老部署没带这个 json 时网页端只会「看不到装备列表」，
    不会让整个 BOX 页面 500。和 ``util._unit_ex_slot_table`` 的降级策略一致。
    """
    path = FilePath.data.value / "ex_equipment.json"
    if not path.exists():
        logger.warning(f"缺少 EX 装备数据表 {path}，网页端 EX 装备属性将不可用")
        return _empty()
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"读取 EX 装备数据表失败 {path}：{e}")
        return _empty()


def is_available() -> bool:
    """数据表在不在（在的话网页端才显示「普通 EX 槽」的装备列表）。"""
    return bool(_data()["equipments"])


def equipment(equipment_id: int) -> Optional[dict]:
    """装备 ID -> {"n": 名称, "c": 类别, "r": 稀有度, "cb": 会战专用, "b"/"m": 属性}。"""
    return _data()["equipments"].get(str(int(equipment_id or 0)))


def equipment_name(equipment_id: int) -> str:
    info = equipment(equipment_id)
    if info and info.get("n"):
        return info["n"]
    return f"未知EX装备({equipment_id})"


def equipment_rarity(equipment_id: int) -> int:
    info = equipment(equipment_id)
    return int(info["r"]) if info else 0


def category_name(category: int) -> str:
    return _data()["categories"].get(str(int(category or 0)), "")


def max_star(equipment_id: int) -> int:
    """这件装备**能強化到**的最高星（= 满突破下的最高星）。

    注意这只是个参考值：真正能到几星还要看该件装备自己的突破等级
    （``enhancement_pt`` 升不上去时游戏也会卡住）。属性换算用的分母就是它，
    与 autopcr ``get_unit_attribute`` 取 ``get_ex_equip_max_star(id, max_rank)`` 一致。
    """
    info = equipment(equipment_id)
    if not info:
        return 0
    return int(_data()["attr_max_star"].get(str(info["r"]), 0))


def star_from_pt(equipment_id: int, enhancement_pt: int) -> int:
    """按强化 PT 算当前星级（0 = 未强化，最高 = 该稀有度的满星）。"""
    info = equipment(equipment_id)
    if not info:
        return 0
    thresholds = _data()["star_pt"].get(str(info["r"])) or []
    pt = int(enhancement_pt or 0)
    star = 0
    for index, need in enumerate(thresholds, start=1):
        if pt >= need:
            star = index
        else:
            break
    return star


def attributes(equipment_id: int, star: int) -> List[Dict]:
    """这件装备在某星级下的属性，返回 [{"key","label","value","percent","text"}]。

    只列有值的项（游戏里也是这么显示的）；万分比的那 7 项 text 已经换算成
    「7%」这种百分比，前端直接展示即可。
    """
    info = equipment(equipment_id)
    if not info:
        return []
    star = int(star or 0)
    denominator = int(_data()["attr_max_star"].get(str(info["r"]), 0))
    base: dict = info.get("b") or {}
    top: dict = info.get("m") or {}
    result = []
    for key, label, percent in ATTRIBUTE_LABELS:
        low = base.get(key, 0)
        high = top.get(key, 0)
        if denominator > 0 and star > 0:
            value = low + (high - low) * star / denominator
        else:
            value = low
        value = int(round(value))
        if value == 0:
            continue
        if percent:
            # 万分比 -> 百分比。700 -> "7%"，117 -> "1.17%"
            text = f"{value / 100:g}%"
        else:
            text = f"{value}"
        result.append(
            {
                "key": key,
                "label": label,
                "value": value,
                "percent": percent,
                "text": text,
            }
        )
    return result


def equipment_payload(equipment_id: int, star: int) -> Dict:
    """给网页端用的装备概要（名称 / 类别 / 稀有度 / 属性 / 图标路径用的 id）。"""
    info = equipment(equipment_id) or {}
    return {
        "equipment_id": int(equipment_id or 0),
        "name": equipment_name(equipment_id),
        "category": int(info.get("c") or 0),
        "category_name": category_name(int(info.get("c") or 0)),
        "rarity": int(info.get("r") or 0),
        "rarity_name": rarity_name(int(info.get("r") or 0)),
        "clan_battle": bool(info.get("cb")),
        "star": int(star or 0),
        "max_star": max_star(equipment_id),
        "attrs": attributes(equipment_id, star),
        "sub_statuses": [],
    }


# ---- 5 星彩装词条：游戏只给 (status, step)，数值要查该 group 的 value_{step} 表 ----
# 换算口径照抄 autopcr `db.get_ex_equip_sub_status_str`（万分比项 /100 显示成百分比）。


def sub_status_group(equipment_id: int) -> int:
    return int(
        (_data().get("sub_status_group") or {}).get(str(int(equipment_id or 0)), 0)
    )


def sub_status_value(equipment_id: int, status: int, step: int) -> Optional[int]:
    """一条词条的数值；这个装备/属性/等级查不到时返回 None。"""
    group = sub_status_group(equipment_id)
    if not group:
        return None
    values = ((_data().get("sub_status") or {}).get(str(group)) or {}).get(
        str(int(status or 0))
    )
    if not values:
        return None
    step = int(step or 0)
    if not 1 <= step <= len(values):
        return None
    return int(values[step - 1])


def field_of(item, name):
    """按名字取值，兼容 **dict 和 pydantic 对象**两种入参。

    游戏数据是 pydantic 对象（`client.common.ExtraEquipSubStatus`），但存库/测试里
    常常是普通 dict，两处都要能用。
    """
    if isinstance(item, dict):
        return item.get(name)
    return getattr(item, name, None)


def sub_status_entries(equipment_id: int, raw) -> List[Dict]:
    """把一件彩装的词条翻成前端可展示的列表（**同一属性会合并累加**）。

    `raw` 是 `client.common.ExtraEquipSubStatus` 列表（dict 形状也行）。
    口径与 autopcr `db.get_ex_equip_sub_status_str` 一致：
      - 同一属性出现多条时**数值相加**（一件装备上两条物穿 → 只显示一条「物穿 10」），
        所以一件彩装最多就是 4 项，正好对得上游戏里那 4 条；
      - 万分比项（血量 / 物攻 / 魔攻 / 物防 / 魔防 / 物爆 / 法爆）显示成 `1.00%` 这种
        两位小数的百分比，其余是固定值；
      - 按属性编号排序（血量 → 物攻 → … → 物穿），和 autopcr 的输出顺序一致。
    查不到定义的那条直接跳过；锁定与否**不输出**（那是炼成时的事，和换装无关）。
    """
    totals: Dict[int, int] = {}
    for item in raw or []:
        status = int(field_of(item, "status") or 0)
        step = int(field_of(item, "step") or 0)
        if status not in PARAM_KEYS:
            continue
        value = sub_status_value(equipment_id, status, step)
        if value is None:
            continue
        totals[status] = totals.get(status, 0) + value

    result: List[Dict] = []
    for status in sorted(totals):
        key = PARAM_KEYS[status]
        label, percent = _LABEL_BY_KEY.get(key, (key, False))
        value = totals[status]
        result.append(
            {
                "status": status,
                "key": key,
                "label": label,
                "percent": percent,
                "value": value,
                "text": f"{value / 100:.2f}%" if percent else f"{value}",
            }
        )
    return result
