// 通知类型枚举，对应后端 NoticeType
export enum NoticeType {
  subscribe = 0, // 预约
  tree = 1,      // 挂树
  apply = 2,     // 申请出刀
  dao = 3,       // 出刀伤害
  fighter = 4,   // 正在出刀
  sl = 5         // SL
}

// 出刀类型
export type DaoFlagType = '完整刀' | '尾刀' | '补偿刀'

// ============ 请求/响应模型 ============

export interface UserLogin {
  account: string
  password: string
}

// 修改网页端登录密码（登录后自助操作，需带旧密码）
export interface ChangePasswordForm {
  old_password: string
  new_password: string
}

// 服务器编号，对应后端 basedata.Platform
export const PLATFORM_NAMES: Record<number, string> = {
  0: '官服（B站）',
  1: '渠道服',
  2: '台服'
}

// 当前登录用户的游戏账号（全局：一个 QQ 一个号，所有群通用）
export interface GroupAccountInfo {
  // 有没有绑号（一个 QQ 只有一个游戏账号，所有群通用）
  bound: boolean
  account_id?: number | null
  name: string
  platform: number
  viewer_id?: number | null
}

// 网页端绑定游戏账号表单（三个服共用一张表单，按 platform 取对应字段）
export interface BindAccountForm {
  platform: number
  // 官服 platform=0：B站账号 + B站密码
  bili_account?: string
  bili_password?: string
  // 渠服 platform=1：login_id + token（token 也接受 "xxx yyy" 加密串）
  login_id?: string
  token?: string
  // 台服 platform=2
  short_udid?: string
  udid?: string
  viewer_id?: number | null
}

export interface BossInfoCounter {
  name: string
  id: number
  current_hp: number
  max_hp: number
  lap: number
  /** 该 BOSS 所在阶段：面字母（A/B/C…），后端没同步到时为 '' */
  stage: string
  /** 该 BOSS 所在阶段数字（1/2/3…），0 表示还没同步到 */
  stage_num: number
  subscribe: number
  apply: number
  fighter: number
  tree: number
}

export interface ClanInfo {
  group_id: number
  group_name?: string
  priority?: number
  // 该群能不能用游戏账号（账号是全局的，各群必然同值；字段保留以兼容旧逻辑）
  has_account?: boolean
  [key: string]: any
}

export interface HomeResponse {
  priority: number
  user_id: number
  name: string
  status: string
  saying: string
  clan: ClanInfo[]
  // 是否已绑定游戏账号（前端据此禁用预约/申请/挂树入口）
  has_account: boolean
  // 首页「游戏账号」卡的绑定 / 换绑 / 解绑入口用它
  account: GroupAccountInfo
}

export interface ReportItem {
  dao_num: number
  names: string[]
}

/**
 * 仪表盘「今日伤害排行」的一行（后端按玩家聚合今日出刀得出，已按伤害倒序）。
 * 替代了原来那张标题写「伤害占比」、实际画「按刀数分组的人数占比」的饼图。
 */
export interface DayDamageRank {
  name: string
  damage: number
  score: number
  /** 今日累计刀数（完整刀 1、尾刀/补偿刀 0.5） */
  dao: number
  /** 占全员总量的百分比（0-100，保留两位） */
  damage_rate: number
  score_rate: number
}

export interface DashboardResponse {
  priority: number
  clan_priority: number
  user_id: number
  name: string
  clan_name: string
  stage: string
  dao: number
  yesterday_dao: number
  rank: number
  state: string
  boss: BossInfoCounter[]
  report: ReportItem[]
  day_num: number
  // 最近 20 条出刀记录（按时间倒序，来自今日出刀）
  last_dao: DaoInfo[]
  // 今日伤害排行 Top 10（后端按玩家聚合今日出刀，已按伤害倒序）
  day_damage_rank: DayDamageRank[]
  // 今日全员总伤害 / 总分数 —— day_damage_rank 里各 rate 的分母
  day_damage_total: number
  day_score_total: number
  // 出刀监控人 QQ（0 = 未开启监控）
  monitor_user_id: number
  // 当前登录用户的游戏账号（全局，状态条上的绑定入口用它）
  account: GroupAccountInfo
}

export interface NoticeCacheModel {
  id?: number
  group_id: number
  notice_type: number
  user_id: number
  boss: number
  lap?: number
  text: string
  time?: number
}

export interface NoticeResponse {
  priority: number
  // 当前登录用户在本群的权限等级（后端 basedata.GroupPriority：0 只读 / 1 管理员 / 2 群主·群管 / 3 bot 主人）
  clan_priority: number
  // 有没有可用的游戏账号（账号是全局的，各群同值）
  has_account: boolean
  user_id: number
  subscribe: NoticeCacheModel[]
  apply: NoticeCacheModel[]
  tree: NoticeCacheModel[]
}

