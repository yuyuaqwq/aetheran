# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 第三组：公会与委托（B2-1）

契约同 cmds_ast：async generator，签名 (env, sink, uid, player)，参数从 env.text 解析。
落档：改了玩家档就必须 _save(env)（引擎不再每条消息整档回写）。

★ P-25：支线的「真前置」—— 交活时校验玩家是不是真做了
------------------------------------------------------
改前交活只判等级（主线）/ 一个没人写的 flag（支线）⇒ 「带他看塔」这类支线，
玩家做没做、做到哪一步，档上没账、交活也不看 —— 支线是假的。

两个形状（都在本文件里定死，别处照抄）：

① quests 域的 `require` —— **只有需要前置的条目才写**（没写的老条目行为逐字节不变）：
     {"kind": "visit", "map": <图 id>, "node": <节点 id>}    去过这一站（node 省了 = 这张图哪儿都算）
     {"kind": "kill",  "monster": <怪 id>, "n": <只数>}      图鉴里那只怪已经打掉过 n 只
     {"kind": "kill",  "role": <role_key>, "n": <只数>}      ★ B3-11：那一**档**的怪合计打掉过 n 只
                                                            （role_key ∈ monsters 的 normal/elite/
                                                             chief …；认不出的档 = 计数 0 = 没满足）
     {"kind": "item",  "item": <物品 id>, "n": <份数>}       背包里有 n 份
     ★ B3-13 又加了四种（账都在现有档上，见本文件抬头 B3-13 一节）：
     {"kind": "enhance", "n": <级>} · {"kind": "cook", "n": <次>}（可带 `quality` 品阶）·
     {"kind": "talk", "npc": <npc id>, "n": <次>} · {"kind": "ask", "n": <人>}；
     而 `{"kind": "kill", "role": …, "daily": true}` = 悬赏那条**当天点名**的那一只。
   写一条 dict，或写一串 dict（**全部**满足才算做了）；认不出的 kind 一律算没满足（fail-closed，
   不静默放行）。中文的 `objective` **不解析** —— 条件的真源是 `require`。
   ★ `role` 与 `monster` 二选一（都写只看 `monster`）；档名只在**呈现**那一行从 monsters 域透传，
     代码不认中文档名。

② 玩家档 `flags.quests`（格子原来就有，不新建容器）：
     flags.quests = {<quest_id>: {"step": <已满足的条件条数>, "done": true, "at": <游戏日>}}
   交活成功那一下才写（此刻 step 恒等于条件总条数；没写 require 的老条目 = 0 —— 它只有「交没交」两态）。
   形状先摆好：将来想让打怪 / 采集那两处「顺手记一步」，往同一个格子累加 step 就行。

★ 三种条件的数据在档上都真存在（本模块**只回头查**，一个都不写）：
   去过哪儿 → `foot.nodes`（第一回到）/ `foot.visits`（去过几回）—— codex.note_visit / note_step
              挂在移动那几处（cmds_ast，别改）
   打过什么 → `books.monster[<怪>].kills` —— codex.note_kill 挂在打怪那一下（cmds_battle，别改）
   手上有啥 → `bag[<物品>]` —— loot.add_to_bag（采集 / 掉落 / 烹饪 / 买，别改）

★ B3-3 生活职业任务（解 P-14 的甲案 · 设计真源 `28_生活职业任务_设计_v1.md`）
------------------------------------------------------------------------
不建新域：quests 域多一个**分类维度** `trade`（"采集" | "垂钓" | "烹饪" | "强化"），
8 条与现有支线重合的**就地合并**（只加字段、不复制文案），另 8 条新的补进同一个域
（`kind: 生活` · `chain: trade`）—— 玩家侧两个入口（『悬赏』找玛莎 / 『副业』找手艺人）吃同一份数据。

  · 四个副业的**名字与顺序**是数据（`quests._meta.trades`，生成器从 28 §三 + 21 §二 解析）
    —— 本模块只读它、只传槽位，不认任何中文副业名（加第五个副业 = 改数据）
  · `_quests()` 是**取条目**的唯一一口：`_meta` 那类私有键不是条目（与 recipes / codex 同口径）
  · 生活任务**一律写 `require`**（上面那三型）—— 不然会落到 `flags.side_*` 那条死路径上
    （那个键仓库里没有任何地方写）。今天现有的 12 条老支线仍在死路径上（P-25 §② 未收口，见报告）
  · 落法（重跑）：`python scripts/rebuild_prof_quests.py`（从真源解析 · 数值不手打）
  · 判据：`scripts/probe_quests.py` ⑪（trade 四值 · 16 条与 21 §二 逐条对账 · 条件真能验 · 副业指令真跑）

★ B3-6c 主线三段行文归位 texts（解 P-17 甲案）
------------------------------------------------
主线 12 条的「接 / 进行中 / 交」三段行文原先内联在 quests 域的 `story` / `progress_text` /
`deliver_text`（写着「待写」「（进行中：…）」），而 texts 域的 `QUEST_MAIN%02d_{STORY,PROGRESS,
DELIVER}` 36 条**谁也读不到** —— 两处真源。裁定甲案：**真源归 texts**。

  · 域里那三个字段**主线已裁掉**（`content/data/quests.json`）
  · 消费端只按 `chain` + `order` 映射取槽位（`_slot_of` / `_beat` 两个口）——
    **不拿名字拼键名**，一个中文都不内联
  · `story` 的落点 = `接 <编号>` 那一下（槽位出处自己写着「接时行文」）；
    `progress_text` = 交活没做完那一行；`deliver_text` = 交掉之后那一行
  · 判据：`scripts/probe_quests.py` ⑲（12 条真取到 · 与 24 号文档逐条对账 · 36 条非占位）

★ B3-8 支线 18 / 生活 8 / 悬赏 3 三段行文归位（同一套办法 · 一次收完）
------------------------------------------------------------------
B3-6c 只做了主线 12 条；剩下 29 条（支线 18 · 生活 8 · 悬赏 3）仍读域内字段 —— `story` 是
「（待写）」、`progress_text` 是备注腔「（进行中：…）」，而它们的 `deliver_text` 今天**是玩家
看得到的**（交活那一行）。本批照同一套映射把这 29 条也归位：

  · 槽位键 = 链模板 + `order`（`QUEST_SIDE%02d` 13–30 · `QUEST_TRADE%02d` 31–38 ·
    `QUEST_BOUNTY%02d` 101–103）—— 与主线那 36 条同一个形状（`_SLOT_TPL` 四个字面量）
  · 域里那三个字段**29 条也裁掉**（现在是「四条链一条不剩」；探针 ㉓ 钉着「域里 0 处」）
  · 文案依据只有三份真源：支线 = `24 §二`（步骤 / 奖励）· 生活 = `28 §四` + `21 §二` ·
    悬赏 = `24 §二` 的悬赏板块 + `05 §一`（报酬区间 / 经验 1/8）—— 文档只给一句就只写那一拍
  · 悬赏那三条的「交时行文」= 归位前域里的 `deliver_text` **逐字保留**（玩家看到的字一个没动）
  · 判据：`scripts/probe_quests.py` ㉓㉔㉕㉖（29 条真取到槽位 · 与三份文档逐条对账 ·
    87 条非占位 · 三类各真跑一遍接/交）

★ B3-11 悬赏三档的数值与交付条件 · 支线「还石头」的交付条件
--------------------------------------------------------
解两个活口：① 悬赏 `reward_exp` 是手打的旧数（125 / 640 / 3920），与 `05 §一`「经验 = 同级
升级需求的 1/8」对不上；② `_obj_ok` 对没写 `require` 的条目去看 `flags.side_<名字>`，而那个键
**仓库里没有任何地方写** ⇒ 今天 12 条支线 + 3 条悬赏都交不掉（P-25 §②）。

  · 数值与条件**一律从真源现算**：`python scripts/rebuild_quest_gates.py`（幂等 · `--dry` 先看）
      - 经验 = `exp_need(该档 min_level) × N/D`（N/D 从 05 §一 与 24 §二 两处解析，必须一致）
      - 悬赏条件 = 「那一档的怪任意一只打掉过」（`kill` + `role`）—— 24 §二 写「打掉**指定的**
        普通怪」，「指定的」= 悬赏板每天轮换挑一只，而**轮换那一步数据面上还没有** ⇒ 先落「档内任意
        一只」（比死路径强、比「指定的那一只」宽；轮换落地时把 `role` 换成 `monster` 即可）
      - 支线「还石头」条件 = `15_彩蛋域口径_v1 §二` 那句「`q_side_13「还石头」的交待就是彩蛋 2`」
        的条件（`hold` → `item` · `where` → `visit`；`read` 那一步是彩蛋自己的，任务不取）
  · 判据：`scripts/probe_quests.py` ㉗（悬赏三档经验/钱逐条对账）· ㉘（18 条支线的交付真跑矩阵：
    交得掉的**真交一次**，交不掉的钉住名单 + 逐条原因）

