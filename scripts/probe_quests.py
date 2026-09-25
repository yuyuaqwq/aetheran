# -*- coding: utf-8 -*-
"""探针：quests 域 —— 结构 · 前置链 · ★ 跨域对账（giver 是真人 · map 是真图）· 奖励可算。

B3-3 加的那一组（生活职业任务 / 副业）：
  ⑪-trade 四值三处一致（28 §三 的取值 ↔ `_meta.trades` ↔ schemas/quests.schema.json 的 enum）
  ⑫ 生活任务 8 条 · 每副业 ≥3（源：21 §二「四项 × 3–5 条」）
  ⑬ ★ 16 条一条不落 + 与 21 §二 **逐条对账**（名字 · 副业 · 内容 · 奖励）—— 域里 trade 任务与
     文档那 16 条**集合相等**（少一条是多一份缺项，多一条是两处口径）
  ⑭ 副业任务都有 giver（真人），且**挂的人与 28 §四 的「挂谁」对上**（按名字对）
  ⑮ ★ 生活任务一律写了 `require`（不许落 `flags.side_*` 那条死路径）且条件逐条可验：
      kind 在三型里 · visit 落在真图真节点 · item 真存在**且真有出产渠道**（探针自己从
      采集池 / 掉落池 / 配方产出重算）· kill 指向真怪
  ⑯ 三条带最深处各有采集点（「去三条带最深处各采一次」这个动作真做得了）
  ⑰ 「副业」指令真跑（无参 · 四个带参 · 一个错参）：都有话、取不到文案的标记一个都没有
  ⑱ ★ 生活任务端到端走得通（真调 接 → 交）：条件没满足时拦住并说清缺什么；补齐后交得掉、
      奖励入档、`flags.quests` 写下 done（这把「新条目落在死路径上」那类事当场钉住）

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_quests.py
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
PLAN = os.environ.get("AST_PLAN", "C:/Users/yuyu/aetheran-plan")
sys.path.insert(0, ENGINE)
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, REPO)          # ★ P-27 顺手：经验曲线要走包内那个唯一的口（禁止手打）

from saintess_engine.package import load_stack          # noqa: E402

st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
st.install()

Q = st.domain("quests")
NPCS = st.domain("npcs")
MAPS = st.domain("maps")
MON = st.domain("monsters")
ITEMS = st.domain("items")
GA = st.domain("gathering")
DP = st.domain("drop_pools")
RC = st.domain("recipes")
TX = st.domain("texts")

#: 域里的**条目**（`_meta` 那类私有键不算条目 —— 与 content/cmds_quest.py::_quests 同口径）
QE = {k: v for k, v in Q.items() if not str(k).startswith("_")}

fails, notes = [], []
CHECKS = [0]
ok = lambda m: (CHECKS.__setitem__(0, CHECKS[0] + 1), print("  ✓ " + m))
bad = lambda m: (fails.append(m), CHECKS.__setitem__(0, CHECKS[0] + 1), print("  ✗ " + m))

print("探针：quests 域（任务与委托）")
print("  ✓ quests 域读得到  —— %d 条" % len(QE))

# ① 三类齐全 + 数量
for kind, want in (("主线", 12), ("支线", 18), ("悬赏", 3), ("生活", 8)):
    n = len([v for v in QE.values() if v["kind"] == kind])
    (ok if n == want else bad)("%s %d 条（应 %d）" % (kind, n, want))

# ② 必填字段
REQ = ("name", "kind", "giver", "map", "min_level", "objective", "reward_exp", "reward_gold")
miss = [k for k, v in QE.items() if any(f not in v for f in REQ)]
(ok if not miss else bad)("必填字段齐全（缺 %s）" % (miss or "无"))

# ③ ★ 跨域：giver 是真 NPC
bad_giver = sorted({v["giver"] for v in QE.values() if v["giver"] not in NPCS})
(ok if not bad_giver else bad)("★ giver 都是真 NPC（坏 %s）" % (bad_giver or "无"))

# ④ ★ 跨域：map 是真地图
bad_map = sorted({v["map"] for v in QE.values() if v["map"] not in MAPS})
(ok if not bad_map else bad)("★ map 都是真地图（坏 %s）" % (bad_map or "无"))

# ⑤ 主线前置链串得起来（q_main_N.need == q_main_{N-1}）
main = sorted([(k, v) for k, v in QE.items() if v["kind"] == "主线"], key=lambda x: x[1]["order"])
chain_bad = []
for i, (k, v) in enumerate(main):
    want = None if i == 0 else main[i - 1][0]
    if v.get("need") != want:
        chain_bad.append(k)
(ok if not chain_bad else bad)("主线前置链完整（12 条首尾相接；坏 %s）" % (chain_bad or "无"))

# ⑥ 主线等级递增
lvs = [v["min_level"] for _, v in main]
(ok if lvs == sorted(lvs) else bad)("主线等级递增  —— %s" % lvs)

# ⑦ ★ 每条主线都有「认知推进」和「钩子」
no_ins = [k for k, v in main if not v.get("insight")]
no_hook = [k for k, v in main if not v.get("hook")]
(ok if not no_ins and not no_hook else bad)(
    "★ 每条主线都有认知推进与钩子（缺 insight %s / hook %s）" % (no_ins or "无", no_hook or "无"))

# ⑧ ★ 奖励可复算（经验 = 等级² × 40 × 系数，钱 = 等级 × 系数）
#   ★ P-27 顺手：这条曲线**不再手打** —— 走包内唯一那个口 `cmds_ast.exp_need`
#     （升级判定 `add_exp` 与死亡惩罚 `_wake_in_chapel` 都走它；曲线一改这里自动跟着变）。
from content.cmds_ast import exp_need                    # noqa: E402
recalc = []
for k, v in QE.items():
    if v["kind"] == "主线":
        e, g = int(exp_need(v["min_level"]) * 0.33), int(v["min_level"] * 10)
        if v["reward_exp"] != e or v["reward_gold"] != g:
            recalc.append(k)
(ok if not recalc else bad)("★ 主线奖励可复算（奖励 = 等级函数，不手打；坏 %s）" % (recalc or "无"))

# ⑨ 交付文案不为空（三段式的第三段）
no_deliver = [k for k, v in QE.items() if not v.get("deliver_text")]
(ok if not no_deliver else bad)("每条都有交付文案（缺 %s）" % (no_deliver or "无"))

# ⑩ 解锁指向的东西真实存在（怪 / 图）
bad_unlock = []
for k, v in QE.items():
    for u in v.get("unlock") or []:
        if u in ("belt_north", "belt_east", "belt_west", "windmill_town", "old_watchtower"):
            if u not in MAPS:
                bad_unlock.append((k, u))
        elif u.startswith("boss_"):
            if not any(m.get("role") == "boss" for m in MON.values()):
                bad_unlock.append((k, u))
(ok if not bad_unlock else bad)("解锁指向真实存在（坏 %s）" % (bad_unlock or "无"))

# ══════════════════════════════════════════════════════════════
# ⑪–⑱ B3-3 生活职业任务（副业）—— 真源：28_生活职业任务_设计_v1.md · 21_长期目标层_v1.md §二
#      ★ 探针**自己**从两份文档解析（走生成器的同一个解析口，不另写镜像表），不信域的自述。
# ══════════════════════════════════════════════════════════════
import rebuild_prof_quests as RP                                          # noqa: E402

doc_trades = RP.parse_trade_values()
doc_old8, doc_new8 = RP.parse_doc28()
doc21 = RP.parse_doc21()
meta_trades = [t.get("trade") for t in ((Q.get("_meta") or {}).get("trades") or [])]
sch = json.load(io.open(os.path.join(REPO, "schemas", "quests.schema.json"), encoding="utf-8"))
sch_enum = ((sch.get("patternProperties") or {}).get("^q_[a-z0-9_]+$") or {}).get("properties", {}) \
    .get("trade", {}).get("enum")

# ⑪ 四值三处一致
(ok if doc_trades == meta_trades == sch_enum else bad)(
    "★ 副业四个取值三处一致（28 §三 %s ＝ _meta.trades %s ＝ schema enum %s）"
    % (doc_trades, meta_trades, sch_enum))

# ⑫ 生活任务条数 + 每副业 3–5 条
trade_q = {k: v for k, v in QE.items() if v.get("trade")}
per = {}
for v in trade_q.values():
    per[v["trade"]] = per.get(v["trade"], 0) + 1
shape_bad = [t for t in doc_trades if not (3 <= per.get(t, 0) <= 5)]
(ok if len(trade_q) == 16 and not shape_bad else bad)(
    "★ 生活职业任务 16 条 · 每副业 3–5 条（实测 %s）" % per)

# ⑬ ★ 16 条一条不落 + 与 21 §二 逐条对账（名字 · 副业 · 内容 · 奖励）
def _norm(s):
    return str(s or "").replace("★", "").replace(" ", "").strip()


def _lcs(a, b):
    row = [0] * (len(b) + 1)
    best = 0
    for ca in a:
        prev, row = row, [0] * (len(b) + 1)
        for j, cb in enumerate(b, 1):
            row[j] = prev[j - 1] + 1 if ca == cb else 0
            best = max(best, row[j])
    return best


def _recon(a, b):
    """奖励对账：归一（去 ★ / 空格）后互相包含，或最长公共子串 ≥ 4 字。

    为什么不是逐字相等：域里那 8 条老支线的交付物是从 24 §二 落的（21 §二 与它
    「奖励一字不差」指的是那两份文档，域里的写法略有出入 —— 例：域「固定座位（buff 时长
    +50%）」vs 文档「客栈有个固定座位（增益 buff 时长 +50%）」）。规则写在明面上，逐条打印。
    """
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return False
    return a in b or b in a or _lcs(a, b) >= 4


doc16, recon_lines, notfound, mismatch, wording = [], [], [], [], []
new_ids = {qid for qid, _n, _t, _p, _r, _w in doc_new8}
for trade, _what, rows in doc21:
    for name, content, reward in rows:
        doc16.append(name)
        hit = [(k, v) for k, v in trade_q.items() if v["name"] == name]
        if len(hit) != 1:
            notfound.append((name, len(hit)))
            continue
        k, v = hit[0]
        why = []
        if v["trade"] != trade:
            why.append("副业 %s≠文档 %s" % (v["trade"], trade))
        if _norm(v["objective"]) != _norm(content):
            # 设计真源要的是「名字 + 奖励」两栏对账；「内容」列两份文档本就措辞有出入
            #   （24 §二 与 21 §二 是同一批人的两稿）—— 所以：**新 8 条**必须逐字一致，
            #   老的 8 条只印出来给人看，不判红（免得为了让它绿去改老条目的 objective）。
            if k in new_ids:
                why.append("内容「%s」vs 文档「%s」" % (v["objective"], content))
            else:
                wording.append("%s：「%s」vs「%s」" % (name, v["objective"], content))
        if not _recon(v.get("deliver_text"), reward):
            why.append("奖励「%s」对不上「%s」" % (v.get("deliver_text"), reward))
        if why:
            mismatch.append((name, why))
        recon_lines.append("%s → %s" % (name, v.get("deliver_text")))
extra = [v["name"] for k, v in trade_q.items() if v["name"] not in doc16]
(ok if len(doc16) == 16 and not notfound and not mismatch and not extra else bad)(
    "★ 与 21 §二 逐条对账（16 条 · 名字/副业/奖励；缺 %s · 不符 %s · 多出 %s）"
    % (notfound or "无", mismatch or "无", extra or "无"))
if wording:
    print("  · 老 8 条「内容」列措辞的出入（两份文档的两稿 · 不判红 · %d 条）：%s" % (len(wording), wording))
print("  · 对账逐条：%s" % " ｜ ".join(recon_lines))

# ⑭ 副业任务都有 giver（真人）· 且与 28 §四 的「挂谁」对上
giver_bad = sorted({v["giver"] for v in trade_q.values() if v["giver"] not in NPCS})
person_bad = []
for qid, name, _t, _prose, _reward, who in doc_new8:
    v = QE.get(qid) or {}
    if (NPCS.get(v.get("giver")) or {}).get("name") != who:
        person_bad.append((qid, who, (NPCS.get(v.get("giver")) or {}).get("name")))
(ok if not giver_bad and not person_bad else bad)(
    "★ 副业任务都有真 giver（坏 %s），且挂的人与 28 §四 的「挂谁」一致（坏 %s）"
    % (giver_bad or "无", person_bad or "无"))

# ⑮ ★ 生活任务一律写了 require，且条件逐条可验（出产渠道由本探针自己重算）
produced = set()
for g in GA.values():
    for e in (g.get("pool") or []):
        produced.add(str(e.get("out")))
for p_ in DP.values():
    for e in (p_.get("entries") or []) + (p_.get("pool") or []):
        produced.add(str(e.get("out")))
for r in RC.values():
    if r.get("out"):
        produced.add(str(r["out"]))

no_req = sorted(k for k, v in trade_q.items() if not (v.get("require")))
cond_bad = []
for k, v in trade_q.items():
    reqs = v.get("require")
    reqs = [reqs] if isinstance(reqs, dict) else list(reqs or [])
    if not reqs:
        continue
    for r in reqs:
        kind = r.get("kind")
        if kind == "visit":
            m = MAPS.get(str(r.get("map")))
            if not m or str(r.get("node")) not in [n["id"] for n in (m.get("nodes") or [])]:
                cond_bad.append((k, "visit", r.get("map"), r.get("node")))
        elif kind == "item":
            iid = str(r.get("item"))
            if iid not in ITEMS and not (iid.startswith("unid_") and iid in DP):
                cond_bad.append((k, "item-不存在", iid))
            elif iid not in produced:
                cond_bad.append((k, "item-没有出产渠道", iid))
        elif kind == "kill":
            if str(r.get("monster")) not in MON:
                cond_bad.append((k, "kill", r.get("monster")))
        else:
            cond_bad.append((k, "认不出的 kind（fail-closed 会把这条任务卡死）", kind))
new_no_req = sorted(k for k in no_req if k in new_ids)
(ok if not new_no_req and not cond_bad else bad)(
    "★ 本批新 8 条一律写了 require（没写的 %s）· 条件逐条可验 / 要的东西真有出产渠道（坏 %s）"
    % (new_no_req or "无", cond_bad or "无"))


def _cond_str(v):
    """条件写成一行（给人看的）—— 出产渠道的出处也顺手带出来。"""
    reqs = v.get("require")
    reqs = [reqs] if isinstance(reqs, dict) else list(reqs or [])
    out = []
    for r in reqs:
        if r.get("kind") == "visit":
            m = (MAPS.get(str(r.get("map"))) or {})
            nd = next((n.get("name") for n in (m.get("nodes") or []) if n["id"] == r.get("node")), r.get("node"))
            out.append("去过「%s」" % nd)
        else:
            iid = str(r.get("item") or r.get("monster"))
            nm = (ITEMS.get(iid) or {}).get("name") or (DP.get(iid) or {}).get("name") or iid
            src = [g["name"] for g in GA.values() if iid in [str(e.get("out")) for e in (g.get("pool") or [])]]
            src += [p_["label"] for p_ in DP.values() if iid in [str(e.get("out")) for e in (p_.get("entries") or [])]]
            out.append("手上有「%s」×%d（出处：%s）" % (nm, int(r.get("n") or 1), " / ".join(src[:2]) or "配方产出"))
    return " ＋ ".join(out) or "（无条件）"


print("  · 人话 → 条件（本批新 8 条 · 逐条过目）：")
for qid in sorted(new_ids, key=lambda x: QE[x]["order"]):
    print("      %s %s「%s」→ %s" % (qid, QE[qid]["name"], QE[qid]["objective"], _cond_str(QE[qid])))

# ⑮-b（备注 · 不判红）★ P-25 §② 的活口：**没写 require 的支线今天交不掉**
#      （`_obj_ok` 对没写 require 的支线去看 `flags.side_<名字>` —— 那个键仓库里没有任何地方写）
dead = sorted(k for k, v in QE.items() if v["kind"] == "支线" and not v.get("require"))
notes.append("P-25 §②（未收口 · 不在本批范围）：今天仍有 %d 条支线**交不掉** —— %s；"
             "其中 %d 条属本批 16 条（%s）—— 「强化到 +3」「做三道菜」这两个动作没有条件形状（只有 "
             "visit/kill/item 三型），要新形状得单独一批 + 鱼鱼点头"
             % (len(dead), dead, len([k for k in dead if k in trade_q]),
                [k for k in dead if k in trade_q]))

# ⑯ ★ 三条带最深处各有采集点（「去三条带最深处各采一次」这个动作真做得了）
deep = RP._deepest_nodes(MAPS)
deep_bad = []
for mid, nd in deep:
    pts = [k for k, g in GA.items() if g.get("subarea") == nd]
    if not pts:
        deep_bad.append((mid, nd))
(ok if not deep_bad else bad)(
    "★ 三条带最深处 %s 各有采集点（空的 %s）" % ([(m, n) for m, n in deep], deep_bad or "无"))

# ⑰ 「副业」指令真跑（无参 · 四个带参 · 一个错参）
from content import cmds_quest as CQ                                      # noqa: E402
from content import cmds_ast as CA                                        # noqa: E402

MISSING = "[MISSING TEXT"


class _E:
    """实现体只要 env.text + env.save()。"""

    def __init__(self, text=""):
        self.text = text

    def save(self):
        pass


def _drive(fn, p, text=""):
    out = []

    async def go():
        async for line in fn(_E(text), None, "u_q", p):
            out.append(line)

    asyncio.run(go())
    return out


def _player(**kw):
    p = dict(CA.DEFAULT_PLAYER)
    p.update(kw)
    return p


cases = [("副业", ""), ("副业 采集", "采集"), ("副业 垂钓", "垂钓"), ("副业 烹饪", "烹饪"),
         ("副业 强化", "强化"), ("副业 打铁", "打铁")]
trade_out, trade_bad, miss_bad = {}, [], []
for label, arg in cases:
    out = _drive(CQ.trade, _player(level=5), label)
    trade_out[label] = out
    if not out or any(MISSING in ln for ln in out):
        miss_bad.append(label)
    if arg in doc_trades:
        rows = [ln for ln in out if ln.startswith("  ")]      # 带参那屏：抬头 + 每一条一行 + 尾注
        if len(rows) < per.get(arg, 0):
            trade_bad.append((label, len(rows), per.get(arg)))
head = trade_out["副业"]
per_line = sum(1 for ln in head if any(ln.strip().startswith(t) for t in doc_trades))
(ok if not miss_bad and not trade_bad and per_line == 4 else bad)(
    "★ 「副业」真跑：无参那屏四个副业各一行（实测 %d 行）· 四个带参都列得出那条线 · 错参回人话"
    "（取不到文案 %s · 带参异常 %s）" % (per_line, miss_bad or "无", trade_bad or "无"))
print("  · 打样：%s" % " ｜ ".join("%s → %s" % (lb, (trade_out[lb][0][:30] if trade_out[lb] else "(空)"))
                                  for lb, _a in cases))

# ⑱ ★ 生活任务端到端走得通（接 → 交 · 条件拦住 → 补齐 → 交掉）
qid = doc_new8[0][0]
order = QE[qid]["order"]
p1 = _player(level=5)
acc = _drive(CQ.quest_accept, p1, "接 %d" % order)
blocked = _drive(CQ.quest_deliver, dict(p1), "交 %d" % order)
reqs = QE[qid].get("require") or []
reqs = [reqs] if isinstance(reqs, dict) else reqs
p2 = _player(level=5, gold=0, exp=0, foot={"nodes": {("%s:%s" % (r["map"], r["node"])): 1
                                                   for r in reqs if r.get("kind") == "visit"}},
             bag={r["item"]: max(1, int(r.get("n") or 1)) for r in reqs if r.get("kind") == "item"},
             flags={"quests_active": [qid]})
paid = _drive(CQ.quest_deliver, p2, "交 %d" % order)
done_ok = (p2.get("flags") or {}).get("quests", {}).get(qid, {}).get("done") is True
taken_ok = qid in ((p1.get("flags") or {}).get("quests_active") or []) and any(QE[qid]["name"] in ln for ln in acc)
(ok if taken_ok and any("还没做完" in ln for ln in blocked)
 and not (p1.get("flags") or {}).get("quests_done")
 and any("交了" in ln for ln in paid) and qid in (p2.get("flags") or {}).get("quests_done", [])
 and p2.get("exp") == QE[qid]["reward_exp"] and p2.get("gold") == QE[qid]["reward_gold"] and done_ok else bad)(
    "★ 生活任务端到端（%s · 编号 %d）：接得下（%s）→ 条件没满足时拦住「%s」→ 补齐后交掉"
    "（经验 +%d · 铜板 +%d · flags.quests 写下 done=%s）"
    % (QE[qid]["name"], order, taken_ok, (blocked[0][:14] if blocked else "?"),
       QE[qid]["reward_exp"], QE[qid]["reward_gold"], done_ok))

for n in notes:
    print("  · " + n)

print()
print("判据 %d 条：%s" % (CHECKS[0], "全绿 ✓" if not fails else "有红 ✗（%d 条）" % len(fails)))
sys.exit(1 if fails else 0)