export interface DaoInfo {
  name: string
  /** 结算后计入的伤害（合刀尾刀会被截到 BOSS 剩余血量） */
  damage: number
  /** 游戏里显示的原始伤害；只有合刀尾刀会和 damage 不同（0 / 相等表示没有截断） */
  damage_raw: number
  score: number
  type: string
  date: number
  boss: number
  lap: number
  dao_id: number
  damage_rate: string
  score_rate: string
  dao: number
}

/** 某一面（阶段）的出刀伤害统计（BOSS 出刀记录弹窗顶部显示用）
 *  只统计完整刀：打满 90 秒、且伤害没有被结算截断（不含尾刀 / 补偿刀 / 合刀尾刀）。
 *  tail_count / comp_count / capped_count 是没计入的刀数，用于口径提示。 */
export interface BossDaoStat {
  count: number
  max: number
  min: number
  avg: number
  tail_count: number
  comp_count: number
  capped_count: number
}

/** /boss_dao 接口响应：完整出刀列表 + D 面统计（还没打到 D 面时 d_face 为 null） */
export interface BossDaoResponse {
  list: DaoInfo[]
  d_face: BossDaoStat | null
}

export interface ReportResponse {
  priority: number
  // 当前登录用户在本群的权限等级（同 NoticeResponse.clan_priority）
  clan_priority: number
  user_id: number
  name: string
  all: DaoInfo[]
  detail: DaoInfo[]
  me: DaoInfo[]
}

export interface SpecialNoticeForm {
  group_id: string
  boss: number
  notice_type: number
  lap: number
  user_id: number
}

export interface CorrectDaoInfo {
  type: DaoFlagType
  dao_id: number
  group_id: number
}

// 出刀监控：当前登录QQ号自己绑定的可选角色账号（方案A只返回自己的）
export interface MonitorAccountOption {
  account_id: number
  name: string
  platform: number
  viewer_id?: number | null
  // 归属群（现在恒为 0：一个 QQ 只有一个全局号）
  group_id: number
}

// 出刀监控开关：action='on'|'off'，on 时带 account_id
export interface MonitorActionForm {
  action: 'on' | 'off'
  account_id?: number | null
}

// ============ BOX / 助战 / 竞技场（首页快捷入口的两个新页面） ============

/** 出图类接口的统一返回（BOX / 助战 / 竞技场排行榜、查防守） */
export interface ImageResult {
  ok: boolean
  /** ok=false 时说明原因（缓存没刷新 / 角色不存在 / 竞技场监控没在跑…） */
  message: string
  count: number
  /** data:image/png;base64,... —— 直接塞进 <img :src> */
  image: string
}

/** 纯文字返回（保留给可能的纯文本接口） */
export interface TextResult {
  ok: boolean
  message: string
  text: string
}

/**
 * 5 星彩装的**一条词条**（究极炼成随机出来的那几条属性）。
 *
 * 数值由后端按 (属性, step) 查表算好，并且**同一属性会合并累加**：
 * 一件装备上两条物穿 → 只显示一条「物穿 10」，所以一件彩装最多 4 项。
 * `percent=true` 的显示成 "1.00%"，其余是固定值，`text` 可直接展示。
 *
 * 锁定与否不在这里：那是炼成时的事，和换装无关，不展示。
 */
export interface ExEquipSubStatus {
  /** 游戏属性编号（eParamType） */
  status: number
  key: string
  /** 属性中文名 */
  label: string
  percent: boolean
  /** 同一属性累加后的数值 */
  value: number
  /** 可直接展示（"1.00%" / "10"） */
  text: string
}

/**
 * BOX 详情里的**一个普通 EX 槽**（网页端专用，与上面那三个会战 `cb_ex_equip_*` 无关）。
 *
 * 槽位能穿的**类别由角色决定**（后端查角色槽位表），所以空槽也会带类别名 ——
 * 界面才能显示「EX 1 · 拳套 · 未装备」，否则用户不知道点开能选什么。
 * 数据来自本地缓存，`BoxUnit.ex_equip_known=false` 时 equipped 恒为 false，
 * 那表示「还没刷新过缓存」，不是「你真的没穿装备」。
 */
export interface BoxExEquip {
  /** 槽位 1~3 */
  slot: number
  /** 槽位能穿的类别（101~110 / 201~204 / 301~305） */
  category: number
  /** 类别中文名（后端给，前端不要自己映射） */
  category_name: string
  equipped: boolean
  equipment_id: number
  name: string
  /** 1 铜 / 2 银 / 3 金 / 4 粉 / 5 彩 */
  rarity: number
  rarity_name: string
  /** 按强化 PT 算出来的星级 */
  star: number
  /** 是不是会战专用（【行会】系列） */
  clan_battle: boolean
  /** 图标地址（走 box/ex_equip_icon，与会战 EX 共用一份缓存资源） */
  icon: string
  /** 5 星彩装的 4 条词条（1~4 星装备恒为空数组） */
  sub_statuses: ExEquipSubStatus[]
}

