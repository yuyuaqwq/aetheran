# -*- coding: utf-8 -*-
"""calendar / weather 两域 —— 数据重建（唯一真源 = 源文档；★ 数值解析得来，禁手打）。

用法：python scripts/rebuild_calendar.py [--dry]

每一处数值都能指回文件与原文：
  ① 游戏日长度      06_第一阶段垂直切片/05_玩法数值口径_v1.md §七「游戏内 1 天 = 现实 2 小时」
  ② 时辰/天气四类名 + 影响  06_第一阶段垂直切片/19_世界热闹度与可发现物_v1.md §三 D 表
  ③ 时辰窗界        参考实现 games/orlandia/content/time_weather.py::PERIODS（晨 5-8 / 昼 8-18 / 昏 18-20 / 夜 20-5）
  ④ 天气权重        同上 today_weather 文档串（晴50/雨15/雾10/雪15；多云·暴雨不在本作四类 ⇒ 记进 _rules.skipped）
  ⑤ 雾 → 精英       06_第一阶段垂直切片/10_地图探索元素库_v1.md D33

★ 本文件只负责「文档 → 表」；表里的中文一律是**槽位名**（文案真源 = texts 域）。
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.environ.get("AETHERAN_PLAN", "C:/Users/yuyu/aetheran-plan")
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")

DOC05 = os.path.join(PLAN, "06_第一阶段垂直切片", "05_玩法数值口径_v1.md")
DOC10 = os.path.join(PLAN, "06_第一阶段垂直切片", "10_地图探索元素库_v1.md")
DOC19 = os.path.join(PLAN, "06_第一阶段垂直切片", "19_世界热闹度与可发现物_v1.md")
REF = os.path.join(ENGINE, "games", "orlandia", "content", "time_weather.py")

#: 文档里的四类名（顺序 = 19 文档表中顺序）→ 我们的 id / 槽位（id 与槽位是本包命名，不是数值）
HOUR_IDS = [("hr_dawn", "HOUR_DAWN"), ("hr_day", "HOUR_DAY"),
            ("hr_dusk", "HOUR_DUSK"), ("hr_night", "HOUR_NIGHT")]
WEATHER_IDS = [("w_sunny", "WEATHER_SUNNY"), ("w_rain", "WEATHER_RAIN"),
               ("w_fog", "WEATHER_FOG"), ("w_snow", "WEATHER_SNOW")]
#: 参考实现的时段 id → 我们的时辰 id（窗界照抄它）
REF_PERIOD_TO_HOUR = {"morning": "hr_dawn", "day": "hr_day",
                      "evening": "hr_dusk", "night": "hr_night"}


def read(path: str) -> str:
    with io.open(path, encoding="utf-8", newline="") as f:
        return f.read()


def die(msg: str):
    print("✗ %s" % msg)
    raise SystemExit(2)


def table_row(doc: str, first_cell: str) -> list:
    """取 markdown 表里第一格 = first_cell 的那一行 → 各单元格（已 strip）。"""
    for line in doc.splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) >= 4 and cells[1] == first_cell:
            return cells[2:]
    die("源文档里找不到表格行「| %s |」" % first_cell)


def names_of(cell: str) -> list:
    return [x.strip() for x in cell.split("/") if x.strip()]


# ── ① 游戏日长度 ──────────────────────────────────────────────
doc05 = read(DOC05)
m = re.search(r"游戏内\s*1\s*天\s*=\s*现实\s*(\d+)\s*小时", doc05)
if not m:
    die("05_玩法数值口径 里找不到「游戏内 1 天 = 现实 N 小时」")
sec_per_day = int(m.group(1)) * 3600
src_day = "06_第一阶段垂直切片/05_玩法数值口径_v1.md §七：游戏内 1 天 = 现实 %s 小时（可调）" % m.group(1)

# ── ② 四类名与影响 ───────────────────────────────────────────
doc19 = read(DOC19)
w_cells = table_row(doc19, "天气")
h_cells = table_row(doc19, "时辰")
w_names, w_effects = names_of(w_cells[0]), w_cells[1]
h_names, h_effects = names_of(h_cells[0]), h_cells[1]
if len(w_names) != 4 or len(h_names) != 4:
    die("19 文档的天气/时辰不是四类：%r / %r" % (w_names, h_names))
src_names = "06_第一阶段垂直切片/19_世界热闹度与可发现物_v1.md §三 D 世界动静"

# ── ③ 时辰窗界（照参考实现 PERIODS，同名的两段合并）────────────
ref = read(REF)
rows = re.findall(r'\(\s*"([a-z]+)"\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', ref)
if not rows:
    die("参考实现里找不到 PERIODS")
span = {}
for name, a, b in rows:
    span.setdefault(name, []).append((int(a), int(b)))
windows = {}
for name, segs in span.items():
    if name not in REF_PERIOD_TO_HOUR:
        continue
    if len(segs) == 2 and segs[0][0] == 0 and segs[1][1] == 24:
        windows[REF_PERIOD_TO_HOUR[name]] = (segs[1][0], segs[0][1])       # 跨零点（夜）
    else:
        windows[REF_PERIOD_TO_HOUR[name]] = segs[0]
missing = [h for hid, _ in HOUR_IDS if hid not in windows]
if missing or sum((b - a) % 24 for a, b in windows.values()) != 24:
    die("参考实现的时段没盖满一天：%r（缺 %r）" % (windows, missing))

# ── ④ 天气权重 ───────────────────────────────────────────────
m = re.search(r"当天天气：([^\"\n]+)", ref)
if not m:
    die("参考实现里找不到 today_weather 的权重串")
ref_weights = {}
_CJK = "[一-龥]"
for nm, w in re.findall("(" + _CJK + "{1,3})(?:[（(][^）)]*[）)])?([0-9]+)", m.group(1)):
    ref_weights[nm] = int(w)          # 晴50 / 多云20 / 雨15 / 暴雨5 / 雪(冬)15 / 雾(特定地图)10
if not ref_weights:
    die("权重要解析不动：%r" % m.group(1))
def _weight_of(name):
    """权重找名 → (权重, 源里那个名)：先精确，再按「谁包含谁」（源里叫「雪」，本作叫「初雪」）。"""
    if name in ref_weights:
        return ref_weights[name], name
    for k, v in ref_weights.items():
        if k in name or name in k:
            return v, k
    return None, None


weights, skipped, used_ref = {}, {}, set()
for name, (wid, slot) in zip(w_names, WEATHER_IDS):
    got, ref_name = _weight_of(name)
    if got is None:
        skipped[name] = "参考实现里找不到对应名"
    else:
        weights[wid] = got
        used_ref.add(ref_name)
for name in ref_weights:
    if name not in used_ref:
        skipped[name] = "不在 19 文档的四类里（本作 P1 不落）"
src_weights = ("games/orlandia/content/time_weather.py::today_weather 文档串：%s"
               "（只取本作四类）" % m.group(1).strip())

# ── ⑤ 逐条影响（只认有原文的那几条）──────────────────────────
w_flags, h_flags = {}, {}
if "雨后出菌" in w_effects:
    w_flags.setdefault("w_rain", {})["gather_growth"] = True
me = re.search(r"([\u4e00-\u9fa5])系\s*\+(\d+)%", w_effects)
if me:
    w_flags.setdefault("w_rain", {})["elem_bonus"] = {me.group(1): int(me.group(2))}
if "稀有鱼只在夜里" in h_effects:
    h_flags.setdefault("hr_night", {})["rare_fish"] = True
if "水鬼夜里上岸" in h_effects:
    h_flags.setdefault("hr_night", {})["nocturnal_spawn"] = True
if "哈根只在傍晚在墙根" in h_effects:
    h_flags.setdefault("hr_dusk", {})["npc_window"] = True
fog = "雾与天气（视野变短 → 更容易撞上精英）" in read(DOC10)
if fog:
    w_flags.setdefault("w_fog", {})["elite_up"] = True
affects = [k for k, v in (("encounter", "遇敌率"), ("gather", "采集"), ("element", "元素伤害"))
           if v in w_effects]

# ── 写表 ─────────────────────────────────────────────────────
calendar = {"_clock": {"zone": "Asia/Shanghai", "real_seconds_per_game_day": sec_per_day,
                       "source": src_day,
                       "note": "游戏时刻 = 宿主注入的 epoch × (86400 / real_seconds_per_game_day)；"
                               "刻度在表里，调时间快慢只改这一个数"}}
for (hid, slot), name in zip(HOUR_IDS, h_names):
    a, b = windows[hid]
    calendar[hid] = {"slot": slot, "desc_slot": slot + "_DESC",
                     "from_hour": a, "to_hour": b,
                     "flags": h_flags.get(hid, {}),
                     "source": "%s（名：%s）· 窗界照 games/orlandia/content/time_weather.py::PERIODS"
                               % (src_names, name)}

weather = {"_rules": {"cycle": "game_day", "pick": "weighted_stable_hash",
                      "weights_source": src_weights,
                      "skipped": skipped,
                      "affects": affects,
                      "seasons": "P1 未开（05_系统总表与阶段开放：季节自 P2 起）",
                      "maps": "P1 全图一致（雾不按地图分）",
                      "source": src_names}}
for (wid, slot), name in zip(WEATHER_IDS, w_names):
    weather[wid] = {"slot": slot, "desc_slot": slot + "_DESC",
                    "weight": weights[wid],
                    "flags": w_flags.get(wid, {}),
                    "source": "%s（名：%s）· 权重 %s" % (src_names, name, src_weights)}
if not weights:
    die("天气权重一条都没解析到")

outs = [(os.path.join(PKG, "content", "data", "calendar.json"), calendar),
        (os.path.join(PKG, "content", "data", "weather.json"), weather)]
for path, data in outs:
    txt = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if "--dry" in sys.argv:
        print("— %s（dry）\n%s" % (path, txt))
        continue
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(txt)
    print("✓ %s（%d 条）" % (path, len(data) - sum(1 for k in data if k.startswith("_"))))
