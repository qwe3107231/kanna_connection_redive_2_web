import asyncio
import contextlib
import json
import time
import hashlib
from typing import Dict, Optional, Tuple
import urllib
from loguru import logger
import httpx
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5 as Cipher_pkcs1_v1_5
import base64
from ..util.tools import load_config
from ..basedata import FilePath
from ..errorclass import (
    NeedCaptchError,
    PassCaptchError,
    PasswordError,
    RiskControlError,
    UnknowError,
)
from ...multicq_send import private_send

TIMEOUT = 20

bililogin = "https://line1-sdk-center-login-sh.biligame.net/"

header = {
    "User-Agent": "Mozilla/5.0 BSGameSDK",
    "Content-Type": "application/x-www-form-urlencoded",
    "Host": "line1-sdk-center-login-sh.biligame.net",
}

modolrsa = '{"operators":"5","merchant_id":"1","isRoot":"0","domain_switch_count":"0","sdk_type":"1","sdk_log_type":"1","timestamp":"1613035485639","support_abis":"x86,armeabi-v7a,armeabi","access_key":"","sdk_ver":"3.4.2","oaid":"","dp":"1280*720","original_domain":"","imei":"227656364311444","version":"1","udid":"KREhESMUIhUjFnJKNko2TDQFYlZkB3cdeQ==","apk_sign":"e89b158e4bcf988ebd09eb83f5378e87","platform_type":"3","old_buvid":"XZA2FA4AC240F665E2F27F603ABF98C615C29","android_id":"84567e2dda72d1d4","fingerprint":"","mac":"08:00:27:53:DD:12","server_id":"1592","domain":"line1-sdk-center-login-sh.biligame.net","app_id":"1370","version_code":"90","net":"4","pf_ver":"6.0.1","cur_buvid":"XZA2FA4AC240F665E2F27F603ABF98C615C29","c":"1","brand":"Android","client_timestamp":"1613035486888","channel_id":"1","uid":"","game_id":"1370","ver":"2.4.10","model":"MuMu"}'
modollogin = '{"operators":"5","merchant_id":"1","isRoot":"0","domain_switch_count":"0","sdk_type":"1","sdk_log_type":"1","timestamp":"1613035508188","support_abis":"x86,armeabi-v7a,armeabi","access_key":"","sdk_ver":"3.4.2","oaid":"","dp":"1280*720","original_domain":"","imei":"227656364311444","gt_user_id":"fac83ce4326d47e1ac277a4d552bd2af","seccode":"","version":"1","udid":"KREhESMUIhUjFnJKNko2TDQFYlZkB3cdeQ==","apk_sign":"e89b158e4bcf988ebd09eb83f5378e87","platform_type":"3","old_buvid":"XZA2FA4AC240F665E2F27F603ABF98C615C29","android_id":"84567e2dda72d1d4","fingerprint":"","validate":"84ec07cff0d9c30acb9fe46b8745e8df","mac":"08:00:27:53:DD:12","server_id":"1592","domain":"line1-sdk-center-login-sh.biligame.net","app_id":"1370","pwd":"rxwA8J+GcVdqa3qlvXFppusRg4Ss83tH6HqxcciVsTdwxSpsoz2WuAFFGgQKWM1+GtFovrLkpeMieEwOmQdzvDiLTtHeQNBOiqHDfJEKtLj7h1nvKZ1Op6vOgs6hxM6fPqFGQC2ncbAR5NNkESpSWeYTO4IT58ZIJcC0DdWQqh4=","version_code":"90","net":"4","pf_ver":"6.0.1","cur_buvid":"XZA2FA4AC240F665E2F27F603ABF98C615C29","c":"1","brand":"Android","client_timestamp":"1613035509437","channel_id":"1","uid":"","captcha_type":"1","game_id":"1370","challenge":"efc825eaaef2405c954a91ad9faf29a2","user_id":"doo349","ver":"2.4.10","model":"MuMu"}'
modolcaptch = '{"operators":"5","merchant_id":"1","isRoot":"0","domain_switch_count":"0","sdk_type":"1","sdk_log_type":"1","timestamp":"1613035486182","support_abis":"x86,armeabi-v7a,armeabi","access_key":"","sdk_ver":"3.4.2","oaid":"","dp":"1280*720","original_domain":"","imei":"227656364311444","version":"1","udid":"KREhESMUIhUjFnJKNko2TDQFYlZkB3cdeQ==","apk_sign":"e89b158e4bcf988ebd09eb83f5378e87","platform_type":"3","old_buvid":"XZA2FA4AC240F665E2F27F603ABF98C615C29","android_id":"84567e2dda72d1d4","fingerprint":"","mac":"08:00:27:53:DD:12","server_id":"1592","domain":"line1-sdk-center-login-sh.biligame.net","app_id":"1370","version_code":"90","net":"4","pf_ver":"6.0.1","cur_buvid":"XZA2FA4AC240F665E2F27F603ABF98C615C29","c":"1","brand":"Android","client_timestamp":"1613035487431","channel_id":"1","uid":"","game_id":"1370","ver":"2.4.10","model":"MuMu"}'
token_config: dict = load_config(str(FilePath.data.value / "token.json"))
gt_lulu_token = token_config.get("lulu_token", "")
gt_ellye_token = token_config.get("ellye_token", "")
gt_wait = 90
lulu_public = True


