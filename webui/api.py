import asyncio
import json
import secrets
import threading
import time
from typing import Dict

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware

from ..util.tools import daoflag2str, anywhere_send

from ..clanbattle import clanbattle_info, notice_update_time
from ..util.auto_boss import clan_boss_info
from ..clanbattle.base import DEFAULT_RANK_LINES, clanbattle_report, query_rank_lines
from ..database.dal import CookieCache, SLDao, pcr_sqla
from ..basedata import NoticeType
from ..setting import WebSetting
from .util import *
from .web_model import *
from nonebot import on_startup

from sse_starlette.sse import EventSourceResponse

app = FastAPI()

# nonebot 主事件循环引用：游戏 client（httpx/asyncio.Lock）都绑定在该 loop 上。
# uvicorn 运行在独立线程有自己的 loop，任何直接 await 游戏 client 的写法都会
# 触发 "bound to a different event loop" 并污染游戏会话（请求正在处理中）。
# 网页端涉及游戏客户端调用时，必须用 run_coroutine_threadsafe 投递回主循环执行。
main_event_loop: asyncio.AbstractEventLoop = None

origins = [
    "http://localhost",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:3141",
    "http://yourhost:3141",
    # 局域网部署地址（前端 5173）
    f"http://{WebSetting.web_host.value}:{WebSetting.web_port.value}",
    # 兼容使用默认 3141 生产端口的部署
    f"http://{WebSetting.web_host.value}:3141",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# FastAPI 路由统一添加 /kanna_dependency 前缀（通过 APIRouter 实现，避免自身 mount 自身）
from fastapi import APIRouter
from starlette.routing import Mount

# 先移除所有已直接注册到 app 的路由（目前尚无，因为我们下面统一用 router）
# 做法：创建一个 root_router 承载全部业务路由，再用 /kanna_dependency 前缀挂载
api_router = APIRouter(prefix=WebSetting.api_base.value)

update_time: Dict[str, Dict[str, int]] = {"report": {}, "notice": {}, "dashboard": {}}
report_time = update_time["report"]
notice_time = update_time["notice"]
dashboard_time = update_time["dashboard"]


@api_router.post("/login")
async def check_user(user: User, response: Response):
    if web_user := await pcr_sqla.web_check_user(user.account, user.password):
        if web_user.temp and time.time() - web_user.create_time > 7 * 24 * 3600:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, "临时密码过期，请重新获取或修改密码"
            )
        token = secrets.token_urlsafe(16)
        # 注意：
        # 1) 必须显式 path="/"，否则浏览器会按请求路径默认 path=/kanna_dependency，
        #    导致前端路由（/#/home）下 document.cookie 读不到 token，跳转失效
        # 2) httponly 关闭并加 secure 的说明：
        #    前端 dev (5173) 是 Vite 服务器，后端 API 通过 vite 代理 (代理到 12138)；
        #    直接使用 httponly cookie 在 Vite 代理下可能因 host 不同导致"浏览器已写入但
        #    document.cookie 读不到"的同步判断失效，这里改用非 httponly 以便前端可以
        #    通过 localStorage 同步持久化标记，同时 token 本身仍由后端校验。
        #    如果是生产 HTTPS 部署，建议把 httponly=True + secure=True 再打开。
        response.set_cookie(
            "token", token, expires=3600 * 24 * 7, httponly=False, path="/",
            samesite="lax",
        )
        await pcr_sqla.web_add_cookie(token, web_user.account)
    else:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "密码错误")


@api_router.post("/logout")
async def logout_user(response: Response, token: CookieCache = Depends(verify_cookie)):
    # 先清服务端记录，再让浏览器删 cookie
    try:
        await pcr_sqla.web_delete_cookie(token=token.cookie)
    except Exception:
        pass
    response.delete_cookie("token", path="/", samesite="lax")
    response.delete_cookie("token", path="/kanna_dependency")
    return "ok"


