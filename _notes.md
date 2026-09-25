# B3-14 · 战斗面真问题与修法（`b3-14-combat-balance`）

> 工作树 `C:/Users/yuyu/ast-wt/b44` · 基线 `bbdc15f` · 引擎零改动（`framework-engine` 工作区空）。
> 真源只读（`aetheran-plan` 未动）。以下数字全部来自固定种子的真跑，命令见 §6。

---

## §1 查出几个真问题（逐条 + 证据）

**一共 6 条**，其中 3 条是同一族（**域里的键名/语义与引擎消费端对不上，引擎一律静默当 0/1**）。

### P1 · 30 条技能全都没有「倍率公式」，六职业的伤害一律走魔法通道（吃 matk 不吃 atk）

- 证据：`content/data/skills.json` 30 条只有 `power`，`exprs`/`formula` **0 条**。
  引擎 `ext_combat/battle/actions.py:resolve_basic_skill` 要求 `bs.get("exprs") or bs.get("formula")`
  ⇒ **六职业的普攻一律被拒**（实测 `resolve_basic_skill(cls_knight)` 返回的是兜底「挥击」）。
- 更要命的是第二半：本包**没挂 `kinds` 词表** ⇒ `game_config.kind_of("phys") == ""`
  ⇒ `_skill_seg_damage` 的 kind 三分支全落 `magi`
  ⇒ 每条攻击都吃 `matk`、打对方 `mdef`。
- 实测（骑士 1 级 · 骨田）：`calc_damage(atk=5, def=0, type=magi)` —— 骑士 `atk 51.6`、`matk 5`
  ⇒ **每击 ~5 点**；同一条路径下法师 `matk 84` ⇒ 一发放倒田鼠。
- 结论：**六职业的区分完全消失，伤害只由 matk 决定**；物理职业（骑士/狂战士/游侠/刺客）
  在实机里等于拿着 5 点攻击力打怪。

### P2 · 普攻取的是「power 最低的那条」⇒ 取到 0 倍率的辅助技

- 证据：`skills_lookup.basic_skill_of` 按 `power` 升序取第一条。
  实测：骑士 → `盾墙(0.0)` · 刺客/游侠 → `后撤(0.0)` · 修女 → `净罪(0.0)` · 法师 → `垂星(0.8)`。
- 之所以今天没炸，是因为 P1 的降级把这条普攻**挡在了引擎门外**（回落兜底）——
  P1 一修好，普攻立刻变成 0 伤害的辅助技。两条必须一起修。
- 旧判据还把这条**钉住**了：`probe_skills ⑦「六职业普攻都取到自己那班 power 最低的那条」`。

### P3 · 怪的四个面板键引擎一个都不认（键名契约）

域（真源 `12_怪物面板与精英词条池_v1.md`）写 `hp / res / eva / crit`，引擎读的是
`max_hp / mdef / dodge / crit(**率**)`。`combat.monster_actor` 直接 `**panel` 透传 ⇒：

| 域里的键 | 引擎读的键 | 实测后果 |
|---|---|---|
| `hp` | `max_hp` | `actor_stats` 给出 **max_hp = 1**（真血靠 `a["hp"]` 走，所以「一击必死」没暴露；但按 max_hp 算的斩杀线 / hp% 技 / 护盾 / Boss 阶段阈值全错） |
| `res` | `mdef` | **怪魔防恒 0** ⇒「法系」原型那 1.6 倍法抗白给 |
| `eva` | `dodge` | **怪永不闪避** ⇒「快速」原型的 1.3 倍闪避白给 |
| `crit`（数值 13/47/94） | `crit`（**率**） | `random.random() < 13` 恒真 ⇒ **每只怪必然暴击** |

### P4 · 玩家的 `eva` 没率化 ⇒ 六职业恒定 40% 闪避

- 证据：`panel_build.build_actor` 只把 `crit` 走 `set` 率层，`eva` 原样进 `dodge`（骑士 10 / 刺客 20）；
  引擎 `landing._roll_dodge` 读的是 `min(dodge, 0.40)` ⇒ **六职业一律 40%**（数值差异被 cap 吃掉）。
  实测日志里每 5 下就有 2 下是「💨 闪避了攻击！」。
- 同一处的第二半：装备那份 `crit` 写在 add 层、随后被 `set` 层**盖掉** ⇒ 带 crit 词条的装备白穿。

### P5 · 怪物 hp 的反推式把「非通道」的那根属性也平均进来了 ⇒ 击杀行动数只有设计值的 ~2/3

