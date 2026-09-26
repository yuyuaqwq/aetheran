# -*- coding: utf-8 -*-
"""探针：**g4-leftovers 那 11 条小账逐条有着落**（本轮唯一的「收口登记」门禁 · 第 50 支）。

为什么要有它
------------
本轮把 11 条小账**分散**收进了 9 支已有的探针（每支加/改的是它自己那一族的口径）。
分散的代价是：删掉其中任何一条**判据**（或哪天真把它写回去），**没有一处**会报
「这一条又没人管了」—— 这就回到 `legacy-debt-triage` 记的那个坑（「门禁不覆盖的地方就是会烂的地方」）。
⇒ 本支只做一件事：把这 11 条 → （探针文件 · 判据锚句）**登记成一张表**，逐行核对锚句在源码里真的在。

判据
----
① 表恰好 11 行（本轮派活的条数）· 每行有：编号 · 一句话 · 探针文件 · 判据锚句（≥8 字）
② 每个 `探针文件` 真在 `scripts/` 下 · 锚句在它的源码里真搜得到（**逐条**核，不是整表核）
③ 每条锚句**只许出现在它登记的那一支**里（防「挪到别处就算数」—— 一处口径）
④ **反证（有牙）**：现编一条不存在的锚句 ⇒ 同一段核对逻辑当场把它报成「找不到」
   （判据真的在搜源码，不是纸上说明）

用法：`GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_leftovers_g4.py`
"""
from __future__ import annotations

import io
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "scripts")

#: ★ 本轮 11 条 → （探针文件 · 判据锚句）。锚句 = 那一条判据落点里**唯一**的一段字
#: （改判据时这段字跟着改，本支就会先红 —— 逼着一起跟账）。
ROWS = [
    ("①", "材料名两条线彻底分得开（铁渣→矿渣 · 骨头→残骸 · 旧铁不动）",
     "probe_gear_starter.py", "两条线的料名彻底分得开"),
    ("②", "随机装甲不再抢打造位（打造件 no_drop · 铺子那三件不排）",
     "probe_gear_starter.py", "真跑 400 轮动态格"),
    ("③", "建号那一步的玩家词三处对齐（引导/帮助/真源都写『名字 <名字>』）",
     "probe_cmds.py", "SYS_RENAME_ASK"),
    ("④", "分页引导逐列点名（列表名从 pager.LIST_DECL 现算）",
     "probe_pager.py", "引导里那一串列表 == 三处登记"),
    ("⑤", "白烛堂按状态分支（满血那一版 · 前几行逐字相同）",
     "probe_onsite.py", "场景按状态分支（满血那一版）"),
    ("⑥", "精英多条词条拼一行：没有 `。；` · 末尾一枚 line_end",
     "probe_monsters.py", "多条词条的 hint 拼接"),
    ("⑦", "两个镇口各有一件上手摸得着的东西",
     "probe_onsite.py", "两个镇口各有自己的「看得见」栏"),
    ("⑧", "三处隐藏点所在的那一站都有可搜刮面（含稀有那一档）",
     "probe_pois.py", "三处隐藏点所在的那一站都有可搜刮面"),
    ("⑨", "NPC 作息 + 「人不在」逐位说清（14 位每位一句「他什么时候在」）",
     "probe_npcs.py", "作息表（31 §七①"),
    ("⑩", "石碑名单按真实经历分支（没读过白桦树不断言「你见过」）",
     "probe_pois.py", "可读物正文按真实经历分支"),
    ("⑪", "东西口「看得见」栏（与第 7 条同一件事的两面 —— 一并核）",
     "probe_onsite.py", "两站那两件是**触摸**类"),
]

OK, BAD = [], []


def chk(label, cond, extra=""):
    (OK if cond else BAD).append(label)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


def _src(fn):
    with io.open(os.path.join(SCRIPTS, fn), encoding="utf-8") as f:
        return f.read()


def _audit(rows, corpus):
    """逐行核对（回 `(找不到的行, 一处口径的行)`）—— ★ 与反证共用同一段逻辑。"""
    miss, dup = [], []
    for item, _what, fn, anchor in rows:
        if fn not in corpus:
            miss.append((item, fn, "探针文件不在 scripts/ 下"))
            continue
        if len(str(anchor)) < 8:
            miss.append((item, fn, "锚句太短（<8 字）"))
            continue
        if str(anchor) not in corpus[fn]:
            miss.append((item, fn, str(anchor)[:24]))
    for item, _what, fn, anchor in rows:
        _hit = [g for g, s in sorted(corpus.items()) if str(anchor) in s]
        if len(_hit) > 1:
            dup.append((item, anchor, _hit))
    return miss, dup


print("探针：g4-leftovers 那 11 条小账逐条有着落（第 50 支）")
#: ★ 本支**自己不算**核对面（锚句本来就写在这张表里）—— 只扫**别的**探针。
_exist = sorted(f for f in os.listdir(SCRIPTS)
                if f.startswith("probe_") and f.endswith(".py")
                and f != os.path.basename(os.path.abspath(__file__)))
_corpus = {f: _src(f) for f in _exist}

chk("① 表恰好 %d 行 · 每行有（编号 · 一句话 · 探针文件 · 锚句 ≥8 字）" % 11,
    len(ROWS) == 11 and all(len(r) == 4 and str(r[3]).strip() and len(str(r[3])) >= 8
                            for r in ROWS) and len({r[0] for r in ROWS}) == 11,
    "%d 行 · 编号 %s" % (len(ROWS), " ".join(r[0] for r in ROWS)))
_miss, _dup = _audit(ROWS, _corpus)
chk("② 每行的探针文件真在 scripts/ 下 · 锚句在它源码里真搜得到（逐条核 · 逐条打印落点）",
    not _miss, "%s" % (_miss,))
for _it, _what, _fn, _an in ROWS:
    print("     · %s %-22s %s" % (_it, _fn, _an))
chk("③ 每条锚句**只出现在它登记的那一支**里（防「挪到别处就算数」—— 一处口径）",
    not _dup, "%s" % (_dup,))

# ④ 反证（有牙）：现编一条不存在的锚句 ⇒ 同一段核对逻辑当场报「找不到」
_fake = list(ROWS) + [("⑫", "这条是编的", "probe_gear_starter.py", "这一句在源码里根本不存在-asdf-9x")]
_miss_fake, _dup_fake = _audit(_fake, _corpus)
chk("④ 反证（有牙）：现编一条不存在的锚句 ⇒ 同一段核对逻辑当场把它报出来（%s）"
    % (_miss_fake[:1] or "没报出来"), len(_miss_fake) == 1 and _miss_fake[0][0] == "⑫")

print()
print("通过 %d · 失败 %d" % (len(OK), len(BAD)))
if BAD:
    for _b in BAD:
        print("  -", _b)
    sys.exit(1)
print("结果：全绿 ✓")
