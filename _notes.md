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
