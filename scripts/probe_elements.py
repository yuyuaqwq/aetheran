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
  ⑨ 文案口全量对账（★ 2026-09-27 换向：声明从「只顶掉 8 条」铺到**全量 59 条**）：
     ⑨-g 逐条真驱动一遍 · ⑨-1 静态双向（声明集合 == 引擎键化调用点集合）· ⑨-2 命名派生式
     · ⑨-3 驱动到的每一条都命中槽位 · ⑨-4 未驱动清单 == 登记表（7 条，逐条写明够不着的原因）
     · ⑨-a 顺带钉死「DoT 那行不含状态机器键」（引擎兜底会打出 `bleeding`）
     · ⑨-d ★ fix-a-screen（2026-09-27）：格挡后那条（`battle.landing.blocked_amount`）也走槽位
       —— 引擎兜底那句是全屏**唯一**一处半角括号，这一屏一个半角括号都不许有
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
import types

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
from ext_combat.battle.actors import DEFEND_TAG, open_window         # noqa: E402
from ext_combat.battle import game_config as GC                      # noqa: E402  容器收口第2批
_ABS = st.optional_submodule("absorb")                               # noqa: E402  吸收型两态门

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
#  ★ P0-1：期望值改**现渲染**（引擎 `safe_format` + 这条 cue 真拿到的 t）——
#    原先 `.replace("{name}", …)` 是手填，填不到 `{t:.0f}` ⇒ 期望里留着字面量 `【{t:.0f} 刻】`
#    （战斗时间轴 P0-1 之后暴露的）。判据只加强：多一个占位符就红。
def _render_line(cue_key, _battle=None, **slots):
    """按 texts 那一格 + 引擎 `safe_format` **现渲染**出期望那一行。
    ★ 时刻 `t` 取**给的那一场**的钟（`_battle` 或外层 `b_on`）—— 战斗时间轴 P0-1 之后
      每一行都带刻 ⇒ 拿别的场次的期望来比必然对不上（那正是 ⑦ 两条红的原因）。"""
    tpl = _tx[BT.slots()[cue_key]]["value"]
    from saintess_engine.text import safe_format
    b = _battle if _battle is not None else b_on
    s = safe_format(tpl, dict(slots, t=float(getattr(b, "_now", 0) or 0)))
    if "{" in s:                      # 还有没填上的占位符 ⇒ 当场抛（不许拿半成品当期望）
        raise AssertionError("槽位 %s 渲染后仍有占位符：%r" % (cue_key, s))
    return s


def _body_of(cue_key, **slots):
    """槽位模板渲染成「**正文那一行**」：时刻那一格也归一化成 `【…】`。

    ★ 与 `_has_cue_line` 同一口径：两侧都把 `【…】` 换成同一个占位 ⇒ 比的是**正文**，
      时刻那一格的**合法性**由 `_TS_RE` 单独钉（见那里）。
    """
    tpl = _tx[BT.slots()[cue_key]]["value"]
    from saintess_engine.text import safe_format
    s = safe_format(tpl, dict(slots, t=0))
    return re.sub(r"【[^】]*】", "【…】", s)


#: 时刻那一格的**合法形态**（真源 26_ §三 优化 1 逐字：`【N 刻】`）。
_TS_RE = re.compile(r"【\d+ 刻】")


def _has_cue_line(lines, body):
    """日志里有没有**那一行**：正文逐字对 + **时刻那一格必须存在且合法**。

    ★ 为什么不能两侧都归一化成 `【…】`：那样「时刻被抠掉」也判过绿（实测反证：
      把那一行的 `【38 刻】` 去掉，判据照样过）。⇒ 时刻单独用 `_TS_RE` 钉住，
      正文比对时**保留**时刻那一格本身（只把别的【…】换掉）。
    """
    for ln in lines:
        s = str(ln)
        if not _TS_RE.search(s):
            continue                      # 时刻格缺失 / 不合法 ⇒ 不算这一行
        if re.sub(r"【[^】]*】", "【…】", s) == body:
            return True
    return False


_want_imm_line = _render_line("battle.landing.element_immune", name=e_on.get("name"))
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
_want_wk_line = _render_line("battle.landing.element_weak", name=e_on.get("name"))
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
#  ★ P0-1：战斗时间轴之后，**时刻那一格是「cue 发出那一刻」**（实测：手末 _now=57，
#    而那行印的是 38）⇒ 判据不能拿某一刻去硬比。改成**按槽位取正文那一段**去对：
#    模板剔掉 `{t:.0f}` 那一格后余下的正文必须**逐字**出现在这一场日志里，对照臂不许有。
#    ★ 判据只加强：正文逐字 + 时刻那一格仍是合法的 `【N 刻】`（不许缺）。
_wk_body = _body_of("battle.landing.element_weak", name=e_on.get("name"))
chk("⑦ 真战斗 · 弱点：那行日志真出现在战斗日志里（且对照臂没有）",
    _has_cue_line(lg_wk_on, _wk_body) and not _has_cue_line(lg_wk_off, _wk_body))

