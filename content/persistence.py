# -*- coding: utf-8 -*-
"""《阿斯特兰》存档层（`content/persistence.py`）—— 宿主**半边**之一。

宿主契约（`host/store_factory.py::StoreFactory.HALF`）要求本模块提供五个口：
`get_player` / `update_player` / `init_db` / `lock` / `connect`。缺一个宿主就
**拒绝静默空跑**（抛 RuntimeError）—— 这是有意的：宁可起不来，也不要静默存不上档。
★ **签名也算契约**：`update_player(group_id, uid, **fields)` —— 宿主逐字这么调
  （`HostStore.save_player` 把整档拆成字段传进来）；写成整档入参 `(g, u, data)` 当场就炸
  （2026-09-25 换包上线实测：`TypeError: unexpected keyword argument 'name'`）。

注入面（与奥兰迪亚同形，不另发明第三套）：
    宿主 `inject_handles()` → 引擎 `inject` → 引擎调包内 `bind_host(**inject)`
    → 本模块 `bind(**handles)`：**本模块只真读** `db_path`（必给）/ `clock` 两个；
      `log` / `tlog` / `attach_tlog` / `grant_reward` 那一批由 `content/facade.py` 的
      `HANDLES` 持有并消费（`facade.log()`），本模块零读取点（审计 L1702：别再登记）。

★ 不改动存档库路径的来历 —— 它是**部署信息**，由宿主解析后注入；包不知道自己在哪台机器上跑。
★★ 但**表名必须自带包前缀**（`aetheran_players` / `aetheran_meta`）：生产库是宿主共用的那一张，
  里面躺着奥兰迪亚的表（它也有 `players`，列是 qq_id/name/level/…）。2026-09-25 换包上线实测：
  本模块原先写 `CREATE TABLE IF NOT EXISTS players` ⇒ **撞上奥兰迪亚那张表后被静默跳过**，
  之后每次 `SELECT data FROM players` 都 `no such column: data` —— **每条指令都崩**。
  （137 个测试文件 + 探针全绿照不出来：它们用的是各自新建的空库；只有真启动才暴露。）
  ⇒ 建完表**核一遍列**（fail-closed），撞车/半截表当场喊出来，不再静默存不上档。
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time

__all__ = ["bind", "db_path", "clock", "init_db", "lock", "connect",
           "get_player", "update_player", "get_player_groups", "groups_of_player",
           "all_players",
           "meta_key", "group_get", "group_set", "group_del"]

#: 存档表名（★ 带包前缀，理由见模块开头）；列 = 存档那一行的形状
TBL = "aetheran_players"
COLS = ("group_id", "uid", "data", "updated_at")
#: ★ B3-26：**按群存的共同档**（「场」这种不是单玩家档的数据）—— 与上面那张同一个库
TBL_META = "aetheran_meta"
META_COLS = ("k", "v")

#: 共同档的键形状：`<scope>:<group_id>`（scope = 谁在用，如 `instance`；
#: 分隔符只有这一处定义 —— 键里的两截都不许再含它，否则会撞别人的行）
META_SEP = ":"

#: 注入句柄的**本模块真源**。只列**本模块真读的**两个键 ——
#: `log` / `tlog` / `attach_tlog` / `grant_reward` 由 `content/facade.py` 的 `HANDLES`
#: 持有并消费（`facade.log()` 等），本模块零读取点（审计 L1702：纯写零读）。
#: ★ `bind(**handles)` 是**泛收**（`facade.bind_host` 会把整批句柄递进来）——
#:   多余的键照收不误但**不再登记**：登记一个从不读的键 = 让人以为本模块会用它。
_H = {"db_path": None, "clock": None}
_LOCK = threading.RLock()


def bind(**handles):
    """注入句柄（幂等；`None` / 缺省 = 不改）。返回本模块便于链式调用。"""
    for k, v in handles.items():
        if v is not None:
            _H[k] = v
    return _H


def db_path() -> str:
    p = _H.get("db_path")
    if not p:
        raise RuntimeError("content.persistence：db_path 句柄未注入（宿主 store_factory 负责注入）")
    return str(p)


def clock() -> float:
    fn = _H.get("clock")
    return float(fn() if callable(fn) else time.time())


# ── 连接 / 锁 ──────────────────────────────────────────────
def lock():
    return _LOCK


def connect():
    """新连接（调用方负责关闭）。表结构随第一次连接自动建好，建完**核一遍**（fail-closed）。"""
    p = db_path()
    d = os.path.dirname(p)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    c = sqlite3.connect(p, timeout=10.0)
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS %s (
        group_id TEXT NOT NULL, uid TEXT NOT NULL, data TEXT NOT NULL,
        updated_at REAL NOT NULL, PRIMARY KEY (group_id, uid))""" % TBL)
    c.execute("""CREATE TABLE IF NOT EXISTS %s (
        k TEXT PRIMARY KEY, v TEXT)""" % TBL_META)
    # ★ `IF NOT EXISTS` 撞上同名的**别人的**表时会**静默跳过**（2026-09-25 换包上线实测：
    #   奥兰迪亚的 `players` 在同一个库里 ⇒ 每次查询都 `no such column: data`）⇒ 当场核列、不对就抛。
    for _t, _cols in ((TBL, COLS), (TBL_META, META_COLS)):
        got = {r["name"] for r in c.execute("PRAGMA table_info(%s)" % _t)}
        if got != set(_cols):
            c.close()
            raise RuntimeError("%s：存档表 %s 的列不对（期望 %s，实际 %s）—— 撞上同名的别的表了？"
                               % (__name__, _t, sorted(_cols), sorted(got)))
    return c


