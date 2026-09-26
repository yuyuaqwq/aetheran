# -*- coding: utf-8 -*-
"""探针：职业资源渠道 + 骑士格挡（B4-1 那批写了声明，这批补消费端）。

判据分八档（全部现算，不写镜像表）
------------------------------------------------------------------
① 形状档：`content/rules/resources.json` 读得到 · 每条资源 max>0 · 主人职业在 `classes` 域里 ·
   渠道名都在 `channels` 里登记过 · 一个职业只挂一条资源
② 跨域对账：域里每条技能的 `res_gain` / `res_cost` 码都声明过（现算）· 反证「塞个没声明的码 ⇒ 装配期抛」
③ 骑士守誓值：开战摆 0 · 受击 +6 · 普攻命中 +3 / 技能命中 +5 · 盾墙 +12（技能自己声明那条）·
   守誓斩扣 25 · **不够时放不出来**（引擎的资源预检 —— 这就是「先攒后放」的闸门）
④ 法师印记：星屑 +1 / 焰痕 +2 · 引燃要 ≥1 层、垂星要 ≥3 层才放得出 · 放完**清空**
⑤ 游侠准星（每次出手 +1 · 封顶 6）· 修女祷言（一次受伤 > 上限 15% ⇒ +1 · 每 300 刻自然回 1 · 倒下清空）
⑥ 格挡（骑士被动「格挡回誓」）：掷中 ⇒ 这次承伤按真源 F10 打折 + 回守誓（账本 +12 + 被动 +8）·
   没掷中 ⇒ 不写字段 · 等级没到 16 ⇒ 不掷
⑦ 反证（不装配 = 与接线前一字不差）：资源表读不到 ⇒ 一个字段都不写
⑧ 引擎零改动（硬指标）

口径说明（为什么「定向」和「端到端」都要）：引擎的事件 ctx（`{"actor","target","info","dmg"}`）
**不会**并进动作的 `params`，读口是 `battle._fire_ctx`；而端到端那一路中间还会夹进对手的出手
（会额外加资源）⇒ 逐值复算用定向（ctx 形状照引擎调用点逐字摆），「真能跑通」用端到端。

用法（Python 用 3.12；3.11 会假红）
    GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_resources.py
"""
from __future__ import annotations

import os
import random
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, ENGINE)
sys.path.insert(0, REPO)

from saintess_engine.package import load_stack                    # noqa: E402

st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"),
                                                          "Temp", "ast_probe_res.db"),
                                   "clock": time.time})
st.install()

CMB = st.optional_submodule("combat")
RES = st.optional_submodule("resources")
MECH = st.optional_submodule("mech")
SK = st.optional_submodule("skills_lookup")
MON = st.domain("monsters")
CLS = st.domain("classes")
from ext_combat.battle import landing as LD                        # noqa: E402
from ext_combat.battle import schedule as SCH                      # noqa: E402
from ext_combat.battle import stats as ST                          # noqa: E402
from ext_combat.battle.effect_triggers import fire as _fire         # noqa: E402
from ext_combat.battle.actions import _skill_usable as _usable, _spend_skill_cost as _spend   # noqa: E402

MID = "ms_field_mouse"
SEED = 1

fails = []


def ok(m):
    print("  ✓ " + m)


def bad(m):
    print("  ✗ " + m)
    fails.append(m)


def chk(label, cond, extra=""):
    if cond:
        ok(label + ("  —— " + extra if extra else ""))
    else:
        bad(label + ("  —— " + extra if extra else ""))


def build(cls, lv, mid=MID, uid="u_res"):
    return CMB.build({"cls": cls, "level": lv, "name": "探", "uid": uid}, [mid], MON, uid=uid)


def focus(b):
    b._ensure_battle_started([])                          # 引擎自己的「整场一次」闸（battle_start 在此）
    return b.focus()


def stacks(actor, key):
    return int((((actor.get("effects") or {}).get(key)) or {}).get("stacks") or 0)


def put(actor, key, n):
    actor.setdefault("effects", {})[key] = {"stacks": n, "expire": None}


def dir_event(b, ev, *, actor, ctx_extra, logs=None):
    """定向：照引擎调用点的形状 fire 一次（ctx 形状逐字对齐那几个 `_fire(...)`）。"""
    _fire(b, ev, dict({"actor": actor}, **ctx_extra), logs if logs is not None else [])


def cast_e2e(b, sid):
    """端到端：真敲一次「技能 <名>」（先把时间推到该他出手那一刻）。"""
    SCH.advance(b, [])
    random.seed(SEED)
    c = b.focus()
    sub, _e, _w = b.human_act("skill", sid, c)
    logs = [str(x) for x in (sub or [])]
    SCH.settle_landing(b, logs, c)                       # ★ 落地那一段的日志也要收（技能名在那里面）
    return c, logs