d_im_on, lg_im_on, _r3 = _cast("cls_berserker", "焚身", True)
d_im_off, lg_im_off, _r4 = _cast("cls_berserker", "焚身", False)
chk("⑦ 真战斗 · 免疫：焚身打样例怪 ⇒ 伤害 **0**（对照 %d）" % d_im_off, d_im_on == 0 and d_im_off > 0)
_im_body = _body_of("battle.landing.element_immune", name=e_on.get("name"))
chk("⑦ 真战斗 · 免疫：那行日志真出现在战斗日志里（且对照臂没有）",
    _has_cue_line(lg_im_on, _im_body) and not _has_cue_line(lg_im_off, _im_body))
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
# ⑨ 文案口：驱动那几条已知要顶掉的（⑨-a..⑨-f）+ 全量对账（⑨-g 与 ⑨-1..⑨-4）
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
#: ★ 2026-09-29（P0-1 收口 · aep0）：取**前缀**再匹配，不拿整条模板去 `in` 一条已渲染的行。
#:   本轮给这一格补了【N 刻】（`⚠️【{t:.0f} 刻】场上没有能打的了 …`）⇒ 渲染出来的那行
#:   里 `{t:.0f}` 已被**填成刻数**，整条模板（含花括号）永远不是任何一行的子串 ⇒ 原写法
#:   必然匹配不上（实测红：⑨-c「（没出）」）。
#:   ★ 判据一个字没动 —— 它保护的东西（这一格**真被引擎请求过** + 引擎兜底那句不上屏）
#:     与「怎么找那一行」无关；同段 `_ctl_pre` 早就是这个写法，这里只是对齐它。
_nt_pre = str(_tx[_nt_slot]["value"]).split("{")[0]     # 前缀现算，别手写那句
_nt_line = [x for x in _lg_nt if _nt_pre in x]
chk("⑨-c 场上没有可攻击目标那一手 ⇒ 走槽位渲染（%s）—— 引擎兜底那句"
    "「但没有可攻击的目标！」不上屏" % (_nt_line[:1] or "（没出）"),
    bool(_nt_line) and not any("没有可攻击的目标" in x for x in _lg_nt))

#: ★ 2026-09-27（夜班试玩 w3 · 修）：本波新声明的一条 —— 控制消费那句
#:   （`battle.core.controlled`）。引擎那行兜底会把**状态机器键**打到玩家屏
#:   （两个号实测逐字：「💫 游荡的骸骨 被【star_daze】控制，无法行动！」）⇒ 走槽位顶掉。
#:   这里真驱动一次（挂 `mode=skip` 的效果 → 轮到它 ⇒ 引擎的行动前检查把这一手整手跳过），
#:   把这一格钉成「真被请求过」，并写死「渲染出来那句不含状态机器键」—— 与 ⑨-a 同款。
_bk = CB.build({"cls": "cls_mage", "level": 2, "name": "探", "uid": "u_ctl"}, [MID], MON, uid="u_ctl")
SCH.advance(_bk, [])
_ek = (_bk.sides[CB.ENEMY_SIDE] or [None])[0]
_ek.setdefault("effects", {})["star_daze"] = {"stacks": 1, "expire": float(_bk._now) + 100.0,
                                              "mode": "skip"}
_sub_k, _end_k = _bk.actor_auto(_ek)
_lg_k = [str(x) for x in (_sub_k or [])]
_ctl_slot = BT.slots()["battle.core.controlled"]
_ctl_pre = str(_tx[_ctl_slot]["value"]).split("{")[0]                 # 前缀现算，别手写那句
_ctl_line = [x for x in _lg_k if _ctl_pre in x]
chk("⑨-d 控制型状态轮到手 ⇒ 走槽位渲染（%s）—— 引擎兜底那句会把状态机器键漏给玩家"
    % (_ctl_line[:1] or "（没出）"),
    bool(_ctl_line) and not any("star_daze" in x for x in _lg_k))
