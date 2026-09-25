# B3-6b-2d-keys-2 **第二刀** · 剩下的「中文枚举当机器键」全收成 ASCII 键（分支 `b3-6b-2d-keys-2` · 工作树 `C:/Users/yuyu/ast-wt/b362d2`）

> 一句话：**代码里「拿中文枚举当机器键」从 17 处收成 0 处** —— 4 个域各补一格 ASCII 机器键
> （items `kind_key` · monsters `role_key` · recipes `kind_key` · drop_pools `kind_key`），
> 4 张 schema 跟着钉住取值，映射表的唯一来源在三支生成器/迁移脚本里，探针用**三头对账**
> （schema enum ↔ 生成器表 ↔ 域里的记录）看着它。行为**逐字相同**：27532 行对照输出里
> **只有 245 行**（＝机器键那一格本身）变了，**玩家看得见的那几节 0 行差异**；真宿主 e2e
> 的确定性子集 **0 行差异**。
>
> ★ 本批 **0 文案新增**（没有新 texts 槽位 ⇒ 真源 `17_文案收口口径_v1.md` 一个字没动）。
> ★ 本批 **0 值改动**（`content/data/*.json` 只多出机器键那一格：191 格，**没有一格是改数值/改文案**）。

---

## 一、量准：「拿中文枚举当机器键」改前 17 处 → 改后 0 处

**口径**（K48 / K51 / P-20）与第一刀同一把尺子：黑名单 = **域里现成的枚举字段取值**（含汉字的那些）：
`items.kind` `items.quality` · `monsters.role` · `recipes.kind` · `skills.kind` ·
`gathering.kind/verb` · `drop_pools` 的 `kind` 与条目 `kind`。
违规 = `content/*.py` 里出现与黑名单**逐字相同**的字符串字面量（docstring / 异常消息不算）。

**复现命令**：

```bash
PY=/c/Users/yuyu/AppData/Local/Programs/Python/Python312/python.exe
GWEN_ENGINE=C:/Users/yuyu/framework-engine "$PY" scripts/probe_copy.py   # ← 看「中文枚举当机器键」那一行
```

改前逐点清单（文件:行 · 中文串 · 谁在比）与改后处置：

| 文件:行（改前） | 中文串 | 谁在比 | 改后走什么 |
|---|---|---|---|
| `content/combat.py:81` | 普通 | 怪 actor 的 `role` 兜底 | `m.get("role") or m.get("role_key") or ""`（档位名照旧透传；**机器判定**走 `role_key`） |
| `content/combat.py:82`（隐含） | boss | `is_boss = (a["role"] == "boss")` | `is_boss = (m.get("role_key") == "boss")`（**换键前后同一只**：`ms_boss_oath_sentry`） |
| `content/combat.py:127`（3 个） | 普通 / 精英 / 头目 | `pick_encounter` 的候选闸 | `role_key in ("normal", "elite", "chief")` |
| `content/cmds_battle.py:117`（3 个） | 精英 / 头目 / 层主 | 掉钱分档 | `role_key`：`elite`→8 · `chief/warden/boss`→20 · 其余→3 |
| `content/cmds_recipe.py:116` | 烹饪 | `_cookable()` 挑配方 | `kind_key == "cook"` |
| `content/loot.py:35` | 材料 | `K_MATERIAL` 兜底 | `K_MATERIAL_KEY = "material"`（ASCII） |
| `content/loot.py:120` | 池 | `roll_pool()` 判嵌套池 | `e.get("kind_key") == "pool"` |
| `content/loot.py:144` | 未鉴定 | `open_unid()` 判未鉴定池 | `u.get("kind_key") != "unidentified"` |
| `content/codex.py:35`（4 个）/ `:37`（2 个） | 材料 / 垃圾 / 线索 / 食物 / 信物 / 未鉴定 | `KIND_BOOK` / `PICK_BOOK`：进哪本谱 | 两张表改成 ASCII 键（`material/junk/clue→material` · `food→flavor` · `keepsake/unidentified→relic`） |

逐文件处数（探针实测 · 改前 → 改后）：

```text
codex.py 6 → 0 · combat.py 4 → 0 · cmds_battle.py 3 → 0 · cmds_recipe.py 1 → 0 · loot.py 3 → 0
合计 17 → 0（探针那一行打印：「一处都没有 · 合 0 处」）
```

