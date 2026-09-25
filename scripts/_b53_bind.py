# -*- coding: utf-8 -*-
"""一次性脚本（B3-23）：给六条战斗声明挂上 bind（声明本身一条不动：patterns/order/visible 全保留）。

用法：python scripts/_b53_bind.py [--dry]
"""
from __future__ import annotations

import io
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(REPO, "content", "data", "commands.json")

#: key → 实现体（都在 content/cmds_battle.py，四参帧：uid + player）
BIND = {
    "interrupt": "content.cmds_battle:interrupt",
    "retreat": "content.cmds_battle:retreat",
    "skill_cast": "content.cmds_battle:skill_cast",
    "battle_item": "content.cmds_battle:battle_item",
    "focus_fire": "content.cmds_battle:focus_fire",
    "swap_weapon": "content.cmds_battle:swap_weapon",
}


def main(argv):
    dry = "--dry" in argv
    with io.open(P, encoding="utf-8") as f:
        tbl = json.load(f)
    add = []
    for key, handler in BIND.items():
        e = tbl.get(key)
        if not isinstance(e, dict):
            raise SystemExit("声明表里没有 %s" % key)
        if e.get("bind"):
            if (e["bind"] or {}).get("handler") != handler:
                raise SystemExit("%s 已经绑了别的实现体：%r" % (key, e["bind"]))
            continue
        add.append(key)
        if not dry:
            e["bind"] = {"handler": handler, "call": "run", "args": ["uid", "player"]}
    print("要挂 bind：%d 条 —— %s" % (len(add), " · ".join(add) or "（无）"))
    if dry or not add:
        return 0
    with io.open(P, "w", newline="\n", encoding="utf-8") as f:
        json.dump(tbl, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("落地：%s" % P)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
