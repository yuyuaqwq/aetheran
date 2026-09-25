# -*- coding: utf-8 -*-
"""探针：items 域 —— kind/quality/slot/**kind_key** 合法 · ★ 词条 stat 守命名规范 · 遗物必有「来处」·
★ B3-9：每条词条在呈现口都说得成人话（数值类有 texts 标签 · 效果类带 note）。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_items.py
"""
from __future__ import annotations

import os
import time
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402

ok = True
# ★ kind / quality / slot 三份都从 schema 读（单一真源）—— 写死一份副本就会漂
#   （本次实测：加了信物/线索/垃圾后忘了同步）。B3-6b-2d-b：连**回退副本**也撤了 ——
#   读不到 schema 就当场退出（fail-closed），不许拿一份旧名单顶上。
import json as _json
_KINDS_SCHEMA = os.path.join(REPO, "schemas", "items.schema.json")
try:
    with open(_KINDS_SCHEMA, encoding="utf-8") as _f:
        _s = _json.load(_f)
    _PROPS = _s["patternProperties"]["^i_[a-z0-9_]+$"]["properties"]
    KINDS = set(_PROPS["kind"]["enum"])
    QUALITIES = set(_PROPS["quality"]["enum"])
    SLOTS = set(_PROPS["slot"]["enum"])
    KIND_KEYS = set(_PROPS["kind_key"]["enum"])       # ★ B3-6b-2d-keys-2：ASCII 机器键那一栏
except Exception as _exc:                                              # noqa: BLE001
    print("  ✗ items.schema.json 读不到（kind/quality/slot/kind_key 的唯一真源，没有回退副本）：%s" % _exc)
    sys.exit(1)
# 数值类（必须用属性字典标准键）—— 照 11_装备特色词条池 §六
NUMERIC = {"hp", "atk", "matk", "def", "res", "spd", "hit", "eva", "crit", "critdmg",
           "block", "pen", "pen_res", "heal_pow", "mo_max"}
ELEM_RES = {"res_fire", "res_ice", "res_water", "res_thunder", "res_earth", "res_wind",
            "res_light", "res_shadow"}
SPECIAL = {"res_element"}          # 唯一允许的笼统写法（必须带 note）


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


print("探针：items 域（装备 / 材料 / 道具）")
st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
st.install()
it = st.domain("items")
chk("items 域读得到", it is not None, "%d 条" % (len(it) if it else 0))
if not it:
    sys.exit(1)

# ★ B3-6b-2d-b：装备的机器键 = 域里现成的 ASCII `slot`（**不再是中文 `kind`**）——
#   装备 = 「有 slot 的那些」（原先按 kind 的六类中文白名单筛）。
equip = {k: v for k, v in it.items() if v.get("slot")}

# ① 三键合法
chk("kind 合法", not [k for k, v in it.items() if v["kind"] not in KINDS])
chk("quality 合法", not [k for k, v in equip.items() if v.get("quality") not in QUALITIES])
chk("slot 合法", not [k for k, v in equip.items() if v.get("slot") not in SLOTS])

# ①之二 ★ B3-6b-2d-b：装备的机器键换成 ASCII `slot` 之后，「走 slot」= 「走 kind 六类白名单」
#   三件事一起钉（这是「换键不改行为」的**结构性前提**，不是巧合）：
#     ① 域自己就是那张「中文 kind → ASCII slot」映射表，而且是**单射**
#     ② kind 把装备 / 非装备分得干净 ⇒ 两种筛法**同集合**
#     ③ 六格全盖到（每种装备 kind 至少一条）
_k2s = {}
for _k, _v in equip.items():
    _k2s.setdefault(_v["kind"], set()).add(_v["slot"])
_dup = {a: sorted(b) for a, b in _k2s.items() if len(b) != 1}
chk("★ 装备的 kind → slot 是单射（域自己就是那张映射表：%s）"
    % " · ".join("%s→%s" % (a, sorted(b)[0]) for a, b in sorted(_k2s.items())),
    not _dup, "%s" % _dup)
_with = {v["kind"] for v in it.values() if v.get("slot")}
_without = {v["kind"] for v in it.values() if not v.get("slot")}
chk("★ kind 把装备 / 非装备分得干净（装备 %s ｜ 非装备 %s）⇒ 「走 slot」与「走 kind 白名单」同集合"
    % ("/".join(sorted(_with)), "/".join(sorted(_without))), not (_with & _without))
