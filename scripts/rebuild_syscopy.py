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
    # ===== P2-18（文案车道 aep2 · 同屏图标不一致 / 整屏 0 图标）=====
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
    "COMBAT_BLOCKED_AMOUNT": {"old": "（格挡后 {dmg} 点伤害）", "new": "🛡️【{t:.0f} 刻】格挡后 {dmg} 点伤害", "why": "P0-1 收口（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "给这条补上刻数 + 行首图标。★★ 本轮**推翻**了此前登记里「续行片段不加刻」那条理由："
               "实测（e2e 真跑 · 骑士『防御』那一手，屏上逐行）：`（格挡后 3 点伤害）` 是**独立一行**——"
               "引擎 `landing.py:205` 的 `_cue(..., logs, ...)` 直接 append 进 `logs`，随后由包侧 "
               "`cmds_battle._fmt` 逐行出屏，**不与上一行拼接** ⇒ 加【N 刻】不会「夹成怪相」。"
               "实测屏上它夹在 `🛡️【100 刻】…防御姿态` 与 `💥【124 刻】…受到 3 点伤害` **中间**——"
               "读不出刻数的那一行正是这条（同一屏两种形态）。"
               "★ 刻数取同一 `deal_damage` 里的 `t`（与紧邻的承伤行同一个 `battle._now`，逐字同值）。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 float（`TIME_SLOT` 走 `now_of`）⇒ `{t}` 会印「100.0 刻」。"
               "★ 图标按真源 §2.2 取 🛡️（防御/减伤/格挡），与同族 `COMBAT_LANDING_BLOCK_REDUCE` 一致。"
               "★ `params` 同步加 `t`；取件点（battle_text.json 映射）一字未动；引擎零改动。"
               "★ 这两格**不在真源槽位表里**（`17_文案收口口径_v1.md` grep 0 命中）⇒ 不是生成器拥有的行，"
               "改值不与真源表打架（`--dry` 仍回「要新增 0」）。"},
    "COMBAT_CORE_SILENCED": {"old": "🤐【{t:.0f} 刻】{name} 被沉默，无法使用技能！(只能普攻/防御)", "new": "🤐【{t:.0f} 刻】{name} 被沉默，无法使用技能！（只能普攻/防御）", "why": "P0-2 续批（战斗族渲染残留 · 括号全角化）："
               "★★ 本条是**同格上的第二笔登记**（第一笔 P0-1 加【N 刻】已落，域里已是那个值）："
               "这一笔只把**半角** `!` 与 `(…)` 换成全角 —— 与 `COMBAT_BLOCKED_AMOUNT` 那笔"
               "（引擎兜底半角括号 → 全角）**同一族缺陷**，也是 `probe_elements` ⑨-f"
               "「那一屏一个半角括号都不许有」要拦的那一类（玩家真会看见：这是活 cue 槽位，"
               "`battle.<x>` → `battle_text.json` 的映射在册，每次触发都上屏）。"
               "★ 逐码位量过、不是肉眼看：除 emoji 的 VS16 序列外，U+0028/U+0029 是仅剩的"
               "两处半角标点；`！` 本来就是 U+FF01 ⇒ **只改那两个括号**，别把感叹号也重写成别的。"
               "★ 只改这一格的值；取件点（cue 映射）与 `params` 一字未动，读端零改动。"
               "★ P0-1 那一笔为何在这一格上（保留在这里，不单独起一条）：行首加【N 刻】（真源 26_ §三 优化 1）。"},
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
    "COMBAT_EFFECTS_IMMUNE_DEBUFF": {"old": "🚫 {name} 免疫【{key}】，异常未生效", "new": "🛡️【{t:.0f} 刻】{name} 免疫【{key}】，异常未生效", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ P2-13（2026-09-29 · 排版规整度）：行首锚 🪨 → 🛡️。与 `COMBAT_EFFECTS_IMMUNE_CONTROL`（免疫控制，已是 🛡️）同为「这一次没生效」一语，且两条由引擎 `effects.py::act_apply` **同一个函数**里两个 `_cue` 连着发（已真跑引擎取过一屏：两行相邻）；真源 26_ §2.2 的 emoji 语义分组表里**没有 🚫**。"},
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
    "COMBAT_GAUGE_REFLECT": {"old": "🪨 反震：反弹 {dmg} 点伤害！", "new": "💢【{t:.0f} 刻】反震：反弹 {dmg} 点伤害！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ P2-13（2026-09-29 · 排版规整度）：行首锚 🪨 → 💢。同族「效果回敬 / 触发」三张行已全是 💢（`COMBAT_GAUGE_TRIGGER` / `COMBAT_GAUGE_SHAKEN` / `COMBAT_GAUGE_PHASE_PRESERVE`），本条与它们同属一簇；更关键的是 🪨 当年被另两条占着（物理免伤 + 本条）、**一个图标持两个不相干的语义**；真源 26_ §2.2 表里没有 🪨。"},
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
    "COMBAT_GAUGE_TRIGGER": {"old": "💢【{t:.0f} 刻】【{bar}】触发！(第 {count} 次)", "new": "💢【{t:.0f} 刻】【{bar}】触发！（第 {count} 次）", "why": "P0-2 续批（战斗族渲染残留 · 括号全角化）："
               "★★ 本条是**同格上的第二笔登记**（第一笔 P0-1 加【N 刻】已落，域里已是那个值）："
               "这一笔只把**半角** `!` 与 `(…)` 换成全角 —— 与 `COMBAT_BLOCKED_AMOUNT` 那笔"
               "（引擎兜底半角括号 → 全角）**同一族缺陷**，也是 `probe_elements` ⑨-f"
               "「那一屏一个半角括号都不许有」要拦的那一类（玩家真会看见：这是活 cue 槽位，"
               "`battle.<x>` → `battle_text.json` 的映射在册，每次触发都上屏）。"
               "★ 逐码位量过、不是肉眼看：除 emoji 的 VS16 序列外，U+0028/U+0029 是仅剩的"
               "两处半角标点；`！` 本来就是 U+FF01 ⇒ **只改那两个括号**，别把感叹号也重写成别的。"
               "★ 只改这一格的值；取件点（cue 映射）与 `params` 一字未动，读端零改动。"
               "★ P0-1 那一笔为何在这一格上（保留在这里，不单独起一条）：行首加【N 刻】（真源 26_ §三 优化 1）。"},
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
    "COMBAT_LANDING_PHYS_IMMUNE": {"old": "🪨 物理免伤，减免 {red} 点物理伤害！", "new": "🛡️【{t:.0f} 刻】物理免伤，减免 {red} 点物理伤害！", "why": "P0-1（战斗时间轴 · 真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）："
               "行首加【N 刻】。★ 硬阻塞已解除：引擎 901c8d8「cue payload 补一格绝对时刻 t」"
               "已进 engine HEAD（`ext_combat.battle.cues.TIME_SLOT`/`with_now`，每条 cue 都给）"
               "⇒ 本批 52 条活 cue 槽位**真能在屏上拿到刻**。"
               "★ 写 `{t:.0f}` 不写 `{t}`：引擎给的是 **float**（实测 142.0）"
               "⇒ `{t}` 会印成「142.0 刻」。"
               "★ 落点在行首图标之后且**吃掉图标后那一个空格**（真源样例逐字："
               "`⚔️【142 刻】你 · 攻击 · 伐木工`）。"
               "★ 只改独立行；续行片段（`COMBAT_BLOCKED_AMOUNT`/`COMBAT_NO_TARGET`）"
               "与标题行（`COMBAT_SCHEDULE_ACTOR_TURN`）不加 —— 加了会夹成怪相。"
               "★ P2-13（2026-09-29 · 排版规整度）：行首锚 🪨 → 🛡️。同族三条（`COMBAT_LANDING_MAGIC_RESIST` / `COMBAT_LANDING_BLOCK_REDUCE` / `COMBAT_LANDING_RESIST_REDUCE`）**已经全是 🛡️**，只有本条不一样；且这三条由引擎 `landing.py::_apply_taken_reductions` **同一个函数**里三个 `_cue` 连着发（已真跑引擎取过一屏：减伤与格挡两行相邻）。真源 26_ §2.2 明写「🛡️ = 防御 / 减伤 / 霸体」。"},
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
    # ★ P0-2（文案修复车道 · 第三批 · 剩余两条「库没接上」）：
    #   全表宽网（「库没接上/存档库/接线/待接/未支持/内部/报错」十个词）扫一遍后，
    #   剩下的**真残留**只有这两条（两条都有活读端）。病根与前面那几批同一：
    #   「存档库没接上」是**给维护者看的话**（数据库那一层没装上）。
    #   玩家需要的只有一件：玩家什么都读不到（这个功能读不出来）。
    #   ★ fail-closed 语义一字未动（仍是「不假装有数据、点名」那一行）。
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
    # ===== P2-14（文案车道 aep2 · 2026-09-29 · 建号两屏抬头补 📜）=====
    #   判据原点仍是鱼鱼口径（「emoji 可以，规整 + 观感好」）—— 不钉覆盖率，
    #   钉的是「**同一屏里抬头与它下面那几行并列项同属清单族，却只有并列项带锚**」。
    #   逐条读过原句，全包只剩两处真的缺（其余「零锚抬头行」是不该加的，见下）：
    #     · `SYS_RACE_HEAD`（`content/cmds_ast.py::race_menu`）—— 抬头下 6 行 `①②③` 并列。
    #     · `SYS_CLS_LEAD`（`content/cmds_ast.py::class_menu`）—— 同上。
    #   选 `📜`（P2-7 已把 📜 收口成「清单/抬头」一族，本批沿用，不自创）。
    #   ★ `SYS_CLS_HEAD` 不补：已退役、零读端（`scripts/probe_copy.py::RETIRED_DOC`），
    #     补一个没人读的键 = 制造第二条口径。
    #   ★ 另外 6 条零锚抬头行**不补**：`COMBAT_RETREAT_HEAD`（「你压低身子，先看退路。」）
    #     与 `COMBAT_ITEM_HEAD` 那一族是**一句正文**而非抬头锚，加行首 emoji 观感更差。
    #     这条「不补」的理由落在本注释里，下一轮别再当缺口捡回来。
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
    "SYS_STATUS_IN_FIGHT": {
        "old": "⚔ 手上这一场还没打完 —— 敲『战斗日志』看打到哪儿了，或者『逃跑』脱身。",
        "new": "⚔️ 手上这一场还没打完 —— 敲『战斗日志』看打到哪儿了，或者『逃跑』脱身。",
        "why": "P2-6：同一批。接线 `content/cmds_ast.py:1356`（「状态」面板末行）。"
               "★ 只加一个 U+FE0F，取件点与判定逻辑一个字没动。",
    },
    "COMBAT_RES_SHORT": {
        "old": "⚡ 【{res}】不够 —— 这一手要 {rv} 点，你现在只有 {cur} 点。",
        "new": "⚡【{res}】不够 —— 这一手要 {rv} 点，你现在只有 {cur} 点。",
        "why": "P2-3b：同屏的 `COMBAT_RES_LACK` 是 `⚡【{t:.0f} 刻】…`（图标后**无**空格、紧跟时间轴），"
               "这一条是 `⚡ 【{res}】…`（**有**空格）⇒ 同一屏、同一个 ⚡、两种接法，"
               "被 `scripts/probe_emoji_order.py` ① 抓到。收敛到无空格那一种：这一格是**战斗日志里**"
               "的一行（与 LACK 同行同屏），时间轴那一族一律「图标+【N 刻】」不夹空格。"
               "★ 纯排版改动：占位符、取值点、判定逻辑一个字没动。",
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
    "SYS_ENHANCE_SHOP": {
        "old": "柯尔的炉子还热着。\n强化 = 材料（铁屑 · 硬骨）+ 钱；+1..+5 必成，+6 起看运气。\n打『强化 <装备名>』。",
        "new": "📜 柯尔的炉子还热着。\n强化 = 材料（铁屑 · 硬骨）+ 钱；+1..+5 必成，+6 起看运气。\n打『强化 <装备名>』。",
        "why": "P2-3 续批（本车道真缺陷 · 同一界面内图标不一致）：铁匠铺这一屏有**四个并列列表抬头**，"
               "其中两个带 📜（`SYS_SMITH_CRAFT_HEAD`「炉边那堆料…」· `SYS_SMITH_SRC_HEAD`「这几���料从哪儿来：」），"
               "另外两个不带 ⇒ 实屏（e2e_drive 真敲『去 半截铁砧』→『铁匠铺』）四段同屏时两段带图标两段不带。"
               "口径：鱼鱼「emoji 少不算缺陷，但**同一界面内用法要一致**」；"
               "📜 在本包已固化为「读东西/清单/单子」语义（四条 HEAD 全用它）⇒ 另两段归 📜。",
    },
    "COMBAT_TURN_RES": {
        "old": "🔹【{name}】{n}/{mx}",
        "new": "⚡ 【{name}】{n}/{mx}",
        "why": "P2-10（本车道真缺陷 · 同一屏内图标不一致）：`_res_rows` 把 `COMBAT_TURN_MP`（`⚡`）"
               "与 `COMBAT_TURN_RES`（`🔹`）相连接输出到同一屏—— 两行都是「资源读数」，"
               "图标却各用一个。乐观口径：一屏两行读数一个上一个下。"
               "改法为跟法力那一族的 `⚡`（已有三条），不新造第二个符号。"
               "★ 只改行首那一个图标；取件点 `content/instance.py:714`、`params`、"
               "`【】` 括号与 `n/mx` 一字未动。判据：`scripts/probe_icon_consistency.py` ④。",
    },
    # ===== P2-11（2026-09-29 夜班 · aep2）—— 物品「穿/脱/换/做」那一族结果行缺行首语义锚 =====
    #   缺口（任务书那几个数字已过期；这是本轮现扫现读出来的，不是照抄台账）：
    #     全包「动作成了」的结果行（*_OK / *_DONE / *_UP）里，同一类「物品事务」分成两拨：
    #       带行首语义锚的：💰 买/卖（SYS_SHOP_BUY_OK · SYS_SELL_OK）· 🗑️ 丢（SYS_DROP_OK）·
    #                   📦 存取箱子（SYS_STASH_IN_OK / SYS_STASH_OUT_OK）·
    #                   🔨 打造/强化（SYS_SMITH_CRAFT_OK · SYS_ENHANCE_OK）
    #       **不带行首语义锚的**：穿上 / 卸下 / 换手 / 做饭 —— 四条结果行都是「{icon}{name}」起头，
    #                   那个 `{icon}` 是**物品自己的图标**（内容数据里的 icon 字段，种类随物品变），
    #                   **不是这一行的行首语义锚**。
    #   ★ 本条要修的**不是「补 emoji 覆盖率」**（那不是判据，emoji 少不算缺陷）：
    #     要修的是**同族结果的行首锚不统一** —— 玩家一屏里连着看到
    #     `📦 放进箱子：…` 与 `你穿上了🗡…（单手剑）。`，前者有语义锚、后者没有。
    #   口径：给这四条**各补同一枚「物品事务」锚 📦** —— 与已固化的 📦（存取箱子）同族；
    #     不用 🎒（奥兰迪亚词典里 🎒 偏「背包那一屏的抬头」，不是每一次物品动作的结果）。
    #   ★ 只在**行首**加一格图标 + 一个空格；`{icon}{name}`（物品自身图标与名字）**一字未动**
    #     —— 那是内容数据，动了是另一件事。
    #   ★ 取件点 5 处（`content/cmds_gear.py:309/355` · `content/cmds_battle.py:994/1005/1021` ·
    #     `content/cmds_recipe.py:241`）与 `params` 一个字未动。
    #   ★ 判据侧全部是**用槽位现算期望**（`probe_cmds` ⑥⑦ 用 `_r("SYS_GEAR_EQUIP_OK", …)`、
    #     `probe_panel` ⑦ 用 `CA.T("SYS_GEAR_EQUIP_OK", …)`）⇒ 改值自动跟随，本批不改任何探针。
    "SYS_COOK_OK": {
        "old": "【{name}】{icon} 做好了，进了背包。\n吃下去：{buff}（{minutes} 分钟）。",
        "new": "📦 【{name}】{icon} 做好了，进了背包。\n吃下去：{buff}（{minutes} 分钟）。",
        "why": "P2-11（同上）：做饭与存取箱子同族（「做好了进了背包」）。★ 原句行首是【】不是图标 —— "
               "`【】` 与图标是两族锚（b208693 定），所以补图标而不动【】。",
    },
    # ===== P2-15（文案车道 aep2 · 2026-09-29 · `·` 与 `｜` 同一行内同现的**最后两条**）=====
    #   口径沿用 P2-9 已定的「一行内不得同时出现 `·` 与 `｜`」—— `·` = 字段/抬头分隔、
    #   `｜` = 行内分栏，两者各司其职仍保留，收敛的只是「同一行里混排」这一种形态。
    #   ★ P2-9 只点了 `SYS_SKILL_HEAD` / `SYS_CMP_HEAD` 两条，**这两条当时没被扫到**
    #     （静态扫表按 `_HEAD` 族找 ⇒ `SYS_CLS_EDGE` / `SYS_ORIGIN_HOME` 两个键名都不带
    #     `_HEAD` 后缀，落在族外）。本轮按**真渲染**重扫全表才捞出来。
    #   两条都真跑过 e2e（不是只看 JSON）：
    #     · `SYS_CLS_EDGE`  出自 `职业` 屏 —— 同屏的 `SYS_CLS_MECH`「节奏 · {mech}」
    #       是行内 `·`，而它自己「优势 · X ｜ 弱点 · Y」在同一行里插了个 `｜`
    #       （屏上原文：`优势 · 6.9% ｜ 弱点 · 1.329`）。
    #     · `SYS_ORIGIN_HOME` 出自 `出身` 屏 —— 同屏 `SYS_ORIGIN_WHY` 是「你为什么来：{why}」，
    #       同屏没有任何一处用 `｜`（屏上原文：`家乡 · 银月林海 ｜ 寿数 · 长到记不清`）。
    #   ⇒ 改法与 P2-9 那两条**同形**：`｜` 让位 `·`，两对「标签 · 值」在同一行内并列。
    #   ★ 只改这两格的值：`params`（adv/weak · home/life）与取件点
    #     （`content/cmds_ast.py::_cls_edge_line` / `_origin_home_line`）一个字没动；
    #     采这两条的探针（`probe_class ⑫` / `probe_races ⑫`）是现取槽位的，不硬编字面量 ⇒ 跟随。
    "COMBAT_SCHEDULE_ACTOR_TURN": {
        "old": "—— {name} 行动 ——",
        "new": "🌀【{t:.0f} 刻】{name} 行动",
        "why": "P0-4（2029-09-29 · 文案修复车道 P0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」，而这一条是**孤立一行**（不是续行片段）：e2e_drive 真打一场「—— 田鼠 行动 ——」是整场战斗日志里**唯一**无刻数、且无行首图标的行（日志里其余每一行都带 🌀【N 刻】）。引擎侧 `battle.schedule.actor_turn`（schedule.py:393）的 payload 经 `with_now` 已补 `TIME_SLOT`（每条 cue 都有）。→ 图标用同族的 🌀（手法）与 `COMBAT_SCHEDULE_CAST_BEGIN` 当成一家，去掉装饰用的长横。★ 判据变动：`probe_texts._NO_TIME_BY_DESIGN` 删掉这一条豁免（两条**续行片段**仍留）。",
    },

    # ★ P0-1 续批四（2026-09-29 · aep0）：Boss 阶段演出那一行补【N 刻】 —— 战斗日志面最后一条漏网的。
    "COMBAT_BOSS_PHASE": {
        "old": "⚠️ {name} 进入「{phase}」\n👁️ {note}\n💡 {tip}",
        "new": "⚠️【{t} 刻】{name} 进入「{phase}」\n👁️ {note}\n💡 {tip}",
        "why": "P0-1 续批四（2026-09-29 · 文案车道 aep0 · 真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」）：★ **这是「进持久战斗日志的那一族」最后一条没带刻的**（本轮现算：24 条经 logs.append / hand.lines 进日志的战斗行，改之前 23 条已带、只有这一条没有）。★ **为什么前几轮一直漏**（探针与 AST 两处盲区叠加，与上一批 `_grant`/`_ward` 同族病）：① probe_texts 那两条刻数判据按 content/rules/battle_text.json（引擎 62 个 cue）取件，而这一格是**内容侧**在 `content/combat.py::_phase_enter` 里 `logs.append` 的 ⇒ 取不到；② 枚举入口只找 `logs.append` 的调用点形参，而 `_phase_enter` 是**经 hook 回调**进去的（`Battle.script_hook(b, actor, logs)`）⇒ 只看 `logs` 变量名的那一族也漏。★ 本轮**只加强不削弱**：给 probe_combat 加两条判据（行首图标 + 【N 刻】、「屏上那一行的刻 == 那一刻的战斗钟」），取件从**真跑出来的那一行**（`_PLG[0]`）现算、刻数按引擎公开面 `now_of` 同一个式子现算 ⇒ 读端改刻源或忘传 t 都会当场红；另加一条反证（旧写法必红）。★ 值写**纯 {t} 不写 {t:.0f}**：内容侧 T() 是字面 replace（content/cmds_ast.py:53-55），格式符会被原样打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f} —— 两侧形态不同是有原因的，别合并。★ 读端补刻在**一处**（`_phase_enter` 那一行取 `int(round(float(getattr(battle,\"_now\",0.0) or 0.0)))`），靠 `hook(b, ...)` 现传的 `b` —— **别在调用点逐个补**。★ 本格**不在**真源 17_ 槽位表里（grep COMBAT_BOSS_PHASE 17_文案收口口径_v1 = 0 命中）⇒ 不是生成器拥有的行、不与真源打架；登记在册是为了两态互锁（不登记就红在 probe_copy ⑤ 与 probe_generators ②③）。",
    },
    "COMBAT_MECH_ONCE": {
        "old": "这一场你已经放过了 —— 【{name}】一场只出一次手。",
        "new": "⚔️【{t} 刻】这一场你已经放过了 —— 【{name}】一场只出一次手。",
        "why": "P0-1 续批七（2026-09-29 · 文案车道 aep0 · **真机试玩取证**）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **前六批为什么还是漏了这两格**（与已修的 18 格同族病、但落点更深一层）：那 18 格走 logs.append(T(...))，取件靠 probe_texts 里那条「logs, …COMBAT_…」的正则能捞到；**这两格走的是引擎 skill_gate_fn 的回执**（引擎 _use_gate_text → logs.extend(_usay)，content/mech.py::skill_gate），**返回值不是 logs.append** ⇒ 三条取件口（cue 表 / T(…) 字面量 / logs, 形参）**一条都取不到它** ⇒ 判据全绿、屏上零刻数。★ 复现（现跑可复现）：AST_E2E_SEED 带 loc=belt_north / node=bn_tower / cls=cls_berserker / level=9 / hp=200，跑 python scripts/e2e_drive.py 攻击 → 技能 焚身 → 技能 焚身 → 战斗日志 ⇒『战斗日志』里「这一场你已经放过了 —— 【焚身】一场只出一次手。」**原样落进去、零刻数**，而同一屏其余每一行都带【N 刻】。★ 值写**纯 {t} 不写 {t:.0f}**：内容侧 T() 是**字面 replace**（content/cmds_ast.py:53-55），格式符会被原样打上屏（同本族 18 格）。★ 只改这一格的值与 params；读端在 content/mech.py::skill_gate 补 t=int(round(_now(battle)))（与那 18 格同一个式子）。★ 图标 ⚔️ 逐字取真源 26_ §2.2「行动/出手」语义，与本族动作行同锚。★ 本格**不在**真源 17_ 槽位表里（grep = 0 命中）⇒ 不是生成器拥有的行、不与真源打架；登记在册是为了两态互锁（不登记就红在 probe_copy ⑤ 与 probe_generators ②③）。★ 本格 = once_per_battle（焚身）那道否决口的回执。"
    },
    "COMBAT_MECH_HP_GATE": {
        "old": "你还没攒够这点血 —— 【{name}】要 {need} 点才付得起，你现在只剩 {cur} 点。",
        "new": "⚔️【{t} 刻】你还没攒够这点血 —— 【{name}】要 {need} 点才付得起，你现在只剩 {cur} 点。",
        "why": "P0-1 续批七（2026-09-29 · 文案车道 aep0 · **真机试玩取证**）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **前六批为什么还是漏了这两格**（与已修的 18 格同族病、但落点更深一层）：那 18 格走 logs.append(T(...))，取件靠 probe_texts 里那条「logs, …COMBAT_…」的正则能捞到；**这两格走的是引擎 skill_gate_fn 的回执**（引擎 _use_gate_text → logs.extend(_usay)，content/mech.py::skill_gate），**返回值不是 logs.append** ⇒ 三条取件口（cue 表 / T(…) 字面量 / logs, 形参）**一条都取不到它** ⇒ 判据全绿、屏上零刻数。★ 复现（现跑可复现）：AST_E2E_SEED 带 loc=belt_north / node=bn_tower / cls=cls_berserker / level=9 / hp=200，跑 python scripts/e2e_drive.py 攻击 → 技能 焚身 → 技能 焚身 → 战斗日志 ⇒『战斗日志』里「这一场你已经放过了 —— 【焚身】一场只出一次手。」**原样落进去、零刻数**，而同一屏其余每一行都带【N 刻】。★ 值写**纯 {t} 不写 {t:.0f}**：内容侧 T() 是**字面 replace**（content/cmds_ast.py:53-55），格式符会被原样打上屏（同本族 18 格）。★ 只改这一格的值与 params；读端在 content/mech.py::skill_gate 补 t=int(round(_now(battle)))（与那 18 格同一个式子）。★ 图标 ⚔️ 逐字取真源 26_ §2.2「行动/出手」语义，与本族动作行同锚。★ 本格**不在**真源 17_ 槽位表里（grep = 0 命中）⇒ 不是生成器拥有的行、不与真源打架；登记在册是为了两态互锁（不登记就红在 probe_copy ⑤ 与 probe_generators ②③）。★ 本格 = min_hp_pct（狂斩）那道血线门的回执。"
    },
    # ★ P0-1 续批（2026-09-29 · aep0）：内容侧机制日志那一族补【N 刻】—— 见各条 why。
    "COMBAT_MECH_SELF_CUT": {
        "old": "你劈出这一下，自己先见了血（−{n}）。",
        "new": "🩸【{t} 刻】你劈出这一下，自己先见了血（−{n}）。",
        "why": "P0-1 续（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **判据的结构盲区**：probe_texts 那两条（活 cue 行带刻 / 行首统一图标）只按 content/rules/battle_text.json（引擎 62 个 cue）取件，**取不到内容侧 content/mech.py 那一族机制日志** ⇒ 这 18 格进的是**持久战斗日志**（_note_battle 把 logs 原样落档、『战斗日志』读它），实测屏上整场只有它们读不出刻数。★ 本格值写**纯 {t} 不写 {t:.0f}**：内容侧 T() 是**字面 replace**（content/cmds_ast.py:53-55），实测 '{t:.0f}' 永远不会被替换、会把字面量打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f} —— 两侧形态不同是有原因的，**别合并**。★ 图标按真源 26_ §2.2 语义分组逐条选（⚔️ 行动 · 🛡️ 防御/减伤 · 🩸 受伤/流血 · ✨ 强化/成功），并把 COMBAT_MECH_IMMUNE / MITIGATE 原有的 ✨ / 🛡️ 提到行首统一位置。★ 只改这一格的值与 params；读端（content/mech.py 各 logs.append）同步补 t=int(round(_now(battle)))。★ 这 18 格**不在**真源槽位表里（grep '| COMBAT_MECH_… |' 17_文案收口口径_v1 = 0 命中）⇒ 不是生成器拥有的行，不与真源打架。",
    },
    "COMBAT_MECH_SEVER": {
        "old": "它那一手被你截断 —— 【{name}】身上露出破绽：{turns} 刻里挨的每一下都多受 {pct}%，谁都吃得着。",
        "new": "⚔️【{t} 刻】它那一手被你截断 —— 【{name}】身上露出破绽：{turns} 刻里挨的每一下都多受 {pct}%，谁都吃得着。",
        "why": "P0-1 续（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **判据的结构盲区**：probe_texts 那两条（活 cue 行带刻 / 行首统一图标）只按 content/rules/battle_text.json（引擎 62 个 cue）取件，**取不到内容侧 content/mech.py 那一族机制日志** ⇒ 这 18 格进的是**持久战斗日志**（_note_battle 把 logs 原样落档、『战斗日志』读它），实测屏上整场只有它们读不出刻数。★ 本格值写**纯 {t} 不写 {t:.0f}**：内容侧 T() 是**字面 replace**（content/cmds_ast.py:53-55），实测 '{t:.0f}' 永远不会被替换、会把字面量打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f} —— 两侧形态不同是有原因的，**别合并**。★ 图标按真源 26_ §2.2 语义分组逐条选（⚔️ 行动 · 🛡️ 防御/减伤 · 🩸 受伤/流血 · ✨ 强化/成功），并把 COMBAT_MECH_IMMUNE / MITIGATE 原有的 ✨ / 🛡️ 提到行首统一位置。★ 只改这一格的值与 params；读端（content/mech.py 各 logs.append）同步补 t=int(round(_now(battle)))。★ 这 18 格**不在**真源槽位表里（grep '| COMBAT_MECH_… |' 17_文案收口口径_v1 = 0 命中）⇒ 不是生成器拥有的行，不与真源打架。",
    },
    "COMBAT_MECH_SUNDER": {
        "old": "【{name}】的甲被劈开 —— 防御 −{pct}%，{turns} 刻。",
        "new": "⚔️【{t} 刻】【{name}】的甲被劈开 —— 防御 −{pct}%，{turns} 刻。",
        "why": "P0-1 续（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **判据的结构盲区**：probe_texts 那两条（活 cue 行带刻 / 行首统一图标）只按 content/rules/battle_text.json（引擎 62 个 cue）取件，**取不到内容侧 content/mech.py 那一族机制日志** ⇒ 这 18 格进的是**持久战斗日志**（_note_battle 把 logs 原样落档、『战斗日志』读它），实测屏上整场只有它们读不出刻数。★ 本格值写**纯 {t} 不写 {t:.0f}**：内容侧 T() 是**字面 replace**（content/cmds_ast.py:53-55），实测 '{t:.0f}' 永远不会被替换、会把字面量打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f} —— 两侧形态不同是有原因的，**别合并**。★ 图标按真源 26_ §2.2 语义分组逐条选（⚔️ 行动 · 🛡️ 防御/减伤 · 🩸 受伤/流血 · ✨ 强化/成功），并把 COMBAT_MECH_IMMUNE / MITIGATE 原有的 ✨ / 🛡️ 提到行首统一位置。★ 只改这一格的值与 params；读端（content/mech.py 各 logs.append）同步补 t=int(round(_now(battle)))。★ 这 18 格**不在**真源槽位表里（grep '| COMBAT_MECH_… |' 17_文案收口口径_v1 = 0 命中）⇒ 不是生成器拥有的行，不与真源打架。",
    },
    "COMBAT_MECH_TAUNT": {
        "old": "你吼了一声 —— 这几刻（{turns} 刻）它只会冲你来。",
        "new": "⚔️【{t} 刻】你吼了一声 —— 这几刻（{turns} 刻）它只会冲你来。",
        "why": "P0-1 续（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **判据的结构盲区**：probe_texts 那两条（活 cue 行带刻 / 行首统一图标）只按 content/rules/battle_text.json（引擎 62 个 cue）取件，**取不到内容侧 content/mech.py 那一族机制日志** ⇒ 这 18 格进的是**持久战斗日志**（_note_battle 把 logs 原样落档、『战斗日志』读它），实测屏上整场只有它们读不出刻数。★ 本格值写**纯 {t} 不写 {t:.0f}**：内容侧 T() 是**字面 replace**（content/cmds_ast.py:53-55），实测 '{t:.0f}' 永远不会被替换、会把字面量打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f} —— 两侧形态不同是有原因的，**别合并**。★ 图标按真源 26_ §2.2 语义分组逐条选（⚔️ 行动 · 🛡️ 防御/减伤 · 🩸 受伤/流血 · ✨ 强化/成功），并把 COMBAT_MECH_IMMUNE / MITIGATE 原有的 ✨ / 🛡️ 提到行首统一位置。★ 只改这一格的值与 params；读端（content/mech.py 各 logs.append）同步补 t=int(round(_now(battle)))。★ 这 18 格**不在**真源槽位表里（grep '| COMBAT_MECH_… |' 17_文案收口口径_v1 = 0 命中）⇒ 不是生成器拥有的行，不与真源打架。",
    },
    "COMBAT_MECH_MATINS": {
        "old": "光落下来 —— {turns} 刻内，打上来的东西到不了身上。",
        "new": "✨【{t} 刻】光落下来 —— {turns} 刻内，打上来的东西到不了身上。",
        "why": "P0-1 续（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **判据的结构盲区**：probe_texts 那两条（活 cue 行带刻 / 行首统一图标）只按 content/rules/battle_text.json（引擎 62 个 cue）取件，**取不到内容侧 content/mech.py 那一族机制日志** ⇒ 这 18 格进的是**持久战斗日志**（_note_battle 把 logs 原样落档、『战斗日志』读它），实测屏上整场只有它们读不出刻数。★ 本格值写**纯 {t} 不写 {t:.0f}**：内容侧 T() 是**字面 replace**（content/cmds_ast.py:53-55），实测 '{t:.0f}' 永远不会被替换、会把字面量打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f} —— 两侧形态不同是有原因的，**别合并**。★ 图标按真源 26_ §2.2 语义分组逐条选（⚔️ 行动 · 🛡️ 防御/减伤 · 🩸 受伤/流血 · ✨ 强化/成功），并把 COMBAT_MECH_IMMUNE / MITIGATE 原有的 ✨ / 🛡️ 提到行首统一位置。★ 只改这一格的值与 params；读端（content/mech.py 各 logs.append）同步补 t=int(round(_now(battle)))。★ 这 18 格**不在**真源槽位表里（grep '| COMBAT_MECH_… |' 17_文案收口口径_v1 = 0 命中）⇒ 不是生成器拥有的行，不与真源打架。",
    },
    "COMBAT_MECH_QUICKSTEP": {
        "old": "你抢了半拍 —— 下一次出手的到点时刻最多提前 {ticks} 刻，再早也早不过此刻。",
        "new": "✨【{t} 刻】你抢了半拍 —— 下一次出手的到点时刻最多提前 {ticks} 刻，再早也早不过此刻。",
        "why": "P0-1 续（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **判据的结构盲区**：probe_texts 那两条（活 cue 行带刻 / 行首统一图标）只按 content/rules/battle_text.json（引擎 62 个 cue）取件，**取不到内容侧 content/mech.py 那一族机制日志** ⇒ 这 18 格进的是**持久战斗日志**（_note_battle 把 logs 原样落档、『战斗日志』读它），实测屏上整场只有它们读不出刻数。★ 本格值写**纯 {t} 不写 {t:.0f}**：内容侧 T() 是**字面 replace**（content/cmds_ast.py:53-55），实测 '{t:.0f}' 永远不会被替换、会把字面量打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f} —— 两侧形态不同是有原因的，**别合并**。★ 图标按真源 26_ §2.2 语义分组逐条选（⚔️ 行动 · 🛡️ 防御/减伤 · 🩸 受伤/流血 · ✨ 强化/成功），并把 COMBAT_MECH_IMMUNE / MITIGATE 原有的 ✨ / 🛡️ 提到行首统一位置。★ 只改这一格的值与 params；读端（content/mech.py 各 logs.append）同步补 t=int(round(_now(battle)))。★ 这 18 格**不在**真源槽位表里（grep '| COMBAT_MECH_… |' 17_文案收口口径_v1 = 0 命中）⇒ 不是生成器拥有的行，不与真源打架。",
    },
    "COMBAT_MECH_OATHWALL": {
        "old": "你把盾立起来 —— 到你下一次行动之前（约 {turns} 刻），落上来的东西轻 {pct}%。",
        "new": "🛡️【{t} 刻】你把盾立起来 —— 到你下一次行动之前（约 {turns} 刻），落上来的东西轻 {pct}%。",
        "why": "P0-1 续（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **判据的结构盲区**：probe_texts 那两条（活 cue 行带刻 / 行首统一图标）只按 content/rules/battle_text.json（引擎 62 个 cue）取件，**取不到内容侧 content/mech.py 那一族机制日志** ⇒ 这 18 格进的是**持久战斗日志**（_note_battle 把 logs 原样落档、『战斗日志』读它），实测屏上整场只有它们读不出刻数。★ 本格值写**纯 {t} 不写 {t:.0f}**：内容侧 T() 是**字面 replace**（content/cmds_ast.py:53-55），实测 '{t:.0f}' 永远不会被替换、会把字面量打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f} —— 两侧形态不同是有原因的，**别合并**。★ 图标按真源 26_ §2.2 语义分组逐条选（⚔️ 行动 · 🛡️ 防御/减伤 · 🩸 受伤/流血 · ✨ 强化/成功），并把 COMBAT_MECH_IMMUNE / MITIGATE 原有的 ✨ / 🛡️ 提到行首统一位置。★ 只改这一格的值与 params；读端（content/mech.py 各 logs.append）同步补 t=int(round(_now(battle)))。★ 这 18 格**不在**真源槽位表里（grep '| COMBAT_MECH_… |' 17_文案收口口径_v1 = 0 命中）⇒ 不是生成器拥有的行，不与真源打架。",
    },
    "COMBAT_MECH_ABSOLVE_NONE": {
        "old": "你身上没有能解的东西。",
        "new": "✨【{t} 刻】你身上没有能解的东西。",
        "why": "P0-1 续（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **判据的结构盲区**：probe_texts 那两条（活 cue 行带刻 / 行首统一图标）只按 content/rules/battle_text.json（引擎 62 个 cue）取件，**取不到内容侧 content/mech.py 那一族机制日志** ⇒ 这 18 格进的是**持久战斗日志**（_note_battle 把 logs 原样落档、『战斗日志』读它），实测屏上整场只有它们读不出刻数。★ 本格值写**纯 {t} 不写 {t:.0f}**：内容侧 T() 是**字面 replace**（content/cmds_ast.py:53-55），实测 '{t:.0f}' 永远不会被替换、会把字面量打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f} —— 两侧形态不同是有原因的，**别合并**。★ 图标按真源 26_ §2.2 语义分组逐条选（⚔️ 行动 · 🛡️ 防御/减伤 · 🩸 受伤/流血 · ✨ 强化/成功），并把 COMBAT_MECH_IMMUNE / MITIGATE 原有的 ✨ / 🛡️ 提到行首统一位置。★ 只改这一格的值与 params；读端（content/mech.py 各 logs.append）同步补 t=int(round(_now(battle)))。★ 这 18 格**不在**真源槽位表里（grep '| COMBAT_MECH_… |' 17_文案收口口径_v1 = 0 命中）⇒ 不是生成器拥有的行，不与真源打架。",
    },
    "COMBAT_MECH_ABSOLVE": {
        "old": "你把它身上那根线解开了。",
        "new": "✨【{t} 刻】你把它身上那根线解开了。",
        "why": "P0-1 续（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **判据的结构盲区**：probe_texts 那两条（活 cue 行带刻 / 行首统一图标）只按 content/rules/battle_text.json（引擎 62 个 cue）取件，**取不到内容侧 content/mech.py 那一族机制日志** ⇒ 这 18 格进的是**持久战斗日志**（_note_battle 把 logs 原样落档、『战斗日志』读它），实测屏上整场只有它们读不出刻数。★ 本格值写**纯 {t} 不写 {t:.0f}**：内容侧 T() 是**字面 replace**（content/cmds_ast.py:53-55），实测 '{t:.0f}' 永远不会被替换、会把字面量打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f} —— 两侧形态不同是有原因的，**别合并**。★ 图标按真源 26_ §2.2 语义分组逐条选（⚔️ 行动 · 🛡️ 防御/减伤 · 🩸 受伤/流血 · ✨ 强化/成功），并把 COMBAT_MECH_IMMUNE / MITIGATE 原有的 ✨ / 🛡️ 提到行首统一位置。★ 只改这一格的值与 params；读端（content/mech.py 各 logs.append）同步补 t=int(round(_now(battle)))。★ 这 18 格**不在**真源槽位表里（grep '| COMBAT_MECH_… |' 17_文案收口口径_v1 = 0 命中）⇒ 不是生成器拥有的行，不与真源打架。",
    },
    "COMBAT_MECH_LULLABY": {
        "old": "你把这口气吹进去 —— {turns} 刻再生，每刻回 {per} 点。",
        "new": "✨【{t} 刻】你把这口气吹进去 —— {turns} 刻再生，每刻回 {per} 点。",
        "why": "P0-1 续（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **判据的结构盲区**：probe_texts 那两条（活 cue 行带刻 / 行首统一图标）只按 content/rules/battle_text.json（引擎 62 个 cue）取件，**取不到内容侧 content/mech.py 那一族机制日志** ⇒ 这 18 格进的是**持久战斗日志**（_note_battle 把 logs 原样落档、『战斗日志』读它），实测屏上整场只有它们读不出刻数。★ 本格值写**纯 {t} 不写 {t:.0f}**：内容侧 T() 是**字面 replace**（content/cmds_ast.py:53-55），实测 '{t:.0f}' 永远不会被替换、会把字面量打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f} —— 两侧形态不同是有原因的，**别合并**。★ 图标按真源 26_ §2.2 语义分组逐条选（⚔️ 行动 · 🛡️ 防御/减伤 · 🩸 受伤/流血 · ✨ 强化/成功），并把 COMBAT_MECH_IMMUNE / MITIGATE 原有的 ✨ / 🛡️ 提到行首统一位置。★ 只改这一格的值与 params；读端（content/mech.py 各 logs.append）同步补 t=int(round(_now(battle)))。★ 这 18 格**不在**真源槽位表里（grep '| COMBAT_MECH_… |' 17_文案收口口径_v1 = 0 命中）⇒ 不是生成器拥有的行，不与真源打架。",
    },
    "COMBAT_MECH_BLOCK": {
        "old": "🛡️ 举盾挡下 —— 这一下轻了 {n} 点，守誓 +{oath}（现在 {cur}）。",
        "new": "🛡️【{t} 刻】举盾挡下 —— 这一下轻了 {n} 点，守誓 +{oath}（现在 {cur}）。",
        "why": "P0-1 续（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **判据的结构盲区**：probe_texts 那两条（活 cue 行带刻 / 行首统一图标）只按 content/rules/battle_text.json（引擎 62 个 cue）取件，**取不到内容侧 content/mech.py 那一族机制日志** ⇒ 这 18 格进的是**持久战斗日志**（_note_battle 把 logs 原样落档、『战斗日志』读它），实测屏上整场只有它们读不出刻数。★ 本格值写**纯 {t} 不写 {t:.0f}**：内容侧 T() 是**字面 replace**（content/cmds_ast.py:53-55），实测 '{t:.0f}' 永远不会被替换、会把字面量打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f} —— 两侧形态不同是有原因的，**别合并**。★ 图标按真源 26_ §2.2 语义分组逐条选（⚔️ 行动 · 🛡️ 防御/减伤 · 🩸 受伤/流血 · ✨ 强化/成功），并把 COMBAT_MECH_IMMUNE / MITIGATE 原有的 ✨ / 🛡️ 提到行首统一位置。★ 只改这一格的值与 params；读端（content/mech.py 各 logs.append）同步补 t=int(round(_now(battle)))。★ 这 18 格**不在**真源槽位表里（grep '| COMBAT_MECH_… |' 17_文案收口口径_v1 = 0 命中）⇒ 不是生成器拥有的行，不与真源打架。",
    },
    "COMBAT_MECH_DAZE": {
        "old": "星砸在【{name}】头上 —— 它晕了 {turns} 刻，下一手什么都做不了。",
        "new": "✨【{t} 刻】星砸在【{name}】头上 —— 它晕了 {turns} 刻，下一手什么都做不了。",
        "why": "P0-1 续（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **判据的结构盲区**：probe_texts 那两条（活 cue 行带刻 / 行首统一图标）只按 content/rules/battle_text.json（引擎 62 个 cue）取件，**取不到内容侧 content/mech.py 那一族机制日志** ⇒ 这 18 格进的是**持久战斗日志**（_note_battle 把 logs 原样落档、『战斗日志』读它），实测屏上整场只有它们读不出刻数。★ 本格值写**纯 {t} 不写 {t:.0f}**：内容侧 T() 是**字面 replace**（content/cmds_ast.py:53-55），实测 '{t:.0f}' 永远不会被替换、会把字面量打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f} —— 两侧形态不同是有原因的，**别合并**。★ 图标按真源 26_ §2.2 语义分组逐条选（⚔️ 行动 · 🛡️ 防御/减伤 · 🩸 受伤/流血 · ✨ 强化/成功），并把 COMBAT_MECH_IMMUNE / MITIGATE 原有的 ✨ / 🛡️ 提到行首统一位置。★ 只改这一格的值与 params；读端（content/mech.py 各 logs.append）同步补 t=int(round(_now(battle)))。★ 这 18 格**不在**真源槽位表里（grep '| COMBAT_MECH_… |' 17_文案收口口径_v1 = 0 命中）⇒ 不是生成器拥有的行，不与真源打架。",
    },
    "COMBAT_MECH_PINDOWN": {
        "old": "箭钉在它起手的地方 —— 【{name}】{turns} 刻里慢 {pct}%。",
        "new": "✨【{t} 刻】箭钉在它起手的地方 —— 【{name}】{turns} 刻里慢 {pct}%。",
        "why": "P0-1 续（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **判据的结构盲区**：probe_texts 那两条（活 cue 行带刻 / 行首统一图标）只按 content/rules/battle_text.json（引擎 62 个 cue）取件，**取不到内容侧 content/mech.py 那一族机制日志** ⇒ 这 18 格进的是**持久战斗日志**（_note_battle 把 logs 原样落档、『战斗日志』读它），实测屏上整场只有它们读不出刻数。★ 本格值写**纯 {t} 不写 {t:.0f}**：内容侧 T() 是**字面 replace**（content/cmds_ast.py:53-55），实测 '{t:.0f}' 永远不会被替换、会把字面量打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f} —— 两侧形态不同是有原因的，**别合并**。★ 图标按真源 26_ §2.2 语义分组逐条选（⚔️ 行动 · 🛡️ 防御/减伤 · 🩸 受伤/流血 · ✨ 强化/成功），并把 COMBAT_MECH_IMMUNE / MITIGATE 原有的 ✨ / 🛡️ 提到行首统一位置。★ 只改这一格的值与 params；读端（content/mech.py 各 logs.append）同步补 t=int(round(_now(battle)))。★ 这 18 格**不在**真源槽位表里（grep '| COMBAT_MECH_… |' 17_文案收口口径_v1 = 0 命中）⇒ 不是生成器拥有的行，不与真源打架。",
    },
    "COMBAT_MECH_SILENCE": {
        "old": "一声闷雷压下去 —— 【{name}】这 {turns} 刻里用不出技能。",
        "new": "✨【{t} 刻】一声闷雷压下去 —— 【{name}】这 {turns} 刻里用不出技能。",
        "why": "P0-1 续（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **判据的结构盲区**：probe_texts 那两条（活 cue 行带刻 / 行首统一图标）只按 content/rules/battle_text.json（引擎 62 个 cue）取件，**取不到内容侧 content/mech.py 那一族机制日志** ⇒ 这 18 格进的是**持久战斗日志**（_note_battle 把 logs 原样落档、『战斗日志』读它），实测屏上整场只有它们读不出刻数。★ 本格值写**纯 {t} 不写 {t:.0f}**：内容侧 T() 是**字面 replace**（content/cmds_ast.py:53-55），实测 '{t:.0f}' 永远不会被替换、会把字面量打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f} —— 两侧形态不同是有原因的，**别合并**。★ 图标按真源 26_ §2.2 语义分组逐条选（⚔️ 行动 · 🛡️ 防御/减伤 · 🩸 受伤/流血 · ✨ 强化/成功），并把 COMBAT_MECH_IMMUNE / MITIGATE 原有的 ✨ / 🛡️ 提到行首统一位置。★ 只改这一格的值与 params；读端（content/mech.py 各 logs.append）同步补 t=int(round(_now(battle)))。★ 这 18 格**不在**真源槽位表里（grep '| COMBAT_MECH_… |' 17_文案收口口径_v1 = 0 命中）⇒ 不是生成器拥有的行，不与真源打架。",
    },
    "COMBAT_MECH_BLEED": {
        "old": "刀口拉得很深 —— 【{name}】{turns} 刻里每 {intv} 刻失一次血（{stacks} 层）。",
        "new": "🩸【{t} 刻】刀口拉得很深 —— 【{name}】{turns} 刻里每 {intv} 刻失一次血（{stacks} 层）。",
        "why": "P0-1 续（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **判据的结构盲区**：probe_texts 那两条（活 cue 行带刻 / 行首统一图标）只按 content/rules/battle_text.json（引擎 62 个 cue）取件，**取不到内容侧 content/mech.py 那一族机制日志** ⇒ 这 18 格进的是**持久战斗日志**（_note_battle 把 logs 原样落档、『战斗日志』读它），实测屏上整场只有它们读不出刻数。★ 本格值写**纯 {t} 不写 {t:.0f}**：内容侧 T() 是**字面 replace**（content/cmds_ast.py:53-55），实测 '{t:.0f}' 永远不会被替换、会把字面量打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f} —— 两侧形态不同是有原因的，**别合并**。★ 图标按真源 26_ §2.2 语义分组逐条选（⚔️ 行动 · 🛡️ 防御/减伤 · 🩸 受伤/流血 · ✨ 强化/成功），并把 COMBAT_MECH_IMMUNE / MITIGATE 原有的 ✨ / 🛡️ 提到行首统一位置。★ 只改这一格的值与 params；读端（content/mech.py 各 logs.append）同步补 t=int(round(_now(battle)))。★ 这 18 格**不在**真源槽位表里（grep '| COMBAT_MECH_… |' 17_文案收口口径_v1 = 0 命中）⇒ 不是生成器拥有的行，不与真源打架。",
    },
    "COMBAT_MECH_TRANCE": {
        "old": "它的爪子撞在你的刀口上 —— 它自己挨了 {n} 点。",
        "new": "✨【{t} 刻】它的爪子撞在你的刀口上 —— 它自己挨了 {n} 点。",
        "why": "P0-1 续（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **判据的结构盲区**：probe_texts 那两条（活 cue 行带刻 / 行首统一图标）只按 content/rules/battle_text.json（引擎 62 个 cue）取件，**取不到内容侧 content/mech.py 那一族机制日志** ⇒ 这 18 格进的是**持久战斗日志**（_note_battle 把 logs 原样落档、『战斗日志』读它），实测屏上整场只有它们读不出刻数。★ 本格值写**纯 {t} 不写 {t:.0f}**：内容侧 T() 是**字面 replace**（content/cmds_ast.py:53-55），实测 '{t:.0f}' 永远不会被替换、会把字面量打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f} —— 两侧形态不同是有原因的，**别合并**。★ 图标按真源 26_ §2.2 语义分组逐条选（⚔️ 行动 · 🛡️ 防御/减伤 · 🩸 受伤/流血 · ✨ 强化/成功），并把 COMBAT_MECH_IMMUNE / MITIGATE 原有的 ✨ / 🛡️ 提到行首统一位置。★ 只改这一格的值与 params；读端（content/mech.py 各 logs.append）同步补 t=int(round(_now(battle)))。★ 这 18 格**不在**真源槽位表里（grep '| COMBAT_MECH_… |' 17_文案收口口径_v1 = 0 命中）⇒ 不是生成器拥有的行，不与真源打架。",
    },
    "COMBAT_MECH_IMMUNE": {
        "old": "✨ 这一下到不了身上。",
        "new": "✨【{t} 刻】这一下到不了身上。",
        "why": "P0-1 续（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **判据的结构盲区**：probe_texts 那两条（活 cue 行带刻 / 行首统一图标）只按 content/rules/battle_text.json（引擎 62 个 cue）取件，**取不到内容侧 content/mech.py 那一族机制日志** ⇒ 这 18 格进的是**持久战斗日志**（_note_battle 把 logs 原样落档、『战斗日志』读它），实测屏上整场只有它们读不出刻数。★ 本格值写**纯 {t} 不写 {t:.0f}**：内容侧 T() 是**字面 replace**（content/cmds_ast.py:53-55），实测 '{t:.0f}' 永远不会被替换、会把字面量打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f} —— 两侧形态不同是有原因的，**别合并**。★ 图标按真源 26_ §2.2 语义分组逐条选（⚔️ 行动 · 🛡️ 防御/减伤 · 🩸 受伤/流血 · ✨ 强化/成功），并把 COMBAT_MECH_IMMUNE / MITIGATE 原有的 ✨ / 🛡️ 提到行首统一位置。★ 只改这一格的值与 params；读端（content/mech.py 各 logs.append）同步补 t=int(round(_now(battle)))。★ 这 18 格**不在**真源槽位表里（grep '| COMBAT_MECH_… |' 17_文案收口口径_v1 = 0 命中）⇒ 不是生成器拥有的行，不与真源打架。",
    },
    "COMBAT_MECH_MITIGATE": {
        "old": "🛡️ 这一下被卸掉了 {pct}%。",
        "new": "🛡️【{t} 刻】这一下被卸掉了 {pct}%。",
        "why": "P0-1 续（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **判据的结构盲区**：probe_texts 那两条（活 cue 行带刻 / 行首统一图标）只按 content/rules/battle_text.json（引擎 62 个 cue）取件，**取不到内容侧 content/mech.py 那一族机制日志** ⇒ 这 18 格进的是**持久战斗日志**（_note_battle 把 logs 原样落档、『战斗日志』读它），实测屏上整场只有它们读不出刻数。★ 本格值写**纯 {t} 不写 {t:.0f}**：内容侧 T() 是**字面 replace**（content/cmds_ast.py:53-55），实测 '{t:.0f}' 永远不会被替换、会把字面量打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f} —— 两侧形态不同是有原因的，**别合并**。★ 图标按真源 26_ §2.2 语义分组逐条选（⚔️ 行动 · 🛡️ 防御/减伤 · 🩸 受伤/流血 · ✨ 强化/成功），并把 COMBAT_MECH_IMMUNE / MITIGATE 原有的 ✨ / 🛡️ 提到行首统一位置。★ 只改这一格的值与 params；读端（content/mech.py 各 logs.append）同步补 t=int(round(_now(battle)))。★ 这 18 格**不在**真源槽位表里（grep '| COMBAT_MECH_… |' 17_文案收口口径_v1 = 0 命中）⇒ 不是生成器拥有的行，不与真源打架。",
    },

    # ★ P0-1 续批二（2026-09-29 · aep0）：后撤/逃跑/打断/道具上限那一族补【N 刻】。
    "SYS_RECIPE_HEAD": {
        "old": "【配方】会做 {known} 道 · 还没学会 {locked} 道（凑到料就能做）",
        "new": "📜 【配方】会做 {known} 道 · 还没学会 {locked} 道（凑到料就能做）",
        "why": "P2-24（同批 · 文案修复车道 aep2）：图标取真源 26_ §2.2「📜 读东西」的延伸 ——"
               "配方屏列的是**一张表**（逐条配方），与指令表同为清单类，故与 SYS_HELP_HEAD 同锚。"
               "★ 这格在 17_ 槽位表里**没有**行（grep = 0）且 rebuild_syscopy.py 里也只在另一个备注里提到它"
               "（line 1171/1182，那里只是用它的「· 分隔」作为另一格的参照，并非生成源）"
               "⇒ 它不是生成器拥有的行，不与真源打架；仍一律走 DOC_PENDING 记录、便下一人可核。"
               "接法 SPACE 形，措辞零改动。",
    },

    "SYS_ITEM_SHOW_ASK": {
        "old": "看哪一件？打『查看 <东西>』。",
        "new": "看哪一件？打『查看 <东西>』。——板上那些编号就是委托，全文也得用它。",
        "why": "copy-p5：旧值一屏**三个指令名**（查看 / 看 <编号> / 悬赏）。保留了『看 <编号>』那个指向（那是唯一告诉玩家「如何看委托全文」的地方——`SYS_BOARD_HOW`「接<编号>接活 · 我的委托看进度」里没它），去掉了多余的『悬赏』那一步（看板的人本来就在板边上）。",
    },


    # ★ P0-1 续批三（2026-09-29 · aep0）：`_grant` / `_ward` 那一族 8 格补【N 刻】。
    #   上一轮漏网的原因写在每条 why 里（AST 看不见 helper 间接入口 + cue 表零命中 ⇒ 两处盲区叠加）。

    "COMBAT_MECH_STANDFAST": {
        "old": "你不退。{turns} 刻内，落上来的东西都轻 {pct}%。",
        "new": "🛡️【{t} 刻】你不退。{turns} 刻内，落上来的东西都轻 {pct}%。",
        "why": "P0-1 续批三（2026-09-29 · 文案车道 aep0 · **补上一轮的漏网一族**）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **上一轮为什么漏**（探针与 AST 两处盲区叠加）：① 枚举只按 `logs.append` / `hand.lines` 找入口，而这 8 格**经 `_grant()` / `_ward()` 两个 helper 间接进 logs**⇒ AST 看不见；② `probe_texts` 那两条判据按 content/rules/battle_text.json（引擎 62 个 cue）取件，而这 8 格**零 cue 映射**（grep battle_text.json = 0 命中）⇒ 判据也取不到。两处盲区叠在一起，于是这一族在两轮里一直是「绿但没接」。★ 本轮判据**只加强不削弱**：给 probe_texts 加一条独立判据「经 `_grant`/`_ward` 进持久战斗日志的那一族必须带【N 刻】」，取件从**那两个 helper 本体**现算（不再靠 cue 表）。★ 读端（content/mech.py）：`_grant` / `_ward` 各补 `t=int(round(_now(battle)))` —— 一处改覆盖 8 格，**别在调用点逐个补**（那正是上一轮的漏法）。★ 写**纯 {t} 不写 {t:.0f}**：内容侧 `T()` 是字面 replace（content/cmds_ast.py:53-55），'{t:.0f}' 永远不被替换、会把字面量打上屏（真机 e2e 实测过）；引擎 cue 那一族走 str.format 才写 {t:.0f}—— 两侧形态不同是有原因的，别合并。★ 图标按真源 26_ §2.2 语义分组：🛡️ 防御/减伤/招架（STANDFAST/AEGIS/REARGUARD/RIPOSTE/FROSTVEIL 五格同族）· 🩸 付代价（血债割自己一道口子）· ✨ 增益（守夜把手上的暖挪过来 / 侧身闪避）。★ 这 8 格**不在**真源 17_ 槽位表里（grep '| COMBAT_MECH_… |' = 0 命中 ×8）⇒ 不是生成器拥有的行，登记在册是为了两态互锁（不登记就红在 probe_copy ⑤ 与 probe_generators ②③）。",
    },
    "COMBAT_MECH_AEGIS": {
        "old": "你先把话垫在前面 —— {turns} 刻内，落上来的东西轻 {pct}%。",
        "new": "🛡️【{t} 刻】你先把话垫在前面 —— {turns} 刻内，落上来的东西轻 {pct}%。",
        "why": "P0-1 续批三（2026-09-29 · 文案车道 aep0 · **补上一轮的漏网一族**）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **上一轮为什么漏**（探针与 AST 两处盲区叠加）：① 枚举只按 `logs.append` / `hand.lines` 找入口，而这 8 格**经 `_grant()` / `_ward()` 两个 helper 间接进 logs**⇒ AST 看不见；② `probe_texts` 那两条判据按 content/rules/battle_text.json（引擎 62 个 cue）取件，而这 8 格**零 cue 映射**（grep battle_text.json = 0 命中）⇒ 判据也取不到。两处盲区叠在一起，于是这一族在两轮里一直是「绿但没接」。★ 本轮判据**只加强不削弱**：给 probe_texts 加一条独立判据「经 `_grant`/`_ward` 进持久战斗日志的那一族必须带【N 刻】」，取件从**那两个 helper 本体**现算（不再靠 cue 表）。★ 读端（content/mech.py）：`_grant` / `_ward` 各补 `t=int(round(_now(battle)))` —— 一处改覆盖 8 格，**别在调用点逐个补**（那正是上一轮的漏法）。★ 写**纯 {t} 不写 {t:.0f}**：内容侧 `T()` 是字面 replace（content/cmds_ast.py:53-55），'{t:.0f}' 永远不被替换、会把字面量打上屏（真机 e2e 实测过）；引擎 cue 那一族走 str.format 才写 {t:.0f}—— 两侧形态不同是有原因的，别合并。★ 图标按真源 26_ §2.2 语义分组：🛡️ 防御/减伤/招架（STANDFAST/AEGIS/REARGUARD/RIPOSTE/FROSTVEIL 五格同族）· 🩸 付代价（血债割自己一道口子）· ✨ 增益（守夜把手上的暖挪过来 / 侧身闪避）。★ 这 8 格**不在**真源 17_ 槽位表里（grep '| COMBAT_MECH_… |' = 0 命中 ×8）⇒ 不是生成器拥有的行，登记在册是为了两态互锁（不登记就红在 probe_copy ⑤ 与 probe_generators ②③）。",
    },
    "COMBAT_MECH_REARGUARD": {
        "old": "你把背后让出来 —— 这半拍晚一步（下一次出手推后 {ticks} 刻），换来 {turns} 刻里落上来的东西轻 {pct}%。",
        "new": "🛡️【{t} 刻】你把背后让出来 —— 这半拍晚一步（下一次出手推后 {ticks} 刻），换来 {turns} 刻里落上来的东西轻 {pct}%。",
        "why": "P0-1 续批三（2026-09-29 · 文案车道 aep0 · **补上一轮的漏网一族**）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **上一轮为什么漏**（探针与 AST 两处盲区叠加）：① 枚举只按 `logs.append` / `hand.lines` 找入口，而这 8 格**经 `_grant()` / `_ward()` 两个 helper 间接进 logs**⇒ AST 看不见；② `probe_texts` 那两条判据按 content/rules/battle_text.json（引擎 62 个 cue）取件，而这 8 格**零 cue 映射**（grep battle_text.json = 0 命中）⇒ 判据也取不到。两处盲区叠在一起，于是这一族在两轮里一直是「绿但没接」。★ 本轮判据**只加强不削弱**：给 probe_texts 加一条独立判据「经 `_grant`/`_ward` 进持久战斗日志的那一族必须带【N 刻】」，取件从**那两个 helper 本体**现算（不再靠 cue 表）。★ 读端（content/mech.py）：`_grant` / `_ward` 各补 `t=int(round(_now(battle)))` —— 一处改覆盖 8 格，**别在调用点逐个补**（那正是上一轮的漏法）。★ 写**纯 {t} 不写 {t:.0f}**：内容侧 `T()` 是字面 replace（content/cmds_ast.py:53-55），'{t:.0f}' 永远不被替换、会把字面量打上屏（真机 e2e 实测过）；引擎 cue 那一族走 str.format 才写 {t:.0f}—— 两侧形态不同是有原因的，别合并。★ 图标按真源 26_ §2.2 语义分组：🛡️ 防御/减伤/招架（STANDFAST/AEGIS/REARGUARD/RIPOSTE/FROSTVEIL 五格同族）· 🩸 付代价（血债割自己一道口子）· ✨ 增益（守夜把手上的暖挪过来 / 侧身闪避）。★ 这 8 格**不在**真源 17_ 槽位表里（grep '| COMBAT_MECH_… |' = 0 命中 ×8）⇒ 不是生成器拥有的行，登记在册是为了两态互锁（不登记就红在 probe_copy ⑤ 与 probe_generators ②③）。",
    },
    "COMBAT_MECH_BLOODDEBT": {
        "old": "你割开自己一道口子 —— 接下来 {turns} 刻，你的刀重 {pct}%。",
        "new": "🩸【{t} 刻】你割开自己一道口子 —— 接下来 {turns} 刻，你的刀重 {pct}%。",
        "why": "P0-1 续批三（2026-09-29 · 文案车道 aep0 · **补上一轮的漏网一族**）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **上一轮为什么漏**（探针与 AST 两处盲区叠加）：① 枚举只按 `logs.append` / `hand.lines` 找入口，而这 8 格**经 `_grant()` / `_ward()` 两个 helper 间接进 logs**⇒ AST 看不见；② `probe_texts` 那两条判据按 content/rules/battle_text.json（引擎 62 个 cue）取件，而这 8 格**零 cue 映射**（grep battle_text.json = 0 命中）⇒ 判据也取不到。两处盲区叠在一起，于是这一族在两轮里一直是「绿但没接」。★ 本轮判据**只加强不削弱**：给 probe_texts 加一条独立判据「经 `_grant`/`_ward` 进持久战斗日志的那一族必须带【N 刻】」，取件从**那两个 helper 本体**现算（不再靠 cue 表）。★ 读端（content/mech.py）：`_grant` / `_ward` 各补 `t=int(round(_now(battle)))` —— 一处改覆盖 8 格，**别在调用点逐个补**（那正是上一轮的漏法）。★ 写**纯 {t} 不写 {t:.0f}**：内容侧 `T()` 是字面 replace（content/cmds_ast.py:53-55），'{t:.0f}' 永远不被替换、会把字面量打上屏（真机 e2e 实测过）；引擎 cue 那一族走 str.format 才写 {t:.0f}—— 两侧形态不同是有原因的，别合并。★ 图标按真源 26_ §2.2 语义分组：🛡️ 防御/减伤/招架（STANDFAST/AEGIS/REARGUARD/RIPOSTE/FROSTVEIL 五格同族）· 🩸 付代价（血债割自己一道口子）· ✨ 增益（守夜把手上的暖挪过来 / 侧身闪避）。★ 这 8 格**不在**真源 17_ 槽位表里（grep '| COMBAT_MECH_… |' = 0 命中 ×8）⇒ 不是生成器拥有的行，登记在册是为了两态互锁（不登记就红在 probe_copy ⑤ 与 probe_generators ②③）。",
    },
    "COMBAT_MECH_RIPOSTE": {
        "old": "你不躲 —— {turns} 刻里谁碰你一下，就得挨你一刀（{pct}% 的攻击）。",
        "new": "🛡️【{t} 刻】你不躲 —— {turns} 刻里谁碰你一下，就得挨你一刀（{pct}% 的攻击）。",
        "why": "P0-1 续批三（2026-09-29 · 文案车道 aep0 · **补上一轮的漏网一族**）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **上一轮为什么漏**（探针与 AST 两处盲区叠加）：① 枚举只按 `logs.append` / `hand.lines` 找入口，而这 8 格**经 `_grant()` / `_ward()` 两个 helper 间接进 logs**⇒ AST 看不见；② `probe_texts` 那两条判据按 content/rules/battle_text.json（引擎 62 个 cue）取件，而这 8 格**零 cue 映射**（grep battle_text.json = 0 命中）⇒ 判据也取不到。两处盲区叠在一起，于是这一族在两轮里一直是「绿但没接」。★ 本轮判据**只加强不削弱**：给 probe_texts 加一条独立判据「经 `_grant`/`_ward` 进持久战斗日志的那一族必须带【N 刻】」，取件从**那两个 helper 本体**现算（不再靠 cue 表）。★ 读端（content/mech.py）：`_grant` / `_ward` 各补 `t=int(round(_now(battle)))` —— 一处改覆盖 8 格，**别在调用点逐个补**（那正是上一轮的漏法）。★ 写**纯 {t} 不写 {t:.0f}**：内容侧 `T()` 是字面 replace（content/cmds_ast.py:53-55），'{t:.0f}' 永远不被替换、会把字面量打上屏（真机 e2e 实测过）；引擎 cue 那一族走 str.format 才写 {t:.0f}—— 两侧形态不同是有原因的，别合并。★ 图标按真源 26_ §2.2 语义分组：🛡️ 防御/减伤/招架（STANDFAST/AEGIS/REARGUARD/RIPOSTE/FROSTVEIL 五格同族）· 🩸 付代价（血债割自己一道口子）· ✨ 增益（守夜把手上的暖挪过来 / 侧身闪避）。★ 这 8 格**不在**真源 17_ 槽位表里（grep '| COMBAT_MECH_… |' = 0 命中 ×8）⇒ 不是生成器拥有的行，登记在册是为了两态互锁（不登记就红在 probe_copy ⑤ 与 probe_generators ②③）。",
    },
    "COMBAT_MECH_FROSTVEIL": {
        "old": "霜从你脚底结上来 —— {turns} 刻里落上来的东西轻 {pct}%，你自己的法术也轻 {cost}%。",
        "new": "🛡️【{t} 刻】霜从你脚底结上来 —— {turns} 刻里落上来的东西轻 {pct}%，你自己的法术也轻 {cost}%。",
        "why": "P0-1 续批三（2026-09-29 · 文案车道 aep0 · **补上一轮的漏网一族**）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **上一轮为什么漏**（探针与 AST 两处盲区叠加）：① 枚举只按 `logs.append` / `hand.lines` 找入口，而这 8 格**经 `_grant()` / `_ward()` 两个 helper 间接进 logs**⇒ AST 看不见；② `probe_texts` 那两条判据按 content/rules/battle_text.json（引擎 62 个 cue）取件，而这 8 格**零 cue 映射**（grep battle_text.json = 0 命中）⇒ 判据也取不到。两处盲区叠在一起，于是这一族在两轮里一直是「绿但没接」。★ 本轮判据**只加强不削弱**：给 probe_texts 加一条独立判据「经 `_grant`/`_ward` 进持久战斗日志的那一族必须带【N 刻】」，取件从**那两个 helper 本体**现算（不再靠 cue 表）。★ 读端（content/mech.py）：`_grant` / `_ward` 各补 `t=int(round(_now(battle)))` —— 一处改覆盖 8 格，**别在调用点逐个补**（那正是上一轮的漏法）。★ 写**纯 {t} 不写 {t:.0f}**：内容侧 `T()` 是字面 replace（content/cmds_ast.py:53-55），'{t:.0f}' 永远不被替换、会把字面量打上屏（真机 e2e 实测过）；引擎 cue 那一族走 str.format 才写 {t:.0f}—— 两侧形态不同是有原因的，别合并。★ 图标按真源 26_ §2.2 语义分组：🛡️ 防御/减伤/招架（STANDFAST/AEGIS/REARGUARD/RIPOSTE/FROSTVEIL 五格同族）· 🩸 付代价（血债割自己一道口子）· ✨ 增益（守夜把手上的暖挪过来 / 侧身闪避）。★ 这 8 格**不在**真源 17_ 槽位表里（grep '| COMBAT_MECH_… |' = 0 命中 ×8）⇒ 不是生成器拥有的行，登记在册是为了两态互锁（不登记就红在 probe_copy ⑤ 与 probe_generators ②③）。",
    },
    "COMBAT_MECH_NIGHTWATCH": {
        "old": "你把灯挪到自己跟前 —— {turns} 刻里落上来的东西轻 {pct}%，手上的暖多 {gain}%。",
        "new": "✨【{t} 刻】你把灯挪到自己跟前 —— {turns} 刻里落上来的东西轻 {pct}%，手上的暖多 {gain}%。",
        "why": "P0-1 续批三（2026-09-29 · 文案车道 aep0 · **补上一轮的漏网一族**）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **上一轮为什么漏**（探针与 AST 两处盲区叠加）：① 枚举只按 `logs.append` / `hand.lines` 找入口，而这 8 格**经 `_grant()` / `_ward()` 两个 helper 间接进 logs**⇒ AST 看不见；② `probe_texts` 那两条判据按 content/rules/battle_text.json（引擎 62 个 cue）取件，而这 8 格**零 cue 映射**（grep battle_text.json = 0 命中）⇒ 判据也取不到。两处盲区叠在一起，于是这一族在两轮里一直是「绿但没接」。★ 本轮判据**只加强不削弱**：给 probe_texts 加一条独立判据「经 `_grant`/`_ward` 进持久战斗日志的那一族必须带【N 刻】」，取件从**那两个 helper 本体**现算（不再靠 cue 表）。★ 读端（content/mech.py）：`_grant` / `_ward` 各补 `t=int(round(_now(battle)))` —— 一处改覆盖 8 格，**别在调用点逐个补**（那正是上一轮的漏法）。★ 写**纯 {t} 不写 {t:.0f}**：内容侧 `T()` 是字面 replace（content/cmds_ast.py:53-55），'{t:.0f}' 永远不被替换、会把字面量打上屏（真机 e2e 实测过）；引擎 cue 那一族走 str.format 才写 {t:.0f}—— 两侧形态不同是有原因的，别合并。★ 图标按真源 26_ §2.2 语义分组：🛡️ 防御/减伤/招架（STANDFAST/AEGIS/REARGUARD/RIPOSTE/FROSTVEIL 五格同族）· 🩸 付代价（血债割自己一道口子）· ✨ 增益（守夜把手上的暖挪过来 / 侧身闪避）。★ 这 8 格**不在**真源 17_ 槽位表里（grep '| COMBAT_MECH_… |' = 0 命中 ×8）⇒ 不是生成器拥有的行，登记在册是为了两态互锁（不登记就红在 probe_copy ⑤ 与 probe_generators ②③）。",
    },
    "COMBAT_MECH_SIDESTEP": {
        "old": "你侧过半个身子 —— {turns} 刻里闪避涨 {pct}%。",
        "new": "✨【{t} 刻】你侧过半个身子 —— {turns} 刻里闪避涨 {pct}%。",
        "why": "P0-1 续批三（2026-09-29 · 文案车道 aep0 · **补上一轮的漏网一族**）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **上一轮为什么漏**（探针与 AST 两处盲区叠加）：① 枚举只按 `logs.append` / `hand.lines` 找入口，而这 8 格**经 `_grant()` / `_ward()` 两个 helper 间接进 logs**⇒ AST 看不见；② `probe_texts` 那两条判据按 content/rules/battle_text.json（引擎 62 个 cue）取件，而这 8 格**零 cue 映射**（grep battle_text.json = 0 命中）⇒ 判据也取不到。两处盲区叠在一起，于是这一族在两轮里一直是「绿但没接」。★ 本轮判据**只加强不削弱**：给 probe_texts 加一条独立判据「经 `_grant`/`_ward` 进持久战斗日志的那一族必须带【N 刻】」，取件从**那两个 helper 本体**现算（不再靠 cue 表）。★ 读端（content/mech.py）：`_grant` / `_ward` 各补 `t=int(round(_now(battle)))` —— 一处改覆盖 8 格，**别在调用点逐个补**（那正是上一轮的漏法）。★ 写**纯 {t} 不写 {t:.0f}**：内容侧 `T()` 是字面 replace（content/cmds_ast.py:53-55），'{t:.0f}' 永远不被替换、会把字面量打上屏（真机 e2e 实测过）；引擎 cue 那一族走 str.format 才写 {t:.0f}—— 两侧形态不同是有原因的，别合并。★ 图标按真源 26_ §2.2 语义分组：🛡️ 防御/减伤/招架（STANDFAST/AEGIS/REARGUARD/RIPOSTE/FROSTVEIL 五格同族）· 🩸 付代价（血债割自己一道口子）· ✨ 增益（守夜把手上的暖挪过来 / 侧身闪避）。★ 这 8 格**不在**真源 17_ 槽位表里（grep '| COMBAT_MECH_… |' = 0 命中 ×8）⇒ 不是生成器拥有的行，登记在册是为了两态互锁（不登记就红在 probe_copy ⑤ 与 probe_generators ②③）。",
    },


    "SYS_FOOT_HEAD": {
        "old": "【记录】走过 {places} 个地方 · 打过 {kills} 只 · {days} 个游戏日",
        "new": "📊 【记录】走过 {places} 个地方 · 打过 {kills} 只 · {days} 个游戏日",
        "why": "P2-26（第 ③ 问取证）：`足迹` 屏（cmds_codex.py::footprint）抬头裸【】起头，"
               "屏内 SYS_FOOT_MORE / _BOOKS 两条都是行首 `· ` 的统计行。"
               "★ 屏上是一张**纯统计面板**（走过/打过/读过/采过/交过 + 四本谱进度）⇒ 真源 26_ §2.2 逐字「📊 面板 / 状态 —— 属性、背包、面板」，"
               "且本包已固化为该语义（SYS_ATTR_HEAD / SYS_STATUS_HEAD / SYS_RANKING_HEAD）。"
               "★ 同屏那两条 `· ` 行按既定口径 `· ` 本身即行首锚、不叠图标 ⇒ 只动抬头这一格。",
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
