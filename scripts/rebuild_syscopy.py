# -*- coding: utf-8 -*-
"""syscopy 落域脚本（B3-6b）：把「系统与移动」那批文案从口径文档解析进 texts 域。

源（唯一真源）：`00_总纲/17_文案收口口径_v1.md` 的槽位表（后续批继续往那份表加）
落点：`content/data/texts.json`（文案真源表）

规矩：
  · 只**新增**缺失的槽位；已存在的槽位必须**逐字相同**（不同就抛 —— 防两处口径打架）
  · 保持原表插入序（K27：别 sort_keys，一排序就是近千行假 diff）
  · 末尾补一个换行 · LF 落盘
  · 连跑两次数据不变（幂等自检；第二次应报「无新增」）
  · 占位与 params **双向对账**（声明的要有占位 · 占位要声明过）

用法：python scripts/rebuild_syscopy.py [--dry]
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.environ.get("AST_PLAN", "C:/Users/yuyu/aetheran-plan")
DOC = os.path.join(PLAN, "00_总纲", "17_文案收口口径_v1.md")
TEXTS = os.path.join(REPO, "content", "data", "texts.json")

#: ★ B4-16 起 `RANK_*` 也在这一族里（公会评级那几张档名 —— 键 = `RANK_<ASCII ID>`，
#:   拼法唯一在 `content/ranks.py::label_key`；档名本体是文案，所以它归 texts 域）。
KEY_RE = re.compile(r"^(SCENE|READ|NPC|COMBAT|QUEST|ITEM|SYS|TITLE|WORLD|HOUR|WEATHER|UNID|TALK|RANK)_[A-Z0-9_]+$")
PH = re.compile(r"\{(\w+)\}")
ROW_RE = re.compile(r"^\|\s*([A-Z][A-Z0-9_]*)\s*\|")

#: ★ g4-leftovers：**口径表待跟账**（真源那一行的值待主线改 · 两态互锁）。
#:
#:   为什么要有这一格：本脚本对已存在的槽位要求**逐字相同**（防两处口径打架），
#:   可这一轮要改的几条（建号那一步的玩家词 · `SYS_PAGE_NONE` 的列表候选）改的是**值**，
#:   而真源仓对本分支只读 ⇒ 不给这一格，就只有「换新槽位 + 退役登记」一条路
#:   （fix3 那次的走法），而那会给 texts 留一条永远没人读的旧句子。
#:
#:   口径（第三态当场抛 —— 「门禁只加强不削弱」）：
#:     · 表里那一格**要么**是旧值（主线还没跟账）· **要么**是新值（跟账后）；别的值 ⇒ 抛；
#:     · 落下时必须已经在域里（`add` 那一支不许借这一格混进来 —— 那会变成「表里没有、域里先有」）；
#:     · 域里那一条必须**逐字等于** `new`（旧值留在域里 ⇒ 抛）。
DOC_PENDING = {
    "SYS_CLS_NAME": {
        "old": "名字还没定 —— 打『改名 <名字>』，只改这一回。",
        "new": "名字还没定 —— 打『名字 <名字>』，只改这一回。",
        "why": "g4-③（P1 体验-1）：建号那一步的玩家词是『名字』（`04_指令总表` 的别名那一个，"
               "玩家照着敲得通），引导却把他指去『改名』—— 三处对齐（见分支 `_notes.md`）",
    },
    "SYS_REG_ASKNAME": {
        "old": "「叫什么名字？」—— 先打『改名 <名字>』，回头再来办证。",
        "new": "「叫什么名字？」—— 先打『名字 <名字>』，回头再来办证。",
        "why": "g4-③：同上（登记那一支也把『名字』递过去）",
    },
    "SYS_RENAME_ASK": {
        "old": "想叫什么？打『改名 <名字>』—— 一到八个字，只改这一回。",
        "new": "想叫什么？打『名字 <名字>』—— 一到八个字，只改这一回。",
        "why": "g4-③：同上（这条指令的 `usage` 也改成『名字』，『改名』留作别名）",
    },
    "SYS_PAGE_NONE": {
        "old": "先打开一个列表（『背包』看东西 ·『排行』看本群榜）—— 再敲『下一页』或『回 <页码>』。",
        "new": "先打开一个列表（{lists}）—— 再敲『下一页』或『回 <页码>』。",
        "why": "g4-④（P4 E-4 的另一半）：那句只点了『背包』『排行』两个列表，"
               "而分页今天有七列（`content/pager.py::LIST_KEYS`）—— 列表名从登记处现算，"
               "不再手打（见分支 `_notes.md`）",
    },
    "READ_TOWER_STELE_NAMES": {
        "old": "名字一排排往下刻。有三个，你在白桦林那棵树皮上见过 —— 重了。",
        "new": "名字一排排往下刻。刻痕很深，边角还利 —— 有几个名字眼熟，你想不起在哪儿见过。",
        "why": "g4-⑩（P2 BUG⑦ 时序）：旧那句对**没去过白桦林**的玩家也断言「你见过」——"
               "改成按真实经历分支：这一格是**没读过**白桦上那棵树名时的那一版，"
               "读过之后走变体槽位 `READ_TOWER_STELE_NAMES__POI_NAMED_BIRCH`（见分支 `_notes.md`）",
    },
    # ★ P0-1 批量登记（战斗时间轴 · **51 条**）—— 逐条 old/new 由脚本从
    #   「HEAD 的旧值 ↔ 域里的新值」现算，不手抄（手抄 52 条必漂）。
    #   ★ 撞上已有登记的那几条**不在这里**（见文件后面 P2-6 那几条已就地升链）——
    #     字典字面量里**后写的赢**，同键插两条会让先写的那条静默失效。
    "COMBAT_ACTIONS_EFFECT_ON": {"old": "✨ {key} 生效！", "new": "✨【{t:.0f} 刻】{key} 生效！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_ACTIONS_LIFESTEAL": {"old": "🩸 吸血：回复 {heal} 点生命！", "new": "🩸【{t:.0f} 刻】吸血：回复 {heal} 点生命！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_ACTIONS_SKILL_CAST": {"old": "【{t:.0f} 刻】你施展【{name}】！", "new": "⚔️【{t:.0f} 刻】你施展【{name}】！", "why": "P0-3（战斗族行首图标对齐 · 真源 26_ §2.2 emoji 语义分组 + §三 优化 1）："
               "上一轮 P0-1 给这 6 条加【N 刻】时**只加了刻、没给行首图标** ⇒ "
               "战斗族出现第二种行首形态（36 条 `图标【N 刻】…` / 这 6 条裸 `【N 刻】…`）。"
               "本批按 §2.2 逐条选图标：⚔️ 行动/攻击（施展）· ✨ 成功/强化（治疗）· "
               "✔ 结束 · ⚠️ 预警（无可行动者 / 未知行动）。"
               "★ `old` 与 `new` 逐字只差一个行首图标 —— 统一形态，不改语义措辞。"
               "★ 引擎零改动；读端与取件逻辑一字未动；params 无变化。"},
    "COMBAT_ACTIONS_SKILL_HEAL": {"old": "【{t:.0f} 刻】你施展【{name}】，治愈了 {heal} 点生命！", "new": "✨【{t:.0f} 刻】你施展【{name}】，治愈了 {heal} 点生命！", "why": "P0-3（战斗族行首图标对齐 · 真源 26_ §2.2 emoji 语义分组 + §三 优化 1）："
               "上一轮 P0-1 给这 6 条加【N 刻】时**只加了刻、没给行首图标** ⇒ "
               "战斗族出现第二种行首形态（36 条 `图标【N 刻】…` / 这 6 条裸 `【N 刻】…`）。"
               "本批按 §2.2 逐条选图标：⚔️ 行动/攻击（施展）· ✨ 成功/强化（治疗）· "
               "✔ 结束 · ⚠️ 预警（无可行动者 / 未知行动）。"
               "★ `old` 与 `new` 逐字只差一个行首图标 —— 统一形态，不改语义措辞。"
               "★ 引擎零改动；读端与取件逻辑一字未动；params 无变化。"},
    "COMBAT_ACTIONS_SKILL_HEAL_FULL": {"old": "【{t:.0f} 刻】你施展【{name}】，圣光治愈了你 {heal} 点生命！", "new": "✨【{t:.0f} 刻】你施展【{name}】，圣光治愈了你 {heal} 点生命！", "why": "P0-3（战斗族行首图标对齐 · 真源 26_ §2.2 emoji 语义分组 + §三 优化 1）："
               "上一轮 P0-1 给这 6 条加【N 刻】时**只加了刻、没给行首图标** ⇒ "
               "战斗族出现第二种行首形态（36 条 `图标【N 刻】…` / 这 6 条裸 `【N 刻】…`）。"
               "本批按 §2.2 逐条选图标：⚔️ 行动/攻击（施展）· ✨ 成功/强化（治疗）· "
               "✔ 结束 · ⚠️ 预警（无可行动者 / 未知行动）。"
               "★ `old` 与 `new` 逐字只差一个行首图标 —— 统一形态，不改语义措辞。"
               "★ 引擎零改动；读端与取件逻辑一字未动；params 无变化。"},
    "COMBAT_CONTROLLED": {"old": "💫 {name} 晕着 —— 这一手什么都做不了！", "new": "💫【{t:.0f} 刻】{name} 晕着 —— 这一手什么都做不了！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_CORE_FINISHED": {"old": "【{t:.0f} 刻】战斗已结束！", "new": "✔【{t:.0f} 刻】战斗已结束！", "why": "P0-3（战斗族行首图标对齐 · 真源 26_ §2.2 emoji 语义分组 + §三 优化 1）："
               "上一轮 P0-1 给这 6 条加【N 刻】时**只加了刻、没给行首图标** ⇒ "
               "战斗族出现第二种行首形态（36 条 `图标【N 刻】…` / 这 6 条裸 `【N 刻】…`）。"
               "本批按 §2.2 逐条选图标：⚔️ 行动/攻击（施展）· ✨ 成功/强化（治疗）· "
               "✔ 结束 · ⚠️ 预警（无可行动者 / 未知行动）。"
               "★ `old` 与 `new` 逐字只差一个行首图标 —— 统一形态，不改语义措辞。"
               "★ 引擎零改动；读端与取件逻辑一字未动；params 无变化。"},
    "COMBAT_CORE_FLED": {"old": "💨 {name} 逃跑了！", "new": "💨【{t:.0f} 刻】{name} 逃跑了！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_CORE_NO_ACTOR": {"old": "【{t:.0f} 刻】没有可行动的玩家！", "new": "⚠️【{t:.0f} 刻】没有可行动的玩家！", "why": "P0-3（战斗族行首图标对齐 · 真源 26_ §2.2 emoji 语义分组 + §三 优化 1）："
               "上一轮 P0-1 给这 6 条加【N 刻】时**只加了刻、没给行首图标** ⇒ "
               "战斗族出现第二种行首形态（36 条 `图标【N 刻】…` / 这 6 条裸 `【N 刻】…`）。"
               "本批按 §2.2 逐条选图标：⚔️ 行动/攻击（施展）· ✨ 成功/强化（治疗）· "
               "✔ 结束 · ⚠️ 预警（无可行动者 / 未知行动）。"
               "★ `old` 与 `new` 逐字只差一个行首图标 —— 统一形态，不改语义措辞。"
               "★ 引擎零改动；读端与取件逻辑一字未动；params 无变化。"},
    "COMBAT_CORE_SILENCED": {"old": "🤐 {name} 被沉默，无法使用技能！(只能普攻/防御)", "new": "🤐【{t:.0f} 刻】{name} 被沉默，无法使用技能！(只能普攻/防御)", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_CORE_UNKNOWN_ACTION": {"old": "【{t:.0f} 刻】未知行动类型：{action}", "new": "⚠️【{t:.0f} 刻】未知行动类型：{action}", "why": "P0-3（战斗族行首图标对齐 · 真源 26_ §2.2 emoji 语义分组 + §三 优化 1）："
               "上一轮 P0-1 给这 6 条加【N 刻】时**只加了刻、没给行首图标** ⇒ "
               "战斗族出现第二种行首形态（36 条 `图标【N 刻】…` / 这 6 条裸 `【N 刻】…`）。"
               "本批按 §2.2 逐条选图标：⚔️ 行动/攻击（施展）· ✨ 成功/强化（治疗）· "
               "✔ 结束 · ⚠️ 预警（无可行动者 / 未知行动）。"
               "★ `old` 与 `new` 逐字只差一个行首图标 —— 统一形态，不改语义措辞。"
               "★ 引擎零改动；读端与取件逻辑一字未动；params 无变化。"},
    "COMBAT_DOT_TICK": {"old": "🔥 【{name}】持续受损（{n} 层）—— 损失 {dmg} 生命", "new": "🔥【{t:.0f} 刻】【{name}】持续受损（{n} 层）—— 损失 {dmg} 生命", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_EFFECTS_CAST_BROKEN": {"old": "💥 {name} 的出招被打断了！", "new": "💥【{t:.0f} 刻】{name} 的出招被打断了！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_EFFECTS_CLEANSED": {"old": "✨ 净化了 {names}！", "new": "✨【{t:.0f} 刻】净化了 {names}！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_EFFECTS_CLEANSE_NONE": {"old": "✨ 净化（无减益可解）", "new": "✨【{t:.0f} 刻】净化（无减益可解）", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_EFFECTS_DAMAGED": {"old": "💥 {name} 受到 {dmg} 点伤害！", "new": "💥【{t:.0f} 刻】{name} 受到 {dmg} 点伤害！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_EFFECTS_HEALED": {"old": "✨ {name} 恢复了 {heal} 点生命！", "new": "✨【{t:.0f} 刻】{name} 恢复了 {heal} 点生命！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_EFFECTS_IMMUNE_CONTROL": {"old": "🛡️ {name} 免疫控制：{key} 未生效", "new": "🛡️【{t:.0f} 刻】{name} 免疫控制：{key} 未生效", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_EFFECTS_IMMUNE_DEBUFF": {"old": "🚫 {name} 免疫【{key}】，异常未生效", "new": "🚫【{t:.0f} 刻】{name} 免疫【{key}】，异常未生效", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_EFFECTS_SHIELD_GAIN": {"old": "🛡️ {name} 获得护盾 {value} 点！", "new": "🛡️【{t:.0f} 刻】{name} 获得护盾 {value} 点！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_EFFECTS_STACK_ADD": {"old": "✦ {key} {n}{cap}（+{amount}）", "new": "✦【{t:.0f} 刻】{key} {n}{cap}（+{amount}）", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_EFFECTS_STACK_SET": {"old": "✦ {key} 置为 {n}", "new": "✦【{t:.0f} 刻】{key} 置为 {n}", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_EFFECTS_STACK_SHORT": {"old": "⚠️ {key} 不足（需 {amount}，当前 {cur}）", "new": "⚠️【{t:.0f} 刻】{key} 不足（需 {amount}，当前 {cur}）", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_EFFECTS_STACK_SPENT": {"old": "✦ 消耗 {amount} 点 {key}（剩余 {left}）", "new": "✦【{t:.0f} 刻】消耗 {amount} 点 {key}（剩余 {left}）", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_ELEM_IMMUNE": {"old": "💠 免疫 —— 【{name}】不吃这一手，伤害一点没落上去。", "new": "💠【{t:.0f} 刻】免疫 —— 【{name}】不吃这一手，伤害一点没落上去。", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_ELEM_WEAK": {"old": "⚡ 弱点 —— 【{name}】怕这一手，伤落得更实。", "new": "⚡【{t:.0f} 刻】弱点 —— 【{name}】怕这一手，伤落得更实。", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_GAUGE_GAIN": {"old": "💥 {bar} 积蓄 +{add}（{val}/{maxcap}）", "new": "💥【{t:.0f} 刻】{bar} 积蓄 +{add}（{val}/{maxcap}）", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_GAUGE_PHASE_PRESERVE": {"old": "💢【{name}】阶段更迭：{bar}积蓄保留 {pct}%（{before} → {after}）", "new": "💢【{t:.0f} 刻】【{name}】阶段更迭：{bar}积蓄保留 {pct}%（{before} → {after}）", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_GAUGE_REFLECT": {"old": "🪨 反震：反弹 {dmg} 点伤害！", "new": "🪨【{t:.0f} 刻】反震：反弹 {dmg} 点伤害！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_GAUGE_SHAKEN": {"old": "💢 【{name}】被{bar}震慑，无法行动！", "new": "💢【{t:.0f} 刻】【{name}】被{bar}震慑，无法行动！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_GAUGE_TRIGGER": {"old": "💢 【{bar}】触发！(第 {count} 次)", "new": "💢【{t:.0f} 刻】【{bar}】触发！(第 {count} 次)", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_LANDING_BLOCK_REDUCE": {"old": "🛡️ 格挡！减免 {red} 点伤害！", "new": "🛡️【{t:.0f} 刻】格挡！减免 {red} 点伤害！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_LANDING_DAMAGE": {"old": "💥 {name} 受到 {dmg} 点伤害！", "new": "💥【{t:.0f} 刻】{name} 受到 {dmg} 点伤害！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_LANDING_DEATH_GUARD": {"old": "✨ {name} 濒死意志触发，保住了性命！", "new": "✨【{t:.0f} 刻】{name} 濒死意志触发，保住了性命！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_LANDING_DODGED": {"old": "💨 {name} 闪避了攻击！", "new": "💨【{t:.0f} 刻】{name} 闪避了攻击！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_LANDING_DOWN": {"old": "💥 {name} 受到 {dmg} 点伤害，倒下了！", "new": "💥【{t:.0f} 刻】{name} 受到 {dmg} 点伤害，倒下了！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_LANDING_HEAL_FORBID": {"old": "🩸 禁疗：治疗量 -{pct}%！", "new": "🩸【{t:.0f} 刻】禁疗：治疗量 -{pct}%！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_LANDING_HEAL_SHARED": {"old": "✨ 治疗由【{name}】分担", "new": "✨【{t:.0f} 刻】治疗由【{name}】分担", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_LANDING_HEAL_WOUND": {"old": "🩸 重伤：治疗量 -{pct}%！", "new": "🩸【{t:.0f} 刻】重伤：治疗量 -{pct}%！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_LANDING_MAGIC_RESIST": {"old": "🛡️ 魔法抗性，减免 {red} 点魔法伤害！", "new": "🛡️【{t:.0f} 刻】魔法抗性，减免 {red} 点魔法伤害！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_LANDING_PHYS_IMMUNE": {"old": "🪨 物理免伤，减免 {red} 点物理伤害！", "new": "🪨【{t:.0f} 刻】物理免伤，减免 {red} 点物理伤害！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_LANDING_RESIST_REDUCE": {"old": "🛡️ 元素抗性减免 {red} 点伤害！", "new": "🛡️【{t:.0f} 刻】元素抗性减免 {red} 点伤害！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_LANDING_SHIELD_ABSORB": {"old": "🛡️ {name} 的护盾吸收了 {absorb} 点伤害！", "new": "🛡️【{t:.0f} 刻】{name} 的护盾吸收了 {absorb} 点伤害！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_LANDING_TAKEN_MULT_SKIPPED": {"old": "🛡️ {name} 减伤 {pct}%（本次事件乘区减伤 {mult_pct}% 已跳过，两条减伤不叠加）", "new": "🛡️【{t:.0f} 刻】{name} 减伤 {pct}%（本次事件乘区减伤 {mult_pct}% 已跳过，两条减伤不叠加）", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_LANDING_TAKEN_REDUCE": {"old": "🛡️ {name} 减伤 {pct}%！", "new": "🛡️【{t:.0f} 刻】{name} 减伤 {pct}%！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_LANDING_WOKEN": {"old": "💥 目标被攻击惊醒！", "new": "💥【{t:.0f} 刻】目标被攻击惊醒！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_RES_LACK": {"old": "⚡ 这一手你还没攒够 —— 需要 {rv:.0f} 点，现在只有 {cur:.0f} 点。", "new": "⚡【{t:.0f} 刻】这一手你还没攒够 —— 需要 {rv:.0f} 点，现在只有 {cur:.0f} 点。", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_SCHEDULE_CAST_BEGIN": {"old": "🌀 {name} 开始出招…", "new": "🌀【{t:.0f} 刻】{name} 开始出招…", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_SCHEDULE_REGEN_HP": {"old": "🍲 {name} 持续恢复，恢复 {heal} 点生命！", "new": "🍲【{t:.0f} 刻】{name} 持续恢复，恢复 {heal} 点生命！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_SCHEDULE_REGEN_MP": {"old": "🍲 {name} 持续恢复，恢复 {heal} 点魔力！", "new": "🍲【{t:.0f} 刻】{name} 持续恢复，恢复 {heal} 点魔力！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    "COMBAT_SKILL_CD": {"old": "⏳ 【{name}】这一手还在缓 —— 再等 {left:.0f} 刻。", "new": "⏳【{t:.0f} 刻】【{name}】这一手还在缓 —— 再等 {left:.0f} 刻。", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ 引擎零改动；读端与取件逻辑一字未动。"},
    # ★ P0-2（文案修复车道 · 有队时那句「集火」回话 · 读端 content/cmds_battle.py:919）：
    #   原值是「🚧 「集火」还没接上 / 💡 全队打同一个还没做」——**开发口吻上屏**，
    #   玩家点「集火」看到的是一句工程自述。改法 = 照实说这一场的实况（各打各的），
    #   并把「功能仍缺」留在 desc 里给下一位（**功能仍缺，本条只改措辞**）。
    "COMBAT_FOCUS_PARTY": {
        "old": "🚧「集火」还没接上\n💡 全队打同一个还没做 —— 这一场各自出手。",
        "new": "队伍里现在没人能统一出手 —— 这一场各打各的。\n💡 你先打的那只就是它；等集火接上，敲『集火 <目标>』能让全队打同一只。",
        "why": "P0-2：开发口吻不该上屏（真源 26 §三 优化1 一族的同一问题：屏上要的是实况）。"
               "功能侧「全队打同一个」仍缺（真源 17_组队与策略配合 §三·8 未落地）—— "
               "本条**只改措辞**，读端与分支行为一字未动。",
    },

    #   共同病根 = 屏上出现**工程自述**（「还没接上」「数据换过」）——
    #   玩家读到的是「这个功能没写完」，不是「你现在能做什么 / 怎么继续」。
    #   四条都**有活读端**（逐条点名见 why），改法 = 照实说这一场的实况 + 给下一步那句话。
    #   ★ 四条**只改措辞**：读端与分支行为一字未动，fail-closed 语义照旧。
    # ★ P0-2（文案修复车道 · 第二批 · 四条「开发口吻上屏」）：
    #   共同病根 = 屏上出现**工程自述**（「还没接上」「数据换过」）——
    #   玩家读到的是「这个功能没写完」，不是「你现在能做什么 / 怎么继续」。
    #   四条都**有活读端**（逐条点名见 why），改法 = 照实说这一场的实况 + 给下一步那句话。
    #   ★ 四条**只改措辞**：读端与分支行为一字未动，fail-closed 语义照旧。
    "SYS_HP_UNSET": {
        "old": "（{name}：职业基础 还没接上。）",
        "new": "（{name}：还没定下怎么打 —— 先打『选职业』定一个，再来动手。）",
        "why": "P0-2：读端 content/cmds_ast.py:372 `hp_cap_or_line`（生命 / 回血 / 战斗 / 面板四处共用）。"
               "玩家建号只走完第一步就来敲『攻击』，屏上是一句「职业基础 还没接上」——"
               "工程自述。改成：说清「还没定下怎么打」+ 给他一句能敲的『选职业』"
               "（指令名逐字取 content/data/commands.json 的 `^选职业$`）。"
               "★ 判据不用松：scripts/probe_copy.py:1122 与 probe_class.py:278 拿"
               "**子串『职业基础』**反证「两步走完就不该卡在这儿」—— 新值里没有那四个字，"
               "反证照样成立（卡住的档仍然出这一行，走完两步的档仍不出）。",
    },
    "SYS_SKILL_STALE": {
        "old": "（技能表里有 {n} 条现在认不出了 —— 数据换过。）",
        "new": "（技能表里有 {n} 条认不出来了 —— 『技能』里还在的那些照旧能用。）",
        "why": "P0-2：读端 content/cmds_skill.py:132（`技能` 面板末行）。"
               "「数据换过」是**给维护者看的话**（「数据换过」= 存档版本对不上域）。"
               "改成：照实说有几条认不出 + 明说其余照旧能用（别让玩家以为整个技能表都废了）。"
               "★ 这条本来就是 fail-closed 的**点名行**（不许静默丢技能），措辞换成玩家话，"
               "点名与计数一个字没少。",
    },
    "SYS_POI_COND_TODO": {
        "old": "（{name}的条件「{keys}」还没接上 —— 先当它没有。）",
        "new": "（{name}的条件「{keys}」这一下算不出来 —— 先当它没开。）",
        "why": "P0-2：读端 content/cmds_ast.py:1686（POI 门槛判不了时点名，**不许静默删内容**）。"
               "「还没接上」= 工程自述；玩家只需要知道「这个条件我算不出来，当它没开」。"
               "★ 判据不受影响：scripts/probe_pois.py:617 判的是"
               "**「点名行以本槽位渲染出的那一段前缀开头」**（按槽位取前缀，不写死中文）"
               "⇒ 值怎么改都对得上，判据一个字未改。",
    },
    "SYS_POI_EFFECT_TODO": {
        "old": "（{name}：{keys} 还没接上。）",
        "new": "（{name}：{keys} 这一下认不出来 —— 先当它没有。）",
        "why": "P0-2：同上一条那一族（POI 的 effect 键认不出 ⇒ fail-closed 点名，"
               "读端 content/cmds_ast.py:1907）。病根与改法同 SYS_POI_COND_TODO；"
               "两行合看仍是「点名 + 不静默生效」这一条形状。",
    },
    "SYS_INN_SLEEP": {
        "old": "你在角落那张床睡下 —— 再睁眼，日头已经换了地方。",
        "new": "你在角落那张床睡下 —— 睡得不沉，醒来外头还是那个时辰。",
        "why": "试玩问题 #15（P1 BUG-6）：时辰/天气是**现算**的（钟由宿主注入、整个进程一根钟）——"
               "住店推不动它，可旧那句断言「日头已经换了地方」⇒ 睡完 `时间` 还是同一个时辰，"
               "回话自己打脸（夜里住店的人以为能等到天亮，实际一步没挪）。"
               "改法 = 照实说（真推时间要先有**按人存的钟偏移**那一层，不是这一簇的事）——"
               "本分支只改这一句的值，见 `_notes.md` §真源行",
    },
    "SYS_ITEM_SHOW_ASK": {
        "old": "看哪一件？打『查看 <东西>』。",
        "new": "看哪一件？打『查看 <东西>』；委托全文是『看 <编号>』——先在公会敲『悬赏』。",
        "why": "夜班试玩 w3（p1 路 ⚠️）：裸『看』在帮助里同时挂在两族（公会『看 <编号>』与"
               "背包『查看 <东西>』，`commands.json` 里 `^看$` 是后者的别名）—— 旧那句只把人"
               "推给背包那一族，敲『看』的人其实可能想查委托全文。两族入口都说清（见分支 `_notes.md`）",
    },
    # ★ fix-c-newbie ①（新手进入面）：建号第一步那两行念的是「天赋 · …」「代价 · …」，
    #   而这两个词**都不是指令**（`04_指令总表 §三` 的角色栏里没有它们、`帮助` 里也没有）
    #   ⇒ 玩家照着屏上的词敲「天赋」只回「这句我没接住」（P-54 那句兜底）。
    #   最小改法 = 句尾加一句括注说清「已经在身上了、不用敲」（不是新增指令 —— 指令名属口径）。
    #   真源那一行（`17_文案收口口径_v1.md` 的这两格）**待主线跟账**成新值；真源仓对本分支只读。
    "SYS_RACE_TALENT": {
        "old": "天赋 · {name}：{effect}",
        "new": "天赋 · {name}：{effect}（已生效）",
        "why": "fix-c-newbie ①（新手进入面 · 狂战士试玩 b01）：建号第一屏把「天赋」当名词念，"
               "玩家会把它当**指令**敲（实跑：`我是 人类` 回话印「天赋 · 人脉 / 天赋 · 适应」，"
               "紧接 `天赋` ⇒ 「「天赋」这句我没接住。」）——`04 §三` 的角色栏与 `帮助` 里都没有这条词。"
               "改法 = 那两行句尾加「（已生效）」：不新增指令名、不动 `出身`（`04 §三` 那一行列的字段没它），"
               "只把那两行从「像是要敲的东西」改成「已经在身上」。见分支 `_notes.md §真源行`",
    },
    "SYS_RACE_COST": {
        "old": "代价 · {name}：{effect}",
        "new": "代价 · {name}：{effect}（已生效）",
        "why": "fix-c-newbie ① 同屏同族：`代价` 与 `天赋` 是同一形状（都不是指令、都印在同一屏），"
               "只标一半 ⇒ 玩家照着剩下的那个词照样敲得空。两条一起标，理由与上一格同",
    },
    # ★ fix-g-enhance（2026-09-27 · 现象 A 现象 B 同族）：`强化` 成功那行原来**一个字没提料**
    #   （背包前后少了 铁屑 ×1 · 硬骨 ×1，回话里只报等级与加成），而缺料那一支却逐项报价 ⇒
    #   两处口径不一；同一条回话里那个 `加成 +0.4%` 在屏上也没有落点（乘的是那一件装备自己的
    #   主词条，面板按整数显示）。改法 = **只动这一格的文案**：把「吃掉了什么」印出来（料表就是
    #   那一档的 `inputs`，与缺料那一支同一份）+ 补一句「面板按整数看」的说明。
    #   ★ 这一条**不在** `00_总纲/17_文案收口口径_v1.md` 的槽位表里（B2-6 那批 `SYS_ENHANCE_*`
    #     是包内先落、真源待搬）⇒ `old` = **本分支改前域里的值**（该族唯一的「旧口径」）；
    #     主线搬那一族槽位表时，照 `new` 落即可（`probe_copy ⑤` 的「逐字一致」从此对上）。
    "SYS_ENHANCE_OK": {
        "old": "🔨 {item} → +{lv}（加成 {bonus}，走装备本体 —— 上限 +{cap}%）。",
        "new": "🔨 {item} → +{lv}（吃了{cost}。加成 {bonus}，走装备本体 —— 上限 +{cap}%。"
               "面板按整数看：+1..+3 这点不到半格，看不出。）",
        "why": "fix-g-enhance（现象 A · 游侠路 b63/b73/b82）：成功那行把**吃掉的料**逐项印出来"
               "（`cost` = 那一档 `inputs` 经 `_need_str`，与「缺料」那一支同一个口）；"
               "（现象 B · 骑士 / 狂战 / 法师）：补一句「面板按整数看」—— 加成乘的是那一件装备"
               "自己的主词条，+1..+3 累计不到半格。判据：`scripts/probe_recipes.py` ⑧-b / ⑨-b",
    },
    # ===== P2-1（文案车道 aep2 · 并列行统一）：行首 `· ` 的口径 =====
    #   判据取仓里**已经成立的 18 条**（`SYS_ACH_ROW` 等）：那 18 条一律「行首一个 `· `、
    #   行内不出现 `·`」—— 行内分隔它们一律用 `——` / `：` / `→` / `×` / `｜`。
    #   ⇒ 选定口径：**行首 `· ` 作条目锚点，行内 `·` 一律换成 `——`**（不搞第二个分隔符）。
    #   只动**没有自带锚点**的 3 条；自带编号/图标的 4 条（`SYS_CLS_ROW` ①②③、`SYS_RANKING_ROW` {i}.、
    #   `SYS_RACE_ROW` ①②③、`SYS_TITLE_ROW`/`SYS_EGG_ROW` 的 `✦`）保持不动 —— 再加一个 `· `
    #   就是同屏两个锚点，���「规整」更远。详见分支 `_notes.md`。
    "SYS_BOARD_MAIN_ROW": {
        "old": "主线 {order} · {name}{mark}  等级 {level}+",
        "new": "· 主线 {order} —— {name}{mark}  等级 {level}+",
        "why": "P2-1：并列行统一（口径见上面那段）。这一条原来把 `·` 用在**行内**，"
               "而同一界面的 `SYS_BOARD_BOUNTY_ROW` 同款 —— 统一成「行首 `· ` + 行内 `——`」。"
               "★ 只改这一格的值，`{order}/{name}/{mark}/{level}` 四个槽位与取件点一个字没动。",
    },
    "SYS_BOARD_BOUNTY_ROW": {
        "old": "悬赏 {order} · {name}{mark}  等级 {level}+",
        "new": "· 悬赏 {order} —— {name}{mark}  等级 {level}+",
        "why": "P2-1：同上（与 `SYS_BOARD_MAIN_ROW` 同一个界面的同款行，必须一起改）。",
    },
    "SYS_TRADE_ROW": {
        "old": "{trade} {n} 条 —— {what}",
        "new": "· {trade} {n} 条 —— {what}",
        "why": "P2-1：这一条既没编号也没图标 ⇒ 补行首 `· `，与另外 18 条对齐。"
               "★ 取件点 `content/cmds_quest.py` 那一处 `yield` 加两个空格的前缀，不动。",
    },
    # ===== P2-2（文案车道 aep2 · 符号混用收敛）：=====
    #   ① `｜` 16 条、`→` 5 条都已是成规模的「分栏 / 前后」符号，**`⇒` 只有 1 条**
    #      （`SYS_ALLOC_OK`）—— 出众数。⇒ 收敛口径：**保留 `｜` 作分栏、`→` 作前后，
    #      把那一个 `⇒` 换成 `→`**（与 `SYS_GEAR_HP_CAP`「生命上限 {old} → {new}」同一语义
    #      用同一个符号）。**不新造符号、不两处都留。**
    #   ② `★` 与 `✦` 同语义（都是「玩家刚拿到一样东西」）：`✦` 5 条全是「获得」（彩蛋/称号/状态），
    #      `★` 里有 3 条也是「获得」（图鉴新进/旧物认出来/任务升级/真身看明白），**混着用**。
    #      ⇒ 统一：**「获得」全用 `✦`**；`★` 只保留它剩下的那一个意思（`SYS_CLS_STAR` 的
    #      「★推荐」= 界面上的推荐角标，那是**另一个**符号用法，不属于「获得」这一族）。
    "SYS_ALLOC_OK": {
        "old": "{stat} +{n} ⇒ {stat} {now} ｜ 还剩 {left} 点",
        "new": "{stat} +{n} → {stat} {now} ｜ 还剩 {left} 点",
        "why": "P2-2①：同屏混了 `｜`（分栏，仓里 16 条）与 `⇒`（前后，仓里只此 1 条）—— "
               "两个符号管两件事、同屏出现。按众数收敛：`｜` 留作分栏，`⇒` → `→`"
               "（`→` 本就是仓里「前后」那一族，与 `SYS_GEAR_HP_CAP` 同款）。"
               "★ 只改这一格的值，取件点 `content/cmds_ast.py` 那一处 `yield` 不动。",
    },
    "SYS_CODEX_NEW": {
        "old": "★ 新进谱：{book} · {name}",
        "new": "✦ 新进谱：{book} · {name}",
        "why": "P2-2②：「获得」这一族 `✦` 已经 5 条（彩蛋/称号/战斗状态），`★` 又有 3 条"
               "是同一个意思（图鉴新进 / 旧物认出来 / 真身看明白）—— 同一语义两个符号。"
               "统一到 `✦`。★ `★推荐` 那条是**界面角标**不是「获得」，留在 `★` 不动。",
    },
    "SYS_CODEX_REVEAL": {
        "old": "★ 旧物谱：「{name}」认出来了。",
        "new": "✦ 旧物谱：「{name}」认出来了。",
        "why": "P2-2②：同 `SYS_CODEX_NEW`（图鉴这一族的另一次「获得」）。",
    },
    "SYS_UNID_OPENED": {
        "old": "★ {who}把它看明白了 —— 原来是：",
        "new": "✦ {who}把它看明白了 —— 原来是：",
        "why": "P2-2②：同族（真身解锁也是「获得」）。",
    },
    "SYS_JOB_LEVELUP": {
        "old": "★ 你升到 {level} 级了。",
        "new": "✦ 你升到 {level} 级了。",
        "why": "P2-2②：任务交付那一条与 `SYS_JOB_REWARD`（经验 ｜ 铜板）**同屏**，"
               "那句是「获得」这一族 —— 所以 `★` 也要一起换成 `✦`（否则同一屏两个获得符号）。"
               "★ 注意别与 `SYS_LEVEL_UP`（`✨ 升级到 Lv.X`，状态面板那一条）混为一谈："
               "**那是另一个界面**，本批不动它（跨界面不同本来就正常，不是问题）。",
    },
    # ===== P2-3（文案车道 aep2 · 补图标）：=====
    #   ★ 判据不是「覆盖率」—— **emoji 少不算缺陷**。本批只补**同一屏内该配而没配**的：
    #   一个列表页面上「主抬头有锚点、它下面那两三个子抬头是裸文字」⇒ 玩家一眼扫过去分不出层级。
    #   补的 4 条**都是多行并列列表的子抬头**（下面真跟着 ≥2 行），用的 emoji 取作业书给的
    #   奥兰迪亚词典「📜 任务/清单」，**不自创**。
    #   ★ 刻意**不补**的（逐条有理由，不是漏）：
    #     · `SYS_*_ASK` 50 余条（问玩家的「装哪一件？」）—— 单行、不是列表、加图标反而花；
    #     · `SYS_*_TAIL` / `_HOW`（收尾提示行）—— 同一屏已有锚点，再加一层是噪音；
    #     · 0% 覆盖界面里「一行只有一个数」的纯数据行（`· {label} {value}`）——
    #       它们已经在 `· ` 锚点里了，**这一条就是 P2-1 的口径**，不是缺图标。
    "SYS_BOARD_BOUNTY_HEAD": {
        "old": "悬赏三档常年挂在公会上：",
        "new": "📜 悬赏三档常年挂在公会上：",
        "why": "P2-3：`board_page` 一屏里 `SYS_BOARD_HEAD` 是【挂板墙】、这两个子抬头是裸文字 —— "
               "**同屏层级不一致**（下面真跟着 3 行）。补 📜（词典：任务/清单）。"
               "★ 与主抬头的【】不同族是刻意的：【】标「这是个界面」，📜 标「这是一份清单」。",
    },
    "SYS_BOARD_SIDE_HEAD": {
        "old": "这人手上还有：",
        "new": "📜 这人手上还有：",
        "why": "P2-3：同 `SYS_BOARD_BOUNTY_HEAD`（同一屏、同一个列表的另个子抬头，必须一起补）。",
    },
    "SYS_SMITH_CRAFT_HEAD": {
        "old": "炉边那堆料是留给学徒的 —— 凑够了，柯尔让你自己上手。",
        "new": "📜 炉边那堆料是留给学徒的 —— 凑够了，柯尔让你自己上手。",
        "why": "P2-3：打造列表的抬头，下面真跟着若干条 `SYS_SMITH_CRAFT_ROW`（≥2 行）—— "
               "而同一屏的完成反馈已经用 🔨（`SYS_SMITH_CRAFT_OK`）⇒ 抬头也该给一个锚点。"
               "★ 选 📜 不选 🔨：🔨 那一条是「**结果**」（打出来了），抬头是「**清单**」，两件事。",
    },
    "SYS_SMITH_SRC_HEAD": {
        "old": "这几样料从哪儿来：",
        "new": "📜 这几样料从哪儿来：",
        "why": "P2-3：料表抬头（下面跟着 `SYS_SMITH_SRC_ROW`），与 `SYS_SMITH_CRAFT_HEAD` 同一批。",
    },
    "COMBAT_MECH_ABSOLVE_NONE": {
        "old": "它身上没有能解的东西。",
        "new": "你身上没有能解的东西。",
        "why": "fix-h-small（真人试玩 b13 · 修女路）：单人无控时 `技能 净罪` 屏上出「它身上没有能解的东西。」——"
               "净罪的**收件人就是施法者自己**（`content/mech.py::_cast_cleanse` 只动 caster 自己的 effects），"
               "单人对面只有怪 ⇒ 屏上的「它」被读成对面，玩家以为打空/解错了对象。"
               "★ 真源 `03_职业与技能/05_修女_v2.md` §三 只写了「净罪 = 队友被控住了，立刻解掉」，"
               "**没有一行写「单人（没有队友）时收件人是谁」** ⇒ 本分支按「单人 = 你」落最小改（只改这一格的值，"
               "判定逻辑一个字没动），**真源那一行待主线补**（补上之后这一格照着跟账：两态见 `pending_ok`）。"
               "★ 同族的 `COMBAT_MECH_ABSOLVE`（解开那一句）也写着「它」，今天**到不了**"
               "（本包 30 条技能一条控制都没有 —— 见 `skill_mech.cleanse.halves` 那条 pending），"
               "故这一格不改，登记在分支 `_notes.md` 待组队/怪物控制技那批一起定口径。",
    },
    # ===== P2-7（文案车道 aep2 · 2026-09-29 00:05 · 📜 语义收口）=====
    #   ★ 判据原点仍是鱼鱼口径（「emoji 可以，规整 + 观感好」）—— 要判的是
    #     **同一图标在不同槽位含义漂**（真问题），不是「emoji 覆盖率低」（那不是门禁指标）。
    #   ★ 实测（`python -c` 现读 `texts.json`）：📜 全包 5 条 = **两种互不相干的语义**：
    #       公会委托板三条（`SYS_BOARD_BOUNTY_HEAD` / `SYS_BOARD_SIDE_HEAD`）= 「板上/单子/清单」
    #         —— 这层含义由 `b208693` 建立，且它写明了「与【】不同族是刻意的」；
    #       铁匠铺两条（`SYS_SMITH_CRAFT_HEAD` / `SYS_SMITH_SRC_HEAD`）= 抬头/清单
    #         —— 同样由 `b208693` 建立，**理由是「抬头=清单、🔨=结果」两件事**（判得对，
    #         本车道**核对后不改**这两条：抬头与 `SYS_SMITH_CRAFT_OK` 的 🔨 确实不是一件事）；
    #       图鉴这条（`UNID_RESULT_LORE`）= 「认出一样东西 + 印出那段文字」= **读东西**
    #         ⇒ 前两种语义都不是它，且它**不与前两者同屏**（`content/cmds_codex.py` 一屏只有它），
    #           所以这不是「同屏不一致」，是**图标含义本身漂**（同一图标 = 三件事）。
    #   ⇒ 收敛口径：**📜 只表示「板上/单子/清单」这一族**（P2-1/P2-3 已定的既有含义），
    #     这条改用 📖（读文本）—— 📖 在本包**尚未被任何槽位占用**（现扫零命中），
    #     且与 📜（板上）/ 📊（状态）/ 📍（地点）分得开 ⇒ 不新造语义，只是归位。
    #   ★ 只换行首那一个码位；取件点 `content/cmds_codex.py` 与 `params` 一个字未动。
    #   ★ 顺带核实过（**不登记**）：`{bar}` 那一族今天到不了屏（本包没配 `enemy_bar`），
    #     `{key}` 那一族引擎灌的确实是机器名（见上面 P2-4 段），本轮不重复发现。
    "UNID_RESULT_LORE": {
        "old": "📜 {title}\n{text}\n💡 已进旧物谱",
        "new": "📖 {title}\n{text}\n💡 已进旧物谱",
        "why": "P2-7：📜 一图三义（板上/清单 · 铁匠铺抬头 · 图鉴读文本）。前两者由 `b208693` "
               "建立且各有理由、**核对后保留**；这一条既不同屏、语义也与那两族无关 ⇒ "
               "把 📜 收回「板上/清单」一族，本条归 📖（读文本，本包未占用）。",
    },
    # ===== P2-4 / P2-5（文案车道 aep2 · 第二轮 2026-09-28 18:20）=====
    #   ★ P2-4 核实结论（**只报不改**）：那 29 条「槽位名是机器键」的槽位里，
    #     引擎灌进去的**确实是机器名本身**（不是显示名）——
    #       · `{key}`：引擎 `extends/ext_combat/battle/effects.py:509/523` 两处
    #         `_cue(..., {"key": key, ...})` 里的 `key` 就是 `EFFECT_RULES` 的键
    #         （本包 `content.mech.rules_module()` 现算 23 条，如 `aeth.oath_shield` /
    #         `blood_debt` / `pinned`）⇒ 这类屏上真会出「aeth.oath_shield 提升（mul×1.2…）」；
    #       · `{bar}`：`extends/ext_combat/gauge/__init__.py:191` 的 `bar_key`，
    #         而本包**没配 `enemy_bar` 表**（内容目录现扫零命中）⇒ 这一族今天到不了屏。
    #     判「**不是漏、而是另一件更事的活**」：要修得在**内容侧**给状态条目补一格显示名
    #     （引擎 `safe_format` 只做朴素替换、**没有查表钩子**）或者动引擎加查表口 ——
    #     前者属内容侧可做、后者违铁律（引擎零改动）。**本车道不碰**，清单交主线。
    #   ★ P2-5（本轮唯一实改）：挂板墙一屏里三个子列表的行首锚点**三样**：
    #     主线那行行首有 `· `、缩进 0（`content/cmds_quest.py:1180`）；
    #     悬赏那三行行首有 `· `、缩进 2（`:1198`，上一轮 P2-1 补的）；
    #     支线那几行是**缩进 2 + 裸文字**（`:1212`）—— 而 `{order}` 灌的是纯数字
    #     （主线 1..12 · 悬赏 101/102/103 · 支线 13..），**不是** `SYS_RACE_ROW` 那种
    #     ①②③ 视觉锚点（那一族上一轮判定「自带锚点、不动」，判得对）。
    #     ⇒ 同屏三份清单、两种层级 ⇒ **真缺陷**（不是「emoji 覆盖率」那种口味问题）。
    #     修法照**上一轮已定的 P2-1 口径**（行首 `· ` 作条目锚点、行内不出现 `·`）：
    #     给支线那一行补上同一枚 `· `，**缩进照旧**（缩进管层级、`· ` 管锚点，两件事）。
    # ★ P0-2（文案修 P0 车道 · 2026-09-28）：两条**开发口吻上屏**的桩句改成玩家能接受的实况。
    #   病根 = 玩家敲一条用不上的指令，看到的是一句工程自述（`🚧「…」还没接上` / `还没做完`）。
    "SYS_CMD_SOON": {
        "old": "🚧「{name}」还没接上\n💡 敲「帮助」看现在能用什么",
        "new": "「{name}」这一下还用不上。\n💡 敲「帮助」看现在能用什么",
        "why": "P0-2：读端 `content/cmds_ast.py::declared_soon`（声明了、包内还没实现的那条指令"
               "—— 玩家敲它就看到这一句）。原句 `🚧「{name}」还没接上` 是**工程自述**上屏；"
               "照实说「这一下还用不上」，不假装功能已存在。★ 判据未动：probe_cmds ⑥ 那几条"
               "是用槽位**现算**期望串的，改值自动跟随（它禁的是「内部 key + 没 handler」那套回显，"
               "不是这句措辞）。",
    },
    "SYS_JOB_NOT_DONE": {
        "old": "还没做完。",
        "new": "还没交差。",
        "why": "P0-2：读端 `content/cmds_quest.py`（交活 · 条件没满足那一行）。"
               "原句 `还没做完。` 是**工程口吻**（像在说这个功能没写完），"
               "玩家读起来是「交活被拒」；改成委托人口吻「还没交差。」，"
               "同一件事、同一分支、只换说法。★ 全仓无探针写死这句话（grep「还没做完」零命中）。",
    },
    "SYS_BOARD_SIDE_ROW": {
        "old": "{order} {name} —— {objective}",
        "new": "· {order} {name} —— {objective}",
        "why": "P2-5：挂板墙一屏里 `SYS_BOARD_MAIN_ROW`（行首 `· ` · 缩进 0）与 "
               "`SYS_BOARD_BOUNTY_ROW`（行首 `· ` · 缩进 2）都有条目锚点，"
               "**只有支线这一行没有** —— 而 `{order}` 灌的是纯数字（13/14/15…），"
               "不是 ①②③ 那种视觉锚点。⇒ 补上同一枚 `· `，与同屏另两个子列表对齐。"
               "★ 缩进（`cmds_quest.py:1212` 那个 `\"  \" +`）一个字不动：缩进管层级、"
               "`· ` 管锚点。★ 只改这一格的值，取件点与判定逻辑一个字没动。",
    },
    # ===== P2-6（文案车道 aep2 · emoji 字形形态）：=====
    #   ★ 判据不是「emoji 少/多」（鱼鱼原话：「适当的 emoji 会更好」）——
    #     是**同一个 emoji 长得不一样**：U+1F6E1 🛡 在本域 15 处里 **14 处带 U+FE0F**、
    #     只有 `COMBAT_CORE_DEFEND` 是裸形态 ⇒ 同一个 🛡 在一屏里一处彩色、一处单色描边。
    #   ★ 已验它与那 14 条**同屏**：`scripts/_baseline_instance_solo.json` 的「防御」那一档
    #     末行就是这句，而同屏前几行是 `⚔ 第 N 手` / `🌀` / `💥`；
    #     `probe_instance.py --dump` 在改前态与该基线**逐字节相同**（玩家真会看到的一屏）。
    #   ★ 按众数收敛：多的那一派（VS16）胜出。`U+2694 ⚔` 虽也是 2:2，但**刻意不动**
    #     —— 打平就没有依据（见 `P2-6_emoji字形形态_交接.md` §四①）。
    "COMBAT_CORE_DEFEND": {
        "old": "🛡 {name} 摆出防御姿态，受到的伤害减半！",
        "new": "🛡️【{t:.0f} 刻】{name} 摆出防御姿态，受到的伤害减半！",
        "why": "★ 本条是**两笔叠起来**的（别当重复登记删一条）：上面那笔 P2-6 先补了 U+FE0F，本条（P0-1 战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）在**那一版之上**再加行首【N 刻】；`old` 仍是域里改之前那一版。"
               "P2-6：emoji **字形形态**统一，不是图标增删 —— `U+1F6E1` 本域 15 处里 14 处带 "
               "`U+FE0F`（彩色 emoji 呈现），只有这一条是裸的；两者同屏时观感不一致。"
               "接线 `battle.core.defend`（引擎 `ext_combat/battle/battle.py:655`），"
               "属玩家真会撞到的那一屏（见 `scripts/_baseline_instance_solo.json`）。"
               "★ 只加了一个 U+FE0F，取件点与判定逻辑一个字没动。",
    },
    #   ★ 同批第二组：`U+2694` 本来 2:2 打平，**不能用众数裂价**（拆平就是选一边倒）。
    #     改用**一致性一致的类比**：同一屏里的「战斗行＝预警」两个 codepoint（`U+2694`与
    #     `U+26A0`）都属于「默认呈现是文字、需要 VS16 才是彩色」那一类 —— `U+26A0` 本包 5/5 全带
    #     VS16。→ 按**同类的已统一口径**，`U+2694` 也全带。
    #   ★ 常驻判据在 `scripts/probe_instance.py` 末尾（P2-6 那两条，含反证）。
    "COMBAT_TURN_STATE": {
        "old": "⚔ 第 {n} 手 —— 你 {hp}/{hp_max}　｜　{name} {foe_hp}/{foe_hp_max}",
        "new": "⚔️ 第 {n} 手 —— 你 {hp}/{hp_max}　｜　{name} {foe_hp}/{foe_hp_max}",
        "why": "P2-6：emoji 字形形态统一的第二组（见上面那段说明）。"
               "接线 `content/instance.py::turn_panel`，是打击屏的第一行（四段式① 现状）。"
               "★ 只加一个 U+FE0F，取件点与判定逻辑一个字没动。",
    },
    "SYS_STATUS_IN_FIGHT": {
        "old": "⚔ 手上这一场还没打完 —— 敲『战斗日志』看打到哪儿了，或者『逃跑』脱身。",
        "new": "⚔️ 手上这一场还没打完 —— 敲『战斗日志』看打到哪儿了，或者『逃跑』脱身。",
        "why": "P2-6：同一批。接线 `content/cmds_ast.py:1356`（「状态」面板末行）。"
               "★ 只加一个 U+FE0F，取件点与判定逻辑一个字没动。",
    },
    "COMBAT_TURN_MENU": {
        "old": "　① 攻击　② 打断　③ 防御　④ 后撤\n　（还有：技能 <名> · 使用 <药> · 逃跑 · 换武器 · 集火 <目标> · 自动 · 战斗日志）",
        "new": "　① 攻击　② 打断　③ 防御　④ 后撤\n　（还有：技能 <名>　使用 <药>　逃跑　换武器　集火 <目标>　自动　战斗日志）",
        "why": "P2-8：P2-1 定的口径是「行首一个 `· `、行内不出现 `·`」"
               "（P2-1 提交消息：行内分隔该用 —— / ： / → / × / ｜）。"
               "★ 这一格是全仓唯一一处**行内 `·` 真在分隔同屏并列选项**的地方 ——"
               "同一屏第一行已用 ①②③④ 作锚点、第二行又用 `·` 分隔，两套锚点同屏混排。"
               "★ **为什么换全角空格、不换 `｜` 或 `——`：** 这一行是括号里的补充可敲词，"
               "不是分栏（`｜` 那族 15 条都是「A ｜ B」两栏对照），也不是前后字段展开"
               "（`——` 那族是「A —— B」）。这里是「一串同级的词」，而同一格第一行"
               "①②③④ 之间本来就是全角空格 ⇒ 同一格内统一，不跨族借符号。"
               "★ `old`/`new` 按**整格**写（含第一行），因为门禁 `probe_copy ⑤` 与"
               "生成器比对的是整格值、不是单行。取件点 `content/instance.py:770` "
               "与判定逻辑一个字没动；这一格 `params` 是空的，不涉及槽位。",
    },
    # ===== P2-9（文案车道 aep2 · 同一行内分隔符收敛）=====
    #   两条，都是端到端真机跑出来的（不是按审计清单逐条猜）：
    #   ① SYS_SKILL_HEAD：47 条 _HEAD 槽位里**只有它一行同时出现 · 与 ｜**
    #      （现算：其余用 · 的 HEAD 一律 ｜=0，用 ｜ 的一律 ·=0）。
    #      且它自己的**双生句** SYS_RECIPE_HEAD（同为「会做 N 条 / 还没学会 M 条」）
    #      两个分隔符都用 · ⇒ **以它为准，把 ｜ 收成 ·**。
    #   ② SYS_CMP_HEAD：同一个对比界面里 SYS_CMP_VERDICT（结论行）已统一用 ·，
    #      且 SYS_CMP_ROW / _NOTE_CUR / _NOTE_NEW 三条都是行首 · 锚点 ⇒
    #      **拿它自己界面里那三条的口径统一拿下来。**
    #   选定口径：**一行内不得同时出现 · 与 ｜。**不新造符号、不两边都留。
    #   （下面的 · / ｜ 只是本文档里的占位名，实际值 = texts.json 里那两个字符。）
    "SYS_SKILL_HEAD": {
        "old": "【技能】{cls} · 已会 {known} 条 ｜ 还没到等级 {locked} 条",
        "new": "【技能】{cls} · 已会 {known} 条 · 还没到等级 {locked} 条",
        "why": "P2-9①：47 条 _HEAD 里唯一一行同时混 · 与 ｜ 的；且它自己的双生句 "
               "SYS_RECIPE_HEAD（同为「会做 N / 还没学会 M」）两个分隔符都是 · ⇒ 以它为准。"
               "只改这一格的值，cls/known/locked 三个槽位与取件点 content/cmds_skill.py:121 "
               "一个字没动；两支采该槽位的探针（probe_cmds.py 711/819）是现取槽位的，"
               "不硬编字符串字面量 ⇒ 跟随。",
    },
    "SYS_CMP_HEAD": {
        "old": "【对比】{name}（{quality} · {kind}） ｜ 现在这件：{cur}",
        "new": "【对比】{name}（{quality} · {kind}） · 现在这件：{cur}",
        "why": "P2-9②：同一个对比界面里 SYS_CMP_ROW / _NOTE_CUR / _NOTE_NEW 三条都是行首 "
               "· 锚点、SYS_CMP_VERDICT 也统一用 · 作分隔 ⇒ 拿它自己界面里那些行的"
               "口径。只改这一格的值，槽位与取件点一个字没动。",
    },

    "SYS_JOB_TAKEN": {
        "old": "接下：{name}",
        "new": "📜 接下：{name}",
        "why": "P2-3（本车道真缺陷 · 同一界面内图标不一致）：真源 `17_文案收口口径_v1` L159 "
               "给**同一族**的 `SYS_JOB_ABANDONED` 配了 `🗑️`，而接活/交活/奖励那三行没有 —— "
               "实屏（e2e_drive 真敲『接 1』）四行同屏时，一行带图标三行不带。"
               "口径：鱼鱼「emoji 少不算缺陷，但**同一界面内用法要一致**」；"
               "📜 在本包已固化为「读东西/清单/单子」语义（`SYS_BOARD_BOUNTY_HEAD`·`SYS_BOARD_SIDE_HEAD`"
               "·`SYS_SMITH_CRAFT_HEAD`·`SYS_SMITH_SRC_HEAD` 四条 **HEAD 全用它**）⇒ 接活那条归 📜。",
    },
    "SYS_JOB_DELIVERED": {
        "old": "交了：{name}",
        "new": "✔ 交了：{name}",
        "why": "P2-3（同上那一条的另一半）：交活是**完成**语义 ⇒ 归 ✔，"
               "与本包既有的 `COMBAT_DONE`『✔ 打完了。』·`COMBAT_CORE_FINISHED` 同一符号，"
               "不自创 ✅（本包 ✅ 使用数为 0，写了就是新造）。"
               "★ 奖励那一行 `SYS_JOB_REWARD`（经验+铜板）**不在这批里**：它与 `SYS_REWARD`"
               "（💰 金币 +{gold}，✨ 经验 +{exp}）是同语义两套写法，牵涉到选哪一套当准，"
               "属口径裁决 ⇒ 留交主线，本批不动。",
    },
    "COMBAT_TURN_FOE_DOING": {
        "old": "◆ {name}正押着一手 —— 那一手还有 {left} 秒落到你身上。",
        "new": "◆ {name}正押着一手 —— 那一手还有 {left} 刻落到你身上。",
        "why": "P0-4（本车道真缺陷）：这是**全包唯一一条把刻数写成「秒」的**玩家可见文案，"
               "而真源那一行自己的来源列就写着「剩几刻」，真源口径与字面偏离。"
               "实测传值：`content/instance.py:767` 给的是 `cast_done_at - now`，即引擎 CTB 的**刻数**"
               "（1 刻 = 1 游戏秒，但对玩家只能写「刻」）⇒ 原句把一个刻数说成秒数，快慢不可比。"
               "口径：交接指南三轴第三条锁定「刻 / 行动机会」、禁用「回合」；"
               "本包 931 条槽位里「回合」已归零、「秒」只剩这一条 ⇒ 改它是最后一个。"
               "只改这一格的值；取件点 `content/instance.py:767` 与 `params` 一字未动。",
    },
}


def pending_ok(key: str, doc_val: str) -> bool:
    """这一条待跟账、且**表里那一格处于允许的两态之一** → True（第三态 ⇒ False ⇒ 当场抛）。"""
    fx = DOC_PENDING.get(str(key))
    return bool(fx) and doc_val in (fx["old"], fx["new"])



def parse_doc(path=DOC):
    """读口径文档里**所有**槽位表 -> 每行一条（顺序 = 文档里的顺序）。

    ★ 后续批次继续往那份文档下面加表就行（脚本按行全扫）—— 别另开一份，免得两处口径。
    """
    if not os.path.exists(path):
        raise SystemExit("口径文档不在：%s" % path)
    lines = io.open(path, encoding="utf-8").read().split(chr(10))
    out = []
    for ln in lines:
        if not ROW_RE.match(ln):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) != 5:
            raise SystemExit("列数不是 5（别改列数）：%s" % ln)
        key, value, params, cat, srcname = cells
        # ★ 多行文案：表里写 `\n`（反斜杠 n）＝真换行（行内不许出现真换行 —— 真换行会把一行切成两行，
        #   第二行不是槽位行、**静默漏掉**）。JSON 落盘时它就是一个真换行（与 SCENE_* 那些多段正文同形）。
        value = value.replace("\\n", "\n")
        prm = [] if params in ("-", "") else [x.strip() for x in params.split(",") if x.strip()]
        out.append({"key": key, "value": value, "params": prm,
                    "category": cat, "src": srcname})
    if not out:
        raise SystemExit("槽位表是空的")
    return out


def check(rows):
    """键名 · 重复 · 占位与 params 双向对账 —— 错一条都不许落。"""
    bad = []
    seen = set()
    for r in rows:
        k, v = r["key"], r["value"]
        if not KEY_RE.match(k):
            bad.append("键名不合规则：%s" % k)
        if k in seen:
            bad.append("重复：%s" % k)
        seen.add(k)
        used = set(PH.findall(v))
        decl = set(r["params"])
        if used - decl:
            bad.append("%s：value 里的占位没声明 -> %s" % (k, sorted(used - decl)))
        if decl - used:
            bad.append("%s：声明了却没占位 -> %s" % (k, sorted(decl - used)))
        if not v.strip():
            bad.append("%s：文案是空的" % k)
        if "〔待填" in v:
            bad.append("%s：还是待填占位" % k)
    if bad:
        for b in bad:
            print("  x %s" % b)
        raise SystemExit("槽位表没过对账，没写任何东西")
    return True


def load_texts():
    return json.load(io.open(TEXTS, encoding="utf-8"))


def dump_texts(tx):
    with io.open(TEXTS, "w", newline=chr(10), encoding="utf-8") as f:
        json.dump(tx, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main(argv):
    dry = "--dry" in argv
    rows = parse_doc()
    check(rows)
    tx = load_texts()
    before = len(tx)
    add, same, clash = [], 0, []
    for r in rows:
        old = tx.get(r["key"])
        if old is None:
            if r["key"] in DOC_PENDING:
                raise SystemExit("%s：登记了待跟账却**域里没有**（域里先有才谈得上跟账）" % r["key"])
            add.append(r)
        elif old.get("value") == r["value"]:
            same += 1
        elif pending_ok(r["key"], r["value"]) and old.get("value") == DOC_PENDING[r["key"]]["new"]:
            same += 1                     # ★ g4：待跟账的两态之一（表里旧值 / 跟账后新值；域里是新值）
        else:
            fx = DOC_PENDING.get(r["key"])
            if fx and r["value"] not in (fx["old"], fx["new"]):
                clash.append((r["key"] + "（跟账第三态：表里既不是旧值也不是新值）",
                              old.get("value"), r["value"]))
            else:
                clash.append((r["key"], old.get("value"), r["value"]))
    if clash:
        for k, a, b in clash:
            print("  x %s 两处不一样：" % k)
            print("      表里：%s" % b)
            print("      域里：%s" % a)
        raise SystemExit("槽位与域里的字不一样 —— 先裁决再落（没写任何东西）")
    print("解析：%d 条（已存在且一致 %d · 要新增 %d · 待跟账 %d）"
          % (len(rows), same, len(add), len(DOC_PENDING)))
    if not add:
        print("  · 无新增 —— 数据不变（幂等）")
        return 0
    for r in add:
        tx[r["key"]] = {"value": r["value"], "params": r["params"],
                        "category": r["category"], "desc": r["src"]}
        print("  + %-22s %s" % (r["key"], r["value"][:34]))
    if dry:
        print("（--dry：没落盘；texts %d -> %d）" % (before, len(tx)))
        return 0
    dump_texts(tx)
    print("落地：texts %d -> %d 条  %s" % (before, len(tx), TEXTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
