# -*- coding: utf-8 -*-
"""面板接线探针：骑士 10 级面板能不能由「数据 + 引擎形状」算出来。

判据：与 03_职业与技能/06_六职业对照_v2.md 的骑士 10 级面板逐项对得上。

★ 2026-09-25 期望值更新（v1 打样 → v2 对照）：v2 重做时骑士上调为
  max_hp 438→462 · def 54.4→69.6（让「骑士 = 六职业最肉」这条取向成立）·
  atk 62.4→62.2（成长系数微调）。**数据没动，是探针的期望值过时**（面板探针此前一直没跑）。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, ENGINE)
sys.path.insert(0, os.path.join(ENGINE, "extends"))

from saintess_engine.package import load_stack          # noqa: E402

st = load_stack(PKG, exts=[os.path.join(ENGINE, "extends")])
st.install()

from content import panel_build                          # noqa: E402
from saintess_engine import config                       # noqa: E402

print("panel_layers_fn 已挂:", config.get_hook("panel_layers_fn") is not None)

actor = panel_build.build_actor("cls_knight", 10, {"STR": 18, "VIT": 13, "WIL": 4})
print("栈 id:", actor["panel_stack"])

from ext_combat.battle.stats import actor_stats          # noqa: E402

panel = actor_stats(None, actor)
want = {"max_hp": 462, "max_mp": 66, "atk": 62.22, "def": 69.6, "mdef": 24.4,
        "spd": 109.0, "hit": 108.5, "block": 40.8}
print("")
print("  %-10s %-10s %-10s %s" % ("键", "引擎算出", "打样期望", "判定"))
ok = True
for k, v in want.items():
    got = panel.get(k)
    good = got is not None and abs(got - v) < 0.05
    ok &= good
    print("  %-10s %-10s %-10s %s" % (k, got, v, "✅" if good else "❌"))
print("")
print("  crit（数值 24 → 率 %.4f）:" % (24 / (24 + 500)), panel.get("crit"))
print("  面板全部键:", sorted(panel))
print("")
print("===== %s =====" % ("面板由数据+引擎形状算出，与打样一致 ✅" if ok else "有项对不上 ❌"))
sys.exit(0 if ok else 1)
