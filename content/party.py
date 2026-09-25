# -*- coding: utf-8 -*-
"""《阿斯特兰》队伍层（B3-25）—— 包侧唯一出口（建队/邀请/同意/加入/离队/解散/查队伍/队长/成员上限）。

真源（包的域）：`content/data/party.json` 那条口径记录 `pt_rules`（上限 / 同一处的门槛 /
队长归属 / 入队要不要『同意』/ 邀请有效期）—— 本文件不写死任何数，全从域里取。
设计真源（只读）：`00_总纲/03_主要玩法.md` §4.7（组队 1–4 人 · 同地图玩家可一起进）·
`06_第一阶段垂直切片/17_组队与策略配合_v1.md`（§一 异步窗口制 · §四 轮流制 · §五 按人数缩放）·
`06_第一阶段垂直切片/04_指令总表.md` §十（`队伍` `组队` 建队/看队 · `邀请 <人>` · `离队`）。

引擎零改动：队伍是「档上那一格 + 现算的名册」，没有新的引擎形状。

档上那一格（两个角色，两个形状）
--------------------------------
    队长   flags.party = {"id": "pt_<队长uid>_<起队那一刻>", "role": "captain",
                          "tick": <起队刻>, "invites": {"<uid>": {"tick": <刻>}}}
    队员   flags.party = {"id": <同一个 id>, "role": "member", "captain": "<队长 uid>"}

★ **名册现算，不另存一份**：队长那一队的队员 = 本群存档里那些档上写着「我在他这个队里」
  的人（`role == member` 且 `id` / `captain` 都对得上）。好处是「队长不在了」不用谁来收尸 ——
  每个读队的人现算时发现队长那一格不在 ⇒ 判「队散了」（`stale`），并**只清自己那一格**
  （自愈，别去改别人的档）。

三条动作的口径（每条判据都在探针里）
------------------------------------
① 建队 `create` —— 发起人即队长（`captain_is_founder`）。
② 邀请 `invite` —— 邀请记在**队长那一格**上（`invites`），有效期 `invite_ttl_ticks` 刻；
   被邀的人自己敲『同意』才算入队（`join_needs_accept`）—— 文字游戏里弹不出窗，
   「同意」就是**他本人打的那一下**（`accept`）。⇒ 「离线的人进不来」是**结构性**保证：
   他不敲那一下就在队外；邀请到点作废（有明确回话，不静默）。宿主没给 presence 注入面，
   本包**不编**「多久没落档 = 离线」那种数（见本分支 _notes.md 的待拍板）。
③ 同意 `accept` —— 那一刻**再判一遍**：队长还在不在 · 队满没满 · 还在不在同一处。
④ 离队 `leave` —— 队员退：清自己那一格；队长退 = **解散**（队员那几格由他们自己现算时清掉）。

fail-closed 三条（不许静默）
---------------------------
  · 口径记录缺了 / 坏了（上限不是 ≥2 的整数、有效期不是正整数、开关不是布尔）⇒ 抛 `PartyError`；
  · 档上 `flags.party` 形状不对（角色认不出 / id 空 / 队员没写队长）⇒ 抛（不静默当没队）；
  · 存档读不出来 ⇒ **不猜人数**：`present_count` 回 `None`（= 「不知道几个人」），
    交给 `content/combat.party_scale_of` 那条 fail-closed 走设计值 —— 绝不因为「不知道」
    而悄悄把团队内容（Boss）削弱。
"""
from __future__ import annotations

import json
import os

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_C: dict = {}

#: 档上那一格的名字（唯一来源 —— 别处不许再拼这串）
FLAG = "party"

ROLE_CAPTAIN = "captain"
ROLE_MEMBER = "member"

