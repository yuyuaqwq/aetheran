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
_DIE.update({"cls": "cls_knight", "level": 3, "hp": 1, "hp_max": 100, "exp": 200,
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

print()
print("结果：%s" % ("全绿 ✓" if not fails else "有红 ✗"))
sys.exit(1 if fails else 0)
