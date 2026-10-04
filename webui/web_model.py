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
    # 首页「游戏账号」卡的绑定 / 换绑 / 解绑入口用它（和仪表盘状态条上原来是同一份）。
    # 2026-10-04 用户要求把绑定入口从「会战仪表盘」挪到首页，所以 /home 也带上它。
    account: GroupAccountInfo = GroupAccountInfo()


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
    kind: str = ""      # 档位类别：'gold'/'silver'/'bronze' 前三名（金/银/铜三色）、
                        # 'last' 榜单末位、'' 普通。由后端 clanbattle.base.rank_line_kind
                        # 判定，前端据此上专属颜色


class RankLineResponse(BaseModel):
    clan_battle_id: int = 0
    lines: List[RankLine | None] = []   # 与请求 targets 顺序一致，查不到的档位为 null
    my: RankLine | None = None          # 我会当前排名
    default_ranks: List[int] = []       # 后端默认档位（前端首次加载用）
    head_ranks: List[int] = []          # 前三名档位（金/银/铜），前端上专属颜色用
    cached: bool = False                # True = 本次结果来自本地缓存，没有去抓游戏接口
    stale: bool = False                 # True = 抓取失败，退回来用的是过期缓存
    monitor_running: bool = False       # 出刀监控是否在跑（只有它在跑时才允许更新缓存）
    updated_at: int = 0                 # 这份数据的抓取时间（Unix 秒，0 = 未知）


# ---------------------------- BOX / 助战 / 竞技场 ----------------------------


class ImageResult(BaseModel):
    """出图类接口的统一返回（BOX / 助战 / 竞技场排行榜、查防守）

    `ok=False` 时由 `message` 说明原因（缓存还没刷新、角色不存在、竞技场监控没在跑…）。
    刻意不用 4xx 表达这些「业务上的空结果」，免得被前端拦截器统一弹成「请求失败」。
    """

    ok: bool = False
    message: str = ""
    count: int = 0
    # data:image/png;base64,... —— 前端直接塞进 <img :src>
    image: str = ""


class TextResult(BaseModel):
    """纯文字返回（竞技场查 ID）"""

    ok: bool = False
    message: str = ""
    text: str = ""


class BoxUnit(BaseModel):
    """BOX / 助战查询结果里的一个角色条目（**Web 端专用**）

    QQ 群指令走的仍是 `support_query.create_img` 那套 PIL 出图（几百个角色拼成一张
    大图），网页端不复用它：只返回结构化数据，头像由
    `/{group_id}/box/avatar/{unit_id}` 单独出 PNG，点开再看详情。

    同一个 `unit_id` 会在公会 BOX / 助战里出现多次（多个玩家都有这个角色），
    靠 `player_name` / `pcrid` 区分。
    """

    unit_id: int = 0
    chara_name: str = ""        # 角色名（fromid(unit_id).name）
    player_name: str = ""       # 玩家昵称（个人 BOX / 我的助战里就是你自己）
    pcrid: int = 0              # 玩家游戏 ID
    owned: bool = True          # 是否已拥有。False = 占位条目，只有 id / 名字 / 头像，
                                # 前端灰度显示（个人 BOX 里用来一眼看出缺哪些角色）
    avatar: str = ""            # 头像地址（相对路径，前端直接塞 <img :src>）。
                                # 带 star / rarity / battle_rarity 三个查询参数，
                                # 后端据此在头像底部叠出星级（含「调星」的亮蓝星）
    star: int = 3               # 头像档位 1/3/6 —— 决定用哪张底图，别让前端猜
    rarity: int = 0             # 真实星级 1~6（拥有到几星）
    battle_rarity: int = 0      # 战斗星级（会战「调星」后的星级，0 = 没调过）。
                                # 与 rarity 不同时头像底部会有亮蓝星，
                                # 详情面板也会标「已调星」
    level: int = 0
    rank: int = 0
    unique_level: int = 0       # 专武等级（-1 = 未装备）
    unique_level2: int = 0
    love_level: int = 0         # 好感等级。只有个人 BOX / 我的助战有（`PlayerUnit`）；
                                # 助战接口不给好感等级，所以助战恒为 0
    special_attribute: str = "" # 好感加成文字。只有助战有（`SupportUnit`）；
                                # 个人 BOX 拿不到。前端平时只显示「N 级 / 加成」短标签，
                                # 点开才看完整文字
    union_burst: int = 0
    main_1: int = 0
    main_2: int = 0
    ex: int = 0
    equip_1: str = ""           # 左上
    equip_2: str = ""           # 右上
    equip_3: str = ""           # 左中
    equip_4: str = ""           # 右中
    equip_5: str = ""           # 左下
    equip_6: str = ""           # 右下
    cb_ex_equip_1: int = 0
    cb_ex_equip_2: int = 0
    cb_ex_equip_3: int = 0
    cb_ex_equip_1_level: int = 0
    cb_ex_equip_2_level: int = 0
    cb_ex_equip_3_level: int = 0
    # 会战 EX 装备图标地址（后端按 equipment_id 拼好；id 为 0 时是空串）。
    # 图标本体由 `/{group_id}/box/ex_equip_icon/{equipment_id}` 出，和 QQ 端出图
    # 用的是同一份缓存资源。
    cb_ex_equip_1_icon: str = ""
    cb_ex_equip_2_icon: str = ""
    cb_ex_equip_3_icon: str = ""
    support_position: int = 0   # 助战位：1/2 冒险，3/4 地下城，5/6 团队战·露娜塔
    # 助战位所属分组（「我的助战」按它分三栏展示）：
    # 'dungeon' 地下城 / 'clan' 团队战·露娜之塔 / 'adventure' 冒险 / '' 认不出来。
    # 由后端按 support_position 判定，前端别自己按位置猜。
    support_group: str = ""