# ── 判据码（ASCII；呈现口拿它映射 texts 槽位，本文件不产中文）────────────
#: 邀请
INV_ASK = "invite_ask"
INV_NOBODY = "invite_nobody"
INV_SELF = "invite_self"
INV_NOTCAP = "invite_not_captain"
INV_NOCLS = "invite_no_class"
INV_MEMBER = "invite_member"
INV_OTHER = "invite_other_party"
INV_FULL = "invite_full"
INV_FAR = "invite_far"
INV_AGAIN = "invite_again"
INV_OK = "invite_ok"
#: 同意
ACC_IN = "accept_in_party"
ACC_NONE = "accept_none"
ACC_EXPIRED = "accept_expired"
ACC_FULL = "accept_full"
ACC_FAR = "accept_far"
ACC_OK = "accept_ok"
#: 离队
LV_NONE = "leave_none"
LV_MEMBER = "leave_member"
LV_CAPTAIN = "leave_captain"


class PartyError(Exception):
    """队伍这条线的数据 / 档坏了 —— 当场抛，不静默兜底。"""


def _load(name):
    if name not in _C:
        with open(os.path.join(_DIR, name + ".json"), encoding="utf-8") as f:
            _C[name] = json.load(f)
    return _C[name]


def table() -> dict:
    """域里的条目（`_` 前缀 = 私有元信息，不是条目 —— 与编辑器/装载器同口径）。"""
    return {k: v for k, v in _load("party").items() if not str(k).startswith("_")}


def rules() -> dict:
    """队伍口径（`pt_rules`）—— 缺了 / 坏了当场抛（fail-closed：不猜上限、不猜有效期）。"""
    rec = table().get("pt_rules")
    if not isinstance(rec, dict):
        raise PartyError("party 域缺 pt_rules（队伍口径那一条）—— 消费端 content/party.py")
    mx = rec.get("max_members")
    if isinstance(mx, bool) or not isinstance(mx, int) or mx < 2:
        raise PartyError("pt_rules.max_members 得是 ≥2 的整数（队伍上限）：%r" % (mx,))
    ttl = rec.get("invite_ttl_ticks")
    if isinstance(ttl, bool) or not isinstance(ttl, int) or ttl < 1:
        raise PartyError("pt_rules.invite_ttl_ticks 得是正整数（刻）：%r" % (ttl,))
    for k in ("same_map", "same_node", "captain_is_founder", "join_needs_accept"):
        if not isinstance(rec.get(k), bool):
            raise PartyError("pt_rules.%s 得是 true / false：%r" % (k, rec.get(k)))
    return rec


def max_members() -> int:
    """成员上限（真源 03_ §4.7「1–4 人」）。"""
    return int(rules()["max_members"])


def grades() -> list:
    """有效人数档 = 1..上限 —— 面板倍数表**必须有数**的就是这几档（探针跨域对账）。"""
    return list(range(1, max_members() + 1))


def invite_ttl_ticks() -> int:
    """邀请有效期（刻）。"""
    return int(rules()["invite_ttl_ticks"])


def now_ticks(epoch=None) -> int:
    """现在第几刻（1 刻 = 1 游戏秒）—— 钟源只有一个：`content/calendar`（别处不许自己算）。"""
    from . import calendar as CAL
    day, hod = CAL.game_time(epoch)
    return int(day) * 86400 + int(hod * 3600)


# ══════════════════════════════════════════════════════════════
# 档上那一格
# ══════════════════════════════════════════════════════════════
def _flags(p) -> dict:
    """档上的 flags（拷一层再改 —— 别污染默认档 / 别人那份）。"""
    f = dict(p.get("flags") or {})
    p["flags"] = f
    return f


def rec_of(p):
    """档上那一格（形状坏 ⇒ 抛）。没有这一格 / 是空 ⇒ `None`（= 没队）。"""
    v = (p.get("flags") or {}).get(FLAG)
    if v in (None, {}):
        return None
    if not isinstance(v, dict):
        raise PartyError("档上的 flags.%s 得是对象：%r" % (FLAG, v))
    role = v.get("role")
    if role not in (ROLE_CAPTAIN, ROLE_MEMBER):
        raise PartyError("档上的 flags.%s.role 认不出（%s / %s）：%r"
                         % (FLAG, ROLE_CAPTAIN, ROLE_MEMBER, role))
    if not str(v.get("id") or ""):
        raise PartyError("档上的 flags.%s.id 是空的（队没有一个可对账的名字）" % FLAG)
    if role == ROLE_MEMBER and not str(v.get("captain") or ""):
        raise PartyError("档上的 flags.%s.captain 是空的（队员得写着队长是谁）" % FLAG)
    return v