def init_db():
    """建表 + 迁移（幂等）。"""
    with _LOCK:
        c = connect()
        try:
            c.commit()
        finally:
            c.close()
    return True


# ── 读写档 ─────────────────────────────────────────────────
def get_player(group_id, uid):
    """读档（dict | None）。`None` = 新玩家（引擎会问包要初始档）。"""
    with _LOCK:
        c = connect()
        try:
            row = c.execute("SELECT data FROM %s WHERE group_id=? AND uid=?" % TBL,
                            (str(group_id or ""), str(uid or ""))).fetchone()
        finally:
            c.close()
    # ★ 审计 L1701：原为 `except Exception: return None`。**`None` 的含义被这一处偷走了** ——
    # 上面 docstring 写明「`None` = 新玩家（引擎会问包要初始档）」，而坏档（存档半截 / 编码坏 /
    # 迁移中断）与「查无此人」塌成同一个值 ⇒ 引擎把一个玩了几十小时的档**当成新玩家**，
    # 走建号初始化，下一次落档就把原档**覆盖销毁**（实测：7 级 / 9999 金币的档被改成
    # 1 级 / 0 金币，全程零报错）。真值判据 = 「这一行不存在」，坏档不是「不存在」。
    if not row:
        return None
    try:
        v = json.loads(row["data"])
    except Exception as _e:
        raise RuntimeError(
            "content.persistence.get_player：存档行存在但 JSON 解析失败（group_id=%r uid=%r）——"
            "拒绝返回 None（None = 新玩家，引擎会走建号初始化并覆盖销毁原档）"
            % (group_id, uid)
        ) from _e
    if not isinstance(v, dict):
        raise RuntimeError(
            "content.persistence.get_player：存档行的 data 顶层不是 dict（group_id=%r uid=%r，"
            "实际 %s）—— 拒绝当作无存档返回 None（否则同上一条：覆盖销毁原档）"
            % (group_id, uid, type(v).__name__)
        )
    return v


