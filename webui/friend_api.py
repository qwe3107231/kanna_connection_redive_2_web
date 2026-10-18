"""好友功能的网页端接口（BOX/助战页新增的「好友」页签）。

与 `box_arena_api` 里那两组接口的分工：

- **看列表**：`GET /{group_id}/friend/list` 纯读本地缓存表（`FriendCache` /
  `FriendCacheMeta`），一次游戏接口都不打 —— 和 BOX / 助战一样「看的时候绝不登录」。
- **刷新 / 加好友 / 删好友**：必须登录**当前登录用户自己绑定的游戏账号**
  （好友是个人数据，不能借竞技场监控那个 client —— 那可能是群监控人的号，
  好友列表不是同一个人），会**顶号**，前端点之前先弹确认。
- **好友详情**：`GET /{group_id}/friend/profile` 与竞技场「查 ID」返回结构完全一致
  （共用 `jjckiller.model.build_profile_data`）。优先借用正在运行的竞技场监控 client
  （不额外登录）；没有监控时退回登录当前用户自己的账号 —— `login.query` 有 client
  缓存，刚刷过好友列表时通常不会重新登录。

游戏接口与判定顺序照抄 autopcr 的【加好友】/【删好友】：
`friend/friend_list`、`friend/request`、`friend/remove`，上限 40 / 已是好友 / 不是好友。
"""

import time

from fastapi import APIRouter, Depends, HTTPException

from ..database.dal import pcr_sqla
from ..database.models import CookieCache, FriendCache
from ..setting import WebSetting
from .box_arena_api import (
    _REFRESHING,
    _avatar_star,
    _get_arena,
    _login_guard,
    _require_account,
)
from .util import call_in_main_loop, verify_group_access
from .web_model import (
    ArenaProfileResult,
    FriendActionForm,
    FriendListResult,
    FriendRequestsResult,
    FriendRow,
)

router = APIRouter(prefix=WebSetting.api_base.value)

# 游戏好友上限固定 40（autopcr 的 FRIEND_LIMIT 同值）
_FRIEND_LIMIT = 40


# ---- 缓存行 <-> 响应模型 ----


def _format_unit_id(unit) -> int:
    """代表角色 id -> 4 位角色 ID（头像接口吃 4 位）。

    与 `jjckiller.model.Arena.format_id` 同口径：游戏 unit_id 是 chara_id*100+1，
    大于 100000 时整除 100；拿不到 / 是 NPC 时回 1000（未知角色占位）。
    """
    try:
        uid = int(getattr(unit, "id", 0) or 0)
    except Exception:
        return 1000
    return uid // 100 if uid > 100000 else 1000


def _friend_avatar_url(group_id: int, unit_id: int, rarity: int) -> str:
    """好友头像地址。

    **刻意不带 rarity 参数**：用户明确要求「好友头像不能有星级」。只传 `star`
    档位决定用哪张底图（6 星角色用 6 星立绘，但底下不叠星星）。
    """
    star = _avatar_star(int(rarity or 0))
    return f"{WebSetting.api_base.value}/{group_id}/box/avatar/{int(unit_id)}?star={star}"


def _build_cache_rows(friends, user_id: int) -> list:
    """接口返回的 `FriendInfo` 列表 -> `FriendCache` 行（准备整表写库）。"""
    now = int(time.time())
    rows = []
    for friend in friends or []:
        viewer_id = int(getattr(friend, "viewer_id", 0) or 0)
        if viewer_id <= 0:
            continue
        fav = getattr(friend, "favorite_unit", None)
        rows.append(
            FriendCache(
                user_id=int(user_id),
                viewer_id=viewer_id,
                name=str(getattr(friend, "name", "") or ""),
                level=int(getattr(friend, "level", 0) or 0),
                total_power=int(getattr(friend, "total_power", 0) or 0),
                friend_num=int(getattr(friend, "friend_num", 0) or 0),
                last_login_time=int(getattr(friend, "last_login_time", 0) or 0),
                favorite_unit_id=_format_unit_id(fav),
                favorite_unit_rarity=(
                    int(getattr(fav, "unit_rarity", 0) or 0) if fav else 0
                ),
                update_time=now,
            )
        )
    return rows


