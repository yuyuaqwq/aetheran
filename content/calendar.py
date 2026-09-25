# -*- coding: utf-8 -*-
"""《阿斯特兰》时辰与天气 —— `calendar` / `weather` 两域的**唯一出口**。

口径（全在表里，本模块不写死数值、不写死中文）：
  · 游戏日长度 = `calendar._clock.real_seconds_per_game_day`（源：05_玩法数值口径 §七）
  · 时辰窗界 = `calendar.hr_*` 的 from/to 小时；中文名 = **texts 域**的 `HOUR_*` / `WEATHER_*`
  · 天气 = 纯函数 `游戏日 → 天气`（按 `weather.w_*.weight` 抽；稳定哈希 ⇒ 全服一致、跨进程可复现）
    ★ 保底（B4-3 · 台账 ⏸ P-5）：连续 `weather._rules.rain_max_gap_days` 个游戏日内**至少一场雨** ——
      往前那几天都没雨时把今天定成雨（只加雨、不动 weight、不存历史）。不带保底的那一层 = `weather_raw()`。
  · 世界事件（B3-5）= `events` 域的三尺度判定（世界 / 限时 / 每日）—— `event_on` / `events_now`；
    它们也是「现在」的判断，所以与时辰/天气同一个口（别处不许自己算 —— K65 家族）

★ 三条纪律：
  ① 本模块是包内「现在什么时辰 / 今天什么天气」的唯一出口 —— 别处不许自己算
     （引擎口径：玩法层不自己取钟；钟源由宿主注入，取件走 `facade.clock()`）。
  ② 名字只在 texts 域；这里只传槽位、只回槽位的值（缺槽位 = 抛，不静默给空名）。
  ③ 档上只记「见过的游戏日」（`day`）—— 时辰/天气**现算不缓存**（缓存 = 双源，改刻度就不同步）。
"""
from __future__ import annotations

import hashlib
import json
import os

from . import facade

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_C: dict = {}
_NAME_MAP = None


# ── 读表 ──────────────────────────────────────────────────────
def _d(name: str):
    if name not in _C:
        with open(os.path.join(_DIR, name + ".json"), encoding="utf-8") as f:
            _C[name] = json.load(f)
    return _C[name]


def _entries(dom: str) -> dict:
    """域里的条目（`_` 前缀 = 私有键，不是条目 —— 与编辑器/装载器同口径）。"""
    return {k: v for k, v in _d(dom).items() if not str(k).startswith("_")}


def hours() -> dict:
    return _entries("calendar")


def weathers() -> dict:
    return _entries("weather")


def clock_meta() -> dict:
    return dict(_d("calendar").get("_clock") or {})


def scale_seconds() -> int:
    """现实多少秒 = 游戏内一天（★ 调时间快慢只改表里这一个数）。"""
    sec = int(clock_meta().get("real_seconds_per_game_day") or 0)
    if sec <= 0:
        raise ValueError("calendar._clock.real_seconds_per_game_day 缺失或非正 —— 表是唯一真源")
    return sec


def _slot_text(key: str) -> str:
    rec = (_d("texts") or {}).get(key)
    if not rec:
        raise KeyError("texts 域缺槽位 %r（名字与风味的真源都在 texts）" % key)
    return rec.get("value", "")


def name(eid: str) -> str:
    """条目 id → 中文名（= 文案槽位的值）。"""
    e = hours().get(eid) or weathers().get(eid)
    if not e:
        raise KeyError("calendar/weather 域里没有条目 %r" % eid)
    return _slot_text(e["slot"])


def desc_slot(eid: str) -> str:
    """条目 id → 风味文案的槽位名（代码只传槽位）。"""
    e = hours().get(eid) or weathers().get(eid) or {}
    return e.get("desc_slot") or ""


# ── 现在是几时 ────────────────────────────────────────────────
def day_key(day: int) -> str:
    """游戏日 → 周期键（天气/日刷新的 key；与档里的 `day` 同源）。"""
    return "g%08d" % int(day)


def _epoch(epoch=None) -> float:
    if epoch is not None:
        return float(epoch)
    return float(facade.clock())


