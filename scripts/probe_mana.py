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

import ast
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
# ★ 键名从表里现取（不再两段拼 —— 守卫与被守卫对拼=语义抵消，审计 L1420）
_K_EVERY = [k for k in _REG if "every" in k][0]
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
# ─────────────────────────────────────────────────────────────────────────
# ② 静态守卫（2026-09-29 审计 L1420 重做 · 门禁可信度维度）
#   旧口径（`:106` 一行）：`_K_EVERY in _t` / `"0.05" in _t` / `re.search(回蓝率…)`
#   —— 实测**七种写法里只抓得住两种**（`every = 20` / `_EVERY = 20` / `regen_ticks = 20` /
#   字面键值对 / 拼串两段拼键名 全部漏过），而它自称守的是「回复率只许在 mana.json」。
#   更要命的是探针自己用**同一串拼法**造 `_K_EVERY` —— 守卫与被守卫在做同一件见不得光的
#   事（双方对拼 ⇒ 语义抵消）；真 `content/mana.py` 也是这么拼的（它要躲开这条守卫）
#   ⇒ 这条判据在自己盯着的那个文件上就是恒真的同义反复。
#   新口径 = AST，**一个键名都不拼**：
#     A 键名层：任何**能折成字符串的常量**（含两段拼接）命中
#       **从 `mana.json` 现取的键名族** ⇒ 红。
#     B 数值层：绑到 regen/mana 概念名上的数字字面量，取值等于**表里现取的真值** ⇒ 红。
#     C 单一主源层：那两个键名只许在 `content/mana.py` 定义一次。
#   键名族与真值**一律从表里现取**（`_REG`）⇒ 探针不参与对拼，改表即自动跟着走。
# ─────────────────────────────────────────────────────────────────────────
_REG_KEYS = [k for k in _REG]                       # 现取（不硬编码）
_REG_VALS = {k: v for k, v in _REG.items()          # 现取：键 → 表里的真值
             if isinstance(v, (int, float)) and not isinstance(v, bool)}


