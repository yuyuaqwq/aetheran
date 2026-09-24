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

#: 最近一次注入的句柄（只读用途；取件请用下面的函数）
HANDLES: dict = {}


def bind_host(**inject):
    """宿主注入入口。返回收到的键（引擎不解释返回值，只为便于诊断）。"""
    HANDLES.clear()
    HANDLES.update(inject or {})
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
