# -*- coding: utf-8 -*-
"""《阿斯特兰》装配入口（第二刀：最小可跑骨架）。

方向只有一条：**内容 → 引擎**。引擎不 import 本包，也不认识本包的表。

| hook | 供体 | 说明 |
|---|---|---|
| `formula_table_fn` | `content/rules/formula_table.json` | 声明式公式表（E1），12 条 |
| `formula_bindings_fn` | `content/rules/formula_bindings.json` | 语义槽位 → 声明 id（E1b）|
| `time_model_fn` | 委托声明 `F6_act_time` | CTB 行动耗时 —— 不自己实现公式 |
| `panel_layers_fn` | `content/panel_build.py` 的栈登记表 | 面板栈声明（E2）—— 形状在 `ext_combat.panel` |
| `action_base_fn` | `content/rules/action_base.json` 的 `cast` 表 | 行动类别 → 第一段基准耗时（刻）|
| `recover_base_fn` | `content/rules/action_base.json` 的 `recover` 表 | 行动类别 → 第二段基准耗时（刻）|
| `route_miss_text_fn` | `content/miss_text.py`（槽位 `SYS_CMD_MISS`） | 路由未命中的回话（P-54 · 引擎**必需注入**，不装 ⇒ 玩家敲错一个词一句话都拿不到）|
| `guard_text_fn` | `content/guard_text.py`（槽位 `SYS_GUARD_REGISTER` / `SYS_GUARD_BATTLE`） | 内置守卫（`player` / `battle`）拦下时的回话（P-11 · 宿主只传**中性键**，句子在本包 texts 域）|
| `recover_model_fn` | 委托声明 `F6_act_time` | 第二段的时间模型（与第一段同一形状）|
| `cue_subs_fn` | `content/cues.py::cue_subs`（订阅表**装配期从引擎 `CUE_NAMES` 现生成**）| 表现事件（cue）订阅：引擎侧 cue 迁移下，已迁移点位的那一行由本包渲染（不装 = 引擎走旧路）|

★ 零双源纪律：本文件不手写任何公式或常数；钳位归声明的 `guard`/`clamp`，
本文件只负责喂变量。速度形状是内容侧的选择（宪法 F6），不是引擎规则。
"""
from __future__ import annotations

import json
from pathlib import Path

from saintess_engine import config
from saintess_engine.formula import FormulaTable

_RULES = Path(__file__).resolve().parent.parent / "content" / "rules"

_TABLE = None
_BINDINGS = None
_ACTION = None
_MOUNTED = False


def _table() -> FormulaTable:
    """装配期读一次、校验一次（`from_decl` 跑 V1–V12，声明错当场抛）。"""
    global _TABLE
    if _TABLE is None:
        decl = json.loads((_RULES / "formula_table.json").read_text(encoding="utf-8"))
        _TABLE = FormulaTable.from_decl(decl)
    return _TABLE


def _bindings() -> dict:
    global _BINDINGS
    if _BINDINGS is None:
        _BINDINGS = json.loads((_RULES / "formula_bindings.json").read_text(encoding="utf-8"))
    return _BINDINGS


def _time_model(spd, base):
    """`time_model_fn` 供体：委托声明 `F6_act_time`（钳位在声明的 `guard` 里，本函数不重复钳）。"""
    return _table().eval("F6_act_time", {"base": float(base), "spd": float(spd or 0)})


def _action() -> dict:
    global _ACTION
    if _ACTION is None:
        _ACTION = json.loads((_RULES / "action_base.json").read_text(encoding="utf-8"))
    return _ACTION


