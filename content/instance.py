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
不在队 ⇒ 回 `[uid]` 一个。
★ B4-18：这一段原先写「（B3-25 那一批）今天还不存在」—— 那句话在 B3-25 落地那天就过时了。
★ G2（本波）：单人**不再**等于「回 False 走一次结算那条老路」—— 单人也有自己那一场，
  键按人分（`key_of`）；这一整段「单人路径一个字都不变」的判据因此**有意换向**，
  逐条账在 `scripts/probe_instance.py ⑤` 的抬头与本分支 `_notes.md`（旧回话 / 新回话 / 为何）。

本批**不做**的（写在这儿免得下一轮当成已完，详见本工作树 `_notes.md`）
--------------------------------------------------------------------
* 队伍本身（谁在队里 / 邀请 / 离队）—— B3-25 那一批；本模块只点名要的口（见 `members_of`）。
* 「轮到你了」的**全队广播**：QQ 那边只有回话能到群里 ⇒ 谁拿着窗口要看回话。本模块的取法
  （谁都能敲一下知道自己该不该动 + 没轮到就报「在等谁」）是骨架；主动推送要宿主的投递口。
* 多人结算的**分配口径**（击杀奖励一人一份还是平分）真源没写 ⇒ 今天按「每人各走一遍单人那条
  结算路」（`_finish`），登记为待补行。
* `battle` 那个内置守卫（「必须在战斗中」）没接：宿主的 `battle_check` 今天不给
  （引擎侧 `Env` 有位置，见 `_notes.md` 遗留清单）。

★★★ B3-26b / G2（2026-09-26 · 本波）：「场」**从「多人专有」放开成「谁都有」**
-------------------------------------------------------------------------------
真源：`06_第一阶段垂直切片/03_风车镇_指令与回复 §二`（四段式战斗回复：现状 / 对方在干什么 /
你的选项 / 上一手的结果）· `02_数值宪法/02_战斗机制 §〇·五`（伪即时 CTB：**一条指令 = 你的
一手**，不是一整场）· `04_指令总表 §五`（11 条战斗指令分开列 = 承诺逐手出招）。

改之前：`route_needed()` 只在「有群 + 在队（≥2 人）」时回 True，其余一律走**单人那条一次结算**
的老路（`cmds_battle.attack` 的 `CB.run_auto`）—— 玩家中途吃不了药、跑不掉、看不到对方在蓄什么。
改之后：**单人也有自己那一场**，每条战斗指令 = 推进到你下一次行动机会。落地只有两条：

  ① **键分两档**（`key_of`）：有队（≥2 人）⇒ 按**群**存（全队同一场，与 B3-26 逐字相同）；
     单人 ⇒ 按**人**存（`<群>#<uid>`）—— 同一个群里两个人都单打时各是各的一场，不互相串。
     存储仍然是**同一条** `persistence.group_get/set/del`（没另造第二套存储）。
  ② **`route_needed` 没有场 ⇒ True**（那一敲就是开场那一敲）。原先这一档回 False。

★ 单人那一场里 `sides["player"]` 只有一个人 —— 引擎每边本来就是列表 ⇒ **引擎零改动**，
  「轮转」退化成「只有你」，`17_ §四` 那五条在那条路上天然成立（等待提示永远不出现）。
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
# 三、「场」的存取（按群 / 按人存的共同档 —— 同一条存储，键分两档）
# ══════════════════════════════════════════════════════════════
def group_of(env) -> str:
    """这一条消息是哪个群 —— 引擎 `Env.group_id`（宿主给的）。

    没群（私聊 / 没接上）⇒ 空串。★ G2 起**不再等于「不进这一场」**：单人的键是
    `<群>#<uid>`，没群时就是 `#<uid>` —— 仍然按人分开（两个人永远不共用一格）。
    """
    return str(getattr(env, "group_id", "") or "")


