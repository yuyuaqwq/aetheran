# -*- coding: utf-8 -*-
"""探针：weather 域（天气表）—— 六条 · ★ 决定论（同一天全服一致）· ★ 权重与分布 ·
★ 天气保底（连续 N 个游戏日内至少一场雨 · B4-3 / 台账 ⏸ P-5）· ★ 名在 texts ·
★ 跨域回指（对话的天气门槛）· 旗标与文档一致。

判据分**两层**（★ 别混）：
  · 表格那一层 = `calendar.weather_raw(day)`（权重 + 稳定哈希）：分布与权重逐日一致由它担保。
  · 玩法那一层 = `calendar.weather_of(day)`（★ 唯一出口）= 表格那一层 + 保底：只加雨、不删别的天气。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_weather.py
"""
from __future__ import annotations

import io
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, REPO)
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402

DB = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db")
fails = []
ok = lambda m: print("  ✓ " + m)
bad = lambda m: (fails.append(m), print("  ✗ " + m))


def chk(label, cond, extra=""):
    (ok if cond else bad)(label + (("  —— %s" % extra) if extra else ""))


FIXED = 100 * 7200
st = load_stack(str(REPO), inject={"db_path": DB, "clock": lambda: FIXED})
st.install()

from content import calendar as CAL                                   # noqa: E402

SCALE = CAL.scale_seconds()
FIXED = 100 * SCALE
WEA = CAL.weathers()
HRS = CAL.hours()
TX = (CAL._d("texts") or {})

print("探针：weather 域（天气表）")

# ① 域
chk("weather 域读得到", bool(WEA), "%d 种天气" % len(WEA))
names = {wid: CAL.name(wid) for wid in WEA}
chk("四种天气", len(WEA) == 4, "%s" % list(names.values()))
chk("★ 名字 = 晴/雨/雾/初雪（texts 槽位的值）", set(names.values()) == {"晴", "雨", "雾", "初雪"}, names)
chk("名字互不相同", len(set(names.values())) == len(names))

# ② 权重
ws = {wid: int(v["weight"]) for wid, v in WEA.items()}
chk("★ 权重都是正整数", all(w > 0 for w in ws.values()), ws)
top = max(ws, key=lambda k: ws[k])
chk("★ 最常见的不是坏天气（晴权重最大）", top == "w_sunny", "%s=%d" % (names[top], ws[top]))
chk("雾最稀（源：参考实现雾 10）", min(ws, key=lambda k: ws[k]) == "w_fog", "%s" % ws)

# ③ ★ 决定论 + 与小时无关（天气按游戏日走）—— 两层都要决定论
d = 12345
chk("★ 同一天两次 = 同一天气", CAL.weather_of(d) == CAL.weather_of(d), CAL.weather_of(d))
chk("★ 表格那一层也是决定论（weather_raw 同一天两次同一个）",
    CAL.weather_raw(d) == CAL.weather_raw(d) and CAL.weather_raw(d) != "",
    "%s" % CAL.weather_raw(d))
same = {CAL.state(d * SCALE + (h / 24.0) * SCALE)["weather"] for h in (1, 7, 13, 21)}
chk("★ 同一天任何时辰，天气不变（天气按游戏日，不按小时）", len(same) == 1, "%s" % same)
chk("跨天天气真会变（不是写死的）", len({CAL.weather_of(d + i) for i in range(60)}) >= 3)

# ④ ★ 天气保底：常量只有一处（weather 域）+ 生成器只搬不编 + 来源可追溯
#   台账 ⏸ P-5：雨天权重 = 15/90 ≈ 17% ⇒ 支线 4「雨后的东西」可能等一整个游戏日；保底见
#   `content/rules/calendar.json`（那里面有真源依据与为什么 N=3；真源待补行见本分支 `_notes.md` §一）。
meta = CAL.weathers_meta()
rules_path = os.path.join(REPO, "content", "rules", "calendar.json")
chk("★ 保底常量在 weather 域里（单一口 `_rules.rain_max_gap_days`，代码不写数）",
    isinstance(meta.get("rain_max_gap_days"), int) and int(meta["rain_max_gap_days"]) >= 1,
    "N = %s" % meta.get("rain_max_gap_days"))
with io.open(rules_path, encoding="utf-8", newline="") as _f:
    _r = json.load(_f)
chk("★ 生成器只搬不编：域里的常量 == `content/rules/calendar.json` 那一个数",
    _r.get("rain_max_gap_days") == meta.get("rain_max_gap_days"),
    "口径表 %s / 域 %s" % (_r.get("rain_max_gap_days"), meta.get("rain_max_gap_days")))
