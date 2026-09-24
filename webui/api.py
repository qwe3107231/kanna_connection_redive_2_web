import asyncio
import json
import secrets
import threading
import time
from typing import Dict, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware

from ..util.tools import daoflag2str, anywhere_send

from ..clanbattle import clanbattle_info, notice_update_time
from ..util.auto_boss import clan_boss_info
from ..clanbattle.base import (
    DEFAULT_RANK_LINES,
    clanbattle_report,
    get_rank_lines_cached,
    is_monitor_running,
)
from ..database.dal import Account, CookieCache, RefreshAccount, SLDao, pcr_sqla
from ..basedata import GroupPriority, NoticeType, Platform
from ..setting import WebSetting
from .util import *
from .web_model import *
from nonebot import logger, on_startup

from sse_starlette.sse import EventSourceResponse

app = FastAPI()

# 说明：nonebot 主事件循环引用与 call_in_main_loop 都定义在 webui/util.py，
# 因为 util 里的群角色查询（OneBot get_group_member_info）同样需要投递回主循环。
# 这里用 from .util import * 一并引入。

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
    # 先清服务端记录，再让浏览器删 cookie。
    # 注意这里是 token.token：CookieCache 的主键字段叫 token，没有 cookie 这个属性，
    # 以前写的 token.cookie 会抛 AttributeError 又被下面的 except 吞掉，
    # 结果「登出」只删了浏览器那侧的 cookie，服务端这条 token 还能继续用满 7 天。
    try:
        await pcr_sqla.web_delete_cookie(token=token.token)
    except Exception as e:
        logger.warning(f"登出时清理服务端 token 失败: {e}")
    response.delete_cookie("token", path="/", samesite="lax")
    response.delete_cookie("token", path="/kanna_dependency")
    return "ok"


@api_router.post("/change_password")
async def change_password(
    form: ChangePasswordForm, token: CookieCache = Depends(verify_cookie)
):
    """修改网页端登录密码（登录后自助操作）

    规则：
      - 必须提供旧密码：光有 cookie 不足以改密，防止借到/偷到浏览器的人直接改走账号
      - 新密码 6~32 位，且不能和旧密码相同
      - 改完清掉 temp 标记，登录接口里「临时密码 7 天过期」就不再适用
      - 其他设备上的登录态全部失效，只把当前这一个补回来，
        免得旧密码已经泄露时旧会话还能继续用

    忘记密码不用走这里：在 QQ 私聊机器人重发【网页端登录】，
    机器人会生成一个新的临时密码（原有的权限等级会保留）。
    """
    account = str(token.user_id)
    new_password = form.new_password.strip()
    if not 6 <= len(new_password) <= 32:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "新密码长度需在 6~32 位之间")
    if new_password == form.old_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "新密码不能和旧密码相同")
    if not await pcr_sqla.change_web_password(account, form.old_password, new_password):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "旧密码不正确")

    try:
        await pcr_sqla.web_delete_cookie(user_id=account)
        await pcr_sqla.web_add_cookie(token.token, account)
    except Exception as e:
        # 清不掉旧会话不影响改密本身，记个日志继续返回成功
        logger.warning(f"改密后清理旧登录态失败 account={account}: {e}")
    return "修改成功"


