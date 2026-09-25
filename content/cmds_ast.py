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
from . import titles as TT            # 称号（B3-2）：显示跟着名字走 · 判定在 titles 域
from . import scene as SC           # 场景槽位解析（B3-6a）：节点级近景 → 退地图级第一眼

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
DEFAULT_PLAYER = {
    "name": "", "race": "", "cls": "", "level": 1, "exp": 0,
    "loc": "windmill_town", "node": "wt_gate_n", "prev": [],
    "hp": 100, "hp_max": 100, "mo": 0, "mo_max": 0,
    "gold": 30, "bag": {}, "equipped": {}, "flags": {}, "codex": {},
}

#: ★ 复活点（`00_总纲/03_主要玩法 §4.9`「回白烛堂」）—— 风车镇的节点 id（探针核它是真节点）
CHAPEL = ("windmill_town", "wt_chapel")


def exp_need(level):
    """升一级所需经验 —— **唯一真源**：交活升级与死亡惩罚都走这一个口。

    ★ 口径有两份（已记台账待拍板 P-22）：`06_第一阶段垂直切片/00_第一阶段内容总纲_v1 §七`
      写的是 `45 × L^1.5`，本包 B2-1 落的是 `L² × 40` —— 两者对不上。在鱼鱼定下来之前，
      这里就是本包内部唯一的那个口（改一处，升级与死亡一起跟着变）。
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
_MUTABLE = ("bag", "equipped", "flags", "codex")


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
    """
    p = dict(DEFAULT_PLAYER)
    if isinstance(player, dict):
        p.update(player)
    p = _fresh(p)
    if not isinstance(p.get("prev"), list):
        p["prev"] = []
    return p


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
    raw = (getattr(env, "text", "") or "").strip()
    parts = raw.split(None, 1)
    want = parts[1].strip() if len(parts) > 1 else ""
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


def _npcs_here(loc, node, st=None):
    """这个节点此刻的活人 —— ★ 出场条件（时辰/天气）现看。

    条件是「与」：写了 time 与 weather 就两个都要满足；`event` 类条件留给事件层（B3-5），
    这里**不判**（判了会让商队那两位永远不出现 —— 而那属于事件层的事）。
    """
    if st is None:
        st = CAL.state()
    out = []
    for k, v in _data("npcs").items():
        if v.get("map") != loc or v.get("subarea") != node:
            continue
        cond = v.get("condition") or {}
        if not (CAL.allows(cond.get("time"), st) and CAL.allows(cond.get("weather"), st)):
            continue
        out.append((k, v))
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
    poi_here = [v for v in _data("pois").values()
                if v.get("map") == loc and v.get("subarea") == node]
    if poi_here:
        yield T("SYS_LOOK_SEES", list=" · ".join("『%s』%s" % (v.get("name"), v.get("icon", "")) for v in poi_here))
    npc_here = [v for _k, v in _npcs_here(loc, node)]
    if npc_here:
        yield T("SYS_LOOK_WHO", list=" · ".join("『%s』%s" % (v.get("name"), v.get("icon", "")) for v in npc_here))
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


async def go_north(env, sink, uid, player):
    p = _p(player)
    if (p["loc"], p["node"]) == ("belt_north", "bn_bone"):        # ★ B3-11：脚下这一站（K60）
        for line in _here_lines(p):
            yield line
        return
    p = _move(p, "belt_north", "bn_bone", sink)
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_MOVE_OUT_NORTH")
    yield _map_scene("belt_north")            # ★ B3-6a：地一屏从 texts 来（原先内联在代码里）


async def go_east(env, sink, uid, player):
    p = _p(player)
    if (p["loc"], p["node"]) == ("belt_east", "be_birch"):        # ★ B3-11：脚下这一站（K60）
        for line in _here_lines(p):
            yield line
        return
    p = _move(p, "belt_east", "be_birch", sink)
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_MOVE_OUT_EAST")
    yield _map_scene("belt_east")             # ★ B3-6a：同上


async def go_west(env, sink, uid, player):
    p = _p(player)
    if (p["loc"], p["node"]) == ("belt_west", "bw_old_ferry"):        # ★ B3-11：脚下这一站（K60）
        for line in _here_lines(p):
            yield line
        return
    p = _move(p, "belt_west", "bw_old_ferry", sink)
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_MOVE_OUT_WEST")
    yield _map_scene("belt_west")             # ★ B3-6a：同上


