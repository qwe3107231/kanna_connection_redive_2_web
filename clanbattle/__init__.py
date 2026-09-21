import re
import time
from typing import Dict

import nonebot
from hoshino import Service, priv
from hoshino.typing import CQEvent, HoshinoBot
from loguru import logger

from ..basedata import NoticeType
from ..database.dal import pcr_sqla, Account, RecordDao
from ..database.models import ClanBattleKPI, NoticeCache, SLDao
from ..login import query
from ..setting import ClientSetting
from ..util.auto_boss import clan_boss_info
from ..util.decorator import (
    check_account_qqid,
    check_priv_adimin,
    is_group_manager,
)
from .base import (
    DEFAULT_RANK_LINES,
    format_time,
    get_cbreport,
    get_plyerreport,
    get_stat,
    dao_detial,
    day_report,
    cuidao,
    get_kpireport,
    clanbattle_report,
    get_rank_lines_cached,
    is_monitor_running,
    rank_lines_pic,
)

from .kpi import kpi_report
from .model import ClanBattle, ClanbattleItem, ClanBattlePool, PrioritizedQueryItem

help_text = """
* “+” 表示空格
【出刀监控】机器人登录账号，监视出刀情况并记录
【催刀】栞栞谁没出满三刀
【当前战报】本期会战出刀情况
【我的战报 + 游戏名称】 栞栞个人出刀情况
【今日战报 + 游戏名称】 栞栞今日个人出刀情况
【昨日战报 + 游戏名称】 栞栞昨日个人出刀情况
【出刀详情 + 出刀编号】 栞栞你这刀怎么出的（出刀编号可以通过查看个人战报获得）
【今日出刀】今日出刀情况
【昨日出刀】昨日出刀情况
【启用肃正协议】数据出现异常使用即可清空所有数据（危险！！！）
【状态】查看当前进度
【预约表】栞栞谁预约了
【预约 + 数字 + （周目）+ （留言） 】预约boss, 周目和留言可不写，默认当前周目
【取消预约 + （数字）】取消预约
【清空预约 + （数字）】（仅）管理，清空预约
【查树】栞栞树上有几个人
【查档线 + 排名】查本届会战档线，可查任意排名如【查档线 500 2000】，不带参数显示常用档位
【下树】寄，掉刀了
【挂树 + 数字】失误了, 寄
【sl】记录sl
【sl?】栞栞今天有没有用过sl
【申请出刀 + 数字 + （留言） 】 申请打boss，boss死亡自动清空
【取消申请】 模拟10次挂10次，老子不打了
【清空申请】（仅）管理，清空预约
【修正出刀 + 出刀编号 + (完整刀|尾刀|补偿)"】修正错误刀（出刀编号可以通过查看个人战报获得）
【会战KPI】查看等效出刀数
【kpi调整 + 游戏id + 补正】给某个玩家额外的kpi点数，可正可负
【清空kpi】删除所有kpi补正
【删除kpi+ 游戏id】删除特定补正
【开启推送】/【关闭推送】开关本群的主动推送（出刀人数、出刀伤害、预约、挂树），默认开启
""".strip()

clanbattle_info: Dict[int, ClanBattle] = {}
notice_update_time: Dict[int, int] = {}
clanbattle_pool = ClanBattlePool(ClientSetting.clanbattle_max.value)

sv = Service(
    name="自动报刀2",  # 功能名
    visible=True,  # 可见性
    enable_on_default=True,  # 默认启用
    help_=help_text,  # 帮助说明
)


@sv.on_fullmatch("自动报刀帮助")
async def clanbattle_help(bot: HoshinoBot, ev: CQEvent):
    await bot.send(ev, help_text)


