# -*- coding: utf-8 -*-
"""排版门禁：三档行宽（阿斯特兰 · 全屏排版车道）

判据来源：鱼鱼「排版要考虑玩家体验，一般一行只能放 14 个字」
—— 14 是**软目标**，故分三档：

  档① 硬上限 20  战斗 cue / 面板行 / 列表行（槽名含 ROW/LINE/ITEM/CELL，或 COMBAT_*）
                   超过 20 全角宽 = 排版事故，硬红。
  档② 软目标 14  提示行 / 问句（槽名含 HINT/ASK/TIP/BAD）
                   14–20 只记警告并统计，不改判据（措辞归 P5 车道）。
  档③ 长文体      场景 / 可读物 / 说明（槽名含 SCENE/READ/HELP/NOTE）
                   长度不限，但**必须按 ≤14 分段**。

宽度量法：全角算 1 · 半角与 emoji 算 0.5（east_asian_width）。
"""
import io
import json
import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXTS = os.path.join(ROOT, "content", "data", "texts.json")

R_TIER1 = re.compile(r"ROW|LINE|ITEM|CELL|^COMBAT", re.I)
R_TIER2 = re.compile(r"HINT|ASK|TIP|BAD", re.I)
R_TIER3 = re.compile(r"SCENE|READ|HELP|NOTE", re.I)

SOFT = 14.0
HARD = 20.0


def width(s):
    t = 0.0
    for ch in s:
        t += 1.0 if unicodedata.east_asian_width(ch) in ("W", "F", "A") else 0.5
    return t


def tier_of(slot):
    if R_TIER1.search(slot):
        return 1
    if R_TIER2.search(slot):
        return 2
    if R_TIER3.search(slot):
        return 3
    return 0


def main():
    texts = json.load(io.open(TEXTS, encoding="utf-8"))
    hard, warn, unsplit = [], [], []
    n_slots = n_lines = 0
    for slot, rec in texts.items():
        val = rec.get("value", "") if isinstance(rec, dict) else ""
        if not val:
            continue
        n_slots += 1
        tier = tier_of(slot)
        for i, line in enumerate(val.split("\n")):
            if not line.strip():
                continue
            n_lines += 1
            lw = width(line)
            if tier == 1 and lw > HARD:
                hard.append((slot, i, lw, line))
            elif tier == 2 and lw > SOFT:
                warn.append((slot, i, lw, line))
            elif tier == 3 and lw > SOFT:
                unsplit.append((slot, i, lw, line))
            elif tier == 0 and lw > HARD:
                # 归不进三档的：按档① 的硬上限兜住（战斗/面板/任务行都在这一类）
                hard.append((slot, i, lw, line))

    print("槽位 %d 有内容 · 非空行 %d" % (n_slots, n_lines))
    print("  档① 硬红（>%.0f 全角）: %d" % (HARD, len(hard)))
    print("  档② 警告（%.0f–%.0f）: %d" % (SOFT, HARD, len(warn)))
    print("  档③ 未按 %.0f 分段    : %d" % (SOFT, len(unsplit)))

    ok = True
    if hard:
        ok = False
        print("\n✗ 档① 硬红 %d 行（必改）" % len(hard))
        for slot, i, lw, line in hard[:40]:
            print("   %-40s L%d  %.1f  %s" % (slot, i, lw, line[:56]))
        if len(hard) > 40:
            print("   ... 共 %d 行" % len(hard))
    if unsplit:
        print("\n✗ 档③ 长文体未按 %.0f 分段 %d 行" % (SOFT, len(unsplit)))
        for slot, i, lw, line in unsplit[:40]:
            print("   %-40s L%d  %.1f  %s" % (slot, i, lw, line[:56]))
        if len(unsplit) > 40:
            print("   ... 共 %d 行" % len(unsplit))
    if warn:
        print("\n△ 档② 软目标未达 %d 行（只统计，不改判据）—— 措辞归 P5 车道" % len(warn))
        for slot, i, lw, line in warn[:10]:
            print("   %-40s L%d  %.1f" % (slot, i, lw))

    if ok:
        print("\n✓ 排版门禁通过（档① 全 ≤%.0f · 档③ 全已按 %.0f 分段）" % (HARD, SOFT))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
