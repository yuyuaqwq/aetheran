# 阿斯特兰 · 数据包

《阿斯特兰》的内容侧数据包（跑在 `framework-engine` 上）。
**上游真源 = `aetheran-plan` 仓**（策划案：重构总纲 / 世界观圣经 / 数值宪法）。

| | |
|---|---|
| 远程 | `git@github.com:yuyuaqwq/aetheran.git`（`master` · 2026-09-28 起有远端） |
| 上游 | `aetheran-plan`（策划案，只读）· `framework-engine`（引擎，`games/aetheran` = 本包的挂载点）|
| 装法 | 数据包 `game.json` → `depends` 那 10 个扩展包 · **一个进程只允许一个数据包** |

## 现状（不是「最小骨架」了 —— 内容已铺满，见下）

| 件 | 内容 |
|---|---|
| `game.json` | `kind=game` · `depends` 10 个扩展包 · `domains` = commands/texts/tlogs |
| `content/apply.py` | 装配入口：挂 **15 个**引擎 hook（`cue_subs_fn` / `panel_layers_fn` / `formula_*` / `time_model_fn` / 各类 `*_gate_fn` …）|
| `content/*.py` | **55** 个模块 / **19 572** 行 —— 指令面、职业技能、战斗流程、任务与日历、副业、评级、图鉴… |
| `content/data/*.json` | **44** 份域表（职业 / 技能 / 怪物 / 地图 / 任务 / NPC / 对话 / 配方 / 图鉴 / 节日…）|
| `content/rules/` | 数值宪法声明（`formula_table` + `formula_bindings`）· 战斗文案（`battle_text`）· 效果规则 |
| `editor/domains.json` | 三个域的编辑器元数据（**刻意不写 `$builtin`**）|
| `scripts/probe_*.py` | **55** 支内容探针（每支都是一叠判据，含反证）|

## 怎么验（可重跑）

```bash
PY=/c/Users/yuyu/AppData/Local/Programs/Python/Python312/python.exe
GWEN_ENGINE=C:/Users/yuyu/framework-engine "$PY" scripts/probe_stack.py
```

期望输出：11 层装入（ext_combat → … → ext_achieve → aetheran）· `install()` 通过 ·
三域可读 · `binding('damage') = damage_full` · `calc_damage = 85`（走声明）对 `66`（摘掉绑定表）·
`time_model = 70.710678`。

## 三条落地纪律（踩过才写的）

1. **绑槽位的声明必须用消费端的变量名契约** —— `ext_combat.calc_damage` 的 `_v` 是写死的映射
   （`level/def/base/mult_skill/amp/mitigation/crit_mult/elem_mult/variance/pene_pct/pene_flat`）。
   照抄宪法 F7 的形参名（`atk/mult/def_mit/...`）会因**缺变量静默算 0**（伤害恒 1）。
2. **不要写 `editor/domains.json` 的 `$builtin: false`** —— 一写整栈丢掉引擎默认域
   （`commands/texts/tlogs`），而且不报错（静默陷阱）。
3. **`*.py` / `*.json` / `*.md` 全 LF**（`.gitattributes` 钉住 eol=lf）。

## 还没接的（下一批）

- 面板栈（E2）· 技能 7 维 schema（E5）· 解锁闸门（E4）—— 形状已就位，内容表还没铺满
- 战斗侧的技能倍率：`ext_combat` 目前传 `mult_skill = 1.0` 恒定（技能要接进来才吃倍率）
- 引擎状态容器第 2 批（`defending` / `shields` / 减伤词条并进 `effects`）—— **闸没开**，等本包内容停点