def _to_friend_row(row: FriendCache, group_id: int) -> FriendRow:
    unit_id = int(row.favorite_unit_id or 1000)
    rarity = int(row.favorite_unit_rarity or 0)
    return FriendRow(
        viewer_id=int(row.viewer_id or 0),
        name=str(row.name or ""),
        level=int(row.level or 0),
        total_power=int(row.total_power or 0),
        friend_num=int(row.friend_num or 0),
        last_login_time=int(row.last_login_time or 0),
        avatar_unit_id=unit_id,
        avatar_rarity=rarity,
        avatar=_friend_avatar_url(group_id, unit_id, rarity),
    )


def _to_friend_row_from_info(friend, group_id: int) -> FriendRow:
    """游戏接口返回的 `FriendInfo` -> 前端好友卡片行（不落库，给申请列表用）"""
    fav = getattr(friend, "favorite_unit", None)
    unit_id = _format_unit_id(fav)
    rarity = int(getattr(fav, "unit_rarity", 0) or 0) if fav else 0
    return FriendRow(
        viewer_id=int(getattr(friend, "viewer_id", 0) or 0),
        name=str(getattr(friend, "name", "") or ""),
        level=int(getattr(friend, "level", 0) or 0),
        total_power=int(getattr(friend, "total_power", 0) or 0),
        friend_num=int(getattr(friend, "friend_num", 0) or 0),
        last_login_time=int(getattr(friend, "last_login_time", 0) or 0),
        avatar_unit_id=unit_id,
        avatar_rarity=rarity,
        avatar=_friend_avatar_url(group_id, unit_id, rarity),
    )


def _requests_result(pending, requested, group_id: int, message: str = "", ok: bool = True):
    return FriendRequestsResult(
        ok=ok,
        message=message,
        pending=[_to_friend_row_from_info(f, group_id) for f in (pending or [])],
        requested=[_to_friend_row_from_info(f, group_id) for f in (requested or [])],
    )


async def _list_result(user_id: int, group_id: int) -> FriendListResult:
    """读库组装好友列表。从没刷过缓存时 ok=False + 提示去点【刷新好友】。"""
    rows = await pcr_sqla.get_friends(user_id)
    updated_at = await pcr_sqla.get_friend_update_time(user_id)
    friends = [_to_friend_row(row, group_id) for row in rows]
    if not updated_at:
        return FriendListResult(
            ok=False,
            message="还没有好友缓存，点上方【刷新好友】读取（会临时登录你的游戏账号，可能顶号）",
            count=0,
            limit=_FRIEND_LIMIT,
            updated_at=0,
            friends=[],
        )
    return FriendListResult(
        ok=True,
        count=len(friends),
        limit=_FRIEND_LIMIT,
        updated_at=updated_at,
        friends=friends,
    )


# ---- 登录游戏账号的操作（都在主循环里跑）----
# 这几个函数收 `account`（当前登录用户自己绑定的号），内部走 `login.query`：
# 命中 client 缓存时只做一次 load_index 校验、不重新登录；没命中才会顶号。


async def _fetch_friend_list(account, user_id: int) -> list:
    """登录一次，拉好友列表并覆盖写缓存，返回写入的行。"""
    from ..login import query

    client = await query(account)
    response = await client.friend_list()
    rows = _build_cache_rows(response.friend_list, user_id)
    await pcr_sqla.refresh_friends(rows, user_id, int(time.time()))
    return rows


