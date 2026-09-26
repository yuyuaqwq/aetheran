# -*- coding: utf-8 -*-
"""探针：maps 域读得到 · 字段齐全 · 拓扑对 · ★ ext_world.space 能真消费。

用法（在 aetheran-package 仓根跑）：
    GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_maps.py
"""
from __future__ import annotations

import os
import time
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402

ok = True


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


print("探针：maps 域（地图）")
st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
st.install()

mp = st.domain("maps")
chk("maps 域读得到", mp is not None, "%d 张图" % (len(mp) if mp else 0))
if not mp:
    sys.exit(1)

# ① 字段齐全
bad = [k for k, v in mp.items()
       if not all(f in v for f in ("name", "roles", "nodes", "topology"))]
chk("每张图四字段齐全（name/roles/nodes/topology）", not bad, "缺：%s" % bad if bad else "")

# ⑨ ★ Q-22 补（2026-09-26 · 分支 `fxd`）：图名 = **区域名**，不许把节点名拼进去。
#   起因（试玩 P3 复测 · 全新玩家）：站在拾荒营地，`状态` 写「在 北带 · 骨田」、`观察` 的标题写
#   「【北带 · 骨田（野外）】」—— 而人根本不在骨田。那串是早先批次把「带名 · 入口节点」拼成一格
#   留下来的（真源 `06_/00_第一阶段内容总纲` 那张表里地带叫**北带**，骨田只是它的第一个节点）。
#   判据：每张图的 `name` 里**不许出现自己任一节点的名字**（复合名一定含节点名 ⇒ 一并挡掉）；
#   当前站在哪个节点由 `观察` 的节点列表（▸ 那一行）与 `时间` 单独给。
bad9 = []
for _k, _v in mp.items():
    _nm = str(_v.get("name") or "")
    _hit = [str(_n.get("name")) for _n in (_v.get("nodes") or [])
            if _n.get("name") and str(_n.get("name")) in _nm]
    if _hit:
        bad9.append("%s:「%s」里含节点名 %s" % (_k, _nm, " · ".join(_hit)))
chk("★ 图名是区域名（不含自己的节点名 · 不是「带名 · 节点」那种复合）", not bad9, " ｜ ".join(bad9))

# ② 拓扑对
chk("风车镇 = star（城镇）", mp.get("windmill_town", {}).get("topology") == "star")
belts = [k for k in mp if k.startswith("belt_")]
chk("三条带 = chain（野外）", belts and all(mp[k]["topology"] == "chain" for k in belts),
    " · ".join(belts))

# ③ 节点 id 全局唯一
ids = [n["id"] for v in mp.values() for n in v["nodes"]]
chk("节点 id 全局唯一", len(ids) == len(set(ids)), "%d 个节点" % len(ids))

# ④ role 都在 roles 里声明过
bad4 = []
for k, v in mp.items():
    declared = set(v["roles"].values())
    for n in v["nodes"]:
        if n["role"] not in declared:
            bad4.append("%s/%s=%s" % (k, n["id"], n["role"]))
chk("每个节点的 role 都在 roles 里声明过", not bad4, " · ".join(bad4))

# ⑤ 风车镇 = 8 场所 + 3 镇口
town = mp.get("windmill_town", {})
shops = [n for n in town.get("nodes", []) if n["role"] == town.get("roles", {}).get("hub")]
gates = [n for n in town.get("nodes", []) if n["role"] == town.get("roles", {}).get("exit")]
chk("风车镇 8 处场所", len(shops) == 8, " · ".join(n["name"] for n in shops))
chk("风车镇 3 个出口（北/东/西）", len(gates) == 3, " · ".join(n["name"] for n in gates))

# ⑥ 每条带 3 节点
chk("三条带各 3 节点", all(len(mp[k]["nodes"]) == 3 for k in belts))

# ⑥-b ★ B3-6：副本那张图（旧哨塔）—— 12 间 · 三层（floors）· 进塔那一格（entrance）
tower = mp.get("old_watchtower", {})
tfl = [(str(f.get("name")), [str(x) for x in (f.get("rooms") or [])])
       for f in (tower.get("floors") or [])]
tflat = [r for _n, rs in tfl for r in rs]
tnodes = [n["id"] for n in (tower.get("nodes") or [])]
chk("★ 副本那张图：12 间 · chain · 三层 floors 覆盖 12 间不重不漏",
    len(tnodes) == 12 and tower.get("topology") == "chain"
    and tflat == tnodes and len(set(tflat)) == 12 and len(tfl) >= 2,
    " / ".join("%s %d" % (n, len(rs)) for n, rs in tfl))
tent = tower.get("entrance") or {}
chk("★ 副本那张图的 entrance 是真节点（从哪儿进塔 —— 跨图那一格）",
    tent.get("map") in mp
    and tent.get("node") in [n["id"] for n in (mp.get(tent.get("map")) or {}).get("nodes", [])],
    "%s:%s" % (tent.get("map"), tent.get("node")))
entry_role = (tower.get("roles") or {}).get("entry")
entry_node = next((n["id"] for n in (tower.get("nodes") or []) if n.get("role") == entry_role), None)
chk("★ roles.entry 落在第一层第一间（进门站的那一间）",
    bool(tfl) and entry_node == tfl[0][1][0], "%r" % entry_node)

# ⑦ ★ 引擎形状真能消费（ext_world.space）
try:
    from ext_world.space import Space
    consumed, detail = 0, []
    for k, v in mp.items():
        sp = Space(v["nodes"], topology=v["topology"], roles=v["roles"])
        adj = sp.adjacency()
        dep = {n["id"]: sp.depth(n["id"]) for n in v["nodes"]}
        au = sp.audit()
        gate, entry = sp.gate(), sp.entry()
        consumed += 1
        detail.append("%s(邻接 %d · 最深 %d · 门 %s)" % (
            v["name"], sum(len(x) for x in adj.values()), max(dep.values()), gate))
    chk("★ ext_world.space 能消费全部地图", consumed == len(mp), " | ".join(detail))
except Exception as e:
    chk("★ ext_world.space 能消费全部地图", False, "%s: %s" % (type(e).__name__, e))

print()
print("地图速览：")
for k, v in mp.items():
    print("  %-16s %-12s %-6s %d 节点" % (k, v["name"], v["topology"], len(v["nodes"])))
print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
