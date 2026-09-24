from typing import Optional
from sqlmodel import Field, SQLModel
import time

from sqlalchemy.orm import registry

# 防止多个sqlmodel冲突


class DataBase(SQLModel, registry=registry()):
    pass


class Account(DataBase, table=True):
    """游戏账号绑定

    表结构上按 group_id 区分（一个 QQ 可以有多行）：
      - group_id = 0  →「全局号」，QQ 私聊【绑定账号】绑的，任何群都能用；
      - group_id = N  →「本群号」，只在第 N 个群里生效。

    2026-09-20 起**网页端只写 group_id = 0**：用户明确废弃了「本群专用号」
    （换公会还要重绑，纯属多余）。所以 N 行只剩历史数据，不会再产生新行；
    DAL 里的按群取值逻辑保留不动（零迁移风险，QQ 私聊侧语义未变）。

    注意：group_id 是后来加的列，老库里的历史数据会落成 0（即全局号），
    与「私聊绑定」的语义正好一致，不会改变原有行为。
    实际补列由 dal.SQALA.create_all 里的幂等迁移完成 —— SQLModel 的
    create_all 只建表不改表，光加字段定义是拿不到列的。
    """

    __table_args__ = {"keep_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True, title="序号")
    user_id: int = Field(title="玩家QQ")
    group_id: int = Field(default=0, title="归属群")
    platform: int = Field(title="服务器编号")
    viewer_id: Optional[int] = Field(default=None, title="游戏ID")
    allow_others: Optional[int] = Field(default=0, title="允许他人触发")
    account: Optional[str] = Field(default=None, title="uid")
    password: Optional[str] = Field(default=None, title="access_key")
    name: Optional[str] = Field(default=None, title="游戏昵称")
    refresh: Optional[str] = Field(default=None, title="b站账号")


class WebAccount(DataBase, table=True):
    __table_args__ = {"keep_existing": True}
    account: str = Field(primary_key=True, title="玩家账号")
    password: str = Field(title="密码")
    temp: Optional[bool] = Field(title="临时", default=True)
    priority: Optional[int] = Field(title="权限等级", default=0)
    create_time: Optional[int] = Field(title="过期时间", default=0)


class RefreshAccount(DataBase, table=True):
    __table_args__ = {"keep_existing": True}
    account: str = Field(primary_key=True, title="b站账号")
    password: str = Field(title="b站密码")


class RecordDao(DataBase, table=True):
    __table_args__ = {"keep_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True, title="序号")
    group_id: int = Field(title="所属群")
    battle_log_id: int = Field(title="出刀编号")
    lap: int = Field(title="周目")
    boss: int = Field(title="boss编号")
    time: int = Field(title="时间")
    pcrid: int = Field(title="玩家ID")
    damage: int = Field(title="伤害")
    name: str = Field(title="玩家昵称")
    remain_time: int = Field(title="战斗剩余时间")
    battle_time: int = Field(title="战斗时间")
    flag: float = Field(title="出刀类型")
    unit1: int = Field(title="出战角色1-ID")
    unit2: Optional[int] = Field(default=0, title="出战角色2-ID")
    unit3: Optional[int] = Field(default=0, title="出战角色3-ID")
    unit4: Optional[int] = Field(default=0, title="出战角色4-ID")
    unit5: Optional[int] = Field(default=0, title="出战角色5-ID")
    unit1_level: int = Field(title="出战角色1-等级")
    unit2_level: Optional[int] = Field(default=0, title="出战角色2-等级")
    unit3_level: Optional[int] = Field(default=0, title="出战角色3-等级")
    unit4_level: Optional[int] = Field(default=0, title="出战角色4-等级")
    unit5_level: Optional[int] = Field(default=0, title="出战角色5-等级")
    unit1_damage: int = Field(title="出战角色1-伤害")
    unit2_damage: Optional[int] = Field(default=0, title="出战角色2-伤害")
    unit3_damage: Optional[int] = Field(default=0, title="出战角色3-伤害")
    unit4_damage: Optional[int] = Field(default=0, title="出战角色4-伤害")
    unit5_damage: Optional[int] = Field(default=0, title="出战角色5-伤害")
    unit1_rarity: int = Field(title="出战角色1-星级")
    unit2_rarity: Optional[int] = Field(default=0, title="出战角色2-星级")
    unit3_rarity: Optional[int] = Field(default=0, title="出战角色3-星级")
    unit4_rarity: Optional[int] = Field(default=0, title="出战角色4-星级")
    unit5_rarity: Optional[int] = Field(default=0, title="出战角色5-星级")
    unit1_rank: int = Field(title="出战角色1-品级")
    unit2_rank: Optional[int] = Field(default=0, title="出战角色2-品级")
    unit3_rank: Optional[int] = Field(default=0, title="出战角色3-品级")
    unit4_rank: Optional[int] = Field(default=0, title="出战角色4-品级")
    unit5_rank: Optional[int] = Field(default=0, title="出战角色5-品级")
    unit1_unique_equip: int = Field(title="出战角色1-专武等级")
    unit2_unique_equip: Optional[int] = Field(default=0, title="出战角色2-专武等级")
    unit3_unique_equip: Optional[int] = Field(default=0, title="出战角色3-专武等级")
    unit4_unique_equip: Optional[int] = Field(default=0, title="出战角色4-专武等级")
    unit5_unique_equip: Optional[int] = Field(default=0, title="出战角色5-专武等级")


class NoticeCache(DataBase, table=True):
    __table_args__ = {"keep_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True, title="序号")
    group_id: int = Field(title="所属群")
    notice_type: int = Field(title="通知类型")
    user_id: int = Field(title="用户QQ")
    boss: int = Field(title="Boss编号")
    lap: Optional[int] = Field(default=0, title="周目")
    text: str = Field(title="留言")
    time: Optional[int] = Field(default=0, title="时间")


class SLDao(DataBase, table=True):
    __table_args__ = {"keep_existing": True}
    group_id: int = Field(primary_key=True, title="所属群")
    user_id: int = Field(primary_key=True, title="用户QQ")
    time: Optional[int] = Field(default=0, title="上次SL")


class ClanBattleKPI(DataBase, table=True):
    __table_args__ = {"keep_existing": True}
    group_id: int = Field(primary_key=True, title="所属群")
    pcrid: int = Field(primary_key=True, title="游戏ID")
    bouns: int = Field(title="补正")
    time: Optional[int] = Field(default=0, title="创建时间")


class PlayerUnit(DataBase, table=True):
    __table_args__ = {"keep_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True, title="序号")
    user_id: int = Field(title="玩家QQ")
    pcrid: int = Field(title="玩家ID")
    unit_id: int = Field(title="角色ID")
    name: str = Field(title="玩家昵称")
    rarity: int = Field(title="星级")
    battle_rarity: Optional[int] = Field(default=0, title="战斗星级")
    unique_level: Optional[int] = Field(default=0, title="专武等级")
    unique_level2: Optional[int] = Field(default=0, title="专武等级2")
    love_level: int = Field(title="好感等级")
    level: int = Field(title="等级")
    rank: int = Field(title="品级")
    main_1: Optional[int] = Field(default=0, title="1技能")
    main_2: Optional[int] = Field(default=0, title="2技能")
    ex: Optional[int] = Field(default=0, title="ex技能")
    union_burst: Optional[int] = Field(default=0, title="连结爆发")
    equip_1: str = Field(title="左上")
    equip_2: str = Field(title="右上")
    equip_3: str = Field(title="左中")
    equip_4: str = Field(title="右中")
    equip_5: str = Field(title="左下")
    equip_6: str = Field(title="右下")
    support_position: Optional[int] = Field(
        default=0, title="支援位置"
    )  # 1, 2 好友支援， 3-6 工会战地下城支援
    cb_ex_equip_1: Optional[int] = Field(default=0, title="会战ex装备1")
    cb_ex_equip_2: Optional[int] = Field(default=0, title="会战ex装备2")
    cb_ex_equip_3: Optional[int] = Field(default=0, title="会战ex装备3")
    cb_ex_equip_1_level: Optional[int] = Field(default=0, title="会战ex装备1等级")
    cb_ex_equip_2_level: Optional[int] = Field(default=0, title="会战ex装备2等级")
    cb_ex_equip_3_level: Optional[int] = Field(default=0, title="会战ex装备3等级")


class SupportUnit(DataBase, table=True):
    __table_args__ = {"keep_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True, title="序号")
    group_id: int = Field(title="所属群")
    pcrid: int = Field(title="玩家ID")
    unit_id: int = Field(title="角色ID")
    name: str = Field(title="玩家昵称")
    rarity: int = Field(title="星级")
    battle_rarity: Optional[int] = Field(default=0, title="战斗星级")
    unique_level: Optional[int] = Field(default=0, title="专武等级")
    unique_level2: Optional[int] = Field(default=0, title="专武等级2")
    special_attribute: Optional[str] = Field(default="", title="好感加成")
    level: int = Field(title="等级")
    rank: int = Field(title="品级")
    main_1: Optional[int] = Field(default=0, title="1技能")
    main_2: Optional[int] = Field(default=0, title="2技能")
    ex: Optional[int] = Field(default=0, title="ex技能")
    union_burst: Optional[int] = Field(default=0, title="连结爆发")
    equip_1: str = Field(title="左上")
    equip_2: str = Field(title="右上")
    equip_3: str = Field(title="左中")
    equip_4: str = Field(title="右中")
    equip_5: str = Field(title="左下")
    equip_6: str = Field(title="右下")
    cb_ex_equip_1: Optional[int] = Field(default=0, title="会战ex装备1")
    cb_ex_equip_2: Optional[int] = Field(default=0, title="会战ex装备2")
    cb_ex_equip_3: Optional[int] = Field(default=0, title="会战ex装备3")
    cb_ex_equip_1_level: Optional[int] = Field(default=0, title="会战ex装备1等级")
    cb_ex_equip_2_level: Optional[int] = Field(default=0, title="会战ex装备2等级")
    cb_ex_equip_3_level: Optional[int] = Field(default=0, title="会战ex装备3等级")


class ClanBattleMember(DataBase, table=True):
    __table_args__ = {"keep_existing": True}
    group_id: int = Field(primary_key=True, title="所属群")
    user_id: int = Field(primary_key=True, title="玩家QQ")
    group_name: str = Field(title="群名称", default="环奈连结")
    priority: Optional[int] = Field(title="权限等级", default=0)


class GroupSetting(DataBase, table=True):
    """群级设置（**按群独立**，一个群一行）

    目前只有「主动推送」一个开关：出刀监控跑起来之后，bot 会主动往群里播报
    出刀人数 / 出刀伤害 / 预约 / 挂树这些消息，群里嫌吵可以用【关闭推送】关掉。
    开关只影响本群，别的群不受影响。

    **默认开启**：表里没有该群的行 = 开启（只有关过一次才会落行）。
    """

    __table_args__ = {"keep_existing": True}
    group_id: int = Field(primary_key=True, title="所属群")
    push_enabled: bool = Field(default=True, title="主动推送")


class BlackUnit(DataBase, table=True):
    __table_args__ = {"keep_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True, title="序号")
    user_id: int = Field(title="玩家QQ")
    black_id: str = Field(title="黑名单id")
    black_type: int = Field(title="黑名单类型")


class ArenaSetting(DataBase, table=True):
    __table_args__ = {"keep_existing": True}
    user_id: int = Field(primary_key=True, title="玩家QQ")
    jjc_notice: bool = Field(default=True, title="竞技场提醒")
    grand_notice: bool = Field(default=True, title="公主竞技场提醒")


class GrandDefenceCache(DataBase, table=True):
    __table_args__ = {"keep_existing": True}
    pcrid: int = Field(primary_key=True, title="玩家ID")
    grand_id: int = Field(title="场次")
    defence: str = Field(title="防守队伍id")
    row: int = Field(primary_key=True, title="防守位置")
    user_id: int = Field(primary_key=True, title="玩家QQ")
    vs_time: int = Field(default=0, title="更新时间")


class CookieCache(DataBase, table=True):
    """网页端登录态（token）

    注意 time 必须用 default_factory，**不能**写成 `default=int(time.time())`：
    后者在类定义（模块 import）时就把时间戳算死了，之后每次新建实例拿到的都是
    同一个「机器人启动那一刻」的值。于是只要机器人连续跑够 7 天，之后签发的每一个
    token 一出生就是过期的 —— 登录接口那边会直接回「登录过期」，而且是必现、无解的那种。
    """

    __table_args__ = {"keep_existing": True}
    token: str = Field(primary_key=True, title="token")
    user_id: str = Field(title="user_id")
    time: int = Field(default_factory=lambda: int(time.time()), title="时间")


class RankLineCache(DataBase, table=True):
    """会战档线缓存（落本地库，重启不丢）

    为什么要缓存：档线是「全服排名」数据，游戏侧每半小时才更新一次，但查一次
    要打十几次 period_ranking 分页请求（默认 14 个档位 = 13 个分页，再加「末位
    二分搜索」十来次），而且 `_safe_period_ranking` 连续失败到上限会禁用查档线功能、
    还要重登一次来救监控会话。所以能不打就不打。

    主键里的 clan_battle_id 是关键：换届之后编号变了，上一届的缓存自然不命中，
    不需要额外的过期清理逻辑。

    ranks_key 是归一化后的档位签名（排序去重后逗号拼接），默认档位和用户自定义
    的档位各占一行，互不覆盖。
    """

    __table_args__ = {"keep_existing": True}
    group_id: int = Field(primary_key=True, title="所属群")
    clan_battle_id: int = Field(primary_key=True, title="会战编号")
    ranks_key: str = Field(primary_key=True, title="档位签名")
    payload: str = Field(title="JSON 结果")
    updated_at: int = Field(
        default_factory=lambda: int(time.time()), title="抓取时间"
    )


class DeepDomainCache(DataBase, table=True):
    """公会深域进度缓存（按群一行，落本地库，重启不丢）

    为什么要缓存：查一次深域要**给公会里每个人**打一次 profile_get（30 人 = 30 次
    请求），而这条数据只有「出刀监控的 client 已经登录着」的时候才敢去抓 ——
    监控没在跑的时候账号很可能正被群友自己登录着，`login.query()` 里的
    `check_client` 一旦失败就会重新 `client.login()`，把人**顶下线**。

    所以：监控在跑 → 抓最新并落库；监控没跑 → 只读这张表，一次游戏接口都不打。
    `updated_at` 会显示在图片标题栏上（「数据时间」），让看到的人知道这份数据有多旧。

    主键只有 group_id：出刀监控是按群起的，群就是这份数据的归属单位。

    `clan_id` 是**游戏内公会 ID**，专门用来发现「这个群换公会了」：
    监控没开时拿不到当前公会 ID，没法在读取路径上判断，所以只在
    【开启出刀监控】时（`clan_info.init()` 刚设好 clan_id）比对一次，
    对不上就把这份缓存作废（见 `dal.clear_deep_domain_cache_if_clan_changed`）。
    不换会时它永远不触发，所以不会白白清掉「重启监控后仍可用」的缓存。
    """

    __table_args__ = {"keep_existing": True}
    group_id: int = Field(primary_key=True, title="所属群")
    payload: str = Field(title="JSON 结果")
    clan_id: int = Field(default=0, title="游戏内公会 ID")
    updated_at: int = Field(
        default_factory=lambda: int(time.time()), title="抓取时间"
    )