**顺带**：`content/cmds_gather.py:128` 调 `LT.kind_of(oid, e.get("kind"))` → 跟着换成
`LT.kind_key_of(oid, e.get("kind_key"))`（它不是字面量，所以不在 17 处里，但它是**同一条链**）。

---

## 二、落法（ASCII 键从哪来 · 为什么不新建 `_meta` 映射表）

| 事 | 落法 | 依据 |
|---|---|---|
| items 的机器键 | **每条记录多一格 `kind_key`**（第二刀 122 条全覆盖） | P-20 甲案样例（`{"kind":"武器","kind_key":"weapon"}`）＋ 台账「5 域约 189 条」（＝逐条一格，不是一张总表） |
| 装备那六类的键 | 与第一刀收的 `slot` **同值**（weapon / armor_top / …） | 第一刀已把装备的机器键收成 `slot`；`probe_items` ⑧ 钉着 `kind_key == slot`（97 件逐件核） |
| 非装备那六类的键 | material / food / tool / junk / keepsake / clue | 新增；`probe_items` ⑧ 核「非装备那半的键 = enum − slot 六格」 |
| monsters 的机器键 | `role_key`（17 条）：普通=normal · 精英=elite · 头目=chief（区域头目）· 层主=warden（副本层主）· boss（世界 Boss） | `08_第1批_字段级设计_v1.md §五` 的档位那一栏（旧案名：区域头目 / 副本层主）；★ `boss` 与引擎 `ext_combat` 那份 ASCII 词表同值 |
| recipes 的机器键 | `kind_key`（18 条）：烹饪=cook · 强化=enhance | 取值与 `recipes._meta.cook` / `_meta.enhance` **同名**（域里本来就这么叫） |
| drop_pools 的机器键 | 记录级（未鉴定 2 条）+ **条目级 32 条**：池=pool · 装备=gear · 材料=material · 道具=tool · 垃圾=junk · 信物=keepsake · 线索=clue · 未鉴定=unidentified | 条目里那 5 个与 items 的键**同值**（一个词表两处用，`probe_drops` ⑭ 跨域核） |
| 中文 `kind` / `role` | **保留**（玩家看得见的分类名 / 策划案原文的档位名） | 与 `quests.chain` / `gathering.verb` / 第一刀的 `slot` 同款 |
| 「中文 → ASCII」那张映射表的唯一来源 | 三支脚本里的三张表：`scripts/rebuild_kind_keys.py`（`ITEM_KIND_KEY` / `POOL_KIND_KEY`）· `scripts/rebuild_monsters.py`（`ROLE_KEY`）· `scripts/rebuild_recipes.py`（`KIND_KEY` / `DISH_KIND_KEY`） | 生成器侧**允许引中文**（它解析的是策划案原文，同 §六 S6）；运行时 `content/*.py` 一个字都不引（`probe_copy` ⑮ = 0 处） |
| 为什么不往域里再写一张 `_meta.kind_key_of` 总表 | 会打破「items/monsters 不许有 `_meta`」的现状（两张 schema 都不放 `^_`），且要动一串探针的迭代口径 | 台账原话是「5 域约 **189 条**」＝逐条一格；映射的**可核**性由三头对账保证（下表） |

**三头对账**（每个域都做了，`probe_*` 里那几条 ★）：

```text
schema 的 enum（校验口径 · 唯一真源）
   ↕ 逐值相等
生成器/迁移脚本里那张表（落数据的口径）
   ↕ 逐条一致（中文 → ASCII 单射）
域里的 191 格 kind_key / role_key
```

★ 这样表漂了、enum 漂了、数据漂了，三种都能抓出来 —— 而这正是「改成 ASCII 键」之后最怕的一类病
（代码比 A、域里写 B ⇒ 静默不命中）。`probe_copy` ⑯ 另外从**代码那一头**再核一遍
（代码里比的 ASCII 键都在域里真出现过）。

**幂等**（连跑两遍数据逐字节不变 · md5 实测）：

```text
scripts/rebuild_kind_keys.py --dry     → 「要补 156 处」→ 写入 → 再跑「要补 0 处 · 无新增（幂等 ✓）」
scripts/rebuild_monsters.py            → 连跑两遍 monsters.json md5 da7abb71… 不变
scripts/rebuild_recipes.py             → 连跑两遍 recipes.json/items.json md5 不变（items「变 0 处」）
```

