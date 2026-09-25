# -*- coding: utf-8 -*-
"""《阿斯特兰》元素通道（P-1 最小样例）—— 「域里 `ELE_*` 码 → 引擎元素名」的唯一出口。

为什么有这一层（先看结论）
------------------------------------------------------------------
引擎**早就有**整条元素通道，而本包这一侧一行都没消费过它：

    `ext_combat/battle/actions.py:440`    出手落地时把 `info["element"]` 传给落地层
    `ext_combat/battle/landing.py:77-108` N10-B4 承伤方免疫/弱点表：
                                          `target.element_immune` 含该元素 ⇒ 伤害归 0；
                                          `target.element_weak[元素] > 1` ⇒ ×倍率
    `ext_combat/battle/battle.py`          `Battle(text=…)` 文案注入（日志走槽位）

而本包：`skills` 域 25 条带 `ELE_*` 码（**原样透传**进引擎），`content/combat.monster_actor`
出来的怪**身上一个免疫/弱点表都没有**，`Battle(...)` 也从不传 `text`。于是这条线是典型的
「表看着有、代码没消费」：数据在、通道在、**判据为零**。本模块把它接上，且只接**一格**：

    域里的码（ELE_FIRE）→ 引擎元素名（fire）· 怪物那一系 → 环里反查出它的弱点

四条纪律
------------------------------------------------------------------
1. **零手打**：映射、环、倍数只在 `content/rules/elements.json` 一处（本模块不写元素名、
   不写 1.25、更不写「水怕冰」——那是从环里**反查**出来的）。真源 =
   `02_数值宪法/01_属性字典与基础公式.md §二·五`。
2. **fail-closed 在装配期**：`check_domain()` 扫整份 `skills` 域与样例挂的怪 id ——
   没声明过的码 / 挂在不存在那只怪上 / 环里反查不到「克它的一系」/ 同一元素既免疫又弱
   ⇒ **当场抛并点名**（与 `content/mech.py::check_domain` 同一形状）。**不静默当「无元素」**。
3. **不装配 = 与今天逐字相同**：`sample` 那块不在（或 `enabled: false`）⇒ `sample_fields()`
   回 `{}` ⇒ `monster_actor` 一个字段都不写（探针 ⑧ 有反证）。
4. ⚠️ **本模块的返回值会进战斗日志与落地判定** ⇒ 映射这一层**不许吞异常**（`landing.py`
   那 108 行整块包在 `except Exception: pass` 里 —— 渲染或映射一抛，免疫会连「伤害归 0」
   一起静默失效）。所以「答不上来」一律在**装配期**抛（装配期抛 = 看得见，运行期抛 = 静默）。
"""
from __future__ import annotations

import json
import os

_RULES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules", "elements.json")

#: 读一次；`_CACHE["decl"]` = 校验过的声明
_CACHE: dict = {}

#: 「明确不入环」的写法（空串）—— 与「没声明」是两件事
_NO_ELEMENT = ""


