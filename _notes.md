# B3-6b-2d-b 第一刀 · 「中文枚举当机器键」收成 ASCII 键（分支 `b3-6b-2d-keys` · 工作树 `C:/Users/yuyu/ast-wt/b362d`）

> 一句话：**装备那半的机器键从 items 的中文 `kind` 换成域里现成的 ASCII `slot`（97 件装备、
> 0 数据改动）；技能那半的机器键从 skills 的中文 `kind`（「主动」）换成 ASCII `owner_class`
> ＋ 域里那一份 kind 值。** 改前 31 处「拿中文枚举当机器键」→ 改后 17 处（余下 17 处全属
> 第二刀：非装备 kind / `monsters.role` / `recipes.kind` / drop_pools kind）。行为**逐字相同**：
> 1791 行对照输出零差异 · 27 个探针全绿 · 真宿主 e2e 走通装备/技能那条线。
>
> ★ 本批 **0 文案新增**（没有新 texts 槽位 ⇒ 真源 `17_文案收口口径_v1.md` 一个字没动）。
> ★ 本批 **0 数据改动**（`content/data/*.json` 一个字没动 —— 依据见 §二：两个 ASCII 维度
> `slot` / `owner_class` 域里本来就有）。

---

## 一、量准：「拿中文枚举当机器键」今天在哪（改前 31 处）

**口径**（K48 / K51 / P-20）：黑名单 = **域里现成的枚举字段取值**（只收这几族，含汉字的那些）：
`items.kind` `items.quality` · `monsters.role` · `recipes.kind` · `skills.kind` ·
`gathering.kind/verb` · `drop_pools` 的 `kind` 与条目 `kind`。
违规 = `content/*.py` 里出现与黑名单**逐字相同**的字符串字面量（docstring / 异常消息不算）。

**复现命令**（黑名单 53 个取值；同一把尺子已进 `probe_copy` ⑮，正式跑法见 §三）：

```bash
PY=/c/Users/yuyu/AppData/Local/Programs/Python/Python312/python.exe
GWEN_ENGINE=C:/Users/yuyu/framework-engine "$PY" scripts/probe_copy.py     # ← 看「中文枚举当机器键」那一行
```

改前逐点清单（文件:行 · 中文串 · 谁在比）：

| 文件:行 | 中文串 | 谁在比 | 本批？ |
|---|---|---|---|
| `content/loot.py:83` | 上甲 / 下甲 / 头盔 / 靴子 | `_resolve()` 挑 `*armor_random` 的候选（落域里 4 个 kind） | ✅ 改走 `slot` |
| `content/loot.py:85` | 武器 | 同上，挑 `*weapon_random` | ✅ 改走 `slot` |
| `content/loot.py:35` | 材料 | `K_MATERIAL`：条目 kind 的兜底值 | ⏳ 第二刀 |
| `content/loot.py:109` | 池 | `roll_pool()` 判嵌套池（drop_pools 条目 kind） | ⏳ 第二刀 |
| `content/loot.py:133` | 未鉴定 | `open_unid()` 判这一条是不是未鉴定池 | ⏳ 第二刀 |
| `content/cmds_recipe.py:197`（+`:51` 消费） | 武器 / 上甲 / 下甲 / 头盔 / 靴子 / 饰品 | `EQUIP_KINDS`：`强化` 的白名单（`_item_of_name(kinds=…)`） | ✅ 改走 `slot` |
| `content/cmds_recipe.py:110` | 烹饪 | `_cookable()` 按 recipes 的 kind 挑配方 | ⏳ 第二刀 |
| `content/codex.py:35`（4 个）/`:37`（2 个） | 材料 / 垃圾 / 线索 / 食物 / 信物 / 未鉴定 | `KIND_BOOK` / `PICK_BOOK`：进哪本谱 | ⏳ 第二刀 |
| `content/combat.py:81` / `:127`（3 个） | 普通 / 精英 / 头目 | 怪 actor 的 `role` 兜底 + `pick_encounter` 的候选闸 | ⏳ 第二刀 |
| `content/cmds_battle.py:117`（3 个） | 精英 / 头目 / 层主 | 掉钱公式按 `monsters.role` 分档 | ⏳ 第二刀 |
| `content/skills_lookup.py:91` | 主动 | `basic_skill_of()` 过滤候选（本职业普攻） | ✅ 改走 `owner_class` |
| `content/skills_lookup.py:81` | 主动 | `monster_skill()` 合成的怪技 dict 的 `kind` 值 | ✅ 改从域取 |
| `content/apply.py:101` | 主动 | `basic_fallback`（兜底普攻）的 `kind` 值 | ✅ 改从域取 |

