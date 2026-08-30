import string
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List

# 会战阶段用数字和用字母之间的转换
stage_dict = {letter: i for i, letter in enumerate(string.ascii_uppercase, start=1)}
stage_dict.update(enumerate(string.ascii_uppercase, start=1))
TALENT = [
    "火",
    "水",
    "风",
    "光",
    "暗",
]


class Platform(Enum):
    """
    各个平台id，仅储存
    与游戏登录那块无关
    """

    b_id = 0
    qu_id = 1
    tw_id = 2


class GamePlatform(Enum):
    """
    各个平台id
    游戏登录有关
    """

    b_id = "2"
    qu_id = "4"


class AllowLevel(Enum):
    """
    允许别人上号等级
    0：只允许自己
    1：允许管理
    2：任何贱民
    """

    own = 0
    adim = 1
    rbq = 2


class NoticeType(Enum):
    """
    分别表示不同的通知类型
    0：预约
    1：挂树
    2：申请出刀
    3：出刀伤害
    4；正在出刀
    5：SL
    """

    subscribe = 0
    tree = 1
    apply = 2
    dao = 3
    fighter = 4
    sl = 5


class UnitBlack(Enum):
    black = 0
    loss = 1
    work = 2


class ItemID(Enum):
    clanbattle_coin = 90006


class EquipRankExp(Enum):
    sliver: List[int] = [0, 30, 80, 160]  # 4
    golden: List[int] = [0, 60, 160, 360, 700, 1200]  # 7
    purple: List[int] = [0, 100, 260, 540, 1020, 1800]  # 11


class FilePath(Enum):
    """
    不同类型文件储存路径
    """

    resource = Path(__file__).parent / "resource"
    data = resource / "data"
    img = resource / "img"
    font = resource / "font"
    run_group = data / "rungroup.json"
    homework_cache = data / "homework_cache.json"


class FontPath(Enum):
    """
    字体，目前就一个
    """

    pcr_font = FilePath.font.value / "SourceHanSansCN-Medium.otf"


@dataclass
class BossValue:
    rate: float
    max_hp: int


@dataclass
class BossInfo:
    boss_id: int
    name: str


class BossDefault(Enum):
    stages = [0, 3, 10, 30, 40]
    boss_info = [
        BossInfo(305702, "巨型哥布林"),
        BossInfo(302002, "野性狮鹫"),
        BossInfo(304801, "幽灵领主"),
        BossInfo(303302, "暗黑滴水嘴兽"),
        BossInfo(301305, "暴食魔兽"),
    ]
    boss_value = [
        [
            BossValue(1.2, 6000000),
            BossValue(1.2, 8000000),
            BossValue(1.3, 10000000),
            BossValue(1.4, 12000000),
            BossValue(1.5, 15000000),
        ],
        [
            BossValue(1.6, 6000000),
            BossValue(1.6, 8000000),
            BossValue(1.8, 10000000),
            BossValue(1.9, 12000000),
            BossValue(2, 15000000),
        ],
        [
            BossValue(2, 7000000),
            BossValue(2, 9000000),
            BossValue(2.4, 13000000),
            BossValue(2.4, 15000000),
            BossValue(2.6, 20000000),
        ],
        [
            BossValue(3.5, 17000000),
            BossValue(3.5, 18000000),
            BossValue(3.7, 20000000),
            BossValue(3.8, 21000000),
            BossValue(4, 23000000),
        ],
        [
            BossValue(3.5, 85000000),
            BossValue(3.5, 90000000),
            BossValue(3.7, 95000000),
            BossValue(3.8, 100000000),
            BossValue(4, 110000000),
        ],
    ]
