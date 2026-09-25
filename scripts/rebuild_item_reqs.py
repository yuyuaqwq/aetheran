# -*- coding: utf-8 -*-
"""重算 items.json 的 `req`（装备属性门槛 · B3-19）—— 家族 × 品质 × 建议加点曲线，**值一律算出来**。

起因（鱼鱼 2026-09-25）：「装备应该也是要依赖加点才能穿的吧」，数值权交主线 ⇒
门槛挂在「家族 × 品质」上，值不许手打。

口径（主线裁决 · 本文件是它的唯一落点）
----------------------------------------
```text
门槛 = 该属性的**最小值**：不满足 ⇒ 穿不上（fail-closed —— `content/cmds_gear.py` 的 `equip`
      报「还差几点」，**不改档、不穿半件**）。不做「能穿但减半」。

① 家族 → 属性（FAMILY_ATTR）
     重甲 armor_top_heavy / 沉甲 armor_bottom_weighted → STR（副 VIT，见 _notes.md 待拍板）
     硬甲 armor_top_tough                            → VIT
     轻甲 armor_bottom_light / 快靴 boots_swift       → AGI
     职业武器 i_weapon_<职业>_*                       → 该职业主属性（suggest_alloc 里份额最高的那项）
② 品质倍数（QUALITY_MULT，乘在「该门槛级、按建议加点铺满时主属性的值」上）
     普通 无门槛 · 精制 0.70 · 稀有 0.90 · 遗物 1.05
③ 门槛级 = 该品阶**在域里的获取起点** = 那一档来源的怪的最低等级：
     精制 ← 精英怪（`monsters.role_key == "elite"`）       → 本包 = 7
     稀有 ← 头目（`chief`）                              → 本包 = 10
     遗物 ← 层主 / boss（`warden` / `boss`）              → 本包 = 17
     普通 ← 镇上铺子 + 普通怪（与加点无关）                → 无门槛
   ★ 为什么不按「某件自己在哪个池里」逐件推：域里 稀有 / 遗物 **武器**今天一个池都没挂
     （只在 15_装备逐件数值 里有值），逐件推会把这 24 件推成「无门槛」——
     与「品阶越高门槛越高」的设计相反。品阶来源带是**域里拿得准**的那一层（怪带 + 真源 §1.1）。
     逐件证据与例外（未鉴定在 lv3 骨田就能开出稀有/遗物）记在 `_notes.md`。
④ 参考值 = 该门槛级、**按建议加点铺满**时该属性的值
     = `rebuild_monsters.alloc_of(req_level, cid)[attr]`（单一口，别处不许再算一份）
     武器的「谁」= 它自己那个职业（职业专属）
     通用防具的「谁」= 该属性的**本命职业** = 六职业 suggest_alloc 里该属性份额最高者
                       （并列取 cid 字典序最小）—— 主属性堆得最高的那个职业，代表这条线
⑤ 门槛值 v = 四舍五入(倍数 × 参考值)，下限 1（不用 banker's rounding：0.5 一律向上）
```

落点：`content/data/items.json` 每件装备的 `req` = `{"attr": "STR", "v": 10, "level": 7}`；
**没有 `req` 那一格 = 无门槛**（显式的那种：家族在 `FAMILY_FREE` / 套装 / 普通品阶 ——
`scripts/probe_items.py` ⑩ 逐件对账，不许「谁都没管」）。schema 见 `schemas/items.schema.json`。

用法：
    python scripts/rebuild_item_reqs.py --dry    # 只看要改什么，不写
    python scripts/rebuild_item_reqs.py          # 落域（幂等：连跑两次数据不变）
"""
from __future__ import annotations

import io
import json
import math
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import rebuild_monsters as RBM                                              # noqa: E402

# ══════════════════════════════════════════════════════════════
# 口径表（改口径改这里，重跑即可 —— 值永远由它算出来）
# ══════════════════════════════════════════════════════════════
#: 家族 → 属性（主线给的四个家族组；家族名 = 物品 id 去掉 `i_` 与末尾 `_<品质>`）
FAMILY_ATTR = {
    "armor_top_heavy": "STR",           # 重甲
    "armor_bottom_weighted": "STR",     # 沉甲（重甲那条下装线）
    "armor_top_tough": "VIT",           # 硬甲
    "armor_bottom_light": "AGI",        # 轻甲
    "boots_swift": "AGI",               # 快靴
}

