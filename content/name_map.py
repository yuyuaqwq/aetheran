# -*- coding: utf-8 -*-
"""机器键 → 玩家显示名（cue 渲染**前**的翻译层）—— P2-4b 车道。

病根
------------------------------------------------------------------
引擎发 cue 时，payload 直传 **ASCII 机器键**：

    _cue(battle, logs, "battle.effects.stack_add",
         {"key": "silenced", ...})        ← silenced 被直接填进文案
    _cue(battle, logs, "battle.gauge.gain",
         {"bar": "shaken", ...})

文案模板写的是 {key} / {bar} ⇒ 玩家在战斗日志里看到
「✦【142 刻】silenced 2/3（+1）」—— 内部实现细节出现在玩家眼前。

修法（**引擎零改动**）
------------------------------------------------------------------
引擎只管发 ASCII 键 —— 那是它的中性词，两款游戏共用（第二款游戏接上去一行不用改）。
翻译发生在**本包这一侧**：注入 Battle(text=…) 的那张表外面套一层，
渲染前把 payload 里的机器键换掉：

    引擎 _cue(payload) → CueBus.emit → **本表** 翻译 → 文案表渲染 → 玩家

为什么不去改引擎那两个注入点（gauge/__init__.py:232 / effects.py:448）
------------------------------------------------------------------
那样要么引擎里写死中文表（违反「引擎零游戏名词」· 第二款游戏不改一行就不能用），
要么给引擎加一个「状态键有显示名」的取件口（同样是游戏语义进引擎）。
现在的形状：**引擎只发键、包里发名** —— 换一款游戏只换 name_map.json。

两条硬规矩
------------------------------------------------------------------
1. ⚠️ **渲染期不抛**（content/battle_text.py 纪律 1 的同一条理由）：引擎把元素免疫/
   弱点逻辑包在 try/except Exception: pass 里 ⇒ 渲染口一抛，**连「伤害归 0」一起
   静默失效**（不是少一行字，是该挡的没挡住）。所以查不到键**照原样透传**
   （露机器键 + 探针当场报红），fail-closed 放在**装配期** check_domain()。
2. **不造词**：显示名一律取既有真源（name_map.json 逐条注明出处），本模块零中文。
"""
from __future__ import annotations

import json
import os

__all__ = ["NameMapError", "load", "name_of", "translate", "check_domain",
           "state_keys", "pending_actions"]

_HERE = os.path.dirname(os.path.abspath(__file__))
_RULES = os.path.join(_HERE, "rules", "name_map.json")
#: ★ 资源键真源（**只读文件**，绝不走 content.resources 的运行期缓存）——
#:   理由见 _want_res_keys() 的注释：装配期判据不能被 fixture 清空缓存影响。
_RES_RULES = os.path.join(_HERE, "rules", "resources.json")

_CACHE: dict = {}

#: payload 里**装机器键**的槽位（哪一格该被翻，不是所有格都翻）。
#: 照引擎 cue payload 的字面量逐条列（gauge/* 与 battle/effects.py）。
_KEY_SLOT = "key"
_BAR_SLOT = "bar"


class NameMapError(RuntimeError):
    """显示名表答不上来 —— **装配期**点名抛（运行期不抛，见模块头规矩 1）。"""


def load() -> dict:
    """读表（进程内一次）。三类：状态键 / 资源键 / 血条键。"""
    if "map" not in _CACHE:
        with open(_RULES, encoding="utf-8") as f:
            raw = json.load(f)
        for sect in ("state", "res", "bar"):
            v = raw.get(sect)
            if not isinstance(v, dict):
                raise NameMapError(
                    "name_map.json 少了 %s 段（拿到的是 %s）" % (sect, type(v).__name__))
        _CACHE["map"] = {s: dict(raw[s]) for s in ("state", "res", "bar")}
    return _CACHE["map"]


def _norm(k) -> str:
    """键归一：去掉容器前缀（bar:shaken 与 shaken 两种形态取同一个）。"""
    s = str(k or "")
    return s.split(":", 1)[1] if ":" in s else s


