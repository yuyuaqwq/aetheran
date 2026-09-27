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

★ fix-m-bounty 两条（2026-09-27 夜班 · 试玩实测报上来的）
------------------------------------------------------------------
① 【真 bug】悬赏是**一次性**的 —— 跨了游戏日也接不回来。
   改前守卫 = `k in _mine(p) or k in _done(p)`，而 `_done` 读的 `flags.quests_done` 是**只加不减
   的永久列表** ⇒ 悬赏交过一次以后，**新的游戏日**再敲『接 101』仍回「这条你已经接了（或交过
   了）。」（游侠路 b125/b130 实测）—— 三档悬赏实际成了一次性委托，「日常」这一层是死的。
   真源三处都写「可反复」（`aetheran-plan`，只读）：
     · `06_第一阶段垂直切片/24_任务线_v1.md §二`：「**悬赏板**（玛莎 · **无限循环的日常内容**）·
       同时挂 6 条 · **每天刷 1 次**」「悬赏板**每天轮换挑一只**」「三档每日悬赏**常年挂在公会上**」
     · `00_总纲/03_主要玩法.md §4.1`：「**悬赏（公会板）** 打怪类的日常活，**可反复接**」
   修法（判据 = **跨游戏日可重接**，一个字都不多松）：
     · 完成时的**游戏日**在 `flags.quests[<id>].at` —— 交活那一拍 `_mark_done` **早就写着**
       （现成的账，不新建容器）；读口 = `_done_at`（缺记录 / 认不出 / 写成别的类型 ⇒ `None`
       = 当「不是跨日的悬赏」算 ⇒ **拦**，fail-closed 不猜哪一天）。
     · `quest_accept` 里命中 `_done` 时只问一句 `_reaccept_ok(x, k, p)`：**只有**
       『`chain == "bounty"` **且** 完成日 `<` 当前游戏日』才放行。主线 / 支线 / 生活（副业）/
       同日重接 —— **一个字都不许松**（仍回 `SYS_JOB_ALREADY`）。
     · 「今天」= `CX.today(p)` = `calendar.day_now()`（**那根钟** —— 与悬赏轮换 / 放弃冷却同一口）。
     · 重接时**不把 k 从 `quests_done` 里摘掉**（那是完成记录：`calendar.main_done` / 『评级』的
       已交条数 / 图鉴 / 彩蛋都在读它）—— 只让 accept 这一处放行；而 `quest_deliver` 落账那一行
       改成**去重后再写**（同一条跨日交两次不进两份，否则已交条数虚高）。
     · 判据：`scripts/probe_quests.py` ㊲ ①（跨日放行 + 同日拦 + 主线/支线/副业一律拦 +
       完成日写坏一律拦 · 全部真敲指令 · 含反证）。

② 【⚠️误导】`board` 的「这人手上还有」那一段**把在场 NPC 的支线全列**（不看 `done`）——
   玩家照着板子点一条**已交**的单子 ⇒ 回「这条你已经接了（或交过了）。」（ranger b130/b131 实测）。
   真源同 ①：「挂板墙上的**单子**」—— 交掉的单子不在板上；这一段的抬头也是「还能接的活」。
   修法：那一段**只列还能接的**（`qid not in _done(p)`）；过滤后一条不剩 ⇒ **连表头都不印**
   （既有 `if side:` 已经管着）。判据：`scripts/probe_quests.py` ㊲ ②（已交那条不在板上 ·
   其余照旧 · 三条全交掉 ⇒ 表头也不印）。

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

★ fxm3-questsnap（本波）：`require` 判「**接活后**新达成」（进度基线）
--------------------------------------------------------------------
【现象】三路试玩复现：主线 3「三张牌」只要**到过三条带**就能交（`看 3` 一行「还差」都没有、
  `提示` 直接说「办完了」、`交 3` 白拿 **经验 118 / 铜板 30**），三条带的活一件没做；
  主 4 交掉 +330 经验；主 11 交掉 **+4276**（与 `reward_exp` 逐字相等）。
【根因】`require` 查的是**历史态**（历史上到过 / 打过 / 采过就算数），而「接活那一刻」没有基线
  ⇒ 接活**前**干过的活也算进任务进度。
【真源】`06_第一阶段垂直切片/24_任务线_v1.md §一` 每一块的「步骤」都是**接了之后要做的那几拍**
  （主 3：「① 玛莎给三张委托（三条带各一张）② **各完成一次**（打怪/采集/送信）③ 回来交活」）
  —— 是**代码没跟上文案**，真源一个字不动。
