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
   ★ `g5-flake`：前两态原先**只跑「掷中」那一半**（`if _luck` 恒真 ⇒ `else` 支从没执行过）——
     现在两态各钉一遍，且都不看手气（掷中 = 把骰子钉成 0.10 · 没掷中 = `block_chance` 压 0）
⑦ 反证（不装配 = 与接线前一字不差）：资源表读不到 ⇒ 一个字段都不写
⑧ 引擎零改动（硬指标）

口径说明（为什么「定向」和「端到端」都要）：引擎的事件 ctx（`{"actor","target","info","dmg"}`）
**不会**并进动作的 `params`，读口是 `battle._fire_ctx`；而端到端那一路中间还会夹进对手的出手
（会额外加资源）⇒ 逐值复算用定向（ctx 形状照引擎调用点逐字摆），「真能跑通」用端到端。

承伤 fixture 口径（`g5-flake` 补）：挨打那几档（③ 受击 · ⑤ 祷言 · ⑦ 反证）量的是**渠道**，
不是命中率。引擎承伤链上有两枚硬币 —— `landing._roll_dodge`（闪避，读口 `dodge_cap()`）
与内容侧 `mech.aeth_block_roll`（格挡）。**被闪掉的那一下 `deal_damage` 直接 `return 0`**
⇒ `on_taken` 根本不触发 ⇒ 拿它当 fixture 的判据 = 掷硬币。故 **③ 起把随机口都收掉**
（`no_block()` 只在 ③；`no_dodge()` 一直挂到 ⑦ 之后才还原），判据本体一个字没松 ——
收的是 fixture，不是判据。（⑦ 那一条另有 fail-closed 兜着：资源表读不到时
`mech.aeth_block_roll` 第一行就 `return`，连骰子都不掷。）

红率实测（本波两把独立尺子）：把 ③ 那处还原成「只打一下」（= `fix7-gear` 之前那一版）
⇒ **200 跑 5 红（2.5%）**，红的整行**恒为**「✗ ③ 受击 +6（真源「受击（无论格挡与否）+6」）
—— ⇒ 0 层」（与骑士 16 级 `dodge=0.031` 那枚硬币对得上）；收口之后连跑 **180 次 0 红**。

★ 同类可疑写法（本波只扫不改，清单留给后续批）：口径 = 「把**会掷骰的真实路径**当
fixture/判据，又没有确定性把手」。**不是所有掷骰都得收** —— 判据不靠单次命中就不算靠运气。
按**后果**分三档（本波逐支实测后重分类，别再把三者混成"抖动"）：

  〔真·抖动〕会**真的红**、随机复现 —— 只有 ③（本波已治）。判据：跑 N 跑数红率。
  〔已兜住〕概率被压到≈0，**红不了**，但判据仍骑在硬币上 —— `probe_mech.py:557/:569` 两处
    `while … < 20`「重试到落槌为止」。实测（本波跑 20 遍）：**0/20 红**，而硬币**翻过一次**
    （19 跑「第 1 次才挨到」· 1 跑「第 2 次才挨到」）⇒ 要连翻 20 次才红（约 0.032²⁰）。
    属**风格收口**（收口走声明面 `dodge.cap`，别裸写 `actor["dodge"]=0` —— 挨打方是玩家、
    面板是聚合出来的），**不是缺陷**。
  〔确定但**脆**〕判据不靠硬币、但**骑在掷骰次序上** —— 别处多/少一次 roll 就红成"像回归"。
    `probe_elements.py:54` 挑种子即此例：实测把 `SEED` 换 4242 ⇒ **真红 2 条**（⑦ 两条，对照臂
    被浅滩水鬼那 4% 闪避吃掉 ⇒ 基线 0 ⇒ 比值判据塌成 `0 × 1.25 == 0`）。**它不假绿、是会叫的脆**。
    ★ 本波已治：挨打方 dodge 归零 ⇒ 同一判据 `SEED=1/4242/7/999` **四种都绿**（见该文件 `_enemy` 注）。
  〔真·假绿〕判据只跑一半/前提被挑出来 —— 本文件 **⑥ 的 else 支从没被执行过**（`if _luck` 那一半
    恒真 ⇒ 「没掷中 ⇒ 一个字都不写」那半判据只存在纸面上）。这个**不会叫**，比抖动更该治。
 ④~⑦ 全骑在 ④ 的 `random.seed(SEED)` 上（③⑤⑦ 本波已换确定性闸）—— 属「脆」那一档的温床。
