# -*- coding: utf-8 -*-
"""探针：组队（B3-25）—— party 域 · 那三条指令 + 一个『同意』动作 · 进战那一刻的人数。

这一批把「声明了、看得见、没有处理器」的 `party`（队伍/组队）与 `party_leave`（离队）真接上，
`party_invite`（邀请）从 invisible 开成可见，另**新加**了 `party_accept`（同意 —— 文字游戏里
弹不出窗，「同意」只能是被邀的人自己打的那一下）。

判据（六档，从浅到深）
----------------------
① 形状档   域读得到 · 必填字段照 **schema 现读** · 值域合法 · 键名命中 schema 的 patternProperties ·
           ★ 口径坏了当场抛（四档）
② 跨域档   ★ monsters 那张 `party_scale` 的键集合 == 本域的「有效人数档 = 1..上限」· 每档都有数 ·
           ★ 代码里引用的每个 `SYS_PARTY_*` 槽位都在 texts 里（且占位与 params 双向对账）
③ 可复算档 ★ 面板逐档现算 == 面板 × 生成器那张表 · 队名（pid）可复现 ·
           ★ 「同一处」的门槛**真读域**（两态：同图不同节点 = 同一处；`same_node` 一开就变不在一处）
④ 接线档   ★ 四条指令的触发词各自命中自己（引擎 registry 现跑）· **真宿主真敲**：建队 → 邀请 →
           同意 → 看队 → fail-closed 八档 → 满员 → 过期 → 解散 → 自愈，逐条与「域 + texts 现算的
           期望」**逐字对账**；档上副作用逐条核（`flags.party` 的形状与角色）
⑤ 纪律档   ★ 幂等（第二遍一字不差 · 档不动）· 看队不动档 · ★ 默认档不被就地改 ·
           ★ 名册是现算的（pid 对不上的假档不算队员）· 存档读不出来 ⇒ 四条各回一句点名行、不动档
⑥ 进战人数 ★ `cmds_battle` 那三处 `party=…` 真传人数：没队 = 1 · 同节点的队友算进来 ·
           队友在别的节点 / 血空都不算 · 存档读不出来 = None（= 不知道 ⇒ 不缩放，接上 B3-17 那条）
⑦ ★ B4-18  「集火」按**此刻真在不在队里**分档（单人两句 / 有队一句 / 队读不出来同有队）·
           两条都真敲、都不动档
         ★ **P-57 改判据（2026-09-26 · w9）**：`逃跑` 在**野外 / 单人**那条老路上已经是
           **真动作**（掷一次定成败 · 失败率 30%）—— 并**加严**：同种子两态都碰得到
           （探针按同一式子现算手气，不靠「跑很多次看比例」）· 跑成 = 这一场没打（无结算）
           · 被拦下 = 那一手白花、这一场照打 · 失败率只有一个口（改声明表 ⇒ 翻面）
         ★ **本波（多人那条接上）**：有队时**不再**回那句桩句 —— 两人同格真组一队、
           先手那位真掷（与单人同一条规则），两态（改率 1.0 / 0.0）都在**多人那一格**里跑到；
           那句退役的桩句由 `probe_copy.RETIRED_DOC` 登记（真源那一行请主线删）

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_party.py
Python 用 3.12（3.11 假红）。
"""
from __future__ import annotations

import io
import json
import os
import random
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                      # noqa: E402
from saintess_engine.host.runtime import Host                       # noqa: E402
from saintess_engine.command import CommandRegistry                 # noqa: E402

ok = True


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


# ── 假钟（可复现）+ 一个干净的库 ──────────────────────────────────
FIXED = [100.0 * 7200 + 3600.0]
DB = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_party.db")
try:
    os.remove(DB)
except OSError:
    pass


def _clock():
    return FIXED[0]


G = "g_party"
LOC, NODE = "belt_north", "bn_bone"            # 骨田（当「同一处」）
LOC2, NODE2 = "belt_east", "be_birch"          # 另一张图（东带 · 白桦林）
PIN = "ms_field_mouse"                         # 遇敌钉死（战斗内部抽怪 ⇒ 不钉住不可复现）
NAMES = {"u_a": "甲", "u_b": "乙", "u_c": "丙", "u_d": "丁",
         "u_e": "戊", "u_f": "己", "u_g": "庚", "u_h": "辛"}

st = load_stack(str(REPO), inject={"db_path": DB, "clock": _clock})
st.install()

from content import party as PT                                     # noqa: E402
from content import cmds_ast as CA                                  # noqa: E402
from content import combat as CBT                                   # noqa: E402
from content import persistence as PS                               # noqa: E402
import rebuild_monsters as RB                                       # noqa: E402

PJ = st.domain("party") or {}
TX = st.domain("texts") or {}
MON = st.domain("monsters") or {}
MP = st.domain("maps") or {}
DECL = st.command_declarations()


#: ★ P0-1 续（2026-09-29 · aep0）：战斗日志行现在**逐字带【N 刻】**（真源 26_ §三 优化 1），
#:   而那一格是**战斗绝对时刻** —— 只有读端（`_flee_decide` 里的 `Battle._now`）知道，
#:   夹具算不出来。⇒ 下面这个「现算期望」对含 `{t}` 的槽位**只对行首锚**
#:   （`图标【…刻】`那一段），与 `probe_texts._ctl_pre` 同一手法（对前缀，不对整条模板）。
#:   ★ 判据要保护的是「这一手跑成了/被拦下了、出的是哪一句」—— 刻数不是它保护的东西；
#:     刻数本身由 `probe_texts`（活 cue 行必带【N 刻】）钉着，未削弱。
#: ★ 锚只取**外廓**（`图标【` … `刻】`），中间那一格刻数**不参与匹配** ——
#:   夹具算不出战斗绝对时刻（只有读端知道），而屏上是「⚔️【127 刻】」；
#:   若把未渲染的 `{t}` 留在锚里，`in` 必然不上。刻数本身由 `probe_texts`
#:   （活 cue 行必带【N 刻】）单独钉着 ⇒ 判据未削弱。
_STAMP_PRE = re.compile(r"^([^【]*【)[^】]*(刻】)")


def _r(key, **kw):
    """槽位现算的期望串（不手写镜像表）。含 `{t}` 的战斗日志行只对**行首锚**。"""
    s = (TX.get(key) or {}).get("value", "")
    for k, v in kw.items():
        s = s.replace("{%s}" % k, str(v))
    if "{t" in s:
        assert _STAMP_PRE.match(s), "战斗日志行首必须带【…刻】（真源 26_ §三 优化 1）：%r" % s
        s = s.replace("{t}", "*")        # ★ 整句逐字，只把**刻数那一格**换成通配
    return s


def _where(loc, node):
    """「现在在哪儿」—— 从 maps 域**现算**（与实现同一个口径，各自独立算）。"""
    m = MP.get(loc) or {}
    nm = str(m.get("name") or loc or "")
    nd = next((str(n.get("name") or "") for n in (m.get("nodes") or []) if n.get("id") == node),
              str(node or ""))
    if nd and nd in nm:
        return nm
    return "%s·%s" % (nm, nd) if nd and nm else (nm or nd)


WHERE_HERE = _where(LOC, NODE)
WHERE_FAR = _where(LOC2, NODE2)

print("探针：组队（party 域 · 队伍/邀请/同意/离队 · 进战人数）")

# ══════════════════════════════════════════════════════════════
# ① 形状档
# ══════════════════════════════════════════════════════════════
print("① 形状档：party 域（口径那一条）")
RECS = {k: v for k, v in PJ.items() if not str(k).startswith("_")}
SCHEMA = json.load(io.open(str(REPO / "schemas" / "party.schema.json"), encoding="utf-8"))
REQ = list(SCHEMA["$defs"]["rule"]["required"])
_val = RECS.get("pt_rules", {})
chk("域读得到（%d 条口径 + `_src` 元信息 · 上限 %s 人 · 邀请有效期 %s 刻）"
    % (len(RECS), PT.max_members(), PT.invite_ttl_ticks()),
    len(RECS) == 1 and "pt_rules" in RECS and "_src" in PJ)
chk("★ 必填字段**照 schema 现读**（%s）—— 一条不缺" % " / ".join(REQ),
    all(k in _val for k in REQ), "%s" % sorted(_val))
chk("值域合法（上限 = ≥2 的整数 · 有效期 = 正整数 · 四个开关都是 true/false）",
    isinstance(_val.get("max_members"), int) and not isinstance(_val.get("max_members"), bool)
    and _val["max_members"] >= 2
    and isinstance(_val.get("invite_ttl_ticks"), int) and _val["invite_ttl_ticks"] > 0
    and all(isinstance(_val.get(k), bool)
            for k in ("same_map", "same_node", "captain_is_founder", "join_needs_accept")))
chk("★ 记录键名都命中 schema 的 patternProperties（%s）"
    % " / ".join(SCHEMA["patternProperties"]),
    all(re.match(r"^pt_[a-z0-9_]+$", k) for k in RECS))
chk("★ 「上限」与「有效人数档」是同一件事：grades == 1..上限（%s）" % PT.grades(),
    PT.grades() == list(range(1, PT.max_members() + 1)))


def _swap_rules(rec):
    """临时把域里那条口径换成 `rec`（`None` = 干脆没有这一条）—— 判 fail-closed 用，跑完还原。"""
    keep = PT._C.get("party")
    dom = dict(keep or {})
    if rec is None:
        dom.pop("pt_rules", None)
    else:
        dom["pt_rules"] = rec
    PT._C["party"] = dom
    return keep


def _raises(rec):
    keep = _swap_rules(rec)
    try:
        PT.rules()
        return False
    except PT.PartyError:
        return True
    finally:
        PT._C["party"] = keep


