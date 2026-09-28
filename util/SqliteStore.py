# !/usr/bin/env python3
# -*- coding:utf-8 -*-
#
# =============================================
# @File  : SqliteStore.py
# @Date  : 2026-10-16
# @Desc  : 通用 SQLite 单表存储工具类, 与具体业务无关
#          提供建表(含索引)、按主键 upsert、条件查询、exists/count 等基础增删改查能力,
#          业务侧只需声明表名/列定义/索引列, 并负责把外部数据(如接口返回)转成列名->值的 dict。
#
# 与 KVCache 的分工:
#   KVCache 是 JSON 文件 kv 缓存, 适合"按 key 记一条中间结果、支持断点重跑"的场景;
#   SqliteStore 面向规整的表格数据, 需要按多个字段检索、随时间不断累积并按主键增量覆盖时使用。
#
# 用法示例:
#   store = SqliteStore('/tmp/demo.db', 'worker',
#                       columns={'id': 'int', 'name': 'str', 'score': 'int'},
#                       primary_key='id', indexes=['name'])
#   store.upsert([{'id': 1, 'name': 'tom', 'score': 90}])
#   store.select(eq={'name': 'tom'})          # 等值查询
#   store.select(like={'name': 'to'})         # 模糊查询(包含匹配)
#   store.exists(1) / store.count()
#   注: upsert/insert 为整批原子 —— 缺主键或列名未定义会抛 ValueError 且一行不写, 执行中途失败整批回滚。
#
# 日期与布尔(SQLite 无原生日期/布尔类型, 只有 NULL/INTEGER/REAL/TEXT/BLOB 五个存储类):
#   日期时间 -> 声明 'str', 业务侧转成定宽 ISO 串后传入, 如 '2026-10-16 13:51:38'
#     定宽补零的 ISO 串字典序等于时间序, 因此 order_by 排序、倒序取最新都直接可用;
#     取用时自行 datetime.strptime(...) 解析, 本类不做序列化。
#     缺值会落成空串, 而空串 ASC 排最前/DESC 排最后, 按时间列排序时用 not_blank=[该列] 排除。
#   布尔 -> 声明 'int', 存 0/1(传 Python True/False 也会被驱动转成 1/0)
#     注意读回来是 int 而非 bool, 需要自行 bool(row['xxx']);
#     不要声明成 'str', 那样 False 会落成文本 '0', 读回是字符串且等值查询依赖隐式转换。
#
#   store = SqliteStore('/tmp/demo.db', 'task',
#                       columns={'id': 'int', 'name': 'str', 'created_at': 'str', 'finished': 'int'},
#                       primary_key='id', indexes=['name'])
#   store.upsert([{'id': 1, 'name': 'demo', 'created_at': '2026-10-16 13:51:38', 'finished': True}])
#   store.select(order_by='created_at', desc=True)   # 按时间倒序, 字符串序即时间序
#
# 并发边界(实测于 sqlite 3.50.1 + 系统 python3.13, 结论与版本无关):
#   不用业务端管的: 单条语句/单个事务的原子性、以及多进程同时写不会把库文件写坏, 这些由 SQLite 引擎保证。
#   需要业务端知道的:
#     1) 锁冲突不排队, 超时即抛错。另一连接持有未提交写事务时, 本连接写入会等 timeout
#        (sqlite3.connect 默认 5.0s) 后抛 OperationalError: database is locked, 不会自行重试。
#        => 多进程同时 sync(如 Jenkins 两个 job 撞车)会有一侧直接失败, 需调用方避免并发或自行重试。
#     2) 连接非线程安全。同一连接实例跨线程使用直接抛
#        ProgrammingError: SQLite objects created in a thread can only be used in that same thread.
#        => 一个 SqliteStore 实例只能在创建它的那个线程里用; 需要多线程时各自建实例(或自行加锁串行化)。
#     3) 默认 journal_mode=delete(回滚日志, 非 WAL), 写事务期间的并发读也更容易撞锁。
#        未开 WAL 是有意选择: 网络盘(Jenkins)上 WAL 的 -wal/-shm 文件行为不稳, 且当前是单进程顺序写入, 用不上。
#     4) upsert 是整行覆盖(未提供的列写 NULL), 两个写入方各持不同快照时"后写覆盖前写"属于业务语义问题,
#        加锁解决不了 —— 落库必须传完整行(如接口返回的整条数据), 不要传局部字段。
# =============================================

