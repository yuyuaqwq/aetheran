# -*- coding: utf-8 -*-
"""《阿斯特兰》多人战斗的轮转与输入窗口（B3-26）—— 「场」的路由 + 轮转骨架。

真源（照奥兰迪亚那一套，不是「代打」）
--------------------------------------
`06_第一阶段垂直切片/17_组队与策略配合_v1.md` §四（★ 2026-09-24 修正）· `00_总纲/03_主要玩法.md` §4.10。
**参考实现（另一个包，只读）**：`orlandia/content/cmds_instance_router.py:378-418`。

    ① 轮转      谁该行动 = **存活玩家中 ct 最小者**（CTB 的自然顺序，不是「同时」）
    ② 没轮到你  返回「等待提示」，告诉你在等谁
    ③ 轮到你    给你**输入窗口**（本作第一版 45 秒；奥兰迪亚 60 秒）
    ④ 超时      **自动防御**（act("defend")），日志写「XX 超时自动防御」（全队可见）
    ⑤ 防死循环  最多连续消化 20 个挂机玩家（guard > 20 就 break）

前四条与第五条的两条数都从 `content/rules/instance.json` 现读（代码里不写数）。

这一层在系统里的位置
--------------------
* **「场」（本模块的唯一新形状）** = 一群人正在打的那一场：`members`（谁在场）·
  `pick` / `affixes`（打的什么）· `battle`（引擎 `Battle.to_state()` 的存档态）·
  `logs`（这一场到现在为止的日志）· `turn` / `turn_time`（谁拿着窗口、窗口什么时候开的）。
  它**按群存**（`persistence.group_get/group_set`，与单人档同一张库的另一张表）——
  存档半边原本只有「每人一行」，共同档是新形状（`_notes.md` §B3-26 记了来历）。
* **引擎零改动**：多人那一场就是 `sides["player"]` 里放几个人（引擎每边本来就是列表），
  「谁该动」照 CTB 的自然顺序（ct 最小者），一场跨多条指令靠引擎自己的
  `serialize.to_state / from_state` 往返（面板 / ct / 待发槽 / 效果都随档走）。
* **入口只有一个**：`route_needed()`（这一条指令要不要走「场」）+ `take_turn()`（真走）。
  `content/cmds_battle.py` 那几条真正花掉「你这一手」的战斗指令都在**同一行**接它。

单人路径一个字都不变（硬判据）
------------------------------
队伍名单口（B3-25 落地之后）：`members_of()` 走 `content.party.members_of` —— 在队 ⇒ 真名单；
不在队 ⇒ 回 `[uid]` 一个 ⇒ 单人档 `route_needed()` 仍回 `False`、直接往下走**单人那条路**
（`scripts/probe_instance.py` ⑤ 拿改前基线的真跑回话逐字对）。
★ B4-18：这一段原先写「（B3-25 那一批）今天还不存在」—— 那句话在 B3-25 落地那天就过时了。

本批**不做**的（写在这儿免得下一轮当成已完，详见本工作树 `_notes.md`）
--------------------------------------------------------------------
* 队伍本身（谁在队里 / 邀请 / 离队）—— B3-25 那一批；本模块只点名要的口（见 `members_of`）。
* 后撤 / 换武器 / 集火 / 逃跑 在多人场里的口径**真源没写** ⇒ 本批不接（单人那条老路原样）；
  只有「花掉一手」的那几条战斗指令走「场」（攻击 / 防御 / 技能 / 用物 / 打断）。
* 「轮到你了」的**全队广播**：QQ 那边只有回话能到群里 ⇒ 谁拿着窗口要看回话。本模块的取法
  （谁都能敲一下知道自己该不该动 + 没轮到就报「在等谁」）是骨架；主动推送要宿主的投递口。
* 多人结算的**分配口径**（击杀奖励一人一份还是平分）真源没写 ⇒ 今天按「每人各走一遍单人那条
  结算路」（`_finish`），登记为待补行。
* `battle` 那个内置守卫（「必须在战斗中」）没接：宿主的 `battle_check` 今天不给
  （引擎侧 `Env` 有位置，见 `_notes.md` 遗留清单）。
"""
from __future__ import annotations

import json
import os

from . import persistence as PS
from .cmds_ast import T, _p, hp_cap_or_line

#: 共同档里的作用域名（这一套数据是谁在用）—— 键形状 `<scope>:<group_id>`
SCOPE = "instance"

