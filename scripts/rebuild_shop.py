# -*- coding: utf-8 -*-
"""铺子口径落盘脚本（B4-15）：把「品阶系数」从真源文档解析进 `content/rules/shop.json`。

源（唯一真源，一个字都不新编）：
  · `06_第一阶段垂直切片/00_第一阶段内容总纲_v1.md §六` 末尾那一行 ——
    品阶四档：普通 1.00 / 精制 1.08 / 稀有 1.16 / 遗物 1.24
  · `06_第一阶段垂直切片/03_风车镇_指令与回复 §一` —— `药铺`（在镇上 · 买药）
  · `06_第一阶段垂直切片/04_指令总表 §物品` —— `购买 <物品>`（别名 买 · 守卫 在铺子且钱够）
  · `06_第一阶段垂直切片/05_玩法数值口径 §六` —— 「铺子｜镇上 3 家；价 = 基础价 × 品阶系数」
口径：`00_总纲/18_铺子买卖口径_v1.md`
落点：`content/rules/shop.json`（`content/shop.py` 只读它；代码里不写数、不写价、不写 id）

规矩：LF 落盘 · 原序 · 末尾一个换行 · 连跑两次数据不变（幂等自检）· `--dry` 一个字节都不写

用法：python scripts/rebuild_shop.py [--dry]
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.environ.get("AST_PLAN", "C:/Users/yuyu/aetheran-plan")
DOC = os.path.join(PLAN, "06_第一阶段垂直切片", "00_第一阶段内容总纲_v1.md")
OUT = os.path.join(PKG, "content", "rules", "shop.json")
ITEMS = os.path.join(PKG, "content", "data", "items.json")
NPCS = os.path.join(PKG, "content", "data", "npcs.json")

#: 品阶四档那一行（真源里就这一处写着这四个数）
LINE_RE = re.compile(r"品阶四档：\s*普通\s*([0-9.]+)\s*/\s*精制\s*([0-9.]+)\s*"
                     r"/\s*稀有\s*([0-9.]+)\s*/\s*遗物\s*([0-9.]+)")
QUAL_ORDER = ("普通", "精制", "稀有", "遗物")

#: 货架 = items 域里这一档 `kind_key`（口径 §二①：03 §一 那一栏写的是「买药」）
STOCK_KIND = "tool"
#: 药铺那一站 = npcs 域里 `funcs` 带这个词的那个人所在节点（口径 §三）
STATION_FUNC = "herb"


def die(msg):
    raise SystemExit("rebuild_shop: %s" % msg)


def _load(path):
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_coeffs():
    if not os.path.exists(DOC):
        die("真源文档不在：%s" % DOC)
    txt = io.open(DOC, encoding="utf-8").read()
    hit = LINE_RE.search(txt)
    if not hit:
        die("真源里找不到「品阶四档：普通 … / 精制 … / 稀有 … / 遗物 …」那一行")
    got = [float(x) for x in hit.groups()]
    if got != sorted(got) or got[0] <= 0:
        die("四个系数必须递增且为正：%r" % (got,))
    return {q: c for q, c in zip(QUAL_ORDER, got)}


def shelf(coeffs, items):
    """货架上有什么、卖多少 —— 与 `content/shop.py` **同一套算法**（本脚本只为过目/对账）。"""
    rows = []
    for iid in sorted(items):
        rec = items[iid] or {}
        if rec.get("kind_key") != STOCK_KIND:
            continue
        base = rec.get("price")
        if not isinstance(base, (int, float)) or isinstance(base, bool) or base <= 0:
            die("%s 在货架上却没有价（items.price）：%r" % (iid, base))
        q = str(rec.get("quality") or "普通")
        if q not in coeffs:
            die("%s 的 quality 不在四档里：%r" % (iid, q))
        rows.append((iid, str(rec.get("name") or ""), int(round(float(base) * coeffs[q]))))
    if not rows:
        die("货架是空的 —— items 域里没有 kind_key == %r 的条目" % STOCK_KIND)
    return rows


def build(coeffs, items, npcs):
    spots = {}
    for k, v in npcs.items():
        if isinstance(v, dict) and STATION_FUNC in (v.get("funcs") or []):
            spots.setdefault(str(v.get("subarea") or ""), []).append(k)
    if len(spots) != 1:
        die("药铺那一站叫不准（带 funcs=%r 的人分在 %s）—— 守卫没法 fail-closed"
            % (STATION_FUNC, sorted(spots)))
    node = next(iter(spots))
    keys = [k for k in items if isinstance(items[k], dict)
            and items[k].get("kind_key") == STOCK_KIND]
    if not keys:
        die("items 域里没有 kind_key == %r 的条目" % STOCK_KIND)
    return {
        "_note": "药铺那一家：货架 + 买价口径 —— **唯一真源**，`content/shop.py` 现读"
                 "（代码里不写数、不写价、不写 id）。",
        "_src": {
            "真源": "aetheran-plan/06_第一阶段垂直切片/00_第一阶段内容总纲_v1.md §六（品阶四档）"
                    " · 03_风车镇_指令与回复 §一（`药铺` 在镇上 · 买药）"
                    " · 04_指令总表 §物品（`购买 <物品>` 别名 买 · 守卫 在铺子且钱够）"
                    " · 05_玩法数值口径 §六（铺子｜价 = 基础价 × 品阶系数）",
            "口径": "aetheran-plan/00_总纲/18_铺子买卖口径_v1.md（本批的四条 + 待拍板那一条）",
            "生成": "scripts/rebuild_shop.py（四个系数从 00 总纲 §六 现解析，本文件不手打）",
        },
        "quality_mult": {q: coeffs[q] for q in QUAL_ORDER},
        "quality_default": "普通",
        "stock_kind": STOCK_KIND,
        "station_func": STATION_FUNC,
    }


def dump(obj, path):
    with io.open(path, "w", newline=chr(10), encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write(chr(10))


def main(argv):
    dry = "--dry" in argv
    coeffs = parse_coeffs()
    items = _load(ITEMS)
    npcs = _load(NPCS)
    obj = build(coeffs, items, npcs)
    rows = shelf(coeffs, items)
    print("品阶系数（源：%s §六）：%s" % (os.path.basename(DOC),
                                      " / ".join("%s %.2f" % (q, coeffs[q]) for q in QUAL_ORDER)))
    print("药铺那一站：%s（npcs.funcs 带 %r 的人所在节点）" % (obj["station_func"], STATION_FUNC))
    for iid, name, gold in rows:
        print("  柜上：%-18s %s  —— %d 铜板" % (iid, name, gold))
    old = None
    if os.path.exists(OUT):
        try:
            old = json.load(io.open(OUT, encoding="utf-8"))
        except ValueError:
            old = None
    same = old == obj
    if dry:
        print("（--dry：没落盘；%s）" % ("与现文件一致" if same else "会改写 content/rules/shop.json"))
        return 0
    if same:
        print("  · 无变化 —— 数据不变（幂等）")
        return 0
    dump(obj, OUT)
    print("落地：%s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
