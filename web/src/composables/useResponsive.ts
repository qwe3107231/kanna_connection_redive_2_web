import { ref } from 'vue'

/**
 * 手机断点：`< 768px` 视为手机。
 * 必须与 `src/style.css` 里的 `@media (max-width: 767px)` 保持一致。
 */
export const MOBILE_BREAKPOINT = 768

const isMobile = ref(false)
let inited = false

function update() {
  isMobile.value = window.innerWidth < MOBILE_BREAKPOINT
}

/**
 * 全局单例的「当前是不是手机」响应式状态。
 *
 * 只有**必须用 JS 分支**的地方才用它（例如同一个位置桌面端渲染表格、手机端渲染
 * 卡片列表）。纯样式差异优先写 CSS 媒体查询 —— 那样不依赖 JS，首屏也不会闪。
 *
 * 监听只挂一份、组件卸载时不撤：状态是全局共享的，监听开销可忽略。
 */
export function useIsMobile() {
  if (!inited && typeof window !== 'undefined') {
    inited = true
    update()
    window.addEventListener('resize', update, { passive: true })
    window.addEventListener('orientationchange', update, { passive: true })
  }
  return isMobile
}