@sv.on_prefix("出刀监控")
@check_account_qqid
async def clanbattle_monitor(
    bot: HoshinoBot, ev: CQEvent, account: Account, qq_id: int
):

    group_id = ev.group_id

    await bot.send(ev, f"正在登录账号，请耐心等待，当前监控玩家为{account.name}")

    # 初始化
    if group_id not in clanbattle_info:
        clanbattle_info[group_id] = ClanBattle(group_id)
    clan_info = clanbattle_info[group_id]
    try:
        await clan_info.init(await query(account), qq_id, ev.self_id)
    except Exception:
        try:
            await clan_info.init(await query(account, True), qq_id, ev.self_id)
        except Exception as e:
            await bot.send(
                ev, "初始化多次失败，请重绑账号或者手动上号检查是否可登录后重试"
            )
            await bot.send(ev, str(e))
            return

    # 换过公会就把上一份公会深域缓存作废。只能在这里判：监控没开时拿不到当前
    # 公会 ID，读取路径上没法比对。不换会时这个调用是 no-op，缓存照旧留着。
    if group_id:
        try:
            if await pcr_sqla.clear_deep_domain_cache_if_clan_changed(
                group_id, int(getattr(clan_info, "clan_id", 0) or 0)
            ):
                logger.info(f"群 {group_id} 的公会已变更，上一份公会深域缓存已作废")
        except Exception as e:
            # 清缓存失败不该影响监控本身
            logger.warning(f"公会深域缓存作废检查失败 group={group_id}：{e!r}")

    loop_num = clan_info.loop_num
    await bot.send(
        ev,
        f"开始监控中, 可以发送【取消出刀监控】或者顶号退出\n#监控编号HN000{loop_num}",
    )
    await clanbattle_pool.add_task(
        PrioritizedQueryItem(data=ClanbattleItem(clan_info, loop_num))
    )


@sv.on_fullmatch("取消出刀监控")
async def delete_monitor(bot: HoshinoBot, ev: CQEvent):
    group_id = ev.group_id
    qq_id = ev.user_id
    if group_id not in clanbattle_info:
        await bot.send(ev, "本群未曾开过出刀监控")
        return
    clan_info = clanbattle_info[group_id]
    if qq_id == clan_info.user_id or priv.check_priv(ev, priv.ADMIN):
        clan_info.loop_num += 1
        # 顺手把「监控在跑」标记清掉：只改 loop_num 的话，要等监控循环下一轮醒来
        # （最多 15~30 秒）才会真正退出，这中间网页端仍会认为本群「监控运行中」，
        # 一开仪表盘就去游戏侧抓档线 —— 抓失败会触发重登，把正在玩游戏的群友顶下线。
        # 网页端的「取消监控」早就这么做了（api.py 里同样置 0），这里补齐。
        clan_info.loop_check = 0
    else:
        await bot.send(ev, "你不是监控人或者管理")


async def _switch_push(bot: HoshinoBot, ev: CQEvent, enabled: bool):
    """开关本群的「主动推送」

    出刀监控跑起来后会主动往群里播报：出刀人数、出刀伤害、预约、挂树。
    这些播报**按群**开关 —— 在 A 群关掉不影响 B 群。
    权限：本群群主 / 群管，或 bot 主人。
    """
    if ev.group_id is None:
        await bot.send(ev, "这个开关是按群设置的，请在群里使用")
        return
    if not is_group_manager(ev):
        await bot.send(ev, "权限不足，需要本群群主 / 群管或 bot 主人", at_sender=True)
        return

    await pcr_sqla.set_push_enabled(int(ev.group_id), enabled)
    if enabled:
        await bot.send(ev, "已开启本群的主动推送（出刀人数 / 出刀伤害 / 预约 / 挂树）")
    else:
        await bot.send(
            ev,
            "已关闭本群的主动推送：出刀监控照常记录数据，只是不再往群里播报。\n"
            "主动查询（【当前战报】【今日出刀】【状态】等）不受影响。",
        )


@sv.on_fullmatch(("开启推送", "打开推送"))
async def open_push(bot: HoshinoBot, ev: CQEvent):
    await _switch_push(bot, ev, True)


@sv.on_fullmatch(("关闭推送", "关闭主动推送"))
async def close_push(bot: HoshinoBot, ev: CQEvent):
    await _switch_push(bot, ev, False)


