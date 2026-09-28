# -*- coding: utf-8 -*-
"""审计 L2009-1/2/3 反证探针（批次2）：miss_lines 的「今日已采满」/ 过滤顺序 / times 单一读口。"""
from __future__ import annotations
import copy, glob, io, os, sys
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO)); sys.path.insert(0, ENGINE)
from saintess_engine.package import load_stack                       # noqa: E402

ok = True
DB = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "b2_probe_explore.db")
for _f in glob.glob(DB + "*"):
    try: os.remove(_f)
    except OSError: pass

def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("OK " if cond else "FAIL", label, ("  -- %s" % extra) if extra else ""))

FIXED = 1790308800
st = load_stack(str(REPO), inject={"db_path": DB, "clock": lambda: FIXED})
st.install()
from content import explore as EX, cmds_gather as CG, calendar as CAL   # noqa: E402

G = st.domain("gathering") or {}
import collections
bynode = collections.defaultdict(list)
for gid, v in G.items():
    if str(gid).startswith("_") or not isinstance(v, dict): continue
    bynode[(v.get("map"), v.get("subarea"))].append((gid, v))
node = next(k for k, v in bynode.items() if v)
pts = sorted(bynode[node])
gid0, pt0 = pts[0]
print("测试站:", node, "点数:", len(pts), "样点:", gid0, pt0.get("name"))
S = CAL.state()

print("\n[1] 未采 -> 应印出拾取点")
p0 = {"loc": node[0], "node": node[1], "flags": {}}
r0 = EX.miss_lines(copy.deepcopy(p0), S)
chk("未采时印出拾取点", "能捡的" in "".join(str(x) for x in r0), r0)

print("\n[2] 核心：全站采满 -> 不得再承诺「能捡的」")
pf = {"loc": node[0], "node": node[1], "flags": {"gather_used": {g: 99 for g, _ in pts}}}
r1 = EX.miss_lines(pf, S)
chk("全站采满 => 落「没什么动静」", "没什么动静" in "".join(str(x) for x in r1), r1)

print("\n[3] 只采满一点 -> 该点不得再进承诺")
p1 = {"loc": node[0], "node": node[1], "flags": {"gather_used": {gid0: 99}}}
r2 = EX.miss_lines(p1, S)
blob = "".join(str(x) for x in r2)
chk("采满的点名字不再出现", pt0.get("name") not in blob or "没什么动静" in blob, blob[:200])

print("\n[4] times 槽位走唯一读口（缺键=3，不该印「一天 0 回」）")
chk("提示里没有「一天 0 回」", "一天 0 回" not in "".join(str(x) for x in r0), r0)

print("")
print("[5] >3 个点的站：先滤后截（旧法先 [:MAX_SPOT] 再过滤）")
GATED = "雨"   # 固定钟下天气 w_sunny => 雨门槛必不过
BIG = {}
for _i in range(5):
    _r = dict(pt0)
    _r.update({"id": "zz%d" % _i, "name": "测试点%d" % _i})
    _r.pop("time", None)
    if _i == 2:
        _r["time"] = GATED
    BIG["zz%d" % _i] = _r
print("")
print("[4] times 槽位走唯一读口：缺 times_per_day 的点 => 3（旧法 or 0 会印「一天 0 回」）")
orig = CG._points_here
_b4 = {"zz9": dict(pt0, id="zz9", name="缺键点")}
_b4["zz9"].pop("times_per_day", None)
try:
    CG._points_here = lambda pp, verb=None: sorted(_b4.items())
    r4b = EX.miss_lines({"loc": node[0], "node": node[1], "flags": {}}, S)
    blob4b = "".join(str(x) for x in r4b)
    chk("缺键点印「一天 3 回」而非 0", "3 回" in blob4b and "0 回" not in blob4b, blob4b[:200])
finally:
    CG._points_here = orig
try:
    CG._points_here = lambda pp, verb=None: sorted(BIG.items())
    r3 = EX.miss_lines({"loc": node[0], "node": node[1], "flags": {}}, S)
    blob3 = "".join(str(x) for x in r3)
    chk("5 点站里点2 受门槛 => 仍印出可采的（旧法会误报「没什么动静」）", "能捡的" in blob3, blob3[:220])
    chk("受门槛的点2 被滤掉（不在提示里）", "测试点2" not in blob3, blob3[:220])
    chk("MAX_SPOT 截断仍在（只取 3 个）", blob3.count("测试点") <= 3, blob3[:220])
    p2 = {"loc": node[0], "node": node[1], "flags": {"gather_used": {"zz0": 99}}}
    r4 = EX.miss_lines(p2, S)
    blob4 = "".join(str(x) for x in r4)
    chk("只采满点0 => 截断窗滑到点1/3/4（点2 受门槛）", "测试点1" in blob4 and "测试点0" not in blob4, blob4[:220])
finally:
    CG._points_here = orig
print("")
print("\n[6] _times_of 单一读口：缺键=3 / 显式 1 / 显式 0 抛（不静默吞）")
chk("缺键 => 3", CG._times_of({}) == 3)
chk("显式 1 => 1", CG._times_of({"times_per_day": 1}) == 1)
try:
    CG._times_of({"times_per_day": 0, "name": "x"}); chk("显式 0 => 抛", False, "没抛")
except ValueError:
    chk("显式 0 => 抛 ValueError", True)

print("\n[7] 采集侧同一读口（口径单源的反证：explore 与 _do_gather 同值）")
chk("_do_gather 用的 times 与 _times_of 同源", CG._times_of(pt0) == max(1, int(pt0.get("times_per_day", 3))),
    "%s vs %s" % (CG._times_of(pt0), max(1, int(pt0.get("times_per_day", 3)))))

print("\n结果: %s" % ("全绿" if ok else "有红"))
sys.exit(0 if ok else 1)
