import { computed, ref, watch } from 'vue'

/**
 * 主题（浅色 / 深色 / 跟随系统）
 *
 * 设计要点：
 * - 一个模块级单例：所有组件（Layout / Login / 图表）共用同一份状态，
 *   切换主题时整站同步，不需要 provide/inject。
 * - 真正的配色在 `src/style.css`：`:root` 定义浅色语义变量，`html.dark` 覆盖成深色。
 *   这里只负责给 `<html>` 加 / 去 `.dark` 类、记住用户选择。
 * - `element-plus/theme-chalk/dark/css-vars.css` 会根据 `html.dark` 自动切 Element Plus
 *   组件（表格 / 弹窗 / 下拉框……）的暗色，main.ts 里已经引入。
 * - 首屏防闪：`index.html` 的 <head> 里有一小段内联脚本，在 CSS / JS 加载前就把
 *   `.dark` 类打好；两处读的是同一个 localStorage 键，改键名要一起改。
 */
export type ThemeMode = 'auto' | 'light' | 'dark'

/** 与 index.html 首屏脚本共用的 localStorage 键名，改这里必须同步改 index.html */
export const THEME_STORAGE_KEY = 'kanna.theme.v1'

const DARK_QUERY = '(prefers-color-scheme: dark)'

function readStoredMode(): ThemeMode {
  try {
    const raw = localStorage.getItem(THEME_STORAGE_KEY)
    if (raw === 'light' || raw === 'dark' || raw === 'auto') return raw
  } catch (e) {
    /* localStorage 不可用（隐私模式等）时按跟随系统处理 */
  }
  return 'auto'
}

/** 用户选择：auto = 跟随系统 */
const mode = ref<ThemeMode>(readStoredMode())

/** 系统当前是不是深色（仅在 mode === 'auto' 时影响结果） */
const systemDark = ref<boolean>(
  typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    ? window.matchMedia(DARK_QUERY).matches
    : false
)

/** 当前**实际**生效的是不是深色 */
const isDark = computed<boolean>(
  () => mode.value === 'dark' || (mode.value === 'auto' && systemDark.value)
)

/** 把主题应用到 <html>：加 / 去 .dark 类，并同步 color-scheme（滚动条、原生控件、地址栏） */
function applyTheme(dark: boolean) {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  root.classList.toggle('dark', dark)
  root.style.colorScheme = dark ? 'dark' : 'light'
}

let inited = false

/** 初始化：应用当前主题 + 监听系统主题变化 / 其它标签页的切换。幂等，可重复调用。 */
export function initTheme() {
  if (inited || typeof window === 'undefined') return
  inited = true

  applyTheme(isDark.value)

  if (typeof window.matchMedia === 'function') {
    const media = window.matchMedia(DARK_QUERY)
    const onChange = (e: MediaQueryListEvent) => {
      systemDark.value = e.matches
      // 手动选过 light / dark 时不受系统影响；auto 模式下立即跟随
      applyTheme(isDark.value)
    }
    if (typeof media.addEventListener === 'function') {
      media.addEventListener('change', onChange)
    } else if (typeof (media as any).addListener === 'function') {
      // 老 Safari / 老内核兜底
      ;(media as any).addListener(onChange)
    }
  }

  // 同一浏览器多个标签页之间同步主题（例如开了两个后台页面）
  window.addEventListener('storage', (e) => {
    if (e.key !== THEME_STORAGE_KEY) return
    mode.value = readStoredMode()
    applyTheme(isDark.value)
  })

  // 其它途径改了 mode（setMode / 同步 storage）时应用到 DOM
  watch(isDark, (dark) => applyTheme(dark))
}

/** 手动切换主题并持久化 */
function setMode(next: ThemeMode) {
  mode.value = next
  try {
    localStorage.setItem(THEME_STORAGE_KEY, next)
  } catch (e) {
    /* 存不下就只在本次会话生效 */
  }
  applyTheme(isDark.value)
}

/** 一键在浅色 / 深色之间切换（点了之后就不再跟随系统） */
function toggle() {
  setMode(isDark.value ? 'light' : 'dark')
}

/** 组件里用这个拿主题状态；单例，多次调用返回同一份 ref */
export function useTheme() {
  initTheme()
  return { mode, isDark, setMode, toggle, initTheme }
}

/* ======================= 图表配色 ======================= */

/**
 * ECharts 没有 CSS 主题机制：坐标轴、图例、tooltip 的颜色都写在 option 里，
 * 所以这里给图表单独提供一套随主题变化的配色。
 *
 * 用法（在 computed option 里读即可，切主题会自动重新计算 → 图表跟着变）：
 *
 *   const chartTheme = useChartTheme()
 *   const option = computed<EChartsOption>(() => {
 *     const c = chartTheme.value
 *     return {
 *       textStyle: { color: c.text },
 *       tooltip: { backgroundColor: c.tooltipBg, borderColor: c.tooltipBorder, textStyle: { color: c.tooltipText } },
 *       xAxis: { axisLabel: { color: c.textSecondary }, axisLine: { lineStyle: { color: c.axisLine } }, splitLine: { lineStyle: { color: c.splitLine } } },
 *       ...
 *     }
 *   })
 */
export interface ChartTheme {
  /** 主要文字：坐标轴名称、数值标签 */
  text: string
  /** 次要文字：坐标轴刻度、图例 */
  textSecondary: string
  /** 弱化文字：说明性标注 */
  muted: string
  /** 坐标轴线 */
  axisLine: string
  /** 网格分隔线 */
  splitLine: string
  /** tooltip 背景 / 边框 / 文字 */
  tooltipBg: string
  tooltipBorder: string
  tooltipText: string
  /** 与页面语义色一致的常用系列色 */
  primary: string
  warning: string
  success: string
  danger: string
  info: string
  /** hover（emphasis）时比系列色深一档的颜色 */
  primaryDeep: string
  warningDeep: string
}

const CHART_LIGHT: ChartTheme = {
  text: '#374151',
  textSecondary: '#4b5563',
  muted: '#9ca3af',
  axisLine: '#e5e7eb',
  splitLine: 'rgba(107, 114, 128, 0.16)',
  tooltipBg: 'rgba(255, 255, 255, 0.96)',
  tooltipBorder: 'rgba(236, 72, 153, 0.25)',
  tooltipText: '#1f2937',
  primary: '#ec4899',
  warning: '#f59e0b',
  success: '#10b981',
  danger: '#ef4444',
  info: '#3b82f6',
  primaryDeep: '#db2777',
  warningDeep: '#d97706'
}

const CHART_DARK: ChartTheme = {
  text: '#e5e7eb',
  textSecondary: '#d1d5db',
  muted: '#9ca3af',
  axisLine: 'rgba(255, 255, 255, 0.2)',
  splitLine: 'rgba(255, 255, 255, 0.12)',
  tooltipBg: 'rgba(34, 29, 41, 0.96)',
  tooltipBorder: 'rgba(244, 114, 182, 0.35)',
  tooltipText: '#e5e7eb',
  primary: '#ec4899',
  warning: '#fbbf24',
  success: '#34d399',
  danger: '#f87171',
  info: '#60a5fa',
  primaryDeep: '#f472b6',
  warningDeep: '#fcd34d'
}

/** 当前主题对应的图表配色（computed，切主题后图表 option 会自动重算） */
export function useChartTheme() {
  const { isDark } = useTheme()
  return computed<ChartTheme>(() => (isDark.value ? CHART_DARK : CHART_LIGHT))
}
