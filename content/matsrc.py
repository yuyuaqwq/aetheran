# -*- coding: utf-8 -*-
"""材料出处（Q-22）：一样料从哪儿来 —— 采集点 + 掉它的怪。

为什么有它
----------
P3 试玩报告 体验-4（铁屑）：强化要的「铁屑」只在『挖掘』里出，而铁匠铺那一屏只写料名 ——
玩家拿着「强化到 +1 要：铁屑 ×1 · 硬骨 ×1 + 40 铜板。」不知道铁屑从哪来，
只能靠连挖三处试出来。真源 `06_第一阶段垂直切片/05_玩法数值口径_v1.md §三`
写的就是「强化材料 采矿产「铁屑」· 怪掉「硬骨」」—— 出处本来就有，只是没人算给玩家看。

口径（一个字都不新编）
----------------------
  · 采集那一半：`gathering` 域里**池里有这件**的点（`map` / `subarea` / `name` / `times_per_day`）
  · 掉落那一半：`drop_pools` 域里**池里有这件**的池 → `monsters` 域里挂着这个池的怪（按等级升序）
  · 摆的顺序 = `maps` 域的图序 / 节点序（玩家走的那条路的顺序）· 怪最多点 `MAX_KILL` 只
  · 中文动作词（采/挖/钓/搜）由调用方走 `SYS_GATHER_VERB_*` 槽位给 —— 本文件一个字中文都不写
  · 认不出的件（两边都空）⇒ 两个函数都回空 —— 调用方走 fail-closed 那一句，不编出处

用法（唯一调用端 = `content/cmds_recipe.py` 的`铁匠铺`与`强化`）：
    from . import matsrc as MS
    MS.gather_spots(iid, gathering, maps) -> [{"id","verb","name","map","node","times"}, …]
    MS.kill_foes(iid, drop_pools, monsters) -> ([{"id","name","lv"}, …], [池 id, …])

★ 本文件是**纯标准库**（不 import 引擎、不 import 包内别的模块）—— 探针也能直接调它现算。
"""
from __future__ import annotations

#: 掉落那一半最多点几只有代表性的怪（再多折进「这类怪」那半句）—— 见 `SYS_SRC_KILL` 的措辞
MAX_KILL = 3


def _pool_entries(rec: dict):
    """一个池的条目 —— `dp_*` 走 `entries`，未鉴定那几条走 `pool`（域里两套写法，只在这里归一）。"""
    return list(rec.get("entries") or []) + list(rec.get("pool") or [])


def _road_order(maps, loc: str, node: str) -> tuple:
    """（图序, 节点序）—— 按 `maps` 域里写的先后摆（= 玩家走的那条路的顺序）。

    认不出的图 / 节点排到最后（`len()`，不猜）—— 排序只影响**摆的顺序**，不影响有没有。
    """
    order = [k for k in (maps or {}) if not str(k).startswith("_")]
    mi = order.index(loc) if loc in order else len(order)
    nodes = [n.get("id") for n in ((maps or {}).get(loc) or {}).get("nodes") or []]
    ni = nodes.index(node) if node in nodes else len(nodes)
    return (mi, ni)


def gather_spots(iid: str, gathering: dict, maps: dict | None = None) -> list:
    """这件料出在哪些**采集点**上（池里有它）—— 按 `maps` 的图序 / 节点序摆（同点再按 id，稳定）。"""
    want = str(iid)
    out = []
    for gid, v in sorted((gathering or {}).items()):
        if str(gid).startswith("_") or not isinstance(v, dict):
            continue
        if not any(str(e.get("out")) == want for e in (v.get("pool") or [])):
            continue
        out.append({"id": str(gid), "verb": str(v.get("verb") or ""),
                    "name": str(v.get("name") or ""), "map": str(v.get("map") or ""),
                    "node": str(v.get("subarea") or ""),
                    "times": int(v.get("times_per_day") or 1)})
    out.sort(key=lambda s: (_road_order(maps, s["map"], s["node"]), s["id"]))
    return out


def kill_foes(iid: str, drop_pools: dict, monsters: dict) -> tuple:
    """这件料由哪些**怪**掉（池里有它 ⇒ 挂了这个池的怪）—— `([怪…], [池 id…])`。"""
    want = str(iid)
    pools = []
    for pid, v in sorted((drop_pools or {}).items()):
        if str(pid).startswith("_") or not isinstance(v, dict):
            continue
        if any(str(e.get("out")) == want for e in _pool_entries(v)):
            pools.append(str(pid))
    foes = []
    for mid, m in sorted((monsters or {}).items()):
        if str(mid).startswith("_") or not isinstance(m, dict):
            continue
        if set(pools) & set(m.get("drops") or []):
            foes.append({"id": str(mid), "name": str(m.get("name") or ""),
                         "lv": int(m.get("lv") or 0)})
    foes.sort(key=lambda x: (x["lv"], x["id"]))          # 等级低的先摆（新手先碰得上的在前）
    return foes, pools