chk("★ 保底来源可追溯（guarantee + guarantee_source 都记在表里 · 指向 ⏸ P-5）",
    bool(meta.get("guarantee")) and "rain_max_gap_days" in str(meta.get("guarantee_source"))
    and "P-5" in str(meta.get("guarantee_source")),
    "%s" % str(meta.get("guarantee_source"))[:64])
N = CAL.rain_max_gap_days()

# ⑤ ★ 保底真生效（玩家侧的那句话）：连推 3000 天 —— 任何 N 日窗里至少一场雨
#    等价说法：从任意一天起，最多等 N−1 天必有雨（支线 4 那类挂板上的线等得起）
D0, M = 100000, 3000
win_bad, run_bad = [], []
for i in range(D0, D0 + M - N + 1):
    if not any(CAL.weather_of(i + k) == "w_rain" for k in range(N)):
        win_bad.append(i)
run, worst = 0, 0
for i in range(D0, D0 + M):
    run = run + 1 if CAL.weather_of(i) != "w_rain" else 0
    worst = max(worst, run)
rain_name_id = CAL.resolve("雨")[1]
gate_bad = [i for i in range(D0, D0 + M - N + 1)
            if not any(CAL.allows("雨", {"weather": CAL.weather_of(i + k), "hour": "hr_day"})
                       for k in range(N))]
chk("★ 连续 %d 个游戏日内至少一场雨（推 %d 天 · 任何 %d 日窗里都有雨）" % (N, M, N),
    not win_bad, "无雨的窗 %d 个%s" % (len(win_bad), win_bad[:3]))
chk("★ 最长连续无雨 = N−1 = %d 天（等雨上界；支线 4 的「雨天去采菌」等得起）" % (N - 1),
    worst == N - 1, "实测最长 %d 天" % worst)
chk("★ 玩家侧同一件事：`allows(\"雨\")`（%s）在任何 %d 日窗里都成立过一次" % (rain_name_id, N),
    not gate_bad, "%s" % (gate_bad[:3] or "无"))

# ⑥ ★ 保底只加雨：逐日 `weather_of ∈ {weather_raw, 雨}`，一天都没被删 / 改成别的天气
added, removed = [], []
for i in range(D0, D0 + M):
    g, r = CAL.weather_of(i), CAL.weather_raw(i)
    if g == r:
        continue
    if r != "w_rain" and g == "w_rain":
        added.append(i)
    else:
        removed.append((i, r, g))
chk("★ 保底只加雨（%d 天被补成雨）· 没有一天被删或被改成别的天气" % len(added),
    bool(added) and not removed, "%s" % (removed[:3] or "被改动的 0 天"))


# ★ 递推那一支（另一种写法，探针自己按同一句口径反算 —— 不是拿实现自证）：
#   「今天抽签不是雨，且往前 N−1 天（**算上保底**）都不是雨 ⇒ 今天雨」
_rec_cache: dict = {}


def _rec(day):
    if day in _rec_cache:
        return _rec_cache[day]
    w = CAL.weather_raw(day)
    out = "w_rain" if (w == "w_rain"
                       or all(_rec(day - k) != "w_rain" for k in range(1, N))) else w
    _rec_cache[day] = out
    return out


mismatch = [i for i in range(D0, D0 + M) if CAL.weather_of(i) != _rec(i)]
chk("★ 现算那一支 == 递推那一支（往前 %d 天算上保底都没雨 ⇒ 今天雨 · %d 天逐日对照）" % (N - 1, M),
    not mismatch, "不一致 %d 天%s" % (len(mismatch), mismatch[:3]))

# ⑦ ★ 表格那一层：分布 = 权重（不手打期望：比例来自表本身）
N_DAYS = 2000
cnt = {}
for i in range(N_DAYS):
    w = CAL.weather_raw(100000 + i)
    cnt[w] = cnt.get(w, 0) + 1
tot = sum(ws.values())
worst_dev, worst_k = 0.0, None
for wid in ws:
    exp = N_DAYS * ws[wid] / tot
    dev = abs(cnt.get(wid, 0) - exp) / exp
    if dev > worst_dev:
        worst_dev, worst_k = dev, wid
chk("★ 2000 天的表格抽签（weather_raw）与权重一致（相对偏差 ≤ 15%）", worst_dev <= 0.15,
    " ".join("%s %.1f%%(期望 %.1f%%)" % (names[k], 100.0 * cnt.get(k, 0) / N_DAYS, 100.0 * ws[k] / tot)
             for k in sorted(ws)) + " · 最大偏 %s %.1f%%" % (names[worst_k], 100 * worst_dev))
chk("★ 四种天气都会出现（表格那一层没有永不落地的天气）", len(cnt) == len(ws),
    "%s" % {names[k]: v for k, v in cnt.items()})