#: ★ fix-a-screen（2026-09-27 · ③）：再钉一格 —— 引擎那句 `battle.landing.blocked_amount`
#:   （兜底模板 `(格挡后 {dmg} 点伤害)` 是全屏**唯一**一处半角括号，骑士路试玩报上来的）。
#:   声明成自己的槽位之后，这一格同样得「真被引擎请求过」（⑨-3 / ⑨-4 钉着这件事），
#:   并把「渲染出来的就是我们槽位里那一行 · 这一屏一个半角括号都不许有」写死。
#:   ★ 闪避要归零得走**声明面**（`formula_skeleton_fn` 的 `dodge.cap`）：玩家 actor 的 dodge 是
#:     面板聚合出来的，裸写 `actor["dodge"] = 0` 不管用（见 `_enemy` 那条注）；骑士这一格
#:     原先靠「挑一颗恰好不闪的种子」站着 —— 判据不骑在掷骰上。
from saintess_engine import config as _CFG                            # noqa: E402
from ext_combat.battle import formulas as _F                          # noqa: E402

_sd_saved = _CFG.optional_hook("formula_skeleton_fn")
_sk_saved = dict(_F._skeleton() or {})
_sk_saved["dodge"] = dict(_sk_saved.get("dodge") or {}, cap=0.0)
_CFG.mount(formula_skeleton_fn=lambda: _sk_saved)
try:
    _bk = CB.build({"cls": "cls_knight", "level": 16, "name": "探", "uid": "u_blk"},
                   [MID], MON, uid="u_blk")
    _ck = _bk.focus()
    # ★ 2026-09-27：防御姿态**已收进状态容器**（引擎 `window_open(target, DEFEND_TAG)` 读
    #   `effects["defend"]` 窗口条目，裸 bool 兄弟字段已删）⇒ 这里必须走引擎唯一的开窗口
    #   （与 `battle.py` 的 defend 动作同款），写裸 bool 那一支**根本不开窗**、屏上是另一句。
    open_window(_ck, DEFEND_TAG)
    _lg_bk = []
    LD.deal_damage(_bk, None, _ck, 20, _lg_bk)
finally:
    _CFG.set_hook("formula_skeleton_fn", _sd_saved)
_bk_slot = BT.slots()["battle.landing.blocked_amount"]
_bk_pre = str(_tx[_bk_slot]["value"]).split("{")[0]                   # 前缀现算，别手写那句
_bk_line = [x for x in _lg_bk if _bk_pre in x]
chk("⑨-e 格挡后那行走**槽位**渲染（%s）—— 引擎兜底那句（半角括号）不上屏"
    % (_bk_line[:1] or "（没出）"), bool(_bk_line))
chk("⑨-f 那一屏里**一个半角括号都没有**（引擎兜底是全屏唯一一处半角括号；这一行全角）",
    bool(_lg_bk) and not any(("(" in str(x) or ")" in str(x)) for x in _lg_bk),
    "%r" % ([x for x in _lg_bk if ("(" in str(x) or ")" in str(x))][:1] or ""))

# ══════════════════════════════════════════════════════════════
# ⑨-g ★★ 2026-09-27（战斗文案真源补全那一批）：把声明的 **59 条**逐条驱动一遍
#
# 为什么这一段非得有：本批把 `content/rules/battle_text.json` 从「只声明要顶掉的 8 条」
# 改成「引擎键化调用点**全量 59 条**」—— 判据跟着换（见 ⑨-1..⑨-4）。而「声明过的槽位
# 真被引擎请求过」这条老规矩，今天只能靠**逐条真驱动**来满足：本段就是那一次穷举。
#
# 驱动面一律是**引擎自己的口**（`landing.deal_damage/heal_actor` · `effects` 的注册动词 ·
# `actions` 的结算函数 · `Battle.human_act`/`act`/`_do_defend`/`_do_flee` · `schedule` 的时间轴），
# **不新造内容声明**；需要「面板里本来就没有的那点数值」时挂**临时夹具**（骨架表那几格，
# 与 ⑨-e 同款，`finally` 无条件还原）—— 夹具只改这一段的进程内骨架，不改任何数据文件。
# ══════════════════════════════════════════════════════════════
from ext_combat.battle import effects as _EFg, actions as _ACg             # noqa: E402
from ext_combat.battle.actors import ActCtx as _Ctxg                      # noqa: E402


def _g_battle(uid, cls="cls_knight", lv=16, mid=MID):
    """一提把：真造一场（怪那一边闪避归零 —— 判据不骑在掷骰上）。"""
    b = CB.build({"cls": cls, "level": lv, "name": "探", "uid": uid}, [mid], MON, uid=uid)
    b.sides[CB.ENEMY_SIDE][0]["dodge"] = 0
    return b, b.focus(), b.sides[CB.ENEMY_SIDE][0]