chk("★ 六格全盖到（%s）" % "/".join(sorted({v["slot"] for v in equip.values()})),
    {v["slot"] for v in equip.values()} == SLOTS)
chk("★ 装备 %d 件都带 `slot` · 非装备 %d 件一件都没带（换 ASCII 键的依据）"
    % (len(equip), len(it) - len(equip)),
    all(v.get("slot") for v in equip.values())
    and not [k for k, v in it.items() if not v.get("slot") and v["kind"] in _with])

# ⑧ ★ B3-6b-2d-keys-2：机器键 `kind_key`（P-20 甲案第二刀）—— **三头对账**：
#   schema enum（唯一真源） ↔ 生成器那张表（`scripts/rebuild_kind_keys.py`） ↔ 域里 122 条。
#   为什么三头都要核：表漂了（代码侧的键变了）或 enum 漂了（校验口径变了）或数据漂了，
#   任何一种都会让「代码比 A、域里写 B」静默不命中 —— 那正是这半批要根除的病。
try:
    import rebuild_kind_keys as RK                                          # noqa: E402
except Exception as _exc:                                                   # noqa: BLE001
    print("  ✗ scripts/rebuild_kind_keys.py 读不到（kind_key 映射表的唯一来源）：%s" % _exc)
    sys.exit(1)
_bad_kk = [k for k, v in it.items() if v.get("kind_key") not in KIND_KEYS]
chk("★ 每件东西都带 `kind_key` 且值都在 schema 的 enum 里（%d 类）" % len(KIND_KEYS),
    not _bad_kk, "缺/非法：%s" % _bad_kk[:6])
chk("★ 生成器映射表 == schema enum（两张表逐值相等：%s）"
    % " · ".join("%s→%s" % kv for kv in sorted(RK.ITEM_KIND_KEY.items())),
    set(RK.ITEM_KIND_KEY.values()) == KIND_KEYS,
    "表=%s / enum=%s" % (sorted(set(RK.ITEM_KIND_KEY.values()) - KIND_KEYS),
                         sorted(KIND_KEYS - set(RK.ITEM_KIND_KEY.values()))))
_k2k: dict = {}
for _k, _v in it.items():
    _k2k.setdefault(_v["kind"], set()).add(_v.get("kind_key"))
chk("★ 中文 kind → ASCII kind_key 是**单射**且与生成器表逐条一致（域自己就是那张映射表）",
    all(len(_s) == 1 and RK.ITEM_KIND_KEY[_k] == sorted(_s)[0] for _k, _s in _k2k.items()),
    "%s" % {a: sorted(b) for a, b in _k2k.items() if len(b) != 1})
chk("★ 装备那半：`kind_key` == `slot`（第一刀收的机器键与这一刀新补的键**同值**· %d 件）"
    % len(equip), all(v["kind_key"] == v["slot"] for v in equip.values()),
    "%s" % [(k, v["kind_key"], v["slot"]) for k, v in equip.items() if v["kind_key"] != v["slot"]][:4])
_nonkey = {v["kind_key"] for v in it.values() if not v.get("slot")}
chk("★ 非装备那半：`kind_key` 落在非装备六类里（%s）且一件都没带 slot"
    % "/".join(sorted(_nonkey)),
    _nonkey == (KIND_KEYS - SLOTS)
    and not [k for k, v in it.items() if not v.get("slot") and v.get("kind_key") in SLOTS],
    "%s" % sorted(_nonkey - (KIND_KEYS - SLOTS)))

# ② 装备类字段齐
bad2 = [k for k, v in equip.items() if not v.get("affixes")]
chk("每件装备都有词条", not bad2, " · ".join(bad2[:4]))

# ③ ★ 词条 stat 守规范
bad3 = []
for k, v in equip.items():
    for a in v.get("affixes", []):
        s = a.get("stat", "")
        if s in NUMERIC or s in ELEM_RES:
            continue
        if s in SPECIAL:
            if not a.get("note"):
                bad3.append("%s.%s 缺 note" % (k, s))
            continue
        # 效果类：必须带 note（说明它改了什么规则）
        if not a.get("note"):
            bad3.append("%s.%s 效果类缺 note" % (k, s))
