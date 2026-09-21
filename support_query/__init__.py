import json
import time
from pathlib import Path
import re
from typing import List, Tuple
from ..database.models import Account
from .create_img import generate_box_img, generate_self_support_img
from .deep_domain_img import (
    MemberDeepDomain,
    format_talent_progress,
    from_payload,
    generate_deep_domain_img,
    to_payload,
)
from .util import (
    get_clan_members_info_with_client,
    get_support_list,
    read_knight_exp_rank,
    save_support_units,
    save_player_units,
    search_target,
    export_library,
    str2mode,
    change_support_unit,
)
from ..util.tools import get_qid, name2id, load_config
from ..util.decorator import check_account_qqid
from ..clanbattle import clanbattle_info
from ..clanbattle.base import is_monitor_running
from ..database.dal import pcr_sqla
from ..basedata import TALENT, FilePath
from ..util.text2img import image_draw
from nonebot import logger
from hoshino import Service
from hoshino.util import pic2b64
from hoshino.typing import MessageSegment, CQEvent, HoshinoBot

help_text = """
【刷新box缓存】会顶号，请注意，机器人自动上号记录你的box
【box查询+角色名字】（@别人可以查别人，角色名输入【所有】则都查）
【公会box查询+角色名字】查询绑定公会的玩家的box，不支持输入所有（卡不死你）
【刷新助战缓存】会顶号，请注意，机器人自动上号记录公会助战
【精确助战+角色名字】（角色名输入【所有】则都查）
【上公会战支援 + 角色名字】换助战，可以at别人
【上地下城支援 + 角色名字】换助战，可以at别人
【上关卡支援 + 角色名字】换助战，可以at别人
【我的助战】 查看自己的助战 (需要刷新box缓存)
【公会深域查询】 查询公会成员的深域进度（图片输出，五个属性各一列）
出刀监控在跑时抓最新的，监控没开时读上次缓存（图片上标了数据时间）
【导出图书馆 + 目标rank + 角色名字】 将你的box导出到兰德索尔图书馆，并且进行目标rank规划。
rank为小数点，小数点后仅只支持03456。可以叠加中间空格隔开，示例，"导出图书馆 19.6 千爱瑠油腻华哥 18.0 小仓唯美美炸弹人"
""".strip()

sv = Service(
    name="精准助战",  # 功能名
    visible=True,  # 可见性
    enable_on_default=True,  # 默认启用
    help_=help_text,  # 帮助说明
)


@sv.on_fullmatch("查box帮助")
async def query_help(bot: HoshinoBot, ev: CQEvent):
    img = image_draw(help_text)
    await bot.send(ev, img)


@sv.on_prefix("精准助战", "精确助战")
async def query_clanbattle_support(bot: HoshinoBot, ev: CQEvent):
    name = ev.message.extract_plain_text().strip()
    ids, msg = name2id(name)
    if msg:
        await bot.send(ev, msg)
        return
    supports = await pcr_sqla.get_support_units(ev.group_id)
    units = search_target(ids, supports)
    if not units:
        await bot.send(ev, "没有找到该角色")
        return
    images = await generate_box_img(units)
    await bot.send(ev, MessageSegment.image(pic2b64(images)))


@sv.on_fullmatch("刷新助战缓存")
@check_account_qqid
async def create_support_cache(
    bot: HoshinoBot, ev: CQEvent, account: Account, qq_id: int
):
    support = await get_support_list("support_query", account)
    self_support = await get_support_list("self_query", account)
    self_unit_list = [
        unit_data
        for unit_data in self_support.unit_list
        if unit_data.id
        in [
            unit.unit_id
            for unit in self_support.dispatch_units
            if unit.position in [3, 4]
        ]
    ]
    if self_unit_list:
        unit_ex_equip_dict = {
            equip.serial_id: (equip.ex_equipment_id, equip.enhancement_pt)
            for equip in self_support.user_ex_equip
        }
        for unit in self_unit_list:
            for equip in unit.cb_ex_equip_slot:
                if equip.serial_id:
                    equip.ex_equipment_id, equip.enhancement_pt = (
                        unit_ex_equip_dict.get(equip.serial_id, (0, 0))
                    )

    if "server_error" in support:
        await bot.send(ev, "可能现在不是会战的时候或者网络异常")
        return
    await save_support_units(
        support.support_unit_list + self_unit_list,
        ev.group_id,
        self_support.user_info.user_name,
        self_support.user_info.viewer_id,
    )
    await bot.send(ev, "刷新成功")


