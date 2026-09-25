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

#: ★ B3-14：普攻口径**必须与战斗侧同一把尺**——`content/panel_build.py` 的 `K_RATE`
#:   （crit/eva 数值→率）与暴击期望系数。漂了就自己跟自己对不上（本文件只读 JSON，
#:   所以这份是副本；`probe_monsters` ⑪ 钉着「两者相等」）。
K_RATE = 500
CRIT_EXP = 0.5          # crit_exp = 1 + 暴击率 × 0.5（暴伤基准 1.5）
HIT_RATE = 0.95         # 命中率占位（怪物侧未定；与旧口径同一个值，保持连续）
#: ★ B3-17：Boss 的**单人档**（「单人也能过」那条口径 —— 落在数据里，不靠代码记住）。
#:
#:   真源四处（都点名了同一件事，只有一处给了数）：
#:     · `06_第一阶段垂直切片/12_怪物面板与精英词条池_v1.md` §一④
#:       「Boss …按 **4 人队 × 18 次行动**设计 —— 单人打会很吃力（有意的，它是团队内容）；
#:        **单人挑战时按 ÷2 看（≈3670）**，一场约 30 次行动」
#:     · `06_第一阶段垂直切片/17_组队与策略配合_v1.md` §五「单人　**能过（Boss 血按 ÷2 看）**」
#:     · `06_第一阶段垂直切片/22_旧哨塔_逐间设计_v1.md` §三④「**组队时按人数缩放**（P1 单人也能过）」
#:     · 台账 P-36（设计原话「单人打 Boss 伤害 ÷2」）
#:
#:   ⇒ 形状 = 「队伍人数 → 面板倍数」，**只放文档给了数的那一格**：1 人 = hp ×0.5。
#:     2 / 3 人**没有数**（不猜）⇒ 表里不写；查不到的人数一律走设计值（= 4 人档）。
#:     fail-closed 那一半在 `content/combat.party_scale_of`（键不是数字当场抛）。
#:   ★ 只收 `hp` 这一项：四处真源里两处字面写的是「**血**按 ÷2 看」（12_ §一④ / 17_ §五）——
#:     伤害 / 防御 / 速度那几项**文档没说**，一律不动（见 `_notes.md` §四·1 的实测：
#:     只缩血仍 0/48，「单人能过」这条意图要靠什么达成属**待拍板**）。
PARTY_SCALE = {"1": {"hp": 0.5}}
PARTY_SCALE_ON = ("ms_boss_oath_sentry",)   # ★ 哪几只算「团队内容」（真源只点了 Boss 这一只）
#: ★ B3-6b-2d-keys-2：档位（中文）→ ASCII **机器键** `role_key`（P-20 甲案第二刀）。
#:   为什么：代码原先拿中文枚举当机器键（战斗里挑遇敌 / 掉钱分档 / 是不是 BOSS）—— K48 / K51。
#:   取值口径：普通=normal · 精英=elite · 头目=chief（区域头目）· 层主=warden（副本层主）· boss（世界 Boss）。
#:   ★ `boss` 与引擎那份 ASCII 词表同值（`ext_combat` 比的是 `role == "boss"`）—— 头目 / 层主
#:     **不是** `boss`（它们今天不算 BOSS：`is_boss` 只对 `ms_boss_oath_sentry` 为真，换键后逐字相同）。
#:   本表是它的唯一来源：`probe_monsters` ⑧ 对着它 + schema enum + 域里 17 条三头对账。
ROLE_KEY = {"普通": "normal", "精英": "elite", "头目": "chief", "层主": "warden", "boss": "boss"}
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


def alloc_of(level, cid):
    """该等级该职业的**示例加点**（口径 = 六职业详案「8 + 3×(级−1) 点，按建议权重平铺」）。

    单一出口：`player_panel`（本文件）与 `scripts/balance_experiment.py`（配平实验）都走它 ——
    两处各算一份加点 = 两把尺，实验就复算不出生成器那张表。
    """
    c = CLS[cid]
    sug = c["suggest_alloc"]
    base = sum(sug.values())
    total = 8 + 3 * (level - 1)
    return {stat: total * w / base for stat, w in sug.items()}


def player_panel(level, cid):
    c = CLS[cid]
    p = dict(c["base"])
    for k, v in c["growth"].items():
        p[k] = p.get(k, 0) + v * (level - 1)
    for stat, n in alloc_of(level, cid).items():
        for k, v in (c["conv"].get(stat) or {}).items():
            p[k] = p.get(k, 0) + v * n
    return p


def avg_panel(level):
    ps = [player_panel(level, c) for c in CLS]
    return {k: sum(p.get(k, 0) for p in ps) / len(ps)
            for k in ("hp", "atk", "matk", "def", "res", "hit", "eva", "crit")}


def per_hit_of(level, cid):
    """★ 某个职业在该等级的**单次行动伤害**（不看敌方防御 —— 与旧口径同一形状）。

    通道取该职业自己的那一根（`rebuild_skills.CHANNEL` 那张表：物理职业吃 atk、
    法系吃 matk）。旧口径取的是「六职业**平均**后的 `max(avg_atk, avg_matk)`」——
    把**非通道**的那一根也平均进来了（骑士的 5 点 matk、法师的 8 点 atk 都算进了 atk 均值），
    ⇒ 反推出来的怪 hp 系统性偏低，实测击杀行动数只有目标值的 ~2/3（B3-14 实测）。
    """
    p = player_panel(level, cid)
    ch = CLS[cid]["dmg_channel"]
    basis = p["atk"] if ch == "phys" else p["matk"]
    crit_rate = p["crit"] / (p["crit"] + K_RATE)
    return basis * (1.0 + crit_rate * CRIT_EXP) * HIT_RATE


