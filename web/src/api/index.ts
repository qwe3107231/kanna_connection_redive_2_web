import request from '@/utils/request'
import type {
  UserLogin,
  ChangePasswordForm,
  BindAccountForm,
  GroupAccountInfo,
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
 * 修改网页端登录密码（需带旧密码；成功后其他设备上的登录态会失效）
 */
export const changePassword = (data: ChangePasswordForm) =>
  request.post<string>('/change_password', data).then((res) => res.data)

/**
 * 首页信息
 */
export const getHomeInfo = () =>
  request.get<HomeResponse>('/home').then((res) => res.data)

/**
 * 绑定游戏账号（**全局生效**，一个 QQ 一个号，换公会 / 进新群都不用重绑）
 * URL 里的 groupId 现在只用于访问校验，不决定这条绑定写到哪
 * 重复绑定 = 覆盖原来那一条；三个服共用一张表单，按 platform 取字段
 */
export const bindAccount = (groupId: number | string, data: BindAccountForm) =>
  request
    .post<GroupAccountInfo>(`/${groupId}/bind_account`, data)
    .then((res) => res.data)

/**
 * 解绑当前登录用户的游戏账号
 * 账号绑定是全局的（一个 QQ 一个号），所以解绑对所有群一起生效
 */
export const unbindAccount = (groupId: number | string) =>
  request.post<string>(`/${groupId}/unbind_account`).then((res) => res.data)

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
  // 本次结果是否来自后端本地缓存（游戏侧档线每个整点 / 30 分各刷新一次，
  // 后端按「刷新槽位」缓存：同一轮内直接复用，跨轮必重抓）
  cached: boolean
  // 抓取失败、退回使用过期缓存
  stale: boolean
  // 出刀监控是否在运行（只有它在跑时后端才允许去游戏侧抓档线）
  monitor_running: boolean
  // 这份数据的抓取时间（Unix 秒，0 表示未知）
  updated_at: number
}

/**
 * 查档线：本届会战指定排名的分数线，ranks 为自定义排名数组（仅会战期间有效）
 * - 不传 force：后端优先返回本地缓存，缓存过期才会真的去游戏侧抓一次
 * - force=true：忽略缓存强制抓取（仅在出刀监控运行中才允许）
 */
export const getRankLines = (
  groupId: number | string,
  ranks?: Array<number | string>,
  force = false,
) =>
  request
    .get<RankLineResponse>(`/${groupId}/rank_lines`, {
      params: {
        ...(ranks && ranks.length ? { ranks: ranks.join(',') } : {}),
        ...(force ? { force: true } : {}),
      },
    })
    .then((res) => res.data)

/**
 * 出刀监控：开/关
 * - action='off'：取消监控（本人或管理员）
 * - action='on'  ：开启监控，account_id 必填且必须为自己绑定的账号
 */
export const switchMonitor = (groupId: number | string, data: MonitorActionForm) =>
  request.post<any>(`/${groupId}/monitor`, data).then((res) => res.data)