#: 「场」记录里必须有的几格（缺了 = 记录坏了 ⇒ 当场抛，不当成「没开过」）
ST_KEYS = ("members", "pick", "battle")

_RULES = None
_RULES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules", "instance.json")


# ══════════════════════════════════════════════════════════════
# 一、那几条边界数（唯一真源 = rules/instance.json）
# ══════════════════════════════════════════════════════════════
def rules() -> dict:
    """`content/rules/instance.json`（读一次；读不到 / 坏 → 当场抛 —— 没有默认值）。"""
    global _RULES
    if _RULES is None:
        with open(_RULES_PATH, encoding="utf-8") as f:
            got = json.load(f)
        if not isinstance(got, dict):
            raise ValueError("instance.json 得是一张表：%r" % (got,))
        _RULES = got
    return _RULES


def _rule_int(key) -> int:
    v = rules().get(key)
    if isinstance(v, bool) or not isinstance(v, int) or v < 1:
        raise ValueError("instance.json 的 %s 得是 1 以上的整数（没有默认值）：%r" % (key, v))
    return v


def window_seconds() -> int:
    """轮到你之后的**输入窗口**（秒）—— 真源 `17_ §四③` / `03_ §4.10`（本作第一版 45）。"""
    return _rule_int("window_seconds")


def afk_guard() -> int:
    """一次路由里最多连续消化几个挂机玩家 —— 真源 `17_ §四⑤`（20）。"""
    return _rule_int("afk_guard")


def now() -> float:
    """现在（秒）—— 走**包自己的钟口**（`persistence.clock`，宿主注入；探针可以换假钟）。"""
    return float(PS.clock())


# ══════════════════════════════════════════════════════════════
# 二、队伍名单口（B3-25 的落点；今天没有 ⇒ 单人）
# ══════════════════════════════════════════════════════════════
#: ★ 注入面：`callable(group_id, uid) -> 序列[uid]`。要替换「谁在队里」只该动这里
#:   （探针就是这么造的：真跑两条档进同一场，而不去发明一个队伍域）。
party_members = None


def members_of(group_id, uid) -> list:
    """这一场该有谁 —— **唯一取队伍名单的口**（三人排：注入面 → 包内 `content.party` → 单人）。

    ★ 队伍域是 B3-25 那一批的活，本批**不发明**它，只点名要的形状：

        content/party.py::members_of(group_id, uid) -> list[str]
            · 按群存的队伍名单；**顺序 = 入队序**（同一份名单每次给同一个顺序）
            · 单人 / 不在队里 ⇒ 回 `[uid]` 这一个（别回空表）

      那个口不在（注入口没给 = 防御性那一支）⇒ 回 `[uid]` ⇒ 调用方走**单人那条老路**
      （一个字不变）。★ B4-18：原先这里写「今天就是这样」—— B3-25 起包内那个口**在**。
    ★ fail-closed：口在、但名单是坏的（空表 / 有空白 uid / 不含请求者自己）⇒ **当场抛**
      —— 不许悄悄退回单人（那会让「以为在组队」的人打出单人战绩）。
    """
    fn = party_members
    if fn is None:
        try:
            from . import party as _party                       # noqa: N813
        except ImportError:
            _party = None
        if _party is not None:
            fn = getattr(_party, "members_of", None)
            if not callable(fn):
                raise RuntimeError("content.party 在、但没有 members_of(group_id, uid) —— "
                                   "本包要的队伍口形状见 content/instance.members_of 的注释")
    raw = list(fn(group_id, uid)) if callable(fn) else [uid]
    out: list = []
    for x in raw:
        s = str(x or "").strip()
        if not s:
            raise ValueError("队伍名单里有空白 uid：%r" % (raw,))
        if s not in out:
            out.append(s)
    if not out:
        raise ValueError("队伍名单是空的（单人也要给 [uid]；接口形状见 members_of 注释）")
    if str(uid or "") not in out:
        raise ValueError("队伍名单里没有请求者自己：%r vs uid=%r" % (out, uid))
    return out


# ══════════════════════════════════════════════════════════════
# 三、「场」的存取（按群存的共同档）
# ══════════════════════════════════════════════════════════════
def group_of(env) -> str:
    """这一条消息是哪个群 —— 引擎 `Env.group_id`（宿主给的）。

    没群（私聊 / 没接上）⇒ 空串 ⇒ 没有「按群存的场」⇒ 一律单人老路（fail-closed）。
    """
    return str(getattr(env, "group_id", "") or "")


