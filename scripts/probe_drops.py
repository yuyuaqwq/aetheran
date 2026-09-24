# -*- coding: utf-8 -*-
"""探针：drop_pools 域 + 掉落逻辑 —— 池合法 · ★ 所有 out 指向真物品 · 权重可抽 · 可复现。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_drops.py
"""
from __future__ import annotations

import os
import random
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack          # noqa: E402

st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
st.install()

DP = st.domain("drop_pools")
IT = st.domain("items")
MON = st.domain("monsters")
LT = st.optional_submodule("loot")

fails = []
ok = lambda m: print("  ✓ " + m)
bad = lambda m: (fails.append(m), print("  ✗ " + m))

print("探针：drop_pools 域 + 掉落逻辑")

# ① 域读得到 + 分两类
pools = {k: v for k, v in DP.items() if k.startswith("dp_")}
unids = {k: v for k, v in DP.items() if k.startswith("unid_")}
(ok if pools and unids else bad)("掉落池 %d 个 · 未鉴定 %d 个" % (len(pools), len(unids)))

# ② 每条有 entries/pool + 权重字段
no_ent = [k for k, v in DP.items() if not (v.get("entries") or v.get("pool"))]
(ok if not no_ent else bad)("每条都有 entries/pool（缺 %s）" % (no_ent or "无"))

# ③ ★ 跨域：所有 out 指向真物品（动态 * 项除外）
bad_out = []
for k, v in DP.items():
    for e in (v.get("entries") or v.get("pool") or []):
        o = str(e.get("out") or "")
        if not o or o.startswith("*"):
            continue
        if o.startswith("dp_") or o.startswith("unid_"):
            if o not in DP:
                bad_out.append((k, o))
        elif o not in IT:
            bad_out.append((k, o))
(ok if not bad_out else bad)("★ 所有 out 指向真物品/真池（坏 %s）" % (bad_out or "无"))

# ④ ★ 怪的 drops 池都真实存在（跨域对账）
bad_ref = []
for mid, m in MON.items():
    for p in (m.get("drops") or []):
        if p not in DP:
            bad_ref.append((mid, p))
(ok if not bad_ref else bad)("★ 怪身上挂的池都存在（坏 %s）" % (bad_ref or "无"))

# ⑤ 未鉴定的四类出口都在（装备/材料/垃圾/信物/线索）
u = DP.get("unid_rare") or {}
kinds = {e.get("kind") for e in (u.get("pool") or [])}
want = {"装备", "材料", "垃圾", "信物", "线索"}
(ok if want <= kinds else bad)("★ 未鉴定四类出口齐（有 %s）" % sorted(kinds))

# ⑥ ★ 权重能抽出来（跑 2000 次，每类都出得来）
rnd = random.Random(42)
got = {}
for _ in range(2000):
    r = LT.open_unid("unid_rare", rnd=rnd)
    if r:
        got[r["kind"]] = got.get(r["kind"], 0) + 1
(ok if len(got) >= 4 else bad)("★ 2000 次开未鉴定，种类分布 = %s" % got)

# ⑦ ★ 可复现（同种子同结果）
a = LT.roll_pool("dp_trash_small", level=3, rnd=random.Random("s"))
b = LT.roll_pool("dp_trash_small", level=3, rnd=random.Random("s"))
(ok if a == b else bad)("★ 同种子掉落可复现（%s）" % a)

# ⑧ 动态挑选 *armor_random 能解析出真装备
r = LT.roll_pool("dp_elite_gear", level=5, rnd=random.Random(1))
ids = [x["id"] for x in r]
(ok if all(i in IT for i in ids) else bad)("动态项解析成真物品（%s）" % ids)

# ⑨ 重复掉落有用（材料能进背包、图鉴记第一次）
p = {"bag": {}, "codex": {}}
first = LT.add_to_bag(p, [{"id": "i_material_iron_chip", "n": 2}])
second = LT.add_to_bag(p, [{"id": "i_material_iron_chip", "n": 1}])
(ok if p["bag"]["i_material_iron_chip"] == 3 and first and not second
 else bad)("重复掉落累计进背包、图鉴只记第一次（%s）" % p["bag"])

print()
print("结果：%s" % ("全绿 ✓" if not fails else "有红 ✗"))
sys.exit(1 if fails else 0)
