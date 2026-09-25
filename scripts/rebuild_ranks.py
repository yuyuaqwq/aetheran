# -*- coding: utf-8 -*-
"""公会评级阶梯落盘脚本（B4-16）：把「档序 / 门槛」从真源文档解析进 `content/rules/ranks.json`。

源（唯一真源，一个字都不新编）：
  · `06_第一阶段垂直切片/05_玩法数值口径_v1.md §一` 那一行 ——
    评级 ｜ 见习 → 铜（交 5 条）→ 银（交 15 条 + 打掉 1 个头目）→ 金（第一阶段到银为止）
  · `06_第一阶段垂直切片/04_指令总表.md §公会与委托` —— `升级证` `换证`（守卫 评级达标）
  · `06_第一阶段垂直切片/03_风车镇_指令与回复.md §一` —— `登记`（办见习证）
口径：`00_总纲/17_文案收口口径_v1.md` 末节（公会评级阶梯 · 档名走 `RANK_<ID>` 槽位）
落点：`content/rules/ranks.json`（`content/ranks.py` 只读它；代码里不写档名、不写门槛数）

规矩：LF 落盘 · 原序 · 末尾一个换行 · 连跑两次数据不变（幂等自检）· `--dry` 一个字节都不写

用法：python scripts/rebuild_ranks.py [--dry]
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.environ.get("AST_PLAN", "C:/Users/yuyu/aetheran-plan")
DOC = os.path.join(PLAN, "06_第一阶段垂直切片", "05_玩法数值口径_v1.md")
OUT = os.path.join(PKG, "content", "rules", "ranks.json")

#: 真源里那档名 → ASCII id 的**唯一映射处**（域里、代码里都不许再写中文档名 —— K51）。
#:   `content/ranks.py::label_key` 按 `RANK_<ID>` 取槽位（档名本体在 texts 域）。
NAME2ID = {"见习": "apprentice", "铜": "bronze", "银": "silver", "金": "gold"}

#: 「第一阶段到这儿为止」那个标记（真源里挂在最后一档后面 —— 它不是一档，是**停标记**）
STOP_MARK = "第一阶段"

ROW_RE = re.compile(r"^\|\s*评级\s*\|([^|]+)\|\s*$", re.M)
SEG_RE = re.compile(r"^([^（(]+?)(?:[（(](.+?)[）)])?$")
DONE_RE = re.compile(r"交\s*(\d+)\s*条")
CHIEF_RE = re.compile(r"打掉\s*(\d+)\s*个头目")


def die(msg):
    raise SystemExit("rebuild_ranks: %s" % msg)


def _load(path):
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_doc(path=DOC):
    """解析真源那一行 -> (档列表, 停标记那一档的中文名)。

    档列表里每条 = `{"id", "order", "need_done", "need_chief"}`（**不带档名** ——
    档名是文案，住在 texts 域；这里只给 ASCII id，代码按 `RANK_<ID>` 取字）。
    """
    if not os.path.exists(path):
        die("真源文档不在：%s" % path)
    txt = io.open(path, encoding="utf-8").read()
    hit = ROW_RE.search(txt)
    if not hit:
        die("真源里找不到「| 评级 | … → … |」那一行")
    segs = [s.strip() for s in hit.group(1).split("→") if s.strip()]
    if len(segs) < 2:
        die("阶梯至少要有两档，真源那一行只切出 %r" % (segs,))
    tiers, stop_name, stop_at = [], None, None
    for i, seg in enumerate(segs):
        m = SEG_RE.match(seg)
        if not m:
            die("切不开这一段：%r" % seg)
        name, cond = m.group(1).strip(), (m.group(2) or "").strip()
        if STOP_MARK in cond:
            stop_name, stop_at = name, i
            break
        if name not in NAME2ID:
            die("真源里出现了新档名 %r（%s）—— 先定它的 ASCII id，再往 NAME2ID 里加" % (name, seg))
        d = DONE_RE.search(cond)
        c = CHIEF_RE.search(cond)
        if cond and not d and not c:
            die("这一段的条件认不出（既没有「交 N 条」也没有「打掉 N 个头目」）：%r" % seg)
        tiers.append({"id": NAME2ID[name], "order": len(tiers) + 1,
                      "need_done": int(d.group(1)) if d else 0,
                      "need_chief": int(c.group(1)) if c else 0})
        tiers[-1]["_name"] = name                      # 只给本脚本印出来过目用，不落盘
    if not stop_name:
        die("真源那一行里没有「%s…为止」那个停标记 —— 第一阶段开到哪一档叫不准" % STOP_MARK)
    if stop_at != len(tiers):
        die("停标记不在最后：它前面还有 %d 段（%s）" % (len(segs) - stop_at - 1, segs[stop_at + 1:]))
    last = tiers[-1]["_name"]
    if ("到%s为止" % last) not in (segs[stop_at]):
        die("停标记那句没说「到%s为止」（原文：%r）—— 真源把口改了，先看文档" % (last, segs[stop_at]))
    if tiers[0]["need_done"] or tiers[0]["need_chief"]:
        die("第一档（%s）不该有门槛：%r" % (tiers[0]["_name"], tiers[0]))
    for a, b in zip(tiers, tiers[1:]):
        if b["need_done"] < a["need_done"] or b["need_chief"] < a["need_chief"]:
            die("门槛必须一档比一档高：%r -> %r" % (a, b))
    if len(NAME2ID) - len(tiers) != 1:
        die("NAME2ID 比阶梯多出的档名不是停标记那一个：%s vs %s"
            % (sorted(NAME2ID), [t["_name"] for t in tiers]))
    return tiers, stop_name


def build(tiers, stop_name):
    clean = [{k: v for k, v in t.items() if not k.startswith("_")} for t in tiers]
    return {
        "_note": "公会评级阶梯 —— **唯一真源**：档序与门槛由 `scripts/rebuild_ranks.py` 从真源文档"
                 "现解析；档名是文案，住在 `texts` 域（键 = `RANK_<ID>`，见 `content/ranks.py`）。"
                 "代码里不写档名、不写门槛数。",
        "_src": {
            "真源": "aetheran-plan/06_第一阶段垂直切片/05_玩法数值口径_v1.md §一（评级那一行）"
                    " · 04_指令总表.md §公会与委托（`升级证`/`换证` · 守卫 评级达标）"
                    " · 03_风车镇_指令与回复.md §一（`登记` 办见习证）",
            "口径": "aetheran-plan/00_总纲/17_文案收口口径_v1.md 末节（公会评级阶梯）",
            "生成": "scripts/rebuild_ranks.py（档序与门槛从 05 §一 现解析，本文件不手打）",
            "第一阶段开到": stop_name,
        },
        "label_tpl": "RANK_%s",
        "tiers": clean,
    }


def dump(obj, path):
    with io.open(path, "w", newline=chr(10), encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write(chr(10))


def main(argv):
    dry = "--dry" in argv
    tiers, stop_name = parse_doc()
    obj = build(tiers, stop_name)
    print("评级阶梯（源：%s §一）：" % os.path.basename(DOC))
    for t in tiers:
        print("  %d. %-4s %-10s 交 %2d 条 ＋ 打掉 %d 个头目"
              % (t["order"], t["_name"], t["id"], t["need_done"], t["need_chief"]))
    print("  停标记：%s（%s）" % (stop_name, obj["_src"]["第一阶段开到"]))
    old = None
    if os.path.exists(OUT):
        try:
            old = _load(OUT)
        except ValueError:
            old = None
    same = old == obj
    if dry:
        print("（--dry：没落盘；%s）" % ("与现文件一致" if same else "会改写 content/rules/ranks.json"))
        return 0
    if same:
        print("  · 无变化 —— 数据不变（幂等）")
        return 0
    dump(obj, OUT)
    print("落地：%s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
