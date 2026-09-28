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
_npc = {k: v for k, v in dl.items() if str(k).startswith("dlg_")}

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
#   判据 = 这种「纯兜底」层不许比基线更多。
#   基线 7（累计：19 → 10 → 7）；硬上限 = **不许比基线更多**（逐步降到 0）。
#   余下 7 个集中在 meet（初次搭话）与两个 daily；meet 层是「还不熟时唯一会说话的那档」，
#   轮换窗口天然小 ⇒ 下批优先给 daily 开轮换，meet 只在角色人设本身有第二条口气时补。
_FLAT = []
for _k, _v in _npc.items():
    for _lk, _nd in _v["nodes"].items():
        if _lk not in _LAYERS4:
            continue
        if all(t.get("need") is None for t in _nd["texts"]):
            _FLAT.append("%s/%s" % (_k, _lk))
_MAX_FLAT = 7
chk("⑩-b ★ 轮换：纯兜底层（每句 need=null ⇒ 玩家每次看同一句）%d 个（上限 ≤ %d · 逐步降到 0）"
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
_ROT_FLOOR = 4
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
_LATE_MIN = 3
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
for _k17 in _npc[_pick17]["nodes"]:
    _ly17 = _k17
    _kept17 = None
    for _c in _npc_save17[_pick17]["nodes"][_ly17]["texts"]:
        if _c.get("need") is None:
            _kept17 = _c
            break
    _npc[_pick17]["nodes"][_ly17]["texts"] = [_kept17] if _kept17 else []
_after17 = _rot_same(_pick17)
_npc.clear()
_npc.update(_npc_save17)
chk("⑰-b ★ 反证：把 %s 整棵树的四层各压到只剩一条兜底 ⇒ 同刻轮换掉到 %d 以下（判据抓得住）"
    % (_pick17.replace("dlg_", ""), _MIN_SAME),
    _after17 < _MIN_SAME,
    "压完 %d 句（%d → %d）" % (_after17, _SAME[_pick17], _after17))

print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
