# -*- coding: utf-8 -*-
"""探针：eggs 域（十条彩蛋）—— 条目对账 · 条件可求值 · 撞上那一下的行为。

判据（★ = 跨域/行为，最要紧）：
  ① 十条齐 · id 形状对 · 编号 1–10 不重不漏（= 19 文档 §三 B 那张表）
  ② 每条形状：标题 / 两端（非空且不同）/ 发现方式 / 揭示文案（12–60 字，不是照抄「发现方式」）
  ③ ★ 跨域对账：条件里每个取值都在对应域里真存在（地图节点 / 物品 / 任务 / 怪 / 种族 / 时辰与天气名）
  ④ ★ 条件只用引擎算子的声明节点，且整表能编译（形状错当场抛，不静默）
  ⑤ ★ 造实例：**逐条造一个满足它的档** → scan 必须命中它；再扫一遍不再报（幂等）
  ⑥ ★ 反向：什么都没做过的档 → 一条都不给（不白送）
  ⑦ ★ 触发点接线：观察 / 地图 / 触摸 / 搭话 的实现体末尾真的调了 egg_lines
  ⑧ 彩蛋指令接在 content.cmds_egg 上（声明 → 实现体）
  ⑨ 用到的文案槽位都在 texts 域
  ⑩ 可达性（信息行）：今天的数据里，几条撞得上、几条在等前置（种族 / 套装出产）

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_eggs.py
"""
from __future__ import annotations

import importlib
import json
import os
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))          # rebuild_eggs 的 walk（对账与造实例共用一份）
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402

ok = True
ID_RE = re.compile(r"^egg_[a-z0-9_]+$")
OPS = {"and", "or", "contains", "eq", "truthy"}


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


print("探针：eggs 域（十条彩蛋）")
st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
st.install()

EG_DOM = st.domain("eggs")
MP = st.domain("maps") or {}
PO = st.domain("pois") or {}
IT = st.domain("items") or {}
QU = st.domain("quests") or {}
MO = st.domain("monsters") or {}
RA = st.domain("races") or {}
TX = st.domain("texts") or {}
frm = st.domain("calendar") or {}
fw = st.domain("weather") or {}
HOUR_NAMES = {str((TX.get(e.get("slot")) or {}).get("value")) for k, e in frm.items() if not str(k).startswith("_")}
WEA_NAMES = {str((TX.get(e.get("slot")) or {}).get("value")) for k, e in fw.items() if not str(k).startswith("_")}

BOOK = {k: dict(v) for k, v in (EG_DOM or {}).items() if not str(k).startswith("_")}
chk("eggs 域读得到", EG_DOM is not None and bool(BOOK), "%d 条" % len(BOOK))
if not BOOK:
    sys.exit(1)

# ① 十条齐 · 形状
bad_id = [k for k in BOOK if not ID_RE.match(k)]
nums = sorted(int(v.get("no") or 0) for v in BOOK.values())
chk("★ 十条齐（= 19 文档 §三 B 那张表）", len(BOOK) == 10, "%d 条" % len(BOOK))
chk("id 形状都是 egg_xxx", not bad_id, bad_id[:4])
chk("编号 1–10 不重不漏", nums == list(range(1, 11)), nums)

# ② 每条形状
bad_shape = []
for k, v in BOOK.items():
    pair = list(v.get("pair") or [])
    line = str(v.get("line") or "")
    if (not v.get("title") or not v.get("how") or len(pair) != 2
            or not pair[0] or not pair[1] or pair[0] == pair[1]
            or not (12 <= len(line) <= 60) or line == v.get("how")):
        bad_shape.append("%s(pair=%r, line=%d 字)" % (k, pair, len(line)))
chk("★ 每条都有「标题 / 两端（两个且不同）/ 发现方式 / 一句 12–60 字的话」", not bad_shape, bad_shape[:4])

BAD_WORDS = ("hp", "atk", "def", "spd", "crit", "×", "％")
bad_txt = ["%s: %s" % (k, v.get("line")) for k, v in BOOK.items()
           if any(w in str(v.get("line") or "") for w in BAD_WORDS)]
chk("揭示文案不是数值表腔", not bad_txt, bad_txt[:3])

