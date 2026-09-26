# -*- coding: utf-8 -*-
"""探针：titles 域（十个称号）—— 条目对账 · 条件可求值 · 拿到那一下的行为 · 记数的口真的在加。

判据（★ = 跨域/行为，最要紧）：
  ① 十条齐 · id 形状对 · 编号 1–10 不重不漏（= 21 文档 §一 那张表）
  ② 每条形状：名 / 怎么拿到 / 依据 / 显示位置（口径 §一 的那一句）
  ③ ★ 跨域对账：条件里每个取值都在对应域里真存在（地图节点 / 物品 / 任务 / 怪 / 彩蛋谱 / 材料谱 / 对话树）
  ④ ★ 条件只用引擎算子的声明节点，且整表能编译（形状错当场抛，不静默）
  ⑤ ★ 造实例：**逐条造一个满足它的档** → scan 必须命中它；再扫一遍不再报（幂等）
  ⑤b ★ B3-10：「认得三种字的人」那个数 —— 四处文档 + 两处域里现算 = 同一个数；再由行为验一次
     （读满 12 条 → 挂上；少一条 → 一个字不给）
  ⑥ ★ 反向：什么都没做过的档 → 一个称号都不给（不白送）
  ⑦ ★ 显示跟着名字走：有称号 = 「名字 · 称号」，没称号 = 名字本身；只显示最近那个
  ⑧ ★ 接线真生效：走到就记一趟（note_step）· 听过一句就记一句（heard.note，同一句不记第二遍）
  ⑨ 称号指令接在 content.cmds_title 上（声明 → 实现体）· 四个触发点都调了 title_lines
  ⑩ 用到的文案槽位都在 texts 域（6 个）
  ⑪ ★ 端到端：真宿主 + 假适配器敲「去 北墙根」×2 +「搭话 哈根」+「观察」→ 落档里真的记下了
  ⑫ 可达性（信息行 + 一条底线）：今天能拿到 ≥5 个（不让前置换掉整层玩法）
  ⑬ ★ P-13（本波 w5）：称号 7「拾荒人的朋友」指谁 —— 条件那两条任务同一个 NPC 给的 ·
     「拾荒人」在 npcs 域 0 名（在 monsters 是精英、在 quests 是主线名）⇒ 只登记、不改数据
  ⑭ ★ P-67（2026-09-26 · 本波 w-h-ux · **裁决：名字不自解释**）：名字钉住「拾荒人的朋友」·
     十个名字形状上就是绰号（≤8 字 · 不带括号 / 逗号 / 句号）· 解释在后半句（真造档跑出那一行）

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_titles.py
"""
from __future__ import annotations

import importlib
import json
import os
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))          # rebuild_titles 的对账函数（与探针共用一份）
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402

ok = True
ID_RE = re.compile(r"^title_[a-z0-9_]+$")
OPS = {"and", "or", "contains", "eq", "ge", "truthy"}


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


print("探针：titles 域（十个称号）")
st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
st.install()

DO = st.domain("titles")
MP = st.domain("maps") or {}
PO = st.domain("pois") or {}
IT = st.domain("items") or {}
QU = st.domain("quests") or {}
MO = st.domain("monsters") or {}
RA = st.domain("races") or {}
CX = st.domain("codex") or {}
DL = st.domain("dialogues") or {}
TX = st.domain("texts") or {}
frm = st.domain("calendar") or {}
fw = st.domain("weather") or {}
HOUR_NAMES = {str((TX.get(e.get("slot")) or {}).get("value")) for k, e in frm.items() if not str(k).startswith("_")}
WEA_NAMES = {str((TX.get(e.get("slot")) or {}).get("value")) for k, e in fw.items() if not str(k).startswith("_")}

BOOK = {k: dict(v) for k, v in (DO or {}).items() if not str(k).startswith("_")}
chk("titles 域读得到", DO is not None and bool(BOOK), "%d 条" % len(BOOK))
if not BOOK:
    sys.exit(1)

