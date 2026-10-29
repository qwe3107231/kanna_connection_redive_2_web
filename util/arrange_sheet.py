"""腾讯文档在线表格抓取 + 排刀作业解析（网页端「排刀」页签用）。

数据源是**公开分享**的腾讯文档表格，例如：

    https://docs.qq.com/sheet/DRHJYcERuc2RpRUpG?tab=BB08J2

腾讯文档没有公开的读表 API，这里走它网页自己用的 `dop-api/opendoc`：

    GET https://docs.qq.com/dop-api/opendoc?id={file_id}&tab={tab}&normal=1&outformat=1

返回 `clientVars.collab_client_vars.initialAttributedText.text[0]`，里面是：

* `related_sheet`：base64(zlib(protobuf))，整张表的单元格数据；
* `block_datas[*].related_sheet`：表格很大时按块返回，结构同上。

protobuf 结构（2026-10 实测；社区解析口径一致）：

* sheet 消息的 **field 5** 是值池：每个子项 **field 1** 是文本（UTF-8），
  **field 3** 是数字；
* sheet 消息的 **field 6** 是单元格记录：
  * field 1 = 行号（0-based）
  * field 2 = 列号（0-based）
  * field 3 = payload，payload.field 4.field 1 = 值池下标（0-based）
* 合并单元格会在每个格子上重复写同一个值，所以作业按文本去重。

排刀作业的格式（表格里一个单元格就是一条）：

    B12345 狼 病娇 战狼 军病 八筒 90s
    C45 姬塔 xxtx 晶 爱梅斯 富婆 79s
    D1 紫罗兰 龙妈 白猫 魔女 兰法 4.5

* 开头 `B12345` = B 面 1~5 王都能打；`C45` = C 面 4/5 王；`D1` = D 面 1 王；
* 中间 5 个是角色名（支持 bot 里的全部别名）；
* 末尾带 `s` = 返还秒数；不带 `s` = 伤害（亿）。

这个模块只做「抓 + 解析 + 名字转 ID」，不碰数据库、不登录游戏。
"""

from __future__ import annotations

import base64
import json
import re
import struct
import zlib
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import parse_qs, urlparse

import httpx

from hoshino.modules.priconne import chara
from hoshino.modules.priconne._pcr_data import CHARA_NAME

DOC_HOST = "docs.qq.com"
OPENDOC_API = "https://docs.qq.com/dop-api/opendoc"
REQUEST_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_TIMEOUT = 20.0

# 一条作业：面 + 王编号 + 5 个角色 + 末尾的伤害 / 补偿秒数。
# 末尾可能同时有伤害和补偿时间（如「3.25 60s」），也可能只有其中一个，
# 所以解析时从行尾往前取值，剩下的才是角色名。
BOSS_RE = re.compile(r"^([A-Za-z])([1-5]{1,5})$")
VALUE_RE = re.compile(r"^(\d+(?:\.\d+)?)(亿)?([sS]?)$")

# 表格作者常用的社区缩写。这些不是 bot 角色表里的别名，但含义是确定的：
#   xxtx = 小小甜心（禊&美美&镜华）
#   a花 / a克 = α花（似似花·始源）/ α克（克莉丝提娜·始源）
# 用户还可以在网页端「排刀」设置里继续补充自己的缩写。
DEFAULT_ALIASES: Dict[str, str] = {
    "xxtx": "小小甜心",
    "a花": "α花",
    "a克": "α克",
}


class SheetError(Exception):
    """表格抓取 / 解析失败（带一句能直接给用户看的说明）。"""


@dataclass
class RawEntry:
    """从表格里读出来、还没把角色名转成 ID 的一条作业。

    一条作业可能同时带「伤害」和「补偿时间」，例如：

        D5 水雷姆 机娘 光裁 白菜 水银莲 3.25 60s

    所以伤害和补偿时间分开存，不能把 3.25 当成第 6 个角色名。
    """

    raw: str
    stage: str
    bosses: List[int]
    names: List[str]
    damage: Optional[float] = None
    return_seconds: Optional[float] = None
    row: int = 0
    col: int = 0

    @property
    def value(self) -> float:
        """兼容旧调用：优先返回补偿时间，否则返回伤害。"""
        if self.return_seconds is not None:
            return float(self.return_seconds)
        return float(self.damage or 0.0)

    @property
    def is_return(self) -> bool:
        return self.return_seconds is not None


