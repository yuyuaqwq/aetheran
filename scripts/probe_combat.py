# -*- coding: utf-8 -*-
"""探针：战斗链路（B2-2）—— actor 造得出 · 技能索引得到 · 打得出伤害 · 结果合法 · 可复现。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_combat.py
"""
from __future__ import annotations

import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack          # noqa: E402

st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
st.install()

CB = st.optional_submodule("combat")
PB = st.optional_submodule("panel_build")
MON = st.domain("monsters")

fails = []
ok = lambda m: print("  ✓ " + m)
bad = lambda m: (fails.append(m), print("  ✗ " + m))

print("探针：战斗链路（ext_combat 接线）")

# ① 玩家 actor 造得出，且必备字段齐
pa = CB.player_actor({"cls": "cls_knight", "level": 3, "hp": 140, "uid": "u1"})
NEED = ("hp", "max_hp", "mp", "max_mp", "atk", "def", "spd", "skills", "level",
        "side", "kind", "human_controlled")
miss = [k for k in NEED if k not in pa]
(ok if not miss else bad)("玩家 actor 必备字段齐全（缺 %s）" % (miss or "无"))
(ok if pa.get("human_controlled") is True else bad)("玩家 actor 是 human_controlled（引擎靠它找输入焦点）")

# ② ★ 技能表非空且能被索引到（缺了会「静默空放」默认技 —— 实测打过 2000 条日志）
sk = pa.get("skills") or []
(ok if sk else bad)("玩家 actor 带技能表（%d 条）" % len(sk))

# ③ 怪 actor 造得出
mid = "ms_field_mouse"
ea = CB.monster_actor(mid, MON[mid])
(ok if ea.get("uid") == mid and ea.get("side") == "enemy" else bad)("怪 actor 造得出（%s）" % mid)
(ok if int(ea.get("level", 0)) == int(MON[mid].get("lv", 0)) else bad)("怪 actor 带 level（★ 等级真源 = actor 的 level，玩家与怪一视同仁）")

# ④ ★ 真打一场：出伤害 · 有结果 · 日志非空
res, logs, hp_after = CB.run_auto({"cls": "cls_knight", "level": 3, "hp": 140, "uid": "u1"},
                                  [mid], MON, seed=12345)
dmg_lines = [x for x in logs if "伤害" in x]
(ok if logs else bad)("战斗产生日志（%d 条）" % len(logs))
(ok if dmg_lines else bad)("★ 产生伤害（%d 条）—— 说明公式链通了" % len(dmg_lines))
(ok if res in ("victory", "defeat", "fled") else bad)("战斗有结果（%s）" % res)
(ok if 0 <= hp_after <= 99999 else bad)("战后血量合法（%s）" % hp_after)

# ⑤ ★ 无 expr 的主动技也能打出伤害（引擎修好后，非 expr 分支从 actor 取等级）
SKD = st.domain("skills")
plain = [k for k, v in SKD.items() if v.get("kind") == "主动" and not v.get("expr")]
(ok if plain else bad)("★ 存在「无 expr」的主动技（%d 条）—— 下面的战斗正是靠它们打的" % len(plain))

# ⑥ ★ 可复现（同种子同结果）
r1 = CB.run_auto({"cls": "cls_knight", "level": 3, "hp": 140, "uid": "u1"}, [mid], MON, seed=7)
r2 = CB.run_auto({"cls": "cls_knight", "level": 3, "hp": 140, "uid": "u1"}, [mid], MON, seed=7)
(ok if (r1[0], r1[2]) == (r2[0], r2[2]) else bad)("★ 同种子可复现（%s/%s vs %s/%s）" % (r1[0], r1[2], r2[0], r2[2]))

# ⑦ 面板栈可用（面板用**宪法键名**：hp / mo / atk / def …；引擎键名由 to_engine 转）
s = PB.panel_of("cls_knight", 3)
(ok if s.get("hp") and s.get("atk") else bad)("面板栈可用（hp=%s atk=%s · 宪法键名）" % (s.get("hp"), s.get("atk")))

# ⑧ ★ B3-8 死亡落地：真调「攻击」+ 造 1 血档，遭遇钉死在最强的那只上（必输）
import asyncio                                                       # noqa: E402

from content import cmds_ast as CA                                   # noqa: E402
from content import cmds_battle as CBAT                              # noqa: E402
from content import combat as CBmod                                  # noqa: E402


