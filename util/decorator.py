import functools

from hoshino import priv
from .tools import get_qid, other_allow
from hoshino.typing import HoshinoBot, CQEvent
from ..database.dal import pcr_sqla


def check_account_qqid(func):

    @functools.wraps(func)
    async def wrapper(bot: HoshinoBot, ev: CQEvent, *arg, **kwarg):
        qq_id, is_other = get_qid(ev)

        # 取号规则：一个 QQ 一个游戏账号（全局号 group_id=0），所有群通用。这里仍走
        # query_account_for_group 以保留「本群优先、回退全局」；别写 query_account()[0]。
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


def _admin_wrapper(func, allow_self: bool):
    """`allow_self=True` 时「没有 @ 人」直接放行；`False` 时一律要求群管以上。"""

    @functools.wraps(func)
    async def wrapper(bot: HoshinoBot, ev: CQEvent, *arg, **kwarg):
        qq_id, is_other = get_qid(ev)
        if not priv.check_priv(ev, priv.ADMIN) and (not allow_self or is_other):
            await bot.send(ev, "权限不足，需要管理员权限")
            return

        return await func(bot, ev, *arg, qq_id=qq_id, **kwarg)

    return wrapper


def require_admin(func):
    """要求本群群主 / 群管或 bot 主人（**不看 @ 对象**，普通成员一律拦）。

    删除全群数据这类危险指令用这个，**不要**用 `check_self_or_admin`。
    """
    return _admin_wrapper(func, allow_self=False)


def check_self_or_admin(allow_self: bool = True):
    """操作自己（没有 @ 人）时放行；@ 了别人就要管理员权限。

    ⚠️ 默认值 `allow_self=True` 对「没有 @ 人」的指令是**直接放行**的 ——
    它从来不是「管理员校验」，别拿它保护危险指令（历史名字 `check_priv_adimin`
    很容易让人误会，2026-10-25 就因此漏了【启用肃正协议】）。
    """
    return lambda func: _admin_wrapper(func, allow_self=allow_self)


# 旧名兼容：语义与以前完全一致（默认 allow_self=True）。新代码请用上面两个明确的名字。
check_priv_adimin = check_self_or_admin


def is_group_manager(ev: CQEvent) -> bool:
    """发言者是不是本群群主 / 群管，或 bot 主人

    这里必须显式比对角色，不能用 `>= priv.ADMIN`：priv.WHITE 是 51，比 ADMIN(21) 大，
    但白名单用户并不因此成为群管理。

    放在这里而不是 webui 里，是为了让 QQ 指令也能直接用 —— webui/__init__.py 会
    `from .api import *`，clanbattle 反过来 import 它容易撞循环导入。
    """
    return priv.get_user_priv(ev) in (priv.ADMIN, priv.OWNER, priv.SUPERUSER)
