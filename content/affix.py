# -*- coding: utf-8 -*-
"""《阿斯特兰》精英词条消费端（B3-24）—— 抽词条 · 落到战斗 actor 上 · 观察预告。

真源 = `aetheran-plan/06_第一阶段垂直切片/09_精英怪机制_v1.md`（§二 规则 / §三 四类词条 /
§四 配平）· `12_怪物面板与精英词条池_v1.md` §二（每只怪 3 条候选 = `monsters.elite_pool`）。

本文件只做四件事（**引擎零改动**：全部走引擎现成的形状）
--------------------------------------------------------
① 抽：`roll()` —— 按 `elite_pool` 抽词条，**固定种子可复现**；PE ≤ 24 · 同轴不叠 ·
   条数照 09_ §二 的等级档位；**只从 `status=="on"` 的词条里抽**（fail-closed：
   绝不发一条只有名字、没有效果的词条给玩家 —— 未接线的那几条在域里带 `why`）。
② 落：`apply_panel()` / `opening_ct()` / `shield_entries_of()` / `thresholds_of()` / `spawn_plan()`
   / `scale_drops()` —— 面板乘 · 先手 · 开场盾 · 血量阈值 · 多只 · 材料倍数。
   通道名（panel/spawn/opening/threshold/shields/drops）与各条词条的 `mods` 键同值，
   唯一真源是域 + `content/rules/elite.json`，本文件不写内容取值（只写通道名与形状）。
   ★ 状态容器收口第 2 批（2026-09-28）：开场盾由 `shields_of()`（旧 `shields` 容器那一格）
   改成 **`shield_entries_of()`**（**状态容器里那条声明为吸收型的条目** —— 键由
     `rules/elite.json::absorb.state_key` 声明，见 `content/absorb.py`）。
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


def _material_key() -> str:
    """判定「这一格是不是材料」用的机器键 —— 真源 `content/loot.py::K_MATERIAL_KEY`
    （与 `items.schema.json` 的 `kind_key` enum 同值）。

    ★ 取值**不在本模块新写**：局部取那一口（`matsrc` / `elite_of` 同一写法），
      免得同一份 ASCII 键在两处各存一份、将来分叉无处可查。
    """
    from .loot import K_MATERIAL_KEY                # noqa: PLC0415
    return str(K_MATERIAL_KEY)


#: 赋值一次（`scale_drops` 每格都要比，用函数调用会重复 import）
_MATERIAL_KEY = _material_key()


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
    """开场盾（改机制 护盾）—— 盾值 = 生命上限 × rules 的比例（真源未给数那一条）。

    ★ **状态容器收口第 2 批（2026-09-28 · 设计案 §2.2）**：这个**返回 `shields` 容器那一格**
      的函数已经**退役** —— 引擎要删掉 `shields` 容器，护盾变成「状态容器里一条带 `value` 的
      条目」。新的消费端是 `shield_entries_of()`（返回 `{状态键: 盾值}`，由
      `content/combat.py` 走 `content/absorb.py::open_shield` 落进容器）。
      ★ 留这一个函数**只当旧形状的回读口**（判据与旧存档对账用），**新代码不许调它**
        —— 新写口一律 `shield_entries_of()`。
    """
    got = _mods(aids, CH_SHIELDS)
    if not got:
        return {}
    pct = float(rules()["shield_pct_of_hp"]["value"])
    val = max(1, int(round(float(max_hp) * pct)))
    return {aid: {"value": val} for aid, _m in got}


def shield_entries_of(aids, max_hp: int) -> dict:
    """★ 状态容器收口第 2 批：开场盾 → **`{容器条目键: 盾值}`**（旧 `shields_of` 的新形状）。

    ★ **条目键由 rules 声明**（`rules/elite.json` 的 `absorb` 那一块），不是拿词条 id 当键 ——
      引擎判「吸收型」问的是**声明**（`EFFECT_RULES[键].absorb`），不是「键名里有没有 shield」。
      词条 id 仍留在 `mods.shields` 里做**声明与对账**（哪条词条发了盾），只是不再兼当容器键。
    ★ 盾值口径与旧 `shields_of` **逐字相同**（生命上限 × `shield_pct_of_hp`）⇒ 数值零变化。
    """
    got = _mods(aids, CH_SHIELDS)
    if not got:
        return {}
    pct = float(rules()["shield_pct_of_hp"]["value"])
    val = max(1, int(round(float(max_hp) * pct)))
    key = str(rules().get("absorb", {}).get("state_key") or "")
    if not key:
        raise AffixError(
            "精英词条要发开场盾，但 rules/elite.json 的 `absorb.state_key` 是空的"
            "（容器里那一格叫什么都没声明 ⇒ 不猜）")
    return {key: val}


def thresholds_of(aids) -> list:
    """血量阈值（改行为 狂暴）：[(词条 id, 阈值 dict)] —— 消费端 = `combat` 的导演钩子。"""
    return [(aid, m) for aid, m in _mods(aids, CH_THRESHOLD)]


def reward_of(aids) -> dict:
    """★ P3 BUG-3（本波 f4）：精英那一场的**钱 / 经验 / 掉落轮数** —— 三格都在 `rules/elite.json::reward`。

    病根：原先 `_settle` 里那一档比的是**怪自己的 `role_key`**（`elite` / `chief` …），
    而词条精英（`† 群居的田鼠 †`）`role_key` 仍是 `normal` ⇒ 打 3 只精英与打 1 只普通怪
    钱/经验一字不差 —— 精英成了纯亏（真源 `09_ §六③` 明写「精英奖励只多 40–50%」）。
    ⇒ 这一格由**词条在不在**说话（`affixes` 非空 = 这一场是精英），不看 `role_key`
    （`role_key` 那一档照旧管**精英档怪**，两条路各管各的）。

    没词条 ⇒ 全 1（= 与接线前逐字相同）。
    """
    if not aids:
        return {"gold_mult": 1.0, "exp_mult": 1.0, "drop_rounds": 1}
    r = rules().get("reward")
    if not isinstance(r, dict):
        raise AffixError("精英口径表缺 `reward` 那一块：%s"
                         % os.path.join(_RULES_DIR, "elite.json"))
    return {"gold_mult": float(r["gold_mult"]),
            "exp_mult": float(r["exp_mult"]),
            "drop_rounds": int(r["drop_rounds"])}


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

    倍数分两段，各自带自己的适用范围（★ 台账 L1148）：

    | 段 | 乘到哪一档 | 什么时候生效 |
    |---|---|---|
    | `base` = 1 + PE×`per_pe` | **材料**（`loot.K_MATERIAL_KEY`） | **无条件** —— 有 PE 就有 |
    | `m` = Π(命中那几条的 `drops.mult`) | 词条点名的 `kind_key` | 词条带 `drops` 通道才生效 |

    ★ 为什么必须拆开（原先两段挂在同一个 `if` 的两端）：`base` 算完之后只在
      `per_kind` 命中时才被用上 ⇒ **一条不带 `drops` 通道的精英拿不到任何 PE 加成**。
      实跑材料 10 份 / PE=20（`per_pe` = 1/48 ⇒ 期望 14）得到 **10**，一字不差，
      不报错、不留痕；全表只有 `af_bountiful` 带 `drops` 通道，而它自己 `pe=0`
      ⇒ 这一整段从上线起就没跑过。

    其余档（装备 / 杂物 / 未鉴定）**只吃 `per_kind`**，与真源逐字对齐 ——
    真源 `_src` 明写「精制装备掉率那半（1+PE/60）落在**掉落池权重**那一层，本批未接线」
    ⇒ 那一半**继续不接线**（不扩面），本函数只把真源声明为已接线的「材料那半」接上。
    """
    base = float(rules()["material_drop_mult"]["base"]) + \
        pe_of(aids) * float(rules()["material_drop_mult"]["per_pe"])
    per_kind: dict = {}
    for _aid, m in _mods(aids, CH_DROPS):
        kk = str(m.get("kind_key") or "")
        # ★ L246 同族：mult=0.0 是**合法**配置（该档不掉落），而 `0.0 or 1` 会被吞成 1
        #   ⇒ 先取原值，只有 None（真源没写）才回落 1.0。缺键语义不变。
        _mv = m.get("mult")
        _mf = 1.0 if _mv is None else float(_mv)
        per_kind[kk] = per_kind.get(kk, 1.0) * _mf
    if not per_kind and abs(base - 1.0) < 1e-9:
        return list(drops or [])
    out = []
    for d in (drops or []):
        e = dict(d)
        kk = str(e.get("kind_key") or "")
        # 材料那档吃 base（无条件）；其余档只吃 per_kind —— 缺档 = 1.0 = 原样不动 n。
        m = per_kind.get(kk)
        if kk == _MATERIAL_KEY:
            m = base * (m if m is not None else 1.0)
        elif m is None:
            out.append(e)
            continue
        e["n"] = max(1, int(round(float(e.get("n", 1) or 1) * m)))
        out.append(e)
    return out


