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
import random
import subprocess
import sys
import time
import types

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, REPO)
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402
from saintess_engine import config as CFG                            # noqa: E402

st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
st.install()

from content import cmds_ast as CA                                   # noqa: E402
from content import mech as MECH                                     # noqa: E402
from content import absorb as ABS                                    # noqa: E402  容器收口第2批
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
    # ★ fxmech：**两格机制都要进这张现算表** —— 域里 `mech2`（垂星的砸晕 `star_stun`）原先
    #   被漏掉：它对 `check_domain` 是**单向**（域 → 表）过的，而下面那条**双向**对账只认
    #   `mech` ⇒ 表里多一条「只有 mech2 在引用」的机制会被判成「表里多出来的」。
    for _fld in ("mech", "mech2"):
        if _rec.get(_fld):
            BY_MECH.setdefault(_rec[_fld], []).append(_sid)

print("探针：技能机制层（B3-27）")
print("  · 域里带 mech 的技能 %d 条 · 机制 %d 个：%s"
      % (sum(len(v) for v in BY_MECH.values()), len(MECH.mechs()),
         " · ".join("%s×%d" % (k, len(v)) for k, v in sorted(BY_MECH.items()))))

# ══════════════════════════════════════════════════════════════
# ① 形状档：表 · 域双向对账
# ══════════════════════════════════════════════════════════════
_badshape = []
for _n, _m in MECH.mechs().items():
    if _m.get("route") not in ("engine", "cast", "trigger", ""):
        _badshape.append((_n, "route", _m.get("route")))
    if _m.get("status") not in ("on", "partial", "pending"):
        _badshape.append((_n, "status", _m.get("status")))
    if _m.get("status") in ("pending", "partial") and not _m.get("why"):
        _badshape.append((_n, "缺 why"))
    if _m.get("route") == "engine" and not _m.get("actions"):
        _badshape.append((_n, "route=engine 没 actions"))
    if _m.get("route") == "cast" and not _m.get("verb"):
        _badshape.append((_n, "route=cast 没 verb"))
(ok if not _badshape else bad)("★ %d 条机制的声明形状齐（route / status / why / actions / verb）　%s"
                               % (len(MECH.mechs()),
                                  "全对" if not _badshape else "红：%s" % _badshape[:3]))

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
# ★ 状态容器收口第 2 批（2026-09-28）：`EFFECT_RULES` 现在有**两个声明来源** ——
#   ① 技能机制的 `mechs.*.rules`；② 精英词条那条吸收型声明（`rules/elite.json::absorb`）。
#   判据跟着扩：期望键 = 两个来源的并集（照旧**逐键相等**，多一格少一格都红）。
#   ★ 强度不变：它照样钉住「挂进引擎的表 == 声明出来的那些格」，只是声明面多了一处。
_want_er = sorted(set(k for m in MECH.mechs().values() for k in (m.get("rules") or {}))
                  | set(MECH.absorb_state_keys()))
(ok if sorted(_ea) == _want_ea else bad)(
    "★ `EFFECT_ACTIONS` 的键 == route=engine 的机制（引擎侧 %s）" % (sorted(_ea),))
(ok if sorted(_er) == _want_er else bad)(
    "★ `EFFECT_RULES` 的键 == 两个来源声明的全部规则（技能机制 %d + 吸收型声明 %d；引擎侧 %s）"
    % (len(_want_er) - len(MECH.absorb_state_keys()), len(MECH.absorb_state_keys()), sorted(_er)))
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
# ★ 2026-09-27（这条判据原本是**偶发红** ⇒ 查出真 bug）：自伤那一笔原先**能被打架的人自己闪开** ——
#   `LD.deal_damage(battle, None, caster, …)` 对 source=None 也照过闪避那一掷 ⇒ 偶尔 `real == 0`
#   ⇒ 上面两条当场红（同一棵树连跑若干次里必有一次「自伤没打出来」）。
#   修：引擎 `deal_damage` 加可选 `no_dodge`（内容侧自付那一笔传 True）；`_self_cut` 已跟账。
#   这一条把那一掷**钉死**（dodge 拉满 = 面板上限 40% + `random.seed(1)` ⇒ 那一掷必「闪开」的
#   输入）⇒ 改前**必红**、改后必绿：偶发红变成常驻判据。
_c0 = fresh("cls_berserker", mid=DOG)
_e0 = _c0.focus()
_amt0 = int(round(int(ST.actor_max_hp(_c0, _e0) or 0) * float(MECH.of("def_break")["self_dmg_pct"]["value"])))
_LD_roll = LD._roll_dodge
try:
    LD._roll_dodge = (lambda *a, **k: True)       # 钉住那一掷：这一笔一定「闪开」
    _rl0 = LD.deal_damage(_c0, None, _e0, _amt0, [], no_dodge=True)     # 该落满
    _rl1 = LD.deal_damage(_c0, None, _e0, _amt0, [])                    # 反证：不传 ⇒ 被闪掉
finally:
    LD._roll_dodge = _LD_roll
(ok if _rl0 == _amt0 and _rl1 == 0 else bad)(
    "★ 自伤不许被自己闪掉（钉住那一掷为「闪开」）：传 `no_dodge` ⇒ 该落满 %d（实 %d）· "
    "反证不传 ⇒ 那一笔该被闪掉（实 %d）" % (_amt0, _rl0, _rl1))
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
#: ★ 资源闸门（③ 资源渠道）上了之后：晨祷要 3 层祷言 ⇒ fixture 得先把资源垫上
#:   （这不是放宽判据 —— 引擎的资源预检本来就该拦；探针给足资源才是「这一手放得出来」的场景）
#:   ★ 顺序要求：`battle_start` 那一趟会把资源**摆回 0**（开战就该是 0）⇒ 先把开门那一趟推掉，
#:     再垫资源；反过来的话垫的会被开门冲掉。
_b2._ensure_battle_started([])
_b2.focus().setdefault("effects", {})["RES_LITANY"] = {"stacks": 3, "expire": None}
_c2, _t2, _l2 = do(_b2, "SKILL_PRS_matins")
(ok if has(_l2, "COMBAT_MECH_MATINS") else bad)("  · 端到端：真出手 ⇒ 出「光落下来」那一行")

print()
print("── ⑩ 抢拍（advance_ct）：下一次行动的到点时刻提前 mech_val 刻")
_b = fresh("cls_ranger")
_c, _t, _l = do(_b, "SKILL_RNG_quickstep")
_want = float(SKD["SKILL_RNG_quickstep"]["mech_val"])
# ★ fxmech（2026-09-26）：这一条原先拿「点射」当同类技能比（B4-4 之前两者都按类别 skill
#   80/50 算，可比）；接线后各用自己的 cast/recover ⇒ 抢拍 30+30、点射 30+20，差值被后摇差吃掉。
#   改成**同一手、只拿掉那一下提前**（把引擎那张 EFFECT_ACTIONS 里的 `advance_ct` 临时摘掉），
#   并且**在落地那一刻量**（落地之后引擎还会继续推到下一个决策点，ct 会被后续行动改写）。
from ext_combat.battle import game_config as _GC2
_ea_tbl = _GC2.get_effect_actions()


def _quickstep_landing(with_effect=True):
    """同一手、同一 spd：只差「有没有那一下提前」。回（ct − now 在落地那一刻, now, ct, 日志）。"""
    _saved = _ea_tbl.pop("advance_ct", None) if not with_effect else None
    try:
        _bb = fresh("cls_ranger")
        _bb._ensure_battle_started([])
        _cc = _bb.focus()
        _info = GC.skill_by_key("SKILL_RNG_quickstep") or SKD["SKILL_RNG_quickstep"]
        _bb.act(ActCtx(caster=_cc, action="skill", skill_name=_info.get("name"), info=_info,
                       target=(_bb.sides.get("enemy") or [None])[0]))
        _lg = []
        SCH.settle_landing(_bb, _lg, _cc)                 # ← 落地那一刻
        return (float(_cc.get("ct") or 0) - float(_bb._now), float(_bb._now),
                float(_cc.get("ct") or 0), [str(x) for x in _lg], _cc, _bb, _info)
    finally:
        if _saved is not None:
            _ea_tbl["advance_ct"] = _saved


_gap_off, _now_off, _ct_off, _lg_off, _cc_off, _bb_off, _info_q = _quickstep_landing(False)
_gap_on, _now_on, _ct_on, _lg_on, _cc_on, _bb_on, _ = _quickstep_landing(True)
_spd_q = int(SCH._spd_of(_bb_on, _cc_on))
_rec_q = float(CFG.get_hook("recover_model_fn")(_spd_q, float(_info_q["recover"]["base"])))
# 落地那一刻：ct = now + 后摇（不带那一下提前）；带上它 ⇒ ct = max(now, now + 后摇 − 声明)
_want_off = _rec_q
_want_on = max(0.0, _rec_q - _want)
_adv = _gap_off - _gap_on                                 # 真正提前了多少 = min(声明, 后摇)
(ok if abs(_gap_off - _want_off) < 0.05 and abs(_gap_on - _want_on) < 0.05
    and abs(_adv - min(_want, _rec_q)) < 0.05 and _ct_on >= _now_on - 1e-9 else bad)(
    "  · 落地那一刻：不带那一下提前 ct−now=%.2f（= 本手后摇 %.2f）｜ 带它 ct−now=%.2f"
    "（= max(0, 后摇 − 声明 %s)）⇒ 真提前 %.2f = min(声明, 后摇) · ct 不小于当刻　%s"
    % (_gap_off, _rec_q, _gap_on, _want, _adv, "✓" if _ct_on >= _now_on - 1e-9 else "✗"))
print("  · 登记：本手后摇（%.2f 刻）**小于**声明值（%s 刻）⇒ 那道「不早于当刻」的闸把它夹到 0，"
      "这一手退化成「落地即可再动」（真源 03_游侠_v2 §三 那句「提前 30 刻」在此形态下就是这个意思；"
      "接线前是按类别 80/50 算的后摇 58.3 刻，所以那一档能吃满 30）" % (_rec_q, _want))
(ok if has(_lg_on, "COMBAT_MECH_QUICKSTEP") else bad)("  · 端到端：真出手 ⇒ 出「你抢了半拍」那一行")

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
_none = CA.T("COMBAT_MECH_ABSOLVE_NONE")
(ok if _none in _mlogs else bad)(
    "  · 没控可解 ⇒ 出「没有能解的东西」那一句（不静默）—— 逐字取自槽位 %r" % _none)
