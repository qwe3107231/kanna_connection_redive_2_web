import time
from typing import Dict, List, Union

from hoshino.modules.priconne._pcr_data import CHARA_NAME
from loguru import logger

from ...convert2img.convert2img import grid2imgb64
from ..basedata import FilePath, stage_dict
from ..client.common import InventoryInfo
from ..client.response import ClanBattlePeriodRanking
from ..database.models import RecordDao
from ..util.auto_boss import clan_boss_info
from ..util.text2img import image_draw
from ..util.tools import daoflag2str


async def units2workid(*args):
    return []


try:
    from ..fendao.timeaxis import units2workid
except Exception:
    units2workid = units2workid

run_path = str(FilePath.run_group.value)


def find_item(item_list: List[InventoryInfo], id: int) -> int:
    if item_list:
        for item in item_list:
            if item.id == id:
                return item.stock
    return 0


def float2int(num: float) -> Union[int, float]:
    # 去小数点后面的0
    return int(num) if num == int(num) else num


def format_time(time: float) -> str:
    time = int(time)
    time_str = ""
    if hour := time // 3600:
        time_str += f"{hour}小时"
    if minute := time % 3600 // 60:
        time_str += f"{minute}分钟"
    if second := time % 60:
        time_str += f"{second}秒"
    return time_str


def format_bignum(num: int) -> str:
    return f"{num // 10000}万" if num > 10000 else num


def format_precent(num: int) -> str:
    return "血皮" if num < 0.00005 else f"{num * 100:.2f}%"


def clanbattle_report(info: List[RecordDao], max_dao: int) -> tuple:
    all_damage = 0
    all_score = 0
    player_info = {
        player.pcrid: {
            "name": player.name,
            "knife": 0,
            "damage": 0,
            "score": 0,
        }
        for player in info
    }
    for player in info:
        player_info[player.pcrid]["knife"] += 1 if player.flag == 0 else 0.5
        player_info[player.pcrid]["damage"] += player.damage
        all_damage += player.damage
        boss_rate = clan_boss_info.get_boss_rate(player.lap, player.boss)
        player_info[player.pcrid]["score"] += boss_rate * player.damage
        all_score += boss_rate * player.damage
    players = [
        (
            pcr_id,
            player_info[pcr_id]["name"],
            min(float2int(player_info[pcr_id]["knife"]), max_dao),
            player_info[pcr_id]["damage"],
            int(player_info[pcr_id]["score"]),
        )
        for pcr_id in player_info
    ]
    players.sort(key=lambda x: x[4], reverse=True)
    return players, all_damage, int(all_score)


async def day_report(info: List[RecordDao], all_player: Dict[int, str]) -> dict:
    player_info = {
        player: {"name": all_player[player], "knife": 0} for player in all_player
    }
    for player in info:
        if player.pcrid not in player_info:
            player_info[player.pcrid] = {
                "name": player.name,
                "knife": 0,
            }
        player_info[player.pcrid]["knife"] += 1 if player.flag == 0 else 0.5
    return [
        (pcr_id, player_info[pcr_id]["name"], float2int(player_info[pcr_id]["knife"]))
        for pcr_id in player_info
    ]


async def get_stat(data: list) -> str:
    member_dao = []
    stat = {3: [], 2.5: [], 2: [], 1.5: [], 1: [], 0.5: [], 0: []}
    total = 0
    for member in data:
        name = member[1]
        dao = min(member[2], 3)
        stat[dao].append(name)
        total += dao
        member_dao.append(name)
    reply = ["以下是出刀次数统计：\n", f"总计出刀：{total}"]
    for k, v in stat.items():
        if len(v) > 0:
            reply.extend((f"\n----------\n以下是出了{k}刀的成员：", "|".join(v)))
    msg = "".join(reply)
    return image_draw(msg)


def cuidao(data: list) -> str:
    if member_dao := [member[1] for member in data if member[2] < 3]:
        msg = "以下是还没满三刀的人：\n" + "\n".join(member_dao)
        return image_draw(msg)
    return "今天所有刀都出啦。下班下班。"


