# -*- coding: utf-8 -*-
"""规范化 items.json 的词条 stat（照 11_装备特色词条池 §六 的规范）：
  · mo → mo_max（属性字典的标准键）
  · 效果类词条补 note（若缺）
用法：python scripts/normalize_items.py
"""
import io
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(REPO, "content/data/items.json")

# 数值类：必须用标准键
NUMERIC = {"hp", "atk", "matk", "def", "res", "spd", "hit", "eva", "crit", "critdmg",
           "block", "pen", "pen_res", "heal_pow", "mo_max", "res_element"}
ELEM_RES = {"res_fire", "res_ice", "res_water", "res_thunder", "res_earth", "res_wind",
            "res_light", "res_shadow"}
RENAME = {"mo": "mo_max", "mp": "mo_max", "mdef": "res"}

it = json.load(io.open(P, encoding="utf-8"))
renamed = noted = 0
for k, v in it.items():
    affs = v.get("affixes") or []
    for a in affs:
        s = a.get("stat", "")
        if s in RENAME:
            a["stat"] = RENAME[s]
            renamed += 1
        s = a["stat"]
        # 效果类（既不是数值类也不是元素抗）必须带 note
        if s not in NUMERIC and s not in ELEM_RES and not a.get("note"):
            a["note"] = "效果类词条（改玩法/规则，非数值加成）"
            noted += 1
io.open(P, "w", encoding="utf-8", newline="\n").write(json.dumps(it, ensure_ascii=False, indent=2) + "\n")
print("规范化完成：重命名 %d 处 · 补 note %d 处" % (renamed, noted))
