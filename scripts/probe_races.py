# -*- coding: utf-8 -*-
"""探针：races 域读得到 · 六族形状对（2 正 1 负 · 至少一条可见性）· 数值天赋值域合理。

用法（在 aetheran-package 仓根跑）：
    GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_races.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402

ok = True
KINDS = ("可见性", "数值", "经济")


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


print("探针：races 域（六族天赋）")
st = load_stack(str(REPO))
st.install()

# ① 域读得到
rc = st.domain("races")
chk("races 域读得到", rc is not None, "%d 族" % (len(rc) if rc else 0))
if not rc:
    sys.exit(1)

# ② 六族
chk("六族齐全", len(rc) == 6, " · ".join(v["name"] for v in rc.values()))

# ③ 每族 2 正 1 负
bad = [k for k, v in rc.items() if len(v.get("talents", [])) != 2 or not v.get("cost")]
chk("每族 2 条正天赋 + 1 条负代价", not bad, "例外：%s" % bad if bad else "")

# ④ ★ 品味判据：每族正向里至少一条「可见性」
bad4 = [k for k, v in rc.items()
        if not any(t.get("kind") == "可见性" for t in v.get("talents", []))]
chk("★ 每族至少一条「可见性」正天赋", not bad4, "缺：%s" % bad4 if bad4 else "")

# ⑤ kind 合法
bad5 = []
for k, v in rc.items():
    for t in list(v.get("talents", [])) + [v.get("cost")]:
        if t and t.get("kind") not in KINDS:
            bad5.append("%s/%s=%s" % (k, t.get("id"), t.get("kind")))
chk("天赋类型合法（可见性/数值/经济）", not bad5, " · ".join(bad5))

# ⑥ id 唯一
ids = []
for k, v in rc.items():
    ids.append(k)
    ids += [t["id"] for t in v.get("talents", [])]
    ids.append(v["cost"]["id"])
chk("id 全局唯一", len(ids) == len(set(ids)), "%d 个 id" % len(ids))

# ⑦ 六句「为什么来」各不相同
lines = [v.get("line", "") for v in rc.values()]
chk("六句「为什么来」互不相同", len(set(lines)) == 6 and all(lines))

# ⑧ 数值类天赋的 values 值域（百分比 ±25 内）
bad8 = []
for k, v in rc.items():
    for t in list(v.get("talents", [])) + [v.get("cost")]:
        for key, val in (t or {}).get("values", {}).items():
            if "pct" in key and not (-25 <= val <= 25):
                bad8.append("%s.%s=%s" % (t["id"], key, val))
chk("数值类天赋百分比在 ±25 内", not bad8, " · ".join(bad8))

# ⑨ schema 在
sch = REPO / "schemas/races.schema.json"
chk("races.schema.json 在位", sch.exists(), str(sch.name))

# ⑩ 通路与反面都写了（设计判据：每族一条别人走不了的路 + 一条真的疼的代价）
bad10 = [k for k, v in rc.items() if not v.get("path") or not v.get("flip")]
chk("每族都写了「专属通路 + 反面」", not bad10, "缺：%s" % bad10 if bad10 else "")

print()
print("六族速览：")
for k, v in rc.items():
    plus = " · ".join("%s(%s)" % (t["name"], t["kind"]) for t in v["talents"])
    print("  %-16s %s  →  正：%s ｜ 负：%s(%s)" % (
        k, v["name"], plus, v["cost"]["name"], v["cost"]["kind"]))

print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