#: ★ fix-h-small（真人试玩 b13 · 修女路）：净罪的**收件人就是施法者自己**
#:   （`_cast_cleanse` 只动 caster 自己的 `effects`；单人对面只有怪）⇒ 那一句的主人公必须是
#:   「你」。改前写的是「它身上…」，屏上被读成**对面**（玩家以为打空 / 解错了对象）。
#:   判据：那一句里有「你」、没有「它」（槽位值改回去 ⇒ 这一条当场红）。
(ok if ("你" in _none and "它" not in _none) else bad)(
    "  · 那一句的主人公是「你」（单人 = 自己，不是对面）：%r" % _none)

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
#: ★ fxmech：这一发的基数走**本包那个唯一的口**（F8 —— 治疗强度 × 倍率），
#:   改前这里量的是引擎兜底（`matk × power`），而落地那一发走的是 F8 ⇒ 两处必须同源。
_heal = int(round(MECH._heal_base_of(_b, _c, GC.skill_by_key("SKILL_PRS_lullaby"))))
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
print("── ⑬ pending 那两条技能（后撤 ×2）：真放一次不抛、不写任何状态（缺口是**声明**出来的，不静默假生效）")
_pend_rows = []
#: ★ fxmech：引燃 / 垂星 从 pending 抬到 **on**（印记 → 引爆的兑现端接上了，判据见 ㉒）
#:   ⇒ 这一档只剩两条后撤（`retreat` 仍是 pending —— 本作 CTB 没有站位轴）。
for _sid in ("SKILL_RNG_backstep", "SKILL_SHD_backstep"):
    _rec = SKD[_sid]
    _m = MECH.of(_rec.get("mech"))
    try:
        _bb = fresh(_rec["owner_class"], mid=MID)
        # ★ B4-1：基线要**在开战那一趟之后**取 —— 常驻被动（route=trigger）在 battle_start
        #   就会挂上自己的状态，那是"这个人本来就有"的，不是这一手写进去的。判据因此改成
        #   「放这一手**没有新增**任何状态」（比原来那句「一个状态都没有」更准，也更严：
        #   它同时钉住了"pending 不写任何东西"与"被动的常驻态是开战给的"两件事）。
        _sb = _bb.focus()
        _eb = (_bb.sides.get("enemy") or [{}])[0]
        #: ★ 基线要取在**开战那一趟之后**：职业资源渠道接上之后，`battle_start` 会把资源条目摆成 0
        #:   （那就是「一个状态都不新增」的基线；不先推开战，资源条目会被算成 pending 写的新状态）
        _bb._ensure_battle_started([])
        SCH.advance(_bb, [])
        _base = set(_sb.get("effects") or {}) | set(_eb.get("effects") or {})
        _cc, _tt, _ll = do(_bb, _sid)
        _wrote = sorted((set(_cc.get("effects") or {}) | set(_tt.get("effects") or {})) - _base)
        _pend_rows.append((_sid, _m.get("status"), bool(_m.get("why")), _wrote))
    except Exception as _ex:                                    # noqa: BLE001
        _pend_rows.append((_sid, "抛了", str(_ex)[:40], []))
_bad_p = [(s, st, w, w2) for s, st, w, w2 in _pend_rows if st != "pending" or not w or w2]
(ok if not _bad_p else bad)("★ 两条 pending 技能（后撤 ×2）：status=pending 且有 why、"
                           "真放不抛、**一个状态都不新增**（基线 = 开战那一趟之后）　%s"
                           % ("全对" if not _bad_p else "红：%s" % _bad_p))

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

# ══════════════════════════════════════════════════════════════
# ★ B4-1 追加：⑯–⑳ —— T1 11–20 那批新机制（11 条主动 + 6 条被动）
#   放在 ⑮「引擎零改动」之前：那一条是收尾的硬指标，让它压轴。
#   每条机制至少一条**真跑**判据，数值一律现算（基线从 actor_stats / 域里那个 mech_val 取）。
# ══════════════════════════════════════════════════════════════
print()
print("── ⑯ 骑士两条新机制（誓约壁垒 = 吸收盾 · 断后 = 推后自己 + 承伤 ×0.5）")
_b = fresh("cls_knight")
_c = _b.focus()
_mx = int(ST.actor_max_hp(_b, _c) or 0)
apply_mech(_b, _c, _c, "SKILL_KNT_bulwark")
# ★ 状态容器收口第 2 批（2026-09-28 · 设计案 §2.1/§2.2）：这一处判据换口径 ——
#   旧口径 = 「`actor["shields"][aeth.oath_shield]` 那一格」；新口径 = 「**容器里那条
#   声明为吸收型的条目**」（键由 `skill_mech.json` 的 `absorb: true` 声明，引擎不硬编码
#   游戏专名；值由 `content/absorb.py::shield_value_of` 读，两态同口径）。
#   ★ 两态门在这里也钉一条：引擎那半没到 ⇒ 走旧容器；到了 ⇒ 自动走容器条目。
_sh = ABS.shield_of(_c, MECH._SHIELD_KEY) or {}
_sh_decl = MECH.state_rule(MECH._SHIELD_KEY) or {}
_want_sh = int(round(_mx * float(MECH.of("oath_shield")["shield_pct"]["value"])))
_t_sh = float(SKD["SKILL_KNT_bulwark"]["mech_val"])
(ok if _sh_decl.get("absorb") is True else bad)(
    "  · ★ 声明：状态 %r 在 `EFFECT_RULES` 里声明了 `absorb: true`（吸收型由声明决定，不硬编码键名）"
    % (MECH._SHIELD_KEY,))
(ok if int(_sh.get("value") or 0) == _want_sh else bad)(
    "  · 定向：盾值 = int(生命上限 %d × %s) = %d（实测 %s）"
    % (_mx, MECH.of("oath_shield")["shield_pct"]["value"], _want_sh, _sh.get("value")))
(ok if abs(ABS.shield_expire_of(_c, MECH._SHIELD_KEY) - (_b._now + _t_sh)) < 1e-6 else bad)(
    "  · 定向：盾到期 = 现在 + mech_val（%.2f = %.2f + %s）"
    % (ABS.shield_expire_of(_c, MECH._SHIELD_KEY), _b._now, _t_sh))
(ok if ABS.container_mode() == (ABS.engine_has_value_entry() and ABS.engine_absorb_by_container())
   else bad)(
    "  · ★ 两态门：容器那态 = %s（引擎 `open_entry` 认 value? %s · 承伤层走容器遍历? %s）"
    % (ABS.container_mode(), ABS.engine_has_value_entry(), ABS.engine_absorb_by_container()))
#: ★ 端到端那几路一律用 **16 级**的号：新技能是 lv 11/14/16 解锁的，10 级的 actor 索引不到它
#:   （`_index_one_actor` 只索引 actor 技能表里那几条）—— 放一条没解锁的招，引擎只会回落普攻。
_b2 = fresh("cls_knight", lv=16)
_b2._ensure_battle_started([])                        # 先推开门（它会把资源摆 0），再垫
_b2.focus().setdefault("effects", {})["RES_OATH"] = {"stacks": 40, "expire": None}   # 誓约壁垒要 40 守誓
_c2, _t2, _l2 = do(_b2, "SKILL_KNT_bulwark")
(ok if ABS.shield_value_of(_c2, MECH._SHIELD_KEY) > 0 and any("护盾" in x for x in _l2) else bad)(
    "  · 端到端：真出手 ⇒ 引擎那句「获得护盾 N 点」（护盾走引擎自己的写入口与文案，不另写一套）")
_b3 = fresh("cls_knight")
_c3 = _b3.focus()
_c3["ct"] = _b3._now + 123.0
apply_mech(_b3, _c3, _c3, "SKILL_KNT_rearguard")
_delay = float(MECH.of("hold_line")["delay_ticks"]["value"])
(ok if abs(float(_c3["ct"]) - (_b3._now + 123.0 + _delay)) < 1e-6 else bad)(
    "  · 定向：断后把自己的下一次行动推后 %s 刻（123 ⇒ %.1f）"
    % (_delay, float(_c3["ct"]) - _b3._now))
_a3 = stub(battle=_b3)
apply_mech(_b3, _a3, _a3, "SKILL_KNT_rearguard")
_r3 = hit(_b3, _a3, 100)
(ok if _r3 == 50 else bad)("  · 定向：rear_guard 里挨 100 点 ⇒ 实收 %d（承接伤乘区 ×0.5）" % _r3)
_b4 = fresh("cls_knight", lv=16)
_c4, _t4, _l4 = do(_b4, "SKILL_KNT_rearguard")
(ok if has(_l4, "COMBAT_MECH_REARGUARD") else bad)("  · 端到端：真出手 ⇒ 出「你把背后让出来」那一行")

print()
print("── ⑰ 狂战士三条新机制（血债 = 自伤换面板 · 狂态 = 自伤换反击 · 横扫 = 自伤换 AOE）")
_b = fresh("cls_berserker", lv=16)
_c, _t, _l = do(_b, "SKILL_BSK_blooddebt")
_cut = [int(x.split("−")[-1].rstrip("）。")) for x in _l if "见了血" in x]
_mx = int(ST.actor_max_hp(_b, _c) or 0)
_want = int(round(_mx * float(MECH.of("blood_price")["self_dmg_pct"]["value"])))
(ok if _cut and _cut[0] == _want else bad)(
    "  · 端到端：血债的自伤 = max_hp %d × %s = %d（实测 %s）"
    % (_mx, MECH.of("blood_price")["self_dmg_pct"]["value"], _want, _cut or "没打出来"))
_b2 = fresh("cls_berserker")
_c2 = _b2.focus()
_a0 = float(ST.actor_stats(_b2, _c2).get("atk", 0) or 0)
apply_mech(_b2, _c2, _c2, "SKILL_BSK_blooddebt")
_a1 = float(ST.actor_stats(_b2, _c2).get("atk", 0) or 0)
_mult2 = float(MECH.state_rule("blood_debt")["panel"]["mult"])
(ok if _a1 == int(_a0 * _mult2) and has(_l, "COMBAT_MECH_BLOODDEBT") else bad)(
    "  · 定向：血债面板 atk %.0f ⇒ %.0f（声明 ×%s ⇒ 期望 %d）" % (_a0, _a1, _mult2, int(_a0 * _mult2)))
_b3 = fresh("cls_berserker")
_c3 = _b3.focus()
#: ★ fixture 收口（本批实测挖出来的一条引擎语义）：**承伤被闪避掉的那一下不触发 `on_taken`**
#:   （`_apply_damage` 先 roll 闪避，闪掉了就直接 return 0 —— 引擎注释：「闪避免伤不打断蓄力」）。
#:   语义上这是对的（「谁碰你一下」—— 闪开了就是没碰到），但对**判据**的要命之处是：
#:   拿自带你 2~6% 闪避的玩家当挨打方，这条断言就变成掷硬币（实测 12 跑 1 红）。
#:   ⇒ 挨打方仍是**玩家**（反击伤害要吃他的 atk），开打方换成**试桩**（不吃面板/闪避）；
#:     挨的那一下若被闪掉就再来一下（最多 20 次 —— 全闪掉是 0.03^20，判据本体一个字没松）。
_atk3 = stub(hp=500, battle=_b3)
apply_mech(_b3, _c3, _c3, "SKILL_BSK_riposte")
_want_re = int(float(ST.actor_stats(_b3, _c3).get("atk", 0) or 0)
               * float(MECH.state_rule("riposte_guard")["reflect_atk_mult"]))
