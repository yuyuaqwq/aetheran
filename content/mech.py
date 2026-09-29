# -*- coding: utf-8 -*-
"""《阿斯特兰》技能机制层（B3-27）—— 「技能 mech 名词 → 引擎动词」表 + 状态规则表的**唯一出口**。

为什么有这一层（先看结论，再看细节）
------------------------------------------------------------------
引擎的机制路只有两样东西，而且**都不在引擎里**（`extends/ext_combat/battle/effects.py`）：

    EFFECT_ACTIONS  名词 → 动词序列     读点 `resolve_actions`（effects.py:136）
    EFFECT_RULES    状态语义（承伤/面板/周期/清算）  读点 `state_effects.state_def`（21 处）

本包原先这两张表**一行都没写**（`game_config.get_effect_rules()` 回空表）。于是
`skills` 域 30 条里那 14 条写了 `mech` 的技能是这样：

    · 只有 `interrupt` 一条**偶然**生效 —— 它的机制名恰好等于引擎的动词名，
      `resolve_actions` 的「动词直通」那一支救了它；
    · 另外 8 条（taunt / unstoppable / def_break / advance_ct / hot / shield_ally /
      immune_window）走名词路 ⇒ 查空表 ⇒ `[]` ⇒ **静默空放**；
    · 剩下 5 条连名词路都到不了：`effects_from_skill` 有一道 `if mech and mval` 的门，
      而 `mval = int(info.get("mech_val", 0) or 0)` —— 盾墙 / 净罪 / 后撤没写 mech_val，
      引燃 / 垂星的 0.35 / 0.8 被 `int()` 截成 0 ⇒ 门直接关掉（`effects_from_skill` 一行不产出）。

本模块把这两张表建起来，并给「引擎现成动词做不动的那半截」注册**内容侧动词**
（`@register_action` 是引擎给内容侧的扩展面 —— 不是改引擎，orlandia 就是这么干的）。

四条纪律（本层的地基）
------------------------------------------------------------------
1. **零手打数**：机制强度数只认两处 —— ① `skills` 域的 `mech_val`（域里唯一那一处，
   本表标 `"turns": "mech_val"` 去取，不重写）；② 真源文字里的常数（逐条抄在它自己的
   `_src` 上，见 `content/rules/skill_mech.json`）。取不到的**登记**（`status: pending` +
   `why`），不编一个数垫上。
2. **三条路互斥（不许双源）**：每条机制在表里声明自己走哪条路 ——
     `engine` 引擎自己那条（`effects_from_skill` → 名词 → `EFFECT_ACTIONS`）：断势 / 破势 /
             挑战咆哮 / 不退 / 抢拍 / 庇护 / 晨祷（它们要落地在**命中时**，或引擎本来就够得着）
     `cast`   内容侧那一手（`act_cast` 触发器 → `aeth_on_cast`）：盾墙 / 净罪 / 安神曲
             （盾墙与净罪被 `mval` 门挡着；安神曲是**治疗路不吃 mech**）
     `trigger` 常驻被动（事件总线上的那一面）：血勇（`dmg_calc`· 按血线现算）/
             鹰眼 · 枕星 · 抚慰 · 刃熟（`battle_start`· 常驻态）/ 反击类（`on_taken`）
   表里声明 + 探针钉着「三条路互斥」，所以同一个机制只有一处落地。
4. **第三条路：常驻被动（B4-1 扩的形状）** —— `route=trigger` + `trigger`（事件名）：
   被动技**不是被"放"出来的**，它是挂在 actor 身上的触发器（引擎的事件总线那一面）。
   `battle_start`（整场一次）挂常驻态、`dmg_calc`（攻击方乘区）按出手那一刻的血线现算、
   `on_taken`（承伤后）做反击。事件名与动词的对应表 = `_TRIGGER_VERBS`（唯一来源），
   `player_triggers()` 从它生成挂载面 —— 表里声明的与挂上去的**逐名相等**，不多不少。
   ★ 这条路的动词一律 **fail-closed**：那两张表没挂（`EFFECT_RULES` 空）⇒ 一个字段都不写
   （「不装配 = 与接线前一字不差」这条纪律对第三条路同样成立）。
5. **fail-closed**：加载期能回答的问题不留到运行期（引擎的 handler 异常是**吞掉**的 ——
  运行期抛等于静默）。所以三件事在装配期就抛：表形状坏 / 声明了没注册的动词 /
  域里出现表里没有的机制名（`check_domain`，点名是哪条技能）。
6. **不装配 = 与今天逐字相同**：两张表不挂 ⇒ 引擎的取件口回空表 ⇒ 名词走 `[]`、
   `mval` 门照旧关着 ⇒ 与接线前**一字不差**（探针有反证那一条）。
"""
from __future__ import annotations

import json
import os
import random
import types

from ext_combat.battle import effects as EF
from ext_combat.battle import landing as LD
from ext_combat.battle import stats as ST
from ext_combat.battle.actors import actor_alive, hostile_sides
from ext_combat.battle.state_effects import state_def

from .cmds_ast import T
from . import resources as RES

_RULES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules", "skill_mech.json")

#: 表缓存（读一次）；`_CACHE["tbl"]` = 校验过的表
_CACHE: dict = {}

#: route=cast 那几条机制的实现（表里声明，这里实现 —— 两边对不上在装配期抛）
_CAST_VERBS: dict = {}

#: ★ B4-1：常驻被动那条路 —— 事件名 → 动词名（**唯一来源**；`_validate` 拿它核对表，
#:   `player_triggers()` 拿它生成挂载面）。加一个事件 = 在这里加一行（表里就能声明了）。
_TRIGGER_VERBS: dict = {
    "battle_start": "aeth_on_start",        # 整场一次：常驻态（面板型被动）
    "dmg_calc": "aeth_on_dmg_calc",         # 攻击方乘区：按出手那一刻的血线现算（血勇）
    "on_taken": "aeth_on_taken",            # 承伤后：反击类（狂态）
    "taken_calc": "aeth_block_roll",        # 承伤乘区：格挡（骑士「格挡回誓」）
}

#: 吸收型（护盾）容器里那一格的 key（同一个来源反复开 = 同源叠厚，引擎 `act_shield` 的语义）。
#: ★ 状态容器收口第 2 批（2026-09-28）：**这个键名不变**（`aeth.oath_shield`）——
#:   变的只是它落在哪儿（旧 `shields` 容器 / 新状态容器条目），而「这一族吸收伤害」这件事
#:   由**声明**说了算（`skill_mech.json` 里那条 `absorb: true`，见 `absorb_state_keys()`）。
_SHIELD_KEY = "aeth.oath_shield"


# ══════════════════════════════════════════════════════════════
# 表：读 + 校验（fail-closed）
# ══════════════════════════════════════════════════════════════
def _validate(t) -> dict:
    """表形状与引用面逐条核 —— 不对就**点名**抛（装配期，不是运行期）。"""
    if not isinstance(t, dict) or not isinstance(t.get("mechs"), dict) or not t["mechs"]:
        raise ValueError("skill_mech.json 得是「一张 mechs 表」：%r" % (t,))
    cast_declared = set()
    trigger_declared = {}
    for name, m in t["mechs"].items():
        if not isinstance(m, dict):
            raise ValueError("机制 %r 的声明得是 dict：%r" % (name, m))
        route = m.get("route")
        if route not in ("engine", "cast", "trigger", ""):
            raise ValueError("机制 %r 的 route 只能是 engine / cast / trigger / 空（待接线）：%r"
                             % (name, route))
        if m.get("status") not in ("on", "partial", "pending"):
            raise ValueError("机制 %r 的 status 只能是 on / partial / pending：%r" % (name, m.get("status")))
        if m.get("status") in ("pending", "partial") and not m.get("why"):
            raise ValueError("机制 %r 标了 %r 却没写 why（缺口的账不许空着）" % (name, m.get("status")))
        if route == "engine" and not (m.get("actions") or []):
            raise ValueError("机制 %r 声明 route=engine，但没给 actions（动词序列）" % (name,))
        if route == "cast" and not m.get("verb"):
            raise ValueError("机制 %r 声明 route=cast，但没有 verb（写清由哪一手落）" % (name,))
        if route == "trigger":
            ev = str(m.get("trigger") or "")
            if ev not in _TRIGGER_VERBS:
                raise ValueError("机制 %r 声明 route=trigger，但事件 %r 不在 _TRIGGER_VERBS 里"
                                 "（有的事件：%s）" % (name, ev, " · ".join(sorted(_TRIGGER_VERBS))))
            if str(m.get("verb") or "") != _TRIGGER_VERBS[ev]:
                raise ValueError("机制 %r 的 trigger=%s 该配动词 %r，表里写的是 %r"
                                 % (name, ev, _TRIGGER_VERBS[ev], m.get("verb")))
            trigger_declared.setdefault(ev, []).append(name)
        if route == "cast":
            cast_declared.add(name)
        for a in (m.get("actions") or []):
            if not isinstance(a, dict) or not a.get("action"):
                raise ValueError("机制 %r 的 actions 里每一条都得有 `action`：%r" % (name, a))
        bad = EF.missing_actions([a.get("action") for a in (m.get("actions") or [])])
        if bad:
            raise ValueError("机制 %r 引用了没注册的动词 %s（已注册：%s）"
                             % (name, bad, EF.action_names()))
        for k, r in (m.get("rules") or {}).items():
            if not isinstance(r, dict):
                raise ValueError("机制 %r 的状态规则 %r 得是 dict：%r" % (name, k, r))
        # ★ fxmech：出手前那道否决口读的两格 —— 形状不对当场抛（别让坏声明静默变成「不拦」）
        _mp = m.get("min_hp_pct")
        if _mp is not None:
            _v = _mp.get("value") if isinstance(_mp, dict) else _mp
            if not isinstance(_v, (int, float)) or not (0 < float(_v) <= 1):
                raise ValueError("机制 %r 的 min_hp_pct 得是 (0, 1] 里的比例：%r" % (name, _mp))
        _ob = m.get("once_per_battle")
        if _ob is not None:
            _v = _ob.get("value") if isinstance(_ob, dict) else _ob
            if not isinstance(_v, bool):
                raise ValueError("机制 %r 的 once_per_battle 得是布尔：%r" % (name, _ob))
    if cast_declared != set(_CAST_VERBS):
        raise ValueError("route=cast 的机制与实现对不上：表里 %s · 代码里 %s"
                         % (sorted(cast_declared), sorted(_CAST_VERBS)))
    # ★ 第三条路：**挂上去的事件与表里用到的事件逐名相等** —— 挂了一个没人在用的事件
    #   （空挂：每场都跑一遍什么也不做），或表里声明的消费事件没挂（接了但永远不触发），
    #   都在装配期点名。`consume_event` = 「这条机制的状态由哪个事件消费」（反击类用它）。
    used = set(trigger_declared)
    for name, m in t["mechs"].items():
        ce = str(m.get("consume_event") or "")
        if ce:
            if ce not in _TRIGGER_VERBS:
                raise ValueError("机制 %r 的 consume_event=%r 不在 _TRIGGER_VERBS 里（%s）"
                                 % (name, ce, " · ".join(sorted(_TRIGGER_VERBS))))
            used.add(ce)
    _mounted = set(_TRIGGER_VERBS)
    if set(used) != _mounted or any(not v for v in trigger_declared.values()):
        raise ValueError("route=trigger 的挂载面与表对不上：表里用到 %s · 代码里挂 %s"
                         % (sorted(used), sorted(_mounted)))
    return t