@sv.on_fullmatch("状态")
async def daostate(bot: HoshinoBot, ev: CQEvent):
    group_id = ev.group_id
    if group_id not in clanbattle_info:
        await bot.send(ev, "未查询到本群当前进度，请开启出刀监控")
        return

    clan_info = clanbattle_info[group_id]
    now = time.time()
    msg = f"当前排名：{clan_info.rank}\n监控状态："
    if clan_info.loop_check:
        msg += "开启"
        try:
            member_info = await bot.get_group_member_info(
                group_id=group_id, user_id=clan_info.user_id
            )
            username = member_info["card"] or member_info["nickname"]
        except Exception:
            username = "桥本环奈"
        msg += f"\n监控人为：{username}"
        msg += "(高占用)" if now - clan_info.loop_check > 30 else ""
    else:
        msg += "关闭"
    msg += "\n" + clan_info.general_boss()
    await bot.send(ev, msg)

    msg = ""
    for i in range(1, 5 + 1):
        if apply_info := await pcr_sqla.get_notice(NoticeType.apply.value, group_id, i):
            msg += f"========={i}王=========\n"
            msg += f"当前有{len(apply_info)}人申请挑战boss\n"
            for i, info in enumerate(apply_info):
                member_info = await bot.get_group_member_info(
                    group_id=group_id, user_id=info.user_id
                )
                name = member_info["card"] or member_info["nickname"]
                msg += f"->{i+1}：{name} {info.text} 已过去{format_time(now - info.time)}\n"
    if msg:
        await bot.send(ev, msg.strip())


@sv.on_prefix("查档线", "档线")
async def query_clan_rank_lines(bot: HoshinoBot, ev: CQEvent):
    """查档线 [排名...]：默认展示常用档位，可自定义排名（如 查档线 500 2000）"""
    group_id = ev.group_id
    clan_info = clanbattle_info.get(group_id)
    # 必须判「真的在跑」而不是「开过监控」：【取消出刀监控】之后对象还留在
    # clanbattle_info 里，只看在不在字典里会拿一个已停掉的监控去抓档线。
    if not is_monitor_running(clan_info):
        await bot.send(ev, "请先开启出刀监控，再查档线")
        return

    # 解析自定义档位参数（支持空格分隔多个）
    arg = ev.message.extract_plain_text().strip()
    if arg:
        try:
            targets = [int(x) for x in arg.split()]
        except ValueError:
            await bot.send(ev, "排名参数格式不对，示例：查档线 或 查档线 500 2000")
            return
    else:
        targets = list(DEFAULT_RANK_LINES)

    try:
        # 走本地缓存：游戏侧档线每半小时才更新一次，可抓一次要打十几次分页请求，
        # 而且接口一失败就会把功能永久禁用。缓存 TTL 25 分钟，拿到的数据最多比
        # 游戏侧晚一轮，但接口调用量降一个数量级（网页端仪表盘共用同一份缓存）。
        result = await get_rank_lines_cached(clan_info, targets)
    except ValueError as e:
        await bot.send(ev, str(e))
        return
    except Exception as e:
        logger.error(f"查档线失败: {e}")
        await bot.send(ev, f"查档线失败：{e}")
        return

    data = result["data"]
    updated_at = result["updated_at"]

    # 优先图片输出，生成失败时退回文字
    try:
        await bot.send(ev, rank_lines_pic(data, ev.user_id, updated_at))
        return
    except Exception as e:
        logger.warning(f"档线图片生成失败，改用文字输出: {e}")

    def _fmt(num: int) -> str:
        return f"{num:,}" if num is not None else "未知"

    msg = f"📡 本届会战档线（编号{data['clan_battle_id']}）\n"
    if updated_at:
        msg += f"🕒 数据时间 {time.strftime('%m-%d %H:%M', time.localtime(int(updated_at)))}\n"
    for line in data["lines"]:
        if line is None:
            msg += "─" * 14 + "\n该档位暂无数据\n"
            continue
        rw = line.get("reward") or {}
        msg += (
            f"🏅{line['rank']}名 {_fmt(line['damage'])}\n"
            f"　└ {line['clan_name']}（{line['member_num']}人/{line['leader_name']}）\n"
        )
        if rw:
            msg += f"　└ 🎁 宝石×{rw.get('gem')} 行会币×{rw.get('coin')} 碎片×{rw.get('shard')}\n"
    my = data["my"]
    msg += "─" * 14 + f"\n📊 我会排名：{my['rank']}名 伤害：{_fmt(my['damage'])}"
    # 计算与上一档线的差距（上一档 = 排名比我好的最近档位）
    better_lines = [
        line for line in data["lines"] if line and my["rank"] and line["rank"] < my["rank"]
    ]
    if better_lines and my["damage"] is not None:
        prev = max(better_lines, key=lambda x: x["rank"])
        diff = prev["damage"] - my["damage"]
        if diff <= 0:
            msg += f"\n🚀 已超过{prev['rank']}名档线 {abs(diff):,} 伤害"
        else:
            msg += f"\n📈 距{prev['rank']}名档线还差 {diff:,}（约 {diff // 100000000} 亿）"
    await bot.send(ev, msg.strip())