chk("★ 词条 stat 守命名规范（数值类用标准键 · 效果类带 note）", not bad3, " · ".join(bad3[:5]))

# ④ ★ 遗物必有「来处」
bad4 = [k for k, v in it.items() if v.get("quality") == "遗物" and not v.get("lore")]
chk("★ 每件遗物都有「来处」", not bad4, " · ".join(bad4[:5]))
relics = [k for k, v in it.items() if v.get("quality") == "遗物"]

# ⑤ 套装件有 set_id
sets = {}
for k, v in it.items():
    if v.get("set_id"):
        sets.setdefault(v["set_id"], []).append(k)
chk("套装件都有 set_id", bool(sets), " · ".join("%s×%d" % (s, len(ks)) for s, ks in sets.items()))

# ⑥ 「来处」不是套话（长度与去重）
lores = [v["lore"] for v in it.values() if v.get("lore")]
chk("「来处」互不相同", len(set(lores)) == len(lores), "%d 条" % len(lores))
short = [k for k, v in it.items() if v.get("lore") and len(v["lore"]) < 8]
chk("「来处」都不是敷衍（≥8 字）", not short, " · ".join(short[:4]))

# ⑨ ★ B3-9：装备词条的**呈现口径**（穿 / 卸 / 对比 三条共用 `cmds_gear` 那两支）——
#   对照只比**不带 note 的数值词条**（面板属性那一类）⇒ 这些键必须能在 texts 里取到中文名
#   （`SYS_STAT_<键>`）；带 note 的是规则，原样出 `note`（域里那句人话），不进数值行。
#   少了标签 = 呈现口要么漏机器键、要么出 `[MISSING TEXT: …]`（B3-7 / B3-9 同族那条线）。
_tx9 = st.domain("texts") or {}
_num9, _note9, _bad9 = set(), set(), []
for _k9, _v9 in equip.items():
    for _a9 in _v9.get("affixes") or []:
        _s9 = str(_a9.get("stat") or "")
        _numeric9 = isinstance(_a9.get("v"), (int, float)) and not isinstance(_a9.get("v"), bool)
        if _a9.get("note"):
            _note9.add(_s9)                     # 规则类：原样出 note（数值差不进对照）
            continue
        if not _numeric9:
            _bad9.append("%s.%s 既无数值也无 note（说不成人话）" % (_k9, _s9))
            continue
        _num9.add(_s9)
        if ("SYS_STAT_%s" % _s9.upper().replace("-", "_")) not in _tx9:
            _bad9.append("%s.%s 缺 texts 标签" % (_k9, _s9))
chk("★ 词条呈现口径：不带 note 的数值词条 %d 个键都有 `SYS_STAT_*` 标签（%s）· "
    "带 note 的 %d 个键原样出 note"
    % (len(_num9), " · ".join(sorted(_num9)), len(_note9)), not _bad9, " · ".join(_bad9[:5]))

# ⑩ ★ B3-19：**装备属性门槛**（`req`）—— 每件都算得出（或显式无门槛），值一律从 `alloc_of` 那个口现算
#   口径唯一落点 = `scripts/rebuild_item_reqs.py`（家族 → 属性 · 品质倍数 · 门槛级来源）。
#   本节的三个方向：
#     ① 每件装备：要么带 `req`，要么**显式无门槛** —— 认不出的家族生成器会抛（fail-closed），
#        这里把「域里有一件谁都没管」钉出来（数量对账）
#     ② 域里那个 `v` **不是抄的**：探针自己用 `rebuild_monsters.alloc_of(门槛级, 参考职业)[属性]`
#        × 品质倍数 现算一遍（不手写镜像串 ⇒ 谁手改域里那个数就翻红）
#     ③ 门槛级 = 那一档来源的怪的最低等级（域里的 `role_key` 现推）
import math as _math10                                                       # noqa: E402
try:
    import rebuild_item_reqs as RIR                                          # noqa: E402
    import rebuild_monsters as RBM10                                         # noqa: E402
except Exception as _exc:                                                    # noqa: BLE001
    print("  ✗ scripts/rebuild_item_reqs.py / rebuild_monsters.py 读不到（门槛那两条口径的源头）：%s"
          % _exc)
    sys.exit(1)
