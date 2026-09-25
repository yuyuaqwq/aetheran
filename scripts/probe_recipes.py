# -*- coding: utf-8 -*-
"""探针：recipes 域（烹饪 / 强化）—— 结构 · ★ 跨域对账 · ★ 源文档复核 · ★ 两个动词真跑 + 真改面板。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_recipes.py
Python 用 3.12（3.11 假红）。
"""
from __future__ import annotations

import asyncio
import io
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
PLAN = os.environ.get("AETHERAN_PLAN", "C:/Users/yuyu/aetheran-plan")
sys.path.insert(0, REPO)
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402

FIXED = 100 * 7200 + 3600.0          # 假钟（先给个能算的；下面按 calendar 的表重算）
DB = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db")

fails = []
ok = lambda m: print("  ✓ " + m)
bad = lambda m: (fails.append(m), print("  ✗ " + m))


def chk(label, cond, extra=""):
    (ok if cond else bad)(label + (("  —— %s" % extra) if extra else ""))


st = load_stack(str(REPO), inject={"db_path": DB, "clock": lambda: FIXED})
st.install()

from content import calendar as CAL                                  # noqa: E402
from content import cmds_recipe as CR                                # noqa: E402
from content import gear as GB                                       # noqa: E402
from content import combat as CB                                     # noqa: E402

SCALE = CAL.scale_seconds()
FIXED = 100 * SCALE + (12.0 / 24.0) * SCALE
CAL.facade.bind_host(clock=lambda: FIXED)

RC = st.domain("recipes")
IT = st.domain("items")
Q = st.domain("quests")
TX = st.domain("texts")
cooks = {k: v for k, v in RC.items() if v.get("kind") == "烹饪"}
enh = {k: v for k, v in RC.items() if v.get("kind") == "强化"}
meta = RC.get("_meta") or {}
eme = meta.get("enhance") or {}
cme = meta.get("cook") or {}

print("探针：recipes 域（烹饪 / 强化）")

# ① 域与规模
chk("recipes 域读得到", bool(cooks) and bool(enh),
    "烹饪 %d 条 · 强化 %d 档 · _meta %s" % (len(cooks), len(enh), bool(meta)))

# ② 烹饪：形状（食材 2–3 样 · 三种增益 · 时长 15 分钟 · 出产是真物品）
lo, hi = cme.get("ingredients") or [0, 0]
secs = int(cme.get("seconds") or 0)
bad_shape, bad_out, bad_buff = [], [], []
for rid, v in cooks.items():
    ins = v.get("inputs") or []
    if not (int(lo) <= len(ins) <= int(hi)):
        bad_shape.append("%s 食材 %d 样" % (rid, len(ins)))
    if v.get("out") not in IT:
        bad_out.append((rid, v.get("out")))
    b = v.get("buff") or {}
    if b.get("stat") not in ("atk", "def", "hp") or int(b.get("seconds") or 0) != secs:
        bad_buff.append((rid, b.get("stat"), b.get("seconds")))
chk("★ 食材 %d–%d 样（源：05 §三）" % (lo, hi), not bad_shape, "%s" % (bad_shape or "无"))
chk("★ out 指向真物品（跨域）", not bad_out, "%s" % (bad_out or "无"))
chk("★ 增益三选一 atk/def/hp · 时长 %d 秒" % secs, not bad_buff, "%s" % (bad_buff or "无"))

# ③ 跨域：食材是真材料 + 菜的 items 条目与配方一致（双向对账）
bad_ing, bad_food = [], []
for rid, v in cooks.items():
    for e in (v.get("inputs") or []):
        if e.get("id") not in IT:
            bad_ing.append((rid, e.get("id")))
    rec = IT.get(v.get("out")) or {}
    if (rec.get("food") or {}) != {k: (v.get("buff") or {}).get(k) for k in ("stat", "pct", "seconds")}:
        bad_food.append((rid, rec.get("food"), v.get("buff")))
    if rec.get("from_recipe") != rid:
        bad_food.append((rid, "from_recipe=%s" % rec.get("from_recipe")))
chk("★ 食材都在 items 域", not bad_ing, "%s" % (bad_ing or "无"))
chk("★ 菜的 food 字段 = 配方的 buff（双向对账）", not bad_food, "%s" % (bad_food or "无"))

# ④ 具名配方对得上源文档（菌汤 ← 支线 4 · 一锅炖 ← 支线 6）
def _by_name(nm):
    for rid, v in cooks.items():
        if v.get("name") == nm:
            return rid, v
    return None, None


