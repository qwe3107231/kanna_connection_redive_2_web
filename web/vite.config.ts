import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd())

  // Vite 5.4.12 起加了 host 检查（防 DNS rebinding），默认只放行 localhost / IP，
  // 用域名访问会被 403。域名属于**部署配置**，写在 web/.env 的
  // VITE_ALLOWED_HOSTS（英文逗号分隔，例如 `pcr.example.com,foo.example.com`），
  // 不要硬编码进源码。留空则只允许 localhost / IP 访问。
  const allowedHosts = (env.VITE_ALLOWED_HOSTS || '')
    .split(',')
    .map((h) => h.trim())
    .filter(Boolean)

  // 前端的 axios baseURL 是相对路径 `/kanna_dependency`（见 src/utils/request.ts），
  // 所以无论 dev 还是 preview，都得把该前缀代理到后端 FastAPI。
  const proxy = {
    '/kanna_dependency': {
      target: env.VITE_API_URL || 'http://localhost:12138',
      changeOrigin: true,
      secure: false
    }
  }

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src')
      }
    },
    // 开发：`npm run dev`
    server: {
      host: '0.0.0.0',
      port: 5173,
      open: false,
      allowedHosts,
      proxy
    },
    // 生产：`npm run build` 产出 dist，再由 `npm run preview` 提供静态服务。
    // 端口刻意与 dev 保持一致（5173），这样群友的访问地址和 QQ 机器人
    // 回复的登录链接都不用改。
    preview: {
      host: '0.0.0.0',
      port: 5173,
      allowedHosts,
      proxy
    },
    build: {
      outDir: 'dist',
      sourcemap: false,
      chunkSizeWarningLimit: 2000,
      rollupOptions: {
        output: {
          manualChunks: {
            vue: ['vue', 'vue-router', 'pinia'],
            element: ['element-plus', '@element-plus/icons-vue'],
            echarts: ['echarts', 'vue-echarts']
          }
        }
      }
    }
  }
})