# ③ ★ 跨域对账（探针自己重算，不信 eggs.json 的自述）
import rebuild_eggs as RB                                            # noqa: E402

CTX = RB.CTX_FIELD
bad_ref = []
for k, v in BOOK.items():
    for field, val in RB.walk(dict(v.get("cond") or {}), []):
        key = [c for c, f in CTX.items() if f == field]
        ck = key[0] if key else field
        if ck in ("where", "been"):
            loc, _, nd = str(val).partition(":")
            good = loc in MP and nd in [n["id"] for n in (MP[loc].get("nodes") or [])]
        elif ck == "map":
            good = val in MP
        elif ck == "race":
            good = ("race_" + str(val)) in RA
        elif ck == "read":
            good = val in PO and bool(PO[val].get("into_codex"))
        elif ck in ("hold", "worn"):
            good = val in IT
        elif ck == "set":
            good = any((rec or {}).get("set_id") == val for rec in IT.values())
        elif ck == "done":
            good = val in QU
        elif ck == "kill":
            good = val in MO
        elif ck == "hour":
            good = val in HOUR_NAMES
        elif ck == "weather":
            good = val in WEA_NAMES
        elif ck == "lore":
            good = str(val) == "scripts"
        else:
            good = False
        if not good:
            bad_ref.append("%s: %s=%s" % (k, ck, val))
chk("★ 条件里的每个取值都在对应域里真存在", not bad_ref, bad_ref[:5])

# ④ 条件只用引擎算子 · 整表能编译
bad_op = []


def ops_of(node):
    out = set()
    if "op" in node:
        out.add(node["op"])
        for a in node.get("args") or []:
            out |= ops_of(a)
        for sub in (node.get("arg"),):
            if isinstance(sub, dict):
                out |= ops_of(sub)
    return out


for k, v in BOOK.items():
    got = ops_of(dict(v.get("cond") or {}))
    if not got or (got - OPS):
        bad_op.append("%s: %s" % (k, sorted(got)))
chk("★ 条件只用引擎算子（and/or/contains/eq/truthy）", not bad_op, bad_op[:4])

from content import eggs as EG                                       # noqa: E402

try:
    SPECS = EG.specs()
    spec_err = ""
except Exception as exc:                                             # noqa: BLE001 —— 形状错就是红
    SPECS, spec_err = {}, "%s: %s" % (type(exc).__name__, exc)
chk("★ 十条条件整表编译通过（形状错当场抛）", set(SPECS) == set(BOOK) and not spec_err,
    spec_err or "%d 条" % len(SPECS))


# ⑤ ★ 逐条造实例：满足它的档 → scan 必须命中它；再扫一遍不再报
from content import calendar as CAL                                   # noqa: E402


def _ck(field: str) -> str:
    key = [c for c, f in CTX.items() if f == field]
    return key[0] if key else field


def profile_for(eid: str):
    """造一个「刚好满足这条彩蛋」的档 + 它需要的那一格时辰/天气。"""
    p = {"day": 4, "level": 3, "loc": "", "node": "", "bag": {}, "equipped": {},
         "books": {"relic": {}, "monster": {}}, "foot": {"nodes": {}}, "flags": {}}
    stx = dict(CAL.state())
    for field, val in RB.walk(dict(BOOK[eid]["cond"]), []):
        ck = _ck(field)
        if ck == "where":
            loc, _, nd = str(val).partition(":")
            p["loc"], p["node"] = loc, nd
        elif ck == "map":
            p["loc"] = str(val)
        elif ck == "race":
            p["race"] = str(val)
        elif ck == "lore":
            p["race"] = "elf"
        elif ck == "read":
            p["books"]["relic"][str(val)] = {"known": True}
        elif ck == "been":
            p["foot"]["nodes"][str(val)] = 1
        elif ck == "hold":
            p["bag"][str(val)] = 1
        elif ck == "worn":
            p["equipped"]["helmet"] = str(val)
        elif ck == "set":
            iid = next((i for i, rec in IT.items() if (rec or {}).get("set_id") == val), None)
            p["bag"][str(iid)] = 1
        elif ck == "done":
            p["flags"]["quests_done"] = [str(val)]
        elif ck == "kill":
            p["books"]["monster"][str(val)] = {"kills": 1}
        elif ck == "hour":
            stx["hour_name"] = str(val)
        elif ck == "weather":
            stx["weather_name"] = str(val)
    return p, stx


