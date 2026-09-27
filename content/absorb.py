# -*- coding: utf-8 -*-
"""吸收型（护盾）—— **状态容器收口第 2 批**（2026-09-28）的包侧一半。

设计案：`gas-design/_r2/DESIGN_state_container_r2.md` §2.1/§2.2
------------------------------------------------------------------
§0 的目标形状一句话：`effects` 是**唯一**的战斗状态容器；护盾、减伤、承伤资源全部变成
「容器里一条**带 `value`** 的条目」，到期/叠加/清除全部走既有的一条通路。引擎那边要删掉
`shields` 这个**特殊容器**、`reduce_left` 影子字段、`halve` 死字段。

本文件负责三件事（**内容侧**）
------------------------------------------------------------------
① **声明**：`absorb: true` 进本包那份 `effect_rules` 声明表（真源
   `content/rules/skill_mech.json` 的 `mechs.<名>.rules.<状态键>`，由
   `content/mech.py::rules_module()` 算成 `EFFECT_RULES` 挂进引擎）。
   ★ **吸收型由声明决定，不硬编码键名** —— 引擎问的是「哪些条目声明了 `absorb`」，
   不是「哪个键叫 shield」。内容侧想加第二种吸收资源（荆棘护罩 / 元素吸收）只要再写
   一条声明，**引擎不用动**（设计案 §2.2 的全部理由）。
② **写口**：护盾开出来一律走**引擎的状态容器写入口**（`actors.open_entry`），不是
   `actor["shields"] = …` 那个要被删掉的独立容器。
③ **形状门**（不是「两态兼容」）：判定只问引擎**形状**（`open_entry` 认不认 `value=`
   + 承伤层那张表在不在），不认版本号、不 try/except 蒙。
   ★ 2026-09-28：引擎那半**已落到 main**（`df4caf0`，`shields` 容器已删）⇒ 旧路
     （`_open_shield_legacy` 写 `actor["shields"]`）**已随之删除**。按「不留兼容壳」：
     形状门不成立时**当场抛**（旧引擎上跑 = 配置错），不悄悄退回一条死路 ——
     留着它的话，护盾会变成一块**不掉的血**（容器删了没人写、吸收层也不读它）。
     本仓既有的「两态」纪律（`content/cues.py::engine_has_cues()`）用于**判形状**，
     不用于**留两条写口**。

★ 为什么写口用**关键字传参**
------------------------------------------------------------------
`open_entry` 的形参表由引擎那半同批改动（新增 `value`）。本包一律
`open_entry(actor, tag, stacks=…, value=…, expire=…)` 全关键字 ⇒ 参数名变了也不炸。
★ 旧引擎上 `value=` 不被接受 —— 见 `engine_has_value_entry()` 那道**形状门**：
  不装就**不调**，退回旧容器（fail-closed 的另一面：形状不认识就不假装会）。

★ 「两态」是本仓库既有纪律，不是新发明：`content/cues.py::engine_has_cues()` 判
  「引擎侧 cue 迁移在不在」；`content/apply.py` 在引擎**认识**新形状却没装上口时**当场抛**。
"""
from __future__ import annotations

import inspect
import os

from ext_combat.battle import actors as ACT
from ext_combat.battle.state_effects import state_def

_RULES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules", "skill_mech.json")

#: 声明表（`{"<状态键>": {"absorb": true, …}}`）—— 唯一真源 `rules/skill_mech.json`。
#: 与 `mech.rules_module()` 算出来的 `EFFECT_RULES` 是**同一份**（不另抄一份名单）：
#: 本模块在装配期与 `mech` 对账，对不上当场抛（两处声明各写一份 = 迟早双源）。
_CACHE: dict = {}


class AbsorbError(RuntimeError):
    """吸收型声明与装配面对不上 —— 装配期当场抛，不静默。"""


# ══════════════════════════════════════════════════════════════
# ① 引擎形状门（两态的唯一判据）
# ══════════════════════════════════════════════════════════════
def engine_has_value_entry() -> bool:
    """引擎的 `open_entry` 认不认 `value` 形参（状态容器收口第 2 批的形状门 · 第一道）。

    ★ 只问**形状**（签名里有没有那个形参），不认版本号、不 try/except 蒙。
    """
    try:
        return "value" in inspect.signature(ACT.open_entry).parameters
    except (TypeError, ValueError):        # 签名单拿不到 ⇒ 不认得形状 ⇒ 当没这形状
        return False


def engine_absorb_by_container() -> bool:
    """引擎的承伤层改没改走「遍历容器里声明了 `absorb` 的条目」（形状门 · 第二道）。

    ★ 信号 = `state_effects.absorb_keys` 这个**引擎词**函数在不在（设计案 §2.2 点名的那个读口）。
      顺带验**旧容器真的没了**（`_MUTABLE_KEYS` 里不再有 `shields`）—— 引擎那半是
      「不留兼容壳」：容器删了而本包还在写那一格的话，护盾会变成一块**不掉的血**。
    """
    try:
        from ext_combat.battle.state_effects import absorb_keys   # noqa: F401
    except ImportError:
        return False
    return "shields" not in (getattr(ACT, "_MUTABLE_KEYS", {}) or {})


#: 两态的单一判据：**两道形状门都真** = 新路（容器条目）；任一假 = 旧路（`shields` 容器）。
def container_mode() -> bool:
    return engine_has_value_entry() and engine_absorb_by_container()