def load(group_id):
    """这一群现在有没有在跑的一场（None = 没有）。"""
    st = PS.group_get(SCOPE, group_id)
    if st is None:
        return None
    miss = [k for k in ST_KEYS if k not in st]
    if miss:
        raise RuntimeError("这一场的记录缺了 %s（坏记录不当成「没开过」）：%r" % (miss, sorted(st)))
    if not isinstance(st.get("battle"), dict):
        raise RuntimeError("这一场的 battle 不是一份战斗态（%r）"
                           % (type(st.get("battle")).__name__,))
    return st


def save(group_id, st) -> None:
    """把这一场写回去（整条覆盖）。"""
    PS.group_set(SCOPE, group_id, st)


def clear(group_id) -> None:
    """这一场散了（结算完 / 没人站着）—— 把记录删掉。"""
    PS.group_del(SCOPE, group_id)


# ══════════════════════════════════════════════════════════════
# 四、轮转（纯函数：谁该动 —— CTB 的自然顺序）
# ══════════════════════════════════════════════════════════════
def players_of(st) -> list:
    """这一场里玩家那一侧的**全量** actor（存活 + 倒下，按序）—— 引擎的 `sides["player"]`。"""
    sides = (st.get("battle") or {}).get("sides")
    if not isinstance(sides, dict):
        raise RuntimeError("这一场的 battle 里没有 sides（%r）" % (type(sides).__name__,))
    return [a for a in (sides.get("player") or []) if isinstance(a, dict)]


def next_actor_key(st):
    """下一个该行动的玩家 = **存活玩家中 ct 最小者**（照奥兰迪亚 `next_actor_key`）。

    `None` = 没有还站着的玩家（这一场该收了）。
    """
    best, best_t = None, None
    for a in players_of(st):
        if int(a.get("hp", 0) or 0) <= 0:
            continue
        t = float(a.get("ct", 0) or 0)
        if best_t is None or t < best_t:
            best_t, best = t, a
    return str(best.get("uid") or "") if best else None


def actor_of(st, uid):
    """这一场里某人那一格 actor（不在 / uid 为空 ⇒ None）。"""
    u = str(uid or "")
    if not u:
        return None
    for a in players_of(st):
        if str(a.get("uid") or "") == u:
            return a
    return None


def hp_of(st, uid) -> int:
    """某人在这一场里的现血（不在 ⇒ 抛 —— 要数的地方不给假数）。"""
    a = actor_of(st, uid)
    if a is None:
        raise RuntimeError("这一场里没有这个人：%r（在场的是 %r）"
                           % (uid, [x.get("uid") for x in players_of(st)]))
    return int(a.get("hp", 0) or 0)


def name_of(group_id, uid) -> str:
    """该报谁的名字 —— 读**他的档**（读不到就用库里那条兜底名，不编一个）。"""
    d = PS.get_player(group_id, uid)
    nm = str((d or {}).get("name") or "").strip()
    return nm or T("SYS_NAME_UNKNOWN")


# ══════════════════════════════════════════════════════════════
# 五、入口（只有两个：要不要走「场」 / 真走）
# ══════════════════════════════════════════════════════════════
def route_needed(env, uid) -> bool:
    """这一条战斗指令要不要走「场」那道（`False` = 今天那条单人老路，一个字不变）。

    三条判：
      · 没群 / 没 uid            ⇒ False（「按群存的场」不存在的前提）
      · 这一群有场、我在名单里    ⇒ True
      · 这一群没场、名单不止我一人 ⇒ True（这一敲就是**开场**那一敲）
      · 其余（单人、且没有场）    ⇒ False
    """
    g = group_of(env)
    u = str(uid or "")
    if not g or not u:
        return False
    st = load(g)
    if st is not None:
        return u in [str(x) for x in (st.get("members") or [])]
    return len(members_of(g, u)) > 1


