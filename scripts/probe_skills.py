# -*- coding: utf-8 -*-
"""探针（第四刀）：skills 域读得到 · 六职业面板算得出 · 行动耗时 hook 挂上了。

用法（在 aetheran-package 仓根跑）：
    GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_skills.py
"""
from __future__ import annotations

import json
import os
import time
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, ENGINE)

from saintess_engine import config                                   # noqa: E402
from saintess_engine.package import load_stack, plan_stack           # noqa: E402

ok = True


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


print("探针：技能落地（第四刀）")
st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
print("  装入顺序：%s" % " → ".join(st.ids))
st.install()

# ① 域读得到
sk = st.domain("skills")
chk("skills 域读得到", sk is not None, "%d 条" % (len(sk) if sk else 0))
by_cls = {}
for sid, rec in (sk or {}).items():
    by_cls.setdefault(rec.get("owner_class", "?"), []).append(sid)
print("     六职业分布：%s" % " · ".join("%s %d" % (k, len(v)) for k, v in sorted(by_cls.items())))

# ② 七维完整性
need = ("name", "kind", "lv", "desc", "cd", "cast", "recover", "range", "mp", "power")
missing = [(sid, k) for sid, r in (sk or {}).items() for k in need if k not in r]
chk("30 条技能 7 维齐全（含 name/kind/lv/desc/cd/cast/recover/range/mp/power）", not missing,
    "" if not missing else str(missing[:4]))

# ③ 三份默认域 + actions
for d in ("commands", "texts", "tlogs", "classes", "skills"):
    chk("域 %-9s 有文件" % d, st.domain_path(d, required=False) is not None)

# ④ 六职业面板（引擎 PanelStack 真算）
from content import panel_build                                       # noqa: E402
from content.apply import install_engine                              # noqa: E402
from ext_combat.battle.stats import actor_stats                       # noqa: E402

install_engine()
print("  hook 状态：panel_layers_fn=%s  action_base_fn=%s  recover_base_fn=%s  time_model_fn=%s" % (
    bool(config.get_hook("panel_layers_fn")), bool(config.get_hook("action_base_fn")),
    bool(config.get_hook("recover_base_fn")), bool(config.get_hook("time_model_fn"))))

CLASSES = json.loads((REPO / "content" / "data" / "classes.json").read_text(encoding="utf-8"))
rows = []
for cid, c in CLASSES.items():
    lv = 10
    actor = panel_build.build_actor(cid, lv, c.get("suggest_alloc"))
    vals = actor_stats(None, actor)
    rows.append((c["name"], vals.get("max_hp"), vals.get("atk"), vals.get("matk"),
                 vals.get("def"), vals.get("mdef"), vals.get("spd"), vals.get("crit")))
    chk("%s 面板算得出（%d 键）" % (c["name"], len(vals)), len(vals) >= 10)

print()
print("  10 级面板（引擎 PanelStack 真算）：")
print("    %-8s %8s %7s %7s %7s %7s %7s %8s" % ("职业", "max_hp", "atk", "matk", "def", "mdef", "spd", "crit率"))
for r in rows:
    print("    %-8s %8.1f %7.1f %7.1f %7.1f %7.1f %7.1f %8.4f" % r)

# ⑤ 行动耗时 hook
ab, rb = config.get_hook("action_base_fn"), config.get_hook("recover_base_fn")
chk("action_base_fn('attack') = 60 刻", ab and abs(ab("attack") - 60) < 1e-9, "" if not ab else "%.1f" % ab("attack"))
chk("recover_base_fn('skill') = 50 刻", rb and abs(rb("skill") - 50) < 1e-9, "" if not rb else "%.1f" % rb("skill"))
rm = config.get_hook("recover_model_fn")
chk("recover_model_fn(spd=100, base=40) = 40 刻", rm and abs(rm(100, 40) - 40) < 1e-6, "" if not rm else "%.4f" % rm(100, 40))

# ⑥ 技能 7 维能喂给耗时模型
sid = "SKILL_MAG_ignite"
rec = sk.get(sid)
if rec:
    cast_ticks = config.get_hook("time_model_fn")(111.0, rec["cast"]["base"])
    chk("引燃 200 刻基准 @法师 spd 111 → %.1f 刻（≈191）" % cast_ticks, 180 < cast_ticks < 200)

print()
print("结论：", "全过 ✅" if ok else "有红 ❌")
sys.exit(0 if ok else 1)