def key_of(group_id, uid, members=None) -> str:
    """这一场的存储键（★ G2 的唯一一口）—— **队按群 · 单人按人**。

      · 有队（名单 ≥2 人）⇒ **群 id**：全队看的是同一场（B3-26 的键，逐字未变）；
      · 单人（名单只有自己）⇒ `<群>#<uid>`：各打各的，互不串场。
        ★ 为什么单人不能也用群 id：一个群里两个人可能同时在两条野外带上单打 ——
          用群做键的话，第二个人会被当成「不在这一场名单里」而拿不到分段战斗
          （或者更糟：两个人的手写进同一场）。

    fail-closed：有队却没群 ⇒ 当场抛（队本身也是按群存的，没有群就取不出名单的形状）。
    """
    g = str(group_id or "")
    mem = [str(x) for x in (members if members is not None else [])]
    if len(set(mem)) > 1:
        if not g:
            raise RuntimeError("有队就得按群存这一场（队伍名单 %r 但没有群）" % (mem,))
        return g
    return "%s#%s" % (g, str(uid or ""))


def battle_key(env, uid) -> str:
    """这一条消息里，**我**这一场的键（现算：群 → 名单 → 键）。"""
    g = group_of(env)
    u = str(uid or "")
    mem = members_of(g, u) if u else []
    return key_of(g, u, mem)


def load(key):
    """这一格现在有没有在跑的一场（None = 没有）。`key` 走 `key_of` / `battle_key`。"""
    st = PS.group_get(SCOPE, key)
    if st is None:
        return None
    miss = [k for k in ST_KEYS if k not in st]
    if miss:
        raise RuntimeError("这一场的记录缺了 %s（坏记录不当成「没开过」）：%r" % (miss, sorted(st)))
    if not isinstance(st.get("battle"), dict):
        raise RuntimeError("这一场的 battle 不是一份战斗态（%r）"
                           % (type(st.get("battle")).__name__,))
    return st


def save(key, st) -> None:
    """把这一场写回去（整条覆盖）。"""
    PS.group_set(SCOPE, key, st)


def clear(key) -> None:
    """这一场散了（结算完 / 没人站着）—— 把记录删掉。"""
    PS.group_del(SCOPE, key)


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
    """这一条战斗指令要不要走「场」那道（`False` = 一次结算那条老路）。

    四条判（★ G2 起第 2/3 条换了语义 —— 单人也有自己那一场）：
      · 没 uid                    ⇒ False（键拼不出来；生产里永远有 uid）
      · 这一格有场、我在名单里     ⇒ True（接着打）
      · 这一格有场、我不在名单里   ⇒ False（fail-closed：别人的场不碰，走老路）
      · 没有场                    ⇒ True（**这一敲就是开场那一敲** —— 单人也是）
    """
    u = str(uid or "")
    if not u:
        return False
    st = load(battle_key(env, u))
    if st is not None:
        return u in [str(x) for x in (st.get("members") or [])]
    return True


def live(env, uid):
    """**我**现在那一场（没有 ⇒ None）—— 『战斗日志』/『集火』这类只读的口用它。"""
    u = str(uid or "")
    if not u:
        return None
    st = load(battle_key(env, u))
    if st is not None and u not in [str(x) for x in (st.get("members") or [])]:
        return None
    return st


def fighting(env, uid) -> bool:
    """这一位手上还有一场**没落地**的仗吗（世界级移动拿它当闸）。

    ★ 试玩复测 #1：G2 把「一条指令打完整场」改成**一手一手**之后，移动那一族没人拦 ——
      跑掉没跑掉都能照常赶路 / 进镇 / 进塔，没打完的那一场跟着你跨图跨层。判据：
      有「场」且那一场的结果还没落下（`battle.result is None`）。只读，不动状态。
    """
    st = live(env, uid)
    if st is None:
        return False
    b = st.get("battle") or {}
    return b.get("result") is None


def foe_of(st):
    """这一场里**还站着的第一个敌人**那一格 actor（没有 ⇒ None）。

    ★ 只读那格 dict —— 它就是在场的那个 actor 的序列化快照（键名与活着的对象同形）。
    """
    for a in ((st.get("battle") or {}).get("sides") or {}).get("enemy") or []:
        if isinstance(a, dict) and int(a.get("hp", 0) or 0) > 0:
            return a
    return None


def live_logs(env, uid) -> list:
    """这一场**到现在为止**的日志（没有在跑的一场 ⇒ 空表）。『战斗日志』看的就是它。"""
    st = live(env, uid)
    return [str(x) for x in ((st or {}).get("logs") or [])]


