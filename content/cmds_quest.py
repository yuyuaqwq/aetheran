# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 第三组：公会与委托（B2-1）

契约同 cmds_ast：async generator，签名 (env, sink, uid, player)，参数从 env.text 解析。
落档：改了玩家档就必须 _save(env)（引擎不再每条消息整档回写）。

★ P-25：支线的「真前置」—— 交活时校验玩家是不是真做了
------------------------------------------------------
改前交活只判等级（主线）/ 一个没人写的 flag（支线）⇒ 「带他看塔」这类支线，
玩家做没做、做到哪一步，档上没账、交活也不看 —— 支线是假的。

两个形状（都在本文件里定死，别处照抄）：

① quests 域的 `require` —— **只有需要前置的条目才写**（没写的老条目行为逐字节不变）：
     {"kind": "visit", "map": <图 id>, "node": <节点 id>}    去过这一站（node 省了 = 这张图哪儿都算）
     {"kind": "kill",  "monster": <怪 id>, "n": <只数>}      图鉴里那只怪已经打掉过 n 只
     {"kind": "kill",  "role": <role_key>, "n": <只数>}      ★ B3-11：那一**档**的怪合计打掉过 n 只
                                                            （role_key ∈ monsters 的 normal/elite/
                                                             chief …；认不出的档 = 计数 0 = 没满足）
     {"kind": "item",  "item": <物品 id>, "n": <份数>}       背包里有 n 份
     ★ B3-13 又加了四种（账都在现有档上，见本文件抬头 B3-13 一节）：
     {"kind": "enhance", "n": <级>} · {"kind": "cook", "n": <次>}（可带 `quality` 品阶）·
     {"kind": "talk", "npc": <npc id>, "n": <次>} · {"kind": "ask", "n": <人>}；
     而 `{"kind": "kill", "role": …, "daily": true}` = 悬赏那条**当天点名**的那一只。
   写一条 dict，或写一串 dict（**全部**满足才算做了）；认不出的 kind 一律算没满足（fail-closed，
   不静默放行）。中文的 `objective` **不解析** —— 条件的真源是 `require`。
   ★ `role` 与 `monster` 二选一（都写只看 `monster`）；档名只在**呈现**那一行从 monsters 域透传，
     代码不认中文档名。

② 玩家档 `flags.quests`（格子原来就有，不新建容器）：
     flags.quests = {<quest_id>: {"step": <已满足的条件条数>, "done": true, "at": <游戏日>}}
   交活成功那一下才写（此刻 step 恒等于条件总条数；没写 require 的老条目 = 0 —— 它只有「交没交」两态）。
   形状先摆好：将来想让打怪 / 采集那两处「顺手记一步」，往同一个格子累加 step 就行。

★ 三种条件的数据在档上都真存在（本模块**只回头查**，一个都不写）：
   去过哪儿 → `foot.nodes`（第一回到）/ `foot.visits`（去过几回）—— codex.note_visit / note_step
              挂在移动那几处（cmds_ast，别改）
   打过什么 → `books.monster[<怪>].kills` —— codex.note_kill 挂在打怪那一下（cmds_battle，别改）
   手上有啥 → `bag[<物品>]` —— loot.add_to_bag（采集 / 掉落 / 烹饪 / 买，别改）

★ B3-3 生活职业任务（解 P-14 的甲案 · 设计真源 `28_生活职业任务_设计_v1.md`）
------------------------------------------------------------------------
不建新域：quests 域多一个**分类维度** `trade`（"采集" | "垂钓" | "烹饪" | "强化"），
8 条与现有支线重合的**就地合并**（只加字段、不复制文案），另 8 条新的补进同一个域
（`kind: 生活` · `chain: trade`）—— 玩家侧两个入口（『悬赏』找玛莎 / 『副业』找手艺人）吃同一份数据。

  · 四个副业的**名字与顺序**是数据（`quests._meta.trades`，生成器从 28 §三 + 21 §二 解析）
    —— 本模块只读它、只传槽位，不认任何中文副业名（加第五个副业 = 改数据）
  · `_quests()` 是**取条目**的唯一一口：`_meta` 那类私有键不是条目（与 recipes / codex 同口径）
  · 生活任务**一律写 `require`**（上面那三型）—— 不然会落到 `flags.side_*` 那条死路径上
    （那个键仓库里没有任何地方写）。今天现有的 12 条老支线仍在死路径上（P-25 §② 未收口，见报告）
  · 落法（重跑）：`python scripts/rebuild_prof_quests.py`（从真源解析 · 数值不手打）
  · 判据：`scripts/probe_quests.py` ⑪（trade 四值 · 16 条与 21 §二 逐条对账 · 条件真能验 · 副业指令真跑）

