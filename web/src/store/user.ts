import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type { ClanInfo } from '@/types'
import { getHomeInfo, login as apiLogin, logout as apiLogout } from '@/api'

// 持久化的 key —— 用于跨刷新记住"本地登录标志"。真正的鉴权由后端 cookie 完成。
const PERSIST_KEY = 'kanna.auth.state.v1'

interface PersistState {
  isLoggedIn: boolean
  userId: number
  userName: string
  priority: number
  status: string
  saying: string
  currentClanId: number
  clanList: ClanInfo[]
}

function readPersist(): Partial<PersistState> {
  try {
    const raw = localStorage.getItem(PERSIST_KEY)
    if (!raw) return {}
    return JSON.parse(raw) as Partial<PersistState>
  } catch (e) {
    return {}
  }
}

function writePersist(state: PersistState) {
  try {
    localStorage.setItem(PERSIST_KEY, JSON.stringify(state))
  } catch (e) {
    /* ignore quota / ssr errors */
  }
}

function clearPersist() {
  try {
    localStorage.removeItem(PERSIST_KEY)
  } catch (e) {
    /* ignore */
  }
}

/**
 * 浏览器端是否存在 token cookie。
 * 注意：后端 token cookie 现在是非 HttpOnly，前端可读；但我们不读取它的值，
 * 只用于"作为是否可能已登录"的补充判断。真正的鉴权永远走后端接口。
 */
function hasCookieToken() {
  try {
    return /(^|;\s*)token=/.test(document.cookie)
  } catch (e) {
    return false
  }
}

/** 删除前端可写的 token cookie（用于登出 / 清理脏状态） */
function clearCookieToken() {
  try {
    document.cookie =
      'token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax'
    // 兼容之前可能漏写在默认 path 下的旧 cookie
    document.cookie =
      'token=; path=/kanna_dependency; expires=Thu, 01 Jan 1970 00:00:00 GMT'
  } catch (e) {
    /* ignore */
  }
}

export const useUserStore = defineStore('user', () => {
  const persisted = readPersist()

  const isLoggedIn = ref<boolean>(
    persisted.isLoggedIn === true || hasCookieToken()
  )
  const userId = ref<number>(persisted.userId || 0)
  const userName = ref<string>(persisted.userName || '')
  const priority = ref<number>(persisted.priority || 0)
  const status = ref<string>(persisted.status || '成员')
  const saying = ref<string>(persisted.saying || '')
  const clanList = ref<ClanInfo[]>(persisted.clanList || [])
  // 当前选中的公会（默认第一个）
  const currentClanId = ref<number>(persisted.currentClanId || 0)

  // 持久化订阅：任何状态变化后写入 localStorage
  watch(
    [isLoggedIn, userId, userName, priority, status, saying, clanList, currentClanId],
    () => {
      if (isLoggedIn.value) {
        writePersist({
          isLoggedIn: isLoggedIn.value,
          userId: userId.value,
          userName: userName.value,
          priority: priority.value,
          status: status.value,
          saying: saying.value,
          currentClanId: currentClanId.value,
          clanList: clanList.value
        })
      } else {
        clearPersist()
      }
    },
    { deep: true }
  )

  const currentClan = computed<ClanInfo | undefined>(() => {
    return clanList.value.find((c) => c.group_id === currentClanId.value)
  })

  /**
   * 登录动作：调后端 /login 获取 cookie，并同步刷新登录标记。
   * 这里再包一层是为了让 store 成为单一认证源，登录成功后立刻调 /home 拿到用户信息。
   */
  async function login(account: string, password: string) {
    await apiLogin({ account, password })
    // 到这里 Set-Cookie: token=xxx 已写入
    // 同步 localStorage 标记，保证刷新后不会被立即判定为"未登录"
    isLoggedIn.value = true
    await fetchUserInfo()
  }

  async function fetchUserInfo() {
    try {
      const info = await getHomeInfo()
      userId.value = info.user_id
      userName.value = info.name
      priority.value = info.priority
      status.value = info.status
      saying.value = info.saying
      clanList.value = info.clan
      if (!currentClanId.value && info.clan.length > 0) {
        currentClanId.value = info.clan[0].group_id
      }
      isLoggedIn.value = true
      return info
    } catch (e: any) {
      const statusCode = e?.response?.status ?? e?.status
      if (statusCode === 401) {
        // 401 表示 cookie 失效，同步清掉本地持久化
        markLoggedOut()
      }
      throw e
    }
  }

  function setCurrentClan(id: number) {
    currentClanId.value = id
  }

  /** 把本 store 的所有"已登录"迹象清除（不负责跳转，跳转由调用方做） */
  function markLoggedOut() {
    isLoggedIn.value = false
    userId.value = 0
    userName.value = ''
    priority.value = 0
    status.value = '成员'
    saying.value = ''
    clanList.value = []
    currentClanId.value = 0
    clearPersist()
    clearCookieToken()
  }

  async function logout(notify = false) {
    // 优先调用后端登出（让 token 立刻失效），失败也继续清本地
    try {
      await apiLogout()
    } catch (e) {
      /* ignore */
    }
    markLoggedOut()
    if (notify) {
      try {
        const { ElMessage } = await import('element-plus')
        ElMessage.success('已退出登录')
      } catch (e) {
        /* ignore */
      }
    }
  }

  return {
    isLoggedIn,
    userId,
    userName,
    priority,
    status,
    saying,
    clanList,
    currentClanId,
    currentClan,
    login,
    fetchUserInfo,
    setCurrentClan,
    markLoggedOut,
    logout
  }
})