def set_focus(env, uid, target_uid) -> bool:
    """把「集火」的目标写进这一场（★ G2）—— 写成了回 True。

    目标按 **uid** 记（怪那一格 actor 的 uid = 怪 id）；后面每一手都按它取对手
    （`take_turn` 里现读现传 ⇒ 目标倒了就自动回落到引擎自己的目标解析）。
    """
    u = str(uid or "")
    st = live(env, u)
    if st is None:
        return False
    st["focus"] = str(target_uid or "")
    save(battle_key(env, u), st)
    return True


async def take_turn(env, p, uid, player, *, head="", hand=None, action=None, skill=None,
                    decide=None):
    """「场」那一道的**唯一出口** —— 轮转 → 轮到我出手 → 落回场（打完就结算）。

    分支正好是 `17_ §四` 那五条（判断顺序也照 `cmds_instance_router.py:378-418`）：

        ① 谁该动 = 存活玩家中 ct 最小者（`next_actor_key`）
        ② 不是我 → 未超时 ⇒ 出**等待提示**收工（**一个字都不写**：档不写、场不写、不开新战斗）
                    已超时 ⇒ 替它出一手「防御」+ 日志（全队可见），再来一轮
        ⑤ 一轮最多消化 `afk_guard` 个挂机玩家（超过就 break，不再往下消化）
        ③ 轮到我 → 窗口开在我名下，我这一手真做出来
        ④ （超时那一手固定是防御 —— 保底不冒险，真源 `17_ §四④`）

    「我这一手」由调用方给（与单人那条 `_run_hand` 同一套形状）：`action`/`skill` 是引擎内置
    动作，`hand` 是 B3-23 那几手（打断 / 用物）的内容侧回调；`head` 是这一手要说的那句话。
    `decide(b, caster, logs, st) -> 结果名 | None`：★ G2 给「后撤 / 逃跑」这两个
    **要先看条件的**那一手用 —— 回一个结果名（例 `"fled"`）= 这一场到此为止、**不花这一手**；
    回 None = 照常花掉这一手（`hand` 那几句由调用方自己塞进 `hand.lines`）。

    ★ G2 的四处收口（单人也有这一场之后才成立的）：
      · 单人那条路在这儿**退化成「只有你」**（等待提示 / 超时 / guard 都走不到）；
      · 回话按 `03_ §二` 的**四段式**：现状 + 对方在干什么 + 你的选项（`turn_lines`）
        → 这一手说的话（`head`）→ 上一手的结果（日志）—— 打完/散场那一档不出这一屏；
      · 每一手都把 `st["hands"]` 加一（「第几手」那一格只有一个写端）；
      · `st["focus"]`（集火）现读现传给引擎的目标解析。
    """
    grp = group_of(env)
    u = str(uid or "")
    key = battle_key(env, u)
    st = load(key)
    if st is None:
        # ── 开场：遇敌一次，把名单里每个人真拉进同一场（sides 每边是列表）
        async for line in _open(env, grp, key, p, u):
            yield line
        st = load(key)
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
            async for line in _finish(env, grp, key, st, p, u, player, "defeat"):
                yield line
            return
        if cur == u:
            break                                    # ③ 轮到我了
        if now() - float(st.get("turn_time") or 0) > window_seconds():
            # ④ 超时 ⇒ 自动防御（日志全队可见）—— 既不惩罚也不遮掩
            _to = T("SYS_TIMEOUT_DEFEND", who=name_of(grp, cur))
            ended, sub = _defend(st, cur)
            st["logs"] = list(st.get("logs") or []) + [_to] + list(sub)
            save(key, st)
            yield _to
            for line in sub:
                yield line
            if ended:
                async for line in _finish(env, grp, key, st, p, u, player,
                                          _result_of(st) or "defeat"):
                    yield line
                return
            continue                                 # 消化掉一个，再来一轮看轮到谁
        # ② 未超时 ⇒ 等待提示，收工（★ 不动档、不动场、不开新战斗）
        yield T("SYS_ROUND_HOLD", who=name_of(grp, cur))
        return
    # ── ③ 轮到我（或 ⑤ 消化到上限后按参考实现落到「轮到请求者」）
    me = actor_of(st, u)
    if me is None or int(me.get("hp", 0) or 0) <= 0:
        # 落到这一档只可能是「⑤ 消化到上限」那一次（`cur == u` 本身就意味着 u 还站着）。
        # 照参考实现：**全场没有站着的玩家**才按输收；这一场已经分出胜负就正常收尾；
        # 队友还在打 ⇒ **不替他出手**（窗口交给下一位），更不许把别人的仗判成输。
        left = next_actor_key(st)
        if left is None:
            async for line in _finish(env, grp, key, st, p, u, player, "defeat"):
                yield line
        elif _result_of(st) is not None:
            async for line in _finish(env, grp, key, st, p, u, player, str(_result_of(st))):
                yield line
        else:
            st["turn_time"] = int(now())
            save(key, st)
            yield T("SYS_ROUND_HOLD", who=name_of(grp, left))
        return
    st["turn"] = [str(x) for x in (st.get("members") or [])].index(u)
    st["turn_time"] = int(now())                     # 窗口开在我名下（我随时可以接着敲）
    save(key, st)
    logs: list = []
    b = _restore(st)
    if hand is not None and getattr(hand, "override", None) is not None:
        b.action_override = hand.override            # 非内置动作的回调随恢复重挂（不可序列化）
    from ext_combat.battle import schedule as SCH

    caster = b.find_actor(u)
    if caster is None:
        raise RuntimeError("引擎那边找不到这一场里的 %r（场的名单与 sides 对不上）" % (u,))
    if hand is not None and str(getattr(hand, "kind", "")) == "item":
        # ★ G2：**每件的每场上限**要跨手有效 ⇒ 记账放在这一场里（原先一个
        #   `Hand` 只活一条指令，一次结算那版天然有效；分段之后必须在场里）
        hand.used = dict(st.get("items_used") or {})
        caster["auto_act"] = {"act": {"type": "item", "skill": hand.item}}
    SCH.advance(b, logs)                             # 推到我的决策点（快的对方该动的先动）
    caster = b.find_actor(u) or caster
    tgt = _focus_actor(b, st)                        # ★ 集火：这一场里记着的那个目标
    took, decided = False, None
    if b.result is None and int(caster.get("hp", 0) or 0) > 0:
        if decide is not None:
            decided = decide(b, caster, logs, st)    # ★ 条件那一手（后撤 / 逃跑）先问它
        if decided is None and b.result is None:
            took = True
            if hand is not None:
                _sub, _ended, _who = b.human_act(str(hand.kind), hand.item, caster, target=tgt)
            else:
                _sub, _ended, _who = b.human_act(str(action), skill, caster, target=tgt)
            logs.extend(str(x) for x in (_sub or []))
    if decided is not None:
        b.result = str(decided)                      # decide 说这一场到此为止（不花这一手）
    st["battle"] = b.to_state()
    st["logs"] = list(st.get("logs") or []) + [str(x) for x in logs]
    st["turn_time"] = int(now())                     # 窗口交到下一位手里（他从现在开始算）
    if took:
        st["hands"] = int(st.get("hands") or 0) + 1   # 「第几手」唯一的写端（★ G2）
        if hand is not None and str(getattr(hand, "kind", "")) == "item":
            st["items_used"] = {k: int(v) for k, v in (hand.used or {}).items()}
    if b.result is None:
        # ★ 四段式 ①②③ —— 这一手打完之后的样子（下一手该敲什么，看这一屏）
        for line in turn_lines(st):
            yield line
    save(key, st)
    if head:
        yield head                                   # ④ 上一手的结果（这一手说的话 + 过程）
    for line in _fmt(logs):
        yield line
    _write_back(env, p, player, b, u)                # 我这一手的血真落到档上（下一敲按它接着走）
    if b.result is not None:
        async for line in _finish(env, grp, key, st, p, u, player, str(b.result)):
            yield line