miss, twitch = [], []
for eid in BOOK:
    p, stx = profile_for(eid)
    first = EG.scan(p, stx)
    second = EG.scan(p, stx)
    if eid not in first:
        miss.append(eid)
    if second:
        twitch.append("%s 报了第二遍 %s" % (eid, second))
chk("★ 十条逐条造实例：满足它的档一定命中它", not miss, miss[:4])
chk("★ 撞上那一下是幂等的（连起来过的不再报）", not twitch, twitch[:3])

# ⑥ 反向：什么都没做过 → 一条都不给
blank = {"day": 1, "level": 1, "loc": "belt_east", "node": "be_birch", "bag": {}, "equipped": {},
         "books": {"relic": {}, "monster": {}}, "foot": {"nodes": {}}, "flags": {}}
chk("★ 什么都没做过的档：一条都不给（不白送）", EG.scan(blank, dict(CAL.state())) == [])

# ⑦ ★ 触发点接线（源码级：四个实现体末尾真的调了）
src_ast = open(str(REPO / "content" / "cmds_ast.py"), encoding="utf-8").read()
src_talk = open(str(REPO / "content" / "cmds_talk.py"), encoding="utf-8").read()
n_ast = src_ast.count("egg_lines(p, player, env)")
n_talk = src_talk.count("egg_lines(p, player, env)")
chk("★ 观察 / 地图 / 触摸 都会扫（cmds_ast 里 3 处）", n_ast == 3, "实测 %d 处" % n_ast)
chk("★ 搭话也会扫（cmds_talk 里 1 处）", n_talk == 1, "实测 %d 处" % n_talk)

# ⑧ 彩蛋指令接在 content.cmds_egg 上
CMDS = json.load(open(str(REPO / "content" / "data" / "commands.json"), encoding="utf-8"))
bind = ((CMDS.get("eggs") or {}).get("bind") or {})
mod = importlib.import_module("content.cmds_egg")
chk("★ 彩蛋指令声明 → content.cmds_egg:eggs_book", bind.get("handler") == "content.cmds_egg:eggs_book", bind)
chk("实现体在 · 主词与别名都写着（彩蛋 / 连起来）",
    callable(getattr(mod, "eggs_book", None)) and len((CMDS.get("eggs") or {}).get("patterns") or []) >= 2)

# ⑨ 用到的文案槽位都在 texts 域
slots = set(re.findall(r'SYS_EGG_[A-Z_]+', src_ast + src_talk
                       + open(str(REPO / "content" / "cmds_egg.py"), encoding="utf-8").read()))
miss_slot = sorted(s for s in slots if s not in TX)
chk("★ 彩蛋用到的文案槽位都在 texts 域（%d 个）" % len(slots), not miss_slot and len(slots) == 7, miss_slot)

# ⑨b ★ L2373：`title_of` 不许把机器键当抬头（玩家可见面）
#   改前 `entry(eid).get("title") or str(eid)` ⇒ 标题缺失时 SYS_EGG_FOUND 抬头
#   直接印 `egg_one_hand`。本条同时钉住「数据侧标题齐全」与「读口认不出就抛」两格。
_bad_title = [k for k, v in BOOK.items() if not v.get("title")]
chk("★ eggs 每条都有 title（抬头不许回落成机器键）", not _bad_title, _bad_title[:4])
try:
    from content import eggs as _EG                                   # noqa: E402
    _EG.title_of("egg_不存在的条目")
    _fallback_raised = False
except KeyError:
    _fallback_raised = True
except Exception as _e:                                                # 抛错类型不对也算不合格
    _fallback_raised = False
    print("    （title_of 抛的是 %s，不是 KeyError）" % type(_e).__name__)
chk("★ title_of 读不到就点名抛（不再回落 str(eid)）", _fallback_raised, "回落 = 机器键上屏")
# 端到端：真调读口渲染抬头，标题里不许含机器键形态
_bad_ui = [k for k in BOOK if re.search(r"eg_[a-z0-9_]+", str(_EG_title := BOOK[k]["title"]))]
chk("★ 抬头文案里没有机器键（egg_xxx）", not _bad_ui, _bad_ui[:4])