@api_router.get("/home")
async def home_info(token: CookieCache = Depends(verify_cookie)):
    user_id = int(token.user_id)
    response = HomeResponse()
    response.user_id = user_id
    if web_user := await pcr_sqla.web_query_user(user_id):
        response.priority = web_user.priority

    if pcr_user := (await pcr_sqla.query_account(user_id)):
        pcr_user = pcr_user[0]
        response.name = pcr_user.name
        # 是否已绑定游戏账号（前端据此禁用预约/申请/挂树入口）
        response.has_account = True
    if groups := await pcr_sqla.get_member_group(user_id):
        response.clan = [group.dict() for group in groups]
    return response.dict()


@api_router.get("/{group_id}/dashboard")
async def dashboard_info(group_id: int, token: CookieCache = Depends(verify_cookie)):
    now = int(time.time())
    boss_info = clan_boss_info.boss_info
    user_id = int(token.user_id)
    response = DashboardResponse()
    response.boss = [
        BossInfoCounter(
            name=boss_info[i].name,
            id=boss_info[i].boss_id,
        )
        for i in range(5)
    ]
    response.user_id = user_id
    if web_user := await pcr_sqla.web_query_user(user_id):
        response.priority = web_user.priority

    if clan_info := clanbattle_info.get(group_id, None):
        response.clan_name = clan_info.clan_name
        response.stage = f"{clan_info.period}面{clan_info.lap_num}周目"
        response.rank = clan_info.rank
        response.name = clan_info.user_id
        # 出刀监控人 QQ：前端据此禁用非监控人的"取消出刀监控"按钮
        response.monitor_user_id = int(getattr(clan_info, "user_id", 0) or 0)
        if clan_info.loop_check:
            response.state = "开启" + (
                "(高占用)" if now - clan_info.loop_check > 30 else ""
            )
            response.boss = [
                BossInfoCounter(
                    name=boss_info[i].name,
                    id=boss_info[i].boss_id,
                    fighter=boss.fighter_num,
                    current_hp=boss.current_hp,
                    max_hp=boss.max_hp,
                    lap=boss.lap_num,
                )
                for i, boss in enumerate(clan_info.boss)
            ]
    # 出刀监控开启时带上完整公会名单，"今日出刀分布"才能显示 0 刀（未出刀）成员
    members = clan_info.members if clan_info else {}
    if dao_data := await pcr_sqla.get_day_rcords(now, group_id):
        response.dao, response.report = await get_day_dao(dao_data, members)
        # 取今日出刀按时间倒序的最近 20 条，给仪表盘"最近出刀"卡片用
        response.last_dao = build_last_dao(dao_data, 20)
    if dao_data := await pcr_sqla.get_day_rcords(now - 3600 * 24, group_id):
        response.yesterday_dao, _ = await get_day_dao(dao_data)

    if subscribes := await pcr_sqla.get_notice(NoticeType.subscribe.value, group_id):
        for subscribe in subscribes:
            response.boss[subscribe.boss - 1].subscribe += 1
    if applies := await pcr_sqla.get_notice(NoticeType.apply.value, group_id):
        for apply in applies:
            response.boss[apply.boss - 1].apply += 1
    if trees := await pcr_sqla.get_notice(NoticeType.tree.value, group_id):
        for tree in trees:
            response.boss[tree.boss - 1].tree += 1
    response.day_num = await pcr_sqla.get_clan_day(group_id)
    return response.dict()


@api_router.get("/{group_id}/boss_dao")
async def boss_dao_records(
    group_id: int, boss: int, token: CookieCache = Depends(verify_cookie)
):
    """指定 BOSS 本次会战周期内的全部出刀记录，按时间倒序（BOSS 卡片"出刀记录"弹窗用）"""
    if not 1 <= boss <= 5:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "BOSS 编号必须是 1~5")
    # 本次会战 = 最近一次出刀时间的 pcr 日期往前推 5 天（与 get_clan_day 口径一致）
    period = await pcr_sqla.get_all_records(group_id)
    filtered = [r for r in period if r.boss == boss] if period else []
    # build_last_dao 本身就是按时间倒序转换，limit 传记录总数即"全部返回"
    return build_last_dao(filtered, max(len(filtered), 1))


