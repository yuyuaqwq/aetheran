# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 第六组：图鉴与记录（B2-7）

六条指令（04_指令总表 §八）：图鉴 · 材料谱 · 风味谱 · 怪物谱 · 旧物谱 · 记录。
口径与文案真源：`00_总纲/14_图鉴四谱口径_v1.md`（条目在 codex 域 · 框架话在 texts 域）。

★ 这一组原先**只看不改**（记录发生在采集/战斗/读书/走路那些地方 —— `content/codex.py`）；
  P-8 起多了一条会落档的：`端详 <旧物>` —— 不靠 NPC 也能看出旧物的**一层**（见 `relic_study`）。
"""
from __future__ import annotations

from .cmds_ast import _p, _save, T
from .cmds_talk import _arg
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
        if CX.studied(p, k):                       # ★ P-8：自己看出的那一层，跟在后面（★ 另起一行，不并进问号那行）
            ev = CX.evidence(k)
            if ev:
                rows.append(T("SYS_CODEX_RELIC_SEEN", line=ev))
    async for line in _one_book(p, "relic", rows):
        yield line


# ══════════════════════════════════════════════════════════════
# 自己看（P-8）—— 不靠 NPC 的那一条路
# ══════════════════════════════════════════════════════════════
def _studiable(p) -> list:
    """他手上**能自己看**的那几件（在旧物谱里 ∧ 在背包里 ∧ 实物域写着物证句）—— 谱里的顺序。"""
    bag = p.get("bag") or {}
    return [k for k in CX.book("relic")
            if CX.has(p, "relic", k) and k in bag and CX.evidence(k)]


def _study_hit(p, want: str):
    """按名字认他手上那一件（★ 认的是**手上**的名字 —— 玩家在背包里看见的就是它）；认不出回 None。"""
    for rid in _studiable(p):
        names = (CX.held_name(rid), CX.name_of("relic", rid))
        if want in names or (len(want) >= 2 and any(want in n for n in names)):
            return rid
    return None


async def relic_study(env, sink, uid, player):
    """`端详 <旧物>` —— 自己上手看久一点，看出一层（★ P-8：没有那个 NPC 也能往前挪一格）。

    口径（**两条路各给一半，不互相替代**）：
      · **自己看只给一层**：手上这一件**本身**看得出的硬事实 —— 物证句
        （`codex.evidence`：实物域那句 `lore`「断口往里卷。不是用坏的 —— 是被人掰断的。」，
        未鉴定那类兜底池表的 `hint`）。能坐实「是什么做的 / 坏在哪 / 谁动过手」，
        但**推不出它在哪儿被人动的手**。
      · **「来处」那一层仍然只能问人**：谁、在哪、为什么（codex 的 `known`）——
        自己看多少遍都不给；看完仍然提醒他「拿去问对人」（`SYS_CODEX_RELIC_ASK_HINT`）。
      · 看过就**落档**（`books.relic[<id>].studied`），**不可逆 · 幂等**：第二遍看回同一句，
        档上不再动（落的是「你看过了」，不是「你知道了」—— `known` 那一格一个字不动）。

    为什么有它：原先只有「拿去问人」这一条路 ⇒ 那个 NPC 不在（或玩家还没走到他那儿），
    这件旧物就永远是问号 —— 玩家会觉得卡住了。

    没点名 → 先把旧物谱摆出来（照「烹饪」那一手）；名字对不上 → 走 fail-closed 的现成槽位。
    """
    p = _p(player)
    _sync_bag(p, player, env)
    want = _arg(env)
    if not want:
        async for line in codex_relic(env, sink, uid, player):
            yield line
        return
    rid = _study_hit(p, want)
    if not rid:
        yield T("SYS_CODEX_RELIC_NOHOLD", input=want)      # 手上没有这一件（fail-closed，不编、不落档）
        return
    if CX.study(p, rid):                           # ★ 只头一回落档
        if player is not None:
            player.update(p)
        _save(env)
    yield T("SYS_READ_HEAD", name=CX.held_name(rid))
    yield T("SYS_CODEX_RELIC_SEEN", line=CX.evidence(rid))
    if not CX.known(p, rid):                       # 另一半还在人那儿
        yield T("SYS_CODEX_RELIC_ASK_HINT")


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
