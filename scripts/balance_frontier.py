# -*- coding: utf-8 -*-
"""档位阶梯的**可达集**（★ B3-18）：把「三项硬要求」换算成一张表，供选点。

三项硬要求：
  ① 跨原型严格不越档（`probe_monsters` ⑬）  ② 打得过（`probe_combat` ④）
  ③ 原型有幅度（`14_怪物原型_v1.md` 那张表的意义）

代数（`n_me` = 玩家击杀它的行动次数 · `n_them` = 它击杀玩家的行动次数 · `R` = atk 每档增幅）：

```text
②  ⇒ n_me(t) ≤ n_them(t)/G           （G = 打得过的余量，实机扫描边界 ≈1.0–1.2）
   ⇒ hp 阶梯总跨度 H = Π n_me(t+1)/n_me(t) ≤ g(普通)/(G·(1+R)³)      （n_them 逐档 ×1/(1+R)）
①  ⇒ 原型幅度 δ ≤ 档间距 ⇒ δ_hp ≈ (每档跨度−1)/0.95 · δ_atk ≈ (atk 每档跨度−取整量子)/0.75
③  ⇒ 要 δ 大 ⇒ 档间距大 ⇒ R 大 ⇒ H 小（同一条预算两头拉）
```

本工具枚举 (普通档 n_them, atk 每档增幅 R) 网格，打印每格的 H 上限与 δ 的**上界解析值**，
并给出按该点上界造出来的阶梯（hp 每档涨到「余量允许」的位置）—— 选点用。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/balance_frontier.py
"""
from __future__ import annotations

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import rebuild_monsters as R                                        # noqa: E402

G = 1.05                      # 打得过的余量（扫描实测边界 1.0–1.2，取 1.05 当预算下限）


def ladder(nt0, step, defn, spd):
    """按 (普通档 n_them, atk 每档增幅) 造一条阶梯：hp 每档涨到「余量允许」的位置。"""
    nt = [nt0 / (1 + step) ** i for i in range(5)]
    nm, prev = [], 4.0
    for i in range(5):
        if i:
            prev = min(prev * (1 + step), nt[i] / G)
        nm.append(prev)
    R.TIERS = {t: {"n_me": nm[i], "n_them": nt[i], "def_n": defn[i], "spd": spd[i],
                   "res_coef": [0.50, 0.55, 0.60, 0.65, 0.72][i]}
               for i, t in enumerate(R.TIER_ORDER)}
    R._SIGMA_CACHE.clear()
    R._DELTA_CACHE.clear()
    d = R.delta_of()
    return d, [nt[i] / nm[i] for i in range(5)], nm, nt


if __name__ == "__main__":
    print(__doc__.split("用法")[0].strip().splitlines()[-3])
    print("%-8s %-6s %-7s %-7s %-7s %-7s | %-24s | %-22s" %
          ("n_them0", "R", "δ_hp", "δ_atk", "δ_def", "δ_spd", "hp 阶梯（行动次数）", "g=n_them/n_me"))
    best = None
    for nt0 in (12.0, 14.0, 16.0, 18.0, 20.0):
        for step in (0.10, 0.15, 0.20, 0.25, 0.30):
            d, g, nm, nt = ladder(nt0, step, [1.0, 1.5, 2.0, 2.5, 3.0], [92, 104, 116, 128, 140])
            ok = all(x >= G for x in g[:4]) and g[4] < 0.8
            score = min(d["hp"], d["atk"], d["def"], d["spd"])
            print("%-8.1f %-6.2f %-7.3f %-7.3f %-7.3f %-7.3f | %-24s | %-22s %s" %
                  (nt0, step, d["hp"], d["atk"], d["def"], d["spd"],
                   " ".join("%.2f" % x for x in nm), " ".join("%.2f" % x for x in g),
                   "" if ok else "✗（余量或 Boss 条件不满足）"))
            if ok and (best is None or score > best[0]):
                best = (score, nt0, step, d, g, nm)
    if best:
        print()
        print("★ 均衡点：n_them(普通)=%.1f · atk 每档 +%.0f%% ⇒ min δ = %.3f"
              "（hp %.3f / atk %.3f / def %.3f / spd %.3f）"
              % (best[1], best[2] * 100, best[0], best[3]["hp"], best[3]["atk"],
                 best[3]["def"], best[3]["spd"]))
        print("  hp 阶梯：%s（普通→层主 跨度 %.2f×）"
              % (" ".join("%.2f" % x for x in best[5]), best[5][3] / best[5][0]))
        print("  余量 g：%s" % " ".join("%.2f" % x for x in best[4]))
