import asyncio
import math
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Union

from hoshino.modules.priconne import chara
from hoshino.util import pic2b64
from loguru import logger
from nonebot import MessageSegment
from PIL import Image

from ..client import BaseClient
from ..client.common import UnitDataForView
from ..client.request import ArenaRankingRequest, GrandArenaRankingRequest
from ..database.dal import pcr_sqla
from ..database.models import ArenaSetting, GrandDefenceCache
from ..basedata import Platform
from ..errorclass import CancelledError
from ..login import check_client, run_group
from ..util.task_pool import PoolBase, PrioritizedQueryItemBase
from ..util.tools import anywhere_send
from .get_img import render_atk_def_teams, generate_player_rank

from .base import id_str2list
from .query_jjc import do_query, generate_collision_free_team

name_cache = {}

# 「胜利次数」可能的字段名：公主竞技场用 winning_number；普通场游戏不一定返回，
# 返回了就显示、没返回显示「不适用」。多列几个别名，接口改名也能认出来。
_WIN_NUM_KEYS = (
    "winning_number",
    "win_num",
    "win_count",
    "winning_count",
    "win_times",
)


def pick_win_num(entry: dict):
    """从 ranking 原始条目里取「胜利次数」，取不到返回 None。"""
    if not isinstance(entry, dict):
        return None
    for key in _WIN_NUM_KEYS:
        value = entry.get(key)
        if value is not None:
            return value
    return None


