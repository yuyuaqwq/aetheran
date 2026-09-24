# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 第二组（对话 / 战斗外的交互）"""
from __future__ import annotations

from .cmds_ast import _data, _p, _save, _map_of, _name_of_node, T, _texts, _npcs_here
from .cmds_ast import egg_lines, title_lines
from . import calendar as CAL
from . import codex as CX
from . import heard as HD


def _arg(env, default=""):
    """从玩家原文取参数：`搭话 哈根` → `哈根`。"""
    t = (getattr(env, "text", "") or "").strip()
    parts = t.split(None, 1)
    return parts[1].strip() if len(parts) > 1 else default


def _pick_indexed(lines, p, st=None):
    """按 need 条件择优：**按顺序挑第一条满足的**（照奥兰迪亚的精华）。

    ★ 时辰 / 天气是真判断（名 → 时辰或天气，唯一出口 = `calendar`）；判不过就是判不过。
    ★ 返回 `(序号, 台词)`；一条都挑不出就 `(None, None)` —— 序号给「听过哪一句」记账用（B3-2）。
    """
    flags = p.get("flags") or {}
    for i, ln in enumerate(lines or []):
        need = ln.get("need")
        if not need:
            return i, ln.get("text")
        ok = True
        for k, v in need.items():
            if k == "flag":
                if not flags.get(v):
                    ok = False
            elif k == "holding":
                if not (p.get("bag") or {}).get(v):
                    ok = False
            elif k == "time" or k == "weather":
                if not CAL.allows(v, st):        # ★ B2-5：真判断（原来是「先当满足」）
                    ok = False
            elif k == "event":
                ok = bool(flags.get("event_" + str(v)))
            elif k == "last":
                ok = bool(flags.get("last_" + str(v)))
            elif k == "quest_done":
                ok = bool(flags.get(v))
            elif k == "codex":
                # `codex: "<谱>:<条目>"` —— 谱里有了才出这句（B2-7：图鉴与对话接上）
                bk, _, rid = str(v).partition(":")
                if not (bk and rid and CX.has(p, bk, rid)):
                    ok = False
            else:
                ok = True
        if ok:
            return i, ln.get("text")
    return None, None


def _pick_line(lines, p, st=None):
    """（老签名保持不变：只要那句话说啥 —— 探针与别处都在用它）"""
    return _pick_indexed(lines, p, st)[1]


async def talk(env, sink, uid, player):
    p = _p(player)
    st = CAL.state()                       # 现在几时、什么天气（一次，全用它）
    here = _npcs_here(p["loc"], p["node"], st)
    if not here:
        yield T("SYS_TALK_NOBODY")
        return
    want = _arg(env)
    if not want:
        yield T("SYS_TALK_HERE", list=" · ".join("『%s』" % v.get("name") for _, v in here))
        yield T("SYS_TALK_HOW", name=here[0][1].get("name"))
        return
    hit = None
    for k, v in here:
        if want == v.get("name") or want in (v.get("name") or ""):
            hit = (k, v)
            break
    if not hit:
        yield T("SYS_TALK_NOSUCH", name=want)
        yield T("SYS_TALK_HERE", list=" · ".join("『%s』" % v.get("name") for _, v in here))
        return
    k, npc = hit
    dlg = _data("dialogues").get(npc.get("dialogue") or "")
    yield "%s %s" % (npc.get("icon", "💬"), npc.get("name"))
    if not dlg:
        yield npc.get("desc") or T("SYS_TALK_NO_LINES")
        return
    nodes = dlg.get("nodes") or {}
    # 节点择优：先看剧情节点（main / hidden），没有再看 meet / daily
    spoke = False
    heard_new = False
    for nn in ("main", "hidden", "meet", "daily", "idle"):
        if nn in nodes:
            idx, txt = _pick_indexed(nodes[nn].get("texts"), p, st)
            if txt:
                for line in str(txt).split("\n"):
                    yield line
                spoke = True
                # ★ B3-2：听过哪一句记下来（称号「听完哈根的全部对话」靠它）
                heard_new = HD.note(p, npc.get("dialogue") or "", nn, idx)
                break
    if not spoke:
        yield T("SYS_TALK_SILENT")
    if heard_new and player is not None:
        player.update(p)
        _save(env)
    # ★ B2-7：他要是认得你谱里那些还留着问号的旧东西 —— 名字当场说出来
    if spoke:
        first = True
        for rid in CX.revealable(p, k):
            if CX.reveal(p, rid):
                if player is not None:
                    player.update(p)
                _save(env)
                if first:                       # 那句话一次对话只说一遍
                    yield T("SYS_CODEX_ASK", who=npc.get("name"))
                    first = False
                yield T("SYS_CODEX_REVEAL", name=CX.name_of("relic", rid))
                yield T("SYS_CODEX_RELIC_KNOWN", name=CX.name_of("relic", rid),
                        known=CX.line_of("relic", rid, "known"))
    for line in egg_lines(p, player, env):      # ★ B3-1：人 + 东西，可能就在这一下连起来
        yield line
    for line in title_lines(p, player, env):    # ★ B3-2：话说完，名字可能就挂上来了
        yield line


async def ask_way(env, sink, uid, player):
    p = _p(player)
    here = _npcs_here(p["loc"], p["node"])
    if not here:
        yield T("SYS_ASK_NOBODY")
        return
    nb = []
    m = _map_of(p["loc"]) or {}
    for n in m.get("nodes") or []:
        if n.get("id") != p["node"]:
            nb.append(n.get("name"))
    yield T("SYS_ASK_HEAD")
    yield T("SYS_ASK_ANSWER", who=here[0][1].get("name"),
            list=" · ".join("『%s』" % x for x in nb[:3]) if nb else T("SYS_ASK_ONLY_WAY"))
