# -*- coding: utf-8 -*-
"""探针：技能机制层（B3-27）—— 30 条技能里写了 `mech` 的那 14 条**真生效**。

背景（为什么这条探针必须存在）
------------------------------------------------------------------
在 B3-27 之前，本包的两张机制表（`EFFECT_ACTIONS` / `EFFECT_RULES`）**一行都没写**。
后果是**静默**的：14 条带机制的技能里，只有「断势」一条靠「机制名恰好等于引擎动词名」
偶然生效，另外 13 条要么查空表走 `[]`（静默空放），要么连引擎的门都进不去
（`effects_from_skill` 的 `if mech and mval`）。**没有一条判据会因为这个变红** ——
这正是本条探针要补的：把「机制真生效」写成可复算的断言。

三档判据
--------
形状档（①–③）：表读得到 · 与域**双向**对账 · 挂进引擎的两张表与表里的声明逐键相等 ·
                两条路互斥（一个机制只有一处落地）
真跑档（⑤–⑬）：每条机制两路并行核 ——
                ① **端到端**：真走 `cmds_battle` 那条路出手（人放技能），断言它那一条槽位行
                   真出了（= 技能 → 机制 → 动词这条链真通）；
                ② **定向**：在对的时刻直接调那一条动词（无后续推时），把状态形状与数值
                   逐点复算（承伤乘区用**试桩 actor**：无职业 ⇒ 不吃面板/闪避/格挡 ⇒ 逐点对得上）。
                ★ 为什么要两路：端到端那条路会继续把时间推下去，「到下一次行动前」这类状态
                  可能恰好在这一刻到期（盾墙就是），只看终态会把「真生效过」判成「没生效」。
fail-closed 档（④⑭⑮）：不装配 ⇒ 与今天一字不差（两条路各自的装配点）· 四种坏声明各抛一次 ·
                        引擎仓零改动

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_mech.py
Python 用 3.12（3.11 假红）。
"""
from __future__ import annotations

import copy
import os
import subprocess
import sys
import time
import types

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, REPO)
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402

st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
st.install()

from content import cmds_ast as CA                                   # noqa: E402
from content import mech as MECH                                     # noqa: E402
from content import combat as CMB                                    # noqa: E402
from ext_combat.battle import actions as ACT                         # noqa: E402
from ext_combat.battle import effects as EF                          # noqa: E402
from ext_combat.battle import game_config as GC                      # noqa: E402
from ext_combat.battle import landing as LD                          # noqa: E402
from ext_combat.battle import schedule as SCH                        # noqa: E402
from ext_combat.battle import stats as ST                            # noqa: E402
from ext_combat.battle.actors import ActCtx, make_actor              # noqa: E402

fails = []
ok = lambda m: print("  ✓ " + m)
bad = lambda m: (fails.append(m), print("  ✗ " + m))

SKD = st.domain("skills")
MON = st.domain("monsters")
MID = "ms_field_mouse"
DOG = "ms_wild_dog"

#: 机制 → 它那几条技能（**现算**，不写镜像表）
MECH.check_domain()
BY_MECH: dict = {}
for _sid, _rec in SKD.items():
    if _rec.get("mech"):
        BY_MECH.setdefault(_rec["mech"], []).append(_sid)

print("探针：技能机制层（B3-27）")
print("  · 域里带 mech 的技能 %d 条 · 机制 %d 个：%s"
      % (sum(len(v) for v in BY_MECH.values()), len(MECH.mechs()),
         " · ".join("%s×%d" % (k, len(v)) for k, v in sorted(BY_MECH.items()))))

# ══════════════════════════════════════════════════════════════
# ① 形状档：表 · 域双向对账
# ══════════════════════════════════════════════════════════════
_badshape = []
for _n, _m in MECH.mechs().items():
    if _m.get("route") not in ("engine", "cast", ""):
        _badshape.append((_n, "route", _m.get("route")))
    if _m.get("status") not in ("on", "partial", "pending"):
        _badshape.append((_n, "status", _m.get("status")))
    if _m.get("status") in ("pending", "partial") and not _m.get("why"):
        _badshape.append((_n, "缺 why"))
    if _m.get("route") == "engine" and not _m.get("actions"):
        _badshape.append((_n, "route=engine 没 actions"))
    if _m.get("route") == "cast" and not _m.get("verb"):
        _badshape.append((_n, "route=cast 没 verb"))