（`content/apply.py:101` 的另一个字面量「挥击」**不是**枚举值 ⇒ 不在本表；它是「兜底普攻叫什么」的
文案，属第二刀 —— 见 §五 · S5。）

---

## 二、落法（ASCII 键从哪来 · 为什么不新建字段）

| 事 | 落法 | 依据 |
|---|---|---|
| 装备「是什么」 | items 的 **`slot`**（六格 · 域里现成的 ASCII） | `schemas/items.schema.json` 的 `slot.enum` = weapon / armor_top / armor_bottom / helmet / boots / accessory；**97 件装备全带、25 件非装备全不带** ⇒ 「走 slot」与「走 kind 六类白名单」**同集合**（`probe_items` ①之二 逐条钉着：kind→slot 是单射 + kind 把装备/非装备分得干净） |
| 动态掉落的「哪一格」 | `loot._GRID_SLOTS`：`*armor_random` / `*weapon_random` 的**格名本来就是 ASCII**，映射到 `slot` 集合 | 格名写在 drop_pools 的 `out` 上（`*armor_random`）；映射值全部来自域 |
| 「谁能用 / 属于哪个职业」 | skills 的 **`owner_class`**（`cls_knight` 这类 ASCII） | `basic_skill_of()` 只按 `owner_class == cls` 挑；等价性 = 域里「有 owner_class」的 30 条 kind **同值**（`probe_skills` ⑦ ① 钉着） |
| 技能类别**值**（引擎 `do_skill` 会比） | `skills_lookup.active_kind()`：**从 skills 域现取**（今天 = 域里那 30 条共用的值） | 代码里不再写死中文枚举；fail-closed：域里取不到就抛，**绝不回空串** |
| 中文名 → 机器键的**入参解析** | 一律保留（`_item_of_name` / `_norm_class` / `去 <地方>` 同族） | 那是「玩家/调用方给的是名字」，不是「拿枚举当键」；机器键本身（`slot` / `owner_class` / `class_name`）全是 ASCII |

**为什么不新建字段**：甲案的判据就是「已经有 ASCII 维度的一律不新建」（P-20 原话：
装备还是双射 上甲↔armor_top 10 · 下甲↔armor_bottom 9 · 头盔↔helmet 9 · 靴子↔boots 8 ·
武器↔weapon 49 · 饰品↔accessory 12；非装备 25 条没有 slot）⇒ 本批 **schema / 数据零改动**。
真需要新字段的（非装备 kind / role / recipes.kind / drop_pools kind / skills 词表）**整批留给第二刀**。

---

## 三、判据（只加强 · 数字钉住只许减）

```text
① probe_copy ⑮（新）★ 静态守卫：黑名单 = 域里现成的枚举字段取值（53 个），扫 content/*.py 的字面量
     · 总数「≤ 快照」（ENUM_KEYS，**只降不升**）：31 → 17
     · 加一条「已收口的取值清单」（ENUM_DONE = 武器/上甲/下甲/头盔/靴子/饰品/主动）——哪个文件都不许再出现
       （清单只许变长，不许变短）
② probe_copy ③ 快照上限（BUDGET）同步下调：loot 11→6 · cmds_recipe 9→3 · apply 2→1
③ probe_copy ② SEALED +1：skills_lookup.py 进「必须 0」那一栏（本批收口）
④ probe_items  ①之二 ★ 真数据判据：kind→slot 单射（域自己就是那张映射表）· kind 把装备/非装备
     分得干净（两种筛法**同集合**）· 六格全盖到 · 97 件全带 slot / 25 件一件都没带
     顺带 fail-closed：KINDS/QUALITIES 不再抄副本，schema 读不到就退（原先那份手写回退名单删了）
⑤ probe_drops  ⑬ ★ 真跑判据：`*armor_random`/`*weapon_random` 各 200 个种子挑出的**每一件都带 slot**
     且落在对应那几格 · 两格**零交集** · 认不出的格 ⇒ None（不猜）· dp_elite_gear 真抽一遍件件带 slot
⑥ probe_recipes ⑫ ★ 真跑判据：`equip_only` 收下的 = 「带 slot 的」（97 件 · 非装备一件都没收下）
     ＋ 真敲一次「强化 半页纸（材料）」⇒ 拒掉、档上不动
⑦ probe_skills ⑦ ★ 真数据判据：域里「有 owner_class」的 30 条 kind 同值 ⇒ 用 owner_class 筛 == 用 kind 筛
     ＋ `active_kind()` 取自域、且**不许是空串**（空串会让引擎把攻击技判成治疗）＋ 六职业普攻各在自己那班
```

