# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体（第一版 · 最小可玩集）。

契约（引擎 `saintess_engine.command.binding`）：实现体是 **async generator**，
`yield` 出行文本；调用帧 `handler(sink, *args)`（`args` 只有 group_id/uid/player 三槽位）。

本文件**只读本包自己的数据**（`content/data/*.json`），不 import 宿主、不 import 扩展包
（接线在 `apply.py`）。玩家档的形状见 `content/persistence.py`。
"""
from __future__ import annotations

import json
import os

from . import calendar as CAL        # 时辰/天气的唯一出口（它不 import 本模块，无环）
from . import codex as CX            # 图鉴四谱的唯一记录口（B2-7）
from . import eggs as EG              # 彩蛋（B3-1）：条件在 eggs 域，判定走引擎声明算子
from . import alloc as AL             # ★ P-34：加点算术的唯一出口（等级→总点数−已花=余额）
from . import titles as TT            # 称号（B3-2）：显示跟着名字走 · 判定在 titles 域
from . import scene as SC           # 场景槽位解析（B3-6a）：节点级近景 → 退地图级第一眼
from . import timed_events as TE     # 限时事件那一格（B3-5）：宿主维护门落档 · 这里只读
from . import affix as AFFIX
from . import argv as AV          # ★ B4-11：取参的唯一口（零依赖 ⇒ 本模块也能 import）         # ★ B3-24：精英词条（观察那行预告 = 遭遇的同一个种子）

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_CACHE: dict = {}


def _data(name: str):
    if name not in _CACHE:
        with open(os.path.join(_DIR, name + ".json"), encoding="utf-8") as f:
            _CACHE[name] = json.load(f)
    return _CACHE[name]


def _texts():
    return _data("texts")


def T(key: str, **slots):
    """取一条文案（fail-closed：缺 key 直接回显 key，不静默）。"""
    rec = _texts().get(key)
    if not rec:
        return "[MISSING TEXT: %s]" % key
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


def _scene_line(loc, node, m=None):
    """观察那一段场景 —— 节点级 SCENE_<节点>（近景）→ 退 SCENE_<地图>（这张图的第一眼）。

    ★ 解析口只有一处（content/scene.py）—— 落域脚本与这里共用，别各写一遍。
    """
    sk = SC.resolve(_texts(), loc, node)
    m = m if m is not None else (_map_of(loc) or {})
    if sk:
        return T(sk, name=m.get("name", loc))
    return "【%s · %s】" % (m.get("name", loc), _name_of_node(loc, node))


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


def _save(env):
    """★ 落档是处理器的责任（引擎 2026-09-15 起不再每条消息整档回写）。"""
    try:
        env.save()
    except Exception:
        pass


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
    #   而面板里骑士是 50 ⇒ 同一件事两处口径。现蓝读档（缺省 0）—— 与战斗 actor 的起手
    #   （`combat.player_actor` 的 `setdefault("mp", 0)`）对得上，不发明「开战满蓝」这种
    #   真源没写的规矩（法力要不要真做 = 台账 §3 新记的那笔）。
    mcap = _PB.mp_cap(p, strict=False)
    if mcap is None:
        p.pop("mo_max", None)                              # 无职业 ⇒ 这一格也不留（照实说未定）
    else:
        p["mo_max"] = mcap
        p["mo"] = max(0, min(int(p.get("mo") or 0), mcap))
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
    _save(env)
    yield T("SYS_RACE_DONE", name=rec.get("name", kid), line=rec.get("line") or "")
    for tal in (rec.get("talents") or []):
        yield T("SYS_RACE_TALENT", name=tal.get("name", ""), effect=tal.get("effect", ""))
    cost = rec.get("cost") or {}
    if cost:
        yield T("SYS_RACE_COST", name=cost.get("name", ""), effect=cost.get("effect", ""))
    if not p.get("cls"):        # ★ B4-7：建号第二步在等着（定过就不再啰嗦）
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
    """建号第二步那一眼：每种打法两行（一行是什么人 · 一行什么节奏）。文案一个字都不在这里写。"""
    out = [T("SYS_CLS_HEAD", race=_race_label(p.get("race")))]
    for i, (k, v) in enumerate(_cls_all(), 1):
        out.append(T("SYS_CLS_ROW", i="①②③④⑤⑥"[i - 1] if i <= 6 else str(i),
                     star=_cls_star(p, v), icon=v.get("icon", ""), name=v.get("name", k),
                     role=v.get("role", ""), desc=v.get("desc", "")))
        out.append(T("SYS_CLS_MECH", mech=v.get("mech", "")))
        edge = _cls_edge_line(v)        # ★ P-50：优势 / 弱点那一栏（真源行没落 ⇒ 今天不印）
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
    _save(env)
    yield T("SYS_CLS_DONE", name=rec.get("name", kid))
    yield T("SYS_CLS_MECH", mech=rec.get("mech", ""))
    if p.get("hp_max"):
        yield T("SYS_CLS_HP", hp=p.get("hp"), max=p.get("hp_max"))
    yield T("SYS_CLS_NEXT", left=AL.left_of_record(p), alloc=_alloc_verb())
    if not str(p.get("name") or "").strip():            # 建号第三步（取名）还没走完
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



def _move(p, loc, node, sink_lines):
    p["prev"] = (p.get("prev") or [])[-8:] + [(p.get("loc"), p.get("node"))]
    p["loc"] = loc
    p["node"] = node
    CX.note_visit(p, loc, node)               # ★ 记录（去过哪儿）
    CX.note_step(p, loc, node)                # ★ B3-2：记一趟（「骨田的常客」靠它）
    return p


def _here_lines(p) -> list:
    """★ K60：目标 == 脚下这一站 —— 说「到了」，别假装又走了一趟（B3-10 立的 · B3-11 收全）。

    四条出口（北口 / 往东 / 往西 / 进镇）原先**无条件**先往 `prev` 压一条「当前这一站」：
    站在骨田再敲一次「北口」会 ① 再演一遍出门那一屏 ② 历史里多一条自己（下一次
    『返回』就成了原地打转） ③ 「去过几回」虚增一趟（称号「骨田的常客」靠它）。
    判据：probe_copy ⑫（真跑四条 × 站在目的地上敲）。
    """
    loc, node = p.get("loc"), p.get("node")
    out = [T("SYS_MOVE_HERE", name=_name_of_node(loc, node))]
    nb = [_name_of_node(loc, x) for x in _neighbors(loc, node)]
    if nb:
        out.append(T("SYS_MOVE_CAN", list=" · ".join("『%s』" % x for x in nb)))
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
    _save(env)
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
    _save(env)
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
    # ★ P-10：还没定族 —— 第一眼不是风景，是「你是谁」（建号是玩的第一步）
    if not p.get("race"):
        for line in race_menu():
            yield line
        return
    if TT.newest(p):                            # ★ B3-2：称号跟着名字走（一个都没拿到就不多这一行）
        yield name_with_title(p)
    loc, node = p["loc"], p["node"]
    m = _map_of(loc) or {}
    yield _scene_line(loc, node, m)           # ★ B3-6a：节点级近景 → 退地图级第一眼
    yield "━" * 12
    nb = [_name_of_node(loc, x) for x in _neighbors(loc, node)]
    yield T("SYS_LOOK_WAY", list=" · ".join("『%s』" % x for x in nb)) if nb else T("SYS_LOOK_DEAD_END")
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
    for line in event_lines(p, loc, node):      # ★ B3-5：这一站聚人那一下（集日）
        yield line
    # ★ B3-24：这一格今天的精英 —— 观察**提前看到**（09_ §二「玩家在「观察」时能提前看到」）。
    #   与「攻击」的遭遇读**同一个口**（同一 uid / 图 / 节点 / 游戏日 ⇒ 同一种子）⇒ 这行是真预告；
    #   文案逐字走 texts 槽位（`COMBAT_ELITE_SPAWN`），本文件不写一个字。
    _el = AFFIX.elite_of(_data("monsters"), loc, node, uid,
                         CAL.state().get("game_day"), int(p.get("level", 1) or 1))
    if _el:
        yield AFFIX.elite_line(str((_data("monsters")[_el[0]] or {}).get("name", _el[0])), _el[1])
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


async def listen(env, sink, uid, player):
    p = _p(player)
    yield T("WORLD_LISHEN_%s" % p["loc"].upper()) if ("WORLD_LISHEN_%s" % p["loc"].upper()) in _texts() \
        else T("SYS_LISTEN_DEFAULT")


async def time_now(env, sink, uid, player):
    """★ 时辰与天气的唯一呈现口（模板 SYS_WEATHER_CHANGE = 26 消息模板第 13 类）。"""
    p = _p(player)
    st = CAL.tick(p)                       # 钟源 = 宿主注入（facade.clock），本模块不自己取钟
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_WEATHER_CHANGE", place=_name_of_node(p["loc"], p["node"]),
            hour=st["hour_name"], weather=st["weather_name"],
            flavor=T(CAL.desc_slot(st["weather"])))
    yield T(CAL.desc_slot(st["hour"]))


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
    _save(env)
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
    p = _p(player)
    if (p["loc"], p["node"]) == ("belt_north", "bn_bone"):        # ★ B3-11：脚下这一站（K60）
        for line in _here_lines(p):
            yield line
        return
    # ★ P-52：出镇那一条的「在镇上」守卫 —— 唯一执行面 = `town.town_gate`（B4-12 收的口）。
    #   本地 import：`town` 要 import 本模块，模块级 import 会成环（与 `_p` 里 panel_build 同一手）。
    #   被拦 ⇒ 一句话、**位置与历史一个字不动**（不 `_save`）。
    from .town import town_gate
    _blocked = town_gate(p)
    if _blocked:
        yield _blocked
        return
    p = _move(p, "belt_north", "bn_bone", sink)
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_MOVE_OUT_NORTH")
    yield _map_scene("belt_north")            # ★ B3-6a：地一屏从 texts 来（原先内联在代码里）
    for line in event_lines(p, "belt_north", "bn_bone", entered=True):    # ★ B3-5：一句进林描述
        yield line


async def go_east(env, sink, uid, player):
    p = _p(player)
    if (p["loc"], p["node"]) == ("belt_east", "be_birch"):        # ★ B3-11：脚下这一站（K60）
        for line in _here_lines(p):
            yield line
        return
    from .town import town_gate                                   # ★ P-52：同 `go_north`
    _blocked = town_gate(p)
    if _blocked:
        yield _blocked
        return
    p = _move(p, "belt_east", "be_birch", sink)
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_MOVE_OUT_EAST")
    yield _map_scene("belt_east")             # ★ B3-6a：同上
    for line in event_lines(p, "belt_east", "be_birch", entered=True):    # ★ B3-5：同上
        yield line


async def go_west(env, sink, uid, player):
    p = _p(player)
    if (p["loc"], p["node"]) == ("belt_west", "bw_old_ferry"):        # ★ B3-11：脚下这一站（K60）
        for line in _here_lines(p):
            yield line
        return
    from .town import town_gate                                   # ★ P-52：同 `go_north`
    _blocked = town_gate(p)
    if _blocked:
        yield _blocked
        return
    p = _move(p, "belt_west", "bw_old_ferry", sink)
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_MOVE_OUT_WEST")
    yield _map_scene("belt_west")             # ★ B3-6a：同上
    for line in event_lines(p, "belt_west", "bw_old_ferry", entered=True):    # ★ B3-5：同上
        yield line


async def enter_town(env, sink, uid, player):
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
    _save(env)
    yield _map_scene(TOWN)                                      # ★ B3-6a：进镇那一屏从 texts 来（原内联）
    yield T("SYS_TOWN_ENTER_HINT")
    for line in event_lines(p, TOWN, "wt_gate_n", entered=True):  # ★ B3-5：进镇那一下
        yield line


async def go_back(env, sink, uid, player):
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
    _save(env)
    yield T("SYS_MOVE_BACK", name=_name_of_node(loc, node))


async def go_to(env, sink, uid, player):
    """`去 <地方>` —— 在同一张图里走到另一个节点。

    ★ 为什么需要它：玩家到了镇上（风车镇是 star 拓扑 11 个节点），若只能在
      「北口 / 东口 / 西口」之间跳，北墙根（哈根）、白烛堂（艾德/莉安）这些地方
      **永远走不到** —— 而 NPC 在那儿。
    规则：目标必须是**当前节点的邻居**（不是任意节点）—— 跨图要先出门。
    """
    p = _p(player)
    want = AV.arg_of(env)        # ★ B4-11：跟着自己的声明剥参（连写也算）
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
        yield T("SYS_MOVE_NOSUCH", name=want)
        yield T("SYS_MOVE_CAN", list=" · ".join("『%s』" % _name_of_node(loc, x) for x in nb))
        return
    p["prev"] = (p.get("prev") or [])[-8:] + [(loc, node)]
    p["node"] = hit
    CX.note_visit(p, loc, hit)
    CX.note_step(p, loc, hit)                 # ★ B3-2：走到的那一趟
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_MOVE_TO", name=_name_of_node(loc, hit))
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
async def status(env, sink, uid, player):
    p = _p(player)
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
        yield T("SYS_STATUS_VITALS", hp=p.get("hp"), hp_max=cap,
                mo=p.get("mo"), mo_max=mcap, gold=p.get("gold"))
    yield T("SYS_STATUS_EXP", exp=p.get("exp"),
            place=_map_of(p["loc"]).get("name", p["loc"]) if _map_of(p["loc"]) else p["loc"])


async def origin(env, sink, uid, player):
    p = _p(player)
    if not p.get("race"):
        yield T("SYS_ORIGIN_NONE")
        return
    rs = _race_rec(p.get("race"))
    yield T("SYS_ORIGIN_WHO", name=rs.get("name") or _race_label(p.get("race")))
    yield T("SYS_ORIGIN_WHY",
            why=rs.get("line") or rs.get("why") or T("SYS_ORIGIN_WHY_TODO"))  # ★ P-10：域里的字段叫 line（原来读 why，永远给「还没写」）


def _bag_rows(p) -> list:
    """背包里每一行（★ 顺序 = 档上的插入序）—— 分页只负责切，行怎么拼只在这一处。"""
    from . import loot as LT                      # local import：免得包装载期成环
    rows = []
    for k, v in (p.get("bag") or {}).items():
        rec = LT.rec_of(k)                        # ★ 未鉴定的 marker：名字与图标写在池上
        # ★ B4-20：名字走 `LT.label_of` —— 「域里重名的那些」缀品阶（同名四档装备原先两行一模一样）
        rows.append("· %s %s ×%s" % (rec.get("icon", ""), LT.label_of(k), v))
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
    p = _p(player)
    cls = str(p.get("cls") or "").strip()
    if not cls:
        yield T("SYS_ATTR_NOCLS")
        return
    lv = max(1, int(p.get("level") or 1))
    try:
        al = AL.of_record(p)                     # 这档实际分了多少（唯一口；坏档 ⇒ 抛）
        left = AL.balance(lv, al)
    except AL.AllocError as e:
        yield T("SYS_ALLOC_BAD_SAVE", why=e)
        return
    usage = str((_data("commands").get("alloc") or {}).get("usage") or "")
    arg = _alloc_arg(env)

    if not arg:
        # 不带参数：把「还剩几点 / 能加哪几维 / 设计基线长什么样」一次说清
        # （甲案把点数交给玩家自己分 ⇒ 得让人一眼看见自己手里有点）
        if left <= 0:
            yield T("SYS_ALLOC_DONE", total=AL.total_points(lv))
            return
        yield T("SYS_ALLOC_ASK", usage=usage, left=left, list=_stat_list())
        # 只列**真投得出点**的维（0 点的维不占屏）；投法来自同一份权重（`alloc.plan`）
        yield T("SYS_ALLOC_SUGGEST", total=AL.total_points(lv),
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

    try:
        p["alloc"] = AL.apply(al, stat, cnt)
    except AL.AllocError as e:                   # 档上那一格是小数（配平基准那种）⇒ 不截断，点名
        yield T("SYS_ALLOC_BAD_SAVE", why=e)
        return
    p = _p(p)                     # ★ 出档口再算一遍：生命上限跟着加点一起动（P-27 同一个口）
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_ALLOC_OK", stat=_stat_slot(stat), n=cnt,
            now=int((p.get("alloc") or {}).get(stat) or 0), left=left - cnt)


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


def _poi_cond(rec, p, st=None):
    """这条 POI 的门槛此刻过不过 → `(状态, 要说给玩家的那一行)`（P-31）。

    三种状态，五条口（观察 / 去 / 触摸 / 读 / 调查）共用这一处判定：

      · `ok`      —— 没写 `condition`，或门槛成立 ⇒ 那一行是**空串**（不多说一个字）
      · `no`      —— 门槛**判得出、且不成立** ⇒ 这一条这一刻不算在场（列表里不列、上手不上手）
                     + 那一行说清差什么（`SYS_POI_NOT_YET`）—— 不许静默不出现
      · `unknown` —— 门槛**判不了**（键不在词表里 / 值查不到对应的账：如「退潮」今天不是
                     calendar 域的合法 token，「main06_done」这样的 flag 全仓没有写端）
                     ⇒ **照旧在场可用**（把它藏起来 = 悄悄删内容）+ 那一行点名差什么
                     （`SYS_POI_COND_TODO`）—— 待真源定下刻度（台账 P-31 甲）

    `st` 省 = 现取（与 `npcs` 同一口径）；没写 `condition` 的条目**不碰钟**。
    """
    cond = rec.get("condition")
    if not isinstance(cond, dict) or not cond:
        return ("ok", "")
    if st is None:
        st = CAL.state()
    name = str(rec.get("name") or "")
    unknown, blocked = [], []
    for key in list(POI_COND_KEYS) + [k for k in cond if k not in POI_COND_KEYS]:
        if key not in cond:
            continue
        want = cond[key]
        if key in ("time", "weather"):
            toks = list(want) if isinstance(want, (list, tuple)) else [want]
            known = [str(t) for t in toks if CAL.resolve(t)[0]]
            if not known:                       # 认不出的 token（「退潮」今天就是这一档）
                unknown.append(" · ".join(str(t) for t in toks))
            elif not CAL.allows(known, st):
                blocked.append(T(_POI_WHY_SLOT[key], token=" · ".join(known)))
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
        return ("unknown", T("SYS_POI_COND_TODO", name=name, keys=" · ".join(unknown)))
    if blocked:
        return ("no", T("SYS_POI_NOT_YET", name=name, why=" · ".join(blocked)))
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


def poi_names_seen(here) -> list:
    """能看见的那几条 —— `no` 不算在场（列表里不列）· `unknown` 照旧在场（点名但不藏）。"""
    return [rec for _pid, rec, state, _ln in here if state != "no"]


def poi_gate_lines(here) -> list:
    """门槛那两句话：不满足的 · 判不了的，各点名一句（`ok` 的一条都不多说）。"""
    return [ln for _pid, _rec, _st, ln in here if ln]


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
            for nn in ("main", "hidden", "meet", "daily", "idle"):
                if nn in nodes:
                    _idx, said = CT._pick_indexed(nodes[nn].get("texts"), p, st)
                    if said:
                        break
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
        _save(env)


# ══════════════════════════════════════════════════════════════
# 四、可读物（触摸）
# ══════════════════════════════════════════════════════════════
async def touch(env, sink, uid, player):
    p = _p(player)
    # ★ P-31：这一站的 poi 走唯一一口（门槛现看）—— 原先这一条自己扫域、`condition` 谁都没读，
    #   带条件的四件（水下的石阶 / 退潮后的石缝 / 商会旧账簿 / 白桦林深处的记号）永远能上手。
    here = _pois_here(p["loc"], p["node"], p)
    if not here:
        yield T("SYS_TOUCH_NONE")
        return
    got = []
    for pid, v, cond_state, cond_line in here:
        if cond_state == "no":                # 门槛判得出不成立 ⇒ 这一下不做，但点名说清差什么
            yield cond_line
            continue
        if cond_line:                         # 判不了的门槛：照旧可用（藏起来 = 静默删内容），只点名
            yield cond_line
        yield T("SYS_TOUCH_GET", icon=v.get("icon", ""), name=v.get("name"))
        rt = v.get("read_text")
        if rt:
            yield "「%s」" % T(rt)
        if v.get("into_codex") and CX.note_read(p, pid):     # ★ 读到就进旧物谱（先一行问号）
            # ★ B3-10 裁决：`into_codex` **空串** = 就地线索（塔内那几条 · 22 §二「可做」列）——
            #   读到就念正文，但**不进旧物谱**（12 类那个量账不动）。判据：probe_pois ②b/⑩。
            got.append(pid)
        # ★ P-28：上手那一下的 effect 走唯一消费端（原先 `effect` 谁都读 —— 摸了等于没摸）
        async for line in poi_effect_lines(env, sink, uid, p, pid, v, "touch", player=player):
            yield line
    if got:
        if player is not None:
            player.update(p)
        _save(env)
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
    here = [(pid, v, st_, ln_) for pid, v, st_, ln_ in _pois_here(p["loc"], p["node"], p)
            if v.get("read_text")]
    if want:
        here = [(pid, v, st_, ln_) for pid, v, st_, ln_ in here
                if want == (v.get("name") or "") or want in (v.get("name") or "")]
    usable = [(pid, v, st_, ln_) for pid, v, st_, ln_ in here if st_ != "no"]
    blocked = [ln_ for _pid, _v, _st, ln_ in here if _st == "no"]
    if not usable:
        for _ln in blocked:                   # 拦下来的那条：说清差什么（不静默回「没有能读的」）
            yield _ln
        if not blocked:
            yield T("SYS_READ_NONE")
        return
    k, v, _st, _ln = usable[0]
    if _ln:                                   # 判不了的门槛：正文照给，门槛那一句一起点名
        yield _ln
    yield T("SYS_READ_HEAD", name=v.get("name"))
    yield T(v["read_text"])
    # ★ P-28：可读物身上的 effect 也走同一个消费端（「读」与「触摸」不分家）
    async for line in poi_effect_lines(env, sink, uid, p, k, v, "read", player=player):
        yield line
    if v.get("into_codex") and CX.note_read(p, k):        # ★ B3-10：空串 = 就地线索，不进谱（同 touch）
        if player is not None:
            player.update(p)
        _save(env)
        yield T("SYS_CODEX_NEW", book=CX.label("relic"), name=CX.name_of("relic", k))


async def hint(env, sink, uid, player):
    p = _p(player)
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
