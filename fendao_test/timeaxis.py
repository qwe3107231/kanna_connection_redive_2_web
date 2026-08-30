from dataclasses import dataclass
from loguru import logger
import json
import itertools
from typing import Dict, List, Tuple, Union
import httpx
from nonebot import on_startup
from .data_model import HomeWorkData, HomeWorkDictItem
from ..basedata import FilePath, stage_dict
from ..util.tools import load_config, write_config
from ..util.auto_boss import clan_boss_info
from hoshino.modules.priconne._pcr_data import CHARA_NAME

clanbattlework_path = FilePath.homework_cache.value

MAX_CALCULATE_LIMIT = 114514  # 最大计算量
MAX_RESULT = 3  # 最大获取结果数
MAX_QUERY = 8  # 一个boss显示几个作业
MAX_SINGLE_BOSS = 3  # 一个阶段中一个boss显示几个作业


class ClanBattleWorkManage:
    def __init__(self):
        self.clanbattle_work: List[Dict[str, Dict[str, HomeWorkDictItem]]] = (
            load_config(clanbattlework_path)
        )

    def get_work_by_id(self, work_id: str) -> HomeWorkDictItem:
        work_id = work_id.upper()
        return self.clanbattle_work[work_id[-3]][letter2stageid(work_id[0])][work_id]

    def filter_by_boss(self, boss: int) -> Dict[str, Dict[str, HomeWorkDictItem]]:
        return self.clanbattle_work[boss]

    def filter_by_stage(
        self, stage: str, show_dict: Dict[str, Dict[str, HomeWorkDictItem]]
    ) -> Dict[str, HomeWorkDictItem]:
        if stage.isdigit():
            stage = letter2stageid(stage)
        return show_dict[stage]

    def filter_by_type(
        self, dao_type: str, show_list: Dict[str, HomeWorkDictItem]
    ) -> Dict[str, HomeWorkDictItem]:
        dao_type = dao_type.upper()
        return {
            work_id: work
            for work_id, work in show_list.items()
            if self.judge_type(work_id, dao_type)
        }

    def judge_type(self, work_id: str, dao_type: str) -> bool:
        if "T" in dao_type and "T" in work_id:
            return True
        if "W" in dao_type and "W" in work_id:
            return True
        return "S" in dao_type and len(work_id[:-3]) == 1

    def query_work_by_units(self, units: List[int], stage: str, boss: int) -> List[str]:
        works = self.filter_by_stage(stage, self.filter_by_boss(boss))
        return [
            work_id for work_id in works if set(units) <= set(works[work_id]["unit"])
        ]

    def work_id2units(self, work_id: str) -> List[int]:
        return self.get_work_by_id(work_id)[work_id]["unit"]

    def get_boss_work(
        self, stage: str, boss: int, dao_type="TWS"
    ) -> Dict[str, HomeWorkDictItem]:  # type,T自动，W尾刀，S手动

        return self.filter_by_type(
            dao_type, self.filter_by_stage(stage, self.filter_by_boss(boss))
        )

    async def get_clanbattlework(self):
        boss_id = -1
        check_id = None
        # 获取json数据
        clanbattle_work = [{} for _ in range(5)]
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(
                    "https://www.caimogu.cc/gzlj/data?date=&lang=zh-cn",
                    headers={"x-requested-with": "XMLHttpRequest"},
                )
                data = HomeWorkData.parse_raw(res.content)
            for work in data.data:
                hw_id = work.id
                stage = str(work.stage)
                if hw_id != check_id:
                    check_id = hw_id
                    boss_id += 1
                clanbattle_work[boss_id][stage] = {
                    bosswork.sn: {
                        "info": bosswork.info,
                        "unit_id": bosswork.unit,
                        "damage": bosswork.damage,
                        "video_link": bosswork.video,
                    }
                    for bosswork in work.homework
                }
            if not clanbattle_work[0][1]:
                return False
            write_config(clanbattlework_path, clanbattle_work)
            self.clanbattle_work = clanbattle_work
            return True
        except httpx.HTTPError as e:
            logger.warning(f"HTTP error occurred: {e}")
            return False
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error occurred: {e}")
            return False
        except Exception as e:
            logger.warning(f"An error occurred: {e}")
            return False


clanbattle_work = ClanBattleWorkManage()


# @on_startup
async def check_msg():
    if not await clanbattle_work.get_clanbattlework():
        print("作业刷新失败")  # 启动就获取一次


def type2chinese(type: str):
    msg = ""
    type_edit = type.upper()
    if "S" in type_edit:
        msg += "手动"
    if "T" in type_edit:
        msg += "自动"
    if "W" in type_edit:
        msg += "尾刀"
    return "" if msg == "手动自动尾刀" else msg


def letter2stageid(stage_letter: str):
    return str(stage_dict[stage_letter.upper()])


@dataclass
class BossWorkDetailData:
    unit: List[int]
    damage: int
    score: int
    work_id: str


@dataclass
class TeamData:
    damage: int
    score: int
    teamid_list: List[str]