async def _add_friend(account, user_id: int, target_viewer_id: int) -> tuple:
    """发送好友请求。返回 (ok, 提示文字)；失败时也会顺手刷新缓存。"""
    from ..login import query

    client = await query(account)
    response = await client.friend_list()
    friends = response.friend_list or []
    # 先把刚拿到的列表写库：不管后面成功失败，缓存都是新的
    rows = _build_cache_rows(friends, user_id)
    await pcr_sqla.refresh_friends(rows, user_id, int(time.time()))

    me = int(account.viewer_id or 0)
    if me and target_viewer_id == me:
        return False, "不能加自己为好友"
    for friend in friends:
        if int(getattr(friend, "viewer_id", 0) or 0) == target_viewer_id:
            name = str(getattr(friend, "name", "") or "")
            return False, f"{name}（ID {target_viewer_id}）已经是你的好友"
    if len(friends) >= _FRIEND_LIMIT:
        return False, (
            f"好友数量已达上限（{len(friends)}/{_FRIEND_LIMIT}），"
            "先解除几个好友再添加吧"
        )

    # 先确认这个 ID 真的存在（顺便拿名字拼提示），不存在时游戏会直接报错、看不出原因
    profile = await client.profile_get(target_viewer_id)
    if profile.user_info is None:
        return False, f"没有查到这个玩家（ID {target_viewer_id}）"
    target_name = str(profile.user_info.user_name or "")

    await client.friend_request(target_viewer_id)
    return True, (
        f"已向 {target_name}（ID {target_viewer_id}）发送好友请求，"
        "对方同意后才会出现在好友列表里"
    )


async def _remove_friend(account, user_id: int, target_viewer_id: int) -> tuple:
    """解除好友关系。返回 (ok, 提示文字)；成功后会重拉列表保证缓存准确。"""
    from ..login import query

    client = await query(account)
    response = await client.friend_list()
    friends = response.friend_list or []
    target = next(
        (
            friend
            for friend in friends
            if int(getattr(friend, "viewer_id", 0) or 0) == target_viewer_id
        ),
        None,
    )
    if target is None:
        rows = _build_cache_rows(friends, user_id)
        await pcr_sqla.refresh_friends(rows, user_id, int(time.time()))
        return False, f"玩家（ID {target_viewer_id}）不是你的好友"

    target_name = str(getattr(target, "name", "") or "")
    await client.friend_remove(target_viewer_id)

    # 删完重拉一次：好友列表以游戏侧为准，别自己在前端过滤（可能还有对方同时删你等情况）
    response = await client.friend_list()
    rows = _build_cache_rows(response.friend_list, user_id)
    await pcr_sqla.refresh_friends(rows, user_id, int(time.time()))
    return True, f"已解除好友 {target_name}（ID {target_viewer_id}）"


def _busy_result() -> FriendListResult:
    return FriendListResult(
        ok=False,
        message="正在登录游戏账号（刷新缓存 / 换装 / 好友操作），请稍候再试",
    )


def _busy_requests() -> FriendRequestsResult:
    return FriendRequestsResult(
        ok=False,
        message="正在登录游戏账号（刷新缓存 / 换装 / 好友操作），请稍候再试",
    )


# ---- 好友申请（待审核 / 申请中）----
# 这两份名单是实时数据，游戏接口不提供缓存，所以每次查看 / 操作都登录一次
# （同一账号的 client 有缓存，通常只做一次 load_index 校验、不会反复顶号）。


async def _fetch_friend_requests(account) -> tuple:
    """拉「待审核列表 + 申请中的名单」，返回两份原始 FriendInfo 列表。"""
    from ..login import query

    client = await query(account)
    pending = (await client.friend_pending_list()).pending_list or []
    requested = (await client.friend_request_list()).request_list or []
    return pending, requested


