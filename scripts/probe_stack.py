# -*- coding: utf-8 -*-
"""阿斯特兰数据包 · 装配探针（可重跑）。

判据：
  ① plan_stack 把 10 个扩展包 + aetheran 按序摆好（11 层）
  ② load_stack + install() 不抛
  ③ 三份默认域（commands/texts/tlogs）读得到
  ④ binding('damage') 解析到 damage_full
  ⑤ ext_combat.calc_damage 走声明链：声明 25 对 摘掉绑定后的旧路 66
  ⑥ time_model_fn 委托到 F6_act_time

用法：
  GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_stack.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, ENGINE)
sys.path.insert(0, os.path.join(ENGINE, "extends"))

from saintess_engine.package import plan_stack, load_stack, PackageError  # noqa: E402

EXT = [os.path.join(ENGINE, "extends")]
ok = True

print("① plan_stack（装入顺序）")
try:
    plan = plan_stack(PKG, exts=EXT)
    for i, item in enumerate(plan, 1):
        print("   %2d. %-9s %s" % (i, item.get("kind"), item.get("id")))
    print("   共 %d 层（期望 11）" % len(plan))
    ok &= len(plan) == 11
except PackageError as e:
    print("   ❌ PackageError: %s" % e)
    raise SystemExit(1)

print("")
print("② load_stack + install()")
st = load_stack(PKG, exts=EXT)
st.install()
print("   ✅ 装载并装配成功")

print("")
print("③ 三份默认域")
for d in ("commands", "texts", "tlogs"):
    try:
        print("   %-9s ✅ %s 条" % (d, len(st.domain(d))))
    except Exception as e:
        ok = False
        print("   %-9s ❌ %s: %s" % (d, type(e).__name__, e))

print("")
print("④ 解析能力面")
print("   provides:", json.dumps({k: str(v)[:60] for k, v in (st.providers() or {}).items()},
                                 ensure_ascii=False))
print("   domain_decl:", list((st.domain_decl() or {}).keys()))

from saintess_engine import config                                     # noqa: E402
from saintess_engine.formula import binding_of                         # noqa: E402

hook = config.get_hook("formula_table_fn")
tbl = hook() if hook else None
did = binding_of("damage", table=tbl) if tbl else None
print("   formula_table_fn 已挂:", hook is not None)
print("   binding('damage') =", did, "（期望 damage_full）")
ok &= did == "damage_full"

print("")
print("⑤ 端到端：ext_combat.calc_damage 走声明链")
from ext_combat.battle.formulas import calc_damage                     # noqa: E402

declared = calc_damage(100, 50, level=20, variance=0.0)
print("   calc_damage(100, 50, level=20, variance=0) = %s（期望 25：def_mit 截到 0.75）" % declared)
ok &= declared == 25
config.set_hook("formula_bindings_fn", None)
legacy = calc_damage(100, 50, variance=0.0)
print("   摘掉绑定表 → %s（旧算法 atk²/(atk+def) = 66）⇒ 上面那条真的走了声明" % legacy)
ok &= legacy == 66

print("")
print("⑥ time_model_fn 委托 F6_act_time")
tm = config.get_hook("time_model_fn")
val = tm(200, 100) if tm else None
print("   time_model(spd=200, base=100) = %s（期望 70.710678）" % val)
ok &= val is not None and abs(val - 70.710678) < 1e-4

print("")
print("===== %s =====" % ("全部判据通过 ✅" if ok else "有判据未过 ❌"))
sys.exit(0 if ok else 1)
