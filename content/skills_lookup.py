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
    """职业名或 id 都收（`骑士` 或 `cls_knight`）。"""
    if not class_name:
        return None
    cs = classes()
    if class_name in cs:
        return class_name
    for k, v in cs.items():
        if v.get("name") == class_name:
            return k
    return class_name


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
                m_panel = m.get("panel") or {}
                # ★ 怪技能必须给 expr：否则引擎走「非 expr 分支」，那里读 st["_player_lv"]
                #   而 _monster_base_stats 不产出该字段 ⇒ 报「调用方没给 level」（引擎 fail-closed）
                return {"name": key, "kind": "主动", "power": 1.0, "cd": 0,
                        "expr": "atk * 1.0", "owner_monster": mid, "_basic": False}
    return None


def basic_skill_of(class_name: str):
    """职业普攻：本职业 tier=1 且 power 最低的那条（没带技能时引擎的第一选择）。"""
    sk = skills()
    cls = _norm_class(class_name)
    mine = [(v.get("power", 1.0), k, v) for k, v in sk.items()
            if v.get("owner_class") == cls and v.get("kind") == "主动"]
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
