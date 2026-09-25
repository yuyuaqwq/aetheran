# -*- coding: utf-8 -*-
"""《阿斯特兰》精英词条消费端（B3-24）—— 抽词条 · 落到战斗 actor 上 · 观察预告。

真源 = `aetheran-plan/06_第一阶段垂直切片/09_精英怪机制_v1.md`（§二 规则 / §三 四类词条 /
§四 配平）· `12_怪物面板与精英词条池_v1.md` §二（每只怪 3 条候选 = `monsters.elite_pool`）。

本文件只做四件事（**引擎零改动**：全部走引擎现成的形状）
--------------------------------------------------------
① 抽：`roll()` —— 按 `elite_pool` 抽词条，**固定种子可复现**；PE ≤ 24 · 同轴不叠 ·
   条数照 09_ §二 的等级档位；**只从 `status=="on"` 的词条里抽**（fail-closed：
   绝不发一条只有名字、没有效果的词条给玩家 —— 未接线的那几条在域里带 `why`）。
② 落：`apply_panel()` / `opening_ct()` / `shields_of()` / `thresholds_of()` / `spawn_plan()`
   / `scale_drops()` —— 面板乘 · 先手 · 开场盾 · 血量阈值 · 多只 · 材料倍数。
   通道名（panel/spawn/opening/threshold/shields/drops）与各条词条的 `mods` 键同值，
   唯一真源是域 + `content/rules/elite.json`，本文件不写内容取值（只写通道名与形状）。
③ 说：`display_name()` / `hint_of()` / `elite_line()` —— 名字与那一行效果**全走 texts 槽位**
   （`COMBAT_ELITE_SPAWN`）；分隔符这类排版骨架也取自 rules（代码里没有汉字文案）。
④ 预告：`elite_of()` —— 这一格、这一天、这个玩家的精英（怪 + 词条）**现算、可复现**；
   观察读它、遭遇也读它 ⇒ 「观察能提前看到」是真的（两处同一个种子）。

★ 概率（09_ §二「按带子深度递增」）与「查不到概率就不刷」的 fail-closed：节点 `role`
  不在 `rate.eligible_node_roles` 里 ⇒ 不刷精英（不兜底成某个数）。
"""
from __future__ import annotations

import hashlib
import json
import os
import random

_RULES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules")
_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_CACHE: dict = {}

#: 词条状态（域里的 ASCII 值）—— 只有 ON 会被抽到。
ST_ON = "on"
ST_PENDING = "pending"

#: 通道名（与域里 `mods` 的键、rules 的 `fx.channels` 同值）
CH_PANEL = "panel"
CH_SPAWN = "spawn"
CH_OPENING = "opening"
CH_THRESHOLD = "threshold"
CH_SHIELDS = "shields"
CH_DROPS = "drops"


class AffixError(Exception):
    """词条数据坏了（键名对不上 / 值不成形状）—— 当场抛，不静默兜底。"""


def _load(path: str) -> dict:
    if path not in _CACHE:
        with open(path, encoding="utf-8") as f:
            _CACHE[path] = json.load(f)
    return _CACHE[path]


def rules() -> dict:
    """口径（PE 表 / 条数档位 / 概率 / 盾值 / 材料倍数 / 分隔符）—— 唯一真源 `rules/elite.json`。"""
    return _load(os.path.join(_RULES_DIR, "elite.json"))


def table() -> dict:
    """词条定义表（`_` 开头的元信息不进表）。"""
    return {k: v for k, v in _load(os.path.join(_DATA_DIR, "monster_affixes.json")).items()
            if not str(k).startswith("_")}


def rec_of(aid: str) -> dict:
    """一条词条 —— 没有这条 id ⇒ 当场抛（悬空 id 不许静默变成「没有词条」）。"""
    t = table()
    if aid not in t:
        raise AffixError("词条 %r 在 monster_affixes 域里没有定义（悬空 id）" % (aid,))
    return t[aid]


def pe_of(aids) -> int:
    return sum(int(rec_of(a).get("pe", 0) or 0) for a in aids or [])


def axes_of(aids) -> set:
    out: set = set()
    for a in aids or []:
        out.update(str(x) for x in (rec_of(a).get("axis") or []))
    return out


