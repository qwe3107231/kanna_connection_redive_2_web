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
  BoxQueryResult,
  BoxCacheRefreshResult,
  SupportChangeForm,
  SupportChangeResult,
  ExEquipOptionsResult,
  ExEquipChangeForm,
  ExEquipChangeResult,
  ArenaSettingForm,
  ArenaStatus,
  GrandCacheRow,
  ArenaMonitorActionForm,
  ArenaRankResult,
  ArenaDefenceResult,
  ArenaProfileResult,
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
  // 档位类别（后端 clanbattle.base.rank_line_kind 判定）：
  // 'gold'/'silver'/'bronze' = 前三名（金/银/铜三色高亮）；
  // 'last' = 服务器实际榜单末位（绿色高亮）；'' / undefined = 普通档位。
  // 由后端算好下发，前端不自己按 rank 猜。
  kind?: 'gold' | 'silver' | 'bronze' | 'last' | ''
}

export interface RankLineResponse {
  clan_battle_id: number
  lines: (RankLine | null)[]
  my: RankLine | null
  default_ranks: number[]
  // 前三名档位（1、2、3 名），后端默认档位里天然包含
  head_ranks?: number[]
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

// ============ BOX / 助战 ============
// 网页端刻意不走插件那套「把整个 box 拼成一张大图」的出图逻辑：后端只返回结构化
// 角色数据（含头像地址），所以这几个接口就是普通的读库查询，不用放宽 timeout。
// 头像走 <img :src="unit.avatar"> 单独请求，由浏览器缓存。

/**
 * 个人 BOX 查询：自己 box 里有没有这个角色（name 传「所有」看整个 box）
 * - includeMissing=true（默认）时，没拥有的角色也会作为灰度占位一起返回
 */
export const queryBox = (
  groupId: number | string,
  name: string,
  includeMissing = true,
) =>
  request
    .get<BoxQueryResult>(`/${groupId}/box/query`, {
      params: { name, include_missing: includeMissing },
    })
    .then((res) => res.data)

/** 公会 BOX 查询：本群所有绑定成员里，谁有这个角色 */
export const queryClanBox = (groupId: number | string, name: string) =>
  request
    .get<BoxQueryResult>(`/${groupId}/box/clan`, { params: { name } })
    .then((res) => res.data)

/** 公会助战一览：本群缓存的公会战助战 */
export const queryClanSupport = (groupId: number | string, name: string) =>
  request
    .get<BoxQueryResult>(`/${groupId}/support/clan`, { params: { name } })
    .then((res) => res.data)

/** 我的助战：当前登录用户挂着的助战 */
export const queryMySupport = (groupId: number | string) =>
  request
    .get<BoxQueryResult>(`/${groupId}/support/mine`)
    .then((res) => res.data)

/**
 * 刷新缓存：**一次把「个人 BOX」和「本群公会助战」两份都刷了**
 * （等价于在群里先后发【刷新box缓存】和【刷新助战缓存】）。
 *
 * ⚠️ 会顶号：后端拿你自己绑定的账号登录游戏，正在游戏的你会被挤下线，
 * 所以调用前必须先弹确认。两份共用同一次登录，耗时和只刷一份差不多，放宽 timeout。
 */
export const refreshCache = (groupId: number | string) =>
  request
    .post<BoxCacheRefreshResult>(`/${groupId}/refresh`, null, { timeout: 90000 })
    .then((res) => res.data)

/**
 * 「我的助战」→【更换支援】：把选中的角色挂到指定栏位的助战
 * （等价于 QQ 群【上地下城支援】/【上公会战支援】/【上关卡支援】）。
 *
 * ⚠️ 写操作：后端会登录你的游戏账号并**真的改游戏里的支援设定**（顶号），
 * 所以调用前必须先弹确认。栏位满了会顶掉挂得最久的那一个。
 */
export const changeSupport = (
  groupId: number | string,
  data: SupportChangeForm,
) =>
  request
    .post<SupportChangeResult>(`/${groupId}/support/change`, data, { timeout: 90000 })
    .then((res) => res.data)

// ============ 普通 EX 装备换装（BOX 详情里的「普通 EX 槽」） ============

/**
 * 列出某个角色某个普通 EX 槽能换的装备（**纯读本地缓存，不登录、不顶号**）。
 *
 * 每一项都带属性、图标，以及「这件装备现在空闲 / 在谁身上」。
 * `slot` 是 1~3，`unitId` 是 4 位角色 ID。
 */
export const getExEquipOptions = (
  groupId: number | string,
  unitId: number,
  slot: number,
) =>
  request
    .get<ExEquipOptionsResult>(`/${groupId}/box/ex_equip/options`, {
      params: { unit_id: unitId, slot },
    })
    .then((res) => res.data)

/**
 * 更换普通 EX 装备（一次可以提交 1~3 个槽，`serial_id=0` 表示卸下那个槽）。
 *
 * ⚠️ 写操作：后端会登录你的游戏账号并**真的改游戏里的 EX 槽**（顶号），
 * 所以调用前必须先弹确认。目标装备在别人身上时会互换（把你这件换给对方），
 * 不会把对方扒光。
 */
export const changeExEquip = (
  groupId: number | string,
  data: ExEquipChangeForm,
) =>
  request
    .post<ExEquipChangeResult>(`/${groupId}/box/ex_equip/change`, data, {
      timeout: 90000,
    })
    .then((res) => res.data)

// ============ 竞技场 ============
// 排行榜 / 查防守 / 查 ID 都要借监控已登录的账号去打游戏接口，耗时更长。

/** 竞技场中心状态：监控在不在跑 + 两个提醒开关 */
export const getArenaStatus = (groupId: number | string) =>
  request.get<ArenaStatus>(`/${groupId}/arena/status`).then((res) => res.data)

/** 开关竞技场 / 公主竞技场的提醒 */
export const setArenaSetting = (
  groupId: number | string,
  data: ArenaSettingForm,
) =>
  request
    .post<{ ok: boolean; message: string }>(`/${groupId}/arena/setting`, data)
    .then((res) => res.data)

/** 竞技场「个人监控」开关：开启等价群里发【竞技场监控】，关闭等价【取消竞技场监控】。
 * ⚠️ 开启会登录你自己的游戏账号（顶号），前端点击前必须先弹确认。 */
export const switchArenaMonitor = (
  groupId: number | string,
  data: ArenaMonitorActionForm,
) =>
  request
    .post<{ message: string; loop_num: number }>(`/${groupId}/arena/monitor`, data, {
      timeout: 90000,
    })
    .then((res) => res.data)

/** 竞技场排行榜（每页 10 名，1~5 页）。返回结构化数据，由前端绘制。 */
export const getArenaRank = (
  groupId: number | string,
  page: number,
  grand: boolean,
) =>
  request
    .get<ArenaRankResult>(`/${groupId}/arena/rank`, {
      params: { page, grand },
      timeout: 90000,
    })
    .then((res) => res.data)

/** 查指定排名的防守阵容 / 作业。返回结构化数据，由前端绘制。 */
export const getArenaDefence = (
  groupId: number | string,
  rank: number,
  grand: boolean,
) =>
  request
    .get<ArenaDefenceResult>(`/${groupId}/arena/defence`, {
      params: { rank, grand },
      timeout: 90000,
    })
    .then((res) => res.data)

/** 按游戏 ID 查玩家资料（对应 autopcr 的【查玩家资料】）。需本群有竞技场监控在跑。 */
export const getArenaProfile = (
  groupId: number | string,
  viewerId: number | string,
) =>
  request
    .get<ArenaProfileResult>(`/${groupId}/arena/profile`, {
      params: { viewer_id: viewerId },
      timeout: 90000,
    })
    .then((res) => res.data)

/** 公主竞技场防守缓存（纯读库，不需要监控在跑） */
export const getArenaCache = (groupId: number | string) =>
  request.get<GrandCacheRow[]>(`/${groupId}/arena/cache`).then((res) => res.data)