class _E:                       # handler 只要 env.save()（落档是处理器的责任）
    text = ""

    def save(self):
        pass


def _drive(fn, p, uid="u_die"):
    out = []

    async def _go():
        async for line in fn(_E(), None, uid, p):
            out.append(line)

    asyncio.run(_go())
    return out


def _lose_once(p):
    """下一场遭遇钉死在最强的那只怪上 —— 1 血必输，好验死亡那条线。"""
    strongest = max(MON, key=lambda k: int(MON[k].get("lv", 1) or 1))
    real = CBmod.pick_encounter
    CBmod.pick_encounter = lambda *a, **k: [strongest]
    try:
        return _drive(CBAT.attack, p)
    finally:
        CBmod.pick_encounter = real


_DIE = dict(CA.DEFAULT_PLAYER)
_DIE.update({"cls": "cls_knight", "level": 3, "hp": 1, "exp": 200,
             "bag": {"i_potion_heal": 2}, "loc": "belt_north", "node": "bn_bone",
             "uid": "u_die"})
_lines_die = _lose_once(_DIE)
(ok if any("眼前一黑" in x for x in _lines_die) else bad)("死亡走 texts 槽位（SYS_DEATH_WILD 真取到）")
(ok if (_DIE["loc"], _DIE["node"]) == CA.CHAPEL else bad)(
    "★ 血空回白烛堂（%s / %s）" % (_DIE["loc"], _DIE["node"]))
(ok if int(_DIE["hp"]) == int(_DIE["hp_max"]) else bad)(
    "★ 输了血回满（hp=%s / %s）—— 不许卡在 1 血" % (_DIE["hp"], _DIE["hp_max"]))
_LOST = 200 - int(_DIE["exp"])
_NEED = int(CA.exp_need(3) * 0.1)
(ok if _LOST == _NEED else bad)("掉当前等级经验的 10%%（掉 %s · 口径 %s · 剩 %s）" % (_LOST, _NEED, _DIE["exp"]))
(ok if (_DIE.get("bag") or {}) == {"i_potion_heal": 2} else bad)("★ 不掉装备（背包原样）")
(ok if (_DIE.get("flags") or {}).get("last_battle") else bad)("★ 每场写 flags.last_battle（『战斗日志』的唯一来源）")

# ⑨ ★ 『战斗日志』取得到上一场（原先只有读端、没人写 ⇒ 永远「还没有打过」）
_LOG = _drive(CBAT.battle_log, _DIE)
(ok if _LOG and not any("还没有打过" in x for x in _LOG) else bad)(
    "★『战斗日志』取得到上一场（%d 行）" % len(_LOG))

# ⑩ ★ 复活点必须是 maps 域里的真节点（id 写错就落在空中 —— 造档验不出这个）
_MP = st.domain("maps") or {}
_NODES = [n.get("id") for n in ((_MP.get(CA.CHAPEL[0]) or {}).get("nodes") or [])]
(ok if CA.CHAPEL[1] in _NODES else bad)("★ 复活点 %s 是 maps 域里的真节点" % (CA.CHAPEL[1],))

# ⑪ ★ B3-13 打怪给经验：真调「攻击」⇒ 经验涨的正好是 `exp_of_kill`（怪自己那级）
#    （口径：`06_第一阶段垂直切片/00_第一阶段内容总纲_v1 §七` 怪给经验 = 同级升级需求的 1/40）
import random as _rnd                                                       # noqa: E402

_rnd.seed(20260925)                        # 遭遇战内部走全局随机 ⇒ 钉住种子好对账
_MID = "ms_field_mouse"
_MON_LV = int(MON[_MID].get("lv", 1) or 1)
_GAIN = dict(CA.DEFAULT_PLAYER)
_GAIN.update({"cls": "cls_knight", "level": 10, "hp": 400,
              "gold": 0, "exp": 0, "loc": "belt_north", "node": "bn_bone",
              "bag": {}, "uid": "u_exp"})
_real_pick = CBmod.pick_encounter
CBmod.pick_encounter = lambda *a, **k: [_MID]
try:
    _lines_exp = _drive(CBAT.attack, _GAIN)
finally:
    CBmod.pick_encounter = _real_pick
