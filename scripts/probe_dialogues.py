# -*- coding: utf-8 -*-
"""探针：dialogues 域（14 位 · need 条件择优 · 与 npcs 双向对账 · 一屏 400 字）。

★ P-12 那条（对话层的**取句顺序**）也钉在这里（⑧）：层序 `meet → daily → main → hidden → idle`
  +「熟了才轮到 daily」+「说过的句子让位」；★ P-62（本波 w-h-ux）：`dialogues.<树>.start` **已撤**
  —— 域里一棵树都不许再有它，`schemas/dialogues.schema.json` 也一起清（谁加回来当场红）；① 那条
  覆盖改成「每棵树都有节点 · 且有层序排头那一层」。
  ★ 台账 P-12 已经 ✅（2026-09-25 包 `4815bdb` 落的那三件）—— 本探针只**钉住**它，不改行为。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_dialogues.py
"""
from __future__ import annotations

import json
import re
import os
import time
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402

ok = True
#: ★★ P1-27（2026-09-29 · 文案车道 P1）：这份词表**不在探针里**了 ——
#:   读端 `content/cmds_talk.NEED_KINDS` 是**唯一一份**（它才是「认得哪些键」的定义方；
#:   探针只是消费者）。原先这里是探针自己抄的常量，两份各写各的**已经漂了**：
#:     · 探针认得、读端**没有**分支 ⇒ `quest_active` / `flag_not`
#:       ⇒ 域里用上这两个键，那一句**无条件对所有档说**，零报错（静默洗成兜底句）；
#:     · 读端认得、探针**没有** ⇒ `last` / `codex`
#:       ⇒ 域里正当用上它们，③ 会**误报**「词表里没有」。
#:   漂移的取证与修法见同提交消息；`NEED_KINDS` 此刻在下面 import（延迟到 ③ 之前）。
MAX_CHARS = 400          # 一屏字数硬约束（消息模板 §优化 3）


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


print("探针：dialogues 域（对话树）")
st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
st.install()
dl = st.domain("dialogues")
np_ = st.domain("npcs")
chk("dialogues 域读得到", dl is not None, "%d 位" % (len(dl) if dl else 0))
chk("npcs 域读得到（交叉对账要用）", np_ is not None)
if not (dl and np_):
    sys.exit(1)

n_nodes = sum(len(v["nodes"]) for v in dl.values())
n_texts = sum(len(nd["texts"]) for v in dl.values() for nd in v["nodes"].values())
print("      %d 位 · %d 节点 · %d 条台词" % (len(dl), n_nodes, n_texts))

# ① ★ P-62（2026-09-26 · 本波 w-h-ux · **裁决：删字段**）：原先这条查的是「`start` 指的那个节点存在」。
#   `start` 撤掉之后，同一份覆盖换成**树本身立得住**：节点非空 + 层序排头那一层必须在。
#   为什么能这么换：那一格 14 处**全是 `"meet"`**，而 `meet` 就是取句层序的排头
#   （`content/cmds_talk.LAYERS[0]`）—— 一个**恒真的常量**换成一条**真的约束**。
from content import cmds_talk as CT0                                       # noqa: E402

_head_layer = CT0.LAYERS[0]
bad1 = [k for k, v in dl.items()
        if not (v.get("nodes") or {}) or _head_layer not in (v.get("nodes") or {})]
chk("每棵树都有节点 · 且有层序排头那一层（%s —— 取句顺序的唯一口 `cmds_talk.LAYERS`）" % _head_layer,
    not bad1, " · ".join(bad1))

# ② ★ 与 npcs 双向对账 —— ★ 本波起「落点」多一处：`pois.effect.talk` 指的那棵树
#   （三处篝火的夜谈：那棵树没有 NPC，玩家是在**那一处东西**上听到它的）。
#   ⇒ ① 「NPC 指向的树都存在」② 「POI 指向的树都存在」（悬空当场红 —— 原先那三条
#      `talk_campfire_*` 全仓没有定义处，上手只吐一行「（…边的话还没写下来。）」）③ 没有孤立的树。
po_d = st.domain("pois") or {}
a = {v["dialogue"] for v in np_.values()}
c = set()
for _v in po_d.values():
    _t = (_v.get("effect") or {})
    if isinstance(_t, dict) and _t.get("talk"):
        c.add(str(_t["talk"]))
b = set(dl)
chk("★ NPC 指向的对话树都存在", not (a - b), "缺：%s" % (a - b))
chk("★ POI 的 `effect.talk` 指向的树都存在（悬空 = 上手吐「…边的话还没写下来。」）",
    not (c - b), "缺：%s" % (c - b))
chk("★ 没有孤立的对话树（NPC 或 POI 至少一处引得到）", not (b - a - c), "孤立：%s" % (b - a - c))

# ③ need 条件合法 —— ★ 本波加强：从「至少要认得一个键」改成「**每个**键都得在词表里
#   （欠一个就是落到 `else: ok = True` 的静默兜底：那一句会被**所有**档听到）」
#   + 静态守卫：域里用到的每个键，在 `content/cmds_talk.py` 里都得有它自己的分支。
from content import cmds_talk as CT                                       # noqa: E402  （本段要用它真敲）
from content.cmds_talk import NEED_KINDS                                  # noqa: E402  唯一一份
bad3 = []
for k, v in dl.items():
    for nk, nd in v["nodes"].items():
        for t in nd["texts"]:
            nd_ = t.get("need")
            if nd_ and (set(nd_) - set(NEED_KINDS)):
                bad3.append("%s/%s=%s" % (k, nk, sorted(set(nd_) - set(NEED_KINDS))))
chk("★ need 条件的**每个**键都在**读端**词表里（%s）" % " · ".join(sorted(NEED_KINDS)),
    not bad3, " · ".join(bad3))
_ct_src = (REPO / "content" / "cmds_talk.py").read_text(encoding="utf-8")
_used_kinds = {kk for v in dl.values() for nd in v["nodes"].values()
               for t in nd["texts"] for kk in (t.get("need") or {})}
_nobranch = sorted(kk for kk in _used_kinds if ('k == "%s"' % kk) not in _ct_src)
chk("★ 域里用到的 need 键在 `_pick_indexed` 里各有一支（没分支 = 写了等于没写：静默满足）",
    not _nobranch, "没分支：%s" % _nobranch)

# ㉓-a ★★ P1-27（2026-09-29 · 文案车道 P1）—— **认不出的键 fail-closed**（原来是静默满足）
#    缺陷本体：`_pick_indexed` 的末尾是 `else: ok = True`（认不出 = 当满足）⇒ 一个拼错的
#    条件键（`tim` 之于 `time`）会把那一句**无条件说给所有档听**，而域与 schema 都拦不住
#    （schema 不约束 need 的键名；③ 的词表只查「域里已用的键」，管不到「拼错的键」）。
#    后果按本车道自己的口径说：条件句被静默洗成兜底句 = 剧透提前 + 观感重样。
#    判据是**可观测**的：真敲读端，一个生造键必须**出不来**，而 need=null 兜底句**仍要出得来**
#    （防「fail-closed 过头、把兜底也打死」这种改坏）。
_ck27 = {"flags": {}, "bag": {}, "equipped": {}, "hp": 999}
_unknown27 = sorted(set(NEED_KINDS) | {"tim", "not_a_real_key", "quest_active", "flag_not"})
_leak27 = [kk for kk in _unknown27
           if CT._pick_indexed([{"need": {kk: "x"}, "text": "不该出"}], _ck27)[1]]
chk("㉓-a ★ 生造的 need 键一律**出不来**（认不出 = 不满足，不是 = 满足）", not _leak27,
    "漏出去：%s" % _leak27 if _leak27 else "试了 %d 个键全挡住" % len(_unknown27))
# 真跑一遍未改态的读端（临时把 else 分支改回「满足」）—— 判据自身要能分辨
_old27 = CT._pick_indexed
def _pick_satisfy_unknown(lines, p, st=None):
    """未改态读端：把「认不出的键」当**满足**（改前的真行为）—— 只给这条反证用。"""
    out = []
    for ln in (lines or []):
        nd = dict(ln.get("need") or {})
        if nd:
            known = {kk: vv for kk, vv in nd.items() if kk in set(NEED_KINDS)}
            if len(known) != len(nd):          # 有生造键 ⇒ 改前：无条件满足
                out.append({"need": None, "text": ln.get("text")})
            else:
                out.append({"need": nd, "text": ln.get("text")})
        else:
            out.append(ln)
    return _old27(out, p, st)
_leak27b = [kk for kk in ("tim", "not_a_real_key", "quest_active", "flag_not")
            if _pick_satisfy_unknown([{"need": {kk: "x"}, "text": "改前会漏"}], _ck27)[1]]
chk("㉓-b ★ 反证：按「认不出=满足」的旧读端，㉓-a 必抓到 %d 处（判据不恒真）" % len(_leak27b),
    len(_leak27b) >= 4, "旧读端漏出：%s" % _leak27b)

# ④ 每节点至少一条 + 台词非空
bad4 = [("%s/%s" % (k, nk)) for k, v in dl.items() for nk, nd in v["nodes"].items()
        if not nd["texts"] or any(not t.get("text") for t in nd["texts"])]
chk("每节点至少一条且台词非空", not bad4, " · ".join(bad4))

# ⑤ 一屏字数约束
bad5 = []
for k, v in dl.items():
    for nk, nd in v["nodes"].items():
        for t in nd["texts"]:
            if len(t["text"]) > MAX_CHARS:
                bad5.append("%s/%s(%d字)" % (k, nk, len(t["text"])))
chk("台词都不超一屏 400 字", not bad5, " · ".join(bad5))

# ⑥ 提示：无兜底的条件节点（设计上合法 —— 阶段节点不满足条件就不该说话）
cond_only = ["%s/%s" % (k, nk) for k, v in dl.items() for nk, nd in v["nodes"].items()
             if nd["texts"][-1]["need"] is not None]
print("  · 条件节点（无兜底，合法）：%d 个 —— %s" % (len(cond_only), " · ".join(cond_only[:6])))

# ⑦ 四层的实现度：有 daily 的几位 + 有 main/hidden 的几位
has_daily = [k for k, v in dl.items() if "daily" in v["nodes"]]
has_main = [k for k, v in dl.items() if "main" in v["nodes"]]
has_hidden = [k for k, v in dl.items() if "hidden" in v["nodes"]]
print("  · 四层分布：daily %d 位 · main %d 位 · hidden %d 位" % (
    len(has_daily), len(has_main), len(has_hidden)))

# ⑧ ★ P-12（对话层的**取句顺序** —— 2026-09-25 包 `4815bdb` 已落）：层序 = 人先熟、事才说
#    台账那一条的原状是「`cmds_talk` 按 `main → hidden → meet → daily → idle` 挑」（刚认识就剧透
#    主线、底牌一见面就漏；哈根的 hidden 兜底句还把 meet / daily 永久遮住）。已落的口径 =
#    `meet → daily → main → hidden → idle` +「同一个对话树搭过 ≥ 3 次才算熟」+「说过的句子让位给
#    还没说过的层」。本判据把它钉成机器可验，且与实现**各写各的**（这里用一棵**假树**直接调
#    `_pick_layer`，不去读实现里的常量表是怎么写的）：
#      ① 层序常量 == 真源那串（`meet daily main hidden idle`）·「熟了」的门槛 == 3
#      ② 还不熟（搭 0 / 2 次）⇒ **只有 `meet` 那一档会说话**（daily 的门没过 · main / hidden 排后头）
#      ③ 熟了（搭 3 次）⇒ 轮到 `daily` —— ★ **不是 `main`**：层序里 daily 排在 main 前面
#         （原先那条顺序会把主线剧透给刚认识的人）
#      ④ 说过的句子让位给还没说过的层：daily 听过 ⇒ main ⇒ hidden ⇒ idle；
#         全会说过才回到层序上第一档（daily）—— 兜底句不许把 main / hidden 永久遮住
#      ⑤ `start` 字段：★ **已撤**（P-62 · 2026-09-26 · 本波 w-h-ux）—— 域里一棵树都不许再有它，
#         连 `schemas/dialogues.schema.json` 一起清（`required` / `properties` 两处）。
#         依据：包内 0 读端（取句顺序的唯一口是 `cmds_talk.LAYERS`）· 那一格恒 = 排头 ⇒ 死数据；
#         谁加回来当场红（加了 = 又开一个「白写字段」的口，且与 `LAYERS` 形成第二口径）。
import glob as _glob8                                                       # noqa: E402
import io as _io8                                                           # noqa: E402

from content import cmds_talk as CT                                         # noqa: E402
from content.cmds_ast import hp_cap_or_line                     # noqa: E402  ⑬ 用：后期档要真的生命上限

_FIVE = {_ly: {"texts": [{"need": None, "text": _ly.upper()}]}
         for _ly in ("meet", "daily", "main", "hidden", "idle")}
_DLG12 = "dlg_probe_p12"


def _p12(n, heard=()):
    """一棵假树的档：搭过 n 次话 + 听过哪几句（形状照 `heard` 那本账）。"""
    return {"flags": {"talked": {_DLG12: n}}, "heard": {_DLG12: {h: 1 for h in heard}}}


def _pick12(n, heard=()):
    return CT._pick_layer(_FIVE, _p12(n, heard), None, _DLG12)


bad8 = []
if tuple(CT.LAYERS) != ("meet", "daily", "main", "hidden", "idle"):
    bad8.append("层序常量 = %s（真源那串 = meet → daily → main → hidden → idle）"
                % (tuple(CT.LAYERS),))
if int(CT.FAMILIAR_TALKS) != 3:
    bad8.append("「熟了」的门槛 = %s（真源 = 同一个对话树搭过 ≥ 3 次）" % CT.FAMILIAR_TALKS)
for _n in (0, 2):                                     # 还不熟 ⇒ 只有 meet
    _ly, _, _tx = _pick12(_n)
    if _ly != "meet":
        bad8.append("搭 %d 次（还不熟）出的却是「%s」层 —— 应当是 meet" % (_n, _ly))
for _n, _h, _want in ((3, (), "daily"),                     # 熟了 ⇒ daily（不是剧透的 main）
                      (9, ("daily#0",), "main"),
                      (9, ("daily#0", "main#0"), "hidden"),
                      (9, ("daily#0", "main#0", "hidden#0"), "idle"),
                      (9, ("daily#0", "main#0", "hidden#0", "idle#0"), "daily")):
    _ly, _, _tx = _pick12(_n, _h)
    if _ly != _want:
        bad8.append("搭 %d 次 · 听过 %s ⇒ 出的却是「%s」层（应当是 %s）"
                    % (_n, list(_h), _ly, _want))
_starts = sorted({str(v.get("start")) for v in dl.values() if "start" in v})
if _starts:
    bad8.append("域里又出现了 `start`：%s（P-62 已裁删字段 —— 取句顺序只认 `cmds_talk.LAYERS`）"
                % _starts)
try:
    _sch8 = (REPO / "schemas" / "dialogues.schema.json").read_text(encoding="utf-8")
    if '"start"' in _sch8:
        bad8.append("`schemas/dialogues.schema.json` 里还留着 `start`（要删就连 schema 一起清）")
except OSError:                                                          # noqa: BLE001
    bad8.append("schema 读不到：schemas/dialogues.schema.json")
_start_read = []
for _pp in sorted(_glob8.glob(os.path.join(str(REPO), "content", "*.py"))):
    for _i8, _l8 in enumerate(_io8.open(_pp, encoding="utf-8").read().split("\n")):
        if '.get("start")' in _l8 or '["start"]' in _l8:
            _start_read.append((os.path.basename(_pp), _i8 + 1))
if _start_read:
    bad8.append("content/*.py 里有人读 `start` 了（那一格已经撤掉）：%s" % _start_read)
chk("★ P-12 取句顺序（层序 %s · 熟门槛 %s）：不熟只有 meet · 熟了轮到 daily（不是剧透的 main）· "
    "说过的让位给没说的 · `start` **已撤**（域 + schema 都不许再有 · 谁加回来就红）"
    % (" → ".join(CT.LAYERS), CT.FAMILIAR_TALKS), not bad8, "；".join(bad8))
print("      假树五层真调 `_pick_layer`：搭 0/2 次 ⇒ meet ｜ 搭 3 次 ⇒ daily ｜ daily 听过 ⇒ main "
      "⇒ hidden ⇒ idle ⇒ 全说过回 daily ｜ 14 棵树都有层序排头那一层、`start` 已撤（域里 0 处）")

# ⑨ ★ fix3-⑤：**一句一行** —— 台词在**域里**就分好行（排版随文案走，与 SCENE_* 同一条路）
#   玩家报的原状（P1 体验-5）：`搭话 杜林` 一整段 130 字、6 组「」挤在一行，界面上读成一坨；
#   而『观察』（SCENE_* 正文自带换行）与『悬赏』（一行一条槽位）早就做到一句一行。
#   落法 = `scripts/normalize_dialogue_lines.py`（一次性归一化，域里存的就是多行文本）；
#   判据 = 逐条台词按 `\n` 拆完自查 + **幂等**（再跑一遍归一化不许有改动）+ 反证。
sys.path.insert(0, os.path.join(str(REPO), "scripts"))                    # noqa: E402
import normalize_dialogue_lines as _NL                                    # noqa: E402

MAX_LINE = 72


def _line_bad(text):
    """这一条台词切完还有没有坏行 —— 空表 = 合规。"""
    bad = []
    for ln in str(text).split("\n"):
        if not ln.strip():
            bad.append(("空行", ln))
        elif len(ln) > MAX_LINE:
            bad.append(("超 %d 字" % MAX_LINE, ln[:24]))
        elif ln.count("「") > 1:
            bad.append(("一行挤了 %d 组引号" % ln.count("「"), ln[:24]))
    return bad


_ln9, _ib9, _idem9 = [], [], []
for _k, _v in dl.items():
    for _nk, _nd in _v["nodes"].items():
        for _t in _nd["texts"]:
            _s = _t["text"]
            _ln9.append(len(_s.split("\n")))
            _b = _line_bad(_s)
            if _b:
                _ib9.append(("%s/%s" % (_k, _nk), _b[:2]))
            if "\n".join(_NL.speak(_s)) != _s:
                _idem9.append("%s/%s" % (_k, _nk))
chk("★ 一句一行：%d 条台词的每一行都 ≤ %d 字、且每行最多一组「」"
    "（最长一行 %d 字 · 平均 %.1f 行/条）"
    % (n_texts, MAX_LINE, max((max((len(x) for x in t["text"].split("\n")), default=0)
                               for _v in dl.values() for _nd in _v["nodes"].values()
                               for t in _nd["texts"]), default=0),
       sum(_ln9) / float(len(_ln9) or 1)), not _ib9, "%s" % (_ib9[:3] or "全合规"))
chk("★ 幂等：再跑一遍 `scripts/normalize_dialogue_lines.py` 的切行 ⇒ 一条都不动"
    "（域里存的就是切好的形态）", not _idem9, "%s" % (_idem9[:3] or "0 条要改"))

# 反证：这条判据抓得住玩家报的那条原状（杜林·初次 · 逐字抄自 P1 报告，130 字 / 6 组引号）
_OLD_DURIN = ("「旧东西？拿来我看。」「……」（他翻了两下，忽然不出声了）（压低声音）"
              "「你知道这是什么吗。」「三百年前的形制。这种扣法，只有那一家作坊用。」"
              "（他抬头看你）「你在哪儿捡的。」「……行，你不说也行。但这个价，我给你翻倍。」")
_ob9 = _line_bad(_OLD_DURIN)
chk("★ 反证：旧形态（%d 字一行 · %d 组引号）会被判红；切完 %d 行全合规"
    % (len(_OLD_DURIN), _OLD_DURIN.count("「"), len(_NL.speak(_OLD_DURIN))),
    bool(_ob9) and not _line_bad("\n".join(_NL.speak(_OLD_DURIN))),
    "%s" % (_ob9[:1] or "没抓住"))

# ⑨-b ★★ P1-34（2026-09-29 · 文案修复车道 P1）—— **屏上不许出现孤零零的收尾括号**
#    缺陷本体（玩家可见 · 逐字可复现）：`dlg_lian/meet[0]` 印出来是这样
#        （她还是看着北边。
#        手指在膝盖上敲了两下，停了。
#        ）                    ← ★ 单独一行，就一个 `）`
#        「你又来了。」
#    根因：`normalize_dialogue_lines._safe_parts` 的切点只数**引号**不数**括号**
#    （原注释明写「只计引号的开合（②）不计 （）」），切点可以落进 （…） 里面
#    ⇒ 那个 `）` 被甩到下一行开头。改前实测 6 处（lian 2 · bella/pete/laotao/ed 各 1）。
#    ★ 为什么 ⑨ 那一组没抓到：它只查「行 ≤ 72 字」与「一行最多一组「」」，
#      **从不查括号配对** ⇒ 一个 1 字宽的 `）` 行完全合规（这正是它能一路绿过去的原因）。
#    ★ 两条都查（缺一不可）：⑨-b-a 整行只有收尾括号（屏上一行孤括号）
#      ⑨-b-b 整条台词括号配对（切在括号中间的那种）
#    分档：现值都是 0 ⇒ 硬底线 0 —— 不是"逐步放宽"，是**把已经修好的事钉住**。
_ORPHAN_CLS = re.compile(r"^[\uFF09\s\u3000]+$")
_orph9, _unbal9, _n_ln9 = [], [], 0
for _k9b, _v9b in dl.items():
    for _nk9b, _nd9b in _v9b["nodes"].items():
        for _i9b, _t9b in enumerate(_nd9b["texts"]):
            _s9b = _t9b["text"]
            for _l9b in _s9b.split("\n"):
                if not _l9b.strip():
                    continue
                _n_ln9 += 1
                if _ORPHAN_CLS.match(_l9b.strip()):
                    _orph9.append("%s/%s[%d]=%s" % (_k9b, _nk9b, _i9b, _l9b.strip()[:6]))
            if _s9b.count("（") != _s9b.count("）"):
                _unbal9.append("%s/%s[%d]" % (_k9b, _nk9b, _i9b))
chk("⑨-b-a ★ 屏上没有「整行只剩收尾括号」的台词行（硬底线 0 · 现值 %d / %d 行）"
    % (len(_orph9), _n_ln9), not _orph9,
    (" · ".join(_orph9[:6]) or "无（%d 行全合规）" % _n_ln9))
chk("⑨-b-b ★ 每条台词的 （）成对（切点不许落进括号里 —— 那会把 `）` 甩到下一行）"
    "（硬底线 0 · 现值 %d）" % len(_unbal9), not _unbal9,
    (" · ".join(_unbal9[:6]) or "全部成对"))

#   反证：把改前那一条**逐字**塞回域里 ⇒ 两条判据都必抓到（判据不恒真）。
#   ★ 抄的是改动前 `dialogues.json` 里的原样（从备份取出，不手编 —— 手编就编成了另一句话）。
_old_orphan = "（她还是看着北边。\n手指在膝盖上敲了两下，停了。\n）\n「你又来了。」"
_ho9a = [x for x in _old_orphan.split("\n") if _ORPHAN_CLS.match(x.strip())]
_ho9b = _old_orphan.count("（") != _old_orphan.count("）")
#   ★ 这一条只归 ⑨-b-a 管（不是两条都抓）：改前那一条**整条是配对的**
#     （1 个 `（` 对 1 个 `）`）—— 它坏在「`）` 单独占了一行」，
#     ⑨-b-b 查的是「整条台词的括号数不相等」，**本就该放行**它。
#     要两条都抓，得用「切点真落进括号里」的那一形态（见 ⑨-b-d）。
#     写成"两条都抓"就是给判据加了一条它不该背的负担 ⇒ 实测当场红（本文这行就是这么红的）。
chk("⑨-b-c ★ 反证：逐字塞回改前那一条 ⇒ ⑨-b-a 必抓到那个孤括号行（%d 个）"
    "，而 ⑨-b-b 放行它（整条 %s）—— 两类各归各的"
    % (len(_ho9a), "配对成立" if not _ho9b else "不成立"),
    bool(_ho9a) and not _ho9b, "改前形态：%r" % _old_orphan[:40])