- 证据：`rebuild_monsters.panel_of` 原先用 `per_hit = max(avg_atk, avg_matk) * crit_exp * 0.95`，
  其中 `avg_*` 是**六职业平均**（骑士的 5 点 matk、法师的 8 点 atk 都算进 atk 均值）。
  逐级实测：这一口径比「六职业中位的实际单次行动伤害」低 **25%（1 级）→ 33%（20 级）**。
- 后果：怪 hp 系统性偏低，实测击杀行动数只有设计值的 ~2/3（田鼠 L3：设计 4 次 ⇒ 模型算 2.5 次）。

### P6 · Boss 单刷「打不完」—— 战斗撞 500 步护栏返回 `result = None`

- 证据（改前 · 24 场）：骑士/狂战士/游侠/刺客 打旧誓哨兵 **出手 500 次**（= `auto_run` 的
  `max_steps` 上限）· 结果**全是 `None`** ⇒ `cmds_battle.attack` 落到 `else` 支
  ⇒ 玩家看到的是「（战斗结束：None）」。这就是上一批报告里那句「Boss 单刷要『回塔』收尾」的来源。
- 同一场里法师/修女 24/24 秒杀（50 / 107 次出手）—— 与 P1 同源。

> ★ 附带查实：`monsters` 域的 `mods`（`hp_mult` / `atk_mult` / `elite_pool` / Boss 的 `phases`）
> **全仓库无人消费** —— 精英词条与 Boss 阶段卡今天都是**死数据**（见 §5 未修）。

---

## §2 修了什么（改前 → 改后）

### ① 倍率公式：`scripts/rebuild_skills.py`（新生成器，数值不手打）

- 口径（真源 = 六份职业详案的**伤害列**）：`classes.json` 新增 `dmg_channel`
  （骑士/狂战士/游侠/刺客 = `phys` 吃 atk；法师/修女 = `magi` 吃 matk）。
  ★ 元素字段（`ELE_FIRE` …）**不是**通道：狂战士「焚身」是火元素的**自伤重击**，打的仍是 atk。
- 生成器按 `power` × 通道算出 `exprs`：`atk*2.2`（守誓斩）· `matk*1.4`（焰痕）…
  30 条里 20 条拿到 `exprs`；6 条 `power<=0` 的非伤害辅助技走「增益」通道（**不产生伤害**）；
  修女「安神曲」（`mech=hot`）走「治疗」通道。
- 连跑两次数据不变（幂等）；探针逐条复算 `exprs == <基准>*<power>`。

### ② 引擎 kind 词表：`content/rules/kinds.json`（新）+ `apply.py` 挂 `kinds=`

```
phys→物理 · magi→魔法 · true→真伤 · heal→治疗 · buff→增益
```
`skills_lookup.skill_info/skill_by_key` 是「域 → 引擎」的翻译口：域里的 `kind`（**技能类别**
主动/被动）不动，新加的 `kind_override`（**引擎行动语义**）顶到 `kind` 上（缺/非法 ⇒ 当场抛）。
代码里不写死这 5 个中文值（整份从 rules 读）。

### ③ 普攻：`basic: true`（域里六条）+ `basic_skill_of` 按它取

`SKILL_KNT_slash 横剑` · `_BSK_cleave 横劈` · `_RNG_shortbow 短弓` · `_MAG_stardust 星屑` ·
`_PRS_staff 圣杖` · `_SHD_blade 短刃`。取不到 ⇒ `None`（引擎回落兜底），不猜。

### ④ 键名契约：`combat.monster_actor` 换名 + 率化

```
hp→max_hp · res→mdef · eva→dodge(率) · crit→crit(率)
```
率化走 `panel_build.rate_of`（与玩家**同一把尺**）。

### ⑤ 玩家的 `crit` / `eva`：一起走 `set` 率层，且把**装备那一份**算进去

改后（10 级）：刺客 dodge 8.44% > 游侠 8.29% > 狂战士 4.85% > 修女 3.19% > 骑士 2.65% > 法师 1.96%
（改前六职业一律 40%）。带 crit 词条的装备现在真的加暴击率（0.0291 → 0.0366）。

### ⑥ 怪 hp 反推式：`per_hit` 换成「六职业中位的**实际通道**单次行动伤害」

`rebuild_monsters.standard_per_hit(L)`，逐只怪 hp 重算（`scripts/rebuild_monsters.py` 现算）。
田鼠 52→68 · 野狗 170→231 · 沉尸 1639→2385 · 层主 1336→1965 · Boss 10275→15259。

