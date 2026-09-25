# B3-9 · 装备与技能那组（`装备` / `卸下` / `装备对比` / `学习` / `技能`）

> 工作树 `C:/Users/yuyu/ast-wt/b39`（分支 `b3-9-equip-cmd` · 基线 `a03ac54`）
> 真源仓只读：本文件是**交接单** —— 要补的真源行在 §六，合入时由主线写进真源表再跑生成器。

---

## §一 本批做了什么

| 指令 | 声明 | 接上的实现体 | 真跑到的支路 |
|---|---|---|---|
| `装备 <装备>`（装 / 穿） | `equip` | `content.cmds_gear:equip` | 穿上 · 同一位子换下（旧的回收进背包）· 已经穿着 · 不是能穿的 · 背包里没有 |
| `卸下 <装备>`（卸 / 脱） | `unequip` | `content.cmds_gear:unequip` | 按名字 / id / 部位名 / 部位键认 · 空参列身上 · 空身 · 身上没这件 |
| `对比 <物品>`（装备对比） | `item_compare` | `content.cmds_gear:item_compare` | 有增有减 · 位子空着 · 全一样 · 带 note 的只出「改规则」那一行 |
| `学习 <技能名>`（学） | `skill_learn` | `content.cmds_skill:skill_learn` | 四道门（没有这条 / 不是本职业 / 解锁等级没到 / 已经会了）+ 落档 |
| `技能`（技能表） | `skills` | `content.cmds_skill:skills` | 本职业此刻解锁那一班 + 还没到等级的另起一拨 + 老档认不出的 id |

三条装备指令动的是**同一格**：档上的 `equipped`（六格，词表 = `schemas/items.schema.json`
的 `slot.enum`）。数值一律借 `content/gear.py` 那一个出口（`gear_stats` / `enhance_bonus`）——
本批**一行数值口径都没新写**（所以「穿上之后面板真的变」是结构性的：改 `equipped` ⇒
`panel_build.hp_cap` / 战斗 actor 下一拍跟着变，P-27 那套派生口径不用动）。

两条技能指令的真源是**档上的 `skills`**（`combat.player_actor` 取的就是它）——
「看到什么 = 打起来放什么」由 `probe_cmds` ⑩ 真跑钉着（`actor["skills"]` 与档上一个字不差）。

新增两个文件（都在包内，**引擎零改动**）：

```
content/cmds_gear.py    装备 / 卸下 / 装备对比（+ 词条呈现那两支）
content/cmds_skill.py   技能 / 学习（+ 解锁那一班那两支）
```

---

## §二 新增槽位（47 行 —— 请照抄进真源 `00_总纲/17_文案收口口径_v1.md` 的槽位表）

★ 键**不带反引号**（`ROW_RE` 只认裸键名，带反引号会静默少一条 —— 踩过）。
★ 本批在分支里是**直接写进生成物** `content/data/texts.json`（445 → 492 条）；
合入时请把这 47 行补进真源表再跑 `rebuild_syscopy.py`（两边逐字一致它才不抛）。

