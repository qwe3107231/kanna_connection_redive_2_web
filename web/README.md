# 环奈连结 R · Web 前端（KCRR WebUI）

基于 **Vue 3 + TypeScript + Vite + Element Plus + Pinia + ECharts** 的 KCRR 公会战管理系统前端。

对接后端：本仓库根目录的 `webui/`（FastAPI，默认监听 `0.0.0.0:12138`）。
界面截图见仓库根目录的 [readme.md](../readme.md#-网页端界面预览)。

---

## 🌟 功能

- **登录与账号**：QQ 机器人私发链接自动登录、修改密码、登出
- **首页**：个人资料、游戏账号绑定 / 换绑 / 解绑、我的公会列表、快捷入口
- **会战仪表盘**：BOSS 状态与血量、一键预约 / 申请 / 挂树、今日出刀分布、最近出刀、今日伤害排行、会战档线（可自定义档位、可强制刷新）、出刀监控开关；页内 Tab 含「出刀报告」「通知管理」
- **出刀报告**：我的出刀明细、全员伤害排行、全员汇总表、修正出刀类型
- **通知管理**：预约 / 申请 / 挂树 / SL 列表，添加、取消、代人取消
- **BOX / 助战**：个人 BOX、公会 BOX、公会助战、我的助战（更换支援）、刷新缓存；角色详情含星级 / 专武 / 好感 / 装备；头像照游戏样式画（品级框 + 星级 + 职业/属性角标）；个人 BOX 查询框下面是**练度条**（MP等级 / 属性强化 / 属性技能 / 职介等级，随【刷新缓存】更新）
- **好友**：好友列表（可按等级 / 战力 / 好友数 / 最后登录排序）、添加 / 解除好友、好友申请（同意 / 拒绝 / 撤回）、好友资料
- **竞技场中心**：监控状态与提醒开关、排行榜、查防守 / 作业、查 ID、防守缓存
- **界面**：粉色樱花主题、浅色 / 夜间 / 跟随系统、手机端自适应（底部导航）
- **权限**：按群计算 —— 普通成员（只读）/ 网页端管理员 / 群主·群管 / bot 主人

> 网页端与 QQ 群指令共用同一套后端数据。涉及登录游戏账号的操作（刷新缓存、更换支援、好友写操作等）会顶号，页面会提前弹出确认提示。

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
├── index.html                # 入口 HTML（含夜间模式首屏防闪脚本）
├── package.json
├── vite.config.ts            # 别名 @ → src、dev 代理 /kanna_dependency、手动分包
├── tsconfig.json
├── env.d.ts
├── .env                      # VITE_API_URL / VITE_API_BASE
└── src/
    ├── main.ts                 # 入口（引入 Element Plus 暗色变量 + initTheme）
    ├── App.vue                 # 根组件
    ├── style.css               # 全局样式 + 浅色/夜间主题变量（--kanna-*）
    ├── api/
    │   └── index.ts            # 所有后端 API 封装
    ├── router/
    │   └── index.ts            # 路由 + 登录守卫（含 URL 凭据自动登录）
    ├── store/
    │   └── user.ts             # Pinia 用户状态（含 currentClanPriority）
    ├── types/
    │   └── index.ts            # TS 类型定义（对齐后端模型）
    ├── assets/
    │   └── unit_icon/          # 游戏原版 UI 图标：品级框 / 星级 / 职业 / 属性（从 autopcr 解包导出）
    ├── data/
    │   └── unit_talent_role.json  # 角色 ID -> [属性(1~5), 职业(1~8)]（从游戏主库导出）
    ├── utils/
    │   ├── request.ts          # Axios 封装（含 401 跳转登录）
    │   └── sse.ts              # SSE 实时推送封装
    ├── composables/
    │   ├── useResponsive.ts    # 手机断点
    │   └── useTheme.ts         # 浅色/夜间/跟随系统 + 图表配色 useChartTheme
    ├── components/
    │   ├── ThemeToggle.vue     # 主题切换按钮（顶栏 / 登录页复用）
    │   ├── AccountBind.vue     # 首页游戏账号绑定卡片
    │   ├── GameUnitAvatar.vue  # 游戏样式角色头像（品级框 + 星级 + 职业/属性角标）
    │   ├── ArenaProfilePanel.vue  # 竞技场资料卡（查 ID / 好友详情共用）
    │   └── ArenaDefencePanel.vue  # 竞技场防守阵容
    ├── layout/
    │   └── Layout.vue          # 主布局（侧边栏 + 顶栏公会切换 + 主题切换 + 修改密码弹窗）
    └── views/
        ├── Login.vue           # 登录页
        ├── Home.vue            # 首页
        ├── Dashboard.vue       # 会战仪表盘
        ├── Report.vue          # 出刀报告
        ├── Notice.vue          # 通知管理
        ├── BoxSupport.vue      # BOX / 助战（首页快捷入口进入）
        └── Arena.vue           # 竞技场中心（首页快捷入口进入）
```

---

## 🔗 后端对接说明

路由前缀 `/kanna_dependency`（`WebSetting.api_base`，由 `webui/api.py` 的 `APIRouter(prefix=...)` 挂载）。

| 后端路由 | 前端调用位置 | 说明 |
| --- | --- | --- |
| `POST /login` | `Login.vue` / `store/user.ts` | 账号密码登录，`Set-Cookie: token=...` |
| `POST /logout` | `store/user.ts` | 登出（后端删 cookie） |
| `POST /change_password` | `Layout.vue` | 修改密码（需旧密码，改完清其他设备登录态） |
| `GET /home` | `store/user.ts` / `Home.vue` | 用户信息 + 公会列表（每群带 `priority`）+ `account`（当前绑定的游戏账号，全局） |
| `GET /{group_id}/dashboard` | `Dashboard.vue` | 仪表盘（含档线、今日伤害排行） |
| `GET /{group_id}/boss_dao?boss=N` | `Dashboard.vue` | 某 BOSS 今日全部出刀记录 |
| `GET /{group_id}/rank_lines?ranks=&force=` | `Dashboard.vue` | 会战档线 |
| `GET /{group_id}/report` | `Report.vue` | 出刀报告 |
| `GET /{group_id}/notice` | `Notice.vue` | 通知列表 |
| `POST /set_notice` | `Dashboard.vue` / `Notice.vue` | 添加通知（预约 / 申请 / 挂树 / SL） |
| `POST /delete_notice` | `Notice.vue` | 取消通知 |
| `POST /delete_notice_special` | `Notice.vue` | 代人取消通知 |
| `POST /correct_dao` | `Report.vue` | 修正出刀类型 |
| `POST /{group_id}/bind_account` | `components/AccountBind.vue` | 绑定游戏账号（全局，URL 里的 group_id 只做访问校验） |
| `POST /{group_id}/unbind_account` | `components/AccountBind.vue` | 解绑游戏账号（对所有群生效） |
| `GET /{group_id}/monitor/accounts` | `Dashboard.vue` | 可用于开启监控的账号（只返回自己的） |
| `POST /{group_id}/monitor` | `Dashboard.vue` | 开 / 关出刀监控 |
| `GET /{group_id}/renew_dashboard`（SSE） | `Dashboard.vue` | 实时推送 |
| `GET /{group_id}/renew_report`（SSE） | `Report.vue` | 实时推送 |
| `GET /{group_id}/renew_notice`（SSE） | `Notice.vue` | 实时推送 |
| `GET /{group_id}/box/query?name=&include_missing=` | `BoxSupport.vue` | 个人 BOX 查询（`include_missing=false` 时不带未拥有占位）。返回里的 `enhance` 是练度快照（MP等级 / 属性强化 / 属性技能 / 职介等级），**纯读库**、随【刷新缓存】更新；没刷过时是 `null` |
| `GET /{group_id}/box/avatar/{unit_id}?star=&rarity=&battle_rarity=` | `GameUnitAvatar.vue` | 角色头像 PNG。带 `rarity` / `battle_rarity` 时后端会把星级直接烤进图（QQ 端出图、竞技场等还在用）；BOX / 助战页现在由前端画游戏样式头像，会去掉这两个参数、只要干净底图 |
| `GET /{group_id}/box/ex_equip_icon/{equipment_id}` | `BoxSupport.vue` | 会战 EX 装备图标 PNG |
| `GET /{group_id}/box/clan?name=` | `BoxSupport.vue` | 公会 BOX 查询 |
| `POST /{group_id}/refresh` | `BoxSupport.vue` | 一次刷新「个人 BOX + 本群公会助战」两份缓存（= 群里【刷新box缓存】+【刷新助战缓存】，**会顶号**，只登录一次） |
| `GET /{group_id}/support/clan?name=` | `BoxSupport.vue` | 公会助战一览 |
| `GET /{group_id}/support/mine` | `BoxSupport.vue` | 我的助战 |
| `POST /{group_id}/support/change` | `BoxSupport.vue` | 更换支援（= 群里【上XX支援】，**会顶号**）；body `{unit_id, mode, star?}`，`mode` 1 地下城 / 2 团队战·露娜塔 / 3 关卡，`star`（3/4/5，选填）= 调到该**战斗星级**（仅 5★ 角色能调，6★ 不能；非 5★ 会在挂支援前直接拒绝）；角色已经在该支援位时传 `star` 只调星、不重复挂。挂**团队战位（mode 2）**成功后还会用同一个已登录 client 顺手刷新本群公会助战缓存 |
| `GET /{group_id}/friend/list` | `BoxSupport.vue` | 好友列表（纯读缓存，不登录） |
| `POST /{group_id}/friend/refresh` | `BoxSupport.vue` | 刷新好友列表（**会顶号**） |
| `POST /{group_id}/friend/add` | `BoxSupport.vue` | 添加好友（发请求，**会顶号**）；body `{viewer_id}` |
| `POST /{group_id}/friend/remove` | `BoxSupport.vue` | 解除好友（**会顶号**）；body `{viewer_id}` |
| `GET /{group_id}/friend/profile?viewer_id=` | `BoxSupport.vue` | 好友资料（与竞技场查 ID 同结构；监控在跑时借监控 client，否则登录当前账号） |
| `GET /{group_id}/friend/requests` | `BoxSupport.vue` | 好友申请：待审核 + 申请中两份名单（**会顶号**；实时数据不落缓存） |
| `POST /{group_id}/friend/requests/accept` | `BoxSupport.vue` | 同意好友申请（**会顶号**）；body `{viewer_id}`，成功后顺手刷新好友列表缓存 |
| `POST /{group_id}/friend/requests/reject` | `BoxSupport.vue` | 拒绝好友申请（**会顶号**）；body `{viewer_id}` |
| `POST /{group_id}/friend/requests/cancel` | `BoxSupport.vue` | 撤回我发出的好友申请（**会顶号**）；body `{viewer_id}` |
| `GET /{group_id}/arena/status` | `Arena.vue` | 竞技场监控状态 + 提醒开关 |
| `POST /{group_id}/arena/setting` | `Arena.vue` | 开关竞技场 / 公主竞技场提醒 |
| `GET /{group_id}/arena/rank?page=&grand=` | `Arena.vue` | 竞技场排行榜 |
| `GET /{group_id}/arena/defence?rank=&grand=` | `Arena.vue` | 查防守 / 作业 |
| `GET /{group_id}/arena/player?rank=&grand=` | `Arena.vue` | 查玩家信息 |
| `GET /{group_id}/arena/cache` | `Arena.vue` | 公主竞技场防守缓存 |

> BOX / 助战、好友与竞技场的接口分别实现在 `webui/box_arena_api.py` 和
> `webui/friend_api.py`（单独成模块，由 `webui/api.py` 在 `include_router` 之前
> import 并挂载），响应模型在 `webui/web_model.py`。

### BOX / 助战头像（游戏样式）

`components/GameUnitAvatar.vue` 按游戏「角色一览 / 支援设定」里的单位头像画：

| 层次 | 资源 | 说明 |
| --- | --- | --- |
| 底图 | 后端 `box/avatar` PNG | 前端请求前去掉 `rarity` / `battle_rarity`，避免后端把星星烤进图里 |
| 品级框 | `assets/unit_icon/frame_{1..10}.png` | 按 `rank` 取档（线上角色都是 Rank 38 → 第 10 档粉色框） |
| 左下星级 | `assets/unit_icon/star_{1..6}.png` | 6★ 固定粉色第 6 颗；其余用战斗星级（`battle_rarity`，0 时回退 `rarity`） |
| 右下角标 | `assets/unit_icon/role_{1..8}.png` + `talent_{1..5}.png` | 职业（攻击/破防/增益/减益/强化/治疗/坦克/干扰）+ 属性（火/水/风/光/暗），数据在 `data/unit_talent_role.json` |

职业 / 属性是**静态游戏数据**，刻意放前端（而不是加后端字段），这样改样式、补角色都不用重启 bot。
数据来源是游戏主库（autopcr 项目 `cache/db/*.db` 里的 `unit_talent` / `unit_role_data` 两张表），
图标来源是游戏资源 CDN 的 NGUI 图集（`atlasngui_atlascommon` / `atlasunitcommontalent` /
`atlaspromotionframe`），用 autopcr 的 `assetmgr` + UnityPy 解包后按图集 sprite 表裁出来。

> 以后游戏更新、要补新角色或新图标时：用 autopcr 重新下载主库 / 图集 → 导出
> `unit_talent_role.json` 与 `assets/unit_icon/*.png` 覆盖即可，前端代码不用动。

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

退群 / 被踢时 bot 会通过 `group_decrease` 事件**自动删掉**该成员在本群的绑定记录，
所以人一旦不在群里，这些 `/{group_id}/...` 路由就会回 403 —— 这正是「防止退群的人
还能看原公会进度」的关键：绑定记录同时是「这个人还在这个群」的唯一凭证。

事件会漏（bot 掉线 / 协议端没上报 / 本群禁用了「成员管理」服务），所以还有一条兜底：
【清理退群绑定】（群主 / 群管）手动对账 + 每天 4:30 的全群自动对账
（`member/__init__.py: clean_stale_members`）。它拉一次群成员列表逐条比对，**三条护栏**
保证接口抽风时不会误删绑定：名单为空或报错不动手、**名单里没有 bot 自己也不动手**
（说明这份名单是残缺的）、只删名单里确实没有的 QQ。

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
