# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 第五组：组队（B3-25 —— 第一层：队伍数据 + 三条指令 + 一个『同意』动作）

这一批把 `04_指令总表 §十` 那张社交表里**声明了、看得见、没有处理器**的两条真接上，
外加上再补一条被 `visible: false` 关着的：

    · `队伍` `组队`（party）        —— 建队 / 看队（单人敲 = 起个队，队长是你）
    · `邀请 <人>`（party_invite）   —— 拉起队的人；**声明原先 invisible**，本批开成可见（见 _notes.md）
    · `同意`（party_accept）     —— ★ **本批新加的声明**：文字游戏里弹不出窗，
      「同意」只能是**被邀的人自己打的那一下**；没有它，邀请就没法表达「答应」。
      （★ 别名只收「同意」一个：「接受」与 `quest_accept` 的触发词撞车 —— probe_cmds ① 拦住了。）
    · `离队`（party_leave）         —— 队员退 / 队长退 = 解散

真源：`00_总纲/03_主要玩法.md` §4.7（组队 1–4 人 · **同地图**玩家可一起进）·
`06_第一阶段垂直切片/17_组队与策略配合_v1.md`（§一 异步窗口制 · §四 轮流制 · §五 按人数缩放）·
`06_第一阶段垂直切片/04_指令总表.md` §十（`队伍` `组队` / `邀请 <人>` / `离队`）。
口径与判据全在 **`content/data/party.json` + `content/party.py`**（本文件只做「取数 → 回话」：

        ★ 本文件**不写一句中文文案**：所有玩家可见的字都走 texts 槽位（`T("SYS_PARTY_…")`），
          判据码（ASCII）由 `content/party.py` 给、这里只做「码 → 槽位 + 参数」的映射。

三条边界（写在这儿免得下一轮当成已完）
--------------------------------------
  · **战斗内那一层（轮流制 / 输入窗口 / 超时自动防御）不在本批**：那是 17_ §四 的三条照搬，
    要「一场战斗跨多条指令」的持久状态 —— 与 B3-23 留在 `_notes.md` 的是同一条账。
  · 「离线」判不了（宿主没给 presence 注入面）⇒ 本批**不编**「多久没落档 = 离线」那种数；
    「离线的人进不来」是**结构性**保证（他不敲『同意』就在队外）+ 邀请到点作废（有回话）。
  · 队伍**不改**战斗里那三处 `party=…` 的算法（那是 `content/cmds_battle.py` 的活：进战那一刻
    现算「在队 + 同节点 + 活人」）。
