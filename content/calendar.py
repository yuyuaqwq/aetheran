# -*- coding: utf-8 -*-
"""《阿斯特兰》时辰与天气 —— `calendar` / `weather` 两域的**唯一出口**。

口径（全在表里，本模块不写死数值、不写死中文）：
  · 游戏日长度 = `calendar._clock.real_seconds_per_game_day`（源：05_玩法数值口径 §七）
  · 时辰窗界 = `calendar.hr_*` 的 from/to 小时；中文名 = **texts 域**的 `HOUR_*` / `WEATHER_*`
  · 天气 = 纯函数 `游戏日 → 天气`（按 `weather.w_*.weight` 抽；稳定哈希 ⇒ 全服一致、跨进程可复现）

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


def weather_of(day: int) -> str:
    """游戏日 → 天气 id。稳定哈希 + 权重（同一天全服一致，跨进程可复现）。"""
    ws = weathers()
    if not ws:
        raise ValueError("weather 域是空的")
    total = sum(int(v["weight"]) for v in ws.values())
    h = hashlib.md5(("aetheran:weather:" + day_key(day)).encode("utf-8")).hexdigest()
    r = int(h[:8], 16) % total
    acc = 0
    for wid in sorted(ws):                       # 顺序固定（id 升序）⇒ 可复现
        acc += int(ws[wid]["weight"])
        if r < acc:
            return wid
    return sorted(ws)[-1]


def state(epoch=None) -> dict:
    """此刻的时辰与天气（★ 唯一出口）。`epoch` 省略 = 宿主注入的钟。"""
    day, hod = game_time(epoch)
    hid, wid = hour_at(hod), weather_of(day)
    return {"game_day": day, "day_key": day_key(day), "hour_of_day": round(hod, 3),
            "hour": hid, "hour_name": name(hid),
            "weather": wid, "weather_name": name(wid)}


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
