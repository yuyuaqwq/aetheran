# -*- coding: utf-8 -*-
"""探针：**探索遇怪**（fxexp · 第 53 支）—— 新指令 `探索` · 遇怪率那一根真轴 · 死槽位解冻。

为什么有这一支
------------------------------------------------------------------
真源 `00_总纲/03_主要玩法.md` 写着「路上：**遇怪**、看见能捡的东西…」，而
`AETHERAN_推进进度.md` P-16 登记「现在遇敌是敲指令打的（`pick_encounter` 由指令触发），
**没有遇见率**」⇒ 世界事件里「遇敌率 / 出现率翻倍」那一类效果**没有消费端**；
`SYS_LOOK_FOE_ROW`（观察那栏的普通怪行）也一直**没有读端**（死槽位）。

本支把设计案《fxexp · 「探索遇怪」字段级设计案》（车道 `_notes.md` 末节）逐条钉住：

判据（只许加强）
------------------------------------------------------------------
  ① 声明与路由：`探索`（别名 探 / 走一圈）→ `explore`；分类与 `观察` 同格 · guard 随时 ·
     不可见声明不抢；**反证**：把这一条摘掉 ⇒ 那三个词没有任何声明接得住（不是借别人的）
  ② 表 = 设计案那几个数（base 五档 / 等级差五档 / 时辰 / 天气 / 事件 / cap / 档位映射
     逐字相等）；**每个节点都落得到档**（覆盖面）
  ③ 单源（静态）：概率数字只在 `rules/explore_encounter.json` 里 —— `content/explore.py`
     与 `cmds_ast.explore` 的 **AST 里一个设计数字都没有**；那张表只有 `explore.py` 打开
  ④ 纯函数逐项可复算：base × 等级差 × 时辰 × 天气 × 事件 × cap（探针按设计案的数**另算一份**
     —— 两处独立对账），五个因子各翻一次面
  ⑤ **四态①  掷中**（固定种子真敲）：开场那一屏 = 「遭遇 + 这一手」，且**两只名字逐字相同**
     （= 同一次抽）；精英那一档也核（名字带 `† … †`）；结算那几行与『攻击』同一套
  ⑥ **四态②  掷空**（威慑档 = 真 0）：出拾取提示 / `SYS_EXPLORE_CLEAR`，且**不建场、不动档**
  ⑦ **四态③  持态**（场在跑）：`探索` 被拦下，回的那一句与移动族**逐字同一句**
  ⑧ **四态④  可读**：`观察` 的普通怪行 = 『攻击』真开的那一只（同一次抽 · 一次命令只抽一次）。
     钉子下在**候选 ≥ 3 的站**（一只候选的站分不出「就是那一只」与「候选名单」），
     并连精英那条口一起钉 —— 判据是「紧跟表头那一行**恰好**是钉死的那只 · 别的候选名一个都不许出现」
     + **反证**：没有候选的站（镇上）一个字都不出
  ⑧-b ★ 本波（2026-09-27 · 任务③）：『遇敌』那一栏的**等级差提示** —— 这一站最弱的一只
     （`explore.station_level` 现算的站基准）比玩家高 > 带阈（`rules/level_band.json`）
     ⇒ 补一行 `SYS_LOOK_FOE_GAP`。正例（站基准最高那一站）· 两个反例（同级 / 镇上）·
     **反证**（把 `combat.in_band` 换成恒真 ⇒ 那一行消失）。★ 只补呈现，怪的数值一个没动
  ⑨ **反证一**：把「威慑档」改成 ×1 ⇒ 掷中率变化**可复算**（800 次抽样现算，实测率 ≈ 现算率）
  ⑩ **反证二**：表拿掉（真把文件挪走）⇒ 回「不掷」：`ratio` 回 `None`、**`roll` 一次都不调**、
     屏上与「掷空」那一支逐字相同、档与场一个字不动
  ⑪ 设计案 §〇 那两条「不掷」：**走路**与**观察**一次都不碰（不建场、不动档、`roll` 零调用）
  ⑫ 掷骰可复现：同人同名同日 ⇒ 同一个数；换人 / 换日 / 换站 ⇒ 翻面

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_explore.py
（Python 用 3.12；3.11 假红）
"""
from __future__ import annotations

import ast
import copy
import glob
import io
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402
from saintess_engine.command.registry import CommandRegistry         # noqa: E402

ok = True
DB = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_explore.db")
for _f in glob.glob(DB + "*"):                                       # 从干净的库开始（场那一条要）
    try:
        os.remove(_f)
    except OSError:
        pass


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


print("探针：探索遇怪（fxexp）")
FIXED = 1790308800          # 与 probe_cmds / probe_pick 同一根假钟（2026-09-25 12:00 +08:00 · 昼）
st = load_stack(str(REPO), inject={"db_path": DB, "clock": lambda: FIXED})
st.install()
DECL = st.command_declarations()
REG = CommandRegistry(name="probe_explore").load(DECL)
TX = st.domain("texts") or {}

from content import facade                                            # noqa: E402
from content import cmds_ast as CA                                    # noqa: E402
from content import cmds_battle as CBAT                               # noqa: E402
from content import cmds_gather as CG                                 # noqa: E402
from content import cmds_tower as CT                                  # noqa: E402
from content import calendar as CAL                                   # noqa: E402
from content import affix as AFFIX                                    # noqa: E402
from content import combat as CBO                                     # noqa: E402
from content import explore as EX                                     # noqa: E402
from content import instance as INST                                  # noqa: E402
from content import matsrc as MSX                                     # noqa: E402

TOWN = "windmill_town"
BONE = ("belt_north", "bn_bone")
CAMP = ("belt_north", "bn_camp")
ROOM = ("old_watchtower", "tower_hall")
MS = CA._data("monsters")
MAPS = CA._data("maps")


def V(slot, **slots):
    """槽位的**渲染值**（逐字从 texts 取 —— 探针里不抄一遍中文）。"""
    return CA.T(slot, **slots)


def parts(slot):
    val = str((TX.get(slot) or {}).get("value") or "")
    head, _, tail = val.partition("{")
    _ph, _, tail = tail.partition("}")
    return head, tail


class _E(object):
    """轻量 env：`_save()` 是空操作（落档是处理器的责任 —— 与 probe_onsite 同形）。

    `group_id` 要能传：那一场是**按群 / 按人**存的（`instance.key_of`），
    探针自己问「这一位名下有没有场」时得用**同一个群**。
    """

    def __init__(self, text="", group_id=""):
        self.text = text
        self.group_id = group_id

    def save(self):
        pass


def run(fn, p, text="", uid="u_exp"):
    out = []

    async def _go():
        async for line in fn(_E(text), None, uid, p):
            out.append(str(line))
    import asyncio
    asyncio.run(_go())
    return out


def clock_at(day, hod):
    return (day * 86400.0 + hod * 3600.0) * int(CAL.scale_seconds()) / 86400.0


def at(day, hod=12.0):
    facade.bind_host(clock=lambda: clock_at(day, hod))
    return CAL.state()


