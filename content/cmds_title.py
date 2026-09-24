# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 称号（B3-2）

一条指令（04_指令总表 §八 图鉴与记录那一族）：**称号** —— 看自己挣到了哪些名字。
口径与显示规则真源：`00_总纲/16_称号域口径_v1.md`（条目在 titles 域 · 框架话在 texts 域）。

★ 这一组**不写档**（只看不改）—— 拿到那一下发生在 观察 / 触摸 / 地图 / 搭话 后面
  （触发在 `content/cmds_ast.py::title_lines`）。
★ 没拿到的不列出来（免得剧透）—— 与彩蛋册同一条纪律。
"""
from __future__ import annotations

from .cmds_ast import _p, T
from . import titles as TT


async def titles_book(env, sink, uid, player):
    p = _p(player)
    g = TT.got(p)
    if not g:
        yield T("SYS_TITLE_NONE")
        return
    yield T("SYS_TITLE_HEAD", n=len(g), total=TT.total())
    for _tid, name, how, _day in g:
        yield T("SYS_TITLE_ROW", name=name, how=how)
    lf = TT.left(p)
    if lf:
        yield T("SYS_TITLE_TAIL", left=lf)