# ① 十条齐 · 形状
bad_id = [k for k in BOOK if not ID_RE.match(k)]
nums = sorted(int(v.get("no") or 0) for v in BOOK.values())
chk("★ 十条齐（= 21 文档 §一 那张表）", len(BOOK) == 10, "%d 条" % len(BOOK))
chk("id 形状都是 title_xxx", not bad_id, bad_id[:4])
chk("编号 1–10 不重不漏", nums == list(range(1, 11)), nums)

# ② 每条形状
bad_shape = []
for k, v in BOOK.items():
    if (not v.get("name") or not v.get("how") or len(str(v.get("why") or "")) < 12
            or not v.get("where") or not v.get("cond")):
        bad_shape.append("%s(名=%r, 依据=%d 字, 显示位置=%r)"
                         % (k, v.get("name"), len(str(v.get("why") or "")), v.get("where")))
chk("★ 每条都有「名 / 怎么拿到 / 依据 / 显示位置 / 条件」", not bad_shape, bad_shape[:4])
chk("★ 显示位置都写着（口径 §一 的唯一一条显示规则）",
    len({v.get("where") for v in BOOK.values()}) == 1
    and "名字后面" in str(next(iter(BOOK.values())).get("where")),
    next(iter(BOOK.values())).get("where"))

# ③ ★ 跨域对账（探针自己重算，不信 titles.json 的自述）
import rebuild_titles as RB                                            # noqa: E402

D = {"maps": MP, "pois": PO, "items": IT, "quests": QU, "monsters": MO, "races": RA,
     "codex": CX, "dialogues": DL, "hours": HOUR_NAMES, "weathers": WEA_NAMES}
bad_ref = []
for k, v in BOOK.items():
    for field, val, target in RB.walk(dict(v.get("cond") or {}), []):
        key = RB._key_of(field)
        if key in RB.COUNT_KEYS + RB.COUNT_AT_KEYS:
            msg = RB.counter_ok(key, int(val), target, str(v.get("why") or ""), D)
        else:
            msg = RB.value_ok(field, val, target, D)
        if msg:
            bad_ref.append("%s: %s" % (k, msg))
chk("★ 条件里的每个取值都在对应域里真存在（含「那三件计数口将来由谁写」）", not bad_ref, bad_ref[:5])

# ④ 条件只用引擎算子 · 整表能编译
bad_op = []


def ops_of(node):
    out = set()
    if "op" in node:
        out.add(node["op"])
        for a in node.get("args") or []:
            out |= ops_of(a)
        sub = node.get("arg")
        if isinstance(sub, dict):
            out |= ops_of(sub)
    return out


for k, v in BOOK.items():
    got = ops_of(dict(v.get("cond") or {}))
    if not got or (got - OPS):
        bad_op.append("%s: %s" % (k, sorted(got)))
chk("★ 条件只用引擎算子（and/or/contains/eq/ge/truthy）", not bad_op, bad_op[:4])

from content import eggs as EG                                        # noqa: E402
from content import titles as TT                                       # noqa: E402
from content import calendar as CAL                                    # noqa: E402

try:
    SPECS = TT.specs()
    spec_err = ""
except Exception as exc:                                               # noqa: BLE001 —— 形状错就是红
    SPECS, spec_err = {}, "%s: %s" % (type(exc).__name__, exc)
chk("★ 十条条件整表编译通过（形状错当场抛）", set(SPECS) == set(BOOK) and not spec_err,
    spec_err or "%d 条" % len(SPECS))

