# -*- coding: utf-8 -*-
"""一次性的落槽脚本（B3-23）：把下面这张表的槽位追加进 content/data/texts.json。

形状与 `scripts/rebuild_syscopy.py` 落盘的一致（value/params/category/desc），
所以真源表补齐之后重跑生成器 = 零 diff（幂等）。
用法：python scripts/_b53_slots.py [--dry]
"""
from __future__ import annotations

import io
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXTS = os.path.join(REPO, "content", "data", "texts.json")

#: (键, 文案, 参数, 类, 出处) —— 真源待补行：`_notes.md` 里有同一张表（五列，键不带反引号）
ROWS = [
    ("COMBAT_MEET", "⚠️ 遭遇：{name}", ["name"], "战斗",
     "战斗 · 遇敌那一行（原为 cmds_battle 内联，逐字搬进表）"),
    ("COMBAT_NONE", "这一带暂时没有遇到什么。", [], "战斗",
     "战斗 · 没遇敌（原为 cmds_battle 内联，逐字搬进表）"),
    ("COMBAT_NEED_FOE", "这一手得在打起来的时候用 —— 这一带没有能打的东西。", [], "战斗",
     "战斗指令五条 · 没遇敌（打断/放技能/用物/换武器/后撤）"),
    ("COMBAT_INT_PLAIN", "你盯着它的起手。", [], "战斗",
     "打断 · 本门没有专门的打断动作时（今天域里只有刺客挂了 mech=interrupt）"),
    ("COMBAT_INT_HEAD", "{skill} —— 你盯着它的起手。", ["skill"], "战斗",
     "打断 · 有本门动作时（skills 域 mech=interrupt 那一条的名字）"),
    ("COMBAT_INT_BREAK", "它起手的那一下被你截断 —— 这一手它没打出来。", [], "战斗",
     "打断 · 清掉对方待发（引擎 effects 的 interrupt 动词；怪技没中文名 ⇒ 不报技名）"),
    ("COMBAT_INT_PUSH", "你把它压在后面 —— 它下一次行动的到点时刻被推后 {ticks} 刻。", ["ticks"],
     "战斗", "打断 · 推后到点时刻（推后量 = 你这一手的耗时，走内容侧声明表）"),
    ("COMBAT_SKILL_HEAD", "「{name}」—— 这一场你的第一手就放它。", ["name"], "战斗",
     "放技能 · 这一手"),
    ("COMBAT_SKILL_BAD", "「{name}」这一手你放不出来 —— 敲『技能』看你这一门会哪些。", ["name"],
     "战斗", "放技能 · 不是本职业 / 没学过 / 认不出（四道门都收在这儿）"),
    ("COMBAT_ITEM_HEAD", "「{name}」备在手边 —— 这一场有空就用它。", ["name"], "战斗",
     "战斗中用物 · 这一手"),
    ("COMBAT_ITEM_BAD", "背包里没有「{name}」。", ["name"], "战斗", "战斗中用物 · 认不出"),
    ("COMBAT_ITEM_CAP", "「{name}」这一场用过了 —— 一场一次，后面的手只能照打。", ["name"], "战斗",
     "战斗中用物 · 每场上限（content/rules/battle_cmds.json · item_uses_per_battle）"),
    ("COMBAT_SWAP_ASK", "背包里还有能换的：{list} —— 想点准哪一件，敲『装备 <名字>』。", ["list"], "战斗",
     "换武器 · 候选不止一件时那一行（本条声明没有参数 ⇒ 换哪件由数据说话）"),
    ("COMBAT_SWAP_OK", "你换上了{icon}{name}（{kind}）—— 这一手花在换手上。", ["icon", "kind", "name"],
     "战斗", "换武器 · 换上（04_指令总表 §五「吃一次行动」）"),
    ("COMBAT_SWAP_NONE", "背包里没有另一件能换的武器 —— 这一手省下了。", [], "战斗",
     "换武器 · 没得换"),
    ("COMBAT_RETREAT_HEAD", "你压低身子，先看退路。", [], "战斗", "后撤 · 这一手"),
    ("COMBAT_RETREAT_OK", "它这会儿没在出招 —— 你退开了，这一场没打。", [], "战斗",
     "后撤 · 能跑掉（对方这一拍没有待发那一手）"),
    ("COMBAT_RETREAT_BLOCK", "{name} 正押着一手 —— 退不开，这一手白花。", ["name"], "战斗",
     "后撤 · 跑不掉（对方那一下正落下来 = 不许无脑逃跑）"),
    ("COMBAT_FOCUS_SOLO", "集火是几个人的事 —— 今天打手只有你一个（组队还没接线）。", [], "战斗",
     "集火 · 单人"),
    ("COMBAT_FOCUS_NAMED", "「{name}」认得出来 —— 但集火得有人跟你一起打。", ["name"], "战斗",
     "集火 · 单人（点名那只在 monsters 域里认得出来）"),
]


def main(argv):
    dry = "--dry" in argv
    with io.open(TEXTS, encoding="utf-8") as f:
        tx = json.load(f)
    before = len(tx)
    add, same, clash = [], 0, []
    for key, value, params, cat, src in ROWS:
        old = tx.get(key)
        if old is None:
            add.append((key, value, params, cat, src))
        elif old.get("value") == value and list(old.get("params") or []) == list(params):
            same += 1
        else:
            clash.append((key, old.get("value"), value))
    if clash:
        for k, a, b in clash:
            print("  x %s 两处不一样：\n      表里：%s\n      域里：%s" % (k, b, a))
        raise SystemExit("槽位与域里的字不一样 —— 先裁决再落（没写任何东西）")
    print("解析：%d 条（已存在且一致 %d · 要新增 %d）" % (len(ROWS), same, len(add)))
    if not add:
        print("  · 无新增 —— 数据不变（幂等）")
        return 0
    for key, value, params, cat, src in add:
        tx[key] = {"value": value, "params": list(params), "category": cat, "desc": src}
        print("  + %-20s %s" % (key, value[:36]))
    if dry:
        print("（--dry：没落盘；texts %d -> %d）" % (before, len(tx)))
        return 0
    with io.open(TEXTS, "w", newline="\n", encoding="utf-8") as f:
        json.dump(tx, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("落地：texts %d -> %d 条  %s" % (before, len(tx), TEXTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
