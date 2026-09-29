# -*- coding: utf-8 -*-
"""探针：npcs 域（14 位 · 三卡齐全 · 位置真在图上 · 口头禅互不相同）。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_npcs.py
"""
from __future__ import annotations

import json
import os
import time
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402
from saintess_engine.host.runtime import Host                        # noqa: E402

ok = True
PERSONA_KEYS = ("look", "temper", "likes", "hates", "habit", "routine", "catch")
SOUL_KEYS = ("wants", "fears", "conflict", "why_here", "theme")
TONE_KEYS = ("words", "rhythm", "attitude", "focus", "pause")
FUNCS = {"inn", "shop", "smith", "strengthen", "heal", "revive", "quest", "board",
         "rank", "herb", "hint", "talk", "train", "appraise", "trade", "lore"}


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


print("探针：npcs 域（14 位）")
st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
st.install()
np_ = st.domain("npcs")
mp = st.domain("maps")
chk("npcs 域读得到", np_ is not None, "%d 位" % (len(np_) if np_ else 0))
chk("maps 域读得到（交叉校验要用）", mp is not None)
if not (np_ and mp):
    sys.exit(1)

chk("14 位齐全", len(np_) == 14, " · ".join(v["name"] for v in np_.values()))

# ① 三卡齐全
bad = [k for k, v in np_.items() if not all(f in v for f in ("persona", "soul", "tone"))]
chk("每位都有三卡（人设/灵魂/语气）", not bad, " · ".join(bad))

# ② 人设卡七项
bad2 = [k for k, v in np_.items() if not all(f in v.get("persona", {}) for f in PERSONA_KEYS)]
chk("人设卡七项齐全（含口头禅）", not bad2, " · ".join(bad2))

# ③ 灵魂卡五问
bad3 = [k for k, v in np_.items() if not all(f in v.get("soul", {}) for f in SOUL_KEYS)]
chk("灵魂卡五问齐全", not bad3, " · ".join(bad3))

# ④ 语气档五项
bad4 = [k for k, v in np_.items() if not all(f in v.get("tone", {}) for f in TONE_KEYS)]
chk("语气档五项齐全", not bad4, " · ".join(bad4))

# ⑤ ★ 跨域：位置真在图上
bad5 = []
for k, v in np_.items():
    ids = [n["id"] for n in mp.get(v.get("map"), {}).get("nodes", [])]
    if v.get("subarea") not in ids:
        bad5.append("%s → %s/%s" % (k, v.get("map"), v.get("subarea")))
chk("★ 每位的位置都在 maps 域的节点里", not bad5, " · ".join(bad5))

# ⑥ funcs 合法
bad6 = [k for k, v in np_.items() if set(v.get("funcs", [])) - FUNCS]
chk("funcs 取值都在约定集合里", not bad6, " · ".join(bad6))

# ⑦ ★ 品味判据：口头禅互不相同（每人有自己的腔）
catches = [v["persona"]["catch"] for v in np_.values()]
chk("★ 14 位口头禅互不相同", len(set(catches)) == 14, "%d 种" % len(set(catches)))

# ⑧ 灵魂卡的「矛盾」都写了（活人感的来源）
bad8 = [k for k, v in np_.items() if not v["soul"].get("conflict")]
chk("★ 每位都写了「矛盾」", not bad8, " · ".join(bad8))

# ⑨ dialogue id 唯一
dids = [v["dialogue"] for v in np_.values()]
chk("对话树 id 唯一", len(set(dids)) == len(dids))


# ⑩ ★ 出场条件：真宿主真敲 —— 「去 <节点>」与「观察」的人名单必须**同源**（B3-15）
#    哈根（npc_hagen）的条件 = 昏 / 夜 ⇒ 白天不该出现在任何一处的「人在」里。
#    改前实测：白天的 `去 北墙根` 照样列哈根（那一条自己扫域、不判条件），
#    而「观察」/「问路」不列 —— 同一个东西两处口径（K60 家族）。
_DAY, _NIGHT = 12, 21          # 昼 / 夜（窗界在 calendar 域，别在这儿手打时辰名）