(ok if not _badshape else bad)("★ 12 条机制的声明形状齐（route / status / why / actions / verb）　%s"
                              % ("全对" if not _badshape else "红：%s" % _badshape[:3]))

_miss = sorted(set(BY_MECH) - set(MECH.mechs()))
_extra = sorted(set(MECH.mechs()) - set(BY_MECH))
(ok if not _miss and not _extra else bad)(
    "★ 域 ↔ 表**双向**对账（域里出现的机制名 %d 个 / 表里 %d 条；域里表里各缺 %s / %s）"
    % (len(BY_MECH), len(MECH.mechs()), _miss or "无", _extra or "无"))

_st = {}
for _m in MECH.mechs().values():
    _st[_m["status"]] = _st.get(_m["status"], 0) + 1
print("  · 状态分布：%s（on = 真生效 · partial = 有半截 pending · pending = 一点没接）"
      % " · ".join("%s %d" % (k, _st.get(k, 0)) for k in ("on", "partial", "pending")))
print("  · 逐条：%s" % " · ".join("%s=%s" % (n, m["status"]) for n, m in sorted(MECH.mechs().items())))

# ══════════════════════════════════════════════════════════════
# ② 挂进引擎的两张表 == 表里的声明（逐键）
# ══════════════════════════════════════════════════════════════
_ea, _er = GC.get_effect_actions() or {}, GC.get_effect_rules() or {}
_want_ea = sorted(n for n, m in MECH.mechs().items() if m.get("route") == "engine")
_want_er = sorted({k for m in MECH.mechs().values() for k in (m.get("rules") or {})})
(ok if sorted(_ea) == _want_ea else bad)(
    "★ `EFFECT_ACTIONS` 的键 == route=engine 的机制（引擎侧 %s）" % (sorted(_ea),))
(ok if sorted(_er) == _want_er else bad)(
    "★ `EFFECT_RULES` 的键 == 表里 states 声明的全部规则（引擎侧 %s）" % (sorted(_er),))
_missv = EF.missing_actions(MECH.declared_actions())
(ok if not _missv else bad)(
    "★ 表里引用的动词都真注册了（%s —— 声明了没实现 = 静默跳过）" % (MECH.declared_actions(),))

# ══════════════════════════════════════════════════════════════
# ③ 两条路互斥 + 机制名不许进 EFFECT_RULES（防叠层劫持）
# ══════════════════════════════════════════════════════════════
_dup = sorted(n for n, m in MECH.mechs().items() if m.get("route") == "cast" and n in _ea)
(ok if not _dup else bad)("★ route=cast 的机制**不并进** EFFECT_ACTIONS（同一件事两处落地 = 双源）　%s"
                          % (_dup or "无"))
_hijack = sorted(set(MECH.mechs()) & set(_er))
(ok if not _hijack else bad)(
    "★ 12 个机制名**不许**出现在 EFFECT_RULES 里 —— 出现了引擎 `_mech_to_effect` 会把它当"
    "「叠层资源」（`if mech and mval` → apply op=add），语义被静默劫持　%s" % (_hijack or "无"))

# ══════════════════════════════════════════════════════════════
# 真跑小件
# ══════════════════════════════════════════════════════════════
def fresh(cls="cls_knight", lv=10, hp=None, mid=MID):
    """真档 → 真 actor → 真战斗（玩家那一侧走 combat.player_actor：触发器也在那儿挂）。"""
    p = {"cls": cls, "level": lv, "uid": "u_mech", "name": "试", "hp": hp}
    return CMB.build(p, [mid], MON, party=1)


def do(b, sid):
    """端到端：活人放一条技能、推进到落地 —— 返回 (caster, target, 日志)。"""
    logs = []
    SCH.advance(b, logs)
    c = b.focus()
    sub, _e, _w = b.human_act("skill", sid, c)
    logs.extend(str(x) for x in (sub or []))
    SCH.settle_landing(b, logs, c)
    return c, (b.sides.get("enemy") or [None])[0], logs


def stub(hp=1000, battle=None):
    """试桩 actor：无职业（不吃面板/闪避/格挡）⇒ 承伤乘区逐点核得出来。"""
    a = make_actor(uid="stub", name="试桩", side="player", kind="monster", max_hp=hp, hp=hp)
    a["triggers"] = MECH.player_triggers()
    if battle is not None:
        battle.add_actor(a, "player")
    return a


