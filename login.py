import contextlib
from re import finditer
from typing import Dict, Tuple
import httpx
import traceback
from hoshino import Service
from hoshino.typing import HoshinoBot, CQEvent
from .client import (
    check_client,
    decryptxml,
    decrypt_access_key,
    pcrclient,
    tw_pcrclient,
    BaseClient,
    get_access_key,
)
from .database.models import Account, RefreshAccount
from .basedata import Platform, FilePath
from nonebot import NoticeSession, get_bot, on_command, on_notice, logger, on_startup
from .database.dal import pcr_sqla
from .util.tools import load_config, write_config
from .errorclass import NeedRefreshError, UnknowError

sv_help = """
（加好友私聊）
【绑定账号+账号+密码】加号为空格 
【渠绑定账号+login_id+token】加号为空格
【台绑定账号+short_udid+udid_viewer_id】加号为空格
login_id和token群里有提取器
short_udid、udid和viewer_id也有提取器
"""

sv = Service("你只需要好好出刀", help_=sv_help, visible=True)

run_group: Dict[int, int] = {}
client_cache: Dict[Tuple[int, int], BaseClient] = {}


async def query(account: Account, is_force=False):
    player = (account.viewer_id, account.platform)
    if player in client_cache and not is_force:
        client = client_cache[player]
        if await check_client(client):
            return client
    if account.platform != Platform.tw_id.value:
        client = pcrclient(account.account, account.password, account.platform)
    else:
        client = tw_pcrclient(
            account.account,
            account.password,
            account.viewer_id,
        )
    try:
        await client.login()
    except NeedRefreshError:
        logger.warning(f"{account.viewer_id}的access_key过期，重新获取")
        bili_account = await pcr_sqla.query_refresh(account.refresh)
        if bili_account:
            uid, access_key = await get_access_key(
                bili_account.account, bili_account.password, account.user_id
            )
            account.account = str(uid)
            account.password = access_key
            await pcr_sqla.add_account(account.user_id, account.dict(exclude_none=True))
            client = pcrclient(account.account, account.password, account.platform)
            await client.login()
    if await check_client(client):
        client_cache[player] = client
        return client
    raise UnknowError("登录失败，请重试，很可能是网络问题")


@on_startup
async def init_database():
    await pcr_sqla.create_all()


@sv.on_fullmatch("绑定账号帮助", only_to_me=False)
async def send_jjchelp(bot: HoshinoBot, ev: CQEvent):
    await bot.send(ev, sv_help)
    await bot.send_private_msg(user_id=ev.user_id, message=sv_help)


@sv.on_fullmatch("缓存运行群")
async def resatrt_remind(bot: HoshinoBot, ev: CQEvent):
    write_config(FilePath.run_group.value, run_group)
    await bot.send(ev, "成功")


@sv.on_fullmatch("提醒掉线")
async def offline_remind(bot: HoshinoBot, ev: CQEvent):
    bot = get_bot()
    for gid in (group_dict := load_config(FilePath.run_group.value)):
        with contextlib.suppress(Exception):
            await bot.send_group_msg(
                self_id=group_dict[gid],
                group_id=gid,
                message="遭遇神秘的桥本环奈偷袭，请检查监控",
            )
    write_config(FilePath.run_group.value, {})
    await bot.send(ev, "成功")


@on_command("绑定账号")
async def bind_support(session: NoticeSession):
    content = session.ctx.message.extract_plain_text().split()
    qq_id = session.ctx.user_id
    if len(content) != 3:
        await session.send(sv_help)
        return

    bili_account = RefreshAccount(account=content[1], password=content[2])
    try:
        uid, access_key = await get_access_key(
            bili_account.account, bili_account.password, qq_id
        )
        account = Account(
            user_id=qq_id,
            platform=Platform.b_id.value,
            account=uid,
            password=access_key,
            refresh=bili_account.account,
        )
        client = await query(account, True)
        if load_index := await check_client(client):
            account.viewer_id = load_index.user_info.viewer_id
            account.name = load_index.user_info.user_name
            await pcr_sqla.add_account(qq_id, account.dict(exclude_none=True))
            await pcr_sqla.add_refresh(bili_account)
            await session.send("绑定成功")
        else:
            await session.send("绑定失败，请检查你的账号密码并重试")
    except Exception as e:
        logger.error(traceback.format_exc())
        await session.send(f"绑定失败{str(e)}")