def clear(p) -> None:
    """清掉自己那一格（离队 / 自愈 —— 只动自己的档）。"""
    _flags(p).pop(FLAG, None)


def is_captain(p) -> bool:
    r = rec_of(p)
    return bool(r) and r.get("role") == ROLE_CAPTAIN


def pid_of(uid, tick) -> str:
    """队名（可复现）：发起人 + 起队那一刻 —— 不掷骰子。"""
    return "pt_%s_%d" % (str(uid), int(tick))


def create(p, uid, tick) -> dict:
    """建队：发起人即队长。返回写下的那一格。"""
    r = {"id": pid_of(uid, tick), "role": ROLE_CAPTAIN, "tick": int(tick), "invites": {}}
    _flags(p)[FLAG] = r
    return r


def _safe_rec(d):
    """别人的档 → 那一格；形状坏 ⇒ 当成「没队」跳过（不因为别人档坏而炸掉我的命令）。"""
    try:
        return rec_of(d if isinstance(d, dict) else {})
    except PartyError:
        return None


# ══════════════════════════════════════════════════════════════
# 本群存档（名册现算的唯一原料）
# ══════════════════════════════════════════════════════════════
def rows_of(group_id) -> list:
    """本群存档里的所有人 —— 唯一来源 = 包自己的存档半边（`content/persistence`）。读不到 ⇒ 抛。"""
    from . import persistence as PS
    try:
        rows = PS.all_players(str(group_id or ""))
    except Exception as exc:                                        # noqa: BLE001
        raise PartyError("存档读不出来（名册要现算它）：%r" % (exc,))
    return [r for r in rows if isinstance(r, dict)]


def index(rows: dict) -> dict:
    """存档行 → {uid: 档}（一次读、全队共用 —— 别在循环里反复查库）。"""
    out = {}
    for r in rows or []:
        d = r.get("data")
        out[str(r.get("uid"))] = d if isinstance(d, dict) else {}
    return out


def _roster(idx: dict, captain: str, pid, with_self=None) -> list:
    """一个队现在的成员（现算）：队长 + 档上写着「我在他这个队里」的人。"""
    mem = [str(captain)]
    for u, d in (idx or {}).items():
        if u == str(captain):
            continue
        r = _safe_rec(d)
        if r and r.get("role") == ROLE_MEMBER and str(r.get("id")) == str(pid) \
                and str(r.get("captain")) == str(captain):
            mem.append(u)
    if with_self is not None and str(with_self) not in mem:
        mem.append(str(with_self))
    return sorted(set(mem))


def membership(rows, p, uid) -> dict:
    """我这一队现在是什么样：`{"role", "pid", "captain", "members", "stale"}`。

    · 我没队 ⇒ `role` = None（members 只有我）；
    · 我是队员、但**队长那一格不在 / 队名对不上** ⇒ `stale` = True（队散了，调用方只清自己那一格）；
    · 我是队长 ⇒ members 现算。
    """
    mine = rec_of(p)
    me = str(uid)
    if not mine:
        return {"role": None, "pid": None, "captain": None, "members": [me], "stale": False}
    idx = index(rows)
    if mine.get("role") == ROLE_CAPTAIN:
        return {"role": ROLE_CAPTAIN, "pid": str(mine["id"]), "captain": me,
                "members": _roster(idx, me, mine["id"]), "stale": False}
    cap = str(mine.get("captain") or "")
    crec = _safe_rec(idx.get(cap))
    if not crec or crec.get("role") != ROLE_CAPTAIN or str(crec.get("id")) != str(mine["id"]):
        return {"role": ROLE_MEMBER, "pid": str(mine.get("id")), "captain": cap,
                "members": [me], "stale": True}
    return {"role": ROLE_MEMBER, "pid": str(mine["id"]), "captain": cap,
            "members": _roster(idx, cap, mine["id"]), "stale": False}


