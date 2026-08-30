from typing import List

try:
    from pydantic.v1 import BaseModel
except ImportError:
    from pydantic import BaseModel
from .common import *


class ErrorInfo(BaseModel):
    title: str = None
    message: str = None
    status: int = 0

    def __str__(self) -> str:
        return f"{self.title}: {self.message} (code={self.status})"


class SourceIniGetMaintenanceStatusResponse(BaseModel):
    encrypt: int = None
    res_http_type: int = None
    node_type: int = None
    silence_download_size: int = None
    res_ver: str = None
    execl_ver: str = None
    res_key: str = None
    start_time: str = None
    manifest_ver: str = None
    required_manifest_ver: str = None
    movie_ver: str = None
    sound_ver: str = None
    patch_ver: str = None
    resource: List[str] = None
    maintenance_message: str = None


class ToolSdkLoginResponse(BaseModel):
    is_risk: bool = False


class LoadIndexResponse(BaseModel):
    user_info: UserInfo = None
    user_jewel: UserJewel = None
    user_gold: UserGold = None
    user_gold_bank_info: UserBankGoldInfo = None
    unit_list: List[UnitData] = None
    user_chara_info: List[UserChara] = None
    deck_list: List[LoadDeckData] = None
    material_list: List[InventoryInfo] = None
    item_list: List[InventoryInfo] = None
    user_equip: List[InventoryInfo] = None
    user_ex_equip: List[ExtraEquipInfo] = None
    user_clan_battle_ex_equip_restriction: List[RestrictionExtraEquip] = None
    today_start_level: int = None
    shop: Shop = None
    tips_id_list: List[int] = None
    ini_setting: IniSetting = None
    daily_reset_time: int = None
    present_count: int = None
    login_bonus_list: LoginBonusList = None
    max_storage_num: int = None
    can_free_gacha: int = None
    can_receive_clan_battle_reward: int = None
    campaign_list: List[int] = None
    read_story_ids: List[int] = None
    clan_like_count: int = None
    dispatch_units: List[UnitDataForClanMember] = None
    clan_battle: ClanBattleData = None
    event_statuses: List[EventStatus] = None
    tower_status: TowerStatus = None
    bgm: List[MusicIdData] = None
    unlock_story_ids: List[int] = None
    can_campaign_gacha: int = None
    can_guarantee_gacha: int = None
    can_limited_guarantee_gacha: int = None
    start_dash_fes_info_list: List[StartDashFesInfo] = None
    return_fes_info_list: List[ReturnFesInfo] = None
    growth_unit_list: List[GrowthInfo] = None
    pa: int = None
    sdg_start: int = None
    sdg_end: int = None
    cf: RaceLoginBonusInfo = None
    drj: CampaignDate = None
    gacha_point_info_list: List[GachaPointInfo] = None
    voice: UserBirthDayVoice = None
    maintenance_status: MaintenanceStatus = None
    user_my_party: List[UserMyParty] = None
    user_my_party_tab: List[UserMyPartyTab] = None
    user_my_quest: List[UserMyQuest] = None
    csc: CounterStopCoinExchange = None
    cgl: int = None
    ebm: int = None
    lsm: int = None
    last_login_bonus_time: int = None
    friend_support_units: List[SupportUnitSetting] = None
    my_page_exists: bool = None
    my_page: List[MyPage] = None
    limit_still_ids: List[int] = None
    frame_ids: List[int] = None
    read_diary_ids: List[int] = None
    unlock_diary_ids: List[int] = None
    read_relay_story_ids: List[int] = None
    unlock_relay_story_ids: List[int] = None
    read_omp_story_ids: List[int] = None
    unlock_omp_story_ids: List[int] = None
    read_nyx_story_ids: List[int] = None
    unlock_nyx_story_ids: List[int] = None
    nyx_color_id: int = None
    cbm: int = None
    csm: int = None
    tbm: int = None
    dbm: int = None
    force_release_chapter: int = None
    een_n: int = None
    een_r: int = None
    serialcode_restrict_release_time: int = None
    chr: int = None
    nls: int = None
    event_sub_story: List[EventSubStory] = None
    cbsa: int = None
    legion_term: int = None
    part_maintenance_status: List[PartMaintenanceStatus] = None
    bank_bought: int = None
    user_redeem_unit: List[RedeemUnitInfo] = None
    errm: int = None
    taq: TaqGameSetting = None
    sre_term: SreTermInfo = None
    wac_start_time: int = None
    wac_end_time: int = None
    tcb: int = None
    ubr: int = None
    evfm: int = None
    giu: int = None
    exeq: int = None
    recheck_dmm_jewel: str = None
    shmb: int = None
    tvq: int = None
    sar: int = None
    mss: int = None
    ags: int = None
    rug: int = None
    tpc: int = None
    wcst: int = None
    hapi: int = None
    sdgl: int = None
    sdgl_start: int = None
    sdgl_end: int = None
    evmb: int = None
    banner_linked_pack_list: List[BannerLinkedPackList] = None
    adc: int = None
    receive_caravan_dice_count: int = None
    drc: int = None
    resident_info: MonthlyGachaInfo = None