**「旧签名」那条提示**：本批把 `cmds_recipe._item_of_name` 的关键字参数从 `kinds=`（中文白名单）
换成 `equip_only=`（走 slot）—— 仓内唯一调用点在 `enhance()`，已同步；探针里没有别处调用。

---

## 四、行为逐字相同（真跑对照 · 不是看代码）

驱动脚本（不进仓 · 放 `%LOCALAPPDATA%\Temp`）：`ast_cmp_b3_6b_2d_b.py`
——固定种子/固定假钟/遭遇钉死，抓 8 段共 **1791 行**：每个掉落池 ×12 种子 · 两个未鉴定池 ×24 种子 ·
`强化` 四类东西 ×（料够/料不够）· 六职业 `basic_skill_of` + 中文职业名 + `monster_skill` +
`skill_info` 四条 · `basic_fallback` · `_default_skills` · `run_auto` ×4 种子 ×2 怪（全日志）·
四个指令口（攻击/强化×3/状态）· `_item_of_name(equip_only)` 逐件 122 条。

```text
跑法（本批实测）：git stash push -- content/…（4 个文件）→ 跑 → git stash pop → 再跑 → diff
结果：before 1791 行 / after 1791 行 · diff **0 行**（唯一被忽略的一行是上面那条「旧签名」提示）
```

真宿主 e2e（`scripts/e2e_drive.py`，起手档 = 骑士 3 级 + 骨田）：

```text
» 状态                【冒烟】未定 · 骑士 · 3 级 / 生命 80/140 ｜ 铜板 500
» 强化 拾荒人的重剑    🔨 拾荒人的重剑 → +1（加成 +0.4%…）          ← 装备：真进白名单
» 强化 效果向饰品      🔨 效果向饰品 → +1（…）                      ← 饰品同理（slot=accessory）
» 强化 铁屑            背包里没有叫「铁屑」的装备。打『背包』看看。    ← 材料：仍被拒
» 强化 半页纸          背包里没有叫「半页纸」的装备。                 ← 线索：仍被拒
» 使用 药水            你喝下药水。生命 +42（122/140）
» 攻击                ⚠️ 遭遇：田鼠 → … → ✔ 打完了 / 拾取：🌿 苦叶 ×2   ← 掉落动态项走 slot
» 技能 横剑            🚧「技能 <参数>」还没接上 💡 敲「帮助」看现在能用什么（P-23 兜底，未实现）
» 装备对比 拾荒人的重剑 🚧「对比 <参数>」还没接上（同上）
```

---

## 五、第二刀清单（下一批照这个干 · 本批**故意没碰**）

> 判据：凡是没有 ASCII 维度、要**新增字段**的，一律留给第二刀（P-20 甲案原话：
> 「再给没维度的域补键（monsters.role → `role_key` · recipes.kind → `kind_key` · items 非装备 kind → `kind_key`）」）。
> 数字 = 本批实测（黑名单那把尺子）。

