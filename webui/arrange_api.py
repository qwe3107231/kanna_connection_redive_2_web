"""网页端「排刀」接口。

排刀的数据来自一份**公开分享的腾讯文档表格**（地址可以在网页上随时改），
表格解析在 `util/arrange_sheet.py`。这里负责：

* 表格地址 / 角色别名配置的读写（**按账号（QQ）单独保存**，不是按群共享）；
* 抓取结果缓存（腾讯文档偶尔抽风时退回上次缓存，不让页面直接空掉）；
* 把作业和「当前登录用户的 BOX + 本群公会助战」拼在一起，前端据此判断
  每一刀能不能出、缺的角色能不能借助战。

在线表格地址**默认是空的**：每个账号第一次进来要自己填，不会套用内置表格。
只读本地缓存表，不登录游戏、不顶号。BOX / 助战缓存不是最新时，页面会提示
去「个人 BOX」点【刷新缓存】（对应群里的【刷新box缓存】/【刷新助战缓存】）。
"""

from __future__ import annotations

import asyncio
import time
from typing import Dict, List, Optional, Sequence, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from nonebot import logger
from pydantic import BaseModel, Field

from hoshino.modules.priconne import chara
from hoshino.modules.priconne._pcr_data import CHARA_NAME

from ..basedata import FilePath
from ..database.dal import CookieCache, pcr_sqla
from ..setting import ArrangeSetting, WebSetting
from ..util.arrange_sheet import (
    RawEntry,
    ResolvedEntry,
    SheetError,
    default_aliases,
    extract_entries,
    fetch_sheet_texts,
    format_values,
    make_boss_label,
    make_boss_text,
    parse_entry_text,
    parse_sheet_url,
    resolve_entries,
)
from ..util.tools import load_config, write_config
from .box_arena_api import _avatar_star
from .util import verify_group_access

router = APIRouter(prefix=WebSetting.api_base.value)


# ============================ 返回给前端的数据模型 ============================


class ArrangeUnit(BaseModel):
    """排刀队伍里的一个角色（只带画头像需要的字段，比 BOX 查询轻很多）。"""

    unit_id: int = 0
    chara_name: str = ""
    avatar: str = ""
    rarity: int = 0
    battle_rarity: int = 0
    rank: int = 0
    level: int = 0
    # 显示用：有数据（自己拥有或助战可借）。前端画头像外框/星级看它。
    owned: bool = True
    # 玩家自己的 BOX 里有没有这个角色 —— 判断「缺几个」用这个，不是 owned。
    player_owned: bool = False
    # 本群公会助战里有没有这个角色（缺的角色能不能借）。
    from_support: bool = False
    # 助战提供者昵称（自己拥有的角色就是自己的昵称）
    player_name: str = ""


class ArrangeTeam(BaseModel):
    """表格里的一条作业。"""

    id: int = 0
    raw: str = ""
    stage: str = ""
    bosses: List[int] = Field(default_factory=list)
    boss_label: str = ""
    boss_text: str = ""
    units: List[int] = Field(default_factory=list)
    unit_names: List[str] = Field(default_factory=list)
    unknown_names: List[str] = Field(default_factory=list)
    # return = 补偿刀时间（90s / 71s…）；damage = 伤害（4.5 亿）；
    # both = 一条作业同时写了伤害和补偿时间（如「3.25 60s」）
    value_kind: str = "damage"
    value: float = 0.0
    value_label: str = ""
    # 分开存，前端才能既显示伤害又显示补偿时间
    damage_value: float = 0.0
    return_seconds: float = 0.0
    source_row: int = 0
    source_col: int = 0


class ArrangeChara(BaseModel):
    """给「未识别角色」手动匹配用的角色选项。"""

    unit_id: int = 0
    name: str = ""
    # 全部角色名 / 别名（中文主名、日文、英文、社区别名），供下拉框搜索
    aliases: List[str] = Field(default_factory=list)


