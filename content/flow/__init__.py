# -*- coding: utf-8 -*-
"""《阿斯特兰》flow 半边（流程类：副本推进 / 周常进度 / 战斗流程）。

宿主按**半边名**取件（`Package.optional_submodule("flow")`），再按自己的 `__name__`
前缀导入子模块 —— 所以这里是包结构与宿主契约的接缝，不是内容。

当前在位：
    weekly_progress.py   周常进度（第一阶段未启用，但半边在位且 selfcheck 诚实回报）
"""
from __future__ import annotations

__all__ = ["weekly_progress"]