@api_router.get("/{group_id}/rank_lines")
async def get_rank_lines(
    group_id: int,
    ranks: str = None,
    token: CookieCache = Depends(verify_cookie),
):
    """查档线：本届会战指定排名的分数线（仅会战期间有效），ranks 为逗号分隔自定义排名"""
    clan_info = clanbattle_info.get(group_id)
    if not clan_info or not clan_info.client:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "出刀监控未开启，无法查询档线")
    if ranks:
        try:
            targets = [int(x.strip()) for x in ranks.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "ranks 参数格式错误，应为逗号分隔数字，如 500,2000"
            )
    else:
        targets = list(DEFAULT_RANK_LINES)
    # 游戏 client 绑定在 nonebot 主循环，必须投递回去执行（与监控循环排队互斥）
    data = await call_in_main_loop(query_rank_lines(clan_info, targets))
    return RankLineResponse(
        clan_battle_id=data["clan_battle_id"],
        lines=[RankLine(**line) if line else None for line in data["lines"]],
        my=RankLine(**data["my"]),
        default_ranks=list(DEFAULT_RANK_LINES),
    )


async def call_in_main_loop(coro, timeout: float = 90):
    """把涉及游戏 client 的协程投递回 nonebot 主事件循环执行（uvicorn loop 不能直接 await）"""
    if main_event_loop is None or main_event_loop.is_closed():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "机器人主循环尚未就绪，请稍后再试"
        )
    future = asyncio.run_coroutine_threadsafe(coro, main_event_loop)
    try:
        return await asyncio.wrap_future(future)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"游戏接口调用失败：{e}")


@api_router.get("/{group_id}/notice")
async def clan_notice(group_id: int, token: CookieCache = Depends(verify_cookie)):
    user_id = int(token.user_id)
    response = NoticeResponse()
    response.user_id = user_id
    if web_user := await pcr_sqla.web_query_user(user_id):
        response.priority = web_user.priority
    if subscribe := await pcr_sqla.get_notice(NoticeType.subscribe.value, group_id):
        response.subscribe = subscribe
    if apply := await pcr_sqla.get_notice(NoticeType.apply.value, group_id):
        response.apply = apply
    if tree := await pcr_sqla.get_notice(NoticeType.tree.value, group_id):
        response.tree = tree
    return response.dict()


@api_router.get("/{group_id}/report")
async def clan_report(group_id: int, token: CookieCache = Depends(verify_cookie)):
    user_id = int(token.user_id)
    response = ReportResponse()
    response.user_id = user_id
    if web_user := await pcr_sqla.web_query_user(user_id):
        response.priority = web_user.priority
    if info := await pcr_sqla.get_all_records(group_id):
        players, all_damage, all_score = clanbattle_report(
            info, await pcr_sqla.get_max_dao(group_id)
        )
        response.all = [
            DaoInfo(
                name=member[1],
                damage=member[3],
                score=member[4],
                dao=member[2],
                damage_rate=f"{member[3]/all_damage*100:.2f}%",
                score_rate=f"{member[4]/all_score*100:.2f}%",
            )
            for member in players
        ]
        response.detail = [
            DaoInfo(
                name=player.name,
                damage=player.damage,
                score=int(
                    clan_boss_info.get_boss_rate(player.lap, player.boss)
                    * player.damage
                ),
                type=daoflag2str(player.flag),
                date=player.time,
                boss=player.boss,
                lap=player.lap,
                dao_id=player.battle_log_id,
            )
            for player in info[::-1]
        ]
    if pcr_user := (await pcr_sqla.query_account(user_id)):
        pcr_user = pcr_user[0]
        response.name = pcr_user.name
        if info := await pcr_sqla.get_player_records(pcr_user.viewer_id, 5, group_id):
            knife = 0
            for dao in info:
                knife += 1 if dao.flag == 0 else 0.5
                response.me.append(
                    DaoInfo(
                        dao=knife,
                        damage=dao.damage,
                        score=int(
                            clan_boss_info.get_boss_rate(dao.lap, dao.boss) * dao.damage
                        ),
                        type=daoflag2str(dao.flag),
                        boss=dao.boss,
                        lap=dao.lap,
                        date=dao.time,
                        dao_id=dao.battle_log_id,
                    )
                )
        response.me = response.me[::-1]
    return response.dict()