class ArrangeData(BaseModel):
    ok: bool = False
    message: str = ""
    url: str = ""
    tab: str = ""
    aliases: Dict[str, str] = Field(default_factory=dict)
    fetched_at: int = 0
    entry_count: int = 0
    teams: List[ArrangeTeam] = Field(default_factory=list)
    units: Dict[str, ArrangeUnit] = Field(default_factory=dict)
    owned_count: int = 0
    support_count: int = 0
    support_ids: List[int] = Field(default_factory=list)
    # True = 助战可以借全部角色（默认）；False = 只能借本群公会助战缓存里的角色
    support_all: bool = True
    unknown_names: List[str] = Field(default_factory=list)
    # 只有出现「未识别角色」时才带全角色列表，供页面上的下拉框手动匹配；
    # 没有未识别角色时是空列表，避免白白把 300 多个角色传给前端。
    charas: List[ArrangeChara] = Field(default_factory=list)
    cached: bool = False


class ArrangeConfig(BaseModel):
    url: str = ""
    aliases: Dict[str, str] = Field(default_factory=dict)


class ArrangeConfigForm(BaseModel):
    url: str
    aliases: Dict[str, str] = Field(default_factory=dict)


# ============================ 缓存 ============================
# 一个 JSON 文件**按账号（QQ）保存**：表格地址、角色别名、上次抓到的原始作业文本、
# 抓取时间。按账号而不是按群，是因为不同账号可能用不同的在线表格；
# 存原始文本而不是解析后的 unit_id：用户改了别名之后不用重新抓表格就能立刻生效。

_CACHE_LOCK = asyncio.Lock()
# v2：从「按群保存」改成「按账号保存」，并且表格地址默认是空。
_CACHE_VERSION = 2


def _cache_path() -> str:
    return str(FilePath.arrange_sheet.value)


def _load_cache() -> dict:
    data = load_config(_cache_path())
    if not isinstance(data, dict):
        return {"version": _CACHE_VERSION, "accounts": {}}
    if data.get("version") != _CACHE_VERSION or not isinstance(
        data.get("accounts"), dict
    ):
        # 旧版是按群存的（groups），不再使用：直接换成按账号的新结构。
        # 在线表格地址本来就要求「默认空」，所以不做迁移。
        return {"version": _CACHE_VERSION, "accounts": {}}
    return data


def _save_cache(cache: dict) -> None:
    try:
        write_config(_cache_path(), cache)
    except Exception as exc:  # noqa: BLE001 - 写缓存失败不影响本次返回
        logger.warning(f"排刀缓存写入失败：{exc!r}")


def _account_cfg(cache: dict, user_id: int) -> dict:
    """取某个账号的排刀配置（没有就初始化一份）。"""
    accounts = cache.setdefault("accounts", {})
    cfg = accounts.setdefault(str(int(user_id)), {})
    # 在线表格地址默认空：每个账号要自己填
    cfg.setdefault("url", "")
    aliases = cfg.get("aliases")
    if not isinstance(aliases, dict):
        aliases = default_aliases()
        cfg["aliases"] = aliases
    cfg.setdefault("raw_entries", [])
    cfg.setdefault("fetched_at", 0)
    cfg.setdefault("fetched_url", "")
    cfg.setdefault("last_error", "")
    # 上次「尝试抓取」的时间：抓失败后 60 秒内不再反复重试，避免每次打开页面
    # 都卡在 20 秒超时上；用户点【刷新表格】会强制重试。
    cfg.setdefault("last_try", 0)
    return cfg


def _fmt_time(timestamp: int) -> str:
    if not timestamp:
        return "从未抓取"
    return time.strftime("%m-%d %H:%M", time.localtime(int(timestamp)))


def _chara_name(unit_id: int) -> str:
    names = CHARA_NAME.get(int(unit_id))
    return names[0] if names else str(unit_id)


def _is_npc(unit_id: int) -> bool:
    try:
        return bool(chara.is_npc(int(unit_id)))
    except Exception:  # noqa: BLE001
        return False


def _avatar_url(group_id: int, unit_id: int, rarity: int, battle_rarity: int) -> str:
    star = _avatar_star(int(rarity or 0))
    return (
        f"{WebSetting.api_base.value}/{group_id}/box/avatar/{unit_id}"
        f"?star={star}&rarity={int(rarity or 0)}&battle_rarity={int(battle_rarity or 0)}"
    )


def _missing_avatar_url(group_id: int, unit_id: int) -> str:
    return f"{WebSetting.api_base.value}/{group_id}/box/avatar/{unit_id}?star=3"


