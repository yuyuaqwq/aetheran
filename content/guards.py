# -*- coding: utf-8 -*-
"""包侧守卫钩子（引擎 `run_guards` 的 `hook:<名>` 通道）。

声明：`content/data/commands.json` 的 `guards: ["hook:register"]`（建号三件套与
`观察` 不挂）。契约：`fn(env, player) -> str | None`（非空 = 拦截回话，已渲染文案）。

★ 2026-09-30（注册面改造）：`register` 守卫 —— **建号没走完**的玩家敲别的指令时，
  不让他撞一鼻子「背包是空的」这种冷板凳，先按他走到哪一步给指引：
  没定族 → 短引导（全屏开场归 `观察` 那条路）；定了族 → 差职业；定了职业 → 差名字。
  引擎的内置 `player` 守卫只管「档案在不在」（新玩家进镇前就建档了），
  「注册走没走完」这层判断属内容侧 —— 就落在这里。
"""
from __future__ import annotations


def guard_register(env, player):
    """建号没走完 → 拦截并给「下一步」引导（走完 → None 放行）。"""
    from .cmds_ast import T          # 本地 import：装载期成环防护（同 commands.py 惯例）
    p = player or {}
    if not p.get("race"):
        return T("SYS_GUARD_REGISTER")
    if not p.get("cls"):
        return T("SYS_GUARD_CLS")
    if not str(p.get("name") or "").strip():
        return T("SYS_GUARD_NAME")
    return None


GUARDS = {
    "register": guard_register,
}
