# -*- coding: utf-8 -*-
"""客栈「住店」那一口钱（口径表 `content/rules/inn.json` 的**唯一读口**· 本批 P-55 下半）。

为什么单开一个模块（与 `content/shop.py` / `content/ranks.py` / `content/town.py` 同一个路子）
------------------------------------------------------------------
  · 「住一宿多少」只在一处算（K65 家族：两处口径迟早打架）；
  · **代码里没有数**：那一格在 `content/rules/inn.json`（真源没给这个数 ⇒ 取值理由与出处
    写在那份表的 `_口径` 里；表是唯一真源）；
  · 只 import 基座（io / json / os）—— 唯一的生产消费方 = `content/cmds_places.py::inn`
  （`INN.fee()`），怎么排 import 都不成环。
  ★ 2026-09-30 审计残余 #32：原句写「**不被谁 import**」是**反的**，还会把下一个人
  引去查错方向 —— 按 Step 3 纪律改成实况。
"""
from __future__ import annotations

import io
import json
import os

RULES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules", "inn.json")

_CACHE = None


def _rules() -> dict:
    """`content/rules/inn.json`（唯一真源）—— 读一次，进程内复用。

    ★ 2026-09-30 审计残余 #50：**私有化**（原 `rules()` 全仓零外部消费者——生产出口只有
      `fee()`）：共享可变 dict 从公开面撤下，`INN.rules()["fee"]=999` 写穿缓存那条路
      整个关掉，`fee()` 的 fail-closed 校验不再被绕开。**不留兼容别名。**
    ★ 审计残余 #14 登记：与 `content/shop.py::rules` / `content/ranks.py` 是三份同形
      loader —— 台账判定**不合并**（与 shop 逐字同形但收益 8 行 < 复核成本；ranks 同形
      不同校验、相似度 0.649 不算同一语义别硬合）。候选形状：
      `rules_loader(path, label, extra_check)`，下次有人动 loader 时一并裁决。
    """
    global _CACHE
    if _CACHE is None:
        if not os.path.exists(RULES):
            raise RuntimeError("客栈口径表不在：%s" % RULES)
        with io.open(RULES, encoding="utf-8") as f:
            _CACHE = json.load(f)
        if not isinstance(_CACHE, dict):
            raise RuntimeError("客栈口径表形状不对（不是一张表）：%s" % RULES)
    return _CACHE


def fee() -> int:
    """住一宿多少铜板 —— 缺这一格 / 不是 ≥1 的整数 = **抛**。

    fail-closed：白住的洞不许静默开着（缺格的默认值只能是「不要钱」，那正是本批要堵的那一口）。
    """
    n = _rules().get("fee")
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise RuntimeError("客栈口径表 `fee` 缺失或不是 ≥1 的整数：%r（%s）" % (n, RULES))
    return n