| 键 | 文案 | 参数 | 类 | 出处 |
|---|---|---|---|---|
| SYS_GEAR_IN_BAG | 背包里没有『{name}』。 | name | 系统 | 装备 · 背包里没有这件 |
| SYS_GEAR_NOT_WEARABLE | 『{name}』不是能穿的 —— 只能拿在手上。 | name | 系统 | 装备 · 这件不是装备 |
| SYS_GEAR_WORN | 『{name}』已经穿在身上了。 | name | 系统 | 装备 · 已经穿上了 |
| SYS_GEAR_EQUIP_OK | 你穿上了{icon}{name}（{kind}）。 | icon,kind,name | 系统 | 装备 · 穿上 |
| SYS_GEAR_SWAP_OUT | 换下的『{name}』收回了背包。 | name | 系统 | 装备 · 同一位子换下 |
| SYS_GEAR_UNEQUIP_OK | 你卸下了{icon}{name}（{kind}）—— 收进背包。 | icon,kind,name | 系统 | 卸下 · 脱 |
| SYS_GEAR_NOT_WORN | 你身上没有『{name}』。 | name | 系统 | 卸下 · 身上没这件 |
| SYS_GEAR_NAKED | 你身上什么都没穿。 | - | 系统 | 卸下 · 空身 |
| SYS_GEAR_WEARING | 身上穿着：{list} | list | 系统 | 卸下 · 没点名时列出身上那几件 |
| SYS_GEAR_SLOT_EMPTY | （这个位子空着） | - | 系统 | 对比 · 现在这件为空 |
| SYS_GEAR_AFFIX_ROW | · {label} +{value} | label,value | 系统 | 装备/对比 · 词条数值行 |
| SYS_GEAR_AFFIX_NOTE | · {note} | note | 系统 | 装备/对比 · 效果类词条（域里那句人话） |
| SYS_GEAR_HP_CAP | 生命上限 {old} → {new} | new,old | 系统 | 装备/卸下 · 面板派生的上限跟着变（P-27） |
| SYS_CMP_HEAD | 【对比】{name}（{quality} · {kind}） ｜ 现在这件：{cur} | cur,kind,name,quality | 系统 | 对比 · 抬头 |
| SYS_CMP_EMPTY | {kind}这一格还空着 —— 穿上就是净赚。 | kind | 系统 | 对比 · 位子空着 |
| SYS_CMP_ROW | · {label}：{old} → {new}（{sign}{delta}） | delta,label,new,old,sign | 系统 | 对比 · 逐词条差值 |
| SYS_CMP_ROW_SAME | · {label}：{value}（一样） | label,value | 系统 | 对比 · 这一项没变 |
| SYS_CMP_NOTE_NEW | · 手里这件改规则：{note} | note | 系统 | 对比 · 手里那件的效果类词条 |
| SYS_CMP_NOTE_CUR | · 现在这件改规则：{note} | note | 系统 | 对比 · 身上那件的效果类词条 |
| SYS_CMP_VERDICT | （更好 {up} 项 · 更差 {down} 项 · 一样 {same} 项） | down,same,up | 系统 | 对比 · 收尾计数（不合成总分 —— 词条无权重） |
| SYS_SKILL_HEAD | 【技能】{cls} · 已会 {known} 条 ｜ 还没到等级 {locked} 条 | cls,known,locked | 系统 | 技能 · 抬头 |
| SYS_SKILL_ROW | · {name}（{kind}） ｜ 耗法 {mp} ｜ 冷却 {cd} 刻 | cd,kind,mp,name | 系统 | 技能 · 一条 |
| SYS_SKILL_NOTE |     ↳ {note} | note | 系统 | 技能 · 域里那句 note |
| SYS_SKILL_LOCKED | · {name} —— 到 {lv} 级才能学 | lv,name | 系统 | 技能 · 解锁等级还没到（skills.lv） |
| SYS_SKILL_TAIL | （打架时敲『技能 <名>』放一条。） | - | 系统 | 技能 · 收尾 |
| SYS_SKILL_NOCLS | 你还没定下职业 —— 技能跟着职业走。 | - | 系统 | 技能/学习 · 档上没有职业 |
| SYS_SKILL_NONE | 没有『{name}』这条技能。 | name | 系统 | 学习 · 域里没这条 |
| SYS_SKILL_NOTMINE | 『{name}』是{owner}的技能 —— 你学不了。 | name,owner | 系统 | 学习 · 不是本职业的 |
| SYS_SKILL_TOO_LOW | 『{name}』要 {lv} 级 —— 你还差 {gap} 级。 | gap,lv,name | 系统 | 学习 · 解锁等级没到 |
| SYS_SKILL_ALREADY | 『{name}』已经写在册上了。 | name | 系统 | 学习 · 已经会了 |
| SYS_SKILL_LEARN | 你把『{name}』记上了技能表 —— 本职业此刻解锁的 {n} 条都在册。 | n,name | 系统 | 学习 · 落档（整班一起记，免得丢默认那一班） |
| SYS_SKILL_STALE | （技能表里有 {n} 条现在认不出了 —— 数据换过。） | n | 系统 | 技能 · 老档上的 id 已经不在域里 |
| SYS_STAT_ATK | 攻击 | - | 系统 | 词条名 · atk（01_属性字典 §2.2） |
| SYS_STAT_HP | 生命 | - | 系统 | 词条名 · hp → max_hp（01_属性字典 §2.2） |
| SYS_STAT_DEF | 防御 | - | 系统 | 词条名 · def（01_属性字典 §2.2） |
| SYS_STAT_SPD | 速度 | - | 系统 | 词条名 · spd（01_属性字典 §2.2） |
| SYS_STAT_CRIT | 暴击 | - | 系统 | 词条名 · crit（01_属性字典 §2.2） |
| SYS_STAT_MATK | 法术攻击 | - | 系统 | 词条名 · matk（01_属性字典 §2.2） |
| SYS_STAT_RES | 抗性 | - | 系统 | 词条名 · res（01_属性字典 §2.2） |
| SYS_STAT_HIT | 命中 | - | 系统 | 词条名 · hit（01_属性字典 §2.2） |
| SYS_STAT_EVA | 闪避 | - | 系统 | 词条名 · eva（01_属性字典 §2.2） |
| SYS_STAT_MO_MAX | 法力 | - | 系统 | 词条名 · mo_max（01_属性字典 §2.2） |
| SYS_STAT_HEAL_POW | 治疗强度 | - | 系统 | 词条名 · heal_pow（01_属性字典 §2.2） |
| SYS_STAT_BLOCK | 格挡 | - | 系统 | 词条名 · block（01_属性字典 §2.2） |
| SYS_STAT_RES_FIRE | 火抗 | - | 系统 | 词条名 · res_fire（01_属性字典 §二·五） |
| SYS_STAT_RES_ICE | 冰抗 | - | 系统 | 词条名 · res_ice（01_属性字典 §二·五） |
| SYS_STAT_RES_SHADOW | 暗抗 | - | 系统 | 词条名 · res_shadow（01_属性字典 §二·五） |