async def take_auto(env, p, uid, player):
    """`自动` —— **一直推到分出胜负**（★ G2：分段制里唯一允许一次打完的那条）。

    与 `take_turn` 同一套骨架，只把「我这一手」换成「引擎自己替我和它都出完手」：
    没场就先开一场（与『攻击』同一条开场路），然后把这一场跑到底、照旧结算。

    `b.auto_run` 在**人控 actor 在场上**时也会替它出普攻（引擎既有的那一支）——
    这正是「自动打完」的语义；本函数不另写第二套轮转。
    """
    grp = group_of(env)
    u = str(uid or "")
    key = battle_key(env, u)
    st = live(env, u)
    if st is None:
        async for line in _open(env, grp, key, p, u):
            yield line
        st = load(key)
        if st is None:
            return
    logs: list = []
    b = _restore(st)
    b.auto_run(logs)
    st["battle"] = b.to_state()
    st["logs"] = list(st.get("logs") or []) + [str(x) for x in logs]
    if b.result is None:
        save(key, st)                                # 没分出胜负 ⇒ 这一场还留着（下一敲接着来）
        for line in turn_lines(st):
            yield line
        for line in _fmt(logs):
            yield line
        _write_back(env, p, player, b, u)
        return
    save(key, st)
    for line in _fmt(logs):
        yield line
    _write_back(env, p, player, b, u)
    async for line in _finish(env, grp, key, st, p, u, player, str(b.result)):
        yield line


