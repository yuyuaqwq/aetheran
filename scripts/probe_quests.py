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

B3-6c 加的那一组（主线三段行文归位 texts · 解 P-17 甲案）：
  ⑨（改）交付文案的取口不再直接读域字段 —— 主线走 texts 槽位，其余链条读域内字段
  ⑲ 主线 12 × 3 = 36 条槽位齐备 · 且都不是占位（「〔待填…〕」「（待写）」「（进行中：…）」）
  ⑳ ★ 12 条与 24_任务线_v1 §一 **逐条对账**（探针自己解析那份文档）：名字一致 ·
      三条行文各自落在**本条**的专名锚上（NPC / 怪 / 物 / 图 / 节点名）· 交时那一段必须命中
      「交付」栏的锚 · 不许提别的条才有的人 / 怪（串台哨兵）
  ㉑ ★ 真跑「接 <编号>」/「交 <编号>」各 12 遍：槽位里的字必须**逐字**出现在屏上
      （取不到文案的标记一个都不许有）—— 槽位 → 玩家眼睛的闭环
  ㉒ 归位总账（**不判红** · 两条批一起算）：quests 域 41 条 · 真源 = texts 123 条槽位 ·
      域里那三个内嵌字段 0 处

B3-8 加的那一组（支线 18 / 生活 8 / 悬赏 3 三段行文归位 · 同一套映射一次收完）：
  ㉓ ★ 29 条按 chain+order 都算得出**真槽位**（不是 fail-closed 哨兵）· 域里**每一条**都不是
      哨兵 · 且域名里那三个内嵌字段 `story/progress_text/deliver_text` **0 处**
      （B3-3 的生成器 `rebuild_prof_quests.py` 还会写那三个字段 —— 谁重跑它，这条当场红）
  ㉔ ★ 29 条与三份真源**逐条对账**（探针自己解析）：
      支线 = `24 §二` 的支线表（名字 · 谁给 · 步骤=objective · 奖励=hook · 三条行文落在
      步骤/奖励的锚上 · 奖励里「」的词一个不落）· 生活 = `28 §四` 新 8 条（+ `21 §二` 两稿
      对账）· 悬赏 = `24 §二` 悬赏板块 + `05 §一`（报酬区间两处一致 · 域里的钱落在区间里）
      · 串台哨兵（三段行文里只许提本条文档行出现过的人）· 悬赏三条「交时行文」逐字＝
      归位前域里那一行（玩家看到的字一个没动）
  ㉕ ★ 87 条槽位非占位（「待填 / 待写 / 〔 / （待 / 进行中」）· 无阿拉伯数字 · 无机器键 · 互不重复
  ㉖ ★ 支线 / 生活 / 悬赏 各抽一条真跑：接 / 交(没做完) / 交 —— 三拍的字逐字在屏上、奖励入档

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
#   ★ B3-6c / B3-8：取口就是 code 里那个映射（`cmds_quest._slot_of` / `_beat` · 不另写镜像表）——
#     四条链都走 texts 槽位；域里那三个内嵌字段已裁掉（㉓ 钉着「0 处」）。
from content import cmds_quest as CQ                                      # noqa: E402


def _beat_of(x, part):
    slot = CQ._slot_of(x, part)
    return (TX.get(slot) or {}).get("value") or ""


no_deliver = [k for k, v in QE.items() if not _beat_of(v, "DELIVER")]
(ok if not no_deliver else bad)("每条都有交付文案（三段式的第三段 · 主线走 texts 槽位；缺 %s）"
                                % (no_deliver or "无"))

# ⑩ 解锁指向的东西真实存在（怪 / 图）
bad_unlock = []
for k, v in QE.items():
    for u in v.get("unlock") or []:
        if u in ("belt_north", "belt_east", "belt_west", "windmill_town", "old_watchtower"):
            if u not in MAPS:
                bad_unlock.append((k, u))
        elif u.startswith("boss_"):
            if not any(m.get("role_key") == "boss" for m in MON.values()):     # ★ 机器键（keys-2）
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
        if not _recon(v.get("hook"), reward):
            why.append("奖励「%s」对不上「%s」" % (v.get("hook"), reward))
        if why:
            mismatch.append((name, why))
        recon_lines.append("%s → %s" % (name, _beat_of(v, "DELIVER")))
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