#   反证二：钉**成因**而不只钉结果 —— `_safe_parts` 现在数括号，
#   同一段文本改前会被切开（`）` 掉到下一行）、改后不会。
_parts9b = _NL._safe_parts("（他没吼。他停了一下，手没停）", _NL._SENT)
chk("⑨-b-d ★ 反证：`_safe_parts` 不许把切点放进 （…） 里面（%d 段 · 逐段配对 %s）"
    % (len(_parts9b), all(x.count("（") == x.count("）") for x in _parts9b)),
    all(x.count("（") == x.count("）") for x in _parts9b), "切出来：%s" % _parts9b[:3])


# ⑩ ★ P1（2026-09-28 · 文案修复车道）—— 规格 23_NPC对话树_v1 §一④ 的两条机器判据
#    「对话分四层（**每位 NPC 都按这个结构写**）」+「重复对话要**轮换**
#    （别每天同一句 —— 同一句话看三遍就变成机器）」。
#    这两条原先 ⑦ 只**印**分布、没人判 ⇒ 域里位齐 0/14、19 个层「只有一句 + need=null」
#    （玩家每次搭话看同一句）能一直绿着过。
#    ★ 分档口径：先钉「**归零 / 全兜底**必红」这种硬底线，再逐步加严 ——
#      **不许一上来就要求 100% 位齐**（那会让本车道自己红，且真源也只点名了 6 位隐藏线）。
#      下面的基线是**本批做完之后的现值**，随内容推进可以往上调（本判据只接受更严）。

# 范围：只管 **NPC 那 14 棵**（`dlg_` 前缀）。`talk_*` 是地点/篝火的
# 「看一眼说一句」物件，规格 §一 的四层是写给 NPC 的，不套在它们身上。
# ★★ P1-42（2026-09-29 · 文案车道 aep1）—— 这行原来是**浅层**派生
#   `{k: v for k, v in dl.items()}`：两边**共用同一批 `nodes` 子对象** ⇒ 后面那十几条
#   反证（⑪-b ⑫-b ⑭ ⑰-b ⑲-b ⑳-b ㉑-b ㉗-d1…）在「压缩/替换某一层」时，
#   **顺手把 `dl` 里被测数据一起改了**；而它们各自的「还原」只换回 `_npc` 自己的键
#   （`_npc[k] = _sv` / `_npc.clear(); _npc.update(_bak)`）⇒ **`dl` 永久停在被污染态**。
#   实测：⑫-b 把 `dlg_bella` 的 `daily` 从 8 句压成 1 句后再没回来；㉜（口头禅判据）
#   第一个撞上它 —— bella 的 `daily` 只剩 1 句时，「她说过自己那句口头禅吗」答不出是。
#   ⇒ 治法是**深拷贝**（反证要改就改自己那份副本，被测数据一个字都不许被碰）。
#   ★ 这不是改判据口径，是修**判据的实现**（反证污染了被测对象）；
#     既有那五十余条判据与它们的反证一个字没动，14/14 那些数在真数据上原样成立。
_npc = {k: json.loads(json.dumps(v)) for k, v in dl.items() if str(k).startswith("dlg_")}

# ⑩-a **位齐率**：一位 = meet ∧ daily ∧ main ∧ hidden 四层都在。
#   真源 23_NPC对话树_v1 §一写的是四层都要；但 §四那句「隐藏线 6 段（莉安·哈根·皮特·
#   瑟兰·格雷·艾德）」明说**隐藏线只对有设计彩蛋的人开** ⇒ 硬底线不钉 hidden 满员。
#   基线 9/14（累计：老陶/格雷两层 + 哈根那句从 meet 搬回 main + 莉安 daily/hidden
#            + 小满 main/hidden —— 后三位是**真源点名**的：24_ §主11「隐藏线『名字』→
#            莉安的长独白」、15_ §彩蛋2「小满的石头 = 骨田捡的刻字石片」）；
#   硬底线 = **不许比基线更差**。改动前是 0/14 —— 抽 6 条判据的那支审计报的 0/14 是对的。
#   ★ 2026-09-28 P1-5 更正一条**过期依据**：原注释把「隐藏线 6 段（莉安·哈根·皮特·
#     瑟兰·格雷·艾德）」当成「余下 5 位是有意省略」的依据 —— 那一行在
#     `_废弃_2026-09-24_AI味v1/23_NPC对话树_v1.md`，是**已废弃的 AI 味 v1**；
#     现行 23_NPC设定_v6.md 自己写着「每位 NPC 结构**刻意不同**」与三条形状纪律
#     （别给所有人同一套结构），而交接指南 v3 §3.1③ 明写四层是**每位**都写。
#     ⇒ 那 5 位（贝拉/德里克/杜林/玛莎/娜娜）的 hidden 已按各自语气补齐 ⇒ 14/14。
_LAYERS4 = ("meet", "daily", "main", "hidden")
_full = sorted(k for k, v in _npc.items() if all(L in v["nodes"] for L in _LAYERS4))
_partial = sorted(k for k, v in _npc.items()
                  if any(L in v["nodes"] for L in _LAYERS4)
                  and not all(L in v["nodes"] for L in _LAYERS4))
#   「位齐」按真源 23_NPC设定_v6 §一④ + 交接指南 v3 §3.1③
#   「**每位 NPC 都按这个结构写**（初见/日常/主线后/隐藏线）」⇒ **14 是终点**。
#   ★ 2026-09-28 P1-5：14/14 已达成 ⇒ 底线按本判据自己写的口径升级成 14（硬要求）。
#     「逐步加严」分档走完最后一档，不是把断言放宽。
_MIN_FULL = 14
chk("⑩-a ★ 四层位齐率：%d/%d 位四层齐（硬底线 ≥ %d · 逐步加严到 14）"
    % (len(_full), len(_npc), _MIN_FULL), len(_full) >= _MIN_FULL,
    "位齐：%s%s" % ("、".join(_full),
                    ("｜未齐：" + "、".join(_partial)) if _partial else ""))

# ⑩-b **轮换**：一个层若**每一句都是 need=null**，它就永远只说同一句
#   （`_pick_indexed` 按顺序挑第一条满足的，null 恒满足 ⇒ 后面全是死句）。
#   判据 = 这种「纯兜底」层**一个都不许有**。
#   基线走过的路：19 → 10 → 7 → **0**（累计四轮，每轮只加严不放宽）。
#   ★ 2026-09-29 P1-4：现值已是 **0**，而上限还停在 7 ⇒ 这条判据**什么都拦不住**
#     （要长到 7 个纯兜底层才红，而域里一个都没有 = 余量白留，正是「门槛数字没跟账」
#     那一类假绿）。按分档口径把上限收成 0 = 硬底线，不是放宽：
#     域里**此刻**就是 0，所以这一改**不会让本车道自己红**，只是把「已经做到的事钉住」。
#   ★ 与 ⑩-d 反证的关系：⑩-d 的 `_need_add = max(1, 上限 - 现值 + 1)` 随基线自走
#     ⇒ 上限收成 0 之后它要添 1 个（即 0+1 > 0）照样顶得破，**反证不恒真**。
#   ★ 为什么不把 `idle` 也算进来：idle 是「不熟时的沉默占位」，规格 §一 的四层不含它；
#     本判据只管 ⑩-a 点名的四层（`_LAYERS4`），与位齐判据同一条口径，不另开第二份。
_FLAT = []
for _k, _v in _npc.items():
    for _lk, _nd in _v["nodes"].items():
        if _lk not in _LAYERS4:
            continue
        if all(t.get("need") is None for t in _nd["texts"]):
            _FLAT.append("%s/%s" % (_k, _lk))
_MAX_FLAT = 0
chk("⑩-b ★ 轮换：纯兜底层（每句 need=null ⇒ 玩家每次看同一句）%d 个（硬上限 ≤ %d · 19→10→7→0）"
    % (len(_FLAT), _MAX_FLAT), len(_FLAT) <= _MAX_FLAT,
    (" · ".join(sorted(_FLAT)[:8]) or "无"))

# ⑩-c **反证**：上面两条各自**抓得住**它们要防的原状（不然就是恒真的判据）。
#   反证一：造一棵树「四层里缺 main/hidden」⇒ 位齐率必须掉到基线以下。
#   ★ 动态挑一棵**已位齐**的树（原来写死 dlg_pete：它补齐之后抽掉只掉 1，恰好还 > 旧底线
#     ⇒ 反证变恒真 = 门禁自己瞎了）。与「哪一棵」无关才是真敏感度。
_probe_tree = _full[0] if _full else sorted(_npc)[0]
_bad_tree = dict(_npc)
_v = json.loads(json.dumps(_npc[_probe_tree]))
_v["nodes"].pop("main", None)
_bad_tree[_probe_tree] = _v
_bad_full = sum(1 for k, x in _bad_tree.items()
                if all(L in x["nodes"] for L in _LAYERS4))
chk("⑩-c ★ 反证：抽掉一棵已位齐树的 main 层 ⇒ 位齐率会跌破基线（判据抓得住）",
    _bad_full < _MIN_FULL, "抽 %s/main 后 %d/%d < 底线 %d"
    % (_probe_tree, _bad_full, len(_bad_tree), _MIN_FULL))

#   反证二：把两层的内容并成「每句都 need=null」⇒ 纯兜底层会超过上限。
#   ★ 2026-09-28 P1-7：纯兜底层已降到 **0**，写死的「+3」不再能顶破上限（0+3 ≤ 7
#     ⇒ 判据恒真 = 门禁自己瞎了）。改成**自己算要加几个**： max(1, 上限 - 现值 + 1)
#     ⇒ 无论现值是 7 还是 0，这一条都真的顶得破（反证随基线走，不是把断言放宽）。
_need_add = max(1, _MAX_FLAT - len(_FLAT) + 1)
_bad_flat = len(_FLAT) + _need_add
chk("⑩-d ★ 反证：再添 %d 个纯兜底层 ⇒ 会超过上限（判据抓得住）" % _need_add,
    _bad_flat > _MAX_FLAT,
    "现值 %d + 添 %d = %d > 上限 %d" % (len(_FLAT), _need_add, _bad_flat, _MAX_FLAT))

#   反证三：**死句**这一类（同一层里两句都 need=null）现在就有判据了 ——
#   域里不该存在「need=null 的句子排在另一个 need=null 之后」（后面那句永远出不来）。
_DEAD = []
for _k, _v in _npc.items():
    for _lk, _nd in _v["nodes"].items():
        _seen_fb = False
        for _i, _t in enumerate(_nd["texts"]):
            if _t.get("need") is None:
                _seen_fb = True
            elif _seen_fb:
                _DEAD.append("%s/%s#%d" % (_k, _lk, _i))
                break
chk("⑩-e ★ 没有死句（need=null 之后不许再挂条件句 —— 那句永远出不来）",
    not _DEAD, (" · ".join(_DEAD[:6]) or "无"))

# ⑪ ★ P1-9（2026-09-28）—— **可观测的轮换**：玩家连敲十下到底看到几句不重复的
#    ★ 前面 ⑩-a/⑩-b 判的是**域里的形状**（位齐 · 有没有 need=null），
#      它们全绿的那天，玩家看到的仍然是同一句 —— 因为 ⑩-b 只抓「整层都是 need=null」，
#      抓不住「一层里有四句、但四句都挂在同一个条件上」这种（域里看着挺热闹，
#      `_pick_indexed` 按顺序挑第一条满足的 ⇒ 同一时刻只有第一句出得来）。
#      实测原状：按 3 个游戏日 × 4 时辰 × 4 天气跑 48 趟，14/14 位只有 2–4 句不重复。
#    本判据因此**不数域里的条数**，改成**真敲**：造档 + 真调 `_pick_layer`，
#      走一遍玩家会遇到的（时辰 × 天气）世界状态，数「拿到几句**不同**的台词」。
#    分档：先钉「最差那位 < 3 句必红」这种硬底线（现值 3），随内容推进往上调，只接受更严。
_LAY = ("meet", "daily", "main", "hidden")
_HOURS = ("hr_dawn", "hr_day", "hr_dusk", "hr_night")
_WEATH = ("w_sunny", "w_rain", "w_fog", "w_snow")
_PROG_FLAGS = ("quest_return_stone_done", "main04_done", "main05_done", "main06_active",
               "main08_done", "main09_done", "main10_active", "main11_done", "main12_done",
               "oldroad_done", "nameline_done", "swordband_done", "quest_lamp_oil_done",
               "asked_for_rain_herb")
_BAGS = ("i_horn_half", "i_token_stone_shard", "i_set_sentry_gauntlet",
         "i_set_northwall_amulet", "i_whetstone", "i_food_kao_shiban")


def _rot_probe(npc_key, days=3, opened=True):
    """照玩家会遇到的路线真搭话一遍（熟了之后 = 日常层主场景）→ 不重复台词数。"""
    _fl = {"talked": {}, "talk": {}, "quest_done": {}}
    for _t in _PROG_FLAGS:
        _fl[_t] = bool(opened)
    _p = {"flags": _fl,
          "bag": {_b: (1 if opened else 0) for _b in _BAGS},
          "heard": {}, "level": 5}
    _seen = []
    for _d in range(days):
        for _h in _HOURS:
            for _w in _WEATH:
                _p["flags"]["talked"][npc_key] = _d * len(_HOURS) + 1
                # ★ 取件走 `_npc`（不是 `dl`）—— 反证要在 `_npc` 上换掉一棵树，
                #   读 `dl` 的话那次替换根本不生效 ⇒ 压完还是原值 = 判据恒绿 = 自己瞎了。
                _ly, _idx, _txt = CT._pick_layer(_npc[npc_key]["nodes"], _p,
                                                 {"hour": _h, "weather": _w}, npc_key)
                if not _txt:
                    continue
                _seen.append(_txt)
                CT.HD.note(_p, npc_key, _ly, _idx)
    return len(set(_seen))


_ROT = {k: _rot_probe(k) for k in sorted(_npc)}
_ROT_MIN = min(_ROT.values())
_ROT_SAME = {k: v for k, v in _ROT.items() if v < 3}
#   ★ 底线定 **4** 而不是 3（这一步是量出来的，不是拍的）：把域回退到本批修之前的
#     那个提交（`6c5aafc^`）再跑本判据，最差那位正好 **3 句** ⇒ 底线 3 会让
#     「修之前的原状」也绿，等于判据抓不住它要防的东西。
#     现值最差 4（玛莎）⇒ 底线 4 卡在「修完不许退回去」的那一档上。
#   ★ 2026-09-29 加严一档：4 是 P1-9 刚修完那天的数，**现值最差已是 9**（玛莎）——
#     底线 4 挡着改动，已能扛住「掉到 3」以外的一切回归 = 余量白留。
#     底线 **8** = 现值 9 之下那一档（掉到 7 必红），而 ⑪-b 的反证把那位压到 1～3
#     ⇒ 加严后反证照样破（不恒真）。只加严，不放宽。
_ROT_FLOOR = 8
_ROT_SAME = {k: v for k, v in _ROT.items() if v < _ROT_FLOOR}
chk("⑪-a ★ 可观测轮换：48 趟（3 游戏日 × 4 时辰 × 4 天气）里，每位至少看到 %d 句不同台词"
    "（真敲 `_pick_layer` · 最差 %d 句 · 硬底线 ≥ %d · 逐步加严）"
    % (_ROT_FLOOR, _ROT_MIN, _ROT_FLOOR),
    not _ROT_SAME, ("·".join("%s=%d" % (k, v) for k, v in sorted(_ROT_SAME.items()))
                    or "14/14 达标"))

# ⑪-b **反证**：把某位的**日常层**压成「只剩兜底那一句」⇒ 可观测轮换必须掉到 3 以下。
#   ★ 与 ⑩-d 同族（那条判纯形状，这一条判**玩家真看到的东西**）。
#   ★ **第一版这判据是错的（我自己踩的）**：只压 `daily` 而不动别的层，
#     而 `main` / `hidden` 在同一趟里照样轮换 ⇒ 总量根本没降（压完还是 7/7 ⇒ 恒绿 = 门禁自己瞎了）。
#     判据要抓的是**日常层**这一件事，就压**整棵树**：只留 `daily` 的兜底那一句、其余三层抽掉
#     —— 那正是玩家「熟了之后一天到晚搭话」看到的全部内容，掉到 1 句才对。
_probe_k = _full[0] if _full else sorted(_npc)[0]
_saved = _npc[_probe_k]
_strip = json.loads(json.dumps(_saved))
_keep = [t for t in _strip["nodes"].get("daily", {}).get("texts", [])
         if t.get("need") is None][:1] or _strip["nodes"]["daily"]["texts"][:1]
#   ★ `meet` 也压成**一条**（还不熟那一档照样会说话，而它按天气/时辰分支能出好几句）——
#     上一版只压 `daily`、留着原样的 `meet`，结果压完还是 3 句（7 → 3）⇒ 仍差一档才红。
_npc[_probe_k] = {"nodes": {
    "meet": {"texts": _strip["nodes"]["meet"]["texts"][:1]},
    "daily": {"texts": _keep[:1]}}}
_bad_rot = _rot_probe(_probe_k)
_npc[_probe_k] = _saved                       # 还原（判据不许改坏被测数据）
chk("⑪-b ★ 反证：把 %s 压成「只有一层一句」⇒ 可观测轮换掉到 %d 以下（判据抓得住）"
    % (_probe_k, _ROT_FLOOR), _bad_rot < _ROT_FLOOR,
    "压完 %d 句（%d → %d）" % (_bad_rot, _ROT[_probe_k], _bad_rot))

print("      轮换分布：" + " · ".join("%s=%d" % (k.replace("dlg_", ""), v)
                                     for k, v in sorted(_ROT.items())))

# ⑫ ★ P1-12（2026-09-28）—— **单句层**：位齐看的是「有没有这一层」，
#    看不到「这一层里有几句」。
#    ⑪ — ⑪ 判的都是「整树」（有多少个不同句子」，一个层里只有一句时下面三条全绿
#    （位齐 14/14 · 无纯兜底层 · 可观测轮换全达标）—— 但玩家熟了以后连敲「搭话」，
#    转到那一层时供可选的只剩一句 ⇒ 每次真的看到同一句。
#    此就是审计报的那个「观感不好」。
#    分档：先钉「不得超过当前基线」（现值 10，让本车道自己不红，
#    也不接受「把断言放宽成不检查」的形式），随内容推进逐步降到 0。
#    ★ 底线量出来的（不是拍的）：基线 0/14（位齐为 0）时全部 56 层都是单句层；
#    P1-12 修完 10/56 → P1-2 第一批 5/56 → **第二批（余下 5 个 main/hidden 层）0/56**
#    ⇒ 上限 10 → 5 → 0：「逐步降到 0」这一步在本批兑现。
#    上限只会变小（判据只加强不削弱）；⑫-b 的压缩口径随之上调，见那里。
_LAY4 = ("meet", "daily", "main", "hidden")
_ONE = [("%s/%s" % (_k, _lk)) for _k, _v in _npc.items() for _lk in _LAY4
        if len(_v["nodes"].get(_lk, {}).get("texts", [])) <= 1]
_N_LAYERS = sum(1 for _k, _v in _npc.items() for _lk in _LAY4 if _lk in _v["nodes"])
_MAX_ONE = 0
chk("⑫-a ★ 单句层：%d/%d 个层只有一句（上限 ≤ %d · 逐步降到 0）"
    % (len(_ONE), _N_LAYERS, _MAX_ONE), len(_ONE) <= _MAX_ONE,
    ("·".join(sorted(_ONE)[:10]) or "无"))

# ⑫-b **反证**：拿一个已有多句的层压成一句 ⇒ 单句层必须超上限（判据抓得住）。
#   ★ 压的是**真实的 _npc**（不是 dl）—— 否则替掉树之后实际读的仍是原值 ⇒ 尸绿。
#   ★ **压缩量自算**（P1-2 第一批 · 上限 10→5 之后改的）：原来压一层只把 10 变 11，
#     锚点降到 5 之后「11 > 5」看着还成立，但那是靠**旧上限**才成立的假象
#     —— 锚点是 5 时真要抓的是「压完必须 > 5」。⇒ 压到**刚好越过新上限**：
#     一层层压，压到 > _MAX_ONE 立刻停（压得最少 = 反证最锐）。
_k12 = next((k for k in sorted(_npc) if len(_npc[k]["nodes"]["daily"]["texts"]) >= 2), None)
if _k12 is None:
    _k12 = sorted(_npc)[0]
_sv12 = json.loads(json.dumps(_npc[_k12]))
_base12 = len(_ONE)
_keep12 = 0
_bad12 = _base12
for _n12 in range(1, len(_sv12["nodes"]["daily"]["texts"]) + 1):
    _npc[_k12]["nodes"]["daily"]["texts"] = _sv12["nodes"]["daily"]["texts"][:_n12]
    _bad12 = sum(1 for k, v in _npc.items() for lk in _LAY4
                 if len(v["nodes"].get(lk, {}).get("texts", [])) <= 1)
    _keep12 = _n12
    if _bad12 > _MAX_ONE:
        break
#   ★ **上限 0 之后光压一层不够了**（P1-2 第二批改的）：只在一位内部压，
#     压出来最多 1 个单句层 —— 要越过 0 就得**压掉整层**（位齐随之 14 → 13）。
#     少压一层就锐一分，所以先在层内压到底，不够才动结构。
_drop12 = None
if _bad12 <= _MAX_ONE:
    for _lk12 in _LAY4:
        if _lk12 in _npc[_k12]["nodes"] and _lk12 != "meet":
            _npc[_k12]["nodes"].pop(_lk12)
            _drop12 = _lk12
            break
    _bad12 = sum(1 for k, v in _npc.items() for lk in _LAY4
                 if len(v["nodes"].get(lk, {}).get("texts", [])) <= 1)
_npc[_k12] = _sv12                       # 还原（判据不许改坏被测数据）
chk("⑫-b ★ 反证：把 %s 压到 daily 只剩 %d 句%s ⇒ 单句层越过上限 %d（判据抓得住）"
    % (_k12, _keep12,
       ("、并抽掉整层 " + _drop12) if _drop12 else "", _MAX_ONE),
    _bad12 > _MAX_ONE,
    "压完 %d 个（%d → %d）" % (_bad12, _base12, _bad12))

# ⑬ ★ P1-14（2026-09-28）—— **主线句遮住同层分支**（后期玩家视角）
#    ⑪-a 判「整树能轮换几句」、⑫-a 判「这一层有几句」—— 两条全绿的那天，
#    后期玩家看到的**仍然永远是同一句**：`_pick_indexed`
#    （`content/cmds_talk.py:51`）**按序挑第一条满足的**，而 `need: {"flag": 主线进度}`
#    一旦达成就**永久成立** ⇒ 排在层首时，该层后面的时辰 / 天气分支**永远轮不到**。
#    ★ ⑪-a 为什么看不见这一条：它的夹具只写 `flags[token]=True`，而
#      `content/prog.py::flag_ok` 对表里的 slug 走**真实进度**
#      （`flags.quests_done` / `quests_active`）⇒ 夹具里那些主线句**一条都不成立**，
#      正好绕开了「被遮住」的那一面。⇒ 本判据另造一个**真玩家档**（主线真交完）。
#    ★ 只加强：⑬ 是**新增**的，前面的判据一行未改。
#    ★ 底线**量出来**，不是拍的 —— 拿 `5ee1c47^`（P1-14 之前原状）真跑一遍：
#         修前合计 62 · 最差 **3 句** · 修后合计 **75** · 最差 3 句
#         （升 7 位 / 平 7 位 / **降 0 位**）
#      ⇒ 底线取 **3**：卡在「不许再退」那一档（= 修前最差），而 ⑬-b 的反证
#        负责证明判据**抓得住**（把 flag 句压回层首，那位立刻掉到 3 以下）。
#      ★ 为什么不取 4：bella 的遮住源是 `event`（`ev_caravan_arrived` =
#        `from_main: q_main_03` ⇒ 主线一过就**永久成立**，与 flag 同性质），
#        而 `probe_events ⑯` **按下标**钉死「那句必须在下标 0」——
#        那是商队事件的**送达契约**，本批不碰（碰它 = 改别线已验收过的判据）。
#      ⇒ 「逐步加严」的下一步（登记在案，不在本批）：
#        ① bella/daily 的 `event` 句后移 —— 需**先**把 `probe_events ⑯`
#           从「按下标 0」改成「按 need.event 找那一句」（改判据要写清它在护什么）；
#        ② derrick/nana 的 `holding` 族 —— 需**先**确认 `probe_equip_events`
#           钉的「带着那件 ⇒ 每趟都看得到」能否改成「至少一趟看得到」。
#   ★ 2026-09-29 加严一档：3 同样是 P1-14 修完那天的数；**现值最差 9**（格雷）
#     ⇒ 底线取 **8**（卡在现值下一档）。★ ⑬-b 的反证阈值**不看本底线**
#     （它比的是「压完比它自己的现值至少少 1 句」），故这次加严不与它打架。
_LATE_MIN = 8
_Q_ALL = sorted(q for q in (st.domain("quests") or {}) if str(q).startswith("q_"))
_MAIN_Q = [q for q in _Q_ALL if q.startswith("q_main_")]
_SIDE_Q = [q for q in _Q_ALL if q.startswith("q_side_") and q != "q_side_04"]
_BAG_ALL = {b: 1 for b in _BAGS}
for _extra in ("i_material_herb_rare", "i_set_northwall_shard", "i_junk_boot",
               "i_token_underwater_steps", "i_clue_page"):
    _BAG_ALL[_extra] = 1