def _g_hit(b, tgt, amount=20, **kw):
    lg = []
    LD.deal_damage(b, None, tgt, amount, lg, **kw)
    return [str(x) for x in lg]


def _g_heal(b, tgt, amount):
    lg = []
    LD.heal_actor(b, tgt, amount, lg)
    return [str(x) for x in lg]


def _g_mount(patch):
    """临时改骨架表几格（**这一段的夹具**）—— 调用方 finally 还原。"""
    saved = _CFG.optional_hook("formula_skeleton_fn")
    sk = dict(_F._skeleton() or {})
    for _k, _v in patch.items():
        sk[_k] = dict(sk.get(_k) or {}, **_v) if isinstance(_v, dict) else _v
    _CFG.mount(formula_skeleton_fn=lambda: sk)
    return saved


_g_seen = []                                        # [(引擎 key 的尾段, 屏上那几行)]


def _g(key, lines):
    _g_seen.append(("battle." + key, [x for x in lines if str(x).strip()]))


# ---- landing：承伤 / 治疗那一族 ------------------------------------
_gb, _gc, _ge = _g_battle("u_g1")
_g("landing.damage", _g_hit(_gb, _ge, 20))
_gb, _gc, _ge = _g_battle("u_g2")
_g("landing.down", _g_hit(_gb, _ge, int(_ge["hp"]) + 10))

_sd = _g_mount({"dodge": {"cap": 1.0}})             # 闪避上限临时拉满 ⇒ 必闪（判据不赌硬币）
try:
    _gb, _gc, _ge = _g_battle("u_g3")
    _ge["dodge"] = 1.0
    _g("landing.dodged", _g_hit(_gb, _ge, 20))
finally:
    _CFG.set_hook("formula_skeleton_fn", _sd)

_gb, _gc, _ge = _g_battle("u_g4")
_ge["phys_reduce"] = 0.3
_g("landing.phys_immune", _g_hit(_gb, _ge, 100, dmg_kind="phys"))
_gb, _gc, _ge = _g_battle("u_g5")
_ge["magic_reduce"] = 0.3
_g("landing.magic_resist", _g_hit(_gb, _ge, 100, dmg_kind="magi"))

_sd = _g_mount({"block": {"cap": 1.0, "reduce": 0.5}})
try:
    _gb, _gc, _ge = _g_battle("u_g6")
    _ge["block"] = 1.0
    _g("landing.block_reduce", _g_hit(_gb, _ge, 100, dmg_kind="phys"))
finally:
    _CFG.set_hook("formula_skeleton_fn", _sd)

_gb, _gc, _ge = _g_battle("u_g7", mid=OTHER)        # 对照组那只（不带样例表）—— 只吃元素抗性
_ge["elem_res"] = 0.3
_g("landing.resist_reduce", _g_hit(_gb, _ge, 100, element="fire"))

_gb, _gc, _ge = _g_battle("u_g8")
# ★ 状态容器收口第 2 批（2026-09-28 · 设计案 §1.1/§2.2）：这一条是**驱动引擎自己那个吸收读点**
#   （cue 覆盖面穷举里的一条），所以夹具得跟着引擎的形状走：
#     · 引擎还认旧 `shields` 容器（今天）⇒ 照旧写那一格（逐字同字段）
#     · 引擎改成遍历容器里**声明为 absorb 的条目**（那半落地后）⇒ 写进 `effects`，
#       并把 `absorb: true` 挂进 `EFFECT_RULES`（引擎只认**声明**，不认键名）
#   ★ 判据强度不变：两种形状下这一条都真的驱动到「吸收」那个 cue。
_g_skey = "aeth.elite_shell"
if _ABS.container_mode():
    from content.mech import _elite_absorb_rules as _EAR
    GC.load_game_rules(types.SimpleNamespace(
        EFFECT_ACTIONS=dict(GC.get_effect_actions() or {}),
        EFFECT_RULES={**(GC.get_effect_rules() or {}), **_EAR()}))
    _ge.setdefault("effects", {})[_g_skey] = {"stacks": 1, "value": 5, "expire": None}
else:
    _ge["shields"] = {_g_skey: {"value": 5, "expire_at": None, "halve": False}}
_g("landing.shield_absorb", _g_hit(_gb, _ge, 10))
_gb, _gc, _ge = _g_battle("u_g9")
_ge["effects"] = {"death_guard": {"stacks": 1}}
_g("landing.death_guard", _g_hit(_gb, _ge, int(_ge["hp"]) + 50))

