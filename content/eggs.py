# -*- coding: utf-8 -*-
"""《阿斯特兰》彩蛋（B3-1）—— 十条「跨文本呼应」的**唯一**进出面。

口径真源：`00_总纲/15_彩蛋域口径_v1.md`（条件语汇 · 文案 · 触发表）。
分工：
  · 数据（十条：标题 / 两端 / 发现方式 / 揭示文案 / 条件）= `content/data/eggs.json`
    （`scripts/rebuild_eggs.py` 从 19 文档 + 口径文档解析，禁手打）
  · 判定 = 引擎 `saintess_engine.conditions.declarative` 的通用算子 —— 本模块只**出 ctx**，
    不自己写条件求值器（要加算子就加引擎的）
  · 记录（谁把哪两件事连起来了）= 玩家档的 `eggs` 一格 —— ★ 只在这里写
  · 呈现 = `content/cmds_egg.py`（文案槽位在 texts 域）

★ 玩家档只多一个键（加出来的，老档不用迁移）：
    eggs = {"<egg id>": {"day": <第几个游戏日>}}

★ 撞上那一下是**幂等**的：条件不满足什么都不发生；连起来过的不再报第二遍。
"""
from __future__ import annotations

import json
import os

from saintess_engine.conditions.declarative import compile_specs

from . import calendar as CAL

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_C: dict = {}
_SPECS = None


def _d(name: str):
    if name not in _C:
        with open(os.path.join(_DIR, name + ".json"), encoding="utf-8") as f:
            _C[name] = json.load(f)
    return _C[name]


# ── 数据 ──────────────────────────────────────────────────────
def data() -> dict:
    return _d("eggs")


def entries() -> dict:
    """十条彩蛋（`_` 前缀 = 私有键，不是条目）。"""
    return {k: v for k, v in data().items() if not str(k).startswith("_")}


def entry(eid: str) -> dict:
    return entries().get(str(eid)) or {}


def title_of(eid: str) -> str:
    """两条相呼应的东西（照 19 文档那一行）。

    ★ L2373：读不到标题**点名抛**，不再回落 `str(eid)`。回落会把机器键
    （`egg_one_hand`）原样塞进玩家可见的 `SYS_EGG_FOUND` 抬头（`cmds_ast.py:809`）
    ⇒ 条件/数据配错时玩家看到的是「你忽然把两件事连起来了 —— egg_one_hand」，
    而入口 `scan()` 不报错、别处也无从发现。认不出 ⇒ 抛（本项目核心铁律）。
    """
    e = entry(eid)
    t = e.get("title")
    if not t:
        raise KeyError("eggs 域条目 %r 缺 title（抬头是玩家可见文案，不许回落成机器键）" % (eid,))
    return t


def line_of(eid: str) -> str:
    """连起来之后那句话（真源在 eggs 域，代码只传槽位）。"""
    return entry(eid).get("line") or ""


def pair_of(eid: str) -> list:
    return list(entry(eid).get("pair") or [])


def how_of(eid: str) -> str:
    return entry(eid).get("how") or ""


def total() -> int:
    """彩蛋总条数 —— ★ **全包唯一一处**算它的地方（台账 L2376 判据 3）。

    ★ 原先 `_meta.count` 与这里 `len(entries())` **各自算同一个量**（两个维护点），
      域里加/删一条就得改两处，漏一处就静默分叉。现已删掉域里的那一格：
      条数只在这里现算，`_meta` 只留**说明性**字段（title / source / spec）。
    """
    return len(entries())


def specs() -> dict:
    """egg id → 判定函数（声明节点编译一次；形状不对当场抛，不静默）。"""
    global _SPECS
    if _SPECS is None:
        _SPECS = compile_specs({k: v["cond"] for k, v in entries().items()})
    return _SPECS


# ── ctx：出题口（唯一）────────────────────────────────────────
def ctx(p: dict, st: dict | None = None) -> dict:
    """「现在的世界 + 这个人的经历」→ 一份扁平上下文（条件声明只认它）。

    ★ 时辰/天气照 `calendar.state()`、足迹与两本谱照 `codex` 的取件口 ——
      别处不许自己翻档（单一真源）。
    """
    from .cmds_ast import _data            # 本地 import：避免包装载期与 cmds_ast 成环
    from . import codex as CX
    st = st or CAL.state()
    worn = {str(x) for x in (p.get("equipped") or {}).values()}
    hold = set(p.get("bag") or {}) | worn
    items = _data("items")
    flags = p.get("flags") or {}
    return {
        "where": "%s:%s" % (p.get("loc") or "", p.get("node") or ""),
        "map": str(p.get("loc") or ""),
        "race": str(p.get("race") or ""),
        "lore_scripts": bool(str(p.get("race") or "") == "elf" or flags.get("lore_scripts")),
        "read": {k for k in CX.book("relic") if CX.has(p, "relic", k)},
        "been": set((p.get("foot") or {}).get("nodes") or {}),
        "hold": hold,
        "worn": worn,
        "set": {sid for sid in ((items.get(i) or {}).get("set_id") for i in hold) if sid},
        "done": set(flags.get("quests_done") or []),
        "kill": {k for k in CX.book("monster") if CX.kills_of(p, k) > 0},
        "hour": st["hour_name"],
        "weather": st["weather_name"],
        "day": CAL.day_now(),                     # ★ B4-9：日期戳现算（别读档上那格）
        "level": int(p.get("level") or 1),
    }


# ── 档上的那一格 ──────────────────────────────────────────────
def found(p: dict) -> dict:
    e = p.get("eggs")
    if not isinstance(e, dict):
        e = {}
        p["eggs"] = e
    return e


def has(p: dict, eid: str) -> bool:
    return str(eid) in found(p)


def count(p: dict) -> int:
    return len(found(p))


def left(p: dict) -> int:
    return max(0, total() - count(p))


def built(p: dict) -> list:
    """已连起来的（顺序 = 数据里的顺序）→ `[(id, 标题, 那句话)]`。"""
    b = found(p)
    return [(k, title_of(k), line_of(k)) for k in entries() if k in b]


def scan(p: dict, st: dict | None = None) -> list:
    """扫一遍 → 这次够格连起来的那几条（★ 顺手写进档）。

    没有新发现就什么都不做（不落「没连起来」的记录 —— 免得泄漏答案）。
    """
    cur = ctx(p, st)
    book = found(p)
    fn = specs()
    new = []
    for eid in entries():
        if eid in book:
            continue
        if fn[eid](cur):
            book[eid] = {"day": CAL.day_now()}      # ★ B4-9：日期戳现算（别读档上那格）
            new.append(eid)
    return new