def _unit_row_key(row) -> Tuple[int, int, int, int]:
    return (
        int(getattr(row, "rarity", 0) or 0),
        int(getattr(row, "battle_rarity", 0) or 0),
        int(getattr(row, "level", 0) or 0),
        int(getattr(row, "rank", 0) or 0),
    )


def _best_support_rows(rows: Sequence) -> Dict[int, object]:
    """同一个角色可能被多个公会成员挂助战，只留数据最好的那一条展示。"""
    best: Dict[int, object] = {}
    for row in rows:
        unit_id = int(getattr(row, "unit_id", 0) or 0)
        if unit_id <= 0 or _is_npc(unit_id):
            continue
        current = best.get(unit_id)
        if current is None or _unit_row_key(row) > _unit_row_key(current):
            best[unit_id] = row
    return best


def _make_unit(
    group_id: int,
    unit_id: int,
    own_row,
    support_row,
) -> ArrangeUnit:
    if own_row is not None:
        rarity = int(getattr(own_row, "rarity", 0) or 0)
        battle_rarity = int(getattr(own_row, "battle_rarity", 0) or 0)
        return ArrangeUnit(
            unit_id=unit_id,
            chara_name=_chara_name(unit_id),
            avatar=_avatar_url(group_id, unit_id, rarity, battle_rarity),
            rarity=rarity,
            battle_rarity=battle_rarity,
            rank=int(getattr(own_row, "rank", 0) or 0),
            level=int(getattr(own_row, "level", 0) or 0),
            owned=True,
            player_owned=True,
            from_support=support_row is not None,
            player_name=str(getattr(own_row, "name", "") or ""),
        )
    if support_row is not None:
        rarity = int(getattr(support_row, "rarity", 0) or 0)
        battle_rarity = int(getattr(support_row, "battle_rarity", 0) or 0)
        return ArrangeUnit(
            unit_id=unit_id,
            chara_name=_chara_name(unit_id),
            avatar=_avatar_url(group_id, unit_id, rarity, battle_rarity),
            rarity=rarity,
            battle_rarity=battle_rarity,
            rank=int(getattr(support_row, "rank", 0) or 0),
            level=int(getattr(support_row, "level", 0) or 0),
            owned=True,
            player_owned=False,
            from_support=True,
            player_name=str(getattr(support_row, "name", "") or ""),
        )
    return ArrangeUnit(
        unit_id=unit_id,
        chara_name=_chara_name(unit_id),
        avatar=_missing_avatar_url(group_id, unit_id),
        owned=False,
        player_owned=False,
        from_support=False,
    )


def _sort_key(entry: ResolvedEntry) -> Tuple[int, int, int, int]:
    stage_order = {"A": 0, "B": 1, "C": 2, "D": 3}
    return (
        stage_order.get(entry.stage, 99),
        entry.bosses[0] if entry.bosses else 99,
        entry.row,
        entry.col,
    )


# ============================ 抓取 + 缓存 ============================


async def _ensure_raw_entries(
    user_id: int, refresh: bool
) -> Tuple[dict, List[RawEntry], bool, str]:
    """确保缓存里有作业原始文本，返回 (账号配置, 原始作业, 是否用了旧缓存, 提示)。

    刷新策略：
      * 没填表格地址 → 直接提示去填，不会去抓；
      * `refresh=True` / 没缓存 / 表格地址换了 → 必须抓一次；
      * 缓存超过 `ArrangeSetting.cache_ttl` → 顺手抓一次；
      * 抓取失败时，有旧缓存就继续用旧缓存，并把原因带回去给前端提示。
    """
    async with _CACHE_LOCK:
        cache = _load_cache()
        cfg = _account_cfg(cache, user_id)
        url = str(cfg.get("url") or "").strip()
        if not url:
            _save_cache(cache)
            raise SheetError(
                "还没有设置在线表格地址：请在上方填写腾讯文档表格地址并点【保存设置】。"
            )
        raw_texts = [str(item) for item in (cfg.get("raw_entries") or []) if str(item).strip()]
        fetched_at = int(cfg.get("fetched_at") or 0)
        ttl = int(ArrangeSetting.cache_ttl.value)

        stale = bool(fetched_at) and (time.time() - fetched_at > ttl)
        last_try = int(cfg.get("last_try") or 0)
        failed_recently = (
            bool(cfg.get("last_error")) and (time.time() - last_try < 60)
        )
        need_fetch = (
            bool(refresh)
            or not raw_texts
            or str(cfg.get("fetched_url") or "") != url
            or (stale and not failed_recently)
        )

        cached_flag = False
        message = ""
        if need_fetch:
            cfg["last_try"] = int(time.time())
            try:
                cells = await fetch_sheet_texts(
                    url, timeout=float(ArrangeSetting.fetch_timeout.value)
                )
                entries = extract_entries(cells)
                if not entries:
                    raise SheetError(
                        "表格里没有识别到作业（格式示例：B1 狼 病娇 战狼 军病 八筒 90s）"
                    )
                raw_texts = [entry.raw for entry in entries]
                cfg["raw_entries"] = raw_texts
                cfg["fetched_at"] = int(time.time())
                cfg["fetched_url"] = url
                cfg["last_error"] = ""
                fetched_at = int(cfg["fetched_at"])
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"排刀表格抓取失败 user={user_id}: {exc!r}")
                cfg["last_error"] = str(exc)
                if not raw_texts:
                    _save_cache(cache)
                    raise SheetError(str(exc))
                cached_flag = True
                message = (
                    f"表格抓取失败，显示 {_fmt_time(fetched_at)} 的缓存：{exc}"
                )

        _save_cache(cache)
        entries = [entry for entry in (parse_entry_text(text) for text in raw_texts) if entry]
        return cfg, entries, cached_flag, message