已核实**不用**收（登记备查）：`probe_cmds.py` 一跑掷 43 枚硬币、且**实测有一跑真闪了 2 下仍全绿**
（它的判据不靠单次命中）；`probe_mana.py` 的回复是**时钟驱动**、与硬币无关。

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
from ext_combat.battle import formulas as F                        # noqa: E402
from ext_combat.battle.effect_triggers import fire as _fire         # noqa: E402
from ext_combat.battle.actions import _skill_usable as _usable, _spend_skill_cost as _spend   # noqa: E402
from saintess_engine import config as CFG                          # noqa: E402

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


def no_dodge():
    """fixture：把**闪避上限**临时压成 0 —— 挨打那一档要问渠道，不能问命中率。

    为什么必须收（`g5-flake` 实测）：引擎承伤链上有一枚硬币 ——
    `landing._roll_dodge` 里 `if random.random() < dodge`（`dodge` 是聚合面板值，
    上限走**声明口** `formulas.dodge_cap()`）。被闪掉的那一下 `deal_damage`
    **直接 `return 0`**，压根走不到 `_apply_damage` ⇒ `on_taken` 根本不触发
    （引擎语义如此，是对的：「没碰到」当然不算受击）。于是**拿它当 fixture 的判据
    = 掷硬币**：骑士 16 级 `dodge=0.031` ⇒ 约每 32 跑红一次。

    收口走**引擎自己的声明面**（不是 monkeypatch 引擎）：`FORMULA_SKELETON["dodge"]["cap"]`
    —— 读口就是 `dodge_cap()`。压成 0 之后 `min(dodge, 0) = 0` ⇒ `dodge <= 0`
    ⇒ 引擎**连 roll 都不发生**（不是「希望它别闪」）。返回挂载前的 hook 值供还原。
    """
    _saved = CFG.optional_hook("formula_skeleton_fn")   # 「不配 = 合法」的读口（不问 strict）
    _sk = dict(F._skeleton() or {})                # 当前生效的骨架表（照抄，只动 dodge.cap）
    _sk["dodge"] = dict(_sk.get("dodge") or {}, cap=0.0)
    CFG.mount(formula_skeleton_fn=lambda: _sk)
    return _saved


def restore_dodge(saved):
    CFG.set_hook("formula_skeleton_fn", saved)


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
_sd = no_dodge()                       # 同理把闪避那枚硬币也收掉（下一段注释：为什么必须收）
chk("③ fixture 生效：闪避上限已被压成 0（挨打不再靠命中率——弹硬币就不算 fixture）",
    F.dodge_cap() == 0.0, "⇒ dodge_cap()=%s" % F.dodge_cap())
_b = build("cls_knight", 16)
_c = focus(_b)
chk("③ 开战把资源摆成 0 层（引擎的资源闸门才真的存在：res_cost 判据是「有该条目才须足额」）",
    stacks(_c, "RES_OATH") == 0, "⇒ %d 层" % stacks(_c, "RES_OATH"))
_mob = (_b.sides.get("enemy") or [None])[0]
put(_c, "RES_OATH", 0)
# ★ g5-flake 收口（**判据本体一个字没松，收的是 fixture**）：这根渠道走的是**挨打**，
#   而引擎承伤链上先有一枚硬币 —— `landing._roll_dodge`（`random.random() < dodge`）；
#   被闪掉的那一下 `deal_damage` **直接 `return 0`**，走不到 `on_taken`。骑士 16 级
#   `dodge=0.031` ⇒ 单跑这里约每 32 次红一次（实测：单跑连跑 160 次，红 6 次 —
#   红的整行就是「③ 受击 +6（真源「受击（无论格挡与否）+6」）  —— ⇒ 0 层」）。
#   前一轮曾用「打到挨住为止」的重试遮过去 —— 重试**仍是运气**（0.031^20 只是小，
#   不是 0），且真出现连续闪避时判据会**悄悄改成量第 20 次的结果**。
#   ⇒ 现在改成**确定性**收口：`no_dodge()` 把闪避上限压成 0（`min(dodge,0)=0`
#   ⇒ 连 roll 都不发生）。这样**闪避要是回来了，这条当场红** —— 比重试更强。
#   期望值仍是声明的 `on_taken` 渠道值（**不许放宽**）。
LD.deal_damage(_b, _mob, _c, 10, [])
chk("③ 受击 +%d（真源「受击（无论格挡与否）+6」）" % RES.gain_of("RES_OATH", "on_taken"),
    stacks(_c, "RES_OATH") == RES.gain_of("RES_OATH", "on_taken"), "⇒ %d 层" % stacks(_c, "RES_OATH"))
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
#: ★ fxmech（2026-09-26）：真出招那一趟会夹进对手的出手 —— **夹进几下**由时间模型说了算
#:   （B4-4 接线后技能用自己的两段：守誓斩 50+50，落地时刻与旧口径不同 ⇒ 窗口里对手打几下会变）。
#:   期望值改成**按这一趟真发生的事件数**现算（判据本体没松：还是「层数 == 40 − 25 + 受击×6 + 命中×5」
#:   那一本账，只是不再把「对手恰好打一下」钉成前提）。
_n_taken = sum(1 for _x in _lg2 if ("受到" in str(_x) and "试" in str(_x)))
_n_hit = sum(1 for _x in _lg2 if ("受到" in str(_x) and "试" not in str(_x)))
_want_e2e = (40 - 25 + _n_taken * RES.gain_of("RES_OATH", "on_taken")
             + _n_hit * RES.gain_of("RES_OATH", "hit_skill"))