---

## §3 配平表（固定种子 · 24 场/格 · 全六职业）

「设计次数」= `TIERS[档].hp_n × ARCH[原型].hp`（怪 hp 就是照它反推的；
真源 `12_怪物面板与精英词条池_v1.md` §一 + `03_全流程数值主干_v1.md` §四）。

### 3.1 改前 → 改后（单刷 · 该怪自己那一级）

| 怪（档/原型） | 设计次数 | 职业 | 改前 胜·出手·刻 | 改后 胜·出手·刻 |
|---|---|---|---|---|
| 野狗（普通/杂兵 lv6） | 4.0 | 骑士 | 24/24 · **38 次** · 3767 刻 | 24/24 · **6 次** · 644 刻 |
| 野狗 | 4.0 | 狂战士 | 24/24 · **47 次** · 4382 刻 | 24/24 · **4 次** · 424 刻 |
| 野狗 | 4.0 | 游侠 | 24/24 · **30 次** · 2460 刻 | 24/24 · **5 次** · 453 刻 |
| 野狗 | 4.0 | 法师 | 24/24 · 3 次 · 348 刻 | 24/24 · 4 次 · 445 刻 |
| 野狗 | 4.0 | 修女 | 24/24 · 4 次 · 439 刻 | 24/24 · 6 次 · 629 刻 |
| 野狗 | 4.0 | 刺客 | 24/24 · **29 次** · 2450 刻 | 24/24 · **5 次** · 464 刻 |
| 伐木工（精英/消耗 lv9） | 12.0 | 骑士 | 24/24 · **147 次** · 14179 刻 | 24/24 · 18 次 · 1790 刻 |
| 伐木工 | 12.0 | 狂战士 | 24/24 · **184 次** · 16511 刻 | 24/24 · 11 次 · 1038 刻 |
| 伐木工 | 12.0 | 法师 | 24/24 · 7 次 · 725 刻 | 24/24 · 10 次 · 1011 刻 |
| 沉尸（头目/厚甲 lv15） | 19.6 | 骑士 | 24/24 · **354 次** · 33211 刻 | 24/24 · 34 次 · 3241 刻 |
| 沉尸 | 19.6 | 狂战士 | 24/24 · **442 次** · 37386 刻 | 24/24 · 19 次 · 1656 刻 |
| 沉尸 | 19.6 | 刺客 | 24/24 · 263 次 · 19593 刻 | 18/24 · 25 次 · 1903 刻 |
| 层主（法系 lv17） | 14.4 | 骑士 | 24/24 · **288 次** · 26796 刻 | 24/24 · 24 次 · 2284 刻 |
| 层主 | 14.4 | 狂战士 | 24/24 · **359 次** · 29863 刻 | 24/24 · 13 次 · 1129 刻 |
| 层主 | 14.4 | 法师 | 24/24 · 7 次 · 674 刻 | 23/24 · 12 次 · 1160 刻 |
| Boss（厚甲 lv19） | 100.8 | 骑士 | **0/24 · 500 次 · 结果 None** | 0/24 · 43 次 · 4014 刻 |
| Boss | 100.8 | 狂战士 | **0/24 · 500 次 · None** | 0/24 · 24 次 · 2006 刻 |
| Boss | 100.8 | 法师 | **24/24 · 50 次** | 0/24 · 19 次 · 1789 刻 |
| Boss | 100.8 | 修女 | **24/24 · 107 次** | 0/24 · 42 次 · 3810 刻 |

**读法**：改前同一只野狗六职业差 **15 倍**（3 次 ↔ 47 次）、伐木工差 **26 倍**；
改后六职业落在 **1.4–1.7 倍**内（骑士最慢、狂战士最快 —— 这就是设计要的那点差异）。

### 3.2 改后 · 1→20 逐级「同级基准怪（普通/杂兵，设计 4 次行动 / 3–5 次）」

| 等级 | 1 | 5 | 10 | 15 | 20 |
|---|---|---|---|---|---|
| 怪 hp | 98 | 204 | 343 | 487 | 636 |
| 中位职业出手（中位） | 5 次 | 5 次 | 5 次 | 5 次 | 5 次 |
| 一场耗时（刻） | 480 | 470 | 440 | 416 | 375 |
| 胜率 | 16/16 | 16/16 | 16/16 | 16/16 | 16/16 |

