# -*- coding: utf-8 -*-
"""《阿斯特兰》战斗接线（B2-2）—— 包侧唯一出口。

形状在扩展包（`ext_combat`：CTB 调度 / 行动结算 / 效果叠层 / 面板公式），
本文件只做三件事：**造 actor · 组战斗 · 推动**。取值全从本包数据来（面板 / 怪 / 技能）。

★ 第一版范围（有意收窄）：先打通「遇敌 → 自动打完 → 拿日志与结果」。
  轮流制（等玩家输入窗口）+ 技能选择的交互层留到 B2-2b（引擎已支持，见
  `Battle.human_act` / `focus()`；奥兰迪亚的实现在 `content/cmds_instance_router.py`）。
"""
from __future__ import annotations

import random

from ext_combat import Battle
from ext_combat.battle.actors import make_actor

from . import panel_build as PB

PLAYER_SIDE = "player"
ENEMY_SIDE = "enemy"


def player_actor(player: dict, stack_prefix: str = "aetheran") -> dict:
    """玩家档 → 战斗 actor（面板走本包的面板栈）。"""
    cls = player.get("cls") or "cls_knight"
    lv = int(player.get("level", 1) or 1)
    a = PB.build_actor(cls, lv, player.get("alloc"), player.get("equip_stats") or {},
                       stack_prefix=stack_prefix)
    a["uid"] = str(player.get("uid") or "p1")
    a["name"] = player.get("name") or "无名者"
    a["side"] = PLAYER_SIDE
    a["kind"] = "player"
    a["human_controlled"] = True
    a["level"] = lv
    # ★ 实时血量必给（引擎读 a["hp"]，缺了会拿 max_hp 当当前值）
    mx = int(a.get("max_hp") or 1)
    hp = int(player.get("hp") or mx)
    a["hp"] = max(1, min(hp, mx))
    a.setdefault("mp", 0)
    a.setdefault("max_mp", int(a.get("max_mp") or 0))
    # ★ 技能表必给（缺了引擎会挑默认技 —— 实测挑成了「圣光治愈」，双方打不死）
    a["skills"] = list(player.get("skills") or _default_skills(cls))
    return a


def _default_skills(cls_id: str):
    """本职业的技能 id（从 skills 域按 owner_class 挑，按 lv 升序）。"""
    import json
    import os
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "skills.json")
    try:
        with open(p, encoding="utf-8") as f:
            sk = json.load(f)
    except OSError:
        return []
    mine = [(v.get("lv", 1), k) for k, v in sk.items() if v.get("owner_class") == cls_id]
    mine.sort()
    return [k for _, k in mine]


def monster_actor(mid: str, m: dict) -> dict:
    """怪数据（monsters 域）→ 战斗 actor。"""
    panel = dict(m.get("panel") or {})
    panel.setdefault("mp", 0)
    panel.setdefault("max_mp", 0)
    a = make_actor(uid=mid, name=m.get("name", mid), side=ENEMY_SIDE, kind="monster",
                   level=int(m.get("lv", 1) or 1), **panel)
    a["role"] = m.get("role") or "普通"
    a["is_boss"] = (a["role"] == "boss")
    # ★ 引擎算 k_def 要读 `_player_lv`（怪走 _monster_base_stats，不会由面板栈补）
    a["_player_lv"] = float(a.get("level", 1) or 1)
    if m.get("skills"):
        a["skills"] = list(m["skills"])
    return a


def build(player: dict, monster_ids, monsters: dict) -> Battle:
    """组一场战斗：玩家 1 人 vs 指定的怪。"""
    ps = [player_actor(player)]
    es = []
    for i, mid in enumerate(monster_ids):
        m = monsters.get(mid)
        if not m:
            continue
        a = monster_actor(mid, m)
        es.append(a)
    return Battle("monster", sides={PLAYER_SIDE: ps, ENEMY_SIDE: es})


def run_auto(player: dict, monster_ids, monsters: dict, *, seed: int | None = None):
    """★ 第一版主路径：自动打完，返回 (结果, 日志行, 玩家战后血量)。"""
    if seed is not None:
        random.seed(seed)                       # 可复现（探针用）
    b = build(player, monster_ids, monsters)
    logs: list = []
    b.auto_run(logs)
    pa = b.sides[PLAYER_SIDE][0]
    return b.result, [str(x) for x in logs], int(pa.get("hp", 0))


def pick_encounter(monsters: dict, loc: str, node: str, level: int, *, seed: int | None = None):
    """从怪里挑一只「这一带、这个等级」的（第一版：按等级最近 + 可复现随机）。"""
    cand = [k for k, m in monsters.items()
            if m.get("role") in ("普通", "精英", "头目")]
    if not cand:
        return []
    cand.sort(key=lambda k: abs(int(monsters[k].get("lv", 1)) - level))
    top = cand[:3]
    rnd = random.Random(seed)
    return [rnd.choice(top)]