def hit(battle, actor, amount=100):
    return LD.deal_damage(battle, None, actor, amount, [])


def apply_mech(battle, caster, target, sid):
    """定向（engine 路）：真调引擎那条机制路（`effects_from_skill` 是引擎现成的 builder）→ 动词。**不推时**。"""
    info = GC.skill_by_key(sid) or SKD[sid]
    logs = []
    EF.apply_effects(battle, caster, target, EF.effects_from_skill(info, 1), logs)
    return logs


def apply_cast(battle, actor, sid):
    """定向（cast 路）：走引擎那条**真门** —— `act_cast` 事件 + 该 actor 身上挂的触发器。**不推时**。"""
    from ext_combat.battle.effect_triggers import fire as _fire
    info = GC.skill_by_key(sid) or SKD[sid]
    logs = []
    _fire(battle, "act_cast", {"actor": actor, "target": actor, "info": info}, logs)
    return logs


def has(logs, slot):
    """日志里有没有某一槽位那一行（逐字取 texts）。"""
    want = CA.T(slot).split("{")[0]
    return any(want in x for x in logs)


print()
print("── ④ 不装配反证：两条路各自的装配点拿掉 ⇒ 与今天一字不差")
_ea_keep, _er_keep = copy.deepcopy(_ea), copy.deepcopy(_er)
GC.load_game_rules(types.SimpleNamespace(EFFECT_ACTIONS={}, EFFECT_RULES={}))
_b = fresh("cls_assassin", mid=DOG)
_c, _t, _l = do(_b, "SKILL_SHD_sever")
_states = sorted(set(_c.get("effects") or {}) | set(_t.get("effects") or {}))
(ok if not _states else bad)("  · engine 路的装配点 = 引擎那两张表：清表后断势**不挂破绽**（%s）"
                             % (_states or "空"))
_b2 = fresh("cls_priest", hp=200)
_b2.focus()["triggers"] = {}                      # cast 路的装配点 = 玩家 actor 上的触发器
_c2, _t2, _l2 = do(_b2, "SKILL_PRS_lullaby")
(ok if not (_c2.get("effects") or {}) else bad)(
    "  · cast 路的装配点 = 玩家 actor 的触发器：拿掉后安神曲**不挂再生**（%s）"
    % (sorted(_c2.get("effects") or {}) or "空"))
GC.load_game_rules(types.SimpleNamespace(EFFECT_ACTIONS=_ea_keep, EFFECT_RULES=_er_keep))
_b3 = fresh("cls_assassin", mid=DOG)
_c3, _t3, _l3 = do(_b3, "SKILL_SHD_sever")
_b4 = fresh("cls_priest", hp=200)
_c4, _t4, _l4 = do(_b4, "SKILL_PRS_lullaby")
(ok if has(_l3, "COMBAT_MECH_SEVER") and has(_l4, "COMBAT_MECH_LULLABY") else bad)(
    "  · 装配点挂回来 ⇒ 同一个调用真出机制那两行（对照，证明上面两条不是「本来就什么都不写」）")

print()
print("── ⑤ 断势（interrupt）：打断待发 + 挂破绽（承伤 ×1.35 / 200 刻）")
_b = fresh("cls_assassin", mid=DOG)
_c, _t, _l = do(_b, "SKILL_SHD_sever")
(ok if has(_l, "COMBAT_MECH_SEVER") else bad)("  · 端到端：真出手 ⇒ 出「破绽」那一行")
_bc = fresh("cls_assassin", mid=DOG)
_target = (_bc.sides.get("enemy") or [None])[0]
_mk = MECH.of("interrupt")["state"]
_turns = float(SKD["SKILL_SHD_sever"]["mech_val"])
apply_mech(_bc, _bc.focus(), _target, "SKILL_SHD_sever")
_e = (_target.get("effects") or {}).get(_mk) or {}
(ok if abs(float(_e.get("expire") or 0) - (_bc._now + _turns)) < 1e-6 else bad)(
    "  · 定向：到期 = 现在 + mech_val（%.2f = %.2f + %s）" % (float(_e.get("expire") or 0), _bc._now, _turns))