# ⑰ 「副业」指令真跑（无参 · 四个带参 · 一个错参）—— `CQ` 已在 ⑨ 那节导入
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

# ══════════════════════════════════════════════════════════════
# ⑲–㉒ B3-6c 主线三段行文归位 texts（解 P-17 甲案）
#     源：`06_第一阶段垂直切片/24_任务线_v1.md` §一（主线 12 条 · 步骤/交付/教/钩子）
#     ★ 探针**自己**解析那份文档再比（照 ⑬ 对 21 §二 那种做法），不信域的自述。
# ══════════════════════════════════════════════════════════════
import io as _io                                                          # noqa: E402
import re as _re                                                          # noqa: E402

DOC24 = os.path.join(PLAN, "06_第一阶段垂直切片", "24_任务线_v1.md")
_BLK = _re.compile(r"^###\s*主\s*(\d+)\s*·\s*(.+?)\s*$")
_FLD = _re.compile(r"^(步骤|交付|教|★\s*认知推进|钩子)\s+(.*)$")


def _parse_main24():
    """24 §一 → {order: {name, 步骤, 交付, 教, ★认知推进, 钩子, raw}}（解析不出就当场抛）。"""
    if not os.path.exists(DOC24):
        raise SystemExit("24 号文档不在：%s" % DOC24)
    out, cur = {}, None
    for ln in _io.open(DOC24, encoding="utf-8", newline="").read().split("\n"):
        m = _BLK.match(ln)
        if m:
            cur = out[int(m.group(1))] = {"name": m.group(2).split("（")[0].strip(), "raw": []}
            continue
        if cur is None:
            continue
        if ln.startswith("## ") or ln.startswith("---"):
            cur = None                    # §一 结束 / 下一节 —— 别把支线表吃进最后一块
            continue
        cur["raw"].append(ln)
        f = _FLD.match(ln.strip())
        if f:
            cur[f.group(1).replace("★ ", "★")] = f.group(2).strip()
    return out


doc24 = _parse_main24()
#: 「锚」= 块里真出现的**专名**（NPC / 怪 / 物 / 图 / 节点名）—— 用来钉「这三条行文是在说本条」
_NAMES = {str(v.get("name")) for d_ in (NPCS, MON, ITEMS) for v in d_.values() if v.get("name")}
for _mm in MAPS.values():
    _NAMES.add(str(_mm.get("name") or ""))
    for _nd in (_mm.get("nodes") or []):
        _NAMES.add(str(_nd.get("name") or ""))
_NAMES = {x for x in _NAMES if len(x) >= 2}
#: 只拿「人 / 怪」当串台哨兵（地名共享是合理的 —— 玩家本来就要到处走）
_PROPER = {str(v.get("name")) for d_ in (NPCS, MON) for v in d_.values() if v.get("name")}

mainq = {int(v["order"]): (k, v) for k, v in QE.items() if v.get("chain") == "main"}

# ⑲ 36 条槽位齐备 · 且都不是占位（「〔待填…〕」「（待写）」「（进行中：…）」）
PLACE = ("待填", "待写", "〔", "（待", "进行中")
slot_miss, slot_place = [], []
for _n in range(1, 13):
    for _part in ("STORY", "PROGRESS", "DELIVER"):
        _key = "QUEST_MAIN%02d_%s" % (_n, _part)
        _v = str((TX.get(_key) or {}).get("value") or "")
        if not _v:
            slot_miss.append(_key)
        elif any(t in _v for t in PLACE):
            slot_place.append((_key, _v[:18]))
(ok if not slot_miss and not slot_place else bad)(
    "★ 主线 36 条槽位齐备且都不是占位（缺 %s · 还是占位 %s）" % (slot_miss or "无", slot_place or "无"))

