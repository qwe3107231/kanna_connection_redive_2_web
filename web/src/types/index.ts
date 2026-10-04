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
  damage: number
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

/** 纯文字返回（竞技场查 ID） */
export interface TextResult {
  ok: boolean
  message: string
  text: string
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
  /** 头像地址（相对路径，直接塞 <img :src>） */
  avatar: string
  /** 头像档位 1/3/6（后端按星级算好，前端不用管） */
  star: number
  /** 真实星级 1~6（拥有到几星） */
  rarity: number
  /**
   * 战斗星级（会战「调星」后的星级，0 = 没调过）。
   * 与 `rarity` 不同时，头像底部的星星会有一部分是亮蓝色（= 拥有但被调下去的），
   * 由后端合成头像时画好，前端不用管。
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
  /** 助战位：1/2 冒险，3/4 地下城，5/6 团队战·露娜塔（「我的助战」用） */
  support_position: number
  /**
   * 助战位所属分组（后端按 support_position 判定，前端别自己猜）：
   * `dungeon` 地下城 / `clan` 团队战·露娜之塔 / `adventure` 冒险 / `''` 认不出来
   */
  support_group: string
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
  /** 挂到了哪个助战位（1~6） */
  position: number
  /** 被顶掉的角色 ID（0 = 没有顶掉谁） */
  removed_unit_id: number
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