| # | 事 | 处数 | 落法建议（照 `quests.chain` / `gathering.verb` 那两次） |
|---|---|---|---|
| S1 | **items 非装备 25 条**（材料 9 · 食物 8 · 道具 2 · 信物 3 · 垃圾 2 · 线索 1）补 ASCII `kind_key` | 6 处（`codex.py` 谱归属 6 个字面量 + `loot.py:35` 那个兜底值「材料」） | schema 里 `kind_key` 紧跟 `kind`（`items.schema.json`）；映射在域里（**别在代码里写中文对照表**）；落法走 `scripts/rebuild_*.py` 或带 `--dry` 的迁移脚本（幂等 · 中文→ASCII 映射表写进域） |
| S2 | **`monsters.role` → `role_key`**（普通/精英/头目/层主/支援 · 17 条） | 7 处（`combat.py` 4 · `cmds_battle.py` 3） | `monsters.schema.json` + 生成器 `rebuild_monsters.py`（它本来就从文档解析 role 那几栏） |
| S3 | **`recipes.kind` → `kind_key`**（烹饪 8 / 强化 10） | 1 处（`cmds_recipe.py:110`）+ 探针侧 `probe_recipes.py:51/52` | `recipes.schema.json` + `rebuild_recipes.py` |
| S4 | **`drop_pools` 的 kind**（顶层「未鉴定」×2 + 条目 kind：池/装备/材料/道具/垃圾/信物/线索） | 2 处（`loot.py:109` 池 · `loot.py:133` 未鉴定） | `drop_pools.schema.json` 补 `kind_key`；`loot.kind_of()` 已经归到一口（B3-6b-2c），这次把**值**也换成 ASCII |
| S5 | **skills 的 kind 词表**（30 条全是「主动」）+ 兜底技「挥击」入域 | 0 处（本批已把代码里那 3 个「主动」字面量清掉） | ★ **先裁决再动**：引擎那三处比的是 `kind == _kind("heal")` / `_kind("buff")`（`ext_combat/battle/actions.py:110/112`），而 `_kind()` 走**内容侧 `kinds` 词表**（`game_config.kind_of`）——**本包没声明** ⇒ `_kind()` 恒回 `""`。两个坑：① `kind` 写成空串会被判成**治疗**（`"" == ""`）② `actions.py:545` 的 `seg_type` 于是恒落 `magi`。要动就得连 `kinds` 词表一起按甲案补（**会改战斗语义** ⇒ 单独立项 + 鱼鱼点头），别顺手做。 |
| S6 | 探针 / 生成器侧的同一族写法（同一把尺子量到 **117 处** = 生成器 48 + 探针 69） | 117 处 | 生成器（`rebuild_codex/equip_events/gathering/monsters/prof_quests/recipes` 共 48 处）**必须**引中文（它们解析的是策划案原文）⇒ 不适用；探针侧 69 处建议随 S1–S4 一起改（它们断言的是数据的枚举值），其中 `probe_items.py` 本批已 20 → 2（只剩两处 `quality == "遗物"`，等 S1 的 `kind_key` 一起收） |

★ 收完 S1–S4 后，`probe_copy` 的 `ENUM_KEYS` 可以整体清空 → 把 §三 ① 那条改成「必须 0」，
`loot.py` / `cmds_recipe.py` / `codex.py` / `combat.py` / `cmds_battle.py` 一起进 `SEALED`。

---

## 六、顺带核出来的真事（下一批/主线看这里）

1. **六职业的「普攻」今天取到的是 0 倍率的辅助技**（`basic_skill_of` 取 power 最低的那条 ⇒
   骑士=盾墙 · 刺客/游侠=后撤 · 修女=净罪 · 狂战=横劈 · 法师=垂星）。**本批不动**（行为逐字相同是判据），
   但**它是活的**：`ext_combat.resolve_basic_skill` 要求技能的 `exprs`/`formula`，而本包 30 条技能
   **一条都没有** ⇒ 取到的那条被引擎丢掉、真打的是 `basic_fallback`（挥击）。要让技能真进战斗，
   得先有 `exprs`/`formula`（属技能域那一整摊，别顺手做）。
2. **`_norm_class` 保留（没改成 ASCII-only）**：它比的是 `classes.<id>.name`（中文名）——那是
   **入参解析**（中文职业名 → 机器键），与 `_item_of_name` / `去 <地方>` 同族；机器键本身
   （`panel_build.build_actor` 写的 `class_name`、skills 的 `owner_class`）**全是 ASCII**
   （`content/panel_build.py:146`）。删了它 = 静默不再收中文职业名（**判据减弱**，本批不干）。
3. **本批 0 数据改动 / 0 文案新增**：`content/data/*.json` 与真源 `17_文案收口口径_v1.md` 都没动；
   `schemas/*.json` 也没动（没新字段）。「中文 → ASCII」的那张映射表**就是域本身**
   （`probe_items` ①之二 从数据里把它算出来核一遍）—— 不是代码里的一张表。
4. `game.json` 的域数 / `commands.json` 的声明数本批没变（99 声明 / 99 处理器，e2e 装配行）。

---

## 七、改了哪些文件（显式清单 · 提交用）