def player(**kw):
    p = dict(CA.DEFAULT_PLAYER)
    p.update({"race": "human", "cls": "cls_knight", "name": "试玩", "hp": 9999,
              "loc": BONE[0], "node": BONE[1], "level": 3,
              "bag": {}, "equipped": {}, "codex": {}, "flags": {}})
    p.update(kw)
    return p


def clear_battle(uid):
    INST.clear(INST.key_of("", uid, [uid]))


# ══════════════════════════════════════════════════════════════
# ① 声明与路由
# ══════════════════════════════════════════════════════════════
print("\n① 声明与路由（`探索` 这一条）")
_dec = DECL.get("explore") or {}
_look = DECL.get("look") or {}
_listen = DECL.get("listen") or {}
chk("★ `探索`（键 `explore`）在声明表里 · 可见 · guard 随时",
    bool(_dec) and _dec.get("visible") is True and str(_dec.get("guard_desc")) == "随时",
    "%s" % json.dumps(_dec, ensure_ascii=False)[:120])
chk("★ 分类与 `观察` / `聆听` **同格**（移动与世界）",
    str(_dec.get("category")) == str(_look.get("category")) == str(_listen.get("category")) == "移动与世界",
    "%s" % _dec.get("category"))
chk("★ 主词 + 两个别名都在 patterns 里（探索 · 探 · 走一圈）",
    [str(x) for x in (_dec.get("patterns") or [])] == ["^探索$", "^探$", "^走一圈$"],
    "%s" % (_dec.get("patterns"),))
chk("★ handler = `content.cmds_ast:explore`（与 `观察` 同一个内容模块）",
    str((_dec.get("bind") or {}).get("handler")) == "content.cmds_ast:explore"
    and str((_look.get("bind") or {}).get("handler")) == "content.cmds_ast:look",
    "%s" % ((_dec.get("bind") or {}).get("handler"),))
_hit3 = [getattr(REG.first_hit(w, visible_only=True), "key", None) for w in ("探索", "探", "走一圈")]
chk("★ 三个词都命中 `explore`（别名不是死的）", _hit3 == ["explore"] * 3, "%s" % _hit3)
# 反证：把这一条摘掉 ⇒ 那三个词没有任何声明接得住（= 不是借了别人的 pattern 命中）
_reg0 = CommandRegistry(name="probe_explore_rev").load(
    {k: v for k, v in DECL.items() if k != "explore"})
chk("★ 反证（拆掉这一条）：三个词一条声明都接不住 ⇒ 上面那三条判的是**这一条**新声明",
    all(_reg0.first_hit(w, visible_only=True) is None for w in ("探索", "探", "走一圈")),
    "%s" % [getattr(_reg0.first_hit(w, visible_only=True), "key", None)
            for w in ("探索", "探", "走一圈")])

# ══════════════════════════════════════════════════════════════
# ② 表 = 设计案那几个数（逐字）
# ══════════════════════════════════════════════════════════════
print("\n② 概率表（`content/rules/explore_encounter.json`）与设计案逐字对账")
#: 设计案 §2.3 那几个数 —— 探针里**另抄一份**（判据的独立一侧；两处不一致当场红）
DES_BASE = {"wild": 0.28, "deep": 0.40, "camp": 0.35, "room": 0.55, "town": 0.0}
DES_CAP, DES_FLOOR = 0.9, 0.0
DES_LEVEL = [(-99, -5, 2.2), (-4, -2, 1.6), (-1, 1, 1.0), (2, 4, 0.4), (5, 99, 0.0)]
DES_TIME = {"hr_dawn": 1.0, "hr_day": 1.0, "hr_dusk": 1.0, "hr_night": 1.25}
DES_WEATHER = {"w_sunny": 1.0, "w_rain": 1.15, "w_fog": 1.3, "w_snow": 1.0}
DES_ROLE = {"镇上": "town", "镇口": "town", "野外": "wild", "深处": "deep",
            "营地": "camp", "塔门": "room", "塔内": "room", "塔顶": "room"}
R = EX.rules()
chk("★ 表读得到（唯一真源）", bool(R), "%d 个顶层键" % len(R))
chk("★ `base` 五档逐字 = 设计案（野外带 .28 · 深处 .40 · 营地 .35 · 副本房间 .55 · 镇内 0）",
    {k: v for k, v in (R.get("base") or {}).items() if not str(k).startswith("_")} == DES_BASE,
    "%s" % (R.get("base"),))
chk("★ `cap` = 0.9 · `floor` = 0（都从表里取，代码里没有这两个数）",
    float((R.get("cap") or {}).get("value")) == DES_CAP
    and float((R.get("floor") or {}).get("value")) == DES_FLOOR)
_got_bands = [(int(b["min_diff"]), int(b["max_diff"]), float(b["mul"]))
              for b in (R.get("m_level") or {}).get("bands") or []]
chk("★ 等级差五档逐字 = 设计案（威慑 ×0 · ×0.4 · ×1 · ×1.6 · ×2.2）",
    sorted(_got_bands) == sorted(DES_LEVEL), "%s" % (_got_bands,))
_drop = lambda d: {k: float(v) for k, v in (d or {}).items() if not str(k).startswith("_")}
chk("★ 时辰档逐字（夜 ×1.25 · 其余 ×1）—— 键是 calendar 的时辰 id，不写死钟点",
    _drop(R.get("m_time")) == DES_TIME, "%s" % _drop(R.get("m_time")))
chk("★ 天气档逐字（雾 ×1.3 · 雨 ×1.15 · 晴 ×1 · 雪 ×1）",
    _drop(R.get("m_weather")) == DES_WEATHER, "%s" % _drop(R.get("m_weather")))
chk("★ 事件那一格 = `calendar.encounter_mul` 那一口（收法 max · 空表取 default 1.0）",
    str((R.get("m_event") or {}).get("reduce")) == "max"
    and float((R.get("m_event") or {}).get("default")) == 1.0)
chk("★ 档位映射逐字（role → 档）", dict(((R.get("band") or {}).get("by_node_role")) or {}) == DES_ROLE,
    "%s" % ((R.get("band") or {}).get("by_node_role"),))
_roles = {str(n.get("role")) for _l, m in MAPS.items() for n in (m.get("nodes") or [])}
chk("★ 覆盖面：maps 域里出现过的每个 `role` 都在表里有档（%d 个）"
    % len(_roles), _roles <= set(DES_ROLE), "%s" % sorted(_roles - set(DES_ROLE)))
_bad_band = []
for _l, m in MAPS.items():
    for n in (m.get("nodes") or []):
        _b = EX.band_of(_l, str(n.get("id")))
        if _b not in DES_BASE:
            _bad_band.append((_l, n.get("id"), _b))
chk("★ 覆盖面：**每一个站点**都落得到档（%d 站）"
    % sum(len(m.get("nodes") or []) for m in MAPS.values()), not _bad_band, "%s" % _bad_band[:4])

# ══════════════════════════════════════════════════════════════
# ③ 单源（静态）：概率数字只在表里
# ══════════════════════════════════════════════════════════════
print("\n③ 单源（静态）：代码里一个设计数字都没有 · 那张表只有一口读")
_nums = {v for v in DES_BASE.values()} | {DES_CAP, DES_FLOOR} \
    | {b[2] for b in DES_LEVEL} | set(DES_TIME.values()) | set(DES_WEATHER.values())