chk("③ 端到端真放一次守誓斩（真出招 · 真扣费 · 数字逐值对得上）",
    stacks(_c2, "RES_OATH") == _want_e2e,
    "⇒ %d 层（期望 %d = 40−25+%d+%d）· 日志 %d 行"
    % (stacks(_c2, "RES_OATH"), _want_e2e, RES.gain_of("RES_OATH", "on_taken"),
       RES.gain_of("RES_OATH", "hit_skill"), len(_lg2)))
chk("③ 本趟真的发生了 %d 次受击 / %d 次命中（期望就是按这两个数现算的）" % (_n_taken, _n_hit),
    _n_taken >= 0 and _n_hit >= 0)
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
# ★ fxmech：真源 03_游侠_v2 §二 的「攒法」写的是**每次行动 +1**（不是「只有短弓 +1」）。
#   域里六条主动原先只有短弓写了 `res_gain` ⇒ 点射 / 抢拍 / 后撤 / 狙击 / 连射 / 箭止 出手都不涨层，
#   于是「狙击花 4 层 · 连射花 6 层」在实战里够不着（六职业试玩报告：45 批里准星最高只到 2 层）。
#   判据两头：① 真出手那一路（定向 act_cast，逐条技能）② **域现算**（不写镜像表）。
_b5b = build("cls_ranger", 16, uid="u_res5b")
_c5b = focus(_b5b)
_mob5b = (_b5b.sides.get("enemy") or [None])[0]
put(_c5b, "RES_AIM", 0)
for _sid5 in ("SKILL_RNG_aimshot", "SKILL_RNG_backstep", "SKILL_RNG_quickstep"):
    dir_event(_b5b, "act_cast", actor=_c5b,
              ctx_extra={"target": _mob5b, "info": SK.skills()[_sid5]})
chk("⑤ ★ 每一条游侠主动出手都 +1（点射 / 后撤 / 抢拍 三手 ⇒ 3 层；改前只有短弓涨层）",
    stacks(_c5b, "RES_AIM") == 3, "⇒ %d 层" % stacks(_c5b, "RES_AIM"))
_miss5 = sorted(sid for sid, r in SK.skills().items()
                if isinstance(r, dict) and r.get("owner_class") == "cls_ranger"
                and r.get("kind_key") == "active"
                and int((r.get("res_gain") or {}).get("RES_AIM") or 0) != 1)
chk("⑤ ★ 域里**每一条**游侠主动都声明了 `res_gain.RES_AIM == 1`（现读域，不写镜像表）",
    not _miss5, "没声明的：%s" % (_miss5 or "无"))
_b6 = build("cls_priest", 16, uid="u_res6")
#: 这一档也要「**真挨到**」才算数 ⇒ 骑在 ③ 挂的那个 `no_dodge()` fixture 上
#: （闪避不关掉的话，「+1 祷言」这半也是掷硬币 —— 修女 16 级 dodge=0.0375）。
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
_want7 = max(1, int(100 * (1 - _mit)))
chk("⑥ 骑士 16 级 block=%g ⇒ F10 减免 %.4f（求值 formula_table，不重写公式）" % (_blk, _mit),
    0 < _mit < 0.6, "⇒ %.4f" % _mit)
