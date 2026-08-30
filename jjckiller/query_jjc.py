import contextlib
import json
import os
import time
import traceback
from math import log
from os.path import exists
from random import random
from typing import List, Tuple, Union

import nonebot
from hoshino.modules.priconne import chara
from loguru import logger

from ..setting import JJCSetting
from ..util.tools import load_config, write_config
from .base import id_list2str, id_str2list
from .pcrdapi import callPcrd

all_seq = {
    1: [2, 4, 3],  # 全服查询顺序为[B,日,台]
    2: [1, 3, 4],  # B服查询顺序为[全,台,日]
    3: [1, 2, 4],  # 台服查询顺序为[全,B,日]
    4: [1, 3, 2],  # 日服查询顺序为[全,台,B]
}


buffer_path = str(JJCSetting.buff_path.value / "buffer.json")
buffer = load_config(buffer_path)
best_atk_records_path = str(JJCSetting.buff_path.value / "best_atk_records.json")


@nonebot.on_startup
async def update_record_start():
    global best_atk_records
    if not exists(best_atk_records_path):
        update_record()
    with open(best_atk_records_path, "r", encoding="utf-8") as fp:
        best_atk_records = json.load(fp)


def update_record():
    buffer_region_cnt = [{}, {}, {}, {}, {}]  # 全服=1 b服=2 台服=3 日服=4
    tot_file_cnt = len(os.listdir(buffer_path))
    for filename in os.listdir(buffer_path):  # 我为什么不用buffer.json 我是猪鼻
        if len(filename) != 26:
            continue

        try:
            region = int(filename[-6])
            if region == 1:  # 按理说全服查询可能出现任何角色，应该归入4
                region = 2  # 但本bot 绝大多数的全服查询实际均为国服，因此归入国服。少数的其它服查询在频率排序后会被滤过。
            if region not in [1, 2, 3, 4]:
                continue

            filepath = str(JJCSetting.buff_path.value / filename)
            with open(filepath, "r", encoding="utf-8") as fp:
                records = json.load(fp)

            for record in records:
                if "atk" in record:
                    unit_id_list = tuple(
                        unit.get("id", 100001) + unit.get("star", 3) * 10
                        for unit in record["atk"]
                    )
                    buffer_region_cnt[region][unit_id_list] = 1 + buffer_region_cnt[
                        region
                    ].get(unit_id_list, 0)
        except Exception:
            continue

    best_atk_records_item = sorted(
        buffer_region_cnt[2].items(), key=lambda x: x[1], reverse=True
    )
    best_atk_records = [x[0] for x in best_atk_records_item[:200]]
    with open(best_atk_records_path, "w", encoding="utf-8") as fp:
        json.dump(best_atk_records, fp, ensure_ascii=False, indent=4)

    return f"从{tot_file_cnt}个文件中搜索到{len(buffer_region_cnt[2])}个进攻阵容（不计日台服查询）\n已缓存最频繁使用的{len(best_atk_records)}个阵容"


async def find_approximate_team(id_list: List[int], region: int = 1):
    if len(id_list) == 4:
        id_list.append(1000)
    logger.info(f"查询近似解：{sorted(id_list)}")
    result = []
    for buffer_id_str in buffer:  # "100110021018105211222"
        if len(buffer_id_str) != 21:
            continue
        if buffer_id_str[-1] not in ["1", "2"]:
            continue
        # [1001, 1002, 1018, 1052, 1122]
        if len(set(id_str2list(buffer_id_str)) & set(id_list)) >= 4:
            pa = str(JJCSetting.buff_path.value / f"{buffer_id_str}.json")
            if exists(pa):
                result += load_config(pa)
    if len(result) < 200 and 1000 in id_list:
        logger.info("近似解较少，尝试直接查询")
        with contextlib.suppress(Exception):
            resp = await callPcrd(id_list[:-1], 1, region, 1)
            result += resp
    logger.info(f"共有{len(result)}条记录")
    render = result2render(result, "approximation", id_list)[:200]
    return list(sorted(render, key=lambda x: x.get("val", -100), reverse=True))[:10]


