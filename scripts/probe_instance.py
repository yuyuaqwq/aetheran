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
  ⑪ ★ 名单变了（离队 / 解散）⇒ 那一场按**现名单**收口（`instance.leave_reconcile` 唯一一口）：
     走的人从 `members` 与 `sides` **一起**摘（剩下的人接着打）· 摘完 ≤1 人 / 队长退 = 解散
     ⇒ 这一场收掉 · 人不在这一场里 / 手上没场 ⇒ 一个字都不动（真敲队伍/邀请/同意/攻击/离队）

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
#   ★ ★ ★ P0-1（2026-09-28 · 文案修复车道 · 战斗时间轴）—— **有意的口径变更**，登记在此：
#     真源 `00_总纲/06_第一阶段垂直切片/26_消息模板_v1.md` §三 优化 1 逐字：
#     「所有战斗日志行统一以【N 刻】开头」，样例 `⚔️【142 刻】你 · 攻击 · 伐木工`。
#     本批给 **52 条活 cue 槽位**的行首加了 `【N 刻】` —— 引擎 `901c8d8` 的 `TIME_SLOT`
#     已给**每条** cue 的 payload 补 `t`，上一轮记的硬阻塞（62 个槽位拿不到刻）到此解除。
#     ⇒ 逐字对账里变的**只有战斗日志那几行**，且只多一段刻数
#     （`🌀 单人 开始出招…` → `🌀【226 刻】单人 开始出招…`：括号顶掉图标后那一个空格，
#      与真源样例逐字同形）：
#       · 攻击（11 行不变）4 行变 · 战斗日志（6 行不变）4 行变 · 防御（10 行不变）3 行变
#       · 状态（4 行）**逐字相同** · `save`（hp/gold/exp/bag…）**逐字相同**（只改措辞）
#     ★ 新旧两份 `--dump` 逐行 diff 过（脚本自检：save 逐字相同 + 每条指令行数不变
#       + 每处差异只能是「行首 `【N 刻】` 顶掉一个空格」，共 11 处）。
#     ★ 判据本身**一个字没改宽**：仍是「这一段的回话与基线**逐字**相同」。
#   来历 = 本批基线 **3ee9148** 那棵树上跑 `python scripts/probe_instance.py --dump`
#   （同一段脚本、同一套夹具、同一个种子）打出来的**逐字回话 + 档上那几格**。
#   `--dump` 在改前那棵树上也跑得动（那支不 import `content.instance`）。
#
#   ★★ P0-4（2026-09-29 · 文案修复车道 P0）再刷新一次（**只动 4 行**）：
#:   `COMBAT_SCHEDULE_ACTOR_TURN`（旋律 `battle.schedule.actor_turn`）的值改成
#:   `🌀【N 刻】… 行动`。取证：`e2e_drive.py` 真打一场，
#:   旧的 `—— 田鼠 行动 ——` 是整场战斗日志里**唯一**无刻数且无行首图标的行
#:   （日志里其余每一行都带 `🌀【N 刻】`）。真源 26_ §三 优化 1
#:   逐字「所有战斗日志行统一以【N 刻】开头」。
#:   本次新旧两份 `--dump` 逐行 diff：变的**只有这 4 行**（四个指令段各 1 行），
#:   每处差异都是同一个变形（`—— X 行动 ——` → `🌀【N 刻】X 行动`，名字逐字不变），
#:   每个指令段**行数不变**，`save`（hp/gold/exp/bag…）**逐字相同**。
#:   判据本身一个字没改宽（仍是逐字对账）。
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
#
#   ★ ★ Q-22 补（2026-09-26 · 分支 `fxd`）第五次刷新 —— 同样是**有意的口径变更**（这一支没动一行）：
#     三张野外图的 `name` 从「北带 · 骨田 / 东带 · 白桦林 / 西带 · 浅滩」改成**区域名**「北带 / 东带 / 西带」。
#     起因：试玩 P3 复测（全新玩家）报「站在拾荒营地，`状态` 与 `观察` 的标题都还写着『北带 · 骨田』」——
#     那一串是早先批次把「带名 · 入口节点」拼成一个字段留下的（真源 `06_/00_第一阶段内容总纲` 那张表里
#     地带叫**北带**，骨田是它的第一个节点 ⇒ 站在别处时那句话就是错的）。
#     ⇒ 逐字对账里唯一变的一行是「…在 北带 · 骨田」→「…在 北带」（新旧两份 `--dump` 逐行 diff 过：
#       5 条指令 · 5 条 row 只差这 1 行 · `save` 那几格逐字相同）。
#       —— 变的只是那份快照的**基准树**（旧基准记的是改前的行为，留着就永远对不上了）。
#       新口径的常驻判据在 `scripts/probe_battle_turns.py` ①（一手一推进 · 分段版与一次结算版两态对照）。
#
#   ★ ★ Q-22 补（2026-09-26 · 分支 `fxd`）第五次刷新 —— 同样是**有意的口径变更**（这一支没动一行）：
#     三张野外图的 `name` 从「北带 · 骨田 / 东带 · 白桦林 / 西带 · 浅滩」改成**区域名**「北带 / 东带 / 西带」。
#     起因：试玩 P3 复测（全新玩家）报「站在拾荒营地，`状态` 与 `观察` 的标题都还写着『北带 · 骨田』」——
#     那一串是早先批次把「带名 · 入口节点」拼成一个字段留下的（真源 `06_/00_第一阶段内容总纲` 那张表里
#     地带叫**北带**，骨田只是它的第一个节点 ⇒ 站在别处时那句话就是错的）。
#     ⇒ 逐字对账里唯一变的一行是「…在 北带 · 骨田」→「…在 北带」（新旧两份 `--dump` 逐行 diff 过：
#       5 条指令 · 5 条 row 只差这 1 行 · `save` 那几格逐字相同）。
#     新口径的常驻判据在 `scripts/probe_maps.py` ⑨（图名是区域名 · 不含自己的节点名）+ 本分支 `_notes.md` §八。
#
#   ★ ★ 夜班试玩 w3（2026-09-27 · 分支 `fix-qa1`）第六次刷新 —— 同样是**有意的口径变更**（这一支没动一行）：
#     战斗屏（四段式①）在「血」那一行后面补了两条读数：`⚡ 法力 {mp}/{mp_max}` 与
#     `🔹【{资源}】{n}/{mx}`（法师的印记 · 骑士的守誓值…名字与上限现取自 `content/rules/resources.json`，
#     层数取自 actor 现成的 `effects[码].stacks` —— 开战摆 0 层那条，不新开账）。
#     起因：六路试玩里有两条（mage 的 c1 与 p3）都报「法师的两个命根子在战斗里一条都看不见」：
#     法力要退出去敲『状态』、印记任何一页都没有（唯一读法是敲一个付不起的技能看它拒绝）。
#     ⇒ 逐字对账里**只多出 6 行**（3 条指令各 2 行：⚡ 法力 50/50 · 🔹【守誓值】12/100 → 24/100），
#       删/改 **0 行** · 命令序列与 `save` 那几格逐字相同（新旧两份 `--dump` 逐行 diff 过）。
#     新口径的常驻判据见 `scripts/probe_battle_turns.py`（战斗屏四段式那一族）与本分支 `_notes.md` §w3。
#   ★ fix-a-screen（2026-09-27 · 显示层那一批）第七次刷新 —— 同样是**有意**的呈现变更
#     （这一支一个字没动；改的是内容侧那一格文案）：`content/rules/battle_text.json` 新声明了
#     引擎槽位 `battle.landing.blocked_amount` ⇒ 那句兜底模板的**半角括号**（全屏唯一一处，
#     骑士路试玩报的「`(格挡后 N 点伤害)` 是全屏唯一的半角括号」）换成 texts 域里那一行。
#     ⇒ 逐字对账里唯一变的一行是「(格挡后 2 点伤害)」→「（格挡后 2 点伤害）」
#     （新旧两份 `--dump` 逐行 diff 过：5 条指令 · 共 37 行只差这 1 行 · `save` 那几格逐字相同；
#       括号以外**逐字节**相同 —— 半角 1 字节 → 全角 3 字节，整份基线只差这 4 字节）。
#     新口径的常驻判据：`scripts/probe_elements.py` ⑨-d（那一屏一个半角括号都不许有）
#     + `scripts/probe_mech.py` ㉑（一笔自付只出一行）。
#     口径依据：措辞归内容侧（引擎只给 key + 兜底模板 + 槽位，`landing.py:170`）。
#   ★ fix-l（2026-09-27 · 夜班修复那一批）第八次刷新 —— 同样是**有意**的呈现变更
#     （这一支一个字没动；改的是内容侧那一屏文案）：`状态` 面板在「手上还留着一场没打完」时
#     多一行（`SYS_STATUS_IN_FIGHT`）。起因：试玩 ranger b38~b40 报「跨进程回来先敲『状态』
#     一个字都不提，直到敲『去 X』被 `SYS_MOVE_IN_FIGHT` 拦下才知道自己走不动」。
#     ⇒ 逐字对账里**只多出 1 行**（第 5 条指令『状态』末行：⚔ 手上这一场还没打完 —— …），
#       删/改 **0 行** · 命令序列与 `save` 那几格逐字相同（新旧两份 `--dump` 逐行 diff 过：
#       5 条指令 · 共 38 行只多这 1 行 · `save` 逐字相同）。
#     新口径的常驻判据：`scripts/probe_copy.py` ⑫-d ①（场在跑 ⇒ 印 · 收掉了 ⇒ 不印，两态互锁）
#     + 同节 ②（野外 `地图` 末行点明回镇的口 · 镇上不印）。
#   ★ 主线（2026-09-27 · 引擎两处口径改动那一批）**第九次刷新** —— 同样是**有意**的行为变更
#     （这一支一个字没动；改的是**引擎**：`Battle.act()` 入口处「防御姿态到期」那条口径）：
#     `_do_defend` 只置 `defending=True`，全仓此前**只有死亡**清它 ⇒ 敲一次『防御』这一场剩下的
#     每一手都被减半（骑士/法师/刺客/狂战四路试玩实测复现）。到期点改到**行动者自己动手那一帧**
#     （= 真源那句「到你下一次行动之前」）。
#     ⇒ 本脚本第 3 条指令（`攻击`）是这个 bug 的**当场证据**：改前那条 row 里第 3 手本该早该失效的
#       减伤**还在**（`（格挡后 2 点伤害）` + `💥 单人 受到 2 点伤害！`），改后回到全额
#       （`💥 单人 受到 4 点伤害！`）⇒ 逐字对账里的差异**只有**这一条指令的 4 行 + 第 5 条那句血量：
#         第 3 手 `158/164` → `156/164` · 去掉 `（格挡后 2 点伤害）` 那一行（12 行 → 11 行）·
#         `save.hp 158 → 156`。命令序列与其余 4 条 row 逐字相同（新旧两份 `--dump` 逐行 diff 过）。
#     新口径的常驻判据：`framework-engine/tests/test_cross_hand_state.py` ①（姿态期内减半 → 自己下一次
#     行动到期 → 到期后全额；含「被控跳过也算一次行动」与「死亡那条老路未改」两态）。
# ★ P2-6（2026-09-28 · 文案车道 aep2）**第十次刷新** —— 同样是**有意**的呈现变更，且**只动了一个字符**（emoji 字形形态）：
#   原因：`COMBAT_CORE_DEFEND` 用的是**裸** `U+1F6E1` 🛡，而同一 codepoint 在本包其余 14 处
#     都带 `U+FE0F`（彩色 emoji 呈现）。同一屏里一处彩色、一处单色描边 → 观感不一致。
#   → 改成带 `U+FE0F`。依据 = 众数（14 : 1），**不是**「想要图标」。
#     另：`U+2694` 也混用两种形态，但那是 2:2 打平 → **刻意不动**（无依据）。
#   ⇒ 逐行 diff 过：5 条指令 · 5 个 row 一一对应，**全副本只差 1 行**（那一行里的
#     🛡 多了一个 `U+FE0F`），删/改 0 行 · `save` 那几格**逐字相同**。
#   常驻判据（只强不弱）：同一 codepoint 不许「带 U+FE0F」与「裸」**同时**
#     出现在文案域里（含反证：塞个裸形态当场红）。
#   ★ 本条**不能当「emoji 覆盖率」类指标**（原话：「适当的 emoji 会更好」）。
#   ★ P0-4（2026-09-28 · 文案车道 aep0）**第十一次刷新** —— 同样是**有意的口径变更**，且**只动两行的两个字**：
#     `06f5fc5` 修掉了战斗族的术语违规：槽位 `COMBAT_TURN_FOE_DOING`（读端 content/instance.py:767）
#     原值「那一手还有 {left} **秒**落到你身上」—— 读端给的是 `cast_done_at - now`，即引擎 CTB 的
#     **刻数**（1 刻 = 1 游戏秒，但传递单位只许写「刻」，三词守账：刻 / 行动机会 / 结算跳数）
#     ⇒ 原句把刻数说成秒数，快慢不可比。**真源 `17_文案收口口径_v1.md:1085` 那一行的来源列
#     自己就写着「剩几刻」**，与字面偏离 ⇒ 那是真字面错，不是口径变更。
#     ★ 那一笔**只改了 texts 的值 + DOC_PENDING 登记**，**没顾上刷新这份冻结基线**
#       ⇒ ⑤ 那条「逐字相同」判据当场红（红的就是这 2 行）。本提交**只把这两行跟成「刻」**。
#     ⇒ 逐行 diff 过：5 条指令 · 5 个 row 一一对应，**全副本只差 2 行**（两行都只差「秒」→「刻」
#       这一个字），删/改 0 行 · 每条指令行数不变 · `save` 那几格**逐字相同**（hp 156 / gold 30 /
#       exp 0 / bag 伤药×2 / loc belt_north · node bn_bone 全部一致）。
#     ★ 判据本身**一个字没改宽**：仍是「这一段的回话与本基线**逐字**相同」——
#       本条登记只是记下「这次为什么允许差 2 行」，不是把断言放宽。
#     常驻判据（只强不弱）：`scripts/probe_texts.py` 扫描文案域里「回合 / 秒」两个禁词
#       （本轮全包 931 条复核：改完「回合」0 条、「秒」0 条 ⇒ 归零）。
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

    # ── ⑧ ★ 本波：实例/组队/战斗结那一族的四处收口（真宿主真敲 · 两人同场）
    print()
    print("⑧ 本波收口：「你」= 敲指令的人 · 结算一人一段 · 倒下的人那句话 · 败仗不记击杀")
    db = _fresh("fx")
    host, ad = _boot(db, "g_fx")
    _seed("g_fx", "u_a", level=PARTY_LV, cls="cls_knight", name="甲")
    _seed("g_fx", "u_b", level=PARTY_LV + 1, cls="cls_assassin", name="乙")   # 乙快一档（先手好摆）
    INST.party_members = lambda g, u: ["u_a", "u_b"] if g == "g_fx" else [u]
    saved = _pin_encounter("ms_boss_oath_sentry")          # 血厚 ⇒ 够走到「有人倒下 / 全灭」
    _B8 = []
    try:
        random.seed(20260926)
        _drive(host, ad, "u_a", "攻击")                     # 开场那一敲（遇敌只来一次）
        s0 = INST.load("g_fx")
        # ① ★「你」那一格 = **敲指令的人**（直调那一口：两人**各报各的**血）
        _hp_a = INST.hp_of(s0, "u_a")
        _hp_b = INST.hp_of(s0, "u_b")
        _t_a = "".join(INST.turn_lines(s0, "u_a"))
        _t_b = "".join(INST.turn_lines(s0, "u_b"))
        _mx_a = int(INST.actor_of(s0, "u_a")["max_hp"])
        _mx_b = int(INST.actor_of(s0, "u_b")["max_hp"])
        if ("%d/%d" % (_hp_a, _mx_a)) not in _t_a or ("%d/%d" % (_hp_b, _mx_b)) not in _t_b:
            _B8.append(("turn_lines 没按请求者报血", _t_a[:40], _t_b[:40]))
        if _t_a == _t_b:
            _B8.append(("两个人的那一屏一模一样（= 还在报同一个人的血）", _t_a[:40]))
        #   真敲一半：让「第二个人」也真出手 ⇒ 回话里那一行必须是他自己的血
        _o_b1 = _drive(host, ad, "u_b", "攻击")
        if not any(("第 " in x and "手" in x) for x in _o_b1):     # 没轮到他 ⇒ 先让先手那位推一手
            _drive(host, ad, "u_a", "攻击")
            _o_b1 = _drive(host, ad, "u_b", "攻击")
        s1 = INST.load("g_fx")
        _me1 = INST.actor_of(s1, "u_b") if s1 else None
        if _me1 is not None:
            _line1 = [x for x in _o_b1 if ("第 " in x and "手" in x)]
            if not _line1 or ("%d/%d" % (int(_me1["hp"]), int(_me1["max_hp"]))) not in _line1[0]:
                _B8.append(("乙真出手那一敲，报的不是乙自己的血", _line1[:1],
                            int(_me1["hp"]), int(_me1["max_hp"])))
        # ② / ③ / ④：一路打到有人倒下 → 倒下的人敲一条 → 再打到全灭
        _dead_seen, _wipe_lines = None, []
        _n = 0
        while _n < 90:
            _n += 1
            s = INST.load("g_fx")
            if s is None:
                break
            _alive = [m for m in ("u_a", "u_b") if INST.hp_of(s, m) > 0]
            if _dead_seen is None and len(_alive) == 1:
                # ③ 倒下的人敲战斗指令 ⇒ 回的是「倒下了」那句（不是「还没轮到你」）
                _dead_seen = [m for m in ("u_a", "u_b") if m not in _alive][0]
                _od = _drive(host, ad, _dead_seen, "攻击")
                _want = slot("COMBAT_FALL",
                             who=(PS.get_player("g_fx", _dead_seen) or {}).get("name"))
                if _od != [_want]:
                    _B8.append(("倒下的人那一敲", _dead_seen, _od[:3], _want))
                if INST.load("g_fx") is None:
                    break
                continue
            # ★ 全灭（没有站着的了）也是**人敲一下**才收场 —— 那一敲的产出就是「结算那一段」
            _actor = INST.next_actor_key(s) or (_alive[0] if _alive else "u_a")
            _out = _drive(host, ad, _actor, "攻击")
            if INST.load("g_fx") is None:
                _wipe_lines = _out
                break
        # ② ★ 结算**一人一段**（全灭那一下只出一段「眼前一黑」—— 原先 2 人场连着两遍）
        _died = [x for x in _wipe_lines if "眼前一黑" in x]
        if len(_died) != 1 or INST.load("g_fx") is not None:
            _B8.append(("全灭那一下的结算", len(_died), INST.load("g_fx") is not None))
        # ④ ★ 败仗不记击杀（但还是进谱 —— 「见过就是见过」）
        _pk = PS.get_player("g_fx", _dead_seen or "u_a") or {}
        _bk = ((_pk.get("books") or {}).get("monster") or {}).get("ms_boss_oath_sentry")
        if not _bk:
            _B8.append(("输了一场却没进谱（见过的怪照样进）", _bk))
        elif int((_bk or {}).get("kills") or 0) != 0:
            _B8.append(("败仗被记成击杀", _bk))
        if int(((_pk.get("foot") or {}).get("kills") or 0)) != 0:
            _B8.append(("败仗把足迹那本账也加了", (_pk.get("foot") or {}).get("kills")))
    finally:
        _unpin(saved)
        INST.party_members = None
    chk("★ 本波四处收口：「你」= 敲指令的人（直调两人各报各的 + 真敲）· 全灭结算**一人一段**"
        "（只出一段「眼前一黑」）· 倒下的人那一敲出「倒下了」· 败仗**不记击杀**（但进谱）",
        not _B8, "%s" % _B8[:2])

    # ── ⑨ ★ 本波：区域 Boss「只能打一次」（真源 05 §四）——打掉过就不再遇得上
    print()
    print("⑨ 本波：区域 Boss 只能打一次（打掉过 ⇒ 遇敌里不再出现；输掉不算）")
    db = _fresh("boss1")
    host, ad = _boot(db, "g_b1")
    _seed("g_b1", "u_x", level=20, cls="cls_knight", name="甲",
          loc="old_watchtower", node="tower_top")
    saved = _pin_encounter("ms_boss_oath_sentry")
    _B9 = []
    try:
        def _boss_here():
            """真敲一次 `攻击`（先清场 —— 不然第二敲接着上一场打、遇敌那一步根本不走）。

            ★ 清场用的键要走**真宿主那两个参数**（群 + 人）：`_Ad` 只有 `gid` 那个属性，
              `instance.group_of()` 读的是 `env.group_id` —— 拿适配器当 env 会算出 `#u_x`
              这一格，清不着真那一格（第一版就是这么写的，第二敲接着「第 2 手」打）。
            """
            INST.clear(INST.battle_key(types.SimpleNamespace(group_id="g_b1"), "u_x"))
            return _drive(host, ad, "u_x", "攻击")

        def _slain(n):
            """把怪物谱上那一格改成「打过 n 回」（进谱 + 击杀数 —— 这就是那一闸读的账）。"""
            d = dict(PS.get_player("g_b1", "u_x"))
            b = dict(d.get("books") or {})
            b["monster"] = dict(b.get("monster") or {})
            b["monster"]["ms_boss_oath_sentry"] = {"day": 1, "kills": int(n)}
            d["books"] = b
            PS.update_player("g_b1", "u_x", **{k: v for k, v in d.items()})

        _meet_line = slot("COMBAT_MEET", name=MON["ms_boss_oath_sentry"]["name"])
        _o0 = _boss_here()
        if _meet_line not in _o0:
            _B9.append(("打掉之前遇不上", _o0[:2]))
        _slain(1)                                     # 打掉过 ⇒ 这一只不再出现在遇敌里
        _o1 = _boss_here()
        if any(_meet_line in x for x in _o1):
            _B9.append(("打掉过之后还遇得上", _o1[:2]))
        _slain(0)                                     # 只输过（进谱、击杀 0）⇒ 照样遇得上
        _o2 = _boss_here()
        if _meet_line not in _o2:
            _B9.append(("只输过那一场（kills=0）就不让打了", _o2[:2]))
    finally:
        _unpin(saved)
    chk("★ 区域 Boss 只能打一次（真源 `05_玩法数值口径_v1 §四` · 真敲）：打掉过 ⇒ 遇敌里不再出现；"
        "**只输过**（进谱但 kills=0）⇒ 照样遇得上", not _B9, "%s" % _B9[:2])

    # ── ⑩ ★ fix-q：持态中敲『状态』报的是**这一场那一格血**（不是档上那一份）──────────
    #   `instance._write_back` 只把**轮到我那一手**的血落回档 ⇒「别人出手那一手我挨的打」
    #   不在档上（实测 2 人同场：乙出手那一手甲挨 27，档上仍是 284 ⇒ 甲敲『状态』报旧数，
    #   下一手头行才见真数）。这里不靠「怪正好打谁」那种抽签：把这一场那一格**改成与档上
    #   不同的一个数**（档一个字不动），再看『状态』报哪一个 —— 判据咬的是「读的是哪一份」。
    print()
    print("⑩ ★ fix-q：持态中敲『状态』报的是**这一场那一格血**（与 `live_mp` 同一个口）")
    import ast as _ast10
    from content import panel_build as _PB10
    db = _fresh("q")
    host, ad = _boot(db, "g_q")
    _seed("g_q", "u_a", level=PARTY_LV, cls="cls_knight", name="甲")
    _seed("g_q", "u_b", level=PARTY_LV, cls="cls_assassin", name="乙")
    INST.party_members = lambda g, u: ["u_a", "u_b"] if g == "g_q" else [u]
    saved = _pin_encounter(PARTY_MON)
    _B10 = []
    try:
        _o_q = _drive(host, ad, "u_a", "攻击")               # 开场 + 甲先出一手
        _st_q = INST.load("g_q")
        if _st_q is None or not any(("遭遇" in x or "⚔" in x) for x in _o_q):
            _B10.append(("攻击 没开成一场", _o_q[:2]))
        else:
            _pk_q = dict(PS.get_player("g_q", "u_a"))
            _cap_q = int(_PB10.hp_cap(_pk_q))
            _me_q = INST.actor_of(_st_q, "u_a")
            _me_q["hp"] = _cap_q - 37                        # 场里那一格 ≠ 档上那一格
            INST.save("g_q", _st_q)
            _snap_q = dict(PS.get_player("g_q", "u_a"))
            _o_q2 = _drive(host, ad, "u_a", "状态")
            _txt_q = "\n".join(_o_q2)
            if ("生命 %d/%d" % (_cap_q - 37, _cap_q)) not in _txt_q:
                _B10.append(("状态 没报场里那一格血（该 %d/%d）" % (_cap_q - 37, _cap_q), _o_q2[:2]))
            if ("生命 %d/%d" % (int(_pk_q.get("hp") or 0), _cap_q)) in _txt_q:
                _B10.append(("状态 报的还是档上那一份（旧数 %s）" % (_pk_q.get("hp"),), _o_q2[:2]))
            if dict(PS.get_player("g_q", "u_a")) != _snap_q:
                _B10.append(("只读的口把档动了",))
        # 两态互锁：**没有场**的那一位照旧报档上那一格（与接线前逐字相同）
        db2 = _fresh("q2")
        host2, ad2 = _boot(db2, "g_q2")
        _seed("g_q2", "u_c", level=PARTY_LV, cls="cls_priest", name="丙")
        _pk2 = dict(PS.get_player("g_q2", "u_c"))
        _txt_q2 = "\n".join(_drive(host2, ad2, "u_c", "状态"))
        if ("生命 %s/" % (_pk2.get("hp"),)) not in _txt_q2:
            _B10.append(("没有场时没照档上那一格报", _txt_q2.splitlines()[:2]))
        # 覆盖面（静态）：这一格的读数只走 `live_hp` 那一口（谁再直接拿 `p["hp"]` 顶上，这里红）
        _src_q = (REPO / "content" / "cmds_ast.py").read_text(encoding="utf-8")
        _st_fn_q = next((n for n in _ast10.walk(_ast10.parse(_src_q))
                         if isinstance(n, _ast10.AsyncFunctionDef) and n.name == "status"), None)
        _uses_q = [n for n in _ast10.walk(_st_fn_q) if isinstance(n, _ast10.Call)
                   and getattr(n.func, "id", "") == "live_hp"] if _st_fn_q else []
        if len(_uses_q) != 1:
            _B10.append(("status 没走 live_hp 那一口（%d 处）" % len(_uses_q),))
    finally:
        _unpin(saved)
        INST.party_members = None
    chk("★ fix-q 持态中『状态』报**这一场那一格血**（档上那一格只对刚出手的那位是活的）· "
        "只读的口**不动档** · 没有场时照旧报档上那一格 · 读数只走 `live_hp` 那一口"
        "（坏 %s）" % (_B10[:2] or "无",), not _B10, "%s" % (_B10[:2],))
    # ── ⑪ 名单变了（离队 / 解散）：那一场按**现名单**收口（fix-r）────────────
    #   ★ 试玩实测（knight 第 3 轮 · 第 41/42 批 + 第 46~50 批）：`离队` 原先只动队伍名单，
    #     那一格 `instance:<群>` 一个字不碰 ⇒ ① 剩下的人敲『攻击』回「⏳ 还没轮到你 ——
    #     你在等 <已经走掉的那位>」（只能等 45 秒窗口过期）② 队散了再开一场 ⇒ 被塞回那场
    #     没打完的旧仗（幽灵成员）。本节的判据 = `instance.leave_reconcile` 那三条口径，
    #     全部**真敲指令**（队伍 / 邀请 / 同意 / 攻击 / 离队 都是真命令，不注入队伍口）。
    print()
    print("⑪ 名单变了：离队 ⇒ 走的人从**这一场**摘掉（剩下的人接着打）· 剩 ≤1 人 / 解散 ⇒ 这一场收掉")
    db = _fresh("lv")
    host, ad = _boot(db, "g_lv")
    _seed("g_lv", "u_a", name="甲", level=PARTY_LV, cls="cls_knight")
    _seed("g_lv", "u_b", name="乙", level=PARTY_LV, cls="cls_assassin")
    _seed("g_lv", "u_c", name="丙", level=PARTY_LV, cls="cls_ranger")
    saved = _pin_encounter(PARTY_MON)
    _B11 = []

    def _names11(mem):
        return sorted(str(x) for x in (mem or []))

    def _sides_uids11(st):
        return [str(a.get("uid") or "") for a in (INST.players_of(st) if st else [])]

    try:
        _drive(host, ad, "u_a", "队伍")
        _drive(host, ad, "u_a", "邀请 乙")
        _drive(host, ad, "u_b", "同意")
        _drive(host, ad, "u_a", "邀请 丙")
        _drive(host, ad, "u_c", "同意")
        _drive(host, ad, "u_a", "攻击")                       # 三个人真进同一场
        _st0 = INST.load("g_lv")
        if _st0 is None or _names11(_st0.get("members")) != ["u_a", "u_b", "u_c"]:
            _B11.append(("三个人没进同一场", None if _st0 is None else _st0.get("members")))
        # ① 队员退（三个人里走一个）⇒ **只**把他从这一场摘掉（members 与 sides 一起）
        _drive(host, ad, "u_b", "离队")
        _st1 = INST.load("g_lv")
        if _st1 is None or _names11(_st1.get("members")) != ["u_a", "u_c"] or "u_b" in _sides_uids11(_st1):
            _B11.append(("走的人没从这一场摘干净",
                         (None if _st1 is None else _st1.get("members"), _sides_uids11(_st1))))
        elif str(INST.key_of("g_lv", "u_a", INST.members_of("g_lv", "u_a"))) != "g_lv":
            _B11.append(("剩下的人这一场的键跑偏了", INST.members_of("g_lv", "u_a")))
        #   剩下的人真能接着打：轮转不再落在走掉的那位身上
        _hands0 = int((_st1 or {}).get("hands") or 0)
        _o2 = _drive(host, ad, "u_a", "攻击")
        _st1b = INST.load("g_lv")
        if _st1b is not None and str(INST.next_actor_key(_st1b) or "") not in ("u_a", "u_c"):
            _B11.append(("轮转还指着走掉的人", INST.next_actor_key(_st1b)))
        if _st1b is not None and int(_st1b.get("hands") or 0) <= _hands0 \
                and not any("还没轮到你" in _x for _x in _o2):
            _B11.append(("剩下的人敲『攻击』什么都没发生", _o2[:3]))
        # ② 摘完只剩一个人 ⇒ 这一场**收掉**（键按名单分：留着就是下一批人踩的坑）
        _drive(host, ad, "u_c", "离队")
        if INST.load("g_lv") is not None:
            _B11.append(("只剩一个人还留着那一场", INST.load("g_lv").get("members")))
        # ③ 走的人**本来就不在这一场**里 ⇒ 一个字都不动（这一场照跑）
        _drive(host, ad, "u_a", "队伍")
        _drive(host, ad, "u_a", "邀请 乙")
        _drive(host, ad, "u_b", "同意")
        _drive(host, ad, "u_a", "攻击")
        _st2 = INST.load("g_lv")
        if _st2 is None or _names11(_st2.get("members")) != ["u_a", "u_b"]:
            _B11.append(("两人场没开起来", None if _st2 is None else _st2.get("members")))
        else:
            _r3 = INST.leave_reconcile("g_lv", "u_c", ["u_a", "u_b"])   # 丙不在这一场里
            _st2b = INST.load("g_lv")
            if _r3.get("action") != "none" or _st2b is None \
                    or _names11(_st2b.get("members")) != ["u_a", "u_b"]:
                _B11.append(("不在这一场里的人也该什么都不动", (_r3, None if _st2b is None
                                                              else _st2b.get("members"))))
        # ④ 队长退 = **解散** ⇒ 这一场收掉（队没了，键也不再是群）
        _drive(host, ad, "u_a", "离队")
        if INST.load("g_lv") is not None:
            _B11.append(("解散之后那一场还留着", INST.load("g_lv").get("members")))
        # ⑤ 手上没有场 ⇒ 什么都不动（两条「none」分支的另一条）
        _lr = getattr(INST, "leave_reconcile", None)      # ★ 这一口没了 ⇒ 这一节照实红（不炸整支）
        if _lr is None:
            _B11.append(("没有 `instance.leave_reconcile` 这一口", None))
        else:
            _r5 = _lr("g_lv", "u_a", ["u_b"])
            if _r5.get("action") != "none":
                _B11.append(("没场时不该动", _r5))
    except Exception as _exc:                             # noqa: BLE001
        _B11.append(("这一节真跑炸了", repr(_exc)))
    finally:
        _unpin(saved)
    chk("★ 名单变了（离队 / 解散）⇒ 那一场按**现名单**收口（真敲：队伍→邀请→同意→攻击→离队）："
        "走的人从 members 与 sides **一起**摘（剩下的人接着打、轮转不再落在他身上）· "
        "摘完 ≤1 人 / 队长退（解散）⇒ 这一场收掉 · 人不在这一场里 / 手上没场 ⇒ 一个字都不动",
        not _B11, "%s" % _B11[:2])

    # ══ P2-6（文案车道 aep2）· emoji 字形形态一致性 ══
    # ★ 判据口径（只强不弱）：**同一个 codepoint 不许带 U+FE0F 与裸形态同时出现**。
    #   理由 = 观感（一处彩色一处单色描边 = 同一个图标长得不一样）。
    #   ★ 本条**不管「覆盖率」、不管「每界面至少 N 个图标」** —— 原话是
    #     「适当的 emoji 会更好」，把优点当指标会让别的线为凑数脏加图标。
    _mixed = {}
    for _k, _v in (TX or {}).items():
        _s = str((_v or {}).get("value") or "")
        for _i, _ch in enumerate(_s):
            _o = ord(_ch)
            if not ((0x1F300 <= _o <= 0x1FAFF) or (0x2600 <= _o <= 0x27BF)
                    or (0x2B00 <= _o <= 0x2BFF)):
                continue
            _vs = (_i + 1 < len(_s)) and (_s[_i + 1] == "️")
            _mixed.setdefault(_o, {True: [], False: []})[_vs].append(_k)
    _bad_mixed = {hex(_o): (v[True][:2], v[False][:2]) for _o, v in _mixed.items()
                  if v[True] and v[False]}
    chk("★ P2-6 emoji 字形形态：同一 codepoint 不同时出现「带 U+FE0F」与「裸」"
        "（同一个图标长得不一样 = 观感破功；不管覆盖率）",
        not _bad_mixed, "%s" % (_bad_mixed,))
    # 反证（不弱化判据）：拿一个**已统一**的 codepoint，强行混入裸形态
    #   → 上面那条必须变红。（否则这条判据可能是死的）
    _uni = [o for o, v in _mixed.items() if v[True] and not v[False]]
    if _uni:
        _cp = _uni[0]
        _k0 = _mixed[_cp][True][0]
        _bad_val = (str(TX[_k0]["value"])[:1] + chr(_cp)
                    + str(TX[_k0]["value"])[1:])          # 首个字符前插一个同 codepoint 裸形态
        _t = {}
        for _k, _v in TX.items():
            _s = _bad_val if _k == _k0 else str((_v or {}).get("value") or "")
            for _i, _ch in enumerate(_s):
                _o = ord(_ch)
                if ((0x1F300 <= _o <= 0x1FAFF) or (0x2600 <= _o <= 0x27BF)
                        or (0x2B00 <= _o <= 0x2BFF)):
                    _t.setdefault(_o, {True: 0, False: 0})[
                        ((_i + 1 < len(_s)) and (_s[_i + 1] == "️"))] += 1
        chk("★ P2-6 反证：归一形态的 codepoint 被塞个裸形态 → 上一条当场红"
            "（否则判据可能是死的）",
            bool(_t.get(_cp, {}).get(True)) and bool(_t.get(_cp, {}).get(False)),
            "cp=%s 槽位=%s" % (hex(_cp), _k0))

    print()
    print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
    return 0 if ok else 1


if DUMP:
    print(json.dumps(solo_transcript(), ensure_ascii=False, sort_keys=True))
    sys.exit(0)

if __name__ == "__main__":
    sys.exit(main())