【修法】接活那一下给这条委托落一份**进度基线** `flags.quests[<id>]["base"]`（`_set_base`，
  在 `_hand_over` 之前 = 接活时塞到手上的东西算「接活后到手」）；判定与呈现一律走
  「现在 − 基线」（`_since`）。读数按机器键记（`_ckey`），条件换顺序不影响基线。
【老档】没有基线的档（本批之前接的活）⇒ 基线按 0 算，判定与改前**逐字节相同**；要更严
  （缺基线一律拦住）只改 `_base_at` 一处 —— 取舍写在那两处的 docstring 里。
【判据】`scripts/probe_quests.py` ㊳（三态：接活前干完 ⇒ 拦住 · 接活后真干一次 ⇒ 交得掉且
  奖励只发一次 · 反证：把 `_set_base` 关掉 ⇒ 同一批当场红；含全 12 条主线的逐条矩阵）。
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


def _done_at(p, k):
    """这条委托**交掉时是第几个游戏日**（`flags.quests[<id>].at` —— 交活那一拍写的，现成的账）。

    ★ fix-m-bounty ①：「悬赏跨游戏日可重接」唯一的日期读口。
    ★ fail-closed：缺记录 / 认不出 / 写成别的类型 ⇒ 回 `None` = **当「不是跨日的悬赏」算**（拦），
      不猜哪一天、更不默认放行（老档只有 `quests_done` 没有 `flags.quests` 时也一样拦住）。
    """
    rec = ((p.get("flags") or {}).get("quests") or {}).get(k)
    if not isinstance(rec, dict) or rec.get("done") is not True:
        return None
    try:
        return int(rec.get("at"))
    except (TypeError, ValueError):
        return None


def _reaccept_ok(x, k, p) -> bool:
    """这条**已交过**的委托，今天还能再接一次吗？—— 四条链只有**悬赏**、且**跨了游戏日**才放行。

    ★ fix-m-bounty ①：真源 = `24_任务线_v1 §二`「悬赏板（玛莎 · **无限循环的日常内容**）·
      每天轮换挑一只 · 三档每日悬赏常年挂在公会上」+ `03_主要玩法 §4.1`「悬赏（公会板）
      打怪类的日常活，**可反复接**」。
    ★ 主线 / 支线 / 生活（副业）**一个字都不松**：它们不是日常内容（`03 §4.1` 三类分列）。
    ★ 同日重接也拦（「每天刷 1 次」）：完成日**严格小于**当前游戏日才算跨日。
    ★ 「今天」= `CX.today(p)` = `calendar.day_now()` —— 与悬赏轮换 / 放弃冷却**同一根钟**。
    """
    if str(x.get("chain") or "") != "bounty":
        return False
    d = _done_at(p, k)
    return d is not None and d < CX.today(p)


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


def _num(v) -> int:
    """一格计数 → 非负整数（认不出的当 0 —— 档上这几本账只许往前长）。"""
    try:
        return max(0, int(v or 0))
    except (TypeError, ValueError):
        return 0


def _visit_have(p, loc, node="") -> int:
    """去过这一站 / 这张图的**趟数**（足迹两格合起来数：`foot.visits` 记趟、`foot.nodes` 记第一回）。

    ★ 为什么要有「数」而不只是「有没有」（本波 · fxm3-questsnap）：进度快照要一个**可比的读数**
      （「接活后又去过一趟」= 这个数变大了），布尔态比不了。
      读数 = 这个节点的**趟数**（`foot.visits`，`note_step` 每走进来一次 +1）
             + 「第一回到过」那一笔（`foot.nodes` 有这个键 ⇒ +1）——
      ⇒ **只增不减**，且 `> 0` 与旧的「有没有这个键」逐条等价（老档 / 老条目行为一个字不变）；
        而「先被 `mark_here` 记下节点、后来才真走进去一趟」这种档也能看出涨了一格。
        · 点一个节点 ⇒ 那个键的读数
        · 点整张图（`node` 省了）⇒ 这张图里所有节点的读数之和 —— 走进任何一个节点都会让它变大
    """
    f = p.get("foot")
    f = f if isinstance(f, dict) else {}
    nds = f.get("nodes") if isinstance(f.get("nodes"), dict) else {}
    vst = f.get("visits") if isinstance(f.get("visits"), dict) else {}
    keys = set(nds.keys()) | set(vst.keys())
    pre = loc + ":"

    def _of(k):
        return _num(vst.get(k)) + (1 if k in nds else 0)

    if node:
        k = pre + node
        return _of(k) if k in keys else 0
    return sum(_of(k) for k in keys if k.startswith(pre))