import os
import re
import sqlite3
from typing import Any, Dict, List, Optional, Sequence, Union

_IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

# 列定义中类型简写 -> SQLite 列类型, 仅支持这三种, 其他一律报错
# 日期时间用 str 存定宽 ISO 串, 布尔用 int 存 0/1, 详见文件头说明
_TYPE_MAP = {'int': 'INTEGER', 'float': 'REAL', 'str': 'TEXT'}


def _check_ident(name: str):
    """表名/列名无法参数绑定, 只允许合法标识符, 避免拼接SQL被注入"""
    if not _IDENT_RE.match(f'{name}'):
        raise ValueError(f'非法的表名或列名: {name}')


def _check_val_type(col: str, val_type: str):
    """类型简写拼错(如 Int/date)若静默降级成 TEXT 会埋下排序与比较的坑, 故直接拒绝"""
    if val_type not in _TYPE_MAP:
        raise ValueError(f'列 {col} 的类型 {val_type} 不支持, 可选: {sorted(_TYPE_MAP.keys())}; '
                         f'日期时间请用 str 存定宽ISO串, 布尔请用 int 存0/1')


class SqliteStore:
    """通用 SQLite 单表存储, 一个实例对应一张表

    连接非线程安全: 实例只能在创建它的线程内使用; 多进程并发写可能抛 database is locked。详见文件头"并发边界"。
    """

    def __init__(self, db_path: str, table: str, columns: Dict[str, str],
                 primary_key: str, indexes: Sequence[str] = (), create_dir: bool = True):
        """
        建库建表(表已存在则只连接, 不动结构), 一个实例固定对应一张表

        @param db_path: 数据库文件路径, 文件及父目录不存在时自动创建;
                        传 ':memory:' 可建纯内存库(单测推荐, 进程退出即消失, 不会污染真实缓存)
        @param table: 表名, 只允许字母/数字/下划线且不以数字开头(拼进 SQL 的标识符无法参数绑定, 故做白名单校验)
        @param columns: 列定义, key-列名, value-类型简写, 只接受 int/float/str(传其他值直接报错, 不会静默降级);
                        日期时间用 str 存定宽 ISO 串, 布尔用 int 存 0/1, 详见文件头说明
        @param primary_key: 主键列名, 必须是 columns 之一, upsert 依据该列覆盖; 主键自带索引无需再进 indexes
        @param indexes: 需要额外建索引的列名列表, 用于非主键字段的等值/模糊/排序查询加速;
                       未列入的列上做条件查询会走全表扫(本仓库千行量级, 影响可忽略)
        @param create_dir: 是否自动创建 db_path 的父目录, 传 False 时需保证目录已存在

        注意:
          1) 建表语句是 CREATE TABLE IF NOT EXISTS —— 改了 columns(加列/改类型)对**已存在的库文件不生效**:
             读时新列在结果 dict 里静默缺失, 写时抛 OperationalError: table xxx has no column named yyy。
             加字段后需自行 ALTER TABLE, 或删掉 db 文件重新全量 sync。
          2) 同一个 db_path 可以开多个实例分别对应不同表, 互不影响。
          3) 实例持有连接, 用完的实例(非默认单例)记得 close()。
        """
        _check_ident(table)
        for col, val_type in columns.items():
            _check_ident(col)
            _check_val_type(col, val_type)
        if primary_key not in columns:
            raise ValueError(f'主键列 {primary_key} 未在 columns 中定义: {list(columns.keys())}')

        self.db_path = db_path
        self.table = table
        self.columns = dict(columns)
        self.primary_key = primary_key
        self.indexes = [col for col in indexes if col != primary_key]
        for col in self.indexes:
            _check_ident(col)
        self.col_names = list(self.columns.keys())

        if create_dir:
            parent = os.path.dirname(db_path)
            if parent and not os.path.exists(parent):
                os.makedirs(parent)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        """建表和索引, 全部 IF NOT EXISTS; 库文件已存在时不会改动已有列结构(见 __init__ 注意1)"""
        cols_sql = ', '.join(f'{col} {self._sql_type(col)}' for col in self.col_names)
        scripts = [f'CREATE TABLE IF NOT EXISTS {self.table} ({cols_sql}, PRIMARY KEY ({self.primary_key}))']
        scripts += [f'CREATE INDEX IF NOT EXISTS idx_{self.table}_{col} ON {self.table}({col})'
                    for col in self.indexes]
        self.conn.executescript(';'.join(scripts) + ';')
        self.conn.commit()

    def _sql_type(self, col: str) -> str:
        """列类型简写 -> SQLite 列类型; 类型已在 __init__ 校验过, 这里直接索引"""
        return _TYPE_MAP[self.columns[col]]

    def _check_rows(self, rows: List[Dict[str, Any]]):
        """
        写入前整批校验, 任一行不合法就抛 ValueError 且整批一条都不写(不校验值类型, 那类问题由 _execute_batch 回滚兜底)

        校验两项:
          1) 列名必须都在 columns 里 —— 提前拦住 executemany 中途失败;
          2) 主键必须有值(键存在且不为 None) —— INTEGER 主键是 rowid 别名, 传 None 时 SQLite 会
             自动分配一个新 rowid, 本该覆盖已有记录的数据会变成一条凭空多出的脏行, 且不报任何错。
        """
        defined = set(self.col_names)
        for index, row in enumerate(rows):
            unknown = set(row.keys()) - defined
            if unknown:
                raise ValueError(f'第{index}行包含未定义的列: {unknown}, 表 {self.table} 仅有: {self.col_names}')
            if row.get(self.primary_key) is None:
                raise ValueError(f'第{index}行缺少主键 {self.primary_key}(键不存在或值为 None), '
                                 f'SQLite 会把它当成"未指定 rowid"自动分配新主键, 导致凭空插入脏数据而非覆盖原行')

    def _execute_batch(self, sql: str, params_list: List[tuple]):
        """
        批量执行并提交; 任何一行失败都整批回滚

        executemany 是逐行绑定的, 值类型不合法(如传了 set/dict/自定义对象)会在绑定阶段抛错,
        此时前面已执行的行留在未提交事务里 —— 不显式 rollback 的话, 后续任意一次 commit 会把这半批脏数据固化。
        """
        try:
            self.conn.executemany(sql, params_list)
        except Exception:
            self.conn.rollback()
            raise
        self.conn.commit()

    def upsert(self, rows: List[Dict[str, Any]]) -> int:
        """
        按主键覆盖写入: 主键不存在则插入, 已存在则**整行覆盖**为本次传入的值

        @param rows: 列名->值 的 dict 列表, **每条都必须含主键列且主键不为 None**(否则整批抛 ValueError);
                     值必须是 SQLite 能直接适配的类型(int/float/str/bytes/None), 本类不做任何类型转换和清洗
        @return: 提交的条数(等于 len(rows))

        坑:
          1) 不是"只更新传入的列"。SQL 是 ON CONFLICT DO SET 全部非主键列, 所以 rows 里没写的列
             会被显式写成 NULL 而不是保留原值。**改单个字段的正确姿势**: 先 get()/select_one() 取出整行,
             改掉目标字段, 再整行 upsert 回去。
          2) 主键取不到值(缺键或值为 None)会抛 ValueError 且整批不写。这是刻意拦的: INTEGER 主键是 rowid 别名,
             传 NULL 时 SQLite 不报错而是自动分配一个新 id, 本该覆盖的记录就变成了一条凭空多出的脏行。
             业务侧映射字段时确认主键真的取到了值(如接口字段是 id/eId, 别映射错)。
          3) 落库要传完整行(如接口返回的整条数据)。两个写入方各持不同快照时"后写覆盖前写"是这里的语义,
             不是 bug, 加锁也解决不了 —— 别拿一份过期快照去覆盖新数据。
          4) rows 里出现未定义的列名会先抛 ValueError(整批不写); 值类型不合法(如传了 set/dict/自定义对象)
             只能在绑定阶段由 SQLite 报错, 本方法会**整批回滚**后再把异常抛出, 不会留下半批数据。
             即: 一次 upsert 要么全成功, 要么一行都没写进去。
          5) 空列表直接返回 0, 不执行任何 SQL。
        """
        if not rows:
            return 0
        self._check_rows(rows)
        cols = self.col_names
        placeholders = ', '.join(['?'] * len(cols))
        update_clause = ', '.join(f'{col}=excluded.{col}' for col in cols if col != self.primary_key)
        sql = (f'INSERT INTO {self.table} ({", ".join(cols)}) VALUES ({placeholders}) '
               f'ON CONFLICT({self.primary_key}) DO UPDATE SET {update_clause}')
        self._execute_batch(sql, [tuple(row.get(col) for col in cols) for row in rows])
        return len(rows)

    def insert(self, rows: List[Dict[str, Any]]) -> int:
        """
        纯插入: 主键已存在时由 SQLite 抛 IntegrityError, 不做覆盖

        与 upsert 的区别只在于冲突时的行为: 适合"重复即异常"的场景(如断言某条数据不该出现两次)。
        日常同步数据基本都该用 upsert; 拿不准就用 upsert, 别用本方法。
        其余约束同 upsert: 整行写入(未提供的列写 NULL)、主键缺失整批抛 ValueError、
        任一行执行失败整批回滚。

        @param rows: 列名->值 的 dict 列表
        @return: 提交的条数(等于 len(rows))
        """
        if not rows:
            return 0
        self._check_rows(rows)
        cols = self.col_names
        sql = f'INSERT INTO {self.table} ({", ".join(cols)}) VALUES ({", ".join(["?"] * len(cols))})'
        self._execute_batch(sql, [tuple(row.get(col) for col in cols) for row in rows])
        return len(rows)

    def delete(self, eq: Dict[str, Any]) -> int:
        """
        按等值条件删除, 多个条件之间是 AND 关系

        @param eq: 列名 -> 值, 必须至少给一个条件; 值走参数绑定, 列名必须是已定义列
        @return: 实际删除的行数, 条件没匹配到任何行时返回 0(不报错)

        坑:
          1) 空条件(None 或 {})直接抛 ValueError —— 本方法不提供清空整表的能力,
             要清库请自行删除 db 文件, 避免误调用把同步好的数据全清掉。
          2) 只支持等值, 不支持模糊匹配和范围比较。想"按名称模糊删"或"删某时间之前的",
             先 select()/select_one() 查出主键, 再按主键逐条 delete。
          3) 没有事务批量删除: 一次 delete 一个条件组合, 批量按主键删请自行循环(数据量小, 够用)。
        """
        if not eq:
            raise ValueError('delete() 必须指定等值条件, 清空整表请自行删除数据库文件')
        where, params = self._build_where(eq=eq)
        cur = self.conn.execute(f'DELETE FROM {self.table} WHERE {where}', params)
        self.conn.commit()
        return cur.rowcount

    @staticmethod
    def _like_pattern(keyword: str) -> str:
        """把用户输入转成包含匹配的 LIKE 值, 转义 % 和 _ 通配符"""
        escaped = f'{keyword}'.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        return f'%{escaped}%'

    def _build_where(self, eq: Dict[str, Any] = None, like: Dict[str, str] = None,
                     not_blank: Sequence[str] = None):
        """拼 WHERE 片段, 返回 (条件串, 参数列表); 值全部参数绑定, 列名先做标识符白名单校验, 条件间固定 AND"""
        conditions, params = [], []
        for col, val in (eq or {}).items():
            _check_ident(col)
            if col not in self.columns:
                raise ValueError(f'查询列 {col} 未在表 {self.table} 中定义')
            conditions.append(f'{col} = ?')
            params.append(val)
        for col, keyword in (like or {}).items():
            _check_ident(col)
            if col not in self.columns:
                raise ValueError(f'查询列 {col} 未在表 {self.table} 中定义')
            conditions.append(f"{col} LIKE ? ESCAPE '\\'")
            params.append(self._like_pattern(keyword))
        for col in (not_blank or ()):
            _check_ident(col)
            if col not in self.columns:
                raise ValueError(f'查询列 {col} 未在表 {self.table} 中定义')
            conditions.append(f"{col} IS NOT NULL AND {col} <> ''")
        return (' AND '.join(conditions), params)

    def select(self, eq: Dict[str, Any] = None, like: Dict[str, str] = None,
               order_by: Optional[str] = None, desc: bool = True,
               limit: Optional[int] = None, not_blank: Sequence[str] = None) -> List[Dict[str, Any]]:
        """
        条件查询, 返回 dict 列表(列名->值), 无匹配返回空列表(不是 None)

        @param eq: 等值条件, 列名 -> 值; 多列之间 AND
        @param like: 模糊条件, 列名 -> 关键字, 语义是**包含匹配**(内部自动包成 %关键字% 并对
                    关键字里的 % _ \\ 做转义, 所以传 'a%b' 查的是字面量 'a%b' 而非通配符)
        @param order_by: 排序列名, 必须是已定义列; None 表示不写 ORDER BY
        @param desc: 是否倒序, 仅在传了 order_by 时才有意义
        @param limit: 最多返回条数; None / 0 / 负数都表示不限制(实现上是 `if limit:` 判真)
        @param not_blank: 列名列表, 要求这些列**既不是 NULL 也不是空串**才入选, 条件间及与 eq/like 之间都是 AND。
                          典型用途: 按时间列 order_by 时排除缺值行 —— 空串在 ASC 时排最前、DESC 时排最后,
                          看着像"最早/最新"其实是脏数据; 也可用于"只统计某字段填了的记录"。
                          本参数只认 NULL 和 '', 不会排除 0 或 '0'(那是合法取值)。
        @return: List[dict]

        坑:
          1) eq 和 like 之间也是 AND, 想"或"关系得自己分两次查再合并, 本方法不支持 OR。
          2) 不传 order_by 时返回顺序由 SQLite 执行计划决定(可能随是否命中索引而变),
             **不要假设它等于插入顺序或主键顺序**; 要稳定顺序就显式传 order_by。
          3) 值类型由列声明类型决定: int 列回 int、str 列回 str。所以按"布尔列"约定存的 int(0/1)
             读回来是 int, 需自行 bool(); 按"日期列"约定存的 str 读回来是字符串, 需自行 strptime。
          4) 走的是 SELECT *, 表里若有 raw_json 这类大字段, 列表查询会把它们全部读进内存。
             只要几个字段时业务侧自行裁剪; 只要一条时用 select_one()。
          5) 模糊查询用 LIKE '%x%' 无法命中索引(全表扫), 关键字尽量给得精确; 精确匹配请用 eq。
        """
        where, params = self._build_where(eq=eq, like=like, not_blank=not_blank)
        sql = f'SELECT * FROM {self.table}'
        if where:
            sql += f' WHERE {where}'
        if order_by:
            _check_ident(order_by)
            if order_by not in self.columns:
                raise ValueError(f'排序列 {order_by} 未在表 {self.table} 中定义')
            sql += f' ORDER BY {order_by} {"DESC" if desc else "ASC"}'
        if limit:
            sql += f' LIMIT {int(limit)}'
        return [dict(row) for row in self.conn.execute(sql, params).fetchall()]

    def select_one(self, eq: Dict[str, Any] = None, like: Dict[str, str] = None,
                   order_by: str = None, desc: bool = True,
                   not_blank: Sequence[str] = None) -> Optional[Dict[str, Any]]:
        """
        按条件取一条, 无匹配返回 None

        等价于 select(..., limit=1) 后取首元素, 参数含义与限制条件全部同 select。

        坑:
          1) 返回值可能是 None, 调用方必须判空, 别写成 self.select_one(...)['name']。
          2) 命中多条时"取到哪条"完全由 order_by 决定: 不传 order_by 结果不确定,
             想取最新一条务必显式传时间列(本类 desc 默认 True, 即倒序=最新在前)。
          3) desc 默认 True 是为"取最新"优化的; 想取最早一条记得显式传 desc=False。
          4) 按时间列取最新/最早时, 建议同时传 not_blank=[该列] 排除缺值行,
             否则 ASC 时空串会排在最前面被当成"最早的一条"。
        """
        result = self.select(eq=eq, like=like, order_by=order_by, desc=desc, limit=1, not_blank=not_blank)
        return result[0] if result else None

    def exists(self, pk_value: Union[str, int]) -> bool:
        """
        判断主键是否已存在, 只做 SELECT 1 ... LIMIT 1, 走主键索引, 比 select_one 轻

        @param pk_value: 主键值(只支持主键, 不支持其他列)
        @return: bool

        坑:
          1) 只能按主键判存在。按非主键字段判断请用 select_one(eq={...}) is not None。
          2) int 主键传字符串 '1941' 也能命中(列亲和性会把参数转成整数比较), 但请显式转成 int,
             别依赖这个隐式转换 —— 反过来 TEXT 列传 int 就不一定对得上了。
          3) **判断时机**: "先判存在再写库"的增量逻辑必须在 upsert 之前调用本方法。
             写完再判的话本页数据刚落库必然返回 True, 会在第 1 页就误判为"全是旧数据"而提前停止翻页
             (按页同步列表数据 + 按时间列做增量停止的场景就踩过这个点)。
        """
        row = self.conn.execute(f'SELECT 1 FROM {self.table} WHERE {self.primary_key} = ? LIMIT 1',
                                (pk_value,)).fetchone()
        return row is not None

    def get(self, pk_value: Union[str, int]) -> Optional[Dict[str, Any]]:
        """
        按主键取整行, 返回 dict(列名->值) 或 None

        典型用途: 配合 upsert 的"整行覆盖"语义做局部更新 —— 先 get 出整行, 改掉目标字段, 再 upsert 回去。

        坑:
          1) 返回的是新建的 dict 副本, 改它不会影响库里的数据, 必须再 upsert 才会落库。
          2) 只按主键查; 按其他字段请用 select_one(eq=.../like=...)。
          3) 无匹配返回 None, 调用方必须判空。
        """
        row = self.conn.execute(f'SELECT * FROM {self.table} WHERE {self.primary_key} = ? LIMIT 1',
                                (pk_value,)).fetchone()
        return dict(row) if row else None

    def count(self) -> int:
        """
        全表行数

        注意: 没有任何过滤能力, 想要"符合条件的条数"请用 len(select(...)) 或自行扩展;
        计数会扫一遍索引/表, 别在循环里反复调用, 需要多次比较时先取出来存变量。
        """
        return self.conn.execute(f'SELECT COUNT(*) FROM {self.table}').fetchone()[0]

    def close(self):
        """
        关闭连接。只关自己 new 出来的实例(如测试用的 ':memory:' 库、或显式传 db_path 新建的连接)

        坑:
          1) 进程内共享的单例连接**不要 close**(如业务侧 `get_xxx_store()` 不传参拿到的那个),
             关掉之后其他调用方再用的话会抛 ProgrammingError: Cannot operate on a closed database.
          2) 本类不会自动关闭, 进程正常退出时由 SQLite/OS 收尾; 单次性脚本可不调用 close, 长驻进程里
             临时建的实例应该用完就关。
        """
        self.conn.close()
