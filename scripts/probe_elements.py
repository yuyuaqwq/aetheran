# -*- coding: utf-8 -*-
"""探针：元素通道（P-1 最小样例）—— 「克制 / 免疫」在战斗里真跑得出来 · 可复算 · 一键撤。

判据口径：`02_数值宪法/01_属性字典与基础公式.md §二·五`（六元素环 · 三档倍数 1.25/0.80/1.00）。
本探针**现解析那份真源**（不写镜像数），并核这几件事：

  ① 声明表（`content/rules/elements.json`）读得到 · 形状对 · 每个码都给了引擎名
  ② 域 → 引擎：技能那条 `element` 真翻了名（原先是**原样透传**：码进了引擎、承伤方却没表）
     · 没声明过的码 **当场抛**（不静默当「无元素」）
  ③ 真源对账（现解析 §二·五）：三档倍数逐字 · 环六条边（两种写法互核）· 字与名两向对齐
  ④ 装配期跨域对账：域里**用到的**码都有声明（条数现算，别写死）· 反证「塞个没声明的码 ⇒ 当场抛」
  ⑤ 免疫（机制层真跑）：直调落地 —— 伤害归 **0** + 那行日志**逐字** = texts 槽位渲染
  ⑥ 弱点（机制层真跑 · 可复算）：直调落地 —— 伤害 **== int(基线 × 真源那个倍数)**
  ⑦ 真战斗（技能 → 落地）：放真技能打样例怪 —— 两态差值对得上（冰 == int(基线×1.25) · 火 == 0）
     + 两行日志逐字 · 战斗照旧打得完
     ★ ⑤⑥⑦ 的挨打方**闪避已归零**（`g5-flake`）：这一档原先靠「挑一颗恰好不闪的种子」站着，
       实测换种子会**真红 2 条** ⇒ 判据骑在掷骰次序上（见 `_enemy` 那条注）。期望值一字未改。
  ⑧ 一键撤 / 零影响：关掉样例 ⇒ actor 上没有那两个字段（逐字相同）· 非样例怪两态逐字相同
  ⑨ 死槽位：声明的槽位（含 2026-09-25 补的 DoT 每跳那条）**真被引擎请求过**（`TextTable.unused()` 空）
     · ⑨-a 顺带钉死「DoT 那行不含状态机器键」（引擎兜底会打出 `bleeding`）
  ⑩ 渲染口绝不抛（纪律）：没声明的 key / 空表 ⇒ 一律回字符串 —— 引擎 `landing.py` 那 108 行
     包在 `except Exception: pass` 里，渲染口一抛，免疫会连「伤害归 0」一起静默失效

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_elements.py
"""
from __future__ import annotations

import os
import random
import re
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
PLAN = os.environ.get("AST_PLAN", "C:/Users/yuyu/aetheran-plan")
DOC = os.path.join(PLAN, "02_数值宪法", "01_属性字典与基础公式.md")
sys.path.insert(0, ENGINE)
sys.path.insert(0, REPO)

from saintess_engine.package import load_stack                      # noqa: E402

st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_elements.db"),
                                    "clock": time.time})
st.install()

CB = st.optional_submodule("combat")
ELE = st.optional_submodule("elements")
BT = st.optional_submodule("battle_text")
SK = st.optional_submodule("skills_lookup")
MON = st.domain("monsters")
from ext_combat.battle import landing as LD                          # noqa: E402

MID = "ms_shallow_ghoul"          # P-1 样例怪（既有怪）
OTHER = "ms_field_mouse"          # 对照：不在样例里
SEED = 1                          # 只用来让**两臂吃同一串随机**（伤害波动/暴击两边一致 ⇒ 比值干净）
                                  # ★ 闪避那枚硬币**不**靠它：已在 fixture 里把挨打方 dodge 归零
                                  #   （原先把判据押在「这一种子恰好不闪」上 —— 实测换 4242 红 2 条）

fails = []


def ok(m):
    print("  ✓ " + m)


def bad(m):
    fails.append(m)
    print("  ✗ " + m)


