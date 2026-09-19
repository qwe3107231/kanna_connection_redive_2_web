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

// 当前登录用户在本群生效的游戏账号
// 取值规则：本群绑定的号优先，本群没绑就回退到全局号（QQ 私聊绑定的那个）
export interface GroupAccountInfo {
  // 本群有没有可用的号（本群号或全局号）
  bound: boolean
  // true = 本群专用号；false = 回退到 QQ 私聊绑定的全局号
  is_group_bound: boolean
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
  // 本群有没有可用的游戏账号（后端按群算：本群绑定优先，回退全局号）
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
  // 当前登录用户在本群生效的游戏账号（状态条上的绑定入口用它）
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
  // 本群有没有可用的游戏账号（本群绑定优先，回退全局号）
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
  // 归属群（0 = 全局号，即 QQ 私聊绑定的那个）
  group_id: number
  // 是否为本群专用号（false 表示是全局号）
  is_group_bound: boolean
}

// 出刀监控开关：action='on'|'off'，on 时带 account_id
export interface MonitorActionForm {
  action: 'on' | 'off'
  account_id?: number | null
}