named = []
for nm, qid, word in (("菌汤", "q_side_04", "菌汤"), ("一锅炖", "q_side_06", "一锅炖")):
    rid, v = _by_name(nm)
    q = Q.get(qid) or {}
    named.append((nm, bool(v), (v or {}).get("learn"), word in str(q.get("deliver_text") or "")))
chk("★ 具名配方：菌汤 ← q_side_04 · 一锅炖 ← q_side_06（且委托的交付物就写着它）",
    all(a and b and c for _n, a, b, c in named), "%s" % named)

# ⑤ ★ 强化：结构 + 对着源文档重解析一遍复核（不拿域里的值自证）
s05 = io.open(os.path.join(PLAN, "06_第一阶段垂直切片", "05_玩法数值口径_v1.md"),
              encoding="utf-8", newline="").read()
s13 = io.open(os.path.join(PLAN, "06_第一阶段垂直切片", "13_装备玩法与随机性_v1.md"),
              encoding="utf-8", newline="").read()
doc_need = [int(x) for x in re.search(r"每级需求 \*\*([\d/]+)\*\*", s05).group(1).split("/")]
doc_cap = int(re.search(r"上限 \*\*\+(\d+)\*\*", s05).group(1))
doc_sure = int(re.search(r"\+(\d+) 到 \+(\d+) 必成", s05).group(2))
doc_ffrom, doc_fpct = (int(x) for x in re.search(r"\+(\d+) 起每级数值 \*\*±(\d+)%\*\*", s13).groups())

levels = sorted(int(v.get("level") or 0) for v in enh.values())
chk("强化档位 1..%d（源：05 §三 上限）" % doc_cap, levels == list(range(1, doc_cap + 1)), "%s" % levels)

bad_n, bad_rate, bad_float, bad_fee, bad_mat = [], [], [], [], []
for lv in range(1, (max(levels) if levels else 0) + 1):
    v = enh.get("rc_enh_%02d" % lv) or {}
    ins = v.get("inputs") or []
    ns = sorted(int(e.get("n") or 0) for e in ins)
    if ns != [doc_need[lv - 1]] * 2:
        bad_n.append((lv, ns, doc_need[lv - 1]))
    if len(ins) != 2:
        bad_mat.append((lv, ins))
    rate = float(v.get("rate") or 0)
    if lv <= doc_sure and rate != 1.0:
        bad_rate.append((lv, rate))
    if lv > doc_sure and (rate >= 1.0 or rate >= float((enh.get("rc_enh_%02d" % (lv - 1)) or {}).get("rate") or 0)):
        bad_rate.append((lv, rate))
    fl = float(v.get("float") or 0)
    if fl != (doc_fpct / 100.0 if lv >= doc_ffrom else 0.0):
        bad_float.append((lv, fl))
    need_n = doc_need[lv - 1]
    step = int(eme.get("fee_step") or 1)
    mat_sum = sum(float((IT.get(e["id"]) or {}).get("price") or 0) * int(e.get("n") or 0)
                  for e in ins)
    want_fee = int(round(mat_sum * int(eme.get("fee_mult") or 0) / float(step))) * step
    if int(v.get("gold") or 0) != want_fee:
        bad_fee.append((lv, v.get("gold"), want_fee, need_n))
chk("★ 每级两条材料各取源文档的 n = %s" % doc_need, not bad_n, "%s" % (bad_n or "无"))
chk("★ 两条材料齐（铁屑 + 硬骨）", not bad_mat, "%s" % (bad_mat or "无"))
chk("★ 必成到 +%d、之后递减（源：05 §三）" % doc_sure, not bad_rate, "%s" % (bad_rate or "无"))
chk("★ 浮动 +%d 起 ±%d%%（源：13 §1.2）" % (doc_ffrom, doc_fpct), not bad_float, "%s" % (bad_float or "无"))
chk("★ 费 = 材料市价合计 × %s 取整到 %s（按 items 域市价复算）"
    % (eme.get("fee_mult"), eme.get("fee_step")), not bad_fee, "%s" % (bad_fee or "无"))
chk("★ 强化加成口径 0.004/级 ⇒ 满强 +%s%%（源：旧案 §7.2）"
    % eme.get("bonus_at_cap_pct"), float(eme.get("bonus_per_level") or 0) == 0.004,
    "bonus_per_level=%s" % eme.get("bonus_per_level"))

# ⑥ 文案槽位：新加的那几条都在 texts 域（缺一条就回不出话）
need_slots = ["SYS_RECIPE_HEAD", "SYS_RECIPE_ROW", "SYS_RECIPE_LOCKED", "SYS_COOK_OK",
              "SYS_COOK_MISSING", "SYS_COOK_LOCKED", "SYS_COOK_UNKNOWN", "SYS_ENHANCE_OK",
              "SYS_ENHANCE_FAIL", "SYS_ENHANCE_CAP", "SYS_ENHANCE_MISSING", "SYS_ENHANCE_SHOP",
              "SYS_ENHANCE_NOITEM", "SYS_ENHANCE_ROW", "SYS_USE_FOOD", "SYS_USE_HEAL",
              "SYS_USE_NOT", "SYS_MONEY"]
