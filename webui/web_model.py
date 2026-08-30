from typing import List
from pydantic import BaseModel

from ..database.models import NoticeCache


class User(BaseModel):
    account: str
    password: str


class BossInfoCounter(BaseModel):
    name: str = ""
    id: int = 0
    current_hp: int = 0
    max_hp: int = 0
    lap: int = 0
    subscribe: int = 0
    apply: int = 0
    fighter: int = 0
    tree: int = 0


class HomeResponse(BaseModel):
    priority: int = 0
    user_id: int = 0
    name: str = "无？你绑定账号了嘛？"
    status: str = "成员"
    saying: str = (
        "我们不必为他人隐藏本性而感到愤怒，因为你自己也在隐藏本性。——拉罗什富科《箴言集》"
    )
    clan: List[int] = []


class NoticeResponse(BaseModel):
    priority: int = 0
    user_id: int = 1791800364
    subscribe: List[NoticeCache] = []
    apply: List[NoticeCache] = []
    tree: List[NoticeCache] = []


class DaoInfo(BaseModel):
    name: str = ""
    damage: int = 0
    score: int = 0
    type: str = ""
    date: int = 0
    boss: int = 0
    lap: int = 0
    dao_id: int = 0
    damage_rate: str = ""
    score_rate: str = ""
    dao: float = 0


# 注意：DashboardResponse 里引用了 DaoInfo，所以必须放在 DaoInfo 之后定义
class DashboardResponse(BaseModel):
    priority: int = 0
    clan_priority: int = 0
    user_id: int = 1791800364
    name: str = "无"
    clan_name: str = "环奈连结"
    stage: str = "暂无信息"
    dao: int = 0
    yesterday_dao: int = 0
    rank: int = 114514
    state: str = "关闭"
    boss: List[BossInfoCounter] = []
    report: list = []
    day_num: int = 0
    # 最近 20 条出刀记录（按时间倒序，用于仪表盘"最近出刀"卡片）
    last_dao: List[DaoInfo] = []


class ReportResponse(BaseModel):
    priority: int = 0
    user_id: int = 1791800364
    name: str = ""
    all: List[DaoInfo] = []
    detail: List[DaoInfo] = []
    me: List[DaoInfo] = []


class SpecialNoticeForm(BaseModel):
    group_id: str
    boss: int
    notice_type: int
    lap: int
    user_id: int


class CorrectDaoInfo(BaseModel):
    type: str
    dao_id: int
    group_id: int


class MonitorActionForm(BaseModel):
    """出刀监控开关：action='on' 时必须携带 account_id"""
    action: str                 # 'on' | 'off'
    account_id: int | None = None  # action=on 时必填（用户绑定的 Account.id 主键）


class MonitorAccountOption(BaseModel):
    """前端【开启出刀监控】弹窗里的可选账号"""
    account_id: int             # Account.id（主键）
    name: str                   # 角色昵称
    platform: int               # 服务器编号
    viewer_id: int | None = None


class RankReward(BaseModel):
    """该档位对应的排名奖励"""

    gem: int = 0        # 宝石
    coin: int = 0       # 行会币
    shard: int = 0      # 依里记忆碎片


class RankLine(BaseModel):
    """档线单条记录（period_ranking 中指定排名的公会信息）"""
    rank: int
    damage: int | None = None
    clan_name: str | None = None
    leader_name: str | None = None
    leader_viewer_id: int | None = None
    member_num: int | None = None
    reward: RankReward | None = None


class RankLineResponse(BaseModel):
    clan_battle_id: int = 0
    lines: List[RankLine | None] = []   # 与请求 targets 顺序一致，查不到的档位为 null
    my: RankLine | None = None          # 我会当前排名
    default_ranks: List[int] = []       # 后端默认档位（前端首次加载用）
