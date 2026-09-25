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
# ⑩ ★ B3-10：**真跑**「读」这条指令 —— 18 条可读物逐条：正文真拿得到；
#    进谱的那 12 条当场进旧物谱（问号起步）· 塔内那 6 条就地线索**一条都不进**（读完不留痕）。
#    判据是行为（不是结构）：看完这一条就知道「谁进谱」不是靠注释说的。
# ══════════════════════════════════════════════════════════════
print("⑩ 真跑『读』：18 条可读物逐条拿到正文 · 谁进谱（12 / 6）由行为说了算")
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


read_bad, read_ok = [], {"进谱": 0, "就地线索": 0}
for pid in sorted(reads):
    body = str((tx.get(po[pid].get("read_text")) or {}).get("value") or "")
    p10 = {"day": 1, "loc": po[pid].get("map"), "node": po[pid].get("subarea"),
           "books": {"relic": {}}, "foot": {}}
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
        if books or any(CA10.T("SYS_CODEX_NEW", book="", name="").split("{")[0] in x for x in got):
            read_bad.append((pid, "就地线索不该进旧物谱", books))
            continue
        read_ok["就地线索"] += 1
chk("★ 18 条可读物逐条真敲『读』：正文逐字拿到（%d 条进谱 → 问号起步 · %d 条就地线索 → 不留痕）"
    % (read_ok["进谱"], read_ok["就地线索"]),
    not read_bad and read_ok == {"进谱": len(codexed), "就地线索": len(reads) - len(codexed)},
    "%s" % (read_bad[:2] or read_ok))

print()
print("按类别计数：")
for kd in KINDS:
    n = [k for k, v in po.items() if v.get("kind") == kd]
    if n:
        print("  %-6s %d 条  %s" % (kd, len(n), " · ".join(po[k]["name"] for k in n[:6])))
print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