async def _accept_friend_request(account, user_id: int, target_viewer_id: int) -> tuple:
    """同意好友申请；成功后顺手刷新好友列表缓存。返回 (ok, 提示, 待审核, 申请中)。"""
    from ..login import query

    client = await query(account)
    pending = (await client.friend_pending_list()).pending_list or []
    target = next(
        (
            friend
            for friend in pending
            if int(getattr(friend, "viewer_id", 0) or 0) == target_viewer_id
        ),
        None,
    )
    if target is None:
        requested = (await client.friend_request_list()).request_list or []
        return (
            False,
            f"待审核列表里没有 ID {target_viewer_id} 的申请（可能已被处理）",
            pending,
            requested,
        )

    target_name = str(getattr(target, "name", "") or "")
    await client.friend_accept(target_viewer_id)

    # 同意后好友列表变了：顺手刷新本地缓存，回到好友页签不用再点一次刷新
    friend_response = await client.friend_list()
    rows = _build_cache_rows(friend_response.friend_list, user_id)
    await pcr_sqla.refresh_friends(rows, user_id, int(time.time()))

    pending = (await client.friend_pending_list()).pending_list or []
    requested = (await client.friend_request_list()).request_list or []
    return (
        True,
        f"已同意 {target_name}（ID {target_viewer_id}）的好友申请",
        pending,
        requested,
    )


async def _reject_friend_request(account, target_viewer_id: int) -> tuple:
    """拒绝好友申请。返回 (ok, 提示, 待审核, 申请中)。"""
    from ..login import query

    client = await query(account)
    pending = (await client.friend_pending_list()).pending_list or []
    target = next(
        (
            friend
            for friend in pending
            if int(getattr(friend, "viewer_id", 0) or 0) == target_viewer_id
        ),
        None,
    )
    if target is None:
        requested = (await client.friend_request_list()).request_list or []
        return (
            False,
            f"待审核列表里没有 ID {target_viewer_id} 的申请（可能已被处理）",
            pending,
            requested,
        )

    target_name = str(getattr(target, "name", "") or "")
    await client.friend_reject(target_viewer_id)
    pending = (await client.friend_pending_list()).pending_list or []
    requested = (await client.friend_request_list()).request_list or []
    return (
        True,
        f"已拒绝 {target_name}（ID {target_viewer_id}）的好友申请",
        pending,
        requested,
    )


async def _cancel_friend_request(account, target_viewer_id: int) -> tuple:
    """撤回我发出的好友申请。返回 (ok, 提示, 待审核, 申请中)。"""
    from ..login import query

    client = await query(account)
    requested = (await client.friend_request_list()).request_list or []
    target = next(
        (
            friend
            for friend in requested
            if int(getattr(friend, "viewer_id", 0) or 0) == target_viewer_id
        ),
        None,
    )
    if target is None:
        pending = (await client.friend_pending_list()).pending_list or []
        return (
            False,
            f"申请中的名单里没有 ID {target_viewer_id}（可能已被处理）",
            pending,
            requested,
        )

    target_name = str(getattr(target, "name", "") or "")
    await client.friend_cancel(target_viewer_id)
    pending = (await client.friend_pending_list()).pending_list or []
    requested = (await client.friend_request_list()).request_list or []
    return (
        True,
        f"已撤回发给 {target_name}（ID {target_viewer_id}）的好友申请",
        pending,
        requested,
    )


# ============================ 接口 ============================


@router.get("/{group_id}/friend/list", response_model=FriendListResult)
async def friend_list(
    group_id: int, token: CookieCache = Depends(verify_group_access)
):
    """好友列表（纯读本地缓存，不登录、不顶号）"""
    return await _list_result(int(token.user_id), group_id)


