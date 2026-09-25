# -*- coding: utf-8 -*-
"""探针：texts 域（文案槽位表）—— 键名规则 · params 与 value 的占位对账 · 待填进度。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_texts.py
"""
from __future__ import annotations

import os
import time
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402

ok = True
#: ★ B4-16 起 `RANK_*` 也在这一族里（公会评级那几张档名 —— 与 `scripts/rebuild_syscopy.py`
#:   的 KEY_RE 逐字同形：两处必须一起改，否则一个认一个不认）
KEY_RE = re.compile(r"^(SCENE|READ|NPC|COMBAT|QUEST|ITEM|SYS|TITLE|WORLD|HOUR|WEATHER|UNID|TALK|RANK)_[A-Z0-9_]+$")
PH = re.compile(r"\{(\w+)\}")


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


print("探针：texts 域（文案槽位表）")
st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
st.install()
tx = st.domain("texts")
chk("texts 域读得到", tx is not None, "%d 条" % (len(tx) if tx else 0))
if not tx:
    sys.exit(1)

# ① 每条结构
bad1 = [k for k, v in tx.items()
        if not isinstance(v, dict) or "value" not in v or "category" not in v]
chk("每条都有 value/category", not bad1, " · ".join(bad1[:5]))

# ② 键名规则
bad2 = [k for k in tx if not KEY_RE.match(k)]
chk("键名都符合 「类_对象_状态」规则", not bad2, " · ".join(bad2[:6]))

# ③ ★ params 声明的参数，value 里必须有对应占位
bad3 = []
for k, v in tx.items():
    for prm in v.get("params", []):
        if ("{%s}" % prm) not in v["value"]:
            bad3.append("%s 缺 {%s}" % (k, prm))
chk("★ 声明的 params 都在 value 里有占位", not bad3, " · ".join(bad3[:5]))

# ④ ★ value 里出现的占位，都声明过 params（防漏声明 + 防打错）
bad4 = []
for k, v in tx.items():
    used = set(PH.findall(v["value"]))
    decl = set(v.get("params", []))
    if used - decl:
        bad4.append("%s 未声明：%s" % (k, sorted(used - decl)))
chk("★ value 里的占位都已声明 params", not bad4, " · ".join(bad4[:5]))

# ⑤ 待填进度（不是错误，是工单进度）
todo = [k for k, v in tx.items() if "〔待填" in v["value"]]
print("  · 待填 %d 条 / 已写 %d 条" % (len(todo), len(tx) - len(todo)))

# ⑥ 分类计数
by_cat = {}
for k, v in tx.items():
    by_cat.setdefault(v.get("category", "?"), 0)
    by_cat[v["category"]] += 1
print("  · " + " · ".join("%s %d" % (c, n) for c, n in sorted(by_cat.items(), key=lambda x: -x[1])))

# ⑦ ★ B3-6a：场景口 —— 每个节点都取得到场景槽位（观察取的就是它）
from content.scene import resolve as _resolve, node_key as _nk        # noqa: E402

mp = st.domain("maps") or {}
nodes = [(loc, n["id"]) for loc, m in mp.items() for n in (m.get("nodes") or [])]
unr = [(loc, nd) for loc, nd in nodes if not _resolve(tx, loc, nd)]
chk("★ 地图上 %d 个节点都能取到场景槽位（节点级 %d）"
    % (len(nodes), len([1 for _l, nd in nodes if _nk(nd) in tx])), not unr, "取不到：%s" % unr)

# ⑧ ★ 真调「观察」（造档逐节点）—— 第一位那行必须就是该节点的场景正文
import asyncio                                                        # noqa: E402

from content import cmds_ast as CA                                    # noqa: E402


class _E:               # 「观察」只要 env.save()（落档是处理器的责任）
    text = ""

    def save(self):
        pass


def _look_first(loc, node):
    p = dict(CA.DEFAULT_PLAYER)
    p.update({"loc": loc, "node": node, "race": "human"})  # ★ P-10：档上要有族，否则第一眼是「选族菜单」而不是场景（探针测的是已建号的玩家）
    out = []

    async def _go():
        async for line in CA.look(_E(), None, "u_scene", p):
            out.append(line)

    asyncio.run(_go())
    return out


wrong = []
for loc, nd in nodes:
    sk = _resolve(tx, loc, nd)
    first = _look_first(loc, nd)[0]
    if first != tx[sk]["value"]:
        wrong.append((nd, first[:24]))
chk("★ 观察 逐节点产出的就是该节点的场景正文（%d 个节点）" % len(nodes), not wrong, "对不上：%s" % wrong[:4])

# ⑨ 节点级场景是正文（≥80 字 —— 工单占位只有 7~16 字，一跑就露）
short = [(k, len(tx[k]["value"])) for _l, nd in nodes if _nk(nd) in tx and len(tx[_nk(nd)]["value"]) < 80]
chk("★ 节点级场景都是正文（≥80 字）", not short, "%s" % short[:5])

# ⑩ 场景类没有待填（这一批的工单清完了）
todo_scene = [k for k, v in tx.items() if v.get("category") == "场景" and "〔待填" in v["value"]]
chk("场景类 0 条待填", not todo_scene, "%s" % todo_scene[:5])

print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
