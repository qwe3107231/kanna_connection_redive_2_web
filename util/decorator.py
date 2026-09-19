import functools

from hoshino import priv
from .tools import get_qid, other_allow
from hoshino.typing import HoshinoBot, CQEvent
from ..database.dal import pcr_sqla


def check_account_qqid(func):

    @functools.wraps(func)
    async def wrapper(bot: HoshinoBot, ev: CQEvent, *arg, **kwarg):
        qq_id, is_other = get_qid(ev)

        # 取号规则（按群绑定）：
        #   群消息 → 本群绑定的号优先；本群没绑过，就回退到全局号（QQ 私聊绑的那个）
        #   私聊   → 没有群上下文，沿用旧行为取第一条（全局号排在最前）
        # 注意以前是无脑取 query_account(qq_id)[0]，一旦按群绑了多个号，
        # 取到哪个纯看数据库返回顺序 —— 在 A 群发指令却用 B 群的号，就是这个原因。
        group_id = int(getattr(ev, "group_id", 0) or 0)
        if group_id:
            account = await pcr_sqla.query_account_for_group(qq_id, group_id)
            tip = (
                "本群还没有绑定游戏账号，请先在网页端仪表盘绑定，"
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
