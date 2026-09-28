# -*- coding: utf-8 -*-
"""Audit L2756-1 probe: gather_spots must not advertise time-gated points."""
from __future__ import annotations
import glob, inspect, os, sys
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, str(REPO))
sys.path.insert(0, os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine"))
from saintess_engine.package import load_stack

ok = True
def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s" % ("OK " if cond else "FAIL", label) + (("  -- %s" % (extra,)) if extra else ""))

DB = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "b2_probe_2756_1.db")
for _f in glob.glob(DB + "*"):
    try: os.remove(_f)
    except OSError: pass
st = load_stack(REPO, inject={"db_path": DB, "clock": lambda: 1790308800})
st.install()
from content import matsrc as MS
from content import calendar as CAL

G = st.domain("gathering") or {}
MP = st.domain("maps") or {}
# 旧签名下 gather_spots 不吃 gate ⇒ 垫一层：如实返回「这版根本不支持门槛」，
# 下面的 [2][3] 在那种树上会给出「与期望相反」的真值，而不是 TypeError 崩掉整支
# （崩掉会让 [6] 那条端到端判据永远跑不到 —— 而它才是撤修正时该红的那条）。
_HAS_GATE = "gate" in inspect.signature(MS.gather_spots).parameters

def _spots(iid, mp, gate):
    if _HAS_GATE:
        return MS.gather_spots(iid, G, mp, gate=gate)
    return MS.gather_spots(iid, G, mp)


gated = dict((k, v.get("time")) for k, v in G.items()
             if isinstance(v, dict) and v.get("time"))

print("[1] the domain really has time-gated points (else this probe proves nothing)")
chk("gathering domain has at least 1 time-gated point", bool(gated), gated)

print("[2] real cost: items whose only source is a gated point")
_items = {}
for k, v in G.items():
    if not isinstance(v, dict):
        continue
    for e in (v.get("pool") or []):
        _items.setdefault(str(e.get("out")), set()).add(k)
_closed = 0
for iid, sids in sorted(_items.items()):
    if not any(G.get(s, {}).get("time") for s in sids):
        continue
    if not _spots(iid, MP, lambda pt: not pt.get("time")):
        _closed += 1
chk("gather_spots accepts a gate parameter at all", _HAS_GATE)
chk("at least 1 item loses every source when the gate is closed", _closed > 0,
    "items_losing_all=%d" % _closed)

print("[3] a closed gate must drop exactly the gated spots, and nothing else")
_ok = True
_dropped = 0
for iid, sids in sorted(_items.items()):
    open_all = [s["id"] for s in MS.gather_spots(iid, G, MP)]
    closed = [s["id"] for s in _spots(iid, MP, lambda pt: not pt.get("time"))]
    gated_here = set(s for s in sids if G.get(s, {}).get("time"))
    if set(closed).intersection(gated_here):
        _ok = False
    if not set(closed) <= set(open_all):
        _ok = False
    if len(closed) != len(open_all):
        _dropped += 1
chk("closed gate removes gated ids only, never invents or reorders", _ok)
chk("the gate actually changed something (it is not a no-op)", _dropped > 0,
    "items_affected=%d" % _dropped)

print("[4] ordering: gate runs BEFORE truncation (a full front row must not blank the line)")
_synth = {"_m": {"nodes": [{"id": "n1"}, {"id": "n2"}, {"id": "n3"}, {"id": "n4"}]}}
_rows = {}
for _i in (1, 2, 3, 4):
    _rows["g%d" % _i] = {"verb": "herb", "name": "spot%d" % _i, "map": "m",
                         "subarea": "n%d" % _i, "pool": [{"out": "i_test"}]}
_blocked = set(["n1", "n2", "n3"])
_res = _spots_synth = (MS.gather_spots("i_test", _rows, _synth,
                        gate=lambda pt: pt["subarea"] not in _blocked)
                       if _HAS_GATE else MS.gather_spots("i_test", _rows, _synth))
chk("first 3 spots are closed, the 4th is open; gate-before-truncate still finds it",
    [s["id"] for s in _res] == ["g4"], [s["id"] for s in _res])
_trunc = MS.gather_spots("i_test", _rows, _synth)[:3]
chk("post-truncation equivalent (what a truncate-then-filter port would return)",
    [s["id"] for s in _trunc] == ["g1", "g2", "g3"],
    [s["id"] for s in _trunc])
_res_all = MS.gather_spots("i_test", _rows, _synth)
chk("without a gate all 4 come back (default path unchanged)", len(_res_all) == 4,
    [s["id"] for s in _res_all])
chk("without a gate the front row is intact",
    [s["id"] for s in _res_all][:3] == ["g1", "g2", "g3"],
    [s["id"] for s in _res_all][:3])

print("[5] the production call site actually injects a gate")
_src = open(os.path.join(REPO, "content", "cmds_recipe.py"), encoding="utf-8").read()
chk("cmds_recipe passes gate=CAL.allows", "gate=lambda pt: CAL.allows" in _src)

print("[6] END TO END: the smithy line itself must not name a gated point")
# Behavioural check on the real render path -- works on the old signature too, so
# reverting the fix gives a clean FAIL here rather than a TypeError above.
import content.calendar as CAL2
from content import cmds_recipe as CR
_line = CR._src_of("i_material_fungus")          # only source = the rain-gated spot
_gate_name = (G.get("gt_be_herb_1") or {}).get("name") or ""
_open_now = CAL2.allows((G.get("gt_be_herb_1") or {}).get("time"), CAL2.state())
print("      rendered: %r" % (_line,))
chk("the probe item really is unavailable right now (gate closed)", not _open_now)
if not _open_now:
    chk("the smithy line does not advertise the gated point",
        _gate_name not in _line, "gated_name=%r" % _gate_name)

print("")
print("result:", "all green" if ok else "HAS FAILURES")
sys.exit(0 if ok else 1)