def _consts(node_or_src):
    """AST 里的**内容数字**（`0` / `1` 那种计数与单位元不算 —— 它们不是概率也不是倍数）。"""
    tree = ast.parse(node_or_src) if isinstance(node_or_src, str) else node_or_src
    out = []
    for nd in ast.walk(tree):
        if not isinstance(nd, ast.Constant) or isinstance(nd.value, bool):
            continue
        if isinstance(nd.value, float):
            out.append(float(nd.value))
        elif isinstance(nd.value, int) and abs(nd.value) > 1:
            out.append(float(nd.value))
    return out


def _code_only(path):
    """源码里**去掉 docstring** 的那一份（「文档里提到」不算「代码里用了」）。"""
    src = io.open(path, encoding="utf-8").read()
    lines = src.splitlines(True)
    tree = ast.parse(src)
    for nd in ast.walk(tree):
        if not isinstance(nd, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(nd, "body", None)
        doc = body[0] if body and isinstance(body[0], ast.Expr) \
            and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str) else None
        if doc is not None:
            for i in range(doc.lineno - 1, (doc.end_lineno or doc.lineno)):
                lines[i] = ""
    return "".join(lines)


_src_exp = io.open(os.path.join(REPO, "content", "explore.py"), encoding="utf-8").read()
_src_ast = io.open(os.path.join(REPO, "content", "cmds_ast.py"), encoding="utf-8").read()
_explore_fn = next(nd for nd in ast.parse(_src_ast).body
                   if isinstance(nd, ast.AsyncFunctionDef) and nd.name == "explore")
_leak = sorted({n for n in set(_consts(_src_exp) + _consts(_explore_fn)) if n in _nums})
chk("★ `content/explore.py` 与 `cmds_ast.explore` 的 AST 里**没有**任何设计数字（%d 个：%s）"
    % (len(_nums), " · ".join("%g" % x for x in sorted(_nums))), not _leak,
    "漏出来的：%s" % _leak)
_owners = sorted(os.path.basename(f) for f in glob.glob(os.path.join(REPO, "content", "*.py"))
                 if "explore_encounter" in _code_only(f))
chk("★ 那张表的打开口只有一处（`content/explore.py` · 别的文件只在注释里提过）",
    _owners == ["explore.py"], "%s" % _owners)
chk("★ 表里每一格都带 `_src`（口径表的纪律：数值要说得清从哪儿来）",
    all(("_src" in (R.get(k) or {})) for k in ("band", "base", "cap", "floor", "m_level",
                                               "m_time", "m_weather", "m_event")
        if isinstance(R.get(k), dict)))

# ══════════════════════════════════════════════════════════════
# ④ 纯函数：五个因子各翻一次面（探针按设计案另算一份）
# ══════════════════════════════════════════════════════════════
print("\n④ `explore.ratio()` 逐项可复算（base × 等级差 × 时辰 × 天气 × 事件 × cap）")


def des_ratio(band, diff, hour, weather, event):
    """设计案那一份（**探针自己算**，与 `explore.py` 无关 —— 两处独立对账）。"""
    m_lv = next(m for lo, hi, m in DES_LEVEL if lo <= diff <= hi)
    p = DES_BASE[band] * m_lv * DES_TIME[hour] * DES_WEATHER[weather] * event
    return max(DES_FLOOR, min(DES_CAP, p))


def _ratio(loc, node, level, st=None, p=None):
    return EX.ratio(MS, loc, node, level, st or CAL.state(), p or player())


_SUNNY = next((d for d in range(100, 200) if CAL.weather_of(d) == "w_sunny"), None)
_RAIN = next((d for d in range(100, 200) if CAL.weather_of(d) == "w_rain"), None)
_FOG = next((d for d in range(100, 200) if CAL.weather_of(d) == "w_fog"), None)
chk("★ 三种天气各自找得到一天（晴 / 雨 / 雾 —— 现算，不手打）",
    None not in (_SUNNY, _RAIN, _FOG), "晴 %s · 雨 %s · 雾 %s" % (_SUNNY, _RAIN, _FOG))
_got = []
for _d, _w, _mul in ((_SUNNY, "w_sunny", 1.0), (_RAIN, "w_rain", 1.15), (_FOG, "w_fog", 1.3)):
    for _hod, _h, _tm in ((12.0, "hr_day", 1.0), (22.0, "hr_night", 1.25)):
        for _band_spot, _lvl in (((BONE[0], BONE[1]), 3), ((BONE[0], BONE[1]), 1)):   # ±1 / ×2.2
            _stt = at(_d, _hod)
            _want = des_ratio(EX.band_of(*_band_spot), _lvl - EX.station_level(MS, *_band_spot, _lvl),
                              _stt["hour"], _stt["weather"], 1.0)
            _got.append((_d, _hod, _lvl, _ratio(*_band_spot, _lvl, _stt), round(_want, 6)))
chk("★ 五种组合（3 天气 × 2 时辰 × 2 等级差）逐项 = 探针另算那份（%d 组）" % len(_got),
    all(abs(g[3] - g[4]) < 1e-9 for g in _got), "%s" % [g for g in _got if abs(g[3] - g[4]) > 1e-9][:3])
_bone_band = EX.band_of(*BONE)
_lv_bone = EX.station_level(MS, *BONE, 3)
_bone_diffs = {}
for _d in (0, 2, 5, -2, -5):
    _stb = CAL.state()
    _bone_diffs[_d] = (_ratio(BONE[0], BONE[1], _lv_bone + _d),
                       des_ratio(_bone_band, _d, _stb["hour"], _stb["weather"], 1.0))
chk("★ 等级差五档各命中一次（站基准 %d · 骨田 · 现算时辰天气）" % _lv_bone,
    all(abs(g[0] - g[1]) < 1e-9 for g in _bone_diffs.values())
    and _bone_diffs[5][0] == 0.0 and _bone_diffs[-5][0] > _bone_diffs[0][0],
    "%s" % {k: (round(v[0], 4), round(v[1], 4)) for k, v in _bone_diffs.items()})
# 事件那一口：给一条就有（零变化 = 没给）
_real_ev = CAL.encounter_mul
at(_SUNNY, 12.0)
chk("★ 今天一条世界事件都没给 `encounter_mul` ⇒ m_event = 1.0（零变化：与接线前逐字相同）",
    EX.event_mul() == 1.0 and _real_ev() == {}, "%s" % _real_ev())
try:
    CAL.encounter_mul = lambda st=None, p=None: {"ms_field_mouse": 2}
    _ev2 = EX.event_mul()
    _p2 = _ratio(*BONE, 3)
    _w2 = des_ratio(_bone_band, 0, "hr_day", CAL.state()["weather"], 2.0)
    chk("★ 给一条 `encounter_mul`（×2）⇒ m_event 真吃上：p 从 %.4f → %.4f（= 2× 现算）"
        % (des_ratio(_bone_band, 0, "hr_day", CAL.state()["weather"], 1.0), _p2),
        abs(_ev2 - 2.0) < 1e-9 and abs(_p2 - _w2) < 1e-9 and _p2 > des_ratio(_bone_band, 0, "hr_day", CAL.state()["weather"], 1.0))