/**
 * BOX / 助战查询结果里的一个角色条目（Web 端专用）。
 *
 * QQ 群指令走的是插件那套 PIL 出图（整个 box 拼成一张大图），网页端不复用它 ——
 * 后端只返回数据，头像由 `/{groupId}/box/avatar/{unitId}` 单独出 PNG。
 * 同一个 unit_id 会在公会 BOX / 助战里出现多次，靠 player_name / pcrid 区分。
 */
export interface BoxUnit {
  unit_id: number
  /** 角色名（后端用 fromid 解析好的） */
  chara_name: string
  /**
   * 全部角色名：主名 + 日文 / 英文 / 社区别名（如 1070 的「似似花 / ネネカ /
   * Neneka / nnk / 448」）。只有个人 BOX 查询会带，用来做别名搜索；
   * 公会 BOX / 助战查询是空数组。
   */
  chara_names: string[]
  /** 玩家昵称（个人 BOX / 我的助战里就是你自己） */
  player_name: string
  /** 玩家游戏 ID */
  pcrid: number
  /**
   * 是否已拥有。
   * false = 后端给的「未拥有」占位条目（只有 id / 角色名 / 头像），前端灰度显示 ——
   * 个人 BOX 查「所有」时靠它一眼看出缺哪些角色。
   */
  owned: boolean
  /**
   * 头像地址（相对路径，直接塞 <img :src>）。
   *
   * 后端拼的 URL 带 `star` / `rarity` / `battle_rarity`：传了后两个，后端会把星星
   * 直接烤进 PNG（QQ 端出图、竞技场那边还在用这套）。BOX / 助战页现在改成前端画
   * 游戏样式的头像（见 `components/GameUnitAvatar.vue`），那边会先把这两个参数去掉、
   * 只用干净底图，所以别直接拿这个 URL 当「已经画好星级」的图用。
   */
  avatar: string
  /** 头像档位 1/3/6（后端按星级算好，前端不用管） */
  star: number
  /** 真实星级 1~6（拥有到几星） */
  rarity: number
  /**
   * 战斗星级（会战「调星」后的星级，0 = 没调过）。
   * BOX / 助战头像左下角显示的星级就用它（没调过时回退到 `rarity`；6★ 固定粉色第 6 颗），
   * 和会战里实际生效的星级一致。
   */
  battle_rarity: number
  level: number
  rank: number
  /** 专武等级，-1 = 未装备 */
  unique_level: number
  unique_level2: number
  /**
   * 好感等级。只有个人 BOX / 我的助战有（后端 `PlayerUnit.love_level`）；
   * 游戏接口不给助战的好感等级，所以助战恒为 0。
   */
  love_level: number
  /**
   * 好感加成文字（如「物理攻击力：1055，回复量上升：35」）。只有助战有
   * （后端 `SupportUnit.special_attribute`）；个人 BOX 拿不到。
   * 详情里平时只显示「N 级 / 加成」短标签，点开才看完整文字。
   */
  special_attribute: string
  union_burst: number
  main_1: number
  main_2: number
  ex: number
  equip_1: string
  equip_2: string
  equip_3: string
  equip_4: string
  equip_5: string
  equip_6: string
  cb_ex_equip_1: number
  cb_ex_equip_2: number
  cb_ex_equip_3: number
  cb_ex_equip_1_level: number
  cb_ex_equip_2_level: number
  cb_ex_equip_3_level: number
  /** 会战 EX 装备图标地址（后端拼好；id 为 0 时是空串） */
  cb_ex_equip_1_icon: string
  cb_ex_equip_2_icon: string
  cb_ex_equip_3_icon: string
  /**
   * 普通 EX 槽（3 个，含类别名；会战 EX 行为完全不受影响）。
   * 表里查不到这个角色的槽位时是空数组，前端整块隐藏。
   */
  ex_equips: BoxExEquip[]
  /**
   * 有没有读到这个玩家的普通 EX 缓存。
   * false = 还没刷过【刷新缓存】（或助战缓存里没有这份数据），
   * 这时槽位会显示成「未装备」，但那是**未知**而不是真的空。
   */
  ex_equip_known: boolean
  /**
   * 这条角色条目是不是**当前登录用户自己的**。
   *
   * 只有自己的才允许点普通 EX 槽去换装 —— 换装是写操作、永远打在当前登录账号上，
   * 而在公会 BOX / 公会助战里看到的可能是别人的 EX 搭配，点它会张冠李戴。
   */
  ex_equip_editable: boolean
  /** 助战位：1/2 冒险，3/4 地下城，5/6 团队战·露娜塔（「我的助战」用） */
  support_position: number
  /**
   * 助战位所属分组（后端按 support_position 判定，前端别自己猜）：
   * `dungeon` 地下城 / `clan` 团队战·露娜之塔 / `adventure` 冒险 / `''` 认不出来
   */
  support_group: string
}