_sd = _g_mount({"heal_down": {"per_stack": 0.3, "cap": 0.9}, "anti_heal": {"cap": 0.6}})
try:
    _gb, _gc, _ge = _g_battle("u_g10")
    _gc["hp"] = int(_gc["hp"]) - 50
    _gc.setdefault("effects", {})["heal_down"] = {"stacks": 1}
    _g("landing.heal_forbid", _g_heal(_gb, _gc, 30))
    _gb, _gc, _ge = _g_battle("u_g11")
    _gc["hp"] = int(_gc["hp"]) - 50
    _gc.setdefault("effects", {})["_anti_heal_pct"] = {"value": {"pct": 0.3}}
    _g("landing.heal_wound", _g_heal(_gb, _gc, 30))
finally:
    _CFG.set_hook("formula_skeleton_fn", _sd)

#: 挡刀 / 治疗分担：两个钩子都由**内容侧**声明（本包今天没有这两条机制）
#: ⇒ 这里挂探针自己的替身钩子（引擎只认回调，不认「谁替你挡」）。
_gb, _gc, _ge = _g_battle("u_g12")
_gc["guard_uid"] = "u_g12b"
_gb.sides[CB.PLAYER_SIDE].append(dict(_gc, uid="u_g12b", name="替"))
_gb.redirect_hook = lambda *a: True
_g("landing.guard_cover", _g_hit(_gb, _gc, 30))
_gb, _gc, _ge = _g_battle("u_g13")
_gc["heal_share_uid"] = "u_g13b"
_gb.sides[CB.PLAYER_SIDE].append(dict(_gc, uid="u_g13b", name="分担"))
_gb.heal_redirect_hook = lambda *a: True
_gc["hp"] = int(_gc["hp"]) - 50
_g("landing.heal_shared", _g_heal(_gb, _gc, 30))

# ---- core：Battle 自己那几句 --------------------------------------
_gb, _gc, _ge = _g_battle("u_c1")
_g("core.defend", _gb._do_defend(_Ctxg(caster=_gc, action="defend")))
_gb, _gc, _ge = _g_battle("u_c2")
_g("core.fled", _gb._do_flee(_Ctxg(caster=_gc, action="flee")))          # 这一手就把 result 置成 fled
_g("core.finished", _gb.human_act("attack", None, _gc)[0])
_gb, _gc, _ge = _g_battle("u_c3")
_gb.sides[CB.PLAYER_SIDE] = []                                           # 场上没人控 ⇒ 那句「没有可行动的玩家」
_g("core.no_actor", _gb.human_act("attack", None, None)[0])
_gb, _gc, _ge = _g_battle("u_c4")
_gc.setdefault("effects", {})["silenced"] = {"mode": "no_skill", "expire": 999999.0}
_g("core.silenced", _gb.act(_Ctxg(caster=_gc, action="skill", skill_name="盾墙"))[0])
_gb, _gc, _ge = _g_battle("u_c5")
_g("core.unknown_action", _gb.human_act("nope", None, _gc)[0])           # 内容侧 override 不认 ⇒ 引擎点名

# ---- effects：引擎注册动词直调 -------------------------------------
_gb, _gc, _ge = _g_battle("u_e1")
_lg = []
_EFg.act_apply(_gb, _gc, _ge, {"key": "bleeding", "op": "set", "amount": 3, "on": "target"}, _lg)
_g("effects.stack_set", _lg)
_lg = []
_EFg.act_consume(_gb, _gc, _ge, {"key": "bleeding", "amount": 99, "on": "target"}, _lg)
_g("effects.stack_short", _lg)
_lg = []
_EFg.act_consume(_gb, _gc, _ge, {"key": "bleeding", "amount": 1, "on": "target"}, _lg)
_g("effects.stack_spent", _lg)
_lg = []
_EFg.act_apply(_gb, _gc, _gc, {"key": "mark_x", "turns": 5}, _lg)
_g("effects.stack_active", _lg)
_lg = []
_EFg.act_apply(_gb, _gc, _gc, {"key": "mark_h", "turns": 5, "hit": {"dmg_mult": 1.2}}, _lg)
_g("effects.on_hit_ready", _lg)
_lg = []
_EFg.act_apply(_gb, _gc, _gc, {"key": "mark_b", "turns": 5, "stat": "atk", "mult": 1.2}, _lg)
_g("effects.buff_boost", _lg)
_lg = []
_EFg.act_apply(_gb, _gc, _gc, {"key": "reduce", "value": 0.4, "turns": 5}, _lg)
_g("effects.shield_pct", _lg)
_lg = []
_EFg.act_apply(_gb, _gc, _ge, {"key": "star_daze", "mode": "skip", "turns": 3, "on": "target"}, _lg)
_g("effects.stack_applied", _lg)

