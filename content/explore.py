# -*- coding: utf-8 -*-
"""《阿斯特兰》探索遇怪 —— 概率与掷骰的**唯一出口**（fxexp · 2026-09-27）

背景（为什么有这一支）
------------------------------------------------------------------
真源 `00_总纲/03_主要玩法.md` 写着「路上：**遇怪**、看见能捡的东西…」，而
`AETHERAN_推进进度.md` P-16 登记「现在遇敌是敲指令打的（`pick_encounter` 由指令触发），
**没有遇见率**」—— 于是世界事件里「遇敌率 / 出现率翻倍」那一类效果**没有消费端**，
`SYS_LOOK_FOE_ROW`（观察那栏的普通怪行）也一直没有读端。

这一支把「遇怪」从**只有战斗指令能触发**扩成**探索也能触发**，并把遇怪率做成一条
**可配、可加权**的真轴（等级差 / 时辰 / 天气 / 世界事件都挂得上）。走路**不掷**
（城镇与同级图保持「走路只位移」），`观察` **不掷**（它是「先看一眼」那条 affordance）。

口径（数值一个都不在本文件里 —— 唯一真源 = `content/rules/explore_encounter.json`）
------------------------------------------------------------------
    p = clamp(base[档] × m_level × m_time × m_weather × m_event, floor, cap)

  · 档     = 站点现取（maps 域节点的 `role` —— 与 `elite.json` 读同一个字段、同一个口）
  · m_level= 玩家等级 − 这一站的基准等级（站基准 = 这一站说得上话的怪里最低的那一级）
  · m_time = 时辰档（calendar 的时辰 id）· m_weather = 天气 id
  · m_event= `calendar.encounter_mul`（`{怪 id: 倍数}` ⇒ 按表里那一档的 `reduce` 收成一个数）
  · cap    = 上限（永远给「掷空」留余地）

**fail-closed（只回「不掷」，与接线前逐字相同）**：表读不到 / 这一站取不到档 / 档位在
表里没有 base / 时辰或天气在表里没有那一格 / 事件那一口给出来的不是正数 —— 一律
`ratio()` 回 `None` ⇒ 调用方**不掷、也不动档**（不建场、不写那格计数）。

掷骰那一口（可复现）
------------------------------------------------------------------
种子 = `uid + 图 + 节点 + 游戏日`（与 `cmds_battle._flee_roll` 同族写法：种子只由**现成的
稳定标识**拼出来，不许 `random.random()` 那种不可复现的口）⇒ 同一个人、同一天、同一站在
**同一份天气/时辰**下掷出来的那一口是**同一个数**（两个进程也一样），探针与「四态」验收
都照这条现算，不靠「跑很多次看比例」。

★ **本批不在档上留任何计数**（设计案 §2.3「不引新状态」+ §四验收 2「掷空 ⇒ 不建场、
不动档」）：掷空那一下**一个字都不写档**。代价与口径都写在 `_notes.md §本批处置 ·
设计决定`：同一站同一天**掷出什么就是什么**（敲十遍也一样，石头剪子布不会因为多敲一次翻面）
—— 「必得一场」的那条路仍然是『攻击』（它本来就必开一场），所以「反复探索刷怪」不成立；
将来若真要「每敲一次换一口手气」，照 `_flee_roll` 的 `nth` 加一维（存在档上）即可。
"""
from __future__ import annotations

import json
import os
import random

from . import calendar as CAL        # 时辰 / 天气 / 世界事件的唯一出口（它不 import 本模块，无环）
from . import affix as AFFIX         # 节点 `role` 的读口（`node_place`，与精英那条同一个口）
#: ★ `combat` **不许在模块级 import**：`combat → panel_build → cmds_ast`（本模块的调用方）
#:   —— 模块级 import 会成环（实测 ImportError: cannot import name 'T'）。用它的地方
#:   （`station_level`，只有一处）本地 import。

#: 概率表（唯一真源）—— 探针把这一格指到别处就能演「表拿掉」那一档，不必真删仓里的文件
RULES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "rules", "explore_encounter.json")

#: 掷骰的种子命名空间（与 `cmds_battle._flee_roll` / `calendar.weather_of` 同一族写法）
_SEED_NS = "aetheran:explore"

_CACHE: dict = {}


def _load(path: str) -> dict:
    if path not in _CACHE:
        with open(path, encoding="utf-8") as f:
            _CACHE[path] = json.load(f)
    return _CACHE[path]