_GOOD = dict(_val)
_FC = [("缺口径", None),
       ("上限不是整数", dict(_GOOD, max_members="4")),
       ("有效期不是正整数", dict(_GOOD, invite_ttl_ticks=0)),
       ("开关不是布尔", dict(_GOOD, same_map="yes"))]
_FC_BAD = [w for w, rec in _FC if not _raises(rec)]
chk("★ 口径坏了当场抛 `PartyError`（四条：%s）· 还原之后域还是好的（上限 %s）"
    % (" / ".join(w for w, _ in _FC), PT.max_members()),
    not _FC_BAD and PT.max_members() == 4, "%s" % _FC_BAD)

# ══════════════════════════════════════════════════════════════
# ② 跨域档
# ══════════════════════════════════════════════════════════════
print("② 跨域档：monsters 那张表 ↔ 本域的档位 · 代码引用的槽位都在 texts 里")
_PS_ON = sorted(k for k, m in MON.items() if (m.get("mods") or {}).get("party_scale"))
_PS_KEYS = sorted(int(k) for k in (((MON.get(_PS_ON[0]) if _PS_ON else {}).get("mods") or {})
                                   .get("party_scale") or {}))
chk("★ 带「按人数缩放」表的怪 == 生成器点名的那几只（%s）"
    % " · ".join(MON[k]["name"] for k in _PS_ON), _PS_ON == sorted(RB.PARTY_SCALE_ON), "%s" % _PS_ON)
chk("★ 那张表的键集合 == 本域的「有效人数档 = 1..上限」（%s vs %s）" % (_PS_KEYS, PT.grades()),
    _PS_KEYS == PT.grades(), "%s" % _PS_KEYS)
chk("★ 每一只带表的怪**每档都有数**（不许有档没数 ⇒ 静默走设计值）",
    all(sorted(int(k) for k in (((MON[k].get("mods") or {}).get("party_scale") or {})))
        == PT.grades() for k in _PS_ON))

_SRC = io.open(str(REPO / "content" / "cmds_party.py"), encoding="utf-8").read()
#   ★ 槽位键在实现体里**两处形式**：`T("…")` 直调 + 映射表里的字符串字面量（`_INV_SLOT` 那些）
#     ⇒ 两处都扫（与 probe_copy 的 ④/⑤ 同口径：字面量也算引用）。
_LITS = sorted(set(re.findall(r'"(SYS_PARTY_[A-Z0-9_]+)"', _SRC)))
chk("★ 实现体引用的 %d 个 `SYS_PARTY_*` 槽位都在 texts 里" % len(_LITS),
    not [k for k in _LITS if k not in TX], "%s" % [k for k in _LITS if k not in TX])
_BADPH = []
for _k in _LITS:
    _ph = set(re.findall(r"\{(\w+)\}", (TX.get(_k) or {}).get("value", "")))
    _decl = set((TX.get(_k) or {}).get("params") or [])
    if _ph != _decl:
        _BADPH.append((_k, sorted(_ph ^ _decl)))
chk("★ 每个槽位的占位与 params **双向对账**（现算，不抄一份）", not _BADPH, "%s" % _BADPH)
chk("★ 本批那 %d 条槽位都在 `SYS_PARTY_*` 这一族里（键名规则与 texts 探针同一条）" % len(_LITS),
    all(re.fullmatch(r"SYS_PARTY_[A-Z0-9_]+", k) for k in _LITS) and len(_LITS) >= 24,
    "%d 条" % len(_LITS))

# ══════════════════════════════════════════════════════════════
# ③ 可复算档
# ══════════════════════════════════════════════════════════════
print("③ 可复算档：面板逐档 · 队名可复现 · 「同一处」的门槛真读域")
_BOSS = RB.PARTY_SCALE_ON[0]
_BH = MON[_BOSS].get("panel") or {}
_LAD = [(n, int(CBT.monster_actor(_BOSS, MON[_BOSS], party=n).get("max_hp"))) for n in PT.grades()]
_WANT = [(n, int(round(float(_BH["hp"]) * float(RB.PARTY_SCALE[str(n)]["hp"])))) for n in PT.grades()]
chk("★ 面板逐档现算 == 面板 × 生成器那张表（%s）"
    % " · ".join("%d 人 %s" % (n, hp) for n, hp in _LAD), _LAD == _WANT, "%s" % _WANT)
chk("★ 队名（pid）可复现（同一 uid + 同一刻 ⇒ 同一个名）：%s" % PT.pid_of("u_a", 12345),
    PT.pid_of("u_a", 12345) == PT.pid_of("u_a", 12345)
    and PT.pid_of("u_a", 12345) != PT.pid_of("u_a", 12346))
_SAME_SAME_MAP = PT.same_place({"loc": LOC, "node": NODE}, {"loc": LOC, "node": "bn_camp"})
_keep_rules = _swap_rules(dict(_val, same_node=True))
try:
    _SAME_STRICT = PT.same_place({"loc": LOC, "node": NODE}, {"loc": LOC, "node": "bn_camp"})
finally:
    PT._C["party"] = _keep_rules
chk("★ 「同一处」的门槛**真读域**两态：`same_node=false` ⇒ 同图不同节点算同一处（%s）· "
    "一开成 true ⇒ 就不算了（%s）—— 改域一个开关就改行为，代码不写死" % (_SAME_SAME_MAP, _SAME_STRICT),
    _SAME_SAME_MAP is True and _SAME_STRICT is False)

_SYN_ROWS = [{"uid": "u_b", "data": {"flags": {"party": {"id": "pt_u_b_1", "role": "captain",
                                                         "tick": 1000,
                                                         "invites": {"u_a": {"tick": 1000}}}}}}]
_TTL_OK = len(PT.pending(_SYN_ROWS, "u_a", 1000 + PT.invite_ttl_ticks())) == 1
_TTL_NO = len(PT.pending(_SYN_ROWS, "u_a", 1000 + PT.invite_ttl_ticks() + 1)) == 0
chk("★ 邀请有效期的**边界**（正好 %d 刻还算数 · 过一刻就不算）" % PT.invite_ttl_ticks(),
    _TTL_OK and _TTL_NO, "%s / %s" % (_TTL_OK, _TTL_NO))

# ══════════════════════════════════════════════════════════════
# ④ 接线档：真宿主真敲（多人同群 · 一张干净的库）
# ══════════════════════════════════════════════════════════════
print("④ 接线档：四条组队指令真敲（真宿主契约 · 多人同群）")


class _Ad(object):
    """多人的最小适配器：recv / load_player / save_player / say —— 每次落档都镜像进本包的库。"""

    def __init__(self):
        self.players = {}
        self.msgs = []
        self.out = []

    def seed(self, uid, name, cls="cls_knight", **kw):
        d = dict(CA.DEFAULT_PLAYER)
        d.update({"name": name, "race": "human", "cls": cls, "level": 5, "hp": 80, "gold": 30,
                  "loc": LOC, "node": NODE, "prev": [], "bag": {}, "equipped": {},
                  "codex": {}, "flags": {}})
        d.update(kw)
        d = CA._p(d)
        self.players[uid] = d
        PS.update_player(G, uid, **d)
        return d

    def recv(self):
        return self.msgs.pop(0) if self.msgs else None

    def load_player(self, uid):
        return self.players.get(uid)

    def save_player(self, uid, data):
        self.players[uid] = dict(data) if isinstance(data, dict) else {}
        PS.update_player(G, uid, **self.players[uid])

    def say(self, to, text):
        self.out.append(str(text))


_ad = _Ad()
_SEED = {}
for _u, _n in NAMES.items():
    _kw = {"cls": ""} if _u == "u_e" else {}                 # 戊：还没定职业（建号没走完）
    if _u == "u_d":                                          # 丁：站在另一张图上
        _kw.update({"loc": LOC2, "node": NODE2})
    _SEED[_u] = _ad.seed(_u, _n, **_kw)

_host = Host(_ad, str(REPO), inject={"db_path": DB, "clock": _clock})
_host.boot()


def say(uid, text):
    _ad.out.clear()
    _host.handle({"uid": uid, "group_id": G, "text": text})
    return list(_ad.out)


def rec(uid):
    """档上那一格（**读库** —— 真宿主的库就是包这半边）。"""
    d = PS.get_player(G, uid) or {}
    return (d.get("flags") or {}).get("party")


_REG = CommandRegistry(name="probe_party").load(DECL)
_ROUTE = [("队伍", "party"), ("组队", "party"), ("邀请 乙", "party_invite"),
          ("同意", "party_accept"), ("离队", "party_leave")]
chk("★ 四条组队指令的触发词各自命中自己（%s）" % " · ".join("%s→%s" % kv for kv in _ROUTE),
    all(getattr(_REG.first_hit(t, visible_only=True), "key", None) == k for t, k in _ROUTE))
chk("★ 四条都挂了 bind（%s）" % " · ".join(k for _t, k in _ROUTE),
    all((DECL.get(k) or {}).get("bind") for _t, k in _ROUTE))

# ── 一、建队（单人敲『队伍』= 起个队）
_B = []
_pv = CA._p(dict(_SEED["u_a"]))
_o = say("u_a", "队伍")
_EXP = [_r("SYS_PARTY_MAKE", max=PT.max_members()),
        _r("SYS_PARTY_HEAD", n=1, max=PT.max_members(), cap="甲"),
        _r("SYS_PARTY_ROW", name="甲", level=_pv["level"], hp=_pv["hp"], hpmax=_pv["hp_max"],
           where=WHERE_HERE),
        _r("SYS_PARTY_TAIL")]
if _o != _EXP:
    _B.append(("建队", _o, _EXP))
