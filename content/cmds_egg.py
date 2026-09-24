# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 彩蛋（B3-1）

一条指令（04_指令总表 §八 图鉴与记录那一族）：**彩蛋** —— 看自己把哪些事连起来了。
口径与文案真源：`00_总纲/15_彩蛋域口径_v1.md`（条目在 eggs 域 · 框架话在 texts 域）。

★ 这一组**不写档**（只看不改）—— 连起来那一下发生在 观察 / 触摸 / 地图 / 搭话 后面
  （触发在 `content/cmds_ast.py::egg_lines`）。
"""
from __future__ import annotations

from .cmds_ast import _p, T
from . import eggs as EG


async def eggs_book(env, sink, uid, player):
    p = _p(player)
    b = EG.built(p)
    if not b:
        yield T("SYS_EGG_NONE")
        return
    yield T("SYS_EGG_HEAD", n=len(b), total=EG.total())
    for _eid, title, line in b:
        yield T("SYS_EGG_ROW", title=title)
        yield T("SYS_EGG_ROW_LINE", line=line)
    lf = EG.left(p)
    if lf:
        yield T("SYS_EGG_TAIL", left=lf)
