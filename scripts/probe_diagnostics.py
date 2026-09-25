# -*- coding: utf-8 -*-
"""探针：战斗诊断通道（P-44）—— 「整场零诊断」+ 反证（故意塞个坏钩子，通道必须记下来）。

判据（两态，缺一不可）
--------------------------------------------------
① 正向：真打一整场（含技能/DoT/护盾/治疗/事件/死亡）⇒ `battle.diagnostics` **必须为空**
   （空 = 正常路径零成本；非空 = 内容侧有 bug，当场有人管）
② 反证：故意挂一个**必炸的钩子**（承伤乘区里除以零）⇒ 诊断必须记下那一条
   （证明这条通道真的在工作，而不是「反正永远是空的」）
③ 行为不变：反证里那一场要照常打完（异常不该阻断落地）—— 伤害照落、谁也没炸

用法：`GWEN_ENGINE=... python scripts/probe_diagnostics.py`（Python 3.12）
"""
import io
import os
import sys
import time
import types

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine"))
sys.path.insert(0, REPO)
from saintess_engine.package import load_stack          # noqa: E402

st = load_stack(REPO, inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp",
                                                     "ast_probe_diag.db"),
                              "clock": lambda: 1790308800.0})
st.install()
CMB = st.optional_submodule("combat")
SK = st.optional_submodule("skills_lookup")
MON = st.domain("monsters")
from ext_combat.battle import diagnostics as DG          # noqa: E402
from ext_combat.battle import schedule as SCH            # noqa: E402

_pass, _fail = [], []


def chk(name, cond, seen=""):
    (_pass if cond else _fail).append(name)
    print("  %s %s%s" % ("✓" if cond else "✗", name, ("  —— %s" % (seen,)) if seen else ""))


def battle(cls="cls_knight", lv=16, mid="ms_bone_wanderer", uid="u_diag"):
    b = CMB.build({"cls": cls, "level": lv, "name": "探", "uid": uid}, [mid], MON, uid=uid)
    return b


def run_full(b):
    """真打一场：普攻 + 技能 + 时间推进（DoT/护盾/治疗都会走到）。"""
    logs = []
    SCH.advance(b, logs)
    for _ in range(14):
        a = b.focus()
        if not a:
            break
        e = (b.sides.get("enemy") or [None])[0]
        if e is None or int(e.get("hp", 0) or 0) <= 0:
            break
        sub, _e2, _w2 = b.human_act("skill", "SKILL_KNT_oathwall", a)
        logs.extend([str(x) for x in (sub or [])])       # ★ 出招那一批行在返回值里（不收集就等于没打）
        SCH.settle_landing(b, logs, a)
        SCH.advance(b, logs)
    return logs


print("══ ① 真打一整场 ⇒ 零诊断")
_b = battle()
_lg = run_full(_b)
_d = DG.of(_b)
chk("① 整场打完 · 诊断为空（%d 条）" % len(_d), not _d, repr(_d[:2]))
chk("① 这一场真打了（日志非空 · 出了伤害/护盾行）",
    bool(_lg) and any(("伤害" in x or "护盾" in x) for x in _lg), "%d 行" % len(_lg))

print()
print("══ ② 反证：故意挂一个必炸的钩子（挂在 `on_taken` 上 ⇒ 异常由事件总线那层接住）⇒ 通道必须记下来")
_b2 = battle(uid="u_diag2")
_c2 = _b2.focus()


def _boom(battle, caster, target, params, logs):     # 内容侧写错的钩子：除以零
    1 / 0


import random                                        # noqa: E402
random.seed(20260925)
_c2.setdefault("triggers", {}).setdefault("on_taken", []).append({"action": "probe_boom_total"})
from ext_combat.battle import effects as EF          # noqa: E402
EF.register_action("probe_boom_total")(_boom)
SCH.advance(_b2, [])
_mob2 = (_b2.sides.get("enemy") or [None])[0]
_lg2 = []
from ext_combat.battle import landing as LD          # noqa: E402
LD.deal_damage(_b2, _mob2, _c2, 40, _lg2)
_d2 = DG.of(_b2)
chk("② 必炸的钩子 ⇒ 诊断记下来了（%d 条）" % len(_d2), bool(_d2),
    repr([(x.get("stage"), x.get("kind")) for x in _d2[:2]]))
chk("② 记的那条带阶段名与异常类型（不是一句空话）",
    bool(_d2) and str(_d2[0].get("stage")) and _d2[0].get("kind") == "ZeroDivisionError"
    and bool(_d2[0].get("msg")),
    repr(_d2[0] if _d2 else None))
chk("③ 行为不变：这一下照样落地（异常不阻断落地）",
    any("受到" in x for x in _lg2) and int(_c2.get("hp", 0)) < int(_c2.get("max_hp", 1)), repr(_lg2[-1:]))

print()
print("══ 汇总")
print("  通过 %d · 失败 %d" % (len(_pass), len(_fail)))
if _fail:
    for x in _fail:
        print("  ✗ %s" % x)
    sys.exit(1)
print("  结果：全绿 ✓")