/**
 * 个人 BOX 练度条里的**一个属性强化**（火 / 水 / 风 / 光 / 暗，固定 5 条）。
 *
 * 数据来自游戏 `load/index` 的 `princess_knight_info.talent_level_info_list`：
 * `point` 是累计点数，`level` 是后端按阈值表换算出来的**属性等级** ——
 * 界面上「火 440」里的 440 就是它。
 */
export interface BoxEnhanceTalent {
  /** 属性编号（1~5，与游戏 talent_id 一致） */
  talent_id: number
  /** 属性中文名（后端给，前端不要自己映射） */
  name: string
  /** 属性等级（换算后的；0 = 还没读到） */
  level: number
  /** 该属性的累计点数 */
  point: number
}

/**
 * 职阶（职能）专精里**一个板块**的进度。一个职阶固定 4 个板块。
 *
 * 后端把 `unit_role_list` 的 `slot_level_n` / `enhance_level_n` 拍平成这个结构：
 * `slot_level_n = 0` 就是没解锁（`unlocked=false`），界面上显示成 `-`。
 */
export interface BoxEnhanceRoleSlot {
  /** 板块序号 1~4 */
  slot: number
  /** 板块等级 0~5（0 = 没解锁） */
  level: number
  /** 星级 0~5 */
  star: number
  /** 该板块解锁了没（false 时界面上是 `-`） */
  unlocked: boolean
}

/** 练度条里的**一个职阶**（攻击型 / 破防型 / …，固定 8 条，每条 4 个板块） */
export interface BoxEnhanceRole {
  /** 职阶编号（与游戏 unit_role_id 一致） */
  role_id: number
  /** 职阶中文名（后端给，前端不要自己映射） */
  name: string
  /** 固定 4 个板块 */
  slots: BoxEnhanceRoleSlot[]
}

/**
 * 属性技能里「最后一个合流节点之后」的一条线（左 / 中 / 右）。
 *
 * 口径与 autopcr【查深域】的 `左2[5级]` 一致：这条线上点了 `count` 个节点，
 * 其中最高等级是 `level`。
 */
export interface BoxEnhanceSkillBranch {
  /** 左 / 中 / 右（认不出来的 pos_x 是「未知」） */
  pos: string
  /** 这条线已点的节点数 */
  count: number
  /** 这条线上最高的节点等级 */
  level: number
}

/**
 * 属性技能进度（练度条上的「属性技能」那一行）。
 *
 * 游戏只给「最后一次强化的那一页」的节点列表，后端配上导出的节点表还原成
 * `第3页 第12合流 左2[5级]/中1[3级] (余123)` —— 与 autopcr 的【查深域】同一套口径。
 * `branches` 为空时看 `last_joined_level`（最后一个合流节点自己的等级）；
 * `leftover` 是星幽碎片剩余。没点过属性技能时整个 `skill` 是 null。
 */
export interface BoxEnhanceSkill {
  /** 第几页（0 = 节点表里查不到） */
  page: number
  /** 第几合流 */
  joined_count: number
  /** 没有后续分支时：最后一个合流节点的等级 */
  last_joined_level: number
  /** 合流之后的左 / 中 / 右三条线 */
  branches: BoxEnhanceSkillBranch[]
  /** 星幽碎片剩余 */
  leftover: number
}

/**
 * 个人 BOX 的**练度快照**（查询框下方那条 MP等级 / 属性强化 / 职介等级）。
 *
 * 只有「个人 BOX」查询（`/{groupId}/box/query`）会带这个字段：公会 BOX / 助战 /
 * 好友查的都是别人的数据，没有练度。还没刷过缓存、或后端是没带这个字段的旧版本时，
 * `BoxQueryResult.enhance` 会整个缺失 / 为 null，前端要退化成一行灰字提示，不能报错。
 */
export interface BoxPlayerEnhance {
  /**
   * 大师技能（MP）等级 —— 社区里说的「MP23」= 点到第 23 个节点，
   * 所以后端直接把 `team_skill_latest_node.node_id` 当等级用。0 = 未知。
   */
  mp_level: number
  /** 属性强化：固定 5 条（火 / 水 / 风 / 光 / 暗） */
  talents: BoxEnhanceTalent[]
  /** 职阶等级：固定 8 条（攻击型 / 破防型 / 增益型 / 减益型 / 强化型 / 治疗型 / 坦克型 / 干扰型） */
  roles: BoxEnhanceRole[]
  /** 属性技能（第几页 / 第几合流 / 左中右三条线 / 余多少星幽碎片）；没点过是 null */
  skill?: BoxEnhanceSkill | null
  /** 快照时间（Unix 秒，0 = 未知） */
  updated_at: number
}

