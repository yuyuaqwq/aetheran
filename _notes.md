# B3-4 装备事件（equip_events）· 落批笔记

分支 `b3-4-equip-events`（工作树 `C:/Users/yuyu/ast-wt/b34`）
真源：`aetheran-plan/06_第一阶段垂直切片/30_装备事件_设计_v1.md`（含 P-15 四条裁决）
上游：`21_长期目标层_v1.md §四`（6 条装备事件）· `15_装备逐件数值_v1.md`

---

## 一、文案槽位：本批**没有新增 texts 槽位**

```text
6 句装备事件的台词全部写在**域内联**（dialogues 5 条 / monsters 1 条）——
理由：dialogues 域的形状是 `nodes{节点:{texts:[{need,text}]}}`，schema 里
`additionalProperties:false` 且**没有槽位字段** ⇒ 域里只能放字符串本身；
B1-4 落 dialogues 域时就是这么做的（皮特/瑟兰那两条原本也在域里）。
`aetheran-plan` 一个字没动（真源只读）。

★ 若将来要把这 6 句收进 `00_总纲/17_文案收口口径_v1.md` 的槽位表（走单一真源），
  按 `| 键 | 文案 | 参数 | 类 | 出处 |` 就是下面这 6 行 —— 但那要先给 dialogues/
  monsters 域加一个「槽位」字段（域形状改动 = 另一件事），本批没做：
```

| 键 | 文案 | 参数 | 类 | 出处 |
|---|---|---|---|---|
| `DLG_EQUIP_SENTRY_GAUNTLET` | （他先看的是你的手，不是你的脸）「哪儿来的。」…「脱了。在我这儿别戴。」 | 无 | 装备事件 | `dialogues.dlg_hagen.nodes.hidden.texts[0]`（真源 30 §三 行 1 · 21 §四 行 1） |
| `DLG_EQUIP_HORN_HALF` | （他看见号角，整个人静下来 —— 静得不像他）… | 无 | 装备事件 | `dialogues.dlg_pete.nodes.hidden.texts[0]`（B1-4 已落 · 本批纳入判据） |
| `DLG_EQUIP_STONE_SHARD` | （她拿过去翻了两下，脸色变了一点）… | 无 | 装备事件 | `dialogues.dlg_seran.nodes.hidden.texts[0]`（B1-4 已落 · 本批纳入判据） |
| `DLG_EQUIP_SCAVENGER_BLADE` | （他盯着你手上那把刀，往后退了半步，又站住了）… | 无 | 装备事件 · 战内 | `monsters.ms_pick_scavenger.encounter_lines[0]`（真源 30 §四 ① 甲案） |
| `DLG_EQUIP_OLD_AMULET` | （他看了一眼就停住了）「这个……」… | 无 | 装备事件 | `dialogues.dlg_ed.nodes.hidden.texts[0]`（真源 30 §三 行 5） |
| `DLG_EQUIP_UNDERWATER_STEPS` | （她接过去，没有立刻看…）「石头不是本地的。」… | 无 | 装备事件 | `dialogues.dlg_lian.nodes.main.texts[0]`（真源 30 §三 行 6） |

（后 3 行是本批新写的文案；前 3 行的文字本来就在域里，本批只是把它们纳入判据。）

---

## 二、六条事件：落在哪（判据：`scripts/probe_events.py`）

| # | 装备 | 消费端 | 挂载处 | 触发条件（域里写的） |
|---|---|---|---|---|
| 1 | `i_set_sentry_gauntlet` 哨兵的护手 | 哈根 `npc_hagen`（北墙根 · 昏/夜） | `dlg_hagen/hidden[0]` | `need.holding` |
| 2 | `i_horn_half` 半截号角 | 皮特 `npc_pete`（客栈） | `dlg_pete/hidden[0]` | `need.holding`（B1-4 已落） |
| 3 | `i_token_stone_shard` 刻字的石片 | 瑟兰 `npc_seran`（镇口） | `dlg_seran/hidden[0]` | `need.holding`（B1-4 已落） |
| 4 | `i_set_scavenger_blade` 拾荒者的短刃 | 拾荒人 `ms_pick_scavenger`（拾荒营地等） | `ms_pick_scavenger.encounter_lines[0]` | `need.holding`（**战内先开口** —— 新形状） |
| 5 | `i_set_northwall_amulet` 老人的护符 | 艾德 `npc_ed`（白烛堂） | `dlg_ed/hidden[0]` | `need.holding` |
| 6 | `i_token_underwater_steps` 石阶缺的那一级 | 莉安 `npc_lian`（白烛堂） | `dlg_lian/main[0]` | `need.holding` |

