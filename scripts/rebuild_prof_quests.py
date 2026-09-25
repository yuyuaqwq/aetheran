# -*- coding: utf-8 -*-
"""prof_quests 落域脚本（B3-3 · 解 P-14「选甲」）：生活职业任务 —— 给 quests 域加 `trade` + 补 8 条新的。

源（只读 · 单一真源，本脚本**只解析、不手打**）：
  · `06_第一阶段垂直切片/28_生活职业任务_设计_v1.md`
      §三  trade 的四个取值（顺序 = 文档顺序）
      §四  两张表：①「已重合的 8 条」（现有 id → trade）②「新的 8 条」（新 id / 名字 / trade / 内容 / 奖励 / 挂谁）
  · `06_第一阶段垂直切片/21_长期目标层_v1.md` §二
      四个小节标题 = 「这条线是干什么的」（`### 采集（娜娜的药草线）` 的括号里那句）
      表里 16 行的 名字 / 内容 / 奖励 —— **探针就拿这一份对账**（probe_quests ⑪）
  说明：名字 / 内容（objective）/ 奖励（deliver_text）以 **21 §二** 为准（对账的那一份），
       id / trade / 挂谁 以 **28 §四** 为准 —— 两边的名字必须一致（脚本断言，不一致就抛）。

落点：`content/data/quests.json`（quests 域）

规矩（生成物规矩，照 skill: aetheran-authoring §六）：
  · 只**新增**：已存在的条目除多一个 `trade` 字段外**逐字不动**（名字/trade 对不上当场抛）
  · 数值**不手打**：新条目的 min_level / reward_exp / reward_gold 从**域里现有支线**的口径取
    （先断言 18 条支线共用同一个 (min_level, exp, gold) —— 不一致就抛，逼人来裁决）
  · 条件（`require`）的形状只有 P-25 的三型（visit / kill / item）—— 文档给的是人话（「内容」列），
    这一层映射由本脚本按**域里的真数据**推出来（禁手打 id）：
      指定矿        → 物品说明里写着「采矿产」的那件（唯一）
      旧铁          → 名字就是「旧铁」的那件（唯一）
      常见鱼 / 稀有鱼 → 垂钓池里**带 `when` 时辰限制**的是稀有鱼、不带的是常见鱼
      不是鱼的东西  → 浅滩那个垂钓点池里**不叫 i_fish_*** 的**信物**那件（B3-4 之后池里有两个「不是鱼」的）
      「有故事」的旧物 → **codex 旧物谱里、认它的人包含接活那位** 的那件（柯尔 → unid_common）
      旧哨塔附近 / 骨田 / 三条带最深处 → maps 域按名字 / 按 `roles.exit == 深处` 找（不手打节点 id）
    数量的中文数词从「内容」列解析（三种 → 3），解析不出就是 1。
  · 保持插入序（K27：别 sort_keys）· 新 8 条插在支线块之后、悬赏块之前 · LF · 末尾一个换行
  · 连跑两次数据不变（幂等自检）
  · `_meta`（四个副业的声明：顺序 / 名字 / 「这条线是干什么的」）也由本脚本落 —— 别的域同口径

用法：python scripts/rebuild_prof_quests.py [--dry]
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.environ.get("AST_PLAN", "C:/Users/yuyu/aetheran-plan")
SLICE = os.path.join(PLAN, "06_第一阶段垂直切片")
DOC28 = os.path.join(SLICE, "28_生活职业任务_设计_v1.md")
DOC21 = os.path.join(SLICE, "21_长期目标层_v1.md")
DATA = os.path.join(REPO, "content", "data")
QFILE = os.path.join(DATA, "quests.json")

CN_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
CELL = re.compile(r"^\|(.+)\|\s*$")
TICK = re.compile(r"`([a-z0-9_]+)`")


def _read(path):
    if not os.path.exists(path):
        raise SystemExit("源文档不在：%s" % path)
    return io.open(path, encoding="utf-8", newline="").read()


def _cells(line):
    """一行 markdown 表 → 去空格的单元格；不是表行/是分隔行就回 None。"""
    m = CELL.match(line.strip())
    if not m:
        return None
    out = [c.strip() for c in m.group(1).split("|")]
    if all(set(c) <= set("-: ") and c for c in out):
        return None                                   # |---|---| 分隔行
    return out


def _rows_after(lines, anchor, stop):
    """从 anchor 那一行之后开始收表行，直到不是表行 / 撞上 stop 前缀。"""
    out, on = [], False
    for ln in lines:
        if not on:
            if anchor in ln:
                on = True
            continue
        if ln.startswith(stop) or ln.startswith("## "):
            break
        cs = _cells(ln)
        if cs:
            out.append(cs)
    return out


def load(name):
    with io.open(os.path.join(DATA, name + ".json"), encoding="utf-8") as f:
        return json.load(f)


# ── 一、解析真源 ────────────────────────────────────────────────
def parse_trade_values(txt28=None):
    """28 §三 的 `取值  "采集" | "垂钓" | "烹饪" | "强化"` → 四个取值（顺序 = 文档顺序）。"""
    txt28 = txt28 if txt28 is not None else _read(DOC28)
    m = re.search(r"^取值\s+(.+)$", txt28, re.M)
    if not m:
        raise SystemExit("28 §三 找不到「取值」那一行")
    vals = re.findall(r"\"([^\"]+)\"", m.group(1))
    if len(vals) != 4:
        raise SystemExit("28 §三 的取值不是四个：%s" % vals)
    return vals


def parse_doc28(txt28=None):
    """28 §四 两张表 → (现有 8 条: [(id, name, trade)], 新 8 条: [(id, name, trade, 内容, 奖励, 挂谁)])。"""
    txt28 = txt28 if txt28 is not None else _read(DOC28)
    lines = txt28.split("\n")
    old = [r for r in _rows_after(lines, "### 已重合的 8 条", "###") if len(r) == 4 and TICK.match(r[0])]
    new = [r for r in _rows_after(lines, "### 新的 8 条", "##") if len(r) == 6 and TICK.match(r[0])]
    old = [(TICK.match(r[0]).group(1), r[1], r[2]) for r in old]
    new = [(TICK.match(r[0]).group(1), r[1], r[2], r[3], r[4], r[5]) for r in new]
    if len(old) != 8 or len(new) != 8:
        raise SystemExit("28 §四 两张表行数不对：已重合 %d 条 / 新 %d 条（应各 8）" % (len(old), len(new)))
    return old, new


def parse_doc21(txt21=None):
    """21 §二 四个小节 → [(trade, 「这条线是干什么的」, [(名字, 内容, 奖励)])]（顺序 = 文档顺序）。"""
    txt21 = txt21 if txt21 is not None else _read(DOC21)
    body = txt21.split("## 二、生活职业任务", 1)[-1].split("\n## 三、", 1)[0]
    out = []
    for ln in body.split("\n"):
        m = re.match(r"^### (\S+?)（(.+?)）\s*$", ln.strip())
        if m:
            out.append([m.group(1), m.group(2), []])
            continue
        if not out:
            continue
        cs = _cells(ln)
        if cs and len(cs) == 3 and cs[0] != "任务":
            out[-1][2].append(tuple(cs))
    if len(out) != 4 or sum(len(x[2]) for x in out) != 16:
        raise SystemExit("21 §二 解析出 %d 节 / %d 行（应 4 节 / 16 行）" %
                         (len(out), sum(len(x[2]) for x in out)))
    return [(t, w, rows) for t, w, rows in out]


# ── 二、域里按「人话」找 id（禁手打）────────────────────────────
def _only(cands, what):
    cands = sorted(cands)
    if len(cands) != 1:
        raise SystemExit("「%s」在域里对应 %d 个 id（应当唯一）：%s" % (what, len(cands), cands))
    return cands[0]


def _n_of(text, default=1):
    """「三种」→ 3 ·「一块」→ 1（数量从人话里解析，不手打）。"""
    for ch, n in CN_NUM.items():
        if re.search(r"%s(?:\s*[种条块件个只份])" % ch, text):
            return n
    return default


def _deepest_nodes(maps):
    """三条带的「最深处」—— 不手打节点 id：

    「三条带」= 名字里带「带」的那三张图（北带 · 骨田 / 东带 · 白桦林 / 西带 · 浅滩）；
    「最深处」= 那条链的**末节点**（`topology: chain` 的最后一格）。
    ★ 为什么不用角色的 `深处` 标记：belt_north 的末节点标了 `深处`，east / west 两个没标
      （同一份 maps 域里两种写法）—— 按角色找会漏两条，按链尾找三条都对得上。
    """
    out = []
    for mid, m in maps.items():
        if "带" not in str(m.get("name") or "") or (m.get("topology") or "chain") != "chain":
            continue
        ns = [n["id"] for n in (m.get("nodes") or [])]
        if ns:
            out.append((mid, ns[-1]))
    if len(out) != 3:
        raise SystemExit("「三条带」按名字里的「带」找出 %d 条，不是 3 条：%s" % (len(out), out))
    return out


def _reachable_items(ga, dp, rc):
    """真拿得到的东西 = 采集池 / 掉落池（含未鉴定池）/ 配方产出（照 probe_codex ④ 的算法）。"""
    out = set()
    for g in ga.values():
        for e in (g.get("pool") or []):
            out.add(str(e.get("out")))
    for p_ in dp.values():
        for e in (p_.get("entries") or []) + (p_.get("pool") or []):
            out.add(str(e.get("out")))
    for r in rc.values():
        if r.get("out"):
            out.add(str(r["out"]))
    return out


def _item_by_desc(it, word):
    return _only([k for k, v in it.items() if word in str(v.get("desc") or "")], "说明里写着「%s」的东西" % word)


def _item_by_name(it, name):
    return _only([k for k, v in it.items() if v.get("name") == name], "叫「%s」的东西" % name)


def _fish_by_when(ga):
    """垂钓池里推「常见鱼 / 稀有鱼」—— 不手打 id：

    一件鱼**每次出现都带时辰限制**（池条目的 `when`，或那个点自己的 `time`）⇒ 稀有鱼；
    有**不受限**的那次出现 ⇒ 常见鱼。（实测：无鳞鱼两次都被「夜」挡住 · 石斑在渡口那点白天也上。）
    """
    restricted, free = set(), set()
    for g in ga.values():
        if (g.get("verb") or "") != "fish":
            continue
        for e in (g.get("pool") or []):
            o = str(e.get("out"))
            if not o.startswith("i_fish_"):
                continue
            if e.get("when") or g.get("time"):
                restricted.add(o)
            else:
                free.add(o)
    rare = _only(restricted - free, "稀有鱼（每次出现都受时辰限制的那件）")
    common = _only(free, "常见鱼（有一次不受限的出现的那件）")
    return rare, common


def _not_fish_in_shoal(ga, maps, it):
    """「浅滩」那个垂钓点池里**不是鱼**的那件 —— 取**信物**那件。

    ★ 池里现在有两个「不是鱼」的：先是垃圾 `i_junk_boot`（旧靴子），B3-4 又按 `30 §三 行 6` / P-15 ①
      做出来一个**信物**（`i_token_underwater_steps` · 石阶缺的那一级 = 隐藏线那一角）。
      设计原文那句「在浅滩钓到一个不是鱼的东西」要的是**信物**那件 ⇒ 按 kind 取，别只靠「唯一」：
      B3-4 落域那天这条启发式当场 fail-closed（两个 id）—— 这正是「唯一」不够用的证据。
    """
    nodes = [(mid, n) for mid, m in maps.items() for n in (m.get("nodes") or [])]
    _mid, shoal = [(mid, n) for mid, n in nodes if n.get("name") == "浅滩"][0]
    cands = set()
    for g in ga.values():
        if g.get("subarea") == shoal["id"] and (g.get("verb") or "") == "fish":
            for e in (g.get("pool") or []):
                o = str(e.get("out"))
                if not o.startswith("i_fish_"):
                    cands.add(o)
    tok = sorted(c for c in cands if (it.get(c) or {}).get("kind") == "信物")
    if len(tok) == 1:
        return tok[0]
    return _only(cands, "浅滩垂钓池里不是鱼的那件")


def _relic_known_by(cx, npc_id):
    """旧物谱里「认它的人」包含这位 NPC 的那件（唯一）。"""
    return _only([k for k, v in (cx.get("relic") or {}).items() if npc_id in (v.get("ask") or [])],
                 "旧物谱里认它的人包含 %s 的那件" % npc_id)


def _node_by_name(maps, name):
    for mid, m in maps.items():
        for n in (m.get("nodes") or []):
            if n.get("name") == name:
                return mid, n["id"]
    raise SystemExit("地图上没有叫「%s」的节点" % name)


def _node_starts(maps, prefix):
    for mid, m in maps.items():
        for n in (m.get("nodes") or []):
            if str(n.get("name") or "").startswith(prefix):
                return mid, n["id"]
    raise SystemExit("地图上没有名字以「%s」开头的节点" % prefix)


# ── 三、条件表：28 §四「内容」列的人话 → P-25 三型条件（id 全部由上面推出来）
def build_require(qid, prose, ctx):
    """一条新任务的 `require`（依据写在每支的注里）。"""
    it, ga, maps, cx = ctx["items"], ctx["gathering"], ctx["maps"], ctx["codex"]
    n = _n_of(prose)
    if qid == "q_trade_01":
        # 「去三条带最深处各采一次」→ 三条带最深处各去一趟（那三处各有采集点，见探针判据）
        return [{"kind": "visit", "map": mid, "node": nd} for mid, nd in _deepest_nodes(maps)]
    if qid == "q_trade_02":
        # 「在旧哨塔附近采到指定矿」→ 去过旧哨塔下（附近）+ 手上有矿（说明里写着「采矿产」那件）
        mid, nd = _node_starts(maps, "旧哨塔")
        return [{"kind": "visit", "map": mid, "node": nd},
                {"kind": "item", "item": _item_by_desc(it, "采矿产"), "n": n}]
    if qid == "q_trade_03":
        # 「钓齐三种常见鱼」→ 常见鱼（垂钓池里不带时辰限制的那件）× N（中文数词解析）
        return [{"kind": "item", "item": _fish_by_when(ga)[1], "n": n}]
    if qid == "q_trade_04":
        # 「夜里钓上稀有鱼」→ 稀有鱼（池里带时辰限制的那件）× 1
        return [{"kind": "item", "item": _fish_by_when(ga)[0], "n": n}]
    if qid == "q_trade_05":
        # 「特定鱼换一道菜谱」→ 那本菜谱（客栈的招牌）自己吃的那种鱼（从配方 inputs 推）
        rec = _only([k for k, r in ctx["recipes"].items() if r.get("name") == "客栈的招牌"], "菜谱「客栈的招牌」")
        ins = [e["id"] for e in (ctx["recipes"][rec].get("inputs") or []) if str(e["id"]).startswith("i_fish_")]
        return [{"kind": "item", "item": _only(ins, "「客栈的招牌」要的鱼"), "n": n}]
    if qid == "q_trade_06":
        # 「在浅滩钓到一个不是鱼的东西」→ 浅滩垂钓池里不是鱼的那件
        return [{"kind": "item", "item": _not_fish_in_shoal(ga, maps, it), "n": n}]
    if qid == "q_trade_07":
        # 「修好一件『有故事』的旧装备」→ 旧物谱里**认它的人包含接活这位（柯尔）**的那件
        #   （形状只有 visit/kill/item 三型：「修好」这个动作没有条件形状 ⇒ 见报告遗留）
        return [{"kind": "item", "item": _relic_known_by(cx, ctx["giver_id"]), "n": n}]
    if qid == "q_trade_08":
        # 「带一块骨田挖出的旧铁给他」→ 去过骨田 + 手上有旧铁（名字就是「旧铁」那件）
        mid, nd = _node_by_name(maps, "骨田")
        return [{"kind": "item", "item": _item_by_name(it, "旧铁"), "n": n},
                {"kind": "visit", "map": mid, "node": nd}]
    raise SystemExit("新任务没有条件映射：%s" % qid)


def _strip_star(s):
    """21 §二 的奖励列带着 ★（强调符）—— 落进域之前去掉，顺手收掉括号里多出来的空格。"""
    s = s.replace("★ ", "").replace("★", "")
    return s.replace("（ ", "（").replace(" ）", "）").strip()


def _insert_after(d, anchor, key, val):
    """把 key 插在 anchor 后面（anchor 不在就追加）—— 保住原插入序，幂等。"""
    if key in d:
        d[key] = val
        return d
    out = {}
    for k, v in d.items():
        out[k] = v
        if k == anchor:
            out[key] = val
    if key not in out:
        out[key] = val
    return out


def build(dry=False):
    trades = parse_trade_values()
    old8, new8 = parse_doc28()
    sec21 = parse_doc21()
    q = load("quests")
    npcs, maps, it, ga, dp, rc, cx = (load("npcs"), load("maps"), load("items"), load("gathering"),
                                      load("drop_pools"), load("recipes"), load("codex"))
    entries = {k: v for k, v in q.items() if not str(k).startswith("_")}
    reach = _reachable_items(ga, dp, rc)

    # ① 21 §二 与 28 §四 的名字必须一致（两份文档不许打架）
    by_name21 = {r[0]: (t, r) for t, _w, rows in sec21 for r in rows}
    for qid, name, trade, prose, reward, who in new8:
        if name not in by_name21:
            raise SystemExit("28 有、21 没有：%s（%s）" % (qid, name))
        if by_name21[name][0] != trade:
            raise SystemExit("%s 的副业两份文档不一致：28 %s vs 21 %s" % (qid, trade, by_name21[name][0]))
        if by_name21[name][1][1] != prose:
            raise SystemExit("%s 的「内容」两份文档不一致：\n  28 %s\n  21 %s"
                             % (qid, prose, by_name21[name][1][1]))
    for _qid, name, _t in old8:
        if name not in by_name21:
            raise SystemExit("28 的已重合表里有、21 没有：%s" % name)

    # ② 现有 8 条：加 `trade`（名字对不上当场抛）
    for qid, name, trade in old8:
        if qid not in entries:
            raise SystemExit("28 指的现有条目不存在：%s" % qid)
        if entries[qid].get("name") != name:
            raise SystemExit("%s 名字对不上：域里是 %s / 文档是 %s" % (qid, entries[qid].get("name"), name))
        if trade not in trades:
            raise SystemExit("%s 的 trade 不在四个取值里：%s" % (qid, trade))

    # ③ 数值口径：现有支线共用一个 (min_level, exp, gold)（不手打，不一致就抛）
    side = [v for v in entries.values() if v.get("chain") == "side"]
    base = sorted({(v["min_level"], v["reward_exp"], v["reward_gold"]) for v in side})
    if len(base) != 1:
        raise SystemExit("现有 %d 条支线不是同一个数值口径，先裁决：%s" % (len(side), base))
    min_level, reward_exp, reward_gold = base[0]

    # ④ 新 8 条：字段与条件（编号接着**支线**那一串排 —— 101+ 那一段是悬赏档自己的区）
    order0 = max(int(v.get("order") or 0) for v in entries.values()
                 if v.get("chain") in ("main", "side")) + 1
    made = {}
    for i, (qid, name, trade, prose, reward, who) in enumerate(new8):
        gid = _only([k for k, v in npcs.items() if v.get("name") == who], "叫「%s」的 NPC" % who)
        mid = (npcs[gid].get("map") or "")
        if mid not in maps:
            raise SystemExit("%s 的挂单人在的地图不在 maps 域：%s" % (qid, mid))
        req = build_require(qid, prose, {"items": it, "gathering": ga, "maps": maps,
                                        "codex": cx, "recipes": rc, "giver_id": gid})
        for r in req:
            if r.get("item") and r["item"] not in it and not r["item"].startswith("unid_"):
                raise SystemExit("%s 要的东西不在物品表：%s" % (qid, r["item"]))
            if r.get("item") and r["item"] not in reach:
                raise SystemExit("%s 要的东西没有出产渠道：%s" % (qid, r["item"]))
        e21 = by_name21[name][1]
        made[qid] = {
            "name": name, "kind": "生活", "chain": "trade", "order": order0 + i,
            "giver": gid, "map": mid, "trade": trade,
            "min_level": min_level, "need": None,
            "objective": e21[1], "require": req,
            "reward_exp": reward_exp, "reward_gold": reward_gold,
            # ★ `story` / `progress_text` / `deliver_text` 三个内嵌字段**不再由本脚本写**：
            #   B3-6c（主线）与 B3-8（支线 / 生活 / 悬赏）已把这三种行文迁进 texts 真源
            #   （槽位 `QUEST_<CHAIN>%02d_{STORY,PROGRESS,DELIVER}`，代码走 `content/cmds_quest.py`
            #   的 `_slot_of` 按 chain + order 取）。写回来就等于把两处口径又立起来（探针 ㉓ 会当场红）。
            "teach": "", "insight": "", "hook": _strip_star(e21[2]),
            "unlock": [],
        }

    # ⑤ 组装（插入序：_meta 在最前 · 新 8 条插在支线块之后、悬赏块之前）
    meta = {"note": "四个副业的声明 —— 由 scripts/rebuild_prof_quests.py 从 28 §三 / 21 §二 解析生成；别手改本文件",
            "source": ["06_第一阶段垂直切片/28_生活职业任务_设计_v1.md §三 §四",
                       "06_第一阶段垂直切片/21_长期目标层_v1.md §二"],
            "trades": [{"trade": t, "order": i + 1, "what": w}
                       for i, (t, w, _rows) in enumerate(sec21)]}
    if [m["trade"] for m in meta["trades"]] != trades:
        raise SystemExit("28 §三 的取值与 21 §二 的小节对不上：%s vs %s"
                         % (trades, [m["trade"] for m in meta["trades"]]))
    trade_of = {qid: t for qid, _n, t in old8}

    out, added, touched = {}, [], []
    for k, v in entries.items():
        v2 = dict(v)
        if k in trade_of:
            v2 = _insert_after(v2, "map", "trade", trade_of[k])
            touched.append(k)
        out[k] = v2
        if k == "q_side_18":                       # 支线块之后插新 8 条
            for nq in sorted(made, key=lambda x: made[x]["order"]):
                if nq in entries:
                    if entries[nq] != made[nq]:
                        diff = [(k2, entries[nq].get(k2), made[nq].get(k2))
                                for k2 in sorted(set(entries[nq]) | set(made[nq]))
                                if entries[nq].get(k2) != made[nq].get(k2)]
                        raise SystemExit("%s 已在域里但内容与文档不符（先裁决）：%s" % (nq, diff))
                    out[nq] = entries[nq]
                else:
                    out[nq] = made[nq]
                    added.append(nq)
                    print("  + %-12s %s（%s · %s）" % (nq, made[nq]["name"], made[nq]["trade"],
                                                      made[nq]["deliver_text"][:18]))
    for nq in made:                                # 万一 q_side_18 不在（锚点丢了）
        if nq not in out:
            raise SystemExit("锚点 q_side_18 不在域里，新条目插不进去")
    final = {"_meta": meta}
    final.update(out)
    return final, {"added": added, "touched": touched, "trades": trades,
                   "meta": meta, "made": made, "base": base[0]}


def main(argv):
    dry = "--dry" in argv
    q = load("quests")
    final, info = build(dry)
    before = {k: v for k, v in q.items()}
    same = (json.dumps(before, ensure_ascii=False, sort_keys=False)
            == json.dumps({k: v for k, v in final.items() if k != "_meta"}, ensure_ascii=False, sort_keys=False))
    print("解析：trade %s · 现有 %d 条加 trade · 新增 %d 条 · 数值口径（支线）%s"
          % (info["trades"], len(info["touched"]), len(info["added"]), info["base"]))
    print("  · 新条目条件：%s" % json.dumps({k: v["require"] for k, v in info["made"].items()},
                                            ensure_ascii=False))
    if dry:
        print("（--dry：没落盘）")
        return 0
    with io.open(QFILE, "w", newline="\n", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("落地：quests %d -> %d 条  %s" % (len(before) + (0 if "_meta" in before else 1),
                                          len(final), QFILE))
    if same and info["added"] == [] and info["touched"] != []:
        print("  · 幂等：条目内容与改前一致（只多了 `trade` 字段）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