async def take_turn(env, p, uid, player, *, head="", hand=None, action=None, skill=None):
    """「场」那一道的**唯一出口** —— 轮转 → 轮到我出手 → 落回场（打完就结算全队）。

    分支正好是 `17_ §四` 那五条（判断顺序也照 `cmds_instance_router.py:378-418`）：

        ① 谁该动 = 存活玩家中 ct 最小者（`next_actor_key`）
        ② 不是我 → 未超时 ⇒ 出**等待提示**收工（**一个字都不写**：档不写、场不写、不开新战斗）
                    已超时 ⇒ 替它出一手「防御」+ 日志（全队可见），再来一轮
        ⑤ 一轮最多消化 `afk_guard` 个挂机玩家（超过就 break，不再往下消化）
        ③ 轮到我 → 窗口开在我名下，我这一手真做出来
        ④ （超时那一手固定是防御 —— 保底不冒险，真源 `17_ §四④`）

    「我这一手」由调用方给（与单人那条 `_run_hand` 同一套形状）：`action`/`skill` 是引擎内置
    动作，`hand` 是 B3-23 那几手（打断 / 用物）的内容侧回调；`head` 是这一手要说的那句话。
    """
    g = group_of(env)
    u = str(uid or "")
    st = load(g)
    if st is None:
        # ── 开场：遇敌一次，把名单里每个人真拉进同一场（sides 每边是列表）
        async for line in _open(env, g, p, u):
            yield line
        st = load(g)
        if st is None:
            return                                    # 没遇敌 / 有人的档还没定职业（已出过话）
    if u not in [str(x) for x in (st.get("members") or [])]:
        raise RuntimeError("uid 不在这一场的名单里（route_needed 该先挡掉）：%r vs %r"
                           % (u, st.get("members")))
    # ── ① 轮转（照参考实现的 while / guard 逐条对应）
    guard = 0
    while True:
        guard += 1
        if guard > afk_guard():                      # ⑤ 防死循环：一轮最多消化这么多挂机的
            break
        cur = next_actor_key(st)
        if cur is None:                              # 没站着的了 ⇒ 这一场按输收（照参考实现）
            async for line in _finish(env, g, st, p, u, player, "defeat"):
                yield line
            return
        if cur == u:
            break                                    # ③ 轮到我了
        if now() - float(st.get("turn_time") or 0) > window_seconds():
            # ④ 超时 ⇒ 自动防御（日志全队可见）—— 既不惩罚也不遮掩
            _to = T("SYS_TIMEOUT_DEFEND", who=name_of(g, cur))
            ended, sub = _defend(st, cur)
            st["logs"] = list(st.get("logs") or []) + [_to] + list(sub)
            save(g, st)
            yield _to
            for line in sub:
                yield line
            if ended:
                async for line in _finish(env, g, st, p, u, player,
                                          _result_of(st) or "defeat"):
                    yield line
                return
            continue                                 # 消化掉一个，再来一轮看轮到谁
        # ② 未超时 ⇒ 等待提示，收工（★ 不动档、不动场、不开新战斗）
        yield T("SYS_ROUND_HOLD", who=name_of(g, cur))
        return
    # ── ③ 轮到我（或 ⑤ 消化到上限后按参考实现落到「轮到请求者」）
    me = actor_of(st, u)
    if me is None or int(me.get("hp", 0) or 0) <= 0:
        # 落到这一档只可能是「⑤ 消化到上限」那一次（`cur == u` 本身就意味着 u 还站着）。
        # 照参考实现：**全场没有站着的玩家**才按输收；这一场已经分出胜负就正常收尾；
        # 队友还在打 ⇒ **不替他出手**（窗口交给下一位），更不许把别人的仗判成输。
        left = next_actor_key(st)
        if left is None:
            async for line in _finish(env, g, st, p, u, player, "defeat"):
                yield line
        elif _result_of(st) is not None:
            async for line in _finish(env, g, st, p, u, player, str(_result_of(st))):
                yield line
        else:
            st["turn_time"] = int(now())
            save(g, st)
            yield T("SYS_ROUND_HOLD", who=name_of(g, left))
        return
    st["turn"] = [str(x) for x in (st.get("members") or [])].index(u)
    st["turn_time"] = int(now())                     # 窗口开在我名下（我随时可以接着敲）
    save(g, st)
    if head:
        yield head
    logs: list = []
    b = _restore(st)
    if hand is not None and getattr(hand, "override", None) is not None:
        b.action_override = hand.override            # 非内置动作的回调随恢复重挂（不可序列化）
    from ext_combat.battle import schedule as SCH

    caster = b.find_actor(u)
    if caster is None:
        raise RuntimeError("引擎那边找不到这一场里的 %r（场的名单与 sides 对不上）" % (u,))
    if hand is not None and str(getattr(hand, "kind", "")) == "item":
        caster["auto_act"] = {"act": {"type": "item", "skill": hand.item}}
    SCH.advance(b, logs)                             # 推到我的决策点（快的对方该动的先动）
    caster = b.find_actor(u) or caster
    if b.result is None and int(caster.get("hp", 0) or 0) > 0:
        if hand is not None:
            _sub, _ended, _who = b.human_act(str(hand.kind), hand.item, caster)
        else:
            _sub, _ended, _who = b.human_act(str(action), skill, caster)
        logs.extend(str(x) for x in (_sub or []))
    st["battle"] = b.to_state()
    st["logs"] = list(st.get("logs") or []) + [str(x) for x in logs]
    st["turn_time"] = int(now())                     # 窗口交到下一位手里（他从现在开始算）
    save(g, st)
    for line in _fmt(logs):
        yield line
    _write_back(env, p, player, b, u)                # 我这一手的血真落到档上（下一敲按它接着走）
    if b.result is not None:
        async for line in _finish(env, g, st, p, u, player, str(b.result)):
            yield line