(ok if any("打完了" in x for x in _lines_exp) else bad)("⑪ 前提：这一场真赢了（下面两条才成立）")
(ok if int(_GAIN["exp"]) == CA.exp_of_kill(_MON_LV) else bad)(
    "★ 打怪给经验（%s Lv%s ⇒ +%s · 实得 %s）" % (_MID, _MON_LV, CA.exp_of_kill(_MON_LV), _GAIN["exp"]))
(ok if int(_GAIN["gold"]) > 0 else bad)("打怪照样给钱（金币 %s）" % _GAIN["gold"])

# ⑫ ★ 「同级 40 只升一级」：1..20 级逐级对账 —— 偏出「一只」以上就红（数值不许手打）
_off = [(L, CA.exp_of_kill(L)) for L in range(1, 21)
        if abs(CA.exp_of_kill(L) * 40 - CA.exp_need(L)) > 40]
(ok if not _off else bad)("★ 同级 40 只升一级（逐级对账；偏出 %s）" % (_off or "无"))

# ⑬ ★ 升级唯一口 + 经验跨级结转（打怪与交活都走 `add_exp` —— 曲线只有 `exp_need` 一处）
_UP = dict(CA.DEFAULT_PLAYER)
_UP.update({"level": 1, "exp": 0})
_N = int(CA.exp_need(1) + CA.exp_need(2) + 5)
_ups = CA.add_exp(_UP, _N)
(ok if (_ups == 2 and _UP["level"] == 3 and _UP["exp"] == 5) else bad)(
    "★ 经验跨级结转（一次 +%s ⇒ 升 %s 级 · level=%s · 余 %s）" % (_N, _ups, _UP["level"], _UP["exp"]))

# ⑭ ★ 交活那条线也走同一个口（换掉原先内联的 while 之后不许变形）
from content import cmds_quest as CQ                                        # noqa: E402

_QREW = int((st.domain("quests") or {})["q_main_01"]["reward_exp"])
_Q = dict(CA.DEFAULT_PLAYER)
_Q.update({"level": 1, "exp": int(CA.exp_need(1)) - _QREW, "uid": "u_up",
           "flags": {"quests_active": ["q_main_01"], "quests_done": []}})


def _drive_text(fn, p, text, uid="u_up"):
    """要带参数的实现体：env.text 给出来（`交 1`）。"""
    out = []

    async def _go():
        e = _E()
        e.text = text
        async for line in fn(e, None, uid, p):
            out.append(line)

    asyncio.run(_go())
    return out


_lines_q = _drive_text(CQ.quest_deliver, _Q, "交 1")
(ok if (int(_Q["level"]) == 2 and int(_Q["exp"]) == 0) else bad)(
    "★ 交活升级走 add_exp（%s + %s ⇒ level=%s · 余 %s）"
    % (int(CA.exp_need(1)) - _QREW, _QREW, _Q["level"], _Q["exp"]))

# ⑮ ★ B3-6b-2d-keys-2：档位换 ASCII 机器键 `role_key`（P-20 甲案第二刀）—— **真造 actor + 真挑遇敌**
#   ① actor 的 `role` 照旧是域里那个档位名（内容侧词汇：引擎那份 `role` 限定规则逐字比它）
#   ② `is_boss` 与旧写法（`role == "boss"`）**逐只相同** —— 头目 / 层主 不算 BOSS
#   ③ 随机遇敌的候选闸：新键那一组与旧写法那一组**同一批怪**，且层主 / 世界 Boss 一只都不进池
sys.path.insert(0, os.path.join(REPO, "scripts"))           # 生成器那张表（ROLE_KEY）的唯一来源
import rebuild_monsters as _RBM                                              # noqa: E402

_PICK_RK = {_k for _k in _RBM.ROLE_KEY.values() if _k in ("normal", "elite", "chief")}
_actor_bad = [k for k, m in MON.items()
              if (lambda a: a.get("role") != m.get("role")
                  or a.get("is_boss") != (m.get("role") == "boss"))(CB.monster_actor(k, m))]
(ok if not _actor_bad else bad)("★ 怪 actor：`role` 照旧透传域里那个档位名 · `is_boss` 与 `role == \"boss\"` "
                                "逐只相同（%d 只；例外 %s）" % (len(MON), _actor_bad or "无"))
