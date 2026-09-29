# -*- coding: utf-8 -*-
"""探针：poi 按名字挑选的那一口（`_poi_pick_by_name`）—— 审计 L159 的常驻判据。

★ 这条门禁守的是什么（**别当成「风格检查」**）：
  原先 `touch` / `read_thing` 两处各写一遍 `want == name or want in name`，
  **没有 `len` 闸** ⇒ 玩家敲一个单字就是「拿它去挨个名字试」：
    `be_dogs` 敲「记」⇒ 同时挑中「重复七次的记号」「白桦林深处的记号」两件
    `bn_bone` 敲「碑」⇒ 同时挑中「半埋的碑」「十一块碑」两件
  ⇒ 玩家想摸一件、却连带把两件的增益/消耗一并领走（`touch` 那支还会连着领两次 hp/buff）。
  这是**玩家可见的行为错**，不是代码洁癖。

判据四条（逐条可复现）：
  ① 单字**挑不中任何一件**（`len(want) >= 2` 这道闸真的在）
  ② **全名相等优先于部分命中**（写全名只拿那一条，不被同站另一条截胡）
  ③ **部分命中 ≥2 字才成立**，且命中的确是**那几件**（不是碰巧）
  ④ 点不着的交**空名单**（由调用方点名说「这儿没有叫这个的」⇒ 不静默塞一件给他）
  ⑤ **反证有牙**：把 `len>=2` 那道闸临时去掉 ⇒ ① 立刻翻面（证明判据真的守着它，不是恒真）

用法（在 aetheran-package 仓根跑）：
    GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_poi_name_match.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, ENGINE)

ok = True


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


# ★ 注入点与被测方不同：直接 import 助手（不经过 `touch` / `read_thing` 两条指令线），
#   免得「指令恰好没触发」把一条真判据测成假绿。
from content import cmds_ast as CA                                # noqa: E402

pick = CA._poi_pick_by_name

print("探针：poi 按名挑选（L159 · 单字不得子串命中）")

# 候选形状 = `(pid, rec, 状态, 那一行)`（与 `_pois_here` 的产出恒同）
def cand(pid, name):
    return (pid, {"name": name}, "ok", "")


BONE = [cand("bn_bone_1", "半埋的碑"), cand("bn_bone_2", "十一块碑")]
DOGS = [cand("be_dogs_1", "重复七次的记号"), cand("be_dogs_2", "白桦林深处的记号")]
WATER = [cand("tw_water_1", "墙上的划痕"), cand("tw_water_2", "水里飘着的一页纸")]

# ① 单字挑不中（台账点名的三组实证反例，一组一条）
for ch, pool, where in [("碑", BONE, "bn_bone"), ("记", DOGS, "be_dogs"), ("划", WATER, "tower_water_room")]:
    hit = pick(pool, ch)
    chk("① 单字 %r 在 %s 挑不中任何一件（不牵连两件）" % (ch, where),
        hit == [], "挑中了 %s" % [h[1]["name"] for h in hit])

# ② 全名相等优先于部分命中：写全名只拿那一条（同站另有一条含这几个字）
chk("② 全名相等优先：写「十一块碑」只拿它，不被「半埋的碑」截胡",
    [h[1]["name"] for h in pick(BONE, "十一块碑")] == ["十一块碑"],
    str([h[1]["name"] for h in pick(BONE, "十一块碑")]))
chk("② 全名相等优先：写「重复七次的记号」只拿它，不被「白桦林深处的记号」截胡",
    [h[1]["name"] for h in pick(DOGS, "重复七次的记号")] == ["重复七次的记号"],
    str([h[1]["name"] for h in pick(DOGS, "重复七次的记号")]))

# ③ 部分命中 ≥2 字才成立，且命中的确是那几件
chk("③ 部分命中（≥2 字）成立：写「块碑」拿中那一条",
    [h[1]["name"] for h in pick(BONE, "块碑")] == ["十一块碑"],
    str([h[1]["name"] for h in pick(BONE, "块碑")]))
#   「记号」是**两件都含**的两个字 ⇒ part 档交**两件**（不是「挑一件」）：调用方
#   `touch` 拿它当「这一下摸哪几件」用 —— 原口径下它本来也交两件，这不是这一版改的。
#   本版只保证**全名相等压过部分命中**（②），部分命中**≥2 字才成立**（③）。
chk("③ 部分命中（≥2 字）成立：写「记号」两件都含它 ⇒ 交这两件（part 档不瞎挑）",
    [h[1]["name"] for h in pick(DOGS, "记号")] == ["重复七次的记号", "白桦林深处的记号"],
    str([h[1]["name"] for h in pick(DOGS, "记号")]))
chk("③ 部分命中（≥2 字）成立：写「深处的记」只中后一件（两字以上且只它含）",
    [h[1]["name"] for h in pick(DOGS, "深处的记")] == ["白桦林深处的记号"],
    str([h[1]["name"] for h in pick(DOGS, "深处的记")]))

# ④ 点不着交空名单（fail-closed：调用方据此点名，不静默塞一件）
chk("④ 点不着交空名单（不静默塞一件给他）",
    pick(BONE, "磨刀石") == [] and pick(DOGS, "磨牙石") == [],
    "摸到 %s" % [h[1]["name"] for h in pick(BONE, "磨刀石")])

# ⑤ 空参 = 不筛（无参调用时原样交回全部，两条指令的既有行为一个字不变）
chk("⑤ 空参不筛（原样交回全部，两条指令行为不变）",
    len(pick(BONE, "")) == 2 and len(pick(BONE, None)) == 2,
    "空参挑中 %d 件" % len(pick(BONE, "")))

# ⑥ ★ 反证（有牙）：把「≥2 字」那道闸去掉 ⇒ ① 立刻翻面（证明判据真的守着它）
_src = open(CA.__file__, encoding="utf-8").read()
_mark = 'elif nm and len(want) >= 2 and want in nm:'
chk("⑥ 反证前提：现行源码里那道闸在（改前先证它存在）", _mark in _src, "没找到 %r" % _mark)
#   真反证 = 用「去掉闸」的那份实现重跑同一组单字，必须命中两件
def _pick_no_gate(here, want):
    want = str(want or "").strip()
    exact = [i for i in here if want == str(i[1].get("name") or "")]
    part = [i for i in here if want in str(i[1].get("name") or "")]
    return exact or part

flip = [h[1]["name"] for h in _pick_no_gate(DOGS, "记")]
chk("⑥ 反证（撤改验证）：去掉「≥2 字」那道闸后，同一组单字 %r 立刻命中 %d 件 ⇒ 判据有牙"
    % ("记", len(flip)), len(flip) == 2, "命中 %s" % flip)

print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