# ══════════════════════════════════════════════════════════════
# ── 「句末那一枚标点」的认词表（★ g4-⑥）─────────────────────────────
#: 拼接前要摘掉的**句末**标点（只摘末尾一枚；行内的 `——` / `、` 一个字不动）。
#: 为什么在代码里也留一份：这是**排版**（句末标点摘掉，末尾由表里的 `line_end` 补一枚），
#: 不是文案；真正的「用哪一枚」仍然只在 `content/rules/elite.json` 的 `label.line_end`。
_END_MARKS = "。！？…；·"


# ── ③ 名字与那一行（全部走 texts 槽位；代码不写文案）
# ══════════════════════════════════════════════════════════════
def display_name(mon_name: str, aids) -> str:
    """`† 硬壳的田鼠 †` —— 走槽位 `COMBAT_ELITE_SPAWN`（名字 + hint 两行一起给）。

    没有词条 ⇒ 原样回怪名（= 与接线前逐字相同）。
    """
    return mon_name if not aids else _spawn_line(mon_name, aids)[0]


def _join_lines(lines, lab) -> str:
    """几条词条的 `line` → 一行效果（★ g4-⑥：句末那一枚标点只留一枚）。

    实机原状（p2/p3 报告 + fix2 §七5 顺手核到）：`af_frenzy` 那句自带句号，用 `line_sep`（`；`）
    接上 `af_swarm` ⇒ 屏幕上成了「…它下手更重。；它身后还有两只…」（**多一枚标点**）。
    口径：每条各自的**句末标点先摘掉**（`_END_MARKS`），用 `line_sep` 连起来，末尾补**一枚**
    `label.line_end`（表里的值，不是代码里写死的中文）。只摘句末那一枚 ——
    `——` 这种行内停顿一个字不动（`af_swarm` 那句的破折号照旧）。
    """
    parts = [str(x).strip() for x in (lines or []) if str(x).strip()]
    if not parts:
        return ""
    end = str(lab.get("line_end") or "")
    marks = _END_MARKS
    parts = [p[:-1] if p and p[-1] in marks else p for p in parts]
    return str(lab["line_sep"]).join(parts) + end


