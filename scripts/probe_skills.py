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
chk("%d 条技能 7 维齐全（含 name/kind/lv/desc/cd/cast/recover/range/mp/power）" % len(sk or {}), not missing,
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
chk("★ %d 条技能的 `kind_override` 都在 kinds 值域里" % len(_owned), not _badkind, "%s" % _badkind[:4])

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

# ══════════════════════════════════════════════════════════════
# ⑧ ★ B4-1：T1 满编账（48 条 = 42 主动 + 6 被动）—— 域 · 生成器 · 消费端三头对账
# ══════════════════════════════════════════════════════════════
print()
print("── ★ B4-1：T1 技能满编账（六职业 7 主动 + 1 被动 = 48 条）")
import collections as _coll                                              # noqa: E402

_CLS8 = sorted(k for k in (st.domain("classes") or {}) if not str(k).startswith("_"))
_OWN = {k: v for k, v in (sk or {}).items() if isinstance(v, dict) and v.get("owner_class")}
_KKS = {str(v.get("kind_key") or "") for v in _OWN.values()}
chk("★ 48 条技能都带 ASCII `kind_key`（%s）：%s"
    % (" · ".join(sorted(_KKS)), " · ".join(sorted({str(v.get("kind")) for v in _OWN.values()}))),
    _KKS == {"active", "passive"} and all(
        (v.get("kind_key") == "passive") == (v.get("kind") == "被动") for v in _OWN.values()),
    "kind_key 取值 %s" % sorted(_KKS))

_c8 = _coll.Counter((v.get("owner_class"), str(v.get("kind_key"))) for v in _OWN.values())
_bad8 = [c for c in _CLS8 if (_c8[(c, "active")], _c8[(c, "passive")]) != (7, 1)]
chk("★ 六职业到 20 级**满编**：%s（合 %d 条 = %d 主动 + %d 被动）"
    % (" · ".join("%s %d+%d" % ((st.domain("classes")[c] or {}).get("name"), _c8[(c, "active")],
                                _c8[(c, "passive")]) for c in _CLS8),
       len(_OWN), sum(_c8[(c, "active")] for c in _CLS8), sum(_c8[(c, "passive")] for c in _CLS8)),
    len(_OWN) == 48 and not _bad8, "%s" % _bad8)

_badP8 = []
for k, v in sorted(_OWN.items()):
    if v.get("kind_key") != "passive":
        continue
    if float(v.get("power") or 0) != 0 or v.get("exprs") or int(v.get("lv") or 0) != 16 \
            or int(v.get("mp") or 0) != 0 or int(v.get("cd") or 0) != 0 or not v.get("mech"):
        _badP8.append((k, v.get("lv"), v.get("power"), v.get("exprs"), v.get("mech")))
chk("★ 六条被动：power 0 · 不带 exprs（它们不产生伤害）· cd/mp 0 · lv=16（真源 05_系统总表"
    "「职业被动 16–20 级开」）· 都挂机制", not _badP8, "%s" % _badP8[:3])

_new18 = sorted((k, int(v.get("lv") or 0)) for k, v in _OWN.items()
                if str(v.get("kind_key")) == "active" and int(v.get("lv") or 0) > 1)
_old30 = [k for k, v in _OWN.items() if int(v.get("lv") or 0) <= 1]
chk("★ B4-1 新补的 12 条主动都带解锁等级、落在 11–16（%s）；原先那 %d 条仍 lv=1（不动已落地的数据）"
    % (" · ".join("%s@%d" % (k.replace("SKILL_", ""), l) for k, l in _new18), len(_old30)),
    len(_new18) == 12 and all(11 <= l <= 20 for _k, l in _new18) and len(_old30) == 30,
    "%s" % (_new18[:3],))

# 消费端①：战斗技能表按等级挑、且**不含被动**
from content import combat as _CB8                                       # noqa: E402

_ds8 = {}
for c in _CLS8:
    _ds8[c] = [_CB8._default_skills(c, lv) for lv in (1, 10, 20)]
_bad8b = [c for c in _CLS8 if len(_ds8[c][2]) != 7 or _ds8[c][2] == _ds8[c][1] == _ds8[c][0]]
_bad8b += [c for c in _CLS8 if any(k in _ds8[c][2] for k, v in _OWN.items()
                                   if v.get("owner_class") == c and v.get("kind_key") == "passive")]
chk("★ 战斗技能表（`combat._default_skills`）按等级挑、**被动一条都不进**：%s"
    % " · ".join("%s %d/%d/%d" % ((st.domain("classes")[c] or {}).get("name"), len(_ds8[c][0]),
                                  len(_ds8[c][1]), len(_ds8[c][2])) for c in _CLS8),
    not _bad8b, "%s" % _bad8b[:3])
from content import cmds_skill as _CSK8                                   # noqa: E402

_bad8d = []
for c in _CLS8:
    _av8 = [k for k, _v in _CSK8._of_class(c, 16)[0] if _v.get("kind_key") != "passive"]
    if _av8 != _CB8._default_skills(c, 16):
        _bad8d.append((c, _av8, _CB8._default_skills(c, 16)))
chk("★ 16 级那一刻：`技能` 页里**能放的那班**与战斗技能表逐条同序（被动只出现在技能页、不进球场）",
    not _bad8d, "%s" % _bad8d[:2])

# 消费端②：被动不许当技能放（真调实现体那一手）
import asyncio as _a8                                                     # noqa: E402
import time as _t8                                                        # noqa: E402
from content import cmds_battle as _CBL8                                  # noqa: E402


class _E8(object):
    def __init__(self, text=""):
        self.text = text

    def save(self):
        pass


def _drive8(fn, p, text=""):
    out = []

    async def _go():
        async for _ln in fn(_E8(text), None, "u_sk8", p):
            out.append(str(_ln))
    _a8.run(_go())
    return out


_PK8 = next(k for k, v in sorted(_OWN.items()) if v.get("kind_key") == "passive"
            and v.get("owner_class") == "cls_knight")
_PN8 = _OWN[_PK8]["name"]
_got8 = _drive8(_CBL8.skill_cast, {"cls": "cls_knight", "level": 16, "race": "human",
                                   "hp": 100, "bag": {}, "equipped": {}, "flags": {}, "codex": {}},
                "技能 %s" % _PN8)
chk("★ 被动**不许当技能放**（真敲「技能 %s」⇒ 出一句放不出来，不是静默白费一手）" % _PN8,
    _got8 == [(st.domain("texts") or {}).get("COMBAT_SKILL_BAD", {}).get("value", "")
              .replace("{name}", _PN8)],
    "%s" % _got8[:2])

# 生成器：kind_key 的映射表是唯一来源（域里每条都能被它复算）
import rebuild_skills as _RS8                                             # noqa: E402

_bad8c = [(k, v.get("kind_key"), _RS8.kind_key_of(v)) for k, v in _OWN.items()
          if v.get("kind_key") != _RS8.kind_key_of(v)]
chk("★ `kind_key` 逐条可复算（唯一来源 = `rebuild_skills.KIND_KEY`：主动→active · 被动→passive）",
    not _bad8c, "%s" % _bad8c[:3])

print()
print("结论：", "全过 ✅" if ok else "有红 ❌")
sys.exit(0 if ok else 1)
