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

#: 增益名 → 引擎面板键（四种：攻击 / 防御 / 生命上限 / 速度）
#: ★ 本批（P-28）加了 `spd`：`pois` 域那件 POI 的短时增益要的是速度
#:   （「心定下来 ⇒ 脚程快一点」），而 `atk / def / hp` 三档归烹饪
#:   （`05 §三`「攻击 / 防御 / 生命上限三选一」）—— 同档重复 = 换个名字的菜。
#:   `spd` 是引擎真读的面板键（CTB 两次行动的间隔，`probe_panel` 钉着骑士 L10 = 109.0），
#:   进面板最后一层 `mul`。★ 口径与白名单的「为什么」写在 `cmds_ast.POI_BUFF_STATS` 那一处，
#:   两处**必须同步**（判据：`probe_pois` ⑪ 的「两张词表不漂」）。
BUFF_KEY = {"atk": "atk", "def": "def", "hp": "max_hp", "spd": "spd"}


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


def enhance_lv(player, item_id) -> int:
    """那件东西当前的强化档（没强化过 = 0）—— 档上 `enhance.<id>.lv` 那一格。

    ★ 试玩问题 #13（本波）：强化成功之后**三个界面都看不出 +1**（`查看` / `背包` / `属性`
      逐字与强化前一模一样）⇒ 展示处统一走 `shown_badge`，这一格是它唯一的读数口。
    """
    e = (player.get("enhance") or {}).get(str(item_id)) or {}
    try:
        return max(0, int(e.get("lv") or 0))
    except (TypeError, ValueError):
        return 0


def shown_badge(player, item_id) -> str:
    """展示用的强化后缀（`" +1"`；**没强化过 = 空串**）—— 拼法只有这一处（K65）。

    消费端五处（都是「那一档变化要看得见」）：`背包` 那一行 · `查看` 的抬头 ·
    `属性` 的「身上」那一栏 · `装备` 的「你穿上了…」· `卸下` 的「你卸下了…」。
    没强化过 ⇒ 与从前逐字相同（老判据一个字不用动）。
    """
    lv = enhance_lv(player, item_id)
    return " +%d" % lv if lv > 0 else ""


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
            # ★ 审计残余 #29：主词条（首位）吃强化，**效果类永远不吃** —— 原判只看位置
            #   （`i == 0`），docstring 那条「效果类不参与强化」代码并不保证：数据里今天
            #   效果类从不在首位（0 处），把效果类排到首位就会被 ×(1+bonus) 放大。
            #   判别键 = `note`（items schema 注的就是效果类词条：30 个效果 stat 全带、
            #   15 个数值 stat 全不带、无一混用 —— 数据与 schema 双证；不手抄效果名单）。
            if i == 0 and not a.get("note"):
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
