# -*- coding: utf-8 -*-
r"""生成器：给每条可见声明补「触发词单独出现」的那一条 pattern（B4-13）。

为什么要有它
------------------------------------------------------------------
`content/data/commands.json` 的 patterns 一律要求**至少一个字符的参**（`^强化\s*(.+)$`）
⇒ 玩家照着「帮助」里写的词念出指令名**本身**（`强化` / `接` / `使用` / `集火` …）时，
**没有任何一条声明命中**，落到宿主那句引擎内置的兜底：

    （没有命中包内任何指令声明；输入 /help 看宿主命令）

—— 引擎内部句 + 一个本服不存在的宿主命令（`/help`），两句都不该给玩家看。
B4-10 已经把「单字别名被当成参」那四条（装备 / 丢弃 / 卖出 / 学习）收口了，可那四条的
**首字恰好是单字别名**（`^装\s*(.+)$` 咬到「装备」）⇒ 只是巧合命中；其余二十几条
（`^强化\s*(.+)$` 这类没有单字别名的）一律落空。K71 那一族的第 2 刀。

做法
------------------------------------------------------------------
取每条可见声明的每个 pattern 的**字面量前缀**（`content/argv.py::lit_prefix` —— 取参那一支
用的同一个口，不另写一份「怎么剥前缀」），那个词**单独出现**时必须命中某条可见声明；
没命中就给它自己补一条 `^<词>$`。补上以后 handler 走 `argv.arg_of` 取到的参是空串
⇒ 各自回「没带参」那一句（B4-10 立的规矩：事实先分清）。

幂等：已有的 `^<词>$` 不重复加；连跑两遍数据不变。
字节级：原序 + `indent=2` + 末尾一个换行 + LF（K27 / K52）。
用法：python scripts/rebuild_bare_patterns.py [--dry]
"""
from __future__ import annotations

import io
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENG = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, REPO)
sys.path.insert(0, ENG)

from content.argv import lit_prefix                        # noqa: E402  取前缀的唯一口
from saintess_engine.command.registry import CommandRegistry   # noqa: E402

PATH = os.path.join(REPO, "content", "data", "commands.json")
DRY = "--dry" in sys.argv


def dump(table: dict) -> str:
    """照原文件的写法回写：原序 + indent=2 + 末尾换行（K52）。"""
    return json.dumps(table, ensure_ascii=False, indent=2) + "\n"


def read() -> tuple:
    with io.open(PATH, encoding="utf-8") as f:
        text = f.read()
    return json.loads(text), text


def words(table: dict) -> dict:
    """声明的每个 pattern 的字面量前缀 → {词: [声明 key, …]}（原序）。

    ★ **不可见的声明也一起收**：不可见的那条与它的可见孪生**必须逐字同形**
      （`battle_item` ↔ `item_use`；判据 = `probe_cmds` ③）—— 只补一边就把那一对拆了。
    """
    out: dict = {}
    for key, spec in table.items():
        if not isinstance(spec, dict):
            continue
        for pat in (spec.get("patterns") or []):
            w = lit_prefix(pat)
            if w:
                out.setdefault(w, []).append(key)
    return out


def misses(table: dict) -> list:
    """裸敲这个字面量前缀，没有任何可见声明接住的那些（原序）。"""
    reg = CommandRegistry(name="bare").load(table)
    bad = []
    for w, owners in words(table).items():
        if reg.first_hit(w, visible_only=True) is None:
            bad.append((w, owners))
    return bad


def is_bare(pat: str) -> bool:
    """这条 pattern 就是「触发词单独出现」那一条（`^强化$`）—— 除了首尾锚点没有别的东西。"""
    s = str(pat or "")
    return s == "^" + lit_prefix(s) + "$" and bool(lit_prefix(s))


def main() -> int:
    table, before = read()
    added, first = [], misses(table)
    for w, owners in first:
        for key in owners:
            pats = table[key].setdefault("patterns", [])
            bare = "^" + w + "$"
            if bare in pats:
                continue
            pats.append(bare)
            added.append((key, w))
    # ★ 不可见孪生必须与可见那条**逐字同形**（`battle_item` ↔ `item_use`；判据 probe_cmds ③）——
    #   判孪生看「去掉裸触发词那几条之后的 patterns」，然后把可见那条的整份原样抄过去。
    for ik, ispec in table.items():
        if not isinstance(ispec, dict) or ispec.get("visible", True) is not False:
            continue
        ibase = [p for p in (ispec.get("patterns") or []) if not is_bare(p)]
        for vk, vspec in table.items():
            if not isinstance(vspec, dict) or vspec.get("visible", True) is False:
                continue
            vbase = [p for p in (vspec.get("patterns") or []) if not is_bare(p)]
            if ibase and ibase == vbase:
                ispec["patterns"] = list(vspec.get("patterns") or [])
                break
    left = misses(table)
    if left:
        raise SystemExit("补完之后仍落空：%s" % (left,))
    body = dump(table)
    if body == before:
        print("无改动（幂等）：%d 条可见声明 · 字面量前缀 %d 个 · 落空 0"
              % (len([1 for v in table.values() if v.get("visible", True) is not False]),
                 len(words(table))))
        return 0
    if DRY:
        print("[dry] 会补 %d 条裸触发词 pattern：%s" % (len(added), ", ".join(
            "%s->^%s$" % (k, w) for k, w in added)))
        return 0
    with io.open(PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    print("补了 %d 条：%s" % (len(added), ", ".join("%s->^%s$" % (k, w) for k, w in added)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