# ⑤ ★ 逐条造实例：满足它的档 → scan 必须命中它；再扫一遍不再报
def profile_for(tid: str):
    """造一个「刚好满足这条称号」的档 + 它需要的那一格时辰/天气。"""
    p = {"day": 4, "level": 3, "name": "试", "loc": "", "node": "", "bag": {}, "equipped": {},
         "books": {"relic": {}, "material": {}, "monster": {}, "flavor": {}},
         "foot": {"nodes": {}, "visits": {}}, "flags": {}, "heard": {}}
    stx = dict(CAL.state())
    for field, val, target in RB.walk(dict(BOOK[tid]["cond"]), []):
        ck = RB._key_of(field)
        if ck == "where":
            loc, _, nd = str(val).partition(":")
            p["loc"], p["node"] = loc, nd
        elif ck == "map":
            p["loc"] = str(val)
        elif ck == "race":
            p["race"] = str(val)
        elif ck == "lore":
            p["race"] = "elf"
        elif ck == "read":
            p["books"]["relic"][str(val)] = {"known": True}
        elif ck == "been":
            p["foot"]["nodes"][str(val)] = 1
        elif ck == "hold":
            p["bag"][str(val)] = 1
        elif ck == "worn":
            p["equipped"]["helmet"] = str(val)
        elif ck == "set":
            iid = next((i for i, rec in IT.items() if (rec or {}).get("set_id") == val), None)
            p["bag"][str(iid)] = 1
        elif ck == "done":
            p["flags"]["quests_done"] = list(p["flags"].get("quests_done") or []) + [str(val)]
        elif ck == "kill":
            p["books"]["monster"][str(val)] = {"kills": 1}
        elif ck == "hour":
            stx["hour_name"] = str(val)
        elif ck == "weather":
            stx["weather_name"] = str(val)
        elif ck == "mat":
            p["books"]["material"][str(val)] = {"day": 1}
        elif ck == "read_all":
            for i in [k for k, v in PO.items() if v.get("into_codex")][:int(val)]:
                p["books"]["relic"][i] = {"known": True}
        elif ck == "visited":
            p["foot"]["visits"][str(target)] = int(val)
        elif ck == "heard":
            p["heard"][str(target)] = {"%s#%d" % ("x", i): 1 for i in range(int(val))}
        elif ck == "interrupt":
            p["foot"]["interrupts"] = int(val)
        elif ck == "clean":
            p["foot"]["clears"] = int(val)
        elif ck == "horn":
            p["flags"]["horn_fixed"] = True
        else:
            raise AssertionError("造实例：不认识的 ctx 字段 %r" % (field,))
    return p, stx


miss, twitch = [], []
for tid in BOOK:
    p, stx = profile_for(tid)
    first = TT.scan(p, stx)
    second = TT.scan(p, stx)
    if tid not in first:
        miss.append(tid)
    if second:
        twitch.append("%s 报了第二遍 %s" % (tid, second))
chk("★ 十条逐条造实例：满足它的档一定挂上它", not miss, miss[:4])
chk("★ 挂上那一下是幂等的（挂过的不再报）", not twitch, twitch[:3])

# ⑤b ★ B3-10：可读物那个数 —— **三处文档 + 两处域里现算 = 同一个数**，再由行为验一次。
#    （「认得三种字的人」的载体就是这 12 条：谁把某条挪出/挪进旧物谱，这里当场红。）
import read_kinds as RK10                                              # noqa: E402

_rk10 = RK10.audit(pois=PO, titles=BOOK)
chk("★ 可读物那个数处处一致（10 §一A %(10)d · 19 §三A %(f)d+%(e)d · 21 §一 %(21)d · 16 §二 %(16)d · "
    "pois.into_codex %(pc)s · titles.read_all %(ta)s）"
    % {"10": _rk10["doc"]["10"], "f": _rk10["doc"]["19_fixed"], "e": _rk10["doc"]["19_expand"],
       "21": _rk10["doc"]["21"], "16": _rk10["doc"]["16"],
       "pc": _rk10["live"].get("pois.into_codex"), "ta": _rk10["live"].get("titles.read_all")},
    not _rk10["bad"], _rk10["bad"])
_READS12 = sorted(k for k, v in PO.items() if v.get("into_codex"))


