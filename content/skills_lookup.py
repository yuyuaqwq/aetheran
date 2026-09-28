# -*- coding: utf-8 -*-
"""《阿斯特兰》技能查询（引擎注入面的供体）—— 技能表 + 怪技能 + 普攻兜底。

引擎的取件口（`saintess_engine/config.py` 的钩子）：
    skill_lookup     模块对象，引擎按属性取 `.skill_info(class_name, key)` / `.skill_by_key(key)`
    monster_skill_fn 怪技能（本包 monsters 域里各怪带的技能）
    basic_skill_fn   职业普攻配置（没带技能时的第一选择）
    basic_fallback   普攻兜底（内容名）
    kinds            引擎 kind 词表（`content/rules/kinds.json`）

★ 为什么必须有：缺了这几口，引擎 `_index_one_actor` 索引不到技能 ⇒ 玩家/怪「静默空放」，
  实测症状是双方都拿默认技（挑成了「圣光治愈」）打了 2000 条日志还打不完。

★ B3-14（2026-09-25）第二件：**`skill_info` 是「域 → 引擎」的翻译口**，它要干两件事
--------------------------------------------------------------------------
① **kind 换语义**：域里 `kind = 主动` 是**技能类别**（主动/被动…），而引擎的 `kind` 是
   **行动语义**（物理/魔法/真伤/治疗/增益）—— 引擎靠它分成「治疗 / 增益 / 伤害」三支，
   并据此选防御通道（phys→def · magi→mdef · true→无视）。两个是不同轴，不能混用。
   ⇒ 域里新加 `kind_override`（取值 = `kinds.json` 那 5 个值，由
     `scripts/rebuild_skills.py` 从 `power` × 职业伤害通道算出来），本口把它顶上 `kind`。
   ★ 没顶之前（B3-14 实测）：域里 30 条全是「主动」⇒ 引擎把**每条攻击**都判成魔法
     （`actions.py:_skill_seg_damage` 的 kind 三分支），骑士 atk 51.6 白给、法师 matk 84 一发放倒田鼠。
② **fail-closed**：`kind_override` 不在 `kinds.json` 的值域里 ⇒ **当场抛**（点名哪条技能）。
   绝不回空串：空串会被引擎判成「治疗」（`actions.py:110` 那条 `kind == _kind("heal")`）。
"""
from __future__ import annotations

import json
import os

from . import elements as ELE                    # ★ P-1：元素码 → 引擎元素名（同一份声明表）

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_RULES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules")
_C: dict = {}

#: 引擎那份 kind 词表的键（`ext_combat/battle/actions.py` 比对的 5 个语义名）
KIND_NAMES = ("phys", "magi", "true", "heal", "buff")

#: 上面那 5 档里**吃「指定目标」**的一档（伤害三通道）—— 治疗 / 增益不吃（★ fix-j）。
#: ★ 键也是**引擎语义名**（不是域内用词），域内用词由 `kind_value()` 现算 ⇒ 代码里不写中文枚举。
TARGET_KINDS = ("phys", "magi", "true")


def _load(name: str):
    if name not in _C:
        with open(os.path.join(_DIR, name + ".json"), encoding="utf-8") as f:
            _C[name] = json.load(f)
    return _C[name]


def skills() -> dict:
    return _load("skills")


def classes() -> dict:
    return _load("classes")


def monsters() -> dict:
    return _load("monsters")


def kinds() -> dict:
    """引擎 kind 词表（真源 = `content/rules/kinds.json`；代码里不写死这 5 个中文值）。"""
    if "kinds" not in _C:
        with open(os.path.join(_RULES, "kinds.json"), encoding="utf-8") as f:
            _C["kinds"] = {k: v for k, v in json.load(f).items() if not str(k).startswith("_")}
    return _C["kinds"]


def kind_value(name: str) -> str:
    """引擎语义名 → 域内用词。没这个语义名 ⇒ 抛（不猜）。"""
    k = kinds()
    if name not in k:
        raise KeyError("kinds.json 里没有语义名 %r（有的：%s）" % (name, " · ".join(sorted(k))))
    return k[name]


def engine_kind(rec: dict) -> str:
    """域里那条技能 → **给引擎看的 `kind`**（= `kind_override`）。fail-closed：缺/非法 ⇒ 抛。"""
    v = rec.get("kind_override")
    vals = set(kinds().values())
    if v not in vals:
        raise KeyError(
            "技能 %r 的 `kind_override` = %r 不在 kinds.json 的值域里（有的：%s）"
            "—— 跑 `python scripts/rebuild_skills.py` 重算" % (rec.get("name") or rec, v, " · ".join(sorted(vals))))
    return str(v)


