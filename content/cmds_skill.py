# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 技能那两条（B3-9「装备与技能」那组）：技能 / 学习。

口径（真源 `06_第一阶段垂直切片/04_指令总表.md` §三 · `03_职业与技能/02_技能体系规划_v1.md §四`）：

    技能 / 技能表        随时               已学技能
    学习 <技能名>（别名 学） 等级 / 点数够     学技能

★ 「已学」的真源 = **档上那一格 `skills`**（`combat.player_actor` 取的就是它）：

  · 档上**记过**      ⇒ 就列那几条（记的顺序按 (解锁等级, id)，与引擎拿到的那一班同序）；
  · 档上**没记过**（新号）⇒ 按现有口径 = 本职业**此刻解锁**的那一班
    （`owner_class` == 你的职业 且 `skills.lv`（**解锁等级**）≤ 你的等级）——
    与 `combat._default_skills` 同一支、同一序，所以「看到什么 = 打起来放什么」。
    ★ B4-1 补一句：那一班里**被动也在**（它开战时由事件总线挂上、不是"放"出来的）——
      所以「能放的那半」才对应战斗技能表（`_default_skills` 把被动排除在外），
      被动只是**列在这儿给玩家看**（`probe_skills` ⑧ 钉着这一条）。
  · 「学习」落档时**把此刻解锁的那一班一起记上** —— 否则「学了一条新的反而丢掉默认那一班」
    是个坑（档上一旦有记录，战斗就只认记录）。

★ 解锁等级走域里的 `skills.lv`（`02_技能体系规划 §四` 原话「已有 skills.lv（解锁等级）」）——
  今天 30 条全是 1 ⇒ 1 级就能学全班；11–20 级那 12 条补进来之后，**这一处自动**开始按级放行
  （`解锁等级 > 等级` 的那些走 `SYS_SKILL_LOCKED`，不手写门槛）。
  「点数」那一档（每 2 级 1 点的**技能强化点**，`07_装备体系_v2 §一`）域里还没有 ⇒ 见 `_notes.md`。

★ 呈现面只出**名字**（skills 域的 id 是机器键，漏出去就是 B3-7 / B3-9 同族那条线）。

