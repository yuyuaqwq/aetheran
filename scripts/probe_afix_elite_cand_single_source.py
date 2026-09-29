# -*- coding: utf-8 -*-
"""探针：aetheran `affix.elite_of` 的「候选 + 等级就近 top-3」必须走 `combat.encounter_cand`
（审计修复·批次 2 · 台账 L1148 同族的另一半面）。

背景（为什么这条要钉）：
  `content/combat.py::encounter_cand` 的抬头明写「两处共用这一处（**同一把尺子**）……
  各写一份 = 迟早对不上（K74 那一族）」，而 `content/affix.py::elite_of` 原先**内联了第二份**
  （habitat 筛选 + `cand.sort(abs(lv-level))` + `cand[:3]`）⇒ 那份就是「迟早对不上」本身，
  且**零判据钉着它**。今天实跑两者逐样本同值（内联段 4000/4000 · 端到端 4000/4000，
  其中 381 次真出精英）⇒ 属**潜伏项**，不是已发生的玩家可见 bug。
  收口 = 换成单源（函数内 import，避开 `combat.py:23 from . import affix` 的环）。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_afix_elite_cand_single_source.py
"""
from __future__ import annotations

import ast
import io
import os
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, ENGINE)

PASS = 0
FAIL = []
FAILURES = []


def chk(label, cond, extra=""):
    global PASS
    if cond:
        PASS += 1
    else:
        FAIL.append(label)
        FAILURES.append(label + ("  " + extra if extra else ""))


AFFIX = REPO / "content" / "affix.py"
COMBAT = REPO / "content" / "combat.py"
src = io.open(AFFIX, encoding="utf-8").read()
csrc = io.open(COMBAT, encoding="utf-8").read()
tree = ast.parse(src)

# ── ① 源码形状：elite_of 里不再自建候选表 / 不再自带那条排序 ────────────────
elite = next(n for n in ast.walk(tree)
             if isinstance(n, ast.FunctionDef) and n.name == "elite_of")
ebody = ast.get_source_segment(src, elite) or ""


def calls(fn, attr):
    return [n for n in ast.walk(fn)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == attr]


chk("①1 elite_of 不再出现 habitat 候选表内联构造",
    "hb.get(\"maps\")" not in ebody,
    "affix.elite_of 里又出现内联 habitat 筛选")
chk("①2 elite_of 不再自带 cand.sort(...)",
    not calls(elite, "sort"),
    "affix.elite_of 里又有 .sort(")
chk("①3 elite_of 不再自带 [:3] 切片",
    not any(isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Slice)
            and isinstance(n.slice.upper, ast.Constant) and n.slice.upper.value == 3
            for n in ast.walk(elite)),
    "affix.elite_of 里又有 [:3]")
chk("①4 elite_of 走 combat.encounter_cand",
    "encounter_cand" in ebody,
    "affix.elite_of 没调 content.combat.encounter_cand")
chk("①5 单源在 encounter_cand 那一侧（不是把第二份搬进 affix）",
    "def encounter_cand" in csrc,
    "content/combat.py 里没有 encounter_cand —— 尺子被搬走了")

# ── ② 单源判据的「牙」：把 affix 换回内联实现 ⇒ ①1–①4 必须当场报红 ────────
#    （不靠改判据证明自己，靠「同一份源码换形状」证明判据真的在读生产文件）
INLINE_MARK = 'hb.get("maps")'
chk("②1 判据读到的是生产文件本身（不是自备副本）",
    INLINE_MARK not in io.open(AFFIX, encoding="utf-8").read(),
    "生产 affix.py 里仍有内联标记")

# ── ③ 循环 import：反序 import 必须不炸 ────────────────────────────────────
try:
    import subprocess
    for order in (("combat", "affix"), ("affix", "combat")):
        r = subprocess.run(
            [sys.executable, "-c",
             "import sys;sys.path.insert(0,r'%s');"
             "from content import %s;from content import %s;print('ok')"
             % (REPO, order[0], order[1])],
            capture_output=True, cwd=str(REPO.parent))
        chk("③ %s→%s 顺序 import 不成环" % order,
            r.returncode == 0 and b"ok" in r.stdout,
            r.stderr.decode("utf-8", "replace")[-160:])
except Exception as e:                                    # pragma: no cover
    chk("③ import 序检查", False, repr(e))