★ B3-13 支线的另外 6 条条件 · 悬赏「指定的」落地（每日轮换）
-----------------------------------------------------------
P-25 §② 剩下的 11 条支线里，**能按真源文档补上正当条件的 6 条**这一批补齐；悬赏那条
「打掉**指定的**普通 / 精英 / 头目怪」也从 b41 的宽口径（该档任意一只打掉过）收成
**当日点名的那一只**（轮换 = 游戏日 + 档位，可复现）。

条件形状（真源 = `06_第一阶段垂直切片/24_任务线_v1.md §二` 的「步骤」列 ·
`21_长期目标层_v1.md §二` 同条；**每条的依据**写在生成器 `scripts/rebuild_quest_gates.py`
的规则表里，数（+3 / 三次 / 三道菜 / 三个人）都从那份文档现取）：

  {"kind": "enhance", "n": <级>}                  档上**有一件**装备的强化等级 ≥ n
                                                  （账 = `p.enhance[<装备>]` 的 `lv`，写入口 cmds_recipe.enhance）
  {"kind": "cook", "n": <次>}                     下过锅 ≥ n 次（账 = `flags.cooked[<配方>]`，写入口 cmds_recipe.cook）
  {"kind": "cook", "quality": <品阶>, "n": <次>}  只数**用了那一品阶食材**的配方（品阶现取自 items 域的
                                                  `quality` —— 数据比数据，代码不认中文；「用稀有食材做一次」那条）
  {"kind": "talk", "npc": <npc id>, "n": <次>}    跟这个人搭过 ≥ n 次话（账 = `flags.talked[<对话树>]`，
                                                  写入口 cmds_talk；npc → 对话树走 `npcs.dialogue`）
  {"kind": "ask", "n": <人>}                      搭过话的**人** ≥ n 个（同一本账；只数域里真有对话树的那些键）
  {"kind": "kill", "role": <role_key>, "n": <只>, "daily": true}
                                                  ★ 今天点名的那一只（见 `_daily_pick`）：该档的怪按 id 排序后取
                                                  第 `(游戏日-1) % 档内只数 + 1` 只 —— 同一日同档必是同结果，
                                                  跨日必换（档内只数 > 1）；游戏日读档上那一格（`codex.today`）

  ★ fail-closed：认不出的 kind / 认不出的档（取不到怪）/ 取不到对话树的 npc ⇒ 一律**没满足**。
  ★ 老条目（没写 `require`）的行为逐字节不变；`flags.side_<名字>` 那条死路径仍只服务它们
    —— 今天还剩 5 条（灯油 / 信 / 隐藏线 flag / 「他的口味」没点明哪一道 / 目的地没写），
    逐条理由与「要补的什么」在工作树 `_notes.md`。

★ B4-2 主线 12 条**也走 `require`**（解 P-25 §①：不许「接了就交」）
---------------------------------------------------------------
改前 `_obj_ok` 对主线只看 `level >= min_level` ⇒ 1 级接 1 级主线，一句『交 1』直接过，
目标那几步（观察 → 看见石头上的字 → 试着读 → 问玛莎）一步都不用做。

  · 条件真源 = `06_第一阶段垂直切片/24_任务线_v1.md §一` 每块的「步骤」行（**含跨行的续行**）
  · 落法：`python scripts/rebuild_quest_gates.py`（幂等 · `--dry` 先看）—— 每条条件的**目标**
    必须在本条自己的「步骤」行里点名；能落到现成形状上的那几步各落一条，形状只用
    `visit` / `kill` / `item` / `talk`（**不加新形状**，新形状要单独立项 + 鱼鱼点头）
  · 落不了的几拍（「观察」「试着读」「读他留下的字条」这类**档上没账**的动作）不硬凑：
    缺口逐条登记在工作树 `_notes.md`
  · 判据：`scripts/probe_quests.py` ㉑（真跑四拍：接 / 没做完 / 接了就交拦住 / 万事俱备）·
    ㉜（逐步记账：缺一步交不掉 · 全满足则 `flags.quests[<id>].step == 条件条数`）

★ B4-27 ② P-53：`接 <编号>` 先办见习证那道门（公会线闭环）
--------------------------------------------------------
改前 `quest_accept` 一眼都不看 `flags.card` —— 而那个证（`登记` 办的）**只有『评级』读**，
「公会 → 登记（见习证）→ 悬赏 → 接活」这条线断在最后一节（办出来的证等于白办）。

  · 口径：两份真源打架（`04_指令总表 §二` 守卫 = **已登记 · 未接**；
    `03_风车镇 §一` = 等级够 · 未接）⇒ 按**命令表真源**落（= 台账 P-53「我的倾向：加」）
  · 那一格**唯一读口** = `cmds_self.has_card`（B4-14 立的规矩，probe_cmds ⑲ 静态守卫钉着）
  · 门的**位置**：认单子 → 「已经接过」（这条单子自己的状态）→ **这道门** → 「等级不够」
    —— 手上真有这条委托的档不许被回一句「你没有证」的假话
  · 没办证的档 ⇒ `SYS_JOB_NEED_CARD` 一行、**档一个字不动**（fail-closed 不静默放行）
  · 判据：`scripts/probe_quests.py` ㉝（三档真敲 + 档上副作用 + 撤改验证）

★ B4-27 ③ P-56：`放弃` 的冷却（1 个游戏日）
--------------------------------------------
真源 `06_第一阶段垂直切片/05_玩法数值口径_v1.md §一`：「放弃 ｜ **冷却 1 天**；**掉一点声望**，
不影响主线」。改前 `quest_abandon` 把那一条从 `flags.quests_active` 摘掉就完事 —— 没有冷却。

  · **本批只落冷却那半**：同一个**游戏日**只许放弃一条（第二条 ⇒ `SYS_JOB_ABANDON_CD` 一行、档不动）
  · 那一格 = `flags.abandon_day`（既有容器 · 不新建）；写口/读口各一处（`_abandon_day`）
  · 「今天」= `codex.today` → `calendar.day_now()`（**那根钟**，与悬赏轮换同一个口）——
    不是档上那格 `p["day"]`（B4-9：那只是 `tick()` 的跨日标记）
  · ★ **「掉一点声望」这半没落**：全仓**没有声望这个容器**（`05 §一` 也没给数）⇒ 登记待裁
    （工作树 `_notes.md`「待鱼鱼拍板」），不自己造第二本账（K74 那一族：别跟 `评级` 开成两处口径）
  · 判据：`scripts/probe_quests.py` ㉞（三拍真敲 + 跨日 + 档上那格假的也不许影响判定）

★ g3-quests2 三件（「差最后一步」那一批 · 2026-09-26）
---------------------------------------------------
① 悬赏轮换池按**可遇性**收窄（`_pool_of` / `_encounterable`）：
   旧规格 = 该档**全部**怪按 id 排序取第 `(游戏日-1)%n+1` 只 ⇒ 可能点名一只按这一档标称等级
   在它自己写明的站上**挑不出来**的怪（`normal` 档点到「野狗」，1 级档的玩家在野狗窝只能撞上
   田鼠 / 拾荒野狗 / 林鸦 —— 玩家报告 P1 BUG-2）；前一轮只补了信息面（「它出没在：…」），
   不够：**池子**要从「真碰得上的」里挑。
   新规格 = 池 = 该档的怪 ∩ **可遇集合**（该怪 `habitat` 写明的**每一站**上，按**该档 `min_level`**
   用 `combat.encounter_cand`（遇敌那一把尺子：habitat × 等级最近前 3）都挑得出来）；
   轮换算法一个字没动（仍是「按 id 排序 + 游戏日取模」）—— 只把池子收窄。
   真源：`24 §二 悬赏板`（「打掉**指定的**普通 / 精英 / 头目怪」＋「每天轮换挑一只」）·
   `14_怪物原型_v1 §三`（每只怪在哪一档、出没在哪）· `05 §一`（按目标档位给报酬）。
   判据：`scripts/probe_quests.py` ㉛（探针**另写一份**可遇集合 + 逐日对账 + 反证关掉过滤当场红）·
   `scripts/probe_qloop.py` ②（逐日真敲「还差…」与出没地那一行）。

