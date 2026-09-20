import functools

from hoshino import priv
from .tools import get_qid, other_allow
from hoshino.typing import HoshinoBot, CQEvent
from ..database.dal import pcr_sqla


def check_account_qqid(func):

    @functools.wraps(func)
    async def wrapper(bot: HoshinoBot, ev: CQEvent, *arg, **kwarg):
        qq_id, is_other = get_qid(ev)

        # 取号规则：一个 QQ 只有一个游戏账号（全局号 group_id = 0），所有群通用。
        # 这里仍统一走 query_account_for_group（群消息）/ query_account（私聊），
        # 是为了保留「本群优先、回退全局」这层语义 —— 历史上按群绑的 N 行
        # 2026-09-20 起不再产生，但老数据还在，DAL 的回退逻辑照旧兜住。
        # 注意别写 query_account(qq_id)[0]：那是「取第一条」，老库里顺序不定。
        group_id = int(getattr(ev, "group_id", 0) or 0)
        if group_id:
            account = await pcr_sqla.query_account_for_group(qq_id, group_id)
            tip = (
                "还没有绑定游戏账号，请先在网页端仪表盘绑定，"
                "或在QQ私聊我发送【绑定账号帮助】"
            )
        else:
            accounts = await pcr_sqla.query_account(qq_id)
            account = accounts[0] if accounts else None
            tip = "没有绑定账号，请发送【绑定账号帮助】（先加机器人好友）"

        if account is None:
            await bot.send(ev, tip)
            return

        if is_other and not other_allow(ev, account.allow_others):
            await bot.send(ev, "权限不足，请发送【成员管理帮助】")
            return
        return await func(bot, ev, *arg, account=account, qq_id=qq_id, **kwarg)

    return wrapper


def check_priv_adimin(allow_self: bool = True):

    def decorator(func):

        @functools.wraps(func)
        async def wrapper(bot: HoshinoBot, ev: CQEvent, *arg, **kwarg):
            qq_id, is_other = get_qid(ev)
            if not priv.check_priv(ev, priv.ADMIN) and (not allow_self or is_other):
                await bot.send(ev, "权限不足,需要管理员权限")
                return

            return await func(bot, ev, *arg, qq_id=qq_id, **kwarg)

        return wrapper

    return decorator


def is_group_manager(ev: CQEvent) -> bool:
    """发言者是不是本群群主 / 群管，或 bot 主人

    这里必须显式比对角色，不能用 `>= priv.ADMIN`：priv.WHITE 是 51，比 ADMIN(21) 大，
    但白名单用户并不因此成为群管理。

    放在这里而不是 webui 里，是为了让 QQ 指令也能直接用 —— webui/__init__.py 会
    `from .api import *`，clanbattle 反过来 import 它容易撞循环导入。
    """
    return priv.get_user_priv(ev) in (priv.ADMIN, priv.OWNER, priv.SUPERUSER)