class Arena:
    def __init__(self, user_id: int) -> None:
        self.loop_num = 0
        self.error_count = 0
        self.loop_check = 0
        self.jjc_rank = 0
        self.grand_rank = 0
        self.jjc_group = 0
        self.grand_group = 0
        self.latest_cache_time = 0
        self.user_id = user_id

    async def init(self, client: BaseClient, group_id: int, bot_id: int, platform: int):
        self.loop_num += 1
        self.battle_record = []
        self.client = client
        self.platform = platform
        self.group_id = group_id
        self.bot_id = bot_id
        await pcr_sqla.init_jjc_setting(ArenaSetting(user_id=self.user_id))
        self.setting = await pcr_sqla.get_jjc_setting(self.user_id)
        await self.refresh_jjc_info()
        await self.refresh_jjc_info(True)

    async def refresh_jjc_info(self, grand=False):
        if grand:
            grand_info = await self.client.grand_arena_info()
            self.grand_rank = grand_info.grand_arena_info.rank
            self.grand_group = grand_info.grand_arena_info.group
        else:
            jjc_info = await self.client.arena_info()
            self.jjc_rank = jjc_info.arena_info.rank
            self.jjc_group = jjc_info.arena_info.group

    async def refresh_cache(self):
        if self.grand_rank >= 200:
            return

        battle_history = await self.client.grand_arena_history()
        if not battle_history.grand_arena_history_list:
            return

        self.latest_cache_time = await pcr_sqla.cache_latest_time(self.user_id)
        temp_list: List[GrandDefenceCache] = []

        for history in battle_history.grand_arena_history_list:
            if self.latest_cache_time >= history.versus_time:
                break
            if history.is_challenge:
                history_detial = await self.client.grand_arena_history_detial(
                    history.log_id
                )
                arena_desk = (
                    history_detial.grand_arena_history_detail.vs_user_grand_arena_deck
                )
                for i, defence_data in enumerate(
                    [arena_desk.first, arena_desk.second, arena_desk.third], 1
                ):
                    if not (
                        defence := self.general_defence_cache(
                            defence_data,
                            history.opponent_user.viewer_id,
                            history.versus_time,
                            i,
                        )
                    ):
                        break
                    temp_list.append(defence)
        self.latest_cache_time = battle_history.grand_arena_history_list[0].versus_time
        await pcr_sqla.add_grand_cache(temp_list)

    def general_defence_cache(
        self,
        defence_data: List[UnitDataForView],
        viewer_id: int,
        versus_time: int,
        rank: int,
    ) -> Union[GrandDefenceCache, None]:
        if not defence_data:
            return None
        return GrandDefenceCache(
            pcrid=viewer_id,
            grand_id=self.grand_group,
            defence=int(
                "".join([str(Arena.format_id(unit.id)) for unit in defence_data])
            ),
            row=rank,
            vs_time=versus_time,
            user_id=self.user_id,
        )

    async def jjc_query_id(self, rank: int, is_grand: bool = False) -> int:
        page = math.ceil(rank / 20)
        rank_list = (
            await self.client.grand_rank(page)
            if is_grand
            else await self.client.arena_rank(page)
        )
        return f"位于排名{rank}的玩家\n{await self.get_player_info(rank_list.ranking[rank - (page - 1) * 20 - 1].viewer_id)}"

    async def get_player_info(self, pcr_id: int):
        player = await self.client.profile_get(pcr_id)
        return f"{await chara.fromid(Arena.format_id(player.favorite_unit.id), player.favorite_unit.unit_rarity).get_icon_cqcode()}\n玩家姓名：{player.user_info.user_name}\nUID：{pcr_id}\n竞技场排名：{player.user_info.arena_rank}({player.user_info.arena_group})/{player.user_info.grand_arena_rank}({player.user_info.grand_arena_group})\n"

    @staticmethod
    def _quest_last(quest, attr: str) -> int:
        """关卡进度取列表最后一项（-1 = 未通关，原样返回）。"""
        try:
            value = getattr(quest, attr, None)
        except Exception:
            return 0
        if isinstance(value, (list, tuple)):
            return int(value[-1]) if value else 0
        try:
            return int(value or 0)
        except Exception:
            return 0

    async def get_profile_data(self, viewer_id: int) -> dict:
        """按游戏 ID 查玩家资料（网页端「查 ID」用）。

        数据源与 autopcr 的【查玩家资料】一致：`profile/get_profile` +
        `target_viewer_id`。返回结构化 dict，前端自己画，不再局限「竞技场排名」。
        """
        profile = await self.client.profile_get(viewer_id)
        user = profile.user_info
        if user is None:
            raise ValueError(f"没有查到这个玩家（ID {viewer_id}）")
        quest = profile.quest_info
        fav = profile.favorite_unit

        def talent(index: int) -> int:
            try:
                return int(quest.talent_quest[index].clear_count or 0)
            except Exception:
                return 0

        return {
            "viewer_id": int(user.viewer_id or viewer_id),
            "name": user.user_name or "",
            "comment": user.user_comment or "",
            # 头像用玩家的代表角色
            "unit_id": Arena.format_id(fav.id) if fav else 1000,
            "rarity": (int(getattr(fav, "unit_rarity", 0) or 0)) if fav else 0,
            "battle_rarity": (int(getattr(fav, "battle_rarity", 0) or 0)) if fav else 0,
            "team_level": int(user.team_level or 0),
            "total_power": int(user.total_power or 0),
            "unit_num": int(user.unit_num or 0),
            "open_story_num": int(user.open_story_num or 0),
            "friend_num": int(user.friend_num or 0),
            "arena_rank": int(user.arena_rank or 0),
            "arena_group": int(user.arena_group or 0),
            "grand_arena_rank": int(user.grand_arena_rank or 0),
            "grand_arena_group": int(user.grand_arena_group or 0),
            "tower_cleared_floor_num": int(user.tower_cleared_floor_num or 0),
            "tower_cleared_ex_quest_count": int(
                user.tower_cleared_ex_quest_count or 0
            ),
            "last_login_time": int(getattr(user, "last_login_time", 0) or 0),
            "clan_name": profile.clan_name or "",
            "quest_normal": self._quest_last(quest, "normal_quest"),
            "quest_hard": self._quest_last(quest, "hard_quest"),
            "quest_very_hard": self._quest_last(quest, "very_hard_quest"),
            "quest_byway": self._quest_last(quest, "byway_quest"),
            # 深域 5 属性（火/水/风/光/暗）的 clear_count
            "talent": [talent(i) for i in range(5)],
        }

    async def jjc_query(self, rank: int) -> Image.Image:
        page = math.ceil(rank / 20)
        rank_list = await self.client.arena_rank(page)
        defence = rank_list.ranking[rank - (page - 1) * 20 - 1].arena_deck
        result = await do_query(
            [unit.id for unit in defence],
            1 if self.platform == Platform.b_id.value else 3,
        )
        return await render_atk_def_teams(
            result,
            [[unit.id // 100 for unit in defence]],
            rank_list.ranking[rank - (page - 1) * 20 - 1].user_name,
            rank_list.ranking[rank - (page - 1) * 20 - 1].rank,
        )

    async def grand_query(self, rank: int) -> List[Image.Image]:
        page = math.ceil(rank / 20)
        rank_list = await self.client.grand_rank(page)
        defence = rank_list.ranking[rank - (page - 1) * 20 - 1].grand_arena_deck
        team_list = await self.get_defence(
            rank_list.ranking[rank - (page - 1) * 20 - 1].viewer_id,
            rank,
            [defence.first, defence.second, defence.third],
        )
        # QQ 端出图只需要角色 id（render_atk_def_teams 吃 4 位 id 列表）
        team_list = [[unit["unit_id"] for unit in team] for team in team_list]
        team_list = [team[5:] if len(team) > 5 else team for team in team_list]
        return await self.get_3defences_solution(
            team_list,
            rank_list.ranking[rank - (page - 1) * 20 - 1].user_name,
            rank_list.ranking[rank - (page - 1) * 20 - 1].rank,
        )

    async def build_3defences_solution(self, team_list: List[List[int]]):
        """公主场：为最多 3 支防守队伍各查一组解，并挑出「互不抢角色」的组合。

        返回 `generate_collision_free_team` 的原始结果（未渲染）。出图与网页绘制
        共用这一段取数逻辑，只是后面一个交给 PIL、一个交给前端。
        """
        all_query_records = [
            [[None, -100, "placeholder"]] for _ in range(len(team_list))
        ]
        for query_index, team in enumerate(team_list):
            records = await do_query(
                [unit_id * 100 + 1 for unit_id in team],
                1 if self.platform == Platform.b_id.value else 3,
            )

            if not records:
                continue

            if records == ["lossunit"]:
                all_query_records[query_index].append([None, 100, "lossunit"])
                continue

            for record in records:
                record_team = tuple(chara_obj.id for chara_obj in record["atk"])
                all_query_records[query_index].append(
                    [record_team, record["val"], record]
                )
        return await generate_collision_free_team(all_query_records)

    async def get_3defences_solution(
        self, team_list: List[List[int]], user_name: str, rank: int
    ):
        result = await self.build_3defences_solution(team_list)
        while len(team_list) < 3:
            team_list.append([1000, 1000, 1000, 1000, 1000])
        return await render_atk_def_teams(result, team_list, user_name, rank)

    @staticmethod
    def _unit_ref(unit: UnitDataForView) -> dict:
        """防守队伍里的一个角色 → {unit_id, rarity, battle_rarity}（4 位 id + 星级）。"""
        return {
            "unit_id": Arena.format_id(unit.id),
            "rarity": int(getattr(unit, "unit_rarity", 0) or 0),
            "battle_rarity": int(getattr(unit, "battle_rarity", 0) or 0),
        }

    async def get_defence(
        self, pcr_id: int, rank: int, defences: List[List[UnitDataForView]]
    ) -> List[List[dict]]:
        if rank <= 50:
            i = 0
        elif rank <= 200:
            i = 1
        elif rank <= 500:
            i = 2
        else:
            i = 3
        defences = [
            [self._unit_ref(unit) for unit in defence] for defence in defences[:i]
        ]

        for rank in range(i + 1, 3 + 1):
            if not (team := await pcr_sqla.query_grand_cache(pcr_id, rank)):
                break
            # 缓存里只存了角色 id，没有星级数据 —— rarity 给 0，前端就不画星
            defences.append(
                [
                    {"unit_id": unit_id, "rarity": 0, "battle_rarity": 0}
                    for unit_id in id_str2list(str(team))
                ]
            )

        return defences

    async def _query_rank_page(self, page: int, is_grand: bool = False) -> List[dict]:
        """排行榜某一「展示页」（每页 10 名）的**原始条目**（dict）。

        游戏接口每页返回 20 条，展示端每页 10 条 —— API 页码 = ceil(page/2)，
        再按 page 的奇偶取前半 / 后半。普通场与公主场只是接口不同，切法一致。

        这里刻意不经过 response 模型：模型会把「未声明的字段」直接丢掉，
        而竞技场排行榜里各场次返回的字段并不完全一样（例如胜利次数只有部分
        场次有）。用原始 dict 才能在字段改名时兜底。原来普通竞技场那支还漏了
        await（拿到协程，一取 .ranking 就 AttributeError），一并修正。
        """
        api_page = math.ceil(page / 2)
        raw = await self.client.callapi(
            GrandArenaRankingRequest(page=api_page)
            if is_grand
            else ArenaRankingRequest(page=api_page)
        )
        entries = raw.get("ranking") or []
        return entries[(1 - page % 2) * 10 : (2 - page % 2) * 10]

    async def jjc_query_page(
        self, page: int, is_grand: bool = False
    ) -> List[Image.Image]:
        rank_list = await self._query_rank_page(page, is_grand)
        players = [
            await self.client.profile_get(entry.get("viewer_id")) for entry in rank_list
        ]
        return [
            await generate_player_rank(
                player.user_info.user_name,
                Arena.format_id(player.favorite_unit.id),
                rank_list[i].get("rank"),
                player.user_info.viewer_id,
                pick_win_num(rank_list[i]),
            )
            for i, player in enumerate(players)
            if player.favorite_unit
        ]

    async def get_rank_rows(self, page: int, is_grand: bool = False) -> List[dict]:
        """排行榜结构化数据（网页端绘制用；QQ 端仍走 jjc_query_page 出图）。

        每行：rank / name / viewer_id / unit_id（4 位头像 id）/ rarity / win_num。
        昵称与 UID 取 profile（与 QQ 出图口径一致）；胜利次数取 ranking 条目，
        取不到就是 None（前端显示「不适用」）。
        """
        rank_list = await self._query_rank_page(page, is_grand)
        rows = []
        for entry in rank_list:
            profile = await self.client.profile_get(entry.get("viewer_id"))
            fav = profile.favorite_unit
            rows.append(
                {
                    "rank": entry.get("rank"),
                    "name": profile.user_info.user_name,
                    "viewer_id": entry.get("viewer_id"),
                    "unit_id": Arena.format_id(fav.id) if fav else 1000,
                    "rarity": (getattr(fav, "unit_rarity", 0) or 0) if fav else 0,
                    "win_num": pick_win_num(entry),
                }
            )
        return rows

    async def jjc_query_simple(
        self, page: int, is_grand: bool = False
    ) -> List[Image.Image]:
        rank_list = (
            await self.client.grand_rank(page)
            if is_grand
            else await self.client.arena_rank(page)
        ).ranking
        return [
            f"{rank_list[i].rank}：{result.user_info.user_name}（{result.user_info.viewer_id}）"
            for i, player in enumerate(rank_list)
            if (result := await self.get_profile_by_cache(player.viewer_id))
        ]

    async def get_profile_by_cache(self, viewer_id: int):
        now = time.time()
        if viewer_id in name_cache:
            if now - name_cache[viewer_id][1] < 3600:
                return name_cache[viewer_id][0]
            del name_cache[viewer_id]
        if result := await self.client.profile_get(viewer_id):
            name_cache[result.user_info.viewer_id] = result, now
        return result

    @staticmethod
    def _norm_solution(entry) -> Optional[dict]:
        """把 do_query / collision_free 的一条结果规整成网页端能画的结构。

        原始条目可能是：
          - []（占位空行，丢弃）
          - "lossunit" / "placeholder"（固定占位文案）
          - dict：{"atk": [chara...], "up", "down", "comment", "team_type"}
        `units` 是 [{unit_id, rarity, battle_rarity}, ...]，前端拿去拼头像接口。
        """
        if entry == []:
            return None
        if entry == "lossunit":
            return {
                "units": [],
                "up": 0,
                "down": 0,
                "comment": "",
                "label": "不足四人随便打",
                "team_type": "lossunit",
            }
        if entry == "placeholder":
            return {
                "units": [],
                "up": 0,
                "down": 0,
                "comment": "",
                "label": "",
                "team_type": "placeholder",
            }

        team_type = entry.get("team_type", "normal")
        if team_type.startswith("approximation"):
            label = "近似解"
        elif team_type == "frequency":
            label = "高频解"
        elif team_type == "any":
            label = "不足四人随便打"
        elif team_type == "normal":
            label = ""
        else:
            label = str(team_type)

        comment = ""
        try:
            first = entry["comment"][0]
            comment = f"{first.get('nickname', '')}:{first.get('msg', '')}".strip(":")
        except Exception:
            comment = ""

        return {
            "units": [
                {
                    "unit_id": c.id,
                    "rarity": int(getattr(c, "star", 0) or 0),
                    "battle_rarity": 0,
                }
                for c in entry.get("atk", [])
            ],
            "up": int(entry.get("up", 0) or 0),
            "down": int(entry.get("down", 0) or 0),
            "comment": comment,
            "label": label,
            "team_type": team_type,
        }

    async def get_defence_data(self, rank: int, is_grand: bool = False) -> dict:
        """查防守结构化数据（网页端绘制用；QQ 端仍走 jjc_query / grand_query 出图）。

        返回：
          {
            "rank": 名次, "name": 玩家昵称,
            "defence": [[{unit_id, rarity, battle_rarity}, ...], ...],  # 防守队伍
            "solutions": [ {units, up, down, comment, label, team_type}, ... ],
          }
        取数逻辑与出图版本完全一致，只是最后不渲染成图片。
        """
        page = math.ceil(rank / 20)
        idx = rank - (page - 1) * 20 - 1
        region = 1 if self.platform == Platform.b_id.value else 3

        if is_grand:
            entry = (await self.client.grand_rank(page)).ranking[idx]
            deck = entry.grand_arena_deck
            team_list = await self.get_defence(
                entry.viewer_id, rank, [deck.first, deck.second, deck.third]
            )
            # 与 grand_query 一致：超过 5 个的截断（缓存里可能带多余位置）
            team_list = [team[5:] if len(team) > 5 else team for team in team_list]
            # 作业按角色 id 查（build_3defences_solution 吃 4 位 id）
            raw = await self.build_3defences_solution(
                [[unit["unit_id"] for unit in team] for team in team_list]
            )
            while len(team_list) < 3:
                team_list.append(
                    [{"unit_id": 1000, "rarity": 0, "battle_rarity": 0} for _ in range(5)]
                )
            defence = team_list
            name = entry.user_name
        else:
            entry = (await self.client.arena_rank(page)).ranking[idx]
            deck = entry.arena_deck or []
            defence = [[self._unit_ref(unit) for unit in deck]]
            raw = await do_query([unit.id for unit in deck], region)
            name = entry.user_name

        solutions = []
        for item in raw if isinstance(raw, list) else [raw]:
            norm = self._norm_solution(item)
            if norm is not None:
                solutions.append(norm)

        return {"rank": rank, "name": name, "defence": defence, "solutions": solutions}

    @staticmethod
    def format_id(unit_id: int) -> int:
        return unit_id // 100 if unit_id > 100000 else 1000


@dataclass
class ArenaItem:
    arena_info: Arena
    loop_num: int


class PrioritizedQueryItem(PrioritizedQueryItemBase):
    data: ArenaItem


class ArenaPool(PoolBase):
    async def do_single(self, item: PrioritizedQueryItem):
        arena: Arena = item.data.arena_info
        loop_num: int = item.data.loop_num
        async with ArenaHandle(arena, loop_num):
            if loop_num != arena.loop_num:
                raise CancelledError
            arena.loop_check = time.time()
            if arena.setting.jjc_notice:
                arena_info = await arena.client.arena_info()
                if arena.jjc_rank < arena_info.arena_info.rank:
                    await anywhere_send(
                        f"jjc: {arena.jjc_rank}->{arena_info.arena_info.rank} [▽{arena_info.arena_info.rank - arena.jjc_rank}][CQ:at,qq={arena.user_id}]",
                        arena.group_id,
                        arena.bot_id,
                    )
                    arena.jjc_rank = arena_info.arena_info.rank
                    """teams = await arena.jjc_query(arena.jjc_rank)
                    await anywhere_send(
                        MessageSegment.image(pic2b64(teams)),
                        arena.group_id,
                        arena.bot_id,
                    )
                    """
            if arena.setting.grand_notice:
                await arena.refresh_cache()
                grand_info = await arena.client.grand_arena_info()
                if arena.grand_rank < grand_info.grand_arena_info.rank:
                    await anywhere_send(
                        f"pjjc: {arena.grand_rank}->{grand_info.grand_arena_info.rank} [▽{grand_info.grand_arena_info.rank - arena.grand_rank}][CQ:at,qq={arena.user_id}]",
                        arena.group_id,
                        arena.bot_id,
                    )
                    arena.grand_rank = grand_info.grand_arena_info.rank
                    """teams = await arena.grand_query(arena.grand_rank)
                    await anywhere_send(
                        MessageSegment.image(pic2b64(teams)),
                        arena.group_id,
                        arena.bot_id,
                    )"""

            arena.error_count = 0
        asyncio.create_task(
            self.add_task(
                PrioritizedQueryItem(data=ArenaItem(arena, loop_num)),
                int(time.time() - arena.loop_check),
                True,
                f"竞技场{str(arena.user_id)}",
            )
        )


class ArenaHandle:
    def __init__(self, arena_info: Arena, loop_num: int) -> None:
        self.arena_info = arena_info
        self.loop_num = loop_num

    async def __aenter__(self):
        run_group[self.arena_info.group_id] = self.arena_info.bot_id
        self.arena_info.loop_check = time.time()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            return

        self.arena_info.loop_check = 0
        if self.arena_info.group_id in run_group:
            del run_group[self.arena_info.group_id]

        if self.loop_num != self.arena_info.loop_num:
            await anywhere_send(
                f"#编号HN100{self.loop_num}监控已关闭",
                self.arena_info.group_id,
                self.arena_info.bot_id,
            )
            return

        if not await check_client(self.arena_info.client):
            await anywhere_send(
                "当前账号被顶号，竞技场监控已退出",
                self.arena_info.group_id,
                self.arena_info.bot_id,
            )
            return

        if self.arena_info.error_count > 3:
            self.arena_info.error_count = 0
            await anywhere_send(
                f"超过最大重试次数，竞技场监控已退出{exc_value}: {traceback}",
                self.arena_info.group_id,
                self.arena_info.bot_id,
            )
            return

        logger.error(
            f"竞技场{self.arena_info.user_id}发生错误，{exc_value}: {traceback}"
        )
        self.arena_info.loop_check = time.time()
        self.arena_info.error_count += 1
        run_group[self.arena_info.group_id] = self.arena_info.bot_id
        return True


class AreanUsePool:
    def __init__(self) -> None:
        self.jjc_info: Dict[int, Arena] = {}
        self.jjc_info_group: Dict[int, Arena] = {}

    def generate_arena(self, qq_id: int, group_id: Optional[int] = None) -> Arena:
        if qq_id not in self.jjc_info:
            self.jjc_info[qq_id] = Arena(qq_id)
        if group_id is not None:
            if (
                group_id not in self.jjc_info_group
                or self.jjc_info_group[group_id].user_id != qq_id
            ):
                self.jjc_info_group[group_id] = self.jjc_info[qq_id]
            return self.jjc_info_group[group_id]
        return self.jjc_info[qq_id]

    def get_arena(self, qq_id: int, group_id: Optional[int] = None) -> Optional[Arena]:
        if qq_id in self.jjc_info and self.jjc_info[qq_id].loop_check:
            return self.jjc_info[qq_id]
        elif (
            group_id in self.jjc_info_group and self.jjc_info_group[group_id].loop_check
        ):
            return self.jjc_info_group[group_id]
        return None

    def delete_arena(
        self, qq_id: int, group_id: Optional[int] = None
    ) -> Optional[Arena]:
        if qq_id in self.jjc_info:
            del self.jjc_info[qq_id]
        if group_id in self.jjc_info_group:
            del self.jjc_info_group[group_id]


arena_manager = AreanUsePool()
