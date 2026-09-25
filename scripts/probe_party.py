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
           「逃跑」那句内联桩句收进 `COMBAT_FLEE_TODO`（照实说 + 指向真能用的『后撤』）·
           两条都真敲、都不动档；再一条源码守卫：那句桩句不许回来

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_party.py
Python 用 3.12（3.11 假红）。
"""
from __future__ import annotations

import io
import json
import os
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


def _r(key, **kw):
    """槽位现算的期望串（不手写镜像表）。"""
    s = (TX.get(key) or {}).get("value", "")
    for k, v in kw.items():
        s = s.replace("{%s}" % k, str(v))
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
#   场是**跨指令留着**的 ⇒ 每一档之前先 `INST.clear(G)`，否则上一档开着的场会把这一档吃掉
#   （实测：不 clear ⇒ 后面三档根本不再 build，观测值停在上一档）。
from content import instance as INST
try:
    CBT.build, CBT.pick_encounter = _spy, (lambda *a, **k: [PIN])
    _set_party("u_a", None)                     # 一、单人（没队）⇒ 1（老路：一个数都没变）
    _at("u_a", LOC, NODE, hp=80)
    INST.clear(G)
    say("u_a", "攻击")
    _SEC.append(("没队", _SEEN[-1], 1))
    _set_party("u_a", {"id": _PID, "role": "captain", "tick": 1, "invites": {}})
    _set_party("u_b", {"id": _PID, "role": "member", "captain": "u_a"})
    _at("u_a", LOC, NODE, hp=80)                # 二、两人同在骨田 ⇒ 2
    _at("u_b", LOC, NODE, hp=70)
    INST.clear(G)
    say("u_a", "攻击")
    _SEC.append(("同节点两人", _SEEN[-1], 2))
    _at("u_b", LOC, "bn_camp")                  # 三、队友在同一张图的另一个节点 ⇒ 1
    INST.clear(G)
    say("u_a", "攻击")
    _SEC.append(("队友在别站", _SEEN[-1], 1))
    _at("u_b", LOC, NODE, hp=70)
    _set_party("u_c", {"id": _PID, "role": "member", "captain": "u_a"})
    _at("u_b", LOC, NODE, hp=70)                # 五、三人同节点 ⇒ 3
    _at("u_c", LOC, NODE, hp=50)
    INST.clear(G)
    say("u_a", "攻击")
    _SEC.append(("同节点三人", _SEEN[-1], 3))
    try:                                        # 六、在队里但读不到存档 ⇒ None（不缩放）
        PS.all_players = _boom
        INST.clear(G)
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
chk("★ 单人那档与 B3-17 之前**逐字相同**（party=1 ⇒ 那只 Boss 的面板照旧 ÷2：%s）"
    % int(CBT.monster_actor(_BOSS, MON[_BOSS], party=1).get("max_hp")),
    _SEC[0][1] == 1
    and int(CBT.monster_actor(_BOSS, MON[_BOSS], party=1).get("max_hp"))
    == int(round(float(_BH["hp"]) * float(RB.PARTY_SCALE["1"]["hp"]))))

# ══════════════════════════════════════════════════════════════
print("⑦ ★ B4-18：集火按此刻真在不在队里分档 · 逃跑那句桩句收进槽位")
_B7 = []
# ── 一、单人（没队）：两句照旧（认得出 / 认不出），且**过时那半句**一个字都没有
_set_party("u_a", None)
_set_party("u_b", None)
_at("u_a", LOC, NODE, hp=80)
_o1 = say("u_a", "集火")
_o2 = say("u_a", "集火 田鼠")
if _o1 != [_r("COMBAT_FOCUS_SOLO")]:
    _B7.append(("单人 集火", _o1, _r("COMBAT_FOCUS_SOLO")))
if _o2 != [_r("COMBAT_FOCUS_NAMED", name="田鼠")]:
    _B7.append(("单人 集火 田鼠", _o2, _r("COMBAT_FOCUS_NAMED", name="田鼠")))
chk("★ 单人档：『集火』= `COMBAT_FOCUS_SOLO`（%s）· 『集火 田鼠』= `COMBAT_FOCUS_NAMED`（%s）"
    % (_o1[0] if _o1 else "", _o2[0] if _o2 else ""), not _B7, "%s" % _B7[:2])

# ── 二、有队（两人站一起）⇒ 单人那两句都不许再说，走「有队」那一句
#      （★ 场是跨指令留着的 ⇒ 与 §⑥ 同一条纪律：先 clear 再敲）
_B7 = []
_set_party("u_a", {"id": _PID, "role": "captain", "tick": 1, "invites": {}})
_set_party("u_b", {"id": _PID, "role": "member", "captain": "u_a"})
_at("u_a", LOC, NODE, hp=80)
_at("u_b", LOC, NODE, hp=70)
INST.clear(G)
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

# ── 四、逃跑：两个别名都真敲 ⇒ 槽位那句 · 不含内部词 · 指向『后撤』· 档一个字不动
_B7 = []
_BEFORE = json.dumps(PS.get_player(G, "u_a") or {}, sort_keys=True, ensure_ascii=False)
_o6 = say("u_a", "逃跑")
_o7 = say("u_a", "脱离")
_AFTER = json.dumps(PS.get_player(G, "u_a") or {}, sort_keys=True, ensure_ascii=False)
if _o6 != [_r("COMBAT_FLEE_TODO")] or _o7 != [_r("COMBAT_FLEE_TODO")]:
    _B7.append(("逃跑 / 脱离", _o6, _o7, _r("COMBAT_FLEE_TODO")))
if _BEFORE != _AFTER:
    _B7.append(("逃跑动了档", _BEFORE[:80], _AFTER[:80]))
for _txt in _o6 + _o7:
    if ("第一版" in _txt) or ("轮流制" in _txt) or ("MISSING" in _txt) or ("【" in _txt):
        _B7.append(("还有内部词 / 内部 key", _txt))
if "后撤" not in (_o6[0] if _o6 else ""):
    _B7.append(("指不到真能用的那条路", _o6))
chk("★ `逃跑`（别名 `脱离`）真敲 = `COMBAT_FLEE_TODO`（%s）· 不含「第一版 / 轮流制 / 内部 key」· "
    "指向『后撤』· **档一个字不动**" % ((_o6[0] if _o6 else "").replace(chr(10), " / ")),
    not _B7, "%s" % _B7[:2])

# ── 五、覆盖面（源码守卫）：那句内联桩句不许回来（K61：判据的覆盖面跟判据一起加）
_CBSRC = io.open(os.path.join(str(REPO), "content", "cmds_battle.py"), encoding="utf-8").read()
# ★ 口径走 ast（K46）：注释 / docstring 里提到那句桩句**不算**「还在回它」——
#   要钉的是「`flee` 这个实现体里一个字符串字面量都不许有」（除了它自己的 docstring）。
import ast as _ast                                                     # noqa: E402
_FN = [n for n in _ast.parse(_CBSRC).body
       if isinstance(n, _ast.AsyncFunctionDef) and n.name == "flee"]
#   ★ docstring 那一格**按节点排掉**（不拿 get_docstring 的 clean 结果去比 —— 多行 docstring
#     的原始字面量与 clean 后的字面量不一样，K46 同族的一个小坑）
_DOC = (_FN[0].body[0].value
        if _FN and _FN[0].body and isinstance(_FN[0].body[0], _ast.Expr)
        and isinstance(_FN[0].body[0].value, _ast.Constant)
        and isinstance(_FN[0].body[0].value.value, str) else None)
#   ★ 什么算「文案」：docstring 不算（K46）· 槽位键那种全大写机器键不算（那是传槽位，不是文案）
_FN_LITS = [n.value for n in _ast.walk(_FN[0])
            if isinstance(n, _ast.Constant) and isinstance(n.value, str)
            and n is not _DOC and re.match(r"^[A-Z][A-Z0-9_]+$", n.value) is None] if _FN else []
_yields = [n for n in _ast.walk(_FN[0]) if isinstance(n, _ast.Yield)] if _FN else []
_HAS_SLOT = bool(re.search(r'^\s*yield T\("COMBAT_FLEE_TODO"\)', _CBSRC, re.M))
chk("★ 覆盖（ast）：`flee` 里**没有内联文案**（%d 处 —— 注释 / docstring / 槽位键都不算）· "
    "它 yield 出来的就是槽位那一句（`yield T(\"COMBAT_FLEE_TODO\")`：%s）"
    % (len(_FN_LITS), _HAS_SLOT),
    len(_FN) == 1 and not _FN_LITS and _HAS_SLOT)
chk("★ 覆盖：两条新槽位都在 texts 里、且占位与 params 双向对账（%s）"
    % " · ".join("%s=%s" % (k, sorted((TX.get(k) or {}).get("params") or []))
                 for k in ("COMBAT_FOCUS_PARTY", "COMBAT_FLEE_TODO")),
    all((TX.get(k) or {}).get("value") for k in ("COMBAT_FOCUS_PARTY", "COMBAT_FLEE_TODO"))
    and all(not (TX.get(k) or {}).get("params") for k in ("COMBAT_FOCUS_PARTY", "COMBAT_FLEE_TODO"))
    and not re.search(r"\{", (TX.get("COMBAT_FOCUS_PARTY") or {}).get("value", "")
                      + (TX.get("COMBAT_FLEE_TODO") or {}).get("value", "")))

print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
