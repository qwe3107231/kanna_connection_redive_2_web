import asyncio
import json
import time
from typing import Dict, List, Union

from hoshino.modules.priconne._pcr_data import CHARA_NAME
from loguru import logger

from ...convert2img.convert2img import grid2imgb64
from ..basedata import FilePath, stage_dict
from ..client.common import InventoryInfo
from ..client.response import ClanBattlePeriodRanking
from ..database.dal import pcr_sqla
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
RANK_REWARD_TABLE = (
    (1, 3, 20000, 5000, 30),
    (4, 10, 15000, 5000, 30),
    (11, 20, 12000, 5000, 30),
    (21, 50, 10000, 5000, 30),
    (51, 200, 8000, 5000, 30),
    (201, 600, 6000, 4500, 25),
    (601, 1200, 4000, 4000, 25),
    (1201, 2800, 3500, 3500, 20),
    (2801, 5000, 3000, 3000, 20),
    (5001, 10000, 2500, 2500, 15),
    (10001, 15000, 2000, 2000, 15),
    (15001, 25000, 1500, 1500, 15),
    (25001, 40000, 1000, 1000, 10),
    (40001, 60000, 750, 750, 10),
)
"""(名次下限, 名次上限, 宝石, 行会币, 绫音（探索者）的记忆碎片)"""
RANK_REWARD_LAST = (500, 500, 10)
"""60001 名及以后的奖励"""

DEFAULT_RANK_LINES = tuple(item[1] for item in RANK_REWARD_TABLE)
"""默认档位 = 各奖励段上边界全量。超出服务器实际排名总数的档位返回空数据，
前端显示"无"而非跳过。"""


def rank_reward(rank: int) -> dict:
    """按名次返回奖励 {gem: 宝石, coin: 行会币, shard: 记忆碎片}"""
    for lo, hi, gem, coin, shard in RANK_REWARD_TABLE:
        if lo <= rank <= hi:
            return {"gem": gem, "coin": coin, "shard": shard}
    return {"gem": RANK_REWARD_LAST[0], "coin": RANK_REWARD_LAST[1], "shard": RANK_REWARD_LAST[2]}


def rank_lines_pic(data: dict, qq: str, updated_at: int = 0) -> str:
    """QQ 查档线结果转图片输出（image_draw 画卡片图，emoji 用文字替代避免字体缺字形）

    updated_at 是这份数据的抓取时间。档线有本地缓存（同一刷新槽位内不重复抓取），
    不把时间标出来就看不出来看到的是不是上一轮的数据。
    """

    def _fmt(num) -> str:
        return f"{num:,}" if num is not None else "未知"

    def _fmt_time(ts: int) -> str:
        return time.strftime("%m-%d %H:%M", time.localtime(int(ts)))

    text = f"本届会战档线（编号{data['clan_battle_id']}）\n"
    if updated_at:
        text += f"数据时间 {_fmt_time(updated_at)}\n"
    text += "─" * 22 + "\n"
    for line in data["lines"]:
        if line is None:
            text += "无\n\n"
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
"""档线接口不可用标记：**连续失败到上限**后置 True，避免反复请求污染监控会话。
到上限时会重登一次恢复监控会话；置位后要重启机器人才能再试（进程内）。"""

RANK_LINE_RETRY_WAIT = 10
"""档线接口失败后的重试间隔（秒）。"""

RANK_LINE_MAX_FAILS = 5
"""连续失败多少次才禁用查档线。

原来是「一次失败即永久禁用」，太脆（2026-09-24 真实事故）：自动刷新撞上游戏侧
一次 502，查档线就被禁用一整天、只能重启。现在改成失败后等 `RANK_LINE_RETRY_WAIT`
秒重试，**连续 5 次都失败**才禁用；成功一次就把计数清零。"""

rankline_fail_count = 0
"""连续失败次数（成功一次即清零）。"""

