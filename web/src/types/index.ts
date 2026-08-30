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
}

export interface ReportItem {
  dao_num: number
  names: string[]
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
  // 出刀监控人 QQ（0 = 未开启监控）
  monitor_user_id: number
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
}

// 出刀监控开关：action='on'|'off'，on 时带 account_id
export interface MonitorActionForm {
  action: 'on' | 'off'
  account_id?: number | null
}