_got, _tries = 0, 0
while _got == 0 and _tries < 20:
    _tries += 1
    _hp0 = int(_atk3.get("hp") or 0)
    if LD.deal_damage(_b3, _atk3, _c3, 100, []) <= 0:
        continue                                       # 这一下被闪掉了 ⇒ 不算「碰到」（引擎语义）
    _got = _hp0 - int(_atk3.get("hp") or 0)
(ok if _got == _want_re and _want_re > 0 else bad)(
    "  · 定向：狂态里真挨到的那一下 ⇒ 攻击者自己挨 %d（= atk × %s ⇒ 期望 %d；第 %d 次才挨到）"
    % (_got, MECH.state_rule("riposte_guard")["reflect_atk_mult"], _want_re, _tries))
_c3["effects"]["riposte_guard"]["expire"] = _b3._now - 1
_hp1 = int(_atk3.get("hp") or 0)
_tries2, _hit2 = 0, False
while _tries2 < 20 and not _hit2:                       # ★ 同上：要**真挨到**的那一下才算数
    _tries2 += 1
    _hit2 = LD.deal_damage(_b3, _atk3, _c3, 100, []) > 0
(ok if _hit2 and int(_atk3.get("hp") or 0) == _hp1 else bad)(
    "  · 定向：态过期后**真挨到**的那一下不反击（第 %d 次挨到 · 桩 %d ⇒ %d）"
    % (_tries2, _hp1, int(_atk3.get("hp") or 0)))
_b4 = fresh("cls_berserker", lv=16)
_c4, _t4, _l4 = do(_b4, "SKILL_BSK_riposte")
(ok if has(_l4, "COMBAT_MECH_RIPOSTE") else bad)("  · 端到端：真出手 ⇒ 出「你不躲」那一行")
_b5 = CMB.build({"cls": "cls_berserker", "level": 16, "uid": "u_mech", "name": "试"},
                [MID, DOG], MON, party=1)
_c5 = _b5.focus()
#: ★ fixture 收口：这一条问的是「AOE 对**每个**目标各结算一次」，不是问闪避率 ——
#:   野狗那 1.3 倍闪避会让「两只都掉血」变成掷硬币（实测 6 跑 2 红）。把两只的 dodge 归零，
#:   判据本体一个字没松（要验闪避另有 landing 那一层）。
for _e5a in (_b5.sides.get("enemy") or []):
    _e5a["dodge"] = 0
_mx5 = int(ST.actor_max_hp(_b5, _c5) or 0)
_logs5 = []
SCH.advance(_b5, _logs5)
_e0_5 = [(a.get("name"), int(a.get("hp") or 0)) for a in (_b5.sides.get("enemy") or [])]
_sub5, _e5, _w5 = _b5.human_act("skill", "SKILL_BSK_sweep", _c5)
_logs5.extend(str(x) for x in (_sub5 or []))
SCH.settle_landing(_b5, _logs5, _c5)
_e1_5 = [(a.get("name"), int(a.get("hp") or 0)) for a in (_b5.sides.get("enemy") or [])]
#: 自伤那一笔从**它自己那一行**读（不拿血差算：advance / settle 里怪也会打他，血差混着别的账）
_cut5 = [int(x.split("−")[-1].rstrip("）。")) for x in _logs5 if "见了血" in x]
_want5 = int(round(_mx5 * float(MECH.of("blood_sweep")["self_dmg_pct"]["value"])))
(ok if len(_e0_5) >= 2 and all(h1 < h0 for (_n0, h0), (_n1, h1) in zip(_e0_5, _e1_5)) else bad)(
    "  · 端到端：横扫真出手 ⇒ **两只怪都掉血**（%s ⇒ %s）—— 引擎的 AOE 支逐目标独立结算"
    % (_e0_5, _e1_5))
(ok if _cut5 and _cut5[0] == _want5 else bad)(
    "  · 端到端：横扫的自伤 = max_hp %d × %s ⇒ %d（实测 %s）"
    % (_mx5, MECH.of("blood_sweep")["self_dmg_pct"]["value"], _want5, _cut5 or "没打出来"))
(ok if not (_c5.get("effects") or {}) else bad)(
    "  · 定向：横扫**不挂任何状态**（它只有自伤那一半 + 伤害）：%s" % (sorted(_c5.get("effects") or {}),))

print()
print("── ⑱ 游侠 / 法师 / 修女的新机制（打断减速 · 静默控制 · 有代价的防御 · 自保）")
_b = fresh("cls_ranger")
_c = _b.focus()
_t = (_b.sides.get("enemy") or [None])[0]
SCH.pending_begin(_b, ActCtx(caster=_t, action="skill", skill_name="x", info={}))
_was = bool(_t.get("charging"))
_sp0 = float(ST.actor_stats(_b, _t).get("spd", 0) or 0)
apply_mech(_b, _c, _t, "SKILL_RNG_pindown")
_sp1 = float(ST.actor_stats(_b, _t).get("spd", 0) or 0)
_mp = float(MECH.state_rule("pinned")["panel"]["mult"])
(ok if _was and not _t.get("charging") else bad)(
    "  · 定向：箭止清掉对方那一手（登记 %s ⇒ 现在 %s）" % (_was, _t.get("charging")))
(ok if abs(_sp1 - int(_sp0 * _mp)) < 1e-6 and _sp0 > 0 else bad)(
    "  · 定向：pinned 让它的 spd %.1f ⇒ %.1f（声明 ×%s ⇒ 期望 %d）" % (_sp0, _sp1, _mp, int(_sp0 * _mp)))
(ok if abs(float(((_t.get("effects") or {}).get("pinned") or {}).get("expire") or 0)
           - (_b._now + float(SKD["SKILL_RNG_pindown"]["mech_val"]))) < 1e-6 else bad)(
    "  · 定向：减速时长 = mech_val(%s) 刻" % SKD["SKILL_RNG_pindown"]["mech_val"])
_b2 = fresh("cls_ranger", lv=16, mid=DOG)             # 目标要够厚：暴击那一下会把田鼠直接打死
_b2._ensure_battle_started([])                        # 先推开门（它会把资源摆 0），再垫
_b2.focus().setdefault("effects", {})["RES_AIM"] = {"stacks": 2, "expire": None}     # 箭止要 2 层准星
_c2, _t2, _l2 = do(_b2, "SKILL_RNG_pindown")
(ok if has(_l2, "COMBAT_MECH_PINDOWN") else bad)("  · 端到端：真出手 ⇒ 出「箭钉在它起手的地方」那一行")

_b3 = fresh("cls_mage")
_c3 = _b3.focus()
_t3 = (_b3.sides.get("enemy") or [None])[0]
apply_mech(_b3, _c3, _t3, "SKILL_MAG_silence")
_e3 = ((_t3.get("effects") or {}).get("silenced") or {})
(ok if str(_e3.get("mode") or "") == str(MECH.of("silence_lock").get("mode") or "") and _e3 else bad)(
    "  · 定向：静默挂的是**控制**（条目 mode=%r —— 引擎的行动前检查认的就是这一格）" % (_e3.get("mode"),))
(ok if abs(float(_e3.get("expire") or 0) - (_b3._now + float(SKD["SKILL_MAG_silence"]["mech_val"]))) < 1e-6 else bad)(
    "  · 定向：控制时长 = mech_val(%s) 刻" % SKD["SKILL_MAG_silence"]["mech_val"])
_b4 = fresh("cls_priest", lv=16)
_c4 = _b4.focus()
apply_mech(_b4, _c4, _c4, "SKILL_MAG_silence")       # 静默挂在修女身上（模拟"她也被沉默了"）
_had4 = "silenced" in (_c4.get("effects") or {})
apply_cast(_b4, _c4, "SKILL_PRS_absolve")
(ok if _had4 and not ((_c4.get("effects") or {}).get("silenced")) else bad)(
    "  · 交叉：修女的净罪能摘掉「静默」这条控制（控制只有一处判据 = 条目带不带 mode）")
_b5 = fresh("cls_mage")
_c5 = _b5.focus()
_m0 = float(ST.actor_stats(_b5, _c5).get("matk", 0) or 0)
apply_mech(_b5, _c5, _c5, "SKILL_MAG_frostveil")
_m1 = float(ST.actor_stats(_b5, _c5).get("matk", 0) or 0)
#: ★ 承伤乘区那半在**试桩**上量（玩家 actor 自带 2~6% 闪避 ⇒ 直接打他自己会掷硬币）
_a5 = stub(battle=_b5)
_a5.setdefault("effects", {})["frost_shell"] = {"stacks": 1, "expire": _b5._now + 240}
_r5 = hit(_b5, _a5, 100)
(ok if _r5 == 65 and _m1 == int(_m0 * 0.8) else bad)(
    "  · 定向：霜障两头都真落地（承伤 100 ⇒ %d · matk %.0f ⇒ %.0f —— 代价那半也算上）" % (_r5, _m0, _m1))
_b6 = fresh("cls_priest")
_c6 = _b6.focus()
apply_mech(_b6, _c6, _c6, "SKILL_PRS_nightwatch")
_a6 = stub(battle=_b6)
_a6.setdefault("effects", {})["night_lamp"] = {"stacks": 1, "expire": _b6._now + 250}
_r6 = hit(_b6, _a6, 100)
_h0 = float(ST.actor_stats(_b6, _c6).get("heal_pow", 0) or 0)
(ok if _r6 == 65 and _h0 > 0 else bad)(
    "  · 定向：守夜承伤 100 ⇒ %d、治疗强度 %.1f（F8 的基数 ×1.25）" % (_r6, _h0))
_b7 = fresh("cls_priest", lv=16)
_c7, _t7, _l7 = do(_b7, "SKILL_PRS_nightwatch")
(ok if has(_l7, "COMBAT_MECH_NIGHTWATCH") else bad)("  · 端到端：真出手 ⇒ 出「你把灯挪到自己跟前」那一行")

print()
print("── ⑲ 刺客两条新机制（割喉 = 叠层流血 DoT · 侧闪 = 只动闪避那一格）")
_b = fresh("cls_assassin")
_c = _b.focus()
_st = stub(hp=1000, battle=_b)
for _i in (1, 2, 3, 4):
    apply_mech(_b, _c, _st, "SKILL_SHD_bleed")