形状只有一条：`need` 条件择优（现成）。第 4 条照真源 30 §四「甲案」走**战内台词** ——
`cmds_battle.encounter_lines()` 读怪身上的 `encounter_lines`，判定复用
`cmds_talk._pick_indexed`（**同一个 need 口，不另写求值器**）；代码里零文案。

---

## 三、P-15 四条裁决（真源 §二）→ 数据

| 裁决 | 真源原话 | 落法 |
|---|---|---|
| ① | 「水下的石阶（钓上的那件）」**做出来** · 归**信物** · 出产挂**浅滩钓点的稀有位** | 新增 `i_token_underwater_steps`（信物 · 遗物 · 来处取自 codex 旧物谱 `poi_underwater_steps.hint`）；出产挂 `gt_bw_fish_2`（浅滩 · 垂钓）的池，`w=10` = 该域「关键物」的现成惯例（5 个搜查点的套装件都是 10）⇒ 池里**最稀**的那一位（40/40/20 → 10） |
| ② | 套装件那件**改名**「北墙根的碎石」 | `i_set_northwall_shard.name`：刻字的石片 → 北墙根的碎石（信物 `i_token_stone_shard` 留名） |
| ③ | 半截号角**只留信物** `i_horn_half` | 删 `i_item_horn_half`（删前脚本全仓扫引用 = 0 处，fail-closed） |
| ④ | 护符**数据留「老人的护符」**（改 21 文档去对齐数据） | 数据一个字节不动；脚本反向断言它就是「老人的护符」（防有人反过来改数据） |

★ 命名上的一处**有意偏离**（照 P-15 的判定原则「哪一边更像『东西本身』就留哪边」）：
`pois` 域里已经有**地方**叫「水下的石阶」（可读物 `poi_underwater_steps`），
所以钓上来的**东西**不叫这个名字，叫「石阶缺的那一级」（`desc` 里点明它来自哪）。
判据 ② 就是拦这件事的：**物品名不许与 pois 名撞**（今天 0 撞）。
⇒ 主线改 21 文档那一行时，建议写成「石阶缺的那一级（钓上的那件）」。

---

## 四、口径一句话

**装备事件的唯一形状 = 「身上带着某件东西 + 走到某人/某怪跟前 → 多说一句」**：
`need.holding` 条件写在域里（人走 dialogues 域的节点、怪走 monsters 域的战内台词），
代码只传 data；判定只有一口（`cmds_talk._pick_indexed`），文案只有一处（域内联）。

---

## 五、遗留与风险（下一位接手看这里）

1. ★ **真源文档待主线同步两处**（`aetheran-plan` 只读，本批没动）：
   - `21_长期目标层_v1.md §四`：四处名对齐数据 —— 「北墙根的护符」→「老人的护符」·
     「刻字的石片」（套装件那行）→「北墙根的碎石」· 「拾荒人的短刃」→「拾荒者的短刃」·
     「水下的石阶（钓上的那件）」→「石阶缺的那一级（钓上的那件）」。
   - `00_总纲/16_称号域口径_v1.md`：`title_wall_listener` 的条件 `heard@dlg_hagen>=8`
     **要改成 9** —— 本批给哈根的树加了一条（装备事件），树的台词条数 8 → 9。
     过渡期状态：`content/data/titles.json` 里登记值已按现算改成 9（probe_titles 全绿），
     但 `scripts/rebuild_titles.py` 会**fail-closed 报错**（它读的是文档里的 8）——
     这正是那个数「不许手打、必须与现算相等」的哨兵，等文档改成 9 就恢复。