# ══════════════════════════════════════════════════════════════
# ① 抽词条（可复现 · PE ≤ 24 · 同轴不叠 · 等级档位）
# ══════════════════════════════════════════════════════════════
def band_of(level: int) -> tuple:
    """这一级的条数区间（09_ §二；出范围 ⇒ 抛，不猜）。"""
    lv = int(level or 1)
    for b in rules()["count_by_level"]["bands"]:
        if int(b["min_lv"]) <= lv <= int(b["max_lv"]):
            return int(b["n_min"]), int(b["n_max"])
    raise AffixError("等级 %r 不在任何条数档位里（09_ §二 只写到 20 级）：先补档位表" % (level,))


def rollable(pool) -> list:
    """池子里**已接线**的那些 id（顺序 = 池子顺序；域里没有的 id ⇒ 抛）。"""
    return [a for a in (pool or []) if rec_of(a).get("status") == ST_ON]


def roll(pool, seed, level: int) -> list:
    """按 `elite_pool` 抽词条 —— **同一个种子两次同结果**。

    规则（逐条对 09_ §二/§四/§六）：
      · 只从 `status=="on"` 里挑（未接线的不发）
      · 目标条数 = 等级档位区间里的一个整数（种子决定取哪个）
      · 逐条挑：**同轴不叠**（与已选的重轴就跳过）·`PE` 累计不得越过上限
      · 池子里可挑的不够 ⇒ 抽到多少算多少（不拿未接线的凑数 —— 这是 fail-closed 那一面）
    """
    rnd = random.Random(seed)
    cand = rollable(pool)
    if not cand:
        return []
    n_min, n_max = band_of(level)
    want = n_min if n_max <= n_min else rnd.randint(n_min, n_max)
    cap = int(rules()["pe_cap"]["value"])
    order = list(cand)
    rnd.shuffle(order)
    out: list = []
    used_axes: set = set()
    used_pe = 0
    for aid in order:
        if len(out) >= want:
            break
        rec = rec_of(aid)
        ax = set(str(x) for x in (rec.get("axis") or []))
        if ax & used_axes:
            continue
        if used_pe + int(rec.get("pe", 0) or 0) > cap:
            continue
        out.append(aid)
        used_axes |= ax
        used_pe += int(rec.get("pe", 0) or 0)
    return out


# ══════════════════════════════════════════════════════════════
# ② 落到 actor 上（四条通道；每条都只读域里声明的值）
# ══════════════════════════════════════════════════════════════
def _mods(aids, channel: str) -> list:
    """这一组词条里所有带 `channel` 的 mods（保序）。"""
    out = []
    for a in aids or []:
        m = (rec_of(a).get("mods") or {}).get(channel)
        if isinstance(m, dict):
            out.append((a, m))
    return out


def apply_panel(panel: dict, aids, mid: str = "") -> dict:
    """面板乘（改数值那一类）—— 在**域那一套键名**上乘（`content/combat.monster_actor` 换名之前）。

    键不在面板里 ⇒ 抛（与 `party_scale_of` 同一条 fail-closed 纪律：键名对不上不许静默当 1）。
    顺序：按词条序逐条乘、逐条取整（复算口径 = 同样顺序、同样取整）。
    """
    out = dict(panel or {})
    known = set(rules()["panel_keys"]["keys"])
    for aid, m in _mods(aids, CH_PANEL):
        for k, v in m.items():
            if k not in known:
                raise AffixError("词条 %s 的面板键 %r 不在 rules 的面板键名单里" % (aid, k))
            if k not in out:
                raise AffixError("词条 %s 要乘的面板键 %s 不在 %s 的 panel 里（键名对不上不静默）"
                                 % (aid, k, mid or "这只怪"))
            out[k] = int(round(float(out[k]) * float(v)))
    return out


def opening_ct(aids):
    """先手（改行为 潜伏）：它第一动的绝对时刻 —— 没有就回 None（= 不动引擎播种）。"""
    got = _mods(aids, CH_OPENING)
    if not got:
        return None
    return float(got[0][1].get("ct", 0))