def name_of(key, slot: str = _KEY_SLOT):
    """机器键 → 显示名；查不到回 None。

    ★ **不回机器键本身** —— 那正是要修的缺陷，调用方要能分辨「没查到」。
    slot 决定查哪一段：key → 状态键 · bar → 血条键。
    """
    return load()["bar" if slot == _BAR_SLOT else "state"].get(_norm(key)) or None


def translate(slots: dict) -> dict:
    """把 payload 里的机器键换成显示名（**不改原 dict**，返回新的一份）。

    查不到 = 照原样透传（渲染期不抛 · 见模块头规矩 1）；探针据此报红。
    """
    out = dict(slots or {})
    for slot in (_KEY_SLOT, _BAR_SLOT):
        raw = out.get(slot)
        if not isinstance(raw, str) or not raw:
            continue
        nm = name_of(raw, slot)
        if nm is not None:
            out[slot] = nm
    return out


#: 动作类槽位（op / tag / action）—— **本轮不接**，登记在案等机制上线。
#: 理由见 P2-4b_机器键上屏_交接.md §四·③：这几条要么要机制上线才上屏、要么是兜底句，
#: 此刻补表 = 做出来玩家永远看不见的活。接线时把它们挪进 name_map.json 的 action 段。
_PENDING_ACTIONS = ("op", "tag", "action")


def pending_actions() -> tuple:
    """在册但本轮不接线的键（探针据此断言「不许被误当已修」）。"""
    return _PENDING_ACTIONS


def state_keys() -> tuple:
    """表里在册的全部键（探针算覆盖率用）。"""
    m = load()
    return tuple(sorted(m["state"])) + tuple(sorted(m["res"])) + tuple(sorted(m["bar"]))


def _want_state_keys() -> set:
    """状态键**现算全集**（真源 = skill_mech.json 的 state / rules 键，不含 aeth.* 内部键）。"""
    from . import mech as _MECH
    out = set()
    for _k, _v in _MECH.mechs().items():
        if _v.get("state"):
            out.add(str(_v["state"]))
        for _rk in (_v.get("rules") or {}):
            if not str(_rk).startswith("aeth."):
                out.add(str(_rk))
    return out


def _want_res_keys() -> set:
    """资源键现算全集（真源 = resources.json 的 resources 段）。

    ★ **现读那张 json，不走 `content.resources.resources()`**：
      本函数是**装配期**的对账，而 `resources()` 读的是**运行期缓存** `resources._CACHE["t"]`
      —— 那个缓存会被 fixture 合法地清空（`probe_resources` 的 ⑦ 反证就是
      「表读不到 ⇒ 一个字段都不写」，它把 `_CACHE["t"]` 设成 `{}`）。
      走缓存 ⇒ 那一刻真源「看起来」没有资源键 ⇒ 4 条全被判成**孤儿**当场抛，
      把一条**设计中的反证**炸成装配错误（2026-09-29 实测：probe_resources ⑦ 处崩）。
      ⇒ 装配期判据只认**真源文件本身**，不被运行期状态影响。
    """
    with open(_RES_RULES, encoding="utf-8") as f:
        raw = json.load(f)
    res = (raw.get("resources") or {})
    return {str(k) for k in res}