_bs = fresh("cls_assassin", mid=DOG)
_ta, _tb = stub(battle=_bs), stub(battle=_bs)
_ta["effects"][_mk] = {"stacks": 1, "expire": 9999.0}
_r1, _r2 = hit(_bs, _ta, 100), hit(_bs, _tb, 100)
_want = 1.0 + float(MECH.state_rule(_mk)["debuff_scale"]["dmg_taken"])
(ok if _r1 == int(100 * _want) and _r2 == 100 else bad)(
    "  · 承伤乘区逐值：带破绽 %d 点 / 不带 %d 点（声明 ×%.2f）" % (_r1, _r2, _want))
_b5 = fresh("cls_assassin", mid=DOG)
_t5 = (_b5.sides.get("enemy") or [None])[0]
SCH.pending_begin(_b5, ActCtx(caster=_t5, action="skill", skill_name="x", info={}))
_was = bool(_t5.get("charging"))
_mlogs = apply_mech(_b5, _b5.focus(), _t5, "SKILL_SHD_sever")
(ok if _was and not _t5.get("charging") else bad)(
    "  · 定向：对方出招窗口里那一手被清掉（登记 %s ⇒ 现在 %s）" % (_was, _t5.get("charging")))
(ok if any("出招被打断" in x for x in _mlogs) else bad)("  · 引擎 `interrupt` 动词真跑了（得出那句断招）")

print()
print("── ⑥ 破势（def_break）：目标 def ×0.70（300 刻）+ 自伤 8% max_hp")
_b = fresh("cls_berserker", mid=DOG)
_c, _t, _l = do(_b, "SKILL_BSK_sunder")
(ok if has(_l, "COMBAT_MECH_SELF_CUT") and has(_l, "COMBAT_MECH_SUNDER") else bad)(
    "  · 端到端：真出手 ⇒ 出「自己见血」+「甲被劈开」两行")
_cut = [int(x.split("−")[-1].rstrip("）。")) for x in _l if "见了血" in x]
_mx = int(ST.actor_max_hp(_b, _c) or 0)
(ok if _cut and _cut[0] == int(round(_mx * float(MECH.of("def_break")["self_dmg_pct"]["value"]))) else bad)(
    "  · 自伤 = max_hp 的 %s（max_hp %d ⇒ 期望 %d · 实测 %s）"
    % (MECH.of("def_break")["self_dmg_pct"]["value"], _mx,
       int(round(_mx * float(MECH.of("def_break")["self_dmg_pct"]["value"]))), _cut or "没打出来"))
_bc = fresh("cls_berserker", mid=DOG)
_c2 = _bc.focus()
_t2 = (_bc.sides.get("enemy") or [None])[0]
_mk = MECH.of("def_break")["state"]
_panel = MECH.state_rule(_mk)["panel"]
_d0 = float(ST.actor_stats(_bc, _t2).get("def", 0) or 0)
apply_mech(_bc, _c2, _t2, "SKILL_BSK_sunder")
_d1 = float(ST.actor_stats(_bc, _t2).get("def", 0) or 0)
_e = (_t2.get("effects") or {}).get(_mk) or {}
_tt = float(MECH.of("def_break")["turns"]["value"])
(ok if _d1 == int(_d0 * float(_panel["mult"])) else bad)(
    "  · 目标 def 真降了：%.0f ⇒ %.0f（声明 ×%.2f ⇒ 期望 %d）"
    % (_d0, _d1, float(_panel["mult"]), int(_d0 * float(_panel["mult"]))))
(ok if abs(float(_e.get("expire") or 0) - (_bc._now + _tt)) < 1e-6 else bad)(
    "  · 破防态时长 = %s 刻（到期 = 现在 + %s）" % (_tt, _tt))

print()
print("── ⑦ 挑战咆哮（taunt）：嘲讽态 100 刻 + 「优先打他」的注入点")
_b = fresh("cls_knight")
_c, _t, _l = do(_b, "SKILL_KNT_taunt")
_mk = MECH.of("taunt")["state"]
(ok if has(_l, "COMBAT_MECH_TAUNT") else bad)("  · 端到端：真出手 ⇒ 出「它只会冲你来」那一行")
_bc = fresh("cls_knight")
_c2 = _bc.focus()
_tt = float(MECH.of("taunt")["turns"]["value"])
apply_mech(_bc, _c2, _c2, "SKILL_KNT_taunt")
_e = (_c2.get("effects") or {}).get(_mk) or {}
(ok if abs(float(_e.get("expire") or 0) - (_bc._now + _tt)) < 1e-6 and _e.get("v") else bad)(
    "  · 定向下：挂上 %s（到期 = 现在 + %s 刻 · mech_val %s 随态存下）" % (_mk, _tt, _e.get("v")))