@dataclass
class ResolvedEntry:
    """角色名已经转成 unit_id 的作业。"""

    raw: str
    stage: str
    bosses: List[int]
    unit_ids: List[int]
    unit_names: List[str]
    unknown_names: List[str]
    damage: Optional[float] = None
    return_seconds: Optional[float] = None
    row: int = 0
    col: int = 0

    @property
    def value(self) -> float:
        if self.return_seconds is not None:
            return float(self.return_seconds)
        return float(self.damage or 0.0)

    @property
    def is_return(self) -> bool:
        return self.return_seconds is not None

    @property
    def valid(self) -> bool:
        """5 个角色都认出来了、而且没有重复，才算一条能用的作业。"""
        return (
            not self.unknown_names
            and len(self.unit_ids) == 5
            and len(set(self.unit_ids)) == 5
        )


# ============================ URL ============================


def parse_sheet_url(url: str) -> Tuple[str, str]:
    """把分享链接拆成 (file_id, tab)。

    只接受 docs.qq.com 的 /sheet/ 链接；tab 可以没有（没有就由腾讯文档决定
    返回哪一页，通常是最前面的可见页签）。
    """
    url = (url or "").strip()
    if not url:
        raise SheetError("表格地址不能为空")
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower().split(":")[0]
    if host != DOC_HOST and not host.endswith("." + DOC_HOST):
        raise SheetError("只支持 docs.qq.com 的腾讯文档表格链接")
    match = re.search(r"/sheet/([A-Za-z0-9]+)", parsed.path or "")
    if not match:
        raise SheetError(
            "链接格式不对，应该像 https://docs.qq.com/sheet/xxxx?tab=yyyy"
        )
    file_id = match.group(1)
    tab = (parse_qs(parsed.query).get("tab") or [""])[0].strip()
    return file_id, tab


# ============================ protobuf ============================


def _read_varint(buf: bytes, index: int) -> Tuple[int, int]:
    value = 0
    shift = 0
    while index < len(buf):
        byte = buf[index]
        index += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, index
        shift += 7
        if shift > 63:
            raise SheetError("protobuf varint 过长")
    raise SheetError("protobuf 数据被截断")


def _parse_fields(buf: bytes) -> List[Tuple[int, int, object]]:
    """最小 protobuf wire 解析：返回 [(field_number, wire_type, value)]。

    wire_type 2 的 value 是 bytes，0 是 int，1/5 是原始 bytes。
    """
    fields: List[Tuple[int, int, object]] = []
    index = 0
    length = len(buf)
    while index < length:
        key, index = _read_varint(buf, index)
        field_number = key >> 3
        wire_type = key & 0x07
        if field_number <= 0:
            raise SheetError("protobuf 字段编号非法")
        if wire_type == 0:
            value, index = _read_varint(buf, index)
        elif wire_type == 1:
            if index + 8 > length:
                raise SheetError("protobuf fixed64 被截断")
            value = buf[index : index + 8]
            index += 8
        elif wire_type == 2:
            size, index = _read_varint(buf, index)
            if index + size > length:
                raise SheetError("protobuf bytes 被截断")
            value = buf[index : index + size]
            index += size
        elif wire_type == 5:
            if index + 4 > length:
                raise SheetError("protobuf fixed32 被截断")
            value = buf[index : index + 4]
            index += 4
        else:
            raise SheetError(f"不支持的 protobuf wire type {wire_type}")
        fields.append((field_number, wire_type, value))
    return fields


def _iter_messages(buf: bytes, depth: int = 0) -> Iterable[List[Tuple[int, int, object]]]:
    """递归产出所有能解析成 protobuf 的嵌套消息的字段列表。"""
    try:
        fields = _parse_fields(buf)
    except SheetError:
        return
    yield fields
    if depth >= 10:
        return
    for field_number, wire_type, value in fields:
        if wire_type != 2 or not isinstance(value, bytes) or len(value) < 2:
            continue
        # 只递归看起来像「字段 key + 数据」的字节串，避免把普通长文本
        # 当成 protobuf 一层层解析（文本里偶尔也能碰巧解析出字段）。
        first = value[0]
        if (first >> 3) <= 0 or (first & 0x07) not in (0, 1, 2, 5):
            continue
        yield from _iter_messages(value, depth + 1)


def _find_sheet_fields(buf: bytes) -> List[Tuple[int, int, object]]:
    """在 related_sheet 的 protobuf 树里找「单元格记录最多」的那层 sheet 消息。"""
    best: Optional[Tuple[int, List[Tuple[int, int, object]]]] = None
    for fields in _iter_messages(buf):
        count = sum(1 for field_number, wire_type, _ in fields if field_number == 6 and wire_type == 2)
        if count and (best is None or count > best[0]):
            best = (count, fields)
    if best is None:
        raise SheetError("表格数据里没有找到单元格")
    return best[1]