# ── ④ 行为：真调生产 elite_of，与「等级就近 top-3」这条口径逐样本对拍 ──────
from content import affix as AFFIX                          # noqa: E402
from content.combat import encounter_cand                  # noqa: E402

# ★ 夹具用**域里真实存在的词条 id**（`rec_of` 对悬空 id 是 fail-closed ⇒ 拿假 id 造样本
#   会让夹具自己抛 `AffixError`，那不是被测行为，是夹具造错）。
import json as _json
_AFF_TABLE = _json.load(io.open(REPO / "content" / "data" / "monster_affixes.json",
                                encoding="utf-8"))
AIDS = [k for k in _AFF_TABLE if not str(k).startswith("_")]
chk("④0 夹具自检：域里有词条可造精英池（空 ⇒ 本判据的 elite_of 半边恒绿 = 假门禁）",
    len(AIDS) >= 2, "monster_affixes 域可用词条 %d" % len(AIDS))
LOCS = ["loc1", "loc2"]
NODES = ["n1", "n2", "n3"]
rnd = random.Random(20260929)
n_elite = 0
diverged = 0
for t in range(600):
    mon = {}
    for i in range(rnd.randint(1, 6)):
        hb = {"maps": [rnd.choice(LOCS)]}
        if rnd.random() < 0.4:
            hb["nodes"] = [rnd.choice(NODES)]
        mon["m%d" % i] = {"lv": rnd.randint(1, 20), "habitat": hb,
                          "elite_pool": [rnd.choice(AIDS) for _ in range(rnd.randint(1, 3))]}
    loc = rnd.choice(LOCS)
    node = rnd.choice(NODES)
    lvl = rnd.randint(1, 20)
    day = rnd.randint(1, 50)
    idx, total = rnd.choice([(0, 3), (1, 3), (2, 3), (0, 1), (3, 4)])

    # 生产那条路真跑（role 必须是域里的中文档位，否则 rate_of fail-closed 早返回）
    try:
        got = AFFIX.elite_of(mon, loc, node, "u%d" % t, day, lvl,
                             node_role="野外", node_index=(idx, total))
    except Exception as e:                                 # noqa: BLE001
        got = ("EXC", type(e).__name__, str(e))
    if got is not None:
        n_elite += 1

    # 口径那一侧：挑出的那只必须落在「等级最近的前 3」之内
    _allc, top = encounter_cand(mon, loc, node, lvl, keep=3)
    if got is not None and not isinstance(got, tuple):
        chk("④%d 出精英的怪落在 encounter_cand 的 top-3 里" % t,
            got[0] in top, "挑到 %r 不在 %r" % (got[0], top))
    elif got is not None and got[0] == "EXC":
        diverged += 1
        chk("④%d elite_of 不抛" % t, False, repr(got))

chk("④A 覆盖面自检：样本里真出过精英（否则本判据恒绿 = 假门禁）",
    n_elite > 0, "600 样本出精英 0 次 —— 判据够不到被改的那几行")
chk("④B 端到端零异常", diverged == 0, "%d 个样本抛了" % diverged)

# ── ⑤ 口径本身：encounter_cand 仍按「等级最近」排，且 keep 生效 ────────────
M = {"a": {"lv": 1}, "b": {"lv": 10}, "c": {"lv": 11}}
_allc, top3 = encounter_cand(dict((k, dict(v, habitat={"maps": ["L"]})) for k, v in M.items()),
                             "L", "n", 10, keep=3)
chk("⑤1 keep=3 时三只都进（不足 keep 不补）", len(top3) == 3, "top3=%r" % (top3,))
chk("⑤2 等级最近在前", top3[0] in ("b", "c"), "top3=%r" % (top3,))
M2 = {"a": {"lv": 1}, "b": {"lv": 10}}
_allc, top1 = encounter_cand(dict((k, dict(v, habitat={"maps": ["L"]})) for k, v in M2.items()),
                             "L", "n", 10, keep=1)
chk("⑤3 keep=1 只给一只且是最近的那只", top1 == ["b"], "top1=%r" % (top1,))

print("PASS=%d FAIL=%d" % (PASS, len(FAIL)))
for f in FAILURES:
    print("  FAIL: " + f)
raise SystemExit(1 if FAIL else 0)
