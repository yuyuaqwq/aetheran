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
    # ★ P-27：职业**不兜底**（原先 `player.get("cls") or "cls_knight"` —— 等于替没择业的玩家
    #   挑了个职业，档与面板从这一行起就分家）。没有职业 ⇒ `panel_build` 当场抛 `PanelMissing`
    #   （生命上限只有一个来源：职业面板）。
    cls = str(player.get("cls") or "")
    lv = int(player.get("level", 1) or 1)
    # ★ 装备与强化走唯一取值口（B2-6，`panel_build.gear_and_buffs` → `gear` 那两个口）：
    #   `gear_stats` 会按强化等级放大主词条；食物增益走最后一层 mul（时效过了自动失效 ——
    #   时钟是宿主注入的那根）。★ P-27：与「档上的上限」（`panel_build.hp_cap`）吃**同一份**
    #   取值口 ⇒ 面板 / 档 / 战斗 actor 三处同一个数。
    gear, buffs = PB.gear_and_buffs(player)
    a = PB.build_actor(cls, lv, player.get("alloc"), gear, buffs=buffs, stack_prefix=stack_prefix)
    a["uid"] = str(player.get("uid") or "p1")
    a["name"] = player.get("name") or "无名者"
    a["side"] = PLAYER_SIDE
    a["kind"] = "player"
    a["human_controlled"] = True
    a["level"] = lv
    # ★ 实时血量必给（引擎读 a["hp"]，缺了会拿 max_hp 当当前值）
    #   ★ P-27：钳制用的上限就是**面板算出来的那一个**（`a["max_hp"]`）—— 现血来自同一份档
    #     （`cmds_ast._p` 已按同一个上限钳过）⇒ 不再「档上写死 100 压住面板 116」那种两个源混用。
    if not isinstance(a.get("max_hp"), (int, float)) or isinstance(a.get("max_hp"), bool):
        raise PB.PanelMissing("面板没给出生命上限（max_hp · 职业数据少了 hp？）：%r"
                              % (a.get("class_name"),))
    mx = int(a["max_hp"])
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


def pick_encounter(monsters: dict, loc: str, node: str, level: int, *, seed: int | None = None,
                   mul: dict | None = None):
    """从怪里挑一只「这一带、这个等级」的（第一版：按等级最近 + 可复现随机）。

    ★ P-30：地点**真的参与挑选**了 —— 每条怪在 monsters 域里挂着 `habitat`：
      `maps` = 会出现的图（必给，空 = 哪儿都不出）；`nodes` = 再收窄到这几个节点
      （可选 / 空 = 该图任意节点）。先按图筛（给了 nodes 再按节点筛），再按等级最近挑。
      **候选为空就返回 `[]`，不兜底**：村镇是安全区，指令那边会回「这一带暂时没有遇到什么」。

    ★ B3-7：**档位不再当门**（原先只放 普通/精英/头目 ⇒ 号角室的层主房与塔顶那两间**一只都
      挑不出来**：敲『攻击』只回「这一带暂时没有遇到什么」）。现在**唯一的门是 `habitat`**
      —— 地点说得上话的怪就能碰上（层主 / Boss 也是怪）。这么改有三条好处：
        · 档位这一栏不再是代码里的机器键（P-20 第二刀的方向：取值全从域里来）；
        · 野外不会多出怪 —— 层主与 Boss 的 `habitat` 只写着旧哨塔那两张节点，图/节点对不上的
          一律不是候选（`probe_monsters` ⑨⑩ 钉着这一条）；
        · 要收窄哪个档位，让它自己的 `habitat` 说话（数据层决定，不在这里加白名单）。

    ★ B3-5：`mul` = 现在开场事件给的遇敌加权（`{怪 id: 倍数}`，来源 `calendar.encounter_mul`）。
      **没给 = 零变化**（还是 `choice` 那一支，同一个种子挑出同一只 —— 判据钉着这一条）；
      给了就按权重挑（倍数为 0 的候选天然挑不中）。
    """
    cand = []
    for k, m in monsters.items():
        hb = m.get("habitat") or {}
        if loc not in (hb.get("maps") or []):
            continue                                  # ★ 不属于这张图的怪，一律不出现
        ns = hb.get("nodes") or []
        if ns and node not in ns:
            continue                                  # ★ 收窄到节点
        cand.append(k)
    if not cand:
        return []                                     # ★ 不兜底（村镇 / 没挂怪的图）
    cand.sort(key=lambda k: abs(int(monsters[k].get("lv", 1)) - level))
    top = cand[:3]
    rnd = random.Random(seed)
    if not mul:
        return [rnd.choice(top)]                      # ★ 没给 = 与改前逐字相同
    weights = [max(0, int(mul.get(k, 1) or 0)) for k in top]
    if sum(weights) <= 0:
        return [rnd.choice(top)]
    return [rnd.choices(top, weights=weights, k=1)[0]]