@router.post("/{group_id}/friend/refresh", response_model=FriendListResult)
async def friend_refresh(
    group_id: int, token: CookieCache = Depends(verify_group_access)
):
    """刷新好友列表：登录当前用户绑定的游戏账号（**顶号**），重新读取并写缓存。"""
    user_id = int(token.user_id)
    account = await _require_account(user_id, group_id)
    if account is None:
        return FriendListResult(
            message="还没有绑定游戏账号，请先在网页端仪表盘绑定，"
            "或在 QQ 私聊我发送【绑定账号帮助】"
        )

    guards = {("friend_refresh", user_id), _login_guard(user_id)}
    if guards & _REFRESHING:
        return _busy_result()
    _REFRESHING.update(guards)
    try:
        rows = await call_in_main_loop(_fetch_friend_list(account, user_id))
    except HTTPException as e:
        return FriendListResult(message=f"刷新好友列表失败：{e.detail}")
    except Exception as e:
        return FriendListResult(message=f"刷新好友列表失败：{e}")
    finally:
        _REFRESHING.difference_update(guards)

    result = await _list_result(user_id, group_id)
    if result.ok:
        result.message = (
            f"好友列表已更新：{result.count}/{_FRIEND_LIMIT} 人"
            if result.count
            else "好友列表已更新：目前还没有好友"
        )
    else:
        # 理论上不会走到这里（刚写过 meta），兜底也当成成功，别让用户白顶一次号
        result.ok = True
        result.message = f"好友列表已更新：{len(rows)} 位好友"
    return result


@router.post("/{group_id}/friend/add", response_model=FriendListResult)
async def friend_add(
    group_id: int,
    form: FriendActionForm,
    token: CookieCache = Depends(verify_group_access),
):
    """添加好友：向指定玩家 ID 发送好友请求（**会顶号**，前端先确认）。

    游戏流程是「发请求 → 对方同意」，所以成功后好友列表不会立刻多出这个人，
    返回的 `friends` 是当前（最新的）好友列表，提示语里会说明这一点。
    """
    target = int(form.viewer_id or 0)
    if target <= 0:
        return FriendListResult(message="请输入有效的玩家 ID（纯数字）")

    user_id = int(token.user_id)
    account = await _require_account(user_id, group_id)
    if account is None:
        return FriendListResult(
            message="还没有绑定游戏账号，请先在网页端仪表盘绑定，"
            "或在 QQ 私聊我发送【绑定账号帮助】"
        )

    guards = {("friend_action", user_id), _login_guard(user_id)}
    if guards & _REFRESHING:
        return _busy_result()
    _REFRESHING.update(guards)
    try:
        ok, message = await call_in_main_loop(
            _add_friend(account, user_id, target)
        )
    except HTTPException as e:
        return FriendListResult(message=f"加好友失败：{e.detail}")
    except Exception as e:
        return FriendListResult(message=f"加好友失败：{e}")
    finally:
        _REFRESHING.difference_update(guards)

    result = await _list_result(user_id, group_id)
    result.ok = bool(ok)
    result.message = message
    return result


@router.post("/{group_id}/friend/remove", response_model=FriendListResult)
async def friend_remove(
    group_id: int,
    form: FriendActionForm,
    token: CookieCache = Depends(verify_group_access),
):
    """解除好友（**会顶号**，前端先确认）。成功返回删除后的最新好友列表。"""
    target = int(form.viewer_id or 0)
    if target <= 0:
        return FriendListResult(message="请输入有效的玩家 ID（纯数字）")

    user_id = int(token.user_id)
    account = await _require_account(user_id, group_id)
    if account is None:
        return FriendListResult(
            message="还没有绑定游戏账号，请先在网页端仪表盘绑定，"
            "或在 QQ 私聊我发送【绑定账号帮助】"
        )

    guards = {("friend_action", user_id), _login_guard(user_id)}
    if guards & _REFRESHING:
        return _busy_result()
    _REFRESHING.update(guards)
    try:
        ok, message = await call_in_main_loop(
            _remove_friend(account, user_id, target)
        )
    except HTTPException as e:
        return FriendListResult(message=f"解除好友失败：{e.detail}")
    except Exception as e:
        return FriendListResult(message=f"解除好友失败：{e}")
    finally:
        _REFRESHING.difference_update(guards)

    result = await _list_result(user_id, group_id)
    result.ok = bool(ok)
    result.message = message
    return result


