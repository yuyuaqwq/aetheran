# -*- coding: utf-8 -*-
"""P4 行宽门禁 —— 三档判据（只加强不削弱）

档① 硬上限 20  · 战斗 cue / 面板行 / 列表行（ROW/LINE/ITEM/CELL/PANEL/COMBAT/STAT/NUM）
档② 软目标 14  · 提示行 / 问句（HINT/ASK/TIP/BAD/NOTICE/WARN/引导）—— 只统计，不判红
档③ 长文体   · SCENE/READ/HELP/任务 STORY/世界动静/称号/彩蛋 —— 只查「有没有按 <=14 分段」

宽度口径：全角 1 · 半角/emoji 0.5（unicodedata.east_asian_width）
鱼鱼原话「一般一行只能放 14 个字」是**软目标**，不是一刀切硬上限
=> 档② 超 14 只记警告；真正的硬红只有档① > 20 与档③ 未分段。

本探针钉的判据（2026-09-29 排版车道 P4-1 立）：
  D1 档① 不许出现 >20 全角宽的行     （硬红）
  D2 档③ 每行必须 <=14               （硬红：长文体必须分段）
  D3 档② 只统计超 14 的行数并打印    （不判红 —— 软目标不硬化）
  D4 玩家可见文案里不许混入真换行     （JSON 里必须是转义的两字符）
"""
import io, json, os, re, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
TEXTS = os.path.join(PKG, "content", "data", "texts.json")

K1 = re.compile(r"(ROW|LINE|ITEM|CELL|PANEL|COMBAT|BATTLE|STAT|NUM)")
K2 = re.compile(r"(HINT|ASK|TIP|BAD|NOTICE|WARN)")
K3 = re.compile(r"(SCENE|READ|HELP|NOTE|INTRO|DESC|LORE|STORY)")
CAT2 = {"引导"}
CAT3 = {"NPC", "对话", "彩蛋", "称号", "世界动静"}


def tier(key, cat):
    for i, rx in enumerate((K1, K2, K3), 1):
        if rx.search(key):
            return i
    for i, rx in enumerate((K1, K2, K3), 1):
        if rx.search(cat or ""):
            return i
    if cat in CAT2:
        return 2
    if cat in CAT3:
        return 3
    return 2


def cw(ch):
    return 1.0 if unicodedata.east_asian_width(ch) in ("W", "F") else 0.5


def width(s):
    return sum(cw(c) for c in s)


def tier_count(T, t):
    return sum(1 for k, v in T.items() if tier(k, v.get("category", "")) == t)


def main():
    raw = io.open(TEXTS, encoding="utf-8", newline="").read()
    T = json.loads(raw)
    bad1, bad3, warn2 = [], [], []
    for k, v in T.items():
        t = tier(k, v.get("category", ""))
        for i, ln in enumerate(v.get("value", "").split("\n")):
            if not ln.strip():
                continue
            wd = width(ln)
            if t == 1 and wd > 20:
                bad1.append((k, i + 1, wd, ln))
            elif t == 3 and wd > 14:
                bad3.append((k, i + 1, wd, ln))
            elif t == 2 and wd > 14:
                warn2.append((k, i + 1, wd, ln))

    print("行宽门禁 P4 · 槽%d 档①%d 档②%d 档③%d"
          % (len(T), tier_count(T,1), tier_count(T,2), tier_count(T,3)))
    print("  档① >20 硬红 = %d   档③ >14 硬红 = %d   档② 14-20 警告 = %d"
          % (len(bad1), len(bad3), len(warn2)))

    fails = 0
    if bad1:
        fails += len(bad1)
        print("")
        print("D1 档① 硬红（>20 全角宽）%d 行：" % len(bad1))
        for k, i, wd, ln in bad1[:25]:
            print("  %-34s L%-3d %5.1f  %s" % (k, i, wd, ln[:46]))
    if bad3:
        fails += len(bad3)
        print("")
        print("D2 档③ 硬红（长文体未按 14 分段）%d 行：" % len(bad3))
        for k, i, wd, ln in bad3[:25]:
            print("  %-34s L%-3d %5.1f  %s" % (k, i, wd, ln[:46]))
    if warn2:
        print("")
        print("D3 档② 警告（14-20 · 软目标不判红）%d 行：" % len(warn2))
        for k, i, wd, ln in warn2[:8]:
            print("  %-34s L%-3d %5.1f  %s" % (k, i, wd, ln[:46]))

    pat = chr(34) + "value" + chr(34) + ": " + chr(34) + "[^" + chr(34) + "]*" + chr(92) + "n[^" + chr(34) + "]*" + chr(34)
    if re.search(pat, raw):
        print("")
        print("D4 硬红：texts.json 里有真换行混进 value（必须是转义的两字符）")
        fails += 1
    else:
        print("  D4 真换行 = 0 OK")

    print("")
    print("✗ 行宽门禁 RED" if fails else "✓ 行宽门禁 GREEN")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