_bb = fresh("cls_knight")
_p1 = _bb.sides["player"][0]
_bb.add_actor(CMB.player_actor({"cls": "cls_knight", "level": 10, "uid": "u_p2", "name": "乙"}), "player")
_mob = (_bb.sides.get("enemy") or [None])[0]
_none_arm = MECH.taunt_picker(_bb, _mob)
_p1.setdefault("effects", {})[_mk] = {"stacks": 1, "expire": _bb._now + 100}
_taunt_arm = MECH.taunt_picker(_bb, _mob)
_p1["effects"][_mk]["expire"] = _bb._now - 1
_expired_arm = MECH.taunt_picker(_bb, _mob)
(ok if _none_arm is None and _taunt_arm is _p1 and _expired_arm is None else bad)(
    "  · 没挂 ⇒ None（走引擎原路）｜ 挂了 ⇒ 指名它（%s）｜ 过期 ⇒ 又回 None"
    % ((_taunt_arm or {}).get("name"),))

print()
print("── ⑧ 减免态（不退 / 庇护 / 盾墙）：承伤乘区逐值 + 同轴只算一次")
_b = fresh("cls_knight")
_c = _b.focus()
_a = stub(battle=_b)
_r0 = hit(_b, _a, 100)
apply_mech(_b, _a, _a, "SKILL_KNT_standfast")
_r1 = hit(_b, _a, 100)
apply_mech(_b, _a, _a, "SKILL_PRS_aegis")
_r2 = hit(_b, _a, 100)
(ok if (_r0, _r1, _r2) == (100, 70, 70) else bad)(
    "  · 不退：%d ⇒ %d（−30%%）；再叠庇护 ⇒ %d（同轴 `join_key` 只算最强那条 ⇒ 不是 ×0.49）"
    % (_r0, _r1, _r2))
_a2 = stub(battle=_b)
apply_mech(_b, _a2, _a2, "SKILL_PRS_aegis")
_r3 = hit(_b, _a2, 100)
(ok if _r3 == 70 else bad)("  · 单独庇护 ⇒ %d 点（−30%%）" % _r3)
_a3 = stub(battle=_b)
_a3["ct"] = _b._now + 123.0
apply_cast(_b, _a3, "SKILL_KNT_oathwall")
_r4 = hit(_b, _a3, 100)
_e = (_a3.get("effects") or {}).get(MECH.of("protect")["state"]) or {}
(ok if _r4 == 60 else bad)("  · 盾墙 ⇒ %d 点（−40%%）" % _r4)
(ok if abs(float(_e.get("expire") or 0) - float(_a3["ct"])) < 1e-6 else bad)(
    "  · 盾墙的时长 = 自己**下一次行动的到点时刻**（现算：到期 %.2f == ct %.2f —— 不编刻数）"
    % (float(_e.get("expire") or 0), float(_a3["ct"])))
_ba = fresh("cls_knight")
_ca, _ta, _la = do(_ba, "SKILL_KNT_oathwall")
(ok if has(_la, "COMBAT_MECH_OATHWALL") else bad)("  · 端到端：真出手 ⇒ 出「你把盾立起来」那一行")

print()
print("── ⑨ 晨祷（immune_window）：免疫窗 = 承伤压到地板（引擎地板 1 点/次 —— 登记在 halves）")
_b = fresh("cls_priest")
_a = stub(battle=_b)
apply_mech(_b, _a, _a, "SKILL_PRS_matins")
_mk = MECH.of("immune_window")["state"]
_e = (_a.get("effects") or {}).get(_mk) or {}
_want_t = float(SKD["SKILL_PRS_matins"]["mech_val"])
(ok if _e and abs(float(_e.get("expire") or 0) - (_b._now + _want_t)) < 1e-6 else bad)(
    "  · 窗挂着（到期 = 现在 + mech_val %s 刻）" % _want_t)
_r = hit(_b, _a, 100)
_a["effects"][_mk]["expire"] = _b._now - 1
_r2 = hit(_b, _a, 100)
(ok if _r <= 1 and _r2 == 100 else bad)(
    "  · 窗内挨 100 点 ⇒ 真扣 %d 点（引擎乘区地板 max(1,…)）｜ 窗过期 ⇒ 恢复 %d 点" % (_r, _r2))