```text
content/loot.py            _GRID_SLOTS（格→slot）· _resolve 走 slot（原 kind 中文枚举）
content/cmds_recipe.py     _item_of_name(equip_only=…) · 撤 EQUIP_KINDS（强化白名单走 slot）
content/skills_lookup.py   basic_skill_of 只按 owner_class 挑 · 新 active_kind()（类别值从域取）·
                           _norm_class 补口径注释（保留的理由写清）
content/apply.py           basic_fallback 的 kind 改从 skills 域取（_active_kind）
scripts/probe_copy.py      ⑮ 新静态守卫 + ENUM_KEYS/ENUM_DONE · BUDGET 下调 · SEALED +skills_lookup ·
                           fixture 挑武器改走 slot
scripts/probe_items.py     装备 = 「带 slot 的那些」· kind/quality/slot 三份都从 schema 读（撤手写回退）
                           · ①之二 单射/同集合/六格全盖到
scripts/probe_drops.py     ⑬ 动态项按 slot 挑的真跑判据（200 种子 · 两格零交集 · 认不出的格 ⇒ None）
scripts/probe_recipes.py   ⑫ equip_only 逐件对账 + 非装备真跑被拒
scripts/probe_skills.py    ⑦ owner_class 等价性 + active_kind 取自域 + 六职业普攻
_notes.md                  本文（含第二刀清单）
```

（真源仓 `aetheran-plan` 一个字没动 · 引擎仓 `framework-engine` 一个字没动 ·
台账/口径文档按派活规矩由主线统一落。）

---


---

# 附录 · 上一批（P-27 生命上限收口）的 `_notes.md` 原文（保留备查）

# P-27 生命上限收口（分支 `p27-hp-source` · 工作树 `C:/Users/yuyu/ast-wt/p27-hp`）

> 一句话：**「生命上限」现在只有**一个**来源 = 职业面板（`content/panel_build.py`）**，
> 档上那格 `hp_max` 由它**派生**（原先 `apply.initial_save` 与 `cmds_ast.DEFAULT_PLAYER`
> 各写死 100 ⇒ 与面板两个源、且升级 / 换装都刷不动它）。顺手把 `probe_quests` 手打的
> `lv*lv*40` 改成走 `cmds_ast.exp_need`。
> 给主线两件活：① 下面那张**待补槽位表**（1 行）搬进真源再重跑生成器；② 台账 §3 的
> ⏳ P-27 改 ✅ + `06_第一阶段垂直切片` 那条「选职业」的依赖记一笔（见 §五 · L1）。

---

## 一、文案槽位

**本批没有新增 texts 槽位**（真源 `17_文案收口口径_v1.md` 只读）—— 按 skill §六 的退路
**借了现成槽位**顶替「还没有职业 ⇒ 算不出上限」那一行：

```text
（{name}：{keys} 还没接上。）      ← 槽位 SYS_POI_EFFECT_TODO
   {name} = 玩家名（空 ⇒ SYS_NAME_UNKNOWN「无名者」）
   {keys} = SYS_PANEL_PROF_BASE（「职业基础」）
实例（实测）：「（试档：职业基础 还没接上。）」
```

⇒ **待补的槽位行**（下一轮连同真源表一起加，然后把下面这处换成新键）：

| 槽位 | 文案 | 参数 | 类 | 出处 |
|---|---|---|---|---|
| `SYS_HP_UNSET` | （{name}：职业基础 还没接上。） | name | 系统 | P-27 · 无职业时的上限（生命 / 回血 / 战斗四处共用） |

代码里那处标了 `★ 待补的槽位名记这儿：SYS_HP_UNSET`（`content/cmds_ast.py::hp_cap_or_line`）。
**借槽位不影响门禁**：`SYS_POI_EFFECT_TODO` / `SYS_PANEL_PROF_BASE` / `SYS_UNSET` 都已在
texts 里、也都已被代码引用（probe_copy ⑤ 三条全绿）。

---

## 二、落法（口径一句话）

