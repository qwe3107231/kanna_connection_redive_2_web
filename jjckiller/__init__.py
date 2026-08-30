import re
import time

import nonebot
from hoshino import Service, priv
from hoshino.typing import CQEvent, HoshinoBot
from hoshino.util import pic2b64
from nonebot import MessageSegment

from ..database.dal import pcr_sqla, Account
from ..login import query, run_group
from .base import best_route
from .get_img import general_img
from .model import ArenaPool, PrioritizedQueryItem, ArenaItem, arena_manager
from ..setting import ClientSetting
from ..util.decorator import check_account_qqid

arena_pool = ArenaPool(ClientSetting.jjc_max.value, 30, 20)

sv = Service(
    name="竞技场杀手",  # 功能名
    visible=True,  # 可见性
    enable_on_default=True,  # 默认启用
    help_="",  # 帮助说明
)

help_text = """
【竞技场监控】：监视排名变化，自动给出复仇阵容
【#竞技场监控】：同上，但是这个给群里挂，其余人无需再挂即可使用下面功能
【竞技场状态】：查看竞技场监控状态
【竞技场杀手 + (开启|关闭) + 竞技场】：开启竞技场提醒，默认全开
【竞技场杀手 + (开启|关闭) + 公主竞技场】：开启公主竞技场提醒，默认全开
【取消竞技场监控】：手动退出，对应【竞技场监控】
【#取消竞技场监控】：手动退出，对应【#竞技场监控】
【竞技场清次数+数字】：最大5，仅查询
【公主竞技场清次数】：最大5，仅查询，如果有之前打过的记录，则显示之前打过的防守
【竞技场排行榜+数字】：最大5，查询10名的排行榜，如1为1-10，2为11-20
【公主竞技场排行榜+数字】：最大5，同上
【竞技场查防守+数字】：迅速查作业
【公主竞技场查防守+数字】：如果有之前打过的记录，则显示之前打过的防守
【竞技场查ID+排名】：查询对应玩家信息
【公主竞技场查ID+排名】：查询对应玩家信息
！！！请注意，ID必须大写，加号默认忽略
""".strip()


@sv.on_fullmatch("竞技场杀手帮助")
async def jjc_help(bot: HoshinoBot, ev: CQEvent):
    await bot.send(ev, help_text)


@sv.on_prefix("竞技场监控", "#竞技场监控")
@check_account_qqid
async def jjc_monitor(bot: HoshinoBot, ev: CQEvent, account: Account, qq_id: int):
    is_group = "#" in ev.raw_message

    await bot.send(ev, f"正在登录账号，请耐心等待，当前监控玩家为{account.name}")

    try:
        arena = arena_manager.generate_arena(qq_id, ev.group_id if is_group else None)
        client = await query(account)
        await arena.init(client, ev.group_id, ev.self_id, account.platform)
    except Exception as e:
        # print(traceback.format_exc())
        await bot.send(ev, str(e))
        return

    run_group[ev.group_id] = ev.self_id
    loop_num = arena.loop_num
    await bot.send(
        ev,
        f"开始监控中, 可以发送【{'#' if is_group else ''}取消竞技场监控】或者顶号退出\n#监控编号HN100{loop_num}",
    )
    await arena_pool.add_task(PrioritizedQueryItem(data=ArenaItem(arena, loop_num)))


@sv.on_fullmatch("竞技场状态")
async def jjc_state(bot: HoshinoBot, ev: CQEvent):
    if not (arena := arena_manager.get_arena(ev.user_id, ev.group_id)):
        await bot.send(ev, "请先开启竞技场监控")
        return

    msg = "监控状态："
    if arena.loop_check:
        msg += "开启" + ("(高占用)" if time.time() - arena.loop_check > 30 else "")
    else:
        msg += "关闭"
    if arena.setting.jjc_notice:
        msg += f"\njjc: {arena.jjc_rank} ({arena.jjc_group})场"
    else:
        msg += "\n竞技场已关闭"
    if arena.setting.grand_notice:
        msg += f"\npjjc: {arena.grand_rank} ({arena.grand_group})场"
    else:
        msg += "\n公主竞技场已关闭"
    msg += f"\n当前监控编号HN100{arena.loop_num}"
    try:
        member_info = await bot.get_group_member_info(
            group_id=ev.group_id, user_id=arena.user_id
        )
        username = member_info["card"] or member_info["nickname"]
    except Exception:
        username = "桥本环奈"
    msg += f"\n当前监控人{username}"
    await bot.send(ev, msg)


@sv.on_rex(r"竞技场杀手(开启|关闭)(公主)?竞技场")
async def jjc_set(bot: HoshinoBot, ev: CQEvent):
    ret: re.Match = ev["match"]
    await pcr_sqla.update_jjc_setting(
        ev.user_id,
        {"grand_notice" if bool(ret[2]) else "jjc_notice": ret[1] == "开启"},
    )
    await bot.send(ev, "设置成功")


