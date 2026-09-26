# -*- coding: utf-8 -*-
r"""生成器：把 `maps` 域里的**节点名**写成 `go_to`（『去 <地方>』）的别名 pattern（fix5-nav）。

为什么要有它
------------------------------------------------------------------
四个真人玩家里有**三个**独立撞上同一件事（P1 BUG-12 / P2 BUG① / P3 体验）：

    屏幕把地点名用『』写出来（`观察` 的「往哪走：『老风车』『东口』…」、
    `进镇` 的「能去的地方：…『北口』」，野外 9 个节点全中），
    玩家照着敲 —— 一律「「老风车」这句我没接住」，只有 `去 老风车` 才行。

⇒ 口径（主线拍定）：**屏幕上写出来的地点名，敲下去就等于 `去 <名>`**（镇内 + 野外都生效），
   `去 <名>` 照旧保留。别名走**引擎现成的那套**（声明表 `patterns` 里多写几条正则 =
   别名，见 `saintess_engine/command/spec.py` 的表结构说明），不另造一套名字表。

做法
------------------------------------------------------------------
① 名字的真源 = `content/data/maps.json` 的 `nodes[].name`（**不手抄一份**：五个图的节点名
   都从那儿现读 ⇒ 加了新节点、改了名字，本脚本跟着动）；
② 每个名字在 `go_to.patterns` 里保证有一条 `^<名字>$`（缺就补，有就不动 —— 幂等）；
③ 同一条名字**不许**还是别的声明的裸触发词（那种「一词两义」正是 P1 BUG-11 / P3 体验：
   `北口` 既是站点名又是「出北门」的口令）—— 撞上就**摘掉那一条**并把它印出来，
   规则一句话：**站名归站点**，出门用方向那几条（`往北` / `出北门` / `往东` / `往西`）。
④ fail-closed：补完之后逐个名字用 `CommandRegistry.first_hit(..., visible_only=True)` 现算，
   有一条落不到 `go_to` 上就当场抛（数据坏了不静默）。

字节级：原序 + `indent=2` + 末尾一个换行 + LF（K27 / K52），与 `rebuild_bare_patterns.py` 同一套。
幂等：连跑两遍数据逐字节不变。
用法：python scripts/rebuild_place_alias.py [--dry]
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENG = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, REPO)
sys.path.insert(0, ENG)

from saintess_engine.command.registry import CommandRegistry      # noqa: E402

CMDS = os.path.join(REPO, "content", "data", "commands.json")
MAPS = os.path.join(REPO, "content", "data", "maps.json")
KEY = "go_to"                       # 站名别名挂在哪一条声明上（『去 <地方>』）
DRY = "--dry" in sys.argv


def dump(table: dict) -> str:
    """照原文件的写法回写：原序 + indent=2 + 末尾换行（K27 / K52）。"""
    return json.dumps(table, ensure_ascii=False, indent=2) + "\n"


def read(path: str) -> dict:
    with io.open(path, encoding="utf-8") as f:
        return json.loads(f.read())


def place_names() -> list:
    """五个图上所有节点名（地图序 + 节点序；去重保序）。名字的真源只有 maps 域。"""
    out = []
    for _loc, m in read(MAPS).items():
        for n in (m.get("nodes") or []):
            nm = str(n.get("name") or "").strip()
            if nm and nm not in out:
                out.append(nm)
    return out


def bare(name: str) -> str:
    """这一个名字「单独出现」的那条 pattern（`^老风车$`）。"""
    return "^" + re.escape(name) + "$"


def main() -> int:
    table, before = read(CMDS), io.open(CMDS, encoding="utf-8").read()
    names = place_names()
    added, stolen = [], []
    for nm in names:
        pat = bare(nm)
        for key, spec in table.items():
            if not isinstance(spec, dict):
                continue
            pats = spec.setdefault("patterns", [])
            if key == KEY:
                if pat not in pats:
                    pats.append(pat)
                    added.append((key, nm))
            elif pat in pats:
                # 一词两义：同一条名字还是别人的裸触发词 ⇒ 摘掉（站名归站点）
                pats[:] = [p for p in pats if p != pat]
                stolen.append((key, nm))
    reg = CommandRegistry(name="place_alias").load(table)
    lost = [nm for nm in names if getattr(reg.first_hit(nm, visible_only=True), "key", None) != KEY]
    if lost:
        raise SystemExit("补完之后这些名字落不到 %s 上：%s" % (KEY, lost))
    body = dump(table)
    if body == before:
        print("无改动（幂等）：%d 个节点名 · 全部挂在 %s 上 · 没有一个名字是别人的裸触发词"
              % (len(names), KEY))
        return 0
    if DRY:
        print("[dry] %s 补 %d 条别名：%s" % (KEY, len(added),
                                         ", ".join("^%s$" % w for _k, w in added)))
        print("[dry] 从别的声明摘掉 %d 条裸触发词（真源原词归站点）：%s"
              % (len(stolen), ", ".join("%s->^%s$" % (k, w) for k, w in stolen)))
        return 0
    with io.open(CMDS, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    print("%s 补 %d 条别名：%s" % (KEY, len(added), ", ".join("^%s$" % w for _k, w in added)))
    print("从别的声明摘掉 %d 条裸触发词（站名归站点）：%s"
          % (len(stolen), ", ".join("%s->^%s$" % (k, w) for k, w in stolen)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
