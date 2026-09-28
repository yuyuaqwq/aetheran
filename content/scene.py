# -*- coding: utf-8 -*-
"""场景槽位解析 —— 「观察」与「落域脚本」共用的一个口（B3-6a）

顺序（★ 单一真源，别在两处各写一遍）：
  ① `SCENE_<节点>`  节点级 · 站在这个点上的近景（例：站在拾荒营地）
  ② `SCENE_<地图>`  地图级 · 踏进这张图的第一眼（野外带的到达一屏）
取不到 = None —— 调用方自己决定怎么兜底（**不静默给空字符串**，也不在这里造文案）。

为什么单开一个模块：`scripts/rebuild_scenes.py` 落表时要按同一套规则对账，
  而它不能 import `content.cmds_ast`（那条链会拉起引擎）。所以本模块**零依赖**。
"""


def slot_key(name):
    """槽位键的**唯一写法**：`SCENE_<名字大写>` —— 节点级与地图级共用这一处（P-19）。

    为什么收成一个口：`SCENE_OLD_WATCHTOWER`（地图级 —— 地图 id `old_watchtower`）与
      `SCENE_TOWER_GATE`（节点级 —— 那一间房的 id `tower_gate`）是**同一处**（旧哨塔门口），
      两条键的写法一模一样，原先却各写一份 `"SCENE_%s" % str(x).upper()`：
      谁哪天动了一处（加前缀 / 换分隔符），另一处就对不上（K65 那族「同一件事两处口径」）。
      现在 `node_key` / `map_key` 都只是本函数的**转发** —— 两个入口的名字不变，调用方一字不用改。
    """
    return "SCENE_%s" % str(name).upper()


def node_key(node):
    """节点级槽位：`SCENE_<节点 id 大写>`（站在拾荒营地 → `SCENE_BN_CAMP`）。"""
    return slot_key(node)


def map_key(loc):
    """地图级槽位：`SCENE_<地图 id 大写>`（踏进骨田 → `SCENE_BELT_NORTH`）。"""
    return slot_key(loc)


#: 「这一站的人此刻都不在」那一版的键尾（`SCENE_<节点>_EMPTY`）—— 口径见 `resolve` 的 `empty`。
#: ★ 它是**键尾的唯一真源**：`empty_key` 逐字由它拼，不另写一份字面量（审计 L2529-3）。
#: ★ 关于「拼法会不会让 `scripts/probe_copy` ⑤ 查不出谁引用了它」：实测**不成立** ——
#:   ⑤ 的模板判据认的是**含 `%s` 的字面量拼出的正则**，而本模块 `slot_key` 里那个
#:   `"SCENE_%s"` 已经把 `SCENE_<任何>_EMPTY` 整个形状覆盖掉（实测 `SCENE_WT_WALL_EMPTY` 命中 True）。
#:   所以这里用 `+` 拼不丢覆盖率；原先那条「写成 + 会让那一条查不出」的理由是**杜撰的**，已删。
EMPTY_SUFFIX = "_EMPTY"


def empty_key(node):
    """节点级 · **人不在那一版**：`SCENE_<节点>_EMPTY`（口径 31_NPC作息 §四「人不在也要有戏」）。

    为什么要在下一版场景：节点级场景是**静态文本**，可这一站的人有作息（哈根只在昏/夜、
    老陶集日被吸去挂板墙）⇒ 画面写「有人在旁边坐着」而名册里一个人都没有，
    玩家照着画面去『搭话』只得到「这儿没有别人」（P1 BUG-5）。空版只在这一站**本该有人、
    此刻一个都没到场**时才用（判定 = `content/town.py::station_empty`）。
    """
    return node_key(node) + EMPTY_SUFFIX