RANK_LINE_REFRESH_INTERVAL = 30 * 60
"""游戏侧档线刷新周期（秒）：会战期间每个整点与 30 分各刷新一次。"""

RANK_LINE_REFRESH_GRACE = 60
"""刷新后留给服务器落库 / 传播的余量（秒）。

槽位边界因此落在 :01 / :31，与前端 `Dashboard.vue` 的定时刷新同一时刻 —— 两边必须
一起改：前端提前刷新，后端会把刚抓到的新数据判成「上一槽位」而立刻重抓；前端推后
刷新，后端又会认为旧数据还在有效期内。"""


def rank_line_slot(ts: int) -> int:
    """返回 ts 时刻所属的档线刷新槽位起点。

    两个时刻的槽位相同 ⇔ 它们看到的是游戏侧同一批档线数据。缓存是否可用就用这个
    判断，而**不是**「距写入不超过 N 分钟」：

    滚动 TTL 有个漏洞 —— 只要上次抓取落在槽位中途，下一次定时刷新就会被缓存吃掉。
    例如 :29 打开页面抓了一次（拿到的是 :00 那批），:31 的定时刷新距写入才 2 分钟、
    在 TTL 内直接命中缓存，可游戏侧 :30 已经刷新过了，用户会一直看到 :00 的数据直到
    缓存过期。实测滚动 25 分钟 TTL 有约 16% 的时间在端上一轮的旧数据，且每次都恰好
    发生在 :01 / :31 这两个刷新点上。
    """
    return (
        (ts - RANK_LINE_REFRESH_GRACE) // RANK_LINE_REFRESH_INTERVAL
    ) * RANK_LINE_REFRESH_INTERVAL


async def _safe_period_ranking(clan_info, page: int):
    """带失败保护的档线接口调用。

    失败后等 `RANK_LINE_RETRY_WAIT` 秒重试，**连续 `RANK_LINE_MAX_FAILS` 次**都失败才
    禁用功能并重登恢复监控会话 —— 一次 502 之类的瞬时故障不该让查档线废掉一整天。

    注意重试是「连续」计数：中间成功过一次就清零，所以偶发抖动只会多等 10 秒。
    """
    global rankline_disabled, rankline_fail_count
    while True:
        try:
            res = await clan_info.client.clan_battle_period_ranking(
                clan_info.clan_id, clan_info.clan_battle_id, page
            )
        except Exception as e:
            rankline_fail_count += 1
            if rankline_fail_count >= RANK_LINE_MAX_FAILS:
                rankline_disabled = True
                logger.error(
                    f"档线接口连续 {rankline_fail_count} 次失败，"
                    f"已禁用查档线功能保护监控会话: {e!r}"
                )
                # 自愈：重新登录拿新会话（新 sid/request_id），让被污染的监控循环尽快恢复
                try:
                    await clan_info.client.login()
                    logger.info("档线接口失败后已自动重新登录，监控会话已恢复")
                except Exception as le:
                    logger.error(f"档线接口失败后自动重登失败，建议重新开启出刀监控: {le!r}")
                raise ValueError(
                    f"档线查询连续 {rankline_fail_count} 次失败，已自动关闭该功能并恢复监控会话。"
                    "如监控仍异常，请重新开启出刀监控。"
                ) from e
            logger.warning(
                f"档线接口第 {rankline_fail_count} 次连续失败，"
                f"{RANK_LINE_RETRY_WAIT} 秒后重试: {e!r}"
            )
            await asyncio.sleep(RANK_LINE_RETRY_WAIT)
            continue
        rankline_fail_count = 0
        return res