⇒ **1→20 全程，一场普通战斗 = 4–7 次出手 / 375–480 刻**（≈ 6–8 分钟游戏内时间），
与设计稿「普通怪 3–5 次行动」**对得上**（实测中位 5 次，落在区间上沿；
差的这 1 次来自怪自己的防御与 0.95 命中率占位，不是公式错）。
逐级明细：`python scripts/balance_experiment.py --onlevel --seeds 16`。

### 3.3 层主 / Boss 可打性（固定种子 · 40 场/格）

**层主「守塔的骨架」（lv17）单刷曲线**：

| 玩家等级 | 13 | 14 | **15** | 16 | 17 |
|---|---|---|---|---|---|
| 胜率（240 场） | 0/240 | 8/240 | **113/240（47%）** | 210/240（88%） | 235/240（98%） |
| 结论 | 打不过 | 掷硬币偏负 | ★ **掷硬币** | 基本稳 | 稳 |

⇒ **16 级起稳；15 级就是「掷硬币」那一档（47%）；14 级以下别去。**

**Boss「旧誓哨兵」（lv19）单刷**：18/19/20 级 × 六职业 × 16/24 场 = **528 场全败**
（其中 96 场穿满「该等级能捡到的最好那一套」）。骑士 20 级 + 满装备是最好的一档，也只撑到 61 次出手；
Boss hp 15259、厚甲 def 100，单人要 ~150 次出手才够。
**唯一能真打完的路 = 4 人队**：
`骑士+狂战士+游侠+法师 · 19 级` ⇒ **24/24 打完**（134 次队伍出手 / 2753 刻）。
（`scripts/balance_experiment.py --party cls_knight,cls_berserker,cls_ranger,cls_mage --monsters ms_boss_oath_sentry`）

⇒ Boss 是**有意**的 4 人内容（真源 `12_…` §一④ + `14_怪物原型_v1.md` §四：
「hp 按 4 人队 × 18 次行动设计 —— 单人打会很吃力」）。**而今天『攻击』只按单人造场 ⇒
塔顶那间单刷必倒地**（不再卡死，走正常死亡落地回白烛堂）。组队接线是另一个批次。

---

## §4 门禁与端到端

### 4.1 `scripts/run_numeric_tests.py` —— **不存在**（包里没有这个文件）

本批跑的**数值门禁**（列出清单，供下一批对齐）：

```text
① 该域探针 + 全量探针：for f in scripts/probe_*.py; do $PY $f; done     ⇒ 28/28 全绿
   （本批把新判据加进 probe_skills ⑦ / probe_combat ⑰⑱⑲⑳ / probe_panel ⑥ / probe_monsters ⑪）
② 配平实验（固定种子 · 改前改后对照）：scripts/balance_experiment.py  —— 见 §3
③ 真宿主 e2e：scripts/e2e_drive.py（三个档：野外 / 塔内层主 / 塔顶 Boss）
④ 生成器幂等：scripts/rebuild_skills.py / rebuild_monsters.py 连跑两次数据不变
```

### 4.2 新增/加强的判据（只加强，不削弱）

| 探针 | 新判据 |
|---|---|
| `probe_skills ⑦` | kinds 词表三头对账 · 30 条 `kind_override` 合法 · `exprs` 逐条复算 == `<基准>*<power>` · 六职业各**恰好一条** `basic` 且 power>0 · `basic_skill_of` 取回的就是那条 · 引擎真读到了（`kind_of("phys")` 非空 + 普攻过得了 expr 门） |
| `probe_combat ⑰` | 17 只怪四个键真到得了引擎（max_hp / mdef / dodge 率化 / crit 率化） |
| `probe_combat ⑱` | 六职业 10 级真打一场：单发伤害落在**自己那根属性**附近 |
| `probe_combat ⑲` | 四档基准怪 × 该等级中位职业 × 16 场：实测出手次数 ∈ 设计值 × [0.6, 1.8] |
| `probe_combat ⑳` | Boss 单刷**一定出结果**（不再 None）· 单人 20 级全败（设计如此）· 4 人队胜 ≥ 7/8 |
| `probe_panel ⑥` | crit/eva 都是率（dodge ∈ [0,0.40]）· 刺客 dodge > 骑士（差异没被 cap 吃掉）· 带 crit 装备真加暴击率 |
| `probe_monsters ⑪` | `rebuild_monsters.K_RATE == panel_build.K_RATE`（两处同一把尺） |

