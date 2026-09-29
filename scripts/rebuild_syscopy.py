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
    "SYS_BOARD_HEAD": {
        "old": "【挂板墙】板上钉着一叠单子。最新的一张还有墨味。",
        "new": "📜 【挂板墙】板上钉着一叠单子。最新的一张还有墨味。",
        "why": "P2-3 真缺陷（现算 + 真机取证）：**同一个挂板墙屏**里 SYS_BOARD_BOUNTY_HEAD / "
               "SYS_BOARD_SIDE_HEAD 两条都带 📜，只有本条抬头裸【】起头 ⇒ 一屏三行、两行带图标一行不带。"
               "📜 在本包已固化为『读东西/清单/单子』语义（四条 _HEAD 都在用）⇒ 本条归 📜。"
               "只改这一格的值，params 空、无槽位，取件点一字未动。",
    },
    "SYS_ATTR_HEAD": {
        "old": "【属性】{who} · {cls} · {level} 级",
        "new": "📊 【属性】{who} · {cls} · {level} 级",
        "why": "P2-3 缺口（真机试玩 10:36 实测）：『属性』整屏**零图标**（20 条里 0 条带），"
               "而同一个包里 SYS_STATUS_HEAD 早就用 📊、真源 26_ §2.2 逐字『📊 面板/状态 —— 属性』。"
               "⇒ 抬头补 📊。★ 刻意不碰 SYS_ATTR_ROW（· 锚点）与 SYS_STAT_* 那一族裸标签："
               "  那族被三处复用（属性页/装备词条/增益名），是标签不是行首锚（见 _notes.md P2-17 同款判据）。",
    },
    "SYS_ATTR_VITAL": {
        "old": "生命上限 {hp} ｜ 法力 {mo} ｜ 暴击率 {crit}%",
        "new": "📊 生命上限 {hp} ｜ 法力 {mo} ｜ 暴击率 {crit}%",
        "why": "P2-3 缺口（同上一条）：属性屏的**三格读数行**同样零图标；与抬头同属一屏、"
               "同属 📊 语义（面板/状态）⇒ 一并补齐。｜ 分栏写法一字未动（与 P2-15 定的那套口径同族）。",
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
        "new": '名字一排排往下刻。\n刻痕很深，\n边角还利\n ——\n 有几个名字眼熟，\n你想不起在哪儿见过。',
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
    "COMBAT_NO_TARGET": {"old": "（场上没有能打的了 —— 这一场就到这儿。）", "new": "⚠️【{t:.0f} 刻】场上没有能打的了 —— 这一场就到这儿。", "why": "P0-1 收口（战斗时间轴 · 真源 26_ §三 优化 1）："
               "同 `COMBAT_BLOCKED_AMOUNT` 那一笔 —— 此前登记的理由「续行片段不加刻」**不成立**："
               "引擎 `actions.py:154-156` 把 `battle.actions.no_target` 的 logs 收进**独立列表**并 return，"
               "包侧照样逐行出屏 ⇒ 它是独立一行，不是任何一行的续行。"
               "★ 触发时机 = 出手时场上已无敌方（`target is None`）⇒ 屏上会出现一条**没有刻数**的战斗行，"
               "而同一屏其它行都有 —— 正是优化 1 要消灭的「读不出先后」。"
               "★ 图标按真源 §2.2 取 ⚠️（预警），与同族 `COMBAT_CORE_NO_ACTOR` / `COMBAT_CORE_UNKNOWN_ACTION` 一致。"
               "★ `params` 同步加 `t`；引擎零改动；这格在真源槽位表里**在册**（`17_…:1017`）⇒ "
               "本登记是「改值」的唯一合法路径（生成器只增不删，故必须在 DOC_PENDING 跟账）。"},
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
    "SYS_PARTY_OFF": {
        "old": "队伍读不出来 —— 存档库没接上。",
        "new": "队伍读不出来 —— 这一办的事写不进去。\n💡 你自己还是能打 —— 你玩的那一打照常。",
        "why": "P0-2（剩余两条之一）：读端 content/cmds_party.py:184/221/241/278（四处「看队 / 邀人 / "
               "退队 / 提问」的前置分支，_load_rows 抛 PT.PartyError 时返回 None）。"
               "屏上的「存档库没接上」是工程自述，改成「这一办的事写不进去」（玩家能懂的失败）"
               "+ 一句还能干什么。★ 判据不用松：scripts/probe_party.py:559 拿**槽位名**比"
               "（got == [_r(\"SYS_PARTY_OFF\")]），不写死中文子串 ⇒ 值怎么改都对得上，判据一个字未改。",
    },
    "SYS_RANKING_OFF": {
        "old": "榜读不出来 —— 存档库没接上。",
        "new": "榜读不出来 —— 这一办的事写不进去。",
        "why": "P0-2（剩余两条之二）：读端 content/cmds_self.py:234（ranking_page，_board_rows "
               "抛异常时的 fail-closed 分支）。病根与 SYS_PARTY_OFF 同（层不一样、但都是"
               "「这一办没装」）。这条不叠「打不打的打」的句子（不在一个上下文里）。"
               "★ 无探针按中文字符串钉它（scripts/probe_* 里 grep 主动引用的只有「槽位名」，"
               "无一处写死「存档库没接上」）。",
    },
    "COMBAT_FOCUS_PARTY": {
        "old": "🚧「集火」还没接上\n💡 全队打同一个还没做 —— 这一场各自出手。",
        "new": "队伍里现在没人能统一出手 —— 这一场各打各的。\n💡 你打的那只就是它 —— 敲『攻击』时，它会照着你先打的那只走。",
        "why": "P0-2：开发口吻不该上屏（真源 26 §三 优化1 一族的同一问题：屏上要的是实况）。"
               "功能侧「全队打同一个」仍缺（真源 17_组队与策略配合 §三·8 未落地）—— "
               "本条**只改措辞**，读端与分支行为一字未动。"
               "★ P0-2 续批（2026-09-29 夜班）：上一版那半句「等集火接上，敲『集火 <目标>』"
               "能让全队打同一只」**仍是开发口吻**（它承诺的那条命令在多人场里回的就是"
               "本句自己 —— `cmds_battle.focus_fire:919` 那个 `_party_now != 1` 分支），"
               "玩家照着敲只会再读到一遍「没人能统一出手」⇒ 改成他**现在真做得到**的那一步"
               "（`content/instance.py::_focus_actor` + `_FOCUS_ACTIONS`：只有 `attack` 吃集火锁）。",
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
    "SYS_GEAR_HP_CAP": {
        "old": "生命上限 {old} → {new}",
        "new": "📊 生命上限 {old} → {new}",
        "why": "P2-3（同上）：『加点』屏第二行（上限变化）同样无锚。"
               "★ 同一格有**三处读端**（cmds_ast 加点 · cmds_gear 穿上/卸下）⇒ 补一次三屏同受益。"
               "语义取 `📊`（数值读数），与本屏上一行 `SYS_ALLOC_OK` 同族同锚。",
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
    # ===== P2-12（文案车道 aep2 · 并列行的可选标记自带分隔）=====
    #   现象：建号第二步那个六行菜单，`{star}`（推荐角标）**紧贴序号**渲染成
    #   `③★推荐 🏹 游侠`（真渲染实测，非推测）。根因**不在模板、在角标那格自己
    #   没带分隔**：仓里可选后缀槽位的先例是 `SYS_BOARD_ACTIVE`「（进行中）」
    #   （用法 `{name}{mark}`）⇒ **靠全角括号自带前导分隔**。`SYS_CLS_STAR` 当年是写成
    #   「行首锚」（`★推荐` 起头），改用到后缀位置却没跟着补分隔。
    #   改法（两格一起，缺一不可）：
    #     ① `SYS_CLS_ROW` 把 `{star}` 挪到 `{name}（{role}）` **之后**（= 后缀位），并去掉原处那个
    #        紧贴 `{i}` 的拼接 ⇒ 序号 / 图标 / 职业名各自留空格。
    #     ② `SYS_CLS_STAR` 补前导空格 ⇒ 角标自己是「 ★推荐」一整段，两边都干净。
    #   ★ 为什么不选「`{i} {star} {icon}`」那种：`star` 为空时会留**双空格**（`①  🛡️ 骑士`），
    #     六行里四行多一格 ⇒ 反而更不齐（真渲染验证过）。
    #   ★ 真渲染对照：带角标 `③ 🏹 游侠（远程输出） ★推荐 —— …` /
    #     不带 `① 🛡️ 骑士（塔克） —— …`（无多余空格）。
    #   ★ 取件点 `content/cmds_ast.py:512` 的 `_cls_star` 一个字没动；`probe_class` 的期望行是用
    #     **同一个槽位**现算的 ⇒ 判据自动跟随，**没改任何既有探针**。
    #   ★ 真源表（真源仓**只读**）那两行本轮不动 —— 它们还是旧句；
    #     下一位接手时把这两行改到新句（真源仓单写）。
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
    "SYS_STATUS_HEAD": {
        "old": "【{who}】{race} · {cls} · {level} 级",
        "new": "📊 【{who}】{race} · {cls} · {level} 级",
        "why": "P2-17（2026-09-29 · 文案修复车道 aep2 · e2e_drive 真机试玩取证）："
               "「状态」是建号之后玩家敲得最多的那一屏，而它是**整屏 0 图标** —— 顶行抬头、"
               "资源读数行、经验行三格全是裸文字（实测屏：`【测试】人类 · 骑士 · 1 级` / "
               "`生命 116/116 ｜ 法力 50/50 ｜ 铜板 30` / `经验 0 ｜ 在 风车镇`）。"
               "★ 图标取自真源 `26_ §2.2` 既定词典那一行「📊 面板 / 状态 · 属性、背包、面板」，"
               "**不是自创**（本包此前 📊 计数为 0，这一格是首次启用）。"
               "★ 只给这一屏的三个**整行**加锚，不碰 `SYS_STAT_*` 那一族裸中文标签 —— "
               "它们被「属性」页行标签 / 装备词条 / 增益名三处复用（`cmds_ast.py:1444`·"
               "`cmds_gear.py:66`·`cmds_ast.py:1760`），是**标签**不是行首锚，塞图标会串到三处屏上。"
               "取件点 `cmds_ast.py::status` 一个字没动。"
               "｜ P2-3b（2026-09-29 · aep2 · 本车道自己上一批的收口）：上面那笔（P2-17）给这一屏"
               "三格补了 📊，却把顶行写成 `📊【{who}】`（图标后**无**空格），而同屏另外两格是 "
               "`📊 生命 …` / `📊 经验 …`（图标后**有**空格）⇒ **同一屏、同一个 📊、两种接法**，"
               "被新立的面禁 `scripts/probe_emoji_order.py` 判据① 当场抓到。收敛方向选「图标+空格」"
               "（不是反过来给两行读数塞【】—— 那屏只有顶行有【】语义）。"
               "★ 因此这一格是**三笔叠起来**的：真源那一版 →（P2-17）`📊【…】`→（P2-3b）`📊 【…】`。"
               "按 `probe_copy._doc_ok` 的契约，`old` 仍取**真源表里那一版**（表里处于「旧值 / 跟账后」"
               "两态之一即可），中间那一版写在 why 里 —— 别把 `old` 改成中间态，那会让真源表"
               "对不上、当场红。",
    },
    "SYS_STATUS_VITALS": {
        "old": "生命 {hp}/{hp_max} ｜ 法力 {mo}/{mo_max} ｜ 铜板 {gold}",
        "new": "📊 生命 {hp}/{hp_max} ｜ 法力 {mo}/{mo_max} ｜ 铜板 {gold}",
        "why": "P2-17：同上一条的 why（同一屏 · 同一语义「面板/状态」· 同一个 📊）。"
               "★ 这一行的三个读数**同屏并列且同级**（生命 / 法力 / 铜板），所以只给整行一个行首锚、"
               "行内的 `｜` 分栏保持原样 —— 与 P2-15 定的「行内 `｜` 作分栏」口径同族。",
    },
    "SYS_STATUS_EXP": {
        "old": "经验 {exp} ｜ 在 {place}",
        "new": "📊 经验 {exp} ｜ 在 {place}",
        "why": "P2-17：同上一条的 why。"
               "★ 地点那一格用 📍 更贴切，但那会让同屏三行出现两个不同锚（④ 判据红），"
               "而这一屏整体是「面板」⇒ 统一 📊，位置语义留给场景头那一族（📍）管。",
    },
    # ===== P2-3b（文案车道 aep2 · 同屏同一图标的**连接形**统一 · 2026-09-29）=====
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
    "SYS_SKILL_HEAD": {
        "old": "【技能】{cls} · 已会 {known} 条 ｜ 还没到等级 {locked} 条",
        "new": "📜 【技能】{cls} · 已会 {known} 条 · 还没到等级 {locked} 条",
        "why": "P2-9①：47 条 _HEAD 里唯一一行同时混 · 与 ｜ 的；且它自己的双生句 "
               "SYS_RECIPE_HEAD（同为「会做 N / 还没学会 M」）两个分隔符都是 · ⇒ 以它为准。"
               "只改这一格的值，cls/known/locked 三个槽位与取件点 content/cmds_skill.py:121 "
               "一个字没动；两支采该槽位的探针（probe_cmds.py 711/819）是现取槽位的，"
               "不硬编字符串字面量 ⇒ 跟随。"
               "★ P2-18 续（2026-09-29 · 文案车道 aep2）：这一格的真机试玩证明『技能』整屏零图标"
               "（17 条里 0 条带）⇒ 抬头补 📜（本包已用它专表『清单/册子』：SMITH_CRAFT_HEAD /"
               "SMITH_SRC_HEAD 同族）。**new 已随之带上图标**，故与 P2-9 那一层合并成一条、"
               "不留两个重名条目（Python 后者覆盖前者 ⇒ 登记会静默失效）。"
               "分隔符那一层（｜→·）继续有效，本次只加图标、没再动它。",
    },
    "SYS_CMP_HEAD": {
        "old": "【对比】{name}（{quality} · {kind}） ｜ 现在这件：{cur}",
        "new": "📊 【对比】{name}（{quality} · {kind}） · 现在这件：{cur}",
        "why": "P2-26（**本条把先后两笔合进一对** —— DOC_PENDING 一个 key 只存一对 {old,new}，而这一格有两笔：P2-9② 把 ｜ 收敛成 ·、P2-26 再加 📊；真源 17_ 槽位表仍停在**第一笔之前**那个 ｜ 值 ⇒ old 必须取表里现值，否则 pending_ok 判「跟账第三态」、生成器当场抛。与 P0 对 COMBAT_CORE_SILENCED 的处理同族：合并不丢口径，两笔的意图都写在这一条里。）对比屏（cmds_gear.py:411）抬头裸【】起头，屏内 SYS_CMP_ROW 是行首 `· ` 的**属性**行（「生命上限 {old} → {new}」）⇒ 屏上是一张「这件 vs 你身上那件」的属性对比表 ⇒ 真源 26_ §2.2「📊 面板 / 状态」，同族 SYS_GEAR_HP_CAP / SYS_ATTR_VITAL 已固化。★ 不用 📍：槽位名里没有地图，屏上也没有一行在讲位置。★ P2-9② 的分隔符口径（拿本屏 _ROW / _NOTE_CUR / _NOTE_NEW 自己的 `· ` 作准）仍有效。",
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
        "new": "◆ {name} 正押着一手 —— 那一手还有 {left} 刻落到你身上。",
        "why": "P0-4（本车道真缺陷）：这是**全包唯一一条把刻数写成「秒」的**玩家可见文案，"
               "而真源那一行自己的来源列就写着「剩几刻」，真源口径与字面偏离。"
               "实测传值：`content/instance.py:767` 给的是 `cast_done_at - now`，即引擎 CTB 的**刻数**"
               "（1 刻 = 1 游戏秒，但对玩家只能写「刻」）⇒ 原句把一个刻数说成秒数，快慢不可比。"
               "口径：交接指南三轴第三条锁定「刻 / 行动机会」、禁用「回合」；"
               "本包 931 条槽位里「回合」已归零、「秒」只剩这一条 ⇒ 改它是最后一个。"
               "只改这一格的值；取件点 `content/instance.py:767` 与 `params` 一字未动。",
    },
    # ===== P0-5（文案修复车道 aep0 · 2026-09-29）· 槽位名与后文黏在一起 =====
    # 真机试玩取证（e2e_drive 真跑 骑士 vs † 群居的林鸦 †）：
    #   屏上打出 "◆ † 群居的林鸦 †手上是空的" —— 名字的尾随空格被中文吃了。
    # ⇒ 精英显示名自带尾随空格，这一族槽位把 {name} 紧贴中文 ⇒ 名字少半个括号。
    #   全表同类只有 4 处（{name}/{who} 之后直接接汉字），本批改这 4 处里
    #   **在真源 17_ 槽位表里的那几格**；不在表里的走 texts 直改。
    "COMBAT_TURN_FOE_IDLE": {
        "old": "◆ {name}手上是空的 —— 这一拍它没押着招。",
        "new": "◆ {name} 手上是空的 —— 这一拍它没押着招。",
        "why": "P0-5：精英名带尾随空格，紧贴中文会读成「†…†手上」——"
               "名字少半个括号。屏上取证见 e2e_drive 真跑。只改这一格的值；"
               "取件点 content/instance.py:775 与 params 一字未动。",
    },
    "SYS_ENHANCE_SHOP": {
        "old": "柯尔的炉子还热着。\n强化 = 材料（铁屑 · 硬骨）+ 钱；+1..+5 必成，+6 起看运气。\n打『强化 <装备名>』。",
        "new": "📜 柯尔的炉子还热着。\n强化 = 材料（铁屑 · 硬骨）+ 钱；+1..+5 必成，+6 起看运气。\n打『强化 <装备名>』。",
        "why": "P2-3 续批（本车道真缺陷 · 同一界面内图标不一致）：铁匠铺这一屏有**四个并列列表抬头**，"
               "其中两个带 📜（`SYS_SMITH_CRAFT_HEAD`「炉边那堆料…」· `SYS_SMITH_SRC_HEAD`「这几���料从哪儿来：」），"
               "另外两个不带 ⇒ 实屏（e2e_drive 真敲『去 半截铁砧』→『铁匠铺』）四段同屏时两段带图标两段不带。"
               "口径：鱼鱼「emoji 少不算缺陷，但**同一界面内用法要一致**」；"
               "📜 在本包已固化为「读东西/清单/单子」语义（四条 HEAD 全用它）⇒ 另两段归 📜。",
    },
    "SYS_SMITH_GOODS": {
        "old": "柜上摆着柯尔自己打的粗货。比不上外头捡来的，胜在现成。",
        "new": "📜 柜上摆着柯尔自己打的粗货。比不上外头捡来的，胜在现成。",
        "why": "P2-3 续批（同上那一条的另一半）：粗货货架抬头与同屏的打造/出处两段写法不一致 —— "
               "与 `SYS_ENHANCE_SHOP` 同批同因，两条一起改才是**同一界面内一致**。"
               "★ 只改这一格的值；取件点 `content/cmds_recipe.py:275` 与 `params` 一字未动。",
    },    # ===== P2-10（2026-09-29 夜班 · aep2）—— 战斗屏上那两条读数的图标混用 =====
    #   缺口（不是任务书那个数字，是冻结基线自己说的事）：
    #     `content/instance.py::_res_rows` 把 `COMBAT_TURN_MP` 与 `COMBAT_TURN_RES` 两条**相连接输出**
    #     到同一屏（一个人马力一条 + 他的职业资源一条）。
    #     而它们的行首图标**各用一个**：`⚡`（法力）与 `🔹`（资源）。
    #     取证：`scripts/_baseline_instance_solo.json`（冻结基线·探针 ⑤ 逐字对账用的那份）
    #     里就排着这两行 —— `⚡ 法力 50/50` 与 `🔹【守誓值〒12/100`。
    #   口径（与本车道 P2-1 / P2-3 一致）：同一屏同一角色必须同一图标。
    #     这两条是**同一类东西**（屏上的资源读数，不是两种语义）。
    #     法力在本包已固化为 `⚡`（`COMBAT_MP_LACK` / `COMBAT_RES_LACK` / `COMBAT_RES_SHORT` 三条）。
    #   改法：`COMBAT_TURN_RES` 行首 `🔹` → `⚡`，**只改那一格图标**。
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
    "SYS_GEAR_EQUIP_OK": {
        "old": "你穿上了{icon}{name}（{kind}）。",
        "new": "📦 你穿上了{icon}{name}（{kind}）。",
        "why": "P2-11（同族结果行行首锚统一）：与 📦 存取箱子 / 💰 买卖 / 🗑️ 丢弃同族，"
               "原来行首没有语义锚（`{icon}` 是物品自身图标，不是行首锚）。★ 只加行首一格。",
    },
    "SYS_GEAR_UNEQUIP_OK": {
        "old": "你卸下了{icon}{name}（{kind}）—— 收进背包。",
        "new": "📦 你卸下了{icon}{name}（{kind}）—— 收进背包。",
        "why": "P2-11（同上）：与穿上同族；『装备』连敲两下就能看到两行同屏，必须同一个锚。",
    },
    "COMBAT_SWAP_OK": {
        "old": "你换上了{icon}{name}（{kind}）—— 这一手花在换手上。",
        "new": "📦【{t} 刻】你换上了{icon}{name}（{kind}）—— 这一手花在换手上。",
        "why": "P2-11（同上）：`换武器` 有两个读端 —— 打得起来走这一条、打不起来回 "
               "`SYS_GEAR_EQUIP_OK`（`content/cmds_battle.py:1005/1021`）"
               "⇒ 同一个动作的三条结果行可能挨着上屏。"
               " ★ P0-1 续批五（2026-09-29 · aep0）在**同一个 `new` 上续**（不是另起一条登记 —— "
               "`DOC_PENDING` 一个 key 只存一对 {old,new}，真源仍停在 `old` 那一版 ⇒ "
               "再加一对会落成「跟账第三态」当场 fail-closed，见 `_notes.md §三`）："
               "补【N 刻】—— 真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。"
               " ★ **这一格是实测出来最后一条进持久战斗日志却不带刻的**：`Hand(swap).override` "
               "把这一行塞进引擎 `logs` ⇒ 两条路径（场里那一手 / 冷启动那一支）都进 `_note_battle` "
               "落档、『战斗日志』原样读它；屏上它夹在【165 刻】与【227 刻】中间读不出刻数。"
               " ★ 写**纯 {t}**（内容侧 `T()` 是字面 replace，`{t:.0f}` 不会被替换）。",
    },
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
    "COMBAT_RETREAT_BLOCK": {
        "old": "{name} 正押着一手 —— 退不开，这一手白花。",
        "new": "⚔️【{t} 刻】{name} 正押着一手 —— 退不开，这一手白花。",
        "why": "P0-1 续（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。这几格经 `logs.append` / `hand.lines` 进**持久战斗日志**（`_note_battle` 原样落档、『战斗日志』读它），实测屏上它们是最后读不出刻数的那一批。★ 写**纯 {t} 不写 {t:.0f}**：内容侧 `T()` 是**字面 replace**（content/cmds_ast.py:53-55），实测 '{t:.0f}' 永远不被替换、会把字面量打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f}。★ 读端同步补 t：`_retreat_decide`/`_flee_decide` 用 `Battle._now` 现读（与 content/mech.py:293、content/battle_acts.py 新增的 `_now` 逐字同形）；`cmds_battle` 后撤那一手已有 `now` 那一格。★ 图标按真源 26_ §2.2：⚔️ 行动/攻击（这几格全是「你这一手做了什么」）· 📦 换装/道具。★ 其中 COMBAT_RETREAT_BLOCK/OK · FLEE_OK/BLOCK · INT_BREAK/PUSH **在**真源 17_ 槽位表里⇒ 走 DOC_PENDING 跟账（改值的唯一合法路径）；INT_PLAIN / ITEM_CAP 同批。",
    },
    "COMBAT_RETREAT_OK": {
        "old": "它这会儿没在出招 —— 你退开了，这一场没打。",
        "new": "⚔️【{t} 刻】它这会儿没在出招 —— 你退开了，这一场没打。",
        "why": "P0-1 续（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。这几格经 `logs.append` / `hand.lines` 进**持久战斗日志**（`_note_battle` 原样落档、『战斗日志』读它），实测屏上它们是最后读不出刻数的那一批。★ 写**纯 {t} 不写 {t:.0f}**：内容侧 `T()` 是**字面 replace**（content/cmds_ast.py:53-55），实测 '{t:.0f}' 永远不被替换、会把字面量打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f}。★ 读端同步补 t：`_retreat_decide`/`_flee_decide` 用 `Battle._now` 现读（与 content/mech.py:293、content/battle_acts.py 新增的 `_now` 逐字同形）；`cmds_battle` 后撤那一手已有 `now` 那一格。★ 图标按真源 26_ §2.2：⚔️ 行动/攻击（这几格全是「你这一手做了什么」）· 📦 换装/道具。★ 其中 COMBAT_RETREAT_BLOCK/OK · FLEE_OK/BLOCK · INT_BREAK/PUSH **在**真源 17_ 槽位表里⇒ 走 DOC_PENDING 跟账（改值的唯一合法路径）；INT_PLAIN / ITEM_CAP 同批。",
    },
    "COMBAT_FLEE_OK": {
        "old": "你转身就跑，把 {name} 甩在了后头 —— 这一场没打。",
        "new": "⚔️【{t} 刻】你转身就跑，把 {name} 甩在了后头 —— 这一场没打。",
        "why": "P0-1 续（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。这几格经 `logs.append` / `hand.lines` 进**持久战斗日志**（`_note_battle` 原样落档、『战斗日志』读它），实测屏上它们是最后读不出刻数的那一批。★ 写**纯 {t} 不写 {t:.0f}**：内容侧 `T()` 是**字面 replace**（content/cmds_ast.py:53-55），实测 '{t:.0f}' 永远不被替换、会把字面量打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f}。★ 读端同步补 t：`_retreat_decide`/`_flee_decide` 用 `Battle._now` 现读（与 content/mech.py:293、content/battle_acts.py 新增的 `_now` 逐字同形）；`cmds_battle` 后撤那一手已有 `now` 那一格。★ 图标按真源 26_ §2.2：⚔️ 行动/攻击（这几格全是「你这一手做了什么」）· 📦 换装/道具。★ 其中 COMBAT_RETREAT_BLOCK/OK · FLEE_OK/BLOCK · INT_BREAK/PUSH **在**真源 17_ 槽位表里⇒ 走 DOC_PENDING 跟账（改值的唯一合法路径）；INT_PLAIN / ITEM_CAP 同批。",
    },
    "COMBAT_FLEE_BLOCK": {
        "old": "{name} 先一步拦住了退路 —— 没跑成，这一手白花，这一场照打。",
        "new": "⚔️【{t} 刻】{name} 先一步拦住了退路 —— 没跑成，这一手白花，这一场照打。",
        "why": "P0-1 续（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。这几格经 `logs.append` / `hand.lines` 进**持久战斗日志**（`_note_battle` 原样落档、『战斗日志』读它），实测屏上它们是最后读不出刻数的那一批。★ 写**纯 {t} 不写 {t:.0f}**：内容侧 `T()` 是**字面 replace**（content/cmds_ast.py:53-55），实测 '{t:.0f}' 永远不被替换、会把字面量打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f}。★ 读端同步补 t：`_retreat_decide`/`_flee_decide` 用 `Battle._now` 现读（与 content/mech.py:293、content/battle_acts.py 新增的 `_now` 逐字同形）；`cmds_battle` 后撤那一手已有 `now` 那一格。★ 图标按真源 26_ §2.2：⚔️ 行动/攻击（这几格全是「你这一手做了什么」）· 📦 换装/道具。★ 其中 COMBAT_RETREAT_BLOCK/OK · FLEE_OK/BLOCK · INT_BREAK/PUSH **在**真源 17_ 槽位表里⇒ 走 DOC_PENDING 跟账（改值的唯一合法路径）；INT_PLAIN / ITEM_CAP 同批。",
    },
    "COMBAT_INT_BREAK": {
        "old": "它起手的那一下被你截断 —— 这一手它没打出来。",
        "new": "⚔️【{t} 刻】它起手的那一下被你截断 —— 这一手它没打出来。",
        "why": "P0-1 续（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。这几格经 `logs.append` / `hand.lines` 进**持久战斗日志**（`_note_battle` 原样落档、『战斗日志』读它），实测屏上它们是最后读不出刻数的那一批。★ 写**纯 {t} 不写 {t:.0f}**：内容侧 `T()` 是**字面 replace**（content/cmds_ast.py:53-55），实测 '{t:.0f}' 永远不被替换、会把字面量打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f}。★ 读端同步补 t：`_retreat_decide`/`_flee_decide` 用 `Battle._now` 现读（与 content/mech.py:293、content/battle_acts.py 新增的 `_now` 逐字同形）；`cmds_battle` 后撤那一手已有 `now` 那一格。★ 图标按真源 26_ §2.2：⚔️ 行动/攻击（这几格全是「你这一手做了什么」）· 📦 换装/道具。★ 其中 COMBAT_RETREAT_BLOCK/OK · FLEE_OK/BLOCK · INT_BREAK/PUSH **在**真源 17_ 槽位表里⇒ 走 DOC_PENDING 跟账（改值的唯一合法路径）；INT_PLAIN / ITEM_CAP 同批。",
    },
    "COMBAT_INT_PUSH": {
        "old": "你把它压在后面 —— 它下一次行动的到点时刻被推后 {ticks} 刻。",
        "new": "⚔️【{t} 刻】你把它压在后面 —— 它下一次行动的到点时刻被推后 {ticks} 刻。",
        "why": "P0-1 续（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。这几格经 `logs.append` / `hand.lines` 进**持久战斗日志**（`_note_battle` 原样落档、『战斗日志』读它），实测屏上它们是最后读不出刻数的那一批。★ 写**纯 {t} 不写 {t:.0f}**：内容侧 `T()` 是**字面 replace**（content/cmds_ast.py:53-55），实测 '{t:.0f}' 永远不被替换、会把字面量打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f}。★ 读端同步补 t：`_retreat_decide`/`_flee_decide` 用 `Battle._now` 现读（与 content/mech.py:293、content/battle_acts.py 新增的 `_now` 逐字同形）；`cmds_battle` 后撤那一手已有 `now` 那一格。★ 图标按真源 26_ §2.2：⚔️ 行动/攻击（这几格全是「你这一手做了什么」）· 📦 换装/道具。★ 其中 COMBAT_RETREAT_BLOCK/OK · FLEE_OK/BLOCK · INT_BREAK/PUSH **在**真源 17_ 槽位表里⇒ 走 DOC_PENDING 跟账（改值的唯一合法路径）；INT_PLAIN / ITEM_CAP 同批。",
    },
    "COMBAT_INT_PLAIN": {
        "old": "你盯着它的起手。",
        "new": "⚔️【{t} 刻】你盯着它的起手。",
        "why": "P0-1 续（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。这几格经 `logs.append` / `hand.lines` 进**持久战斗日志**（`_note_battle` 原样落档、『战斗日志』读它），实测屏上它们是最后读不出刻数的那一批。★ 写**纯 {t} 不写 {t:.0f}**：内容侧 `T()` 是**字面 replace**（content/cmds_ast.py:53-55），实测 '{t:.0f}' 永远不被替换、会把字面量打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f}。★ 读端同步补 t：`_retreat_decide`/`_flee_decide` 用 `Battle._now` 现读（与 content/mech.py:293、content/battle_acts.py 新增的 `_now` 逐字同形）；`cmds_battle` 后撤那一手已有 `now` 那一格。★ 图标按真源 26_ §2.2：⚔️ 行动/攻击（这几格全是「你这一手做了什么」）· 📦 换装/道具。★ 其中 COMBAT_RETREAT_BLOCK/OK · FLEE_OK/BLOCK · INT_BREAK/PUSH **在**真源 17_ 槽位表里⇒ 走 DOC_PENDING 跟账（改值的唯一合法路径）；INT_PLAIN / ITEM_CAP 同批。",
    },
    "COMBAT_ITEM_CAP": {
        "old": "「{name}」这一场用过了 —— 一场一次，后面的手只能照打。",
        "new": "📦【{t} 刻】「{name}」这一场用过了 —— 一场一次，后面的手只能照打。",
        "why": "P0-1 续（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。这几格经 `logs.append` / `hand.lines` 进**持久战斗日志**（`_note_battle` 原样落档、『战斗日志』读它），实测屏上它们是最后读不出刻数的那一批。★ 写**纯 {t} 不写 {t:.0f}**：内容侧 `T()` 是**字面 replace**（content/cmds_ast.py:53-55），实测 '{t:.0f}' 永远不被替换、会把字面量打上屏；引擎 cue 那一族走 str.format 才写 {t:.0f}。★ 读端同步补 t：`_retreat_decide`/`_flee_decide` 用 `Battle._now` 现读（与 content/mech.py:293、content/battle_acts.py 新增的 `_now` 逐字同形）；`cmds_battle` 后撤那一手已有 `now` 那一格。★ 图标按真源 26_ §2.2：⚔️ 行动/攻击（这几格全是「你这一手做了什么」）· 📦 换装/道具。★ 其中 COMBAT_RETREAT_BLOCK/OK · FLEE_OK/BLOCK · INT_BREAK/PUSH **在**真源 17_ 槽位表里⇒ 走 DOC_PENDING 跟账（改值的唯一合法路径）；INT_PLAIN / ITEM_CAP 同批。",
    },

    # ★ P2-24（2026-09-29 · 文案修复车道 aep2）：屏抬头补行首语义锚。
    #   真源 17_ 槽位表里的那四格 · 因此属于本生成器拥有 → 改值走 DOC_PENDING。
    "SYS_SHOP_HEAD": {
        "old": "【药铺】{name}",
        "new": "📍 【药铺】{name}",
        "why": "P2-24（2026-09-29 · 文案修复车道 aep2）：屏抬头类的**缺口**（整屏全裸 = 自洽，不是不一致）。"
               "图标取真源 26_ §2.2「📍 位置 / 地图 / 去哪 —— 场景头、位置提示」"
               "—— **不用 💰**（第一版选它，已改）：该格的参数是 `SH.station_name()`"
               "（府名，屏上实测写「苦叶摊」），且该手在 "
               "`content/cmds_places.py::herbalist`" "—— 与地图 / 所在场所同屏，是**位置头**不是价格头；"
               "本包 P2-23 已固化 SYS_PLACE_HEAD / SYS_MAP_HEAD = 📍。"
               "接法 SPACE 形（emoji + 空格 + 【】）：本包已带锚的 _HEAD **15/15 全是这个接法**。"
               "措辞一个字未动，params 面未变（仍只有 name）⇒ 读端零改动。",
    },
    # ★ 2026-09-30：SYS_HELP_HEAD 的条目随「帮助面板改造」删除（该键已从真源/域下线）。
    "SYS_RANKING_HEAD": {
        "old": "【本群榜】按等级与经验排 —— 只有这个群里的人。",
        "new": "📊 【本群榜】按等级与经验排 —— 只有这个群里的人。",
        "why": "P2-24（同批 · 文案修复车道 aep2）：图标取真源 26_ §2.2「📊 面板 / 状态 —— 属性、背包、面板」"
               "的逐字对应：榜单就是面板读数（同包 SYS_STATUS_HEAD / SYS_ATTR_HEAD 均为 📊，现成事实）。"
               "接法 SPACE 形，措辞零改动，params 面未变。",
    },
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

    "COMBAT_FOCUS_MISS": {
        "old": "「{name}」认不出是哪一只 —— 『集火 <目标>』写一只认得出的怪。",
        "new": "「{name}」这一带没有 —— 眼前只看得见 {here}。",
        "why": "P0-2c（2026-09-29 · 文案修复车道 aep0 · 真机试玩取证）：真机敲『集火 不存在的东西』实测上屏"
               "「『不存在的东西』认不出是哪一只 —— 『集火 <目标>』写一只认得出的怪。」—— 「认不出」「目标」是**机器词**"
               "（真源 23_ §一 语气六要素：说人话，不把实现层的判断词扔给玩家；memory 同款口径「玩家可见文本禁机器键/黑话」）。"
               "★ 改法只换**措辞**、不动语义：仍然点名玩家写下的 {name}、仍然说「这只不在眼前」、仍然把下一步说清。"
               "  {here} 是**眼下真的站着的那几只**（读端 `content/cmds_battle.py` 的 `_foe_names(st)` 现算，"
               "  与 `_match_foe` 同一把尺子：`hp > 0` 的敌方 actor 的显示名），"
               "  于是「你写的名字对不上」变成「你写的名字不在这一群」——玩家自己看屏就知道该写哪一只。"
               "★ **参数面是新增的**（原 params 只有 name）：读端同批补 `here` 传参；"
               "  `probe_cmds.py:2315` 与 `probe_party.py:751` 那两处断言走 `_r(...)` 现读槽位 ⇒ 跟着自动跟随，不改判据。"
               "★ **两个读端的 `here` 源不同、措辞同形**：在场那一档取场上还站着的几只（`_foe_names(st)`，"
               "  与 `_match_foe` 同一把尺子 `hp > 0`）；没在打的那一档取**这一带会遇到的那些**"
               "  （`_foe_names_in(ms)`，与 `hit` 分支同一个 `ms` 循环）—— 两处都不另抄一份「有哪些怪」。"
               "★ **第二处曾一度并进 `COMBAT_NEED_FOE`、已回退**：F6（QA P3，`probe_cmds` 五那条判据）"
               "  钉的是「点了名却认不出」必须与「空着没点名」分开说（改前两句同形、玩家以为点对了）；"
               "  并进去那一刻它就与「空着」同形了 ⇒ 判据在保护一件真事，不动它。"
               "★ 顺带解掉一条 `probe_copy ②`：第一版读端写过 `or 「一只」` 那个兜底，那个量词内联在代码里"
               "  就是**内联中文文案**（已收口文件要求 0 条）⇒ 读端一个字不许自造，代码只许传槽位里有的值。",
    },
    "COMBAT_FOCUS_NAMED": {
        "old": "「{name}」认得出来 —— 但集火得有人跟你一起打。",
        "new": "「{name}」找得到 —— 但集火得有人跟你一起打。",
        "why": "P0-2c（同上一条 · 真机试玩取证）：「认得出来」与上一条「认不出」是同一组机器词（实现层的「认得/认不出」"
               "判定词），与屏上其余集火三句的腔调不齐——`COMBAT_FOCUS_LOCK` 说「锁定了」、"
               "`COMBAT_FOCUS_PARTY` 说「队伍里现在没人能统一出手」。★ 语义一字未动（认得出名字 / 但要有人），"
               "只把判定词换成玩家口吻的「找得到」。params 面未变（仍只有 name）⇒ 读端零改动。",
    },

    "SYS_LOOK_HINT": {
        "old": "「『触摸』可以上手摸，『聆听』可以听，『地图』看全貌。」",
        "new": "角落里那几件东西往过。你还是想先碰一下。",
        "why": "copy-p5（去 AI 感 · 提示行）：旧值是**一屏三个指令名 + 每个跟一句功能解释**（「『触摸』可以上手摸」…」解析自己）。改成场景 + 留钩子。新门禁：probe_hint_voice ①②。",
    },
    "SYS_TOWN_ENTER_HINT": {
        "old": "「『观察』看细节，『往东』『往西』『往北』出门，『公会』在挂板墙。」",
        "new": "风车在头顶上转。街上没人。",
        "why": "copy-p5：旧值一屏**五个指令名**（观察/往东/往西/往北/公会）。每个地方的去处由 `SYS_TOWN_ENTER_GATE`（下一行）负责，重列两次是冗余；改成进镇那一眼的感觉，封口行**一个字未动**。",
    },
    "SYS_HINT_TOWN": {
        "old": "先『观察』看看镇口那块石头，再去『公会』接一件小活。",
        "new": "镇口那块石头上刻着字。先读一读。",
        "why": "copy-p5：旧值是**指令清单**（观察 + 公会）。改成只引一件物实（镇口那块石头）——`probe_onsite`/`probe_qloop` 钉的是**石头本身**的正文，不是这个槽位，两个探针一个字未动。",
    },
    "SYS_HINT_WILD": {
        "old": "往北是骨田和旧哨塔，往东是白桦林，往西是浅滩渡口。『返回』回上一个地方。",
        "new": "荒野里没人去过。往东那边的白桦林有点不对。",
        "why": "copy-p5：旧值是**地图读照**（三个方向 + 返回）。改成现场的一句 + 一个钩子（白槐林「有点不对」 = 提醒一下的地方，不是答案）。",
    },
    "SYS_TOWER_HINT": {
        "old": "「『去 <房间>』往里走 · 『副本地图』看这一层 · 『调查』查这一间 · 『撤退』出塔」",
        "new": "塔里黑。每一间都有自己的东西，往里走就行。",
        "why": "copy-p5：旧值是**四个指令名串成一行**（逐个用 · 分隔）。改成进塔那一眼的感觉；口令依旧能打（地图里 12 间、cmds_tower 的导航口一个字未动）。",
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
    "SYS_PARTY_HEAD": {
        "old": "【队伍】{n}/{max} 人 · 队长：{cap}",
        "new": "👥 【队伍】{n}/{max} 人 · 队长：{cap}",
        "why": "P2-19（2026-09-29 · 文案车道 aep2 · 真机试玩取证）：队伍屏 29 个槽位零图标（审计口径），真机 e2e 实测拿到的屏形是「【队伍】{n}/{max} 人 · 队长：cap」光裸起头。图标按真源 26_ §2.2 emoji 语义分组现字选：👥 队伍/阵友（不自创）。本屏只有这一条抬头（heads_of 现算：SYS_PARTY 仅 SYS_PARTY_HEAD）⇒ 不触发 probe_emoji_order §④「同屏抬头锚点齐」，不得拿它适用到其他屏。【为什么不加在后面的 ROW 里】队员行 SYS_PARTY_ROW 已有行首锚「· 」，再加一层 = 两重行首（P2-18 已经把这个口径写过）。本槽位**在**真源 17_ 槽位表里 ⇒ 改值走 DOC_PENDING 跟账（改值的唯一合法路径）。",
    },
    "COMBAT_MECH_SIDESTEP": {
        "old": "你侧过半个身子 —— {turns} 刻里闪避涨 {pct}%。",
        "new": "✨【{t} 刻】你侧过半个身子 —— {turns} 刻里闪避涨 {pct}%。",
        "why": "P0-1 续批三（2026-09-29 · 文案车道 aep0 · **补上一轮的漏网一族**）：真源 26_ §三 优化 1 逐字「所有战斗日志行统一以【N 刻】开头」。★ **上一轮为什么漏**（探针与 AST 两处盲区叠加）：① 枚举只按 `logs.append` / `hand.lines` 找入口，而这 8 格**经 `_grant()` / `_ward()` 两个 helper 间接进 logs**⇒ AST 看不见；② `probe_texts` 那两条判据按 content/rules/battle_text.json（引擎 62 个 cue）取件，而这 8 格**零 cue 映射**（grep battle_text.json = 0 命中）⇒ 判据也取不到。两处盲区叠在一起，于是这一族在两轮里一直是「绿但没接」。★ 本轮判据**只加强不削弱**：给 probe_texts 加一条独立判据「经 `_grant`/`_ward` 进持久战斗日志的那一族必须带【N 刻】」，取件从**那两个 helper 本体**现算（不再靠 cue 表）。★ 读端（content/mech.py）：`_grant` / `_ward` 各补 `t=int(round(_now(battle)))` —— 一处改覆盖 8 格，**别在调用点逐个补**（那正是上一轮的漏法）。★ 写**纯 {t} 不写 {t:.0f}**：内容侧 `T()` 是字面 replace（content/cmds_ast.py:53-55），'{t:.0f}' 永远不被替换、会把字面量打上屏（真机 e2e 实测过）；引擎 cue 那一族走 str.format 才写 {t:.0f}—— 两侧形态不同是有原因的，别合并。★ 图标按真源 26_ §2.2 语义分组：🛡️ 防御/减伤/招架（STANDFAST/AEGIS/REARGUARD/RIPOSTE/FROSTVEIL 五格同族）· 🩸 付代价（血债割自己一道口子）· ✨ 增益（守夜把手上的暖挪过来 / 侧身闪避）。★ 这 8 格**不在**真源 17_ 槽位表里（grep '| COMBAT_MECH_… |' = 0 命中 ×8）⇒ 不是生成器拥有的行，登记在册是为了两态互锁（不登记就红在 probe_copy ⑤ 与 probe_generators ②③）。",
    },


    "SYS_EV_CARAVAN": {
        "old": '北口还空着，跟着车来的那两个人没在镇上。',
        "new": '北口还空着，\n跟着车来的那两个人没在镇上。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "SYS_EV_MARKET": {
        "old": '挂板墙那边比平时挤，板上多了一张新贴的纸。',
        "new": '挂板墙那边比平时挤，\n板上多了一张新贴的纸。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "SYS_EV_FIRST_SNOW": {
        "old": '天阴着，看那样子，头一场雪说下就下。',
        "new": '天阴着，\n看那样子，\n头一场雪说下就下。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_MAIN01_STORY": {
        "old": '镇口的石头你天天从它跟前过。今天你停下来了。',
        "new": '镇口的石头你天天从它跟前过。\n今天你停下来了。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_MAIN02_STORY": {
        "old": '白烛堂的侧屋你还没敲过。住在里头的人，说话只说一半。',
        "new": '白烛堂的侧屋你还没敲过。\n住在里头的人，\n说话只说一半。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_MAIN03_STORY": {
        "old": '玛莎一次给了你三张单子，没多解释 —— 北边、东边、西边，各一张。',
        "new": '玛莎一次给了你三张单子，\n没多解释 —— 北边、\n东边、\n西边，\n各一张。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_MAIN04_STORY": {
        "old": '北边那片地叫骨田。碑排成一排立在土里，大半埋着。',
        "new": '北边那片地叫骨田。\n碑排成一排立在土里，\n大半埋着。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_MAIN05_STORY": {
        "old": '拾荒营地你还没走到。风一来，那几块篷布就往一边倒。',
        "new": '拾荒营地你还没走到。\n风一来，\n那几块篷布就往一边倒。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_MAIN06_STORY": {
        "old": '北边那座塔的轮廓，你在镇上就看得见 —— 今天你走到旧哨塔下，门就在跟前。',
        "new": '北边那座塔的轮廓，\n你在镇上就看得见 —— 今天你走\n到旧哨塔下，\n门就在跟前。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_MAIN07_STORY": {
        "old": '旧哨塔里几间房，一间一间往里走。水房在最里头。',
        "new": '旧哨塔里几间房，\n一间一间往里走。\n水房在最里头。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_MAIN08_STORY": {
        "old": '塔里再往上还有一层。守在那儿的东西，不是人。',
        "new": '塔里再往上还有一层。\n守在那儿的东西，\n不是人。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_MAIN09_STORY": {
        "old": '格雷先开的口 —— 他从前不主动跟人说话。',
        "new": '格雷先开的口 —— 他从前不主动\n跟人说话。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_MAIN10_STORY": {
        "old": '北墙根那个人一直坐在墙边数什么。今天他抬了头。',
        "new": '北墙根那个人一直坐在墙边数什\n么。\n今天他抬了头。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_MAIN11_STORY": {
        "old": '白桦林里的刻名，你已经记下来了。塔里那一排，还在等着比。',
        "new": '白桦林里的刻名，\n你已经记下来了。\n塔里那一排，\n还在等着比。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_MAIN12_STORY": {
        "old": '塔顶只剩一层没走。上面那个东西，一直在那儿等着。',
        "new": '塔顶只剩一层没走。\n上面那个东西，\n一直在那儿等着。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "SCENE_OLD_WATCHTOWER": {
        "old": '进了门，灰只在门槛那一线断掉 —— 里头干净得不像没人来。门厅空着，正对着一道楼梯贴墙往上旋，看不见顶。塔顶没有墙，风从北边来，顺着楼梯下来，绕你一圈又上去。水声也在上头，一阵一阵的，不像漏雨。',
        "new": '进了门，\n灰只在门槛那一线断掉\n ——\n 里头干净得不像没人来。\n门厅空着，\n正对着一道楼梯贴墙往上旋，\n看不见顶。\n塔顶没有墙，\n风从北边来，\n顺着楼梯下来，\n绕你一圈又上去。\n水声也在上头，\n一阵一阵的，不像漏雨。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "READ_TOWER_GATE_MARKS": {
        "old": '三道刻痕，刻在门闩上。三道都新 —— 不像旧痕。闩是从里侧扣上的：刻它的人，当时站在里面。',
        "new": '三道刻痕，\n刻在门闩上。\n三道都新\n ——\n 不像旧痕。\n闩是从里侧扣上的：\n刻它的人，当时站在里面。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "READ_TOWER_ARMORY_NAMES": {
        "old": '架子上每一格都有一个名字。名字不是一个人刻的 —— 刻法一路在变。刻给谁看，没说。',
        "new": '架子上每一格都有一个名字。\n名字不是一个人刻的\n ——\n 刻法一路在变。\n刻给谁看，没说。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "READ_TOWER_TOP_WORDS": {
        "old": '石头地上刻着一行字 —— 「它在执行一条没人撤销的命令」。',
        "new": '石头地上刻着一行字\n ——\n 「它在执行一条没人撤销的命\n令」。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "READ_TOWER_NORTH_RIFT": {
        "old": '往北看，天边有一道裂口。想起那半页纸上写的：北边有一条会走的裂缝。',
        "new": '往北看，\n天边有一道裂口。\n想起那半页纸上写的：\n北边有一条会走的裂缝。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_BOUNTY101_STORY": {
        "old": '单子是从挂板墙上取下来的 —— 一只普通怪，打掉，回来交。',
        "new": '单子是从挂板墙上取下来的 —— \n一只普通怪，\n打掉，\n回来交。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_BOUNTY102_STORY": {
        "old": '这一张写的是精英怪 —— 光靠硬碰，交不回来。',
        "new": '这一张写的是精英怪 —— 光靠硬\n碰，\n交不回来。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_BOUNTY103_STORY": {
        "old": '板子最里头那张写的是头目 —— 那种单子，接的人不多。',
        "new": '板子最里头那张写的是头目 —— \n那种单子，\n接的人不多。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_SIDE13_STORY": {
        "old": '柯尔把话说明白：一件装备，往上强化 —— 学徒的活从这儿开始。',
        "new": '柯尔把话说明白：一件装备，\n往上强化 —— 学徒的活从这儿开\n始。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_SIDE14_STORY": {
        "old": '柯尔不缺工钱。他要一块旧铁 —— 他手上那把锤子，还缺这一块。',
        "new": '柯尔不缺工钱。\n他要一块旧铁 —— 他手上那把锤\n子，\n还缺这一块。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_SIDE15_STORY": {
        "old": '娜娜要三种药草，各三份 —— 少一份都算没采齐。',
        "new": '娜娜要三种药草，\n各三份 —— 少一份都算没采齐。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_SIDE16_STORY": {
        "old": '娜娜提过的那种菌，只有雨天才有 —— 天不出雨，摊上就缺这一样。',
        "new": '娜娜提过的那种菌，\n只有雨天才有 —— 天不出雨，\n摊上就缺这一样。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_SIDE17_STORY": {
        "old": '贝拉要三道菜，端到她面前尝 —— 客栈的招牌，得先过她这一关。',
        "new": '贝拉要三道菜，\n端到她面前尝 —— 客栈的招牌，\n得先过她这一关。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_SIDE18_STORY": {
        "old": '贝拉要看你能不能拿出稀有食材 —— 做一次，就一次。',
        "new": '贝拉要看你能不能拿出稀有食材\n —— 做一次，\n就一次。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_SIDE19_STORY": {
        "old": '白烛堂的灯该添油了。艾德把油壶递过来，让你跟着跑一趟。',
        "new": '白烛堂的灯该添油了。\n艾德把油壶递过来，\n让你跟着跑一趟。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_SIDE20_STORY": {
        "old": '艾德把饭交给你：送到北墙根，趁热。',
        "new": '艾德把饭交给你：送到北墙根，\n趁热。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_SIDE21_STORY": {
        "old": '老陶要讲那条旧路 —— 他讲一遍不算完，得听够三回。',
        "new": '老陶要讲那条旧路 —— 他讲一遍\n不算完，\n得听够三回。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_SIDE22_STORY": {
        "old": '有封信要送出去，得有人陪着走一趟 —— 老陶把这活儿挂了出来。',
        "new": '有封信要送出去，\n得有人陪着走一趟 —— 老陶把这\n活儿挂了出来。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_SIDE23_STORY": {
        "old": '皮特天天有酒喝，钱却不像是挣来的 —— 这笔账得替他查。',
        "new": '皮特天天有酒喝，\n钱却不像是挣来的 —— 这笔账得\n替他查。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_SIDE24_STORY": {
        "old": '皮特醉话里有个名字，他从来不说完 —— 那个名字得你自己找。',
        "new": '皮特醉话里有个名字，\n他从来不说完 —— 那个名字得你\n自己找。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_SIDE25_STORY": {
        "old": '小满把那块石头塞给你 —— 它该回到缺着它的那块碑上去。',
        "new": '小满把那块石头塞给你 —— 它该\n回到缺着它的那块碑上去。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_SIDE26_STORY": {
        "old": '小满要去看塔 —— 你带他到塔下就行，他不进去。',
        "new": '小满要去看塔 —— 你带他到塔下\n就行，\n他不进去。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_SIDE27_STORY": {
        "old": '格雷腰间那把断剑，断口一直空着 —— 他要一块配得上的旧铁。',
        "new": '格雷腰间那把断剑，\n断口一直空着 —— 他要一块配得\n上的旧铁。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_SIDE28_STORY": {
        "old": '格雷要讲断剑团的事 —— 三段，每段他自己都缺着一块。',
        "new": '格雷要讲断剑团的事 —— 三段，\n每段他自己都缺着一块。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_SIDE29_STORY": {
        "old": '瑟兰在找一座塔，她自己不问人 —— 三个人，得你去问。',
        "new": '瑟兰在找一座塔，\n她自己不问人 —— 三个人，\n得你去问。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_SIDE30_STORY": {
        "old": '杜林先问你手上有什么料 —— 他要按自己的口味吃一道菜。',
        "new": '杜林先问你手上有什么料 —— 他\n要按自己的口味吃一道菜。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_TRADE31_STORY": {
        "old": '娜娜嫌你采得太浅 —— 三条带，各走到底，各采一次。',
        "new": '娜娜嫌你采得太浅 —— 三条带，\n各走到底，\n各采一次。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_TRADE32_STORY": {
        "old": '娜娜要一块长在石头缝里的矿 —— 旧哨塔那一片才有。',
        "new": '娜娜要一块长在石头缝里的矿 —\n— 旧哨塔那一片才有。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_TRADE33_STORY": {
        "old": '老陶的鱼篓空着 —— 他要三种常见的鱼。',
        "new": '老陶的鱼篓空着 —— 他要三种常\n见的鱼。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_TRADE34_STORY": {
        "old": '水里有条鱼只在夜里上钩 —— 老陶把这一条单拎出来给你。',
        "new": '水里有条鱼只在夜里上钩 —— 老\n陶把这一条单拎出来给你。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_TRADE35_STORY": {
        "old": '贝拉要一条鱼，指名的那种 —— 换的是一张菜谱。',
        "new": '贝拉要一条鱼，\n指名的那种 —— 换的是一张菜谱。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_TRADE36_STORY": {
        "old": '浅滩底下钓上来过不是鱼的东西 —— 贝拉要你再试一次。',
        "new": '浅滩底下钓上来过不是鱼的东西\n —— 贝拉要你再试一次。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_TRADE37_STORY": {
        "old": '那件有故事的旧装备还断着 —— 柯尔肯修，修完他会说这东西的来处。',
        "new": '那件有故事的旧装备还断着 —— \n柯尔肯修，\n修完他会说这东西的来处。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "QUEST_TRADE38_STORY": {
        "old": '柯尔开口要一块旧铁：骨田底下挖出来的那种。',
        "new": '柯尔开口要一块旧铁：骨田底下\n挖出来的那种。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "SYS_ATTR_NOTE": {
        "old": '（这一页是现算的：职业基础 + 等级成长 + 加点 + 装备 + 增益。）',
        "new": '（这一页是现算的：\n职业基础\n +\n 等级成长\n + 加点 + 装备 + 增益。）',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "SYS_HINT_JOB_READY": {
        "old": '（这一条办完了 —— 打『交 {order}』。）',
        "new": '（这一条办完了\n —— 打『交 {order}』。）',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "SYS_READ_NOSUCH": {
        "old": '这儿没有叫「{name}」的东西能读。',
        "new": '这儿没有叫「{name}」\n的东西能读。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "SCENE_WT_GATE_E": {
        "old": '东口开在镇子东边，两根木桩立在路两边，桩上缠过绳，绳烂得只剩几圈挂着。\n路从这儿出去，压出两道车辙，一直往白桦林那边去。车辙是干的。\n回头是镇子 —— 风车在远处转，转到这儿只剩一点吱呀声。\n这儿没有摊子，也没有人。就一条路，朝东。',
        "new": '东口开在镇子东边，\n两根木桩立在路两边，\n桩上缠过绳，\n绳烂得只剩几圈挂着。\n路从这儿出去，\n压出两道车辙，\n一直往白桦林那边去。\n车辙是干的。\n回头是镇子\n ——\n 风车在远处转，转到这儿只剩\n一点吱呀声。\n这儿没有摊子，\n也没有人。就一条路，朝东。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "SCENE_WT_GATE_W": {
        "old": '西口开在镇子最低的那一头，路往下走，走两步就有潮气。\n口子是敞的，门板只剩一边，另一半靠在墙上，钉子锈在木头里。\n路从这儿出去，往浅滩渡口那边 —— 晴天看得见水，阴天只剩一层白。\n这儿没有摊子，也没有人。就一条路，朝西。',
        "new": '西口开在镇子最低的那一头，\n路往下走，走两步就有潮气。\n口子是敞的，\n门板只剩一边，\n另一半靠在墙上，\n钉子锈在木头里。\n路从这儿出去，\n往浅滩渡口那边\n ——\n 晴天看得见水，\n阴天只剩一层白。\n这儿没有摊子，\n也没有人。就一条路，朝西。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "SCENE_WT_WALL_EMPTY": {
        "old": '北墙根离镇上不远，但走过去像走过了两个地方。\n墙是从地里长出来的那种矮墙，到这儿就断了。断口那面对着北边，什么也没有 —— 麦田到头，荒开始。\n墙根下那排东西还摆着，一个挨一个，间距几乎一样。\n东西前头空着 —— 这个点他不在。天黑了他才来坐。',
        "new": '北墙根离镇上不远，\n但走过去像走过了两个地方。\n墙是从地里长出来的那种矮墙，\n到这儿就断了。\n断口那面对着北边，\n什么也没有\n —— 麦田到头，荒开始。\n墙根下那排东西还摆着，\n一个挨一个，间距几乎一样。\n东西前头空着\n ——\n 这个点他不在。\n天黑了他才来坐。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "SCENE_WT_SHED_EMPTY": {
        "old": '歇脚棚的顶是茅草压的，一半塌了，另一半还撑着。\n棚里堆着草，能坐人。地上有几个坑，是常年踩出来的。\n草堆上那个坑最深 —— 平时就他坐那儿。今天空着。\n这个点他不在。他要是在，你说什么他都不太接。',
        "new": '歇脚棚的顶是茅草压的，\n一半塌了，另一半还撑着。\n棚里堆着草，\n能坐人。\n地上有几个坑，\n是常年踩出来的。\n草堆上那个坑最深\n ——\n 平时就他坐那儿。今天空着。\n这个点他不在。\n他要是在，\n你说什么他都不太接。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "READ_HIDDEN_CAMP": {
        "old": '扒开一半 —— 底下的东西裹着布，布外还缠了一道绳，绳子还是新的。有人重新捆过，捆完就走了。',
        "new": '扒开一半\n ——\n 底下的东西裹着布，\n布外还缠了一道绳，\n绳子还是新的。有人重新捆过，\n捆完就走了。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "READ_HIDDEN_BIRCH": {
        "old": '记号刻在背阴的那一面 —— 从路上看不见，得绕到树背后。刻痕比树上别处都深，最后一道拖出去，指着林子更里面。',
        "new": '记号刻在背阴的那一面\n ——\n 从路上看不见，\n得绕到树背后。\n刻痕比树上别处都深，\n最后一道拖出去，\n指着林子更里面。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "READ_HIDDEN_SHOAL": {
        "old": '石缝横在湿泥上，缝里的东西露出一点颜色。缝比看着深，底下那截还泡在水里。',
        "new": '石缝横在湿泥上，\n缝里的东西露出一点颜色。\n缝比看着深，\n底下那截还泡在水里。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "SYS_SHOP_HERB_NOTE": {
        "old": '摊上只卖药 —— 苦叶这些是自己上山采的，柜上没有。',
        "new": '摊上只卖药\n ——\n 苦叶这些是自己上山采的，\n柜上没有。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_WT_MILL": {
        "old": '木头一圈一圈地响。扫帚扫过地面的声音，很轻。',
        "new": '木头一圈一圈地响。\n扫帚扫过地面的声音，\n很轻。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_WT_INN": {
        "old": '门轴抬一下的响。里面有人说话，压着嗓子。',
        "new": '门轴抬一下的响。\n里面有人说话，\n压着嗓子。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_WT_FORGE": {
        "old": '炉火烧得很细。铁翻过来，磕在砧子上。',
        "new": '炉火烧得很细。\n铁翻过来，\n磕在砧子上。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_WT_BOARD": {
        "old": '纸边被风掀起来，一下一下打着墙。',
        "new": '纸边被风掀起来，\n一下一下打着墙。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_WT_HERBS": {
        "old": '草叶被翻过来，又翻过去。小罐子里有一点动静。',
        "new": '草叶被翻过来，\n又翻过去。\n小罐子里有一点动静。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_WT_CHAPEL": {
        "old": '堂里很静。灯芯偶尔响一声，木屑落到石头上。',
        "new": '堂里很静。\n灯芯偶尔响一声，\n木屑落到石头上。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_WT_WALL": {
        "old": '风从荒那头过来，没有挡的。墙根下有人挪了一下身子。',
        "new": '风从荒那头过来，\n没有挡的。\n墙根下有人挪了一下身子。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_WT_SHED": {
        "old": '棚里有人在说话 —— 说给自己听。手里那根东西一下一下戳着地。',
        "new": '棚里有人在说话 —— 说给自己听。\n手里那根东西一下一下戳着地。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_WT_GATE_N": {
        "old": '风从麦田那头来。风车的声音在背后，很远。',
        "new": '风从麦田那头来。\n风车的声音在背后，\n很远。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_WT_GATE_E": {
        "old": '镇上的人声在身后。往东，声音一层层薄下去。',
        "new": '镇上的人声在身后。\n往东，\n声音一层层薄下去。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_WT_GATE_W": {
        "old": '很远的地方有水声，若有若无。身后的镇子还热闹着。',
        "new": '很远的地方有水声，\n若有若无。\n身后的镇子还热闹着。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_BN_BONE": {
        "old": '风过麦茬，沙沙的。土里像有什么轻轻碰了一下。',
        "new": '风过麦茬，\n沙沙的。\n土里像有什么轻轻碰了一下。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_BN_CAMP": {
        "old": '篷布被风掀起来，拍两下又落下。火堆里还有一点响。',
        "new": '篷布被风掀起来，\n拍两下又落下。\n火堆里还有一点响。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_BN_TOWER": {
        "old": '风从塔顶那个缺口进去，又从里面出来。铁门后面没有别的声音。',
        "new": '风从塔顶那个缺口进去，\n又从里面出来。\n铁门后面没有别的声音。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_BE_BIRCH": {
        "old": '鸟叫得很密，看不见鸟。脚底下是踩碎的叶子。',
        "new": '鸟叫得很密，\n看不见鸟。\n脚底下是踩碎的叶子。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_BE_DOGS": {
        "old": '草里有什么在低低地哼。骨头被踩碎的声音，很近。',
        "new": '草里有什么在低低地哼。\n骨头被踩碎的声音，\n很近。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_BE_SHED": {
        "old": '棚顶的木条在响。粘成一块的纸被风掀不起来。',
        "new": '棚顶的木条在响。\n粘成一块的纸被风掀不起来。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_BW_SHOAL": {
        "old": '水一下一下地响，很平。石缝里有东西被水推着撞。',
        "new": '水一下一下地响，\n很平。\n石缝里有东西被水推着撞。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_BW_FERRY": {
        "old": '木板在脚底下响。水从断桩那儿过去，分开又合上。',
        "new": '木板在脚底下响。\n水从断桩那儿过去，\n分开又合上。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_BW_OLD_FERRY": {
        "old": '一点动静都没有 —— 风不往这边来。只有水拍石阶，很闷。',
        "new": '一点动静都没有 —— 风不往这边\n来。\n只有水拍石阶，\n很闷。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_TOWER_GATE": {
        "old": '门缝里有风出来，很细。里面没有别的声音。',
        "new": '门缝里有风出来，\n很细。\n里面没有别的声音。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_TOWER_HALL": {
        "old": '高处有风，顺着楼梯下来。地上那两具东西没出声。',
        "new": '高处有风，\n顺着楼梯下来。\n地上那两具东西没出声。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_TOWER_ARMORY": {
        "old": '格子空着，不响。这间安静得能听见自己的呼吸。',
        "new": '格子空着，\n不响。\n这间安静得能听见自己的呼吸。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_TOWER_STAIR1": {
        "old": '上面有人在啃东西。楼梯口堵着，过不去。',
        "new": '上面有人在啃东西。\n楼梯口堵着，\n过不去。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_TOWER_OUTPOST_OUT": {
        "old": '风在墙外侧打转。脚底下是湿土，踩一下响一下。',
        "new": '风在墙外侧打转。\n脚底下是湿土，\n踩一下响一下。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_TOWER_OUTPOST_IN": {
        "old": '甲片之间有一点响 —— 你不动，它就不动。',
        "new": '甲片之间有一点响 —— 你不动，\n它就不动。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_TOWER_WATER_ROOM": {
        "old": '水一动就响。那页纸在水面上慢慢转。',
        "new": '水一动就响。\n那页纸在水面上慢慢转。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_TOWER_STORAGE": {
        "old": '木料被风吹得互相磨。墙角的绳子轻轻响。',
        "new": '木料被风吹得互相磨。\n墙角的绳子轻轻响。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_TOWER_EMPTY_ROOM": {
        "old": '窗关得很严，一点风都没有。这间比别处安静。',
        "new": '窗关得很严，\n一点风都没有。\n这间比别处安静。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_TOWER_HORN_ROOM": {
        "old": '风到这儿就断了。石台那边很轻的一声，像铜锈掉了一块。',
        "new": '风到这儿就断了。\n石台那边很轻的一声，\n像铜锈掉了一块。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_TOWER_STAIR2": {
        "old": '上面有光，也有脚步声 —— 不停，也不近。',
        "new": '上面有光，\n也有脚步声 —— 不停，\n也不近。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WORLD_LISHEN_TOWER_TOP": {
        "old": '风从缺口进来，从那边出去。那个东西一动不动，甲没响。',
        "new": '风从缺口进来，\n从那边出去。\n那个东西一动不动，\n甲没响。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "WEATHER_SUNNY_DESC__HR_NIGHT": {
        "old": '（夜里没有云。星星落在石头上，白得发亮。）',
        "new": '（夜里没有云。\n星星落在石头上，\n白得发亮。）',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "NPC_WHEN_BELLA": {
        "old": '天不亮她去买菜，白天到夜里都在客栈。',
        "new": '天不亮她去买菜，\n白天到夜里都在客栈。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "NPC_WHEN_COLE": {
        "old": '他住在作坊里 —— 什么时候来都找得到。',
        "new": '他住在作坊里 —— 什么时候来都\n找得到。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "NPC_WHEN_DERRICK": {
        "old": '他守着风车 —— 什么时候来都找得到。',
        "new": '他守着风车 —— 什么时候来都找\n得到。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "NPC_WHEN_DURIN": {
        "old": '他跟着商队，一年来两趟 —— 车到了才在。',
        "new": '他跟着商队，\n一年来两趟 —— 车到了才在。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "NPC_WHEN_GREY": {
        "old": '商队到了他才来，就坐客栈那个墙角。',
        "new": '商队到了他才来，\n就坐客栈那个墙角。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "NPC_WHEN_LAOTAO": {
        "old": '他白天在棚里。天黑了就睡下了。',
        "new": '他白天在棚里。\n天黑了就睡下了。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "NPC_WHEN_LIAN": {
        "old": '她守着门槛那块地方 —— 什么时候都在。',
        "new": '她守着门槛那块地方 —— 什么时\n候都在。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "NPC_WHEN_MASHA": {
        "old": '白天她在板子后面。天黑了她就回去了。',
        "new": '白天她在板子后面。\n天黑了她就回去了。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "NPC_WHEN_NANA": {
        "old": '她总在摊上 —— 天亮前上山，回来就摆摊。',
        "new": '她总在摊上 —— 天亮前上山，\n回来就摆摊。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "NPC_WHEN_PETE": {
        "old": '他白天在板子那边，入夜才坐回这个角。',
        "new": '他白天在板子那边，\n入夜才坐回这个角。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "NPC_WHEN_SERAN": {
        "old": '她跟着商队走 —— 商队到了，她才在这儿。',
        "new": '她跟着商队走 —— 商队到了，\n她才在这儿。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "NPC_WHEN_XIAOMAN": {
        "old": '天黑了小孩就回家。白天他在这儿看人。',
        "new": '天黑了小孩就回家。\n白天他在这儿看人。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "READ_TOWER_STELE_NAMES__POI_NAMED_BIRCH": {
        "old": '名字一排排往下刻。有三个，你在白桦林那棵树皮上见过 —— 重了。',
        "new": '名字一排排往下刻。\n有三个，\n你在白桦林那棵树皮上见过\n —— 重了。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    "SCENE_WT_CHAPEL__FULL": {
        "old": '白烛堂是镇上唯一用石头砌得齐整的房子。\n堂里暗，只有一盏灯点着，搁在窗台上。窗台上没有灰 —— 这里每天都擦。\n艾德在修椅子，一把很旧的椅子。他修得很慢，但不返工。\n你身上没伤 —— 他看了一眼，就低头接着修那把椅子。',
        "new": '白烛堂是镇上唯一用石头砌得齐\n整的房子。\n堂里暗，\n只有一盏灯点着，\n搁在窗台上。\n窗台上没有灰\n —— 这里每天都擦。\n艾德在修椅子，\n一把很旧的椅子。\n他修得很慢，但不返工。\n你身上没伤\n ——\n 他看了一眼，\n就低头接着修那把椅子。',
        "why": 'P4-3（排版车道 copy-p4 · 折行跟账）：P4-1/P4-1b 按 <=14 全角宽给本格折了行，**一个字没改**（把换行符去掉后与真源 17_ 槽位表逐字相同，本条由脚本现算证明）。折行改的是域里那一格的值、而真源仓只读 => 走 DOC_PENDING 跟账（改值的唯一合法路径）。',
    },
    # ★ 2026-09-30：SYS_HELP_BATTLE_TURN 的条目随「帮助面板改造」删除（该键已从真源/域下线；
    #   它的口径「一手一手打」并进子面板 SYS_HELP_BATTLE 的结尾贴士）。
    "SYS_BAG_HEAD": {
        "old": "【背包】{n} 种",
        "new": "🎒 【背包】{n} 种",
        "why": "P2-21（同屏抬头补行首语义锚）：`背包` 是玩家敲得最多的那一屏，"
               "而词典里 🎒 早就归了『背包』（`SYS_BAG_FULL` 已在用）。"
               "★ 接法选 **SPACE 形**（图标 + 空格 + 【），与 10 条 `SYS_*_HEAD` 同形（`SYS_BOARD_HEAD` / `SYS_SKILL_HEAD` / `SYS_PARTY_HEAD` / `SYS_STATUS_HEAD` …）。"
               "  ★ **第一版我写成了 BRACKET 形（emoji 紧贴【），是 `probe_emoji_order` ① 当场拒了：**同屏里 🎒 出现两种接法**（`SYS_BAG_FULL` 是 SPACE）。**判据被拒回去把接法改对，不是放宽判据**（断一字未改）。"
               "★ **不给并列行加图标**：`· ` 就是行首锚（P2-15 已定），`_ROW` 不加第二层。",
    },
    "SYS_SORT_HEAD": {
        "old": "【整理】{n} 种，按类归好了",
        "new": "🎒 【整理】{n} 种，按类归好了",
        "why": "P2-21（同上）：`整理` 屏列的就是背包那几类东西 ⇒ 与 `SYS_BAG_HEAD` 同一个锚。"
               "★ 同屏的 `SYS_SORT_ROW` 是 `· ` 起头的并列行，按既定口径不加图标（不制造第二重行首）。",
    },
    # ===== P2-22（文案车道 aep2 · 屏抬头补行首语义锚 · 委托屏 + 成就屏）=====
    "SYS_MINE_HEAD": {
        "old": "【进行中】{n} 条",
        "new": "📜 【进行中】{n} 条",
        "why": "P2-22 缺口（现算 + 读端取证）：`我的委托` 屏三条抬头（进行中/已交/评级）**整屏全裸**，"
               "而本包已固化 📜 = 读东西/清单/单子（真源 26_ §2.2 逐字「📜 读东西 —— 碑、书、字条、划痕」），"
               "同义的 SYS_BOARD_HEAD / SYS_CODEX_HEAD / SYS_SKILL_HEAD 三条抬头都在用。"
               "★ 屏内三条抬头必须同锚（`probe_emoji_order` ④ 同屏抬头锚点须一致）⇒ 三格同批。"
               "★ 接法取 SPACE 形（emoji + 空格 + 【】）：同包 10 条已落地的 _HEAD 全部是这个接法。"
               "只改这一格的值，params / 取件点一字未动。",
    },
    "SYS_MINE_DONE": {
        "old": "【已交】{n} 条",
        "new": "📜 【已交】{n} 条",
        "why": "P2-22（同上）：与 SYS_MINE_HEAD / SYS_MINE_RANK 同屏同角色（三条抬头）⇒ 必须同锚同接法。"
               "★ 本槽位与 `评级` 屏那一行共用（B4-14 起同一个门、同一格），同锚后两屏都齐。",
    },
    "SYS_MINE_RANK": {
        "old": "【评级】{tier}",
        "new": "📜 【评级】{tier}",
        "why": "P2-22（同上）：委托屏第三条抬头。前两条补锚后，若本条仍裸 ⇒ `probe_emoji_order` ④ 当场红"
               "（同屏抬头锚点不齐）⇒ 三格必须同批。档名走 RANK_<ID> 槽位，本格只带 tier 一个参数。",
    },
    "SYS_ACH_HEAD": {
        "old": "【成就】今天能记的都在这儿",
        "new": "📜 【成就】今天能记的都在这儿",
        "why": "P2-22 缺口（现算 + 读端取证）：`成就` 屏抬头整屏全裸，而屏内四条并列行是 ·  起头"
               "（·  即行首锚，按既定口径不再加第二层）；抬头那一层缺锚 ⇒ 一屏两套行首接法。"
               "★ 图标取 📜（读东西/清单）：本屏列的就是「称号/彩蛋/四本谱/交付」几本账 = 读清单，"
               "  与 SYS_ACH_ROW 的 ·  不冲突（一行首、两种角色各用各的锚）。"
               "★ 屏内无任何已带图标的行可参照接法 ⇒ 沿用本包 _HEAD 的统一 SPACE 形（10/10 现成事实）。",
    },
    # ===== P2-23（文案车道 aep2 · 屏抬头补行首语义锚 · 第二批）=====
    "SYS_READ_HEAD": {
        "old": "【{name}】",
        "new": "📜 【{name}】",
        "why": "P2-23 缺口（现算 + 真源词典取证）：`读东西` 屏（4 条）**整屏零图标**，抬头裸【】起头。"
               "📜 取自真源 26_ §2.2 逐字「📜 读东西 —— 碑、书、字条、划痕」；本包已固化 19 处同语义。"
               "★ 屏内其余三条（能读的是/没有/没叫这名）是正文与提示，不属抬头层 ⇒ 不动。",
    },
    "SYS_MAP_HEAD": {
        "old": "【{name}（{kind}）】",
        "new": "📍 【{name}（{kind}）】",
        "why": "P2-23（同上）：`地图` 屏（5 条）整屏零图标。📍 取自真源 26_ §2.2 逐字"
               "「📍 位置 / 地图 / 去哪 —— 场景头、位置提示」；本包该语义目前仅 1 处，"
               "由本格补齐为这一族的既定写法。★ 只加行首图标，括号与参数一字未动。",
    },
    "SYS_PLACE_HEAD": {
        "old": "【{name}】",
        "new": "📍 【{name}】",
        "why": "P2-23（同上）：`场所` 屏（4 条）整屏零图标，与 `地图` 屏同属「位置」语义"
               "（真源 §2.2 把「场景头、位置提示」列在同一行）⇒ 同一图标，不新造第三个。",
    },
    "SYS_ITEM_HEAD": {
        "old": "【{name}】{icon} {detail} ×{n}",
        "new": "📦 【{name}】{icon} {detail} ×{n}",
        "why": "P2-23（同上）：`物品详情` 屏（8 条）整屏零图标。📦 在本包已固化为「物品进出」语义"
               "（7 处：穿上/卸下/放进箱子/取出/做成/这一场用过），本屏列的正是这一件东西 ⇒ 同一图标。"
               "★ 注意本格**屏内已有 `{icon}` 参数**（物品自带字形）：行首 📦 与之不同层、不冲突"
               "（一为屏锚、一为物名装饰），与 P2-21/P2-22 定的「一行首一锚」同口径。",
    },
    # ===== P2-25（文案车道 aep2 · 屏抬头补行首语义锚 · 第三批）=====
    "SYS_TOWER_MAP_HEAD": {
        "old": "【{name} · {floor}】（第 {n}/{all} 层）",
        "new": "📍 【{name} · {floor}】（第 {n}/{all} 层）",
        "why": "P2-25 缺口（现算 + 读端取证）：`副本地图` 屏（5 条）**整屏零图标**，抬头裸【】起头。"
               "📍 取自真源 26_ §2.2 逐字「📍 位置 / 地图 / 去哪 —— 场景头、位置提示」；"
               "P2-23 已把该语义固化为本包既定写法（SYS_MAP_HEAD / SYS_PLACE_HEAD / SYS_SHOP_HEAD 各一处）。"
               "★ 读端 `cmds_tower.py::tower_map` 的参数是 `{name}`=副本名 + `{floor}`=这一层名，"
               "  屏上就是一张「我在哪一层」的位置图 ⇒ 归 📍，不是 📜（那一格没在读东西）。"
               "★ 屏内其余四格：房间名是 `▸`/空格起头的并列行（另一种行首接法）、两句尾行是散文 ⇒ 都不补。",
    },
    "SYS_JUNK_HEAD": {
        "old": "【旧货铺】柜台上摊着一堆没人要的东西。",
        "new": "🎒 【旧货铺】柜台上摊着一堆没人要的东西。",
        "why": "P2-25（同上）：`旧货铺` 屏（6 条）整屏零图标。🎒 在本包已固化为「背包/整理」语义"
               "（P2-21 给 SYS_BAG_HEAD / SYS_SORT_HEAD 定下，共 2 处），而本屏列的正是"
               "「你包里能出手的东西」（SYS_JUNK_MINE 逐字）⇒ 同一图标，不新造。"
               "★ 屏内 SYS_JUNK_ROW 是 `· ` 起头的并列行（按既定口径 `· ` 本身即行首锚，不再叠图标）"
               "  ⇒ 抬头 🎒 之外那一层不碰，两层各用各的锚。",
    },
    "SYS_TRADE_HEAD": {
        "old": "【副业】手艺人自己的活 —— 不在玛莎那块板上。",
        "new": "📜 【副业】手艺人自己的活 —— 不在玛莎那块板上。",
        "why": "P2-25（同上）：`副业` 屏（7 条）整屏零图标。📜 = 读东西/清单/单子"
               "（真源 26_ §2.2 逐字；本包已固化 20 余处），本屏列的就是一份「手艺人自己的活」的清单"
               "⇒ 与 SYS_MINE_HEAD（我的委托，📜）同族。",
    },
    "SYS_TRADE_LIST_HEAD": {
        "old": "【{trade}】{n} 条",
        "new": "📜 【{trade}】{n} 条",
        "why": "P2-25（同上）：`副业 · 某一条线` 屏抬头。★ 与 SYS_TRADE_HEAD **同一族但不同屏**"
               "（`副业` 总览 vs `副业 采集` 单列），本包既定口径是「同屏三条抬头必须同锚」"
               "（见 SYS_MINE_HEAD/MINE_DONE/MINE_RANK 那次三格同批）⇒ 本格与上一条同锚同接法，"
               "否则打『副业 采集』时那一屏整屏全裸、而总览屏带 📜 ⇒ 两屏读起来像两种东西。",
    },

    # ===== P2-26（文案车道 aep2 · 2026-09-29 16:3x · A 类裸抬头**清零**）=====
    # A 类 = 值以【 开头（屏上的纯【】标题行）且行首没有图标的那一格。
    # ★ 现算（逐条扫 texts.json，不抄作业书）：动手前 **11 条**（45 条 _HEAD 里）⇒ 本批处理 9 条。
    # ★ 判据承 P2-24/P2-25 的「补锚三问」，第 ③ 问**按读端取证、不按槽位名猜**。
    # ★ 排期口径两条**别推翻**（承 P2-24/P2-25）：并列行（`· ` 起头）一个都不补 ·
    #   散文式抬头不补 · 接法 SPACE 形 · 图标逐字取真源 26_ §2.2 · 只补 A 类纯【】标题行。
    "SYS_FOOT_HEAD": {
        "old": "【记录】走过 {places} 个地方 · 打过 {kills} 只 · {days} 个游戏日",
        "new": "📊 【记录】走过 {places} 个地方 · 打过 {kills} 只 · {days} 个游戏日",
        "why": "P2-26（第 ③ 问取证）：`足迹` 屏（cmds_codex.py::footprint）抬头裸【】起头，"
               "屏内 SYS_FOOT_MORE / _BOOKS 两条都是行首 `· ` 的统计行。"
               "★ 屏上是一张**纯统计面板**（走过/打过/读过/采过/交过 + 四本谱进度）⇒ 真源 26_ §2.2 逐字「📊 面板 / 状态 —— 属性、背包、面板」，"
               "且本包已固化为该语义（SYS_ATTR_HEAD / SYS_STATUS_HEAD / SYS_RANKING_HEAD）。"
               "★ 同屏那两条 `· ` 行按既定口径 `· ` 本身即行首锚、不叠图标 ⇒ 只动抬头这一格。",
    },
    "SYS_GUILD_HEAD": {
        "old": "【公会】门面比镇上任何一家都像样：一块木牌，牌上画着一把断了的剑和一只手。",
        "new": "📜 【公会】门面比镇上任何一家都像样：一块木牌，牌上画着一把断了的剑和一只手。",
        "why": "P2-26（第 ③ 问取到**槽位名会骗人**的一处）：槽位叫「公会」，"
               "但读端（cmds_quest.py::guild, :1148）第二格 SYS_GUILD_DESK 逐字是「柜台在挂板墙那边」⇒ 屏上讲的**就是挂板墙那个地点**，"
               "而挂板墙三条抬头（SYS_BOARD_HEAD / _BOUNTY_HEAD / _SIDE_HEAD）早已固化 📜 ⇒ 本格同族同锚，"
               "不新造 🏠（真源 26_ §2.2 有 🏠「镇上/场所」，但本包 P2-23 已裁决「场所一律走 📍、不启用 🏠」，"
               "此处屏上又不是场所而是单子）。★ 同屏另两格：DESK 是散文、HOW 是「」引起的指令指引 ⇒ 都不是行首锚，"
               "不碰。",
    },
    "SYS_EV_HEAD": {
        "old": "【今天的动静】",
        "new": "📜 【今天的动静】",
        "why": "P2-26（第 ③ 问）：`异动` 屏（cmds_ast.py:1024）抬头裸【】起头，"
               "屏内是events_now 逐条事件正文（世界动静域）。真源 26_ §2.2 的表里**没有「异动」字面**⇒ 不硬造同义图标；"
               "按本包已固化的「清单 / 事件类 = 📜」归（与 SYS_CARAVAN_HEAD 同族）。"
               "★ 屏内逐条事件正文没有行首锚（不带 · 也不带图标）⇒ 抬头这个锚是**全屏唯一**的，"
               "  补上正是「该配图标而没配」的那一类缺口。",
    },
    "SYS_CARAVAN_HEAD": {
        "old": "【商队歇脚处】通北商道上下来的消息先到这儿。",
        "new": "📜 【商队歇脚处】通北商道上下来的消息先到这儿。",
        "why": "P2-26（第 ③ 问）：`商队歇脚处` 屏（cmds_places.py:173）抬头裸【】起头，"
               "屏内是 events_now 的 world 档逐条消息 ⇒ 与 SYS_EV_HEAD **同读端同形状**（都是「一屏一个清单头 + 逐条正文」）⇒ 同锚。"
               "⚠️ 别按槽位名里的「商队/歇脚处」去配 🏠 或 📍：屏上没有任何一行在讲位置（真源 26_ §2.2 📍 = 位置/地图/去哪）。",
    },
    "SYS_NOTICE_HEAD": {
        "old": "【公告】本服现在跑的是这一份：",
        "new": "📜 【公告】本服现在跑的是这一份：",
        "why": "P2-26（第 ③ 问）：`公告` 屏（cmds_self.py:283）抬头裸【】起头，"
               "屏内三格是本服版本 / 能敲什么 / 下一步 ⇒ 一份清单 ⇒ 📜（与挂板墙、指令表、本群榜同族）。"
               "★ 屏内另两格是行首 `· ` 的清单行 ⇒ 按既定口径不叠图标，只动抬头。",
    },
    "SYS_CARAVAN_GOODS": {
        "old": "跟着车来的货摊在棚子底下：",
        "new": "📜 跟着车来的货摊在棚子底下：",
        "why": "P2-26b（★ **由 `probe_icon_consistency` ① 当场抓出来的真缺陷**，不��预先想到的）：补了 SYS_CARAVAN_HEAD 的 📜 之后，`商队` 屏里另一条 **section_head**（`SYS_CARAVAN_GOODS`，槽位名以 `_GOODS` 结尾、落在 `probe_icon_consistency` 的 HEAD_SUF 里）仍是裸的 ⇒ **同屏两条 section_head 一条带图标一条不带**，正是鱼鱼口径（「emoji 是可以的……只要很规整观感好问题就不大」）要判的那一类。⇒ 同批补 📜，与该族已固化的 SYS_SMITH_CRAFT_HEAD / SYS_SMITH_SRC_HEAD 一致。",
    },
    "SYS_BSHOW_HEAD": {
        "old": "【单子 {order}】{name}（{level} 级以上）",
        "new": "📜 【单子 {order}】{name}（{level} 级以上）",
        "why": "P2-26（第 ③ 问）：`单子 <编号>` 屏（cmds_more.py:160，"
               "B3-12 委托全文）抬头裸【】起头。★ 它与 SYS_BOARD_HEAD 是**同一张单子的两种看法**（板上那一条 vs 打开看全文）⇒ 挂板墙那三条早已固化 📜 ⇒ 本格必须同锚；"
               "只补它会造成「板上带 📜、打开单子整屏全裸」。",
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