---

## 三、判据（只加强）

| 探针 | 新增/改动的判据 |
|---|---|
| `probe_copy` ⑮ ★ | 「拿中文枚举当机器键」从「≤ 快照 17」改成「**必须 0 处**」（ENUM_KEYS 清空）；已收口取值清单 `ENUM_DONE` 从 7 个扩到 **22 个**（两刀的并集，只许变长）；`SEALED` **+ codex.py**；`BUDGET` 全线下调：cmds_battle 14→**11** · loot 6→**3** · cmds_recipe 3→**2** · combat 5→**1**（apply.py 1 不变） |
| `probe_copy` ⑯ ★（新） | 代码里比的 ASCII 机器键**都在域里真出现过**：monsters ⊇ normal/elite/chief/warden/boss · items ⊇ material/junk/clue/food/keepsake · drop_pools ⊇ pool/unidentified · recipes ⊇ cook（与 ⑦ chain / ⑧ verb 同款） |
| `probe_items` ⑧ ★（新） | 每件都带 `kind_key` 且在 enum 里 · **生成器表 == schema enum** · 中文 kind→kind_key 单射且与表逐条一致 · 装备 97 件 `kind_key == slot` · 非装备 25 件落在「enum − slot」六格里 |
| `probe_monsters` ②之二 ★（新） | 每只带 `role_key` 且在 enum 里 · 生成器表 == enum · 单射 · 五档全盖到 · **`role_key == "boss"` 命中的 = `role == "boss"` 命中的**（同一只）· `boss` 这个键只从那一档来（头目/层主不卷进来） |
| `probe_recipes` ①之二 ★（新） | 每条带 `kind_key` 且在 enum 里 · 生成器表 == enum · 单射 · **`_cookable()` 与域里 cook 那 8 条同一个集合** |
| `probe_drops` ⑭ ★（新） | 池 2 条 + 条目 32 条都带对的 `kind_key` · 生成器表 == enum（池侧 8 类）· 单射 + 全 ASCII · **跨域**：条目那 5 个键与 items 的 `kind_key` 同值 · **真跑** `kind_key_of()` 每件东西/未鉴定池都回域里那一格 · 认不出的回兜底键 `material` · 条目写了键就优先用它（`gear` ≠ `weapon`）<br>（⑤ 加「未鉴定四类出口的**机器键**齐」· ⑥ 分布改按 `kind_key` · ⑪ 未鉴定池按 `kind_key` 挑） |
| `probe_codex` ⑨ ★（新） | 代码两张表只有 ASCII 键且不撞键 · 表里的键都在域里真出现过 · **逐件真跑 122 件 + 2 个未鉴定池：归属 == 表算出来的** · 认不出的不进任何谱 · 装备 97 件一件都不进谱（② 两条改按 `kind_key`；「装备那类不进谱」fixture 改走 `slot`） |
| `probe_combat` ⑮⑯ ★（新） | **真造 actor**：`role` 照旧透传 + `is_boss` 与旧写法逐只相同（17 只）· 遇敌候选闸换键前后**同一批**（15 只）· **真挑 6×5×5 把**挑出来的全在闸里、层主/世界 Boss 不混进 · 掉钱分档换键前后**逐只同值** + 三档都还在用 |
| `probe_events` ⑩ / `probe_quests` ⑩ | 两处「中文 role」的镜像改按 `role_key` 重算（探针那一头的机器判定也收成 ASCII） |

改前/改后「内联中文文案」逐文件计数（`probe_copy` ①②③ 那把尺子，只降不升）：

```text
apply.py 1 → 1   cmds_battle.py 14 → 11   cmds_recipe.py 3 → 2   combat.py 5 → 1
loot.py 6 → 3    codex.py 6 → 0（进 SEALED）
```

---

## 四、行为逐字相同（真跑对照 · 不是看代码）

驱动脚本（不进仓 · 放 `%LOCALAPPDATA%\Temp`）：`ast_cmp_b3_6b_2d_keys2.py`
—— 固定假钟 + 固定种子，S1–S12 共 **27532 行**：每个掉落池 ×12 种子 · 两个未鉴定池 ×24 种子 ·
`_resolve` 三格 ×20 种子 · `kind_of` 逐件 122 + 2 · 图鉴归谱逐件 + `new_lines` + 进度 ·
17 只怪 actor 全字段 · `run_auto` 17 只 ×3 种子（**全日志 25475 行**）· `pick_encounter`
全图全节点 ×5 等级 ×5 种子 + mul 三分支 · 「攻击」五档位各一只（遭遇钉死）·
配方（`_cookable` / 一览 / 烹饪 4 例 / 铁匠铺 / 强化 5 例）· 采集 19 个点各两遍 ·
状态 / 背包 / 图鉴呈现。