@on_command("渠绑定账号")
async def bind_support_qu(session: NoticeSession):
    content = session.ctx.message.extract_plain_text().split()
    qq_id = session.ctx.user_id
    if len(content) == 3:
        password = content[2]
    elif len(content) == 4:
        password = decrypt_access_key(f"{content[2]} {content[3]}")
    else:
        await session.send(sv_help)
        return
    try:
        account = Account(
            user_id=qq_id,
            platform=Platform.qu_id.value,
            account=content[1],
            password=password,
        )
        client = await query(account, True)
        if load_index := await check_client(client):
            account.viewer_id = load_index.user_info.viewer_id
            account.name = load_index.user_info.user_name
            await pcr_sqla.add_account(qq_id, account.dict(exclude_none=True))
            await session.send("绑定成功")
        else:
            await session.send("绑定失败，请检查你的获取的数据是否完整并重试")
    except Exception as e:
        logger.error(traceback.format_exc())
        await session.send(f"绑定失败{str(e)}")


@on_command("台绑定账号")
async def bind_support_tw(session: NoticeSession):
    content = session.ctx.message.extract_plain_text().split()
    qq_id = session.ctx.user_id
    if len(content) >= 4:
        short_udid = content[1]
        udid = content[2]
        view_id = int(content[3])
    try:
        account = Account(
            user_id=qq_id,
            platform=Platform.tw_id.value,
            viewer_id=view_id,
            account=short_udid,
            password=udid,
        )
        client = await query(account, True)
        if load_index := await check_client(client):
            account.name = load_index.user_info.user_name
            await pcr_sqla.add_account(qq_id, account.dict(exclude_none=True))
            await session.send("绑定成功")
        else:
            await session.send("绑定失败，请检查你的获取的数据是否完整并重试")
    except Exception as e:
        logger.error(traceback.format_exc())
        await session.send(f"绑定失败{str(e)}")


@on_notice("offline_file")
async def qu_bind(session: NoticeSession):
    file = session.event.file
    # 防止贱民传过大文件搞事情
    if file["size"] // 1024 // 1024 < 1 and (
        "v2.playerprefs" in file["name"] or "base.track" in file["name"]
    ):
        qq_id = session.ctx.user_id
        async with httpx.AsyncClient() as AsyncClient:
            res = await AsyncClient.get(url=file["url"])
            temp_dict = {"user_id": qq_id}

        if "bilibili.priconne" in file["name"]:
            access_key, viewer_id = decryptxml(
                res.content.decode(), Platform.qu_id.value
            )
            temp_dict["password"] = access_key
            temp_dict["viewer_id"] = viewer_id
            temp_dict["platform"] = Platform.qu_id.value
        elif "base.track" in file["name"]:
            for re in finditer(
                r'<string name="(.*)">(\d{22})</string>', res.content.decode()
            ):
                temp_dict["account"] = re.groups()[1]
                temp_dict["platform"] = Platform.qu_id.value
                break
        else:
            account, password, viewer_id, _ = decryptxml(
                res.content.decode(), Platform.tw_id.value
            )
            temp_dict["account"] = account
            temp_dict["password"] = password
            temp_dict["viewer_id"] = viewer_id
            temp_dict["platform"] = Platform.tw_id.value

        await pcr_sqla.add_account(qq_id, temp_dict)
        await session.send("接受文件成功")

        client = await query((await pcr_sqla.query_account(qq_id))[0])
        if load_index := await check_client(client):
            await pcr_sqla.add_account(qq_id, {"name": load_index.user_info.user_name})
            await session.send("绑定成功")
