# -*- coding: utf-8 -*-
"""探针：texts 域（文案槽位表）—— 键名规则 · params 与 value 的占位对账 · 待填进度。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_texts.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402

ok = True
KEY_RE = re.compile(r"^(SCENE|READ|NPC|COMBAT|QUEST|ITEM|SYS|TITLE|WORLD|HOUR|WEATHER|UNID|TALK)_[A-Z0-9_]+$")
PH = re.compile(r"\{(\w+)\}")


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


print("探针：texts 域（文案槽位表）")
st = load_stack(str(REPO))
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

print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