```text
跑法：改前跑一遍（baseline）→ 改后跑一遍 → 逐行 diff
结果：before 27532 行 / after 27532 行 · 差异 **245 行**，全部落在「机器键那一格」：
  · S1/S2 共 120 行 = 掉落记录：`"kind": "材料"` → `"kind_key": "material"`（字段名 + 值一起换）
  · S4  共 125 行 = `kind_key_of()` 的返回值：13 个中文枚举值 → ASCII 键（**双射**：中文→ASCII 唯一、反过来也唯一）
  · S5–S12（图鉴归谱 / 怪 actor / 战斗日志 / 遇敌挑选 / 「攻击」五档 / 配方 / 采集 / 状态·背包）
    = **0 行差异**
★ stash 基线复跑一致（`diff before before3` 为空）⇒ 上面那份 diff 不是脚本自己抖出来的。
```

真宿主 e2e（`scripts/e2e_drive.py` · 起手档 = 骑士 3 级 · 北带骨田 · 假钟 epoch=723600）：

```text
» 状态        【无名者】未定 · 骑士 · 3 级 / 生命 80/140 ｜ 铜板 500
» 采集        【碑缝里的草】… 得到：🌿 苦叶 ×2 ｜ ★ 新进谱：材料谱 · 苦叶        ← kind_key 那条线
» 挖掘        【塌了一半的坑】得到：❓ 一块刻着字的石片 ×1 ｜ ★ 新进谱：旧物谱 · 一块刻着字的石片
                                                                              ← 未鉴定池的 kind_key
» 搜查        【骨田里那根钩子】得到：🪝 捡来的钩子 ×1                          ← 信物 → 旧物谱
» 配方        【配方】会做 8 道 · 还没学会 0 道（…）                            ← kind_key == "cook"
» 烹饪 苦叶汤  做苦叶汤要：苦叶 ×2 · 石斑 ×1。你还差：石斑 ×1。
» 铁匠铺      柯尔的炉子还热着。… +1..+5 必成，+6 起看运气。
» 强化 拾荒人的重剑  🔨 拾荒人的重剑 → +1（加成 +0.4%，走装备本体 —— 上限 +4.0%）
» 图鉴        【图鉴】四本谱 … 材料谱 4/10 ｜ 风味谱 1/8 ｜ 怪物谱 0/12 ｜ 旧物谱 2 条
» 背包        【背包】9 种 … ❓ 一块看不出用途的旧东西 ×1（未鉴定的名字取自池上）
» 攻击        ⚠️ 遭遇：田鼠 → … → ✔ 打完了。｜ 拾取：🌿 苦叶 ×2                ← 掉落 + 掉钱分档
» 战斗日志    【上一场】田鼠 …

★ 确定性子集（状态/采集/挖掘/搜查/配方/烹饪/铁匠铺/强化/图鉴/背包）**改前 vs 改后 0 行差异**
  （e2e 里「攻击」那一支走不可复现的遭遇随机 ⇒ 那一段只做「跑得通」的证据，逐字比对交给上面那份对照驱动）
```

---

## 五、门禁真实数字（本批实测）

```text
全量探针 28 个：**28 绿 / 0 红**（`for f in scripts/probe_*.py; do … done`）
  · probe_copy   ⑮ 17 → **0 处** · ⑯ 四条全绿 · ①②③ 与 BUDGET/SEALED 全绿
  · probe_items  ⑧ 五条全绿（122 件 · 装备 97 件 kind_key == slot）
  · probe_monsters ②之二 六条全绿（17 只 · boss 只有 ms_boss_oath_sentry）
  · probe_recipes ①之二 四条全绿（18 条 · _cookable == cook 那 8 条）
  · probe_drops  ⑭ 八条全绿（池 2 + 条目 32 · 跨域 5 键同值）
  · probe_codex  ⑨ 五条全绿（122 件 + 2 池逐件真跑归属）
  · probe_combat ⑮⑯ 六条全绿（17 只 actor · 真挑遇敌全在闸里 · 三档掉钱）
生成器幂等：三支连跑两遍，四份数据文件 md5 逐字节不变
schema：四张都还是合法 JSON；`required` 跟着加了新字段（items / monsters / recipes）
引擎仓 framework-engine：`git status --short` 为空（零改动）
真源仓 aetheran-plan：`git status --short` 为空（真源待补的行见 §七，由主线统一落）
```