def shields_of(aids, max_hp: int) -> dict:
    """开场盾（改机制 护盾）：盾值 = 生命上限 × rules 的比例（真源未给数那一条）。"""
    got = _mods(aids, CH_SHIELDS)
    if not got:
        return {}
    pct = float(rules()["shield_pct_of_hp"]["value"])
    val = max(1, int(round(float(max_hp) * pct)))
    return {aid: {"value": val} for aid, _m in got}


def thresholds_of(aids) -> list:
    """血量阈值（改行为 狂暴）：[(词条 id, 阈值 dict)] —— 消费端 = `combat` 的导演钩子。"""
    return [(aid, m) for aid, m in _mods(aids, CH_THRESHOLD)]


def spawn_plan(mid: str, aids) -> tuple:
    """多只（改行为 群居）：`([怪 id...], [每只的生命倍数])` —— 没有就打一只（倍数全 None）。"""
    got = _mods(aids, CH_SPAWN)
    if not got:
        return [mid], [None]
    sp = rules()["spawn"]
    n = int(sp["n"])
    half = int(sp["half_hp_index"])
    mult = float(sp["hp_mult"])
    ids = [mid] * n
    mults = [mult if i == half else None for i in range(n)]
    return ids, mults


def scale_drops(drops, aids) -> list:
    """材料倍数（09_ §四 按 PE 等比上调 + 富饶 的「材料翻倍」）。

    倍数 = (1 + PE × material_drop_mult.per_pe) × Π(命中那几条的 drops.mult)
    —— 只乘命中那一类（`drops.kind_key`）；一件都没命中 ⇒ 原样返回（不动 `n`）。
    """
    base = float(rules()["material_drop_mult"]["base"]) + \
        pe_of(aids) * float(rules()["material_drop_mult"]["per_pe"])
    per_kind: dict = {}
    for _aid, m in _mods(aids, CH_DROPS):
        kk = str(m.get("kind_key") or "")
        per_kind[kk] = per_kind.get(kk, 1.0) * float(m.get("mult", 1) or 1)
    if not per_kind and abs(base - 1.0) < 1e-9:
        return list(drops or [])
    out = []
    for d in (drops or []):
        e = dict(d)
        m = per_kind.get(str(e.get("kind_key") or ""))
        if m is None:
            out.append(e)
            continue
        e["n"] = max(1, int(round(float(e.get("n", 1) or 1) * base * m)))
        out.append(e)
    return out


# ══════════════════════════════════════════════════════════════
# ③ 名字与那一行（全部走 texts 槽位；代码不写文案）
# ══════════════════════════════════════════════════════════════
def display_name(mon_name: str, aids) -> str:
    """`† 硬壳的田鼠 †` —— 走槽位 `COMBAT_ELITE_SPAWN`（名字 + hint 两行一起给）。

    没有词条 ⇒ 原样回怪名（= 与接线前逐字相同）。
    """
    return mon_name if not aids else _spawn_line(mon_name, aids)[0]


def _spawn_line(mon_name: str, aids) -> tuple:
    """(名字那一行, hint 那一行) —— 槽位 `COMBAT_ELITE_SPAWN` 的渲染结果按行拆。"""
    from .cmds_ast import T
    lab = rules()["label"]
    names = [str(rec_of(a).get("name") or a) for a in aids]
    lines = [str((rec_of(a).get("line") or "")).strip() for a in aids]
    hint = str(lab["line_sep"]).join(x for x in lines if x)
    s = T("COMBAT_ELITE_SPAWN", affix=str(lab["sep"]).join(names), name=mon_name, hint=hint)
    parts = str(s).split("\n")
    return parts[0], (parts[1] if len(parts) > 1 else "")


def elite_line(mon_name: str, aids) -> str:
    """观察 / 遭遇那两行（名字行 + 一句话效果）—— 逐字取自槽位。"""
    return "\n".join(x for x in _spawn_line(mon_name, aids) if x)


def hint_of(aids) -> str:
    """那一行效果（词条自己的 `line` 拼起来 —— 域里的话，不是代码里的话）。"""
    lab = rules()["label"]
    return str(lab["line_sep"]).join(
        str(rec_of(a).get("line") or "").strip() for a in aids or [] if rec_of(a).get("line"))