_b2 = fresh("cls_priest")
_c2, _t2, _l2 = do(_b2, "SKILL_PRS_matins")
(ok if has(_l2, "COMBAT_MECH_MATINS") else bad)("  · 端到端：真出手 ⇒ 出「光落下来」那一行")

print()
print("── ⑩ 抢拍（advance_ct）：下一次行动的到点时刻提前 mech_val 刻")
_b = fresh("cls_ranger")
_c, _t, _l = do(_b, "SKILL_RNG_quickstep")
_ct_a = float(_c.get("ct") or 0)
_b2 = fresh("cls_ranger")
_c2, _t2, _l2 = do(_b2, "SKILL_RNG_aimshot")            # 同类技能（同一 cast/recover 类别）
_ct_b = float(_c2.get("ct") or 0)
_want = float(SKD["SKILL_RNG_quickstep"]["mech_val"])
(ok if abs((_ct_b - _ct_a) - _want) < 0.5 else bad)(
    "  · 同一场同一手：不放抢拍 %.2f 刻 ｜ 放抢拍 %.2f 刻 ⇒ 提前 %.2f（声明 %s）"
    % (_ct_b, _ct_a, _ct_b - _ct_a, _want))
(ok if has(_l, "COMBAT_MECH_QUICKSTEP") else bad)("  · 端到端：真出手 ⇒ 出「你抢了半拍」那一行")

print()
print("── ⑪ 净罪（cleanse）：解掉**一个**控制效果；不是控制的条目留着")
_b = fresh("cls_priest")
_c = _b.focus()
_ef = _c.setdefault("effects", {})
_ef["zz_buff"] = {"stacks": 1, "expire": _b._now + 100}
_ef["aa_ctl"] = {"stacks": 1, "expire": _b._now + 100, "mode": "skip"}
apply_cast(_b, _c, "SKILL_PRS_absolve")
_left = sorted(_c.get("effects") or {})
(ok if "aa_ctl" not in _left and "zz_buff" in _left else bad)(
    "  · 控制态被解掉、非控制条目留着（剩 %s）" % (_left,))
_mlogs = apply_cast(_b, _c, "SKILL_PRS_absolve")
(ok if any("没有能解" in x for x in _mlogs) else bad)("  · 没控可解 ⇒ 出「没有能解的东西」那一句（不静默）")

print()
print("── ⑫ 安神曲（hot）：300 刻再生，每刻 = 这一发治疗量的 1/4（真推进时间轴）")
_b = fresh("cls_priest", hp=150)
_c = _b.focus()
_c["hp"] = 150
apply_cast(_b, _c, "SKILL_PRS_lullaby")
_mk = MECH.of("hot")["state"]
_e = (_c.get("effects") or {}).get(_mk) or {}
_pd = _e.get("period") or {}
_ratio = float(MECH.of("hot")["hot_ratio"]["value"])
_heal = int(ACT.heal_amount(ST.actor_stats(_b, _c), _c, GC.skill_by_key("SKILL_PRS_lullaby"), 1))
_per = int(round(_heal * _ratio))
(ok if _e and _pd.get("dir") == "heal" and int(_pd.get("interval") or 0) == 1 else bad)(
    "  · 条目自带周期声明（dir=%s · interval=%s · heal_pct=%.6f）"
    % (_pd.get("dir"), _pd.get("interval"), float(_pd.get("heal_pct") or 0)))
(ok if abs(float(_e.get("expire") or 0) - (_b._now + float(SKD["SKILL_PRS_lullaby"]["mech_val"]))) < 1e-6 else bad)(
    "  · 时长 = mech_val %s 刻（到期 = 现在 + 它）" % SKD["SKILL_PRS_lullaby"]["mech_val"])
_hp0 = int(_c.get("hp") or 0)
_mx = int(_c.get("max_hp") or 0)
SCH._advance_time(_b, 1.0, [])                    # ★ 首次挂：引擎先**登记下一跳**（这一下不结算）
_ticks: list = []
SCH._advance_time(_b, 5.0, _ticks)                # 再推进 ⇒ 真跳（每刻一跳）
_heals = [int(x.split("恢复 ")[1].split(" 点")[0]) for x in _ticks if "持续恢复" in x]
_gain = int(_c.get("hp") or 0) - _hp0
(ok if _heals and set(_heals) == {_per} and _gain == min(sum(_heals), _mx - _hp0) else bad)(
    "  · 真推进 ⇒ 每刻回 %d 点、跳 %d 次、共回 %d 点（= 治疗 %d × %s 每刻；超出上限的那点被 clamp）"
    % (_per, len(_heals), _gain, _heal, _ratio))