def _pool_text(value: bytes) -> str:
    """值池里的一个文本项：通常是 {field 1: text} 的小消息。"""
    try:
        inner = _parse_fields(value)
        texts = [v for field_number, wire_type, v in inner if field_number == 1 and wire_type == 2]
        if texts:
            return texts[0].decode("utf-8", "replace")
    except SheetError:
        pass
    return value.decode("utf-8", "replace")


def _pool_number(value: object, wire_type: int) -> str:
    if wire_type == 1 and isinstance(value, bytes) and len(value) == 8:
        number = struct.unpack("<d", value)[0]
    elif wire_type == 0:
        number = float(value)  # type: ignore[arg-type]
    else:
        return ""
    if float(number).is_integer():
        return str(int(number))
    return f"{number:g}"


def _value_pool(sheet_fields: List[Tuple[int, int, object]]) -> List[str]:
    """取 sheet 的 field 5 值池。

    实测一个 sheet 只有一个 field 5 消息，里面是若干个 {field 1: 文本}；
    个别文档会拆成多个 field 5 消息，取条目最多的那个。
    """
    best: Optional[List[str]] = None
    for field_number, wire_type, value in sheet_fields:
        if field_number != 5 or wire_type != 2 or not isinstance(value, bytes):
            continue
        try:
            inner = _parse_fields(value)
        except SheetError:
            continue
        texts: List[str] = []
        numbers: List[str] = []
        for sub_number, sub_wire_type, sub_value in inner:
            if sub_number == 1 and sub_wire_type == 2 and isinstance(sub_value, bytes):
                texts.append(_pool_text(sub_value))
            elif sub_number == 3 and sub_wire_type in (0, 1):
                number = _pool_number(sub_value, sub_wire_type)
                if number:
                    numbers.append(number)
        # 正常表格的单元格值都是文本（作业本身就是一段文字）；数字池只在
        # 纯数字单元格的文档里出现，作为兜底。
        items = texts if texts else numbers
        if items and (best is None or len(items) > len(best)):
            best = items
    return best or []


def _first_value(
    fields: Sequence[Tuple[int, int, object]], number: int, wire_type: int
) -> Optional[object]:
    for field_number, field_wire_type, value in fields:
        if field_number == number and field_wire_type == wire_type:
            return value
    return None


def _cell_value_index(payload: bytes) -> Optional[int]:
    """从单元格 payload 里取值池下标。

    主流格式：payload.field 4.field 1；少数文档放在 payload.field 2.field 1。
    先找 field 4，找不到再退回 field 2（field 2 也可能只是格式信息，所以放后面）。
    """
    try:
        payload_fields = _parse_fields(payload)
    except SheetError:
        return None
    for target in (4, 2):
        for field_number, wire_type, value in payload_fields:
            if field_number != target or wire_type != 2 or not isinstance(value, bytes):
                continue
            try:
                inner = _parse_fields(value)
            except SheetError:
                continue
            index = _first_value(inner, 1, 0)
            if isinstance(index, int):
                return index
    return None


def _decode_blob(blob: str) -> Dict[Tuple[int, int], str]:
    """base64(zlib(protobuf)) -> {(row, col): text}。"""
    try:
        raw = zlib.decompress(base64.b64decode(blob))
    except Exception as exc:  # noqa: BLE001 - 腾讯文档格式变化时给一句人话
        raise SheetError(f"表格数据解压失败：{exc}") from exc
    sheet_fields = _find_sheet_fields(raw)
    pool = _value_pool(sheet_fields)
    if not pool:
        raise SheetError("表格数据里没有值池")

    cells: Dict[Tuple[int, int], str] = {}
    for field_number, wire_type, cell in sheet_fields:
        if field_number != 6 or wire_type != 2 or not isinstance(cell, bytes):
            continue
        try:
            cell_fields = _parse_fields(cell)
        except SheetError:
            continue
        row = _first_value(cell_fields, 1, 0)
        col = _first_value(cell_fields, 2, 0)
        payload = _first_value(cell_fields, 3, 2)
        if not isinstance(payload, bytes):
            continue
        index = _cell_value_index(payload)
        if index is None or not (0 <= index < len(pool)):
            continue
        text = pool[index]
        if text and text.strip():
            cells[(int(row or 0), int(col or 0))] = text
    return cells


# ============================ 抓取 ============================