/** BOX / 助战查询的返回（替代原来的整图 ImageResult） */
export interface BoxQueryResult {
  ok: boolean
  /** ok=false 时说明原因（缓存没刷新 / 角色不存在…） */
  message: string
  /** units 总条数（含未拥有的占位） */
  count: number
  /** 其中已拥有 */
  owned_count: number
  /** 其中未拥有（灰度占位） */
  missing_count: number
  units: BoxUnit[]
  /**
   * 练度快照（MP等级 / 属性强化 / 职介等级），**只有个人 BOX 查询会带**。
   * 缺字段 / null = 还没刷过缓存（或后端还是没这个字段的旧版本），
   * 个人 BOX 的练度条会退化成一行「点【刷新缓存】后显示」的灰字。
   */
  enhance?: BoxPlayerEnhance | null
}

/**
 * 「刷新缓存」按钮的返回。
 *
 * 一次把「个人 BOX」和「本群公会助战」两份缓存都刷新，等价于在群里先后发
 * 【刷新box缓存】和【刷新助战缓存】—— 后端会**真的登录游戏账号**（顶号），
 * 所以点之前要先给用户确认。两份只登录一次，不会比原来更慢。
 * 刷新逻辑与 QQ 指令共用同一份代码。
 */
export interface BoxCacheRefreshResult {
  ok: boolean
  /** 可直接展示的提示文案（成功条数 / 失败原因都在里面） */
  message: string
  /** 固定 'all'：一次刷新「个人 BOX + 本群公会助战」两份缓存 */
  kind: string
  /** 本次写入的条目数合计 */
  count: number
  /** 其中个人 BOX 的角色数 */
  box_count: number
  /** 其中公会助战的条数 */
  support_count: number
  /**
   * 公会助战那半失败的提示（例如「现在不是会战期间」）。
   * 为空 = 两份都刷成了；非空时 `ok` 仍是 true —— 个人 BOX 已经刷新成功。
   */
  support_error: string
}

/**
 * 「我的助战」→【更换支援】的请求体。
 *
 * `mode` 是游戏里的支援栏位，和 QQ 端三条指令一一对应：
 * 1 地下城（【上地下城支援】）/ 2 团队战·露娜之塔（【上公会战支援】）/
 * 3 关卡·冒险（【上关卡支援】）。`unit_id` 是要挂上去的角色 ID。
 */
export interface SupportChangeForm {
  unit_id: number
  mode: number
  /**
   * 战斗星级（会战「调星」）：3 / 4 / 5 = 把战斗星级调到该档，**不传 = 不调整**。
   *
   * 只有 5 星角色（`BoxUnit.rarity === 5`）能调 —— 6★ 已经满星、低星还没到可调档位，
   * 后端会直接拒绝，所以前端只在 rarity === 5 时才给选项。传了 star 且角色**已经挂在
   * 目标支援位**时，后端只调星级、不重复挂支援（见 `SupportChangeResult.position`）。
   */
  star?: number
}

/**
 * 「更换支援」的返回。
 *
 * ⚠️ 这是**写操作**：后端会登录你的游戏账号并真的改游戏里的支援设定（顶号），
 * 正在玩游戏的你会被挤下线，所以点之前必须先弹确认。栏位满了会顶掉挂得最久的
 * 那一个（游戏侧规则：挂满 30 分钟后才允许换）。
 */
export interface SupportChangeResult {
  ok: boolean
  /** ok=false 时说明原因（没绑号 / 已在支援中 / 等级过低 / 栏位挂满不足 30 分钟…） */
  message: string
  /** 1 地下城 / 2 团队战·露娜塔 / 3 关卡（冒险） */
  mode: number
  /** 本次挂上去的角色 ID */
  unit_id: number
  /** 挂到了哪个助战位（1~6）。只调星级时也是角色所在的那个支援位 */
  position: number
  /** 被顶掉的角色 ID（0 = 没有顶掉谁） */
  removed_unit_id: number
  /** 本次实际调整到的战斗星级（3/4/5；**0 = 这次没调星级**） */
  star: number
  /** 调整前的战斗星级（**0 = 这次没调星级**） */
  old_star: number
}

/** 竞技场提醒开关（只改这两个开关，开 / 关监控仍然只在 QQ 群里做） */
export interface ArenaSettingForm {
  jjc_notice?: boolean
  grand_notice?: boolean
}

export interface ArenaStatus {
  /** 本群有没有正在运行的竞技场监控 */
  running: boolean
  jjc_notice: boolean
  grand_notice: boolean
  jjc_rank: number
  jjc_group: number
  grand_rank: number
  grand_group: number
  /** 监控编号 */
  loop_num: number
  /** 监控人 QQ（0 = 没有监控在跑） */
  monitor_user_id: number
  /** 当前登录用户是不是监控人本人 */
  is_monitor: boolean
}

/** 公主竞技场防守缓存的一行 */
export interface GrandCacheRow {
  /** 对手玩家 ID */
  pcrid: number
  grand_id: number
  /** 防守位置 1/2/3 */
  row: number
  /** 对战时间（Unix 秒） */
  vs_time: number
  units: number[]
  names: string[]
}

