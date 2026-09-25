# -*- coding: utf-8 -*-
"""《阿斯特兰》装配入口（第二刀：最小可跑骨架）。

方向只有一条：**内容 → 引擎**。引擎不 import 本包，也不认识本包的表。

| hook | 供体 | 说明 |
|---|---|---|
| `formula_table_fn` | `content/rules/formula_table.json` | 声明式公式表（E1），12 条 |
| `formula_bindings_fn` | `content/rules/formula_bindings.json` | 语义槽位 → 声明 id（E1b）|
| `time_model_fn` | 委托声明 `F6_act_time` | CTB 行动耗时 —— 不自己实现公式 |
| `panel_layers_fn` | `content/panel_build.py` 的栈登记表 | 面板栈声明（E2）—— 形状在 `ext_combat.panel` |
| `action_base_fn` | `content/rules/action_base.json` 的 `cast` 表 | 行动类别 → 第一段基准耗时（刻）|
| `recover_base_fn` | `content/rules/action_base.json` 的 `recover` 表 | 行动类别 → 第二段基准耗时（刻）|
| `recover_model_fn` | 委托声明 `F6_act_time` | 第二段的时间模型（与第一段同一形状）|

★ 零双源纪律：本文件不手写任何公式或常数；钳位归声明的 `guard`/`clamp`，
本文件只负责喂变量。速度形状是内容侧的选择（宪法 F6），不是引擎规则。
"""
from __future__ import annotations

import json
from pathlib import Path

from saintess_engine import config
from saintess_engine.formula import FormulaTable

_RULES = Path(__file__).resolve().parent.parent / "content" / "rules"

_TABLE = None
_BINDINGS = None
_ACTION = None
_MOUNTED = False


def _table() -> FormulaTable:
    """装配期读一次、校验一次（`from_decl` 跑 V1–V12，声明错当场抛）。"""
    global _TABLE
    if _TABLE is None:
        decl = json.loads((_RULES / "formula_table.json").read_text(encoding="utf-8"))
        _TABLE = FormulaTable.from_decl(decl)
    return _TABLE


def _bindings() -> dict:
    global _BINDINGS
    if _BINDINGS is None:
        _BINDINGS = json.loads((_RULES / "formula_bindings.json").read_text(encoding="utf-8"))
    return _BINDINGS


def _time_model(spd, base):
    """`time_model_fn` 供体：委托声明 `F6_act_time`（钳位在声明的 `guard` 里，本函数不重复钳）。"""
    return _table().eval("F6_act_time", {"base": float(base), "spd": float(spd or 0)})


def _action() -> dict:
    global _ACTION
    if _ACTION is None:
        _ACTION = json.loads((_RULES / "action_base.json").read_text(encoding="utf-8"))
    return _ACTION


def _action_base_fn(action):
    """`action_base_fn` 供体：行动类别 → 第一段基准（刻）；未知类别落 `default.cast`。"""
    a = _action()
    return float(a["cast"].get(action, a["default"]["cast"]))


def _recover_base_fn(action):
    """`recover_base_fn` 供体：行动类别 → 第二段基准（刻）；未知类别落 `default.recover`。"""
    a = _action()
    return float(a["recover"].get(action, a["default"]["recover"]))


def _recover_model(spd, base):
    """`recover_model_fn` 供体：第二段时间模型 = 与第一段同一形状（F6）。"""
    return _table().eval("F6_act_time", {"base": float(base), "spd": float(spd or 0)})


def install_engine():
    """把本包的 hook 挂进引擎 config（全局一次、幂等）。"""
    global _MOUNTED
    if _MOUNTED:
        return
    tbl = _table()
    bind = _bindings()
    from ext_combat.battle import formulas as _formulas   # 引擎自带纯公式模块（引擎侧，非内容）
    config.mount(
        formulas=_formulas,                     # ★ 缺了它引擎走 _NullFormulas：伤害算不出来
        formula_table_fn=lambda: tbl,
        formula_bindings_fn=lambda slot: bind.get(slot),
        time_model_fn=_time_model,
        action_base_fn=_action_base_fn,
        recover_model_fn=_recover_model,
        recover_base_fn=_recover_base_fn,
        panel_layers_fn=_panel_layers,
        # ★ 技能取件口（缺了引擎索引不到技能 ⇒ 玩家/怪「静默空放」默认技）
        skill_lookup=_skills_mod(),
        monster_skill_fn=_monster_skill,
        basic_skill_fn=_basic_skill,
        basic_fallback={"name": "挥击", "kind": "主动", "power": 1.0, "cd": 0,
                        "cast": {"base": 60}, "recover": {"base": 0}, "range": 1, "mp": 0,
                        "_basic": True},
    )
    _MOUNTED = True


def _skills_mod():
    """技能查询模块对象（引擎按属性取 .skill_info / .skill_by_key）。"""
    from . import skills_lookup
    return skills_lookup


def _monster_skill(key):
    from . import skills_lookup
    return skills_lookup.monster_skill(key)


def _basic_skill(class_name):
    from . import skills_lookup
    return skills_lookup.basic_skill_of(class_name)


def apply_game_content(actor):        # noqa: ARG001 —— 最小骨架阶段暂无 actor 级内容
    """单个 actor 的装配（第二阶段为空；职业/机制待后续轮次）。"""
    return None

def _panel_layers(stack_id):
    """`panel_layers_fn` 供体：栈 id → 面板栈声明（内容侧现算并登记，引擎当不透明字符串）。"""
    from . import panel_build
    return panel_build.stacks().get(stack_id)


# ══════════════════════════════════════════════════════════════
# 新玩家初始档（引擎 `Package.initial_save(uid, ctx)` 调它）
# ══════════════════════════════════════════════════════════════
def initial_save(uid: str, ctx: dict | None = None) -> dict:
    """第一次来的人在哪儿、有什么。

    ★ 起始位置 = 风车镇北口（玩家第一眼看到的就是那块刻字的石头）。
    ★ 30 枚铜板是一个人在镇上活三天的钱（住店 8 / 一顿饭 2）；给多了镇子就没意义了。
    ★ P-27：**不写 `hp` / `hp_max`** —— 生命上限只有一个来源（职业面板），由 `cmds_ast._p`
      出档时按面板派生（原先这里与 `cmds_ast.DEFAULT_PLAYER` 各写死 100 ⇒ 两个源，
      而且没有任何升级 / 换装钩子刷它）。
    """
    return {
        "name": "", "race": "", "cls": "", "level": 1, "exp": 0,
        "loc": "windmill_town", "node": "wt_gate_n", "prev": [],
        "mo": 0, "mo_max": 0,
        "gold": 30, "bag": {}, "equipped": {}, "flags": {}, "codex": {},
    }
