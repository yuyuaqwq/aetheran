# -*- coding: utf-8 -*-
"""战斗日志的**文案槽位注入**（P-1 / 引擎侧 B1–B5 走完后改口径）。

引擎这一侧现在长什么样（2026-09-27 之后）
------------------------------------------------------------------
    `ext_combat/battle/battle.py`   `Battle(..., text=None)`：**鸭子类型**，只要求
                                    `render_or(key, default, **slots)`。
                                    ★ B5 之后引擎自己的 60 个点位**都不走这个口了**
                                    （`render_via` / `text_of` 已删）——它留给内容侧/第三方
                                    自己的调用点。
    战斗日志的措辞真源 = **表现事件（cue）**：
        引擎 `_cue(battle, logs, "<key>", {槽位})`
          → 订阅表（本包 `content/cues.py` 的 `cue_subs_fn`）
            → 引擎 `render_required(key)`：**必须命中**（表不在 / 表里没这一格 ⇒ 抛）
              → 本包这张表（`content/rules/battle_text.json` 的槽位 ↔ `content/data/texts.json` 的句子）
    ⇒ **引擎侧已经没有「兜底模板」这回事**：不挂订阅 / 缺一格，都不会回落引擎的话，
      而是装配期点名抛（`CueSubsError`）或落一行坏数据（诊断面同时报警）。

本模块管的那两件事
------------------------------------------------------------------
* 声明面：`battle_text.json` 的 `slots`（引擎 key → texts 槽位名）**全量 60 条**，
  与引擎 `CUE_NAMES` 逐条对齐（引擎加一条点位 ⇒ 本包必须同批补一格，否则装配期抛）。
* 运行面：把 texts 域的句子取出来交给引擎（本模块**不造字、不写文案**）。

三条纪律
------------------------------------------------------------------
1. ⚠️ **绝不抛**（本模块最重要的一条）：引擎把整块元素免疫/弱点逻辑包在
   `try/except Exception: pass` 里（`landing.py`）——**渲染口一抛，免疫会连
   「伤害归 0」一起静默失效**（不是少一行字，是该挡的没挡住）。所以本模块对任何输入
   都返回字符串：没声明过的 key / 槽位缺 / 模板坏 ⇒ 一律回字符串（宁可露机器键 + 探针报红）。
   配套：**装配期** `check_slots()` / 引擎的 `check_domain()` 做 fail-closed（缺一条当场抛），
   不把 fail-closed 压在这条吞异常的渲染路上。
2. **声明就要全**：`battle_text.json` 里写了的 key 必须有格子；没写的 key 引擎也不会问
   （引擎侧 60 个点位全在册）——「只声明 8 条」那种半接线口径已废。
3. **不新增第二份文案真源**：值一律从 `content/data/texts.json`（文案唯一真源）现取；
   本模块不造字、不写文案。缺槽位时**不兜一句自造的话**（装配期就抛 + 探针报红）。
"""
from __future__ import annotations

import contextlib
import json
import os

from saintess_engine.text import TextTable, safe_format

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
                raise ValueError("引擎槽位名形如 `battle.<模块>.<事件>`（照 `ext_combat.battle.cues.CUE_NAMES` / `_cue(...)` 第 3 个位置实参逐字抄）：%r" % (k,))
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

    ★ 表里就是**声明的那 60 条**（引擎侧 60 个点位全在册）——「没写进本表的 key 走引擎兜底
    模板」那个口径**已废**（B5 之后引擎侧没有任何兜底模板；引擎不会问本表以外的 key）。
    引擎的 `TextTable` 自带 `missing()` / `unused()` 记账 ⇒ 探针靠它验
    「声明的槽位真被引擎请求过」（防死槽位）。
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


# ══════════════════════════════════════════════════════════════
# ★ 一次性遮挡：**自付血**那一笔的引擎通用伤害行
#   （`content/mech.py::_self_cut` 用它；不是「文案覆盖」—— 表里那条 key 照样不声明）
# ══════════════════════════════════════════════════════════════
#: 引擎那条**通用伤害行**的槽位名（`landing.py::_apply_damage` 的 else 支逐字抄）。
_ENGINE_DAMAGE_KEY = "battle.landing.damage"