def _read_profile(ids):
    """读满 ids 这些可读物的档（其余全空 —— 只让 read_all 这一条起作用）。"""
    return {"day": 4, "level": 3, "name": "试", "loc": "", "node": "", "bag": {}, "equipped": {},
            "books": {"relic": {i: {"known": True} for i in ids}, "material": {}, "monster": {},
                      "flavor": {}},
            "foot": {"nodes": {}, "visits": {}}, "flags": {}, "heard": {}}


_FULL = TT.scan(_read_profile(_READS12), dict(CAL.state()))
_MINUS = TT.scan(_read_profile(_READS12[:-1]), dict(CAL.state()))
chk("★ 真跑：读满全部 %d 条 → 挂上「%s」· 少一条（%d 条）→ 一个字不给"
    % (len(_READS12), BOOK["title_three_scripts"]["name"], len(_READS12) - 1),
    _FULL == ["title_three_scripts"] and _MINUS == [],
    "满 %s / 少一条 %s" % (_FULL, _MINUS))

# ⑥ 反向：什么都没做过 → 一个都不给
blank = {"day": 1, "level": 1, "loc": "belt_east", "node": "be_birch", "bag": {}, "equipped": {},
         "books": {"relic": {}, "material": {}, "monster": {}, "flavor": {}},
         "foot": {"nodes": {}}, "flags": {}, "heard": {}}
chk("★ 什么都没做过的档：一个称号都不给（不白送）", TT.scan(blank, dict(CAL.state())) == [])

# ⑦ ★ 显示跟着名字走（只显示最近拿到的那个）
from content import cmds_ast as CA                                     # noqa: E402

p1 = {"name": "鱼鱼", "titles": {"title_tower_top": {"day": 3}}}
chk("★ 有称号：显示「名字 · 称号」",
    CA.name_with_title(p1) == "鱼鱼 · " + TT.name_of("title_tower_top"), CA.name_with_title(p1))
chk("没称号：就是名字本身", CA.name_with_title({"name": "鱼鱼"}) == "鱼鱼",
    CA.name_with_title({"name": "鱼鱼"}))
chk("名字空着的人：落「无名者 · 称号」",
    CA.name_with_title({"titles": {"title_tower_top": {"day": 3}}}) == "无名者 · 塔上的人")
p3 = {"name": "鱼鱼", "titles": {"title_tower_top": {"day": 3}, "title_night_net": {"day": 5}}}
chk("★ 挂着几个时：只显示最近拿到的那个（21 §一「同上（替换）」）",
    TT.newest(p3) and TT.newest(p3)[0] == "title_night_net", str(TT.newest(p3)))

# ⑧ ★ 接线真生效：记数的口真的在加（不看代码看不出来）
from content import codex as CM                                        # noqa: E402
from content import heard as HD                                        # noqa: E402

pp = {"day": 9, "foot": {}}
CM.note_step(pp, "belt_north", "bn_bone")
CM.note_step(pp, "belt_north", "bn_bone")
chk("★ 走到两趟 → 记 2 趟（「骨田的常客」靠它）",
    CM.foot(pp)["visits"].get("belt_north:bn_bone") == 2, CM.foot(pp)["visits"])
first_v = CM.note_visit(pp, "belt_north", "bn_bone")
chk("★ 「第一回到」与「去过几回」是两笔账（note_visit 不重复记 · note_step 每次都加）",
    first_v and not CM.note_visit(pp, "belt_north", "bn_bone")
    and CM.foot(pp)["visits"]["belt_north:bn_bone"] == 2)

hh = {"day": 9}
f1 = HD.note(hh, "dlg_hagen", "meet", 0)
f2 = HD.note(hh, "dlg_hagen", "meet", 0)
HD.note(hh, "dlg_hagen", "daily", 1)
chk("★ 听过哪一句记哪一句（同一句不记第二遍）",
    f1 and not f2 and HD.count(hh, "dlg_hagen") == 2, HD.count(hh, "dlg_hagen"))
