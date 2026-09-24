# -*- coding: utf-8 -*-
"""探针：items 域 —— kind/quality/slot 合法 · ★ 词条 stat 守命名规范 · 遗物必有「来处」。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_items.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402

ok = True
KINDS = {"武器", "上甲", "下甲", "头盔", "靴子", "饰品", "材料", "道具"}
QUALITIES = {"普通", "精制", "稀有", "遗物"}
SLOTS = {"weapon", "armor_top", "armor_bottom", "helmet", "boots", "accessory"}
# 数值类（必须用属性字典标准键）—— 照 11_装备特色词条池 §六
NUMERIC = {"hp", "atk", "matk", "def", "res", "spd", "hit", "eva", "crit", "critdmg",
           "block", "pen", "pen_res", "heal_pow", "mo_max"}
ELEM_RES = {"res_fire", "res_ice", "res_water", "res_thunder", "res_earth", "res_wind",
            "res_light", "res_shadow"}
SPECIAL = {"res_element"}          # 唯一允许的笼统写法（必须带 note）


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


print("探针：items 域（装备 / 材料 / 道具）")
st = load_stack(str(REPO))
st.install()
it = st.domain("items")
chk("items 域读得到", it is not None, "%d 条" % (len(it) if it else 0))
if not it:
    sys.exit(1)

equip = {k: v for k, v in it.items() if v["kind"] in KINDS - {"材料", "道具"}}

# ① 三键合法
chk("kind 合法", not [k for k, v in it.items() if v["kind"] not in KINDS])
chk("quality 合法", not [k for k, v in equip.items() if v.get("quality") not in QUALITIES])
chk("slot 合法", not [k for k, v in equip.items() if v.get("slot") not in SLOTS])

# ② 装备类字段齐
bad2 = [k for k, v in equip.items() if not v.get("affixes")]
chk("每件装备都有词条", not bad2, " · ".join(bad2[:4]))

# ③ ★ 词条 stat 守规范
bad3 = []
for k, v in equip.items():
    for a in v.get("affixes", []):
        s = a.get("stat", "")
        if s in NUMERIC or s in ELEM_RES:
            continue
        if s in SPECIAL:
            if not a.get("note"):
                bad3.append("%s.%s 缺 note" % (k, s))
            continue
        # 效果类：必须带 note（说明它改了什么规则）
        if not a.get("note"):
            bad3.append("%s.%s 效果类缺 note" % (k, s))
chk("★ 词条 stat 守命名规范（数值类用标准键 · 效果类带 note）", not bad3, " · ".join(bad3[:5]))

# ④ ★ 遗物必有「来处」
bad4 = [k for k, v in it.items() if v.get("quality") == "遗物" and not v.get("lore")]
chk("★ 每件遗物都有「来处」", not bad4, " · ".join(bad4[:5]))
relics = [k for k, v in it.items() if v.get("quality") == "遗物"]

# ⑤ 套装件有 set_id
sets = {}
for k, v in it.items():
    if v.get("set_id"):
        sets.setdefault(v["set_id"], []).append(k)
chk("套装件都有 set_id", bool(sets), " · ".join("%s×%d" % (s, len(ks)) for s, ks in sets.items()))

# ⑥ 「来处」不是套话（长度与去重）
lores = [v["lore"] for v in it.values() if v.get("lore")]
chk("「来处」互不相同", len(set(lores)) == len(lores), "%d 条" % len(lores))
short = [k for k, v in it.items() if v.get("lore") and len(v["lore"]) < 8]
chk("「来处」都不是敷衍（≥8 字）", not short, " · ".join(short[:4]))

print()
by_kind = {}
for k, v in it.items():
    by_kind[v["kind"]] = by_kind.get(v["kind"], 0) + 1
print("  · 按 kind：" + " · ".join("%s %d" % (a, b) for a, b in sorted(by_kind.items())))
by_q = {}
for v in equip.values():
    by_q[v.get("quality", "?")] = by_q.get(v.get("quality", "?"), 0) + 1
print("  · 装备按品阶：" + " · ".join("%s %d" % (a, b) for a, b in sorted(by_q.items())))
print("  · 遗物 %d 件（全带「来处」）· 套装 %d 套" % (len(relics), len(sets)))
print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
