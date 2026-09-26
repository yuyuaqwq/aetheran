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
#: ★ 本波（P1 BUG-7）加的两个：`hurt`（有伤 —— 生命没满）· `equipped`（那一格上有东西）。
#:   两个字都在 `content/cmds_talk._pick_indexed` 里各有一支（下面 ③ 的静态守卫钉着）。
NEED_KINDS = {"flag", "quest_done", "quest_active", "time", "event", "holding",
              "weather", "codex", "flag_not", "hurt", "equipped"}
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
bad3 = []
for k, v in dl.items():
    for nk, nd in v["nodes"].items():
        for t in nd["texts"]:
            nd_ = t.get("need")
            if nd_ and (set(nd_) - NEED_KINDS):
                bad3.append("%s/%s=%s" % (k, nk, sorted(set(nd_) - NEED_KINDS)))
chk("★ need 条件的**每个**键都在词表里（%s）" % " · ".join(sorted(NEED_KINDS)),
    not bad3, " · ".join(bad3))
_ct_src = (REPO / "content" / "cmds_talk.py").read_text(encoding="utf-8")
_used_kinds = {kk for v in dl.values() for nd in v["nodes"].values()
               for t in nd["texts"] for kk in (t.get("need") or {})}
_nobranch = sorted(kk for kk in _used_kinds if ('k == "%s"' % kk) not in _ct_src)
chk("★ 域里用到的 need 键在 `_pick_indexed` 里各有一支（没分支 = 写了等于没写：静默满足）",
    not _nobranch, "没分支：%s" % _nobranch)

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

print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