def table() -> dict:
    """整张机制表（读一次 + 校验一次）。"""
    if "tbl" not in _CACHE:
        with open(_RULES, encoding="utf-8") as f:
            _CACHE["tbl"] = _validate(json.load(f))
    return _CACHE["tbl"]


def mechs() -> dict:
    return table()["mechs"]


def of(name: str) -> dict:
    """按机制名取它那一条声明（没有 = 空 dict，调用方自己判）。"""
    return mechs().get(str(name or "")) or {}


def state_rule(key: str) -> dict:
    """状态语义（= 挂在引擎 `EFFECT_RULES` 上的那一份；引擎与内容动词**读同一处**）。"""
    return state_def(key) or {}


def absorb_state_keys() -> list:
    """声明了 `absorb` 的那些状态键（**现算**，不写死名单）—— 吸收型只由声明决定。

    ★ 状态容器收口第 2 批（2026-09-28 · 设计案 `gas-design/_r2/DESIGN_state_container_r2.md` §2.2）：
      护盾不再是一个**特殊容器**，而是「带 `value` 的状态」这一族的一员；**哪一族吸收伤害由
      声明说了算**（`absorb: true`），引擎不硬编码任何游戏专名。
      消费端 = `content/absorb.py`（写口 + 读口 + 两态门）。
    ★ 唯一真源 = `EFFECT_RULES` 那张表（`rules_module()` 算出来的，含技能机制 + 精英词条两个
      来源）—— **直接读引擎那个取件口**，不另抄一份名单：抄一份 = 迟早双源。
    """
    keys = set(k for k, r in
               ((k, rule) for m in mechs().values()
                for k, rule in (m.get("rules") or {}).items())
               if isinstance(r, dict) and r.get("absorb") is True)
    for key, rule in _elite_absorb_rules().items():
        if isinstance(rule, dict) and rule.get("absorb") is True:
            keys.add(key)
    return sorted(keys)


def rules_module() -> types.SimpleNamespace:
    """给 `game_config.load_game_rules(module)` 的模块壳：两张表从**同一张表**算出来。

    ★ route=cast 的机制**不并进 EFFECT_ACTIONS** —— 它们由内容侧那一手（act_cast 触发）落，
      并进去就等于同一件事两处落地（引擎那条名词路也会走一遍）。表里声明、探针钉着。
    ★ **吸收型（护盾）的声明也进这张表**（状态容器收口第 2 批 · 设计案 §2.2）：护盾是
      「状态容器里一条带 `value` 的条目」，**哪一族吸收伤害由声明说了算**（引擎不硬编码
      任何游戏专名，只问 `absorb_keys`）。两个来源合成同一张 `EFFECT_RULES`：
        · `mechs.*.rules`（技能机制那条，如 `aeth.oath_shield`）
        · 精英词条那条（`rules/elite.json::absorb.state_key`，如 `aeth.elite_shell`）
      ★ 同一格被两处声明 ⇒ **当场抛**（状态语义只许有一处，与下面那行同纪律）。
    """
    ea: dict = {}
    er: dict = {}
    for name, m in mechs().items():
        if m.get("route") == "engine":
            ea[name] = [dict(a) for a in (m.get("actions") or [])]
        for key, rule in (m.get("rules") or {}).items():
            if key in er:
                raise KeyError("状态规则 %r 被两条机制同时声明（状态语义只许有一处）：%r" % (key, name))
            er[key] = json.loads(json.dumps(rule, ensure_ascii=False))
    # ★ 精英词条的吸收型声明（同一张表、同一处对账）
    for key, rule in _elite_absorb_rules().items():
        if key in er:
            raise KeyError("状态规则 %r 被技能机制与精英词条同时声明（状态语义只许有一处）" % (key,))
        er[key] = rule
    return types.SimpleNamespace(EFFECT_ACTIONS=ea, EFFECT_RULES=er)


def _elite_absorb_rules() -> dict:
    """精英词条那条吸收型声明 → `EFFECT_RULES` 的一格（真源 `rules/elite.json::absorb`）。

    ★ 键 = `absorb.state_key`（内容侧声明的容器条目键），值 = `{"absorb": true}`。
      **不是**拿词条 id 当键，也不是硬编码 —— 引擎只认「声明了 `absorb`」这件事。
    ★ 表里没有那一块 ⇒ 回空表（**不兜底**）：那等于「本包没有精英开场盾这条吸收资源」，
      与接线前一致，而不是悄悄造一格。
    """
    from . import affix as _AF
    spec = (_AF.rules() or {}).get("absorb") or {}
    key = str(spec.get("state_key") or "")
    if not key:
        return {}
    return {key: {"_src": str(spec.get("_src") or ""), "absorb": True}}


def check_domain(raise_on_unknown: bool = True) -> dict:
    """跨域对账：域里每条技能声明的机制都得在表里 —— 不认得的**当场抛**（点名技能）。

    返回 `{机制名: [技能 id, ...]}`（现算，不写镜像表）。
    """
    from . import skills_lookup as SL

    seen: dict = {}
    for sid, rec in SL.skills().items():
        if str(sid).startswith("_") or not isinstance(rec, dict):
            continue
        for fld in ("mech", "mech2"):
            nm = str(rec.get(fld) or "")
            if not nm:
                continue
            if nm not in mechs():
                if raise_on_unknown:
                    raise KeyError(
                        "技能 %s（%s）声明了机制 %r，而 skill_mech.json 里没有这一条 —— "
                        "不认得的机制不许静默空放（补表或改域，别在这儿兜底）"
                        % (sid, rec.get("name"), nm))
                continue
            seen.setdefault(nm, []).append(sid)
    return seen


def declared_actions() -> list:
    """表里引用到的全部动词名（装配自检/probe 用：`EF.missing_actions` 必须为空）。"""
    out = []
    for m in mechs().values():
        out.extend([str(a.get("action")) for a in (m.get("actions") or [])])
    return sorted(set(out))


# ══════════════════════════════════════════════════════════════
# 取值小件（全部零手打：时长来自声明，语义来自状态规则表）
# ══════════════════════════════════════════════════════════════
def _now(battle) -> float:
    return float(getattr(battle, "_now", 0.0) or 0.0)


def _info(params: dict) -> dict:
    return (params or {}).get("info") or {}


def _ctx_info(battle) -> dict:
    """出手那一刻的**事件 ctx** 里那份技能 dict（`info`）—— 触发器那一路的 `params` 没有它。

    与 `content/resources.py::_info(battle)` 读的是同一处（`battle._fire_ctx`）——「谁在出手、
    出的哪条技能」只有一个口，不许各读各的。
    """
    v = getattr(battle, "_fire_ctx", None)
    return ((v or {}).get("info") or {}) if isinstance(v, dict) else {}


def _mval(params: dict, field: str = "mech_val") -> float:
    """技能自己那个强度数（`skills` 域的 `mech_val` / `mech2_val`）—— 唯一来源，本层不重写。"""
    try:
        return float(_info(params).get(field) or 0)
    except (TypeError, ValueError):
        return 0.0


def _mech_of(params: dict) -> dict:
    """这次落地的**机制声明** —— 先认 `params["mech"]`（引擎 `_mech_to_effect` 写的那个名字，
    `mech2` 走的也是它），退化到技能自己的 `info["mech"]`（`route=cast` 那条内容动词路上没有
    `params["mech"]`）。两者都取不到 ⇒ 空 dict（调用方一律「一个字段都不写」）。"""
    p = params or {}
    return of(str(p.get("mech") or _info(p).get("mech") or ""))


def _num(m: dict, key: str) -> float:
    """表里那个常数（`{"value": …, "_src": …}` 形态）。"""
    d = m.get(key)
    if isinstance(d, dict):
        d = d.get("value")
    try:
        return float(d or 0)
    except (TypeError, ValueError):
        return 0.0


def _turns(m: dict, params: dict) -> float:
    """这次落地持续多久（刻）：`"mech_val"` / `"mech2_val"` = 取技能域那个数；dict = 表里那个常数。"""
    t = m.get("turns")
    if t in ("mech_val", "mech2_val"):
        return _mval(params, str(t))
    if isinstance(t, dict):
        try:
            return float(t.get("value") or 0)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _holder(params: dict, caster, target):
    """作用对象：动作声明的 `on`（缺省 caster —— 与引擎 `apply` 同口径）。"""
    return caster if str((params or {}).get("on") or "caster") == "caster" else (target or caster)


def _pct_from_mult(mult: float) -> int:
    """×0.70 → 「−30%」那句人话里的数（口径只有一个：`1 − mult`）。"""
    return int(round((1.0 - float(mult)) * 100))


def _pct_of_rule(rule: dict) -> int:
    """状态规则 → 「减伤百分之几」（同一个口径，供文案用）。"""
    return _pct_from_mult(1.0 - float(rule.get("reduce_taken") or 0))


def _put(holder: dict, key: str, expire: float, **extra) -> None:
    """写/刷新一条状态：同 key **只刷新到期时刻**（真源「不叠加，只刷新时长」的通用形状）。"""
    ef = holder.setdefault("effects", {})
    old = ef.get(key)
    old_exp = float(old.get("expire") or 0) if isinstance(old, dict) else 0.0
    entry = {"stacks": 1, "expire": max(old_exp, float(expire))}
    entry.update(extra)
    ef[key] = entry


def _live(holder: dict, key: str, now: float) -> bool:
    e = (holder.get("effects") or {}).get(key)
    if not isinstance(e, dict):
        return False
    exp = e.get("expire")
    return exp is None or float(exp) > now