---

## §三 判据（只加强）

| 探针 | 加了什么 |
|---|---|
| `probe_cmds.py` ④ | 老那条（`装备对比…` 回 soon 句）改成**更硬**的写法：回的是实现体那句人话、不再是 `SYS_CMD_SOON` |
| `probe_cmds.py` ⑨ | 真宿主真敲 6 条（装备 → 状态 → 对比 → 卸下 → 学习 → 技能）：逐字对槽位 · 档上 `equipped` 真改 · 面板派生的上限真跟着变 · 穿脱回原样 · 同一件东西**两条真分开**（对比出头 · 装备出穿上）· 回话里没有物品/技能 id · 没有取不到文案 |
| `probe_cmds.py` ⑩ | 六职业 1 级解锁那一班（30 条 = 域里挂 `owner_class` 的全部）· 四道门逐门真跑 · 落档后档上那班 = actor 那班 · 真打一场出真伤害 |
| `probe_cmds.py` ⑪ | `装备对比` **四档整段逐字对账**：期望值由 `gear_stats`（唯一取值口）+ texts 现算，不手写镜像串；并断言一行 `[MISSING TEXT` 都没有 |
| `probe_cmds.py` UNBOUND_MAX | 「声明了、可见、还没实现」**只许降**：本批 38 → 33，钉成常量 |
| `probe_panel.py` ⑤ | 穿一件带 hp 词条的装 ⇒ 面板 / 档（真落库读回）/ 战斗 actor **三处一起涨** ⇒ 卸下 ⇒ 逐字回原样 + 幂等（同一档再跑一遍穿脱两段逐字相同） |
| `probe_items.py` ⑨ | 词条呈现口径：不带 note 的数值词条（15 个键）都有 `SYS_STAT_*` 标签 · 带 note 的 30 个键原样出 note |
| `probe_copy.py` ⑰ | 新接的 5 条进用例表（真跑 108 → 127 个实现体）⇒ ⑥ 的「不缺文案 / 不漏机器键」自动罩到它们身上 |

★ 一条本来会漏的**真 bug 被自己新加的判据抓到**：`dmg_half_chance` 这类词条**既有数值又有 note**，
`gear_stats` 会把它的数值也并进面板 ⇒ 对比的数值行原先会去找 `SYS_STAT_DMG_HALF_CHANCE`（没有这个槽位），
真机上出 `[MISSING TEXT: …]`。修法：对比的数值行只比**不带 note** 的词条（带 note 的走「改规则」那一行）——
`probe_cmds` ⑪ 为此专门加了第 4 档。