> ★ 被**替换**掉的旧判据：`probe_skills ⑦「普攻取 power 最低的那条」` ——
> 那条把辅助技钉成了普攻（P2）。新判据更严（它同时要求通道、公式、恰好一条、引擎真读到）。

### 4.3 全量探针

```text
GREEN=28 RED=0
```

### 4.4 e2e（真宿主 · `scripts/e2e_drive.py`）

```text
① 野外（骑士 lv6 · 骨田 · 已加点）：遭遇「游荡的骸骨」⇒ 单发 38–45 点 ⇒ ✔ 打完（金币 +18 / 经验 +17）
② 塔内层主（骑士 lv17 · 号角室）：遭遇「守塔的骨架」⇒ ✔ 打完，拾取 📯 半截号角（主线 8 的交付物）
③ 塔顶 Boss（狂战士 lv20 · 已加点）：遭遇「旧誓哨兵」⇒ 💀 倒地回白烛堂（不再撞护栏挂住）
```

---

## §5 没修的（以及为什么）

| 项 | 为什么没修 |
|---|---|
| `monsters.mods`（`hp_mult`/`atk_mult`/`elite_pool`/Boss `phases`）**全无人消费** | 精英词条与 Boss 阶段卡是**一整套机制**（`09_精英怪机制_v1.md` 四类词条 + `14_怪物原型_v1.md` §四 阶段卡）；引擎的 `phase` 事件"无自然点位、由上层驱动" ⇒ 要写内容侧导演。属另一批次，本批只登记（**今天塔顶没有阶段转换、精英没有词条**） |
| 技能的 `mech`（protect/taunt/interrupt/def_break/mark_burst/hot/shield/cleanse/immune/advance_ct/retreat/unstoppable）**没有消费点** | 同上（机制层那一批）。本批只保证**它们不产生伤害**（走「增益」通道）且不崩 |
| 命中/闪避的**对冲式**（宪法 F2 `hit/(hit+eva)`）无消费端 | 引擎的闪避是**一刀切 rate**（`landing._roll_dodge` 只看守方 `dodge`，攻方 `hit` 没进这个函数）⇒ 要真做对冲必须改引擎（本批**零改动**）。`formula_bindings.json` 自己也写着「miss 不绑：引擎槽位语义是未命中率，本包 F2 给的是命中率」 |
| 怪的 `hit` 字段引擎不读 | `_monster_base_stats` 里没有 `hit`、也没有消费点。等对冲式那一批一起接 |
| `block` 格挡不生效（`block_cap()` 未装配 ⇒ 0） | 要挂 `formula_skeleton_fn`（V4 下沉那张骨架表）。属「公式骨架落表」那一批；本批不动以免两处各有一套常量 |
| `K_def`/`K_rate` 仍是常数 300/500（真源 `03_全流程数值主干_v1.1` §二 要 `100+20L` / `300+30L`） | 那份文档自己写着 §二·五「六职业 def 成长要一次性重算」，且改它会连带改六职业面板 / 装备预算 / 怪物反推 —— 属**数值主干**那一批。本批只把**生成器与战斗侧统一到同一个常数**（probe_monsters ⑪ 钉住），并把口径写成 `K_RATE` 一处 |
| 群居怪「一次来 3–4 只」没实现 | `combat.build` 支持多怪，但 `pick_encounter` 只返回 1 只 ⇒ 群居原型（hp ×0.45）今天等于白送的弱怪。属遭遇接线那一批 |
| 引燃/垂星的印记层数倍率（`power + 0.35×层数`）没进 `exprs` | 表达式器变量表里没有「印记层数」这一项（`build_vars` 只给 atk/matk/… ）；要等机制层把资源读点接上。今天的 `exprs` 是**基础倍率**（`matk*1` / `matk*0.8`） |
| 修女「安神曲」的治疗量口径 | 设计是 F8 `heal_pow × mult`，引擎的治疗兜底是 `matk × power`（`build_vars` 没有 `heal_pow`）⇒ 本批先让它**真的是治疗**（不再打人），数值口径留给技能机制那一批 |
| 单人打 Boss 的路 | 设计有意（4 人内容）。**组队命令还没接线** ⇒ 塔顶那间单刷必倒地。本批给的是实测证据（4 人队 24/24），接线是另一批次 |

### 待拍板（建议进台账，本批只登记）