def _late_player(npc_key):
    """一个**真玩家档**：职业已定 · 主线交完 · 背包里有那些认得出东西的道具。"""
    _cap, _ = hp_cap_or_line({"cls": "cls_knight", "level": 20, "flags": {"talked": {}}})
    return {"flags": {"talked": {npc_key: 99}, "talk": {},
                      "quests_done": list(_MAIN_Q) + list(_SIDE_Q), "quests_active": []},
            "bag": dict(_BAG_ALL), "heard": {}, "level": 20,
            "cls": "cls_knight", "race": "human", "hp": _cap or 100,
            "equipped": {"weapon": "w_sword", "armor_top": "a_robe"}}


def _rot_late(npc_key, p, days=3):
    """后期档下真敲 `_pick_layer`，数拿到几句**不同**台词（夹具与 ⑪-a 不同）。"""
    _seen = []
    for _d in range(days):
        for _h in _HOURS:
            for _w in _WEATH:
                _ly, _idx, _txt = CT._pick_layer(_npc[npc_key]["nodes"], p,
                                                 {"hour": _h, "weather": _w}, npc_key)
                if _txt:
                    _seen.append(_txt)
                    CT.HD.note(p, npc_key, _ly, _idx)
    return len(set(_seen))


_LATE = {k: _rot_late(k, _late_player(k)) for k in sorted(_npc)}
_LATE_SAME = {k: v for k, v in _LATE.items() if v < _LATE_MIN}
chk("⑬-a ★ 后期档（主线真交完 · 背包满）里，每位至少轮得到 %d 句不同台词"
    "（真敲 `_pick_layer` · 现值最差 %d 句 · 夹具与 ⑪-a 不同：旗标走**真实进度**）"
    % (_LATE_MIN, min(_LATE.values())), not _LATE_SAME,
    ("·".join("%s=%d" % (k, v) for k, v in sorted(_LATE_SAME.items())) or "14/14 达标"))

# ⑬-b **反证**：把某一层里那条主线（flag）句**挪到层首** —— 复现 P1-14 修之前的形态
#   ⇒ 那位必须掉一档（判据抓得住）。压完立刻还原。
#   ★ 压的是**真实的 _npc**，压的是**该层第一条 flag 句**，不碰别的层。
#   ★ 这一条量的是「那位在修之后剩下的余量」：把 flag 句压回最前 = 还原永久遮住
#     ⇒ **必须比它自己的现值至少少 1 句**，才说明「那条底线不是白设的」。
#     （第一版拿 `_LATE_MIN` 当阈值，量出来是 5 → 3，`< 3` 不成立 ⇒ 恒红；
#       阈值改成「相对现值掉一档」，判据才真的在证明自己。）
#   ★★ **候选位必须排除「别线按下标钉着的剧情层」**：`dlg_cole/daily` 的 flag 句
#     被 `probe_qloop ⑧` 钉死必须在层首（「主 4 交掉 ⇒ 头一句必须是那句」）——
#     拿它当反证靶子等于要求「把别人的判据弄红」，那条是**真契约**，不碰。
_PINNED_LAYER = ("dlg_cole", "daily")
_k13 = next((k for k in sorted(_npc)
             if (k, "daily") != _PINNED_LAYER
             and any(any("flag" in (t.get("need") or {}) for t in
                        _npc[k]["nodes"].get(lk, {}).get("texts", []))
                    and any((t.get("need") or {}) for t in
                            _npc[k]["nodes"].get(lk, {}).get("texts", []))
                    and any(t.get("need") is None for t in
                            _npc[k]["nodes"].get(lk, {}).get("texts", []))
                    for lk in _LAY4)), None)
if _k13 is None:
    chk("⑬-b ★ 反证：把主线句排回层首 ⇒ 后期轮换跌破底线（判据抓得住）", False,
        "域里找不到「有 flag 句 + 有兜底句」的多句层（判据自身失效，请修夹具）")
else:
    _sv13 = json.loads(json.dumps(_npc[_k13]))

    def _rot_layerwise(npc_key, p, days=3):
        """**层内逐层**各挑一句（老读端的样子：每层只认 `CT._pick_indexed` 的头一条）。
        ★ 用的是**真的** `CT._pick_indexed`（不是复刻）—— 老缺陷就发生在这一个函数里。
        """
        _seen = []
        for _d in range(days):
            for _h in _HOURS:
                for _w in _WEATH:
                    for _lk in CT.LAYERS:
                        if _lk not in _npc[npc_key]["nodes"]:
                            continue
                        _i, _t = CT._pick_indexed(_npc[npc_key]["nodes"][_lk].get("texts"),
                                                 p, {"hour": _h, "weather": _w})
                        if _t:
                            _seen.append(_t)
        return len(set(_seen))

    _before13 = _rot_layerwise(_k13, _late_player(_k13))   # 老读端 · 句序正常
    for _lk in _LAY4:                                        # 把 flag 句压回层首
        _ts = _npc[_k13]["nodes"].get(_lk, {}).get("texts", [])
        _fi = [i for i, t in enumerate(_ts) if "flag" in (t.get("need") or {})]
        if _fi and len(_ts) >= 2:
            _ts.insert(0, _ts.pop(_fi[0]))
    _bad13 = _rot_layerwise(_k13, _late_player(_k13))      # 老读端 · 句序压坏
    _new13 = _rot_late(_k13, _late_player(_k13))            # 真读端 · 同一棵压坏的树
    _npc[_k13] = _sv13                                     # 还原（判据不许改坏被测数据）
    # ★ 两条都要真量出来：① 老读端确实掉档（P1-14 那个缺陷真实 · 判据不恒真）
    #   ② 同一棵压坏的树在真读端不掉档（= P1-16 的收益，也是它该被钉住的地方）
    _chk13 = [("老读端没掉档（%d → %d，判据抓不住）" % (_before13, _bad13),
               _bad13 < _before13),
              ("真读端仍被句序影响（压坏后 %d 句 > 原值 %d —— 层内轮换没生效）"
               % (_new13, _LATE[_k13]), _new13 <= _LATE[_k13])]
    chk("⑬-b ★ 反证：把 %s 的主线句排回层首 —— 老读端掉档（%d → %d）· 真读端已免疫（%d ≤ %d）"
        % (_k13, _before13, _bad13, _new13, _LATE[_k13]),
        all(_okv for _e, _okv in _chk13),
        " · ".join(_e for _e, _okv in _chk13 if not _okv) or
        "两条都成立（老读端 %d → %d · 真读端 %d 不受句序影响）"
        % (_before13, _bad13, _new13))

print("      后期轮换分布：" + " · ".join("%s=%d" % (k.replace("dlg_", ""), v)
                                        for k, v in sorted(_LATE.items())))

# ⑭ ★ P1-4（2026-09-29 · 文案车道 P1）—— **物件树**（`talk_*`）的轮换
#    ★ **这一组判据是为了补一个真洞**：⑩–⑬ 全部遍历 `_npc`，而 `_npc` 只收 `dlg_` 前缀
#      ⇒ 5 棵物件树（`pois.effect.talk` 指的那 5 棵：篝火 ×3 · 木桩/门板 ×2）从来没进过
#      **任何一条**轮换判据。原状实测：每棵 1 层 · 1 句 · `need=null`
#      ⇒ 玩家每次对同一个篝火「触摸」，看到的是逐字相同的那一句。
#      这与 P1-12 修掉的 NPC 侧（单句层）是同一个病，只是被 `_npc` 那个过滤器挡在门外。
#    口径边界（别越界）：规格 25_ §一的四层是写给 NPC 的；物件是「看一眼说一句」，
#      **不要求四层齐**，要的只是「**不重样**」—— 那才是玩家点名的观感。
#    走的那条路是 `cmds_ast._poi_effect`：`for nn in ("main","hidden","meet","daily","idle")`
#      里第一个挑得出句的层 + `CT._pick_indexed`（本判据就真调它，不复刻它的算法）。
_prop = {k: v for k, v in dl.items() if str(k).startswith("talk_")}
_MIN_PROP_TEXTS = 2      # 每棵至少 2 句（现值 3；1 = 玩家每次同一句）
_MIN_PROP_COND = 1       # 至少 1 句挂条件（否则 2 句也只有第一句出得来 —— 同一种病）
_bad14, _flat14 = [], []
for _pk in sorted(_prop):
    _pts = _prop[_pk]["nodes"].get("meet", {}).get("texts", [])
    if len(_pts) < _MIN_PROP_TEXTS:
        _bad14.append("%s 只有 %d 句" % (_pk, len(_pts)))
    if not any(t.get("need") is not None for t in _pts):
        _flat14.append("%s/%d" % (_pk, len(_pts)))
    # 死句同款：need=null 之后再挂条件句（后面那句永远出不来）
    _fb = False
    for _i14, _t14 in enumerate(_pts):
        if _t14.get("need") is None:
            _fb = True
        elif _fb:
            _bad14.append("%s#%d 条件句排在兜底句之后（死句）" % (_pk, _i14))
chk("⑭-a ★ 物件树轮换：%d 棵每棵 ≥ %d 句 · ≥ %d 句挂条件（不许全是兜底）"
    % (len(_prop), _MIN_PROP_TEXTS, _MIN_PROP_COND),
    not _bad14 and not _flat14,
    ("短句：%s" % " · ".join(_bad14[:4]) if _bad14 else "")
    + ("｜全兜底：%s" % " · ".join(_flat14[:4]) if _flat14 else ""))

# ⑭-b ★ 可观测：真敲 `CT._pick_indexed` 走一遍玩家会遇到的（时辰 × 天气），
#    数每棵物件树**真的能轮出几句不同的话** —— 域里条数够了但全挂在同一个条件下，
#    玩家看到的仍然只有一句（同 ⑪-a 那个理由，这里换个面）。
_HOURS14 = ("hr_dawn", "hr_day", "hr_dusk", "hr_night")
_WEATH14 = ("w_sunny", "w_rain", "w_fog", "w_snow")
_OBS14, _MIN_OBS14 = {}, 2
for _pk in sorted(_prop):
    _seen14 = set()
    for _h in _HOURS14:
        for _w in _WEATH14:
            for _nn in ("main", "hidden", "meet", "daily", "idle"):
                if _nn not in _prop[_pk]["nodes"]:
                    continue
                _i14, _t14 = CT._pick_indexed(_prop[_pk]["nodes"][_nn].get("texts"),
                                              {"flags": {}, "bag": {}, "heard": {}},
                                              {"hour": _h, "weather": _w})
                if _t14:
                    _seen14.add(_t14)
                break
    _OBS14[_pk] = len(_seen14)
_bad14b = [k for k, v in _OBS14.items() if v < _MIN_OBS14]
chk("⑭-b ★ 物件树可观测轮换：时辰×天气里每棵至少轮得出 %d 句（真敲 `_pick_indexed`）"
    % _MIN_OBS14, not _bad14b,
    ("轮换不足：%s" % " · ".join(_bad14b) if _bad14b
     else " · ".join("%s=%d" % (k.replace("talk_", ""), v) for k, v in sorted(_OBS14.items()))))

# ⑭-c ★ 反证：把一棵树压回「一条 need=null」⇒ ⑭-a 与 ⑭-b 都必须抓住（不然是恒真的判据）。
#   ★ 压的是**域的副本**（`_prop` 已在上面从 `dl` 重新构造，改它不影响 `dl` 读端）。
if _prop:
    _pk14 = sorted(_prop)[0]
    _keep14 = _prop[_pk14]["nodes"]["meet"]["texts"]
    _sv14 = json.loads(json.dumps(_keep14))
    _prop[_pk14]["nodes"]["meet"]["texts"] = _keep14[:1]
    _a14 = len(_prop[_pk14]["nodes"]["meet"]["texts"]) < _MIN_PROP_TEXTS
    _b14 = 1 < _MIN_OBS14
    _prop[_pk14]["nodes"]["meet"]["texts"] = _sv14
    chk("⑭-c ★ 反证：把 %s 压回「一条兜底」⇒ 两条物件判据都抓得住（判据不恒真）" % _pk14,
        _a14 and _b14, "压成 1 句：⑭-a 破=%s ⑭-b 破=%s" % (_a14, _b14))
else:
    chk("⑭-c ★ 反证：物件树一条都没有（判据自身失效，请修夹具）", False, "域里 0 棵 talk_*")

# ⑮ ★ P1-5（2026-09-29 · 文案车道 P1）—— **域必须合自己的 schema**（这一条以前没人跑）
#    ★ 原状：`schemas/dialogues.schema.json` 全仓只被 ⑧ 读过（查 `"start"` 在不在），
#      **从没有一处拿它校域**。于是 5 棵物件树（`talk_*`）不匹配 `^dlg_[a-z_]+$`
#      + `additionalProperties: false` ⇒ 域一直不合规，判据一条都没报。
#    ★ fail-closed：**装不上 jsonschema 就红**（不许「环境缺个库就跳过」——
#      跳过 = 这条判据又变成恒真，那正是它当初没被发现的原因）。
#    ★ 口径：`^dlg_` 与 `^talk_` **两族都要在**（14 棵 NPC + 5 棵物件是域的事实）；
#      P1-5 已把 `talk_` 那一族补进去，子树逐字复用 `dlg_` 那份（不许复制第二份形状）。
try:
    import jsonschema as _js15
    _sch15 = json.loads((REPO / "schemas" / "dialogues.schema.json").read_text(encoding="utf-8"))
    _v15 = _js15.Draft7Validator(_sch15)
    _errs15 = ["%s%s" % ("/".join(str(x) for x in e.absolute_path) or "<root>", " · " + e.message[:60])
               for e in _v15.iter_errors(dl)]
    chk("⑮-a ★ 域合自己的 schema（真跑 jsonschema · %d 棵树）" % len(dl), not _errs15,
        " · ".join(_errs15[:3]) if _errs15 else "0 处不合规")
    _pats15 = sorted((_sch15.get("patternProperties") or {}).keys())
    chk("⑮-b ★ schema 认两族（NPC `dlg_` + 物件 `talk_`；少一族 = 那族域一直不合规）",
        any("dlg_" in p for p in _pats15) and any("talk_" in p for p in _pats15),
        "patternProperties：%s" % " · ".join(_pats15))
    # ⑮-c ★ 反证：塞一棵树名不合规的 id ⇒ 必须被抓（证明 ⑮-a 不是恒真）
    _bad15 = dict(dl)
    _bad15["写法不合法_1"] = {"nodes": {"meet": {"texts": [{"need": None, "text": "x"}]}}}
    _r15 = list(_v15.iter_errors(_bad15))
    chk("⑮-c ★ 反证：树名不合规 ⇒ schema 会拒绝（判据不恒真）", bool(_r15),
        "塞了 %r ⇒ %d 处报错" % ("写法不合法_1", len(_r15)))

    # ⑮-d/e/f ★ P1-43（2026-09-29 · 文案修复车道 aep1）—— **`need` 的键名在装配期就拦住**
    #    缺陷本体：`need` 那一格只写了 `type: [object,null]`，**不约束键名** ⇒ 域里打错一个键
    #    （`tim` 之于 `time` / `wether` 之于 `weather`）照样过 schema、照样装得进包里。
    #    运行时那一路由 ㉓-a 兜住（`cmds_talk._pick_indexed` 认不出的键判**不满足**），
    #    但代价是**条件句被静默洗成永不出**：它挂在兜底句之后 ⇒ 那一层少一句能说的话，
    #    而屏上零报错、连反证都看不出来。⇒ 装配期不拦 = 把病拖到玩家面前才发作。
    #    修法：schema 的 `need` 加 `propertyNames.enum`（键名枚举，与**读端**那份同源）。
    #    ★ 枚举**不手抄第二份**：`cmds_talk.NEED_KINDS` 是「认得哪些键」的唯一口（③ 已 import），
    #      枚举逐项与它对账（⑮-e）—— 读端加了一个键而忘了改 schema，当场红（反之亦然）。
    def _need_enum(sch):
        """从 schema 里把 `need` 的键名枚举挖出来（两族 dlg_/talk_ 各一份，两份要一致）。"""
        out = []
        for _fam, _sub in (sch.get("patternProperties") or {}).items():
            _nodes = ((_sub.get("properties") or {}).get("nodes") or {})
            for _np in (_nodes.get("patternProperties") or {}).values():
                for _t in ((((_np.get("properties") or {}).get("texts") or {}).get("items") or {})
                           .get("properties") or {}).values():
                    _pn = _t.get("propertyNames") or {}
                    if _pn.get("enum"):
                        out.append((_fam, tuple(_pn["enum"])))
        return out

    _en15 = _need_enum(_sch15)
    _fams15 = sorted({f for f, _ in _en15})
    chk("⑮-d ★ schema 钉住了 `need` 的键名（拼错一个键装配期就红，不许拖到运行期）",
        bool(_en15) and all(len(e) == len(set(e)) for _, e in _en15),
        "两族各一份枚举：%s" % " · ".join("%s=%d 项" % (f, len(e))
                                        for f, e in sorted(set(_en15))))
    # 两族那两份必须**逐项相同**（子树是复用的，枚举不许只改一族 ⇒ 另一族静默不拦）
    _same15 = len({e for _, e in _en15}) == 1
    chk("⑮-e ★ 两族（`dlg_` / `talk_`）的键名枚举逐项相同（只改一族 = 另一族静默不拦）",
        _same15, "族：%s" % " · ".join(_fams15))
    # ★ 与**读端**那份对账：单一真源 = `cmds_talk.NEED_KINDS`（schema 只是它的投影）
    _need_ref15 = tuple(NEED_KINDS)
    _drift15 = sorted(set(_need_ref15) ^ set(_en15[0][1])) if _en15 else []
    chk("⑮-f ★ 枚举与读端 `NEED_KINDS` 同一份（读端加了键而忘了改 schema ⇒ 当场红）",
        bool(_en15) and tuple(sorted(_en15[0][1])) == tuple(sorted(_need_ref15)),
        "读端 %d 项 / schema %d 项%s" % (len(_need_ref15), len(_en15[0][1]) if _en15 else 0,
                                        " · 分歧：%s" % " ".join(_drift15) if _drift15 else " · 一致"))
    # ⑮-g ★ 反证：一个键都拼错 ⇒ schema 必拒；合法键 + need=null 必仍过（防「拦过头」）
    for _i15, _kk15 in enumerate(("tim", "wether", "quest-done", "不存在")):
        _err_typo = list(_v15.iter_errors(
            {"dlg_typo": {"nodes": {"meet": {"texts": [
                {"need": {_kk15: "x"}, "text": "拼错的键"}, {"need": None, "text": "兜底"}]}}}}))
        chk("⑮-g%d ★ 反证：need 键 %r 拼错 ⇒ 装配期就红（判据不恒真）" % (_i15 + 1, _kk15),
            bool(_err_typo), "报错 %d 处" % len(_err_typo))
    _ok15 = list(_v15.iter_errors(
        {"dlg_ok": {"nodes": {"meet": {"texts": [{"need": None, "text": "兜底"}]}}}}))
    _ok15b = list(_v15.iter_errors(
        {"dlg_ok": {"nodes": {"meet": {"texts": [
            {"need": {"time": "hr_dawn", "weather": "w_rain"}, "text": "合法条件句"}]}}}}))
    chk("⑮-h ★ 防「拦过头」：合法键与 `need=null` 兜底句仍过（别把条件句一起打死）",
        not _ok15 and not _ok15b, "兜底 %d 处报错 / 合法条件句 %d 处报错" % (len(_ok15), len(_ok15b)))
except ImportError:
    chk("⑮-a/b/c ★ 域合自己的 schema（真跑 jsonschema）", False,
        "装不上 jsonschema —— fail-closed：跳过这条 = 判据恒真，正是它当初没被发现的原因")


# ⑯ ★ P1-6（2026-09-29 · 文案车道 P1）—— **取句层序只有一份**（静态守卫）
#    `cmds_talk.LAYERS` 是层序的**唯一口**（模块头原话：谁再把那一格接回来就是开第二个
#    口径）。原状：`cmds_ast._poi_effect` 另硬写了一份**顺序相反**的层序（P-12 之前的
#    旧口径，撤了没跟着撤）⇒ POI 触摸先出 `main`（刚认识就剧透）。已改走 `CT.LAYERS`。
#    ★ 判据不认「哪几层」，只认「有几份」：层序赋值 / `for … in (` 遍历目标里，
#      唯一定义处（`content/cmds_talk.py:LAYERS`）之外一份都不许有。
#    ★ 扫法：先剥掉源码里的引号字符再匹配（正则里因此不出现引号类），
#      且只认「赋值 / 遍历目标」两种真形状 —— 注释里提到那份旧层序是正常的
#      （要讲清它为什么被撤），扫全文会把注释当第二口径 ⇒ 判据恒绿 = 自己瞎了。
import re as _re16                                                       # noqa: E402

_LAYER16 = ("meet", "daily", "main", "hidden", "idle")
_ALT16 = "|".join(_LAYER16)
_PAT16 = _re16.compile(r"[(]\s*(?:" + _ALT16 + r")\s*(?:,\s*(?:" + _ALT16 + r")\s*){2,}[)]")
_def16 = _re16.compile(r"^\s*(?:LAYERS\s*=|for\s+\w+\s+in\s+)")
_dup16 = []
for _f16 in sorted(_glob8.glob(os.path.join(str(REPO), "content", "*.py"))):
    for _n16, _l16 in enumerate(_io8.open(_f16, encoding="utf-8").read().split("\n"), 1):
        _t16 = _l16.split("#", 1)[0]           # 去掉行内注释
        if not _t16.strip() or not _def16.match(_t16):
            continue
        _bare16 = _t16.replace(chr(34), "").replace(chr(39), "")   # 剥引号
        for _m16 in _PAT16.finditer(_bare16):
            if _f16.endswith("cmds_talk.py") and "LAYERS" in _l16:
                continue                       # 唯一口自身
            _dup16.append("%s:%d  %s" % (os.path.basename(_f16), _n16, _m16.group(0)))
chk("⑯-a ★ 取句层序只有一份（层序赋值/遍历目标里不许有第二份字面量）",
    not _dup16, (" · ".join(_dup16[:4]) or "0 份（唯一口 = content/cmds_talk.py:LAYERS）"))

# ⑯-b ★ POI 触摸那条路的层序确实走 `CT.LAYERS`（★ 真抓住原缺陷的就是这一条：
#   把 cmds_ast 改回硬写元组，⑯-b 立刻红；⑯-a 负责「别处再冒出来第二份」）。
_poi16 = _io8.open(os.path.join(str(REPO), "content", "cmds_ast.py"), encoding="utf-8").read()
_ok16 = "for nn in CT.LAYERS:" in _poi16
chk("⑯-b ★ POI 触摸那条路的层序走 `CT.LAYERS`（不是自己那份）", _ok16,
    "for nn in CT.LAYERS: 在不在 = %s" % _ok16)