@router.get("/{group_id}/friend/requests", response_model=FriendRequestsResult)
async def friend_requests(
    group_id: int, token: CookieCache = Depends(verify_group_access)
):
    """好友申请列表：待审核 + 申请中（**会登录游戏账号**，前端先确认顶号）。

    游戏接口里这两份名单是实时的、不落本地缓存，所以每次查看都要现拉；
    和好友列表的「读缓存不登录」是两套口径。
    """
    user_id = int(token.user_id)
    account = await _require_account(user_id, group_id)
    if account is None:
        return FriendRequestsResult(
            message="还没有绑定游戏账号，请先在网页端仪表盘绑定，"
            "或在 QQ 私聊我发送【绑定账号帮助】"
        )

    guards = {("friend_requests", user_id), _login_guard(user_id)}
    if guards & _REFRESHING:
        return _busy_requests()
    _REFRESHING.update(guards)
    try:
        pending, requested = await call_in_main_loop(_fetch_friend_requests(account))
    except HTTPException as e:
        return FriendRequestsResult(message=f"读取好友申请失败：{e.detail}")
    except Exception as e:
        return FriendRequestsResult(message=f"读取好友申请失败：{e}")
    finally:
        _REFRESHING.difference_update(guards)
    return _requests_result(pending, requested, group_id)


@router.post(
    "/{group_id}/friend/requests/accept", response_model=FriendRequestsResult
)
async def friend_request_accept(
    group_id: int,
    form: FriendActionForm,
    token: CookieCache = Depends(verify_group_access),
):
    """同意好友申请（**会顶号**）。成功后顺手刷新好友列表缓存，并返回最新两份名单。"""
    target = int(form.viewer_id or 0)
    if target <= 0:
        return FriendRequestsResult(message="请输入有效的玩家 ID（纯数字）")

    user_id = int(token.user_id)
    account = await _require_account(user_id, group_id)
    if account is None:
        return FriendRequestsResult(
            message="还没有绑定游戏账号，请先在网页端仪表盘绑定，"
            "或在 QQ 私聊我发送【绑定账号帮助】"
        )

    guards = {("friend_action", user_id), _login_guard(user_id)}
    if guards & _REFRESHING:
        return _busy_requests()
    _REFRESHING.update(guards)
    try:
        ok, message, pending, requested = await call_in_main_loop(
            _accept_friend_request(account, user_id, target)
        )
    except HTTPException as e:
        return FriendRequestsResult(message=f"同意好友申请失败：{e.detail}")
    except Exception as e:
        return FriendRequestsResult(message=f"同意好友申请失败：{e}")
    finally:
        _REFRESHING.difference_update(guards)
    return _requests_result(pending, requested, group_id, message=message, ok=bool(ok))


@router.post(
    "/{group_id}/friend/requests/reject", response_model=FriendRequestsResult
)
async def friend_request_reject(
    group_id: int,
    form: FriendActionForm,
    token: CookieCache = Depends(verify_group_access),
):
    """拒绝好友申请（**会顶号**）"""
    target = int(form.viewer_id or 0)
    if target <= 0:
        return FriendRequestsResult(message="请输入有效的玩家 ID（纯数字）")

    user_id = int(token.user_id)
    account = await _require_account(user_id, group_id)
    if account is None:
        return FriendRequestsResult(
            message="还没有绑定游戏账号，请先在网页端仪表盘绑定，"
            "或在 QQ 私聊我发送【绑定账号帮助】"
        )

    guards = {("friend_action", user_id), _login_guard(user_id)}
    if guards & _REFRESHING:
        return _busy_requests()
    _REFRESHING.update(guards)
    try:
        ok, message, pending, requested = await call_in_main_loop(
            _reject_friend_request(account, target)
        )
    except HTTPException as e:
        return FriendRequestsResult(message=f"拒绝好友申请失败：{e.detail}")
    except Exception as e:
        return FriendRequestsResult(message=f"拒绝好友申请失败：{e}")
    finally:
        _REFRESHING.difference_update(guards)
    return _requests_result(pending, requested, group_id, message=message, ok=bool(ok))


