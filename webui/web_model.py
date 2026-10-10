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


class ExEquipSubStatus(BaseModel):
    """5 星彩装的**一条词条**（究极炼成随机出来的那几条属性）。

    数值不在游戏给的数据里，要按 (属性, step) 查表算 —— 见
    `support_query.ex_equip_data.sub_status_entries`。**同一属性会合并累加**
    （一件装备上两条物穿 → 只显示一条「物穿 10」），所以一件彩装最多 4 项。
    `percent=True` 的显示成 "1.00%"（`text` 已经换算好），其余是固定值。

    锁定与否不在这里：那是炼成时的事，和换装无关，不展示。
    """

    status: int = 0             # 游戏属性编号（eParamType）
    key: str = ""               # 我们自己的属性键
    label: str = ""             # 属性中文名
    percent: bool = False
    value: int = 0              # 同一属性累加后的数值
    text: str = ""              # 可直接展示（"1.00%" / "10"）


class BoxExEquip(BaseModel):
    """角色详情里的**一个普通 EX 槽**（网页端 BOX 页专用）

    与上面那三个 `cb_ex_equip_*`（会战 EX，QQ 端出图也在用）刻意分开：普通 EX 槽
    一共 3 个，每个槽能穿的**类别由角色决定**（`resource/data/unit_ex_equipment_slot.json`），
    所以「空槽」也必须带类别名一起下发 —— 前端才能显示「EX 1 · 拳套 · 未装备」，
    否则用户根本不知道点开能选什么。

    数据来自本地缓存表 `PlayerExEquip`（【刷新box缓存】时写入）；
    详情弹窗点这个槽会去打 `/{group_id}/box/ex_equip/options` 拿可选装备列表。
    """

    slot: int = 0               # 槽位 1~3
    category: int = 0           # 槽位能穿的类别（101~110 / 201~204 / 301~305）
    category_name: str = ""     # 类别中文名（后端查表给，前端别自己映射）
    equipped: bool = False      # 这个槽现在有没有穿装备
    equipment_id: int = 0
    name: str = ""
    rarity: int = 0             # 1 铜 / 2 银 / 3 金 / 4 粉 / 5 彩
    rarity_name: str = ""
    star: int = 0               # 按强化 PT 算出来的星级
    clan_battle: bool = False   # 是不是会战专用（【行会】系列）
    icon: str = ""              # 图标地址（走 box/ex_equip_icon，和会战 EX 共用一份资源）
    # 5 星彩装的 4 条词条（1~4 星装备恒为空）
    sub_statuses: List[ExEquipSubStatus] = []


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
    # 会战 EX 图标地址（后端按 equipment_id 拼好；id 为 0 时是空串），本体走
    # `/{group_id}/box/ex_equip_icon/{equipment_id}`，与 QQ 端出图同一份缓存。
    cb_ex_equip_1_icon: str = ""
    cb_ex_equip_2_icon: str = ""
    cb_ex_equip_3_icon: str = ""
    # ---- 普通 EX 装备（会战 EX 不受影响）----
    # 类别来自角色槽位表，空槽也有 3 条；ex_equip_known=False = 还没缓存，前端提示刷新。
    ex_equips: List[BoxExEquip] = []
    ex_equip_known: bool = False
    # 这个条目是不是当前登录用户自己的。只有自己的能换装 —— 换装永远打在当前账号上，
    # 公会 BOX / 助战里点别人那条会张冠李戴。
    ex_equip_editable: bool = False
    support_position: int = 0   # 助战位：1/2 冒险，3/4 地下城，5/6 团队战·露娜塔
    # 助战位分组：'dungeon' 地下城 / 'clan' 团队战·露娜之塔 / 'adventure' 冒险 / '' 未知。
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


class ArenaMonitorActionForm(BaseModel):
    """网页端「个人监控」开关：action='on' 开（等价群里发【竞技场监控】）/ 'off' 关"""

    action: str                     # 'on' | 'off'


class ArenaRankRow(BaseModel):
    """竞技场排行榜的一行（网页端绘制；替代原来拼好的 PNG）"""

    rank: int = 0                   # 名次
    name: str = ""                  # 玩家昵称
    viewer_id: int = 0              # 玩家游戏 ID
    unit_id: int = 1000             # 头像角色 ID（4 位，喂给 box/avatar 接口）
    rarity: int = 0                 # 头像角色星级（真实星级 1~6）
    win_num: int | None = None      # 胜利次数；None = 该场次不提供（前端显示「不适用」）


