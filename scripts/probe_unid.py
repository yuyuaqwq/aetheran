# -*- coding: utf-8 -*-
"""探针：**未鉴定容器**——拿给识货的人看 ⇒ 当场开出来（本件接的那一格）。

来源（这一格是「半成品」的收口，账一直记着）
--------------------------------------------------
· 前一车道 `_notes.md §四·④`：「`unid_*` 那几件**永远不会「开」**（`content/loot.open_unid`
  全仓没有调用端）——未鉴定机制的最后一步（`27 §3.3/§3.5` 的「拿给人看 ⇒ 开出了什么」）
  今天没接线。」本件就是把这根线接上。
· 真源：
  `06_第一阶段垂直切片/27_掉落的惊喜感与未鉴定_v1.md`
    §3.3「拿给谁看（★ 这一步本身就是玩法）」：杜林认锻造物 · 柯尔只认铁 · 艾德认教会器物与文字 ·
         莉安认铭文；认不出来也有味道 · §3.5「你把那块东西放在柜台上。杜林拿起来……」·
    §3.4 五类出口 = 玩家得到什么（装备/材料/垃圾/信物/线索）· §3.6「同一类鉴定过一次之后自动识别」·
    §六 数据面 `appraiser` 那一格（`["npc_durin", "npc_cole"]`）。
  `06_第一阶段垂直切片/06_装备获取与支线玩法_v1.md §1.1`：「捡到不认得的东西 →
         拿给修士/铁匠/莉安看 → 认出来」。
  `00_总纲/14_图鉴四谱口径_v1.md §五` 旧物谱那三行的「谁认得出」那一列（= 域里的 `identify_by`）。
  `06_第一阶段垂直切片/04_指令总表.md §一`：『搭话』是现成的指令 —— **路口不另造动词**。

判据（每条正例 + 反证；反证一律在进程内把那一处临时关掉，跑完立刻还原）
--------------------------------------------------
  ⓪ 前提：三件容器都在域里 · 都是未鉴定 · `identify_by` 非空 · 池子非空；
     「谁鉴定」= 「谁认得出」那一列（`14 §五` 逐字）—— 不然下面几条会静默通过。
  ① 路口 = 现成的『搭话』（声明表里还是它）+ 静态守卫：`open_unid` 的调用端**只有**一处
     （`cmds_talk`），`"identify_by"` 这个字面量在 `content/*.py` 里**只有** `loot.py` 一处
     （唯一一口 —— 谁再自己扫一遍域，口径就会分叉）。
  ② 正例·真敲（杜林 + 一件）：出「★ <他>把它看明白了」+「得到：…」；开出来的那件**真在域里那份池里**
     （探针自己从 `drop_pools` 的 pool 解析出候选集合，不看实现体）；容器**从背包消失**；
     开出来的**真进背包**；旧物谱那一条**问号换真名**（谱里那一行变成「· 名字 —— 认出后那句」）。
  ③ 可重复：手上两件 ⇒ 两次搭话各开一件（两次抽的**不是同一件**），容器归零。
  ④ 三件容器**各自**开得出来（柯尔 · 杜林 · 莉安各走一遍）。
  ⑤ 认不出的那一档：不在名单里的人（莉安 + 骨田那件）⇒ 只说她那一句，**东西照旧留在手上**。
  ⑥ ★ F6 同族：他刚在旧物谱那一支里说过的那句，鉴定这一支**不再贴第二遍**（只出现一次）。
  ⑦ 反证 A：把这一支挂空（= 接线前那原样）⇒ 容器还在 · 什么都没开出来 · 谱里还挂问号。
  ⑧ 反证 B：池子那边开不出来（`open_unid` 回空）⇒ **容器还在**（fail-closed：不吞容器、不编一件）。
  ⑨ 反证 C：把 `codex.reveal` 挂空 ⇒ 开得出来，但旧物谱那一条**还挂问号**（不是恒真）。
  ⑩ 不刷 · 可复现（P-26 同款）：同一档跑两遍 ⇒ 同结果；种子随「手上还剩几件」变（换个剩数会变）。
  ⑪ 保险仍在（前一车道那条 `hint` 逐字判据**一个字没动**）：容器算数 · 池里没有的 / hint 不一样的 /
     材料类一律不算。
  ⑫ 两侧一致：容器开的池子 = 域里现成那一份（实现体 200 次产出全部落在探针自己解析出的候选集合里）。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_unid.py
"""
from __future__ import annotations