def _spawn_line(mon_name: str, aids) -> tuple:
    """(名字那一行, hint 那一行) —— 槽位 `COMBAT_ELITE_SPAWN` 的渲染结果按行拆。"""
    from .cmds_ast import T
    lab = rules()["label"]
    names = [str(rec_of(a).get("name") or a) for a in aids]
    hint = _join_lines([rec_of(a).get("line") for a in aids], lab)
    s = T("COMBAT_ELITE_SPAWN", affix=str(lab["sep"]).join(names), name=mon_name, hint=hint)
    parts = str(s).split("\n")
    return parts[0], (parts[1] if len(parts) > 1 else "")


def elite_line(mon_name: str, aids) -> str:
    """观察 / 遭遇那两行（名字行 + 一句话效果）—— 逐字取自槽位。"""
    return "\n".join(x for x in _spawn_line(mon_name, aids) if x)


def hint_of(aids) -> str:
    """那一行效果（词条自己的 `line` 拼起来 —— 域里的话，不是代码里的话）。"""
    return _join_lines([rec_of(a).get("line") for a in aids or []], rules()["label"])


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


def no_elite_at(loc: str, node: str) -> bool:
    """这一格**不许**刷精英（`rules/elite.json` 的 `rate.no_elite_nodes`）。

    ★ 真源 `09_ §六②` 的对策写着「精英不出现在新手带第一个节点」，而 `09_ §二` 的概率表写着
      「第一节点 8%」—— 两处打架（`rules/elite.json` 的 `_conflict_note` 记着上一批照表办）。
      P3 试玩复证（全新玩家 · 2026-09-26）：1 级在骨田撞上「† 群居的田鼠 †」（一包 3 只）必败、
      而且**当天那一格反复是它**（种子含 `game_day`）⇒ 真源那两条里选**对策**：
      只摘名单里这一格，其余档位（8% / 12% / 20%）一概不动。已登记真源行，待主线裁。
    """
    r = rules()["rate"]
    for e in (r.get("no_elite_nodes") or []):
        if str(e.get("map")) == str(loc) and str(e.get("node")) == str(node):
            return True
    return False


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
    if no_elite_at(loc, node):
        return None                                   # ★ 09_ §六② 的对策：新手带第一节点不刷精英
    r = rate_of(node_role, int(node_index[0]), int(node_index[1]))
    if r is None:
        return None
    # ★ 审计 B2 收口（台账 L1148 同族的另一半面）：候选 + 等级就近 top-3 这一段
    #   原先在这里内联一份，而 `content/combat.encounter_cand` 的抬头明写
    #   「两处共用这一处（**同一把尺子**）…… 两处要回答的是同一件事；各写一份 = 迟早对不上」。
    #   ⇒ 这一份就是那个「迟早对不上」的第二份：**零判据钉着它**。
    #   今天实跑两者逐条同值（8 组样本：不同等级 × 不同域内键序）⇒ 属潜伏项，
    #   但承诺是「同一把尺子」，不是「今天恰好一样」⇒ 收成单源。
    #   循环 import：`content/combat.py:23` 就 `from . import affix as AFFIX`
    #   ⇒ 顶层 import 会成环，用仓内既有的函数内 import 惯例（同本文件 :58 / :366）。
    from .combat import encounter_cand                # noqa: PLC0415
    _all_cand, top = encounter_cand(monsters, loc, node, level, keep=3)
    if not top:
        return None
    rnd = random.Random(seed_of(uid, loc, node, game_day))
    if rnd.random() >= r:
        return None                                   # 今天这一格不刷精英（与概率表同种子）
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
