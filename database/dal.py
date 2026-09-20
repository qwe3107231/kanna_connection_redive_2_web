import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Union

from sqlalchemy import asc, delete, desc, insert, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, func

from ..basedata import FilePath, NoticeType
from .models import (
    Account,
    ArenaSetting,
    ClanBattleKPI,
    ClanBattleMember,
    CookieCache,
    DataBase,
    GrandDefenceCache,
    GroupSetting,
    NoticeCache,
    PlayerUnit,
    RankLineCache,
    RecordDao,
    RefreshAccount,
    SLDao,
    SupportUnit,
    WebAccount,
)

# 老库补列清单：(表名, 列名, 列定义)
# 加字段时在这里补一条，剩下的交给 SQALA._run_migrations 幂等执行。
_COLUMN_MIGRATIONS = [
    # 游戏账号的归属群（0 = 全局号，即 QQ 私聊绑定的那个）
    ("account", "group_id", "INTEGER NOT NULL DEFAULT 0"),
]


def pcr_date(timeStamp: int) -> datetime:
    now = datetime.fromtimestamp(timeStamp, tz=timezone(timedelta(hours=8)))
    if now.hour < 5:
        now -= timedelta(days=1)
    return now.replace(hour=5, minute=0, second=0, microsecond=0)  # 用5点做基准