② 支线「还石头」**接活时真发东西**（`quests.<id>.give` + `_hand_over`）：
   改前 `接 25` 一个东西都不发（`QUEST_SIDE25_STORY` 那句「小满把那块石头塞给你」是空话，
   玩家只能自己去骨田挖）；现在接活那一下真把这件东西给到手上（走唯一口 `loot.add_to_bag`，
   并印一行「得到：…」）。真源 = `15_彩蛋域口径_v1 §二` 第 2 行（「q_side_13「还石头」的交待
   就是彩蛋 2，**小满的石头 = 骨田捡的刻字石片**」）＋ `17 §QUEST_SIDE25_STORY`。
   域里的 `give` 是**生成物**（`scripts/rebuild_quest_gates.py` 从同一份真源现取）。
   判据：`scripts/probe_qloop.py` ⑧（正例 + 反证：拿掉 `give` ⇒ 一个东西都不发）。

③ 对话旗标族（`main*_done` / `quest_*_done` / `main09_active` / `nameline_done`）**补写端**：
   那一族 slug 只有读端（`cmds_talk._pick_indexed` 的 `flag` 那一支）、**全仓没有写端**
   ⇒ 域里 12 条台词永久出不来。现在读端走 `content/prog.flag_ok`（表里的 slug 一律以
   **真实进度**为准）、写端走 `content/prog.resync`（接 / 交 / 放弃那三处照真实进度重写）。
   判据：`scripts/probe_qloop.py` ⑨（写端三拍 + 读端真搭话 + 两条反证：没做到 ⇒ 旗标没写且
   那句出不来；只塞一个脏旗标 ⇒ 那句**照样**出不来）。