@router.post(
    "/{group_id}/friend/requests/cancel", response_model=FriendRequestsResult
)
async def friend_request_cancel(
    group_id: int,
    form: FriendActionForm,
    token: CookieCache = Depends(verify_group_access),
):
    """撤回我发出的好友申请（**会顶号**）"""
    target = int(form.viewer_id or 0)
    if target <= 0:
        return FriendRequestsResult(message="请输入有效的玩家 ID（纯数字）")

    user_id = int(token.user_id)
    account = await _require_account(user_id, group_id)
    if account is None:
        return FriendRequestsResult(
            message="还没有绑定游戏账号，请先在网页端仪表盘绑定，"
            "或在 QQ 私聊我发送【绑定账号帮助】"
        )

    guards = {("friend_action", user_id), _login_guard(user_id)}
    if guards & _REFRESHING:
        return _busy_requests()
    _REFRESHING.update(guards)
    try:
        ok, message, pending, requested = await call_in_main_loop(
            _cancel_friend_request(account, target)
        )
    except HTTPException as e:
        return FriendRequestsResult(message=f"撤回好友申请失败：{e.detail}")
    except Exception as e:
        return FriendRequestsResult(message=f"撤回好友申请失败：{e}")
    finally:
        _REFRESHING.difference_update(guards)
    return _requests_result(pending, requested, group_id, message=message, ok=bool(ok))


@router.get("/{group_id}/friend/profile", response_model=ArenaProfileResult)
async def friend_profile(
    group_id: int,
    viewer_id: int,
    token: CookieCache = Depends(verify_group_access),
):
    """按好友的游戏 ID 查资料 —— 与竞技场「查 ID」返回结构完全一致。

    优先借正在运行的竞技场监控 client（不额外登录）；没有监控时用当前登录用户
    自己绑定的账号（`login.query` 优先复用缓存，刚刷过好友列表通常不会重新登录）。
    """
    if viewer_id <= 0:
        return ArenaProfileResult(message="请输入有效的玩家 ID（纯数字）")

    # 函数内 import：web 插件可能早于 jjckiller 插件加载（与 box_arena_api 一致）
    from ..jjckiller.model import build_profile_data

    user_id = int(token.user_id)

    arena = _get_arena(user_id, group_id)
    if arena is not None:
        try:
            data = await call_in_main_loop(
                build_profile_data(arena.client, viewer_id)
            )
        except HTTPException:
            raise
        except Exception as e:
            return ArenaProfileResult(message=f"查询失败：{e}")
        return ArenaProfileResult(ok=True, **data)

    account = await _require_account(user_id, group_id)
    if account is None:
        return ArenaProfileResult(
            message="没有可用的游戏账号：请先在网页端仪表盘绑定游戏账号，"
            "或开启竞技场监控后再查"
        )

    async def _query() -> dict:
        from ..login import query

        client = await query(account)
        return await build_profile_data(client, viewer_id)

    guards = {("friend_profile", user_id), _login_guard(user_id)}
    if guards & _REFRESHING:
        return ArenaProfileResult(
            message="正在登录游戏账号（刷新缓存 / 换装 / 好友操作），请稍候再试"
        )
    _REFRESHING.update(guards)
    try:
        data = await call_in_main_loop(_query())
    except HTTPException as e:
        return ArenaProfileResult(message=f"查询失败：{e.detail}")
    except Exception as e:
        return ArenaProfileResult(message=f"查询失败：{e}")
    finally:
        _REFRESHING.difference_update(guards)
    return ArenaProfileResult(ok=True, **data)
