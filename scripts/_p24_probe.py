# -*- coding: utf-8 -*-
"""P2-4 取证：真跑引擎那条注入面，看 texts 的 value 被填成什么 —— 即玩家真看到的那一行。"""
import os, sys, time, json, io
REPO = r"C:/Users/yuyu/aetheran-package"
ENGINE = os.environ.get("GWEN_ENGINE", r"C:/Users/yuyu/framework-engine")
sys.path.insert(0, ENGINE); sys.path.insert(0, REPO)
from saintess_engine.package import load_stack
st = load_stack(REPO, inject={"db_path": os.path.join(os.environ["LOCALAPPDATA"],"Temp","ast_p24.db"),
                               "clock": time.time})
st.install()
from ext_combat.battle import effects as EF
BT = st.optional_submodule("battle_text")
TX = json.load(io.open(os.path.join(REPO,"content","data","texts.json"), encoding="utf-8"))

def render(slot, **kw):
    t = (TX.get(slot) or {}).get("value","")
    for k,v in kw.items(): t = t.replace("{%s}"%k, str(v)).replace("{%s:.0f}"%k, str(v))
    return t

print("=== 屏上实况：引擎真传 machine key 时，texts 那句会印成什么 ===")
cases = [
    ("COMBAT_EFFECTS_STACK_ADD",   dict(key="aim", n="3", cap="/6", amount="1")),
    ("COMBAT_EFFECTS_STACK_APPLIED",dict(key="aim", name="田鼠", turns="30")),
    ("COMBAT_EFFECTS_IMMUNE_CONTROL", dict(name="田鼠", key="silence_lock")),
    ("COMBAT_GAUGE_GAIN",          dict(bar="shaken", add="2", val="4", maxcap="6")),
    ("COMBAT_GAUGE_TRIGGER",       dict(bar="shaken", count="3")),
    ("COMBAT_CORE_UNKNOWN_ACTION", dict(action="nosuchverb")),
    ("COMBAT_RES_SHORT",           dict(res="RES_OATH", rv="6", cur="2")),
]
for slot, kw in cases:
    print("  %-30s -> %s" % (slot, render(slot, **kw)))
print()
print("=== 结论依据 ===")
print("  引擎 gauge/__init__.py:232  _cue(... 'battle.gauge.gain', {'bar': bar_key, ...})  ← 直传 bar_key")
print("  引擎 battle/effects.py:448 _cue(... 'battle.effects.stack_add', {'key': key, ...})  ← 直传 key")
print("  包内 enemy_bar 显示名表：", "无（grep 0 命中）")