def chk(label, cond, extra=""):
    (ok if cond else bad)(label + (("  —— %s" % extra) if extra else ""))


print("探针：元素通道（P-1 最小样例）")

# ══════════════════════════════════════════════════════════════
# ① 声明表
# ══════════════════════════════════════════════════════════════
codes, labels, mult, ring = ELE.codes(), ELE.labels(), ELE.multipliers(), ELE.ring()
chk("① 声明表读得到（%d 个元素码 · %d 个字 · 环 %d 条）" % (len(codes), len(labels), len(ring)),
    bool(codes) and bool(labels) and len(ring) == 6)
_named = {c: ELE.engine_label(c) for c in codes}
chk("① 每个码都给了「引擎名 or 明确不入环」（%s）" % " · ".join("%s→%r" % kv for kv in sorted(_named.items())),
    all(isinstance(v, str) for v in _named.values()))
chk("① 环是闭合的（每元素恰好被一个克、恰好克一个）",
    len({a for a, _b in ring}) == 6 and len({b for _a, b in ring}) == 6 and len(set(map(tuple, ring))) == 6)

# ══════════════════════════════════════════════════════════════
# ② 域 → 引擎（技能那条 element 真翻了名）
# ══════════════════════════════════════════════════════════════
fire = SK.skill_info("cls_berserker", "焚身")["element"]        # 域里 ELE_FIRE
ice = SK.skill_info("cls_mage", "冰棱")["element"]              # 域里 ELE_ICE
chk("② 域里的码真翻了名（焚身 ELE_FIRE → %r · 冰棱 ELE_ICE → %r）" % (fire, ice),
    fire == ELE.engine_label("ELE_FIRE") and ice == ELE.engine_label("ELE_ICE")
    and fire == "fire" and ice == "ice")
chk("② 不入环的码翻成空串（物理 / 域里那两个宪法没定义的档）",
    ELE.engine_label("ELE_PHYS") == "" and ELE.engine_label("ELE_ARCANE") == ""
    and ELE.engine_label("ELE_HOLY") == "")
try:
    ELE.engine_label("ELE_NOPE")
    bad("② 没声明过的码没抛（会静默当「无元素」）")
except KeyError:
    ok("② 没声明过的码**当场抛**（不静默当「无元素」）")

# ══════════════════════════════════════════════════════════════
# ③ 真源对账（现解析宪法 §二·五）
# ══════════════════════════════════════════════════════════════
_src = open(DOC, encoding="utf-8").read().split("\n")
_i = next(i for i, ln in enumerate(_src) if ln.startswith("## 二·五"))
_j = next(i for i in range(_i + 1, len(_src)) if _src[i].startswith("## "))
sect = "\n".join(_src[_i:_j])
_m = re.search(r"克制\s*×\s*([\d.]+)\s*被克\s*×\s*([\d.]+)\s*中性\s*×\s*([\d.]+)", sect)
doc_mult = [float(x) for x in _m.groups()] if _m else []
chk("③ 真源三档倍数逐字对上（文档 %s vs 表 %s）" % (doc_mult, [mult["strong"], mult["weak"], mult["neutral"]]),
    doc_mult == [mult["strong"], mult["weak"], mult["neutral"]])

_arrow = re.search(r"六元素环\s+(.+→.+)$", sect, re.M)
_verbs = re.search(r"^\s*(.+?·.+?·.+)$", sect, re.M)
_l2e = {v: k for k, v in labels.items()}
_seq = [x.strip() for x in _arrow.group(1).split("→")] if _arrow else []
# ★ 环的**方向**一律以箭头那一行为准（真源自带那句「每元素克一个、被一个克，闭合」正好对上）：
_doc_pairs = [(_l2e.get(a), _l2e.get(b)) for a, b in zip(_seq[:-1], _seq[1:])]
chk("③ 表里的 ring == 真源那一行（箭头序 %s）" % (_doc_pairs,), [tuple(x) for x in ring] == _doc_pairs)
# 口诀那一行（「火融冰 · 冰凝水 · 水导电 …」）只用来**核字**：真源在它那儿用同义字
# （雷写成「电」，见 elements.json 的 labels_alt）——方向的读法不取它。
_alt = {c for v in ELE.labels_alt().values() for c in v}
_segs = [p.strip() for p in (_verbs.group(1).split("·") if _verbs else [])]
_bad_seg = []
for (a, b), seg in zip(zip(_seq[:-1], _seq[1:]), _segs):
    _alts_b = set(ELE.labels_alt().get(_l2e.get(b) or "", []))
    if len(seg) < 3 or seg[0] != a or seg[-1] not in ({b} | _alts_b):
        _bad_seg.append((seg, a, b))
