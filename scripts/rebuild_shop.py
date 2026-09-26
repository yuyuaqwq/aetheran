# -*- coding: utf-8 -*-
"""铺子口径落盘脚本（B4-15）：把「品阶系数」从真源文档解析进 `content/rules/shop.json`。

源（唯一真源，一个字都不新编）：
  · `06_第一阶段垂直切片/00_第一阶段内容总纲_v1.md §六` 末尾那一行 ——
    品阶四档：普通 1.00 / 精制 1.08 / 稀有 1.16 / 遗物 1.24
  · `06_第一阶段垂直切片/03_风车镇_指令与回复 §一` —— `药铺`（在镇上 · 买药）
  · `06_第一阶段垂直切片/04_指令总表 §物品` —— `购买 <物品>`（别名 买 · 守卫 在铺子且钱够）
  · `06_第一阶段垂直切片/05_玩法数值口径 §六` —— 「铺子｜镇上 3 家；价 = 基础价 × 品阶系数」
★ P-55 那一格（本批加的）：**固定加价** `buy_markup` —— 真源 05 §六 只给了方向
  （「价 = 基础价 × 品阶系数」），这一格真源**没给数** ⇒ 乙档保守取：
  台账 ⏸ P-55 的倾向（「例：买价 = 收价 × 2」）+ 本路作业书同一句 ⇒ 普通档（系数 1.00）
  下正好就是「买价 = 收价 × 2」，「卖给铺子的东西能原价买回来」那个怪现象从此堵上；
  收价一个字不动（B3-12 落的『卖出』= `items.price`）。要调只改下面这一格 + 重跑本脚本。
口径：`00_总纲/18_铺子买卖口径_v1.md`（B4-15 那四条 + 加价与物价倍率两格 · 待主线落）
落点：`content/rules/shop.json`（`content/shop.py` 只读它；代码里不写数、不写价、不写 id）
★ fix7-gear（2026-09-26）：这一份从「药铺一家」扩成「几家」—— 本脚本仍然只生成**真源派生的那几格**
  （四个系数 / 固定加价 / 药铺那一家 = 顶层那两格），**手写的 `shelves`（柯尔那家 · 商队那家）
  照原样带过去**（见 `merge_hand_shelves`：冲掉它 = 铁匠铺那一屏整段消失，那是静默丢功能）。

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
#: ★ 铺子的固定加价（P-55）：买价 = 基础价 × 品阶系数 × 这一格。
#:   真源没给这个数（05 §六 只有方向）⇒ 口径来源与理由见本文件头注（台账 ⏸ P-55 的倾向）。
BUY_MARKUP = 2


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
        rows.append((iid, str(rec.get("name") or ""),
                     int(round(float(base) * coeffs[q] * BUY_MARKUP)), int(base)))
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
        "_note": "铺子那几家：货架 + 买价口径 —— **唯一真源**，`content/shop.py` 现读"
                 "（代码里不写数、不写价、不写 id）。顶层那几格 = **药铺那一家**（本脚本生成）；"
                 "`shelves` 那几格 = 其余几家（手写 · 重跑时照原样带过去）。",
        "_src": {
            "真源": "aetheran-plan/06_第一阶段垂直切片/00_第一阶段内容总纲_v1.md §六（品阶四档）"
                    " · 03_风车镇_指令与回复 §一（`药铺` 在镇上 · 买药）"
                    " · 04_指令总表 §物品（`购买 <物品>` 别名 买 · 守卫 在铺子且钱够）"
                    " · 05_玩法数值口径 §六（铺子｜价 = 基础价 × 品阶系数）",
            "口径": "aetheran-plan/00_总纲/18_铺子买卖口径_v1.md（B4-15 那四条 + P-55 落的加价那一格）",
            "生成": "scripts/rebuild_shop.py（四个系数从 00 总纲 §六 现解析；`buy_markup` 那一格"
                    "真源没给数，取值理由写在脚本头注里 —— 本文件不手打）",
            "加几家（fix7-gear · 手写那几格）":
                    "`shelves` = 除药铺之外的几家（柯尔那家 · 商队那家）—— **不是本脚本生成**"
                    "（重跑时照原样带过去，见 `merge_hand_shelves`）。依据：真源 "
                    "`06_第一阶段垂直切片/06_装备获取与支线玩法_v1.md §一 1.1 + §5.4 + §5.3`"
                    "（普通档 = 镇上铺子直接买 · 兜底 · 制作是「同档不同形状」）· "
                    "`07_装备体系_v2 §四`（低阶铺子能买）· "
                    "`00_总纲/06_阶段交接指南_v3.md §3.1③`（凑整 · 费用按等级）· "
                    "`06_第一阶段垂直切片/29_世界事件_设计_v1.md §五`（商队到货才有货）。"
                    "逐条裁决与逐件数值写在包 `_notes.md`「fix7-gear」那一节。",
        },
        "quality_mult": {q: coeffs[q] for q in QUAL_ORDER},
        "quality_default": "普通",
        "buy_markup": BUY_MARKUP,
        "stock_kind": STOCK_KIND,
        "station_func": STATION_FUNC,
    }


def merge_hand_shelves(obj, old):
    """★ fix7-gear：把**手写**的那一格（`shelves` = 除药铺之外的几家）原样带过去。

    为什么：本脚本是**生成物**（只重算真源派生的那几格：四个系数 / 加价 / 药铺那一家）；
    `shelves` 不是真源那张表派生的（真源只给「普通档铺子能买」这条口径，逐家怎么收写在
    `_notes.md`）⇒ 重跑本脚本**不许把它冲掉**（冲掉 = `content/shop.py` 当场抛，
    铁匠铺那一屏整段消失 —— 那是「静默丢功能」，比报错还坏）。
    规矩：旧文件里有 `shelves` 就照原样带过去（顺序也不动 —— 货架的顺序是判据的一部分）；
    形状不对（缺收法）⇒ **当场抛**（fail-closed，不许带一份坏表过去）。
    """
    sh = (old or {}).get("shelves")
    if sh is None:
        return obj
    if not isinstance(sh, dict) or not sh:
        die("旧文件里的 `shelves` 形状不对：%r（不带着它落盘，先改对）" % (sh,))
    for k, v in sh.items():
        if not isinstance(v, dict) or not (v.get("stock_kind") or v.get("shop_key")):
            die("`shelves.%s` 既没写 `stock_kind` 也没写 `shop_key` —— 收什么货判不了" % k)
    obj = dict(obj)
    obj["shelves"] = sh
    return obj


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
    old = None
    if os.path.exists(OUT):
        try:
            old = json.load(io.open(OUT, encoding="utf-8"))
        except ValueError:
            old = None
    obj = merge_hand_shelves(obj, old)                       # ★ 手写那几家带过去
    rows = shelf(coeffs, items)
    print("品阶系数（源：%s §六）：%s" % (os.path.basename(DOC),
                                      " / ".join("%s %.2f" % (q, coeffs[q]) for q in QUAL_ORDER)))
    print("固定加价（P-55 · 真源没给数 ⇒ 台账倾向取）：买价 = 收价 × 品阶系数 × %d" % BUY_MARKUP)
    print("药铺那一站：%s（npcs.funcs 带 %r 的人所在节点）" % (obj["station_func"], STATION_FUNC))
    for iid, name, gold, base in rows:
        print("  柜上：%-18s %s  —— %d 铜板（收价 %d × %d）" % (iid, name, gold, base, BUY_MARKUP))
    if obj.get("shelves"):
        print("  ★ 手写那几家（`shelves` · 不是本脚本生成，照原样带过去）：%s"
              % " · ".join(sorted(obj["shelves"])))
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