def view(rows, p, uid) -> dict:
    """「队伍」那一屏要的账：这一队 + 逐人（名字 / 等级 / 血 / 在哪一站）。

    ★ 别人的那几格来自**存档里那一份档**（现读）；自己那份用**手上这份**（刚被命令改过的）。
    """
    mem = membership(rows, p, uid)
    idx = index(rows)
    out = []
    for u in mem["members"]:
        d = p if u == str(uid) else (idx.get(u) or {})
        out.append({"uid": u, "me": u == str(uid),
                    "name": str(d.get("name") or ""),
                    "level": int(d.get("level") or 1),
                    "hp": d.get("hp"), "hp_max": d.get("hp_max"),
                    "loc": str(d.get("loc") or ""), "node": str(d.get("node") or "")})
    return {"role": mem["role"], "pid": mem["pid"], "captain": mem["captain"] or str(uid),
            "stale": mem["stale"], "members": out, "n": len(out),
            "max": max_members()}


# ══════════════════════════════════════════════════════════════
# 同一处（真源 03_ §4.7「同地图玩家可一起进」）
# ══════════════════════════════════════════════════════════════
def same_place(a, b) -> bool:
    """两档在不在同一处 —— 门槛全读域（`same_map` 真源写了；`same_node` 是更严的那一档）。"""
    r = rules()
    if not r["same_map"]:
        return True
    if str(a.get("loc") or "") != str(b.get("loc") or ""):
        return False
    if r["same_node"] and str(a.get("node") or "") != str(b.get("node") or ""):
        return False
    return True


def _find_by_name(idx: dict, want: str) -> str:
    """名字 → uid（本群存档里现找）。**并列取 uid 最小的那个**（可复现，不掷骰子）。"""
    hits = sorted(u for u, d in (idx or {}).items()
                  if d and str(d.get("name") or "").strip() == str(want or "").strip())
    return hits[0] if hits else ""


def name_in(idx: dict, uid, p=None, me=None) -> str:
    """某人的显示名（自己那份优先 —— 手上那份可能是刚改过的）。"""
    if me is not None and str(uid) == str(me) and p is not None:
        d = p
    else:
        d = (idx or {}).get(str(uid)) or {}
    return str((d or {}).get("name") or "")


# ══════════════════════════════════════════════════════════════
# ② 邀请（记在队长那一格上）
# ══════════════════════════════════════════════════════════════
def _live_invites(rec: dict, tick) -> dict:
    """这一格上还活着的邀请（过期的当场不算 —— 失效是**现算**的，不靠谁来清）。"""
    ttl = invite_ttl_ticks()
    out = {}
    for u, v in (rec.get("invites") or {}).items():
        at = int((v or {}).get("tick") or 0)
        if int(tick) - at <= ttl:
            out[str(u)] = {"tick": at}
    return out


