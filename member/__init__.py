from ..util.decorator import check_account_qqid
from ..util.tools import get_qid
from ..database.dal import pcr_sqla
from ..database.models import Account, ClanBattleMember
from ..basedata import AllowLevel
from hoshino import Service, priv
from hoshino.typing import CQEvent
from hoshino.typing import HoshinoBot

help_text = """
【绑定本群公会】将自己绑定在这个群
【删除本群公会绑定】将自己踢出公会（管理可以at别人实现踢人效果/输入qq）
【退出公会+群号】将自己踢出公会，用于自己不在公会
【账号权限变更+数字】0：默认，只允许本人。1：允许管理，2：任何人
""".strip()

sv = Service(
    name="成员管理",  # 功能名
    visible=False,  # 可见性
    enable_on_default=True,  # 默认启用
    help_=help_text,  # 帮助说明
)


@sv.on_fullmatch("成员管理帮助")
async def member_help(bot: HoshinoBot, ev: CQEvent):
    await bot.send(ev, help_text)


@sv.on_prefix("账号权限变更")
async def change_account_access(bot: HoshinoBot, ev: CQEvent):
    user_id = ev.user_id
    if not (account := await pcr_sqla.query_account(user_id)):
        await bot.send(ev, "你没有绑定账号")
        return

    num: str = ev.message.extract_plain_text().strip()

    if not num.isdigit():
        await bot.send(ev, "需要数字")
        return

    num = int(num)

    account = account[0]

    if num not in AllowLevel._value2member_map_:
        await bot.send(ev, "无效权限等级")
        return

    await pcr_sqla.change_access(user_id, num)
    await bot.send(ev, "修改成功")


@sv.on_fullmatch("绑定本群公会")
@check_account_qqid
async def bind_clan(bot: HoshinoBot, ev: CQEvent, account: Account, qq_id):
    try:
        group_info = await bot.get_group_info(group_id=ev.group_id)
        group_name = group_info["group_name"]
    except Exception:
        group_name = "环奈连结"
    await pcr_sqla.add_member(
        ClanBattleMember(group_id=ev.group_id, user_id=qq_id, group_name=group_name)
    )
    await bot.send(ev, "绑定本群公会成功")


@sv.on_prefix("删除本群公会绑定")
async def delete_clan_bind(bot: HoshinoBot, ev: CQEvent):
    if qq_id := ev.message.extract_plain_text().strip():
        qq_id = int(qq_id)
        is_other = True
    else:
        qq_id, is_other = get_qid(ev)
    if is_other and not priv.check_priv(ev, priv.ADMIN):
        msg = "很抱歉您没有权限进行此操作，该操作仅管理员"
        await bot.send(ev, msg)
        return
    await pcr_sqla.delete_member(ev.group_id, qq_id)
    await bot.send(ev, "删除本群公会绑定成功")


@sv.on_prefix("退出公会")
async def exit_clan(bot: HoshinoBot, ev: CQEvent):
    group_id = int(ev.message.extract_plain_text().strip())
    await pcr_sqla.delete_member(group_id, ev.user_id)
    await bot.send(ev, "退出公会成功")