#: 品质 → 倍数（普通 = 无门槛 ⇒ None）
QUALITY_MULT = {"普通": None, "精制": 0.70, "稀有": 0.90, "遗物": 1.05}

#: 品质 → 它的来源那一档的**怪机器键**（`monsters.role_key`）—— 门槛级 = 这些怪的最低等级
QUALITY_ROLE = {"精制": ("elite",), "稀有": ("chief",), "遗物": ("warden", "boss")}

#: ★ 本批**明确无门槛**的家族（主线只点了四个家族组；这五个不猜 —— 理由与待补建议见 _notes.md）
FAMILY_FREE = ("helmet_thick", "helmet_bright", "boots_steady",
               "accessory_stat", "accessory_effect")

QUALITIES = ("普通", "精制", "稀有", "遗物")

#: ★ id 末尾的**ASCII 品阶词** → 域里那一格中文品阶（`items.quality`）。
#:   装备 id 的后缀是 `_common / _refined / _rare / _relic`（不是中文）——`scripts/rebuild_kind_keys.py`
#:   那一族的机器键纪律：代码侧认 ASCII，中文只留在域里给玩家看。
QUALITY_KEY = {"common": "普通", "refined": "精制", "rare": "稀有", "relic": "遗物"}


# ══════════════════════════════════════════════════════════════
# 取值小件（全部可 import 给探针 —— 探针拿同一批函数现算，不手写镜像串）
# ══════════════════════════════════════════════════════════════
def family_of(iid: str) -> str:
    """物品 id → 家族（去掉 `i_` 前缀与末尾的 `_<ASCII 品阶词>`）。没有品阶后缀 ⇒ 原样当家族。"""
    body = str(iid)
    if body.startswith("i_"):
        body = body[2:]
    for key in QUALITY_KEY:
        if body.endswith("_" + key):
            return body[: -(len(key) + 1)]
    return body


def main_attr_of(classes: dict, cid: str) -> str:
    """某职业的**主属性** = `suggest_alloc` 里份额最高的那项（并列取字母序）—— 算出来，不写死。"""
    sug = (classes.get(cid) or {}).get("suggest_alloc") or {}
    if not sug:
        raise SystemExit("职业 %s 没有 suggest_alloc —— 主属性算不出来" % cid)
    return max(sorted(sug), key=lambda s: sug[s])


def ref_class_of(classes: dict, attr: str) -> str:
    """某属性的**本命职业** = 六职业里建议加点该属性份额最高者（并列取 cid 字典序最小）。

    「本命」只用来定参考值（谁代表这条线），玩家侧不设限：任何人都能加点去够门槛。
    """
    cids = [c for c in sorted(classes) if not str(c).startswith("_")]
    if not cids:
        raise SystemExit("classes 域是空的 —— 参考职业算不出来")
    best = None
    for cid in cids:
        sug = classes[cid].get("suggest_alloc") or {}
        share = float(sug.get(attr, 0)) / float(sum(sug.values()) or 1)
        if best is None or share > best[1]:
            best = (cid, share)
    if not best or best[1] <= 0:
        raise SystemExit("没有职业在 %s 上加过点 —— 参考职业算不出来（别猜）" % attr)
    return best[0]


def ref_class_for_item(classes: dict, iid: str, attr: str) -> str:
    """这件装备的参考职业：武器用**它自己那个职业**；通用防具用该属性的本命职业。"""
    fam = family_of(iid)
    if fam.startswith("weapon_"):
        token = fam.split("_")[1]
        cid = "cls_" + token
        if cid not in classes:
            raise SystemExit("武器 %s 的职业 %s 不在 classes 域里（别猜）" % (iid, cid))
        if main_attr_of(classes, cid) != attr:
            raise SystemExit("武器 %s 的属性 %s 与职业 %s 的主属性对不上"
                             % (iid, attr, cid))
        return cid
    return ref_class_of(classes, attr)


