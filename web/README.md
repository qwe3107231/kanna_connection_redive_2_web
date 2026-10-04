# 环奈连结 R · Web 前端（KCRR WebUI）

基于 **Vue 3 + TypeScript + Vite + Element Plus + Pinia + ECharts** 的 KCRR 公会战管理系统前端。

对接后端：本仓库根目录的 `webui/`（FastAPI，默认监听 `0.0.0.0:12138`）。
界面截图见仓库根目录的 [readme.md](../readme.md#-网页端界面预览)。

---

## 🌟 功能

### 🔐 登录与账号

- **机器人私发链接自动登录**：URL 携带 `account` / `password`，打开即登录（`router/index.ts` 的路由守卫会无条件放行，避免浏览器里的旧登录态把人顶成别人）
- 首次登录用的是 QQ 私聊【网页端登录】下发的**临时密码**（7 天有效）；登录后可在右上角**修改密码**，改完自己不再过期，其他设备上的登录态会失效
- **登出**：后端立即失效 token + 清理本地登录标记

### 🏠 首页

- 欢迎卡片：昵称 / QQ 号 / 身份 / 签名，右侧统计「我的公会数」「最高权限」
- **游戏账号**（`components/AccountBind.vue`）：显示当前绑定的角色 + 服务器，右侧「换绑」/「解绑」
  - 账号是**全局**的（一个 QQ 一个号，绑一次所有群通用），所以放在首页而不是某个公会的仪表盘里
  - 未绑号 / 一个公会都没有时按钮禁用并给出引导；绑 / 解绑成功后自动重新拉一次 `/home`
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
- SSE 实时刷新（`renew_dashboard`）

> 「绑定游戏账号」的入口在**首页**（`components/AccountBind.vue`），不在仪表盘上 ——
> 账号是全局的，和当前看的是哪个公会无关。

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

### 📦 BOX / 助战

对应 QQ 端的 `support_query`（精准助战）模块。**查询纯读本地缓存**（`PlayerUnit` / `SupportUnit`），
一次游戏接口都不打 —— 不会顶号，也不要求出刀监控在跑。
代价是数据新鲜度取决于上一次刷新的时间；页面上有**刷新缓存**按钮可以直接刷
（等价于群里的【刷新box缓存】/【刷新助战缓存】，**会短暂顶号**，见下）。

- **个人 BOX**：默认显示整个 box（含未拥有）；也可以输入角色名只看某一个
- **公会 BOX**：本群所有绑定成员里谁有该角色（不支持「所有」）
- **公会助战**：默认显示本群缓存的**全部**公会战助战（QQ 端【精确助战】）；可输入角色名筛选
- **我的助战**：当前登录用户挂着的助战，照游戏「支援设定」界面排成三栏**卡片**
  （**地下城 / 团队战·露娜之塔 / 冒险**，每栏固定 2 个位，**空位也占一格**）
  （QQ 端【我的助战】）。卡片上是头像 + 角色名 + 角色等级 + 角色 Rank，
  底下的按钮是**更换支援**（空位是「设置支援」）

**网页端不复用 QQ 端那套 PIL 出图**：那边一次把整个 box 拼成一张大图，几百个角色时
又慢又费带宽。网页端只拿结构化数据，渲染成**头像网格**，点开头像弹出详情面板
（星级 / 战斗星级 / 等级 / 品级 / 专武 / 好感 / 技能 / 6 格装备 / 3 件会战 EX 装备）。
QQ 群指令的行为一个字都没改。

- 头像是 `<img>` 单独请求
  `/{group_id}/box/avatar/{unit_id}?star=&rarity=&battle_rarity=`，浏览器缓存一周
  - `star` 是**头像档位** 1/3/6（决定用哪张底图）；`rarity` 是**真实星级** 1~6；
    `battle_rarity` 是**战斗星级**（会战「调星」后的星级，0 = 没调过）
  - 传了 `rarity` 就会在头像底部叠一排小星星，**画法与 QQ 端 BOX 出图
    （`create_img.draw_star`）一致**：
    **金色 = 战斗星级**、**亮蓝 = 已拥有但被调星调下去的**、**淡蓝 = 还没到**；
    6★ 时 5 颗全金 + 第 6 格一颗粉色「6 星」标记
  - 素材用的是 QQ 端 BOX 出图的同一份（模块自带
    `resource/img/support_query/16px-星星{蓝,无,6}.png`）。
    **不是** `priconne/gadget/star*` —— 那一套只有 金/灰/粉 三色，画不出调星的亮蓝
  - 合成结果落在**模块自己的** `resource/img/support_query/starred_icon/`，
    按 `(unit_id, star, rarity, battle_rarity)` 缓存，
    **绝不覆盖 `priconne/unit/` 下的原图**（QQ 端出图在用）
  - `rarity=0`（未拥有的占位条目）不画星星 —— 没拥有就不知道星级，
    画成全灰反而像「0 星」
- **会战 EX 装备也带图标**：`/{group_id}/box/ex_equip_icon/{equipment_id}`，
  和 QQ 端出图用**同一份缓存资源**（`resource/img/support_query/ex_equipment/{id}.png`），
  本地没有就按需从 pcredivewiki 下载并存回同一目录，最后退回 `unknown.png`
- **个人 BOX 的「未拥有」角色会灰度列出**（`owned=false` 占位条目），一眼看出缺什么；
  右上角开关可以关掉。未拥有的头像点开只显示「未拥有」，没有等级/装备数据
- 公会 BOX / 助战里同一角色常被多人拥有，所以这两个 tab 的头像下方带玩家名
- **我的助战**照游戏「支援设定」界面排成三栏**卡片**：每栏固定 2 个位、空位也占一格
  （虚线框 + 「未设定」）。列的顺序与库里助战位编号的对应关系写死在
  `BoxSupport.vue` 的 `SUPPORT_COLUMNS` 里（**地下城 = 位 3/4 · mode 1**、
  **团队战·露娜之塔 = 位 5/6 · mode 2**、**冒险 = 位 1/2 · mode 3**），
  和后端 `_SUPPORT_POSITION_GROUP` 一致；窄屏自动落成一列。库里出现认不出来的
  助战位时会单独兜一栏「其他」（那栏没有对应 mode，按钮禁用），不让角色凭空消失
- **更换支援按钮**（`POST /{group_id}/support/change`）：点开弹窗从**自己的 BOX** 里
  搜角色名选一个（只列 **Lv>10** 的 —— 游戏规定 Lv10 以上才能当支援），确定后挂上去。
  对应 QQ 端【上地下城支援】/【上公会战支援】/【上关卡支援】，后端调的是同一个
  `support_query.util.change_support_unit`。**这是写操作**：会登录你的游戏账号并真的
  改游戏里的支援设定（**顶号**），所以确认框里写明了；栏位满了会顶掉挂得最久的那一个
  （游戏侧规则：挂满 30 分钟后才允许换）。成功后后端会**顺手把本地缓存的助战位改掉**
  （`dal.set_player_support_positions`，只动 `support_position` 一列），前端重查一次就是
  最新的，不用再点【刷新 BOX 缓存】。选了「本来就挂在这个位」的角色会被前端拦下来
  —— 后端那一步虽然也不会真改，但已经登录过账号、白顶一次号。
  另外挂**团队战位（mode 2）**成功时，还会用**同一个已登录的 client** 顺手把本群的
  **公会助战缓存**重拉一次（`support_query.util.save_clan_support`）—— 否则换完支援，
  公会助战页显示的还是旧的（新角色不在里面、被顶掉的还留着）。
  只在 mode 2 做：公会助战缓存里只有团队战栏（线上库实测每人恰好 2 条 = 游戏侧 clan 位
  3/4，`support_unit_list_2` **不含自己**，自己那两条是刷新时补进去的），地下城 / 冒险栏
  的更换本来就不进这份缓存。这一步**不额外登录、不顶第二次号**，失败只记日志
- **好感**：详情里平时只显示短标签（`8 级` / `加成`），**点一下才弹出完整加成文字**
  （「物理攻击力：1055，回复量上升：35」太长，平铺在表格里不好看）。
  注意：**游戏接口不给助战单位的好感等级**（好感等级只在玩家自己账号的
  `user_chara_info` 里，助战接口只返回 `bonus_param` 加成数值），所以助战**只有
  「加成」短标签、没有等级**；个人 BOX / 我的助战反过来只有等级、没有加成文字。
- **刷新缓存按钮**（`POST /{group_id}/refresh`）：右上角只有这一个按钮，点一下把
  **「个人 BOX」和「本群公会助战」两份缓存一起刷**（`PlayerUnit` + `SupportUnit`），
  等价于在群里先后发【刷新box缓存】和【刷新助战缓存】。
  **会真的登录你自己的游戏账号（顶号）**，所以点之前先弹确认框；成功后自动重查一次。
  两份**共用同一次登录**（两次取数复用同一个 client），不会比原来只刷一份更慢。
  后端**不重写刷新逻辑**：直接调 `support_query.util.refresh_box_and_support`，
  它就是 QQ 指令用的那批底层函数拼起来的，两边行为天然一致。
  两份是分开写的：公会助战那份失败（例如**现在不是会战期间**）**不影响个人 BOX** ——
  这时 `ok` 仍是 true，原因在 `support_error` 里，前端用 warning 样式展示完整文案。
  并发闸门 `_REFRESHING` 有**两层键**：`(kind, 目标)` 挡同一目标重复点，
  `("login", QQ)` 挡**同一个账号**被并发登录 —— 刷新缓存和更换支援都会
  `login.query()` 登同一个号，撞在一起只会互相顶号，所以它们共用这一把闸门；
  不同 QQ 的账号互不影响，仍然可以并行

### ⚔️ 竞技场中心

对应 QQ 端的 `jjckiller`（竞技场杀手）模块。排行榜 / 查防守 / 查 ID 都要打游戏接口，
所以**复用正在运行的竞技场监控已经登录好的 client**（`arena_manager`）；没有监控在跑时
只提示去群里开，绝不自己登录游戏（会顶号）。

- **监控状态 + 提醒开关**：监控在不在跑、当前排名 / 场次 / 监控编号；开关竞技场 / 公主竞技场提醒
- **排行榜**：每页 10 名，1~5 页（需监控在跑）
- **查防守 / 查 ID**：查指定排名的防守阵容与作业 / 玩家信息（需监控在跑）
- **防守缓存**：监控过程中记录的公主竞技场对手防守队伍（纯读库，不需要监控在跑）

> 这两个页面**只挂在首页「快捷入口」**，不进侧边栏和手机底部导航（保持底部 4 个 tab 不挤）。

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
| `GET /{group_id}/box/query?name=&include_missing=` | `BoxSupport.vue` | 个人 BOX 查询（`include_missing=false` 时不带未拥有占位） |
| `GET /{group_id}/box/avatar/{unit_id}?star=&rarity=&battle_rarity=` | `BoxSupport.vue` | 角色头像 PNG（`<img>` 直接请求；带星级时叠「战斗星级金色 / 调星亮蓝 / 未达到淡蓝」） |
| `GET /{group_id}/box/ex_equip_icon/{equipment_id}` | `BoxSupport.vue` | 会战 EX 装备图标 PNG |
| `GET /{group_id}/box/clan?name=` | `BoxSupport.vue` | 公会 BOX 查询 |
| `POST /{group_id}/refresh` | `BoxSupport.vue` | 一次刷新「个人 BOX + 本群公会助战」两份缓存（= 群里【刷新box缓存】+【刷新助战缓存】，**会顶号**，只登录一次） |
| `GET /{group_id}/support/clan?name=` | `BoxSupport.vue` | 公会助战一览 |
| `GET /{group_id}/support/mine` | `BoxSupport.vue` | 我的助战 |
| `POST /{group_id}/support/change` | `BoxSupport.vue` | 更换支援（= 群里【上XX支援】，**会顶号**）；body `{unit_id, mode}`，`mode` 1 地下城 / 2 团队战·露娜塔 / 3 关卡。挂**团队战位（mode 2）**成功后还会用同一个已登录 client 顺手刷新本群公会助战缓存 |
| `GET /{group_id}/arena/status` | `Arena.vue` | 竞技场监控状态 + 提醒开关 |
| `POST /{group_id}/arena/setting` | `Arena.vue` | 开关竞技场 / 公主竞技场提醒 |
| `GET /{group_id}/arena/rank?page=&grand=` | `Arena.vue` | 竞技场排行榜 |
| `GET /{group_id}/arena/defence?rank=&grand=` | `Arena.vue` | 查防守 / 作业 |
| `GET /{group_id}/arena/player?rank=&grand=` | `Arena.vue` | 查玩家信息 |
| `GET /{group_id}/arena/cache` | `Arena.vue` | 公主竞技场防守缓存 |

> BOX / 助战与竞技场的接口实现在 `webui/box_arena_api.py`（单独成模块，由 `webui/api.py`
> 在 `include_router` 之前 import 并挂载），响应模型在 `webui/web_model.py`。

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