2. ⚠️ **「装备着」这一半今天做不到**：`装备`（equip）这条声明**没有处理器**（P-23 家族），
   `equipped` 永远是空的 ⇒ 6 条事件今天都走「**带在身上**」（设计原文也允许：
   「装备在身（**或带在身上**）」）。等 P-23 裁了、equip 真能穿，可再补一条 `worn` 条件的
   同款挂载（但 `_pick_indexed` 现在只认 `holding`，那一支要另立形状）。
3. ⚠️ **第 3 条（瑟兰）依赖 B3-5**：她的出场条件写着 `event: caravan`，而 `_npcs_here`
   今天**不判** event（P-16）⇒ 她永远在场、所以这条今天测得到。B3-5 落完要把 `event` 判定
   接进 `_npcs_here`，那时「商队没来 ⇒ 这条拿不到」要重新验一遍。
4. ⚠️ **新信物没进旧物谱**：`codex` 那 16 条是 `scripts/rebuild_codex.py` 从
   `00_总纲/14_图鉴四谱口径_v1.md` 生成的，加一条要改真源 ⇒ 本批没加。
   ⇒ 「端详 石阶缺的那一级」今天会回「不是旧东西」（fail-closed），要认得它得先补口径表那一行。
   （顺带：`pois` 里那处地方已经在旧物谱里，`ask` 写着 `npc_lian` —— 与第 6 条事件同一个方向。）
5. `pois` 的 `condition`（`poi_underwater_steps` 写着 `time: ["退潮"]`）仍然没有消费端（P-31），
   「退潮」也不是合法时辰/天气 —— 与 B3-4 无关，但它是这条隐藏线的另一半。
6. 本批**没动**台账/口径文档（按派活规矩，主线统一落账）；也没动 `content/cmds_talk.py`
   （另一条线在改它 —— 本批只**导入**它的 `_pick_indexed`，一个字没改）。

---

## 六、门禁真实数字（本批实测）

```text
探针 26 个全绿（原 25 个 + 本批新增 probe_events）
  · probe_events 16 条判据（含 ★ 真跑：真宿主 + 假钟 5 条逐条「带着拿到 / 不带拿不到」）
  · probe_copy：内联中文文案 cmds_battle 14 · 快照上限 14（**没涨**）· SEALED 5 个文件 0
  · probe_items / probe_dialogues / probe_gather / probe_codex / probe_titles 全绿
端到端真宿主冒烟（GWEN_ENGINE=framework-engine python scripts/e2e_drive.py）：
  ① 夜（假钟 epoch=6300）带护手 → 去 北墙根 → 搭话 哈根 ⇒ 拿到「（他先看的是你的手…）」
     对照（不带）⇒ 「（他看着你，不说话。）」
  ② 带号角 → 搭话 皮特 ⇒ 「（他看见号角，整个人静下来…）」
  ③ 带石片 → 搭话 瑟兰 ⇒ 「（她拿过去翻了两下，脸色变了一点）…」
  ④ ★ 带短刃 → 拾荒营地连续「攻击」：第 1 场遭遇拾荒人**先开口那句**；
     打完它掉了「拾荒者的短刃」进背包 ⇒ 之后每场遭遇拾荒人都认得出这把刀（实测 5/5）
  ⑤ 带老人的护符 → 搭话 艾德 ⇒ 「（他看了一眼就停住了）…」
  ⑥ 带石阶残块 → 搭话 莉安 ⇒ ★ 她第一次把一句话说完（「北边运来的。修它的人，
     不打算让它留在水面以上。」）；对照（不带）⇒ 「守着我们不该动的。」
撤改验证（判据是活的）：① 新信物改叫「水下的石阶」⇒ 判据 ② 当场红；
  ② 把莉安那条挪到兜底句之后 ⇒ 判据 ⑥ + 真跑 + 幂等三条同时红；③ 撤掉战内接线 ⇒ 战内两条红。
引擎零改动：git -C framework-engine status --short 为空。
```
