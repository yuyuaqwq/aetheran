# -*- coding: utf-8 -*-
"""探针：gathering 域 —— 点合法 · ★ 位置在真图上 · ★ pool 指向真物品 · 密度分布。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_gather.py
"""
from __future__ import annotations

import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack          # noqa: E402

st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
st.install()

G = st.domain("gathering")
MAPS = st.domain("maps")
IT = st.domain("items")
DP = st.domain("drop_pools")

fails = []
ok = lambda m: print("  ✓ " + m)
bad = lambda m: (fails.append(m), print("  ✗ " + m))

print("探针：gathering 域（采集点）")
print("  ✓ gathering 域读得到  —— %d 个点" % len(G))

# ① 四类齐全
kinds = {}
for v in G.values():
    kinds[v["kind"]] = kinds.get(v["kind"], 0) + 1
want = {"采药", "挖掘", "垂钓", "搜查"}
(ok if want <= set(kinds) else bad)("四类齐全  —— %s" % kinds)

# ② ★ 跨域：位置在真图上、节点在图里
bad_loc = []
for gid, v in G.items():
    m = MAPS.get(v.get("map"))
    if not m:
        bad_loc.append((gid, v.get("map")))
        continue
    ids = [n.get("id") for n in (m.get("nodes") or [])]
    if v.get("subarea") not in ids:
        bad_loc.append((gid, v.get("subarea")))
(ok if not bad_loc else bad)("★ 位置都在真图真节点上（坏 %s）" % (bad_loc or "无"))

# ③ ★ pool 指向真物品/真未鉴定
bad_out = []
for gid, v in G.items():
    for e in (v.get("pool") or []):
        o = str(e.get("out") or "")
        if o.startswith("unid_"):
            if o not in DP:
                bad_out.append((gid, o))
        elif o not in IT:
            bad_out.append((gid, o))
(ok if not bad_out else bad)("★ pool 指向真物品/真未鉴定（坏 %s）" % (bad_out or "无"))

# ④ 每条都有出产（不能空手）
no_pool = [k for k, v in G.items() if not v.get("pool")]
(ok if not no_pool else bad)("每个点都有出产（空 %s）" % (no_pool or "无"))

# ⑤ ★ 密度刻意不均（真源：没有空，密就不显）
by_map = {}
for v in G.values():
    by_map[v["map"]] = by_map.get(v["map"], 0) + 1
lo, hi = min(by_map.values()), max(by_map.values())
(ok if hi >= lo * 2 else bad)("★ 密度刻意不均（%s；最密 %d vs 最疏 %d）" % (by_map, hi, lo))

# ⑥ 有次数上限（不能无限刷）
no_cap = [k for k, v in G.items() if not v.get("times_per_day")]
(ok if not no_cap else bad)("每个点都有每日上限（缺 %s）" % (no_cap or "无"))

# ⑦ 有带时辰限制的点（夜明砂/无鳞鱼那类）
timed = [k for k, v in G.items() if v.get("time")]
(ok if timed else bad)("有时辰/天气限制的点（%s）" % (timed or "无"))

print()
print("按地图：%s" % by_map)
print("结果：%s" % ("全绿 ✓" if not fails else "有红 ✗"))
sys.exit(1 if fails else 0)