def _load() -> dict:
    """读 + 校验 `content/rules/elements.json`（**装配期**该回答的问题不留到运行期）。"""
    if "decl" in _CACHE:
        return _CACHE["decl"]
    with open(_RULES, encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError("elements.json 的根必须是对象：%r" % (type(raw).__name__,))
    codes = raw.get("codes")
    if not isinstance(codes, dict) or not codes:
        raise ValueError("elements.json 少了 `codes`（域里的码 → 引擎元素名）")
    for k, v in codes.items():
        if not str(k).startswith("ELE_"):
            raise ValueError("元素码要以 ELE_ 开头（域里的写法）：%r" % (k,))
        if not isinstance(v, dict) or not isinstance(v.get("engine"), str):
            raise ValueError("元素码 %r 要写 {\"engine\": \"<引擎侧名>\"}（明确不入环就写空串）" % (k,))
    labels = raw.get("labels")
    if not isinstance(labels, dict) or not labels:
        raise ValueError("elements.json 少了 `labels`（元素名 → 真源那一行里的字），环对账要用它")
    alts = raw.get("labels_alt") or {}
    if not isinstance(alts, dict):
        raise ValueError("elements.json 的 `labels_alt` 要写成 {元素名: [同义字]}：%r" % (alts,))
    for k, v in alts.items():
        if k not in labels or not isinstance(v, list) or not all(str(x) for x in v):
            raise ValueError("labels_alt 的键得在 labels 里、值要是字：%r" % ({k: v},))
    mult = raw.get("multipliers")
    if not isinstance(mult, dict) or "strong" not in mult:
        raise ValueError("elements.json 少了 `multipliers.strong`（克制倍数，真源 = 宪法二·五）")
    for k in ("strong", "weak", "neutral"):
        if k in mult and not isinstance(mult[k], (int, float)):
            raise ValueError("multipliers.%s 要是个数：%r" % (k, mult.get(k)))
    ring = raw.get("ring")
    if not isinstance(ring, list) or not ring:
        raise ValueError("elements.json 少了 `ring`（六元素环，[克者, 被克者] 成对）")
    for pair in ring:
        if not isinstance(pair, list) or len(pair) != 2 or not all(isinstance(x, str) and x for x in pair):
            raise ValueError("ring 每条要写 [克者, 被克者] 两个非空名：%r" % (pair,))
        if pair[0] not in labels or pair[1] not in labels:
            raise ValueError("ring 里的名字要在 `labels` 里都有字：%r" % (pair,))
    # ⚠️ 这里**不能**调 `labels()` / `beaten_by()`（它们会回头调 `_load()` ⇒ 递归）——
    #   把已经读到手的 `labels` 与 `ring` 直接传进去。
    _validate_sample(raw.get("sample"), codes, ring, labels)
    _CACHE["decl"] = raw
    return raw


def _validate_sample(sample, codes: dict, ring: list, labels_map: dict):
    """样例声明自检（装配期）：只认声明过的码 · 弱点必须由环反查得到 · 免疫不许自相矛盾。"""
    def _beats(e: str) -> str:                    # 环里克 e 的那一系（就地算，不回头调 _load）
        return next((a for a, b in ring if b == e), "")

    if sample in (None, {}):
        return
    if not isinstance(sample, dict):
        raise ValueError("elements.json 的 `sample` 要么整块删掉，要么是个对象：%r" % (sample,))
    if sample.get("enabled") is not True:
        return                                   # 明确关掉 ⇒ 与整块删掉同义，不再校验细节
    mons = sample.get("monsters")
    if not isinstance(mons, dict) or not mons:
        raise ValueError("样例开着，`sample.monsters` 就得写「挂在哪只怪上（域里的怪 id）」")
    for mid, rec in mons.items():
        if not isinstance(rec, dict):
            raise ValueError("样例 %r 要写成一个对象：{\"element\": \"ELE_…\", \"immune\": [...]}" % (mid,))
        own = str(rec.get("element") or "")
        if own not in codes:
            raise ValueError("样例 %s 的 `element`（%r）没在 codes 里声明过" % (mid, own))
        if not codes[own].get("engine"):
            raise ValueError("样例 %s 的 `element`（%r）是「明确不入环」的码 —— 入不了环就反查不出弱点" % (mid, own))
        own_lbl = codes[own]["engine"]
        if own_lbl not in labels_map:
            raise ValueError("样例 %s 那一系 %r 不在 labels 里（环对账对不上）" % (mid, own_lbl))
        if not _beats(own_lbl):
            raise ValueError("环里反查不到「克 %s 的那一系」（环坏了 / 名字不在环里）：%s" % (own_lbl, ring))
        for c in (rec.get("immune") or []):
            if c not in codes:
                raise ValueError("样例 %s.immune 里的 %r 没在 codes 里声明过（先声明再挂）" % (mid, c))
            if not codes[c].get("engine"):
                raise ValueError("样例 %s.immune 里的 %r 是「明确不入环」的码 —— 挂它没有意义" % (mid, c))
            if codes[c]["engine"] == own_lbl:
                raise ValueError("样例 %s 免疫自己那一系（%s）—— 自相矛盾" % (mid, own_lbl))
            if codes[c]["engine"] == _beats(own_lbl):
                raise ValueError("样例 %s 把「克自己那一系」（%s）写成免疫 —— 免疫与克制不能同时挂"
                                 % (mid, _beats(own_lbl)))


def codes() -> dict:
    return _load()["codes"]


def labels() -> dict:
    """元素名 → 真源那一行里的字（`fire` → `火`）。"""
    return _load()["labels"]


def labels_alt() -> dict:
    """元素名 → 真源**另一处**用的同义字（`thunder` → `电`）—— 只给「口诀 × 环」对账用。"""
    return {k: list(v) for k, v in (_load().get("labels_alt") or {}).items()}


def multipliers() -> dict:
    return _load()["multipliers"]


def ring() -> list:
    """六元素环：`[[克者, 被克者], ...]`（现读声明；真源 = 宪法二·五那两行）。"""
    return [list(x) for x in _load()["ring"]]


def beaten_by(elem: str) -> str:
    """环里**克** `elem` 的那一系（每元素恰好一个，闭合环）——取不到回 `""`（不猜）。"""
    e = str(elem or "")
    if not e:
        return ""
    for a, b in ring():
        if b == e:
            return a
    return ""


def engine_label(code: str) -> str:
    """域里的码 → 引擎侧元素名。空/未声明都在这儿定：空 ⇒ `""`（无元素）；没声明过 ⇒ **抛**。"""
    c = str(code or "").strip()
    if not c:
        return _NO_ELEMENT
    tbl = codes()
    if c not in tbl:
        raise KeyError("元素码 %r 没在 content/rules/elements.json 的 `codes` 里声明过（有的：%s）"
                       % (c, " · ".join(sorted(tbl))))
    return str(tbl[c].get("engine") or "")


def element_of(rec: dict) -> str:
    """域里那条技能 → 给引擎看的 `element`（空串 = 无元素 ⇒ 落地层那条元素支整个不进）。"""
    if not isinstance(rec, dict):
        return _NO_ELEMENT
    return engine_label(rec.get("element"))


def sample_enabled() -> bool:
    s = _load().get("sample") or {}
    return bool(s) and s.get("enabled") is True


def sample_monsters() -> dict:
    """样例连着的怪：`{怪 id: 声明原样}`（没开 ⇒ 空表）。"""
    s = _load().get("sample") or {}
    if not s or s.get("enabled") is not True:
        return {}
    return dict(s.get("monsters") or {})


def monster_element(mid: str) -> str:
    """样例里这只怪**自己那一系**（引擎侧名 + 真源那个字）；不是样例怪 ⇒ 空串。"""
    rec = sample_monsters().get(str(mid))
    if not isinstance(rec, dict):
        return ""
    return engine_label(rec.get("element"))


def sample_fields(mid: str) -> dict:
    """P-1 样例：这只怪身上要挂的元素字段（没声明 / 关掉 / 不是那只怪 ⇒ 空 dict = 一个字段不写）。

    ★ **弱点不写死在声明里** —— 由「这只怪是哪一系」在环里**反查**（水 ⇒ 冰凝水 ⇒ 弱冰）；
      倍数取 `multipliers.strong`（唯一那一处数）。免疫那一栏是真源还没给口径的样例档
      （见 `_notes.md` 待补行），所以只声明「免哪个元素」，不声明强度。
    """
    rec = sample_monsters().get(str(mid))
    if not isinstance(rec, dict):
        return {}
    out: dict = {}
    imm = [engine_label(c) for c in (rec.get("immune") or [])]
    if imm:
        out["element_immune"] = imm
    own = engine_label(rec.get("element"))
    weak = beaten_by(own)
    if weak:
        out["element_weak"] = {weak: float(multipliers()["strong"])}
    return out


def check_domain(raise_on_unknown: bool = True) -> dict:
    """跨域对账（装配期）：域里每个 `element` 值都声明过 · 样例挂在**真有的**怪上。

    返回 `{元素码: [技能 id, ...]}`（现算，不写镜像表）。这一条就是防「元素表看着有、
    代码没消费」的常驻判据：新加一条技能带了个没人认得的码 ⇒ 装配当场红，而不是静默
    按「无元素」打出去。
    """
    from . import skills_lookup as SL

    seen: dict = {}
    unknown: list = []
    for sid, rec in SL.skills().items():
        if str(sid).startswith("_") or not isinstance(rec, dict):
            continue
        code = str(rec.get("element") or "").strip()
        if not code:
            continue
        seen.setdefault(code, []).append(sid)
        if code not in codes():
            unknown.append((sid, code))
    if unknown and raise_on_unknown:
        raise KeyError("域里这些技能的元素码没声明过（域 → 引擎这条线会静默当「无元素」）：%s"
                       % " · ".join("%s=%s" % (s, c) for s, c in unknown))
    ghosts: list = []
    if sample_enabled():
        have = SL.monsters()
        ghosts = [m for m in sample_monsters() if m not in have]
    if ghosts and raise_on_unknown:
        raise KeyError("样例挂在不存在的怪上（域里没有这些 id）：%s" % (ghosts,))
    return seen