def _self_cut_raw(battle, caster, m: dict) -> int:
    """这一笔**该付多少**（不含「保底留 1 血」那道闸）—— 血线门与扣血共用这一处算式。

    ★ 为什么要与 `_self_cut_amount` 分开：`_self_cut_amount` 把金额夹到 `hp − 1`（保底留 1 血），
      于是「付完还剩得下血」这个判据**恒真** ⇒ 血线门形同虚设。真源那句「血 < 12% 时这一手
      不可用」说的是**该付的钱**（12% × 生命上限），不是夹完之后的钱。
    """
    pct = _num(m, "self_dmg_pct")
    if pct <= 0 or not isinstance(caster, dict) or caster.get("hp") is None:
        return 0
    hp = int(caster.get("hp") or 0)
    base = m.get("self_dmg_base")
    if isinstance(base, dict):
        base = base.get("value")
    base = str(base or "max_hp")
    ref = hp if base == "hp" else int(ST.actor_max_hp(battle, caster) or 0)
    cut = int(round(ref * pct))
    cap = _num(m, "self_dmg_cap")
    if cap > 0:
        cut = min(cut, int(cap))
    return max(0, int(cut))


def _self_cut_amount(battle, caster, m: dict) -> int:
    """这一笔付血**真扣多少** = min(该付的, hp − 1)。

    真源 02_狂战士_v2 §二那句「不能把自己打死」是同一句话的两半：
      · 这里那道 `hp − 1` 保证**不会**把自己打死（保底留 1 血）；
      · `skill_gate` 的血线门（用 `_self_cut_raw`）保证**不该**在付不起的时候放出去
        （「血 < 12% 时这一手不可用」）。
    """
    if not isinstance(caster, dict) or caster.get("hp") is None:
        return 0
    hp = int(caster.get("hp") or 0)
    return min(_self_cut_raw(battle, caster, m), max(0, hp - 1))


def _self_cut(battle, caster, m: dict, logs) -> int:
    """**付血**（代价那一半的公共实现）—— 按机制表里 `self_dmg_pct` 扣自己。

    三格全在声明里（本函数一个数都不写）：
      · `self_dmg_base` —— 比例的**基数**：`max_hp`（缺省）＝ 生命上限的比例
        （破势 8% / 狂斩 12% / 血债 / 狂态 / 横扫）；`hp` ＝ **当前生命**的比例
        （焚身 35% —— 血越少付得越少，真源 §六③ 那条「满血放太浪费」就是这么来的）。
      · `self_dmg_cap` —— 这一笔的**上限**（缺省 0 = 不设；焚身那句「最多 40 点」）。
      · `self_dmg_pct` —— 比例本身。

    真源口径（02_狂战士_v2.md §二「不能把自己打死」）：**保底留 1 血** —— 算式在
    `_self_cut_amount` 里（与出手前那道血线门共用）。破势（旧）/ 血债 / 狂态 / 横扫 /
    狂斩 / 焚身 六条共用这一处。

    ★ fix-a-screen（2026-09-27）：**一笔自付只出一行**。落地照旧走引擎那一条
      （`LD.deal_damage` —— 护盾 / 减伤 / 事件 / 濒死一个字不动），但引擎那条**通用**
      伤害行（`battle.landing.damage` = `💥 {name} 受到 {dmg} 点伤害！`，与「被怪打」
      长得一模一样）在**这一调**里被顶掉（`BT.quiet_engine_damage`）⇒ 屏上只剩本包的
      专用行。专用行报的数是**真扣下去的那一笔**（引擎的返回值），不是算式值
      —— 这一笔不吃减免时两者相同（试玩实测 40 = 35%×116 撞上限）。
    """
    cut = _self_cut_amount(battle, caster, m)
    if cut > 0:
        from . import battle_text as BT
        _n0 = len(logs)
        with BT.quiet_engine_damage(battle):
            # ★ 2026-09-27（引擎 `no_dodge`）：**自己付给自己的这一笔没人能闪** ——
            #   原先 source=None 也照过闪避那一掷 ⇒ 施放者能「闪开自己砍的这一刀」：
            #   `real == 0` ⇒ 下面那条 `if real > 0` 不写行 ⇒ 屏上少一句、档上少扣血。
            #   实测（probe_mech ⑥ 偶发红）：同一棵树连跑若干次里必有一次自伤「没打出来」。
            real = LD.deal_damage(battle, None, caster, cut, logs, no_dodge=True)
        # ★ 顶掉的那一行在两条路上形状不同，**归口**给 `BT.drop_quiet_lines` 剔（2026-09-29 修）：
        #   旧路 `render_via` = 空串；新路 cue = 引擎 `_render` 见空串判**坏数据**、就地
        #   append 一行 `MISS_LINE`（引擎 L2060 `9eeb12d` 之后）⇒ 那一行原样上屏，玩家在
        #   战斗屏看到「⚠️ 这条表现没渲染出来（cue 装配/文案缺口，见诊断）」。
        #   ★ 引擎零改动：那一行是普通字符串，剔在包侧。
        logs[_n0:] = BT.drop_quiet_lines(logs[_n0:])
        if real > 0:                       # 全额被护盾吃掉 ⇒ 不谎报一笔没落的血
                                           #   （★ 2026-09-27：闪避那一格已由 `no_dodge` 关掉，
                                           #    所以这里不会再有「被自己闪掉」那种 0）
            logs.append(T("COMBAT_MECH_SELF_CUT", t=int(round(_now(battle))), n=real))
    return cut


def _grant(battle, caster, m: dict, params: dict, logs, slot: str, **fields):
    """把这条机制声明的状态挂到施放者身上（时长取声明的 mech_val / 表里那个常数）+ 报一句。

    ★ fail-closed：规则表里没有这个状态 key ⇒ **一个字段都不写**（「不装配 = 与接线前
      一字不差」）。这一条对所有新动词都成立，不只是它。
    """
    key = str(m.get("state") or "")
    turns = _turns(m, params)
    if not isinstance(caster, dict) or not key or turns <= 0 or not state_rule(key):
        return ""
    _put(caster, key, _now(battle) + turns)
    logs.append(T(slot, t=int(round(_now(battle))), turns=int(turns), **fields))
    return key


def _panel_delta(rule: dict) -> int:
    """状态规则里那条 `panel` 声明 → 「涨/降百分之几」（带符号：+25 / −20）。

    口径只有一个：`(mult − 1) × 100`。要写「慢 {pct}%」这种句子的调用点自己取 `abs()`。
    """
    try:
        mult = float((rule.get("panel") or {}).get("mult") or 1.0)
    except (TypeError, ValueError):
        return 0
    return int(round((mult - 1.0) * 100))


# ══════════════════════════════════════════════════════════════
# 动词（引擎的 register_action 面 —— 内容侧扩展，不改引擎）
# ══════════════════════════════════════════════════════════════
@EF.register_action("aeth_sever")
def aeth_sever(battle, caster, target, params, logs):
    """断势：① 打断对方待发（引擎 `interrupt` 动词，含霸体判定与事件）② 给目标挂「破绽」。

    破绽的承伤倍率不在这里写 —— 挂在状态规则表 `EFFECT_RULES[break_mark].debuff_scale` 上，
    由 `landing.deal_damage` 自己消费（谁打都吃，真源「全队共享」）。
    """
    m = of("interrupt")
    if not target or not actor_alive(target):
        return
    EF.act_interrupt(battle, caster, target, {}, logs)
    key = str(m.get("state") or "")
    turns = _turns(m, params)
    if not key or turns <= 0:
        return
    _put(target, key, _now(battle) + turns)
    # ★ 那一句里的「多受 N%」= 状态规则表里写的那一档（`debuff_scale.dmg_taken` × 100），
    #   现算 —— 不给槽位留空（`{pct}` 空着会原样打给玩家）。
    _bs = (state_rule(key).get("debuff_scale") or {}).get("dmg_taken")
    logs.append(T("COMBAT_MECH_SEVER", t=int(round(_now(battle))),
                  name=target.get("name", ""), turns=int(turns),
                  pct=int(round(float(_bs or 0) * 100))))


@EF.register_action("aeth_sunder")
def aeth_sunder(battle, caster, target, params, logs):
    """破势：① 自己见血（按声明比例，保底留 1 血）② 目标 `def` 按状态规则表乘一个系数。

    破防写成**面板快照态**（条目自带 stat/op/mult）—— 与引擎 `apply` 的快照形态同一形状，
    `stats.actor_stats` 的 `_apply_effects` 直接读它 ⇒ 之后每一次伤害计算都吃这一档。
    """
    m = of("def_break")
    # ① 付：自伤
    _self_cut(battle, caster, m, logs)                        # 保底 1 血（可用性门那半见 why）
    # ② 收：破防
    key = str(m.get("state") or "")
    turns = _turns(m, params)
    panel = state_rule(key).get("panel") or {}
    if not key or turns <= 0 or not panel.get("stat") or not target or not actor_alive(target):
        return
    _put(target, key, _now(battle) + turns,
         **{k: panel[k] for k in ("stat", "op", "mult") if k in panel})
    logs.append(T("COMBAT_MECH_SUNDER", t=int(round(_now(battle))),
                  name=target.get("name", ""), turns=int(turns),
                  pct=_pct_from_mult(panel.get("mult") or 1)))


@EF.register_action("aeth_taunt")
def aeth_taunt(battle, caster, target, params, logs):
    """挑战咆哮：给持有者挂「嘲讽」态（谁挂着谁被优先打）—— 消费端 = `taunt_picker`。"""
    m = of("taunt")
    holder = _holder(params, caster, target)
    key = str(m.get("state") or "")
    turns = _turns(m, params)
    if not isinstance(holder, dict) or not key or turns <= 0:
        return
    _put(holder, key, _now(battle) + turns, v=_mval(params))
    logs.append(T("COMBAT_MECH_TAUNT", t=int(round(_now(battle))), turns=int(turns)))


def _ward(battle, caster, target, params, m, logs, slot: str) -> None:
    """减免类状态（不退 / 庇护）的公共落地：写态 + 报一句 —— 数值全在状态规则表里。"""
    holder = _holder(params, caster, target)
    key = str(m.get("state") or "")
    turns = _turns(m, params)
    if not isinstance(holder, dict) or not key or turns <= 0:
        return
    _put(holder, key, _now(battle) + turns)
    logs.append(T(slot, t=int(round(_now(battle))), turns=int(turns),
                     pct=_pct_of_rule(state_rule(key))))


@EF.register_action("aeth_standfast")
def aeth_standfast(battle, caster, target, params, logs):
    """不退：300 刻减伤（真源「全队 300 刻免伤 30%」—— 单人这一档就是自己）。"""
    _ward(battle, caster, target, params, of("unstoppable"), logs, "COMBAT_MECH_STANDFAST")


