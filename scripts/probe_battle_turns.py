# -*- coding: utf-8 -*-
r"""探针：战斗的**分段推进**（★ G2 · B3-26b）—— 一手一推进 · 中途吃药 · 逃跑两态 · 清场 · 反证。

真源（改这一批的依据，全部只读）
--------------------------------
* `06_第一阶段垂直切片/04_指令总表.md §五`（11 条战斗指令**分开列** = 承诺逐手出招）
* `06_第一阶段垂直切片/03_风车镇_指令与回复.md §二`（**四段式**战斗回复：现状 / 对方在干什么 /
  你的选项 / 上一手的结果 —— 那一屏要「一场战斗跨多条指令」的持久状态）
* `02_数值宪法/02_战斗机制.md §〇·五`（伪即时 CTB：`ct` = 绝对时刻、1 刻 = 1 游戏秒、
  一条指令 = **你的一个行动机会**，不是一整场；禁用词「回合」）
* `06_第一阶段垂直切片/17_组队与策略配合_v1.md §四`（轮转 / 输入窗口 —— 多人那一层，B3-26 已落）

判据（全部**真跑**：真宿主管道 + 真存档库 + 真敲指令）
------------------------------------------------------
  ① ★ 一手一推进：反复敲 `攻击` 能把**同一场**分多次打完（每一敲都回你手里）
     —— 两态对照（**反证在 ⑥**：把分段化拆掉 ⇒ 这一条必须红）
  ② ★ 中途能喝药：真扣药、真回血、真花掉这一手；同一场上限用满 ⇒ 回落普攻且**不再扣药**
  ③ ★ `自动` 仍能**一次打完**（分段制里唯一允许一条指令打到底的那条）
  ④ ★ `逃跑` 失败率两态：探针**自己现算种子**（不调被测函数）并排核 + 同一场里再敲会**重掷**
  ⑤ ★ 打完 / 死完：这一场的**状态清干净**（下一场不带残留：第 1 手 · 怪满血 · 手数从 1 起）
  ⑥ ★ 反证：把 `instance.route_needed` 拆掉（回到一次结算）⇒ ① 与本探针的分段读法**当场红**
  ⑦ 其余几条真接上：`防御`（真花一手 + 后摇短）· `打断`（清掉对方待发 + 推后到点时刻）·
     `后撤` 两态 · `换武器`（档上真换 + 场里面板当场重挂）· `集火`（锁目标 + 不吃行动）·
     `战斗日志`（看在打的那一场 + 分页）· `使用` 非药（照实说、不消耗）
  ⑧ fail-closed：没得打的地方那五条说**同一句**（`COMBAT_NEED_FOE`）· 两个单人互不串场
  ⑨ ★ fix-j：**集火锁的是敌人 ⇒ 只有「攻击那一档」吃它** —— 治疗 / 增益不吃
     （改前：`集火 <怪>` 之后敲 `技能 安神曲` 把那一发的治疗量**整份**加到那只敌人身上，
     而屏上印「圣光治愈了你 N 点生命」= 修女核心机制反向，第 2 轮真人试玩 8 批逐条复现）。
     分档：技能按域里 `kind_override`（治疗 / 增益不吃，伤害三通道吃）· 内置动作只有 `attack` ·
     内容侧那几手只有 `interrupt`（用物只为它**上限用满回落成普攻**那一手）。

跑法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_battle_turns.py
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
TMP = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp")
sys.path.insert(0, str(REPO))
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402

ok = True


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("OK " if cond else "X  ", label,
                         ("  —— %s" % str(extra)) if extra != "" else ""))


# ══════════════════════════════════════════════════════════════
# 夹具：真宿主契约 + 真存档库（与 probe_instance 同源）
# ══════════════════════════════════════════════════════════════
def _fresh(name) -> str:
    p = os.path.join(TMP, "ast_probe_turns_%s.db" % name)
    try:
        os.remove(p)
    except OSError:
        pass
    return p


class _Clock:
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


class _E(object):
    """只读口要的最小 env（`group_of` 读 group_id）。"""

    def __init__(self, gid):
        self.group_id = str(gid)


SEED = {"name": "分段", "cls": "cls_knight", "race": "human", "level": 7, "exp": 0,
        "gold": 30, "bag": {"i_potion_minor": 3}, "equipped": {}, "codex": {}, "flags": {},
        "prev": [], "loc": "belt_north", "node": "bn_bone"}

MID = "ms_field_mouse"          # 田鼠：hp 66 · 普通档（几手之内打得完，读数稳）
LOC, NODE = "belt_north", "bn_bone"


def _boot(db, gid, clock=None):
    from saintess_engine.host.runtime import Host
    from content import persistence as PS
    inject = {"db_path": db, "clock": clock or time.time}
    h = Host(_Ad(gid), str(REPO), inject=inject)
    h.boot()
    if clock is not None:
        PS.bind(clock=clock)
    return h, h.adapter


def _seed(gid, uid, **kw):
    from content import cmds_ast as CA
    from content import panel_build as PB
    from content import persistence as PS
    d = dict(CA.DEFAULT_PLAYER)
    d.update(SEED)
    d.update(kw)
    cap = PB.hp_cap(d)
    d["hp"] = int(kw.get("hp") or cap)
    d.pop("hp_max", None)
    PS.update_player(gid, uid, **d)
    return d


def _drive(host, ad, uid, text):
    ad.out.clear()
    host.handle({"uid": uid, "group_id": ad.gid, "text": text})
    return [str(x) for x in ad.out]


def _pin(monster=MID, affixes=None):
    """把遇敌钉死（战斗内部抽怪 ⇒ 不钉住不可复现）。"""
    from content import combat as CB
    from content import affix as AFFIX
    real = (CB.pick_encounter, AFFIX.elite_of)
    CB.pick_encounter = (lambda *a, **k: [monster]) if monster else (lambda *a, **k: [])
    if affixes is None:
        AFFIX.elite_of = lambda *a, **k: None
    else:
        AFFIX.elite_of = lambda *a, **k: (monster, list(affixes))
    return real


def _unpin(saved):
    from content import combat as CB
    from content import affix as AFFIX
    CB.pick_encounter, AFFIX.elite_of = saved


MON = None
TX = None


def slot(key, **kw):
    s = (TX.get(key) or {}).get("value", "")
    for k, v in kw.items():
        s = s.replace("{%s}" % k, str(v))
    return s


def _pre(key):
    """某个槽位渲染出来的**字面前缀**（第一个占位之前那一段）—— 用来认「这一行在不在」。"""
    return slot(key).split("{")[0]


def _has(lines, key):
    p = _pre(key)
    return any(str(x).startswith(p) for x in lines)


def main():
    global MON, TX
    st = load_stack(str(REPO), inject={"db_path": _fresh("stack"), "clock": time.time})
    st.install()
    MON = st.domain("monsters") or {}
    TX = st.domain("texts") or {}

    from content import cmds_battle as CBAT                          # noqa: E402
    from content import combat as CB                                 # noqa: E402
    from content import instance as INST                             # noqa: E402
    from content import pager as PG                                  # noqa: E402
    from content import persistence as PS                            # noqa: E402

    print("探针：战斗的分段推进（★ G2）")

    # ── ① 一手一推进（+ 反证读法两态）──────────────────────────────
    print()
    print("① 一手一推进 —— 反复敲 `攻击` 把**同一场**分多次打完（每一敲回你手里）")
    db = _fresh("turn")
    host, ad = _boot(db, "g_turn")
    _seed("g_turn", "u_a")
    env = _E("g_turn")
    saved = _pin()
    n_press = 0
    hands_seen = []
    mid_ok, end_ok = True, False
    try:
        random.seed(20260926)
        o1 = _drive(host, ad, "u_a", "攻击")
        s1 = INST.live(env, "u_a")
        chk("★ 开场那一敲：遇敌那一行 + 四段式那一屏（现状 / 谁先动 / 对方在干什么 / 你的选项）",
            _has(o1, "COMBAT_MEET") and _has(o1, "COMBAT_TURN_STATE")
            and _has(o1, "COMBAT_TURN_FOE_IDLE") and slot("COMBAT_TURN_MENU") in o1, o1[:3])
        #: ★ 2026-09-27（夜班试玩 w3 · mage 的 c1 与 p3 两条都报）：战斗屏原先只有血 ——
        #:   法师的两条命根子（法力 / 印记）在打的时候一条都看不见。本波在血那一行后面补了
        #:   两条读数（`COMBAT_TURN_MP` + `COMBAT_TURN_RES`），这里把「在不在」与「数对不对」
        #:   都钉住：**逐字**比 actor 上那两格（法力 = `mp`/`max_mp`；资源 = `resources.json`
        #:   声明的那个码在 `effects[码].stacks` 的层数）。
        _a1 = INST.actor_of(s1, "u_a") if s1 is not None else None
        from content import resources as _RES                            # noqa: E402

        _code = next((k for k in sorted(_RES.resources())
                      if k in ((_a1 or {}).get("effects") or {})), "")
        _stk = int((((_a1 or {}).get("effects") or {}).get(_code) or {}).get("stacks") or 0)
        chk("★ 战斗屏带资源读数（法力那一格 + 职业资源那一格 —— 只读 actor 现成的两格）：%s"
            % [str(x) for x in o1 if "法力" in str(x) or "🔹" in str(x)][:2],
            _has(o1, "COMBAT_TURN_MP") and _has(o1, "COMBAT_TURN_RES"), o1[:5])
        chk("★ 那两行报的数**逐字** = actor 上那两格（法力 %s/%s · %s %s 层）"
            % ((_a1 or {}).get("mp"), (_a1 or {}).get("max_mp"), _code, _stk),
            _a1 is not None and _code
            and slot("COMBAT_TURN_MP", mp=int(_a1.get("mp") or 0),
                     mp_max=int(_a1.get("max_mp") or 0)) in o1
            and slot("COMBAT_TURN_RES", name=_RES.of(_code).get("name"), n=_stk,
                     mx=int(_RES.max_of(_code))) in o1,
            None if _a1 is None else (_a1.get("mp"), _a1.get("max_mp")))
        chk("★ 这一敲**没打完**（场还在 · 引擎那边 result 还是 None · 手数 1）",
            s1 is not None and (s1.get("battle") or {}).get("result") is None
            and int(s1.get("hands") or 0) == 1,
            None if s1 is None else (s1.get("hands"), (s1.get("battle") or {}).get("result")))
        chk("★ 双方都真出了手（这一段日志 ≥3 行：你这一手 + 对方那一手）",
            s1 is not None and len(s1.get("logs") or []) >= 3,
            None if s1 is None else len(s1["logs"]))
        n_press = 1
        hands_seen.append(int(s1.get("hands") or 0))
        while n_press < 40:
            o = _drive(host, ad, "u_a", "攻击")
            n_press += 1
            s = INST.live(env, "u_a")
            if s is None:
                end_ok = _has(o, "COMBAT_DONE")
                break
            hands_seen.append(int(s.get("hands") or 0))
            if int(s.get("hands") or 0) <= n_press - 2:
                mid_ok = False
        chk("★ 反复敲 `攻击` 把**同一场**分 %d 次打完（%s —— 一次结算那种必是 1）"
            % (n_press, "、".join(str(h) for h in hands_seen)), 3 <= n_press <= 20 and mid_ok)
        chk("★ 最后一敲才是结算（`✔ 打完了` 那一屏）", end_ok)
        chk("★ 打完之后场**清干净**（`instance.live` = None）", INST.live(env, "u_a") is None)
        far = INST.battle_key(env, "u_a")
        chk("★ 那一格存储也真删了（共同档里查不到）", PS.group_get(INST.SCOPE, far) is None, far)
    finally:
        _unpin(saved)

    # ── ② 中途能喝药 ─────────────────────────────────────────────
    print()
    print("② 中途能喝药 —— 真扣药 · 真回血 · 真花掉这一手（每场上限用满 ⇒ 回落普攻且不扣药）")
    db = _fresh("pill")
    host, ad = _boot(db, "g_pill")
    _seed("g_pill", "u_p", bag={"i_potion_minor": 2})
    env = _E("g_pill")
    saved = _pin()
    try:
        random.seed(20260926)
        _drive(host, ad, "u_p", "攻击")
        _drive(host, ad, "u_p", "攻击")
        s0 = INST.live(env, "u_p")
        hp0 = int(INST.actor_of(s0, "u_p").get("hp") or 0)
        bag0 = dict((PS.get_player("g_pill", "u_p") or {}).get("bag") or {})
        h0 = int(s0.get("hands") or 0)
        random.seed(20260926)
        o = _drive(host, ad, "u_p", "使用 伤药")
        s1 = INST.live(env, "u_p")
        hp1 = int(INST.actor_of(s1, "u_p").get("hp") or 0)
        bag1 = dict((PS.get_player("g_pill", "u_p") or {}).get("bag") or {})
        chk("★ 战斗里敲 `使用 伤药` ⇒ 真回血那一行（%s）" % slot("SYS_USE_HEAL", name="伤药",
                                                                heal="?", hp="?", hp_max="?")[:14],
            _has(o, "SYS_USE_HEAL"), o[-3:])
        chk("★ 血真涨了（%d → %d）" % (hp0, hp1), hp1 > hp0)
        chk("★ 药真扣了一瓶（%s → %s）"
            % (bag0.get("i_potion_minor"), bag1.get("i_potion_minor")),
            int(bag1.get("i_potion_minor") or 0) == int(bag0.get("i_potion_minor") or 0) - 1)
        chk("★ 这一手真花掉了（手数 %d → %d）—— 吃药不是白吃" % (h0, int(s1.get("hands") or 0)),
            int(s1.get("hands") or 0) == h0 + 1)
        # 同一场再喝一次 ⇒ 每场上限（`item_uses_per_battle`）⇒ 回落普攻、**不再扣药**
        bag2_0 = dict((PS.get_player("g_pill", "u_p") or {}).get("bag") or {})
        random.seed(20260926)
        o2 = _drive(host, ad, "u_p", "使用 伤药")
        bag2 = dict((PS.get_player("g_pill", "u_p") or {}).get("bag") or {})
        chk("★ 同一场第 2 瓶 ⇒ 照实说「这一场用过了」（`COMBAT_ITEM_CAP`）+ **不再扣药**",
            _has(o2, "COMBAT_ITEM_CAP")
            and int(bag2.get("i_potion_minor") or 0) == int(bag2_0.get("i_potion_minor") or 0),
            o2[-3:])
    finally:
        _unpin(saved)

    # ── ③ 自动仍能一次打完 ────────────────────────────────────────
    print()
    print("③ `自动` 仍能**一次打完**（分段制里唯一允许一条指令打到底的那条）")
    db = _fresh("auto")
    host, ad = _boot(db, "g_auto")
    _seed("g_auto", "u_z")
    env = _E("g_auto")
    saved = _pin()
    try:
        random.seed(20260926)
        g0 = int((PS.get_player("g_auto", "u_z") or {}).get("gold") or 0)
        o = _drive(host, ad, "u_z", "自动")
        g1 = int((PS.get_player("g_auto", "u_z") or {}).get("gold") or 0)
        chk("★ 一条 `自动` ⇒ 这一场真打完（场清干净 + `✔ 打完了` + 钱真涨）",
            INST.live(env, "u_z") is None and _has(o, "COMBAT_DONE") and g1 > g0,
            (g0, g1))
    finally:
        _unpin(saved)

    # ── ③b ★ fxe（修 e·道具使用）：道具那一手本身的两档 ───────────────────────
    #   真源两份（只读）：`06_第一阶段垂直切片/04_指令总表 §五`（药与道具 · 一场每件一次）·
    #   `02_数值宪法/02_战斗机制 §〇·五`（一条指令 = 你的一个行动机会 —— 所以「不吃」也要说话）。
    #   ★ 两档都是**真宿主真敲**跑出来的；只有「活体 actor 此刻多少血」这一格是夹具摆的
    #     （`INST.save` 写回这一场 · 明写在这儿，不藏）：要的就是「满血」与「挂彩」两个**确定**状态。
    #   ① 满血敲 `使用 <药>` ⇒ 一句实话 + 药一瓶不动 + 这一手**回落普攻**（不白花）
    #   ② 挂彩敲 `使用 <药>` ⇒ 真回血、药真扣；**接着敲 `自动`**：引擎那条
    #      「未知行动类型」一个字都不许出（改前实跑：玩家一手都不出、被活活打完）、
    #      我方每手真出招、这一场真打完；且这一场里玩家 actor 的 `auto_act` 只能是**引擎内置动作**。
    print()
    print("③b 道具那一手：满血**不吃**（回落普攻）· 用过之后敲 `自动` 我方照样每手出招")
    db = _fresh("pill2")
    host, ad = _boot(db, "g_pill2")
    _seed("g_pill2", "u_q")
    env = _E("g_pill2")
    saved = _pin()

    def _foe_hp(state):
        """这一场敌方还剩多少血（读场里那份战斗态 —— 只读，不改）。"""
        _b = (state or {}).get("battle") or {}
        return sum(int((x or {}).get("hp") or 0)
                   for x in (((_b.get("sides") or {}).get("enemy")) or []))

    def _bag(gid, uid, iid):
        return int(((PS.get_player(gid, uid) or {}).get("bag") or {}).get(iid) or 0)

    try:
        random.seed(20260926)
        _drive(host, ad, "u_q", "攻击")
        _key = INST.battle_key(env, "u_q")
        _s = INST.live(env, "u_q")
        _a = INST.actor_of(_s, "u_q")
        _mx = int(_a.get("max_hp") or 0)
        # ① 满血那一档
        _a["hp"] = _mx
        INST.save(_key, _s)
        _b0 = _bag("g_pill2", "u_q", "i_potion_minor")
        _f0 = _foe_hp(_s)
        random.seed(20260926)
        _o_full = _drive(host, ad, "u_q", "使用 伤药")
        _s1 = INST.live(env, "u_q")
        _b1 = _bag("g_pill2", "u_q", "i_potion_minor")
        chk("★ 满血（%d/%d）敲 `使用 伤药` ⇒ 照实说「%s」+ **药一瓶不动**（%d → %d）· "
            "账上一件都没用掉（%s）"
            % (_mx, _mx, slot("SYS_USE_FULL")[:12], _b0, _b1, (INST.live(env, "u_q") or {}).get("items_used")),
            _has(_o_full, "SYS_USE_FULL")
            and _b1 == _b0
            and not ((_s1 or {}).get("items_used") or {}).get("i_potion_minor"),
            _o_full[-4:])
        chk("★ 这一手**不白花**：照「上限用满」那一支的形状回落成普攻（对面这一手真掉血 %s → %s）"
            % (_f0, _foe_hp(_s1)),
            _foe_hp(_s1) < _f0,
            None if _s1 is None else (_s1.get("hands"), _s1.get("items_used")))
        # ② 挂彩那一档 + 接着 `自动`
        _s2 = INST.live(env, "u_q")
        _a2 = INST.actor_of(_s2, "u_q")
        _a2["hp"] = max(1, _mx - 30)
        INST.save(_key, _s2)
        _b2 = _bag("g_pill2", "u_q", "i_potion_minor")
        random.seed(20260926)
        _o_use = _drive(host, ad, "u_q", "使用 伤药")
        _s3 = INST.live(env, "u_q")
        _b3 = _bag("g_pill2", "u_q", "i_potion_minor")
        chk("★ 挂彩（上限 −30）敲 `使用 伤药` ⇒ 真回血那一行 + 药真扣（%d → %d）"
            % (_b2, _b3),
            _has(_o_use, "SYS_USE_HEAL") and _b3 == _b2 - 1, _o_use[-3:])
        _aa = ((INST.actor_of(_s3, "u_q") or {}).get("auto_act") or {}).get("act") or {}
        chk("★ 这一场里玩家 actor 的 `auto_act` 只能是引擎内置动作（attack/skill/defend/flee）"
            "—— 内容侧动作（如 `item`）在**从场里恢复出来的**那一场 Battle 上没有 "
            "`action_override`（不可序列化）⇒ 引擎只会回「未知行动类型」、玩家一手都不出",
            str(_aa.get("type")) in ("attack", "skill", "defend", "flee"), _aa)
        random.seed(20260926)
        _o_auto = _drive(host, ad, "u_q", "自动")
        _foe_name = str((MON[MID] or {}).get("name") or MID)
        _hits = [ln for ln in _o_auto if _foe_name in str(ln) and "受到" in str(ln)]
        chk("★ 用过道具之后敲 `自动`：引擎那条 `battle.core.unknown_action`（「未知行动类型」）"
            "**一个字都不许出**（改前：每手一条、我方零动作）",
            not [ln for ln in _o_auto if "未知行动类型" in str(ln)],
            [str(ln) for ln in _o_auto if "未知行动类型" in str(ln)][:2])
        chk("★ 我方每手真有动作（对面挨了 %d 下）· 这一场真打完（`✔ 打完了`）· 场清干净"
            % len(_hits),
            _hits and _has(_o_auto, "COMBAT_DONE") and INST.live(env, "u_q") is None,
            _o_auto[-4:])
    finally:
        _unpin(saved)

    # ── ④ 逃跑两态 + 同一场重掷 ──────────────────────────────────
    print()
    print("④ `逃跑` 失败率两态（探针自己现算种子）+ 同一场里再敲会**重掷**")
    from content import battle_acts as BA                            # noqa: E402
    from content import calendar as CAL                              # noqa: E402
    rate = float(BA.flee_fail_pct())
    day = int((CAL.state() or {}).get("game_day") or 0)

    def _roll(uid, nth=0):
        """探针**自己**拼种子（不调 `cmds_battle._flee_roll`）—— 与生产端各写各的。

        ★ 手气那一格的方向（P-57 原文）：`roll < 失败率` ⇒ **被拦下**（三成那一档）；
          `roll ≥ 失败率` ⇒ **跑成**。这里就按这个方向分两档（下面两态各真跑一次）。
        """
        seed = "%s:flee:%s:%s:%s:%d" % (uid, MID, LOC, NODE, day)
        if nth:
            seed += ":%d" % int(nth)
        return random.Random(seed).random()

    uids = ["u_f%02d" % i for i in range(40)]
    miss = [u for u in uids if _roll(u) < rate]            # 被拦下那一档
    hit = [u for u in uids if _roll(u) >= rate]            # 跑成那一档
    chk("★ 两态的候选都真找到了（拦下 %d 个 / 跑成 %d 个 · 失败率 %.2f）"
        % (len(miss), len(hit), rate), bool(miss) and bool(hit))
    db = _fresh("flee")
    host, ad = _boot(db, "g_flee")
    for u in (miss[0], hit[0]):
        _seed("g_flee", u)
    env = _E("g_flee")
    saved = _pin()
    try:
        random.seed(20260926)
        for u, want in ((miss[0], "block"), (hit[0], "ok")):
            random.seed(20260926)
            o = _drive(host, ad, u, "逃跑")
            s = INST.live(env, u)
            if want == "block":
                chk("★ 掷败那个（%s：手气 %.3f < %.2f）⇒ 被拦下 · 这一手白花 · **这一场照打**"
                    % (u, _roll(u), rate),
                    _has(o, "COMBAT_FLEE_BLOCK") and s is not None
                    and int(s.get("hands") or 0) == 1 and int(s.get("flee_tries") or 0) == 1, o[:3])
            else:
                g0 = int((PS.get_player("g_flee", u) or {}).get("gold") or 0)
                chk("★ 掷成那个（%s：手气 %.3f ≥ %.2f）⇒ 脱离 · 这一场**没打** · 场清干净"
                    % (u, _roll(u), rate),
                    _has(o, "COMBAT_FLEE_OK") and s is None
                    and int((PS.get_player("g_flee", u) or {}).get("gold") or 0) == g0, o[:3])
        # 同一场重掷：找一个 nth=0 被拦下、nth=1 跑得掉的号（现算，不手写）
        both = [u for u in uids if _roll(u) < rate and _roll(u, 1) >= rate]
        chk("★ 找到「第一次被拦下、第二次跑得掉」的号（%s）" % (both[:1] or "（无）"), bool(both))
        if both:
            u = both[0]
            PS.group_del(INST.SCOPE, INST.battle_key(env, u))
            _seed("g_flee", u)
            random.seed(20260926)
            oa = _drive(host, ad, u, "逃跑")
            ob = _drive(host, ad, u, "逃跑")
            chk("★ 同一场连敲两次 `逃跑`：第一次拦住（种子 = P-57 那颗）· 第二次**重掷**并跑掉"
                "（手气 %.3f → %.3f）" % (_roll(u), _roll(u, 1)),
                _has(oa, "COMBAT_FLEE_BLOCK") and _has(ob, "COMBAT_FLEE_OK")
                and INST.live(env, u) is None, (oa[:1], ob[:1]))
    finally:
        _unpin(saved)

    # ── ⑤ 打完 / 死完：状态清干净 · 下一场不带残留 ─────────────────
    print()
    print("⑤ 打完 / 死完：这一场的状态清干净（下一场第 1 手 · 怪满血 · 手数从 1 起）")
    db = _fresh("clean")
    host, ad = _boot(db, "g_cl")
    _seed("g_cl", "u_c")
    env = _E("g_cl")
    saved = _pin()
    try:
        random.seed(20260926)
        _drive(host, ad, "u_c", "自动")                     # 一：打完一场
        chk("★ 打完 ⇒ 场清干净", INST.live(env, "u_c") is None)
        random.seed(20260926)
        o2 = _drive(host, ad, "u_c", "防御")                # 二：下一场（防御不出伤 ⇒ 怪还是满血）
        s2 = INST.live(env, "u_c")
        foe = INST.foe_of(s2) if s2 else None
        chk("★ 下一场**不带残留**（场是新开的：第 1 手 · 日志只有这一敲那几行 · 怪满血 "
            "· 集火/逃跑/用物的记账都空）",
            s2 is not None and int(s2.get("hands") or 0) == 1
            and INST.foe_of(s2) is not None and int(foe.get("hp") or 0) == int(foe.get("max_hp") or 0)
            and len(s2.get("logs") or []) <= 8 and not (s2.get("focus") or "")
            and not (s2.get("flee_tries") or 0) and not (s2.get("items_used") or {}),
            None if s2 is None else (s2.get("hands"), len(s2.get("logs") or []),
                                     foe.get("hp"), foe.get("max_hp")))
    finally:
        _unpin(saved)
    # 死完那一档：血只给 1 点（对方一落手就倒）
    db = _fresh("die")
    host, ad = _boot(db, "g_die")
    _seed("g_die", "u_d", hp=1)
    env = _E("g_die")
    saved = _pin()
    try:
        random.seed(20260926)
        o = _drive(host, ad, "u_d", "攻击")
        p_d = PS.get_player("g_die", "u_d") or {}
        from content import cmds_ast as CA                          # noqa: E402
        _at_chapel = (str(p_d.get("loc") or "") == str(CA.CHAPEL[0])
                      and str(p_d.get("node") or "") == str(CA.CHAPEL[1]))
        chk("★ 倒地 ⇒ 回白烛堂 · 血回满（%s/%s）· 场清干净"
            % (p_d.get("hp"), CA.hp_cap(p_d)),
            _has(o, "SYS_DEATH_WILD") and INST.live(env, "u_d") is None
            and _at_chapel and int(p_d.get("hp") or 0) == int(CA.hp_cap(p_d)),
            (o[-3:], (p_d.get("loc"), p_d.get("node"))))
    finally:
        _unpin(saved)

    # ── ⑥ 反证：拆掉分段化 ⇒ ① 的两条读法当场红 ────────────────────
    print()
    print("⑥ 反证：把分段化拆掉（回到「一条指令一次结算」）⇒ ① 的判据必须红")
    db = _fresh("neg")
    host, ad = _boot(db, "g_neg")
    _seed("g_neg", "u_n")
    env = _E("g_neg")
    saved = _pin()
    real_route = INST.route_needed
    INST.route_needed = lambda env2, uid: False          # ★ 病根：这一步就是「不分段」
    try:
        random.seed(20260926)
        o = _drive(host, ad, "u_n", "攻击")
        s = INST.live(env, "u_n")
        seg_holds = (s is not None) and ((s.get("battle") or {}).get("result") is None)
        one_shot = _has(o, "COMBAT_DONE")
        chk("★ 拆掉之后**一敲就打完**（①-甲当场不成立：`✔ 打完了` 就在第一敲里）", one_shot, o[-3:])
        chk("★ 拆掉之后**没有场**（①-乙当场不成立：`instance.live` = None）", s is None)
        chk("★ 两态对照齐了：分段版「第一敲之后 result 还是 None」= %s ⇒ 拆掉版 = %s"
            % (True, seg_holds), seg_holds is False)
    finally:
        INST.route_needed = real_route
        _unpin(saved)
    # 装回来之后再真跑一次 —— 分段那一档立刻回来（说明上面那条反证不是「探针坏了」）
    db = _fresh("neg2")
    host, ad = _boot(db, "g_neg2")
    _seed("g_neg2", "u_n2")
    env = _E("g_neg2")
    saved = _pin()
    try:
        random.seed(20260926)
        o = _drive(host, ad, "u_n2", "攻击")
        chk("★ 装回来（`route_needed` 复原）⇒ 第一敲又**不**打完了（场在 · 没结算）",
            INST.live(env, "u_n2") is not None and not _has(o, "COMBAT_DONE"))
    finally:
        _unpin(saved)

    # ── ⑦ 其余几条真接上 ─────────────────────────────────────────
    print()
    print("⑦ 其余几条真接上：防御 / 打断 / 后撤两态 / 换武器 / 集火 / 战斗日志分页 / 使用非药")
    # 甲 · 防御真花一手 + 后摇短（到点时刻推进得比普攻少）—— 两态对照
    db = _fresh("def")
    host, ad = _boot(db, "g_def")
    _seed("g_def", "u_k")
    _seed("g_def", "u_d2")
    env = _E("g_def")
    saved = _pin()
    try:
        random.seed(20260926)
        _drive(host, ad, "u_k", "攻击")
        ct_k0 = float(INST.actor_of(INST.live(env, "u_k"), "u_k").get("ct") or 0)
        random.seed(20260926)
        _drive(host, ad, "u_k", "防御")
        ct_k1 = float(INST.actor_of(INST.live(env, "u_k"), "u_k").get("ct") or 0)
        random.seed(20260926)
        _drive(host, ad, "u_d2", "攻击")
        ct_a0 = float(INST.actor_of(INST.live(env, "u_d2"), "u_d2").get("ct") or 0)
        random.seed(20260926)
        _drive(host, ad, "u_d2", "攻击")
        ct_a1 = float(INST.actor_of(INST.live(env, "u_d2"), "u_d2").get("ct") or 0)
        chk("★ `防御` 真花掉一手，而且**后摇短**（推进 %s 刻 < 普攻那一手的 %s 刻）"
            % (round(ct_k1 - ct_k0, 1), round(ct_a1 - ct_a0, 1)),
            0 < (ct_k1 - ct_k0) < (ct_a1 - ct_a0))
    finally:
        _unpin(saved)
    # 乙 · 打断：先用一手 `防御`（后摇短）把自己落到对方**出招窗口**里 ⇒ 断成 + 清掉待发
    db = _fresh("int")
    host, ad = _boot(db, "g_int")
    _seed("g_int", "u_i")
    env = _E("g_int")
    saved = _pin()
    try:
        random.seed(20260926)
        _drive(host, ad, "u_i", "攻击")
        _drive(host, ad, "u_i", "防御")
        s0 = INST.live(env, "u_i")
        foe0 = INST.foe_of(s0)
        charging = isinstance((foe0 or {}).get("charging"), dict)
        ct0 = float((foe0 or {}).get("ct") or 0)
        chk("★ 前提：这一敲真落在对方**出招窗口**里（它正押着一手）", charging,
            None if not foe0 else (foe0.get("name"), foe0.get("charging")))
        random.seed(20260926)
        o = _drive(host, ad, "u_i", "打断")
        s1 = INST.live(env, "u_i")
        foe1 = INST.foe_of(s1)
        chk("★ `打断` 真接上：断成了那一句（`COMBAT_INT_BREAK`）· 它那一手被清掉 · 到点时刻被推后"
            "（%s → %s）" % (round(ct0, 1), None if not foe1 else round(float(foe1.get("ct") or 0), 1)),
            _has(o, "COMBAT_INT_BREAK") and (foe1 or {}).get("charging") is None
            and float((foe1 or {}).get("ct") or 0) > ct0)
        chk("★ `打断` 也是「你这一手」（手数 2 → 3）",
            int(s1.get("hands") or 0) == int(s0.get("hands") or 0) + 1)
    finally:
        _unpin(saved)
    # 丙 · 后撤两态：对方**没押着手** ⇒ 退得开；**正押着** ⇒ 退不开（这一手白花、照打）
    db = _fresh("ret")
    host, ad = _boot(db, "g_ret")
    _seed("g_ret", "u_r1")
    _seed("g_ret", "u_r2")
    env = _E("g_ret")
    saved = _pin()
    try:
        random.seed(20260926)
        _drive(host, ad, "u_r1", "攻击")                  # 普攻那一手落地后 ⇒ 它没在窗口里
        random.seed(20260926)
        o1 = _drive(host, ad, "u_r1", "后撤")
        chk("★ `后撤` 甲档（对方没押着手）⇒ 真退开（`COMBAT_RETREAT_OK`）· 这一场没打 · 场清干净",
            _has(o1, "COMBAT_RETREAT_OK") and INST.live(env, "u_r1") is None, o1[-2:])
        random.seed(20260926)
        _drive(host, ad, "u_r2", "攻击")
        _drive(host, ad, "u_r2", "防御")                  # 这一手后摇短 ⇒ 落在它的窗口里
        s0 = INST.live(env, "u_r2")
        random.seed(20260926)
        o2 = _drive(host, ad, "u_r2", "后撤")
        s2 = INST.live(env, "u_r2")
        chk("★ `后撤` 乙档（对方正押着一手）⇒ 退不开（`COMBAT_RETREAT_BLOCK`）· 这一手白花 · 这一场照打",
            _has(o2, "COMBAT_RETREAT_BLOCK") and s2 is not None
            and int(s2.get("hands") or 0) == int(s0.get("hands") or 0) + 1, o2[-2:])
    finally:
        _unpin(saved)
    # 丁 · 换武器：档上真换 + **场里面板当场重挂**（上限涨了）+ 这一手真花掉
    db = _fresh("swap")
    host, ad = _boot(db, "g_sw")
    from content import cmds_gear as CG                                # noqa: E402
    _seed("g_sw", "u_w", level=12, alloc={"STR": 9},
          bag={"i_weapon_knight_wall_refined": 1},
          equipped={"weapon": "i_weapon_knight_wall_common"})
    env = _E("g_sw")
    saved = _pin()
    try:
        p_w = PS.get_player("g_sw", "u_w") or {}
        chk("★ 前提：那件备用武器这号用得上（门槛为空）",
            not CG.unmet_req(dict(p_w), "i_weapon_knight_wall_refined"),
            CG.unmet_req(dict(p_w), "i_weapon_knight_wall_refined"))
        random.seed(20260926)
        _drive(host, ad, "u_w", "攻击")
        s0 = INST.live(env, "u_w")
        mx0 = int(INST.actor_of(s0, "u_w").get("max_hp") or 0)
        h0 = int(s0.get("hands") or 0)
        random.seed(20260926)
        o = _drive(host, ad, "u_w", "换武器")
        s1 = INST.live(env, "u_w")
        mx1 = int(INST.actor_of(s1, "u_w").get("max_hp") or 0)
        p1 = PS.get_player("g_sw", "u_w") or {}
        chk("★ `换武器` 档上真换（手上 %s → 背包里 %s）"
            % ((p1.get("equipped") or {}).get("weapon"), sorted((p1.get("bag") or {}))),
            (p1.get("equipped") or {}).get("weapon") == "i_weapon_knight_wall_refined"
            and "i_weapon_knight_wall_common" in (p1.get("bag") or {}))
        chk("★ 场里那一格的**面板当场重挂**（上限 %d → %d：新武器带 hp +16）" % (mx0, mx1), mx1 > mx0)
        chk("★ 换手也是「你这一手」（手数 %d → %d）" % (h0, int(s1.get("hands") or 0)),
            int(s1.get("hands") or 0) == h0 + 1)
    finally:
        _unpin(saved)
    # 戊 · 集火：群居三只 ⇒ 锁一只，**不吃行动**；接下来那一手真打它
    db = _fresh("focus")
    host, ad = _boot(db, "g_fo")
    _seed("g_fo", "u_f")
    env = _E("g_fo")
    saved = _pin(affixes=["af_swarm"])
    try:
        random.seed(20260926)
        _drive(host, ad, "u_f", "攻击")
        s0 = INST.live(env, "u_f")
        foes0 = [a for a in (((s0.get("battle") or {}).get("sides") or {}).get("enemy") or [])
                 if int(a.get("hp") or 0) > 0]
        chk("★ 前提：这一场真是三只（群居词条）—— %d 只" % len(foes0), len(foes0) == 3)
        cid = str(foes0[0].get("uid"))
        random.seed(20260926)
        o = _drive(host, ad, "u_f", "集火 %s" % MID)
        s1 = INST.live(env, "u_f")
        chk("★ `集火 <目标>` 在打的时候真锁上（%s）· **不吃行动**（手数还是 %s）"
            % (s1.get("focus"), s1.get("hands")),
            str(s1.get("focus")) == cid and _has(o, "COMBAT_FOCUS_LOCK")
            and int(s1.get("hands") or 0) == int(s0.get("hands") or 0))
        # 锁上了还得**真传进引擎的目标解析**：拿这一场复原一份真 Battle，看它把谁当目标
        b_now = INST._restore(s1)
        tgt = INST._focus_actor(b_now, s1)
        chk("★ 锁真传进引擎（拿这一场复原的真 Battle：`_focus_actor` 回的就是锁的那一格）",
            tgt is not None and str(tgt.get("uid")) == cid
            and tgt is (b_now.sides.get("enemy") or [None])[0], None if tgt is None else tgt.get("uid"))
        # 反证：锁一只**不在这一场**的 uid ⇒ 回 None（引擎自己挑目标，不是把攻击丢空）
        bad = dict(s1)
        bad["focus"] = "ms_sunken_corpse"
        chk("★ 反证：锁了一个不在这一场的 uid ⇒ `_focus_actor` 回 None（落回引擎自己的目标解析）",
            INST._focus_actor(b_now, bad) is None)
        # 真打完那一下：锁的那只掉血（三只同名同 uid ⇒ 只认得出「有一只被打了」）
        hp_before = [int(a.get("hp") or 0) for a in (((s1.get("battle") or {}).get("sides")
                                                     or {}).get("enemy") or [])]
        random.seed(20260926)
        _drive(host, ad, "u_f", "攻击")
        s2 = INST.live(env, "u_f")
        hp_after = [int(a.get("hp") or 0) for a in (((s2.get("battle") or {}).get("sides")
                                                    or {}).get("enemy") or [])]
        chk("★ 锁上之后那一手真落在敌人身上（血量 %s → %s）" % (hp_before, hp_after),
            sum(hp_after) < sum(hp_before))
    finally:
        _unpin(saved)
    # 己 · 战斗日志：在打的那一场（抬头 + 分页）
    db = _fresh("log")
    host, ad = _boot(db, "g_lg")
    _seed("g_lg", "u_l")
    env = _E("g_lg")
    saved = _pin()
    try:
        random.seed(20260926)
        _drive(host, ad, "u_l", "攻击")
        for _i in range(8):                                # 只防御（不出伤）⇒ 这一场一直在打
            random.seed(20260926 + _i)
            _drive(host, ad, "u_l", "防御")
        s = INST.live(env, "u_l")
        n_log = len(s.get("logs") or [])
        random.seed(20260926)
        o = _drive(host, ad, "u_l", "战斗日志")
        chk("★ `战斗日志` 在打的时候出的是**这一场**（抬头 `COMBAT_LOG_LIVE_HEAD` · 打到第 %s 手）"
            % s.get("hands"), _has(o, "COMBAT_LOG_LIVE_HEAD"), o[:1])
        per = PG.per_page("battle_log")
        chk("★ 这一场日志 %d 行 > 一页 %d 行 ⇒ 真分页（出了 `SYS_PAGE_FOOT`）" % (n_log, per),
            n_log > per and _has(o, "SYS_PAGE_FOOT"), len(o))
        for ln in o:
            if "第" in ln and "/" in ln:
                break
        random.seed(20260926)
        o2 = _drive(host, ad, "u_l", "下一页")
        chk("★ `下一页` 接着翻这一场（第 2 页 · 还是同一场的那一屏）",
            _has(o2, "COMBAT_LOG_LIVE_HEAD") and _has(o2, "SYS_PAGE_FOOT") and o2 != o,
            (len(o), len(o2)))
    finally:
        _unpin(saved)
    # 庚 · `使用` 非药（食物）：照实说、不消耗、不动档
    db = _fresh("food")
    host, ad = _boot(db, "g_fd")
    _seed("g_fd", "u_fo", bag={"i_food_koye_tang": 2})
    env = _E("g_fd")
    saved = _pin()
    try:
        random.seed(20260926)
        _drive(host, ad, "u_fo", "攻击")
        s0 = INST.live(env, "u_fo")
        bag0 = dict((PS.get_player("g_fd", "u_fo") or {}).get("bag") or {})
        random.seed(20260926)
        o = _drive(host, ad, "u_fo", "使用 苦叶汤")
        s1 = INST.live(env, "u_fo")
        bag1 = dict((PS.get_player("g_fd", "u_fo") or {}).get("bag") or {})
        chk("★ 战斗里吃菜 ⇒ 照实说「打起来的时候只能吃药」· **不消耗、不动档、不吃行动**",
            _has(o, "COMBAT_ITEM_ONLY_HEAL") and bag1 == bag0
            and INST.live(env, "u_fo") is not None
            and int(s1.get("hands") or 0) == int(s0.get("hands") or 0), o[:2])
    finally:
        _unpin(saved)

    # ── 辛 · ★ fix-j：集火锁的是敌人 ⇒ 只有**攻击那一档**吃它 ──────────────
    print()
    print("辛 ★ fix-j：集火之后 治疗 / 增益 **不吃**那个目标 —— 攻击 / 打断 / 用物回落照旧吃")
    from content import battle_acts as BA2                             # noqa: E402
    from content import mech as MECH                                   # noqa: E402
    from content import skills_lookup as SK                            # noqa: E402
    # ① 分档表：**逐条现算对账**（不手打名单）—— 「吃不吃集火」== 「是不是伤害三通道」
    _non_attack = {SK.kind_value("heal"), SK.kind_value("buff")}
    _actives = [(sid, rec) for sid, rec in sorted(SK.skills().items())
                if not str(sid).startswith("_") and isinstance(rec, dict)
                and str(rec.get("kind_key")) == "active"]
    _bad = [(sid, rec.get("kind_override"), INST._hand_takes_focus("skill", sid, None))
            for sid, rec in _actives
            if (rec.get("kind_override") not in _non_attack)
            != INST._hand_takes_focus("skill", sid, None)]
    chk("★ 分档表逐条现算对账（%d 条主动技能：「这一手吃不吃集火」==「是不是伤害三通道」"
        "= 域里 kind_override 经 kinds.json 换语义）" % len(_actives), not _bad, _bad[:3])
    _rows = [(t, INST._hand_takes_focus(a, s, h)) for (t, a, s, h) in (
        ("攻击", "attack", None, None),
        ("防御", "defend", None, None),
        ("技能《安神曲》(治疗)", "skill", "SKILL_PRS_lullaby", None),
        ("技能《庇护》(增益)", "skill", "SKILL_PRS_aegis", None),
        ("技能《圣杖》(魔法)", "skill", "SKILL_PRS_staff", None),
        ("打断", None, None, BA2.Hand("interrupt")),
        ("用物", None, None, BA2.Hand("item")),
        ("换手", None, None, BA2.Hand("swap")),
        ("后撤", None, None, BA2.Hand("retreat")))]
    chk("★ 地标：吃 = %s ｜ 不吃 = %s"
        % ("、".join(t for t, v in _rows if v), "、".join(t for t, v in _rows if not v)),
        [v for _t, v in _rows] == [True, False, False, False, True, True, True, False, False], _rows)
    try:
        INST._hand_takes_focus("skill", "SKILL_NOPE_fixj", None)
        _raised = ""
    except RuntimeError as _e:
        _raised = str(_e)
    chk("★ fail-closed：技能 id 域里没有 ⇒ 当场抛且**点名**（不按「吃 / 不吃」猜）",
        "SKILL_NOPE_fixj" in _raised, _raised)

    def _foe_hps(s):
        return [int(a.get("hp") or 0) for a in
                ((((s or {}).get("battle") or {}).get("sides") or {}).get("enemy") or [])]

    def _my_hp(s, uid):
        return int((INST.actor_of(s, uid) or {}).get("hp") or 0)

    def _heal_scene(tag, focus, affixes=None, seq=("技能 安神曲",)):
        """集火那一档（focus=True）/ 对照那一档（focus=False）真跑一遍，逐格读数。"""
        db = _fresh(tag)
        host, ad = _boot(db, "g_%s" % tag)
        _seed("g_%s" % tag, "u_%s" % tag, cls="cls_priest", hp=60)
        env = _E("g_%s" % tag)
        saved = _pin(affixes=affixes)
        gid, uid = "g_%s" % tag, "u_%s" % tag
        try:
            random.seed(20260926)
            _drive(host, ad, uid, "攻击")
            if focus:
                random.seed(20260926)
                _drive(host, ad, uid, "集火 %s" % MID)
            s0 = INST.live(env, uid)
            chk("★ 前提（%s）：%s" % (tag, "锁真锁上了" if focus else "这一场**没锁**集火"),
                bool(s0.get("focus")) == bool(focus), s0.get("focus"))
            out = []
            for _t in seq:
                random.seed(20260926)
                out += _drive(host, ad, uid, _t)
            s1 = INST.live(env, uid)
            return (_foe_hps(s0), _foe_hps(s1), _my_hp(s0, uid), _my_hp(s1, uid), out)
        finally:
            _unpin(saved)

    # ② 集火 + 安神曲：敌人**一格不动**、自己真涨血（修女核心机制那一半）
    fo0, fo1, h0, h1, out = _heal_scene("fhA", True)
    chk("★ ② 集火之后敲 `技能 安神曲` ⇒ **敌人一格都不动**（%s → %s）"
        "—— 改前：那一发的治疗量整份落在锁着的那只身上（实测 田鼠 12→51 = +39）"
        % (fo0, fo1), fo0 == fo1, out[-2:])
    chk("★ ② 而好处真到了**自己**身上（%d → %d）" % (h0, h1), h1 > h0, (h0, h1))
    chk("★ ② 报的还是「治愈了你 N 点生命」那一句（改前报的是**敌人**那一次治疗，"
        "自己一格没涨）", any(("治愈了" in x) for x in out), out[-2:])
    # ③ 对照（无集火）：同形 —— 敌人不动、自己涨血
    co0, co1, ch0, ch1, cout = _heal_scene("fhB", False)
    chk("★ ③ 对照：**没锁**集火时同形（敌人 %s → %s 不动 ｜ 你 %d → %d）"
        % (co0, co1, ch0, ch1), co0 == co1 and ch1 > ch0, cout[-2:])

    # ④ 集火 + 攻击：**仍打在集火目标上**（这条不许松）—— 群居三只，另两只一格不动
    db = _fresh("fhC")
    host, ad = _boot(db, "g_fhC")
    _seed("g_fhC", "u_fhC", cls="cls_priest", hp=60)
    env = _E("g_fhC")
    saved = _pin(affixes=["af_swarm"])
    try:
        random.seed(20260926)
        _drive(host, ad, "u_fhC", "攻击")
        random.seed(20260926)
        _drive(host, ad, "u_fhC", "集火 %s" % MID)
        s0 = INST.live(env, "u_fhC")
        a0 = _foe_hps(s0)
        random.seed(20260926)
        _drive(host, ad, "u_fhC", "攻击")
        s1 = INST.live(env, "u_fhC")
        a1 = _foe_hps(s1)
        chk("★ ④ 集火之后 `攻击` **仍打在锁的那一只上**（三只 %s → %s：只有第 1 只掉血）"
            % (a0, a1), a0[0] > a1[0] and a1[1:] == a0[1:], (a0, a1))
        # ⑤ 用物（上限用满那一手回落成普攻）也吃集火 —— 同一条规则
        random.seed(20260926)
        _drive(host, ad, "u_fhC", "使用 伤药")                 # 第 1 瓶：真回血、真扣药
        b0 = _foe_hps(INST.live(env, "u_fhC"))
        random.seed(20260926)
        o = _drive(host, ad, "u_fhC", "使用 伤药")             # 第 2 瓶：回落成普攻那一手
        b1 = _foe_hps(INST.live(env, "u_fhC"))
        chk("★ ⑤ 用满上限那一手回落成普攻 ⇒ **也打在锁的那一只上**（%s → %s）" % (b0, b1),
            _has(o, "COMBAT_ITEM_CAP") and b0[0] > b1[0] and b1[1:] == b0[1:], (b0, b1))
        # ⑥ 增益：态挂在**自己**身上，敌人身上没有那一条
        _key = str(MECH.of("shield_ally").get("state") or "")
        random.seed(20260926)
        _drive(host, ad, "u_fhC", "技能 庇护")
        s2 = INST.live(env, "u_fhC")
        _me = INST.actor_of(s2, "u_fhC") or {}
        _foes = [a for a in ((s2.get("battle") or {}).get("sides") or {}).get("enemy") or []]
        chk("★ ⑥ 集火之后敲 `技能 庇护`（增益）⇒ 态 `%s` 挂在**自己**身上、敌人身上没有"
            % _key,
            bool(_key) and _key in (_me.get("effects") or {})
            and not any(_key in (a.get("effects") or {}) for a in _foes))
    finally:
        _unpin(saved)

    # ⑦ 反证：把分档撤掉（回到「集火目标原样传给每一条指令」）⇒ ② 那条判据**当场红**
    _real_tf = INST._hand_takes_focus
    INST._hand_takes_focus = lambda *a, **k: True
    try:
        bo0, bo1, bh0, bh1, bout = _heal_scene("fhD", True)
    finally:
        INST._hand_takes_focus = _real_tf
    chk("★ ⑦ 反证（有牙）：分档撤掉 ⇒ 同一句 `技能 安神曲` 把好处整份送给敌人"
        "（敌 %s → %s，自己 %d → %d —— ② 的「敌人一格不动」当场红）"
        % (bo0, bo1, bh0, bh1), bo1 != bo0 and bo1[0] > bo0[0],
        (bo0, bo1, bh0, bh1))

    # ── ⑧ fail-closed：没得打那五条说同一句 · 两个单人互不串场 ──────
    print()
    print("⑧ fail-closed：没得打的地方那几条说**同一句** · 两个单人各是各的一场")
    db = _fresh("none")
    host, ad = _boot(db, "g_no")
    from content import town as TOWN                                   # noqa: E402
    _seed("g_no", "u_x", loc=TOWN.TOWN, node="wt_square")
    env = _E("g_no")
    saved = _pin(monster=None)                     # 这一带一只都挑不出来
    try:
        want = [slot("COMBAT_NEED_FOE")]
        rows = []
        for t in ("打断", "防御", "后撤", "逃跑", "自动"):
            random.seed(20260926)
            o = _drive(host, ad, "u_x", t)
            rows.append((t, o == want, o[:1]))
        chk("★ 没得打的地方：打断 / 防御 / 后撤 / 逃跑 / 自动 回**同一句** `COMBAT_NEED_FOE`",
            all(r[1] for r in rows), rows)
        random.seed(20260926)
        o_atk = _drive(host, ad, "u_x", "攻击")
        chk("★ 两态对照：`攻击` 在同一处**照旧**回场景口吻那一句（`COMBAT_NONE`）",
            o_atk == [slot("COMBAT_NONE")], o_atk[:1])
        chk("★ 这一圈**一场都没开**（场里的记录一条都没有）",
            INST.live(env, "u_x") is None)
    finally:
        _unpin(saved)
    db = _fresh("two")
    host, ad = _boot(db, "g_2s")
    _seed("g_2s", "u_p1")
    _seed("g_2s", "u_p2")
    saved = _pin()
    try:
        random.seed(20260926)
        _drive(host, ad, "u_p1", "攻击")
        random.seed(20260926)
        _drive(host, ad, "u_p2", "攻击")
        s1 = INST.live(_E("g_2s"), "u_p1")
        s2 = INST.live(_E("g_2s"), "u_p2")
        chk("★ 同群两个人各打各的**各一场**（键不同 · 名单都只有自己 · 都是第 1 手）",
            s1 is not None and s2 is not None and list(s1.get("members") or []) == ["u_p1"]
            and list(s2.get("members") or []) == ["u_p2"]
            and INST.battle_key(_E("g_2s"), "u_p1") != INST.battle_key(_E("g_2s"), "u_p2"),
            (INST.battle_key(_E("g_2s"), "u_p1"), INST.battle_key(_E("g_2s"), "u_p2")))
    finally:
        _unpin(saved)

    print()
    print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
