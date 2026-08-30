import json
from pathlib import Path
import re
from ..database.models import Account
from .create_img import generate_box_img, generate_self_support_img
from .util import (
    get_clan_members_info,
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
from ..database.dal import pcr_sqla
from ..basedata import TALENT, FilePath
from ..util.text2img import image_draw
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
【公会深域查询】 查询公会成员的深域进度
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


@sv.on_fullmatch("公会深域查询")
@check_account_qqid
async def query_deep_domain(bot: HoshinoBot, ev: CQEvent, account: Account, qq_id: int):
    members = await get_clan_members_info(account)
    member_infos = []
    for member in members:
        # 构建深域进度信息
        talent_progress = []
        for quest in member.quest_info.talent_quest:
            stage = str((quest.clear_count - 1) // 10 + 1)
            level = (quest.clear_count % 10) or 10
            talent_progress.append(f"{TALENT[quest.talent_id-1]}: {stage}-{level}")

        # 构建成员信息
        member_info = (
            f"{member.user_info.user_name}：\n"
            f"公主骑士等级{read_knight_exp_rank(member.user_info.princess_knight_rank_total_exp)}\n"
            f"深域进度：{'/'.join(talent_progress)}"
        )
        member_infos.append(member_info)

    msg = "公会成员深域进度：\n" + "\n\n".join(member_infos)
    await bot.send(ev, msg)
