# -*- coding: utf-8 -*-
"""《阿斯特兰》存档层（`content/persistence.py`）—— 宿主**半边**之一。

宿主契约（`host/store_factory.py::StoreFactory.HALF`）要求本模块提供五个口：
`get_player` / `update_player` / `init_db` / `lock` / `connect`。缺一个宿主就
**拒绝静默空跑**（抛 RuntimeError）—— 这是有意的：宁可起不来，也不要静默存不上档。

注入面（与奥兰迪亚同形，不另发明第三套）：
    宿主 `inject_handles()` → 引擎 `inject` → 引擎调包内 `bind_host(**inject)`
    → 本模块 `bind(**handles)`：`db_path`（必给）/ `clock` / `log` / `tlog` / `grant_reward` …

★ 不改动存档库路径的来历 —— 它是**部署信息**，由宿主解析后注入；包不知道自己在哪台机器上跑。
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time

__all__ = ["bind", "db_path", "clock", "init_db", "lock", "connect",
           "get_player", "update_player", "get_player_groups", "all_players"]

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
    """新连接（调用方负责关闭）。表结构随第一次连接自动建好。"""
    p = db_path()
    d = os.path.dirname(p)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    c = sqlite3.connect(p, timeout=10.0)
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS players (
        group_id TEXT NOT NULL, uid TEXT NOT NULL, data TEXT NOT NULL,
        updated_at REAL NOT NULL, PRIMARY KEY (group_id, uid))""")
    c.execute("""CREATE TABLE IF NOT EXISTS aetheran_meta (
        k TEXT PRIMARY KEY, v TEXT)""")
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
            row = c.execute("SELECT data FROM players WHERE group_id=? AND uid=?",
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


def update_player(group_id, uid, data):
    """落档（整档覆盖）。"""
    if not isinstance(data, dict):
        return False
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    with _LOCK:
        c = connect()
        try:
            c.execute("INSERT INTO players(group_id, uid, data, updated_at) VALUES(?,?,?,?) "
                      "ON CONFLICT(group_id, uid) DO UPDATE SET data=excluded.data, "
                      "updated_at=excluded.updated_at",
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
            rows = c.execute("SELECT group_id FROM players WHERE uid=?", (str(uid or ""),)).fetchall()
        finally:
            c.close()
    return [r["group_id"] for r in rows]


def all_players(group_id=None):
    with _LOCK:
        c = connect()
        try:
            if group_id is None:
                rows = c.execute("SELECT group_id, uid, data FROM players").fetchall()
            else:
                rows = c.execute("SELECT group_id, uid, data FROM players WHERE group_id=?",
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