---

## §四 实跑数字

```
「声明了、可见、包内还没实现」  38 → 33（本批降 5 条：equip / unequip / item_compare / skills / skill_learn）
                                  probe_cmds ⑨ 的 `UNBOUND_MAX = 33` 钉住「只许降」
「帮助」列的可用量               59 → 64 条（可见 + 有 bind；probe_cmds ⑤ 逐条对账）
探针                            28 个全绿（本批加 5 节判据：probe_cmds ⑨⑩⑪ · probe_panel ⑤ · probe_items ⑨）
probe_copy 真跑实现体            108 → 127 个
texts 域                        445 → 492 条（+47，全部是本批新增槽位）
```

e2e 真宿主逐字（`scripts/e2e_drive.py`，起手档 `AST_E2E_SEED`）：

```
» 状态
    生命 140/140 ｜ 法力 0/0 ｜ 铜板 120
» 装备 轻下甲
    你穿上了🩳轻下甲（下甲）。
    · 生命 +33
    生命上限 140 → 173
» 状态
    生命 140/173 ｜ 法力 0/0 ｜ 铜板 120
» 装备 拾荒人的重剑
    你穿上了⚔️拾荒人的重剑（武器）。
    · 攻击 +9
» 装备对比 哨兵的长剑
    【对比】哨兵的长剑（精制 · 武器） ｜ 现在这件：拾荒人的重剑
    · 攻击：9 → 10（+1）
    · 暴击：0 → 10（+10）
    · 速度：0 → 13（+13）
    （更好 3 项 · 更差 0 项 · 一样 0 项）
» 卸下 拾荒人的重剑
    你卸下了⚔️拾荒人的重剑（武器）—— 收进背包。
» 卸下 轻下甲
    你卸下了🩳轻下甲（下甲）—— 收进背包。
    生命上限 173 → 140
» 状态
    生命 140/140 ｜ 法力 0/0 ｜ 铜板 120
» 学习 盾墙
    『盾墙』已经写在册上了。
» 技能
    【技能】骑士 · 已会 5 条 ｜ 还没到等级 0 条
    · 守誓斩（主动） ｜ 耗法 15 ｜ 冷却 5 刻
        ↳ 挨打换来的那一刀
    · 盾墙（主动） ｜ 耗法 8 ｜ 冷却 6 刻
        ↳ 替队友接下一次指向技能
    · 横剑（主动） ｜ 耗法 0 ｜ 冷却 0 刻
        ↳ 挨打段的普攻：伤害低，但攒守誓
    · 不退（主动） ｜ 耗法 30 ｜ 冷却 30 刻
        ↳ 300 刻霸体 + 全队减伤 30%
    · 挑战咆哮（主动） ｜ 耗法 12 ｜ 冷却 12 刻
        ↳ 仇恨 ×3，把对面的出手拉过来
    （打架时敲『技能 <名>』放一条。）
```

第二趟（对比里带 note 的词条 + 学习真落档）：

```
» 装备对比 重上甲
    【对比】重上甲（稀有 · 上甲） ｜ 现在这件：重上甲
    · 防御：4（一样）
    · 生命：21 → 23（+2）
    · 火抗：0 → 60（+60）
    · 现在这件改规则：受伤时 10% 概率减半
    （更好 2 项 · 更差 0 项 · 一样 1 项）
» 学习 盾墙
    你把『盾墙』记上了技能表 —— 本职业此刻解锁的 5 条都在册。
```

---

## §五 不做的 / 如实报的

1. **技能数据缺 `exprs` / `formula`（如实报，不自己造数值公式）**：`skills` 域 30 条**全都没有**
   `exprs` / `expr` / `formula` / `heal_formula`。**不是打不出来** —— 引擎
   `ext_combat/battle/actions.py` 的 `_one_seg_damage` 在「非 formula / 非 expr」那一支按
   `atk|matk × power + skill_flat` 兜底算（`probe_cmds` ⑩ 真打一场、`probe_combat` ⑤ 一直钉着）。
   ⇒ 今天 30 条的伤害只吃 `power`，**技能等级成长（逐级 exprs）那一路是空的**；
   要真做「技能强化 / 逐级成长」得先给域补 `exprs`，那是**数值口径**，不在这一批拍。
   ★ 另：`skills.*.desc` 指的是槽位名（如 `SKILL_KNT_slash_desc`），**texts 域里 0 条**
   ⇒ `技能` 那一栏只能出 `note`（域里现成的人话），不能出 desc。补 desc 要先补 30 行槽位。
