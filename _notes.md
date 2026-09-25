# P-23 帮助只列有处理器的指令（+「读」接上）· 落批笔记

分支 `p23-help-filter`（工作树 `C:/Users/yuyu/ast-wt/p23-help`，从 `master d325086` 切）
真源：`aetheran-plan` 一个字没动（真源只读）；本批的两处「该进真源表」的东西记在下面。

---

## 一、新增 texts 槽位：**1 条**

> 「声明了、包内还没实现」的指令原先由**引擎**回显（`saintess_engine/host/runtime.py::declared_echo`
> 第 373 行：「（该声明未提供处理器：包内 content/commands.py 里没有它的 handler）」）——
> 把**内部 key** 与**文件路径**一起漏给玩家了。引擎零改动 ⇒ 包侧接住这些声明，只说槽位文案。

按 `| 键 | 文案 | 参数 | 类 | 出处 |`（照 `00_总纲/17_文案收口口径_v1.md §二` 的格式）：

| 键 | 文案 | 参数 | 类 | 出处 |
|---|---|---|---|---|
| `SYS_CMD_SOON` | 🚧「{name}」还没接上<br>💡 敲「帮助」看现在能用什么 | name | 系统 | 帮助 / 声明回显 · 声明了但包内还没实现（P-23：原先把内部 key 与文件路径漏给玩家） |

★ 已按**生成器口径**直接落进 `content/data/texts.json`：只在**末尾追加**一条
（`scripts/rebuild_syscopy.py` 就是「保持原表插入序、新的追加到尾部」⇒ 主线把上面这行加进
真源表后重跑生成器，**应当零 diff**）。`{name}` 喂的是该声明的 `usage`（如 `技能 <参数>` / `药铺`），
**不是内部 key**。

---

## 二、`commands.json`：新增 1 条声明（`read`）

`content/cmds_ast.py::read_thing` 早在代码里（`probe_copy` 一直在驱动它），但 `commands.json`
**没声明** ⇒ 玩家只能靠「触摸」读物。本批给它补上声明（绑到**现有实现体**，没重写）：

```json
"read": {"patterns": ["^读(?:\\s*(.+))?$", "^阅读(?:\\s*(.+))?$"],
         "category": "移动与世界", "desc": "读一读这儿能读的东西", "usage": "读",
         "visible": true, "order": 8, "guard_desc": "有可读物时",
         "bind": {"handler": "content.cmds_ast:read_thing", "call": "run", "args": ["uid", "player"]}}
```

* `order: 8` 与 `聆听` 同值 —— 表里本来就有 6 组重复 order（`be_race`/`relic_study` 都是这么进来的），
  且**没有任何代码读 commands.json 的 order**（只有 races / quests 有 order 语义）。
* 撞车：`probe_cmds ①` 190 个样例全命中自己（无撞车）；`②` 181 条文档触发词不变。
* ★ **真源待补一行**：`06_第一阶段垂直切片/04_指令总表.md §一` 现在只有 11 条（观察/触摸/聆听…），
  **没有「读」** —— 请主线把「读（别名 阅读，可选点名）」补进那张表（本批真源只读，没动）。

---

## 三、本批改了什么（包内，4 个文件）

| 文件 | 改法 |
|---|---|
| `content/cmds_ast.py` | ① `help_cmd`：循环里加一行 `if not v.get("bind"): continue`（**只列有处理器的**）；② 新增 `declared_soon(env)`：没实现的声明回 `SYS_CMD_SOON`（只传槽位）；③ `read_thing`：`读 <名字>` 按名字挑（点错名照 `SYS_READ_NONE` 说，**不随便塞一样**） |
| `content/commands.py` | 新增 `load_declared_soon()` / `UNBOUND_KEYS`：把**没有 bind** 的声明也登记一个兜底处理器（`env → list[str]`），引擎那句回显就再也落不到玩家眼里；声明本身**一条不动**（不动 `visible`、不删、不编实现） |
| `content/data/texts.json` | 追加 `SYS_CMD_SOON`（见 §一） |
| `content/data/commands.json` | 新增 `read` 声明（见 §二） |

★ 反例（**本批没走**）：把 43 条的 `visible` 改成 `false` —— 那会同时把
「声明了没实现」这件事藏起来，并且撞 `probe_cmds ②`（文档点名的触发词必须 first_hit 到期望那条）。

---

## 四、门禁（本工作树实跑 · Python 3.12 · GWEN_ENGINE=C:/Users/yuyu/framework-engine）

| 门禁 | 数字 |
|---|---|
| `probe_cmds` | ① 95 条可见声明 / 190 样例全命中自己；② 181 条文档触发词全中；**⑤ 帮助正好列 52 条（= 可见 + 有 bind），43 条没实现的一条都不在表里、10 行里 0 个内部 key**；**⑥ 43 条真敲逐字回 `SYS_CMD_SOON`、0 处内部 key / 路径 /「未提供处理器」**；**⑦ 「读」6 条真敲抬头+正文都对（含骨田同一处两个可读物按名字挑）+ 点错名回「这里没有能读的东西。」** |
| `probe_copy` | 已收口文件 0 条中文；92 个实现体全出话；`T("…")` 引用键 186 个（+1）全在 texts；口径表 107 条逐字一致且都被引用；呈现口不漏机器键（329 个域键） |
| `probe_texts` | 322 条槽位（+1）；键名规则 · 占位对账全绿 |
| 全量探针 | **25 绿 / 0 红** |
| e2e 真宿主 | `帮助/触摸/读 墙上的划痕` 跑通；另跑两组：默认起点「读」→【镇口的石头】+正文；旧哨塔水房「读 墙上的划痕」→【墙上的划痕】+正文 |

装配行：**指令声明 97 · 处理器 97**（批前 96 / 51）。处理器数追平声明数**不是**「都实现了」——
43 条走的是兜底句，判据钉在 `probe_cmds ⑤⑥`（「帮助」列的就是有 bind 的那些 + 没实现的回人话）。
