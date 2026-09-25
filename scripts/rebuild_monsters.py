# -*- coding: utf-8 -*-
"""重算 monsters.json 的 panel（**档位反解** · 2026-09-25 B3-18 重做）—— 数值可复算，不手打。

★ 判据（本文件存在的理由）：**「阿斯特兰不改一行能用」** 的数值侧版本 ——
  同一套档位/原型表在 1 级与 100 级都成立（反解式挂在玩家面板上，玩家涨它自动涨）。

## 两层结构（唯一真源 = `content/rules/monster_tiers.json`）

```text
档位（多强）  普通 · 精英 · 头目 · 层主 · boss —— 四项 hp/atk/def/spd **都走档位**
原型（哪种强）杂兵 · 快速 · 厚甲 · 法系 · 群居 · 消耗 · 爆发 · 支援 —— 只作**偏移**
```

## 反解（不是拍数，是把引擎真的那一条伤害链倒过来解）

```text
玩家单次行动伤害（打某只怪）  = basis_p × (1 + 暴击率×0.5) × (1 − 怪闪避率) × K/(怪def + K)
怪单次行动伤害（打标准玩家）= 怪atk × (1 + 怪暴击率×0.5) × (1 − 玩家闪避率) × K/(玩家def + K)
   其中 K = `content/rules/formula_table.json` 的 `$const.K_def`（**同一份**，不写第二次）
        ← 引擎侧真读的就是这条声明链（`damage_full`，见 `ext_combat.calc_damage` 的绑定分支）

⇒ 档位给一对 TTK 目标（n_me = 玩家要打几下 / n_them = 它要打玩家几下），
  把上面两式分别对 **hp** 与 **atk** 解出来；def / spd 由档位阶梯直接给。
⇒ 原型偏移加在**同一档的基准**上；偏移幅度 σ 由「档间距 > 原型全幅」反解（`sigma_of`），
  保序压幅 —— 排序即 `14_怪物原型_v1.md` §二 的形状，幅度按「不越档」这条硬判据定。
```

★ 数值凑整口径（2026-09-25）：hp · atk · def · res · hit · eva · crit · spd 全部取整。
★ 本模块只提供算法（panel_of）；写文件走 main —— **import 不改任何数据**。
  用法：python scripts/rebuild_monsters.py          （重写 content/data/monsters.json）
        python scripts/rebuild_monsters.py --table  （只打印表，不写）
"""
import io
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLS = json.loads(io.open(os.path.join(REPO, "content/data/classes.json"), encoding="utf-8").read())

#: 唯一真源：档位表 + 原型偏移表（一个文件两段，别再在代码里抄第二份）
_RULES = os.path.join(REPO, "content", "rules")
_TIERS_JSON = json.loads(io.open(os.path.join(_RULES, "monster_tiers.json"), encoding="utf-8").read())
TIERS = _TIERS_JSON["tiers"]
ARCH = _TIERS_JSON["arch"]
SAFETY = float(_TIERS_JSON.get("safety", 0.9))

#: ★ 数值→率 / 减伤刻度：**从公式表读**（`$const`）—— 反解与被反解的那条链共用一份常数，
#:   绝不在这里写 300/500 两个数（写第二份 = 两把尺，probe_monsters ⑪⑫ 钉着这一条）。
_CONST = json.loads(io.open(os.path.join(_RULES, "formula_table.json"), encoding="utf-8").read())["$const"]
K_DEF = int(_CONST["K_def"])
K_RATE = int(_CONST["K_rate"])
DODGE_CAP = 0.40                    # 引擎承伤侧闪避上限（`landing._roll_dodge`）
CRIT_EXP = 0.5                      # crit_exp = 1 + 暴击率 × 0.5（暴伤基准 1.5）

