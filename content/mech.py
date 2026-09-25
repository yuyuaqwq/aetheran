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
import types

from ext_combat.battle import effects as EF
from ext_combat.battle import landing as LD
from ext_combat.battle import stats as ST
from ext_combat.battle.actors import actor_alive, hostile_sides
from ext_combat.battle.state_effects import state_def

from .cmds_ast import T

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
}

#: 盾容器里那一格的 key（同一个来源反复开 = 同源叠厚，引擎 `act_shield` 的语义）
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
            trigger_declared[ev] = name
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
    if used != set(_TRIGGER_VERBS):
        raise ValueError("route=trigger 的挂载面与表对不上：表里用到 %s · 代码里挂 %s"
                         % (sorted(used), sorted(_TRIGGER_VERBS)))
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


def rules_module() -> types.SimpleNamespace:
    """给 `game_config.load_game_rules(module)` 的模块壳：两张表从**同一张表**算出来。

    ★ route=cast 的机制**不并进 EFFECT_ACTIONS** —— 它们由内容侧那一手（act_cast 触发）落，
      并进去就等于同一件事两处落地（引擎那条名词路也会走一遍）。表里声明、探针钉着。
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
    return types.SimpleNamespace(EFFECT_ACTIONS=ea, EFFECT_RULES=er)


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


def _mval(params: dict) -> float:
    """技能自己那个强度数（`skills` 域的 `mech_val`）—— 唯一来源，本层不重写。"""
    try:
        return float(_info(params).get("mech_val") or 0)
    except (TypeError, ValueError):
        return 0.0


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
    """这次落地持续多久（刻）：`"mech_val"` = 取技能域那个数；dict = 表里那个常数。"""
    t = m.get("turns")
    if t == "mech_val":
        return _mval(params)
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


def _self_cut(battle, caster, m: dict, logs) -> int:
    """**付血**（代价那一半的公共实现）—— 按机制表里 `self_dmg_pct` 扣自己的 max_hp。

    真源口径（02_狂战士_v2.md §一）：自伤按 **max_hp 的比例**算；**保底留 1 血**
    （引擎没有「按条件判某条技能此刻能不能放」的注入面 ⇒ 先兜住下限，别让玩家被自己打死，
    那条 why 见 `_notes.md` 破势那条）。破势（旧）/ 血债 / 狂态 / 横扫 四条共用这一处。
    """
    pct = _num(m, "self_dmg_pct")
    if pct <= 0 or not isinstance(caster, dict) or caster.get("hp") is None:
        return 0
    mx = int(ST.actor_max_hp(battle, caster) or 0)
    hp = int(caster.get("hp") or 0)
    cut = min(int(round(mx * pct)), max(0, hp - 1))
    if cut > 0:
        LD.deal_damage(battle, None, caster, cut, logs)
        logs.append(T("COMBAT_MECH_SELF_CUT", n=cut))
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
    logs.append(T(slot, turns=int(turns), **fields))
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
    logs.append(T("COMBAT_MECH_SEVER", name=target.get("name", ""), turns=int(turns),
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
    logs.append(T("COMBAT_MECH_SUNDER", name=target.get("name", ""), turns=int(turns),
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
    logs.append(T("COMBAT_MECH_TAUNT", turns=int(turns)))


def _ward(battle, caster, target, params, m, logs, slot: str) -> None:
    """减免类状态（不退 / 庇护）的公共落地：写态 + 报一句 —— 数值全在状态规则表里。"""
    holder = _holder(params, caster, target)
    key = str(m.get("state") or "")
    turns = _turns(m, params)
    if not isinstance(holder, dict) or not key or turns <= 0:
        return
    _put(holder, key, _now(battle) + turns)
    logs.append(T(slot, turns=int(turns), pct=_pct_of_rule(state_rule(key))))


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
    logs.append(T("COMBAT_MECH_MATINS", turns=int(turns)))


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
    logs.append(T("COMBAT_MECH_QUICKSTEP", ticks=int(adv),
                  left=int(round(caster["ct"] - now))))


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
        logs.append(T("COMBAT_MECH_IMMUNE"))
    else:
        logs.append(T("COMBAT_MECH_MITIGATE", pct=int(round((1.0 - mult) * 100))))


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
# route=cast 那三条（引擎那两条路都够不着 —— 见文件抬头第 2 条）
# ══════════════════════════════════════════════════════════════
def _cast_protect(battle, caster, info, m, logs):
    """盾墙：免伤到**自己下一次行动之前**（时长现算：`ct − 现在` —— 引擎自己推的那个数）。"""
    key = str(m.get("state") or "")
    now = _now(battle)
    turns = max(1.0, float(caster.get("ct") or 0) - now)
    if not key:
        return
    _put(caster, key, now + turns)
    logs.append(T("COMBAT_MECH_OATHWALL", turns=int(round(turns)),
                  pct=_pct_of_rule(state_rule(key))))


def _cast_cleanse(battle, caster, info, m, logs):
    """净罪：解掉**一个**控制效果（控制的判据 = 引擎的那个 `mode`，不认任何态名）。"""
    ef = caster.setdefault("effects", {})
    hit = next((k for k, e in ef.items() if isinstance(e, dict) and e.get("mode")), None)
    if hit is None:
        logs.append(T("COMBAT_MECH_ABSOLVE_NONE"))
        return
    ef.pop(hit, None)
    logs.append(T("COMBAT_MECH_ABSOLVE"))


def _cast_hot(battle, caster, info, m, logs):
    """安神曲：挂 300 刻再生，每刻回「这一发治疗量的 1/4」（比例来自声明，量现算）。

    治疗量走**与 `do_heal` 同一个口**（`actions.heal_amount`）—— 不另写一套公式。
    条目自带 `period`（引擎优先读它，EFFECT_RULES 不必再声明一份）⇒ 时间轴上真跳。
    """
    from ext_combat.battle import actions as ACT
    from ext_combat.battle import game_config as GC

    key = str(m.get("state") or "")
    turns = _turns(m, {"info": info})
    ratio = _num(m, "hot_ratio")
    # ★ 生命上限：先读 actor 自己那一份，读不到才问聚合面板 —— 不拿任何常数垫上
    #   （静态守卫 `probe_panel ④` 钉着「`\"max_hp\"` 后面跟 `or <数>`」这个指纹）。
    _mx_raw = caster.get("max_hp")
    mx = int(_mx_raw) if _mx_raw else 0
    if mx <= 0:
        mx = int(ST.actor_max_hp(battle, caster) or 1)
    lv = GC.formulas().skill_level_of(caster, info.get("name", "")) if caster.get("class_name") else 0
    heal = ACT.heal_amount(ST.actor_stats(battle, caster), caster, info, lv)
    per = int(round(float(heal) * ratio))
    if not key or turns <= 0 or per <= 0:
        return
    caster.setdefault("effects", {})[key] = {
        "stacks": 1,
        "expire": _now(battle) + turns,
        "period": {"dir": "heal", "interval": 1, "heal_pct": float(per) / float(mx)},
    }
    logs.append(T("COMBAT_MECH_LULLABY", turns=int(turns), per=per))


_CAST_VERBS.update({
    "protect": _cast_protect,
    "cleanse": _cast_cleanse,
    "hot": _cast_hot,
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


def player_triggers() -> dict:
    """玩家 actor 要挂的注入点（引擎的事件总线 + 承伤乘区 + B4-1 的常驻被动那条路）。

    ★ 挂载面**从 `_TRIGGER_VERBS` 生成**（不手写字面量）：表里声明了几个事件、这里就挂几个，
      多挂一个（空跑）少挂一个（接了永不触发）都在 `_validate` 里当场抛。
    """
    out = {
        "act_cast": [{"action": "aeth_on_cast"}],
        "taken_calc": [{"action": "aeth_mitigate"}],
    }
    for ev, verb in _TRIGGER_VERBS.items():
        out[ev] = [{"action": verb}]
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
    `shield` 动词（护盾容器 shields + 它那句「获得护盾 N 点」），不自己另写一套护盾结算。
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
    logs.append(T("COMBAT_MECH_PINDOWN", name=target.get("name", ""), turns=int(turns),
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
    logs.append(T("COMBAT_MECH_SILENCE", name=target.get("name", ""), turns=int(turns)))


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
    logs.append(T("COMBAT_MECH_BLEED", name=target.get("name", ""), turns=int(turns),
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
    """攻击方乘区（`dmg_calc`）：按**出手那一刻**的血线现算（血勇：血少就打得狠）。

    现算而不是挂态 ⇒ 「治疗回到线上」自动不再生效，不留过期态（见机制表那条 judge）。
    """
    if not _rules_mounted():
        return
    ctx = getattr(battle, "_fire_ctx", None)
    if not isinstance(ctx, dict):
        return
    actor = caster if isinstance(caster, dict) else ctx.get("actor")
    m = of(_passive_mech(actor))
    if not m or m.get("trigger") != "dmg_calc" or not isinstance(actor, dict):
        return
    below = _num(m, "hp_below")
    mult = _num(m, "dmg_mult")
    mx = float(ST.actor_max_hp(battle, actor) or 0)
    hp = float(actor.get("hp") or 0)
    if mult <= 0 or below <= 0 or mx <= 0 or hp / mx >= below:
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
        logs.append(T("COMBAT_MECH_TRANCE", name=src.get("name", ""), n=real))
