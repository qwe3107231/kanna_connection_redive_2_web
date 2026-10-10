"""从 autopcr 的游戏主数据库导出 EX 装备数据表 -> ``resource/data/ex_equipment.json``。

为什么要单独存一份
------------------
游戏里 EX 装备的**名称 / 类别名 / 每级属性上下限 / 星级所需强化PT** 全在主数据库
（autopcr 的 ``cache/db/<版本>.db``）里，本模块运行时不带那份库。自动穿会战 EX
（``support_query.util.equip_clan_battle_ex``）只需要「能不能穿」的判定，而这些判定
全编码在 ``ex_equipment_id`` 里（见 ``util.py`` 的注释），所以以前不查表；但网页端
要让用户**看见属性再挑装备**，就必须把这几张表导出成模块自带的小 json。

导出内容（约 240 件装备 / 60KB）
--------------------------------
    star_pt         稀有度 -> [强化到第1/2/3...颗星所需的累计 enhancement_pt]
    max_star_by_rank 稀有度 -> [突破等级 -> 该突破下最高星]
    max_rank        稀有度 -> 最高突破等级
    attr_max_star   稀有度 -> 算属性时用的分母（= 满突破下的最高星，见 autopcr
                    ``ExEquipmentDatum.get_unit_attribute``）
    categories      类别号 -> 类别名（101~110 / 201~204 / 301~305）
    equipments      装备ID -> {n 名称, c 类别, r 稀有度, cb 是否会战专用,
                    b/m 各属性 default_/max_ 值（只记非 0 的键）}

用法
----
    python support_query/gen_ex_equipment_data.py [游戏主库路径]

不传路径时自动找 autopcr 模块 ``cache/db/`` 下最新的 ``.db``。**游戏大版本更新后
再跑一次即可**，旧的 json 直接覆盖；``util.ex_equip_*`` 那套 id 编码判定不受影响。
"""

import json
import sqlite3
import sys
from pathlib import Path

# 属性列 -> 我们自己的键名。与 autopcr ``model.custom.UnitAttribute`` 的字段一一对应
# （``UnitAttribute.load(obj, pre='default_')`` 取的就是 ``default_<key>``）。
ATTR_KEYS = [
    "hp",
    "atk",
    "magic_str",
    "def",
    "magic_def",
    "physical_critical",
    "magic_critical",
    "wave_hp_recovery",
    "wave_energy_recovery",
    "dodge",
    "physical_penetrate",
    "magic_penetrate",
    "life_steal",
    "hp_recovery_rate",
    "energy_recovery_rate",
    "energy_reduce_rate",
    "accuracy",
]

# 默认去**兄弟模块** autopcr 的 cache/db 找主库（hoshino/modules/autopcr/cache/db/*.db）。
# 布局不一样就直接把路径当命令行参数传进来，别改这里。
DEFAULT_DB_DIR = (
    Path(__file__).resolve().parent.parent.parent / "autopcr" / "cache" / "db"
)
OUT_PATH = Path(__file__).resolve().parent.parent / "resource" / "data" / "ex_equipment.json"


def find_latest_db() -> Path:
    if not DEFAULT_DB_DIR.exists():
        raise SystemExit(f"找不到 autopcr 主数据库目录：{DEFAULT_DB_DIR}，请手动传路径")
    dbs = sorted(DEFAULT_DB_DIR.glob("*.db"), key=lambda p: p.stat().st_mtime)
    if not dbs:
        raise SystemExit(f"{DEFAULT_DB_DIR} 下没有 .db")
    return dbs[-1]


