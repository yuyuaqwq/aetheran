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


def resolve_map(texts, loc):
    """只取地图级（「踏进这张图的第一眼」）—— 取不到回 None。"""
    k = map_key(loc)
    rec = texts.get(k)
    if rec and (rec.get("value") or "").strip():
        return k
    return None


def resolve(texts, loc, node):
    """节点级 → 地图级 —— 取不到回 None。"""
    for k in (node_key(node), map_key(loc)):
        rec = texts.get(k)
        if rec and (rec.get("value") or "").strip():
            return k
    return None