def update_player(group_id, uid, **fields):
    """落档 —— ★ **字段式**：宿主逐字就是 `half().update_player(group_id, uid, **fields)`
    （`host/store_factory.py::HostStore.save_player`，一条消息一次、整档拆成字段传进来）。

    ★★ 形状别改成 `(group_id, uid, data)` 那种整档入参 —— 2026-09-25 换包上线实测：
      签名错位 ⇒ **每条指令都 `TypeError: unexpected keyword argument 'name'`**（与
      「表名撞车」同一轮抓出来的第二处；奥兰迪亚半边也是 `(g, qq_id, **fields)`）。
    口径 = **读-改-写**：把这几格盖到库里那一行上（与奥兰迪亚那半边的字段式 UPDATE 同义）。

    ★ 不另抄一份「合法字段」白名单：玩家档那个 dict 的形状真源在包里（`cmds_ast.DEFAULT_PLAYER`
      + 各域自己那几格），本半边只负责把它整块存下来。
    """
    if not fields:
        return False
    with _LOCK:
        c = connect()
        try:
            row = c.execute("SELECT data FROM %s WHERE group_id=? AND uid=?" % TBL,
                            (str(group_id or ""), str(uid or ""))).fetchone()
            cur = {}
            if row:
                # ★ 审计 L1701-同族（写口）：读口 get_player 已在同一次修复里 fail-closed，
                #   而这里仍把坏档塌成 {} —— 读-改-写会拿这个空 dict 当底，**下一次任意
                #   落档就把原档覆盖销毁**（实测：7 级 / 9999 金币 → 1 级 / 0 金币，rc=True、
                #   零报错）。两处必须同口径：行存在而内容坏 ⇒ 抛，绝不自己造一个空档。
                try:
                    cur = json.loads(row["data"])
                except Exception as _e:
                    c.close()
                    raise RuntimeError(
                        "content.persistence.update_player：存档行存在但 JSON 解析失败"
                        "（group_id=%r uid=%r）—— 拒绝从空档重建（会把原档覆盖销毁）"
                        % (group_id, uid)
                    ) from _e
                if not isinstance(cur, dict):
                    c.close()
                    raise RuntimeError(
                        "content.persistence.update_player：存档行的 data 顶层不是 dict"
                        "（group_id=%r uid=%r，实际 %s）—— 拒绝从空档重建（会把原档覆盖销毁）"
                        % (group_id, uid, type(cur).__name__)
                    )
            if not isinstance(cur, dict):
                cur = {}
            cur.update(fields)
            blob = json.dumps(cur, ensure_ascii=False, separators=(",", ":"))
            c.execute("INSERT INTO %s(group_id, uid, data, updated_at) VALUES(?,?,?,?) "
                      "ON CONFLICT(group_id, uid) DO UPDATE SET data=excluded.data, "
                      "updated_at=excluded.updated_at" % TBL,
                      (str(group_id or ""), str(uid or ""), blob, clock()))
            c.commit()
        finally:
            c.close()
    return True


# ── 附带查询（宿主/编辑器用） ───────────────────────────────
def get_player_groups():
    """**广播群表**（引擎零参调的那一口，审计 L1702）—— 所有有玩家注册/活跃过的群号。

    ★ 签名是**宿主契约**，不是随手写的：引擎 `host/shell.py::_group_table()` 逐字
      `self._store.get_player_groups()`（**零参**），`_broadcast()` 的扇出全走它
      ⇒ 原先写成 `get_player_groups(uid)` 时升级即 `TypeError`，而包内**零生产消费者**
      （只有探针按 uid 调）⇒ 跑包内测试永远照不出来。
      奥兰迪亚那份同名口（`content/persistence/players.py::get_player_groups`）也是零参，
      两款游戏同一契约。
    ★ 「某个人在哪几个群」是**另一个问题**，走 `groups_of_player(uid)` —— 不塞可选参数进来：
      两套语义（群表 / 单人分布）名字必须能各自说清，否则调用方迟早拿错那一支。
    """
    with _LOCK:
        c = connect()
        try:
            rows = c.execute("SELECT DISTINCT group_id FROM %s" % TBL).fetchall()
        finally:
            c.close()
    return [r["group_id"] for r in rows]


