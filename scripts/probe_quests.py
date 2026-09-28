# -*- coding: utf-8 -*-
"""探针：quests 域 —— 结构 · 前置链 · ★ 跨域对账（giver 是真人 · map 是真图）· 奖励可算。

B3-3 加的那一组（生活职业任务 / 副业）：
  ⑪-trade 四值三处一致（28 §三 的取值 ↔ `_meta.trades` ↔ schemas/quests.schema.json 的 enum）
  ⑫ 生活任务 8 条 · 每副业 ≥3（源：21 §二「四项 × 3–5 条」）
  ⑬ ★ 16 条一条不落 + 与 21 §二 **逐条对账**（名字 · 副业 · 内容 · 奖励）—— 域里 trade 任务与
     文档那 16 条**集合相等**（少一条是多一份缺项，多一条是两处口径）
  ⑭ 副业任务都有 giver（真人），且**挂的人与 28 §四 的「挂谁」对上**（按名字对）
  ⑮ ★ 生活任务一律写了 `require`（不许落 `flags.side_*` 那条死路径）且条件逐条可验：
      kind 在三型里 · visit 落在真图真节点 · item 真存在**且真有出产渠道**（探针自己从
      采集池 / 掉落池 / 配方产出重算）· kill 指向真怪
  ⑯ 三条带最深处各有采集点（「去三条带最深处各采一次」这个动作真做得了）
  ⑰ 「副业」指令真跑（无参 · 四个带参 · 一个错参）：都有话、取不到文案的标记一个都没有
  ⑱ ★ 生活任务端到端走得通（真调 接 → 交）：条件没满足时拦住并说清缺什么；补齐后交得掉、
      奖励入档、`flags.quests` 写下 done（这把「新条目落在死路径上」那类事当场钉住）

B3-6c 加的那一组（主线三段行文归位 texts · 解 P-17 甲案）：
  ⑨（改）交付文案的取口不再直接读域字段 —— 主线走 texts 槽位，其余链条读域内字段
  ⑲ 主线 12 × 3 = 36 条槽位齐备 · 且都不是占位（「〔待填…〕」「（待写）」「（进行中：…）」）
  ⑳ ★ 12 条与 24_任务线_v1 §一 **逐条对账**（探针自己解析那份文档）：名字一致 ·
      三条行文各自落在**本条**的专名锚上（NPC / 怪 / 物 / 图 / 节点名）· 交时那一段必须命中
      「交付」栏的锚 · 不许提别的条才有的人 / 怪（串台哨兵）
  ㉑ ★ 真跑「接 <编号>」/「交 <编号>」各 12 遍：槽位里的字必须**逐字**出现在屏上
      （取不到文案的标记一个都不许有）—— 槽位 → 玩家眼睛的闭环
      ★ B4-2 加严：另加「等级够 + 目标那几步一步没做」那档 —— 必须拦住，且「还差…」要把
      缺的**每一条**都点出来（条数 = 条件条数）
  ㉒ 归位总账（**不判红** · 两条批一起算）：quests 域 41 条 · 真源 = texts 123 条槽位 ·
      域里那三个内嵌字段 0 处

B3-8 加的那一组（支线 18 / 生活 8 / 悬赏 3 三段行文归位 · 同一套映射一次收完）：
  ㉓ ★ 29 条按 chain+order 都算得出**真槽位**（不是 fail-closed 哨兵）· 域里**每一条**都不是
      哨兵 · 且域名里那三个内嵌字段 `story/progress_text/deliver_text` **0 处**
      （B3-3 的生成器 `rebuild_prof_quests.py` 还会写那三个字段 —— 谁重跑它，这条当场红）
  ㉔ ★ 29 条与三份真源**逐条对账**（探针自己解析）：
      支线 = `24 §二` 的支线表（名字 · 谁给 · 步骤=objective · 奖励=hook · 三条行文落在
      步骤/奖励的锚上 · 奖励里「」的词一个不落）· 生活 = `28 §四` 新 8 条（+ `21 §二` 两稿
      对账）· 悬赏 = `24 §二` 悬赏板块 + `05 §一`（报酬区间两处一致 · 域里的钱落在区间里）
      · 串台哨兵（三段行文里只许提本条文档行出现过的人）· 悬赏三条「交时行文」逐字＝
      归位前域里那一行（玩家看到的字一个没动）
  ㉕ ★ 87 条槽位非占位（「待填 / 待写 / 〔 / （待 / 进行中」）· 无阿拉伯数字 · 无机器键 · 互不重复
  ㉖ ★ 支线 / 生活 / 悬赏 各抽一条真跑：接 / 交(没做完) / 交 —— 三拍的字逐字在屏上、奖励入档

B3-11 加的那一组（悬赏三档的数值口径 · 支线的交付真跑矩阵 · P-25 §② 的能修那部分）：
  ㉗ ★ 悬赏三档（普通 / 精英 / 头目）的**经验与钱逐条对账**（探针自己解析真源）：
      经验 = 该档 `min_level` 的升级需求 × N/D（N/D 从 `05 §一` 与 `24 §二` 两处解析，两处必须
      写着且一致；升级需求走包内唯一口 `cmds_ast.exp_need` —— 不手打）· 钱落在 `24 §二` ＝
      `05 §一` 的报酬区间里（区间中点那件事只印出来给人看）
  ㉘ ★ 18 条支线的**交付真跑矩阵**：交得掉的**真接一次、真交一次**（造满足 `require` 的档）；
      交不掉的**钉住名单 + 逐条原因**，且每个都用「万事俱备的档（满级 + 全图全节点 + 所有物品 +
      所有怪各 99 只）」**复现**一遍 —— 那样都交不掉 ⇒ 它看的不是条件，而是 `flags.side_<名字>`
      那个没人写的键（P-25 §② 的根因）。名单一变（修好一条 / 新死一条）当场红。

B3-13 加的那一组（支线另外 6 条的条件 · 悬赏「指定的」落地成每日轮换）：
  ㉚ ★ 新四型（`enhance` / `cook`（含 `quality`）/ `talk` / `ask`）逐条对账：探针**自己**从
      `24 §二` 的「步骤」列 + `21 §二` 解析出该有什么条件（含数词），与域里的 `require` 比；
      再核「账真存在」（写入口那几处真跑出来的账）·「量够达成」（强化上限 / 可做的菜 / 有对话树的人）
      ·「途径存在」（`cook.quality` 那一品阶的食材真有出产渠道）；最后**每条真做一次再真交一次**
      （强化 ×3 / 下锅 ×3 / 跟老陶搭话 ×3 / 跟三个人搭话 / 用稀有食材下锅 ×1）。
  ㉛ ★ 悬赏「指定的」：24 §二 那两句（`打掉**指定的**普通 / 精英 / 头目怪` +「每天轮换挑一只」）
      ★ B4-9：轮换看的「第几个游戏日」= `calendar.day_now()`（现算那根钟）⇒ 用例**拨钟造日**
      都在 ⇒ 三档条件都必须带 `daily`；轮换**可复现**（同一日同档两次同结果 · 跨日必换 ·
      探针自己按「该档按 id 排序取第 (游戏日-1)%n+1 只」算一遍与实现比）；**宽口径已被拦住**
      （打掉同档的**另一只**不顶用 —— 这是判据加强的那一半）；认不出的档 ⇒ 没满足（fail-closed）。
      ★ g3-quests2（本波）**规格收窄**：池从「该档**全部**怪」改成「该档的怪 ∩ **可遇集合**」
      （该怪 `habitat` 写明的**每一站**上，按该档 `min_level` 都进得了「等级最近前 3」——
      尺子 = 玩家敲『攻击』时挑怪用的那一把）。轮换算法一个字没动。新增三条判据（只加强）：
      ① 三档的池子 == 探针自己算的可遇集合；② 被剔掉的**逐只点名** + 剔的理由现算；
      ③ **反证**：把可遇性过滤拿掉 ⇒ 逐个游戏日比至少一天对不上（改回旧规格当场红）。

B4-2 加的那一组（P-25 §① 主线收口 · P-37 曲线唯一口）：
  ⑧-b ★ P-37：本探针原先**手打了一份 `lv*lv*40`**（K59「曲线别在第三处再手打一个」的第 4 处）——
      B3-19 顺手改走 `cmds_ast.exp_need`；这一批把它钉成机器可验：探针用的那个口**就是**包内
      唯一口（对象同一）· 本文件里手打的曲线式子 **0 处**（守卫的式子拼出来写，免得撞自己）
  ㉜ ★ 主线 12 条**逐步记账**（条件真源 = `24 §一` 每块的「步骤」行，含**续行**）：每条都写了
      `require`（一条不落）· 每条条件的**目标**（人 / 站 / 图 / 怪 / 物）在本条自己的「步骤」
      行里点了名（探针现解析；不是从别条串台凑的）· **缺一步矩阵**（逐条少做那一件 ⇒ 拦住）·
      万事俱备 ⇒ 交得掉 + 奖励入档 + `flags.quests[<id>]` 的 `step == 条件条数`

B4-27 加的那一组（P-25 §① 主线交活判据 · 按条目身份复核后钉住）：㉟（见 ㉜ 之后那一节）。
★ 台账 P-25 那句「① 主线交活只判等级」**已经过期** —— B4-2 已把 12 条主线全落上 `require`、
`_obj_ok` 主线那一支已是「等级 **且** 逐步记账」；本批 grep 消费者复核后**没有改行为**，
只把结论钉成机器可验：等级那一半单独载重（万事俱备 + 等级压在门槛下 ⇒ 拦住）·
每条条件的途径都存在（与支线 ⑮/㉚ 同一把尺子）· `_obj_ok` 主线那一支两半都在（静态守卫）。

B4-27 加的那一组（P-25 §② 再收一条：支 7 白烛堂的灯）：
  ㉚（扩）★ 支 7「送灯油 → 陪他配一次」的后半截落成 `talk npc_ed ×1`（「陪」= 搭话，与
      「听他讲完（三次）」同一族；次数从那一句现取）⇒ `_EXP_KIND` 6 → **7**，于是 ㉘ 的
      「交不掉」钉住名单 5 → **4**（名单只许变短，变了当场红）。
      ★ 前半截「送灯油」**没落**：items 域里没有「灯油」这件东西 ⇒ 缺口登记在 `_notes.md`。

B4-27 加的那一组（P-53 见习证门）：㉝（四拍，见文件尾部那一节）。**判据没有一条放宽** ——
既有夹具里「手拼最小档直接接活」的十几处只是照**新守卫**补上 `flags.card`（探针 / probe_copy /
probe_cmds 各自补），原来钉的那些分支一条都没少。

B4-27 加的那一组（P-56 放弃的冷却）：㉞（三拍真敲 + 跨日 + 失败档，见文件尾部那一节）。
★ 「掉一点声望」那半**没落**（没有容器）—— 登记在工作树 `_notes.md`「待鱼鱼拍板」。

w9 加的那一组（P-61 悬赏板列三档悬赏）：㊱（见文件尾部那一节）—— 三档逐行对槽位 ·
板上那三个编号**真接得下**（接线档）· 已接那档带「进行中」· 段序照旧 · 域里没有悬赏档时
一行都不列（反证）。★ 判据只加不松：这一节没动上面任何一条。

fix-m-bounty 加的那一组（悬赏日常循环断链 · 看板列了交掉的活）：㊲（见文件尾部那一节）——
① 悬赏**跨游戏日可重接**（真源 `24 §二`「无限循环的日常内容 · 每天刷 1 次」+ `03 §4.1`
「打怪类的日常活，**可反复接**」）：第 A 日交掉后**同日**仍拦 · **第 B 日放行**（真接下 ·
完成记录不摘）· 第 B 日再交一次**落账去重**（`quests_done` 不许同一档进两份）·
主线 / 支线 / 副业**跨日也照旧拦**（判据只加强）· 完成日**写坏 / 缺记录**一律拦（fail-closed）·
反证：把链的限定拿掉 ⇒ 主线当场就接得下（拦主线真靠这条判据）。
② `悬赏` 板那一段**只列还能接的**：已交那条不在板上 · 没交的照旧 · 全交掉 ⇒ **连表头都不印**；
反证：把 `_done` 换回空表 ⇒ 已交那条又出现。

fxm3-questsnap 加的那一组（接活即能交 · 白拿经验）：㊴（见文件尾部那一节）——
`require` 判的是「**接活后**新达成」（接活那一下落进度基线 `flags.quests[<id>]["base"]`）：
① 形状（基线逐条等于接活那一刻的读数 · 没写 `require` 的不落那一格）·
② 态一「接活前把活干完」⇒ **增量型条件逐条拦住**（读数只会因「接活那一下真给的」而涨，见下）、
`提示` 跟着判定走（还有没满足的 ⇒ 不许说办完了；全满了 ⇒ 必须说办完了）、`交` 的门跟着判定走
（该拦的拦住且**档上一个字不动**）·
③ 态二「接活后真干一次」⇒ 交得掉、奖励逐字入档且**只发一次** ·
④ 反证（关掉 `_set_base`）⇒ 主 3 / 主 4 / 主 11 当场又白拿 ·
⑤ 老档（无基线）与改前逐字节相同（**有意兼容**，不是放宽）。
★ 2026-09-27（这一组的四处自身错，已修 · 判据只加强 · 见 `_tot39` 与那一节的注释）：
   · 奖励与「只发一次」按**累计经验**比（`add_exp` 跨级结转 —— 比 `exp` 那格的差会把升级消耗
     当成少发奖励：21 条支线/副业被误报）；
   · 条件分两种口径：**增量型**（visit/kill/item/cook/talk/ask ⇒ 判「接活后新达成」）与
     **状态型**（`enhance` ⇒ 判绝对值，有意；走到「接活那一刻就全达标」那一态时**登记成
     `_l39` 里的一行有意缺口**，不静默放过）；
   · **接活那一下真给的东西**（`quests.<id>.give`）算「接活后到手」（真源 `17 §QUEST_SIDE25_STORY`
     「小满把那块石头塞给你」· `_set_base` 就在 `_hand_over` 之前 —— 顺序本身就是口径）；
   · 「还差」的版面判据改成**逐条**核（没满足的每条 `_req_lines` 都得出现 · 已满足的一条都不许留），
     不再数「含『还差』的行数 == 条件条数」（文字是槽位文本，判据不该认它）。
真源：`24_任务线_v1.md §一` 每块的「步骤」（主 3「② **各完成一次**（打怪/采集/送信）」）。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_quests.py
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
PLAN = os.environ.get("AST_PLAN", "C:/Users/yuyu/aetheran-plan")
sys.path.insert(0, ENGINE)
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, REPO)          # ★ P-27 顺手：经验曲线要走包内那个唯一的口（禁止手打）

from saintess_engine.package import load_stack          # noqa: E402

st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
st.install()

Q = st.domain("quests")
NPCS = st.domain("npcs")
MAPS = st.domain("maps")
MON = st.domain("monsters")
ITEMS = st.domain("items")
GA = st.domain("gathering")
DP = st.domain("drop_pools")
RC = st.domain("recipes")
TX = st.domain("texts")

#: 域里的**条目**（`_meta` 那类私有键不算条目 —— 与 content/cmds_quest.py::_quests 同口径）
QE = {k: v for k, v in Q.items() if not str(k).startswith("_")}

#: ★ B4-9：`_daily_pick` 的「今天是第几个游戏日」走 `calendar.day_now()`（**现算**那根钟）
#:   ⇒ 「第 N 日」要**拨钟**来造，不是往档上写一个 `day`（那格只是 `tick()` 的跨日标记；
#:   B4-9 起日期戳一律现算 —— 见 `content/calendar.py::day_now` 与 §4 的 K70）。
from content import calendar as CAL_Q                                   # noqa: E402
from content import facade as FC_Q                                      # noqa: E402

_FC_SAVED = dict(FC_Q.HANDLES)
_DAY_SECS = CAL_Q.scale_seconds()


def _at_day(d, h=6.0):
    """把假钟拨到「第 d 个游戏日 · 昼（6 点）」—— 轮换与日期戳看的就是这根钟。"""
    FC_Q.bind_host(clock=lambda _e=(float(d) + h / 24.0) * _DAY_SECS: _e)


fails, notes = [], []
CHECKS = [0]
ok = lambda m: (CHECKS.__setitem__(0, CHECKS[0] + 1), print("  ✓ " + m))
bad = lambda m: (fails.append(m), CHECKS.__setitem__(0, CHECKS[0] + 1), print("  ✗ " + m))

print("探针：quests 域（任务与委托）")
print("  ✓ quests 域读得到  —— %d 条" % len(QE))

# ① 三类齐全 + 数量
for kind, want in (("主线", 12), ("支线", 18), ("悬赏", 3), ("生活", 8)):
    n = len([v for v in QE.values() if v["kind"] == kind])
    (ok if n == want else bad)("%s %d 条（应 %d）" % (kind, n, want))

# ② 必填字段
REQ = ("name", "kind", "giver", "map", "min_level", "objective", "reward_exp", "reward_gold")
miss = [k for k, v in QE.items() if any(f not in v for f in REQ)]
(ok if not miss else bad)("必填字段齐全（缺 %s）" % (miss or "无"))

# ③ ★ 跨域：giver 是真 NPC
bad_giver = sorted({v["giver"] for v in QE.values() if v["giver"] not in NPCS})
(ok if not bad_giver else bad)("★ giver 都是真 NPC（坏 %s）" % (bad_giver or "无"))

# ④ ★ 跨域：map 是真地图
bad_map = sorted({v["map"] for v in QE.values() if v["map"] not in MAPS})
(ok if not bad_map else bad)("★ map 都是真地图（坏 %s）" % (bad_map or "无"))

# ⑤ 主线前置链串得起来（q_main_N.need == q_main_{N-1}）
main = sorted([(k, v) for k, v in QE.items() if v["kind"] == "主线"], key=lambda x: x[1]["order"])
chain_bad = []
for i, (k, v) in enumerate(main):
    want = None if i == 0 else main[i - 1][0]
    if v.get("need") != want:
        chain_bad.append(k)
(ok if not chain_bad else bad)("主线前置链完整（12 条首尾相接；坏 %s）" % (chain_bad or "无"))

# ⑥ 主线等级递增
lvs = [v["min_level"] for _, v in main]
(ok if lvs == sorted(lvs) else bad)("主线等级递增  —— %s" % lvs)

# ⑦ ★ 每条主线都有「认知推进」和「钩子」
no_ins = [k for k, v in main if not v.get("insight")]
no_hook = [k for k, v in main if not v.get("hook")]
(ok if not no_ins and not no_hook else bad)(
    "★ 每条主线都有认知推进与钩子（缺 insight %s / hook %s）" % (no_ins or "无", no_hook or "无"))

# ⑧ ★ 奖励可复算（经验 = 等级² × 40 × 系数，钱 = 等级 × 系数）
#   ★ P-27 顺手：这条曲线**不再手打** —— 走包内唯一那个口 `cmds_ast.exp_need`
#     （升级判定 `add_exp` 与死亡惩罚 `_wake_in_chapel` 都走它；曲线一改这里自动跟着变）。
from content.cmds_ast import exp_need                    # noqa: E402
recalc = []
for k, v in QE.items():
    if v["kind"] == "主线":
        e, g = int(exp_need(v["min_level"]) * 0.33), int(v["min_level"] * 10)
        if v["reward_exp"] != e or v["reward_gold"] != g:
            recalc.append(k)
(ok if not recalc else bad)("★ 主线奖励可复算（奖励 = 等级函数，不手打；坏 %s）" % (recalc or "无"))

# ⑧-b ★ P-37（K59 同族：「曲线别在第三处再手打一个」）—— 本探针原先就是**第 4 处**（手打了一份
#   `lv*lv*40`），B3-19 顺手改走 `exp_need`；这一批把它**钉成机器可验**的两条：
#     ① 探针用的那个口**就是**包内唯一口（对象同一 —— 不是本地第二份实现）
#     ② 本文件里手打的曲线式子 **0 处**（式子拼出来写，免得守卫撞自己）
import content.cmds_ast as _CA8                                          # noqa: E402
_MUL8 = chr(42)
_src8 = io.open(os.path.join(REPO, "scripts", "probe_quests.py"), encoding="utf-8").read()
_hand8 = [x for x in ("lv" + _MUL8 + " lv", "lvl" + _MUL8 + " lvl",
                      "level" + _MUL8 + " level", _MUL8 + " 40")
          if x in _src8]
(ok if (exp_need is _CA8.exp_need and not _hand8) else bad)(
    "★ P-37：经验曲线只有包内一个口 —— 探针用的就是 `cmds_ast.exp_need`（同一对象：%s）· "
    "本文件里手打的曲线式子 0 处（实得 %s）" % (exp_need is _CA8.exp_need, _hand8 or "无"))

# ⑧-c ★ P-37 收口（B3-14 顺手核出那条账的**另一半**）：唯一口还要与**真源现算对账**，
#   而且「曲线只此一处」要按**全包**核 —— ⑧-b 只核了本文件自己。
#   真源 `06_第一阶段垂直切片/00_第一阶段内容总纲_v1.md §七`（2026-09-25 定格）：
#     「升级需求 40 × L² ⇒ L1 40 · L10 4,000 · L20 16,000（1→20 级合计 98,800）」
#   ⇒ ① 乘数与那三个锚点、那一个合计**从文档现解析**，与 `exp_need` 逐点现算比；
#      ② 1–20 全等级 + 六锚点（1/20/40/60/80/100）逐点比（鱼鱼硬约束：数值都要按等级扩展体检）；
#      ③ 全包（`content/` 与 `scripts/` 的 .py）里「等级平方」那种式子的**代码落点只有
#         `content/cmds_ast.py` 一处**；别的文件里若出现，只许在注释里（列出来）。
import re as _re7                                                        # noqa: E402
_DOC7 = os.path.join(PLAN, "06_第一阶段垂直切片", "00_第一阶段内容总纲_v1.md")
_D7 = io.open(_DOC7, encoding="utf-8").read() if os.path.exists(_DOC7) else ""
_SEC7 = _D7.split("## 七、经济口径")[1].split("## 八")[0] if "## 七、经济口径" in _D7 else ""
_K7 = _re7.search(r"升级需求\s+(\d+)\s*[×x]\s*L", _SEC7)
_PTS7 = [(int(a), int(b.replace(chr(44), ""))) for a, b in _re7.findall(r"L(\d+)\s+([\d,]+)", _SEC7)]
_TOT7 = _re7.search(r"1→20 级合计\s*([\d,]+)", _SEC7)
_k7 = int(_K7.group(1)) if _K7 else 0
_bad7 = [("L%d" % _L7, _v7, exp_need(_L7)) for _L7, _v7 in _PTS7 if exp_need(_L7) != _v7]
_all7 = [_L7 for _L7 in range(1, 21) if exp_need(_L7) != _k7 * _L7 * _L7]
_anch7 = [_L7 for _L7 in (1, 20, 40, 60, 80, 100) if exp_need(_L7) != _k7 * _L7 * _L7]
(ok if (_k7 and _PTS7 and not _bad7 and not _all7 and not _anch7) else bad)(
    "★ P-37：曲线与真源**现算对账** —— 乘数 %s 从 `00 §七` 现解析 · 文档那 %d 个锚点逐点相等"
    "（%s）· 1–20 全等级 + 六锚点逐点相等（坏 %s / %s）"
    % (_k7 or "没解析到", len(_PTS7), _bad7 or "全对", _all7 or "无", _anch7 or "无"))
_sum7 = sum(exp_need(_L7) for _L7 in range(1, 20))          # 1→20 级 = 19 次升级
_want7 = int(_TOT7.group(1).replace(chr(44), "")) if _TOT7 else -1
(ok if _sum7 == _want7 else bad)(
    "★ P-37：1→20 级合计**现算** %d == 真源那一个数 %d（= 19 次升级，从 1 级升到 20 级）"
    % (_sum7, _want7))
_SQ7 = _re7.compile(r"\b(lv|lvl|level)\s*" + _re7.escape(_MUL8) + r"\s*(lv|lvl|level)\b")
#   ★ 分类口径：**按 AST 判「代码里真有这个式子」** —— 注释与文档串里的「提到」不算
#     （行文本判会假阳：`probe_quests` 自己的注释与模块头注里就写着那两处旧账）。
import ast as _ast7                                                      # noqa: E402
_STAT7 = {"lv", "lvl", "level"}
_code7, _mention7 = [], []
for _r7 in ("content", "scripts"):
    for _dp7, _dn7, _fn7 in os.walk(os.path.join(REPO, _r7)):
        _dn7[:] = [_d7 for _d7 in _dn7 if _d7 != "__pycache__"]
        for _f7 in sorted(_fn7):
            if not _f7.endswith(".py"):
                continue
            _fp7 = os.path.join(_dp7, _f7)
            _rel7 = os.path.relpath(_fp7, REPO).replace("\\", "/")
            _src7 = io.open(_fp7, encoding="utf-8").read()
            if _SQ7.search(_src7):                       # 文本层命中 = 只在注释/串里也记一笔
                _mention7.append(_rel7)
            _tree7 = _ast7.parse(_src7)
            # ★ 落点认**在哪个函数里**，不认行号（行号谁在上面加几行就漂 —— 本波就漂过一次）：
            #   取包住这个式子的**最内层**函数名；找不到 = 写在模块级（那也算「别处」）。
            _fnr7 = [(getattr(_d7, "lineno", 0), getattr(_d7, "end_lineno", _d7.lineno), _d7.name)
                     for _d7 in _ast7.walk(_tree7)
                     if isinstance(_d7, (_ast7.FunctionDef, _ast7.AsyncFunctionDef))]
            for _n7 in _ast7.walk(_tree7):
                if (isinstance(_n7, _ast7.BinOp) and isinstance(_n7.op, _ast7.Mult)
                        and isinstance(_n7.left, _ast7.Name) and isinstance(_n7.right, _ast7.Name)
                        and _n7.left.id in _STAT7 and _n7.right.id in _STAT7):
                    _own7 = ""
                    for _a7, _b7, _nm7 in _fnr7:         # 最内层：起点最大的那个包得住它的
                        if _a7 <= _n7.lineno <= _b7 and (_own7 == "" or _a7 > _own7[0]):
                            _own7 = (_a7, _nm7)
                    _code7.append("%s:%s@L%d" % (_rel7, (_own7[1] if _own7 else "（模块级）"),
                                                 _n7.lineno))
_OWN7 = {_c7.split("@")[0] for _c7 in _code7}
(ok if len(_code7) == 1 and _OWN7 == {"content/cmds_ast.py:exp_need"} else bad)(
    "★ P-37：「等级平方」那种式子的**代码落点只有一处** = `content/cmds_ast.exp_need`"
    "（按 AST 取「在哪个函数里」—— **不认行号**，行号谁在上面加几行就漂）"
    "· 实得 %s · 文本层提到过它的文件（注释/文档串，不算）：%s"
    % (_code7 or "无", _mention7 or "无"))

# ⑨ 交付文案不为空（三段式的第三段）
#   ★ B3-6c / B3-8：取口就是 code 里那个映射（`cmds_quest._slot_of` / `_beat` · 不另写镜像表）——
#     四条链都走 texts 槽位；域里那三个内嵌字段已裁掉（㉓ 钉着「0 处」）。
from content import cmds_quest as CQ                                      # noqa: E402


def _beat_of(x, part):
    slot = CQ._slot_of(x, part)
    return (TX.get(slot) or {}).get("value") or ""


no_deliver = [k for k, v in QE.items() if not _beat_of(v, "DELIVER")]
(ok if not no_deliver else bad)("每条都有交付文案（三段式的第三段 · 主线走 texts 槽位；缺 %s）"
                                % (no_deliver or "无"))

# ⑩ 解锁指向的东西真实存在（怪 / 图）
bad_unlock = []
for k, v in QE.items():
    for u in v.get("unlock") or []:
        if u in ("belt_north", "belt_east", "belt_west", "windmill_town", "old_watchtower"):
            if u not in MAPS:
                bad_unlock.append((k, u))
        elif u.startswith("boss_"):
            if not any(m.get("role_key") == "boss" for m in MON.values()):     # ★ 机器键（keys-2）
                bad_unlock.append((k, u))
(ok if not bad_unlock else bad)("解锁指向真实存在（坏 %s）" % (bad_unlock or "无"))

# ══════════════════════════════════════════════════════════════
# ⑪–⑱ B3-3 生活职业任务（副业）—— 真源：28_生活职业任务_设计_v1.md · 21_长期目标层_v1.md §二
#      ★ 探针**自己**从两份文档解析（走生成器的同一个解析口，不另写镜像表），不信域的自述。
# ══════════════════════════════════════════════════════════════
import rebuild_prof_quests as RP                                          # noqa: E402

doc_trades = RP.parse_trade_values()
doc_old8, doc_new8 = RP.parse_doc28()
doc21 = RP.parse_doc21()
meta_trades = [t.get("trade") for t in ((Q.get("_meta") or {}).get("trades") or [])]
sch = json.load(io.open(os.path.join(REPO, "schemas", "quests.schema.json"), encoding="utf-8"))
sch_enum = ((sch.get("patternProperties") or {}).get("^q_[a-z0-9_]+$") or {}).get("properties", {}) \
    .get("trade", {}).get("enum")

# ⑪ 四值三处一致
(ok if doc_trades == meta_trades == sch_enum else bad)(
    "★ 副业四个取值三处一致（28 §三 %s ＝ _meta.trades %s ＝ schema enum %s）"
    % (doc_trades, meta_trades, sch_enum))

# ⑫ 生活任务条数 + 每副业 3–5 条
trade_q = {k: v for k, v in QE.items() if v.get("trade")}
per = {}
for v in trade_q.values():
    per[v["trade"]] = per.get(v["trade"], 0) + 1
shape_bad = [t for t in doc_trades if not (3 <= per.get(t, 0) <= 5)]
(ok if len(trade_q) == 16 and not shape_bad else bad)(
    "★ 生活职业任务 16 条 · 每副业 3–5 条（实测 %s）" % per)

# ⑬ ★ 16 条一条不落 + 与 21 §二 逐条对账（名字 · 副业 · 内容 · 奖励）
def _norm(s):
    return str(s or "").replace("★", "").replace(" ", "").strip()


def _lcs(a, b):
    row = [0] * (len(b) + 1)
    best = 0
    for ca in a:
        prev, row = row, [0] * (len(b) + 1)
        for j, cb in enumerate(b, 1):
            row[j] = prev[j - 1] + 1 if ca == cb else 0
            best = max(best, row[j])
    return best


def _recon(a, b):
    """奖励对账：归一（去 ★ / 空格）后互相包含，或最长公共子串 ≥ 4 字。

    为什么不是逐字相等：域里那 8 条老支线的交付物是从 24 §二 落的（21 §二 与它
    「奖励一字不差」指的是那两份文档，域里的写法略有出入 —— 例：域「固定座位（buff 时长
    +50%）」vs 文档「客栈有个固定座位（增益 buff 时长 +50%）」）。规则写在明面上，逐条打印。
    """
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return False
    return a in b or b in a or _lcs(a, b) >= 4


doc16, recon_lines, notfound, mismatch, wording = [], [], [], [], []
new_ids = {qid for qid, _n, _t, _p, _r, _w in doc_new8}
for trade, _what, rows in doc21:
    for name, content, reward in rows:
        doc16.append(name)
        hit = [(k, v) for k, v in trade_q.items() if v["name"] == name]
        if len(hit) != 1:
            notfound.append((name, len(hit)))
            continue
        k, v = hit[0]
        why = []
        if v["trade"] != trade:
            why.append("副业 %s≠文档 %s" % (v["trade"], trade))
        if _norm(v["objective"]) != _norm(content):
            # 设计真源要的是「名字 + 奖励」两栏对账；「内容」列两份文档本就措辞有出入
            #   （24 §二 与 21 §二 是同一批人的两稿）—— 所以：**新 8 条**必须逐字一致，
            #   老的 8 条只印出来给人看，不判红（免得为了让它绿去改老条目的 objective）。
            if k in new_ids:
                why.append("内容「%s」vs 文档「%s」" % (v["objective"], content))
            else:
                wording.append("%s：「%s」vs「%s」" % (name, v["objective"], content))
        if not _recon(v.get("hook"), reward):
            why.append("奖励「%s」对不上「%s」" % (v.get("hook"), reward))
        if why:
            mismatch.append((name, why))
        recon_lines.append("%s → %s" % (name, _beat_of(v, "DELIVER")))
extra = [v["name"] for k, v in trade_q.items() if v["name"] not in doc16]
(ok if len(doc16) == 16 and not notfound and not mismatch and not extra else bad)(
    "★ 与 21 §二 逐条对账（16 条 · 名字/副业/奖励；缺 %s · 不符 %s · 多出 %s）"
    % (notfound or "无", mismatch or "无", extra or "无"))
if wording:
    print("  · 老 8 条「内容」列措辞的出入（两份文档的两稿 · 不判红 · %d 条）：%s" % (len(wording), wording))
print("  · 对账逐条：%s" % " ｜ ".join(recon_lines))

# ⑭ 副业任务都有 giver（真人）· 且与 28 §四 的「挂谁」对上
giver_bad = sorted({v["giver"] for v in trade_q.values() if v["giver"] not in NPCS})
person_bad = []
for qid, name, _t, _prose, _reward, who in doc_new8:
    v = QE.get(qid) or {}
    if (NPCS.get(v.get("giver")) or {}).get("name") != who:
        person_bad.append((qid, who, (NPCS.get(v.get("giver")) or {}).get("name")))
(ok if not giver_bad and not person_bad else bad)(
    "★ 副业任务都有真 giver（坏 %s），且挂的人与 28 §四 的「挂谁」一致（坏 %s）"
    % (giver_bad or "无", person_bad or "无"))

# ⑮ ★ 生活任务一律写了 require，且条件逐条可验（出产渠道由本探针自己重算）
produced = set()
for g in GA.values():
    for e in (g.get("pool") or []):
        produced.add(str(e.get("out")))
for p_ in DP.values():
    for e in (p_.get("entries") or []) + (p_.get("pool") or []):
        produced.add(str(e.get("out")))
for r in RC.values():
    if r.get("out"):
        produced.add(str(r["out"]))

no_req = sorted(k for k, v in trade_q.items() if not (v.get("require")))
cond_bad = []
for k, v in trade_q.items():
    reqs = v.get("require")
    reqs = [reqs] if isinstance(reqs, dict) else list(reqs or [])
    if not reqs:
        continue
    for r in reqs:
        kind = r.get("kind")
        if kind == "visit":
            m = MAPS.get(str(r.get("map")))
            if not m or str(r.get("node")) not in [n["id"] for n in (m.get("nodes") or [])]:
                cond_bad.append((k, "visit", r.get("map"), r.get("node")))
        elif kind == "item":
            iid = str(r.get("item"))
            if iid not in ITEMS and not (iid.startswith("unid_") and iid in DP):
                cond_bad.append((k, "item-不存在", iid))
            elif iid not in produced:
                cond_bad.append((k, "item-没有出产渠道", iid))
        elif kind == "kill":
            if str(r.get("monster")) not in MON:
                cond_bad.append((k, "kill", r.get("monster")))
        elif kind == "enhance":                    # ★ B3-13 四型：这里只核**结构性**那一点，
            if int(r.get("n") or 0) < 1:           #   逐条核（形状对文档 / 可达性 / 真做真交）在 ㉚
                cond_bad.append((k, "enhance-没给级数", r.get("n")))
        elif kind == "cook":
            if int(r.get("n") or 0) < 1:
                cond_bad.append((k, "cook-没给次数", r.get("n")))
        elif kind == "talk":
            if not (NPCS.get(str(r.get("npc"))) or {}).get("dialogue"):
                cond_bad.append((k, "talk-这个人没挂对话树", r.get("npc")))
        elif kind == "ask":
            if int(r.get("n") or 0) < 1:
                cond_bad.append((k, "ask-没给人数", r.get("n")))
        else:
            cond_bad.append((k, "认不出的 kind（fail-closed 会把这条任务卡死）", kind))
new_no_req = sorted(k for k in no_req if k in new_ids)
(ok if not new_no_req and not cond_bad else bad)(
    "★ 本批新 8 条一律写了 require（没写的 %s）· 条件逐条可验 / 要的东西真有出产渠道（坏 %s）"
    % (new_no_req or "无", cond_bad or "无"))


def _cond_str(v):
    """条件写成一行（给人看的）—— 出产渠道的出处也顺手带出来。"""
    reqs = v.get("require")
    reqs = [reqs] if isinstance(reqs, dict) else list(reqs or [])
    out = []
    for r in reqs:
        if r.get("kind") == "visit":
            m = (MAPS.get(str(r.get("map"))) or {})
            nd = next((n.get("name") for n in (m.get("nodes") or []) if n["id"] == r.get("node")), r.get("node"))
            out.append("去过「%s」" % nd)
        else:
            iid = str(r.get("item") or r.get("monster"))
            nm = (ITEMS.get(iid) or {}).get("name") or (DP.get(iid) or {}).get("name") or iid
            src = [g["name"] for g in GA.values() if iid in [str(e.get("out")) for e in (g.get("pool") or [])]]
            src += [p_["label"] for p_ in DP.values() if iid in [str(e.get("out")) for e in (p_.get("entries") or [])]]
            out.append("手上有「%s」×%d（出处：%s）" % (nm, int(r.get("n") or 1), " / ".join(src[:2]) or "配方产出"))
    return " ＋ ".join(out) or "（无条件）"


print("  · 人话 → 条件（本批新 8 条 · 逐条过目）：")
for qid in sorted(new_ids, key=lambda x: QE[x]["order"]):
    print("      %s %s「%s」→ %s" % (qid, QE[qid]["name"], QE[qid]["objective"], _cond_str(QE[qid])))

# ⑮-b（备注 · 不判红）★ P-25 §② 的活口：**没写 require 的支线今天交不掉**
#      （`_obj_ok` 对没写 require 的支线去看 `flags.side_<名字>` —— 那个键仓库里没有任何地方写）
#      ★ B3-11：逐条真跑 + 逐条原因在 ㉘（这里只报个数，别在这儿下结论）
#      ★ B4-2：主线那一半已收口（12 条都写了 `require` ⇒ 判据在 ㉜）；这几条支线仍缺**内容 / 形状**
dead = sorted(k for k, v in QE.items() if v["kind"] == "支线" and not v.get("require"))
notes.append("P-25 §②（未收口）：今天仍有 %d 条支线**交不掉** —— %s（逐条真跑与原因见 ㉘；"
             "主线那一半 B4-2 已收口 —— 12 条都写了 require，见 ㉜）" % (len(dead), dead))

# ⑯ ★ 三条带最深处各有采集点（「去三条带最深处各采一次」这个动作真做得了）
deep = RP._deepest_nodes(MAPS)
deep_bad = []
for mid, nd in deep:
    pts = [k for k, g in GA.items() if g.get("subarea") == nd]
    if not pts:
        deep_bad.append((mid, nd))
(ok if not deep_bad else bad)(
    "★ 三条带最深处 %s 各有采集点（空的 %s）" % ([(m, n) for m, n in deep], deep_bad or "无"))

# ⑰ 「副业」指令真跑（无参 · 四个带参 · 一个错参）—— `CQ` 已在 ⑨ 那节导入
from content import cmds_ast as CA                                        # noqa: E402

MISSING = "[MISSING TEXT"


class _E:
    """实现体只要 env.text + env.save()。"""

    def __init__(self, text=""):
        self.text = text

    def save(self):
        pass


def _drive(fn, p, text=""):
    out = []

    async def go():
        async for line in fn(_E(text), None, "u_q", p):
            out.append(line)

    asyncio.run(go())
    return out


def _player(**kw):
    p = dict(CA.DEFAULT_PLAYER)
    p.update(kw)
    return p


cases = [("副业", ""), ("副业 采集", "采集"), ("副业 垂钓", "垂钓"), ("副业 烹饪", "烹饪"),
         ("副业 强化", "强化"), ("副业 打铁", "打铁")]
trade_out, trade_bad, miss_bad = {}, [], []
for label, arg in cases:
    out = _drive(CQ.trade, _player(level=5), label)
    trade_out[label] = out
    if not out or any(MISSING in ln for ln in out):
        miss_bad.append(label)
    if arg in doc_trades:
        rows = [ln for ln in out if ln.startswith("  ")]      # 带参那屏：抬头 + 每一条一行 + 尾注
        if len(rows) < per.get(arg, 0):
            trade_bad.append((label, len(rows), per.get(arg)))
head = trade_out["副业"]
#: ★ 另一处「拿文案当机器键 grep」（P2-1 车道 2026-09-28 收的）：
#:   原来 `ln.strip().startswith(t)` 直接拿**副业名**当行首去认那一行；P2-1 把并列行
#:   统一成「行首一个 `· `」之后行首不再是那个名 ⇒ 四个副业被数成 **0 行**（判据本身没错，
#:   是取件方式错了）。改成**剥掉行首锚点再认副业名** —— 锚点那一段从 `SYS_TRADE_ROW`
#:   现取（`{trade}` 之前那截），不写死 `·`，措辞再改也不用回来动这条判据。
_TRADE_PFX = (str((TX.get("SYS_TRADE_ROW") or {}).get("value") or "")
              .split("{trade}")[0].strip())


def _trade_line36(ln, t):
    """这一行是副业 `t` 那一行吗（剥掉行首锚点后比对）。"""
    body = ln.strip()
    if not _TRADE_PFX or not body.startswith(_TRADE_PFX):
        return False
    return body[len(_TRADE_PFX):].lstrip().startswith(t)


per_line = sum(1 for ln in head if any(_trade_line36(ln, t) for t in doc_trades))
(ok if not miss_bad and not trade_bad and per_line == 4 else bad)(
    "★ 「副业」真跑：无参那屏四个副业各一行（实测 %d 行）· 四个带参都列得出那条线 · 错参回人话"
    "（取不到文案 %s · 带参异常 %s）" % (per_line, miss_bad or "无", trade_bad or "无"))
print("  · 打样：%s" % " ｜ ".join("%s → %s" % (lb, (trade_out[lb][0][:30] if trade_out[lb] else "(空)"))
                                  for lb, _a in cases))

# ⑱ ★ 生活任务端到端走得通（接 → 交 · 条件拦住 → 补齐 → 交掉）
qid = doc_new8[0][0]
order = QE[qid]["order"]
p1 = _player(level=5, flags={"card": 1})      # ★ B4-27：接活那道门要证（起手档补上，判据没放宽）
acc = _drive(CQ.quest_accept, p1, "接 %d" % order)
blocked = _drive(CQ.quest_deliver, dict(p1), "交 %d" % order)
reqs = QE[qid].get("require") or []
reqs = [reqs] if isinstance(reqs, dict) else reqs
p2 = _player(level=5, gold=0, exp=0, foot={"nodes": {("%s:%s" % (r["map"], r["node"])): 1
                                                   for r in reqs if r.get("kind") == "visit"}},
             bag={r["item"]: max(1, int(r.get("n") or 1)) for r in reqs if r.get("kind") == "item"},
             flags={"quests_active": [qid]})
paid = _drive(CQ.quest_deliver, p2, "交 %d" % order)
done_ok = (p2.get("flags") or {}).get("quests", {}).get(qid, {}).get("done") is True
taken_ok = qid in ((p1.get("flags") or {}).get("quests_active") or []) and any(QE[qid]["name"] in ln for ln in acc)
(ok if taken_ok and any("还没做完" in ln for ln in blocked)
 and not (p1.get("flags") or {}).get("quests_done")
 and any("交了" in ln for ln in paid) and qid in (p2.get("flags") or {}).get("quests_done", [])
 and p2.get("exp") == QE[qid]["reward_exp"] and p2.get("gold") == QE[qid]["reward_gold"] and done_ok else bad)(
    "★ 生活任务端到端（%s · 编号 %d）：接得下（%s）→ 条件没满足时拦住「%s」→ 补齐后交掉"
    "（经验 +%d · 铜板 +%d · flags.quests 写下 done=%s）"
    % (QE[qid]["name"], order, taken_ok, (blocked[0][:14] if blocked else "?"),
       QE[qid]["reward_exp"], QE[qid]["reward_gold"], done_ok))

# ══════════════════════════════════════════════════════════════
# ⑲–㉒ B3-6c 主线三段行文归位 texts（解 P-17 甲案）
#     源：`06_第一阶段垂直切片/24_任务线_v1.md` §一（主线 12 条 · 步骤/交付/教/钩子）
#     ★ 探针**自己**解析那份文档再比（照 ⑬ 对 21 §二 那种做法），不信域的自述。
# ══════════════════════════════════════════════════════════════
import io as _io                                                          # noqa: E402
import re as _re                                                          # noqa: E402

DOC24 = os.path.join(PLAN, "06_第一阶段垂直切片", "24_任务线_v1.md")
_BLK = _re.compile(r"^###\s*主\s*(\d+)\s*·\s*(.+?)\s*$")
_FLD = _re.compile(r"^(步骤|交付|教|★\s*认知推进|钩子)\s+(.*)$")


def _parse_main24():
    """24 §一 → {order: {name, 步骤, 交付, 教, ★认知推进, 钩子, raw}}（解析不出就当场抛）。

    ★ B4-2：**字段会跨行写**（`①…②…` 一行、`③…` 另起一行缩进写 —— 主 2 / 3 / 4 / 7 / 8 /
      9 / 10 / 11 / 12 都这样）⇒ 上一行是字段行、这一行不是空行 / 不是围栏 / 不是新字段，
      就当成它的**续行**接上去。只读第一行会把「③ 水房那页纸」「④ 问艾德」「③ 拿给莉安看」
      这类末步整条丢掉（主线条件正是按这几步落的）。
    """
    if not os.path.exists(DOC24):
        raise SystemExit("24 号文档不在：%s" % DOC24)
    out, cur, last = {}, None, None
    for ln in _io.open(DOC24, encoding="utf-8", newline="").read().split("\n"):
        m = _BLK.match(ln)
        if m:
            cur = out[int(m.group(1))] = {"name": m.group(2).split("（")[0].strip(), "raw": []}
            last = None
            continue
        if cur is None:
            continue
        if ln.startswith("## ") or ln.startswith("---"):
            cur, last = None, None        # §一 结束 / 下一节 —— 别把支线表吃进最后一块
            continue
        cur["raw"].append(ln)
        f = _FLD.match(ln.strip())
        if f:
            last = f.group(1).replace("★ ", "★")
            cur[last] = f.group(2).strip()
            continue
        if last and ln.strip() and not ln.lstrip().startswith("```"):
            cur[last] = (cur[last] + " " + ln.strip()).strip()
    return out


doc24 = _parse_main24()
#: 「锚」= 块里真出现的**专名**（NPC / 怪 / 物 / 图 / 节点名）—— 用来钉「这三条行文是在说本条」
_NAMES = {str(v.get("name")) for d_ in (NPCS, MON, ITEMS) for v in d_.values() if v.get("name")}
for _mm in MAPS.values():
    _NAMES.add(str(_mm.get("name") or ""))
    for _nd in (_mm.get("nodes") or []):
        _NAMES.add(str(_nd.get("name") or ""))
_NAMES = {x for x in _NAMES if len(x) >= 2}
#: 只拿「人 / 怪」当串台哨兵（地名共享是合理的 —— 玩家本来就要到处走）
_PROPER = {str(v.get("name")) for d_ in (NPCS, MON) for v in d_.values() if v.get("name")}

mainq = {int(v["order"]): (k, v) for k, v in QE.items() if v.get("chain") == "main"}

# ⑲ 36 条槽位齐备 · 且都不是占位（「〔待填…〕」「（待写）」「（进行中：…）」）
PLACE = ("待填", "待写", "〔", "（待", "进行中")
slot_miss, slot_place = [], []
for _n in range(1, 13):
    for _part in ("STORY", "PROGRESS", "DELIVER"):
        _key = "QUEST_MAIN%02d_%s" % (_n, _part)
        _v = str((TX.get(_key) or {}).get("value") or "")
        if not _v:
            slot_miss.append(_key)
        elif any(t in _v for t in PLACE):
            slot_place.append((_key, _v[:18]))
(ok if not slot_miss and not slot_place else bad)(
    "★ 主线 36 条槽位齐备且都不是占位（缺 %s · 还是占位 %s）" % (slot_miss or "无", slot_place or "无"))

# ⑳ ★ 12 条主线按 chain+order 真取到槽位 · 与 24 §一 逐条对账（名字 / 锚 / 交付 / 不串台）
recon_bad, recon_lines = [], []
for _n in sorted(doc24):
    if _n not in mainq:
        recon_bad.append("域里没有编号 %d 的主线" % _n)
        continue
    _k, _x = mainq[_n]
    _b = doc24[_n]
    _own = sorted({a for a in _NAMES if a in "\n".join(_b["raw"])})
    _vals = {p: _beat_of(_x, p) for p in ("STORY", "PROGRESS", "DELIVER")}
    _hits = {a for a in _own if any(a in _vals[p] for p in _vals)}
    _need = min(2, len(_own))
    if _x["name"] != _b["name"]:
        recon_bad.append("主%d 名字「%s」≠ 文档「%s」" % (_n, _x["name"], _b["name"]))
    if len(_hits) < _need:
        recon_bad.append("主%d 三条行文只命中 %d/%d 个文档锚 %s" % (_n, len(_hits), _need, _own))
    _dl = {a for a in _own if a in (_b.get("交付") or "")}
    if _dl and not any(a in _vals["DELIVER"] for a in _dl):
        recon_bad.append("主%d 交时那一段没命中「交付」栏的锚 %s" % (_n, sorted(_dl)))
    _cross = sorted(a for a in _PROPER if a not in _own
                    and any(a in _vals[p] for p in _vals))
    if _cross:
        recon_bad.append("主%d 串台（提了别的条才有的人 / 怪）%s" % (_n, _cross))
    recon_lines.append("主%-2d %-7s 锚 %s" % (_n, _b["name"], "/".join(sorted(_hits))))
    if not (_b.get("步骤") and _b.get("交付") and _b.get("钩子")):
        recon_bad.append("主%d 24 号文档那块的 步骤/交付/钩子 没解析全" % _n)
(ok if len(doc24) == 12 and not recon_bad else bad)(
    "★ 主线 12 条与 24 §一 逐条对账（名字 · 三条行文落在本条的锚上 · 交时命中「交付」栏 · 不串台；"
    "坏 %s）" % (recon_bad or "无"))
for _ln in recon_lines:
    print("      %s" % _ln)

# ⑳-b ★ fix-h-small（真人试玩 b59 · 游侠路）：主线 2 的 objective 把玩家指去**图上走不到**的
#      「白烛堂侧屋」——镇图 11 站里没有「侧屋」那一站（实测 `去 白烛堂侧屋` ⇒
#      「这儿没有叫「白烛堂侧屋」的地方。」），而莉安就站在 `白烛堂`（`wt_chapel` =
#      她 `subarea` 那一格，`观察` 的「人在」栏印着她）。
#   判据（**全现算**：站名从 `maps` 取、人名从 `npcs` 取、真源那一行探针自己解析）：
#     ① objective 的第一步那段**逐字** = 「去<莉安真站的那一站>找<莉安>」—— 站名与名字都现算，
#        不手打（改前那句多了「侧屋」两个字 ⇒ 这一条当场红）；
#     ② 「侧屋」不许再出现在 objective 里（站内的子地点 —— 图上走不到）；
#     ③ **真源那一行待主线跟账**（两态互锁 · 第三态红）：`24 §一` 主 2 的「步骤」行
#        **要么**还写着「去白烛堂侧屋找莉安」（未跟账 —— 域里那句是去掉那两个字的版本）·
#        **要么**已经跟账成同一句（域里这句那时与真源逐字同款）；两态都不是 ⇒ 真源被改跑偏了 ⇒ 红。
#        ★ 两态之下**域里那句都是** `去<站>找<人>`：这一格是「玩家照着敲得通」的呈现口径，
#          真源补/删「侧屋」都不改变它（那一行只是叙述莉安住在侧屋 —— 站内的子房间）。
_Q2 = (mainq.get(2) or (None, {}))[1]
_OBJ2 = str(_Q2.get("objective") or "")
#: 域里那一步找的那个人 —— 从**本条自己的 require** 现取（不手打名字）
_TALK2 = next((r for r in CQ._require_of(_Q2) if r.get("kind") == "talk"), {})
_NPC2 = NPCS.get(str(_TALK2.get("npc") or "")) or {}
_LIAN_NM = str(_NPC2.get("name") or "?")
#: 这个人**真站的那一站名** —— `subarea` → `maps` 里的节点名（不写死「白烛堂」）
_LIAN_STOP = next((str(_nd.get("name")) for _m in MAPS.values()
                   for _nd in (_m.get("nodes") or [])
                   if str(_nd.get("id")) == str(_NPC2.get("subarea") or "")), "")
_STEP2 = _re.sub(r"\s+", "", str((doc24.get(2) or {}).get("步骤") or ""))
_WANT2 = "去%s找%s" % (_LIAN_STOP, _LIAN_NM)
_DOC_OLD2 = "去%s侧屋找%s" % (_LIAN_STOP, _LIAN_NM)        # 真源未跟账那一版（多「侧屋」两字）
_FORMS2 = [f for f in (_DOC_OLD2, _WANT2) if f and f in _STEP2]
_obj2_bad = []
if not (_LIAN_NM != "?" and _LIAN_STOP):
    _obj2_bad.append("主 2 的交待那个人 / 他真站的那一站，在 npcs+maps 里算不出来")
if len(_FORMS2) != 1:
    _obj2_bad.append("真源 24 §一 主2 那一行既不是「%s」也不是「%s」（%s）"
                     % (_DOC_OLD2, _WANT2, _STEP2 or "解析不出「步骤」"))
if _OBJ2.split("（")[0] != _WANT2:
    _obj2_bad.append("objective 第一步那段 ≠「%s」：%s" % (_WANT2, _OBJ2.split("（")[0]))
if "侧屋" in _OBJ2:
    _obj2_bad.append("objective 里还写着站内的子地点「侧屋」：%s" % _OBJ2)
(ok if not _obj2_bad else bad)(
    "★ 主 2 的 objective 指的就是那个人真站的那一站（现算 %r）· 子地点「侧屋」不在 objective 里 · "
    "真源 24 §一 那一行 %s（坏 %s）"
    % (_WANT2, "**待主线跟账**（仍写着「%s」）" % _DOC_OLD2
       if _FORMS2 and _FORMS2[0] == _DOC_OLD2 else "**已跟账**", _obj2_bad or "无"))

# ㉑ ★ 真跑「接 <编号>」/「交 <编号>」：槽位里的字必须**原样**出现在屏上（槽位 → 玩家眼睛的闭环）
#   ★ B4-2（P-25 §①）：这一块的**执行**挪到下面（`_sat_player` 定义之后就开跑 —— 见 §㉑ 那一段）。
#     为什么：主线这一批开始有 `require` 了，「交得掉」那一拍得先把条件那条账做上，
#     而造档口 `_sat_player` 在本文件后半段才定义（它要读 recipes / npcs 那几个域）。

# ㉒ 归位总账（**不判红** —— 数字登记 · 判据在 ㉓–㉖）
_lane = {}
for _k, _v in QE.items():
    _lane.setdefault(_v["chain"], []).append(_k)
notes.append("B3-6c + B3-8 归位总账：quests 域 %d 条（主线 %d / 支线 %d / 生活 %d / 悬赏 %d）—— "
             "三段行文真源唯一 = texts 的 %d 条槽位（主线 36 + 支线/生活/悬赏 87）；"
             "域里 `story` / `progress_text` / `deliver_text` 三个内嵌字段 **0 处**"
             % (len(QE), len(_lane.get("main") or []), len(_lane.get("side") or []),
                len(_lane.get("trade") or []), len(_lane.get("bounty") or []),
                3 * len(QE)))

# ══════════════════════════════════════════════════════════════
# ㉓–㉖ B3-8 支线 18 / 生活 8 / 悬赏 3 三段行文归位 texts（同一套映射 · 一次收完）
#      源：`24_任务线_v1.md §二`（支线表 + 悬赏板块）· `28 §四`（新 8 条）+ `21 §二`（奖励）
#          · `05_玩法数值口径_v1.md §一`（悬赏报酬区间）
#      ★ 探针**自己**解析那几份文档再比（照 ⑬ 对 21 §二 / ⑳ 对 24 §一 的做法），不信域的自述。
# ══════════════════════════════════════════════════════════════
DOC05 = os.path.join(PLAN, "06_第一阶段垂直切片", "05_玩法数值口径_v1.md")
_ROW_SIDE = _re.compile(r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$")
_BOUNTY_RANGE = _re.compile(r"报酬\s*(\d+)[–\-~](\d+)（普通）\s*/\s*(\d+)[–\-~](\d+)（精英）"
                            r"\s*/\s*(\d+)[–\-~](\d+)（头目）")
#: 05 §一 的那一行（同一件事的另一份写法）：`悬赏报酬 | 按目标档位：普通 **20–40** 币 · 精英 …`
_BOUNTY_RANGE05 = _re.compile(r"按目标档位：普通\s*\**\s*(\d+)[–\-~](\d+)\s*\**\s*币\s*·\s*"
                              r"精英\s*\**\s*(\d+)[–\-~](\d+)\s*\**\s*·\s*"
                              r"头目\s*\**\s*(\d+)[–\-~](\d+)\s*\**")


def _parse_side24():
    """24 §二 → (支线 rows, 悬赏板块文本)。支线 row = (序号, 名字, 谁给, 步骤, 奖励)。"""
    if not os.path.exists(DOC24):
        raise SystemExit("24 号文档不在：%s" % DOC24)
    lines = [x.rstrip("\r") for x in
             _io.open(DOC24, encoding="utf-8", newline="").read().split("\n")]
    on, rows, blk_at, stop = False, [], None, None
    for i, ln in enumerate(lines):
        if ln.startswith("## 二、"):
            on = True
            continue
        if on and ln.startswith("## 三、"):
            stop = i
            break
        if not on:
            continue
        if ln.startswith("**悬赏板**"):
            blk_at = i
            continue
        if blk_at is None:
            m = _ROW_SIDE.match(ln)
            if m and m.group(1).isdigit() and "---" not in ln:
                rows.append((int(m.group(1)), m.group(2), m.group(3), m.group(4), m.group(5)))
    blk = lines[blk_at:stop] if blk_at is not None else []
    return rows, "\n".join(blk)


side24, bounty_blk = _parse_side24()
side_rows = {r[1]: r for r in side24}
#: 悬赏报酬区间：24 §二 与 05 §一 **两处都要写着**，且必须一致（双源对账）
_b24 = _BOUNTY_RANGE.search(bounty_blk)
_b05 = _BOUNTY_RANGE05.search(_io.open(DOC05, encoding="utf-8", newline="").read()
                              if os.path.exists(DOC05) else "")
_rng = None
if _b24:
    _rng = {"普通": (int(_b24.group(1)), int(_b24.group(2))),
            "精英": (int(_b24.group(3)), int(_b24.group(4))),
            "头目": (int(_b24.group(5)), int(_b24.group(6)))}
(ok if side24 and _rng and _b05 and _b05.groups() == _b24.groups() else bad)(
    "★ 悬赏板真源：24 §二 的报酬区间 %s ＝ 05 §一 的同一条（%s）" %
    (_rng, "两处一致" if _b05 and _b24 and _b05.groups() == _b24.groups() else "对不上"))

side_q = {k: v for k, v in QE.items() if v.get("chain") == "side"}
trade_chain_q = {k: v for k, v in QE.items() if v.get("chain") == "trade"}
bounty_q = {k: v for k, v in QE.items() if v.get("chain") == "bounty"}
#: 串台哨兵只认**人**（NPC 名）—— 地名共享是合理的（支线本来就横跨三带）
_NPC_NAMES = {str(v.get("name")) for v in NPCS.values() if v.get("name")}
LANES = (("支线", "side", side_q, 18, "24 §二"), ("生活", "trade", trade_chain_q, 8, "28 §四"),
         ("悬赏", "bounty", bounty_q, 3, "24 §二 悬赏板"))

# ㉓ ★ 每一条都能按 chain + order 算出**真槽位**（不是哨兵）；域里那三个内嵌字段 0 处
slot_bad, keys29 = [], []
for _kind, _chain, _qs, _want, _src in LANES:
    for _k, _x in _qs.items():
        for _p in ("STORY", "PROGRESS", "DELIVER"):
            _s = CQ._slot_of(_x, _p)
            if str(_s).startswith("QUEST_UNMAPPED"):
                slot_bad.append((_k, _p, _s))
            elif _s not in TX:
                slot_bad.append((_k, _p, "texts 里没有 " + _s))
            else:
                keys29.append(_s)
# 另外两条链（主线 / 后面新加的）也一并钉：**域里每一条**都算得出真槽位
allq_bad = [(k, p) for k, v in QE.items() for p in ("STORY", "PROGRESS", "DELIVER")
            if str(CQ._slot_of(v, p)).startswith("QUEST_UNMAPPED")]
inline = sorted("%s.%s" % (k, f) for k, v in QE.items()
                for f in ("story", "progress_text", "deliver_text") if f in v)
(ok if not slot_bad and not allq_bad and not inline else bad)(
    "★ 29 条按 chain+order 都算得出真槽位（坏 %s）· 域里每一条都不是哨兵（坏 %s）· "
    "那三个内嵌字段 0 处（还有 %s）" % (slot_bad or "无", allq_bad or "无", inline or "无"))

# ㉔ ★ 29 条与三份真源**逐条对账**（名字 · 谁给 · 步骤/内容 · 奖励锚 · 不串台 · 悬赏报酬区间）
_side_ok, _why_side, _lines29 = 0, [], []
_doc28_new = {r[0]: r for r in doc_new8}
_doc21_r = {name: (content, reward) for _t, _w, rows in doc21 for name, content, reward in rows}


def _common(a, b):
    """最长公共子串（打印给人看用 —— 判据就是它的长度；与 ⑬ 那个 `_lcs` 同源）。"""
    a, b = _norm(a), _norm(b)
    row = [0] * (len(b) + 1)
    best = ""
    for i, ca in enumerate(a, 1):
        prev, row = row, [0] * (len(b) + 1)
        for j, cb in enumerate(b, 1):
            if ca == cb:
                row[j] = prev[j - 1] + 1
                if row[j] > len(best):
                    best = a[i - row[j]:i]
    return best


def _anchor(a, b, n=2):
    """共同片段 ≥ n 字（子串判据 —— 文案是照文档写的**行文**，不是文档的抄件 · 与 ⑳ 同款）。"""
    return len(_common(a, b)) >= n


for _kind, _chain, _qs, _want, _src in LANES:
    if len(_qs) != _want:
        _why_side.append("%s 条数 %d ≠ %d" % (_kind, len(_qs), _want))
    for _k, _x in sorted(_qs.items(), key=lambda kv: kv[1]["order"]):
        _3 = "".join(_beat_of(_x, p) for p in ("STORY", "PROGRESS", "DELIVER"))
        _dl = _beat_of(_x, "DELIVER")
        _own = [_x["name"], _x["objective"]]
        _giver = (NPCS.get(_x["giver"]) or {}).get("name") or _x["giver"]
        if _chain == "side":
            _r = side_rows.get(_x["name"])
            if not _r:
                _why_side.append("%s 不在 24 §二 支线表里" % _k)
                continue
            _n, _nm, _who, _steps, _reward = _r
            _own += [_steps, _reward]
            if _who != _giver:
                _why_side.append("%s 谁给「%s」≠ 域 giver「%s」" % (_k, _who, _giver))
            if _norm(_steps) != _norm(_x["objective"]):
                _why_side.append("%s 步骤「%s」≠ objective「%s」" % (_k, _steps, _x["objective"]))
            if _norm(_reward) != _norm(_x.get("hook")):
                _why_side.append("%s 奖励「%s」≠ hook「%s」" % (_k, _reward, _x.get("hook")))
            if not _anchor(_3, _steps):
                _why_side.append("%s 三条行文没落在「步骤」上" % _k)
            if not _anchor(_dl, _reward):
                _why_side.append("%s 交时那一段没落在「奖励」上" % _k)
            _miss = [t for t in _re.findall(r"「([^」]+)」", _reward) if t not in _3]
            if _miss:
                _why_side.append("%s 奖励里的词一个都没落：%s" % (_k, _miss))
        elif _chain == "trade":
            _r = _doc28_new.get(_k)
            if not _r:
                _why_side.append("%s 不在 28 §四 新 8 条里" % _k)
                continue
            _qid, _nm, _tr, _prose, _reward, _who = _r
            _own += [_prose, _reward]
            if _nm != _x["name"] or _tr != _x.get("trade") or _who != _giver:
                _why_side.append("%s 名字/副业/挂谁 与 28 §四 对不上（%s）" % (_k, _r))
            if _norm(_prose) != _norm(_x["objective"]):
                _why_side.append("%s 内容「%s」≠ objective「%s」" % (_k, _prose, _x["objective"]))
            if not _anchor(_3, _prose):
                _why_side.append("%s 三条行文没落在「内容」上" % _k)
            if not _anchor(_dl, _reward):
                _why_side.append("%s 交时那一段没落在「奖励」上" % _k)
            _miss = [t for t in _re.findall(r"「([^」]+)」", _reward) if t not in _3]
            if _miss:
                _why_side.append("%s 奖励里的词一个都没落：%s" % (_k, _miss))
            _a21 = _doc21_r.get(_x["name"])
            if not _a21 or not _recon(_a21[1], _reward):
                _why_side.append("%s 21 §二 奖励与 28 §四 对不上（%s）" % (_k, _a21))
        else:                                   # 悬赏档：真源是 24 §二 悬赏块 + 05 §一
            _tier = _x["name"].split("·")[-1]
            _lo, _hi = (_rng or {}).get(_tier, (0, -1))
            if not (_lo <= int(_x["reward_gold"]) <= _hi):
                _why_side.append("%s 报酬 %d 不在文档区间 %s（%s）"
                                 % (_k, _x["reward_gold"], (_lo, _hi), _x["name"]))
            if _x["name"] != "悬赏·%s" % _tier or _tier not in _x["objective"]:
                _why_side.append("%s 名字/目标与档位对不上：%s" % (_k, _x["objective"]))
        # 串台哨兵：三段行文里只许提**本条文档行里出现过的人**（谁给 / 名字 / 步骤 / 奖励）
        _doc_text = "".join(_own)
        _cross = sorted(n for n in sorted(_NPC_NAMES)
                        if n not in _doc_text and n not in (_giver,) and n in _3)
        if _cross:
            _why_side.append("%s 串台（提了别条的人）%s" % (_k, _cross))
        _side_ok += 1
        _lines29.append("%s %-9s 锚「%s」（%d 字）｜ 交「%s」" % (
            {"side": "支", "trade": "生", "bounty": "赏"}[_chain], _x["name"],
            _common(_3, "".join(_own))[:6], _lcs(_norm(_3), _norm("".join(_own))), _dl[:16]))
#: 悬赏那三条的「交时行文」= 归位前域里的 `deliver_text` **逐字保留**（玩家看到的字一个没动）
_BOUNTY_FROZEN = {"q_bounty_normal": "交了。下次还有。",
                  "q_bounty_elite": "这活儿你接得住。",
                  "q_bounty_boss": "……我没想到你真办到了。"}
_frozen_bad = [(k, _beat_of(QE[k], "DELIVER")) for k, want in _BOUNTY_FROZEN.items()
               if _beat_of(QE.get(k) or {}, "DELIVER") != want]
(ok if not _why_side and not _frozen_bad and _side_ok == 29 else bad)(
    "★ 29 条与真源逐条对账（支线 24 §二 / 生活 28 §四 + 21 §二 / 悬赏 24 §二 悬赏板 + 05 §一）："
    "名字 · 谁给 · 步骤=objective · 奖励锚落在交时 · 不串台（坏 %s）· 悬赏三条交时行文逐字＝归位前"
    "域里那一行（坏 %s）" % (_why_side or "无", _frozen_bad or "无"))
for _ln in _lines29:
    print("      %s" % _ln)

# ㉕ ★ 87 条槽位值都非占位（「待填 / 待写 / 〔 / （待 / 进行中」）+ 与主线同款的硬约束
_place87 = [(s, str((TX.get(s) or {}).get("value"))[:16]) for s in keys29
            if any(t in str((TX.get(s) or {}).get("value") or "") for t in PLACE)]
_digit87 = [s for s in keys29 if _re.search(r"[0-9]", str((TX.get(s) or {}).get("value") or ""))]
_keyleak87 = [s for s in keys29
              if _re.search(r"(q_[a-z_]+|[A-Z][A-Z0-9_]{3,})",
                            str((TX.get(s) or {}).get("value") or ""))]
_dup87 = [s for s in set(keys29)
          if [str((TX.get(x) or {}).get("value")) for x in keys29].count(
              str((TX.get(s) or {}).get("value"))) > 1]
(ok if len(keys29) == 87 and len(set(keys29)) == 87 and not _place87
 and not _digit87 and not _keyleak87 and not _dup87 else bad)(
    "★ 29 条 × 3 = 87 条槽位齐备 · 都不是占位（还是占位 %s）· 无阿拉伯数字（%s）· 无机器键（%s）· "
    "互不重复（%s）" % (_place87 or "无", _digit87 or "无", _keyleak87 or "无", _dup87 or "无"))

def _role_ids_of(role):
    return [k for k, m in MON.items() if not str(k).startswith("_") and m.get("role_key") == role]


# ── ★ g3-quests2：轮换池的**可遇集合**（探针自己算一遍；与实现各写一份）──────────────
def _tier_lv(role):
    """这一档悬赏**自己标的等级**（那条单子的 `min_level`；认不出回 0）—— 从域里现查，不手打。"""
    for _v in QE.values():
        for _r in CQ._require_of(_v):
            if _r.get("kind") == "kill" and str(_r.get("role") or "") == str(role or ""):
                return int(_v.get("min_level") or 0)
    return 0


def _top3(loc, node, level):
    """这一站上「说得上话的怪」按等级最近的前 3（照 `combat.pick_encounter` 那把尺子自己写一遍）。"""
    cand = []
    for _k, _m in MON.items():
        if str(_k).startswith("_"):
            continue
        hb = _m.get("habitat") or {}
        if loc not in (hb.get("maps") or []):
            continue
        ns = hb.get("nodes") or []
        if ns and node not in ns:
            continue
        cand.append(_k)
    cand.sort(key=lambda k: abs(int(MON[k].get("lv", 1)) - level))
    return cand[:3]


def _spots_spec(mid):
    """这只怪 `habitat` 说得上话的**真图真节点**表（照域现算）。"""
    hb = (MON.get(mid) or {}).get("habitat") or {}
    ns = [str(x) for x in (hb.get("nodes") or []) if x]
    out = []
    for m in (hb.get("maps") or []):
        for nd in ((MAPS.get(str(m)) or {}).get("nodes") or []):
            nid = str((nd or {}).get("id") or "")
            if not nid or (ns and nid not in ns):
                continue
            out.append((str(m), nid))
    return out


#: ★ 本波（2026-09-27 · 任务②）：**等级带** —— 探针**自己读**声明表，判据**自己写一遍**
#:   （唯一真源 = `content/rules/level_band.json`；不与实现共用函数 —— 照 ⑬/⑳ 的老规矩）。
_BAND = json.load(io.open(os.path.join(REPO, "content", "rules", "level_band.json"),
                          encoding="utf-8"))
_BAND_MAX = int(_BAND["max_level_diff"]["value"])


def _in_band(lv_mon, lv_ref):
    """|怪的等级 − 参照等级| ≤ 带宽 ⇒ 带内（悬赏那一档的参照 = 单子自己的 `min_level`）。"""
    return abs(int(lv_mon) - int(lv_ref)) <= _BAND_MAX


def _pool_spec(role):
    """★ 这一档的**可遇集合**（规格 · 探针自己算）：该档的怪里，按该档 `min_level`
    —— ① 在它 `habitat` 写明的**每一站**上都进得了「等级最近前 3」（旧尺子）；
      ② **且落在等级带内**（`_in_band`，本波加的：差 > 带宽 ⇒ 不进池 —— 病灶是「只有 3 只怪的
         站上前 3 = 全部 ⇒ 等于没筛」，1 级档点到 lv9 石滩螃蟹、5 级档点到 lv13 水里的东西）
    —— 按 id 排序。两半都**不带玩家当前等级**（池要按日稳定：`_tier_lv` = 该档标称等级）。"""
    lv = _tier_lv(role)
    out = []
    for mid in _role_ids_of(role):
        spots = _spots_spec(mid)
        if lv <= 0 or not spots or not _in_band(MON[mid].get("lv"), lv):
            continue
        if all(mid in _top3(_l, _n, lv) for _l, _n in spots):
            out.append(mid)
    return sorted(out)


def _pool_spec_no_band(role):
    """**只按旧尺子**的可遇集合（本波反证用：拿掉「等级带」这一半 ⇒ 应当点名到带外那一只）。"""
    lv = _tier_lv(role)
    out = []
    for mid in _role_ids_of(role):
        spots = _spots_spec(mid)
        if lv <= 0 or not spots:
            continue
        if all(mid in _top3(_l, _n, lv) for _l, _n in spots):
            out.append(mid)
    return sorted(out)


def _pick_of(role, day):
    """★ 轮换的**规格**（探针自己实现一遍）：该档的**可遇集合**按 id 排序，取第 `(游戏日-1)%n+1` 只。

    ★ g3-quests2：池子从「该档全部怪」收窄成「可遇集合」（见 `_pool_spec`）—— 轮换算法一个字没变。
    与 `cmds_quest._daily_pick` **各写一遍**（共用一份等于把两处的错一起掩盖 —— 照 ⑬/⑳ 的老规矩）。
    """
    ids = _pool_spec(role)
    return ids[(int(day) - 1) % len(ids)] if ids else ""


def _cook_recs(quality="", known_only=False):
    """能顶这个 `cook` 条件的配方（探针自己挑：`kind_key == cook` + 用了那一品阶的食材）。

    ★ `known_only`：只要**不用先交别条任务**就会做的那些（`learn` 没写 / 不挂委托）。
      为什么必须有这一档：配方「一锅炖」的 `learn` 就是 **q_side_06 自己**（交掉才学会）——
      拿它去顶 q_side_06 的条件就是**循环**；这一档把「只能靠本条自己锁着的配方」当场标出来。
    """
    out = []
    for rid, rec in RC.items():
        if str(rid).startswith("_") or rec.get("kind_key") != "cook":
            continue
        if known_only:
            learn = rec.get("learn")
            if isinstance(learn, dict) and learn.get("quest"):
                continue
        if quality:
            hit = False
            for e in (rec.get("inputs") or []):
                iid = str(e.get("id") or "")
                if str((ITEMS.get(iid) or {}).get("quality") or "") == quality:
                    hit = True
            if not hit:
                continue
        out.append(rid)
    return sorted(out)


def _talked_rec(r):
    """`talk` / `ask` 两种条件 → 档上 `flags.talked` 该长什么样（探针自己按 npc 域推）。"""
    k = r.get("kind")
    n = max(1, int(r.get("n") or 1))
    if k == "talk":
        dlg = str((NPCS.get(str(r.get("npc"))) or {}).get("dialogue") or "")
        return ({dlg: n} if dlg else {})
    if k == "ask":
        ds = sorted((v.get("dialogue") or "") for v in NPCS.values() if v.get("dialogue"))
        return {d: 1 for d in ds[:n]}
    return {}


# ㉖ ★ 三类各真跑一遍：接 / 交(没做完) / 交 —— 槽位里的字必须**逐字**出现在屏上
_drive3, _drive3_lines = [], []
#: ★ B3-13：悬赏那一条的条件带 `daily`（当天点名的那一只）⇒ 探针按**规格自己算出**那一天的那只
#:   （共用实现的函数等于把两处的错一起掩盖；这里另写一遍 `_pick_of`）
_B_DAY = 3
_DRIVE = (("支线", "q_side_02", "item", {"bag": {"i_material_old_iron": 1}}),
          ("生活", "q_trade_02", "visit+item",
           {"foot": {"nodes": {"belt_north:bn_tower": 1}}, "bag": {"i_material_iron_scrap": 1}}),
          # ★ B3-11：悬赏的「做到」从**旧 flag**（`flags.side_悬赏·普通` —— 那个键没人写）改成
          #   **真的打掉过一只普通档的怪**（`books.monster` 那本谱的击杀账，codex.note_kill 写的）
          # ★ B3-13：再收窄成**那天点名的那一只**（见 `_pick_of`）
          ("悬赏", "q_bounty_normal", "kill@role+daily",
           {"books": {"monster": {_pick_of("normal", _B_DAY): {"day": _B_DAY, "kills": 1}}},
            "day": _B_DAY}))
for _kind, _k, _shape, _fix in _DRIVE:
    _x = QE[_k]
    _n = int(_x["order"])
    _lv = int(_x["min_level"])
    _acc = _drive(CQ.quest_accept, _player(level=_lv, flags={"card": 1}), "接 %d" % _n)
    _nod = _drive(CQ.quest_deliver, _player(level=_lv, flags={"quests_active": [_k]}), "交 %d" % _n)
    _flags = {"quests_active": [_k]}
    _flags.update({k: v for k, v in _fix.items() if k == "flags"}.get("flags", {}) or {})
    _p2 = _player(level=_lv)
    _p2.update({k: v for k, v in _fix.items() if k != "flags"})
    _p2["flags"] = _flags
    #: ★ B4-9：条件里带 `daily`（当天点名的那一只）看的是**那根钟** —— 档上写了「第 N 日」
    #:   就顺带拨钟（判据没变：那一天的规格仍由探针自己算）。这一档用完拨回真钟。
    _day_fix = int(_fix.get("day") or 0)
    if _day_fix:
        _at_day(_day_fix)
    _pay = _drive(CQ.quest_deliver, _p2, "交 %d" % _n)
    if _day_fix:
        FC_Q.bind_host(**_FC_SAVED)
    _want = {p: _beat_of(_x, p) for p in ("STORY", "PROGRESS", "DELIVER")}
    if _want["STORY"] not in _acc:
        _drive3.append((_k, "接", _acc[:2]))
    if not any(ln.startswith("还没做完") and _want["PROGRESS"] in ln for ln in _nod):
        _drive3.append((_k, "交(没做完)", _nod[:2]))
    if _want["DELIVER"] not in _pay or _k not in (_p2.get("flags") or {}).get("quests_done", []):
        _drive3.append((_k, "交", _pay[:3]))
    if any(MISSING in ln for ln in _acc + _nod + _pay):
        _drive3.append((_k, "取不到文案", ""))
    _drive3_lines.append("%s %s（编号 %d）接「%s」｜ 没做完「%s」｜ 交「%s」"
                         % (_kind, _x["name"], _n, _want["STORY"][:14],
                            _want["PROGRESS"][:12], _want["DELIVER"][:14]))
(ok if not _drive3 and len(_drive3_lines) == 3 else bad)(
    "★ 支线 / 生活 / 悬赏 各抽一条真跑：接 / 交(没做完) / 交 三拍的字逐字在屏上、奖励入档"
    "（坏 %s）" % (_drive3 or "无"))
for _ln in _drive3_lines:
    print("      %s" % _ln)

# ══════════════════════════════════════════════════════════════
# ㉗–㉘ B3-11 悬赏三档的**数值口径** · 支线的**交付真跑矩阵**
#      源：`05_玩法数值口径_v1.md §一` + `24_任务线_v1.md §二 悬赏板`（报酬区间 + 「经验 = 同级需求
#         的 N/D」）· `00_第一阶段内容总纲_v1.md §七`（升级曲线 —— 真源，包内唯一口 `exp_need`）
#          · `15_彩蛋域口径_v1.md §二`（支线交付条件的另一处真源）
#      ★ 照 ⑬/⑳/㉔ 的老规矩：**探针自己解析文档**（不与生成器共用镜像表 —— 共用会把两处的错
#        一起掩盖）；文档一改，判据跟着变。
# ══════════════════════════════════════════════════════════════
#: 悬赏经验占比：05 §一 与 24 §二 各写一遍（「同级需求的 N/D」/「同级升级需求的 N/D」）—— 必须一致
_BOUNTY_EXP = _re.compile(r"经验\s*=\s*同级(?:升级)?需求的\s*(\d+)\s*/\s*(\d+)")
_d05 = _io.open(DOC05, encoding="utf-8", newline="").read() if os.path.exists(DOC05) else ""
_e05 = _BOUNTY_EXP.search(_d05)
_e24 = _BOUNTY_EXP.search(bounty_blk)
_bn_bad, _bn_lines, _num, _den = [], [], 0, 0
if not _e05 or not _e24:
    _bn_bad.append("经验占比解析不出（05 §一 %s · 24 §二 %s）" % (bool(_e05), bool(_e24)))
elif _e05.groups() != _e24.groups():
    _bn_bad.append("★ 两处真源打架：05 §一 %s/%s vs 24 §二 %s/%s"
                   % (_e05.group(1), _e05.group(2), _e24.group(1), _e24.group(2)))
else:
    _num, _den = int(_e05.group(1)), int(_e05.group(2))

# ── ㉗ ★ 悬赏三档：经验 = 该档等级的升级需求 × N/D（逐条算）· 钱落在文档区间里（逐条核）
for _k, _x in sorted(bounty_q.items(), key=lambda kv: kv[1]["order"]):
    _tier = _x["name"].split("·")[-1]
    _need_ = exp_need(_x["min_level"])
    _want = (_need_ * _num // _den) if _den else -1
    _lo, _hi = (_rng or {}).get(_tier, (0, -1))
    _rng_ok = _lo <= int(_x["reward_gold"]) <= _hi
    if _x["reward_exp"] != _want:
        _bn_bad.append("%s 经验 %s ≠ 需求 %d × %d/%d = %d（手打的数？）"
                       % (_k, _x["reward_exp"], _need_, _num, _den, _want))
    if not _rng_ok:
        _bn_bad.append("%s 报酬 %s 跑出文档区间 %s" % (_k, _x["reward_gold"], (_lo, _hi)))
    _bn_lines.append("赏 %-7s 编号 %-4d 等级 %-3d 升级需求 %-5d × %d/%d = %-4d（域 %-4d ✓）"
                     "｜ 报酬 %-4d ∈ [%d,%d]（区间中点 %d）"
                     % (_x["name"], _x["order"], _x["min_level"], _need_, _num, _den, _want,
                        _x["reward_exp"], int(_x["reward_gold"]), _lo, _hi, (_lo + _hi) // 2))
(ok if not _bn_bad else bad)(
    "★ 悬赏三档的经验/钱与真源逐条对账（经验 = 同级升级需求 × %d/%d，走包内唯一口 `exp_need`；"
    "钱落在 24 §二 ＝ 05 §一 的区间里；坏 %s）" % (_num, _den, _bn_bad or "无"))
for _ln in _bn_lines:
    print("      %s" % _ln)

# ── ㉘ ★ 18 条支线的交付**真跑矩阵**：能交的当场真交一次；不能交的钉住名单 + 逐条原因
#   ★ 「交得掉」的判法：造一个**满足它 require** 的档 → 接 → 交，屏上出现「交了」且 `flags.quests_done`
#     记上。★ 「交不掉」的判法：再造一个**万事俱备**的档（满级 + 全图全节点 + 所有物品 + 所有怪各 99
#     只 —— 凡是 visit/item/kill 三型表达得出来的，这个档都满足）→ 仍然被拦 ⇒ 证明它看的不是条件，
#     而是 `flags.side_<名字>` 那个**没人写**的键（P-25 §② 的根因，可复现）。
_SHAPE_OF = {"visit": "「去过某处」", "item": "「手上有某物」",
             "kill": "「打过某只怪 / 某一档的怪」",
             # ★ B3-13 四型（账都在现有档上 —— 形状名只是给人看的那一栏）
             "enhance": "「有一件装备强化到某一级」", "cook": "「下过锅 N 次」",
             "talk": "「跟某人搭过 N 次话」", "ask": "「搭过话的人有 N 个」"}
#: ★ 今天交不掉的支线**钉住名单**（B4-27：从 5 条压到 4 条）—— 名单一变当场红：
#:   少一条（有人把它修好了）要**故意**从这儿删掉，多一条（新死的）立刻红。
#:   ★ 这 4 条的根因都是**内容/形状缺**（不是代码漏判）—— 逐条「要补进真源的行」写在工作树
#:     `_notes.md`；补上之后照 支 7 那条的办法（生成器 + 探针各写一条从文档现解析的规则）落。
_DEAD_SIDE = {
    "q_side_10": "「陪一个 NPC 走一段（送信）」—— 信这个物品域里不存在，且**目的地文档没写**"
                 "（没目的地落不了 `visit`；「陪一段」本身也没有形状）",
    "q_side_11": "「查他酒钱从哪来」—— 要「线索 / 隐藏线 flag」这种形状（隐藏线「号角」口径未落）",
    "q_side_12": "「（间接）找到那个名字」—— 同上（隐藏线「名字」口径未落）",
    "q_side_18": "「按他的口味做一道菜」——「一道菜」这半截能查（`cook`），但**「他的口味」是哪一品阶 / "
                 "哪一道，文档一个字没写** ⇒ 落成「做过任意一道菜」等于没查「他的口味」（等裁决，"
                 "见工作树 `_notes.md`）",
}


def _kills_rec(r, n, day=1):
    """条件 → 档上那本怪物谱该长什么样（点名那只 / 点那一档里今天的**那一只**）。"""
    mid = str(r.get("monster") or "")
    if not mid:
        role = str(r.get("role") or "")
        ids = _role_ids_of(role)
        mid = _pick_of(role, day) if r.get("daily") else (ids[0] if ids else "")
    return ({mid: {"day": day, "kills": n}} if mid else {})


def _sat_player(x, qid, day=1, skip=None):
    """造一个**满足这条 require** 的档（每一型各按自己的账造 —— 不猜）。

    ★ B4-2：`skip=<第几条>` ⇒ **故意少做那一条**（其余照做）—— 主线的「缺一步交不掉」矩阵
      就靠它逐条复现（不许靠「整体不满足」糊过去）。
    """
    p = _player(level=max(1, int(x["min_level"])))
    foot, bag, mon, enh, talked, cooked = {}, {}, {}, {}, {}, {}
    for _i, r in enumerate(CQ._require_of(x)):
        if skip is not None and _i == skip:
            continue
        k = r.get("kind")
        if k == "visit":
            foot["%s:%s" % (r.get("map"), r.get("node"))] = 1
        elif k == "item":
            bag[str(r.get("item"))] = max(1, int(r.get("n") or 1))
        elif k == "kill":
            mon.update(_kills_rec(r, max(1, int(r.get("n") or 1)), day))
        elif k == "enhance":
            n = max(1, int(r.get("n") or 1))
            enh["_probe_gear"] = {"lv": n, "bonus": 0.0}
        elif k == "cook":
            n = max(1, int(r.get("n") or 1))
            recs = _cook_recs(str(r.get("quality") or ""), known_only=True)
            cooked[recs[0] if recs else "_probe_dish"] = n
        elif k in ("talk", "ask"):
            talked.update(_talked_rec(r))
    if foot:
        p["foot"] = {"nodes": foot}
    if bag:
        p["bag"] = bag
    if mon:
        p["books"] = {"monster": mon}
    if enh:
        p["enhance"] = enh
    p["day"] = int(day)                       # ★ B3-13：轮换看这一格（同一日同档同结果）
    p["flags"] = {"quests_active": [qid], "talked": talked, "cooked": cooked}
    return p


_SATIATED = {}


def _satiated(qid):
    """万事俱备的档（同一份骨架只造一次；`_p()` 会把四个可变容器拷一层，改不到它）。"""
    if not _SATIATED:
        nodes = {"%s:%s" % (m, nd["id"]): 1 for m, mv in MAPS.items()
                 for nd in (mv.get("nodes") or [])}
        bag = {k: 99 for k in ITEMS if not str(k).startswith("_")}
        bag.update({k: 99 for k in DP if not str(k).startswith("_")})
        _SATIATED["v"] = {"foot": {"nodes": nodes}, "bag": bag,
                          "books": {"monster": {k: {"day": 1, "kills": 99} for k in MON
                                                if not str(k).startswith("_")}}}
    p = _player(level=99)
    p.update(json.loads(json.dumps(_SATIATED["v"])))
    p["flags"] = {"quests_active": [qid]}
    return p


# ══════════════════════════════════════════════════════════════
# ㉑ ★ 真跑「接 <编号>」/「交 <编号>」：槽位里的字必须**原样**出现在屏上（槽位 → 玩家眼睛的闭环）
#   ★ B4-2：这一块的**执行**挪到这儿（原在 ⑲ 那一段后面）—— 「交得掉」那一拍必须先造出
#     满足 `require` 的档，而造档口 `_sat_player` 在上面才定义（它要读 recipes / npcs 那几个域）。
#   ★ 顺手加严（P-25 §①）：**等级够了、目标那几步一步没做**也必须拦住，且「还差…」得把
#     缺的**每一条**都点出来（条数 = 未满足的条件条数）—— 「1 级接 1 级主线，一句『交 1』就过」
#     这条路当场钉死。
drive_bad, drive_lines = [], []
for _n in range(1, 13):
    _k, _x = mainq[_n]
    _lv = int(_x["min_level"])
    _want = {p: _beat_of(_x, p) for p in ("STORY", "PROGRESS", "DELIVER")}
    _reqs = CQ._require_of(_x)
    _acc = _drive(CQ.quest_accept, _player(level=_lv, flags={"card": 1}), "接 %d" % _n)
    # ① 等级不够那档（老口径）：压到门槛之下（主 1 的门槛就是 1 ⇒ 用 0 —— 别拿 1 当「不够」）
    _nod = _drive(CQ.quest_deliver, _player(level=max(0, _lv - 1), flags={"quests_active": [_k]}),
                  "交 %d" % _n)
    # ② ★「接了就交」那档：等级够了、目标那几步一步没做
    _idle = _player(level=_lv, flags={"quests_active": [_k]})
    _idle_out = _drive(CQ.quest_deliver, _idle, "交 %d" % _n)
    # ③ 万事俱备那档：条件逐条做上（账走 `_sat_player`）
    _full = _sat_player(_x, _k)
    _pay = _drive(CQ.quest_deliver, _full, "交 %d" % _n)
    if _want["STORY"] not in _acc:
        drive_bad.append((_n, "接", _acc[:2]))
    if not any(ln.startswith("还没做完") and _want["PROGRESS"] in ln for ln in _nod):
        drive_bad.append((_n, "交(没做完)", _nod[:2]))
    if not any(ln.startswith("还没做完") for ln in _idle_out) \
            or _k in ((_idle.get("flags") or {}).get("quests_done") or []):
        drive_bad.append((_n, "★ 接了就交（等级够 + 一步没做，竟然交掉了）", _idle_out[:3]))
    _lack21 = [ln for ln in _idle_out if "还差" in ln]
    if len(_lack21) != len(_reqs):
        drive_bad.append((_n, "「还差…」说了 %d 条（条件 %d 条）" % (len(_lack21), len(_reqs)),
                          _idle_out[:4]))
    if _want["DELIVER"] not in _pay:
        drive_bad.append((_n, "交", _pay[:3]))
    if any(MISSING in ln for ln in _acc + _nod + _idle_out + _pay):
        drive_bad.append((_n, "取不到文案", ""))
    drive_lines.append("主%-2d 接「%s…」｜ 没做完「%s…」｜ 接了就交「拦住 · 还差 %d 条」｜ 交「%s…」"
                       % (_n, _want["STORY"][:12], _want["PROGRESS"][:10], len(_lack21),
                          _want["DELIVER"][:12]))
(ok if not drive_bad else bad)(
    "★ 主线 12 条真跑四拍：接 / 交(没做完) / 交(等级够但一步没做 · 拦住) / 交(万事俱备) —— "
    "槽位里的字逐字在屏上（坏 %s）" % (drive_bad or "无"))
for _ln in drive_lines:
    print("      %s" % _ln)

# ══════════════════════════════════════════════════════════════
# ㉜ ★ B4-2（P-25 §①）：主线**逐步记账** —— 条件从 24 §一 的「步骤」行来 · 缺一步交不掉
#   改前 `_obj_ok` 对主线只看 `level >= min_level`（1 级接 1 级主线，一句「交 1」就过，
#   「观察 → 看见石头上的字 → 试着读 → 问玛莎」一步都不用做）。四条判据：
#     ① 12 条主线**每一条都写了 `require`**（一条不落）
#     ② 每条条件的**目标**（人 / 站 / 图 / 怪 / 物）在**本条自己的**「步骤」行里点了名
#        （探针现解析 24 §一，含续行；与 ⑳ 的锚判据同款：最长公共片段 ≥ 2 字）
#        —— 条件是从这一条的文档推出来的，不是从别条串台凑的
#     ③ 「缺一步」矩阵：对每条条件各造一个**只差这一条**的档 ⇒ 必须拦住
#        （逐条证明「每一步都要做」；不许拿「整体没做」糊过去）
#     ④ 「万事俱备」那档：交得掉 + 奖励入档 + `flags.quests[<id>]` 写下 `done` 与
#        `step == 条件条数`（那就是「逐步记账」那本账）
_main_bad, _main_lines = [], []


def _tg_names(r):
    """条件指向的东西在**域里**的名字（给文档锚用；认不出的回空串，那种要人工看一眼）。"""
    k = r.get("kind")
    if k == "visit":
        mp, nd = str(r.get("map") or ""), str(r.get("node") or "")
        if nd:
            for n in ((MAPS.get(mp) or {}).get("nodes") or []):
                if str(n.get("id")) == nd:
                    return [str(n.get("name") or nd)]
            return [nd]
        return [str((MAPS.get(mp) or {}).get("name") or mp)]
    if k == "kill":
        return [str((MON.get(str(r.get("monster") or "")) or {}).get("name") or r.get("monster"))]
    if k == "item":
        return [str((ITEMS.get(str(r.get("item") or "")) or {}).get("name") or r.get("item"))]
    if k == "talk":
        return [str((NPCS.get(str(r.get("npc") or "")) or {}).get("name") or r.get("npc"))]
    return []


def _belts_ctx():
    """「三条带」= 地图名里带「带」字的那几张（与生成器各写各的 —— 两边都从 maps 域现取）。"""
    return sorted(k for k, v in MAPS.items()
                  if not str(k).startswith("_") and "带" in str(v.get("name") or ""))


for _n in sorted(mainq):
    _k, _x = mainq[_n]
    _reqs = CQ._require_of(_x)
    _steps = _re.sub(r"\s+", "", str((doc24.get(_n) or {}).get("步骤") or ""))
    if not _steps:
        _main_bad.append("主%d：24 §一 那块解析不出「步骤」（续行接上之后还是空）" % _n)
    if not _reqs:
        _main_bad.append("主%d「%s」没写 require —— 还是「接了就交」" % (_n, _x["name"]))
        continue
    # ② 文档锚（逐条）
    _beltvis = [str(r.get("map")) for r in _reqs
                if r.get("kind") == "visit" and not r.get("node")]
    if len(_beltvis) >= 2:
        _belts = _belts_ctx()
        if "三条带" not in _steps or _beltvis != _belts:
            _main_bad.append("主%d：图级条件 %s 与文档那句「三条带」对不上（域里 %s）"
                             % (_n, _beltvis, _belts))
    else:
        for _r in _reqs:
            for _nm in _tg_names(_r):
                if len(_common(_nm, _steps)) < 2:
                    _main_bad.append("主%d 的条件 %s 指向「%s」—— 本条「步骤」行里找不到它的名字"
                                     % (_n, json.dumps(_r, ensure_ascii=False), _nm))
    # ③ 「缺一步」矩阵：逐条少做那一件 ⇒ 必须拦住
    for _i, _r in enumerate(_reqs):
        _near = _sat_player(_x, _k, skip=_i)
        _out = _drive(CQ.quest_deliver, _near, "交 %d" % _n)
        if any(ln.startswith("交了") for ln in _out) \
                or _k in ((_near.get("flags") or {}).get("quests_done") or []):
            _main_bad.append("主%d：缺第 %d 条（%s）竟然也交得掉"
                             % (_n, _i + 1, json.dumps(_r, ensure_ascii=False)))
        elif not any(ln.startswith("还没做完") for ln in _out):
            _main_bad.append("主%d：缺第 %d 条时没说「还没做完」：%s" % (_n, _i + 1, _out[:2]))
    # ④ 万事俱备 ⇒ 交得掉 + 奖励入档 + 逐步记账那本账
    _full = _sat_player(_x, _k)
    _exp0, _gold0 = int(_full.get("exp") or 0), int(_full.get("gold") or 0)
    _pay = _drive(CQ.quest_deliver, _full, "交 %d" % _n)
    _rec = (((_full.get("flags") or {}).get("quests") or {}).get(_k) or {})
    if not any(ln.startswith("交了") for ln in _pay) \
            or _k not in ((_full.get("flags") or {}).get("quests_done") or []):
        _main_bad.append("主%d「%s」万事俱备却交不掉：%s" % (_n, _x["name"], _pay[:3]))
    if _rec.get("done") is not True:
        _main_bad.append("主%d：交掉了但 flags.quests[%s].done 不是 true（%s）" % (_n, _k, _rec))
    if int(_rec.get("step") or -1) != len(_reqs):
        _main_bad.append("主%d：flags.quests[%s].step = %s ≠ 条件条数 %d"
                         % (_n, _k, _rec.get("step"), len(_reqs)))
    _de, _dg = int(_full.get("exp") or 0) - _exp0, int(_full.get("gold") or 0) - _gold0
    if _de != int(_x["reward_exp"]) or _dg != int(_x["reward_gold"]):
        _main_bad.append("主%d：奖励没照单入档（经验 %+d 应是 +%d · 铜板 %+d 应是 +%d）"
                         % (_n, _de, _x["reward_exp"], _dg, _x["reward_gold"]))
    if any(MISSING in ln for ln in _pay):
        _main_bad.append("主%d：有取不到文案的行" % _n)
    _main_lines.append("主%-2d %-7s 条件 %d 条（%s）→ 缺一条：拦住 · 全满足：交了 "
                       "（step %s/%d · 经验 +%d 铜板 +%d）"
                       % (_n, _x["name"], len(_reqs),
                          "/".join(str(r.get("kind")) for r in _reqs),
                          _rec.get("step"), len(_reqs), _x["reward_exp"], _x["reward_gold"]))
(ok if len(mainq) == 12 and not _main_bad else bad)(
    "★ 主线 12 条**逐步记账**：每条都写了 require · 每条条件都有本条「步骤」行的锚 · "
    "**缺一步交不掉**（逐条矩阵）· 万事俱备交得掉且 flags.quests 写下 step=条件条数（坏 %s）"
    % (_main_bad or "无"))
for _ln in _main_lines:
    print("      %s" % _ln)

# ══════════════════════════════════════════════════════════════
# ㉟ ★ B4-27 ①（P-25 §① 那一条的收口）：主线交活 = **等级 + 逐步记账**（B4-2 已落）
#   本批按**条目身份** grep 消费者复核之后，把结论钉成机器可验（台账那半句「主线交活只判等级」
#   **已经过期** —— B4-2 落了 require、`_obj_ok` 主线那一支已是 `level >= min_level` **且**
#   逐条 `_req_ok`；台账会过期，所以判据不能只写在注释里）：
#     ① 等级那一半**单独**是载重的：万事俱备（条件全做上）但等级压在门槛之下 ⇒ 照样拦住、
#        档一个字不动；同一个档把等级抬回门槛 ⇒ 立刻交得掉（差别**只**在等级）——
#        把那半摘掉就当场红
#     ② 逐步记账那一半：与支线走的是**同一条判定**（`all(_req_ok(...))`）—— 按条钉在 ㉜
#        （每条都写了 require + 缺一步矩阵）
#     ③ 每条条件的**途径都存在**（与支线 ⑮ / ㉚ 同一把尺子）：`visit` 的图与节点在 maps 域里 ·
#        `kill` 的怪在 monsters 域里 · `item` 在 items 域里且**有出产渠道**（采集 / 掉落 / 配方
#        三处汇总，探针自己重算）· `talk` 的人挂着对话树 —— 一条做不到的条件 = 这条主线永远交不掉
#     ④ 静态守卫：`_obj_ok` 主线那一支**必须两半都在**（`min_level` 与 `_req_ok`）——
#        「接了就交」与「等级变唯一判据」两个方向都堵死
# ══════════════════════════════════════════════════════════════
_lv_bad, _lv_lines = [], []
for _n in sorted(mainq):
    _k, _x = mainq[_n]
    # ① 等级那一半：条件全做上、等级压到门槛之下 ⇒ 拦住且档不动；抬回门槛 ⇒ 交得掉
    _low = _sat_player(_x, _k)
    _low["level"] = int(_x["min_level"]) - 1
    _lv_out = _drive(CQ.quest_deliver, _low, "交 %d" % _n)
    if any(ln.startswith("交了") for ln in _lv_out) \
            or _k in ((_low.get("flags") or {}).get("quests_done") or []):
        _lv_bad.append("主%d：等级压到 %d（门槛 %d）竟然交得掉 —— 等级那一半不在载重"
                       % (_n, _low["level"], _x["min_level"]))
    elif not any(ln.startswith("还没做完") for ln in _lv_out):
        _lv_bad.append("主%d：等级不够时没说「还没做完」：%s" % (_n, _lv_out[:2]))
    _full1 = _sat_player(_x, _k)
    _full1["level"] = int(_x["min_level"])
    _pay1 = _drive(CQ.quest_deliver, _full1, "交 %d" % _n)
    if not any(ln.startswith("交了") for ln in _pay1):
        _lv_bad.append("主%d：等级刚够（%d）也交不掉：%s" % (_n, _x["min_level"], _pay1[:2]))
    _lv_lines.append("主%-2d 门槛 %-2d：等级 %-2d（门槛下）拦住 · 等级 %-2d 交得掉 → 「%s…」"
                     % (_n, _x["min_level"], int(_x["min_level"]) - 1, _x["min_level"],
                        next((ln for ln in _pay1 if ln.startswith("交了")), "?")[:14]))
    # ③ 条件途径存在（一把一个 kind）
    for _r in CQ._require_of(_x):
        _kind = _r.get("kind")
        if _kind == "visit":
            _mv = MAPS.get(str(_r.get("map")))
            if not _mv:
                _lv_bad.append("主%d：要去的图 %s 不在 maps 域里" % (_n, _r.get("map")))
            elif _r.get("node") \
                    and str(_r["node"]) not in [x["id"] for x in (_mv.get("nodes") or [])]:
                _lv_bad.append("主%d：要去的节点 %s 不在图 %s 里"
                               % (_n, _r.get("node"), _r.get("map")))
        elif _kind == "kill":
            if str(_r.get("monster")) not in MON:
                _lv_bad.append("主%d：要打的怪 %s 不在 monsters 域里" % (_n, _r.get("monster")))
        elif _kind == "item":
            _iid = str(_r.get("item"))
            if _iid not in ITEMS and not (_iid.startswith("unid_") and _iid in DP):
                _lv_bad.append("主%d：要拿的 %s 不在 items 域里" % (_n, _iid))
            elif _iid not in produced:
                _lv_bad.append("主%d：要拿的 %s **没有任何出产渠道**（采集 / 掉落 / 配方都没有）"
                               "⇒ 这条主线永远交不掉" % (_n, _iid))
        elif _kind == "talk":
            if not (NPCS.get(str(_r.get("npc"))) or {}).get("dialogue"):
                _lv_bad.append("主%d：要搭话的 %s 没挂对话树" % (_n, _r.get("npc")))
        else:
            _lv_bad.append("主%d：条件 kind「%s」不在主线用的那一族里（visit/kill/item/talk）"
                           % (_n, _kind))
# ④ 静态守卫：`_obj_ok` 主线那一支必须两半都在（`min_level` 与 `_req_ok`）
#   ★ g3-quests2：本守卫原先在全文件里找**第一行** `return …min_level…` —— 那时它是 `_obj_ok`
#     那一行；本波 `cmds_quest` 里多了一处同样带 `min_level` 的 `return`（`_tier_level`，
#     与 `_obj_ok` 无关）⇒ 守卫会在**别人的函数**里找。判据一个字没松：**只把取行范围收窄到
#     `_obj_ok` 这个函数体内**（它要钉的本来就是那一支）。
_cq_lines = io.open(os.path.join(REPO, "content", "cmds_quest.py"),
                    encoding="utf-8").read().split("\n")
_a4 = next((i for i, _s in enumerate(_cq_lines) if _s.startswith("def _obj_ok(")), None)
_b4 = next((i for i in range((_a4 or 0) + 1, len(_cq_lines))
            if _cq_lines[i].startswith("def ")), len(_cq_lines))
_m_line = next((_s for _s in _cq_lines[(_a4 or 0):_b4]
                if _s.strip().startswith("return") and "min_level" in _s), "") if _a4 is not None else ""
if not _m_line or "_req_ok" not in _m_line:
    _lv_bad.append("_obj_ok 主线那一支不再两半都在（读到的是「%s」）" % _m_line.strip())
(ok if not _lv_bad else bad)(
    "★ P-25 §① 主线交活那一半（B4-2 已收口 · 台账那半句已过期）：**等级 + 逐步记账两条都在载重**"
    "（万事俱备但等级压在门槛下 ⇒ 拦住且档原样 · 抬回门槛 ⇒ 交掉）· 每条条件的**途径都存在**"
    "（图/节点 · 怪 · 物有出产渠道 · 对话树 —— 与支线 ⑮/㉚ 同一把尺子）· `_obj_ok` 主线那一支"
    "两半都在（静态守卫；坏 %s）" % (_lv_bad or "无"))
for _ln in _lv_lines:
    print("      %s" % _ln)

_m_bad, _m_lines, _can, _cant = [], [], [], []
for _k, _x in sorted(side_q.items(), key=lambda kv: kv[1]["order"]):
    _n, _lv = int(_x["order"]), int(_x["min_level"])
    _accp = _player(level=_lv, flags={"card": 1})        # ★ B4-27：接活要证
    _acc = _drive(CQ.quest_accept, _accp, "接 %d" % _n)
    if _k not in ((_accp.get("flags") or {}).get("quests_active") or []):
        _m_bad.append((_k, "接都接不下", _acc[:2]))
        continue
    _p = _sat_player(_x, _k)
    _pay = _drive(CQ.quest_deliver, _p, "交 %d" % _n)
    _deliv = any(ln.startswith("交了") for ln in _pay) \
        and _k in ((_p.get("flags") or {}).get("quests_done") or [])
    if _deliv:
        _can.append(_k)
        _m_lines.append("交得掉 %-8s 编号 %-3d 条件 %s → 屏上「%s」· 经验 +%d 铜板 +%d"
                        % (_x["name"], _n,
                           " ＋ ".join(_SHAPE_OF.get(r.get("kind"), r.get("kind"))
                                      for r in CQ._require_of(_x)),
                           (_pay[0][:22] if _pay else "?"), _x["reward_exp"], _x["reward_gold"]))
        continue
    _cant.append(_k)
    _q = _satiated(_k)
    _pay2 = _drive(CQ.quest_deliver, _q, "交 %d" % _n)
    if any(ln.startswith("交了") for ln in _pay2):
        _m_bad.append((_k, "万事俱备的档竟然交掉了（那就不该在交不掉名单里）", _pay2[:2]))
    if _k not in _DEAD_SIDE:
        _m_bad.append((_k, "新死的一条（钉住名单里没有它）", _x["objective"]))
    _m_lines.append("交不掉 %-8s 编号 %-3d「%s」→ 万事俱备的档照样拦着：「%s」｜ 缺的形状：%s"
                    % (_x["name"], _n, _x["objective"], (_pay2[0][:18] if _pay2 else "?"),
                       _DEAD_SIDE.get(_k, "★ 不在钉住名单里（要补一条）")))
if set(_cant) != set(_DEAD_SIDE):
    _m_bad.append(("名单", "交不掉的集合 %s ≠ 钉住名单 %s" % (sorted(_cant), sorted(_DEAD_SIDE)), ""))
(ok if not _m_bad and len(_can) + len(_cant) == 18 else bad)(
    "★ 18 条支线交付真跑矩阵：**交得掉 %d 条**（各真接一次、真交一次、奖励入档）· "
    "**交不掉 %d 条**（万事俱备的档仍被拦 ⇒ 看的是没人写的 `flags.side_<名字>`；名单钉住，"
    "一变就红；坏 %s）" % (len(_can), len(_cant), _m_bad or "无"))
for _ln in _m_lines:
    print("      %s" % _ln)

# ── ★ B4-2（P-25 §② 的根因**钉死**）：`flags.side_<名字>` 这条路今天**只有读端、没有写端**
#   （所以那 5 条才交不掉：它看的不是「做没做」，是一个没人写的键）。
#   静态守卫：`"side_"` 这个**字符串字面量**在 `content/*.py` 里只许出现 **1 处**，且那处
#   必须在 `_obj_ok` 里（读端）—— 谁哪天给它补了个写端（绕过 `require` 的第二种活法）当场红。
#   （注释 / 文档串里那种带反引号的写法不算 —— 这一条只认**字面量**。）
import glob as _glob                                                      # noqa: E402

_sw_hits, _sw_bad = [], []
for _p in sorted(_glob.glob(os.path.join(REPO, "content", "*.py"))):
    _src = io.open(_p, encoding="utf-8").read().split("\n")
    for _i, _ln in enumerate(_src):
        if '"side_"' not in _ln:
            continue
        _fn = next((_s.split("(")[0].replace("def ", "").strip()
                    for _s in reversed(_src[:_i]) if _s.startswith("def ")), "?")
        _sw_hits.append((os.path.basename(_p), _i + 1, _fn, _ln.strip()[:56]))
if len(_sw_hits) != 1 or _sw_hits[0][2] != "_obj_ok":
    _sw_bad.append(_sw_hits)
(ok if not _sw_bad else bad)(
    "★ P-25 §② 的根因钉死：`\"side_\"` 字面量在 content/*.py 里只有**读端 1 处**（`_obj_ok`）"
    " —— 实测 %s（多一处 = 有人给这条死路写了第二个口）" % (_sw_hits or "无"))

# ── ㉙ ★ 支线条件的**另一处真源**：`15_彩蛋域口径_v1 §二` 那句「<任务>「<名字>」的交待就是彩蛋 <n>」
#   那条彩蛋的条件（`hold` → 手上有 · `where` → 去过）就是那个任务的交付条件（`read` 是彩蛋自己的
#   那一步，任务不取）。★ 探针**自己解析**这份文档 —— 与生成器各写各的解析（共用镜像表会把两处的
#   错一起掩盖）；一句都找不着也判红（文档换说法要有人重新裁决，不许静默少一条条件）。
_DOC15 = os.path.join(PLAN, "00_总纲", "15_彩蛋域口径_v1.md")
_ROW15 = _re.compile(r"^\|\s*\d+\s*\|\s*(egg_[a-z_]+)\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*$")
_IS_TOLD = _re.compile(r"(q_[a-z0-9_]+)\s*「([^」]+)」\s*的交待就是彩蛋\s*(\d+)")
_told, _told_bad, _told_lines = 0, [], []
for _ln in (_io.open(_DOC15, encoding="utf-8", newline="").read().split("\n")
            if os.path.exists(_DOC15) else []):
    _r = _ROW15.match(_ln)
    if not _r:
        continue
    _j = _IS_TOLD.search(_r.group(3))
    if not _j:
        continue
    _qid, _qname, _egg_no = _j.group(1), _j.group(2), int(_j.group(3))
    _told += 1
    _want = []
    for _cl in _r.group(2).split("&"):
        _cl = _cl.strip()
        if "=" not in _cl:
            continue
        _ck, _cv = [p.strip() for p in _cl.split("=", 1)]
        if _ck == "read":
            continue
        if _ck == "hold":
            _want.append({"kind": "item", "item": _cv, "n": 1})
        elif _ck == "where":
            _m, _, _nd = _cv.partition(":")
            _want.append({"kind": "visit", "map": _m, "node": _nd})
        elif _ck == "kill":
            _want.append({"kind": "kill", "monster": _cv, "n": 1})
        else:
            _told_bad.append("%s 的子句键「%s」没有条件形状（15 §二 第 %s 条彩蛋）"
                             % (_qid, _ck, _egg_no))
    _x = QE.get(_qid)
    if not _x:
        _told_bad.append("15 §二 点名了 %s，但域里没有这条任务" % _qid)
    elif _x["name"] != _qname:
        _told_bad.append("15 §二 说的「%s」与域里 %s 的名字「%s」对不上"
                         % (_qname, _qid, _x["name"]))
    elif CQ._require_of(_x) != _want:
        _told_bad.append("%s 的 require %s ≠ 15 §二 彩蛋 %d 的条件 %s"
                         % (_qid, json.dumps(_x.get("require"), ensure_ascii=False), _egg_no,
                            json.dumps(_want, ensure_ascii=False)))
    else:
        _told_lines.append("%s「%s」→ 条件取自 15 §二 彩蛋 %d：%s"
                           % (_qid, _qname, _egg_no, json.dumps(_want, ensure_ascii=False)))
(ok if _told and not _told_bad else bad)(
    "★ 支线条件与 15 §二「交待就是彩蛋」那句逐条对账（%d 条；坏 %s）"
    % (_told, _told_bad or "无"))
for _ln in _told_lines:
    print("      %s" % _ln)

# ══════════════════════════════════════════════════════════════
# ㉚–㉛ B3-13：支线新四型（enhance / cook / talk / ask）· 悬赏「指定的」的每日轮换
#      源：`24_任务线_v1.md §二`（支线表的「步骤」列 · 悬赏板那两句）· `21_长期目标层_v1.md §二`
#      ★ 照 ⑬/⑳/㉔/㉙ 的老规矩：探针**自己**解析文档、自己算轮换（不与实现/生成器共用一份）。
# ══════════════════════════════════════════════════════════════
import content.cmds_recipe as CR                                          # noqa: E402
import content.cmds_talk as CT                                            # noqa: E402

EV = st.domain("events")
_NUM2 = r"[一二两三四五六七八九十\d]"
_CN2 = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
        "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
#: 这 7 条该是什么型（条件**形状**由哪一句推 —— 与生成器各写各的）
_EXP_KIND = {"q_side_01": "enhance", "q_side_05": "cook", "q_side_06": "cook+quality",
             "q_side_07": "talk",           # ★ B4-27：陪他配一次 → 跟艾德搭 1 次话
             "q_side_09": "talk", "q_side_16": "talk", "q_side_17": "ask"}


def _cn(tok):
    t = str(tok or "").strip()
    return int(t) if t.isdigit() else _CN2.get(t, -1)


def _exp_side(steps, who):
    """«24 §二» 那一行的「步骤」+「谁给」→ 该有的 `require`（探针自己推一遍；推不出回 None）。"""
    m = _re.search(r"强化到\s*\+?(\d+)", steps)
    if m:
        return [{"kind": "enhance", "n": int(m.group(1))}]
    m = _re.search(r"用(\S+?)食材做(" + _NUM2 + r"*)[次回]", steps)
    if m:
        return [{"kind": "cook", "quality": m.group(1), "n": _cn(m.group(2) or "一")}]
    m = _re.search(r"做(" + _NUM2 + r"+)道菜", steps)
    if m:
        return [{"kind": "cook", "n": _cn(m.group(1))}]
    m = _re.search(r"听[他她]讲完[（(](" + _NUM2 + r"+)次[）)]", steps) \
        or _re.search(r"听[他她]讲完(" + _NUM2 + r"+)段", steps)
    if m:
        ids = [k for k, v in NPCS.items() if v.get("name") == who]
        return ([{"kind": "talk", "npc": ids[0], "n": _cn(m.group(1))}] if len(ids) == 1 else None)
    m = _re.search(r"帮[他她]问(" + _NUM2 + r"+)个人", steps)
    if m:
        return [{"kind": "ask", "n": _cn(m.group(1))}]
    # ★ B4-27 · 支 7 白烛堂的灯：「陪他配一次」⇒ 跟**谁给的那位**搭 N 次话
    #   （「陪」在支线里就是搭话 —— 与「听他讲完（三次）」同一族；次数从这一句现取）
    m = _re.search(r"陪[他她]配(" + _NUM2 + r"*)次", steps)
    if m:
        ids = [k for k, v in NPCS.items() if v.get("name") == who]
        return ([{"kind": "talk", "npc": ids[0], "n": _cn(m.group(1) or "一")}]
                if len(ids) == 1 else None)
    return None


def _mon_name(mid):
    return str((MON.get(mid) or {}).get("name") or mid)


def _flags_for_event(eid):
    """让那个事件成立的最小档（★ 只读 events 域的 `period` —— 探针自己推，不猜）。"""
    per = ((EV.get(str(eid)) or {}).get("period") or {}) if eid else {}
    if per.get("from_main"):
        return {"quests_done": [str(per["from_main"])]}
    if per.get("until_main"):
        return {"quests_done": []}
    return {}


def _stand(npc_id, extra_flags=None):
    """这个人**此刻**在哪个节点（现看 `_npcs_here` —— 集日会把人吸到板子那边）。"""
    for _loc, _mv in MAPS.items():
        for _nd in (_mv.get("nodes") or []):
            _pp = _player(level=9, flags=dict(extra_flags or {}))
            _pp.update({"loc": _loc, "node": _nd["id"]})
            try:
                if any(k == npc_id for k, _v in CA._npcs_here(_loc, _nd["id"], None, _pp)):
                    return _loc, _nd["id"]
            except Exception:                                             # noqa: BLE001
                continue
    return None


def _event_of(npc_id):
    return ((NPCS.get(npc_id) or {}).get("condition") or {}).get("event") or ""


#: 真做的四件（每条 = (真做什么, 造档并真跑, 一句打样)）—— 动作全走**真指令的实现体**
_GEAR = next(((k, v) for k, v in ITEMS.items()
              if not str(k).startswith("_") and v.get("slot")), (None, None))


def _accept_then(x, p, accept_first):
    """★ fxm3-questsnap：**先接活，再真做那一次** —— 返回接活那一段回话（不接就回空表）。

    为什么要有它（本波口径）：`content/cmds_quest._req_ok` 现在判的是「**接活后**新达成」
    （接活那一刻落一份进度基线 `flags.quests[<id>]["base"]`）。「先做 → 再接 → 交」那个老时序，
    在新判据下**就该交不掉**（= ㊳ 要钉住的那一态）；这一档问的还是「这条支线真做得成、真交得掉」，
    所以驱动时序回到玩家真实那一条：**接 → 做 → 交**。断言一个字没改（真做一次 ⇒ 交得掉），
    而新时序还顺带把「接活那一刻基线真落了」也压在载重上（不落基线这条就红）。
    """
    if not accept_first:
        return []
    return _drive(CQ.quest_accept, p, "接 %d" % x["order"])


def _act_enhance(x, accept_first=False):
    """真做：真的把一件装备强化到 +n（走 `cmds_recipe.enhance`，不是往档里写数）。

    ★ P3 BUG-2（本波 f4）：`强化` 现在有**地点门禁**（必须在铁匠铺那一站，与『铁匠铺』同口径）
      ⇒ 这一支的档要**站在那一站**（节点从 `npcs.funcs` 的 `smith` 现取，不手写）。

    ★ fxm3-questsnap：`accept_first=True` ⇒ **先接活再真做**（`require` 判「接活后新达成」——
      见 ㊳ 与 `_accept_then`）。
    """
    iid, rec = _GEAR
    if not iid:
        return None, [], "items 域里没有能强化的装备"
    from content.town import _func_node as _fn_enh
    p = _player(level=1, gold=9999, flags={"card": 1},
                loc="windmill_town", node=_fn_enh("smith"),
                bag={iid: 1, "i_material_iron_scrap": 9, "i_material_hard_bone": 9})
    out = []
    out += _accept_then(x, p, accept_first)
    for _ in range(int(CQ._require_of(x)[0]["n"])):
        out += _drive(CR.enhance, p, "强化 %s" % rec.get("name"))
    lv = int(((p.get("enhance") or {}).get(iid) or {}).get("lv") or 0)
    return p, out, "强化到 +%d（%s）" % (lv, rec.get("name"))


def _act_cook(x, accept_first=False):
    """真做：真的下锅（走 `cmds_recipe.cook`；食材按配方给够 —— 账由锅自己记）。"""
    r0 = CQ._require_of(x)[0]
    n = int(r0.get("n") or 1)
    recs = _cook_recs(str(r0.get("quality") or ""), known_only=True)
    if not recs:
        return None, [], "没有能顶这个条件的配方"
    rid = recs[0]
    rg = RC[rid]
    bag = {}
    for e in (rg.get("inputs") or []):
        bag[str(e.get("id"))] = int(e.get("n") or 1) * n
    p = _player(level=1, bag=bag, flags={"card": 1})
    out = []
    out += _accept_then(x, p, accept_first)
    for _ in range(n):
        out += _drive(CR.cook, p, "烹饪 %s" % rg.get("name"))
    return p, out, "下锅 %d 次（%s）" % (CQ._cook_have(p, r0), rg.get("name"))


def _band_hour(npc_id):
    """这位 NPC 的作息里挑一个「他在」的钟点（没写 `condition.time` ⇒ None = 不拨钟）。

    ★ 合入落账（Wave-2 · G4 作息那一批）：五位 NPC 起有了 `condition.time` ⇒「他在不在」成了
      **按钟点翻面**的事。而这一档问的是「这条支线真能走通」，不是「此刻他在不在」——
      不拨钟的后果：真实钟点落在昏/夜时这条判据红、早上跑却是绿的（那种红不是回归）。
      钟点→时辰的对应由 `content/calendar.py::state` **现算**（晨 5–7 · 昼 8–17 · 昏 18–19 · 夜 20–4）。
    """
    toks = ((NPCS.get(npc_id) or {}).get("condition") or {}).get("time")
    if not toks:
        return None
    toks = toks if isinstance(toks, (list, tuple)) else [toks]
    for band, h in (("hr_day", 12.0), ("hr_dawn", 6.0), ("hr_dusk", 18.0), ("hr_night", 22.0)):
        for t in toks:
            _k, _e = CAL_Q.resolve(t)
            if _k == "hour" and _e == band:
                return h
    return None


def _act_talk(x, accept_first=False):
    """真做：站到他那儿真的搭 N 次话（走 `cmds_talk.talk`）。

    ★ 有作息的那位：**先把假钟拨到他在的时辰**再跑（跑完还原）—— 见 `_band_hour`。
    """
    r0 = CQ._require_of(x)[0]
    n = int(r0.get("n") or 1)
    npc = str(r0.get("npc") or "")
    who = str((NPCS.get(npc) or {}).get("name") or npc)
    fl = _flags_for_event(_event_of(npc))
    _saved = dict(FC_Q.HANDLES)
    _h = _band_hour(npc)
    if _h is not None:
        _at_day(CAL_Q.day_now(), _h)
    try:
        spot = _stand(npc, fl)
        if not spot:
            return None, [], "找不到「%s」此刻在场的节点" % who
        p = _player(level=9, flags={"card": 1})
        p.update({"loc": spot[0], "node": spot[1]})
        if fl:
            # ★ B4-27：那一位有出场条件（事件）时**并进去**，不是整格换掉 ——
            #   否则刚补上的 `flags.card`（接活那道门要的）会被这一行冲掉。
            p["flags"] = dict(p.get("flags") or {}, **fl)
        out = []
        out += _accept_then(x, p, accept_first)
        for _ in range(n):
            out += _drive(CT.talk, p, "搭话 %s" % who)
        return p, out, "跟「%s」搭话 %d 次（他在 %s）" % (who, CQ._talk_have(p, npc), spot[1])
    finally:
        FC_Q.bind_host(**_saved)


def _act_ask(x, accept_first=False):
    """真做：真的跟 N 个**不同的人**搭话（走同一个 `talk` 实现体 —— 账按对话树记）。

    ★ 同 `_act_talk`：先把假钟拨到**昼**（在场的人最多）再挑人 —— 否则「问得到几个人」
      会按真实钟点翻面（夜里好几位不在 ⇒ 这条也红）。
    """
    n = int(CQ._require_of(x)[0].get("n") or 1)
    p = _player(level=9, flags={"card": 1})
    out, hit = [], []
    out += _accept_then(x, p, accept_first)
    _saved = dict(FC_Q.HANDLES)
    _at_day(CAL_Q.day_now(), 12.0)
    try:
        for npc, v in sorted(NPCS.items(), key=lambda kv: kv[0]):
            if len(hit) >= n or not v.get("dialogue"):
                continue
            fl = _flags_for_event(_event_of(npc))
            spot = _stand(npc, fl)
            if not spot:
                continue
            p.update({"loc": spot[0], "node": spot[1]})
            p["flags"] = dict(p.get("flags") or {}, **fl) if isinstance(p.get("flags"), dict) else dict(fl)
            out += _drive(CT.talk, p, "搭话 %s" % v.get("name"))
            hit.append(str(v.get("name")))
        return p, out, "搭话过 %d 个人（%s）" % (CQ._asked_have(p), "/".join(hit))
    finally:
        FC_Q.bind_host(**_saved)


_ACT = {"enhance": _act_enhance, "cook": _act_cook, "talk": _act_talk, "ask": _act_ask}
_nk_bad, _nk_lines = [], []
_enh_cap = int(((RC.get("_meta") or {}).get("enhance") or {}).get("cap") or 0)
_people = len([k for k, v in NPCS.items() if v.get("dialogue")])

for _qid in sorted(_EXP_KIND, key=lambda q: QE[q]["order"]):
    _x = QE[_qid]
    _row = side_rows.get(_x["name"])
    if not _row:
        _nk_bad.append("%s 不在 24 §二 支线表里" % _qid)
        continue
    _want = _exp_side(_row[3], _row[2])
    if _want != CQ._require_of(_x):
        _nk_bad.append("%s 条件 %s ≠ 文档「%s」推出来的 %s"
                       % (_qid, json.dumps(_x.get("require"), ensure_ascii=False), _row[3],
                          json.dumps(_want, ensure_ascii=False)))
        continue
    _r0 = _want[0]
    if _EXP_KIND[_qid] != _r0["kind"] and _EXP_KIND[_qid] != "%s+quality" % _r0["kind"]:
        _nk_bad.append("%s 的型变了：%s" % (_qid, _r0["kind"]))
    # ── 可达性（量够不够 / 途径有没有）—— 探针自己重算
    if _r0["kind"] == "enhance" and int(_r0["n"]) > _enh_cap:
        _nk_bad.append("%s 要 +%d，强化上限只有 +%d（到不了）" % (_qid, _r0["n"], _enh_cap))
    if _r0["kind"] == "cook":
        _recs = _cook_recs(str(_r0.get("quality") or ""), known_only=True)
        _all_recs = _cook_recs(str(_r0.get("quality") or ""))
        if not _recs:
            _nk_bad.append("%s 的 `cook` 条件**不用先交别条任务**就顶不上（能顶的只有 %s —— "
                           "先交别条才学会的配方不算数）" % (_qid, _all_recs or "一个都没有"))
        elif _r0.get("quality"):
            _q_items = [k for k, v in ITEMS.items()
                        if not str(k).startswith("_") and str(v.get("quality")) == _r0["quality"]]
            if not _q_items:
                _nk_bad.append("%s 要「%s」品阶的食材，items 域里没有这一档"
                               % (_qid, _r0["quality"]))
            elif not [k for k in _q_items if k in produced]:
                _nk_bad.append("%s 要「%s」品阶的食材，但那几样**没有任何出产渠道**：%s"
                               % (_qid, _r0["quality"], _q_items))
    if _r0["kind"] == "talk":
        _npc = str(_r0.get("npc") or "")
        if _npc not in NPCS or not (NPCS.get(_npc) or {}).get("dialogue"):
            _nk_bad.append("%s 要跟「%s」搭话，但 npcs 域里取不到他 / 他没挂对话树" % (_qid, _npc))
    if _r0["kind"] == "ask":
        if _people < int(_r0["n"]):
            _nk_bad.append("%s 要问 %d 个人，镇上有对话树的只有 %d 位" % (_qid, _r0["n"], _people))
    # ── ★ 真做一次 → 真交一次（动作全走真指令，不是把账写进档）
    #   ★ fxm3-questsnap：时序 = **接 → 真做一次 → 真交一次**（`require` 判「接活后新达成」，
    #     见 `_accept_then`）。断言一个字没改：真做一次 ⇒ 交得掉、没有取不到文案的行。
    _p, _out, _how = _ACT[_r0["kind"]](_x, accept_first=True)
    if _p is None:
        _nk_bad.append("%s 的真做走不通：%s" % (_qid, _how))
        continue
    _pay = _drive(CQ.quest_deliver, _p, "交 %d" % _x["order"])
    _deliv = any(ln.startswith("交了") for ln in _pay) \
        and _qid in ((_p.get("flags") or {}).get("quests_done") or [])
    if not _deliv:
        _nk_bad.append("%s 真做了（%s）却交不掉：%s" % (_qid, _how, _pay[:3]))
    if any(MISSING in ln for ln in _out + _pay):
        _nk_bad.append("%s 有取不到文案的行" % _qid)
    _nk_lines.append("%s %-6s（编号 %-3d）条件 %s → 真做：%s → 真交：%s"
                     % ({"enhance": "强化", "cook": "烹饪", "talk": "搭话",
                         "ask": "问人"}[_r0["kind"]], _x["name"], _x["order"],
                        json.dumps(_want, ensure_ascii=False), _how,
                        (next((ln for ln in _pay if ln.startswith("交了")), "?") + " · 经验 +%d 铜板 +%d"
                         % (_x["reward_exp"], _x["reward_gold"]))))
(ok if len(_EXP_KIND) == 7 and not _nk_bad else bad)(
    "★ 支线新四型 %d 条：与 24 §二「步骤」列逐条对账（含数词）· 量够达成 / 途径存在 · "
    "**接 → 真做一次 → 真交一次**（动作走真指令：强化 / 下锅 / 搭话 / 问人；"
    "★ fxm3-questsnap：时序改成「先接后做」—— 老时序「先做后接」在新判据下就该交不掉，"
    "那一态由 ㊳ 钉着；坏 %s）"
    % (len(_EXP_KIND), _nk_bad or "无"))
for _ln in _nk_lines:
    print("      %s" % _ln)

# ── ㉛ ★ 悬赏「指定的」= 每天轮换挑一只（可复现 · 跨日必换 · **池按可遇性收窄** · fail-closed）
#   ★ g3-quests2 规格变更（**只加强，不放宽**）：
#     旧规格 = 池 = 该档**全部**怪（只看 `monsters.role_key`），按 id 排序取第 (游戏日-1)%n+1 只
#       ⇒ 可能点名一只**按这一档标称等级、在它自己写明的站上根本挑不出来**的怪
#         （玩家报告 P1 BUG-2：`normal` 档点到「野狗」ms_wild_dog，1 级档的玩家在野狗窝
#          按 `pick_encounter` 只能撞上 田鼠 / 拾荒野狗 / 林鸦 —— 杀了 4 回也不算）。
#     g3 规格 = 池 = 该档的怪 ∩ **可遇集合**（`_pool_spec`：该怪 `habitat` 写明的**每一站**上，
#       按该档 `min_level` 都进得了「等级最近前 3」的那批）；轮换算法一个字没动。
#   ★ 本波（2026-09-27 · 任务②）**再加一半 —— 等级带**：
#     病灶：只站着 **3 只怪**的站上「前 3」= **全部** ⇒ 可遇那半等于没筛（knight 第 3 轮 b5
#     1 级档点到 lv9 石滩螃蟹；ranger 第 4 轮 b156 精英档点到 lv13 水里的东西）⇒ 接得下、交不掉。
#     新规格 = 池 = 该档的怪 ∩ 可遇 ∩ **带内**（|怪 lv − 该档标称等级| ≤ `level_band.json` 的
#       `max_level_diff`；边界 5 借的是探索那条已批口径「差 ≥ +5 ⇒ 怪躲」）。数值一个没动。
#     逐条判据（新增的都在这儿，原来的**一条没松**）：
#       ① 三档的池子逐只与探针自己算的（可遇 ∩ 带内）**相等**
#       ② 被剔掉的那几只**逐只点名** + 剔的理由**现算**（在哪一站进不了前 3 / 带外差几级）
#       ③ 反证 A：把可遇性过滤拿掉（放行全档）⇒ 逐个游戏日比，至少有一天对不上
#       ④ 反证 B（本波加）：**把等级带拿掉**（只按旧尺子）⇒ 至少有一天点名到**带外**那一只
#          —— 证明「带」这一半真的载重（不是装饰）
_rot_bad, _rot_lines = [], []
_CERTAIN = _re.search(r"打掉\s*\**\s*指定的", bounty_blk or "")
_ROTATE = _re.search(r"每天轮换挑一只", bounty_blk or "")
if not (_CERTAIN and _ROTATE):
    _rot_bad.append("24 §二 悬赏板里「指定的」/「每天轮换挑一只」解析不出（%s / %s）"
                    % (bool(_CERTAIN), bool(_ROTATE)))
_bt = sorted(bounty_q.items(), key=lambda kv: kv[1]["order"])
_roles = []
for _k, _x in _bt:
    _r0 = (CQ._require_of(_x) or [{}])[0]
    if _r0.get("kind") != "kill" or not _r0.get("daily") or not _r0.get("role"):
        _rot_bad.append("%s 的条件不是「点档 + daily」：%s"
                        % (_k, json.dumps(_x.get("require"), ensure_ascii=False)))
        continue
    _roles.append(str(_r0["role"]))
_total_cut = []
for _role in sorted(set(_roles)):
    _lv_role = _tier_lv(_role)
    _allids = sorted(_role_ids_of(_role))                  # 该档**全部**怪（= 旧规格的池）
    _spec = _pool_spec(_role)                              # ★ 新规格：可遇集合（探针自己算）
    if len(_spec) < 2:
        _rot_bad.append("档「%s」的可遇集合只有 %d 只 —— 「轮换」观察不到（池要 > 1）"
                        % (_role, len(_spec)))
        continue
    if list(CQ._pool_of(_role)) != _spec:
        _rot_bad.append("档 %s 的池子 %s ≠ 探针自己算的可遇集合 %s"
                        % (_role, list(CQ._pool_of(_role)), _spec))
    _cut = [m for m in _allids if m not in _spec]
    _total_cut += [(str(_role), m) for m in _cut]
    if _lv_role <= 0:
        _rot_bad.append("档 %s 取不到标称等级（`_tier_lv` 回 0）" % _role)
    _why_lines = []
    for _m in _cut:
        _spots = _spots_spec(_m)
        _bad = [(l, n) for l, n in _spots if _m not in _top3(l, n, _lv_role)]
        _mlv = int(MON[_m].get("lv") or 0)
        if _lv_role > 0 and not _in_band(_mlv, _lv_role):
            _why_lines.append("%s（带外：lv%d vs 标称 %d 级 · 差 %d > %d%s）"
                              % (_mon_name(_m), _mlv, _lv_role, abs(_mlv - _lv_role), _BAND_MAX,
                                 "" if not _bad else "；另在 %s 也进不了前 3"
                                 % " · ".join("%s:%s" % (l, n) for l, n in _bad)))
            continue
        if not _spots or not _bad:
            _rot_bad.append("★ 档 %s 把「%s」剔了，但按规格它该在池里（可遇 · 且带内）"
                            % (_role, _mon_name(_m)))
            continue
        _why_lines.append("%s（在 %s 进不了前 3）"
                          % (_mon_name(_m), " · ".join("%s:%s" % (l, n) for l, n in _bad)))
    # ★ 正例（本波加）：池里**每一只**都必须在等级带内 —— 拿掉带子这一条当场红
    for _m in _spec:
        if not _in_band(MON[_m].get("lv"), _lv_role):
            _rot_bad.append("★ 档 %s 的池子里「%s」（lv%s）在等级带外（标称 %s 级 · 带宽 %d）"
                            % (_role, _mon_name(_m), MON[_m].get("lv"), _lv_role, _BAND_MAX))
    for _d in range(1, 3 * len(_spec) + 2):
        _want = _spec[(_d - 1) % len(_spec)]
        _at_day(_d)                                                   # ★ B4-9：造「第 d 日」= 拨钟
        _a = CQ._daily_pick(_role, {})
        _b = CQ._daily_pick(_role, {})                                # 同一日再来一次
        _at_day(_d + 1)                                               # ★ 跨日：钟推一个游戏日
        _n1 = CQ._daily_pick(_role, {})
        if _a != _want or _b != _want:
            _rot_bad.append("档 %s 第 %d 日：实现 %s/%s ≠ 规格 %s" % (_role, _d, _a, _b, _want))
        if _n1 == _a:
            _rot_bad.append("档 %s 第 %d 日与第 %d 日挑了同一只（没轮换）" % (_role, _d, _d + 1))
    _rot_lines.append("档 %-7s 池 %2d/%2d 只（标称 %d 级）· 剔掉：%s"
                      % (_role, len(_spec), len(_allids), _lv_role,
                         " · ".join(_why_lines) or "无"))
    _rot_lines.append("档 %-7s · 第 1..%d 日的点名：%s → 第 %d 日回到 %s（循环 ✓ · "
                      "同一日两次同结果 ✓ · 跨日必换 ✓）"
                      % (_role, len(_spec), "/".join(_mon_name(m) for m in _spec),
                         len(_spec) + 1, _mon_name(_spec[0])))
# ★ 反证（本波新增）：把可遇性过滤拿掉 ⇒ 实现那一头退回「该档全部怪」，逐日比**至少一天对不上**
if not _total_cut:
    _rot_bad.append("★ 三档一只都没被剔掉 —— 可遇性过滤没生效（判据可能恒真）")
_keep_pool = CQ._pool_of
_off_diff = 0
try:
    CQ._pool_of = (lambda role: sorted(_role_ids_of(str(role or ""))))
    for _role in sorted(set(_roles)):
        _spec = _pool_spec(_role)
        if len(_spec) < 2:
            continue
        for _d in range(1, len(_spec) + 1):
            _at_day(_d)
            if CQ._daily_pick(_role, {}) != _spec[(_d - 1) % len(_spec)]:
                _off_diff += 1
finally:
    CQ._pool_of = _keep_pool
if not _off_diff:
    _rot_bad.append("★ 反证没生效：把可遇性过滤拿掉后逐个游戏日比，竟然一天都不差（判据可能恒真）")
# ★ 反证 B（本波新增）：「等级带」那一半真的载重 —— 把 `_pool_of` 换成**只按旧尺子**的可遇集合
#   （不带带）⇒ 逐个游戏日比，至少有一天点名到**带外**那一只（改回旧尺子当场红）
_keep_pool_b = CQ._pool_of
_band_off = 0
try:
    CQ._pool_of = (lambda role: _pool_spec_no_band(str(role or "")))
    for _role in sorted(set(_roles)):
        _lv_r = _tier_lv(_role)
        _spec2 = _pool_spec_no_band(_role)
        if _lv_r <= 0 or len(_spec2) < 2:
            continue
        for _d in range(1, len(_spec2) + 1):
            _at_day(_d)
            _p = CQ._daily_pick(_role, {})
            if _p == _spec2[(_d - 1) % len(_spec2)] and not _in_band(MON[_p].get("lv"), _lv_r):
                _band_off += 1
finally:
    CQ._pool_of = _keep_pool_b
if not _band_off:
    _rot_bad.append("★ 反证 B 没生效：拿掉等级带后逐个游戏日比，一天都没点到带外那一只（判据可能恒真）")
# ★ 池空那一档（本波新加的**人话**）：现网三档池都 ≥2 只 ⇒ 这一档到不了，**反证式**造空它 ——
#   池空必须「不点名」+ 说 `SYS_JOB_REQ_NO_MATCH` 那一句，**不许**掉到
#   `SYS_JOB_REQ_UNKNOWN`（「这条的前置条件取不出来」= 给「数据坏了」用的，读起来像 bug）
_keep_pool_c = CQ._pool_of
try:
    CQ._pool_of = (lambda role: [])
    _at_day(2)
    _empty = _drive(CQ.quest_deliver, _player(level=1, day=2,
                                              flags={"quests_active": ["q_bounty_normal"]}), "交 101")
finally:
    CQ._pool_of = _keep_pool_c
_want_nomatch = str(CQ.T("SYS_JOB_REQ_NO_MATCH"))
_want_unknown = str(CQ.T("SYS_JOB_REQ_UNKNOWN"))
if not any(_want_nomatch in ln for ln in _empty):
    _rot_bad.append("★ 池空（反证造空）时没出「没点到合适的怪」那一句：%s" % (_empty,))
if any(_want_unknown in ln for ln in _empty):
    _rot_bad.append("★ 池空时掉到了 `SYS_JOB_REQ_UNKNOWN`（那句是给数据坏了用的）：%s" % (_empty,))
# fail-closed：认不出的档
_at_day(2)
if CQ._daily_pick("no_such_role", {}) != "" \
        or CQ._req_ok({}, {"kind": "kill", "role": "no_such_role", "daily": True}) \
        or CQ._req_ok({}, {"kind": "kill", "daily": True}):
    _rot_bad.append("认不出的档 / 没写档：没 fail-closed（应当一律没满足）")
# ★ 判据加强的那一半：只认**当天点名的那一只** —— 同档的另一只不算
_ROT_D = 3
_at_day(_ROT_D)                                                        # ★ B4-9：下面这几档都在第 3 日
_bx = QE.get("q_bounty_normal") or {}
_bpick = _pick_of("normal", _ROT_D)
_bother = next((k for k in sorted(_role_ids_of("normal")) if k != _bpick), "")
_p_hit = _player(level=1, day=_ROT_D, books={"monster": {_bpick: {"day": _ROT_D, "kills": 1}}},
                 flags={"quests_active": ["q_bounty_normal"]})
_p_oth = _player(level=1, day=_ROT_D, books={"monster": {_bother: {"day": _ROT_D, "kills": 9}}},
                 flags={"quests_active": ["q_bounty_normal"]})
_p_non = _player(level=1, day=_ROT_D, flags={"quests_active": ["q_bounty_normal"]})
if not CQ._obj_ok(_bx, _p_hit):
    _rot_bad.append("打了第 %d 日点名的那一只（%s）却交不掉" % (_ROT_D, _mon_name(_bpick)))
if CQ._obj_ok(_bx, _p_oth):
    _rot_bad.append("★ 宽口径没被拦住：打了同档的**另一只**（%s）也交得掉" % _mon_name(_bother))
if CQ._obj_ok(_bx, _p_non):
    _rot_bad.append("一只都没打也交得掉")
# 真跑：没做到 → 拦住且那一行**点名今天那只**；做到了 → 交掉
_lack = _drive(CQ.quest_deliver, _player(level=1, day=_ROT_D,
                                         flags={"quests_active": ["q_bounty_normal"]}), "交 101")
_lack_line = next((ln for ln in _lack if "还差" in ln), "")
if _mon_name(_bpick) not in _lack_line:
    _rot_bad.append("「还差」那一行没点名第 %d 日的那只（%s）：%s" % (_ROT_D, _mon_name(_bpick), _lack))
_pay2 = _drive(CQ.quest_deliver, _player(level=1, day=_ROT_D,
                                         books={"monster": {_bpick: {"day": _ROT_D, "kills": 1}}},
                                         flags={"quests_active": ["q_bounty_normal"]}), "交 101")
if not any(ln.startswith("交了") for ln in _pay2):
    _rot_bad.append("打了点名的那只却交不掉：%s" % _pay2[:3])
(ok if not _rot_bad and len(_roles) == 3 else bad)(
    "★ 悬赏「指定的」= 每天轮换挑一只（可复现 · 跨日必换〔拨钟造日〕· 探针自己算规格一致 · "
    "★ **池按「可遇 ∩ 等级带」收窄**：池 == 探针自算的（可遇 ∩ 带内）· 剔掉的逐只现算核过"
    "（带外差几级 / 哪一站进不了前 3）· 池里每一只都在带内 · 反证 A 关掉可遇过滤 ⇒ "
    "逐日至少一天对不上 · ★ 反证 B 关掉等级带 ⇒ 至少一天点到**带外**那一只 · "
    "★ 池空（反证造空）⇒ 不点名 + 说 `SYS_JOB_REQ_NO_MATCH`（不掉 UNKNOWN）· "
    "**打同档另一只不算** · 认不出的档 fail-closed · 真跑拦得住也交得掉；"
    "坏 %s）" % (_rot_bad or "无"))
for _ln in _rot_lines:
    print("      %s" % _ln)
print("      真跑：没做到 →「%s」｜打了「%s」→「%s」｜反证（拿掉过滤）：逐日对不上 %d 天"
      % (_lack_line[:40], _mon_name(_bpick),
         next((ln for ln in _pay2 if ln.startswith("交了")), "?"), _off_diff))
FC_Q.bind_host(**_FC_SAVED)                                            # ★ B4-9：拨回真钟

# ── ★ P-60（B4-25 顺手全扫记的那一笔 · 本批落）：每日轮换**只留一份写法**
#   原先同一个概念有两份：`quests.q_bounty_*.repeat = "daily"`（域 + schema 里都有，**0 个读端**）
#   与 `require[].daily`（`cmds_quest._daily_pick` 真读的那一份）。今天不咬人（没人读 `repeat`），
#   但谁哪天顺手去读它，两边就可能给出不同的日子（K74：同一件事两处口径）。
#   ⇒ 清成一份：域里那三格删掉 · `schemas/quests.schema.json` 那条 enum 删掉 · 并在这儿立守卫
#     （判据只加强：这三条谁破了当场红，而不是等哪一天真去读才发现两份不一样）。
_REP_BAD = []
#   ① 域里一条都不许带 `repeat`（条目级扫，不是扫文件文本）
_rep = [k for k, v in QE.items() if isinstance(v, dict) and "repeat" in v]
if _rep:
    _REP_BAD.append("域里还有 %s 带 repeat" % _rep)
#   ② schema 里没有 `repeat` 这个键（唯一真源那一侧也清干净 —— 不然编辑器还会把它当合法字段）
_schp = os.path.join(REPO, "schemas", "quests.schema.json")
_sch_txt = io.open(_schp, encoding="utf-8").read() if os.path.exists(_schp) else ""
if '"repeat"' in _sch_txt:
    _REP_BAD.append("schemas/quests.schema.json 里还有 repeat")
#   ③ 代码里 0 处读 `"repeat"`（键字面量；注释里提一嘴不算）
_rep_code = []
for _f in sorted(os.listdir(os.path.join(REPO, "content"))):
    if not _f.endswith(".py"):
        continue
    for _i, _ln in enumerate(io.open(os.path.join(REPO, "content", _f),
                                     encoding="utf-8").read().split("\n")):
        if '"repeat"' in _ln:
            _rep_code.append((_f, _i + 1))
if _rep_code:
    _REP_BAD.append("content 里还有读 repeat 的地方 %s" % _rep_code)
#   ④ 今日轮换的那**一份**写法还在，且真挂在悬赏三档上（那份就是 `require[].daily`）——
#      域里那三档必须各带一条 `daily`（轮换本身由 ㉛ 真跑核：同一次探针里逐日对账）
_rep_ok = [k for k in ("q_bounty_normal", "q_bounty_elite", "q_bounty_boss")
           if any(r.get("daily") for r in ((QE.get(k) or {}).get("require") or []))]
if len(_rep_ok) != 3:
    _REP_BAD.append("悬赏三档里只有 %s 带 require[].daily" % _rep_ok)
(ok if not _REP_BAD else bad)(
    "★ P-60 · 每日轮换只有一份写法（`require[].daily`）：域里带 `repeat` 的条目 **0** 条 · "
    "schema 里没有 `repeat` · content/*.py 里读它的地方 **0** 处 · 悬赏三档各带一条 `daily`"
    "（%s）—— 坏 %s" % ("/".join(_rep_ok), _REP_BAD or "无"))
# ══════════════════════════════════════════════════════════════
# ㉝ ★ B4-27 ②（P-53）：「接 <编号>」那道门 —— **先办见习证**
#      口径 = `06_第一阶段垂直切片/04_指令总表 §二` 的守卫「**已登记 · 未接**」
#        （`03_风车镇 §一` 只写「等级够 · 未接」—— 两份真源打架 ⇒ 按**命令表真源**落，
#         与台账 P-53「我的倾向：加」一致；理由写在 `content/cmds_quest.quest_accept` 抬头）。
#      改前 `quest_accept` **一眼都不看** `flags.card`（那个证只有『评级』读）⇒ 办证白办、
#        「公会 → 登记（见习证）→ 悬赏 → 接活」断在最后一节。
#      判据四拍（都真敲）：① 无证档**四条链各试一条**都拦 + **档一个字不动**
#                           ② 有证档接得下（档上真写下 quests_active）
#                           ③ 顺序钉子：手上真有这条委托的档（无证）回「已经接了」——
#                              不许被回一句「你没有证」的假话
#                           ④ 这道门**只管「接」**：交活 / 我的委托 在无证档上照旧
# ══════════════════════════════════════════════════════════════
_CARD_Q = (TX.get("SYS_JOB_NEED_CARD") or {}).get("value") or ""
_BACK_Q = (TX.get("SYS_JOB_ALREADY") or {}).get("value") or ""
_card_bad, _card_lines = [], []
if not _CARD_Q:
    _card_bad.append(("槽位 SYS_JOB_NEED_CARD 取不到文案", ""))

# ① 无证档：四条链各一条 —— 都拦，且档一个字不动（`flags` 仍是空表：没接、也没塞别的东西）
for _kind, _qid, _n in (("主线", "q_main_01", 1), ("支线", "q_side_07", 19),
                        ("生活", "q_trade_01", 31), ("悬赏", "q_bounty_normal", 101)):
    _p0 = _player(level=9)                       # 等级够 ⇒ 门挡的不是等级
    _o0 = _drive(CQ.quest_accept, _p0, "接 %d" % _n)
    if _o0 != [_CARD_Q]:
        _card_bad.append(("无证 · " + _kind, _o0[:3]))
    if (_p0.get("flags") or {}) != {}:
        _card_bad.append(("无证 · %s 竟然动了档" % _kind, _p0.get("flags")))
    _card_lines.append("无证 · %-4s 编号 %-3d ⇒ 「%s」· 档原样"
                       % (_kind, _n, (_o0[0][:20] if _o0 else "?")))

# ② 有证档（`登记` 写的就是这一格）：接得下 + 档上真写下来
_p_c1 = _player(level=9, flags={"card": 1})
_o_c1 = _drive(CQ.quest_accept, _p_c1, "接 1")
if not any(ln.startswith("接下") for ln in _o_c1) \
        or "q_main_01" not in ((_p_c1.get("flags") or {}).get("quests_active") or []):
    _card_bad.append(("有证 · 接不下", _o_c1[:3]))
_card_lines.append("有证 ⇒ 「%s」· 档上 quests_active=%s"
                   % (next((ln for ln in _o_c1 if ln.startswith("接下")), "?"),
                      (_p_c1.get("flags") or {}).get("quests_active")))

# ③ 顺序钉子：这条单子**自己**的状态优先（手上真有它 ⇒ 不许回「你没有证」）
_p_c2 = _player(level=9, flags={"quests_active": ["q_main_01"]})
_o_c2 = _drive(CQ.quest_accept, _p_c2, "接 1")
if _o_c2 != [_BACK_Q]:
    _card_bad.append(("无证 + 已经接过（应当回「已经接了」）", _o_c2[:3]))
_card_lines.append("无证 + 已经接过 ⇒ 「%s」" % (_o_c2[0][:20] if _o_c2 else "?"))

# ④ 门只管「接」那一件事：交活与『我的委托』在无证档上照旧（没人被这道门连累）
_p_c3 = _player(level=9, flags={"quests_active": ["q_main_01"],
                                "talked": {CQ._dlg_of("npc_masha"): 1}})
_o_c3 = _drive(CQ.quest_deliver, _p_c3, "交 1")
if not any(ln.startswith("交了") for ln in _o_c3):
    _card_bad.append(("无证 · 交活被连累", _o_c3[:3]))
_o_c4 = _drive(CQ.quest_mine, _player(level=9, flags={"quests_active": ["q_main_01"]}), "")
if not _o_c4 or any(MISSING in ln for ln in _o_c4):
    _card_bad.append(("无证 · 我的委托", _o_c4[:3]))
_card_lines.append("无证 ⇒ 交活「%s」· 我的委托 %s 行照旧"
                   % (next((ln for ln in _o_c3 if ln.startswith("交了")), "?"), len(_o_c4)))
(ok if not _card_bad else bad)(
    "★ B4-27（P-53）「接 <编号>」的守卫「已登记 · 未接」：无证档**四条链都拦**且档原样 · "
    "有证档接得下 · 「已经接过」优先于这道门 · 交活 / 我的委托 不受连累（坏 %s）"
    % (_card_bad or "无"))
for _ln in _card_lines:
    print("      %s" % _ln)

# ══════════════════════════════════════════════════════════════
# ㉞ ★ B4-27 ③（P-56）：`放弃` 的冷却 = **同一个游戏日只许放弃一条**
#      真源 = `06_第一阶段垂直切片/05_玩法数值口径_v1.md §一`「放弃 ｜ 冷却 1 天；掉一点声望」。
#      ★ 本批**只落冷却那半**（「掉一点声望」没有容器 ⇒ 登记待裁，见 `_notes.md`）。
#      判据（都真敲 · 拨钟造日）：
#        ① 第 5 日 放弃 1 ⇒ 掉了 + `flags.abandon_day = 5`
#        ② 同一日再 放弃 2 ⇒ **拦住**（冷却那一行）+ **档一个字不动**
#        ③ 跨到第 6 日 ⇒ 放行（冷却真的只有 1 个游戏日）
#        ④ 冷却期内「另一件事」不许被连累：`放弃 99`（不在手上）照旧回「没有这一条」·
#           裸「放弃」照旧回「放弃哪一条」（两拍档都不动）
#        ⑤ ★ 判定读的是**那根钟**：档上那格 `p["day"]` 故意写成错的旧值也不许影响
#           （B4-9 同族 —— 日期戳一律现算）· 那一格写坏了（认不出）不许把玩家永久锁住
# ══════════════════════════════════════════════════════════════
_CD_Q = (TX.get("SYS_JOB_ABANDON_CD") or {}).get("value") or ""
_NONE_Q = (TX.get("SYS_JOB_NO_ACTIVE_ONE") or {}).get("value") or ""
_ASK_Q = (TX.get("SYS_JOB_ABANDON_ASK") or {}).get("value") or ""
_cd_bad, _cd_lines = [], []
if not _CD_Q:
    _cd_bad.append(("槽位 SYS_JOB_ABANDON_CD 取不到文案", ""))
_CD_D = 5
_at_day(_CD_D)                                  # ★ 拨钟造「第 5 个游戏日」
# ① 第一条：放得下 + 冷却那一格写下**今天**
_p_cd1 = _player(level=3, day=99, flags={"card": 1,
                                         "quests_active": ["q_main_01", "q_main_02"]})
_o_cd1 = _drive(CQ.quest_abandon, _p_cd1, "放弃 1")
_f_cd1 = _p_cd1.get("flags") or {}
if not any("放弃了" in ln for ln in _o_cd1):
    _cd_bad.append(("第 %d 日 · 放弃 1" % _CD_D, _o_cd1[:2]))
if _f_cd1.get("quests_active") != ["q_main_02"] or int(_f_cd1.get("abandon_day") or 0) != _CD_D:
    _cd_bad.append(("第 %d 日 · 掉完之后档上不对" % _CD_D, _f_cd1))
_cd_lines.append("第 %d 日 · 放弃 1 ⇒ 「%s」（档上 abandon_day=%s · 手上 %s）"
                 % (_CD_D, next((ln for ln in _o_cd1 if "放弃了" in ln), "?"),
                    _f_cd1.get("abandon_day"), _f_cd1.get("quests_active")))
# ② 同一天第二条：拦住 + 档一个字不动（`day=99` 那格假的旧戳照样不许影响判定）
_p_cd2 = _player(level=3, day=99, flags={"card": 1, "quests_active": ["q_main_02"],
                                         "abandon_day": _CD_D})
_o_cd2 = _drive(CQ.quest_abandon, _p_cd2, "放弃 2")
if _o_cd2 != [_CD_Q]:
    _cd_bad.append(("同一日 · 放弃 2（应当只回冷却那一行）", _o_cd2[:2]))
if (_p_cd2.get("flags") or {}) != {"card": 1, "quests_active": ["q_main_02"],
                                   "abandon_day": _CD_D}:
    _cd_bad.append(("同一日 · 拦下时动了档", _p_cd2.get("flags")))
_cd_lines.append("同日 · 放弃 2 ⇒ 「%s」· 档原样" % (_o_cd2[0][:20] if _o_cd2 else "?"))
# ④ 冷却期内「另一件事」不受连累（不在手上 / 没带编号 —— 都是别的问法）
_o_cd4 = _drive(CQ.quest_abandon, _player(level=3, flags={"card": 1, "quests_active": ["q_main_02"],
                                                          "abandon_day": _CD_D}), "放弃 99")
_p_cd5 = _player(level=3, flags={"card": 1, "quests_active": ["q_main_02"], "abandon_day": _CD_D})
_o_cd5 = _drive(CQ.quest_abandon, _p_cd5, "放弃")
if _o_cd4 != [_NONE_Q] or _o_cd5 != [_ASK_Q]:
    _cd_bad.append(("冷却期内的另一件事被连累", (_o_cd4[:2], _o_cd5[:2])))
if (_p_cd5.get("flags") or {}).get("quests_active") != ["q_main_02"]:
    _cd_bad.append(("裸「放弃」动了档", _p_cd5.get("flags")))
# ③ 跨日 ⇒ 放行（冷却只有 1 个游戏日）
_at_day(_CD_D + 1)
_p_cd3 = _player(level=3, day=99, flags={"card": 1, "quests_active": ["q_main_02"],
                                         "abandon_day": _CD_D})
_o_cd3 = _drive(CQ.quest_abandon, _p_cd3, "放弃 2")
_f_cd3 = _p_cd3.get("flags") or {}
if not any("放弃了" in ln for ln in _o_cd3) \
        or int(_f_cd3.get("abandon_day") or 0) != _CD_D + 1:
    _cd_bad.append(("跨到第 %d 日竟然还拦着" % (_CD_D + 1), (_o_cd3[:2], _f_cd3)))
_cd_lines.append("第 %d 日 · 放弃 2 ⇒ 「%s」（abandon_day 跟到 %s）"
                 % (_CD_D + 1, next((ln for ln in _o_cd3 if "放弃了" in ln), "?"),
                    _f_cd3.get("abandon_day")))
# ⑤ 那一格写坏了（认不出）不许把玩家永久锁住 —— 退回「没冷却过」
_p_cd6 = _player(level=3, flags={"card": 1, "quests_active": ["q_main_02"],
                                 "abandon_day": "坏了"})
_o_cd6 = _drive(CQ.quest_abandon, _p_cd6, "放弃 2")
if not any("放弃了" in ln for ln in _o_cd6):
    _cd_bad.append(("abandon_day 写坏了却被永久锁住", _o_cd6[:2]))
# 静态守卫：那一格只有 `cmds_quest.py` 两处（读口 `_abandon_day` + 写口那一行）
_ab_hits = []
for _p_ab in sorted(_glob.glob(os.path.join(REPO, "content", "*.py"))):
    for _i_ab, _ln_ab in enumerate(io.open(_p_ab, encoding="utf-8").read().split("\n")):
        if '"abandon_day"' in _ln_ab or "'abandon_day'" in _ln_ab:
            _fn_ab = next((_s.split("(")[0].replace("def ", "").strip()
                           for _s in reversed(io.open(_p_ab, encoding="utf-8").read()
                                              .split("\n")[:_i_ab]) if _s.startswith("def ")), "?")
            _ab_hits.append((os.path.basename(_p_ab), _i_ab + 1, _fn_ab))
if [h for h in _ab_hits if h[0] != "cmds_quest.py"] or len(_ab_hits) != 2 \
        or not any(h[2] == "_abandon_day" for h in _ab_hits):
    _cd_bad.append(("冷却那一格出现了第二个口", _ab_hits))
(ok if not _cd_bad else bad)(
    "★ B4-27（P-56）`放弃` 的冷却（1 个游戏日 · 源 05 §一）：同日第二条拦住且档原样 · 跨日放行 · "
    "冷却期内别的问法不受连累 · 判定走那根钟（档上那格假的也不影响）· 那一格坏掉不把人锁死 · "
    "读写各一处（坏 %s）" % (_cd_bad or "无"))
for _ln in _cd_lines:
    print("      %s" % _ln)
FC_Q.bind_host(**_FC_SAVED)                     # ★ 拨回真钟

# ══════════════════════════════════════════════════════════════
# ㊱ ★ P-61：`悬赏` 那块板**把三档每日悬赏也列出来**（玩家不必先知道编号）
#      真源两份各说一个形状，本批挑**写得下**的那一条落：
#        · `24_任务线_v1 §二`：「**悬赏板**（玛莎 · 无限循环的日常内容）」
#        · `03_风车镇_指令与回复 §一`：`悬赏` → 看板 → **三行列表**
#      ⇒ 一档一行（普通 101 / 精英 102 / 头目 103），写法与主线那一行同形；
#        那三行的**编号**就是『接 <编号>』认的同一个 `order`（列出来 = 接得上）。
#      判据（都真敲）：
#        ① 三档一个不落 · 每行逐字 = `SYS_BOARD_BOUNTY_ROW` 填参（编号 · 名字 · 标记 · 等级）
#        ② ★ 接线档：板上那三个编号，`接 <编号>` **真接得下**（档上真写下 `quests_active`）
#        ③ 已接那一档带「进行中」标记，另两档不带
#        ④ 另一条路没被抢：主线段与尾注逐字照旧，段的先后 = 主线 → 悬赏 → 尾注
#        ⑤ 反证：域里那三条一拿掉 ⇒ 板上**一行悬赏都不出现**（fail-closed：没数据就不列，
#           也不拿别的东西顶上），而主线那一段照旧
# ══════════════════════════════════════════════════════════════
_BRD36 = CQ._func_node("board")
_TOWN36 = CA.TOWN
_BQ36 = sorted([(k, v) for k, v in CQ._quests().items() if v["chain"] == "bounty"],
               key=lambda kv: kv[1]["order"])
_LV36 = max((v["min_level"] for _k, v in _BQ36), default=1)


def _slot36(key, **kw):
    """槽位现算的期望串（不手写镜像表）。"""
    s = (TX.get(key) or {}).get("value", "")
    for k, v in kw.items():
        s = s.replace("{%s}" % k, str(v))
    return s


_HEAD36 = _slot36("SYS_BOARD_BOUNTY_HEAD")
_HOW36 = _slot36("SYS_BOARD_HOW")


def _row36(v, mark=""):
    return "  " + _slot36("SYS_BOARD_BOUNTY_ROW", order=v["order"], name=v["name"],
                          mark=mark, level=v["min_level"])


#: ★ 主线那一行的定位器 —— **从槽位取前缀**（P2 车道 2026-09-28）。
#:   原来这里写死 `x.startswith("主线 ")`：那是**拿文案当机器键 grep**，
#:   P2-1 把并列行统一成「行首 `· `」之后定位就失配了（判据没错，是取件方式错了）。
#:   改法 = 用 `SYS_BOARD_MAIN_ROW` 现算的前缀去认它，措辞怎么改都不用回来动这条判据。
def _is_main_row36(line, _v=None):
    """这一行是**主线那一条**的板行吗 —— 现算，不认字面文案。

    ★ 原来写死 `x.startswith("主线 ")`（拿文案当机器键 grep）；P2-1 把并列行统一成
      「行首 `· `」之后那个定位就失配了。改成**用槽位把这一行整行算出来再比对** ——
      行首锚点、编号、名字、等级四格全都由 `SYS_BOARD_MAIN_ROW` 现填，措辞怎么改都不用回来动判据。
    ★ 用**整行相等**而不是「前缀」：只比前缀的话，行首那个 `· ` 会让三档悬赏行也误判成主线行。
    """
    v = _v or next((x for x in CQ._quests().values() if x["chain"] == "main"), None)
    if not v:
        return False
    want = _slot36("SYS_BOARD_MAIN_ROW", order=v["order"], name=v["name"],
                   mark="", level=v["min_level"]).strip()
    return line.strip() == want


def _board36(flags):
    return _drive(CQ.board, _player(loc=_TOWN36, node=_BRD36, level=_LV36, flags=flags), "")


_bad36 = []
_o36 = _board36({"card": 1})
if not _BQ36:
    _bad36.append(("quests 域里一条 bounty 都没有", []))
for _k, _v in _BQ36:
    _ln = _row36(_v)
    if _ln not in _o36:
        _bad36.append(("三档里这一行不在板上 / 逐字对不上", _v["order"], _ln))
# ①b 段的先后：主线那一行 → 悬赏抬头 → 三档 → 尾注（别把谁挤掉）
_MAIN36 = next((v for v in CQ._quests().values() if v["chain"] == "main"), None)
_i_main = next((i for i, x in enumerate(_o36)
                if _MAIN36 and _is_main_row36(x, _MAIN36)), -1)
_i_head = _o36.index(_HEAD36) if _HEAD36 in _o36 else -1
_i_how = len(_o36) - 1 if _o36 and _o36[-1] == _HOW36 else -1
if not (_i_main >= 0 and _i_main < _i_head < _i_how and _BQ36
        and _o36.index(_row36(_BQ36[0][1])) > _i_head):
    _bad36.append(("段的先后不对（主线 → 悬赏 → 尾注）", (_i_main, _i_head, _i_how, len(_o36))))
# ② 接线档：板上那三个编号真接得下
for _k, _v in _BQ36:
    _pa = _player(level=_LV36, flags={"card": 1})
    _oa = _drive(CQ.quest_accept, _pa, "接 %d" % _v["order"])
    if not _oa or MISSING in "".join(_oa) or _v["name"] not in "".join(_oa[:1]):
        _bad36.append(("板上那个编号接不下（没那句「接下」）", _v["order"], _oa[:2]))
    if _k not in ((_pa.get("flags") or {}).get("quests_active") or []):
        _bad36.append(("板上那个编号接下了却没落档", _v["order"], _pa.get("flags")))
# ③ 已接那一档带「进行中」，另两档不带
if _BQ36:
    _taken36 = _BQ36[0][0]
    _o36b = _board36({"card": 1, "quests_active": [_taken36]})
    _act36 = _slot36("SYS_BOARD_ACTIVE")
    if _row36(_BQ36[0][1], _act36) not in _o36b:
        _bad36.append(("已接那一档没带「进行中」", _row36(_BQ36[0][1], _act36), _o36b[:6]))
    for _k, _v in _BQ36[1:]:
        if _row36(_v, _act36) in _o36b:
            _bad36.append(("没接的那一档却带了「进行中」", _v["order"]))
# ⑤ 反证：域里没有悬赏档 ⇒ 板上不列（不拿别的东西顶上），主线那一段照旧
_keep_q36 = CQ._quests
try:
    CQ._quests = (lambda: {k: v for k, v in _keep_q36().items() if v["chain"] != "bounty"})
    _o36c = _board36({"card": 1})
finally:
    CQ._quests = _keep_q36
if (_HEAD36 in _o36c) or any(_row36(v) in _o36c for _k, v in _BQ36):
    _bad36.append(("域里一条悬赏都没有，板上却列了", _o36c[:6]))
if _MAIN36 and not any(_is_main_row36(x, _MAIN36) for x in _o36c):
    _bad36.append(("反证那一支把主线那一段也弄没了", _o36c[:4]))
(ok if not _bad36 else bad)(
    "★ P-61 `悬赏` 板列三档每日悬赏（源 24 §二 悬赏板 + 03 §一「三行列表」）：%s 行逐字 = "
    "`SYS_BOARD_BOUNTY_ROW` 填参 · 板上那三个编号**真接得下**（接线档）· 已接那档带「进行中」· "
    "主线 → 悬赏 → 尾注 的先后照旧 · 域里没有悬赏档时一行都不列（坏 %s）"
    % ("/".join(str(v["order"]) for _k, v in _BQ36), _bad36 or "无"))
for _k, _v in _BQ36:
    print("      %s" % _row36(_v).strip())

# ══════════════════════════════════════════════════════════════
# ㊲ ★ fix-l：缺的是**料**时也要说「从哪儿来」（试玩 ranger b71/b85 · 副业 15「娜娜的药单」）
#   与 `kill` 那一支的「出没地」（QB-3）**同一口径**：`强化` / `打造` 早就有这一栏
#   （唯一出处口 = `cmds_recipe._src_of` → `matsrc`：采集点 + 掉它的怪），而 `提示` /
#   `看 <编号>` 这一路原先只报名字与数目 ⇒ 玩家拿着「夜明砂 ×3」不知道去哪儿找。
#   判据（现算，不硬编码材料名 · 期望走**同一个出处口**）：逐条带 `item` 条件的任务，
#   用一个空手档真敲「看 <编号>」—— 凡是那件东西域里真有出产渠道的，那一行必须在屏上；
#   取不到渠道的不许多塞一行。反证：把出处口换成空 ⇒ 那些行全消失（判据不是恒真）。
print()
print("── ★ fix-l ㊲：缺料要说「从哪儿来」（与 `kill` 的「出没地」同一口径）")
from content import cmds_recipe as _CR37                                  # noqa: E402
from content import cmds_more as _CMO37                                    # noqa: E402（`看 <编号>` 那一支住在 cmds_more）
_LW37 = TX["SYS_JOB_REQ_ITEM_WHERE"]["value"]


def _want37(iid):
    _wh = _CR37._src_of(iid)
    if not _wh:
        return ""
    # 品名走**实现那一口**（`CQ._item_name`）—— 未鉴定件（`unid_*`）不在 items 域里，
    # 探针自己从域里取名会取到机器键（那正是判据要防的那种漏键）。
    return _LW37.replace("{item}", str(CQ._item_name(iid))).replace("{where}", _wh)


_bad37, _n37, _tgt37, _sat_p37 = [], [0], [], {}
for _k37, _v37 in sorted(QE.items(), key=lambda kv: int(kv[1].get("order") or 0)):
    for _i37, _r37 in enumerate(CQ._require_of(_v37)):
        if _r37.get("kind") != "item":
            continue
        _iid37 = str(_r37.get("item") or "")
        _w37 = _want37(_iid37)
        if not _w37:
            continue                      # 域里真没渠道的那几样：不在本条判据的范围（另有 ⑮ 管「渠道存在」）
        #   单子按步走 ⇒ 只有**轮到这一条**（前面几步都做过）时它才上屏：用 `skip=<这一条>`
        #   造一个「前面都做过、只差这件料」的档（同一个骨架，不另写一份）。
        _p37 = _sat_player(_v37, _k37, skip=_i37)
        _p37["loc"], _p37["node"] = "windmill_town", "wt_board"
        _sat_p37[(_v37["order"], _iid37)] = _p37
        _n37[0] += 1
        _tgt37.append((_v37["order"], _iid37, _w37))
        _o37 = _drive(_CMO37.board_show, _p37, "看 %s" % _v37["order"])
        if not any(_w37 in _ln for _ln in _o37):      # 单子那一屏每条前面自带两个空格 ⇒ 比子串
            _bad37.append((_v37["order"], _v37.get("name"), _w37, _o37[-3:]))
(ok if not _bad37 else bad)(
    "★ fix-l ㊲：带 `item` 条件的单子，缺那件料时屏上带「从哪儿来」那一行"
    "（%d 处逐条真敲 · 期望走同一个出处口）· 取不到渠道的不多话（坏 %s）"
    % (_n37[0], _bad37[:2] or "无"))
# 反证：把出处口换成空 ⇒ 刚才那几行**全都**消失（判据真的咬在「出处是现算的」上）
_keep_src37 = _CR37._src_of
try:
    _CR37._src_of = (lambda *_a, **_k: "")
    _rev37 = [(od, w) for od, _iid, w in _tgt37
              if any(w in _ln for _ln in _drive(_CMO37.board_show, _sat_p37[(od, _iid)],
                                                "看 %s" % od))]
finally:
    _CR37._src_of = _keep_src37
(ok if (not _rev37 and _tgt37) else bad)(
    "★ 反证：把出处口换成空 ⇒ 那 %d 行全都消失（判据咬得住「有没有真现算」）"
    "（坏 %s）" % (len(_tgt37), _rev37[:2] or "无"))
# ㊳ ★ fix-m-bounty ①：悬赏**跨游戏日可重接**（「日常」那一层本来是死的）
#                    ②：`悬赏` 板的「这人手上还有」**只列还能接的**
#      真源（`aetheran-plan`，只读）：
#        · `06_第一阶段垂直切片/24_任务线_v1.md §二`：悬赏板（玛莎 · **无限循环的日常内容**）·
#          「同时挂 6 条 · **每天刷 1 次**」「悬赏板**每天轮换挑一只**」「三档每日悬赏**常年挂
#          在公会上**」；同文件 §二 支线表 = 板上那一段列的活儿（一人一行 · 带编号）
#        · `00_总纲/03_主要玩法.md §4.1`：「**悬赏（公会板）** 打怪类的日常活，**可反复接**」
#      改前两条：① `quest_accept` 的 `k in _done(p)` 是**永久**挡（`quests_done` 只加不减）⇒
#      悬赏交过一次以后**新的游戏日**再接仍回「这条你已经接了（或交过了）。」（游侠路
#      b125/b130 实测）· ② `board` 那一段把在场 NPC 的支线**全列**（不看 `done`）⇒ 玩家照着
#      点一条交掉的单子，回的就是那句「你已经接了（或交过了）」（ranger b130/b131 实测）。
#      判据（**只加强** · 每一条都真敲指令 · 日期一律拨钟造 —— B4-9 那根钟）：
#        ① 第 A 日 接 → 交：交活那一拍把**完成日**记下（`flags.quests[<id>].at` = A）
#        ② 同一日再敲 ⇒ 仍拦（`SYS_JOB_ALREADY` 一行 · **档一个字不动**）
#        ③ 拨到第 B 日 再敲 ⇒ **放行**（真接下 · 档上真写下 · `quests_done` 不被动过）
#        ④ 第 B 日再交一次 ⇒ 落账**去重**（同一条不进两份 —— 已交条数不许虚高）· 完成日跟到 B
#        ⑤ 其余链条一个字不松：主线 / 支线 / 副业各一条，完成日远在昨天也照旧拦
#        ⑥ fail-closed：完成日**写坏 / 缺记录**（老档只有 `quests_done`）/ 写在将来 ⇒ 拦
#        ⑦ 反证：把「只有悬赏」那半拿掉（`_reaccept_ok` 恒真）⇒ **主线当场就接得下**
#           （「拦主线」真靠这条判据，而不是靠别的守卫）
#        ⑧ 板子：**已交那条不列** · 没交的照旧列 · 抬头照旧
#        ⑨ 板子：在场那位手上的全交掉 ⇒ **连表头都不印**（主线那一段一字不动）
#        ⑩ 反证：把 `_done` 换回空表 ⇒ 已交那条**又出现在板上**（「不列」真由 done 过滤管着）
# ══════════════════════════════════════════════════════════════
_ALREADY_Q = (TX.get("SYS_JOB_ALREADY") or {}).get("value") or ""
_TAKEN_Q = (TX.get("SYS_JOB_TAKEN") or {}).get("value") or ""
_DELIV_Q = (TX.get("SYS_JOB_DELIVERED") or {}).get("value") or ""
_SIDEHEAD_Q = (TX.get("SYS_BOARD_SIDE_HEAD") or {}).get("value") or ""
_fb_bad, _fb_lines = [], []


def _pfx(_s):
    """槽位那句话的头两个字 —— 判「这一拍走的是哪一支」用现取的槽位，不写死中文。"""
    return (_s or "")[:2]


def _fb_flags(p):
    return json.loads(json.dumps(p.get("flags") or {}))


_BQ1 = next(((k, v) for k, v in QE.items() if v.get("chain") == "bounty"), None)
_DAY_A, _DAY_B = 20, 21
if _BQ1 is None or not (_ALREADY_Q and _TAKEN_Q and _DELIV_Q and _SIDEHEAD_Q):
    _fb_bad.append(("夹具不齐（悬赏档 / 槽位取不到文案）", ""))
else:
    _bk, _bx = _BQ1
    _bn = int(_bx["order"])
    _blv = max(1, int(_bx["min_level"]))
    # ── ① 第 A 日：接 → 交（完成日 = A）────────────────────────────
    _at_day(_DAY_A)
    _p1 = _player(level=_blv, flags={"card": 1})
    _o1 = _drive(CQ.quest_accept, _p1, "接 %d" % _bn)
    if not _o1 or not _o1[0].startswith(_pfx(_TAKEN_Q)) or _bx["name"] not in _o1[0] \
            or _bk not in ((_p1.get("flags") or {}).get("quests_active") or []):
        _fb_bad.append(("第 %d 日 · 悬赏 %d 接不下" % (_DAY_A, _bn), _o1[:2]))
    _p2 = _sat_player(_bx, _bk, day=_DAY_A)
    _o2 = _drive(CQ.quest_deliver, _p2, "交 %d" % _bn)
    _F_DONE = _fb_flags(_p2)
    _atA = ((_F_DONE.get("quests") or {}).get(_bk) or {}).get("at")
    if not _o2 or not _o2[0].startswith(_pfx(_DELIV_Q)) \
            or _bk not in (_F_DONE.get("quests_done") or []):
        _fb_bad.append(("第 %d 日 · 悬赏交不掉" % _DAY_A, _o2[:2]))
    if int(_atA or -1) != _DAY_A:
        _fb_bad.append(("交活那一拍没把完成日记下（`flags.quests[%s].at` = %s）" % (_bk, _atA), _F_DONE))
    _fb_lines.append("第 %-2d 日 · 接 %d ⇒「%s」· 交 ⇒「%s」（完成日 at=%s）"
                     % (_DAY_A, _bn, (_o1[0][:12] if _o1 else "?"),
                        (_o2[0][:12] if _o2 else "?"), _atA))
    # ── ② 同一日再敲 ⇒ 仍拦 · 档一个字不动 ─────────────────────────
    _p3 = _player(level=_blv, flags=json.loads(json.dumps(_F_DONE)))
    _o3 = _drive(CQ.quest_accept, _p3, "接 %d" % _bn)
    if _o3 != [_ALREADY_Q] or _fb_flags(_p3) != _F_DONE:
        _fb_bad.append(("第 %d 日 · 同日重接没拦住 / 拦下时动了档" % _DAY_A, (_o3[:2], _p3.get("flags"))))
    _fb_lines.append("第 %-2d 日（同一天）· 再接 %d ⇒「%s」· 档原样" % (_DAY_A, _bn, (_o3[0][:22] if _o3 else "?")))
    # ── ③ 第 B 日 再敲 ⇒ 放行（真接下 · 完成记录不摘）──────────────
    #   ★ 起手档带上 `card`：证那道门管的是「能不能**新接**一条」——跨日的悬赏就是新接一条，
    #     照旧要证（与 ㉝ 同一把尺子；探针不因为这条改动把证那道门绕过去）。
    _F_CARD = dict(_F_DONE, card=1)
    _at_day(_DAY_B)
    _p4 = _player(level=_blv, flags=json.loads(json.dumps(_F_CARD)))
    _o4 = _drive(CQ.quest_accept, _p4, "接 %d" % _bn)
    _f4 = _fb_flags(_p4)
    if not _o4 or not _o4[0].startswith(_pfx(_TAKEN_Q)) \
            or _bk not in (_f4.get("quests_active") or []):
        _fb_bad.append(("第 %d 日 · 悬赏跨日竟接不下（日常循环还是死的）" % _DAY_B, _o4[:2]))
    if (_f4.get("quests_done") or []) != (_F_DONE.get("quests_done") or []):
        _fb_bad.append(("重接时把 `quests_done` 动了（那是完成记录，不许摘）", _f4.get("quests_done")))
    _fb_lines.append("第 %-2d 日（跨日）· 再接 %d ⇒「%s」· 手上 %s"
                     % (_DAY_B, _bn, (_o4[0][:12] if _o4 else "?"), _f4.get("quests_active")))
    # ── ④ 第 B 日再交一次 ⇒ 落账去重 · 完成日跟过来 ──────────────────
    _p5 = _sat_player(_bx, _bk, day=_DAY_B)
    _p5["flags"] = json.loads(json.dumps(_f4))
    _o5 = _drive(CQ.quest_deliver, _p5, "交 %d" % _bn)
    _f5 = _fb_flags(_p5)
    _dn5 = list(_f5.get("quests_done") or [])
    _at5 = ((_f5.get("quests") or {}).get(_bk) or {}).get("at")
    if not _o5 or not _o5[0].startswith(_pfx(_DELIV_Q)):
        _fb_bad.append(("第 %d 日 · 再交一次交不掉" % _DAY_B, _o5[:2]))
    if _dn5.count(_bk) != 1 or len(_dn5) != len(_F_DONE.get("quests_done") or []):
        _fb_bad.append(("同一档跨日交两次把 `quests_done` 写重了（已交条数虚高）", _dn5))
    if int(_at5 or -1) != _DAY_B or _bk in (_f5.get("quests_active") or []):
        _fb_bad.append(("第二次交活：完成日没跟到第 %d 日 / 手上没摘掉" % _DAY_B, (_at5, _f5.get("quests_active"))))
    _fb_lines.append("第 %-2d 日 · 再交一次 ⇒「%s」· quests_done=%s（去重后 %d 条）· at=%s"
                     % (_DAY_B, (_o5[0][:12] if _o5 else "?"), _dn5, len(_dn5), _at5))
    # ── ⑤ 其余链条跨日**一个字不松** ───────────────────────────────
    for _kd, _qid2, _n2 in (("主线", "q_main_01", 1), ("支线", "q_side_09", 21),
                            ("副业", "q_trade_01", 31)):
        _x2 = QE.get(_qid2)
        if not _x2:
            _fb_bad.append(("%s 的夹具不在域里（%s）" % (_kd, _qid2), ""))
            continue
        _fl = {"card": 1, "quests_done": [_qid2],
               "quests": {_qid2: {"step": 1, "done": True, "at": _DAY_A}}}
        _at_day(_DAY_B)
        _p6 = _player(level=99, flags=dict(_fl))
        _o6 = _drive(CQ.quest_accept, _p6, "接 %d" % _n2)
        if _o6 != [_ALREADY_Q] or _fb_flags(_p6) != _fl:
            _fb_bad.append(("%s 跨日竟能重接（判据松了）" % _kd, _o6[:2]))
        _fb_lines.append("%s（%s）· 完成日 %d ⇒ 第 %d 日再敲「%s」"
                         % (_kd, _qid2, _DAY_A, _DAY_B, (_o6[0][:22] if _o6 else "?")))
    # ── ⑥ fail-closed：完成日写坏 / 缺记录 / 写在将来 ────────────────
    _at_day(99)
    for _lbl6, _raw6 in (
            ("老档只有 quests_done（没有 flags.quests）", {"quests_done": [_bk]}),
            ("完成日写坏（认不出）",
             {"quests_done": [_bk], "quests": {_bk: {"step": 1, "done": True, "at": "坏了"}}}),
            ("完成日写在将来（第 100 日）",
             {"quests_done": [_bk], "quests": {_bk: {"step": 1, "done": True, "at": 100}}})):
        _fl6 = dict(_raw6, card=1)
        _p7 = _player(level=_blv, flags=dict(_fl6))
        _o7 = _drive(CQ.quest_accept, _p7, "接 %d" % _bn)
        if _o7 != [_ALREADY_Q] or _fb_flags(_p7) != _fl6:
            _fb_bad.append(("fail-closed 破了：%s 竟放行" % _lbl6, _o7[:2]))
        _fb_lines.append("第 99 日 · %s ⇒「%s」" % (_lbl6, (_o7[0][:22] if _o7 else "?")))
    # ── ⑦ 反证：把「只有悬赏」那半拿掉 ⇒ 主线当场就接得下 ────────────
    _keep_ra = CQ._reaccept_ok
    _fl7 = {"card": 1, "quests_done": ["q_main_01"],
            "quests": {"q_main_01": {"step": 1, "done": True, "at": _DAY_A}}}
    _at_day(_DAY_B)
    try:
        CQ._reaccept_ok = (lambda *_a: True)
        _o8 = _drive(CQ.quest_accept, _player(level=99, flags=dict(_fl7)), "接 1")
    finally:
        CQ._reaccept_ok = _keep_ra
    if not _o8 or not _o8[0].startswith(_pfx(_TAKEN_Q)):
        _fb_bad.append(("反证失败：把「只有悬赏」那半拿掉，主线也没接得下 —— 拦主线的不是这条判据",
                        _o8[:2]))
    _fb_lines.append("反证（拿掉链的限定）· 主线跨日 ⇒「%s」· 复原后 ⇒ 上面 ⑤ 那一行仍拦"
                     % (_o8[0][:22] if _o8 else "?"))
    # ── ⑧⑨⑩ 看板那一段 ────────────────────────────────────────
    # 找「板子那边有支线 giver」的那个游戏日（集日：小满 / 老陶被吸到板子那边）——
    # 前提现算（数据一动，这里当场说清是夹具变了，而不是悄悄跳过判据）
    _mk = _player(level=3)
    _best = (0, 0, [])
    for _d in range(1, 29):
        _at_day(_d, 10.0)                              # 昼
        _here_d = [n for n, _v2 in CQ._npcs_here(CA.TOWN, _BRD36, p=_mk)]
        _cnt = len([1 for _k2, _v2 in QE.items()
                    if _v2["chain"] == "side" and _v2["giver"] in _here_d])
        if _cnt > _best[0]:
            _best = (_cnt, _d, _here_d)
    _MKT_N, _DAY_MKT, _HERE_MKT = _best
    if _MKT_N < 2:
        _fb_bad.append(("板子那边凑不出两条支线（在场就是 %s）—— 夹具前提变了" % (_HERE_MKT,), ""))
    else:
        _at_day(_DAY_MKT, 10.0)
        _side_here = [(k2, v2) for k2, v2 in QE.items()
                      if v2["chain"] == "side" and v2["giver"] in _HERE_MKT]
        _rows8 = ["  " + _slot36("SYS_BOARD_SIDE_ROW", order=v2["order"], name=v2["name"],
                                 objective=v2["objective"]) for _k2, v2 in _side_here[:3]]
        _k8, _v8 = _side_here[0]
        _row8 = _rows8[0]
        _o9a = _board36({"card": 1})                   # 全没交
        if _SIDEHEAD_Q not in _o9a or any(r not in _o9a for r in _rows8):
            _fb_bad.append(("没交过时那一段就不对了（抬头 / 行）", _o9a[-5:]))
        _o9b = _board36({"card": 1, "quests_done": [_k8]})   # 交掉其中一条
        if _row8 in _o9b:
            _fb_bad.append(("已交（%s）的那条**还列在板上** ⇒ 玩家点它就是「你已经接过」" % _k8, _o9b[-5:]))
        for _r2 in _rows8[1:]:
            if _r2 not in _o9b:
                _fb_bad.append(("没交的那条被连累滤掉了", (_r2, _o9b[-5:])))
        if _SIDEHEAD_Q not in _o9b:
            _fb_bad.append(("还有人能接，那一段的抬头却不印了", _o9b[-5:]))
        _fb_lines.append("第 %d 日板子那边在场 %s ⇒ 没交过 %d 行；交掉 %s 后 ⇒ 那一行不在板上、"
                         "另 %d 行照旧 · 抬头在（板上 %s 行）"
                         % (_DAY_MKT, _HERE_MKT, len(_rows8), _k8, max(0, len(_rows8) - 1), len(_o9b)))
        # ⑨ 全交掉 ⇒ 连表头都不印
        _o9c = _board36({"card": 1, "quests_done": [k2 for k2, _v2 in _side_here]})
        if _SIDEHEAD_Q in _o9c or any(r in _o9c for r in _rows8):
            _fb_bad.append(("在场那位手上的活全交掉了，那一段（抬头 / 行）还在印", _o9c[-5:]))
        if not any(_is_main_row36(x, _MAIN36) for x in _o9c):
            _fb_bad.append(("那一支把主线那一段也弄没了", _o9c[:4]))
        _fb_lines.append("全交掉（%s）⇒ 抬头与那几行都不印（板上剩 %d 行，主线那一段照旧）"
                         % ([k2 for k2, _v2 in _side_here], len(_o9c)))
        # ⑩ 反证：把 done 过滤拿掉 ⇒ 已交那条又出现
        _keep_done = CQ._done
        try:
            CQ._done = (lambda _pp: [])
            _o9d = _board36({"card": 1, "quests_done": [_k8]})
        finally:
            CQ._done = _keep_done
        if _row8 not in _o9d:
            _fb_bad.append(("反证失败：把 done 过滤拿掉，已交那条也没回来 —— 管它的不是这条判据",
                            _o9d[-5:]))
        _fb_lines.append("反证（把 done 过滤拿掉）· 已交的 %s ⇒ 又列在板上（那一行真由 done 管着）" % _k8)
FC_Q.bind_host(**_FC_SAVED)                             # ★ 拨回真钟
(ok if not _fb_bad else bad)(
    "★ fix-m-bounty：① 悬赏**跨游戏日可重接**（同日仍拦 · 主线/支线/副业一律不松 · 完成日写坏"
    "一律拦 · 落账去重 · 反证）② `悬赏` 板那一段**只列还能接的**（已交不列 · 全交掉连表头都不印 ·"
    " 反证）（坏 %s）" % (_fb_bad or "无"))
for _ln in _fb_lines:
    print("      %s" % _ln)

# ══════════════════════════════════════════════════════════════
# ㊴ ★ fxm3-questsnap：`require` 判的是「**接活后**新达成」（接活那一下落进度基线）
#   【现象】三路试玩复现：主线 3「三张牌」只要**到过三条带**就能交（`看 3` 一行「还差」都没有、
#     `提示` 直接说「办完了」、`交 3` 白拿 118 经验 / 30 铜板），三条带的活一件没做；
#     主 4 交掉 +330 经验；主 11 交掉 +4276（与 `reward_exp` 逐字相等）。
#   【根因】`require` 查的是**历史态**（历史上到过 / 打过 / 采过就算数），而「接活那一刻」没有基线
#     ⇒ 接活**前**干过的活也算进任务进度。
#   【真源】`24 §一` 每块的「步骤」都是**接了之后要做的那几拍**（主 3 步骤②「**各完成一次**
#     （打怪/采集/送信）」）—— 代码没跟上文案，真源一个字不动。
#   【判据】**三态 + 形状 + 反证 + 老档**，全部真敲指令（造档 → `接` → `看` / `提示` / `交`）：
#     ① 形状：写了 `require` 的条目真接一次 ⇒ `flags.quests[<id>].base` 是 dict，**逐条等于**
#        接活那一刻每条条件的读数（键 = `_ckey`）；**没写 `require` 的老条目**不落那一格。
#     ② 态一「接活前把活干完」（起手档 = 万事俱备）：`看 <编号>` 的「还差」= 条件条数、
#        每一条的缺项行与 `_unmet` 同一口；`提示` **不说**「办完了」；`交 <编号>` 拦住，
#        经验 / 铜板一个字不动、`quests_done` 不长。
#     ③ 态二「接活后真干一次」（把读数各推满一格）：交得掉 · 奖励**逐字** = 域里那两格 ·
#        `flags.quests[<id>].step` = 条件条数；再交一次**不再发奖励**、不再回「交了」。
#     ④ 反证：把 `_set_base` 关掉（= 改前那一版：接活不落基线）⇒ 主 3 / 主 4 / 主 11 **当场又白拿**；
#        复原即绿（判据真咬在基线上）。
#     ⑤ 老档（**有意差异登记**）：**没有基线**的档（= 本批之前接的活 / 起手档直接塞
#        `quests_active`）判定与改前**逐字节相同**（主 3 到过三条带 ⇒ 交得掉）——
#        这是**有意兼容**、不是放宽；要更严（缺基线一律拦）只改 `cmds_quest._base_at` 一处一行。
print()
print("── ★ fxm3-questsnap ㊴：`require` 判「接活后新达成」（接活落进度基线 · 三态 + 反证）")
from content import cmds_more as _CMO39                                  # noqa: E402
from content.town import _func_node as _FN39                             # noqa: E402
from content.cmds_ast import T as _T39                                   # noqa: E402（槽位渲染：判据自己拼期望）
from content.cmds_ast import exp_need as _EXP_NEED39                     # noqa: E402（经验曲线唯一口）

_BOARD39 = _FN39("board")
_DLG39 = st.domain("dialogues") or {}
_at_day(1)                                                              # 悬赏那条「今日点名」要定日


def _bump39(p, r, m=1):
    """把这条条件的**读数**推 m 格 —— 只动那本账本身（= 模拟「接活后真干 m 次」）。

    ★ 探针不另写一份读数口径：推完之后一律由 `CQ._since` 现算，判据只看「推得动 / 交得掉」。
    """
    kind = r.get("kind")
    if kind == "visit":
        loc, nd = str(r.get("map") or ""), str(r.get("node") or "")
        if not nd:
            nd = next((str(x["id"]) for x in ((MAPS.get(loc) or {}).get("nodes") or [])), "n_probe")
        f = dict(p.get("foot") or {})
        v = dict(f.get("visits") or {})
        kk = "%s:%s" % (loc, nd)
        v[kk] = int(v.get(kk) or 0) + m
        f["visits"] = v
        p["foot"] = f
    elif kind == "kill":
        mid = str(r.get("monster") or "")
        if not mid:
            role = str(r.get("role") or "")
            mid = CQ._daily_pick(role, p) if r.get("daily") \
                else next(iter(sorted(_role_ids_of(role))), "")
        b = dict(p.get("books") or {})
        mo = dict(b.get("monster") or {})
        rec = dict(mo.get(mid) or {})
        rec["kills"] = int(rec.get("kills") or 0) + m
        rec.setdefault("day", 1)
        mo[mid] = rec
        b["monster"] = mo
        p["books"] = b
    elif kind == "item":
        b = dict(p.get("bag") or {})
        iid = str(r.get("item") or "")
        b[iid] = int(b.get(iid) or 0) + m
        p["bag"] = b
    elif kind == "enhance":
        e = {kk: (dict(vv) if isinstance(vv, dict) else vv)
             for kk, vv in (p.get("enhance") or {}).items()}
        iid = next(iter(e), "") or "_probe_gear"
        rec = dict(e.get(iid) or {})
        rec["lv"] = int(rec.get("lv") or 0) + m
        e[iid] = rec
        p["enhance"] = e
    elif kind == "cook":
        fl = dict(p.get("flags") or {})
        ck = dict(fl.get("cooked") or {})
        rid = next(iter(ck), "")
        if not rid:
            recs = _cook_recs(str(r.get("quality") or ""), known_only=True)
            rid = recs[0] if recs else "_probe_dish"
        ck[rid] = int(ck.get(rid) or 0) + m
        fl["cooked"] = ck
        p["flags"] = fl
    elif kind == "talk":
        fl = dict(p.get("flags") or {})
        tk = dict(fl.get("talked") or {})
        d = CQ._dlg_of(str(r.get("npc") or ""))
        tk[d] = int(tk.get(d) or 0) + m
        fl["talked"] = tk
        p["flags"] = fl
    else:                                   # ask：要多 **m 个不同的人**有账
        fl = dict(p.get("flags") or {})
        tk = dict(fl.get("talked") or {})
        add = [kk for kk in sorted(_DLG39)
               if not str(kk).startswith("_") and kk not in tk][:m]
        if len(add) < m:
            return False
        for kk in add:
            tk[kk] = 1
        fl["talked"] = tk
        p["flags"] = fl
    return True


def _mk39(x, k):
    """万事俱备的档 + 站在板子那一站 + 带证 + **手上没有这条活**（接下来要真接一次）。"""
    p = _sat_player(x, k, day=1)
    fl = dict(p.get("flags") or {})
    fl["quests_active"] = []
    fl["card"] = 1
    p["flags"] = fl
    p["loc"], p["node"] = "windmill_town", _BOARD39
    return p


_b39, _l39, _base39 = [], [], [0]


def _tot39(p):
    """档上的**累计经验**（把升级时消耗掉的那些也算回来）—— 曲线不另写一份，走 `exp_need` 一个口。

    ★ 为什么判据要看累计（2026-09-27 修）：`add_exp` 会**跨级结转**（一次加 100、当级只要 40
      ⇒ 升一级、余 60）⇒ 直接比「`exp` 那一格的差」会把升级消耗误报成「少发了奖励」。
      改前这一条就是这么错的：21 条支线/副业的 `reward_exp` = 100 而它们的主人是 1 级
      （40 升 2 级）⇒ 全被报成「经验 +60（应 +100）」，连带「再交一次又动了档」。
    """
    lv = int(p.get("level") or 1)
    return sum(int(_EXP_NEED39(i)) for i in range(1, max(1, lv))) + int(p.get("exp") or 0)


for _k39, _x39 in sorted(QE.items(), key=lambda kv: int(kv[1].get("order") or 0)):
    _reqs39 = CQ._require_of(_x39)
    if not _reqs39:
        continue                              # 没写 require 的 4 条老支线不在这条判据的范围（走死路径）
    _n39 = int(_x39["order"])
    _reql = len(_reqs39)
    # ★ 条件的两种口径（取舍写在 `cmds_quest._req_ok` 的 docstring 里）：
    #   · **增量型**（visit / kill / item / cook / talk / ask）⇒ 判「接活后新达成」
    #   · **状态型**（enhance：「有一件装备强化到 ≥ n」）⇒ 判**绝对值**（有意不判增量：
    #     真源写的就是「把一件装备强化到 +3」这个状态；档上只有等级、没有「强化成功次数」那本账）
    _state39 = [r for r in _reqs39 if r.get("kind") == "enhance"]
    _incr39 = [r for r in _reqs39 if r.get("kind") != "enhance"]
    p = _mk39(_x39, _k39)
    _wantb = {CQ._ckey(r): CQ._metric(p, r) for r in _reqs39}       # 接活**那一刻**每条条件的读数
    _e0, _g0 = int(p.get("exp") or 0), int(p.get("gold") or 0)
    _t0 = _tot39(p)
    _acc39 = _drive(CQ.quest_accept, p, "接 %d" % _n39)
    if _k39 not in ((p.get("flags") or {}).get("quests_active") or []):
        _b39.append("%s 接不下：%s" % (_k39, _acc39[:2]))
        continue
    _base = ((p.get("flags") or {}).get("quests") or {}).get(_k39, {}).get(CQ._BASE)
    if not isinstance(_base, dict):
        _b39.append("%s 接活**没落进度基线**（flags.quests[%s].base = %s）" % (_k39, _k39, _base))
    elif _base != _wantb:
        _b39.append("%s 基线不是「接活那一刻的读数」：%s ≠ %s" % (_k39, _base, _wantb))
    _base39[0] += 1

    # ── 态一：接活前把活干完 ⇒ 增量型逐条拦住 · 状态型有意仍算达标 · 判定／呈现／『交』同一把尺
    _o39 = _drive(_CMO39.board_show, p, "看 %d" % _n39)
    # ★ 接活那一刻**真发到手上**的那几件（`quests.<id>.give`）—— 有意算「接活后到手」：
    #   真源 `17 §QUEST_SIDE25_STORY` 写着「小满把那块石头塞给你」⇒ 石头是接活那一下到包的
    #   （`_set_base` 就在 `_hand_over` **之前**，正是为了让这一份算进「接活后新达成」）。
    #   除它以外，接活前干完的活**一律不许**算 —— 这一条就是本判据要钉死的那条线。
    _give39 = {}
    for _g39 in (_x39.get("give") or []):
        _iid39 = str((_g39 or {}).get("item") or "")
        if _iid39:
            _give39[_iid39] = _give39.get(_iid39, 0) + int((_g39 or {}).get("n") or 1)
    for _r39 in _incr39:
        _base_r39 = CQ._base_at(p, _k39, _r39)
        _growth39 = CQ._metric(p, _r39) - _base_r39          # 「接活后新达成」的量
        _give_n39 = (_give39.get(str(_r39.get("item") or ""), 0)
                     if _r39.get("kind") == "item" else 0)
        _expect39 = _give_n39 >= CQ._n_of(_r39)   # 该不该达标：只有「接活那一下真到手的」算
        if _growth39 > _give_n39:                 # 接活前干完的活被算进进度 ⇒ 白拿
            _b39.append("%s 接活前干完的活被算成「接活后新达成」（该拦住）：%s"
                        "（读数 %d · 基线 %d · 接活给的 %d）"
                        % (_k39, CQ._ckey(_r39), CQ._metric(p, _r39), _base_r39, _give_n39))
        if CQ._req_ok(p, _r39, _k39) != _expect39:
            _b39.append("%s 条件判定与「接活给的 + 目标」对不上：%s（该 %s · 实 %s）"
                        % (_k39, CQ._ckey(_r39), _expect39, CQ._req_ok(p, _r39, _k39)))
    _met39 = [r for r in _reqs39 if CQ._req_ok(p, r, _k39)]
    _unmet39 = [r for r in _reqs39 if not CQ._req_ok(p, r, _k39)]
    # 版面：**没满足的**每条都得逐行说出来；**已满足的**一行都不许留（呈现跟判定同一把尺子）
    for _r39 in _unmet39:
        for _ln39 in CQ._req_lines(p, _r39, _k39):
            if ("  " + _ln39) not in _o39:
                _b39.append("%s（`看 %d`）没满足却没逐行说清：%s 缺「%s」：%s"
                            % (_k39, _n39, CQ._ckey(_r39), _ln39, _o39[-4:]))
    for _r39 in _met39:
        for _ln39 in CQ._req_lines(p, _r39, _k39):
            if ("  " + _ln39) in _o39:
                _b39.append("%s（`看 %d`）已满足却还报「还差」：%s（%s）"
                            % (_k39, _n39, CQ._ckey(_r39), _ln39[:28]))
    # 『提示』跟着判定走：还有没满足的 ⇒ 不许说办完了；全满了 ⇒ 必须说办完了
    _h39 = CQ._hint_lines(p)
    _ready39 = any(_T39("SYS_HINT_JOB_READY", order=_n39) in ln for ln in _h39)
    if _unmet39 and _ready39:
        _b39.append("%s 接活后还有 %d 条没满足，『提示』却说办完了：%s"
                    % (_k39, len(_unmet39), _h39[:3]))
    if not _unmet39 and not _ready39:
        _b39.append("%s 条件全满足了，『提示』却没说办完了：%s" % (_k39, _h39[:3]))
    _pay0 = _drive(CQ.quest_deliver, p, "交 %d" % _n39)
    if _unmet39:
        # 判定说还差 ⇒ 『交』必须拦住、档上的经验／铜板／已交名单一个字都不许动
        if any(ln.startswith("交了") for ln in _pay0) \
                or _k39 in ((p.get("flags") or {}).get("quests_done") or []) \
                or int(p.get("exp") or 0) != _e0 or int(p.get("gold") or 0) != _g0:
            _b39.append("★ %s「%s」：**接活前就把活干完，接活后一句就交掉了（白拿经验/铜板）**：%s"
                        % (_k39, _x39["name"], _pay0[:3]))
            continue
    else:
        # ── 条件在接活那一刻**就**全达标 ⇒ 两种合法来源：状态型（enhance）· 接活那一下真给的
        #    （`give`）⇒ **有意**：接活后一句就交得掉（这就是上面那条线钉住的边界）
        if not any(ln.startswith("交了") for ln in _pay0):
            _b39.append("%s 条件在接活那一刻就全达标（状态型／接活给的）却交不掉：%s"
                        % (_k39, _pay0[:3]))
            continue
        _d0 = _tot39(p) - _t0
        _dg0 = int(p.get("gold") or 0) - _g0
        if _d0 != int(_x39["reward_exp"]) or _dg0 != int(_x39["reward_gold"]):
            _b39.append("%s 状态型那一跳奖励没照单入档：经验 %+d（应 +%d）· 铜板 %+d（应 +%d）"
                        % (_k39, _d0, _x39["reward_exp"], _dg0, _x39["reward_gold"]))
        _pay0b = _drive(CQ.quest_deliver, p, "交 %d" % _n39)
        if any(ln.startswith("交了") for ln in _pay0b) \
                or _tot39(p) != _t0 + int(_x39["reward_exp"]) \
                or int(p.get("gold") or 0) != _g0 + int(_x39["reward_gold"]):
            _b39.append("%s 状态型那一跳之后再交一次又动了档（奖励只许发一次）：%s"
                        % (_k39, _pay0b[:3]))
        _l39.append("★ 有意缺口 · %s「%s」：状态型条件（%s）接活前已达标 ⇒ 接活后一句就能交"
                    "（**不判增量** —— 取舍写在 `_req_ok` 的 docstring；要改口径得先有"
                    "「强化成功次数」那本账）" % (_k39, _x39["name"],
                                             "/".join(CQ._ckey(r) for r in _state39)))
        continue
    # ── 态二：接活后**真干一次** ⇒ 交得掉 · 奖励只发一次
    for _r39 in _reqs39:
        if not _bump39(p, _r39, CQ._n_of(_r39)):
            _b39.append("%s：条件 %s 推不动（造不出「接活后再干一次」的账）"
                        % (_k39, CQ._ckey(_r39)))
    _pay1 = _drive(CQ.quest_deliver, p, "交 %d" % _n39)
    _de = _tot39(p) - _t0
    _dg = int(p.get("gold") or 0) - _g0
    _rec39 = ((p.get("flags") or {}).get("quests") or {}).get(_k39) or {}
    if not any(ln.startswith("交了") for ln in _pay1):
        _b39.append("%s 接活后真干一次却交不掉：%s" % (_k39, _pay1[:3]))
    if _de != int(_x39["reward_exp"]) or _dg != int(_x39["reward_gold"]):
        _b39.append("%s 奖励没照单入档：经验 %+d（应 +%d）· 铜板 %+d（应 +%d）"
                    % (_k39, _de, _x39["reward_exp"], _dg, _x39["reward_gold"]))
    if int(_rec39.get("step") or -1) != _reql:
        _b39.append("%s：flags.quests[%s].step = %s ≠ 条件条数 %d"
                    % (_k39, _k39, _rec39.get("step"), _reql))
    _pay2 = _drive(CQ.quest_deliver, p, "交 %d" % _n39)
    if any(ln.startswith("交了") for ln in _pay2) \
            or _tot39(p) != _t0 + int(_x39["reward_exp"]) \
            or int(p.get("gold") or 0) != _g0 + int(_x39["reward_gold"]):
        _b39.append("%s 再交一次又动了档（奖励只许发一次）：%s" % (_k39, _pay2[:3]))
    if str(_x39.get("chain")) == "main":
        _l39.append("主%-2d %-7s 条件 %d 条（%s）：接活（活已干完）⇒ 还差 %d 条 + 拦住 · "
                    "接活后真干一次 ⇒ 交了（经验 +%d 铜板 +%d · 再交不动档）"
                    % (_n39, _x39["name"], _reql, "/".join(str(r.get("kind")) for r in _reqs39),
                       len(_unmet39), _de, _dg))
# ── ⑤ 老档兼容（**有意差异登记**）：没有基线 ⇒ 判定与改前逐字节相同（= 改前那一版）
_old39 = []
for _k9, _n9, _why in (("q_main_03", 3, "到过三条带"), ("q_main_04", 4, "万事俱备"),
                       ("q_side_13", 25, "万事俱备")):
    _x9 = QE.get(_k9) or {}
    _p9 = _sat_player(_x9, _k9, day=1)             # ← 直接塞 quests_active：**没有基线**的老档
    _p9["flags"] = dict(_p9.get("flags") or {}, card=1)
    _d9 = _drive(CQ.quest_deliver, _p9, "交 %d" % _n9)
    _ok9 = any(ln.startswith("交了") for ln in _d9)
    _old39.append("%s（%s · 无基线）⇒ %s" % (_k9, _why, "交得掉（与改前逐字相同）" if _ok9 else "拦住了 ✗"))
    if not _ok9:
        _b39.append("★ 老档兼容路径的方向变了：%s（%s · 没有基线）改前交得掉、现在交不掉"
                    % (_k9, _why))
# ── ⑥ 形状的另一半：没写 `require` 的老条目接活**不落**那一格
_p6 = _player(level=9, flags={"card": 1})
_a6 = _drive(CQ.quest_accept, _p6, "接 22")        # q_side_10「带路」：没写 require
_rec6 = ((_p6.get("flags") or {}).get("quests") or {}).get("q_side_10")
if _rec6 is not None:
    _b39.append("没写 `require` 的老条目接活竟然落了 flags.quests 那一格：%s" % (_rec6,))
# ── ④ 反证：把 `_set_base` 关掉（= 改前那一版）⇒ 主 3 / 主 4 / 主 11 **当场又白拿**
_REV39 = [("q_main_03", 3), ("q_main_04", 4), ("q_main_11", 11)]
_rev39 = []
_keep_sb39 = CQ._set_base
try:
    CQ._set_base = (lambda _pp, _kk, _xx: None)
    for _k9, _n9 in _REV39:
        _p9 = _mk39(QE.get(_k9) or {}, _k9)
        _drive(CQ.quest_accept, _p9, "接 %d" % _n9)
        _d9 = _drive(CQ.quest_deliver, _p9, "交 %d" % _n9)
        if any(ln.startswith("交了") for ln in _d9):
            _rev39.append((_k9, _d9[0][:24]))
finally:
    CQ._set_base = _keep_sb39
if len(_rev39) != len(_REV39):
    _b39.append("★ 反证没生效：把 `_set_base` 关掉之后只有 %d/%d 条又白拿"
                "（判据没咬在基线上）：%s" % (len(_rev39), len(_REV39), _rev39))
FC_Q.bind_host(**_FC_SAVED)                        # ★ 拨回真钟
(ok if not _b39 else bad)(
    "★ fxm3-questsnap ㊴：`require` 判「**接活后**新达成」—— 带 `require` 的条目**逐条**真敲"
    "（接 → 看 / 提示 / 交）：① 接活那一刻落进度基线（逐条等于当时读数；没写 require 的不落）· "
    "② 接活前把活干完 ⇒ 看还差 = 条件条数 + 提示不说办完了 + 交拦住且档不动 · "
    "③ 接活后真干一次 ⇒ 交得掉且奖励逐字入档、**只发一次** · ④ 反证（关掉 `_set_base`）⇒ "
    "主 3 / 主 4 / 主 11 当场又白拿 · ⑤ 老档（无基线）与改前逐字相同（有意兼容）"
    "（基线落 %d 条 · 坏 %s）" % (_base39[0], _b39 or "无"))
for _ln in _l39:
    print("      %s" % _ln)
print("      老档兼容（⑤）：%s" % " · ".join(_old39))
print("      反证（④ · 关掉 `_set_base`）：%s" % " · ".join("%s → %s" % t for t in _rev39))

for n in notes:
    print("  · " + n)

print()
print("判据 %d 条：%s" % (CHECKS[0], "全绿 ✓" if not fails else "有红 ✗（%d 条）" % len(fails)))
sys.exit(1 if fails else 0)
