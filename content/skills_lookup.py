# -*- coding: utf-8 -*-
"""《阿斯特兰》技能查询（引擎注入面的供体）—— 技能表 + 怪技能 + 普攻兜底。

引擎的取件口（`saintess_engine/config.py` 的钩子）：
    skill_lookup     模块对象，引擎按属性取 `.skill_info(class_name, key)` / `.skill_by_key(key)`
    monster_skill_fn 怪技能（本包 monsters 域里各怪带的技能）
    basic_skill_fn   职业普攻配置（没带技能时的第一选择）
    basic_fallback   普攻兜底（内容名）

★ 为什么必须有：缺了这三口，引擎 `_index_one_actor` 索引不到技能 ⇒ 玩家/怪「静默空放」，
  实测症状是双方都拿默认技（挑成了「圣光治愈」）打了 2000 条日志还打不完。
"""
from __future__ import annotations

import json
import os

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_C: dict = {}


def _load(name: str):
    if name not in _C:
        with open(os.path.join(_DIR, name + ".json"), encoding="utf-8") as f:
            _C[name] = json.load(f)
    return _C[name]


def skills() -> dict:
    return _load("skills")


def classes() -> dict:
    return _load("classes")


def monsters() -> dict:
    return _load("monsters")


def _norm_class(class_name: str | None) -> str | None:
    """职业名或 id 都收（`骑士` 或 `cls_knight`）。

    ★ B3-6b-2d-b 复核：这是**入参解析**（中文名 → 机器键），不是「拿中文枚举当机器键」——
      与 `cmds_recipe._item_of_name` / `去 <地方>` 同一族（玩家/调用方给的是名字）。
      机器键本身（`owner_class` / actor 的 `class_name`）一律是 ASCII `cls_*`。
    """
    if not class_name:
        return None
    cs = classes()
    if class_name in cs:
        return class_name
    for k, v in cs.items():
        if v.get("name") == class_name:
            return k
    return class_name


def active_kind() -> str:
    """「主动技」这个类别**值** —— 唯一来源 = skills 域（域里 30 条记录共用同一个值）。

    ★ B3-6b-2d-b：这个值既是给人看的词、又是**引擎 `do_skill` 分派**（治疗 / 增益 / 攻击）
      要比对的机器键 ⇒ 代码里不许写死这一份中文枚举（K48 / P-20），只认域里那一份。
    ★ fail-closed：域里一条带 `kind` 的技能都没有 ⇒ **抛**。绝不回空串 ——
      引擎那三处比的是 `kind == _kind("heal")`，而本包没声明 kind 词表（`_kind()` 回 ""），
      空串会让攻击技落进治疗那一支（`ext_combat/battle/actions.py:110`）。
    """
    sk = skills()
    for k in sorted(sk):
        if str(k).startswith("_"):
            continue
        v = sk[k]
        if isinstance(v, dict) and v.get("kind"):
            return str(v["kind"])
    raise KeyError("skills 域里没有带 kind 的技能 —— 拿不到「主动技」那个值")


def skill_info(class_name: str, skill_name: str):
    """技能详情（返回**浅副本** —— 引擎会把返回值放进 actor 的运行时索引，
    战斗内机制会改写它；原样返回表条目 = 一次施放永久改写全表）。"""
    sk = skills()
    cls = _norm_class(class_name)
    key = skill_name
    if key in sk:
        v = sk[key]
        if cls and v.get("owner_class") not in (None, cls):
            return None
        return dict(v)
    for k, v in sk.items():                       # 中文名路
        if v.get("name") == skill_name and (not cls or v.get("owner_class") in (None, cls)):
            return dict(v)
    return None


def skill_by_key(key: str):
    v = skills().get(key)
    return dict(v) if isinstance(v, dict) else None


def monster_skill(key: str):
    """怪技能：本包把怪技挂在 monsters 域的 skills 列表里（当前只给 id，名字即 id）。"""
    for mid, m in monsters().items():
        for sid in (m.get("skills") or []):
            if sid == key:
                return {"name": key, "kind": active_kind(), "power": 1.0, "cd": 0,
                        "owner_monster": mid, "_basic": False}
    return None


def basic_skill_of(class_name: str):
    """职业普攻：本职业 power 最低的那条（没带技能时引擎的第一选择）。

    ★ B3-6b-2d-b：候选只按域里现成的 ASCII `owner_class` 挑（原先还叠了一道
      `kind == "主动"` 的**中文枚举**筛选 —— 「中文枚举当机器键」）。
      等价性由 `scripts/probe_skills.py ⑦` 钉着：域里「有 owner_class」的技能 kind 同值。
    """
    sk = skills()
    cls = _norm_class(class_name)
    if not cls:
        return None
    mine = [(v.get("power", 1.0), k, v) for k, v in sk.items() if v.get("owner_class") == cls]
    if not mine:
        return None
    mine.sort()
    v = dict(mine[0][2])
    v["_basic"] = True
    return v


def skill_level_of(actor: dict, skill_name: str) -> int:
    """技能等级（本包第一版：全按 1）。"""
    return 1 if skill_name else 0


def skill_up(actor: dict, skill_name: str, n: int = 1):
    return None