async def enter_town(env, sink, uid, player):
    p = _p(player)
    if (p["loc"], p["node"]) == ("windmill_town", "wt_gate_n"):        # ★ B3-11：脚下这一站（K60）
        for line in _here_lines(p):
            yield line
        return
    p["prev"] = (p.get("prev") or [])[-8:] + [(p.get("loc"), p.get("node"))]
    p["loc"] = "windmill_town"
    p["node"] = "wt_gate_n"
    CX.note_visit(p, "windmill_town", "wt_gate_n")
    CX.note_step(p, "windmill_town", "wt_gate_n")
    if player is not None:
        player.update(p)
    _save(env)
    yield _map_scene("windmill_town")         # ★ B3-6a：进镇那一屏从 texts 来（原内联）
    yield T("SYS_TOWN_ENTER_HINT")


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
    raw = (getattr(env, "text", "") or "").strip()
    parts = raw.split(None, 1)
    want = parts[1].strip() if len(parts) > 1 else ""
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
    poi_here = [v for v in _data("pois").values() if v.get("map") == loc and v.get("subarea") == hit]
    # ★ B3-15：走唯一一口 —— 出场条件（时辰 / 天气）现看。改前这一条自己扫域、不判条件，
    #   白天的「去 北墙根」照样把只在该在昏/夜的哈根列出来（与「观察」「问路」两处口径不一致）。
    npc_here = [v for _k, v in _npcs_here(loc, hit)]
    if poi_here:
        yield T("SYS_LOOK_SEES", list=" · ".join("『%s』%s" % (v.get("name"), v.get("icon", "")) for v in poi_here))
    if npc_here:
        yield T("SYS_LOOK_WHO", list=" · ".join("『%s』%s" % (v.get("name"), v.get("icon", "")) for v in npc_here))


# ══════════════════════════════════════════════════════════════
# 二、角色
# ══════════════════════════════════════════════════════════════
async def status(env, sink, uid, player):
    p = _p(player)
    nm = name_with_title(p)                     # ★ B3-2：称号跟着名字走进面板
    yield T("SYS_STATUS_HEAD", who=nm, race=_race_label(p.get("race")),
            cls=_cls_label(p.get("cls")), level=p.get("level"))
    yield T("SYS_STATUS_VITALS", hp=p.get("hp"), hp_max=p.get("hp_max"),
            mo=p.get("mo"), mo_max=p.get("mo_max"), gold=p.get("gold"))
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


async def bag(env, sink, uid, player):
    p = _p(player)
    items = p.get("bag") or {}
    if not items:
        yield T("SYS_BAG_EMPTY")
        return
    yield T("SYS_BAG_HEAD", n=len(items))
    from . import loot as LT                      # 本地 import：避免包装载期的环
    for k, v in list(items.items())[:20]:
        rec = LT.rec_of(k)                        # ★ 未鉴定的 marker：名字与图标写在池上
        yield "· %s %s ×%s" % (rec.get("icon", ""), rec.get("name", k), v)
    if len(items) > 20:
        yield T("SYS_BAG_MORE", n=len(items) - 20)


async def money(env, sink, uid, player):
    p = _p(player)
    yield T("SYS_MONEY_POUCH", gold=p.get("gold"))


# ══════════════════════════════════════════════════════════════
# 三、POI 的 effect（P-28）—— 原先「数据写了没人读」的那一个字段，唯一消费端在这一处
# ══════════════════════════════════════════════════════════════
#: ★ P-28：`effect.buff` 带数值时落进**现成容器** `food_buff`（形状 `{stat, pct, until}`）。
#:   stat 只认这三档 —— 与 `gear.BUFF_KEY` 是同一个词表（菜那套），别另开一份。
POI_BUFF_STATS = ("atk", "def", "hp")

#: ★ P-28 甲（**待拍板**）：`effect.buff` **只写了名字、没写数值**时的安全默认 ——
#:   回生命上限的这一成数（与 `cmds_gather.rest` 的歇脚同一个 20% · 封顶）。
#:   为什么不猜别的：`buff_shrine_blessing` 全仓没有定义处，文档（`05 §二`）只有
#:   「神龛（短时增益）」一句 —— 给什么属性、多少，谁都没写。⇒ 按最保守的那一档落地，
#:   让「摸了什么都不发生」变成「摸了有回血」；数值一旦定下来，往 pois 的 effect 里补
#:   `stat` / `pct`（见 `_poi_buff_spec`）就**自动变成真增益，这一行不用改**。
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


def _poi_heal_gain(p, eff):
    """`effect` 里「回多少」的那两个词（与 items 域同一套：`hp` 固定 · `hp_pct` 上限的几成）。

    返回 `(有没有写, 回多少)` —— 没写 = `(False, 0)`：**不猜**，由上头的安全默认那一档接管。
    """
    hit, gain = False, 0
    if "hp" in eff:
        hit, gain = True, gain + int(eff.get("hp") or 0)
    if "hp_pct" in eff:
        mx = int(p.get("hp_max") or 100)
        hit, gain = True, gain + int(round(mx * float(eff.get("hp_pct") or 0)))
    return hit, max(0, gain)