# ★ B3-7（副本内容）合入后：**档位白名单删掉了** —— 遇敌唯一的门改成 `habitat`
#   （原先只放 普通/精英/头目 ⇒ 层主 / Boss 永远打不上）。所以候选闸的定义随之改成
#   「挂了 habitat 的怪」，判据换成两条更贴意图的：野外/村镇不许混进 层主/Boss；塔里真挑得出。
_pool = {k for k, m in MON.items() if (m.get("habitat") or {}).get("maps")}
_pool_old = {k for k, m in MON.items() if _RBM.ROLE_KEY.get(m.get("role")) in _PICK_RK}
(ok if _pool and len(_pool) >= len(_pool_old) else bad)("★ 遇敌候选闸（挂 habitat 的怪 %d 只）⊇ 旧白名单那批（%d 只）"
                                                       % (len(_pool), len(_pool_old)))
_MP2 = st.domain("maps") or {}
_seen = set()
_seen_out = set()          # 野外 / 村镇
_seen_in = set()           # 副本（旧哨塔）
_DUNGEON = "old_watchtower"
for _loc, _mv in sorted(_MP2.items()):
    for _n in (_mv.get("nodes") or []):
        for _lv in (1, 5, 10, 15, 19):
            for _s in range(6):
                _got = CB.pick_encounter(MON, _loc, _n.get("id"), _lv, seed=_s)
                _seen.update(_got)
                (_seen_in if _loc == _DUNGEON else _seen_out).update(_got)
(ok if _seen and _seen <= _pool else bad)("★ 真挑 6×5×%d 把：挑出来的（%d 只）全在候选闸里" % (len(_MP2), len(_seen)))
if not _seen <= _pool:                                          # 真红了就把话补全（不然只有一句）
    bad("  混进来的：%s" % sorted(_seen - _pool))
_BIG = sorted(k for k, m in MON.items() if m.get("role_key") in ("warden", "boss"))
_big_out = sorted(set(_BIG) & _seen_out)
_big_in = sorted(set(_BIG) & _seen_in)
(ok if not _big_out else bad)("★ 层主 / 世界 Boss（%d 只）在**野外与村镇**一只都不混进来（%s）"
                              % (len(_BIG), _big_out or "无"))
(ok if _big_in == _BIG else bad)("★ 塔内那几只真挑得出来（%s / 共 %d）—— 白名单删掉后这才打得上了"
                                 % (_big_in, len(_BIG)))

# ⑯ ★ B3-6b-2d-keys-2：打钱分档（`cmds_battle`）换 ASCII `role_key` 之后**逐档对得上**
#   普通 3×lv · 精英 8×lv · 头目/层主/Boss 20×lv —— 与旧写法（中文那三组）在 17 只怪上逐只同值。
_GOLD_NEW = {k: (8 if m.get("role_key") == "elite"
                 else (20 if m.get("role_key") in ("chief", "warden", "boss") else 3))
             for k, m in MON.items()}
_GOLD_OLD = {k: (8 if m.get("role") == "精英"                 # 旧写法照抄一份，只为对账（探针侧允许引中文）
                 else (20 if m.get("role") in ("头目", "层主", "boss") else 3))
             for k, m in MON.items()}
(ok if _GOLD_NEW == _GOLD_OLD else bad)("★ 掉钱分档换键前后逐只同值（差：%s）"
                                       % (sorted(k for k in _GOLD_NEW if _GOLD_NEW[k] != _GOLD_OLD[k]) or "无"))
(ok if set(_GOLD_NEW.values()) == {3, 8, 20} else bad)("★ 三档都还在用（%s）" % sorted(set(_GOLD_NEW.values())))

# ══════════════════════════════════════════════════════════════
# ★ B3-14 战斗面：键名契约 / 通道 / 配平（真跑，不看模型自说自话）
# ══════════════════════════════════════════════════════════════
import io as _io                                                           # noqa: E402
import re as _re                                                           # noqa: E402
sys.path.insert(0, os.path.join(REPO, "scripts"))                           # 生成器那张表
import rebuild_monsters as _RBM                                            # noqa: E402
from content import skills_lookup as _SL                                   # noqa: E402
from ext_combat.battle import game_config as _GC                           # noqa: E402
from ext_combat.battle.stats import actor_stats as _stats                  # noqa: E402

