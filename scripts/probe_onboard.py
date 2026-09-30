# -*- coding: utf-8 -*-
"""探针：引导层（B 档「有目标感」）—— copy-p5 车道 · 2026-09-29 的常驻门禁。

钉的是什么
------------------------------------------------------------------
鱼鱼原话：「想开始玩游戏啥的都没什么引导」+「可以加点仪式感」。
开工时现取的底账：引导族槽位 **0 个**（GUIDE/ONBOARD/WELCOME/TUTOR/INTRO 全零命中）
⇒ 病根是**根本没有这一层**，不是「不够丰富」。本探针是这一层建起来之后的**防回退**门。

五档判据（每档都真跑玩家那一路，不读代码）
------------------------------------------------------------------
① 新玩家第一屏必含开场白（只在建号没走完那一档给；走完之后不许再给）
② 建号未完时「当前该做」指向正确的那一步（三档逐档真敲）+ 机器键不上屏 + 不念说明书
③ 第一件委托在进镇后自动出现在「我的委托」里（系统派的，不是玩家自己接的）
④ 反证一：把顶栏那一格摘掉 ⇒ **当场红**（证明这一格真接在屏上，不静默不显示）
⑤ 反证二：清掉 flags.current_goal ⇒ 回落到正确兜底，不空白 / 不机器键 / 不漏字面量

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_onboard.py
      （Python 3.12 —— 3.11 会假红）
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
TMP = os.environ.get("AST_PROBE_TMP", "C:/Users/yuyu/AppData/Local/Temp")
DB = os.path.join(TMP, "ast_probe_onboard.db")
TEXTS = os.path.join(REPO, "content", "data", "texts.json")

print("探针：引导层 · B 档（开场白 / 三步标题块 / 第一件委托 / 顶栏当前该做）")

sys.path.insert(0, REPO)
sys.path.insert(0, ENGINE)

failures = []


def chk(label, cond, extra=""):
    print("  %s %s%s" % ("OK" if cond else "X", label, ("  —— %s" % extra) if extra else ""))
    if not cond:
        failures.append(label)
    return bool(cond)


class _Clock(object):
    def __init__(self, t0=1700000000.0):
        self.t = float(t0)

    def __call__(self):
        return self.t

    def tick(self, dt):
        self.t += float(dt)
        return self.t


class _Ad(object):
    def __init__(self, gid):
        self.gid = str(gid)
        self.out = []

    def recv(self):
        return None

    def load_player(self, uid):
        from content import persistence as PS
        return PS.get_player(self.gid, uid)

    def save_player(self, uid, data):
        from content import persistence as PS
        fields = {k: v for k, v in dict(data or {}).items()
                  if k not in ("group_id", "qq_id", "uid")}
        PS.update_player(self.gid, uid, **fields)

    def say(self, to, text):
        self.out.append(str(text))


def _boot(gid):
    from saintess_engine.host.runtime import Host
    from content import persistence as PS
    clock = _Clock()
    h = Host(_Ad(gid), str(REPO), inject={"db_path": DB, "clock": clock})
    h.boot()
    PS.bind(clock=clock)
    return h, h.adapter


def _seed(gid, uid, **kw):
    from content import cmds_ast as CA
    from content import persistence as PS
    d = dict(CA.DEFAULT_PLAYER)
    d.update(kw)
    PS.update_player(gid, uid, **d)
    return d


def _drive(host, ad, uid, text):
    ad.out.clear()
    host.handle({"uid": uid, "group_id": ad.gid, "text": text})
    return [str(x) for x in ad.out]
try:
    os.remove(DB)
except OSError:
    pass

TX = json.loads(io.open(TEXTS, encoding="utf-8").read())
GID = "g_onboard"

NEED = ["SYS_ONBOARD_OPEN", "SYS_ONBOARD_GOAL", "SYS_ONBOARD_GOAL_STEP", "SYS_ONBOARD_GOAL_JOB",
        "SYS_ONBOARD_GOAL_FIRST", "SYS_ONBOARD_GOAL_IDLE", "SYS_ONBOARD_WELCOME"]
miss = [k for k in NEED if k not in TX or not str(TX[k].get("value") or "").strip()]
chk("引导族槽位 %d 条都在 texts 域（这一层的存在性）" % len(NEED), not miss, "%s" % miss)

BS = chr(92) + "n"
_nl = [k for k in NEED if k in TX and chr(10) not in str(TX[k].get("value") or "")
       and BS in str(TX[k].get("value") or "")]
chk("★ 槽位里的换行是真换行（不是字面量两字符 —— 踩过：整段挤成一行）", not _nl, "%s" % _nl)

h, ad = _boot(GID)
from content import cmds_ast as CA          # noqa: E402
from content import onboard as OB           # noqa: E402
from content import persistence as PS       # noqa: E402

UID1 = "u_first_screen"
_seed(GID, UID1, level=1, gold=30, loc="windmill_town", node="wt_gate_n")
first = _drive(h, ad, UID1, "观察")
open_txt = TX.get("SYS_ONBOARD_OPEN", {}).get("value", "").split(chr(10))[0].strip()
chk("① 新玩家第一屏含开场白", bool(open_txt) and any(open_txt in ln for ln in first),
    "第一行=%r" % (first[0] if first else ""))

_drive(h, ad, UID1, "选族 矮人")
_drive(h, ad, UID1, "选职业 骑士")
_drive(h, ad, UID1, "名字 老陈")
after = _drive(h, ad, UID1, "观察")
chk("① 反证：建号走完之后开场白不再给（老玩家不该每敲一次重看一遍世界史）",
    not any(open_txt and open_txt in ln for ln in after))
UID2 = "u_steps"
from content import cmds_ast as _CA      # ★ ② 的期望值：STEP_WHAT 已槽位化（2026-09-29 收尾批）⇒ 经槽位取渲染文本
_seed(GID, UID2, level=1, gold=30, loc="windmill_town", node="wt_gate_n")
g1 = _drive(h, ad, UID2, "状态")
chk("② 建号第 1 步（未定族）顶栏指向那一步", _CA.T(OB.STEP_WHAT["race"]) in chr(10).join(g1),
    "屏=%r" % g1[:1])
_drive(h, ad, UID2, "选族 矮人")
g2 = _drive(h, ad, UID2, "状态")
chk("② 建号第 2 步（未定职业）顶栏指向那一步", _CA.T(OB.STEP_WHAT["class"]) in chr(10).join(g2),
    "屏=%r" % g2[:1])
_drive(h, ad, UID2, "选职业 骑士")
g3 = _drive(h, ad, UID2, "状态")
chk("② 建号第 3 步（未定名字）顶栏指向那一步", _CA.T(OB.STEP_WHAT["name"]) in chr(10).join(g3),
    "屏=%r" % g3[:1])

_goal_lines = [ln for g in (g1, g2, g3) for ln in g if "当前该做" in ln]
_mk = [(k, ln) for ln in _goal_lines for k in ("race", "class", "name") if k in ln]
chk("★ ② 顶栏那一屏一个机器键都不许出现（呈现名 ≠ 机器键）", not _mk, "%s" % _mk[:2])

def _cmds(s):
    return [x for x in re.findall(chr(0x300E) + "([^" + chr(0x300E) + chr(0x300F) + "]+)" + chr(0x300F), s)]

chk("★ ② 顶栏三档都真的印出来了（三行都在屏上）", len(_goal_lines) == 3,
    "印了 %d 行" % len(_goal_lines))
BS2 = chr(0x300E) + "([^" + chr(0x300E) + chr(0x300F) + "]+)" + chr(0x300F)
_many = [ln for ln in _goal_lines if len(re.findall(BS2, ln)) >= 2]
chk("★ ② 顶栏那一屏不许并列 >=2 个指令名（不许念说明书）", not _many, "%s" % _many[:2])

UID3 = "u_autoquest"
_seed(GID, UID3, level=1, gold=30, loc="windmill_town", node="wt_gate_n")
_drive(h, ad, UID3, "选族 矮人")
_drive(h, ad, UID3, "选职业 骑士")
nm = _drive(h, ad, UID3, "名字 老陈")
from content.cmds_quest import _quests as _q   # noqa: E402
# ★ B5（P-60）：**带档**取第一件 —— 派发口径改按族走（矮人 ⇒ 引子『交不掉的货』），
#   无参老口径固定回 order==1 主线 1，跟实际派出去的那条对不上（③ 两条断言会假红）。
#   ★ 有意差异登记（B5 设计稿 §5 probe_onboard 改法③）：断言**一个字没松** ——
#     仍旧查「真派那条的名字在一屏上 + 在册 + 只派一条」，只是「第一件」改成按档现算。
_d3 = PS.get_player(GID, UID3) or {}
_fid = OB.first_quest_id(_d3)
_qname = (_q().get(_fid) or {}).get("name", "")
chk("③ 取名那一拍递**欢迎屏**（自动派上了才说）—— 名字 / 族 / 职业 / 第一件委托一屏收",
    any("✨" in ln and "风车镇" in ln for ln in nm)
    and any(_qname and _qname in ln for ln in nm), "屏=%r" % nm[-2:])
mine = _drive(h, ad, UID3, "我的委托")
chk("③ 第一件委托已在「我的委托」在册上（不是玩家自己接的）",
    bool(_qname) and any(_qname in ln for ln in mine), "屏=%r" % mine[:3])
_act = list(((_d3.get("flags") or {}).get("quests_active")) or [])
chk("★ ③ 幂等：手上只有那一条（没被派两遍）", len(_act) == 1, "quests_active=%s" % _act)

_flags_now = dict(_d3.get("flags") or {})
chk("★ ④ 顶栏那格**落档**了（flags.current_goal 真写进去了，不只是现算）",
    "current_goal" in _flags_now, "flags=%s" % list(_flags_now.keys()))
chk("★ ④ 落档那一格存的是**中文正文**（不是机器键 / 不是槽位名）",
    bool(str(_flags_now.get("current_goal") or "").strip())
    and "SYS_ONBOARD" not in str(_flags_now.get("current_goal")),
    "值=%r" % _flags_now.get("current_goal"))
_tx2 = json.loads(io.open(TEXTS, encoding="utf-8").read())
_saved_goal = _tx2.pop("SYS_ONBOARD_GOAL", None)
_orig = CA._texts
CA._texts = lambda: _tx2
try:
    _line = OB.goal_line(_d3)
    chk("★ ④ 反证：摘掉顶栏那一格 ⇒ 不显示（回空串），绝不把缺文案标记印上屏",
        _line == "", "回=%r" % _line)
    chk("★ ④ 反证：缺文案时渲染口 fail-closed（当场显形，不静默编一句）",
        CA.MISSING_MARK in CA.T("SYS_ONBOARD_GOAL_NOT_THERE_AT_ALL"))
finally:
    CA._texts = _orig
    if _saved_goal is not None:
        _tx2["SYS_ONBOARD_GOAL"] = _saved_goal

# ★ 「清 flags.current_goal」这一格要证的是：**它是派生态** —— 删掉它，
#   顶栏照样现算得出同一句（不是「靠那一格显示」）。所以先在**同一个玩家**上删它。
_p5 = dict(_d3)
_f5 = dict(_p5.get("flags") or {})
_f5.pop("current_goal", None)
_p5["flags"] = _f5
_line5 = OB.goal_line(_p5)
chk("★ ⑤ 那格是**派生态**：删掉它顶栏照样现算得出（不靠落档那一格才显示）",
    bool(_line5.strip()) and _line5 == OB.goal_line(_d3), "回=%r" % _line5)
# ★ 真正的「兜底」那一档：**手上没活 + 第一件已交** ⇒ 回落句（不是空白）。
#   （上一版把这两件事混成一件 —— 删 current_goal 不等于「没活」，判据写错了；
#     这是判据写错不是实现错，按纪律改判据不改实现。）
_p5b = dict(_d3)
_f5b = dict(_p5b.get("flags") or {})
_f5b["quests_active"] = []
# ★ B5（P-60）：兜底档的「第一件」**带档**算（矮人 ⇒ 引子），**接力的下一棒**（order==1
#   主线 1）也得一并标成交 —— 引子交了顶栏会指「先把镇口的石头接了」（这正是 B5 的接力行为，
#   不是 bug）；真的「没话」= 头两棒都交完。断言一个字没松（还是查 IDLE 句落在屏上）。
_fid5 = OB.first_quest_id(_d3)
_fid5n = OB.first_quest_id()
_f5b["quests_done"] = [k for k in (_fid5, _fid5n) if k]
_f5b.pop("current_goal", None)
_p5b["flags"] = _f5b
_line5 = OB.goal_line(_p5b)
_idle = str(TX.get("SYS_ONBOARD_GOAL_IDLE", {}).get("value") or "")
chk("⑤ 清掉 flags.current_goal ⇒ 顶栏仍有话（不空白）", bool(_line5.strip()), "回=%r" % _line5)
chk("⑤ 顶栏回落到兜底那一档（手上没活 ⇒ IDLE 句）", bool(_idle) and _idle in _line5,
    "回=%r" % _line5)
chk("★ ⑤ 顶栏不许漏出未替换的字面量（{body}/{what}/{name}/{objective}）",
    not any(t in _line5 for t in ("{body}", "{what}", "{name}", "{objective}")),
    "回=%r" % _line5)
chk("★ ⑤ 顶栏不许出现机器键", not any(k in _line5 for k in ("race", "class", _fid)),
    "回=%r" % _line5)

_empty = [k for k in ("SYS_ONBOARD_GOAL_STEP", "SYS_ONBOARD_GOAL_JOB",
           "SYS_ONBOARD_GOAL_FIRST", "SYS_ONBOARD_GOAL_IDLE")
          if not str(TX.get(k, {}).get("value") or "").strip()]
chk("★ 顶栏四档正文都在（缺一档 ⇒ 那一档玩家看到空屏）", not _empty, "%s" % _empty)

# ★ B5 六族引子（P-60）[按族段]：六族各派各的 · 欢迎屏 · 交引子接力主线 1 · 幂等
#   【口径】B5 设计稿 §4：建号自动派**本族**引子（`first_quest_id(p)` 按 race 现算）；
#     交掉引子 ⇒ 主线 1 **自动上手**（否则新玩家手上没活、自己『接 1』又撞 B4-27 证门 = 断档）；
#     两处都幂等（已派过 / 手上已有活 ⇒ 不回派）。
#   【判据】六次**真建号**（选族 → 选职业 → 取名三拍真敲）：每族派的 id = 该族引子、
#     欢迎屏印它的名字、六条互不相同；人类那条把三条件推满真交一次 ⇒ 屏上出接力话术 +
#     档上接力成主线 1 + 再调一次不重派。
print()
print("── ★ B5 六族引子 [按族段]：六族各派各的 · 欢迎屏 · 交引子接力主线 1 · 幂等")
import content.cmds_quest as _CQ60                                      # noqa: E402
_R60 = (("人类", "human"), ("精灵", "elf"), ("矮人", "dwarf"),
        ("兽人", "orc"), ("龙裔", "dragonkin"), ("亚人", "beastkin"))
_INTRO60 = {k: x for k, x in _q().items() if str(x.get("chain")) == "intro"}
_seen60 = {}
for _i60, (_rn60, _rs60) in enumerate(_R60):
    _u60 = "u_intro_%s" % _rs60
    _seed(GID, _u60, level=1, gold=30, loc="windmill_town", node="wt_gate_n")
    _drive(h, ad, _u60, "选族 %s" % _rn60)
    _drive(h, ad, _u60, "选职业 骑士")
    _w60 = _drive(h, ad, _u60, "名字 试%s" % _rn60)
    _d60 = PS.get_player(GID, _u60) or {}
    _exp60 = next((k for k, x in _INTRO60.items() if str(x.get("race")) == _rs60), "")
    _act60 = list(((_d60.get("flags") or {}).get("quests_active")) or [])
    chk("★ 按族段 · %s 建号派的是**本族**引子（期望 %s）" % (_rn60, _exp60),
        bool(_exp60) and _act60 == [_exp60], "quests_active=%s" % _act60)
    _qnm60 = (_q().get(_exp60) or {}).get("name", "")
    chk("★ 按族段 · %s 欢迎屏印的是本族引子的名字" % _rn60,
        bool(_qnm60) and any(_qnm60 in ln for ln in _w60), "屏=%r" % (_w60[-2:] if _w60 else []))
    if _exp60:
        _seen60[_rs60] = _exp60
chk("★ 按族段 · 六族各派各的（六条 id 互不相同 = 没有串族）",
    len(_seen60) == 6 and len(set(_seen60.values())) == 6, "%s" % _seen60)

# 交引子 ⇒ 主线 1 自动上手（三条件接活后各推满一格：talk 挂树 · kill 打过一只 ·
#   持有物是接活那一下 give 到手的（基线在 give 之前 ⇒ 自然算「接活后新达成」））
_uh60 = "u_intro_human"
_dh60 = PS.get_player(GID, _uh60) or {}
_flh60 = dict(_dh60.get("flags") or {})
_tkh60 = dict(_flh60.get("talked") or {})
_dlg60 = _CQ60._dlg_of("npc_xiaoman")
_tkh60[_dlg60] = int(_tkh60.get(_dlg60) or 0) + 1
_flh60["talked"] = _tkh60
_bkh60 = dict((_dh60.get("books") or {}).get("monster") or {})
_mr60 = dict(_bkh60.get("ms_field_mouse") or {})
_mr60["kills"] = int(_mr60.get("kills") or 0) + 1
_mr60.setdefault("day", 1)
_bkh60["ms_field_mouse"] = _mr60
_bk60 = dict(_dh60.get("books") or {})
_bk60["monster"] = _bkh60
_dh60["books"] = _bk60
_dh60["flags"] = _flh60
_fl60 = {kk: vv for kk, vv in _dh60.items() if kk not in ("group_id", "qq_id", "uid")}
PS.update_player(GID, _uh60, **_fl60)                                # 照 _Ad.save_player 的剔法落档
_del60 = _drive(h, ad, _uh60, "交 探路")
_qnmh60 = (_q().get("q_intro_human") or {}).get("name", "")
_nxt60 = ((_q().get(OB.first_quest_id()) or {}).get("name") or "")
chk("★ 按族段 · 三条件（talk/kill/持有物）齐 ⇒ 引子**真交得掉**",
    bool(_qnmh60) and any(CA.T("SYS_JOB_DELIVERED", name=_qnmh60) in ln for ln in _del60),
    "屏=%r" % _del60[-3:])
chk("★ 按族段 · 交掉引子 ⇒ 屏上出**接力话术**（SYS_JOB_AUTO_NEXT）",
    bool(_nxt60) and any(CA.T("SYS_JOB_AUTO_NEXT", name=_nxt60) in ln for ln in _del60),
    "屏=%r" % _del60[-3:])
_dh60b = PS.get_player(GID, _uh60) or {}
_act60b = list(((_dh60b.get("flags") or {}).get("quests_active")) or [])
_done60b = list(((_dh60b.get("flags") or {}).get("quests_done")) or [])
chk("★ 按族段 · 交掉引子 ⇒ 主线 1 **自动上手**（接力成册 · 不卡在证门上）",
    _act60b == [OB.first_quest_id()] and "q_intro_human" in _done60b,
    "active=%s done=%s" % (_act60b, _done60b))
_r60b, _ng60b = OB.auto_first_quest(_dh60b, _q())     # ★ F21 后返回 (id, give 行)
chk("★ 按族段 · 幂等（手上已有接力的活 ⇒ 再调一次不重派、且不发东西）",
    _r60b == "" and not _ng60b, "auto_first_quest 回=%r give行=%r" % (_r60b, _ng60b))

print("探针：引导层 · B 档：%s" % ("全绿" if not failures else "有红 X（%d 条）" % len(failures)))
sys.exit(1 if failures else 0)