def _all_keys(obj, acc):
    if isinstance(obj, dict):
        for k, v in obj.items():
            acc.add(k)
            _all_keys(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _all_keys(v, acc)
    return acc


def _keys_of_file(path):
    try:
        return _all_keys(json.loads(io.open(path, encoding="utf-8").read()), set())
    except Exception:
        return set()


# 键名族 = regen 那两格里**只有 mana.json 自己有**的那些。
# 共用词（如 `amount` 同时在 resources.json / battle_text.json 里当键名）不算「法力独有」，
# 拿它当守卫词 = 把别的域也误判进来（实测 resources.py:343 就被这样打红过）。
_RULES_DIR = os.path.join(REPO, "content", "rules")
_OWN_KEYS = [k for k in _REG_KEYS
             if not any(k in _keys_of_file(os.path.join(_RULES_DIR, f))
                        for f in os.listdir(_RULES_DIR)
                        if f.endswith(".json") and f != "mana.json")]
if not _OWN_KEYS:                                   # 表把两格都改成共用词 ⇒ 守卫无从判起
    _OWN_KEYS = list(_REG_KEYS)
_TOKENS = {"regen", "mana", "mp"}                   # 概念名族（键名派生的在下面并入）
for _k in _REG_KEYS:
    _TOKENS.add(_k.lower())
    _TOKENS.update(p for p in re.split(r"[^0-9A-Za-z]+", _k) if len(p) >= 3)
_NAME_RE = re.compile("|".join(sorted(_TOKENS)), re.IGNORECASE)
_DOCS = set()          # docstring 的 ast.Constant 节点 id —— 叙述给人读，不是取值


def _fold(node):
    """这个节点能折出的全部字符串常量（含 `"a" + "b"` 两段拼接）。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = _fold(node.left), _fold(node.right)
        if a is None or b is None:
            return None
        return {x + y for x in a for y in b}
    return None


def _names_of(node):
    out = [t.id for t in getattr(node, "targets", []) or [] if isinstance(t, ast.Name)]
    tg = getattr(node, "target", None)
    if isinstance(tg, ast.Name):
        out.append(tg.id)
    return out


_num_hit, _def_site, _raw_hit = [], [], []
for _root, _dirs, _files in os.walk(os.path.join(REPO, "content")):
    _dirs[:] = [d for d in _dirs if d != "__pycache__"]
    for _f in sorted(_files):
        if not _f.endswith(".py"):
            continue
        _path = os.path.join(_root, _f)
        _rel = os.path.relpath(_path, REPO).replace(os.sep, "/")
        _tree = ast.parse(io.open(_path, encoding="utf-8").read(), _path)
        _DOCS.clear()
        for _n in ast.walk(_tree):
            _body = getattr(_n, "body", None)
            if isinstance(_body, list) and _body and isinstance(_body[0], ast.Expr)                     and isinstance(_body[0].value, ast.Constant)                     and isinstance(_body[0].value.value, str):
                _DOCS.add(id(_body[0].value))
        for _n in ast.walk(_tree):
            if id(_n) in _DOCS:                       # docstring 不算「取值」
                continue
            for _s in _fold(_n) or ():
                for _k in _OWN_KEYS:
                    if _k in _s and len(_s) <= 64:     # 只抓「就是个键名」的短串
                        _raw_hit.append((_rel, _n.lineno, _s))
            if isinstance(_n, (ast.Assign, ast.AnnAssign)):
                _names = _names_of(_n)
                _val = getattr(_n, "value", None)
                if _names and _val is not None and any(_NAME_RE.search(x) for x in _names):
                    for _sub in ast.walk(_val):
                        if isinstance(_sub, ast.Constant) and isinstance(_sub.value, (int, float))                                 and not isinstance(_sub.value, bool):
                            for _k, _v in _REG_VALS.items():
                                if _sub.value == _v:
                                    _num_hit.append("%s:%d %s=%r（= 表里 %s）"
                                                    % (_rel, _sub.lineno, _names[0], _sub.value, _k))
                for _s in _fold(_val) or ():
                    if _s in _OWN_KEYS and _names:
                        _def_site.append((_rel, _n.lineno, "%s = %r" % (_names[0], _s)))

# 绑定点（`_K_EVERY = "every" + "_ticks"` 这**唯一合法**的拼写处）本身不算违规；
# 违规的是「在绑定点之外又拼了一次」—— 例如另一个文件自己也去读那一格。
_def_pos = {(r, ln) for (r, ln, _) in _def_site}
_key_hit = ["%s:%d %r" % (r, ln, s) for (r, ln, s) in _raw_hit if (r, ln) not in _def_pos]
_offsite = ["%s:%d %s" % t for t in _def_site if t[0] != "content/mana.py"]
chk("★ ②-A 键名层（AST · 键名族从 mana.json 现取、且只取法力**独有**的那几格）：`content/*.py` 里不落它"
    "（两段拼接出来的键名一并抓 —— 那是对拼写法）", not _key_hit, "; ".join(_key_hit[:6]))
chk("★ ②-B 数值层（AST · 真值从 mana.json 现取）：回复率那两个数不落进 `content/*.py`"
    "（`every = 20` / `_EVERY = 20` / `regen_ticks = 20` / 字面键值对 四种旧写法全抓）",
    not _num_hit, "; ".join(_num_hit[:6]))
chk("★ ②-C 单一主源层：法力独有那几个键名**全树恰好一个拼写点**，且在 `content/mana.py`"
    "（别处再抄一份 = 表与代码分叉；抄零份 = `every_of()` 读不到那一格）",
    not _offsite and len(_def_site) == len(_OWN_KEYS),
    "拼写点 %d 个（应 %d 个，各对应一格）· 外面的：%s"
    % (len(_def_site), len(_OWN_KEYS), "; ".join(_offsite[:4]) or "无"))
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


def _usable(mo, mp_need=None, _info=None):
    b = CB.build(_pl("cls_mage", 10, mo), ["syn_bag"], _MONS, uid="u_gate")
    a = b.sides[CB.PLAYER_SIDE][0]
    logs = []
    got = ACT._skill_usable(b, a, _info or {}, logs)
    # ★ P0-1 续批六（2026-09-29 · aep0）：返回当时那个战斗钟。期望值与实得值
    #   同源（同一个式子现算，不手写一个数）—— 否则改了刻源这条判据
    #   会静默变红。取法与生产 content/mana.py::gate_line 逐字同形。
    return got, [str(x) for x in logs], float(getattr(b, "_now", 0.0) or 0.0)


def _gate_line(rv, cur, t):
    """那一句的期望值——现渲染，不手拼字面量。"""
    return str(_slot_rec.get("value")).format(rv=float(rv), cur=float(cur), t=float(t))


_ok_no, _logs_no, _t_no = _usable(0, _info=_info)
_want_line = _gate_line(_need, 0, _t_no)
_ok_yes, _logs_yes, _t_yes = _usable(max(1, _need), _info=_info)
chk("★ ⑤ 蓝不够 ⇒ **拦下**：`_skill_usable` 回 False，那一句逐字 = 槽位 `%s` 渲染（「%s」）"
    % (_GATE.get("slot"), _want_line),
    bool(_vs) and _ok_no is False and _want_line in _logs_no,
    "实得：%s" % str(_logs_no[:2])[:90])
# ★ P0-1 续批六（2026-09-29 · 文案修复车道 aep0）：那一句进**持久战斗日志**。
#   引擎 `extends/ext_combat/battle/actions.py::_mp_gate_text` 把内容侧回执展开后 `logs.extend(_say)`，
#   而 `logs` 就是那张落档的日志表 ⇒ 与那 37 格带刻的同一面。
#   真源 `26_§三 优化 1` 逐字「所有战斗日志行统一以【N 刻】开头」。
#   取件 = **本条真跑出来那一行**（`_logs_no`），不是模板串 → 改模板但读端没接刻也会红。
import re as _re6
_STAMP6 = _re6.compile(r"^⚡【(\d+) 刻】")
_m6 = _STAMP6.match(_logs_no[0]) if _logs_no else None
chk("★ ⑤-b 法力门槛那一句进持久战斗日志 ⇒ 行首带【N 刻】（真源 26_ §三 优化 1）  —— 屏=%r"
    % (_logs_no[0] if _logs_no else None,),
    _m6 is not None and int(_m6.group(1)) == int(round(_t_no)),
    "实得：%s" % str(_logs_no[:1])[:90])
# 反证：把模板换回不带刻的旧值 ⇒ 上面那条必红（不许变成永远绿的附幕）。
_bad6 = "⚡ 法力不够 —— 这一手要 {rv:.0f} 点，你现在只有 {cur:.0f} 点。".format(
    rv=float(_need), cur=0.0)
chk("★ ⑤-c 反证：旧写法（无【N 刻】）不满足上面那条判据  —— %r" % _bad6,
    _STAMP6.match(_bad6) is None)

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
    _ok2, _l2, _t2 = _usable(_n2 - 1, _info=_i2)
    chk("★ ⑤ 门槛线是**这一手自己**的耗法：换一条 %s 点的技、给 %s 点 ⇒ 拦下那一句里的数 = %s"
        % (_n2, _n2 - 1, _n2),
        _ok2 is False and _gate_line(_n2, _n2 - 1, _t2) in _l2,
        "实得：%s" % str(_l2[:2])[:90])
_plain = next(((_s, _r) for _s, _r in sorted((st.domain("skills") or {}).items())
               if not str(_s).startswith("_") and _r.get("owner_class") == "cls_mage"
               and _r.get("kind_key") != "passive" and int(_r.get("mp") or 0) == 0
               and int(_r.get("lv") or 1) <= 10), None)
if _plain:
    _i3 = dict(SL.skill_info("cls_mage", _plain[0]) or {})
    _i3.setdefault("name", _plain[1].get("name") or _plain[0])
    _ok3, _l3, _t3 = _usable(0, _info=_i3)
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
    _ok_off, _l_off, _t_off = _usable(0)
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

# ══════════════════════════════════════════════════════════════════════
# ⑨ 战斗内已结过的那一段，结算口不许再结一遍（审计 L1410-1）
# ══════════════════════════════════════════════════════════════════════
# 机制：战斗内那笔回蓝走**战斗钟**（引擎 `battle._now`）· 结算口走**游戏钟**（墙上钟）——
#       两把尺不是同一把（游戏内 1 天 = 现实 2 小时 ⇒ 墙钟被放大约 12 倍成游戏刻）。
#       修法 = 结算口**只结到开战刻**、书签也落在开战刻 ⇒ 两笔各结各的那一段。
#   ★ 判据把游戏钟做成**可控的**（`settle` 走 `game_tick()`，猴补它在发币那一格），
#     于是「这一场占了多少游戏刻」可以手摆 —— 不然测的是墙钟（固定时钟）碰巧的取值。
#   ★ 打**公开口 `settle`**（三格那个），不打在自己新抽的 `battle_start_tick` 上
#     （本车道第 32 轮踩过：助手正确 ≠ 调用点正确）。
_real_gt9 = MANA.game_tick
_CLOCK9 = {"now": 0}
MANA.game_tick = lambda: float(_CLOCK9["now"])

# ★ 这一组要**三格** `settle`（第三格 = 开战刻）。产品码退回两格时：把整组判红并说清缺哪一格，
#   而不是让判据自己崩在 TypeError 上（崩掉看不出是哪一条红，也会被当成「环境问题」）。
try:
    MANA.settle({}, 0, 0.0)
    _3ARG = True
except TypeError:
    _3ARG = False
if not _3ARG:
    chk("★ ⑨ 结算口必须收「开战刻」那一格（三格 settle）—— 现在只有两格 ⇒ 战斗内已结过的那一段会再结一遍",
        False, "settle() 不接第三格（审计 L1410-1 未落地）")


def _seg9(battle_ground_ticks, after_ticks):
    """造一档真战斗，算出「[书签, 开战刻]」这一段结算口该结几点 / 落档现蓝。
    返回 (结算口回了几点, 落档现蓝, 开战刻, 战斗内回了多少)。"""
    _CLOCK9["now"] = 0
    _d = {"mo_max": 10 ** 6, "mo": 0, MANA.settle_stamp(): 0}      # 上一笔结在 0 刻
    _CLOCK9["now"] = battle_ground_ticks                            # 战斗外先走这么多刻
    _b = CB.build(_pl(cls="cls_mage", level=10, mo=0, uid="u_mana"), ["syn_bag"], _MONS, uid="u_mana")
    for _ in range(8):
        SCH.advance(_b, [])
        _c = _b.focus()
        if _c is None or _b.result is not None:
            break
        _b.human_act("defend", None, _c)
    _a = _b.focus()
    _inner = int(_a.get("mp") or 0) if _a else 0
    _start = _a.get("_mp_game_at")                                  # 开战刻（战斗内第一拍落的）
    _CLOCK9["now"] = battle_ground_ticks + after_ticks              # 收尾那一刻（战斗已打过 after 刻墙钟）
    _g = MANA.settle(_d, _inner, _start)
    return _g, int(_d.get(MANA.settle_field()) or 0), _start, _inner


if _3ARG:
  try:
    # 期望口径**现算**：战斗外那一段 = [0, 开战刻]（书签落在 0、开战刻 = battle_ground_ticks）
    # ⇒ 应结 floor(battle_ground_ticks / every) 点。战斗内那几刻**不归结算口**。
    _g9, _m9, _s9, _i9 = _seg9(1000, 200)
    _want9 = int(1000 // _EVERY)
    chk("⑨-a 真战斗 + 真场：拿得到开战刻，战斗内回 %s 点、结算口结 %s 点" % (_i9, _g9),
        _s9 is not None and _g9 >= 0, "开战刻 %s" % (_s9,))
    chk("⑨-b ★ 战斗内那一段不许再结一遍：战斗外 %s 刻 ⇒ 结算口**只**结 floor(%s/%s)=%s 点（旧口径会结 %s 点）"
        % (1000, 1000, _EVERY, _want9, int((1000 + 200) // _EVERY)),
        _g9 == _want9, "实得 %s" % (_g9,))
    # 撤改验证：第三格不传 = 旧口径 ⇒ 同输入**确实**多结
    _CLOCK9["now"] = 0
    _d_old = {"mo_max": 10 ** 6, "mo": 0, MANA.settle_stamp(): 0}
    _CLOCK9["now"] = 1200
    _gold = MANA.settle(_d_old, 0)
    chk("⑨-c ★ 撤改验证：第三格不传（回到旧口径）⇒ 同一份输入确实多结 %s 点（%s → %s）"
        % (_gold - _want9, _want9, _gold), _gold > _want9)
    # 书签落**开战刻**（不是「现在」）⇒ 战斗内那 200 刻不结、也不吞掉
    _CLOCK9["now"] = 0
    _d_bm = {"mo_max": 10 ** 6, "mo": 0, MANA.settle_stamp(): 0}
    _CLOCK9["now"] = 1000
    _b2 = CB.build(_pl(cls="cls_mage", level=10, mo=0, uid="u_mana"), ["syn_bag"], _MONS, uid="u_mana")
    for _ in range(8):
        SCH.advance(_b2, [])
        _c2 = _b2.focus()
        if _c2 is None or _b2.result is not None:
            break
        _b2.human_act("defend", None, _c2)
    _a2 = _b2.focus()
    _s2 = _a2.get("_mp_game_at")
    _CLOCK9["now"] = 1200
    MANA.settle(_d_bm, int(_a2.get("mp") or 0), _s2)
    chk("⑨-d 书签落在**开战刻**（%s）而不是「现在」（1200）—— 战斗内那 200 刻不结、也不被吞掉"
        % (_d_bm.get(MANA.settle_stamp()),),
        _s2 is not None and _d_bm.get(MANA.settle_stamp()) == _s2)
    # ⑨-e ★ 那 200 刻不许**被吞掉**（书签落开战刻只是「挪后」，不是「丢掉」）：
    #   再结一次账（模拟下一场收尾），这 200 刻 + 后面的 200 刻要**整块**结出来。
    _CLOCK9["now"] = 1400
    _g9b = MANA.settle(_d_bm, 0)
    _want9b = int(400 // _EVERY)
    chk("⑨-e ★ 战斗内挪后的那 200 刻**没被吞掉**：再结一次账 ⇒ [开战刻, 1400] 共 400 刻结 %s 点"
        % (_g9b,), _g9b == _want9b, "现算 floor(400/%s)=%s" % (_EVERY, _want9b))
  finally:
    MANA.game_tick = _real_gt9
else:
    MANA.game_tick = _real_gt9

print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