@api_router.get("/home")
async def home_info(token: CookieCache = Depends(verify_cookie)):
    user_id = int(token.user_id)
    response = HomeResponse()
    response.user_id = user_id
    if web_user := await pcr_sqla.web_query_user(user_id):
        response.priority = web_user.priority

    accounts = await pcr_sqla.query_account(user_id)
    if accounts:
        # 昵称只用于首页问候，优先取全局号（没有全局号就取第一条）
        global_account = next(
            (a for a in accounts if int(a.group_id) == 0), accounts[0]
        )
        response.name = global_account.name
        # 顶层 has_account = 「有没有绑过号」（账号是全局的，一个 QQ 一个号）。
        # clan[i].has_account 仍然逐群给，是为了让前端沿用原逻辑 —— 现在各群必然同值。
        response.has_account = True
    if groups := await pcr_sqla.get_member_group(user_id):
        clan_list = []
        for group in groups:
            item = group.dict()
            # 每个群单独算权限：群主/群管在本群自动是 2 级（bot 主人是 3 级），
            # 前端据此显示"群主/群管/管理员/成员"标签并控制管理入口
            item["priority"] = await effective_group_priority(user_id, group.group_id)
            # 本群有没有可用的号。账号是**全局**的（一个 QQ 一个号，绑一次所有群通用），
            # 所以这里各群结果必然一致 —— 保留逐群字段只是让前端沿用原逻辑。
            # query_account_for_group 会回退到全局号（group_id = 0），语义仍然成立。
            item["has_account"] = (
                await pcr_sqla.query_account_for_group(user_id, group.group_id)
            ) is not None
            clan_list.append(item)
        response.clan = clan_list

    # 把「我管理的群」补进列表：群主/群管很可能没发过【绑定本群公会】，
    # 不补的话他们在网页端连自己的群都点不进去，"群主自动 2 级"就只是纸面能力；
    # bot 主人则能看到所有在用的群。候选范围只取「有人在用」的群，是有限集合。
    known = {int(clan["group_id"]) for clan in response.clan}
    candidates: Dict[int, str] = {
        int(g.group_id): g.group_name for g in await pcr_sqla.get_bound_groups()
    }
    for group_id in clanbattle_info:
        candidates.setdefault(int(group_id), "")

    owner = is_bot_owner(user_id)
    for gid, gname in candidates.items():
        if gid in known:
            continue
        if owner or await is_group_manager_in(gid, user_id):
            response.clan.append(
                {
                    "group_id": gid,
                    "group_name": gname or "环奈连结",
                    "priority": await effective_group_priority(user_id, gid),
                    # 群主/群管可能没在这个群绑过公会，这里同样按群算一次
                    "has_account": (
                        await pcr_sqla.query_account_for_group(user_id, gid)
                    ) is not None,
                }
            )
    return response.dict()


@api_router.get("/{group_id}/dashboard")
async def dashboard_info(group_id: int, token: CookieCache = Depends(verify_group_access)):
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
    # 本群实际权限等级（群主/群管自动 2 级，bot 主人 3 级），前端据此控制按钮显隐
    response.clan_priority = await effective_group_priority(user_id, group_id)
    # 游戏账号（全局，一个 QQ 一个号、各群同值），仪表盘状态条上的绑定入口用它
    response.account = _account_info(
        await pcr_sqla.query_account_for_group(user_id, group_id)
    )

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
        # 今日伤害排行（Top 10）+ 全员总量，给右栏横向条形图用。
        # 和上面两处共用同一份 dao_data，不额外查库。
        rank_rows, damage_total, score_total = build_day_damage_rank(dao_data, 10)
        response.day_damage_rank = [DayDamageRank(**row) for row in rank_rows]
        response.day_damage_total = damage_total
        response.day_score_total = score_total
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
    group_id: int, boss: int, token: CookieCache = Depends(verify_group_access)
):
    """指定 BOSS 本次会战周期内的全部出刀记录，按时间倒序（BOSS 卡片"出刀记录"弹窗用）"""
    if not 1 <= boss <= 5:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "BOSS 编号必须是 1~5")
    # 本次会战 = 最近一次出刀时间的 pcr 日期往前推 5 天（与 get_clan_day 口径一致）
    period = await pcr_sqla.get_all_records(group_id)
    filtered = [r for r in period if r.boss == boss] if period else []
    # build_last_dao 本身就是按时间倒序转换，limit 传记录总数即"全部返回"
    return build_last_dao(filtered, max(len(filtered), 1))