async def poi_effect_lines(env, sink, uid, p, pid, rec, verb, player=None):
    """★ P-28：POI `effect` 的**唯一**消费端 —— 原先这一个字段谁都没读（数据写了白写）。

    「触摸（`verb='touch'`）」与「读（`verb='read'`）」都从这一处过。四条口径，
    **数据里没写的一律不猜**：

      · `need` —— 写了就只认那一个动词。三个隐藏点写的是 `need: "search"` ⇒ 归「搜查」
        （那条线在 `cmds_gather`）：本口**不越权**代它消费，也不替它出「去搜」的提示 ——
        那三条 `effect.loot` 指的池子在 drop_pools 域里**根本不存在**（悬空引用），
        出提示等于把玩家引到死路上。⇒ 报告里挂 P-28 待拍板（乙）。
      · `rest: true` —— 歇脚回血。**不抄第二份**：整支委托 `cmds_gather.rest`
        （同一个「上限的 20% · 封顶」口径 —— 那边改了这儿跟着变）。
      · `buff` —— 短时增益。**带数值的**（`stat` ∈ atk/def/hp + `pct` + `duration` 秒）
        写进**现成容器 `food_buff`**（`cmds_recipe.item_use` 写的就是它、`gear.food_buff`
        一直在读它 → 进引擎面板最后一层 `mul`）⇒ 不新建容器、不动读者、不碰面板。
        **只写了名字没写数值的**（今天的神龛就是这一档）不瞎猜属性与数值 —— 走数据里
        写着的 `hp` / `hp_pct`（与药水同一个词表）；连这个都没写，就按安全默认
        `POI_BLESS_HEAL_PCT`（上限的 20% 回血 · 与歇脚同一个数）落地，口径写在报告里
        （P-28 甲 待拍板）。
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
                buff="%s +%d%%" % (eff.get("stat_name") or key, pct), minutes=secs // 60)
    else:
        wrote, gain = _poi_heal_gain(p, eff)
        if eff.get("buff") or wrote:
            mx = int(p.get("hp_max") or 100)
            bad = []
            if eff.get("buff") and not wrote:
                # ★ 只写了名字、没写数值（今天的神龛就是这一档）—— **不猜属性也不猜数**：
                #   按安全默认「回生命上限的 POI_BLESS_HEAL_PCT」落地（与歇脚同一个数）。
                #   真写了数值但认不出的那几个子键点名（fail-closed：别让它看着像生效了）。
                gain = max(1, int(mx * POI_BLESS_HEAL_PCT))
                bad = [k for k in ("stat", "stat_name", "pct") if k in eff]
            hp0 = int(p.get("hp") or mx)
            hp = min(mx, hp0 + gain)              # ★ 封顶：不许超过上限（与药水同一口径）
            p["hp"] = hp
            dirty = True
            consumed.update(("buff", "duration", "hp", "hp_pct"))
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
    here = [(k, v) for k, v in _data("pois").items()
            if v.get("map") == p["loc"] and v.get("subarea") == p["node"]]
    if not here:
        yield T("SYS_TOUCH_NONE")
        return
    got = []
    for pid, v in here:
        yield T("SYS_TOUCH_GET", icon=v.get("icon", ""), name=v.get("name"))
        rt = v.get("read_text")
        if rt:
            yield "「%s」" % T(rt)
        if v.get("into_codex") and CX.note_read(p, pid):     # ★ 读到就进旧物谱（先一行问号）
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
    raw = (getattr(env, "text", "") or "").strip()
    parts = raw.split(None, 1)
    want = parts[1].strip() if len(parts) > 1 else ""
    here = [(k, v) for k, v in _data("pois").items()
            if v.get("map") == p["loc"] and v.get("subarea") == p["node"] and v.get("read_text")]
    if want:
        here = [(k, v) for k, v in here
                if want == (v.get("name") or "") or want in (v.get("name") or "")]
    if not here:
        yield T("SYS_READ_NONE")
        return
    k, v = here[0]
    yield T("SYS_READ_HEAD", name=v.get("name"))
    yield T(v["read_text"])
    # ★ P-28：可读物身上的 effect 也走同一个消费端（「读」与「触摸」不分家）
    async for line in poi_effect_lines(env, sink, uid, p, k, v, "read", player=player):
        yield line
    if v.get("into_codex") and CX.note_read(p, k):
        if player is not None:
            player.update(p)
        _save(env)
        yield T("SYS_CODEX_NEW", book=CX.label("relic"), name=CX.name_of("relic", k))


async def hint(env, sink, uid, player):
    p = _p(player)
    if p["loc"] == "windmill_town":
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
