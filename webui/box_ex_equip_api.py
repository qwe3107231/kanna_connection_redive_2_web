"""普通 EX 装备换装的网页端接口（BOX 页 → 点角色头像 → 详情里的「普通 EX 槽」）。

和 `box_arena_api` 里那两组接口的分工：

- **读（列装备）**：`GET /{group_id}/box/ex_equip/options`
  纯读本地缓存（`PlayerExEquip`：背包清单 + 每件穿在谁身上），**一次游戏接口都不打**，
  和 BOX 页其它查询一样「看的时候绝不登录」。
- **写（真换）**：`POST /{group_id}/box/ex_equip/change`
  会 `login.query` 登录你的游戏账号（**顶号**）并真的改游戏里的普通 EX 槽，
  前端必须先弹确认 —— 和「我的助战 → 更换支援」是同一套规矩。

**会战 EX 一律不碰**：自动穿会战 EX（`support_query.util.equip_clan_battle_ex`）、
`cb_ex_equip_slot` 的展示、撤下会战 EX 这些都维持原样。这里只动 `ex_equip_slot`。

换装的判定与动作顺序全在 `support_query.util.change_normal_ex_equip`（含「从别人身上
拿装备时互换而不是把对方扒光」、会战冷却拦截），本文件只做参数校验、权限、并发闸门、
以及把结果转成响应模型。
"""

from fastapi import APIRouter, Depends, HTTPException
from nonebot import logger

from ..database.dal import pcr_sqla
from ..database.models import CookieCache
from ..setting import WebSetting
from .util import call_in_main_loop, verify_group_access
from .web_model import (
    ExEquipChangeForm,
    ExEquipChangeResult,
    ExEquipOptionsResult,
    ExEquipSlotChangeResult,
)

# 注意：这里**只**从 web_model 拿 ExEquipChangeResult（响应模型）；
# `support_query.util.ExEquipChangeResult` 是同名的 dataclass，别互相 import 混了。
from .box_arena_api import (  # noqa: E402  必须在上面之后
    _REFRESHING,
    _ex_equip_icon_url,
    _login_guard,
    _require_account,
)

router = APIRouter(prefix=WebSetting.api_base.value)


def _chara_name(chara_id: int) -> str:
    from hoshino.modules.priconne.chara import fromid

    try:
        return fromid(int(chara_id)).name
    except Exception:
        return str(chara_id)


@router.get("/{group_id}/box/ex_equip/options", response_model=ExEquipOptionsResult)
async def ex_equip_options(
    group_id: int,
    unit_id: int,
    slot: int,
    token: CookieCache = Depends(verify_group_access),
):
    """列出某个角色某个普通 EX 槽能换的装备（纯本地缓存，不登录、不顶号）。

    `unit_id` 是 4 位角色 ID（前端 BOX 条目里那个），`slot` 是 1~3。
    每个候选带：名称 / 类别 / 稀有度 / 星级 / **属性** / 图标，
    以及这份装备现在**空闲还是在谁身上**（同一件装备多把时会给 `copies` 让用户挑）。
    """
    if slot not in (1, 2, 3):
        return ExEquipOptionsResult(message="EX 槽位编号只能是 1~3")

    # 函数内 import：web 插件可能早于 support_query 插件加载（与 box_arena_api 一致）
    from ..support_query.util import build_ex_equip_options

    user_id = int(token.user_id)
    rows = await pcr_sqla.get_player_ex_equips(user_id)
    options = build_ex_equip_options(rows, int(unit_id), int(slot))
    if options is None:
        return ExEquipOptionsResult(
            message=f"找不到{_chara_name(unit_id)}的 EX 槽位数据（可能是新角色，或槽位表未更新）"
        )

    # 图标走 `/{group_id}/box/ex_equip_icon/{equipment_id}`（和会战 EX 共用一份缓存资源）
    for candidate in options["candidates"]:
        candidate["icon"] = _ex_equip_icon_url(candidate["equipment_id"], group_id)
    if options["current"]:
        options["current"]["icon"] = _ex_equip_icon_url(
            options["current"]["equipment_id"], group_id
        )

    message = ""
    if not rows:
        # 没有任何 EX 缓存 = 这个账号还没点过【刷新缓存】（或确实一件 EX 都没有）。
        # 不能直接显示「无可选装备」，那会被理解成「我真的没有这件装备」。
        message = (
            "还没有你的 EX 装备缓存，请先点右上角【刷新缓存】"
            "（会短暂顶号）后再来换装。"
        )
    elif not options["candidates"]:
        message = (
            f"你的 EX 装备里没有能装在「{options['category_name']}」槽上的"
            "（这一类的装备可能都正穿在会战槽上）。"
        )

    return ExEquipOptionsResult(
        ok=True,
        message=message,
        chara_name=_chara_name(int(unit_id)),
        **options,
    )


@router.post("/{group_id}/box/ex_equip/change", response_model=ExEquipChangeResult)
async def ex_equip_change(
    group_id: int,
    form: ExEquipChangeForm,
    token: CookieCache = Depends(verify_group_access),
):
    """把某个角色的**若干普通 EX 槽**一次换掉（`serial_id=0` = 卸下那个槽）。

    网页端弹窗里挑好 EX1/EX2/EX3 后一次提交，所以这里只登录一次游戏账号、
    只发一批 `unit/equip_ex` —— 不是一件一件换。

    ⚠️ **写操作 + 顶号**：会登录你自己绑定的游戏账号，正在游戏的你会被挤下线，
    并真的改游戏里的 EX 槽；目标装备在别人身上时会**互换**（把你这件换给对方）。
    """
    from ..support_query.util import change_normal_ex_equips

    user_id = int(token.user_id)
    account = await _require_account(user_id, group_id)
    if account is None:
        return ExEquipChangeResult(
            ok=False,
            message="还没有绑定游戏账号，请先在网页端仪表盘绑定，或在 QQ 私聊我发送【绑定账号帮助】",
        )

    changes = [(int(item.slot), int(item.serial_id or 0)) for item in form.changes]
    if not changes:
        return ExEquipChangeResult(ok=False, message="没有要更换的 EX 槽")

    # 和刷新缓存 / 更换支援共用同一把闸门：这些操作都会 `login.query()` 登同一个账号，
    # 撞在一起只会互相顶号。用户连点两下按钮不该触发两次登录。
    guards = {("ex_equip_change", user_id), _login_guard(user_id)}
    if guards & _REFRESHING:
        return ExEquipChangeResult(
            ok=False, message="正在操作中，请稍候…（同一时间只允许一次登录类操作）"
        )
    _REFRESHING.update(guards)
    try:
        res = await call_in_main_loop(
            change_normal_ex_equips(account, form.unit_id, changes)
        )
    except HTTPException as e:
        return ExEquipChangeResult(ok=False, message=f"更换失败：{e.detail}")
    except Exception as e:
        logger.warning(f"更换普通EX装备失败：{e!r}")
        return ExEquipChangeResult(ok=False, message=f"更换失败：{e}")
    finally:
        _REFRESHING.difference_update(guards)

    return ExEquipChangeResult(
        ok=res.ok,
        message=res.message,
        chara_id=res.chara_id,
        chara_name=res.chara_name,
        slots=[
            ExEquipSlotChangeResult(
                slot=item.slot,
                serial_id=item.serial_id,
                equipment_id=item.equipment_id,
                name=item.name,
                star=item.star,
                old_serial_id=item.old_serial_id,
                swapped_chara_id=item.swapped_chara_id,
                swapped_chara_name=item.swapped_chara_name,
            )
            for item in res.slots
        ],
    )