finally:
    CAL.encounter_mul = _real_ev
# cap：把两个因子叠到越界 ⇒ 正好落在 cap
try:
    CAL.encounter_mul = lambda st=None, p=None: {"x": 4}
    at(_FOG, 22.0)
    _capv = _ratio(*ROOM, 6)
    _raw = DES_BASE["room"] * 1.0 * DES_TIME["hr_night"] * DES_WEATHER["w_fog"] * 4.0
    chk("★ `cap` 真兜住（副本房间 × 夜 × 雾 × 事件4 = %.3f 原值 ⇒ 掷出来正好 %.2f）" % (_raw, DES_CAP),
        _raw > DES_CAP and abs(_capv - DES_CAP) < 1e-9, "%s" % _capv)
finally:
    CAL.encounter_mul = _real_ev
# fail-closed 单元（表缺 / 档取不到 / 时辰或天气没配 / 这一站没挂怪）
_orig_rules = EX.rules
try:
    EX.rules = lambda: {}
    _fc = [_ratio(*BONE, 3), EX.band_of(*BONE)]
    chk("★ fail-closed：表空 ⇒ `ratio` 回 `None`（不掷）· 档回空串（`band.default` 也没了）",
        _fc[0] is None and _fc[1] == "", "%s" % _fc)
finally:
    EX.rules = _orig_rules
_bad = copy.deepcopy(R)
_bad["band"]["by_node_role"] = {}
del _bad["band"]["default"]
_bad2 = copy.deepcopy(R)
_bad2["m_time"] = {"hr_day": 1.0}
_bad3 = copy.deepcopy(R)
_bad3["m_level"]["bands"] = [{"min_diff": 50, "max_diff": 99, "mul": 1.0}]
for _tbl, _tag in ((_bad, "拿不到档（role 不在表里 + 没有 default）"),
                   (_bad2, "时辰没配"), (_bad3, "等级差落在表外")):
    EX.rules = lambda _t=_tbl: _t
    _v = _ratio(*BONE, 3)
    EX.rules = _orig_rules
    chk("★ fail-closed：%s ⇒ 回 `None`（不掷）" % _tag, _v is None, "%s" % _v)
chk("★ fail-closed：这一站一只怪都没挂（镇上）⇒ 回 `None`（本来也没得打）",
    _ratio(TOWN, "wt_gate_n", 3) is None and _ratio(TOWN, "wt_gate_n", 9) is None)
at(_RAIN, 12.0)

# ══════════════════════════════════════════════════════════════
# ⑤ 四态① 掷中（固定种子真敲）
# ══════════════════════════════════════════════════════════════
print("\n⑤ 四态①  掷中（固定种子真敲 ⇒ 开场那一屏 = 遭遇 + 这一手，两只名字逐字相同）")


def hit_uid(loc, node, level, day, hod=12.0, upto=400):
    """现算一个「今天这一站必定撞上」的 uid（不手打 —— 种子 = uid + 图 + 节点 + 游戏日）。"""
    at(day, hod)
    for i in range(upto):
        u = "u_exp%03d" % i
        pr = player(loc=loc, node=node, level=level)
        r = _ratio(loc, node, level, CAL.state(), pr)
        if r and EX.roll(u, pr) < r:
            return u, r
    return None, None


_uid, _pr = hit_uid(BONE[0], BONE[1], 3, _RAIN)
clear_battle(_uid)
_p = player()
_out = run(CA.explore, _p, uid=_uid)
_mid = next((m for m in MS if _out and _out[0] == V("COMBAT_MEET", name=MS[m].get("name", m))), None)
chk("★ 第一行 = 『遭遇：<怪名>』（走的是老那一口 `COMBAT_MEET`）", _mid is not None,
    "%s" % (_out[:1],))
chk("★ 第二行 = 新槽位 `COMBAT_EXPLORE_MET`，且名字与遭遇那只**逐字相同**（同一次抽）",
    _mid is not None and len(_out) > 1
    and _out[1] == V("COMBAT_EXPLORE_MET", name=MS[_mid].get("name", _mid)),
    "%s" % (_out[1:2],))
chk("★ 那一屏接着真打完并落账（与『攻击』同一套：日志 + 结算 + 掉落行）",
    any("打完了" in x for x in _out) and any("金币" in x or "生命" in x for x in _out)
    and bool(_p.get("flags", {}).get("last_battle")),
    "%s" % (_out[-4:],))
_out2 = run(CA.explore, player(loc=BONE[0], node=BONE[1], level=3), uid=_uid)
chk("★ 同人同日同站再敲一次：掷骰可复现 ⇒ **还是撞**（种子 = uid + 图 + 节点 + 游戏日）",
    any("遭遇" in x for x in _out2), "%s" % (_out2[:1],))
clear_battle(_uid)
# 精英那一档：名字带 † … †（进度条那条名字与 head 里那只必须同一只）
_e_u, _e_day, _e_mid = None, None, None
for _d in range(100, 140):
    at(_d, 12.0)
    for i in range(80):
        u = "u_eli%03d" % i
        el = AFFIX.elite_of(MS, CAMP[0], CAMP[1], u, CAL.state().get("game_day"), 3)
        if el:
            _e_u, _e_day, _e_mid = u, _d, el
            break
    if _e_u:
        break
chk("★ 找得到「今天这一站有精英」的档（骨田被 `no_elite_nodes` 摘掉了 ⇒ 用拾荒营地）",
    bool(_e_u), "uid=%s day=%s 怪=%s" % (_e_u, _e_day, _e_mid[0] if _e_mid else None))
if _e_u:
    at(_e_day, 12.0)
    clear_battle(_e_u)
    _eo = run(CA.explore, player(loc=CAMP[0], node=CAMP[1], level=3), uid=_e_u)
    _disp = AFFIX.display_name(str(MS[_e_mid[0]].get("name", _e_mid[0])), list(_e_mid[1]))
    chk("★ 精英那一档：第一行 = `COMBAT_ELITE_SPAWN` 那一行 · 第二行 = `COMBAT_EXPLORE_MET`，"
        "名字 = **同一只**（`affix.display_name`）",
        bool(_eo) and _eo[0] == AFFIX.elite_line(str(MS[_e_mid[0]].get("name", _e_mid[0])), _e_mid[1])
        and len(_eo) > 1 and _eo[1] == V("COMBAT_EXPLORE_MET", name=_disp),
        "%s" % (_eo[:2],))
    clear_battle(_e_u)

# ══════════════════════════════════════════════════════════════
# ⑥ 四态② 掷空
# ══════════════════════════════════════════════════════════════
print("\n⑥ 四态②  掷空（威慑档 = 真 0）：有拾取点给提示 · 没有就通用那句 · 不建场不动档")
_lv9 = EX.station_level(MS, *BONE, 9) + 5          # 玩家比站基准高 5 ⇒ 威慑档（×0）
at(_RAIN, 12.0)
_r0 = _ratio(BONE[0], BONE[1], _lv9)
chk("★ 威慑档真算出来是 0（玩家 %d 级 · 站基准 %d）" % (_lv9, EX.station_level(MS, *BONE, _lv9)),
    _r0 == 0.0, "%s" % _r0)