| 事 | 落法 | 依据 |
|---|---|---|
| 上限的来源 | `panel_build.hp_cap(record)`：职业（`cls_rec` 把关）+ 等级 + 加点 + **装备 + 食物增益**（`gear_and_buffs` 与战斗 actor 吃同一份） | 裁定甲案（面板为唯一真源）；「数值不许手打」 |
| 档上那格 `hp_max` | **派生值**：`cmds_ast._p()`（唯一出档口）现算 → 写进这份档；读它的人一律走 `hp_cap()` | 档上原先写死 100 的两个点是 `apply.py:146` / `cmds_ast.py:71` |
| 档上 `hp` / `hp_max` **不再进默认档** | `DEFAULT_PLAYER` / `initial_save` 里删掉这两格 | 「上限只有一个来源」；旧档那两格（写死的 100）由 `_p` **丢掉**，不许当上限用 |
| 空职业（还没择业） | = **还没声明**（合法稳态，不是错）：`hp_cap(strict=False)` 回 `None` ⇒ `状态` 照实说「未定」；要数字的四处（攻击 / 歇脚 / 药水 / POI 回血）出上面那一行点名行，**整支不做** | `fail-closed-boundaries` §1「没声明 / 声明错了」两档分开 |
| 职业不在 `classes` 域里 | = **声明错了** ⇒ 一律抛 `PanelMissing`（点名 + 列出现有的），**不吞** | 同上（§1 第二档）+ skill §6 反证⑥ |
| `combat.player_actor` | 撤掉 `player.get("cls") or "cls_knight"`（替玩家挑职业 = 两个源的起头）；钳制用的上限就是 `a["max_hp"]`（面板那一个） | 台账 P-27 只读复核 ②（`min(档hp, 面板max_hp)` 跨口钳制） |
| 装备的「生命上限」 | 32 条 hp 词条现在**真的进战斗血池**（档 = 面板 = actor，三处同值） | 台账 P-27 只读复核 ③（原先「装备的上限是死的」） |
| `probe_quests` ⑧ | 手打的 `lv*lv*40` → `from content.cmds_ast import exp_need` | 「数值不许手打」（与升级 / 死亡惩罚同一个口） |

---

## 三、本批核出来的真事

1. **现役生产库只有一条阿斯特兰档，而且 `cls` 是空的**（只读核过 `qqbot/.../game_data.db`
   的 `aetheran_players`）：`gm_playtest` / `gm_test_group` · `cls=""` · `level=1` ·
   `race=human` · `hp=100 / hp_max=100`。
   ⇒ **建号第二步「选职业」还没落地**（全仓没有 `be_class` / 「我是 <职业>」那类指令）——
   今天所有档都走「无职业」那一档。这正是 §二 里「未定 + 点名行」那一支存在的原因，
   也是本批**最大的遗留**（§五 L1）。
2. **`hp_max` 全仓原先只有两处写死 100**（`apply.py:146` · `cmds_ast.py:71`），
   现在 content 里 **0 处**（probe_panel ④ 静态守卫钉着）。
3. **`player_actor` 里那个 `or "cls_knight"` 与 `or (player.get("equip_stats") or {})`**
   都撤了（前者替玩家挑职业、后者是全仓没人写的旧键）。
4. **装备的 hp 词条不再是死的**（实测：骑士 L1 裸档 116 → 换一件带生命上限的装 129；
   面板 / 档 / 战斗 actor 三处都 129）。

---

## 四、门禁真实数字（本批实测）

```text
探针 25 个 · 对着「本分支基线那份真源（720b9bb · 107 行）」全绿 25/25
  · probe_panel ★ P-27 三处一致（真造 actor + 真读档 = content/persistence 落库再读回）
      骑士 L1 = 116 / L2 = 128 / L10 = 224 —— 面板 / 档 / actor 三处同一个数
      六职业 1 级：骑士 116 · 狂战 92 · 游侠 104 · 法师 90 · 修女 140 · 刺客 96（三处一致）
      加点 VIT×3 ⇒ 146（三处一致 · 高于裸档）· 换一件 hp 装 ⇒ 129（三处一致）
      反证：无职业 ⇒ PB.hp_cap / 战斗 actor / cmds_ast.hp_cap 三处都抛 PanelMissing（点名）
            错职业（cls_berserk）⇒ 点名抛 · 无职业 strict=False ⇒ None
      ④ 静态守卫：content/*.py 里「写死的上限」0 处
  · probe_copy ★ P-27：无职业档 `状态` = 「生命 未定/未定」（老档那两格写死的 100 也不出）；
      `攻击` ⇒ 「（无名者：职业基础 还没接上。）」且不开那一场；POI 回血（神龛）同一口径
  · probe_quests ⑧ 奖励复算改走 `exp_need`（不再手打）
  · probe_combat ⑧『输了血回满』fixture 去掉写死的 hp_max（回满 = 面板上限）
端到端真宿主（GWEN_ENGINE=framework-engine python scripts/e2e_drive.py）：
  ① 默认起手档（无职业）：「状态」⇒ 生命 未定/未定 · 「攻击」/「歇脚」⇒ 点名行 · 「触摸」照常
  ② 带职业起手档（骑士 L2 · 骨田 · hp80）：「状态」⇒ 生命 80/128（★ 原先恒 100）→
     「攻击」⇒ 真打完 → 「歇脚」⇒ 生命 +25（98/128）（20% 取的是面板的 128，不是 100）
引擎零改动：git -C framework-engine status --short 为空（本批没碰引擎）。
```