#: ★ g4-⑤：「按状态分支」那一档的变体后缀（`SCENE_<节点>__<状态>`）。
#:   今天只有一处：白烛堂那句「你把伤口给他看」对**满血**的玩家同样别扭（P1 BUG-7 同族），
#:   满血那一版走 `SCENE_WT_CHAPEL__FULL`。状态名由调用方给（`cmds_ast.look` 按面板判），
#:   本模块不认识「血」这件事 —— 它只管「哪条键」。
VARIANT_FULL = "FULL"


def variant_key(base: str, tag) -> str:
    """`<基础槽位>__<状态名大写>` —— 变体槽位的**唯一写法**（P-19 / K65）。

    ★ 与 `content/calendar.py::variant_key` 是**同一个拼法**（那边传的是条件条目 id，
      这边传的是状态名）—— 那边只是转发到这一个函数，别在两处各写一遍 `%s__%s`。
    """
    return "%s__%s" % (str(base), str(tag).upper())


def variant_slot(texts, base: str, tag) -> str | None:
    """基础槽位的变体（表里有这一条、且非空）→ 那个键；没有 ⇒ None（回落基础槽位）。"""
    if not (base and tag):
        return None
    k = variant_key(base, tag)
    rec = texts.get(k)
    if rec and (rec.get("value") or "").strip():
        return k
    return None


def resolve_map(texts, loc):
    """只取地图级（「踏进这张图的第一眼」）—— 取不到回 None。"""
    k = map_key(loc)
    rec = texts.get(k)
    if rec and (rec.get("value") or "").strip():
        return k
    return None


def resolve(texts, loc, node, empty=False, variant=None):
    """节点级 → 地图级 —— 取不到回 None。

    `empty=True`（★ 本波）：先试**人不在那一版**（`SCENE_<节点>_EMPTY`），再退老那一套。
      ★ 空版**不退地图级** —— 退过去就是把「踏进这张图的第一眼」（写着镇子北口那块石头）
        拿来当这一站的近景，正是 P1 BUG-4 / P4 BUG-1 那一族（东口读到「风车在镇子北口」）。
        空版缺位只许退**节点级**（`SCENE_<节点>`）；**节点级也没有 ⇒ 返 `None`**
        （调用方 `cmds_ast._scene_line` 那行有 `【%s · %s】` 占位），不静默给空字符串。
      ⇒ 这就是 `empty` 分支自己走一遍候选、而不是共用下面那个 for 的原因（共用就得带上地图级）。
    `variant`（★ g4-⑤）：**按状态分支**那一档 —— 先试 `SCENE_<节点>__<状态大写>`（例：
      `SCENE_WT_CHAPEL__FULL` 满血那一版），取不到就照老那一套走。状态名由调用方判好传进来。
      ★ 优先级（g4-⑤ 台账 #2 点名、本轮补记）：`empty` > `variant` > 节点级。
      调用方 `cmds_ast.py:832` 两处**同时**为真时以 `empty` 为准 —— 那是 `insert(0, …)` 的直接结果，
      这里写明，不再让它只由调用先后隐式决定。今天两者不同时为真（唯一有变体的 `wt_chapel` 无 `_EMPTY` 槽）。
    """
    keys = [node_key(node)]
    if variant:
        v = variant_slot(texts, node_key(node), variant)
        if v:
            keys.insert(0, v)
    if empty:
        keys.insert(0, empty_key(node))
        # ★ 审计 L2529-1：`empty=True` 时**不把地图级塞进候选**。空版缺位只许退**节点级**
        #   （`SCENE_<节点>`），退到地图级就是拿「踏进这张图的第一眼」当这一站的近景 ——
        #   正是本函数 docstring :93-95 点名、而代码没兑现的那一族（东口读到「风车在镇子北口」）。
        #   宁可回 None：调用方 `cmds_ast._scene_line` 那行有 `【%s · %s】` 占位，不拿宽景充近景。
        for k in keys:
            rec = texts.get(k)
            if rec and (rec.get("value") or "").strip():
                return k
        return None
    keys.append(map_key(loc))
    for k in keys:
        rec = texts.get(k)
        if rec and (rec.get("value") or "").strip():
            return k
    return None
