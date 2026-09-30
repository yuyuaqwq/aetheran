# -*- coding: utf-8 -*-
"""《阿斯特兰》包级门面（`content/facade.py`）—— **宿主注入的单点**。

`game.json` 的 `bind` 声明指向本模块：

    "bind": {"module": "content/facade.py", "func": "bind_host"}

引擎在**加载期**（import 包命令模块之前）调它一次，把宿主给的注入 dict 交给包；
包内各模块不 import 宿主，只向本门面取件（与奥兰迪亚同形，不另发明第三套）。

注入键（宿主 `host/store_factory.py::inject_handles()` 给）：
    db_path · clock · log · tlog · attach_tlog · grant_reward
"""
from __future__ import annotations

__all__ = ["bind_host", "HANDLES", "persistence", "db_path", "clock", "log", "tlog"]

# ★ 2026-09-30 审计残余 #11：手写 6 行注入样板 → 引擎 `wire.slot()`（「这段样板在包里
#   抄了 37 遍」的第 38 遍就此收口）。存储面（增量 · `None` = 不改 · 整批校验再落盘）
#   由引擎单源提供；`HANDLES` 从「本模块的字典」变成 wire 存储面的**只读活视图**
#   —— 名字与读者逐字不变（`probe_codex` ⑯ 钉的增量口径就是这个面）。
from saintess_engine.wire import slot as _slot

from . import persistence

#: 觉察口（`log` / `tlog`）与宿主注入的句柄（wire 存储面的只读活视图 · **增量口径**
#: —— 与 `persistence.bind`（`None` / 缺省 = 不改）同一口径）。
_WIRE, _bind_wire = _slot()
HANDLES = _WIRE.handles()


def bind_host(**inject):
    """宿主注入入口。返回收到的键（引擎不解释返回值，只为便于诊断）。

    ★ **增量、`None` = 不改、绝不 `clear()`**（引擎 L2711 口径）—— 2026-09-30 起由引擎
      `wire.slot()` 单源提供。历史教训留一句：原先这里整个 `clear()` 再 `update`，
      于是二次 `bind_host(clock=…)` 会把 `HANDLES` 洗成只剩 `{clock}`、而
      `persistence._H` 照旧保留全部键 ⇒ 同一批句柄出两个真相，且 `facade.log(…)`
      静默返 `None`（宿主回调未被调用、日志直接丢、零报错）。
    本函数只做包内两件事：把**累积面**转发给 `persistence.bind`（它自己那格同口径增量，
    两边才不会对同一批句柄给出不同答案）、返回诊断。
    """
    _bind_wire(**inject)
    persistence.bind(**HANDLES)
    return {"bound": sorted(HANDLES)}


def db_path():
    return persistence.db_path()


def clock():
    return persistence.clock()


def log(msg, *a, **kw):
    fn = HANDLES.get("log")
    if callable(fn):
        return fn(msg, *a, **kw)
    return None


def tlog():
    return HANDLES.get("tlog")
