# -*- coding: utf-8 -*-
"""探针：weather 域（天气表）—— 四条 · ★ 决定论（同一天全服一致）· ★ 权重与分布 ·
★ 名在 texts · ★ 跨域回指（对话的天气门槛）· 旗标与文档一致。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_weather.py
"""
from __future__ import annotations

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

# ③ ★ 决定论 + 与小时无关（天气按游戏日走）
d = 12345
chk("★ 同一天两次 = 同一天气", CAL.weather_of(d) == CAL.weather_of(d), CAL.weather_of(d))
same = {CAL.state(d * SCALE + (h / 24.0) * SCALE)["weather"] for h in (1, 7, 13, 21)}
chk("★ 同一天任何时辰，天气不变（天气按游戏日，不按小时）", len(same) == 1, "%s" % same)
chk("跨天天气真会变（不是写死的）", len({CAL.weather_of(d + i) for i in range(60)}) >= 3)

# ④ ★ 2000 天的分布 = 权重（不手打期望：比例来自表本身）
N = 2000
cnt = {}
for i in range(N):
    w = CAL.weather_of(100000 + i)
    cnt[w] = cnt.get(w, 0) + 1
tot = sum(ws.values())
worst, worst_k = 0.0, None
for wid in ws:
    exp = N * ws[wid] / tot
    dev = abs(cnt.get(wid, 0) - exp) / exp
    if dev > worst:
        worst, worst_k = dev, wid
chk("★ 2000 天分布与权重一致（相对偏差 ≤ 15%%）", worst <= 0.15,
    " ".join("%s %.1f%%(期望 %.1f%%)" % (names[k], 100.0 * cnt.get(k, 0) / N, 100.0 * ws[k] / tot)
             for k in sorted(ws)) + " · 最大偏 %s %.1f%%" % (names[worst_k], 100 * worst))
chk("★ 四种天气都会出现（没有永不落地的天气）", len(cnt) == len(ws), "%s" % {names[k]: v for k, v in cnt.items()})

# ⑤ 槽位都在 texts 里
bad_slot = [(k, v.get("slot"), v.get("desc_slot")) for k, v in WEA.items()
            if v.get("slot") not in TX or v.get("desc_slot") not in TX]
chk("★ slot / desc_slot 都在 texts 域（跨域对账）", not bad_slot, "%s" % (bad_slot or "无"))

# ⑥ ★ 跨域回指：对话里的天气门槛
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

# ⑦ ★ 旗标与文档一致（19 §世界动静：雨后出菌 / 雾更容易撞上精英 / 雷雨天雷系 +10%）
f = lambda wid: (WEA[wid].get("flags") or {})
chk("雨后出菌 挂在「雨」上", f("w_rain").get("gather_growth") is True)
chk("雷系 +10% 挂在「雨」上（19 文档的「雷雨天」在四类里并入雨）",
    (f("w_rain").get("elem_bonus") or {}).get("雷") == 10, f("w_rain").get("elem_bonus"))
chk("雾 → 更容易撞上精英（10 文档 D33）", f("w_fog").get("elite_up") is True)
chk("没原文的天气不给旗标（不许脑补）",
    all(not (k in ("w_sunny", "w_snow") and f(k)) for k in ("w_sunny", "w_snow")),
    "晴 %s / 初雪 %s" % (f("w_sunny"), f("w_snow")))

# ⑧ 规则块：来源都记着（可追溯）
rules = (CAL._d("weather") or {}).get("_rules") or {}
chk("★ 权重来源记在表里（可追溯）", bool(rules.get("weights_source")) and bool(rules.get("source")),
    "%s · 跳过 %s" % (str(rules.get("weights_source"))[:38], rules.get("skipped")))

print()
print("结果：%s" % ("全绿 ✓" if not fails else "有红 ✗（%d）" % len(fails)))
sys.exit(1 if fails else 0)