@api_router.post("/set_notice")
async def set_notice(notice: NoticeCache, token: CookieCache = Depends(verify_cookie)):
    user_id = int(token.user_id)
    notice.user_id = user_id
    # 通知管理操作仅限网页端管理员（priority >= 1），普通成员（priority 0）只读
    web_user = await pcr_sqla.web_query_user(user_id)
    if not web_user or (web_user.priority or 0) < 1:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "权限不足：仅网页端管理员可管理通知"
        )
    # 预约/挂树/申请出刀必须先绑定游戏账号（未绑定用户没有出刀身份，不允许发起）
    if notice.notice_type in (
        NoticeType.subscribe.value,
        NoticeType.tree.value,
        NoticeType.apply.value,
    ) and not await pcr_sqla.query_account(user_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "未绑定游戏账号，请先在QQ对机器人发送【绑定账号帮助】完成绑定",
        )
    if notice.notice_type == NoticeType.sl.value:
        if not await pcr_sqla.add_sl(
            SLDao(group_id=notice.group_id, user_id=user_id, time=int(time.time()))
        ):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "已经sl过了")
    else:
        await pcr_sqla.add_notice(notice)
    notice_update_time[int(notice.group_id)] = int(time.time())
    await anywhere_send(
        get_notice_msg(
            notice.notice_type, user_id, notice.boss, notice.lap, notice.text
        ),
        group_id=notice.group_id,
    )
    return "成功"


@api_router.post("/delete_notice")
async def set_notice(notice: NoticeCache, token: CookieCache = Depends(verify_cookie)):
    user_id = int(token.user_id)
    # 通知管理操作仅限网页端管理员（priority >= 1），普通成员（priority 0）只读
    web_user = await pcr_sqla.web_query_user(user_id)
    if not web_user or (web_user.priority or 0) < 1:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "权限不足：仅网页端管理员可管理通知"
        )
    notice.user_id = user_id
    if notice.notice_type == NoticeType.sl.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "那你自己心里清楚")
    else:
        await pcr_sqla.delete_notice(
            notice.notice_type,
            notice.group_id,
            notice.boss,
            user_id=user_id,
        )
    notice_update_time[int(notice.group_id)] = int(time.time())
    await anywhere_send(
        cancel_notice_msg(notice.notice_type, user_id, notice.boss, user_id),
        group_id=notice.group_id,
    )
    return "取消成功"


@api_router.post("/delete_notice_special")
async def set_notice(
    notice: SpecialNoticeForm, token: CookieCache = Depends(verify_cookie)
):
    user_id = int(token.user_id)
    if user_id != notice.user_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "权限不足，如果管理请等待权限系统完善"
        )
    else:
        await pcr_sqla.delete_notice(
            notice.notice_type,
            notice.group_id,
            notice.boss,
            user_id=user_id,
            lap=notice.lap,
        )
    notice_update_time[int(notice.group_id)] = int(time.time())
    await anywhere_send(
        cancel_notice_msg(
            notice.notice_type, notice.user_id, notice.boss, operator=user_id
        ),
        group_id=notice.group_id,
    )
    return "取消成功"


@api_router.get("/{group_id}/renew_dashboard")
async def renew_dashboard(group_id: int, token: CookieCache = Depends(verify_cookie)):
    async def dashboard_generator():
        dashboard_time[token.token] = int(time.time())
        notice_time[token.token] = int(time.time())
        while True:
            await asyncio.sleep(3)  # 3 秒轮询一次变化标记，加速网页端实时刷新
            if clan_info := clanbattle_info.get(group_id, None):
                # 出刀入库(dao_update_time)或战斗人数变化(fighter_update_time)都推送仪表盘
                latest = max(
                    clan_info.dao_update_time,
                    getattr(clan_info, "fighter_update_time", 0),
                )
                if latest > dashboard_time[token.token]:
                    dashboard_time[token.token] = latest
                    yield json.dumps(await dashboard_info(group_id, token))
                    continue
            if update_time := notice_update_time.get(group_id, 0):
                if update_time > notice_time[token.token]:
                    notice_time[token.token] = update_time
                    yield json.dumps(await dashboard_info(group_id, token))

    return EventSourceResponse(content=dashboard_generator())


