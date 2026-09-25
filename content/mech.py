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
2. **两条路互斥（不许双源）**：每条机制在表里声明自己走哪条路 ——
     `engine` 引擎自己那条（`effects_from_skill` → 名词 → `EFFECT_ACTIONS`）：断势 / 破势 /
             挑战咆哮 / 不退 / 抢拍 / 庇护 / 晨祷（它们要落地在**命中时**，或引擎本来就够得着）
     `cast`   内容侧那一手（`act_cast` 触发器 → `aeth_on_cast`）：盾墙 / 净罪 / 安神曲
             （盾墙与净罪被 `mval` 门挡着；安神曲是**治疗路不吃 mech**）
   表里声明 + 探针钉着「两条路不许同时出现一条机制」，所以同一个机制只有一处落地。
3. **fail-closed**：加载期能回答的问题不留到运行期（引擎的 handler 异常是**吞掉**的 ——
   运行期抛等于静默）。所以三件事在装配期就抛：表形状坏 / 声明了没注册的动词 /
   域里出现表里没有的机制名（`check_domain`，点名是哪条技能）。
4. **不装配 = 与今天逐字相同**：两张表不挂 ⇒ 引擎的取件口回空表 ⇒ 名词走 `[]`、
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


# ══════════════════════════════════════════════════════════════
# 表：读 + 校验（fail-closed）
# ══════════════════════════════════════════════════════════════
def _validate(t) -> dict:
    """表形状与引用面逐条核 —— 不对就**点名**抛（装配期，不是运行期）。"""
    if not isinstance(t, dict) or not isinstance(t.get("mechs"), dict) or not t["mechs"]:
        raise ValueError("skill_mech.json 得是「一张 mechs 表」：%r" % (t,))
    cast_declared = set()
    for name, m in t["mechs"].items():
        if not isinstance(m, dict):
            raise ValueError("机制 %r 的声明得是 dict：%r" % (name, m))
        route = m.get("route")
        if route not in ("engine", "cast", ""):
            raise ValueError("机制 %r 的 route 只能是 engine / cast / 空（待接线）：%r" % (name, route))
        if m.get("status") not in ("on", "partial", "pending"):
            raise ValueError("机制 %r 的 status 只能是 on / partial / pending：%r" % (name, m.get("status")))
        if m.get("status") in ("pending", "partial") and not m.get("why"):
            raise ValueError("机制 %r 标了 %r 却没写 why（缺口的账不许空着）" % (name, m.get("status")))
        if route == "engine" and not (m.get("actions") or []):
            raise ValueError("机制 %r 声明 route=engine，但没给 actions（动词序列）" % (name,))
        if route == "cast" and not m.get("verb"):
            raise ValueError("机制 %r 声明 route=cast，但没有 verb（写清由哪一手落）" % (name,))
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
    pct = _num(m, "self_dmg_pct")
    cut = 0
    if pct > 0 and isinstance(caster, dict) and caster.get("hp") is not None:
        mx = int(ST.actor_max_hp(battle, caster) or 0)
        hp = int(caster.get("hp") or 0)
        cut = min(int(round(mx * pct)), max(0, hp - 1))       # 保底 1 血（可用性门那半见 why）
        if cut > 0:
            LD.deal_damage(battle, None, caster, cut, logs)
            logs.append(T("COMBAT_MECH_SELF_CUT", n=cut))
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
    """玩家 actor 要挂的两个注入点（引擎的事件总线 + 承伤乘区）。"""
    return {
        "act_cast": [{"action": "aeth_on_cast"}],
        "taken_calc": [{"action": "aeth_mitigate"}],
    }