# ⑧ ★ 玩法那一层（保底后）：四种天气都还在 + 「雨」只会变多（≥ 表里的份额）
cnt2 = {}
for i in range(N_DAYS):
    w = CAL.weather_of(100000 + i)
    cnt2[w] = cnt2.get(w, 0) + 1
share_w = ws["w_rain"] / float(tot)
share_g = cnt2.get("w_rain", 0) / float(N_DAYS)
chk("★ 保底后四种天气都会出现（没有天气被保底挤没）", len(cnt2) == len(ws),
    " ".join("%s %.1f%%" % (names[k], 100.0 * cnt2.get(k, 0) / N_DAYS) for k in sorted(cnt2)))
chk("★ 保底后「雨」的占比 ≥ 表里的份额（只增不减：%.1f%% ≥ %.1f%%）"
    % (100 * share_g, 100 * share_w),
    share_g >= share_w, "表里的 %.1f%% → 保底后 %.1f%%（N=%d）" % (100 * share_w, 100 * share_g, N))

# ⑨ ★ fail-closed + 现读常量真生效（反证：改表里那一格，行为当场跟着变）
_wj = CAL._d("weather")
_rec = _wj.setdefault("_rules", {})
_old = _rec.get("rain_max_gap_days")
before = [CAL.weather_of(100000 + i) for i in range(40)]
try:
    _rec["rain_max_gap_days"] = 0
    try:
        CAL.weather_of(100000)
        threw0 = False
    except ValueError:
        threw0 = True
    _rec["rain_max_gap_days"] = "3"
    try:
        CAL.weather_of(100000)
        threw_str = False
    except ValueError:
        threw_str = True
    _rec["rain_max_gap_days"] = 1
    all_rain = all(CAL.weather_of(100000 + i) == "w_rain" for i in range(40))
finally:
    _rec["rain_max_gap_days"] = _old
after = [CAL.weather_of(100000 + i) for i in range(40)]
chk("★ fail-closed：N 坏掉（0 / 字符串）⇒ weather_of 当场抛（不静默取消保底）", threw0 and threw_str)
chk("★ 表里那一格是**现读**的（临时改成 1 ⇒ 天天是雨；改回原样 ⇒ 逐日复原）",
    all_rain and before == after, "N=1 时 40 天全雨 = %s" % all_rain)

# ⑩ 槽位都在 texts 里
bad_slot = [(k, v.get("slot"), v.get("desc_slot")) for k, v in WEA.items()
            if v.get("slot") not in TX or v.get("desc_slot") not in TX]
chk("★ slot / desc_slot 都在 texts 域（跨域对账）", not bad_slot, "%s" % (bad_slot or "无"))

# ⑪ ★ 跨域回指：对话里的天气门槛
dlg = []


def _tokens(obj, key, out):
    if isinstance(obj, dict):
        if key in obj and isinstance(obj[key], (str, list)):
            out.extend(obj[key] if isinstance(obj[key], list) else [obj[key]])
        for v in obj.values():
            _tokens(v, key, out)
    elif isinstance(obj, list):
        for v in obj:
            _tokens(v, key, out)


_tokens(CAL._d("dialogues"), "weather", dlg)
unknown = [t for t in dlg if CAL.resolve(t) != ("weather", CAL.resolve(t)[1])]
chk("★ 对话的天气门槛（%d 处）都认得出" % len(dlg), bool(dlg) and not unknown,
    "%s" % (dlg or "无"))

# ⑫ ★ 旗标与文档一致（19 §世界动静：雨后出菌 / 雾更容易撞上精英 / 雷雨天雷系 +10%）
f = lambda wid: (WEA[wid].get("flags") or {})
chk("雨后出菌 挂在「雨」上", f("w_rain").get("gather_growth") is True)
chk("雷系 +10% 挂在「雨」上（19 文档的「雷雨天」在四类里并入雨）",
    (f("w_rain").get("elem_bonus") or {}).get("雷") == 10, f("w_rain").get("elem_bonus"))
chk("雾 → 更容易撞上精英（10 文档 D33）", f("w_fog").get("elite_up") is True)
chk("没原文的天气不给旗标（不许脑补）",
    all(not (k in ("w_sunny", "w_snow") and f(k)) for k in ("w_sunny", "w_snow")),
    "晴 %s / 初雪 %s" % (f("w_sunny"), f("w_snow")))

# ⑬ 规则块：来源都记着（可追溯）
rules = (CAL._d("weather") or {}).get("_rules") or {}
chk("★ 权重来源记在表里（可追溯）", bool(rules.get("weights_source")) and bool(rules.get("source")),
    "%s · 跳过 %s" % (str(rules.get("weights_source"))[:38], rules.get("skipped")))

print()
print("结果：%s" % ("全绿 ✓" if not fails else "有红 ✗（%d）" % len(fails)))
sys.exit(1 if fails else 0)
