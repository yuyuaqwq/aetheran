# -*- coding: utf-8 -*-
"""P2-4 关键分层：29 条机器键槽位分成两类 ——
   ① **包侧自己填**的（取件点传的就是显示名 ⇒ 屏上没问题，不是缺陷）
   ② **引擎 cue 填**的（引擎直传机器键 ⇒ 屏上印 `aim` / `shaken` ⇒ 真缺陷，要改引擎）
   判据现算：槽位在 content/rules/battle_text.json 里声明了 ⇔ 由引擎 cue 填。"""
import ast, io, os, json, re
D = json.load(io.open("content/data/texts.json", encoding="utf-8"))
BT = json.load(io.open("content/rules/battle_text.json", encoding="utf-8"))
# battle_text.json 的形状：{cue 名: 槽位} 或 {域: {cue: 槽}}
engine_slots = {}
def walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(v, str) and v in D: engine_slots[v] = k
            else: walk(v)
    elif isinstance(o, list):
        for x in o: walk(x)
walk(BT)
KEYS = {"key","kind","bar","stat","cat","op","res","tag","action","val"}
cand = {}
for s, v in D.items():
    if not isinstance(v, dict): continue
    used = set(m.group(1) for m in re.finditer(r"\{(\w+)[:}]", v.get("value","")))
    if used & KEYS: cand[s] = sorted(used & KEYS)
eng  = [s for s in cand if s in engine_slots]
pkg  = [s for s in cand if s not in engine_slots]
print("=== 29 条分成两类（判据：content/rules/battle_text.json 有没有声明它）===")
print("\n② 引擎 cue 填的 = %d 条（★ 屏上会印机器键，要改引擎 ⇒ 交主线）" % len(eng))
for s in sorted(eng): print("   %-30s cue=%-34s %s" % (s, engine_slots[s], sorted(cand[s])))
print("\n① 包侧自己填的 = %d 条（取件点传显示名 ⇒ 屏上正常）" % len(pkg))
for s in sorted(pkg): print("   %-30s %s" % (s, cand[s]))
