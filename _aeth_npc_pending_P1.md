# 待落真源 · P1（NPC 对话）· 2026-09-29 夜班

> 车道 = 文案修复车道 P1（锁 `_lane_aep1`）。**真源 `aetheran-plan` 只读**，故本件只交可执行清单。
> 主线落法：改真源那张表的**一格** → 跑 `python scripts/rebuild_titles.py` → 跑 `scripts/probe_generators.py`。
> （**不要手编 `content/data/titles.json`** —— 它是生成物。）

---

## R-P1-1（唯一一条，阻塞 `probe_generators ②③`）★ 真缺陷，不是过期的审计数字

### 症状（现取，Python 3.12 · `GWEN_ENGINE=C:/Users/yuyu/framework-engine`）

```
$ python scripts/rebuild_titles.py --dry
title_wall_listener 的条件对不上：heard@dlg_hagen 写的是 9，而那棵树有 14 条台词（现算）   rc=1
$ python scripts/probe_generators.py    →  ✗ ②③ rebuild_titles.py  （通过 22 · 失败 1）
```

### 根因：`titles.json` 的那个数**从 P1-9 起就再没跟过对话树**

| 提交 | `dlg_hagen` 台词条数 | 称号条件里的数 |
|---|---|---|
| `titles.json` 最后一次生成（`3c994b8`） | 9 | **9** ✓ |
| `a359b9b` P1-9 轮换补第二批 | **11** | 9 ✗ |
| `9953d7d` P1-11 / `b39e580` P1-12 | **13** | 9 ✗ |
| `ad88b00` P1-19/20（当前 HEAD 侧） | **14** | 9 ✗ |

生成器 `scripts/rebuild_titles.py:250-253` 对 `heard` 一族**现算**「那棵树的全部台词条数」
（不许手打）⇒ 对不上就 fail-closed 抛错。**这个 fail-closed 是对的，不许绕。**

### ★★ 比"数字漂了"更值得修的：**那一格的语义也过期了**

真源 `00_总纲/16_称号域口径_v1.md:53` 写的是「听完哈根的**全部**对话」，
而 21 号文档 `:32` 同一句也是「**全部**」。
`heard@dlg_hagen>=N` 的 N 应当 = 树里**全部**台词条数。
现状 `>=9` 配 14 句的树 ⇒ **玩家听满 9 句就拿到「北墙根的听众」，
`main#0/1/2`（主 04/08/10 交完才出）与 `hidden#0`（带着哨兵护手）那 4 句就白送了**
—— 称号的成就感被提前兑现，而后 4 句恰恰是哈根这个角色最重的四句。

⇒ **修法不是把 9 改成 14 就算完**（那样数字对了、但那 4 句要到主 04 之后才拿得到，
玩家前期拿不到称号、后期又在树里只剩 3 句可轮 ⇒ 得先看下面这一条）。

### 落法（两步，都要主线点头，属真源口径）

1. **N 改成现算值 14**（`rebuild_titles.py` 会自己算，源表那格要跟它对上）。
2. ★ **同表 `:124-125` 的「等前置」第 10 条要一起改口**：
   现在写「说话那一下已接线，但对话层的取句顺序把 meet 那几层挡在 hidden 后面（P-12），
   哈根今天只会重复同一句」—— **这一条已经过期了**：P-12 那批改了层序
   （`meet → daily → main → hidden`，见 `content/cmds_talk.py` 模块抬头 ①），
   探针 `probe_dialogues ⑬-a` 现取**后期档下哈根能轮 11 句 / 全树 14 句里最差 8 句**。
   ⇒ 那句「只会重复同一句」现在读起来是假的，会误导下一位。
   ★ 顺带核实一件更要紧的：`>=14` 是否**可达**（`hidden#0` 要 `holding:i_set_sentry_gauntlet`、
   `main#*` 要主线交完）—— 真源 `16` 自己在「等前置」里承认「等前置 = 数据/机制缺口，
   不是判据放宽」；若某句在第一阶段拿不到，N 就该按**第一阶段可达的那部分**取，
   并把理由写进 `why`（生成器要求 `why` 里写清依据，见 `rebuild_titles.py` 的 `PRODUCER` 那套）。