def no_block():
    """fixture：把格挡概率临时压成 0（这一档问的是**渠道**，不是格挡；两条撞在一起会串数）。"""
    _m = MECH.of("block_oath")
    _saved_ch = _m.get("block_chance")
    _m["block_chance"] = {"value": 0.0}
    return _saved_ch


def restore_block(saved):
    if saved is None:
        MECH.of("block_oath").pop("block_chance", None)
    else:
        MECH.of("block_oath")["block_chance"] = saved


print("══ ① 形状档（resources.json）")
_res, _ch = RES.resources(), RES.channels()
chk("① 资源表读得到（%d 条资源 · %d 个渠道名）" % (len(_res), len(_ch)), bool(_res) and bool(_ch))
_bad = []
for _k, _v in _res.items():
    if not isinstance(_v.get("max"), (int, float)) or _v["max"] <= 0:
        _bad.append((_k, "max"))
    if str(_v.get("owner_class") or "") not in CLS:
        _bad.append((_k, "owner_class=%r 不在 classes 域" % _v.get("owner_class")))
    for _c in (_v.get("gain") or {}):
        if _c not in _ch:
            _bad.append((_k, "渠道 %r" % _c))
chk("① 每条资源：max>0 · 主人职业在 classes 域 · 渠道名登记过", not _bad, "%s" % (_bad or "全对"))
_by_cls = {}
for _k, _v in _res.items():
    _by_cls.setdefault(_v.get("owner_class"), []).append(_k)
chk("① 一个职业只挂一条资源（%s）" % " · ".join("%s=%s" % (c, ks) for c, ks in sorted(_by_cls.items())),
    all(len(v) == 1 for v in _by_cls.values()))

print()
print("══ ② 跨域对账（域里声明的资源码都得在表里）")
_seen = RES.check_domain()
chk("② 域里用到的资源码都有声明（%s）" % " · ".join("%s=%d 条技能" % (k, len(v)) for k, v in sorted(_seen.items())),
    set(_seen) <= set(_res))
_sk_all = SK.skills()
try:
    _sk_all["SKILL_FAKE_res"] = {"name": "探针假技", "kind": "主动", "kind_key": "active", "lv": 1,
                                 "res_gain": {"RES_NOPE": 1}}
    RES.check_domain()
    bad("② 域里塞了个没声明的资源码，装配期没抛（会静默不涨）")
except KeyError:
    ok("② 反证：域里塞个没声明的资源码 ⇒ 装配期当场抛（防「技能声明了资源、渠道没这张表」）")
finally:
    _sk_all.pop("SKILL_FAKE_res", None)

print()
print("══ ③ 骑士守誓值（受击 +6 · 普攻命中 +3 · 技能命中 +5 · 盾墙 +12 · 守誓斩 −25）")
_sb = no_block()                       # 这一档只看渠道：先把格挡推开（格挡自己那一档在 ⑥）
_b = build("cls_knight", 16)
_c = focus(_b)
chk("③ 开战把资源摆成 0 层（引擎的资源闸门才真的存在：res_cost 判据是「有该条目才须足额」）",
    stacks(_c, "RES_OATH") == 0, "⇒ %d 层" % stacks(_c, "RES_OATH"))
_mob = (_b.sides.get("enemy") or [None])[0]
put(_c, "RES_OATH", 0)
# ★ fix7-gear 顺手收口（**判据一个字没松，收的是 fixture**）：引擎 `_apply_damage` **先 roll 闪避**，
#   被闪掉的那一下**不触发 `on_taken`**（`_apply_damage` 里闪掉就 return 0 —— 引擎语义如此）。
#   原先这里只打一下 ⇒ 命中率那一枚硬币有时翻到「闪掉了」，这一条就红一次（实测：满载那一跑红过一回，
#   单独连跑 3 回又全绿 —— 是掷硬币，不是判据错）。⇒ 改成「打到真挨住那一发为止」，
#   期望值仍然是 `gain_of`（**不许放宽**：挨住的第一下必须正好等于声明的 +6）。
_took = 0
for _try in range(20):
    LD.deal_damage(_b, _mob, _c, 10, [])
    if stacks(_c, "RES_OATH"):
        _took = stacks(_c, "RES_OATH")
        break
