# 环奈连结 R · Web 前端（KCRR WebUI）

基于 **Vue 3 + TypeScript + Vite + Element Plus + Pinia + ECharts** 的 KCRR 公会战管理系统前端。

对接后端：`kanna_connection_redive_2/webui/` (FastAPI，监听 `0.0.0.0:12138`)

---

## 🌟 功能

- 🔐 **登录**：支持机器人私发链接自动登录（URL 携带 `account`/`password`）
- 🏠 **首页**：公会概览 / 玩家信息 / 快捷入口
- ⚔️ **会战仪表盘**：BOSS 实时状态、今日出刀分布、伤害饼图、一键预约/申请/挂树、SSE 实时刷新
- 📊 **出刀报告**：全员排行榜 + 柱状图、出刀明细表（支持搜索、修正出刀类型）
- 🔔 **通知管理**：预约/申请/挂树列表、添加/取消通知、SSE 实时同步
- 🎨 粉色樱花系主题 + 玻璃拟态卡片

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd web
npm install
```

### 2. 开发模式（已内置代理转发后端 API）

```bash
npm run dev
```

默认前端地址：`http://localhost:5173`

后端请求 `VITE_API_BASE=/kanna_dependency` 会被代理到 `http://localhost:12138`（可在 `.env` 中修改 `VITE_API_URL`）。

### 3. 生产构建

```bash
npm run build
# 构建产物输出到 web/dist
```

构建后，你可以将 `dist` 目录部署到任意静态服务器；**确保生产环境前端和后端同源，或者后端 CORS 增加你的生产域名**（后端 CORS 配置位于 `webui/api.py` 的 `origins` 列表）。

---

## 📂 目录结构

```
web/
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
├── env.d.ts
├── .env
└── src/
    ├── main.ts                 # 入口
    ├── App.vue                 # 根组件
    ├── style.css               # 全局样式
    ├── api/
    │   └── index.ts            # 所有后端 API 封装
    ├── router/
    │   └── index.ts            # 路由配置
    ├── store/
    │   └── user.ts             # Pinia 用户状态
    ├── types/
    │   └── index.ts            # TS 类型定义（对齐后端模型）
    ├── utils/
    │   ├── request.ts          # Axios 封装（含 401 跳转登录）
    │   └── sse.ts              # SSE 实时推送封装
    ├── layout/
    │   └── Layout.vue          # 主布局（侧边栏 + 顶栏）
    └── views/
        ├── Login.vue           # 登录页
        ├── Home.vue            # 首页
        ├── Dashboard.vue       # 会战仪表盘
        ├── Report.vue          # 出刀报告
        └── Notice.vue          # 通知管理
```

---

## 🔗 后端对接说明

| 后端路由 (前缀 `/kanna_dependency`) | 前端调用位置 |
|---|---|
| `POST /login` | Login.vue |
| `GET /home` | store/user.ts |
| `GET /{group_id}/dashboard` | Dashboard.vue |
| `GET /{group_id}/renew_dashboard` (SSE) | Dashboard.vue |
| `GET /{group_id}/report` | Report.vue |
| `GET /{group_id}/renew_report` (SSE) | Report.vue |
| `GET /{group_id}/notice` | Notice.vue |
| `GET /{group_id}/renew_notice` (SSE) | Notice.vue |
| `POST /set_notice` | Dashboard.vue / Notice.vue |
| `POST /delete_notice` | Notice.vue |
| `POST /correct_dao` | Report.vue |

**鉴权方式**：后端通过 `Set-Cookie: token=<xxx>; httponly` 下发会话，前端所有请求自动带 cookie（axios `withCredentials: true`，SSE `EventSource({ withCredentials: true })`）。

---

## 📌 建议的生产部署

1. 构建前端：`npm run build`，生成 `web/dist/*`
2. 在后端 `webui/api.py` 中挂载 `dist` 作为静态目录（类似下面的伪代码），即可同端口访问前后端：

```python
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

# 挂载前端静态
app.mount("/static", StaticFiles(directory="web/dist/assets"), name="static")

# SPA 兜底
@app.get("/{full_path:path}")
async def spa_catchall():
    return FileResponse("web/dist/index.html")
```

或者使用 Nginx 反向代理 `/kanna_dependency` 到 `127.0.0.1:12138`，其他路径指向前端 `dist/index.html`。