2. **「技能点」那一档不存在**：`07_装备体系_v2 §一` 写「技能强化点 每 2 级 1 点」，域里没有任何承载
   ⇒ `学习` 的守卫按声明里那句「等级 / 点数够」的**等级那一半**落地（`skills.lv` = 解锁等级）。
3. **今天 30 条 `skills.lv` 全是 1** ⇒ 1 级就解锁全班 ⇒ `学习` 的实际效果是「把此刻解锁的那一班
   落进档上的技能表」（`SYS_SKILL_LEARN`），**不是逐条从无到有**。这是照 `02_技能体系规划_v1 §四`
   「T1 是等级到自动学」的口径落的；等 11–20 级那 12 条补进域（带 `lv`），这一条才逐级显出增量。
   ⇒ 记一条**待拍板**：技能到底是「等级自动学」还是「手动一条条学」？（今天两者同集合，改法只影响
   `cmds_skill.known_ids` 一处；`probe_cmds` ⑩ 里那条「今天没有 lv>1 的技能」会随数据翻红提醒。）
4. **卸下回背包不走 `loot.add_to_bag`**：那个口会顺手把东西记进 `codex`（掉落路径要它、卸下不要）
   —— 走它会让「穿一次再脱」凭空多一条图鉴记录、也不满足「逐字回原样」。本批按 `_take` 的逆写一格。
   若以后要统一成一个口，得先给 `add_to_bag` 加个「别记 codex」的开关。
5. **装备事件的「装备在身」那一半没做**：台账（第十四次留账 ③）写「装备事件的『装备在身』要等
   『装备』指令有处理器」—— 现在处理器有了，但那六条挂载现在读的是 `need.holding`（背包里带着），
   不是 `equipped`。要加 `need.wearing` 得同时动 `cmds_talk._pick_indexed`（另一条线的文件）+ 
   `probe_equip_events` 的六条判据 ⇒ **留给下一批**，本批不碰 `cmds_talk.py`。
6. **重名技能**：`后撤` 一对（游侠 `SKILL_RNG_backstep` / 刺客 `SKILL_SHD_backstep`）—— `学习 后撤`
   认到的是排序靠前的那条（游侠的），别的职业会被 `SYS_SKILL_NOTMINE` 挡住。玩家想学**自己**那条
   同名技时得靠 id（今天没有「按职业优先」的择优）。记遗留。
7. **对比不合成总分**：只给「更好 N 项 / 更差 N 项 / 一样 N 项」。词条之间没有可比权重（那要 PE 尺），
   本批不拍脑袋给一个分数。带 note 的规则类词条（`res_element` 那 16 处「火/冰/暗 选一」）也不进数值行。
8. **`skills` 域里的 `lv_band` / `tier` 没消费**：`lv_band`（P1…P5）与 `tier`（1–5）今天没有读端，
   本批只用了 `owner_class` + `lv`。等 T2–T5（转职）那几条进来再谈。
9. 本批**没动**引擎、没动 `content/cmds_talk.py`、没动 `content/cmds_tower.py`、没动别的批次的文件；
   其它 33 条「声明了没实现」的指令一条没碰（`achievements` / `alloc` / `attrs` / `board_show` / …）。

---

## §六 合入时要补的真源

1. `00_总纲/17_文案收口口径_v1.md`：把 §二 那 **47 行**照抄进槽位表（新开一节，如 §十五
   「装备与技能（B3-9）」）⇒ 再跑 `scripts/rebuild_syscopy.py`（口径表 268 → 315 行；两边逐字一致）。
2. 上一条跑完 `probe_copy.py` 的 ⑤「口径表每条都被引用」会**自动**把新 47 行纳入（都已真跑引用到）。
3. 本批 `probe_cmds.py` 的 `UNBOUND_MAX = 33` —— 下一个接指令的批次把它往下调（只许降）。
4. `skills` 域的 `desc` 槽位（30 行）与 `exprs`（数值口径）另立条目，不在本批。