# ══════════════════════════════════════════════════════════════
# 六、小件（开场 / 恢复 / 落回档 / 结算）
# ══════════════════════════════════════════════════════════════
def _member_seed(g, m, uid, p) -> dict:
    """某个人进场用的那份档（**请求者自己**那一份直用；别人的从**他的档**读 —— 读不到就抛）。

    ★ uid 一律**显式盖上去**（引擎靠 `actor.uid` 找「该谁动」与落账 —— 不许两格撞成同一个；
      也不假定宿主在档里塞过 uid）。
    """
    u = str(m)
    if u == str(uid):
        d = dict(p)
    else:
        raw = PS.get_player(g, u)
        if not isinstance(raw, dict):
            raise RuntimeError("这一场里有人的档读不到（队伍名单 %r）—— 不许把他当空气开打" % (u,))
        d = dict(raw)
    d["uid"] = u
    return d


async def _open(env, g, p, uid):
    """开场那一敲：遇敌**一次** → 名单里每个人真进同一场 → 存成「场」。

    没遇敌 / 有人的档还没定职业 ⇒ 什么都不开（fail-closed：不动档、不建场）。
    """
    from . import cmds_battle as CBAT
    from . import combat as CB
    from . import affix as AFFIX

    members = members_of(g, uid)
    pick, ms, affixes, mline = CBAT._meet(p, uid)
    if not pick:
        yield T("COMBAT_NONE")
        return
    seeds = []
    for m in members:
        d = _member_seed(g, m, uid, p)
        _mx, _line = hp_cap_or_line(d)
        if _line:
            yield _line                  # 点名「谁的档还没定职业」—— 这一场不开
            return
        seeds.append(d)
    yield mline
    for line in CBAT.encounter_lines(ms[pick[0]], p):
        yield line
    _ids, _hm = AFFIX.spawn_plan(pick[0], list(affixes))
    b = CB.build(p, _ids, ms, party=len(members), affixes=list(affixes), hp_mults=_hm,
                 players=seeds)
    save(g, {"members": list(members), "pick": list(pick), "affixes": list(affixes),
             "hp_mults": list(_hm), "party": len(members), "battle": b.to_state(),
             "logs": [], "turn": 0, "turn_time": int(now())})


def _restore(st):
    """「场」里那份战斗态 → 引擎 Battle（引擎自带的往返，面板 / ct / 待发槽 / 效果都随档走）。"""
    from ext_combat.battle import serialize as SER
    from . import battle_text as BT
    # ★ P-1：文案表**不落盘**（引擎 `from_state` 的注释明写「续战方重新传入」）——
    #   不传 ⇒ 续战那几刻的日志退回引擎兜底模板（元素那两行走不到槽位 = 静默降级）。
    return SER.from_state(dict(st.get("battle") or {}), text=BT.battle_text())


def _result_of(st):
    """这一场现在的胜负（还没分出来 → None）。"""
    return (st.get("battle") or {}).get("result")


def _defend(st, uid):
    """替某个挂机的人出一手「防御」（引擎内置动作）—— 返回 `(打完了没, 日志)`。

    ★ 口径：超时保底固定是防御（真源 `17_ §四④`「保底要简单、不冒险」）——
      本模块不认识别的保底动作，也不替玩家挑技能。
    """
    b = _restore(st)
    a = b.find_actor(uid)
    if a is None:
        raise RuntimeError("引擎那边找不到这个挂机的人：%r（场的名单与 sides 对不上）" % (uid,))
    sub, ended, _who = b.human_act("defend", None, a)
    st["battle"] = b.to_state()
    return bool(ended), [str(x) for x in (sub or [])]