# ══════════════════════════════════════════════════════════════
# ② 声明侧：哪些状态键声明了 `absorb`（引擎词，零游戏专名）
# ══════════════════════════════════════════════════════════════
def absorb_declared() -> dict:
    """声明了 `absorb` 的那些状态规则（`{<状态键>: <那条规则>}`）—— 现读，不写死名单。

    真源 = 本包那份 `effect_rules` 声明表（`rules/skill_mech.json` 的 `mechs.*.rules`）。
    ★ 与 `mech.rules_module()` 挂进引擎的 `EFFECT_RULES` **同一份**：这里走
      `state_def`（引擎那个取件口，读的就是 `EFFECT_RULES`）⇒ 内容与引擎读同一处，
      不存在「内容声明了、引擎没挂」的双源缝。
    """
    from . import mech as MECH                    # 本地 import：mech → 本模块（不成环）
    out = {}
    for key in MECH.absorb_state_keys():
        rule = state_def(key)
        if not rule:
            raise AbsorbError(
                "状态 %r 在 skill_mech.json 里声明了 absorb，但它没挂进 EFFECT_RULES"
                "（state_def 回空）—— 声明了没落地 = 静默不吸收，装配期点名" % (key,))
        out[key] = rule
    return out


def absorb_keys_of(actor: dict) -> list:
    """这个 actor 身上**当前开着**的吸收型条目（按容器键序，可复现）。

    ★ 判据 = 「这条的 `value` 还是正数」（引擎承伤层同一条口径：归零即删、不再吸收）。
      返回的是**条目键**列表，不是规则 —— 规则在 `absorb_declared()` 那儿。
    """
    out = []
    for key in sorted(actor.get("effects") or {}):
        entry = (actor.get("effects") or {}).get(key)
        if not isinstance(entry, dict):
            continue
        try:
            if float(entry.get("value") or 0) > 0:
                out.append(key)
        except (TypeError, ValueError):
            continue
    return out


# ══════════════════════════════════════════════════════════════
# ③ 写口：护盾开出来（唯一一条路 = 容器条目）
# ══════════════════════════════════════════════════════════════
def open_shield(actor: dict, key: str, value: int, expire=None) -> dict:
    """给 `actor` 开一条吸收型条目（盾值 `value`，到期 `expire`），回那条条目。

    ★ **容器条目那条路**（新）：一律**关键字**传给引擎那个唯一写入口
      `actors.open_entry`（引擎侧同批新增 `value` 形参，见 `open_entry`）：
      `stacks` / `value` / `expire` 三个格子全由这一口落 —— 内容侧**不自己拼 dict**
      （自己拼 = 绕过唯一写入口 = 形状一变就悄悄错位）。
    ★ **旧 `shields` 容器那条路已删**（2026-09-28 · 引擎 `df4caf0` 落到 main 之后）：
      引擎已删掉那个容器，留着这条写口就是**永不生效的壳** —— 护盾会变成一块不掉的血
      （写进去没人读、吸收层也不看它）。形状门不成立 ⇒ **当场抛**（那是引擎版本配错）。
    """
    if not isinstance(actor, dict) or not key:
        raise AbsorbError("开吸收型条目要一个 actor 与一个非空状态键：%r" % (actor,))
    if not container_mode():
        raise AbsorbError(
            "引擎形状门不成立（open_entry 缺 value= / 承伤层没走 absorb_keys / _MUTABLE_KEYS "
            "里还有 shields）—— 本包只支持收口后的引擎（main ≥ df4caf0）。"
            "★ 不退回旧容器：那个容器引擎已删，写进去是一块不掉的血。")
    #: ★ 同源叠厚（同一状态键反复开 = 叠厚，与旧 `act_shield` 同口径）——
    #: 引擎那条 `open_entry` 是**覆盖**语义，所以叠厚由这一口自己做（取 max，不丢旧量）。
    old = (actor.get("effects") or {}).get(key)
    if not isinstance(old, dict):
        old = {}
    keep = max(int(old.get("value") or 0), int(value))
    keep_exp = expire
    if keep_exp is None:
        keep_exp = old.get("expire")
    elif old.get("expire") is not None:
        keep_exp = max(float(keep_exp), float(old["expire"]))
    return ACT.open_entry(actor, str(key), stacks=1, value=keep, expire=keep_exp)


def shield_of(actor: dict, key: str) -> dict:
    """读某一格吸收型条目 —— 读口，**不写**（只认容器那一条路）。

    ★ 探针与文案读它。读 `effects[key]`；引擎没给这格 ⇒ 空 dict（调用方按「没这盾」算）。
    """
    e = (actor.get("effects") or {}).get(str(key))
    return e if isinstance(e, dict) else {}


def shield_value_of(actor: dict, key: str) -> int:
    """那一格还剩多少（两态同口径：条目自己的 `value`）。"""
    try:
        return int(shield_of(actor, key).get("value") or 0)
    except (TypeError, ValueError):
        return 0


def shield_expire_of(actor: dict, key: str) -> float:
    """那一格什么时候到期（只认容器条目的 `expire`）。"""
    e = shield_of(actor, key)
    raw = e.get("expire")
    try:
        return float(raw) if raw is not None else 0.0
    except (TypeError, ValueError):
        return 0.0