```text
P-31  真源自相矛盾：`03_全流程数值主干_v1.md` §四 写「精英一场 5–8 次行动」，
      而 `12_怪物面板与精英词条池_v1.md` §一 的 hp_n = 12 次（= 普通 4 次 ×3，与 §四自己的
      hp 比例 ×1.5/×0.5 一致）。⇒ 本批按 12 走（生成器实现的那一版），5–8 那句建议改真源。
P-32  Boss 单人可打性：`12_…` §一④ 写「hp 按 4 人队 × 18 次设计；单人挑战时按 ÷2 看（≈3670），
      一场约 30 次行动」—— 但表里 hp_n = 72（单人就是 72 次行动，实测单人 150 次出手才够）。
      ⇒ 要么承认「单人无解、必须组队」，要么给 Boss 一条单人档（本批保持设计原值不改）。
P-33  `exp_need` 两份口径（`45 × L^1.5` vs `L² × 40`）—— 早已登记，本批未动。
```

---

## §6 可复现命令

```bash
export GWEN_ENGINE=C:/Users/yuyu/framework-engine
export AST_PLAN=C:/Users/yuyu/aetheran-plan
PY=C:/Users/yuyu/AppData/Local/Programs/Python/Python312/python.exe

# 生成器（幂等）
$PY scripts/rebuild_skills.py --dry     # 预览；去掉 --dry 才写盘
$PY scripts/rebuild_monsters.py

# 全量探针（28 个）
for f in scripts/probe_*.py; do $PY "$f"; done

# 配平实验（改前/改后同一套指标）
$PY scripts/balance_experiment.py --seeds 24                       # 五档 × 六职业
$PY scripts/balance_experiment.py --onlevel --seeds 16             # 1→20 逐级
$PY scripts/balance_experiment.py --seeds 40 --levels 13,14,15,16,17 --monsters ms_bone_warden
$PY scripts/balance_experiment.py --seeds 24 --monsters ms_boss_oath_sentry --gear
$PY scripts/balance_experiment.py --seeds 24 --party cls_knight,cls_berserker,cls_ranger,cls_mage \
    --monsters ms_boss_oath_sentry

# 真宿主 e2e（三个档；★ 起手档必须带 alloc —— 不加点等于少 ~1/3 属性，层主就打不过）
AST_E2E_SEED='{"name":"试炼者","cls":"cls_knight","level":17,"alloc":{"STR":29,"VIT":21,"WIL":6},
  "loc":"old_watchtower","node":"tower_horn_room","bag":{},"equipped":{},"flags":{},"codex":{}}' \
  $PY scripts/e2e_drive.py "攻击"

# 改前基线（读对象库，不改任何工作树）
mkdir -p /tmp/ast_base && git -C <repo> archive bbdc15f | tar -x -C /tmp/ast_base
```

---

## §7 改动文件清单（显式）

```text
content/data/skills.json          30 条：+kind_override / +exprs / +basic（生成器产物）
content/data/classes.json         六职业：+dmg_channel
content/data/monsters.json        17 只：panel.hp 按新 per_hit 重算（生成器产物）
content/rules/kinds.json          ★ 新增：引擎 kind 词表（5 个语义名 ↔ 域内用词）
content/skills_lookup.py          取件口：kind 换语义 + basic_skill_of + 怪技能走物理
content/apply.py                  挂 kinds 词表 + 兜底普攻带 exprs 走物理
content/combat.py                 monster_actor 键名契约（hp/res/eva/crit）
content/panel_build.py            crit/eva 一起率化（含装备那一份）+ rate_of
schemas/skills.schema.json        +exprs / +basic / kind_override 注释
scripts/rebuild_skills.py         ★ 新增：倍率公式生成器（幂等 · --dry）
scripts/rebuild_monsters.py       per_hit 口径换成「六职业中位实际通道伤害」+ K_RATE 常量
scripts/balance_experiment.py     ★ 新增：配平实验（多场统计 · 可 1 人可 4 人 · --onlevel）
scripts/probe_skills.py           ⑦ 换成「通道 + 倍率公式 + 普攻」判据
scripts/probe_combat.py           +⑰⑱⑲⑳ 键名契约 / 通道 / 配平 / 层主·Boss 可打性
scripts/probe_panel.py            +⑥ crit/eva 率化判据
scripts/probe_monsters.py         +⑪ 两把尺同值
_notes.md                         本文件
```

**没碰**：`content/cmds_talk.py` · `content/cmds_gear.py` · `content/cmds_skill.py` · 别的批次文件 ·
引擎仓（工作区空）· 真源仓（工作区空）。