def _epoch_at(day, hod):
    """第 day 个游戏日的 hod 点 —— 刻度从 calendar 域读（不手打 7200）。"""
    cal = json.loads((REPO / "content" / "data" / "calendar.json").read_text(encoding="utf-8"))
    scale = int(cal["_clock"]["real_seconds_per_game_day"])
    return (day * 86400.0 + hod * 3600.0) * scale / 86400.0


class _Ad(object):
    """三函数 + say（照 host-api 契约的最小适配器 —— 与 scripts/e2e_drive.py 同形）。"""

    def __init__(self, texts):
        self._msgs = [{"uid": "u_n", "group_id": "g_n", "text": t, "is_group": True} for t in texts]
        self.out = []
        self.saved = None

    def recv(self):
        return self._msgs.pop(0) if self._msgs else None

    def load_player(self, uid):
        if uid != "u_n":
            return None
        # ★ P-10：档上要有族（否则「观察」第一眼变成选族菜单）
        d = dict(self.saved or {})
        d.setdefault("race", "human")
        # ★ 2026-09-30（注册面改造）：注册守卫先行 —— 建号走完（族/职业/名）才到得了玩
        d.setdefault("cls", "cls_knight")
        d.setdefault("name", "试刀")
        return d

    def save_player(self, uid, data):
        self.saved = dict(data) if isinstance(data, dict) else data

    def say(self, to, text):
        self.out.append(str(text))


STEPS = ["去 北墙根", "观察"]


def _run_at(hod):
    """真宿主 + 假钟：在 hod 点敲「去 北墙根」与「观察」，回各自的输出。"""
    db = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_npcs_e2e.db")
    try:
        os.remove(db)
    except OSError:
        pass
    ad = _Ad(STEPS)
    host = Host(ad, str(REPO), inject={"db_path": db, "clock": (lambda: _epoch_at(100, hod))})
    host.boot()
    got = {}
    for t in STEPS:
        ad.out.clear()
        host.handle({"uid": "u_n", "group_id": "g_n", "text": t})
        got[t] = list(ad.out)
    return got


def _hagen(lines):
    """★ g4-⑨：只认**「人在」那一栏**里有没有他 —— 「人不在」那句点名不算在场
    （本批起：不在场时名册那一侧会**点名说清他不在**，那正是「不在」的证据，不是「在」）。"""
    _head = str((st.domain("texts") or {}).get("SYS_LOOK_WHO", {}).get("value") or "").split("{")[0]
    return any(x.startswith(_head) and "『哈根』" in x for x in (lines or []))


try:
    _day = _run_at(_DAY)
    _night = _run_at(_NIGHT)
    chk("★ 昼（hod 12）：「去 北墙根」不列哈根（改前列 —— 它自己扫域不判条件）", not _hagen(_day.get("去 北墙根")),
        _day.get("去 北墙根"))
    chk("★ 昼：「观察」也不列哈根（两边口径一致）", not _hagen(_day.get("观察")), _day.get("观察"))
    chk("★ 夜（hod 21）：「去 北墙根」与「观察」都列哈根",
        _hagen(_night.get("去 北墙根")) and _hagen(_night.get("观察")),
        [_night.get("去 北墙根"), _night.get("观察")])   # ★ 传 list：chk 的 extra 走 "%s" % x，元组会被当多参
    chk("★ 「去」与「观察」的人名单同源（白天/夜里两边逐趟一致）",
        _hagen(_day.get("去 北墙根")) == _hagen(_day.get("观察"))
        and _hagen(_night.get("去 北墙根")) == _hagen(_night.get("观察")))
except Exception as exc:                                              # noqa: BLE001 —— 起不来就是红
    chk("★ 真宿主端到端跑得起来（出场条件那条线）", False, "%s: %s" % (type(exc).__name__, exc))

_src = (REPO / "content" / "cmds_ast.py").read_text(encoding="utf-8")
chk("★ npcs 域只经 `_npcs_here` 这一口（源码里没有第二处自己扫域 —— 两处口径的根）",
    _src.count('_data("npcs")') == 1, '出现 %d 次' % _src.count('_data("npcs")'))

