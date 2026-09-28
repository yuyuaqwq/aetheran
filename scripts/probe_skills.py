# -*- coding: utf-8 -*-
"""探针（第四刀）：skills 域读得到 · 六职业面板算得出 · 行动耗时 hook 挂上了。

用法（在 aetheran-package 仓根跑）：
    GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_skills.py
"""
from __future__ import annotations

import json
import io
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
#: ★ 2026-09-25（P-40）：「描述」那一维从 `desc`（悬空的槽位名）改成 `note`（技能页真渲它那句）
#:   —— 这一条**只加强**：48 条技能现在**每条都必须有**一句玩家看得见的描述（摘要是红的）。
need = ("name", "kind", "kind_key", "lv", "note", "cd", "cast", "recover", "range", "mp", "power")
missing = [(sid, k) for sid, r in (sk or {}).items() for k in need if k not in r]
chk("%d 条技能字段齐全（name/kind/kind_key/lv/note/cd/cast/recover/range/mp/power）" % len(sk or {}),
    not missing,
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
# ★ L1980-1 补上真正缺的那条比对：上面 `_ENGINE_NAMES` 是**手抄**的第三份名单，
#   代表「引擎要哪 5 个名字」—— 它与引擎**没有任何机械关联**，所以「引擎改了名字
#   忘了同步这里」这道洞是敞着的（审计原判断「删掉 skills_lookup.KIND_NAMES 后
#   probe 仍全绿 = 少一个真源」成立；但台账建议的「probe 改 import 那个常量」是
#   **错的**：那会变成 `set(kinds()) == set(KIND_NAMES)` 拿被测对象比自己，恒真）。
#   ⇒ 正确的收法 = **让引擎自己成为第三个头**：静态扫引擎 `actions.py` 里
#     `_kind("...")` 的全部实参，与本探针这份独立声明逐名对账。
#     探针这份**必须继续独立**（它的价值就是「第三方声明」，不能改成 import）。
#   ★ 引擎仓路径从环境变量取（`GWEN_FRAMEWORK_DIR`），取不到就**跳过并点名**
#     —— 不是静默通过（判据 fail-closed：认不出引擎在哪 = 这条没跑成，不是过了）。
_ENG16 = os.environ.get("GWEN_FRAMEWORK_DIR", "").strip()
_acts16 = os.path.join(_ENG16, "extends", "ext_combat", "battle", "actions.py") if _ENG16 else ""
_engine_wants16 = set()
if _acts16 and os.path.isfile(_acts16):
    import re as _re16
    with io.open(_acts16, encoding="utf-8") as _fh16:
        _engine_wants16 = set(_re16.findall(r'_kind\(\s*"([^"]+)"\s*\)', _fh16.read()))
chk("★ 三头对账（补）：引擎 `actions.py` 实扫出来的 kind 名 == 本探针独立声明的 5 个"
    "（引擎 %d 个：%s）—— 引擎改名忘了同步这边当场红"
    % (len(_engine_wants16), " · ".join(sorted(_engine_wants16))),
    bool(_ENG16) and os.path.isfile(_acts16) and _engine_wants16 == set(_ENGINE_NAMES),
    "GWEN_FRAMEWORK_DIR=%s（未设 / 路径不存在 ⇒ 这条**没跑成**，不是过了）" % (_ENG16 or "<空>",))


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

# ══════════════════════════════════════════════════════════════
# ⑨ ★ fix-f-dupname：**撞名技能认本职业那条**
#    （真人试玩 · nightplay 基线：刺客敲 `技能 后撤` 恒回「这一手你放不出来」，
#      可同一张 `技能` 页把它列在「已会 5 条」里 —— 自己会、却永远放不出来）
#    根因：`cmds_skill._by_name` 按 `sorted(sk)` 取第一条（id 序 `RNG_ < SHD_`）⇒
#      两个职业同名时刺客永远认到游侠那条 ⇒ owner 不符 ⇒ `COMBAT_SKILL_BAD`。
#    这里**现算**域里的撞名组（不硬编码技能名），钉三件事：
#      ① 撞名那一条，本职业的人认到的就是**本职业**那条（按 id 直认也不受影响）；
#      ② 别人门的同名技能照旧认得到、但认出来的**不是他那一门** ⇒ 调用点照旧拦
#         （`COMBAT_SKILL_BAD` / `SYS_SKILL_NOTMINE` 的语义一个字没松 —— 只紧不松）；
#      ③ 「技能」页列的那一条 **==** 真放进球场的那一条（页和释放走同一个口）。
# ══════════════════════════════════════════════════════════════
print()
print("── ★ fix-f-dupname：撞名技能（一对「后撤」落在两门上）认本职业那条")
_KSK9 = {k: v for k, v in (sk or {}).items() if isinstance(v, dict) and v.get("owner_class")}
_GRP9: dict = {}
for _k9, _v9 in _KSK9.items():
    _GRP9.setdefault(str(_v9.get("name") or ""), []).append(_k9)
_DUP9 = {n: sorted(i) for n, i in _GRP9.items() if len(i) > 1}
_CROSS9 = {n: i for n, i in _DUP9.items()
           if len({str(_KSK9[x].get("owner_class")) for x in i}) > 1}
chk("★ 域里**撞名**的技能现算：%s（合 %d 组 · 其中**跨门**的 %d 组 —— 跨门撞名是这条判据的靶子）"
    % (" · ".join("%s→%s" % (n, "+".join(i)) for n, i in sorted(_DUP9.items())) or "无",
       len(_DUP9), len(_CROSS9)),
    bool(_CROSS9), "撞名组：%s" % (_DUP9 or "无"))

_MINE9, _OTHER9, _EXACT9, _BADPAGE9 = [], [], [], []
for _n9, _ids9 in sorted(_CROSS9.items()):
    _owners9 = {str(_KSK9[x].get("owner_class")) for x in _ids9}
    for _c9 in sorted(_CLS8):
        _page9 = [x for x in _CSK8.known_ids({"cls": _c9, "level": 16})
                  if (_KSK9.get(x) or {}).get("name") == _n9]
        _got9, _rec9 = _CSK8._by_name(_KSK9, _n9, _c9)
        if _c9 in _owners9:
            if _got9 not in _ids9 or str((_rec9 or {}).get("owner_class") or "") != _c9:
                _MINE9.append((_c9, _n9, _got9))
            if set(_page9) != {_got9}:
                _BADPAGE9.append((_c9, _n9, "页列 %s / 认到 %s" % (_page9, _got9)))
        else:
            if _page9:
                _BADPAGE9.append((_c9, _n9, "页上不该有它：%s" % _page9))
            if _got9 and str((_rec9 or {}).get("owner_class") or "") == _c9:
                _OTHER9.append((_c9, _n9, _got9))
    for _i9 in _ids9:
        if _CSK8._by_name(_KSK9, _i9, "cls_none_such")[0] != _i9:
            _EXACT9.append(_i9)
chk("★ 每一条撞名的技能：**本职业的人**认到的就是本职业那条（%s）"
    % " · ".join("%s→%s" % (str(_KSK9[x].get("owner_class")), _KSK9[x].get("name"))
                 for _n, _i in sorted(_CROSS9.items()) for x in _i),
    not _MINE9, "%s" % (_MINE9[:3],))
chk("★ **别人门**的同名技能：照旧认得到、而认出来的**不是你那一门** ⇒ 调用点照旧拦"
    "（改这一档为「认不出」会把门放**松** —— `SYS_SKILL_NOTMINE` 会退化成「域里没有这条」）",
    not _OTHER9, "%s" % (_OTHER9[:3],))
chk("★ 撞名的技能**按 id 直认**照旧（不受 cls 影响）", not _EXACT9, "%s" % (_EXACT9[:3],))
chk("★ ★ 「技能」页**列的那一条** == 认得出、放得出来的那一条（页与释放同一个口 —— "
    "改前刺客页上列 `SHD`、放的那一路认 `RNG`）", not _BADPAGE9, "%s" % (_BADPAGE9[:3],))

# ★ ★ 真调实现体那一手：本职业放得出来 / 别的职业照旧放不出来（bug 的原句就是这两句之差）
_BAD9 = (st.domain("texts") or {}).get("COMBAT_SKILL_BAD", {}).get("value", "")


def _cast9(cls9, name9, uid9):
    _p9 = {"cls": cls9, "level": 16, "race": "human", "hp": 300, "bag": {}, "equipped": {},
           "flags": {}, "codex": {}}
    _out9 = []

    async def _go9():
        async for _ln9 in _CBL8.skill_cast(_E8("技能 %s" % name9), None, uid9, _p9):
            _out9.append(str(_ln9))
    _a8.run(_go9())
    return _out9


_REL9 = []
for _n9, _ids9 in sorted(_CROSS9.items()):
    _owners9 = {str(_KSK9[x].get("owner_class")) for x in _ids9}
    for _c9 in sorted(_CLS8):
        _lines9 = _cast9(_c9, _n9, "u_dup_%s_%d" % (_c9, len(_REL9)))
        if _BAD9.replace("{name}", _n9) in _lines9:
            if _c9 in _owners9:
                _REL9.append((_c9, _n9, "本职业的却放不出来", _lines9[:1]))
        elif _c9 not in _owners9:
            _REL9.append((_c9, _n9, "别的职业却放得出来", _lines9[:1]))
chk("★ ★ 真调 `skill_cast`：撞名那一条 —— 本职业放得出来 · 别的职业照旧「放不出来」"
    "（改前刺客这一路恒回「这一手你放不出来」）", not _REL9, "%s" % (_REL9[:3],))

print()
print("── ★ fix-l：**「等级没到」那一档要说得出「要几级」**（试玩 berserker b58）")
#   「技能 血债」（11 级才学）在 1~2 级敲 ⇒ 原先回的是「这一手你放不出来 —— 敲『技能』看你这一门
#   会哪些。」——玩家读成「这门没这条技能」，可同一张 `技能` 页正写着「到 11 级才能学」。
#   根因：抬头那张门表写的第三道门（`SYS_SKILL_TOO_LOW`）**走不到** —— `owner` 判定与
#   `sid not in known_ids(p)` 挤在同一条 `if` 里，而 `known_ids` 只列**此刻解锁**的那一班。
#   判据（现算，不硬编码技能名）：逐职业挑本门**等级最高**那一条（低级别一定没到）⇒ 必须
#   逐字回 `SYS_SKILL_TOO_LOW`（点名到几级）；三条反证钉「门一条没松」：别人门的技能照旧
#   `COMBAT_SKILL_BAD` · 域里没这个名字照旧 `COMBAT_SKILL_BAD` · 够等级的那一条照旧放得出来。
_TX10 = st.domain("texts") or {}
_BAD10 = _TX10["COMBAT_SKILL_BAD"]["value"]
_LOW10, _NOTMINE10, _NONE10, _UP10 = [], [], [], []
_NC10 = 0                                               # 真跑过的职业数（报数用）
for _c10 in _CLS8:
    _mine10 = sorted((int(v.get("lv") or 1), k, v) for k, v in _OWN.items()
                     if v.get("owner_class") == _c10 and v.get("kind_key") != "passive")
    if not _mine10:
        continue
    _NC10 += 1
    _lv10, _id10, _rec10 = _mine10[-1]                 # 本门等级最高那一条
    _low_pl = {"cls": _c10, "level": 1, "race": "human", "hp": 300, "bag": {},
               "equipped": {}, "flags": {}, "codex": {}}
    _got10 = _drive8(_CBL8.skill_cast, _low_pl, "技能 %s" % _rec10.get("name"))
    _want10 = (_TX10["SYS_SKILL_TOO_LOW"]["value"]
               .replace("{name}", str(_rec10.get("name")))
               .replace("{lv}", str(_lv10)).replace("{gap}", str(_lv10 - 1)))
    if _got10 != [_want10]:
        _LOW10.append((_c10, _rec10.get("name"), _lv10, _got10[:1], _want10))
    # 反证① 别人门的（等级也没到）：owner 那一关在前 ⇒ 照旧「放不出来」
    _other10 = sorted((int(v.get("lv") or 1), k, v) for k, v in _OWN.items()
                      if v.get("owner_class") and v.get("owner_class") != _c10
                      and v.get("kind_key") != "passive")
    if _other10:
        _o10 = _other10[-1][2]
        _g10 = _drive8(_CBL8.skill_cast, _low_pl, "技能 %s" % _o10.get("name"))
        if _g10 != [_BAD10.replace("{name}", str(_o10.get("name")))]:
            _NOTMINE10.append((_c10, _o10.get("name"), _g10[:1]))
    # 反证③ 够等级的那一条（本门最低等级那条 + 够那个级）照旧放得出来
    _lv_a, _id_a, _rec_a = _mine10[0]
    _ok_pl = dict(_low_pl)
    _ok_pl["level"] = _lv_a
    _g10a = _drive8(_CBL8.skill_cast, _ok_pl, "技能 %s" % _rec_a.get("name"))
    if not _g10a or _g10a[0] in (_BAD10.replace("{name}", str(_rec_a.get("name"))),
                                 _want10):
        _UP10.append((_c10, _rec_a.get("name"), _lv_a, _g10a[:1]))
# 反证② 域里没有这个名字 ⇒ 照旧「放不出来」
_g10n = _drive8(_CBL8.skill_cast, {"cls": "cls_knight", "level": 16, "race": "human",
                                   "hp": 300, "bag": {}, "equipped": {}, "flags": {},
                                   "codex": {}}, "技能 没有这条技能")
_NONE10 = [] if _g10n == [_BAD10.replace("{name}", "没有这条技能")] else _g10n[:2]

chk("★ 逐职业：敲「等级没到」那一条 ⇒ 回 `SYS_SKILL_TOO_LOW`（点名到几级），"
    "不再落成「这一手你放不出来」（%d 职业）" % _NC10, not _LOW10,
    "%s" % (_LOW10[:2],))
chk("★ 反证①：别人门的技能（等级也没到）照旧「放不出来」—— owner 那一关没松",
    not _NOTMINE10, "%s" % (_NOTMINE10[:2],))
chk("★ 反证②：域里没有这个名字 ⇒ 照旧「放不出来」", not _NONE10, "%s" % (_NONE10,))
chk("★ 反证③：够等级的那一条照旧放得出来（不是把技能一律拦了）", not _UP10,
    "%s" % (_UP10[:2],))

print()
print("结论：", "全过 ✅" if ok else "有红 ❌")
sys.exit(0 if ok else 1)
