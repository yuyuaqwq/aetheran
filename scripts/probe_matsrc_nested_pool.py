# -*- coding: utf-8 -*-
"""Audit L2756-2 probe: matsrc.kill_foes must see the pool-inside-pool layer."""
from __future__ import annotations
import glob, os, sys
REPO = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, str(REPO)); sys.path.insert(0, os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine"))
from saintess_engine.package import load_stack

ok = True
def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s" % ("OK " if cond else "FAIL", label) + (("  -- %s" % (extra,)) if extra else ""))

DB = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "b2_probe_2756.db")
for _f in glob.glob(DB + "*"):
    try: os.remove(_f)
    except OSError: pass
st = load_stack(REPO, inject={"db_path": DB, "clock": lambda: 1790308800})
st.install()
from content import matsrc as MS

DP = st.domain("drop_pools") or {}
MON = st.domain("monsters") or {}

print("[1] nested pool: unid_rare holds i_token_stone_shard; parent dp_elite_gear holds unid_rare")
NESTED = "i_token_stone_shard"
holders = [pid for pid, v in sorted(DP.items()) if isinstance(v, dict) and not str(pid).startswith("_")
           and any(str(e.get("out")) == "unid_rare" for e in MS._pool_entries(v))]
chk("domain really has a parent pool holding unid_rare", bool(holders), holders)
real = sorted(mid for mid, m in MON.items() if not str(mid).startswith("_") and isinstance(m, dict)
              and set(holders).intersection(set(m.get("drops") or [])))
chk("parent pool really hangs on monsters", bool(real), real[:6])
foes, pools = MS.kill_foes(NESTED, DP, MON)
chk("kill_foes no longer returns 0 (old code empty here)", bool(foes), (len(foes), pools))
chk("found foes superset of real channels", set(real).issubset({f["id"] for f in foes}),
    sorted({f["id"] for f in foes}.intersection(set(real))))
chk("parent pools present in result", set(holders).issubset(set(pools)), pools)

print("")
print("[2] pool list must not repeat a pool")
dup = [pid for pid in set(pools) if pools.count(pid) > 1]
chk("no duplicate pool id", not dup, dup)

print("")
print("[3] dynamic item star_xxx_random is not treated as a pool")
star = [e.get("out") for v in DP.values() if isinstance(v, dict) for e in MS._pool_entries(v)
        if str(e.get("out")).startswith("*")]
chk("domain really has dynamic items", bool(star), star[:3])
if star:
    f2, p2 = MS.kill_foes(str(star[0]), DP, MON)
    chk("querying a dynamic id does not crash", isinstance(f2, list) and isinstance(p2, list), (f2[:2], p2[:2]))
    chk("dynamic id never becomes a pool key", not any(x.startswith("*") for x in p2), p2[:4])
    chk("dynamic id is not itself a domain pool", str(star[0]) not in DP, list(DP)[:3])

print("")
print("[4] regression: directly-held pool still found (not only the nested layer)")
direct = [(pid, v) for pid, v in sorted(DP.items()) if isinstance(v, dict) and not str(pid).startswith("_")
          and any(str(e.get("out")) == "i_material_old_iron" for e in MS._pool_entries(v))]
dfoes, dpools = MS.kill_foes("i_material_old_iron", DP, MON)
chk("direct hit still returns something", bool(dfoes), (len(dfoes), dpools[:5]))
chk("no directly-held pool lost", set(pid for pid, _ in direct).issubset(set(dpools)),
    sorted(set(pid for pid, _ in direct) - set(dpools)))

print("")
print("result: %s" % ("all green" if ok else "has red"))
sys.exit(0 if ok else 1)
