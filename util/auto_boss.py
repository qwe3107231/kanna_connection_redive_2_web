import datetime
from dataclasses import dataclass
from typing import List, Union

import httpx

from ..basedata import BossDefault, BossInfo, BossValue, stage_dict
from ..setting import BossData
from .tools import load_config, write_config


@dataclass
class BossOnlineData:
    boss_info: List[BossInfo]
    boss_value: List[List[BossValue]]
    stages: List[int]


async def get_boss_data(server: str = "cn") -> BossOnlineData:
    date = datetime.date.today()
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"https://pcr.satroki.tech/api/Quest/GetClanBattleInfos?s={server}"
        )
        content = res.json()
        for info in content:
            if info["year"] == date.year and info["month"] == date.month:
                write_config(BossData.info_path.value, info["phases"])
                return general_boss_info(info["phases"])


def general_boss_info(info: dict) -> BossOnlineData:
    boss_info = [BossInfo(boss["unitId"], boss["name"]) for boss in info[0]["bosses"]]
    boss_value = [[] for _ in range(5)]
    stages = [0]
    for i, stage in enumerate(info):
        stages.append(stage["lapTo"])
        boss_value[i] = [
            BossValue(boss["scoreCoefficient"], boss["hp"]) for boss in stage["bosses"]
        ]
    return BossOnlineData(boss_info, boss_value, stages[:-1])


class ClanBossInfo:
    def __init__(self) -> None:
        if BossData.use_online.value:
            self.load_online()
        else:
            self.load_default()

    def load_online(self):
        if info := load_config(BossData.info_path.value):
            boss = general_boss_info(info)
            self.stages = boss.stages
            self.boss_value = boss.boss_value
            self.boss_info = boss.boss_info
        else:
            self.load_default()

    def load_default(self):
        self.stages = BossDefault.stages.value
        self.boss_value = BossDefault.boss_value.value
        self.boss_info = BossDefault.boss_info.value

    def lap2stage(self, lap_num: int, use_num=False) -> Union[int, str]:
        stage_max = len(self.stages)
        return next(
            (
                i if use_num else stage_dict[i]
                for i in range(stage_max)
                if lap_num <= self.stages[i]
            ),
            stage_max if use_num else stage_dict[stage_max],
        )

    def get_boss_rate(self, lap_num: int, boss: int) -> float:
        stage: int = self.lap2stage(lap_num, True)
        return self.boss_value[stage - 1][boss - 1].rate

    def get_boss_rate_by_stage(self, stage: int, boss: int) -> float:
        return self.boss_value[stage - 1][boss - 1].rate

    def get_boss_max(self, lap_num: int, boss: int) -> float:
        stage: int = self.lap2stage(lap_num, True)
        return self.boss_value[stage - 1][boss - 1].max_hp

    def get_boss_info(self, order: int) -> BossInfo:
        return self.boss_info[order]

    def get_boss_value(self, order: int) -> BossInfo:
        return self.boss_value[order]

    async def update_boss(self, server: str = "cn"):
        if BossData.use_online.value:
            await get_boss_data(server)
            self.load_online()


clan_boss_info = ClanBossInfo()