def game_time(epoch=None):
    """→ (游戏日, 游戏内当日小时[0,24))。刻度在表里。"""
    g = _epoch(epoch) * (86400.0 / scale_seconds())
    return int(g // 86400), (g % 86400) / 3600.0


def hour_at(hod: float) -> str:
    """游戏内小时 → 时辰 id（窗界支持跨零点，如 夜 20→5）。"""
    for hid, h in sorted(hours().items(), key=lambda kv: int(kv[1]["from_hour"])):
        a, b = int(h["from_hour"]), int(h["to_hour"])
        if (a <= hod < b) if a < b else (hod >= a or hod < b):
            return hid
    raise ValueError("时辰表没盖住 %r 点 —— 表错了（探针会拦）" % hod)


def rain_max_gap_days() -> int:
    """★ 天气保底的天数 N（`weather._rules.rain_max_gap_days`）—— **表是唯一真源，代码不写数**。

    「连续 N 个游戏日内至少一场雨」；缺这一格 / 不是 ≥1 的整数 = 抛（fail-closed：
    保底是玩法承诺，静默取消会比报错更糟）。取数口径见 `content/rules/calendar.json`。
    """
    n = (weathers_meta().get("rain_max_gap_days"))
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError("weather._rules.rain_max_gap_days 缺失或不是 ≥1 的整数：%r —— 表是唯一真源" % (n,))
    return n


def weathers_meta() -> dict:
    """`weather._rules`（私有块 · 权重来源 / 保底 / 季节与地图那几条说明）。"""
    return dict(_d("weather").get("_rules") or {})


def weather_raw(day: int) -> str:
    """游戏日 → 天气 id（**表格抽签那一层**：权重 + 稳定哈希，**不含保底**）。

    ★ 单独留着这一层是为了对账：分布与权重逐日一致这件事由它担保（`probe_weather ⑦`），
      保底则是在它上面「只加雨」（`probe_weather ⑧⑨`）。玩法层一律走 `weather_of`。
    """
    w = weather_weights(day)
    if not w:
        raise ValueError("weather 域是空的")
    total = sum(w.values())
    h = hashlib.md5(("aetheran:weather:" + day_key(day)).encode("utf-8")).hexdigest()
    r = int(h[:8], 16) % total
    acc = 0
    for wid in sorted(w):                        # 顺序固定（id 升序）⇒ 可复现
        acc += int(w[wid])
        if r < acc:
            return wid
    return sorted(w)[-1]


def weather_of(day: int) -> str:
    """游戏日 → 天气 id（★ 唯一出口：表格抽签 + 天气保底）。

    ★ 权重走 `weather_weights(day)`（表里的 weight 再叠开场事件的 `weather_mul` ——
      初雪那 3 天里「初雪」的窗变宽；没有事件时与表逐字相同）。
    ★ 保底（`weather._rules.rain_max_gap_days` = N）：「连续 N 个游戏日内至少一场雨」
      ⇒ 连着 N−1 天没有雨的那个第 N 天，定成雨。于是**最长连续无雨 = N−1 天**
      （等雨最长 N−1 天 —— 支线 4「雨后的东西」那类挂在板上的线等得起；B4-3 · 台账 ⏸ P-5）。
    ★ 怎么现算（★ 纯函数、不存历史 —— 没有第二个源，改刻度不会不同步）：
      从今往回找**最近一次「表格抽签就是雨」的那天 r**（保底补出来的雨只用来看计数，
      不必再往前追），从 r 起重数 ⇒ `(day − r) % N == 0` 就是雨（`r` 那天本身 + 之后每 N 天补一场）。
      等价写法 = 递推「往前 N−1 天（算上保底）都没有雨 ⇒ 今天雨」—— 探针两支逐日对照
      （`scripts/probe_weather.py` ⑥），不是两处口径。
    ★ 只加雨：不碰 weight、不删别的天气（`weather_raw` 那一层与权重逐日一致）。
    """
    n = rain_max_gap_days()
    r = int(day)
    while weather_raw(r) != "w_rain":         # 最近一次「抽签就是雨」的日子（伪随机 ⇒ 实际几天的量级）
        r -= 1
    if (int(day) - r) % n == 0:
        return "w_rain"
    return weather_raw(day)


def weather_weights(day: int) -> dict:
    """这一天各天气的权重（表里的 weight × 开场事件的 `weather_mul`）—— 只归一处。

    ★ 天气是**全服一天一张**（不跟人走）⇒ 世界级事件（看主线）不参与加权；
      只有按游戏日算的窗（限时 / 每日）能影响天气。没有这类事件时 = 表里的数原样。
    """
    out = {wid: int(v["weight"]) for wid, v in weathers().items()}
    st = {"game_day": int(day)}
    for eid, rec in sorted(events().items()):
        per = rec.get("period") or {}
        if "from_main" in per or "until_main" in per:
            continue
        if not _on(eid, rec, st, None):
            continue
        for wid, mul in ((rec.get("effects") or {}).get("weather_mul") or {}).items():
            if wid in out:
                out[wid] = int(out[wid]) * int(mul)
    return out


def state(epoch=None) -> dict:
    """此刻的时辰与天气（★ 唯一出口）。`epoch` 省略 = 宿主注入的钟。"""
    day, hod = game_time(epoch)
    hid, wid = hour_at(hod), weather_of(day)
    return {"game_day": day, "day_key": day_key(day), "hour_of_day": round(hod, 3),
            "hour": hid, "hour_name": name(hid),
            "weather": wid, "weather_name": name(wid)}


def day_now(epoch=None) -> int:
    """此刻是**第几个游戏日**（★ 唯一口）—— 档上那些「日期戳」（图鉴 / 称号 / 彩蛋 /
    听过什么 / 记录的游戏日）一律走它。

    ★ B4-9：**别读档上那一格 `p["day"]`**。那一格只是 `tick()` 留下的**跨日标记**
      （采集点次数靠它归零），全仓只有「时间 / 采集 / 建号那两处」几个入口在刷它
      ⇒ 别的路读它要么是 0（这档还没 tick 过）、要么是**上一回 tick 那天的旧值**。
      日期戳要的是「此刻」，那就是现算（宿主注入的那根钟）。
      实测（假钟）：全新角色同一分钟里 `往北` → `采集` → `往东`，`记录` 报「2 个游戏日」
      —— 其中一个就是那个 0（`往北` 那一下还没 tick 过）。
    """
    return int(state(epoch)["game_day"])


# ── 落到档上 ──────────────────────────────────────────────────
def tick(p: dict, epoch=None) -> dict:
    """把「今天」记到档上，并处理跨（游戏）日。

    只写一个 `day`；跨日时把**日计数**清掉（采集点次数那类）。
    时辰/天气不落档 —— 现算，避免缓存与表不同步。
    """
    st = state(epoch)
    prev = p.get("day")
    p["day"] = st["game_day"]
    rolled = prev is not None and int(prev) != st["game_day"]
    if rolled:
        f = dict(p.get("flags") or {})
        f.pop("gather_used", None)
        p["flags"] = f
    st["rolled"] = rolled
    return st


# ── 门槛（采集点 / 对话 / 事件共用一套「名字 → 现看时辰还是天气」）──
def resolve(token):
    """名字（「夜」「雨」…）→ `("hour"|"weather", id)`；认不出 → `(None, None)`。"""
    global _NAME_MAP
    if _NAME_MAP is None:
        m = {}
        for hid, h in hours().items():
            m[str(_slot_text(h["slot"]))] = ("hour", hid)
        for wid, w in weathers().items():
            m[str(_slot_text(w["slot"]))] = ("weather", wid)
        _NAME_MAP = m
    return _NAME_MAP.get(str(token), (None, None))


def allows(token, st: dict | None = None) -> bool:
    """门槛判据：`"夜"` / `"雨"` / `["昏","夜"]`（多值 = 任一命中）。

    空 / None = 没有门槛 → True。认不出的名字 = False（探针会把这类名字拦在提交前）。
    """
    if not token:
        return True
    st = st or state()
    toks = token if isinstance(token, (list, tuple)) else [token]
    for t in toks:
        kind, eid = resolve(t)
        if kind == "hour" and eid == st["hour"]:
            return True
        if kind == "weather" and eid == st["weather"]:
            return True
    return False


# ══════════════════════════════════════════════════════════════
# 世界事件（B3-5 · 三尺度：世界 / 限时 / 每日）—— ★ 判定唯一口
# ------------------------------------------------------------
# 口径（`06_第一阶段垂直切片/29_世界事件_设计_v1.md` §二）：
#   世界级 = 跟着主线进度走的**开关**（一次翻转）· 限时 = 到点自己开合的**周期** · 每日 = 每天重来。
#   三者都只是「当前是否成立」的一个布尔 —— **谁都不存历史**。
# ★ 两件纪律：
#   ① 判定只走这一处（`event_on` / `events_now`），别处不许自己算（K65 家族：两处口径）
#   ② 事件名 / 节点 / npc / 天气 / 委托 **只当 id 比**：认不出的名字给 False，
#      探针（`probe_events`）把脏名字拦在提交前 —— 不许静默当「不成立」
# 历史那一格（「上次刷新时开着哪些窗」）由维护门落档，见 `content/timed_events.py`。
# ══════════════════════════════════════════════════════════════

#: 尺度排序（呈现口按它排：world → timed → daily）—— ★ 用 ASCII 键，不拿中文枚举当机器键（P-20）
_SCALE_ORDER = {"world": 0, "timed": 1, "daily": 2}


def events() -> dict:
    """事件表（`_` 前缀 = 私有键，不是条目）。"""
    return _entries("events")


def event(name) -> dict:
    """事件 id → 那条记录（认不出给空表 —— 判据在 `event_on`）。"""
    return events().get(str(name)) or {}


def _flags(p) -> dict:
    return (p or {}).get("flags") or {}


def main_done(p, qid) -> bool:
    """主线过了没有 —— 两个键都是「交活那一下」写的（`cmds_quest._set quests_done` + `_mark_done`）。"""
    qid = str(qid)
    f = _flags(p)
    if qid in (f.get("quests_done") or []):
        return True
    return bool(((f.get("quests") or {}).get(qid) or {}).get("done"))


def _on(eid, rec, st, p) -> bool:
    """一条事件此刻成不成立（period 认不出 = 抛 —— 表错了，别静默当不成立）。"""
    per = rec.get("period") or {}
    if "from_main" in per:
        return main_done(p, per["from_main"])
    if "until_main" in per:
        return not main_done(p, per["until_main"])
    if per.get("daily"):
        return True
    d = int(st["game_day"])
    if per.get("every_days"):
        return d % int(per["every_days"]) < int(per.get("last_days") or 1)
    if per.get("from_day"):
        a = int(per["from_day"])
        return a <= d < a + int(per.get("last_days") or 1)
    raise ValueError("events 域 %r 的 period 认不出（表错了，探针会拦）" % eid)


def window_key(name, st: dict | None = None, p=None) -> str:
    """事件这一「窗」的键（周期键）—— 键怎么拼在本模块，值只当不透明串（与 `ext_life.periodic` 同口径）。

    · 世界级 = `<事件id>:m:<主线id>:<0|1>`（主线一翻转就是新的一格 ⇒ 「商队到了」那一下算新开）
    · 限时 = `<事件id>:w:<窗头那个游戏日>:<持续几日的槽>`（同一天永远同一个键 ⇒ 幂等的根）
    · 每日 = `<事件id>:d:<游戏日>`（每天重来）

    ★ 键**以事件 id 开头**（`id_of_key` 反查得回 id）—— 维护门那一格只存键，
      呈现口要按旧键说「收了」就得认得出是哪条。
    """
    rec = events().get(str(name)) or {}
    if not rec:
        raise KeyError("events 域里没有 %r —— 键要先有事件" % name)
    per = rec.get("period") or {}
    if "from_main" in per or "until_main" in per:
        qid = per.get("from_main") or per.get("until_main")
        return "%s:m:%s:%d" % (name, qid, 1 if main_done(p, qid) else 0)
    d = int((st or state())["game_day"])
    if per.get("daily"):
        return "%s:d:%s" % (name, day_key(d))
    if per.get("every_days"):
        every = int(per["every_days"])
        return "%s:w:%s:%d" % (name, day_key(d - (d % every)), int(per.get("last_days") or 1))
    if per.get("from_day"):
        return "%s:w:%s:%d" % (name, day_key(int(per["from_day"])), int(per.get("last_days") or 1))
    raise ValueError("events 域 %r 的 period 认不出（表错了，探针会拦）" % name)


def id_of_key(key) -> str:
    """窗键 → 事件 id（键以 id 开头，见 `window_key`）；认不出给空串。"""
    eid = str(key or "").split(":", 1)[0]
    return eid if eid in events() else ""


def event_on(name, st: dict | None = None, p=None) -> bool:
    """这个事件此刻成不成立 —— ★ 唯一口（`_npcs_here` / 对话 need / 效果栏都走它）。

    认不出的名字 = False（fail-closed：不静默当成立）；`p` 不传 = 按新档算主线进度
    （包内调用方**都要把档传进来** —— 世界级看主线，不传档就会把商队那两位藏起来）。
    """
    eid = str(name)
    rec = events().get(eid)
    if not rec:
        return False
    return _on(eid, rec, st or state(), p)


def events_now(st: dict | None = None, p=None) -> list:
    """此刻成立的事件（世界 → 限时 → 每日，同尺度按文档行号）—— 每条多带 `id` 与 `window`。"""
    st = st or state()
    out = []
    for eid, rec in events().items():
        if _on(eid, rec, st, p):
            out.append(dict(rec, id=eid, window=window_key(eid, st, p)))
    out.sort(key=lambda r: (_SCALE_ORDER.get(r.get("scale_key"), 9), int(r.get("no") or 99), r["id"]))
    return out


def on_keys(st: dict | None = None, p=None) -> list:
    """此刻成立的那些**窗键**（升序）—— 维护门落档与「异动」标「新开的」共用这一口。"""
    return sorted(r["window"] for r in events_now(st, p))


def where_hit(rec, loc) -> bool:
    """这条事件在不在这一图生效（`where` 不给 = 全图）。"""
    w = rec.get("where") or []
    return (not w) or (loc in w)


def last_refresh(p) -> dict:
    """上次刷新时开着哪些窗（宿主维护门落的档 · `content/timed_events.py` 写）—— 呈现口用它标「新开/收了」。"""
    return dict(_flags(p).get("ev") or {})


def crowd_roster(st: dict | None = None, p=None) -> dict:
    """现在被事件「吸走」的 NPC：`{npc_id: 节点 id}`（集日那两位的临时在场）。

    ★ 消费端 = `cmds_ast._npcs_here`：被吸走的不在基位算在场，只在 `crowd.node` 那一站算在场；
      文档依据 = 29 §四③「多出 2–3 位 NPC 的**临时在场**」。
    """
    st = st or state()
    out = {}
    for rec in events_now(st, p):
        c = (rec.get("effects") or {}).get("crowd") or {}
        if not c.get("node"):
            continue
        for n in c.get("npcs") or []:
            out[str(n)] = str(c["node"])
    return out


def crowd_text_at(node, st: dict | None = None, p=None) -> str:
    """这一站聚人那一下的文案槽位（没有 = 空串）。"""
    for rec in events_now(st, p):
        c = (rec.get("effects") or {}).get("crowd") or {}
        if c.get("node") == node and c.get("text"):
            return str(c["text"])
    return ""


def _mul_effect(key, st, p) -> dict:
    """效果栏里「加权重」那一类键 → `{目标: 倍数}`。

    同一个目标被多条事件点名 ⇒ **依次相乘**（按事件 id 序，可复现）：两件都翻倍 = ×4。
    """
    out = {}
    for eid, rec in sorted(events().items()):
        if not _on(eid, rec, st, p):
            continue
        for tgt, mul in ((rec.get("effects") or {}).get(key) or {}).items():
            out[str(tgt)] = out.get(str(tgt), 1) * int(mul)
    return out


def encounter_mul(st: dict | None = None, p=None) -> dict:
    """遇敌候选加权（怪 id → 倍数）—— 消费端 `combat.pick_encounter`（空 = 零变化）。"""
    return _mul_effect("encounter_mul", st or state(), p)