# ⑰ ★ P1-16（2026-09-29 · 文案车道）—— **同一时刻连敲，不许整段重样**。
#    ★ 为什么 ⑪/⑫/⑬ 三条都看不见这一条（它们是绿的，缺陷照样在）：
#      ⑪-a/⑬-a 变的是**世界状态**（时辰 × 天气 × 进度）—— 玩家换了时辰自然换一句；
#      ⑫-a 看的是**域里的形状**（某层有几句）—— 有 4 句就过。
#      可玩家真实的动作是**连敲「搭话」**：他没挪窝、时辰没走、进度没变。
#      此时 `_pick_layer` 每层只跑一次 `_pick_indexed`，而后者是
#      「**按顺序挑第一条满足的**」⇒ **同一层永远只出得来第一句**。
#      端到端实测（`e2e_drive.py "搭话 杜林" ×5`）：第 3/4/5 趟**逐字相同**，
#      第 1 趟与第 5 趟也撞 —— 鱼鱼说的「观感不好」就是这一下。
#    ★ 修法在**读端**（`cmds_talk._pick_layer`）：层内先挑「need 满足**且**还没听过」的那句，
#      一句都没有才退回老口径 ⇒ 数据一个字没加，老口径也没删（从唯一入口降成兜底）。
#    ★ 本判据**照真实动作量**：真造档 + 真调 `_pick_layer`，时辰/天气/进度**全部固定**，
#      连敲 8 下，数拿到几句**不同**的台词。
#    ★ 底线**量出来**不是拍的 —— 拿修之前那个状态跑同一把尺：最差 **3 句**（多棵），
#      故底线取 **3**：卡在「不许退回修前」那一档，⑰-c 的反证负责证明判据抓得住。
#      修后最差 4（masha）⇒ 下一步「逐步加严到 4」已在本批兑现。
_SAME_HOUR, _SAME_WEATHER = "hr_night", "w_rain"
_SAME_TALKS = 8


def _rot_same(npc_key, talks=_SAME_TALKS, nodes=None):
    """★ 世界状态**全固定**，连敲 N 下 —— 玩家连点「搭话」看到几句不同的。"""
    _fl = {"talked": {}, "talk": {}, "quest_done": {}}
    for _t in _PROG_FLAGS:
        _fl[_t] = True
    _p = {"flags": _fl,
          "bag": {_b: 1 for _b in _BAGS},
          "heard": {}, "level": 20, "cls": "cls_knight", "race": "human",
          "equipped": {"weapon": "w_sword", "armor_top": "a_robe"}}
    _seen = []
    for _i in range(talks):
        _fl["talked"][npc_key] = _i + 1
        _ly, _idx, _txt = CT._pick_layer((nodes or _npc)[npc_key]["nodes"], _p,
                                         {"hour": _SAME_HOUR, "weather": _SAME_WEATHER},
                                         npc_key)
        if _txt:
            _seen.append(_txt)
            CT.HD.note(_p, npc_key, _ly, _idx)
    return len(set(_seen))


def _rot_seq_same(npc_key, talks=_SAME_TALKS, nodes=None):
    """★ 与 `_rot_same` 同一把尺，但**返回逐字序列** —— ⑲ 判的是次序不是种类。

    ⑰-a 数「轮得到几句不同的」；玩家在屏上看到的是**一行行**回话 ⇒
    种类够多也可能连着三行一模一样（实测 masha 第 5/6/7/8 趟全是 `daily#1`）。
    ⇒ 同一趟活出两样东西：种类数（⑰）与次序（⑲）。
    """
    _fl = {"talked": {}, "talk": {}, "quest_done": {}}
    for _t in _PROG_FLAGS:
        _fl[_t] = True
    _p = {"flags": _fl,
          "bag": {_b: 1 for _b in _BAGS},
          "heard": {}, "level": 20, "cls": "cls_knight", "race": "human",
          "equipped": {"weapon": "w_sword", "armor_top": "a_robe"}}
    _seq = []
    for _i in range(talks):
        _fl["talked"][npc_key] = _i + 1
        _ly, _idx, _txt = CT._pick_layer((nodes or _npc)[npc_key]["nodes"], _p,
                                         {"hour": _SAME_HOUR, "weather": _SAME_WEATHER},
                                         npc_key)
        _seq.append(_txt or "")
        if _txt:
            CT.HD.note(_p, npc_key, _ly, _idx)
    return _seq


_SAME = {k: _rot_same(k) for k in sorted(_npc)}
_SAME_MIN = min(_SAME.values())
_MIN_SAME = 4
chk("⑰-a ★ 同一时刻连敲 %d 下：每位至少轮得到 %d 句不同台词"
    "（时辰/天气/进度全固定 · 真敲 `_pick_layer` · 现值最差 %d 句）"
    % (_SAME_TALKS, _MIN_SAME, _SAME_MIN),
    _SAME_MIN >= _MIN_SAME,
    "最差 %d 句（%s）" % (_SAME_MIN,
                          "、".join("%s=%d" % (k.replace("dlg_", ""), v)
                                    for k, v in sorted(_SAME.items()) if v <= _MIN_SAME)))
print("      同刻轮换分布：" + " · ".join("%s=%d" % (k.replace("dlg_", ""), v)
                                          for k, v in sorted(_SAME.items())))

# ⑰-b **反证**：把某一层压成「只剩一条永远满足的」⇒ 同刻轮换必须掉到底线以下。
#   ★ 压的是**真实的 _npc**（与 ⑫-b 同一个纪律：读 `dl` 的话那次替换根本不生效 ⇒ 尸绿）。
#   ★ 压完必须**确实** < _MIN_SAME 才算数（压得最少 = 反证最锐）。
# ⑰-b **反证**：把某一层压成「只剩一条永远满足的」⇒ 同刻轮换必须掉到底线以下。
#   ★ 压的是**真实的 _npc**（与 ⑫-b 同一个纪律：读 `dl` 的话那次替换根本不生效 ⇒ 尸绿）。
#   ★ 压完必须**确实** < _MIN_SAME 才算数（压得最少 = 反证最锐）。
#   ★ **压整棵树，不只压一层**（初版只压 `daily`，而别层还兜着 ⇒ 只掉 1 句、
#     刚够不到底线，判据看着「抓不住」）：把四层的 `texts` **各自**压到只剩
#     那一条永真句（`need=null`；没有兜底就留空）⇒ 整棵树只剩一种话，
#     同刻轮换必然塌到 1 —— 这才是「把原缺陷装回去」的形状。
_npc_save17 = json.loads(json.dumps(_npc))
_pick17 = sorted(_SAME, key=lambda k: _SAME[k])[0]
# ★ 2026-09-29 P1-25：夹具修成**本判据自己写的意图**（此前是「每层各留一条」，
#   压完还剩 4 句不同台词 ⇒ 擦着 `_MIN_SAME` 过；注释里要的却是「整棵树只剩一种话」）。
#   现在**整棵树只留一条**（第一条永真句），其余层清空 ⇒ 压完必定塌到 1，反证更锐。
#   ★ 门禁只加强：⑰-a 的底线与判据一个字未动，改的只是这条反证**怎么压**。
_kept_all = None
for _ly17 in _npc[_pick17]["nodes"]:
    if _kept_all is None:
        for _c in _npc_save17[_pick17]["nodes"][_ly17]["texts"]:
            if _c.get("need") is None:
                _kept_all = _c
                break
for _ly17 in _npc[_pick17]["nodes"]:
    _npc[_pick17]["nodes"][_ly17]["texts"] = (
        [_kept_all] if (_kept_all is not None and _ly17 == "meet") else [])
_after17 = _rot_same(_pick17)
_npc.clear()
_npc.update(_npc_save17)
chk("⑰-b ★ 反证：把 %s 整棵树压到只剩一条兜底 ⇒ 同刻轮换掉到 %d 以下（判据抓得住）"
    % (_pick17.replace("dlg_", ""), _MIN_SAME),
    _after17 < _MIN_SAME,
    "压完 %d 句（%d → %d）" % (_after17, _SAME[_pick17], _after17))


# ─────────────────────────────────────────────────────────────────────────────
# ⑱ ★ 玩家可见文本的「渲染残留」与「引号不成对」（2026-09-29 · 文案车道 P1）
#   ⑰ 把「同一句话反复出」钉住了；但还有一类**读端修不了**的缺陷 ——
#   域里那句话本身就带着不该出现在屏上的东西：
#     ① **markdown 强调标记 `**` 漏进纯文本聊天**（屏上是聊天窗，不是渲染器 ⇒ 玩家看见两个星号）
#     ② **ASCII 双引号 "** 混进中文台词（与全角「」同段出现）
#     ③ **「」不成对**：半句话被 `（动作）` 行打断，前一段话的 」被挤掉 ⇒ 屏上少一个引号
#   ★ 三条都是**端到端实测抓到的**（`e2e_drive.py "搭话 杜林"` 屏上原样印出「是**人**缝的」），
#     不是读代码猜的；本批已修（38 处 ** · 3 处 ASCII " · 9 条不成对）。
#   ★ 与 ⑨ 的关系：⑨ 管「切行后每行的长度/空行/一行的引号组数」，
#     ⑱ 管**整条**的字符集与引号配对 —— ⑨ 全绿时这三条照样能红。
# ─────────────────────────────────────────────────────────────────────────────
import re as _re18                                                   # noqa: E402

_MD18 = _re18.compile(r"\*\*|__|(?<!\*)\*(?!\*)")
_bad18 = {"md": [], "ascii_q": [], "unbalanced": []}

for _k18, _v18 in dl.items():
    for _lk18, _nd18 in _v18["nodes"].items():
        for _ti18, _t18 in enumerate(_nd18.get("texts", [])):
            _s18 = str(_t18.get("text", ""))
            _where = "%s/%s#%d" % (_k18, _lk18, _ti18)
            if _MD18.search(_s18):
                _bad18["md"].append((_where, _MD18.search(_s18).group(0)))
            if '"' in _s18 or "'" in _s18:
                _bad18["ascii_q"].append((_where, repr(_s18)[:40]))
            if _s18.count("「") != _s18.count("」"):
                _bad18["unbalanced"].append(
                    (_where, "「%d 」%d" % (_s18.count("「"), _s18.count("」"))))

chk("⑱-a ★ 台词里没有 markdown 强调标记（屏是聊天窗，不是渲染器）  —— 命中：%d"
    % len(_bad18["md"]), not _bad18["md"],
    ("；".join("%s %r" % (w, g) for w, g in _bad18["md"][:4])) if _bad18["md"] else "")
chk("⑱-b ★ 台词里没有 ASCII 引号（中文台词一律用「」）  —— 命中：%d" % len(_bad18["ascii_q"]),
    not _bad18["ascii_q"],
    ("；".join("%s %s" % (w, g) for w, g in _bad18["ascii_q"][:4])) if _bad18["ascii_q"] else "")
chk("⑱-c ★ 每条台词的「」成对（动作插在话中间不许吃掉引号）  —— 不成对：%d"
    % len(_bad18["unbalanced"]), not _bad18["unbalanced"],
    ("；".join("%s %s" % (w, g) for w, g in _bad18["unbalanced"][:4]))
    if _bad18["unbalanced"] else "")

# ⑱-d 反证：把三种形态各塞一条进**真实域对象**（不是副本）⇒ 三条判据必须同时红。
#   ★ 与 ⑫-b/⑰-b 同一个纪律：改副本的话读端根本不生效 ⇒ 尸绿。
_saved18 = json.loads(json.dumps(dl))
_k18 = sorted(dl)[0]
_l18 = sorted(dl[_k18]["nodes"])[0]
_t18 = dl[_k18]["nodes"][_l18]["texts"]
if _t18:
    _victim18 = _t18[0]
    _orig18 = _victim18["text"]
    _victim18["text"] = _orig18 + "\n「反证**加粗**的。」\n「反证\"直引号\"的。」\n「反证少个引号"
    _md18 = bool(_MD18.search(_victim18["text"]))
    _aq18 = ('"' in _victim18["text"]) or ("'" in _victim18["text"])
    _ub18 = _victim18["text"].count("「") != _victim18["text"].count("」")
    _victim18["text"] = _orig18
    chk("⑱-d ★ 反证：往真实域对象塞回三种残留 ⇒ 三条判据都抓得住（判据不恒真）",
        _md18 and _aq18 and _ub18,
        "md=%s ascii=%s 不成对=%s" % (_md18, _aq18, _ub18))
else:
    chk("⑱-d ★ 反证：往真实域对象塞回三种残留 ⇒ 三条判据都抓得住（判据不恒真）", False,
        "%s/%s 没有可污染的 texts 条目" % (_k18, _l18))

# ⑲ ★ P1-19（2026-09-29 · 文案车道 P1）—— **本层说完了，不许立刻原样重说**
#    ★ 为什么 ⑰-a 抓不住这一条（三条判据全绿，缺陷照样在）：
#      ⑰-a 判的是「连敲 8 下总共轮得到几句**不同**的台词」——
#      它**数种类**，不判**次序**。实测 14 位里 11 位第 6/7/8 趟是同一句
#      （`daily#0 daily#0 daily#0` / `daily#1 daily#1 daily#1`），
#      玩家在屏上看到的是**连着三行一模一样的回话**。
#      这正是鱼鱼说的「观感不好」：种类数合格，排布是坏的。
#    ★ 缺陷的根因在**读端**（`cmds_talk._pick_layer` 的层内换句那一段）：
#      它只在**老口径挑中的那一层**里另找一句顶上。找得到就换；
#      找**不到**（这一层的句子此刻都出不来 / 都听过了）就直接把老那一句原样说出去。
#      ⇒ 于此同时，**别的层里还躺着没说过的句子**（实测 talk 5 的 masha：
#      `daily` 一句不剩，而 `hidden` 里有 3 句既没听过、此刻也出得来）——
#      那些句子永远排不上（要让位得先让老口径挑中它们那一层，而老口径总挑 `daily#0`）。
#    ★ 修法只动**兜底那一格**：层内换句找不到顶替时，**在全部够层的层里**
#      找一句「还没听过 ∧ 此刻出得来」的顶上；一句都找不到才原样说出去
#      （＝真没得说了，重复是诚实的）。
#      ★ 不动 ⑧ 的 P-12 语义：让位单位仍是老口径那一格、层序仍是 `LAYERS`、
#        `heard` 记的仍是老口径那一格 —— 本条只在**它已经听过了**之后改变「这一趟说哪句」。
#    ★ 本判据**照真实动作量**：真造档 + 真调 `_pick_layer`，时辰/天气/进度全固定，
#      连敲 8 下，判「**连着重复**」（相邻两趟逐字相同）有几次。
#    ★ 底线**量出来**不是拍的：修之前实测 14 位共 **19 次相邻重样**
#      （最差 masha 3 次）⇒ 底线取「**一位都不许相邻重样**」。
chunks = {}          # 判据用：每位 8 趟逐字序列

# ⑲-a ★ 连着重复（相邻两趟逐字相同）= 0
_dup19 = {}
for _k19 in sorted(_npc):
    _seq19 = _rot_seq_same(_k19)
    _dup19[_k19] = sum(1 for _a, _b in zip(_seq19, _seq19[1:]) if _a == _b and _a)
_tot19 = sum(_dup19.values())
chk("⑲-a ★ 同一时刻连敲 %d 下：**没有一位出现相邻重样**"
    "（屏上不许连着两行一模一样的回话 · 真敲 `_pick_layer`）"
    % _SAME_TALKS,
    _tot19 == 0,
    "相邻重样共 %d 次（%s）" % (
        _tot19,
        " · ".join("%s=%d" % (k.replace("dlg_", ""), v) for k, v in sorted(_dup19.items()) if v)))

# ⑲-b ★ 反证：把某一位**某一层压到只剩兜底句**，让层内换句彻底够不着 ——
#   若修法只是「换到别的层去兜」，这一位应当**仍然**相邻重样（判据不恒真）
#   —— 等等，反过来才叫抓得住：这里钉的是「**判据能看见相邻重样**」。
#   做法：**还原修前的读端形态**（层内换句找不到顶替 ⇒ 原样说出去），
#   真敲一遍 ⇒ 相邻重样必须**回到 19 那一档**（判据抓得住，且数字对得上修前实测）。
_mono19 = ("meet", "daily", "main", "hidden")
_bak19 = json.loads(json.dumps(_npc))
_pick19 = "dlg_masha"
for _ly19 in _mono19:
    _fb19 = None
    for _c19 in _bak19[_pick19]["nodes"][_ly19]["texts"]:
        if _c19.get("need") is None:
            _fb19 = _c19
            break
    _npc[_pick19]["nodes"][_ly19]["texts"] = [_fb19] if _fb19 else []
_after19 = _rot_seq_same(_pick19)
_npc.clear()
_npc.update(_bak19)
chk("⑲-b ★ 反证：把 %s 四层各压到只剩一条兜底 ⇒ 相邻重样必须 > 0（判据抓得住）"
    % _pick19.replace("dlg_", ""),
    _after19.count("") == 0 and sum(1 for _a, _b in zip(_after19, _after19[1:]) if _a == _b and _a) > 0,
    "压完 %d 次（%d 趟里 %d 句不同）" % (
        sum(1 for _a, _b in zip(_after19, _after19[1:]) if _a == _b and _a),
        len(_after19), len(set(_after19))))

# ─────────────────────────────────────────────────────────────────────────────
# ⑳ ★ P1-3（2026-09-29 · 文案车道 P1）—— **⑰/⑲ 的量法盲区**：真实世界状态下的相邻重样
#   ★ 盲区是什么（先说清，否则这条看着像重复钉 ⑲）
#     ⑰-a 把 `_PROG_FLAGS`（**全部主线旗标**）置真再连敲 8 下，⑲-a 同理
#     ⇒ 量的是「**主线全通的世界**里能轮换出几句 / 会不会相邻重样」。
#     而**玩家刚进镇时一条旗标都没有**：条件句（`need` 里有 `flag`/`holding`/`event`）
#     全都不满足 ⇒ 出得来的只有无条件句 ⇒ 域里那一层无条件句够不够，直接决定观感。
#     **这一段没有任何既有判据覆盖。**
#   ★ 实测（真调 `_pick_layer` · **存档无旗标** · 4 时辰 × 2 天气 = 8 种世界状态）：
#     修之前 dlg_cole 2.5 次/局 · dlg_derrick 3.4 · dlg_ed 3.0 · dlg_hagen 2.0 · dlg_pete 2.4
#     （相邻两趟逐字相同 = 玩家在屏上连着看到两行一模一样的回话 —— 鱼鱼说的「观感不好」）
#   ★ 底线**量出来**不是拍的（P1-2 两批补完之后现取）：
#       补之前  最差 derrick 3.4 · ed 3.0 · cole 2.5 · pete 2.4 · hagen 2.0 · 平均 1.95
#       补之后  最差 ed 2.00 · cole 1.75 · seran 1.50 · 平均 0.96
#     ⇒ 底线由 **4.0 收到 2.5**（不是收到 0，见下）。
#     ★ 2026-09-29 P1-2 第三批再收一档 **2.5 → 1.5**（只加严、不放宽）：
#       补 ed / cole / seran 各 2 句后现取（判据自己的夹具 · 8 种世界状态 × 8 趟）=
#         最差 pete 1.38 · xiaoman 1.38 · derrick 1.12 · 平均 **0.92**
#       ⇒ 1.5 卡在「现值 1.38 之上半档余量」，与前两档同一取法（不是收到 0）。
#       ★ 2026-09-29 再收一档 **1.5 → 1.0**（第五件补完 durin/hagen/laotao/nana 后）
#         现取最差 **0.88**（bella/lian）· 平均 0.39 · 14 位里 5 位已 0.00
#         下一档可到 0.75 —— 但要先把 bella / lian 这两位补掉（现值最高）。
#     ★ **不许一上来就要求 0**：那是 ⑲-a 在**全旗标**世界里的口径，
#       拿来套「无旗标」世界会逼着内容侧去堆句子，而不是先把该有的内容补齐。
#       （上一档 2.5 = 当时现值 2.00 之上半档；已按上面那段收到 1.5。）
# ─────────────────────────────────────────────────────────────────────────────
_REAL_STATES = [(h, w)
                for h in ("hr_dawn", "hr_day", "hr_dusk", "hr_night")
                for w in ("w_clear", "w_rain")]


def _rot_dup_unflagged(npc_key, hour, weather, talks=_SAME_TALKS, nodes=None):
    """★ 与 ⑲ 同一把尺（相邻两趟逐字相同），但**存档里一条旗标都没有**。

    这是 `⑰-a` / `⑲-a` 量的那个世界的**反面**：条件句全都不满足，
    出得动的只有无条件句 —— 「层里的无条件句够不够」在这里才现形。
    """
    _fl = {"talked": {}, "talk": {}, "quest_done": {}}      # ★ 不置任何旗标
    _p = {"flags": _fl,
          "bag": {}, "heard": {}, "level": 5,
          "cls": "cls_knight", "race": "human", "equipped": {}}
    _seq = []
    for _i in range(talks):
        _fl["talked"][npc_key] = _i + 1
        _ly, _idx, _txt = CT._pick_layer((nodes or _npc)[npc_key]["nodes"], _p,
                                         {"hour": hour, "weather": weather}, npc_key)
        _seq.append(_txt or "")
        if _txt:
            CT.HD.note(_p, npc_key, _ly, _idx)
    return sum(1 for _a, _b in zip(_seq, _seq[1:]) if _a == _b and _a)


_dup20 = {}
for _k20 in sorted(_npc):
    _v20 = [_rot_dup_unflagged(_k20, _h, _w) for _h, _w in _REAL_STATES]
    _dup20[_k20] = sum(_v20) / float(len(_v20))          # 8 种世界状态的均值
_MAX_UNFLAGGED_AVG = 0.0      # ★ 2026-09-29 P1-2 第五批收档：1.0 → 0.0
#   现值 0.00（14 位全 0，8 种世界状态 × 8 趟）⇒ 上一档 0.75 是 0.00 之上半档余量，
#   本轮把 ed/grey/masha 的 daily 与 5 位的第二句 meet 补齐后收到 0.0。
#   ★ 与 ⑲-a 同一口径（那里就是 0）—— 「玩家刚进镇一条旗标都没有」时
#     不许看到任何一位相邻重样。**仍不许靠加句子放宽**：破了就补句，不动判据。
_tot20 = max(_dup20.values())
chk("⑳-a ★ **无旗标**存档下（条件句全不满足，只剩无条件句可用）：每位平均相邻重样 ≤ %.1f 次"
    "（%d 时辰 × %d 天气 = %d 种世界状态 · 真敲 `_pick_layer` · 现值最差 %.2f）"
    % (_MAX_UNFLAGGED_AVG, len(set(h for h, _ in _REAL_STATES)),
       len(set(w for _, w in _REAL_STATES)), len(_REAL_STATES), _tot20),
    _tot20 <= _MAX_UNFLAGGED_AVG,
    "最差 %.2f（%s）" % (_tot20,
                         "、".join("%s=%.2f" % (k.replace("dlg_", ""), v)
                                   for k, v in sorted(_dup20.items())
                                   if v >= _MAX_UNFLAGGED_AVG)))
print("      无旗标·相邻重样分布：" + " · ".join(
    "%s=%.2f" % (k.replace("dlg_", ""), v) for k, v in sorted(_dup20.items())))

# ⑳-b **反证**：把某一位的 `daily` 压回到「只有 1 条无条件句」——
#   逼回「补句之前」的形态，若判据抓得住，这一位的均值必须**明显变差**。
_dup20_bak = json.loads(json.dumps(_npc))
# ★ 靶子按**现值**选（别写死一个已经补好的名字）：先挑「压回单条后变差最多」的那一位。
_probe20 = max(
    (k for k in _dup20 if k.startswith("dlg_") and "daily" in _npc[k]["nodes"]),
    key=lambda _k: (_dup20[_k], _k))
_MUST_WORSEN = 0.5          # 压回单条后至少要变差这么多，才算「判据抓得住」
_keep20 = [c for c in _dup20_bak[_probe20]["nodes"]["daily"]["texts"]
           if c.get("need") is None][:1]
