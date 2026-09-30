# -*- coding: utf-8 -*-
"""探针：世界事件（B3-5 · 第 26 个）—— 三尺度（世界 / 限时 / 每日）+ 四个消费端 + 宿主插口。

为什么有它
----------
B3-2 轮次核过：19 §D 世界动静的效果栏**一个消费端都没有**（P-16）。这一批把三个接上、
一个诚实标出来，本探针就是那件事的判据（★ 规格来自 29 §七⑧）：

  ① 每条事件都能算出当下成不成立（**可复现**：注入假钟）
  ② ★ 效果栏的**每个键都有消费端** —— ★ 本批之后**四个键全接**（`price_mul` 那一格
     由 P-16 收口：B4-15 落了铺子 ⇒ 判定口 `calendar.price_mul` + 消费端 `shop` 买价）
  ③ 注入假钟跨「集日边界」⇒ 判定翻转（边界可测）

判据（逐条）
------------
  ① 域形状：4 条 · 字段齐 · scale 与 ASCII 尺度键一一对应
  ② ★ 域 = 从**设计案 §五 表**解析来的（重跑生成器解析的产物与域逐条相同）
  ③ ★ 跨域对账：文案槽位 / 图 / 节点 / npc / 天气 / 委托 都是真件
  ④ ★ 假钟：每条事件算得出 · 同一天两次一致（可复现）
  ⑤ ★ 边界：集日（每 7 日 · 持续 1 日）与初雪（第 20 日起 · 持续 3 日）的窗头 / 窗尾逐日扫
  ⑥ 世界级是一对互补开关（主线 3 前 / 后）
  ⑦ 每日尺度可算（第一阶段数据里没有每日条目 —— 注入一条假的证明那条路）
  ⑧ ★ 消费端 ④ NPC 出场：真宿主两趟（主线 3 前 / 后）+ 两个口（观察 / 去）同源
  ⑨ ★ 消费端 ③ 场地：集日那天挂板墙多两位「临时在场」，那两位**不在**原处
  ⑩ ★ 消费端 ② 遇敌：没给 mul = 与改前逐字相同；给了 mul = 分布真偏
  ⑪ ★ 消费端 ① 物价：四个效果键**全接了**（待接清单空）· 注入一条 `price_mul` = 1.25 的
     假事件 ⇒ 每件买价 ×1.25、收价不动；拿掉 ⇒ 回 1.0（没给 = 零变化）· 静态守卫：
     `price_mul` 只许在 `calendar.py`（判定口）与 `shop.py`（消费端）出现
  ⑫ 初雪那 3 天：天气权重真变（消费端 `weather_weights`），别天原样
  ⑬ 文案：事件与「异动」的字**逐字**取自 texts 槽位
  ⑭ ★ 宿主插口：`timed_events` 半边取得到 + `refresh_timed` 真调一次不抛 · **幂等** ·
     没玩家 / 没事件 ⇒ 零动作 · 坏了也不抛
  ⑮ ★ 闭环：维护门落的那一格真被「异动」读（新开的 / 收了）
  ⑯ 对话层 `need.event` 真被点亮（贝拉那句只在商队到了之后出）
  ⑰ ★ 门槛名守卫：数据里所有 `condition.event` / `need.event` 都是**真事件 id**
  ⑱ ★ 源码守卫：`_npcs_here` 的每个调用点都把档传进去（防「两处口径」）

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_events.py
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
PLAN = os.environ.get("AST_PLAN", "C:/Users/yuyu/aetheran-plan")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402
from saintess_engine.host.runtime import Host                        # noqa: E402
from saintess_engine.command import CommandRegistry                  # noqa: E402

import rebuild_events as RE                                          # noqa: E402

DB = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_events.db")
TMP = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp")

ok = True


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


# ── 假钟（刻度从 calendar 域读，不手打 7200）────────────────────
_CAL_JSON = json.loads((REPO / "content" / "data" / "calendar.json").read_text(encoding="utf-8"))
_SCALE = int(_CAL_JSON["_clock"]["real_seconds_per_game_day"])


def epoch_at(day, hod=12.0):
    """第 day 个游戏日的 hod 点（现实 epoch 秒）。"""
    return (day * 86400.0 + hod * 3600.0) * _SCALE / 86400.0


print("探针：世界事件（B3-5 · 三尺度 + 四个消费端 + 宿主插口）")

st = load_stack(str(REPO), inject={"db_path": DB, "clock": lambda: epoch_at(100, 21.0)})
st.install()

from content import calendar as CAL                                   # noqa: E402
from content import cmds_ast as CA                                    # noqa: E402
from content.cmds_ast import _data                                    # noqa: E402  ★ #46：域读口（与 content 同一个）
from content import cmds_talk as CT                                   # noqa: E402
from content import combat as CB                                      # noqa: E402
from content import timed_events as TE                                # noqa: E402
from content import facade as FC                                      # noqa: E402
from content import persistence as PS                                 # noqa: E402

EV = CAL.events()
TX = _data("texts")
MAPS = _data("maps")
NPCS = _data("npcs")
WX = CAL.weathers()
QS = _data("quests")

print("① 域形状")
chk("events 域读得到（4 条 · 第一阶段）", len(EV) == 4, " · ".join(EV))
FIELDS = ("no", "name", "scale", "scale_key", "period", "text", "where", "effects", "source", "look")
bad = [k for k, v in EV.items() if [f for f in FIELDS if f not in v]]
chk("每条都有 %d 个字段（含 ASCII 尺度键 · 可追溯的 look/source）" % len(FIELDS), not bad, bad)
PAIR = {"世界": "world", "限时": "timed", "每日": "daily"}
bad2 = sorted(k for k, v in EV.items() if PAIR.get(v["scale"]) != v["scale_key"])
chk("★ scale（中文·玩家看）与 scale_key（ASCII·代码比值）一一对应（P-20 家族）", not bad2, bad2)
chk("no 是 1..4 连号", sorted(v["no"] for v in EV.values()) == list(range(1, len(EV) + 1)))

print("② ★ 域 = 从设计案 §五 表解析来的（生成物对账）")
try:
    fresh = {k: v for k, v in RE.build().items() if not str(k).startswith("_")}
    same = fresh == {k: v for k, v in EV.items()}
    chk("★ 重跑生成器解析出来的四条与域里逐字段相同", same,
        "" if same else sorted(set(fresh.items()) ^ set(EV.items()))[:2])
except SystemExit as exc:                                              # 设计案不在 / 认不出触发串
    chk("★ 重跑生成器解析出来的四条与域里逐字段相同", False, exc)
chk("★ 域里记着生成物身份（source + generator · 可追溯）",
    "29_世界事件_设计_v1.md" in str(_data("events").get("_meta", {}).get("source"))
    and bool(_data("events")["_meta"].get("generator")),
    _data("events")["_meta"].get("generator", "")[:40])

print("③ ★ 跨域对账：文案槽位 / 图 / 节点 / npc / 天气 / 委托 都是真件")
bad3 = []
for eid, v in EV.items():
    if v["text"] not in TX:
        bad3.append("%s.text=%s" % (eid, v["text"]))
    for m in v["where"]:
        if m not in MAPS:
            bad3.append("%s.where=%s" % (eid, m))
    c = (v["effects"] or {}).get("crowd") or {}
    if c:
        nodes = [n["id"] for n in (MAPS.get(v["where"][0]) or {}).get("nodes") or []]
        if c.get("node") not in nodes:
            bad3.append("%s.crowd.node=%s" % (eid, c.get("node")))
        bad3 += ["%s.crowd.npc=%s" % (eid, n) for n in c.get("npcs") or [] if n not in NPCS]
        if c.get("text") not in TX:
            bad3.append("%s.crowd.text=%s" % (eid, c.get("text")))
    for wid, mul in ((v["effects"] or {}).get("weather_mul") or {}).items():
        if wid not in WX:
            bad3.append("%s.weather_mul=%s" % (eid, wid))
        if int(mul) < 2:
            bad3.append("%s.weather_mul 倍数 <2（「拉长」得真拉长）" % eid)
    for key in ("from_main", "until_main"):
        q = (v["period"] or {}).get(key)
        if q and (q not in QS or QS[q].get("chain") != "main"):
            bad3.append("%s.%s=%s" % (eid, key, q))
chk("★ 所有引用都是真件（槽位 / 图 / 节点 / npc / 天气 / 主线委托）", not bad3, bad3)

print("④ 假钟：每条事件算得出 · 可复现")
day = 7
st7 = CAL.state(epoch_at(day))
chk("★ 第 %d 游戏日：四条事件都能判" % day,
    all(isinstance(CAL.event_on(eid, st7, {}), bool) for eid in EV))
chk("★ 可复现：同一天两次 = 同一结果（含窗键）",
    CAL.events_now(st7, {}) == CAL.events_now(st7, {}) and CAL.on_keys(st7, {}) == CAL.on_keys(st7, {}),
    CAL.on_keys(st7, {}))
chk("认不出的事件名 = False（fail-closed，不许静默成立）", CAL.event_on("ev_nope", st7, {}) is False)

print("⑤ ★ 边界：窗头 / 窗尾逐日扫（判定与 period 的算术一致）")
mk = lambda d: CAL.state(epoch_at(d))
mk_on = lambda d, eid: CAL.event_on(eid, mk(d), {})
market = sorted(d for d in range(0, 29) if mk_on(d, "ev_market_day"))
snow = sorted(d for d in range(0, 30) if mk_on(d, "ev_first_snow"))
chk("★ 集日：每 7 日一次 · 只 1 日（0/7/14/21/28）", market == [0, 7, 14, 21, 28], market)
chk("★ 初雪：第 20 日起 3 日（20/21/22 —— 23 日起收）", snow == [20, 21, 22], snow)
chk("★ 跨边界翻转：集日 6→7 开 / 7→8 收；初雪 19→20 开 / 22→23 收",
    (not mk_on(6, "ev_market_day")) and mk_on(7, "ev_market_day") and (not mk_on(8, "ev_market_day"))
    and (not mk_on(19, "ev_first_snow")) and mk_on(20, "ev_first_snow") and not mk_on(23, "ev_first_snow"))

print("⑥ 世界级：一对互补开关（主线 3 前 / 后）")
p_before, p_after = {}, {"flags": {"quests_done": ["q_main_03"]}}
p_after2 = {"flags": {"quests": {"q_main_03": {"step": 3, "done": True}}}}
chk("★ 主线 3 之前：商队在路上 成立 · 商队到了 不成立",
    CAL.event_on("ev_caravan", st7, p_before) and not CAL.event_on("ev_caravan_arrived", st7, p_before))
chk("★ 主线 3 之后：反过来（两个键都要认：quests_done 与 quests.<id>.done）",
    CAL.event_on("ev_caravan_arrived", st7, p_after) and not CAL.event_on("ev_caravan", st7, p_after)
    and CAL.event_on("ev_caravan_arrived", st7, p_after2) and not CAL.event_on("ev_caravan", st7, p_after2))
chk("★ 世界级不看游戏日（第 7 天与第 99 天同结论）",
    CAL.event_on("ev_caravan", st7, p_before) == CAL.event_on("ev_caravan", mk(99), p_before))

print("⑦ 每日尺度：那条路可算（第一阶段数据里没有每日条目）")
EVRAW = _data("events")                                    # ★ 缓存里的那张表本体（`cmds_ast._CACHE` —— 注入要动它）
EVRAW["ev_probe_daily"] = {"no": 99, "name": "probe", "scale": "每日", "scale_key": "daily",
                           "period": {"daily": True}, "text": "SYS_EV_NONE", "where": [], "effects": {}}
try:
    chk("★ 注入一条每日事件 ⇒ 每天成立、窗键按天（每天重来）",
        CAL.event_on("ev_probe_daily", st7, {}) is True
        and CAL.window_key("ev_probe_daily", st7) == "ev_probe_daily:d:" + CAL.day_key(7)
        and CAL.event_on("ev_probe_daily", mk(8), {}) is True)
    chk("★ 每日事件：两天两个窗键（跨日就是新的一格）",
        CAL.window_key("ev_probe_daily", st7) != CAL.window_key("ev_probe_daily", mk(8)))
finally:
    EVRAW.pop("ev_probe_daily", None)
chk("★ 第一阶段数据里**没有**每日条目（29 §二：那层归时辰 / 对话 need）",
    not [k for k, v in EV.items() if v.get("scale_key") == "daily"])


# ── 真宿主：假钟 + 真契约（出场条件 / 场地 两条消费端）──────────
class _Ad(object):
    """三函数 + say（照 host-api 契约的最小适配器 —— 与 scripts/e2e_drive.py 同形）。"""

    def __init__(self, texts, seed=None):
        self._msgs = [{"uid": "u_ev", "group_id": "g_ev", "text": t, "is_group": True} for t in texts]
        self.out = []
        self.saved = seed

    def recv(self):
        return self._msgs.pop(0) if self._msgs else None

    def load_player(self, uid):
        if uid != "u_ev":
            return None
        d = dict(self.saved or {})
        d.setdefault("race", "human")           # 定过族（否则「观察」第一眼是选族菜单）
        d.setdefault("cls", "cls_knight")       # ★ 2026-09-30：注册守卫 —— 建号走完才到得了玩
        d.setdefault("name", "试刀")
        return d

    def save_player(self, uid, data):
        self.saved = dict(data) if isinstance(data, dict) else data

    def say(self, to, text):
        self.out.append(str(text))


STEPS = ["去 挂板墙", "观察", "去 北口", "观察"]


def run_at(day, seed=None, steps=STEPS, tag="x"):
    """真宿主 + 假钟：走一遍，回 {敲的词: [回话]}（去/观察 同名两次的按出现序存 list）。"""
    db = os.path.join(TMP, "ast_probe_events_%s.db" % tag)
    try:
        os.remove(db)
    except OSError:
        pass
    ad = _Ad(steps, seed=seed)
    host = Host(ad, str(REPO), inject={"db_path": db, "clock": (lambda: epoch_at(day, 12.0))})
    host.boot()
    got = []
    for t in steps:
        ad.out.clear()
        host.handle({"uid": "u_ev", "group_id": "g_ev", "text": t})
        got.append((t, list(ad.out)))
    return got


def _who(lines):
    """「人在：…」那一行（没有给空串）。"""
    return next((x for x in lines if x.startswith("人在：")), "")


def _first(out, text):
    return next((ls for t, ls in out if t == text), [])


print("⑧ ★ 消费端 ④ NPC 出场（真宿主 + 假钟两趟 · 两个口同源）")
try:
    before = run_at(7, tag="before")                       # 主线 3 未过
    after = run_at(7, seed={"race": "human", "flags": {"quests_done": ["q_main_03"]}}, tag="after")
    lbl = [x for x in before if x[0] == "观察"][-1][1]      # 最后一次「观察」= 在北口
    lb2 = _who(_first(before, "去 北口"))
    chk("★ 主线 3 之前：北口不列瑟兰 / 格雷（两个口都不列）",
        "瑟兰" not in "".join(lbl) and "格雷" not in "".join(lbl)
        and "瑟兰" not in lb2 and "格雷" not in lb2, [lbl[:2], lb2])
    chk("★ 主线 3 之前：杜林在（商队在路上 · 那位矮人一直在）", "杜林" in lb2, lb2)
    la = [x for x in after if x[0] == "观察"][-1][1]
    la2 = _who(_first(after, "去 北口"))
    chk("★ 主线 3 之后：北口列瑟兰（两个口都列）",
        "瑟兰" in "".join(la) and "瑟兰" in la2, [la[1:2], la2])
    _go = {t: _who(x) for t, x in before if t.startswith("去 ")}
    _ob = [_who(x) for t, x in before if t == "观察"]
    chk("★ 「观察」与「去」的人名单同源（同一站两趟逐字一致）",
        _go.get("去 挂板墙") == _ob[0] and _go.get("去 北口") == _ob[1], [_go, _ob])
except Exception as exc:                                   # noqa: BLE001 —— 起不来就是红
    chk("★ 真宿主端到端跑得起来（出场条件那条线）", False, "%s: %s" % (type(exc).__name__, exc))

print("⑨ ★ 消费端 ③ 场地（集日：那两位被吸到挂板墙）")
try:
    m7 = run_at(7, tag="m7")                                # 第 7 天 = 集日
    m8 = run_at(8, tag="m8")                                # 第 8 天 = 平常
    board7 = _first(m7, "去 挂板墙")
    board8 = _first(m8, "去 挂板墙")
    gate7 = _who(_first(m7, "去 北口"))
    gate8 = _who(_first(m8, "去 北口"))
    chk("★ 集日：挂板墙那站多两位（小满 / 老陶）", "小满" in _who(board7) and "老陶" in _who(board7), _who(board7))
    chk("★ 集日：那两位**不在**原处（北口没有小满）", "小满" not in gate7, gate7)
    chk("★ 集日：这一站多一行「挤」（槽位的字逐字在）",
        any(TX["SYS_EV_MARKET_CROWD"]["value"] == x for x in board7), board7[-2:])
    chk("★ 非集日（第 8 天）：挂板墙不多人、小满回北口",
        "小满" not in _who(board8) and "老陶" not in _who(board8) and "小满" in gate8,
        [_who(board8), gate8])
    chk("★ 集日那条「集日」表征进镇就看得到（从野外踏进镇那一下）",
        any(TX["SYS_EV_MARKET"]["value"] == x for x in
            run_at(7, seed={"race": "human", "loc": "belt_north", "node": "bn_bone"},
                   steps=["进镇"], tag="in7")[0][1]))
except Exception as exc:                                   # noqa: BLE001
    chk("★ 真宿主端到端跑得起来（场地那条线）", False, "%s: %s" % (type(exc).__name__, exc))

print("⑩ ★ 消费端 ② 遇敌权重（没给 = 零变化 · 给了 = 真偏）")
MS = _data("monsters")
BEST, TOP = None, []
for mk_, mv in MAPS.items():
    for n in mv.get("nodes") or []:
        # ★ B3-6b-2d-keys-2：候选闸照**代码那份 ASCII `role_key`** 重算（原先用中文 kind）
        cand = [k for k, m in MS.items()
                if m.get("role_key") in ("normal", "elite", "chief")
                and mk_ in ((m.get("habitat") or {}).get("maps") or [])]
        if len(cand) >= 3 and (BEST is None or len(cand) > len(BEST[2])):
            BEST = (mk_, n["id"], cand)
if BEST:
    loc, node, cand = BEST
    lvl = min(int(MS[k].get("lv", 1)) for k in cand)
    top = sorted(cand, key=lambda k: abs(int(MS[k]["lv"]) - lvl))[:3]
    same = [CB.pick_encounter(MS, loc, node, lvl, seed=s) for s in range(50)]
    same2 = [CB.pick_encounter(MS, loc, node, lvl, seed=s, mul=None) for s in range(50)]
    chk("★ 没给 mul = 与改前逐字相同（同一个种子同一只 · 50 个种子）", same == same2, same[:2])
    tgt = top[-1]
    N = 400
    base = [CB.pick_encounter(MS, loc, node, lvl, seed=i)[0] for i in range(N)]
    with_ = [CB.pick_encounter(MS, loc, node, lvl, seed=i, mul={tgt: 8})[0] for i in range(N)]
    share0 = base.count(tgt) / float(N)
    share1 = with_.count(tgt) / float(N)
    chk("★ 给了 mul（%s ×8）：它被挑中的比例真上升（期望 ≈ 8/(8+2)）" % MS[tgt].get("name"),
        share1 > 0.65 and share0 < 0.55,
        "改前 %.0f%% → 改后 %.0f%%（%s / %s）" % (100 * share0, 100 * share1, loc, node))
    zero = [CB.pick_encounter(MS, loc, node, lvl, seed=i, mul={tgt: 0})[0] for i in range(200)]
    chk("★ 倍数为 0 的候选挑不中（权重真的参与挑选）", tgt not in zero)
else:
    chk("★ 找得到一张图有三个候选（遇敌用例的前提）", False, "没有候选 ≥3 的地点")

print("⑪ ★ 消费端 ①：物价倍数 `price_mul` **已接**（P-16 收口）—— 真生效，不是「没人读」")
#: 四个效果键的**消费者登记表** —— 这是 29 §七⑧ 要的那一份（每个键都要有消费端）
CONSUMED = {"crowd": "cmds_ast._npcs_here / event_lines", "weather_mul": "calendar.weather_weights",
            "encounter_mul": "combat.pick_encounter",
            "price_mul": "calendar.price_mul → shop 买价（content/shop.py）"}
#: ★ P-16 收口：待接清单**空了**（B4-15 落了铺子之后，物价这一格终于有地方生效）
PENDING = {}
used = sorted({k for v in EV.values() for k in (v.get("effects") or {})})
chk("★ 效果栏用到的键都在「消费者登记表」里（已接 %d 个 · 待接 %d 个）"
    % (len(CONSUMED), len(PENDING)),
    set(used) <= set(CONSUMED) | set(PENDING), sorted(set(used) - set(CONSUMED) - set(PENDING)))
chk("★ 待接清单**空了**：四个效果键（crowd / weather_mul / encounter_mul / price_mul）"
    "每一个都有消费端 —— P-16 当初诚实留的那一个今天收口", not PENDING, sorted(PENDING))
chk("★ 数据里今天一条都没写 `price_mul`（29 §五 那四条不含物价类）—— 「现在没生效」是数据的"
    "样子，不是「没人读」：下面那条注入就证明谁写进来谁真生效",
    not [k for k, v in EV.items() if "price_mul" in (v.get("effects") or {})])

#: ★ 真生效那一半（P-16 的判据）：注入一条**带 price_mul 的假事件** ⇒ 买价按倍数涨、收价不动；
#:   拿掉 ⇒ 回 1.0 / 原价（「没给 = 零变化」那一档）。
from content import shop as SHP                                          # noqa: E402
_PM18 = 1.25                       # 「价格 +25%」（例值；真源 21 §二 那一行写的是 +20%）
_base_pm18 = CAL.price_mul(st7, {})
_base_shelf18 = [(g["id"], g["gold"], int(g["rec"]["price"])) for g in SHP.goods({})]
EVRAW["ev_probe_price18"] = {"no": 98, "name": "probe", "scale": "每日", "scale_key": "daily",
                             "period": {"daily": True}, "text": "SYS_EV_NONE", "where": [],
                             "effects": {"price_mul": _PM18}}
try:
    _on_pm18 = CAL.price_mul(st7, {})
    _on_shelf18 = [(g["id"], g["gold"], int(g["rec"]["price"])) for g in SHP.goods({})]
finally:
    EVRAW.pop("ev_probe_price18", None)
_off_pm18 = CAL.price_mul(st7, {})
_off_shelf18 = [(g["id"], g["gold"], int(g["rec"]["price"])) for g in SHP.goods({})]
chk("★ 真生效：注入 `price_mul` = %s ⇒ 判定口给 %s、**每一件买价都 ×%s**（收价一个字不动）"
    " 拿掉 ⇒ 回 %s / 原价（没给 = 零变化）" % (_PM18, _on_pm18, _PM18, _off_pm18),
    _base_pm18 == 1.0 and abs(_on_pm18 - _PM18) < 1e-9
    and [g for _i, g, _p in _on_shelf18] == [int(round(g * _PM18)) for _i, g, _p in _base_shelf18]
    and [p for _i, _g, p in _on_shelf18] == [p for _i, _g, p in _base_shelf18]
    and abs(_off_pm18 - 1.0) < 1e-9 and _off_shelf18 == _base_shelf18,
    "%s → %s → %s" % (_base_pm18, _on_pm18, _off_pm18))
_src18 = {p.name: p.read_text(encoding="utf-8") for p in (REPO / "content").glob("*.py")}
_who18 = sorted(n for n, s in _src18.items() if "price_mul" in s)
chk("★ 静态：`price_mul` 只有「判定口 + 消费端」两处 —— %s（谁再自己扫一遍 events 域算物价，这里红）"
    % " · ".join(_who18), _who18 == ["calendar.py", "shop.py"], _who18)

print("⑫ 初雪的天气加权（消费端真吃到了）")
base_w = {wid: int(v["weight"]) for wid, v in WX.items()}
snow_id = next(k for k in WX if (TX.get(WX[k].get("slot")) or {}).get("value") == "初雪")
chk("★ 初雪那 3 天：「初雪」的权重按数据里那个倍数抬起来",
    CAL.weather_weights(20)[snow_id] == base_w[snow_id] * 2
    and CAL.weather_weights(21)[snow_id] == base_w[snow_id] * 2
    and CAL.weather_weights(22)[snow_id] == base_w[snow_id] * 2,
    "%s → %s" % (base_w[snow_id], CAL.weather_weights(20)[snow_id]))
chk("★ 别天原样（窗头前 / 窗尾后都不动）",
    CAL.weather_weights(19) == base_w and CAL.weather_weights(23) == base_w)
chk("★ 天气仍是决定论（同一天两次同一个天气 · 窗里也一样）",
    len({CAL.weather_of(20), CAL.weather_of(20), CAL.weather_of(20)}) == 1
    and len({CAL.weather_of(999) for _ in range(5)}) == 1)

print("⑬ 文案：事件与「异动」的字逐字取自槽位")
import asyncio                                                          # noqa: E402


class _E(object):
    def __init__(self, text=""):
        self.text = text

    def save(self):
        pass


def drive_event_now(p):
    out = []

    async def go():
        async for line in CA.event_now(_E(""), None, "u_ev", p):
            out.append(str(line))
    asyncio.run(go())
    return out


_p7 = dict(CA.DEFAULT_PLAYER, flags={})
_fake = dict(CA.DEFAULT_PLAYER, flags={"ev": {"day": 7, "on": [], "prev_day": 6,
                                              "prev_on": ["ev_first_snow:w:g00000020:3"]}})
FC.bind_host(clock=lambda: epoch_at(7, 12.0))          # 「异动」里的 CAL.tick 也走这根假钟
lines = drive_event_now(_p7)
on7 = CAL.events_now(st7, {})
chk("★ 头的槽位在 + 每条成立的事件的表征槽位都在行里（一个字都不在代码里）",
    TX["SYS_EV_HEAD"]["value"] in lines
    and all(any(TX[EV[r["id"]]["text"]]["value"] in x for x in lines) for r in on7), lines)
chk("★ 「异动」按世界 → 限时 排（商队在路上 那行在 集日 那行前面）",
    [i for i, x in enumerate(lines) if TX["SYS_EV_CARAVAN"]["value"] in x][0]
    < [i for i, x in enumerate(lines) if TX["SYS_EV_MARKET"]["value"] in x][0], lines)
lines2 = drive_event_now(_fake)
chk("★ 落过档（今天刷的）⇒ 新开的标出来 · 上一格开着的说「收了」",
    TX["SYS_EV_ROW_NEW"]["value"].format(name="集日", text=TX["SYS_EV_MARKET"]["value"]) in lines2
    and TX["SYS_EV_GONE"]["value"].format(name="初雪") in lines2, lines2)

print("⑭ ★ 宿主插口：timed_events 半边（宿主每轮按名取它）")
half = st.optional_submodule("timed_events")
chk("★ `optional_submodule(\"timed_events\")` 真取得到（宿主 `_sub` 的那一口）", half is not None)
chk("★ 半边有 `refresh_timed(group_id, qq_id)`", callable(getattr(half, "refresh_timed", None)))
edb = os.path.join(TMP, "ast_probe_events_refresh.db")
try:
    os.remove(edb)
except OSError:
    pass
FC.bind_host(db_path=edb, clock=lambda: epoch_at(8, 12.0))
PS.init_db()
r_none = TE.refresh_timed("g_ev", "u_absent")
chk("★ 没玩家 ⇒ 零动作（不抛 · 也不给他建档）",
    r_none.get("changed") is False and PS.get_player("g_ev", "u_absent") is None, r_none)
PS.update_player("g_ev", "u1", race="human", flags={})
r1 = TE.refresh_timed("g_ev", "u1")
r2 = TE.refresh_timed("g_ev", "u1")
snap = TE.snapshot(PS.get_player("g_ev", "u1"))
chk("★ 第一次调真落档（今天开着哪些窗）", r1.get("changed") is True, r1)
chk("★ ★ 幂等：同一个窗里再调 ⇒ 零写入（第二次 changed=False、档逐字段没动）",
    r2.get("changed") is False and snap.get("day") == 8
    and TE.snapshot(PS.get_player("g_ev", "u1")) == snap, r2)
FC.bind_host(clock=lambda: epoch_at(14, 12.0))          # 跨窗（第 14 天又是一个集日）
r3 = TE.refresh_timed("g_ev", "u1")
snap3 = TE.snapshot(PS.get_player("g_ev", "u1"))
chk("★ 跨窗 ⇒ 推一格，且把上一格留在 `prev_on`（呈现口要它）",
    r3.get("changed") is True and snap3.get("day") == 14 and len(snap3.get("prev_on") or []) >= 1, snap3)
_saved = dict(PS.player_handles())
FC.bind_host(db_path=TMP)                      # 指一个**目录**（连不上库 —— 真坏一回）
r_bad = TE.refresh_timed("g_ev", "u1")
FC.bind_host(db_path=_saved["db_path"])
chk("★ ★ 绝不抛：库连不上 / 参数烂也回一个 dict（宿主那条 WARN 不该被触发）",
    isinstance(r_bad, dict) and r_bad.get("changed") is False
    and isinstance(TE.refresh_timed(None, None), dict)
    and isinstance(TE.refresh_timed("g", object()), dict), r_bad)

print("⑮ ★ 闭环：维护门落的那一格真被「异动」读")
EV_SAVE = dict(PS.get_player("g_ev", "u1") or {})
FC.bind_host(db_path=edb, clock=lambda: epoch_at(7, 12.0))
PS.update_player("g_ev", "u1", flags={})
TE.refresh_timed("g_ev", "u1")                      # 第 7 天第一次上线：集日刚开
p_live = dict(CA.DEFAULT_PLAYER, **PS.get_player("g_ev", "u1"))
l7 = drive_event_now(p_live)
TE_off = TC_off = None
FC.bind_host(clock=lambda: epoch_at(8, 12.0))
TE.refresh_timed("g_ev", "u1")                      # 第 8 天：集日收了
FC.bind_host(clock=lambda: epoch_at(8, 12.0))
p_live8 = dict(CA.DEFAULT_PLAYER, **PS.get_player("g_ev", "u1"))
l8 = drive_event_now(p_live8)
chk("★ 集日刚开那一下，「异动」把它标成「今天新开的」",
    TX["SYS_EV_ROW_NEW"]["value"].format(name="集日", text=TX["SYS_EV_MARKET"]["value"]) in l7, l7)
chk("★ 第二天（收了）：「异动」说「集日 —— 收了。」且不再标新开",
    TX["SYS_EV_GONE"]["value"].format(name="集日") in l8
    and TX["SYS_EV_ROW_NEW"]["value"].format(name="集日", text=TX["SYS_EV_MARKET"]["value"]) not in l8, l8)
FC.bind_host(clock=lambda: epoch_at(100, 21.0))      # 还原（后面还有用例）

print("⑯ 对话层 `need.event` 真被点亮（读端 = 事件层的唯一口 `CAL.event_on`）")
bl = (_data("dialogues") or {}).get("dlg_bella", {}).get("nodes", {}).get("daily", {}).get("texts", [])
i_before, _ = CT._pick_indexed(bl, {}, st7)
i_after, _ = CT._pick_indexed(bl, {"flags": {"quests_done": ["q_main_03"]}}, st7)
chk("★ 那句「今天杜林到了」只在**商队到了**之后出（没到：挑不到它 · 到了：头一句就是它）"
    "—— 原先读端读的是没人写的 `flags.event_<名字>`，2026-09-25 合入时补的三行之一",
    i_before != 0 and i_after == 0, [i_before, i_after])
chk("★ 但它的门槛名换成了**真事件 id**（数据侧先正过来 —— ⑰ 守着这一条）",
    ((bl[0].get("need") or {}).get("event") in EV), bl[0].get("need"))

print("⑰ ★ 门槛名守卫：数据里的事件名都是真事件 id")
toks = []
for k, v in NPCS.items():
    t = (v.get("condition") or {}).get("event")
    if t:
        toks.append(("npcs.%s" % k, t))
for dk, dv in (_data("dialogues") or {}).items():
    if not isinstance(dv, dict):
        continue
    for nk, nv in (dv.get("nodes") or {}).items():
        for ln in (nv.get("texts") or []):
            t = (ln.get("need") or {}).get("event")
            if t:
                toks.append(("dialogues.%s.%s" % (dk, nk), t))
bad17 = [(w, t) for w, t in toks if t not in EV]
chk("★ 数据里 %d 处事件门槛全部是真事件 id（认不出的当场红 —— 改前那个 `caravan` 就是没人判的）"
    % len(toks), bool(toks) and not bad17, bad17)

print("⑱ ★ 源码守卫：`_npcs_here` 的每个调用点都把档传进去（两处口径的根）")
#: ★ 2026-09-25 合入时那两处调用已补上档（原先是已知缺口，登记在 `_notes.md` §三）⇒ 现在**一处都不许缺**。
KNOWN_GAP = set()
srcs = {p.name: p.read_text(encoding="utf-8") for p in (REPO / "content").glob("*.py")}
calls, no_p, gap = [], [], []
for name, s in srcs.items():
    for m in re.finditer(r"_npcs_here\(", s):
        ls = s.rfind("\n", 0, m.start()) + 1
        head = s[ls:m.start()]
        tail = s[m.end():s.find("\n", m.end())]
        if head.rstrip().endswith("def"):           # 定义那一行不算调用点
            continue
        here = None
        for m2 in re.finditer(r"^(?:async\s+)?def\s+(\w+)", s, re.M):
            if m2.start() > m.start():
                break
            here = m2
        fn = here.group(1) if here else "?"
        calls.append((name, fn))
        if not (", p)" in tail or "p=p)" in tail):
            (gap if (name, fn) in KNOWN_GAP else no_p).append((name, fn, tail.strip()))
chk("★ %d 个调用点都传了档（`p` / `p=p`）—— 一处都不许缺（原来 talk / ask_way 那两处已补）" % len(calls),
    bool(calls) and not no_p and not gap, no_p or gap)

print()
print("事件速览（名字 · 尺度 · 窗 · 效果）:")
for eid, v in EV.items():
    print("  %-20s %-6s %-22s %s" % (eid, v["name"], json.dumps(v["period"], ensure_ascii=False),
                                     json.dumps(v["effects"], ensure_ascii=False)))
print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
EVRAW = _data("events")                                     # ★ 缓存里的那张表本体（`cmds_ast._CACHE`——注入要动它）