### 复现 / 验收命令

```bash
PY="C:/Users/yuyu/AppData/Local/Programs/Python/Python312/python.exe"
cd C:/Users/yuyu/aetheran-package
export GWEN_ENGINE=C:/Users/yuyu/framework-engine
$PY scripts/rebuild_titles.py --dry     # 期望 rc=0（现在 rc=1）
$PY scripts/probe_generators.py          # 期望 通过 23 · 失败 0（现在 22/1）
```

---

## P1 车道本轮**已核实无缺口**的三处（免得下一位重查）

任务书给的三个审计数字**全部已过期**，逐条现取（`content/data/dialogues.json`，178 句）：

| 项 | 任务书 | 现取 | 依据 |
|---|---|---|---|
| NPC 对话条数 | 63（规格 165） | **178 句**（14 位 NPC 166 + 5 棵物件树 15；规格目标 ~165 **已达标**） | 按 `nodes.*.texts` 逐层求和 |
| 四层位齐 | 0/14 | **14/14 全齐** | 位齐率 100% |
| 「只有 1 句」的层 | 26 | **0** | 单句 node 清单为空 |

已由仓里的历史提交做完：`c2f2e04`（单句层 5→0）· `9953d7d`（最后一个纯兜底层归零）
· `a359b9b`/`7225b32`/`ad88b00`（轮换补句）· `5ee1c47`/`746e1e3`（同层按「易变优先」重排）。

门禁侧也已落位，**本轮未改一行判据**（门禁只加强）：
`probe_dialogues` ⑩-a 位齐率 · ⑩-b 纯兜底层 · ⑩-d/⑩-e 死句 · ⑪-a 可观测轮换（48 趟真敲）+ ⑪-b 反证 ·
⑫-a 单句层（上限已 0）+ ⑫-b 反证 · ⑬-a 后期档轮换（`_LATE_MIN=3`）+ ⑬-b 反证。

**本轮新做的两项实测**（都是「域里看着对、玩家未必看得到」那一面）：

```text
① 死句扫描（need 条件在**真判定**下永不成立 ⇒ 写进域里却永远出不来）：
   178 句全跑真判定（flags 走 content/prog.truth 的**真实进度**口径、道具/时辰/天气/事件全枚举）
   ⇒ **死句 0 条**。★ 第一次跑出 29 条是**夹具错**（只写了 slug 本身，而 flag_ok 对表内 slug
     走真实进度 quests_done/quests_active）—— 夹具修对后归零。判据记在这里：
     **探针夹具写对话旗标必须写 `flags.quests_done` / `quests_active`，不是写 slug。**
② 后期玩家可观测轮换（照抄 `probe_dialogues ⑬-a` 的夹具，主线交完 + 背包满）：
   合计 **129 句 / 最差 8 句**（判据底线 3）⇒ **绿，余量充足**。
   ★ 反面：若用「背包里有全部 128 件 + 身上有伤」的极端档，会掉到合计 76 / 最差 2 ——
     那不是缺陷，是**夹具比玩家狠**（玩家身上不会同时带全套 + 带着伤）。
     记这一条是因为它能反过来骗人：**判据夹具的宽严决定了数字的含义**。
```

### 与 P1 文件面无关、但会盖住全量的红（别重复归因）

`F1_eff_def` 的穿透变量（`pene_pct`/`pene_flat`）在**引擎** `saintess_engine/formula/__init__.py:236`
的 `_compile` 还没进那张 13 名变量表 ⇒ `install_engine()` import 期抛 `FormulaDeclError`
⇒ **全包 57 支探针同一条红**（含本车道要跑的 `probe_dialogues`/`probe_texts`/`probe_copy`）。
本轮实测：引擎仓 `git status` 脏（`extends/ext_combat/battle/battle.py` M ·
`games/orlandia` m）⇒ **别车道在飞**。已在 `e581c35` 登记，本车道不碰（不动引擎 / 不改判据 / 不改夹具）。
⇒ **下一位的开工第一步**：先跑 `probe_texts`；PASS 了再回 P1 面，还是那条 `FormulaDeclError` ⇒
按上面 ①-③ 判「别车道在飞」，去做**不启动引擎**的活。