chk("③ 受击 +%d（真源「受击（无论格挡与否）+6」· 挨住那一发：第 %d 次落上）"
    % (RES.gain_of("RES_OATH", "on_taken"), _try + 1),
    _took == RES.gain_of("RES_OATH", "on_taken")
    and stacks(_c, "RES_OATH") == RES.gain_of("RES_OATH", "on_taken"),
    "⇒ %d 层" % stacks(_c, "RES_OATH"))
put(_c, "RES_OATH", 0)
dir_event(_b, "attack_hit", actor=_c, ctx_extra={"target": _mob, "info": {"_basic": True}, "dmg": 9})
chk("③ 普攻命中 +%d（引擎 `attack_hit`）" % RES.gain_of("RES_OATH", "hit_basic"),
    stacks(_c, "RES_OATH") == RES.gain_of("RES_OATH", "hit_basic"), "⇒ %d 层" % stacks(_c, "RES_OATH"))
put(_c, "RES_OATH", 0)
dir_event(_b, "skill_hit", actor=_c, ctx_extra={"target": _mob, "info": {"_basic": False}, "dmg": 30})
chk("③ 技能命中 +%d（引擎 `skill_hit`）" % RES.gain_of("RES_OATH", "hit_skill"),
    stacks(_c, "RES_OATH") == RES.gain_of("RES_OATH", "hit_skill"), "⇒ %d 层" % stacks(_c, "RES_OATH"))
put(_c, "RES_OATH", 0)
_wall = SK.skill_info("cls_knight", "盾墙")
dir_event(_b, "act_cast", actor=_c, ctx_extra={"target": _mob, "info": _wall})
_want_wall = int((_wall.get("res_gain") or {}).get("RES_OATH") or 0)
chk("③ 盾墙 +%d（技能自己声明的 `res_gain`，走 `act_cast`）" % _want_wall,
    stacks(_c, "RES_OATH") == _want_wall, "⇒ %d 层" % stacks(_c, "RES_OATH"))
put(_c, "RES_OATH", 30)
_ok_usable = _usable(_b, _c, SK.skill_info("cls_knight", "守誓斩"), logs=None)
_spend(_c, SK.skill_info("cls_knight", "守誓斩"))                    # 引擎自己的扣费口
chk("③ 30 层时守誓斩可用（引擎资源预检过）· 扣费口扣掉 25", _ok_usable and stacks(_c, "RES_OATH") == 5,
    "⇒ %d 层" % stacks(_c, "RES_OATH"))
put(_c, "RES_OATH", 10)
chk("③ 只有 10 层时**放不出来**（这就是「先攒后放」；接渠道之前这些技能是零成本）",
    _usable(_b, _c, SK.skill_info("cls_knight", "守誓斩"), logs=None) is False)
put(_c, "RES_OATH", 40)
_c2, _lg2 = cast_e2e(_b, "SKILL_KNT_oathslash")
#: 真出招那一趟会夹进对手的出手 ⇒ 期望值 = 40 − 25（这一手）+ 受击 6 + 技能命中 5（那一下真的打到怪了）
_want_e2e = 40 - 25 + RES.gain_of("RES_OATH", "on_taken") + RES.gain_of("RES_OATH", "hit_skill")
chk("③ 端到端真放一次守誓斩（真出招 · 真扣费 · 数字逐值对得上）",
    stacks(_c2, "RES_OATH") == _want_e2e,
    "⇒ %d 层（期望 %d = 40−25+%d+%d）· 日志 %d 行"
    % (stacks(_c2, "RES_OATH"), _want_e2e, RES.gain_of("RES_OATH", "on_taken"),
       RES.gain_of("RES_OATH", "hit_skill"), len(_lg2)))
restore_block(_sb)

print()
print("══ ④ 法师印记（星屑 +1 · 焰痕 +2 · 引燃/垂星：攒够才放 + 放完清空）")
_b4 = build("cls_mage", 16, uid="u_res4")
_c4 = focus(_b4)
_mob4 = (_b4.sides.get("enemy") or [None])[0]
put(_c4, "RES_MARK", 0)
dir_event(_b4, "act_cast", actor=_c4, ctx_extra={"target": _mob4, "info": SK.skill_info("cls_mage", "星屑")})
chk("④ 星屑 +1", stacks(_c4, "RES_MARK") == 1, "⇒ %d 层" % stacks(_c4, "RES_MARK"))
dir_event(_b4, "act_cast", actor=_c4, ctx_extra={"target": _mob4, "info": SK.skill_info("cls_mage", "焰痕")})
chk("④ 焰痕 +2", stacks(_c4, "RES_MARK") == 3, "⇒ %d 层" % stacks(_c4, "RES_MARK"))
put(_c4, "RES_MARK", 0)
chk("④ 0 层时引燃放不出来（`res_cost: 1` ⇒ 先攒后放）",
    _usable(_b4, _c4, SK.skill_info("cls_mage", "引燃"), logs=None) is False)
