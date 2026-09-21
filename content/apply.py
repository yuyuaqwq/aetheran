# -*- coding: utf-8 -*-
"""《艾瑟兰：织誓》——唯一装配入口。

方向只有一个：**内容 → 引擎**。引擎不 import 本包，也不认识本包的表。

⚠️ 当前是 **P1 骨架阶段**：只装配「时间模型」这一个 hook，
   其余（公式族 F1–F12 / 面板聚合 / 技能表）待 `12_迁移引擎评估/01` 的 E1/E2 落地后接入。
   引擎对未装配的 hook 走「零默认值」⇒ 包能加载、能进编辑器，但战斗数学还是中性兜底。
"""
from __future__ import annotations

from saintess_engine import config

# 时间模型（内容侧参数，数据字典 §0 红线 Z2：1 刻 = 1 次普通行动，1 天 = 120 刻）
TIME_MODEL = {"shape": "pow", "spd_ref": 100.0, "alpha": 0.5, "spd_cap": 300.0}

_MOUNTED = False


def _time_model(spd, base):
    """`time_model_fn` 供体：行动间隔 = base × (SPD_REF/有效spd)^alpha。

    形状 = F5（数据字典 §3.1）：`ActTime = base × (SPD_REF/有效spd)^0.5`，α 是唯一的速度权重旋钮。
    """
    _spd = max(float(spd or 0), 1.0)
    _spd = min(_spd, float(TIME_MODEL["spd_cap"]))
    return float(base) * (float(TIME_MODEL["spd_ref"]) / _spd) ** float(TIME_MODEL["alpha"])


def install_engine():
    """把本包的 hook 挂进引擎 config（幂等）。"""
    global _MOUNTED
    if _MOUNTED:
        return
    config.mount(time_model_fn=_time_model)
    _MOUNTED = True


def apply_game_content(actor):        # noqa: ARG001 —— P1 骨架暂无 actor 级内容
    """单个 actor 的装配（P1 骨架为空；随从/机制待后续轮次）。"""
    return None