# ★★ E4 声明口：`expr_vars_fn` —— 「公式表用到的变量名」由**本包自己声明**
#   （引擎 E4 把表达式变量表从「引擎写死 13 名」改成「内容侧声明」，内容侧一声明**整表替换**）。
#
#   为什么必须有（2026-09-29 · 本车道 P0 实测）：引擎 `aff3712` 起 `compile_expr` **按变量名校验**
#   （审计 L1281 #3，写错的变量名装配期就抛）。而本包 `content/rules/formula_table.json` 的
#   13 条条目引用了 31 个**不在默认 13 名表里**的名字（`pene_pct` / `pene_flat` / `def_eff` /
#   `K` / `heal_pow` / `var_roll` …）⇒ 装配方 `F1_eff_def` 第一条就抛 `FormulaDeclError`
#   ⇒ **本包 63 支探针里 60 支在 import 期就死**（连 `load_stack` 都进不去）。
#
#   ★ **取值来源为什么是「入参优先、属性兜底」**（这一条是实测定的，别照抄默认表）：
#   公式表**不**走 `expr.build_vars` 那条路。查全部消费端只有两处：
#     ① 引擎 `ext_combat/battle/formulas.py::calc_damage` → `_tbl.run('damage_full', _v)`，
#        `_v` 是**调用点现攒的完整 dict**（`level` / `def` / `pene_pct` / `mitigation` … 全在里面）；
#     ② 本包 `content/mech.py` → `.eval('F8_heal'/'F10_block_mit', {...})`，同样传完整 dict。
#   而 `build_vars`（技能/装备/食物那条路）**只认四个具名入参**（`player_lv`/`skill_lv`/
#   `target_max_hp`/`base`）—— 实测本包**没有**任何技能/装备公式引用这 31 个名字
#   （扫 `content/data/*.json` 的 `expr` 字段 = 0 命中）⇒ 那条路上这 31 个变量恒取 0
#   **是设计内的**（它们只服务于公式表，不服务于技能公式）。
#   声明里仍给 `else → stat` 兜底：某天真有内容侧按名字取属性时，缺了它会**静默算成 0**
#   （引擎 `_value_of` 对缺键 `or 0`），而我们要的是「取到真值」或「当场红」。
def _expr_vars() -> dict:
    """本包声明的表达式变量表（引擎 `expr_vars_fn` 供体）。

    以引擎默认表为底，**逐条补上**本包公式表用到、而默认表没有的名字 ——
    名单不手打，从 `formula_table.json` 现解析（条目 `vars` / `guard` / `params.expr` /
    `expr` / `item_expr` / `combine` / 链式 `steps`），⇒ 公式表加一条公式引了新变量，
    这张表下一轮 `install_engine` 自动跟上，不会又红在「变量表里没有的名字」。
    """
    import re
    from saintess_engine.expr import _DEFAULT_EXPR_VARS

    decl = json.loads((_RULES / "formula_table.json").read_text(encoding="utf-8"))
    entries = decl.get("entries", decl)
    names = set()
    for _eid, e in entries.items():
        if not isinstance(e, dict):
            continue
        names |= set(e.get("vars") or [])
        if isinstance(e.get("guard"), dict):
            names |= set(e["guard"])
        for _f in ("expr", "item_expr", "combine"):
            if isinstance(e.get(_f), str):
                names |= set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", e[_f]))
        params = e.get("params")
        if isinstance(params, dict):
            names |= _names_in_params(params)
        steps = e.get("steps") or []
        for st in steps:
            if not isinstance(st, dict):
                continue
            if isinstance(st.get("guard"), dict):
                names |= set(st["guard"])
            if isinstance(st.get("params"), dict):
                names |= _names_in_params(st["params"])
        # ★ 链式条目：**前一步的 `id` 就是后一步表达式里的变量名**
        #   （`damage_full` 的 raw → after_amp → … → final，一条接一条算）。
        #   漏了这一族 ⇒ 第一条带 `expr` 的 step 就报「变量表里没有的名字 'raw'」
        #   （2026-09-29 实测：13→42 之后仍红在 `damage_full` 的 `raw`）。
        for st in steps:
            if isinstance(st, dict) and isinstance(st.get("id"), str):
                names.add(st["id"])
        # ★ `random`：引擎**唯一**的随机来源（F2 波动）。它在 `_inject_random` 里
        #   **运行期**写进 `local`（`local[rnd['key']] = uniform(-pct, pct)`），
        #   但名字仍要先在变量表里在位，否则 `compile_expr` 的按名校验会先红
        #   （2026-09-29 实测：50 名之后红在 `damage_full.final` 的 `var_roll`）。
        #   声明里给 0 兜底即可 —— 真实值永远由引擎那一行覆盖。
        if isinstance(e.get("random"), dict) and isinstance(e["random"].get("key"), str):
            names.add(e["random"]["key"])

    tbl = dict(_DEFAULT_EXPR_VARS)
    for n in sorted(names - set(tbl)):
        src = {"from": "input", "key": n}
        if n == "level":
            # 公式表里的 `level` 语义 = 等级；`build_vars` 的具名入参叫 `player_lv`
            src = {"from": "input", "key": "player_lv", "else": {"from": "stat", "key": "level"}}
        else:
            src["else"] = {"from": "stat", "key": n}
        tbl[n] = {"label": n, "source": src}
    return tbl


