# 环奈连结 R · Web 前端（KCRR WebUI）

基于 **Vue 3 + TypeScript + Vite + Element Plus + Pinia + ECharts** 的 KCRR 公会战管理系统前端。

对接后端：`kanna_connection_redive_2/webui/`（FastAPI，默认监听 `0.0.0.0:12138`）。
界面截图见仓库根目录的 [readme.md](../readme.md#-网页端界面预览)。

---

## 🌟 功能

### 🔐 登录与账号

- **机器人私发链接自动登录**：URL 携带 `account` / `password`，打开即登录（`router/index.ts` 的路由守卫会无条件放行，避免浏览器里的旧登录态把人顶成别人）
- 首次登录用的是 QQ 私聊【网页端登录】下发的**临时密码**（7 天有效）；登录后可在右上角**修改密码**，改完自己不再过期，其他设备上的登录态会失效
- **登出**：后端立即失效 token + 清理本地登录标记

### 🏠 首页

- 欢迎卡片：昵称 / QQ 号 / 身份 / 签名，右侧统计「我的公会数」「最高权限」
- **我的公会**：一张卡片一个群，带该群的权限标签，点击直接进入该群控制台
  - 列表 = 我绑定过公会的群 ∪ 我是群主 / 群管的在用群（bot 主人 = 全部在用群）
  - 一个群都没有时给出引导：在 QQ 群里发【绑定本群公会】
- 快捷入口

### ⚔️ 会战仪表盘

- **BOSS 状态**：5 个 BOSS 的血量进度、预约 / 申请 / 挂树人数；点 BOSS 卡可查看该 BOSS 今日全部出刀记录
- 时钟卡与 BOSS 卡等高
- **今日出刀分布** / **最近出刀（Top 20）** / **今日伤害排行**（横向条形 Top 10，同时给出伤害与分数；右上角标签是全员累计伤害）
- **会战档线**：各档位分数线、守线公会 / 会长 / 人数 / 档位奖励、与我会的差距；支持自定义档位
  - 右上角显示数据抓取时间，可手动强制刷新
- 一键**预约 / 申请 / 挂树**
- **出刀监控**开 / 关：只能开自己绑定的账号；取消需监控人本人或 bot 主人
- **绑定游戏账号**：官服 / 渠道服 / 台服三套表单
- SSE 实时刷新（`renew_dashboard`）

### 📊 出刀报告

- **我的出刀**明细（时间 / BOSS / 伤害 / 类型 / 刀数），固定高度、超出滚动
- **全员伤害排行**：伤害 + 分数双序列柱状图
- **全员汇总**表，支持排序
- **修正出刀**类型（完整刀 / 尾刀 / 补偿）
- SSE 实时刷新（`renew_report`）

### 🔔 通知管理

- 预约 / 申请 / 挂树 / SL 列表，添加与取消通知
- **代人取消**通知（`delete_notice_special`）
- SSE 实时刷新（`renew_notice`）

### 🔑 权限模型（按群算）

前端**不自己算权限**，一律读后端下发的字段：

- `/home` → 每个公会的 `priority`
- `dashboard` / `report` / `notice` → `clan_priority`

| 等级 | 说明 |
| --- | --- |
| 0 | 普通成员（只读，默认） |
| 1 | 网页端管理员（【网页权限】授予，全局） |
| 2 | 群主 / 群管（群内角色自动识别，**仅本群**） |
| 3 | bot 主人（`SUPERUSERS`，所有群） |

> ⚠️ **不要用全局的 `userStore.priority` 判断页面权限**。群主 / 群管是在各自群里自动获得 2 级的，
> 用全局值会把「我在 A 群是群主」误当成「我在所有群都是管理员」。页面里请用
> `userStore.currentClanPriority` 或接口返回的 `clan_priority`。

### 🎨 界面

- 粉色樱花系主题 + 玻璃拟态卡片
- 顶部可**切换公会**（切换后 URL 与页面数据一起切，见 `layout/Layout.vue`）

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

请求 `/kanna_dependency/**` 会被 Vite 代理到 `VITE_API_URL`（默认 `http://localhost:12138`，可在 `.env` 中修改）。
前后端不在同一台机器时，把 `VITE_API_URL` 改成后端所在机器的内网 IP。

### 3. 生产构建

```bash
npm run build
# = vue-tsc --noEmit && vite build，产物输出到 web/dist
```

构建后，你可以将 `dist` 目录部署到任意静态服务器；**确保生产环境前端和后端同源，或者后端 CORS 增加你的生产域名**（后端 CORS 配置位于 `webui/api.py` 的 `origins` 列表）。

---

## 📂 目录结构

```
web/
├── index.html
├── package.json
├── vite.config.ts            # 别名 @ → src、dev 代理 /kanna_dependency、手动分包
├── tsconfig.json
├── env.d.ts
├── .env                      # VITE_API_URL / VITE_API_BASE
└── src/
    ├── main.ts                 # 入口
    ├── App.vue                 # 根组件
    ├── style.css               # 全局样式（樱花主题变量、玻璃拟态卡片）
    ├── api/
    │   └── index.ts            # 所有后端 API 封装
    ├── router/
    │   └── index.ts            # 路由 + 登录守卫（含 URL 凭据自动登录）
    ├── store/
    │   └── user.ts             # Pinia 用户状态（含 currentClanPriority）
    ├── types/
    │   └── index.ts            # TS 类型定义（对齐后端模型）
    ├── utils/
    │   ├── request.ts          # Axios 封装（含 401 跳转登录）
    │   └── sse.ts              # SSE 实时推送封装
    ├── layout/
    │   └── Layout.vue          # 主布局（侧边栏 + 顶栏公会切换 + 修改密码弹窗）
    └── views/
        ├── Login.vue           # 登录页
        ├── Home.vue            # 首页
        ├── Dashboard.vue       # 会战仪表盘
        ├── Report.vue          # 出刀报告
        └── Notice.vue          # 通知管理
```

---

## 🔗 后端对接说明

路由前缀 `/kanna_dependency`（`WebSetting.api_base`，由 `webui/api.py` 的 `APIRouter(prefix=...)` 挂载）。

| 后端路由 | 前端调用位置 | 说明 |
| --- | --- | --- |
| `POST /login` | `Login.vue` / `store/user.ts` | 账号密码登录，`Set-Cookie: token=...` |
| `POST /logout` | `store/user.ts` | 登出（后端删 cookie） |
| `POST /change_password` | `Layout.vue` | 修改密码（需旧密码，改完清其他设备登录态） |
| `GET /home` | `store/user.ts` | 用户信息 + 公会列表（每群带 `priority`） |
| `GET /{group_id}/dashboard` | `Dashboard.vue` | 仪表盘（含档线、今日伤害排行） |
| `GET /{group_id}/boss_dao?boss=N` | `Dashboard.vue` | 某 BOSS 今日全部出刀记录 |
| `GET /{group_id}/rank_lines?ranks=&force=` | `Dashboard.vue` | 会战档线 |
| `GET /{group_id}/report` | `Report.vue` | 出刀报告 |
| `GET /{group_id}/notice` | `Notice.vue` | 通知列表 |
| `POST /set_notice` | `Dashboard.vue` / `Notice.vue` | 添加通知（预约 / 申请 / 挂树 / SL） |
| `POST /delete_notice` | `Notice.vue` | 取消通知 |
| `POST /delete_notice_special` | `Notice.vue` | 代人取消通知 |
| `POST /correct_dao` | `Report.vue` | 修正出刀类型 |
| `POST /{group_id}/bind_account` | `Dashboard.vue` | 绑定游戏账号 |
| `POST /{group_id}/unbind_account` | `Dashboard.vue` | 解绑游戏账号 |
| `GET /{group_id}/monitor/accounts` | `Dashboard.vue` | 可用于开启监控的账号（只返回自己的） |
| `POST /{group_id}/monitor` | `Dashboard.vue` | 开 / 关出刀监控 |
| `GET /{group_id}/renew_dashboard`（SSE） | `Dashboard.vue` | 实时推送 |
| `GET /{group_id}/renew_report`（SSE） | `Report.vue` | 实时推送 |
| `GET /{group_id}/renew_notice`（SSE） | `Notice.vue` | 实时推送 |

### 鉴权

后端通过 `Set-Cookie: token=<xxx>` 下发会话，前端所有请求自动带 cookie
（axios `withCredentials: true`，SSE `EventSource({ withCredentials: true })`）。

两类后端依赖（定义在 `webui/util.py`）：

| 依赖 | 含义 | 用在 |
| --- | --- | --- |
| `verify_cookie` | 只要求已登录 | `/home`、`/set_notice`、`/delete_notice`、`/correct_dao` 等 |
| `verify_group_access` | 已登录 **且** 对该群有访问权 | 所有 `/{group_id}/...` 路由 |

`ensure_group_access` 的规则：bot 主人任意群；其他人必须和该群有关系 —— 有成员绑定记录，
或是该群的群主 / 群管。**没有它，任何登录用户改一下地址栏里的群号就能看到别的群数据。**

401 由 `utils/request.ts` 统一拦截 → 清本地登录标记 → 跳登录页。

### 两个需要前端配合的后端约定

1. **档线接口**：只有**出刀监控正在运行**时后端才允许去游戏侧抓档线，否则只返回本地缓存
   （响应里 `monitor_running: false`），读不到才 400。前端用响应里的
   `cached` / `stale` / `updated_at` 显示数据来源与抓取时间；`force=true` 才会强制抓一次。
2. **SSE**：三个 `renew_*` 接口返回 `text/event-stream`。如果被代理 / 拦截成 `application/json`，
   浏览器会报 `MIME type ("application/json") is not "text/event-stream"` 并断开 —— 排查时先看这里。

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
