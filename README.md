# 阿斯特兰 · 数据包

《阿斯特兰》的内容侧数据包（跑在 `framework-engine` 上）。
**上游真源 = `aetheran-plan` 仓**（策划案：重构总纲 / 世界观圣经 / 数值宪法）。

## 现状（第二刀：最小可跑骨架）

| 件 | 内容 |
|---|---|
| `game.json` | `kind=game` · `depends` 10 个扩展包 · `domains` = commands/texts/tlogs |
| `content/apply.py` | 装配入口：挂 `formula_table_fn` / `formula_bindings_fn` / `time_model_fn` |
| `content/rules/formula_table.json` | 数值宪法 F1–F10 → 12 条声明（含 `damage_full` 全链） |
| `content/rules/formula_bindings.json` | 语义槽位 → 声明（`damage` → `damage_full`） |
| `content/data/*.json` | 三份默认域（最小空表，待填） |
| `editor/domains.json` | 三个域的编辑器元数据（**刻意不写 `$builtin`**） |

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

- 21 条引擎 hook 目前只挂了 3 条：面板栈 `panel_layers_fn`、`panel_fn`、`skill_lookup`、
  `segment_plan_fn`、`basic_skill_fn`… 共 18 条待接
- 面板栈（E2）· 技能 7 维 schema（E5）· 解锁闸门（E4）
- 战斗侧的技能倍率：`ext_combat` 目前传 `mult_skill = 1.0` 恒定（技能要接进来才吃倍率）
- 内容层：职业 / 技能 / 装备 / 怪物 / 地图 / 任务 六条线（等 `aetheran-plan` 的 03–07 出稿）
