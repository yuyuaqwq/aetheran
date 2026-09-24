# -*- coding: utf-8 -*-
"""《阿斯特兰》flow 半边 · 周常进度（`content/flow/weekly_progress.py`）。

为什么有这个文件：宿主的启动自检（`main.py::_weekly_reward_selfcheck`）要求
「`flow` 半边在 + `weekly_progress` 可导入 + `selfcheck()` 可调」—— 缺就**拒绝启动**
（fail-closed，实测过：宿主宁可起不来，也不要「玩家达标却静默不发奖」）。

★ 第一阶段**还没开周常**（那是长期目标层的事）。但半边必须**在位且诚实**：
  本文件的 `selfcheck()` 明确回报「本包未启用周常」，**不是**假装通过。
"""
from __future__ import annotations

__all__ = ["selfcheck", "bump", "progress_of", "reset"]

STATE_KEY = "weekly_progress"


def _store():
    """宿主存储口（经包门面取；缺 → None，不炸）。"""
    try:
        from .. import facade
        return facade.HANDLES.get("persistence")
    except Exception:
        return None


def selfcheck() -> str:
    """启动自检：返回一行可读结论（**不抛** = 本包没有会让玩家静默吃亏的周常链路）。"""
    return ("阿斯特兰周常自检：本包第一阶段未启用周常发奖（无静默失效风险）"
            " —— 周常属长期目标层，开放时本模块会补 bump/grant 并同步收紧自检")


def bump(uid, key, n=1):
    """加进度（第一阶段为占位：只回报，不落库）。"""
    return {"uid": str(uid), "key": str(key), "n": int(n), "applied": False,
            "why": "第一阶段未启用周常"}


def progress_of(uid):
    """读某人的周常进度（第一阶段恒空）。"""
    return {}


def reset():
    """重置（第一阶段无操作）。"""
    return False