_rc = rec("u_a") or {}
if _rc.get("role") != PT.ROLE_CAPTAIN or not str(_rc.get("id") or "") or _rc.get("invites") != {}:
    _B.append(("建队没落成队长那一格", _rc))
_CAP_PID = str(_rc.get("id") or "")
chk("★ `队伍` 真敲（单人）= 建队：四行逐字对槽位 · 档上写成「队长那一格」（%s · invites 空）"
    % _CAP_PID, not _B, "%s" % _B[:2])

# ── 二、邀请（同图的人）
_B = []
_o = say("u_a", "邀请 乙")
_EXP = [_r("SYS_PARTY_INV_OK", name="乙", ttl=PT.invite_ttl_ticks())]
if _o != _EXP:
    _B.append(("邀请 乙", _o, _EXP))
if ((rec("u_a") or {}).get("invites") or {}).get("u_b") is None:
    _B.append(("邀请没记在队长那一格上", rec("u_a")))
if rec("u_b") is not None:
    _B.append(("被邀的人**这一步不许**被写进队", rec("u_b")))
if say("u_a", "邀请 丙") != [_r("SYS_PARTY_INV_OK", name="丙", ttl=PT.invite_ttl_ticks())]:
    _B.append(("邀请 丙", say("u_a", "邀请 丙")))
if say("u_a", "邀请 丙") != [_r("SYS_PARTY_INV_AGAIN", name="丙")]:
    _B.append(("重复邀请", say("u_a", "邀请 丙")))
chk("★ `邀请 <名字>` 真敲：记在**队长那一格**（被邀的人这一步一个格子都不动）· 重复邀请有回话",
    not _B, "%s" % _B[:2])

# ── 三、同意（本人在有效期内自己敲）
_B = []
_o = say("u_b", "同意")
if _o != [_r("SYS_PARTY_ACC_OK", cap="甲", n=2)]:
    _B.append(("同意", _o, [_r("SYS_PARTY_ACC_OK", cap="甲", n=2)]))
_MB = rec("u_b") or {}
if _MB.get("role") != PT.ROLE_MEMBER or str(_MB.get("captain")) != "u_a" \
        or str(_MB.get("id")) != _CAP_PID:
    _B.append(("入队那一格不对", _MB))
if say("u_b", "同意") != [_r("SYS_PARTY_JOINED", cap="甲")]:
    _B.append(("已在队里再敲同意", say("u_b", "同意")))
if rec("u_b") != _MB:
    _B.append(("第二遍改了档（幂等破了）", rec("u_b"), _MB))
chk("★ `同意` 真敲：入队（逐字对槽位 · 那格写成「队员」且 id 与队长的对得上）· "
    "**第二遍一字不差且档不动**（幂等）", not _B, "%s" % _B[:2])

# ── 四、看队（队长与队员两条路看到同一份名册）
_B = []
_pv2 = CA._p(dict(_SEED["u_b"]))
_EXP = [_r("SYS_PARTY_HEAD", n=2, max=PT.max_members(), cap="甲"),
        _r("SYS_PARTY_ROW", name="甲", level=_pv["level"], hp=_pv["hp"], hpmax=_pv["hp_max"],
           where=WHERE_HERE),
        _r("SYS_PARTY_ROW", name="乙", level=_pv2["level"], hp=_pv2["hp"], hpmax=_pv2["hp_max"],
           where=WHERE_HERE),
        _r("SYS_PARTY_TAIL")]
if say("u_a", "队伍") != _EXP:
    _B.append(("队长看队", say("u_a", "队伍"), _EXP))
_mb0 = rec("u_b")
_o = say("u_b", "队伍")
if _o != _EXP:
    _B.append(("队员看队", _o, _EXP))
if rec("u_b") != _mb0 or rec("u_a") is None:
    _B.append(("看队动了档", rec("u_b"), rec("u_a")))
chk("★ `队伍` 真敲（队长 / 队员两条路）：看到**同一份现算的名册**（2/4 · 逐人一行）· 看队不动档",
    not _B, "%s" % _B[:2])

# ── 四之二、★ 本波：**有邀请在身时敲『队伍』不该把自己立成队长**
#    起因（试玩报告 §5⑧）：被邀的人只想看一眼，原先那一刻会顺手 `create`
#    （「你起了个队（队长：你）」）⇒ 邀他的人再邀他就撞「他在别人的队里」，被卡一轮。
#    判据两态：① 被邀的人敲『队伍』⇒ 只回「没在队里」+ 那一封邀请，档上**不出现队长那一格**；
#              ② 对照：**没邀请在身**的人敲『队伍』⇒ 照旧建队（老口径一个字没变）。
_B = []


def _unparty(uid):
    """把这几位的队格清掉（`_set_party` 定义在后面那一节 ⇒ 这儿自己来一下，一行不差）。"""
    d = dict(_ad.players[uid])
    f = dict(d.get("flags") or {})
    f.pop("party", None)
    d["flags"] = f
    d = CA._p(d)
    _ad.players[uid] = d
    PS.update_player(G, uid, **d)


for _u in ("u_c", "u_f", "u_g"):
    _unparty(_u)
_o_c = say("u_c", "队伍")                                   # 丙 起个队（队长）
say("u_c", "邀请 己")                                       # 丙 邀 己
if rec("u_f") is not None:
    _B.append(("被邀那一步就不该写档", rec("u_f")))
_o_f = say("u_f", "队伍")
_EXP_F = [_r("SYS_PARTY_LV_NONE"),
          _r("SYS_PARTY_PEND", cap="丙", left=PT.invite_ttl_ticks())]
if _o_f != _EXP_F:
    _B.append(("被邀的人敲『队伍』", _o_f, _EXP_F))
if rec("u_f") is not None:
    _B.append(("被邀的人被顺手立成了队长", rec("u_f")))
_o_f2 = say("u_f", "队伍")                                   # 幂等：再来一遍还是那两行、档还空着
if _o_f2 != _EXP_F or rec("u_f") is not None:
    _B.append(("第二遍变了", _o_f2, rec("u_f")))
_o_g = say("u_g", "队伍")                                   # 对照：没邀请 ⇒ 照旧建队
_pv_g = CA._p(dict(_SEED["u_g"]))
_EXP_G = [_r("SYS_PARTY_MAKE", max=PT.max_members()),
          _r("SYS_PARTY_HEAD", n=1, max=PT.max_members(), cap="庚"),
          _r("SYS_PARTY_ROW", name="庚", level=_pv_g["level"], hp=_pv_g["hp"],
             hpmax=_pv_g["hp_max"], where=WHERE_HERE),
          _r("SYS_PARTY_TAIL")]
if _o_g != _EXP_G:
    _B.append(("对照：没邀请的人敲『队伍』", _o_g, _EXP_G))
chk("★ 本波：**有邀请在身**时敲『队伍』= 只回「没在队里」+ 那一封邀请（档上**不立队长**）· "
    "没邀请的人照旧建队（对照）", not _B, "%s" % _B[:2])
for _u in ("u_c", "u_f", "u_g"):
    _unparty(_u)

# ── 五、fail-closed 八档（逐条明确回话；被拒的那几支一个格子都不动）
_B = []
_pend0 = dict((rec("u_a") or {}).get("invites") or {})
_CASES = [
    ("u_b", "邀请 丙", _r("SYS_PARTY_INV_NOTCAP", cap="甲"), "不是队长"),
    ("u_a", "邀请 甲", _r("SYS_PARTY_INV_SELF"), "邀自己"),
    ("u_a", "邀请 丁", _r("SYS_PARTY_INV_FAR", name="丁", where=WHERE_FAR), "不同图"),
    ("u_a", "邀请 戊", _r("SYS_PARTY_INV_NOCLS", name="戊"), "还没定职业"),
    ("u_a", "邀请 谁都不认识", _r("SYS_PARTY_INV_NOBODY", name="谁都不认识"), "查无此人"),
    ("u_a", "邀请 乙", _r("SYS_PARTY_INV_MEMBER", name="乙"), "已在本队"),
    ("u_a", "邀请", _r("SYS_PARTY_INV_ASK"), "没带名字"),
    ("u_d", "同意", _r("SYS_PARTY_ACC_NONE"), "没人邀你"),
]
for _u, _t, _e, _why in _CASES:
    _got = say(_u, _t)
    if _got != [_e]:
        _B.append((_why, _t, _got, [_e]))
if sorted((rec("u_a") or {}).get("invites") or {}) != sorted(_pend0):
    _B.append(("被拒的八档里有一档真写进了邀请", _pend0, rec("u_a")))
chk("★ fail-closed 八档真敲（%s）—— 逐条明确回话 · 被拒的**一个格子都不动**"
    % " / ".join(c[3] for c in _CASES), not _B, "%s" % _B[:2])

# ── 六、满员 · 过期 · 解散 · 自愈
_B = []
for _u in ("u_c", "u_f", "u_g"):
    say("u_a", "邀请 %s" % NAMES[_u])
if say("u_c", "同意") != [_r("SYS_PARTY_ACC_OK", cap="甲", n=3)]:
    _B.append(("第三个入队", say("u_c", "同意")))
if say("u_f", "同意") != [_r("SYS_PARTY_ACC_OK", cap="甲", n=4)]:
    _B.append(("第四个入队", say("u_f", "同意")))
if say("u_a", "邀请 辛") != [_r("SYS_PARTY_INV_FULL", max=PT.max_members())]:
    _B.append(("满员再邀请", say("u_a", "邀请 辛")))
if say("u_g", "同意") != [_r("SYS_PARTY_ACC_FULL", cap="甲", max=PT.max_members())]:
    _B.append(("满员那一档的同意", say("u_g", "同意")))
chk("★ 满员四档真敲：第 4 个人进得来 · 第 5 个人**邀不进** · 第 5 个人**同意也进不来**",
    not _B, "%s" % _B[:2])

