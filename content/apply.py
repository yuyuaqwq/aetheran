# -*- coding: utf-8 -*-
"""《阿斯特兰》装配入口（第二刀：最小可跑骨架）。

方向只有一条：**内容 → 引擎**。引擎不 import 本包，也不认识本包的表。

| hook | 供体 | 说明 |
|---|---|---|
| `formula_table_fn` | `content/rules/formula_table.json` | 声明式公式表（E1），12 条 |
| `formula_bindings_fn` | `content/rules/formula_bindings.json` | 语义槽位 → 声明 id（E1b）|
| `time_model_fn` | 委托声明 `F6_act_time` | CTB 行动耗时 —— 不自己实现公式 |
| `panel_layers_fn` | `content/panel_build.py` 的栈登记表 | 面板栈声明（E2）—— 形状在 `ext_combat.panel` |

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


def install_engine():
    """把本包的 hook 挂进引擎 config（全局一次、幂等）。"""
    global _MOUNTED
    if _MOUNTED:
        return
    tbl = _table()
    bind = _bindings()
    config.mount(
        formula_table_fn=lambda: tbl,
        formula_bindings_fn=lambda slot: bind.get(slot),
        time_model_fn=_time_model,
        panel_layers_fn=_panel_layers,
    )
    _MOUNTED = True


def apply_game_content(actor):        # noqa: ARG001 —— 最小骨架阶段暂无 actor 级内容
    """单个 actor 的装配（第二阶段为空；职业/机制待后续轮次）。"""
    return None

def _panel_layers(stack_id):
    """`panel_layers_fn` 供体：栈 id → 面板栈声明（内容侧现算并登记，引擎当不透明字符串）。"""
    from . import panel_build
    return panel_build.stacks().get(stack_id)