chk("★ 出题口拿到的是「句数」（heard 那个键要的形状）",
    (TT.ctx(hh).get("heard") or {}).get("dlg_hagen") == 2, TT.ctx(hh).get("heard"))

# ⑨ 触发点接线（源码级）+ 称号指令接在 content.cmds_title 上
src_ast = open(str(REPO / "content" / "cmds_ast.py"), encoding="utf-8").read()
src_talk = open(str(REPO / "content" / "cmds_talk.py"), encoding="utf-8").read()
src_title = open(str(REPO / "content" / "titles.py"), encoding="utf-8").read()
src_cmd = open(str(REPO / "content" / "cmds_title.py"), encoding="utf-8").read()
n_ast = src_ast.count("title_lines(p, player, env)")
n_talk = src_talk.count("title_lines(p, player, env)")
chk("★ 观察 / 地图 / 触摸 都会扫（cmds_ast 里 3 处）", n_ast == 3, "实测 %d 处" % n_ast)
chk("★ 搭话也会扫（cmds_talk 里 1 处）", n_talk == 1, "实测 %d 处" % n_talk)
n_step = src_ast.count("CX.note_step(")
chk("★ 四条真的在走的实现体都记一趟（cmds_ast 里 4 处）", n_step == 4, "实测 %d 处" % n_step)
chk("★ 显示接在名字上（观察一处 yielded · 状态一处取件 —— 定义那处不算）",
    src_ast.count("yield name_with_title(p)") == 1 and src_ast.count("nm = name_with_title(p)") == 1,
    "实测 yield %d 处 / 取件 %d 处" % (src_ast.count("yield name_with_title(p)"),
                                     src_ast.count("nm = name_with_title(p)")))

CMDS = json.load(open(str(REPO / "content" / "data" / "commands.json"), encoding="utf-8"))
bind = ((CMDS.get("titles") or {}).get("bind") or {})
mod = importlib.import_module("content.cmds_title")
chk("★ 称号指令声明 → content.cmds_title:titles_book",
    bind.get("handler") == "content.cmds_title:titles_book", bind)
chk("实现体在 · 主词与别名都写着（称号 / 头衔）",
    callable(getattr(mod, "titles_book", None)) and len((CMDS.get("titles") or {}).get("patterns") or []) >= 2)

# ⑩ 用到的文案槽位都在 texts 域
slots = set(re.findall(r"SYS_TITLE_[A-Z_]+", src_ast + src_talk + src_title + src_cmd))
miss_slot = sorted(s for s in slots if s not in TX)
chk("★ 称号用到的文案槽位都在 texts 域（%d 个）" % len(slots), not miss_slot and len(slots) == 6, miss_slot)

# ⑪ ★ 端到端：真宿主 + 假适配器（记数的口在真流程里真的被踩到）
from saintess_engine.host.runtime import Host                          # noqa: E402


class _Ad:
    """三函数 + say（照 host-api 契约的最小适配器 —— 与 scripts/e2e_drive.py 同形）。"""

    def __init__(self, texts):
        self._msgs = [{"uid": "u_t", "group_id": "g_t", "text": t, "is_group": True} for t in texts]
        self.out = []
        self.saved = None

    def recv(self):
        return self._msgs.pop(0) if self._msgs else None

    def load_player(self, uid):
        return self.saved if uid == "u_t" else None

    def save_player(self, uid, data):
        self.saved = dict(data) if isinstance(data, dict) else data

    def say(self, to, text):
        self.out.append(str(text))


def _night_epoch(day: int = 100, hod: int = 21) -> float:
    """第 day 个游戏日的 hod 点（默认 21 点 = 夜）—— 哈根只在昏/夜站墙根。"""
    return (day * 86400.0 + hod * 3600.0) * CAL.scale_seconds() / 86400.0


STEPS = ["去 北墙根", "去 北口", "去 北墙根", "搭话 哈根", "观察", "称号"]
_db = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_titles.db")
try:
    os.remove(_db)