@EF.register_action("aeth_aegis")
def aeth_aegis(battle, caster, target, params, logs):
    """庇护：200 刻减伤 30%（吃预判那一条 —— 数值与时长都来自声明）。"""
    _ward(battle, caster, target, params, of("shield_ally"), logs, "COMBAT_MECH_AEGIS")


@EF.register_action("aeth_matins")
def aeth_matins(battle, caster, target, params, logs):
    """晨祷：免疫窗（态里声明 `immune` —— 承伤乘区由 `aeth_mitigate` 折成 0）。"""
    m = of("immune_window")
    holder = _holder(params, caster, target)
    key = str(m.get("state") or "")
    turns = _turns(m, params)
    if not isinstance(holder, dict) or not key or turns <= 0:
        return
    _put(holder, key, _now(battle) + turns)
    logs.append(T("COMBAT_MECH_MATINS", t=int(round(_now(battle))), turns=int(turns)))


@EF.register_action("aeth_advance_ct")
def aeth_advance_ct(battle, caster, target, params, logs):
    """抢拍：把自己下一次行动的到点时刻提前（提前量 = 技能域那个数，不重写）。

    ★ 落地这一刻 `ct` 已经推过（`battle.human_act` 的次序：T0 登记 → `_after_act` 推 ct →
    推进期间才落地）⇒ 这里减的就是**下一次行动**那个到点时刻，不是当前这一手。
    """
    m = of("advance_ct")
    adv = _mval(params)
    if not isinstance(caster, dict) or adv <= 0:
        return
    now = _now(battle)
    ct = float(caster.get("ct") or 0)
    caster["ct"] = max(now, ct - adv)
    # ★ 那半句「（{left} 刻后就到你）」撤了（试玩 b20/b23 实测 · 2026-09-27）：
    #   `left` = 夹制后 ct 与当刻之差，而抢拍的 `recover.base`(30) == `mech_val`(30)，
    #   两个数走**同一个**时间模型 ⇒ spd ≥ 100 时后摇 < 声明量 ⇒ 那道「不早于当刻」的闸
    #   把差吃掉 ⇒ `left` **结构性恒 0**（实跑 spd=118：后摇 27.62 < 30 ⇒ left=0）。
    #   于是「提前 30 刻（0 刻后就到你）」被玩家读成自相矛盾（b20/b23 原话）。
    #   ★ 夹制与声明**一个字没动**（`max(now, …)` 照旧，不许负 ct）——见 `probe_mech` ⑩
    #     与 `skill_mech.json` 那条 judge「少 mech_val 刻，**且不小于当刻**」。
    #   现在这句报的是**声明量**（域里 mech_val），文案那边写「最多提前」把闸说清楚。
    logs.append(T("COMBAT_MECH_QUICKSTEP", t=int(round(_now(battle))), ticks=int(adv)))


@EF.register_action("aeth_mitigate")
def aeth_mitigate(battle, caster, target, params, logs):
    """承伤乘区（`taken_calc` 触发）：把持有者身上带 `reduce_taken` / `immune` 的态折成乘区。

    引擎零知识：**哪些 key 是减免态全看状态规则表**，本函数不认任何机制名/状态名。
    没带态的持有者 ⇒ 一个字段都不写（与接线前逐字相同）。
    """
    ctx = getattr(battle, "_fire_ctx", None)
    if not isinstance(ctx, dict):
        return
    holder = ctx.get("actor") or target or caster
    if not isinstance(holder, dict):
        return
    now = _now(battle)
    mult = 1.0
    immune = False
    plain: list = []
    axes: dict = {}
    for k, e in list((holder.get("effects") or {}).items()):
        if not isinstance(e, dict):
            continue
        exp = e.get("expire")
        if exp is not None and float(exp) <= now:
            continue
        rule = state_rule(k)
        if rule.get("immune"):
            immune = True
            mult = 0.0
            continue
        red = float(rule.get("reduce_taken") or 0)
        if red <= 0:
            continue
        # ★ 同轴（join_key 相同）只算**最强的那一条** —— 声明在状态规则表里
        #   （真源没写两条同类减伤并存怎么算 ⇒ 表里的这条是显式设计决定，
        #    探针钉着：不退 + 庇护 同时开 = ×0.7，不是 ×0.49）。
        jk = str(rule.get("join_key") or "")
        if jk:
            axes[jk] = max(float(axes.get(jk, 0.0)), red)
        else:
            plain.append(red)
    for red in plain:
        mult *= (1.0 - red)
    for red in axes.values():
        mult *= (1.0 - red)
    if mult == 1.0 and not immune:
        return
    cur = ctx.get("mult")
    ctx["mult"] = (1.0 if cur is None else float(cur)) * mult
    if immune:
        logs.append(T("COMBAT_MECH_IMMUNE", t=int(round(_now(battle)))))
    else:
        logs.append(T("COMBAT_MECH_MITIGATE", t=int(round(_now(battle))),
                      pct=int(round((1.0 - mult) * 100))))


def taunt_picker(battle, actor):
    """引擎的「这次打谁」注入点（`Battle.target_picker`）：谁挂着嘲讽态就先打谁。

    **没挂 = 返回 None** ⇒ 引擎回落默认目标解析 ⇒ 与接线前逐字相同（探针有反证那一条）。
    """
    key = str(of("taunt").get("state") or "")
    if not key or not isinstance(actor, dict):
        return None
    now = _now(battle)
    for sn in hostile_sides(battle, actor.get("side") or ""):
        for a in (battle.sides.get(sn) or []):
            if a is not actor and actor_alive(a) and _live(a, key, now):
                return a
    return None


# ══════════════════════════════════════════════════════════════
# route=cast 那五条（引擎那两条路都够不着 —— 见文件抬头第 2 条）
# ══════════════════════════════════════════════════════════════
def _cast_protect(battle, caster, info, m, logs):
    """盾墙：免伤到**自己下一次行动之前**（时长现算：`ct − 现在` —— 引擎自己推的那个数）。"""
    key = str(m.get("state") or "")
    now = _now(battle)
    turns = max(1.0, float(caster.get("ct") or 0) - now)
    if not key:
        return
    _put(caster, key, now + turns)
    logs.append(T("COMBAT_MECH_OATHWALL", t=int(round(_now(battle))), turns=int(round(turns)),
                  pct=_pct_of_rule(state_rule(key))))


def _cast_cleanse(battle, caster, info, m, logs):
    """净罪：解掉**一个**控制效果（控制的判据 = 引擎的那个 `mode`，不认任何态名）。"""
    ef = caster.setdefault("effects", {})
    hit = next((k for k, e in ef.items() if isinstance(e, dict) and e.get("mode")), None)
    if hit is None:
        logs.append(T("COMBAT_MECH_ABSOLVE_NONE", t=int(round(_now(battle)))))
        return
    ef.pop(hit, None)
    logs.append(T("COMBAT_MECH_ABSOLVE", t=int(round(_now(battle)))))


def _cast_hot(battle, caster, info, m, logs):
    """安神曲：挂 300 刻再生，每跳回「这一发治疗量的 1/4」（比例来自声明，量现算）。

    治疗量走**本包那个唯一的基数口**（`_heal_base_of` = F8）—— 不另写一套公式；
    引擎的 `do_heal` 那一发吃的是同一个口（`aeth_heal_calc` 折的是同一个数）。
    条目自带 `period`（引擎优先读它，EFFECT_RULES 不必再声明一份）⇒ 时间轴上真跳。
    """
    key = str(m.get("state") or "")
    turns = _turns(m, {"info": info})
    ratio = _num(m, "hot_ratio")
    # ★ 生命上限：先读 actor 自己那一份，读不到才问聚合面板 —— 不拿任何常数垫上
    #   （静态守卫 `probe_panel ④` 钉着「`\"max_hp\"` 后面跟 `or <数>`」这个指纹）。
    _mx_raw = caster.get("max_hp")
    mx = int(_mx_raw) if _mx_raw else 0
    if mx <= 0:
        try:
            mx = int(ST.actor_max_hp(battle, caster) or 0)
        except Exception:                                   # noqa: BLE001 · 面板未装配 / 栈未声明
            mx = 0
    # ★ 审计 L407（2026-09-29 · 批次 1）：兜底原先写 `or 1`。
    #   引擎 `stats.actor_max_hp` 那一口的**默认值本身就是 1**
    #   （`actor_stats(...).get("max_hp", actor.get("max_hp", 1))`）⇒ 面板取不到时
    #   `mx` 恒为 1，而 `heal_pct = per / mx` 是「每跳回**上限**的百分比」
    #   ⇒ 读不到上限时每跳直接回满血。台账实测：同场景上限 116 那档 0.0172，
    #   读不到那档 **2.0（116 倍）**，不报错、不留痕。
    #   同文件另三处（399 / 1220 / 1393）一律 `or 0` = 「取不到就不写态」⇒ 此处同口径；
    #   且 `mx <= 0` 时**不挂再生**（分母为 0 的百分比无意义，静默写一个巨大值更糟）。
    if mx <= 0:
        return
    try:
        heal = _heal_base_of(battle, caster, info)
    except Exception:                                   # noqa: BLE001
        heal = _engine_heal_of(battle, caster, info)    # F8 没装配 ⇒ 引擎那一口（与接线前一字不差）
    per = int(round(float(heal) * ratio))
    if not key or turns <= 0 or per <= 0:
        return
    caster.setdefault("effects", {})[key] = {
        "stacks": 1,
        "expire": _now(battle) + turns,
        "period": {"dir": "heal", "interval": 1, "heal_pct": float(per) / float(mx)},
    }
    logs.append(T("COMBAT_MECH_LULLABY", t=int(round(_now(battle))), turns=int(turns), per=per))


def _f8_heal(battle, caster, info) -> float:
    """本包 F8（`content/rules/formula_table.json::F8_heal`）**求值** —— 治疗量基数那一格。

    真源 `02_数值宪法/01_属性字典与基础公式.md` F8：`heal = heal_pow × mult × (1 + heal_bonus/100)`
      · `heal_pow`   治疗强度（真源那一栏的原话就是「治疗量基数」）
      · `mult`       这一发技能自己的倍率（域里的 `power`：安神曲 1.5）
      · `heal_bonus` 治疗加成（点数）—— 本包今天没有任何一档声明它 ⇒ 恒 0

    ★ 本函数**只求值**、不写任何字段；取不到（公式表没挂 / 变量名对不上）⇒ 抛给调用方
      （`_heal_base_of` 接住并回落到引擎那一口；探针 ㉓ 有撤改那条判据钉着）。
    """
    from . import apply as _AP                      # 公式表的唯一出口（本包那一份）
    st = ST.actor_stats(battle, caster)
    return float(_AP._table().eval("F8_heal", {
        "heal_pow": float(st.get("heal_pow", 0) or 0),
        "mult": float((info or {}).get("power") or 0),
        "heal_bonus": float(st.get("heal_bonus", 0) or 0),
    }))


