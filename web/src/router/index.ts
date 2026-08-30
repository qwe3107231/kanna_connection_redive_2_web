import { createRouter, createWebHashHistory, RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/store/user'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录', requiresAuth: false }
  },
  {
    path: '/',
    component: () => import('@/layout/Layout.vue'),
    redirect: '/home',
    children: [
      {
        path: 'home',
        name: 'Home',
        component: () => import('@/views/Home.vue'),
        meta: { title: '首页', icon: 'HomeFilled', requiresAuth: true }
      },
      {
        path: 'dashboard/:groupId?',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '会战仪表盘', icon: 'DataAnalysis', requiresAuth: true }
      },
      {
        path: 'report/:groupId?',
        name: 'Report',
        component: () => import('@/views/Report.vue'),
        meta: { title: '出刀报告', icon: 'Document', requiresAuth: true }
      },
      {
        path: 'notice/:groupId?',
        name: 'Notice',
        component: () => import('@/views/Notice.vue'),
        meta: { title: '通知管理', icon: 'Bell', requiresAuth: true }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/home'
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

/**
 * 浏览器端是否"可能"存在登录 cookie。
 * 注意：现在 token 是非 HttpOnly，只是判断有没有；真正有效性看后端接口。
 */
function hasCookieToken() {
  try {
    return /(^|;\s*)token=/.test(document.cookie)
  } catch (e) {
    return false
  }
}

router.beforeEach(async (to, _from, next) => {
  const title = (to.meta?.title as string) || '环奈连结 R'
  document.title = `${title} · 环奈连结 R`

  const userStore = useUserStore()

  // 从 URL query 获取 account/password（QQ 机器人私发的登录链接）
  const urlAccount = to.query.account as string
  const urlPassword = to.query.password as string
  const hasUrlCredentials = !!(urlAccount && urlPassword)

  // 登录页直接放行（如果本地有已登录标记，就主动跳首页）
  // 但注意：带 account/password 凭据的登录链接必须无条件放行去自动登录（换号登录），
  // 否则浏览器里残留的旧登录标记会把登录页重定向到 /home，导致打开的还是别人的账号
  if (to.meta.requiresAuth === false) {
    if (hasUrlCredentials) {
      return next()
    }
    if (userStore.isLoggedIn && userStore.userId) {
      return next('/home')
    }
    return next()
  }

  if (hasUrlCredentials && to.path !== '/login') {
    return next({
      path: '/login',
      query: {
        account: urlAccount,
        password: urlPassword,
        redirect: to.fullPath
      }
    })
  }

  // 是否有任何"疑似已登录"的本地标记
  const hasLocalMark = userStore.isLoggedIn || hasCookieToken()

  if (!hasLocalMark) {
    // 完全没有登录迹象，直接去登录页
    return next({ path: '/login', query: { redirect: to.fullPath } })
  }

  // 有本地标记但没拿到用户基本信息 → 说明是"刷新后第一次进入"，需要向后端校验
  // 注意：这一步是关键 —— 保证刷新后"真的已登录"才停留在目标页面，
  // "cookie 过期 / token 失效"会走 401 分支被 axios 打回登录页。
  if (!userStore.userId) {
    try {
      await userStore.fetchUserInfo()
    } catch (e: any) {
      // 401 已由 axios 拦截器做 markLoggedOut + 跳登录
      const status = e?.response?.status ?? e?.status
      if (status !== 401) {
        // 非 401（网络问题 / 500 等）先放行到页面，让页面各自的 onMounted
        // 接口请求来展示报错，避免整站白屏
      } else {
        // 已被拦截器跳转到登录页，这里不再二次处理
        return false as any
      }
    }
  }

  next()
})

export default router
