# -*- coding: utf-8 -*-
r"""探针：多人战斗的轮转与输入窗口（B3-26）—— 场 · 轮转 · 等待 · 超时 · guard · 单人不变。

真源：`06_第一阶段垂直切片/17_组队与策略配合_v1.md §四`（照奥兰迪亚的实现）·
`00_总纲/03_主要玩法.md §4.10`；参考实现（另一个包，只读）
`orlandia/content/cmds_instance_router.py:378-418`。

判据（全部**真跑**：真宿主管道 + 真存档库 + 真敲指令）
--------------------------------------------------------
  ① ★ 两个档真进同一场战斗，「谁该动」== ct 序（CTB 的自然顺序，不是「同时」）——
     慢的先敲只会被告知在等谁；快的敲下去**真出手**（场里的 actor 真变了）
  ② ★ 没轮到 ⇒ **只得等待提示**（槽位 `SYS_ROUND_HOLD`，带「你在等谁」）· **不动档**
     （那个人的整份档一字不变）· **不开新战斗**（场里还是原来那一只，没多出一场）
  ③ ★ 超时那一支真跑到：**假钟**把 `turn_time` 推过窗口 ⇒ 替挂机的人**自动防御**
     （槽位 `SYS_TIMEOUT_DEFEND` + 引擎的防御那一手真落到 actor 上 `defending=True`）；
     窗口内（没超时）再多一秒都不防御 —— 两侧都钉
  ④ ★ guard：一轮最多消化 `afk_guard` 个挂机玩家（真摆 21 个挂机 + 1 个请求者）
  ⑤ ★ 单人那条路：同一条脚本拿**冻结基线**（`scripts/_baseline_instance_solo.json`）的真跑回话逐行对账
     ★ G2 起这一支的**基准树**换过一次（单人从「一次结算」改成「一手一推进」）—— 账见 ⑤ 抬头
  ⑥ fail-closed：队伍口坏了当场抛 · 队却没群当场抛 · **没群时单人照样有自己那一场、两个人各一格** · 场记录坏了不当成「没开过」
  ⑥b 名单外的人敲战斗指令 ⇒ 走单人老路，别人的场一字不动
  ⑦ 一场真打完（两个档轮流出手）⇒ 结算落两个人的档 · 场散掉

跑法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_instance.py
     python scripts/probe_instance.py --dump      # 打基线（改前那份树的真跑回话）
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
DUMP = "--dump" in sys.argv
sys.path.insert(0, str(REPO))
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402

ok = True


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("OK " if cond else "X  ", label, ("  —— %s" % extra) if extra else ""))


# ══════════════════════════════════════════════════════════════
# 夹具：真宿主契约 + 真存档库（适配器与生产宿主壳同源：读写都走包自己的存档半边）
# ══════════════════════════════════════════════════════════════
def _fresh(name) -> str:
    p = os.path.join(TMP, "ast_probe_instance_%s.db" % name)
    try:
        os.remove(p)
    except OSError:
        pass
    return p


class _Clock:
    """假钟（③ 靠它，别真等 45 秒）。"""

    def __init__(self, t0=1700000000.0):
        self.t = float(t0)

    def __call__(self):
        return self.t

    def tick(self, dt):
        self.t += float(dt)
        return self.t


class _Ad(object):
    """照真宿主壳的最小适配器（`load_player` / `save_player` 都走包自己的存档半边）。"""

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
                  if k not in ("group_id", "qq_id", "uid")}   # 与宿主壳 _IDENTITY_KEYS 同表
        PS.update_player(self.gid, uid, **fields)

    def say(self, to, text):
        self.out.append(str(text))


SEED = {"name": "单人", "cls": "cls_knight", "race": "human", "level": 5, "exp": 0,
        "gold": 30, "bag": {"i_potion_minor": 2}, "equipped": {}, "codex": {}, "flags": {},
        "prev": [], "loc": "belt_north", "node": "bn_bone"}


def _boot(db, gid, clock=None, extra_inject=None):
    """装一份真宿主（真存档库路径 + 真钟/假钟）。"""
    from saintess_engine.host.runtime import Host
    from content import persistence as PS
    inject = {"db_path": db}
    inject.update(extra_inject or {})
    if clock is not None:
        inject["clock"] = clock
    if DUMP:
        inject.setdefault("clock", time.time)
    h = Host(_Ad(gid), str(REPO), inject=inject)
    h.boot()
    if clock is not None:
        PS.bind(clock=clock)                    # 包自己的钟口也换成假钟（`instance.now()` 走它）
    return h, h.adapter


def _seed(gid, uid, **kw):
    """往真存档库里种一份档（与宿主落档同一张表、同一套字段）。"""
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


def _pin_encounter(monster):
    """把遇敌钉死（战斗内部抽怪 ⇒ 不钉住不可复现）；`None` = 这一带挑不出怪。"""
    from content import combat as CB
    from content import affix as AFFIX
    real_pick, real_elite = CB.pick_encounter, AFFIX.elite_of
    CB.pick_encounter = (lambda *a, **k: [monster]) if monster else (lambda *a, **k: [])
    AFFIX.elite_of = lambda *a, **k: None       # 精英那条抽签带 game_day（墙钟）⇒ 钉掉
    return real_pick, real_elite


def _unpin(saved):
    from content import combat as CB
    from content import affix as AFFIX
    CB.pick_encounter, AFFIX.elite_of = saved


MON = None


#: ★ 多人那几节用的「打谁 / 什么等级」——挑一只**血厚又不致命**的（沉尸 lv15 · hp 1199 ·
#:  atk 24）：几手之内打不死它、它也几手之内打不死人 ⇒ 下面那些「场还在不在 / 谁的 ct 动了」
#:  的读数才稳（换成田鼠那种 66 血的，两三个人两下就打完，读数会随时被「打完了」冲掉）。
PARTY_MON = "ms_sunken_corpse"
PARTY_LV = 15


# ══════════════════════════════════════════════════════════════
# ⑤ 的基线脚本（单人那条路 —— 这一支在改前那棵树上也跑得动，见 --dump）
# ══════════════════════════════════════════════════════════════
SOLO_STEPS = ("攻击", "战斗日志", "防御", "攻击", "状态")
SOLO_SEED_RND = 20260926
SOLO_MON = "ms_field_mouse"


def solo_transcript():
    """单人那条路的**全部回话**（逐行）—— 改前 / 改后都跑这一段，逐字比。"""
    db = _fresh("solo")
    host, ad = _boot(db, "g_solo")
    _seed("g_solo", "u_solo")
    saved = _pin_encounter(SOLO_MON)
    rows = []
    try:
        for t in SOLO_STEPS:
            random.seed(SOLO_SEED_RND)
            rows.append([t, _drive(host, ad, "u_solo", t)])
    finally:
        _unpin(saved)
    from content import persistence as PS
    last = PS.get_player("g_solo", "u_solo") or {}
    return {"rows": rows,
            "save": {k: last.get(k) for k in ("hp", "hp_max", "gold", "exp", "level",
                                              "bag", "loc", "node")}}


# ══════════════════════════════════════════════════════════════
# ★ 基线（⑤ 改前的真跑回话）：`scripts/_baseline_instance_solo.json` ——
#   来历 = 本批基线 **3ee9148** 那棵树上跑 `python scripts/probe_instance.py --dump`
#   （同一段脚本、同一套夹具、同一个种子）打出来的**逐字回话 + 档上那几格**。
#   `--dump` 在改前那棵树上也跑得动（那支不 import `content.instance`）。
#
#   ★ B4-8 刷新过一次（就一次）：`状态` 那一行的**法力上限**改成走面板唯一口
#     （`panel_build.mp_cap`，原先读档上那格零写端的 `mo_max`）⇒ 逐字对账里
#     唯一变的一行是「…法力 0/0…」→「…法力 0/50…」（新旧两份 `--dump` 逐行 diff 过，
#     其余 4 条指令 · 85 行 · 档上那几格**一字未动**）。这一条判据的意思是
#     「单人那条路没被**动过**」，不是「一个字都不许改」—— 有意的口径变更要在这里跟账，
#     并另加判据钉住新口径（见 `probe_panel` ⑨ / `probe_recipes` ⑪）。
#   ★ P-51（2026-09-26）再刷新过一次（第二次，同样是**有意**的口径变更）：
#     现蓝的起手改成走唯一一口 `mana.initial_mp`（档上有那一格 ⇒ 照它；**缺格** ⇒ 满池）
#     ⇒ 逐字对账里唯一变的一行是「…法力 0/50…」→「…法力 50/50…」（新旧两份 `--dump`
#     逐行 diff 过：5 条指令 86 行只差这 1 行 · `save` 那几格逐字相同）。
#     新口径的常驻判据在 `scripts/probe_mana.py` ④（三处一个数 + 缺格⇒满）。
#   ★ P3 BUG-1（2026-09-26 · 本波 f4）第三次刷新（同样是**有意**的口径变更 · 这一支没动过一行）：
#     掉落种子从 `uid:怪 id` 改成走唯一一口 `cmds_battle.drop_seed(uid, 怪, **第几次**, 轮)`
#     —— 原先那种子不含次数 ⇒ **同一只怪对同一个人每次都掉同一件**（田鼠 4 次全铁渣）。
#     这一段脚本里有**两次 `攻击`**（同一个人打同一只怪）⇒ 那两场的掉落行与 `bag` 跟着变
#     （第一次打 = 第 0 次那一份、第二次 = 第 1 次那一份）；其余指令与那几格一字未动。
#     新口径的常驻判据在 `scripts/probe_fix4_combat.py` ①（两态对照 + 真跑 20 场 + 静态）。
#   ★ ★ G2（2026-09-26 · 本波）第四次刷新 —— 这一支的**语义有意换向**（唯一一次不是「同一件事换个做法」）：
#     「单人那条路」从**一条指令打完整场**改成**一手一推进**（`content/instance.py` 的「场」放开到单人）
#     ⇒ 这一段脚本里的 5 条指令产出**必然全变**（不再有「一次结算」，每一敲落回你手里、
#     多出一屏四段式：现状 / 谁先动 / 对方在干什么 / 你的选项）。
#
#     旧（本批基线 `bea4df9` 那棵树）：  攻击 20 行 · 战斗日志 25 行 · 防御 19 行 · 攻击 19 行 · 状态 3 行
#                                       `save` = {hp 116, gold 57, exp 27, bag {铁渣×4, 伤药×3}, …}
#     新（G2 本树）：                    攻击 10 行 · 战斗日志 6 行 · 防御 8 行 · 攻击 10 行 · 状态 3 行
#                                       `save` = {hp 158, gold 30, exp 0, bag {伤药×2}, …}
#
#     逐条说「为什么」：
#       · 攻击（旧 20 → 新 10）：旧那一敲 = 整场（打到田鼠倒下 + 掉落/经验/进谱）；新那一敲 =
#         **第 1 手 + 对方那一手**，所以只有 1 组「受 13 / 受 4」，**没有** `✔ 打完了`／掉落那几行。
#       · 战斗日志（旧 25 → 新 6）：旧读的是 `flags.last_battle`（上一场全文）；新的是
#         **在打的这一场**（`【这一场】田鼠 —— 打到第 1 手` + 这一场到现在的 5 行）。
#       · 防御（旧 19 → 新 8）：新一敲 = 接着上一场往下推一手（防御），不再开第二场。
#       · 攻击（旧 19 → 新 10）：同上（第 3 手）。
#       · 状态（旧 3 = 新 3，但数字不同）：血/钱/经验都随「只推了一手」而变
#         （这一场到第 3 手还没打完 ⇒ 钱 30、经验 0、包里那瓶药没动过）。
#     ★ 判据本身**没改宽**：仍然是「这一段的回话与 `scripts/_baseline_instance_solo.json` **逐字**相同」
#       —— 变的只是那份快照的**基准树**（旧基准记的是改前的行为，留着就永远对不上了）。
#       新口径的常驻判据在 `scripts/probe_battle_turns.py` ①（一手一推进 · 分段版与一次结算版两态对照）。
# ══════════════════════════════════════════════════════════════
BASELINE_PATH = os.path.join(str(REPO), "scripts", "_baseline_instance_solo.json")


def _baseline():
    try:
        with open(BASELINE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return None


SOLO_BASELINE = None


def main():
    global MON
    st = load_stack(str(REPO), inject={"db_path": _fresh("stack"), "clock": time.time})
    st.install()
    MON = st.domain("monsters") or {}
    TX = st.domain("texts") or {}

    from content import combat as CB                            # noqa: E402
    from content import instance as INST                        # noqa: E402
    from content import persistence as PS                       # noqa: E402

    def slot(key, **kw):
        s = (TX.get(key) or {}).get("value", "")
        for k, v in kw.items():
            s = s.replace("{%s}" % k, str(v))
        return s

    print("探针：多人战斗的轮转与输入窗口（B3-26）")

    # ── ① 两档真进同一场：轮转顺序 == ct 序 ───────────────────────
    print()
    print("① 两个档真进同一场战斗 —— 「谁该动」== ct 序（CTB 自然顺序）")
    db = _fresh("two")
    host, ad = _boot(db, "g_two")
    _seed("g_two", "u_a", level=PARTY_LV, cls="cls_knight", name="甲")
    _seed("g_two", "u_b", level=PARTY_LV, cls="cls_assassin", name="乙")
    INST.party_members = lambda g, u: ["u_a", "u_b"] if g == "g_two" else [u]
    saved = _pin_encounter(PARTY_MON)
    st_a = st_b = None
    try:
        # 先不动手：拿引擎自己排出来的 ct 序当期望（不手写「谁快」）
        b = CB.build({}, [PARTY_MON], MON, party=2,
                     players=[dict(PS.get_player("g_two", u), uid=u) for u in ("u_a", "u_b")])
        cts = [(a["uid"], round(float(a.get("ct", 0) or 0), 4)) for a in b.sides["player"]]
        first = min(cts, key=lambda x: x[1])[0]
        second = [u for u, _c in cts if u != first][0]
        chk("★ 引擎排的 ct 序可判（%s）" % " · ".join("%s=%s" % x for x in cts), first != second)
        # 排后面的那个先敲：开场（遇敌）之后**立刻**该是「没轮到你」
        o1 = _drive(host, ad, second, "攻击")
        st_a = INST.load("g_two")
        chk("★ 开场那一敲真建了场（%d 个人 · 打的 %s）"
            % (len(st_a["members"]), st_a["pick"][0]) if st_a else "★ 开场那一敲",
            st_a is not None and sorted(st_a["members"]) == ["u_a", "u_b"]
            and list(st_a["pick"]) == [PARTY_MON])
        chk("★ 没轮到 ⇒ 出等待提示（槽位 SYS_ROUND_HOLD，带「你在等谁」）",
            slot("SYS_ROUND_HOLD", who=(PS.get_player("g_two", first) or {}).get("name")) in o1, o1)
        # 再敲一次（场已经在跑）：② 那三条 —— 等待提示 · 场一字不动 · 档一字不动
        snap_st = json.dumps(INST.load("g_two"), ensure_ascii=False, sort_keys=True)
        snap_p = dict(PS.get_player("g_two", second))
        o2 = _drive(host, ad, second, "攻击")
        st_b = INST.load("g_two")
        chk("★ ② 没轮到的再敲一次：还是只给等待提示",
            slot("SYS_ROUND_HOLD", who=(PS.get_player("g_two", first) or {}).get("name")) in o2
            and len(o2) == 1, o2)
        chk("★ ② **不动档**（整份档逐格比）", dict(PS.get_player("g_two", second)) == snap_p)
        chk("★ ② **不动场**（含 turn_time —— 窗口没被推）",
            json.dumps(st_b, ensure_ascii=False, sort_keys=True) == snap_st)
        chk("★ ② **不开新战斗**（场还是第一次遇敌那一只，没多一场）",
            list(st_b.get("pick") or []) == [PARTY_MON] and list(st_b.get("members") or []) ==
            list(st_a.get("members") or []))
        # 该动的那个敲：真出手
        o3 = _drive(host, ad, first, "攻击")
        st_c = INST.load("g_two")
        chk("★ 轮到的那个真出手（场里累计日志非空）",
            st_c is not None and len(st_c.get("logs") or []) > 0, o3[:2])
        chk("★ 轮转顺序 == ct 序（下一个该动的是 ct 次小的 %s）" % second,
            st_c is not None and str(INST.next_actor_key(st_c)) == str(second))
    finally:
        _unpin(saved)
        INST.party_members = None

    # ── ③ 超时那一支：假钟（别真等 45 秒）────────────────────────
    print()
    print("③ 超时 ⇒ 自动防御（假钟；槽位 SYS_TIMEOUT_DEFEND + 挂机那位真花掉一手）")
    db = _fresh("to")
    clock = _Clock(1700000000.0)
    host, ad = _boot(db, "g_to", clock=clock)
    _seed("g_to", "u_a", level=PARTY_LV, cls="cls_knight", name="甲")
    _seed("g_to", "u_b", level=PARTY_LV, cls="cls_assassin", name="乙")
    INST.party_members = lambda g, u: ["u_a", "u_b"] if g == "g_to" else [u]
    saved = _pin_encounter(PARTY_MON)
    try:
        # 先在引擎侧排一遍 ct 序，挑**快的那个**当请求者（他一出手，窗口就交到挂机那位手里）
        b = CB.build({}, [PARTY_MON], MON, party=2,
                     players=[dict(PS.get_player("g_to", u), uid=u) for u in ("u_a", "u_b")])
        cts = {a["uid"]: float(a.get("ct", 0) or 0) for a in b.sides["player"]}
        fast = min(cts, key=lambda k: cts[k])
        slow = [u for u in cts if u != fast][0]
        clock.tick(10)
        _drive(host, ad, fast, "攻击")                        # 开场 + 快的先出手
        s0 = INST.load("g_to")
        cur = INST.next_actor_key(s0)
        chk("★ 前提：快的先出手，窗口交到挂机那位（%s）手里" % slow, cur == slow, cur)
        ct0 = float(INST.actor_of(s0, cur).get("ct", 0) or 0)
        # 窗口里（差 1 秒）⇒ 不防御：只给等待提示，挂机那位一手都没花
        clock.tick(INST.window_seconds() - 1)
        o_in = _drive(host, ad, fast, "攻击")
        chk("★ 窗口内（差 1 秒）不防御：仍是等待提示",
            slot("SYS_ROUND_HOLD", who=(PS.get_player("g_to", cur) or {}).get("name")) in o_in,
            o_in[:2])
        chk("★ 窗口内挂机那位**一手都没花**（ct 没动）",
            float(INST.actor_of(INST.load("g_to"), cur).get("ct", 0) or 0) == ct0)
        # 推过窗口 ⇒ 替挂机的人自动防御（那一手真落地：它的到点时刻被推到了后面）
        clock.tick(2)
        o_to = _drive(host, ad, fast, "攻击")
        s2 = INST.load("g_to")
        ct1 = float(INST.actor_of(s2, cur).get("ct", 0) or 0)
        chk("★ 超时 ⇒ 出槽位那行（SYS_TIMEOUT_DEFEND，全队可见）",
            slot("SYS_TIMEOUT_DEFEND", who=(PS.get_player("g_to", cur) or {}).get("name")) in o_to,
            o_to[:1])
        chk("★ 超时 ⇒ 替挂机那位**真花掉一手**（它的到点时刻被推到后面：%s → %s）"
            % (round(ct0, 2), round(ct1, 2)), ct1 > ct0)
        chk("★ 那一行也进了这一场的日志（『战斗日志』看得到）",
            any("超时" in x for x in (s2.get("logs") or [])))
    finally:
        _unpin(saved)
        INST.party_members = None

    # ── ④ guard：一轮最多消化这么多挂机玩家 ───────────────────────
    print()
    print("④ 防死循环：一轮最多消化 afk_guard 个挂机（真摆 21 个挂机 + 1 个请求者）")
    n_afk = INST.afk_guard() + 1
    db = _fresh("guard")
    clock = _Clock(1700000000.0)
    host, ad = _boot(db, "g_gd", clock=clock)
    members = ["u_afk%02d" % i for i in range(n_afk)] + ["u_req"]
    for m in members:
        _seed("g_gd", m, level=PARTY_LV,
              cls="cls_assassin" if m.startswith("u_afk") else "cls_knight",
              name=("挂机" + m[-2:]) if m.startswith("u_afk") else "请求者")
    INST.party_members = lambda g, u: list(members) if g == "g_gd" else [u]
    saved = _pin_encounter(PARTY_MON)
    try:
        clock.tick(10)
        _drive(host, ad, "u_req", "攻击")
        s = INST.load("g_gd")
        chk("★ 前提：%d 个人的场开着" % len(members), s is not None and len(s["members"]) == len(members))
        ct_before = {m: float(INST.actor_of(s, m).get("ct", 0) or 0) for m in members}
        clock.tick(INST.window_seconds() + 1)                # 全体挂机都超时了
        o = _drive(host, ad, "u_req", "攻击")
        s2 = INST.load("g_gd")
        n_to = sum(1 for x in (s2.get("logs") or []) if "超时" in x)
        done = [m for m in members if m.startswith("u_afk")
                and float(INST.actor_of(s2, m).get("ct", 0) or 0) > ct_before[m]]
        chk("★ 一轮正好消化 %d 个挂机（guard 到了就不再往下）" % INST.afk_guard(),
            n_to == INST.afk_guard(), "真消化 %d 个" % n_to)
        chk("★ 第 %d 个挂机**没被消化**（它那一手没花：到点时刻没动）" % n_afk,
            len(done) == INST.afk_guard(), "花过一手的 %d 个" % len(done))
        chk("★ 消化到上限就 break：请求者那一敲没被卡住（回话 %d 行）" % len(o), bool(o))
    finally:
        _unpin(saved)
        INST.party_members = None

    # ── ⑤ 单人路径与改前逐字相同 ──────────────────────────────────
    print()
    print("⑤ 单人那条路：与**冻结基线**（scripts/_baseline_instance_solo.json · G2 树那份）逐字相同")
    now = solo_transcript()
    base = _baseline()
    if not base:
        chk("★ 基线在（scripts/_baseline_instance_solo.json）", False, "文件不在 —— 先跑 --dump")
    else:
        diff = []
        for i, (row, brow) in enumerate(zip(now["rows"], base["rows"])):
            if row[0] != brow[0] or row[1] != brow[1]:
                diff.append((i, row[0], (brow[1] or [])[:2], (row[1] or [])[:2]))
        chk("★ 逐条指令的回话逐字相同（%d 条 · 共 %d 行）"
            % (len(now["rows"]), sum(len(r[1]) for r in now["rows"])),
            now["rows"] == base["rows"], diff[:1])
        chk("★ 档上那几格也相同", now["save"] == base["save"],
            {k: (now["save"][k], base["save"].get(k)) for k in now["save"]
             if now["save"][k] != base["save"].get(k)})

    # ── ⑥ fail-closed ──────────────────────────────────────────────
    print()
    print("⑥ fail-closed：队伍口坏 / 单人 / 没群 / 场记录坏")
    INST.party_members = lambda g, u: []
    try:
        INST.members_of("g_x", "u_x")
        chk("★ 队伍名单是空表 ⇒ 当场抛（不悄悄退回单人）", False, "没抛")
    except ValueError:
        chk("★ 队伍名单是空表 ⇒ 当场抛（不悄悄退回单人）", True)
    finally:
        INST.party_members = None
    chk("★ 没接队伍口 ⇒ 单人（今天就是这样）", INST.members_of("g_x", "u_x") == ["u_x"],
        INST.members_of("g_x", "u_x"))
    import types                                                         # noqa: E402
    # ★ G2（2026-09-26 · 本波）：这一段**有意换向** —— 改前是「没群 ⇒ 不进『场』（route_needed=False）」。
    #   战斗改成一手一推进之后，单人也有自己那一场 ⇒ 没群照样进（键 = `#<uid>`，按人分开）。
    #   判据**只加强不削弱**：不但要求「没群也进」，还要求「两个人各是各的一格」+「有队却没群当场抛」。
    chk("★ 没群（私聊 / 宿主没给 group_id）⇒ 单人也进「场」（route_needed=True）",
        INST.route_needed(types.SimpleNamespace(group_id=""), "u_x") is True
        and INST.route_needed(_Ad(""), "u_x") is True)
    chk("★ 没群时**按人分开**（两个 uid 各一格，谁也不串谁的场）",
        INST.key_of("", "u_x", ["u_x"]) != INST.key_of("", "u_y", ["u_y"])
        and INST.key_of("g", "u_x", ["u_x"]) != INST.key_of("g", "u_y", ["u_y"])
        and INST.key_of("g", "u_x", ["u_x", "u_y"]) == "g",
        "%r / %r" % (INST.key_of("", "u_x", ["u_x"]), INST.key_of("", "u_y", ["u_y"])))
    try:
        INST.key_of("", "u_x", ["u_x", "u_y"])
        chk("★ 有队却没有群 ⇒ 当场抛（队是按群存的，取不出名单的形状）", False, "没抛")
    except RuntimeError:
        chk("★ 有队却没有群 ⇒ 当场抛（队是按群存的，取不出名单的形状）", True)
    INST.party_members = lambda g, u: ["u_y"]
    try:
        INST.members_of("g_x", "u_x")
        chk("★ 名单里没有请求者自己 ⇒ 当场抛", False, "没抛")
    except ValueError:
        chk("★ 名单里没有请求者自己 ⇒ 当场抛", True)
    finally:
        INST.party_members = None
    db = _fresh("bad")
    host, ad = _boot(db, "g_bad")
    PS.group_set("instance", "g_bad", {"members": ["u_x"]})
    try:
        INST.load("g_bad")
        chk("★ 场记录缺格 ⇒ 当场抛（不当成「没开过」）", False, "没抛")
    except RuntimeError:
        chk("★ 场记录缺格 ⇒ 当场抛（不当成「没开过」）", True)
    PS.group_del("instance", "g_bad")

    # ── ⑥b 不在这一场名单里的人：走单人老路（不动别人的场）──────────
    print()
    print("⑥b 名单外的人敲战斗指令 ⇒ 走单人老路，别人的场一字不动")
    db = _fresh("out")
    host, ad = _boot(db, "g_out")
    _seed("g_out", "u_in1", level=PARTY_LV, cls="cls_knight", name="队里甲")
    _seed("g_out", "u_in2", level=PARTY_LV, cls="cls_assassin", name="队里乙")
    _seed("g_out", "u_out", level=PARTY_LV, cls="cls_knight", name="路人")
    _IN2 = ("u_in1", "u_in2")
    INST.party_members = lambda g, u: (list(_IN2) if u in _IN2 else [u]) if g == "g_out" else [u]
    saved = _pin_encounter(SOLO_MON)
    try:
        _drive(host, ad, "u_in1", "攻击")            # 那两个人开一场（名单不含路人）
        st0 = INST.load("g_out")
        chk("★ 前提：两个人的场开着，名单里没有路人",
            st0 is not None and sorted(st0["members"]) == sorted(_IN2), None if not st0 else
            st0["members"])
        snap = json.dumps(st0, ensure_ascii=False, sort_keys=True)
        o_out = _drive(host, ad, "u_out", "攻击")
        chk("★ 名单外的人敲 ⇒ 那一句是**遇敌**（单人老路），不是等待提示",
            bool(o_out) and o_out[0] == slot("COMBAT_MEET", name=MON[SOLO_MON]["name"])
            and not any("还没轮到你" in x for x in o_out), o_out[:2])
        chk("★ 别人的场**一字没动**",
            json.dumps(INST.load("g_out"), ensure_ascii=False, sort_keys=True) == snap)
    finally:
        _unpin(saved)
        INST.party_members = None

    # ── ⑥c 名单里有人还没定职业 ⇒ 这一场不开（点名那一行）──────────
    print()
    print("⑥c 名单里有人还没定职业 ⇒ 这一场不开（点名那一行）· 场里不留东西")
    db = _fresh("nocls")
    host, ad = _boot(db, "g_nc")
    _seed("g_nc", "u_ok", level=PARTY_LV, cls="cls_knight", name="定了职")
    from content import cmds_ast as CA2                                  # noqa: E402
    _raw = dict(CA2.DEFAULT_PLAYER)
    _raw.update({"name": "没定职", "level": 1, "loc": "belt_north", "node": "bn_bone",
                 "bag": {}, "equipped": {}, "flags": {}, "gold": 0})
    PS.update_player("g_nc", "u_raw", **_raw)         # 建号第二步没走完 = 档上没有职业
    INST.party_members = lambda g, u: ["u_ok", "u_raw"] if g == "g_nc" else [u]
    saved = _pin_encounter(PARTY_MON)
    try:
        o = _drive(host, ad, "u_ok", "攻击")
        chk("★ 出的是**点名那一行**（谁的档还没定职业）",
            bool(o) and o[0] == slot("SYS_HP_UNSET", name="没定职"), o[:2])
        chk("★ 这一场**没开**（不留场：不动档 / 不建场）", INST.load("g_nc") is None)
    finally:
        _unpin(saved)
        INST.party_members = None

    # ── ⑦ 真打完一场：两边轮流出手 → 结算全队 → 场散掉 ─────────────
    print()
    print("⑦ 一场真打完（两个档轮流出手）—— 结算落两个人的档 · 场散掉")
    db = _fresh("end")
    host, ad = _boot(db, "g_end")
    _seed("g_end", "u_a", cls="cls_knight", name="甲")
    _seed("g_end", "u_b", cls="cls_assassin", name="乙")
    INST.party_members = lambda g, u: ["u_a", "u_b"] if g == "g_end" else [u]
    saved = _pin_encounter(SOLO_MON)
    try:
        random.seed(20260926)
        n_round = 0
        lines: list = []
        _drive(host, ad, "u_a", "攻击")                 # 开场那一敲（谁敲都行 —— 遇敌只来一次）
        n_round += 1
        while n_round < 80:
            s = INST.load("g_end")
            if s is None:
                break
            cur = INST.next_actor_key(s)
            if cur is None:
                break
            n_round += 1
            lines = _drive(host, ad, cur, "攻击")
        s_end = INST.load("g_end")
        chk("★ 这一场真打完了（%d 手之内结束：场散掉 = %s）" % (n_round, s_end is None),
            s_end is None and n_round < 80, "还剩 %d 手" % n_round)
        p_a = PS.get_player("g_end", "u_a") or {}
        p_b = PS.get_player("g_end", "u_b") or {}
        chk("★ 两个人的档都落了账（铜板 %s/%s · 经验 %s/%s）"
            % (p_a.get("gold"), p_b.get("gold"), p_a.get("exp"), p_b.get("exp")),
            int(p_a.get("gold") or 0) > 0 and int(p_b.get("gold") or 0) > 0
            and int(p_a.get("exp") or 0) > 0 and int(p_b.get("exp") or 0) > 0)
        _enemy = [_lb.get("enemy") for _lb in ((p_a.get("flags") or {}).get("last_battle") or {},
                                               (p_b.get("flags") or {}).get("last_battle") or {})]
        chk("★ 两个人的『战斗日志』都写了同一只怪（%s）" % _enemy,
            _enemy[0] == _enemy[1] == MON[SOLO_MON]["name"])
        chk("★ 两个人都没倒（血 %s/%s，与档上那条钳法一致）" % (p_a.get("hp"), p_b.get("hp")),
            int(p_a.get("hp") or 0) > 0 and int(p_b.get("hp") or 0) > 0)
    finally:
        _unpin(saved)
        INST.party_members = None

    print()
    print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
    return 0 if ok else 1


if DUMP:
    print(json.dumps(solo_transcript(), ensure_ascii=False, sort_keys=True))
    sys.exit(0)

if __name__ == "__main__":
    sys.exit(main())