def _heal_base_of(battle, caster, info) -> float:
    """这一发治疗的**基数**：本包 F8（声明）优先，取不到才回落引擎那一口。

    ★ fail-closed 的落点：「公式表没装配 ⇒ 与接线前一字不差」（F8 求值抛 / 回 ≤ 0 ⇒ 用引擎那一口，
      即声明的 `heal_formula` 或兜底 `matk × power`）—— 探针 ㉓ 有撤改那条判据钉着。
    ★ 本函数只取基数、不写任何字段 —— 落地的两处是 `aeth_heal_calc`（引擎那一发）与
      `_cast_hot`（再生每一跳）。
    """
    try:
        got = _f8_heal(battle, caster, info)
        if got > 0:
            return got
    except Exception:                                   # noqa: BLE001
        pass
    return _engine_heal_of(battle, caster, info)


def _engine_heal_of(battle, caster, info) -> float:
    """引擎那一口治疗量（`actions.heal_amount`：声明式 `heal_formula` / 兜底 `matk × power`）。"""
    from ext_combat.battle import actions as ACT
    from ext_combat.battle import game_config as GC

    lv = GC.formulas().skill_level_of(caster, info.get("name", "")) if caster.get("class_name") else 0
    return float(ACT.heal_amount(ST.actor_stats(battle, caster), caster, info, lv))


@EF.register_action("aeth_heal_calc")
def aeth_heal_calc(battle, caster, target, params, logs):
    """治疗量的基数（F8）—— 挂在引擎的 `heal_calc`（**治疗算出后、落地前**的乘区口，主体 = 施法者）。

    引擎那一发在 `ctx["heal"]` 里，而那个口只给「乘一个系数」（没有「换基数」的形参）
    ⇒ 本层按**比值**把引擎那一发折成本包 F8 那一发（比例与 F8 都是现算，本层一个数都不写）。

    ★ 为什么走 `heal_calc` 而不是 `heal_formula`：那条要 `heal_pow` 当表达式变量，而变量表由
      内容侧另一处声明（引擎那份默认表里没有 `heal_pow`）—— 本批不许动那一处（见 `_notes.md` 的
      「需要那一半」）。`heal_calc` 是本包已经挂着的口，且它拿到的是**同一个**技能 dict。
    ★ fail-closed 两道：F8 求不出来（公式表没挂 / 变量对不上）/ 引擎那一发 ≤ 0 ⇒ 一个字段都不写
      （与接线前一字不差：引擎照旧用自己那一口）。
    """
    ctx = getattr(battle, "_fire_ctx", None)
    if not isinstance(ctx, dict) or not isinstance(caster, dict):
        return
    info = ctx.get("info") or {}
    try:
        want = _heal_base_of(battle, caster, info)
    except Exception:                                   # noqa: BLE001
        return
    cur = float(ctx.get("heal") or 0)
    if want <= 0 or cur <= 0:
        return
    ratio = want / cur
    if abs(ratio - 1.0) < 1e-9:
        return
    cur_m = ctx.get("mult")
    ctx["mult"] = (1.0 if cur_m is None else float(cur_m)) * ratio


def _cast_self_cut(battle, caster, info, m, logs):
    """**付血**（狂斩 / 焚身）：出手那一刻先付（真源 §二 那本账是「付：… / 收：…」两步）。

    ★ 为什么这两条走 `route=cast` 而不是与 破势 同一条（命中后的 `engine` 路）：
      ① 真源的账是先付后打，付血与「这一下打没打中」无关（自伤不是命中效果）；
      ② 引擎那条 `if mech and mval` 的门要一个非 0 的**整数** `mech_val`，而这两条的比例
         是 0.12 / 0.35（`int()` 会把它截成 0 ⇒ 门直接关，见文件抬头第 2 条）。
      两格比例都取自 `skill_mech.json` 的 `self_dmg_pct`（含基数与上限），本函数不写数。
    """
    _self_cut(battle, caster, m, logs)


_CAST_VERBS.update({
    "protect": _cast_protect,
    "cleanse": _cast_cleanse,
    "hot": _cast_hot,
    "rampage": _cast_self_cut,
    "immolate": _cast_self_cut,
})


@EF.register_action("aeth_on_cast")
def aeth_on_cast(battle, caster, target, params, logs):
    """出手那一刻的机制分发（`act_cast` 触发）：只接 route=cast 的那几条。

    engine 路的那几条由引擎自己的机制路落 —— 两边**互斥**（表里声明，探针钉着），
    所以这里对它们直接放行（一个字段都不写）。
    """
    info = (getattr(battle, "_fire_ctx", None) or {}).get("info") or {}
    mech = str(info.get("mech") or "")
    m = of(mech)
    if not m or m.get("route") != "cast":
        return
    fn = _CAST_VERBS.get(mech)
    if fn is None:
        raise KeyError("机制 %r 声明 route=cast 但没有实现（表与代码对不上）" % (mech,))
    fn(battle, caster, info, m, logs)


@EF.register_action("aeth_block_roll")
def aeth_block_roll(battle, caster, target, params, logs):
    """格挡（骑士被动「格挡回誓」）：掷一次 → 中了就按**真源 F10** 打折 + 回守誓。

    ★ 为什么掷骰在内容侧：引擎那条 `block` 通道**只算减免、不发事件**（`landing` 里滚完就完了），
      而这条被动要的是「**格挡成功**」这个信号；真源 `02_数值宪法/01_属性字典` F10 自己写着
      「触发率**另配**（走被动/装备，不在这里定）」⇒ 掷骰放内容侧、减免照走真源那条公式。
    ★ 数字全部来自声明：概率在机制表（`block_chance`）· 减免走 `formula_table.json` 的
      `F10_block_mit`（**求值，不重写**）· 回誓在 `resources.json` 的渠道表（`on_block`）+
      本机制自己那半（`oath_bonus`）。
    ★ fail-closed：资源表没挂 / 被动没到等级 ⇒ 一个字段都不写（与接线前一字不差）。
    """
    if not RES.table():
        return
    if _passive_mech(caster) != "block_oath":       # 不是这个职业的被动 / 等级没到 ⇒ 不格挡
        return
    m = of("block_oath")
    chance = _num(m, "block_chance")
    ctx = getattr(battle, "_fire_ctx", None)
    if chance <= 0 or not isinstance(ctx, dict):
        return
    if random.random() >= chance:
        return
    # 减免：真源 F10（从声明式公式表求值 —— 代码里不重写那条公式）
    from . import apply as _AP
    try:
        blk = float(ST.actor_stats(battle, caster).get("block", 0) or 0)
        mit = float(_AP._table().eval("F10_block_mit", {"block": blk}))
    except Exception:                                   # noqa: BLE001
        mit = 0.0
    if mit <= 0:
        # 【L408】mit ≤ 0 整条返回：不打折、不回誓、不播报。
        #   改前实跑（block=0 · F10=0.0）：掉血 100（零减免正确）、
        #   守誓层 0→26（额外 +20）、仍播「举盾挡下 —— 这一下轻了 **0 点**」。
        #   与本函数 docstring 的 fail-closed 承诺相反（「→ 一个字段都不写」）。
        return
    cur = ctx.get("mult")
    ctx["mult"] = (1.0 if cur is None else float(cur)) * (1.0 - mit)
    # 回誓：账本那条（渠道表）+ 这条被动自己那半
    key = RES.res_of_class(str(caster.get("class_name") or ""))
    oath = int(RES.gain_of(key, "on_block")) + int(_num(m, "oath_bonus"))
    got = RES.add(battle, caster, key, oath, logs) if key and oath else 0
    try:
        _dmg = float(ctx.get("dmg") or 0)
    except Exception:                                   # noqa: BLE001
        _dmg = 0.0
    logs.append(T("COMBAT_MECH_BLOCK", t=int(round(_now(battle))),
                      n=int(_dmg * mit), oath=oath, cur=got))


# ══════════════════════════════════════════════════════════════
# 「清空型资源」的层数快照 + 兑现端（`mark_burst`：印记 → 引爆）
# ══════════════════════════════════════════════════════════════
#: 层数快照那一格（挂在 actor 身上：`{资源码: 层数}`）—— 只服务「扣费/清空发生在出手之前」
#: 那一类资源（今天的实例 = 法师的印记）。与 `_res_at` / `_mp_at` 同族：都是不落档的临时书签。
_TRACE_KEY = "_res_trace"


def _stacks_of(actor, key: str) -> int:
    """actor 某条资源当前的层数（读 `effects[key].stacks`；没有条目 ⇒ 0）。"""
    try:
        return int(float((((actor.get("effects") or {}).get(key)) or {}).get("stacks") or 0))
    except (TypeError, ValueError, AttributeError):
        return 0


def _burst_mech(info: dict) -> dict:
    """这一次出手的机制声明里那份 `burst`（今天只有 `mark_burst`）—— 名字取 `info["mech"]` /
    `info["mech2"]`（引擎的 `_mech_to_effect` 两格都支持）。

    两格都取不到、或那条机制没声明 `burst` ⇒ 空 dict（调用方一律「一个字段都不写」）。
    """
    for fld in ("mech", "mech2"):
        m = of(str((info or {}).get(fld) or ""))
        if m.get("burst"):
            return m
    return {}


def _trace_keys() -> frozenset:
    """表里**声明了 `burst.trace` 的资源码**（现读机制表 ⇒ 加一条带 burst 的机制不用改这里）。

    这一格决定「哪些资源要留清空之前的层数」—— 名字住在机制表里，代码只读不写。
    """
    return frozenset(str((m.get("burst") or {}).get("trace") or "")
                     for m in mechs().values()) - {""}