_p3 = player(level=_lv9)
_before = copy.deepcopy(_p3)
clear_battle("u_exp")
_out3 = run(CA.explore, _p3, uid="u_exp")
_pts = CG._points_here(_p3)
chk("★ 骨田有拾取点（%d 处）⇒ 出 `SYS_EXPLORE_PICK`，现成声明一条条列出来"
    % len(_pts),
    bool(_pts) and len(_out3) == 1 and _out3[0].startswith(parts("SYS_EXPLORE_PICK")[0])
    and all(str(pt.get("name")) in _out3[0] for _g, pt in _pts[:MSX.MAX_SPOT]),
    "%s" % (_out3[:1],))
chk("★ 提示那一行由**现成**的 `SYS_SRC_GATHER` 片段拼（动作词走 `SYS_GATHER_VERB_*`）",
    all(V("SYS_GATHER_VERB_%s" % str(pt.get("verb")).upper()) in _out3[0]
        for _g, pt in _pts[:MSX.MAX_SPOT]),
    "%s" % (_out3[0][:60],))
chk("★ 掷空**不动档、不建场**（档逐字相同 · 没有 `last_battle` · 这一位名下有场？否）",
    _p3 == _before and not INST.fighting(_E(), "u_exp")
    and not (_p3.get("flags") or {}).get("last_battle"),
    "档变了：%s" % [k for k in set(list(_before) + list(_p3)) if _before.get(k) != _p3.get(k)])
# 没有拾取点的野外站 ⇒ 通用那句：**旧哨塔下**那一站只有一个「夜」才开的采集点
#   （`gathering` 域现读 —— 白天的 `CAL.allows` 拦下它）⇒ 昼 = 通用那句 / 夜 = 拾取提示。
_GATED = next(((l, str(n.get("id"))) for l, m in MAPS.items() for n in (m.get("nodes") or [])
               if (m.get("topology") or "chain") != "star"
               and any(v.get("map") == l and v.get("subarea") == str(n.get("id"))
                       and v.get("time") for v in CG._data("gathering").values())
               and all(v.get("time") for v in CG._data("gathering").values()
                       if v.get("map") == l and v.get("subarea") == str(n.get("id")))), None)
chk("★ 找得到一个「有怪、只有一个**整点门槛**采集点」的野外站（反证那一档的前提）",
    bool(_GATED) and bool(CBO.encounter_cand(MS, _GATED[0], _GATED[1], _lv9)[0]),
    "%s" % (_GATED,))
if _GATED:
    _p4 = player(loc=_GATED[0], node=_GATED[1], level=_lv9)
    at(_RAIN, 12.0)                                     # 昼 ⇒ 那个点还开不了
    clear_battle("u_exp")
    _out4 = run(CA.explore, _p4, uid="u_exp")
    chk("★ 拾取点**整点门槛没过**（昼）⇒ 只出 `SYS_EXPLORE_CLEAR`（%s）" % V("SYS_EXPLORE_CLEAR"),
        _out4 == [V("SYS_EXPLORE_CLEAR")], "%s" % (_out4[:1],))
    at(_RAIN, 22.0)                                     # 夜 ⇒ 那个点开了
    _out4n = run(CA.explore, player(loc=_GATED[0], node=_GATED[1], level=_lv9), uid="u_exp")
    chk("★ 反证（两态都由**现成声明**说话）：同一个站到夜里 ⇒ 那一句换成拾取提示（同一个口）",
        len(_out4n) == 1 and _out4n[0].startswith(parts("SYS_EXPLORE_PICK")[0])
        and _out4n != _out4, "%s" % (_out4n[:1],))
    # 反证：把「有没有拾取点」那口摘空 ⇒ 骨田（有采集点）也走通用那句
    _real_pts = CG._points_here
    try:
        CG._points_here = lambda p, verb=None: []
        _rev = EX.miss_lines(_p3)
    finally:
        CG._points_here = _real_pts
    chk("★ 反证（拆掉声明）：把采集点那口摘空 ⇒ 骨田也回 `SYS_EXPLORE_CLEAR` —— 判的是现成声明",
        _rev == [V("SYS_EXPLORE_CLEAR")] and EX.miss_lines(_p3) == _out3, "%s" % (_rev[:1],))
at(_RAIN, 12.0)
# 镇上（安全区 · 一只候选都没有）⇒ 不掷
_p5 = player(loc=TOWN, node="wt_gate_n", level=3)
clear_battle("u_exp")
chk("★ 镇上（安全区：这一站一只候选都没有）⇒ 不掷 ⇒ 只出通用那句",
    run(CA.explore, _p5, uid="u_exp") == [V("SYS_EXPLORE_CLEAR")])

# ══════════════════════════════════════════════════════════════
# ⑦ 四态③ 持态（场在跑 ⇒ 拦下 · 与移动族同一句）
# ══════════════════════════════════════════════════════════════
print("\n⑦ 四态③  持态：场在跑时敲 `探索` ⇒ 拦下，回的那一句与移动族**逐字同一句**")


class _Ad(object):
    """三函数 + say（照 host-api 契约的最小适配器 —— 与 probe_cmds / e2e_drive 同形）。"""

    def __init__(self, msgs, seed):
        self._msgs = [{"uid": "u_h", "group_id": "g_h", "text": t, "is_group": True} for t in msgs]
        self.out = []
        self.saved = seed

    def recv(self):
        return self._msgs.pop(0) if self._msgs else None

    def load_player(self, uid):
        return self.saved if uid == "u_h" else None

    def save_player(self, uid, data):
        self.saved = dict(data) if isinstance(data, dict) else data

    def say(self, to, text):
        self.out.append(str(text))


from saintess_engine.host.runtime import Host                          # noqa: E402

_hdb = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_explore_host.db")
for _f in glob.glob(_hdb + "*"):
    try:
        os.remove(_f)
    except OSError:
        pass
at(_RAIN, 12.0)
_hit_u, _hr = hit_uid(BONE[0], BONE[1], 3, _RAIN)
_seed = {"name": "试玩", "race": "human", "cls": "cls_knight", "level": 3, "exp": 0,
         "loc": BONE[0], "node": BONE[1], "prev": [], "gold": 30, "hp": 9999,
         "bag": {}, "equipped": {}, "codex": {}, "flags": {}}
_ad = _Ad(["攻击"], _seed)
_host = Host(_ad, str(REPO), inject={"db_path": _hdb, "clock": lambda: clock_at(_RAIN, 12.0)})
_host.boot()
_ad.out.clear()
_host.handle({"uid": "u_h", "group_id": "g_h", "text": "攻击"})
_game = list(_ad.out)
chk("★ 真宿主：`攻击` 开起一场（G2 一手推进 ⇒ 场落在库里）",
    any("遭遇" in x for x in _game), "%s" % _game[:1])
chk("★ 这一位名下真有一场没打完的（`instance.fighting` · 用**同一个群**问）",
    INST.fighting(_E(group_id="g_h"), "u_h") is True)