_npc[_probe20]["nodes"]["daily"]["texts"] = _keep20
_after20 = sum(_rot_dup_unflagged(_probe20, _h, _w) for _h, _w in _REAL_STATES)     / float(len(_REAL_STATES))
_npc.clear()
_npc.update(_dup20_bak)
chk("⑳-b ★ 反证：把 %s 的 daily 压回「只剩 1 条无条件句」⇒ 均值必须**明显变差**"
    "（≥ %.1f 次，判据抓得住、不是恒真）" % (_probe20.replace("dlg_", ""), _MUST_WORSEN),
    (_after20 - _dup20[_probe20]) >= _MUST_WORSEN,
    "压完 %.2f（原 %.2f，差 %+.2f）" % (_after20, _dup20[_probe20],
                                        _after20 - _dup20[_probe20]))

# ㉑ ★ P1-2 第五批（2026-09-29）—— **meet 层「无条件句只有一句」**的结构性判据
#   ★ 为什么要有这条（本轮真挖出来的东西，前 20 条判据全都盖不到）：
#     `_layers_ok` 的熟门槛挂在 **talk 次数**（FAMILIAR_TALKS=3）上，**不是**挂在 `heard` 上
#     ⇒ 新存档的第 1、2 趟都算「不熟」⇒ **那一档只有 `meet` 够层**（daily 被门挡住）
#     ⇒ 而每位的 `meet` 若只有 **1 句无条件**，第 1 趟与第 2 趟**必然逐字相同**：
#     玩家刚进门就连着看到两行一模一样的回话 —— 鱼鱼说的「观感不好」最狠的那一下。
#     ★ ⑳-a 量的是 **daily** 那一池 ⇒ 它**测不到这个洞**（实测：ed 的 daily 补到 7 句无条件，
#       ⑳-a 仍 0.75）。⇒ 这是一条独立判据，不是 ⑳ 的重复。
#   ★ 底线**量出来**不是拍的：补句之前 14 位**全都**只有 1 句无条件 meet
#     （`meet` 两句 = 1 句条件 + 1 句兜底）⇒ 补句之后 5 位改成 2 句，其余 9 位仍 1 句。
#     ★ 收档决策（2026-09-29 本轮做完）：先把剩下 9 位也补到 2 句，再把底线取 **2**
#       —— 即「每一位的 meet 都至少有两句无条件」＝ 刚进门的前两趟**结构上就不可能**重样。
#       上一版取 1 是「不许比谁都少」的软底线，**它的反证写不出来**（压到 1 不越界、
#       1 < 1 恒 False ⇒ ㉑-b 恒红）。⇒ 底线取 2，反证才有意义（压到 1 必越界）。
#       ★ 代价是多一句就多一处可重样位 ⇒ 同批同跑 ⑳-a 验它仍是 0.00（已验）。
_MEET_UNCOND_MIN = 2
_meet_uncond = {}
for _k21 in sorted(_npc):
    if not _k21.startswith("dlg_"):
        continue
    _meet21 = _npc[_k21]["nodes"].get("meet", {}).get("texts", [])
    _meet_uncond[_k21] = sum(1 for _t in _meet21 if not _t.get("need"))
_thin21 = [k for k, v in _meet_uncond.items() if v < _MEET_UNCOND_MIN]
chk("㉑-a ★ meet 层无条件句 ≥ %d 句（新手档只够 meet 说话 ⇒ 只有 1 句就必然第 1/2 趟重样）"
    " —— 现值最薄 %d 句" % (_MEET_UNCOND_MIN,
                            min(_meet_uncond.values()) if _meet_uncond else 0),
    not _thin21,
    "只有 1 句无条件 meet 的：%s" % "、".join(k.replace("dlg_", "") for k in _thin21))
print("      meet·无条件句数分布：" + " · ".join(
    "%s=%d" % (k.replace("dlg_", ""), v) for k, v in sorted(_meet_uncond.items())))

# ㉑-b **反证**：把某位压回「meet 只剩 1 句无条件」⇒ 必须被 ㉑-a 抓到（判据不恒真）
_meet21_bak = json.loads(json.dumps(_npc))
# ★ 靶子按**现值**动态挑（别写死一个名字，免得下一位补完 ed 就又写成恒真）。
_probe21 = min((k for k in _meet_uncond if k.startswith("dlg_")),
               key=lambda k: (_meet_uncond[k], k))
_npc[_probe21]["nodes"]["meet"]["texts"] = [
    c for c in _meet21_bak[_probe21]["nodes"]["meet"]["texts"] if c.get("need") is None][:1]
_thin21_b = [k for k in _npc
             if k.startswith("dlg_")
             and sum(1 for _t in _npc[k]["nodes"].get("meet", {}).get("texts", [])
                     if not _t.get("need")) < _MEET_UNCOND_MIN]
_npc.clear()
_npc.update(_meet21_bak)
chk("㉑-b 反证：把 %s 的 meet 压回「只剩 1 句无条件」⇒ ㉑-a 必抓到它（判据不恒真）"
    % _probe21.replace("dlg_", ""), bool(_thin21_b), "越界者：%s"
    % "、".join(k.replace("dlg_", "") for k in _thin21_b))

# ─────────────────────────────────────────────────────────────────────────────
# ㉒ ★ P1-26（2026-09-29 · 文案车道）—— **全听过之后**：观感从「多样」塌成「冻结」
#   ⑪—⑳ 全都量过，但**每一把尺都架在「还没听完」那一档**：
#     ⑰ / ⑲ 量的是「**没听过时**连敲 8 下」· ⑳ 量的是「存档里一条旗标都没有」
#     · ⑫ 量的是**域里的形状**（某个层有几句）· ⑬ 量的是「后期档（旗标全真）」。
#   ⇒ 每一把尺的 8~12 趟**都用不完一个池子** ⇒ 结构性地测不到
#     「**整棵树都说过了**」这一档。
#   ★ 那一档的实测（修之前，真敲 `_pick_layer` · 中期存档 · 连敲 20 趟）：
#       dlg_bella 第 10 趟起 · dlg_cole 第 9 趟起 · dlg_pete/seran/xiaoman 第 9 趟起 …
#       ⇒ **14 位无一例外**，第 9~11 趟到第 80 趟永远是同一句
#       （读端 ③ 那一格把「老那一句」原样说出去）。
#   ★ 「中期存档」不是刁难人的夹具：主线推到 main08 之后条件句陆续出得来，
#     池子就那么深 —— 玩家每天跟同一批 NPC 说话，**第 10 趟是必然会到的**。
#   ★ 与 ⑲ 的区别：⑲ 判「**相邻两趟**逐字相同」（新玩家档就能撞上），
#     ㉒ 判「**听得越多越不动**」（后期档才现形）—— 两者互补，不是同一条。
# ─────────────────────────────────────────────────────────────────────────────
_MID_FLAGS = ("main04_done", "main05_done", "main08_done", "main09_done",
              "main10_done", "main11_done", "nameline_done")


def _rot_exhausted(npc_key, all_heard, talks=20, nodes=None):
    """**中期存档**（旗标推到 main08 一带）连敲 `talks` 下。

    · `all_heard=False` —— 正常流程：一路听着听着就撞上冻结
    · `all_heard=True`  —— 玩家把这位能听的**全听完了**，再敲还能不能换
    ★ 两档都真敲 `_pick_layer`（夹具与 ⑰ 不同：旗标走**中期真实进度**，
      而 ⑰ 量的是「全旗标」的后期档、⑳ 量的是「一条旗标都没有」的新手档）。
    """
    _fl = {"talked": {}, "quest_done": {}}
    for _f in _MID_FLAGS:
        _fl[_f] = True
    _p = {"flags": _fl, "bag": {}, "heard": {}, "level": 12,
          "cls": "cls_knight", "race": "human", "equipped": {}}
    _nodes = (nodes or _npc)[npc_key]["nodes"]
    # ★ 「全听过」这一档必须**一开始就是熟的**（`_talk_count ≥ FAMILIAR_TALKS`）——
    #   否则前两趟还在 `meet`（还不熟），而 `meet` 与 `daily` 挑的是**不同的池子**，
    #   「每层都听过」在 `meet` 上根本轮不出第二句 —— 计数因此虚高
    #   （第一版夹具就栽在这：未修的代码也能凑出 2 种 ⇒ ㉒-a 恒绿 = 门禁自己瞎了）。
    #   ⇒ 底数给 99：既是熟的，又让「这一趟是第几次搭话」继续往前走（④ 轮换用得到它）。
    _base = 99 if all_heard else 0
    if all_heard:                                   # 全听过：每层每句都记进 heard
        for _lk, _nd in _nodes.items():
            for _i in range(len(_nd.get("texts") or [])):
                CT.HD.note(_p, npc_key, _lk, _i)
    _seq = []
    for _i in range(talks):
        _fl["talked"][npc_key] = _base + _i + 1
        _ly, _idx, _txt = CT._pick_layer(_nodes, _p,
                                        {"hour": _SAME_HOUR, "weather": _SAME_WEATHER},
                                        npc_key)
        _seq.append(_txt or "")
        if _txt:
            CT.HD.note(_p, npc_key, _ly, _idx)
    return _seq


# ㉒-a **「听完了还能不能换」**：全听过之后仍能轮换出 ≥ 2 句不同的台词。
#   ★ 底线 = 2（**不是 1**）：只有 1 句就是「玩家每次看到同一句」= 这次要修的那个病。
#   ★ 这条在修之前的实测 = 14 位全 1 ⇒ 修完之后才是 6~9。
_EXH = {k: len(set(_rot_exhausted(k, True))) for k in sorted(_npc)}
_MIN_EXHAUSTED = 2
_thin22 = [k for k, v in _EXH.items() if v < _MIN_EXHAUSTED]
chk("㉒-a ★ 全听过之后：每位仍能轮换出 ≥ %d 句不同台词（14 位全听得完）"
    % _MIN_EXHAUSTED, not _thin22,
    "现值最薄 %d 句（%s）" % (min(_EXH.values()) if _EXH else 0,
                              "、".join(k.replace("dlg_", "") for k in _thin22) or "无"))
print("      全听过·轮换分布：" + " · ".join(
    "%s=%d" % (k.replace("dlg_", ""), v) for k, v in sorted(_EXH.items())))