@EF.register_action("aeth_burst_trace")
def aeth_burst_trace(battle, caster, target, params, logs):
    """出手那一刻：给「清空型资源」记一行**层数快照**（`actor["_res_trace"][<资源码>]`）。

    ★ 为什么要有这一格：引擎的扣费（`res_cost`）与清空（`consume_all`）都发生在 `act_cast`
      **之前**（`do_skill` 的次序：预检 → 扣费 → 冷却 → `act_cast` → 命中 / 伤害）⇒ 兑现端
      （`dmg_calc`，伤害算出之后）**读不到印记层数**。所以层数一变（= 出手那一刻）就顺手记一行；
      兑现端读它、用完即销（一次性 —— 没重新铺印记的第二发不再加成）。
    ★ **判据是「这一手真涨了那条资源」**（技能自己声明的 `res_gain`），不是「这一手带不带 burst」：
      涨层的那几条（星屑 / 焰痕 / 冰棱）自己不带 burst 机制；而带 burst 的那两条（引燃 / 垂星）
      出手时印记已经被扣费/清空 —— 两边都不许拿自己那一格去覆盖快照（否则兑现端读到 0）。
      盯哪条资源由**机制表里 `burst.trace`** 现读（`_trace_keys()`），代码里零资源名。
    ★ 挂载顺序：本动作排在 `content/resources.py::aeth_res_on_cast` **之后**
      （`player_triggers()` 里最后追加）⇒ 记下的是「这一手加完之后」的层数。
    ★ fail-closed：表里没有 burst 声明 / 这个 actor 没有那条资源 / 这一手不涨它 ⇒ 一个字段都不写。
    """
    actor = caster
    if not isinstance(actor, dict):
        return
    key = RES.res_of_class(str(actor.get("class_name") or ""))
    if not key or key not in _trace_keys():
        return
    info = _ctx_info(battle) or _info(params)
    if int((info.get("res_gain") or {}).get(key) or 0) <= 0:
        return                          # 这一手不涨这条资源（含引燃/垂星自己那一手）⇒ 快照保持
    actor.setdefault(_TRACE_KEY, {})[key] = _stacks_of(actor, key)


def _burst_mult(battle, actor, info: dict) -> float:
    """这一发的层数乘区（`mark_burst`）：`(power + N × 每层系数) / power`。

    N = 出手**之前**那一刻的层数（快照）；系数与 base 的名字都取自表里的 `burst`
    （`rate` / `power`）⇒ 本层不认任何机制名、也不写任何数。
    ★ 快照**一次性**：只有「真要用它」时才销（声明坏了 / N=0 ⇒ 不销，留给下一次机会）。
    ★ 没有快照 ⇒ 1.0（一个字段都不写 —— 与接线前一字不差）。
    """
    m = _burst_mech(info)
    if not m or not isinstance(actor, dict):
        return 1.0
    b = m.get("burst") or {}
    key = str(b.get("trace") or "")
    tr = actor.get(_TRACE_KEY)
    if not key or not isinstance(tr, dict) or key not in tr:
        return 1.0
    try:
        rate = float((info or {}).get(str(b.get("rate") or "mech_val")) or 0)
        power = float((info or {}).get(str(b.get("power") or "power")) or 0)
        n = int(tr.get(key))
    except (TypeError, ValueError):
        return 1.0
    if n <= 0 or rate <= 0 or power <= 0:
        return 1.0
    tr.pop(key, None)                                  # ★ 用完即销（一次性）
    # ★ 清空之后把条目**摆回 0 层**：引擎的 res_cost 判据是「**有**该条目才须足额」
    #   （`_skill_usable` 里 `if not isinstance(entry, dict): continue`）—— 条目被
    #   `consume_all` 连容器一起清掉之后，那道门就跟着消失了 ⇒ 摆回 0 层才是真闸门
    #   （与 `content/resources.py::aeth_res_start` 开战那一下同一条口径；真源
    #   04_法师_v2.md §三「引燃 先得有一层才放得出来」）。
    RES.set_to(actor, key, 0)
    return (power + n * rate) / power


@EF.register_action("aeth_daze")
def aeth_daze(battle, caster, target, params, logs):
    """砸晕（垂星的第二格机制 `star_stun`）：给目标挂一条**控制**（`mode=skip`）。

    与 `silence_lock`（`mode=no_skill`：禁技、还能普攻）**不同轴**：这一条是**整手作废** ——
    引擎的行动前检查读 `mode`，`skip` = 这一手跳过 + 条目消费掉（真源 02_战斗机制 §〇·五
    「控制 = 剥夺一次行动机会」）。时长只认技能自己声明的 `mech2_val`（表里 `turns: "mech2_val"`），
    表里不抄第二份数。
    """
    m = _mech_of(params)
    key = str(m.get("state") or "")
    turns = _turns(m, params)
    mode = str(m.get("mode") or "")
    if target is None or not actor_alive(target) or not key or turns <= 0 or not mode:
        return
    if not state_rule(key):
        return
    _put(target, key, _now(battle) + turns, mode=mode)
    logs.append(T("COMBAT_MECH_DAZE", t=int(round(_now(battle))),
                  name=target.get("name", ""), turns=int(turns)))


# ══════════════════════════════════════════════════════════════
# 装配面：两条给引擎的供体（E5 两段耗时 · E6 出手前否决）
# ══════════════════════════════════════════════════════════════
#: 行动类别名「技能」—— 与 `content/rules/action_base.json` 的键同源，代码里不新造词
_SEG_SKILL = "skill"


def segment_plan(actor, action, entry):
    """E5 `segment_plan_fn` 供体：**这一次行动的两段耗时**（技能 dict 自己声明的那两段）。

    只在「行动类别 = 技能」且 `entry` 是技能 dict 时声明；其余一律 `None`
    （引擎落回 `action_base.json` 的类别基准）。

    ★ **普攻（`attack`）那条路今天不喂 entry** —— 本职业 basic 技能自己声明的那两段
      （真源 00_重做总纲 §五·六 对 basic 也成立）**还没接**：开它会把难度底线顶开
      （零加点骑士 vs 精英 lv9：0/40 → 33/40 · 层主低 4 级 0/36 → 9/36），而同一份真源的
      「一次行动（F6）」六列是**类别 attack** 的账 ⇒ 单独立条、要真源先裁口径（D4）。

    ★ **原样透传**（只剥掉没声明的那一段），不在内容侧判形状：形状守卫是引擎那**一个**口
      （`saintess_engine/_validators.segment_of`），内容侧再判一遍就是双源
      （`schemas/skills.schema.json` 的 anyOf 已经声明了那三形态）。

    ★ 纯函数约束（引擎把同一份回执喂给「排落地时刻」与「推 ct」两处）：只依赖入参，
      不读 `battle._now`、不写任何字段 —— 两次必须同值。
    """
    if not isinstance(entry, dict) or action != _SEG_SKILL:
        return None
    out = {}
    for k in ("cast", "recover"):
        v = entry.get(k)
        if v is not None:
            out[k] = v
    return out or None


def _used_of(battle) -> dict:
    """本场「每场一次」那类机制的用量表 —— 挂在引擎的 **`battle.flags`**（战斗级跨手标记）上。

    ★ 2026-09-27：原先挂在 `Battle` 的临时属性（`setattr(battle, "_aeth_mech_used")`）——
    而本包「场」这条路由**每一手都要 `to_state`/`from_state` 往返一次**，临时属性过不了往返
    ⇒ 计数每手清零，「每场一次 / 每场几层」整族机制形同不存在（焚身四轮试玩都复现）。
    引擎侧 `serialize.py` 已把 `flags` 那一格接上（读写两端）⇒ 这一格随档走、跨手有效。
    """
    return battle.flags


def _flag(m: dict, key: str) -> bool:
    """表里那个开关（`{"value": true, "_src": …}` 形态）。"""
    d = m.get(key)
    if isinstance(d, dict):
        d = d.get("value")
    return bool(d)


def skill_gate(battle, actor, info):
    """E6 `skill_gate_fn` 供体：**出手前**那一问（放不放 / 拦下说什么）—— 规则全在表里。

    今天管两条（都在 `skill_mech.json` 的声明里，本函数一个数都不写）：

      ① `min_hp_pct`（狂斩）：真源 02_狂战士_v2 §二「付：自伤 12% = 32.6 点（不能把自己打死
         —— **血 < 12% 时这一手不可用**）」⇒ 判据 = 「付完还得剩得下血」：`hp − 这一笔 ≥ 1`
         （这一笔的算式与 `_self_cut` 同源，见 `_self_cut_amount`）。
      ② `once_per_battle`（焚身）：真源 §三「一场战斗最多一次，而且要看修女在不在」——
         计数记在**放行那一刻**（引擎这个口回 `None` = 这一手真的会放）。

    回执形状（引擎 `_use_gate_text` 那份契约）：`None` = 放行；非空 str/序列 = 拦下并回话。
    """
    m = of(str((info or {}).get("mech") or ""))
    if not m:
        return None
    pct = _num(m, "min_hp_pct")
    if pct > 0:
        need = _self_cut_raw(battle, actor, m)          # 「该付多少」（不含保底那道闸）
        hp = int((actor or {}).get("hp") or 0)
        # 审计 L409：原写法 hp < need 在 hp == need 那一档**放行**（付完按真源剩 0 血 = 死），
        #   而本函数 docstring（+ 表里 min_hp_pct._src）自写的判据是「hp − 这一笔 ≥ 1」。
        #   ⇒ 按 docstring 收紧 1 点；保底留 1 血那一档仍由 _self_cut_amount 独立兜着。
        if hp - need < 1:                               # 真源「付完还得剩得下血」
            return [T("COMBAT_MECH_HP_GATE", name=str((info or {}).get("name") or ""),
                      need=need, cur=hp)]
    if _flag(m, "once_per_battle"):
        key = str((info or {}).get("name") or "")
        box = _used_of(battle)
        if box.get(key):
            return [T("COMBAT_MECH_ONCE", name=key)]
        box[key] = 1
    return None


