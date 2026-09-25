# -*- coding: utf-8 -*-
"""配平扫描（★ B3-18）：某只怪的 **atk / hp 倍率 → 胜率曲线**。

为什么要有它：`probe_combat` 只回答「这一版过不过」，回答不了「边界在哪」。
档位阶梯里 `n_them`（它打我几下）和 `n_me`（我打它几下）是一对**预算**：
前者要小（atk 才抬得起来）、后者要大（档位才分得开），而「打得过」把两者绑在一起 ——
本工具就是去量这条边界的（本轮据此定下 `n_them/n_me ≥ ~1.1` 与「层主在自己那一级 ≥83% 胜、
低 4 级 0 胜」的窗口）。

用法（包根）：
    GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/balance_sweep.py <怪 id> <等级> <atk 倍率列表> [hp 倍率列表]

例（守卫塔层主的可打性窗口）：
    python scripts/balance_sweep.py ms_bone_warden 17 1.0,1.2,1.4
    python scripts/balance_sweep.py ms_bone_warden 13 0.85,1.0 1.0,1.2

输出：每格 36 局（6 职业 × 6 固定种子）的胜场数与出手次数中位数 —— **固定种子**，
      两次跑同一格必须同数（否则就是随机源没锁）。
"""
from __future__ import annotations

import os
import random
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine"))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))

from saintess_engine.package import load_stack                      # noqa: E402

st = load_stack(REPO, inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_sw.db"),
                              "clock": 1.0})
st.install()
from content.apply import install_engine                            # noqa: E402
install_engine()
from content import combat as CB                                    # noqa: E402
from content import panel_build as PB                               # noqa: E402
import rebuild_monsters as RBM                                      # noqa: E402

MON = dict(st.domain("monsters"))
CLS = ["cls_knight", "cls_berserker", "cls_ranger", "cls_mage", "cls_priest", "cls_assassin"]


def _player(cid, lv):
    p = {"cls": cid, "level": lv, "uid": "u_%s_%d" % (cid, lv), "name": PB.classes()[cid]["name"],
         "alloc": RBM.alloc_of(lv, cid), "bag": {}, "gold": 0}
    p["hp"] = PB.hp_cap(p)
    return p


def run(mid, lv, amul, hmul, seeds=6):
    """一只怪的 (atk×amul, hp×hmul) 打 36 局：返回 (胜场, 出手中位, 最少, 最多)。"""
    m = dict(MON[mid])
    m["panel"] = dict(m["panel"])
    m["panel"]["atk"] = int(round(m["panel"]["atk"] * amul))
    m["panel"]["hp"] = int(round(m["panel"]["hp"] * hmul))
    wins, acts = 0, []
    for cid in CLS:
        for s in range(seeds):
            random.seed(5000 + s)                                   # 固定种子：同格必同数
            b = CB.build(_player(cid, lv), [mid], {mid: m})
            logs = []
            b.auto_run(logs)
            wins += 1 if b.result == "victory" else 0
            pa = b.sides["player"][0]
            acts.append(sum(1 for x in logs if ("🌀 %s 开始出招" % pa.get("name")) in x))
    acts.sort()
    return wins, acts[len(acts) // 2], acts[0], acts[-1]


def main(argv):
    mid, lv = argv[0], int(argv[1])
    amuls = [float(x) for x in argv[2].split(",")]
    hmuls = [float(x) for x in (argv[3].split(",") if len(argv) > 3 else ["1.0"])]
    base = MON[mid]["panel"]
    print("%s lv%d 基准 hp=%d atk=%d def=%d spd=%d（档=%s · 原型=%s）"
          % (mid, lv, base["hp"], base["atk"], base["def"], base["spd"],
             MON[mid].get("role"), MON[mid].get("archetype")))
    for hm in hmuls:
        for am in amuls:
            w, me, lo, hi = run(mid, lv, am, hm)
            print("  atk×%-5.2f(=%-4d) hp×%-5.2f(=%-6d) 胜 %2d/36  出手 med=%-3d [%d..%d]"
                  % (am, base["atk"] * am, hm, base["hp"] * hm, w, me, lo, hi))


if __name__ == "__main__":
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    main(sys.argv[1:])