@sv.on_rex(r"^预约\s?(\d)(\s\d+)?(\s\S*)?$")
async def subscirbe(bot: HoshinoBot, ev: CQEvent):
    match = ev["match"]
    boss = int(match.group(1))
    lap = int(match.group(2)[1:]) if match.group(2) else 0

    if boss > 5 or boss < 1:
        await bot.send(ev, "不约，滚")
        return

    text = text[1:] if (text := match.group(3)) else ""
    await pcr_sqla.add_notice(
        NoticeCache(
            group_id=ev.group_id,
            notice_type=NoticeType.subscribe.value,
            user_id=ev.user_id,
            boss=boss,
            lap=lap,
            text=text,
        )
    )
    notice_update_time[ev.group_id] = int(time.time())
    await bot.send(ev, "预约成功", at_sender=True)


@sv.on_fullmatch("预约表", only_to_me=False)
async def formsubscribe(bot: HoshinoBot, ev: CQEvent):
    group_id = ev.group_id
    FormSubscribe = ""
    subscribers = []
    for boss in range(1, 5 + 1):
        if info := await pcr_sqla.get_notice(
            NoticeType.subscribe.value, group_id, boss
        ):
            for player in info:
                lap = f"第{player.lap}周目" if player.lap else "当前周目"
                info = await bot.get_group_member_info(
                    group_id=ev.group_id, user_id=player.user_id
                )
                name = "card" if info["card"] else "nickname"
                msg = (
                    f"{info[name]}:{player.text}" if player.text else info[name]
                ) + f" {lap}"
                subscribers.append(msg)
        if subscribers:
            FormSubscribe += f"\n========={boss}王=========\n" + "\n".join(subscribers)
            subscribers.clear()

    await bot.send(
        ev, f"当前预约列表{FormSubscribe}" if FormSubscribe else "无人预约呢喵"
    )


@sv.on_rex(r"^取消预约\s?(\d)$")
@check_priv_adimin()
async def cancelsubscirbe(bot: HoshinoBot, ev: CQEvent, qq_id: int):
    boss = int(ev["match"].group(1))

    if boss > 5 or boss < 1:
        await bot.send(ev, "爬爬")
        return

    await pcr_sqla.delete_notice(NoticeType.subscribe.value, ev.group_id, boss, qq_id)
    notice_update_time[ev.group_id] = int(time.time())
    await bot.send(ev, "取消成功", at_sender=True)


@sv.on_rex(r"^清空预约\s?(\d)$")
@check_priv_adimin(False)
async def cleansubscirbe(bot: HoshinoBot, ev: CQEvent, qq_id: int):

    boss = int(ev["match"].group(1))
    if boss > 5 or boss < 1:
        await bot.send(ev, "爬爬")
        return

    await pcr_sqla.delete_notice(NoticeType.subscribe.value, ev.group_id, boss)
    notice_update_time[ev.group_id] = int(time.time())
    await bot.send(ev, "清除成功", at_sender=True)