miss = [k for k in need_slots if k not in TX]
chk("★ %d 条新文案槽位都在 texts 域" % len(need_slots), not miss, "%s" % (miss or "无"))


# ══════════════════════════════════════════════════════════════
# ★ 端到端：真调两个动词（async handler），不是看代码
# ══════════════════════════════════════════════════════════════
class E:
    """假 env（handler 只用到 .text 与 .save()）。"""

    def __init__(self, text):
        self.text = text
        self.saved = 0

    def save(self):
        self.saved += 1


async def _drain(ag):
    return [str(x) async for x in ag]


def run_ag(ag):
    return asyncio.run(_drain(ag))


IRON = (enh["rc_enh_01"].get("inputs") or [{}])[0].get("id")
BONE = (enh["rc_enh_01"].get("inputs") or [{}])[1].get("id")
WEAPON = sorted(k for k, v in IT.items() if v.get("kind") == "武器" and v.get("quality") == "普通")[0]
WNAME = IT[WEAPON].get("name")


def mk(lv_now=0, target=None, gold=None):
    """测试档：背包里带那件武器 + 下一档要的材料与钱。"""
    tgt = min(int(target or (lv_now + 1)), len(doc_need))
    n = doc_need[tgt - 1]
    fee = int((enh.get("rc_enh_%02d" % tgt) or {}).get("gold") or 0)
    p = {"name": "测试者", "cls": "cls_knight", "level": 1, "exp": 0,
         "loc": "windmill_town", "node": "wt_gate_n", "prev": [],
         "gold": (fee if gold is None else gold),
         "bag": {WEAPON: 1, IRON: n, BONE: n}, "equipped": {"weapon": WEAPON},
         "flags": {}, "codex": {}}
    if lv_now:
        p["enhance"] = {WEAPON: {"lv": lv_now, "bonus": round(0.004 * lv_now, 6)}}
    return p


# ⑦ 烹饪：真跑一遍
rid, rec = _by_name("苦叶汤")
p = mk()
for e in (rec.get("inputs") or []):
    p["bag"][e["id"]] = int(e["n"]) + 1        # 多给一份：只该扣该扣的
_env = E("烹饪 %s" % rec["name"])
lines = run_ag(CR.cook(_env, None, "u_cook", p))
ded = all(int(p["bag"].get(e["id"], 0)) == 1 for e in (rec.get("inputs") or []))
chk("★ 烹饪真跑：菜进背包（%s ×%d）· 食材按量扣（各剩 1）· 落档 %d 次"
    % (rec["out"], int(p["bag"].get(rec["out"], 0)), _env.saved),
    int(p["bag"].get(rec["out"], 0)) == int(rec.get("out_n") or 1) and ded and _env.saved >= 1,
    "%s / %s" % (p["bag"], lines[:1]))

# ⑧ 强化：真跑一遍（+1 必成）
p = mk()
lines = run_ag(CR.enhance(E("强化 %s" % WNAME), None, "u_enh", p))
e1 = (p.get("enhance") or {}).get(WEAPON) or {}
chk("★ 强化真跑：%s → +%s · 材料扣完 · 钱扣掉（%d）"
    % (WNAME, e1.get("lv"), int(p.get("gold") or 0)),
    int(e1.get("lv") or 0) == 1 and int(p["bag"].get(IRON, 0)) == 0
    and int(p["bag"].get(BONE, 0)) == 0 and int(p.get("gold") or 0) == 0,
    "%s / %s" % (e1, lines[:1]))

# ⑨ ★ 接线：强化真改面板（战斗真读的那份 = ext_combat.stats.actor_stats）
from ext_combat.battle import stats as ST                            # noqa: E402

def panel(p):
    b = CB.build(p, [], {})
    return ST.actor_stats(b, b.sides["player"][0])


base = panel(mk(lv_now=0))
plus = panel(mk(lv_now=10))
main_v = float((IT[WEAPON].get("affixes") or [{}])[0].get("v") or 0)
want = main_v * (1 + 0.004 * 10)
chk("★ 强化 +10 真进面板：atk %.3f → %.3f（主词条 %.0f × 1.04）"
    % (base.get("atk", 0), plus.get("atk", 0), main_v),
    plus.get("atk", 0) > base.get("atk", 0) and abs((plus.get("atk", 0) - base.get("atk", 0)) - main_v * 0.04) < 1e-6,
    "差 %.4f（该 %.4f）" % (plus.get("atk", 0) - base.get("atk", 0), main_v * 0.04))

