import random
from typing import List

try:
    from pydantic.v1 import BaseModel
except ImportError:
    from pydantic import BaseModel

from .common import ExtraEquipChangeUnit


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