/** 竞技场「个人监控」开关：等价群里发【竞技场监控】/【取消竞技场监控】 */
export interface ArenaMonitorActionForm {
  action: 'on' | 'off'
}

/** 竞技场排行榜的一行（网页端绘制，替代原来拼好的 PNG） */
export interface ArenaRankRow {
  rank: number
  name: string
  viewer_id: number
  /** 头像角色 ID（4 位，喂给 box/avatar 接口） */
  unit_id: number
  /** 头像角色真实星级 1~6 */
  rarity: number
  /** 胜利次数；null = 该场次不提供（显示「不适用」） */
  win_num: number | null
}

/** 竞技场排行榜返回（结构化，前端自己画） */
export interface ArenaRankResult {
  ok: boolean
  message: string
  grand: boolean
  /** 场次 */
  group: number
  page: number
  rows: ArenaRankRow[]
}

/** 防守 / 作业里的一个角色：4 位 id + 星级（前端据此画头像与星星） */
export interface ArenaUnit {
  unit_id: number
  /** 真实星级 1~6；0 = 未知（不画星，如缓存里的防守） */
  rarity: number
  /** 战斗星级（调星后），0 = 没调过 */
  battle_rarity: number
}

/** 查防守里的一条进攻解 */
export interface ArenaSolution {
  /** 进攻队伍角色（4 位 id + 星级） */
  units: ArenaUnit[]
  up: number
  down: number
  comment: string
  /** '' 普通 / '近似解' / '高频解' / '不足四人随便打' */
  label: string
  team_type: string
}

/** 查防守返回（结构化，前端自己画） */
export interface ArenaDefenceResult {
  ok: boolean
  message: string
  grand: boolean
  rank: number
  name: string
  /** 防守队伍（普通场 1 队、公主场最多 3 队），每队是角色（4 位 id + 星级） */
  defence: ArenaUnit[][]
  solutions: ArenaSolution[]
}

/** 玩家资料里挂的一个助战角色（游戏 `profile/get_profile` 自带） */
export interface ArenaSupportUnit {
  /** 分组：friend 好友支援 / dungeon 地下城支援 / clan 团队战支援 */
  group: 'friend' | 'dungeon' | 'clan'
  /** 中文分组名（后端给，前端直接用） */
  group_name: string
  /** 游戏侧助战位（同组内 1/2） */
  position: number
  /** 4 位角色 ID */
  unit_id: number
  chara_name: string
  /** 拥有星级（头像叠星用） */
  rarity: number
  /** 战斗星级（会战调星后；0 = 没调过） */
  battle_rarity: number
  level: number
  /** 品级（promotion_level） */
  rank: number
}

/** 按游戏 ID 查玩家资料的返回（结构化，前端自己画） */
export interface ArenaProfileResult {
  ok: boolean
  message: string
  /** 查询的玩家 ID */
  viewer_id: number
  name: string
  /** 个人签名 */
  comment: string
  /** 代表角色头像 id（4 位）+ 星级 */
  unit_id: number
  rarity: number
  battle_rarity: number
  team_level: number
  total_power: number
  unit_num: number
  open_story_num: number
  friend_num: number
  arena_rank: number
  /** 竞技场场次 */
  arena_group: number
  /** 竞技场创建日（Unix 秒，0 = 未知） */
  arena_time: number
  grand_arena_rank: number
  /** 公主竞技场场次 */
  grand_arena_group: number
  /** 公主竞技场创建日（Unix 秒，0 = 未知） */
  grand_arena_time: number
  tower_cleared_floor_num: number
  tower_cleared_ex_quest_count: number
  /** 上次登录时间（Unix 秒，0 = 未知） */
  last_login_time: number
  clan_name: string
  quest_normal: number
  quest_hard: number
  quest_very_hard: number
  /** 支线关卡进度 */
  quest_byway: number
  /** 深域 5 属性（火/水/风/光/暗）的 clear_count */
  talent: number[]
  /** 对方挂的助战（好友支援 / 地下城支援 / 团队战支援）；没挂就是空数组 */
  support_units: ArenaSupportUnit[]
}

// ============ 普通 EX 装备换装（BOX 详情里的「普通 EX 槽」） ============

/**
 * EX 装备的一条属性。
 *
 * `percent=true` 的是**万分比**项（血量 / 物攻 / 魔攻 / 物防 / 魔防 / 物爆 / 法爆）：
 * `value=700` 就是 +7%，`text` 后端已经换算好，前端直接显示，别再自己除。
 */
export interface ExEquipAttr {
  key: string
  label: string
  value: number
  percent: boolean
  /** 可直接展示的文案（"7%" / "12"） */
  text: string
}