def player_triggers() -> dict:
    """玩家 actor 要挂的注入点（引擎的事件总线 + 承伤乘区 + B4-1 的常驻被动那条路）。

    ★ 挂载面**从 `_TRIGGER_VERBS` 生成**（不手写字面量）：表里声明了几个事件、这里就挂几个，
      多挂一个（空跑）少挂一个（接了永不触发）都在 `_validate` 里当场抛。
    ★ 职业资源那几条（`resources.json`）由 `content/resources.py::triggers()` 合并进来 ——
      同一个事件允许多个动作（例：`taken_calc` 上「减伤乘区」与「格挡」各一个），引擎按序跑。
    ★ 另外三个口**不是机制**（它们没有机制名，也不进机制表）：它们是**引擎事件 → 内容槽位**
      那类读端，只有该事件真发生时才有话：
      · `heal_calc` → `aeth_heal_calc`：治疗量的**基数**（F8 · 治疗强度是那一格的基数）；
      · `act_cast` 追加 `aeth_burst_trace`：「清空型资源」的层数快照（兑现端在伤害那一步才出手）；
      · ★ fix-k-critline `crit` → `aeth_crit_line`：**暴击/幸运一击那一行**
        （`COMBAT_CRIT` 槽位原先全仓零读端 —— 引擎在 `actions.py` 真掷
        `random.random() < crit`，玩家屏上却一个字都不播）。动词就在本文件（下同 ——
        `aeth_*` 全族一处；★ 实测：动词若放到指令模块（`content/cmds_battle.py`）里，
        走 `load_stack()+install()` 那条路（不 import 命令模块）的进程里
        `EF.missing_actions` 会非空 ⇒ 引擎**静默跳过**，那一行一个字都不出）。
    """
    out = {
        "act_cast": [{"action": "aeth_on_cast"}],
        "taken_calc": [{"action": "aeth_mitigate"}],
        # ★ fix-k-critline：`crit` 是**引擎事件**（不是机制 —— 没有机制名、不进机制表），
        #   所以在这一处手挂（与 `act_cast` / `taken_calc` 那两条同族）。
        "crit": [{"action": "aeth_crit_line"}],
    }
    for ev, verb in _TRIGGER_VERBS.items():
        out.setdefault(ev, []).append({"action": verb})      # ★ 追加，不覆盖（taken_calc 上有两个）
    for ev, acts in (RES.triggers() or {}).items():          # 职业资源渠道（B4-1 那批的声明）
        out.setdefault(ev, []).extend(acts)                  # ★ 同一个事件允许多个动作（引擎按序跑）
    # ★ 顺序要紧：快照那条**必须**排在 `aeth_res_on_cast` 之后（它记的是这一手加完之后的层数）
    out.setdefault("act_cast", []).append({"action": "aeth_burst_trace"})
    out.setdefault("heal_calc", []).append({"action": "aeth_heal_calc"})
    return out


# ══════════════════════════════════════════════════════════════
# B4-1：T1 11–20 那批技能用的动词（11 条主动 + 6 条被动）
# ══════════════════════════════════════════════════════════════
def _passive_mech(actor) -> str:
    """这个 actor **职业的那个被动**用的是哪条机制（现算：skills 域按 owner_class + kind_key 挑）。

    只认域里那两格：`owner_class`（ASCII）与 `kind_key`（ASCII `passive`）—— 一个中文字都不比
    （`scripts/rebuild_skills.py` 算出 `kind_key`，`probe_copy` ⑮ 钉着「中文枚举不当机器键」）。

    ★ **解锁等级**必须一起看：被动在域里也带 `lv`（真源 05_系统总表「职业被动 P1 六条
      （16–20 级开）」⇒ 六条都是 lv 16）。等级没到 ⇒ 回空串（**这个人的被动还没开**）。
      少了这一道，一个 13 级的号就白拿了 16 级的被动 —— 实测就是这么把
      `probe_combat ④`「层主低 4 级（13）单刷打不过」那条钉死的判据撞红的（基线 0/36 →
      带了被动 3/36）。**这一道不是可选项**：它与 `combat._default_skills` 的等级闸是同一条口径。
    """
    from . import skills_lookup as _SL

    cls = str((actor or {}).get("class_name") or "")
    if not cls:
        return ""
    lv = int((actor or {}).get("level") or 0)
    for sid, rec in _SL.skills().items():
        if str(sid).startswith("_") or not isinstance(rec, dict):
            continue
        if rec.get("owner_class") != cls or rec.get("kind_key") != "passive" or not rec.get("mech"):
            continue
        if int(rec.get("lv") or 1) <= lv:
            return str(rec["mech"])
    return ""


def _rules_mounted() -> bool:
    """那两张表挂上了没有（`EFFECT_RULES` 非空）—— 常驻被动那条路的 fail-closed 门。"""
    from ext_combat.battle import game_config as _GC

    return bool(_GC.get_effect_rules())


@EF.register_action("aeth_self_cut")
def aeth_self_cut(battle, caster, target, params, logs):
    """**付血**（血债 / 狂态 / 横扫 三条共用）：比例只认机制表里那条 `self_dmg_pct`。"""
    m = of(_info(params).get("mech"))
    if m:
        _self_cut(battle, caster, m, logs)


@EF.register_action("aeth_oath_shield")
def aeth_oath_shield(battle, caster, target, params, logs):
    """誓约壁垒（骑士 · 11 级）：花守誓换一张**吸收型**的墙（不是减伤率 —— 另一条通道）。

    盾值 = 生命上限 × 表里那个比例（现算）；时长 = 域里 `mech_val`（刻）。落地走引擎现成的
    `shield` 动词（**引擎那一口**的护盾落点 + 它那句「获得护盾 N 点」），不自己另写一套护盾结算。

    ★ 状态容器收口第 2 批（2026-09-28）· **本文件这一处是「透传」，不是包侧写口**：
      它走的是**引擎自己的** `act_shield`（`effects.py:554`）—— 引擎那半会把那一口改写成
      `open_entry(..., value=…, expire=…)` 并删掉 `shields` 容器（设计案 §1.1 把 `act_shield`
      列在**引擎文件**里，不在包侧清单里）。所以本包**一个字不用改**就会跟着走新形状。
      ★ 正因为如此本包**不许**在这里自己拼条目 dict、也不许自己发 `battle.effects.shield_gain`
      那条 cue —— 那是引擎那个唯一写入口的活（内容侧重发 = 同一句话出两遍）。
      ★ 内容侧真正要交的是**声明**：`skill_mech.json` 里 `aeth.oath_shield` 那条 `absorb: true`
        （吸收型由声明决定，引擎不认「盾」这个专名）—— 见 `mech.absorb_state_keys()`。
    """
    m = of("oath_shield")
    if not isinstance(caster, dict):
        return
    pct = _num(m, "shield_pct")
    turns = _turns(m, params)
    val = int(round(int(ST.actor_max_hp(battle, caster) or 0) * pct))
    if val <= 0 or turns <= 0:
        return
    EF.act_shield(battle, caster, caster,
                  {"on": "caster", "value": val, "turns": int(turns), "key": _SHIELD_KEY}, logs)


@EF.register_action("aeth_hold_line")
def aeth_hold_line(battle, caster, target, params, logs):
    """断后（骑士 · 14 级）：把自己的**下一次行动**推后 + 这段里承伤打对折。

    ★ 与 `aeth_advance_ct`（抢拍）对称：那里是 `ct −= adv`，这里是 `ct += delay`；两处的
      `ct` 都已经是**这一手之后**的下一个到点时刻（`battle.human_act` 的次序：T0 登记 →
      推 ct → 推进期间才落地）—— 所以动的是下一次行动，不是当前这一手。
    """
    m = of("hold_line")
    d = _num(m, "delay_ticks")
    if not isinstance(caster, dict) or not state_rule(str(m.get("state") or "")):
        return
    now = _now(battle)
    if d > 0:
        caster["ct"] = float(caster.get("ct") or now) + d
    _grant(battle, caster, m, params, logs, "COMBAT_MECH_REARGUARD",
           ticks=int(d), pct=_pct_of_rule(state_rule(str(m.get("state") or ""))))


@EF.register_action("aeth_blood_price")
def aeth_blood_price(battle, caster, target, params, logs):
    """血债（狂战士 · 11 级）：血已经付过了（`aeth_self_cut`），这里挂上那段攻击增益。"""
    m = of("blood_price")
    _grant(battle, caster, m, params, logs, "COMBAT_MECH_BLOODDEBT",
           pct=abs(_panel_delta(state_rule(str(m.get("state") or "")))))


@EF.register_action("aeth_riposte")
def aeth_riposte(battle, caster, target, params, logs):
    """狂态（狂战士 · 14 级）：挂上「谁打我谁挨一刀」那段态 —— 消费端是 `on_taken`。"""
    m = of("riposte")
    _grant(battle, caster, m, params, logs, "COMBAT_MECH_RIPOSTE",
           pct=int(round(_num(m, "reflect_atk_mult") * 100)))


@EF.register_action("aeth_pin_down")
def aeth_pin_down(battle, caster, target, params, logs):
    """箭止（游侠 · 11 级）：打断是引擎那一条动词干的，这里只挂减速那半截。"""
    m = of("pin_down")
    if target is None or not actor_alive(target):
        return
    key = str(m.get("state") or "")
    turns = _turns(m, params)
    if not key or turns <= 0 or not state_rule(key):
        return
    _put(target, key, _now(battle) + turns)
    logs.append(T("COMBAT_MECH_PINDOWN", t=int(round(_now(battle))),
                  name=target.get("name", ""), turns=int(turns),
                  pct=abs(_panel_delta(state_rule(key)))))


@EF.register_action("aeth_silence_lock")
def aeth_silence_lock(battle, caster, target, params, logs):
    """静默（法师 · 11 级）：给目标挂一条**控制**（引擎认的那一格是条目上的 `mode`）。

    `mode` 取表里声明的那个值（`no_skill` = 接下来那一手技能转普攻）；引擎的行动前检查读它。
    ★ 这一条**不认态名**：谁带 `mode` 谁就是控制（净罪那半边也是同一条判据）。
    """
    m = of("silence_lock")
    key = str(m.get("state") or "")
    turns = _turns(m, params)
    mode = str(m.get("mode") or "")
    if target is None or not actor_alive(target) or not key or turns <= 0 or not mode:
        return
    if not state_rule(key):
        return
    _put(target, key, _now(battle) + turns, mode=mode)
    logs.append(T("COMBAT_MECH_SILENCE", t=int(round(_now(battle))),
                  name=target.get("name", ""), turns=int(turns)))


@EF.register_action("aeth_frost_veil")
def aeth_frost_veil(battle, caster, target, params, logs):
    """霜障（法师 · 14 级）：一条状态吃两头 —— 承伤乘区（−35%）与自己的面板（matk ×0.8）。"""
    m = of("frost_veil")
    _grant(battle, caster, m, params, logs, "COMBAT_MECH_FROSTVEIL",
           pct=_pct_of_rule(state_rule(str(m.get("state") or ""))),
           cost=abs(_panel_delta(state_rule(str(m.get("state") or "")))))


@EF.register_action("aeth_night_watch")
def aeth_night_watch(battle, caster, target, params, logs):
    """守夜（修女 · 14 级）：承伤 −35% + 这段里治疗量 +25%（她把灯挪到自己跟前）。"""
    m = of("night_watch")
    _grant(battle, caster, m, params, logs, "COMBAT_MECH_NIGHTWATCH",
           pct=_pct_of_rule(state_rule(str(m.get("state") or ""))),
           gain=abs(_panel_delta(state_rule(str(m.get("state") or "")))))