@sv.on_fullmatch(("sl", "SL", "Sl"))
async def addsl(bot: HoshinoBot, ev: CQEvent):

    if await pcr_sqla.add_sl(
        SLDao(group_id=ev.group_id, user_id=ev.user_id, time=int(time.time()))
    ):
        notice_update_time[ev.group_id] = int(time.time())
        await bot.send(ev, "SL已记录", at_sender=True)
    else:
        await bot.send(ev, "今天已经SL过了", at_sender=True)


@sv.on_fullmatch(("sl?", "SL?", "sl？", "SL？"))
async def issl(bot: HoshinoBot, ev: CQEvent):
    if await pcr_sqla.check_sl(ev.user_id, ev.group_id):
        await bot.send(ev, "今天已经SL过了", at_sender=True)
    else:
        await bot.send(ev, "今天还没有使用过SL", at_sender=True)


@sv.on_rex(r"^(上|挂)树\s?(\d)\s?(.+)?$")
async def climbtree(bot: HoshinoBot, ev: CQEvent):
    match: re.Match = ev["match"]
    boss = match[2]
    text = match[3] or " "
    await pcr_sqla.add_notice(
        NoticeCache(
            group_id=ev.group_id,
            notice_type=NoticeType.tree.value,
            user_id=ev.user_id,
            boss=boss,
            text=text,
        )
    )
    notice_update_time[ev.group_id] = int(time.time())
    await bot.send(ev, "上树成功", at_sender=True)


@sv.on_fullmatch("下树")
async def offtree(bot: HoshinoBot, ev: CQEvent):
    await pcr_sqla.delete_notice(NoticeType.tree.value, ev.group_id, user_id=ev.user_id)
    notice_update_time[ev.group_id] = int(time.time())
    await bot.send(ev, "下树成功", at_sender=True)


@sv.on_fullmatch("查树")
async def checktree(bot: HoshinoBot, ev: CQEvent):
    reply = ""
    for i in range(1, 5 + 1):
        if info := await pcr_sqla.get_notice(NoticeType.tree.value, ev.group_id, i):
            reply += f"{i}王树上目前有{len(info)}人\n"
            for i, player in enumerate(info):
                player_info = await bot.get_group_member_info(
                    group_id=ev.group_id, user_id=player.user_id
                )
                reply += f'->{i+1}：{player_info["card" if player_info["card"] else "nickname"]} {player.text} 已过去{format_time(time.time() - player.time)}\n'
    await bot.send(ev, reply or "目前树上空空如也")


@sv.on_rex(r"^申请出刀\s?(\d)\s?(\S+)?$")
async def apply(bot: HoshinoBot, ev: CQEvent):

    match: re.Match = ev["match"]
    boss = match[1]
    text = match[2] or ""
    now = time.time()
    await pcr_sqla.add_notice(
        NoticeCache(
            group_id=ev.group_id,
            notice_type=NoticeType.apply.value,
            user_id=ev.user_id,
            boss=boss,
            text=text,
        )
    )
    notice_update_time[ev.group_id] = int(time.time())
    await bot.send(ev, "申请成功", at_sender=True)
    msg = ""
    apply_info = await pcr_sqla.get_notice(
        NoticeType.apply.value, ev.group_id, int(boss)
    )
    msg += f"========={boss}王=========\n"
    msg += f"当前有{len(apply_info)}人申请挑战boss\n"
    for i, info in enumerate(apply_info):
        member_info = await bot.get_group_member_info(
            group_id=ev.group_id, user_id=info.user_id
        )
        name = member_info["card"] or member_info["nickname"]
        msg += f"->{i+1}：{name} {info.text} 已过去{format_time(now - info.time)}\n"
    await bot.send(ev, msg.strip())


@sv.on_prefix("取消申请")
@check_priv_adimin()
async def cancel_apply(bot: HoshinoBot, ev: CQEvent, qq_id: int):

    await pcr_sqla.delete_notice(NoticeType.apply.value, ev.group_id, user_id=qq_id)
    notice_update_time[ev.group_id] = int(time.time())
    await bot.send(ev, "取消成功", at_sender=True)


@sv.on_fullmatch("清空申请")
@check_priv_adimin(False)
async def clear_apply(bot: HoshinoBot, ev: CQEvent, qq_id: int):
    await pcr_sqla.delete_notice(NoticeType.apply.value, ev.group_id)
    notice_update_time[ev.group_id] = int(time.time())
    await bot.send(ev, "清空成功", at_sender=True)