# ══════════════════════════════════════════════════════════════
# ★ g4-⑨：作息表整体落地（31_NPC作息 §三/§七①⑤）
#   口径 = **已有的 `condition`**（`time` / `weather` / `event` 三档「与」起来），不新增形状。
#   判据：① token 全是 calendar 域里认得的名字；② 「故意全天」的那几位与 §三 的设计原则① 对上；
#         ③ 每个带 `time` 的窗口**两态都成立**（既不是全天开、也不是全天关）；
#         ④ 真宿主两个时辰走一遍：同一个人在场/不在场**翻面**（换时辰翻面，不是常量）；
#         ⑤ `07 §七⑤`：交活那位（带 `board` 职能 = 玛莎）**昼间必须在场**；
#         ⑥ 反证：把那一格临时摘掉 ⇒ 夜里她也「在」（那一格真的在管）。
# ══════════════════════════════════════════════════════════════
print("")
print("⑪ 作息表（31 §七①：补 `condition.time` · 4 位故意全天）")
sys.path.insert(0, str(REPO))
from content import calendar as CAL9                                  # noqa: E402
from content import cmds_ast as CA9                                   # noqa: E402

_with_time = {k: v for k, v in np_.items() if (v.get("condition") or {}).get("time")}
_tok_bad = []
for _k, _v in _with_time.items():
    for _t in _v["condition"]["time"]:
        if CAL9.resolve(_t)[0] is None:
            _tok_bad.append((_k, _t))
chk("★ %d 位挂了作息（`condition.time`）· token 全是 calendar 域认得的名字（%s）"
    % (len(_with_time), " · ".join("%s=%s" % (k[4:], "/".join(v["condition"]["time"]))
                                   for k, v in sorted(_with_time.items()))),
    len(_with_time) >= 6 and not _tok_bad, "脏 token：%s" % _tok_bad)
# 「故意全天」= 没有 `time` 那一格的那几位（§三 设计原则①：柯尔/娜娜/莉安/德里克 故意不动；
#   瑟兰/杜林/格雷 那三位的作息是 `event`（商队到了才在），也不带 time）
_ALWAYS = {"npc_cole", "npc_nana", "npc_lian", "npc_derrick",       # §三 原则①：故意不动手做人
           "npc_seran", "npc_durin", "npc_grey",                     # 作息是 `event`（商队到了才在）
           "npc_ed"}                                                 # ★ 功能位（治疗/复活）：§三 原则③
                                                                     #   「别在玩家最需要他的时候把他挪走」——
                                                                     #   夜里的「教堂」还得有人应；§五① 那一问拍板前不动
_no_time = {k for k in np_ if not (np_[k].get("condition") or {}).get("time")}
chk("★ 「全天」那几位与设计原则① 对得上（不动手做人：%s）"
    % " · ".join(np_[k]["name"] for k in sorted(_ALWAYS & _no_time)),
    _no_time == _ALWAYS, "没有 time 的：%s" % sorted(_no_time))
# ③ 两态都成立：每个窗口在这 24 小时里既有满足的时刻、也有不满足的时刻
_flat = []
for _k, _v in _with_time.items():
    _ok_h, _no_h = [], []
    for _h in range(24):
        _stx = CAL9.state(_epoch_at(100, _h + 0.5))
        (_ok_h if CAL9.allows(_v["condition"]["time"], _stx) else _no_h).append(_h)
    if not (_ok_h and _no_h):
        _flat.append((_k, _v["condition"]["time"], len(_ok_h)))
chk("★ 每个作息窗口**两态都成立**（24 小时里既有在场的时刻、也有不在的时刻 —— "
    "不是「全天开」也不是「全天关」）", len(_flat) == 0, "%s" % (_flat,))
# ④ 真宿主两个时辰：同一个人翻面 + ⑤ 交活那位昼间必须在
def _node_name(node):
    """节点 id → 玩家敲的那个名字（`去 <名字>` 才走得到 —— 名字从 maps 域现读）。"""
    for _n in (mp.get("windmill_town") or {}).get("nodes") or []:
        if str(_n.get("id")) == str(node):
            return str(_n.get("name"))
    return str(node)


def _roster_at(hod, node):
    """真宿主 + 假钟：走到那一站再「观察」，把两次回话拼起来（看「人在」那一栏）。"""
    db = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_npcs_roster.db")
    try:
        os.remove(db)
    except OSError:
        pass
    steps = ["去 %s" % _node_name(node), "观察"]
    ad = _Ad(list(steps))
    host = Host(ad, str(REPO), inject={"db_path": db, "clock": (lambda: _epoch_at(100, hod))})
    host.boot()
    out = []
    for t in steps:
        ad.out.clear()
        host.handle({"uid": "u_n", "group_id": "g_n", "text": t})
        out += list(ad.out)
    return "\n".join(out)


