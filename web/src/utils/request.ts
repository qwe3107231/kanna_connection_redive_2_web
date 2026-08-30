import axios, { AxiosError, InternalAxiosRequestConfig, AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'
import { useUserStore } from '@/store/user'

const API_BASE = import.meta.env.VITE_API_BASE || '/kanna_dependency'

const instance = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
  // withCredentials 必须开启，因为后端使用 cookie 存储 token
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
instance.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 防止 401 时多个并发请求一起触发 "已过期" 提示 + 多次跳转
let __loginRedirecting = false

// 响应拦截器
instance.interceptors.response.use(
  (response: AxiosResponse) => {
    return response
  },
  (error: AxiosError<any>) => {
    if (error.response) {
      const { status, data, config } = error.response
      switch (status) {
        case 401: {
          const userStore = useUserStore()
          // 先清掉所有本地登录态，避免"明明过期但 localStorage 显示已登录"的反复横跳
          userStore.markLoggedOut()

          const msg = data?.detail || '登录已过期，请重新登录'
          // /home 接口是每次页面刷新进入时的自动校验，不要重复弹提示污染 UI
          const isSilentApi =
            typeof config?.url === 'string' &&
            /\/home(\?|$)/.test(config.url.replace(API_BASE, ''))
          if (!isSilentApi) {
            ElMessage.error(msg)
          }
          if (!__loginRedirecting) {
            __loginRedirecting = true
            const redirect = router.currentRoute.value.fullPath
            // 如果已经在登录页，就不要再带 redirect 死循环
            if (router.currentRoute.value.path !== '/login') {
              router
                .replace({ path: '/login', query: { redirect } })
                .finally(() => {
                  setTimeout(() => { __loginRedirecting = false }, 800)
                })
            } else {
              __loginRedirecting = false
            }
          }
          break
        }
        case 403:
          ElMessage.error(data?.detail || '权限不足')
          break
        case 404:
          ElMessage.error('接口不存在')
          break
        case 500:
          ElMessage.error(data?.detail || '服务器内部错误')
          break
        default:
          ElMessage.error(data?.detail || `请求失败 (${status})`)
      }
    } else if (error.request) {
      ElMessage.error('网络错误，无法连接到服务器')
    } else {
      ElMessage.error(error.message || '未知错误')
    }
    return Promise.reject(error)
  }
)

export default instance
export { API_BASE }
