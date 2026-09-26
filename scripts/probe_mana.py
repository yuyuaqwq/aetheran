# -*- coding: utf-8 -*-
"""探针：法力渠道（P-51）—— 回蓝率 / 蓝门槛 / 起手，**逐条现算**。

判据（每条都现算，不抄镜像表）
------------------------------------------------------------------
① 口径表 == 真源**现解析**：`03_职业与技能/04_法师_v2.md` §二 的回蓝率（每刻多少点）
   × `02_数值宪法/01_属性字典与基础公式.md` §一「1 刻 = 1 秒」⇒ 每多少刻回 1 点。
   （两个数从文档现取；文档改了、或表被手改 ⇒ 这条当场红。）
② 单一来源（静态守卫）：那两个数 / 那两个键名只许在 `content/rules/mana.json` 里；
   `content/*.py` 里自己算回复率的写法 ⇒ 红。拦下那句话用的槽位必须在 texts 域里、
   且它声明的两格参数（`rv` / `cur`）喂得进。
③ 真跑基础回复：真战斗 + 真时钟推进 —— 蓝只涨不跌、每 N 刻 +1、**一次结算跨过几个 N
   就整块回几点**（只回 1 点 = 把「按刻的慢回」变成「1 点/次行动」，差 5 倍）、涨到上限就停。
④ 起手：档上**有**现蓝那一格 ⇒ 照它（钳到上限）；**缺格** ⇒ 面板上限满池 ——
   且面板 / 档（`cmds_ast._p`）/ actor 三处同一个数（同一口 `mana.initial_mp`）。
⑤ 门槛两态（引擎**真读**那个钩子）：不够 ⇒ 拦下（`_skill_usable` 回 False + 那一句逐字
   = texts 槽位渲染 · 含两个现算的数）· 够 ⇒ 放行；需要 0 点的技（普攻）**永不拦**。
⑥ 范围：池子为 0 的职业（狂战士）与怪 actor —— 不回、不写书签、不出话。
⑦ 反证（未装配 = 接线前）：把两个 hook 从引擎 config 卸掉 ⇒ 0 蓝**照样放得出来**
   （这就是 P-51 之前「耗法 = 空账」的现状）。
⑧ 撤改验证：把回复率改坏（N → N+1）⇒ ③ 那条账当场红。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_mana.py
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
PLAN = os.environ.get("AST_PLAN", "C:/Users/yuyu/aetheran-plan")
sys.path.insert(0, ENGINE)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))

from saintess_engine.package import load_stack                       # noqa: E402

_FIXED = 1790308800            # 2026-09-25 12:00 +08:00（与 probe_combat / probe_cmds 同一口径）
ok = True


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"),
                                                          "Temp", "ast_probe.db"),
                                   "clock": lambda: _FIXED})
st.install()

MANA = st.optional_submodule("mana") or __import__("content.mana", fromlist=["x"])
CB = st.optional_submodule("combat")
PB = st.optional_submodule("panel_build")
TXT = st.domain("texts") or {}
from ext_combat.battle import actions as ACT                        # noqa: E402
from ext_combat.battle import schedule as SCH                       # noqa: E402
from saintess_engine import config as CFG                           # noqa: E402
from content import cmds_ast as CA                                  # noqa: E402
from content import skills_lookup as SL                             # noqa: E402

_RULES = os.path.join(REPO, "content", "rules", "mana.json")
_TBL = json.loads(io.open(_RULES, encoding="utf-8").read())
_REG = dict(_TBL.get("regen") or {})
_GATE = dict(_TBL.get("gate") or {})
_K_EVERY = "every" + "_ticks"                                       # 守卫要求：content/*.py 里不落字面量
_EVERY = int(_REG[_K_EVERY])
_AMOUNT = int(_REG["amount"])

print("探针：法力渠道（P-51 · content/rules/mana.json → content/mana.py → 引擎两个钩子）")

# ══════════════════════════════════════════════════════════════
# ① 口径表 == 真源现解析
# ══════════════════════════════════════════════════════════════
_DOC_M = os.path.join(PLAN, "03_职业与技能", "04_法师_v2.md")
_DOC_U = os.path.join(PLAN, "02_数值宪法", "01_属性字典与基础公式.md")
_DM = io.open(_DOC_M, encoding="utf-8").read() if os.path.exists(_DOC_M) else ""
_DU = io.open(_DOC_U, encoding="utf-8").read() if os.path.exists(_DOC_U) else ""
_m = re.search(r"回蓝\s+\*{0,2}([\d.]+)\s*/\s*刻", _DM)
_rate = float(_m.group(1)) if _m else None
_want_every = int(round(1.0 / _rate)) if _rate else None
_sec = bool(re.search(r"1 刻 = 1 秒", _DU))
chk("★ ① 真源现解析：`04_法师_v2 §二` 回蓝 %s/刻 × `01_属性字典 §一`「1 刻 = 1 秒」"
    "⇒ 每 **%s** 刻回 1 点 == 表里那一格 = %s（每次 1 点）"
    % (_rate, _want_every, _EVERY),
    _rate is not None and _sec and _want_every == _EVERY and _AMOUNT == 1,
    "文档窗口：%s" % (_m.group(0) if _m else "（没解析出「回蓝 N/刻」）"))
print("     · 换算成玩家看得见的话：一次行动 ≈ 95–100 刻 ⇒ 自然回 ≈ %.1f 点/次行动"
      % (95.0 / _EVERY))

# ══════════════════════════════════════════════════════════════
# ② 单一来源（静态守卫）+ 回话槽位
# ══════════════════════════════════════════════════════════════
_bad_src = []
for _root, _dirs, _files in os.walk(os.path.join(REPO, "content")):
    _dirs[:] = [d for d in _dirs if d != "__pycache__"]
    for _f in _files:
        if not _f.endswith(".py"):
            continue
        _t = io.open(os.path.join(_root, _f), encoding="utf-8").read()
        _hit = (_K_EVERY in _t) or ("0.05" in _t) or bool(re.search(r"回蓝率?\s*[:=]\s*[\d.]", _t))
        if _hit:
            _bad_src.append(_f)
chk("★ ② 静态守卫：回复率那两个数 / 键名只许在 `content/rules/mana.json`"
    "（`content/*.py` 里自己算回复率的写法 ⇒ 红）", not _bad_src, "%s" % _bad_src)
_slot_rec = TXT.get(str(_GATE.get("slot") or "")) or {}
chk("★ ② 拦下那句话用的**已有槽位** `%s` 真在 texts 域里，且声明的两格参数都在（`rv` / `cur` 喂得进）"
    % _GATE.get("slot"),
    bool(_slot_rec) and {"rv", "cur"} <= set(_slot_rec.get("params") or [])
    and "{rv" in str(_slot_rec.get("value")) and "{cur" in str(_slot_rec.get("value")))

# ══════════════════════════════════════════════════════════════
# 木桩（血厚 · 打不痛）：让时钟真走，蓝的账只看这一条
# ══════════════════════════════════════════════════════════════
_BAG = {"name": "木桩", "icon": "🪵", "archetype": "杂兵", "role": "普通", "role_key": "normal",
        "lv": 10, "habitat": {"maps": [CA.TOWN], "nodes": ["wt_gate_n"]},
        "panel": {"hp": 10 ** 7, "atk": 1, "def": 0, "res": 0, "spd": 50, "hit": 1, "eva": 0, "crit": 0},
        "elite_pool": []}
_MONS = {"syn_bag": _BAG}


def _pl(cls="cls_knight", level=10, mo=0, uid="u_mana"):
    p = {"cls": cls, "level": level, "uid": uid, "name": "试炼者", "alloc": {},
         "hp": 10 ** 6, "bag": {}, "flags": {}}
    p["hp"] = CA.hp_cap(p)
    if mo is not None:
        p["mo"] = mo
    return p


def _walk(cls="cls_knight", level=10, mo=0, steps=36):
    """真战斗 + 真时钟：每走一步记 (now, 蓝)。玩家每步『防御』（不耗法）⇒ 蓝只涨不跌。"""
    b = CB.build(_pl(cls, level, mo), ["syn_bag"], _MONS, uid="u_mana")
    a = b.focus()
    tr = [(0.0, int(a.get("mp") or 0))]
    for _ in range(steps):
        SCH.advance(b, [])
        c = b.focus()
        if c is None or b.result is not None:
            break
        tr.append((round(float(b._now), 3), int(c.get("mp") or 0)))
        b.human_act("defend", None, c)
    return b, tr


_b, _tr = _walk()
_cap = int(_b.focus().get("max_mp") or 0) if _b.focus() else 0
_t0 = _tr[1][0] if len(_tr) > 1 else 0.0            # 第一次结算那一刻（书签落这儿）
_later = [(t, m) for t, m in _tr if t > _t0]
_want_last = min(_cap, int((_later[-1][0] - _t0) // _EVERY)) if _later else 0
_mono = all(_tr[i][1] <= _tr[i + 1][1] for i in range(len(_tr) - 1))
#: 跨步整块结账：相邻两个结算点之间涨的点数 == floor((t2-t0)/N) - floor((t1-t0)/N)（现算）
_gaps_bad = []
for i in range(1, len(_later) - 1):
    _want = min(_cap, int((_later[i + 1][0] - _t0) // _EVERY)) - min(_cap, int((_later[i][0] - _t0) // _EVERY))
    if _later[i + 1][1] - _later[i][1] != _want:
        _gaps_bad.append((_later[i][0], _later[i + 1][0], _later[i + 1][1] - _later[i][1], _want))
chk("★ ③ 真跑基础回复：蓝只涨不跌 · 每 %s 刻 +1 · **一次结算跨过几个 %s 就整块回几点**"
    "（逐步现算对账）· 走到 %s 刻时 = **%s**（现算 %s）· 上限 %s"
    % (_EVERY, _EVERY, _later[-1][0] if _later else "-", _tr[-1][1], _want_last, _cap),
    bool(_later) and _mono and _tr[-1][1] == _want_last and not _gaps_bad,
    "逐步偏差：%s" % (_gaps_bad[:3] or "无"))
_jump_max = max((_later[i + 1][1] - _later[i][1]) for i in range(len(_later) - 1)) if len(_later) > 1 else 0
chk("★ ③ 反面（防「每拍只回 1 点」）：这一步里最大的单次回复 = %s 点 > 1（一步 ≈ 一次行动的刻数）"
    % _jump_max, _jump_max > 1)

# ══════════════════════════════════════════════════════════════
# ④ 起手：档上有 ⇒ 照它 · 缺格 ⇒ 满 · 三处一个数（同一口）
# ══════════════════════════════════════════════════════════════
_b_full = CB.build(_pl("cls_knight", 10, None), ["syn_bag"], _MONS, uid="u_full")
_a_full = _b_full.focus()
chk("★ ④ 档上**缺** `mo` 那一格 ⇒ 起手满池（%s / 上限 %s）—— 口径 `initial.mode` = %s"
    % (int(_a_full.get("mp") or 0), int(_a_full.get("max_mp") or 0), MANA.initial_mode()),
    int(_a_full.get("mp") or 0) == int(_a_full.get("max_mp") or 0) > 0)
_b_seven = CB.build(_pl("cls_knight", 10, 7), ["syn_bag"], _MONS, uid="u_seven")
chk("★ ④ 档上**有**那一格（7）⇒ 起手就是 7（不被「满池」盖掉）· 上限仍是面板那一个（%s）"
    % int(_b_seven.focus().get("max_mp") or 0),
    int(_b_seven.focus().get("mp") or 0) == 7 and int(_b_seven.focus().get("max_mp") or 0) > 7)
_p3 = CA._p({"cls": "cls_knight", "level": 1})
_ma = CB.player_actor({"cls": "cls_knight", "level": 1})
_mp = PB.mp_cap({"cls": "cls_knight", "level": 1})
chk("★ ④ 面板 / 档（`_p`）/ actor 三处同一个数，且**缺格 ⇒ 满**（%s / %s / %s）"
    % (_mp, _p3.get("mo"), _ma.get("mp")),
    int(_mp) == int(_p3.get("mo") or 0) == int(_ma.get("mp") or 0) == int(_p3.get("mo_max") or 0) > 0)
_p_over = CA._p({"cls": "cls_knight", "level": 1, "mo": 9999})
chk("★ ④ 档上写超了 ⇒ 出档口按面板上限钳（9999 → %s）" % _p_over.get("mo"),
    int(_p_over.get("mo") or 0) == int(_p_over.get("mo_max") or -1) == int(_mp))

# ══════════════════════════════════════════════════════════════
# ⑤ 门槛两态（引擎真读那个钩子）
# ══════════════════════════════════════════════════════════════
_pick = None
for _sid, _rec in sorted((st.domain("skills") or {}).items()):
    if str(_sid).startswith("_") or _rec.get("owner_class") != "cls_mage":
        continue
    if _rec.get("kind_key") != "passive" and int(_rec.get("mp") or 0) > 0 and int(_rec.get("lv") or 1) <= 10:
        if _pick is None or int(_rec.get("mp") or 0) > int(_pick[1].get("mp") or 0):
            _pick = (_sid, _rec)
_vs, _vr = _pick if _pick else ("", {})
_need = int((_vr or {}).get("mp") or 0)
_info = dict(SL.skill_info("cls_mage", _vs) or {}) if _vs else {}
_info.setdefault("name", (_vr or {}).get("name") or _vs)
_want_line = str(_slot_rec.get("value")).format(rv=float(_need), cur=0.0)


def _usable(mo, mp_need=None, _info=None):
    b = CB.build(_pl("cls_mage", 10, mo), ["syn_bag"], _MONS, uid="u_gate")
    a = b.sides[CB.PLAYER_SIDE][0]
    logs = []
    got = ACT._skill_usable(b, a, _info or {}, logs)
    return got, [str(x) for x in logs]


_ok_no, _logs_no = _usable(0, _info=_info)
_ok_yes, _logs_yes = _usable(max(1, _need), _info=_info)
chk("★ ⑤ 蓝不够 ⇒ **拦下**：`_skill_usable` 回 False，那一句逐字 = 槽位 `%s` 渲染（「%s」）"
    % (_GATE.get("slot"), _want_line),
    bool(_vs) and _ok_no is False and _want_line in _logs_no,
    "实得：%s" % str(_logs_no[:2])[:90])
chk("★ ⑤ 蓝够（= 这一手的耗法 %s）⇒ **放行**（不拦、不出那句）" % _need,
    bool(_vs) and _ok_yes is True and not any(_GATE.get("slot") and _want_line in x for x in _logs_yes),
    "实得：%s" % str(_logs_yes[:2])[:90])
#: 门槛线 = **这一手自己**的耗法（不是某条全局常数）：换一条更贵的技，拦住的那一句里的数跟着变
_cheap = next(((_s, _r) for _s, _r in sorted((st.domain("skills") or {}).items())
               if not str(_s).startswith("_") and _r.get("owner_class") == "cls_mage"
               and _r.get("kind_key") != "passive" and 0 < int(_r.get("mp") or 0) < _need
               and int(_r.get("lv") or 1) <= 10), None)
if _cheap and _vs:
    _i2 = dict(SL.skill_info("cls_mage", _cheap[0]) or {})
    _i2.setdefault("name", _cheap[1].get("name") or _cheap[0])
    _n2 = int(_cheap[1].get("mp") or 0)
    _ok2, _l2 = _usable(_n2 - 1, _info=_i2)
    chk("★ ⑤ 门槛线是**这一手自己**的耗法：换一条 %s 点的技、给 %s 点 ⇒ 拦下那一句里的数 = %s"
        % (_n2, _n2 - 1, _n2),
        _ok2 is False and str(_slot_rec.get("value")).format(rv=float(_n2), cur=float(_n2 - 1)) in _l2,
        "实得：%s" % str(_l2[:2])[:90])
_plain = next(((_s, _r) for _s, _r in sorted((st.domain("skills") or {}).items())
               if not str(_s).startswith("_") and _r.get("owner_class") == "cls_mage"
               and _r.get("kind_key") != "passive" and int(_r.get("mp") or 0) == 0
               and int(_r.get("lv") or 1) <= 10), None)
if _plain:
    _i3 = dict(SL.skill_info("cls_mage", _plain[0]) or {})
    _i3.setdefault("name", _plain[1].get("name") or _plain[0])
    _ok3, _l3 = _usable(0, _info=_i3)
    chk("★ ⑤ 不耗法的一手（`%s` · mp 0）在 **0 蓝**时也放得出来（普攻那类永远不受蓝约束）"
        % _plain[1].get("name"), _ok3 is True and not _l3, "实得：%s" % str(_l3[:2])[:90])
else:
    chk("⑤ 找得到一条 mp=0 的本职业技能（找不到 ⇒ 这条测不了）", False)

# ══════════════════════════════════════════════════════════════
# ⑥ 范围：池子 0 的职业 / 怪 —— 都不吃这条渠道
# ══════════════════════════════════════════════════════════════
_bz = CB.build(_pl("cls_berserker", 10, None, uid="u_bz"), ["syn_bag"], _MONS, uid="u_bz")
_ba = _bz.focus()
SCH.advance(_bz, [])
SCH.advance(_bz, [])
chk("★ ⑥ 池子为 0 的职业（狂战士 · 上限 %s）不回蓝、不写书签、不出话 —— 它压根没有这条渠道"
    % _ba.get("max_mp"),
    int(_ba.get("max_mp") or 0) == 0 and "_mp_at" not in _ba and int(_ba.get("mp") or 0) == 0)
_bm = CB.monster_actor("syn_bag", _BAG)
chk("★ ⑥ 怪 actor 不参与（没有法力条）：书签不写、蓝不动 —— 这条渠道只管有池子的那些",
    MANA.regen_amount(_bz, _bm) is None and "_mp_at" not in _bm)

# ══════════════════════════════════════════════════════════════
# ⑦ 反证：未装配 = 与接线前逐字节相同（P-51 之前：耗法是空账）
# ══════════════════════════════════════════════════════════════
_saved = {k: CFG._HOOKS.get(k) for k in ("mp_regen_fn", "mp_gate_fn")}
try:
    CFG._HOOKS["mp_regen_fn"] = None
    CFG._HOOKS["mp_gate_fn"] = None
    _ok_off, _l_off = _usable(0)
    chk("★ ⑦ 反证：两个钩子卸掉 ⇒ **0 蓝照样放得出来**（= P-51 之前「耗法 = 空账」的现状），"
        "那句拦下的话一个字都不出现",
        _ok_off is True and not _l_off, "实得：%s" % str(_l_off[:2])[:90])
finally:
    for _k, _v in _saved.items():
        CFG._HOOKS[_k] = _v

# ══════════════════════════════════════════════════════════════
# ⑧ 撤改验证：把回复率改坏 ⇒ ③ 那条账当场红
# ══════════════════════════════════════════════════════════════
_save_t = json.loads(json.dumps(MANA._CACHE.get("t") or {}))
#: 撤改这一格要用**大池子 + 短几步**：骑士 lv10 池子只有 50，36 步早就撞顶
#: ⇒ 20 与 21 都算出「满」，分辨不出改坏（这一条自己踩过一次）。
def _expect(tr, every, cap):
    t0 = tr[1][0] if len(tr) > 1 else 0.0
    later = [(t, m) for t, m in tr if t > t0]
    return min(int(cap), int((later[-1][0] - t0) // every)) if later else 0


_b3, _tr3 = _walk(cls="cls_mage", level=10, mo=0, steps=8)
_cap3 = int(_b3.focus().get("max_mp") or 0)
_want3 = _expect(_tr3, _EVERY, _cap3)
try:
    MANA._CACHE["t"]["regen"][_K_EVERY] = _EVERY + 1
    _b4, _tr4 = _walk(cls="cls_mage", level=10, mo=0, steps=8)
    _want4 = _expect(_tr4, _EVERY + 1, _cap3)
    chk("★ ⑧ 撤改验证：回复率 %s → %s ⇒ 同一条账**当场对不上**（法师 lv10 池 %s · 8 步走到 %s 刻："
        "按 %s 刻算 = %s、按 %s 刻算 = %s —— 实得 %s / %s）"
        % (_EVERY, _EVERY + 1, _cap3, _tr3[-1][0], _EVERY, _want3, _EVERY + 1, _want4,
           _tr3[-1][1], _tr4[-1][1]),
        _want3 > 0 and _want4 > 0 and _want3 != _want4
        and _tr3[-1][1] == _want3 and _tr4[-1][1] == _want4,
        "阈值 %s / 改坏后 %s" % (_want3, _want4))
finally:
    MANA._CACHE["t"] = _save_t

print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