_e = ((_st.get("effects") or {}).get("bleeding") or {})
_cap = int(MECH.state_rule("bleeding")["cap"])
(ok if int(_e.get("stacks") or 0) == _cap else bad)(
    "  · 定向：连割四刀 ⇒ 层数停在 cap（%d 层；声明 cap=%d）" % (int(_e.get("stacks") or 0), _cap))
(ok if abs(float(_e.get("expire") or 0) - (_b._now + float(SKD["SKILL_SHD_bleed"]["mech_val"]))) < 1e-6 else bad)(
    "  · 定向：流血时长 = mech_val(%s) 刻" % SKD["SKILL_SHD_bleed"]["mech_val"])
_per = MECH.state_rule("bleeding")["period"]
_snap = int((_e.get("src") or {}).get("atk") or 0)
_want_tick = int(_snap * float(_per["atk"]) * int(_e.get("stacks") or 0))
SCH._advance_time(_b, 1.0, [])                    # 首次挂：引擎先登记下一跳（这一下不结算）
_ticks = []
SCH._advance_time(_b, float(_per["interval"]), _ticks)
_hits = [int(x.split("损失 ")[1].split(" 生命")[0]) for x in _ticks if "损失" in x]
(ok if _hits and _hits[0] == _want_tick else bad)(
    "  · 定向：真推 %s 刻 ⇒ 一跳 %s 点（= 快照 atk %d × %s × %d 层 ⇒ 期望 %d）"
    % (_per["interval"], _hits or "没跳", _snap, _per["atk"], int(_e.get("stacks") or 0), _want_tick))
_st["hp"] = 100                                   # 见底（100 < 上限 1000 的 30%）
_ticks2 = []
SCH._advance_time(_b, float(_per["interval"]), _ticks2)
_hits2 = [int(x.split("损失 ")[1].split(" 生命")[0]) for x in _ticks2 if "损失" in x]
(ok if _hits2 and _hits2[0] == _want_tick * 2 else bad)(
    "  · 定向：目标见底 ⇒ 那一跳翻倍（%s vs 期望 %d）" % (_hits2 or "没跳", _want_tick * 2))
_b2 = fresh("cls_assassin", lv=16, mid=DOG)           # 目标要够厚（暴击那一下能秒掉田鼠）
_c2, _t2, _l2 = do(_b2, "SKILL_SHD_bleed")
(ok if has(_l2, "COMBAT_MECH_BLEED") else bad)("  · 端到端：真出手 ⇒ 出「刀口拉得很深」那一行")
_b3 = fresh("cls_assassin")
_c3 = _b3.focus()
apply_mech(_b3, _c3, _c3, "SKILL_SHD_sidestep")
_eva = float(ST.actor_stats(_b3, _c3).get("eva", 0) or 0)
_a3 = stub(battle=_b3)                                 # ★ 同上：乘区那半在试桩上量
_a3.setdefault("effects", {})["sidestep_veil"] = {"stacks": 1, "expire": _b3._now + 180}
_r3 = hit(_b3, _a3, 100)
(ok if _r3 == 100 else bad)(
    "  · 定向：侧闪**不动减伤**（100 点还是 100 点 —— 它改的是打不打得到；玩家自己的 eva 现算 %.1f）" % _eva)
(ok if abs(float(((_c3.get("effects") or {}).get("sidestep_veil") or {}).get("expire") or 0)
           - (_b3._now + float(SKD["SKILL_SHD_sidestep"]["mech_val"]))) < 1e-6 else bad)(
    "  · 定向：侧闪时长 = mech_val(%s) 刻" % SKD["SKILL_SHD_sidestep"]["mech_val"])

print()
print("── ⑳ 六条职业被动（battle_start 常驻 ×4 · dmg_calc 血线 ×1 · 一条登记未接）")
#: (职业, 机制, 规则键, 看的属性, op, 那个数)
_PASS = (("cls_ranger", "hawk_eye", "hawk_eye_hit", "hit", "mul", 1.12),
         ("cls_ranger", "hawk_eye", "hawk_eye_crit", "crit", "add", 8),
         ("cls_mage", "starred", "starlit", "matk", "mul", 1.12),
         ("cls_priest", "comfort", "soothed", "heal_pow", "mul", 1.12),
         ("cls_assassin", "keen_edge", "whetted", "critdmg", "add", 30))
#: 每个职业那条零消耗普攻 —— 用来**真出手**驱动开战（`battle_start` 由 `human_act` 那一趟触发，
#: `advance` 不触发它：引擎的 `_ensure_battle_started` 挂在行动入口上）
_BASIC_OF = {}
for _sid, _rec in SKD.items():
    if _rec.get("basic") is True and _rec.get("owner_class"):
        _BASIC_OF[_rec["owner_class"]] = _sid
_bad_pass = []
for _cls, _mk, _key, _stat, _op, _num in _PASS:
    _bb = fresh(_cls, lv=16)
    _cc = _bb.focus()
    _s0 = float(ST.actor_stats(_bb, _cc).get(_stat, 0) or 0)
    do(_bb, _BASIC_OF[_cls])                          # 开战那一趟（真出手 ⇒ battle_start 整场一次）
    _ef = _cc.get("effects") or {}
    _s1 = float(ST.actor_stats(_bb, _cc).get(_stat, 0) or 0)
    _want = (_s0 + _num) if _op == "add" else int(_s0 * _num)
    if _key not in _ef or abs(_s1 - _want) > 1e-6:
        _bad_pass.append((_cls, _mk, _key, _s0, _s1, _want, sorted(_ef)))
(ok if not _bad_pass else bad)(
    "  · 开战那一趟之后：四条常驻被动都挂上了、面板逐值对得上（%d 条断言）　%s"
    % (len(_PASS), "全对" if not _bad_pass else "红：%s" % _bad_pass[:2]))
_bad_lv = []
for _cls, _mk, _key, _stat, _op, _num in _PASS:
    _bb = fresh(_cls, lv=15)                          # 被动 16 级才开（真源 05_系统总表）
    _cc = _bb.focus()
    do(_bb, _BASIC_OF[_cls])
    if _key in (_cc.get("effects") or {}):
        _bad_lv.append((_cls, _mk, _key))
(ok if not _bad_lv else bad)(
    "  · ★ 等级闸：15 级的号**一个被动都没开**（16 级才开 —— 少了这一道，13 级就白拿 16 级的被动，"
    "实测会把 `probe_combat ④`「层主低 4 级单刷打不过」那条判据撞红）　%s"
    % ("全对" if not _bad_lv else "红：%s" % _bad_lv[:2]))
from ext_combat.battle.effect_triggers import fire as _fire                 # noqa: E402
_bb = fresh("cls_berserker", lv=16)
_cc = _bb.focus()
_tt = (_bb.sides.get("enemy") or [None])[0]
_mx = float(ST.actor_max_hp(_bb, _cc) or 0)
_cc["hp"] = int(_mx * 0.9)
_ctx_hi = {"actor": _cc, "target": _tt, "dmg": 100}
_fire(_bb, "dmg_calc", _ctx_hi, [])
_cc["hp"] = int(_mx * 0.4)
_ctx_lo = {"actor": _cc, "target": _tt, "dmg": 100}
_fire(_bb, "dmg_calc", _ctx_lo, [])
_mm = float(MECH.of("blood_brave")["dmg_mult"]["value"])
(ok if _ctx_hi.get("mult") is None and abs(float(_ctx_lo.get("mult") or 0) - _mm) < 1e-9 else bad)(
    "  · 血勇：血在线上（90%%）乘区不写 ｜ 掉到线下（40%%）乘区 ×%s（按出手那一刻现算，不留过期态）"
    % (_mm,))
_bb2 = fresh("cls_berserker", lv=15)
_cc2 = _bb2.focus()
_cc2["hp"] = int(float(ST.actor_max_hp(_bb2, _cc2) or 0) * 0.4)
_ctx2 = {"actor": _cc2, "target": (_bb2.sides.get("enemy") or [None])[0], "dmg": 100}
_fire(_bb2, "dmg_calc", _ctx2, [])
(ok if _ctx2.get("mult") is None else bad)(
    "  · ★ 血勇同样吃等级闸：15 级血再少也不加成（mult=%s）" % (_ctx2.get("mult"),))
_bo = MECH.of("block_oath")
_bo_ok = (_bo.get("status") == "on" and _bo.get("route") == "trigger"
          and _bo.get("trigger") == "taken_calc" and _bo.get("verb") == "aeth_block_roll"
          and not EF.missing_actions([_bo.get("verb")])
          and float((_bo.get("block_chance") or {}).get("value") or 0) > 0
          and float((_bo.get("oath_bonus") or {}).get("value") or 0) > 0)
(ok if _bo_ok else bad)(
    "  · ★ 格挡回誓：**已接线**（status=on · route=trigger · trigger=taken_calc · 动词已注册 · "
    "概率与回誓都是声明）—— 掷骰/减免/回誓的逐值判据在 `probe_resources` ⑥（接之前这里是 pending）")
_ea, _er = GC.get_effect_actions() or {}, GC.get_effect_rules() or {}
(ok if "blood_sweep" in _ea and not (set(MECH.mechs()) & set(_er)) else bad)(
    "  · ★ 17 条新机制：route=engine 的进了 EFFECT_ACTIONS · 机制名一个都没进 EFFECT_RULES（防叠层劫持）")
_teeth.clear()
_b1 = copy.deepcopy(MECH.table())
_b1["mechs"]["blood_brave"]["trigger"] = "no_such_event"
_try(lambda: MECH._validate(_b1), ValueError, "trigger 事件没挂")
_b2 = copy.deepcopy(MECH.table())
_b2["mechs"]["hawk_eye"]["verb"] = "aeth_on_taken"
_try(lambda: MECH._validate(_b2), ValueError, "trigger 与动词配错")
_b3 = copy.deepcopy(MECH.table())
_b3["mechs"]["riposte"]["consume_event"] = "no_such_event"
_try(lambda: MECH._validate(_b3), ValueError, "consume_event 没挂")
(ok if not _teeth else bad)(
    "  · ★ 第三条路的三种坏声明也当场抛（事件没挂 / 动词配错 / 消费事件没挂）　%s"
    % ("全对" if not _teeth else "红：%s" % _teeth))

print()
print("── ㉑ ★ fxmech：狂战士那两条自付血（狂斩 12% 生命上限 · 焚身 35% 当前生命 / 上限 40 点）")
#  改前：这两条**一分钱不付** —— 实测放 13 次逐手血账差额恰好 = 对面咬伤（域里没 `mech`、
#  表里没 `rampage` / `immolate`，付血那一个公共件 `_self_cut` 只被 破势/血债/狂态/横扫 调）。
#  现在走 route=cast（出手那一刻付，早于命中）：命不命中都付（自伤不是命中效果）。