async def build_arrange_data(
    group_id: int, user_id: int, refresh: bool = False
) -> ArrangeData:
    try:
        cfg, raw_entries, cached_flag, message = await _ensure_raw_entries(
            int(user_id), refresh
        )
    except SheetError as exc:
        cfg = _account_cfg(_load_cache(), int(user_id))
        return ArrangeData(
            ok=False,
            message=str(exc),
            url=str(cfg.get("url") or ""),
            aliases=dict(cfg.get("aliases") or {}),
        )

    aliases = cfg.get("aliases") if isinstance(cfg.get("aliases"), dict) else {}
    resolved, unknown_names = resolve_entries(raw_entries, aliases)
    resolved.sort(key=_sort_key)

    player_units = await pcr_sqla.get_player_units(int(user_id))
    support_rows = await pcr_sqla.get_support_units(int(group_id))

    own_by_id: Dict[int, object] = {}
    for row in player_units:
        unit_id = int(getattr(row, "unit_id", 0) or 0)
        if unit_id > 0 and not _is_npc(unit_id):
            own_by_id[unit_id] = row
    support_by_id = _best_support_rows(support_rows)

    units: Dict[str, ArrangeUnit] = {}

    def unit_of(unit_id: int) -> ArrangeUnit:
        key = str(unit_id)
        if key not in units:
            units[key] = _make_unit(
                group_id,
                unit_id,
                own_by_id.get(unit_id),
                support_by_id.get(unit_id),
            )
        return units[key]

    teams: List[ArrangeTeam] = []
    for index, entry in enumerate(resolved):
        for unit_id in entry.unit_ids:
            unit_of(unit_id)
        damage = entry.damage
        return_seconds = entry.return_seconds
        if damage is not None and return_seconds is not None:
            value_kind = "both"
        elif return_seconds is not None:
            value_kind = "return"
        else:
            value_kind = "damage"
        value = float(return_seconds if return_seconds is not None else (damage or 0.0))
        teams.append(
            ArrangeTeam(
                id=index,
                raw=entry.raw,
                stage=entry.stage,
                bosses=list(entry.bosses),
                boss_label=make_boss_label(entry.stage, entry.bosses),
                boss_text=make_boss_text(entry.stage, entry.bosses),
                units=list(entry.unit_ids),
                unit_names=list(entry.unit_names),
                unknown_names=list(entry.unknown_names),
                value_kind=value_kind,
                value=value,
                value_label=format_values(damage, return_seconds),
                damage_value=float(damage or 0.0),
                return_seconds=float(return_seconds or 0.0),
                source_row=int(entry.row),
                source_col=int(entry.col),
            )
        )

    support_all = bool(ArrangeSetting.support_all.value)

    notes: List[str] = []
    if message:
        notes.append(message)
    if not own_by_id:
        notes.append(
            "还没有你的 BOX 缓存：请先在「个人 BOX」点【刷新缓存】"
            "（等价于群里发【刷新box缓存】），否则判断不了你有哪些角色。"
        )
    if not support_by_id and not support_all:
        notes.append(
            "本群还没有公会助战缓存：请在 BOX/助战页点【刷新缓存】"
            "（等价于群里发【刷新助战缓存】），否则缺的角色借不到。"
        )

    tab = ""
    try:
        tab = parse_sheet_url(str(cfg.get("url") or ""))[1]
    except SheetError:
        pass

    charas: List[ArrangeChara] = []
    if unknown_names:
        for unit_id, names in CHARA_NAME.items():
            if _is_npc(int(unit_id)):
                continue
            alias_list: List[str] = []
            seen_alias = set()
            for raw_name in names:
                alias = str(raw_name or "").strip()
                if not alias or alias in seen_alias:
                    continue
                seen_alias.add(alias)
                alias_list.append(alias)
            charas.append(
                ArrangeChara(
                    unit_id=int(unit_id),
                    name=(alias_list[0] if alias_list else str(unit_id)),
                    aliases=alias_list,
                )
            )
        charas.sort(key=lambda item: (item.name, item.unit_id))

    return ArrangeData(
        ok=True,
        message="\n".join(notes),
        url=str(cfg.get("url") or ""),
        tab=tab,
        aliases=dict(aliases),
        fetched_at=int(cfg.get("fetched_at") or 0),
        entry_count=len(teams),
        teams=teams,
        units=units,
        owned_count=len(own_by_id),
        support_count=len(support_by_id),
        support_ids=sorted(support_by_id.keys()),
        support_all=support_all,
        unknown_names=unknown_names,
        charas=charas,
        cached=cached_flag,
    )