def rules() -> dict:
    """概率表（唯一真源 `rules/explore_encounter.json`）。

    ★ 读不到 ⇒ `{}`（= 没配）—— 消费端见到空表就**不掷**（fail-closed，不猜一个默认率）。
    """
    try:
        return dict(_load(RULES_FILE) or {})
    except Exception:                    # noqa: BLE001 —— 表缺 / 表坏了都是「没配」
        return {}


# ══════════════════════════════════════════════════════════════
# ① 档（站点现取）
# ══════════════════════════════════════════════════════════════
def band_of(loc: str, node: str) -> str:
    """这一站属于哪一档 —— 节点的 `role` 现读（`maps` 域，读口 = `affix.node_place`）。

    取不到（节点不在图里 / 没有 `role` / `role` 不在表里）⇒ 表里的 `band.default`
    （设计案 §2.3「取不到 ⇒ 按野外带」）。表里连 `default` 都没有 ⇒ 空串
    （消费端照「拿不到档」办 —— 不掷）。
    """
    band = rules().get("band") or {}
    role = (AFFIX.node_place(loc, node) or (None, None, None))[0]
    m = band.get("by_node_role") or {}
    if role is not None and str(role) in m:
        return str(m[str(role)])
    return str(band.get("default") or "")


def station_level(ms: dict, loc: str, node: str, level: int):
    """这一站的**基准等级** —— 在这一站说得上话的怪里**最低的那一级**；一只都没有 ⇒ `None`。

    「说得上话的怪」走 `combat.encounter_cand` 那一口（**唯一一处**：遇敌挑选与悬赏轮换池
    都问它）—— 本函数只用它的**全部候选**那一格（`near` 那一格跟玩家等级走，站基准不能跟人走）。
    """
    from . import combat as CB                    # 本地 import：`combat → panel_build → cmds_ast`（成环）
    cand, _near = CB.encounter_cand(ms or {}, loc, node, int(level or 1))
    lvs = [int((ms.get(k) or {}).get("lv", 1) or 1) for k in cand]
    return min(lvs) if lvs else None


def event_mul(st: dict | None = None, p=None):
    """`calendar.encounter_mul` 那一口（`{怪 id: 倍数}`）→ **一个数**（设计案 `m_event`）。

    空表 / 没给 ⇒ 表里的 `m_event.default`（今天 = 1，零变化 —— P-16 那个死轴盘活之前
    与接线前逐字相同）。给了就按表里那一档的 `reduce` 收：`max` = 取被抬得最多的那一个
    （见表里的 `_reduce_note`）。取到的不是正数 ⇒ `None`（fail-closed：不掷）。
    """
    spec = rules().get("m_event") or {}
    raw = CAL.encounter_mul(st, p) or {}
    vals = []
    for v in raw.values():
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return None
        vals.append(float(v))
    if not vals:
        d = spec.get("default")
        return float(d) if isinstance(d, (int, float)) and not isinstance(d, bool) else None
    if str(spec.get("reduce") or "") == "max":
        got = max(vals)
    else:
        return None                      # 表里没写「怎么收」⇒ 不猜（fail-closed）
    return got if got > 0 else None


# ══════════════════════════════════════════════════════════════
# ② 概率（入口 · 纯函数）
# ══════════════════════════════════════════════════════════════
def _num(x):
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def _band_mul(spec: dict, diff: int):
    """等级差落在哪一档（表里的 `bands` 逐条比对；落在表外 ⇒ `None` = 不掷）。"""
    for b in (spec or {}).get("bands") or []:
        lo, hi = _num(b.get("min_diff")), _num(b.get("max_diff"))
        if lo is None or hi is None:
            return None
        if lo <= int(diff) <= hi:
            return _num(b.get("mul"))
    return None


def _table_mul(tbl: dict, key):
    """某一格倍数（`m_time` / `m_weather`）—— 键不在表里 / 不是数 ⇒ `None`（fail-closed）。

    ★ 「键不在表里」也算没配：宁可**这一档不掷**，也不许代码兜底一个「大概 1 倍」——
      那会让「表与代码两处口径」从缝里长出来（K48 那一族）。
    """
    if not isinstance(tbl, dict) or key is None:
        return None
    return _num(tbl.get(str(key)))