chk("③ 口诀逐句与箭头环对得上（%d 句；其中同义字 %s 真被用到）" % (len(_segs), "".join(sorted(_alt))),
    not _bad_seg and any(seg[-1] in _alt for seg in _segs),
    ("对不上：%s" % (_bad_seg[:3],)) if _bad_seg else "")
_want_weak = [a for a, b in _doc_pairs if b == ELE.monster_element(MID)]
chk("③ 环里的字 == labels 里的字（%s）" % "".join(labels.values()),
    set(_seq[:-1]) == set(labels.values()))
_res_line = max(sect.split("\n"), key=lambda ln: ln.count("res_"))
_res = {m for m in re.findall(r"res_([a-z]+)", _res_line) if m != "xxx"}
chk("③ 表里那六个名都在真源「元素抗性」那一行里（%s）" % sorted(_res), set(labels) <= _res and len(_res) == 8,
    "真源是八元素 · 表里只声明环内六个（域里那两个码不在宪法那八档里 —— 见 ② / _notes 待补行）")
chk("③ 样例怪那一系（%s = %s）在环里被克 ⇒ 弱点由真源反查得出" % (ELE.monster_element(MID), labels.get(ELE.monster_element(MID), "?")),
    _want_weak == list(ELE.sample_fields(MID).get("element_weak") or {}))

# ══════════════════════════════════════════════════════════════
# ④ 装配期跨域对账
# ══════════════════════════════════════════════════════════════
seen = ELE.check_domain()
chk("④ 域里每个元素码都声明过（%s）" % " · ".join("%s=%d 条" % (k, len(v)) for k, v in sorted(seen.items())),
    set(seen) <= set(codes))
_sk = SK.skills()
_keep = _sk.get("SKILL_BSK_immolate")
try:
    _sk["SKILL_BSK_immolate"] = dict(_keep, element="ELE_NOPE")
    try:
        ELE.check_domain()
        bad("④ 域里塞了个没声明的码，装配期没抛（会静默按「无元素」打出去）")
    except KeyError:
        ok("④ 反证：域里塞个没声明的码 ⇒ 装配期当场抛（这就是防「表看着有、代码没消费」的常驻判据）")
finally:
    _sk["SKILL_BSK_immolate"] = _keep

# ══════════════════════════════════════════════════════════════
# ⑤⑥ 机制层真跑（直调落地 · source=None ⇒ 不掺等级压制，读数就是元素那一格）
# ══════════════════════════════════════════════════════════════
def _enemy(sample_on=True):
    """造一场真战斗，取那只样例怪 actor（`sample_on=False` = 撤掉样例的对照臂）。

    ★ fixture（`g5-flake` · 2026-09-26）：**把挨打方的闪避归零**。原先这一档靠「挑一颗恰好
    不闪的种子」（`SEED=1`）站着 —— 本波实测：换成 4242 **真红 2 条**（⑦ 两条都是"对照臂被
    闪掉 ⇒ 基线 0 ⇒ 比值判据塌成 `0 × 1.25 == 0`"）。判据本身没错，错的是它**骑在掷骰次序上**：
    别处多一次/少一次 roll（比如战斗管线被改）就会让它红成"像回归"。怪是**试桩式**的
    （无职业 ⇒ 面板不参与），所以裸写 `actor["dodge"] = 0` 就生效；**玩家那边不行**（面板是
    聚合出来的，要给玩家去闪避得走声明面 `dodge.cap`，见 `probe_resources.no_dodge()`）。
    要验闪避另有 `probe_engine_knobs` 那一档。**期望值一个字没改。**
    """
    _orig = ELE.sample_fields
    if not sample_on:
        ELE.sample_fields = lambda m: {}
    try:
        b = CB.build({"cls": "cls_mage", "level": 9, "name": "探", "uid": "u_el"}, [MID], MON, uid="u_el")
        e = b.sides[CB.ENEMY_SIDE][0]
        e["dodge"] = 0
        return b, e
    finally:
        ELE.sample_fields = _orig


