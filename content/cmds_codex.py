# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 第六组：图鉴与记录（B2-7）

六条指令（04_指令总表 §八）：图鉴 · 材料谱 · 风味谱 · 怪物谱 · 旧物谱 · 记录。
口径与文案真源：`00_总纲/14_图鉴四谱口径_v1.md`（条目在 codex 域 · 框架话在 texts 域）。

★ 这一组**不写档**（只看不改）—— 记录发生在采集/战斗/读书/走路那些地方（content/codex.py）。
"""
from __future__ import annotations

from .cmds_ast import _p, _save, T
from . import codex as CX

#: 空谱时那句话（每个谱自己一句 —— 文案在 texts 域）
EMPTY_SLOT = {"material": "SYS_CODEX_EMPTY_MATERIAL", "flavor": "SYS_CODEX_EMPTY_FLAVOR",
              "monster": "SYS_CODEX_EMPTY_MONSTER", "relic": "SYS_CODEX_EMPTY_RELIC"}


def _progress_row(bk: str, pr: dict):
    p_ = pr[bk]
    if bk == "relic":
        return T("SYS_CODEX_ROW_RELIC", book=CX.label(bk), n=p_["n"], q=p_["unknown"])
    return T("SYS_CODEX_ROW", book=CX.label(bk), n=p_["n"], target=p_["target"],
             note=_note_of(bk, p_))


def _note_of(bk: str, p_) -> str:
    """一行里那句小注（记满还差多少 / 已记满）。"""
    if p_["target"] and p_["n"] >= p_["target"]:
        return T("SYS_CODEX_FULL")
    if p_["target"]:
        return T("SYS_CODEX_TODO", left=p_["target"] - p_["n"])
    return ""


def new_lines(new) -> list:
    """`codex.note_items()` 的结果 → 一两行「进了哪本谱」（采集/战斗/烹饪都要说一声）。"""
    return [T("SYS_CODEX_NEW", book=CX.label(bk), name=CX.name_of(bk, rid)) for bk, rid in new]


def _sync_bag(p, player, env):
    """开谱时跟背包对账（补上没记过的）—— 补了就要落档。"""
    if CX.sync_bag(p):
        if player is not None:
            player.update(p)
        _save(env)


async def codex(env, sink, uid, player):
    p = _p(player)
    _sync_bag(p, player, env)
    pr = CX.progress(p)
    yield T("SYS_CODEX_HEAD")
    for bk in CX.BOOKS:
        yield _progress_row(bk, pr)
    yield T("SYS_CODEX_HINT")


async def _one_book(p, bk: str, rows):
    """一本谱：表头 + 一行一行（顺序 = 数据里的顺序）。"""
    pr = CX.progress(p)[bk]
    n = pr["n"]
    if not n:
        yield T(EMPTY_SLOT[bk])
        return
    if bk == "relic":
        yield T("SYS_CODEX_BOOK_HEAD_OPEN", book=CX.label(bk), n=n)
    else:
        yield T("SYS_CODEX_BOOK_HEAD", book=CX.label(bk), n=n, target=pr["target"])
    for line in rows:
        yield line
    if bk == "relic" and pr["unknown"]:
        yield T("SYS_CODEX_RELIC_ASK_HINT")


async def codex_material(env, sink, uid, player):
    p = _p(player)
    _sync_bag(p, player, env)
    rows = [T("SYS_CODEX_ENTRY", name=CX.name_of("material", k),
              line=CX.line_of("material", k))
            for k in CX.book("material") if CX.has(p, "material", k)]
    async for line in _one_book(p, "material", rows):
        yield line


async def codex_flavor(env, sink, uid, player):
    p = _p(player)
    _sync_bag(p, player, env)
    rows = [T("SYS_CODEX_ENTRY", name=CX.name_of("flavor", k),
              line=CX.line_of("flavor", k))
            for k in CX.book("flavor") if CX.has(p, "flavor", k)]
    async for line in _one_book(p, "flavor", rows):
        yield line


async def codex_monster(env, sink, uid, player):
    p = _p(player)
    rows = [T("SYS_CODEX_ENTRY_KILL", name=CX.name_of("monster", k),
              kills=CX.kills_of(p, k), line=CX.line_of("monster", k))
            for k in CX.book("monster") if CX.has(p, "monster", k)]
    async for line in _one_book(p, "monster", rows):
        yield line


async def codex_relic(env, sink, uid, player):
    p = _p(player)
    _sync_bag(p, player, env)
    rows = []
    for k in CX.book("relic"):
        if not CX.has(p, "relic", k):
            continue
        if CX.known(p, k):
            rows.append(T("SYS_CODEX_RELIC_KNOWN", name=CX.name_of("relic", k),
                          known=CX.line_of("relic", k, "known")))
        else:
            rows.append(T("SYS_CODEX_RELIC_UNKNOWN", hint=CX.line_of("relic", k, "hint")))
    async for line in _one_book(p, "relic", rows):
        yield line


async def footprint(env, sink, uid, player):
    p = _p(player)
    before = dict((p.get("foot") or {}).get("nodes") or {})
    CX.mark_here(p)                        # ★ 站着的这个节点也算去过（起始位置不落空）
    f = CX.foot(p)
    if (p.get("foot") or {}).get("nodes") != before:
        if player is not None:
            player.update(p)
        _save(env)
    places = len(f["nodes"])
    if not places:
        yield T("SYS_FOOT_EMPTY")
        return
    pr = CX.progress(p)
    quests = (p.get("flags") or {}).get("quests_done") or []
    yield T("SYS_FOOT_HEAD", places=places, kills=f["kills"], days=f["days"])
    yield T("SYS_FOOT_MORE", reads=f["reads"], gathers=f["gathers"], quests=len(quests))
    yield T("SYS_FOOT_BOOKS",
            material=pr["material"]["n"], mt=pr["material"]["target"],
            flavor=pr["flavor"]["n"], ft=pr["flavor"]["target"],
            monster=pr["monster"]["n"], ot=pr["monster"]["target"],
            relic=pr["relic"]["n"], q=pr["relic"]["unknown"])