def ratio(ms: dict, loc: str, node: str, level: int, st: dict | None = None, p=None):
    """探索在这一站撞上怪的概率（**纯函数**：只现读表与域，一个字都不写）。

    签名照 `affix.elite_of(ms, loc, node, …)` 那一族（域 + 位置 + 等级现取，不另存状态）。
    回 `None` = **不掷**（表缺 / 拿不到档 / 档位或时辰或天气没配 / 这一站一只怪都没有）。
    """
    r = rules()
    if not r:
        return None
    base = r.get("base")
    if not isinstance(base, dict):
        return None
    band = band_of(loc, node)
    b = _num(base.get(band))
    if b is None:
        return None                                   # 拿不到档 ⇒ 不掷
    lv = station_level(ms, loc, node, level)
    if lv is None:
        return None                                   # 这一站没挂怪 ⇒ 不掷（本来也没得打）
    st = st if isinstance(st, dict) else CAL.state()
    m_lv = _band_mul(r.get("m_level") or {}, int(level or 1) - int(lv))
    if m_lv is None:
        return None
    m_t = _table_mul(r.get("m_time") or {}, st.get("hour"))
    if m_t is None:
        return None
    m_w = _table_mul(r.get("m_weather") or {}, st.get("weather"))
    if m_w is None:
        return None
    m_e = event_mul(st, p)
    if m_e is None:
        return None
    cap, floor = _num((r.get("cap") or {}).get("value")), _num((r.get("floor") or {}).get("value"))
    if cap is None or floor is None:
        return None
    out = b                                          # 从 base 起乘（乘法单位元不落在代码里）
    for f in (m_lv, m_t, m_w, m_e):
        out *= f
    return max(floor, min(cap, out))


# ══════════════════════════════════════════════════════════════
# ③ 掷骰（可复现 · 唯一随机口）
# ══════════════════════════════════════════════════════════════
def seed_of(uid, p: dict) -> str:
    """这一手探索的种子 —— `uid : 图 : 节点 : 游戏日`（与 `_flee_roll` 同一族写法）。"""
    day = int((CAL.state() or {}).get("game_day") or 0)
    return "%s:%s:%s:%s:%d" % (_SEED_NS, uid, (p or {}).get("loc") or "",
                               (p or {}).get("node") or "", day)


def roll(uid, p: dict) -> float:
    """这一手探索的手气（`0 ≤ x < 1`）—— ★ 唯一随机口。

    判定只由调用方做（`roll(...) < ratio(...)` 就是撞上）—— 这里不写任何阈值。
    """
    return random.Random(seed_of(uid, p)).random()


# ══════════════════════════════════════════════════════════════
# ④ 掷空的产出（「不空手」）
# ══════════════════════════════════════════════════════════════
def miss_lines(p: dict, st: dict | None = None) -> list:
    """掷空那一下的产出 —— **有拾取点就给拾取提示，没有就通用那句**（设计案 §2.4 三选一①/③）。

    · 拾取点 = 脚下这一站**现成声明**的采集点（`gathering` 域；扫的点走
      `cmds_gather._points_here` 那一口，本函数不自己扫一遍域 —— K65 那一族）。
      提示那一行由**现成槽位** `SYS_SRC_GATHER` 拼（动作词走 `SYS_GATHER_VERB_*`，
      与『出处』那一支同一个形状），外面套一句引子 `SYS_EXPLORE_PICK`。
    · 一个点都没有 ⇒ `SYS_EXPLORE_CLEAR`（「转了一圈 —— 这一带没什么动静。」）。

    本地 import `cmds_ast` / `cmds_gather`：它们要 import 本模块（模块级 import 会成环）。
    """
    from .cmds_ast import T, _name_of_node            # noqa: PLC0415
    from .cmds_gather import _points_here             # noqa: PLC0415
    from . import matsrc as MS                        # noqa: PLC0415（条数上限的唯一真源）
    st = st if isinstance(st, dict) else CAL.state()
    parts = []
    for _gid, pt in sorted(_points_here(p), key=lambda kv: str(kv[0]))[:MS.MAX_SPOT]:
        if not CAL.allows(pt.get("time"), st):
            continue                                  # 整点门槛没过（夜明砂那类）⇒ 不当「有」
        verb = str(pt.get("verb") or "")
        parts.append(T("SYS_SRC_GATHER",
                       verb=T("SYS_GATHER_VERB_%s" % verb.upper()) if verb else "",
                       node=_name_of_node(p["loc"], p["node"]),
                       point=pt.get("name"), times=int(pt.get("times_per_day") or 0)))
    if parts:
        return [T("SYS_EXPLORE_PICK", list=" · ".join(parts))]
    return [T("SYS_EXPLORE_CLEAR")]
