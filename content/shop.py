# -*- coding: utf-8 -*-
"""药铺那一家：货架 · 买价 · 那一站 —— **唯一解析处**（B4-15）。

为什么单开一个模块（与 `content/town.py` / `content/argv.py` / `content/scene.py` 同一个路子）
------------------------------------------------------------
  · 三处要读同一份口径：`cmds_places.herbalist`（药铺面板）· `cmds_more.item_buy`（购买）
    · `scripts/probe_shop.py`（逐行对账）—— 放下面的模块会被另外两处 import 成环；
  · **代码里没有价、没有 id、没有节点名**：四个品阶系数在 `content/rules/shop.json`
    （`scripts/rebuild_shop.py` 从真源 `06_…/00_第一阶段内容总纲_v1.md §六` 现解析进来的），
    货架由 items 域的 `kind_key` 现取，那一站由 npcs 域的 `funcs` 现取；
  · 只 import 基座 `cmds_ast`（TOWN / _data）与 `content/town.py`，**不被它们 import**
    ⇒ 谁都能用、怎么排 import 都不成环。
"""
from __future__ import annotations

import io
import json
import os

from .cmds_ast import TOWN, _data, _name_of_node
from . import town as TW

RULES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules", "shop.json")

_CACHE = None


def rules() -> dict:
    """`content/rules/shop.json`（唯一真源）—— 读一次，进程内复用。"""
    global _CACHE
    if _CACHE is None:
        if not os.path.exists(RULES):
            raise RuntimeError("铺子口径表不在：%s（跑 scripts/rebuild_shop.py）" % RULES)
        with io.open(RULES, encoding="utf-8") as f:
            _CACHE = json.load(f)
        if not isinstance(_CACHE, dict) or not _CACHE.get("quality_mult"):
            raise RuntimeError("铺子口径表形状不对：%s" % RULES)
    return _CACHE


def station(loc: str = TOWN) -> str:
    """药铺那一站（节点 id）—— 叫不准（分在两处 / 一个都没有）就给空串。

    ★ 空串 = **拦**（`town_gate` 的 fail-closed 语义）：不假装自己在柜台上。
    """
    return TW._func_node(str(rules().get("station_func") or ""), loc)


def price_of(rec: dict) -> int:
    """买价 = 域里的基础价 × 品阶系数（真源 05 §六），取整到 1。

    品阶取条目的 `quality`；没写的一律按「普通」（`quality_default`，口径 §二②）。
    认不出的品阶 ⇒ **当场喊**（fail-closed，不静默当 0 —— K68）。
    """
    r = rules()
    mult = r.get("quality_mult") or {}
    q = str((rec or {}).get("quality") or r.get("quality_default") or "")
    if q not in mult:
        raise RuntimeError("品阶 %r 不在铺子口径表里（%s）" % (q, sorted(mult)))
    return int(round(float((rec or {}).get("price") or 0) * float(mult[q])))


def goods() -> list:
    """柜上有什么 —— `[{"id", "rec", "gold"}, …]`（按 items 域自己的顺序，不重排）。

    货架 = 域里 `kind_key == stock_kind` 且**有价**的那些（口径 §二①）。
    """
    kind = str(rules().get("stock_kind") or "")
    out = []
    for iid, rec in (_data("items") or {}).items():
        if str(iid).startswith("_") or not isinstance(rec, dict):
            continue
        if rec.get("kind_key") != kind or not rec.get("price"):
            continue
        out.append({"id": iid, "rec": rec, "gold": price_of(rec)})
    return out


def find(name) -> tuple:
    """柜上按名字 / id 找一件 —— `(id, rec, gold)`；找不到 `(None, {}, 0)`。

    比法照仓里现成的惯例（`cmds_more._bag_hit` / `cmds_recipe._item_of_name`）：
    id 或全名相等，或者（名字 ≥ 2 字）是名字的一部分。
    """
    want = str(name or "").strip()
    if not want:
        return (None, {}, 0)
    for g in goods():
        rec = g["rec"]
        nm = str(rec.get("name") or "")
        if want == g["id"] or (nm and (want == nm or (len(want) >= 2 and want in nm))):
            return (g["id"], rec, g["gold"])
    return (None, {}, 0)


def station_name(loc: str = TOWN) -> str:
    """那一站**给玩家看**的名字（从 maps 现取，不写死）。"""
    return str(_name_of_node(loc, station(loc)) or "")