def _loads_json(text: str):
    """dop-api 可能返回 JSON，也可能返回 `clientVarsCallback({...})` 形式的 JSONP。"""
    text = (text or "").strip()
    if text.startswith("clientVarsCallback("):
        text = text[len("clientVarsCallback(") :].strip()
        if text.endswith(");"):
            text = text[:-2]
        elif text.endswith(")"):
            text = text[:-1]
    return json.loads(text)


async def fetch_sheet_texts(
    url: str, timeout: float = DEFAULT_TIMEOUT
) -> List[Tuple[int, int, str]]:
    """抓取表格并返回 [(row, col, text)]（只包含非空单元格）。"""
    file_id, tab = parse_sheet_url(url)
    params = {"id": file_id, "normal": "1", "outformat": "1"}
    if tab:
        params["tab"] = tab
    referer = f"https://docs.qq.com/sheet/{file_id}"
    if tab:
        referer += f"?tab={tab}"
    headers = {"User-Agent": REQUEST_UA, "Referer": referer}

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(OPENDOC_API, params=params, headers=headers)
    except httpx.HTTPError as exc:
        raise SheetError(f"连不上腾讯文档：{exc}") from exc

    if response.status_code != 200:
        raise SheetError(f"腾讯文档返回 HTTP {response.status_code}")
    try:
        data = _loads_json(response.text)
    except Exception as exc:  # noqa: BLE001
        raise SheetError("腾讯文档返回的数据不是合法 JSON") from exc

    client_vars = data.get("clientVars") if isinstance(data, dict) else None
    collab = client_vars.get("collab_client_vars") if isinstance(client_vars, dict) else None
    attributed = collab.get("initialAttributedText") if isinstance(collab, dict) else None
    text_items = attributed.get("text") if isinstance(attributed, dict) else None
    if isinstance(text_items, dict):
        text_items = [text_items]
    if not isinstance(text_items, list) or not text_items:
        raise SheetError("腾讯文档没有返回表格内容（可能是链接失效或没有权限）")

    blobs: List[str] = []
    for item in text_items:
        if not isinstance(item, dict):
            continue
        blob = item.get("related_sheet")
        if isinstance(blob, str) and blob:
            blobs.append(blob)
        for block in item.get("block_datas") or []:
            if not isinstance(block, dict):
                continue
            block_blob = block.get("related_sheet")
            if isinstance(block_blob, str) and block_blob:
                blobs.append(block_blob)

    if not blobs:
        raise SheetError("腾讯文档没有返回单元格数据（页签可能不存在或没有权限）")

    merged: Dict[Tuple[int, int], str] = {}
    errors: List[str] = []
    for blob in blobs:
        try:
            merged.update(_decode_blob(blob))
        except SheetError as exc:
            errors.append(str(exc))
    if not merged:
        raise SheetError(errors[0] if errors else "表格里没有读到单元格数据")

    return sorted((row, col, text) for (row, col), text in merged.items())


# ============================ 作业解析 ============================


def _clean_name(token: str) -> str:
    return (token or "").strip().strip("，,。.、;；:：()（）[]【】")


def _chara_name(unit_id: int) -> str:
    names = CHARA_NAME.get(unit_id)
    return names[0] if names else str(unit_id)


def resolve_name(token: str, aliases: Dict[str, str]) -> Optional[int]:
    """把一个角色名 / 别名转成 unit_id；认不出来返回 None。"""
    token = _clean_name(token)
    if not token:
        return None

    candidates: List[str] = []
    mapped = aliases.get(token) or aliases.get(token.lower())
    if mapped:
        mapped = _clean_name(str(mapped))
        if mapped.isdigit():
            unit_id = int(mapped)
            if unit_id in CHARA_NAME:
                return unit_id
        if mapped:
            candidates.append(mapped)
    candidates.append(token)
    # 社区里常把 α（阿尔法）写成英文字母 a：a花 -> α花，a克 -> α克。
    if len(token) > 1 and token[0] in "aA":
        candidates.append("α" + token[1:])

    for candidate in candidates:
        try:
            unit_ids, unknown = chara.roster.parse_team(candidate)
        except Exception:  # noqa: BLE001 - 角色表异常不应该让整个排刀挂掉
            continue
        if len(unit_ids) == 1 and not unknown:
            unit_id = int(unit_ids[0])
            try:
                if chara.is_npc(unit_id):
                    continue
            except Exception:  # noqa: BLE001
                pass
            return unit_id
    return None


