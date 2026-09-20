import random
import string
from hoshino import Service, priv
from hoshino.typing import CQEvent, HoshinoBot
from nonebot import NoticeSession, on_command, logger
from ..basedata import GroupPriority
from ..database.dal import pcr_sqla
from ..database.models import WebAccount
from ..setting import WebSetting
from ..util.decorator import is_group_manager
from ..util.tools import get_qid
from .api import *
from .util import get_member_row, is_bot_owner

sv = Service(
    name="环奈网页端管理",  # 功能名
    visible=False,  # 可见性
    enable_on_default=True,  # 默认启用
)

# 网页端权限等级（basedata.GroupPriority）
# 0 只读 + 自助预约/挂树 / 1 可修正出刀 / 2 群主·群管（本群自动，可管理他人的通知） / 3 bot 主人
WEB_PRIORITY_NAMES = {
    GroupPriority.member.value: "普通成员（可自助预约 / 挂树，其余只读）",
    GroupPriority.manager.value: "网页端管理员（可修正出刀）",
    GroupPriority.group_admin.value: "群主 / 群管（本群自动获得，可管理他人的通知）",
    GroupPriority.bot_owner.value: "bot 主人（所有群，自动获得）",
}
WEB_PRIORITY_HELP = (
    "用法：【网页权限 @某人 1】或【网页权限 12345 1】\n"
    + "\n".join(f"{lv} = {name}" for lv, name in WEB_PRIORITY_NAMES.items())
    + "\n\n各级能力：\n"
    "  0 级：看数据，并给自己预约 / 挂树 / 申请 / 记录 SL\n"
    "  1 级：额外可以修正出刀\n"
    "  2 级：额外可以管理他人的通知（替人发 / 替人取消）\n"
    "  3 级：额外可以取消他人的出刀监控、跨群查看\n"
    "群主 / 群管在本群自动是 2 级，bot 主人（SUPERUSERS）是 3 级，都无需手动设置。"
)

GROUP_PRIORITY_HELP = (
    "用法：【本群权限 @某人 1】或【本群权限 12345 1】\n"
    "只影响本群：0 = 普通成员（可自助预约 / 挂树，其余只读），"
    "1 = 网页端管理员（可修正本群出刀）\n"
    "群主 / 群管在本群自动是 2 级（可管理他人的通知），无需设置。"
)


# is_group_manager 的实现已挪到 util/decorator.py —— clanbattle 的 QQ 指令也要用它，
# 那边反过来 import webui 会撞循环导入。这里继续用同一个函数，行为不变。


@on_command("apply_login", aliases=("网页端登录"), only_to_me=True)
async def apply_login(session: NoticeSession):
    qq_id = str(session.ctx.user_id)
    temp_password = "".join(random.sample(string.ascii_letters + string.digits, 8))
    await pcr_sqla.web_add_user(WebAccount(account=qq_id, password=temp_password))
    host = WebSetting.web_host.value
    port = WebSetting.web_port.value
    # 前端用的是 hash 路由（createWebHashHistory），所以需要用 #/login 而非 /login
    login_url = (
        f"http://{host}:{port}/#/login?account={qq_id}&password={temp_password}"
    )
    await session.send(
        f"🌐 环奈连结 R · 网页端登录链接：\n{login_url}\n\n"
        "⚠️ 临时密码 7 天内有效，建议登录后点右上角头像 →【修改密码】换成自己的。\n"
        "（忘了密码就重新私聊我发【网页端登录】，会再给一个临时密码，权限等级不会丢）\n\n"
        "🎮 游戏账号可以直接在仪表盘上绑定：一个 QQ 只绑一个号、所有群通用"
        "（和私聊我绑的是同一个号，换公会也不用重绑）。",
        ensure_private=True,
    )


@sv.on_prefix("网页权限")
async def set_web_priority(bot: HoshinoBot, ev: CQEvent):
    """网页权限 + @某人 + 等级：设置全局网页端权限等级（仅 bot 主人可用）

    0 = 普通成员（可自助预约 / 挂树，其余只读）
    1 = 网页端管理员（可修正出刀）
    2 = 群主 / 群管级（本群自动获得，这里手动授予表示"在 ta 所属的群里都给 2 级"）

    3 级是 bot 主人专属，由 SUPERUSERS 自动判定，不能手动授予。
    """
    # 这条指令写的是全局账号等级（WebAccount.priority），会对该用户所属的所有群生效，
    # 所以收归 bot 主人。群主/群管在自己群里本来就有 2 级，不需要这条；
    # 要给本群某个成员单独开权限，用【本群权限】。
    if not is_bot_owner(ev.user_id):
        await bot.send(ev, "权限不足：仅 bot 主人可以设置网页端权限")
        return

    qq_id, is_other = get_qid(ev)
    args = ev.message.extract_plain_text().split()

    # 没 @ 人时，把第一个参数当作 QQ 号：【网页权限 12345 1】
    if not is_other:
        if len(args) < 2 or not args[0].isdigit():
            await bot.send(ev, WEB_PRIORITY_HELP)
            return
        qq_id, args = int(args[0]), args[1:]

    if not args or args[0] not in ("0", "1", "2"):
        await bot.send(ev, WEB_PRIORITY_HELP)
        return

    level = int(args[0])
    if not await pcr_sqla.web_query_user(str(qq_id)):
        await bot.send(
            ev,
            f"{qq_id} 还没有网页端账号，"
            "请先让 ta 私聊机器人发送【网页端登录】获取账号后再设置权限",
        )
        return

    await pcr_sqla.change_web_priority(str(qq_id), level)
    await bot.send(
        ev, f"已把 {qq_id} 的网页端权限设为 {level}（{WEB_PRIORITY_NAMES[level]}）"
    )


@sv.on_prefix("本群权限")
async def set_group_priority(bot: HoshinoBot, ev: CQEvent):
    """本群权限 + @某人 + 等级：设置某人在「本群」的网页端权限

    和【网页权限】的区别：【网页权限】写全局账号等级（影响 ta 所属的所有群），
    【本群权限】只写本群这一条记录，适合群主给本群某个成员开「修正出刀」权限。
    群主 / 群管 / bot 主人可以设置。
    """
    if not is_group_manager(ev):
        await bot.send(ev, "权限不足：仅群主 / 群管 / bot 主人可以设置本群权限")
        return

    qq_id, is_other = get_qid(ev)
    args = ev.message.extract_plain_text().split()

    # 没 @ 人时，把第一个参数当作 QQ 号：【本群权限 12345 1】
    if not is_other:
        if len(args) < 2 or not args[0].isdigit():
            await bot.send(ev, GROUP_PRIORITY_HELP)
            return
        qq_id, args = int(args[0]), args[1:]

    # 2 级是群主/群管自动获得的，不给手动设，免得误操作把群主"降级"
    if not args or args[0] not in ("0", "1"):
        await bot.send(ev, GROUP_PRIORITY_HELP)
        return

    level = int(args[0])
    if await get_member_row(int(qq_id), ev.group_id) is None:
        await bot.send(
            ev,
            f"{qq_id} 还没有绑定本群公会，"
            "请先让 ta 在本群发送【绑定本群公会】后再设置权限",
        )
        return

    await pcr_sqla.change_member_priority(ev.group_id, int(qq_id), level)
    await bot.send(
        ev,
        f"已把 {qq_id} 在本群的网页端权限设为 {level}"
        f"（{WEB_PRIORITY_NAMES[level]}），仅对本群生效",
    )