★ B3-6c 主线三段行文归位 texts（解 P-17 甲案）
------------------------------------------------
主线 12 条的「接 / 进行中 / 交」三段行文原先内联在 quests 域的 `story` / `progress_text` /
`deliver_text`（写着「待写」「（进行中：…）」），而 texts 域的 `QUEST_MAIN%02d_{STORY,PROGRESS,
DELIVER}` 36 条**谁也读不到** —— 两处真源。裁定甲案：**真源归 texts**。

  · 域里那三个字段**主线已裁掉**（`content/data/quests.json`）
  · 消费端只按 `chain` + `order` 映射取槽位（`_slot_of` / `_beat` 两个口）——
    **不拿名字拼键名**，一个中文都不内联
  · `story` 的落点 = `接 <编号>` 那一下（槽位出处自己写着「接时行文」）；
    `progress_text` = 交活没做完那一行；`deliver_text` = 交掉之后那一行
  · 判据：`scripts/probe_quests.py` ⑲（12 条真取到 · 与 24 号文档逐条对账 · 36 条非占位）

★ B3-8 支线 18 / 生活 8 / 悬赏 3 三段行文归位（同一套办法 · 一次收完）
------------------------------------------------------------------
B3-6c 只做了主线 12 条；剩下 29 条（支线 18 · 生活 8 · 悬赏 3）仍读域内字段 —— `story` 是
「（待写）」、`progress_text` 是备注腔「（进行中：…）」，而它们的 `deliver_text` 今天**是玩家
看得到的**（交活那一行）。本批照同一套映射把这 29 条也归位：

  · 槽位键 = 链模板 + `order`（`QUEST_SIDE%02d` 13–30 · `QUEST_TRADE%02d` 31–38 ·
    `QUEST_BOUNTY%02d` 101–103）—— 与主线那 36 条同一个形状（`_SLOT_TPL` 四个字面量）
  · 域里那三个字段**29 条也裁掉**（现在是「四条链一条不剩」；探针 ㉓ 钉着「域里 0 处」）
  · 文案依据只有三份真源：支线 = `24 §二`（步骤 / 奖励）· 生活 = `28 §四` + `21 §二` ·
    悬赏 = `24 §二` 的悬赏板块 + `05 §一`（报酬区间 / 经验 1/8）—— 文档只给一句就只写那一拍
  · 悬赏那三条的「交时行文」= 归位前域里的 `deliver_text` **逐字保留**（玩家看到的字一个没动）
  · 判据：`scripts/probe_quests.py` ㉓㉔㉕㉖（29 条真取到槽位 · 与三份文档逐条对账 ·
    87 条非占位 · 三类各真跑一遍接/交）

★ B3-11 悬赏三档的数值与交付条件 · 支线「还石头」的交付条件
--------------------------------------------------------
解两个活口：① 悬赏 `reward_exp` 是手打的旧数（125 / 640 / 3920），与 `05 §一`「经验 = 同级
升级需求的 1/8」对不上；② `_obj_ok` 对没写 `require` 的条目去看 `flags.side_<名字>`，而那个键
**仓库里没有任何地方写** ⇒ 今天 12 条支线 + 3 条悬赏都交不掉（P-25 §②）。

  · 数值与条件**一律从真源现算**：`python scripts/rebuild_quest_gates.py`（幂等 · `--dry` 先看）
      - 经验 = `exp_need(该档 min_level) × N/D`（N/D 从 05 §一 与 24 §二 两处解析，必须一致）
      - 悬赏条件 = 「那一档的怪任意一只打掉过」（`kill` + `role`）—— 24 §二 写「打掉**指定的**
        普通怪」，「指定的」= 悬赏板每天轮换挑一只，而**轮换那一步数据面上还没有** ⇒ 先落「档内任意
        一只」（比死路径强、比「指定的那一只」宽；轮换落地时把 `role` 换成 `monster` 即可）
      - 支线「还石头」条件 = `15_彩蛋域口径_v1 §二` 那句「`q_side_13「还石头」的交待就是彩蛋 2`」
        的条件（`hold` → `item` · `where` → `visit`；`read` 那一步是彩蛋自己的，任务不取）
  · 判据：`scripts/probe_quests.py` ㉗（悬赏三档经验/钱逐条对账）· ㉘（18 条支线的交付真跑矩阵：
    交得掉的**真交一次**，交不掉的钉住名单 + 逐条原因）

★ B3-13 支线的另外 6 条条件 · 悬赏「指定的」落地（每日轮换）
-----------------------------------------------------------
P-25 §② 剩下的 11 条支线里，**能按真源文档补上正当条件的 6 条**这一批补齐；悬赏那条
「打掉**指定的**普通 / 精英 / 头目怪」也从 b41 的宽口径（该档任意一只打掉过）收成
**当日点名的那一只**（轮换 = 游戏日 + 档位，可复现）。

