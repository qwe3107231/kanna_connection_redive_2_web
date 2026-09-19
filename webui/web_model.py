from typing import List
from pydantic import BaseModel

from ..database.models import NoticeCache


class User(BaseModel):
    account: str
    password: str


class ChangePasswordForm(BaseModel):
    """网页端修改密码：必须带旧密码，避免只拿到 cookie 的人直接把账号改走"""

    old_password: str
    new_password: str


class GroupAccountInfo(BaseModel):
    """当前登录用户在本群生效的游戏账号

    「按群绑定」的取值规则是：本群绑定的号优先，本群没绑就回退到全局号
    （group_id=0，即 QQ 私聊绑定的那个）。所以这里把两种来源都标出来，
    前端才能显示成「本群专用」还是「沿用全局号」。
    """

    bound: bool = False            # 本群有没有可用的号（本群号或全局号）
    is_group_bound: bool = False   # True = 本群专用号；False = 回退到全局号
    account_id: int | None = None  # Account.id（主键）
    name: str = ""                 # 角色昵称
    platform: int = 0              # 服务器编号（basedata.Platform）
    viewer_id: int | None = None   # 游戏ID


class BindAccountForm(BaseModel):
    """网页端在某个群里绑定游戏账号

    三个服共用一张表单，按 platform 取对应字段（与 QQ 端三条绑定指令一一对应）：
      官服 platform=0：bili_account + bili_password（B站账号密码，先换 access_key）
      渠服 platform=1：login_id + token（token 也接受 "xxx yyy" 的加密串形式）
      台服 platform=2：short_udid + udid + viewer_id
    """

    platform: int
    # 官服
    bili_account: str = ""
    bili_password: str = ""
    # 渠服
    login_id: str = ""
    token: str = ""
    # 台服
    short_udid: str = ""
    udid: str = ""
    viewer_id: int | None = None


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
    clan: List[dict] = []
    # 是否已绑定游戏账号（前端据此禁用预约/申请/挂树入口）
    has_account: bool = False


class NoticeResponse(BaseModel):
    priority: int = 0
    # 当前登录用户在本群的权限等级（basedata.GroupPriority），前端按它控制通知管理入口
    clan_priority: int = 0
    # 本群有没有可用的游戏账号（本群号或全局号），前端据此禁用「添加通知」
    has_account: bool = False
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
    # 出刀监控人 QQ（0 = 未开启监控）；前端据此禁用非监控人的监控开关按钮
    monitor_user_id: int = 0
    # 当前登录用户在本群生效的游戏账号（仪表盘状态条上显示 / 绑定入口用它判断）
    account: GroupAccountInfo = GroupAccountInfo()


class ReportResponse(BaseModel):
    priority: int = 0
    # 当前登录用户在本群的权限等级（basedata.GroupPriority），前端按它控制修正出刀入口
    clan_priority: int = 0
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
    group_id: int = 0           # 归属群（0 = 全局号，即 QQ 私聊绑定的那个）
    is_group_bound: bool = False  # 是否为本群专用号（False 表示是全局号）


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
    cached: bool = False                # True = 本次结果来自本地缓存，没有去抓游戏接口
    stale: bool = False                 # True = 抓取失败，退回来用的是过期缓存
    monitor_running: bool = False       # 出刀监控是否在跑（只有它在跑时才允许更新缓存）
    updated_at: int = 0                 # 这份数据的抓取时间（Unix 秒，0 = 未知）
