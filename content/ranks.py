# -*- coding: utf-8 -*-
"""公会评级阶梯 —— **唯一读口**（B4-16）。

为什么单开一个模块（与 `content/town.py` / `content/argv.py` / `content/shop.py` 同一个路子）
------------------------------------------------------------
  · 四处要读同一份口径：`cmds_self.rank`（评级）· `cmds_self.rank_up`（换证）·
    `cmds_quest.quest_mine`（我的委托里那一行评级）· `scripts/probe_ranks.py`（逐条对账）；
  · **代码里没有档名、没有门槛数**：档序与门槛在 `content/rules/ranks.json`
    （`scripts/rebuild_ranks.py` 从真源 `06_…/05_玩法数值口径_v1.md §一` 那一行现解析进来的）；
    档名是文案，住在 `texts` 域（键 = `RANK_<ID>`，`label_key` 是唯一拼法）；
  · 档上那一格 `flags.rank` **只在本模块里读、只在本模块里写**（K74 那一族：同一格档数据
    不许有两处出口）—— 静态守卫见 `scripts/probe_ranks.py` ⑥；
  · 只 import 基座 `cmds_ast`（拿文案口 `T`）—— 不被它们 import，怎么排 import 都不成环。
"""
from __future__ import annotations

import io
import json
import os

from .cmds_ast import T

RULES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules", "ranks.json")

#: 档那一格（档上 flags 里的键）—— 全仓只有本模块碰它
FLAG = "rank"

_CACHE = None


def rules() -> dict:
    """`content/rules/ranks.json`（唯一真源）—— 读一次，进程内复用。"""
    global _CACHE
    if _CACHE is None:
        if not os.path.exists(RULES):
            raise RuntimeError("评级口径表不在：%s（跑 scripts/rebuild_ranks.py）" % RULES)
        with io.open(RULES, encoding="utf-8") as f:
            obj = json.load(f)
        tiers = (obj or {}).get("tiers")
        if not isinstance(tiers, list) or len(tiers) < 2:
            raise RuntimeError("评级口径表形状不对（tiers 至少要两档）：%s" % RULES)
        for i, t in enumerate(tiers):
            if not isinstance(t, dict) or not t.get("id") or int(t.get("order") or 0) != i + 1:
                raise RuntimeError("评级口径表第 %d 档不对（order 必须 1..n）：%r" % (i + 1, t))
            if "need_done" not in t or "need_chief" not in t:
                raise RuntimeError("评级口径表第 %d 档缺门槛：%r" % (i + 1, t))
        _CACHE = obj
    return _CACHE


def ladder() -> list:
    """按档序排好的那几档（order 1..n）。"""
    return list(rules().get("tiers") or [])


def ids() -> list:
    """所有合法档 id（按档序）。"""
    return [str(t["id"]) for t in ladder()]


def label_key(tier_id) -> str:
    """档名槽位的键 = `RANK_<ID>`（形如 `RANK_APPRENTICE`）—— 全仓唯一拼法。"""
    return str(rules().get("label_tpl") or "RANK_%s") % str(tier_id).upper()


def label(tier_id) -> str:
    """档名（文案 · 从 texts 域现取）—— `T()` 缺槽位会当场回显 `[MISSING TEXT: …]`。"""
    return T(label_key(tier_id))


def current(record) -> str:
    """这一档**现在**是哪一档。

    · 档上没那一格（刚办完证）⇒ 第一档（见习）；
    · 档上那一格认不出（老数据 / 手搓档）⇒ **当场喊**（fail-closed，不静默当第一档）。
    """
    got = (record or {}).get("flags") or {}
    tid = got.get(FLAG)
    if not tid:
        return ids()[0]
    if str(tid) not in ids():
        raise RuntimeError("档上那格 flags.%s 认不出：%r（口径表里是 %s）"
                           % (FLAG, tid, ids()))
    return str(tid)


def next_of(tier_id) -> dict:
    """下一档（已经是最后一档 ⇒ None）。"""
    seq = ladder()
    for i, t in enumerate(seq):
        if str(t["id"]) == str(tier_id):
            return seq[i + 1] if i + 1 < len(seq) else None
    raise RuntimeError("认不出的档：%r（口径表里是 %s）" % (tier_id, ids()))


def meets(stats, tier) -> bool:
    """够不够这一档的门槛 —— `stats = {"done": 已交条数, "chief": 打掉的头目数}`。"""
    try:
        return (int(stats.get("done") or 0) >= int(tier.get("need_done") or 0)
                and int(stats.get("chief") or 0) >= int(tier.get("need_chief") or 0))
    except (TypeError, ValueError):
        return False


def set_rank(record, tier_id) -> None:
    """把这一档写进档里（**唯一写口**）。

    ★ 写容器前先拷一层（K57：`_p()` 是浅拷贝，就地改会污染默认档 / 别的玩家）。
    """
    if str(tier_id) not in ids():
        raise RuntimeError("不许写一个认不出的档：%r" % (tier_id,))
    f = dict((record or {}).get("flags") or {})
    f[FLAG] = str(tier_id)
    record["flags"] = f
