# -*- coding: utf-8 -*-
"""《艾瑟兰：织誓》——唯一装配入口。

方向只有一个：**内容 → 引擎**。引擎不 import 本包，也不认识本包的表。

## 本文件装什么

| hook | 供体 | 说明 |
|---|---|---|
| `formula_table_fn` | `content/rules/formula_table.json` | 声明式公式表（F1–F12 + F2 全链），E1 |
| `formula_bindings_fn` | `content/rules/formula_bindings.json` | 语义槽位 → 声明 id，E1b |
| `time_model_fn` | 同上表（**委托 `F5_act_time`**） | 行动间隔，E2b/CTB |

★ **零双源纪律**：本文件**不再手写任何公式或常数**。
  修前 `_time_model` 自己实现了 `base*(spd_ref/spd)^alpha` 且自带一份
  `TIME_MODEL = {spd_ref, alpha, spd_cap}` —— 与 `F5_act_time` 的声明**同式同数**，
  改一处另一处会静默漂（这正是 E1 要消灭的东西）。
  现在钳位归声明的 `guard`、常数归声明的 `$const`，本文件只负责**喂变量**。
"""
from __future__ import annotations

import json
from pathlib import Path

from saintess_engine import config
from saintess_engine.formula import FormulaTable

_RULES = Path(__file__).resolve().parent.parent / "content" / "rules"

_MOUNTED = False
_TABLE: FormulaTable | None = None
_BINDINGS: dict | None = None


def _load_table() -> FormulaTable:
    """装配期读一次、校验一次（`from_decl` 跑 V1–V12，声明错当场抛）。"""
    global _TABLE
    if _TABLE is None:
        decl = json.loads((_RULES / "formula_table.json").read_text(encoding="utf-8"))
        _TABLE = FormulaTable.from_decl(decl)
    return _TABLE


def _load_bindings() -> dict:
    global _BINDINGS
    if _BINDINGS is None:
        _BINDINGS = json.loads(
            (_RULES / "formula_bindings.json").read_text(encoding="utf-8"))
    return _BINDINGS


def _time_model(spd, base):
    """`time_model_fn` 供体：**委托声明** `F5_act_time`（不再自己实现）。

    声明侧口径：`ActTime = base × (SPD_REF/有效spd)^0.5`，
    `spd_ref`/`alpha` 取自 `$const`，`spd` 的 floor=1 / cap=300 由声明的 `guard` 负责
    —— 本函数**不做任何钳位**，否则就是把 guard 又抄了一遍。
    """
    return _load_table().eval("F5_act_time", {"base": float(base), "spd": float(spd or 0)})


def install_engine():
    """把本包的 hook 挂进引擎 config（幂等）。"""
    global _MOUNTED
    if _MOUNTED:
        return
    tbl = _load_table()
    bind = _load_bindings()
    config.mount(
        formula_table_fn=lambda: tbl,
        formula_bindings_fn=lambda slot: bind.get(slot),
        time_model_fn=_time_model,
    )
    _MOUNTED = True


def apply_game_content(actor):        # noqa: ARG001 —— P1 阶段暂无 actor 级内容
    """单个 actor 的装配（P1 为空；随从/机制待后续轮次）。"""
    return None
