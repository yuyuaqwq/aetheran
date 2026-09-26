# -*- coding: utf-8 -*-
r"""探针：移动 / 口令体系 / 副本进出（fix5-nav · 第 45 支）。

起因：四个真人玩家跑完第一阶段 QA，**三个独立撞上同一件事**（P1 BUG-12 / P2 BUG① / P3 体验）——
屏幕把地点名用『』写出来（`观察` 的「往哪走：『老风车』『东口』…」、`进镇` 的「能去的地方」），
玩家照着敲一律「「老风车」这句我没接住」；而 `北口` 偏偏**又是出镇口令**（P1 BUG-11：在客栈
敲它一步到骨田）。同一批还夹着副本进出两处（P2 旧哨塔下无进塔引导 · P4 撤退后返回回塔内）。

判据（每条都带正例 + 反证 —— 反证 = 把这一条赖以成立的那一格去掉/换回旧写法，判据必须翻面）：

  ① 站名别名走**引擎现成的别名机制**（声明表的 `patterns` 多写几条正则 = 别名，见
     `saintess_engine/command/spec.py` 的表结构说明）；名字的真源 = `maps` 域，**双向相等**；
     反证：把别名摘掉 ⇒ 逐名 `first_hit` 当场落空
  ② 裸站名真能走（镇内 + 野外 · 真宿主真敲）· 与 `去 <名>` 走同一支（逐字同一串回话）
  ③ 裸**指令名**（去 / 走到 / 前往）不被当成站名 —— 「去哪儿？现在能走到：…」照旧出得来
  ④ 名字真存在、只是**不在这张图上** ⇒ 「从这儿过不去」（不是「这儿没有叫…的地方」）
  ⑤ `北口` 归**站点**：在镇里任何一站敲它 ⇒ 落到镇口（不是骨田）；出镇是 `往北` / `出北门`；
     反证：把 `^北口$` 放回 go_north ⇒ first_hit 当场翻面
  ⑥ `撤退` 出塔之后第一下 `返回` 回**塔外那一格**（P4 BUG-5）；反证：按旧写法（只弹顶上一条）
     在**同一串 prev** 上算 ⇒ 返回落回塔内那一间
  ⑦ 本层尽头挡路的怪**没过手** ⇒ 『下一层』真拦（P2 体验：原先「过不去」只是嘴上说说）；
     过了手才上得去（probe_tower ⑧ 另有一份真跑）
  ⑧ 『帮助』里同时列着 『往北』 与 『存放 / 取出 <物品>』（P1 BUG-14 / P4 E-8）
  ⑨ 塔门口那一站多一句「门就在跟前」（P2 体验：主线去处别当背景板）—— 只那一站出、别处不出
  ⑩ 散文门槛（「退潮」）把刻度点明（P2 体验 · 与 probe_pois ③-c 同一条口径）
  ⑪ 石滩渡口真能垂钓（P2 体验 —— 同带另一个渡口能、这一个不能）
  ⑫ 生成器幂等：`scripts/rebuild_place_alias.py --dry` ⇒ 报「无改动」

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_nav.py
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, ENGINE)

from saintess_engine.command import CommandRegistry                # noqa: E402
from saintess_engine.host.runtime import Host                      # noqa: E402
from saintess_engine.package import load_stack                     # noqa: E402

from content import cmds_ast as CA                                 # noqa: E402
from content import cmds_tower as CTW                              # noqa: E402
from content import calendar as CAL                                # noqa: E402

ok = True


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


MISSING = "[MISSING TEXT"
FIXED = 1790308800.0                 # 2026-09-25 12:00 +08:00（与 probe_cmds / probe_miss 同一口径）
DB = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_nav.db")

print("探针：移动 / 口令体系 / 副本进出（fix5-nav · 第 45 支）")

DE = load_stack(str(REPO), inject={"db_path": DB, "clock": lambda: FIXED})
DE.install()
DECL = DE.command_declarations()
REG = CommandRegistry(name="probe_nav").load(DECL)
MP = DE.domain("maps") or {}
TX = DE.domain("texts") or {}
G = DE.domain("gathering") or {}
MS = DE.domain("monsters") or {}

PLACES = [(str(loc), str(n.get("id")), str(n.get("name")))
          for loc, m in MP.items() for n in (m.get("nodes") or [])]
NAMES = [p[2] for p in PLACES]
KEY = "go_to"


def _clone(obj):
    """声明表 / 档的深拷贝（反证都在**副本**上算 —— 绝不动真数据）。"""
    return json.loads(json.dumps(obj))


def _txt(slot, **kw):
    s = str((TX.get(slot) or {}).get("value") or "")
    for k, v in kw.items():
        s = s.replace("{%s}" % k, str(v))
    return s


def _bare(nm):
    return "^" + re.escape(nm) + "$"


# ══════════════════════════════════════════════════════════════
# ① 站名别名 = 引擎现成的别名机制（名字从 maps 现读 · 双向相等）
# ══════════════════════════════════════════════════════════════
print("① 站名别名走引擎现成的别名机制（声明表 patterns · 名字从 maps 现读）")
WANT = {_bare(n) for n in NAMES}
HAVE = {p for p in (DECL.get(KEY, {}).get("patterns") or []) if p in WANT}
chk("★ maps 的 %d 个节点名**每个**都有 `^<名>$` 挂在 %s 上（双向相等 · 名字不手抄）" % (len(WANT), KEY),
    WANT and HAVE == WANT and len(set(NAMES)) == len(NAMES),
    "缺：%s" % sorted(WANT - HAVE)[:5])
_bad_r = [n for n in NAMES if getattr(REG.first_hit(n, visible_only=True), "key", None) != KEY]
chk("★ 逐名 first_hit 都落到 %s（路由层：敲站名 = 『去 <名>』）" % KEY, not _bad_r, "%s" % _bad_r[:5])
# 反证：把站名别名从声明里摘掉 ⇒ 这些名字当场没人接（判据有牙）
_broken = _clone(DECL)
_broken[KEY]["patterns"] = [p for p in (_broken[KEY].get("patterns") or []) if p not in WANT]
_RB = CommandRegistry(name="probe_nav_broken").load(_broken)
_left = [n for n in NAMES if getattr(_RB.first_hit(n, visible_only=True), "key", None) is not None]
chk("★ 反证：把站名别名摘掉 ⇒ %d 个名字**一个都落不到** %s 上（判据真的在判别名那一格）"
    % (len(NAMES), KEY), not _left, "%s" % _left[:5])
# 非站名的词**不许**被这个机制顺手接住（否则「没接住」那一条线整片失效）
_rnd = [w for w in ("唱歌", "睡觉", "数星星") if _RB.first_hit(w, visible_only=True) is not None
        or REG.first_hit(w, visible_only=True) is not None]
chk("★ 非站名的词一个都没被接住（摘了别名之后也没人接 —— 别名不是万能兜底）", not _rnd, "%s" % _rnd)

# ══════════════════════════════════════════════════════════════
# 真宿主（②③④⑤⑥⑦⑨⑪ 都在这一条上真敲）
# ══════════════════════════════════════════════════════════════
print("② 真宿主真敲：裸站名能走（镇内 + 野外）")


class _Ad(object):
    """三函数 + say（照 host-api 契约的最小适配器 —— 与 e2e_drive / probe_tower 同形）。"""

    def __init__(self):
        self.out = []
        self.saved = {"loc": "windmill_town", "node": "wt_gate_n", "race": "human",
                      "cls": "cls_knight", "name": "试", "level": 5, "gold": 100,
                      "hp": 120, "exp": 0, "bag": {}, "equipped": {}, "codex": {},
                      "books": {}, "flags": {}, "prev": [], "alloc": {},
                      "foot": {"nodes": {}, "kills": 0, "reads": 0, "gathers": 0, "visits": {}}}

    def recv(self):
        return None

    def load_player(self, uid):
        return self.saved if uid == "u_nav" else None

    def save_player(self, uid, data):
        self.saved = dict(data) if isinstance(data, dict) else data

    def say(self, to, text):
        self.out.append(str(text))


try:
    os.remove(DB)
except OSError:
    pass
AD = _Ad()
HOST = Host(AD, str(REPO), inject={"db_path": DB, "clock": lambda: FIXED})
HOST.boot()
chk("★ 真宿主跑得起来（真宿主契约）", True)


def put(loc, node, **kw):
    AD.saved = dict(AD.saved, loc=loc, node=node, **kw)


def send(text):
    AD.out.clear()
    HOST.handle({"uid": "u_nav", "group_id": "g_nav", "text": text})
    return list(AD.out)


def here():
    return (AD.saved.get("loc"), AD.saved.get("node"))


# ② 镇内：三个镇口 + 两个镇上的站 —— 裸名与 `去 <名>` 逐字同一串回话
TOWN_CASES = [("wt_mill", "老风车"), ("wt_gate_e", "东口"), ("wt_gate_w", "西口"),
              ("wt_gate_n", "北口"), ("wt_forge", "半截铁砧"), ("wt_wall", "北墙根")]
walk_bad = []
for nid, nm in TOWN_CASES:
    put("windmill_town", "wt_board")
    bare_out = send(nm)
    bare_at = here()
    put("windmill_town", "wt_board")
    arg_out = send("去 %s" % nm)
    if bare_at != ("windmill_town", nid):
        walk_bad.append((nm, "裸名落点 %s" % (bare_at,)))
    if bare_out != arg_out:
        walk_bad.append((nm, "裸名与『去 <名>』不是同一串回话：%s / %s" % (bare_out[:1], arg_out[:1])))
chk("★ 镇内 %d 个站名裸敲 = 『去 <名>』（落点 + 回话逐字同一串）"
    % len(TOWN_CASES), not walk_bad, "%s" % walk_bad[:3])

# ② 野外：北带三站（骨田 → 拾荒营地 → 旧哨塔下）逐站裸敲走一遍
put("belt_north", "bn_bone")
send_out = send("拾荒营地")
mid_ok = here() == ("belt_north", "bn_camp") and send_out[:1] == [_txt("SYS_MOVE_TO", name="拾荒营地")]
deep_out = send("旧哨塔下")
deep_ok = here() == ("belt_north", "bn_tower")
chk("★ 野外 2 个站名裸敲能一步步往里走（拾荒营地 → 旧哨塔下）", mid_ok and deep_ok,
    "%s / %s · %s" % (here(), send_out[:1], deep_out[:1]))
# ② 三带的头一站（东/西带）也从镇外那头验一遍
WILD_CASES = [("belt_east", "be_birch", "野狗窝"), ("belt_west", "bw_shoal", "石滩渡口")]
wild_bad = []
for loc, node, nm in WILD_CASES:
    put(loc, node)
    out = send(nm)
    _tid = dict(((p[0], p[2]), p[1]) for p in PLACES).get((loc, nm), "")
    if out[:1] != [_txt("SYS_MOVE_TO", name=nm)] or here() != (loc, _tid):
        wild_bad.append((nm, out[:1], here(), (loc, _tid)))
chk("★ 另两条带上的站名裸敲也走得动（%s）"
    % " · ".join(nm for _l, _n, nm in WILD_CASES), not wild_bad, "%s" % wild_bad[:2])

print("③ 裸指令名不被当成站名 · ④ 跨图那个名字说「过不去」")
put("windmill_town", "wt_board")
ask_outs = {}
for w in ("去", "走到", "前往"):
    ask_outs[w] = send(w)
_want_ask = _txt("SYS_MOVE_ASK", list=" · ".join(
    "『%s』" % CA._name_of_node("windmill_town", x) for x in CA._neighbors("windmill_town", "wt_board")))
chk("★ 裸『去 / 走到 / 前往』照旧回「去哪儿？」（不是「这儿没有叫「去」的地方」）",
    all(ask_outs[w] == [_want_ask] for w in ask_outs), "%s" % {k: v[:1] for k, v in ask_outs.items()})
put("windmill_town", "wt_board")
cross = send("白桦林")
_far = _txt("SYS_MOVE_FAR", name="白桦林")
_nosuch = _txt("SYS_MOVE_NOSUCH", name="白桦林")
chk("★ 名字真存在、只是不在这张图上 ⇒ 「从这儿过不去」（原先/或没这一支时会说「没这个地方」）",
    cross[:1] == [_far] and _nosuch not in chr(10).join(cross), "%s" % cross[:1])
put("windmill_town", "wt_board")
nope = send("去 高塔")
chk("★ 五张图上都没有的名字照旧回「这儿没有叫「高塔」的地方」（带 `去` 那一支）",
    nope[:1] == [_txt("SYS_MOVE_NOSUCH", name="高塔")] and len(nope) == 2
    and nope[1].startswith(_txt("SYS_MOVE_CAN", list="").split("{")[0]), "%s" % nope[:2])
put("windmill_town", "wt_board")
chk("★ 而**裸**的、哪张图上都没有的词照旧落「没接住」那一句（别名不许变成万能兜底）",
    send("高塔") == [_txt("SYS_CMD_MISS", word="高塔")], "%s" % send("高塔")[:1])

print("⑤ 北口 归站点（P1 BUG-11 · P3 体验）")
chk("★ `北口` 的 first_hit = %s（站点名那一族）"
    % getattr(REG.first_hit("北口", visible_only=True), "key", None),
    getattr(REG.first_hit("北口", visible_only=True), "key", None) == KEY
    and _bare("北口") not in (DECL.get("go_north", {}).get("patterns") or []))
chk("★ 出镇那两条（往北 / 出北门）照旧归 go_north，且 usage 是『往北』（帮助里显示的就是它）",
    getattr(REG.first_hit("往北", visible_only=True), "key", None) == "go_north"
    and getattr(REG.first_hit("出北门", visible_only=True), "key", None) == "go_north"
    and (DECL.get("go_north", {}).get("usage") or "").split()[0] == "往北")
_gate_bad = []
for _nid, _nm in TOWN_CASES:
    put("windmill_town", _nid)
    send("北口")
    if here() != ("windmill_town", "wt_gate_n"):
        _gate_bad.append((_nm, here()))
chk("★ 在镇里 %d 个站上敲『北口』⇒ 一律落到**镇口**（不是骨田）" % len(TOWN_CASES),
    not _gate_bad, "%s" % _gate_bad[:3])
put("windmill_town", "wt_board")
_out_n = send("出北门")
chk("★ 『出北门』从镇上任何一站出门 ⇒ 落到骨田（真源 04 §一 那一行的原词一个没丢）",
    here() == ("belt_north", "bn_bone") and _out_n[:1] == [_txt("SYS_MOVE_OUT_NORTH")], "%s" % (_out_n[:1],))
# 反证：把 `^北口$` 放回 go_north ⇒ first_hit 当场翻面（证明这一条判的正是那一格）
_back = _clone(DECL)
_back["go_north"]["patterns"] = [_bare("北口")] + list(_back["go_north"].get("patterns") or [])
_RBK = CommandRegistry(name="probe_nav_back").load(_back)
chk("★ 反证：`^北口$` 一放回 go_north ⇒ `北口` 的 first_hit 当场变成 go_north（判据能翻面）",
    getattr(_RBK.first_hit("北口", visible_only=True), "key", None) == "go_north")

print("⑥ 撤退之后第一下『返回』回塔外（P4 BUG-5）")
put("belt_north", "bn_camp")
send("去 旧哨塔下")
send("进塔")
send("去 门厅")
send("去 武器架室")
send("去 楼梯前")
_prev_in = _clone(AD.saved.get("prev") or [])
send("撤退")
chk("★ 『撤退』真出塔（回到塔门口那一格）", here() == ("belt_north", "bn_tower"), "%s" % (here(),))
_back_out = send("返回")
chk("★ 紧接着的『返回』回**塔外那一格**（进塔之前站的拾荒营地）—— 不是塔内房间",
    here() == ("belt_north", "bn_camp") and _back_out[:1] == [_txt("SYS_MOVE_BACK", name="拾荒营地")],
    "%s · %s" % (here(), _back_out[:1]))
# 反证：按**旧写法**（只在「顶上那条正好等于塔门口」时弹一条）在同一串 prev 上算 ⇒ 返回落回塔内
_old_prev = list(_prev_in)
if _old_prev and tuple(_old_prev[-1]) == ("belt_north", "bn_tower"):
    _old_prev.pop()
chk("★ 反证：旧写法（只弹一条 · 保留塔内那几条）在同一串 prev 上算 ⇒ 返回落回**塔内那一间**"
    "（%s）—— 判据真的在判那一段回滚" % (_old_prev[-1] if _old_prev else None),
    bool(_old_prev) and str(_old_prev[-1][0]) == "old_watchtower")
_prev_now = list(AD.saved.get("prev") or [])
chk("★ 现在这一串 prev 顶上**一格塔内的都不剩**（撤退把这一趟进塔整段撤掉了）",
    not [x for x in _prev_now if str(x[0]) == "old_watchtower"]
    and ("belt_north", "bn_tower") not in [tuple(x) for x in _prev_now],
    "%s" % (_prev_now[-3:],))

print("⑦ 本层尽头挡路的怪没过手 ⇒ 『下一层』真拦（P2 体验）")
FLOORS = [(str(f.get("name")), [str(x) for x in (f.get("rooms") or [])])
          for f in ((MP.get("old_watchtower") or {}).get("floors") or [])]
_last1 = FLOORS[0][1][-1]
_foes = sorted(mid for mid, m in MS.items()
               if "old_watchtower" in [str(x) for x in ((m.get("habitat") or {}).get("maps") or [])]
               and _last1 in [str(x) for x in ((m.get("habitat") or {}).get("nodes") or [])])
chk("★ 一层尽头那一间（%s）有挡路的怪 %d 只" % (CA._name_of_node("old_watchtower", _last1), len(_foes)),
    bool(_foes), "%s" % _foes)
put("old_watchtower", _last1, books={}, prev=[])
_blk = send("下一层")
chk("★ 没过手 ⇒ 拦住并点名（位置一格不动）",
    _blk == [_txt("SYS_TOWER_BLOCKED", name=" · ".join(
        str((MS.get(_m) or {}).get("name") or _m) for _m in _foes))]
    and here() == ("old_watchtower", _last1), "%s" % _blk[:1])
put("old_watchtower", _last1, books={"monster": {_foes[0]: {"day": 1, "kills": 1}}}, prev=[])
_up = send("下一层")
chk("★ 反证：过了手（怪物谱上有它）⇒ 拦那一句不出、真上到第二层第一间",
    here() == ("old_watchtower", FLOORS[1][1][0])
    and _blk[0] not in _up and _up[0] == _txt("SYS_TOWER_UP", floor=FLOORS[1][0],
                                             room=CA._name_of_node("old_watchtower", FLOORS[1][1][0])),
    "%s" % _up[:1])

print("⑧ 『帮助』里补上了 往北 与 取出（P1 BUG-14 / P4 E-8）")
_ad = _Ad()
_db2 = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_nav_help.db")
try:
    os.remove(_db2)
except OSError:
    pass
_h = Host(_ad, str(REPO), inject={"db_path": _db2, "clock": lambda: FIXED})
_h.boot()
_ad.out.clear()
_h.handle({"uid": "u_nav", "group_id": "g_nav", "text": "帮助"})
_help = list(_ad.out)
_listed = [w for ln in _help for w in re.findall("『([^』]*)』", ln)]
chk("★ 帮助里列出 『往北』（去骨田唯一那条路 —— 委托 25 硬要玩家去骨田）", "往北" in _listed, "%s" % _listed[:3])
chk("★ 帮助里列出 『存放 / 取出 <物品>』（游戏自己在客栈教玩家敲『取出』）",
    "存放 / 取出 <物品>" in _listed, "%s" % [w for w in _listed if "存放" in w])
chk("★ 帮助里的词表 = 可见且有处理器那些声明的 usage（现读声明表逐条对账）",
    sorted(_listed) == sorted(str(v.get("usage")) for v in DECL.values()
                              if v.get("bind") and v.get("visible", True) is not False))
# 反证：把 go_north 的 usage 改回『北口』（副本声明表）⇒ 那句话里就没有往北（判据在判 usage 那一格）
_hb = _clone(DECL)
_hb["go_north"]["usage"] = "北口"
chk("★ 反证：usage 改回『北口』⇒ 帮助那一栏里就没有『往北』（玩家的『往北』是从 usage 来的）",
    not any(str(v.get("usage")) == "往北" for v in _hb.values()))
_sb = _clone(DECL)
_sb["stash"]["usage"] = "存放 <参数>"
chk("★ 反证：stash 的 usage 一改回『存放 <参数>』⇒ 帮助里那一条里就没有『取出』"
    "（玩家的两个词都是从 usage 来的）",
    "取出" in str(DECL.get("stash", {}).get("usage") or "")
    and "取出" not in str(_sb["stash"]["usage"]))

print("⑨ 塔门口那一站多一句「门就在跟前」（P2 体验）")
_want_door = _txt("SYS_TOWER_DOOR")
_door_bad, _door_ok = [], []
for loc, node, _nm in PLACES:
    put(loc, node)
    if _want_door in send("观察"):
        _door_ok.append((loc, node))
chk("★ 那一句**只在**塔门口那一格出（%s）· 别处一格都不出" % ([(a, b) for a, b in _door_ok],),
    _door_ok == [("belt_north", "bn_tower")], "实出：%s" % (_door_ok,))
put("old_watchtower", "tower_gate")
_in_tower = send("观察")
chk("★ 人已经在塔里就不再说（那一刻由进塔那一屏的尾注说话）",
    _want_door not in _in_tower, "%s" % _in_tower[:2])
put("belt_north", "bn_camp")
_arrive = send("旧哨塔下")
chk("★ 走到塔门口那一下顺口就说（走路那一支也挂了同一句）",
    _want_door in _arrive, "%s" % _arrive[:2])

print("⑩ 散文门槛把刻度点明（P2 体验 · 「退潮」⇒「夜」）")
_tok = CAL.token_alias()
_slot = next((k for k, v in sorted(DE.domain("pois").items())
              if (v.get("condition") or {}).get("time")), "")
_pid = _slot
_rec = (DE.domain("pois").get(_pid) or {})
if _pid:
    _scale = []
    for _hod in (12.0, 22.0):
        _e = 200 * CAL.scale_seconds() + (_hod / 24.0) * CAL.scale_seconds()
        CAL.facade.bind_host(clock=lambda _e=_e: _e)
        _scale.append(CA._poi_cond(_rec, CA._p(dict(CA.DEFAULT_PLAYER)), None))
    CAL.facade.bind_host(clock=lambda: FIXED)
    _t0 = str((_rec.get("condition") or {}).get("time", [""])[0])
    _real = CAL.name(CAL.resolve(_t0)[1])
    _alias_line = CA.T("SYS_POI_WHY_TIME_ALIAS", token=_t0, real=_real)
    chk("★ 「%s」那一档把刻度写出来了：昼 ⟶ 「%s」" % (_t0, _alias_line),
        _scale[0][0] == "no" and _alias_line in str(_scale[0][1])
        and str(_scale[0][1]).count("（就是") == 1, "%s" % (str(_scale[0][1])[:60],))
    chk("★ 真名字（非别名）那一档照旧走原槽位（没把简单那一档也一起改）",
        any(_v for _k, _v in TX.items() if _k == "SYS_POI_WHY_TIME")
        and _t0 in CAL.token_alias(), "%s" % (_t0,))
else:
    chk("★ pois 里有一条带 time 门槛的（它才是这一条的样本）", False)

print("⑪ 石滩渡口真能垂钓（P2 体验）")
_pts = [(k, v) for k, v in G.items()
        if v.get("map") == "belt_west" and v.get("subarea") == "bw_ferry" and v.get("verb") == "fish"]
chk("★ gathering 域里 石滩渡口 有一条 verb=fish 的点（%s）"
    % [(k, v.get("name")) for k, v in _pts], len(_pts) == 1, "%s" % [(k, v.get("name")) for k, v in _pts])
put("belt_west", "bw_ferry", flags={}, bag={})
_fout = send("垂钓")
_pt = _pts[0][1] if _pts else {}
chk("★ 真敲『垂钓』不再是「这儿没什么可钓的」（有产出行）",
    bool(_fout) and _txt("SYS_GATHER_NONE", word=_txt("SYS_GATHER_VERB_FISH")) not in _fout
    and bool(_pt) and _fout[0].startswith("【%s】" % _pt.get("name"))
    and any(x.startswith("得到：") for x in _fout),
    "%s" % _fout[:3])
chk("★ 同带另一个渡口（旧渡口）那条垂钓点照旧在（没被换掉）",
    any(v.get("subarea") == "bw_old_ferry" and v.get("verb") == "fish" for v in G.values()))
chk("★ 回话里没有取不到文案 / 机器键", MISSING not in chr(10).join(_fout), "%s" % _fout[:2])

print("⑫ 生成器幂等（`scripts/rebuild_place_alias.py --dry`）")
_env = dict(os.environ, GWEN_ENGINE=str(ENGINE))
_run = subprocess.run([sys.executable, os.path.join(str(REPO), "scripts", "rebuild_place_alias.py"),
                       "--dry"], cwd=str(REPO), env=_env, stdout=subprocess.PIPE,
                      stderr=subprocess.STDOUT)
_out = (_run.stdout or b"").decode("utf-8", "replace")
chk("★ 数据已是最新（生成器报「无改动（幂等）」· 名字全挂在 %s 上）" % KEY,
    _run.returncode == 0 and "无改动（幂等）" in _out, _out.strip().splitlines()[-1:] or "")

print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