_CL10 = {k: v for k, v in (st.domain("classes") or {}).items() if not str(k).startswith("_")}
_MON10 = st.domain("monsters") or {}
_LV10 = {q: RIR.req_level_of(q, _MON10) for q in ("精制", "稀有", "遗物")}
_bad10, _n10 = [], 0
for _k10, _v10 in sorted(equip.items()):
    _got10 = _v10.get("req")
    _want10 = RIR.req_of(_k10, _v10, _CL10, _MON10)          # ① 算得出？认不出的家族这里就抛了
    if _want10 != _got10:                                    # 域里那一格是不是生成器会写的那一格
        _bad10.append((_k10, "域里那一格与生成器算的不同", _got10, _want10))
        continue
    if not _want10:                                          # 显式无门槛（普通 / 头盔 / 稳靴 / 饰品 / 套装）
        continue
    _n10 += 1
    _a10, _q10 = _want10["attr"], _v10["quality"]
    _cid10 = RIR.ref_class_for_item(_CL10, _k10, _a10)        # 武器的「谁」= 它自己那个职业
    _ref10 = float(RBM10.alloc_of(_LV10[_q10], _cid10)[_a10])
    _exp10 = max(1, int(_math10.floor(RIR.QUALITY_MULT[_q10] * _ref10 + 0.5)))
    if _want10["v"] != _exp10 or _want10["level"] != _LV10[_q10]:
        _bad10.append((_k10, "值/门槛级对不上", _want10, {"v": _exp10, "level": _LV10[_q10]}))
_free10 = [k for k, v in equip.items() if not v.get("req")]
chk("★ 装备 %d 件：%d 件有门槛（%s）· %d 件显式无门槛（普通品阶 + 头盔/稳靴/饰品/套装 —— 见 `_notes.md`）"
    % (len(equip), _n10, " · ".join("%s %d" % (q, len([1 for k, v in equip.items()
                                                      if v.get("req") and v["quality"] == q]))
                                    for q in ("精制", "稀有", "遗物")), len(_free10)),
    not _bad10 and _n10 > 0 and bool(_free10), "%s" % _bad10[:3])
_badk10 = [k for k, v in it.items() if not v.get("slot") and v.get("req")]
chk("★ 非装备（没 slot 的 %d 件）一件都不许带 `req`" % (len(it) - len(equip)), not _badk10,
    "%s" % _badk10[:3])
chk("★ 门槛级 = 那一档来源的怪的最低等级（域里现推）：%s"
    % " · ".join("%s=%s（%s 档）" % (q, _LV10[q], "/".join(RIR.QUALITY_ROLE[q]))
                 for q in ("精制", "稀有", "遗物")),
    all(_LV10[q] == min(int(m.get("lv")) for m in _MON10.values()
                        if m.get("role_key") in RIR.QUALITY_ROLE[q])
        for q in ("精制", "稀有", "遗物")))
_BADFAM10 = []
for _k10, _v10 in equip.items():
    _fam10 = RIR.family_of(_k10)
    if _fam10 not in RIR.FAMILY_ATTR and not _fam10.startswith(("weapon_", "set_")) \
            and _fam10 not in RIR.FAMILY_FREE:
        _BADFAM10.append((_k10, _fam10))
chk("★ 每个家族都登记过（有门槛的 %d 个 / 显式无门槛的 %d 个 + 套装）—— 不许有「谁都没管」的家族"
    % (len(RIR.FAMILY_ATTR), len(RIR.FAMILY_FREE)), not _BADFAM10, "%s" % _BADFAM10[:4])

print()
by_kind = {}
for k, v in it.items():
    by_kind[v["kind"]] = by_kind.get(v["kind"], 0) + 1
print("  · 按 kind：" + " · ".join("%s %d" % (a, b) for a, b in sorted(by_kind.items())))
by_q = {}
for v in equip.values():
    by_q[v.get("quality", "?")] = by_q.get(v.get("quality", "?"), 0) + 1
print("  · 装备按品阶：" + " · ".join("%s %d" % (a, b) for a, b in sorted(by_q.items())))
print("  · 遗物 %d 件（全带「来处」）· 套装 %d 套" % (len(relics), len(sets)))
print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