def _names_in_params(params: dict) -> set:
    """`params` 段里出现的变量名（含 `expr` 表达式里的与 `ref` 指向的入参名）。"""
    import re
    out = set()
    for spec in params.values():
        if not isinstance(spec, dict):
            continue
        if isinstance(spec.get("expr"), str):
            out |= set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", spec["expr"]))
        ref = spec.get("ref")
        if isinstance(ref, str) and not ref.startswith("formula."):
            out.add(ref)
    return out


def _action_base_fn(action):
    """`action_base_fn` 供体：行动类别 → 第一段基准（刻）；未知类别落 `default.cast`。"""
    a = _action()
    return float(a["cast"].get(action, a["default"]["cast"]))


def _recover_base_fn(action):
    """`recover_base_fn` 供体：行动类别 → 第二段基准（刻）；未知类别落 `default.recover`。"""
    a = _action()
    return float(a["recover"].get(action, a["default"]["recover"]))


def _recover_model(spd, base):
    """`recover_model_fn` 供体：第二段时间模型 = 与第一段同一形状（F6）。"""
    return _table().eval("F6_act_time", {"base": float(base), "spd": float(spd or 0)})


def _basic_name() -> str:
    """兜底普攻那条技的名字 —— 走 texts 槽位（★ B4-19：这一格原先写死「挥击」）。"""
    from .cmds_ast import T                    # ★ B4-19：本地 import（免得包装载期成环）
    return T("SYS_BASIC_NAME")


