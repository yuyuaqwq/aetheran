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


def _peek(p: dict) -> dict:
    """只读口：档上那一格（缺键/坏值 ⇒ 空表）—— **绝不写档**（读不改档）。

    ★ 审计残余 #12：原 `_h` 读写合一 —— `counts()` 跑一次就在空档上落出 `heard` 键、
      坏值（list 那类）被**就地替换成 `{}`**（读路径吞证据）。现在读走这里：
      坏值**留原值**（本次返回空、档一个字节不动）；写只在 `note` 的 `_h`。
    """
    h = (p or {}).get("heard")
    return h if isinstance(h, dict) else {}


def _h(p: dict) -> dict:
    """写口专用（`note` 唯一入口）：确保存在可写的容器。

    顶层坏值**不再静默替换** —— 留原值当场抛（写路径同样不许吞证据；审计残余 #12）。
    """
    h = p.get("heard")
    if h is None:
        h = {}
        p["heard"] = h
        return h
    if not isinstance(h, dict):
        raise RuntimeError("档上 `heard` 形状坏了（要 dict，拿到 %s）—— 留原值待修，拒绝静默覆盖"
                           % type(h).__name__)
    return h


def _today(p: dict) -> int:
    """「今天是第几个游戏日」—— 与 `codex.today` **同一个口**（现算，不读档上那格）。

    ★ B4-9：理由见 `calendar.day_now` 的注释（档上那格只是 tick 的跨日标记）。
    ★ 审计残余 #31：原名 `today` 是**死导出**（全仓 0 生产消费）—— 改名收进模块私有面。
    """
    from . import calendar as CAL                  # 本地 import：免得装载期成环
    return CAL.day_now()


def note(p: dict, dlg_id: str, group: str, idx: int) -> bool:
    """他说出口了一句 → 记下（★ 只记第一次）。返回这次是不是新的一句。"""
    h = _h(p)
    d = h.get(str(dlg_id))
    if d is None:
        d = {}
        h[str(dlg_id)] = d
    elif not isinstance(d, dict):
        raise RuntimeError("档上 heard[%r] 形状坏了（要 dict，拿到 %s）—— 句级账留原值待修"
                           % (dlg_id, type(d).__name__))
    key = "%s#%s" % (group, idx)
    if key in d:
        return False
    d[key] = _today(p)
    return True


def counts(p: dict) -> dict:
    """对话树 id → 听过几句（出题口 `heard` 那个键要的形状）。"""
    return {k: len(v) for k, v in _peek(p).items() if isinstance(v, dict)}


def lines(p: dict, dlg_id: str) -> list:
    """听过的那几句（顺序 = 记下的顺序）→ `["层#序号", …]`。"""
    d = _peek(p).get(str(dlg_id))
    return list(d.keys()) if isinstance(d, dict) else []