---

## 六、遗留与风险（下一位接手看这里）

| # | 事 | 为什么要问 / 怎么收 |
|---|---|---|
| L1 | ★★ **skills 的 `kind` 词表（30 条全是「主动」）没动** —— 引擎那三处比的是 `kind == _kind("heal")` / `_kind("buff")`（`ext_combat/battle/actions.py:110/112`），而 `_kind()` 走**内容侧 `kinds` 词表**（`game_config.kind_of`），**本包没声明** ⇒ `_kind()` 恒回 `""`。两个坑：① `kind` 写成空串会被判成**治疗**（`"" == ""`）② `actions.py:545` 的 `seg_type` 于是恒落 `magi`。**动它等于改战斗语义** ⇒ 单独立项 + 鱼鱼点头。本批**只登记不动手**（第一刀留的坑，原样保留） |
| L2 | **`a["role"]` 照旧透传中文档位名**（本批有意选的：引擎那份 `role` 限定规则是**逐字比对内容侧词汇**的，而 `is_boss` / 遇敌闸 / 掉钱分档都改走 `role_key`）。好处 = 逐字相同（对照 diff 里 S6 那 17 行 actor 全字段零差异）；代价 = 引擎那句 `role == "boss"` 仍然靠数据里那一格恰好是 ASCII `boss` 命中 —— 与改前**一模一样**，没变好也没变坏 |
| L3 | **drop rec 的机器键那一格改名了**（`{"id","n","kind"}` → `{"id","n","kind_key"}`，值也从中文换成 ASCII 键） | 全仓的**读端只有** `scripts/probe_drops.py`（已同步）；`content/*.py` 里没人读它（`add_to_bag` 只读 id/n）。`open_unid()` 同理（`{id, kind_key, from_unid}`） |
| L4 | **`items.quality` 还是中文**（普通/精制/稀有/遗物） | 代码里没有拿它当**字面量**比的地方（17 处里没有它）；`loot._resolve` 里那句是「池条目声明的品质 vs 物品自己的品质」＝**数据对数据**，不是「中文枚举当机器键」（同 `gathering.verb == verb` 那一族）。要不要补 `quality_key` 由主线定，本批不动 |
| L5 | 生成器/探针侧同一族写法（第一刀记的 117 处 = 生成器 48 + 探针 69） | 生成器必须引中文（解析策划案原文）⇒ 不适用；探针侧本批顺手把**与代码同一条链**的几处收了（`probe_recipes` 51/52/191 · `probe_drops` ⑤⑥⑪ · `probe_codex` 72/74/139 · `probe_events` 306 · `probe_quests` 147）。**断言数据中文枚举值**的那些（`probe_monsters` 五档位、`probe_items` quality、`probe_combat` 旧写法镜像、`probe_codex` 旧物谱的读/捡）**有意保留**：它们是「数据那一栏没写错」的判据 |
| L6 | 三条兜底仍是「不猜不崩」的旧语义 | `kind_key_of()` 认不出的 id ⇒ `material`（原来是「材料」，同一语义的 ASCII 写法）· `monster_actor` 缺档位名 ⇒ 拿 `role_key` 顶上（都没有 ⇒ 空串，两条路在引擎那边都是「不是 boss」）· 两处都是**不可达分支**（探针钉着「每条都带键」）。要不要改成 fail-closed（抛）另算 |

---

## 七、要补的真源行（真源仓只读 ⇒ 写在这儿，请主线统一落）