def _no_dodge():
    """fixture：把**闪避上限**临时压成 0 —— 自伤那一档要问的是「扣了多少」，不是「你自己闪没闪开」。

    为什么必须收（收的是 fixture，判据一个字没松）：`_self_cut` 走引擎的承伤链
    （`landing.deal_damage`），那条链上先有一枚硬币（`_roll_dodge`）。狂战士 1 级 dodge 率
    ≈ 2.3% ⇒ 单跑约 44 次红一次。收口走**引擎自己的声明面**（`formula_skeleton_fn` 的
    `dodge.cap`，读口 `dodge_cap()`）—— 与 `probe_resources.py::no_dodge()` 同一处写法。
    """
    from saintess_engine import config as _CFG
    from ext_combat.battle import formulas as _F
    _saved = _CFG.optional_hook("formula_skeleton_fn")
    _sk = dict(_F._skeleton() or {})
    _sk["dodge"] = dict(_sk.get("dodge") or {}, cap=0.0)
    _CFG.mount(formula_skeleton_fn=lambda: _sk)
    return _saved


def _restore_dodge(_saved):
    from saintess_engine import config as _CFG
    _CFG.set_hook("formula_skeleton_fn", _saved)


def _self_cut_of(logs):
    """日志里那一行「自己先见了血（−N）」→ N（表里声明的那一笔）。"""
    return [int(x.split("−")[-1].rstrip("）。")) for x in logs if "见了血" in x]


def _bare(cls, lv=1, hp=None, mid=DOG, uid="u_self"):
    """起一个「已经开战、还没人出手」的战斗（自伤那几档不推时间 ⇒ 没有对面咬伤混进血账）。"""
    _b = CMB.build({"cls": cls, "level": lv, "uid": uid, "name": "试", "hp": hp}, [mid], MON, party=1)
    _b._ensure_battle_started([])
    return _b, _b.focus()


_sd = _no_dodge()
_b, _c = _bare("cls_berserker", mid=DOG, hp=500)
_mx = int(ST.actor_max_hp(_b, _c) or 0)
_hp0 = int(_c["hp"])
apply_cast(_b, _c, "SKILL_BSK_rampage")
_cut = _hp0 - int(_c["hp"])
_x = float(MECH.of("rampage")["self_dmg_pct"]["value"])
(ok if _cut == int(round(_mx * _x)) and _cut > 0 else bad)(
    "  · 狂斩（route=cast）：出手那一刻**真扣** %d（= max_hp %d × %s ⇒ 期望 %d）—— 改前是 0"
    % (_cut, _mx, _x, int(round(_mx * _x))))

_b, _c = _bare("cls_berserker", lv=16, mid=DOG)
_hp0 = int(_c["hp"])
apply_cast(_b, _c, "SKILL_BSK_immolate")
_cut = _hp0 - int(_c["hp"])
_cap = int(MECH.of("immolate")["self_dmg_cap"]["value"])
(ok if _cut == _cap and _hp0 * 0.35 > _cap else bad)(
    "  · 焚身：血 %d 的 35%% = %d > 上限 %d ⇒ 真扣 **%d**（上限那一格声明在表里）"
    % (_hp0, int(_hp0 * 0.35), _cap, _cut))

_b, _c = _bare("cls_berserker", lv=16, mid=DOG)
_c["hp"] = int(_c["hp"]) // 2
_hp0 = int(_c["hp"])
apply_cast(_b, _c, "SKILL_BSK_immolate")
_cut = _hp0 - int(_c["hp"])
_want2 = min(int(round(_hp0 * float(MECH.of("immolate")["self_dmg_pct"]["value"]))), _cap)
(ok if _cut == _want2 and _cut < _cap else bad)(
    "  · 焚身的**基数 = 当前生命**（不是上限）：半血 %d ⇒ 付 %d（35%% ⇒ %d，未到上限）"
    % (_hp0, _cut, _want2))

_b, _c = _bare("cls_berserker", mid=DOG)
_c["hp"] = 2
apply_cast(_b, _c, "SKILL_BSK_rampage")
(ok if int(_c["hp"]) == 1 else bad)(
    "  · 付了不够血 ⇒ 只扣到剩 **1 血**（真源 02_狂战士_v2 §二「不能把自己打死」；"
    "「血 < 12% 时这一手不可用」那道门今天没有注入面 —— 登记在表里的 halves）")

_b4 = fresh("cls_berserker", mid=DOG, hp=500)
_c4, _t4, _l4 = do(_b4, "SKILL_BSK_rampage")
(ok if _self_cut_of(_l4) else bad)("  · 端到端：真出手 ⇒ 出「自己先见了血」那一行")
_b5 = fresh("cls_berserker", mid=DOG, hp=500)
_c5, _t5, _l5 = do(_b5, "SKILL_BSK_sunder")
_w5 = int(round(float(ST.actor_max_hp(_b5, _c5) or 0)
                * float(MECH.of("def_break")["self_dmg_pct"]["value"])))
(ok if _self_cut_of(_l5) == [_w5] else bad)(
    "  · 回归：破势（走命中后的 engine 路）自伤口径一点没变（%s，期望 [%d]）" % (_self_cut_of(_l5), _w5))

#: ★ fix-a-screen（2026-09-27 · ①）：一笔自付**只出一行**。落地照旧走引擎那条
#:   （`LD.deal_damage` —— 结算 / 事件 / 保底 1 血一个字不动），但引擎那条**通用**伤害行
#:   （`battle.landing.damage` = `💥 {name} 受到 {dmg} 点伤害！`，与「被怪打」同形）在**自付那一调**
#:   里被顶掉（`content/battle_text.quiet_engine_damage`）⇒ 屏上只剩本包的专用行；
#:   专用行报的数是**真扣下去的那一笔**（= 血账差分）。
_b6, _c6 = _bare("cls_berserker", mid=DOG, hp=500)
_hp6 = int(_c6["hp"])
_l6 = apply_cast(_b6, _c6, "SKILL_BSK_rampage")
_d6 = _hp6 - int(_c6["hp"])
_hurt6 = [x for x in _l6 if "受到" in x]
(ok if _self_cut_of(_l6) == [_d6] and _d6 > 0 and not _hurt6 else bad)(
    "  · 一笔自付**只出一行**：专用行 %s（真扣 %d）· 引擎那条通用伤害行不再重复（%s）"
    % (_self_cut_of(_l6), _d6, _hurt6[:1] or "没有"))

#: 反证（这一条判据不是空转）：同一调里「怪打你」那条**照旧**上屏 —— 遮挡只认自付那一笔，
#:   没把引擎那条 key 全局改掉（`content/rules/battle_text.json` 里它**照样没声明**）。
_b7, _c7 = _bare("cls_berserker", mid=DOG, hp=500)
_l7 = []
LD.deal_damage(_b7, _b7.sides["enemy"][0], _c7, 20, _l7)
(ok if [x for x in _l7 if "受到" in x] else bad)(
    "  · 反证：「挨打」那条通用伤害行照旧（%s）—— 遮挡只作用于自付那一笔"
    % ([x for x in _l7 if "受到" in x][:1] or "不见了"))
_restore_dodge(_sd)

print()
print("── ㉒ ★ fxmech：法师的印记 → 引爆（兑现端）+ 垂星的砸晕")


def _burst_off():
    """fixture：把 `mark_burst` 的 `burst` 那一格临时拿掉 = **同一发不带印记加成**的对照臂。"""
    _m = MECH.of("mark_burst")
    _saved = _m.get("burst")
    _m.pop("burst", None)
    return _saved


def _burst_on(_saved):
    if _saved is not None:
        MECH.of("mark_burst")["burst"] = _saved


#: 铺印记那一套（星屑 +1 · 焰痕 +2）—— 本判据固定用它铺到 5 层
_MARK_ROT = ("SKILL_MAG_stardust", "SKILL_MAG_flameprint", "SKILL_MAG_flameprint")


def _burst_run(sid, seed=7):
    """同一场 / 同一手 / 同一枚种子：铺 5 层 → 引爆。返回 (伤害, 层数快照, 日志, 施法者, 目标, 战斗)。"""
    random.seed(seed)
    _bb = fresh("cls_mage", lv=2, mid=DOG, hp=3000)
    _bb._ensure_battle_started([])
    SCH.advance(_bb, [])
    for _s in _MARK_ROT:
        _cc, _tt, _ll = do(_bb, _s)
    _tr = dict(_cc.get(MECH._TRACE_KEY) or {})
    _t = (_bb.sides.get("enemy") or [None])[0]
    _h0 = int(_t.get("hp") or 0)
    _c2, _t2, _l2 = do(_bb, sid)
    return _h0 - int(_t2.get("hp") or 0), _tr, _l2, _c2, _t2, _bb


_d_burst, _tr, _lg, _cc, _t2, _bb = _burst_run("SKILL_MAG_ignite")
_n = 5
_p = float(SKD["SKILL_MAG_ignite"]["power"])
_x = float(SKD["SKILL_MAG_ignite"]["mech_val"])
_want_mult = (_p + _n * _x) / _p
_saved_burst = _burst_off()
_d_base, _tr2, _lg2, _cc2, _t3, _bb2 = _burst_run("SKILL_MAG_ignite")
_burst_on(_saved_burst)
(ok if _tr == {"RES_MARK": _n} else bad)(
    "  · 出手那一刻的层数快照 = %s（引擎的扣费/清空都在 `act_cast` **之前** ⇒ 兑现端只能读这一格）"
    % (_tr,))
(ok if abs(_d_burst - _d_base * _want_mult) <= max(2.0, 0.06 * _d_base * _want_mult) else bad)(
    "  · 引燃（出手前 %d 层）：伤害 **%d** ｜ 同一发不带印记加成（同种子对照臂）%d ⇒ 倍数 %.2f"
    "（声明 (power %s + %d × mech_val %s) / %s = %.2f）"
    % (_n, _d_burst, _d_base, (_d_burst / _d_base) if _d_base else 0, _p, _n, _x, _p, _want_mult))
(ok if _d_burst >= _d_base * 2 else bad)(
    "  · 方向：引爆这一发至少是底数的 **2 倍**（改前：引燃 12 < 免费星屑 20 —— 铺印记等于白做）")
(ok if int((((_cc.get("effects") or {}).get("RES_MARK")) or {}).get("stacks") or 0) == 0 else bad)(
    "  · 放完**清空**印记（引擎 `consume_all`）")
(ok if MECH.of("mark_burst").get("burst") and not _cc.get(MECH._TRACE_KEY) else bad)(
    "  · 快照**一次性**：这一发用完即销（快照格 = %s）" % (_cc.get(MECH._TRACE_KEY),))