def _been(p, loc, node=""):
    """去过吗？—— 档上足迹两格都算：`foot.nodes`（第一回到）与 `foot.visits`（去过几回）。

    ★ 布尔视图（`_visit_have(...) > 0`）—— 判定与呈现走的是 `_visit_have` / `_metric` 那个读数。
    """
    return _visit_have(p, loc, node) > 0


# ── ★ fxm3-questsnap（本波）：`require` 判「**接活后**新达成」的进度基线 ──────────────
# 【现象】三路试玩复现：主线 3「三张牌」只要**到过三条带**就能交（`看 3` 一行「还差」都没有、
#   提示 直接说「办完了」、`交 3` 白拿 118 经验 / 30 铜板），三条带的活一件没做；主 4 交掉 +330；
#   主 11 交掉 +4276（与 `reward_exp` 逐字相等）。
# 【根因】`require` 查的是**历史态**（历史上到过 / 打过 / 采过就算数），而「接活那一刻」没有基线
#   ⇒ 接活**前**干过的活也算进任务进度。
# 【真源】`06_第一阶段垂直切片/24_任务线_v1.md §一` 每一块的「步骤」都是**接了之后要做的那几拍**
#   （主 3：「① 玛莎给三张委托（三条带各一张）② **各完成一次**（打怪/采集/送信）③ 回来交活」）
#   —— 是代码没跟上文案。**真源一个字不动**。
# 【修法】接活那一下（`quest_accept`）给这条委托落一份**进度基线**：`flags.quests[<id>]["base"]`
#   = 那一刻每条条件的读数；判定与呈现一律走「现在 − 基线」（`_since`）。
#   · 基线在**发东西（`give`）之前**落：接活时塞到手上的那件东西（支线 25「还石头」的刻字石片）
#     算「接活后到手」—— 真源那一句就是「小满把那块石头塞给你」。
#   · 读数按**机器键**记（`_ckey`）：条件在域里换个顺序，基线不受影响。
#   · 落基线与同一格上的 `done` / `at` **合并写**（悬赏跨游戏日重接读的 `_done_at` 就在那格上）。
# 【老档】本批之前接的活 / 起手档直接塞 `flags.quests_active` 的档 ⇒ 没有基线 ⇒ 基线按 0 算，
#   判定与改前**逐字节相同**（有意兼容：不清仓老档里进行中的委托；公测前没有真老档）。
#   要更严（缺基线一律拦住）只改 `_base_at` 那一处一行 —— 取舍写在那个函数的 docstring 里。
# 【一型例外】`enhance`（「有一件装备强化到 ≥ n」）是**状态**条件，不是「接活后新涨几级」
#   （档上只有等级、没有「强化成功次数」那本账）⇒ 它照旧判**绝对值**，见 `_req_ok`。
_BASE = "base"


def _ckey(r) -> str:
    """一条条件的**机器键**（基线按它记 —— 与域里的书写顺序无关，也不认任何中文）。"""
    kind = str(r.get("kind") or "")
    if kind == "visit":
        return "visit|%s|%s" % (r.get("map") or "", r.get("node") or "")
    if kind == "kill":
        return "kill|%s|%s|%s" % (r.get("monster") or "", r.get("role") or "",
                                  "daily" if r.get("daily") else "")
    if kind == "item":
        return "item|%s" % (r.get("item") or "")
    if kind == "cook":
        return "cook|%s" % (r.get("quality") or "")
    if kind == "talk":
        return "talk|%s" % (r.get("npc") or "")
    return kind or "?"                     # enhance / ask：一条一件（上面几型按目标分）


def _metric(p, r) -> int:
    """这条条件**现在的读数**（接活快照与「现在 − 基线」都走它 —— 与 `_have_n` 同一把尺子）。

    ★ 一型一读法，与 `_have_n` 认的是**同一本账**（改前 `_have_n` 里那些取值口原样搬过来）：
      认不出的 kind / 没点名的目标一律回 0（与判定同一口径：fail-closed 不算做了）。
    """
    kind = r.get("kind")
    if kind == "visit":
        return _visit_have(p, str(r.get("map") or ""), str(r.get("node") or ""))
    if kind == "kill":
        return _kill_have(p, r) if (r.get("monster") or r.get("role")) else 0
    if kind == "item":
        return _bag_n(p, str(r.get("item") or ""))
    if kind == "enhance":
        return _enhance_have(p)
    if kind == "cook":
        return _cook_have(p, r)
    if kind == "talk":
        return _talk_have(p, r.get("npc")) if r.get("npc") else 0
    if kind == "ask":
        return _asked_have(p)
    return 0