def parse_entry_text(text: str) -> Optional[RawEntry]:
    """解析一个单元格里的作业；不是作业就返回 None。

    从行尾往前收集数字：带 s 的是补偿时间，不带 s 的是伤害。
    这样「D5 水雷姆 机娘 光裁 白菜 水银莲 3.25 60s」会解析成
    5 个角色 + 伤害 3.25 + 补偿 60s，而不是把 3.25 当成第 6 个角色。
    """
    normalized = re.sub(r"\s+", " ", (text or "").replace("\u3000", " ")).strip()
    if not normalized:
        return None
    tokens = normalized.split(" ")
    if len(tokens) < 3:
        return None
    boss_match = BOSS_RE.match(tokens[0])
    if not boss_match:
        return None
    stage = boss_match.group(1).upper()
    bosses = sorted({int(char) for char in boss_match.group(2)})
    if not bosses or any(boss < 1 or boss > 5 for boss in bosses):
        return None

    rest = tokens[1:]
    damage: Optional[float] = None
    return_seconds: Optional[float] = None
    while rest:
        value_match = VALUE_RE.match(rest[-1])
        if not value_match:
            break
        number = float(value_match.group(1))
        is_return = bool(value_match.group(3))
        if is_return:
            if return_seconds is None:
                return_seconds = number
        elif damage is None:
            damage = number
        rest.pop()

    if damage is None and return_seconds is None:
        return None
    names = [name for name in rest if name]
    if len(names) < 4:
        return None
    return RawEntry(
        raw=normalized,
        stage=stage,
        bosses=bosses,
        names=names,
        damage=damage,
        return_seconds=return_seconds,
    )


def extract_entries(cells: Sequence[Tuple[int, int, str]]) -> List[RawEntry]:
    """从单元格列表里提取所有作业（按表格顺序、按文本去重）。"""
    entries: List[RawEntry] = []
    seen = set()
    for row, col, text in cells:
        for line in (text or "").splitlines():
            entry = parse_entry_text(line)
            if entry is None:
                continue
            if entry.raw in seen:
                continue
            seen.add(entry.raw)
            entry.row = int(row)
            entry.col = int(col)
            entries.append(entry)
    entries.sort(key=lambda item: (item.row, item.col))
    return entries


def resolve_entries(
    raw_entries: Sequence[RawEntry], aliases: Dict[str, str]
) -> Tuple[List[ResolvedEntry], List[str]]:
    """把作业里的角色名全部转成 unit_id；返回 (作业列表, 没认出来的名字)。"""
    resolved: List[ResolvedEntry] = []
    unknown_all: List[str] = []
    for raw in raw_entries:
        unit_ids: List[int] = []
        unit_names: List[str] = []
        unknown: List[str] = []
        for token in raw.names:
            unit_id = resolve_name(token, aliases)
            if unit_id is None:
                unknown.append(token)
                if token not in unknown_all:
                    unknown_all.append(token)
            else:
                unit_ids.append(unit_id)
                unit_names.append(_chara_name(unit_id))
        resolved.append(
            ResolvedEntry(
                raw=raw.raw,
                stage=raw.stage,
                bosses=list(raw.bosses),
                unit_ids=unit_ids,
                unit_names=unit_names,
                unknown_names=unknown,
                damage=raw.damage,
                return_seconds=raw.return_seconds,
                row=raw.row,
                col=raw.col,
            )
        )
    return resolved, unknown_all


# ============================ 展示用的小工具 ============================


def format_values(
    damage: Optional[float], return_seconds: Optional[float]
) -> str:
    """作业末尾的展示文字：伤害和补偿时间可能同时存在。"""
    parts: List[str] = []
    if damage is not None:
        parts.append(f"{damage:g}亿")
    if return_seconds is not None:
        parts.append(f"{return_seconds:g}s")
    return " · ".join(parts)


def format_value(value: float, is_return: bool) -> str:
    """兼容旧调用：单个值。"""
    if is_return:
        return f"{value:g}s"
    return f"{value:g}亿"


def make_boss_label(stage: str, bosses: Sequence[int]) -> str:
    """和表格里写法一致的标签：B12345 / C45 / D1。"""
    return f"{stage}{''.join(str(boss) for boss in bosses)}"


def make_boss_text(stage: str, bosses: Sequence[int]) -> str:
    """给人看的说明：B面 1-5王 / C面 4王、5王。"""
    if list(bosses) == [1, 2, 3, 4, 5]:
        return f"{stage}面 1-5王"
    return f"{stage}面 " + "、".join(f"{boss}王" for boss in bosses)


def default_aliases() -> Dict[str, str]:
    return dict(DEFAULT_ALIASES)