"""
from __future__ import annotations

from .cmds_ast import _p, _save, _map_of, _name_of_node, T
from .cmds_talk import _arg
from . import party as PT


def _where(loc, node) -> str:
    """「现在在哪一站」—— 站名（图名里已经带着的那截不重复念；名字全从 maps 域现取）。"""
    nm = (_map_of(loc) or {}).get("name") or loc or ""
    nd = _name_of_node(loc, node) if node else ""
    if nd and nd in nm:
        return nm
    return "%s·%s" % (nm, nd) if nd and nm else (nm or nd)


def _commit(env, player, p) -> None:
    """落档：`_p()` 出的是**副本** ⇒ 先把改过的那份写回引擎手上那份，再 `env.save()`。"""
    if player is not None:
        player.update(p)
    _save(env)


def _load_rows(group_id):
    """本群存档（名册现算的原料）—— `None` = 读不出来（fail-closed：出一行点名的行、什么都不动）。"""
    try:
        return PT.rows_of(group_id)
    except PT.PartyError:
        return None


def _cap_name(rows, p, uid, r) -> str:
    """回话里那个队长的显示名（自己那份档优先 —— 手上这份可能刚被改过）。"""
    ref = str(r.get("captain") or "")
    return str(r.get("name") or "") or PT.name_in(PT.index(rows), ref, p, uid) or ref


# ── 判据码 → 槽位（一把尺，别处不许再拼）──────────────────────────
_INV_SLOT = {
    PT.INV_ASK: "SYS_PARTY_INV_ASK",
    PT.INV_NOBODY: "SYS_PARTY_INV_NOBODY",
    PT.INV_SELF: "SYS_PARTY_INV_SELF",
    PT.INV_NOTCAP: "SYS_PARTY_INV_NOTCAP",
    PT.INV_NOCLS: "SYS_PARTY_INV_NOCLS",
    PT.INV_MEMBER: "SYS_PARTY_INV_MEMBER",
    PT.INV_OTHER: "SYS_PARTY_INV_OTHER",
    PT.INV_FULL: "SYS_PARTY_INV_FULL",
    PT.INV_FAR: "SYS_PARTY_INV_FAR",
    PT.INV_AGAIN: "SYS_PARTY_INV_AGAIN",
    PT.INV_OK: "SYS_PARTY_INV_OK",
}
_ACC_SLOT = {
    PT.ACC_IN: "SYS_PARTY_JOINED",
    PT.ACC_NONE: "SYS_PARTY_ACC_NONE",
    PT.ACC_EXPIRED: "SYS_PARTY_ACC_EXPIRED",
    PT.ACC_FULL: "SYS_PARTY_ACC_FULL",
    PT.ACC_FAR: "SYS_PARTY_ACC_FAR",
    PT.ACC_OK: "SYS_PARTY_ACC_OK",
}
_LV_SLOT = {
    PT.LV_NONE: "SYS_PARTY_LV_NONE",
    PT.LV_MEMBER: "SYS_PARTY_LV_MEMBER",
    PT.LV_CAPTAIN: "SYS_PARTY_LV_CAPTAIN",
}


def _slot_of(table, code, where):
    key = table.get(code)
    if not key:
        raise ValueError("组队：%s 回了一个没有槽位的判据码 %r（数据与实现分家了）" % (where, code))
    return key


def _inv_line(rows, p, uid, r) -> str:
    slot = _slot_of(_INV_SLOT, r.get("code"), "invite")
    if r["code"] in (PT.INV_FAR,):
        return T(slot, name=r.get("name", ""), where=_where(r.get("loc"), r.get("node")))
    if r["code"] == PT.INV_NOTCAP:
        return T(slot, cap=_cap_name(rows, p, uid, r))
    if r["code"] == PT.INV_OK:
        return T(slot, name=r.get("name", ""), ttl=r.get("ttl", 0))
    if r["code"] == PT.INV_FULL:
        return T(slot, max=r.get("max", PT.max_members()))
    if r["code"] == PT.INV_ASK or r["code"] == PT.INV_SELF:
        return T(slot)
    return T(slot, name=r.get("name", ""))


def _acc_line(rows, p, uid, r) -> str:
    slot = _slot_of(_ACC_SLOT, r.get("code"), "accept")
    code = r["code"]
    if code == PT.ACC_NONE:
        return T(slot)
    if code == PT.ACC_FAR:
        return T(slot, cap=_cap_name(rows, p, uid, r),
                 where=_where(r.get("loc"), r.get("node")))
    if code == PT.ACC_FULL:
        return T(slot, cap=_cap_name(rows, p, uid, r), max=r.get("max", PT.max_members()))
    if code == PT.ACC_OK:
        return T(slot, cap=_cap_name(rows, p, uid, r), n=r.get("n", 0))
    return T(slot, cap=_cap_name(rows, p, uid, r))


def _lv_line(rows, p, uid, r) -> str:
    if r.get("code") == PT.LV_CAPTAIN and not (r.get("names") or []):
        return T("SYS_PARTY_LV_SOLO")           # 队里就自己一个：那句带名单的话读起来是空的
    slot = _slot_of(_LV_SLOT, r.get("code"), "leave")
    if r["code"] == PT.LV_CAPTAIN:
        return T(slot, list="、".join(r.get("names") or []))
    if r["code"] == PT.LV_MEMBER:
        return T(slot, cap=_cap_name(rows, p, uid, r))
    return T(slot)


def _panel(rows, p, uid) -> list:
    """「队伍」那一屏：抬头 + 逐人一行 + （有邀请就提示） + 尾注。"""
    out = []
    v = PT.view(rows, p, uid)
    out.append(T("SYS_PARTY_HEAD", n=v["n"], max=v["max"],
                 cap=PT.name_in(PT.index(rows), v["captain"], p, uid)
                 or T("SYS_NAME_UNKNOWN")))
    for m in v["members"]:
        out.append(T("SYS_PARTY_ROW", name=m["name"] or T("SYS_NAME_UNKNOWN"),
                     level=m["level"],
                     hp="—" if m["hp"] is None else int(m["hp"]),
                     hpmax="—" if m["hp_max"] is None else int(m["hp_max"]),
                     where=_where(m["loc"], m["node"])))
    pend = PT.pending(rows, uid, PT.now_ticks(), p=p)
    if pend:
        out.append(T("SYS_PARTY_PEND", cap=PT.name_in(PT.index(rows), pend[0]["captain"]) or
                     pend[0]["captain"], left=int(pend[0]["left"])))
    out.append(T("SYS_PARTY_TAIL"))
    return out


# ══════════════════════════════════════════════════════════════
# 一、队伍 / 组队（建队 · 看队）
# ══════════════════════════════════════════════════════════════
async def party(env, sink, group_id, uid, player):
    """`队伍`（别名 组队）—— 单人敲 = 起个队（发起人即队长）；在队里敲 = 看这一队。

    ★ 队长走了 / 队名对不上（`stale`）⇒ 我这一格**自愈**清掉并说明（只动自己的档）。
    ★ 本波：**身上有一封活着的邀请**（别人正在邀我）时**不起队** —— 自愈之后只回
      「你没在队里」+ 那一封邀请，**不把只想看一眼的人立成队长**。
      为什么：原先那一刻会顺手 `create`（「你起了个队（队长：你）」）⇒ 那位被邀的人
      一回「队伍」就成了新队长，邀他的人再邀他就撞「他在别人的队里」（试玩实测被卡了一轮）。
      判据：`party.pending(...)` 非空 = 此刻真有指向我的邀请（过期的现算不算）。
      ★ 「建队」与「看队」共用一个入口（声明里 `^队伍$` / `^组队$` 同一格），所以这一档
      对两个词一起生效；要建队就先应下 / 等邀请过期（见 `_notes.md §真源行`）。
    """
    p = _p(player)
    rows = _load_rows(group_id)
    if rows is None:
        yield T("SYS_PARTY_OFF")
        return
    mem = PT.membership(rows, p, uid)
    if mem["stale"]:
        PT.clear(p)
        _commit(env, player, p)
        yield T("SYS_PARTY_STALE", cap=PT.name_in(PT.index(rows), mem["captain"])
                or mem["captain"])
        mem = PT.membership(rows, p, uid)
    if mem["role"] is None:
        pend = PT.pending(rows, uid, PT.now_ticks(), p=p)
        if pend:
            yield T("SYS_PARTY_LV_NONE")           # 只看一眼：报「没在队里」（不建队 —— 见抬头）
            yield T("SYS_PARTY_PEND",
                    cap=PT.name_in(PT.index(rows), pend[0]["captain"]) or pend[0]["captain"],
                    left=int(pend[0]["left"]))
            return
        PT.create(p, uid, PT.now_ticks())
        _commit(env, player, p)
        yield T("SYS_PARTY_MAKE", max=PT.max_members())
    for line in _panel(rows, p, uid):
        yield line


# ══════════════════════════════════════════════════════════════
# 二、邀请 <人>（邀本群的人 —— 他得自己打『同意』）
# ══════════════════════════════════════════════════════════════
async def party_invite(env, sink, group_id, uid, player):
    """`邀请 <名字>` —— 记在队长那一格上（有效期 `invite_ttl_ticks` 刻）。

    ★ 单人敲 = 顺带起个队（发起人即队长）；只有队长能拉人（`04_指令总表 §十` 那条是队伍动作）。
    ★ 同不同一处在这一步只是**预判**（按他档上那份「现在在哪」）；权威的那一判在 `同意` 里。
    """
    p = _p(player)
    want = _arg(env)
    rows = _load_rows(group_id)
    if rows is None:
        yield T("SYS_PARTY_OFF")
        return
    r = PT.invite(p, uid, want, rows, PT.now_ticks())
    if r.get("code") == PT.INV_OK:
        _commit(env, player, p)
    yield _inv_line(rows, p, uid, r)


# ══════════════════════════════════════════════════════════════
# 三、同意（★ 本批新加的声明：入队的那一下得本人敲）
# ══════════════════════════════════════════════════════════════
async def party_accept(env, sink, group_id, uid, player):
    """`同意` —— 应下最近那一封邀请，入队。

    ★ 入队那一刻**再判一遍**：队长还在不在 · 队满没满 · 还在不在同一处（同图）——
      过期 / 队长散了 / 不在一处 / 满员都各有明确回话，且**不动档**（fail-closed）。
    """
    p = _p(player)
    rows = _load_rows(group_id)
    if rows is None:
        yield T("SYS_PARTY_OFF")
        return
    r = PT.accept(p, uid, rows, PT.now_ticks())
    if r.get("code") == PT.ACC_OK:
        _commit(env, player, p)
    yield _acc_line(rows, p, uid, r)


# ══════════════════════════════════════════════════════════════
# 四、离队（队员退 / 队长退 = 解散）
# ══════════════════════════════════════════════════════════════
async def party_leave(env, sink, group_id, uid, player):
    """`离队` —— 队员退：清自己那一格；队长退 = **解散**（队员的格由他们自己现算时清掉）。"""
    p = _p(player)
    rows = _load_rows(group_id)
    if rows is None:
        yield T("SYS_PARTY_OFF")
        return
    r = PT.leave(p, uid, rows)
    if r.get("code") != PT.LV_NONE:
        _commit(env, player, p)
    yield _lv_line(rows, p, uid, r)