# ★ g5-flake：这一档原先**只有「掷中」那一半真跑** —— `if _luck:` 恒真（种子 1 的头一枚骰子
#   0.134 < 0.25），`else:` 那半（「没掷中 ⇒ 一个字都不写」）**从没被执行过** = 判据只跑一半
#   （不叫的那种假绿）。现在**两态各钉一遍**，而且都不看手气（不是"换颗种子赌另一面"）。
_chance = (MECH.of("block_oath").get("block_chance") or {}).get("value")
_rand = random.random
try:
    # ① 掷中：把那一枚骰子钉成 0.10（< 声明的 block_chance）⇒ 必掷中，且与掷骰次序无关
    random.random = lambda: 0.10
    put(_c7, "RES_OATH", 0)
    _hp0 = int(_c7.get("hp") or 0)
    _lg7 = []
    LD.deal_damage(_b7, None, _c7, 100, _lg7)                      # source=None ⇒ 不掺等级压制
    _d7 = _hp0 - int(_c7.get("hp") or 0)
    chk("⑥ 掷中（fixture 把骰子钉成 0.10 < %s）⇒ 承伤按 F10 打折（100 点应剩 %d）" % (_chance, _want7),
        _d7 == _want7 and any("举盾挡下" in x for x in _lg7), "实测掉 %d 点" % _d7)
    chk("⑥ 掷中 ⇒ 回守誓 %d（账本 +%d + 本被动 +%d）+ 那一下的受击 +%d"
        % (_acct + _bonus + RES.gain_of("RES_OATH", "on_taken"), _acct, _bonus,
           RES.gain_of("RES_OATH", "on_taken")),
        stacks(_c7, "RES_OATH") == _acct + _bonus + RES.gain_of("RES_OATH", "on_taken"),
        "⇒ %d 层" % stacks(_c7, "RES_OATH"))
finally:
    random.random = _rand
# ② 没掷中：`block_chance` 压 0 ⇒ 机制第一行就 `return`（连骰子都不掷）⇒ 不打折、一个字都不写
_sb7 = no_block()
try:
    put(_c7, "RES_OATH", 0)
    _hp1 = int(_c7.get("hp") or 0)
    _lg7b = []
    LD.deal_damage(_b7, None, _c7, 100, _lg7b)
finally:
    restore_block(_sb7)
_d7b = _hp1 - int(_c7.get("hp") or 0)
chk("⑥ 没掷中（block_chance 压 0）⇒ 掉血 = 不打折的基线 100，且只写「受击」那一笔（+%d）"
    % RES.gain_of("RES_OATH", "on_taken"),
    _d7b == 100 and stacks(_c7, "RES_OATH") == RES.gain_of("RES_OATH", "on_taken")
    and not any("举盾挡下" in x for x in _lg7b),
    "掉 %d 点 · 层 %d" % (_d7b, stacks(_c7, "RES_OATH")))
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

restore_dodge(_sd)                     # ★ ③ 起挂的那个「挨打必中」fixture 到这儿还原
                                       #   （③⑤⑦ 三档的挨打渠道都骑在它上面；③ 的格挡那半
                                       #     已由 ③ 末尾的 restore_block 先还原了）

print()
print("══ ⑧ 引擎改动面（硬指标）")
#  ★ fxmech（2026-09-26）起：本批**动了引擎**（B4-4 两段耗时接线 + 一条可选否决口 `skill_gate_fn`）
#    ⇒ 判据从「引擎零改动」改成**钉住改动面**：只许落在声明的那些文件里（多一个文件就红）。
#  ★ 2026-09-27（跨手状态三条那一批）**换锚不换强度**：原先只看 `git log -1`（HEAD 那一笔），
#    而本批在引擎仓可以落好几笔（代码 → docs 落账 → 上一笔判据的 fixture 修）⇒ HEAD 是
#    docs-only 提交时那写法会假红。改成**自基准提交起 diff**（`<base>..HEAD` 的并集）。
#    ★ 换批时改 `_ENGINE_BASE8`（本批开工前引擎的 HEAD）与 `_want_t`。
#    ★ P-11（2026-09-27）**换批**：本批引擎改动 = 守卫拦截句读口那三份（见 `probe_mech` ⑮
#      同一处换批说明）⇒ 基准前移到 `f31ee59`、声明表换这三份；强度不变（多一份代码就红）。
import subprocess as _sp                                                # noqa: E402
_ENGINE_BASE8 = "f31ee59"
_want_t = sorted(["saintess_engine/config.py",
                  "saintess_engine/host/runtime.py",
                  "tests/test_host_contract.py"])
_out = _sp.run(["git", "-C", ENGINE, "status", "--porcelain"],
               capture_output=True, text=True, encoding="utf-8").stdout.strip()
_committed = {p for p in _sp.run(
    ["git", "-C", ENGINE, "diff", "--name-only", "%s..HEAD" % _ENGINE_BASE8],
    capture_output=True, text=True, encoding="utf-8").stdout.split() if p}
_code = sorted(p for p in _committed if not p.startswith("docs/"))
chk("⑧ 引擎仓工作区干净 + 本批（自 %s 起）的代码落点 == 声明的那几份（干净 %s ｜ 代码 %s）"
    % (_ENGINE_BASE8, _out == "", "、".join(_code) or "无"),
    _out == "" and _code == _want_t, "实际 %s / 声明 %s" % (_code, _want_t))

print()
print("结果：%s" % ("全绿 ✓" if not fails else "有红 ✗（%d 条）" % len(fails)))
sys.exit(0 if not fails else 1)