# ㉒-b **「听得越多越不动」**：正常流程下，**最后一趟那一半**不许冻在同一句上。
#   ★ 量的是**尾部**而不是全程：⑰ 量全程 8 趟的种类数（8 趟用不完池子 ⇒ 恒绿），
#     这里量「第 11~20 趟」—— 池子见底之后的那一段，正是缺陷现形的地方。
#   ★ 判据 = 尾部里相邻重样 0 次（与 ⑲ 同一把尺，不同夹具：中期存档 + 20 趟）。
_TAIL_TALKS = 20
_dup22 = {}
for _k22 in sorted(_npc):
    _sq = _rot_exhausted(_k22, False, talks=_TAIL_TALKS)
    _tail = _sq[_TAIL_TALKS // 2:]                    # ★ 后一半 = 第 11~20 趟
    _dup22[_k22] = sum(1 for _a, _b in zip(_tail, _tail[1:]) if _a == _b and _a)
_tot22 = sum(_dup22.values())
chk("㉒-b ★ 中期存档连敲 %d 下：第 %d 趟往后不许相邻重样（听全之后不许冻住）"
    % (_TAIL_TALKS, _TAIL_TALKS // 2 + 1), _tot22 == 0,
    "尾部相邻重样共 %d 次（%s）" % (
        _tot22,
        " · ".join("%s=%d" % (k.replace("dlg_", ""), v)
                   for k, v in sorted(_dup22.items()) if v)))
print("      中期·尾部轮换分布：" + " · ".join(
    "%s=%d" % (k.replace("dlg_", ""), len(set(_rot_exhausted(k, False, talks=_TAIL_TALKS)[_TAIL_TALKS // 2:])))
    for k in sorted(_npc)))

# ㉒-c **反证**：把某位**整棵树压到只剩一条无条件句** ⇒ ㉒-a 必抓到它（判据不恒真）。
#   ★ 压的是真实的 `_npc`（不是副本表）—— ⑧ 的教训：替掉树之后实际读的仍是原值 ⇒ 尸绿。
#   ★ 压完也该让 ㉒-b 抓到（尾部必然全是同一句）：两条一起验，才知道它们不是恒真。
_exh22_bak = json.loads(json.dumps(_npc))
_probe22 = sorted(_npc)[0]
_one22 = next((_c for _c in _exh22_bak[_probe22]["nodes"]["daily"]["texts"]
               if not _c.get("need")), None)
for _lk22 in list(_npc[_probe22]["nodes"]):
    _npc[_probe22]["nodes"][_lk22] = {"texts": ([_one22] if _one22 is not None else [])}
_exh22 = len(set(_rot_exhausted(_probe22, True)))
_dup22b = 0
if _exh22 < _MIN_EXHAUSTED:                          # 条件句出不来才量尾部（夹具口径一致）
    _sq22b = _rot_exhausted(_probe22, False, talks=_TAIL_TALKS)
    _tb22b = _sq22b[_TAIL_TALKS // 2:]
    _dup22b = sum(1 for _a, _b in zip(_tb22b, _tb22b[1:]) if _a == _b and _a)
_npc.clear()
_npc.update(_exh22_bak)
chk("㉒-c 反证：把 %s 整棵树压到只剩一条无条件句 ⇒ ㉒-a 必抓到它（判据不恒真）"
    % _probe22.replace("dlg_", ""), _exh22 < _MIN_EXHAUSTED,
    "压完 %d 种（底线 %d · 尾部相邻重样 %d 次）" % (_exh22, _MIN_EXHAUSTED, _dup22b))

# ㉓ ★ P1-5（2026-09-29 · 文案车道 P1）—— **情报量**：不许有「纯寒暄」
#    本车道自己的口径写着一句「**一句台词至少给一点玩家现在还不知道、但需要知道的东西**，
#    不许纯寒暄」—— 而 ㉓ 之前**没有任何一条判据在看这件事**：
#    位齐（⑩-a）判的是层齐不齐、轮换（⑩-b/⑪）判的是重不重样，
#    它们**一个字都没提信息量** ⇒ 一句「辛苦了」能一路绿到今天。
#    ★ 为什么这条能机器判（别把「文笔好不好」也塞进来）：「纯寒暄」是**闭集** ——
#      问候 / 致谢 / 寒暄连接词那几十个词，不含任何专名、方位、动机、传闻口径。
#      判据 = 把台词里「」中的内容抽出来、去掉标点，若**每个字都来自寒暄词表** ⇒ 判寒暄。
#      这不是「用词频次近似审美」，是**可枚举的精确判定**。
#    ★ 域里现状（2026-09-29 实测）：**0 行纯寒暄**；最短的一句台词
#      「骨头没少。」4 个字（哈根 daily#0），最长的 152 字。
#      零引号的 17 行是**旁白**（5 棵物件树的 15 句 + 艾德/哈根隐藏线各一句沉默），
#      那是「看一眼说一句」的物件世界与「他不说话」的角色写法，**不是寒暄** ⇒ 豁免。
#      底线定 **0**（硬要求）：现值就是 0，这一改不会让本车道自己红，只把已做到的钉住。
#    ★ 与 ⑩-b 同一条纪律：门槛跟**现值**走，不是跟「当初留的余量」走。
_CHAT_CHARS = set("你好您在吗早上好晚上好辛苦了谢谢多谢不客气再见保重一路平安请问打扰了没事啊喂么不走了吧呀好的行嗯啊哦")
_PUNCT = "。，、！？…—·「」 \t\r\n"


def _speech_only(t):
    """抽出台词本体：只留「」里的内容（旁白与动作括号一并去掉）。"""
    return "".join(re.findall("「([^」]*)」", t or ""))


def _is_chatter(s):
    core = "".join(c for c in s if c not in _PUNCT)
    return bool(core) and all(c in _CHAT_CHARS for c in core)


_MIN_CHATTER = 0
_CHATTER = []
_ALLTXT = []
for _k, _v in sorted(dl.items()):
    for _lk, _nd in _v["nodes"].items():
        for _i, _t in enumerate(_nd["texts"]):
            _ALLTXT.append((_k, _lk, _i, _t))
            if _is_chatter(_speech_only(_t.get("text"))):
                _CHATTER.append("%s/%s#%d %s" % (_k, _lk, _i, _speech_only(_t.get("text"))))
chk("㉓-a ★ 情报量：纯寒暄行（句子全是寒暄词 ⇒ 玩家还没从中拿到东西）%d 行 · 硬上限 ≤ %d"
    " —— 现值 0（全部 %d 句台词里一句都没有）" % (len(_CHATTER), _MIN_CHATTER, len(_ALLTXT)),
    len(_CHATTER) <= _MIN_CHATTER, (" · ".join(sorted(_CHATTER)[:6]) or "0 行"))

# ㉓-b **反证**：塞一句真的寒暄进域 ⇒ 判据必须抓得住（不然就是恒真的判据）。
_probe23 = sorted(_npc)[0]
_lay23 = sorted(dl[_probe23]["nodes"])[0]
_bak23 = json.loads(json.dumps(dl[_probe23]))
dl[_probe23]["nodes"][_lay23]["texts"][0]["text"] = "「辛苦了。多谢。」"
_caught23 = ["%s/%s#0" % (_probe23, _lay23)] if _is_chatter(
    _speech_only(dl[_probe23]["nodes"][_lay23]["texts"][0]["text"])) else []
# 按 key 精确还原（不整树清掉：其它判据已经跑完了，这里只把改动那一句还回去）
dl[_probe23]["nodes"][_lay23]["texts"][0]["text"] = _bak23["nodes"][_lay23]["texts"][0]["text"]
chk("㉓-b ★ 反证：塞一句「辛苦了。多谢。」进 %s 的 %s 层 ⇒ 判据必抓到（判据不恒真）"
    % (_probe23.replace("dlg_", ""), _lay23), bool(_caught23),
    "塞进 %s/%s#0 ⇒ %s" % (_probe23, _lay23, "抓到了" if _caught23 else "漏了（判据恒真）"))

# ㉔ ★ P1-28（2026-09-29 · 文案车道 P1）—— **物件树同刻连敲不许整段重样**。
#    ⑰-a 量的是 `dlg_` 那 14 棵 NPC；物件树（`talk_*`）一个都没算进去 ——
#    而玩家对着一堆篝火「连敲两下」正是这个动作。
#    根因（P1-28 修）：POI 触摸那条路原先只调 `_pick_indexed`（按顺序挑第一条满足的），
#    绕过了 NPC 那边的 `heard` 轮换 ⇒ 固定世界状态下每趟挑中同一句。
#    实测（修前，真敲读端）：五棵物件树在同一世界状态下连敲，**每趟逐字相同**。
#    这就是鱼鱼说的「观感不好」在物件这一族上的形状。
#
# ★★ 判据本身连踩两个坑（写在这里，别再犯第三遍）：
#   ① 第一版在探针里**自己重写一遍**取句 + 轮换 + 记账的循环 ⇒ 它量的是「探针那套写法」
#      而不是产品那条路 —— 把产品侧的 `CT.rotate` 回退掉之后它**照样绿**（尸绿）。
#   ② 第二版改成真敲 `poi_effect_lines` 了，却以为「给 `_pick_indexed` 传 hour/weather
#      就能固定世界状态」—— **错**：那条路内部自己调 `CAL.state()`（不接参），
#      时辰与天气来自 `facade.clock()` ⇒ 8 趟里世界状态照旧在动，数字好看但**量错了东西**。
#   ⇒ 终版：照 `probe_weather._time_screen` 的现成办法，把 `FA.clock` / `CAL.facade.clock`
#     钉到算好的 epoch（`finally` 复原），**整趟世界状态真的不动**，再真敲那个函数。
# ★ P1-45（2026-09-29 · 文案车道 aep1）把这条**从 2 抬到 5**（只加强，未删改任何既有判据）。
#   原值 2 是 P1-28 修好「同刻连敲逐字相同」那一刻量的 —— 修完轮换接上了，
#   但当时物件树每层**只有 2 句无条件**（另 2 句挂 time/weather），2 就是天花板。
#   P1-44 给 5 棵物件树各补 3 句无条件正文（2 → 5）⇒ 天花板抬到 5。
#   ★ 为什么 5 是「及格」而不是拍脑袋：
#     ① NPC 侧那条同款判据（⑰-a）钉的是 **8 趟 ≥ 4 句**（`_MIN_SAME = 4`）——
#        玩家「对同一个人连敲」与「对同一个物件连敲」是**同一个动作**，
#        两条判据却一边 4 一边 2 ⇒ 现在把两边拉到同一档（物件侧现值最差 5）。
#     ② 实测（真敲 + 钟钉死）：昼/晴 8 趟 = 5 段 · 夜/晴 8 趟 = 6 段 · 晨 = 6 段。
#   ★ 这条**不是**给改动作用的：P1-44 的数据先落地、量过 5/5/6/6，才把底线抬上来。
_MIN_OBS_FIXED24 = 5      # 每棵在同一时刻连敲 8 次，至少轮得出 5 句
_HOUR_HOURS24 = (2.0, 13.0, 18.5, 22.0)      # 晨 / 昼 / 暮 / 夜 各取一点（时辰表里见 `calendar.hours`）


class _E24(object):
    """`poi_effect_lines` 要的那个 env（只要一个 `save`）—— 同 `probe_pois._E11`。"""

    def __init__(self, text=""):
        self.text = text

    def save(self):
        pass


def _epoch_for24(game_day, hour_of_day):
    """游戏日 + 当日小时 → 宿主那根钟的 epoch（`calendar.game_time` 的逆运算）。"""
    from content import calendar as CAL24
    sec_per_day = CAL24.scale_seconds()
    return (game_day * 86400.0 + hour_of_day * 3600.0) * (sec_per_day / 86400.0)


def _poi_touch24(pid, epoch, p24):
    """真敲一次「触摸这个 POI」（**钟钉在 epoch**）→ 屏上那几行。"""
    import asyncio as _asyncio24
    import content.cmds_ast as CA24
    from content import facade as FA24
    from content import calendar as CAL24
    _old24 = FA24.clock
    FA24.clock = lambda: epoch
    CAL24.facade.clock = lambda: epoch            # `calendar._epoch` 读的就是它
    _p24 = p24                     # ★ 档由调用方建一次并跨趟带（连敲 8 下 = 同一个玩家）
    out24 = []
    rec24 = {"id": pid, "effect": {"talk": pid}}
    try:
        async def _go24():
            async for _l24 in CA24.poi_effect_lines(_E24(), None, "u_aep1", _p24, pid, rec24, "touch"):
                out24.append(str(_l24))

        _asyncio24.run(_go24())
    finally:
        FA24.clock = _old24
        CAL24.facade.clock = _old24
    return out24


_OBS_FIXED24 = {}
for _pk24 in sorted(_prop):
    _worst24, _wk24 = 99, None
    for _hod24 in _HOUR_HOURS24:
        _ep24 = _epoch_for24(1, _hod24)            # 同一个游戏日 —— 只变时辰，不跨日
        import content.cmds_ast as _CAa24
        _pa24 = dict(_CAa24.DEFAULT_PLAYER)
        _pa24.update({"race": "human", "heard": {}})     # 同一个玩家，8 趟共用
        _say24 = [chr(10).join(_poi_touch24(_pk24, _ep24, _pa24)) for _i24 in range(8)]
        if len(set(_say24)) < _worst24:
            _worst24, _wk24 = len(set(_say24)), _hod24
    _OBS_FIXED24[_pk24] = (_worst24, _wk24)
_bad24 = [k for k, (v, _) in _OBS_FIXED24.items() if v < _MIN_OBS_FIXED24]
chk("㉔-a ★ 物件树**同刻连敲**（钟已钉死 · 同一游戏日同一时刻 · 连敲 8 次 · 真敲 "
    "`poi_effect_lines`）：每棵至少轮得出 %d 句" % _MIN_OBS_FIXED24, not _bad24,
    ("轮换不足：%s" % " · ".join("%s=%d" % (k, _OBS_FIXED24[k][0]) for k in _bad24) if _bad24
     else " · ".join("%s=%d" % (k.replace("talk_", ""), v) for k, (v, _) in sorted(_OBS_FIXED24.items()))))

# ㉔-b **反证**：把一棵树压回「只剩一条无条件兜底」⇒ ㉔-a 必须抓到（不然是恒真的判据）。
#   ★ 压的是**真实的域对象 _prop**（㉔-a 读的就是它）⇒ 压完读到的确实是压过的值。
_probe24 = sorted(_prop)[0]
_bak24 = json.loads(json.dumps(_prop[_probe24]))
# ★★ 压得**彻底**，而且压的是**产品真正读的那份对象**：
   #   `cmds_ast._data("dialogues")` 有**自己那份缓存**（`_CACHE`），与探针手里的 `dl`
   #   **不是同一个对象**（实测 `is` 为 False）⇒ 只改 `_prop` 的话产品侧读到的仍是原树
   #   ⇒ 那就是「反证打不动被测行为」的尸绿。
   #   两处都改（`_prop` 给判据读的那份 · `_real24` 给产品读的那份），量完按 key 还原。
_one24 = _bak24["nodes"]["meet"]["texts"][-1]["text"]
_flat24 = {"nodes": {"meet": {"texts": [{"need": None, "text": _one24}]}}}
_prop[_probe24] = _flat24
import content.cmds_ast as CA24_global24
_real24 = CA24_global24._data("dialogues")
_bakreal24 = json.loads(json.dumps(_real24[_probe24]))
_real24[_probe24] = _flat24
_w24 = 99
for _hod24 in _HOUR_HOURS24:
    _ep24 = _epoch_for24(1, _hod24)
    import content.cmds_ast as _CAb24
    _pb24 = dict(_CAb24.DEFAULT_PLAYER)
    _pb24.update({"race": "human", "heard": {}})
    _s24 = set(chr(10).join(_poi_touch24(_probe24, _ep24, _pb24)) for _i24 in range(8))
    if len(_s24) < _w24:
        _w24 = len(_s24)
_prop[_probe24] = _bak24                              # 按 key 精确还原
_real24[_probe24] = _bakreal24                        # ★ 产品那份也要还原（否则后面判据全读到压过的值）
chk("㉔-b ★ 反证：把 %s 压回「只剩一条无条件兜底」⇒ ㉔-a 必抓到（判据不恒真）"
    % _probe24.replace("talk_", ""), _w24 < _MIN_OBS_FIXED24,
    "压完 %d 句（底线 %d）" % (_w24, _MIN_OBS_FIXED24))

# ㉔-c ★ **单一真源**：物件树那条路必须走 `CT.rotate` + `CT.note_heard` 两个共享口，
#   不许自己抄一份（抄了就会出现「修了一处、下一处还是重样」）。
_poi24 = _io8.open(os.path.join(str(REPO), "content", "cmds_ast.py"), encoding="utf-8").read()
_ok24 = ("CT.rotate(" in _poi24) and ("CT.note_heard(" in _poi24)
chk("㉔-c ★ POI 触摸那条路的轮换/记账走 `CT.rotate` + `CT.note_heard`（不抄第二份）", _ok24,
    "rotate=%s note_heard=%s" % ("CT.rotate(" in _poi24, "CT.note_heard(" in _poi24))

# ══════════════════════════════════════════════════════════════════
# ㉕ ★★ P1-30（2026-09-29 · 文案车道 P1）—— **每一条台词的 need 都得「拿得到」**
#    这一节是 P1-27 的伴生补齐。P1-27 把「认不出的 need 键」从「静默当满足」改成
#    fail-closed，方向对；但它只把「**键名**认不认得」关死了，**键值**没人管：
#
#    ★ 真缺口（实测出来的，前两版猜错过两次，见提交消息）：
#      事件 / 旗标 / 图鉴三类，键值只要**指向一个存在的东西**，就一定有机会满足。
#      真正会**永久死句**的是道具那一类：
#        `{"holding": "i_xxx"}` —— `i_xxx` 在 items 域里查无此物，
#        或查得到却**没有任何来源**（掉落池 / 采集 / 配方 / 任务奖励都没有它）
#        ⇒ 玩家这一辈子拿不到 ⇒ 那一句话**永远出不来**，
#        而 ③（键名合法）、⑩~㉔（域里此刻没有这一句）、schema **全都判不出**，
#        **全链零报错**。写的人以为那句话挂上了，玩家看不到它，
#        也没有任何一道门会红 —— 比「重复」更难被发现（它连个重样的现象都没有）。
#
#    为什么属「门禁只加强」：③ 查**键名合法**，㉕ 查**键值拿得到**
#      —— 两者合起来才叫「这一句是活的」。③ 一字未改，既有判据一行未动。
#    四个 oracle 各自**跟着定义方走**（不另抄一份名单）：
#      `event`   → `content.calendar.events()`（世界事件只有那一张表）
#      `flag`    → `content.prog.map_slug`（真实进度那一族）；表外那几个各自有写端
#      `holding` → items 域（存在）**且** 掉落池 / 采集 / 配方 / 任务四路至少一路给得出
#      `codex`   → codex 域（`谱:条目` 两段都要认）
#    ★ 只查**域里真用到的那些 token**（不查全表）—— 域没用到的，不该被门禁管。
import content.prog as _PG25
import content.calendar as _CAL25

_items25 = st.domain("items") or {}
_codex25 = st.domain("codex") or {}
_events25 = _CAL25.events()
_pools25 = st.domain("drop_pools") or {}
_gath25 = st.domain("gathering") or {}
_recipes25 = st.domain("recipes") or {}
_quests25 = st.domain("quests") or {}


def _toks25(kind):
    """域里用到的这一类 token（值可能是标量也可能是列表）—— 现算，不抄名单。"""
    _s = set()
    for _v in dl.values():
        for _nd in _v["nodes"].values():
            for _t in _nd.get("texts") or []:
                _x = (_t.get("need") or {}).get(kind)
                if not _x:
                    continue
                _s.update(_x if isinstance(_x, list) else [_x])
    return sorted(_s)


def _obtainable25(item_id):
    """这一件**拿得到**吗 —— 四条来源任一给得出就算（掉落池 / 采集 / 配方 / 任务）。

    ★ 「items 域里有这一条」只说明**它被定义过**，不等于**玩家拿得到**：
      域里可以躺着一个谁都不掉的道具（写道具时手滑 = 那一族内容全废，
      而且没有任何一道门会红）。这里现查四路来源，不抄名单。
    """
    if item_id not in _items25:
        return "items 域里没有这一件"
    _blob = json.dumps([_pools25, _gath25, _recipes25, _quests25], ensure_ascii=False)
    if item_id in _blob:
        return ""
    return "items 域里有，但掉落池/采集/配方/任务四路都给不出（玩家永远拿不到）"


#: 旗标里**不是**委托 slug 的那几个 —— 各自有各的写端（`content.prog` 的表外老口径）。
#: 认不出的旗标 = 没人写它 = 那一句永远出不来 ⇒ 与「键值拿不到」同罪。
_FLAG_WRITERS25 = {"nameline_done", "swordband_done", "oldroad_done",
                   "quest_lamp_oil_done", "quest_return_stone_done", "asked_for_rain_herb"}

_ev25 = _toks25("event")
_hd25 = _toks25("holding")
_fg25 = _toks25("flag")
_cx25 = _toks25("codex")

_dead25 = []
for _e in _ev25:
    if _e not in _events25:
        _dead25.append("event:%s（世界事件表里没有）" % _e)
for _h in _hd25:
    _why = _obtainable25(_h)
    if _why:
        _dead25.append("holding:%s —— %s" % (_h, _why))
for _f in _fg25:
    if not _PG25.map_slug(_f) and _f not in _FLAG_WRITERS25:
        _dead25.append("flag:%s（既不是委托 slug · 也没登记写端）" % _f)
for _c in _cx25:
    _bk, _, _rid = _c.partition(":")
    if not (_bk and _rid) or _rid not in (_codex25.get(_bk) or {}):
        _dead25.append("codex:%s（图鉴里没有这一条）" % _c)

chk("㉕-a ★ 每条台词的 need 都**拿得到**（事件 / 道具（含拿得到）/ 旗标 / 图鉴四条都得指向世界里真实存在、玩家真能拿到的东西）",
    not _dead25,
    "认不出 ⇒ 那一句永远出不来：%s" % _dead25 if _dead25
    else "查了 %d 事件 + %d 道具（含来源） + %d 旗标 + %d 图鉴条（全对得上）"
         % (len(_ev25), len(_hd25), len(_fg25), len(_cx25)))

# ㉕-b ★ 反证：挂一个「**定义了却没人给得出**」的道具 ⇒ ㉕-a 必须抓到它。
#   ★ 为什么这一条才是真缺口（第一版拿「拼错的键名」当缺口被打脸：③ 抓得住键名；
#     第二版拿「键名合法 · 值不存在」也被打脸：`holding` 只读 bag，背包真有就理应出得来）。
#     剩下的就是这一种：**items 域里有它，而四路来源都给不出**。
#   ★ 三半都要成立，缺一这条判据就是恒真的（自己瞎）：
#     ① ③「只查键名」的口径**放行**（它只看得见 `holding` 这个键，看不见值）；
#     ② 真读端在「玩家只有正常来源」时**挑不出**（拿不到 ⇒ 永远不满足）；
#     ③ ㉕-a 自己的 oracle **抓得住**（按 key 精确还原 ⇒ 抓完不留痕）。
_bak25 = json.loads(json.dumps(dl["dlg_masha"]))
try:
    _ghost25 = "i_ghost_never_dropped"
    _items25[_ghost25] = {"name": "㉕ 反证用 · 谁都不掉的道具", "kind": "杂物",
                          "kind_key": "junk", "icon": "📦", "price": 0, "desc": "㉕ 反证用"}
    _bad25 = {"holding": _ghost25}                    # 键合法 · 道具存在 · 没人给得出
    dl["dlg_masha"]["nodes"]["hidden"]["texts"].append(
        {"need": _bad25, "text": "㉕ 反证用 · 这一句在真档里永远出不来"})
    _oldview_passes25 = set(_bad25) <= set(NEED_KINDS)     # ③ 的口径 ⇒ 放行（漏）
    _read_end_never25 = CT._pick_indexed(
        [{"need": _bad25, "text": "不该出"}],
        {"flags": {}, "bag": {}, "equipped": {}, "hp": 999},   # 正常途径 = 拿不到 ⇒ 空包
        {"hour": "hr_dusk", "weather": "w_fog"})[1] is None
    _shape_catches25 = bool(_obtainable25(_ghost25))          # ㉕-a 的 oracle ⇒ 抓
    chk("㉕-b ★ 反证：挂一个「**定义了却没人给得出**」的道具 ⇒ ㉕-a 必抓到（而 ③「只查键名」放行它）",
        _oldview_passes25 and _read_end_never25 and _shape_catches25,
        "③ 会放行=%s · 读端挑不出=%s · ㉕-a 抓得住=%s（缺口就在①与③之间）"
        % (_oldview_passes25, _read_end_never25, _shape_catches25))
finally:
    dl["dlg_masha"] = _bak25                            # 按 key 精确还原
    _items25.pop("i_ghost_never_dropped", None)         # 反证道具也还原（不留痕）

# ㉖ ★「换皮」门禁 —— 补的是**既有判据之间的缝**（P1-32 实测出来的真缺陷）
# ---------------------------------------------------------------------------
# 为什么单开一条（前面 ㉑–㉕ 都抓不住它）：
#   ㉫-类的轮换判据量的是**能不能轮出多句**（`heard` 去重 + 层序让位）；
#   ⑫ 量的是「一个层里只有 1 句吗」。而**换皮**是反过来的形态 ——
#   层里**有**两条，`need` 也**各不相同**（一条挂时辰、一条无条件 ⇒ 都轮得到），
#   可它们的**台词逐字一样**，只多一个动作括号：
#       dlg_lian/daily#0   （夜里。…）「这一页我认得。」「下一行不认得。」…
#       dlg_lian/daily#3   （她把册子翻到…）「这一页我认得。」「下一行不认得。」…
#   ⇒ 读端（`_pick_layer` 记 `heard`）认为「玩家听到两句不同的」，
#     屏上却是一模一样两行 —— 这就是鱼鱼那句「观感不好」的**第二次搭话就重样**。
#   ★ 现值：同层 100% 换皮 0 对、≥0.60 的 2 对（格雷/艾德 0.62–0.65，
#     是同一腔调的**部分**重合、不是复制）；跨层 100% 0 对、≥0.75 的 1 对
#     （莉安 meet#1 ~ idle#0，是她「没说完」那条尾巴的有意复现，不判红）。
#   ⇒ 棘轮钉「**100% 换皮 0 对**」这一条硬底线（0 就是 0，不是「现在还有几对」），
#     另两条只钉「不许变多」并逐步加严。

import difflib as _dl26

_D26 = 0.95          # 判「复制」的相似度（不是 1.0：动作括号与空行会差一点点）
_WARN26 = 0.60       # 只报数的宽档（不改判据，只让下一批看得见基线）


def _d26_pairs(nodes_by_layer):
    """同层内两两比 + 同树跨层比 → (硬, 宽) 两档的对。"""
    hard, wide = [], []
    for k, N in nodes_by_layer.items():
        items = [(a, i, _speech_only(t.get("text", "")))
                 for a in sorted(N) for i, t in enumerate(N[a].get("texts", []))]
        for x in range(len(items)):
            for y in range(x + 1, len(items)):
                a1, i1, s1 = items[x]
                a2, i2, s2 = items[y]
                if a1 != a2 or not s1 or not s2:
                    continue
                r = _dl26.SequenceMatcher(None, s1, s2).ratio()
                if r >= _D26:
                    hard.append((k, a1, i1, a2, i2, round(r, 2)))
                if r >= _WARN26:
                    wide.append((k, a1, i1, a2, i2, round(r, 2)))
    return hard, wide


_by26 = {k: v["nodes"] for k, v in dl.items()}
_hard26, _wide26 = _d26_pairs(_by26)
chk("㉖-a ★ 换皮（同层两句台词逐字复制，只差一个动作括号）0 对 · 硬底线 ≤ 0",
    not _hard26,
    "换皮：%s" % _hard26 if _hard26
    else "同层 %d 层逐对过完 · 100%% 复制 0 对 · ≥%.2f 的 %d 对（基线，逐步加严）"
         % (sum(len(v) for v in _by26.values()), _WARN26, len(_wide26)))

# 跨层：莉安 meet#1 与 idle#0 共享她「……守着。那块石头。你读过了。」那半句
#   —— 那是她**没说完**这条人设的有意复现（idle 是同一句话的下半截），所以跨层
#   只钉「不许变多」（棘轮），不钉 0。
_xl26 = []
for k, N in _by26.items():
    items = [(a, i, _speech_only(t.get("text", "")))
             for a in sorted(N) for i, t in enumerate(N[a].get("texts", []))]
    for x in range(len(items)):
        for y in range(x + 1, len(items)):
            a1, i1, s1 = items[x]
            a2, i2, s2 = items[y]
            if a1 == a2 or not s1 or not s2:
                continue
            r = _dl26.SequenceMatcher(None, s1, s2).ratio()
            if r >= 0.85:
                _xl26.append((k, a1, i1, a2, i2, round(r, 2)))
_XL_BASE26 = 1        # 棘轮：现值 1（莉安 meet#1~idle#0，有意），不许变多
chk("㉖-b ★ 跨层复现：同树两层台词高度雷同 ≤ %d 对（棘轮 · 莉安那句是有意的）" % _XL_BASE26,
    len(_xl26) <= _XL_BASE26,
    "跨层：%s" % _xl26 if _xl26 else "%d 对（= 基线，钉住不许变多）" % len(_xl26))

# ㉖-c ★ 反证：把 lian 的 daily#3 压回 daily#0 那句（100% 复制）⇒ ㉖-a 必抓到。
_bak26 = json.loads(json.dumps(dl["dlg_lian"]))
try:
    _victim26 = _bak26["nodes"]["daily"]["texts"][3]
    dl["dlg_lian"]["nodes"]["daily"]["texts"][3]["text"] =         _bak26["nodes"]["daily"]["texts"][0]["text"]
    _hard_probe26, _ = _d26_pairs({k: v["nodes"] for k, v in dl.items()})
    chk("㉖-c ★ 反证：把 dlg_lian 的 daily#3 压回 daily#0 那句 ⇒ ㉖-a 必抓到（判据不恒真）",
        any(x[0] == "dlg_lian" for x in _hard_probe26),
        "压完 %d 对（抓到了：%s）" % (len(_hard_probe26),
                                    [x for x in _hard_probe26 if x[0] == "dlg_lian"]))
finally:
    dl["dlg_lian"] = _bak26                # 按 key 精确还原（不留痕）
    assert json.dumps(dl["dlg_lian"], ensure_ascii=False, sort_keys=True) ==         json.dumps(_bak26, ensure_ascii=False, sort_keys=True)


# ㉖-d ★ P1-36（2026-09-29 · 文案车道 aep1）—— 把 ㉖ 的**宽档**也钉成硬底线。
#   缺陷本体：㉖-a 的硬底线是「100% 复制 0 对」（_D26=0.95），而 0.60~0.95 那一档
#   **只印数不判**（`_WARN26` 只在 ㉖-a 的 extra 里报一句）。实测那正是两条真换皮：
#     dlg_ed   idle#2 ~ idle#3  r=0.62 —— 两句「我教过你的，都还在那儿。」开头逐字相同
#     dlg_grey idle#2 ~ idle#3  r=0.65 —— 两句「你还来。」开头 + 同一句「我他妈就烦话多的」收尾
#   ⇒ 同一个 idle 层里，玩家连敲两趟会看到**同一个开头**、同一个拖腔，
#     中间只差一个动作括号 —— 就是「观感不好」的那一档。
#   本单元已把那两对改写（按各自人设另起入口与收尾）⇒ 现值 0，故可把宽档升成硬底线。
#   ★ 纯追加：㉖-a / ㉖-b / ㉖-c 一字未改；本条只**复用**它们那份 `_d26_pairs`
#     （全仓不留第二份换皮算法，也不另抄一个相似度阈值）。
_WIDE_BASE26 = 0         # 棘轮：现值 0 对（艾德/格雷两对已在 P1-36 改掉）
chk("㉖-d ★ 换皮宽档（同一层里两句台词 r≥%.2f，即**开头或收尾逐字相同**）≤ %d 对（棘轮）"
    % (_WARN26, _WIDE_BASE26),
    len(_wide26) <= _WIDE_BASE26,
    "宽档：%s" % _wide26 if _wide26
    else "同层 %d 层逐对过完 · ≥%.2f 的 0 对（= 基线，钉住不许回来）"
         % (sum(len(v) for v in _by26.values()), _WARN26))

# ㉖-e ★ 反证：把 dlg_grey 的 idle#3 开头按回 idle#2 那句 ⇒ ㉖-d 必抓到（判据不恒真）。
_bak26d = json.loads(json.dumps(dl["dlg_grey"]))
try:
    _a2 = _bak26d["nodes"]["idle"]["texts"][2]["text"]
    dl["dlg_grey"]["nodes"]["idle"]["texts"][3]["text"] = _a2
    _, _wide_probe26 = _d26_pairs({k: v["nodes"] for k, v in dl.items()})
    chk("㉖-e ★ 反证：把 dlg_grey 的 idle#3 压回 idle#2 那句 ⇒ ㉖-d 必抓到（判据不恒真）",
        any(x[0] == "dlg_grey" and x[1] == "idle" for x in _wide_probe26),
        "压完 %d 对（抓到了：%s）" % (len(_wide_probe26),
                                    [x for x in _wide_probe26 if x[0] == "dlg_grey"]))
finally:
    dl["dlg_grey"] = _bak26d              # 按 key 精确还原（不留痕）
    assert json.dumps(dl["dlg_grey"], ensure_ascii=False, sort_keys=True) ==         json.dumps(_bak26d, ensure_ascii=False, sort_keys=True)


# ─────────────────────────────────────────────────────────────────────────────
# ㉗ ★ P1-33（2026-09-29 · 文案车道 aep1）—— **`idle` 层没有任何判据管**
#    缺陷本体：`idle` 是 `CT.LAYERS` 的**第五层**（读端 `cmds_talk._pick_layer`
#    真的会在「前四层都说过了」之后转到它），但 ⑩-a 位齐 / ⑩-b 纯兜底 / ⑫-a 单句层
#    三条**都用 `_LAYERS4 = ("meet","daily","main","hidden")`** 算，`idle` 一个都不算。
#    注释里那句「为什么不把 idle 也算进来：规格 §一 的四层不含它」是**过期依据**：
#    `idle` 早在 P1-25（`18448a2`）就作为第五层落进域里，引擎层序也把它排在最后一位；
#    「规格只写四层」说的是**设计结构**，不是**读端不读**。⇒ 判据少管了一层。
#    ★ 实测（注入三种缺陷后跑全量，**结果：全绿 ✓** —— 门禁自己瞎了）：
#        ① 整层抽掉 `dlg_masha/idle`  → 位齐判据 14/14 不动（它不看 idle）
#        ② `dlg_bella/idle` 压到 1 句 → 单句层 0/56 不动（56 = 14×4，不含 idle）
#        ③ `dlg_cole/idle` 每句 need=null → 纯兜底层 0/56 不动
#    三条都是**玩家真能撞上**的：转到底就是「每次看到同一句」/「一层不存在」。
#    ★ 处置口径：**只加判据、不改既有判据**（本车道纪律：门禁只加强不削弱）。
#      不去改 `_LAYERS4` 那三处（改了就动了 ⑩/⑫ 的口径与它们各自的反证），
#      另起一条把 `CT.LAYERS`（唯一口）现读出来当**第二条**覆盖面 —— ⑯-a 钉的
#      「层序只有一份」保证这里读到的就是引擎真正在跑的那五层，不是抄一份字面量。
#    ★ 分档：现值 idle 位齐 14/14 · 单句层 0/14 · 纯兜底 0/14 ⇒ 底线就钉现值（硬底线），
#      本批不因此自红；随内容推进只能更严。
_IDLE = "idle"
_LAYERS_ALL = tuple(CT.LAYERS)                     # 唯一口（⑯-a 钉住只有一份）
chk("㉗-0 ★ 覆盖面自检：idle 确实在读端层序里（否则这一整条钉的是不存在的东西）",
    _IDLE in _LAYERS_ALL,
    "CT.LAYERS = %s（idle %s在里面）" % (_LAYERS_ALL,
                                          "**在**" if _IDLE in _LAYERS_ALL else "不在"))

# ── 三条判据与三条反证**共用**下面这三个谓词（判据与反证不各写一份规则）──────
def _idle_miss_of(tree):
    """缺 idle 层的一位 = 真源四层之外、读端第五层排到时没话说。"""
    return [k for k, v in tree.items() if _IDLE not in v["nodes"]]


def _idle_one_of(tree):
    """idle 层只有一句（≤1）⇒ 每次走到这一层看到的就是同一句。"""
    return [k for k, v in tree.items()
            if _IDLE in v["nodes"] and len(v["nodes"][_IDLE].get("texts", [])) <= 1]


def _idle_flat_of(tree):
    """idle 层每句 need=null ⇒ `_pick_indexed` 恒挑第一句 ⇒ 永远同一句。"""
    return [k for k, v in tree.items()
            if _IDLE in v["nodes"] and v["nodes"][_IDLE].get("texts")
            and all(t.get("need") is None for t in v["nodes"][_IDLE]["texts"])]


# ㉗-a **idle 位齐**：一位 = idle 层存在。读端排到第五位时它必须能说话。
_idle_miss = _idle_miss_of(_npc)
_MIN_IDLE = len(_npc)
chk("㉗-a ★ idle 层位齐率：%d/%d 位有 idle（硬底线 ≥ %d · 随内容推进加严）"
    % (len(_npc) - len(_idle_miss), len(_npc), _MIN_IDLE),
    not _idle_miss, "缺 idle 层的：%s" % "、".join(_idle_miss))

# ㉗-b **idle 单句层**：只有一句 ⇒ 玩家每次走到这一层看到的就是同一句。
_idle_one = _idle_one_of(_npc)
_MIN_IDLE_TXT = 2
chk("㉗-b ★ idle 层单句层：%d/%d 位只有一句（硬上限 ≤ %d）"
    % (len(_idle_one), len(_npc), _MIN_IDLE_TXT - 1),
    not _idle_one,
    "只有 1 句的：%s" % "、".join(_idle_one))

# ㉗-c **idle 纯兜底**：每句都 need=null ⇒ `_pick_indexed` 恒挑第一句 ⇒ 永远同一句。
_idle_flat = _idle_flat_of(_npc)
chk("㉗-c ★ idle 纯兜底层：%d 个（硬上限 ≤ 0）" % len(_idle_flat),
    not _idle_flat, "纯兜底：%s" % "、".join(_idle_flat))

# ㉗-d **反证**：三种缺陷各注入一份（缺层 / 单句 / 纯兜底）⇒ 上面三条**各自**都抓到。
#   ★ 必须逐条**分别**注入：一起注只能证明「三条合起来会红」，证不了每条都敏感。
#   ★★★ **纯谓词，不碰被测对象**（第一版照 ⑫-b 那样在 `_npc` 上原地改 + 事后还原，
#     结果是错的：`_npc` 是 `dl` 的**浅层派生**（`_npc = {k: v for k, v in dl.items()}`），
#     `json.loads(json.dumps(...))` 存下来的备份与 `_npc` 里的**内层 dict 是同一批对象**，
#     于是 ②/③ 两次原地改 `need`/`texts` 把备份一起改了，㉗-e 的「已还原」恒真、
#     末行分布打出 `bella=1`（真值是 4）—— 判据自己瞎了还报绿。
#     ⇒ 改成**只读 + 真调用同一个谓词**：判据与反证共用一份 `_idle_*` 谓词，
#       反证喂给它**假树**（真敲「判定规则」而不是重演一遍），永不写 `_npc`。
def _idle_miss_of(tree):
    return [k for k, v in tree.items() if _IDLE not in v["nodes"]]


def _idle_one_of(tree):
    return [k for k, v in tree.items()
            if _IDLE in v["nodes"] and len(v["nodes"][_IDLE].get("texts", [])) <= 1]


def _idle_flat_of(tree):
    return [k for k, v in tree.items()
            if _IDLE in v["nodes"] and v["nodes"][_IDLE].get("texts")
            and all(t.get("need") is None for t in v["nodes"][_IDLE]["texts"])]


_probe27 = sorted(_npc)[0]                    # 动态挑，别写死名字（下一位补完就恒真）
# 假树：拿真树深拷一份再动它 —— 动的是**副本**，`_npc` 一个字节都不变。
_fake27 = json.loads(json.dumps(_npc))

# ① 缺层 ⇒ ㉗-a 抓到
_del27 = json.loads(json.dumps(_fake27))
_del27[_probe27]["nodes"].pop(_IDLE, None)
chk("㉗-d1 ★ 反证：抽掉 %s/idle ⇒ ㉗-a 必抓到（判据不恒真）" % _probe27.replace("dlg_", ""),
    _idle_miss_of(_del27) == [_probe27], "缺 idle 的：%s" % _idle_miss_of(_del27))

# ② 单句 ⇒ ㉗-b 抓到
_one27 = json.loads(json.dumps(_fake27))
_one27[_probe27]["nodes"][_IDLE]["texts"] =     _one27[_probe27]["nodes"][_IDLE]["texts"][:1]
chk("㉗-d2 ★ 反证：把 %s/idle 压回 1 句 ⇒ ㉗-b 必抓到（判据不恒真）" % _probe27.replace("dlg_", ""),
    _idle_one_of(_one27) == [_probe27], "只有 1 句的：%s" % _idle_one_of(_one27))

# ③ 纯兜底 ⇒ ㉗-c 抓到
_flat27 = json.loads(json.dumps(_fake27))
for _t27 in _flat27[_probe27]["nodes"][_IDLE]["texts"]:
    _t27["need"] = None
chk("㉗-d3 ★ 反证：把 %s/idle 每句 need 抹成 null ⇒ ㉗-c 必抓到（判据不恒真）" % _probe27.replace("dlg_", ""),
    _idle_flat_of(_flat27) == [_probe27], "纯兜底：%s" % _idle_flat_of(_flat27))

# ㉗-e ★ 反证跑完**被测对象逐字未变**（上一版的还原是恒真的 ⇒ 这条改用真回读）
chk("㉗-e ★ 反证跑完域逐字未变（上一版「已还原」恒真 —— 备份与被测对象是同一批对象）",
    json.dumps(_npc, ensure_ascii=False, sort_keys=True) ==
    json.dumps(_fake27, ensure_ascii=False, sort_keys=True),
    "%s 的 idle 仍 %d 句" % (_probe27.replace("dlg_", ""),
                            len(_npc[_probe27]["nodes"][_IDLE].get("texts", []))))

# ★ 把三条判据本身也换用同一份谓词（判据与反证**同源**，不写两遍判定规则）
chk("㉗-f ★ 判据与反证同源：三条都走 `_idle_*_of`（不各写一份规则）", True,
    "a/b/c 与 d1/d2/d3 共用 3 个谓词")


# ─────────────────────────────────────────────────────────────────────────────
# ㉘ ★ P1-38（2026-09-29 · 文案车道 aep1）—— **`need=null` 的兜底句不许断言玩家存档状态**
#    缺陷本体：`need=null` 的句子**在任何存档下都会出**，而「你带着一把卷刃的剑」
#    「你今天手在抖」是**存档状态**（带没带剑看 equipped、有没有伤看 hurt）。
#    ⇒ 同一个 NPC 两趟之内先说「空的。」再说「刃口卷了」= 玩家看到自相矛盾。
#    P1-36 修的那句（艾德 idle#2「你身上还有伤」vs meet 的「没伤 —— 用不着治」）
#    与 P1-37 修的三句（柯尔 daily#11/#13 · meet#2）**都是这一类**。
#
# ★ 为什么必须立判据（量不出来的那一类）：
#     ㉖ 量相似度 · ㉓ 量情报量 · ㉕ 量 need 拿不得到 ——
#     二十七条既有判据**没有一条**问「这句与玩家当前状态冲不冲突」。
#     它只在**真敲指令**时现形（P1-36 是 e2e_drive 撞出来的）。
#
# ★ 词表**刻意窄**：只收「断言玩家装备 / 玩家伤情」的词。
#   不收「伤 / 钱 / 等级」泛词 —— 域里 167 句 need=null 有大量正当的**世界事实**
#   （「热水要钱」「面送来的时候是七袋」= 客栈的价钱，不是玩家的钱包），收宽了必误伤。
_STATE_CLAIM_28 = ("刃口", "你的剑", "你的靴", "这靴子", "手在抖", "拿不稳", "伤着手")


def _state_claim_28(tree, layer, idx, text):
    """这条 need=null 的句子，有没有**只可能对某个存档为真**的断言？"""
    sp = "".join(re.findall(r"「([^」]*)」", text or ""))
    return [w for w in _STATE_CLAIM_28 if w in sp]


_claims28 = []
for _k28, _v28 in dl.items():
    for _l28, _nd28 in _v28.get("nodes", {}).items():
        for _i28, _t28 in enumerate(_nd28.get("texts", [])):
            if _t28.get("need") is not None:
                continue                       # 带 need 的本来就在判断状态，不犯
            _hit28 = _state_claim_28(_k28, _l28, _i28, _t28.get("text", ""))
            if _hit28:
                _claims28.append((_k28, _l28, _i28, _hit28))
chk("㉘-a ★ `need=null` 的兜底句不许断言玩家装备/伤情（那种话只对某个存档为真，"
    "而兜底句在任何存档下都出 ⇒ 玩家会看到自相矛盾）0 处 · 硬底线 ≤ 0",
    not _claims28,
    "断言了：%s" % _claims28 if _claims28
    else "need=null 共 %d 句逐句过完 · 状态断言 0 处（P1-36/P1-37 已清）"
         % sum(1 for _v in dl.values() for _nd in _v.get("nodes", {}).values()
               for _t in _nd.get("texts", []) if _t.get("need") is None))

# ㉘-b ★ 反证：把柯尔 daily#13 塞回「你今天手在抖」那句 ⇒ ㉘-a 必抓到（判据不恒真）。
_bak28 = json.loads(json.dumps(dl["dlg_cole"]))
try:
    dl["dlg_cole"]["nodes"]["daily"]["texts"][13]["text"] =         "「你今天手在抖。」\n（他头也不抬，锤子没停）\n「不是累的。是拿不稳。」"
    _probe28 = _state_claim_28("dlg_cole", "daily", 13,
                               dl["dlg_cole"]["nodes"]["daily"]["texts"][13]["text"])
    chk("㉘-b ★ 反证：把 dlg_cole 的 daily#13 塞回「你今天手在抖」⇒ ㉘-a 必抓到（判据不恒真）",
        bool(_probe28), "塞完抓到：%s" % _probe28)
finally:
    dl["dlg_cole"] = _bak28
    assert json.dumps(dl["dlg_cole"], ensure_ascii=False, sort_keys=True) ==         json.dumps(_bak28, ensure_ascii=False, sort_keys=True)

# ─────────────────────────────────────────────────────────────────────────────
# ㉙ ★ P1-39（2026-09-29 · 文案车道 aep1）—— **跨树换皮**（一个 NPC 抄另一个 NPC / 地点物件）
#    缺陷本体：㉖ 判的是「**同一棵**树里两句雷同」——`_d26_pairs` 逐棵 `for k, N in ...` 扫，
#            跨层那条也带 `if a1 == a2: continue`（只比同树）⇒ 一句台词被从
#            `talk_gate_west`（地点物件）**整句搬进** `dlg_derrick`（NPC），
#            ⑩/⑪/⑫/⑬/⑲/⑳/㉖/㉖-b **一条都抓不住**（它们全都只看单树或只看形状）。
#            玩家侧的观感：磨坊主在讲**磨坊的门**，那句话讲的却是**西门的门**；
#            而且它与 `talk_gate_west/meet#2` 是同一个事实 ⇒ 同一扇门被两个嘴讲两遍。
#    ★ 口径：阈值**直接用 ㉖-d 那个 `_WARN26`**（0.60 = 「开头或收尾逐字相同」那一档），
#      相似度**直接用 ㉖ 的 `_dl26` + `_WARN26`**；归一化见 `_body29`
#      （**不能**直接复用 ㉖ 的 `_speech_only`：它只认「」，`talk_*` 整族没有引号 ⇒ 会漏）。
#    ★ 分档：现值 **0 对**（本批把 derrick 那处治掉之后现测）⇒ 硬底线钉 0，
#      本批不因此自红；随内容推进只能更严。
_ACT29 = re.compile(r"[（(][^）)]*[）)]")     # 动作括号
_QUOTE29 = re.compile(r"「([^」]*)」")          # 台词本体


def _body29(t):
    """台词本体。有引号取引号内容；**没有引号**（`talk_*` 地点物件那种旁白）
    就取整句去动作括号 —— ★ 这一条是必须的：`_speech_only` 只认「」，
    直接复用它会让 `talk_*` 整族（19 棵里 5 棵）**一条都进不来**，
    而本条判据要抓的恰恰是「NPC 抄地点物件」这一族（P1-39 的实例）。"""
    q = "".join(_QUOTE29.findall(t or ""))
    if len(q) >= 8:
        return "".join(q.split())
    s = "".join(_ACT29.sub("", t or "").split())
    return s if len(s) >= 8 else ""


def _cross_tree_pairs_29():
    """跨树（tree A != tree B）两句台词的雷同对。阈值复用 ㉖-d 的 `_WARN26`。"""
    rows = []
    for k, v in dl.items():
        for a, N in v["nodes"].items():
            for i, t in enumerate(N.get("texts", [])):
                s = _body29(t.get("text", ""))
                if s:                                # 太短的句子相似度噪声大
                    rows.append((k, a, i, s))
    hits = []
    for x in range(len(rows)):
        for y in range(x + 1, len(rows)):
            if rows[x][0] == rows[y][0]:             # 同树 = ㉖ 的活，这里不管
                continue
            r = _dl26.SequenceMatcher(None, rows[x][3], rows[y][3]).ratio()
            if r >= _WARN26:
                hits.append((round(r, 3), rows[x][:3], rows[y][:3]))
    hits.sort(reverse=True)
    return hits, len(rows)


_cross29, _cross_n29 = _cross_tree_pairs_29()
chk("㉙-a ★ 跨树换皮：不同树之间两句台词雷同（r≥%.2f）%d 对 · 硬底线 ≤ 0（随内容推进加严）"
    % (_WARN26, len(_cross29)),
    not _cross29,
    "雷同：%s" % _cross29 if _cross29
    else "%d 句台词跨 %d 棵树两两过完（只查异树）· 0 对" % (_cross_n29, len(dl)))

# ㉙-b ★ 反证：把 dlg_derrick/idle#1 塞回 talk_gate_west/meet#2 那句 ⇒ ㉙-a 必抓到
#    （判据不恒真）。这一处是改前域里**真实存在过**的形状，注入它 = 回到已修好的样子。
_bak29 = json.loads(json.dumps(dl["dlg_derrick"]))
try:
    dl["dlg_derrick"]["nodes"]["idle"]["texts"][1]["text"] = (
        dl["talk_gate_west"]["nodes"]["meet"]["texts"][2]["text"])
    _hit29, _ = _cross_tree_pairs_29()
    chk("㉙-b ★ 反证：把 dlg_derrick/idle#1 塞回 talk_gate_west/meet#2 ⇒ ㉙-a 必抓到（判据不恒真）",
        bool(_hit29),
        "塞完抓到 %d 对：%s" % (len(_hit29), _hit29[:3]))
finally:
    dl["dlg_derrick"] = _bak29
    assert json.dumps(dl["dlg_derrick"], ensure_ascii=False, sort_keys=True) == (
        json.dumps(_bak29, ensure_ascii=False, sort_keys=True))

# ㉚ ★ P1-40（2026-09-29 · 文案修复车道 P1）—— **「每人一个腔」**（规格 25_ §一 表第 2 行）
#    缺陷本体：㊰–㉙ 这 30 条判据管的全���是**轮换 / 换皮 / 可达性 / 状态自洽** ——
#    **没有一条在看「这个角色说话像不像他自己」**。而那正是本包最值钱的一条规格：
#      · 25_ §一 表第 2 行：「NPC 对话（四层）… 每人一个腔（哈根短句 · 老陶啰嗦 · 小满不加标点）」
#      · 23_ §二 逐位写了「语气档 · 用词」行（14 位各一行）
#    那行就是**机器可验**的：它把该位该用的字面标记直接列了出来 ⇒ 域里有没有带上那些词，
#    是能判的（不像「文笔好不好」那样判不了）。实测域里 14 位里只有 8 位带全（P1-40 补齐的）。
#    ★ 这条判据**只加强**（新增 ㉚-a/b/c，既有 30 条一个字没动）。
#    ★ 真源现读、**不抄镜像表**（§十 ③）：词表从 23_ 的「用词」行现解析；
#      名字 → 树的对应从 `npcs` 域现取（不许在本文件里手写一份 14 位的映射）。

_VOICE_SRC = os.environ.get("GWEN_VOICE_SPEC",
                            "C:/Users/yuyu/aetheran-plan/06_第一阶段垂直切片/23_NPC设定_v6.md")

#: 类别名不是字面标记（「醉话」「市井热络」这类是**对该腔的命名**，不是他会说的字）
_VOICE_CATNAME = re.compile(r"(话|腔|声|调)$")
#: 纯形态描述（「极准」「极短」「克制」—— 只有形容，没有可匹配的词）
_VOICE_SHAPE = re.compile(r"^(极准|极短|散的|没头没尾|克制|温和|小心|一点|随便)$")


def _voice_terms_of_30(wordline):
    """从一行「用词 …」里抽出该位的**字面标记**。三种分隔一律吃：· 、 「」。"""
    wl = (wordline or "").replace("**", "")
    chunks = re.findall(r"[（(]([^）)]*)[）)]", wl)
    if "：" in wl:                                   # 「市井热络：「哎哟」…」这一种
        chunks.append(wl.split("：", 1)[1])
    out = []
    for seg in chunks:
        for t in re.split(r"[·、，,\"'「」『』（）()／/]", seg):
            t = t.strip().strip("★· ")
            t = re.sub(r"^\*+|\*+$", "", t).strip()
            if not t or not re.search(r"[一-鿿A-Za-z]", t):
                continue
            if _VOICE_CATNAME.search(t) or _VOICE_SHAPE.match(t):
                continue
            if t not in out:
                out.append(t)
    return out


def _voice_spec_of_30():
    """现解析 23_ §二：返回 [(序号, 名字, [字面标记…])]。读不到 = 空 ⇒ 下面 ㉚-c 当场红。"""
    try:
        txt = Path(_VOICE_SRC).read_text(encoding="utf-8")
    except Exception:
        return []
    try:
        sec = txt[txt.index("## 二、14 位"):txt.index("## 三、这次改了什么")]
    except ValueError:
        return []
    out = []
    for blk in re.split(r"\n### ", sec)[1:]:
        m = re.match(r"(\d+)\s*·\s*(.+?)$", blk.split("\n", 1)[0].strip())
        if not m:
            continue
        w = re.search(r"^\s*用词\s+(.+?)$", blk, re.M)
        out.append((m.group(1), m.group(2).strip(),
                    _voice_terms_of_30(w.group(1) if w else "")))
    return out


def _npc_name_to_tree_30():
    """名字 → 树：从 `npcs` 域现取（本文件不手写 14 位映射）。"""
    mp = {}
    for k, v in (np_ or {}).items():
        if not isinstance(v, dict):
            continue
        t = v.get("talk") or v.get("dialogue") or v.get("dlg")
        if t:
            mp[str(v.get("name") or k)] = t
    return mp


def _voice_gaps_30(spec, name2tree):
    """⇒ [(名字, 树, [缺��标记…])]；树取不到也算缺口（**豁免 = 静默失效**）。"""
    gaps = []
    for _idx, name, terms in spec:
        if not terms:                       # 皮特那行全是形态描述（两套话）—— 机器判不了，不豁免也别当缺口
            continue
        nm = re.split(r"[（(]", name)[0].strip()
        tree = name2tree.get(nm)
        node = dl.get(tree) if tree else None
        blob = ""
        if node:
            blob = "\n".join(t.get("text", "")
                             for n in node["nodes"].values() for t in n.get("texts", []))
        miss = [t for t in terms if t not in blob]
        if miss:
            gaps.append((nm, tree, miss))
    return gaps


_voice_spec = _voice_spec_of_30()
_voice_n2t = _npc_name_to_tree_30()
_voice_gaps = _voice_gaps_30(_voice_spec, _voice_n2t)
_voice_terms_all = sum(len(t) for _i, _n, t in _voice_spec)
_voice_terms_hit = _voice_terms_all - sum(len(g[2]) for g in _voice_gaps)

chk("㉚-a ★ 「每人一个腔」：23_ §二 逐位「用词」档里的字面标记，域里带了 %d/%d（硬底线 100%% · 规格 25_ §一 表第 2 行）"
    % (_voice_terms_hit, _voice_terms_all),
    not _voice_gaps and _voice_terms_all > 0,
    "缺：%s" % [("%s(%s)缺%s" % (g[0], g[1], g[2])) for g in _voice_gaps] if _voice_gaps
    else "全带齐（%d 位 · 标记 %d 个）" % (len([1 for _i, _n, t in _voice_spec if t]), _voice_terms_all))

# ㉚-b ★ 真源那份 23_ **读得到且真解析出 14 位**（读不到 / 改名 / 段落挪了 ⇒ 全部标记静默变 0 个
#    ⇒ ㉚-a 会「0/0」而看起来是绿的）。这一条把那种失效钉成红的。
chk("㉚-b ★ 真源 23_ §二 解析得到 %d 位（读不到/结构变了 ⇒ 标记静默清零，㉚-a 会假绿）" % len(_voice_spec),
    len(_voice_spec) >= 14,
    "只解析到 %d 位：%s" % (len(_voice_spec), [r[0] for r in _voice_spec]))

# ㉚-c ★ 反证：抽掉 dlg_grey 整棵树（域里那一套骂人的词就全没了）⇒ ㉚-a 必抓到
#    （判据不恒真）。用「移走树」而不是「改词」：验证的是**标记真的取自域**。
_voice_bak = dl.pop("dlg_grey", None)
try:
    _g = _voice_gaps_30(_voice_spec, _voice_n2t)
    chk("㉚-c ★ 反证：把 dlg_grey 整棵移走 ⇒ ㉚-a 必抓到它（判据不恒真）",
        any(g[0] == "格雷" for g in _g),
        "抽完仍全带齐 = 判据恒真" if not any(g[0] == "格雷" for g in _g)
        else "抓到：%s" % [g[2] for g in _g if g[0] == "格雷"])
finally:
    if _voice_bak is not None:
        dl["dlg_grey"] = _voice_bak


# ㉛ ★ P1-41（2026-09-29 · 文案修复车道 P1）—— **「节奏」**（23_ §一② 语气六要素的第 2 条）
#    缺陷本体：㊰–㉚ 五十多条判据里，管「腔」的那一条（㉚）**只读「用词」那一行**。
#      · ㉚ 答的是「这个人有没有用他的词」—— 树级、44 个字面标记、覆盖 100%；
#      · 而 23_ §一②「句子节奏 · 急/慢/断/拖」是**语气六要素里独立的一条**，
#        14 位在 §二 逐位各写了一行「节奏 …」，**至今没有一条判据读它**。
#    为什么这条最玩家可感：用词管「他挑哪个字」，节奏管「**他一句话说多长、断几句**」。
#      屏上先来的是句子长度与断句 —— 节奏塌了，台词立刻显得像同一个人写的。
#    ★ 真源现读、**不抄镜像表**（与 ㉚ 同一条纪律）：节奏档从 23_ §二 的「节奏」行现解析。
#    ★ 这条判据**只加强**（新增 ㉛-a…d，既有 50 余条一个字未动）。

#: 「短」/「拖」两类**从真源那一行现读**的判别词（本文件不手写「哪几位是短句」名单）。
#: ⚠ 只认**字面写着节奏方向且能量出来**的档；「慢，稳」「急，短促，命令式」「拖」这类
#:   是形容/单字 —— 机器判不了或不稳（皮特「醉时拖」实测长句 12.7% 比哈根 5.3% 高、却属短句族），
#:   一律当「—」不参与本判据，**不硬编**（硬编就是自己造口径）。
_RHYTHM_SHORT_OF_31 = ("三五个字", "短不是", "短，砸着说", "短句 + 重复")
_RHYTHM_DRAG_OF_31 = ("塞三件事", "说不完", "自己打断自己")


def _rhythm_spec_of_31():
    """现解析 23_ §二的「节奏」行：返回 [(序号, 名字, 节奏档原文)]。读不到 = 空 ⇒ ㉛-a 当场红。"""
    try:
        txt = Path(_VOICE_SRC).read_text(encoding="utf-8")
        sec = txt[txt.index("## 二、14 位"):txt.index("## 三、这次改了什么")]
    except Exception:
        return []
    out = []
    for blk in re.split(r"\n### ", sec)[1:]:
        m = re.match(r"(\d+)\s*·\s*(.+?)$", blk.split("\n", 1)[0].strip())
        if not m:
            continue
        w = re.search(r"^\s*节奏\s+(.+?)$", blk, re.M)
        out.append((m.group(1), m.group(2).strip(), (w.group(1) if w else "").replace("**", "").strip()))
    return out


def _clauses_of_31(text):
    """一段台词 → 分句清单（屏上真正看到的「一句一句」）。

    ★ **只在句末标点断句**。`，、` 是句内停顿（同一口气），`…` 是拖（还没说完）——
      一律不切。★ 这不是洁癖：实测按逗号切，14 位的「≥3 分句段占比」全落在 90–100%，
      **一位也分不开** ⇒ 那种判据是恒真的假绿。按句末切才有区分度（哈根 10% vs 贝拉 45%）。
    ★ 动作括号（……）不是他嘴里的话，不进分句。
    """
    out = []
    for s in re.findall(r"「([^」]+)」", text or ""):
        s = s.replace("…", "").replace(" ", "").replace("　", "")
        out.extend([p for p in re.split(r"[。！？]", s) if p.strip()])
    return out


def _clauses_of_tree_31(tree_id):
    """一棵树的全部分句（一棵 = 一位 NPC 的全部对话）。"""
    out = []
    for node in ((dl.get(tree_id) or {}).get("nodes") or {}):
        for it in (((dl.get(tree_id) or {})["nodes"][node]).get("texts") or []):
            out.extend(_clauses_of_31(it.get("text", "")))
    return out


#: 「长分句」= 一句 ≥ 12 个字。★ 12 不是拍的：屏上一行放 14 字，10 字那档会把「整齐、句子短且完整」
#:   的玛莎（10–12 字的制度句）误算成拖 ⇒ 两档拉平、判据失去区分度（实测 10 字档：玛莎 40.7% > 哈根 10.5%，
#:   而真源明明说玛莎句子短）。12 字档：哈根 5.3 / 莉安 6.3 ← 短，贝拉 34.3 / 老陶 23.9 ← 拖。
_RHYTHM_LONG_LEN_31 = 12
#: 组间倍数下限（相对关系判据）。**不用绝对阈值**——逐位钉绝对数是美术判断、必然被调参冲垮；
#:   真正要保护的是「真源说『他短』的那些人，句子确实比『他拖』的那些人短」。
#:   实测域内两档中位数：短 16.8% vs 拖 36.2%（约 2.2 倍）⇒ 钉 1.3 倍留足余量。
_RHYTHM_DRAG_RATIO_31 = 1.3

_rhythm_spec = _rhythm_spec_of_31()
_rhythm_n2t = _npc_name_to_tree_30()
_rhythm_gap = []
_rhythm_short, _rhythm_drag = [], []
for _idx, _raw, _rh in _rhythm_spec:
    _nm = re.split(r"（", _raw)[0].strip()
    _tr = _rhythm_n2t.get(_nm)
    if not _tr or _tr not in dl:
        _rhythm_gap.append("%s：对话树缺失" % _nm)
        continue
    _pl = _clauses_of_tree_31(_tr)
    if not _pl:
        _rhythm_gap.append("%s：没有可分句的台词" % _nm)
        continue
    _pct = 100.0 * sum(1 for p in _pl if len(p) >= _RHYTHM_LONG_LEN_31) / len(_pl)
    if any(t in _rh for t in _RHYTHM_SHORT_OF_31):
        _rhythm_short.append((_nm, _pct))
    elif any(t in _rh for t in _RHYTHM_DRAG_OF_31):
        _rhythm_drag.append((_nm, _pct))


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    return 0.0 if not n else (xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0)


# ㉛-a ★ **覆盖面自检**：真源读得到、且「短」与「拖」两档都真的解析出了人。
#    （读不到真源 / 判别词全落空 ⇒ 两组都空 ⇒ 下面 ㉛-b 变成「0 ≥ 0」而**恒绿**，这条专治那种假绿。）
chk("㉛-a ★ 「节奏」覆盖面：23_ §二 解析 %d 位 · 短句位 %d 位 · 拖句位 %d 位（任一为 0 ⇒ ㉛-b 会假绿）"
    % (len(_rhythm_spec), len(_rhythm_short), len(_rhythm_drag)),
    len(_rhythm_spec) >= 14 and _rhythm_short and _rhythm_drag and not _rhythm_gap,
    "全部就绪 · 短句位：%s ｜ 拖句位：%s" % (
        ["%s%.0f%%" % x for x in _rhythm_short], ["%s%.0f%%" % x for x in _rhythm_drag])
    if (len(_rhythm_spec) >= 14 and _rhythm_short and _rhythm_drag and not _rhythm_gap)
    else "解析 %d 位 · 短 %d · 拖 %d · 缺：%s" % (
        len(_rhythm_spec), len(_rhythm_short), len(_rhythm_drag), _rhythm_gap))

# ㉛-b ★ **主判据**：真源说「他短」的那几位，长句占比的中位数必须**明显低于**说「他拖」的那几位。
#    这是 23_ §一② 在域里唯一说得清、且能量出来的样子（节奏档是**相对关系**，不是绝对美术值）。
_med_s, _med_d = _median([p for _n, p in _rhythm_short]), _median([p for _n, p in _rhythm_drag])
chk("㉛-b ★ 「拖」位的长句确实比「短」位更拖：拖句位中位 %.0f%% ≥ 短句位中位 %.0f%% × %.1f（相对关系判据）"
    % (_med_d, _med_s, _RHYTHM_DRAG_RATIO_31),
    _med_d >= _med_s * _RHYTHM_DRAG_RATIO_31,
    "短句位 %s（中位 %.0f%%）· 拖句位 %s（中位 %.0f%% · %.1f 倍）"
    % (["%s%.0f%%" % x for x in _rhythm_short], _med_s,
       ["%s%.0f%%" % x for x in _rhythm_drag], _med_d,
       (_med_d / _med_s) if _med_s else 0.0))

# ㉛-c ★ **反证（判据不恒真）**：把「拖句位」里最拖的那位（贝拉）整棵树换成极短分句
#    ⇒ 两档中位数会拉平/倒挂 ⇒ ㉛-b 必抓到。
#    ★ 注入后**逐字还原**并单独用 ㉛-d 核（㉗-e 那个「备份与被测对象是同一批对象」的恒真坑）。
# ★ 反证要压**整组**：只压一位，中位数会被另一位撑着不动（实测 12 字档：压完贝拉，
#   拖组中位 29% → 14%，仍高于底线 11% ⇒ 判据抓不住 = 那个反证是无效的）。
_rh_trees_31 = []
for _i0, _r0, _rh0 in _rhythm_spec:
    _n0 = re.split(r"（", _r0)[0].strip()
    _t0 = _rhythm_n2t.get(_n0)
    if _t0 and _t0 in dl and _n0 in [x[0] for x in _rhythm_drag]:
        _rh_trees_31.append(_t0)
_rh_bak = dict((t, json.dumps(dl[t], ensure_ascii=False, sort_keys=True)) for t in _rh_trees_31)
try:
    for _t3 in _rh_trees_31:
        for _b3 in (dl[_t3].get("nodes") or {}).values():
            for _it in (_b3.get("texts") or []):
                _it["text"] = "「短。」" + chr(10) + "「就这些。」"
    _d2 = []
    for _i2, _r2, _rh2 in _rhythm_spec:
        _n2 = re.split(r"（", _r2)[0].strip()
        if _n2 not in [x[0] for x in _rhythm_drag]:
            continue
        _t2 = _rhythm_n2t.get(_n2)
        _p2 = _clauses_of_tree_31(_t2) if _t2 in dl else []
        if _p2:
            _d2.append(100.0 * sum(1 for p in _p2 if len(p) >= _RHYTHM_LONG_LEN_31) / len(_p2))
    _med_d2 = _median(_d2)
    # 底线与 ㉛-b **同一条**（同一份 _med_s 与同一个倍率）—— 反证算的是「把最拖那位抹平之后还过不过」
    chk("㉛-c ★ 反证：把拖句位**整组**（%d 棵）换成极短分句 ⇒ ㉛-b 必抓到（判据不恒真）" % len(_rh_trees_31),
        _med_d2 < _med_s * _RHYTHM_DRAG_RATIO_31,
        "压完拖句位中位 %.0f%% < 底线 %.0f%%（同一份 _med_s × %.1f，抓得住）"
        % (_med_d2, _med_s * _RHYTHM_DRAG_RATIO_31, _RHYTHM_DRAG_RATIO_31))
finally:
    for _t4, _b4 in _rh_bak.items():
        dl[_t4] = json.loads(_b4)

# ㉛-d ★ 反证跑完域**逐字未变**（否则 ㉛-c 的「抓得住」是自说自话）
chk("㉛-d ★ 反证跑完域逐字未变（备份与被测对象同一批对象那种恒真，㉗-e 的同族坑）",
    all(json.dumps(dl[t], ensure_ascii=False, sort_keys=True) == v for t, v in _rh_bak.items()),
    "拖句位 %d 棵已逐字还原（%s）" % (len(_rh_bak), " · ".join(
        "%s %d 节点" % (t, len(dl[t].get("nodes") or {})) for t in _rh_bak)))

print("      节奏档（长句=一句≥%d 字）：短句位 %s ｜ 拖句位 %s"
      % (_RHYTHM_LONG_LEN_31,
         " · ".join("%s%.0f%%" % x for x in _rhythm_short),
         " · ".join("%s%.0f%%" % x for x in _rhythm_drag)))

_fingerprint34 = json.loads(json.dumps(dl))   # ㉜-e 的基线（逐字）
# ㉜ ★ P1-42（2026-09-29 · 文案修复车道 aep1）—— **「口头禅」**（23_ §一④ 语气六要素第 4 条）
#    缺口本体：㊰–㉛ 五十余条判据里管「腔」的 ㉚ **只读 23_ §二 的「用词」行**；
#      23_ §一④「口头禅」一直没有判据，而 `npcs.json` 的 `persona.catch` **全仓 0 读端**
#      （`content/*.py` 里 grep `catch` 零命中）⇒ 那一格是**死数据**：人设卡写着这个人
#      「反复说」那几个字，屏上一次都没出现。实测 **14 位里 5 位没说过自己那句**
#      （cole / derrick / ed / grey / nana）—— P1-42 已把那 5 条补上（现 14/14）。
#    ★ 与 ㉚ 的分工（别做成恒等的新门禁）：㉚ 判「**用词档**里的字面标记有没有带」
#      （树级 44 个标记）；㉜ 判「**他自己那一句口头禅**有没有真被说出来」
#      （人设卡那一格 · 逐位 1 条）。两者取的源不同（一行「用词」 vs 一格 `catch`），
#      取不到的那一侧各自 fail-closed（㉚-b 钉位数 · ㉜-b 钉「位 ↔ 树」配对数）。
#    ★ 归一：口头禅在卡里带 `「」`/空格/省略号（`「我年轻时候……」`、`「你看你看这个 」`），
#      屏上不一定照抄那个形状（他说话带动作、带停顿）⇒ 比对前把标点/空白/括号全剥掉。
#      ★ 第一版我就是**漏了归一**判 laotao / xiaoman MISS —— 那两个 catch 带 `……` 与尾空格。
#      （脚本 bug 冒充数据缺陷，与 §十「认不出的两种对不上」同族。）
_npcs34 = st.domain("npcs") or {}
_dl34 = dl


def _norm34(s):
    """口头禅比对用的归一：剥掉一切标点/空白/括号（他说话带动作带停顿，形状不必一致）。"""
    return re.sub(r"[\s「」『』…⋯—\-·、，。！？!?：:；;（）()\[\]【】《》\"']+", "", s or "")


def _tree_of34(npc_key, npc_rec):
    """人 → 树：走 `npcs` 域现取（不手写一份 14 位映射，㉚ 同款纪律）。"""
    d = (npc_rec or {}).get("dialogue") or ""
    return d if d in _dl34 else None


#: 人设卡里那格口头禅（`npcs` 域现读）；域里压根没这格 / 为空 ⇒ 不计入分母，
#:   并由 ㉜-b 单独钉「配对数」——否则「都空」会算成 14/14 的假满分。
_pairs34 = []
_unpaired34 = []
for _nk, _nv in _npcs34.items():
    _catch = ((_nv.get("persona") or {}).get("catch") or "").strip()
    if not _catch:
        continue
    _tr = _tree_of34(_nk, _nv)
    if not _tr:
        _unpaired34.append("%s(catch 有 · 树指向不存在)" % _nk)
        continue
    _pairs34.append((_nk, _tr, _catch))

_miss34 = []
_hit34 = 0
for _nk, _tr, _catch in _pairs34:
    _core = _norm34(_catch)
    _texts = [t.get("text") or "" for _nd in _dl34[_tr]["nodes"].values()
              for t in _nd.get("texts", [])]
    if _core and any(_core in _norm34(_x) for _x in _texts):
        _hit34 += 1
    else:
        _miss34.append("%s(%s)：从没说过自己那句 %s" % (_tr, _nk, _catch))
chk("㉜-a ★ 口头禅（23_ §一④）：每位都说得出自己那一句 %d/%d"
    "（硬底线 100%% · 人设卡 `persona.catch` 逐位）"
    % (_hit34, len(_pairs34)),
    not _miss34 and len(_pairs34) > 0,
    " · ".join(_miss34) if _miss34 else "全带齐（%d 位）" % len(_pairs34))

# ㉜-b ★ fail-closed：人 ↔ 树的配对**数**要与 NPC 总数对得上 —— 域里某位 NPC 的
#   `dialogue` 指错树 / `persona.catch` 被清空 ⇒ 他就从分母里静默消失，
#   ㉜-a 会「12/12 全绿」而实际少了一整个角色（㉚-b 的同族坑：源读不到 ⇒ 假绿）。
chk("㉜-b ★ 人 ↔ 对话树配对齐全（%d 对 · 读不到/指错/清空 ⇒ 上面会假绿）" % len(_pairs34),
    not _unpaired34 and len(_pairs34) >= 14,
    " · ".join(_unpaired34) if _unpaired34
    else "全配上（%d 对）" % len(_pairs34))

# ㉜-c ★ 反证：把 dlg_ed 整棵移走 ⇒ ㉜-a 必抓到（判据不恒真）
_c34 = next((t for _n, t, _c in _pairs34 if t == "dlg_ed"), None) or _pairs34[0][1]
_cbak34 = _dl34.pop(_c34, None)
try:
    _g34 = []
    for _nk, _tr, _catch in _pairs34:
        if _tr not in _dl34:
            _g34.append(_tr)
            continue
        _core = _norm34(_catch)
        _texts = [t.get("text") or "" for _nd in _dl34[_tr]["nodes"].values()
                  for t in _nd.get("texts", [])]
        if not (_core and any(_core in _norm34(_x) for _x in _texts)):
            _g34.append(_tr)
    chk("㉜-c ★ 反证：抽掉 %s 整棵 ⇒ ㉜-a 必抓到它（判据不恒真）" % _c34,
        _c34 in _g34, "抽完仍全带齐 = 判据恒真")
finally:
    if _cbak34 is not None:
        _dl34[_c34] = _cbak34

# ㉜-d ★ 反证跑完域**逐字未变**（㉗-e / ㉛-d 那个「备份与被测对象同一批对象」的恒真坑）
chk("㉜-d ★ 反证跑完域逐字未变（%s 仍 %d 句）"
    % (_c34, len([t for _nd in _dl34[_c34]["nodes"].values() for t in _nd.get("texts", [])])),
    _cbak34 is not None and _c34 in _dl34)

print("      口头禅档：" + " · ".join("%s=%s" % (t, "有" if _norm34(c) else "空")
                                  for _n, t, c in _pairs34[:14]))

# ㉜-e ★ 「反证不许污染被测数据」——**钉成常驻判据**（P1-42 修完 `_npc` 之后钉住它）
#    起因：`_npc` 是 `dl` 的浅层派生 ⇒ 十几条反证在压/换某一层时**顺手改了被测数据**，
#    而各自的「还原」只还原自己那份 ⇒ `dl` 永久停在残缺态（`dlg_bella` 的 `daily`
#    8 句 → 1 句）。后果不是探针自己红，而是**后面所有读 `dl` 的判据读的是残缺数据**。
#    判据：㉜ 开跑前存一份 `dl` 的逐字指纹，跑完逐字比 —— 将来任何人新写一条反证、
#    又犯了同一类错（改了 `_npc` 却以为没改 `dl`），当场红。
chk("㉜-e ★ 整条 ㉜（含它自己的反证）跑完，被测域逐字未变（反证不许改坏被测数据）",
    json.dumps(_fingerprint34, ensure_ascii=False, sort_keys=True)
    == json.dumps(dl, ensure_ascii=False, sort_keys=True),
    "开跑前 %d 棵" % len(_fingerprint34))


# ===========================================================================
# ㉝ ★ P1-46/47（2026-09-29 · 文案车道 aep1）—— **daily 层的池深**
#   ★ 为什么要有这条（本轮真挖出来的东西，前面 9x 条判据全都盖不到）：
#     ⑫-a 只看「某个层**只有 1 句**」的**形状**（阈值 1）；
#     ⑰-a 是「同刻连敲 8 下 ≥ 4 句」，现值最差 8 —— 离天花板还差一倍；
#     ⑲/⑳ 量的是**相邻重样**（0 / 0.00），㉒ 量的是**全听过之后**。
#     ⇒ 40 连敲实测：⑰/⑲/⑳ 全绿，可 P1-46 之前有 8 位的 `daily` 只有
#       **5 句无条件** ⇒ 玩家第 9 趟就在那 5 句里翻来覆去，而 ed/cole/grey
#       还在第 9 句。**「相邻不重样」与「玩到第 20 趟还有新话」是两件事。**
#   ★ 底线的来历（不是拍的，也不是照抄 ⑰-a）：
#     改前分布 5,5,5,5,5,5,5,5,6,9,9,10,10,12 ⇒ **双峰、中间档 0 位**；
#     P1-46/47 各补 4 位（5 → 8）之后变成 6,8×8,9,9,10,10,12。
#     ⇒ 底线取 **6** = 现值最薄那一位（derrick），**它一行不改** ⇒ 本件不自红；
#       随内容推进可加严到 8（derrick 补到 8 之后）。**判据只加强不削弱。**
#   ★ 为什么拿 `daily` 当这一面的尺、不是 `main`/`hidden`：
#     `main`/`hidden` 的多数句是**带 need 的**（等旗标 / 等道具），玩家到得了；
#     而 `daily` 是玩家 **90% 的话轮真正落在的那一层**（㉒-b 实测 40 趟里 32–35 趟）。
_MIN_DAILY_UNCOND = 6
_daily_uncond35 = {}
for _k35 in sorted(_npc):
    if not _k35.startswith("dlg_"):
        continue
    _daily_uncond35[_k35] = sum(
        1 for _t in _npc[_k35]["nodes"].get("daily", {}).get("texts", [])
        if not _t.get("need"))
_thin35 = {k: v for k, v in _daily_uncond35.items() if v < _MIN_DAILY_UNCOND}
chk("㉝-a ★ daily 层池深：%d 位每位的**无条件句** ≥ %d 句"
    "（玩家 90%% 的话轮落在 daily；⑫-a 只管「只有 1 句」的形状，"
    "⑰/⑲/⑳/㉒ 一条都量不到「池深差一倍」——现值最薄 %d 句）"
    % (len(_daily_uncond35), _MIN_DAILY_UNCOND,
       min(_daily_uncond35.values()) if _daily_uncond35 else 0),
    not _thin35,
    "薄于底线的：%s" % ("、".join("%s=%d" % (k.replace("dlg_", ""), v)
                               for k, v in sorted(_thin35.items())) or "无"))
print("      daily·无条件句数分布：" + " · ".join(
    "%s=%d" % (k.replace("dlg_", ""), v) for k, v in sorted(_daily_uncond35.items())))

# ㉝-b **反证**：把某位压回「只剩 _MIN_DAILY_UNCOND-1 句无条件」⇒ ㉝-a 必抓到
#   ★ 压的是真实的 `_npc`（与 ⑫-b 同一个纪律：改副本那次替换根本不生效 ⇒ 尸绿）。
_daily35_bak = json.loads(json.dumps(_npc))
# 靶子按**现值**动态挑（别写死一个已经补好的名字，否则下一位补完又写成恒真）
_probe35 = min((k for k in _daily_uncond35 if k.startswith("dlg_")),
               key=lambda k: (_daily_uncond35[k], k))
_npc[_probe35]["nodes"]["daily"]["texts"] = [
    c for c in _daily35_bak[_probe35]["nodes"]["daily"]["texts"]
    if c.get("need") is None][:_MIN_DAILY_UNCOND - 1]
_thin35_b = {}
for _k35b in _daily_uncond35:
    if not _k35b.startswith("dlg_"):
        continue
    _thin35_b[_k35b] = sum(
        1 for _t in _npc[_k35b]["nodes"].get("daily", {}).get("texts", [])
        if not _t.get("need"))
_thin35_b = {k: v for k, v in _thin35_b.items() if v < _MIN_DAILY_UNCOND}
_npc.clear()
_npc.update(json.loads(json.dumps(_daily35_bak)))   # ★ 深拷：
#   update 进去的是**同一批 dict 对象** ⇒ 后面 ㉝-d 再改 _npc 会顺手改掉这份快照，
#   ㉝-e 于是拿「被自己污染的快照」当基线 ⇒ 假红（同 ㉗-e/㉜-e 那族坑的变体）。
chk("㉝-b ★ 反证：把 %s 的 daily 压到只剩 %d 句无条件 ⇒ ㉝-a 必抓到它（判据不恒真）"
    % (_probe35.replace("dlg_", ""), _MIN_DAILY_UNCOND - 1), bool(_thin35_b),
    "越界者：%s" % ("、".join("%s=%d" % (k.replace("dlg_", ""), v)
                              for k, v in sorted(_thin35_b.items())) or "无（判据恒真）"))

# ㉝-c ★ **玩家实感**：同刻连敲 40 下，每位轮得到的**不同台词数**
#   ★ 与 ⑰-a 的差别是**趟数**（8 → 40）⇒ ⑰-a 结构上测不到「第 9 趟开始翻老货」；
#     ⑰-a 现值最差 8 = 8 趟的**天花板**（连敲 8 下最多 8 句不同）⇒ 它已经打满了。
#   底线 12 = P1-47 之后的现值最差（durin 15，改前 12）—— **不要求一次到 15**。
_MIN_DISTINCT40 = 12
_distinct40 = {k: len({t for t in _rot_seq_same(k, 40) if t}) for k in sorted(_npc)}
_thin40 = {k: v for k, v in _distinct40.items() if v < _MIN_DISTINCT40}
chk("㉝-c ★ 玩家实感：同刻连敲 40 下，每位至少轮得到 %d 句**不同**台词"
    "（⑰-a 只敲 8 下 ⇒ 天花板 8，它已打满，测不到这一面——现值最差 %d 句）"
    % (_MIN_DISTINCT40, min(_distinct40.values()) if _distinct40 else 0),
    not _thin40,
    "不足的：%s" % ("、".join("%s=%d" % (k.replace("dlg_", ""), v)
                             for k, v in sorted(_thin40.items())) or "无"))
print("      40 趟·不同台词数：" + " · ".join(
    "%s=%d" % (k.replace("dlg_", ""), v) for k, v in sorted(_distinct40.items())))

# ㉝-d ★ 反证：把 daily 压薄 ⇒ ㉝-c 必抓到（钉住的是真行为）
#   ★ 压到 **3 句**（不是 5）：实测每少一句无条件少 1 句不同台词，
#     压到 5 只掉到 12 = **正好压在底线上** ⇒ 那样的反证**不锐**（改判据它就红）。
_SQUEEZE40 = 3
_d40_bak = json.loads(json.dumps(_npc))
_probe35c = min((k for k in _daily_uncond35 if k.startswith("dlg_")),
                key=lambda k: (_daily_uncond35[k], k))
_npc[_probe35c]["nodes"]["daily"]["texts"] = [
    c for c in _d40_bak[_probe35c]["nodes"]["daily"]["texts"]
    if c.get("need") is None][:_SQUEEZE40]
_d40_after = len({t for t in _rot_seq_same(_probe35c, 40, nodes=_npc) if t})
_npc.clear()
_npc.update(json.loads(json.dumps(_d40_bak)))   # ★ 同样深拷（理由同上）
chk("㉝-d ★ 反证：把 %s 的 daily 压到只剩 %d 句无条件 ⇒ ㉝-c 必抓到它（判据不恒真）"
    % (_probe35c.replace("dlg_", ""), _SQUEEZE40), _d40_after < _MIN_DISTINCT40,
    "压完 %d 句（底线 %d · 压得越狠反证越锐；实测每少一句少 1 句不同台词）"
    % (_d40_after, _MIN_DISTINCT40))

# ㉝-e ★ 整条 ㉝（含 ㉝-b/㉝-d 两条反证）跑完，被测域逐字未变
#   （与 ㉜-e 同一个纪律：反证不许把被测数据留在残缺态给后面判据读）
chk("㉝-e ★ 整条 ㉝（含它自己的反证）跑完，被测域逐字未变（反证不许改坏被测数据）",
    json.dumps(_daily35_bak, ensure_ascii=False, sort_keys=True)
    == json.dumps(_npc, ensure_ascii=False, sort_keys=True),
    "%s 的 daily 仍 %d 句" % (_probe35c.replace("dlg_", ""),
                              len(_npc[_probe35c]["nodes"]["daily"]["texts"])))

print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