def _base_snap(p, x) -> dict:
    """这条委托**接活那一刻**的进度基线（`{机器键: 读数}`；没写 `require` ⇒ 空表）。"""
    return {_ckey(r): _metric(p, r) for r in _require_of(x)}


def _set_base(p, k, x) -> None:
    """把进度基线写进 `flags.quests[<id>]["base"]`（接活那一拍 · 合并写，不动同一格上的别的键）。"""
    book = dict((p.get("flags") or {}).get("quests") or {})
    rec = book.get(k)
    rec = dict(rec) if isinstance(rec, dict) else {}
    rec[_BASE] = _base_snap(p, x)
    book[k] = rec
    _set(p, "quests", book)


def _base_at(p, k, r) -> int:
    """这条条件**接活那一刻**的读数（`flags.quests[k].base[机器键]`）。

    ★ 两侧的取舍都写清（与 `_abandon_day` 那一族同一把尺子）：
      · **没有基线**（老档：本批之前接的活 / 起手档直接塞 `flags.quests_active`）⇒ **0**
        = 历史进度全算数 —— 与改前逐字节相同（不清仓老档里进行中的委托）。
      · 基线**坏了**（不是 dict / 读不出的数）⇒ 同样回 0：那一格坏了不该把玩家永久锁住。
      ⇒ 要更严（缺基线 / 坏基线一律**拦住**，只认「接活后新达成」）就改这一处：
         把两个 `return 0` 换成 `return _metric(p, r)`（= 基线取「现在的读数」⇒ 差值恒 0 ⇒ 拦住）。
    """
    if not k:
        return 0
    rec = ((p.get("flags") or {}).get("quests") or {}).get(k)
    base = rec.get(_BASE) if isinstance(rec, dict) else None
    if not isinstance(base, dict):
        return 0
    return _num(base.get(_ckey(r)))


def _since(p, k, r) -> int:
    """「接活之后**新达成**了多少」= 现在 − 基线（负的一律当 0：这几本账只许往前长）。"""
    return max(0, _metric(p, r) - _base_at(p, k, r))


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


def _req_ok(p, r, k=None) -> bool:
    """一条条件满足没有 —— ★ 本波（fxm3-questsnap）：判的是「**接活后**新达成的量」（`_since`）。

    `k` = 这条委托的 id（基线在 `flags.quests[k]["base"]`；不传 = 老档口径，基线 0）。
    认不出的 kind / 认不出的目标一律算没满足（fail-closed，不静默放行）：
      · `kill` —— 点名一只（`monster`）或点**某一档**（`role`，见 `_role_ids`）；两个都不写 ⇒ 没满足。
        `role` + `daily` ⇒ 只算**今天点名的那一只**（`_kill_have` 里那一条）。
      · `item` / `visit` / `talk` —— 目标写空了 ⇒ 没满足（不许白给）。
    ★ `enhance` 是**状态**条件（「有一件装备强化到 ≥ n」）—— 判**绝对值**，不减基线：
      真源写的是「把一件装备强化到 +3」（`28 §四` / `21 §二`），不是「接活后再涨 3 级」；
      而档上只有等级、没有「强化成功次数」那本账 ⇒ 扭成增量就是**改口径**，不干。
      （「接活那一刻已经 +3」这一种白拿要有成功次数账 —— 缺口登记在工作树 `_notes.md`，不自己造第二本账。）
    """
    kind = r.get("kind")
    if kind == "visit":
        if not str(r.get("map") or ""):
            return False
    elif kind == "kill":
        if not (str(r.get("monster") or "") or str(r.get("role") or "")):
            return False
    elif kind == "item":
        if not str(r.get("item") or ""):
            return False
    elif kind == "talk":
        if not str(r.get("npc") or ""):
            return False
    elif kind not in ("enhance", "cook", "ask"):
        return False
    if kind == "enhance":
        return _enhance_have(p) >= _n_of(r)
    return _since(p, k, r) >= _n_of(r)


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