def standard_per_hit(level):
    """该等级的**标准单次行动伤害** = 六职业**中位**（宪法 §二·六「标准怪 = 同级中位」同一口径）。"""
    vals = sorted(per_hit_of(level, c) for c in CLS)
    return vals[len(vals) // 2]


def panel_of(level, tier, arch):
    """★ 唯一真源：怪面板 = 标准单次行动伤害 × 档位 × 原型。全字段取整。

    `hp` = 标准单次行动伤害 × `hp_n`（普通 4 / 精英 12 / 头目 14 / 层主 18 / Boss 72）
      —— 真源 `12_怪物面板与精英词条池_v1.md` §一 的反推式，与
      `02_数值宪法/03_全流程数值主干_v1.md` §四「一场战斗行动次数」同源。
    """
    a = avg_panel(level); t = TIERS[tier]; k = ARCH[arch]
    dr = a["def"] / (a["def"] + (100.0 + 20.0 * level))
    per_hit = standard_per_hit(level)
    return {
        "hp": round(per_hit * t["hp_n"] * k["hp"]),
        "atk": round(a["hp"] / (18.0 * (1 - dr)) * k["atk"]),
        "def": round(a["def"] * t["res"] * k["dfn"]),
        "res": round(a.get("res", a["def"]) * t["res"] * k["dfn"]),
        "spd": int(t["spd"] * k["spd"]),
        "hit": round(a["hit"] * t["res"] * k["res"]),
        "eva": round(a["eva"] * t["res"] * k["res"]),
        "crit": round(a["crit"] * t["res"] * k["res"])}


# ══════════════════════════════════════════════════════════════════════════════
# ★ B3-17：**上一版口径**（B3-14 那次修正之前那一版）—— 只为对账，**不参与生成**。
#
#   为什么要留着它：真源 `06_第一阶段垂直切片/12_怪物面板与精英词条池_v1.md` §一 那张表
#   是**那一版口径的快照**（B3-17 逐只复算：17/17 行 hp 与它逐字相符）。探针要能现算
#   「doc 那一列 == 旧口径复算」才证明那列**不是手打偏的**，而是一次**口径变更**留下的
#   快照（探针 `probe_monsters ⑫`）。写法照 B3-14 前那一版逐字（`bbdc15f` 的 panel_of）：
#     · 通道是 `max(六职业**平均** atk, 六职业**平均** matk)` —— 把非通道那根也平均进来了；
#     · crit 率的分母是**等级尺** `300 + 30L`（不是战斗侧那把 K_RATE=500）。
#   ★ 它跟 `panel_of` 只差这两处 —— 差出来的就是 B3-14 修的那条（实测击杀行动数只有设计值的 ~2/3）。
def per_hit_v1(level):
    a = avg_panel(level)
    crit_mult = 1.0 + (a["crit"] / (a["crit"] + 300 + 30 * level)) * 0.5
    return max(a["atk"], a["matk"]) * crit_mult * 0.95


def panel_of_v1(level, tier, arch):
    """B3-14 之前那一版的面板算法（对账用；真源 `12_…` §一 表就是它的快照）。"""
    a = avg_panel(level); t = TIERS[tier]; k = ARCH[arch]
    dr = a["def"] / (a["def"] + (100.0 + 20.0 * level))
    per_hit = per_hit_v1(level)
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
        # ★ B3-6b-2d-keys-2：`role`（中文档位名 · 策划案原话）与 `role_key`（ASCII 机器键）成对写，
        #   机器键紧挨 `role`（读数据的人一眼看见两格）。tier 不在表里 ⇒ KeyError 当场炸（不猜）。
        role_key = ROLE_KEY[tier]
        rec = {}
        for k, v in mos[key].items():
            if k == "role_key":                       # 老数据里已有一格：下面统一写，别写两遍
                continue
            if k == "role":
                rec["role"] = tier
                rec["role_key"] = role_key
                continue
            rec[k] = v
        if "role" not in rec:                         # 记录里压根没有 role（不该发生）⇒ 补一对
            rec["role"], rec["role_key"] = tier, role_key
        rec["lv"] = lv
        # ★ B3-17：单人档那一格（只有团队内容那几只有）—— 照 PARTY_SCALE 重写，
        #   不在表里的怪**显式抹掉**这一格（换表之后不留旧值）。
        mods = dict(rec.get("mods") or {})
        if key in PARTY_SCALE_ON:
            mods["party_scale"] = {n: dict(v) for n, v in PARTY_SCALE.items()}
        else:
            mods.pop("party_scale", None)
        rec["mods"] = mods
        mos[key] = rec
        fixed += 1
    io.open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(mos, ensure_ascii=False, indent=2) + "\n")
    print("重算 %d 只怪的 panel（取整口径）· 补 role_key（%s）"
          % (fixed, " / ".join("%s→%s" % kv for kv in ROLE_KEY.items())))
    print("单人档（%s）：%s"
          % ("+".join(PARTY_SCALE_ON),
             " · ".join("%s 人 → %s" % (n, "+".join("%s×%s" % kv for kv in sorted(v.items())))
                        for n, v in sorted(PARTY_SCALE.items()))))
    for k in ("ms_field_mouse", "ms_bone_wanderer", "ms_stone_crab", "ms_boss_oath_sentry"):
        v = mos[k]; pp = v["panel"]
        print("  %-22s %-4s lv%-3s hp=%-6s atk=%-4s def=%-4s spd=%-4s" % (
            k, v["archetype"], v["lv"], pp["hp"], pp["atk"], pp["def"], pp["spd"]))


if __name__ == "__main__":
    main()