def result2render(result: dict, team_type="normal", id_list=None):
    """
    team_type:
    "normal":正常查询的阵容
    "approximation":根据近似解推荐的阵容 由id_list字段自动计算uid_4_1 uid_4_2

    "approximation uid_4_1 uid_4_2":根据近似解推荐的阵容 原查询角色uid_4_1 被替换为 近似查询角色uid_4_2 # 本函数不支持
    "frequency":根据频率推荐的阵容 # 本函数不支持
    "youshu":五个佑树 # 本函数不支持
    """
    if id_list is None:
        id_list = []
    render = []
    duplicated = set()
    for entry in result:
        fingerprint = "".join(
            [
                str(x)
                for x in (
                    [c["id"] // 100 for c in entry["atk"]]
                    + [c["id"] // 100 for c in entry["def"]]
                )
            ]
        )
        if fingerprint in duplicated:
            continue
        duplicated.add(fingerprint)
        # atk up down val: 都一样
        # team_type: approximation要手动算 nomal直接贴
        if team_type == "approximation":
            with contextlib.suppress(Exception):
                entry_id_list = [c["id"] // 100 for c in entry["def"]]
                team_type = f"approximation {list((set(id_list) - set(entry_id_list)))[0]} {list((set(entry_id_list) - set(id_list)))[0]}"

        render.append(
            {
                "atk": [
                    chara.fromid(c["id"] // 100, c["star"], c["equip"])
                    for c in entry["atk"]
                ],
                "up": entry["up"],
                "down": entry["down"],
                "val": caculateVal(entry),
                "team_type": team_type,
                "comment": entry["comment"],
            }
        )

    return render


def caculateVal(record) -> float:
    up_vote = int(record["up"])
    down_vote = int(record["down"])
    val_1 = up_vote / (down_vote + up_vote + 0.0001) * 2 - 1  # 赞踩比占比 [-1, 1]
    val_2 = log(up_vote + down_vote + 0.01, 100)  # 置信度占比（log(100)）[-1,+inf]
    return val_1 + val_2 + random() / 1000  # 阵容推荐度权值


async def do_query(id_list: List[int], region: int = 1) -> Union[str, List[dict]]:
    if len(id_list) < 4:
        return ["lossunit"]
    if len(id_list) == 4:
        return await find_approximate_team(id_list, region)

    key = id_list2str(id_list) + str(region)

    logger.info(f"查询阵容：{key}")

    now_time = time.time()
    # 5天内查询过 直接返回
    result = None
    degrade_result = None
    key_path = str(JJCSetting.buff_path.value / f"{key}.json")
    if degrade_result := load_config(key_path):
        if now_time - buffer.get(key, 0) >= 3600 * 24 * 5:
            logger.info(f"存在本服({region})远缓存，作为降级备用")
        else:
            logger.info(f"存在本服({region})近缓存，直接使用")
            result = degrade_result
    else:
        logger.info(f"不存在本服({region})缓存，查找它服缓存")
        for other_region in all_seq.get(region, []):
            other_key = "".join([str(x) for x in sorted(id_list)]) + str(other_region)
            if degrade_result := load_config(
                str(JJCSetting.buff_path.value / f"{other_key}.json")
            ):
                logger.info(f"存在它服({other_region})缓存，作为降级备用")
                break
        else:
            logger.info("不存在它服缓存")

    if not result:
        try:
            result = await callPcrd(id_list, 1, region, 1)
            logger.info(f"查询成功，共有{len(result)}条结果")
            if not len(result):
                raise

            logger.info("保存结果至缓存库")
            buffer[key] = int(now_time)
            write_config(buffer_path, buffer)
            write_config(str(JJCSetting.buff_path.value / f"{key}.json"), result)
        except Exception:
            if not degrade_result:
                logger.info("查询失败并且无缓存，查询近似解")
                return await find_approximate_team(id_list, region)
            logger.info("查询失败，使用缓存")
            result = degrade_result

    render = result2render(result)
    if len(render) < 10:
        logger.info("    结果较少，查询近似解")
        # 裁剪去重
        approximate_result = await find_approximate_team(id_list, region)
        for result1 in render:
            for i, result2 in enumerate(approximate_result):
                if result1["atk"] == result2["atk"]:
                    approximate_result.pop(i)
        render += approximate_result

    if not result:
        remove_buffer(key)

    logger.info(f"共有{len(render)}条结果")

    return render[:10]


def recommend_team(
    already_used_units: List[int], team_num: int
) -> Tuple[Union[str, dict]]:
    """
    already_used_units: [1110,1008,1011,1026,1089] 不可使用的角色id（四位）
    return : render | "placeholder"
    """
    try_combinations = []
    result = ["placeholder"] * team_num
    if team_num == 1:
        # [111451,101261,110351,103461,103261]
        for record_6 in best_atk_records:
            # [1114,1012,1103,1034,1032]
            record_4 = [x // 100 for x in record_6]
            team_mix = already_used_units + record_4
            if len(team_mix) == len(set(team_mix)):  # 推荐配队成功
                result[0] = {
                    "atk": [
                        chara.fromid(uid_6 // 100, uid_6 % 100 // 10)
                        for uid_6 in record_6
                    ],
                    "team_type": "frequency",
                }
    elif team_num == 2:
        for record_1_index in range(len(best_atk_records) - 1):
            try_combinations.extend(
                [
                    record_1_index,
                    record_2_index,
                    record_1_index + record_2_index,
                ]
                for record_2_index in range(record_1_index + 1, len(best_atk_records))
            )
        try_combinations = sorted(try_combinations, key=lambda x: x[-1])
        for try_combination in try_combinations:
            record_6_1 = best_atk_records[try_combination[0]]
            record_4_1 = [x // 100 for x in record_6_1]

            record_6_2 = best_atk_records[try_combination[1]]
            record_4_2 = [x // 100 for x in record_6_2]

            team_mix = already_used_units + record_4_1 + record_4_2
            if len(team_mix) == len(set(team_mix)):  # 推荐配队成功
                result[0] = {
                    "atk": [
                        chara.fromid(uid_6 // 100, uid_6 % 100 // 10)
                        for uid_6 in record_6_1
                    ],
                    "team_type": "frequency",
                }
                result[1] = {
                    "atk": [
                        chara.fromid(uid_6 // 100, uid_6 % 100 // 10)
                        for uid_6 in record_6_2
                    ],
                    "team_type": "frequency",
                }

    else:
        for record_1_index in range(len(best_atk_records) - 2):
            for record_2_index in range(record_1_index + 1, len(best_atk_records) - 1):
                try_combinations.extend(
                    [
                        record_1_index,
                        record_2_index,
                        record_3_index,
                        record_1_index + record_2_index + record_3_index,
                    ]
                    for record_3_index in range(
                        record_2_index + 1, len(best_atk_records)
                    )
                )
        try_combinations = list(sorted(try_combinations, key=lambda x: x[-1]))
        for try_combination in try_combinations:
            record_6_1 = best_atk_records[try_combination[0]]
            record_4_1 = [x // 100 for x in record_6_1]

            record_6_2 = best_atk_records[try_combination[1]]
            record_4_2 = [x // 100 for x in record_6_2]

            record_6_3 = best_atk_records[try_combination[2]]
            record_4_3 = [x // 100 for x in record_6_3]

            team_mix = record_4_1 + record_4_2 + record_4_3
            if len(team_mix) == len(set(team_mix)):  # 推荐配队成功
                result[0] = {
                    "atk": [
                        chara.fromid(uid_6 // 100, uid_6 % 100 // 10)
                        for uid_6 in record_6_1
                    ],
                    "team_type": "frequency",
                }
                result[1] = {
                    "atk": [
                        chara.fromid(uid_6 // 100, uid_6 % 100 // 10)
                        for uid_6 in record_6_2
                    ],
                    "team_type": "frequency",
                }
                result[2] = {
                    "atk": [
                        chara.fromid(uid_6 // 100, uid_6 % 100 // 10)
                        for uid_6 in record_6_3
                    ],
                    "team_type": "frequency",
                }
    return tuple(result) if len(result) > 1 else result[0]


def remove_buffer(uid: str):
    with contextlib.suppress(Exception):
        os.remove(JJCSetting.buff_path.value / f"{uid}.json")
        del buffer[uid]
        with open(buffer_path, "w", encoding="utf-8") as fp:
            json.dump(buffer, fp, ensure_ascii=False, indent=4)


async def generate_collision_free_team(all_query_records):
    """
    all_query_records
    [
        [
            [None, -100, "placeholder"], # 通配，等待从缓存中获取配队
            [(1110,1008,1011,1026,1089), 2.105, render], # [(第1队第1解),权值,render(渲染该队所需数据)]
            [(1111,1008,1802,1012,1014), 1.152, render] # [(第1队第2解),权值,render]
        ],
        [
            [None, -100, "placeholder"], # 通配
            [(第2队第1解),权值,render]
        ]
    ]
    """
    collision_free_match_cnt = 0
    outp_render = []
    collision_free_match_cnt_2 = 0  # 处理三队查询只能两队无冲的情况
    outp_render_2 = []
    try_combinations = []

    if len(all_query_records) == 0:
        team_recommend_1, team_recommend_2 = recommend_team([], 2)
        if team_recommend_1 != "placeholder" and team_recommend_2 != "placeholder":
            outp_render = [team_recommend_1, team_recommend_2, []]
            collision_free_match_cnt_2 += 1

    if len(all_query_records) == 1:
        try_combinations = sorted(
            [
                [query_1_index, query_1_record[1]]
                for query_1_index, query_1_record in enumerate(all_query_records[0])
            ],
            key=lambda x: x[-1],
            reverse=True,
        )
        for try_combination in try_combinations:
            succ = False
            # [(1110,1008,1011,1026,1089), 2.105, render] # 或通配
            record_1 = all_query_records[0][try_combination[0]]
            team_1 = (
                [] if record_1[0] is None else list(record_1[0])
            )  # (1110,1008,1011,1026,1089)

            val = try_combination[-1]
            if val < -250:
                break
            elif val < -150:  # 已有0队，要补2队 # 只会出现一次
                team_recommend_1, team_recommend_2 = recommend_team(team_1, 2)
                if (
                    team_recommend_1 == "placeholder"
                    or team_recommend_2 == "placeholder"
                ):
                    continue
                record_1[-1] = team_recommend_1
                record_2 = [team_recommend_2]
                succ = True
            else:  # 已有1队，要补1队
                team_recommend = recommend_team(team_1, 1)
                if team_recommend == "placeholder":
                    continue
                record_2 = [team_recommend]
                succ = True

            if succ:
                collision_free_match_cnt += 1
                outp_render += [record_1[-1], record_2[-1], []]
                if collision_free_match_cnt >= 8:
                    break
    elif len(all_query_records) == 2:
        for query_1_index, query_1_record in enumerate(all_query_records[0]):
            for query_2_index, query_2_record in enumerate(all_query_records[1]):
                try_combinations.append(
                    [
                        query_1_index,
                        query_2_index,
                        query_1_record[1] + query_2_record[1],
                    ]
                )
        try_combinations = sorted(try_combinations, key=lambda x: x[-1], reverse=True)

        for try_combination in try_combinations:
            succ = False
            # [(1110,1008,1011,1026,1089), 2.105, render] # 或通配
            record_1 = all_query_records[0][try_combination[0]]
            record_2 = all_query_records[1][try_combination[1]]
            team_1 = (
                [] if record_1[0] is None else list(record_1[0])
            )  # (1110,1008,1011,1026,1089)
            team_2 = [] if record_2[0] is None else list(record_2[0])
            team_mix = team_1 + team_2  # list
            if len(team_mix) != len(set(team_mix)):  # 存在冲突
                continue

            val = try_combination[-1]
            if val < -250:
                break
            if val < -150:  # 已有0队，要补2队 # 只会出现一次
                team_recommend_1, team_recommend_2 = recommend_team(team_mix, 2)
                if (
                    team_recommend_1 == "placeholder"
                    or team_recommend_2 == "placeholder"
                ):
                    continue
                record_1[-1] = team_recommend_1
                record_2[-1] = team_recommend_2
            elif val < -50:  # 已有1队，要补1队
                team_recommend = recommend_team(team_mix, 1)
                if team_recommend == "placeholder":
                    continue
                if not team_1:
                    record_1[-1] = team_recommend
                if not team_2:
                    record_2[-1] = team_recommend
            succ = True
            if succ:
                collision_free_match_cnt += 1
                outp_render += [record_1[-1], record_2[-1], []]
                if collision_free_match_cnt >= 8:
                    break

    elif len(all_query_records) == 3:
        for query_1_index, query_1_record in enumerate(all_query_records[0]):
            for query_2_index, query_2_record in enumerate(all_query_records[1]):
                for query_3_index, query_3_record in enumerate(all_query_records[2]):
                    val = query_1_record[1] + query_2_record[1] + query_3_record[1]
                    try_combinations.append(
                        [query_1_index, query_2_index, query_3_index, val]
                    )
        try_combinations = sorted(try_combinations, key=lambda x: x[-1], reverse=True)

        for try_combination in try_combinations:
            succ = False
            # [(1110,1008,1011,1026,1089), 2.105, render] # 或通配
            record_1 = all_query_records[0][try_combination[0]]
            record_2 = all_query_records[1][try_combination[1]]
            record_3 = all_query_records[2][try_combination[2]]
            team_1 = (
                [] if record_1[0] is None else list(record_1[0])
            )  # (1110,1008,1011,1026,1089)
            team_2 = [] if record_2[0] is None else list(record_2[0])
            team_3 = [] if record_3[0] is None else list(record_3[0])
            team_mix = team_1 + team_2 + team_3  # list
            if len(team_mix) != len(set(team_mix)):  # 存在冲突
                continue

            val = try_combination[-1]
            if val < -250:
                break
            if val < -150:  # 已有1队，要补2队
                team_recommend_1, team_recommend_2 = recommend_team(team_mix, 2)
                if (
                    team_recommend_1 == "placeholder"
                    or team_recommend_2 == "placeholder"
                ):
                    continue
                if team_1 != []:
                    record_2[-1] = team_recommend_1
                    record_3[-1] = team_recommend_2
                if team_2 != []:
                    record_3[-1] = team_recommend_1
                    record_1[-1] = team_recommend_2
                if team_3 != []:
                    record_1[-1] = team_recommend_1
                    record_2[-1] = team_recommend_2
                succ = True
            elif val < -50:  # 已有2队，要补1队 # 此时已有两队无冲
                team_recommend = recommend_team(team_mix, 1)
                if team_recommend == "placeholder":
                    collision_free_match_cnt_2 += 1
                    outp_render_2 += [record_1[-1], record_2[-1], record_3[-1], []]
                else:
                    if not team_1:
                        record_1[-1] = team_recommend
                    if not team_2:
                        record_2[-1] = team_recommend
                    if not team_3:
                        record_3[-1] = team_recommend
                    succ = True
            else:  # 已有3队
                succ = True

            if succ:
                collision_free_match_cnt += 1
                outp_render += [record_1[-1], record_2[-1], record_3[-1], []]
                # print(f'当前无冲配队数={collision_free_match_cnt} len(outp_render)={len(outp_render)}')  # test
                if collision_free_match_cnt >= 6:
                    break

    if collision_free_match_cnt or collision_free_match_cnt_2:
        # print(f'\n\n总共无冲配队数={collision_free_match_cnt} len(outp_render)={len(outp_render)}')  # test
        return outp_render[:-1]
    return None