_B = []
if say("u_f", "离队") != [_r("SYS_PARTY_LV_MEMBER", cap="甲")]:
    _B.append(("腾位子（队员退）", say("u_f", "离队")))
if say("u_a", "邀请 辛") != [_r("SYS_PARTY_INV_OK", name="辛", ttl=PT.invite_ttl_ticks())]:
    _B.append(("腾出位子后邀请", say("u_a", "邀请 辛")))
FIXED[0] += (PT.invite_ttl_ticks() + 1)                    # 把假钟推过有效期
try:
    _got = say("u_h", "同意")
finally:
    FIXED[0] -= (PT.invite_ttl_ticks() + 1)
if _got != [_r("SYS_PARTY_ACC_EXPIRED", cap="甲")]:
    _B.append(("过期的邀请", _got))
if rec("u_h") is not None:
    _B.append(("过期还落档了", rec("u_h")))
chk("★ 邀请**到点作废**（推过 `invite_ttl_ticks` 再敲『同意』⇒ 明确回话 · 不落档）",
    not _B, "%s" % _B[:2])

_B = []
#   名单现算：档上写着「我在甲这个队里」的人，**按 uid 升序**（= 名册那一条口径），自己不算
_pid_a = str((rec("u_a") or {}).get("id") or "")
_others = [NAMES[u] for u in sorted(NAMES)
           if u != "u_a" and str((rec(u) or {}).get("id")) == _pid_a
           and (rec(u) or {}).get("captain") == "u_a"]
_got = say("u_a", "离队")
if _got != [_r("SYS_PARTY_LV_CAPTAIN", list="、".join(_others))]:
    _B.append(("队长解散", _got, [_r("SYS_PARTY_LV_CAPTAIN", list="、".join(_others))]))
if rec("u_a") is not None:
    _B.append(("队长那一格没清", rec("u_a")))
_EXP2 = [_r("SYS_PARTY_STALE", cap="甲"),
         _r("SYS_PARTY_MAKE", max=PT.max_members()),
         _r("SYS_PARTY_HEAD", n=1, max=PT.max_members(), cap="乙"),
         _r("SYS_PARTY_ROW", name="乙", level=_pv2["level"], hp=_pv2["hp"], hpmax=_pv2["hp_max"],
            where=WHERE_HERE),
         _r("SYS_PARTY_TAIL")]
_got = say("u_b", "队伍")
if _got != _EXP2:
    _B.append(("队员自愈", _got, _EXP2))
chk("★ 队长退 = 解散（名单逐字对现算：%s）· 队员那条路**自愈**（说一句 · 只清自己那一格 · "
    "顺手起个新队）" % "、".join(_others), not _B, "%s" % _B[:2])
_B = []
if say("u_b", "离队") != [_r("SYS_PARTY_LV_SOLO")]:
    _B.append(("散一个只有自己的队", say("u_b", "离队")))
if say("u_b", "离队") != [_r("SYS_PARTY_LV_NONE")]:
    _B.append(("没队时离队", say("u_b", "离队")))
chk("★ `离队` 三档：队员退 / 队长散（队里就自己一个）/ 没队时 —— 各有各的那句话",
    not _B, "%s" % _B[:2])

# ══════════════════════════════════════════════════════════════
# ⑤ 纪律档
# ══════════════════════════════════════════════════════════════
print("⑤ 纪律档：默认档不被就地改 · 名册是现算的 · 存档读不出来时不动档")


def _defsnap():
    return json.dumps({k: CA.DEFAULT_PLAYER.get(k) for k in ("flags", "bag", "equipped", "codex")},
                      ensure_ascii=False, sort_keys=True)


_def0 = _defsnap()
_ad.seed("u_b", "乙", flags={"party": {"id": "pt_u_b_9", "role": "captain", "tick": 9,
                                       "invites": {}}})
_ad.seed("u_c", "丙", flags={"party": {"id": "pt_u_b_999", "role": "member", "captain": "u_b"}})
_M1 = PT.membership(PT.rows_of(G), PS.get_player(G, "u_b") or {}, "u_b")["members"]
_ad.seed("u_c", "丙", flags={"party": {"id": "pt_u_b_9", "role": "member", "captain": "u_b"}})
_M2 = PT.membership(PT.rows_of(G), PS.get_player(G, "u_b") or {}, "u_b")["members"]
chk("★ 名册是**现算**的：pid 对不上的那一格不算队员（%s）· 对上了才算（%s）—— 不串队"
    % (_M1, _M2), _M1 == ["u_b"] and _M2 == ["u_b", "u_c"])
_keep_all = PS.all_players


def _boom(*_a, **_kw):
    raise RuntimeError("库没了（探针故意）")


_off = []
_before_c = json.dumps(rec("u_c"), ensure_ascii=False, sort_keys=True)
try:
    PS.all_players = _boom
    for _u, _t in (("u_a", "队伍"), ("u_a", "邀请 乙"), ("u_a", "同意"), ("u_a", "离队")):
        _off.append((_t, say(_u, _t)))
finally:
    PS.all_players = _keep_all
chk("★ 存档读不出来 ⇒ 四条各回**一句点名的** fail-closed 行（不静默 · 不开队 · 不落档）",
    all(got == [_r("SYS_PARTY_OFF")] for _t, got in _off), "%s" % _off[:2])
chk("★ 那四下里**别人的档一个字没动**",
    _before_c == json.dumps(rec("u_c"), ensure_ascii=False, sort_keys=True))
chk("★ 跑完上面这一大串之后，默认档那四个容器**原样**（一个格子都没被就地改）",
    _def0 == _defsnap())

# ══════════════════════════════════════════════════════════════
# ⑥ 进战人数（`cmds_battle` 那三处 party=… 真传人数）
# ══════════════════════════════════════════════════════════════
print("⑥ 进战人数：`攻击` 打在骨田（遇敌钉死）—— `combat.build(party=…)` 拿到的是什么")
_SEEN = []
_REAL_BUILD, _REAL_PICK = CBT.build, CBT.pick_encounter


def _spy(*a, **kw):
    _SEEN.append(kw.get("party"))
    return _REAL_BUILD(*a, **kw)


def _at(uid, loc, node, hp=None):
    d = dict(CA._p(_ad.players[uid]))
    d["loc"], d["node"] = loc, node
    if hp is not None:
        d["hp"] = hp
    d = CA._p(d)
    _ad.players[uid] = d
    PS.update_player(G, uid, **d)
    return d


def _set_party(uid, val):
    d = dict(_ad.players[uid])
    f = dict(d.get("flags") or {})
    if val is None:
        f.pop("party", None)
    else:
        f["party"] = val
    d["flags"] = f
    d = CA._p(d)
    _ad.players[uid] = d
    PS.update_player(G, uid, **d)


_PID = PT.pid_of("u_a", 777)
_SEC = []
# ★ 合入提示（B3-26 × B3-25）：有队(≥2 站一起)之后 `攻击` 会走「场」（`instance.take_turn`）——
#   场是**跨指令留着**的 ⇒ 每一档之前先清干净，否则上一档开着的场会把这一档吃掉
#   （实测：不 clear ⇒ 后面三档根本不再 build，观测值停在上一档）。
# ★ G2（2026-09-26）：**单人也有自己那一场了**，而且键分两档（有队 ⇒ 按群 `G`；单人 ⇒
#   按人 `G#<uid>`）—— 所以「清干净」得**两档都清**（只清 `G` 会把单人的那一格漏在库里，
#   下一档的 `攻击` 就接着上一场打、根本不 build ⇒ 观测值停住）。
from content import instance as INST


def _clear_field():
    """清掉这一群里的**所有**场（按群的 + 按人的 —— G2 起键分两档）。"""
    INST.clear(G)                                  # 按群那一格（有队时用）
    for _u in sorted(NAMES):
        INST.clear(INST.key_of(G, _u, [_u]))       # 按人那一格（单人时用）


try:
    CBT.build, CBT.pick_encounter = _spy, (lambda *a, **k: [PIN])
    _set_party("u_a", None)                     # 一、单人（没队）⇒ 1（老路：一个数都没变）
    _at("u_a", LOC, NODE, hp=80)
    _clear_field()
    say("u_a", "攻击")
    _SEC.append(("没队", _SEEN[-1], 1))
    _set_party("u_a", {"id": _PID, "role": "captain", "tick": 1, "invites": {}})
    _set_party("u_b", {"id": _PID, "role": "member", "captain": "u_a"})
    _at("u_a", LOC, NODE, hp=80)                # 二、两人同在骨田 ⇒ 2
    _at("u_b", LOC, NODE, hp=70)
    _clear_field()
    say("u_a", "攻击")
    _SEC.append(("同节点两人", _SEEN[-1], 2))
    _at("u_b", LOC, "bn_camp")                  # 三、队友在同一张图的另一个节点 ⇒ 1
    _clear_field()
    say("u_a", "攻击")
    _SEC.append(("队友在别站", _SEEN[-1], 1))
    _at("u_b", LOC, NODE, hp=70)
    _set_party("u_c", {"id": _PID, "role": "member", "captain": "u_a"})
    _at("u_b", LOC, NODE, hp=70)                # 五、三人同节点 ⇒ 3
    _at("u_c", LOC, NODE, hp=50)
    _clear_field()
    say("u_a", "攻击")
    _SEC.append(("同节点三人", _SEEN[-1], 3))
    try:                                        # 六、在队里但读不到存档 ⇒ None（不缩放）
        PS.all_players = _boom
        _clear_field()
        say("u_a", "攻击")
    finally:
        PS.all_players = _keep_all
    _SEC.append(("在队里但读不到存档", _SEEN[-1], None))