@EF.register_action("aeth_bleed")
def aeth_bleed(battle, caster, target, params, logs):
    """割喉（刺客 · 11 级）：目标挂**叠层**的流血（cap 取规则表；到期 = 域里的 mech_val）。

    周期怎么跳由引擎按规则表里的 `period` 走（dir=damage · atk 系数 × **持刀那一刻**的施法者
    面板 —— 快照由引擎的 `note_dot_source` 记，本层不自己算 DoT 的账）。
    """
    m = of("bleed")
    key = str(m.get("state") or "")
    turns = _turns(m, params)
    cfg = state_rule(key)
    if target is None or not actor_alive(target) or not key or turns <= 0 or not cfg:
        return
    ef = target.setdefault("effects", {})
    old = ef.get(key) if isinstance(ef.get(key), dict) else {}
    n = min(int(cfg.get("cap") or 1), int(old.get("stacks") or 0) + 1)
    ef[key] = {"stacks": n, "expire": _now(battle) + turns}
    EF.note_dot_source(battle, target, key, caster)
    # ★ 跳的间隔从**规则表那一条**现读（文案里那个「每 N 刻」不许另写一个数 —— 单源）
    _intv = int(float((cfg.get("period") or {}).get("interval") or 1))
    logs.append(T("COMBAT_MECH_BLEED", t=int(round(_now(battle))),
                  name=target.get("name", ""), turns=int(turns),
                  stacks=n, intv=_intv))


@EF.register_action("aeth_sidestep")
def aeth_sidestep(battle, caster, target, params, logs):
    """侧闪（刺客 · 14 级）：只动闪避那一格（不改承伤乘区 —— 与四个减伤类防御不同轴）。"""
    m = of("sidestep")
    _grant(battle, caster, m, params, logs, "COMBAT_MECH_SIDESTEP",
           pct=abs(_panel_delta(state_rule(str(m.get("state") or "")))))


# ── 常驻被动那条路（route=trigger）的三个动词 ──────────────────────────
@EF.register_action("aeth_on_start")
def aeth_on_start(battle, caster, target, params, logs):
    """开战（`battle_start`，整场一次）：把这个 actor 那个被动里声明的**每一条规则键**挂成常驻态。

    ★ fail-closed 两道：① 那两张表没挂 ⇒ 直接返回（不装配 = 与接线前一字不差）；
      ② 某条规则不在表里 ⇒ 跳过那一条（不写半个字段）。
    """
    if not _rules_mounted() or not isinstance(caster, dict):
        return
    m = of(_passive_mech(caster))
    if not m or m.get("trigger") != "battle_start":
        return
    ef = caster.setdefault("effects", {})
    for key in (m.get("rules") or {}):
        if not state_rule(key):
            continue
        ef[key] = {"stacks": 1, "expire": None}          # 常驻：不到期


@EF.register_action("aeth_on_dmg_calc")
def aeth_on_dmg_calc(battle, caster, target, params, logs):
    """攻击方乘区（`dmg_calc`）—— 引擎这**一个**事件在这里只有一个动词，所以两件事共用它：

    ① **血的乘区**（血勇那类常驻被动）：按出手那一刻的血线现算（血少就打得狠）——
       现算而不是挂态 ⇒ 「治疗回到线上」自动不再生效，不留过期态（见机制表那条 judge）；
    ② **层数乘区**（印记 → 引爆的兑现端）：技能声明了 `burst` 的那一发，按出手**之前**那一刻的
       层数快照加成（`_burst_mult`；数值全在表里那三格，本函数不认任何机制名）。

    两半各写各的乘区、最后一次性折进 `ctx["mult"]`（都不命中 ⇒ 一个字段都不写）。
    """
    if not _rules_mounted():
        return
    ctx = getattr(battle, "_fire_ctx", None)
    if not isinstance(ctx, dict):
        return
    actor = caster if isinstance(caster, dict) else ctx.get("actor")
    if not isinstance(actor, dict):
        return
    mult = _burst_mult(battle, actor, ctx.get("info") or {})        # ② 层数乘区（印记引爆）
    m = of(_passive_mech(actor))                                    # ① 血的乘区（常驻被动）
    if m and m.get("trigger") == "dmg_calc":
        below = _num(m, "hp_below")
        _dm = _num(m, "dmg_mult")
        mx = float(ST.actor_max_hp(battle, actor) or 0)
        hp = float(actor.get("hp") or 0)
        if _dm > 0 and below > 0 and mx > 0 and hp / mx < below:
            mult *= _dm
    if mult == 1.0:
        return
    cur = ctx.get("mult")
    ctx["mult"] = (1.0 if cur is None else float(cur)) * mult


@EF.register_action("aeth_on_taken")
def aeth_on_taken(battle, caster, target, params, logs):
    """承伤后（`on_taken`）：把「谁打我谁挨一刀」那一类态兑现成对**攻击者**的伤害。

    引擎零知识：哪些状态算反击全看规则表里那条 `reflect_atk_mult`（本函数不认任何态名）。
    反击伤害 = 持有者 atk × 那个系数（现算）；攻击者缺失 / 已死 ⇒ 不反击（不静默打空气）。
    """
    if not _rules_mounted() or not isinstance(caster, dict):
        return
    ctx = getattr(battle, "_fire_ctx", None)
    src = (ctx or {}).get("source") if isinstance(ctx, dict) else None
    if not isinstance(src, dict) or not actor_alive(src):
        return
    now = _now(battle)
    for k, e in list((caster.get("effects") or {}).items()):
        if not isinstance(e, dict):
            continue
        exp = e.get("expire")
        if exp is not None and float(exp) <= now:
            continue
        mult = float(state_rule(k).get("reflect_atk_mult") or 0)
        if mult <= 0:
            continue
        dmg = int(float(ST.actor_stats(battle, caster).get("atk", 0) or 0) * mult)
        if dmg <= 0:
            continue
        real = LD.deal_damage(battle, None, src, dmg, logs)
        logs.append(T("COMBAT_MECH_TRANCE", t=int(round(_now(battle))),
                      name=src.get("name", ""), n=real))


# ── ★ fix-k-critline：暴击那一行（引擎 `crit` 事件 · 内容侧唯一读端）──────────
@EF.register_action("aeth_crit_line")
def aeth_crit_line(battle, caster, target, params, logs):
    """暴击命中那一刻那一行（引擎 `crit` 事件 → `texts` 槽位 `COMBAT_CRIT`）。

    ★ 病根（接之前）：引擎 `actions.py::_single_target_pipeline` **真在掷** ——
      `is_crit = random.random() < st["crit"]`，命中后再掷 30% 追加一次「幸运一击 ×1.3」
      （1.5 × 1.3 = 1.95 倍，与试玩实测那 1.5~1.9 倍跳变对得上）。可 `crit` 是**事件**：
      引擎只渲染裸伤害行（`battle.landing.damage`），内容侧没人消费它 ⇒ 玩家打了整轮
      也看不到「暴击」两个字（`COMBAT_CRIT` 槽位当时**全仓零读端**）。而
      `effect_triggers.fire` 只跑**主体 actor 自己**声明的触发器 ⇒ 读端必须挂在玩家 actor
      的挂载面上（`combat.player_actor` → `player_triggers()` 的 `crit` 那一格）。

    ★ 为什么动词落在**本文件**而不是指令模块（分支 `_notes.md` 里那三步改法当时写的是
      `content/cmds_battle.py` —— 那批的文件面碰不到 mech.py 才那么写）：`@register_action`
      是 import 期跑的装饰器 ⇒ 注册**取决于那条 import 路径**。实测把动词放进指令模块后，
      走 `load_stack()+install()`（不 import 命令模块）的进程里 `EF.missing_actions` 非空、
      引擎**静默跳过**那一行（`probe_mech` 那条形状判据当场红）。本文件由 `combat.py` 在
      模块级 import ⇒ 两条路都注册得上。判据 `probe_mech` 里「挂载面 + 动词两半都在」钉着。

    ★ 五个值全从**事件上下文**与 actor 现取（代码里一个中文字都不写 —— 文案在 texts 域，
      `params` 照它声明的 [act, dmg, t, tgt, who]）：
      · `who` = 出手那个 actor 的名字；
      · `act` = 引擎给过来的那条技能**自己的名字**（`_fire` 的 ctx.info.name：普攻也是域里
        那一条的名字，如「短刃」）—— 分隔符照真源那份战斗日志样张的写法（`你 · 攻击 · 伐木工`）；
      · `tgt` = 挨这一下的那个 actor 名字；
      · `t`   = 现在这一刻的游戏刻（引擎的绝对时刻）；
      · `dmg` = 引擎这一手算出来的伤害（ctx.dmg = 伤害管线那一个总数，**落地前**的数）。
    ★ ★ 已知口径（引擎只给这一个数 · 内容侧不编第二个）：落地那一侧还会叠**等级压制 / 元素**
      这类加成（`landing._lv_pressure` 等）⇒ 这一行的数与紧上面那行裸伤害行**不一定逐值相同**
      （实测：这一行 76 点、落地行 82 点；被闪避／被护盾吃掉的场合，这一行照样按管线数报，
      而裸伤害行是「闪避了攻击！」）。`crit` 事件上没有「落地后那一个数」，内容侧拿不到 ——
      要收紧它得引擎在 ctx 里多给一格（登记在分支 `_notes.md`，属引擎立项）。
    ★ 取不到的**不编**：`info` 缺名字 ⇒ `act` 空着；挨打那个 actor 不在 ⇒ `tgt` 空着 ——
      这一行照样出（谁打谁挨打、多少伤都在）。这条读端**不读机制表**（它不是机制），
      所以也不吃 `_rules_mounted()` 那道门。
    """
    ctx = getattr(battle, "_fire_ctx", None)
    ctx = ctx if isinstance(ctx, dict) else {}
    actor = caster if isinstance(caster, dict) else ctx.get("actor")
    tgt = target if isinstance(target, dict) else ctx.get("target")
    info = ctx.get("info") if isinstance(ctx.get("info"), dict) else {}
    name = str((actor or {}).get("name") or "")
    tname = str((tgt or {}).get("name") or "")
    logs.append(T("COMBAT_CRIT",
                  t=int(round(float(getattr(battle, "_now", 0) or 0))),
                  who=name,
                  act=(" · %s" % info["name"]) if info.get("name") else "",
                  tgt=(" · %s" % tname) if tname else "",
                  dmg=int(ctx.get("dmg") or 0)))