def is_monitor_running(clan_info) -> bool:
    """出刀监控是否**真的在跑**。

    判断依据是 `loop_check`（监控循环时间戳），**不能**看 `client`：

    - `client` 一旦登录就再也不会被清空 —— 发【取消出刀监控】只是把 `loop_num` +1，
      让监控循环自己抛 `CancelledError` 退出（`model.ClanbattleHandle.__aexit__`），
      但 `ClanBattle` 对象仍留在 `clanbattle_info` 里、`client` 也还在。只看 `client`
      会把「已经停掉的监控」当成「运行中」。
    - `loop_check` 在每次进入监控循环时置为当前时间，在循环被取消 / 被顶号 /
      连续报错超限时清 0，正好等价于【状态】指令里那个「监控状态：开启 / 关闭」。

    这个判断很关键：档线接口失败时 `_safe_period_ranking` 会 `client.login()` 重登一次，
    如果监控其实没在跑、账号正被群友自己登录着，这一下就会把人**顶下线**。
    """
    return bool(clan_info and getattr(clan_info, "loop_check", 0))


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
    if not is_monitor_running(clan_info):
        raise ValueError("出刀监控未开启，无法查询档线")
    if not clan_info.clan_battle_id:
        raise ValueError("未获取到本届会战编号，请稍后再试")
    targets = sorted({int(t) for t in targets})
    if not targets or targets[0] < 1 or targets[-1] > 60000:
        raise ValueError("排名档位需在 1~60000 之间")

    # 每页只有 10 条：按目标档位直接跳页取数（N 名 => page = (N-1)//10），无需顺序翻页。
    # 某页为空（超出服务器实际排名总数）只跳过该页，不影响其它档位。
    rank_map: Dict[int, ClanBattlePeriodRanking] = {}
    page_has_data: Dict[int, bool] = {}  # 记录每页是否有数据，供后续二分搜索最后一名
    pages = sorted({(t - 1) // 10 for t in targets})
    for page in pages:
        res = await _safe_period_ranking(clan_info, page)
        has = bool(res.ranking_list)
        page_has_data[page] = has
        for item in res.ranking_list or []:
            rank_map[item.rank] = item
    if not rank_map:
        raise ValueError("当前会战排名正在结算或暂无数据，请稍后再试")

    # 找出服务器实际最后一名公会的排名：在已请求页之间做二分搜索，
    # 定位"最后一个有数据的页"，再取该页最高 rank 即为最后一名公会排名。
    highest_page_fetched = max(pages)
    max_page_with_data = max((p for p, v in page_has_data.items() if v), default=-1)
    if 0 <= max_page_with_data < highest_page_fetched:
        lo, hi = max_page_with_data + 1, highest_page_fetched
        while lo <= hi:
            mid = (lo + hi) // 2
            res = await _safe_period_ranking(clan_info, mid)
            if res.ranking_list:
                page_has_data[mid] = True
                lo = mid + 1
            else:
                page_has_data[mid] = False
                hi = mid - 1
        # hi 此时指向最后一个有数据的页
        if hi >= 0 and page_has_data.get(hi):
            res = await _safe_period_ranking(clan_info, hi)
            for item in res.ranking_list or []:
                rank_map[item.rank] = item

    # 从 rank_map 里找出实际最后一名公会排名，加入档位列表
    last_rank = max(rank_map.keys())
    if last_rank not in targets:
        targets.append(last_rank)
        targets.sort()
        # 重新构建空档位奖励信息（因为 targets 变了）
        # 但 rank_map 里已经有 last_rank 的数据了，所以下面的 lines 构建会自然包含它

    lines = []
    for t in targets:
        item = rank_map.get(t)
        reward = rank_reward(t)
        if item is None:
            # 空档位：仍返回完整结构（带档位奖励），前端显示"无"
            lines.append({
                "rank": t,
                "damage": None,
                "clan_name": None,
                "leader_name": None,
                "leader_viewer_id": None,
                "member_num": None,
                "reward": reward,
            })
        else:
            lines.append({
                "rank": item.rank,
                "damage": item.damage,
                "clan_name": item.clan_name,
                "leader_name": item.leader_name,
                "leader_viewer_id": item.leader_viewer_id,
                "member_num": item.member_num,
                "reward": reward,
            })
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


async def get_rank_lines_cached(
    clan_info, targets: List[int], force: bool = False
) -> dict:
    """带本地缓存的档线查询（网页端接口和 QQ 指令共用这一条路）。

    为什么要缓存：档线是全服排名数据，游戏侧每半小时才更新一次，可抓一次要打十几次
    period_ranking 分页请求（默认 14 个档位 = 13 个分页，外加「末位二分搜索」十来次），
    而且档线接口连续失败到上限会把该功能禁用、还要重登一次来救监控会话。所以结果按
    「群 + 届 + 档位组合」落本地库，**同一刷新槽位内**直接读缓存。

    「同一槽位」用 `rank_line_slot()` 判，不是滚动 TTL：只要上次抓取落在槽位中途，
    TTL 就会把下一次定时刷新吃掉、让用户整轮看不到新数据（详见 `rank_line_slot`）。

    :param clan_info: ClanBattle 监控对象（需已登录 client）
    :param targets:   要查询的排名档位列表
    :param force:     True = 忽略缓存强制抓一次
    :return: {
        "data": query_rank_lines 的返回值,
        "cached": bool,      # True = 本次没去抓游戏接口
        "stale": bool,       # True = 抓取失败，退回来用的是旧缓存
        "updated_at": int,   # 这份数据的抓取时间（Unix 秒）
    }
    :raises ValueError: 档位非法 / 接口失败 / 功能被禁用；此时若一张缓存都没有则原样抛出
    """
    targets = sorted({int(t) for t in targets})
    ranks_key = ",".join(str(t) for t in targets)
    group_id = int(clan_info.group_id)
    clan_battle_id = int(clan_info.clan_battle_id or 0)

    # 拿得到本届编号才查缓存；编号为空说明监控还没初始化完，直接去抓（那边会报错）
    cached = None
    if clan_battle_id:
        cached = await pcr_sqla.get_rank_line_cache(group_id, clan_battle_id, ranks_key)

    # now 在抓取**之前**取，返回值里的 updated_at 用的也是它：游戏返回的是「发起抓取
    # 那一刻」所属槽位的数据，而抓一次要十几秒（十几个分页 + 末位二分搜索），拿结束
    # 时刻打戳会把 :30:55 发起的、实为上一槽位的抓取记成新槽位，下一轮就会误判成
    # 新鲜的而端出去。取早不取晚 —— 宁可多抓一次，也不端旧数据。
    now = int(time.time())
    # 缓存写入时刻与「现在」属于同一刷新槽位 = 手里这份就是游戏侧最新的一批数据。
    # 落在别的槽位（哪怕只早了几分钟）就说明游戏侧已经刷新过，必须重抓。
    if (
        cached is not None
        and not force
        and rank_line_slot(now) == rank_line_slot(int(cached.updated_at))
    ):
        return {
            "data": json.loads(cached.payload),
            "cached": True,
            "stale": False,
            "updated_at": int(cached.updated_at),
        }

    try:
        data = await query_rank_lines(clan_info, targets)
    except Exception:
        # 抓不到就退回旧数据（调用方从 stale 能看出来）；一张缓存都没有才原样抛
        if cached is not None:
            return {
                "data": json.loads(cached.payload),
                "cached": True,
                "stale": True,
                "updated_at": int(cached.updated_at),
            }
        raise

    try:
        await pcr_sqla.set_rank_line_cache(
            group_id,
            data["clan_battle_id"],
            ranks_key,
            json.dumps(data, ensure_ascii=False),
        )
    except Exception as e:
        # 写缓存失败不影响本次结果，只是下次还得再抓一遍
        logger.warning(f"档线缓存写入失败 group={group_id}: {e!r}")
    # updated_at 用抓取前取的 now（见上方注释）：槽位判断靠它，宁可偏早。
    return {"data": data, "cached": False, "stale": False, "updated_at": now}


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
