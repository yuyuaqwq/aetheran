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
(ok if ea.get("_player_lv") else bad)("怪 actor 带 _player_lv（★ 引擎算 k_def 要它；缺了 fail-closed 抛错）")

# ④ ★ 真打一场：出伤害 · 有结果 · 日志非空
res, logs, hp_after = CB.run_auto({"cls": "cls_knight", "level": 3, "hp": 140, "uid": "u1"},
                                  [mid], MON, seed=12345)
dmg_lines = [x for x in logs if "伤害" in x]
(ok if logs else bad)("战斗产生日志（%d 条）" % len(logs))
(ok if dmg_lines else bad)("★ 产生伤害（%d 条）—— 说明公式链通了" % len(dmg_lines))
(ok if res in ("victory", "defeat", "fled") else bad)("战斗有结果（%s）" % res)
(ok if 0 <= hp_after <= 99999 else bad)("战后血量合法（%s）" % hp_after)

# ⑤ ★ 技能 expr 全覆盖（缺 expr 的主动技会走引擎的「非 expr 分支」⇒ 那里读 _player_lv ⇒ 怪侧必炸）
SKD = st.domain("skills")
no_expr = [k for k, v in SKD.items() if v.get("kind") == "主动" and not v.get("expr")]
(ok if not no_expr else bad)("★ 所有主动技都有 expr（缺 %s）" % (no_expr or "无"))

# ⑥ ★ 可复现（同种子同结果）
r1 = CB.run_auto({"cls": "cls_knight", "level": 3, "hp": 140, "uid": "u1"}, [mid], MON, seed=7)
r2 = CB.run_auto({"cls": "cls_knight", "level": 3, "hp": 140, "uid": "u1"}, [mid], MON, seed=7)
(ok if (r1[0], r1[2]) == (r2[0], r2[2]) else bad)("★ 同种子可复现（%s/%s vs %s/%s）" % (r1[0], r1[2], r2[0], r2[2]))

# ⑦ 面板栈可用（面板用**宪法键名**：hp / mo / atk / def …；引擎键名由 to_engine 转）
s = PB.panel_of("cls_knight", 3)
(ok if s.get("hp") and s.get("atk") else bad)("面板栈可用（hp=%s atk=%s · 宪法键名）" % (s.get("hp"), s.get("atk")))

print()
print("结果：%s" % ("全绿 ✓" if not fails else "有红 ✗"))
sys.exit(1 if fails else 0)