条件形状（真源 = `06_第一阶段垂直切片/24_任务线_v1.md §二` 的「步骤」列 ·
`21_长期目标层_v1.md §二` 同条；**每条的依据**写在生成器 `scripts/rebuild_quest_gates.py`
的规则表里，数（+3 / 三次 / 三道菜 / 三个人）都从那份文档现取）：

  {"kind": "enhance", "n": <级>}                  档上**有一件**装备的强化等级 ≥ n
                                                  （账 = `p.enhance[<装备>]` 的 `lv`，写入口 cmds_recipe.enhance）
  {"kind": "cook", "n": <次>}                     下过锅 ≥ n 次（账 = `flags.cooked[<配方>]`，写入口 cmds_recipe.cook）
  {"kind": "cook", "quality": <品阶>, "n": <次>}  只数**用了那一品阶食材**的配方（品阶现取自 items 域的
                                                  `quality` —— 数据比数据，代码不认中文；「用稀有食材做一次」那条）
  {"kind": "talk", "npc": <npc id>, "n": <次>}    跟这个人搭过 ≥ n 次话（账 = `flags.talked[<对话树>]`，
                                                  写入口 cmds_talk；npc → 对话树走 `npcs.dialogue`）
  {"kind": "ask", "n": <人>}                      搭过话的**人** ≥ n 个（同一本账；只数域里真有对话树的那些键）
  {"kind": "kill", "role": <role_key>, "n": <只>, "daily": true}
                                                  ★ 今天点名的那一只（见 `_daily_pick`）：该档的怪按 id 排序后取
                                                  第 `(游戏日-1) % 档内只数 + 1` 只 —— 同一日同档必是同结果，
                                                  跨日必换（档内只数 > 1）；游戏日读档上那一格（`codex.today`）

  ★ fail-closed：认不出的 kind / 认不出的档（取不到怪）/ 取不到对话树的 npc ⇒ 一律**没满足**。
  ★ 老条目（没写 `require`）的行为逐字节不变；`flags.side_<名字>` 那条死路径仍只服务它们
    —— 今天还剩 5 条（灯油 / 信 / 隐藏线 flag / 「他的口味」没点明哪一道 / 目的地没写），
    逐条理由与「要补的什么」在工作树 `_notes.md`。

★ B4-2 主线 12 条**也走 `require`**（解 P-25 §①：不许「接了就交」）
---------------------------------------------------------------
改前 `_obj_ok` 对主线只看 `level >= min_level` ⇒ 1 级接 1 级主线，一句『交 1』直接过，
目标那几步（观察 → 看见石头上的字 → 试着读 → 问玛莎）一步都不用做。

  · 条件真源 = `06_第一阶段垂直切片/24_任务线_v1.md §一` 每块的「步骤」行（**含跨行的续行**）
  · 落法：`python scripts/rebuild_quest_gates.py`（幂等 · `--dry` 先看）—— 每条条件的**目标**
    必须在本条自己的「步骤」行里点名；能落到现成形状上的那几步各落一条，形状只用
    `visit` / `kill` / `item` / `talk`（**不加新形状**，新形状要单独立项 + 鱼鱼点头）
  · 落不了的几拍（「观察」「试着读」「读他留下的字条」这类**档上没账**的动作）不硬凑：
    缺口逐条登记在工作树 `_notes.md`
  · 判据：`scripts/probe_quests.py` ㉑（真跑四拍：接 / 没做完 / 接了就交拦住 / 万事俱备）·
    ㉜（逐步记账：缺一步交不掉 · 全满足则 `flags.quests[<id>].step == 条件条数`）