def takes_target(rec: dict) -> bool:
    """这条技能**吃不吃「指定目标」** —— 只有伤害那一档吃，治疗 / 增益不吃（★ fix-j）。

    ★ 为什么按这条轴分档：引擎 `actions.do_skill` 的分派就是它 ——
      `kind == 治疗` ⇒ `_do_heal`（`target` = **受疗对象**，缺省施法者自己）；
      `kind == 增益` ⇒ `_do_buff`（`target` = 挂机制的落点，内容侧那几条 `route=cast`
      的机制一律挂**施法者**自己）；**其余**（伤害三通道）⇒ 拿 `target` 当**打击对象**。
      ⇒ 「集火」锁着的那一格是**敌方 actor**，它只对**打击对象**这一档合法。
      真源：`04_指令总表 §五`「集火 <目标> | 多人时指定」· `17_组队与策略配合 §三·8`
      「集火 —— 一起**打掉**一个」。

    与 `engine_kind` **同一格**（同一份 `kind_override`、同一条 fail-closed：缺 / 非法 ⇒ 抛）——
    不另抄一份「哪些算攻击」的名单；哪几档吃目标只有一个来源 =
    `TARGET_KINDS`（引擎语义名，配 `kinds.json` 现算域内用词）。
    """
    return engine_kind(rec) in {kind_value(n) for n in TARGET_KINDS}


def _norm_class(class_name: str | None) -> str | None:
    """职业名或 id 都收（`骑士` 或 `cls_knight`）—— **认不出就抛**（★ 审计 L3408）。

    ★ B3-6b-2d-b 复核：这是**入参解析**（中文名 → 机器键），不是「拿中文枚举当机器键」——
      与 `loot.match_ids` / `去 <地方>` 同一族（玩家/调用方给的是名字）。
      机器键本身（`owner_class` / actor 的 `class_name`）一律是 ASCII `cls_*`。

    ★ L3408 原先的末行是 `return class_name`（**认不出就原样吐回去**）：职业名写错 /
      存档脏 / 上游拼错一个字母时，`basic_skill_of` 拿它去筛 `owner_class` 恒筛不到
      ⇒ 返回 `None` ⇒ 引擎 `resolve_basic_skill` 回落 `basic_fallback`
      （普攻「挥击」）⇒ **玩家看不出来**，只看到「我怎么打不出职业技能了」。
      口径与同文件 `kind_value` / `engine_kind` 统一（认不出 ⇒ 抛，点名合法值）。

    ★ `None` / 空串**不是**「认不出的职业」：怪没有 `class_name`（引擎
      `resolve_basic_skill` 会拿 `None` 来问），那是合法的一态，照旧返回 `None`。
    """
    if not class_name:
        return None
    cs = classes()
    if class_name in cs:
        return class_name
    for k, v in cs.items():
        if v.get("name") == class_name:
            return k
    known = " · ".join(sorted(cs))
    names = " · ".join(sorted(str(v.get("name")) for v in cs.values()))
    raise KeyError(
        "classes.json 里没有职业 %r（机器键有的：%s；中文名有的：%s）"
        % (class_name, known, names))


def basic_kind() -> str:
    """普攻兜底那条的通道值（物理）—— 唯一来源 = `kinds.json`（代码不写死中文枚举）。"""
    return kind_value("phys")


def _to_engine(v: dict) -> dict:
    """域里那条记录 → 引擎消费的那一份（浅副本 + kind 与 element 换语义）。

    ★ P-1：`element` 也得翻 —— 域里是 `ELE_FIRE` 这种**码**，而引擎落地层
      （`ext_combat/battle/landing.py` 的免疫/弱点表 + `res_fire` 那一族抗性键）认的是
      `fire` 这种**名**。原先这格是**原样透传**的：码进了引擎、而承伤方的免疫/弱点表
      一个都没挂 ⇒ 谁都没发现它没生效（「表看着有、代码没消费」）。
      ⇒ 翻名走 `content/elements.py`（唯一映射处，码没声明过**当场抛**，不静默当无元素）。
      「明确不入环」的码（物理 / 域里那两个宪法没定义的档）翻成空串 ⇒ 引擎那整支不进，
      与接线前**逐字相同**。
    """
    out = dict(v)
    out["kind"] = engine_kind(v)
    out["element"] = ELE.element_of(v)
    return out


def skill_info(class_name: str, skill_name: str):
    """技能详情（返回**浅副本** —— 引擎会把返回值放进 actor 的运行时索引，
    战斗内机制会改写它；原样返回表条目 = 一次施放永久改写全表）。"""
    sk = skills()
    cls = _norm_class(class_name)
    key = skill_name
    if key in sk:
        v = sk[key]
        if cls and v.get("owner_class") not in (None, cls):
            return None
        return _to_engine(v)
    for k, v in sk.items():                       # 中文名路
        if v.get("name") == skill_name and (not cls or v.get("owner_class") in (None, cls)):
            return _to_engine(v)
    return None