# ══════════════════════════════════════════════════════════════
# ④ 这一格 · 这一天 · 这个玩家的精英（观察预告 = 遭遇，同一个种子）
# ══════════════════════════════════════════════════════════════
def seed_of(uid: str, loc: str, node: str, game_day) -> int:
    """（玩家 · 图 · 节点 · 游戏日）→ 种子。

    ★ 用 sha1 不用内置 hash：内置 hash 每进程加盐 ⇒ 换一次运行就不一样（预告会骗人）。
    """
    raw = "affix|%s|%s|%s|%s" % (uid, loc, node, game_day)
    return int(hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12], 16)


def rate_of(node_role: str, idx: int, total: int):
    """这一格出精英的概率（09_ §二）—— 不在名单里的档位 ⇒ **None = 不刷**（fail-closed）。"""
    r = rules()["rate"]
    if str(node_role) not in [str(x) for x in r["eligible_node_roles"]]:
        return None
    t = r["by_node_index"]
    if total <= 1 or idx <= 0:
        return float(t["first"])
    if idx >= total - 1:
        return float(t["last"])
    return float(t["middle"])


def maps() -> dict:
    """地图域（只读节点 `role` 与节点序 —— 概率靠它分档，不另造深度字段）。"""
    return _load(os.path.join(_DATA_DIR, "maps.json"))


def node_place(loc: str, node: str) -> tuple:
    """`(节点的 role, 节点在本图里的序号, 本图节点数)`；查不到 ⇒ `(None, None, None)`。"""
    m = (maps() or {}).get(loc) or {}
    nodes = [str(n.get("id")) for n in (m.get("nodes") or [])]
    if str(node) not in nodes:
        return None, None, None
    i = nodes.index(str(node))
    role = next((n.get("role") for n in (m.get("nodes") or []) if str(n.get("id")) == str(node)), None)
    return role, i, len(nodes)


def elite_of(monsters: dict, loc: str, node: str, uid: str, game_day, level: int,
             node_role=None, node_index=None):
    """这一格今天的精英 → `(怪 id, [词条 id...])`；不出 ⇒ `None`。

    候选与 `content.combat.pick_encounter` 同一套规则（`habitat` 说得上话的怪），
    等级就近取前 3 只（同一顺序）—— 这样「观察看到的」与「打起来遇到的」是同一个东西。
    节点档位（`role` / 序号）不传就现读 `maps` 域（唯一真源，不另造深度字段）。
    """
    if node_role is None or node_index is None:
        node_role, i, total = node_place(loc, node)
        node_index = (i, total)
    if node_role is None or node_index[0] is None:
        return None
    r = rate_of(node_role, int(node_index[0]), int(node_index[1]))
    if r is None:
        return None
    cand = []
    for k, m in monsters.items():
        hb = m.get("habitat") or {}
        if loc not in (hb.get("maps") or []):
            continue
        ns = hb.get("nodes") or []
        if ns and node not in ns:
            continue
        cand.append(k)
    if not cand:
        return None
    rnd = random.Random(seed_of(uid, loc, node, game_day))
    if rnd.random() >= r:
        return None                                   # 今天这一格不刷精英（与概率表同种子）
    cand.sort(key=lambda k: abs(int(monsters[k].get("lv", 1)) - int(level)))
    top = cand[:3]
    mid = rnd.choice(top)
    aids = roll(monsters[mid].get("elite_pool") or [], rnd.randint(0, 2 ** 31), monsters[mid].get("lv", 1))
    if not aids:
        return None                                   # 池子里一条都没接线 ⇒ 不硬发（见 roll）
    return mid, aids


def coverage(monsters: dict) -> dict:
    """覆盖快照（判据用 · 只许变长）：有池子的怪里，池子至少含一条 on 词条的只数。"""
    tot = 0
    ok = []
    bad = []
    for k, m in monsters.items():
        pool = m.get("elite_pool") or []
        if not pool:
            continue
        tot += 1
        (ok if rollable(pool) else bad).append(k)
    return {"total": tot, "ok": sorted(ok), "bad": sorted(bad)}