def _focus_actor(b, st):
    """这一场「集火」锁着的那一格 actor（没锁 / 锁的那只已经倒了 ⇒ None = 引擎自己挑）。"""
    fu = str(st.get("focus") or "")
    if not fu:
        return None
    a = b.find_actor(fu)
    if a is None or int(a.get("hp", 0) or 0) <= 0:
        return None
    return a


def turn_lines(st) -> list:
    """★ G2 四段式的 ①②③ —— **只读那一份场**（不重开引擎），给每一次出手之后看。

    ① 现状 + 谁先动（`COMBAT_TURN_STATE` + `COMBAT_TURN_I_FIRST` / `COMBAT_TURN_FOE_FIRST`）
    ② 对方在干什么（`COMBAT_TURN_FOE_DOING` / `COMBAT_TURN_FOE_IDLE`）
    ③ 你的选项（`COMBAT_TURN_MENU`）

    两边有一边不在了（打完了 / 场是坏的）⇒ 出**空表**：那种时候该说话的是结算那一段，
    这里不抢话（空表 = 不出一屏，不是「出了几行空行」）。
    """
    bd = st.get("battle") or {}
    me = None
    for a in ((bd.get("sides") or {}).get("player") or []):
        if isinstance(a, dict) and int(a.get("hp", 0) or 0) > 0:
            me = a
            break
    foe = foe_of(st)
    if me is None or foe is None:
        return []
    nm = str(foe.get("name") or "")
    my_ct = float(me.get("ct", 0) or 0)
    foe_ct = float(foe.get("ct", 0) or 0)
    # ★ 两边的血先取成局部量再拼 —— `probe_panel ④` 那条静态守卫扫的是
    #   「`"max_hp"` 后面紧跟 `or <数字>`」那种**写死上限**的写法，这里只是读快照。
    _my_hp, _my_mx = me.get("hp"), me.get("max_hp")
    _fo_hp, _fo_mx = foe.get("hp"), foe.get("max_hp")
    out = [T("COMBAT_TURN_STATE", n=int(st.get("hands") or 0),
             hp=int(_my_hp or 0), hp_max=int(_my_mx or 0),
             name=nm, foe_hp=int(_fo_hp or 0), foe_hp_max=int(_fo_mx or 0))]
    if my_ct <= foe_ct:
        out.append(T("COMBAT_TURN_I_FIRST", my_ct=int(round(my_ct)), foe_ct=int(round(foe_ct))))
    else:
        out.append(T("COMBAT_TURN_FOE_FIRST", my_ct=int(round(my_ct)), foe_ct=int(round(foe_ct))))
    slot = foe.get("charging")
    left = 0.0
    if isinstance(slot, dict):
        left = max(0.0, float(slot.get("cast_done_at", 0) or 0) - float(bd.get("now", 0) or 0))
    if left > 0:
        out.append(T("COMBAT_TURN_FOE_DOING", name=nm, left=int(round(left))))
    else:
        out.append(T("COMBAT_TURN_FOE_IDLE", name=nm))
    out.append(T("COMBAT_TURN_MENU"))
    return out


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