class SQALA:
    def __init__(self, url: str):
        self.url = f"sqlite+aiosqlite:///{url}"
        self.engine = create_async_engine(
            self.url,
            pool_recycle=1500,  # 连接回收时间
            pool_pre_ping=True,  # 使用前检查连接是否有效
            echo=False,  # 关闭 SQL 日志减少内存
        )
        self.async_session = sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )

    async def refresh(self, table: SQLModel, day: int, group_id: Optional[int] = 0):
        async with self.async_session() as session:
            async with session.begin():
                date = pcr_date(datetime.now().timestamp())
                time = date - timedelta(days=day)
                sql = delete(table).where(table.time < time.timestamp())
                if group_id:
                    sql = sql.filter(table.group_id == group_id)
                await session.execute(sql)

    async def create_all(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(DataBase.metadata.create_all)
            # create_all 只负责「建缺失的表」，对已存在的表一个字段都不会改
            # （__table_args__ 里的 keep_existing=True 也只是「别动它」）。
            # 所以给老表加字段必须自己来，见 _run_migrations。
            await conn.run_sync(self._run_migrations)

    @staticmethod
    def _run_migrations(conn):
        """幂等补列：让老库也能拿到新加的字段。

        做法是「先问再改」——用 PRAGMA table_info 看列在不在，不在才 ALTER。
        所以每次启动都跑一遍是安全的，重复执行不会报错、也不会重置已有数据。

        新增字段时往 _COLUMN_MIGRATIONS 里加一条即可。
        """
        for table, column, ddl in _COLUMN_MIGRATIONS:
            info = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
            if not info:
                # 表还不存在（理论上 create_all 刚建过，这里只是兜底）
                continue
            if any(row[1] == column for row in info):
                continue
            conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    # 账号部分
    async def query_account(self, user_id: int) -> List[Account]:
        """某个 QQ 名下的全部游戏账号（含各群单独绑定的）

        按 group_id 升序排，全局号（group_id=0）永远在最前面 —— 老代码里那些
        `query_account(qq_id)[0]` 因此仍然优先拿到全局号，行为不变。
        """
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(Account)
                    .where(Account.user_id == user_id)
                    .order_by(asc(Account.group_id))
                )
                return result.scalars().all()

    async def query_account_for_group(
        self, user_id: int, group_id: int
    ) -> Optional[Account]:
        """按群取号：本群绑定的优先，本群没绑就回退到全局号（group_id=0）

        这是「按群绑定」的核心取值规则：在 A 群绑的号只在 A 群生效；
        没在某个群单独绑过的人，则沿用他 QQ 私聊绑的全局号。
        """
        group_id = int(group_id)
        accounts = await self.query_account(user_id)
        for account in accounts:
            if int(account.group_id) == group_id:
                return account
        for account in accounts:
            if int(account.group_id) == 0:
                return account
        return None

    async def query_accounts_for_group(
        self, user_id: int, group_id: int
    ) -> List[Account]:
        """本群号 + 全局号（本群在前，全局在后），供「可选账号」类下拉使用

        和 query_account_for_group 的区别：那个只返回一个（本群优先、回退全局），
        这个把两者都给出来让用户自己挑 —— 本群绑了大号、全局绑了小号的情况，
        开监控时想用小号也说得过去。
        """
        group_id = int(group_id)
        accounts = await self.query_account(user_id)
        mine = [a for a in accounts if int(a.group_id) == group_id]
        global_ = [a for a in accounts if int(a.group_id) == 0]
        return mine + global_

    async def add_account(self, user_id: int, account: dict, group_id: int = 0):
        """按 (user_id, group_id) 新增或更新一条绑定

        group_id 默认 0（全局号），所以 QQ 端【绑定账号】系列指令的行为完全不变。
        同一个 QQ 在不同群里绑不同账号会各占一行，互不影响。
        """
        group_id = int(group_id)
        values = {k: v for k, v in account.items() if k != "id"}
        values["user_id"] = int(user_id)
        # 覆盖成本次 upsert 的目标群，防止调用方传进来的值不一致
        values["group_id"] = group_id
        async with self.async_session() as session:
            async with session.begin():
                exists = await session.execute(
                    select(Account.id).where(
                        Account.user_id == user_id, Account.group_id == group_id
                    )
                )
                if exists.first() is not None:
                    await session.execute(
                        update(Account)
                        .where(
                            Account.user_id == user_id, Account.group_id == group_id
                        )
                        .values(**values)
                    )
                else:
                    await session.execute(insert(Account).values(**values))

    async def delete_account(self, user_id: int, group_id: int) -> int:
        """解绑某人在某群（group_id=0 则是全局）的游戏账号，返回删掉的条数"""
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    delete(Account).where(
                        Account.user_id == user_id, Account.group_id == int(group_id)
                    )
                )
                return result.rowcount or 0

    async def change_access(self, user_id: int, level: int):
        async with self.async_session() as session:
            async with session.begin():
                await session.execute(
                    update(Account)
                    .where(Account.user_id == user_id)
                    .values(allow_others=level)
                )

    async def query_refresh(self, account: str) -> RefreshAccount:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(RefreshAccount).where(RefreshAccount.account == account)
                )
                return result.scalar_one_or_none()

    async def add_refresh(self, account: RefreshAccount):
        async with self.async_session() as session:
            async with session.begin():
                await session.merge(account)

    # 会战部分
    async def add_record(self, dao_list: List[RecordDao]):
        async with self.async_session() as session:
            async with session.begin():
                session.add_all(dao_list)

    async def get_history(self, id: int, group_id: int) -> RecordDao:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(RecordDao).where(
                        RecordDao.battle_log_id == id, RecordDao.group_id == group_id
                    )
                )
                return result.scalars().one_or_none()

    async def get_latest_time(self, group_id: int) -> int:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(func.max(RecordDao.time)).where(
                        RecordDao.group_id == group_id
                    )
                )
                return result.fetchone()[0] or 0

    async def get_player_records(
        self, pcrid: int, day: int, group_id: int
    ) -> List[RecordDao]:
        latest_time = await self.get_latest_time(group_id)
        async with self.async_session() as session:
            async with session.begin():
                date = pcr_date(latest_time)
                start_day = date - timedelta(days=day)
                result = await session.execute(
                    select(RecordDao)
                    .where(
                        RecordDao.time >= start_day.timestamp(),
                        RecordDao.time <= latest_time,
                        RecordDao.pcrid == pcrid,
                        RecordDao.group_id == group_id,
                    )
                    .order_by(asc(RecordDao.time))
                )
                return result.scalars().all()

    async def get_clan_day(self, group_id: int) -> int:
        latest_time = await self.get_latest_time(group_id)
        async with self.async_session() as session:
            async with session.begin():
                date = pcr_date(latest_time)
                start_day = date - timedelta(days=5)
                result = await session.execute(
                    select(func.min(RecordDao.time)).where(
                        RecordDao.time >= start_day.timestamp(),
                        RecordDao.time <= latest_time,
                        RecordDao.group_id == group_id,
                    )
                )
                time = result.fetchone()[0] or 0
                return ((latest_time - time) // (3600 * 24)) + 1

    async def get_max_dao(self, group_id: int) -> int:
        day = await self.get_clan_day(group_id)
        return day * 3

    async def get_all_records(self, group_id: int) -> List[RecordDao]:
        latest_time = await self.get_latest_time(group_id)
        async with self.async_session() as session:
            async with session.begin():
                date = pcr_date(latest_time)
                start_day = date - timedelta(days=5)
                result = await session.execute(
                    select(RecordDao).where(
                        RecordDao.time >= start_day.timestamp(),
                        RecordDao.time <= latest_time,
                        RecordDao.group_id == group_id,
                    )
                )
                return result.scalars().all()

    async def get_day_rcords(self, timestamp: int, group_id: int) -> List[RecordDao]:
        date = pcr_date(timestamp)
        tomorrow = date + timedelta(days=1)
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(RecordDao).where(
                        RecordDao.time >= date.timestamp(),
                        RecordDao.time <= tomorrow.timestamp(),
                        RecordDao.group_id == group_id,
                    )
                )
                return result.scalars().all()

    async def clanbattle_name2pcrid(self, group_id: int, name: str) -> List[int]:
        latest_time = await self.get_latest_time(group_id)
        date = pcr_date(latest_time)
        start_day = date - timedelta(days=5)
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(RecordDao.pcrid)
                    .where(
                        RecordDao.time >= start_day.timestamp(),
                        RecordDao.time <= latest_time,
                        RecordDao.name == name,
                        RecordDao.group_id == group_id,
                    )
                    .distinct()
                )
                return result.scalars().all()

    async def correct_dao(self, dao_id: int, flag: int, group_id: int):
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(RecordDao).where(
                        RecordDao.battle_log_id == dao_id,
                        RecordDao.group_id == group_id,
                    )
                )
                if result.scalar_one_or_none():
                    await session.execute(
                        update(RecordDao)
                        .where(
                            RecordDao.battle_log_id == dao_id,
                            RecordDao.group_id == group_id,
                        )
                        .values(flag=flag)
                    )
                    return True
        return False

    # 通知部分
    async def get_notice(
        self,
        item: int,
        group_id: int,
        boss: Optional[int] = None,
        lap: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> List[NoticeCache]:
        async with self.async_session() as session:
            async with session.begin():
                sql = select(NoticeCache).where(
                    NoticeCache.notice_type == item,
                    NoticeCache.group_id == group_id,
                    NoticeCache.time - int(time.time()) <= 24 * 3600,
                )
                if boss:
                    sql = sql.filter(NoticeCache.boss == boss)
                if lap:
                    sql = sql.filter(NoticeCache.lap <= lap)
                if user_id:
                    sql = sql.filter(NoticeCache.user_id == user_id)
                result = await session.execute(sql)
                return result.scalars().all()

    async def delete_notice(
        self,
        item: int,
        group_id: int,
        boss: Optional[int] = None,
        user_id: Optional[int] = None,
        lap: Optional[int] = None,
    ):
        async with self.async_session() as session:
            async with session.begin():
                sql = delete(NoticeCache).where(
                    NoticeCache.notice_type == item, NoticeCache.group_id == group_id
                )
                if boss:
                    sql = sql.filter(NoticeCache.boss == boss)
                if lap:
                    sql = sql.filter(NoticeCache.lap <= lap)
                if user_id:
                    sql = sql.filter(NoticeCache.user_id == user_id)
                await session.execute(sql)

    async def add_notice(self, notice: NoticeCache):
        async with self.async_session() as session:
            async with session.begin():
                notice.time = int(time.time())
                if notice.notice_type == NoticeType.subscribe.value:
                    if await self.get_notice(
                        notice.notice_type,
                        notice.group_id,
                        notice.boss,
                        user_id=notice.user_id,
                    ):
                        await session.execute(
                            update(NoticeCache)
                            .where(
                                NoticeCache.notice_type == notice.notice_type,
                                NoticeCache.group_id == notice.group_id,
                                NoticeCache.boss == notice.boss,
                                NoticeCache.user_id == notice.user_id,
                            )
                            .values(text=notice.text, lap=notice.lap)
                        )
                        return
                elif await self.get_notice(
                    notice.notice_type, notice.group_id, user_id=notice.user_id
                ):
                    await session.execute(
                        update(NoticeCache)
                        .where(
                            NoticeCache.notice_type == notice.notice_type,
                            NoticeCache.group_id == notice.group_id,
                            NoticeCache.user_id == notice.user_id,
                        )
                        .values(boss=notice.boss, text=notice.text, time=notice.time)
                    )
                    return

                await session.merge(notice)

    async def add_sl(self, sl: SLDao) -> bool:
        async with self.async_session() as session:
            async with session.begin():
                if await self.check_sl(sl.user_id, sl.group_id):
                    return False
                await session.merge(sl)
                return True

    async def check_sl(self, uid: int, group_id: int) -> bool:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(SLDao).where(
                        SLDao.user_id == uid,
                        SLDao.group_id == group_id,
                        SLDao.time > pcr_date(datetime.now().timestamp()).timestamp(),
                    )
                )
                return bool(result.scalar_one_or_none())

    async def get_kpis(self, group_id: int) -> List[ClanBattleKPI]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(ClanBattleKPI).where(ClanBattleKPI.group_id == group_id)
                )
                return result.scalars().all()

    async def add_kpi_special(self, kpi: ClanBattleKPI):
        async with self.async_session() as session:
            async with session.begin():
                kpi.time = int(time.time())
                await session.merge(kpi)

    async def delete_kpi(self, group_id: int, pcrid: Optional[int] = None) -> int:
        """删除本群的 KPI 记录，返回实际删掉的条数（0 = 没有这条记录）

        不传 pcrid = 清空本群全部（【清空kpi】）；传了 = 只删那个 pcrid（【删除kpi】）。
        返回条数是为了让【删除kpi】能区分「删掉了」和「本来就没有」—— 不然用户输错
        编号也只会看到「删除成功」，不知道自己删了个寂寞。
        """
        async with self.async_session() as session:
            async with session.begin():
                sql = delete(ClanBattleKPI).where(ClanBattleKPI.group_id == group_id)
                if pcrid is not None:
                    sql = sql.filter(ClanBattleKPI.pcrid == pcrid)
                result = await session.execute(sql)
                return result.rowcount or 0

    # BOX部分
    async def refresh_player_units(self, unit_list: List[PlayerUnit], user_id: int):
        async with self.async_session() as session:
            async with session.begin():
                await session.execute(
                    delete(PlayerUnit).where(PlayerUnit.user_id == user_id)
                )
                session.add_all(unit_list)

    async def get_player_units(self, user_id: int) -> List[PlayerUnit]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(PlayerUnit).where(PlayerUnit.user_id == user_id)
                )
                return result.scalars().all()

    async def get_player_support_units(self, user_id: int) -> List[PlayerUnit]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(PlayerUnit).where(
                        PlayerUnit.user_id == user_id, PlayerUnit.support_position != 0
                    )
                )
                return result.scalars().all()

    async def refresh_support_units(
        self, support_list: List[SupportUnit], group_id: int
    ):
        async with self.async_session() as session:
            async with session.begin():
                await session.execute(
                    delete(SupportUnit).where(SupportUnit.group_id == group_id)
                )
                session.add_all(support_list)

    async def get_support_units(self, group_id: int) -> List[SupportUnit]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(SupportUnit).where(SupportUnit.group_id == group_id)
                )
                return result.scalars().all()

    # 成员部分
    async def add_member(self, member: ClanBattleMember):
        async with self.async_session() as session:
            async with session.begin():
                await session.merge(member)

    async def delete_member(self, group_id: int, user_id: int) -> int:
        """删掉某人在某群的公会绑定，返回实际删掉的条数（0 = 本来就没绑过）

        返回条数是为了让调用方能给出「你在这个群没有绑定」这种友好提示 ——
        不然无论有没有删掉都回一句「成功」，用户会以为自己退错了群。
        """
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    delete(ClanBattleMember).where(
                        ClanBattleMember.user_id == user_id,
                        ClanBattleMember.group_id == group_id,
                    )
                )
                return result.rowcount or 0

    async def get_group_member(self, group_id: int) -> List[ClanBattleMember]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(ClanBattleMember).where(
                        ClanBattleMember.group_id == group_id
                    )
                )
                return result.scalars().all()

    async def get_member_group(self, user_id: int) -> List[ClanBattleMember]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(ClanBattleMember).where(ClanBattleMember.user_id == user_id)
                )
                return result.scalars().all()

    async def get_bound_groups(self) -> List[ClanBattleMember]:
        """所有「有人绑定过」的群，每个群只取一条记录

        用于给群主/群管自动发现"我管理的群"：这些人可能没发过【绑定本群公会】，
        但只要群里有人用过，就应该能在网页端看到自己的群。
        SQLite 允许 GROUP BY 时直接取非聚合列（每群任取一行），够用。
        """
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(ClanBattleMember).group_by(ClanBattleMember.group_id)
                )
                return result.scalars().all()

    # 竞技场设置
    # 群级设置（按群独立）

    async def get_push_enabled(self, group_id: int) -> bool:
        """本群的「主动推送」是否开启

        **没设置过 = 开启**，所以查不到行时直接返回 True，而不是顺手插一行 ——
        绝大多数群根本不会碰这个开关，没必要留一堆没用的行。
        """
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(GroupSetting).where(GroupSetting.group_id == group_id)
                )
                setting = result.scalar_one_or_none()
                return True if setting is None else bool(setting.push_enabled)

    async def set_push_enabled(self, group_id: int, enabled: bool):
        """写入本群的「主动推送」开关（按群 upsert）"""
        async with self.async_session() as session:
            async with session.begin():
                await session.merge(
                    GroupSetting(group_id=int(group_id), push_enabled=bool(enabled))
                )

    async def init_jjc_setting(self, user_setting: ArenaSetting):
        async with self.async_session() as session:
            async with session.begin():
                if not await self.get_jjc_setting(user_setting.user_id):
                    session.add(user_setting)

    async def get_jjc_setting(self, user_id: int) -> Union[ArenaSetting, None]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(ArenaSetting).where(ArenaSetting.user_id == user_id)
                )
                return result.scalar_one_or_none()

    async def update_jjc_setting(self, user_id: int, update_valuse: dict):
        async with self.async_session() as session:
            async with session.begin():
                await session.execute(
                    update(ArenaSetting)
                    .where(ArenaSetting.user_id == user_id)
                    .values(**update_valuse)
                )

    # 公主竞技场防守缓存

    async def add_grand_cache(self, historys: List[GrandDefenceCache]):
        if not historys:
            return
        async with self.async_session() as session:
            async with session.begin():
                for history in historys[::-1]:
                    await session.merge(history)

    async def query_grand_cache(self, pcrid: int, row: int) -> Union[int, None]:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(GrandDefenceCache.defence)
                    .where(
                        GrandDefenceCache.pcrid == pcrid, GrandDefenceCache.row == row
                    )
                    .order_by(desc(GrandDefenceCache.vs_time))
                )
                return int(result) if (result := result.scalars().first()) else result

    async def cache_latest_time(self, user_id: int) -> int:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(func.max(GrandDefenceCache.vs_time)).where(
                        GrandDefenceCache.user_id == user_id
                    )
                )
                return result.scalar_one_or_none() or 0

    # Web
    async def web_check_user(self, account: str, password: str) -> WebAccount:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(WebAccount).where(
                        WebAccount.account == account, WebAccount.password == password
                    )
                )
                return result.scalar_one_or_none()

    async def web_query_user(self, account) -> WebAccount:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(WebAccount).where(WebAccount.account == account)
                )
                return result.scalar_one_or_none()

    async def web_add_user(self, account: WebAccount):
        async with self.async_session() as session:
            async with session.begin():
                account.create_time = time.time()
                # 按账号（主键）查旧记录来继承权限等级。
                # 不能再用 web_check_user(account, password)：网页端登录每次都会生成新的随机
                # 临时密码，按 account+password 查必然落空，随后 merge 会把用户原有的
                # priority 一起覆盖成默认值 0，表现就是「设好的权限一登录就没了」。
                if user := await self.web_query_user(account.account):
                    account.priority = user.priority
                await session.merge(account)

    async def change_web_priority(self, account: str, level: int):
        async with self.async_session() as session:
            async with session.begin():
                await session.execute(
                    update(WebAccount)
                    .where(WebAccount.account == account)
                    .values(priority=level)
                )

    async def change_web_password(
        self, account: str, old_password: str, new_password: str
    ) -> bool:
        """修改网页端登录密码：先校验旧密码，通过才更新，并清掉「临时密码」标记。

        返回 False 表示旧密码不对。改成自己设的密码后 temp=False，登录接口里
        「临时密码 7 天过期」那条限制就不再对它生效。
        """
        if await self.web_check_user(account, old_password) is None:
            return False
        async with self.async_session() as session:
            async with session.begin():
                await session.execute(
                    update(WebAccount)
                    .where(WebAccount.account == account)
                    .values(password=new_password, temp=False)
                )
        return True

    async def change_member_priority(self, group_id: int, user_id: int, level: int):
        """设置某人在「某个群」里的网页端权限等级（ClanBattleMember.priority）

        只影响这一个群，和 WebAccount.priority（全局账号等级）是两回事。
        目标没有绑定记录时是空操作，调用方需要自己先确认行存在。
        """
        async with self.async_session() as session:
            async with session.begin():
                await session.execute(
                    update(ClanBattleMember)
                    .where(
                        ClanBattleMember.group_id == group_id,
                        ClanBattleMember.user_id == user_id,
                    )
                    .values(priority=level)
                )

    async def web_add_cookie(self, token: str, user_id: str):
        """写入 / 刷新一条登录态。

        time 显式写当前时间，不依赖模型默认值 —— 登录、以及改密后把当前 token
        补回来，都需要从这一刻重新起算 7 天有效期。
        """
        async with self.async_session() as session:
            async with session.begin():
                await session.merge(
                    CookieCache(token=token, user_id=user_id, time=int(time.time()))
                )

    async def web_delete_cookie(
        self, token: Optional[str] = None, user_id: Optional[str] = None
    ):
        """删除登录态：给 token 删这一条，给 user_id 删这个人的全部登录态。

        两个都不给就报错，避免不小心写成「无条件清空整张表」。
        """
        async with self.async_session() as session:
            async with session.begin():
                # 原写法 `if not token or user_id` 等价于「token 为空就报错」，
                # 于是「按 user_id 清掉某人的全部登录」这条路根本走不通；
                # 而按 token 删的那条又被调用方传错字段静默吞掉了（见 api.py 的 logout）。
                # 这里改成真正的「两个都不给才报错」。
                if not token and not user_id:
                    raise ValueError("需要指定token或者user")
                sql = delete(CookieCache)
                if token:
                    sql = sql.where(CookieCache.token == token)
                if user_id:
                    sql = sql.where(CookieCache.user_id == user_id)
                await session.execute(sql)

    async def web_query_cookie(self, token: str) -> CookieCache:
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(CookieCache).where(CookieCache.token == token)
                )
                return result.scalar_one_or_none()

    # ---------------------------- 会战档线缓存 ----------------------------
    #
    # 档线是全服排名数据，游戏侧每半小时才更新一次，但抓一次要打十几次分页请求
    # （默认 14 个档位 = 13 个分页，外加「末位二分搜索」十来次），而且档线接口
    # 一旦报错会直接把功能禁用、还要重登一次来救监控会话。所以落库缓存、由 webui
    # 按 TTL 决定要不要重抓。主键带 clan_battle_id，换届之后自动失效。

    async def get_rank_line_cache(
        self, group_id: int, clan_battle_id: int, ranks_key: str
    ) -> Optional[RankLineCache]:
        """取「某个群 + 某一届 + 某个档位组合」的档线缓存，没有返回 None"""
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(RankLineCache).where(
                        RankLineCache.group_id == int(group_id),
                        RankLineCache.clan_battle_id == int(clan_battle_id),
                        RankLineCache.ranks_key == ranks_key,
                    )
                )
                return result.scalar_one_or_none()

    async def get_latest_rank_line_cache(
        self, group_id: int, ranks_key: str
    ) -> Optional[RankLineCache]:
        """取某个群最新一届的档线缓存（不限定会战编号）

        给「出刀监控没开」的情况用：这时拿不到 clan_battle_id，但页面仍可以把上次
        抓到的档线显示出来（前端会标注数据时间），总比一片空白强。
        """
        async with self.async_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(RankLineCache)
                    .where(
                        RankLineCache.group_id == int(group_id),
                        RankLineCache.ranks_key == ranks_key,
                    )
                    .order_by(desc(RankLineCache.clan_battle_id))
                    .limit(1)
                )
                return result.scalar_one_or_none()

    async def set_rank_line_cache(
        self, group_id: int, clan_battle_id: int, ranks_key: str, payload: str
    ):
        """写入档线缓存，并顺手清掉本群其它届的残留

        换届之后旧行永远不会再被读到（主键对不上），留着只会一直涨，所以在写入
        路径上删一次就够，不需要额外的定时清理任务。
        """
        group_id, clan_battle_id = int(group_id), int(clan_battle_id)
        async with self.async_session() as session:
            async with session.begin():
                await session.execute(
                    delete(RankLineCache).where(
                        RankLineCache.group_id == group_id,
                        RankLineCache.clan_battle_id != clan_battle_id,
                    )
                )
                await session.merge(
                    RankLineCache(
                        group_id=group_id,
                        clan_battle_id=clan_battle_id,
                        ranks_key=ranks_key,
                        payload=payload,
                        updated_at=int(time.time()),
                    )
                )

pcr_sqla = SQALA(str(FilePath.data.value / "data.db"))