def invite(p, uid, want, rows, tick) -> dict:
    """邀请本群里的一个人（`want` = 名字）。返回 `{"code": …, "name": …, …}`。

    判据顺序（每一条都有明确回话，一条都不静默）：
      没给名字 → 查无此人 → 就是你 → 不是队长 → 他还没建号 → 他已经在本队 →
      他在别人的队里 → 队满了 → 不在一处 → 已经邀过（没过期）→ 记下这一封。
    ★ 同不同一处是**预判**（按他档上那一份「现在在哪」）—— 权威的那一判在 `accept` 里。
    """
    me, want = str(uid), str(want or "").strip()
    if not want:
        return {"code": INV_ASK}
    if want == str(p.get("name") or "").strip():
        return {"code": INV_SELF}                  # 自己的名字先认（本群存档里还没有我那一行也认得）
    idx = index(rows)
    hit = _find_by_name(idx, want)
    if not hit:
        return {"code": INV_NOBODY, "name": want}
    if hit == me:
        return {"code": INV_SELF}
    mem = membership(rows, p, uid)
    if mem["stale"]:
        clear(p)                                   # 自愈：队长那支队不在了 ⇒ 我现在没队
        mem = membership(rows, p, uid)
    if mem["role"] is None:
        create(p, uid, tick)                       # 单人打『邀请』= 顺带起个队（发起人即队长）
        mem = membership(rows, p, uid)
    elif mem["role"] != ROLE_CAPTAIN:
        return {"code": INV_NOTCAP, "captain": mem["captain"],
                "name": name_in(idx, mem["captain"])}
    t = idx.get(hit) or {}
    if not str(t.get("cls") or ""):
        return {"code": INV_NOCLS, "name": name_in(idx, hit) or hit, "uid": hit}
    tmem = membership(rows, t, hit)
    if tmem["role"] is not None:
        if tmem["pid"] and tmem["pid"] == mem["pid"]:
            return {"code": INV_MEMBER, "name": name_in(idx, hit) or hit, "uid": hit}
        if not tmem["stale"]:
            return {"code": INV_OTHER, "name": name_in(idx, hit) or hit, "uid": hit}
    if len(mem["members"]) >= max_members():
        return {"code": INV_FULL, "max": max_members(), "name": name_in(idx, hit) or hit, "uid": hit}
    if not same_place(p, t):
        return {"code": INV_FAR, "name": name_in(idx, hit) or hit, "uid": hit,
                "loc": str(t.get("loc") or ""), "node": str(t.get("node") or "")}
    rec = rec_of(p) or {}
    live = {u: v for u, v in _live_invites(rec, tick).items() if u not in mem["members"]}
    if hit in live:
        return {"code": INV_AGAIN, "name": name_in(idx, hit) or hit, "uid": hit}
    live[hit] = {"tick": int(tick)}
    rec["invites"] = live
    _flags(p)["party"] = rec
    return {"code": INV_OK, "name": name_in(idx, hit) or hit, "uid": hit,
            "ttl": invite_ttl_ticks()}


# ══════════════════════════════════════════════════════════════
# ③ 同意（本人在有效期内自己敲的那一下）
# ══════════════════════════════════════════════════════════════
def pending(rows, uid, tick, *, expired=False, p=None) -> list:
    """本群**指向我**的邀请，最新的排前面（tick 大的在前；并列按队长 uid —— 可复现）。

    ★ 两条「现算」的过滤（不在别人档上做清理 —— 谁的档谁改）：
      · 已经用掉的那一封：我档上写的就是那支队（`id` 对得上）⇒ 这条邀请不算数了
        （入队那一下只改**自己**那一格，队长那格的名单留着，读的时候跳过）；
      · `expired=True` ⇒ 只要**过期**的那些（调用方拿它区分「没人邀你」与「那封过期了」）。
    """
    ttl = invite_ttl_ticks()
    idx = index(rows)
    mine = rec_of(p) if p is not None else _safe_rec((idx.get(str(uid)) or {}))
    my_pid = str((mine or {}).get("id") or "")
    out = []
    for u, d in idx.items():
        r = _safe_rec(d)
        if not r or r.get("role") != ROLE_CAPTAIN:
            continue
        if my_pid and (mine or {}).get("role") == ROLE_MEMBER and str(r.get("id")) == my_pid:
            continue
        v = (r.get("invites") or {}).get(str(uid))
        if not v:
            continue
        at = int((v or {}).get("tick") or 0)
        left = ttl - (int(tick) - at)
        if not ((left < 0) if expired else (left >= 0)):
            continue
        out.append({"captain": u, "pid": str(r.get("id")), "tick": at, "left": left,
                    "members": _roster(idx, u, r.get("id"))})
    out.sort(key=lambda x: (-x["tick"], x["captain"]))
    return out