import asyncio
import copy
import io
import os
import random
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, ENGINE)
sys.path.insert(0, REPO)

from saintess_engine.package import load_stack                       # noqa: E402

st = load_stack(str(REPO), inject={"db_path": os.path.join(
    os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
st.install()

from content import calendar as CAL                                  # noqa: E402
from content import cmds_ast as CA                                   # noqa: E402
from content import cmds_codex as CC                                 # noqa: E402
from content import cmds_quest as CQ                                 # noqa: E402
from content import cmds_talk as CT                                  # noqa: E402
from content import codex as CX                                      # noqa: E402
from content import facade as FC                                     # noqa: E402
from content import loot as LT                                       # noqa: E402

DP = st.domain("drop_pools")
IT = st.domain("items")
NPCS = st.domain("npcs")
TX = st.domain("texts")

_FC_SAVED = dict(FC.HANDLES)
_SCS = CAL.scale_seconds()


def _at_day(d, h=6.0):
    """假钟拨到「第 d 个游戏日 · 昼」—— 日期戳（抽签种子）看的就是这根钟。"""
    FC.bind_host(clock=lambda _e=(float(d) + h / 24.0) * _SCS: _e)


_at_day(1)


class _E:
    """实现体要 env.text / env.save() / 分页那两个输入面。"""

    def __init__(self, text=""):
        self.text = text

    def save(self):
        pass

    def page(self, raw=None, default=1):
        from saintess_engine.command import parse_page
        return int(parse_page(self.text if raw is None else raw) or default)

    def page_items(self, items, page=1, per_page=10):
        from saintess_engine.command import page_items
        return page_items(items, page, per_page=per_page)


def _drive(fn, p, text=""):
    out = []

    async def go():
        async for line in fn(_E(text), None, "u_unid", p):
            out.append(str(line))

    asyncio.run(go())
    return out


def _player(**kw):
    p = dict(CA.DEFAULT_PLAYER)
    p.update(kw)
    return p


def T(key, **slots):
    return CA.T(key, **slots)


MISSING = "[MISSING TEXT"
fails, CHECKS = [], [0]
ok = lambda m: (CHECKS.__setitem__(0, CHECKS[0] + 1), print("  ✓ " + m))
bad = lambda m: (fails.append(m), CHECKS.__setitem__(0, CHECKS[0] + 1), print("  ✗ " + m))

print("探针：未鉴定容器 —— 拿给识货的人看 ⇒ 当场开出来")

UNIDS = sorted(k for k, v in DP.items() if v.get("kind_key") == "unidentified")


def _pool_ids(uid, n=200):
    """探针**自己**从域里那份池算出「这一件可能开出什么」（不看实现体）。"""
    out = set()
    for e in ((DP.get(uid) or {}).get("pool") or []):
        for s in range(n):
            oid = LT._resolve(str(e.get("out")), e, 1, random.Random(s), IT)
            if oid:
                out.add(str(oid))
    return out


def _book(uid, known=False):
    """一件容器在旧物谱里那一条（**每次都新造** —— `_fresh` 只拷那四个容器，
    `books` 是同一个对象，共用一个 dict 会把上一条用例的结果串到下一条）。"""
    return {"relic": {str(uid): {"day": 1, "known": bool(known)}}}


def _talk_spot(npc_id):
    v = NPCS.get(npc_id) or {}
    return {"loc": v.get("map"), "node": v.get("subarea")}


def _talk(npc_id, bag, books=None, **kw):
    """真敲一次『搭话 <这个人>』（档**每次新造** —— 不许把上一档的结果串过来）。"""
    p = _player(bag=dict(bag), books=copy.deepcopy(books if books is not None else {}),
                level=3, card=1, **kw)
    p.update(_talk_spot(npc_id))
    out = _drive(CT.talk, p, "搭话 %s" % (NPCS.get(npc_id) or {}).get("name"))
    return p, out


def _got_line(out):
    """「得到：…」那一行（唯一口 = 采集/鉴定共用的那个槽位）。"""
    return next((ln for ln in out if ln.startswith("得到：")), "")


def _opened(out, who):
    return T("SYS_UNID_OPENED", who=who) in out


def _unknown_row(uid):
    """谱里**没认出来**时那一行（F6 排版：捡的那几件写手上的名字）。"""
    return T("SYS_CODEX_RELIC_UNKNOWN_HELD", name=CX.held_name(uid),
             hint=CX.line_of("relic", uid, "hint"))


def _known_row(uid):
    return T("SYS_CODEX_RELIC_KNOWN", name=CX.name_of("relic", uid),
             known=CX.line_of("relic", uid, "known"))


def _relic_rows(p):
    return _drive(CC.codex_relic, p, "旧物谱")


EXPECT_APPRAISERS = {                                   # 14 §五 旧物谱那三行的「谁认得出」那一列
    "unid_common": ("npc_durin", "npc_cole"),
    "unid_rare": ("npc_durin", "npc_lian"),
    "unid_tower": ("npc_grey", "npc_durin"),
}

# ══════════════════════════════════════════════════════════════
# ⓪ 前提：这一格真在域里（不然下面会静默通过）
# ══════════════════════════════════════════════════════════════
_b0, _l0 = [], []
if UNIDS != sorted(EXPECT_APPRAISERS):
    _b0.append("未鉴定容器那一批变了：%s" % UNIDS)
for _u in UNIDS:
    if (DP.get(_u) or {}).get("kind_key") != "unidentified":
        _b0.append("%s 不再是未鉴定" % _u)
    if not LT.appraisers_of(_u):
        _b0.append("%s 的「谁鉴定」是空的（那就谁也开不了）" % _u)
    if not ((DP.get(_u) or {}).get("pool") or []):
        _b0.append("%s 的池子是空的" % _u)
    if LT.appraisers_of(_u) != EXPECT_APPRAISERS.get(_u):
        _b0.append("%s 的鉴定名单 ≠ `14 §五` 那一列：%s vs %s"
                   % (_u, LT.appraisers_of(_u), EXPECT_APPRAISERS.get(_u)))
(ok if not _b0 else bad)(
    "⓪ 前提：%d 件未鉴定容器都在 · 都有池子 · 都有「谁认得这一门」的名单（且与 `14 §五` 那一列逐字相同）"
    "（坏 %s）" % (len(UNIDS), _b0 or "无"))
for _u in UNIDS:
    _l0.append("%s → 谁鉴定 %s · 池 %d 条（可能开出 %d 个 id）"
               % (_u, "/".join(LT.appraisers_of(_u)), len((DP.get(_u) or {}).get("pool") or []),
                  len(_pool_ids(_u))))
for _ln in _l0:
    print("      %s" % _ln)

# ══════════════════════════════════════════════════════════════
# ① 路口 = 现成的『搭话』+ 两条静态守卫
# ══════════════════════════════════════════════════════════════
_b1, _l1 = [], []
_CALLERS = {}
_LITT = {}
for _f in sorted(os.listdir(os.path.join(REPO, "content"))):
    if not _f.endswith(".py"):
        continue
    _src = io.open(os.path.join(REPO, "content", _f), encoding="utf-8").read()
    if "open_unid(" in _src:
        _CALLERS[_f] = _src.count("open_unid(")
    if '"identify_by"' in _src:
        _LITT[_f] = _src.count('"identify_by"')
if sorted(_CALLERS) != ["cmds_talk.py", "loot.py"] or _CALLERS.get("cmds_talk.py") != 1:
    _b1.append(("`open_unid` 的调用端不是「唯一一口」", _CALLERS))
if sorted(_LITT) != ["loot.py"]:
    _b1.append(('`"identify_by"` 的字面量出现在别的文件里（唯一一口破了）', _LITT))
# 声明表：『搭话』还是它（没另造动词）
_hit = [k for k, v in st.domain("commands").items()
        if isinstance(v, dict) and v.get("bind", {}).get("handler") == "content.cmds_talk:talk"]
_l1.append("`open_unid(` 出现处：%s ｜ `\"identify_by\"`：%s ｜ 『搭话』声明：%s"
           % (_CALLERS, _LITT, _hit))
if not _hit:
    _b1.append(("『搭话』那条声明没了", _hit))
(ok if not _b1 else bad)(
    "① 路口 = 现成的『搭话』（不另造动词）｜静态守卫：`open_unid` 的调用端只有 `cmds_talk` 一处 · "
    "`identify_by` 只许 `loot.py` 读（唯一一口）（坏 %s）" % (_b1 or "无"))
for _ln in _l1:
    print("      %s" % _ln)

# ══════════════════════════════════════════════════════════════
# ② 正例·真敲：杜林 + unid_rare（谱里挂着问号）
# ══════════════════════════════════════════════════════════════
_b2, _l2 = [], []
_p2, _o2 = _talk("npc_durin", {"unid_rare": 1},
                 {"relic": {"unid_rare": {"day": 1, "known": False}}})
if not _opened(_o2, "杜林"):
    _b2.append(("没出「看明白了」那一行", _o2[-4:]))
_line2 = _got_line(_o2)
if not _line2:
    _b2.append(("没出「得到：…」那一行", _o2[-4:]))
_prod = next((k for k in (_p2.get("bag") or {})), "")
if not _prod:
    _b2.append(("开出来的东西没进背包", _p2.get("bag")))
elif _prod not in _pool_ids("unid_rare"):
    _b2.append(("开出来的那件不在域里那份池里（两侧不一致）", _prod))
if "unid_rare" in (_p2.get("bag") or {}):
    _b2.append(("容器没消失", _p2.get("bag")))
if not CX.known(_p2, "unid_rare"):
    _b2.append(("旧物谱那一条还挂着问号（没认出来）", (CX.unknowns(_p2),)))
_rows = _relic_rows(_p2)
if _known_row("unid_rare") not in _rows:
    _b2.append(("谱里没换成「认出后」那一行", _rows))
if _unknown_row("unid_rare") in _rows:
    _b2.append(("谱里还留着一行问号", _rows))
if any(MISSING in ln for ln in _o2):
    _b2.append(("有取不到的文案", _o2))
_l2.append("杜林 + 一件 ⇒ %s ｜ %s" % (T("SYS_UNID_OPENED", who="杜林"), _line2))
_l2.append("背包：%s（容器已消失）｜ 谱里那一行：%s" % (_p2.get("bag"), _known_row("unid_rare")[:34] + "…"))
(ok if not _b2 else bad)(
    "② 真敲（杜林 + 骨田那件）：他当场把它开出来 ⇒ 开出的是**域里那份池里的真东西**（探针自己解析）· "
    "进背包 · 容器消失 · 旧物谱那一条**问号换真名**（坏 %s）" % (_b2 or "无"))
for _ln in _l2:
    print("      %s" % _ln)

# ══════════════════════════════════════════════════════════════
# ③ 可重复：手上两件 ⇒ 两次搭话各开一件
# ══════════════════════════════════════════════════════════════
_b3, _l3 = [], []
_p3, _o3a = _talk("npc_durin", {"unid_rare": 2}, _book("unid_rare"))
_first = next((k for k in (_p3.get("bag") or {}) if k != "unid_rare"), "")
_o3b = _drive(CT.talk, _p3, "搭话 杜林")
_second = next((k for k in (_p3.get("bag") or {}) if k not in ("unid_rare", _first)), "")
if int((_p3.get("bag") or {}).get("unid_rare") or 0) != 0:
    _b3.append(("两件都开完了，容器还剩下", _p3.get("bag")))
if not _first or not _second:
    _b3.append(("两件没各开出一件", (_first, _second, _p3.get("bag"))))
for _x in (_first, _second):
    if _x and _x not in _pool_ids("unid_rare"):
        _b3.append(("开出来的不在池里", _x))
if _first and _second and _first == _second:
    _b3.append(("两件抽到同一个结果（剩数没进种子？）", _first))
if not _opened(_o3a, "杜林") or not _opened(_o3b, "杜林"):
    _b3.append(("两次搭话没有各出一次「看明白了」", (_o3a[-3:], _o3b[-3:])))
_l3.append("两件 unid_rare：第 1 次 ⇒ %s ｜ 第 2 次 ⇒ %s ｜ 容器 %s"
           % (_first, _second, (_p3.get("bag") or {}).get("unid_rare", 0)))
(ok if not _b3 else bad)(
    "③ 可重复：手上两件，两次搭话各开一件（各按各的抽签 · 都落在池里）· 容器归零（坏 %s）" % (_b3 or "无"))
for _ln in _l3:
    print("      %s" % _ln)

# ══════════════════════════════════════════════════════════════
# ④ 三件容器各自开得出来（各走一位认得的人）
# ══════════════════════════════════════════════════════════════
_b4, _l4 = [], []
for _u, _npc in (("unid_common", "npc_cole"), ("unid_tower", "npc_durin"), ("unid_rare", "npc_lian")):
    _who = (NPCS.get(_npc) or {}).get("name") or _npc
    _p4, _o4 = _talk(_npc, {_u: 1}, {"relic": {_u: {"day": 1, "known": False}}})
    if not _opened(_o4, _who):
        _b4.append(("%s 在 %s 那儿没开出来" % (_u, _who), _o4[-3:]))
        continue
    _pid = next((k for k in (_p4.get("bag") or {})), "")
    if not _pid or _pid not in _pool_ids(_u):
        _b4.append(("%s 开出来的不在它自己的池里" % _u, (_pid, _p4.get("bag"))))
    if _u in (_p4.get("bag") or {}):
        _b4.append(("%s 没消失" % _u, _p4.get("bag")))
    if not CX.known(_p4, _u):
        _b4.append(("%s 的谱条目还挂问号" % _u))
    _l4.append("%s → %s 开 ⇒ %s（容器 %s）"
               % (_u, _who, _pid, (_p4.get("bag") or {}).get(_u, 0)))
(ok if not _b4 else bad)(
    "④ 三件容器**各自**开得出来（各走一位认得的人）：认出 · 开出池里的东西 · 容器消失 · 谱里换名"
    "（坏 %s）" % (_b4 or "无"))
for _ln in _l4:
    print("      %s" % _ln)

# ══════════════════════════════════════════════════════════════
# ⑤ 认不出的那一档：只说他那一句，东西照旧留在手上
# ══════════════════════════════════════════════════════════════
_b5, _l5 = [], []
_p5, _o5 = _talk("npc_lian", {"unid_common": 1}, {"relic": {"unid_common": {"day": 1, "known": False}}})
if T("TALK_IDENTIFY_LIAN") not in _o5:
    _b5.append(("不在名单里的人没说那句「她没有说话」", _o5[-3:]))
if int((_p5.get("bag") or {}).get("unid_common") or 0) != 1:
    _b5.append(("认不出却把东西开掉了/吞了", _p5.get("bag")))
if _got_line(_o5):
    _b5.append(("认不出却给了东西", _o5[-3:]))
_l5.append("莉安 + 骨田那件 ⇒ %s（容器还在：%s）"
           % (T("TALK_IDENTIFY_LIAN"), (_p5.get("bag") or {}).get("unid_common")))
(ok if not _b5 else bad)(
    "⑤ 「认不出来也有味道」（27 §3.3）：不在名单里的人只说那一句，东西照旧留在手上"
    "（坏 %s）" % (_b5 or "无"))
for _ln in _l5:
    print("      %s" % _ln)

# ══════════════════════════════════════════════════════════════
# ⑥ ★ F6 同族：旧物谱那一支刚说过的那句，不再贴第二遍
# ══════════════════════════════════════════════════════════════
_b6, _l6 = [], []
_ASK_LINE = T("TALK_IDENTIFY_KNOWN")
_times = _o2.count(_ASK_LINE)
_in_ask_line = sum(1 for ln in _o2 if _ASK_LINE in ln)
if _in_ask_line != 1 or _times != 0:
    _b6.append(("同一句被贴了不止一遍（F6 同族）", (_times, _in_ask_line, _o2[-6:])))
# 反证：第二趟（谱里已经认出来了，旧物谱那一支不再说话）⇒ 那句该**重出**（说明不是「永远不说」）
_p6 = dict(_p2)
_p6["bag"] = {"unid_rare": 1}
_o6 = _drive(CT.talk, _p6, "搭话 杜林")
if _ASK_LINE not in _o6:
    _b6.append(("谱里已认出之后再搭话，他反倒不认了（那句话没了来源）", _o6[-4:]))
_l6.append("第一趟：那句「我见过」只出现 1 遍（在旧物谱那一支里）· 第二趟（谱里已认出）⇒ 它重出")
(ok if not _b6 else bad)(
    "⑥ 同一件事不许贴两遍（F6）：第一趟那句只在旧物谱那一支里说一遍；第二趟（谱里已认出）⇒ "
    "鉴定这一支自己说（不是「永远不说」）（坏 %s）" % (_b6 or "无"))
for _ln in _l6:
    print("      %s" % _ln)

# ══════════════════════════════════════════════════════════════
# ⑦⑧⑨ 三条反证（正例是②③④⑤那几条 —— 这里逐条把它们打回原样）
# ══════════════════════════════════════════════════════════════
_b7, _l7 = [], []

# ⑦ 反证 A：把这一支挂空 = **接线前那原样**
_keep_id = CT._identify_lines
try:
    async def _off(*_a, **_k):
        if False:                                  # pragma: no cover —— 就是「一支都不出」
            yield ""
    CT._identify_lines = _off
    _p7, _o7 = _talk("npc_durin", {"unid_rare": 1}, _book("unid_rare"))
finally:
    CT._identify_lines = _keep_id
if _opened(_o7, "杜林") or _got_line(_o7) or int((_p7.get("bag") or {}).get("unid_rare") or 0) != 1:
    _b7.append(("反证 A 没生效（挂空了还开得出来）", (_o7[-3:], _p7.get("bag"))))
(ok if not _b7 else bad)(
    "⑦ 反证 A：把这一支挂空（= 接线前那原样）⇒ 一次都开不出来 · 容器还留在手上（坏 %s）" % (_b7 or "无"))

_b8 = []
# ⑧ 反证 B：池子那边开不出来 ⇒ 容器还在（fail-closed 不吞容器）
_keep_op = LT.open_unid
try:
    LT.open_unid = (lambda *_a, **_k: {})
    _p8, _o8 = _talk("npc_durin", {"unid_rare": 1}, _book("unid_rare"))
finally:
    LT.open_unid = _keep_op
if _opened(_o8, "杜林") or _got_line(_o8) or int((_p8.get("bag") or {}).get("unid_rare") or 0) != 1:
    _b8.append(("反证 B 没生效（开不出来却动了档）", (_o8[-3:], _p8.get("bag"))))
(ok if not _b8 else bad)(
    "⑧ 反证 B：池子那边开不出来（`open_unid` 回空）⇒ **什么都不动**（容器还在 · 不编一件）"
    "（坏 %s）" % (_b8 or "无"))

_b9 = []
# ⑨ 反证 C：把 `codex.reveal` 挂空 ⇒ 开得出来，但谱里还挂问号
_keep_rv = CX.reveal
try:
    CX.reveal = (lambda *_a, **_k: False)
    _p9, _o9 = _talk("npc_durin", {"unid_rare": 1}, _book("unid_rare"))
finally:
    CX.reveal = _keep_rv
if not _opened(_o9, "杜林") or CX.known(_p9, "unid_rare") \
        or _unknown_row("unid_rare") not in _relic_rows(_p9):
    _b9.append(("反证 C 没生效（关掉 reveal 谱里照样变真名）",
                (_o9[-3:], CX.known(_p9, "unid_rare"))))
(ok if not _b9 else bad)(
    "⑨ 反证 C：把 `codex.reveal` 挂空 ⇒ 东西照样开得出来，但旧物谱那一条**还挂问号**"
    "（「问号变真名」不是恒真）（坏 %s）" % (_b9 or "无"))

# ══════════════════════════════════════════════════════════════
# ⑩ 不刷 · 可复现（P-26 同款：种子由稳定标识拼）
# ══════════════════════════════════════════════════════════════
_b10, _l10 = [], []
_s_same1 = CT._unid_seed("u_unid", 1, "unid_rare", 1)
_s_same2 = CT._unid_seed("u_unid", 1, "unid_rare", 1)
_s_other = CT._unid_seed("u_unid", 1, "unid_rare", 2)
if _s_same1 != _s_same2 or _s_same1 == _s_other:
    _b10.append(("种子不是「稳定标识拼」的（同输入不同结果 / 换剩数不变）",
                 (_s_same1, _s_same2, _s_other)))
# 真跑两遍同一档 ⇒ 同结果（同一根假钟 · 同一个 uid）
_p10a, _o10a = _talk("npc_durin", {"unid_rare": 1}, _book("unid_rare"))
_p10b, _o10b = _talk("npc_durin", {"unid_rare": 1}, _book("unid_rare"))
_a_id = next((k for k in (_p10a.get("bag") or {})), "")
_b_id = next((k for k in (_p10b.get("bag") or {})), "")
if not _a_id or _a_id != _b_id:
    _b10.append(("同一档跑两遍结果不一样（不可复现）", (_a_id, _b_id)))
_l10.append("种子：%s（同剩数同串 · 换剩数 ⇒ %s）" % (_s_same1, _s_other))
_l10.append("同一档真跑两遍 ⇒ 都是「%s」" % _a_id)
(ok if not _b10 else bad)(
    "⑩ 不刷 · 可复现：抽签种子 = 人·游戏日·容器·手上还剩几件（P-26 同款）—— 同一档两遍同结果 · "
    "换个剩数会变（坏 %s）" % (_b10 or "无"))
for _ln in _l10:
    print("      %s" % _ln)

# ══════════════════════════════════════════════════════════════
# ⑪ 保险仍在（前一车道那条 `hint` 逐字判据一个字没动）
# ══════════════════════════════════════════════════════════════
_b11, _l11 = [], []
if not CQ._unid_carries("unid_rare", "i_token_stone_shard"):
    _b11.append(("容器那件不再算数（把保险碰坏了）",))
if CQ._unid_carries("unid_common", "i_token_stone_shard") \
        or CQ._unid_carries("unid_tower", "i_token_stone_shard"):
    _b11.append(("hint 不一样的容器也被算进来了（放宽过头）",))
if CQ._bag_n({"bag": {"unid_rare": 1}}, "i_material_old_iron") \
        or CQ._bag_n({"bag": {"unid_rare": 1}}, "i_junk_bone"):
    _b11.append(("材料/垃圾类也被容器顶掉了",))
if CQ._bag_n({"bag": {"unid_rare": 1}}, "i_token_stone_shard") != 1:
    _b11.append(("容器不再计入「手上有几件」",))
_src_q = io.open(os.path.join(REPO, "content", "cmds_quest.py"), encoding="utf-8").read()
for _mark in ('def _unid_carries', 'u.get("kind_key") != "unidentified"',
              'str(u.get("hint") or "") != said'):
    if _mark not in _src_q:
        _b11.append(("保险那三条判据的源码形态变了：%s" % _mark,))
_l11.append("`_unid_carries(unid_rare, 刻字的石片)` = %s · 池里没有的/hint 不一样的 = %s"
            % (CQ._unid_carries("unid_rare", "i_token_stone_shard"),
               (CQ._unid_carries("unid_common", "i_token_stone_shard"),
                CQ._unid_carries("unid_tower", "i_token_stone_shard"))))
(ok if not _b11 else bad)(
    "⑪ 保险仍在（前一车道那条 `hint` 逐字判据**一个字没动**）：容器算数 · 池里没有的 / hint 不一样的 / "
    "材料类一律不算（坏 %s）" % (_b11 or "无"))
for _ln in _l11:
    print("      %s" % _ln)

# ══════════════════════════════════════════════════════════════
# ⑫ 两侧一致：容器开的池子 = 域里现成那一份（200 次产出全落在候选集合里）
# ══════════════════════════════════════════════════════════════
_b12, _l12 = [], []
_N = 200
_leak = []
for _u in UNIDS:
    _cand = _pool_ids(_u)
    for _s in range(_N):
        _r = LT.open_unid(_u, rnd=random.Random("%s:%d" % (_u, _s)))
        if not _r:
            _leak.append((_u, _s, "开不出来"))
            continue
        if str(_r["id"]) not in _cand:
            _leak.append((_u, _s, _r["id"]))
        if LT.rec_of(_r["id"]).get("name") is None:
            _leak.append((_u, _s, "没有名字"))
# 两态对照：候选集合**不为空**且真被覆盖到（判据不是永真）
_hit_any = {_u: len([1 for _s in range(_N)
                     if str((LT.open_unid(_u, rnd=random.Random("%s:h:%d" % (_u, _s))) or {}).get("id", ""))
                     in _pool_ids(_u)]) for _u in UNIDS}
if _leak:
    _b12.append(("实现体开出了池外的东西", _leak[:4]))
if any(v == 0 for v in _hit_any.values()):
    _b12.append(("有一件容器一次都开不出池里的东西", _hit_any))
_l12.append("%d 件 × %d 次 ⇒ 产出全部落在探针自己从域池解析出的候选集合里（%s）"
            % (len(UNIDS), _N, " · ".join("%s %d/%d" % (k, v, _N) for k, v in sorted(_hit_any.items()))))
(ok if not _b12 else bad)(
    "⑫ 两侧一致：容器开的池子 = **域里现成那一份**（本支不另写池）—— %d 件 × %d 次产出全在池里"
    "（坏 %s）" % (len(UNIDS), _N, _b12 or "无"))
for _ln in _l12:
    print("      %s" % _ln)

FC.bind_host(**_FC_SAVED)                                            # ★ 拨回真钟

print()
print("判据 %d 条：%s" % (CHECKS[0], "全绿 ✓" if not fails else "有红 ✗（%d 条）" % len(fails)))
sys.exit(1 if fails else 0)