# ⑳ ★ 12 条主线按 chain+order 真取到槽位 · 与 24 §一 逐条对账（名字 / 锚 / 交付 / 不串台）
recon_bad, recon_lines = [], []
for _n in sorted(doc24):
    if _n not in mainq:
        recon_bad.append("域里没有编号 %d 的主线" % _n)
        continue
    _k, _x = mainq[_n]
    _b = doc24[_n]
    _own = sorted({a for a in _NAMES if a in "\n".join(_b["raw"])})
    _vals = {p: _beat_of(_x, p) for p in ("STORY", "PROGRESS", "DELIVER")}
    _hits = {a for a in _own if any(a in _vals[p] for p in _vals)}
    _need = min(2, len(_own))
    if _x["name"] != _b["name"]:
        recon_bad.append("主%d 名字「%s」≠ 文档「%s」" % (_n, _x["name"], _b["name"]))
    if len(_hits) < _need:
        recon_bad.append("主%d 三条行文只命中 %d/%d 个文档锚 %s" % (_n, len(_hits), _need, _own))
    _dl = {a for a in _own if a in (_b.get("交付") or "")}
    if _dl and not any(a in _vals["DELIVER"] for a in _dl):
        recon_bad.append("主%d 交时那一段没命中「交付」栏的锚 %s" % (_n, sorted(_dl)))
    _cross = sorted(a for a in _PROPER if a not in _own
                    and any(a in _vals[p] for p in _vals))
    if _cross:
        recon_bad.append("主%d 串台（提了别的条才有的人 / 怪）%s" % (_n, _cross))
    recon_lines.append("主%-2d %-7s 锚 %s" % (_n, _b["name"], "/".join(sorted(_hits))))
    if not (_b.get("步骤") and _b.get("交付") and _b.get("钩子")):
        recon_bad.append("主%d 24 号文档那块的 步骤/交付/钩子 没解析全" % _n)
(ok if len(doc24) == 12 and not recon_bad else bad)(
    "★ 主线 12 条与 24 §一 逐条对账（名字 · 三条行文落在本条的锚上 · 交时命中「交付」栏 · 不串台；"
    "坏 %s）" % (recon_bad or "无"))
for _ln in recon_lines:
    print("      %s" % _ln)

# ㉑ ★ 真跑「接 <编号>」/「交 <编号>」：槽位里的字必须**原样**出现在屏上（槽位 → 玩家眼睛的闭环）
drive_bad, drive_lines = [], []
for _n in range(1, 13):
    _k, _x = mainq[_n]
    _lv = int(_x["min_level"])
    _acc = _drive(CQ.quest_accept, _player(level=_lv), "接 %d" % _n)
    # 「没做完」的档：等级压到这条线之下（主 1 的门槛就是 1 ⇒ 用 0 —— 别拿 1 当「不够」）
    _nod = _drive(CQ.quest_deliver, _player(level=max(0, _lv - 1), flags={"quests_active": [_k]}),
                  "交 %d" % _n)
    _pay = _drive(CQ.quest_deliver, _player(level=_lv, flags={"quests_active": [_k]}), "交 %d" % _n)
    _want = {p: _beat_of(_x, p) for p in ("STORY", "PROGRESS", "DELIVER")}
    if _want["STORY"] not in _acc:
        drive_bad.append((_n, "接", _acc[:2]))
    if not any(ln.startswith("还没做完") and _want["PROGRESS"] in ln for ln in _nod):
        drive_bad.append((_n, "交(没做完)", _nod[:2]))
    if _want["DELIVER"] not in _pay:
        drive_bad.append((_n, "交", _pay[:3]))
    if any(MISSING in ln for ln in _acc + _nod + _pay):
        drive_bad.append((_n, "取不到文案", ""))
    drive_lines.append("主%-2d 接「%s…」｜ 没做完「%s…」｜ 交「%s…」"
                       % (_n, _want["STORY"][:12], _want["PROGRESS"][:10], _want["DELIVER"][:12]))
(ok if not drive_bad else bad)(
    "★ 主线 12 条真跑：接 / 交(没做完) / 交 各一遍，槽位里的字逐字在屏上（坏 %s）" % (drive_bad or "无"))
for _ln in drive_lines:
    print("      %s" % _ln)

# ㉒ 归位总账（**不判红** —— 数字登记 · 判据在 ㉓–㉖）
_lane = {}
for _k, _v in QE.items():
    _lane.setdefault(_v["chain"], []).append(_k)
notes.append("B3-6c + B3-8 归位总账：quests 域 %d 条（主线 %d / 支线 %d / 生活 %d / 悬赏 %d）—— "
             "三段行文真源唯一 = texts 的 %d 条槽位（主线 36 + 支线/生活/悬赏 87）；"
             "域里 `story` / `progress_text` / `deliver_text` 三个内嵌字段 **0 处**"
             % (len(QE), len(_lane.get("main") or []), len(_lane.get("side") or []),
                len(_lane.get("trade") or []), len(_lane.get("bounty") or []),
                3 * len(QE)))