def rsacreate(message: str, public_key: str) -> str:
    cipher = Cipher_pkcs1_v1_5.new(
        RSA.importKey(public_key)
    )  # 创建用于执行pkcs1_v1_5加密或解密的密码
    return base64.b64encode(cipher.encrypt(message.encode("utf-8"))).decode("utf-8")


async def sendpost(url: str, data: dict) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        return (await client.post(url=url, data=data, headers=header)).json()


def setsign(data: Dict[str, str]) -> str:
    data["timestamp"] = int(time.time())
    data["client_timestamp"] = int(time.time())
    result = f"pwd={urllib.parse.quote(data['pwd'])}&" if "pwd" in data else ""
    result += "".join([f"{key}={data[key]}&" for key in data])
    sign = (
        "".join([f"{data[key]}" for key in sorted(data)])
        + "fe8aac4e02f845b8ad67c427d48bfaf1"
    )
    result += f"sign={hashlib.md5(sign.encode()).hexdigest()}"
    return result


async def try_login(
    account: str,
    password: str,
    challenge: Optional[str] = "",
    gt_user: Optional[str] = "",
    validate: Optional[str] = "",
) -> Tuple[str]:
    rsa = await sendpost(f"{bililogin}api/client/rsa", setsign(json.loads(modolrsa)))
    data = json.loads(modollogin)
    public_key = rsa["rsa_key"]
    data["access_key"] = ""
    data["gt_user_id"] = gt_user
    data["uid"] = ""
    data["challenge"] = challenge
    data["user_id"] = account
    data["validate"] = validate
    if validate:
        data["seccode"] = f"{validate}|jordan"
    data["pwd"] = rsacreate(rsa["hash"] + password, public_key)
    res = await sendpost(f"{bililogin}api/client/login", setsign(data))
    if res.get("message", "") == "用户名或密码错误":
        raise PasswordError("用户名或密码错误")
    if res["code"] == 200000:
        raise NeedCaptchError
    if res["code"] == 200001:
        raise PassCaptchError
    if res["code"] == 500053:
        raise RiskControlError
    if "access_key" in res:
        return res["uid"], res["access_key"]
    logger.error(str(res))
    raise UnknowError("未知错误")


async def make_captch(gt: str, challenge: str, user_id: str, qq_id: int) -> dict:
    if gt_lulu_token:
        try:
            logger.info("使用路路自动过码")
            return await lulu_captch(gt, challenge, user_id)
        except Exception as e:
            logger.warning(f"路路自动过码失败{str(e)}")
    if gt_ellye_token:
        try:
            logger.info("使用怡宝自动过码")
            return await ellye_captch()
        except Exception as e:
            logger.warning(f"怡宝自动过码失败{str(e)}")
    if lulu_public:
        try:
            logger.info("使用路路公用自动过码")
            return await lulu_public_captch(gt, challenge, user_id)
        except Exception as e:
            logger.warning(f"路路自动过码失败{str(e)}")

    logger.info("寄了，使用手动过码")
    return await manual_captch(challenge, gt, user_id, qq_id)


async def lulu_captch(
    gt: str,
    challenge: str,
    user_id: str,
) -> str:
    try:
        async with httpx.AsyncClient(timeout=30) as AsyncClient:
            res = await AsyncClient.get(
                f"https://api.fuckmys.tk/geetest?token={gt_lulu_token}&gt={gt}&challenge={challenge}"
            )
            res = res.json()
            # print(res)
            if res.get("code", -1) != 0:
                raise PassCaptchError(f"{res}")
            return {
                "challenge": challenge,
                "gt_user_id": user_id,
                "validate": res["data"]["validate"],
            }
    except httpx.HTTPError:
        raise
    except Exception as e:
        raise PassCaptchError(f"自动过码异常：{e}") from e