finally:
    CBT.build, CBT.pick_encounter = _REAL_BUILD, _REAL_PICK
_BAD = [(w, got, want) for w, got, want in _SEC if got != want]
chk("★ `攻击` 真敲五档：%s"
    % " · ".join("%s=%s" % (w, got) for w, got, _x in _SEC), not _BAD, "%s" % _BAD)
#   ★ 「活人」这一条**直调**钉住（命令那一路造不出来：出档口 `cmds_ast._p` 把血钳到 ≥1，
#     档上不可能躺着 hp≤0 的人 —— 所以这一档只在读别人的档时才有意义，判据走直调）。
_SYN = [{"uid": "u_a", "data": {"name": "甲", "cls": "cls_knight", "level": 5, "hp": 60,
                                 "loc": LOC, "node": NODE,
                                 "flags": {"party": {"id": _PID, "role": "captain",
                                                     "tick": 1, "invites": {}}}}},
        {"uid": "u_b", "data": {"name": "乙", "cls": "cls_knight", "level": 5, "hp": 0,
                                "loc": LOC, "node": NODE,
                                "flags": {"party": {"id": _PID, "role": "member",
                                                    "captain": "u_a"}}}}]
_SYN_P = dict(_SYN[0]["data"])
_SYN2 = [_SYN[0], {"uid": "u_b", "data": dict(_SYN[1]["data"], hp=70)}]
chk("★ 站在一起但**血空**的队友不算人数（直调：%s → 人数 %s；他血满了就是 %s）"
    % (PT.members_present(_SYN, _SYN_P, "u_a"), PT.present_count(_SYN_P, "u_a", _SYN),
       PT.present_count(_SYN_P, "u_a", _SYN2)),
    PT.present_count(_SYN_P, "u_a", _SYN) == 1
    and PT.present_count(_SYN_P, "u_a", _SYN2) == 2,
    "%s | %s | 甲 %s %s | 乙 %s %s" % (
        PT.membership(_SYN, _SYN_P, "u_a")["members"],
        [(r["uid"], r["data"].get("hp"), r["data"].get("loc"), r["data"].get("node"))
         for r in _SYN2],
        _SYN_P.get("hp"), (_SYN_P.get("loc"), _SYN_P.get("node")),
        _SYN[1]["data"].get("hp"), (_SYN[1]["data"].get("loc"), _SYN[1]["data"].get("node"))))
# ★ 审计 L892-#1（高）坏档那条的判据夹具：一个**写坏了 role** 的队友。
#   旧码下他静默从名册消失（3 -> 2 人 ⇒ Boss 悄悄变弱），本轮起必须被看见。
_BRKP = dict(_SYN[1]["data"])
_BRKP["flags"] = {"party": {"id": _PID, "role": "captain_typo", "captain": "u_a"}}
_SYN3 = [_SYN[0], _SYN[1], {"uid": "u_c", "data": _BRKP}]
_SYN3_OK = [_SYN[0], _SYN[1],
            {"uid": "u_c", "data": dict(_SYN[2 - 1]["data"], uid="u_c", hp=70)}]
_BRK = PT.membership(_SYN3, _SYN_P, "u_a")
_BRK_CNT = PT.present_count(_SYN_P, "u_a", _SYN3)
_OK = PT.membership(_SYN3_OK, _SYN_P, "u_a")
_OK_CNT = PT.present_count(_SYN_P, "u_a", _SYN3_OK)
chk("★ 队友档**坏**了（role 写坏）不静默少人：`present_count` 回 `None` = 不知道几个人 ⇒ 不缩放"
    "（旧码回 2 ⇒ Boss 血 7412 悄悄变 4447）· broken 带上原话点名（%s）"
    % ([b.get("why") for b in _BRK.get("broken") or []][:1]),
    _BRK_CNT is None
    and bool(_BRK.get("broken"))
    and "u_c" not in (_BRK.get("members") or [])
    and "role" in str((_BRK.get("broken") or [{}])[0].get("why", "")),
    "人数 %s · 名册 %s · broken %s" % (_BRK_CNT, _BRK.get("members"), _BRK.get("broken")))
chk("★ 同一支里**没坏**的人照旧算进去（好数据零行为变化：名册 %s 人 / 在场 %s 人；"
    "u_b 那份血是 0（上一档刚钉过「血空不算人数」⇒ 活人 %s））"
    % (len(_OK.get("members") or []), _OK_CNT, _OK_CNT),
    _OK_CNT == 2 and _OK.get("members") == ["u_a", "u_b", "u_c"] and not _OK.get("broken"),
    "人数 %s · 名册 %s" % (_OK_CNT, _OK.get("members")))

chk("★ 单人那档与 B3-17 之前**逐字相同**（party=1 ⇒ 那只 Boss 的面板照旧 ÷2：%s）"
    % int(CBT.monster_actor(_BOSS, MON[_BOSS], party=1).get("max_hp")),
    _SEC[0][1] == 1
    and int(CBT.monster_actor(_BOSS, MON[_BOSS], party=1).get("max_hp"))
    == int(round(float(_BH["hp"]) * float(RB.PARTY_SCALE["1"]["hp"]))))

# ══════════════════════════════════════════════════════════════
def _field(uid):
    """这个人在这一群里的「场」（★ G2 键分两档：单人按人 / 有队按群）—— 没有 ⇒ None。"""
    return INST.load(INST.key_of(G, uid, [uid])) or INST.load(G)


# ══════════════════════════════════════════════════════════════
print("⑦ ★ B4-18：集火按此刻真在不在队里分档 · 逃跑那句桩句收进槽位")
_B7 = []
# ── 一、单人（没队）：**没在打** ⇒ 两句照旧（认得出 / 认不出），且**过时那半句**一个字都没有
_set_party("u_a", None)
_set_party("u_b", None)
_at("u_a", LOC, NODE, hp=80)
_clear_field()                                    # ★ G2：单人也有场 ⇒ 先清干净（这一档要的是「没在打」）
_o1 = say("u_a", "集火")
_o2 = say("u_a", "集火 田鼠")
if _o1 != [_r("COMBAT_FOCUS_SOLO")]:
    _B7.append(("单人 集火", _o1, _r("COMBAT_FOCUS_SOLO")))
if _o2 != [_r("COMBAT_FOCUS_NAMED", name="田鼠")]:
    _B7.append(("单人 集火 田鼠", _o2, _r("COMBAT_FOCUS_NAMED", name="田鼠")))
# ── 一之二（★ G2 新增的那一档）：**真打起来的时候**『集火 <目标>』真锁上（不吃行动）
_real_pick7 = CBT.pick_encounter
CBT.pick_encounter = lambda *a, **k: [PIN]
try:
    random.seed(20260926)
    say("u_a", "攻击")                             # 这一敲就开一场
    _f0 = _field("u_a")
    _h0 = int((_f0 or {}).get("hands") or 0)
    _o2b = say("u_a", "集火 田鼠")
    _f1 = _field("u_a")
    if _o2b[:1] != [_r("COMBAT_FOCUS_LOCK", name="田鼠")]:
        _B7.append(("战斗中 集火 <名>", _o2b[:2], _r("COMBAT_FOCUS_LOCK", name="田鼠")))
    if str((_f1 or {}).get("focus") or "") != PIN:
        _B7.append(("战斗中 集火 没写进这一场", (_f1 or {}).get("focus")))
    if int((_f1 or {}).get("hands") or 0) != _h0:
        _B7.append(("集火 竟然吃了行动", (int((_f1 or {}).get("hands") or 0), _h0)))
finally:
    CBT.pick_encounter = _real_pick7
    _clear_field()
chk("★ 单人档：没在打 ⇒ 『集火』= `COMBAT_FOCUS_SOLO`（%s）· 『集火 田鼠』= `COMBAT_FOCUS_NAMED`（%s）；"
    "★ G2：**真打起来的时候**同一条 = `COMBAT_FOCUS_LOCK`（锁写进这一场 · **不吃行动**）"
    % (_o1[0] if _o1 else "", _o2[0] if _o2 else ""), not _B7, "%s" % _B7[:2])

# ── 二、有队（两人站一起）⇒ 单人那两句都不许再说，走「有队」那一句
#      （★ 场是跨指令留着的 ⇒ 与 §⑥ 同一条纪律：先 clear 再敲）
_B7 = []
_set_party("u_a", {"id": _PID, "role": "captain", "tick": 1, "invites": {}})
_set_party("u_b", {"id": _PID, "role": "member", "captain": "u_a"})
_at("u_a", LOC, NODE, hp=80)
_at("u_b", LOC, NODE, hp=70)
_clear_field()
_o3 = say("u_a", "集火 田鼠")
_o4 = say("u_a", "集火")
if _o3 != [_r("COMBAT_FOCUS_PARTY")]:
    _B7.append(("有队 集火 田鼠", _o3, _r("COMBAT_FOCUS_PARTY")))
if _o4 != [_r("COMBAT_FOCUS_PARTY")]:
    _B7.append(("有队 集火", _o4, _r("COMBAT_FOCUS_PARTY")))
# ── 三、在队里但存档读不出来（不知道几个人）⇒ 同「有队」那一句（fail-closed）
try:
    PS.all_players = _boom
    _o5 = say("u_a", "集火")
finally:
    PS.all_players = _keep_all
if _o5 != [_r("COMBAT_FOCUS_PARTY")]:
    _B7.append(("队读不出来 集火", _o5, _r("COMBAT_FOCUS_PARTY")))
chk("★ 有队档：『集火 <名>』『集火』都回**有队那一句**（%s / %s）；队在、存档读不出来也回同一句"
    "（%s）—— 不拿单人那两句去说一支读不出来的队" % (_o3[0] if _o3 else "", _o4[0] if _o4 else "",
                                                    _o5[0] if _o5 else ""),
    not _B7, "%s" % _B7[:2])