@sv.on_prefix("box查询")
async def query_box(bot: HoshinoBot, ev: CQEvent):
    qq_id, _ = get_qid(ev)
    name = ev.message.extract_plain_text().strip()
    ids, msg = name2id(name)
    if msg:
        await bot.send(ev, msg)
        return
    supports = await pcr_sqla.get_player_units(qq_id)
    units = search_target(ids, supports)
    if not units:
        await bot.send(ev, "没有找到该角色")
        return
    images = await generate_box_img(units)
    await bot.send(ev, MessageSegment.image(pic2b64(images)))


@sv.on_prefix("我的助战")
async def query_support_box(bot: HoshinoBot, ev: CQEvent):
    if ev.message.extract_plain_text().strip():
        return
    qq_id, _ = get_qid(ev)
    supports = await pcr_sqla.get_player_support_units(qq_id)
    images = await generate_self_support_img(supports)
    await bot.send(ev, MessageSegment.image(pic2b64(images)))


@sv.on_rex(
    r"^(上|挂)(地下城|公会|公会战|会战|工会战|工会|露娜|露娜塔|关卡)支援 ?(\S+)$"
)
@check_account_qqid
async def change_player_support_unit(bot, ev, account: Account, qq_id: int):
    info: re.Match = ev["match"]
    mode = str2mode[info[2][:2]]
    ids, msg = name2id(info[3])
    if msg:
        await bot.send(ev, msg)
        return
    if len(ids) > 1:
        await bot.send(ev, "只能输入一个角色")
        return
    try:
        await bot.send(ev, await change_support_unit(account, ids[0], mode))
    except Exception as e:
        await bot.send(ev, f"更换失败{str(e)}")


@sv.on_fullmatch("刷新box缓存")
@check_account_qqid
async def create_self_cache(bot: HoshinoBot, ev: CQEvent, account: Account, qq_id: int):

    player_info = await get_support_list("self_query", account)
    await save_player_units(
        player_info.unit_list,
        player_info.user_chara_info,
        player_info.user_ex_equip,
        qq_id,
        player_info.user_info.user_name,
        player_info.user_info.viewer_id,
        friend_support_list=player_info.friend_support_units,
        support_list=player_info.dispatch_units,
    )
    await bot.send(ev, "刷新成功")


@sv.on_prefix("公会box查询")
async def query_clanbattle_box(bot: HoshinoBot, ev: CQEvent):
    clan_info = []
    name = ev.message.extract_plain_text().strip()
    if name == "所有":
        await bot.send(ev, "爬爬，你想累死我")
        return
    ids, msg = name2id(name)
    if msg:
        await bot.send(ev, msg)
        return
    members = await pcr_sqla.get_group_member(ev.group_id)
    for member in members:
        units = await pcr_sqla.get_player_units(member.user_id)
        clan_info += search_target(ids, units)
    if len(clan_info) == 0:
        await bot.send(ev, "没有找到该角色")
        return
    images = await generate_box_img(clan_info)
    result = pic2b64(images)
    await bot.send(ev, MessageSegment.image(result))


@sv.on_fullmatch("导出原始box")
async def export_box(bot: HoshinoBot, ev: CQEvent):
    qq_id, _ = get_qid(ev)
    supports = await pcr_sqla.get_player_units(qq_id)

    _path = str(FilePath.data.value / "temp" / f"box_{qq_id}.json")
    with open(_path, "w") as f:
        json.dump([support.dict() for support in supports], f)

    await bot.call_action(
        action="upload_group_file",
        group_id=ev.group_id,
        name=f"{qq_id}.json",
        file=_path,
    )
    await bot.send(ev, f"用户{qq_id}json已上传至群文件")


@sv.on_fullmatch("会战一键规划")
@check_account_qqid
async def recommend_clanbattle(
    bot: HoshinoBot, ev: CQEvent, account: Account, qq_id: int
):
    calculate_json = load_config(str(Path(__file__).parent / "clanbattle.json"))
    calculate_dict = {float(rank): calculate_json[rank] for rank in calculate_json}

    await bot.send(ev, "请耐心等候喵~")
    info = await export_library(calculate_dict, account)

    _path = str(FilePath.data.value / "temp" / f"recommend_clanbattle_{qq_id}.txt")
    with open(_path, "w") as f:
        f.write(info)

    await bot.call_action(
        action="upload_group_file",
        group_id=ev.group_id,
        name=f"recommend_clanbattle_{qq_id}.txt",
        file=_path,
    )
    await bot.send(ev, f"用户{qq_id}文件已上传至群文件")