_gb, _gc, _ge = _g_battle("u_e2")                    # 控制免疫（引擎只认态名 `cc_immune`）
_ge.setdefault("effects", {})["cc_immune"] = {"expire": 999999.0}
_lg = []
_EFg.act_apply(_gb, _gc, _ge, {"key": "star_daze", "mode": "skip", "turns": 3, "on": "target"}, _lg)
_g("effects.immune_control", _lg)
_gb, _gc, _ge = _g_battle("u_e3")                    # 异常免疫（名单里点名了那条 DOT）
_ge["immune_dots"] = ["bleeding"]
_lg = []
_EFg.act_apply(_gb, _gc, _ge, {"key": "bleeding", "op": "add", "amount": 1, "on": "target"}, _lg)
_g("effects.immune_debuff", _lg)

_gb, _gc, _ge = _g_battle("u_e3c")                   # 净化：先真挂一个可解 DOT 再解
_lg = []
_EFg.act_apply(_gb, _gc, _ge, {"key": "bleeding", "op": "add", "amount": 1, "on": "target"}, _lg)
_lg1 = []
_EFg.act_cleanse(_gb, _gc, _ge, {}, _lg1)
_g("effects.cleansed", _lg1)
_lg2 = []
_EFg.act_cleanse(_gb, _gc, _ge, {}, _lg2)            # 第二发：身上已经没得解
_g("effects.cleanse_none", _lg2)

_lg = []
_EFg.act_shield(_gb, _gc, _gc, {"key": "sh", "value": 20, "turns": 5}, _lg)
_g("effects.shield_gain", _lg)
_lg = []
_EFg.act_damage(_gb, _gc, _ge, {"value": 5}, _lg)
_g("effects.damaged", _lg)
_gc["hp"] = int(_gc["hp"]) - 30
_lg = []
_EFg.act_heal(_gb, _gc, _gc, {"value": 10, "on": "caster"}, _lg)
_g("effects.healed", _lg)
_gb, _gc, _ge = _g_battle("u_e4")                    # 打断出招窗口
_ge["charging"] = {"unstoppable": False}
_lg = []
_EFg.act_interrupt(_gb, _gc, _ge, {}, _lg)
_g("effects.cast_broken", _lg)

# ---- actions：出手消费 / 附伤 / 吸血 / 技能那条路 -------------------
_gb, _gc, _ge = _g_battle("u_a1")                    # 一发出手把「出手消费型」那两格一起吃掉
_gc.setdefault("effects", {})["next_atk"] = {"stacks": 1, "expire": 999999.0,
                                             "hit": {"dmg_mult": 1.2, "bonus_atk_pct": 0.15,
                                                     "bonus_tag": "⚡"}}
_lg = _ACg._single_target_pipeline(_gb, _gc, _ge, {"name": "普攻", "_basic": True, "kind": "phys"}, 10)
_g("actions.effect_on", [x for x in _lg if "生效" in str(x)])
_g("actions.enchant_followup", [x for x in _lg if "附魔" in str(x)])

_gb, _gc, _ge = _g_battle("u_a2")                    # 吸血：用**纯怪**当出手者（面板直读 actor 字段）
_ge["lifesteal"] = 0.2
_ge["hp"] = int(_ge["hp"]) - 40
_lg = []
_ACg._settle_lifesteal(_gb, _ge, 100, "phys", _lg)
_g("actions.lifesteal", _lg)

_gb, _gc, _ge = _g_battle("u_a3")                    # 技能那条路：`_do_buff` 尾巴那句
_g("actions.skill_cast", _ACg.do_skill(_gb, _Ctxg(caster=_gc, action="skill", skill_name="盾墙")))
_gb, _gc, _ge = _g_battle("u_a4")                    # 治疗两支：全落住 / 溢出只补得回一部分
_gc["hp"] = int(_gc["hp"]) - 80
_gc["effects"] = {}
_g("actions.skill_heal_full",
   _ACg._do_heal(_gb, _Ctxg(caster=_gc, action="skill", skill_name="治愈"), _gc,
                 {"name": "治愈", "hp_pct": 0.02}, []))
_gb, _gc, _ge = _g_battle("u_a5")
_gc["hp"] = int(_gc["max_hp"]) - 1
_gc["effects"] = {}
_g("actions.skill_heal",
   _ACg._do_heal(_gb, _Ctxg(caster=_gc, action="skill", skill_name="治愈"), _gc,
                 {"name": "治愈", "hp_pct": 0.05}, []))