def _have_n(p, r, k=None):
    """这一条条件「做到哪了」→ `(已达成数, 需要数)` —— **唯一一口**（达成数**封顶**在需要数上）。

    ★ QB-4：『还差…』那几行里的数（「你手上有 1」「你打过 2 只」）与『我的委托』的进度
      都从这里来 —— 进度不许自己再数一遍（两处数法 = 迟早对不上）。
    ★ 本波（fxm3-questsnap）：这个「已达成数」就是**接活后新达成的量**（`_since`）——
      与交活那把尺子 `_req_ok` 认的是同一个数（改前是绝对读数；老档基线 0 ⇒ 逐字节相同）。
      认不出的 kind ⇒ `(0, n)`（与判定同一口径：fail-closed 不算做了）。
      封顶那一刀对『还差…』那几行是**空操作**（那几行只在**没满足**时印，没满足 ⇒ 达成数 < 需要数），
      但它挡住「听够 4 回显示 4/3」这种读起来像坏了的数。
    ★ 「去过某处」这一型的数是趟数（没去过 = 0），需要数恒 1。
    ★ `enhance` 那一型走 `_enhance_have`（**绝对值** —— 与 `_req_ok` 同一把尺子，
      不然「已达成」与屏上的「0/3」会打架）。
    """
    n = _n_of(r)
    if r.get("kind") == "enhance":
        have = _enhance_have(p)
    else:
        have = _since(p, k, r)
    return min(int(have), n), n


def _req_lines(p, r, k=None):
    """没满足的那一条 → 说人话的那一行。★ 只给名字不给机器键（id 不许出现在回话里）。

    `k` = 这条委托的 id（本波：那几个「你手上有 N / 你打过 N 只」的数与判定走**同一个口** `_have_n`，
    传了 k 才是「接活后新达成」的数；不传 = 老档口径，与改前逐字相同）。
    """
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
        out = [T("SYS_JOB_REQ_KILL", monster=name, n=_n_of(r), have=_have_n(p, r, k)[0])]
        # ★ QB-3：点名点到**一只**时，把它的出没地也说出来（点档那种没有「一只」可说）
        where = _habitat_of(mid) if mid else []
        if where:
            out.append(T("SYS_JOB_REQ_MON_WHERE", list=" · ".join(where)))
        return out
    if kind == "item":
        iid = str(r.get("item") or "")
        out = [T("SYS_JOB_REQ_ITEM", item=_item_name(iid), n=_n_of(r), have=_have_n(p, r, k)[0])]
        # ★ fix-l（试玩 ranger b71/b85 · 副业 15「娜娜的药单」）：与上面 `kill` 那一支的
        #   「出没地」**同一口径** —— 缺的是**料**时把「从哪儿来」也说一遍。
        #   `强化` / `打造` 早就有这一栏（唯一出处口 = `cmds_recipe.src_lines` → `matsrc`：
        #   采集点 + 掉它的怪），而 `提示` / `看 <编号>` 这一路原先只报名字与数目 ⇒ 玩家
        #   拿着「夜明砂 ×3」不知道去哪儿找。出处现算 —— 域里加一个出产点这一行跟着变。
        #   取不到出处（域里真没有渠道）⇒ 不多话（与「只差钱 ⇒ 那几行为空」同一把尺）。
        from .cmds_recipe import _src_of as _src_of_item     # 本地 import：避免装载期成环
        _where = _src_of_item(iid)
        if _where:
            out.append(T("SYS_JOB_REQ_ITEM_WHERE", item=_item_name(iid), where=_where))
        return out
    if kind == "enhance":                  # ★ B3-13
        return [T("SYS_JOB_REQ_ENHANCE", n=_n_of(r), have=_have_n(p, r, k)[0])]
    if kind == "cook":                     # ★ B3-13（带品阶的走品阶那条槽位）
        if r.get("quality"):
            return [T("SYS_JOB_REQ_COOK_GRADE", grade=r.get("quality"), n=_n_of(r),
                      have=_have_n(p, r, k)[0])]
        return [T("SYS_JOB_REQ_COOK", n=_n_of(r), have=_have_n(p, r, k)[0])]
    if kind == "talk":                     # ★ B3-13
        who = _npc_name(r.get("npc"))
        if not who:
            return [T("SYS_JOB_REQ_UNKNOWN")]
        return [T("SYS_JOB_REQ_TALK", who=who, n=_n_of(r), have=_have_n(p, r, k)[0])]
    if kind == "ask":                      # ★ B3-13
        return [T("SYS_JOB_REQ_ASK", n=_n_of(r), have=_have_n(p, r, k)[0])]
    return [T("SYS_JOB_REQ_UNKNOWN")]


def _unmet(p, x, k=None):
    """还没满足的那几条 → 要回的话（老条目没写 require ⇒ 空表 ⇒ 一行都不多，输出逐字节不变）。

    `k` = 这条委托的 id（本波：判定走「接活后新达成」那一把尺子，见 `_req_ok`）。
    """
    out = []
    for r in _require_of(x):
        if not _req_ok(p, r, k):
            out.extend(_req_lines(p, r, k))
    return out