class _QuietOnce:
    """`battle.text` 的**临时替身**：只顶掉一条 key，其余原样转发给真表。

    ★ 为什么在渲染口顶、而不是在 `texts` 里覆盖 `battle.landing.damage`：
      那条 key 是**全局**的 —— 自付血与「被怪打」共用同一句，覆盖它会改到别处
      （`content/rules/battle_text.json` 的纪律 2：只声明要覆盖的那几条）。
      而自付血那一笔的落地是**本包自己调的** `LD.deal_damage` ⇒ 只在**那一调**期间
      把 `battle.text` 换成这张表：一笔自付就只剩专用行（`COMBAT_MECH_SELF_CUT`）一行。
    ★ 一次性：顶掉**第一条** `battle.landing.damage` 就交还（这一调里不会再冒出第二条 ——
      `_apply_damage` 先把这条 append 完才 fire `on_taken`）；调用方在 `finally` 里
      **无条件还原**（护盾全额吸收那种「走不到那一条」的情况也不会把遮挡留给后面的手）。
    ★ 只**显示**这一件事：结算一个字不动（护盾 / 减伤 / 事件 / 濒死全照跑），
      表的记账口（`missing()` / `unused()`）照旧问真表。
    """

    __slots__ = ("_t", "_armed")

    def __init__(self, table):
        self._t = table
        self._armed = True

    def render_or(self, key, default, /, **slots):
        if self._armed and key == _ENGINE_DAMAGE_KEY:
            self._armed = False
            return ""                     # 旧路（`render_via`）：引擎照 append ⇒ 调用方剔空串
                                          # 新路（cue）：总线 `_render` 见到空串**直接不出行**
        if self._t is None:               # 没注入表 ⇒ 与 `render_or(None, …)` 同一条路
            return safe_format(default, slots)
        return self._t.render_or(key, default, **slots)

    def __contains__(self, key) -> bool:
        """★ 「表里有没有这一格」—— cue 那条路走 `render_required`/`text_hit`，它**问的就是这一句**。

        缺了它：`key in self` 抛 `TypeError` ⇒ 引擎按「答不出 = 没有」处理 ⇒ 每个 cue 都出一行
        坏数据（表现层静悄悄地全坏）。替身表必须对这两个口（`render_or` / `__contains__`）都成立。
        """
        return self._t is not None and key in self._t

    def __getattr__(self, name):          # 自检口透传（它不是表，只是这一笔的遮挡）
        if self._t is None:
            raise AttributeError(name)
        return getattr(self._t, name)


@contextlib.contextmanager
def quiet_engine_damage(battle):
    """★ **这一调** `LD.deal_damage` 里的引擎通用伤害行被顶掉（旧路返回空串 / cue 路不出行）。

    用法（`content/mech.py::_self_cut`）：记下日志长度 → `with` 里落地 → 把新增里那格
    **空串**剔掉（引擎把渲染结果无条件 append 进 logs）⇒ 玩家那一屏只剩专用行一行。

    ★ 2026-09-27（引擎侧 cue 迁移）：引擎把 `battle.landing.damage` 那一行改成**发 cue** ——
      于是它渲染走的是 **cue 总线手里那张表**（`Build` 那一刻抓走的引用），光换 `battle.text`
      **顶不掉**（实测：自付那一笔会多出一行「💥 … 受到 N 点伤害！」，与专用行重复）。
      所以总线在 ⇒ **两张一起换**（同一个替身，共用一个「一次性」开关），还原时两张一起还。
      总线不在（引擎树还没合 cue 形状 / 这场战斗没接 cue）⇒ 行为与接线前逐字相同。
    """
    _orig = getattr(battle, "text", None)
    _bus = getattr(battle, "cues", None)
    _bus_tbl = getattr(_bus, "table", None) if _bus is not None else None
    _guard = _QuietOnce(_orig)
    battle.text = _guard
    if _bus is not None:
        _bus.table = _guard
    try:
        yield
    finally:
        battle.text = _orig
        if _bus is not None:
            _bus.table = _bus_tbl
