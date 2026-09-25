# -*- coding: utf-8 -*-
"""重算 skills 域的「引擎通道」与「倍率公式」—— 数值可复算，不手打。

★ 为什么要这份生成器（B3-14 查出的真问题）
--------------------------------------------------------------
skills 域 30 条技能原先只有 `power`（倍率基数），**没有 `exprs` / `formula`**。
而引擎的取件口 `ext_combat/battle/actions.py:resolve_basic_skill` 要求
`bs.get("exprs") or bs.get("formula")` 才算一条合法普攻 ⇒ 六职业的普攻**一律被拒**，
全员退化成兜底「挥击」；更要命的是非 expr 分支按 `kind` 推伤害类型，而本包没挂
`kinds` 词表（`kind_of("phys") == ""`）⇒ **所有攻击判成魔法**（吃 matk 不吃 atk）。
结果：骑士 atk 51.6 白给、法师 matk 84 一发放倒田鼠 —— 六职业的伤害全由 matk 决定。

★ 本文件落两样东西（都从设计真源推，不手打）
--------------------------------------------------------------
① `kind_override` —— 这条技能走哪条**引擎通道**（`content/rules/kinds.json` 的 5 个值）：
     物理 / 魔法 / 真伤 / 治疗 / 增益
   口径表 `CHANNEL`（职业 → 通道）的真源 = 六份职业详案的**伤害列**：
     骑士 / 狂战士 / 游侠 / 刺客  的伤害表用的是 **atk**（01_骑士_v2 §七「10 级 atk 62.2 × 2.2」
        · 03_游侠_v2 §五「83.6 × 2.6」· 06_刺客_v2 §五「82.0 × 1.2」）⇒ `phys`
     法师 / 修女  的伤害/治疗表用的是 **matk**（04_法师_v2 §五「matk 116.8 × (1+0.35×4)」·
       05_修女_v2 §六「安神曲治疗量 F8」）⇒ `magi`
   —— 元素字段（ELE_FIRE …）**不是**通道：狂战士「焚身」是火元素的自伤重击，打的仍是 atk。
   `mech == "hot"` 的那条（安神曲）是**治疗**，不是攻击（设计：它的 1.5 是治疗倍率）。
   `power <= 0` 的那几条（盾墙 / 挑战咆哮 / 不退 / 抢拍 / 后撤 / 净罪 / 庇护 / 晨祷）
   是**非伤害类主动技** ⇒ 走引擎的「增益」支（唯一不产生伤害的落点；
   它们真正的机制要等机制层那一批接线，届时也仍是「不产生伤害」）。

② `exprs` —— 倍率公式，由 `power` × 通道基准**算出来**：`atk*2.2` / `matk*1.4`。
   带 `exprs` 之后引擎走**表达式分支**（`_skill_seg_damage`），不再按 kind 兜底取 matk。

③ `kind_key` —— 技能类别（`主动` / `被动`）的 **ASCII 机器键**（`active` / `passive`），
   紧跟 `kind` 后面落一条（B4-1）。为什么要有它（K48 / K51 / P-20 同族）：
   - 代码里**不许拿中文枚举当机器键**（`probe_copy` ⑮ 必须 0 处）—— 而「这条技能是不是被动」
     正是代码要判的一件事（被动不进战斗技能表、不许当技能放）；
   - 与 `items.kind_key` / `monsters.role_key` / `recipes.kind_key` 同一形状：中文 `kind`
     留给玩家看，ASCII `kind_key` 给代码比；
   - 映射表 `KIND_KEY` 是唯一来源（解析的是域里那份中文枚举）；域里出现表外的类别 ⇒ **当场抛**。

★ 幂等：连跑两次数据不变。`--dry` 只打印不写盘。

用法：python scripts/rebuild_skills.py [--dry]
"""
from __future__ import annotations

import argparse
import io
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(REPO, "content", "data", "skills.json")
KINDS = os.path.join(REPO, "content", "rules", "kinds.json")
CLASSES = os.path.join(REPO, "content", "data", "classes.json")
with io.open(CLASSES, encoding="utf-8") as _f:
    CLS = json.load(_f)

#: 职业 → 伤害通道 —— **真源 = `content/data/classes.json` 的 `dmg_channel`**
#: （该职业的伤害走 atk 还是 matk；六份职业详案的伤害列就是这么写的：
#:   骑士 / 狂战士 / 游侠 / 刺客 用 atk（01_骑士_v2 §七「10 级 atk 62.2 × 2.2」·
#:   03_游侠_v2 §五「83.6 × 2.6」· 06_刺客_v2 §五「82.0 × 1.2」）；
#:   法师 / 修女 用 matk（04_法师_v2 §五「matk 116.8 × (1+0.35×4)」）
#:   —— 元素字段（ELE_FIRE …）**不是**通道：狂战士「焚身」是火元素的自伤重击，打的仍是 atk）。
def _channel(rec: dict) -> str:
    ch = (CLS.get(rec.get("owner_class")) or {}).get("dmg_channel")
    if ch not in ("phys", "magi"):
        raise KeyError("职业 %r 在 classes.json 里没有 `dmg_channel`（phys/magi）—— 技能 %r 算不出倍率公式"
                       % (rec.get("owner_class"), rec.get("name")))
    return ch


#: 治疗类机制（不产生伤害，走治疗通道；倍率含义 = 治疗倍率）
HEAL_MECHS = ("hot",)