# ★ fxmech（2026-09-26）：检查点从「整轮跑完」挪到**落地那一刻** —— B4-4 接线后垂星自己
#   的落地要 227.8 刻、引擎的推进循环还会继续往后走，等整轮跑完那 100 刻早过期了
#   （旧写法在接线前是对的，因为所有技能都按类别 80/50 算，落地早、推进短）。
def _star_landing():
    """铺 5 层 → 垂星，**只推到落地**（`settle_landing` 一步），回（伤害, 日志, 施法者, 目标, 战斗）。"""
    random.seed(7)
    _bb = fresh("cls_mage", lv=2, mid=DOG, hp=3000)
    _bb._ensure_battle_started([])
    SCH.advance(_bb, [])
    for _s in _MARK_ROT:
        do(_bb, _s)
    _cc = _bb.focus()
    _info = GC.skill_by_key("SKILL_MAG_fallenstar") or SKD["SKILL_MAG_fallenstar"]
    _t = (_bb.sides.get("enemy") or [None])[0]
    _h0 = int(_t.get("hp") or 0)
    _bb.act(ActCtx(caster=_cc, action="skill", skill_name=_info.get("name"), info=_info, target=_t))
    _lg = []
    SCH.settle_landing(_bb, _lg, _cc)                 # ← 只到落地这一点，不再往后推
    return _h0 - int(_t.get("hp") or 0), [str(x) for x in _lg], _cc, _t, _bb


_d_star, _lg3, _c3, _t4, _bb4 = _star_landing()
(ok if any("晕了" in x for x in _lg3) else bad)(
    "  · 垂星：伤害 %d + 出「砸晕」那一句（改前：垂星 26 < 星屑 51，而且没有砸晕）" % _d_star)
_e4 = ((_t4.get("effects") or {}).get("star_daze")) or {}
_turns = float(SKD["SKILL_MAG_fallenstar"]["mech2_val"])
(ok if _e4 and str(_e4.get("mode") or "") == str(MECH.of("star_stun").get("mode") or "")
    and 0 < float(_e4.get("expire") or 0) - _bb4._now <= _turns else bad)(
    "  · 砸晕落在**目标**身上：`star_daze`（mode=%s · 剩余 %.1f 刻 ≤ mech2_val %s）"
    % (_e4.get("mode"), float(_e4.get("expire") or 0) - _bb4._now, _turns))
_sub4, _end4 = _bb4.actor_auto(_t4)
_ctl = [str(x) for x in (_sub4 or [])]
#: ★ 2026-09-27（夜班试玩 w3）：这一行的**措辞本波起走槽位**（`battle.core.controlled`）——
#:   原先写死的那个中文词是**引擎兜底模板**里的字，而那句兜底会把状态机器键 `star_daze`
#:   原样打到玩家屏（两个号实测逐字：「💫 游荡的骸骨 被【star_daze】控制，无法行动！」）。
#:   判据改成「按槽位逐字对」（与 DoT 那条同款）**并加一条**：机器键不上屏 ⇒ 只紧不松。
(ok if has(_ctl, "COMBAT_CONTROLLED") and not any("star_daze" in x for x in _ctl) else bad)(
    "  · 这 100 刻里轮到它 ⇒ 引擎的行动前检查把这一手整手跳过 · 那行走槽位渲染、"
    "且机器键不上屏（真源 02_战斗机制 §〇·五）")
(ok if not ((_t2.get("effects") or {}).get("star_daze")) else bad)(
    "  · 引燃（同一条 `mark_burst`、没有 mech2）**不挂**砸晕 —— 两半各自钉住")

print()
print("── ㉓ ★ fxmech：修女「治疗强度」不是死属性（F8 = 治疗量的**基数**）")
_info_h = GC.skill_by_key("SKILL_PRS_lullaby")
_h_rows = []
for _wil in (0, 6, 11):
    _hb = CMB.build({"cls": "cls_priest", "level": 2, "uid": "u_heal%d" % _wil, "name": "试",
                     "alloc": {"WIL": _wil}}, [MID], MON, party=1)
    _hb._ensure_battle_started([])
    SCH.advance(_hb, [])
    _hc = _hb.focus()
    _hst = ST.actor_stats(_hb, _hc)
    _hf8 = MECH._heal_base_of(_hb, _hc, _info_h)
    _heng = ACT.heal_amount(_hst, _hc, _info_h, 1)
    _hc["hp"] = 100
    _hlog = []
    _sub, _en, _wn = _hb.human_act("skill", "SKILL_PRS_lullaby", _hc)
    _hlog += [str(x) for x in (_sub or [])]
    SCH.settle_landing(_hb, _hlog, _hc)
    _got = [x for x in _hlog if "治愈了" in x or "圣光治愈" in x]
    _h_rows.append((_wil, float(_hst.get("heal_pow", 0) or 0), _hf8, _heng, _got[:1]))
(ok if all(abs(r[2] - r[1] * float(_info_h["power"])) < 1e-6 for r in _h_rows) else bad)(
    "  · F8 现算：治疗量 == 治疗强度 × 倍率（%s）"
    % " · ".join("WIL%d：%.1f×%s=%.1f" % (r[0], r[1], _info_h["power"], r[2]) for r in _h_rows))
(ok if _h_rows[0][2] < _h_rows[1][2] < _h_rows[2][2] else bad)(
    "  · 往意志里灌（0 → 6 → 11 点）⇒ 治疗量跟着涨：%s"
    % " → ".join("%.0f" % r[2] for r in _h_rows))
(ok if _h_rows[0][3] == _h_rows[2][3] != int(_h_rows[2][2]) else bad)(
    "  · 对照：引擎那一口（兜底 `matk × power`）三条一样 —— **%d**（改前实测：意志 15→31、"
    "治疗量恒 30 —— 治疗强度是死属性）" % int(_h_rows[0][3]))
(ok if _h_rows[2][4] and ("%d" % int(_h_rows[2][2])) in str(_h_rows[2][4][0]) else bad)(
    "  · 端到端：真放一次 ⇒ 落地那一发就是 F8 那一发（%s）" % (_h_rows[2][4][:1] or "没打出来"))


def _f8_off():
    """撤改：把 F8 那一格拿掉（= 公式表没装配）⇒ 基数回落引擎那一口（与接线前一字不差）。"""
    _saved = MECH._f8_heal
    MECH._f8_heal = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("撤改：F8 取不到"))
    return _saved


def _f8_back(_saved):
    MECH._f8_heal = _saved


_sf = _f8_off()
try:
    _hb2 = CMB.build({"cls": "cls_priest", "level": 2, "uid": "u_healoff", "name": "试",
                      "alloc": {"WIL": 11}}, [MID], MON, party=1)
    _hb2._ensure_battle_started([])
    _hc2 = _hb2.focus()
    _hb2._ensure_battle_started([])
    _off_base = MECH._heal_base_of(_hb2, _hc2, _info_h)
    _off_eng = ACT.heal_amount(ST.actor_stats(_hb2, _hc2), _hc2, _info_h, 1)
finally:
    _f8_back(_sf)
(ok if abs(_off_base - _off_eng) < 1e-6 and _off_eng > 0 else bad)(
    "  · ★ 撤改反证：F8 取不到 ⇒ 基数就是引擎那一口（%d == %d；治疗照旧出得来）"
    % (_off_base, _off_eng))

print()
print("── ㉔ ★ fxmech 复核：冷却这个消费端是活的（+ 一个登记：真源那些 cd 数都小于一次行动）")
from content import skills_lookup as _SL_CD          # noqa: E402  —— 引擎那个取件口读的就是它
_sk_back = _SL_CD.skills()["SKILL_RNG_backstep"]      # ★ 引擎读的是这一份（`skill_by_key` 的取件口）
_cd_old = _sk_back.get("cd")
#: ★ fixture 收口：合成 cd 要**大过这一场里可能流逝的刻数**（两可出手之间对手会行动好几轮，
#:   野狗 spd 那一档实测能推走 300+ 刻 ⇒ cd=300 会被时间自然磨掉 = 判据假红）。
#:   10 万刻 ≈ 27 小时游戏时间 ⇒ 这一场里绝不可能到期（判据本体一个字没松）。
_sk_back["cd"] = 100000
try:
    _b, _c = _bare("cls_ranger", mid=DOG, hp=3000)
    _cc1, _tt1, _ll1 = do(_b, "SKILL_RNG_backstep")
    _cc2, _tt2, _ll2 = do(_b, "SKILL_RNG_backstep")
finally:
    _sk_back["cd"] = _cd_old
(ok if any(("缓" in x) or ("冷却" in x) for x in _ll2) else bad)(
    "  · 合成 cd=10 万刻 ⇒ 同一场第二手当场被拦（%s）—— 「冷却」不是装饰"
    % ([x for x in _ll2 if ("缓" in x) or ("冷却" in x)][:1] or "没拦"))
_cd_max = max(int(v.get("cd") or 0) for v in SKD.values()
              if isinstance(v, dict) and v.get("owner_class") and v.get("kind_key") == "active")
print("  · 登记（不当判据）：域里全部主动技的 cd 最大值 = %d 刻；真源 `02_数值宪法/02_战斗机制.md` §〇"
      "「所有时长（前摇 / 后摇 / 冷却 / 状态 / DoT）一律用刻」⇒ cd 与一次行动同单位，"
      "而六职业一次行动 ≈ 90–130 刻 ⇒ 这些 cd 在结构上不可能触发（真源数如此，不是接线缺口）。"
      % _cd_max)
print("  · 登记：域里「焚身」那句「一场只放得出一次」与它的 `cd: 30` 打架（要落那句话得先有"
      "「每场一次」这个形状，引擎的冷却只有绝对时刻制）—— 见 _notes.md 的真源行。")

print()
print("── ㉕ ★ fxmech：技能自己声明的 cast/recover（B4-4 接线 · 落地与到点同源）")
#  改前：技能 dict 里那两段**没人读**（引擎按行动类别 skill 80/50 算）—— 引燃设计 227.8 刻、
#        现算 123.4 刻；垂星 275.3 / 123.4；断势 47.1 / 102.1。
#  改后：`pending_begin`（落地）与 `_after_act`（下次能动的时刻）**同一个函数、同一份声明**。
_TM = CFG.get_hook("time_model_fn")                    # 内容侧时间模型（第一段）
_RM = CFG.get_hook("recover_model_fn")                 # 内容侧第二段模型（独立的一条面）


def _plan_off():
    """撤改臂：把 E5 那条挂载拿掉 ⇒ 引擎落回类别基准（= 接线前那一态）。"""
    saved = CFG.optional_hook("segment_plan_fn")
    CFG.set_hook("segment_plan_fn", None)
    return saved


def _plan_on(saved):
    CFG.set_hook("segment_plan_fn", saved)