"""
from __future__ import annotations

from .cmds_ast import _data, _p, _save, _map_of, _name_of_node, T, add_exp
from .town import _func_node, town_gate
from .cmds_talk import _arg
from .cmds_ast import _npcs_here
from . import codex as CX            # 打怪记录（books.monster.kills）的**唯一**读口
from . import loot as LT             # 东西的名字（呈现口不许漏机器键 —— 名字从这里取）


def _mine(p):
    """进行中的委托（id 列表）。"""
    v = (p.get("flags") or {}).get("quests_active")
    return list(v) if isinstance(v, list) else []


def _done(p):
    v = (p.get("flags") or {}).get("quests_done")
    return list(v) if isinstance(v, list) else []


def _set(p, key, val):
    f = dict(p.get("flags") or {})
    f[key] = val
    p["flags"] = f


# ── B3-6c / B3-8：任务三段行文（接 / 进行中 / 交）都从 texts 槽位取 ─────────────
# 真源：`00_总纲/17_文案收口口径_v1.md` 的 `QUEST_{MAIN,SIDE,TRADE,BOUNTY}%02d_{STORY,PROGRESS,
# DELIVER}` 表（B3-6c 主线 36 条 + B3-8 支线/生活/悬赏 87 条 = 123 条）。
# P-17 甲案：quests 域内联的 story / progress_text / deliver_text 三个字段**四条链全裁掉** ——
# 消费端只按 `chain` + `order` 映射取槽位（一个中文都不内联）。
#   · `order` 是域里现成的稳定标识（『接 <编号>』用的就是它：主线 1–12 · 支线 13–30 ·
#     生活 31–38 · 悬赏档 101–103），所以键名 = 链模板 + 编号 —— 不拿名字拼键名。
#   · 四条链的模板写成**字面量**（`_SLOT_TPL`）：probe_copy ⑤ 的「口径表每条都被引用」认这种
#     `前缀%02d_%s` 形状（模板拼出来的键也算引用），别改成运行时拼串。
#   · 认不出的链**不许静默留白**：回一个 fail-closed 哨兵键 —— `T()` 当场回显
#     `[MISSING TEXT: QUEST_UNMAPPED_STORY]`（探针 ㉓ 也钉着「域里每条都算得出真槽位」）。
_SLOT_TPL = {"main": "QUEST_MAIN%02d_%s", "side": "QUEST_SIDE%02d_%s",
             "trade": "QUEST_TRADE%02d_%s", "bounty": "QUEST_BOUNTY%02d_%s"}


def _slot_of(x, part):
    """这条委托的这一拍 → 槽位名（`QUEST_<链>%02d_<PART>`）；认不出的链 ⇒ fail-closed 哨兵键。

    ★ 只认「链 + 编号」这一个映射 —— 不拿名字拼键名（名字改一个字，槽位不该跟着漂）。
    ★ 编号对不上（写缺了 / 超出台账）时 `T()` 会把键名回显出来（fail-closed），不静默留白。
    """
    tpl = _SLOT_TPL.get(str(x.get("chain") or ""))
    if tpl is None:
        return "QUEST_UNMAPPED_%s" % part
    return tpl % (int(x.get("order") or 0), part)


def _beat(x, part):
    """三段行文的一口（唯一取口）—— 四条链都走 texts 槽位（域内那三个字段已裁掉）。"""
    return T(_slot_of(x, part))


# ── 副业（B3-3 · 解 P-14「选甲」）：四个副业的声明在 quests 域的 `_meta.trades` ──────
def _quests():
    """quests 域里的**条目**（`_meta` 那类私有键不算条目 —— 与 recipes / codex 等域同口径）。"""
    return {k: v for k, v in _data("quests").items() if not str(k).startswith("_")}


def _trade_meta():
    """四个副业的声明（顺序 / 名字 / 「这条线是干什么的」）—— 全在数据里，代码不造中文。

    ★ 代码只认「有哪些副业」这件事本身：顺序与名字从 `_meta.trades` 读（生成器从
      `28 §三` + `21 §二` 解析落域）—— 加第五个副业是改数据，不是改代码。
    """
    return list((_data("quests").get("_meta") or {}).get("trades") or [])


def _trade_rows():
    """按副业分好的任务（每组按 `order` 排）—— 分组键就是条目自己的 `trade`（不给 = 不是副业任务）。"""
    out = {}
    for k, v in _quests().items():
        t = v.get("trade")
        if t:
            out.setdefault(t, []).append((k, v))
    for t in out:
        out[t].sort(key=lambda kv: kv[1].get("order") or 0)
    return out


async def trade(env, sink, uid, player):
    """`副业 [名字]` —— 按副业列任务（与『悬赏』并列的第二个入口：悬赏是玛莎的公会委托，副业是手艺人自己的活）。

    无参：四个副业各自任务数 + 一句「这条线是干什么的」（那句从数据来）
    带参：那一个副业下的每一条（可接 / 进行中 / 已交三种标记）
    """
    p = _p(player)
    meta = _trade_meta()
    want = _arg(env)
    act, done = _mine(p), _done(p)
    rows = _trade_rows()
    if not want:
        yield T("SYS_TRADE_HEAD")
        for t in meta:
            yield "  " + T("SYS_TRADE_ROW", trade=t.get("trade"),
                           n=len(rows.get(t.get("trade")) or []), what=t.get("what") or "")
        yield T("SYS_TRADE_HOW")
        return
    hit = next((t for t in meta if want == t.get("trade")), None)
    if hit is None:
        yield T("SYS_TRADE_NOSUCH", name=want,
                list=" · ".join("「%s」" % t.get("trade") for t in meta))
        return
    one = rows.get(hit["trade"]) or []
    yield T("SYS_TRADE_LIST_HEAD", trade=hit["trade"], n=len(one))
    for k, x in one:
        mark = T("SYS_BOARD_ACTIVE") if k in act else \
            (T("SYS_TRADE_MARK_DONE") if k in done else T("SYS_TRADE_MARK_CAN"))
        yield "  " + T("SYS_TRADE_ONE", order=x.get("order"), name=x.get("name"),
                       mark=mark, objective=x.get("objective"))
    yield T("SYS_TRADE_HOW")


# ── 前置条件（P-25）：两个形状见文件抬头 ① ② ────────────────────────
def _require_of(x):
    """这条委托的机器可读前置 —— 没写 = 空表（交活走老判据）。一条 dict 或一串 dict。"""
    r = x.get("require")
    if isinstance(r, dict):
        return [r]
    if isinstance(r, list):
        return [e for e in r if isinstance(e, dict)]
    return []


def _n_of(r):
    """要几个 / 几只（没写 = 1；写成 0 或负数一律当 1 —— 条件不许是白给的）。"""
    try:
        return max(1, int(r.get("n") or 1))
    except (TypeError, ValueError):
        return 1


def _been(p, loc, node=""):
    """去过吗？—— 档上足迹两格都算：`foot.nodes`（第一回到）与 `foot.visits`（去过几回）。"""
    f = p.get("foot")
    f = f if isinstance(f, dict) else {}
    keys = set((f.get("nodes") or {}).keys()) | set((f.get("visits") or {}).keys())
    pre = loc + ":"
    if node:
        return pre + node in keys
    return any(k.startswith(pre) for k in keys)


def _shadow(p):
    """只读影子档：`books` / `foot` 各拷一层。

    为什么：codex 的读口（`kills_of`）走 `_books()`，那把缺的格子**补齐** ——
    在真档上调它，等于「查一次进度」就往玩家档里塞空容器（K57 那族）。
    """
    s = dict(p)
    for k in ("books", "foot"):
        v = p.get(k)
        if isinstance(v, dict):
            s[k] = dict(v)
    return s


def _bag_n(p, iid):
    try:
        return int((p.get("bag") or {}).get(iid) or 0)
    except (TypeError, ValueError):
        return 0


def _req_ok(p, r):
    """一条条件满足没有（认不出的 kind 一律算没满足 —— fail-closed，不静默放行）。"""
    kind = r.get("kind")
    if kind == "visit":
        return _been(p, str(r.get("map") or ""), str(r.get("node") or ""))
    if kind == "kill":
        # ★ B3-11：`kill` 两种写法 —— 点名一只（`monster`）或点**某一档**（`role`，见 `_role_ids`）。
        #   两个都不写 ⇒ 没满足（fail-closed）；认不出的 role ⇒ 那一档取不到怪 ⇒ 计数 0 ⇒ 没满足。
        # ★ B3-13：点档 + `daily` ⇒ 只算**今天点名的那一只**（`_kill_have` 里那一条）。
        return bool(str(r.get("monster") or "") or str(r.get("role") or "")) \
            and _kill_have(p, r) >= _n_of(r)
    if kind == "item":
        iid = str(r.get("item") or "")
        return bool(iid) and _bag_n(p, iid) >= _n_of(r)
    if kind == "enhance":                       # ★ B3-13：有一件装备强化到 ≥ n
        return _enhance_have(p) >= _n_of(r)
    if kind == "cook":                          # ★ B3-13：下过锅 ≥ n 次（可只数某一品阶的食材）
        return _cook_have(p, r) >= _n_of(r)
    if kind == "talk":                          # ★ B3-13：跟这个人搭过 ≥ n 次话
        return bool(str(r.get("npc") or "")) and _talk_have(p, r.get("npc")) >= _n_of(r)
    if kind == "ask":                           # ★ B3-13：搭过话的**人** ≥ n 个
        return _asked_have(p) >= _n_of(r)
    return False


def _role_ids(role):
    """机器键（`monsters.role_key`）→ 这一档的怪 id 表。认不出的档回**空表**（fail-closed）。

    ★ 为什么按 `role_key` 而不是中文档名：`cmds_battle` / `combat` 那两处分档也一律比 ASCII
      `role_key`（中文只用于呈现）—— 条件判定与战斗分档走同一根轴。中文是数据，不是代码。
    """
    if not role:
        return []
    return [k for k, m in _data("monsters").items()
            if not str(k).startswith("_") and m.get("role_key") == role]


def _role_name(role):
    """这一档的**中文档名**（从 monsters 域透传，代码不造中文；认不出的档回空串）。"""
    for m in _data("monsters").values():
        if m.get("role_key") == role:
            return str(m.get("role") or "")
    return ""


def _daily_pick(role, p):
    """★ B3-13：今天这一档**点名**的那一只（「悬赏板每天轮换挑一只」的数据面）。

    轮换 = 该档的怪按 **id 排序**（稳定序 —— 与域里的书写顺序无关）之后，按**游戏日**
    取第 `(游戏日 - 1) % 档内只数 + 1` 只：
      · 同一日、同一档 ⇒ 必是同结果（两个进程也一样 —— 那一天由**那一根钟**唯一决定）
      · ★ B4-9：那一天的来源 = `codex.today(p)` = `calendar.day_now()`（**现算**）——
        原先读的是档上那格 `day`，可它只是 `tick()` 的跨日标记（只有「时间 / 采集 / 建号」
        几个入口在刷）⇒ 悬赏会卡在「上一回 tick 那天」甚至 0 上（今天日期戳那一族一起收的）
      · 跨日 ⇒ 必换（档内只数 > 1；「轮换」的原意就是这个）
      · 游戏日读不到（老档没那一格）= 0 ⇒ 退到档内最后一只：**仍然是确定值，不是随机**
      · 认不出的档 / 空档 ⇒ 空串（调用方一律当「没满足」算 —— fail-closed）
    """
    ids = sorted(_role_ids(str(role or "")))
    if not ids:
        return ""
    return ids[(int(CX.today(p)) - 1) % len(ids)]


def _kill_have(p, r):
    """条件「打掉过几只」的**已达成数**（就是档上那本怪物谱的击杀账 —— 只读，不写）。"""
    mid = str(r.get("monster") or "")
    s = _shadow(p)
    if mid:
        return CX.kills_of(s, mid)
    if r.get("daily"):                       # ★ B3-13：点档 + 每日轮换 ⇒ 只数今天点名的那一只
        tgt = _daily_pick(str(r.get("role") or ""), p)
        return CX.kills_of(s, tgt) if tgt else 0
    return sum(CX.kills_of(s, k) for k in _role_ids(str(r.get("role") or "")))


def _mon_name(mid):
    return (_data("monsters").get(mid) or {}).get("name") or mid


def _item_name(iid):
    return LT.rec_of(iid).get("name") or iid


# ── ★ B3-13：四本**已经在档上**的账（本模块只回头查，一个都不写）────────────
#   · `p.enhance[<装备>]`     强化等级  —— cmds_recipe.enhance 写
#   · `flags.cooked[<配方>]`  下过几次锅 —— cmds_recipe.cook 写
#   · `flags.talked[<对话树>]` 搭过几次话 —— cmds_talk 写
#   · (没有第四本：`ask` 数的是 talked 那本账上有几个**不同的人**)
def _npc_name(npc):
    """NPC id → 中文名（从 npcs 域透传；认不出回空串 —— 呈现口由调用方把关）。"""
    return str((_data("npcs").get(str(npc or "")) or {}).get("name") or "")


def _dlg_of(npc):
    """NPC id → 它那棵对话树 id（唯一出处 = `npcs.dialogue`；认不出回空串）。"""
    return str((_data("npcs").get(str(npc or "")) or {}).get("dialogue") or "")


def _talked(p):
    """档上「搭过几次话」那本账（对话树 id → 次数）；不是 dict = 空账。"""
    t = (p.get("flags") or {}).get("talked")
    return t if isinstance(t, dict) else {}


def _talk_have(p, npc):
    """跟这个人搭过几次话（取不到对话树 ⇒ 0 —— 认不出的 npc 一律当没满足）。"""
    d = _dlg_of(npc)
    if not d:
        return 0
    try:
        return int(_talked(p).get(d) or 0)
    except (TypeError, ValueError):
        return 0


def _asked_have(p):
    """搭过话的**人**有几个 —— 只数域里真有对话树的键（脏键不算一个人）。"""
    ds = _data("dialogues")
    return len([k for k in _talked(p) if k in ds])


def _enhance_have(p):
    """档上**最高**的一件强化等级（`p.enhance[<装备>] = {"lv": …}`；认不出的一律跳过）。"""
    e = p.get("enhance")
    if not isinstance(e, dict):
        return 0
    best = 0
    for v in e.values():
        try:
            best = max(best, int((v if isinstance(v, dict) else {}).get("lv") or 0))
        except (TypeError, ValueError):
            continue
    return best


def _quality_ids(quality):
    """items 域里这个**品阶**的东西（只比数据 —— 代码不认中文品阶名）。"""
    q = str(quality or "")
    return set(k for k, v in _data("items").items()
               if not str(k).startswith("_") and str((v or {}).get("quality") or "") == q)


def _cook_have(p, r):
    """「下过锅几次」的已达成数（账 = `flags.cooked[<配方>]`，写入口 cmds_recipe.cook）。

    带 `quality` 子键时**只数用了那一品阶食材的配方**（食材品阶现从 items 域取 —— 数据比数据；
    品阶名一个字都没写进代码）。认不出的品阶 ⇒ 一道都数不到 ⇒ 没满足（fail-closed）。
    """
    cooked = (p.get("flags") or {}).get("cooked")
    cooked = cooked if isinstance(cooked, dict) else {}
    q = str(r.get("quality") or "")
    ok_ids = _quality_ids(q) if q else None
    have = 0
    for rid, rec in _data("recipes").items():
        if str(rid).startswith("_") or (rec or {}).get("kind_key") != "cook":
            continue
        if ok_ids is not None:
            ins = [str((e or {}).get("id") or "") for e in (rec.get("inputs") or [])]
            if not ok_ids.intersection(ins):
                continue
        try:
            have += int(cooked.get(rid) or 0)
        except (TypeError, ValueError):
            continue
    return have


def _req_lines(p, r):
    """没满足的那一条 → 说人话的那一行。★ 只给名字不给机器键（id 不许出现在回话里）。"""
    kind = r.get("kind")
    if kind == "visit":
        loc, node = str(r.get("map") or ""), str(r.get("node") or "")
        name = _name_of_node(loc, node) if node else ((_map_of(loc) or {}).get("name") or loc)
        return [T("SYS_JOB_REQ_VISIT", place=name)]
    if kind == "kill":
        # ★ B3-11：点名的那一只给怪名；点档的给**档名**（「普通 / 精英 / 头目」—— monsters 域里透传）
        # ★ B3-13：点档 + `daily` ⇒ 报**今天点名的那一只**的怪名（玩家由此知道要打哪一只）
        mid = str(r.get("monster") or "")
        if mid:
            name = _mon_name(mid)
        elif r.get("daily"):
            name = _mon_name(_daily_pick(str(r.get("role") or ""), p))
        else:
            name = _role_name(str(r.get("role") or ""))
        if not name:                       # 档 / 怪认不出 ⇒ 不糊一句空名字（fail-closed 的那一行）
            return [T("SYS_JOB_REQ_UNKNOWN")]
        return [T("SYS_JOB_REQ_KILL", monster=name, n=_n_of(r), have=_kill_have(p, r))]
    if kind == "item":
        iid = str(r.get("item") or "")
        return [T("SYS_JOB_REQ_ITEM", item=_item_name(iid), n=_n_of(r), have=_bag_n(p, iid))]
    if kind == "enhance":                  # ★ B3-13
        return [T("SYS_JOB_REQ_ENHANCE", n=_n_of(r), have=_enhance_have(p))]
    if kind == "cook":                     # ★ B3-13（带品阶的走品阶那条槽位）
        if r.get("quality"):
            return [T("SYS_JOB_REQ_COOK_GRADE", grade=r.get("quality"), n=_n_of(r),
                      have=_cook_have(p, r))]
        return [T("SYS_JOB_REQ_COOK", n=_n_of(r), have=_cook_have(p, r))]
    if kind == "talk":                     # ★ B3-13
        who = _npc_name(r.get("npc"))
        if not who:
            return [T("SYS_JOB_REQ_UNKNOWN")]
        return [T("SYS_JOB_REQ_TALK", who=who, n=_n_of(r), have=_talk_have(p, r.get("npc")))]
    if kind == "ask":                      # ★ B3-13
        return [T("SYS_JOB_REQ_ASK", n=_n_of(r), have=_asked_have(p))]
    return [T("SYS_JOB_REQ_UNKNOWN")]


def _unmet(p, x):
    """还没满足的那几条 → 要回的话（老条目没写 require ⇒ 空表 ⇒ 一行都不多，输出逐字节不变）。"""
    out = []
    for r in _require_of(x):
        if not _req_ok(p, r):
            out.extend(_req_lines(p, r))
    return out


def _mark_done(p, k, step):
    """交活那一下把 done 写进 `flags.quests`（形状见文件抬头 ②；step = 已满足的条件条数）。"""
    book = dict((p.get("flags") or {}).get("quests") or {})
    book[k] = {"step": int(step), "done": True, "at": CX.today(p)}
    _set(p, "quests", book)


async def guild(env, sink, uid, player):
    """`公会` —— 柜台（声明里的 `guard_desc` = 在镇上 · 那一站 = 挂板墙）。

    ★ B4-12：原先这一条**一个地点都不判**（`here` 还是算完不用的死变量）—— 人站在骨田照样
      把公会看个遍，而同一个位置『登记』回的是「这几处都在镇上」。守卫现在与镇上其它几处
      共用 `cmds_ast.town_gate` 那一个执行面。
    """
    p = _p(player)
    line = town_gate(p, _func_node("board"))
    if line:
        yield line
        return
    yield T("SYS_GUILD_HEAD")
    yield T("SYS_GUILD_DESK")
    yield T("SYS_GUILD_HOW")


async def board(env, sink, uid, player):
    """`悬赏` —— 挂板墙上的单子（声明里的 `guard_desc` = 在公会）。★ B4-12：补上守卫。"""
    p = _p(player)
    line = town_gate(p, _func_node("board"))
    if line:
        yield line
        return
    qs = _quests()
    done = _done(p)
    active = _mine(p)
    main = sorted([v for v in qs.values() if v["chain"] == "main"], key=lambda v: v["order"])
    nxt = None
    for v in main:
        qid = [k for k, x in qs.items() if x is v][0]
        if qid not in done:
            nxt = (qid, v)
            break
    yield T("SYS_BOARD_HEAD")
    if nxt is None:
        yield T("SYS_BOARD_NOMAIN")
    else:
        qid, v = nxt
        mark = T("SYS_BOARD_ACTIVE") if qid in active else ""
        yield T("SYS_BOARD_MAIN_ROW", order=v["order"], name=v["name"], mark=mark, level=v["min_level"])
        yield "  " + T("SYS_BOARD_TODO", objective=v["objective"])
        if qid in active:
            yield "  " + T("SYS_BOARD_DELIVER", order=v["order"])
        else:
            yield "  " + T("SYS_BOARD_NEXT", order=v["order"])
    side = [v for v in qs.values() if v["chain"] == "side" and v["giver"] in
            [k for k, _ in _npcs_here(p["loc"], p["node"], p=p)]]
    if side:
        yield T("SYS_BOARD_SIDE_HEAD")
        for v in side[:3]:
            # ★ 支线也**必须带编号**：不带编号 + `接 <编号>` 只认主线 ⇒ 18 条支线全接不了
            #   （2026-09-25 端到端玩出来的真 bug）。硬编码中文一并收进槽位（B3-6 口径）。
            yield "  " + T("SYS_BOARD_SIDE_ROW", order=v["order"], name=v["name"],
                           objective=v["objective"])
    yield T("SYS_BOARD_HOW")


async def quest_accept(env, sink, uid, player):
    p = _p(player)
    want = _arg(env)
    qs = _quests()
    if not want:
        yield T("SYS_JOB_ASK")
        return
    v = None
    if want.isdigit():
        n = int(want)
        for k, x in qs.items():
            # ★ 编号对**所有**链都成立（原先只认 main ⇒ 支线接不了）
            if x.get("order") == n:
                v = (k, x)
                break
    if v is None:
        for k, x in qs.items():
            if x["name"] == want:
                v = (k, x)
                break
    if v is None:
        yield T("SYS_JOB_NOSUCH", name=want)
        return
    k, x = v
    if k in _mine(p) or k in _done(p):
        yield T("SYS_JOB_ALREADY")
        return
    if p.get("level", 1) < x["min_level"]:
        yield T("SYS_JOB_LOWLEVEL", name=x["name"], need=x["min_level"], now=p.get("level"))
        yield T("SYS_JOB_MARTHA")
        return
    _set(p, "quests_active", _mine(p) + [k])
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_JOB_TAKEN", name=x["name"])
    # ★ B3-6c / B3-8：接时那一段（槽位自己的出处就写着「接时行文」）—— 四条链都取槽位。
    yield _beat(x, "STORY")
    yield "  " + T("SYS_JOB_TODO", objective=x["objective"])
    if x.get("insight"):
        yield "  " + T("SYS_JOB_INSIGHT", insight=x["insight"])
    yield T("SYS_JOB_GO")


async def quest_deliver(env, sink, uid, player):
    p = _p(player)
    want = _arg(env)
    qs = _quests()
    act = _mine(p)
    if not act:
        yield T("SYS_JOB_NONE")
        return
    k = None
    if want.isdigit():
        for kk in act:
            if qs.get(kk, {}).get("order") == int(want):
                k = kk
                break
    else:
        for kk in act:
            if qs.get(kk, {}).get("name") == want:
                k = kk
                break
    if k is None:
        yield T("SYS_JOB_NOT_MINE")
        for kk in act:
            yield "  · %s" % qs.get(kk, {}).get("name", kk)
        return
    x = qs[k]
    if not _obj_ok(x, p):
        yield T("SYS_JOB_NOT_DONE") + (_beat(x, "PROGRESS") or x["objective"])
        for line in _unmet(p, x):          # ★ P-25：把「还差什么」说清楚（老条目这里一行都不多）
            yield "  " + line
        return
    _set(p, "quests_active", [a for a in act if a != k])
    _set(p, "quests_done", _done(p) + [k])
    _mark_done(p, k, len(_require_of(x)))   # ★ P-25：done 记进 flags.quests（形状见文件抬头 ②）
    p["gold"] = p.get("gold", 0) + x["reward_gold"]
    # ★ B3-13：升级判定收成 `cmds_ast.add_exp` **一个口**（打怪给经验也走它）
    leveled = bool(add_exp(p, x["reward_exp"]))
    lv = p.get("level", 1)
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_JOB_DELIVERED", name=x["name"])
    yield _beat(x, "DELIVER")         # ★ B3-6c / B3-8：交时那一段（四条链都走槽位）
    yield T("SYS_JOB_REWARD", exp=x["reward_exp"], gold=x["reward_gold"])
    if leveled:
        yield T("SYS_JOB_LEVELUP", level=lv)
    if x.get("hook"):
        yield "（「%s」）" % x["hook"]


def _obj_ok(x, p):
    """交活判据 —— ★ P-25：写了 `require` 的条目**逐条真查**（做没做，档上有账）。

    · 主线：**等级 + 逐步记账** —— ★ B4-2 落了 `require` 之后，判据就是
      `level >= min_level` **且** `require` 逐条满足（12 条全写了 ⇒ 「1 级接 1 级主线、
      一句『交 1』就过」那条老路已经堵死）。没写 `require` 的主线仍只看等级。
    · 支线：写了 `require` 就逐条查；**没写的照旧**看 `flags.side_<名字>`
    ⇒ 没有 `require` 的老条目，这一支的行为逐字节不变（回归口径见任务卡 P-25）。
    """
    reqs = _require_of(x)
    if x["chain"] == "main":
        return p.get("level", 1) >= x["min_level"] and all(_req_ok(p, r) for r in reqs)
    if reqs:
        return all(_req_ok(p, r) for r in reqs)
    return bool((p.get("flags") or {}).get("side_" + x["name"]))


async def quest_abandon(env, sink, uid, player):
    p = _p(player)
    act = _mine(p)
    if not act:
        yield T("SYS_JOB_NO_ACTIVE")
        return
    want = _arg(env)
    qs = _quests()
    k = act[0] if not want else next((a for a in act if qs.get(a, {}).get("name") == want
                                      or qs.get(a, {}).get("order") == (int(want) if want.isdigit() else -1)), None)
    if not k:
        yield T("SYS_JOB_NO_ACTIVE_ONE")
        return
    _set(p, "quests_active", [a for a in act if a != k])
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_JOB_ABANDONED", name=qs.get(k, {}).get("name", k))


async def quest_mine(env, sink, uid, player):
    p = _p(player)
    qs = _quests()
    act, done = _mine(p), _done(p)
    if not act:
        yield T("SYS_MINE_NONE")
    else:
        yield T("SYS_MINE_HEAD", n=len(act))
        for k in act:
            x = qs.get(k, {})
            yield "· %s —— %s" % (x.get("name", k), x.get("objective", ""))
    if done:
        yield T("SYS_MINE_DONE", n=len(done))
    yield T("SYS_MINE_RANK")