@api_router.get("/{group_id}/renew_report")
async def renew_report(group_id: int, token: CookieCache = Depends(verify_cookie)):
    async def report_generator():
        report_time[token.token] = int(time.time())
        while True:
            await asyncio.sleep(3)  # 3 秒轮询一次变化标记，加速网页端实时刷新
            if clan_info := clanbattle_info.get(group_id, None):
                if clan_info.dao_update_time > report_time[token.token]:
                    yield json.dumps(await clan_report(group_id, token))
                    report_time[token.token] = clan_info.dao_update_time
            if not report_time[token.token]:
                yield json.dumps(await clan_report(group_id, token))
                report_time[token.token] = int(time.time())

    return EventSourceResponse(content=report_generator())


@api_router.get("/{group_id}/renew_notice")
async def renew_notice(group_id: int, token: CookieCache = Depends(verify_cookie)):
    async def notice_generator():
        notice_time[token.token] = int(time.time())
        while True:
            await asyncio.sleep(3)  # 3 秒轮询一次变化标记，加速网页端实时刷新
            if update_time := notice_update_time.get(group_id, 0):
                if update_time > notice_time[token.token]:
                    yield json.dumps(await clan_notice(group_id, token))
                    notice_time[token.token] = update_time

    return EventSourceResponse(content=notice_generator())


@api_router.post("/correct_dao")
async def events(correct: CorrectDaoInfo, token: CookieCache = Depends(verify_cookie)):
    # 修正出刀类型仅限网页端管理员（priority >= 1），普通成员（priority 0）只读
    user_id = int(token.user_id)
    web_user = await pcr_sqla.web_query_user(user_id)
    if not web_user or (web_user.priority or 0) < 1:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "权限不足：仅网页端管理员可修正出刀类型"
        )
    if await pcr_sqla.correct_dao(
        correct.dao_id,
        0 if correct.type == "完整刀" else 1 if correct.type == "尾刀" else 0.5,
        correct.group_id,
    ):
        report_time[token.token] = 0
        return "修改成功"
    else:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "请检查你输入了正确的出刀编号")


@api_router.get("/{group_id}/monitor/accounts")
async def monitor_list_accounts(
    group_id: int, token: CookieCache = Depends(verify_cookie)
):
    """方案A：只列出"当前登录QQ号自己绑定"的角色账号，供开启出刀监控下拉选。"""
    user_id = int(token.user_id)
    accounts = await pcr_sqla.query_account(user_id)
    if not accounts:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "未绑定任何角色账号，请先在QQ上对机器人发送【绑定账号帮助】完成绑定后再开启",
        )
    from .web_model import MonitorAccountOption

    return [
        MonitorAccountOption(
            account_id=acc.id,
            name=acc.name or "未命名",
            platform=acc.platform,
            viewer_id=acc.viewer_id,
        ).dict()
        for acc in accounts
        if acc.id is not None
    ]


