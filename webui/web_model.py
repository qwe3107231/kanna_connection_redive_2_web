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
    """仪表盘状态条上显示的游戏账号

    **一个 QQ 只有一个游戏账号，在任何群里都通用**：绑定写的是
    `Account.group_id = 0` 那一行，和 QQ 私聊【绑定账号】写的是同一行，
    所以换公会 / 进新群都不需要重新绑定。

    历史上还支持过「本群专用号」（group_id = 本群号），2026-09-20 按用户
    要求废弃 —— 网页端不再产生、也不再区分这种号，`is_group_bound` 一并去掉。
    """

    bound: bool = False            # 有没有绑号
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
    # 有没有可用的游戏账号（账号是全局的，各群同值），前端据此禁用「添加通知」
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


class DayDamageRank(BaseModel):
    """仪表盘「今日伤害排行」的一行（按玩家聚合今日出刀）。

    替代了原来那张标题写「伤害占比」、实际画「按刀数分组的人数占比」的饼图 ——
    那个和左栏「今日出刀分布」读的是同一份数据，纯重复。
    """

    name: str = ""
    damage: int = 0
    score: int = 0
    # 今日累计刀数（完整刀 1、尾刀/补偿刀 0.5）
    dao: float = 0
    # 占全员总量的百分比（0-100，保留两位）
    damage_rate: float = 0
    score_rate: float = 0


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
    # 今日伤害排行 Top N（按伤害倒序），给仪表盘右栏的横向条形图用
    day_damage_rank: List[DayDamageRank] = []
    # 今日全员总伤害 / 总分数 —— 排行里 damage_rate / score_rate 的分母，
    # 前端标题栏也会显示"全员总伤害"，让 Top N 之外的量有个交代
    day_damage_total: int = 0
    day_score_total: int = 0
    # 出刀监控人 QQ（0 = 未开启监控）；前端据此禁用非监控人的监控开关按钮
    monitor_user_id: int = 0
    # 当前登录用户的游戏账号（全局，一个 QQ 一个号；状态条显示 / 绑定入口判断用它）
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
    group_id: int = 0           # 归属群（现在恒为 0：一个 QQ 只有一个全局号）


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