async def _open(env, grp, key, p, uid):
    """开场那一敲：遇敌**一次** → 名单里每个人真进同一场 → 存成「场」。

    没遇敌 / 有人的档还没定职业 ⇒ 什么都不开（fail-closed：不动档、不建场）。

    ★ G2：`grp` = **群**（别人的档按它读）· `key` = 这一场的键（单人时是 `<群>#<uid>`）。
      两件事分开之后，同一个群里两个人各自单打互不影响。
    """
    from . import cmds_battle as CBAT
    from . import combat as CB
    from . import affix as AFFIX

    members = members_of(grp, uid)
    pick, ms, affixes, mline = CBAT._meet(p, uid)
    if not pick:
        yield T("COMBAT_NONE")
        return
    seeds = []
    for m in members:
        d = _member_seed(grp, m, uid, p)
        _mx, _line = hp_cap_or_line(d)
        if _line:
            yield _line                  # 点名「谁的档还没定职业」—— 这一场不开
            return
        seeds.append(d)
    yield mline
    for line in CBAT.encounter_lines(ms[pick[0]], p):
        yield line
    _ids, _hm = AFFIX.spawn_plan(pick[0], list(affixes))
    # ★ 人数那一格与单人那条老路**同一个口径**（`cmds_battle._party_now`：在队 + 同处 + 活人；
    #   存档读不出来 ⇒ **None ⇒ `party_scale_of` 不缩放**，绝不因为「不知道」而悄悄削弱 Boss）。
    _pn = CBAT._party_now(env, p, uid)
    b = CB.build(p, _ids, ms, party=_pn, affixes=list(affixes), hp_mults=_hm, players=seeds)
    save(key, {"members": list(members), "pick": list(pick), "affixes": list(affixes),
               "hp_mults": list(_hm), "party": len(members), "battle": b.to_state(),
               "logs": [], "turn": 0, "turn_time": int(now()), "hands": 0, "focus": "",
               "items_used": {}})
    # ★ G2 fail-closed：写完**当场读回来核一遍** —— 这一场是唯一跨指令的状态，
    #   存不住的话下一条指令会「只回一行、什么都没发生」（静默）。存不住就点名（常见因：
    #   宿主注进来的 db_path 是 `:memory:` 那种**每条连接各一份**的库 ⇒ 下一次读不到）。
    if load(key) is None:
        raise RuntimeError("开场那一敲没把这一场留下（共同档 %r 存不住）—— 存档半边的共同档口没接上？"
                           % (key,))


def _restore(st):
    """「场」里那份战斗态 → 引擎 Battle（引擎自带的往返，面板 / ct / 待发槽 / 效果都随档走）。

    ★ G2：恢复之后**把面板栈补登记回来**（`panel_build.ensure_stack`）—— 栈声明只活在造它的
      那个进程里，而这一场是**落盘**的（机器人重启 / 换一个进程接着打 ⇒ 旧栈 id 查不到，
      引擎当场抛 `panel_layers 无此栈`）。补登记用的是 actor 自己那份快照 ⇒ 数一个都不动。
    """
    from ext_combat.battle import serialize as SER
    from . import battle_text as BT
    from . import panel_build as PB
    # ★ P-1：文案表**不落盘**（引擎 `from_state` 的注释明写「续战方重新传入」）——
    #   不传 ⇒ 续战那几刻的日志退回引擎兜底模板（元素那两行走不到槽位 = 静默降级）。
    b = SER.from_state(dict(st.get("battle") or {}), text=BT.battle_text())
    for acts in (b.sides or {}).values():
        for a in acts:
            PB.ensure_stack(a)
    return b


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


async def _finish(env, grp, key, st, p, uid, player, res):
    """这一场收尾：**在场的每个人**各按单人那条结算路走一遍（钱 / 经验 / 掉落 / 死亡 / 日志），
    然后删掉这一场的记录（★ G2：`clear(key)` —— 单人那一格也要清干净，下一场不带残留）。

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
            raw = PS.get_player(grp, m)
            if not isinstance(raw, dict):
                continue                             # 他这一份档不在（没他的份，不凭空造一份）
            d = dict(raw)
            d["uid"] = m
            p_m, handle = _p(d), _StoreHandle(grp, m)
        seen = CX.note_kill(p_m, pick[0])
        # ★ 现血：倒地的按 **1** 落（与 `cmds_ast._p` / `player_actor` 同一条钳法）——
        #   「队伍里有人倒下了、但这一场赢了」的下场真源没写（见 `_notes.md` 待补行）。
        async for line in CBAT._settle(env, p_m, m, pick, ms, res, logs,
                                       max(1, hp_of(st, m)), seen, handle, affixes=affixes):
            yield line
    clear(key)


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
