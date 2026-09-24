# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 第五组：野外采集（B2-4）

采集 / 挖掘 / 垂钓 / 搜查 / 歇脚 / 拾取 —— 六个动词，同一套「找到点什么」的形状。
★ 时辰与天气：第一版只做「有没有 time 限制」的提示（真判断等 B2-5 calendar 落）。
"""
from __future__ import annotations

import random

from .cmds_ast import _data, _p, _save, _map_of, _name_of_node, T
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
    if _used(p, gid) >= int(pt.get("times_per_day", 3)):
        yield "%s今天已经被翻过了。明天再来。" % pt["name"]
        return
    rnd = random.Random("%s:%s:%s" % (uid, gid, p.get("day", 0)))
    # 采集点自己就是一张池（形状与 dp_* 一致）
    got = []
    entries = pt.get("pool") or []
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
    first = LT.add_to_bag(p, got) if got else []
    p["hp"] = p.get("hp", 1)
    if player is not None:
        player.update(p)
    _save(env)
    yield "【%s】%s" % (pt["name"], pt.get("desc") or "")
    if pt.get("time"):
        yield "（这东西只在「%s」出。）" % pt["time"]
    it = LT.items()
    for d in got:
        rec = it.get(d["id"]) or LT.pools().get(d["id"]) or {}
        yield "得到：%s %s ×%s" % (rec.get("icon", "·"), rec.get("name", d["id"]), d.get("n", 1))
        if rec.get("hint"):
            yield "  （%s）" % rec["hint"]
    if first:
        yield "★ %d 件第一次见到的东西记进了旧物谱。" % len(first)


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


async def codex_materials(env, sink, uid, player):
    p = _p(player)
    bag = p.get("bag") or {}
    mats = [(k, v) for k, v in bag.items()
            if (LT.items().get(k, {}).get("kind") in ("材料", "垃圾"))]
    if not mats:
        yield "【材料谱】空的。"
        return
    yield "【材料谱】%d 种" % len(mats)
    for k, n in mats[:15]:
        rec = LT.items().get(k, {})
        yield "· %s %s ×%s" % (rec.get("icon", "·"), rec.get("name", k), n)