class BoxQueryResult(BaseModel):
    """BOX / 助战查询的返回（替代原来的整图 ImageResult）"""

    ok: bool = False
    message: str = ""
    count: int = 0          # units 总条数（含未拥有的占位）
    owned_count: int = 0    # 其中已拥有
    missing_count: int = 0  # 其中未拥有（灰度占位）
    units: List[BoxUnit] = []


class BoxCacheRefreshResult(BaseModel):
    """网页端「刷新缓存」按钮的返回

    一次把**个人 BOX** 和**本群公会助战**两份缓存都刷新，等价于在群里先后发
    【刷新box缓存】和【刷新助战缓存】—— 会**真的登录游戏账号**（顶号），前端点之前
    必须给出提示。两份只登录一次（两次取数复用同一个 client），所以不比原来更慢。
    刷新逻辑与 QQ 指令共用 `support_query.util.refresh_box_and_support`。
    """

    ok: bool = False
    message: str = ""
    kind: str = "all"           # 固定 'all'（个人 BOX + 公会助战）
    count: int = 0              # 本次写入的条目数合计
    box_count: int = 0          # 其中个人 BOX 的角色数
    support_count: int = 0      # 其中公会助战的条数
    # 公会助战那半失败的提示（例如「现在不是会战期间」）。**为空表示两份都刷成了**；
    # 非空时 `ok` 仍然是 True —— 个人 BOX 已经刷新成功，不该整个报失败。
    support_error: str = ""


class SupportChangeForm(BaseModel):
    """网页端「我的助战」→【更换支援】的请求体。

    `mode` 是游戏里的支援栏位，和 QQ 端三条指令一一对应：
      1 = 地下城（【上地下城支援】）
      2 = 团队战 · 露娜之塔（【上公会战支援】/【上露娜塔支援】）
      3 = 关卡 · 冒险（【上关卡支援】）
    `unit_id` 是要挂上去的角色 ID（不带末尾的 01）。
    """

    unit_id: int
    mode: int


class SupportChangeResult(BaseModel):
    """「更换支援」的返回。

    ⚠️ 这是**写操作**：会登录你的游戏账号并真的改游戏里的支援设定（**顶号**），
    正在玩游戏的你会被挤下线 —— 前端点之前必须先弹确认。
    更换逻辑与 QQ 端【上XX支援】共用 `support_query.util.change_support_unit`。
    """

    ok: bool = False
    message: str = ""
    mode: int = 0             # 1 地下城 / 2 团队战·露娜塔 / 3 关卡（冒险）
    unit_id: int = 0          # 本次挂上去的角色 ID
    position: int = 0         # 挂到了哪个助战位（1~6）
    removed_unit_id: int = 0  # 被顶掉的角色 ID（0 = 没有顶掉谁）


class ArenaSettingForm(BaseModel):
    """竞技场提醒开关（网页端只改这两个开关，开 / 关监控仍然只在 QQ 群里做）"""

    jjc_notice: bool | None = None
    grand_notice: bool | None = None


class ArenaStatus(BaseModel):
    """竞技场中心顶部状态卡"""

    running: bool = False           # 本群有没有正在运行的竞技场监控
    jjc_notice: bool = True         # 竞技场提醒（落 ArenaSetting 表）
    grand_notice: bool = True       # 公主竞技场提醒
    jjc_rank: int = 0               # 监控账号当前竞技场排名
    jjc_group: int = 0              # 竞技场场次
    grand_rank: int = 0
    grand_group: int = 0
    loop_num: int = 0               # 监控编号
    monitor_user_id: int = 0        # 监控人 QQ（0 = 没有监控在跑）
    is_monitor: bool = False        # 当前登录用户是不是监控人本人


class GrandCacheRow(BaseModel):
    """公主竞技场防守缓存的一行"""

    pcrid: int = 0                  # 对手玩家 ID
    grand_id: int = 0               # 场次
    row: int = 0                    # 防守位置（1/2/3）
    vs_time: int = 0                # 对战时间（Unix 秒）
    units: List[int] = []           # 防守队伍的角色 ID
    names: List[str] = []           # 对应的角色名（后端解析好，前端直接用）