/** 同一件装备的一份具体拷贝（一个 serial_id 一件） */
export interface ExEquipCopy {
  serial_id: number
  rank: number
  enhancement_pt: number
  /** 0 = 空闲 */
  wearer_unit_id: number
  wearer_name: string
  wearer_slot: number
  /** 'ex' 普通槽 / 'cb' 会战槽 / '' 空闲 */
  wearer_kind: string
  /** 「空闲」/「当前穿戴」/「佩可莉姆 槽2」 */
  label: string
}

/** 可选装备列表里的一项 */
export interface ExEquipCandidate {
  equipment_id: number
  name: string
  category: number
  category_name: string
  /** 1 铜 / 2 银 / 3 金 / 4 粉 / 5 彩 */
  rarity: number
  rarity_name: string
  clan_battle: boolean
  star: number
  max_star: number
  icon: string
  attrs: ExEquipAttr[]
  /**
   * 5 星彩装的词条（同一属性已累加，最多 4 项）；铜/银/金/粉恒为空数组。
   * **空数组 + rarity=5** 表示这件彩装的词条是「空」。
   */
  sub_statuses: ExEquipSubStatus[]
  /**
   * 这一行的**唯一标识**。彩装是 `装备:星级:serial_id`（一件一行，互不干扰），
   * 1~4 星装备是 `装备:星级:0`（合并成一行）。
   *
   * 前端拿它做「这行选中了没」—— 彩装同装备同星级会有多行，没有它就点一行亮一片。
   */
  candidate_key: string
  /** 这一行代表的 serial（彩装 = 那一件；合并的铜/银/金/粉 = 0）。
   *  对 `current`（当前穿的那件）来说就是它自己的 serial。 */
  serial_id: number
  /** 这个组合一共有几份 */
  count: number
  /** 其中空闲的几份 */
  free_count: number
  /** 是不是正穿在这个槽上 */
  equipped_here: boolean
  copies: ExEquipCopy[]
  /** 只有 `current`（当前穿的那件）会带 */
  rank: number
}

/** 角色三个普通 EX 槽各自的类别 */
export interface ExEquipSlotInfo {
  slot: number
  category: number
  category_name: string
}

/** 某个角色某个普通 EX 槽能换的装备列表（纯读缓存，不登录） */
export interface ExEquipOptionsResult {
  ok: boolean
  message: string
  chara_id: number
  chara_name: string
  unit_id: number
  slot: number
  category: number
  category_name: string
  slots: ExEquipSlotInfo[]
  current: ExEquipCandidate | null
  candidates: ExEquipCandidate[]
}

/** 批量换装里要改的一个槽（`serial_id=0` 表示卸下） */
export interface ExEquipSlotChange {
  slot: number
  serial_id: number
}

/**
 * 更换普通 EX 装备的请求体（`unit_id` 是 4 位角色 ID）。
 *
 * `changes` 是本次要改的槽（1~3 个）：弹窗里挑好 EX1/EX2/EX3 后**一次提交**，
 * 后端只登录一次、只发一批 `unit/equip_ex`，不用一件一件换。
 * 没列进来的槽保持不动。
 */
export interface ExEquipChangeForm {
  unit_id: number
  changes: ExEquipSlotChange[]
}

/** 批量换装里一个槽的结果 */
export interface ExEquipSlotChangeResult {
  slot: number
  /** 换上去的（0 = 本槽是卸下） */
  serial_id: number
  equipment_id: number
  name: string
  star: number
  old_serial_id: number
  /** 与谁互换（0 = 没动别人） */
  swapped_chara_id: number
  swapped_chara_name: string
}

/**
 * 更换普通 EX 装备的返回。
 *
 * ⚠️ 写操作：后端会登录你的游戏账号并真的改游戏里的 EX 槽（顶号），
 * 所以点之前必须先弹确认。目标装备在别人身上时会**互换**（把你这件换给对方）。
 */
export interface ExEquipChangeResult {
  ok: boolean
  message: string
  chara_id: number
  chara_name: string
  /** 本次真正改动的那几个槽，前端拿它就地更新详情面板 */
  slots: ExEquipSlotChangeResult[]
}

// ============ 好友（BOX / 助战页的「好友」页签） ============

/**
 * 好友列表里的一行（对应游戏 `friend/list` 接口）。
 *
 * 头像 `avatar` 由后端拼好，**不带 rarity 参数** —— 好友列表照游戏里那样
 * 不画星级（`avatar_rarity` 只是随接口带过来，前端不拿它画星）。
 * `last_login_time` 是 Unix 秒（0 = 未知）。
 * 用户明确要求不显示称号，所以后端不再下发称号字段，这里也没有。
 */
export interface FriendRow {
  viewer_id: number
  name: string
  level: number
  total_power: number
  /** 该好友自己的好友数 */
  friend_num: number
  /** 最后登录时间（Unix 秒，0 = 未知） */
  last_login_time: number
  /** 代表角色 4 位 ID */
  avatar_unit_id: number
  /** 代表角色星级（前端不用画星） */
  avatar_rarity: number
  /** 头像地址（后端已拼好，不带 rarity 参数 → 无星级） */
  avatar: string
}