# ── ★ fxb②（试玩 P1 BUG-2）：完成条件**还没落地**的那几条老支线 ───────────────────
def _no_wire(x) -> bool:
    """这条委托的完成条件**在数据面上不存在** ⇒ 今天走不通（老条目那条死路径）。

    ★ 为什么由数据判、不手写名单（试玩 P1 BUG-2 支线 22「带路」接了永远交不掉）：
      支线没写 `require` 时，交活看的是 `flags.side_<名字>` —— 那个键**全仓没有写端**
      （P-25 §② 的根因；`probe_quests` 的静态守卫钉着「『side_』只有读端 1 处」）。
      真源 `24_任务线_v1 §二` 给这一条的条件是「陪一个 NPC 走一段（送信）」，而
      **目的地与「信」这件东西真源都没写**、也没有对应形状（§三 逐条 why 见工作树 `_notes.md`）
      ⇒ 这不是代码漏判，是**内容还没接线**：不许自己编一个条件顶上（那是改真源口径），
      就照实标出来（报告 BUG-2 的第二条期望）。
    ★ 范围：**非主线且没写 `require`** —— 主线的老条目走「等级」那一支（`_obj_ok`），
      生活 / 悬赏两类按口径**一律写 require**（文件抬头 B3-3），所以这一条挑出来的
      正是那几条还没接线的支线。
    """
    return str(x.get("chain") or "") != "main" and not _require_of(x)


def _no_wire_line(x) -> str:
    """「这条还没接线」那一行（没接线 ⇒ 空串，一行都不多）。"""
    return T("SYS_JOB_NO_WIRE") if _no_wire(x) else ""


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