# ── 四、★ 本波：**多人场里 `逃跑` 真掷**（原先有队时回的是那句已退役的桩句）
#     ★ 这一条要用的镜子（`_roll7` / `_RATE7` / `_FLY7` / `_STOP7`）在 §六 里（P-57 那一节）
#       ⇒ 本块**包成一个函数、在 §六 之后调用**（`_multi_flee_criterion()`）。
#     口径：与单人**同一条规则**（真源 `05_玩法数值口径_v1 §四` 只有一条「逃跑」规则，
#       没把单人 / 多人分家）—— 谁敲谁掷（种子 = 他自己 + 那一只 + 这一处 + 游戏日）。
#       ★ 多人那一层的**语义**（跑成之后全队算不算「这一场没打」）真源没写 ⇒ 本波照
#       「跑成 = 这一场没打」落地并登记（见 `_notes.md §真源行`）。
#     判据三头（都真敲 · 遇敌钉死 ⇒ 可复现）：
#       ① 队里那一掷：回的是 OK / BLOCK 里**与探针现算那颗种子相符**的那句（不是桩句）
#       ② 两态都在多人场里跑到：临时把率改成 1.0 / 0.0 ⇒ 被拦下（这一场还在、真花一手）/
#          跑成（这一场清干净 + 记 fled）—— 顺带再证一次「率只有一个口」
#       ③ 那一场真是**多人那一格**（按群存、members 两个人）—— 不是退回单人那一格


def _warm_party7(fleer, other):
    """★ 本波（任务①）：**先把这一场真开起来、并推到「轮到 fleer」**。

    为什么：新口径下 `逃跑` **不在场就不开场**（旧口径它自己开那一下）—— 多人那一掷那一档
    得先把场摆好。做法：拿 `防御` 喂当前拿窗口的那位（**不出伤 ⇒ 对面满血**、也不会把这一场打完），
    一直到 `next_actor_key(st) == fleer`；最多 8 手（打不到就回 None，调用方当场报红）。
    返回「喂完之后的那一格场」（None = 没推开）。
    """
    if _field(fleer) is None:
        say(other, "防御")                       # 开那一场（多人在场的开场；轮不轮到他不重要）
    for _i in range(8):
        _st = _field(fleer)
        if _st is None:
            return None
        _cur = INST.next_actor_key(_st)
        if _cur == fleer:
            return _st
        say(_cur, "防御")
    return None


def _drive_party7(fleer, other):
    """（多人场）两人真组一队、同在骨田 ⇒ 让 `fleer` 在**已经在打**的那一场里敲一次 `逃跑`。

    返回 `(屏上那几行, 这一场, last_battle, 逃跑之前这一场花过几手)`。先把两个档都摆干净：
    队格 / 场 / 上一场的账。
    """
    for _u in (fleer, other):
        _set_party(_u, None)
    _set_party(fleer, {"id": _PID, "role": "captain", "tick": 1, "invites": {}})
    _set_party(other, {"id": _PID, "role": "member", "captain": fleer})
    for _u in (fleer, other):
        _at(_u, LOC, NODE, hp=80)
        _d = dict(CA._p(_ad.players[_u]))
        _f = dict(_d.get("flags") or {})
        _f.pop("last_battle", None)
        _d["flags"] = _f
        _ad.players[_u] = _d
        PS.update_player(G, _u, **_d)
    _clear_field()
    _st0 = _warm_party7(fleer, other)
    _h0 = int((_st0 or {}).get("hands") or 0)
    _o = say(fleer, "逃跑")
    _lb = ((PS.get_player(G, fleer) or {}).get("flags") or {}).get("last_battle") or {}
    return _o, _field(fleer), _lb, _h0


def _multi_flee_criterion():
    """★ 本波：多人场那一掷（真敲 · 两态都跑到）—— 见上面那段抬头。"""
    _bad = []
    _todo_old = str((TX.get("COMBAT_FLEE_TODO") or {}).get("value") or "")
    _pair = (_FLY7[0] if _FLY7 else "", _STOP7[0] if _STOP7 else "")
    _fast = ""
    if not (_pair[0] and _pair[1] and _pair[0] != _pair[1]):
        chk("★ 多人场 `逃跑` 真接了（前提：同一颗种子下「跑成 / 被拦下」两个人都凑得齐）",
            False, "两态凑不齐：%s" % (_pair,))
        return
    try:
        CBT.build, CBT.pick_encounter = _spy, (lambda *a, **k: [_MID7])
        # 谁先手：拿引擎自己排的 ct 序当期望（不手写 —— 与 `content/instance` 同一把尺）
        _bb = _REAL_BUILD({}, [_MID7], MON, party=2,
                          players=[dict(PS.get_player(G, u), uid=u) for u in _pair])
        _cts = {a["uid"]: float(a.get("ct") or 0) for a in _bb.sides["player"]}
        _fast = min(_cts, key=_cts.get)
        _slow = [u for u in _pair if u != _fast][0]
        # ① 先手那位真掷（哪一边由探针现算的种子说）—— ★ 本波：那一场先由「防御」摆好（见 `_warm_party7`）
        _exp = _r("COMBAT_FLEE_OK", name=_NAME7) if _roll7(_fast) >= _RATE7 \
            else _r("COMBAT_FLEE_BLOCK", name=_NAME7)
        random.seed(20260926)
        _o1, _st1, _lb1, _h1 = _drive_party7(_fast, _slow)
        if not _hit(_exp, _o1):
            _bad.append(("多人场那一掷与现算的种子不符（那一场已先摆好）", _fast, _o1[:4], _exp))
        if _st1 is not None and sorted(_st1.get("members") or []) != sorted(_pair):
            _bad.append(("那一场不是多人那一格", _st1.get("members")))
        if _todo_old and any(_todo_old.split("\n")[0] in _x for _x in _o1):
            _bad.append(("多人场还在回那句已退役的桩句", _o1[:2]))
        # ② 两态都真跑到（改率那一格 —— 与 §六 的反证同一个手法）
        _keep = _BA7.flee_fail_pct
        try:
            _BA7.flee_fail_pct = (lambda: 1.0)
            random.seed(20260926)
            _ob, _stb, _lbb, _hb = _drive_party7(_fast, _slow)
            _BA7.flee_fail_pct = (lambda: 0.0)
            random.seed(20260926)
            _oc, _stc, _lbc, _hc = _drive_party7(_fast, _slow)
        finally:
            _BA7.flee_fail_pct = _keep
        if not (_hit(_r("COMBAT_FLEE_BLOCK", name=_NAME7), _ob) and _stb is not None
                and int(_stb.get("hands") or 0) == _hb + 1):
            _bad.append(("多人场被拦下那一档不对（这一场应当还在、且这一手真花了）",
                         _ob[:3], None if _stb is None else (_hb, _stb.get("hands"))))
        if not (_hit(_r("COMBAT_FLEE_OK", name=_NAME7), _oc) and _stc is None
                and _lbc.get("result") == "fled"):
            _bad.append(("多人场跑成那一档不对（这一场应当清干净、记 fled）",
                         _oc[:3], _lbc.get("result")))
    finally:
        CBT.build, CBT.pick_encounter = _REAL_BUILD, _REAL_PICK
    chk("★ 多人场 `逃跑` 真接了（两人同格 · **那场先由防御摆好** · 先手那位 %s 真掷 ⇒「%s」；"
        "改率 1.0 ⇒ 被拦下且这一场照打（这一手真花）· 改率 0.0 ⇒ 跑成且这一场清干净记 "
        "`fled`）· 不再回那句退役桩句"
        % (_fast or "（没跑）", _exp if _fast else ""),
        not _bad, "%s" % _bad[:2])

# ── 五、覆盖面（源码守卫）：`flee` 里一句内联文案都没有（K61：覆盖面跟判据一起加）
_CBSRC = io.open(os.path.join(str(REPO), "content", "cmds_battle.py"), encoding="utf-8").read()
# ★ 口径走 ast（K46）：注释 / docstring 里提到什么都不算 —— 要钉的是「`flee` 这个实现体里
#   **没有一个含汉字的字符串字面量**」（与 `probe_copy` 的 SEALED 口径同一把尺子）。
#   ★ P-57 起口径**换锚不换强度**：老那条要求「一个字符串字面量都没有」，可它把机器口令也
#   算成文案了（`"retreat"` / `"fled"` 是**接线**不是给玩家看的字）⇒ 收口的那条线改成
#   「含汉字的字面量一个都没有」+「三个槽位都真由它 yield 出来」（两句都真判）。
import ast as _ast                                                     # noqa: E402
_TREE7 = _ast.parse(_CBSRC)
#   ★ 本波（2026-09-27 · 任务①）：`flee` 的**冷启动那一档**不再掷骰 ⇒ 掷骰那两位（`跑成` /
#     `被拦下` 的落点）挪到 `_flee_decide` 那一格里。这条静态守卫因此**换锚不换强度**：
#     认的是「这一族两个实现体（`flee` + `_flee_decide`）**合起来**把两条槽位都取到了、
#     且**一个含汉字的字面量都没有**、且**一个数都没写死**」—— 比只扫 `flee` 那一个更严
#     （多扫了一个函数）。
_FN_BY_NAME7 = {n.name: n for n in _TREE7.body
                if isinstance(n, (_ast.AsyncFunctionDef, _ast.FunctionDef))}
_FN = [_FN_BY_NAME7["flee"]] if "flee" in _FN_BY_NAME7 else []
_FD = [_FN_BY_NAME7["_flee_decide"]] if "_flee_decide" in _FN_BY_NAME7 else []
_FAM7 = _FN + _FD


