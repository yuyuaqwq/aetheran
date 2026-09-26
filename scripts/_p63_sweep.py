# -*- coding: utf-8 -*-
"""P-63 现算实验：Boss 单人档该缩到多少（一次性 · 不入提交，跑完删）。

对每个「单人 hp 倍数 m」× 等级 {18,19,20} × 六职业 × 16 种子 = 96 场真跑，
数胜场与出手中位数。用法：
  GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/_p63_sweep.py
"""
from __future__ import annotations

import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, ENGINE)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))

from saintess_engine.package import load_stack          # noqa: E402

_FIXED = 1790308800
st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": lambda: _FIXED})
st.install()
CB = st.optional_submodule("combat")
MON = st.domain("monsters")
import rebuild_monsters as RBM                          # noqa: E402
from content import cmds_ast as CA                      # noqa: E402

BOSS = "ms_boss_oath_sentry"
_classes = sorted(RBM.CLS)
_misses = [0.5, 0.45, 0.40, 0.35, 0.30, 0.28, 0.26, 0.25, 0.24, 0.22, 0.20, 0.18, 0.16, 0.14]

_orig = CB.party_scale_of
print("m      " + "  ".join("lv%d" % L for L in (18, 19, 20)))
for _m in _misses:
    CB.party_scale_of = lambda rec, party, _m=_m: ({"hp": _m} if party else {})
    row = []
    for _lv in (18, 19, 20):
        wins, acts = 0, []
        for _cid in _classes:
            for _s in range(16):
                _pl = {"cls": _cid, "level": _lv, "uid": "u_s", "name": "试",
                       "alloc": RBM.alloc_of(_lv, _cid)}
                _pl["hp"] = CA.hp_cap(_pl)
                _r, _l, _ = CB.run_auto(_pl, [BOSS], MON, seed=6100 + _s, party=1)
                wins += 1 if _r == "victory" else 0
                acts.append(sum(1 for x in _l if ("🌀 %s 开始出招" % _pl["name"]) in x))
        acts.sort()
        row.append("%2d/96 med=%-3d" % (wins, acts[len(acts) // 2]))
    print("%-6s " % _m + "  ".join(row))
CB.party_scale_of = _orig