except OSError:
    pass
try:
    _ad = _Ad(STEPS)
    _host = Host(_ad, str(REPO), inject={"db_path": _db, "clock": (lambda: _night_epoch())})
    _host.boot()
    _lines = {}
    for _t in STEPS:
        _ad.out.clear()
        _host.handle({"uid": "u_t", "group_id": "g_t", "text": _t})
        _lines[_t] = list(_ad.out)
    _saved = _ad.saved or {}
    _visits = ((_saved.get("foot") or {}).get("visits") or {})
    _heard = _saved.get("heard") or {}
    chk("★ 端到端：真宿主敲「去 北墙根」两趟 → 落档里记了 2 趟",
        _visits.get("windmill_town:wt_wall") == 2, _visits)
    chk("★ 端到端：「搭话 哈根」真的记下听过的那一句",
        bool(_heard.get("dlg_hagen")), _heard)
    chk("★ 端到端：「称号」指令说得出话（不是回显声明）",
        bool(_lines.get("称号")) and not str(_lines.get("称号")[0]).startswith("【titles】"),
        (_lines.get("称号") or [""])[0][:40])
except Exception as exc:                                               # noqa: BLE001 —— 起不来就是红
    chk("★ 端到端跑得起来（真宿主契约）", False, "%s: %s" % (type(exc).__name__, exc))

# ⑬ ★ P-13（2026-09-26 · 本波 w5）：「拾荒人的朋友」到底指谁 —— 由**数据**说清，不靠注释
#   那条老账的由来：称号 7 的「怎么拿到」写着「完成拾荒人的两条支线」，而 npcs 域里**没有**
#   「拾荒人」这个人 —— 那它指的是谁？本档把这条链**每一环都现查一遍**（K80 的自检问法：
#   「这句指的是哪一条数据？」）：
#     · 称号 7 的条件那两条任务 = 同一个 NPC 给的（小满）
#     · 「拾荒人」在 npcs 域里 **0 命中**（不是人）；在 monsters 域里是精英（`ms_pick_scavenger`）；
#       在 quests 域里名字等于「拾荒人」的是**一条主线**（q_main_05 · 玛莎给的）
#   ⇒ 那句「完成拾荒人的两条支线」能且只能读成「（与）拾荒人（有关的那两条）支线」
#     = 小满给的那两条（24 §二 支 13 / 14：还石头 · 带他看塔）。B4-3 的只读复核就是这个结论。
#   ★ 这一档只**登记**（不改数据）：要让玩家读到的那句不含糊 ⇒ 改真源 `21_长期目标层_v1.md §一`
#     那一格（+ 口径 `16_称号域口径_v1.md` 同句），归主线（见本波 `_notes.md §三`）。
_NPC13 = st.domain("npcs") or {}
_TID13 = next((k for k, v in BOOK.items() if v.get("no") == 7), None)
_R13 = BOOK.get(_TID13) or {}
_DONE13 = [(a, b) for a, b, _c in RB.walk(dict(_R13.get("cond") or {}), [])
           if RB._key_of(a) == "done"]
_GIV13 = [(QU.get(b) or {}).get("giver") for _a, b in _DONE13]
chk("★ P-13：称号 7「%s」的条件 = 两条任务 %s —— 同一个 NPC 给的（%s ⇒ %s）"
    % (_R13.get("name"), [b for _a, b in _DONE13], sorted(set(_GIV13)),
       ((_NPC13.get(_GIV13[0]) or {}).get("name") if _GIV13 and _GIV13[0] else "")),
    len(_DONE13) == 2 and len(set(_GIV13)) == 1 and all(g in _NPC13 for g in _GIV13 if g))