print()
print("── ★ B3-14 ① 键名契约：域里那套键名要真到得了引擎（照域里的名字传 ⇒ 静默当 0/1）")
_KEY_BAD = []
for _mid, _m in sorted(MON.items()):
    _p = _m["panel"]
    _a = CB.monster_actor(_mid, _m)
    _st = _stats(None, _a)
    _want = [("max_hp", int(_p["hp"])), ("mdef", int(_p["res"]))]
    for _k, _v in _want:
        if _a.get(_k) != _v or _st.get(_k) != _v:
            _KEY_BAD.append("%s.%s actor=%s stats=%s 期望=%s" % (_mid, _k, _a.get(_k), _st.get(_k), _v))
    if abs(float(_st.get("dodge", 0)) - _p["eva"] / (_p["eva"] + 500.0)) > 1e-6:
        _KEY_BAD.append("%s.dodge=%s 期望率 %s" % (_mid, _st.get("dodge"), _p["eva"] / (_p["eva"] + 500.0)))
    if not 0.0 <= float(_st.get("crit", 0)) <= 0.75:
        _KEY_BAD.append("%s.crit=%s 不是率" % (_mid, _st.get("crit")))
(ok if not _KEY_BAD else bad)("★ 17 只怪：`hp→max_hp`（原先恒 1）· `res→mdef`（原先恒 0）· `eva→dodge`（原先恒 0，"
                              "且必须**率化**）· `crit` 率化（原先 13>1 ⇒ 必然暴击）　%s"
                              % ("全对" if not _KEY_BAD else "红：%s" % _KEY_BAD[:3]))

print()
print("── ★ B3-14 ② 六职业普攻打的是**自己那根属性**（原先全走 matk ⇒ 物理职业 5 点伤害）")
_BASIS = {}
for _cid, _c in sorted(PB.classes().items()):
    _ch = _c.get("dmg_channel")
    _BASIS[_cid] = "atk" if _ch == "phys" else "matk"
_DMG_RE = _re.compile(r"受到 (\d+) 点伤害")
_HIT_BAD = []
for _cid in sorted(_BASIS):
    _r = _SL.basic_skill_of(_cid)
    if not _r or not _r.get("exprs"):
        _HIT_BAD.append("%s 普攻没 expr（回落兜底）" % _cid); continue
    if not str(_r["exprs"][0]).startswith(_BASIS[_cid] + "*"):
        _HIT_BAD.append("%s 普攻走 %s" % (_cid, _r["exprs"][0])); continue
    _pl = {"cls": _cid, "level": 10, "uid": "u_ch", "name": "试", "alloc": _RBM.alloc_of(10, _cid)}
    _pl["hp"] = CA.hp_cap(_pl)
    _res, _logs, _ = CB.run_auto(_pl, [_MID], MON, seed=4242)
    _dmg = [int(x) for x in (_DMG_RE.search(l).group(1) for l in _logs
                             if ("💥 %s 受到" % MON[_MID].get("name", _MID)) in l and _DMG_RE.search(l))]
    _st = _stats(None, PB.build_actor(_cid, 10, _pl["alloc"]))
    _basis_v = float(_st.get(_BASIS[_cid], 0))
    if not _dmg:
        _HIT_BAD.append("%s 没打出伤害" % _cid); continue
    _lo, _hi = 0.5 * _basis_v * 0.8, 2.0 * _basis_v
    if not (_lo <= max(_dmg) <= _hi):
        _HIT_BAD.append("%s 单发 max=%s 不在 [%.1f, %.1f]（%s=%.1f）" % (_cid, max(_dmg), _lo, _hi, _BASIS[_cid], _basis_v))
(ok if not _HIT_BAD else bad)("★ 六职业 10 级真打一场：单发伤害落在自己那根属性附近（物理吃 atk · 法系吃 matk）　%s"
                              % ("全对" if not _HIT_BAD else "红：%s" % _HIT_BAD))

print()
print("── ★ B3-14 ③ 配平：四档基准怪 × 该等级**中位职业** × 16 场，实测出手次数 vs 设计次数")
#   设计次数 = `TIERS[档].hp_n × ARCH[原型].hp`（怪 hp 就是照它反推的）
#   口径真源：`12_怪物面板与精英词条池_v1.md` §一
_TIERS = (("ms_wild_dog", "普通"), ("ms_bitten_lumberjack", "精英"),
          ("ms_sunken_corpse", "头目"), ("ms_bone_warden", "层主"))
