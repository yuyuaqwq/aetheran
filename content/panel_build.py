# -*- coding: utf-8 -*-
"""面板构造（内容侧）—— 把 (职业, 等级, 加点) 算成引擎 PanelStack 要的声明。

★ 分工：本文件只负责「准备每层的数」；逐键合并 / 钳制 / 归因由引擎形状 `PanelStack` 做。
★ 引擎键名映射也在这里（宪法名 → 战斗侧认的名字），crit 要率化（引擎的 crit 是率，不是数值）。
"""
from __future__ import annotations

import json
from pathlib import Path

_DATA = Path(__file__).resolve().parent / "data"
_CLASSES = None

K_DEF, K_RATE = 300, 500

KEYMAP = {
    "hp": "max_hp", "mo": "max_mp", "atk": "atk", "matk": "matk", "def": "def",
    "res": "mdef", "spd": "spd", "hit": "hit", "eva": "dodge", "block": "block",
    "heal_pow": "heal_pow", "critdmg": "crit_dmg",
}
INT_KEYS = ("max_hp", "max_mp")

_REGISTRY: dict = {}          # 栈 id → decl（panel_layers_fn 的供体）


def classes() -> dict:
    global _CLASSES
    if _CLASSES is None:
        _CLASSES = json.loads((_DATA / "classes.json").read_text(encoding="utf-8"))
    return _CLASSES


def panel_of(cls_id: str, level: int, alloc: dict | None = None) -> dict:
    """宪法键名的面板：基础 + 成长×(级-1) + 加点换算。"""
    c = classes()[cls_id]
    p = dict(c["base"])
    for k, v in c["growth"].items():
        p[k] = p.get(k, 0) + v * (level - 1)
    for stat, n in (alloc or {}).items():
        for k, v in (c["conv"].get(stat) or {}).items():
            p[k] = p.get(k, 0) + v * n
    return p


def to_engine(p: dict) -> dict:
    """宪法键名 → 引擎键名；crit 数值 → 率（引擎的 crit 是率）。

    闪避不做率化：宪法 F2 是 hit/(hit+eva) 对冲式，落点在战斗侧（下一刀）。
    """
    out = {}
    for k, v in p.items():
        if k == "crit":
            out["crit"] = v / (v + K_RATE)
            continue
        if k == "critdmg":
            out["crit_dmg"] = v
            continue
        if k in KEYMAP:
            out[KEYMAP[k]] = v
    return out


def _layers_of(cls_id: str, level: int, alloc: dict | None):
    """三层**数值**键（不含 crit）：职业基础 / 成长 / 加点。crit 单独走 set 层（率化）。"""
    c = classes()[cls_id]
    base = dict(c["base"])
    grow = {k: v * (level - 1) for k, v in c["growth"].items()}
    attr: dict = {}
    for stat, n in (alloc or {}).items():
        for k, v in (c["conv"].get(stat) or {}).items():
            attr[k] = attr.get(k, 0) + v * n
    drop = ("crit",)
    return (to_engine({k: v for k, v in base.items() if k not in drop}),
            to_engine({k: v for k, v in grow.items() if k not in drop}),
            to_engine({k: v for k, v in attr.items() if k not in drop}))


def build_actor(cls_id: str, level: int, alloc: dict | None = None,
                equipment: dict | None = None, *, stack_prefix: str = "aetheran") -> dict:
    """造一个玩家 actor：自带 panel_stack（栈 id）与战斗侧字段。"""
    base_e, grow_e, attr_e = _layers_of(cls_id, level, alloc)
    gear_e = {KEYMAP.get(k, k): v for k, v in (equipment or {}).items()}

    p = panel_of(cls_id, level, alloc)
    crit_rate = p["crit"] / (p["crit"] + K_RATE)       # 宪法 F3：数值 → 率（引擎的 crit 是率）

    sid = "%s.%s@%d" % (stack_prefix, cls_id, level)
    keys = sorted(set(base_e) | set(grow_e) | set(attr_e) | set(gear_e))
    _REGISTRY[sid] = {
        "version": 1,
        "base": {"mode": "value", "value": {k: 0 for k in keys + ["crit"]}},
        "layers": [
            {"id": "prof_base", "src": "职业基础", "group": "base", "mode": "add",
             "keys": keys, "values": {k: base_e.get(k, 0) for k in keys}},
            {"id": "growth", "src": "等级成长", "group": "base", "mode": "add",
             "keys": keys, "values": {k: grow_e.get(k, 0) for k in keys}},
            {"id": "attr", "src": "主属性加点", "group": "attr", "mode": "add",
             "keys": keys, "values": {k: attr_e.get(k, 0) for k in keys}},
            {"id": "gear", "src": "装备", "group": "gear", "mode": "add",
             "keys": keys, "values": {k: gear_e.get(k, 0) for k in keys}},
            # crit 是非线性率（F3），三层相加无意义 ⇒ 内容侧算好后用 set 层一次性写入
            {"id": "crit_rate", "src": "暴击率（F3 换算）", "group": "rate", "mode": "set",
             "keys": ["crit"], "values": {"crit": crit_rate}},
        ],
        "emit": {"int_keys": [k for k in INT_KEYS if k in keys], "round": 4},
    }
    actor = {k: sum((base_e, grow_e, attr_e, gear_e)[i].get(k, 0) for i in range(4)) for k in keys}
    actor.update({
        "class_name": cls_id,
        "level": level,
        "panel_stack": sid,
        "panel_refs": {},
        "panel_flags": {},
    })
    return actor


def stacks() -> dict:
    """panel_layers_fn 的供体：栈 id → decl。"""
    return _REGISTRY