/**
 * 好友列表的返回。
 *
 * 读缓存（`GET friend/list`）与刷新 / 添加 / 解除好友（都会登录游戏账号、顶号）
 * 返回的都是这个结构，所以前端每次拿到都可以直接整个替换掉列表。
 */
export interface FriendListResult {
  ok: boolean
  message: string
  count: number
  /** 好友上限（固定 40） */
  limit: number
  /** 上次刷新时间（Unix 秒，0 = 从未刷新） */
  updated_at: number
  friends: FriendRow[]
}

/**
 * 好友申请列表（游戏「好友管理」界面的两个页签）。
 *
 * 这两份名单游戏接口里是**实时数据、不落本地缓存**，所以查看 / 同意 / 拒绝 /
 * 撤回都会临时登录游戏账号（顶号），前端调用前先弹确认。
 */
export interface FriendRequestsResult {
  ok: boolean
  message: string
  /** 待审核列表：别人申请加我好友、等我同意 / 拒绝 */
  pending: FriendRow[]
  /** 申请中的名单：我发出去、对方还没处理（可以撤回） */
  requested: FriendRow[]
}

// ===================== 排刀（BOX/助战 →「排刀」页签） =====================

/**
 * 画头像需要的最小角色结构。
 *
 * `GameUnitAvatar` 原来直接吃 `BoxUnit`；排刀接口只返回画头像要用的几个字段，
 * 所以抽一个最小接口。`BoxUnit` / `ArrangeUnit` 在结构上都满足它。
 */
export interface AvatarUnit {
  unit_id: number
  chara_name: string
  avatar: string
  /** 有数据（自己拥有或助战可借）→ 画品级框 / 星级；false = 灰色占位 */
  owned: boolean
  rarity: number
  battle_rarity: number
  rank: number
}

/** 排刀作业里的一个角色 */
export interface ArrangeUnit extends AvatarUnit {
  level: number
  /** 玩家自己的 BOX 里有没有这个角色（判断「缺几个」用） */
  player_owned: boolean
  /** 本群公会助战里有没有这个角色（缺的角色能不能借） */
  from_support: boolean
  /** 助战提供者昵称；自己拥有的角色就是自己的昵称 */
  player_name: string
}

/** 未识别角色手动匹配用的角色选项 */
export interface ArrangeChara {
  unit_id: number
  name: string
  /** 全部角色名 / 别名（中文主名、日文、英文、社区别名），供下拉框搜索 */
  aliases: string[]
}

/** 表格里的一条作业 */
export interface ArrangeTeam {
  id: number
  /** 表格里的原始写法，例如「B1 狼 病娇 战狼 军病 八筒 90s」 */
  raw: string
  stage: string
  bosses: number[]
  /** 和表格一致的标签：B12345 / C45 / D1 */
  boss_label: string
  /** 给人看的说明：B面 1-5王 / C面 4王、5王 */
  boss_text: string
  units: number[]
  unit_names: string[]
  /** 没认出来的角色名（非空时这条作业不可用） */
  unknown_names: string[]
  /** return = 补偿刀时间；damage = 伤害；both = 同时有伤害和补偿时间 */
  value_kind: 'return' | 'damage' | 'both' | string
  value: number
  value_label: string
  /** 伤害（亿）；0 = 没写伤害 */
  damage_value: number
  /** 补偿时间（秒）；0 = 没写补偿时间 */
  return_seconds: number
  source_row: number
  source_col: number
}

/** 排刀页面主数据：表格作业 + 当前用户 BOX/助战情况 */
export interface ArrangeData {
  ok: boolean
  message: string
  url: string
  tab: string
  aliases: Record<string, string>
  /** 上次成功抓取表格的时间（Unix 秒，0 = 从未抓取） */
  fetched_at: number
  entry_count: number
  teams: ArrangeTeam[]
  /** key 是 unit_id 的字符串形式 */
  units: Record<string, ArrangeUnit>
  owned_count: number
  support_count: number
  /** 本群助战里出现过的角色 ID（去重） */
  support_ids: number[]
  /**
   * true = 助战可以借全部角色（默认）；false = 只能借 support_ids 里的角色。
   * 旧后端没有这个字段时前端按 true 处理。
   */
  support_all: boolean
  /** 全表没认出来的角色名（去重，用于提示补别名） */
  unknown_names: string[]
  /** 未识别角色手动匹配用的全角色列表；没有未识别角色时为空 */
  charas: ArrangeChara[]
  /** true = 本次抓取失败，显示的是上次缓存 */
  cached: boolean
}

/** 排刀表格地址 / 角色别名配置 */
export interface ArrangeConfig {
  url: string
  aliases: Record<string, string>
}

export interface ArrangeConfigForm {
  url: string
  aliases: Record<string, string>
}
