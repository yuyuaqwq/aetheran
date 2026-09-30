# -*- coding: utf-8 -*-
"""《阿斯特兰》称号（B3-2）—— 十个称号的**唯一**进出面。

口径真源：`00_总纲/16_称号域口径_v1.md`（条件语汇 · 显示规则 · 可达性）。
分工：
  · 数据（十条：名 / 怎么拿到 / 条件 / 显示位置）= `content/data/titles.json`
    （`scripts/rebuild_titles.py` 从 21 文档 + 口径文档解析，禁手打）
  · 判定 = 引擎 `saintess_engine.conditions.declarative` 的通用算子 —— 本模块只**出 ctx**
  · 出题口 = `content/eggs.py::ctx`（★ 与彩蛋同一套语汇，本模块只在它上面加 6 个键 ——
    免得两处各算一套「去过哪儿 / 有什么」）
  · 记录 = 玩家档的 `titles` 一格 —— ★ 只在这里写
  · 呈现 = 显示形态跟着名字走（`content/cmds_ast.py` 的 观察 / 状态）· 称号册在 `content/cmds_title.py`

★ 玩家档只多一个键（加出来的，老档不用迁移）：
    titles = {"<title id>": {"day": <第几个游戏日>}}

★ 称号**不给任何数值**（21 §一：称号是荣誉，不是装备）；拿到那一下也是幂等的。
★ 显示只显示**最近拿到的那个**（21 §一「同上（替换）」）—— 全都在 `cmds_title.py` 里列。
"""
from __future__ import annotations

from saintess_engine.conditions.declarative import compile_specs

from . import calendar as CAL
from . import eggs as EG
from . import heard as HD

_SPECS = None


# ── 数据 ──────────────────────────────────────────────────────
def data() -> dict:
    # ★ 2026-09-30 审计残余 #46：读表收敛到 `content.cmds_ast._data`（仓内唯一的域读口）——
    #   本模块被 `cmds_ast` 在装载期 import ⇒ 顶层引会成环（titles → cmds_ast → titles）。
    from .cmds_ast import _data                        # ★ 域读口（与别处同一个）
    return _data("titles")


def entries() -> dict:
    """十个称号（`_` 前缀 = 私有键，不是条目）。"""
    return {k: v for k, v in data().items() if not str(k).startswith("_")}


def meta() -> dict:
    return dict(data().get("_meta") or {})


def entry(tid: str) -> dict:
    return entries().get(str(tid)) or {}


def name_of(tid: str) -> str:
    return entry(tid).get("name") or str(tid)


def how_of(tid: str) -> str:
    """怎么拿到（照 21 文档那一行）。"""
    return entry(tid).get("how") or ""


def where_of(tid: str) -> str:
    """显示位置（口径 §一 的唯一一条显示规则）。"""
    return entry(tid).get("where") or ""


def total() -> int:
    return len(entries())


def specs() -> dict:
    """title id → 判定函数（声明节点编译一次；形状不对当场抛，不静默）。"""
    global _SPECS
    if _SPECS is None:
        _SPECS = compile_specs({k: v["cond"] for k, v in entries().items()})
    return _SPECS


# ── ctx：出题口（★ 底子就是 eggs 的那个 —— 只在它上面加后 6 个键）──────
EXTRA_KEYS = ("read_all", "mat", "visited", "heard", "interrupt", "clean", "horn")


def ctx(p: dict, st: dict | None = None) -> dict:
    """「现在的世界 + 这个人的经历」→ 一份扁平上下文（条件声明只认它）。

    ★ 前 13 个键由 `eggs.ctx` 出（同一套语汇，两个域不许各算一套）；
      后面这几个只有称号用得上：
        read_all  读过几处可读物（口径 §二 #2 的 12 = pois 里 into_codex 的条数 —— 就是 19 §三A
                  那 12 条量账；塔内那几条**就地线索**（`into_codex` 空串 · 22 §二「可做」列）
                  读完也不进谱、不往这里加，见工作树 `_notes.md` §一）
        mat       材料谱里有哪几样（夜里下网的：那条鱼在不在谱里）
        visited   去过几回（`codex.note_step` 记的账）· 值 {图:节点: 次数}
        heard     听过几句（`heard` 模块记的账）· 值 {对话树 id: 句数}
        interrupt 打断成功累计 · clean 无人倒地通关累计 · horn 修好的号角数
    """
    from .cmds_ast import _data            # 本地 import：避免包装载期与 cmds_ast 成环
    out = dict(EG.ctx(p, st))
    pois = _data("pois")
    books = p.get("books") or {}
    relic = books.get("relic") or {}
    foot = p.get("foot") or {}
    out["read_all"] = len([k for k, v in pois.items() if v.get("into_codex") and k in relic])
    out["mat"] = set((books.get("material") or {}).keys())
    out["visited"] = dict(foot.get("visits") or {})
    out["heard"] = HD.counts(p)
    out["interrupt"] = int(foot.get("interrupts") or 0)
    out["clean"] = int(foot.get("clears") or 0)
    out["horn"] = 1 if (p.get("flags") or {}).get("horn_fixed") else 0
    return out


# ── 档上的那一格 ──────────────────────────────────────────────
def held(p: dict) -> dict:
    t = p.get("titles")
    if not isinstance(t, dict):
        t = {}
        p["titles"] = t
    return t


def has(p: dict, tid: str) -> bool:
    return str(tid) in held(p)


def count(p: dict) -> int:
    return len(held(p))


def left(p: dict) -> int:
    return max(0, total() - count(p))


def got(p: dict) -> list:
    """已拿到的（顺序 = 数据里的顺序）→ `[(id, 名, 怎么拿到, 第几个游戏日)]`。"""
    h = held(p)
    out = []
    for k, v in entries().items():
        if k in h:
            out.append((k, name_of(k), how_of(k), int((h[k] or {}).get("day") or 0)))
    return out


def newest(p: dict):
    """最近拿到的那个（★ 显示只显示它 —— 21 §一「同上（替换）」）→ `(id, 名)` | None。

    同一天拿到两个：按数据里的顺序取靠后的那个（稳定，不靠字典序）。
    """
    h = held(p)
    best, best_key = None, None
    for i, k in enumerate(entries()):
        if k not in h:
            continue
        key = (int((h[k] or {}).get("day") or 0), i)
        if best_key is None or key > best_key:
            best, best_key = k, key
    return (best, name_of(best)) if best else None


def scan(p: dict, st: dict | None = None) -> list:
    """扫一遍 → 这次新挂上的称号 id（★ 顺手写进档；没有新的就什么都不做）。"""
    cur = ctx(p, st)
    h = held(p)
    fn = specs()
    new = []
    for tid in entries():
        if tid in h:
            continue
        if fn[tid](cur):
            h[tid] = {"day": CAL.day_now()}       # ★ B4-9：日期戳现算（别读档上那格）
            new.append(tid)
    return new