def main(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ---- 每级强化所需累计 PT（按稀有度）----
    star_pt: dict = {}
    for row in cur.execute(
        "select rarity, enhance_level, total_point from ex_equipment_enhance_data"
        " order by rarity, enhance_level"
    ):
        levels = star_pt.setdefault(str(row["rarity"]), {})
        if row["enhance_level"] <= 0:
            continue  # 0 级 = 未强化，total_point 恒为 0，不用记
        levels[row["enhance_level"]] = row["total_point"]
    star_pt = {r: [lv[r2] for r2 in sorted(lv)] for r, lv in star_pt.items()}

    # ---- 突破等级 -> 该突破下的最高星；以及最高突破等级 ----
    ranks: dict = {}
    for row in cur.execute(
        "select rarity, rankup_level, max(enhance_level) as star from ex_equipment_enhance_data"
        " group by rarity, rankup_level order by rarity, rankup_level"
    ):
        ranks.setdefault(str(row["rarity"]), {})[row["rankup_level"]] = row["star"]

    max_rank: dict = {}
    max_star_by_rank: dict = {}
    for row in cur.execute(
        "select rarity, max(rankup_level) as mr from ex_equipment_rankup_data group by rarity"
    ):
        max_rank[str(row["rarity"])] = row["mr"]
    for rarity, by_rank in ranks.items():
        last = max(by_rank)
        max_star_by_rank[rarity] = [by_rank.get(i, 0) for i in range(0, last + 1)]
        max_rank.setdefault(rarity, last)
    # 5 星彩装没有强化等级（enhance_level 只有 0），属性就取 default_ 值
    attr_max_star = {r: (v[-1] if v else 0) for r, v in max_star_by_rank.items()}

    # ---- 类别名 ----
    categories = {
        str(row["category"]): (row["category_name"] or "").strip()
        for row in cur.execute("select category, category_name from ex_equipment_category")
    }

    # ---- 5 星彩装的「词条」（词条池按 group 分组，实测 7 组 × 5~6 个 status）----
    # 每条数值 = 该 group 下该 status 的 value_{step}（step 1~5）。
    sub_status_group = {
        str(row["ex_equipment_id"]): int(row["group_id"])
        for row in cur.execute(
            "select ex_equipment_id, group_id from ex_equipment_sub_status_group"
        )
    }
    sub_status: dict = {}
    for row in cur.execute(
        "select group_id, status, value_1, value_2, value_3, value_4, value_5"
        " from ex_equipment_sub_status order by group_id, status"
    ):
        sub_status.setdefault(str(row["group_id"]), {})[str(row["status"])] = [
            row[f"value_{i}"] for i in range(1, 6)
        ]

    # ---- 装备本体 ----
    cols = [r[1] for r in cur.execute("PRAGMA table_info(ex_equipment_data)")]
    equipments = {}
    for row in cur.execute("select * from ex_equipment_data order by ex_equipment_id"):
        base, top = {}, {}
        for key in ATTR_KEYS:
            d = row[f"default_{key}"] if f"default_{key}" in cols else 0
            m = row[f"max_{key}"] if f"max_{key}" in cols else 0
            if d:
                base[key] = d
            if m:
                top[key] = m
        equipments[str(row["ex_equipment_id"])] = {
            "n": (row["name"] or "").strip(),
            "c": row["category"],
            "r": row["rarity"],
            "cb": row["clan_battle_equip_flag"],
            "b": base,
            "m": top,
        }

    data = {
        "_source": db_path.name,
        "star_pt": star_pt,
        "max_star_by_rank": max_star_by_rank,
        "max_rank": max_rank,
        "attr_max_star": attr_max_star,
        "categories": categories,
        "sub_status_group": sub_status_group,
        "sub_status": sub_status,
        "equipments": equipments,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    # 简单自检：类别 / 稀有度 / 属性上下限都齐了才认为导出成功
    missing = [k for k, v in equipments.items() if not v["n"]]
    no_attr = [k for k, v in equipments.items() if not v["b"] and not v["m"]]
    print(f"source       : {db_path}")
    print(f"out          : {OUT_PATH} ({OUT_PATH.stat().st_size} bytes)")
    print(f"equipments   : {len(equipments)}  (无名 {len(missing)} / 无属性 {len(no_attr)})")
    print(f"star_pt      : {star_pt}")
    print(f"max_star/rank: {max_star_by_rank}")
    print(f"max_rank     : {max_rank}")
    print(f"attr_max_star: {attr_max_star}")
    print(f"categories   : {categories}")
    print(
        f"sub_status   : {len(sub_status_group)} 件彩装 / "
        f"{len(sub_status)} 个词条池 / "
        f"{sum(len(v) for v in sub_status.values())} 条词条定义"
    )
    if missing:
        print("!! 有装备没有名字：", missing[:10])
    conn.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(Path(sys.argv[1]))
    else:
        main(find_latest_db())
