# -*- coding: utf-8 -*-
"""探针：npcs 域（14 位 · 三卡齐全 · 位置真在图上 · 口头禅互不相同）。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_npcs.py
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
PERSONA_KEYS = ("look", "temper", "likes", "hates", "habit", "routine", "catch")
SOUL_KEYS = ("wants", "fears", "conflict", "why_here", "theme")
TONE_KEYS = ("words", "rhythm", "attitude", "focus", "pause")
FUNCS = {"inn", "shop", "smith", "strengthen", "heal", "revive", "quest", "board",
         "rank", "herb", "hint", "talk", "train", "appraise", "trade", "lore"}


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


print("探针：npcs 域（14 位）")
st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
st.install()
np_ = st.domain("npcs")
mp = st.domain("maps")
chk("npcs 域读得到", np_ is not None, "%d 位" % (len(np_) if np_ else 0))
chk("maps 域读得到（交叉校验要用）", mp is not None)
if not (np_ and mp):
    sys.exit(1)

chk("14 位齐全", len(np_) == 14, " · ".join(v["name"] for v in np_.values()))

# ① 三卡齐全
bad = [k for k, v in np_.items() if not all(f in v for f in ("persona", "soul", "tone"))]
chk("每位都有三卡（人设/灵魂/语气）", not bad, " · ".join(bad))

# ② 人设卡七项
bad2 = [k for k, v in np_.items() if not all(f in v.get("persona", {}) for f in PERSONA_KEYS)]
chk("人设卡七项齐全（含口头禅）", not bad2, " · ".join(bad2))

# ③ 灵魂卡五问
bad3 = [k for k, v in np_.items() if not all(f in v.get("soul", {}) for f in SOUL_KEYS)]
chk("灵魂卡五问齐全", not bad3, " · ".join(bad3))

# ④ 语气档五项
bad4 = [k for k, v in np_.items() if not all(f in v.get("tone", {}) for f in TONE_KEYS)]
chk("语气档五项齐全", not bad4, " · ".join(bad4))

# ⑤ ★ 跨域：位置真在图上
bad5 = []
for k, v in np_.items():
    ids = [n["id"] for n in mp.get(v.get("map"), {}).get("nodes", [])]
    if v.get("subarea") not in ids:
        bad5.append("%s → %s/%s" % (k, v.get("map"), v.get("subarea")))
chk("★ 每位的位置都在 maps 域的节点里", not bad5, " · ".join(bad5))

# ⑥ funcs 合法
bad6 = [k for k, v in np_.items() if set(v.get("funcs", [])) - FUNCS]
chk("funcs 取值都在约定集合里", not bad6, " · ".join(bad6))

# ⑦ ★ 品味判据：口头禅互不相同（每人有自己的腔）
catches = [v["persona"]["catch"] for v in np_.values()]
chk("★ 14 位口头禅互不相同", len(set(catches)) == 14, "%d 种" % len(set(catches)))

# ⑧ 灵魂卡的「矛盾」都写了（活人感的来源）
bad8 = [k for k, v in np_.items() if not v["soul"].get("conflict")]
chk("★ 每位都写了「矛盾」", not bad8, " · ".join(bad8))

# ⑨ dialogue id 唯一
dids = [v["dialogue"] for v in np_.values()]
chk("对话树 id 唯一", len(set(dids)) == len(dids))

print()
print("14 位速览（位置 · 功能 · 口头禅 · 矛盾）:")
for k, v in np_.items():
    print("  %-14s %-6s %-22s %-12s %s" % (
        v["name"], v["subarea"], "/".join(v.get("funcs", [])) or "—",
        v["persona"]["catch"], v["soul"]["conflict"][:26]))
print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