def _doc_of7(f):
    """这个函数的 docstring 字面量节点（没有 ⇒ None）—— 排掉它，不算「字面量」。"""
    if f.body and isinstance(f.body[0], _ast.Expr) \
            and isinstance(f.body[0].value, _ast.Constant) \
            and isinstance(f.body[0].value.value, str):
        return f.body[0].value
    return None


_DOCNODES7 = {id(_doc_of7(f)) for f in _FAM7 if _doc_of7(f) is not None}
_CJK = re.compile(r"[\u4e00-\u9fff]")
_FN_LITS = [n.value for f in _FAM7 for n in _ast.walk(f)
            if isinstance(n, _ast.Constant) and isinstance(n.value, str)
            and id(n) not in _DOCNODES7 and _CJK.search(n.value)]
_SLOTS7 = ("COMBAT_FLEE_OK", "COMBAT_FLEE_BLOCK")
#   ★ 那两条槽位**在这一族的实现体里真被取**（ast 认 `T("<键>")` 这种调用 ——
#     `COMBAT_FLEE_BLOCK` 是挂在 `hand.lines` 上由引擎取走的 / 由 `_flee_decide` 写进日志的，
#     不是 `flee` 自己 `yield` 出来的，所以认「调用」而不是认「yield 那一行」）。
_T_CALLS7 = sorted({n.args[0].value for f in _FAM7 for n in _ast.walk(f)
                    if isinstance(n, _ast.Call) and isinstance(n.func, _ast.Name)
                    and n.func.id == "T" and n.args
                    and isinstance(n.args[0], _ast.Constant)
                    and isinstance(n.args[0].value, str)})
_HAS7 = sorted(set(_SLOTS7) & set(_T_CALLS7))
#   ★ 那一族里**除 0 / 1 没有别的数**：失败率 / 阈值一个都不许写进代码（唯一来源 = 声明表）。
_NUMS7 = sorted({n.value for f in _FAM7 for n in _ast.walk(f)
                 if isinstance(n, _ast.Constant) and not isinstance(n.value, bool)
                 and isinstance(n.value, (int, float))}) if _FAM7 else []
chk("★ 覆盖（ast）：`flee` + `_flee_decide` 这一族里**没有一个含汉字的字面量**"
    "（%d 处 —— 注释 / docstring / 槽位键不算）· 那两条槽位都由这一族 `T(\"…\")` 取到（%s）· "
    "这一族里出现的数只有 %s（率不在代码里）"
    % (len(_FN_LITS), " · ".join(_HAS7) or "一个都没取", _NUMS7),
    len(_FN) == 1 and len(_FD) == 1 and not _FN_LITS and _HAS7 == sorted(_SLOTS7)
    and set(_NUMS7) <= {0, 1})
chk("★ 覆盖：这一族的三条槽位都在 texts 里、且占位与 params **双向对账**（%s）"
    % " · ".join("%s=%s" % (k, sorted((TX.get(k) or {}).get("params") or []))
                 for k in ("COMBAT_FOCUS_PARTY",) + _SLOTS7),
    all((TX.get(k) or {}).get("value") for k in ("COMBAT_FOCUS_PARTY",) + _SLOTS7)
    and all(set(re.findall(r"\{(\w+)\}", (TX.get(k) or {}).get("value", "")))
            == set((TX.get(k) or {}).get("params") or [])
            for k in ("COMBAT_FOCUS_PARTY",) + _SLOTS7))

# ══════════════════════════════════════════════════════════════
# 六、★ P-57：野外 / 单人那一路 —— 掷一次定成败（同种子两态都碰得到 · 率只有一个口）
#      真源：`04_指令总表 §五`（`逃跑 … 可能失败`）+ P-57 裁决（**三成被拦下**）。
#      判据（都真敲 · 遇敌钉死 ⇒ 可复现）：
#        ① 率只有一个口：声明表 `flee_fail_pct` ↔ `battle_acts.flee_fail_pct()`（代码不写数）
#        ② ★ 同种子两态都碰得到：探针**按实现那条式子自己算**手气 ⇒ 挑一个跑成的、一个被拦下的
#           （不许只断言代码里有 0.3 这个字面量）
#        ③ 跑成 ⇒ 那一句 + `last_battle.result == "fled"` + **没有结算那一段**（这一场没打）
#           被拦下 ⇒ 那一句 + `result != "fled"` + **有结算那一段**（这一场照打）
#        ④ 同种子再来一遍 ⇒ 同结果
#        ⑤ ★ 反证（率真被读）：临时改成 1.0 ⇒ 那个跑成的当场被拦下；改成 0.0 ⇒ 那个被拦下的
#           当场跑成 —— 同一个种子、同一个人，证明判的是声明表那个数
# ══════════════════════════════════════════════════════════════
from content import battle_acts as _BA7                                # noqa: E402
from content import calendar as _CAL7                                  # noqa: E402
_RATE7 = _BA7.flee_fail_pct()
_RULES7 = json.load(io.open(str(REPO / "content" / "rules" / "battle_cmds.json"), encoding="utf-8"))
chk("★ P-57 失败率只有一个口：声明表 `flee_fail_pct` = %r ↔ `battle_acts.flee_fail_pct()` 读到的 %r"
    % (_RULES7.get("flee_fail_pct"), _RATE7),
    _RULES7.get("flee_fail_pct") == _RATE7 and 0.0 < float(_RATE7) < 1.0)
_DAY7 = int(_CAL7.state().get("game_day") or 0)
_MID7 = PIN
_NAME7 = str((MON.get(_MID7) or {}).get("name") or _MID7)


def _roll7(uid):
    """★ 照实现那条式子**自己算一遍**手气（种子 = uid + 那一只 + 这一处 + 游戏日）。

    与 `content/cmds_battle._flee_roll` 各写各的：改种子 / 改率 ⇒ 这一节当场红。
    """
    return random.Random("%s:flee:%s:%s:%s:%d" % (uid, _MID7, LOC, NODE, _DAY7)).random()


_FLY7 = [u for u in sorted(NAMES) if _roll7(u) >= _RATE7]
_STOP7 = [u for u in sorted(NAMES) if _roll7(u) < _RATE7]
#   ★ 只拿**定过职业**的人当试样：没择业的档在 `hp_cap_or_line` 那一关就回了点名行，
#     根本走不到逃跑这一手（`u_e` 就是这一档 —— 与 §⑤ 那条纪律同源）。
_FLY7 = [u for u in _FLY7 if (_SEED[u].get("cls"))]
_STOP7 = [u for u in _STOP7 if (_SEED[u].get("cls"))]
chk("★ P-57 **同种子两态都碰得到**（第 %d 游戏日 · 率 %s · 手气探针自己算：%s）—— 跑成 %s · 被拦下 %s"
    % (_DAY7, _RATE7, " · ".join("%s=%.3f" % (u, _roll7(u)) for u in sorted(NAMES)),
       sorted(_FLY7), sorted(_STOP7)),
    bool(_FLY7) and bool(_STOP7))


def _drive7(uid, warm=False):
    """单人（没队）+ 遇敌钉死，真敲一次 `逃跑` ⇒ (屏上那几行, 这一场的状态, `last_battle`)。

    ★ G2 起这一手走「场」：清干净（群/人两格都清）· 顺手把上一场的 `flags.last_battle` 也抹掉
      （那是**结算期**才写的账，不清就会把「上一场的结局」当成「这一拍的结果」）。
    ★ 本波（2026-09-27 · 任务①）：`warm=True` ⇒ **先用 `防御` 真开一场**（防御不出伤 ⇒ 对面满血），
      再敲 `逃跑` —— 掷骰那一档（真源「三成被拦下」）只在「**已经在打**」时谈得上。
      `warm=False`（默认）= **冷启动**那一档：这一敲是「这一带站着怪、但这一场还没开打」——
      新口径 = **不建场、不掷骰、0 风险走人**（旧口径会先开一场再掷骰 ⇒ 掷败就把人拉进去）。
      返回的 `_o` 仍然是**逃跑那一敲**的屏（`防御` 那几行不混进来）。
    """
    _set_party(uid, None)
    _at(uid, LOC, NODE, hp=80)
    _d = dict(CA._p(_ad.players[uid]))
    _f = dict(_d.get("flags") or {})
    _f.pop("last_battle", None)
    _d["flags"] = _f
    _ad.players[uid] = _d
    PS.update_player(G, uid, **_d)
    _clear_field()
    _b0 = (int(_d.get("gold") or 0), int(_d.get("exp") or 0), sorted(_d.get("bag") or {}))
    _hp0 = int(_d.get("hp") or 0)
    if warm:
        say(uid, "防御")                         # ★ 真开一场（这一手不出伤 ⇒ 怪还满血）
    _o = say(uid, "逃跑")
    _st = _field(uid)
    _lb = ((PS.get_player(G, uid) or {}).get("flags") or {}).get("last_battle") or {}
    _d2 = PS.get_player(G, uid) or {}
    _a0 = (int(_d2.get("gold") or 0), int(_d2.get("exp") or 0), sorted(_d2.get("bag") or {}))
    return _o, _st, _lb, _b0, (_hp0, int(_d2.get("hp") or 0), _a0)


#: ★ P0-1 续（aep0）：`_r()` 对含 `{t}` 的槽位给出的是**带通配**的行首锚
#:   （`图标【*刻】` —— 刻数是战斗绝对时刻，只有读端知道）。
#:   ⇒ 断言点一律走 `_hit()`：无通配走 `in`（逐字，最紧），有通配走正则（只对那一段）。
#:   ★ 判据强度不降：通配**只覆盖刻数那一格**，句子本体、图标、行尾全部逐字对。
def _hit(exp, out):
    if "*" in exp:
        rx = re.compile("^" + ".*".join(re.escape(p) for p in exp.split("*")) + "$")
        return any(rx.match(x.strip()) for x in out)
    return exp in out