@sv.on_fullmatch("今日出刀", "昨日出刀")
async def dao_state(bot: HoshinoBot, ev: CQEvent):
    group_id = ev.group_id
    members = {}
    if group_id not in clanbattle_info:
        await bot.send(ev, "未开启出刀监控,不显示没出刀的人")
    else:
        members = clanbattle_info[group_id].members
    data = (
        await pcr_sqla.get_day_rcords(int(time.time()), group_id)
        if "今日" in ev.raw_message
        else await pcr_sqla.get_day_rcords(int(time.time()) - 3600 * 24, group_id)
    )
    await bot.send(ev, await get_stat(await day_report(data, members)))


@sv.on_fullmatch("启用肃正协议")
async def kill_all(bot: HoshinoBot, ev: CQEvent):
    await pcr_sqla.refresh(RecordDao, -1, ev.group_id)
    await bot.send(
        ev,
        "[WARNING]肃正协议将清理一切事物（不分敌我），期间出现任何报错均为正常现象，事后请重新开启出刀监控",
    )


@sv.on_fullmatch("当前战报")
async def get_report(bot: HoshinoBot, ev: CQEvent):
    if not (data := await pcr_sqla.get_all_records(ev.group_id)):
        await bot.send(ev, "数据库为空，请确保开启出刀监控")
        return
    players, all_damage, all_score = clanbattle_report(
        data, await pcr_sqla.get_max_dao(ev.group_id)
    )
    await bot.send(ev, await get_cbreport(players, all_damage, all_score))


@sv.on_prefix("今日战报", "昨日战报", "我的战报")
async def player_report(bot: HoshinoBot, ev: CQEvent):
    name: str = ev.message.extract_plain_text().strip()
    if (preid := ev.prefix[:2]) == "今日":
        day = 0
    elif preid == "昨日":
        day = 1
    else:
        day = 5
    data = None
    if name.isdigit():
        data = await pcr_sqla.get_player_records(int(name), day, ev.group_id)
    if not data:
        members = await pcr_sqla.clanbattle_name2pcrid(ev.group_id, name)
        if not members:
            await bot.send(ev, "昵称错误")
            return
        if len(members) != 1:
            await bot.send(
                ev,
                "出现重名，请使用id查询，以下是可能id"
                + "\n".join([str(x) for x in members[:3]]),
            )
            return
        pcrid = members[0]
        data = await pcr_sqla.get_player_records(pcrid, day, ev.group_id)

    if not data:
        await bot.send(ev, "数据库为空，请确保开启出刀监控或使用正确的角色名")
        return
    await bot.send(ev, await get_plyerreport(data))


@sv.on_prefix("出刀详情")
async def single_player_report(bot: HoshinoBot, ev: CQEvent):
    if _id := ev.message.extract_plain_text().strip():
        if not _id.isdigit():
            await bot.send(ev, "请输入正确的出刀编号")
        elif info := await pcr_sqla.get_history(int(_id), ev.group_id):
            await bot.send(ev, await dao_detial(info))
        else:
            await bot.send(ev, "请检查你的出刀编号是否正确。")


@sv.on_rex(r"修正出刀\s?(\d+)\s?(完整刀|尾刀|补偿)")
async def correct_dao(bot: HoshinoBot, ev: CQEvent):
    info: re.Match = ev["match"]
    dao = info[2]
    if await pcr_sqla.correct_dao(
        int(info[1]), 0 if dao == "完整刀" else 1 if dao == "尾刀" else 0.5, ev.group_id
    ):
        await bot.send(ev, "修改成功")
    else:
        await bot.send(ev, "请检查你输入了正确的出刀编号")