print()
print("── ⑬ pending 的四条技能：真放一次不抛、不写任何状态（缺口是**声明**出来的，不静默假生效）")
_pend_rows = []
for _sid in ("SKILL_RNG_backstep", "SKILL_SHD_backstep", "SKILL_MAG_ignite", "SKILL_MAG_fallenstar"):
    _rec = SKD[_sid]
    _m = MECH.of(_rec.get("mech"))
    try:
        _bb = fresh(_rec["owner_class"], mid=MID)
        _cc, _tt, _ll = do(_bb, _sid)
        _wrote = sorted(set(_cc.get("effects") or {}) | set(_tt.get("effects") or {}))
        _pend_rows.append((_sid, _m.get("status"), bool(_m.get("why")), _wrote))
    except Exception as _ex:                                    # noqa: BLE001
        _pend_rows.append((_sid, "抛了", str(_ex)[:40], []))
_bad_p = [(s, st, w, w2) for s, st, w, w2 in _pend_rows if st != "pending" or not w or w2]
(ok if not _bad_p else bad)("★ 四条 pending 技能（后撤×2 · 引燃 · 垂星）：status=pending 且有 why、"
                           "真放不抛、不写任何状态　%s" % ("全对" if not _bad_p else "红：%s" % _bad_p))

print()
print("── ⑭ fail-closed：四种坏声明各抛一次（加载期，不留运行期静默）")
_teeth = []


def _try(fn, want, label):
    try:
        fn()
        _teeth.append("%s 没抛" % label)
    except want:
        return True
    except Exception as _e:                                     # noqa: BLE001
        _teeth.append("%s 抛了别的：%s" % (label, type(_e).__name__))
    return False


_bad1 = copy.deepcopy(MECH.table())
_bad1["mechs"]["interrupt"]["route"] = "magic"
_try(lambda: MECH._validate(_bad1), ValueError, "route 乱写")

_bad2 = copy.deepcopy(MECH.table())
_bad2["mechs"]["retreat"]["route"] = "cast"
_bad2["mechs"]["retreat"]["verb"] = "aeth_on_cast"
_try(lambda: MECH._validate(_bad2), ValueError, "route=cast 与实现对不上")

_bad3 = copy.deepcopy(MECH.table())
_bad3["mechs"]["taunt"]["actions"] = [{"action": "aeth_no_such_verb"}]
_try(lambda: MECH._validate(_bad3), ValueError, "动词没注册")

SKD["SKILL_FAKE_x"] = {"name": "假技能", "mech": "no_such_mech", "owner_class": "cls_knight"}
try:
    # ★ 域那一侧的真源是 `skills_lookup` 的缓存（读的是 content/data/skills.json）——
    #   往它的缓存里塞一条假的 = 模拟「有人改域加了一条机制名」（改完立刻撤回）。
    from content import skills_lookup as _SL
    _SL._C.setdefault("skills", SKD)["SKILL_FAKE_x"] = SKD["SKILL_FAKE_x"]
    _try(MECH.check_domain, KeyError, "域里出现没声明的机制")
finally:
    SKD.pop("SKILL_FAKE_x", None)
    from content import skills_lookup as _SL2
    (_SL2._C.get("skills") or {}).pop("SKILL_FAKE_x", None)
(ok if not _teeth else bad)("★ 四种坏声明都当场抛（route 乱写 / cast 没实现 / 动词没注册 / 域里没声明的机制）　%s"
                           % ("全对" if not _teeth else "红：%s" % _teeth))

print()
print("── ⑮ 引擎零改动（硬指标）")
_git = subprocess.run(["git", "status", "--porcelain"], cwd=ENGINE, capture_output=True, text=True)
(ok if not (_git.stdout or "").strip() else bad)(
    "★ 引擎仓 git status 为空（%r）" % ((_git.stdout or "").strip()[:60] or "干净"))

print()
print("结果：%s" % ("全绿 ✓" if not fails else "有红 ✗（%d）" % len(fails)))
sys.exit(1 if fails else 0)