★ **并发引起的一条红（不是本批引入，别误判）**：对**活的**真源跑时 `probe_copy` 的
「口径表 N 条都落在 texts 里 / 每条都被代码引用」两条会红 —— 因为主线已把真源表推到
**125 行**（b33 的 8 条 `SYS_TRADE_*` + b35 的 10 条 `SYS_EV_*`），而那两个分支的
texts / 代码**还没进 master**（本分支切自 `d325086` = 321 槽位）。
同一现象在 master 工作树上也复现（它红的是 `SYS_EV_*`，因为那边刚重跑过 texts）。
⇒ **合入顺序**：先 merge（或先把 b33/b35 合进来）→ 重跑 `rebuild_syscopy.py` → 再跑 25 个探针
（本批的判据不受影响：对基线那份真源是 **25/25 全绿**）。

---

## 五、遗留与风险（下一位接手看这里）

| # | 事 | 为什么要问 / 怎么收 |
|---|---|---|
| L1 | ★★ **建号第二步「选职业」还没落地** ⇒ 今天所有档都是「无职业」⇒ `状态` 显示「生命 未定/未定」，`攻击` / `歇脚` / `药水` / 带 buff 的 POI 四处出点名行（**不出假数、也不崩**） | 这是本批把「上限只有一个来源」推到底的必然结果，也是**必须尽快拍的一件**：要么紧接着做建号第二步（`我是 <职业名>` 之类），要么先给一条口径「无职业时上限取谁」。今天生产库里只有 `gm_playtest` 一条档（§三 · 1），所以影响面仅限冒烟 —— 但**真玩家一进来就是无职业** |
| L2 | 法力（`mo_max`）同族：档上 0，面板算得 50 | 本批只收「生命上限」（点名范围）；`mo` / `mo_max` 要不要一起归面板，另开一句拍板 |
| L3 | `content/cmds_gather.py:135` 那句 `p["hp"] = p.get("hp", 1)`（采集顺手往档里塞个 1） | 本批没动（与上限无关，且无职业档读不到它）。它是一处**静默造默认值**，建议与 L1 一起清 |
| L4 | 档上 `hp_max` 是**出档口现算的快照**：升级（`add_exp`）后同一条命令里落档写的是升级前那一份 | 读到的一定是面板值（每次 `_p` 都现算）⇒ 不影响判据；要不要在升级点顺手刷一遍，看主线口径 |
| L5 | 借的槽位（§一） | 真源表加 `SYS_HP_UNSET` 后，把 `cmds_ast.hp_cap_or_line` 那处换掉（一行） |

---

## 六、改了哪些文件（显式清单）

```text
content/panel_build.py   PanelMissing · cls_rec（把关）· gear_and_buffs · hp_cap（唯一上限口）
content/cmds_ast.py      DEFAULT_PLAYER 去掉写死 100 · _p 出档口派生 · hp_cap / hp_cap_or_line ·
                         status「未定」· POI 回血走同一个口
content/cmds_gather.py   rest（歇脚）走上限口
content/cmds_recipe.py   _heal_gain / item_use（药水）走上限口
content/cmds_battle.py   attack 先判（无职业 ⇒ 点名行）· _wake_in_chapel「血回满」走上限口
content/combat.py        撤职业兜底与 equip_stats 旧键 · 钳制口径写清（上限 = 面板那一个）
content/apply.py         initial_save 不写 hp / hp_max
scripts/probe_panel.py   ★ P-27 一节（三处一致 + 反证 + 静态守卫）
scripts/probe_copy.py    ⑭ 两条判据 + 四处 fixture 带职业 + 两条「还没择业」用例
scripts/probe_combat.py  fixture 去掉写死的 hp_max（回满 = 面板上限）
scripts/probe_quests.py  ⑧ 改走 `exp_need`
scripts/probe_recipes.py fixture 去掉写死的 hp_max
```

（真源仓 `aetheran-plan` 一个字没动；台账/口径文档按派活规矩由主线统一落。）