"""
from __future__ import annotations

from .cmds_ast import _data, _p, _save, _map_of, _name_of_node, T, add_exp
from .town import _func_node, town_gate
from .cmds_talk import _arg
from .cmds_ast import _npcs_here
from . import codex as CX            # 打怪记录（books.monster.kills）的**唯一**读口
from . import loot as LT             # 东西的名字（呈现口不许漏机器键 —— 名字从这里取）
from . import ranks as RK            # 评级那一档（档名/门槛的唯一读口 —— B4-16）
from . import combat as CB           # ★ 本波：遇敌那把尺子（`encounter_cand`）—— 悬赏池按它收窄
from . import prog as PROG           # ★ 本波：对话旗标族（`main*_done` 那一族）的写端


def _mine(p):
    """进行中的委托（id 列表）。"""
    v = (p.get("flags") or {}).get("quests_active")
    return list(v) if isinstance(v, list) else []


def _done(p):
    v = (p.get("flags") or {}).get("quests_done")
    return list(v) if isinstance(v, list) else []


def _set(p, key, val):
    f = dict(p.get("flags") or {})
    f[key] = val
    p["flags"] = f


# ── B3-6c / B3-8：任务三段行文（接 / 进行中 / 交）都从 texts 槽位取 ─────────────
# 真源：`00_总纲/17_文案收口口径_v1.md` 的 `QUEST_{MAIN,SIDE,TRADE,BOUNTY}%02d_{STORY,PROGRESS,
# DELIVER}` 表（B3-6c 主线 36 条 + B3-8 支线/生活/悬赏 87 条 = 123 条）。
# P-17 甲案：quests 域内联的 story / progress_text / deliver_text 三个字段**四条链全裁掉** ——
# 消费端只按 `chain` + `order` 映射取槽位（一个中文都不内联）。
#   · `order` 是域里现成的稳定标识（『接 <编号>』用的就是它：主线 1–12 · 支线 13–30 ·
#     生活 31–38 · 悬赏档 101–103），所以键名 = 链模板 + 编号 —— 不拿名字拼键名。
#   · 四条链的模板写成**字面量**（`_SLOT_TPL`）：probe_copy ⑤ 的「口径表每条都被引用」认这种
#     `前缀%02d_%s` 形状（模板拼出来的键也算引用），别改成运行时拼串。
#   · 认不出的链**不许静默留白**：回一个 fail-closed 哨兵键 —— `T()` 当场回显
#     `[MISSING TEXT: QUEST_UNMAPPED_STORY]`（探针 ㉓ 也钉着「域里每条都算得出真槽位」）。
_SLOT_TPL = {"main": "QUEST_MAIN%02d_%s", "side": "QUEST_SIDE%02d_%s",
             "trade": "QUEST_TRADE%02d_%s", "bounty": "QUEST_BOUNTY%02d_%s"}


def _slot_of(x, part):
    """这条委托的这一拍 → 槽位名（`QUEST_<链>%02d_<PART>`）；认不出的链 ⇒ fail-closed 哨兵键。

    ★ 只认「链 + 编号」这一个映射 —— 不拿名字拼键名（名字改一个字，槽位不该跟着漂）。
    ★ 编号对不上（写缺了 / 超出台账）时 `T()` 会把键名回显出来（fail-closed），不静默留白。
    """
    tpl = _SLOT_TPL.get(str(x.get("chain") or ""))
    if tpl is None:
        return "QUEST_UNMAPPED_%s" % part
    return tpl % (int(x.get("order") or 0), part)


def _beat(x, part):
    """三段行文的一口（唯一取口）—— 四条链都走 texts 槽位（域内那三个字段已裁掉）。"""
    return T(_slot_of(x, part))


# ── 副业（B3-3 · 解 P-14「选甲」）：四个副业的声明在 quests 域的 `_meta.trades` ──────
def _quests():
    """quests 域里的**条目**（`_meta` 那类私有键不算条目 —— 与 recipes / codex 等域同口径）。"""
    return {k: v for k, v in _data("quests").items() if not str(k).startswith("_")}


def _trade_meta():
    """四个副业的声明（顺序 / 名字 / 「这条线是干什么的」）—— 全在数据里，代码不造中文。

    ★ 代码只认「有哪些副业」这件事本身：顺序与名字从 `_meta.trades` 读（生成器从
      `28 §三` + `21 §二` 解析落域）—— 加第五个副业是改数据，不是改代码。
    """
    return list((_data("quests").get("_meta") or {}).get("trades") or [])


def _trade_rows():
    """按副业分好的任务（每组按 `order` 排）—— 分组键就是条目自己的 `trade`（不给 = 不是副业任务）。"""
    out = {}
    for k, v in _quests().items():
        t = v.get("trade")
        if t:
            out.setdefault(t, []).append((k, v))
    for t in out:
        out[t].sort(key=lambda kv: kv[1].get("order") or 0)
    return out


async def trade(env, sink, uid, player):
    """`副业 [名字]` —— 按副业列任务（与『悬赏』并列的第二个入口：悬赏是玛莎的公会委托，副业是手艺人自己的活）。

    无参：四个副业各自任务数 + 一句「这条线是干什么的」（那句从数据来）
    带参：那一个副业下的每一条（可接 / 进行中 / 已交三种标记）
    """
    p = _p(player)
    meta = _trade_meta()
    want = _arg(env)
    act, done = _mine(p), _done(p)
    rows = _trade_rows()
    if not want:
        yield T("SYS_TRADE_HEAD")
        for t in meta:
            yield "  " + T("SYS_TRADE_ROW", trade=t.get("trade"),
                           n=len(rows.get(t.get("trade")) or []), what=t.get("what") or "")
        yield T("SYS_TRADE_HOW")
        return
    hit = next((t for t in meta if want == t.get("trade")), None)
    if hit is None:
        yield T("SYS_TRADE_NOSUCH", name=want,
                list=" · ".join("「%s」" % t.get("trade") for t in meta))
        return
    one = rows.get(hit["trade"]) or []
    yield T("SYS_TRADE_LIST_HEAD", trade=hit["trade"], n=len(one))
    for k, x in one:
        mark = T("SYS_BOARD_ACTIVE") if k in act else \
            (T("SYS_TRADE_MARK_DONE") if k in done else T("SYS_TRADE_MARK_CAN"))
        yield "  " + T("SYS_TRADE_ONE", order=x.get("order"), name=x.get("name"),
                       mark=mark, objective=x.get("objective"))
    yield T("SYS_TRADE_HOW")


# ── 前置条件（P-25）：两个形状见文件抬头 ① ② ────────────────────────
def _require_of(x):
    """这条委托的机器可读前置 —— 没写 = 空表（交活走老判据）。一条 dict 或一串 dict。"""
    r = x.get("require")
    if isinstance(r, dict):
        return [r]
    if isinstance(r, list):
        return [e for e in r if isinstance(e, dict)]
    return []


def _n_of(r):
    """要几个 / 几只（没写 = 1；写成 0 或负数一律当 1 —— 条件不许是白给的）。"""
    try:
        return max(1, int(r.get("n") or 1))
    except (TypeError, ValueError):
        return 1


def _been(p, loc, node=""):
    """去过吗？—— 档上足迹两格都算：`foot.nodes`（第一回到）与 `foot.visits`（去过几回）。"""
    f = p.get("foot")
    f = f if isinstance(f, dict) else {}
    keys = set((f.get("nodes") or {}).keys()) | set((f.get("visits") or {}).keys())
    pre = loc + ":"
    if node:
        return pre + node in keys
    return any(k.startswith(pre) for k in keys)


def _shadow(p):
    """只读影子档：`books` / `foot` 各拷一层。

    为什么：codex 的读口（`kills_of`）走 `_books()`，那把缺的格子**补齐** ——
    在真档上调它，等于「查一次进度」就往玩家档里塞空容器（K57 那族）。
    """
    s = dict(p)
    for k in ("books", "foot"):
        v = p.get(k)
        if isinstance(v, dict):
            s[k] = dict(v)
    return s


#: ★ QB-2（试玩卡死 1）：**故事类**门类 —— 只有这两类才谈「一件东西本身就是那件东西」
#:   （两个取值是域里现成的 `kind_key`，代码不认中文）。
_STORY_KINDS = ("keepsake", "clue")


def _unid_carries(uid, iid):
    """这件**还没鉴定**的东西，是不是**就是** `iid`（同一件东西，只是还没认出来）？

    真源 · 为什么要有它（试玩报告 P1 BUG-1「委托 25 还石头永远交不掉」，玩家的判据原话是
    「单子要的就是玩家在骨田挖到的那件东西（**描述一字不差**）」）：
      · `00_总纲/15_彩蛋域口径_v1.md §二` 第 2 行：彩蛋 2 条件 `hold=i_token_stone_shard`
        （依据栏「q_side_13「还石头」的交待就是彩蛋 2，小满的石头 = **骨田捡的刻字石片**」）
      · `06_第一阶段垂直切片/06_装备获取与支线玩法_v1.md §1.2`：「刻字的石片 ← **骨田「挖掘」挖出来**」
      · `00_总纲/27_掉落的惊喜感与未鉴定_v1.md §三`：骨田挖到的是**未鉴定**的那件，
        它的 `hint` = 那件信物的 `lore`（「上面有字。不是这儿的话。」）—— **逐字相同**。

    判据三条（数据比数据，代码不认中文；不许放宽成「池里有就算」）：
      · 目标必须是**故事类**（items 域的 `kind_key` ∈ keepsake / clue）—— 材料 / 垃圾 / 装备不算
        （不然「找一块旧铁」会被一件未鉴定顶过去）
      · 容器自己那句 `hint` 与目标那句 `lore` **逐字相同**（容器自己写着它是谁）
      · 池里那一格真写着它（`out` 逐字相等）
    """
    it = LT.items().get(str(iid or "")) or {}
    if str(it.get("kind_key") or "") not in _STORY_KINDS:
        return False
    said = str(it.get("lore") or "")
    if not said:
        return False
    u = LT.pools().get(str(uid or "")) or {}
    if u.get("kind_key") != "unidentified" or str(u.get("hint") or "") != said:
        return False
    return any(str((e or {}).get("out") or "") == str(iid) for e in (u.get("pool") or []))


def _bag_n(p, iid):
    """背包里有几件 `iid`。

    ★ QB-2：**未鉴定**的那件容器如果唯一能开出的就是它（`_unid_carries`），也数进来 ——
      玩家手上那件「一块刻着字的石片」与单子要的「刻字的石片」是同一件东西，只是还没认出来。
    """
    bag = p.get("bag") or {}
    n = 0
    try:
        n += int(bag.get(iid) or 0)
    except (TypeError, ValueError):
        pass
    for k, v in bag.items():
        if not str(k).startswith("unid_") or not _unid_carries(k, iid):
            continue
        try:
            n += int(v or 0)
        except (TypeError, ValueError):
            continue
    return n


def _req_ok(p, r):
    """一条条件满足没有（认不出的 kind 一律算没满足 —— fail-closed，不静默放行）。"""
    kind = r.get("kind")
    if kind == "visit":
        return _been(p, str(r.get("map") or ""), str(r.get("node") or ""))
    if kind == "kill":
        # ★ B3-11：`kill` 两种写法 —— 点名一只（`monster`）或点**某一档**（`role`，见 `_role_ids`）。
        #   两个都不写 ⇒ 没满足（fail-closed）；认不出的 role ⇒ 那一档取不到怪 ⇒ 计数 0 ⇒ 没满足。
        # ★ B3-13：点档 + `daily` ⇒ 只算**今天点名的那一只**（`_kill_have` 里那一条）。
        return bool(str(r.get("monster") or "") or str(r.get("role") or "")) \
            and _kill_have(p, r) >= _n_of(r)
    if kind == "item":
        iid = str(r.get("item") or "")
        return bool(iid) and _bag_n(p, iid) >= _n_of(r)
    if kind == "enhance":                       # ★ B3-13：有一件装备强化到 ≥ n
        return _enhance_have(p) >= _n_of(r)
    if kind == "cook":                          # ★ B3-13：下过锅 ≥ n 次（可只数某一品阶的食材）
        return _cook_have(p, r) >= _n_of(r)
    if kind == "talk":                          # ★ B3-13：跟这个人搭过 ≥ n 次话
        return bool(str(r.get("npc") or "")) and _talk_have(p, r.get("npc")) >= _n_of(r)
    if kind == "ask":                           # ★ B3-13：搭过话的**人** ≥ n 个
        return _asked_have(p) >= _n_of(r)
    return False


def _role_ids(role):
    """机器键（`monsters.role_key`）→ 这一档的怪 id 表。认不出的档回**空表**（fail-closed）。

    ★ 为什么按 `role_key` 而不是中文档名：`cmds_battle` / `combat` 那两处分档也一律比 ASCII
      `role_key`（中文只用于呈现）—— 条件判定与战斗分档走同一根轴。中文是数据，不是代码。
    """
    if not role:
        return []
    return [k for k, m in _data("monsters").items()
            if not str(k).startswith("_") and m.get("role_key") == role]


def _role_name(role):
    """这一档的**中文档名**（从 monsters 域透传，代码不造中文；认不出的档回空串）。"""
    for m in _data("monsters").values():
        if m.get("role_key") == role:
            return str(m.get("role") or "")
    return ""


def _tier_level(role) -> int:
    """这一档悬赏**自己标的等级**（= 那条单子的 `min_level`）—— 从 quests 域里现查。

    ★ 为什么要有它：轮换池按「**这一档标称等级下真碰得上**」收窄（见 `_pool_of`），
      而「这个等级」不能手打一个数 —— 它就是那条单子上印给玩家看的那个数
      （`SYS_BOARD_BOUNTY_ROW` / `SYS_JOB_LOWLEVEL` 用的同一格）。
      认不出（没有哪条悬赏点名这个档）⇒ 0 ⇒ 池空 ⇒ 一律没满足（fail-closed，不猜）。
    """
    for v in _quests().values():
        for r in _require_of(v):
            if r.get("kind") == "kill" and str(r.get("role") or "") == str(role or ""):
                return int(v.get("min_level") or 0)
    return 0


def _spots_of(mid) -> list:
    """这只怪 `habitat` 说得上话的**真图真节点**表 → `[(图, 节点)]`（取不到回空表）。

    ★ 与挑怪那一边同一格（`habitat.maps` 必给，给了 `nodes` 再收窄）—— 不另开「怪在哪」的口径。
    """
    hb = (_data("monsters").get(str(mid or "")) or {}).get("habitat") or {}
    nodes = [str(n) for n in (hb.get("nodes") or []) if n]
    out = []
    for m in (hb.get("maps") or []):
        mv = _map_of(str(m)) or {}
        for nd in (mv.get("nodes") or []):
            nid = str((nd or {}).get("id") or "")
            if not nid:
                continue
            if nodes and nid not in nodes:
                continue
            out.append((str(m), nid))
    return out


def _encounterable(mid, level) -> bool:
    """★ 悬赏轮换池的**可遇性**：这只怪在它自己写明的**每一站**上、按这个等级，都挑得出来吗。

    ★ 尺子 = `combat.encounter_cand`（玩家敲『攻击』那一下真挑怪用的**同一个口**）：
      「这一站 habitat 说得上话的怪，按等级最近取前 3」——不在前 3 里 = 在这一站**碰不上**。
    ★ 为什么是「每一站」而不是「有一站就行」：单子把它的出没地点**逐站列给玩家看**
      （`_habitat_of` → `SYS_JOB_REQ_MON_WHERE`），所以每一站都得真碰得上；否则玩家照着
      单子走到某一站，撞到的却是别人（报告 P1 BUG-2 的原样：在野狗窝杀成 4 回「拾荒野狗」
      而单子要的「野狗」一次没出）。
    ★ fail-closed：没有 habitat / 站表为空 / 等级取不到 ⇒ **不算可遇**（不猜）。
    """
    try:
        lv = int(level)
    except (TypeError, ValueError):
        return False
    if lv <= 0 or not mid:
        return False
    spots = _spots_of(mid)
    if not spots:
        return False
    mon = _data("monsters")
    for loc, nd in spots:
        _cand, top = CB.encounter_cand(mon, loc, nd, lv)
        if mid not in top:
            return False
    return True


def _pool_of(role) -> list:
    """★ 这一档的**轮换池** = 该档的怪 ∩ **可遇集合**（按 id 排序 —— 稳定序，与书写顺序无关）。

    ★ 规格变更（本波 · g3-quests2）：**收窄**成「本地图真刷得出的怪」。
      旧规格 = 该档**全部**怪（只看 `monsters.role_key`）按 id 排序取第 `(游戏日-1)%n+1` 只
      ⇒ 可能点名一只**按这一档标称等级、在它自己写明的站上根本挑不出来**的怪
      （`normal` 档点到 `ms_wild_dog`「野狗」时，1 级档的玩家在野狗窝只能撞上
       田鼠 / 拾荒野狗 / 林鸦 —— 玩家报告 P1 BUG-2）。
      新规格只把**池子**收窄，轮换算法一个字没动（仍是「按 id 排序 + 游戏日取模」）。
      真源：`24_任务线_v1 §二 悬赏板`「打掉**指定的**普通 / 精英 / 头目怪」＋ 同条的
      「每天轮换挑一只」＋ `14_怪物原型_v1 §三`（每只怪在哪儿、是哪一档）＋ `05 §一`
      （悬赏按**目标档位**给报酬 ⇒ 单子点名的那只必须在**那一档**碰得上）。
      ⇒ 「指定的」= 每天轮换挑一只 **碰得上的**。
    """
    lv = _tier_level(role)
    return sorted(mid for mid in _role_ids(role) if _encounterable(mid, lv))


def _daily_pick(role, p):
    """★ B3-13：今天这一档**点名**的那一只（「悬赏板每天轮换挑一只」的数据面）。

    轮换 = 该档的**可遇集合**（`_pool_of` —— 本波按可遇性收窄；旧规格是该档全部怪）
    按 **id 排序**（稳定序 —— 与域里的书写顺序无关）之后，按**游戏日**
    取第 `(游戏日 - 1) % 池内只数 + 1` 只：
      · 同一日、同一档 ⇒ 必是同结果（两个进程也一样 —— 那一天由**那一根钟**唯一决定）
      · ★ B4-9：那一天的来源 = `codex.today(p)` = `calendar.day_now()`（**现算**）——
        原先读的是档上那格 `day`，可它只是 `tick()` 的跨日标记（只有「时间 / 采集 / 建号」
        几个入口在刷）⇒ 悬赏会卡在「上一回 tick 那天」甚至 0 上（今天日期戳那一族一起收的）
      · 跨日 ⇒ 必换（池内只数 > 1；「轮换」的原意就是这个）
      · 游戏日读不到（老档没那一格）= 0 ⇒ 退到池内最后一只：**仍然是确定值，不是随机**
      · 认不出的档 / 空池（该档一只都碰不上）⇒ 空串（调用方一律当「没满足」算 —— fail-closed）
    """
    ids = _pool_of(str(role or ""))
    if not ids:
        return ""
    return ids[(int(CX.today(p)) - 1) % len(ids)]


def _kill_have(p, r):
    """条件「打掉过几只」的**已达成数**（就是档上那本怪物谱的击杀账 —— 只读，不写）。"""
    mid = str(r.get("monster") or "")
    s = _shadow(p)
    if mid:
        return CX.kills_of(s, mid)
    if r.get("daily"):                       # ★ B3-13：点档 + 每日轮换 ⇒ 只数今天点名的那一只
        tgt = _daily_pick(str(r.get("role") or ""), p)
        return CX.kills_of(s, tgt) if tgt else 0
    return sum(CX.kills_of(s, k) for k in _role_ids(str(r.get("role") or "")))


def _mon_name(mid):
    return (_data("monsters").get(mid) or {}).get("name") or mid


def _item_name(iid):
    return LT.rec_of(iid).get("name") or iid


# ── ★ B3-13：四本**已经在档上**的账（本模块只回头查，一个都不写）────────────
#   · `p.enhance[<装备>]`     强化等级  —— cmds_recipe.enhance 写
#   · `flags.cooked[<配方>]`  下过几次锅 —— cmds_recipe.cook 写
#   · `flags.talked[<对话树>]` 搭过几次话 —— cmds_talk 写
#   · (没有第四本：`ask` 数的是 talked 那本账上有几个**不同的人**)
def _npc_name(npc):
    """NPC id → 中文名（从 npcs 域透传；认不出回空串 —— 呈现口由调用方把关）。"""
    return str((_data("npcs").get(str(npc or "")) or {}).get("name") or "")


def _dlg_of(npc):
    """NPC id → 它那棵对话树 id（唯一出处 = `npcs.dialogue`；认不出回空串）。"""
    return str((_data("npcs").get(str(npc or "")) or {}).get("dialogue") or "")


def _talked(p):
    """档上「搭过几次话」那本账（对话树 id → 次数）；不是 dict = 空账。"""
    t = (p.get("flags") or {}).get("talked")
    return t if isinstance(t, dict) else {}


def _talk_have(p, npc):
    """跟这个人搭过几次话（取不到对话树 ⇒ 0 —— 认不出的 npc 一律当没满足）。"""
    d = _dlg_of(npc)
    if not d:
        return 0
    try:
        return int(_talked(p).get(d) or 0)
    except (TypeError, ValueError):
        return 0


def _asked_have(p):
    """搭过话的**人**有几个 —— 只数域里真有对话树的键（脏键不算一个人）。"""
    ds = _data("dialogues")
    return len([k for k in _talked(p) if k in ds])


def _enhance_have(p):
    """档上**最高**的一件强化等级（`p.enhance[<装备>] = {"lv": …}`；认不出的一律跳过）。"""
    e = p.get("enhance")
    if not isinstance(e, dict):
        return 0
    best = 0
    for v in e.values():
        try:
            best = max(best, int((v if isinstance(v, dict) else {}).get("lv") or 0))
        except (TypeError, ValueError):
            continue
    return best


def _quality_ids(quality):
    """items 域里这个**品阶**的东西（只比数据 —— 代码不认中文品阶名）。"""
    q = str(quality or "")
    return set(k for k, v in _data("items").items()
               if not str(k).startswith("_") and str((v or {}).get("quality") or "") == q)


def _cook_have(p, r):
    """「下过锅几次」的已达成数（账 = `flags.cooked[<配方>]`，写入口 cmds_recipe.cook）。

    带 `quality` 子键时**只数用了那一品阶食材的配方**（食材品阶现从 items 域取 —— 数据比数据；
    品阶名一个字都没写进代码）。认不出的品阶 ⇒ 一道都数不到 ⇒ 没满足（fail-closed）。
    """
    cooked = (p.get("flags") or {}).get("cooked")
    cooked = cooked if isinstance(cooked, dict) else {}
    q = str(r.get("quality") or "")
    ok_ids = _quality_ids(q) if q else None
    have = 0
    for rid, rec in _data("recipes").items():
        if str(rid).startswith("_") or (rec or {}).get("kind_key") != "cook":
            continue
        if ok_ids is not None:
            ins = [str((e or {}).get("id") or "") for e in (rec.get("inputs") or [])]
            if not ok_ids.intersection(ins):
                continue
        try:
            have += int(cooked.get(rid) or 0)
        except (TypeError, ValueError):
            continue
    return have


def _habitat_of(mid):
    """这只怪**出没在哪几站**（`monsters[].habitat.nodes` → 站名；取不到回空表）。

    ★ QB-3（试玩报告 P1 BUG-2「悬赏 101 交不掉」）：单子只点一次名（`看 <编号>` 那一行），
      玩家在图上乱撞 —— 「野狗窝」刷的是**拾荒野狗**（名字只差三个字），杀了四回不算；
      而真正点名的那只出没在别的站。这一段把那几站**点出来**（站名走 `maps` 域透传，
      代码不造中文），玩家照着走就找得到。

    ★ 数据来源就是挑选怪时用的同一格（`combat.pick_encounter` 的 `habitat`）——
      不另开一份「怪在哪」的口径。
    """
    hb = (_data("monsters").get(str(mid or "")) or {}).get("habitat") or {}
    nodes = [n for n in (hb.get("nodes") or []) if n]
    if not nodes:
        return []
    out, where = [], []
    for m, mv in _data("maps").items():
        if str(m).startswith("_"):
            continue
        for nd in (mv.get("nodes") or []):
            nid = str((nd or {}).get("id") or "")
            if nid in nodes and nid not in out:
                out.append(nid)
                where.append((str(m), nid))
    return [(_name_of_node(m, n) or n) for m, n in where]


def _have_n(p, r):
    """这一条条件「做到哪了」→ `(已达成数, 需要数)` —— **唯一一口**（达成数**封顶**在需要数上）。

    ★ QB-4：『还差…』那几行里的数（「你手上有 1」「你打过 2 只」）与『我的委托』的进度
      都从这里来 —— 进度不许自己再数一遍（两处数法 = 迟早对不上）。
      认不出的 kind ⇒ `(0, n)`（与判定同一口径：fail-closed 不算做了）。
      封顶那一刀对『还差…』那几行是**空操作**（那几行只在**没满足**时印，没满足 ⇒ 达成数 < 需要数），
      但它挡住「听够 4 回显示 4/3」这种读起来像坏了的数。
    ★ 「去过某处」这一型没有数：去过 = 1、没去过 = 0（需要数恒 1）。
    """
    n = _n_of(r)
    kind = r.get("kind")
    if kind == "visit":
        return (1 if _req_ok(p, r) else 0), 1
    if kind == "item":
        have = _bag_n(p, str(r.get("item") or ""))
    elif kind == "kill":
        have = _kill_have(p, r) if (r.get("monster") or r.get("role")) else 0
    elif kind == "enhance":
        have = _enhance_have(p)
    elif kind == "cook":
        have = _cook_have(p, r)
    elif kind == "talk":
        have = _talk_have(p, r.get("npc")) if r.get("npc") else 0
    elif kind == "ask":
        have = _asked_have(p)
    else:
        have = 0
    return min(int(have), n), n


def _req_lines(p, r):
    """没满足的那一条 → 说人话的那一行。★ 只给名字不给机器键（id 不许出现在回话里）。"""
    kind = r.get("kind")
    if kind == "visit":
        loc, node = str(r.get("map") or ""), str(r.get("node") or "")
        name = _name_of_node(loc, node) if node else ((_map_of(loc) or {}).get("name") or loc)
        return [T("SYS_JOB_REQ_VISIT", place=name)]
    if kind == "kill":
        # ★ B3-11：点名的那一只给怪名；点档的给**档名**（「普通 / 精英 / 头目」—— monsters 域里透传）
        # ★ B3-13：点档 + `daily` ⇒ 报**今天点名的那一只**的怪名（玩家由此知道要打哪一只）
        mid = str(r.get("monster") or "")
        if mid:
            name = _mon_name(mid)
        elif r.get("daily"):
            mid = _daily_pick(str(r.get("role") or ""), p)
            name = _mon_name(mid)
        else:
            mid, name = "", _role_name(str(r.get("role") or ""))
        if not name:                       # 档 / 怪认不出 ⇒ 不糊一句空名字（fail-closed 的那一行）
            return [T("SYS_JOB_REQ_UNKNOWN")]
        out = [T("SYS_JOB_REQ_KILL", monster=name, n=_n_of(r), have=_have_n(p, r)[0])]
        # ★ QB-3：点名点到**一只**时，把它的出没地也说出来（点档那种没有「一只」可说）
        where = _habitat_of(mid) if mid else []
        if where:
            out.append(T("SYS_JOB_REQ_MON_WHERE", list=" · ".join(where)))
        return out
    if kind == "item":
        iid = str(r.get("item") or "")
        return [T("SYS_JOB_REQ_ITEM", item=_item_name(iid), n=_n_of(r), have=_have_n(p, r)[0])]
    if kind == "enhance":                  # ★ B3-13
        return [T("SYS_JOB_REQ_ENHANCE", n=_n_of(r), have=_have_n(p, r)[0])]
    if kind == "cook":                     # ★ B3-13（带品阶的走品阶那条槽位）
        if r.get("quality"):
            return [T("SYS_JOB_REQ_COOK_GRADE", grade=r.get("quality"), n=_n_of(r),
                      have=_have_n(p, r)[0])]
        return [T("SYS_JOB_REQ_COOK", n=_n_of(r), have=_have_n(p, r)[0])]
    if kind == "talk":                     # ★ B3-13
        who = _npc_name(r.get("npc"))
        if not who:
            return [T("SYS_JOB_REQ_UNKNOWN")]
        return [T("SYS_JOB_REQ_TALK", who=who, n=_n_of(r), have=_have_n(p, r)[0])]
    if kind == "ask":                      # ★ B3-13
        return [T("SYS_JOB_REQ_ASK", n=_n_of(r), have=_have_n(p, r)[0])]
    return [T("SYS_JOB_REQ_UNKNOWN")]


def _unmet(p, x):
    """还没满足的那几条 → 要回的话（老条目没写 require ⇒ 空表 ⇒ 一行都不多，输出逐字节不变）。"""
    out = []
    for r in _require_of(x):
        if not _req_ok(p, r):
            out.extend(_req_lines(p, r))
    return out


def _mark_done(p, k, step):
    """交活那一下把 done 写进 `flags.quests`（形状见文件抬头 ②；step = 已满足的条件条数）。"""
    book = dict((p.get("flags") or {}).get("quests") or {})
    book[k] = {"step": int(step), "done": True, "at": CX.today(p)}
    _set(p, "quests", book)


def _hand_over(p, x) -> list:
    """★ 本波②：**接活时真发东西**（`quests.<id>.give`）→ 回那几行「得到：…」。

    ★ 为什么非有不可：`17 §QUEST_SIDE25_STORY` 那句是「**小满把那块石头塞给你** —— 它该回到
      缺着它的那块碑上去。」，而改前 `接 25` **一个东西都不发** —— 玩家只能自己去骨田挖
      （30% 出 `unid_rare`）才走得通 ⇒ 接时那行字是空话（报告 P1 BUG-1 那一半）。
      真源 `15_彩蛋域口径_v1 §二` 第 2 行的依据栏自己写着「**小满的石头 = 骨田捡的刻字石片**」
      —— 石头是小满交到手上的，接到手那一下就该到包里。
    ★ 唯一口 = `loot.add_to_bag`（与采集 / 掉落 / 烹饪 / 买同一条路 —— 顺手记 `codex`）。
    ★ fail-closed：`give` 里认不出的 id / 非正的 n 一律跳过（不许把空 id 塞进背包）。
    """
    out = []
    for g in (x.get("give") or []):
        iid = str((g or {}).get("item") or "")
        try:
            n = int((g or {}).get("n") or 1)
        except (TypeError, ValueError):
            n = 0
        if not iid or n <= 0:
            continue
        LT.add_to_bag(p, [{"id": iid, "n": n}])
        rec = LT.rec_of(iid)
        out.append(T("SYS_JOB_GIVE", icon=rec.get("icon", "·"), name=rec.get("name", iid), n=n))
    return out


async def guild(env, sink, uid, player):
    """`公会` —— 柜台（声明里的 `guard_desc` = 在镇上 · 那一站 = 挂板墙）。

    ★ B4-12：原先这一条**一个地点都不判**（`here` 还是算完不用的死变量）—— 人站在骨田照样
      把公会看个遍，而同一个位置『登记』回的是「这几处都在镇上」。守卫现在与镇上其它几处
      共用 `cmds_ast.town_gate` 那一个执行面。
    """
    p = _p(player)
    line = town_gate(p, _func_node("board"))
    if line:
        yield line
        return
    yield T("SYS_GUILD_HEAD")
    yield T("SYS_GUILD_DESK")
    yield T("SYS_GUILD_HOW")


async def board(env, sink, uid, player):
    """`悬赏` —— 挂板墙上的单子（声明里的 `guard_desc` = 在公会）。★ B4-12：补上守卫。

    ★ P-61：板子列三样 —— 下一条主线 · **三档每日悬赏**（101/102/103，常年挂在公会上）·
    在场那位手上的支线（不带编号玩家接不了，B3-6 起一直带）。
    """
    p = _p(player)
    line = town_gate(p, _func_node("board"))
    if line:
        yield line
        return
    qs = _quests()
    done = _done(p)
    active = _mine(p)
    main = sorted([v for v in qs.values() if v["chain"] == "main"], key=lambda v: v["order"])
    nxt = None
    for v in main:
        qid = [k for k, x in qs.items() if x is v][0]
        if qid not in done:
            nxt = (qid, v)
            break
    yield T("SYS_BOARD_HEAD")
    if nxt is None:
        yield T("SYS_BOARD_NOMAIN")
    else:
        qid, v = nxt
        mark = T("SYS_BOARD_ACTIVE") if qid in active else ""
        yield T("SYS_BOARD_MAIN_ROW", order=v["order"], name=v["name"], mark=mark, level=v["min_level"])
        yield "  " + T("SYS_BOARD_TODO", objective=v["objective"])
        if qid in active:
            yield "  " + T("SYS_BOARD_DELIVER", order=v["order"])
        else:
            yield "  " + T("SYS_BOARD_NEXT", order=v["order"])
    # ★ P-61：三档**每日悬赏**常年挂在公会上 —— 板上把它们列出来（玩家不必先知道编号）。
    #   口径 = `24_任务线_v1 §二`（悬赏板 · 玛莎 · 无限循环的日常内容）+ `03_风车镇 §一`
    #   （`悬赏` → 看板 → **三行列表**）⇒ **一档一行**（普通 / 精英 / 头目，各带自己的
    #   `min_level`）。写法与主线那一行同形（编号 · 名字 · 标记 · 等级）；那一行的**编号**
    #   就是『接 <编号>』认的同一个 `order` —— 「列出来 → 接得上」这条接线由探针钉着
    #   （`probe_quests` ㊱）。不列怪名：「指定的」是哪一只仍然由『看 <编号>』点名。
    bounty = sorted([(k, v) for k, v in qs.items() if v["chain"] == "bounty"],
                    key=lambda kv: kv[1]["order"])
    if bounty:
        yield T("SYS_BOARD_BOUNTY_HEAD")
        for qid, v in bounty:
            mark = T("SYS_BOARD_ACTIVE") if qid in active else ""
            yield "  " + T("SYS_BOARD_BOUNTY_ROW", order=v["order"], name=v["name"],
                           mark=mark, level=v["min_level"])
    side = [v for v in qs.values() if v["chain"] == "side" and v["giver"] in
            [k for k, _ in _npcs_here(p["loc"], p["node"], p=p)]]
    if side:
        yield T("SYS_BOARD_SIDE_HEAD")
        for v in side[:3]:
            # ★ 支线也**必须带编号**：不带编号 + `接 <编号>` 只认主线 ⇒ 18 条支线全接不了
            #   （2026-09-25 端到端玩出来的真 bug）。硬编码中文一并收进槽位（B3-6 口径）。
            yield "  " + T("SYS_BOARD_SIDE_ROW", order=v["order"], name=v["name"],
                           objective=v["objective"])
    yield T("SYS_BOARD_HOW")


async def quest_accept(env, sink, uid, player):
    p = _p(player)
    want = _arg(env)
    qs = _quests()
    if not want:
        yield T("SYS_JOB_ASK")
        return
    v = None
    if want.isdigit():
        n = int(want)
        for k, x in qs.items():
            # ★ 编号对**所有**链都成立（原先只认 main ⇒ 支线接不了）
            if x.get("order") == n:
                v = (k, x)
                break
    if v is None:
        for k, x in qs.items():
            if x["name"] == want:
                v = (k, x)
                break
    if v is None:
        yield T("SYS_JOB_NOSUCH", name=want)
        return
    k, x = v
    if k in _mine(p) or k in _done(p):
        yield T("SYS_JOB_ALREADY")
        return
    # ★ B4-27（P-53）：「接 <编号>」这一条**真有门了** —— 先办见习证。
    #   · 口径依据 = `06_第一阶段垂直切片/04_指令总表 §二`「`接 <编号>` 的守卫 = **已登记 · 未接**」
    #     （`03_风车镇 §一` 那一格只写了「等级够 · 未接」——两份真源打架，本轮按**命令表真源**落，
    #      与台账 P-53「我的倾向：加」一致）。
    #   · 为什么非加不可：`flags.card`（`登记` 办的那个证）今天**只有『评级』读** ⇒ 办出来的证等于
    #     白办，「公会 → 登记（见习证）→ 悬赏 → 接活」这条线断在最后一节。
    #   · 那一格的**唯一读口** = `cmds_self.has_card`（B4-14 立的规矩；probe_cmds ⑲ 的静态守卫
    #     钉着「读 `flags[\"card\"]` 只许一处」）—— 这里不自己去看那一格。
    #   · 为什么排在「已经接过」之后：「已经接了 / 交过了」是**这条单子自己的状态**（玩家手上
    #     真有它时不能被回一句「你没有证」的假话）；这一道门管的是「能不能**新接**一条」。
    from .cmds_self import has_card
    if not has_card(p):
        yield T("SYS_JOB_NEED_CARD")
        return
    if p.get("level", 1) < x["min_level"]:
        yield T("SYS_JOB_LOWLEVEL", name=x["name"], need=x["min_level"], now=p.get("level"))
        yield T("SYS_JOB_MARTHA")
        return
    _set(p, "quests_active", _mine(p) + [k])
    gained = _hand_over(p, x)                 # ★ 本波②：接活时**真发东西**（`quests.<id>.give`）
    PROG.resync(p, k)                         # ★ 本波③：旗标族的**写端**（接活那一拍）
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_JOB_TAKEN", name=x["name"])
    # ★ B3-6c / B3-8：接时那一段（槽位自己的出处就写着「接时行文」）—— 四条链都取槽位。
    yield _beat(x, "STORY")
    for _ln in gained:                        # 「得到：…」跟在接时行文之后（话说完，东西才到手）
        yield _ln
    yield "  " + T("SYS_JOB_TODO", objective=x["objective"])
    if x.get("insight"):
        yield "  " + T("SYS_JOB_INSIGHT", insight=x["insight"])
    yield T("SYS_JOB_GO")


async def quest_deliver(env, sink, uid, player):
    p = _p(player)
    want = _arg(env)
    if not want:
        # ★ B4-13：裸「交」—— 原先回「这条不是你的委托」（拿空名字去比，等于说了句假话）
        yield T("SYS_JOB_DELIVER_ASK")
        return
    qs = _quests()
    act = _mine(p)
    if not act:
        yield T("SYS_JOB_NONE")
        return
    k = None
    if want.isdigit():
        for kk in act:
            if qs.get(kk, {}).get("order") == int(want):
                k = kk
                break
    else:
        for kk in act:
            if qs.get(kk, {}).get("name") == want:
                k = kk
                break
    if k is None:
        yield T("SYS_JOB_NOT_MINE")
        for kk in act:
            yield "  · %s" % qs.get(kk, {}).get("name", kk)
        return
    x = qs[k]
    if not _obj_ok(x, p):
        yield T("SYS_JOB_NOT_DONE") + (_beat(x, "PROGRESS") or x["objective"])
        for line in _unmet(p, x):          # ★ P-25：把「还差什么」说清楚（老条目这里一行都不多）
            yield "  " + line
        return
    _set(p, "quests_active", [a for a in act if a != k])
    _set(p, "quests_done", _done(p) + [k])
    _mark_done(p, k, len(_require_of(x)))   # ★ P-25：done 记进 flags.quests（形状见文件抬头 ②）
    PROG.resync(p, k)                       # ★ 本波③：旗标族的**写端**（交活那一拍：done 型 True）
    p["gold"] = p.get("gold", 0) + x["reward_gold"]
    # ★ B3-13：升级判定收成 `cmds_ast.add_exp` **一个口**（打怪给经验也走它）
    leveled = bool(add_exp(p, x["reward_exp"]))
    lv = p.get("level", 1)
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_JOB_DELIVERED", name=x["name"])
    yield _beat(x, "DELIVER")         # ★ B3-6c / B3-8：交时那一段（四条链都走槽位）
    yield T("SYS_JOB_REWARD", exp=x["reward_exp"], gold=x["reward_gold"])
    if leveled:
        yield T("SYS_JOB_LEVELUP", level=lv)
    if x.get("hook"):
        yield "（「%s」）" % x["hook"]


def _obj_ok(x, p):
    """交活判据 —— ★ P-25：写了 `require` 的条目**逐条真查**（做没做，档上有账）。

    · 主线：**等级 + 逐步记账** —— ★ B4-2 落了 `require` 之后，判据就是
      `level >= min_level` **且** `require` 逐条满足（12 条全写了 ⇒ 「1 级接 1 级主线、
      一句『交 1』就过」那条老路已经堵死）。没写 `require` 的主线仍只看等级。
    · 支线：写了 `require` 就逐条查；**没写的照旧**看 `flags.side_<名字>`
    ⇒ 没有 `require` 的老条目，这一支的行为逐字节不变（回归口径见任务卡 P-25）。
    """
    reqs = _require_of(x)
    if x["chain"] == "main":
        return p.get("level", 1) >= x["min_level"] and all(_req_ok(p, r) for r in reqs)
    if reqs:
        return all(_req_ok(p, r) for r in reqs)
    return bool((p.get("flags") or {}).get("side_" + x["name"]))


def _abandon_day(p) -> int:
    """上一次「放弃」是**第几个游戏日**（`flags.abandon_day`；没记过 / 坏了 = 0）。

    ★ B4-27 ③（P-56）：「放弃」的冷却那一格 —— 只读、不建容器（K57：问一句冷却不该往档里塞东西）。
      认不出（写成别的类型）一律当 0 ⇒ 退回「没冷却过」（这一格坏了不该把玩家永久锁住）。
    """
    try:
        return int((p.get("flags") or {}).get("abandon_day") or 0)
    except (TypeError, ValueError):
        return 0


async def quest_abandon(env, sink, uid, player):
    p = _p(player)
    act = _mine(p)
    if not act:
        yield T("SYS_JOB_NO_ACTIVE")
        return
    want = _arg(env)
    if not want:
        # ★ B4-13：裸「放弃」—— **不许**拿 act[0] 顶上（B3-14 那条判据：裸「放弃」不许动档）
        yield T("SYS_JOB_ABANDON_ASK")
        return
    qs = _quests()
    k = next((a for a in act if qs.get(a, {}).get("name") == want
              or qs.get(a, {}).get("order") == (int(want) if want.isdigit() else -1)), None)
    if not k:
        yield T("SYS_JOB_NO_ACTIVE_ONE")
        return
    # ★ B4-27 ③（P-56）：「放弃」的冷却 = **同一个游戏日只许放弃一条**（真源 `05 §一`「冷却 1 天」）。
    #   · 读的是**那根钟**（`_abandon_day` → `CX.today` = `calendar.day_now`，与悬赏轮换同一口）——
    #     不是档上那格 `p["day"]`（B4-9：那只是 `tick()` 的跨日标记，别处读它会拿到旧值 / 0）。
    #   · 冷却那一格是 `flags.abandon_day`（既有容器，不新建）；写在**真放下那一下**。
    #   · fail-closed：冷却期内 ⇒ 只回一行、**档一个字不动**（不静默放行、不替玩家挑一条）。
    #   · 位置在「认可这一条」之后：「没有这一条」那种问法不该被冷却挡住（那是另一件事）。
    if _abandon_day(p) == CX.today(p):
        yield T("SYS_JOB_ABANDON_CD")
        return
    _set(p, "quests_active", [a for a in act if a != k])
    _set(p, "abandon_day", CX.today(p))
    PROG.resync(p, k)                       # ★ 本波③：放掉了 ⇒ 名下「在手上」那种旗标写回 False
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_JOB_ABANDONED", name=qs.get(k, {}).get("name", k))


def _progress(x, p):
    """这一条的**进度**那一格（`（已达成 / 需要）`）—— 没写 `require` 的老条目回空串（一个字不多）。

    ★ QB-4（试玩报告 P4 E-10）：『我的委托』原先只给一句 objective —— 玩家要先跑一趟『交』
      失败一次，才知道自己听了几回（『交』那边写着「你听过 0 回」，两处不成体系）。
      真源：`06_第一阶段垂直切片/04_指令总表 §二`「`我的委托` `任务` ｜ 随时 ｜ 进行中的委托」
      ＋ 同一条委托自己的 objective（`24_任务线_v1 §二` 支 9「听他讲完（三次）」——
      「（三次）」是**文档那一格自己写的**，所以进度就该按它数：`（1/3）`）。
    ★ 数与『还差…』那几行走**同一个口**（`_have_n` —— 它就是交活那把尺子的读数）。
    """
    reqs = _require_of(x)
    if not reqs:
        return ""
    pairs = [_have_n(p, r) for r in reqs]
    return T("SYS_MINE_PROGRESS", done=sum(h for h, _n in pairs), n=sum(n for _h, n in pairs))


def _hint_lines(p):
    """『提示』优先给的那几行 —— **当前委托的下一步**（手上没活 ⇒ 空表，调用方退回地点那一句）。

    ★ QB-5（试玩报告 P1 BUG-3 / P4 E-1）：『提示』原先只看地点（镇上 / 野外各一句固定文案），
      从不随委托走 —— 1→3 级、交 0→3 条，镇上永远回建号那一句「先『观察』…再去『公会』」，
      而**每一条接活回话**都写着「『提示』会告诉你往哪走」（`quest_accept` 的 `SYS_JOB_GO`）。
      真源：`06_第一阶段垂直切片/04_指令总表 §一`「`提示` `去哪` ｜ 随时 ｜ **给一条当前该做什么
      的提示**」—— 「当前」= 手上这条活 ⇒ 先报它的名字与 objective，再逐条说还差什么
      （那几行就是『交』失败时给的同一批行，同一个口 `_unmet`）。
    """
    qs = _quests()
    for k in _mine(p):
        x = qs.get(k) or {}
        if not x:
            continue
        out = [T("SYS_HINT_JOB", name=x.get("name", k), objective=x.get("objective", ""))]
        if _obj_ok(x, p):
            out.append("  " + T("SYS_HINT_JOB_READY", order=x.get("order", 0)))
        else:
            out += ["  " + ln for ln in _unmet(p, x)]
        return out
    return []


async def quest_mine(env, sink, uid, player):
    p = _p(player)
    qs = _quests()
    act, done = _mine(p), _done(p)
    if not act:
        yield T("SYS_MINE_NONE")
    else:
        yield T("SYS_MINE_HEAD", n=len(act))
        for k in act:
            x = qs.get(k, {})
            yield "· %s —— %s%s" % (x.get("name", k), x.get("objective", ""), _progress(x, p))
    if done:
        yield T("SYS_MINE_DONE", n=len(done))
    # ★ B4-14：那半句评级与『评级』**走同一个门**（`cmds_self.has_card`）—— 没办证的人
    #   原先在这一条里照样印「【评级】见习」，与同一刻『评级』回的「你还没有证」直接打架。
    from .cmds_self import has_card
    if has_card(p):
        # ★ B4-16：这一行与『评级』里那一行**同一槽位**（`SYS_MINE_RANK`）—— 档名现取
        yield T("SYS_MINE_RANK", tier=RK.label(RK.current(p)))