_BAL_BAD, _BAL_ROWS = [], []
for _mid, _tier in _TIERS:
    _m = MON[_mid]
    _lv = int(_m.get("lv", 1))
    _design = _RBM.TIERS[_tier]["hp_n"] * _RBM.ARCH[_m["archetype"]]["hp"]
    _med = sorted(_BASIS, key=lambda c: _RBM.per_hit_of(_lv, c))[3]      # 六取中位（第 4 个）
    _acts = []
    for _s in range(16):
        _pl = {"cls": _med, "level": _lv, "uid": "u_bal", "name": "试", "alloc": _RBM.alloc_of(_lv, _med)}
        _pl["hp"] = CA.hp_cap(_pl)
        _res, _logs, _ = CB.run_auto(_pl, [_mid], MON, seed=9000 + _s)
        _acts.append(sum(1 for x in _logs if ("🌀 %s 开始出招" % _pl["name"]) in x))
    _acts.sort()
    _me = _acts[len(_acts) // 2]
    _BAL_ROWS.append((_m["name"], _tier, _lv, _m["panel"]["hp"], _design, _med, _me))
    if not (0.6 * _design <= _me <= 1.8 * _design):
        _BAL_BAD.append("%s 设计 %.1f 实测中位 %d" % (_m["name"], _design, _me))
    print("     %-8s %-4s lv=%-3d hp=%-6d 设计 %5.1f 次 ｜ 中位职业 %-14s 实测 %2d 次"
          % (_m["name"], _tier, _lv, _m["panel"]["hp"], _design, _med, _me))
(ok if not _BAL_BAD else bad)("★ 四档实测出手次数落在设计值的 [0.6, 1.8] 倍内（配平没跑飞）　%s"
                              % ("全对" if not _BAL_BAD else "红：%s" % _BAL_BAD))

print()
print("── ★ B3-14 ④ 层主 / Boss 可打性（真跑 · 固定种子）：多少级稳、多少级难")
_WD, _BOSS = "ms_bone_warden", "ms_boss_oath_sentry"
_WD_LV = {}
for _lv in (13, 14, 15, 16, 17):
    _w = 0
    for _cid in sorted(_BASIS):
        for _s in range(6):
            _pl = {"cls": _cid, "level": _lv, "uid": "u_w", "name": "试", "alloc": _RBM.alloc_of(_lv, _cid)}
            _pl["hp"] = CA.hp_cap(_pl)
            _r, _l, _ = CB.run_auto(_pl, [_WD], MON, seed=7000 + _s)
            _w += 1 if _r == "victory" else 0
    _WD_LV[_lv] = _w
    print("     层主（守塔的骨架 lv17）· 单刷 lv%-3d ⇒ 胜 %2d/%-2d（%.0f%%）" % (_lv, _w, 36, 100.0 * _w / 36))
(ok if _WD_LV[17] >= 30 else bad)("★ 层主在**自己那一级（17）**单刷稳（≥ 83%%：实测 %d/36）" % _WD_LV[17])
(ok if _WD_LV[13] == 0 else bad)("★ 层主低 4 级（13）单刷打不过（实测 %d/36 —— 低于就是碾压，不该赢）" % _WD_LV[13])

_BS_OUT = {}
for _cid in sorted(_BASIS):
    _pl = {"cls": _cid, "level": 20, "uid": "u_b", "name": "试", "alloc": _RBM.alloc_of(20, _cid)}
    _pl["hp"] = CA.hp_cap(_pl)
    # ★ B3-17：走**真实单人口径**（`cmds_battle` 就是这么调的：今天只有单人 ⇒ party=1）
    _r, _l, _ = CB.run_auto(_pl, [_BOSS], MON, seed=5150, party=1)
    _BS_OUT[_cid] = (_r, sum(1 for x in _l if ("🌀 %s 开始出招" % _pl["name"]) in x))
(ok if all(v[0] in ("victory", "defeat") for v in _BS_OUT.values()) else bad)(
    "★ Boss 单刷**一定出结果**（不再撞 500 步护栏返回 None ⇒ 命令层只会回「（战斗结束：None）」）"
    "　%s" % " · ".join("%s=%s/%d 次" % (c.split("_")[-1], v[0], v[1]) for c, v in sorted(_BS_OUT.items())))
(ok if all(v[0] == "defeat" for v in _BS_OUT.values()) else bad)(
    "★ Boss 单人 **20 级 + 满强化对不上**（设计：4 人队内容 —— 单人必倒地，6 职业全 defeat）")
_BP = ["cls_knight", "cls_berserker", "cls_ranger", "cls_mage"]
_BW = 0
for _s in range(8):
    _ps = []
    for _cid in _BP:
        _pl = {"cls": _cid, "level": 19, "uid": "p_%s" % _cid, "name": _cid,
               "alloc": _RBM.alloc_of(19, _cid)}
        _pl["hp"] = CA.hp_cap(_pl)
        _ps.append(CB.player_actor(_pl))
    import random as _rnd2                                                       # noqa: E402
    from ext_combat import Battle as _Btl                                        # noqa: E402
    _rnd2.seed(31337 + _s)
    _b2 = _Btl("monster", sides={"player": _ps,
                                 "enemy": [CB.monster_actor(_BOSS, MON[_BOSS], party=len(_BP))]})
    _l2 = []
    _b2.auto_run(_l2)
    _BW += 1 if _b2.result == "victory" else 0
(ok if _BW >= 7 else bad)("★ 4 人队（骑士/狂战士/游侠/法师 · 19 级）真打完 Boss：胜 %d/8 —— 这是 Boss 唯一走得通的路"
                          "（组队今天还没接线 ⇒ 塔顶那间单刷必倒地，见 _notes.md）" % _BW)

# ══════════════════════════════════════════════════════════════════════════════
# ★ B3-17 ⑤ 单人口径（Boss 单人 ÷2）—— 数据 / 判据 / 真跑统计量三头
# ══════════════════════════════════════════════════════════════════════════════
print()
print("── ★ B3-17 ⑤ 单人口径：Boss 单人 hp ÷2（真源 `12_…` §一④ / `17_组队与策略配合_v1` §五"
      "/ `22_旧哨塔_逐间设计_v1` §三④「组队时按人数缩放（P1 单人也能过）」）")
_PS_ONLY = sorted(k for k, m in MON.items() if (m.get("mods") or {}).get("party_scale"))
(ok if _PS_ONLY == [_BOSS] else bad)(
    "★ 带「按人数缩放」表的只有团队内容那一只（%s）—— 别的怪一格不动"
    % " · ".join(MON[k]["name"] for k in _PS_ONLY))

_BH = MON[_BOSS]["panel"]
_a1 = CB.monster_actor(_BOSS, MON[_BOSS], party=1)
_a4 = CB.monster_actor(_BOSS, MON[_BOSS], party=4)
_an = CB.monster_actor(_BOSS, MON[_BOSS])
_want1 = int(round(float(_BH["hp"]) * 0.5))
(ok if int(_a1.get("max_hp")) == _want1 else bad)(
    "★ 单人（party=1）Boss 的面板血 = 面板 ÷2（%s → %s · 期望 %s）"
    % (_BH["hp"], _a1.get("max_hp"), _want1))
(ok if int(_a1.get("atk")) == int(_BH["atk"]) else bad)(
    "★ 单人档**只动血那一项**（文档两处字面都只说「**血**按 ÷2 看」）—— atk 仍是 %s"
    % _a1.get("atk"))
(ok if int(_a4.get("max_hp")) == int(_BH["hp"]) and int(_an.get("max_hp")) == int(_BH["hp"]) else bad)(
    "★ 4 人档 / 不传人数（= 不知道 ⇒ 设计值）都是**原值**（%s / %s vs 面板 %s）"
    % (_a4.get("max_hp"), _an.get("max_hp"), _BH["hp"]))
_drift = [k for k, m in MON.items() if k != _BOSS
          and int(CB.monster_actor(k, m, party=1).get("max_hp"))
          != int(CB.monster_actor(k, m).get("max_hp"))]
(ok if not _drift else bad)("★ 另外 16 只：单人档与设计档**逐只同值**（差：%s）" % (_drift or "无"))

_FC = []
try:                       # ① 表的键不是正整数人数 ⇒ 当场抛
    CB.party_scale_of({"mods": {"party_scale": {"solo": {"hp": 0.5}}}}, 1)
    _FC.append("非法键没抛")
except ValueError:
    pass
try:                       # ② 人数不是正整数 ⇒ 抛（不知道要传 None，不许拿 0 蒙）
    CB.party_scale_of({"mods": {"party_scale": {"1": {"hp": 0.5}}}}, 0)
    _FC.append("party=0 没抛")
except ValueError:
    pass
if CB.party_scale_of({"mods": {"party_scale": {"1": {"hp": 0.5}}}}, None) != {}:
    _FC.append("party=None 没有退回设计值")
try:                       # ③ 要缩的面板键不在 panel 里 ⇒ 抛（键名对不上不静默当 0）
    CB.monster_actor("syn_fake", {"name": "假怪", "lv": 1, "panel": {"hp": 10, "atk": 1},
                                  "mods": {"party_scale": {"1": {"mdef": 0.5}}}}, party=1)
    _FC.append("面板键对不上没抛")
except KeyError:
    pass
(ok if not _FC else bad)("★ fail-closed 三条（非法键 / 非正整数人数 / 面板键对不上 —— 都当场抛；"
                         "「不知道几个人」= 不缩放）　%s" % ("全对" if not _FC else "红：%s" % _FC))

_BST = []
for _lv in (18, 19, 20):
    _arm = {}
    for _party in (1, None):                     # 单人档 vs 设计档（同种子 · 同配置 · 16 场 × 6 职业）
        _rows = []
        for _cid in sorted(_BASIS):
            for _s in range(16):
                _pl = {"cls": _cid, "level": _lv, "uid": "u_ps", "name": "试",
                       "alloc": _RBM.alloc_of(_lv, _cid)}
                _pl["hp"] = CA.hp_cap(_pl)
                _r, _l, _ = CB.run_auto(_pl, [_BOSS], MON, seed=6100 + _s, party=_party)
                _rows.append((_r, sum(1 for x in _l if ("🌀 %s 开始出招" % _pl["name"]) in x)))
        _ac = sorted(x[1] for x in _rows)
        _arm[_party] = (sum(1 for x in _rows if x[0] == "victory"), len(_rows), _ac[len(_ac) // 2])
    _BST.append((_lv, _arm[1], _arm[None]))
    print("     lv%-3d ｜ 单人档 胜 %2d/%-2d 出手 med=%-3d ｜ 设计档 胜 %2d/%-2d 出手 med=%d"
          % (_lv, _arm[1][0], _arm[1][1], _arm[1][2], _arm[None][0], _arm[None][1], _arm[None][2]))
(ok if all(b[0] >= a[0] for _lv, a, b in _BST) else bad)(
    "★ 单人档**只会更宽松**（同种子同配置：单人档胜场 ≥ 设计档 —— 缩放方向不许反）　%s"
    % " · ".join("lv%d %d≥%d" % (lv, b[0], a[0]) for lv, a, b in _BST))
print("     · ★ 但**单人仍然全败**（%s）⇒ 「÷2」这条口径落了、也没落错，可它**没达到**"
      " `17_ §五`「单人能过」 / `22_ §三④`「P1 单人也能过」那句 —— 见 `_notes.md` §二·1（附实测对照）"
      % " · ".join("lv%d %d/96" % (lv, b[0]) for lv, _a, b in _BST))
# ③ 三头对账：生成器那张表 ↔ schema 的键形状 ↔ 域里那一格（单人口径只有**一个**来源）
_PS_SCHEMA = _io.open(os.path.join(REPO, "schemas", "monsters.schema.json"), encoding="utf-8").read()
_PS_TBL = (MON[_BOSS].get("mods") or {}).get("party_scale") or {}
_PS_OK = (_PS_TBL == {n: dict(v) for n, v in _RBM.PARTY_SCALE.items()}
          and set(_RBM.PARTY_SCALE) == {"1"}
          and '"party_scale"' in _PS_SCHEMA and "^[1-9][0-9]*$" in _PS_SCHEMA
          and abs(float(_RBM.PARTY_SCALE["1"]["hp"]) - 0.5) < 1e-9)
(ok if _PS_OK else bad)(
    "★ 单人档三头对账：生成器 `RBM.PARTY_SCALE` == 域 `mods.party_scale` == schema 那一格"
    "（键形状 `^[1-9][0-9]*$`）· 值 = 文档给的 0.5（%s）" % _PS_TBL)

print()
print("结果：%s" % ("全绿 ✓" if not fails else "有红 ✗"))
sys.exit(1 if fails else 0)