@sv.on_fullmatch("竞技场一键规划")
@check_account_qqid
async def recommend_jjc(bot: HoshinoBot, ev: CQEvent, account: Account, qq_id: int):
    calculate_json = load_config(str(Path(__file__).parent / "jjc.json"))
    calculate_dict = {float(rank): calculate_json[rank] for rank in calculate_json}

    await bot.send(ev, "请耐心等候喵~")
    info = await export_library(calculate_dict, account)

    _path = str(FilePath.data.value / "temp" / f"recommend_jjc_{qq_id}.txt")
    with open(_path, "w") as f:
        f.write(info)
    await bot.call_action(
        action="upload_group_file",
        group_id=ev.group_id,
        name=f"recommend_jjc_{qq_id}.txt",
        file=_path,
    )
    await bot.send(ev, f"用户{qq_id}文件已上传至群文件")


@sv.on_prefix("导出图书馆")
@check_account_qqid
async def box2library(bot: HoshinoBot, ev: CQEvent, account: Account, qq_id: int):
    calculate = ev.message.extract_plain_text().strip().split()

    try:
        if len(calculate) % 2 != 0:
            raise ValueError
        calculate_dict = {
            float(calculate[i]): calculate[i + 1] for i in range(0, len(calculate), 2)
        }
    except ValueError:
        await bot.send(ev, "格式错误，示例【导出图书馆 21.0 千爱瑠雪菲 19.6 油腻】")
        return

    for rank in calculate_dict:
        ids, msg = name2id(calculate_dict[rank])
        if 1701 in ids or 1702 in ids:
            await bot.send(ev, "环奈应该优先直接拉满，规划个什么。把环奈拉满了再来找我")
            return
        if msg:
            await bot.send(ev, msg)
            return

        calculate_dict[rank] = ids
    await bot.send(ev, "请耐心等候喵~")
    info = await export_library(calculate_dict, account)

    _path = str(FilePath.data.value / "temp" / f"library_{qq_id}.txt")
    with open(_path, "w") as f:
        f.write(info)
    await bot.call_action(
        action="upload_group_file",
        group_id=ev.group_id,
        name=f"library_{qq_id}.txt",
        file=_path,
    )
    await bot.send(ev, f"用户{qq_id}文件已上传至群文件")


def _deep_domain_progress_text(progress: dict) -> str:
    """文字降级用的进度串：五个属性都列出来，没打过的写「未通关」"""
    parts = []
    for element in TALENT:
        value = progress.get(element)
        parts.append(f"{element}: " + ("未通关" if value is None else "%d-%d" % value))
    return "/".join(parts)


DEEP_DOMAIN_NO_CACHE = (
    "本群还没有公会深域缓存：请先在群里【开启出刀监控】，"
    "等监控跑起来之后再发一次【公会深域查询】。"
    "之后即使监控停了，也能查到这份缓存（图片上会标出数据时间）"
)
"""既没开监控、也没有缓存时的提示。

这种情况**绝不能**去登录游戏侧抓数据：账号很可能正被群友自己登录着，
`login.query()` 里的 `check_client` 一失败就会重新 `client.login()`，把人顶下线。
"""


async def _read_deep_domain_cache(
    group_id: int,
) -> Tuple[str, List[MemberDeepDomain], int]:
    """读本群的深域缓存，返回 (公会名, 成员列表, 抓取时间)。

    读不到 / 读坏了都返回空列表 + 0，由调用方决定怎么提示 —— 缓存只是「监控没开
    时的降级来源」，不能让它把指令打崩。
    """
    if not group_id:
        return "", [], 0
    try:
        cached = await pcr_sqla.get_deep_domain_cache(group_id)
    except Exception as e:
        logger.warning(f"公会深域缓存读取失败 group={group_id}：{e!r}")
        return "", [], 0
    if cached is None:
        return "", [], 0
    try:
        clan_name, members = from_payload(cached.payload)
    except Exception as e:
        logger.warning(f"公会深域缓存解析失败 group={group_id}：{e!r}")
        return "", [], 0
    return clan_name, members, int(cached.updated_at or 0)