# ══════════════════════════════════════════════════════════════
# ㉓–㉖ B3-8 支线 18 / 生活 8 / 悬赏 3 三段行文归位 texts（同一套映射 · 一次收完）
#      源：`24_任务线_v1.md §二`（支线表 + 悬赏板块）· `28 §四`（新 8 条）+ `21 §二`（奖励）
#          · `05_玩法数值口径_v1.md §一`（悬赏报酬区间）
#      ★ 探针**自己**解析那几份文档再比（照 ⑬ 对 21 §二 / ⑳ 对 24 §一 的做法），不信域的自述。
# ══════════════════════════════════════════════════════════════
DOC05 = os.path.join(PLAN, "06_第一阶段垂直切片", "05_玩法数值口径_v1.md")
_ROW_SIDE = _re.compile(r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$")
_BOUNTY_RANGE = _re.compile(r"报酬\s*(\d+)[–\-~](\d+)（普通）\s*/\s*(\d+)[–\-~](\d+)（精英）"
                            r"\s*/\s*(\d+)[–\-~](\d+)（头目）")
#: 05 §一 的那一行（同一件事的另一份写法）：`悬赏报酬 | 按目标档位：普通 **20–40** 币 · 精英 …`
_BOUNTY_RANGE05 = _re.compile(r"按目标档位：普通\s*\**\s*(\d+)[–\-~](\d+)\s*\**\s*币\s*·\s*"
                              r"精英\s*\**\s*(\d+)[–\-~](\d+)\s*\**\s*·\s*"
                              r"头目\s*\**\s*(\d+)[–\-~](\d+)\s*\**")


def _parse_side24():
    """24 §二 → (支线 rows, 悬赏板块文本)。支线 row = (序号, 名字, 谁给, 步骤, 奖励)。"""
    if not os.path.exists(DOC24):
        raise SystemExit("24 号文档不在：%s" % DOC24)
    lines = [x.rstrip("\r") for x in
             _io.open(DOC24, encoding="utf-8", newline="").read().split("\n")]
    on, rows, blk_at, stop = False, [], None, None
    for i, ln in enumerate(lines):
        if ln.startswith("## 二、"):
            on = True
            continue
        if on and ln.startswith("## 三、"):
            stop = i
            break
        if not on:
            continue
        if ln.startswith("**悬赏板**"):
            blk_at = i
            continue
        if blk_at is None:
            m = _ROW_SIDE.match(ln)
            if m and m.group(1).isdigit() and "---" not in ln:
                rows.append((int(m.group(1)), m.group(2), m.group(3), m.group(4), m.group(5)))
    blk = lines[blk_at:stop] if blk_at is not None else []
    return rows, "\n".join(blk)


side24, bounty_blk = _parse_side24()
side_rows = {r[1]: r for r in side24}
#: 悬赏报酬区间：24 §二 与 05 §一 **两处都要写着**，且必须一致（双源对账）
_b24 = _BOUNTY_RANGE.search(bounty_blk)
_b05 = _BOUNTY_RANGE05.search(_io.open(DOC05, encoding="utf-8", newline="").read()
                              if os.path.exists(DOC05) else "")
_rng = None
if _b24:
    _rng = {"普通": (int(_b24.group(1)), int(_b24.group(2))),
            "精英": (int(_b24.group(3)), int(_b24.group(4))),
            "头目": (int(_b24.group(5)), int(_b24.group(6)))}
(ok if side24 and _rng and _b05 and _b05.groups() == _b24.groups() else bad)(
    "★ 悬赏板真源：24 §二 的报酬区间 %s ＝ 05 §一 的同一条（%s）" %
    (_rng, "两处一致" if _b05 and _b24 and _b05.groups() == _b24.groups() else "对不上"))

side_q = {k: v for k, v in QE.items() if v.get("chain") == "side"}
trade_chain_q = {k: v for k, v in QE.items() if v.get("chain") == "trade"}
bounty_q = {k: v for k, v in QE.items() if v.get("chain") == "bounty"}
#: 串台哨兵只认**人**（NPC 名）—— 地名共享是合理的（支线本来就横跨三带）
_NPC_NAMES = {str(v.get("name")) for v in NPCS.values() if v.get("name")}
LANES = (("支线", "side", side_q, 18, "24 §二"), ("生活", "trade", trade_chain_q, 8, "28 §四"),
         ("悬赏", "bounty", bounty_q, 3, "24 §二 悬赏板"))

# ㉓ ★ 每一条都能按 chain + order 算出**真槽位**（不是哨兵）；域里那三个内嵌字段 0 处
slot_bad, keys29 = [], []
for _kind, _chain, _qs, _want, _src in LANES:
    for _k, _x in _qs.items():
        for _p in ("STORY", "PROGRESS", "DELIVER"):
            _s = CQ._slot_of(_x, _p)
            if str(_s).startswith("QUEST_UNMAPPED"):
                slot_bad.append((_k, _p, _s))
            elif _s not in TX:
                slot_bad.append((_k, _p, "texts 里没有 " + _s))
            else:
                keys29.append(_s)
# 另外两条链（主线 / 后面新加的）也一并钉：**域里每一条**都算得出真槽位
allq_bad = [(k, p) for k, v in QE.items() for p in ("STORY", "PROGRESS", "DELIVER")
            if str(CQ._slot_of(v, p)).startswith("QUEST_UNMAPPED")]
inline = sorted("%s.%s" % (k, f) for k, v in QE.items()
                for f in ("story", "progress_text", "deliver_text") if f in v)
(ok if not slot_bad and not allq_bad and not inline else bad)(
    "★ 29 条按 chain+order 都算得出真槽位（坏 %s）· 域里每一条都不是哨兵（坏 %s）· "
    "那三个内嵌字段 0 处（还有 %s）" % (slot_bad or "无", allq_bad or "无", inline or "无"))

# ㉔ ★ 29 条与三份真源**逐条对账**（名字 · 谁给 · 步骤/内容 · 奖励锚 · 不串台 · 悬赏报酬区间）
_side_ok, _why_side, _lines29 = 0, [], []
_doc28_new = {r[0]: r for r in doc_new8}
_doc21_r = {name: (content, reward) for _t, _w, rows in doc21 for name, content, reward in rows}


def _common(a, b):
    """最长公共子串（打印给人看用 —— 判据就是它的长度；与 ⑬ 那个 `_lcs` 同源）。"""
    a, b = _norm(a), _norm(b)
    row = [0] * (len(b) + 1)
    best = ""
    for i, ca in enumerate(a, 1):
        prev, row = row, [0] * (len(b) + 1)
        for j, cb in enumerate(b, 1):
            if ca == cb:
                row[j] = prev[j - 1] + 1
                if row[j] > len(best):
                    best = a[i - row[j]:i]
    return best


def _anchor(a, b, n=2):
    """共同片段 ≥ n 字（子串判据 —— 文案是照文档写的**行文**，不是文档的抄件 · 与 ⑳ 同款）。"""
    return len(_common(a, b)) >= n


for _kind, _chain, _qs, _want, _src in LANES:
    if len(_qs) != _want:
        _why_side.append("%s 条数 %d ≠ %d" % (_kind, len(_qs), _want))
    for _k, _x in sorted(_qs.items(), key=lambda kv: kv[1]["order"]):
        _3 = "".join(_beat_of(_x, p) for p in ("STORY", "PROGRESS", "DELIVER"))
        _dl = _beat_of(_x, "DELIVER")
        _own = [_x["name"], _x["objective"]]
        _giver = (NPCS.get(_x["giver"]) or {}).get("name") or _x["giver"]
        if _chain == "side":
            _r = side_rows.get(_x["name"])
            if not _r:
                _why_side.append("%s 不在 24 §二 支线表里" % _k)
                continue
            _n, _nm, _who, _steps, _reward = _r
            _own += [_steps, _reward]
            if _who != _giver:
                _why_side.append("%s 谁给「%s」≠ 域 giver「%s」" % (_k, _who, _giver))
            if _norm(_steps) != _norm(_x["objective"]):
                _why_side.append("%s 步骤「%s」≠ objective「%s」" % (_k, _steps, _x["objective"]))
            if _norm(_reward) != _norm(_x.get("hook")):
                _why_side.append("%s 奖励「%s」≠ hook「%s」" % (_k, _reward, _x.get("hook")))
            if not _anchor(_3, _steps):
                _why_side.append("%s 三条行文没落在「步骤」上" % _k)
            if not _anchor(_dl, _reward):
                _why_side.append("%s 交时那一段没落在「奖励」上" % _k)
            _miss = [t for t in _re.findall(r"「([^」]+)」", _reward) if t not in _3]
            if _miss:
                _why_side.append("%s 奖励里的词一个都没落：%s" % (_k, _miss))
        elif _chain == "trade":
            _r = _doc28_new.get(_k)
            if not _r:
                _why_side.append("%s 不在 28 §四 新 8 条里" % _k)
                continue
            _qid, _nm, _tr, _prose, _reward, _who = _r
            _own += [_prose, _reward]
            if _nm != _x["name"] or _tr != _x.get("trade") or _who != _giver:
                _why_side.append("%s 名字/副业/挂谁 与 28 §四 对不上（%s）" % (_k, _r))
            if _norm(_prose) != _norm(_x["objective"]):
                _why_side.append("%s 内容「%s」≠ objective「%s」" % (_k, _prose, _x["objective"]))
            if not _anchor(_3, _prose):
                _why_side.append("%s 三条行文没落在「内容」上" % _k)
            if not _anchor(_dl, _reward):
                _why_side.append("%s 交时那一段没落在「奖励」上" % _k)
            _miss = [t for t in _re.findall(r"「([^」]+)」", _reward) if t not in _3]
            if _miss:
                _why_side.append("%s 奖励里的词一个都没落：%s" % (_k, _miss))
            _a21 = _doc21_r.get(_x["name"])
            if not _a21 or not _recon(_a21[1], _reward):
                _why_side.append("%s 21 §二 奖励与 28 §四 对不上（%s）" % (_k, _a21))
        else:                                   # 悬赏档：真源是 24 §二 悬赏块 + 05 §一
            _tier = _x["name"].split("·")[-1]
            _lo, _hi = (_rng or {}).get(_tier, (0, -1))
            if not (_lo <= int(_x["reward_gold"]) <= _hi):
                _why_side.append("%s 报酬 %d 不在文档区间 %s（%s）"
                                 % (_k, _x["reward_gold"], (_lo, _hi), _x["name"]))
            if _x["name"] != "悬赏·%s" % _tier or _tier not in _x["objective"]:
                _why_side.append("%s 名字/目标与档位对不上：%s" % (_k, _x["objective"]))
        # 串台哨兵：三段行文里只许提**本条文档行里出现过的人**（谁给 / 名字 / 步骤 / 奖励）
        _doc_text = "".join(_own)
        _cross = sorted(n for n in sorted(_NPC_NAMES)
                        if n not in _doc_text and n not in (_giver,) and n in _3)
        if _cross:
            _why_side.append("%s 串台（提了别条的人）%s" % (_k, _cross))
        _side_ok += 1
        _lines29.append("%s %-9s 锚「%s」（%d 字）｜ 交「%s」" % (
            {"side": "支", "trade": "生", "bounty": "赏"}[_chain], _x["name"],
            _common(_3, "".join(_own))[:6], _lcs(_norm(_3), _norm("".join(_own))), _dl[:16]))
#: 悬赏那三条的「交时行文」= 归位前域里的 `deliver_text` **逐字保留**（玩家看到的字一个没动）
_BOUNTY_FROZEN = {"q_bounty_normal": "交了。下次还有。",
                  "q_bounty_elite": "这活儿你接得住。",
                  "q_bounty_boss": "……我没想到你真办到了。"}
_frozen_bad = [(k, _beat_of(QE[k], "DELIVER")) for k, want in _BOUNTY_FROZEN.items()
               if _beat_of(QE.get(k) or {}, "DELIVER") != want]
(ok if not _why_side and not _frozen_bad and _side_ok == 29 else bad)(
    "★ 29 条与真源逐条对账（支线 24 §二 / 生活 28 §四 + 21 §二 / 悬赏 24 §二 悬赏板 + 05 §一）："
    "名字 · 谁给 · 步骤=objective · 奖励锚落在交时 · 不串台（坏 %s）· 悬赏三条交时行文逐字＝归位前"
    "域里那一行（坏 %s）" % (_why_side or "无", _frozen_bad or "无"))
for _ln in _lines29:
    print("      %s" % _ln)

# ㉕ ★ 87 条槽位值都非占位（「待填 / 待写 / 〔 / （待 / 进行中」）+ 与主线同款的硬约束
_place87 = [(s, str((TX.get(s) or {}).get("value"))[:16]) for s in keys29
            if any(t in str((TX.get(s) or {}).get("value") or "") for t in PLACE)]
_digit87 = [s for s in keys29 if _re.search(r"[0-9]", str((TX.get(s) or {}).get("value") or ""))]
_keyleak87 = [s for s in keys29
              if _re.search(r"(q_[a-z_]+|[A-Z][A-Z0-9_]{3,})",
                            str((TX.get(s) or {}).get("value") or ""))]
_dup87 = [s for s in set(keys29)
          if [str((TX.get(x) or {}).get("value")) for x in keys29].count(
              str((TX.get(s) or {}).get("value"))) > 1]
(ok if len(keys29) == 87 and len(set(keys29)) == 87 and not _place87
 and not _digit87 and not _keyleak87 and not _dup87 else bad)(
    "★ 29 条 × 3 = 87 条槽位齐备 · 都不是占位（还是占位 %s）· 无阿拉伯数字（%s）· 无机器键（%s）· "
    "互不重复（%s）" % (_place87 or "无", _digit87 or "无", _keyleak87 or "无", _dup87 or "无"))

# ㉖ ★ 三类各真跑一遍：接 / 交(没做完) / 交 —— 槽位里的字必须**逐字**出现在屏上
_drive3, _drive3_lines = [], []
_DRIVE = (("支线", "q_side_02", "item", {"bag": {"i_material_old_iron": 1}}),
          ("生活", "q_trade_02", "visit+item",
           {"foot": {"nodes": {"belt_north:bn_tower": 1}}, "bag": {"i_material_iron_scrap": 1}}),
          ("悬赏", "q_bounty_normal", "legacy-flag", {"flags": {"side_悬赏·普通": True}}))
for _kind, _k, _shape, _fix in _DRIVE:
    _x = QE[_k]
    _n = int(_x["order"])
    _lv = int(_x["min_level"])
    _acc = _drive(CQ.quest_accept, _player(level=_lv), "接 %d" % _n)
    _nod = _drive(CQ.quest_deliver, _player(level=_lv, flags={"quests_active": [_k]}), "交 %d" % _n)
    _flags = {"quests_active": [_k]}
    _flags.update({k: v for k, v in _fix.items() if k == "flags"}.get("flags", {}) or {})
    _p2 = _player(level=_lv)
    _p2.update({k: v for k, v in _fix.items() if k != "flags"})
    _p2["flags"] = _flags
    _pay = _drive(CQ.quest_deliver, _p2, "交 %d" % _n)
    _want = {p: _beat_of(_x, p) for p in ("STORY", "PROGRESS", "DELIVER")}
    if _want["STORY"] not in _acc:
        _drive3.append((_k, "接", _acc[:2]))
    if not any(ln.startswith("还没做完") and _want["PROGRESS"] in ln for ln in _nod):
        _drive3.append((_k, "交(没做完)", _nod[:2]))
    if _want["DELIVER"] not in _pay or _k not in (_p2.get("flags") or {}).get("quests_done", []):
        _drive3.append((_k, "交", _pay[:3]))
    if any(MISSING in ln for ln in _acc + _nod + _pay):
        _drive3.append((_k, "取不到文案", ""))
    _drive3_lines.append("%s %s（编号 %d）接「%s」｜ 没做完「%s」｜ 交「%s」"
                         % (_kind, _x["name"], _n, _want["STORY"][:14],
                            _want["PROGRESS"][:12], _want["DELIVER"][:14]))
(ok if not _drive3 and len(_drive3_lines) == 3 else bad)(
    "★ 支线 / 生活 / 悬赏 各抽一条真跑：接 / 交(没做完) / 交 三拍的字逐字在屏上、奖励入档"
    "（坏 %s）" % (_drive3 or "无"))
for _ln in _drive3_lines:
    print("      %s" % _ln)

for n in notes:
    print("  · " + n)

print()
print("判据 %d 条：%s" % (CHECKS[0], "全绿 ✓" if not fails else "有红 ✗（%d 条）" % len(fails)))
sys.exit(1 if fails else 0)