class TranslatedTable:
    """给 `Battle(text=…)` 用的**翻译代理**：渲染前把 payload 的机器键换成显示名。

    为什么是代理而不是改模板 / 改引擎
    ------------------------------------------------------------------
    · 改模板：模板里 `{key}` 是**引擎 payload 的槽位名**，把它抄进 17 格文案
      = 引擎接口名进内容表（双源温床），且 17 格要同步改。
    · 改引擎：要么引擎写死中文表（违反「引擎零游戏名词」），要么给引擎加
      「状态键有显示名」的取件口（同样是游戏语义进引擎）。
    · 代理：翻译发生在**本包这一侧**，引擎只管发 ASCII 键 ——
      「第二款游戏不改一行能用」这条判据天然成立（换游戏只换 `name_map.json`）。

    透传哪些口
    ------------------------------------------------------------------
    引擎对这张表只要求鸭子类型（`render_or` / `__contains__`），但本包自己
    还在用 `missing()` / `unused()` 记账（探针靠它验「声明的槽位真被请求过」）
    ⇒ 代理把 `render` / `render_or` 翻完槽位，其余（记账、迭代、`__contains__`）
    **原样转发**给真表，不自己记一份（两本账会让探针的数字对不上）。
    """

    # ★ 故意**不写** `__slots__`：探针（`probe_cues` ⑧）会在实例上猴补
    #   `render_or` 来测「渲染就抛会怎样」；`__slots__` 会让那种猴补直接
    #   `AttributeError: read-only` ⇒ 门禁自己崩（不是变红，是报不出话）。
    #   代价 = 代理多一个 `__dict__`，可忽略。

    def __init__(self, table):
        self._t = table

    # ── 引擎真正用的两个口（槽位在这里被翻译）──────────────────
    def render(self, key, /, **slots):
        return self._t.render(key, **translate(slots))

    def render_or(self, key, default, /, **slots):
        return self._t.render_or(key, default, **translate(slots))

    # ── 记账与查询：原样转发（不自己记第二本账）────────────────
    def missing(self):
        return self._t.missing()

    def unused(self):
        return self._t.unused()

    def __contains__(self, key):
        return key in self._t

    def __len__(self):
        return len(self._t)

    def __iter__(self):
        return iter(self._t)

    def keys(self):
        return self._t.keys()

    def by_category(self):
        return self._t.by_category()

    #: 「拆包」口：探针据此断言「**句子真源仍是一张**」——
    #:   总线持有的表 == 注入 Battle(text=…) 的那个 == 它的真表 == battle_text.table()。
    #:   ★ 代理是**翻译层**不是第二份表（它不持有任何文案），所以拆包后必须是同一张。
    @property
    def wrapped(self):
        return self._t

    #: ★ 透传内部记账：探针（`probe_cues`）会摸 `_specs` 做「表里到底有哪些格子」的核对。
    #:   代理**不自己记一份账**（两本账会让探针数字对不上），所以把内部结构原样交出去。
    #:   `__getattr__` 只在常规属性找不到时兜底 ⇒ 上面显式定义的那几个口优先。
    def __getattr__(self, item):
        return getattr(self._t, item)

    def __repr__(self):
        return "TranslatedTable(%r)" % (self._t,)


def check_domain() -> dict:
    """**装配期** fail-closed 对账（由 content/cues.py::check_domain 调用）。

    两条判据（两侧都**现算**，不是手写名单 —— 文档改了探针跟着变）：
      ① 状态键集与 skill_mech.json 全集逐条对齐（少一条 = 玩家会看到 ASCII 键）
      ② 资源键集与 resources.json 全集逐条对齐
    另判一条**孤儿**：表里有、真源里已不存在的键（有人改了规则表没同步这里）。

    ★ 这是「删掉表里一条显示名 ⇒ 当场报红」那颗牙（见 probe_machine_key_names.py）。
    """
    m = load()
    want_state, have_state = _want_state_keys(), set(m["state"])
    want_res, have_res = _want_res_keys(), set(m["res"])
    missing = sorted((want_state - have_state) | (want_res - have_res))
    if missing:
        raise NameMapError(
            "机器键没有显示名（玩家会在战斗日志里看到这些 ASCII 键）：%s\n"
            "去 content/rules/name_map.json 补 —— 显示名取既有真源（状态键取技能域 mech "
            "对应的技能中文名 · 资源键取 resources.json 的 name），**不许新造词**"
            % "、".join(missing))
    orphan = sorted((have_state - want_state) | (have_res - want_res))
    if orphan:
        raise NameMapError(
            "name_map.json 里有真源已不存在的键（孤儿条目）：%s —— "
            "真源改了没同步这张表；删掉它们（孤儿会让「表里有这个 key」的空判断为真）"
            % "、".join(orphan))
    return {"state": sorted(have_state), "res": sorted(have_res), "bar": sorted(m["bar"]),
            "pending_actions": list(_PENDING_ACTIONS)}