b_on, e_on = _enemy(True)
b_off, e_off = _enemy(False)
chk("⑤ 样例怪 actor 身上真有那两张表（immune=%s · weak=%s）"
    % (e_on.get("element_immune"), e_on.get("element_weak")),
    e_on.get("element_immune") == [fire] and e_on.get("element_weak") == {ice: mult["strong"]})
chk("⑤ 免疫表认的键 == 技能真送进去的那个名（%r）" % fire, fire in (e_on.get("element_immune") or []))
chk("⑤ 弱点表认的键 == 技能真送进去的那个名（%r）" % ice, ice in (e_on.get("element_weak") or {}))

random.seed(SEED)
_lg_imm = []
d_imm = LD.deal_damage(b_on, None, e_on, 100, _lg_imm, element=fire)
random.seed(SEED)
_lg_ctl = []
d_ctl = LD.deal_damage(b_off, None, e_off, 100, _lg_ctl, element=fire)
chk("⑤ 免疫：同样 100 点计划伤害 ⇒ 真扣血 **0**（对照臂 = %d）" % d_ctl, d_imm == 0 and d_ctl > 0)
_tx = st.domain("texts")
_want_imm_line = _tx[BT.slots()["battle.landing.element_immune"]]["value"].replace("{name}", e_on.get("name"))
chk("⑤ 免疫那行日志**逐字** = texts 槽位渲染（%s）" % _want_imm_line, _want_imm_line in _lg_imm)
chk("⑤ 对照臂（撤掉样例）没有那行 · 也没走槽位外的机器码", not any("免疫" in x for x in _lg_ctl))

random.seed(SEED)
_lg_wk = []
d_wk = LD.deal_damage(b_on, None, e_on, 100, _lg_wk, element=ice)
random.seed(SEED)
_lg_ct2 = []
d_ct2 = LD.deal_damage(b_off, None, e_off, 100, _lg_ct2, element=ice)
chk("⑥ 弱点：伤害 == int(基线 × 真源那个倍数)（%d × %s ⇒ %d，实测 %d）"
    % (d_ct2, mult["strong"], int(d_ct2 * mult["strong"]), d_wk),
    d_ct2 > 0 and d_wk == int(d_ct2 * mult["strong"]))
_want_wk_line = _tx[BT.slots()["battle.landing.element_weak"]]["value"].replace("{name}", e_on.get("name"))
chk("⑥ 弱点那行日志**逐字** = texts 槽位渲染（%s）" % _want_wk_line, _want_wk_line in _lg_wk)
chk("⑥ 两行都**不含**元素机器名（%s）" % " / ".join(labels),
    not any(lbl in _want_imm_line + _want_wk_line for lbl in labels))

# ══════════════════════════════════════════════════════════════
# ⑦ 真战斗：放真技能（技能 → 引擎行动管线 → 落地）
# ══════════════════════════════════════════════════════════════
def _cast(cls, skill, sample_on):
    """真战斗里放一手技能，返回 (这一手对怪造成的伤害, 日志行)。"""
    _orig = ELE.sample_fields
    if not sample_on:
        ELE.sample_fields = lambda m: {}
    try:
        b = CB.build({"cls": cls, "level": 9, "name": "探", "uid": "u_el2"}, [MID], MON, uid="u_el2")
        e = b.sides[CB.ENEMY_SIDE][0]
        e["dodge"] = 0                      # ★ 同 `_enemy`：挨打方闪避归零（判据不骑在掷骰上）
        c = b.focus()
        random.seed(SEED)
        hp0 = int(e.get("hp"))
        sub, _ended, _who = b.human_act("skill", skill, c)
        return hp0 - int(e.get("hp")), [str(x) for x in (sub or [])], b.result
    finally:
        ELE.sample_fields = _orig