def _rank_line_response(
    data: dict,
    cached: bool,
    monitor_running: bool,
    updated_at: int,
    stale: bool = False,
) -> RankLineResponse:
    """把 query_rank_lines 的结果（或缓存里还原出来的同一结构）转成接口响应"""
    return RankLineResponse(
        clan_battle_id=data["clan_battle_id"],
        lines=[RankLine(**line) if line else None for line in data["lines"]],
        my=RankLine(**data["my"]) if data.get("my") else None,
        default_ranks=list(DEFAULT_RANK_LINES),
        cached=cached,
        stale=stale,
        monitor_running=monitor_running,
        updated_at=updated_at,
    )


@api_router.get("/{group_id}/rank_lines")
async def get_rank_lines(
    group_id: int,
    ranks: str = None,
    force: bool = False,
    token: CookieCache = Depends(verify_group_access),
):
    """查档线：本届会战指定排名的分数线（仅会战期间有效），ranks 为逗号分隔自定义排名

    档线是全服排名数据，游戏侧每半小时才更新一次，但抓一次要打十几次分页请求
    （默认 14 个档位 = 13 个分页，外加「末位二分搜索」十来次）。缓存逻辑统一收在
    clanbattle.base.get_rank_lines_cached 里（QQ 端【查档线】指令走同一条路），
    这里只负责「监控没开时只读缓存」和把结果转成响应。

    抓取的前置条件是「出刀监控在跑」，用 `is_monitor_running` 判 —— **不能**只看
    `clan_info.client`：发过【取消出刀监控】之后 client 仍在，而账号很可能正被群友
    自己登录着，这时抓一次失败会触发重登，直接把人顶下线。监控没开时只读缓存，
    读不到才报错。
    """
    # 解析档位。默认档位和每个自定义档位组合各占一条缓存，互不覆盖。
    if ranks:
        try:
            targets = [int(x.strip()) for x in ranks.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "ranks 参数格式错误，应为逗号分隔数字，如 500,2000"
            )
        if not targets:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "ranks 不能为空")
    else:
        targets = list(DEFAULT_RANK_LINES)
    ranks_key = ",".join(str(t) for t in sorted(set(targets)))

    clan_info = clanbattle_info.get(group_id)
    if not is_monitor_running(clan_info):
        # 监控没开：只读缓存，不抓。拿不到 clan_battle_id，所以取本群最新一届那条。
        cached = await pcr_sqla.get_latest_rank_line_cache(group_id, ranks_key)
        if cached is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "出刀监控未开启，无法查询档线（开启监控后会自动抓取并缓存）",
            )
        return _rank_line_response(
            json.loads(cached.payload),
            cached=True,
            stale=True,
            monitor_running=False,
            updated_at=int(cached.updated_at),
        )

    # 游戏 client 绑定在 nonebot 主循环，必须投递回去执行（与监控循环排队互斥）。
    # 缓存命中 / 抓取 / 抓失败退回旧缓存，都在 get_rank_lines_cached 内部处理完了。
    result = await call_in_main_loop(get_rank_lines_cached(clan_info, targets, force))
    return _rank_line_response(
        result["data"],
        cached=result["cached"],
        stale=result["stale"],
        monitor_running=True,
        updated_at=result["updated_at"],
    )


@api_router.get("/{group_id}/notice")
async def clan_notice(group_id: int, token: CookieCache = Depends(verify_group_access)):
    user_id = int(token.user_id)
    response = NoticeResponse()
    response.user_id = user_id
    if web_user := await pcr_sqla.web_query_user(user_id):
        response.priority = web_user.priority
    # 本群实际权限等级，前端据此控制通知管理入口（>= 1 才显示）
    response.clan_priority = await effective_group_priority(user_id, group_id)
    # 有没有可用的号（账号是全局的，各群同值）；没有就不让发预约/挂树
    response.has_account = (
        await pcr_sqla.query_account_for_group(user_id, group_id)
    ) is not None
    if subscribe := await pcr_sqla.get_notice(NoticeType.subscribe.value, group_id):
        response.subscribe = subscribe
    if apply := await pcr_sqla.get_notice(NoticeType.apply.value, group_id):
        response.apply = apply
    if tree := await pcr_sqla.get_notice(NoticeType.tree.value, group_id):
        response.tree = tree
    return response.dict()