# ⑩ ★ 吃菜：增益真进面板；过了时效自动失效（假钟）
hp_rid = next(k for k, v in cooks.items() if (v.get("buff") or {}).get("stat") == "hp")
dish = cooks[hp_rid]["out"]
p = mk()
p["bag"] = {dish: 1}
before = panel(p)
run_ag(CR.item_use(E("吃 %s" % IT[dish]["name"]), None, "u_eat", p))
after = panel(p)
CAL.facade.bind_host(clock=lambda: FIXED + 3600)
expired = GB.food_buff(p)
CAL.facade.bind_host(clock=lambda: FIXED)
pct = int((cooks[hp_rid]["buff"] or {}).get("pct") or 0)
chk("★ 吃 %s：血上限 %s → %s（+%d%%）· 一小时后面板回原样"
    % (IT[dish]["name"], before.get("max_hp"), after.get("max_hp"), pct),
    after.get("max_hp", 0) > before.get("max_hp", 0) and not expired
    and abs(after.get("max_hp", 0) - int(before.get("max_hp", 0) * (1 + pct / 100.0))) <= 1,
    "过期后 food_buff=%s" % (expired or "空"))


# ⑪ ★ 失败口径 + 成功率分布（都对着率表与 05 原文）
N = 2000
for tgt in (6, 10):
    step = enh["rc_enh_%02d" % tgt]
    rate = float(step.get("rate") or 0)
    fee = int(step.get("gold") or 0)
    hit, bad_rule = 0, []
    for i in range(N):
        q = mk(lv_now=tgt - 1, target=tgt)
        gold0 = int(q.get("gold") or 0)
        run_ag(CR.enhance(E("强化 %s" % WNAME), None, "u%d" % i, q))
        lv = int(((q.get("enhance") or {}).get(WEAPON) or {}).get("lv") or 0)
        if lv == tgt:
            hit += 1
            if int(q.get("gold") or 0) != gold0 - fee:
                bad_rule.append(("成了没扣钱", i))
        else:
            if int(q.get("gold") or 0) != gold0:
                bad_rule.append(("失败还扣了钱", i))
            if lv != tgt - 1:
                bad_rule.append(("失败掉了级", i))
    got = hit / float(N)
    chk("★ +%d 的成功比例对着率表（实 %.1f%% / 设 %.0f%%）" % (tgt, got * 100, rate * 100),
        abs(got - rate) <= 0.04, "样本 %d" % N)
    chk("★ +%d 失败口径：材料吃了、钱不扣、等级不掉（05 原文「失败只吃材料、不掉级」）" % tgt,
        not bad_rule, "%s" % (bad_rule[:3] or "无"))

# ⑫ ★ B3-6b-2d-b：强化白名单 = 「有 ASCII `slot` 的那些」（原按 items 的**中文** kind 六类筛）
#   ① 逐件对账：`equip_only` 收下的 = 「带 slot 的」（同名多品阶只命中排序在前的那个 ⇒ 记「收下了」）
#   ② 真跑一件**非装备**（料/钱都给够）⇒ 必须拒掉、档上不动
_ok_names, _not_names = [], []
for _iid, _rec in sorted(IT.items()):
    _got = CR._item_of_name(str(_rec.get("name") or ""), equip_only=True)
    if _rec.get("slot"):
        if _got:
            _ok_names.append(_iid)
    elif _got:
        _not_names.append(_iid)
chk("★ `equip_only` 收下的 = 「带 slot 的那些」（%d 件 · 非装备一件都没收下：%s）"
    % (len(_ok_names), _not_names or "无"), not _not_names)
_plain = next(k for k, v in sorted(IT.items()) if not v.get("slot"))
_pname = IT[_plain].get("name") or _plain
_p2 = {"name": "试", "cls": "cls_knight", "level": 1, "exp": 0, "gold": 9999,
       "bag": {_plain: 1}, "flags": {}, "codex": {}}
_l2 = run_ag(CR.enhance(E("强化 %s" % _pname), None, "u_cmp2", _p2))
chk("★ 非装备真跑「强化 %s（%s）」：拒掉（不出强化结果、档上不动）" % (_pname, _plain),
    bool(_l2) and not (_p2.get("enhance") or {}) and any(_pname in ln for ln in _l2),
    "%s / enhance=%s" % (_l2[:1], _p2.get("enhance")))

print()
print("结果：%s" % ("全绿 ✓" if not fails else "有红 ✗（%d）" % len(fails)))
sys.exit(1 if fails else 0)