def req_level_of(quality: str, monsters: dict) -> int | None:
    """该品阶的**门槛级** = 那一档来源的怪的最低等级（域里现推）；普通 ⇒ None（无门槛）。

    怪那一栏用 `role_key`（ASCII 机器键）—— 中文档位名不进代码（K48 / P-20）。
    """
    roles = QUALITY_ROLE.get(quality)
    if roles is None:
        return None
    lvs = [int(m.get("lv")) for m in monsters.values()
           if m.get("role_key") in roles and m.get("lv")]
    if not lvs:
        raise SystemExit("品质 %s 的来源那一档在 monsters 域里一只都没有 —— 门槛级推不出来（别猜）"
                         % quality)
    return min(lvs)


def attr_of(iid: str, classes: dict) -> str | None:
    """这件装备的门槛属性；`None` = **显式无门槛**。认不出的家族 ⇒ 抛（fail-closed，不许静默无门槛）。"""
    fam = family_of(iid)
    if fam in FAMILY_ATTR:
        return FAMILY_ATTR[fam]
    if fam.startswith("weapon_"):
        return main_attr_of(classes, "cls_" + fam.split("_")[1])
    if fam in FAMILY_FREE or fam.startswith("set_"):
        return None
    raise SystemExit("家族 %s（物品 %s）没登记：要么进 FAMILY_ATTR，要么进 FAMILY_FREE" % (fam, iid))


def req_value(attr: str, quality: str, level: int, classes: dict, cid: str | None = None) -> int:
    """门槛值 = 四舍五入(品质倍数 × `alloc_of(level, 参考职业)[属性]`)，下限 1。

    ★ 参考值只走 `rebuild_monsters.alloc_of` 那一个口（与战斗 / 配平实验同一把尺）。
    """
    mult = QUALITY_MULT.get(quality)
    if mult is None:
        return 0
    cid = cid or ref_class_of(classes, attr)
    ref = float(RBM.alloc_of(int(level), cid).get(attr) or 0.0)
    if ref <= 0:
        raise SystemExit("%s 在 %s 级按建议加点没有 %s 的点数 —— 参考值是 0（别猜）"
                         % (cid, level, attr))
    return max(1, int(math.floor(mult * ref + 0.5)))


def req_of(iid: str, rec: dict, classes: dict, monsters: dict) -> dict | None:
    """该件装备该写进域里的 `req` 那一格；`None` = 无门槛（普通品阶 / 显式无门槛家族）。

    ★ 品阶读**记录上那一格**（`rec["quality"]`）—— 套装件的 id 里没有品阶词
      （`i_set_scavenger_blade` 是精制），按 id 猜会静默判成「认不出」。缺了 = 数据坏了，当场抛。
    """
    q = rec.get("quality")
    if q not in QUALITIES:
        raise SystemExit("物品 %s 的 quality 不在四档里（%r）—— 别猜" % (iid, q))
    if QUALITY_MULT.get(q) is None:            # 普通 = 无门槛
        return None
    attr = attr_of(iid, classes)
    if attr is None:                           # 显式无门槛的家族（头盔 / 稳靴 / 饰品 / 套装）
        return None
    lv = req_level_of(q, monsters)
    cid = ref_class_for_item(classes, iid, attr)
    return {"attr": attr, "v": req_value(attr, q, lv, classes, cid), "level": int(lv)}


def items_of(equip_only: bool = True) -> dict:
    p = os.path.join(REPO, "content/data/items.json")
    it = json.loads(io.open(p, encoding="utf-8").read())
    return {k: v for k, v in it.items() if (v.get("slot") if equip_only else True)}


def domains() -> tuple:
    def d(n):
        return json.loads(io.open(os.path.join(REPO, "content/data/%s.json" % n),
                                  encoding="utf-8").read())
    return d("items"), d("classes"), d("monsters")


# ══════════════════════════════════════════════════════════════
# 落盘
# ══════════════════════════════════════════════════════════════
def _with_req(rec: dict, req: dict | None) -> dict:
    """把 `req` 插在 `slot` 后面（幂等：先摘掉旧的那一格，再按同一个位置插回去）。"""
    out = {}
    for k, v in rec.items():
        if k == "req":
            continue
        out[k] = v
        if k == "slot" and req is not None:
            out["req"] = req
    if req is not None and "req" not in out:
        raise SystemExit("这条记录没有 `slot` —— 门槛不该挂上去（物品 id 漏了？）")
    return out


