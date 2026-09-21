from typing import List, Optional

from nonebot import NoticeSession, get_bot, logger

from ..util.decorator import is_group_manager
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
（退群 / 被踢时 bot 会自动清掉你在本群的公会绑定和出刀通知，不用手动发）
【清理退群绑定】对账本群：清掉已经退群的人留下的公会绑定（群主 / 群管 / bot 主人）
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


@sv.on_notice("group_decrease")
async def auto_exit_clan(session: NoticeSession):
    """人不在群里了，自动清掉他在本群的公会绑定与出刀通知。

    这是【退出公会】的自动版。以前只有「人已经不在那个群、但绑定还留着」时，
    手动发【退出公会+群号】才能清理；现在退群 / 被踢当场就清。

    nonebot 的事件总线会从 `notice.group_decrease.leave` **逐级回溯**到
    `notice.group_decrease`，所以这一个处理器就能收到三种 sub_type：
      - leave   主动退群     → 清
      - kick    被管理员踢    → 清
      - kick_me bot 自己被踢  → **跳过**：这时 user_id 是 bot 自己，清它没有意义；
                               而且群里其他成员还在，他们的绑定必须保留

    只删 `ClanBattleMember` 那一行和本群通知，**不动出刀记录 / SL / KPI**
    —— 那些是战绩历史，删了会丢。正在跑的出刀监控也不受影响：监控的成员名单
    来自游戏内公会（`client.clan_info()`），跟这张 QQ↔群的绑定表无关。

    代价：管理员手动给过的 `ClanBattleMember.priority`（【本群权限】）会跟着一起丢，
    重新进群要重新给；群主 / 群管的 2 级是自动识别的，不受影响。
    """
    ev = session.event
    # kick_me 时 user_id 就是 bot 自己 —— 别把它当成「有成员退群」来处理。
    if ev.sub_type == "kick_me" or ev.user_id == ev.self_id:
        return
    group_id, user_id = ev.group_id, ev.user_id
    if group_id is None or user_id is None:
        return

    removed = await pcr_sqla.delete_member(group_id, user_id)
    notices = await pcr_sqla.delete_notice_by_user(group_id, user_id)
    if removed or notices:
        logger.info(
            f"成员 {user_id} 退出群 {group_id}："
            f"自动清理公会绑定 {removed} 条、出刀通知 {notices} 条"
        )


async def _fetch_group_member_ids(bot: HoshinoBot, group_id: int) -> Optional[set]:
    """取群成员 QQ 集合；接口失败或返回空都返回 None。

    **只回答「接口给没给出一份可用的名单」，不代表这份名单是完整的** ——
    完整性由 `clean_stale_members` 里的护栏负责判。
    """
    try:
        members = await bot.get_group_member_list(group_id=int(group_id))
    except Exception as e:
        logger.warning(f"获取群 {group_id} 成员列表失败：{e}")
        return None
    if not members:
        return None
    return {int(m["user_id"]) for m in members if m.get("user_id")}


async def clean_stale_members(bot: HoshinoBot, group_id: int) -> Optional[List[int]]:
    """对账本群：把「已经不在群里」的人留下的公会绑定清掉。

    返回被清掉的 QQ 列表；**返回 None 表示这次没敢动手**（名单不可信），
    调用方要把它和「没有需要清理的人」区分开。

    为什么需要它 —— `group_decrease` 事件是「当场清」，但它会漏：
      - 退群那一刻 bot 掉线 / 协议端没上报 / 本群禁用了「成员管理」服务；
      - 以及**本功能上线之前**就已经退群的人，事件早就过去了。
    而绑定就是 web 端访问权的唯一凭证（`webui/util.py: ensure_group_access`），
    留着脏绑定 = 退群的人还能看本群数据。

    **三条安全护栏，缺一不可**（接口抽风时宁可漏清，也不能把全群绑定删光）：
      1. 名单拿不到或为空 → 不动手；
      2. **bot 自己必须出现在名单里** —— bot 明明在这个群里、名单里却没有它，
         说明这份名单是残缺的（分页 / 限流 / 协议端实现差异），一律不信；
      3. 逐条比对，只删名单里确实没有的 QQ。

    清掉的东西和事件路径一致：**公会绑定 + 本群出刀通知**。
    **不动出刀记录 / SL / KPI** —— 那是战绩历史，删了会丢。
    """
    ids = await _fetch_group_member_ids(bot, group_id)
    if ids is None:
        return None
    self_id = getattr(bot, "self_id", None)
    if not self_id or int(self_id) not in ids:
        logger.warning(
            f"群 {group_id} 对账跳过：成员名单里没有 bot 自己"
            f"（self_id={self_id}，名单 {len(ids)} 人），判定名单不可信"
        )
        return None

    removed: List[int] = []
    for member in await pcr_sqla.get_group_member(group_id):
        uid = int(member.user_id)
        if uid in ids:
            continue
        gone = await pcr_sqla.delete_member(group_id, uid)
        await pcr_sqla.delete_notice_by_user(group_id, uid)
        if gone:
            removed.append(uid)
    return removed


@sv.on_fullmatch("清理退群绑定")
async def clean_stale_members_cmd(bot: HoshinoBot, ev: CQEvent):
    """对账本群，清掉已退群成员留下的公会绑定（群主 / 群管 / bot 主人）。

    给【清理退群绑定】留一个手动入口，是因为自动路径有两处够不着：
    刚退群但事件漏收（想立刻处理，不想等每天那次对账），
    以及本功能上线前就已经退群的历史脏数据。
    """
    if not is_group_manager(ev):
        await bot.send(ev, "很抱歉您没有权限进行此操作，该操作仅群主 / 群管")
        return
    group_id = ev.group_id
    if group_id is None:
        await bot.send(ev, "这条指令要在群里发，它清的是本群的绑定")
        return

    removed = await clean_stale_members(bot, group_id)
    if removed is None:
        await bot.send(
            ev,
            "获取群成员列表失败（或名单不完整），已跳过本次清理 —— **没有改动任何数据**，请稍后再试",
        )
        return
    if not removed:
        await bot.send(ev, "本群没有需要清理的绑定，绑定过的人都在群里")
        return
    qq_list = "、".join(str(q) for q in removed)
    await bot.send(
        ev,
        f"已清理 {len(removed)} 个已退群成员的公会绑定（连同他们的出刀通知）：\n{qq_list}",
    )


@sv.scheduled_job("cron", hour="4", minute="30")
async def daily_clean_stale_members():
    """每天 4:30 对所有「有人绑定过」的群做一次对账。

    兜住 `group_decrease` 漏收的情况；静默执行、只写日志，不在群里发消息。
    每个群独立 try，一个群失败不影响其他群。
    """
    try:
        bot = get_bot()
    except Exception as e:
        logger.warning(f"退群绑定对账跳过：拿不到 bot 实例（{e}）")
        return
    for row in await pcr_sqla.get_bound_groups():
        group_id = int(row.group_id)
        try:
            removed = await clean_stale_members(bot, group_id)
        except Exception as e:
            logger.warning(f"群 {group_id} 退群绑定对账异常：{e}")
            continue
        if removed is None:
            logger.info(f"群 {group_id} 退群绑定对账跳过（成员名单不可信，未改动数据）")
        elif removed:
            logger.info(f"群 {group_id} 退群绑定对账：清理了 {len(removed)} 条 {removed}")