def _landing_and_ct(b, caster, sid):
    """真跑：T0 登记（落地时刻）+ 推 ct（下次能动的时刻）—— 两个数分别量，口径写死。"""
    info = GC.skill_by_key(sid) or SKD[sid]
    t0 = float(getattr(b, "_now", 0) or 0)
    ctx = ActCtx(caster=caster, action="skill", skill_name=info.get("name"), info=info,
                 target=(b.sides.get("enemy") or [None])[0])
    b.act(ctx)
    slot = (caster.get("charging") or {})
    land = float(slot.get("cast_done_at") or 0) - t0
    caster.pop("charging", None)                      # 只量数，不真落地（下一手要干净）
    SCH._after_act(b, caster, "skill", plan=getattr(ctx, "_plan", None))
    ct = float(caster.get("ct") or 0) - t0
    return land, ct, info


_rows25 = []
for _cls, _sid in (("cls_berserker", "SKILL_BSK_rampage"), ("cls_mage", "SKILL_MAG_ignite"),
                   ("cls_assassin", "SKILL_SHD_sever"), ("cls_ranger", "SKILL_RNG_quickstep")):
    _b25 = fresh(_cls, mid=DOG, hp=5000)
    _b25._ensure_battle_started([])
    _c25 = _b25.focus()
    _spd = int(SCH._spd_of(_b25, _c25))
    _land, _ct, _info25 = _landing_and_ct(_b25, _c25, _sid)
    _w_c, _w_r = float(_info25["cast"]["base"]), float(_info25["recover"]["base"])
    _rows25.append((_sid, _spd, (_w_c, _w_r), round(_land, 1), round(_ct, 1),
                    round(float(_TM(_spd, _w_c)), 1), round(float(_RM(_spd, _w_r)), 1)))
_bad25 = [r for r in _rows25 if abs(r[3] - r[5]) > 0.05 or abs(r[4] - (r[5] + r[6])) > 0.15]
(ok if not _bad25 else bad)(
    "  ① 落地 = 技能自己的 cast · 到点 = cast + recover（四个职业逐条对账）　%s"
    % ("全对（%s）" % "｜".join("%s %.1f+%.1f → 落地%.1f · 到点%.1f" % (r[0].split("_")[-1], r[2][0], r[2][1], r[3], r[4])
                            for r in _rows25) if not _bad25 else "红：%s" % _bad25[:2]))

# ★ 同一份声明被两处读：槽里记下的 `cast_base` == 供体回的那一段（不许各自解析）
_b25b = fresh("cls_mage", mid=DOG, hp=5000)
_b25b._ensure_battle_started([])
_c25b = _b25b.focus()
_inf = GC.skill_by_key("SKILL_MAG_fallenstar") or SKD["SKILL_MAG_fallenstar"]
_ctxb = ActCtx(caster=_c25b, action="skill", skill_name=_inf.get("name"), info=_inf)
_b25b.act(_ctxb)
_slotb = (_c25b.get("charging") or {})
(ok if _slotb.get("cast_base") == _inf.get("cast") and _slotb.get("recover_base") == _inf.get("recover") else bad)(
    "  ② 同源：槽里那两格（落地用）== 技能自己声明的两段　%s"
    % ("cast %s · recover %s" % (_slotb.get("cast_base"), _slotb.get("recover_base"))))
_c25b.pop("charging", None)

# ★ 撤改臂：不挂 E5 ⇒ 落地/到点回到类别 skill 80/50
_saved25 = _plan_off()
try:
    _b25d = fresh("cls_berserker", mid=DOG, hp=5000)
    _b25d._ensure_battle_started([])
    _c25d = _b25d.focus()
    _spd_d = int(SCH._spd_of(_b25d, _c25d))
    _landd, _ctd, _ = _landing_and_ct(_b25d, _c25d, "SKILL_BSK_rampage")
    (ok if abs(_landd - float(_TM(_spd_d, 80.0))) < 0.05 and abs(_ctd - (float(_TM(_spd_d, 80.0)) + float(_RM(_spd_d, 50.0)))) < 0.05 else bad)(
        "  ④ 撤改（不挂 E5）⇒ 落地 %.1f / 到点 %.1f 刻 = 类别 skill 80/50（改前那一态）"
        % (_landd, _ctd))
finally:
    _plan_on(_saved25)

print()
print("── ㉖ ★ fxmech：出手前那道否决口（狂斩的血线门 · 焚身的每场一次）")
#  真源：02_狂战士_v2 §二「不能把自己打死 —— 血 < 12% 时这一手不可用」· §三「焚身 …… 一场战斗最多一次」。


def _fight(sid, hp=None, cls="cls_berserker"):
    """真跑一手：开战 → 真出手（T0 登记 → 落地 → 技能管线）。回（日志, 施放者, 战斗）。

    ★ 日志取 `human_act` 的**真回执**（它内部已经把落地推完了 —— 再 `settle_landing`
      一次只会拿到空表，那会让判据变成「什么都没发生」的假绿）。
    """
    b = fresh(cls, mid=DOG, hp=hp)
    b._ensure_battle_started([])
    c = b.focus()
    sub, _e, _w = b.human_act("skill", sid, c)
    logs = [str(x) for x in (sub or [])]
    SCH.settle_landing(b, logs, c)
    return logs, c, b


_low, _clow, _blow = _fight("SKILL_BSK_rampage", hp=6)          # 6 血 < 12% × 92 = 11.04
_lowtxt = "".join(_low)
(ok if ("攒够这点血" in _lowtxt and "受到" not in _lowtxt) else bad)(
    "  ① 血线门：6 血放狂斩 ⇒ **被拦下**（%s）· 自己那一笔没扣（血 %d）"
    % ([x for x in _low if "攒够" in x] or _low[-1:], int(_clow.get("hp") or 0)))
_hi, _chi, _bhi = _fight("SKILL_BSK_rampage", hp=5000)
(ok if ("攒够这点血" not in "".join(_hi)) and any("见了血" in x for x in _hi) else bad)(
    "  ② 付得起 ⇒ 照放（出「自己先见了血」那一行）　%s" % [x for x in _hi if "见了血" in x])

_b26 = fresh("cls_berserker", mid=DOG, hp=5000)
_b26._ensure_battle_started([])
_c26 = _b26.focus()
_sub1, _e1, _w1 = _b26.human_act("skill", "SKILL_BSK_immolate", _c26)   # ★ 取真回执（别再 settle 一次）
_l26 = [str(x) for x in (_sub1 or [])]
_sub2, _e2, _w2 = _b26.human_act("skill", "SKILL_BSK_immolate", _c26)
_l26b = [str(x) for x in (_sub2 or [])]
_t1, _t2 = "".join(_l26), "".join(_l26b)
(ok if ("一场只出一次手" not in _t1) and ("一场只出一次手" in _t2) else bad)(
    "  ③ 每场一次：同一场第一手放得出、第二手被拦下（%s）"
    % ([str(x) for x in _l26b if "一场" in str(x)] or "没拦"))
_b26c = fresh("cls_berserker", mid=DOG, hp=5000)
_b26c._ensure_battle_started([])
_c26c = _b26c.focus()
_subc, _ec, _wc = _b26c.human_act("skill", "SKILL_BSK_immolate", _c26c)
_l26c = [str(x) for x in (_subc or [])]
(ok if "一场只出一次手" not in "".join(_l26c) else bad)(
    "  ④ 换一场 ⇒ 又放得出（每场一次不是「一辈子一次」）")

_saved26 = CFG.optional_hook("skill_gate_fn")
CFG.set_hook("skill_gate_fn", None)
try:
    _z1, _zc1, _ = _fight("SKILL_BSK_rampage", hp=6)
    _zb = fresh("cls_berserker", mid=DOG, hp=5000)
    _zb._ensure_battle_started([])
    _zc = _zb.focus()
    _z2 = []
    for _ in range(2):
        _subz, _ez, _wz = _zb.human_act("skill", "SKILL_BSK_immolate", _zc)
        _z2.extend(str(x) for x in (_subz or []))
    (ok if ("攒够这点血" not in "".join(_z1) and "一场只出一次手" not in "".join(_z2)) else bad)(
        "  ⑤ 撤改（不挂 E6）⇒ 两条门都不存在（6 血照放 · 焚身同场照放第二次）—— 与接线前逐字相同")
finally:
    CFG.set_hook("skill_gate_fn", _saved26)

print()
print("── ★ fix-k-critline：暴击那一行（引擎 `crit` 事件 → texts 槽位 `COMBAT_CRIT`）")
#  改前：`COMBAT_CRIT` 槽位**全仓零读端**。引擎 `extends/ext_combat/battle/actions.py` 真在掷 ——
#    `is_crit = random.random() < st["crit"]`（命中后再掷 30% 追加一次「幸运一击 ×1.3」⇒
#    1.5 × 1.3 = 1.95 倍，与试玩实测那 1.5~1.9 倍跳变对得上），可玩家屏上只有裸伤害行：
#    刺客整轮看不到「暴击」两个字。而 `effect_triggers.fire` 只跑**主体 actor 自己**声明的触发器
#    ⇒ 读端只能挂在 `combat.player_actor` → `MECH.player_triggers()` 的 `crit` 那一格上。
import re as _re                                                            # noqa: E402
from unittest import mock as _mock                                          # noqa: E402

_SLOT_CRIT = "COMBAT_CRIT"
_ACT_CRIT = "aeth_crit_line"
#: 槽位里**最长的那一段固定字** —— 判「这一行是不是暴击行」用现算出来的它（文案一改，判据跟着动），
#: 探针里不另写一份中文镜像。
_MARK_CRIT = max((p for p in _re.split(r"\{\w+\}", CA.T(_SLOT_CRIT)) if p.strip()), key=len)
#: 引擎那一侧这一刻的两个数（刻 / 伤害）—— 只有引擎知道；读端读的是 `battle._fire_ctx`，
#: 这里换成读**同一个口**旁听一手（不改任何行为），拿它当逐字锚点的另一半。
_LIVE_CRIT: dict = {}
_orig_crit = EF.ACTION_HANDLERS.get(_ACT_CRIT)


def _crit_watch(battle, caster, target, params, logs):
    """旁听那一手：记下引擎 ctx 里的刻与伤害，其余照旧交给真读端。"""
    ctx = getattr(battle, "_fire_ctx", None) or {}
    _LIVE_CRIT.clear()
    _LIVE_CRIT.update({"t": int(round(float(getattr(battle, "_now", 0) or 0))),
                       "dmg": int(ctx.get("dmg") or 0)})
    return _orig_crit(battle, caster, target, params, logs)