_snap = copy.deepcopy(_ad.saved)
_ad.out.clear()
_host.handle({"uid": "u_h", "group_id": "g_h", "text": "探索"})
_locked = list(_ad.out)
chk("★ 场在跑时敲 `探索` ⇒ 拦下那一句 `SYS_MOVE_IN_FIGHT`（%s）" % V("SYS_MOVE_IN_FIGHT"),
    _locked == [V("SYS_MOVE_IN_FIGHT")], "%s" % (_locked[:1],))
_ad.out.clear()
_host.handle({"uid": "u_h", "group_id": "g_h", "text": "往东"})
_move = list(_ad.out)
chk("★ 与移动族**同一句**（同一道闸 `_in_fight`）：`往东` 回的与 `探索` 回的逐字相同",
    _move == _locked and _move == [V("SYS_MOVE_IN_FIGHT")], "移动=%s ／ 探索=%s" % (_move[:1], _locked[:1]))
chk("★ 拦下那两下**档一个字不动**（位置 / 历史 / 血都是拦下前的）",
    _ad.saved == _snap, "变了：%s" % [k for k in set(list(_snap) + list(_ad.saved))
                                      if _snap.get(k) != _ad.saved.get(k)])

# ══════════════════════════════════════════════════════════════
# ⑧ 四态④ 可读：`观察` 的普通怪行 = 『攻击』真开的那一只（同一次抽）
# ══════════════════════════════════════════════════════════════
print("\n⑧ 四态④  可读：`SYS_LOOK_FOE_ROW` 接上读端，且那一只 = 『攻击』真开的那只（同一次抽）")
_real_pick = CBO.pick_encounter
_real_elite = AFFIX.elite_of
_calls = []


def _pinned(mid):
    def _f(*a, **k):
        _calls.append(mid)
        return [mid]
    return _f


#: 钉子下在**候选 ≥ 3 的站**（拾荒营地：田鼠 / 拾荒野狗 / 拾荒人），钉的是**最后那一只**。
#:  ★ 第二手复核（2026-09-27 · 复核那一路的自查）：这一条原先下在**骨田**，而骨田按这一档
#:    只有**一只**候选 ⇒ 「把候选列出来」那种写法（`SYS_LOOK_FOE_ROW` 的 `{list}` 天然容得下
#:    多名）与「就是那一只」在屏上**逐字相同** ⇒ 判据抓不住（实测：把实现换成候选名单，
#:    这一条照样绿 —— 那是「判据没牙」）。三处加严：
#:      ① 挪到候选 ≥ 3 的站；
#:      ② **连精英那条口一起钉**（野外 `affix.elite_of` 会抢「这一格那只」，不钉它钉子会被顶掉）；
#:      ③ 判据从「屏上**有**这一行」加严成「紧跟表头那一行**恰好**是它 · 别的候选名一个都不许出现」。
_PIN_AT = CAMP
_CAND = CBO.encounter_cand(MS, _PIN_AT[0], _PIN_AT[1], 3)[0]
_PIN = _CAND[-1] if len(_CAND) > 1 else _CAND[0]
_OTHERS = [m for m in _CAND if m != _PIN]
at(_RAIN, 12.0)
try:
    CBO.pick_encounter = _pinned(_PIN)
    AFFIX.elite_of = lambda *a, **k: []            # 精英那条口也钉掉（野外它会抢「这一格那只」）
    _calls.clear()
    _pl = player(loc=_PIN_AT[0], node=_PIN_AT[1])
    _lk = run(CA.look, _pl, uid="u_exp")
    _row = V("SYS_LOOK_FOE_ROW", list="『%s』" % MS[_PIN].get("name", _PIN))
    _hdr_at = _lk.index(V("SYS_LOOK_FOE")) if V("SYS_LOOK_FOE") in _lk else -1
    _rows_on = _lk[_hdr_at + 1:_hdr_at + 2] if _hdr_at >= 0 else []
    chk("★ `观察` 印出表头 `SYS_LOOK_FOE` + 普通怪行 `SYS_LOOK_FOE_ROW`：紧跟表头那一行"
        "**恰好**是钉死的那一只",
        _hdr_at >= 0 and _rows_on == [_row], "表头后那一行 = %s" % (_rows_on,))
    chk("★ 那一行里**没有别的候选**的名字（这一栏说的是会开打的那一只，不是候选名单）",
        bool(_OTHERS) and _rows_on == [_row]
        and all(str(MS[m].get("name") or m) not in "".join(_rows_on) for m in _OTHERS),
        "别的候选 = %s ／ 表头后那一行 = %s"
        % ([(m, MS[m].get("name")) for m in _OTHERS], _rows_on))
    chk("★ 行里的名字 = 钉的那一只（名字走 `cmds_battle.foe_here` —— 『攻击』开的也是它）",
        _rows_on == [_row] and _calls == [_PIN],
        "抽怪被调了 %d 次 · %s" % (len(_calls), _calls[:2]))
    _calls.clear()
    clear_battle("u_exp")
    _at = run(CBAT.attack, player(loc=_PIN_AT[0], node=_PIN_AT[1]), uid="u_exp")
    _head = [x for x in _at if "遭遇" in x]
    chk("★ 『攻击』真开的那一只 = `观察` 印的那一只（同一个口 · 同一次抽 · 逐字）",
        bool(_head) and MS[_PIN].get("name") in _head[0] and _calls == [_PIN],
        "遭遇=%s ／ 抽怪 %d 次" % (_head[:1], len(_calls)))
    clear_battle("u_exp")
finally:
    CBO.pick_encounter = _real_pick
    AFFIX.elite_of = _real_elite
# 反证：没有候选的站（镇上）一个字都不出
_town_look = run(CA.look, player(loc=TOWN, node="wt_gate_n"), uid="u_exp")
chk("★ 反证：镇上（这一站一只候选都没有）⇒ 表头与那一行**都不出**（不是「总要印一行」）",
    V("SYS_LOOK_FOE") not in _town_look and V("SYS_LOOK_FOE_ROW", list="x") not in _town_look,
    "%s" % (_town_look[-3:],))
# 反证：一次命令只抽一次（没多抽一只手气）
_calls.clear()
try:
    CBO.pick_encounter = _pinned(_PIN)
    run(CA.look, player(), uid="u_exp")
    _n_look = len(_calls)
    _calls.clear()
    clear_battle("u_exp")
    run(CBAT.attack, player(), uid="u_exp")
    _n_atk = len(_calls)
finally:
    CBO.pick_encounter = _real_pick
    clear_battle("u_exp")
chk("★ 一次命令只抽一次（`观察` %d 次 · `攻击` %d 次 ⇒ 都在同一个口上）" % (_n_look, _n_atk),
    _n_look == 1 and _n_atk == 1, "观察 %d ／ 攻击 %d" % (_n_look, _n_atk))
