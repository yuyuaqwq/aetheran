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
    → 本模块 `bind(**handles)`：`db_path`（必给）/ `clock` / `log` / `tlog` / `grant_reward` …

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
           "get_player", "update_player", "get_player_groups", "all_players"]

#: 存档表名（★ 带包前缀，理由见模块开头）；列 = 存档那一行的形状
TBL = "aetheran_players"
COLS = ("group_id", "uid", "data", "updated_at")

_H = {"db_path": None, "clock": None, "log": None, "tlog": None,
      "attach_tlog": None, "grant_reward": None}
_LOCK = threading.RLock()
_local = threading.local()


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
    c.execute("""CREATE TABLE IF NOT EXISTS aetheran_meta (
        k TEXT PRIMARY KEY, v TEXT)""")
    # ★ `IF NOT EXISTS` 撞上同名的**别人的**表时会**静默跳过**（2026-09-25 换包上线实测：
    #   奥兰迪亚的 `players` 在同一个库里 ⇒ 每次查询都 `no such column: data`）⇒ 当场核列、不对就抛。
    got = {r["name"] for r in c.execute("PRAGMA table_info(%s)" % TBL)}
    if got != set(COLS):
        c.close()
        raise RuntimeError("%s：存档表 %s 的列不对（期望 %s，实际 %s）—— 撞上同名的别的表了？"
                           % (__name__, TBL, sorted(COLS), sorted(got)))
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
    if not row:
        return None
    try:
        v = json.loads(row["data"])
    except Exception:
        return None
    return v if isinstance(v, dict) else None


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
                try:
                    cur = json.loads(row["data"])
                except Exception:                      # 库里那行坏了 ⇒ 从头来（不把坏数据当档）
                    cur = {}
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
def get_player_groups(uid):
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


def player_handles():
    """包内取件口（正本 = 本模块）。"""
    return _H