# 会战排名奖励档表（上限边界作为默认查询档位，每档正好对应一个奖励段分数线）
# 2026-09 更新：bilibili 官服最新会战奖励（行会币整体上调，碎片为当期角色记忆碎片）
RANK_REWARD_TABLE = (
    (1, 10, 20000, 10000, 30),
    (11, 40, 15000, 10000, 30),
    (41, 120, 13000, 10000, 30),
    (121, 200, 11000, 10000, 30),
    (201, 400, 9000, 10000, 30),
    (401, 800, 7000, 9000, 25),
    (801, 1800, 6000, 8000, 25),
    (1801, 3000, 5000, 7000, 20),
    (3001, 6000, 4000, 6000, 20),
    (6001, 10000, 3000, 5000, 15),
    (10001, 15000, 2500, 4000, 15),
    (15001, 30000, 2000, 3000, 15),
    (30001, 60000, 1500, 2000, 10),
)
"""(名次下限, 名次上限, 宝石, 行会币, 当期角色记忆碎片)"""
RANK_REWARD_LAST = (1000, 1000, 10)
"""60001 名及以后的奖励"""

DEFAULT_RANK_LINES = tuple(item[1] for item in RANK_REWARD_TABLE if item[1] <= 5000)
"""默认档位 = 5000 名以内各奖励段上边界（10/40/120/200/400/800/1800/3000）。
服务器排名总数通常到不了 5000 名以后，超出部分的页会返回空数据，故不作为默认档位。"""


def rank_reward(rank: int) -> dict:
    """按名次返回奖励 {gem: 宝石, coin: 行会币, shard: 记忆碎片}"""
    for lo, hi, gem, coin, shard in RANK_REWARD_TABLE:
        if lo <= rank <= hi:
            return {"gem": gem, "coin": coin, "shard": shard}
    return {"gem": RANK_REWARD_LAST[0], "coin": RANK_REWARD_LAST[1], "shard": RANK_REWARD_LAST[2]}


def rank_lines_pic(data: dict, qq: str) -> str:
    """QQ 查档线结果转图片输出（image_draw 画卡片图，emoji 用文字替代避免字体缺字形）"""

    def _fmt(num) -> str:
        return f"{num:,}" if num is not None else "未知"

    text = f"本届会战档线（编号{data['clan_battle_id']}）\n"
    text += "─" * 22 + "\n"
    for line in data["lines"]:
        if line is None:
            text += "该档位暂无数据\n\n"
            continue
        rw = line.get("reward") or {}
        text += f"【{line['rank']}名】{_fmt(line['damage'])}\n"
        text += f"　{line['clan_name']}（{line['member_num']}人/{line['leader_name']}）\n"
        if rw:
            text += (
                f"　奖励 宝石{rw.get('gem')} / 行会币{rw.get('coin')} / 碎片{rw.get('shard')}\n"
            )
    my = data["my"]
    text += "─" * 22 + f"\n我团：第{my['rank']}名  分数 {_fmt(my['damage'])}\n"
    # 与上一档线（排名比我好的最近档位）的差距
    better_lines = [
        line for line in data["lines"] if line and my["rank"] and line["rank"] < my["rank"]
    ]
    if better_lines and my["damage"] is not None:
        prev = max(better_lines, key=lambda x: x["rank"])
        diff = prev["damage"] - my["damage"]
        if diff <= 0:
            text += f"已超过{prev['rank']}名档线 {abs(diff):,} 分数\n"
        else:
            text += f"距{prev['rank']}名档线还差 {diff:,}（约 {diff // 100000000} 亿）\n"
    text += f"\n自定义档位：查档线 500 2000\nqq：{qq}"
    return image_draw(text)


rankline_disabled = False
"""档线接口不可用标记：请求失败（空响应/异常）时置 True，避免反复请求污染监控会话。
首次失败即永久禁用（进程内），并自动重登恢复监控会话。"""


