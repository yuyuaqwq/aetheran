# -*- coding: utf-8 -*-
"""探针：calendar 域（时辰表）—— 窗界盖满一天 · ★ 假钟注入 · ★ 表只存槽位（名在 texts）·
★ 各域的门槛名都能回到时辰表 · 接线真生效（NPC 出场 / 对话择优 / 采集门槛）。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_calendar.py
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

#: 假钟：epoch 从表里算（不手打）—— 第 100 个游戏日的 21 点（夜）
CAL_PRE = None
fails = []
ok = lambda m: print("  ✓ " + m)
bad = lambda m: (fails.append(m), print("  ✗ " + m))


def chk(label, cond, extra=""):
    (ok if cond else bad)(label + (("  —— %s" % extra) if extra else ""))


FIXED = 100 * 7200 + (21.0 / 24.0) * 7200          # 先给个能算的；下面按表重算
st = load_stack(str(REPO), inject={"db_path": DB, "clock": lambda: FIXED})
st.install()

from content import calendar as CAL                                   # noqa: E402
from content import cmds_ast, cmds_talk                               # noqa: E402

SCALE = CAL.scale_seconds()
FIXED = 100 * SCALE + (21.0 / 24.0) * SCALE

HRS = CAL.hours()
WEA = CAL.weathers()
TX = (CAL._d("texts") or {})

print("探针：calendar 域（时辰表）")

# ① 域与刻度
chk("calendar 域读得到", bool(HRS), "%d 个时辰" % len(HRS))
meta = CAL.clock_meta()
chk("★ 刻度在表里（_clock.real_seconds_per_game_day）", int(meta.get("real_seconds_per_game_day") or 0) > 0,
    "%s 秒/游戏日 · 源：%s" % (meta.get("real_seconds_per_game_day"), str(meta.get("source"))[:40]))

# ② 四条 + 名字（名字只认 texts）
names = {hid: CAL.name(hid) for hid in HRS}
chk("四个时辰", len(HRS) == 4, "%s" % names)
chk("★ 名字 = 晨/昼/昏/夜（texts 槽位的值）", set(names.values()) == {"晨", "昼", "昏", "夜"}, names)
chk("名字互不相同", len(set(names.values())) == len(names))

# ③ ★ 窗界盖满一天：每一分钟都能落到一个时辰，且四个时辰都被用到
hit = {}
for mnt in range(24 * 60):
    hid = CAL.hour_at(mnt / 60.0)
    hit[hid] = hit.get(hid, 0) + 1
chk("★ 窗界盖满一天（无缺口、无重叠）", sum(hit.values()) == 24 * 60 and len(hit) == 4,
    " ".join("%s %d 分钟" % (CAL.name(k), v) for k, v in sorted(hit.items())))

# ④ ★ 假钟：注入面通了才叫「可测」
from_iject = CAL.state()
from_arg = CAL.state(epoch=FIXED)
chk("★ 假钟穿得过（注入钟 = 显式 epoch）", from_iject == from_arg, "now=%s" % from_iject["hour_name"])
chk("假钟时刻对得上（21 点 = 夜）", from_arg["hour"] == "hr_night", from_arg["hour_name"])

# ⑤ ★ 刻度：过了一个游戏日，游戏日 +1、时辰不变
a = CAL.state(FIXED)
b = CAL.state(FIXED + SCALE)
chk("★ 过一天 = 现实 %d 秒（游戏日 +1，时辰不变）" % SCALE,
    b["game_day"] == a["game_day"] + 1 and b["hour"] == a["hour"] and b["weather"] is not None,
    "%s → %s" % (a["day_key"], b["day_key"]))

# ⑥ 槽位都在 texts 里（缺一条就回不出名）
bad_slot = [(k, v.get("slot")) for k, v in HRS.items()
            if v.get("slot") not in TX or v.get("desc_slot") not in TX]
chk("★ slot / desc_slot 都在 texts 域（跨域对账）", not bad_slot, "%s" % (bad_slot or "无"))

# ⑦ ★ 别的域的门槛名，必须能回到时辰表 / 天气表（认不出 = 数据里有脏名字）
def _tokens(obj, key, out):
    if isinstance(obj, dict):
        if key in obj and isinstance(obj[key], (str, list)):
            out.extend(obj[key] if isinstance(obj[key], list) else [obj[key]])
        for v in obj.values():
            _tokens(v, key, out)
    elif isinstance(obj, list):
        for v in obj:
            _tokens(v, key, out)


doors, must_hour, must_weather = [], [], []
for gid, g in (CAL._d("gathering") or {}).items():      # 采集点：时辰或天气都行（「雨后才有」）
    if g.get("time"):
        doors.append(("gathering.time:" + gid, g["time"]))
    for e in (g.get("pool") or []):
        if e.get("when"):
            doors.append(("gathering.pool.when:" + gid, e["when"]))
for npc_id, npc in (CAL._d("npcs") or {}).items():       # NPC 出场：时辰
    for tok in ((npc.get("condition") or {}).get("time") or []):
        must_hour.append(("npcs.condition.time:" + npc_id, tok))
dlg_h, dlg_w = [], []
_tokens(CAL._d("dialogues"), "time", dlg_h)
_tokens(CAL._d("dialogues"), "weather", dlg_w)
must_hour += [("dialogues.need.time", t) for t in dlg_h]
must_weather += [("dialogues.need.weather", t) for t in dlg_w]

unknown = [(w, t) for w, t in (doors + must_hour + must_weather) if CAL.resolve(t) == (None, None)]
kind_bad = [(w, t) for w, t in must_hour if CAL.resolve(t)[0] != "hour"]
kind_bad += [(w, t) for w, t in must_weather if CAL.resolve(t)[0] != "weather"]
chk("★ 门槛名 %d 处全部认得出（采集 %d / 时辰 %d / 天气 %d）"
    % (len(doors) + len(must_hour) + len(must_weather), len(doors), len(must_hour), len(must_weather)),
    not unknown, "%s" % (unknown or "无脏名字"))
chk("★ 键与名对得上（need.time 只能是时辰、need.weather 只能是天气）", not kind_bad,
    "%s" % (kind_bad or "无"))

# ⑧ 门槛语义
night = CAL.state(FIXED)
day = CAL.state(FIXED + (12.0 / 24.0) * SCALE)
chk("门槛语义：None = 没门槛", CAL.allows(None, day) is True)
chk("门槛语义：夜 in 夜 = 过", CAL.allows("夜", night) is True)
chk("门槛语义：夜 in 昼 = 不过", CAL.allows("夜", day) is False)
chk("门槛语义：多个 = 任一命中", CAL.allows(["昼", "夜"], day) is True)
chk("门槛语义：认不出的名字 = 不过（不静默放过）", CAL.allows("傍晚", day) is False)

# ⑨ ★ 跨日：档上只记游戏日；跨日把日计数清掉
p = {"day": None, "flags": {"gather_used": {"gt_x": 2}}}
CAL.tick(p)
chk("tick 把「今天」记到档上", p["day"] == night["game_day"], "day=%s" % p["day"])
p2 = dict(p)
CAL.tick(p2)
chk("同一天再 tick：不清日计数", (p2["flags"] or {}).get("gather_used") == {"gt_x": 2})
CAL.facade.bind_host(clock=lambda: FIXED + SCALE * 2)     # 换钟（模拟第二天）
CAL.tick(p)
chk("★ 跨（游戏）日：日计数归零", not (p["flags"] or {}).get("gather_used"),
    "day=%s flags=%s" % (p["day"], p["flags"]))
CAL.facade.bind_host(clock=lambda: FIXED)                 # 还原

# ⑩ ★ 接线真生效（真调消费端，不看代码看不出来）
at_wall_night = [k for k, _v in cmds_ast._npcs_here("windmill_town", "wt_wall", night)]
at_wall_day = [k for k, _v in cmds_ast._npcs_here("windmill_town", "wt_wall", day)]
chk("★ NPC 出场随时辰变（哈根：夜在墙根、昼不在）",
    at_wall_night == ["npc_hagen"] and at_wall_day == [], "夜 %s / 昼 %s" % (at_wall_night, at_wall_day))
derrick = (CAL._d("dialogues") or {}).get("dlg_derrick", {}).get("nodes", {}).get("daily", {}).get("texts", [])
rain_st = dict(day, weather="w_rain")
line_rain = cmds_talk._pick_line(derrick, {}, rain_st)
line_day = cmds_talk._pick_line(derrick, {}, day)
chk("★ 对话按时辰/天气择优（德里克的雨天那句只在雨天出）",
    line_rain != line_day and line_rain and "雨" in line_rain, "%s" % str(line_rain)[:24])
gid, pt = "gt_be_herb_1", (CAL._d("gathering") or {})["gt_be_herb_1"]
chk("★ 采集门槛：那条雨后才长的菌，晴天采不到",
    CAL.allows(pt.get("time"), rain_st) and not CAL.allows(pt.get("time"), day), "门槛=%s" % pt.get("time"))

# ── ⑪ ★ 审计 L1058：保底锚点**单一真源**（`RAIN_ID` 那一格，不许函数体里再写一遍字面量）——
#   病根：`weather_of` 的 `while weather_raw(r) != "w_rain"` / `return "w_rain"` 两行把锚点
#   **硬编在函数体里**，而 `RAIN_ID = "w_rain"` 就声明在下面几行 ⇒ 同一个锚点两个名字。
#   真实代价 = **整进程挂死**，不是「不优雅」：锚点改名（合法编辑）时
#   `weather_weights` 的 `if RAIN_ID not in wmap` 仍**绿**（域里当然有那一档），
#   而这个 while 认不出雨 ⇒ 一路 `r -= 1` 无下界回溯（L1083 的铁证形态；
#   L1059 补的出口校验只挡「域里没这一档」、**挡不住「锚点改名」**）。
#   三条：① 静态：函数体里不再有 `"w_rain"` 字面量，锚点一律走 `RAIN_ID`
#        ② 行为：注入「域里雨那档改名 + RAIN_ID 跟着改」⇒ **必须在有界时间内返回**
#           （改前 = 挂死；用子进程跑，不许把本探针自己拖死）
#        ③ 注入的域文件必须逐字节复原（探针不许留脏数据）
_src_cal = io.open(os.path.join(REPO, "content", "calendar.py"), encoding="utf-8").read()
# ★ 只看**函数体**：`def weather_of` 到下一个顶格行（下一个 def / 常量赋值）之间。
#   第一版取固定 4000 字，会把下面那行 `RAIN_ID = "w_rain"` 一并吃进来
#   ⇒ 判据把自己的真源判成「残留」= 假红（当场自纠）。
_lines = _src_cal.splitlines()
_i0 = next(i for i, l in enumerate(_lines) if l.startswith("def weather_of"))
_body = []
for _l in _lines[_i0 + 1:]:
    if _l and not _l[0].isspace():            # 顶格 ⇒ 已出函数体
        break
    _body.append(_l)
_lit = [l.strip()[:64] for l in _body
        if '"w_rain"' in l and not l.strip().startswith("#")]
chk("★ ① `weather_of` 函数体里不再硬编锚点字面量（残留 %s）—— 单一真源 = RAIN_ID"
    % (_lit or "无"), not _lit)

# ② 行为：把「域里雨那档改名 + RAIN_ID 跟着改」塞进**子进程**跑（有界超时）。
#    真跑本函数（不在探针里重写一遍算法），锚点已单源 ⇒ 认得出新锚点 ⇒ 立刻返回。
import json as _json
import subprocess as _sp
_WP = os.path.join(REPO, "content", "data", "weather.json")
_orig_w = io.open(_WP, encoding="utf-8", newline="").read()
_new_anchor = "w_rain_renamed"
_CHILD = (
    "import sys, os\n"
    "os.chdir(%r); sys.path.insert(0, %r)\n"
    "from content import calendar as CAL\n"
    "CAL.RAIN_ID = %r\n"
    "try:\n"
    "    print(CAL.weather_of(252))\n"
    "except Exception as e:\n"
    "    print('RAISED:' + type(e).__name__)\n" % (REPO, REPO, _new_anchor)
)
try:
    _d = _json.loads(_orig_w)
    _d[_new_anchor] = _d.pop("w_rain")
    io.open(_WP, "w", encoding="utf-8", newline="").write(
        _json.dumps(_d, ensure_ascii=False, indent=2))
    try:
        _r = _sp.run([sys.executable, "-c", _CHILD], capture_output=True, timeout=25)
        _out = _r.stdout.decode("utf-8", "replace").strip()
        _ok = bool(_out) and not _out.startswith("Traceback")
    except _sp.TimeoutExpired:
        _out, _ok = "25s 未返回（无下界回溯 = 整进程挂死）", False
finally:
    io.open(_WP, "w", encoding="utf-8", newline="").write(_orig_w)
chk("★ ② 锚点改名后**有界返回**（注入：域里雨那档改 id + RAIN_ID 跟着改 ⇒ %s）"
    "—— 改前这一档挂死" % _out, _ok)
chk("★ ③ 域文件注入后逐字节复原（探针不许留脏数据）",
    io.open(_WP, encoding="utf-8", newline="").read() == _orig_w, "长度 %d" % len(_orig_w))

print()
print("结果：%s" % ("全绿 ✓" if not fails else "有红 ✗（%d）" % len(fails)))
sys.exit(1 if fails else 0)