class TimaAxis:

    def __init__(
        self, stage: str, arrange: str, set_type: str = "TS", all_boss: List[int] = None
    ):
        if all_boss is None:
            all_boss = []
        self.set_stage = stage.upper()
        self.set_arrange = arrange
        self.set_type = set_type.upper()
        self.all_boss = all_boss

    def set_black(self, loss_units=None, black_units=None, black_work=None):
        if loss_units is None:
            loss_units = []
        if black_units is None:
            black_units = []
        if black_work is None:
            black_work = []
        self.loss_units = loss_units
        self.black_units = black_units
        self.black_work = black_work
        self.box = set(CHARA_NAME) - set(loss_units)

    def judge2team(self, x, y):
        return len(set(x + y)) > 8

    def same_chara(self, x, y):
        return 10 - len(x | y)

    def have_chara(self, x):
        return len(x & self.box)

    def have_84(self, x, y):
        return self.have_chara(x) >= 8 and self.have_chara(y) >= 4

    def check_available(self, perm: Tuple[BossWorkDetailData]):

        knife = len(perm)

        check = False

        # 五个角色里有4个可用即可
        if knife == 1 and self.have_chara(set(perm[0].unit)) >= 4:
            check = True

        elif knife == 2:  # 剩2刀没出
            x, y = set(perm[0].unit), set(perm[1].unit)
            if self.same_chara(x, y) == 0:  # 如果没有重复
                if self.have_chara(x) >= 4 and self.have_chara(y) >= 4:
                    # 这两队中每队的5个角色要有4个
                    check = True
                elif (
                    self.same_chara(x, y) <= 2 and self.have_chara(x | y) >= 8
                ):  # 有1~2个重复
                    # 这两队中出现的角色要有8个
                    check = True

        elif knife == 3:  # 剩3刀没出
            x, y, z = set(perm[0].unit), set(perm[1].unit), set(perm[2].unit)
            jxy, jyz, jxz = (
                self.same_chara(x, y),
                self.same_chara(y, z),
                self.same_chara(x, z),
            )  # 获取两两之间重复角色
            if jxy < 3 and jyz < 3 and jxz < 3 and jxy + jxz + jyz <= 3:
                # print("无冲，接下来判断当前账号是否可用")
                if jxy + jxz + jyz == 3:  # 210/111
                    if set(x | y | z).issubset(self.box):  # 三队中出现的所有角色都要有
                        check = True
                elif (jxy == 0) + (jxz == 0) + (jyz == 0) == 2:  # 200/100:  # 200/100
                    # 重复的两队有8个角色 另一队有4个
                    if (
                        jxy
                        and self.have_84(x | y, z)
                        or jxz
                        and self.have_84(x | z, y)
                        or jyz
                        and self.have_84(y | z, x)
                    ):
                        check = True
                elif jxy + jxz + jyz == 0:  # 000
                    if (
                        self.have_chara(x) >= 4
                        and self.have_chara(y) >= 4
                        and self.have_chara(z) >= 4
                    ):  # 每队有4个
                        check = True
                else:  # 110:
                    if self.have_chara(x | y | z) >= 12:
                        # 三队中出现的所有角色（13个）要有任意12个
                        check = True
        if not check:
            return False, 0, 0, []

        total_damage = 0
        total_score = 0
        teamid_list = []
        for data in perm:
            total_damage += data.damage
            total_score += data.score
            teamid_list.append(data.work_id)
        teamid_list.sort()
        return True, TeamData(total_damage, total_score, teamid_list)

    def get_result(self, work_list: List[List[BossWorkDetailData]]):
        res = []
        for perm in itertools.product(*work_list):
            data = self.check_available(perm)
            if data[0]:
                if len(res) >= MAX_CALCULATE_LIMIT:
                    break
                _, team = data
                res.append(team)
        result = self.arrange_fen_dao(res, arrange=self.set_arrange)
        return result[:MAX_RESULT]

    async def check_black_unit(self, units):
        return len(set(units) | set(self.black_units)) == len(units + self.black_units)

    def arrange_fen_dao(
        self, res: List[Union[BossWorkDetailData, TeamData]], arrange: str
    ):
        if arrange == "毛分":
            res.sort(key=lambda x: x.score, reverse=True)
        else:
            res.sort(key=lambda x: x.damage, reverse=True)
        return res

    def filter_black_work_id(self, works: Dict[str, HomeWorkDictItem]):
        return {
            work_id: work
            for work_id, work in works.items()
            if work_id not in self.black_work
        }

    def get_work_list(self, works, boss, stage):
        works = self.filter_black_work_id(works)
        return self.arrange_fen_dao(
            [
                BossWorkDetailData(
                    works[work_id]["unit"],
                    works[work_id]["damage"],
                    works[work_id]["damage"]
                    * clan_boss_info.get_boss_rate_by_stage(int(stage), boss),
                    work_id,
                )
                for work_id in works
                if self.check_black_unit(works[work_id]["unit"])
            ],
            self.set_arrange,
        )

    async def fen_dao(self) -> List[TeamData]:
        # 默认不计算尾刀
        if (i := len(self.set_stage)) == 1:
            stage = letter2stageid(self.set_stage)
            stage_list = [stage, stage, stage]
        elif i < len(self.all_boss):
            return "输入错误"
        else:
            stage_list = [letter2stageid(stages) for stages in self.set_stage]

        if len(self.all_boss) > 0:
            work_list = [
                self.get_work_list(
                    clanbattle_work.get_boss_work(
                        stage_list[index], boss, self.set_type
                    ),
                    boss,
                    stage,
                )
                for index, boss in enumerate(self.all_boss)
            ]
        else:
            temp = []
            for boss in range(1, 6):
                temp += self.get_work_list(
                    clanbattle_work.get_boss_work(stage_list[0], boss, self.set_type),
                    boss,
                    stage,
                )

            work_list = [temp, temp, temp]
        return self.get_result(work_list)
