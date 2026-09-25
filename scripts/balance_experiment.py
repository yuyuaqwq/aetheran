# -*- coding: utf-8 -*-
"""配平实验（固定种子 · 多场统计）：等级 × 职业 × 档位 → 胜率 / 出手次数 / 刻数。

★ 为什么有这份东西（B3-14）：`scripts/probe_*.py` 只回答「接缝对不对」，回答不了
  「一场战斗该打几个刻 / 打几下」。配平要的是**统计量**：同一配置跑 N 个固定种子，
  看胜率中位数与出手次数中位数 —— 单跑一场会把自己骗过去（同一份数据三次跑出
  97/98/104 那种）。

用法（在 aetheran-package 仓根跑）：
    python scripts/balance_experiment.py --seeds 40
    python scripts/balance_experiment.py --seeds 40 --monsters ms_bone_warden,ms_boss_oath_sentry
    python scripts/balance_experiment.py --seeds 40 --party cls_knight,cls_mage,cls_priest,cls_assassin \
        --monsters ms_boss_oath_sentry --levels 19

输出列：
    设计次数 = `rebuild_monsters.TIERS[档].hp_n × ARCH[原型].hp`（该怪自己那一档的设计击杀行动数，
               口径 = `12_怪物面板与精英词条池_v1.md` §一 的反推式；怪 hp 也是照它算出来的）
    胜率     = 该配置 N 场里 victory 的场数
    出手 med = 玩家侧「出手次数」的中位数（日志里 🌀 <名字> 开始出招… 的条数）
    刻 med   = 整场战斗耗掉的游戏内刻数（`battle._now`）
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine"))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))


#: `--alloc` 三种口径的中文说法（只用于实验输出；玩家侧的那份在 texts 槽位里）
_MODE_LABEL = {"flat": "按建议权重平铺 · 配平基准",
               "int": "照建议整数投法 · 玩家真敲得出来的那一份",
               "none": "一点不投 · 建号那 8 点没动"}


def _player(cls_id, level, gear=None, mode="flat"):
    """一份起手档：职业 + 等级 + 加点（走 `content.alloc` 那一个口）+ 可选装备。

    `mode`（★ P-34：战力基线口径 —— 三种都能量出来，别再用"感觉"）：
      flat = 按建议权重**平铺**（浮点 · **配平基准**：怪物面板就是照它反推的）
      int  = 照建议**整数投法**（`alloc.plan` —— 玩家真能一点一点敲出来的那一份）
      none = **一点不投**（建号那 8 点没动 —— 装上加点指令之前玩家的真实战力）
    """
    import rebuild_monsters as RBM
    from content import alloc as AL
    from content import panel_build as PB
    al = {"flat": lambda: RBM.alloc_of(level, cls_id),
          "int": lambda: AL.plan(level, cls_id),
          "none": lambda: {}}[mode]()
    p = {"cls": cls_id, "level": level, "uid": "u_%s_%d" % (cls_id, level), "name": PB.classes()[cls_id]["name"],
         "alloc": al, "bag": {}, "gold": 0}
    if gear:
        p["equipped"] = dict(gear)
    p["hp"] = PB.hp_cap(p)
    return p


def _best_gear(level):
    """该等级的「能捡到的最好那一套」（每槽取词条总和最大的稀有件）—— 给可打性那条路用。

    真源 = items 域（`04_装备与道具`）。只按**词条数值之和**挑，不引入新口径。
    """
    import io
    d = json.load(io.open(os.path.join(REPO, "content/data/items.json"), encoding="utf-8"))
    best = {}
    for iid, rec in d.items():
        slot = rec.get("slot")
        if not slot:
            continue
        s = sum(float(a.get("v") or 0) for a in (rec.get("affixes") or [])
                if isinstance(a.get("v"), (int, float)) and not isinstance(a.get("v"), bool))
        if slot not in best or s > best[slot][1]:
            best[slot] = (iid, s)
    return {slot: iid for slot, (iid, _s) in best.items()}


def _fight(party, mids, monsters, seed, mode="flat"):
    """打一场：party = [(职业, 等级, 装备)]（1 人 = 单刷）。`mode` 见 `_player`（战力基线口径）。"""
    from content import combat as CB
    from ext_combat import Battle
    ps = []
    for i, (cls_id, level, gear) in enumerate(party):
        a = CB.player_actor(_player(cls_id, level, gear, mode))
        a["uid"] = "p%d" % i
        ps.append(a)
    es = [CB.monster_actor(mid, monsters[mid]) for mid in mids if mid in monsters]
    random.seed(seed)
    b = Battle("monster", sides={"player": ps, "enemy": es})
    logs = []
    b.auto_run(logs)
    n = {}
    for a in ps:
        nm = a.get("name") or a.get("uid")
        n[nm] = sum(1 for x in logs if ("🌀 %s 开始出招" % nm) in x)
    return {"result": b.result, "acts": n, "acts_sum": sum(n.values()),
            "ticks": float(getattr(b, "_now", 0) or 0),
            "hp": [int(x.get("hp", 0)) for x in ps],
            "max_hp": [int(x.get("max_hp", 0) or 0) for x in ps], "logs": len(logs)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=40)
    ap.add_argument("--levels", default="")
    ap.add_argument("--classes", default="cls_knight,cls_berserker,cls_ranger,cls_mage,cls_priest,cls_assassin")
    ap.add_argument("--monsters", default="ms_wild_dog,ms_bitten_lumberjack,ms_sunken_corpse,ms_bone_warden,ms_boss_oath_sentry")
    ap.add_argument("--party", default="", help="多人队 = 逗号分隔的职业（1 个 = 单刷）")
    ap.add_argument("--gear", action="store_true", help="给每人穿上「该等级能捡到的最好那一套」")
    ap.add_argument("--alloc", default="flat", choices=("flat", "int", "none"),
                    help="加点口径（★ P-34 战力基线）：flat=按建议权重平铺（配平基准，默认）· "
                         "int=照建议整数投法（玩家真敲得出来的那一份）· none=一点不投")
    ap.add_argument("--out", default="")
    ap.add_argument("--onlevel", action="store_true",
                    help="1–20 逐级：造一只「同级 杂兵 普通怪」（panel_of(L,'普通','杂兵')），"
                         "用该等级中位职业打 16 场 —— 这就是「每级一场战斗该打几个刻」那张表")
    a = ap.parse_args()

    from saintess_engine.package import load_stack
    st = load_stack(REPO, inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_bal.db"), "clock": 1.0})
    st.install()
    from content.apply import install_engine
    install_engine()
    import rebuild_monsters as RBM
    MON = st.domain("monsters")

    rows = []
    party_classes = [c for c in a.party.split(",") if c] or None
    if a.onlevel:
        # ★「1→20 逐级一场战斗」：同级 杂兵 普通怪（设计 4 次行动）—— 口径真源
        #   `02_数值宪法/03_全流程数值主干_v1.md` §四（普通怪 3–5 次行动）+ `12_…_v1.md` §一
        MON = dict(MON)
        for _L in range(1, 21):
            MON["syn_normal_%d" % _L] = {
                "name": "同级基准怪", "lv": _L, "role": "普通", "role_key": "normal",
                "archetype": "杂兵", "panel": RBM.panel_of(_L, "普通", "杂兵"),
                "mods": {}, "habitat": {}, "skills": [], "drops": [], "elite_pool": []}
        _cls_list = a.classes.split(",")
        print("── 加点口径 --alloc=%s（%s）" % (a.alloc, _MODE_LABEL[a.alloc]), flush=True)
        for _L in range(1, 21):
            _med = sorted(_cls_list, key=lambda c: RBM.per_hit_of(_L, c))[3]     # 六取中位
            seed_rows = []
            for s in range(16):
                try:
                    seed_rows.append(_fight([(_med, _L, None)], ["syn_normal_%d" % _L], MON, 1000 + s, a.alloc))
                except Exception as exc:                                # noqa: BLE001
                    seed_rows.append({"result": "ERR:%s" % exc, "acts": {}, "acts_sum": 0,
                                      "ticks": 0, "hp": [], "max_hp": [], "logs": 0})
            wins = sum(1 for r in seed_rows if r["result"] == "victory")
            ac = sorted(r["acts_sum"] for r in seed_rows)
            tk = sorted(r["ticks"] for r in seed_rows)
            rows.append({"monster": "syn_normal_%d" % _L, "name": "同级基准怪", "tier": "普通",
                         "arch": "杂兵", "lv": _L, "hp": MON["syn_normal_%d" % _L]["panel"]["hp"],
                         "design": 4.0, "who": _med, "plv": _L, "n": 16, "win": wins,
                         "alloc": a.alloc,
                         "outcomes": {"victory": wins, "defeat": 16 - wins},
                         "acts_med": ac[8], "acts_min": ac[0], "acts_max": ac[-1],
                         "ticks_med": round(tk[8], 1)})
            r = rows[-1]
            print("lv%-3d 同级基准怪 hp=%-6d（设计 4 次行动 / 3–5 次）｜中位职业 %-14s 胜 %2d/16 出手 med=%-3d [%d..%d] 刻 med=%.0f"
                  % (_L, r["hp"], _med, wins, r["acts_med"], r["acts_min"], r["acts_max"], r["ticks_med"]),
                  flush=True)
        if a.out:
            with open(a.out, "w", encoding="utf-8", newline="\n") as f:
                json.dump(rows, f, ensure_ascii=False, indent=1)
            print("→", a.out)
        return
    for mid in a.monsters.split(","):
        if mid not in MON:
            continue
        m = MON[mid]
        lv = int(m.get("lv", 1) or 1)
        tier = m.get("role"); arch = m.get("archetype")
        design = RBM.TIERS[tier]["hp_n"] * RBM.ARCH[arch]["hp"]
        hp = m["panel"]["hp"]
        combos = []
        if party_classes:
            combos.append(("+".join(party_classes), party_classes))
        else:
            combos = [(c, [c]) for c in a.classes.split(",")]
        for label, members in combos:
            for plv in ([int(x) for x in a.levels.split(",")] if a.levels else [lv]):
                party = [(c, plv, None) for c in members]
                seed_rows = []
                for s in range(a.seeds):
                    try:
                        g = _best_gear(plv) if a.gear else None
                        if g:
                            party = [(c, plv, g) for c in members]
                        seed_rows.append(_fight(party, [mid], MON, 1000 + s, a.alloc))
                    except Exception as exc:                       # noqa: BLE001
                        seed_rows.append({"result": "ERR:%s" % exc, "acts": {}, "acts_sum": 0,
                                          "ticks": 0, "hp": [], "max_hp": [], "logs": 0})
                wins = sum(1 for r in seed_rows if r["result"] == "victory")
                outs = {}
                for r in seed_rows:
                    k = str(r["result"]).split(":")[0]
                    outs[k] = outs.get(k, 0) + 1
                ac = sorted(r["acts_sum"] for r in seed_rows)
                tk = sorted(r["ticks"] for r in seed_rows)
                rows.append({"monster": mid, "name": m["name"], "tier": tier, "arch": arch,
                             "lv": lv, "hp": hp, "design": design, "who": label, "plv": plv,
                             "n": a.seeds, "win": wins, "alloc": a.alloc, "outcomes": outs,
                             "acts_med": ac[len(ac) // 2], "acts_min": ac[0], "acts_max": ac[-1],
                             "ticks_med": round(tk[len(tk) // 2], 1)})
                r = rows[-1]
                print("%-16s %-4s %-4s lv=%-3d hp=%-7d 设计%5.1f 次 | %-22s lv=%-3d 胜 %3d/%-3d %-22s 出手 med=%-4d [%d..%d] 刻 med=%.0f"
                      % (m["name"], tier, arch, lv, hp, design, label, plv, wins, a.seeds,
                         str(outs), r["acts_med"], r["acts_min"], r["acts_max"], r["ticks_med"]),
                      flush=True)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        print("→", a.out)


if __name__ == "__main__":
    main()