def plan(items: dict) -> tuple:
    """算出「每件该长什么样」：返回 (新的、新增/改动的、摘掉的)。"""
    _, classes, monsters = domains()
    new, changed, dropped = {}, [], []
    for iid, rec in items.items():
        if not rec.get("slot"):
            if "req" in rec:                       # 非装备不许带门槛（脏数据当场清掉，并报出来）
                dropped.append(iid)
                new[iid] = _with_req(rec, None)
            else:
                new[iid] = rec
            continue
        want = req_of(iid, rec, classes, monsters)
        got = rec.get("req")
        if want != got:
            changed.append((iid, got, want))
        new[iid] = _with_req(rec, want)
    return new, changed, dropped


def main(argv: list) -> int:
    dry = "--dry" in argv
    items, classes, monsters = domains()
    new, changed, dropped = plan(items)

    with_req = [k for k, v in new.items() if v.get("req")]
    free = [k for k, v in new.items() if v.get("slot") and not v.get("req")]
    print("装备属性门槛（B3-19）· 家族 × 品质 × 建议加点曲线")
    print("  口径：门槛级 精制=%s · 稀有=%s · 遗物=%s（域里 role_key：%s）"
          % (req_level_of("精制", monsters), req_level_of("稀有", monsters),
             req_level_of("遗物", monsters),
             " / ".join("%s→%s" % (q, "+".join(QUALITY_ROLE[q])) for q in QUALITY_ROLE)))
    print("  门槛值 = 倍数(普通无 · 精制 %.2f · 稀有 %.2f · 遗物 %.2f) × alloc_of(门槛级, 参考职业)[属性]"
          % (QUALITY_MULT["精制"], QUALITY_MULT["稀有"], QUALITY_MULT["遗物"]))
    print("  ★ 本命职业（建议加点里份额最高的那个）：%s"
          % " · ".join("%s→%s" % (a, ref_class_of(classes, a))
                       for a in ("STR", "AGI", "VIT", "INT", "WIL")))
    print()
    print("  家族 × 品质 → 门槛值表")
    rows = {}
    for iid, rec in sorted(new.items()):
        r = rec.get("req")
        if not r:
            continue
        rows.setdefault((family_of(iid), rec.get("quality")), set()).add(
            (r["attr"], r["v"], r["level"]))
    for (fam, q), vals in sorted(rows.items()):
        if len(vals) != 1:
            print("  %-24s %-4s ⚠ 同家族同品质出现多个门槛：%s" % (fam, q, sorted(vals)))
            continue
        attr, v, lv = sorted(vals)[0]
        print("  %-24s %-4s 门槛级 %-3s %s ≥ %-4s" % (fam, q, lv, attr, v))
    print()
    print("  带门槛 %d 件 · 显式无门槛（装备）%d 件 · 非装备 %d 件"
          % (len(with_req), len(free), len(new) - len(with_req) - len(free)))
    print("  普通品阶（口径 0 档）= 无门槛：%d 件"
          % len([k for k, v in new.items() if v.get("slot") and v.get("quality") == "普通"]))
    if dropped:
        print("  ! 非装备上发现了要摘掉的 `req`：%s" % dropped)
    if not changed and not dropped:
        print("  —— 无改动（幂等）")
        return 0

    if dry:
        print()
        print("  --dry：以下 %d 件会变（不写盘）" % len(changed))
        for iid, old, want in changed[:12]:
            print("    %-34s %s → %s" % (iid, old, want))
        if len(changed) > 12:
            print("    … 其余 %d 件" % (len(changed) - 12))
        return 0

    p = os.path.join(REPO, "content/data/items.json")
    io.open(p, "w", encoding="utf-8", newline="\n").write(
        json.dumps(new, ensure_ascii=False, indent=2) + "\n")
    print()
    print("  已写 content/data/items.json：%d 件改动" % len(changed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
