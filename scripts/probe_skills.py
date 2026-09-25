# -*- coding: utf-8 -*-
"""探针（第四刀）：skills 域读得到 · 六职业面板算得出 · 行动耗时 hook 挂上了。

用法（在 aetheran-package 仓根跑）：
    GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_skills.py
"""
from __future__ import annotations

import json
import os
import time
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(SCRIPTS))          # ★ 生成器那张表（rebuild_skills）的唯一来源
sys.path.insert(0, ENGINE)

from saintess_engine import config                                   # noqa: E402
from saintess_engine.package import load_stack, plan_stack           # noqa: E402

ok = True


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


print("探针：技能落地（第四刀）")
st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
print("  装入顺序：%s" % " → ".join(st.ids))
st.install()

# ① 域读得到
sk = st.domain("skills")
chk("skills 域读得到", sk is not None, "%d 条" % (len(sk) if sk else 0))
by_cls = {}
for sid, rec in (sk or {}).items():
    by_cls.setdefault(rec.get("owner_class", "?"), []).append(sid)
print("     六职业分布：%s" % " · ".join("%s %d" % (k, len(v)) for k, v in sorted(by_cls.items())))

# ② 七维完整性
need = ("name", "kind", "lv", "desc", "cd", "cast", "recover", "range", "mp", "power")
missing = [(sid, k) for sid, r in (sk or {}).items() for k in need if k not in r]
chk("30 条技能 7 维齐全（含 name/kind/lv/desc/cd/cast/recover/range/mp/power）", not missing,
    "" if not missing else str(missing[:4]))

# ③ 三份默认域 + actions
for d in ("commands", "texts", "tlogs", "classes", "skills"):
    chk("域 %-9s 有文件" % d, st.domain_path(d, required=False) is not None)

# ④ 六职业面板（引擎 PanelStack 真算）
from content import panel_build                                       # noqa: E402
from content.apply import install_engine                              # noqa: E402
from ext_combat.battle.stats import actor_stats                       # noqa: E402

install_engine()
print("  hook 状态：panel_layers_fn=%s  action_base_fn=%s  recover_base_fn=%s  time_model_fn=%s" % (
    bool(config.get_hook("panel_layers_fn")), bool(config.get_hook("action_base_fn")),
    bool(config.get_hook("recover_base_fn")), bool(config.get_hook("time_model_fn"))))

CLASSES = json.loads((REPO / "content" / "data" / "classes.json").read_text(encoding="utf-8"))
rows = []
for cid, c in CLASSES.items():
    lv = 10
    actor = panel_build.build_actor(cid, lv, c.get("suggest_alloc"))
    vals = actor_stats(None, actor)
    rows.append((c["name"], vals.get("max_hp"), vals.get("atk"), vals.get("matk"),
                 vals.get("def"), vals.get("mdef"), vals.get("spd"), vals.get("crit")))
    chk("%s 面板算得出（%d 键）" % (c["name"], len(vals)), len(vals) >= 10)

print()
print("  10 级面板（引擎 PanelStack 真算）：")
print("    %-8s %8s %7s %7s %7s %7s %7s %8s" % ("职业", "max_hp", "atk", "matk", "def", "mdef", "spd", "crit率"))
for r in rows:
    print("    %-8s %8.1f %7.1f %7.1f %7.1f %7.1f %7.1f %8.4f" % r)

# ⑤ 行动耗时 hook
ab, rb = config.get_hook("action_base_fn"), config.get_hook("recover_base_fn")
chk("action_base_fn('attack') = 60 刻", ab and abs(ab("attack") - 60) < 1e-9, "" if not ab else "%.1f" % ab("attack"))
chk("recover_base_fn('skill') = 50 刻", rb and abs(rb("skill") - 50) < 1e-9, "" if not rb else "%.1f" % rb("skill"))
rm = config.get_hook("recover_model_fn")
chk("recover_model_fn(spd=100, base=40) = 40 刻", rm and abs(rm(100, 40) - 40) < 1e-6, "" if not rm else "%.4f" % rm(100, 40))

# ⑥ 技能 7 维能喂给耗时模型
sid = "SKILL_MAG_ignite"
rec = sk.get(sid)
if rec:
    cast_ticks = config.get_hook("time_model_fn")(111.0, rec["cast"]["base"])
    chk("引燃 200 刻基准 @法师 spd 111 → %.1f 刻（≈191）" % cast_ticks, 180 < cast_ticks < 200)

# ⑦ ★ B3-14：**引擎通道 + 倍率公式**（原判据是「普攻取自己那班 power 最低的那条」——
#    那条判据把**辅助技**钉成了普攻：骑士盾墙(0.0) / 刺客·游侠后撤(0.0) / 修女净罪(0.0)）。
#    新判据（更严，且每一格都能复算）：
#      ① 域里每条技能都有 `kind_override` 且落在 `content/rules/kinds.json` 的值域里
#      ② 伤害技（kind_override ∈ 物理/魔法）必须有 `exprs`，且**等于** `<基准>*<power>`
#         复算（基准 = `classes.dmg_channel`：物理→atk · 法系→matk）—— 数值不算手打
#      ③ 治疗/增益类**不许**有 exprs（它们不产生伤害；有 exprs 就会去打人）
#      ④ 六职业各有**恰好一条** `basic: true`，power > 0，通道 = 该职业的 dmg_channel
#      ⑤ `basic_skill_of` 取回的就是那条（不是 power 最低的那条）
#      ⑥ 引擎侧真读到了：`kinds` 挂上、`kind_of("phys")` 非空、普攻能过
#         `resolve_basic_skill` 的 `exprs/formula` 门（缺了它六职业普攻全退化成兜底「挥击」）
from content import skills_lookup as SL                              # noqa: E402
import rebuild_skills as RSK                                         # noqa: E402