@sv.on_fullmatch("催刀")
async def nei_gui(bot: HoshinoBot, ev: CQEvent):
    group_id = ev.group_id
    members = {}
    if group_id not in clanbattle_info:
        await bot.send(ev, "未开启出刀监控,不显示没出刀的人")
    else:
        members = clanbattle_info[group_id].members
    if not (data := await pcr_sqla.get_day_rcords(int(time.time()), ev.group_id)):
        await bot.send(ev, "数据库为空，请确保开启出刀监控")
        return
    await bot.send(ev, cuidao(await day_report(data, members)))


@sv.on_fullmatch("会战KPI", "会战kpi")
async def get_kpi(bot: HoshinoBot, ev: CQEvent):
    if not (data := await pcr_sqla.get_all_records(ev.group_id)):
        await bot.send(ev, "数据库为空，请确保开启出刀监控")
        return
    img = await get_kpireport(kpi_report(data, await pcr_sqla.get_kpis(ev.group_id)))
    await bot.send(ev, img)


@sv.on_prefix("kpi调整")
@check_priv_adimin(False)
async def correct_kpi(bot: HoshinoBot, ev: CQEvent, qq_id: int):
    try:
        info = ev.message.extract_plain_text().strip().split()
        await pcr_sqla.add_kpi_special(
            ClanBattleKPI(group_id=ev.group_id, pcrid=int(info[0]), bouns=int(info[1]))
        )
        await bot.send(ev, "设置成功")
    except Exception:
        await bot.send(ev, "设置失败，一定是你输入了奇怪的东西，爬爬")


@sv.on_fullmatch("清空kpi", "清空KPI")
async def clean_kpi(bot: HoshinoBot, ev: CQEvent):
    await pcr_sqla.delete_kpi(ev.group_id)
    await bot.send(ev, "清空成功")


@sv.on_prefix("删除kpi", "删除KPI")
async def del_kpi(bot: HoshinoBot, ev: CQEvent):
    """删除本群某个 pcrid 的 KPI 记录。

    必须带上 pcrid —— 以前直接 `int(参数)`，不带参数时是 `int("")`，抛 ValueError 被
    nonebot 吞掉，用户什么提示都收不到（和【退出公会】原来那个 bug 同型）。要清空本群
    全部 KPI 用【清空kpi】。
    """
    arg = ev.message.extract_plain_text().strip()
    if not arg.isdigit():
        await bot.send(ev, "请跟上要删除的 pcrid，示例：【删除kpi 123456789】；清空全部用【清空kpi】")
        return
    if await pcr_sqla.delete_kpi(ev.group_id, int(arg)):
        await bot.send(ev, "删除成功")
    else:
        await bot.send(ev, f"本群没有 pcrid 为 {int(arg)} 的 KPI 记录")


@nonebot.on_startup
async def start_loop_handle():
    clanbattle_pool.init()


@sv.scheduled_job("cron", hour="1")
async def refresh_boss_info():
    try:
        await clan_boss_info.update_boss()
    except Exception as e:
        logger.warning(f"更新boss数据异常：{e}")


@sv.scheduled_job("cron", hour="5")
async def morning_rank_push():
    """每天 5:00 查一次正在监控的公会排名，发群通知并更新 web 端。

    只在会战期间播报：休赛期直接跳过，避免把上一届的残留排名天天推一遍。
    """
    from ..util.tools import anywhere_send

    for group_id, clan_info in clanbattle_info.items():
        if not clan_info.client or clan_info.rank == 0:
            continue
        try:
            if not await clan_info.in_clan_battle():
                logger.info(f"5点排名播报跳过 group={group_id}：当前不在会战期间")
                continue
            top = await clan_info.get_clanbattle_top()
            clan_info.rank = top.period_rank or 0
            clan_info.dao_update_time = int(time.time())  # 触发 SSE 推送 web 端
            if clan_info.rank:
                await anywhere_send(
                    f"每日排名播报：当前 {clan_info.rank} 位",
                    group_id,
                    clan_info.bot_id,
                )
                logger.info(f"5点排名播报 group={group_id} rank={clan_info.rank}")
        except Exception as e:
            logger.warning(f"5点排名播报 group={group_id} 失败: {e}")


@nonebot.on_startup
@sv.scheduled_job("cron", hour="8")
async def refresh_record():
    await pcr_sqla.refresh(RecordDao, 30)