def _sig7(out, st, lb, exp):
    """这一拍的「结果签名」= 走的是哪一边 + 这一场还在不在 + `last_battle` 记成什么。

    ★ 不拿整屏比：同一拍里**背包 / 图鉴的账会变**（第二回来那一件已经不是新东西了，
      「拾取」那一行就不一样）—— 那条与「掷出来是哪一边」无关，别让判据被它带红。
    ★ G2 换锚不换强度：老那版拿「有没有 `━` 结算抬头」当「这一场打没打」的代理；
      分段之后**跑成也走结算那一段**（要写 `last_battle` 那一格）⇒ 代理换成**这一场还在不在**
      （`fled` ⇒ 场清干净）；「没打」的**实质**（没有掉落 / 没有经验）另有一条逐数判据。
    """
    return (_hit(exp, out), st is not None, lb.get("result"))


try:
    CBT.build, CBT.pick_encounter = _spy, (lambda *a, **k: [_MID7])
    if not (_FLY7 and _STOP7):
        print("      （两态凑不齐 —— 上面那条已报红，本节不真敲）")
    else:
        for _u in sorted(NAMES):                 # 先全清干净：别让 §二 建的那支队影响人数
            _set_party(_u, None)
        _u_ok, _u_no = _FLY7[0], _STOP7[0]
        # ★ P0-1 续（aep0）：冷启动（没在打）走 `COMBAT_FLEE_COLD`（**无场、无刻**，
        #   只当回话）；场里那一手走 `COMBAT_FLEE_OK`（带【N 刻】、进战斗日志）。
        #   `_r` 对含 {t} 的槽位只对行首锚（见上面 `_STAMP_PRE` 的说明）。
        # ★ P0-1 续（aep0）：两个读端两个语义，各归各位 ——
        #   · 冷启动（`INST.live(...) is None`，**根本没有场**、`_note_battle` 收到 `[]`）
        #     ⇒ `COMBAT_FLEE_COLD`，只当回话、不带刻（那一格是战斗绝对时刻，没有战斗可读）。
        #   · 场里那一手（掷骰）⇒ `COMBAT_FLEE_OK` / `COMBAT_FLEE_BLOCK`，
        #     带【N 刻】且真进战斗日志（`_r` 对含 {t} 的槽位只对**行首锚**）。
        _EXP_COLD = _r("COMBAT_FLEE_COLD", name=_NAME7)
        _EXP_OK = _r("COMBAT_FLEE_OK", name=_NAME7)
        _EXP_NO = _r("COMBAT_FLEE_BLOCK", name=_NAME7)
        # ── ① ★ 本波（任务①）：**不在场（这一场还没开打）⇒ 不建场、不掷骰、0 风险**
        #    拿**手气最差**那个号（`_u_no`：冷启动若还掷必被拦下）来验「一个骰子都没掷」。
        _B7 = []
        for _u, _tag in ((_u_no, "手气最差那个"), (_u_ok, "跑成那档那个")):
            random.seed(20260926)
            _o_c, _st_c, _lb_c, _b_c, (_hp0_c, _hp1_c, _a_c) = _drive7(_u)
            if not _hit(_EXP_COLD, _o_c):
                _B7.append(("冷启动（%s）没有「这一场没打」那一句" % _tag, _o_c[:3]))
            if _hit(_EXP_NO, _o_c):
                _B7.append(("冷启动（%s）竟然出了「被拦下」那一句（= 还在掷骰）" % _tag, _o_c[:3]))
            if _st_c is not None:
                _B7.append(("冷启动（%s）竟然建了场" % _tag, list((_st_c or {}).keys())))
            if _lb_c.get("result") != "fled":
                _B7.append(("冷启动（%s）没记 fled" % _tag, _lb_c.get("result")))
            if _hp0_c != _hp1_c or _a_c != _b_c:
                _B7.append(("冷启动（%s）动了档上的血/账" % _tag, (_hp0_c, _hp1_c, _b_c, _a_c)))
        chk("★ 任务① 不在场敲 `逃跑`（两个号都验，含手气最差那个 %s）：**不建场**（场 = None）· "
            "出的是「…甩在了后头 —— 这一场没打」· 档上血与账逐格不动 · `last_battle` 记 fled "
            "—— 冷启动**一个骰子都不掷**（那一档不存在「被拦下」）"
            % _u_no, not _B7, "%s" % _B7[:2])
        # ── ② 「已经在打」（先 `防御` 真开一场）⇒ 掷骰两态照旧（真源那条「三成被拦下」）
        random.seed(20260926)                    # 两遍走**同一颗引擎种子** ⇒ 逐字可比
        _o_ok, _st_ok, _lb_ok, _b_ok, _x_ok = _drive7(_u_ok, warm=True)
        random.seed(20260926)
        _o_ok2, _st_ok2, _lb_ok2, _b_ok2, _x_ok2 = _drive7(_u_ok, warm=True)
        random.seed(20260926)
        _o_no, _st_no, _lb_no, _b_no, _x_no = _drive7(_u_no, warm=True)
        random.seed(20260926)
        _o_no2, _st_no2, _lb_no2, _b_no2, _x_no2 = _drive7(_u_no, warm=True)
        _B7b = []
        if not _hit(_EXP_OK, _o_ok):
            _B7b.append(("跑成那一档没有那一句", _o_ok[:3]))
        if _lb_ok.get("result") != "fled":
            _B7b.append(("跑成却没记 fled", _lb_ok.get("result")))
        if _st_ok is not None:
            _B7b.append(("跑成竟然还留着这一场", list((_st_ok or {}).keys())))
        if not _hit(_EXP_NO, _o_no):
            _B7b.append(("被拦下那一档没有那一句", _o_no[:4]))
        if _hit(_EXP_OK, _o_no):
            _B7b.append(("被拦下却出了「跑成」那一句", _o_no[:4]))
        if _lb_no.get("result") == "fled":
            _B7b.append(("被拦下却记成 fled", _lb_no.get("result")))
        if _st_no is None or int(_st_no.get("hands") or 0) != 2:
            _B7b.append(("被拦下没照打（这一场应当还在、且真花了这一手：防御 1 + 逃跑 1 = 2）",
                         None if _st_no is None else _st_no.get("hands")))
        if not (_sig7(_o_ok2, _st_ok2, _lb_ok2, _EXP_OK) == _sig7(_o_ok, _st_ok, _lb_ok, _EXP_OK)
                and _sig7(_o_no2, _st_no2, _lb_no2, _EXP_NO) == _sig7(_o_no, _st_no, _lb_no, _EXP_NO)):
            _B7b.append(("同种子再来一遍不是同一边",
                         (_sig7(_o_ok2, _st_ok2, _lb_ok2, _EXP_OK),
                          _sig7(_o_no2, _st_no2, _lb_no2, _EXP_NO))))
        chk("★ P-57 同种子真敲两态（**已经在打**那一档 · 先 `防御` 开一场）：%s ⇒「%s」"
            "（last_battle=%s · 这一场清干净）· %s ⇒「%s」（last_battle=%s · 这一场照打、花了一手）· "
            "各自再来一遍**还是那一边**"
            % (_u_ok, _EXP_OK, _lb_ok.get("result"), _u_no, _EXP_NO, _lb_no.get("result")),
            not _B7b, "%s" % _B7b[:2])
        # ★ G2 另加一条**实质**判据：「跑成 = 这一场没打」= 没有掉落 / 没有经验 / 没有铜板
        _d_ok = PS.get_player(G, _u_ok) or {}
        _a_ok = (int(_d_ok.get("gold") or 0), int(_d_ok.get("exp") or 0),
                 sorted(_d_ok.get("bag") or {}))
        chk("★ P-57 跑成的**实质**：这一场没打 ⇒ 铜板 / 经验 / 背包与这一拍之前**逐格相同**"
            "（%s → %s）" % (_b_ok, _a_ok), _a_ok == _b_ok)
        # ⑤ 反证：那个数真被读（同一个种子、同一个人，只改声明表那个数）—— 仍然在「已经在打」那一档上验
        _keep_rate7 = _BA7.flee_fail_pct
        try:
            _BA7.flee_fail_pct = (lambda: 1.0)
            _o_r1, _st_r1, _lb_r1, _b_r1, _x_r1 = _drive7(_u_ok, warm=True)
            _BA7.flee_fail_pct = (lambda: 0.0)
            _o_r2, _st_r2, _lb_r2, _b_r2, _x_r2 = _drive7(_u_no, warm=True)
        finally:
            _BA7.flee_fail_pct = _keep_rate7
        chk("★ P-57 反证（率只有一个口、真被读 · **场里**那一档）：临时改成 1.0 ⇒ 原来跑成的 %s "
            "当场被拦下（%s）· 改成 0.0 ⇒ 原来被拦下的 %s 当场跑成（%s）"
            % (_u_ok, (_hit(_EXP_NO, _o_r1) and _st_r1 is not None),
               _u_no, (_hit(_EXP_OK, _o_r2) and _st_r2 is None and _lb_r2.get("result") == "fled")),
            _hit(_EXP_NO, _o_r1) and _st_r1 is not None
            and _hit(_EXP_OK, _o_r2) and _st_r2 is None and _lb_r2.get("result") == "fled")
finally:
    CBT.build, CBT.pick_encounter = _REAL_BUILD, _REAL_PICK

# ★ 本波（多人场那一掷）—— §⑦ 段四 那一条要用的镜子在上一节里 ⇒ 到这里才调用。
_multi_flee_criterion()

print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
