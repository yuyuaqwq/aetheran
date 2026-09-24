# -*- coding: utf-8 -*-
"""探针：pois 域 + texts 域（含★跨域交叉校验：poi 的位置与文案槽位都要真的存在）。

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

# ② 12 类可读物齐不齐
reads = [k for k, v in po.items() if v.get("kind") == "可读物"]
chk("可读物 12 类", len(reads) == 12, "%d 条" % len(reads))

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

print()
print("按类别计数：")
for kd in KINDS:
    n = [k for k, v in po.items() if v.get("kind") == kd]
    if n:
        print("  %-6s %d 条  %s" % (kd, len(n), " · ".join(po[k]["name"] for k in n[:6])))
print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