def accept(p, uid, rows, tick) -> dict:
    """『同意』—— 入队那一刻**再判一遍**（队长还在 · 队没满 · 还在同一处）。"""
    me = str(uid)
    mine = rec_of(p)
    if mine:
        mem0 = membership(rows, p, uid)
        if not mem0["stale"]:
            return {"code": ACC_IN, "captain": mem0["captain"]}
        clear(p)                                   # 自愈：队长那支队不在了
    cand = pending(rows, uid, tick, p=p)
    if not cand:
        old = pending(rows, uid, tick, expired=True, p=p)
        if old:
            return {"code": ACC_EXPIRED, "captain": old[0]["captain"]}
        return {"code": ACC_NONE}
    best = cand[0]
    idx = index(rows)
    cap = best["captain"]
    cdata = idx.get(cap) or {}
    if len(best["members"]) >= max_members():
        return {"code": ACC_FULL, "captain": cap, "name": name_in(idx, cap),
                "max": max_members()}
    if not same_place(p, cdata):
        return {"code": ACC_FAR, "captain": cap, "name": name_in(idx, cap),
                "loc": str(cdata.get("loc") or ""), "node": str(cdata.get("node") or "")}
    _flags(p)[FLAG] = {"id": str(best["pid"]), "role": ROLE_MEMBER, "captain": cap}
    return {"code": ACC_OK, "captain": cap, "name": name_in(idx, cap),
            "n": len(best["members"]) + 1}


# ══════════════════════════════════════════════════════════════
# ④ 离队 / 解散
# ══════════════════════════════════════════════════════════════
def leave(p, uid, rows) -> dict:
    """离队：队员清自己那一格；队长退 = 解散（队员的格由他们自己现算时清掉）。"""
    mine = rec_of(p)
    if not mine:
        return {"code": LV_NONE}
    me = str(uid)
    mem = membership(rows, p, uid)
    idx = index(rows)
    if mine.get("role") == ROLE_CAPTAIN:
        others = [name_in(idx, u) or u for u in mem["members"] if u != me]
        clear(p)
        return {"code": LV_CAPTAIN, "names": others, "n": len(mem["members"])}
    cap = str(mine.get("captain") or "")
    clear(p)
    return {"code": LV_MEMBER, "captain": cap, "name": name_in(idx, cap)}


def disband(p, uid, rows) -> dict:
    """解散 —— 队长那一支（`leave` 的同一条路；单独给一个名字，调用方读着清楚）。"""
    return leave(p, uid, rows)


# ══════════════════════════════════════════════════════════════
# 进战那一刻：真实人数（cmds_battle 那三处 party=… 的唯一来源）
# ══════════════════════════════════════════════════════════════
def _alive(d) -> bool:
    """活人 = 档上那格血**不是 ≤0**（没这一格 = 没被打倒过 ⇒ 算活着）。"""
    hp = (d or {}).get("hp")
    if hp is None:
        return True
    try:
        return float(hp) > 0
    except (TypeError, ValueError):
        return True


def members_present(rows, p, uid) -> list:
    """在队 + **同节点** + 活人（含自己）—— 打这一场实际站在一起的人。"""
    mem = membership(rows, p, uid)
    if mem["role"] is None or mem["stale"]:
        return [str(uid)]
    idx = index(rows)
    loc, node = str(p.get("loc") or ""), str(p.get("node") or "")
    out = []
    for u in mem["members"]:
        d = p if u == str(uid) else (idx.get(u) or {})
        if str(d.get("loc") or "") != loc or str(d.get("node") or "") != node:
            continue
        if not _alive(d):
            continue
        out.append(u)
    return out


def present_count(p, uid, rows) -> int | None:
    """进战那一刻的**真实人数**（= `members_present` 的长度，至少 1）。

    ★ 两种「不知道」的语义分得清清楚楚：
      · 我没队 ⇒ **1**（单人那条老路，一个数都没变，连库都不用读）；
      · 我在队里、但**存档读不出来**（`rows is None`）⇒ **None** = 「不知道几个人」——
        调用方（`content/combat.party_scale_of`）据此**不缩放**（走设计值），
        绝不因为不知道而悄悄把团队内容削弱。
    """
    if not rec_of(p):
        return 1
    if rows is None:
        return None
    return max(1, len(members_present(rows, p, uid)))