_HEAD_WHO9 = str((st.domain("texts") or {}).get("SYS_LOOK_WHO", {}).get("value") or "").split("{")[0]


def _who_in(text):
    """那一趟回话里**「人在」栏**上的人名表（★ g4：只认那一栏 —— 不在场时的点名句不算）。"""
    out = []
    for _ln in str(text).split("\n"):
        if _ln.startswith(_HEAD_WHO9):
            out += [x for x in _ln.replace("『", "|").replace("』", "|").split("|")[1::2]]
    return out


_BOARD_NODE = str(np_["npc_masha"]["subarea"])
_INN_NODE = str(np_["npc_bella"]["subarea"])
_board_day, _board_night = _roster_at(_DAY, _BOARD_NODE), _roster_at(_NIGHT, _BOARD_NODE)
_inn_day, _inn_night = _roster_at(_DAY, _INN_NODE), _roster_at(_NIGHT, _INN_NODE)
chk("★ 真宿主两态（同一个人翻面）：挂板墙 昼有『玛莎』/ 夜没有；客栈 昼没有『皮特』/ 夜有",
    np_["npc_masha"]["name"] in _who_in(_board_day)
    and np_["npc_masha"]["name"] not in _who_in(_board_night)
    and np_["npc_pete"]["name"] not in _who_in(_inn_day)
    and np_["npc_pete"]["name"] in _who_in(_inn_night),
    "板昼=%s 板夜=%s / 栈昼=%s 栈夜=%s"
    % (_who_in(_board_day), _who_in(_board_night), _who_in(_inn_day), _who_in(_inn_night)))
chk("★ `07 §七⑤`：交活那位（带 `board` 职能 = %s）**昼间必须在场**（防「找不到人交活」）"
    % np_["npc_masha"]["name"],
    any("board" in (v.get("funcs") or []) for v in np_.values())
    and np_["npc_masha"]["name"] in _who_in(_board_day))
# ⑥ 反证：把那一格临时摘掉 ⇒ 夜里她也在（这一格真的在管）
_dom9 = CA9._data("npcs")                         # ★ 要动**代码读的那一份**（见 probe_onsite ⑧ 同款注释）
_keep9 = dict(_dom9["npc_masha"].get("condition") or {})
_st9 = CAL9.state(_epoch_at(100, _NIGHT))          # 夜那一刻（判据不看真钟）


def _inflight9():
    return [k for k, _v in CA9._npcs_here("windmill_town", _BOARD_NODE, _st9, {})]


_before9 = _inflight9()
_dom9["npc_masha"]["condition"] = None
try:
    _after9 = _inflight9()
finally:
    _dom9["npc_masha"]["condition"] = _keep9
chk("★ 反证（撤改验证）：同一时刻（夜）把玛莎那一格摘掉 ⇒ 她当场在场了"
    "（`condition.time` 真的在管这一条 —— 夜：%s → 摘掉后：%s）"
    % ("有" if "npc_masha" in _before9 else "无", "有" if "npc_masha" in _after9 else "无"),
    bool(_keep9) and "npc_masha" not in _before9 and "npc_masha" in _after9)
# ⑦ 每位「会动的」都有一句「他什么时候在」（§七④ · 与 `probe_onsite ⑨` 同一条账）
_tx9 = st.domain("texts") or {}
_miss9 = [k for k in np_ if ("NPC_WHEN_%s" % str(k)[4:].upper()) not in _tx9]
chk("★ 14 位每位都有一句「他什么时候在」（`NPC_WHEN_<id>` 槽位）——「人不在」那句用它", not _miss9,
    "缺：%s" % _miss9)

print()
print("14 位速览（位置 · 功能 · 口头禅 · 矛盾）:")
for k, v in np_.items():
    print("  %-14s %-6s %-22s %-12s %s" % (
        v["name"], v["subarea"], "/".join(v.get("funcs", [])) or "—",
        v["persona"]["catch"], v["soul"]["conflict"][:26]))
print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