async def _safe_period_ranking(clan_info, page: int):
    """带失败保护的档线接口调用：失败时禁用功能并重登恢复监控会话"""
    global rankline_disabled
    try:
        return await clan_info.client.clan_battle_period_ranking(
            clan_info.clan_id, clan_info.clan_battle_id, page
        )
    except Exception as e:
        rankline_disabled = True
        logger.error(f"档线接口调用失败，已禁用查档线功能保护监控会话: {e!r}")
        # 自愈：重新登录拿新会话（新 sid/request_id），让被污染的监控循环尽快恢复
        try:
            await clan_info.client.login()
            logger.info("档线接口失败后已自动重新登录，监控会话已恢复")
        except Exception as le:
            logger.error(f"档线接口失败后自动重登失败，建议重新开启出刀监控: {le!r}")
        raise ValueError(
            "档线查询失败，已自动关闭该功能并恢复监控会话。"
            "如监控仍异常，请重新开启出刀监控。"
        ) from e


async def query_rank_lines(clan_info, targets: List[int]) -> dict:
    """
    查询本届会战档线（clan_battle/period_ranking，游戏内会战排名列表同款接口）。

    :param clan_info: ClanBattle 监控对象（需已登录 client、clan_id 与 clan_battle_id）
    :param targets:   要查询的排名档位列表
    :return: {
        "clan_battle_id": int,
        "lines": [{rank, damage, clan_name, leader_name, leader_viewer_id, member_num}, ...]  # 按 targets 顺序，查不到的档位为 None
        "my": {rank, damage, clan_name}  # 我会当前排名与伤害（排名不在已取数据中时 damage 为 None）
    }
    :raises ValueError: 接口失败、会战已结算（空页）或档位非法
    """
    global rankline_disabled
    if rankline_disabled:
        raise ValueError("档线查询已被禁用：接口此前调用失败（详见日志），重启机器人可重试")
    if not clan_info or not clan_info.client:
        raise ValueError("出刀监控未开启，无法查询档线")
    if not clan_info.clan_battle_id:
        raise ValueError("未获取到本届会战编号，请稍后再试")
    targets = sorted({int(t) for t in targets})
    if not targets or targets[0] < 1 or targets[-1] > 5000:
        raise ValueError("排名档位需在 1~5000 之间")

    # 每页只有 10 条：按目标档位直接跳页取数（N 名 => page = (N-1)//10），无需顺序翻页。
    # 某页为空（超出服务器实际排名总数）只跳过该页，不影响其它档位。
    rank_map: Dict[int, ClanBattlePeriodRanking] = {}
    pages = sorted({(t - 1) // 10 for t in targets})
    for page in pages:
        res = await _safe_period_ranking(clan_info, page)
        for item in res.ranking_list or []:
            rank_map[item.rank] = item
    if not rank_map:
        raise ValueError("当前会战排名正在结算或暂无数据，请稍后再试")

    lines = []
    for t in targets:
        item = rank_map.get(t)
        lines.append(
            None
            if item is None
            else {
                "rank": item.rank,
                "damage": item.damage,
                "clan_name": item.clan_name,
                "leader_name": item.leader_name,
                "leader_viewer_id": item.leader_viewer_id,
                "member_num": item.member_num,
                "reward": rank_reward(t),
            }
        )
    my_item = rank_map.get(clan_info.rank)
    if my_item is None and clan_info.rank:
        # 目标档位页里没有我会条目：用 is_my_clan=1 单独取我会所在页，拿准确伤害算差线
        try:
            res_my = await clan_info.client.clan_battle_period_ranking(
                clan_info.clan_id, clan_info.clan_battle_id, 0, is_my_clan=1
            )
            for item in res_my.ranking_list or []:
                rank_map[item.rank] = item
            my_item = rank_map.get(clan_info.rank)
        except Exception as e:
            # 仅影响"我会差距"展示，不禁用档线功能
            logger.warning(f"查询我会排名数据失败（不影响档线展示）: {e!r}")
    my = {
        "rank": clan_info.rank,
        "damage": my_item.damage if my_item else None,
        "clan_name": clan_info.clan_name,
        "leader_name": my_item.leader_name if my_item else None,
        "leader_viewer_id": my_item.leader_viewer_id if my_item else None,
        "member_num": my_item.member_num if my_item else None,
    }
    return {
        "clan_battle_id": clan_info.clan_battle_id,
        "lines": lines,
        "my": my,
    }


async def get_cbreport(data: list, total_damage: int, total_score: int) -> str:
    reply = []
    for index, member in enumerate(data):
        name = member[1]
        knife = member[2]
        damage = member[3]
        score = member[4]
        rate_damage = f"{member[3]/total_damage*100:.2f}%"
        rate_score = f"{member[4]/total_score*100:.2f}%"
        reply.append(
            [
                str(index + 1),
                name,
                str(knife),
                str(damage),
                str(score),
                str(rate_damage),
                str(rate_score),
            ]
        )
    return grid2imgb64(
        reply, ["排名", "昵称", "出刀次数", "造成伤害", "分数", "伤害占比", "分数占比"]
    )


async def get_kpireport(data: list) -> str:
    return grid2imgb64(
        [
            [str(index + 1), member[1], str(member[0]), str(member[2]), str(member[3])]
            for index, member in enumerate(data)
        ],
        ["排名", "昵称", "游戏id", "等效出刀", "补正"],
    )


async def get_plyerreport(data: List[RecordDao]) -> str:
    reply = []
    knife = 0
    for dao in data:
        time_str = time.strftime("%Y/%m/%d-%H:%M:%S", time.localtime(dao.time))
        knife += 1 if dao.flag == 0 else 0.5
        item = daoflag2str(dao.flag)
        score = int(clan_boss_info.get_boss_rate(dao.lap, dao.boss) * dao.damage)
        reply.append(
            [
                time_str,
                str(knife),
                f"{dao.damage}",
                f"{dao.lap}周目{dao.boss}王",
                str(score),
                item,
                str(dao.battle_log_id),
            ]
        )
    return grid2imgb64(
        reply[::-1],
        ["日期", "出刀次数", "造成伤害", "BOSS", "得分", "类型", "出刀编号"],
    )


async def dao_detial(info: RecordDao) -> str:
    stage = clan_boss_info.lap2stage(info.lap)
    stage_num = stage_dict[stage]
    msg = f"{stage}面{stage_num}阶段，{info.lap}周目，{info.boss}王"
    if info.unit1:
        msg += f"\n{CHARA_NAME[info.unit1 // 100][0]} 星级:{info.unit1_rarity} RANK:{info.unit1_rank} 等级:{info.unit1_level} 专武:{info.unit1_unique_equip} 造成伤害:{info.unit1_damage}"
    if info.unit2:
        msg += f"\n{CHARA_NAME[info.unit2 // 100][0]} 星级:{info.unit2_rarity} RANK:{info.unit2_rank} 等级:{info.unit2_level} 专武:{info.unit2_unique_equip} 造成伤害:{info.unit2_damage}"
    if info.unit3:
        msg += f"\n{CHARA_NAME[info.unit3 // 100][0]} 星级:{info.unit3_rarity} RANK:{info.unit3_rank} 等级:{info.unit3_level} 专武:{info.unit3_unique_equip} 造成伤害:{info.unit3_damage}"
    if info.unit4:
        msg += f"\n{CHARA_NAME[info.unit4 // 100][0]} 星级:{info.unit4_rarity} RANK:{info.unit4_rank} 等级:{info.unit4_level} 专武:{info.unit4_unique_equip} 造成伤害:{info.unit4_damage}"
    if info.unit5:
        msg += f"\n{CHARA_NAME[info.unit5 // 100][0]} 星级:{info.unit5_rarity} RANK:{info.unit5_rank} 等级:{info.unit5_level} 专武:{info.unit5_unique_equip} 造成伤害:{info.unit5_damage}"

    predict_work = await units2workid(
        [info.unit1, info.unit2, info.unit3, info.unit4, info.unit5],
        stage_num,
        info.boss,
    )
    msg += "\n可能作业：" + (str(predict_work) if predict_work else "未收录轴")
    return msg