def install_engine():
    """把本包的 hook 挂进引擎 config（全局一次、幂等）。"""
    global _MOUNTED
    if _MOUNTED:
        return
    # ★ 顺序要紧：`expr_vars_fn` **必须先挂**，`_table()`（下面第一行）才会拿着
    #   本包声明的变量表去编译那 13 条公式 ⇒ 反过来就是「先编译、后声明」⇒
    #   编译期看不到本包的变量名 ⇒ 第一条就抛（2026-09-29 实测踩过）。
    config.mount(expr_vars_fn=_expr_vars)
    tbl = _table()
    bind = _bindings()
    from ext_combat.battle import formulas as _formulas   # 引擎自带纯公式模块（引擎侧，非内容）
    from . import skills_lookup as _SL                     # 技能取件口 + kind 词表（同一份真源）
    from . import mech as _MECH                            # ★ fxmech：E5/E6 两条供体在这个模块里
    from . import cues as _CUES                            # ★ cue 订阅表（引擎侧 cue 迁移的内容半边）
    config.mount(
        formulas=_formulas,                     # ★ 缺了它引擎走 _NullFormulas：伤害算不出来
        # ★ E4 声明口 `expr_vars_fn` 在**上一行之前**就挂好了（`_table()` 要先编译公式，
        #   变量表必须先在位）；这里不重复挂，挂两次没意义。
        formula_table_fn=lambda: tbl,
        formula_bindings_fn=lambda slot: bind.get(slot),
        time_model_fn=_time_model,
        action_base_fn=_action_base_fn,
        recover_model_fn=_recover_model,
        recover_base_fn=_recover_base_fn,
        panel_layers_fn=_panel_layers,
        # ★ 技能取件口（缺了引擎索引不到技能 ⇒ 玩家/怪「静默空放」默认技）
        skill_lookup=_skills_mod(),
        monster_skill_fn=_monster_skill,
        basic_skill_fn=_basic_skill,
        # ★ B3-14：**引擎 kind 词表**（`content/rules/kinds.json`）—— 缺了它
        #   `game_config.kind_of("phys")` 一律回空串 ⇒ 引擎把每条攻击都判成魔法
        #   （吃 matk 不吃 atk）、治疗/增益技落进伤害支。值不在这里写死：整份从 rules 读。
        kinds=_SL.kinds(),
        # ★ 兜底普攻的**类别值**不写死中文枚举（B3-6b-2d-b）—— 从 kinds 词表现取
        #   （`basic_kind()` = 物理，fail-closed）。空串会被引擎判成「治疗」（`actions.py:110`）。
        #   B3-14：这条兜底同时是**怪物普攻**（怪没有 class_name ⇒ 走它），它必须带 `exprs`
        #   并走物理通道 —— 否则怪伤害恒为下限 1（matk=0 走魔法支）。
        #   `name`（SYS_BASIC_NAME）是「这条兜底技叫什么」的文案 —— ★ B4-19 已进 texts 槽位。
        # ★ fxmech（2026-09-26）：技能 dict 自己声明的那两段耗时（E5）—— 引擎在
        #   「排落地时刻」与「推下一次能动的时刻」两处问同一个口（落地与到点同源）；
        #   **不挂 = 与接线前逐字相同**（引擎落回 `action_base.json` 的类别基准）。
        #   供体 = `content/mech.py::segment_plan`（技能那一路 + 普攻那条 basic 技能那一路）。
        segment_plan_fn=_MECH.segment_plan,
        # ★ fxmech（2026-09-26）：「出手前的通用否决口」（E6 · 与 mp_gate_fn 同形状）——
        #   管两件真源写明、而运行期一直没人管的事：狂斩的**血线门**（「血 < 12% 时这一手
        #   不可用」）与焚身的**每场一次**（「一场战斗最多一次」）。判据与回话全在
        #   `content/rules/skill_mech.json` 的声明 + `content/mech.py::skill_gate`；
        #   **不挂 = 那两条不存在**（不拦、不回，与接线前逐字节相同）。
        skill_gate_fn=_MECH.skill_gate,
        basic_fallback={"name": _basic_name(), "kind": _SL.basic_kind(), "power": 1.0, "cd": 0,
                        "exprs": ["atk*1"],
                        "cast": {"base": 60}, "recover": {"base": 0}, "range": 1, "mp": 0,
                        "_basic": True},
        # ★ cue（2026-09-27）：表现事件（引擎把「结算里顺手拼玩家文案」改成发 cue）——
        #   已迁移点位的那一行由**本包订阅者**渲染，措辞仍在 texts 域（`battle_text.json`）。
        #   订阅表**不在这里写**、也不是手抄名单：`content/cues.py::cue_subs` 在装配期
        #   现读引擎的 `CUE_NAMES` 生成 ⇒ 引擎每加一条点位，本包自动跟上；那条点位在本包
        #   没有对应文案格时，装配期当场点名抛（`CueSubsError`，绝不静默丢那一行）。
        cue_subs_fn=_CUES.cue_subs,
    )
    # ★ 反「静默不装」（同 route_miss / guard_text 那两条）：`config.set_hook` 对**不认识的名字
    #   静默忽略 ⇒ 装完回读一次。★ 只在引擎树**真有 cue 形状**时才要求（`ext_combat.battle.cues`
    #   导得进来）：引擎树没有这个形状时（旧检出）本包照跑 —— 那种引擎上战斗日志本来就不经过 cue，
    #   不能因为「引擎版本旧」把整包拦死。
    if _CUES.engine_has_cues() and config.optional_hook("cue_subs_fn") is None:
        raise config.EngineNotConfigured(
            "cue_subs_fn 没装配上：引擎认识 cue 形状，却不认这个口（引擎 config 版本旧？）")
    # ★ B3-27：机制那两张表 —— 「技能 mech 名词 → 引擎动词」（EFFECT_ACTIONS）与
    #   「状态语义」（EFFECT_RULES）。声明表**不能走 mount**（走的是 `load_game_rules`）。
    #   同一张真源：`content/rules/skill_mech.json`；出口只有一个：`content/mech.py`。
    #   不挂这两张表 ⇒ 名词查空表、`mech_val` 那道门照旧关着 ⇒ 与接线前**一字不差**
    #   （探针有反证那一条）。
    from ext_combat.battle import game_config as _GC
    from . import mech as _MECH
    _GC.load_game_rules(_MECH.rules_module())
    # ★ 跨域对账（装配期 fail-closed）：域里每条技能声明的机制都得在表里 ——
    #   不认得的当场抛并点名是哪条技能（绝不静默空放）。
    _MECH.check_domain()
    # ★ P-1（元素通道）：两样都在装配期对账，答不上来当场抛 ——
    #   ① 域里每个 `element` 码都得在 `content/rules/elements.json` 里声明过
    #      （没声明过 ⇒ 引擎那条线静默按「无元素」走；这就是「元素表看着有、代码没消费」
    #       的常驻判据）；同一条也顺带核样例挂在**真有的**怪上；
    #   ② 战斗日志槽位声明的槽位都得在 texts 域里取得到（缺了**不兜一句自造的话**）。
    from . import battle_text as _BT
    from . import elements as _ELE
    _ELE.check_domain()
    _BT.check_slots()
    # ★ 职业资源渠道（B4-1 那批只写了 `res_gain` / `res_cost` 声明，这里是它的消费端）：
    #   装配期核「域里每条技能声明的资源码都在 resources.json 里」+「一个职业只挂一条资源」——
    #   答不上来当场抛（认不得的资源不许静默不涨）。数据表本身由 `content/resources.py` 现读。
    from . import resources as _RES
    _RES.check_domain()
    # ★ P-51（2026-09-26）法力渠道：**基础回复 + 蓝不够就拦**两个入口（引擎 `a49422a` 已开好，
    #   未装配 = 与接线前逐字节相同）。数值全在 `content/rules/mana.json`（唯一真源），
    #   本包只把两个供体挂上 —— 引擎零数值、零玩家文案：
    #     · `mp_regen_fn` —— 每次时间推进结算问一次「这一拍回多少」（每刻问 · 多久回一次
    #       由内容侧按 `battle._now` 自己判）；
    #     · `mp_gate_fn`  —— 出手前问一次「这一手放不放」（不够 ⇒ 拦下 + 一句玩家看得见的话）。
    #   那句拦下的话走 texts 槽位（`gate.slot`，已有槽位 `COMBAT_RES_LACK`）—— 代码里零文案。
    from . import mana as _MANA
    _MANA.check_domain()
    if _MANA.installed():
        config.mount(mp_regen_fn=_MANA.regen_amount, mp_gate_fn=_MANA.gate_line)
    # ★ P-54（2026-09-26）「路由未命中」的回话：引擎把这一句改成**必需注入**了 ——
    #   `Host.route()` 没接住玩家敲的那个词时去问 `route_miss_text_fn`；
    #   **没装配（或装了给不出文本）⇒ 抛 `EngineNotConfigured`**
    #   （引擎不自己编一句中文、也不提任何宿主命令名 —— 原先那半就是这么收掉的）。
    #   ⇒ 本包不挂这个口，玩家敲一个没命中的词就是**一句话都拿不到**（不是「回得不好」）。
    #   那一句在 texts 域（槽位 `SYS_CMD_MISS`），代码里零中文：本件只传槽位名 + 把玩家敲的
    #   那个词嵌进去；「指向哪条指令」也归槽位（`content/miss_text.py::referenced_commands`）
    #   —— 代码里不写死「它指的是帮助」。
    #   ★ 装配期对账（fail-closed）：槽位在不在 + 那句引号里指向的指令是不是本包**可见**
    #     声明里的那一个（指向一条不存在的指令 = 把玩家支去再撞一次空）⇒ 答不上来当场抛。
    from . import miss_text as _MISS
    _MISS.check_domain()
    config.mount(route_miss_text_fn=_MISS.line)
    # ★ 反「静默不装」：引擎 `config.set_hook` 对**不认识的名字静默忽略** ⇒ 装完回读一次：
    #   读不回来 = 引擎不认识这个口（版本旧）—— 症状是「玩家敲错一个词直接抛」，要等上线
    #   才照得出来（真机才照得出的那一类），所以在这里当场现形。
    if config.optional_hook("route_miss_text_fn") is None:
        raise config.EngineNotConfigured(
            "route_miss_text_fn 没装配上：引擎 config 不认识这个口（引擎版本旧？）")
    # ★ P-11（2026-09-27）内置守卫（`player` / `battle`）拦下时的回话：**句子搬进包**了 ——
    #   宿主 `main.py` 那两个参数改传**中性键**（引擎 `host/runtime.py::GUARD_KEYS`：
    #   `guard.register_missing` / `guard.battle_missing`），句子由本包 texts 域渲染
    #   （宿主面因此零游戏词，宿主自己的 `check_host_boundary.py` 才可能全绿）。
    #   引擎那一头三态 fail-closed：装了本口 ⇒ 那个值当键用（答不上来当场抛）；
    #   没装本口 ⇒ 值当字面量（老宿主逐字不变），但值**恰好是中性键** ⇒ 抛。
    #   ⇒ 本包不挂这个口，宿主传的那两个键就**当场抛**（引擎既不编兜底、也不把键投给玩家）。
    #   ★ 装配期对账（fail-closed）：映射的键集 == 引擎的中性键全集 + 两条槽位都真有字
    #     （缺一条 ⇒ 守卫拦下时玩家拿到的是抛错，不是一句人话）。
    from . import guard_text as _GUARD
    _GUARD.check_domain()
    config.mount(guard_text_fn=_GUARD.line)
    # ★ 反「静默不装」（同 route_miss 那条）：`config.set_hook` 对**不认识的名字静默忽略**
    #   ⇒ 装完回读一次：读不回来 = 引擎不认识这个口（版本旧）—— 症状是「守卫一拦就抛」，
    #   要等线上才照得出来，所以在这里当场现形。
    if config.optional_hook("guard_text_fn") is None:
        raise config.EngineNotConfigured(
            "guard_text_fn 没装配上：引擎 config 不认识这个口（引擎版本旧？）")
    _MOUNTED = True