@api_router.get("/{group_id}/report")
async def clan_report(group_id: int, token: CookieCache = Depends(verify_group_access)):
    user_id = int(token.user_id)
    response = ReportResponse()
    response.user_id = user_id
    if web_user := await pcr_sqla.web_query_user(user_id):
        response.priority = web_user.priority
    # 本群实际权限等级，前端据此控制修正出刀入口（>= 1 才显示）
    response.clan_priority = await effective_group_priority(user_id, group_id)
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
    # 当前生效的号。一个 QQ 只有一个全局号，但仍统一走 query_account_for_group
    # （本群优先、回退全局），别写 query_account(user_id)[0]（那是「取第一条」的语义）。
    if pcr_user := await pcr_sqla.query_account_for_group(user_id, group_id):
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
async def add_notice(notice: NoticeCache, token: CookieCache = Depends(verify_cookie)):
    user_id = int(token.user_id)
    # 只能操作本人所属的群，防止改请求体里的 group_id 去别的群发通知
    await ensure_group_access(user_id, int(notice.group_id))

    # 预约 / 挂树 / 申请 / SL 都是「自己的事」，普通成员（0 级）就能做，这里不再卡等级；
    # 只有替别人发通知才算「管理他人的通知」，需要本群 2 级（群主 / 群管自动获得）。
    # user_id 传 0 或不传按「给自己发」处理，避免客户端漏传一个字段就变成替别人发。
    target_id = int(notice.user_id) or user_id
    if target_id != user_id:
        await require_group_priority(
            user_id,
            int(notice.group_id),
            GroupPriority.group_admin.value,
            "管理他人的通知",
        )
    notice.user_id = target_id

    # 预约/挂树/申请出刀必须先绑定游戏账号（未绑定用户没有出刀身份，不允许发起）。
    # 检查的是「这条通知挂谁头上」，所以替别人发时校验的是对方。
    # 账号绑定是全局的（一个 QQ 一个号），所以这里不分群。
    if notice.notice_type in (
        NoticeType.subscribe.value,
        NoticeType.tree.value,
        NoticeType.apply.value,
    ) and not await pcr_sqla.query_account_for_group(
        target_id, int(notice.group_id)
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "还没绑定游戏账号，请先在网页端仪表盘绑定，"
            "或在QQ私聊机器人发送【绑定账号帮助】完成绑定",
        )
    if notice.notice_type == NoticeType.sl.value:
        if not await pcr_sqla.add_sl(
            SLDao(group_id=notice.group_id, user_id=target_id, time=int(time.time()))
        ):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "已经sl过了")
    else:
        await pcr_sqla.add_notice(notice)
    notice_update_time[int(notice.group_id)] = int(time.time())
    await anywhere_send(
        get_notice_msg(
            notice.notice_type, target_id, notice.boss, notice.lap, notice.text
        ),
        group_id=notice.group_id,
    )
    return "成功"


@api_router.post("/delete_notice")
async def remove_notice(notice: NoticeCache, token: CookieCache = Depends(verify_cookie)):
    user_id = int(token.user_id)
    # 只能操作本人所属的群，防止改请求体里的 group_id 去别的群删通知
    await ensure_group_access(user_id, int(notice.group_id))

    # 取消自己的通知不限等级；取消别人的通知属于「管理他人的通知」，需要本群 2 级。
    # 注意删的是 notice.user_id 名下那一条，不能像以前那样先覆盖成自己 ——
    # 覆盖之后管理员点「取消」只会去删自己那条（通常压根不存在），别人的通知永远删不掉。
    target_id = int(notice.user_id) or user_id
    if target_id != user_id:
        await require_group_priority(
            user_id,
            int(notice.group_id),
            GroupPriority.group_admin.value,
            "管理他人的通知",
        )
    notice.user_id = target_id

    if notice.notice_type == NoticeType.sl.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "那你自己心里清楚")
    else:
        await pcr_sqla.delete_notice(
            notice.notice_type,
            notice.group_id,
            notice.boss,
            user_id=target_id,
        )
    notice_update_time[int(notice.group_id)] = int(time.time())
    await anywhere_send(
        cancel_notice_msg(
            notice.notice_type, target_id, notice.boss, operator=user_id
        ),
        group_id=notice.group_id,
    )
    return "取消成功"


