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
    return any("『哈根』" in x for x in (lines or []))


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

print()
print("14 位速览（位置 · 功能 · 口头禅 · 矛盾）:")
for k, v in np_.items():
    print("  %-14s %-6s %-22s %-12s %s" % (
        v["name"], v["subarea"], "/".join(v.get("funcs", [])) or "—",
        v["persona"]["catch"], v["soul"]["conflict"][:26]))
print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