def _kept(x) -> list:
    """★ fxb④（试玩 P1 BUG-4「交了还石头，刻字的石片还在背包里」）：交付物**去向说清**那一行。

    为什么**不是**「交活把东西收走」（不是漏做，是真源不许）：
      · `item` 条件在真源里的定义就是**持有条件** —— `00_总纲/08_第1批_字段级设计_v1.md`：
        `{"kind": "item", "item": <物品 id>, "n": <份数>}  背包里有 n 份`；
        `04_指令总表 §二` 的 `交 <编号>` 只写着「条件达成 → 交活结算」，
        全仓没有一处真源说过「交活要把东西交出去」。
      · 更要紧的是：这几件交付物**自己挂着「在身上」的钩子**，收走就变成长不出来的 ——
        `i_token_stone_shard` ｜ 彩蛋 2（`15 §二`：hold=… & read=… & where=…）· 瑟兰的隐藏台词
        （`dialogues.dlg_seran.hidden` 的 `need.holding`）；
        `i_horn_half` ｜ 彩蛋 4 ＋ 柯尔 / 皮特的隐藏台词（都要手里拿着号角）；
        `i_material_old_iron` ｜ 彩蛋 6（`hold=… & where=…`）。
        而石片与号角都是**信物**（`21 §四`：信物写「带着」= 不是装备 —— 本来就是攥在手里的东西）。
      ⇒ 依据报告 BUG-4 的第二条期望（「**若为后续彩蛋有意保留，回话里该说明**」），
        交付那一下**照实说清**东西还在你手上 —— 一行，不静默留白。
    """
    out = []
    for r in _require_of(x):
        if r.get("kind") != "item":
            continue
        iid = str(r.get("item") or "")
        if not iid:
            continue
        out.append(T("SYS_JOB_KEEP", name=_item_name(iid)))
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
    # ★ fix-m-bounty ②：这一段列的是**还能接的**活儿 —— 已交的不列（改前把在场 NPC 的支线
    #   **全列**，不看 `done` ⇒ 玩家照着点一条**交掉**的单子，回的是「这条你已经接了（或交过了）。」
    #   —— ranger b130/b131 实测；板子是「挂板墙上的单子」，交掉的单子不在板上）。
    #   过滤后一条不剩 ⇒ **连表头都不印**（下面的 `if side:` 已经管着）。
    _side_here = [n for n, _ in _npcs_here(p["loc"], p["node"], p=p)]
    side = [(qid, v) for qid, v in qs.items()
            if v["chain"] == "side" and v["giver"] in _side_here and qid not in done]
    if side:
        yield T("SYS_BOARD_SIDE_HEAD")
        for _qid, v in side[:3]:
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
    # ★ fix-m-bounty ①：「已经接过」这条守卫里，**只有悬赏跨了游戏日**才放行（见 `_reaccept_ok`）
    #   —— 改前 `k in _done(p)` 是**永久**挡（`quests_done` 只加不减）⇒ 悬赏交过一次以后
    #   **新的游戏日**再接仍回「这条你已经接了（或交过了）。」，三档悬赏实际成了一次性委托
    #   （游侠路 b125/b130 实测）。主线 / 支线 / 副业 / 同日重接**一个字都没松**（探针 ㊲ 钉着）。
    #   ★ 重接时**不把 k 从 `quests_done` 里摘掉**（那是完成记录，`calendar.main_done` /
    #     『评级』已交条数 / 图鉴 / 彩蛋都在读它）—— 只这一处放行。
    if k in _mine(p) or (k in _done(p) and not _reaccept_ok(x, k, p)):
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
    # ★ fxm3-questsnap（本波）：**接活这一刻落进度基线** —— `flags.quests[k]["base"]` 里记下每条
    #   条件现在的读数；从这一刻起 `require` 判的是「现在 − 基线」（`_since`）⇒ 接活**前**干过的
    #   活不再算数（改前 `require` 查历史态：到过三条带就能交主 3，白拿 118 经验 / 30 铜板）。
    #   · 位置 = 「已经接了 / 证 / 等级」三道门**之后**、`_hand_over` **之前**：
    #     位置在这三道门之后 ⇒ 没真接下的那条（被拦住）一个字都不落档；
    #     在 `_hand_over` 之前 ⇒ 接活时塞到手上的那件东西算「接活后到手」
    #     （真源 `17 §QUEST_SIDE25_STORY`「小满把那块石头塞给你」）。
    #   · 没写 `require` 的老条目 ⇒ 基线是空表（不多写一格没用的东西）。
    if _require_of(x):
        _set_base(p, k, x)                    # ★ 本波：接活快照（见文件抬头「进度基线」那一节）
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
    if not _obj_ok(x, p, k):              # ★ 本波：判「**接活后**新达成」（`k` = 基线在哪一格）
        if _no_wire(x):
            # ★ fxb②：这条的完成条件在数据面上还不存在（老条目那条死路径）—— 照实说
            #   「还没接线」，不糊一句「还没做完 + 一段与条件无关的进行中行文」。
            yield T("SYS_JOB_NO_WIRE")
            return
        yield T("SYS_JOB_NOT_DONE") + (_beat(x, "PROGRESS") or x["objective"])
        for line in _unmet(p, x, k):       # ★ P-25：把「还差什么」说清楚（老条目这里一行都不多）
            yield "  " + line
        return
    _set(p, "quests_active", [a for a in act if a != k])
    # ★ fix-m-bounty ①：**去重后再写** —— 悬赏跨游戏日交第二次时这条早在 `quests_done` 里了，
    #   照旧写 `+ [k]` 就是同一条进两份（『评级』的「已交条数」/ 图鉴 / `main_done` 都在读这本账
    #   ⇒ 计数会虚高）。顺序保持「第一次交掉」那一次的位置（只加不重排）。
    _done_now = _done(p)
    if k not in _done_now:
        _done_now.append(k)
    _set(p, "quests_done", _done_now)
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
    for _ln in _kept(x):              # ★ fxb④：条件的物件还在你手上 —— 照实说清（见 `_kept`）
        yield _ln
    yield T("SYS_JOB_REWARD", exp=x["reward_exp"], gold=x["reward_gold"])
    if leveled:
        yield T("SYS_JOB_LEVELUP", level=lv)
    if x.get("hook"):
        yield "（「%s」）" % x["hook"]


def _obj_ok(x, p, k=None):
    """交活判据 —— ★ P-25：写了 `require` 的条目**逐条真查**（做没做，档上有账）。

    · 主线：**等级 + 逐步记账** —— ★ B4-2 落了 `require` 之后，判据就是
      `level >= min_level` **且** `require` 逐条满足（12 条全写了 ⇒ 「1 级接 1 级主线、
      一句『交 1』就过」那条老路已经堵死）。没写 `require` 的主线仍只看等级。
    · 支线：写了 `require` 就逐条查；**没写的照旧**看 `flags.side_<名字>`
    ⇒ 没有 `require` 的老条目，这一支的行为逐字节不变（回归口径见任务卡 P-25）。
    ★ 本波（fxm3-questsnap）：`k` = 这条委托的 id —— 逐条查走的是「**接活后**新达成」
      （`_req_ok` → `_since`），不是历史态；不传 k = 老档口径（基线 0，与改前逐字节相同）。
    """
    reqs = _require_of(x)
    if x["chain"] == "main":
        return p.get("level", 1) >= x["min_level"] and all(_req_ok(p, r, k) for r in reqs)
    if reqs:
        return all(_req_ok(p, r, k) for r in reqs)
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