# ---- schedule：时间轴上的持续恢复（条目自带 `period`） ---------------
_gb, _gc, _ge = _g_battle("u_s1")
_gc["hp"] = int(_gc["hp"]) - 60
_gc["mp"] = int(_gc["mp"]) - 30
_gc.setdefault("effects", {})["hot"] = {"stacks": 1,
                                       "period": {"dir": "heal", "interval": 1, "heal_pct": 0.05,
                                                  "mana_pct": 0.05, "turns": 5}}
_lg = []
SCH._settle_time_effects(_gb, _lg)                   # 首过登记下一跳（与 ⑨-a 那条 DoT 同款）
SCH._advance_time(_gb, 2.0, _lg)
_g("schedule.regen_hp", [x for x in _lg if "生命" in str(x)])
_g("schedule.regen_mp", [x for x in _lg if "魔力" in str(x)])

#: 打样（看得见：59 条里这一段真驱动到的那些，屏上确实是**内容侧槽位**那一行）
chk("⑨-g 本段真驱动 %d 条引擎键化调用点（逐条屏上取样：%s）"
    % (len(_g_seen), " ｜ ".join("%s→%s" % (k.split(".", 1)[1], v[0] if v else "（没出）")
                                for k, v in _g_seen[:6])),
    len(_g_seen) >= 40)

# ══════════════════════════════════════════════════════════════
# ⑨ 文案口全量对账（★ 2026-09-27 判据换向 —— 只加强，不放松）
#
# 老判据 `unused() == ()` 是「只声明 8 条」那个时代的东西：它今天挡的其实**不是死槽位**，
# 而是「本探针没驱动过的那 48 条」—— 那 48 条里有一半要专门夹具、5 条（`battle.gauge.*`）
# 本包**今天根本没有 enemy_bar 声明**（`bar_def()` 回 {} 直接 return）⇒ 拿老判据卡，
# 等于强迫探针去编内容声明。换成的四条**全都新加**，且合起来比老那条严：
#   ⑨-1 静态双向：声明集合 == 引擎源码现扫出来的键化调用点集合（拼错 / 漏跟账当场红）
#   ⑨-2 命名：除 8 条手工槽位（CURATED）外，槽位名必须 == 派生式（防手抄漂移）
#   ⑨-3 运行时：本探针驱动到的**每一条**都命中内容侧槽位（`missing()` 里零条 `battle.*`）
#   ⑨-4 未驱动清单 == 登记表（逐条写明为什么够不着）· 条数 == 写死的锚点（两态互锁）
# ══════════════════════════════════════════════════════════════
import ast as _ast9                                                       # noqa: E402


def _engine_text_keys() -> set:
    """现扫引擎源码：**表现事件（cue）**调用点的 key 实参（字面量 `battle.*`）。

    ★ 2026-09-27（引擎侧 B1–B5 走完之后）：旧三种调用形态
      （`render_via(battle, "…")` / `render_or(text, "…")` / `Battle._t("…")`）**已从引擎删净**
      —— B5 连 `render_via` / `text_of` 两个 helper 都删了 ⇒ 再扫旧形态只会扫到 0 条、
      把 60 条声明全判成「多声明」。现在引擎侧唯一出口是
      `_cue(battle, logs, "<key>", {槽位})` ⇒ 扫它的**第 3 个位置实参**。
      （`emit` 是总线的对外别名，key 由调用方给，不在这里数。）
    """
    out = set()
    root = os.path.join(ENGINE, "extends", "ext_combat")
    for _dp, _dn, _fns in os.walk(root):
        for _fn in _fns:
            if not _fn.endswith(".py"):
                continue
            with open(os.path.join(_dp, _fn), encoding="utf-8") as _f:
                _src = _f.read()
            for _node in _ast9.walk(_ast9.parse(_src)):
                if not isinstance(_node, _ast9.Call):
                    continue
                _f2 = _node.func
                if isinstance(_f2, _ast9.Name) and _f2.id in ("_cue", "cue"):
                    _i = 2
                else:
                    continue
                _a = _node.args
                if len(_a) > _i and isinstance(_a[_i], _ast9.Constant) \
                        and isinstance(_a[_i].value, str) and _a[_i].value.startswith("battle."):
                    out.add(_a[_i].value)
    return out


#: ★ 8 条手工槽位（各自的名字是**人定的**：`COMBAT_ELEM_IMMUNE` 这一类；不跟着派生式走）
CURATED_SLOTS = {
    "COMBAT_BLOCKED_AMOUNT", "COMBAT_ELEM_IMMUNE", "COMBAT_ELEM_WEAK", "COMBAT_DOT_TICK",
    "COMBAT_SKILL_CD", "COMBAT_RES_LACK", "COMBAT_NO_TARGET", "COMBAT_CONTROLLED",
}

