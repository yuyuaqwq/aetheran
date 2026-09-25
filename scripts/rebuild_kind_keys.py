# -*- coding: utf-8 -*-
"""items / drop_pools 的**机器键**落法（`kind` 中文枚举 → ASCII `kind_key`）—— B3-6b-2d-keys-2。

为什么要有它（P-20 甲案第二刀 · K48 / K51）：
  代码原先**拿域里的中文枚举当机器键**（`loot.kind_of` 的兜底「材料」· 嵌套池判「池」·
  未鉴定判「未鉴定」· `codex` 的四本谱归属 6 处）—— 一字之差就静默挑不出东西。
  本批把机器键收成 ASCII：**域里每条记录多一格 `kind_key`**，代码只比 ASCII。

口径（与 `quests.chain` / `gathering.verb` / 第一刀的 `slot` 同款）：
  · 中文 `kind` **保留**（它是玩家看得见的分类名 / 策划案原文的写法）
  · ASCII `kind_key` 是**机器键**（代码只认它）—— 本文件里那张表是它的**唯一来源**
  · 映射表必须与 `schemas/items.schema.json` / `schemas/drop_pools.schema.json` 的 enum 逐字一致
    （`probe_items` ⑧ 与 `probe_drops` ⑭ 两头对账 —— 表漂了、schema 漂了、数据漂了都能抓出来）
  · ★ 生成器侧允许引中文（它解析的是策划案原文）；运行时 `content/*.py` **一个字都不许引**
    （判据 = `scripts/probe_copy.py` ⑮「中文枚举当机器键」必须 0 处）

用法：
  python scripts/rebuild_kind_keys.py --dry     # 只打印，不写（看「要补几处、有没有对不上」）
  python scripts/rebuild_kind_keys.py           # 写（连跑两次数据逐字节不变 = 幂等）
"""
from __future__ import annotations

import io
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "content", "data")

#: ★ items 的 `kind`（12 类）→ ASCII `kind_key`。
#:   装备那六类**与 `slot` 同值**（第一刀已经把装备的机器键收成 `slot`；这里只是把整张表补齐，
#:   让「items 的机器键」在全域上**全函数**——装备 `kind_key == slot`，非装备 6 类各有各的键）。
ITEM_KIND_KEY = {
    "武器": "weapon",
    "上甲": "armor_top",
    "下甲": "armor_bottom",
    "头盔": "helmet",
    "靴子": "boots",
    "饰品": "accessory",
    "材料": "material",
    "食物": "food",
    "道具": "tool",
    "垃圾": "junk",
    "信物": "keepsake",
    "线索": "clue",
}

#: ★ drop_pools 的 `kind`（顶层未鉴定 + 条目那一层）→ ASCII `kind_key`。
#:   条目里那 5 个（材料 / 道具 / 垃圾 / 信物 / 线索）与 items 的键**同值**（一个词表两处用）；
#:   `pool`（嵌套池）/ `gear`（动态装备）/ `unidentified`（未鉴定）是池侧独有的三个键。
POOL_KIND_KEY = {
    "池": "pool",
    "装备": "gear",
    "材料": "material",
    "道具": "tool",
    "垃圾": "junk",
    "信物": "keepsake",
    "线索": "clue",
    "未鉴定": "unidentified",
}

#: 顶层带 `kind` 的池（未鉴定那两个）用哪张表 —— 与条目同一张（`未鉴定` → `unidentified`）
TOP_KIND_KEY = POOL_KIND_KEY


def _rd(name: str):
    with io.open(os.path.join(DATA, name + ".json"), encoding="utf-8") as f:
        return json.load(f)


def _wr(name: str, obj) -> None:
    with io.open(os.path.join(DATA, name + ".json"), "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def _key_of(table: dict, kind, where: str) -> str:
    """中文 kind → ASCII 键。表里没有 ⇒ **当场抛**（不猜、不静默兜底）。"""
    if not isinstance(kind, str) or kind not in table:
        raise SystemExit("%s 的 kind=%r 不在映射表里（新取值要先补表 + 补 schema enum）" % (where, kind))
    return table[kind]


def _place_after(rec: dict, anchor: str, key: str, value) -> None:
    """把 `key` 插在 `anchor` 后面（就地改）—— 机器键紧挨着它对应的中文枚举，读数据的人一眼看见两格。"""
    out = {}
    for k, v in rec.items():
        out[k] = v
        if k == anchor:
            out[key] = value
    if key not in out:                      # anchor 不在（不该发生）⇒ 兜在末尾，不丢字段
        out[key] = value
    rec.clear()
    rec.update(out)


def _fill(rec: dict, table: dict, where: str, hits: list) -> None:
    """一条记录：`kind` → `kind_key`（缺就补；已有但不一致 ⇒ 当场抛，不静默覆盖）。"""
    kind = rec.get("kind")
    if kind is None:
        return
    want = _key_of(table, kind, where)
    have = rec.get("kind_key")
    if have is None:
        _place_after(rec, "kind", "kind_key", want)
        hits.append("%s +%s" % (where, want))
    elif have != want:
        raise SystemExit("%s 的 kind_key=%r 与映射表(%s→%s)对不上（先弄清哪个是对的）"
                         % (where, have, kind, want))


def plan() -> tuple:
    """算出「要补哪些」—— dry 与写盘走**同一套**判定。"""
    items = _rd("items")
    pools = _rd("drop_pools")
    hits: list = []
    for iid, v in items.items():
        if str(iid).startswith("_"):
            continue
        _fill(v, ITEM_KIND_KEY, "items.%s" % iid, hits)
    for pid, v in pools.items():
        if str(pid).startswith("_"):
            continue
        _fill(v, TOP_KIND_KEY, "drop_pools.%s" % pid, hits)
        for i, e in enumerate(v.get("entries") or []):
            _fill(e, POOL_KIND_KEY, "drop_pools.%s.entries[%d]" % (pid, i), hits)
        for i, e in enumerate(v.get("pool") or []):
            _fill(e, POOL_KIND_KEY, "drop_pools.%s.pool[%d]" % (pid, i), hits)
    return items, pools, hits


def main(argv) -> int:
    dry = "--dry" in argv
    items, pools, hits = plan()
    print("== rebuild_kind_keys ==")
    print("  items  %d 条（机器键表 %d 类）· drop_pools %d 条（池侧表 %d 类）"
          % (len([k for k in items if not str(k).startswith("_")]),
             len(ITEM_KIND_KEY), len([k for k in pools if not str(k).startswith("_")]),
             len(POOL_KIND_KEY)))
    print("  要补 %d 处" % len(hits))
    for h in hits[:20]:
        print("      %s" % h)
    if len(hits) > 20:
        print("      …（还有 %d 处）" % (len(hits) - 20))
    if dry:
        print("  --dry：不写盘")
        return 0
    if not hits:
        print("  无新增（幂等 ✓）")
        return 0
    _wr("items", items)
    _wr("drop_pools", pools)
    print("  写入 items.json · drop_pools.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
