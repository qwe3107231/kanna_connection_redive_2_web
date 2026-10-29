import random
from typing import List

try:
    from pydantic.v1 import BaseModel
except ImportError:
    from pydantic import BaseModel

from .common import ChangeRarityUnit, ExtraEquipChangeUnit


class RequestBase(BaseModel):
    viewer_id: str = None
    tw_server_id: str = None  # 台湾需要

    @property
    def header(self) -> bool:
        return False

    @property
    def crypted(self) -> bool:
        return True

    @property
    def allow_empty_response(self) -> bool:
        """这个接口「成功时 data 也可能为空」吗？默认 False。

        `BCRClient.callapi` 默认把空 `data` 当成异常（抛 `NoneResponseError`，
        上层会变成用户看到的「网络异常，请稍后再试」）。但有几个接口**成功时就是
        没有 payload**，实测返回 `{'data_headers': {...'result_code': 1}, 'data': []}`：

          - `unit/equip_ex`（换 EX 装）
          - `support_unit/change_setting` 的**撤下**（`action=2`）

        这类接口把它覆写成 True，别把「成功」误判成「网络异常」。
        （autopcr 那边压根没有这个判空，所以它一直没这个问题。）
        """
        return False

    @property
    def url(self) -> str:
        raise NotImplementedError()


class ToolSdkLoginRequest(RequestBase):
    uid: str = None
    access_key: str = None
    platform: str = None
    channel_id: str = "1"

    @property
    def url(self) -> str:
        return "tool/sdk_login"

    @property
    def header(self) -> bool:
        return True


class CheckGameStartRequest(RequestBase):
    apptype: int = 0
    campaign_data: str = ""
    campaign_user: int = random.randint(0, 100000) & ~1

    @property
    def url(self) -> str:
        return "check/game_start"

    @property
    def header(self) -> bool:
        return True


class CheckAgreementRequest(RequestBase):
    @property
    def url(self) -> str:
        return "check/check_agreement"


class SourceIniGetMaintenanceStatusRequest(RequestBase):
    @property
    def url(self) -> str:
        return "source_ini/get_maintenance_status?format=json"

    @property
    def crypted(self) -> bool:
        return False


class LoadIndexRequest(RequestBase):
    carrier: str = "OPPO"

    @property
    def url(self) -> str:
        return "load/index"


class HomeIndexRequest(RequestBase):
    message_id: int = 1
    tips_id_list: List[int] = []
    is_first: int = 1
    gold_history: int = 0

    @property
    def url(self) -> str:
        return "home/index"


class ClanBattleTopRequest(RequestBase):
    is_first: int = 0
    clan_id: int = None
    current_clan_battle_coin: int = None

    @property
    def url(self) -> str:
        return "clan_battle/top"


class ClanBattleReloadDetailInfoRequest(RequestBase):
    clan_id: int = None
    clan_battle_id: int = None
    lap_num: int = None
    order_num: int = None

    @property
    def url(self) -> str:
        return "clan_battle/reload_detail_info"


class ClanBattleLogListRequest(RequestBase):
    clan_battle_id: int = None
    order_num: int = 0
    page: int = None
    phases: List[int] = [1, 2, 3, 4]
    report_types: List[int] = [1]
    hide_same_units: int = 0
    favorite_ids: list = []
    sort_type: int = 4

    @property
    def url(self) -> str:
        return "clan_battle/battle_log_list"


class ClanBattleTimeLineReportRequest(RequestBase):
    target_viewer_id: int = None
    clan_battle_id: int = None
    battle_log_id: int = None

    @property
    def url(self) -> str:
        return "clan_battle/timeline_report"


class ClanBattleSupportUnitList2Request(RequestBase):
    clan_id: int = None

    @property
    def url(self) -> str:
        return "clan_battle/support_unit_list_2"


class ClanBattlePeriodRankingRequest(RequestBase):
    """会战期间全服公会排名（游戏内会战排名列表同款接口），每页 10 条，page 从 0 开始"""

    clan_id: int = None
    clan_battle_id: int = None
    period: int = 1
    month: int = 0
    page: int = 0
    is_my_clan: int = 0
    is_first: int = 1

    @property
    def url(self) -> str:
        return "clan_battle/period_ranking"


class ClanInfoRequest(RequestBase):
    clan_id: int = None
    get_user_equip: int = 0

    @property
    def url(self) -> str:
        return "clan/info"


class ArenaInfoRequest(RequestBase):
    @property
    def url(self) -> str:
        return "arena/info"


class GrandArenaInfoRequest(RequestBase):
    @property
    def url(self) -> str:
        return "grand_arena/info"


class GrandArenaHistoryRequest(RequestBase):
    @property
    def url(self) -> str:
        return "grand_arena/history"


class GrandArenaHistoryDetailRequest(RequestBase):
    log_id: int = None

    @property
    def url(self) -> str:
        return "grand_arena/history_detail"


