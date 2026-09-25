# -*- coding: utf-8 -*-
"""镇上那一族：「哪一站」与「在不在那一站」的**唯一解析处**。

为什么单开这个模块（B4-12）
--------------------------
  · `_func_node`（镇上带某职能的人在哪一站）原先在 `cmds_places` 里，可 `cmds_quest` /
    `cmds_more` / `cmds_recipe` 也要用它 —— 而那三个模块 import `cmds_places` 会成环
    （`cmds_places` → `cmds_more` → `cmds_quest`）；
  · `town_gate`（`guard_desc` 写着「在镇上 / 在公会 / 在铺子 / 在客栈」那一族的**唯一执行面**）
    同样要能被上面那几个模块直接 import；
  · 放到基座 `cmds_ast` 里也不行 —— 它要读 `npcs` 域，会撞 `probe_npcs` 那条静态守卫
    （「`cmds_ast.py` 里 `_data("npcs")` 只许 1 处」：列谁在场只能走 `_npcs_here` 一口，K65）。

⇒ 本模块只 import 基座 `cmds_ast`（`TOWN` / `_data` / `_name_of_node` / `T`），**不被它 import**，
  因此谁都能用、怎么排 import 都不成环（与 `content/scene.py` / `content/argv.py` 同一个路子）。
"""
from __future__ import annotations

from .cmds_ast import TOWN, _data, _name_of_node, T

def _func_spots(func: str, loc: str = TOWN) -> dict:
    """这张图上带某个职能的人，按所在节点分组 → `{节点: [(人 id, 记录), …]}`。

    职能键 = `npcs.funcs` 里那几个 ASCII 词（heal / inn / board / smith…）—— 域里现成的一栏，
    不另建一张「哪个指令对哪个人」的表。
    ★ B4-12 从 `cmds_places` 搬到本模块：`cmds_quest` / `cmds_more` / `cmds_recipe` 也要用它，
      而那三个模块 import `cmds_places` 会成环（`cmds_places` → `cmds_more` → `cmds_quest`）。
    """
    out: dict = {}
    for k, v in (_data("npcs") or {}).items():
        if not isinstance(v, dict) or v.get("map") != loc:
            continue
        if func not in (v.get("funcs") or []):
            continue
        out.setdefault(str(v.get("subarea") or ""), []).append((k, v))
    return out


def _func_node(func: str, loc: str = TOWN) -> str:
    """带这个职能的人所在的那一站 —— **叫不准就给空串**（没有 / 分在两处都不猜）。"""
    spots = _func_spots(func, loc)
    return next(iter(spots)) if len(spots) == 1 else ""


def town_gate(p, node=None, notown: str = "SYS_PLACE_NOTOWN", away: str = "SYS_PLACE_AWAY") -> str:
    """「回镇上 / 走到那一站」这一族守卫的**唯一执行面**（`guard_desc`：在镇上 · 在公会 · 在铺子 · 在客栈）。

    返回该回的那一句（空串 = 放行）：
      · 不在镇上 ⇒ `notown`（默认「这几处都在镇上 —— 出了镇就找不到了。」）
      · 在镇上、但没走到那一站 ⇒ `away`（指路）。`node` 三种写法：
          `None` = 这一族**不核**那一站（旧货 / 商队 / 卖出 —— 铺子与歇脚处没有单独一站）；
          节点 id = 必须站到那一站；空串 = 叫不准那一站（也拦 —— fail-closed，不假装在）。

    ★ 为什么收成一个口（B4-12 · 端到端玩出来的真 bug）：同一条 `guard_desc` 原先**两种实现** ——
      客栈 / 教堂 / 旧货 / 登记 / 商队判脚下，而 **公会 / 悬赏 / 看 <编号> / 铁匠铺 一句都不判**：
      实测人站在骨田照样能把挂板墙看个遍、把活接了（同一个位置『登记』回的是「这几处都在镇上」）。
      ⇒ 守卫只许有这一处；谁再自己写一遍 `p["loc"] != TOWN`，`probe_cmds ⑰` 的覆盖面当场红。
    """
    if p.get("loc") != TOWN:
        return T(notown)
    if node is None:
        return ""
    if not node or p.get("node") != node:
        return T(away, name=_name_of_node(TOWN, node))
    return ""
