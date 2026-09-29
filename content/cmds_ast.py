# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体（第一版 · 最小可玩集）。

契约（引擎 `saintess_engine.command.binding`）：实现体是 **async generator**，
`yield` 出行文本；调用帧 `handler(sink, *args)`（`args` 只有 group_id/uid/player 三槽位）。

本文件**只读本包自己的数据**（`content/data/*.json`），不 import 宿主、不 import 扩展包
（接线在 `apply.py`）。玩家档的形状见 `content/persistence.py`。
"""
from __future__ import annotations

import json
import logging
import os

from . import calendar as CAL        # 时辰/天气的唯一出口（它不 import 本模块，无环）
from . import codex as CX            # 图鉴四谱的唯一记录口（B2-7）
from . import eggs as EG              # 彩蛋（B3-1）：条件在 eggs 域，判定走引擎声明算子
from . import alloc as AL             # ★ P-34：加点算术的唯一出口（等级→总点数−已花=余额）
from . import titles as TT            # 称号（B3-2）：显示跟着名字走 · 判定在 titles 域
from . import scene as SC           # 场景槽位解析（B3-6a）：节点级近景 → 退地图级第一眼
from . import timed_events as TE     # 限时事件那一格（B3-5）：宿主维护门落档 · 这里只读
from . import affix as AFFIX
from . import explore as EX          # ★ fxexp：探索遇怪的概率与掷骰（唯一出口 · 表在 rules/）
from . import argv as AV          # ★ B4-11：取参的唯一口（零依赖 ⇒ 本模块也能 import）         # ★ B3-24：精英词条（观察那行预告 = 遭遇的同一个种子）
from . import onboard as OB       # ★ copy-p5：引导层（B 档「有目标感」）—— 只 import，不反向依赖

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_CACHE: dict = {}


def _data(name: str):
    if name not in _CACHE:
        with open(os.path.join(_DIR, name + ".json"), encoding="utf-8") as f:
            _CACHE[name] = json.load(f)
    return _CACHE[name]


def _texts():
    return _data("texts")


#: 取不到文案时 `T` 回的那串标记（**真源** · fail-closed：宁可当场显形，也不静默编一句）。
#: ★ 全包**只有这一处**写得出它 —— 别处要判「取不到文案」就 import 这个常量
#:   （审计 L2212 / L2614：原先 4 处逐字硬编码，改上游标记文案时下游 3 处静默失效）。
MISSING_MARK = "[MISSING TEXT"


#: ★ 机器侧诊断的 logger（玩家可见文本禁机器键 ⇒ 细节只进这里；台账 L2154）
_LOG = logging.getLogger("aetheran.alloc")


def T(key: str, **slots):
    """取一条文案（fail-closed：缺 key 直接回显 key，不静默）。"""
    rec = _texts().get(key)
    if not rec:
        return "%s: %s]" % (MISSING_MARK, key)
    s = rec.get("value", "")
    for k, v in slots.items():
        s = s.replace("{%s}" % k, str(v))
    return s


# ── 「待槽位」两处（★ P-50 / P-68 · 2026-09-26 本波 w-h-ux）────────────────────
#: 真源已经点名了这两处玩家可见的位置、**句子还没写成真源行**（因此 texts 域里也没有那条槽位）：
#:   · `cls_edge`    建号第二步那一眼 —— 真源 `06_第一阶段垂直切片/18_建号与新手引导_v1.md §一 第 2 步`
#:                   「显示 职业名 · 节奏来源一句话 · **优势 / 弱点** · 一句自述」；
#:   · `origin_home` 「出身」那一屏 —— 真源 `06_第一阶段垂直切片/04_指令总表.md §三` 的 `出身` 那一行
#:                   （本波裁：那一行加「家乡与寿数」，见本分支 `_notes.md §真源行`）。
#: 口径（fail-closed · **两态都绿**）：
#:   · 域里那一格 + texts 里那条槽位**都在** ⇒ 这一行出；
#:   · 缺任何一头（今天就是这一态）⇒ **少这一行** —— 不补替身、也不印 `[MISSING TEXT]`；
#:   · **半截**（加了域没加槽位 / 加了槽位没加域）⇒ 探针当场红（`probe_class ⑭` / `probe_races ⑫`）。
#: 键名写在这张表里、**不是** `T("…")` 直调：`probe_copy ④` 查的是「代码 `T()` 引用的键都在 texts
#:   里」，而待槽位**本来就不在** —— 直调会把那一条判据打红。走这张表，由上面那两条判据把
#:   「还缺哪一头」逐条印出来；真源行落地 + 主线跑 `scripts/rebuild_syscopy.py` 之后自动开始出。
PENDING_SLOTS = {
    "cls_edge": "SYS_CLS_EDGE",          # P-50 · 优势 · {adv} ｜ 弱点 · {weak}（classes.adv / classes.weak）
    "origin_home": "SYS_ORIGIN_HOME",    # P-68 · 家乡 · {home} ｜ 寿数 · {life}（races.home / races.lifespan）
}


def _pending_line(slot, **slots):
    """待槽位那一行：texts 里真有这条槽位才给（缺 = `None` —— 不编、也不印 MISSING 标记）。"""
    if slot not in _texts():
        return None
    return T(slot, **slots)


def _cls_edge_line(rec):
    """建号第二栏（优势 / 弱点）那一行 —— 域里**两句都在** 且 texts 里有槽位才给，否则 `None`。

    ★ 半截也不算数：只写了优势没写弱点（或反过来）⇒ 少这一行（宁可少一行，不许只印半句）。
    """
    adv = str((rec or {}).get("adv") or "").strip()
    weak = str((rec or {}).get("weak") or "").strip()
    if not (adv and weak):
        return None
    return _pending_line(PENDING_SLOTS["cls_edge"], adv=adv, weak=weak)


def _origin_home_line(rec):
    """「出身」那一屏的家乡与寿数那一行（★ P-68）—— 两格都在 且 有槽位才给，否则 `None`。"""
    home = str((rec or {}).get("home") or "").strip()
    life = str((rec or {}).get("lifespan") or "").strip()
    if not (home and life):
        return None
    return _pending_line(PENDING_SLOTS["origin_home"], home=home, life=life)


def _scene_line(loc, node, m=None, empty=False, variant=None):
    """观察那一段场景 —— 节点级 SCENE_<节点>（近景）→ 退 SCENE_<地图>（这张图的第一眼）。

    ★ 解析口只有一处（content/scene.py）—— 落域脚本与这里共用，别各写一遍。
    ★ `empty=True`（本波）：先试「这一站的人都不在」那一版（`SCENE_<节点>_EMPTY`）——
      由调用方按 `content/town.py::station_empty` 判好传进来（画面与名册不许打架，P1 BUG-5）。
    ★ `variant`（★ g4-⑤）：**按状态分支**那一档 —— 先试 `SCENE_<节点>__<状态大写>`
      （今天只有白烛堂的满血版）；状态名由调用方判好传进来，这一层不认识「血」。
    """
    sk = SC.resolve(_texts(), loc, node, empty=empty, variant=variant)
    m = m if m is not None else (_map_of(loc) or {})
    if sk:
        return T(sk, name=m.get("name", loc))
    return "【%s · %s】" % (m.get("name", loc), _name_of_node(loc, node))


def scene_variant_of(p):
    """观察那一段场景要不要走「按状态分支」那一档（★ g4-⑤）—— 今天这一档 = **满血**。

    为什么在 `cmds_ast`（不在 `scene`）：判断要看**面板**（上限的唯一来源 = `hp_cap_or_line`），
    而 `content/scene.py` 是零依赖模块（落域脚本要用它）。
    判不了的档（还没择业 / 档上没有 hp）⇒ `None`（回落基础那一段，fail-closed：不假装满血）。
    """
    cap, _line = hp_cap_or_line(p)
    if cap is None or p.get("hp") is None:
        return None
    try:
        return SC.VARIANT_FULL if int(p.get("hp")) >= int(cap) else None
    except (TypeError, ValueError):
        return None


def npc_when_slot(nid) -> str:
    """这一位「他什么时候在」的槽位键 —— `NPC_WHEN_<id 去掉 npc_ 前缀 · 大写>`（唯一写法）。"""
    tail = str(nid).upper()
    if tail.startswith("NPC_"):
        tail = tail[4:]
    return "NPC_WHEN_%s" % tail


def npc_gone_lines(loc, node, p, st=None) -> list:
    """这一站**按作息还没来**的那几位 —— 每人一行（31_NPC作息 §四「人不在也要有戏」）。

    ★ 与「人不在那一版场景」（`SCENE_<节点>_EMPTY`）同一个判据来源（`town.absent_here`）——
      画面 / 名册 / 这一行三处不许各说一套（P1 BUG-5 那一族）。
    ★ 只对**基位在这一站**的人说（路过的人不在此列）；一位都不欠 ⇒ 空表（调用方走原来那句）。
    """
    from .town import absent_here
    out = []
    for nid, rec in absent_here(loc, node, p, st):
        slot = npc_when_slot(nid)
        if slot not in _texts():
            continue                                  # 没写「他什么时候在」的位不出声（不编）
        out.append(T("SYS_WHO_GONE", name=_poi_label(rec), when=T(slot)))
    return out


def _map_scene(loc):
    """踏进这张图的第一眼（野外带到达时显示）—— 只取地图级槽位，取不到退回一行占位。"""
    sk = SC.resolve_map(_texts(), loc)
    if sk:
        return T(sk)
    return "【%s】" % ((_map_of(loc) or {}).get("name", loc))


# ── 玩家档（形状：location/level/race/class/name/hp…）──────────────
#: ★ P-27：档上**不写** `hp` / `hp_max` —— 生命上限只有一个来源（职业面板），
#:   由 `_p()` 出档时按面板派生（原先这里与 `apply.initial_save` 各写死 100 ⇒ 两个源）。
#: ★ B4-8：`mo` / `mo_max` 同理撤掉（原先两处写死 0 ⇒ `状态` 恒「法力 0/0」而面板是 50）——
#:   两个上限都只认面板那一个来源。
#: ★ B4-12：镇子那张图的 id —— **唯一一份字面量**（本包的守卫 / 起点 / 出口都走它；
#:   宿主那半边 `apply.py` 的初始档自己写了一份，见 `probe_cmds ⑰` 的覆盖面那一支）
TOWN = "windmill_town"

DEFAULT_PLAYER = {
    "name": "", "race": "", "cls": "", "level": 1, "exp": 0,
    "loc": TOWN, "node": "wt_gate_n", "prev": [],
    "gold": 30, "bag": {}, "equipped": {}, "flags": {}, "codex": {},
}

#: ★ 复活点（`00_总纲/03_主要玩法 §4.9`「回白烛堂」）—— 风车镇的节点 id（探针核它是真节点）
CHAPEL = (TOWN, "wt_chapel")

#: ★ P-69（2026-09-26 · 本波 w-h-ux 裁）：建号是这四步，**第 4 步「出身」并进第 1 步**。
#:   真源 `06_第一阶段垂直切片/18_建号与新手引导_v1.md §一` 把第 4 步写成**单独一步**
#:   （「这一步只给一个选项（确认）」）—— 本路裁：**不拆**。依据两条：
#:     ① 那一步的**内容**（那句「为什么来」）本来就在第 1 步里：六族菜单每一行末尾带的就是它，
#:        定族那一下（`SYS_RACE_DONE`）再念一次 —— 拆出去等于把同一句话问两遍；
#:     ② 「只给一个确认」的一屏是纯点击：**少一屏就少一个放弃点**（建号这段每多一步都在掉人）。
#:   跟着来的两件事：`04_指令总表 §三` 的 `出身`（守卫「随时」）是**回看口**、不是建号那一步；
#:   `18 §六` 的实现状态那一行记成「已裁：并进第 1 步」。判据 = `scripts/probe_race.py ⑨`。
BUILD_STEPS = ("race", "class", "name", "town")


def exp_need(level):
    """升一级所需经验 —— **唯一真源**：交活升级与死亡惩罚都走这一个口。

    ★ 曲线**已定格**（2026-09-25）：真源 `06_第一阶段垂直切片/00_第一阶段内容总纲_v1.md §七`
      写死 `40 × L²`（L1 40 · L10 4,000 · L20 16,000 · 1→20 合计 98,800），并点名
      「原 45 × L^1.5 是旧案 —— 裁定以 40 × L² 为准」⇒ 下面的实现就是它，本包不再有第二处。
      对账与守卫：`scripts/probe_quests.py` ⑧-c（与 §七 现算逐点对账 + 全包代码落点只有这一处）。
      （P-37 那条旧账 —— B3-14 之前本包与探针各手打过一份曲线 —— 已收成这一处。）
    """
    lv = max(1, int(level or 1))
    return lv * lv * 40


def exp_of_kill(monster_level):
    """打怪给的经验 = **同级升级需求的 1/40**（`00_第一阶段内容总纲_v1 §七` 经验产出）。

    「同级」= 那只怪**自己**的等级 ⇒ 同级打同级平均 **40 只升一级**（精英 / 头目天然更高，
    它们等级本来就高）。★ 分母不手打：走 `exp_need` 一个口 —— 曲线一旦定下来（P-22），
    这里自动跟着变。
    """
    lv = max(1, int(monster_level or 1))
    return max(1, int(round(exp_need(lv) / 40.0)))


def add_exp(p, n):
    """加经验并结算升级 —— 升级判定**唯一口**（打怪与交活都走它）。返回升了几级。

    曲线只认 `exp_need`；经验**跨级结转**（一次加很多也能连升几级）。
    """
    p["exp"] = int(p.get("exp") or 0) + int(n or 0)
    lv = int(p.get("level", 1) or 1)
    ups = 0
    while p["exp"] >= exp_need(lv):
        p["exp"] -= exp_need(lv)
        lv += 1
        ups += 1
    if ups:
        p["level"] = lv
    return ups


def _save_why(exc: Exception) -> str:
    """落库失败**说给玩家听**的那一句原因 —— 异常的类名 + 它自己带的话。

    ★ 为什么要点名到「类名 + 原话」而不是笼统一句「存不上」：`except Exception: pass`
      那一支之所以是「高」级静默失败，正是因为它**什么都不说** —— 玩家拿到一句「做成了」，
      重连之后发现东西没了，却不知道发生过什么。把真因摊开，维护的人与玩家都看得见。
    ★ 不用玩家看不懂的机器词，但也不许把它藏起来：类名（`OSError` / `RuntimeError` …）是
      这套仓通篇的错因写法（`SYS_ALLOC_BAD_SAVE` 的 `{why}` 同款），不是新发明。
    ★ 空消息（`Exception()` 什么都不带）也有下文，不会印出一个空白的「：」。
    """
    msg = str(exc).strip()
    return ("%s: %s" % (type(exc).__name__, msg)) if msg else type(exc).__name__


def _save(env):
    """★ 落档是处理器的责任（引擎 2026-09-15 起不再每条消息整档回写）。

    ★★ 2026-09-28 审计 B 车道高①（原先这里是 `try: env.save() / except Exception: pass`）：
      `_save` 是**全包唯一落档口**（`cmds_battle` 等 16 个文件共 60 个调用点都走它）
      ⇒ 那一行 `pass` 是**一次落库失败 ⇒ 全包 30+ 条指令都回一句「做成了」而档没落**，
      玩家零可见（实测：把 `save_player` 弄抛，敲『往北』照样收到「你走出北门」两屏，
      重连后位置弹回原处）。这是「不静默兜底」铁律上最该先拆的一处。
    ⇒ **不吞**：落库失败一律把**原因**交回调用方，由调用方点名给玩家（`SYS_SAVE_FAIL`），
      并且**当次操作的成功话术一并作废**（不许一边说「做成了」一边没存上）。
      返回值 = `None`（存上了）or 原因字符串（没存上）；`env` 为空（无落档上下文）按**存上了**算
      —— 那是「这一下本来就不改档」的读路径（`title_lines` / `egg_lines` 允许 `env=None`）。

    ★ 为什么不干脆往上抛：实测引擎 `runtime.invoke` **不接处理器异常** ⇒ 抛出去 = 玩家收到
      **0 行**（比现在还糟：连场景描述都没了，而且对玩家仍然是静默）。命名 + 当场点名才是
      这个引擎面上唯一能让玩家看见的路（另两条车道正在改引擎的那几处）。

    ★ 调用方的统一写法（16 处逐字同形；本包**不另发明一个包一层 try 的包装函数** ——
      那正是把问题重新藏起来）：生成器实现体

          _bad = _save(env)
          if _bad:
              yield T("SYS_SAVE_FAIL", why=_bad)
              return                       # ★ 当次操作的成功话术一并作废

      交 list 的那两个（`title_lines` / `egg_lines`）把 `yield`/`return` 换成 `return [那一行]`。
    """
    if env is None:
        return None
    try:
        env.save()
    except Exception as exc:                      # noqa: BLE001 —— 这里就是「接住并点名」那一口
        return _save_why(exc)
    return None


#: ★ B3-12（K57 的活口）：默认档里的**可变容器** —— 出档一律换新对象，别把默认档当草稿纸
_MUTABLE = ("bag", "equipped", "flags", "codex", "alloc")


def _fresh(base) -> dict:
    """一份可以随便改的玩家档（四个容器各拷一层；`prev` 只用重建、没人原地加）。"""
    out = dict(base)
    for _k in _MUTABLE:
        _v = out.get(_k)
        if isinstance(_v, dict):
            out[_k] = dict(_v)
    return out


def _p(player):
    """玩家档（引擎给的是 dict；缺字段用默认值补齐 —— 不改原档）。

    ★ B3-12：`dict(DEFAULT_PLAYER)` 只是**浅**拷贝 —— `bag / equipped / flags / codex`
      这四个值仍是默认档里的**同一个对象**。谁在原地改（`loot.add_to_bag` 就是
      `setdefault` + 原地写）就把默认档改脏：进程内跨玩家串档、探针之间也串。
      ⇒ 出档一律走 `_fresh()`（默认档那一边、引擎给的档那一边，两边都不当草稿纸）。
      判据：probe_copy ⑬（真跑完一遍之后默认档四个容器必须原样 + 半截老档采集不串给下一个人）。

    ★ P-27：**生命上限只有一个来源 = 职业面板**（`panel_build.hp_cap`）—— 出档口现算一遍写
      进这份档：档上那格 `hp_max` 是**派生值**（不是真源，也不许再写死 100）。档上没有职业
      （建号第二步「选职业」还没走完）⇒ 上限**未定**：这一格干脆不写，读它的人走 `hp_cap()`
      （缺了当场喊，不许猜数）。判据：probe_panel 的「三处一致」那一节。
    """
    p = dict(DEFAULT_PLAYER)
    if isinstance(player, dict):
        p.update(player)
    p = _fresh(p)
    if not isinstance(p.get("prev"), list):
        p["prev"] = []
    from . import panel_build as _PB                       # 本地 import：避免包装载期成环
    cap = _PB.hp_cap(p, strict=False)                      # 无职业 ⇒ None（未定）
    if cap is None:
        p.pop("hp_max", None)                              # ★ 别把旧档上写死的 100 当上限留着
        p.pop("hp", None)
    else:
        p["hp_max"] = cap
        p["hp"] = max(1, min(int(p.get("hp") or cap), cap))   # 现血跟着同一个上限（满血起手）
    # ★ B4-8：**法力上限**同样只有面板一个来源（`mp_cap`，与生命那把尺同一把）——
    #   档上 `mo_max` 这一格原先零写端（两个初始档都写死 0）⇒ `状态` 恒显示「法力 0/0」，
    #   而面板里骑士是 50 ⇒ 同一件事两处口径。
    # ★ P-51（2026-09-26）：现蓝的口径**已定**（不再挂账）—— 走唯一一口 `mana.initial_mp`
    #   （档上有那一格 ⇒ 照它并钳到上限；**缺格** ⇒ 面板上限满池）。原先写
    #   `int(p.get("mo") or 0)` = 「每场仗都从 0 起手」⇒ 耗法技能开局一个都放不出来
    #   （与技能表印着「耗法」自相矛盾）。与战斗 actor 的起手（`combat.player_actor`）
    #   **同一口** ⇒ 面板 / 档 / actor 三处一个数；口径与理由见 `content/rules/mana.json`。
    mcap = _PB.mp_cap(p, strict=False)
    if mcap is None:
        p.pop("mo_max", None)                              # 无职业 ⇒ 这一格也不留（照实说未定）
    else:
        from . import mana as _MANA
        # ★ 本批（试玩 A3）：**上限涨了现值跟着涨**（差量补）—— 基线 = 档上那一格「上次派生出来的
        #   上限」。加点 / 升级 / 换装把面板上限推上去时，现值按同一个差量补（唯一口 `mana.on_cap`）
        #   ⇒ 智力 / 意志里那半「+法力」真看得见（改前上限 110→159 而现值恒 110）。
        _prev_cap = p.get("mo_max")
        p["mo_max"] = mcap
        p["mo"] = _MANA.initial_mp(_MANA.on_cap(p.get("mo"), _prev_cap, mcap), mcap)
    return p


def hp_cap(p) -> int:
    """档上的生命上限（**唯一来源 = 职业面板**；`_p` 出档时已按它派生）。

    ★ 缺了（档上没有职业 ⇒ 没有面板 ⇒ `_p` 没写这一格）或者职业不在 `classes` 域里
      ⇒ 当场抛 `PanelMissing`（点名）—— 要数字的地方（回血 / 战斗）宁可报错，也不出假数。
    """
    from . import panel_build as _PB
    return _PB.hp_cap(p)


def hp_cap_or_line(p):
    """档上的生命上限；**档上还没有职业**时回 `(None, 一行点名的 fail-closed 行)`。

    ★ P-27 两档分开（fail-closed 纪律：`fail-closed-boundaries` §1）：

      · 档上没有职业（建号第二步「选职业」还没走完）= **还没声明** ⇒ 这里**不猜数**：
        调用方别做那件事（回血 / 打架），把那一行说给玩家听（自己的槽位 `SYS_HP_UNSET`；
        原先借「效果待接」那两句，2026-09-25 合入时已换回）。
      · 档上的职业**不在 classes 域里** = **声明错了** ⇒ 照样抛（本函数不吞这一档）。
    """
    from . import panel_build as _PB
    cap = _PB.hp_cap(p, strict=False)
    if cap is not None:
        return cap, None
    return None, T("SYS_HP_UNSET", name=p.get("name") or T("SYS_NAME_UNKNOWN"))


def _race_rec(race):
    """档上的族 id（短名：`elf`）→ races 域里那条记录（认不出给空表）。"""
    r = str(race or "").strip().lower()
    if not r:
        return {}
    d = _data("races")
    return d.get("race_" + r) or d.get(r) or {}


def _race_all():
    """六族按 `order` 排（照 02_种族体系 §四 的表序：人类→精灵→矮人→兽人→龙裔→亚人）。

    ★ 别按 id 字母序 —— 那样菜单第一行是「亚人」，玩家最可能选的是排在最后的「人类」。
    """
    d = _data("races")
    return sorted(d.items(), key=lambda kv: (kv[1].get("order") or 99, kv[0]))


async def be_race(env, sink, uid, player):
    """★ 建号：定下自己是哪一族（P-10）。

    为什么需要：原先档上 `race` 恒为空 ⇒ 六族天赋全落空（精灵的「铭文之眼」
    是彩蛋 3 的条件）。档上存**短名**（`elf`）—— 与 `_race_rec` / `eggs.ctx` 一致。
    已经定过的：不再改（免得玩家手滑换族）；要重来是另一件事（没做）。
    """
    p = _p(player)
    want = AV.arg_of(env)        # ★ B4-11：跟着自己的声明剥参（连写也算）
    all6 = _race_all()

    if p.get("race"):
        yield T("SYS_RACE_HAS", name=_race_label(p.get("race")))
        return

    if not want:
        yield T("SYS_RACE_NOARG", all=" · ".join(v.get("name", k) for k, v in all6))
        return

    hit = None
    for k, v in all6:
        if want in (v.get("name"), k, k.replace("race_", "")):
            hit = (k, v)
            break
    if hit is None:
        yield T("SYS_RACE_BAD", want=want, all=" · ".join(v.get("name", k) for k, v in all6))
        return

    kid, rec = hit
    p["race"] = kid.replace("race_", "")
    if player is not None:
        player.update(p)
    _bad = _save(env)
    if _bad:
        yield T("SYS_SAVE_FAIL", why=_bad)
        return
    yield T("SYS_RACE_DONE", name=rec.get("name", kid), line=rec.get("line") or "")
    for tal in (rec.get("talents") or []):
        yield T("SYS_RACE_TALENT", name=tal.get("name", ""), effect=tal.get("effect", ""))
    cost = rec.get("cost") or {}
    if cost:
        yield T("SYS_RACE_COST", name=cost.get("name", ""), effect=cost.get("effect", ""))
    if not p.get("cls"):        # ★ B4-7：建号第二步在等着（定过就不再啰嗦）
        for _h in OB.step_head_lines(p):   # ★ copy-p5：第二步标题块（同一个口，cmds_ast.look 那处同款）
            yield _h
        yield T("SYS_CLS_ASK")


def race_menu():
    """新号第一眼：还没定族就把菜单递过去（`观察` 里用）。"""
    out = [T("SYS_RACE_HEAD")]
    for i, (k, v) in enumerate(_race_all(), 1):
        out.append(T("SYS_RACE_ROW", i="①②③④⑤⑥"[i - 1] if i <= 6 else str(i),
                     name=v.get("name", k), line=v.get("line") or ""))
    out.append(T("SYS_RACE_HOW"))
    return out


def _race_label(race):
    """呈现口用：族 id → 中文名（`elf` → 精灵）；没定给 SYS_UNSET，认不出就原样回显。"""
    if not str(race or "").strip():
        return T("SYS_UNSET")
    return _race_rec(race).get("name") or str(race)


def _cls_label(cls):
    """呈现口用：职业 id → 中文名（`cls_knight` → 骑士）；没定给 SYS_UNSET。"""
    c = str(cls or "").strip()
    if not c:
        return T("SYS_UNSET")
    d = _data("classes")
    return (d.get(c) or d.get("cls_" + c.lower()) or {}).get("name") or c


def _cls_rec(cls):
    """档上的职业 id（`cls_knight`）→ classes 域里那条记录（认不出给空表）。

    与 `_race_rec` 同形：短名（`knight`）也认（域里的键带「cls_」前缀那一份）。
    """
    c = str(cls or "").strip()
    if not c:
        return {}
    d = _data("classes")
    return d.get(c) or d.get("cls_" + c.lower()) or {}


def _cls_all():
    """六门按 `order` 排（真源 `03_职业与技能/08_六职业对照_v2 §一` 的表序：
    骑士 → 狂战士 → 游侠 → 法师 → 修女 → 刺客）。

    ★ 别按 id 字母序 —— 那样菜单第一行是「刺客」（`cls_assassin`），
      而那份对照表把「骑士」放在第一行（玩家最可能选的就是它）。
    """
    d = _data("classes")
    return sorted(((k, v) for k, v in d.items() if isinstance(v, dict) and not k.startswith("_")),
                  key=lambda kv: (kv[1].get("order") or 99, kv[0]))


def _cls_match(want):
    """玩家写的那个词 →（id, 记录）：中文名 / 短名（`knight`）/ 全 id（`cls_knight`）都认。"""
    w = str(want or "").strip().lower()
    if not w:
        return None
    for k, v in _cls_all():
        if w in (str(v.get("name") or "").strip().lower(), k.lower(), k.lower().replace("cls_", "")):
            return (k, v)
    return None


def _cls_star(p, rec):
    """菜单那一行末尾那个星 —— 跟**你选的那一族**的 `recommend` 走（真源 18 §二 推荐组合）。

    `任意`（人类那条）不算推荐：它说的是「哪一门都行」，不该六行全挂星。
    """
    recs = (_race_rec(p.get("race")) or {}).get("recommend") or []
    return T("SYS_CLS_STAR") if rec.get("name") in recs else ""


def class_menu(p) -> list:
    """建号第二步那一眼：每种打法两行（一行是什么人 · 一行什么节奏）。文案一个字都不在这里写。

    ★ fix3-⑦：菜单头原先读 `SYS_CLS_HEAD`（「你是{race}了 —— 还没定下怎么打。」）——
      族是**上一步**刚定过的，这一步再说一遍就是重报（玩家报告 P1 体验-2）。
      换成 `SYS_CLS_LEAD`（「族定了 —— 还没定下怎么打。」）；旧槽位退役登记见
      `scripts/probe_copy.py::RETIRED_DOC`（真源那一行待主线改）。
    """
    out = [T("SYS_CLS_LEAD")]
    for i, (k, v) in enumerate(_cls_all(), 1):
        out.append(T("SYS_CLS_ROW", i="①②③④⑤⑥"[i - 1] if i <= 6 else str(i),
                     star=_cls_star(p, v), icon=v.get("icon", ""), name=v.get("name", k),
                     role=v.get("role", ""), desc=v.get("desc", "")))
        out.append(T("SYS_CLS_MECH", mech=v.get("mech", "")))
        edge = _cls_edge_line(v)        # ★ P-50：优势 / 弱点那一栏（★ 2026-09-26 真源行已落 ⇒ 现在真印）
        if edge:
            out.append(edge)
    out.append(T("SYS_CLS_HOW"))
    return out


def _cls_page(rec) -> list:
    """定过之后再「职业」那一眼 —— 名字 · 定位 · 一句自述 · 节奏（与菜单同一句话，不另写一份）。

    ★ P-50：优势 / 弱点那一栏也是**同一行**（`_cls_edge_line` 一个口）—— 定完还想再读一遍
      那句话的玩家不用回头翻聊天记录。真源行没落 ⇒ 今天这一行同样不印。
    """
    out = [T("SYS_CLS_VIEW", icon=rec.get("icon", ""), name=rec.get("name", ""),
             role=rec.get("role", ""), desc=rec.get("desc", ""), mech=rec.get("mech", ""))]
    edge = _cls_edge_line(rec)
    if edge:
        out.append(edge)
    return out


async def be_class(env, sink, uid, player):
    """★ 建号第二步：定下自己是哪一门（B4-7）。

    为什么需要：档上 `cls` 原先**没有任何写端**（建号只走完了第一步选族）⇒ 新号没有面板：
    `状态` 的生命是「未定」，「攻击」「歇脚」这类要数字的地方全被 fail-closed 挡掉
    （回「职业基础 还没接上」）—— 端到端玩一把就能看到。

    三个触发词一件事：`选职业 <职业名>` 定下来 · 裸 `选职业` / `职业` 看六种打法。
    定过之后再敲 = 看你这一门；带名字想换 ⇒ 明说「已经定了」（换门是 21–40 级的转职，
    真源 18 §五）—— 与 `be_race` 同一条纪律：手滑换门会毁档。
    """
    p = _p(player)
    want = AV.arg_of(env)        # ★ B4-11：跟着自己的声明剥参（连写也算）
    all6 = _cls_all()
    cur = str(p.get("cls") or "").strip()

    if cur:
        rec = _cls_rec(cur)
        if not rec:                                     # 声明错了：不猜、不出假页
            yield T("SYS_CLS_HAS", name=_cls_label(cur))
            return
        for line in _cls_page(rec):
            yield line
        if want:
            yield T("SYS_CLS_HAS", name=rec.get("name", cur))
        return

    if not p.get("race"):                               # 建号第一步还没走完
        yield T("SYS_CLS_NORACE")
        return

    if not want:
        for line in class_menu(p):
            yield line
        return

    hit = _cls_match(want)
    if hit is None:
        yield T("SYS_CLS_BAD", want=want, all=" · ".join(v.get("name", k) for k, v in all6))
        return

    kid, rec = hit
    p["cls"] = kid
    p = _p(p)                       # ★ 出档口现算：上限这一格随职业落地（`hp` 跟着回满）
    if player is not None:
        player.update(p)
    _bad = _save(env)
    if _bad:
        yield T("SYS_SAVE_FAIL", why=_bad)
        return
    yield T("SYS_CLS_DONE", name=rec.get("name", kid))
    yield T("SYS_CLS_MECH", mech=rec.get("mech", ""))
    if p.get("hp_max"):
        yield T("SYS_CLS_HP", hp=p.get("hp"), max=p.get("hp_max"))
    yield T("SYS_CLS_NEXT", left=AL.left_of_record(p), alloc=_alloc_verb())
    if not str(p.get("name") or "").strip():            # 建号第三步（取名）还没走完
        for _h in OB.step_head_lines(p):   # ★ copy-p5：第三步标题块（同上）
            yield _h
        yield T("SYS_CLS_NAME")


def _npcs_here(loc, node, st=None, p=None):
    """这个节点此刻的活人 —— ★ 出场条件（时辰 / 天气 / 事件）现看。

    条件是「与」：写了 time 与 weather 就两个都要满足；`event` 走 `CAL.event_on`
    （★ B3-5：事件层的**唯一口** —— 世界级看主线进度、限时看游戏日窗；认不出的名字给 False）。

    ★ 临时在场（29 §四③「多出 2–3 位 NPC 的临时在场」）：事件给的 `crowd` 名单**覆盖**基位 ——
      被吸走的那些不在原处算在场，只在 crowd 那一站算在场（集日把两位吸到板子那边）。

    ★ `p`：判世界级事件要档（主线过没过）—— **包内调用方都要传**（不传 = 按新档算，
      商队那两位就永远不出现；那是 K65 家族的第二处口径）。
    """
    if st is None:
        st = CAL.state()
    moved = CAL.crowd_roster(st, p)
    out = []
    for k, v in _data("npcs").items():
        spot = moved.get(k)
        if spot is not None:
            if spot != node:
                continue                      # 被事件吸去别处了 ⇒ 基位不算在场
        elif v.get("map") != loc or v.get("subarea") != node:
            continue
        cond = v.get("condition") or {}
        if cond.get("event") and not CAL.event_on(cond["event"], st, p):
            continue
        if not (CAL.allows(cond.get("time"), st) and CAL.allows(cond.get("weather"), st)):
            continue
        out.append((k, v))
    return out


def event_lines(p, loc, node, entered=False) -> list:
    """这一站 / 这一图此刻该出的**世界事件**那几行（B3-5）。

    · 场地那条（`effects.crowd` 的 `node` == 脚下这一站）：随时看得到 —— 那站聚人那一下
    · 事件表征那条（`where` 命中这一图）：**踏进来那一下**才说（进林一句描述 / 进镇一句），
      与 `_map_scene` 同一时机 —— 省得「观察」每次都重念一遍

    口径（29 §四、§五）：世界级（看主线）、限时（看游戏日窗）都走 `CAL.events_now` 一个口。
    """
    st = CAL.state()
    out = []
    for rec in CAL.events_now(st, p):
        if not CAL.where_hit(rec, loc):
            continue
        c = (rec.get("effects") or {}).get("crowd") or {}
        if c.get("node") == node and c.get("text"):
            out.append(T(c["text"]))
        elif entered and rec.get("text"):
            out.append(T(rec["text"]))
    return out


def _map_of(loc):
    return _data("maps").get(loc)


def _node_of(loc, node):
    m = _map_of(loc) or {}
    for n in m.get("nodes") or []:
        if n.get("id") == node:
            return n
    return None


def _neighbors(loc, node):
    """按拓扑算邻居。

    · `star`（城镇）：**全互通** —— 在镇子里走路不该有障碍（玩家体验优先）。
      取「中心 = nodes[0]」是错的：本包节点顺序是「8 场所 + 3 镇口」，
      中心会被算成老风车 ⇒ 北墙根（哈根）永远走不到。
    · `chain`（野外/副本）：线性，取前后。
    """
    m = _map_of(loc) or {}
    nodes = [n.get("id") for n in (m.get("nodes") or [])]
    if node not in nodes:
        return []
    if (m.get("topology") or "chain") == "star":
        return [x for x in nodes if x != node]
    i = nodes.index(node)
    out = []
    if i > 0:
        out.append(nodes[i - 1])
    if i + 1 < len(nodes):
        out.append(nodes[i + 1])
    return out


def _name_of_node(loc, node):
    n = _node_of(loc, node)
    return (n or {}).get("name") or node


def _place_at(name):
    """这个名字（或节点 id）在**哪张图**上 → `(loc, 显示名)`；五张图都没有 → `(None, "")`。

    ★ fix5-nav：**裸站名**那一支要用它 —— 屏幕把地点名用『』写出来（`观察` 的「往哪走」、
      `进镇` 的「能去的地方」），敲下去就该等于 `去 <名>`（P1 BUG-12 / P2 BUG① / P3 体验，
      三个玩家里有三个独立撞上）。名字的真源只有 `maps` 域：逐个图现扫，
      **不手抄一份名字表**（`scripts/rebuild_place_alias.py` 补的别名 pattern 也从同一份现读）。
    """
    want = str(name or "").strip()
    if not want:
        return (None, "")
    for loc, m in (_data("maps") or {}).items():
        for n in (m.get("nodes") or []):
            if want in (n.get("id"), n.get("name")):
                return (str(loc), str(n.get("name") or want))
    return (None, "")



def _move(p, loc, node, sink_lines):
    p["prev"] = (p.get("prev") or [])[-8:] + [(p.get("loc"), p.get("node"))]
    p["loc"] = loc
    p["node"] = node
    CX.note_visit(p, loc, node)               # ★ 记录（去过哪儿）
    CX.note_step(p, loc, node)                # ★ B3-2：记一趟（「骨田的常客」靠它）
    return p


def _can_line(loc, node) -> str:
    """「现在能走到：…」那一行 —— 邻居名从 `maps` 现取（**唯一拼法**：`_here_lines` 与出镇那三条共用）。

    ★ 试玩问题 #9（本波）：出镇那三条在野外被拦下的那一刻，要把「这一带能走到哪儿」
      一并说清 —— 玩家才不至于以为是自己敲错了地方（原先只借铺子那一句，答不了那个问题）。
    """
    nb = [_name_of_node(loc, x) for x in _neighbors(loc, node)]
    return T("SYS_MOVE_CAN", list=" · ".join("『%s』" % x for x in nb))


def _entry_node(loc) -> str:
    """这张图**入口那一站** = `maps.<loc>.nodes` 的第一站（出镇那三条口令的落点 · 唯一口径）。

    ★ 试玩问题 #10（本波）：`往西` 原先在代码里写死落在西带**最后一站**（旧渡口），
      而往北 / 往东都落第一站 ⇒ 一进西带就跳过《浅滩》《石滩渡口》两站，
      而且进门第一屏讲的是浅滩、脚下却是旧渡口（画面与落点打架）。
      落点一律从 `maps` 现取：图上第一站就是那条带的入口，三层图（`topology: chain`）一个口径。
    """
    nodes = (_map_of(loc) or {}).get("nodes") or []
    return str((nodes[0] or {}).get("id") or "") if nodes else ""


def _here_lines(p) -> list:
    """★ K60：目标 == 脚下这一站 —— 说「到了」，别假装又走了一趟（B3-10 立的 · B3-11 收全）。

    四条出口（北口 / 往东 / 往西 / 进镇）原先**无条件**先往 `prev` 压一条「当前这一站」：
    站在骨田再敲一次「北口」会 ① 再演一遍出门那一屏 ② 历史里多一条自己（下一次
    『返回』就成了原地打转） ③ 「去过几回」虚增一趟（称号「骨田的常客」靠它）。
    判据：probe_copy ⑫（真跑四条 × 站在目的地上敲）。
    """
    loc, node = p.get("loc"), p.get("node")
    out = [T("SYS_MOVE_HERE", name=_name_of_node(loc, node))]
    if _neighbors(loc, node):
        out.append(_can_line(loc, node))
    return out


def name_with_title(p) -> str:
    """★ B3-2：名字后面跟称号（一个称号都没有就是名字本身）。

    显示位置照口径 §一：称号跟着名字走，**只显示最近拿到的那个**（21 §一「同上（替换）」）。
    """
    nm = p.get("name") or T("SYS_NAME_UNKNOWN")
    n = TT.newest(p)
    return T("SYS_TITLE_BY_NAME", who=nm, name=n[1]) if n else nm


def title_lines(p, player=None, env=None) -> list:
    """扫一遍称号：这次新挂上的那几个 → 要说的行（★ 有新称号才落档）。

    触发点与彩蛋同一批（口径 §一 的显示规则 + 21 §一 的拿法）：观察 · 触摸 · 地图 · 搭话。
    """
    new = TT.scan(p, CAL.state())
    if not new:
        return []
    if player is not None:
        player.update(p)
    _bad = _save(env)
    if _bad:
        return [T("SYS_SAVE_FAIL", why=_bad)]     # ★ 本函数交 list（不是 yield）· 成功话术一并作废
    return [T("SYS_TITLE_FOUND", name=TT.name_of(t)) for t in new]


def egg_lines(p, player=None, env=None) -> list:
    """扫一遍彩蛋：这次够格连起来的那几条 → 要说的行（★ 有新发现才落档）。

    触发点（口径 §一）：观察 · 触摸 · 地图 · 搭话 —— 都在各自实现体的末尾调一次。
    """
    new = EG.scan(p, CAL.state())
    if not new:
        return []
    if player is not None:
        player.update(p)
    _bad = _save(env)
    if _bad:
        return [T("SYS_SAVE_FAIL", why=_bad)]     # ★ 同上：本函数交 list（不是 yield）
    out = []
    for eid in new:
        out.append(T("SYS_EGG_FOUND", title=EG.title_of(eid)))
        out.append(T("SYS_EGG_LINE", line=EG.line_of(eid)))
    return out


# ══════════════════════════════════════════════════════════════
# 一、移动与世界
# ══════════════════════════════════════════════════════════════
async def look(env, sink, uid, player):
    p = _p(player)
    # ★ copy-p5（B 档 ① · 开场白）：**新玩家第一屏**先给一屏世界观框架 ——
    #   口径 `content/onboard.py::is_new`（建号还没走完那一档），只给一次性的「第一次」。
    #   ★ 位置在种族菜单**之前**：新玩家第一眼不是六行族表，是「你到了个什么地方」。
    if OB.is_new(p):
        yield T("SYS_ONBOARD_OPEN")
        yield "━" * 12
    # ★ P-10：还没定族 —— 第一眼不是风景，是「你是谁」（建号是玩的第一步）
    if not p.get("race"):
        for line in OB.step_head_lines(p):   # ★ copy-p5：标题块加在那一步**第一行之前**
            yield line
        for line in race_menu():
            yield line
        return
    if TT.newest(p):                            # ★ B3-2：称号跟着名字走（一个都没拿到就不多这一行）
        yield name_with_title(p)
    loc, node = p["loc"], p["node"]
    m = _map_of(loc) or {}
    # ★ 本波：这一站的人一个都不在 ⇒ 走「人不在那一版」场景（画面与名册不许打架 —— P1 BUG-5）。
    #   判据在 `content/town.py::station_empty`（基位在这一站、此刻一个都没到场），
    #   与下面那行「人在」走的是**同一个** `_npcs_here`。
    from .town import station_empty                 # 本地 import：town 要 import 本模块，模块级会成环
    yield _scene_line(loc, node, m, empty=station_empty(loc, node, p),
                      variant=scene_variant_of(p))   # ★ g4-⑤：满血那一站走变体那一段
    yield "━" * 12
    nb = [_name_of_node(loc, x) for x in _neighbors(loc, node)]
    yield T("SYS_LOOK_WAY", list=" · ".join("『%s』" % x for x in nb)) if nb else T("SYS_LOOK_DEAD_END")
    # ★ fix5-nav（P2 体验）：塔门口那一站多一句「门就在跟前 —— 敲『进塔』推门进去。」
    #   （门在哪一格从 `maps.old_watchtower.entrance` 现读 —— 见 `door_hint_lines`；
    #    本地 import：`cmds_tower` 要 import 本模块，模块级 import 会成环。）
    from .cmds_tower import door_hint_lines
    for _door in door_hint_lines(p):
        yield _door
    # ★ P-31：列 poi 走唯一一口（`_pois_here` 现看门槛）—— 门槛判得出不成立的这一刻不算在场，
    #   但**不静默**：逐条点名说清差什么；判不了的（如「退潮」）照旧在场 + 点名。
    poi_here = _pois_here(loc, node, p)
    seen_poi = poi_names_seen(poi_here)
    if seen_poi:
        yield T("SYS_LOOK_SEES", list=" · ".join("『%s』%s" % (v.get("name"), v.get("icon", "")) for v in seen_poi))
    for _gate in poi_gate_lines(poi_here):
        yield _gate
    npc_here = [v for _k, v in _npcs_here(loc, node, p=p)]
    if npc_here:
        yield T("SYS_LOOK_WHO", list=" · ".join("『%s』%s" % (v.get("name"), v.get("icon", "")) for v in npc_here))
    else:
        # ★ g4-⑨（31_NPC作息 §四）：这一站一个人都没有、可**基位**上本来有人 ⇒
        #   不再一片空白，逐位说清「这个点他不在 + 他什么时候在」（与空版场景同一判据）。
        for _gone in npc_gone_lines(loc, node, p):
            yield _gone
    for line in event_lines(p, loc, node):      # ★ B3-5：这一站聚人那一下（集日）
        yield line
    # ★ B3-24：这一格今天的精英 —— 观察**提前看到**（09_ §二「玩家在「观察」时能提前看到」）。
    #   与「攻击」的遭遇读**同一个口**（同一 uid / 图 / 节点 / 游戏日 ⇒ 同一种子）⇒ 这行是真预告；
    #   文案逐字走 texts 槽位（`COMBAT_ELITE_SPAWN`），本文件不写一个字。
    _el = AFFIX.elite_of(_data("monsters"), loc, node, uid,
                         CAL.state().get("game_day"), int(p.get("level", 1) or 1))
    if _el:
        # ★ 本波：这一栏原先**裸着**（「看得见」「人在」都有表头，只有它没有）——
        #   现在先出一行表头（`SYS_LOOK_FOE`），怪那一行照旧走 `COMBAT_ELITE_SPAWN`。
        yield T("SYS_LOOK_FOE")
        yield AFFIX.elite_line(str((_data("monsters")[_el[0]] or {}).get("name", _el[0])), _el[1])
    # ★ fxa（P2 试玩 #2）：**副本房间里也把「遇敌」写在屏幕上** —— 塔内不刷精英（见
    #   `rules/elite.json` 的 `eligible_node_roles`），上面那一支在塔里一格都不出，玩家按
    #   『下一层』那句去「打它」却看不见目标。这一栏与『攻击』**同一次抽**（名字从
    #   `cmds_battle.foe_here` 来）⇒ 看见的就是会开打的那只。本地 import：`cmds_tower`
    #   要 import 本模块（模块级 import 会成环）。
    #   ★ fxexp（本波）：这一栏原先**只有塔内**有名字行 —— 野外 / 镇上那一档的槽位
    #     `SYS_LOOK_FOE_ROW` 一个读端都没有（死槽位）。现在两档都走这一口（`elite_row`
    #     = 上面那一支已经说过精英 ⇒ 不再重复一行）。
    from .cmds_tower import foe_lines_here
    for _foe in foe_lines_here(p, uid, elite_row=bool(_el)):
        yield _foe
    yield T("SYS_LOOK_HINT")
    for line in egg_lines(p, player, env):      # ★ B3-1：看四周那一下可能把两件事连起来
        yield line
    for line in title_lines(p, player, env):    # ★ B3-2：看四周那一下也可能把名字挂上来
        yield line


async def map_view(env, sink, uid, player):
    p = _p(player)
    loc, node = p["loc"], p["node"]
    m = _map_of(loc) or {}
    nodes = m.get("nodes") or []
    yield T("SYS_MAP_HEAD", name=m.get("name", loc),
            kind=T("SYS_MAP_KIND_TOWN") if m.get("topology") == "star" else T("SYS_MAP_KIND_WILD"))
    for n in nodes:
        mark = "▸" if n.get("id") == node else " "
        yield "%s %s%s" % (mark, n.get("name"), T("SYS_MAP_HERE") if mark == "▸" else "")
    for line in egg_lines(p, player, env):      # ★ B3-1：走到底再看地图
        yield line
    for line in title_lines(p, player, env):    # ★ B3-2：走了那么多趟，名字该挂上来了
        yield line
    # ★ fix-l（试玩 ranger b56/b57：野外敲『地图』只列本图三站，回镇得自己想出「进镇」，
    #   而『往南』这类方向词根本不被接住）：**野外**那一屏补一行尾注点明回镇的口。
    #   只认拓扑（`star` = 镇上 ⇒ 不印：镇里回镇那句话已由进镇那一屏的尾注说了）；
    #   真源 `04_指令总表 §一` 那张表里 `进镇` 的守卫本来就是「在北口或野外」。
    if str(m.get("topology") or "") != "star":
        yield T("SYS_MAP_BACK_TOWN")


async def listen(env, sink, uid, player):
    """★ fix3-④：听这一站 —— **先本节点、再本图、最后才通用句**。

    原先只按 `p["loc"]`（图）取 `WORLD_LISHEN_<图>`，而 texts 域里一张图都没有这一族
    ⇒ 玩家在镇上 11 个站点听到的是同一句 `SYS_LISTEN_DEFAULT`（玩家报告 P1 体验-3：与
    同站『观察』写的东西对不上）。现在口径与 `scene.resolve` 一致：节点级 → 地图级 → 默认；
    句子都在 texts 域，本文件一个字不写（呈现口只传槽位）。
    """
    p = _p(player)
    for key in ("WORLD_LISHEN_%s" % str(p["node"]).upper(),
                "WORLD_LISHEN_%s" % str(p["loc"]).upper()):
        if key in _texts():
            yield T(key)
            return
    yield T("SYS_LISTEN_DEFAULT")


async def explore(env, sink, uid, player):
    """★ fxexp：`探索`（别名 探 / 走一圈）—— 在**脚下这一站**转一圈：掷一次遇怪；没撞上 ⇒ 不空手。

    口径（设计案《fxexp · 「探索遇怪」字段级设计案 §2》· 真源 `00_总纲/03_主要玩法`
    「路上：**遇怪**、看见能捡的东西…」）：

      · **持态**：手上还有一场没打完 ⇒ **拦下**（与移动族**同一道闸** `_in_fight`、
        同一句 fail-closed —— 位置与历史一个字不动）；
      · **概率**走 `content/explore.py`（表 = `content/rules/explore_encounter.json`；
        base[档] × 等级差 × 时辰 × 天气 × 世界事件，上限 0.9）—— 本文件**一个数都不写**。
        **表缺 / 这一站拿不到档 ⇒ 不掷**（与接线前逐字相同：不建场、不动档）；
      · **命中** ⇒ 走**同一条** `_open_and_hand` 骨架开一场（head 用槽位
        `COMBAT_EXPLORE_MET`，名字由骨架从**同一次抽**里现读）—— 抽怪仍走
        `_encounter` / `affix.elite_of`（**不另起一套**），所以「探索撞到的」与
        「『观察』印的那只 / 『攻击』开的那一场」是**同一个口**；
      · **掷空** ⇒ 有拾取点给拾取提示，没有就通用那句（`explore.miss_lines`）。
        ★ 掷空这一支**一个字都不写档**（设计案 §四验收 2「不建场、不动档」）。
    """
    _lock = _in_fight(env, uid)
    if _lock:
        yield _lock
        return
    p = _p(player)
    st = CAL.state()                              # 时辰 / 天气 / 游戏日（现算，不落档）
    _ratio = EX.ratio(_data("monsters"), p["loc"], p["node"], int(p.get("level", 1) or 1), st, p)
    if _ratio is None or EX.roll(uid, p) >= float(_ratio):
        # 不掷（表缺 / 档取不到）或掷空 —— 两支都**不建场、不动档**
        for line in EX.miss_lines(p, st):
            yield line
        return
    # ★ P-27 同一个口径：这一场要靠面板（档上还没有职业 ⇒ 不出假数、这一场不开）
    _mx, _line = hp_cap_or_line(p)
    if _line:
        yield _line
        return
    from .cmds_battle import _open_and_hand        # 本地 import：`cmds_battle` 要 import 本模块
    async for line in _open_and_hand(env, p, uid, player, "", head_slot="COMBAT_EXPLORE_MET"):
        yield line


async def time_now(env, sink, uid, player):
    """★ 时辰与天气的唯一呈现口（模板 SYS_WEATHER_CHANGE = 26 消息模板第 13 类）。

    ★ fix3-①②：天气风味行与时辰风味行**同屏**，两句各自只认自己那一轴 ⇒ 原先
      `昼 · 雨` 的正文里写「日头正」、`夜 · 晴` 的正文里写「太阳晒到石头上」（两个玩家
      独立撞上：P1 BUG + P4 BUG-2 / P2 BUG⑤）。现在两句都走 `CAL.desc_slot(条目, st)`：
      基础句已按对轴中立，另外**夜里还有一种自己的晴**（变体槽位 `WEATHER_SUNNY_DESC__HR_NIGHT`）。
    """
    p = _p(player)
    st = CAL.tick(p)                       # 钟源 = 宿主注入（facade.clock），本模块不自己取钟
    if player is not None:
        player.update(p)
    _bad = _save(env)
    if _bad:
        yield T("SYS_SAVE_FAIL", why=_bad)
        return
    yield T("SYS_WEATHER_CHANGE", place=_name_of_node(p["loc"], p["node"]),
            hour=st["hour_name"], weather=st["weather_name"],
            flavor=T(CAL.desc_slot(st["weather"], st)))
    yield T(CAL.desc_slot(st["hour"], st))


async def event_now(env, sink, uid, player):
    """★ B3-5：新指令「异动」（别名「今天」「动静」）—— 看今天世界怎么了。

    口径（29 §六「指令不变，内容长」）：
      · 三尺度（世界 / 限时 / 每日）**现算** —— 走 `CAL.events_now` 一个口，不存历史
      · 「今天新开的 / 收了」拿宿主维护门落的那一格比（`timed_events.snapshot`）：
        那一格 = 「上次刷新时开着哪些窗」。★ 只在那格**是今天刷的**时才标 —— 没刷新过就不瞎标。
    """
    p = _p(player)
    st = CAL.tick(p)                       # 与「时间」同一口径：把「今天」记到档上
    if player is not None:
        player.update(p)
    _bad = _save(env)
    if _bad:
        yield T("SYS_SAVE_FAIL", why=_bad)
        return
    yield T("SYS_EV_HEAD")
    on = CAL.events_now(st, p)
    if not on:
        yield T("SYS_EV_NONE")
        return
    seen = TE.snapshot(p)
    fresh = bool(seen) and int(seen.get("day") if seen.get("day") is not None else -1) \
        == int(st["game_day"])
    prev_on = [str(x) for x in (seen.get("prev_on") or [])] if fresh else []
    now_keys = {r["window"] for r in on}
    for rec in on:
        slot = "SYS_EV_ROW_NEW" if (fresh and rec["window"] not in prev_on) else "SYS_EV_ROW"
        yield T(slot, name=rec["name"], text=T(rec["text"]))
    for key in prev_on:                    # 上一格开着、这一格收了的（限时「关一段」那一面）
        if key in now_keys:
            continue
        rec = CAL.event(CAL.id_of_key(key))
        if rec:
            yield T("SYS_EV_GONE", name=rec["name"])


async def go_north(env, sink, uid, player):
    _lock = _in_fight(env, uid)
    if _lock:
        yield _lock
        return
    p = _p(player)
    dest = _entry_node("belt_north")
    if (p["loc"], p["node"]) == ("belt_north", dest):        # ★ B3-11：脚下这一站（K60）
        for line in _here_lines(p):
            yield line
        return
    # ★ P-52：出镇那一条的「在镇上」守卫 —— 唯一执行面 = `town.town_gate`（B4-12 收的口）。
    #   本地 import：`town` 要 import 本模块，模块级 import 会成环（与 `_p` 里 panel_build 同一手）。
    #   被拦 ⇒ 一句话、**位置与历史一个字不动**（不 `_save`）。
    #   ★ 试玩问题 #9（本波）：不在镇上时**不再借铺子那一句**（「这几处都在镇上」答不了
    #     「往北去哪儿了」）—— 方向各自一句 + 「现在能走到」从 `maps` 现算。
    from .town import town_gate
    _blocked = town_gate(p, notown="SYS_MOVE_NO_ROAD_NORTH")
    if _blocked:
        yield _blocked
        yield _can_line(p["loc"], p["node"])
        return
    p = _move(p, "belt_north", dest, sink)
    if player is not None:
        player.update(p)
    _bad = _save(env)
    if _bad:
        yield T("SYS_SAVE_FAIL", why=_bad)
        return
    yield T("SYS_MOVE_OUT_NORTH")
    yield _map_scene("belt_north")            # ★ B3-6a：地一屏从 texts 来（原先内联在代码里）
    for line in event_lines(p, "belt_north", dest, entered=True):    # ★ B3-5：一句进林描述
        yield line


async def go_east(env, sink, uid, player):
    _lock = _in_fight(env, uid)
    if _lock:
        yield _lock
        return
    p = _p(player)
    dest = _entry_node("belt_east")
    if (p["loc"], p["node"]) == ("belt_east", dest):        # ★ B3-11：脚下这一站（K60）
        for line in _here_lines(p):
            yield line
        return
    from .town import town_gate                                   # ★ P-52：同 `go_north`
    _blocked = town_gate(p, notown="SYS_MOVE_NO_ROAD_EAST")       # ★ #9：方向各自那一句
    if _blocked:
        yield _blocked
        yield _can_line(p["loc"], p["node"])
        return
    p = _move(p, "belt_east", dest, sink)
    if player is not None:
        player.update(p)
    _bad = _save(env)
    if _bad:
        yield T("SYS_SAVE_FAIL", why=_bad)
        return
    yield T("SYS_MOVE_OUT_EAST")
    yield _map_scene("belt_east")             # ★ B3-6a：同上
    for line in event_lines(p, "belt_east", dest, entered=True):    # ★ B3-5：同上
        yield line


async def go_west(env, sink, uid, player):
    _lock = _in_fight(env, uid)
    if _lock:
        yield _lock
        return
    p = _p(player)
    dest = _entry_node("belt_west")           # ★ #10：落点 = 西带第一站（浅滩），从 maps 现取
    if (p["loc"], p["node"]) == ("belt_west", dest):        # ★ B3-11：脚下这一站（K60）
        for line in _here_lines(p):
            yield line
        return
    from .town import town_gate                                   # ★ P-52：同 `go_north`
    _blocked = town_gate(p, notown="SYS_MOVE_NO_ROAD_WEST")       # ★ #9：方向各自那一句
    if _blocked:
        yield _blocked
        yield _can_line(p["loc"], p["node"])
        return
    p = _move(p, "belt_west", dest, sink)
    if player is not None:
        player.update(p)
    _bad = _save(env)
    if _bad:
        yield T("SYS_SAVE_FAIL", why=_bad)
        return
    yield T("SYS_MOVE_OUT_WEST")
    yield _map_scene("belt_west")             # ★ B3-6a：同上
    for line in event_lines(p, "belt_west", dest, entered=True):    # ★ B3-5：同上
        yield line


def _in_fight(env, uid) -> str:
    """手上还留着一场没打完吗 —— 有就返回拦下那句话（没有 ⇒ 空串）。

    ★ 试玩复测 #1（2026-09-26）：一场没结就走不了（出镇 / 带间 / 返回 / 去 / 进镇）。
      要走先『逃跑』/『后撤』脱身，或者把它打完。拦下时**位置与历史一个字不动**。
    """
    from . import instance as INST
    if not INST.fighting(env, uid):
        return ""
    return T("SYS_MOVE_IN_FIGHT")


async def enter_town(env, sink, uid, player):
    _lock = _in_fight(env, uid)
    if _lock:
        yield _lock
        return
    p = _p(player)
    if (p["loc"], p["node"]) == (TOWN, "wt_gate_n"):             # ★ B3-11：脚下这一站（K60）
        for line in _here_lines(p):
            yield line
        return
    p["prev"] = (p.get("prev") or [])[-8:] + [(p.get("loc"), p.get("node"))]
    p["loc"] = TOWN
    p["node"] = "wt_gate_n"
    CX.note_visit(p, TOWN, "wt_gate_n")
    CX.note_step(p, TOWN, "wt_gate_n")
    if player is not None:
        player.update(p)
    _bad = _save(env)
    if _bad:
        yield T("SYS_SAVE_FAIL", why=_bad)
        return
    yield _map_scene(TOWN)                                      # ★ B3-6a：进镇那一屏从 texts 来（原内联）
    yield T("SYS_TOWN_ENTER_HINT")
    # ★ fix5-nav（P1 BUG-11 / P3 体验）：`北口` 归站点（站名那一族）之后，「出镇走哪个词」要当面说清 ——
    #   上面那一句 `SYS_TOWN_ENTER_HINT`（真源 `17_文案收口口径_v1.md` 锁着、一字不动）
    #   把『北口』列在「出门」里；这一句把口径补齐：北口 是镇口那一站，出镇是 往北 / 往东 / 往西。
    #   （真源那一行该改成「『往北』出门」—— 两处一起改的那笔账写在 `_notes.md`。）
    yield T("SYS_TOWN_ENTER_GATE")
    for line in event_lines(p, TOWN, "wt_gate_n", entered=True):  # ★ B3-5：进镇那一下
        yield line


async def go_back(env, sink, uid, player):
    _lock = _in_fight(env, uid)
    if _lock:
        yield _lock
        return
    p = _p(player)
    prev = p.get("prev") or []
    if not prev:
        yield T("SYS_MOVE_BACK_NONE")
        return
    loc, node = prev[-1]
    p["prev"] = prev[:-1]
    p["loc"], p["node"] = loc, node
    CX.note_step(p, loc, node)                # ★ B3-2：退回也是走到了一趟
    if player is not None:
        player.update(p)
    _bad = _save(env)
    if _bad:
        yield T("SYS_SAVE_FAIL", why=_bad)
        return
    yield T("SYS_MOVE_BACK", name=_name_of_node(loc, node))


async def go_to(env, sink, uid, player):
    """`去 <地方>` —— 在同一张图里走到另一个节点。

    ★ 为什么需要它：玩家到了镇上（风车镇是 star 拓扑 11 个节点），若只能在
      「北口 / 东口 / 西口」之间跳，北墙根（哈根）、白烛堂（艾德/莉安）这些地方
      **永远走不到** —— 而 NPC 在那儿。
    规则：目标必须是**当前节点的邻居**（不是任意节点）—— 跨图要先出门。
    """
    # ★ fxa（P2 试玩 #2/#3）：这一条原先**漏在外面** —— 上一波补的那三行闸被写进了
    #   docstring 里（成了死字），于是「场在跑」的时候 `去 <房间>` 照旧走得动：野外那一场
    #   会跟着玩家跨图跨层（P2 原文：拾荒营地打「拾荒人」→ 进塔 → 去 楼梯前 → `攻击`
    #   ⇒「第 3 手 …… 拾荒人 229/244」），副本里也成了「说的那只 ≠ 打的那只」的来源。
    _lock = _in_fight(env, uid)
    if _lock:
        yield _lock
        return
    p = _p(player)
    want = AV.arg_of(env)        # ★ B4-11：跟着自己的声明剥参（连写也算）
    raw = (getattr(env, "text", "") or "").strip()
    # ★ fix5-nav：**屏幕上的站名能直接敲** —— 整句就是一个地点名时，当它等于「去 <名>」。
    #   别名 pattern（`^老风车$` 那一族）由 `scripts/rebuild_place_alias.py` 从 `maps` 现读补上；
    #   这里**只认「整句真是一个地点名」**（本包五张图的节点名 / id）⇒ 裸指令名
    #   （`去` / `走到` / `前往`）照旧走「去哪儿？」那一支（判据 probe_nav ③）。
    if not want and raw and _place_at(raw)[0]:
        want = raw
    loc, node = p["loc"], p["node"]
    nb = _neighbors(loc, node)
    if not want:
        yield T("SYS_MOVE_ASK", list=" · ".join("『%s』" % _name_of_node(loc, x) for x in nb))
        return
    hit = None
    for x in nb:
        if want == x or want == _name_of_node(loc, x):
            hit = x
            break
    if hit is None:
        for n in (_map_of(loc) or {}).get("nodes") or []:
            if want in (n.get("id"), n.get("name")):
                # ★ B3-10：目标就是脚下这一站 —— 别说「过不去」（玩家会以为路被堵了）
                if n.get("id") == node:
                    for line in _here_lines(p):      # ★ B3-11：与四条出口共用同一支
                        yield line
                    return
                yield T("SYS_MOVE_FAR", name=n.get("name"))
                yield T("SYS_MOVE_CAN", list=" · ".join("『%s』" % _name_of_node(loc, x) for x in nb))
                return
        # ★ fix5-nav：名字真存在、只是**不在这张图上** —— 说「从这儿过不去」（别印 id、
        #   也别谎称「没这个地方」）。判据 probe_nav ④。
        _there, _disp = _place_at(want)
        if _there:
            yield T("SYS_MOVE_FAR", name=_disp)
            yield T("SYS_MOVE_CAN", list=" · ".join("『%s』" % _name_of_node(loc, x) for x in nb))
            return
        yield T("SYS_MOVE_NOSUCH", name=want)
        yield T("SYS_MOVE_CAN", list=" · ".join("『%s』" % _name_of_node(loc, x) for x in nb))
        return
    # ★ fxa（P2 试玩 #3）：副本里**本层尽头那一间往外走**走的是同一道守卫闸（『下一层』
    #   那一句的同一个门）—— 原先只有楼梯那一句拦，`去 <上一层第一间>` 照通（那一步就是
    #   上楼，等于把整层守卫绕过去）。拦下时位置与历史一个字不动。别的图这一步恒为空串。
    from .cmds_tower import step_guard_line
    _step = step_guard_line(p, uid, hit)
    if _step:
        yield _step
        return
    p["prev"] = (p.get("prev") or [])[-8:] + [(loc, node)]
    p["node"] = hit
    CX.note_visit(p, loc, hit)
    CX.note_step(p, loc, hit)                 # ★ B3-2：走到的那一趟
    if player is not None:
        player.update(p)
    _bad = _save(env)
    if _bad:
        yield T("SYS_SAVE_FAIL", why=_bad)
        return
    yield T("SYS_MOVE_TO", name=_name_of_node(loc, hit))
    # ★ fix5-nav：走到塔门口那一格 —— 顺口说一句门能进（与 `观察` 同一支 · `door_hint_lines`）
    from .cmds_tower import door_hint_lines
    for _door in door_hint_lines(p):
        yield _door
    # ★ P-31：与「观察」同一个口（`_pois_here` 现看门槛）—— 原先这一条自己扫域、不判条件
    poi_here = _pois_here(loc, hit, p)
    seen_poi = poi_names_seen(poi_here)
    # ★ B3-15：走唯一一口 —— 出场条件（时辰 / 天气）现看。改前这一条自己扫域、不判条件，
    #   白天的「去 北墙根」照样把只在该在昏/夜的哈根列出来（与「观察」「问路」两处口径不一致）。
    npc_here = [v for _k, v in _npcs_here(loc, hit, p=p)]
    if seen_poi:
        yield T("SYS_LOOK_SEES", list=" · ".join("『%s』%s" % (v.get("name"), v.get("icon", "")) for v in seen_poi))
    for _gate in poi_gate_lines(poi_here):
        yield _gate
    if npc_here:
        yield T("SYS_LOOK_WHO", list=" · ".join("『%s』%s" % (v.get("name"), v.get("icon", "")) for v in npc_here))
    # ★ B3-5：镇内/带内走一步只出「这一站」那一条（聚人）；跨图那一下（进镇 / 往东 / 往西 / 北口）
    #   才出事件的表征句 —— 不然在镇上走两步就把「商队到了」念两遍（一句话的时机要克制）
    for line in event_lines(p, loc, hit):
        yield line


# ══════════════════════════════════════════════════════════════
# 二、角色
# ══════════════════════════════════════════════════════════════
def live_mp(env, uid, p):
    """打斗中途「我这一手」的现蓝 —— **唯一口**：有「场」就按场里那一格 actor 现读。

    ★ 本批（试玩 A2）：扣蓝的落账落在**这一场收尾那一刻**（`cmds_battle._settle`），
      所以在打的这一场里档上那一格还是开场时的数 —— 中途敲『状态』该报的是**眼下这一场**
      的余蓝，不是开打前那个（改前实测：放完两招敲 `状态`，报的还是 `85/85`）。
      拿不到（没在打 / 场里没这一格）⇒ 照**档上那一格**（= 与接线前逐字相同，不编数）。

    ★ 血也在这儿读（`live_hp`）—— 原先这句写的是「血在每一手都落回档，档上那一格本来就是
      活的」：**只对出手的那一位成立**。`instance._write_back` 只把**轮到我那一手**的血落回档，
      而「别人出手那一手我挨的打」不在档上（实测 2 人同场：乙出手那一手甲挨 27，档上仍是 284）
      ⇒ 甲敲『状态』报的是旧数。见 `live_hp`。
    """
    from . import instance as INST                 # 本地 import：与 `live_foe` 那一族同款
    st = INST.live(env, uid)
    if st is None:
        return p.get("mo")
    a = INST.actor_of(st, uid)
    if not isinstance(a, dict) or a.get("mp") is None:
        return p.get("mo")
    return a.get("mp")


def live_hp(env, uid, p):
    """打斗中途「我」的现血 —— **唯一口**：有「场」就按场里那一格 actor 现读。

    ★ fix-q（试玩 · 与 `歇脚` 那条同源）：`instance._write_back` 的抬头明写「『不动档』那条
      只对**没轮到我的那两敲**成立」—— 也就是说，**别人出手那一手我挨的打根本不在档上**。
      实测（2 人同场 · 真宿主）：乙（后手）出手那一手甲挨了 27 点，甲档上仍是 `284` ⇒
      甲敲『状态』报 `生命 284/284`，而场上它 `257/284`（下一手头行才见真数）——
      「一人两套血」的读数那一面，与 `live_mp` 同一个理由。
      拿不到（没在打 / 场里没这一格）⇒ 照**档上那一格**（= 与接线前逐字相同，不编数）。
    ★ 倒地的这一档同样照档：0 不是「档上的血」，是这一场的处置（回白烛堂 / 回满）——
      与 `_write_back` 不写 0 同口径，不许拿 0 顶替（否则面板上出现「生命 0/248」的活人）。
    """
    from . import instance as INST                 # 本地 import：与 `live_mp` 同款
    st = INST.live(env, uid)
    if st is None:
        return p.get("hp")
    a = INST.actor_of(st, uid)
    if not isinstance(a, dict) or a.get("hp") is None:
        return p.get("hp")
    hp = int(a.get("hp") or 0)
    return hp if hp > 0 else p.get("hp")


async def status(env, sink, uid, player):
    p = _p(player)
    # ★ copy-p5（B 档 ② · 面板顶栏「当前该做：⋯」）：**第一行** —— 玩家打开面板第一眼看到
    #   「现在该干什么」，而不是一串数字。四档正文现算（`onboard.goal_line` 一个口）。
    #   ★ 读档这一刻先校正一次（`refresh_goal`）：那一格是派生态，换进程回来时按旧值印会过期。
    _goal = OB.goal_line(p)
    if _goal:
        yield _goal
    nm = name_with_title(p)                     # ★ B3-2：称号跟着名字走进面板
    yield T("SYS_STATUS_HEAD", who=nm, race=_race_label(p.get("race")),
            cls=_cls_label(p.get("cls")), level=p.get("level"))
    # ★ P-27：上限只有一个来源（职业面板）。档上没有职业 ⇒ 上限**未定** —— 照实说，
    #   不拿 100 垫（原先写死 100 ⇒ 面板 116 的骑士 `状态` 显示 100/100）。
    from . import panel_build as _PB                       # 本地 import：避免包装载期成环
    cap = _PB.hp_cap(p, strict=False)
    mcap = _PB.mp_cap(p, strict=False)                     # ★ B4-8：与生命同一把尺（面板）
    if cap is None:
        # 还没择业 ⇒ 两格的**上限**都是未定（法力上限同样由职业决定：骑士 50 / 狂战士 0）
        yield T("SYS_STATUS_VITALS", hp=T("SYS_UNSET"), hp_max=T("SYS_UNSET"),
                mo=T("SYS_UNSET"), mo_max=T("SYS_UNSET"), gold=p.get("gold"))
    else:
        # ★ fix-q：血与蓝都按**这一场那一格**现读（`live_hp` / `live_mp` 同一个口）——
        #   档上那一格只对「刚出手的那一位」是活的，别人出手时我挨的打不在档上。
        yield T("SYS_STATUS_VITALS", hp=live_hp(env, uid, p), hp_max=cap,
                mo=live_mp(env, uid, p), mo_max=mcap, gold=p.get("gold"))
    yield T("SYS_STATUS_EXP", exp=p.get("exp"),
            place=_map_of(p["loc"]).get("name", p["loc"]) if _map_of(p["loc"]) else p["loc"])
    # ★ fix-l（试玩 ranger b38~b40：跨进程回来先敲『状态』一个字都不提，直到敲『去 X』
    #   才被 `SYS_MOVE_IN_FIGHT` 拦下 ⇒ 玩家读不懂为什么走不动）：**手上还留着一场**时
    #   面板上就把它说出来。只读 `instance` 那两个现成口（`live` / `fighting`），
    #   不动状态、不重开那一场；面板其余各行一个字不动（`SYS_MOVE_IN_FIGHT` 那道闸也照旧）。
    from . import instance as _INST                       # 本地 import：避免包装载期成环
    if _INST.fighting(env, uid):
        yield T("SYS_STATUS_IN_FIGHT")


async def origin(env, sink, uid, player):
    """`出身` —— 你从哪儿来的（`04_指令总表 §三` · 守卫「随时」）。

    ★ P-69：「出身」是**回看口**（建号那一步并进第 1 步了，见 `BUILD_STEPS`）。
    ★ P-68（2026-09-26 · 本波 w-h-ux 裁）：**家乡与寿数放进这一屏，一行**（第三行）——
      真源 `04 §三` 那一行本波裁成「族 · 那句「为什么来」· **家乡与寿数**」，`races.home` /
      `races.lifespan` 两格（六族都有）就从这儿见光。位置就这一处：别处不再放第二遍
      （`观察` 是「眼下这一站」、`状态` 是「这一会话的数字」，两处都不带族谱那一层）。
      槽位 `SYS_ORIGIN_HOME` 的真源行还没落 ⇒ **今天不印这一行**（`_origin_home_line` 回 None）。
    """
    p = _p(player)
    if not p.get("race"):
        yield T("SYS_ORIGIN_NONE")
        return
    rs = _race_rec(p.get("race"))
    yield T("SYS_ORIGIN_WHO", name=rs.get("name") or _race_label(p.get("race")))
    yield T("SYS_ORIGIN_WHY",
            why=rs.get("line") or rs.get("why") or T("SYS_ORIGIN_WHY_TODO"))  # ★ P-10：域里的字段叫 line（原来读 why，永远给「还没写」）
    home = _origin_home_line(rs)          # ★ P-68：家乡 · 寿数（待槽位 ⇒ 今天不印）
    if home:
        yield home


def _bag_rows(p) -> list:
    """背包里每一行（★ 顺序 = 档上的插入序）—— 分页只负责切，行怎么拼只在这一处。"""
    from . import loot as LT                      # local import：免得包装载期成环
    from . import gear as GB                      # ★ #13：`+N` 那截后缀走它唯一那一口
    rows = []
    for k, v in (p.get("bag") or {}).items():
        rec = LT.rec_of(k)                        # ★ 未鉴定的 marker：名字与图标写在池上
        # ★ B4-20：名字走 `LT.label_of` —— 「域里重名的那些」缀品阶（同名四档装备原先两行一模一样）
        # ★ 试玩问题 #13：强化过的缀上 `+N`（没强化过 ⇒ 与从前逐字相同）
        rows.append("· %s %s%s ×%s" % (rec.get("icon", ""), LT.label_of(k), GB.shown_badge(p, k), v))
    return rows


async def bag_page(env, sink, uid, player, page=None):
    """`背包` 的第 `page` 页（★ B4-17：长列表分页 · 切页走 `content/pager.py` 那一口）。"""
    p = _p(player)
    items = p.get("bag") or {}
    if not items:
        yield T("SYS_BAG_EMPTY")
        return
    from . import pager as PG
    head = [T("SYS_BAG_HEAD", n=len(items))]
    for line in PG.render(env, "bag", head, _bag_rows(p), page=page):
        yield line


async def bag(env, sink, uid, player):
    """`背包` —— 页码从本条消息里取（`背包 2`），不写就是第一页。"""
    async for line in bag_page(env, sink, uid, player):
        yield line


async def money(env, sink, uid, player):
    p = _p(player)
    yield T("SYS_MONEY_POUCH", gold=p.get("gold"))


# ══════════════════════════════════════════════════════════════
# ★ P-34：加点（`加点 <属性> [次数]`）—— 建号 8 点 + 每级 3 点，玩家自己分
# ══════════════════════════════════════════════════════════════
#: 真源 `06_第一阶段垂直切片/04_指令总表.md`：`加点 <属性> [次数]` ｜ 条件「有属性点」｜ 分配
#: ★ 为什么原先「加不了点」：这条声明一直在（`content/data/commands.json`），但**没有实现体**
#:   —— 引擎走「该声明未提供处理器」那一支。而配平（怪面板 = 按建议权重**铺满**反推）与
#:   六职业详案（「1 级行 = 职业基础值（**建号 8 点未投**）」）都假定这些点是真的会被投出去的。
#:   裁决（2026-09-25 鱼鱼拍板 · 甲案）：**玩家自己加点**，不做「新档自动平铺」——
#:   依据 `06_第一阶段垂直切片/18_建号与新手引导_v1.md` §四 第一小时目标清单
#:   「升到 2 级并加点（`加点 STR 3`）」与 `16_玩家体验走查_v1.md`「他能做什么 …加点…」。
#:   ⇒ 铺满 = **参照上界**（配平基准）· 零加点 = **下界**，两头都用数字钉住（probe_panel ⑦）。
def _alloc_verb() -> str:
    """这条指令的**触发词**（取声明自己的 `usage` 第一个词 —— 代码里一个中文都不写）。"""
    u = str((_data("commands").get("alloc") or {}).get("usage") or "").split(" ")
    return (u[0].strip() if u else "")


def _stat_slot(stat) -> str:
    """五维 → 中文名槽位（`SYS_STAT_STR` = 力量）—— 维名的中文只有 texts 那一处。"""
    return T("SYS_STAT_%s" % str(stat or "").upper())


def _stat_of(want) -> str:
    """玩家写的那个词 → 五维之一（ASCII `str` / 中文名 `力量` 都认）；认不出回空串。"""
    w = str(want or "").strip()
    if not w:
        return ""
    up = w.upper()
    for s in AL.STATS:
        if up == s:
            return s
    for s in AL.STATS:
        if w == _stat_slot(s):
            return s
    return ""


def _stat_list() -> str:
    """五个维名的**呈现面**（加点提示与认不出维名那一行共用 —— 只一处拼）。"""
    return " · ".join(_stat_slot(s) for s in AL.STATS)


def _alloc_arg(env) -> str:
    """`加点 力量 3` → `力量 3` —— 走**取参那个口**（★ B4-11：原先只认主词
    `加点`，别名 / 连写都会被剔成空串；现在跟自己的声明走）。
    """
    return AV.arg_of(env)


async def alloc_points(env, sink, uid, player):
    """`加点 <属性> [次数]` —— 把等级给的点真投到五维上（★ P-34）。

    点数只有一个来源（`content/alloc.py`）：**总点数 = 8 + 3×(级−1)**（真源
    `00_总纲/05_系统总表与阶段开放_v1.md`「五维加点（建号 8 + 每级 3）」）——
    **不落档、不另发**（等级改了它自动跟着变；写了新容器就是两个源）。余额 = 总点数 − 已花。

    fail-closed（`fail-closed-boundaries` §1）—— 三种"加不了"分开说，**都不动档**：
      · 档上还没有职业 ⇒ 属性跟着职业走（`SYS_ATTR_NOCLS`，与「属性」页同一个口）
      · 认不出的维 / 次数不是 1 以上的整数 ⇒ 点名回一行
      · 想加的点数超了余额 ⇒ 只说不够（**余额就是硬上限**：总点数没有别的门）
      · 档上那一格 `alloc` 本身是坏的（认不出的维 / 小数 / 超投）⇒ 点名（`SYS_ALLOC_BAD_SAVE`），
        不"当作没投过"接着加
    """
    # ★ 台账 L2154-2：原先 `p = _p(player)` 是**裸的一行**，而 `_p` 自己的面板那一口
    #   （`hp_cap` → `build_actor` → `ALLOC.of_record`）也走同一把尺 ⇒ 坏档在**这一行**
    #   就抛 AllocError，**先于**下面那个 catch ⇒ 四种坏档（坏维 / 非数字 / 负数 / 坏等级）
    #   实测整个异常**裸逃出指令**（那处 `T(SYS_ALLOC_BAD_SAVE, why=…)` 对它们是死支）。
    #   修法 = 把这一行也纳入同一个 catch（不新造处理路径，同一句玩家文案、同一条日志）。
    # ★ 台账 L2154-3：等级那一格**先**过本包已有的 fail-closed 口。
    #   为什么不放在后面：`_p()` 自己就调 `panel_build.actor_of_record`（`:376` 裸
    #   `max(1, int(rec.get("level") or 1))`），坏等级在**这一行**就 ValueError 裸逃出
    #   指令 —— 而 `panel_build.py` **不在批次 1 的文件面**（别车道/公共面，撞不得）。
    #   ⇒ 在进 `_p()` 之前先自己把这一格验掉：不改别处、也不靠一个宽 `except` 兜。
    #   `_p` 之后那处 `AL.level_of` 保留（归一化后的档再取一次，同一把尺）。
    try:
        lv = max(1, AL.level_of(player.get("level") if isinstance(player, dict) else None))
    except AL.AllocError as e:
        _LOG.warning("[aep.alloc] 读档时等级那格坏了：%s", e, exc_info=True)
        yield T("SYS_ALLOC_BAD_SAVE", why=T(e.player_reason))
        return
    try:
        p = _p(player)
    except AL.AllocError as e:
        _LOG.warning("[aep.alloc] 读档时加点格坏了（面板那一口先抛）：%s", e, exc_info=True)
        yield T("SYS_ALLOC_BAD_SAVE", why=T(e.player_reason))
        return
    cls = str(p.get("cls") or "").strip()
    if not cls:
        yield T("SYS_ATTR_NOCLS")
        return
    # 等级那一格已在进 `_p()` 之前验过（上面）；归一化后的档**再取一次**走同一把尺
    # —— 防止 `_fresh` 填了默认值后口径漂移。
    try:
        lv = max(1, AL.level_of(p.get("level")))
    except AL.AllocError as e:
        _LOG.warning("[aep.alloc] 归一化后等级那格坏了：%s", e, exc_info=True)
        yield T("SYS_ALLOC_BAD_SAVE", why=T(e.player_reason))
        return
    try:
        al = AL.of_record(p)                     # 这档实际分了多少（唯一口；坏档 ⇒ 抛）
        left = AL.balance(lv, al)
    except AL.AllocError as e:
        # ★ 台账 L2154：原填 `why=e`（整个 str）⇒ 档里的坏键 `'ZZZ'` 原样上屏。
        #   玩家那一行只拿 `player_reason`（分类句）；机器侧原话 + 栈进日志，不丢诊断。
        _LOG.warning("[aep.addoc] 读档时加点格坏了：%s", e, exc_info=True)
        yield T("SYS_ALLOC_BAD_SAVE", why=T(e.player_reason))
        return
    usage = str((_data("commands").get("alloc") or {}).get("usage") or "")
    arg = _alloc_arg(env)

    if not arg:
        # 不带参数：把「还剩几点 / 能加哪几维 / 推荐怎么分」一次说清
        # （甲案把点数交给玩家自己分 ⇒ 得让人一眼看见自己手里有点）
        # ★ fix3-⑥：原先这一步读 `SYS_ALLOC_SUGGEST`，那一句开头写着「**设计基线**（按建议权重铺满…）」
        #   —— 策划口径直接上屏（P4 E-5）。换成 `SYS_ALLOC_PLAN`（「推荐分配」），
        #   投法还是同一个口（`alloc.plan`）；旧槽位退役登记见 `scripts/probe_copy.py::RETIRED_DOC`。
        if left <= 0:
            yield T("SYS_ALLOC_DONE", total=AL.total_points(lv))
            return
        yield T("SYS_ALLOC_ASK", usage=usage, left=left, list=_stat_list())
        yield T("SYS_ALLOC_PLAN", total=AL.total_points(lv),
                list=" · ".join("%s %d" % (_stat_slot(s), n)
                                for s, n in AL.plan(lv, cls).items() if n))
        return

    parts = arg.split()
    stat = _stat_of(parts[0])
    if not stat:
        yield T("SYS_ALLOC_BAD_STAT", want=parts[0], list=_stat_list())
        return
    cnt = 1
    if len(parts) > 1:
        try:
            cnt = int(parts[1])
        except (TypeError, ValueError):
            cnt = 0
        if len(parts) > 2 or cnt < 1:
            yield T("SYS_ALLOC_BAD_NUM", want=" ".join(parts[1:]))
            return
    if cnt > left:
        yield T("SYS_ALLOC_SHORT", stat=_stat_slot(stat), n=cnt, left=left, usage=usage)
        return

    from . import panel_build as _PB   # 本地 import（与 `_p` 同一个理由：避免包装载期成环）
    _cap0 = _PB.hp_cap(p, strict=False)          # ★ 加点**前**那一格（唯一来源 = 职业面板）
    try:
        p["alloc"] = AL.apply(al, stat, cnt)
    except AL.AllocError as e:                   # 档上那一格是小数（配平基准那种）⇒ 不截断，点名
        # ★ 台账 L2154 同上：玩家只拿分类句，带坏值的原话进日志。
        _LOG.warning("[aep.alloc] 写入前加点格坏了：%s", e, exc_info=True)
        yield T("SYS_ALLOC_BAD_SAVE", why=T(e.player_reason))
        return
    p = _p(p)                     # ★ 出档口再算一遍：生命上限跟着加点一起动（P-27 同一个口）
    if player is not None:
        player.update(p)
    _bad = _save(env)
    if _bad:
        yield T("SYS_SAVE_FAIL", why=_bad)
        return
    yield T("SYS_ALLOC_OK", stat=_stat_slot(stat), n=cnt,
            now=int((p.get("alloc") or {}).get(stat) or 0), left=left - cnt)
    # ★ fix-n-small ①：**加点也报上限变化** —— 与「装备 / 卸下」那一条**同一句话、同一份数据源**：
    #   槽位 `SYS_GEAR_HP_CAP`（「生命上限 {old} → {new}」）+ 上限走 `panel_build.hp_cap`
    #   这唯一一口（与 `_p` 出档口、`属性` 页、战斗 actor 同一个数）。原先只报「力量 +3」，
    #   上限自己悄悄涨了一格 ⇒ 玩家看不见这一笔投在哪儿兑现（P-27 三处一致，独独回话不提）。
    #   ★ 上限没动（例：只加不带上限的那几维）⇒ **不出这一行**（与装备那条同形：真变了才说）。
    #   ★ 只报上限：**现值那半边一个字不碰** —— 「加点后上限涨、现血/现蓝跟不跟」是队列里
    #     一条**待裁**的口径题（归主线），这里不许顺手拍。（现血/现蓝仍由 `_p` 那条既有口径管。）
    #   ★ 借槽位：真源 `00_总纲/17_文案收口口径_v1.md` 里这一句挂在「装备/卸下」名下，
    #     还没有「加点」自己的槽位名 ⇒ 本轮借 `SYS_GEAR_HP_CAP` 顶上（待补的槽位名写在
    #     分支 `_notes.md`），等主线连同真源表一起补 —— 别在代码里新造中文。
    _cap1 = _PB.hp_cap(p, strict=False)          # 加完点**同一口**再算一遍
    if _cap0 is not None and _cap1 is not None and int(_cap0) != int(_cap1):
        yield T("SYS_GEAR_HP_CAP", old=int(_cap0), new=int(_cap1))


# ══════════════════════════════════════════════════════════════
# 三、POI：这一站有什么（门槛 · P-31）与上手那一下（effect · P-28）
# ══════════════════════════════════════════════════════════════
# ★ P-31：`condition` 的**键词表**（唯一一处）—— 每个键都有唯一一本账：
#   · `time` / `weather` —— 与 `npcs` 的出场条件同一套 token（`CAL.allows` 认时辰 / 天气名）
#   · `event`            —— 与 `npcs` / 世界事件同一个口（`CAL.event_on`）
#   · `quest`            —— 那一条委托交没交（`CAL.main_done`；账由「交活」那一下写）
#   · `read`             —— 读到过那条可读物没有（`codex` 旧物谱（读的），`CX.note_read` 写的账）
#   ★ 词表外的键 / 值查不到对应的账 ⇒ 一律算**判不了**（`unknown`）：点名给玩家看，
#     不当成「不满足」—— 当不满足就是把内容悄悄藏起来，比点名更难被发现。
#   ★ 三处对账：本常量 ↔ `schemas/pois.schema.json` 的 condition 键 ↔ 域里用到的键（probe_pois ⑫）。
POI_COND_KEYS = ("time", "weather", "event", "quest", "read")

#: 门槛「为什么还动不了」那一句的槽位 —— 代码只挑槽位，中文全在 texts 域
_POI_WHY_SLOT = {"time": "SYS_POI_WHY_TIME", "weather": "SYS_POI_WHY_WEATHER",
                 "event": "SYS_POI_WHY_EVENT", "quest": "SYS_POI_WHY_QUEST",
                 "read": "SYS_POI_WHY_READ"}


def _poi_read_slot(rec, p):
    """这一条可读物**此刻**该念哪一条正文槽位（★ g4-⑩：按真实经历分支）。

    数据：`pois.<pid>.text_variant = {"read": "<poi id>"}`（可选）—— 一个「读过了才成立」的条件。
    判据沿用唯一的读账（`p.books.relic` 里那一条 = `CX.note_read` 写的），与 `_poi_cond` 的
    `read` 那一支**同一个来源**（不在两处各判一套）。条件成立 ⇒ 走变体槽位
    `variant_key(base, <poi id>)`（表里有才用）；否则回基础槽位。
    """
    base = str(rec.get("read_text") or "")
    tv = rec.get("text_variant")
    if not (isinstance(tv, dict) and tv and base):
        return base
    pid = str(tv.get("read") or "")
    if not pid:
        return base
    if pid not in ((p.get("books") or {}).get("relic") or {}):
        return base
    from .scene import variant_slot
    return variant_slot(_texts(), base, pid) or base


def _poi_label(rec) -> str:
    """POI 在**文字里**被点名时的写法 —— 与「看得见」那一栏同一形：『名字』图标。

    ★ 本波（P1 体验-10）：门槛那两句（`SYS_POI_NOT_YET` / `SYS_POI_COND_TODO`）原先只传名字 ——
      屏幕上「看得见」那一栏写的是『重复七次的记号』✂️，点名行却是光秃秃的
      「白桦林深处的记号 —— …」，两条名字里都带「记号」时，读起来像在说上面那一条。
      图标从**域里取**（不是代码里写死），写法收在这一处（谁要改口径只改这里）。
    """
    name = str(rec.get("name") or "")
    icon = str(rec.get("icon") or "")
    return "『%s』%s" % (name, icon) if icon else name


def _poi_cond(rec, p, st=None):
    """这条 POI 的门槛此刻过不过 → `(状态, 要说给玩家的那一行)`（P-31）。

    三种状态，五条口（观察 / 去 / 触摸 / 读 / 调查）共用这一处判定：

      · `ok`      —— 没写 `condition`，或门槛成立 ⇒ 那一行是**空串**（不多说一个字）
      · `no`      —— 门槛**判得出、且不成立** ⇒ 这一条这一刻不算在场（列表里不列、上手不上手）
                     + 那一行说清差什么（`SYS_POI_NOT_YET`）—— 不许静默不出现
      · `unknown` —— 门槛**判不了**（键不在词表里 / 值查不到对应的账：如「退潮」今天不是
                     calendar 域的合法 token，或者 `quest` 那一格写的是一面**旗标的名字**
                     （「main06_done」那种 slug）而不是一条委托的 id）
                     ⇒ **照旧在场可用**（把它藏起来 = 悄悄删内容）+ 那一行点名差什么
                     （`SYS_POI_COND_TODO`）—— 待真源定下刻度（台账 P-31 甲）
                     ★ g3-quests2 备注：对话那一族的 slug（`main*_done` 那一族）本波起**有写端**了
                       （`content/prog.py`），但那是**对话 need** 的口径；`quest` 这一格要的仍是
                       **委托 id**（`q_main_06` 那种），别把旗标名写进来 —— 两者不是一个东西。

    `st` 省 = 现取（与 `npcs` 同一口径）；没写 `condition` 的条目**不碰钟**。
    """
    cond = rec.get("condition")
    if not isinstance(cond, dict) or not cond:
        return ("ok", "")
    if st is None:
        st = CAL.state()
    # ★ 本波（P1 体验-10）：点名行里的名字走 `_poi_label`（『名字』图标 —— 与「看得见」同一形），
    #   这里不再单独取一次 `name`（两处取法就有两处口径了）。
    unknown, blocked = [], []
    for key in list(POI_COND_KEYS) + [k for k in cond if k not in POI_COND_KEYS]:
        if key not in cond:
            continue
        want = cond[key]
        if key in ("time", "weather"):
            toks = list(want) if isinstance(want, (list, tuple)) else [want]
            known = [str(t) for t in toks if CAL.resolve(t)[0]]
            if not known:                       # 词表外的 token（真源没有这一档 —— 「涨潮」那类）
                unknown.append(" · ".join(str(t) for t in toks))
            elif not CAL.allows(known, st):
                # ★ fix5-nav（P2 体验）：域里那个词常常是**散文**（「退潮」）—— 别名表把它接到真时辰上
                #   （`rules/calendar.json` 的 `token_alias`）。这里把**刻度**一并点明：
                #   token 不是它自己的正式名（= 它是别名）就补一句「就是「夜」」——
                #   原先只写「得等到退潮」，玩家在浅滩拿六个动词挨个试（报告原话）。
                #   ★ 判据：probe_pois ③-c（别名那一档走新槽位 · 真名字那一档照旧走旧的）。
                _real = []
                for _t in known:
                    _k2, _e2 = CAL.resolve(_t)
                    if _k2 and _t != CAL.name(_e2):
                        _real.append(CAL.name(_e2))
                _slot = "SYS_POI_WHY_TIME_ALIAS" if (key == "time" and _real) else _POI_WHY_SLOT[key]
                blocked.append(T(_slot, token=" · ".join(known), real=" · ".join(_real)))
        elif key == "event":
            nm = str(want)
            if not CAL.event(nm):
                unknown.append(nm)
            elif not CAL.event_on(nm, st, p):
                blocked.append(T(_POI_WHY_SLOT[key], token=nm))
        elif key == "quest":
            qid = str(want)
            q = (_data("quests") or {}).get(qid) or {}
            if not q:                           # 账上没这条委托 ⇒ 判不了（不静默当没过）
                unknown.append(qid)
            elif not CAL.main_done(p, qid):
                blocked.append(T(_POI_WHY_SLOT[key], token=q.get("name") or qid))
        elif key == "read":
            pid = str(want)
            one = (_data("pois") or {}).get(pid) or {}
            if not one.get("into_codex"):
                unknown.append(pid)             # 不进谱的东西没有「读到过」这本账
            elif pid not in ((p.get("books") or {}).get("relic") or {}):
                blocked.append(T(_POI_WHY_SLOT[key], token=one.get("name") or pid))
        else:
            unknown.append("%s %s" % (key, want))     # 词表外的键
    if unknown:
        return ("unknown", T("SYS_POI_COND_TODO", name=_poi_label(rec), keys=" · ".join(unknown)))
    if blocked:
        return ("no", T("SYS_POI_NOT_YET", name=_poi_label(rec), why=" · ".join(blocked)))
    return ("ok", "")


def _pois_here(loc, node, p, st=None):
    """这一站**所有** poi → `[(pid, rec, 状态, 那一行)]` —— 列 poi 的口**只此一处**（P-31）。

    ★ 为什么收成一口（台账 P-31 乙案）：原先 `look` / `go_to` / `touch` / `read_thing` 四处
      各自扫一遍 `pois` 域、都只按 map + subarea 过滤 ⇒ 带 `condition` 的四件永远在场
      （「水下的石阶」「退潮后的石缝」「商会旧账簿」「白桦林深处的记号」）。
    """
    out = []
    for pid, rec in _data("pois").items():
        if rec.get("map") != loc or rec.get("subarea") != node:
            continue
        state, line = _poi_cond(rec, p, st)
        out.append((pid, rec, state, line))
    return out


def rest_places() -> list:
    """有火的那几站（节点名 · 按 pois 域的顺序去重）—— `歇脚` 没有火时**指路**用（★ F6）。

    ★ 与 `_pois_here` 同一处：`pois` 域的读口只在本模块（P-31 / K65）——
      `cmds_gather.py` 里一个 `_data("pois")` 都不许有（`probe_cmds` ㉑④ 钉着）。
    """
    out = []
    for v in (_data("pois") or {}).values():
        if not isinstance(v, dict) or not (v.get("effect") or {}).get("rest"):
            continue
        nm = _name_of_node(str(v.get("map") or ""), str(v.get("subarea") or ""))
        if nm and nm not in out:
            out.append(nm)
    return out


def poi_names_seen(here) -> list:
    """能看见的那几条 —— `no` 不算在场（列表里不列）· `unknown` 照旧在场（点名但不藏）。"""
    return [rec for _pid, rec, state, _ln in here if state != "no"]


def poi_gate_lines(here) -> list:
    """门槛那两句话：不满足的 · 判不了的，各点名一句（`ok` 的一条都不多说）。"""
    return [ln for _pid, _rec, _st, ln in here if ln]


def _poi_pick_by_name(here, want):
    """按玩家写下的名字，从这一站的候选里挑出**该挑的那几件**（空名单 = 没挑中）。

    ★ 命中的判定**只在这一处**（审计 L159）。原先 `touch` / `read_thing` 两处各写一遍
      `want == name or want in name`，**没有 `len` 闸** ⇒ 敲一个单字就是「拿它去挨个名字试」：
        `be_dogs` 敲「记」同时命中「重复七次的记号」「白桦林深处的记号」两件，
        `bn_bone` 敲「碑」同时命中「半埋的碑」「十一块碑」两件
      ⇒ 玩家想摸一件、却连带把两件的增益/消耗一并领走（`touch` 那一支），读也是一次读出两件。

    · **全名相等优先于名字的一部分**（一条叫「记号」、另一条叫「深处的记号」时，
      玩家写「记号」要拿到前者 —— 与 `loot.match_ids` / `cmds_skill._by_name` 同一口径，
      免得撞上哪一条取决于遍历序，K71 同族）；
    · **部分命中至少两个字**（`len(want) >= 2`）—— 单字不是名字，是运气；
    · 两档都没命中就交**空名单**，由调用方照实点名说「这儿没有叫这个的」——
      **不静默塞一件给他**（原口径里点错名会拿到别的，正是这件事）。
    """
    want = str(want or "").strip()
    if not want:
        return list(here)
    exact, part = [], []
    for item in here:
        nm = str(item[1].get("name") or "")        # ★ 候选形状恒为 (pid, rec, 状态, 那一行)
        if want == nm:
            exact.append(item)
        elif nm and len(want) >= 2 and want in nm:
            part.append(item)
    return exact or part


#: ★ P-28：`effect.buff` 带数值时落进**现成容器** `food_buff`（形状 `{stat, pct, until}`）。
#:   stat 只认这四档 —— 与 `gear.BUFF_KEY` 是同一个词表（菜那套 + 本批加的 `spd`），别另开一份。
#:   ★ 为什么本批把 `spd` 加进白名单（甲 · 数据里那件要的就是它）：骨田边那件 POI 是
#:     「诸神离开已久，只留遗迹与**祷词**」那条世界线下的一处 —— 摸的不是护身符，
#:     是「心里定下来 ⇒ 脚程快一点」，落到面板上正是 `spd`（速度）。
#:     而 `atk / def / hp` 三档是**烹饪**的领地（`05 §三`「攻击 / 防御 / 生命上限三选一」）——
#:     再给同一档就是「一个菜的效果换了个名字」。`spd` 是引擎真读的面板键
#:     （CTB 的两次行动间隔，`probe_panel` 钉着骑士 L10 = 109.0），与菜不重叠。
#:   ★ 数值口径（本批落的值 · 真源待补）：`spd +10%` · `900 秒`（时长数据里本来就有）。
#:     10% 与菜那档同量级（`items.food.pct` 现为 10–15%）；`spd` 只影响行动序，
#:     不像攻击那样直接改伤害链 ⇒ 取菜档的**下沿**。
POI_BUFF_STATS = ("atk", "def", "hp", "spd")


def _poi_buff_label(key) -> str:
    """增益的中文名 —— 只在 texts 域（`SYS_STAT_<键>` 那一族，与「属性」页 / 加点同一处）。

    **代码里一个中文名都不写**：`01_属性字典 §2.2` 的词条名就是这么进 texts 的；
    键 → 槽位的写法与 `_stat_slot`（五维）同款。
    """
    return T("SYS_STAT_%s" % str(key or "").upper())

#: ★ P-28 甲（**兜底护栏** · 只在数据「写了 buff 名字却没写数值」时生效）：回生命上限的这一成数
#:   （与 `cmds_gather.rest` 的歇脚同一个 20% · 封顶）。
#:   ★ 本批起数据里那一件已经给了真数值（`spd` + `pct`）⇒ 走上面那一支，兜底不参与；
#:     它继续留着是为了「新写的 buff 忘了写数值」时不至于静默什么都不发生。
#:   为什么不猜别的：`buff_shrine_blessing` 那类名字全仓没有定义处、文档也没给刻度
#:   ⇒ 一律按最保守的那一档落地，并把「往 pois 的 effect 里补 `stat` / `pct`」写在这里
#:   （补上就**自动变成真增益，这一行不用改**）。
POI_BLESS_HEAL_PCT = 0.2


def _poi_verb_ok(rec, verb) -> bool:
    """这条 POI 的 effect 归不归**现在这个动词**（`need` 缺省 = 谁都能碰；写了就只认那一个）。"""
    need = (rec.get("effect") or {}).get("need")
    return (not need) or str(need) == str(verb)


def _poi_buff_spec(eff):
    """`effect.buff` 的数值 → `(面板键, 百分比)`；**没写数值给 None**（不猜属性、不猜数）。"""
    key = str(eff.get("stat") or "")
    if key not in POI_BUFF_STATS:
        return None
    try:
        pct = int(eff.get("pct") or 0)
    except (TypeError, ValueError):
        return None
    return (key, pct) if pct > 0 else None


def _poi_heal_gain(p, eff, mx):
    """`effect` 里「回多少」的那两个词（与 items 域同一套：`hp` 固定 · `hp_pct` 上限的几成）。

    返回 `(有没有写, 回多少)` —— 没写 = `(False, 0)`：**不猜**，由上头的安全默认那一档接管。
    `mx` = 生命上限（★ P-27：由调用方从唯一来源取好 —— 本函数不自己去翻档）。
    """
    hit, gain = False, 0
    if "hp" in eff:
        hit, gain = True, gain + int(eff.get("hp") or 0)
    if "hp_pct" in eff:
        hit, gain = True, gain + int(round(mx * float(eff.get("hp_pct") or 0)))
    return hit, max(0, gain)


async def poi_effect_lines(env, sink, uid, p, pid, rec, verb, player=None):
    """★ P-28：POI `effect` 的**唯一**消费端 —— 原先这一个字段谁都没读（数据写了白写）。

    「触摸（`verb='touch'`）」与「读（`verb='read'`）」都从这一处过。四条口径，
    **数据里没写的一律不猜**：

      · `need` —— 写了就只认那一个动词。三个隐藏点写的是 `need: "search"` ⇒ 归「搜查」
        （那条线在 `cmds_gather`）：本口**不越权**代它消费，也不替它出「去搜」的提示 ——
        隐藏点的**产出**归不归 `pois.effect.loot` 还没拍板（台账 P-28 乙），而原先那三条
        `effect.loot` 指的池子（`dp_hidden_camp` / `dp_hidden_birch` / `dp_hidden_shoal`）
        在 `drop_pools` 域里**根本不存在**（悬空引用）⇒ 出提示等于把玩家引到死路上。
        ★ B3-28 ②（2026-09-25）：三条悬空引用**已摘掉**（选择与理由见 `_notes.md`；
          真源今天给不出这三张池的条目 / 权重，照形状补池就得编数）；判据补在 `probe_pois` ⑬
          （凡写 `effect.loot` 必须在 `drop_pools` 里查得到 —— 悬空当场红）。
      · `rest: true` —— 歇脚回血。**不抄第二份**：整支委托 `cmds_gather.rest`
        （同一个「上限的 20% · 封顶」口径 —— 那边改了这儿跟着变）。
      · `buff` —— 短时增益。**带数值的**（`stat` ∈ `POI_BUFF_STATS` + `pct` + `duration` 秒）
        写进**现成容器 `food_buff`**（`cmds_recipe.item_use` 写的就是它、`gear.food_buff`
        一直在读它 → 进引擎面板最后一层 `mul`）⇒ 不新建容器、不动读者、不碰面板。
        中文名走 `_poi_buff_label`（texts 域那一族槽位），增益名 `buff` 只是数据里的一个标签。
        **只写了名字没写数值的**不瞎猜属性与数值 —— 走数据里写着的 `hp` / `hp_pct`
        （与药水同一个词表）；连这个都没写，就按兜底 `POI_BLESS_HEAL_PCT`
        （上限的 20% 回血 · 与歇脚同一个数）落地，并把「补 stat / pct」写在报告与注释里。
      · `talk` —— 按 id 去 dialogues 域找那条对话，**找到**就说它的第一句（择优逻辑
        只有一处：`cmds_talk._pick_indexed`）；**找不到**就明说没这条（fail-closed ——
        今天三条篝火都是这一档：`talk_campfire_*` 全仓没有定义处）。
      · 其余键 —— 出一行点名的 fail-closed 行（`SYS_POI_EFFECT_TODO`）；`buff` 写了数值
        但认不出的（属性不在 atk/def/hp 里 · `pct` 不是正数）同样点名（`SYS_POI_BUFF_BAD`）
        —— 两种情况都不静默吞掉。

    动了档就在这一口里落（`player.update` + `_save`）—— 与别处同一个口。
    """
    eff = rec.get("effect")
    if not isinstance(eff, dict) or not eff:
        return
    if not _poi_verb_ok(rec, verb):
        return
    name = rec.get("name") or pid
    dirty = False
    consumed = {"need"}                  # ★ 认下的键（收尾时「没认下的」点名 —— 不静默吞）

    if eff.get("rest"):
        from . import cmds_gather as CG           # 本地 import：免得包装载期成环
        async for line in CG.rest(env, sink, uid, player):
            yield line
        consumed.add("rest")
        # ★ 歇脚那一支写的是 `player`（它自己有一套 `_p`）—— 把血回填进外层这份拷贝：
        #   同一趟里后面那句 `player.update(p)` 会拿旧血把它盖回去（实测踩到过）。
        if player is not None and "hp" in player:
            p["hp"] = player["hp"]

    spec = _poi_buff_spec(eff) if eff.get("buff") else None
    if spec:
        from . import facade
        key, pct = spec
        secs = int(eff.get("duration") or 0)
        p["food_buff"] = {"stat": key, "pct": pct, "until": float(facade.clock()) + secs}
        dirty = True
        consumed.update(("buff", "stat", "stat_name", "pct", "duration"))
        yield T("SYS_POI_BUFF", name=name,
                buff="%s +%d%%" % (eff.get("stat_name") or _poi_buff_label(key), pct),
                minutes=secs // 60)
    else:
        # ★ P-27：上限只有一个来源（职业面板）。档上还没有职业 ⇒ **不出假数**：出一行点名的
        #   fail-closed 行（借槽位，见 `hp_cap_or_line`），这一支整段不做。
        mx, _line = hp_cap_or_line(p)
        wrote, gain = _poi_heal_gain(p, eff, mx or 0)
        if eff.get("buff") or wrote:
            consumed.update(("buff", "duration", "hp", "hp_pct"))
            if _line:
                yield _line
            else:
                bad = []
                if eff.get("buff") and not wrote:
                    # ★ 只写了名字、没写数值 —— **不猜属性也不猜数**：
                    #   按兜底「回生命上限的 POI_BLESS_HEAL_PCT」落地（与歇脚同一个数）。
                    #   真写了数值但认不出的那几个子键点名（fail-closed：别让它看着像生效了）。
                    gain = max(1, int(mx * POI_BLESS_HEAL_PCT))
                    bad = [k for k in ("stat", "stat_name", "pct") if k in eff]
                hp0 = int(p.get("hp") or mx)
                hp = min(mx, hp0 + gain)          # ★ 封顶：不许超过上限（与药水同一口径）
                p["hp"] = hp
                dirty = True
                if bad:
                    yield T("SYS_POI_BUFF_BAD", name=name, keys=" · ".join(bad))
                yield T("SYS_POI_BLESS", name=name, add=max(0, hp - hp0), hp=hp, max=mx)

    if eff.get("talk"):
        dlg = _data("dialogues").get(str(eff.get("talk"))) or {}
        nodes = dlg.get("nodes") or {}
        said = ""
        if nodes:
            from . import cmds_talk as CT         # 择优那一支只有一处，不抄第二份
            st = CAL.state()
            # ★ P1-6（2026-09-29 · 文案车道 P1）：层序**只认 `CT.LAYERS`**。
            #   原先这里硬写了一份 ("main","hidden","meet","daily","idle") —— 与
            #   `cmds_talk.LAYERS`（meet → daily → main → hidden → idle）
            #   **顺序正好相反**（那一版是 P-12 之前的旧口径，撤了没跟着撤）。
            #   后果：POI 的 `effect.talk` 碰到**同时有 meet 与 main** 的树时，
            #   先出 main —— 玩家还没「熟」就先看到那一层（与 P-12 修掉的
            #   「刚认识就剧透」同一个病，只是这条路上没人钉过）。
            #   ★ 不新建第二份常量：直接复用 `CT.LAYERS`（择优逻辑只有一处，
            #   层序也只有一处 —— 判据见 `probe_dialogues ⑯`）。
            _picked = None
            for nn in CT.LAYERS:
                if nn in nodes:
                    _idx, said = CT._pick_indexed(nodes[nn].get("texts"), p, st)
                    if said:
                        _picked = (nn, _idx, said)
                        break
            # ★ P1-28（2026-09-29 · 文案车道 P1）：这一条路原来**只调 `_pick_indexed`** ——
            #   那是「按顺序挑第一条满足的」，于是固定世界状态（时辰 / 天气 / 进度都不变）
            #   下每趟都挑中同一句 ⇒ 玩家连敲两次篝火，看到的是**逐字相同**的一段。
            #   NPC 那条路（`cmds_talk._pick_layer`）早就修过这一档（P1-16 / P1-19 / P1-26），
            #   唯独 POI 触摸这条路没接上去 —— 物件树一个句池都轮换不了。
            #   修法**不新造机制**：走读端已有的 `CT.rotate`（heard + 搭话次数那套现成容器），
            #   与 NPC 同一口径、同一份存档形状、同一处判定。
            #   ★ 层序、够层判定、need 择优一个字节没动 —— 只改「这一趟说哪句」。
            if _picked is not None:
                _rl, _ri, said = CT.rotate(nodes, p, st, str(eff.get("talk")), _picked)
                # ★ P1-28：把「这一趟说出去的是哪一句」记下来 —— 轮换判据就是它
                #   （`heard` 那套现成容器）。这条路原先从不记 ⇒ 每趟都像第一趟
                #   ⇒ 轮换那一档永远进不去。NPC 那条路在 `cmds_talk.ask` 里记，
                #   这里补上同一次记账（同一份存档形状、同一格键）。
                if said:
                    CT.note_heard(p, str(eff.get("talk")), _rl, _ri)
                    #   搭过几次也要记 —— `rotate` 第 ④ 档（全都说过了之后在层内轮换）
                    #   用 `_talk_count` 选句；不记它就是恒 0 ⇒ 那一档又冻回第一句。
                    CT.note_talk(p, str(eff.get("talk")))
                    dirty = True
        if said:
            consumed.add("talk")
            for one in str(said).split("\n"):
                yield one
        else:
            consumed.add("talk")
            yield T("SYS_POI_TALK_MISSING", name=name)

    unknown = [k for k in eff if k not in consumed]
    if unknown:
        yield T("SYS_POI_EFFECT_TODO", name=name, keys=" · ".join(sorted(unknown)))

    if dirty:
        if player is not None:
            player.update(p)
        _bad = _save(env)
        if _bad:
            yield T("SYS_SAVE_FAIL", why=_bad)
            return


# ══════════════════════════════════════════════════════════════
# 四、可读物（触摸）
# ══════════════════════════════════════════════════════════════
def _poi_touch_gives(rec) -> bool:
    """这一样东西**上手真给得出内容** → True（★ 本波 · P2 BUG②）。

    给得出 = 两样里占一样：
      · 有正文（`read_text` —— 可读物，以及本波给三处隐藏点补上的那三句）
      · 有一个**归「触摸」这个动词**的 `effect`（`rest` / 带数值的 `buff` / `talk`；门槛 `need` 写的是
        别的动词 = 那样东西的产出归那条线，本口不越权代它消费）

    ★ 为什么要有这一条：原先「看得见」里的每一样都**无条件**先吐一行「📦你摸到…」——
      三处隐藏点（`effect.need = search`、没有正文）在屏幕上就是**一行标题、零内容**；
      玩家以为自己摸到了那件东西（P2 BUG②，`📍` `🐚` 正是最想摸的两件）。
      ⇒ 上手给不出内容的，这一支**不出声**（别假装摸到了）；整站一样都上不了手时，
      末尾那一句 `SYS_TOUCH_NONE` 兜底（P1 BUG-6）。
    """
    eff = rec.get("effect")
    if isinstance(eff, dict) and eff and _poi_verb_ok(rec, "touch"):
        return True
    return bool(str(rec.get("read_text") or "").strip())


async def touch(env, sink, uid, player):
    """`触摸 [<东西>]` —— 上手摸。

    ★ F6（QA P2 BUG⑧）：原先**不吃参数**（`触摸 半埋的碑` 回「这句我没接住」），
      同一个 POI 上「读」吃得下名字、「触摸」吃不下 —— 玩家想只摸某一件事做不到，
      还得连带把整站的增益/消耗一并领了。现在与 `读` 同一待遇：
      点了名就只摸那一件；名字对不上照实说（不静默换成「这儿没有可以上手的」——
      这儿明明有，只是他敲错了名字）。
    """
    p = _p(player)
    # ★ P-31：这一站的 poi 走唯一一口（门槛现看）—— 原先这一条自己扫域、`condition` 谁都没读，
    #   带条件的四件（水下的石阶 / 退潮后的石缝 / 商会旧账簿 / 白桦林深处的记号）永远能上手。
    here = _pois_here(p["loc"], p["node"], p)
    if not here:
        yield T("SYS_TOUCH_NONE")
        return
    want = AV.arg_of(env)                     # ★ F6：跟着自己的声明剥参（连写也算）
    if want:
        hit = _poi_pick_by_name(here, want)          # ★ 命中判定只此一处（L159）
        if not hit:
            yield T("SYS_TOUCH_MISS", name=want,
                    list=" · ".join("『%s』" % v.get("name") for _pid, v, _st, _ln in here))
            return
        here = hit
    got = []
    got, touched = [], 0
    for pid, v, cond_state, cond_line in here:
        if cond_state == "no":                # 门槛判得出不成立 ⇒ 这一下不做，但点名说清差什么
            yield cond_line
            continue
        if cond_line:                         # 判不了的门槛：照旧可用（藏起来 = 静默删内容），只点名
            yield cond_line
        # ★ 本波（P2 BUG②）：上手给不出内容的**不出声** —— 别吐一行标题就当摸到了。
        if not _poi_touch_gives(v):
            continue
        yield T("SYS_TOUCH_GET", icon=v.get("icon", ""), name=v.get("name"))
        touched += 1
        rt = _poi_read_slot(v, p)              # ★ g4-⑩：按真实经历取正文（读过白桦树 ⇒ 变体那一条）
        if rt:
            yield "「%s」" % T(rt)
        if v.get("into_codex") and CX.note_read(p, pid):     # ★ 读到就进旧物谱（先一行问号）
            # ★ B3-10 裁决：`into_codex` **空串** = 就地线索（塔内那几条 · 22 §二「可做」列）——
            #   读到就念正文，但**不进旧物谱**（12 类那个量账不动）。判据：probe_pois ②b/⑩。
            got.append(pid)
        # ★ P-28：上手那一下的 effect 走唯一消费端（原先 `effect` 谁都读 —— 摸了等于没摸）
        async for line in poi_effect_lines(env, sink, uid, p, pid, v, "touch", player=player):
            yield line
    # ★ 本波（P1 BUG-6）：这一站一样都上不了手（有东西但门槛全挡着 / 全归别的动词）⇒
    #   照别处一样明说，**别把「看得见」栏的锁定说明当成触摸结果**（玩家会以为摸到了那本账簿）。
    if not touched:
        yield T("SYS_TOUCH_NONE")
    if got:
        if player is not None:
            player.update(p)
        _bad = _save(env)
        if _bad:
            yield T("SYS_SAVE_FAIL", why=_bad)
            return
        for pid in got:
            yield T("SYS_CODEX_NEW", book=CX.label("relic"), name=CX.name_of("relic", pid))
    for line in egg_lines(p, player, env):      # ★ B3-1：读过东西那一处可能连上另一处
        yield line
    for line in title_lines(p, player, env):    # ★ B3-2：读过的东西也算数
        yield line


async def read_thing(env, sink, uid, player):
    """按编号读一样东西（第一阶段先给第一条）。

    ★ P-23：这条声明此前只在代码里（`commands.json` 没声明）⇒ 玩家只能靠「触摸」读物。
    现在接上了；点名的写法（`读 墙上的划痕`）按名字挑，点错名照「这儿没有能读的东西」说 ——
    fail-closed：不随便塞一样给玩家（同一处有两个可读物时最容易出这种错）。
    """
    p = _p(player)
    want = AV.arg_of(env)        # ★ B4-11：跟着自己的声明剥参（连写也算）
    # ★ P-31：与「触摸」同一个口（门槛现看）—— 门槛判得出不成立的：正文一个字都不给，只点名
    at = [(pid, v, st_, ln_) for pid, v, st_, ln_ in _pois_here(p["loc"], p["node"], p)
          if v.get("read_text")]
    here = at
    if want:
        here = _poi_pick_by_name(here, want)          # ★ 命中判定只此一处（L159）
    usable = [(pid, v, st_, ln_) for pid, v, st_, ln_ in here if st_ != "no"]
    blocked = [ln_ for _pid, _v, _st, ln_ in here if _st == "no"]
    if not usable:
        for _ln in blocked:                   # 拦下来的那条：说清差什么（不静默回「没有能读的」）
            yield _ln
        if not blocked:
            # ★ QB-6（试玩报告 P2 BUG⑨）：点了名却对不上时，原话只回「这里没有能读的东西」——
            #   而这一站明明有两件可读物，玩家会以为这站本来就没东西、转身走掉。
            #   ⇒ 名字对不上就**点名说对不上**，再把这站**现在真能读的**列出来（fail-closed：
            #     不因为名字没对上就随便塞一件给他读）。没点名（空参）时行为一个字不变。
            if want and at:
                yield T("SYS_READ_NOSUCH", name=want)
                names = [v.get("name") for _pid, v, st_, _ln in at if st_ != "no" and v.get("name")]
                if names:
                    yield T("SYS_READ_HERE", list=" · ".join(names))
            else:
                yield T("SYS_READ_NONE")
        return
    k, v, _st, _ln = usable[0]
    if _ln:                                   # 判不了的门槛：正文照给，门槛那一句一起点名
        yield _ln
    yield T("SYS_READ_HEAD", name=v.get("name"))
    yield T(_poi_read_slot(v, p))            # ★ g4-⑩：按真实经历取正文（读过白桦树 ⇒ 变体那一条）
    # ★ P-28：可读物身上的 effect 也走同一个消费端（「读」与「触摸」不分家）
    async for line in poi_effect_lines(env, sink, uid, p, k, v, "read", player=player):
        yield line
    if v.get("into_codex") and CX.note_read(p, k):        # ★ B3-10：空串 = 就地线索，不进谱（同 touch）
        if player is not None:
            player.update(p)
        _bad = _save(env)
        if _bad:
            yield T("SYS_SAVE_FAIL", why=_bad)
            return
        yield T("SYS_CODEX_NEW", book=CX.label("relic"), name=CX.name_of("relic", k))


async def hint(env, sink, uid, player):
    """`提示 [去哪]` —— ★ QB-5：**先给当前委托的下一步**，手上没活才退回地点那一句。

    真源 `06_第一阶段垂直切片/04_指令总表 §一`：「`提示` `去哪` ｜ 随时 ｜ **给一条当前该做什么
    的提示**」。改前只看地点（镇上 / 野外各一句固定文案）⇒ 接了活以后那句永远不变，而每条接活
    回话都写着「『提示』会告诉你往哪走」（`quest_accept` → `SYS_JOB_GO`）。
    ★ 野外那一句（往北 / 往东 / 往西）说的是**地形**、与进度无关 ⇒ 有活时也照样补在后面。
    """
    p = _p(player)
    from .cmds_quest import _hint_lines          # 本地 import：免得装载期成环（同 quest_accept 那处）
    lines = _hint_lines(p)
    if lines:
        for line in lines:
            yield line
        if p["loc"] != TOWN:
            yield T("SYS_HINT_WILD")
        return
    if p["loc"] == TOWN:
        yield T("SYS_HINT_TOWN")
    else:
        yield T("SYS_HINT_WILD")


async def help_cmd(env, sink, uid, player):
    """指令表 —— **只列有处理器的声明**（P-23）。

    ★ 为什么按 `bind` 判：`commands.json` 是声明真源，`bind` 就是「包内真有实现体」那一栏
      （`content/commands.py::load_declared_bindings` 只登记带 bind 的）。原先按 `visible`
      全列 ⇒ 94 条里有 43 条是**敲了没反应**的（玩家照着表敲，回一句「未提供处理器」）。
    """
    cmds = _data("commands")
    cats = {}
    for k, v in cmds.items():
        if v.get("visible") is False:
            continue
        if not v.get("bind"):
            continue
        cats.setdefault(v.get("category") or T("SYS_HELP_CAT_OTHER"), []).append(v.get("usage") or k)
    yield T("SYS_HELP_HEAD")
    for c, ws in cats.items():
        yield T("SYS_HELP_ROW", cat=c, list=" · ".join("『%s』" % w for w in ws))
    # ★ P1 BUG-9 ① / P4 E-11（本波 f4）：**界面上的承诺改诚实** —— 战斗那一栏与别的栏一样是
    #   一串平铺的『防御』『打断』『技能 <参数>』…，读起来像「逐手出招」。
    #   ★ G2（本波）撤掉的就是那句「一条指令打完整场」：**战斗真分了一手一手**，
    #     帮助尾巴改成本波的口径（`SYS_HELP_BATTLE_TURN`）。旧槽位 `SYS_HELP_BATTLE_NOTE`
    #     的包内读端到这一行就没了 —— 它的退役登记在 `scripts/probe_copy.py::RETIRED_DOC`
    #     （真源那一行的**值**要由主线改：真源仓对本分支只读 ⇒ 账在 `_notes.md`）。
    _bat = str((cmds.get("attack") or {}).get("category") or "")
    if _bat and any(str(c) == _bat for c in cats):
        yield T("SYS_HELP_BATTLE_TURN")


def declared_soon(env):
    """声明了、包内还没实现的指令 —— **只说人话**（P-23）。

    ★ 引擎的降级回显（`saintess_engine/host/runtime.py::declared_echo`）把**内部 key**
      与「包内 content/commands.py 里没有它的 handler」一起丢给玩家 —— 引擎零改动，
      所以包侧自己接住这些声明（`content/commands.py::load_declared_soon`）：玩家看到的
      只剩一个槽位（`SYS_CMD_SOON`），一眼知道「这条还没接上」。
    """
    spec = (getattr(env, "state", None) or {}).get("spec")
    name = (getattr(spec, "usage", "") or "").strip()
    if not name:
        name = (getattr(env, "text", "") or "").strip()
    return [T("SYS_CMD_SOON", name=name)]