# 覆盖：野外每个有候选的站都印得出来（塔内维持 ROOM 那一档）
_miss_row = []
for _d in (100, _RAIN):
    at(_d, 12.0)
    for _l, _m in MAPS.items():
        if _l == "old_watchtower":
            continue
        for _n in (_m.get("nodes") or []):
            _pl2 = player(loc=_l, node=str(_n.get("id")))
            if not CBO.encounter_cand(MS, _l, str(_n.get("id")), 3)[0]:
                continue
            if not any(x == V("SYS_LOOK_FOE") for x in run(CA.look, _pl2, uid="u_exp")):
                _miss_row.append((_l, _n.get("id")))
chk("★ 覆盖：野外每个「有候选」的站，`观察` 都印得出「遇敌」那一栏（0 个漏）",
    not _miss_row, "%s" % _miss_row[:4])
_room_look = run(CA.look, player(loc=ROOM[0], node=ROOM[1], level=6), uid="u_exp")
_room_name = CBAT.foe_here(player(loc=ROOM[0], node=ROOM[1], level=6), "u_exp")
chk("★ 塔内维持现状：名字行走 `SYS_LOOK_FOE_ROOM`（副本那档一个字没改）",
    V("SYS_LOOK_FOE") in _room_look and bool(_room_name)
    and V("SYS_LOOK_FOE_ROOM", name=_room_name) in _room_look,
    "%s" % (_room_look[-3:],))

# ══════════════════════════════════════════════════════════════
# ⑧-b ★ 本波（2026-09-27 · 任务③）：『遇敌』那一栏的**等级差提示**
#   口径：这一站**最弱的一只**（`explore.station_level` 现算的站基准）比玩家高 ≥5 级
#   （= 整片都在等级带外 —— 唯一声明处 `content/rules/level_band.json`）⇒ 补一行
#   `SYS_LOOK_FOE_GAP`。★ 这是**新增呈现**，不是降数值（P-30 后半「旧哨塔下 = 1 级必死场、
#   两条退路都被堵」仍是未定口径 ⇒ 怪的 hp/atk 一个数都没动）。
#   判据：正例（站基准最高的那一站 · 玩家按数据现算一个「差 ≥ 带阈+1」的等级）· 反例（同站
#   同等级 ⇒ 一个字都不多说）· ★ 反证（把「带内」判据换成恒真 ⇒ 那一行当场消失）。
# ══════════════════════════════════════════════════════════════
print("\n⑧-b 任务③ `观察`「遇敌」那一栏的等级差提示（站基准 vs 玩家等级 · 只补呈现）")
_GAP_AT = []
for _l, _m in MAPS.items():
    for _n in (_m.get("nodes") or []):
        _b = EX.station_level(MS, str(_l), str(_n.get("id")), 1)
        if _b:
            _GAP_AT.append((str(_l), str(_n.get("id")), int(_b)))
_GAP_AT.sort(key=lambda x: (-x[2], x[0], x[1]))
_gl, _gn, _gbase = _GAP_AT[0]                          # 站基准最高那一站（现算，不手写）
_BAND_MAX = int(json.load(io.open(os.path.join(REPO, "content", "rules", "level_band.json"),
                                  encoding="utf-8"))["max_level_diff"]["value"])
_plow = max(1, _gbase - _BAND_MAX - 1)                 # 差 = 带阈+1（≥5）⇒ 出带
_GAP_HEAD, _ = parts("SYS_LOOK_FOE_GAP")
_look_low = run(CA.look, player(loc=_gl, node=_gn, level=_plow), uid="u_exp")
chk("★ 站基准最高那一站（%s · %s · 最弱一只 lv%d）· 玩家 %d 级（差 %d > 带阈 %d）⇒ 补那一行"
    "（逐字 = 槽位渲染 `%s`）"
    % (_gl, _gn, _gbase, _plow, _gbase - _plow, _BAND_MAX,
       V("SYS_LOOK_FOE_GAP", gap=_gbase - _plow)),
    V("SYS_LOOK_FOE_GAP", gap=_gbase - _plow) in _look_low, "%s" % (_look_low[-4:],))
chk("★ 反例：同一站、把玩家放到**站基准同级**（差 0）⇒ 那一行一个字都不多说",
    not any(str(x).startswith(_GAP_HEAD)
            for x in run(CA.look, player(loc=_gl, node=_gn, level=_gbase), uid="u_exp")), "")
chk("★ 反例：镇上（这一站一只候选都没有）⇒ 同样不说那一句",
    not any(str(x).startswith(_GAP_HEAD)
            for x in run(CA.look, player(loc=TOWN, node="wt_gate_n", level=1), uid="u_exp")), "")
_keep_inband = CBO.in_band
try:
    CBO.in_band = (lambda *a, **k: True)               # 「永远在带内」⇒ 那一句不该再出
    _look_off = run(CA.look, player(loc=_gl, node=_gn, level=_plow), uid="u_exp")
finally:
    CBO.in_band = _keep_inband
chk("★ 反证：把 `combat.in_band` 换成恒真 ⇒ 那一行当场消失（判据真载重、不是恒真）",
    not any(str(x).startswith(_GAP_HEAD) for x in _look_off), "%s" % (_look_off[-3:],))

# ══════════════════════════════════════════════════════════════
# ⑨ 反证一：把「威慑档」改成 ×1 ⇒ 掷中率变化可复算
# ══════════════════════════════════════════════════════════════
print("\n⑨ 反证一：表里那一格「威慑档」改成 ×1 ⇒ 掷中率**变化可复算**（800 次抽样现算）")
_LV = 9
_SAMPLES = []
for _d in range(100, 140):                       # 40 天 × 20 人 = 800 次
    _stx = at(_d, 12.0)
    for _i in range(20):
        _SAMPLES.append(("u_rate%03d" % _i, _d, copy.deepcopy(_stx), player(level=_LV)))
chk("★ 抽样点建好了（%d 个 (人 × 日) 组合 · 现算时辰天气）" % len(_SAMPLES), len(_SAMPLES) == 800)


def _rate(tbl_getter):
    """现算：这一批抽样里「掷中」的比例 + 现算的期望率（两边都自己算，不借实现体）。"""
    _save_r = EX.rules
    EX.rules = tbl_getter
    hit, exp = 0, 0.0
    try:
        for _u, _d, _stx, _pp in _SAMPLES:
            facade.bind_host(clock=lambda _dd=_d: clock_at(_dd, 12.0))   # 手气按**那一天**算
            _p_here = _ratio(BONE[0], BONE[1], _LV, _stx, _pp)
            exp += _p_here
            if EX.roll(_u, _pp) < _p_here:
                hit += 1
    finally:
        EX.rules = _save_r
    return hit / float(len(_SAMPLES)), exp / float(len(_SAMPLES))


_obs0, _exp0 = _rate(_orig_rules)
_band_patched = copy.deepcopy(R)
for _b in _band_patched["m_level"]["bands"]:
    if float(_b["mul"]) == 0.0:
        _b["mul"] = 1.0
_obs1, _exp1 = _rate(lambda: _band_patched)
chk("★ 基线（今天的表）：威慑档 ⇒ 期望率 %.4f · 实测率 %.4f（一次都没撞）" % (_exp0, _obs0),
    _exp0 == 0.0 and _obs0 == 0.0)
chk("★ 改成 ×1 之后：期望率 %.4f · 实测率 %.4f（**只有表变了**）" % (_exp1, _obs1),
    _exp1 > 0.25 and _obs1 > 0.0)
