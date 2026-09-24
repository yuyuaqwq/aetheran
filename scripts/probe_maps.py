# -*- coding: utf-8 -*-
"""探针：maps 域读得到 · 字段齐全 · 拓扑对 · ★ ext_world.space 能真消费。

用法（在 aetheran-package 仓根跑）：
    GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_maps.py
"""
from __future__ import annotations

import os
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
st = load_stack(str(REPO))
st.install()

mp = st.domain("maps")
chk("maps 域读得到", mp is not None, "%d 张图" % (len(mp) if mp else 0))
if not mp:
    sys.exit(1)

# ① 字段齐全
bad = [k for k, v in mp.items()
       if not all(f in v for f in ("name", "roles", "nodes", "topology"))]
chk("每张图四字段齐全（name/roles/nodes/topology）", not bad, "缺：%s" % bad if bad else "")

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