chk("④ 0 层时垂星放不出来（`res_cost: 3`）",
    _usable(_b4, _c4, SK.skill_info("cls_mage", "垂星"), logs=None) is False)
put(_c4, "RES_MARK", 2)
chk("④ 2 层时垂星仍放不出来（要 ≥3）",
    _usable(_b4, _c4, SK.skill_info("cls_mage", "垂星"), logs=None) is False)
put(_c4, "RES_MARK", 6)
_spend(_c4, SK.skill_info("cls_mage", "引燃"))
chk("④ 引燃放完**清空**印记（引擎 `consume_all`；接渠道前 `res_cost: 99` 是死占位）",
    stacks(_c4, "RES_MARK") == 0, "⇒ %d 层" % stacks(_c4, "RES_MARK"))
put(_c4, "RES_MARK", 5)
_c4b, _lg4b = cast_e2e(_b4, "SKILL_MAG_ignite")
chk("④ 端到端真放一次引燃（真出招 · 5 层被一次清空 · 有伤害行）",
    stacks(_c4b, "RES_MARK") == 0 and any("受到" in x for x in _lg4b),
    "⇒ %d 层 · 日志 %d 行" % (stacks(_c4b, "RES_MARK"), len(_lg4b)))

print()
print("══ ⑤ 游侠准星（每次出手 +1 · 封顶 6）· 修女祷言（一次受伤 > 上限 15% ⇒ +1 · 每 300 刻回 1 · 倒下清空）")
_b5 = build("cls_ranger", 16, uid="u_res5")
_c5 = focus(_b5)
_mob5 = (_b5.sides.get("enemy") or [None])[0]
put(_c5, "RES_AIM", 0)
dir_event(_b5, "act_cast", actor=_c5, ctx_extra={"target": _mob5, "info": SK.skill_info("cls_ranger", "短弓")})
chk("⑤ 出手一次 +1 准星（真源「距离 3 每次行动 +1」那一档）", stacks(_c5, "RES_AIM") == 1,
    "⇒ %d 层" % stacks(_c5, "RES_AIM"))
put(_c5, "RES_AIM", RES.max_of("RES_AIM") - 1)
dir_event(_b5, "act_cast", actor=_c5, ctx_extra={"target": _mob5, "info": SK.skill_info("cls_ranger", "短弓")})
dir_event(_b5, "act_cast", actor=_c5, ctx_extra={"target": _mob5, "info": SK.skill_info("cls_ranger", "短弓")})
chk("⑤ 准星封顶 %d（夹在 0..max）" % RES.max_of("RES_AIM"), stacks(_c5, "RES_AIM") == RES.max_of("RES_AIM"),
    "⇒ %d 层" % stacks(_c5, "RES_AIM"))
_b6 = build("cls_priest", 16, uid="u_res6")
_c6 = focus(_b6)
_mob6 = (_b6.sides.get("enemy") or [None])[0]
_mx6 = int(ST.actor_max_hp(_b6, _c6) or 0)
put(_c6, "RES_LITANY", 0)
LD.deal_damage(_b6, _mob6, _c6, int(_mx6 * 0.05), [])
chk("⑤ 小伤（承伤后 5% 上限）不涨祷言（真源：一次受伤**超过** 15% 才算）", stacks(_c6, "RES_LITANY") == 0,
    "⇒ %d 层" % stacks(_c6, "RES_LITANY"))
LD.deal_damage(_b6, _mob6, _c6, int(_mx6 * 0.40), [])
chk("⑤ 重击（承伤后 > 15% 上限）+1 祷言", stacks(_c6, "RES_LITANY") == 1,
    "⇒ %d 层" % stacks(_c6, "RES_LITANY"))
#: 自然回的书签：`<= 0` = 「还没初始化」（只登记下一跳，不涨）⇒ fixture 要写**当前刻**
SCH._advance_time(_b6, 1.0, [])                        # 先把时钟推过 0（书签 0 会被当「没初始化」）
_c6["_res_at"] = _b6._now
SCH._advance_time(_b6, 1.0, [])
chk("⑤ 自然回：每 %s 刻 +%s" % ((RES.of("RES_LITANY").get("regen") or {}).get("every"),
                                 (RES.of("RES_LITANY").get("regen") or {}).get("amount")),
    stacks(_c6, "RES_LITANY") == 2, "⇒ %d 层" % stacks(_c6, "RES_LITANY"))