def groups_of_player(uid):
    """某个 uid 落在哪几个群（**不是**广播群表 —— 那口是 `get_player_groups`）。"""
    with _LOCK:
        c = connect()
        try:
            rows = c.execute("SELECT group_id FROM %s WHERE uid=?" % TBL,
                             (str(uid or ""),)).fetchall()
        finally:
            c.close()
    return [r["group_id"] for r in rows]


def all_players(group_id=None):
    with _LOCK:
        c = connect()
        try:
            if group_id is None:
                rows = c.execute("SELECT group_id, uid, data FROM %s" % TBL).fetchall()
            else:
                rows = c.execute("SELECT group_id, uid, data FROM %s WHERE group_id=?" % TBL,
                                 (str(group_id),)).fetchall()
        finally:
            c.close()
    out = []
    for r in rows:
        try:
            d = json.loads(r["data"])
        except Exception:
            d = {}
        out.append({"group_id": r["group_id"], "uid": r["uid"], "data": d})
    return out


# ── 按群存的共同档（★ B3-26：多人在场时的「场」这类数据） ─────────
def meta_key(scope, group_id) -> str:
    """共同档的键 `<scope>:<group_id>` —— 形状只有这一处，别在调用方拼。"""
    s = str(scope or "").strip()
    if not s or META_SEP in s:
        raise ValueError("scope 必须是非空且不含 %r 的简单词：%r" % (META_SEP, scope))
    return "%s%s%s" % (s, META_SEP, str(group_id or ""))


def group_get(scope, group_id):
    """读一条按群存的共同档（没写过 → None）。

    ★ fail-closed 两档（与 `get_player` 有意不同，理由在下面）：
      · 行不在 = **没写过** ⇒ None（调用方按「没有这一场」处理）；
      · 行在、但值不是 JSON 对象 = **写坏了** ⇒ 当场抛 —— 静默回 None 会让
        「这一场」凭空消失（打到一半的战斗被当成没开过），宁可喊出来。
    """
    with _LOCK:
        c = connect()
        try:
            row = c.execute("SELECT v FROM %s WHERE k=?" % TBL_META,
                            (meta_key(scope, group_id),)).fetchone()
        finally:
            c.close()
    if not row:
        return None
    try:
        v = json.loads(row["v"])
    except Exception as e:                                   # noqa: BLE001
        raise RuntimeError("%s：共同档 %s 读不出来（数据坏了，不当成「没有」）：%s"
                           % (__name__, meta_key(scope, group_id), e))
    if not isinstance(v, dict):
        raise RuntimeError("%s：共同档 %s 不是一个对象（%r）"
                           % (__name__, meta_key(scope, group_id), type(v).__name__))
    return v


def group_set(scope, group_id, value) -> bool:
    """写一条按群存的共同档（整条覆盖；值必须是 JSON 对象）。"""
    if not isinstance(value, dict):
        raise ValueError("共同档只存对象（不是对象就别塞）：%r" % (type(value).__name__,))
    blob = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    with _LOCK:
        c = connect()
        try:
            c.execute("INSERT INTO %s(k, v) VALUES(?,?) "
                      "ON CONFLICT(k) DO UPDATE SET v=excluded.v" % TBL_META,
                      (meta_key(scope, group_id), blob))
            c.commit()
        finally:
            c.close()
    return True


def group_del(scope, group_id) -> bool:
    """删一条按群存的共同档（没写过也回 True —— 幂等）。"""
    with _LOCK:
        c = connect()
        try:
            c.execute("DELETE FROM %s WHERE k=?" % TBL_META, (meta_key(scope, group_id),))
            c.commit()
        finally:
            c.close()
    return True


def player_handles():
    """包内取件口（正本 = 本模块）。"""
    return _H
