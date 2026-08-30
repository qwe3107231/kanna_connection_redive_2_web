import functools

from hoshino import priv
from .tools import get_qid, other_allow
from hoshino.typing import HoshinoBot, CQEvent
from ..database.dal import pcr_sqla


def check_account_qqid(func):

    @functools.wraps(func)
    async def wrapper(bot: HoshinoBot, ev: CQEvent, *arg, **kwarg):
        qq_id, is_other = get_qid(ev)

        if not (account := await pcr_sqla.query_account(qq_id)):
            await bot.send(ev, "没有绑定账号，请发送【绑定账号帮助】（先加机器人好友）")
            return

        account = account[0]

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
