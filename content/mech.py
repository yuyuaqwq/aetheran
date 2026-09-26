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


def _self_cut(battle, caster, m: dict, logs) -> int:
    """**付血**（代价那一半的公共实现）—— 按机制表里 `self_dmg_pct` 扣自己。

    三格全在声明里（本函数一个数都不写）：
      · `self_dmg_base` —— 比例的**基数**：`max_hp`（缺省）＝ 生命上限的比例
        （破势 8% / 狂斩 12% / 血债 / 狂态 / 横扫）；`hp` ＝ **当前生命**的比例
        （焚身 35% —— 血越少付得越少，真源 §六③ 那条「满血放太浪费」就是这么来的）。
      · `self_dmg_cap` —— 这一笔的**上限**（缺省 0 = 不设；焚身那句「最多 40 点」）。
      · `self_dmg_pct` —— 比例本身。

    真源口径（02_狂战士_v2.md §二「不能把自己打死」）：**保底留 1 血** —— 引擎没有
    「按血线判某条技能此刻能不能放」的注入面 ⇒ 先兜住下限（那道**可用性门**的账见
    `skill_mech.json` 里 rampage / immolate 的 `halves`）。破势（旧）/ 血债 / 狂态 / 横扫 /
    狂斩 / 焚身 六条共用这一处。
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
    cut = min(cut, max(0, hp - 1))
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
        mx = int(ST.actor_max_hp(battle, caster) or 1)
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
    logs.append(T("COMBAT_MECH_LULLABY", turns=int(turns), per=per))


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
    if mit > 0:
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
    logs.append(T("COMBAT_MECH_BLOCK", n=int(_dmg * mit), oath=oath, cur=got))


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
    logs.append(T("COMBAT_MECH_DAZE", name=target.get("name", ""), turns=int(turns)))


def player_triggers() -> dict:
    """玩家 actor 要挂的注入点（引擎的事件总线 + 承伤乘区 + B4-1 的常驻被动那条路）。

    ★ 挂载面**从 `_TRIGGER_VERBS` 生成**（不手写字面量）：表里声明了几个事件、这里就挂几个，
      多挂一个（空跑）少挂一个（接了永不触发）都在 `_validate` 里当场抛。
    ★ 职业资源那几条（`resources.json`）由 `content/resources.py::triggers()` 合并进来 ——
      同一个事件允许多个动作（例：`taken_calc` 上「减伤乘区」与「格挡」各一个），引擎按序跑。
    ★ 另外两个口**不是机制**（它们没有机制名，也不进机制表）：它们是**数值宪法那两条算式**的消费端 ——
      · `heal_calc` → `aeth_heal_calc`：治疗量的**基数**（F8 · 治疗强度是那一格的基数）；
      · `act_cast` 追加 `aeth_burst_trace`：「清空型资源」的层数快照（兑现端在伤害那一步才出手）。
    """
    out = {
        "act_cast": [{"action": "aeth_on_cast"}],
        "taken_calc": [{"action": "aeth_mitigate"}],
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
        logs.append(T("COMBAT_MECH_TRANCE", name=src.get("name", ""), n=real))