_PICKN13 = [v.get("name") for v in _NPC13.values() if v.get("name") == "拾荒人"]
_PICKM13 = [k for k, v in MO.items() if v.get("name") == "拾荒人"]
_PICKQ13 = [k for k, v in QU.items() if v.get("name") == "拾荒人"]
chk("★ P-13：「拾荒人」在 npcs 域 **0 名**（它不是人）· 在 monsters 域 %s（精英）· "
    "在 quests 域 %s（主线，玛莎给的）—— 两条支线都是小满给的 ⇒ 那句不该读成「它自己的支线」"
    % (_PICKM13, _PICKQ13),
    not _PICKN13 and bool(_PICKM13) and bool(_PICKQ13))
# ★ 二选一的**依据**（为什么是「改正文案」而不是「补一个 NPC」）—— 两句话都由数据当场说清：
#   ① 「拾荒人」在数据里是**玩家的对手**：主线 `q_main_05`（名字就叫「拾荒人」· 玛莎给的）的要求
#      是 `kill ms_pick_scavenger` ⇒ 在同一张图里再补一个**同名 NPC** = 一个名字挂两个实体，
#      还会与主 5「打拾荒人」正面撞车（K97 那族：同名的两件东西）。
#   ② 能挂上称号 7 的那两条支线**已经是**小满给的（24 §二 支 13 / 14 · 口径 §二 第 7 行）——
#      NPC 本来就在，缺的只是玩家可见那句里点他的名 ⇒ 改那**一句文案**，不动数据。
_KILL13 = [(r or {}).get("monster") for r in ((QU.get("q_main_05") or {}).get("require") or [])
           if isinstance(r, dict) and r.get("kind") == "kill"]
chk("★ P-13 依据①：「拾荒人」这条主线 `q_main_05`（%s 给的）的要求 = 打死 %s ⇒ 「拾荒人」是**打的**，"
    "不是给支线的人 ⇒ ★ 不补同名 NPC（一个名字挂两个实体 + 与主 5 对撞）"
    % ((QU.get("q_main_05") or {}).get("giver"), _KILL13),
    "ms_pick_scavenger" in _KILL13)
chk("★ P-13 依据②：能挂上称号 7 的那两条支线的 giver 就是 %s（`npc_xiaoman`）—— 人本来就在数据里，"
    "缺的只是玩家可见那句点名 ⇒ **改文案**（要改的真源行逐字写在 `_notes.md`）"
    % ((_NPC13.get("npc_xiaoman") or {}).get("name") or "?"),
    sorted(set(_GIV13)) == ["npc_xiaoman"]
    and (_NPC13.get("npc_xiaoman") or {}).get("name") == "小满")

# ⑫ 可达性（信息行 + 一条底线）：今天的数据里几个拿得到
gaps, live = {}, []
for tid, v in BOOK.items():
    why = []
    for field, val, target in RB.walk(dict(v["cond"]), []):
        ck = RB._key_of(field)
        if ck in ("race", "lore"):
            why.append("要种族/铭文（建号未落地）")
        elif ck == "interrupt":
            why.append("要「打断成功」（战斗交互层未落 —— foot.interrupts 已备好）")
        elif ck == "clean":
            why.append("要「副本」（第一个副本未落 —— foot.clears 已备好）")
        elif ck == "horn":
            why.append("要隐藏线「号角」（口径未落 —— flags.horn_fixed 已备好）")
        elif ck == "heard":
            why.append("要对话层先说得出别的句子（取句顺序 P-12 —— heard 已接线）")
    if why:
        gaps[tid] = sorted(set(why))
    else:
        live.append(tid)
for tid in BOOK:
    print("  · %s %s：%s" % (BOOK[tid]["no"], BOOK[tid]["name"],
                             "今天拿得到" if tid in live else "等前置 —— " + "；".join(gaps[tid])))
# 底线：今天能拿到的不少于 5 个（1 等建号 · 5 等战斗交互层 · 6 等副本 · 9 等隐藏线 · 10 等取句顺序）；
# 这条盯的是「别让前置把整层长期目标捂死」，不是「必须全能拿到」。
chk("★ 今天就能拿到的 ≥ 5 个（不让前置换掉整层玩法）", len(live) >= 5,
    "%d 个：%s" % (len(live), live))