# ============================ 路由 ============================


@router.get("/{group_id}/arrange", response_model=ArrangeData)
async def get_arrange_data(
    group_id: int,
    refresh: int = 0,
    token: CookieCache = Depends(verify_group_access),
):
    """排刀页面的主数据：表格作业 + 当前用户 BOX/助战情况。

    `refresh=1` 强制重新抓表格（网页上的【刷新表格】按钮）；平时走缓存，
    缓存超过 10 分钟也会自动抓一次。
    """
    return await build_arrange_data(group_id, int(token.user_id), bool(refresh))


@router.get("/{group_id}/arrange/config", response_model=ArrangeConfig)
async def get_arrange_config(
    group_id: int, token: CookieCache = Depends(verify_group_access)
):
    """读当前账号的排刀表格地址和角色别名（按账号单独保存）。"""
    async with _CACHE_LOCK:
        cache = _load_cache()
        cfg = _account_cfg(cache, int(token.user_id))
        _save_cache(cache)
        return ArrangeConfig(
            url=str(cfg.get("url") or ""),
            aliases=dict(cfg.get("aliases") or {}),
        )


@router.post("/{group_id}/arrange/config", response_model=ArrangeConfig)
async def save_arrange_config(
    group_id: int,
    form: ArrangeConfigForm,
    token: CookieCache = Depends(verify_group_access),
):
    """保存当前账号的表格地址 / 角色别名（按账号单独保存，不影响别人）。

    表格地址只接受 docs.qq.com 的 /sheet/ 链接（避免 bot 变成任意 URL 的代理）。
    改了地址会清掉旧缓存；只改别名不会清缓存，下一次读取会用新别名重新解析。
    """
    url = (form.url or "").strip()
    try:
        parse_sheet_url(url)
    except SheetError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    aliases: Dict[str, str] = {}
    for key, value in (form.aliases or {}).items():
        key = str(key).strip()
        value = str(value).strip()
        if not key or not value:
            continue
        if len(key) > 40 or len(value) > 40:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "角色别名太长了（每条最多 40 个字符）",
            )
        aliases[key] = value
    if len(aliases) > 200:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "角色别名太多了（最多 200 条）"
        )

    async with _CACHE_LOCK:
        cache = _load_cache()
        cfg = _account_cfg(cache, int(token.user_id))
        old_url = str(cfg.get("url") or "")
        cfg["url"] = url
        cfg["aliases"] = aliases
        if old_url != url:
            cfg["raw_entries"] = []
            cfg["fetched_at"] = 0
            cfg["fetched_url"] = ""
            cfg["last_error"] = ""
            cfg["last_try"] = 0
        _save_cache(cache)

    return ArrangeConfig(url=url, aliases=aliases)
