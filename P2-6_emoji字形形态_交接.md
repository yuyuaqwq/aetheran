# P2-6 · emoji 字形形态不一致（VS16）—— 已落地

> 车道：文案修复车道 · P2（排版规整度 + 补图标）· 2026-09-28
> ★ 本轮**曾让位、后窗口开了下来**：开工时 `content/data/texts.json` 与
> `scripts/rebuild_syscopy.py` 正被另一车道（owner `aep0`）写入（差异量 `2/2`、`19/0` 非我手笔）
> → 先落此取证文件、**零改动**；等它提交（`ce74528`）后进来实改，提交里只带自己的文件。

## 一、判据（照鱼鱼口径，不是自造）

```
「emoji 是可以的……只要很规整观感好问题就不大」
「我甚至觉得适当的 emoji 会更好」
```

⇒ emoji **多与少都不是缺陷**；要判的是**同一语义 / 同一界面内的观感一致性**。
本条属「**同一个 emoji 长得不一样**」—— 比「少图标」严重：
同一个 🛡 在一屏里一处彩色、一处单色描边字形，观感直接破功。

## 二、核实到的确切数字（现跑，非记忆）

`content/data/texts.json` 全部 931 条槽位 · 逐字符扫（Python 3.12）：

```
emoji 字符总数 122  · 带 VS16（U+FE0F）24  · 裸形态 98
```

按 codepoint 归组后，**混用两种形态**的只有 2 个 —— 本批**两个都收了**（见 §四①）：

| codepoint | 出现次数 | 带 VS16 | 裸形态 | 本批处置 |
|---|---|---|---|---|
| U+1F6E1 🛡 | 15 | 14 | 1 | → 补成 VS16 |
| U+2694 ⚔ | 4 | 2 | 2 | → 补成 VS16（**改判据，不按众数**，见 §四①） |

其余 31 个 codepoint 全部「一刀切」要么全带 VS16、要么全裸 —— 仓内自洽，不动。

## 三、实改 3 条（每条只加一个 U+FE0F，取件点与判定逻辑一个字没动）

```
COMBAT_CORE_DEFEND    battle.core.defend（引擎 ext_combat/battle/battle.py:655）
SYS_STATUS_IN_FIGHT   content/cmds_ast.py:1356（『状态』面板末行）
COMBAT_TURN_STATE     content/instance.py::turn_panel（打击屏四段式① 现状）
```

★ **都验过「同屏」**：`scripts/_baseline_instance_solo.json` 里 `防御` 那一档的末行就是
`COMBAT_CORE_DEFEND`，同屏前几行是 `COMBAT_TURN_STATE` / `🌀` / `💥` —— 玩家真会看到。
`probe_instance.py --dump` 新旧两份**逐行 diff**：5 条指令 · 5 个 row 一一对应，
**全副本只差 5 行**（每行就多个 `U+FE0F`），删/改 0 行 · `save` 那几格**逐字相同**。

## 四、★ 本批最重要的一条：**我自己写的判据被自己的改动推翻过一次**

```text
① 我第一版的判据是「按众数收敛」——
   对 🛡 成立（14:1）；对 ⚔ 是 2:2 **打平**，
   我据此写了「打平就没有依据 ⇒ 不动」。
   ★ 然后我把判据写成常驻门禁跑了一遍，**它当场把 ⚔ 判红**：
     同一条判据在「一致性」这个口径下根本不看众数 —— 2:2 打平**本身就是不一致**。
   ⇒ 改判据（只加强、不削弱），依据换成**同类已统一的先例**：
     `U+2694` 与 `U+26A0` 同属「默认呈现是文字、需 VS16 才是彩色」那一类，
     而 `U+26A0` 本包 **5/5 全带 VS16** ⇒ 按同类的既有口径，`U+2694` 也全带。
   ★ 教训写在这里：**「众数」是给「选一个值」用的；一致性判据是「不许有两个值」。**
     自己定的判据要先真跑一遍再登记文档 —— 不跑就写进交接件，下一轮会当成定论。
```

## 五、刻意**不**做的（带理由，不是漏）

```text
① emoji 覆盖率类的东西：**一个数都不当指标**。鱼鱼原话是「适当的 emoji 会更好」，
   把「emoji 覆盖率」写成门禁目标值 = 把优点当 KPI，会让别的线为凑数乱加图标。
   ⇒ 判据里明确写了这一条，防止下一轮有人补「emoji 覆盖率门禁」。

② 0% 覆盖的那批界面（PARTY / STAT / GEAR / SKILL / ALLOC / ATTR / SHOP / SMITH）
   —— **本轮没动，也不建议为「补图标」而动**：它们多是「一行只有一个数」的纯数据行，
   在屏上不构成多行并列，加图标是花不是锚点。补图标只在两种位置划算：
   同屏并列行的**子抬头**、界面的**抬头行**。这轮两轮（P2-3 / P2-5）已经各做过一次，
   都在 `rebuild_syscopy.py::DOC_PENDING` 里留了账。

③ `COMBAT_FLEE_TODO` 的 🚧（审计点名的「同语义两 emoji」）——
   **已退役**：那句桩句的唯一读端在 B4-18 删掉了（`probe_copy.py:125` 写着来龙去脉），
   现在是给 `probe_copy ⑤`「没被引用」当靶子用的。**不是「该改没改」。**
```

## 六、落这条时配的判据（已落，只加强不削弱）

```text
位置  scripts/probe_instance.py 末尾（P2-6 那两条）
判据  同一 codepoint 不许「带 U+FE0F」与「裸形态」同时出现在文案域里
反证  拿一个已归一的 codepoint 强塞个裸形态 ⇒ 上一条当场红（否则判据可能是死的）
⚠️ 绝不许钉「emoji 覆盖率 / 每个界面至少 N 个图标」—— 见 §五①
```

## 七、本轮状态

```
改动文件  content/data/texts.json（3/3）· scripts/rebuild_syscopy.py（36/0 · 三条 DOC_PENDING）
          scripts/probe_instance.py（52/0 · 门禁+反证+基线改动登记）· scripts/_baseline_instance_solo.json（1/1）
未带进   scripts/probe_texts.py（P0-3 的在途改动 68/0，**不是我的**，显式清单 add 挡掉了）
真源    aetheran-plan 一字未改（改值走 DOC_PENDING 两态互锁）
门禁    probe_texts / probe_copy / probe_guard_text / probe_instance 全绿
生成器  rebuild_syscopy.py --dry：待跟账 27 → 30，数据不变（幂等）
```
