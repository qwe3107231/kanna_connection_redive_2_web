import random
import string
from hoshino import Service
from nonebot import NoticeSession, on_command, logger
from ..database.dal import pcr_sqla
from ..database.models import WebAccount
from ..setting import WebSetting
from .api import *

sv = Service(
    name="环奈网页端管理",  # 功能名
    visible=False,  # 可见性
    enable_on_default=True,  # 默认启用
)


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
        f"🌐 环奈连结 R · 网页端登录链接：\n{login_url}\n\n⚠️ 临时密码 7 天内有效，建议登录后自行修改。",
        ensure_private=True,
    )