class ArenaRankingRequest(RequestBase):
    limit: int = 20
    page: int = None

    @property
    def url(self) -> str:
        return "arena/ranking"


class GrandArenaRankingRequest(RequestBase):
    limit: int = 20
    page: int = None

    @property
    def url(self) -> str:
        return "grand_arena/ranking"


class ProfileGetRequest(RequestBase):
    target_viewer_id: int = None

    @property
    def url(self) -> str:
        return "profile/get_profile"


class SupportUnitGetSettingRequest(RequestBase):
    @property
    def url(self) -> str:
        return "support_unit/get_setting"


class SupportUnitChangeSettingRequest(RequestBase):
    support_type: int = None
    position: int = None
    action: int = None
    unit_id: int = None

    @property
    def url(self) -> str:
        return "support_unit/change_setting"

    @property
    def allow_empty_response(self) -> bool:
        # 撤下支援（action=2）成功时游戏返回空 data，换上（action=1）才有 payload；
        # 不置 True 的话「顶掉挂最久的那个」这条路径会误报「网络异常」。
        return True


class UnitEquipExRequest(RequestBase):
    """更换角色的 EX 装备。

    `ExtraEquipChangeUnit` 里有两个槽位字段，**只传需要动的那一个，另一个给 None**：
    普通 EX 走 `ex_equip_slot`，会战 EX 走 `cb_ex_equip_slot`（见 `unit_equip_ex`）。
    """

    ex_equip_change_unit_list: List[ExtraEquipChangeUnit] = None

    @property
    def url(self) -> str:
        return "unit/equip_ex"

    @property
    def allow_empty_response(self) -> bool:
        # 换 EX 装成功时游戏返回 `data: []`（响应模型是空的）。
        return True


class ChangeRarityRequest(RequestBase):
    """调整角色的**战斗星级**（只能 3 / 4 / 5），不会改变觉醒后的稀有度。

    ⚠️ `ChangeRarityUnit.unit_id` 是**6 位**角色 ID（4 位角色 ID * 100 + 1，
    例：1001 → 100101），与 `load/index` 里 `unit_list[].id`、
    `support_unit/change_setting` 的 `unit_id` 同一口径（AUTOPCR 的 `unitchoice`
    默认值 100101 也是这个）；**不是**数据库 `PlayerUnit.unit_id` 的 4 位口径。
    """

    change_rarity_unit_list: List[ChangeRarityUnit] = None

    @property
    def url(self) -> str:
        return "unit/change_rarity"

    @property
    def allow_empty_response(self) -> bool:
        # 这是写操作，成功时游戏可能没有 payload（与 `unit/equip_ex` 同类）；
        # 真正失败会走 server_error / result_code，不会落到这里。
        return True


# ---- 好友（网页端「好友」页签用；接口与 autopcr 的【加好友】/【删好友】同源）----
# 好友列表是**别人账号上的数据**，只能拿当前登录用户自己绑定的号去查，
# 复用不了竞技场监控的 client（那可能是群监控人的号，好友列表不是同一个人）。
class FriendFriendListRequest(RequestBase):
    @property
    def url(self) -> str:
        return "friend/friend_list"


class FriendRequestRequest(RequestBase):
    target_viewer_id: int = None

    @property
    def url(self) -> str:
        return "friend/request"

    @property
    def allow_empty_response(self) -> bool:
        # 发送好友请求成功时游戏可能返回空 data（与 `unit/equip_ex` 同类）；
        # 不置 True 会被 callapi 当成「网络异常」，让人误以为没发出去。
        return True


class FriendRemoveRequest(RequestBase):
    target_viewer_id: int = None

    @property
    def url(self) -> str:
        return "friend/remove"

    @property
    def allow_empty_response(self) -> bool:
        # 删除好友成功时游戏可能返回空 data，原因同上。
        return True


# ---- 好友申请（待审核 / 申请中，对应游戏「好友管理」界面）----
class FriendPendingListRequest(RequestBase):
    """待审核列表：别人申请加我为好友、等我处理的名单"""

    @property
    def url(self) -> str:
        return "friend/pending_list"


class FriendRequestListRequest(RequestBase):
    """申请中的名单：我发出去、对方还没处理的好友申请"""

    @property
    def url(self) -> str:
        return "friend/request_list"


class FriendAcceptRequest(RequestBase):
    target_viewer_id: int = None

    @property
    def url(self) -> str:
        return "friend/accept"

    @property
    def allow_empty_response(self) -> bool:
        return True


class FriendRejectRequest(RequestBase):
    target_viewer_id: int = None

    @property
    def url(self) -> str:
        return "friend/reject"

    @property
    def allow_empty_response(self) -> bool:
        return True


class FriendCancelRequest(RequestBase):
    target_viewer_id: int = None

    @property
    def url(self) -> str:
        return "friend/cancel"

    @property
    def allow_empty_response(self) -> bool:
        return True