class HomeIndexResponse(BaseModel):
    unread_message_list: UnreadMessageList = None
    missions: List[UserMissionInfo] = None
    season_pack: List[UserSeasonPackInfo] = None
    daily_reset_time: int = None
    limited_shop: List[LimitedShop] = None
    daily_shop: DailyShop = None
    user_clan: UserClan = None
    have_clan_invitation: int = None
    new_equip_donation: EquipRequests = None
    have_join_request: int = None
    quest_list: List[UserQuestInfo] = None
    dungeon_info: DungeonInfo = None
    training_quest_count: TrainingQuestCount = None
    training_quest_max_count: TrainingQuestCount = None
    training_quest_pack_end_time: int = None
    have_clan_battle_reward: int = None
    gold: List[int] = None
    paid_jewel: int = None
    free_jewel: int = None
    alchemy_reward_list: List[AlchemyReward] = None
    alchemy_reward_time: int = None
    season_pack_alert: int = None
    season_pack_end_time: int = None
    daily_jewel_pack_end: int = None
    last_friend_time: LastFriendTime = None
    clan_battle_remaining_count: int = None
    campaign_target_flag: bool = None
    everyday_jewel_pack_buy: bool = None
    chara_e_ticket_purchased_times: List[CharaExchangeTicketProductData] = None
    purchased_arcade_id_list: List[int] = None
    shiori_quest_info: ShioriQuestInfo = None
    srt_story_id_list: List[int] = None


class ClanBattleTopResponse(BaseModel):
    clan_battle_id: int = None
    period: int = None
    lap_num: int = None
    boss_info: List[BossInfo] = None
    damage_history: List[DamageHistory] = None
    period_rank: int = None
    remaining_count: int = None
    used_unit: List[int] = None
    using_unit: List[int] = None
    point: int = None
    hp_reset_count: int = None
    boss_reward: List[BossReward] = None
    last_rank_result: List[RankResult] = None
    change_period: int = None
    change_season: int = None
    add_present_count: int = None
    carry_over_time: int = None
    clan_battle_mode: int = None
    next_clan_battle_mode: int = None
    user_clan: ClanBattleTopUserClanInformation = None
    missions: List[UserMissionInfo] = None
    challenge_reward: List[ClanBattleExtraBattleChallengeRewardInfo] = None


class ClanBattleReloadDetailInfoResponse(BaseModel):
    fighter_num: int = None
    current_hp: int = None


class ClanBattleLogListResponse(BaseModel):
    clan_battle_mode: int = None
    battle_list: List[BattleInfo] = None
    max_page: int = None


class ClanBattleTimeLineReportResponse(BaseModel):
    target_viewer_id: int = None
    order_num: int = None
    lap_num: int = None
    total_damage: int = None
    start_remain_time: int = None
    battle_time: int = None
    battle_end_time: int = None
    units: List[BattleUnitInfo]
    timeline: List[UnitBurstTime] = None