d_wk_on, lg_wk_on, _r1 = _cast("cls_mage", "冰棱", True)
d_wk_off, lg_wk_off, _r2 = _cast("cls_mage", "冰棱", False)
chk("⑦ 真战斗 · 弱点：冰棱打样例怪 ⇒ 伤害 == int(对照 × 倍数)（%d × %s ⇒ %d，实测 %d）"
    % (d_wk_off, mult["strong"], int(d_wk_off * mult["strong"]), d_wk_on),
    d_wk_off > 0 and d_wk_on == int(d_wk_off * mult["strong"]))
chk("⑦ 真战斗 · 弱点：那行日志真出现在战斗日志里", _want_wk_line in lg_wk_on and _want_wk_line not in lg_wk_off)

d_im_on, lg_im_on, _r3 = _cast("cls_berserker", "焚身", True)
d_im_off, lg_im_off, _r4 = _cast("cls_berserker", "焚身", False)
chk("⑦ 真战斗 · 免疫：焚身打样例怪 ⇒ 伤害 **0**（对照 %d）" % d_im_off, d_im_on == 0 and d_im_off > 0)
chk("⑦ 真战斗 · 免疫：那行日志真出现在战斗日志里", _want_imm_line in lg_im_on and _want_imm_line not in lg_im_off)
chk("⑦ 真战斗 · 这一手之外照旧打得下去（还没分出胜负 ⇒ result 为 None · 不因为元素这格崩掉）",
    all(r is None or r in ("victory", "defeat", "fled") for r in (_r1, _r2, _r3, _r4)))

# ══════════════════════════════════════════════════════════════
# ⑧ 一键撤 / 零影响
# ══════════════════════════════════════════════════════════════
_keys = [k for k in e_on if k.startswith("element_")]
chk("⑧ 样例开着：actor 上多出来的就是那两个字段（%s）" % _keys,
    sorted(_keys) == ["element_immune", "element_weak"])
chk("⑧ 撤掉样例：样例怪 actor 上一个元素字段都没有（键集 = %s）" % sorted(e_off),
    not [k for k in e_off if k.startswith("element_")])
_orig_sf = ELE.sample_fields
try:
    _a_off = CB.monster_actor(OTHER, MON[OTHER])
    ELE.sample_fields = lambda m: {}
    _a_off2 = CB.monster_actor(OTHER, MON[OTHER])
finally:
    ELE.sample_fields = _orig_sf
chk("⑧ 非样例怪（%s）两态 actor **逐字相同**" % MON[OTHER].get("name"), _a_off == _a_off2)
_saved = ELE._CACHE.get("decl")
try:
    ELE._CACHE["decl"] = dict(_saved, sample=dict(_saved["sample"], enabled=False))
    off1 = ELE.sample_fields(MID)
    ELE._CACHE["decl"] = {k: v for k, v in _saved.items() if k != "sample"}
    off2 = ELE.sample_fields(MID)
    chk("⑧ 声明表的两种撤法都生效（enabled=false → %r · 整块删掉 → %r）" % (off1, off2), off1 == {} and off2 == {})
finally:
    if _saved is None:
        ELE._CACHE.pop("decl", None)
    else:
        ELE._CACHE["decl"] = _saved

# ══════════════════════════════════════════════════════════════
# ⑨ 死槽位（声明的两条**真被引擎请求过**）
# ══════════════════════════════════════════════════════════════
from ext_combat.battle import schedule as SCH                        # noqa: E402