#: ★ B3-6b-2d-keys-2：档位（中文）→ ASCII **机器键** `role_key`（P-20 甲案第二刀）。
#:   为什么：代码原先拿中文枚举当机器键（战斗里挑遇敌 / 掉钱分档 / 是不是 BOSS）—— K48 / K51。
#:   取值口径：普通=normal · 精英=elite · 头目=chief（区域头目）· 层主=warden（副本层主）· boss（世界 Boss）。
#:   ★ `boss` 与引擎那份 ASCII 词表同值（`ext_combat` 比的是 `role == "boss"`）—— 头目 / 层主
#:     **不是** `boss`（它们今天不算 BOSS：`is_boss` 只对 `ms_boss_oath_sentry` 为真，换键后逐字相同）。
#:   本表是它的唯一来源：`probe_monsters` ⑧ 对着它 + schema enum + 域里 17 条三头对账。
ROLE_KEY = {"普通": "normal", "精英": "elite", "头目": "chief", "层主": "warden", "boss": "boss"}
MOS = [("田鼠", "普通", 3, "群居"), ("拾荒野狗", "普通", 4, "群居"), ("游荡的骸骨", "普通", 6, "厚甲"),
       ("林鸦", "普通", 4, "快速"), ("野狗", "普通", 6, "杂兵"), ("浅滩水鬼", "普通", 8, "消耗"),
       ("石滩螃蟹", "普通", 9, "厚甲"), ("拾荒人", "精英", 7, "爆发"), ("被咬过的伐木工", "精英", 9, "消耗"),
       ("白桦树精", "精英", 11, "法系"), ("摆渡人", "精英", 12, "支援"), ("水里的东西", "精英", 13, "爆发"),
       ("旧哨塔的守兵", "头目", 14, "厚甲"), ("头狗", "头目", 10, "快速"), ("沉尸", "头目", 15, "厚甲"),
       ("守塔的骨架", "层主", 17, "法系"), ("旧誓哨兵", "boss", 19, "厚甲")]

TIER_ORDER = ["普通", "精英", "头目", "层主", "boss"]
_PANEL_STATS = ("hp", "atk", "matk", "def", "res", "hit", "eva", "crit", "spd")
#: 体检锚点：全流程 1–100 级六格（真源 `02_数值宪法/03_全流程数值主干_v1.md` §三 同一组）
ANCHORS = (1, 20, 40, 60, 80, 100)


# ══════════════════════════════════════════════════════════════
# 玩家侧的标准（同级六职业**中位**面板）
# ══════════════════════════════════════════════════════════════

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


