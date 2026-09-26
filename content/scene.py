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
#: ★ 这个字面量带 `%s`：`scripts/probe_copy` 的「模板拼出来的键也算被引用」认的是 `"%s_…"` 这种写法
#:   （与 `slot_key` 的 `"SCENE_%s"` 同一手）—— 写成 `+ "_EMPTY"` 会让那一条查不出「谁引用了它」。
EMPTY_SUFFIX = "_EMPTY"


def empty_key(node):
    """节点级 · **人不在那一版**：`SCENE_<节点>_EMPTY`（口径 31_NPC作息 §四「人不在也要有戏」）。

    为什么要在下一版场景：节点级场景是**静态文本**，可这一站的人有作息（哈根只在昏/夜、
    老陶集日被吸去挂板墙）⇒ 画面写「有人在旁边坐着」而名册里一个人都没有，
    玩家照着画面去『搭话』只得到「这儿没有别人」（P1 BUG-5）。空版只在这一站**本该有人、
    此刻一个都没到场**时才用（判定 = `content/town.py::station_empty`）。
    """
    return "%s_EMPTY" % node_key(node)


def resolve_map(texts, loc):
    """只取地图级（「踏进这张图的第一眼」）—— 取不到回 None。"""
    k = map_key(loc)
    rec = texts.get(k)
    if rec and (rec.get("value") or "").strip():
        return k
    return None


def resolve(texts, loc, node, empty=False):
    """节点级 → 地图级 —— 取不到回 None。

    `empty=True`（★ 本波）：先试**人不在那一版**（`SCENE_<节点>_EMPTY`），再退老那一套。
      ★ 空版**不退地图级** —— 退过去就是把「踏进这张图的第一眼」（写着镇子北口那块石头）
        拿来当这一站的近景，正是 P1 BUG-4 / P4 BUG-1 那一族（东口读到「风车在镇子北口」）。
        空版取不到就照老的那一套走（不静默给空字符串）。
    """
    keys = [node_key(node)]
    if empty:
        keys.insert(0, empty_key(node))
    keys.append(map_key(loc))
    for k in keys:
        rec = texts.get(k)
        if rec and (rec.get("value") or "").strip():
            return k
    return None
