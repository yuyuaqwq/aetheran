# -*- coding: utf-8 -*-
"""装备 / 强化 / 食物增益 → 面板的唯一取值口（B2-6）。

三个出口，别处不许自己去翻 `equipped` / `enhance` / `food_buff`：

  · `gear_stats(player)` —— 已装备每件 → 面板数值。**主词条**（`affixes[0]`）吃强化加成。
    口径真源：旧案 `06_装备道具/00_装备体系与PE预算.md §7.2`
    `装备PE × (1 + 0.004 × 强化等级)` ⇒ +10 = +4%（旧案纪律：不许「+10 = 换一个装等」）
  · `enhance_bonus(player, item_id)` —— 那件装备当前的强化加成（比例，0 = 没强化）
  · `food_buff(player)` —— 吃下去的菜还在时效内 → `{面板键: 乘数}`（引擎面板栈的 mul 层）

★ 效果类词条（reflect / stun_immune / auto_cleanse 那类）**不参与强化** —— 它们是规则不是数值。
"""
from __future__ import annotations

from . import facade

#: 菜里写的增益名 → 引擎面板键（三种：攻击 / 防御 / 生命上限）
BUFF_KEY = {"atk": "atk", "def": "def", "hp": "max_hp"}


def _items():
    from .cmds_ast import _data
    return _data("items")


def enhance_bonus(player, item_id) -> float:
    """那件装备当前的强化加成（比例）。档上没有 = 0。"""
    e = (player.get("enhance") or {}).get(str(item_id)) or {}
    try:
        return max(0.0, float(e.get("bonus") or 0.0))
    except (TypeError, ValueError):
        return 0.0


def gear_stats(player) -> dict:
    """已装备的东西 → 面板数值（主词条 × 强化加成，其余词条原样）。"""
    out: dict = {}
    for _slot, iid in (player.get("equipped") or {}).items():
        rec = _items().get(iid) or {}
        for i, a in enumerate(rec.get("affixes") or []):
            v = a.get("v")
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                continue
            v = float(v)
            if i == 0:
                v = v * (1.0 + enhance_bonus(player, iid))
            out[a.get("stat")] = round(out.get(a.get("stat"), 0.0) + v, 4)
    return out


def food_buff(player) -> dict:
    """吃下去的菜还在时效内 → `{面板键: 乘数}`（引擎面板栈的 mul 层）。

    过期 = 自动失效（时间源 = 宿主注入的钟，不自己取系统时间）。
    """
    fb = player.get("food_buff") or {}
    if not isinstance(fb, dict) or not fb:
        return {}
    try:
        until = float(fb.get("until") or 0)
        pct = int(fb.get("pct") or 0)
    except (TypeError, ValueError):
        return {}
    if until <= float(facade.clock()) or pct <= 0:
        return {}
    key = BUFF_KEY.get(str(fb.get("stat")))
    return {key: 1.0 + pct / 100.0} if key else {}