@api_router.post("/delete_notice_special")
async def remove_notice_special(
    notice: SpecialNoticeForm, token: CookieCache = Depends(verify_cookie)
):
    user_id = int(token.user_id)
    # 只能操作本人所属的群，防止改请求体里的 group_id 去别的群取消通知
    await ensure_group_access(user_id, int(notice.group_id))
    # 取消自己的通知不限等级；替别人取消属于「管理他人的通知」，需要本群 2 级
    # （群主 / 群管自动获得）。这里用 notice.user_id 去删，才能真的删掉目标那条。
    if user_id != notice.user_id:
        await require_group_priority(
            user_id,
            int(notice.group_id),
            GroupPriority.group_admin.value,
            "管理他人的通知",
        )
    await pcr_sqla.delete_notice(
        notice.notice_type,
        notice.group_id,
        notice.boss,
        user_id=notice.user_id,
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


def dashboard_push_marker(clan_info) -> int:
    """仪表盘 SSE 的推送判据：下面几个标记里最大的那个，比上次推送时大了就推一次。

    三路变化各自独立：

    - `dao_update_time`     出刀入库（今日/昨日出刀、伤害排行都会变）
    - `fighter_update_time` 战斗人数变化（「正在出刀」卡片）
    - `rank_update_time`    **会战排名变化**（「公会排名」卡片）

    排名必须单独算一路：它跟本团有没有人出刀**无关** —— 游戏侧每半小时刷一次榜，
    别的公会在打，我们排名就会动。以前只看出刀和人数，于是「一直没人出刀」时排名
    变了前端也收不到，卡片一直停在旧值、手动刷新页面才更新
    （2026-09-24 用户报的现象）。`ClanBattle.set_rank()` 负责在排名真的变了时打戳。
    """
    return max(
        getattr(clan_info, "dao_update_time", 0) or 0,
        getattr(clan_info, "fighter_update_time", 0) or 0,
        getattr(clan_info, "rank_update_time", 0) or 0,
    )


@api_router.get("/{group_id}/renew_dashboard")
async def renew_dashboard(group_id: int, token: CookieCache = Depends(verify_group_access)):
    async def dashboard_generator():
        dashboard_time[token.token] = int(time.time())
        notice_time[token.token] = int(time.time())
        while True:
            await asyncio.sleep(3)  # 3 秒轮询一次变化标记，加速网页端实时刷新
            if clan_info := clanbattle_info.get(group_id, None):
                # 出刀入库 / 战斗人数变化 / 会战排名变化 —— 判据见 dashboard_push_marker
                latest = dashboard_push_marker(clan_info)
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
async def renew_report(group_id: int, token: CookieCache = Depends(verify_group_access)):
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
async def renew_notice(group_id: int, token: CookieCache = Depends(verify_group_access)):
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
async def correct_dao_record(
    correct: CorrectDaoInfo, token: CookieCache = Depends(verify_cookie)
):
    user_id = int(token.user_id)
    # 只能操作本人所属的群，防止改请求体里的 group_id 去改别的群的出刀记录
    await ensure_group_access(user_id, int(correct.group_id))
    # 修正出刀仅限本群 1 级以上（群主/群管自动 2 级），普通成员只读
    await require_group_priority(
        user_id, int(correct.group_id), GroupPriority.manager.value, "修正出刀类型"
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


# ------------------------ 游戏账号绑定（全局，一个 QQ 一个号） ------------------------
#
# 网页端和 QQ 私聊写的是同一行（Account.group_id = 0），所以在哪个群打开仪表盘
# 都一样，换公会 / 进新群都不需要重新绑定。URL 里的 group_id 现在只用于访问校验。
# 三条链路与 QQ 指令（login.py 的【绑定账号】/【渠绑定账号】/【台绑定账号】）
# 完全一致，只是把参数从聊天文本换成了表单字段。


def _account_info(account: Optional[Account]) -> GroupAccountInfo:
    """把 Account 行转成前端要的账号信息（现在一个 QQ 只有一个全局号）"""
    if account is None:
        return GroupAccountInfo()
    return GroupAccountInfo(
        bound=True,
        account_id=account.id,
        name=account.name or "",
        platform=int(account.platform),
        viewer_id=account.viewer_id,
    )


async def _login_new_account(
    account: Account, refresh: Optional[RefreshAccount] = None
) -> Optional[Account]:
    """登录校验 + 落库：成功返回填好昵称/viewer_id 的 Account，登录不上返回 None

    整段必须投递回 nonebot 主循环 —— 游戏 client 的 httpx 连接、以及
    login.client_cache 这个全局字典都归属主循环，在 uvicorn 线程里直接跑
    会和正在出刀监控的会话串在一起。
    """
    from ..client import check_client
    from ..login import query

    client = await query(account, True)
    load_index = await check_client(client)
    if not load_index:
        return None
    account.viewer_id = load_index.user_info.viewer_id
    account.name = load_index.user_info.user_name
    await pcr_sqla.add_account(
        account.user_id,
        account.dict(exclude_none=True),
        group_id=int(account.group_id or 0),
    )
    if refresh is not None:
        await pcr_sqla.add_refresh(refresh)
    return account


@api_router.post("/{group_id}/bind_account")
async def bind_account(
    group_id: int,
    form: BindAccountForm,
    token: CookieCache = Depends(verify_group_access),
):
    """绑定游戏账号（**全局生效**，一个 QQ 只绑一个号）

    和 QQ 私聊【绑定账号】写的是同一行（`Account.group_id = 0`），所以在哪个群
    打开仪表盘都一样，换公会 / 进新群都不需要重新绑定。URL 里的 group_id 现在
    只用来做访问校验（verify_group_access），不再决定这条绑定写到哪。

    权限：绑自己的号属于「自己的事」，0 级即可，不限等级。
    重复绑定 = 覆盖原来那一条。
    """
    from ..client import decrypt_access_key, get_access_key

    user_id = int(token.user_id)
    group_id = int(group_id)
    platform = int(form.platform)

    try:
        if platform == Platform.b_id.value:
            bili_account = form.bili_account.strip()
            bili_password = form.bili_password.strip()
            if not bili_account or not bili_password:
                raise ValueError("请填写 B站账号和 B站密码")
            # 换 access_key 要连 B站，同样得回主循环
            uid, access_key = await call_in_main_loop(
                get_access_key(bili_account, bili_password, user_id)
            )
            account = Account(
                user_id=user_id,
                group_id=0,
                platform=Platform.b_id.value,
                account=str(uid),
                password=access_key,
                refresh=bili_account,
            )
            refresh: Optional[RefreshAccount] = RefreshAccount(
                account=bili_account, password=bili_password
            )
        elif platform == Platform.qu_id.value:
            login_id = form.login_id.strip()
            raw_token = form.token.strip()
            if not login_id or not raw_token:
                raise ValueError("请填写 login_id 和 token")
            # token 有两种给法：
            #   1) 直接的 access_key
            #   2) 提取器导出的 XML 片段（<string name="...">...</string>）
            # 用「像不像 XML」来判断，而不是像 QQ 指令那样按空格切成两段 ——
            # XML 里有没有空格、粘过来是几段都不确定，按空格切很容易切错，
            # 而且切错了 decrypt_access_key 会直接抛 AttributeError 变成 500。
            password = raw_token
            if raw_token.lstrip().startswith("<"):
                try:
                    password = decrypt_access_key(raw_token)
                except Exception:
                    raise ValueError(
                        "token 看起来是提取器导出的 XML，但解析失败，"
                        '请确认复制完整（形如 <string name="...">...</string>）'
                    )
            account = Account(
                user_id=user_id,
                group_id=0,
                platform=Platform.qu_id.value,
                account=login_id,
                password=password,
            )
            refresh = None
        elif platform == Platform.tw_id.value:
            short_udid = form.short_udid.strip()
            udid = form.udid.strip()
            if not short_udid or not udid or not form.viewer_id:
                raise ValueError("请填写 short_udid、udid 和 viewer_id")
            account = Account(
                user_id=user_id,
                group_id=0,
                platform=Platform.tw_id.value,
                viewer_id=int(form.viewer_id),
                account=short_udid,
                password=udid,
            )
            refresh = None
        else:
            raise ValueError("未知的服务器编号")
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    account = await call_in_main_loop(_login_new_account(account, refresh))
    if account is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "绑定失败，请检查账号信息是否完整正确（密码 / token 可能已过期）",
        )
    return _account_info(account).dict()


@api_router.post("/{group_id}/unbind_account")
async def unbind_account(
    group_id: int, token: CookieCache = Depends(verify_group_access)
):
    """解绑当前登录用户绑定的游戏账号（全局，所有群一起生效）

    账号绑定不再按群区分，所以这里删的就是那唯一一条；删掉之后仪表盘会显示
    「未绑定游戏账号」，重新点【绑定游戏账号】或 QQ 私聊【绑定账号】即可。
    """
    user_id = int(token.user_id)
    if not await pcr_sqla.delete_account(user_id, 0):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "还没有绑定过游戏账号，无需解绑",
        )
    return "解绑成功"


