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

from . import persistence

#: 觉察口（`log` / `tlog`）与宿主注入的句柄。**增量口径**
#: —— 与 `persistence.bind`（`None` / 缺省 = 不改）同一口径。
HANDLES: dict = {}


def bind_host(**inject):
    """宿主注入入口。返回收到的键（引擎不解释返回值，只为便于诊断）。

    ★ 为什么不再 `clear()`（引擎 L2711）：
        两边句柄口径相反 —— `persistence.bind` 是**增量**（`None` = 不改），
        而这里原先整个 `clear()` 再 `update`，于是**覆盖**。
        实跑：全绑 `{db_path,clock,log,tlog}` → 另起一次 `bind_host(clock=…)`
          → `HANDLES` 只剩 `{clock}`，而 `persistence._H` 照旧保留全部 6 个
          ⇒ **同一批句柄出两个真相**，且 `facade.log(…)` 静默返 `None`（
          宿主回调**未被调用**，日志直接丢、零报错）。
        口径：两边同一个「增量、`None` = 不改」，`HANDLES` 和
        `persistence._H` 才不会对同一批句柄给出不同答案。
    """
    for _k, _v in (inject or {}).items():
        if _v is not None:
            HANDLES[_k] = _v
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