def _crit_hand(roll, mounted=True, seed=20260927, cls="cls_assassin", lv=10,
               sid="SKILL_SHD_blade", name="试"):
    """钉死随机源跑**你这一手**（`advance` 那一段照旧自由跑 —— 只钉你出手这一下）。

    ★ 两处各钉一枚：`roll` 钉**决策**（暴击 / 幸运一击 / 闪避都走 `random.random()`）；
      `seed` 钉**波动**（引擎公式那支 `variance=0.15` 走 `random.uniform()`，用的是同一个
      Random 实例 —— 只 patch `random.random` 钉不住它，同一个 fixture 的数会一次一个样）。
    """
    random.seed(seed)
    _bb = CMB.build({"cls": cls, "level": lv, "uid": "u_crit", "name": name, "hp": 300},
                    [DOG], MON, party=1)
    _ll = []
    SCH.advance(_bb, _ll)
    _cc = _bb.focus()
    if not mounted:
        _cc["triggers"] = {}                 # 撤改臂：拿掉挂载面 ⇒ 那一行该一个字都不出
    with _mock.patch.object(ACT.random, "random", return_value=roll):
        _sub, _e, _w = _bb.human_act("skill", sid, _cc)
    return _bb, _cc, [str(x) for x in (_sub or [])]


def _crit_lines(_logs):
    """日志里那几行暴击行（按槽位现算出来的那段固定字认）。"""
    return [x for x in _logs if _MARK_CRIT in x]


#  ── 形状：挂载面与动词**两半都得在**（挂了没人注册 = 引擎静默跳过；注册了没人挂 = 死码）
_mnt = [a.get("action") for a in (MECH.player_triggers().get("crit") or []) if isinstance(a, dict)]
(ok if _mnt == [_ACT_CRIT] and not EF.missing_actions(_mnt) else bad)(
    "  · ★ 挂载面与动词两半都在：`player_triggers()[crit]` = %s ｜ `EF.missing_actions` = %s"
    % (_mnt, EF.missing_actions(_mnt) or "空"))

#  ── ① 正向：钉死随机源（必暴击）⇒ 那一行真出，且**逐字** = 槽位 + 这一手真值
_sd_c = _no_dodge()                          # 收口的是 fixture：闪避那枚硬币不参与这一档
EF.ACTION_HANDLERS[_ACT_CRIT] = _crit_watch
try:
    _b1, _c1, _l1 = _crit_hand(0.0)
finally:
    EF.ACTION_HANDLERS[_ACT_CRIT] = _orig_crit
    _restore_dodge(_sd_c)
_bh1 = [int(x.split("受到 ")[1].split(" 点伤害")[0]) for x in _l1 if "受到 " in x and "点伤害" in x]
_want1 = CA.T(_SLOT_CRIT, t=_LIVE_CRIT.get("t"), who="试",
              act=" · %s" % SKD["SKILL_SHD_blade"]["name"],
              tgt=" · %s" % MON[DOG]["name"], dmg=_LIVE_CRIT.get("dmg"))
(ok if _crit_lines(_l1) == [_want1] and _bh1 else bad)(
    "  · ① 必暴击那一手（随机源钉成 0.0）⇒ 回话里**恰好一行**暴击行、逐字 = 槽位 + 引擎给的真值：\n"
    "        %s\n        （同一句现算：%s ｜ 这一手真落地 %s 点）"
    % (_crit_lines(_l1) or "没出", _want1, _bh1 or "没打上"))

#  ── ② 反证：**不暴击**那一手（同一 fixture · 随机源钉成 0.99）⇒ 这一行一个字都不许出
_b2, _c2, _l2 = _crit_hand(0.99)
_bh2 = [int(x.split("受到 ")[1].split(" 点伤害")[0]) for x in _l2 if "受到 " in x and "点伤害" in x]
(ok if not _crit_lines(_l2) and _bh2 else bad)(
    "  · ② 反证（不暴击）：随机源钉成 0.99 ⇒ 这一手照打（真落地 %s 点）**但没有**那一行"
    % (_bh2 or "没打上"))

#  ── ③ 反证：拿掉挂载面（触发器清空）⇒ 即使钉了必暴击，这一行也一个字都不出
#       （证明那一行来自**内容侧的挂载面**，不是引擎自己渲染的）
_b3, _c3, _l3 = _crit_hand(0.0, mounted=False)
(ok if not _crit_lines(_l3) else bad)(
    "  · ③ 反证（撤改）：触发器清空 + 同一手钉必暴击 ⇒ 一个字都不出（%s）"
    % (_crit_lines(_l3) or "空"))

print()
print()
print("── ⑮ 引擎改动面（硬指标）")
#  ★ fxmech（2026-09-26）起：本批**动了引擎**（B4-4 的两段耗时接线 + 一条新的可选否决口
#    `skill_gate_fn`）—— 判据从「引擎零改动」改成**钉住改动面**：改动只许落在声明的那些文件里
#    （声明在下一条 `_want_touched` 那里；本批 = 跨手状态三条），
#    且**引擎自带的门禁要全过**（那一半在本包门禁之外，由引擎仓自己的 `tests/` 跑）。
# ★ 0 号：引擎仓**工作区干净**（本批的引擎改动已提交 —— 不留半截在盘上）
_git = subprocess.run(["git", "status", "--porcelain"], cwd=ENGINE, capture_output=True, text=True)
_dirty = [ln for ln in (_git.stdout or "").splitlines() if ln.strip()]
(ok if not _dirty else bad)("★ 引擎仓工作区干净（未提交的 %d 条：%s）"
                            % (len(_dirty), [x.strip() for x in _dirty[:3]]))
# ★ 1 号：**本批**（自 `_ENGINE_BASE` 起）的落点 == 声明的这几份代码文件（其余只许 docs/ 落账）
#   ★ 2026-09-27（跨手状态三条那一批）**换锚不换强度**：原先只看 `git log -1`（HEAD 那一笔），
#     而本批在引擎仓可以落好几笔（代码 → docs 落账 → 上一笔判据的 fixture 修）⇒ HEAD 是
#     docs-only 提交时那写法会算出「代码 无」而**假红**。改成**自基准提交起 diff**
#     （`<base>..HEAD` 的并集 —— 与「本批落了几笔」无关，且扫的面更宽）。
#     ★ 换批时改两处：`_ENGINE_BASE`（本批**开工前**引擎的 HEAD）与 `_want_touched`。
#   ★ P-11（2026-09-27）**换批**：本批的引擎改动 = 内置守卫拦截句读口那三份
#     （`config.py` 新增 `guard_text_fn` 读口 · `host/runtime.py` 新增 `GUARD_KEYS` +
#     `Host._guard_text` 三态 · `tests/test_host_contract.py` 那 16 条判据）——
#     本包 `content/guard_text.py` 直接 `import GUARD_KEYS` ⇒ 换批必须跟着前移基准，
#     否则这两个探针会把「本批的引擎改动」误判成越界。**强度不变**（代码落点多一个就红）。
#   ★ 2026-09-27（**引擎侧 cue 解耦 B0–B5 那一批落到 main**）**换批**：本批引擎仓的落点 =
#     表现事件（cue）形状 + 60 个点位从「引擎内联措辞」搬进 cue（`battle/*.py` · `gauge/*.py` ·
#     `saintess_engine/cues.py` · `text/template.py` 删两个取表 helper）· 配套门禁与冻结尺子
#     （`tools/_cue_freeze.py`）· 标签机制三笔（`tags.py` / `traits.py` / `state_effects.py` /
#     `actors.py` / `battle.py` 的状态容器与注册表收口）。基准 = 那批开工前引擎的 HEAD。
#     ⇒ 声明面变成 **34 份代码文件**（多一个就红 —— 强度不变，只是这一批面大）。
_ENGINE_BASE = "8f85f7d"   # 换批只扩声明面（47 份），基准仍是共同起点
_want_touched = sorted([
    "README.md",
    "examples/host-skeleton/main.py",
    "examples/minimal-game/content/apply.py",
    "examples/minimal-game/content/bridge.py",
    "examples/minimal-game/content/cues.py",
    "examples/minimal-game/content/data/rules.py",
    "examples/minimal-game/content/texts.py",
    "examples/minimal-game/tests/test_smoke.py",
    "extends/ext_combat/battle/actions.py",
    "extends/ext_combat/battle/actors.py",
    "extends/ext_combat/battle/attributes.py",
    "extends/ext_combat/battle/battle.py",
    "extends/ext_combat/battle/cues.py",
    "extends/ext_combat/battle/effects.py",
    "extends/ext_combat/battle/game_config.py",
    "extends/ext_combat/battle/landing.py",
    "extends/ext_combat/battle/schedule.py",
    "extends/ext_combat/battle/serialize.py",
    "extends/ext_combat/battle/state_effects.py",
    "extends/ext_combat/battle/tags.py",
    "extends/ext_combat/battle/traits.py",
    "extends/ext_combat/gauge/__init__.py",
    "extends/ext_combat/gauge/actions.py",
    "saintess_engine/config.py",
    "saintess_engine/cues.py",
    "saintess_engine/domains.py",
    "saintess_engine/host/runtime.py",
    "saintess_engine/text/__init__.py",
    "saintess_engine/text/template.py",
    "tests/_cue_text_fixture.py",
    "tests/test_attrs_write_port.py",
    "tests/test_battle_text_inject.py",
    "tests/test_builtin_false_warn.py",
    "tests/test_cross_hand_state.py",
    "tests/test_cue_coverage.py",
    "tests/test_cues_shape.py",
    "tests/test_dot_cur_hp_shape.py",
    "tests/test_editor_wiki.py",
    "tests/test_engine_neutral_fallback.py",
    "tests/test_gauge_actions_frozen.py",
    "tests/test_segment_declaration.py",
    "tests/test_state_container.py",
    "tests/test_state_container_r2.py",
    "tests/test_tags.py",
    "tools/_cue_coverage.py",
    "tools/_cue_freeze.py",
    "tools/check_wiki_refs.py",])
_committed = {p for p in subprocess.run(
    ["git", "diff", "--name-only", "%s..HEAD" % _ENGINE_BASE], cwd=ENGINE,
    capture_output=True, text=True).stdout.split() if p}
_code = sorted(p for p in _committed if not p.startswith("docs/"))
_docs = sorted(p for p in _committed if p.startswith("docs/"))
(ok if _code == _want_touched else bad)(
    "★ 本批（自 %s 起）的代码落点 == 声明的那几份（代码 %s ｜ docs 落账 %d 份）"
    % (_ENGINE_BASE, "、".join(_code) or "无", len(_docs)))
_hooks_decl = {"segment_plan_fn", "skill_gate_fn"}
from saintess_engine import config as _CFG15
_missing_hook = sorted(h for h in _hooks_decl if _CFG15.optional_hook(h) is None and h == "segment_plan_fn")
(ok if not _missing_hook else bad)(
    "★ 本批用到的注入面都在引擎 `_HOOKS` 里声明过（%s）" % ("、".join(sorted(_hooks_decl),)))

print()
print("结果：%s" % ("全绿 ✓" if not fails else "有红 ✗（%d）" % len(fails)))
sys.exit(1 if fails else 0)
