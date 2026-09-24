# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 第二组（对话 / 战斗外的交互）"""
from __future__ import annotations

from .cmds_ast import _data, _p, _save, _map_of, _name_of_node, T, _texts, _npcs_here
from . import calendar as CAL


def _arg(env, default=""):
    """从玩家原文取参数：`搭话 哈根` → `哈根`。"""
    t = (getattr(env, "text", "") or "").strip()
    parts = t.split(None, 1)
    return parts[1].strip() if len(parts) > 1 else default


def _pick_line(lines, p, st=None):
    """按 need 条件择优：**按顺序挑第一条满足的**（照奥兰迪亚的精华）。

    ★ 时辰 / 天气是真判断（名 → 时辰或天气，唯一出口 = `calendar`）；判不过就是判不过。
    """
    flags = p.get("flags") or {}
    for ln in lines or []:
        need = ln.get("need")
        if not need:
            return ln.get("text")
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
            else:
                ok = True
        if ok:
            return ln.get("text")
    return None


async def talk(env, sink, uid, player):
    p = _p(player)
    st = CAL.state()                       # 现在几时、什么天气（一次，全用它）
    here = _npcs_here(p["loc"], p["node"], st)
    if not here:
        yield "这儿没有别人。"
        return
    want = _arg(env)
    if not want:
        yield "这儿有：" + " · ".join("『%s』" % v.get("name") for _, v in here)
        yield "想搭话就打『搭话 %s』。" % here[0][1].get("name")
        return
    hit = None
    for k, v in here:
        if want == v.get("name") or want in (v.get("name") or ""):
            hit = (k, v)
            break
    if not hit:
        yield "这儿没有叫「%s」的。" % want
        yield "这儿有：" + " · ".join("『%s』" % v.get("name") for _, v in here)
        return
    k, npc = hit
    dlg = _data("dialogues").get(npc.get("dialogue") or "")
    yield "%s %s" % (npc.get("icon", "💬"), npc.get("name"))
    if not dlg:
        yield npc.get("desc") or "（这个人还没写台词。）"
        return
    nodes = dlg.get("nodes") or {}
    # 节点择优：先看剧情节点（main / hidden），没有再看 meet / daily
    for nn in ("main", "hidden", "meet", "daily", "idle"):
        if nn in nodes:
            txt = _pick_line(nodes[nn].get("texts"), p, st)
            if txt:
                for line in str(txt).split("\n"):
                    yield line
                return
    yield "（他没说话。）"


async def ask_way(env, sink, uid, player):
    p = _p(player)
    here = _npcs_here(p["loc"], p["node"])
    if not here:
        yield "没人可问。"
        return
    nb = []
    m = _map_of(p["loc"]) or {}
    for n in m.get("nodes") or []:
        if n.get("id") != p["node"]:
            nb.append(n.get("name"))
    yield "「往哪走？」"
    yield "%s想了想：「%s。」" % (here[0][1].get("name"),
                                 " · ".join("『%s』" % x for x in nb[:3]) if nb else "就这一条路")
