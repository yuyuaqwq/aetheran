# -*- coding: utf-8 -*-
"""场景槽位解析 —— 「观察」与「落域脚本」共用的一个口（B3-6a）

顺序（★ 单一真源，别在两处各写一遍）：
  ① `SCENE_<节点>`  节点级 · 站在这个点上的近景（例：站在拾荒营地）
  ② `SCENE_<地图>`  地图级 · 踏进这张图的第一眼（野外带的到达一屏）
取不到 = None —— 调用方自己决定怎么兜底（**不静默给空字符串**，也不在这里造文案）。

为什么单开一个模块：`scripts/rebuild_scenes.py` 落表时要按同一套规则对账，
  而它不能 import `content.cmds_ast`（那条链会拉起引擎）。所以本模块**零依赖**。
"""


def node_key(node):
    return "SCENE_%s" % str(node).upper()


def map_key(loc):
    return "SCENE_%s" % str(loc).upper()


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