@api_router.get("/{group_id}/monitor/accounts")
async def monitor_list_accounts(
    group_id: int, token: CookieCache = Depends(verify_group_access)
):
    """方案A：只列出"当前登录QQ号自己绑定"的角色账号，供开启出刀监控下拉选。

    账号绑定是全局的（一个 QQ 一个号），所以这里就是该用户绑过的那一条；
    别人绑定的账号不会出现在这里。
    """
    user_id = int(token.user_id)
    accounts = await pcr_sqla.query_account(user_id)
    if not accounts:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "还没绑定角色账号，请先在网页端仪表盘绑定，"
            "或在QQ上对机器人发送【绑定账号帮助】完成绑定后再开启",
        )
    from .web_model import MonitorAccountOption

    return [
        MonitorAccountOption(
            account_id=acc.id,
            name=acc.name or "未命名",
            platform=acc.platform,
            viewer_id=acc.viewer_id,
            group_id=int(acc.group_id or 0),
        ).dict()
        for acc in accounts
        if acc.id is not None
    ]


@api_router.post("/{group_id}/monitor")
async def monitor_switch(
    group_id: int,
    form: MonitorActionForm,
    token: CookieCache = Depends(verify_group_access),
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

        # 权限：监控人本人，或 bot 主人。
        # 出刀监控是拿某个人的游戏账号在跑，所以群主/群管也不允许取消别人的监控，
        # 只有 bot 主人有跨群权限（和"取消他人的出刀监控仅 bot 主人"的规则一致）。
        is_monitor_owner = user_id == clan_info.user_id
        if (not is_monitor_owner) and (not is_bot_owner(user_id)):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "只有监控人本人或 bot 主人可以取消出刀监控",
            )

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
    #    与 /monitor/accounts 列出来的完全一致（该用户绑定的全部账号）
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
                "登录角色账号失败，请确认账号信息是否有效（密码 / token 可能已过期）；"
                "可在仪表盘上重新绑定这个账号，或在QQ私聊机器人重发【绑定账号】。"
                f"原始错误：{e}",
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
    # on_startup 钩子在 nonebot 主事件循环内执行，此刻记录的 loop 就是游戏 client 所属 loop。
    # 注意必须写到 webui.util 的模块全局上：call_in_main_loop 和群角色查询都读那里，
    # 写成本模块的全局变量的话 util 里读到的还是 None，所有投递都会 503。
    from . import util as web_util

    web_util.main_event_loop = asyncio.get_running_loop()
    web = threading.Thread(
        target=uvicorn.run, kwargs={"app": app, "host": "0.0.0.0", "port": 12138}
    )
    web.start()