class ClanBattleSupportUnitList2Response(BaseModel):
    support_unit_list: List[ClanBattleSupportUnitLight] = None


class ClanBattlePeriodRanking(BaseModel):
    """period_ranking 单条公会排名记录"""

    rank: int = None
    damage: int = None
    clan_name: str = None
    leader_name: str = None
    leader_viewer_id: int = None
    member_num: int = None
    grade_rank: int = None


class ClanBattlePeriodRankingPageInfo(BaseModel):
    """兼容部分协议版本的 page_info 层结构"""

    period_ranking: List[ClanBattlePeriodRanking] = None


class ClanBattlePeriodRankingResponse(BaseModel):
    """B 服当前结构：period_ranking 在顶层；旧协议在 page_info 下，两者都兼容"""

    period_ranking: List[ClanBattlePeriodRanking] = None
    page_info: ClanBattlePeriodRankingPageInfo = None

    @property
    def ranking_list(self):
        if self.period_ranking:
            return self.period_ranking
        if self.page_info and self.page_info.period_ranking:
            return self.page_info.period_ranking
        return None


class ClanInfoResponse(BaseModel):
    clan: ClanData = None
    clan_status: int = None
    user_equip: List[InventoryInfoShort] = None
    have_join_request: int = None
    unread_liked_count: int = None
    is_equip_request_finish_checked: int = None
    add_present_count: int = None
    user_gold: UserGold = None
    latest_request_time: int = None
    current_period_ranking: int = None
    last_total_ranking: int = None
    current_clan_battle_mode: int = None
    current_battle_joined: int = None
    last_clan_battle_mode: int = None
    last_battle_joined: int = None
    grade_rank: int = None
    clan_point: int = None
    remaining_count: int = None


class ArenaInfoResponse(BaseModel):
    arena_info: ArenaInfo = None
    attack_deck: DeckData = None
    defend_deck: DeckData = None
    search_opponent: List[SearchOpponent] = None
    reward_info: InventoryInfo = None
    reward_hour_num: int = None
    is_time_reward_max: bool = None


class GrandArenaInfoResponse(BaseModel):
    grand_arena_info: GrandArenaInfo = None
    attack_deck_list: List[DeckData] = None
    defend_deck_list: List[DeckData] = None
    search_opponent: List[GrandArenaSearchOpponent] = None
    reward_info: InventoryInfo = None
    reward_hour_num: int = None
    is_time_reward_max: bool = None


class GrandArenaHistoryResponse(BaseModel):
    grand_arena_history_list: List[GrandArenaHistoryInfo] = None


class GrandArenaHistoryDetailResponse(BaseModel):
    grand_arena_history_detail: GrandArenaHistoryDetailInfo = None


class ArenaRankingResponse(BaseModel):
    ranking: List[RankingSearchOpponent] = None


class GrandArenaRankingResponse(BaseModel):
    ranking: List[GrandArenaSearchOpponent] = None


class ProfileGetResponse(BaseModel):
    user_info: ProfileUserInfo = None
    quest_info: ProfileQuestInfo = None
    favorite_unit: UnitDataForView = None
    clan_name: str = None
    own_clan_role: int = None
    clan_invite_result_code: int = None
    invite_enable_time: int = None
    friend_support_units: List[SupportUnitForProfile] = None
    clan_support_units: List[SupportUnitForProfile] = None
    campaign_target_list: List[CampaignTarget] = None
    clan_battle_id: int = None
    clan_battle_mode: int = None
    clan_battle_own_score: int = None


class SupportUnitGetSettingResponse(BaseModel):
    friend_support_units: List[SupportUnitSetting] = None
    clan_support_units: List[SupportUnitSetting] = None
    clan_support_available_status: int = None


class SupportUnitChangeSettingResponse(BaseModel):
    support_units: SupportUnitSetting = None
    support_time_bonus: List[InventoryInfo] = None
    support_count_bonus: List[InventoryInfo] = None
    add_present_count: int = None
