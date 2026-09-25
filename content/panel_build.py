# -*- coding: utf-8 -*-
"""面板构造（内容侧）—— 把 (职业, 等级, 加点) 算成引擎 PanelStack 要的声明。

★ 分工：本文件只负责「准备每层的数」；逐键合并 / 钳制 / 归因由引擎形状 `PanelStack` 做。
★ 引擎键名映射也在这里（宪法名 → 战斗侧认的名字），crit 要率化（引擎的 crit 是率，不是数值）。
"""
from __future__ import annotations

import json
from pathlib import Path

from .cmds_ast import T     # 文案真源只有 texts 域（B3-6b-2d）：分段名只传槽位

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


class PanelMissing(Exception):
    """档上没有可用的面板 ⇒ 属性 / 生命上限算不出来。

    ★ 不猜数：面板是**唯一来源**（`classes` 域那条职业 + 等级 + 加点 + 装备 + 增益）——
      没有职业就没有面板，宁可当场喊出来，也不许拿 100 / 别人的职业垫上
      （`apply.initial_save` 与 `cmds_ast.DEFAULT_PLAYER` 原先各写死 100 就是这么来的）。
    """


def classes() -> dict:
    global _CLASSES
    if _CLASSES is None:
        _CLASSES = json.loads((_DATA / "classes.json").read_text(encoding="utf-8"))
    return _CLASSES


def cls_rec(cls_id: str) -> dict:
    """职业 id → `classes` 域里那条记录。

    ★ 两种失败都当场抛（fail-closed：`fail-closed-boundaries` §1）：
      空 = 「还没择业」（建号第二步还没落地）· 有值却不在域里 = 「声明错了」（点名 + 列出现有的）。
    """
    cid = str(cls_id or "").strip()
    if not cid:
        raise PanelMissing("档上没有职业（cls 空）—— 没有职业就没有面板，属性 / 生命上限算不出来")
    c = classes().get(cid)
    if c is None:
        raise PanelMissing("职业 %r 不在 classes 域里（有的：%s）"
                           % (cid, " · ".join(sorted(classes()))))
    return c


def panel_of(cls_id: str, level: int, alloc: dict | None = None) -> dict:
    """宪法键名的面板：基础 + 成长×(级-1) + 加点换算。"""
    c = cls_rec(cls_id)
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
    c = cls_rec(cls_id)
    base = dict(c["base"])
    grow = {k: v * (level - 1) for k, v in c["growth"].items()}
    attr: dict = {}
    for stat, n in (alloc or {}).items():
        for k, v in (c["conv"].get(stat) or {}).items():
            attr[k] = attr.get(k, 0) + v * n
    drop = ("crit",)
    # ★ 不再往层里塞等级：引擎 `stats.actor_stats` 已把 `level` 统一带出
    #   （真源 = actor["level"]，玩家与怪一视同仁）—— 内容侧只给面板属性。
    return (to_engine({k: v for k, v in base.items() if k not in drop}),
            to_engine({k: v for k, v in grow.items() if k not in drop}),
            to_engine({k: v for k, v in attr.items() if k not in drop}))


def build_actor(cls_id: str, level: int, alloc: dict | None = None,
                equipment: dict | None = None, buffs: dict | None = None,
                *, stack_prefix: str = "aetheran") -> dict:
    """造一个玩家 actor：自带 panel_stack（栈 id）与战斗侧字段。

    `buffs` —— `{面板键: 乘数}`（B2-6 食物增益那类），走**最后**一层 `mul`：
      乘层必须排在加层之后（引擎逐层作用：先加后乘，值才是对的）；
      只乘列出的键（引擎面板栈的 per-key mul），不写 `apply: whole`。
    """
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
            {"id": "prof_base", "src": T("SYS_PANEL_PROF_BASE"), "group": "base", "mode": "add",
             "keys": keys, "values": {k: base_e.get(k, 0) for k in keys}},
            {"id": "growth", "src": T("SYS_PANEL_GROWTH"), "group": "base", "mode": "add",
             "keys": keys, "values": {k: grow_e.get(k, 0) for k in keys}},
            {"id": "attr", "src": T("SYS_PANEL_ATTR"), "group": "attr", "mode": "add",
             "keys": keys, "values": {k: attr_e.get(k, 0) for k in keys}},
            {"id": "gear", "src": T("SYS_PANEL_GEAR"), "group": "gear", "mode": "add",
             "keys": keys, "values": {k: gear_e.get(k, 0) for k in keys}},
            # crit 是非线性率（F3），三层相加无意义 ⇒ 内容侧算好后用 set 层一次性写入
            {"id": "crit_rate", "src": T("SYS_PANEL_CRIT_RATE"), "group": "rate", "mode": "set",
             "keys": ["crit"], "values": {"crit": crit_rate}},
        ] + ([{"id": "food", "src": T("SYS_PANEL_FOOD"), "group": "buff", "mode": "mul",
               "keys": sorted(buffs), "values": dict(buffs)}] if buffs else []),
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


# ══════════════════════════════════════════════════════════════
# ★ P-27：生命上限的**唯一来源**（就是本文件这个面板）
# ══════════════════════════════════════════════════════════════
def gear_and_buffs(record) -> tuple:
    """档 → `(装备面板数值, 食物增益乘数)` —— 走 `gear` 那两个唯一取值口。

    ★ 战斗 actor 与「档上的上限」必须吃**同一份**装备 / 增益，否则又是两个源。
    """
    from . import gear as GB                  # 本地 import：免得包装载期成环
    rec = record if isinstance(record, dict) else {}
    return (GB.gear_stats(rec) or None), (GB.food_buff(rec) or None)


def hp_cap(record, *, strict: bool = True):
    """玩家档 → **生命上限**（宪法键 `hp_max`）。唯一来源：本函数（职业面板）。

    两种失败分开处置（fail-closed 纪律：`fail-closed-boundaries` §1）：

      · 档上 `cls` **空**（建号第二步「选职业」还没走完）= **还没声明** ⇒
        `strict=False` 回 `None`（呈现面照实说「未定」，不猜数）；`strict=True` 抛
        `PanelMissing` —— 需要数字的地方（回血 / 战斗）不许拿 100 或别的职业垫上。
      · 档上 `cls` **有值、但 classes 域里没有** = **声明错了** ⇒ 一律抛（点名 + 列出现有的）。

    档上那一格 `hp_max` 由本函数**派生**（原先 `apply.initial_save` 与 `cmds_ast.DEFAULT_PLAYER`
    各写死 100 ⇒ 与面板两个源；现在唯一的一处是 `cmds_ast._p`，出档口现算）。把门的是
    `cls_rec`（空 / 不在域里都点名）—— 本函数不再自己判一遍。
    """
    rec = record if isinstance(record, dict) else {}
    cls = str(rec.get("cls") or "").strip()
    if not cls and not strict:
        return None                            # 还没择业 ⇒ 上限未定（不猜数、也不崩）
    cls_rec(cls)                               # ★ 唯一的把关口（空 / 不在域里 ⇒ 当场抛）
    lv = max(1, int(rec.get("level") or 1))
    gear, buffs = gear_and_buffs(rec)
    return int(build_actor(cls, lv, rec.get("alloc"), gear, buffs=buffs)["max_hp"])