def _write_back(env, p, player, b, uid) -> None:
    """把我这一手的**血**真落回档（引擎那边 actor 的现血 —— 下一敲按它接着走）。

    倒地的这一档不写 0（他的下场由结算说话：回白烛堂 / 血回满）；其余各格原样。
    ★ 「不动档」那条只对**没轮到我的那两敲**成立（等待 / 超时）；轮到我出手这一敲，
      血是这一场的真状态，必须落回，否则下一敲拿旧血续命。
    ★ 落档是处理器的责任：`player.update(p)` 只是把格盖回宿主那份 dict，
      真写库还得 `env.save()`（与单人那条 `_save(env)` 同款）。
    """
    a = b.find_actor(uid)
    if a is None:
        return
    hp = int(a.get("hp", 0) or 0)
    if hp > 0:
        p["hp"] = hp
        if player is not None:
            player.update(p)
        _save(env)


def _save(env) -> None:
    """落档（宿主回调；没给 / 抛了都不阻断回话 —— 与 `cmds_ast._save` 同款）。"""
    try:
        env.save()
    except Exception:                                        # noqa: BLE001
        pass


async def _finish(env, g, st, p, uid, player, res):
    """这一场收尾：**在场的每个人**各按单人那条结算路走一遍（钱 / 经验 / 掉落 / 死亡 / 日志），
    然后删掉这一场的记录。

    ★ 分配口径真源没写（`_notes.md` 待补行）⇒ 今天就是「每人各走一遍单人那条路」；
      `_settle` 是单人那条**唯一**的结算实现，本模块不另写一份（单一出口）。
    ★ 别人的档走包自己的存档半边（`update_player`）；请求者那一份走宿主给的 `player` 句柄
      （与单人那条完全同款）。
    """
    from . import cmds_battle as CBAT
    from . import cmds_ast as CA
    from . import codex as CX

    pick = list(st.get("pick") or [])
    if not pick:
        raise RuntimeError("这一场没有 pick（没法结算）：%r" % (sorted(st),))
    ms = CA._data("monsters")
    affixes = list(st.get("affixes") or [])
    logs = [str(x) for x in (st.get("logs") or [])]
    for m in [str(x) for x in (st.get("members") or [])]:
        if m == str(uid):
            p_m, handle = p, player
        else:
            raw = PS.get_player(g, m)
            if not isinstance(raw, dict):
                continue                             # 他这一份档不在（没他的份，不凭空造一份）
            d = dict(raw)
            d["uid"] = m
            p_m, handle = _p(d), _StoreHandle(g, m)
        seen = CX.note_kill(p_m, pick[0])
        # ★ 现血：倒地的按 **1** 落（与 `cmds_ast._p` / `player_actor` 同一条钳法）——
        #   「队伍里有人倒下了、但这一场赢了」的下场真源没写（见 `_notes.md` 待补行）。
        async for line in CBAT._settle(env, p_m, m, pick, ms, res, logs,
                                       max(1, hp_of(st, m)), seen, handle, affixes=affixes):
            yield line
    clear(g)


#: 「谁是玩家」那几列**不进档** —— 与宿主壳 `host/store_factory.py::_IDENTITY_KEYS` 同一张表
#: （档里从来就没有 uid：宿主 `save_player` 先摘掉它们才调 `update_player`）。本模块为了把
#: actor 与档对上是**自己现盖**一个 uid 上去的，落回档时按同一张表摘掉。
IDENTITY_KEYS = ("group_id", "qq_id", "uid")


class _StoreHandle:
    """别人的那一份「落档」句柄（`_settle` 只调 `update(档)`）—— 走包自己的存档半边。"""

    def __init__(self, group_id, uid):
        self._g = str(group_id or "")
        self._u = str(uid or "")

    def update(self, data):
        fields = {k: v for k, v in dict(data or {}).items() if k not in IDENTITY_KEYS}
        if not fields:
            return False
        return PS.update_player(self._g, self._u, **fields)


def _fmt(logs, limit=12):
    """日志压到一屏 —— **借单人那条的实现**（`cmds_battle._fmt`），本模块不另写一份。"""
    from . import cmds_battle as CBAT
    return CBAT._fmt(logs, limit)
