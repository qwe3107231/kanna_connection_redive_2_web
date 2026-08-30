from typing import Dict
from urllib.parse import unquote
from re import finditer, match
from base64 import b64decode
from struct import unpack
from random import choice
from ..basedata import Platform

key = b"e806f6"


def _deckey(s: str) -> bytes:
    b = b64decode(unquote(s))
    return bytes(key[i % len(key)] ^ b[i] for i in range(len(b)))


def _decval(k: str, s: str) -> bytes:
    b = b64decode(unquote(s))
    key2 = k.encode("utf8") + key
    b = b[: len(b) - (11 if b[-5] != 0 else 7)]
    return bytes(key2[i % len(key2)] ^ b[i] for i in range(len(b)))


def _ivstring() -> str:
    return "".join([choice("0123456789") for _ in range(32)])


def _encode(dat: str) -> str:
    return (
        f"{len(dat):0>4x}"
        + "".join(
            [
                (chr(ord(dat[int(i / 4)]) + 10) if i %
                 4 == 2 else choice("0123456789"))
                for i in range(len(dat) * 4)
            ]
        )
        + _ivstring()
    )


def decrypt_access_key(content: str) -> str:
    g = match(r'<string name="(.*)">(.*)<(.*)ing>', content).groups()
    return "".join(
        [
            chr(_decval(_deckey(g[0]).decode("utf8"), g[1])[4 * i + 6] - 10)
            for i in range(36)
        ]
    ).replace("-", "")


def decryptxml(content: str, platfrom: int) -> tuple:
    result: Dict[str, str] = {}
    for re in finditer(r'<string name="(.*)">(.*)</string>', content):
        g = re.groups()
        try:
            key = _deckey(g[0]).decode("utf8")
        except Exception:
            continue
        val = _decval(key, g[1])
        if key == "UDID":
            val = "".join([chr(val[4 * i + 6] - 10) for i in range(36)])
        elif "SHORT_UDID" in key:
            result["viewer_id"] = key.replace("SHORT_UDID", "")
            key = "SHORT_UDID"
            val = _encode(str(val))
        elif len(val) == 4:
            val = str(unpack("i", val)[0])
        result[key] = val

    return (
        (result["UDID"].replace("-", ""), result["viewer_id"])
        if platfrom == Platform.qu_id.value
        else (
            result["UDID"],
            result["SHORT_UDID"],
            result["VIEWER_ID"],
            result["TW_SERVER_ID"],
        )
    )