★ 文案一律走 texts（`SYS_SKILL_*`）—— 本文件不内联中文（probe_copy ①②③）。
"""
from __future__ import annotations

from .cmds_ast import _data, _cls_label, _p, _save, T
from .cmds_talk import _arg


def _skills() -> dict:
    return {k: v for k, v in _data("skills").items() if not str(k).startswith("_")}


def _of_class(cls_id: str, level) -> tuple:
    """本职业的技能分两拨（与 `combat._default_skills` 同一支、同一序：`(lv, id)` 升序）。

    返回 `(解锁了的那一拨 [(id, rec)], 还没到等级的那一拨 [(id, rec, lv)])`。
    """
    mine = [(int(v.get("lv") or 1), k, v) for k, v in _skills().items()
            if v.get("owner_class") == cls_id]
    mine.sort()
    lv = int(level or 1)
    return ([(k, v) for a, k, v in mine if a <= lv],
            [(k, v, a) for a, k, v in mine if a > lv])


def known_ids(p) -> list:
    """档上的技能表；**没记过** ⇒ 本职业此刻解锁的那一班（现状口径）。"""
    got = p.get("skills")
    if isinstance(got, list) and got:
        return [str(x) for x in got]
    avail, _locked = _of_class(str(p.get("cls") or ""), p.get("level") or 1)
    return [k for k, _v in avail]


def _ordered(p, ids) -> list:
    """技能表按 `(解锁等级, id)` 排 —— 与引擎拿到的那一班同序（别让档上的次序乱着）。"""
    order = {k: (int(v.get("lv") or 1), k) for k, v in _skills().items()}
    return sorted(set(str(x) for x in ids), key=lambda x: order.get(x, (99, x)))


def _by_name(sk: dict, want: str) -> tuple:
    """技能按名字（或 id）认一条；认不出回 `(None, None)`。

    ★ 「≥2 字才算部分匹配」与 `loot.match_ids` 同一口径（B4-20 起那一个是唯一的一口）。
      （重名的那一对「后撤」落在两个职业上 —— 认到的那条**不是你职业的**会被
      `SYS_SKILL_NOTMINE` 挡住，不乱学。）
    """
    want = str(want or "").strip()
    if not want:
        return (None, None)
    if want in sk:
        return (want, sk[want])
    for k in sorted(sk):
        nm = str(sk[k].get("name") or "")
        if nm and (want == nm or (len(want) >= 2 and want in nm)):
            return (k, sk[k])
    return (None, None)


# ══════════════════════════════════════════════════════════════
# 一、技能（已学技能一览）
# ══════════════════════════════════════════════════════════════
async def skills(env, sink, uid, player):
    """`技能` —— 已会的逐条列（名字 / 类别 / 耗法 / 冷却 + 域里的 `note` 那句人话）。

    还没到解锁等级的另起一拨（`SYS_SKILL_LOCKED`）—— 玩家看得见「再升几级会多出什么」。
    """
    p = _p(player)
    cls = str(p.get("cls") or "")
    if not cls:
        yield T("SYS_SKILL_NOCLS")
        return

    sk = _skills()
    known = [i for i in known_ids(p) if i in sk]
    _avail, locked = _of_class(cls, p.get("level") or 1)
    yield T("SYS_SKILL_HEAD", cls=_cls_label(cls), known=len(known), locked=len(locked))
    for iid in _ordered(p, known):
        rec = sk[iid]
        yield T("SYS_SKILL_ROW", name=rec.get("name", iid), kind=rec.get("kind", ""),
                mp=rec.get("mp", 0), cd=rec.get("cd", 0))
        if rec.get("note"):
            yield T("SYS_SKILL_NOTE", note=str(rec["note"]))
    for k, v, lv in locked:
        yield T("SYS_SKILL_LOCKED", name=v.get("name", k), lv=lv)
    stale = [i for i in known_ids(p) if i not in sk]
    if stale:
        yield T("SYS_SKILL_STALE", n=len(stale))
    yield T("SYS_SKILL_TAIL")


# ══════════════════════════════════════════════════════════════
# 二、学习
# ══════════════════════════════════════════════════════════════
async def skill_learn(env, sink, uid, player):
    """`学习 <技能名>` —— 把一条技能记进档上的技能表。

    四道门，依次收紧（每一道都点名，不静默）：
      ① 域里得有这条（名字或 id）      ② 得是本职业的
      ③ 解锁等级 ≤ 当前等级            ④ 档上还没有它
    过了就落档：**此刻解锁的那一班 + 这一条**一起记上（见文件抬头的那个坑）。
    """
    p = _p(player)
    want = _arg(env)
    cls = str(p.get("cls") or "")
    if not cls:
        yield T("SYS_SKILL_NOCLS")
        return
    if not want:                       # ★ B4-10：没带技能名就照实说
        yield T("SYS_SKILL_LEARN_ASK")
        return

    sk = _skills()
    sid, rec = _by_name(sk, want)
    if not sid:
        yield T("SYS_SKILL_NONE", name=want)
        return

    owner = str(rec.get("owner_class") or "")
    if owner and owner != cls:
        yield T("SYS_SKILL_NOTMINE", name=rec.get("name", sid), owner=_cls_label(owner))
        return

    lv = int(rec.get("lv") or 1)
    mine = int(p.get("level") or 1)
    if lv > mine:
        yield T("SYS_SKILL_TOO_LOW", name=rec.get("name", sid), lv=lv, gap=lv - mine)
        return

    if sid in known_ids(p):
        yield T("SYS_SKILL_ALREADY", name=rec.get("name", sid))
        return

    avail, _locked = _of_class(cls, mine)
    p["skills"] = _ordered(p, [k for k, _v in avail] + [sid])
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_SKILL_LEARN", name=rec.get("name", sid), n=len(p["skills"]))
