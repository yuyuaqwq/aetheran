# -*- coding: utf-8 -*-
"""《阿斯特兰》限时事件半边（`content/timed_events.py`）—— 宿主维护门插口（B3-5）。

为什么有这个文件
----------------
宿主壳（`host/shell.py::_maint_gate`）**每轮按半边名**取本模块：

    self._sub("timed_events").refresh_timed(group_id, qq_id)

包原先没有这一半 ⇒ 日志里每轮一条 `[timed_events] _maint_gate 刷新失败（不影响指令主流程）`。
本文件把那个插口补上（B3-5 · 台账 §3 的硬约束）。

这一半干什么（口径：`06_第一阶段垂直切片/29_世界事件_设计_v1.md` §一 / §二）
--------------------------------------------------------------------
世界事件是「当前是否成立」的**纯函数**（判定只有一处 = `content/calendar.py`；三尺度都只是
一个布尔，**谁都不存历史**）。但「限时 = 开一段、关一段」这件事需要留一格给**呈现口**：
玩家再上线时要能看出「哪件是新开的、哪件收了」。所以本模块唯一的职责是**推进那一格**：

    flags.ev = {"day": <上次刷新时的游戏日>, "on": [<那次成立着的窗键>],
                "prev_day": <再上一格那天>, "prev_on": [<再上一格的窗键>]}

消费端 = 「异动」（`content/cmds_ast.py::event_now`）：拿 `prev_on` 与此刻现算的窗比对，
说「今天新开的」/「收了」。宿主每轮先跑本模块、再走指令 ⇒ 指令读到的是**刷新后的那一格**。

★ 三条纪律（宿主每轮都调它，写坏了就是每条指令都脏）：
  ① **幂等**：同一天、同一组窗 ⇒ 一个字节都不写（第二次调用零动作）
  ② **绝不抛**：整段包在 try 里 —— 宿主那边的 except 只打一条 WARN，本半边不该靠它兜
  ③ **没到点 / 没事件 ⇒ 零动作**：连那一格都不建（新号没建档也一样）

窗键怎么拼只在 `calendar.window_key` 一处（键格式是内容侧口径，别处不许自己拼）。
"""
from __future__ import annotations

from . import calendar as CAL
from . import facade

__all__ = ["refresh_timed", "snapshot", "STATE_KEY"]

#: 档上那一格的名字（`flags.ev`）
STATE_KEY = "ev"


def _store():
    """存档半边（正本 = `content/persistence.py`；经包门面取件 —— 包内不 import 宿主）。"""
    return getattr(facade, "persistence", None)


def _log(msg):
    """一条诊断给运维看（ASCII —— 玩家看不到；宿主没注入口就算了）。"""
    try:
        facade.log("[timed_events] " + str(msg))
    except Exception:                                          # noqa: BLE001
        pass


def snapshot(p) -> dict:
    """档上那一格（**读口**：呈现口与探针都走它，别自己翻 flags）。"""
    return dict(((p or {}).get("flags") or {}).get(STATE_KEY) or {})


def refresh_timed(group_id, qq_id):
    """宿主维护门（每条消息一次）：把「今天世界开着哪些窗」推到档上那一格。

    返回一个诊断 dict（宿主不解释返回值）：`{"changed": bool, "why"/"day"/"on"…}`。
    """
    try:
        ps = _store()
        if ps is None:
            return {"changed": False, "why": "no-store"}
        p = ps.get_player(group_id, qq_id)
        if not isinstance(p, dict):
            return {"changed": False, "why": "no-player"}       # 还没建档 ⇒ 零动作
        st = CAL.state()                                        # 钟 = 宿主注入的那根（facade.clock）
        today = int(st["game_day"])
        cur = CAL.on_keys(st, p)                                # 此刻成立的那些窗（唯一口）
        old = snapshot(p)
        if int(old.get("day") if old.get("day") is not None else -1) == today \
                and list(old.get("on") or []) == list(cur):
            return {"changed": False, "why": "same-window"}     # ★ 幂等（宿主每轮都调）
        if not cur and not (old.get("on") or []):
            return {"changed": False, "why": "nothing-due"}     # ★ 没事件、也没历史 ⇒ 零动作
        flags = dict(p.get("flags") or {})                      # ★ K57 口径：容器换新对象再写
        flags[STATE_KEY] = {"day": today, "on": list(cur),
                            "prev_day": old.get("day"), "prev_on": list(old.get("on") or [])}
        ps.update_player(group_id, qq_id, flags=flags)          # ★ 字段式（宿主逐字这么调）
        _log("refresh day=%s on=%s prev=%s" % (today, cur, old.get("on")))
        return {"changed": True, "day": today, "on": list(cur)}
    except Exception as exc:                                    # noqa: BLE001 —— ★ 绝不抛
        _log("refresh failed: %s: %s" % (type(exc).__name__, exc))
        return {"changed": False, "why": "error"}