async def lulu_public_captch(gt, challenge, userid):
    async with httpx.AsyncClient(timeout=30) as AsyncClient:
        try:
            res = await AsyncClient.get(
                url=f"https://pcrd.tencentbot.top/geetest_renew?captcha_type=1&challenge={challenge}&gt={gt}&userid={userid}&gs=1",
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "pcrjjc2/1.0.0",
                },
            )
            res = res.json()
            uuid = res["uuid"]
            for _ in range(10):
                res = await AsyncClient.get(
                    url=f"https://pcrd.tencentbot.top/check/{uuid}",
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "pcrjjc2/1.0.0",
                    },
                )
                res = res.json()

                if "queue_num" in res:
                    tim = min(int(res["queue_num"]), 3) * 10
                    logger.info(
                        f"过码排队，当前有{res['queue_num']}个在前面，等待{tim}s"
                    )
                    await asyncio.sleep(tim)
                    continue

                info = res["info"]
                if "validate" in info:
                    return {
                        "challenge": info["challenge"],
                        "gt_user_id": info["gt_user_id"],
                        "validate": info["validate"],
                    }
                if res["info"] in ["fail", "url invalid"]:
                    raise PassCaptchError(f"{res}")
                if res["info"] == "in running":
                    logger.info("正在过码。等待5s")
                    await asyncio.sleep(5)

            raise PassCaptchError("自动过码多次失败")

        except Exception as e:
            raise PassCaptchError(f"自动过码异常，{e}") from e


async def ellye_captch():
    """
    怡宝自动过码模块
    """

    try:
        async with httpx.AsyncClient() as client:
            url = f"https://:{gt_ellye_token}@captcha-api.bot.hwmoe.com/geetest-captcha/validate"
            response = await client.get(url, timeout=60)
            response.raise_for_status()
            res = response.json()
            assert res.get("code", -1) == 0, str(res)
            return {
                "challenge": res["data"]["challenge"],
                "gt_user_id": res["data"]["gt_user"],
                "validate": res["data"]["validate"],
            }
    except Exception as e:
        raise PassCaptchError(f"自动过码异常，{e}") from e


async def manual_captch_listener(user_id: str):
    url = f"https://captcha.ellye.cn/api/block?userid={user_id}"
    while True:
        async with httpx.AsyncClient() as client:
            with contextlib.suppress(httpx.TimeoutException):
                response = await client.get(url, timeout=28)
                if response.status_code == 200:
                    res = response.json()
                    return res["validate"]
                else:
                    logger.warning(f"手动过码异常,返回{response.text}")


async def manual_captch(challenge: str, gt: str, user_id: str, qqid: int) -> dict:
    """
    怡宝手动过码模块

    Args:
        challenge (str): 程序生成
        gt (str): 程序生成
        userId (str): 程序生成
        qqid (int): 发送验证链接。

    Raises:
        Exception: 向[qqid]私发过码验证消息失败，可能尚未添加好友。
        Exception: 其它异常（超时等）

    Returns:
        str: 过码结果字典
    """

    url = f"https://captcha.ellye.cn/?captcha_type=1&challenge={challenge}&gt={gt}&userid={user_id}&gs=1"
    await private_send(
        qqid, f"pcr账号登录触发验证码，请在{gt_wait}秒内完成以下链接中的验证内容。"
    )
    await private_send(qqid, url)

    try:
        return {
            "challenge": challenge,
            "gt_user_id": user_id,
            "validate": await asyncio.wait_for(
                manual_captch_listener(user_id), gt_wait
            ),
        }
    except asyncio.TimeoutError as e:
        await private_send(qqid, "手动过码获取结果超时")
        raise RuntimeError("手动过码获取结果超时") from e
    except Exception as e:
        await private_send(qqid, f"手动过码获取结果异常：{e}")
        raise


async def get_access_key(bili_account: str, bili_pwd: str, qq_id: int) -> Tuple[str]:
    logger.info(f"logging in with acc={bili_account}, pwd={bili_pwd}")
    try:
        return await try_login(bili_account, bili_pwd)
    except NeedCaptchError:
        logger.info("需要验证码，尝试过码")
        cap = await sendpost(
            f"{bililogin}api/client/start_captcha",
            setsign(json.loads(modolcaptch)),
        )
        validate = await make_captch(
            cap["gt"], cap["challenge"], cap["gt_user_id"], qq_id
        )
        return await try_login(
            bili_account,
            bili_pwd,
            validate["challenge"],
            validate["gt_user_id"],
            validate["validate"],
        )
