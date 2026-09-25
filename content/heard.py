# -*- coding: utf-8 -*-
"""《阿斯特兰》听过什么（B3-2）—— 「哪句话他已经听过」的**唯一**记录口。

口径真源：`00_总纲/16_称号域口径_v1.md` §四（`p[heard]` 的形状）。
分工：
  · 写 = `content/cmds_talk.py`（说话成功那一下 —— 唯一写入口）
  · 读 = `content/titles.py::ctx` 的 `heard` 键（「听完哈根的全部对话」）
    ＋ `content/cmds_title.py`（称号那一行的小注：听过几句）

★ 玩家档只多一个键（加出来的，老档不用迁移）：
    heard = {"<对话树 id>": {"<层>#<序号>": <第几个游戏日>}}

★ 为什么按「层#序号」记：对话是按 need 条件择优的 —— 同一棵树的不同句子
  要在不同前置下才说得出来，「听全没听全」只能一句一句数。
"""
from __future__ import annotations


def _h(p: dict) -> dict:
    h = p.get("heard")
    if not isinstance(h, dict):
        h = {}
        p["heard"] = h
    return h


def today(p: dict) -> int:
    """「今天是第几个游戏日」—— 与 `codex.today` **同一个口**（现算，不读档上那格）。

    ★ B4-9：理由见 `calendar.day_now` 的注释（档上那格只是 tick 的跨日标记）。
    """
    from . import calendar as CAL                  # 本地 import：免得装载期成环
    return CAL.day_now()


def note(p: dict, dlg_id: str, group: str, idx: int) -> bool:
    """他说出口了一句 → 记下（★ 只记第一次）。返回这次是不是新的一句。"""
    h = _h(p)
    d = h.get(str(dlg_id))
    if not isinstance(d, dict):
        d = {}
        h[str(dlg_id)] = d
    key = "%s#%s" % (group, idx)
    if key in d:
        return False
    d[key] = today(p)
    return True


def count(p: dict, dlg_id: str) -> int:
    d = _h(p).get(str(dlg_id))
    return len(d) if isinstance(d, dict) else 0


def counts(p: dict) -> dict:
    """对话树 id → 听过几句（出题口 `heard` 那个键要的形状）。"""
    return {k: len(v) for k, v in _h(p).items() if isinstance(v, dict)}


def lines(p: dict, dlg_id: str) -> list:
    """听过的那几句（顺序 = 记下的顺序）→ `["层#序号", …]`。"""
    d = _h(p).get(str(dlg_id))
    return list(d.keys()) if isinstance(d, dict) else []