_KINDS = SL.kinds()
_ENGINE_NAMES = ("phys", "magi", "true", "heal", "buff")
chk("★ kinds 词表三头对账：引擎要的 5 个语义名 == kinds.json 的键（%s）"
    % " · ".join("%s→%s" % (k, _KINDS[k]) for k in _ENGINE_NAMES),
    set(_KINDS) == set(_ENGINE_NAMES) and all(_KINDS.values()))

_owned = {k: v for k, v in (sk or {}).items() if v.get("owner_class")}
_badkind = [(k, v.get("kind_override")) for k, v in _owned.items() if v.get("kind_override") not in _KINDS.values()]
chk("★ 30 条技能的 `kind_override` 都在 kinds 值域里（%d 条）" % len(_owned), not _badkind, "%s" % _badkind[:4])

_badexpr = []
for _k, _v in sorted(_owned.items()):
    _want = RSK.exprs_of(_v)
    _got = list(_v.get("exprs") or [])
    if _want != _got:
        _badexpr.append("%s 包=%s 算=%s" % (_v.get("name"), _got or "—", _want or "—"))
chk("★ 倍率公式逐条可复算（`exprs` == `<基准>*<power>`；治疗/增益不带 exprs）",
    not _badexpr, " · ".join(_badexpr[:4]))

_chan = {k: (SL.classes().get(v["owner_class"]) or {}).get("dmg_channel") for k, v in _owned.items()}
_badchan = [(k, c) for k, c in _chan.items() if c not in ("phys", "magi")]
chk("★ 六职业在 classes 域里都声明了 `dmg_channel`（物理/法系）", not _badchan, "%s" % _badchan)
_badbasis = [k for k, v in _owned.items()
             if v.get("exprs") and not str(v["exprs"][0]).startswith(
                 "atk*" if _chan.get(k) == "phys" else "matk*")]
chk("★ `exprs` 的基准与职业通道一致（物理吃 atk · 法系吃 matk）", not _badbasis, "%s" % _badbasis)

_BASIC = {k: v for k, v in _owned.items() if v.get("basic") is True}
_per = {}
for k in _BASIC:
    _per.setdefault(_BASIC[k]["owner_class"], []).append(k)
_badbasic = [c for c, ks in _per.items() if len(ks) != 1]
_badbasic += [k for k, v in _BASIC.items() if float(v.get("power", 0) or 0) <= 0]
chk("★ 六职业各有**恰好一条** `basic`，且是伤害技（power>0；原先是盾墙/后撤/净罪这些 0 倍率辅助技）",
    set(_per) == {v["owner_class"] for v in _owned.values()} and not _badbasic,
    " · ".join("%s→%s" % (c, "+".join(ks)) for c, ks in sorted(_per.items())) + (" ｜ 红：%s" % _badbasic if _badbasic else ""))

_badpick = []
for _cls in sorted(set(_per)):
    _b = SL.basic_skill_of(_cls)
    if not _b or _b.get("name") != (sk.get(_per[_cls][0]) or {}).get("name"):
        _badpick.append((_cls, (_b or {}).get("name"), _per[_cls]))
    elif not (_b.get("exprs") or _b.get("formula")):
        _badpick.append((_cls, "没 expr", _b.get("name")))
chk("★ `basic_skill_of` 取回的就是域里标了 basic 的那条（且带 exprs）"
    "（%s）" % " · ".join("%s→%s" % (c, (sk[_per[c][0]] or {}).get("name")) for c in sorted(_per)),
    not _badpick, "%s" % (_badpick or "无"))

from ext_combat.battle.actions import resolve_basic_skill          # noqa: E402
from ext_combat.battle import game_config as _GC                   # noqa: E402
_kind_hook = config.get_hook("kinds")
chk("★ 引擎 `kinds` 词表真挂上了（`kind_of('phys')` = %r）" % _GC.kind_of("phys"),
    bool(_kind_hook) and _GC.kind_of("phys") == _KINDS["phys"] and _GC.kind_of("heal") == _KINDS["heal"])
_badres = []
for _cls in sorted(set(_per)):
    _r = resolve_basic_skill(_cls)
    if not _r.get("exprs") and not _r.get("formula"):
        _badres.append(_cls)
    elif _r.get("name") != SL.basic_skill_of(_cls).get("name"):
        _badres.append("%s→%s" % (_cls, _r.get("name")))
chk("★ 六职业普攻都过得了 `resolve_basic_skill` 的 expr 门（不过就回落兜底「挥击」）",
    not _badres, "%s" % (_badres or "无"))

print()
print("结论：", "全过 ✅" if ok else "有红 ❌")
sys.exit(0 if ok else 1)
