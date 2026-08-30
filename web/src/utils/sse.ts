/**
 * SSE (Server-Sent Events) 工具封装
 * 对应后端 renew_dashboard / renew_report / renew_notice 接口
 */

export interface SSEOptions {
  onMessage: (data: any) => void
  onError?: (err: Event) => void
  onOpen?: (e: Event) => void
}

export function createSSEConnection(url: string, options: SSEOptions): EventSource {
  // 浏览器直接 fetch 会自动带上 cookie（httponly 的 token cookie 由浏览器自动发送）
  const es = new EventSource(url, { withCredentials: true })

  es.addEventListener('open', (e) => {
    console.log('[SSE] connected:', url)
    options.onOpen?.(e)
  })

  es.addEventListener('message', (event) => {
    try {
      const data = JSON.parse(event.data)
      options.onMessage(data)
    } catch (err) {
      console.warn('[SSE] parse failed:', event.data, err)
    }
  })

  es.addEventListener('error', (err) => {
    console.error('[SSE] error:', url, err)
    options.onError?.(err)
  })

  return es
}
