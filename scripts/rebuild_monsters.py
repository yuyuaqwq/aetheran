# -*- coding: utf-8 -*-
"""重算 monsters.json 的 panel（按「档位 × 原型」偏移）—— 数值可复算，不手打。

★ 数值凑整口径（2026-09-25）：hp · atk · def · res · hit · eva · crit · spd 全部取整。
★ 本模块只提供算法（panel_of）；写文件走 main —— **import 不改任何数据**。
  用法：python scripts/rebuild_monsters.py
"""
import io
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLS = json.loads(io.open(os.path.join(REPO, "content/data/classes.json"), encoding="utf-8").read())

TIERS = {"普通": dict(hp_n=4.0, spd=92, res=0.50), "精英": dict(hp_n=12.0, spd=104, res=0.55),
         "头目": dict(hp_n=14.0, spd=98, res=0.60), "层主": dict(hp_n=18.0, spd=96, res=0.60),
         "boss": dict(hp_n=72.0, spd=102, res=1.00)}
ARCH = {
    "杂兵": dict(hp=1.00, atk=1.00, dfn=1.00, res=1.00, spd=1.00),
    "快速": dict(hp=0.70, atk=1.10, dfn=0.80, res=0.90, spd=1.30),
    "厚甲": dict(hp=1.40, atk=0.85, dfn=1.60, res=1.20, spd=0.85),
    "法系": dict(hp=0.80, atk=0.95, dfn=0.70, res=1.60, spd=1.00),
    "群居": dict(hp=0.45, atk=0.75, dfn=0.90, res=0.90, spd=1.10),
    "消耗": dict(hp=1.00, atk=0.90, dfn=1.00, res=1.00, spd=1.00),
    "爆发": dict(hp=0.70, atk=1.50, dfn=0.80, res=0.90, spd=0.90),
    "支援": dict(hp=1.00, atk=0.80, dfn=1.00, res=1.10, spd=1.00)}
MOS = [("田鼠", "普通", 3, "群居"), ("拾荒野狗", "普通", 4, "群居"), ("游荡的骸骨", "普通", 6, "厚甲"),
       ("林鸦", "普通", 4, "快速"), ("野狗", "普通", 6, "杂兵"), ("浅滩水鬼", "普通", 8, "消耗"),
       ("石滩螃蟹", "普通", 9, "厚甲"), ("拾荒人", "精英", 7, "爆发"), ("被咬过的伐木工", "精英", 9, "消耗"),
       ("白桦树精", "精英", 11, "法系"), ("摆渡人", "精英", 12, "支援"), ("水里的东西", "精英", 13, "爆发"),
       ("旧哨塔的守兵", "头目", 14, "厚甲"), ("头狗", "头目", 10, "快速"), ("沉尸", "头目", 15, "厚甲"),
       ("守塔的骨架", "层主", 17, "法系"), ("旧誓哨兵", "boss", 19, "厚甲")]


def player_panel(level, cid):
    c = CLS[cid]
    p = dict(c["base"])
    for k, v in c["growth"].items():
        p[k] = p.get(k, 0) + v * (level - 1)
    total = 8 + 3 * (level - 1)
    sug = c["suggest_alloc"]; base = sum(sug.values())
    for stat, w in sug.items():
        n = total * w / base
        for k, v in (c["conv"].get(stat) or {}).items():
            p[k] = p.get(k, 0) + v * n
    return p


def avg_panel(level):
    ps = [player_panel(level, c) for c in CLS]
    return {k: sum(p.get(k, 0) for p in ps) / len(ps)
            for k in ("hp", "atk", "matk", "def", "res", "hit", "eva", "crit")}


def panel_of(level, tier, arch):
    """★ 唯一真源：怪面板 = 同级玩家平均 × 档位 × 原型。全字段取整。"""
    a = avg_panel(level); t = TIERS[tier]; k = ARCH[arch]
    dr = a["def"] / (a["def"] + (100.0 + 20.0 * level))
    crit_mult = 1.0 + (a["crit"] / (a["crit"] + 300 + 30 * level)) * 0.5
    per_hit = max(a["atk"], a["matk"]) * crit_mult * 0.95
    return {
        "hp": round(per_hit * t["hp_n"] * k["hp"]),
        "atk": round(a["hp"] / (18.0 * (1 - dr)) * k["atk"]),
        "def": round(a["def"] * t["res"] * k["dfn"]),
        "res": round(a.get("res", a["def"]) * t["res"] * k["dfn"]),
        "spd": int(t["spd"] * k["spd"]),
        "hit": round(a["hit"] * t["res"] * k["res"]),
        "eva": round(a["eva"] * t["res"] * k["res"]),
        "crit": round(a["crit"] * t["res"] * k["res"])}


def main():
    p = os.path.join(REPO, "content/data/monsters.json")
    mos = json.load(io.open(p, encoding="utf-8"))
    by_name = {v["name"]: k for k, v in mos.items()}
    fixed = 0
    for name, tier, lv, arch in MOS:
        key = by_name.get(name)
        if not key:
            print("  ! 找不到：%s" % name); continue
        mos[key]["panel"] = panel_of(lv, tier, arch)
        mos[key]["archetype"] = arch
        mos[key]["role"] = tier
        mos[key]["lv"] = lv
        fixed += 1
    io.open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(mos, ensure_ascii=False, indent=2) + "\n")
    print("重算 %d 只怪的 panel（取整口径）" % fixed)
    for k in ("ms_field_mouse", "ms_bone_wanderer", "ms_stone_crab", "ms_boss_oath_sentry"):
        v = mos[k]; pp = v["panel"]
        print("  %-22s %-4s lv%-3s hp=%-6s atk=%-4s def=%-4s spd=%-4s" % (
            k, v["archetype"], v["lv"], pp["hp"], pp["atk"], pp["def"], pp["spd"]))


if __name__ == "__main__":
    main()