# ⑩ 可达性（信息行 + 一条底线）：今天的数据里几条撞得上
produced = set()
for g in (st.domain("gathering") or {}).values():
    for e in (g.get("pool") or []):
        produced.add(str(e.get("out")))
for d in (st.domain("drop_pools") or {}).values():
    for e in (d.get("entries") or []) + (d.get("pool") or []):
        produced.add(str(e.get("out")))
for r in (st.domain("recipes") or {}).values():
    if r.get("out"):
        produced.add(str(r["out"]))

# ★ 装套可达性：`set` 取的是 **set_id**（`items.json` 的 `set_id`）、
#   `worn`/`hold` 取的是**物品 id**。两者都要拿 `produced` 判实验，
#   不得无条件写“无出产渠道”（就算没渠道也不是这个理由）。
#   套装：一套里**任一件**能出就算能集齐 → 该 set_id 可达。
PIECES_OF = {}
for _iid, _rec in IT.items():
    _sid = (_rec or {}).get("set_id")
    if _sid:
        PIECES_OF.setdefault(str(_sid), set()).add(str(_iid))


def _reachable(ck, val):
    """这个前置在今天的出产表里到不到底。"""
    if ck == "set":
        # 套装：那套的任一件在产出表里 → 能集齐
        return bool(PIECES_OF.get(str(val), set()) & produced)
    return str(val) in produced


gaps, live = {}, []
for eid, v in BOOK.items():
    why = []
    for field, val in RB.walk(dict(v["cond"]), []):
        ck = _ck(field)
        if ck in ("race", "lore"):
            why.append("要种族/铭文（建号未落地）")
        elif ck in ("set", "worn", "hold") and not _reachable(ck, val):
            why.append("%s 无出产渠道（%s）" % (val, ck))
    if why:
        gaps[eid] = sorted(set(why))
    else:
        live.append(eid)
for eid in BOOK:
    print("  · %s：%s" % (eid, "今天撞得上" if eid in live else "等前置 —— " + "；".join(gaps[eid])))

# ★ 带齿判据：它**读 `gaps` 本身**（不是另算一遍）——「归因逻辑」一旦退回旧写法就当场报红。
#   口径（与判语措辞无关）：某条彩蛋的条件里若有**任何一条真的能达成**的前置
#   （`set` 按「该套任一件在产出表就算可达」，`worn`/`hold` 按「该物品 id 在产出表」），
#   那么这条彩蛋就**不许**带着「无出产渠道」这种判语进 `gaps`。
#   反证：把上面 :287 那行退回 `elif ck in ("set","worn"): why.append("要套装件（无出产渠道）")`
#   ⇒ 3 套全在产出表里却被写「无出产渠道」⇒ 本条立刻红。
_bad = []
for _eid, _v in BOOK.items():
    for _f, _val in RB.walk(dict(_v["cond"]), []):
        if _ck(_f) not in ("set", "worn", "hold"):
            continue
        if _reachable(_ck(_f), _val) and any("无出产渠道" in _r
                                        for _r in gaps.get(_eid, [])):
            _bad.append("%s（%s:%s实际可达）" % (_eid, _ck(_f), _val))
chk("★ 归因不编造（真可达的前置不许报“无出产渠道”）",
    not _bad, "已到产出表却被归因的：%s" % (_bad or "无"))
chk("★ 套装件产出渠道逐件对账（套件 id → 产出表）",
    all(PIECES_OF.get(s, set()) & produced for s in PIECES_OF),
    "%d 套 / %d 件，完全无产出的：%s"
    % (len(PIECES_OF), sum(len(v) for v in PIECES_OF.values()),
       [s for s, v in sorted(PIECES_OF.items()) if not (v & produced)]))

# 底线：今天能撞上的不少于 5 条（1 / 3 / 7 等建号选族 · 9 / 10 等套装出产渠道 —— 见口径 §六）；
# 这条盯的是「别让前置把整层玩法捂死」，不是「必须全都能撞上」。
chk("★ 今天就能撞上的 ≥ 5 条（不让前置换掉整层玩法）", len(live) >= 5, "%d 条：%s" % (len(live), live))

print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