| 真源文件 | 补什么 |
|---|---|
| `00_总纲/AETHERAN_推进进度.md` | P-20 那条：**第二刀已落** —— 包（本工作树提交短 hash）· 「17 处 → 0 处」· 4 域 191 格新键 + 4 张 schema + 迁移/生成器三支 + 探针三头对账；并记 L1（skills `kind` 词表 = 单独立项） |
| `00_总纲/08_第1批_字段级设计_v1.md` §五 monsters 字段表 | 加一行：`role_key` \| str \| ★ ASCII 机器键（normal/elite/chief/warden/boss —— 代码只认它；`role` 是中文档位名 / 策划案原话） |
| `00_总纲/08_第1批_字段级设计_v1.md` §六 items 字段表 | 加一行：`kind_key` \| str \| ★ ASCII 机器键（装备六类与 `slot` 同值；非装备 material/food/tool/junk/keepsake/clue） |
| `00_总纲/13_配方域口径_v1.md`（recipes 那段） | 加一句：配方多了 `kind_key`（烹饪=cook · 强化=enhance，与 `_meta.cook` / `_meta.enhance` 同名） |
| drop_pools 的口径文档（哪一份由主线定） | 加一句：池与条目多了 `kind_key`（池=pool · 装备=gear · 未鉴定=unidentified；材料/道具/垃圾/信物/线索与 items 同值） |
| `00_总纲/17_文案收口口径_v1.md` | **不用改**（本批 0 文案新增） |

---

## 八、改了哪些文件（显式清单 · 提交用）

```text
content/loot.py                   K_MATERIAL → K_MATERIAL_KEY（ASCII）· kind_of → kind_key_of（回 ASCII 键）·
                                  嵌套池判 kind_key=="pool" · 未鉴定判 kind_key!="unidentified" ·
                                  drop rec / open_unid 那一格改名 kind_key
content/codex.py                  KIND_BOOK / PICK_BOOK 两张表改 ASCII 键 · note_item 读 rec["kind_key"]
content/combat.py                 monster_actor：role 照旧透传 + is_boss 走 role_key ·
                                  pick_encounter 候选闸走 role_key（normal/elite/chief）
content/cmds_battle.py            掉钱分档走 role_key（elite 8 / chief·warden·boss 20 / 其余 3）
content/cmds_recipe.py            _cookable() 走 kind_key == "cook"
content/cmds_gather.py            调 loot.kind_key_of（随域改名）
content/data/items.json           +122 格 kind_key（其余一字未动）
content/data/monsters.json        +17 格 role_key（紧挨 role）
content/data/recipes.json         +18 格 kind_key（紧挨 kind）
content/data/drop_pools.json      +34 格 kind_key（2 条记录级未鉴定 + 32 条条目级）
schemas/items.schema.json         kind_key（enum 12 · 进 required）
schemas/monsters.schema.json      role_key（enum 5 · 进 required）
schemas/recipes.schema.json       两个 pattern 各加 kind_key（enum cook / enhance · 进 required）
schemas/drop_pools.schema.json    kind_key（记录级 enum 8 · entries/pool 的 items 也钉住同一份 enum）
scripts/rebuild_kind_keys.py      ★ 新：items / drop_pools 的 kind_key 落法（--dry · 幂等 · 映射表唯一来源）
scripts/rebuild_monsters.py       ★ 新：ROLE_KEY 表 + 写 role_key
scripts/rebuild_recipes.py        ★ 新：KIND_KEY / DISH_KIND_KEY（菜那一格也带上，重跑不丢）
scripts/probe_copy.py             ⑮ 改成「必须 0」· ENUM_DONE 扩到 22 · SEALED + codex.py · BUDGET 下调 · ⑯（新）
scripts/probe_items.py            ⑧（新）三头对账 + 装备 kind_key == slot
scripts/probe_monsters.py         ②之二（新）三头对账 + boss 同一只
scripts/probe_recipes.py          ①之二（新）三头对账 + _cookable 同集合
scripts/probe_drops.py            ⑭（新）三头对账 + 跨域 + 真跑；⑤之二 / ⑥ / ⑪ 改按 kind_key
scripts/probe_codex.py            ⑨（新）逐件真跑归属；② 两条 / 装备 fixture 改按 kind_key / slot
scripts/probe_combat.py           ⑮⑯（新）真造 actor + 真挑遇敌 + 掉钱分档逐只对账
scripts/probe_events.py           ⑩ 候选闸镜像改按 role_key
scripts/probe_quests.py           ⑩ boss 存在性改按 role_key
_notes.md                         本文（含真源待补行与剩下的账）
```

（真源仓 `aetheran-plan` 一个字没动 · 引擎仓 `framework-engine` 一个字没动 ·
台账/口径文档按派活规矩由主线统一落。）