def skill_by_key(key: str):
    v = skills().get(key)
    return _to_engine(v) if isinstance(v, dict) else None


def monster_skill(key: str):
    """怪技能：本包把怪技挂在 monsters 域的 skills 列表里（当前只给 id，名字即 id）。

    ★ B3-14：怪技能一律走**物理通道**（域里那些 `ms_skill_*` 没有记录、也无从谈魔法）——
      原先给的是 `kind = "主动"`，配上没挂的 kinds 词表 ⇒ 怪物伤害恒为下限 1
      （matk=0 的怪走魔法支，`calc_damage(0, …)` 保底 1 点）。物理通道下它吃怪的 `atk`
      （真源 `12_怪物面板与精英词条池_v1.md`：`怪 atk = 玩家标准 HP / (18 × (1−玩家DR) × 暴击乘区)`
      ⇒ 普通怪打玩家 18 次才打死）。
    """
    for mid, m in monsters().items():
        for sid in (m.get("skills") or []):
            if sid == key:
                return {"name": key, "kind": basic_kind(), "power": 1.0, "cd": 0,
                        "exprs": ["atk*1"], "owner_monster": mid, "_basic": False}
    return None


def basic_skill_of(class_name: str):
    """职业普攻：本职业那条标了 `basic` 的（域里唯一一口；无则 `None` → 引擎回落兜底）。

    ★ B3-14 之前是按 `power` 升序取「最低的那条」—— 那条判据把**辅助技**当成了普攻：
      骑士取到盾墙(0.0)、刺客/游侠取到后撤(0.0)、修女取到净罪(0.0)。
      「哪条是普攻」是设计决定（`02_技能体系规划_v1.md` §五「普攻 + 第一条主动」）⇒ 落成域里的
      `basic: true`（由 `scripts/rebuild_skills.py` 写），不在代码里猜。
    """
    sk = skills()
    cls = _norm_class(class_name)
    if not cls:
        return None
    mine = [(v.get("lv", 1), k) for k, v in sk.items() if v.get("owner_class") == cls and v.get("basic") is True]
    if not mine:
        return None
    mine.sort()
    v = _to_engine(sk[mine[0][1]])
    v["_basic"] = True
    return v


# ★ 2026-09-28 审计 B 车道高③ —— **两个零消费者的死出口，本批删掉**（不留兼容壳）。
#
#   原先这里有两行「看着像接线、其实谁也没调」的函数：
#       def skill_level_of(actor, skill_name): return 1 if skill_name else 0
#       def skill_up(actor, skill_name, n=1):  return None
#   删它们的理由（三条都实测过，不是推断）：
#     ① **零挂载**：`git grep skill_level_of_fn / skill_up_fn` 在本包 = 0 处 ——
#        引擎认的那两个 hook（`saintess_engine/config.py:58-60`）本包**从来没装过**。
#     ② **零消费端**：本包唯一读技能等级的那一处（`content/mech.py:779`）走的是
#        **引擎**的转发位 `GC.formulas().skill_level_of(...)`，不是这里这个函数。
#        留着它 = 下一个读代码的人会以为「技能等级已经接好了」。
#     ③ **它自己就是那条静默降级链的源头**：引擎 `extends/ext_combat/battle/formulas.py::skill_level_of`
#        读 `skill_level_of_fn`，未装配就 `return 1` —— 技能等级恒按 1 级算。删掉本包这个
#        恒 1 的假实现，降级链的那一半就断在这儿（**引擎那一半的 fail-closed 归车道 A/D**，
#        见本批报告；本车道不碰引擎仓）。
#
#   ★ 为什么不「在这里装一个真实现」：本包**没有技能等级这个玩法**。三处取证 ——
#     · 玩家档上没有 `skill_levels` 那一格（全包 0 处）；
#     · `content/data/skills.json` 里那 48 条的 `lv` 是**解锁等级**（`cmds_skill._of_class` /
#       `combat._default_skills` 都按它分「学会了 / 还没到等级」两拨），不是成长等级，
#       拿它当等级填进去 = 把「几级能学」错当成「这条技几级」；
#     · 真源里没有这一条口径：`aetheran-plan` 全树搜「技能等级/技能成长/技能点」只命中
#       `02_数值宪法/_旧案参考/`（旧案调研材料）三处，不是在线规格。
#     另外实测：即便把等级接上，本包今天**一个数都不会变**（`skill_power_mult` 的 `p` 来自
#     未装配的 `skill_up_fn` ⇒ 恒 1.0；48 条技能没有一条带 `effect` / `buff_turns`，
#     `_do_buff` 那条支走不到）。所以**不装**：真要开这个玩法，得先有真源口径。
#     —— 真要开的时候，装的是 `skill_level_of_fn`（引擎认的那个名字），不是这里这两个。

