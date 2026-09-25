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
     {"kind": "item",  "item": <物品 id>, "n": <份数>}       背包里有 n 份
   写一条 dict，或写一串 dict（**全部**满足才算做了）；认不出的 kind 一律算没满足（fail-closed，
   不静默放行）。中文的 `objective` **不解析** —— 条件的真源是 `require`。

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
"""
from __future__ import annotations

from .cmds_ast import _data, _p, _save, _map_of, _name_of_node, T, add_exp
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
        mid = str(r.get("monster") or "")
        return bool(mid) and CX.kills_of(_shadow(p), mid) >= _n_of(r)
    if kind == "item":
        iid = str(r.get("item") or "")
        return bool(iid) and _bag_n(p, iid) >= _n_of(r)
    return False


def _mon_name(mid):
    return (_data("monsters").get(mid) or {}).get("name") or mid


def _item_name(iid):
    return LT.rec_of(iid).get("name") or iid


def _req_lines(p, r):
    """没满足的那一条 → 说人话的那一行。★ 只给名字不给机器键（id 不许出现在回话里）。"""
    kind = r.get("kind")
    if kind == "visit":
        loc, node = str(r.get("map") or ""), str(r.get("node") or "")
        name = _name_of_node(loc, node) if node else ((_map_of(loc) or {}).get("name") or loc)
        return [T("SYS_JOB_REQ_VISIT", place=name)]
    if kind == "kill":
        mid = str(r.get("monster") or "")
        return [T("SYS_JOB_REQ_KILL", monster=_mon_name(mid), n=_n_of(r),
                  have=CX.kills_of(_shadow(p), mid))]
    if kind == "item":
        iid = str(r.get("item") or "")
        return [T("SYS_JOB_REQ_ITEM", item=_item_name(iid), n=_n_of(r), have=_bag_n(p, iid))]
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
    p = _p(player)
    here = _npcs_here(p["loc"], p["node"], p=p)
    yield T("SYS_GUILD_HEAD")
    yield T("SYS_GUILD_DESK")
    yield T("SYS_GUILD_HOW")


async def board(env, sink, uid, player):
    p = _p(player)
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

    · 主线：到等级就算做完（原判据）· 另加 `require`（写了才判 —— 现在一条都没写）
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
