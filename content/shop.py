# -*- coding: utf-8 -*-
"""药铺那一家：货架 · 买价 · 那一站 —— **唯一解析处**（B4-15）。

为什么单开一个模块（与 `content/town.py` / `content/argv.py` / `content/scene.py` 同一个路子）
------------------------------------------------------------
  · 三处要读同一份口径：`cmds_places.herbalist`（药铺面板）· `cmds_more.item_buy`（购买）
    · `scripts/probe_shop.py`（逐行对账）—— 放下面的模块会被另外两处 import 成环；
  · **代码里没有价、没有 id、没有节点名**：四个品阶系数 + 固定加价在 `content/rules/shop.json`
    （`scripts/rebuild_shop.py` 从真源 `06_…/00_第一阶段内容总纲_v1.md §六` 现解析进来的；
    加价那一格真源没给数 —— 取值理由与出处写在那个脚本的头注里），
    货架由 items 域的 `kind_key` 现取，那一站由 npcs 域的 `funcs` 现取；
  · 只 import 基座 `cmds_ast`（TOWN / _data）与 `content/town.py`，**不被它们 import**
    ⇒ 谁都能用、怎么排 import 都不成环。
"""
from __future__ import annotations

import io
import json
import os

from .cmds_ast import TOWN, _data, _name_of_node
from . import calendar as CAL
from . import loot as LT
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


def price_of(rec: dict, p=None, mul=None) -> int:
    """买价 = 基础价 × 品阶系数 × 固定加价 × **物价倍数**（真源 05 §六 + 口径表 + 事件层），取整到 1。

    品阶取条目的 `quality`；没写的一律按「普通」（`quality_default`，口径 §二②）。
    认不出的品阶 ⇒ **当场喊**（fail-closed，不静默当 0 —— K68）。
    ★ P-55：加价那一格（`buy_markup`）真源没给数（05 §六 只给「价 = 基础价 × 品阶系数」）⇒
      台账的倾向是「例：买价 = 收价 × 2」；普通档系数 1.00 ⇒ 正好是「买价 = 收价 × 2」
      （收价 = `items.price`，B3-12 落的那一路，一个字不动）。缺格 / 烂值 = 抛（fail-closed：
      没有它买价就退回等于收价，「低买高卖」那条路又开了）。
    ★ P-16：**物价倍数**接在这一格里 —— 世界事件效果栏 `price_mul`（如 1.2 = 「价格 +20%」，
      真源 21 §二）走事件层的唯一口 `calendar.price_mul`；今天数据里一条都没给 ⇒ 1.0
      （买价与改前逐字相同）。★ `p` 要传（世界级事件看主线进度）；`mul` 传了就用它
      （同一眼货架上的价得用**同一刻**的倍数 —— 由 `goods` / `find` 算一次传下来）。
    ★ 买价**永远 ≥ 收价**：算完再核一遍（口径 / 数据错了当场喊，不静默放一条刷钱的路过去）。
    """
    r = rules()
    mult = r.get("quality_mult") or {}
    mark = r.get("buy_markup")
    if isinstance(mark, bool) or not isinstance(mark, (int, float)) or mark < 1:
        raise RuntimeError("铺子口径表缺「固定加价」或不是 ≥1 的数：%r（%s）" % (mark, RULES))
    q = str((rec or {}).get("quality") or r.get("quality_default") or "")
    if q not in mult:
        raise RuntimeError("品阶 %r 不在铺子口径表里（%s）" % (q, sorted(mult)))
    base = float((rec or {}).get("price") or 0)
    pm = CAL.price_mul(p=p) if mul is None else float(mul)
    gold = int(round(base * float(mult[q]) * float(mark) * pm))
    if gold < int(base):
        raise RuntimeError("买价 %d 比收价 %d 还低 —— 铺子被刷了（口径 / 数据 / 物价倍数错了）"
                           % (gold, int(base)))
    return gold


def goods(p=None) -> list:
    """柜上有什么 —— `[{"id", "rec", "gold"}, …]`（按 items 域自己的顺序，不重排）。

    货架 = 域里 `kind_key == stock_kind` 且**有价**的那些（口径 §二①）。
    `gold` = 买价（基础价 × 品阶系数 × 固定加价 × 物价倍数 —— 与『购买』扣的是同一个数）。
    ★ P-16：物价倍数**算一次**传下去（同一眼货架上的价必须是同一刻的；`p` 要传 ——
      世界级事件看主线；不传 = 按「没有世界级事件」算，调用方别这么干）。
    """
    kind = str(rules().get("stock_kind") or "")
    pm = CAL.price_mul(p=p)
    out = []
    for iid, rec in (_data("items") or {}).items():
        if str(iid).startswith("_") or not isinstance(rec, dict):
            continue
        if rec.get("kind_key") != kind or not rec.get("price"):
            continue
        out.append({"id": iid, "rec": rec, "gold": price_of(rec, mul=pm)})
    return out


def find(name, p=None) -> tuple:
    """柜上按名字 / id 找一件 —— `(id, rec, gold, cands)`；找不到 `(None, {}, 0, [])`。

    ★ B4-20：比法走**全包唯一的一口** `loot.match_ids`（原先这里自己写了一份「遍历序里
      第一个命中的就算」）。`cands` 非空 = 柜上有**好几件同一个名字** ⇒ 调用方照实说，
      不替玩家挑（今天柜上那两件名字不重，但这一格归了口就不会再各自跑偏）。
    ★ P-16：`p` 一路传给 `goods`（物价倍数按这一档的事件算 —— 与面板同一眼同一个价）。
    """
    shelf = goods(p)
    hits = LT.match_ids([g["id"] for g in shelf], name)
    if len(hits) > 1:
        return (None, {}, 0, sorted(hits))
    if not hits:
        return (None, {}, 0, [])
    g = next(x for x in shelf if x["id"] == hits[0])
    return (g["id"], g["rec"], g["gold"], [])


def station_name(loc: str = TOWN) -> str:
    """那一站**给玩家看**的名字（从 maps 现取，不写死）。"""
    return str(_name_of_node(loc, station(loc)) or "")
