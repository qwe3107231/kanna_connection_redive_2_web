from typing import List
from .base import float2int
from ..util.auto_boss import clan_boss_info
from ..database.models import RecordDao, ClanBattleKPI

standard = {"low": 0.3, "high": 0.8, "e_low": 0.1, "e_high": 0.3}


def kpi_dao(damage: int, order: int, lap: int) -> int:
    stage = clan_boss_info.lap2stage(lap)
    rate = damage / clan_boss_info.get_boss_max(lap, order)

    if stage == 5:
        if rate > standard["high"]:
            return 1.5  # e面高伤特别奖励
        elif rate > standard["e_high"]:
            return 1
        elif rate < standard["e_low"]:
            return 0.5
        else:
            return (
                0.5
                / (standard["e_high"] - standard["e_low"])
                * (rate - standard["e_low"])
                + 0.5
            )

    if rate > standard["high"]:
        return 1
    elif rate < standard["low"]:
        return 0.5
    else:
        return (
            0.5 / (standard["high"] - standard["low"]) * (rate - standard["low"]) + 0.5
        )


def kpi_report(info: List[RecordDao], special: List[ClanBattleKPI]) -> list:
    special_kpi = {player.pcrid: player.bouns for player in special}
    player_info = {
        player.pcrid: {
            "pcrid": player.pcrid,
            "name": player.name,
            "knife": 0
            if player.pcrid not in special_kpi
            else special_kpi[player.pcrid],
            "correct": 0
            if player.pcrid not in special_kpi
            else special_kpi[player.pcrid],
        }
        for player in info
    }

    for player in info:
        player_info[player.pcrid]["knife"] += kpi_dao(
            player.damage, int(player.boss), player.lap
        )
    players = [
        (
            player["pcrid"],
            player["name"],
            float2int(round(player["knife"], 3)),
            player["correct"],
        )
        for player in player_info.values()
    ]
    players.sort(key=lambda x: x[2], reverse=True)
    return players