class ArenaRankResult(BaseModel):
    """竞技场排行榜返回（结构化，前端自己画）"""

    ok: bool = False
    message: str = ""
    grand: bool = False
    group: int = 0                  # 场次
    page: int = 1
    rows: List[ArenaRankRow] = []


class ArenaUnit(BaseModel):
    """防守 / 作业里的一个角色：4 位 id + 星级（前端据此画头像与星星）"""

    unit_id: int = 1000
    rarity: int = 0          # 真实星级 1~6；0 = 未知（不画星，如缓存里的防守）
    battle_rarity: int = 0   # 战斗星级（调星后），0 = 没调过


class ArenaSolution(BaseModel):
    """查防守里的一条进攻解"""

    units: List[ArenaUnit] = []     # 进攻队伍角色（4 位 id + 星级）
    up: int = 0                     # 点赞数
    down: int = 0                   # 点踩数
    comment: str = ""               # 作业留言
    # 标签：'' 普通 / '近似解' / '高频解' / '不足四人随便打'
    label: str = ""
    team_type: str = "normal"


class ArenaDefenceResult(BaseModel):
    """查防守返回（结构化，前端自己画）

    `defence` 是防守方队伍（普通场 1 队、公主场最多 3 队），`solutions` 是对应的
    进攻作业。普通场只有一个 `rank`/`name`；公主场三队共用同一套 solutions。
    """

    ok: bool = False
    message: str = ""
    grand: bool = False
    rank: int = 0
    name: str = ""
    # 每支防守队伍的角色（4 位 id + 星级）
    defence: List[List[ArenaUnit]] = []
    solutions: List[ArenaSolution] = []


class ArenaProfileResult(BaseModel):
    """按游戏 ID 查玩家资料的返回（结构化，前端自己画）

    数据源同 autopcr 的【查玩家资料】（`profile/get_profile` + `target_viewer_id`）。
    """

    ok: bool = False
    message: str = ""
    viewer_id: int = 0              # 查询的玩家 ID
    name: str = ""                  # 昵称
    comment: str = ""               # 个人签名
    unit_id: int = 1000             # 代表角色头像 id（4 位）
    rarity: int = 0                 # 代表角色星级
    battle_rarity: int = 0
    team_level: int = 0             # 团队等级
    total_power: int = 0            # 总战力
    unit_num: int = 0               # 持有角色数
    open_story_num: int = 0         # 已解锁剧情数
    friend_num: int = 0             # 好友数
    arena_rank: int = 0
    arena_group: int = 0            # 竞技场场次
    grand_arena_rank: int = 0
    grand_arena_group: int = 0      # 公主竞技场场次
    tower_cleared_floor_num: int = 0        # 已通关塔层数
    tower_cleared_ex_quest_count: int = 0   # 已通关塔额外关卡数
    last_login_time: int = 0        # 上次登录时间（Unix 秒，0 = 未知）
    clan_name: str = ""             # 所在公会
    quest_normal: int = 0           # 普通关卡进度
    quest_hard: int = 0
    quest_very_hard: int = 0
    quest_byway: int = 0            # 支线关卡进度
    # 深域 5 属性（火/水/光/暗）的 clear_count
    talent: List[int] = []


# ---- 普通 EX 装备换装 ----
# 读（列表）走本地缓存不打游戏接口；写（更换）会登录游戏账号（顶号），前端先弹确认。


class ExEquipAttr(BaseModel):
    """EX 装备的一条属性。

    `percent=True` 的是**万分比**项（血量 / 物攻 / 魔攻 / 物防 / 魔防 / 物爆 / 法爆，
    与 autopcr `UnitAttribute.is_present` 一致），`value=700` 就是 +7%；`text` 已经
    换算好（"7%" / "12"），前端直接显示就行，别自己再除 100。
    """

    key: str = ""
    label: str = ""
    value: int = 0
    percent: bool = False
    text: str = ""


class ExEquipCopy(BaseModel):
    """同一件装备的**一份具体拷贝**（一个 serial_id 一件）。

    一个玩家手里同一件铜装可能十几把，列表里合并成一格，但「要动哪一把」不一样：
    空闲的随便穿，在别人身上的会把对方换下来。所以每一份都带上现在的位置。
    """

    serial_id: int = 0
    rank: int = 0
    enhancement_pt: int = 0
    wearer_unit_id: int = 0     # 0 = 空闲
    wearer_name: str = ""
    wearer_slot: int = 0
    wearer_kind: str = ""       # 'ex' 普通槽 / 'cb' 会战槽 / '' 空闲
    label: str = ""             # 「空闲」/「当前穿戴」/「佩可莉姆 槽2」