#: ★ 2026-09-25（P-38）：先让一个 DoT **真跳一跳**（否则下面那条「dot_tick 槽位被请求过」是假死）。
#:   顺带把一件事钉死：引擎兜底那句 `🔥 {name} 受 {key} {n} 层影响…` 里的 `{key}` 是**状态机器键**
#:   （B4-1 合入后 e2e 实测打出「受 **bleeding** 1 层影响」）—— 走槽位就是为了把它收掉。
_bd = CB.build({"cls": "cls_assassin", "level": 16, "name": "探", "uid": "u_dot"}, [MID], MON, uid="u_dot")
_ed = _bd.sides[CB.ENEMY_SIDE][0]
_cd2 = _bd.focus()
random.seed(SEED)
_sub_dot, _e_dot, _w_dot = _bd.human_act("skill", "SKILL_SHD_bleed", _cd2)
SCH.settle_landing(_bd, [], _cd2)
SCH._advance_time(_bd, 1.0, [])                                      # 首次挂：登记下一跳
_lg_dot = []
SCH._advance_time(_bd, 30.0, _lg_dot)                                # 跳一次
_dot_pre = str(_tx[BT.slots()["battle.schedule.dot_tick"]]["value"]).split("{")[0]     # 前缀现算，别手写那句
_dot_lines = [x for x in _lg_dot if _dot_pre in x]
chk("⑨-a 真放「割喉」⇒ DoT 每跳那行走**槽位**渲染（%s）" % (_dot_lines[:1] or "（没跳）"),
    bool(_dot_lines))
chk("⑨-a 那行**不含**状态机器键（%r）—— 引擎兜底会把它原样打给玩家"
    % "bleeding",
    bool(_dot_lines) and not any("bleeding" in x for x in _dot_lines))

#: ★ 2026-09-25（③ 资源渠道那一批顺带挖出来的）：引擎另两句兜底模板的**格式符是坏的**
#:   （`{left::.1f}` / `{rv::g}` 不是合法 Python 格式 ⇒ `render_or` 渲染失败就把带花括号的模板
#:   **原样**吐给玩家；`resource_lack` 那句还会漏出资源机器键）。这里各驱动一次，把两条槽位
#:   钉成「真被请求过」，并把「渲染出来的句子里没有花括号 / 没有机器键」写死。
_bc = CB.build({"cls": "cls_knight", "level": 16, "name": "探", "uid": "u_slot"}, [MID], MON, uid="u_slot")
_cc = _bc.focus()
SCH.advance(_bc, [])
_lg_s = []
_cc.setdefault("effects", {})["RES_OATH"] = {"stacks": 0, "expire": None}
_sub_a, _ea, _wa = _bc.human_act("skill", "SKILL_KNT_bulwark", _cc)          # 誓约壁垒要 40 守誓 ⇒ 资源不足那句
_lg_s += [str(x) for x in (_sub_a or [])]
SCH.settle_landing(_bc, _lg_s, _cc)
#: 冷却那句：本包技能的耗时刻数（≈110）都比 cd 长 ⇒ 真打里几乎到不了这一句（这就是它一直没人发现坏了的原因）。
#: 这里用**文档化的预检口**直调一次（`_skill_usable(…, logs=…)` 是引擎自己的判据口），把那条槽位钉成「真被请求过」。
from ext_combat.battle.actions import _skill_usable as _usable_e               # noqa: E402
_cc["cooldown"] = {"盾墙": _bc._now + 99999}
_usable_e(_bc, _cc, SK.skill_info("cls_knight", "盾墙"), logs=_lg_s)
_lack_pre = str(_tx[BT.slots()["battle.actions.resource_lack"]]["value"]).split("{")[0]
_cd_pre = str(_tx[BT.slots()["battle.actions.skill_cd"]]["value"]).split("{")[0]
_lack = [x for x in _lg_s if _lack_pre in x]
_cdl = [x for x in _lg_s if _cd_pre in x]
chk("⑨-b 资源不足那行**走槽位**（不让引擎那句坏格式符漏给玩家）：%s" % (_lack[:1] or "（没出）"),
    bool(_lack))
chk("⑨-b 冷却那行**走槽位**：%s" % (_cdl[:1] or "（没出）"), bool(_cdl))
chk("⑨-b 两句都**不含花括号 / 机器键**（引擎兜底实测会漏 `{rv::g}` 与 `RES_OATH`）",
    bool(_lack) and bool(_cdl)
    and all(("{" not in x and "}" not in x and "RES_" not in x) for x in (_lack + _cdl)))

