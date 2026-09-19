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
【退出公会】在哪个群发就退出哪个群的公会；也可【退出公会+群号】退出指定群
（带群号是留给「人已经不在那个群、但绑定还留着」的情况）
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
async def bind_clan(bot: HoshinoBot, ev: CQEvent):
    """在本群发指令即可绑定本群（无需先绑定游戏账号）。
    必须人在群里才能发这条指令，天然防止绑定到别的群看别人数据。"""
    try:
        group_info = await bot.get_group_info(group_id=ev.group_id)
        group_name = group_info["group_name"]
    except Exception:
        group_name = "环奈连结"
    await pcr_sqla.add_member(
        ClanBattleMember(group_id=ev.group_id, user_id=ev.user_id, group_name=group_name)
    )
    await bot.send(ev, "绑定本群公会成功")


@sv.on_prefix("删除本群公会绑定")
async def delete_clan_bind(bot: HoshinoBot, ev: CQEvent):
    """把某人踢出本群的公会绑定。

    不带参数 = 删自己；@某人 或跟一个 QQ 号 = 删别人（需要管理员）。
    跟的 QQ 号必须是纯数字 —— 以前直接 `int()`，输错（比如「删除本群公会绑定 abc」）
    就抛 ValueError 被 nonebot 吞掉，用户什么提示都收不到（和【退出公会】原来那个
    bug 同型）。
    """
    arg = ev.message.extract_plain_text().strip()
    if arg:
        if not arg.isdigit():
            await bot.send(ev, "QQ 号要填纯数字，示例：【删除本群公会绑定】或【删除本群公会绑定 123456】")
            return
        qq_id, is_other = int(arg), True
    else:
        qq_id, is_other = get_qid(ev)
    if is_other and not priv.check_priv(ev, priv.ADMIN):
        msg = "很抱歉您没有权限进行此操作，该操作仅管理员"
        await bot.send(ev, msg)
        return

    # 私聊里 ev.group_id 是 None（aiocqhttp 取不到字段返回 None，不是抛异常），
    # 而这条指令删的就是「本群」的绑定，没群可删直接给提示。
    group_id = ev.group_id
    if group_id is None:
        await bot.send(ev, "这条指令要在群里发，它删的是本群的绑定")
        return

    if await pcr_sqla.delete_member(group_id, qq_id):
        await bot.send(ev, "删除本群公会绑定成功")
    else:
        await bot.send(ev, f"群 {group_id} 里没有 QQ {qq_id} 的绑定记录")


@sv.on_prefix("退出公会")
async def exit_clan(bot: HoshinoBot, ev: CQEvent):
    """退出公会绑定。

    不带群号：退出「当前这个群」的绑定 —— 在哪个群发就退哪个群，这是最直觉的用法。
    带群号  ：退出指定群的绑定。留给「人已经不在那个群、但绑定还留着」的情况：
              不在群里就没法在那个群发指令，只能从别处指定群号。

    只删自己那条（ev.user_id），删不了别人 —— 要踢人用【删除本群公会绑定 @某人】。
    """
    arg = ev.message.extract_plain_text().strip()
    if arg:
        if not arg.isdigit():
            await bot.send(ev, "群号要填纯数字，示例：【退出公会】或【退出公会 123456】")
            return
        group_id = int(arg)
    else:
        # 群消息里 ev.group_id 就是本群；私聊里它是 None（aiocqhttp 的 Event 取不到字段
        # 返回 None 而不是抛异常），所以这里必须单独判一下。
        group_id = ev.group_id
        if group_id is None:
            await bot.send(ev, "私聊里请带上群号，示例：【退出公会 123456】")
            return

    if await pcr_sqla.delete_member(group_id, ev.user_id):
        await bot.send(ev, f"已退出群 {group_id} 的公会")
    else:
        await bot.send(ev, f"你在群 {group_id} 没有公会绑定记录，无需退出")