def _skills_mod():
    """技能查询模块对象（引擎按属性取 .skill_info / .skill_by_key）。"""
    from . import skills_lookup
    return skills_lookup


def _monster_skill(key):
    from . import skills_lookup
    return skills_lookup.monster_skill(key)


def _basic_skill(class_name):
    from . import skills_lookup
    return skills_lookup.basic_skill_of(class_name)


def apply_game_content(actor):        # noqa: ARG001 —— 最小骨架阶段暂无 actor 级内容
    """单个 actor 的装配（第二阶段为空；职业/机制待后续轮次）。"""
    return None

def _panel_layers(stack_id):
    """`panel_layers_fn` 供体：栈 id → 面板栈声明（内容侧现算并登记，引擎当不透明字符串）。"""
    from . import panel_build
    return panel_build.stacks().get(stack_id)


# ══════════════════════════════════════════════════════════════
# 新玩家初始档（引擎 `Package.initial_save(uid, ctx)` 调它）
# ══════════════════════════════════════════════════════════════
def initial_save(uid: str, ctx: dict | None = None) -> dict:
    """第一次来的人在哪儿、有什么。

    ★ 起始位置 = 风车镇北口（玩家第一眼看到的就是那块刻字的石头）。
    ★ 30 枚铜板是一个人在镇上活三天的钱（住店 8 / 一顿饭 2）；给多了镇子就没意义了。
      —— ★ P-55：那两个数里「住店」那一口从本批起**有机器可读的一格**了：
      `content/rules/inn.json`（`content/inn.py::fee()` 现读）就是照这句账定的 8
      （3 × 8 + 3 × 2 = 30）；要调住店价只改那一格，别改这句注释（注释只是由来）。
    ★ P-27：**不写 `hp` / `hp_max`** —— 生命上限只有一个来源（职业面板），由 `cmds_ast._p`
      出档时按面板派生（原先这里与 `cmds_ast.DEFAULT_PLAYER` 各写死 100 ⇒ 两个源，
      而且没有任何升级 / 换装钩子刷它）。
    ★ B4-8：`mo` / `mo_max` 同理撤掉 —— 法力上限同样只由面板派生（`panel_build.mp_cap`）；
      原先两处各写死 0 ⇒ 骑士面板 50 点法力，`状态` 却恒显示「法力 0/0」。
    """
    return {
        "name": "", "race": "", "cls": "", "level": 1, "exp": 0,
        "loc": "windmill_town", "node": "wt_gate_n", "prev": [],
        "gold": 30, "bag": {}, "equipped": {}, "flags": {}, "codex": {},
    }
