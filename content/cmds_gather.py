# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 第五组：野外采集（B2-4）

采集 / 挖掘 / 垂钓 / 搜查 / 歇脚 / 拾取 —— 六个动词，同一套「找到点什么」的形状。
★ 时辰与天气：第一版只做「有没有 time 限制」的提示（真判断等 B2-5 calendar 落）。
"""
from __future__ import annotations

import random

from .cmds_ast import _data, _p, _save, _map_of, _name_of_node, T
from .cmds_codex import new_lines
from . import calendar as CAL
from . import codex as CX
from . import loot as LT


def _points_here(p, kind=None):
    out = []
    for gid, v in _data("gathering").items():
        if v.get("map") == p["loc"] and v.get("subarea") == p["node"]:
            if kind is None or v.get("kind") == kind:
                out.append((gid, v))
    return out


def _used(p, gid):
    return int(((p.get("flags") or {}).get("gather_used") or {}).get(gid, 0) or 0)


def _bump_used(p, gid):
    f = dict(p.get("flags") or {})
    u = dict(f.get("gather_used") or {})
    u[gid] = int(u.get(gid, 0)) + 1
    f["gather_used"] = u
    p["flags"] = f


async def _do_gather(env, sink, uid, player, kind: str, verb: str):
    p = _p(player)
    pts = _points_here(p, kind)
    if not pts:
        yield "这儿没什么可%s的。" % verb
        return
    gid, pt = pts[0]
    st = CAL.tick(p)                       # ★ 时辰/天气现算；跨（游戏）日把采集次数归零
    if not CAL.allows(pt.get("time"), st):          # 整点门槛：夜明砂那类
        if player is not None:
            player.update(p)
        _save(env)
        yield T("SYS_TIME_GATED", what=pt["name"], when=pt["time"])
        return
    if _used(p, gid) >= int(pt.get("times_per_day", 3)):
        yield "%s今天已经被翻过了。明天再来。" % pt["name"]
        return
    rnd = random.Random("%s:%s:%s" % (uid, gid, p.get("day", 0)))
    # 采集点自己就是一张池（形状与 dp_* 一致）
    got = []
    pool = pt.get("pool") or []
    # ★ 条目级门槛 `when`（「稀有鱼只在夜里」这种按条算的）
    entries = [e for e in pool if CAL.allows(e.get("when"), st)]
    if not entries:
        if player is not None:
            player.update(p)
        _save(env)
        yield T("SYS_TIME_GATED", what=pt["name"],
                when=" · ".join(sorted({str(e.get("when")) for e in pool if e.get("when")})))
        return
    tot = sum(int(e.get("w", 1)) for e in entries)
    r = rnd.uniform(0, tot or 1)
    acc = 0.0
    for e in entries:
        acc += int(e.get("w", 1))
        if r <= acc:
            oid = e["out"]
            n = 1
            rng = e.get("n")
            if isinstance(rng, list) and len(rng) == 2:
                n = rnd.randint(int(rng[0]), int(rng[1]))
            if oid.startswith("unid_"):
                got.append({"id": oid, "n": n, "kind": "未鉴定"})
            else:
                it = LT.items()
                got.append({"id": oid, "n": n,
                            "kind": e.get("kind") or it.get(oid, {}).get("kind") or "材料"})
            break
    _bump_used(p, gid)
    if got:
        LT.add_to_bag(p, got)
    new = CX.note_items(p, [d["id"] for d in got]) if got else []
    CX.note_gather(p)
    p["hp"] = p.get("hp", 1)
    if player is not None:
        player.update(p)
    _save(env)
    yield "【%s】%s" % (pt["name"], pt.get("desc") or "")
    if pt.get("time"):
        yield T("SYS_TIME_ONLY", when=pt["time"])
    it = LT.items()
    for d in got:
        rec = it.get(d["id"]) or LT.pools().get(d["id"]) or {}
        yield "得到：%s %s ×%s" % (rec.get("icon", "·"), rec.get("name", d["id"]), d.get("n", 1))
        if rec.get("hint"):
            yield "  （%s）" % rec["hint"]
    for line in new_lines(new):
        yield line


async def gather(env, sink, uid, player):
    async for line in _do_gather(env, sink, uid, player, "采药", "采"):
        yield line


async def dig(env, sink, uid, player):
    async for line in _do_gather(env, sink, uid, player, "挖掘", "挖"):
        yield line


async def fish(env, sink, uid, player):
    async for line in _do_gather(env, sink, uid, player, "垂钓", "钓"):
        yield line


async def search(env, sink, uid, player):
    async for line in _do_gather(env, sink, uid, player, "搜查", "搜"):
        yield line


async def rest(env, sink, uid, player):
    p = _p(player)
    mx = int(p.get("hp_max") or 100)
    hp = int(p.get("hp") or mx)
    if hp >= mx:
        yield "你不累。"
        return
    heal = max(1, int(mx * 0.2))
    p["hp"] = min(mx, hp + heal)
    if player is not None:
        player.update(p)
    _save(env)
    yield "你坐下来歇了一会儿。风从北边来。"
    yield "生命 +%d（%d/%d）" % (heal, p["hp"], mx)


async def pick_up(env, sink, uid, player):
    yield "地上没什么可捡的 —— 打怪掉的东西会自己进背包。"