@sv.on_prefix("竞技场查ID", "公主竞技场查ID")
async def query_jjc_id(bot: HoshinoBot, ev: CQEvent):
    num: str = ev.message.extract_plain_text().strip()
    if not num.isdigit():
        await bot.send(ev, "你一定输入了奇怪的东西，爬爬")
        return
    if not (arena := arena_manager.get_arena(ev.user_id, ev.group_id)):
        await bot.send(ev, "请先开启竞技场监控")
        return
    num = int(num)
    is_grand = "公主" in ev.raw_message
    await arena.refresh_jjc_info(is_grand)
    if (is_grand and arena.grand_rank == num) or (
        not is_grand and arena.jjc_rank == num
    ):
        await bot.send(ev, "此为监控人，无需查询")
        return
    await bot.send(ev, await arena.jjc_query_id(num, is_grand))


@sv.on_fullmatch("取消竞技场监控", "#取消竞技场监控")
async def delete_jjc(bot: HoshinoBot, ev: CQEvent):
    is_group = "#" in ev.raw_message
    if not (
        arena := arena_manager.get_arena(ev.user_id, ev.group_id if is_group else None)
    ):
        await bot.send(ev, "未曾开过竞技场监控")
        return
    if ev.user_id == arena.user_id or priv.check_priv(ev, priv.ADMIN):
        arena.loop_num += 1
        arena_manager.delete_arena(ev.user_id, ev.group_id if is_group else None)
    else:
        await bot.send(ev, "你不是监控人或者管理")


@sv.on_prefix("#竞技场排行榜", "#公主竞技场排行榜")
async def jjc_rank_page(bot: HoshinoBot, ev: CQEvent):
    num: str = ev.message.extract_plain_text().strip()
    is_grand = "公主" in ev.raw_message
    if not num.isdigit():
        await bot.send(ev, "你一定输入了奇怪的东西，爬爬")
        return
    num = int(num)
    if num > 5 or num <= 0:
        await bot.send(ev, "?爬爬，你这个数")
        return
    if not (arena := arena_manager.get_arena(ev.user_id, ev.group_id)):
        await bot.send(ev, "请先开启竞技场监控")
        return
    msg = f"{'公主' if is_grand else ''}竞技场{arena.grand_group if is_grand else arena.jjc_group}号场"
    await bot.send(ev, f"正在查询，请稍等。当前为{msg}")
    imgs = await arena.jjc_query_page(num, is_grand)
    await bot.send(
        ev,
        MessageSegment.image(pic2b64(await general_img(imgs, True))),
    )


@sv.on_prefix("竞技场排行榜", "公主竞技场排行榜")
async def jjc_rank_page_simple(bot: HoshinoBot, ev: CQEvent):
    num: str = ev.message.extract_plain_text().strip()
    is_grand = "公主" in ev.raw_message
    if not num.isdigit():
        await bot.send(ev, "你一定输入了奇怪的东西，爬爬")
        return
    num = int(num)
    if num > 3 or num <= 0:
        await bot.send(ev, "?爬爬，你这个数")
        return
    if not (arena := arena_manager.get_arena(ev.user_id, ev.group_id)):
        await bot.send(ev, "请先开启竞技场监控")
        return
    msg = f"{'公主' if is_grand else ''}竞技场{arena.grand_group if is_grand else arena.jjc_group}号场"
    await bot.send(ev, f"正在查询，请稍等。当前为{msg}")
    msg = await arena.jjc_query_simple(num, is_grand)
    await bot.send(ev, "\n".join(msg))


@sv.on_prefix("竞技场清次数", "公主竞技场清次数")
async def jjc_route(bot: HoshinoBot, ev: CQEvent):
    num: str = ev.message.extract_plain_text().strip()
    is_grand = "公主" in ev.raw_message
    if not num.isdigit():
        await bot.send(ev, "你一定输入了奇怪的东西，爬爬")
        return
    num = int(num)
    if num > 5 or num <= 0:
        await bot.send(ev, "?爬爬，你这个数")
        return
    if not (arena := arena_manager.get_arena(ev.user_id)):
        await bot.send(ev, "请先开启竞技场监控")
        return

    await arena.refresh_jjc_info(is_grand)
    atk_list = best_route(arena.grand_rank if is_grand else arena.jjc_rank, num)
    await bot.send(ev, "最优击剑路径(大概)：" + ",".join(map(str, atk_list)))
    msg = (
        [await arena.grand_query(atk_rank) for atk_rank in atk_list]
        if is_grand
        else [await arena.jjc_query(atk_rank) for atk_rank in atk_list]
    )
    await bot.send(ev, MessageSegment.image(pic2b64(await general_img(msg))))


@sv.on_prefix("竞技场查防守", "公主竞技场查防守")
async def query_jjc(bot: HoshinoBot, ev: CQEvent):
    num: str = ev.message.extract_plain_text().strip()
    is_grand = "公主" in ev.raw_message
    if not num.isdigit():
        await bot.send(ev, "你一定输入了奇怪的东西，爬爬")
        return
    num = int(num)
    if num > 500 or num <= 0:
        await bot.send(ev, "?爬爬，你这个数")
        return
    if not (arena := arena_manager.get_arena(ev.user_id, ev.group_id)):
        await bot.send(ev, "请先开启竞技场监控")
        return

    await arena.refresh_jjc_info(is_grand)
    msg = await arena.grand_query(num) if is_grand else await arena.jjc_query(num)
    await bot.send(ev, MessageSegment.image(pic2b64(msg)))


@nonebot.on_startup
async def start_loop_handle():
    arena_pool.init()