#: ★ B4-1：技能类别（域里那份中文枚举）→ ASCII 机器键。代码只比 `kind_key`，
#:   一个中文字都不比（`probe_copy` ⑮ 钉着「中文枚举当机器键」必须 0 处）。
#:   新类别（若以后有「天赋」之类）要先补这张表 —— 表外取值当场抛，不静默当主动。
KIND_KEY = {"主动": "active", "被动": "passive"}

#: 六职业的**普攻**（真源 = `03_职业与技能/02_技能体系规划_v1.md` §五「普攻 + 第一条主动」：
#:   普攻 = 本职业那条零消耗、无冷却的起手技）。原先 `basic_skill_of` 按 power 升序取
#:   「最低的那条」⇒ 骑士取到盾墙(0.0)、刺客/游侠取到后撤(0.0)、修女取到净罪(0.0)。
BASIC = (
    "SKILL_KNT_slash", "SKILL_BSK_cleave", "SKILL_RNG_shortbow",
    "SKILL_MAG_stardust", "SKILL_PRS_staff", "SKILL_SHD_blade",
)


def _kinds() -> dict:
    with io.open(KINDS, encoding="utf-8") as f:
        d = json.load(f)
    return {k: v for k, v in d.items() if not str(k).startswith("_")}


def _basis(channel: str) -> str:
    """通道 → 表达式里的属性名（物理吃 atk · 魔法/治疗吃 matk）。"""
    return "atk" if channel == "phys" else "matk"


def _num(x) -> str:
    """倍率写进表达式时的写法（与探针复算同一格式）。"""
    s = ("%.6f" % float(x)).rstrip("0").rstrip(".")
    return s or "0"


def channel_of(rec: dict) -> str:
    """一条技能走哪条通道（键名 = kinds.json 的键）。"""
    if str(rec.get("mech") or "") in HEAL_MECHS:
        return "heal"
    if float(rec.get("power", 0) or 0) <= 0:
        return "buff"
    return _channel(rec)


def kind_key_of(rec: dict) -> str:
    """技能类别 → ASCII 机器键（`KIND_KEY` 是唯一来源；表外取值当场抛，不静默兜底）。"""
    k = rec.get("kind")
    if k not in KIND_KEY:
        raise KeyError("技能 %r 的 `kind` = %r 不在 KIND_KEY 表里（有的：%s）—— "
                       "新类别要先补表（表在 scripts/rebuild_skills.py）"
                       % (rec.get("name") or rec.get("desc") or "?", k, " · ".join(sorted(KIND_KEY))))
    return KIND_KEY[k]


def _place_after(rec: dict, anchor: str, key: str, value) -> None:
    """把 `key` 插在 `anchor` 后面（就地改）—— 机器键紧挨着它对应的中文枚举。"""
    out = {}
    for k, v in rec.items():
        out[k] = v
        if k == anchor:
            out[key] = value
    if key not in out:
        out[key] = value
    rec.clear()
    rec.update(out)


def exprs_of(rec: dict) -> list:
    """倍率公式：`<基准>*<power>`（治疗/增益不做伤害 ⇒ 不算这条）。"""
    ch = channel_of(rec)
    if ch in ("heal", "buff"):
        return []
    return ["%s*%s" % (_basis(ch), _num(rec.get("power", 0)))]


def fix(mos: dict, kinds: dict, dry: bool = False) -> int:
    """就地补 kind_override / exprs / basic；返回改动条数。"""
    n = 0
    for sid, rec in mos.items():
        if str(sid).startswith("_") or not isinstance(rec, dict):
            continue
        ch = channel_of(rec)
        want_kind = kinds[ch]
        want_exprs = exprs_of(rec)
        want_basic = sid in BASIC
        want_kk = kind_key_of(rec)
        if rec.get("kind_key") != want_kk:
            if "kind_key" in rec:
                rec["kind_key"] = want_kk
            else:
                _place_after(rec, "kind", "kind_key", want_kk)
            n += 1
        if rec.get("kind_override") != want_kind:
            rec["kind_override"] = want_kind
            n += 1
        if want_exprs:
            if rec.get("exprs") != want_exprs:
                rec["exprs"] = want_exprs
                n += 1
        else:
            if "exprs" in rec:
                rec.pop("exprs")
                n += 1
        if want_basic and rec.get("basic") is not True:
            rec["basic"] = True
            n += 1
        elif not want_basic and "basic" in rec:
            rec.pop("basic")
            n += 1
    if dry:
        return n
    with io.open(PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(mos, ensure_ascii=False, indent=2) + "\n")
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    with io.open(PATH, encoding="utf-8") as f:
        mos = json.load(f)
    kinds = _kinds()
    n = fix(mos, kinds, dry=a.dry)
    print("%s：%d 条技能 · 改动 %d 格" % ("预览（未写盘）" if a.dry else "已写盘", len(mos), n))
    print("  %-24s %-8s %-6s %-8s %s" % ("技能", "通道", "power", "exprs", "basic"))
    for sid in sorted(mos):
        r = mos[sid]
        if not isinstance(r, dict):
            continue
        print("  %-24s %-8s %-6s %-8s %s"
              % (sid, r.get("kind_override"), r.get("power"),
                 (r.get("exprs") or ["—"])[0], "●" if r.get("basic") else ""))


if __name__ == "__main__":
    main()