@api_router.post("/{group_id}/monitor")
async def monitor_switch(
    group_id: int,
    form: MonitorActionForm,
    token: CookieCache = Depends(verify_cookie),
):
    """
    出刀监控开关（方案A：只允许当前登录QQ号，用自己绑定的账号开启）
      - action='off' 取消：当前登录QQ号 == 监控人本人，或 群管理员/机器人管理，才允许
      - action='on'  开启：必须用自己绑定账号列表里的 account_id，并且成功登录后丢进 clanbattle_pool
    """
    from hoshino import priv  # 延迟导入，避免 web 插件先于 hoshino 核心的导入环

    user_id = int(token.user_id)

    # —— 关闭监控 ——
    if form.action == "off":
        if group_id not in clanbattle_info:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "本群从未开启过出刀监控")
        clan_info = clanbattle_info[group_id]
        if not clan_info.loop_check:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "出刀监控当前未运行")

        # 权限：监控人本人，或 ADMIN
        is_monitor_owner = user_id == clan_info.user_id
        # 注意：priv.check_priv 需要一个 HoshinoBot CQEvent；这里没有，我们用内置的"机器人管理权限等级"兜底：
        # 优先看 web_user.priority 是否 ADMIN 级（>=2）；否则就严格要求是监控人本人
        web_is_admin = False
        if web_user := await pcr_sqla.web_query_user(user_id):
            web_is_admin = bool(getattr(web_user, "priority", 0) or 0) >= 2
        if (not is_monitor_owner) and (not web_is_admin):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "不是监控人也不是管理员，无法取消")

        clan_info.loop_num += 1  # 和 QQ 指令【取消出刀监控】等价：让下一轮循环的 loop_num 比对失败，自身退出
        # 立刻把前端可见的状态置为"关闭"
        clan_info.loop_check = 0
        return "已取消出刀监控，稍后会自动停止（最多等待一轮循环）"

    # —— 开启监控 ——
    if form.action != "on":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"未知 action: {form.action}")
    if form.account_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择要用于启动监控的角色账号")

    # 1) 确保这个 account_id 就是当前登录用户自己的（方案A硬约束）
    my_accounts = await pcr_sqla.query_account(user_id)
    account = next((a for a in my_accounts if a.id == form.account_id), None)
    if account is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "只能使用您自己绑定的角色账号开启出刀监控（方案A约束）",
        )

    # 2) 从 clanbattle 包延迟拿启动依赖（防止 web 插件先于 clanbattle 插件启动造成导入环）
    try:
        from ..clanbattle import clanbattle_info as _ci_mirror, clanbattle_pool
        from ..clanbattle.model import ClanBattle, ClanbattleItem, PrioritizedQueryItem
        from ..login import query
    except Exception as e:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"clanbattle 插件尚未就绪，请稍后再试（{e}）",
        )

    # 3) 初始化 ClanBattle（完全对齐 QQ【出刀监控】指令逻辑）
    if group_id not in _ci_mirror:
        _ci_mirror[group_id] = ClanBattle(group_id)
    clan_info = _ci_mirror[group_id]

    # 先尝试普通登录；失败再尝试 is_force=True 重新拿 access_key；再失败就拒绝
    # （query 登录流程与 clan_info.init 都涉及游戏 client 网络请求，必须整体投递回 nonebot 主循环）
    async def _init_monitor(is_force: bool = False):
        access = await query(account, is_force)
        await clan_info.init(access, user_id, 0)

    try:
        await call_in_main_loop(_init_monitor(False))
    except Exception:
        try:
            await call_in_main_loop(_init_monitor(True))
        except Exception as e:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                f"登录角色账号失败，请确认账号密码有效或在QQ上尝试解绑重绑：{e}",
            )

    loop_num = clan_info.loop_num

    # 4) 丢进任务池异步启动循环（和 QQ 指令完全一致）
    #    clanbattle_pool.queue 是主循环创建的 asyncio.PriorityQueue，put 也要投递回主循环
    async def _add_monitor_task():
        await clanbattle_pool.add_task(
            PrioritizedQueryItem(data=ClanbattleItem(clan_info, loop_num))
        )

    await call_in_main_loop(_add_monitor_task())

    return {
        "message": f"已启动出刀监控（编号HN000{loop_num}），请稍后刷新页面查看状态",
        "loop_num": loop_num,
    }


# 统一把所有业务路由挂载到 app（已在 api_router 上带 /kanna_dependency 前缀）
app.include_router(api_router)


@on_startup
async def kanna_web():
    global main_event_loop
    # on_startup 钩子在 nonebot 主事件循环内执行，此刻记录的 loop 就是游戏 client 所属 loop
    main_event_loop = asyncio.get_running_loop()
    web = threading.Thread(
        target=uvicorn.run, kwargs={"app": app, "host": "0.0.0.0", "port": 12138}
    )
    web.start()