async def _fetch_deep_domain(clan_info) -> Tuple[str, List[MemberDeepDomain]]:
    """用出刀监控**已经登录好**的 client 抓一次公会深域进度。

    这里刻意只吃 `clan_info.client`、不走 `login.query()`：监控的 client 已经登录着，
    复用不会触发任何登录；自己重新登录才有顶号风险。
    """
    clan_name, members = await get_clan_members_info_with_client(clan_info.client)

    deep_domain_members = []
    for member in members:
        quest_info = member.quest_info
        talent_quests = (
            (getattr(quest_info, "talent_quest", None) or []) if quest_info else []
        )
        progress = {}
        for quest in talent_quests:
            # talent_id 是 1-based；越界就跳过，别让一个脏数据把整张图带崩
            if not 1 <= quest.talent_id <= len(TALENT):
                continue
            progress[TALENT[quest.talent_id - 1]] = format_talent_progress(
                quest.clear_count
            )
        deep_domain_members.append(
            MemberDeepDomain(
                name=member.user_info.user_name,
                knight_rank=read_knight_exp_rank(
                    member.user_info.princess_knight_rank_total_exp
                ),
                progress=progress,
            )
        )
    return clan_name, deep_domain_members


@sv.on_fullmatch("公会深域查询")
@check_account_qqid
async def query_deep_domain(bot: HoshinoBot, ev: CQEvent, account: Account, qq_id: int):
    """公会深域查询：监控在跑就抓最新并落缓存；监控没开就只读缓存，一次游戏接口都不打。

    为什么要这么分：查一次深域要给公会里每个人打一次 profile_get（30 人 = 30 次
    请求），而登录游戏侧是有代价的 —— 监控没在跑的时候账号很可能正被群友自己
    登录着，`login.query()` 里 `check_client` 一失败就会重新登录把人**顶下线**。
    所以只在「监控的 client 已经登录着」时才去抓。
    """
    group_id = int(getattr(ev, "group_id", 0) or 0)
    if not group_id:
        await bot.send(ev, "请在开启了出刀监控的群里使用【公会深域查询】")
        return

    clan_info = clanbattle_info.get(group_id)
    updated_at = 0
    footer_note = ""

    if is_monitor_running(clan_info):
        # 监控在跑：client 已经登录好了，直接抓最新的一份并落缓存
        try:
            clan_name, deep_domain_members = await _fetch_deep_domain(clan_info)
        except Exception as e:
            logger.warning(f"公会深域抓取失败 group={group_id}：{e!r}")
            clan_name, deep_domain_members, updated_at = await _read_deep_domain_cache(
                group_id
            )
            if not deep_domain_members:
                await bot.send(ev, "公会深域查询失败，请稍后再试")
                return
            footer_note = "抓取失败，退回上一次缓存"
        else:
            updated_at = int(time.time())
            try:
                await pcr_sqla.set_deep_domain_cache(
                    group_id,
                    to_payload(deep_domain_members, clan_name),
                    # 记下游戏内公会 ID：这个群以后换公会时，开启监控那一刻会拿它
                    # 比对，对不上就把这行作废（读取路径上没法判断，见 DAL 的说明）
                    clan_id=int(getattr(clan_info, "clan_id", 0) or 0),
                )
            except Exception as e:
                # 写缓存失败不影响本次结果，只是监控停了以后会读不到
                logger.warning(f"公会深域缓存写入失败 group={group_id}：{e!r}")
    else:
        clan_name, deep_domain_members, updated_at = await _read_deep_domain_cache(
            group_id
        )
        if not deep_domain_members:
            await bot.send(ev, DEEP_DOMAIN_NO_CACHE)
            return
        footer_note = "出刀监控未运行，以下为缓存数据"

    # 优先图片输出，生成失败时退回文字（同【查档线】的做法）
    try:
        await bot.send(
            ev,
            generate_deep_domain_img(
                deep_domain_members,
                clan_name=clan_name,
                generated_at=updated_at or None,
                footer_note=footer_note,
            ),
        )
        return
    except Exception as e:
        logger.warning(f"深域进度图片生成失败，改用文字输出：{e}")

    lines = ["公会成员深域进度："]
    if updated_at:
        lines.append(
            "数据时间 " + time.strftime("%m-%d %H:%M", time.localtime(updated_at))
        )
    if footer_note:
        lines.append(f"（{footer_note}）")
    for member in deep_domain_members:
        lines.append(
            f"{member.name}：\n"
            f"公主骑士等级{member.knight_rank}\n"
            f"深域进度：{_deep_domain_progress_text(member.progress)}"
        )
    await bot.send(ev, "\n\n".join(lines))