# ⑭ ★ P-67（2026-09-26 · 本波 w-h-ux · **裁决：称号名「不自解释」**）
#   老账问的是「称号名『拾荒人的朋友』要不要自解释」。本路裁：**不要** —— **绰号就要像绰号**。
#   依据三条：
#     ① `21 §一` 的原则是「**称号本身就是剧情**」：名字负责**让人记住**（短、像人嘴里说出来的），
#        说明负责**说清**（就是 `SYS_TITLE_ROW` 那个破折号后面那半句）。两件事两处各干一件；
#        名字里塞解释 = 把一句描述当绰号，玩家念不出来、也记不住。
#     ② 「指谁」这件事 P-13 已经解决在**后半个句子里**（`how` 那一句点名「小满」，数据驱动 ——
#        本探针 ⑬ 钉着）⇒ 名字一个字不用动。
#     ③ 形状就是这条裁决的机器版：十个名字**都 ≤8 字**、**不带括号 / 逗号 / 句号 / 破折号**
#        （形状上就是绰号）。谁哪天写一个「骨田那个小孩的朋友」进来 —— 先红。
_PICK14 = next((k for k, v in BOOK.items() if v.get("no") == 7), None)
_R14 = BOOK.get(_PICK14) or {}
chk("★ P-67 名字钉住：称号 7 = 「%s」（一个字不动 —— 改名字要同批改 21 §一 与 16 §二 两处，"
    "`rebuild_titles` 会拿两处对账）" % _R14.get("name"),
    _R14.get("name") == "拾荒人的朋友" and _R14.get("how") == "完成小满的两条支线（还石头 · 带他看塔）",
    "%r / %r" % (_R14.get("name"), _R14.get("how")))
_BADCH14 = ("（", "(", "）", ")", "，", ",", "。", "——", "·", "：", ":")
_bad14 = [(k, v.get("name")) for k, v in BOOK.items()
          if len(str(v.get("name") or "")) > 8 or any(c in str(v.get("name") or "") for c in _BADCH14)]
chk("★ P-67 十个名字**形状上就是绰号**（都 ≤8 字 · 不带括号 / 逗号 / 句号 / 破折号 —— "
    "名字里塞解释 = 把一句描述当绰号）：%s"
    % " · ".join("%d %s" % (v["no"], v["name"]) for _k, v in sorted(BOOK.items(),
                                                                   key=lambda kv: kv[1].get("no") or 0)),
    not _bad14, "%s" % _bad14)
_p14, _err14 = None, ""
try:
    _p14, _stx14 = profile_for(_PICK14)               # ⑤ 那个造档器：造一个刚好满足称号 7 的档
    TT.scan(_p14, _stx14)
except Exception as _e14:                                                # noqa: BLE001
    _p14 = None
    _err14 = "%s: %s" % (type(_e14).__name__, _e14)
_hit14 = [x for x in TT.got(_p14 or {}) if x[0] == _PICK14]
_TPL14 = (TX.get("SYS_TITLE_ROW") or {}).get("value") or ""
_row14 = ("✦ %s —— %s" % (_hit14[0][1], _hit14[0][2])) if _hit14 else ""
_want14 = _TPL14.replace("{name}", str(_R14.get("name") or "")).replace(
    "{how}", str(_R14.get("how") or ""))
chk("★ P-67 解释在**后半句**（拿称号 7 的档真跑 → 玩家看到的那一行 = 「%s」）："
    "名字负责记住 · 破折号后面那半句负责说清谁（小满）—— 这就是「不自解释」的分工" % _want14,
    bool(_hit14) and _row14 == _want14 and "小满" in _want14,
    "%r%s" % (_row14, ("（造档失败：%s）" % _err14) if _err14 else ""))

print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
