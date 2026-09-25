# -*- coding: utf-8 -*-
"""战斗日志的**文案槽位注入**（P-1）—— 引擎 `Battle(text=…)` 那一口的供体。

引擎这一侧早就备好了口
------------------------------------------------------------------
    `ext_combat/battle/battle.py`   `Battle(..., text=None)`：**鸭子类型**，只要求
                                    `render_or(key, default, **slots)`
    `saintess_engine/text/template.py`
                                    `render_or` 的语义：**未注入** 与 **表里缺该 key**
                                    两条路径的输出**逐字节相同**（都走 `safe_format(default)`）
    `landing.py:85` 等             `render_via(battle, "battle.landing.element_immune", "💠 免疫！…")`
                                    —— 引擎只给 key + 兜底模板 + 槽位，措辞归内容侧的表

本包此前**从不传 `text`** ⇒ 所有战斗日志走引擎兜底模板（中文内联在引擎里，且
`{element}` 那个槽位是**机器码**，玩家会看到 `免疫fire伤害`）。本模块把声明过的**几条**
接上 texts 域，别的一律不动（见纪律 2）。

三条纪律
------------------------------------------------------------------
1. ⚠️ **绝不抛**（本模块最重要的一条）：引擎把整块元素免疫/弱点逻辑包在
   `try/except Exception: pass` 里（`landing.py:81-108`）——**渲染口一抛，免疫会连
   「伤害归 0」一起静默失效**（不是少一行字，是该挡的没挡住）。所以本模块对任何输入
   都返回字符串：没声明过的 key / 槽位缺 / 模板坏 ⇒ 一律走引擎兜底模板。
   配套：槽位在不在 texts 域里，由**装配期**的 `check_slots()` 兜（fail-closed 落在
   装配期，不落在这条吞异常的渲染路上）。
2. **只声明要覆盖的那几条**：`content/rules/battle_text.json` 里没写的 key ⇒ 引擎兜底
   模板原样输出 ⇒ 剩余几百条战斗日志与接线前**一字不差**。
3. **不新增第二份文案真源**：值一律从 `content/data/texts.json`（文案唯一真源）现取；
   本模块不造字、不写文案。缺槽位时**不兜一句自造的话**（宁可露出引擎兜底模板 + 探针报红）。
"""
from __future__ import annotations

import json
import os

from saintess_engine.text import TextTable

_HERE = os.path.dirname(os.path.abspath(__file__))
_RULES = os.path.join(_HERE, "rules", "battle_text.json")
_TEXTS = os.path.join(_HERE, "data", "texts.json")

_CACHE: dict = {}


def _rules() -> dict:
    if "rules" not in _CACHE:
        with open(_RULES, encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict) or not isinstance(raw.get("slots"), dict):
            raise ValueError("battle_text.json 少了 `slots`（引擎槽位 → texts 槽位名）")
        for k, v in raw["slots"].items():
            if not str(k).startswith("battle."):
                raise ValueError("引擎槽位名形如 `battle.<模块>.<事件>`（照 `render_via` 第一参逐字抄）：%r" % (k,))
            if not isinstance(v, str) or not v:
                raise ValueError("引擎槽位 %r 要指向一个 texts 槽位名：%r" % (k, v))
        _CACHE["rules"] = raw
    return _CACHE["rules"]


def _texts() -> dict:
    """文案真源表（**同一份文件**，不是第二份真源）—— 照 `skills_lookup._load` 那份做法现读。"""
    if "texts" not in _CACHE:
        with open(_TEXTS, encoding="utf-8") as f:
            _CACHE["texts"] = json.load(f)
    return _CACHE["texts"]


def slots() -> dict:
    """引擎槽位名 → texts 槽位名（声明原样）。"""
    return dict(_rules()["slots"])


def missing_slots() -> list:
    """声明了、但 texts 域里取不到（或值是空的）—— 装配期就要报出来的那一类。"""
    tx = _texts()
    out = []
    for eng, key in sorted(slots().items()):
        rec = tx.get(key)
        if not isinstance(rec, dict) or not str(rec.get("value") or "").strip():
            out.append((eng, key))
    return out


def check_slots() -> dict:
    """装配期 fail-closed：声明的槽位都得在 texts 域里。缺 ⇒ **当场抛并点名**（不静默兜）。"""
    bad = missing_slots()
    if bad:
        raise KeyError("战斗日志槽位在 texts 域里取不到（先按真源表加槽位、再跑 rebuild_syscopy）：%s"
                       % " · ".join("%s→%s" % (e, k) for e, k in bad))
    return slots()


def table() -> TextTable:
    """引擎要的那张表（`render_or` 鸭子类型）—— 进程内只建一次。

    ★ 表里**只有声明过的那几条**（其余 key 走引擎兜底模板）；引擎的 `TextTable` 自带
    `missing()` / `unused()` 记账 ⇒ 探针靠它验「声明的槽位真被引擎请求过」（防死槽位）。
    """
    if "table" not in _CACHE:
        tx = _texts()
        entries = {}
        for eng, key in slots().items():
            rec = tx.get(key)
            if isinstance(rec, dict) and str(rec.get("value") or "").strip():
                entries[eng] = rec["value"]
        _CACHE["table"] = TextTable(entries, name="aetheran.battle")
    return _CACHE["table"]


def battle_text() -> TextTable:
    """`Battle(text=…)` 的实参（语义名 —— 调用点不必知道它是 `TextTable`）。"""
    return table()
