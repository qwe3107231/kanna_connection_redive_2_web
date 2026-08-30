import request from '@/utils/request'
import type {
  UserLogin,
  HomeResponse,
  DashboardResponse,
  NoticeResponse,
  ReportResponse,
  NoticeCacheModel,
  SpecialNoticeForm,
  CorrectDaoInfo,
  DaoInfo,
  MonitorAccountOption,
  MonitorActionForm,
} from '@/types'

/**
 * 登录
 */
export const login = (data: UserLogin) =>
  request.post<any>('/login', data)

/**
 * 登出（后端清理 cookie）
 */
export const logout = () => request.post<any>('/logout')

/**
 * 首页信息
 */
export const getHomeInfo = () =>
  request.get<HomeResponse>('/home').then((res) => res.data)

/**
 * 公会战仪表盘
 */
export const getDashboard = (groupId: number | string) =>
  request.get<DashboardResponse>(`/${groupId}/dashboard`).then((res) => res.data)

/**
 * 公会战通知列表
 */
export const getNoticeList = (groupId: number | string) =>
  request.get<NoticeResponse>(`/${groupId}/notice`).then((res) => res.data)

/**
 * 出刀报告
 */
export const getReport = (groupId: number | string) =>
  request.get<ReportResponse>(`/${groupId}/report`).then((res) => res.data)

/**
 * 设置通知（预约/申请/挂树/SL）
 */
export const setNotice = (data: NoticeCacheModel) =>
  request.post<string>('/set_notice', data).then((res) => res.data)

/**
 * 取消通知
 */
export const deleteNotice = (data: NoticeCacheModel) =>
  request.post<string>('/delete_notice', data).then((res) => res.data)

/**
 * 特殊取消通知（代人取消）
 */
export const deleteNoticeSpecial = (data: SpecialNoticeForm) =>
  request.post<string>('/delete_notice_special', data).then((res) => res.data)

/**
 * 修正出刀
 */
export const correctDao = (data: CorrectDaoInfo) =>
  request.post<string>('/correct_dao', data).then((res) => res.data)

/**
 * 出刀监控：当前登录QQ号自己绑定的可用角色账号列表
 * （方案A：别人绑定的账号不会返回，保证只能开自己的）
 */
export const getMonitorAccounts = (groupId: number | string) =>
  request.get<MonitorAccountOption[]>(`/${groupId}/monitor/accounts`).then((res) => res.data)

/**
 * 指定 BOSS 今日全部出刀记录（按时间倒序）
 * 用于 BOSS 卡片上的「出刀记录」弹窗
 */
export const getBossDao = (groupId: number | string, boss: number) =>
  request.get<DaoInfo[]>(`/${groupId}/boss_dao`, { params: { boss } }).then((res) => res.data)

// 档线单条记录
export interface RankLine {
  rank: number
  damage: number | null
  clan_name: string | null
  leader_name: string | null
  leader_viewer_id: number | null
  member_num: number | null
  reward?: { gem: number; coin: number; shard: number } | null
}

export interface RankLineResponse {
  clan_battle_id: number
  lines: (RankLine | null)[]
  my: RankLine | null
  default_ranks: number[]
}

// 查档线：本届会战指定排名的分数线，ranks 为自定义排名数组（仅会战期间有效）
export const getRankLines = (groupId: number | string, ranks?: Array<number | string>) =>
  request
    .get<RankLineResponse>(`/${groupId}/rank_lines`, {
      params: ranks && ranks.length ? { ranks: ranks.join(',') } : {},
    })
    .then((res) => res.data)

/**
 * 出刀监控：开/关
 * - action='off'：取消监控（本人或管理员）
 * - action='on'  ：开启监控，account_id 必填且必须为自己绑定的账号
 */
export const switchMonitor = (groupId: number | string, data: MonitorActionForm) =>
  request.post<any>(`/${groupId}/monitor`, data).then((res) => res.data)