class ExEquipCandidate(BaseModel):
    """可选装备列表里的一项。

    **合并规则**：1~4 星装备（铜/银/金/粉）按「装备 + 星级」合并（同一件可能几十把）；
    **5 星彩装一件一行、不合并** —— 每件的词条都可能不一样（也可能都是「空」），
    合并了就没法挑词条，也没法只换你点的那一件。
    """

    equipment_id: int = 0
    name: str = ""
    category: int = 0
    category_name: str = ""
    rarity: int = 0
    rarity_name: str = ""
    clan_battle: bool = False
    star: int = 0
    max_star: int = 0
    icon: str = ""
    attrs: List[ExEquipAttr] = []
    # 5 星彩装的词条（同一属性已累加，最多 4 项）；铜/银/金/粉恒为空列表。
    # 空列表 + rarity=5 表示这件彩装的词条是「空」。
    sub_statuses: List[ExEquipSubStatus] = []
    # 唯一标识：彩装是「装备:星级:serial_id」（一件一行），1~4 星是「装备:星级:0」。
    # 前端用它判断「这行选中了没」，否则彩装同名几行会一起点亮。
    candidate_key: str = ""
    # 这一行代表的 serial（彩装 = 那一件；合并的铜/银/金/粉 = 0）
    serial_id: int = 0
    count: int = 0              # 这个组合一共有几份
    free_count: int = 0         # 其中空闲的几份
    equipped_here: bool = False # 是不是正穿在这个槽上
    copies: List[ExEquipCopy] = []
    # 只有 `current`（当前穿的那件）才带上这两个字段
    rank: int = 0


class ExEquipSlotInfo(BaseModel):
    """角色三个普通 EX 槽各自的类别（弹窗里用来显示「EX1 拳套 / EX2 衣服…」）。"""

    slot: int = 0
    category: int = 0
    category_name: str = ""


class ExEquipOptionsResult(BaseModel):
    """`/{group_id}/box/ex_equip/options` 的返回：某个角色某个槽能换的装备列表。"""

    ok: bool = False
    message: str = ""
    chara_id: int = 0
    chara_name: str = ""
    unit_id: int = 0            # 游戏里的 unit_id（chara_id * 100 + 1）
    slot: int = 0
    category: int = 0
    category_name: str = ""
    slots: List[ExEquipSlotInfo] = []
    current: ExEquipCandidate | None = None   # 这个槽现在穿的（没穿为 None）
    candidates: List[ExEquipCandidate] = []


class ExEquipSlotChange(BaseModel):
    """批量换装里要改的一个槽（`serial_id=0` 表示卸下）。"""

    slot: int
    serial_id: int = 0


class ExEquipChangeForm(BaseModel):
    """`/{group_id}/box/ex_equip/change` 的请求体。

    `unit_id` 是 4 位角色 ID（不是游戏 unit_id）。`changes` 是本次要改的槽
    （1~3 个）—— 网页端弹窗里挑好 EX1/EX2/EX3 后**一次提交**，后端只登录一次、
    只发一批 `unit/equip_ex`，不用一件一件换。没列进来的槽保持不动。
    """

    unit_id: int
    changes: List[ExEquipSlotChange] = []


class ExEquipSlotChangeResult(BaseModel):
    """批量换装里**一个槽**的结果。"""

    slot: int = 0
    serial_id: int = 0          # 换上去的（0 = 本槽是卸下）
    equipment_id: int = 0
    name: str = ""
    star: int = 0
    old_serial_id: int = 0      # 原来在这个槽里的
    swapped_chara_id: int = 0   # 与谁互换（0 = 没动别人）
    swapped_chara_name: str = ""


class ExEquipChangeResult(BaseModel):
    """普通 EX 换装的返回。

    ⚠️ 这是**写操作**：后端会登录你的游戏账号并真的改游戏里的 EX 槽（顶号），
    所以前端点之前必须先弹确认。目标装备在别人身上时会**互换**
    （对方槽里换成你这件），而不是把对方扒光。

    `slots` 是本次真正改动的那几个槽，网页端拿它就地更新详情面板。
    """

    ok: bool = False
    message: str = ""
    chara_id: int = 0
    chara_name: str = ""
    slots: List[ExEquipSlotChangeResult] = []