def _median(vals):
    return sorted(vals)[len(vals) // 2]                  # 六取第 4 个（与 probe_combat ③ 同一口径）


def std_panel(level):
    """同级**标准面板** = 六职业中位（宪法 §二·六「标准怪 = 同级中位」同一口径）。

    ★ 逐项取中位（不是「先挑一个中位职业再读它」）：标准怪是**参照系**，不是某个真角色。
    """
    ps = [player_panel(level, c) for c in CLS]
    return {k: _median([p.get(k, 0) for p in ps]) for k in _PANEL_STATS}


def per_hit_of(level, cid):
    """★ 某个职业在该等级的**单次行动伤害**（不看敌方防御 —— 纯粹是职业自己的输出尺）。

    通道取该职业自己的那一根（`rebuild_skills.CHANNEL` 那张表：物理职业吃 atk、法系吃 matk）。
    """
    p = player_panel(level, cid)
    ch = CLS[cid]["dmg_channel"]
    basis = p["atk"] if ch == "phys" else p["matk"]
    return basis * (1.0 + rate_of(p["crit"]) * CRIT_EXP)


def std_ref(level):
    """反解用的**参照角色** = 六职业里 per_hit 中位那一个（与配平实验挑的是同一个）。

    返回 `dict(basis, channel, crit_rate, crit, hit, hp, def, eva, spd, res)` ——
    设计尺与测量尺同一把。
    """
    cid = sorted(CLS, key=lambda c: per_hit_of(level, c))[len(CLS) // 2]
    p = player_panel(level, cid)
    ch = CLS[cid]["dmg_channel"]
    basis = p["atk"] if ch == "phys" else p["matk"]
    return {"cls": cid, "channel": ch, "basis": basis,
            "crit_rate": rate_of(p["crit"]), "crit": p["crit"], "hit": p["hit"],
            "hp": p["hp"], "def": p["def"], "res": p["res"], "eva": p["eva"], "spd": p["spd"]}


def std_per_hit(level):
    """参照角色的单次行动伤害（**未算敌方防御/闪避**的那一半）。"""
    r = std_ref(level)
    return r["basis"] * (1.0 + r["crit_rate"] * CRIT_EXP)


def rate_of(rating):
    """数值 → 率（宪法 F3 形状 `r/(r+K_rate)`）。**玩家与怪共用这一把尺**。"""
    r = float(rating or 0)
    if r <= 0:
        return 0.0
    return r / (r + K_RATE)


# ══════════════════════════════════════════════════════════════
# 原型偏移幅度 σ —— 「保序压幅」，由档间距反解（不手写）
# ══════════════════════════════════════════════════════════════

def dev(stat, arch):
    """原型的**偏移量**（相对该档基准）：hp/atk/def/spd = (x−1)（加减偏移）。

    ★ 读法：`14_怪物原型_v1.md` §二 那张 x 表**既是形状也是偏移** ——
      「普通档」那一段逐字等于原表（杂兵 1.00 / 群居 0.45 / 厚甲 1.40…），
      高档只是把它当**偏移**加在更大的基准上（⇒ 相对幅度自然收窄，档位始终压得住原型）。
    """
    return float(ARCH[arch][stat]) - 1.0


def _dev_spread(stat):
    vs = [dev(stat, a) for a in ARCH]
    return max(vs) - min(vs)


#: 各 stat 的「单位」= 普通档基准（把阶梯归一成倍率，让「档间距」与「原型全幅」同量纲）。
#: hp 的单位 = 4 次行动 · atk 的单位 = 1.0 倍「普通档的怪 atk」· spd 的单位 = 92。
UNIT = {"hp": 4.0, "atk": 1.0, "def": 1.0, "spd": 92.0}


def ladder(stat, tier):
    """该档该 stat 的**基准倍率**（普通档 = 1.0，spd 是绝对速度）。

    hp  ← n_me / 4        （普通档 4 次行动 = 1.0）
    atk ← 18 / n_them      ★ 反比：它要打玩家越多下才打死 ⇒ 单次 atk 越低（普通档 18 = 1.0）
    def ← def_n            （怪的 def / 同级标准玩家的 def，普通档 1.0）
    spd ← 档位绝对速度
    """
    t = TIERS[tier]
    if stat == "hp":
        return float(t["n_me"]) / UNIT["hp"]
    if stat == "atk":
        return UNIT["atk"] * float(TIERS["普通"]["n_them"]) / float(t["n_them"])
    if stat == "def":
        return float(t["def_n"])
    if stat == "spd":
        return float(t["spd"]) / UNIT["spd"]
    raise KeyError(stat)


def _gap_min(stat):
    """相邻两档的**最小间距**（倍率量纲；spd 也是倍率）。"""
    vals = [ladder(stat, t) for t in TIER_ORDER]
    return min(vals[i + 1] - vals[i] for i in range(len(vals) - 1))


MARGIN_UNIT = 1.0           # 取整量子：分离量必须 > 1.0 才不会被 round() 抹成平手


def baseline(level, tier):
    """该档的**基准怪**（原型=杂兵，偏移 0）—— 反解只解它，原型偏移另加。

    ★ 为什么反解只用基准：若让原型的 def/eva 一起进反解，hp 会「谁硬谁反而血少」
      （补偿掉了），hp 那一栏就不再是一条可比较的阶梯 ⇒ 「跨族同级不越档」当场失效。
      原型对 TTK 的影响**保留在实机里**（厚甲就是更难打），但不许改写面板阶梯。
    """
    r = std_ref(level)
    t = TIERS[tier]
    coef = float(t["res_coef"])
    eva0 = round(r["eva"] * coef)
    crit0 = round(r["crit"] * coef)
    dodge_m = min(rate_of(eva0), DODGE_CAP)
    dodge_p = min(rate_of(r["eva"]), DODGE_CAP)
    crit_r = rate_of(crit0)
    side = K_DEF / (r["def"] + K_DEF)                     # 玩家挨怪一刀的减伤系数（怪技一律物理）
    def0 = r["def"] * float(t["def_n"])
    mit0 = K_DEF / (def0 + K_DEF)                         # 怪挨玩家一刀的减伤系数（基准怪的 def）
    hp0 = float(t["n_me"]) * std_per_hit(level) * (1.0 - dodge_m) * mit0
    atk0 = r["hp"] / (float(t["n_them"]) * (1.0 + crit_r * CRIT_EXP) * (1.0 - dodge_p) * side)
    return {"hp": hp0, "atk": atk0, "def": def0, "spd": UNIT["spd"] * ladder("spd", tier),
            "hit": r["hit"] * coef, "eva": eva0, "crit": crit0, "res": r["res"] * coef}


def _base_min(stat, levels=ANCHORS):
    """该 stat 在全部锚点上**最小的档位基准绝对值**（诊断用：看取整量子占了多大幅度）。"""
    return min(baseline(L, t)[stat] for L in levels for t in TIER_ORDER)


_SIGMA_CACHE = {}


def lstat(stat, tier, arch):
    """该档该原型在**倍率量纲**下的值：`阶梯 × (1 + δ×偏移)`（δ 由 sigma_of 的反解给出）。"""
    return ladder(stat, tier) * (1.0 + delta_of()[stat] * dev(stat, arch))


#: ★ 2026-09-25 鱼鱼拍板（`_notes.md` §三）：四项**分两条判据**——
#:   `def`/`spd` → 跨族全原型空间**严格**不越档（「普通怪比精英怪还硬」那个病的所在）；
#:   `hp`/`atk`  → 只要**基准阶梯**（杂兵）严格不越档，原型**保 14 号原表全幅**（δ=1）
#:                ⇒ 代价：群居精英的血可能低于厚甲普通（群居的原意是「一次来 3–4 只」，
#:                那 3 只加起来还是厚）。这是设计取舍，不是判据放宽的意外。
FULL_BAND_STATS = ("hp", "atk")

_DELTA_CACHE = {}


def delta_of():
    """每项的**原型偏移幅度 δ**（δ=1 ⇔ `14_怪物原型_v1.md` §二 那张表逐字可用）。

    ```text
    def/spd：要不越档：任意原型的高一档 > 任意原型的低一档
            ⇔ 档间距 > 原型全幅          ← 按各锚点真算出来的基准值逐格解出 δ 的上界
              （含取整量子：1 级怪的面板只有个位数，分离量不到 1 点会被 round() 抹成平手）
    hp/atk ：鱼鱼拍板保全幅 ⇒ δ 恒 1.0（跨族倒挂是设计的一部分，见 FULL_BAND_STATS）
    ```
    """
    if _DELTA_CACHE:
        return _DELTA_CACHE
    for st in ("hp", "atk", "def", "spd"):
        if st in FULL_BAND_STATS:
            _DELTA_CACHE[st] = 1.0
            continue
        vs = [dev(st, a) for a in ARCH]
        dmin, dmax = min(vs), max(vs)
        if dmax - dmin <= 0:
            _DELTA_CACHE[st] = 1.0
            continue
        bound = 1.0
        for L in ANCHORS:
            b = [baseline(L, t)[st] for t in TIER_ORDER]
            for i in range(1, len(b)):
                num = (b[i] - b[i - 1]) - MARGIN_UNIT           # 档间距（扣掉取整量子）
                den = dmax * b[i - 1] - dmin * b[i]             # 偏移全幅的绝对量
                if den > 0:
                    bound = min(bound, num / den)
        _DELTA_CACHE[st] = round(max(0.0, min(1.0, SAFETY * bound)), 4)
    return _DELTA_CACHE


# ══════════════════════════════════════════════════════════════
# 反解：档位 × 原型 → panel
# ══════════════════════════════════════════════════════════════

def panel_of(level, tier, arch):
    """★ 唯一真源：怪面板 = **档位基准（反解）× 原型偏移**（用引擎真跑的那条伤害链反解）。

    反解只解「基准怪（杂兵）」，原型再以**乘区**叠上去：

    ```text
    hp  ← n_me  ：玩家要打几下  = hp / (单次行动伤害)
                  单次行动伤害 = per_hit × (1 − 怪闪避率) × K/(怪def + K)
    atk ← n_them：它要打玩家几下 = 玩家标准HP / (单次行动伤害)
                  单次行动伤害 = atk × (1 + 怪暴击率×0.5) × (1 − 玩家闪避率) × K/(玩家def + K)
    def ← def_n ：怪的 def = 玩家标准 def × def_n
    spd ← 档位绝对速度
    四项的**原型偏移** = lstat/ladder − 1（加减偏移的乘区写法，见 sigma_of 的反解）
    ```
    """
    b = baseline(level, tier)
    amul = float(ARCH[arch]["res"])          # 对抗属性是**乘区**（语义本来就是「相对玩家的系数」）

    def _off(stat):
        return lstat(stat, tier, arch) / ladder(stat, tier)

    return {"hp": round(b["hp"] * _off("hp")),
            "atk": round(b["atk"] * _off("atk")),
            "def": round(b["def"] * _off("def")),
            "res": round(b["res"] * amul),
            "spd": int(round(UNIT["spd"] * lstat("spd", tier, arch))),
            "hit": round(b["hit"] * amul),
            "eva": round(b["eva"] * amul),
            "crit": round(b["crit"] * amul)}


def design_ttk(tier, arch):
    """该怪自己的**设计击杀 / 设计被击杀行动数**（档位 TTK 目标 + 原型偏移）—— 验收口径的唯一出口。

    `probe_combat` ③（实测出手次数 vs 设计值）与 `balance_experiment` 的设计列都调它，
    不许在别处重算（重算 = 第二把尺）。
    """
    return (UNIT["hp"] * lstat("hp", tier, arch),
            float(TIERS["普通"]["n_them"]) / lstat("atk", tier, arch))


# ══════════════════════════════════════════════════════════════
# 自检 + 落盘
# ══════════════════════════════════════════════════════════════

ANCHORS = (1, 20, 40, 60, 80, 100)


def check_monotone(levels=ANCHORS, verbose=True):
    """自检（★ 2026-09-25 鱼鱼拍板的分工 · `_notes.md` §三）：

    ```text
    def / spd：**全原型空间**严格不越档 —— 任意原型的高一档 > 任意原型的低一档
               （「普通怪比精英怪还硬」那个病的所在，不许再犯）
    hp  / atk：只要**基准阶梯**（杂兵）严格不越档 —— 原型保 14 号原表全幅（δ=1），
               跨族倒挂是设计的一部分（群居血薄，它一次来 3–4 只）
    ```
    """
    bad = []
    for st in ("def", "spd"):                       # 全原型空间
        for L in levels:
            vals = {t: [panel_of(L, t, a)[st] for a in ARCH] for t in TIER_ORDER}
            for i in range(1, len(TIER_ORDER)):
                lo, hi = TIER_ORDER[i - 1], TIER_ORDER[i]
                if min(vals[hi]) <= max(vals[lo]):
                    bad.append("[跨族] %s L%d %s(%d) 没压住 %s(%d)"
                               % (st, L, hi, min(vals[hi]), lo, max(vals[lo])))
    for st in ("hp", "atk"):                        # 只看基准（杂兵）
        for L in levels:
            vals = [baseline(L, t)[st] for t in TIER_ORDER]
            for i in range(1, len(vals)):
                if vals[i] <= vals[i - 1]:
                    bad.append("[基准] %s L%d %s(%d) 没压住 %s(%d)"
                               % (st, L, TIER_ORDER[i], vals[i], TIER_ORDER[i - 1], vals[i - 1]))
    if verbose:
        print("  「档位单调」def/spd 跨族全原型空间 + hp/atk 基准阶梯（8 原型 × 5 档 × %d 个锚点）：%s"
              % (len(levels), "全绿 ✓" if not bad else "红 %d 条 ✗" % len(bad)))
        for b in bad[:6]:
            print("     -", b)
    return bad


def print_table(monsters=None):
    """打印 17 只怪的完整面板表（供真源 `12_怪物面板与精英词条池_v1.md` §一 逐字覆盖）。

    形如真源那张表：| 名字 | 档 | 原型 | 等级 | hp | atk | def | spd | hit | eva | crit |
    ★ 文档里那张表**只能**由本函数 stdout 覆盖（口径 G3：数值表不手抄）。
    """
    print("| 名字 | 档 | 原型 | 等级 | hp | atk | def | spd | hit | eva | crit | 设计击杀 | 设计被击杀 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for name, tier, lv, arch in MOS:
        p = panel_of(lv, tier, arch)
        n_me, n_them = design_ttk(tier, arch)
        print("| %s | %s | %s | %d | %d | %d | %d | %d | %d | %d | %d | %.1f | %.1f |"
              % (name, tier, arch, lv, p["hp"], p["atk"], p["def"], p["spd"],
                 p["hit"], p["eva"], p["crit"], n_me, n_them))


def print_ladders():
    """打印档位阶梯 + 原型幅度 δ（供真源 §一 的「输入表」逐字覆盖）。"""
    print("| 档 | 设计击杀 n_me | 设计被击杀 n_them | def_n | spd | 对抗系数 |")
    print("|---|---|---|---|---|---|")
    for t in TIER_ORDER:
        d = TIERS[t]
        print("| %s | %.0f | %.0f | %.2f | %d | %.2f |"
              % (t, d["n_me"], d["n_them"], d["def_n"], d["spd"], d["res_coef"]))
    dl = delta_of()
    print()
    print("原型偏移幅度 δ（保序压幅 · 由「档间距 > 原型全幅」逐格解出 · safety=%.2f · 取整量子=%.1f）："
          % (SAFETY, MARGIN_UNIT))
    for st in ("hp", "atk", "def", "spd"):
        print("  %-4s δ=%.3f  档最小间距=%.4f  原型全幅=%.3f ⇒ 生效幅度=%.3f"
              % (st, dl[st], _gap_min(st), _dev_spread(st), dl[st] * _dev_spread(st)))


def main(argv=None):
    argv = list(argv if argv is not None else [])
    print("档位反解（真源 content/rules/monster_tiers.json · K_def=%d / K_rate=%d 来自公式表 $const）"
          % (K_DEF, K_RATE))
    print_ladders()
    print()
    print("17 只怪的面板（生成器 stdout · 文档那张表照此逐字覆盖）：")
    print_table()
    print()
    check_monotone()
    if "--table" in argv:
        return
    p = os.path.join(REPO, "content/data/monsters.json")
    mos = json.load(io.open(p, encoding="utf-8"))
    by_name = {v["name"]: k for k, v in mos.items()}
    fixed = 0
    for name, tier, lv, arch in MOS:
        key = by_name.get(name)
        if not key:
            print("  ! 找不到：%s" % name)
            continue
        mos[key]["panel"] = panel_of(lv, tier, arch)
        mos[key]["archetype"] = arch
        # ★ B3-6b-2d-keys-2：`role`（中文档位名）与 `role_key`（ASCII 机器键）成对写。
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
        mos[key] = rec
        fixed += 1
    io.open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(mos, ensure_ascii=False, indent=2) + "\n")
    print("重算 %d 只怪的 panel（档位反解 · 取整）· 补 role_key（%s）"
          % (fixed, " / ".join("%s→%s" % kv for kv in ROLE_KEY.items())))


if __name__ == "__main__":
    import sys
    main(sys.argv[1:])