#: ★ B4-23：还要**不含小数尾巴** —— 引擎这两句传的都是 float
#:   （`cur = float(entry.get("stacks") ...)` · `left = _cd_left_of(battle, ...)`），模板不给格式符
#:   就原样印出来（实测「现在只有 6.0 点」「再等 99999.0 刻」）。
#:   口径 = 宪法 §一「数值 = 整数显示」（与 B4-22 那一批同一把尺）。
chk("⑨-b 两句里**一个小数尾巴都不许有**（整数显示 —— 原先印「6.0 点 / 99999.0 刻」）",
    bool(_lack) and bool(_cdl)
    and all(re.search(r"\d\.\d", x) is None for x in (_lack + _cdl)))
#: 覆盖面（K61）：判据跟着一起加 —— 这一场里渲染出来的**每一条**都不许有小数尾巴，
#:   不只盯那两句（新加的槽位漏了也会红）。
chk("⑨-b 这一场渲染出来的**每一条**日志都没有小数尾巴（共 %d 条）" % len(_lg_s),
    all(re.search(r"\d\.\d", str(y)) is None for y in _lg_s))

#: ★ fix3-⑥（P2 BUG⑪）：再驱动一次**没有可攻击目标**的那一手 —— 引擎那句兜底
#:   （`battle.actions.no_target`）原先**原样上屏**：玩家在『战斗日志』尾巴上看到的就是它
#:   （「但没有可攻击的目标！」—— 没有 emoji、缩进与玩家行也不同，一看就是内部循环的收尾话）。
#:   组一场**对面没人**的仗再出一手攻击技能即可走到那一支；这里把这一格也钉成
#:   「声明的槽位真被请求过」，并写死「渲染出来的就是我们槽位里那一行」。
_bn = CB.build({"cls": "cls_assassin", "level": 16, "name": "探", "uid": "u_nt"}, [], MON, uid="u_nt")
_nt_slot = BT.slots()["battle.actions.no_target"]
_lg_nt = [str(x) for x in (_bn.human_act("skill", "SKILL_SHD_bleed", _bn.focus())[0] or [])]
_nt_line = [x for x in _lg_nt if str(_tx[_nt_slot]["value"]) in x]
chk("⑨-c 场上没有可攻击目标那一手 ⇒ 走槽位渲染（%s）—— 引擎兜底那句"
    "「但没有可攻击的目标！」不上屏" % (_nt_line[:1] or "（没出）"),
    bool(_nt_line) and not any("没有可攻击的目标" in x for x in _lg_nt))

_unused = BT.battle_text().unused()
chk("⑨ 声明的槽位（%d 条）都被引擎真请求过（unused = %r）" % (len(BT.slots()), _unused), _unused == ())

# ══════════════════════════════════════════════════════════════
# ⑩ 渲染口绝不抛（纪律：引擎那 108 行是 `except Exception: pass`）
# ══════════════════════════════════════════════════════════════
_tb = BT.battle_text()
_nope = _tb.render_or("battle.landing.nope", "兜底 {name}", name="X")
chk("⑩ 没声明过的 key ⇒ 回字符串（= 引擎兜底模板渲染，%r）" % _nope, _nope == "兜底 X")
_empty = _tb.render_or("", "", )
chk("⑩ 空 key / 空模板 ⇒ 回字符串（%r）" % _empty, isinstance(_empty, str))
_weird = _tb.render_or(BT.slots()["battle.landing.element_weak"], "兜 {name}", name=None)
chk("⑩ 声明过的 key 缺槽位 ⇒ 现渲染（不抛）：%r" % _weird, isinstance(_weird, str))
chk("⑩ 引擎兜底模板本身**带机器码槽位**（这就是为什么要走槽位：%r）"
    % "免疫{element}伤害",
    "{element}" in "💠 免疫！【{name}】免疫{element}伤害！")

print()
print("结果：%s" % ("全绿 ✓" if not fails else "有红 ✗（%d 条）" % len(fails)))
sys.exit(0 if not fails else 1)