#: ★ ⑨-4 登记表：**本探针够不着**的那几条（逐条写清为什么 —— 第三态当场红：
#:   登记了却驱动上了 / 驱动上了却没登记 / 新声明一条没登记，三种都会让 ⑨-4 翻红）。
NEED_DRIVE = {
    "battle.landing.woken":
        "「受击打醒」要目标身上有一个 `EFFECT_RULES[k].wake_on_hit` 的状态；"
        "本包 EFFECT_RULES（`content/rules/skill_mech.json` 的 rules）今天一条都没有该字段（没有睡眠类机制）",
    "battle.actions.lifesteal":
        "吸血要面板 `lifesteal` 词条或技能 `info.lifesteal`；本包两条来源都没有"
        "（纯怪面板 `_monster_base_stats` 不带该键 · 本包 48 条技能没有一条声明吸血）",
    "battle.gauge.gain":
        "资源条（enemy_bar）本包今天**没有声明**（`game_config.mech_cfg('enemy_bar')` 回空）"
        "⇒ `bar_def()` 回 {}，`bar_gain` 直接 return（那 5 条槽位属「引擎侧通路留着、内容侧还没接」）",
    "battle.gauge.trigger": "同上（bar_def 空 ⇒ `bar_trigger` 直接 return False）",
    "battle.gauge.shaken": "同上（只有条真触发、且 `trigger_effect=skip_turn` 才走这一句）",
    "battle.gauge.phase_preserve": "同上（阶段更迭那一手，本包没有分阶段的条）",
    "battle.gauge.reflect": "同上（`passive_reflect_bar` 是挂在条机制上的被动，条没声明就挂不上）",
    # ★ 状态容器收口第 2 批（2026-09-28 · 引擎落到 main `adad98a`）新增的点位
    "battle.landing.taken_reduce":
        "承伤减免读点要容器里有条目声明了 `taken_pct`（引擎 `state_effects.taken_pct_keys`）；"
        "本包 `grep taken_pct content/` **零命中** —— 那一族今天一条都没声明"
        "（本包的承伤减伤走 `reduce_taken` 乘区那条老路，与这一族不是同一件事）⇒ 这一句永不出口",
    # ★ 2026-09-28 承伤减免两条通道**互斥**（引擎 C 车道新增点位）
    "battle.landing.taken_mult_skipped":
        "互斥判定 `_skip_event_mult` 的「跳过」那一支要求通道 A（`taken_pct` 声明且封顶后 > 0）"
        "**先**成立；本包 `grep taken_pct content/` **零命中** ⇒ 通道 A 恒 0 ⇒ 那一支永不进 ⇒ 这一句永不出口",
}

_eng_keys = _engine_text_keys()
_declared = set(BT.slots())
_undecl = sorted(_eng_keys - _declared)
_extra = sorted(_declared - _eng_keys)
chk("⑨-1 静态双向：声明的 %d 条 == 引擎 `extends/ext_combat` 里现扫出的 %d 个键化调用点 key"
    "（漏声明 %s · 多声明 %s）" % (len(_declared), len(_eng_keys), _undecl or "无", _extra or "无"),
    not _undecl and not _extra)

_bad_name = sorted("%s→%s" % (k, v) for k, v in BT.slots().items()
                   if v not in CURATED_SLOTS
                   and v != "COMBAT_" + k.split(".", 1)[1].upper().replace(".", "_"))
chk("⑨-2 命名：除 %d 条手工槽位外，槽位名一律 == 派生式 `COMBAT_<引擎 key 去 battle.> 大写点转下划线`"
    "（不合的 %s）" % (len(CURATED_SLOTS), _bad_name or "无"), not _bad_name)

_miss_eng = sorted(k for k in BT.battle_text().missing() if k.startswith("battle."))
chk("⑨-3 运行时：本探针**真驱动到**的每一条战斗日志 key 都命中了内容侧槽位"
    "（`missing()` 里零条 `battle.*`；实测 %s）" % (_miss_eng[:3] or "0 条"), not _miss_eng)

_unused = tuple(BT.battle_text().unused())
chk("⑨-4 未驱动清单 == 登记表（%d 条，逐条写明为什么本探针够不着）：%s"
    % (len(NEED_DRIVE), " · ".join(sorted(NEED_DRIVE))),
    set(_unused) == set(NEED_DRIVE) and len(_unused) == len(NEED_DRIVE),
    "实测未驱动 = %s" % (sorted(set(_unused) ^ set(NEED_DRIVE)) or "与登记表一致",))

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
