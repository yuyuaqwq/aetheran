# -*- coding: utf-8 -*-
"""探针：pois 域 + texts 域（含★跨域交叉校验：poi 的位置与文案槽位都要真的存在）。

判据里的两条要紧事：
  · 「12 类可读物」那个数**不许手打** —— 由 `scripts/read_kinds.py` 从四处文档现解析，
    再与两处域里现算比对（②/②b）；塔内那几条就地线索是**另一档**（22 §二「可做」列，不进谱）。
  · 「读」这条指令**真跑**一遍（⑩）：谁进旧物谱、谁只是念一句正文，由行为说了算。

用法（在 aetheran-package 仓根跑）：
    GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_pois.py
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
KINDS = ("可读物", "触摸", "生息", "发现", "危险", "隐藏点")


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


print("探针：pois 域（地图元素）+ texts 域（文案）")
st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
st.install()

po = st.domain("pois")
tx = st.domain("texts")
mp = st.domain("maps")
chk("pois 域读得到", po is not None, "%d 条" % (len(po) if po else 0))
chk("texts 域读得到", tx is not None, "%d 条" % (len(tx) if tx else 0))
chk("maps 域读得到（交叉校验要用）", mp is not None, "%d 张图" % (len(mp) if mp else 0))
if not (po and tx and mp):
    sys.exit(1)

# ① kind 合法
bad = [k for k, v in po.items() if v.get("kind") not in KINDS]
chk("kind 都在六类里", not bad, " · ".join(bad))

# ② 可读物齐不齐 —— ★ 那个数**不许手打**（手打就是第二个数）：
#    `scripts/read_kinds.py` 把「12」从**四处文档**现解析出来（10 §一A 的编号项 · 19 §三A 的「已定 3 类
#    + 该扩 9 类」· 21 §一 称号那句「读完全部 N 类可读物」· 16 §二 的条件 `read_all>=N`），
#    再与**两处域里现算**（pois 里 into_codex 的条数 · 旧物谱里 from=read 的条数）逐处比对：
#    一处跟别处不一样 ⇒ 这条当场红（「两个数各说一套」不许存在）。
sys.path.insert(0, str(Path(__file__).resolve().parent))       # scripts/ 自己（read_kinds）
import read_kinds as RK                                         # noqa: E402

CX2 = st.domain("codex") or {}
_rk = RK.audit(pois=po,
               relic_read=[k for k, v in (CX2.get("relic") or {}).items() if v.get("from") == "read"],
               titles=st.domain("titles") or {})
chk("★ 「12 类」四处文档 + 两处域里现算 = 同一个数（10 §一A %(10)d · 19 §三A %(19_fixed)d+%(19_expand)d · "
    "21 §一 %(21)d · 16 §二 %(16)d · pois.into_codex %(pc)s · 旧物谱（读的）%(rr)s · titles.read_all %(ta)s）"
    % {"10": _rk["doc"]["10"], "19_fixed": _rk["doc"]["19_fixed"], "19_expand": _rk["doc"]["19_expand"],
       "21": _rk["doc"]["21"], "16": _rk["doc"]["16"],
       "pc": _rk["live"].get("pois.into_codex"), "rr": _rk["live"].get("codex.relic[from=read]"),
       "ta": _rk["live"].get("titles.read_all")}, not _rk["bad"], _rk["bad"])

reads = [k for k, v in po.items() if v.get("kind") == "可读物"]
codexed = [k for k in reads if po[k].get("into_codex")]
TW22 = RK.tower_reads(RK.rd(RK.DOC22))                          # 22 §一 那一列（塔内 9 项）
tw_in = sorted(k for k in reads if po[k].get("map") == "old_watchtower" and po[k].get("into_codex"))
chk("★ 可读物总数 = 12（量账里的，全部进谱）+ 塔内就地线索 %d 条（22 §一 那 %d 项 − 其中已进谱的 %d 条）"
    % (TW22["n"] - len(tw_in), TW22["n"], len(tw_in)),
    len(reads) == _rk["n"] + TW22["n"] - len(tw_in) and len(codexed) == _rk["n"],
    "%d 条（进谱 %d）" % (len(reads), len(codexed)))

# ②b ★ B3-10：**显式声明**（不进谱 ≠ 忘了写）—— 18 条可读物都要有 `into_codex` 那一格
#     （空串 = 「读它但不进谱」，塔内就地线索这么写）；非空时只认 `relic_codex`；
#     而**不进谱的只许出现在旧哨塔**（塔外多一条没进谱的可读物 = 当场红）。
_decl_bad = [k for k, v in po.items() if v.get("kind") == "可读物" and "into_codex" not in v]
_val_bad = [k for k, v in po.items() if v.get("kind") == "可读物"
            and str(v.get("into_codex")) not in ("", "relic_codex")]
_stray = [k for k, v in po.items() if v.get("kind") == "可读物" and not v.get("into_codex")
          and v.get("map") != "old_watchtower"]
chk("★ 每条可读物都显式声明进不进谱（%d 条 · 空的 = 就地线索）· 非空只认 `relic_codex` · 不进谱的只许在塔内"
    % len(reads), not (_decl_bad or _val_bad or _stray),
    "没声明 %s · 值不对 %s · 塔外没进谱 %s" % (_decl_bad, _val_bad, _stray))

# ③ ★ 跨域：poi 的 map 必须真在 maps 域里
bad3 = [k for k, v in po.items() if v.get("map") not in mp]
chk("★ 每个 poi 的 map 都在 maps 域里", not bad3, " · ".join(bad3))

# ④ ★ 跨域：poi 的 subarea 必须真在对应地图的节点里
bad4 = []
for k, v in po.items():
    ids = [n["id"] for n in mp.get(v.get("map"), {}).get("nodes", [])]
    if v.get("subarea") not in ids:
        bad4.append("%s → %s/%s" % (k, v.get("map"), v.get("subarea")))
chk("★ 每个 poi 的 subarea 都在对应地图的节点里", not bad4, " · ".join(bad4))

# ⑤ ★ 跨域：可读物的 read_text 必须在 texts 域里
bad5 = [k for k, v in po.items() if v.get("read_text") and v["read_text"] not in tx]
chk("★ 每个可读物的 read_text 都在 texts 域里", not bad5, " · ".join(bad5))

# ⑥ 可读物都有 hint（观察时看到的一行）
bad6 = [k for k in reads if not po[k].get("hint")]
chk("可读物都有 hint（观察时的一行）", not bad6, " · ".join(bad6))

# ⑦ texts 条目结构
bad7 = [k for k, v in tx.items()
        if not isinstance(v, dict) or "value" not in v or "category" not in v]
chk("texts 条目都有 value/category", not bad7, " · ".join(bad7))

# ⑧ 隐藏点都有产出
bad8 = [k for k, v in po.items() if v.get("kind") == "隐藏点" and not v.get("effect")]
chk("隐藏点都有 effect（产出）", not bad8, " · ".join(bad8))

# ⑨ ★ B3-7：旧物谱入口那条串得起三个域（pois ↔ codex ↔ gathering/drop_pools）
#    ① 塔内那 5 条这一批新加的可读物（正文槽位 READ_TOWER_*）**一条都不挂 into_codex** ——
#       塔内这几条是「就地线索」（22 §二 的「可做」列），12 类那个数（`10_地图探索元素库 §一A`）不动；
#    ② 2 房（门厅）那件不认得的（`unid_tower`）挂在池表（未鉴定 marker）+ 在旧物谱里（捡的）⇒
#       到手那一刻旧物谱先给一行问号（K28：known=False 起步）；
#    ③ 三处「可做」所在的三间（门厅/储藏室/号角室）各有一个「可搜物」（gathering 的 search 点）。
cx9 = st.domain("codex") or {}
ga9 = st.domain("gathering") or {}
dp9 = st.domain("drop_pools") or {}
# ★ B3-10 裁决（本批）：塔内的可读物分两档，**两档都显式** ——
#   ① 进谱的 3 条在旧物谱（读的）里（墙上的划痕 · 拾荒人留的字条 · 没寄出的信）；
#   ② 其余 6 条是**就地线索**（22 §二「可做」列）：读完不给问号、不进谱 ——
#      5 条各有自己的正文槽位（`READ_TOWER_*`），第 6 条（水里飘着的一页纸）与伐木棚那半页
#      **同一句正文**（全案只有「那半页纸」一张 · 22 §二·12 塔顶正文也写「那半页纸」）。
#   ⇒ 谁要动这一档（拆半页 / 让某条进谱），先改真源 + 这两条判据（见工作树 `_notes.md` §一）。
tw_reads = sorted(k for k in reads if po[k].get("map") == "old_watchtower")
tw_local = [k for k in tw_reads if not po[k].get("into_codex")]
tw_slots = [k for k in tw_local if str(po[k].get("read_text") or "").startswith("READ_TOWER_")]
tw_share = [k for k in tw_local if k not in tw_slots]
chk("★ 塔内可读物的清单 ↔ 22 §一「可读物」那一列**双向相等**（%d 项 · 不多不少）" % TW22["n"],
    sorted(str(po[k].get("name")) for k in tw_reads) == sorted(TW22["names"]),
    "%s" % sorted(set(TW22["names"]) ^ {str(po[k].get("name")) for k in tw_reads}))
chk("★ 塔内那 %d 条就地线索一条都不进旧物谱（= 22 §一 那 %d 项 − 已进谱的 %d 条）"
    % (len(tw_local), TW22["n"], len(tw_in)),
    len(tw_local) == TW22["n"] - len(tw_in) and len(tw_slots) + len(tw_share) == len(tw_local)
    and not [k for k in tw_local if k in (cx9.get("relic") or {}) or po[k].get("into_codex")],
    "%s" % tw_local)
chk("★ 就地线索里 5 条各有自己的正文槽位（%s）· 第 6 条与伐木棚那半页同一句（「那半页纸」只有一张）"
    % " · ".join(tw_slots),
    len(tw_slots) == 5 and len(tw_share) == 1
    and len([k for k in codexed
             if po[k].get("read_text") == po[tw_share[0]].get("read_text")]) == 1,
    "%s（共用那一句的进谱条目：%s）"
    % ([po[k].get("name") for k in tw_share],
      [(k, po[k].get("name")) for k in codexed
       if po[k].get("read_text") == po[tw_share[0]].get("read_text")]))

# ★ fix3-⑦（P2 BUG⑫ 的处置）：上面那条「两处共用同一句正文」**是有据的，不是漏抄** ——
#   真源 `22_旧哨塔_逐间设计_v1.md §二·12 可做` 那一行明写：
#     「捞那页纸（→ **就是** 14 §五 那半页：同一句正文，与伐木棚那本共用 READ_SOAKED_JOURNAL；
#       P1 不拆成半页 A/B）」
#   玩家把它当「复制粘贴」报了上来（两处一字不差）；照 `legacy-debt-triage` 的口径先核实，
#   结论 = **有意为之**（同一样东西的两个位置）⇒ **不改文案**；改成把「这条共享有真源依据」
#   钉成判据：真源哪天翻成「要拆」，这里当场红（那时才该拆槽位 + 改上面那条判据）。
_D22 = RK.rd(RK.DOC22)
_SHARE_LINE = [ln for ln in _D22.splitlines()
               if "READ_SOAKED_JOURNAL" in ln and "共用" in ln and "不拆" in ln]
chk("★ 共用正文那一档**有真源依据**（22 §二·12「同一句正文 · 与伐木棚那本共用 · P1 不拆成半页 A/B」）"
    "—— 真源翻转 ⇒ 这里当场红", bool(_SHARE_LINE),
    "%s" % ((_SHARE_LINE[0].strip()[:70] + "…") if _SHARE_LINE else "22 文档里找不到那一行"))
chk("★ 反证：域里确实还是共用（那几处的 `read_text` 逐字相同）—— 判据对象没跑空",
    len({str(po[k].get("read_text")) for k in tw_share}) == 1
    and str(po[tw_share[0]].get("read_text")) == "READ_SOAKED_JOURNAL",
    "%s" % [(k, po[k].get("read_text")) for k in tw_share])
chk("★ 门厅那件不认得的：挂在池表（未鉴定）· 在旧物谱里（捡的）· 是门厅那个可搜物的产物",
    "unid_tower" in dp9
    and (cx9.get("relic", {}).get("unid_tower") or {}).get("from") == "pick"
    and any(str(e.get("out")) == "unid_tower" for v in ga9.values()
            if v.get("subarea") == "tower_hall" for e in (v.get("pool") or [])),
    "%s" % (cx9.get("relic", {}).get("unid_tower")))
_miss9 = [nd for nd in ("tower_hall", "tower_storage", "tower_horn_room")
          if not [g for g, v in ga9.items() if v.get("map") == "old_watchtower"
                  and v.get("subarea") == nd and v.get("verb") == "search"]]
chk("★ 三处「可做」所在的三间（门厅/储藏室/号角室）各有一个可搜物", not _miss9, "%s" % _miss9)

# ══════════════════════════════════════════════════════════════
# ⑩ ★ B3-10 + ★ P-31：**真跑**「读」这条指令 —— 18 条可读物逐条：正文真拿得到；
#    进谱的那 12 条当场进旧物谱（问号起步）· 塔内那 6 条就地线索**一条都不进**（读完不留痕）。
#    判据是行为（不是结构）：看完这一条就知道「谁进谱」不是靠注释说的。
#    ★ P-31 加强：带 `condition` 的那几条先把**门槛该有的账**补上（交过的委托 / 读到过的
#      那条）再敲 —— 「门槛满足时一条都不许少」与「门槛不满足时真被挡」两件事分开钉（⑫）。
# ══════════════════════════════════════════════════════════════
print("⑩ 真跑『读』：18 条可读物逐条拿到正文 · 谁进谱（12 / 6）由行为说了算 · 带门槛的先补账")
import asyncio                                                            # noqa: E402

from content import cmds_ast as CA10                                      # noqa: E402


class _E10(object):                    # `read_thing` 只要 env.text（按名字挑）与 env.save
    def __init__(self, text):
        self.text = text
        self.saved = 0

    def save(self):
        self.saved += 1


def _run10(p, text):
    out = []

    async def _go():
        async for line in CA10.read_thing(_E10(text), None, "u_read", p):
            out.append(line)

    asyncio.run(_go())
    return out


def _sat10(p10, rec):
    """把这条 POI 门槛**该有的那本账**补上（P-31）—— 只补 `quest` / `read` 两路。

    · `quest` → 算已交（交活那一刻写的就是 `flags.quests_done`）
    · `read`  → 旧物谱里那条已在（`codex.note_read` 写的就是它）
    · `time` / `weather` **不补账**（补不了）—— ★ P-31（本批）：那两条**拨钟**去满足它
      （`_epoch_sat`），见下面那一段：门槛满足时照样一条都不许少。
    """
    cond = rec.get("condition") or {}
    if cond.get("quest"):
        p10.setdefault("flags", {})["quests_done"] = [str(cond["quest"])]
    if cond.get("read"):
        p10.setdefault("books", {}).setdefault("relic", {})[str(cond["read"])] = {"known": False}
    return p10


#: ★ P-31（2026-09-26）：这一段以前跟着**真钟**跑（K79 那一族：判据不许看真钟）—— 现在拨到
#:   固定的一天正午；带时辰/天气门槛的那几条再按门槛把钟拨到**满足**它的那一刻。
from content import calendar as _CAL0                                     # noqa: E402

_DAY0 = 200
_EPOCH0 = _DAY0 * _CAL0.scale_seconds() + (12.0 / 24.0) * _CAL0.scale_seconds()


def _epoch_sat(rec):
    """这条 POI 的时辰 / 天气门槛**满足了的那一刻**的 epoch（没有门槛 / 找不到 ⇒ None）。

    现算：扫这一天之后的每一天、每小时，取第一个 `calendar.allows` 两路都真的时刻。
    """
    cond = rec.get("condition") or {}
    if not (cond.get("time") or cond.get("weather")):
        return None
    for _d in range(_DAY0, _DAY0 + 30):
        for _h in range(24):
            _e = _d * _CAL0.scale_seconds() + (_h + 0.5) / 24.0 * _CAL0.scale_seconds()
            _CAL0.facade.bind_host(clock=lambda _e=_e: _e)
            _st = _CAL0.state()
            if _CAL0.allows(cond.get("time"), _st) and _CAL0.allows(cond.get("weather"), _st):
                return _e
    return None


read_bad, read_ok = [], {"进谱": 0, "就地线索": 0, "带门槛": 0, "拨钟满足": 0}
for pid in sorted(reads):
    body = str((tx.get(po[pid].get("read_text")) or {}).get("value") or "")
    p10 = _sat10({"day": _DAY0, "loc": po[pid].get("map"), "node": po[pid].get("subarea"),
                  "books": {"relic": {}}, "foot": {}}, po[pid])
    if po[pid].get("condition"):
        read_ok["带门槛"] += 1
    _e_sat = _epoch_sat(po[pid])
    if _e_sat is not None:
        read_ok["拨钟满足"] += 1
        _CAL0.facade.bind_host(clock=lambda _e=_e_sat: _e)
    else:
        _CAL0.facade.bind_host(clock=lambda: _EPOCH0)
    got = _run10(p10, "读 %s" % po[pid].get("name"))
    books = ((p10.get("books") or {}).get("relic") or {})
    if not body or CA10.T("SYS_READ_HEAD", name=po[pid].get("name")) not in got or body not in got:
        read_bad.append((pid, "正文没拿到", got[:2]))
        continue
    if po[pid].get("into_codex"):
        if pid not in books or books[pid].get("known") is not False:
            read_bad.append((pid, "进谱的那条没落档 / 不是从问号起步", books.get(pid)))
            continue
        read_ok["进谱"] += 1
    else:
        # ★ P-31：这条自己不许进谱（原先看「整本谱是不是空的」—— 补过门槛账的档会把它误判成进谱）
        if pid in books or any(CA10.T("SYS_CODEX_NEW", book="", name="").split("{")[0] in x for x in got):
            read_bad.append((pid, "就地线索不该进旧物谱", books))
            continue
        read_ok["就地线索"] += 1
chk("★ 18 条可读物逐条真敲『读』：正文逐字拿到（%d 条进谱 → 问号起步 · %d 条就地线索 → 不留痕 · "
    "其中 %d 条带门槛：账补上 / **拨钟到门槛满足**的 %d 条照样一条都不少）"
    % (read_ok["进谱"], read_ok["就地线索"], read_ok["带门槛"], read_ok["拨钟满足"]),
    not read_bad and read_ok["进谱"] == len(codexed)
    and read_ok["就地线索"] == len(reads) - len(codexed)
    and read_ok["带门槛"] == len([k for k in reads if po[k].get("condition")]),
    "%s" % (read_bad[:2] or read_ok))

# ══════════════════════════════════════════════════════════════
# ⑪ ★ P-28：短时增益**真落到面板上**（数据 → 唯一消费端 → food_buff → 引擎面板 mul 层）
# ------------------------------------------------------------
# 判据是「摸了以后面板上的数真的变了」，不是「代码里有这一支」：
#   ① 两张词表不许漂（`cmds_ast.POI_BUFF_STATS` ⊆ `gear.BUFF_KEY`）
#   ② 数值**从数据现读**（不手抄）：stat 在白名单里 · pct > 0 · duration > 0
#   ③ 真敲『触摸』那一站：出一行 `SYS_POI_BUFF`（逐字对槽位）+ 档上 `food_buff` 落档（until = 敲钟 + duration）
#   ④ 面板真涨：引擎 `actor_stats` 的该键 == 基础 × (1 + pct/100)，**别的键一个都不动**
#   ⑤ 过期自动失效（假钟拨过 duration）：`food_buff` 读回空、面板回基础值
#   ⑥ 反证（有牙）：把数据那份 `pct` 抹掉 / `stat` 换成不认得的 ⇒ **不出 BUFF 行**（走点名那一支）
# ══════════════════════════════════════════════════════════════
print("")
print("⑪ 真跑『触摸』：POI 的短时增益真进面板（P-28）")
from content import gear as GB11                                          # noqa: E402
from content import combat as CB11                                        # noqa: E402
from content import calendar as CAL11                                     # noqa: E402
from ext_combat.battle import stats as ST11                               # noqa: E402

FIX11 = 100 * CAL11.scale_seconds() + (12.0 / 24.0) * CAL11.scale_seconds()
CAL11.facade.bind_host(clock=lambda: FIX11)


def _panel11(p):
    b = CB11.build(p, [], {})
    return ST11.actor_stats(b, b.sides["player"][0])


class _E11(object):
    def __init__(self, text=""):
        self.text = text

    def save(self):
        pass


def _touch11(p):
    out = []

    async def _go():
        async for line in CA10.touch(_E11(), None, "u_buff", p):
            out.append(str(line))

    asyncio.run(_go())
    return out


_buff_pid = next((k for k, v in sorted(po.items())
                  if isinstance(v.get("effect"), dict) and v["effect"].get("pct")), "")
chk("★ 两张词表不漂（`POI_BUFF_STATS` ⊆ `gear.BUFF_KEY`：%s）"
    % " · ".join(sorted(CA10.POI_BUFF_STATS)),
    bool(_buff_pid) and set(CA10.POI_BUFF_STATS) <= set(GB11.BUFF_KEY), _buff_pid)

if not _buff_pid:
    chk("pois 域里有一条带数值的短时增益（找不到 ⇒ 这条测不了）", False, "")
else:
    _eff = po[_buff_pid]["effect"]
    _stat, _pct, _secs = str(_eff.get("stat")), int(_eff.get("pct") or 0), int(_eff.get("duration") or 0)
    chk("★ 数值从数据现读：%s.effect = %s（stat 在白名单里 · pct>0 · duration>0）"
        % (_buff_pid, {k: _eff[k] for k in ("buff", "stat", "pct", "duration") if k in _eff}),
        _stat in CA10.POI_BUFF_STATS and _pct > 0 and _secs > 0, _eff)
    _pb = {"cls": "cls_knight", "level": 3, "race": "human", "hp": 100, "gold": 0, "bag": {},
           "equipped": {}, "flags": {}, "books": {"relic": {}}, "codex": {}, "foot": {},
           "loc": po[_buff_pid]["map"], "node": po[_buff_pid]["subarea"]}
    _before = _panel11(_pb)
    _out11 = _touch11(_pb)
    _after = _panel11(_pb)
    _want_line = CA10.T("SYS_POI_BUFF", name=po[_buff_pid]["name"],
                        buff="%s +%d%%" % (CA10.T("SYS_STAT_%s" % _stat.upper()), _pct),
                        minutes=_secs // 60)
    _fb = _pb.get("food_buff") or {}
    chk("★ 真敲『触摸』（%s）：出「%s」· 档上 food_buff 落档（stat=%s · pct=%s · until=敲钟+%d）"
        % (po[_buff_pid]["name"], _want_line, _fb.get("stat"), _fb.get("pct"), _secs),
        _want_line in _out11 and _fb.get("stat") == _stat and int(_fb.get("pct") or 0) == _pct
        and abs(float(_fb.get("until") or 0) - (FIX11 + _secs)) < 1e-6,
        "%s / %s" % (_out11[-1:], _fb))
    _key = GB11.BUFF_KEY[_stat]
    _okp = abs(float(_after.get(_key, 0)) - float(_before.get(_key, 0)) * (1 + _pct / 100.0)) <= 1e-6
    _drift = {k: (_before.get(k), _after.get(k)) for k in sorted(set(_before) & set(_after))
              if abs(float(_after.get(k, 0)) - float(_before.get(k, 0))) > 1e-9
              and k != _key}
    chk("★ 面板真涨（引擎 `actor_stats`）：%s %.2f → %.2f（×%.2f 才是对的）· 别的键一个都没动 %s"
        % (_key, _before.get(_key, 0), _after.get(_key, 0), 1 + _pct / 100.0, sorted(_drift) or "✓"),
        _okp and not _drift, "该 %s，实 %s" % (float(_before.get(_key, 0)) * (1 + _pct / 100.0),
                                              _after.get(_key, 0)))
    CAL11.facade.bind_host(clock=lambda: FIX11 + _secs + 1)              # ⑤ 过期（假钟）
    _exp = _panel11(_pb)
    chk("★ 过了 %d 秒自动失效：`food_buff` 读回空（%s）· 面板回基础值（%s → %s）"
        % (_secs, GB11.food_buff(_pb) or "空", _after.get(_key), _exp.get(_key)),
        not GB11.food_buff(_pb) and abs(float(_exp.get(_key, 0)) - float(_before.get(_key, 0))) <= 1e-6,
        "%s / %s" % (GB11.food_buff(_pb), _exp.get(_key)))
    CAL11.facade.bind_host(clock=lambda: FIX11)
    # ⑥ 反证：数据没写数值 / 写了认不出的 —— 不许假装生效（走兜底回血或点名行）
    _bad_pid, _bad_out = [], []
    for _tag, _over in (("没了 pct", {"buff": "b_x", "stat": _stat, "duration": _secs}),
                        ("stat 认不出", {"buff": "b_x", "stat": "luck", "pct": _pct, "duration": _secs})):
        _r = dict(po[_buff_pid])
        _r["effect"] = _over
        _q = {"cls": "cls_knight", "level": 3, "race": "human", "hp": 50, "gold": 0, "bag": {},
              "equipped": {}, "flags": {}, "books": {"relic": {}}, "codex": {}, "foot": {},
              "loc": po[_buff_pid]["map"], "node": po[_buff_pid]["subarea"]}
        _o = []

        async def _go2(_r=_r, _q=_q):
            async for _l in CA10.poi_effect_lines(_E11(), None, "u_bad", _q, _buff_pid, _r, "touch"):
                _o.append(str(_l))

        asyncio.run(_go2())
        if any("+%d%%" % _pct in x for x in _o) or (_q.get("food_buff") or {}):
            _bad_pid.append(_tag)
        _bad_out.append((_tag, _o[-1:]))
    chk("★ 反证（不写数值 / 认不出的 stat 都不许假装生效）：两种坏数据都不出增益行、也不落 food_buff",
        not _bad_pid, "%s" % _bad_out)

# ══════════════════════════════════════════════════════════════
# ⑫ ★ P-31：四条 `condition` 真生效 —— **挡得下 · 放得开 · 判不了就点名**
# ------------------------------------------------------------
# ① 三处对账：域里用到的键 ⊆ 代码 `POI_COND_KEYS` == `schemas/pois.schema.json` 的 condition 键
#    （schema 现解析，不手抄）
# ② 每一条带门槛的：状态 ∈ {ok, no, unknown}，且 `no` 必须配 `SYS_POI_NOT_YET`、`unknown` 必须配
#    `SYS_POI_COND_TODO`（**一条都不许静默**）
# ③ 真挡 + 真放行（两面都跑，不写死名字）：
#      · `quest` 门槛：没过 ⇒ 观察不列它、『读』只回点名行（正文一个字都不给）；补上那笔账 ⇒ 列表有它、正文出来
#      · `read` 门槛：同理（账 = 旧物谱里那条）
#      · `time` 门槛（合法的 token）：假钟两档 —— 不满足 `no` / 满足 `ok`
# ④ 判不了的那两条（今天写的是「退潮」）：点名行出得来，且**照旧可用**（藏起来 = 静默删内容）
# ══════════════════════════════════════════════════════════════
print("")
print("⑫ 真跑门槛：四条 condition 的 POI —— 挡 / 放行 / 判不了就点名（P-31）")
import io as _io12                                                       # noqa: E402
import json as _json12                                                   # noqa: E402

_sch12 = _json12.load(_io12.open(os.path.join(REPO, "schemas", "pois.schema.json"), encoding="utf-8"))
_sch_keys = set((_sch12.get("patternProperties") or {}).get("^poi_[a-z_]+$", {})
                .get("properties", {}).get("condition", {}).get("propertyNames", {}).get("enum") or [])
_used_keys = set()
for _k, _v in po.items():
    _used_keys |= set((_v.get("condition") or {}).keys())
chk("★ 三处对账（条件键词表只有一份）：代码 %s == schema %s ⊇ 域里用到的 %s"
    % (" · ".join(CA10.POI_COND_KEYS), " · ".join(sorted(_sch_keys)), " · ".join(sorted(_used_keys))),
    set(_used_keys) <= set(CA10.POI_COND_KEYS) == _sch_keys, sorted(_used_keys))


class _E12(object):
    def __init__(self, text=""):
        self.text = text

    def save(self):
        pass


def _run12(fn, p, text=""):
    out = []

    async def _go():
        async for line in fn(_E12(text), None, "u_cond", p):
            out.append(str(line))

    asyncio.run(_go())
    return out


def _player12(**kw):
    q = {"cls": "cls_knight", "level": 3, "race": "human", "hp": 100, "gold": 0, "bag": {},
         "equipped": {}, "flags": {}, "books": {"relic": {}}, "codex": {}, "foot": {}}
    q.update(kw)
    return q


_cond_pids = sorted(k for k, v in po.items() if v.get("condition"))
_bad12, _tally12 = [], {}
for _pid in _cond_pids:
    _rec12 = po[_pid]
    _st12, _ln12 = CA10._poi_cond(_rec12, _player12(), None)
    _tally12[_st12] = _tally12.get(_st12, 0) + 1
    if _st12 == "ok":
        if _ln12:
            _bad12.append((_pid, "ok 不该有话说", _ln12))
        continue
    # 点名行必须是**那个槽位**渲染出来的（不手抄整句：拿槽位模板的前半截当判据）
    _slot12 = "SYS_POI_NOT_YET" if _st12 == "no" else "SYS_POI_COND_TODO"
    # ★ 本波（P1 体验-10）：点名行现在**带主语** —— 与「看得见」那一栏同一形（『名字』图标）。
    #   期望值按**域里的名字与图标**现算（不抄代码里那一行怎么写）。
    _head12 = str((tx.get(_slot12) or {}).get("value") or "").replace(
        "{name}", "『%s』%s" % (_rec12["name"], _rec12.get("icon") or ""))
    _head12 = _head12.split("{")[0]
    if not _ln12 or not _ln12.startswith(_head12):
        _bad12.append((_pid, "点名行不是 %s 渲染的" % _slot12, _ln12[:40]))
    elif str(_rec12.get("icon") or "") and str(_rec12["icon"]) not in _ln12:
        _bad12.append((_pid, "点名行没带上那件东西的图标（主语不明）", _ln12[:40]))
chk("★ 域里带门槛的 %d 条：每一条都判出了状态（%s），且**不满足 / 判不了都要点名**（一条都不许静默）"
    % (len(_cond_pids), " · ".join("%s=%d" % kv for kv in sorted(_tally12.items()))),
    not _bad12, "%s" % _bad12[:2])

# ③-a `quest` 门槛：没过 / 已交 两面
_q_pid = next((k for k, v in sorted(po.items()) if (v.get("condition") or {}).get("quest")), "")
if not _q_pid:
    chk("pois 域里有一条 `quest` 门槛（找不到 ⇒ 这条测不了）", False, "")
else:
    _qid = str(po[_q_pid]["condition"]["quest"])
    _qname = str((st.domain("quests").get(_qid) or {}).get("name") or _qid)
    _loc12, _node12 = po[_q_pid]["map"], po[_q_pid]["subarea"]
    _p_no = _player12(loc=_loc12, node=_node12)
    _p_yes = _player12(loc=_loc12, node=_node12, flags={"quests_done": [_qid]})
    _no_txt = CA10.T("SYS_POI_NOT_YET", name=CA10._poi_label(po[_q_pid]),
                     why=CA10.T("SYS_POI_WHY_QUEST", token=_qname))
    _no_look = _run12(CA10.look, _p_no)
    _no_read = _run12(CA10.read_thing, _p_no, "读 %s" % po[_q_pid]["name"])
    _yes_look = _run12(CA10.look, _p_yes)
    _yes_read = _run12(CA10.read_thing, _p_yes, "读 %s" % po[_q_pid]["name"])
    _body12 = str((tx.get(po[_q_pid].get("read_text")) or {}).get("value") or "")
    _sees12 = str((tx.get("SYS_LOOK_SEES") or {}).get("value") or "").split("{")[0]
    chk("★ `quest` 门槛（%s ← %s）真挡：观察不列「%s」· 只回「%s」· **正文一个字都不给**"
        % (_qid, _qname, po[_q_pid]["name"], _no_txt),
        _no_txt in _no_look and _no_txt in _no_read and _body12 not in _no_read
        and not any(x.startswith(_sees12) and po[_q_pid]["name"] in x for x in _no_look),
        "%s / %s" % (_no_look[:1], _no_read))
    chk("★ 交过那一条之后（`flags.quests_done` 那本账）**立刻放行**：观察列得出它 · 正文真出来",
        any(po[_q_pid]["name"] in x for x in _yes_look) and _body12 in _yes_read
        and _no_txt not in _yes_read, "%s / %s" % (_yes_look[3:4], _yes_read[:2]))

# ③-b `read` 门槛：没读到过 / 读到过 两面
_r_pid = next((k for k, v in sorted(po.items()) if (v.get("condition") or {}).get("read")), "")
if not _r_pid:
    chk("pois 域里有一条 `read` 门槛（找不到 ⇒ 这条测不了）", False, "")
else:
    _need = str(po[_r_pid]["condition"]["read"])
    _need_name = str((po.get(_need) or {}).get("name") or _need)
    _p_no2 = _player12(loc=po[_r_pid]["map"], node=po[_r_pid]["subarea"])
    _p_yes2 = _player12(loc=po[_r_pid]["map"], node=po[_r_pid]["subarea"],
                        books={"relic": {_need: {"known": False}}})
    _no2 = CA10.T("SYS_POI_NOT_YET", name=CA10._poi_label(po[_r_pid]),
                  why=CA10.T("SYS_POI_WHY_READ", token=_need_name))
    _l_no2 = _run12(CA10.look, _p_no2)
    _l_yes2 = _run12(CA10.look, _p_yes2)
    _sees2 = str((tx.get("SYS_LOOK_SEES") or {}).get("value") or "").split("{")[0]
    chk("★ `read` 门槛（先读到过『%s』）真挡：没读到 ⇒ 观察里列不出「%s」+ 点名「%s」"
        % (_need_name, po[_r_pid]["name"], _no2),
        _no2 in _l_no2
        and not any(x.startswith(_sees2) and po[_r_pid]["name"] in x for x in _l_no2),
        "%s" % _l_no2[3:5])
    chk("★ 读到过那一条之后（旧物谱那本账）**立刻放行**：观察里列得出它",
        any(po[_r_pid]["name"] in x for x in _l_yes2)
        and not any(_no2 in x for x in _l_yes2), "%s" % _l_yes2[3:5])

# ③-c `time` 门槛（合法 token · 假钟两档）：★ P-31（2026-09-26）**用域里那条真的**（「退潮」）
#   —— 别名表把它接到真时辰上之后，它就是一条**真门槛**：不满足挡得下、满足放得开。
_t_pid = next((k for k, v in sorted(po.items()) if (v.get("condition") or {}).get("time")), "")
_t_tok = str((po[_t_pid].get("condition") or {}).get("time", [""])[0]) if _t_pid else ""
_kind_t, _eid_t = CAL11.resolve(_t_tok)
_alias_t = CAL11.token_alias()
# ★ 三处对账（别名表只有一份）：`rules/calendar.json` ↔ calendar 域 + `resolve` 认得它
_rules_cal = _json12.load(_io12.open(os.path.join(REPO, "content", "rules", "calendar.json"),
                                    encoding="utf-8"))
chk("★ P-31 别名表三处对账：`content/rules/calendar.json` 的 token_alias %s == calendar 域的 `_token_alias` %s"
    "，且 `resolve(%s)` 真认得它 → %s（域里那条 POI 写的**真源原词**因此成了真门槛）"
    % (_rules_cal.get("token_alias"), _alias_t, _t_tok, (_kind_t, _eid_t)),
    bool(_alias_t) and _rules_cal.get("token_alias") == _alias_t and _kind_t is not None,
    "域里用到的 time token = %s" % _t_tok)
# ★ 别名**不覆盖**真名字（撞名 = 悄悄改掉真门槛的含义）：每个真名字 resolve 出来的还是它自己
_real_toks = [(CAL11.name(h), h) for h in CAL11.hours()] + [(CAL11.name(w), w) for w in CAL11.weathers()]
_shadow = [(nm, CAL11.resolve(nm)) for nm, eid in _real_toks if CAL11.resolve(nm)[1] != eid]
chk("★ P-31 别名**不覆盖真名字**：四时辰 + 四天气逐个 `resolve` 出来的还是它自己（%s ｜ 别名那一格：%s→%s）"
    % (" · ".join("%s→%s" % t for t in _real_toks), _t_tok, _eid_t),
    not _shadow, "%s" % _shadow)
_cases12 = []
for _hod in (12.0, 22.0):
    _e12 = _DAY0 * CAL11.scale_seconds() + (_hod / 24.0) * CAL11.scale_seconds()
    CAL11.facade.bind_host(clock=lambda _e12=_e12: _e12)
    _cases12.append((_hod, CAL11.state()["hour"], CA10._poi_cond(po[_t_pid], _player12(), None)))
CAL11.facade.bind_host(clock=lambda: FIX11)
#: 点名那一句里的 token **用域里那个词**（`_poi_cond` 就是这么渲染的：写「退潮」不写「夜」）
#: ★ fix5-nav：域里那个词是**散文**（「退潮」）时，门槛那一句要把**刻度**一并点明
#:   （P2 体验：「退潮后的石缝」只报条件不给刻度 ⇒ 玩家在浅滩把六个动词挨个试）——
#:   走的槽位因此是 `SYS_POI_WHY_TIME_ALIAS`（token 照旧 + 补一句「就是「夜」」）。
_alias_line = CA10.T("SYS_POI_WHY_TIME_ALIAS", token=_t_tok, real=CAL11.name(_eid_t))
chk("★ P-31 「%s → %s」是**真门槛**（域里那条 POI · 假钟两档）：昼 = %s ⟶ %s ｜ 夜 = %s ⟶ %s"
    % (_t_tok, CAL11.name(_eid_t), _cases12[0][1], _cases12[0][2][0],
       _cases12[1][1], _cases12[1][2][0]),
    _cases12[0][2][0] == "no" and _cases12[1][2][0] == "ok"
    and CA10.T("SYS_POI_WHY_TIME", token=_t_tok) in _cases12[0][2][1]
    and _alias_line in _cases12[0][2][1],
    "%s" % _cases12)
chk("★ fix5-nav（P2 体验）：门槛那一句把**刻度**点明了 —— 散文词「%s」的那一档走 "
    "`SYS_POI_WHY_TIME_ALIAS`、逐字 = 「%s」（昼那一档）" % (_t_tok, _alias_line),
    _alias_line in (_cases12[0][2][1] or "") and CAL11.token_alias().get(_t_tok) == CAL11.name(_eid_t),
    "%s" % (_cases12[0][2][1],))

# ④ ★ P-31（2026-09-26）**换锚**：原先这一条要求「判不了的那两条」在场（= 把「真源写着、刻度没有」
#   这个**欠账状态**钉成了判据）。现在那两条判得了（别名表），判据换成更强的一条：
#     · 域里带门槛的 POI **一条都不许判不了**（`unknown` 必须是 0 —— 欠账清零）；
#     · 「判不了就点名」那条**路**仍然在：拿一条**合成记录**（脏 token）证它还活着。
_unk = [_pid for _pid in _cond_pids if CA10._poi_cond(po[_pid], _player12(), None)[0] == "unknown"]
chk("★ P-31 换锚④：域里带门槛的 %d 条 POI **一条都不许判不了**（`unknown` = %s —— 真源写着的词都得有刻度）"
    % (len(_cond_pids), _unk or "0 条"),
    not _unk, "%s" % [po[k]["name"] for k in _unk])
# ★ 本波加强：这一支原先拿「域里第一条带门槛的」当底座，而那条**没有正文** ⇒ 「正文照样拿得到」
#   半句被 `not read_text` 短路掉了（等于没测）。现在换成**有正文的那条**（带时辰门槛的那件），
#   并把域里那条记录**临时**换成脏 token 真跑 `读`：正文必须照样拿得到；换回去 ⇒ 回到被门槛挡住。
#   （注入面 = 代码真正在用的那一份 `_CACHE`，跑完原样还原 —— 不动盘上的数据。）
_LIVE = CA10._data("pois")
_REC_U = _LIVE[str(_t_pid)]
_SAVED_U = _json12.loads(_json12.dumps(_REC_U, ensure_ascii=False))
_st_u, _ln_u, _o_u, _o_u2 = "", "", [], []
try:
    _REC_U["condition"] = {"time": ["涨潮"]}               # 词表外的 token（真源没有这一档）
    _st_u, _ln_u = CA10._poi_cond(_REC_U, _player12(), None)
    _p_u = _player12(loc=_REC_U["map"], node=_REC_U["subarea"])
    _o_u = _run12(CA10.read_thing, _p_u, "读 %s" % _REC_U["name"])
finally:
    _REC_U.clear()
    _REC_U.update(_SAVED_U)
_body_u = str((tx.get(_REC_U.get("read_text")) or {}).get("value") or "")
_p_u2 = _player12(loc=_REC_U["map"], node=_REC_U["subarea"])
_o_u2 = _run12(CA10.read_thing, _p_u2, "读 %s" % _REC_U["name"])
chk("★ P-31 「判不了就点名 + 照旧可用」那条**路**仍在（把域里 `%s` 临时换成脏 token「涨潮」）："
    "状态 = %s · 点名行 = 「%s」· 正文照样拿得到（不许静默删内容）"
    % (str(_REC_U.get("name")), _st_u, str(_ln_u)[:42]),
    _st_u == "unknown"
    and _ln_u.startswith(CA10.T("SYS_POI_COND_TODO", name=CA10._poi_label(_REC_U)).split("{")[0])
    and bool(_body_u) and _body_u in _o_u,
    "%s" % (_o_u[:2] if _o_u else "（不可读物 · 只看点名行）"))
chk("★ 同一件的**另一态**（脏 token 还原回真源那个词）：门槛判得出来 ⇒ 昼被挡、正文一个字不给 "
    "（`%s`）" % _t_tok,
    _body_u not in _o_u2 and CA10.T("SYS_POI_WHY_TIME", token=_t_tok) in "\n".join(_o_u2),
    "%s" % _o_u2[:2])

print()
print("⑬ 隐藏点的产出引用 —— `effect.loot` 不许悬空（B3-28 ②）")
#   背景（台账 P-28 乙 的原话）：三个隐藏点原先各挂一条 `effect.loot` 指
#   `dp_hidden_camp` / `dp_hidden_birch` / `dp_hidden_shoal`，而这三张池在 `drop_pools` 域里
#   **根本不存在**（全仓引用只有 pois 这一处 = 悬空引用）；而本节原先只核「隐藏点都有 effect」
#   ⇒ 放它过。台账当时写的正是：「定下来再补『effect.loot 必须在 drop_pools 里』这一条」。
#   ★ B3-28 ② 的处置 = **摘掉那三条引用**（二选一里的哪一个 + 理由见工作树 `_notes.md`：
#     真源今天给不出这三张池的条目 / 权重，照 `dp_*` 形状补池就得**编数**；而产出线到底归
#     `pois.effect.loot` 还是归 `gathering`（搜查 / 攀爬那条线）本身还没拍板）。
_dp13 = st.domain("drop_pools") or {}
_loot_refs13 = [(k, str((v.get("effect") or {}).get("loot")))
                for k, v in sorted(po.items())
                if isinstance(v.get("effect"), dict) and (v.get("effect") or {}).get("loot")]
_dangling13 = [(k, L) for k, L in _loot_refs13 if L not in _dp13]
chk("★ 掉落的池引用**不悬空**：`pois.effect.loot` 凡写了，池必须在 drop_pools 域里查得到"
    "（引用 %d 处 · 悬空 %d 处）" % (len(_loot_refs13), len(_dangling13)),
    not _dangling13, "%s" % _dangling13)
_hid13 = {k: v for k, v in po.items() if v.get("kind") == "隐藏点"}
chk("★ 三个隐藏点都**显式写了 `effect.need`**（产出口归哪条线不许靠默认「谁都能碰」）· 今天三条同线：%s"
    % " · ".join("%s→%s" % (po[k].get("name"), (po[k].get("effect") or {}).get("need"))
                 for k in sorted(_hid13)),
    _hid13 and all(str((v.get("effect") or {}).get("need") or "") for v in _hid13.values())
    and len({str((v.get("effect") or {}).get("need")) for v in _hid13.values()}) == 1,
    "%s" % {k: (v.get("effect") or {}) for k, v in _hid13.items()})
#   ▲ 这一条记的是**本批的处置**：三条悬空引用今天**一条都不挂**（= 摘干净了）。
#     哪天攀爬 / 搜查接线 + 真源给出这三张池的条目与权重，就**连同工作树 `_notes.md` 一起**把
#     本节改成「引用数 = 真源点名的那几个池，且逐个在 drop_pools 里」（判据只加强，不削弱）。
chk("★ 隐藏点今天**一条 `effect.loot` 都不挂**（B3-28 ② · 摘干净的登记值 = 0）",
    not _loot_refs13, "%s" % _loot_refs13)

# ══════════════════════════════════════════════════════════════
# ★ g4-⑩：可读物的正文**按真实经历分支**（`pois.<pid>.text_variant`）
#   原状（P2 报告 BUG⑦）：号角室那块碑那句「有三个，你在白桦林那棵树皮上见过 —— 重了。」
#   对**没去过白桦林**的玩家也照说（抢跑一个当时还不成立的发现）。
#   判据三态：① schema 声明了那一格（键只有 `read`）· 每条的条件 id 真在 pois 域里；
#             ② 真跑两态：没读到 ⇒ 基础正文 / 读到过 ⇒ 变体正文（两个都不等于对方）；
#             ③ 反证（有牙）：没读到过时**旧那一句**一个字都不上屏。
# ══════════════════════════════════════════════════════════════
print("")
print("★ g4-⑩：可读物正文按真实经历分支（号角室碑名单那句）")
_sch10b = _json12.load(_io12.open(os.path.join(REPO, "schemas", "pois.schema.json"), encoding="utf-8"))
_tv_prop = (((_sch10b.get("patternProperties") or {}).get("^poi_[a-z_]+$") or {})
            .get("properties") or {}).get("text_variant")
_tv_pids = sorted(k for k, v in po.items() if (v.get("text_variant") or {}).get("read"))
_tv_bad = [k for k in _tv_pids if str(po[k]["text_variant"]["read"]) not in po]
chk("★ `text_variant` 那一格：schema 里声明了（键只有 `read`）· 域里 %d 条（%s）· "
    "条件指向的 poi 真在域里"
    % (len(_tv_pids), " · ".join(po[k]["name"] for k in _tv_pids)),
    bool(_tv_prop) and _tv_pids and not _tv_bad
    and list(((_tv_prop.get("propertyNames") or {}).get("enum")) or []) == ["read"],
    "schema=%s · 域里=%s · 悬空=%s" % (bool(_tv_prop), _tv_pids, _tv_bad))
if not _tv_pids:
    chk("pois 域里有一条 `text_variant`（找不到 ⇒ 这条测不了）", False, "")
else:
    _tp = _tv_pids[0]
    _tneed = str(po[_tp]["text_variant"]["read"])
    _tbase = str(po[_tp].get("read_text") or "")
    from content.scene import variant_key as _vk10                      # noqa: E402
    _tvk = _vk10(_tbase, _tneed)
    _p_before = _player12(loc=po[_tp]["map"], node=po[_tp]["subarea"], books={"relic": {}})
    _p_after = _player12(loc=po[_tp]["map"], node=po[_tp]["subarea"],
                         books={"relic": {_tneed: {"known": True}}})
    _body_b = str((tx.get(_tbase) or {}).get("value") or "")
    _body_a = str((tx.get(_tvk) or {}).get("value") or "")
    _r_before = _run12(CA10.read_thing, _p_before, "读 %s" % po[_tp]["name"])
    _r_after = _run12(CA10.read_thing, _p_after, "读 %s" % po[_tp]["name"])
    chk("★ 真跑两态（%s ← 先读到过『%s』）：没读到 ⇒ 基础正文（%s…）· 读到过 ⇒ 变体正文（%s…）"
        % (po[_tp]["name"], _tneed, _body_b[:14], _body_a[:14]),
        bool(_body_a) and _body_a != _body_b and _tbase != _tvk
        and _body_b in _r_before and _body_a not in _r_before
        and _body_a in _r_after and _body_b not in _r_after,
        "before=%s / after=%s" % (_r_before[1:2], _r_after[1:2]))
    # ③ 反证：真源口径表里旧那一句（不分支的那一句）在「没读到过」那一态一个字都不上屏
    _old10 = str((tx.get(_tvk) or {}).get("value") or "")
    chk("★ 反证（有牙）：没读到过白桦树时**旧那一句不出现** —— 旧句 = 变体那句（%s），"
        "它只在读到过那一态上屏" % _old10[:20], bool(_old10) and _old10 not in _r_before)

# ══════════════════════════════════════════════════════════════
# ★ g4-⑧：三处隐藏点**都摸得着也搜得到**（每条带一个隐藏点 ⇒ 那一站要有 `verb=search` 的采集点）
#   原状（P-28 脚注 + 本批核实）：`be_dogs` 那一站**没有**可搜点** ⇒「白桦林深处的记号」
#   摸得着、读得到，敲『搜查』却回「这儿没什么可搜的」（bn_camp / bw_shoal 两处有）。
#   口径 = 真源 `06 §一 1.1`（稀有 1.16 ← **隐藏点** · 头目掉 · 野外之王）+ `10 §一C`（隐藏点）+
#          `05 §三`（稀有按池权重 20%–60% · n 1–2 · 每天 3 次）。
# ══════════════════════════════════════════════════════════════
print("")
print("★ g4-⑧：三处隐藏点所在的那一站都有可搜刮面（与真源资源表对得上）")
_ga10 = st.domain("gathering") or {}
_it10 = st.domain("items") or {}


def _search_at(node):
    return [g for g, v in _ga10.items() if v.get("subarea") == node and v.get("verb") == "search"]


_hid10 = sorted(k for k, v in po.items() if v.get("kind") == "隐藏点")
_miss10, _thin10, _rare10 = [], [], {}
for _k10 in _hid10:
    _node10 = str(po[_k10].get("subarea"))
    _pts10 = _search_at(_node10)
    if not _pts10:
        _miss10.append((_k10, _node10))
        continue
    for _g10 in _pts10:
        _pool10 = _g10 and (_ga10[_g10].get("pool") or [])
        if not _pool10:
            _thin10.append(_g10)
        _rare10[_g10] = [str(e.get("out")) for e in _pool10
                         if str(e.get("out")) == "unid_rare"
                         or str((_it10.get(str(e.get("out"))) or {}).get("quality")) in ("稀有", "遗物")
                         or str(e.get("out")).startswith("i_set_")]
chk("★ 三处隐藏点（%s）所在的那一站各有一个 `verb=search` 的采集点 ——「摸得着」与「拿得走」是两回事"
    % " · ".join(po[k]["name"] for k in _hid10), bool(_hid10) and not _miss10, "%s" % (_miss10,))
chk("★ 那几个可搜点的池非空 · 且都够得着**稀有那一档**（真源 `06 §一 1.1`：稀有 ← 头目掉 · "
    "**隐藏点** · 野外之王）—— %s" % " · ".join("%s:%s" % (g, "/".join(v) or "无")
                                                for g, v in sorted(_rare10.items())),
    not _thin10 and all(_rare10.values()) and bool(_rare10), "空池 %s · 各点稀有档 %s"
    % (_thin10, _rare10))
# 与 05 §三 的三条数对得上（稀有 20%–60% · n 上限 ≤ 3 · 每天 3 次）
_off10 = []
for _g10, _rares10 in sorted(_rare10.items()):
    _rec10 = _ga10[_g10]
    if int(_rec10.get("times_per_day") or 0) != 3:
        _off10.append((_g10, "times_per_day", _rec10.get("times_per_day")))
    for _e10 in _rec10.get("pool") or []:
        _w10 = int(_e10.get("w") or 0)
        _tot10 = sum(int(x.get("w") or 1) for x in _rec10["pool"])
        _pct10 = 100.0 * _w10 / _tot10
        if _pct10 > 60.5 and _e10.get("out") not in ("i_junk_bone",):
            _off10.append((_g10, "权重超 60%", round(_pct10, 1)))
        if max([int(n) for n in (_e10.get("n") or [1])] or [1]) > 3:
            _off10.append((_g10, "n 上限 >3", _e10.get("n")))
chk("★ 与 `05 §三` 对得上：每点每天 3 次 · 池权重落在 0–60% 带内 · `n` 上限 ≤ 3",
    not _off10, "%s" % (_off10[:3],))
# 反证（有牙）：把 `be_dogs` 那个点临时摘掉 ⇒ 上面那一格当场翻面
_be10 = [g for g in _search_at("be_dogs")]
_rev10 = {g: _ga10.pop(g) for g in _be10}
try:
    _after10 = [k for k in _hid10 if not _search_at(str(po[k].get("subarea")))]
finally:
    _ga10.update(_rev10)
chk("★ 反证（撤改验证）：把野狗窝那个可搜点临时摘掉 ⇒ 那一格当场点名出 %s（判据真的守着它）"
    % " · ".join(po[k]["name"] for k in _after10),
    bool(_be10) and len(_after10) == 1, "摘掉的是 %s" % _be10)

print()
print("按类别计数：")
for kd in KINDS:
    n = [k for k, v in po.items() if v.get("kind") == kd]
    if n:
        print("  %-6s %d 条  %s" % (kd, len(n), " · ".join(po[k]["name"] for k in n[:6])))
print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