chk("★ 掷中率变化**可复算**：实测 %d/%d = %.4f 与现算 %.4f 的差 ≤ 0.05（800 次抽样）"
    % (round(_obs1 * len(_SAMPLES)), len(_SAMPLES), _obs1, _exp1),
    abs(_obs1 - _exp1) <= 0.05, "差 %.4f" % abs(_obs1 - _exp1))
chk("★ 反证：把表改回去 ⇒ 又回 0（判据判的是**表里那一格**，不是别的）",
    _rate(_orig_rules)[0] == 0.0)

# ══════════════════════════════════════════════════════════════
# ⑩ 反证二：表拿掉 ⇒ 回「不掷」（与接线前逐字相同）
# ══════════════════════════════════════════════════════════════
print("\n⑩ 反证二：把表**真挪走** ⇒ 回「不掷」：`roll` 一次都不调 · 屏上与掷空那一支逐字相同")
_REAL_FILE = EX.RULES_FILE
_roll_calls = []
_real_roll = EX.roll


def _counting_roll(*a, **k):
    _roll_calls.append(a)
    return _real_roll(*a, **k)


at(_RAIN, 12.0)
_exp_miss = EX.miss_lines(player())                       # 「掷空那一支」的标准样子（表在时现算）
_p6 = player()
clear_battle("u_exp")
_base_scr = run(CA.explore, _p6, uid=_uid)                # 表在时（会掷、会撞）—— 先留一份对照
chk("★ 对照：表在时同一敲会**撞**（下面那支判的真是「表在不在」）",
    any("遭遇" in x for x in _base_scr), "%s" % (_base_scr[:1],))
clear_battle("u_exp")
try:
    os.rename(_REAL_FILE, _REAL_FILE + ".probe-bak")
    EX._CACHE.clear()
    chk("★ 表真挪走了（`os.path.exists` 为假）", not os.path.exists(_REAL_FILE))
    chk("★ `explore.rules()` 回空表（不猜一个默认率）", EX.rules() == {})
    chk("★ `ratio` 回 `None` = 不掷", _ratio(BONE[0], BONE[1], 3) is None)
    EX.roll = _counting_roll
    _roll_calls.clear()
    _p7 = player()
    _before7 = copy.deepcopy(_p7)
    clear_battle("u_exp")
    _out7 = run(CA.explore, _p7, uid=_uid)
    chk("★ 真敲 `探索`：`roll` **一次都没调**（不掷是「不掷」，不是「掷了没中」）",
        _roll_calls == [], "%d 次" % len(_roll_calls))
    chk("★ 屏上**逐字** = 掷空那一支（与接线前那套非战斗产出同一句）",
        _out7 == _exp_miss and _out7 == EX.miss_lines(player()),
        "不掷=%s ／ 掷空那一支=%s" % (_out7[:1], _exp_miss[:1]))
    chk("★ 不掷 ⇒ **档一个字不动 · 不建场 · 没有遭遇行**",
        _p7 == _before7 and not INST.fighting(_E(), "u_exp")
        and not [x for x in _out7 if "遭遇" in x],
        "档变了：%s" % [k for k in set(list(_before7) + list(_p7)) if _before7.get(k) != _p7.get(k)])
finally:
    EX.roll = _real_roll
    if os.path.exists(_REAL_FILE + ".probe-bak"):
        os.rename(_REAL_FILE + ".probe-bak", _REAL_FILE)
    EX._CACHE.clear()
chk("★ 探针自己把表放回去了（`os.path.exists` 为真 · 表读得回来）",
    os.path.exists(_REAL_FILE) and bool(EX.rules()))
chk("★ 表回来之后：同一敲**又**会撞（上面那支判的真是「表在不在」）",
    any("遭遇" in x for x in run(CA.explore, player(), uid=_uid)), "%s" % (_base_scr[:1],))
clear_battle("u_exp")

# ══════════════════════════════════════════════════════════════
# ⑪ 设计案 §〇：走路与观察**不掷**
# ══════════════════════════════════════════════════════════════
print("\n⑪ 设计案 §〇 那两条：走路不掷 · `观察` 不掷（一次都不碰遇怪那一口）")
for _tag, _fn, _pp in (("观察", CA.look, player()),
                       ("聆听", CA.listen, player())):
    EX.roll = _counting_roll
    _roll_calls.clear()
    _b4 = copy.deepcopy(_pp)
    clear_battle("u_exp")
    run(_fn, _pp, uid="u_exp")
    EX.roll = _real_roll
    chk("★ `%s` 一次都没掷（`roll` 0 次 · 不建场 · 档不变 —— 掷是 `探索` 的专属）" % _tag,
        _roll_calls == [] and not INST.fighting(_E(), "u_exp") and _pp == _b4,
        "roll %d 次 · 场=%s" % (len(_roll_calls), INST.fighting(_E(), "u_exp")))
_pm = player(loc=TOWN, node="wt_gate_n")
EX.roll = _counting_roll
_roll_calls.clear()
clear_battle("u_exp")
_outm = run(CA.go_north, _pm, uid="u_exp")
EX.roll = _real_roll
chk("★ `往北` 一次都没掷（`roll` 0 次 · 不建场）—— 走路照旧只位移（位置真变到北带）",
    _roll_calls == [] and not INST.fighting(_E(), "u_exp")
    and (_pm.get("loc"), _pm.get("node")) != (TOWN, "wt_gate_n"),
    "roll %d 次 · 场=%s · 落点=%s" % (len(_roll_calls), INST.fighting(_E(), "u_exp"),
                                      (_pm.get("loc"), _pm.get("node"))))
at(_RAIN, 12.0)

# ══════════════════════════════════════════════════════════════
# ⑫ 掷骰可复现
# ══════════════════════════════════════════════════════════════
print("\n⑫ 掷骰可复现：同人同名同日 ⇒ 同一个数；换人 / 换日 / 换站 ⇒ 翻面")
at(_RAIN, 12.0)
_p8 = player()
_r1 = EX.roll("u_same", _p8)
_r2 = EX.roll("u_same", _p8)
chk("★ 同一颗种子 ⇒ 同一个数（%.6f）" % _r1, _r1 == _r2)
chk("★ 种子逐字 = `aetheran:explore:<uid>:<图>:<节点>:<游戏日>`",
    EX.seed_of("u_same", _p8) == "aetheran:explore:u_same:%s:%s:%d"
    % (BONE[0], BONE[1], CAL.state()["game_day"]), "%s" % EX.seed_of("u_same", _p8))
_r_other = EX.roll("u_other", _p8)
_r_day = EX.roll("u_same", player(loc=BONE[0], node=CAMP[1]))
at(_RAIN + 1, 12.0)
_r_next = EX.roll("u_same", _p8)
chk("★ 换人 / 换站 / 换日 ⇒ 手气翻面（三个数都不一样）",
    len({round(_r1, 9), round(_r_other, 9), round(_r_day, 9), round(_r_next, 9)}) == 4,
    "%s" % [round(x, 4) for x in (_r1, _r_other, _r_day, _r_next)])
at(_RAIN, 12.0)

print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