def _progress(x, p, k=None):
    """这一条的**进度**那一格（`（已达成 / 需要）`）—— 没写 `require` 的老条目回空串（一个字不多）。

    ★ QB-4（试玩报告 P4 E-10）：『我的委托』原先只给一句 objective —— 玩家要先跑一趟『交』
      失败一次，才知道自己听了几回（『交』那边写着「你听过 0 回」，两处不成体系）。
      真源：`06_第一阶段垂直切片/04_指令总表 §二`「`我的委托` `任务` ｜ 随时 ｜ 进行中的委托」
      ＋ 同一条委托自己的 objective（`24_任务线_v1 §二` 支 9「听他讲完（三次）」——
      「（三次）」是**文档那一格自己写的**，所以进度就该按它数：`（1/3）`）。
    ★ 数与『还差…』那几行走**同一个口**（`_have_n` —— 它就是交活那把尺子的读数）。
    ★ 本波（fxm3-questsnap）：`k` = 这条委托的 id ⇒ 数的是「**接活后**新达成」
      （不传 k = 老档口径，与改前逐字节相同）。
    """
    reqs = _require_of(x)
    if not reqs:
        return ""
    pairs = [_have_n(p, r, k) for r in reqs]
    return T("SYS_MINE_PROGRESS", done=sum(h for h, _n in pairs), n=sum(n for _h, n in pairs))


def _hint_lines(p):
    """『提示』优先给的那几行 —— **当前委托的下一步**（手上没活 ⇒ 空表，调用方退回地点那一句）。

    ★ QB-5（试玩报告 P1 BUG-3 / P4 E-1）：『提示』原先只看地点（镇上 / 野外各一句固定文案），
      从不随委托走 —— 1→3 级、交 0→3 条，镇上永远回建号那一句「先『观察』…再去『公会』」，
      而**每一条接活回话**都写着「『提示』会告诉你往哪走」（`quest_accept` 的 `SYS_JOB_GO`）。
      真源：`06_第一阶段垂直切片/04_指令总表 §一`「`提示` `去哪` ｜ 随时 ｜ **给一条当前该做什么
      的提示**」—— 「当前」= 手上这条活 ⇒ 先报它的名字与 objective，再逐条说还差什么
      （那几行就是『交』失败时给的同一批行，同一个口 `_unmet`）。

    ★ fxb②（试玩 P1 BUG-2 / UX-4）：**说得出下一步的才给** —— 手上那条要是「没接线」
      （`_no_wire`：非主线且没写 `require`），报出来只有一行标题、既没有「还差」也没有去处，
      等于拿一条死单把『提示』这条主线级辅助**永久占住**（QA 原话：「把真正能做的委托
      全部挡住」，`放弃 22` 才恢复）⇒ 跳过它，接着看手上下一条；全都没得说才退回地点那一句。
    """
    qs = _quests()
    for k in _mine(p):
        x = qs.get(k) or {}
        if not x:
            continue
        if _no_wire(x):
            continue                       # ★ 说不出一句可做的 ⇒ 不占这一屏（UX-4）
        out = [T("SYS_HINT_JOB", name=x.get("name", k), objective=x.get("objective", ""))]
        if _obj_ok(x, p, k):                # ★ 本波：与『交』同一把尺子（接活后新达成）
            out.append("  " + T("SYS_HINT_JOB_READY", order=x.get("order", 0)))
        else:
            out += ["  " + ln for ln in _unmet(p, x, k)]
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
            # ★ fxb②：没接线的那几条在列表里也**带一句标记**（不然玩家只看得出它「没有进度」）
            yield "· %s —— %s%s%s" % (x.get("name", k), x.get("objective", ""),
                                       _progress(x, p, k), _no_wire_line(x))
    if done:
        yield T("SYS_MINE_DONE", n=len(done))
    # ★ B4-14：那半句评级与『评级』**走同一个门**（`cmds_self.has_card`）—— 没办证的人
    #   原先在这一条里照样印「【评级】见习」，与同一刻『评级』回的「你还没有证」直接打架。
    from .cmds_self import has_card
    if has_card(p):
        # ★ B4-16：这一行与『评级』里那一行**同一槽位**（`SYS_MINE_RANK`）—— 档名现取
        yield T("SYS_MINE_RANK", tier=RK.label(RK.current(p)))