_c6["hp"] = 1
LD.deal_damage(_b6, _mob6, _c6, 9999, [])
chk("⑤ 倒下 ⇒ 资源清空（真源「队友倒下清空」按含自己落；挂在 `on_death` 上 —— 濒死那一下 `on_taken` 不触发）",
    stacks(_c6, "RES_LITANY") == 0, "⇒ %d 层" % stacks(_c6, "RES_LITANY"))

print()
print("══ ⑥ 格挡（骑士被动「格挡回誓」：真源 F10 减免 + 回誓）")
from content import apply as _AP                                   # noqa: E402

_b7 = build("cls_knight", 16, uid="u_res7")
_c7 = focus(_b7)
_blk = float(ST.actor_stats(_b7, _c7).get("block", 0) or 0)
_mit = float(_AP._table().eval("F10_block_mit", {"block": _blk}))
_bonus = int((MECH.of("block_oath").get("oath_bonus") or {}).get("value") or 0)
_acct = int(RES.gain_of("RES_OATH", "on_block"))
put(_c7, "RES_OATH", 0)
random.seed(SEED)
_hp0 = int(_c7.get("hp") or 0)
_lg7 = []
LD.deal_damage(_b7, None, _c7, 100, _lg7)                          # source=None ⇒ 不掺等级压制
_d7 = _hp0 - int(_c7.get("hp") or 0)
_luck = any("举盾挡下" in x for x in _lg7)
_want7 = max(1, int(100 * (1 - _mit)))
chk("⑥ 骑士 16 级 block=%g ⇒ F10 减免 %.4f（求值 formula_table，不重写公式）" % (_blk, _mit),
    0 < _mit < 0.6, "⇒ %.4f" % _mit)
if _luck:
    chk("⑥ 掷中 ⇒ 承伤按 F10 打折（100 点应剩 %d）" % _want7, _d7 == _want7, "实测掉 %d 点" % _d7)
    chk("⑥ 掷中 ⇒ 回守誓 %d（账本 +%d + 本被动 +%d）+ 那一下的受击 +%d"
        % (_acct + _bonus + RES.gain_of("RES_OATH", "on_taken"), _acct, _bonus,
           RES.gain_of("RES_OATH", "on_taken")),
        stacks(_c7, "RES_OATH") == _acct + _bonus + RES.gain_of("RES_OATH", "on_taken"),
        "⇒ %d 层" % stacks(_c7, "RES_OATH"))
else:
    chk("⑥ 这一种子没掷中（概率 %s）—— 掉血 = 不打折的基线，且一个字都不写"
        % (MECH.of("block_oath").get("block_chance") or {}).get("value"),
        _d7 == 100 and stacks(_c7, "RES_OATH") == RES.gain_of("RES_OATH", "on_taken"),
        "掉 %d 点 · 层 %d" % (_d7, stacks(_c7, "RES_OATH")))
_b8 = build("cls_knight", 15, uid="u_res8")
_c8 = focus(_b8)
put(_c8, "RES_OATH", 0)
_lg8 = []
for _i in range(12):
    LD.deal_damage(_b8, None, _c8, 10, _lg8)
chk("⑥ 等级没到 16 ⇒ 一次都不格挡（12 次全无「举盾挡下」）", not any("举盾挡下" in x for x in _lg8))

print()
print("══ ⑦ 反证：不装配（资源表读不到）⇒ 一个字段都不写")
_saved = RES._CACHE.pop("t", None)
try:
    RES._CACHE["t"] = {}
    _b9 = build("cls_knight", 16, uid="u_res9")
    _c9 = focus(_b9)
    put(_c9, "RES_OATH", 0)
    _lg9 = []
    LD.deal_damage(_b9, None, _c9, 100, _lg9)
    chk("⑦ 表读不到 ⇒ 挨打不涨资源、也不格挡（与接线前一字不差）",
        stacks(_c9, "RES_OATH") == 0 and not any("举盾挡下" in x for x in _lg9),
        "层=%d · 格挡行=%d" % (stacks(_c9, "RES_OATH"), len([x for x in _lg9 if "举盾挡下" in x])))
finally:
    if _saved is None:
        RES._CACHE.pop("t", None)
    else:
        RES._CACHE["t"] = _saved

print()
print("══ ⑧ 引擎零改动（硬指标）")
_out = subprocess.run(["git", "-C", ENGINE, "status", "--porcelain"],
                      capture_output=True, text=True, encoding="utf-8").stdout.strip()
chk("⑧ 引擎仓 `git status` 为空（本批只在内容侧落）", _out == "", _out or "干净")

print()
print("结果：%s" % ("全绿 ✓" if not fails else "有红 ✗（%d 条）" % len(fails)))
sys.exit(0 if not fails else 1)
