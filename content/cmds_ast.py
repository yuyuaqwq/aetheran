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


def _save(env):
    """★ 落档是处理器的责任（引擎 2026-09-15 起不再每条消息整档回写）。"""
    try:
        env.save()
    except Exception:
        pass


def _p(player):
    """玩家档（引擎给的是 dict；缺字段用默认值补齐 —— 不改原档）。"""
    if not isinstance(player, dict):
        return dict(DEFAULT_PLAYER)
    p = dict(DEFAULT_PLAYER)
    p.update(player)
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
    p = _move(p, "belt_north", "bn_bone", sink)
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_MOVE_OUT_NORTH")
    yield _map_scene("belt_north")            # ★ B3-6a：地一屏从 texts 来（原先内联在代码里）


async def go_east(env, sink, uid, player):
    p = _p(player)
    p = _move(p, "belt_east", "be_birch", sink)
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_MOVE_OUT_EAST")
    yield _map_scene("belt_east")             # ★ B3-6a：同上


async def go_west(env, sink, uid, player):
    p = _p(player)
    p = _move(p, "belt_west", "bw_old_ferry", sink)
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_MOVE_OUT_WEST")
    yield _map_scene("belt_west")             # ★ B3-6a：同上


async def enter_town(env, sink, uid, player):
    p = _p(player)
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
    npc_here = [v for v in _data("npcs").values() if v.get("map") == loc and v.get("subarea") == hit]
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
    yield T("SYS_ORIGIN_WHY", why=rs.get("why") or T("SYS_ORIGIN_WHY_TODO"))


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
# 三、可读物（触摸）
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
    """按编号读一样东西（第一阶段先给第一条）。"""
    p = _p(player)
    here = [(k, v) for k, v in _data("pois").items()
            if v.get("map") == p["loc"] and v.get("subarea") == p["node"] and v.get("read_text")]
    if not here:
        yield T("SYS_READ_NONE")
        return
    k, v = here[0]
    yield T("SYS_READ_HEAD", name=v.get("name"))
    yield T(v["read_text"])
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
    cmds = _data("commands")
    cats = {}
    for k, v in cmds.items():
        if v.get("visible") is False:
            continue
        cats.setdefault(v.get("category") or T("SYS_HELP_CAT_OTHER"), []).append(v.get("usage") or k)
    yield T("SYS_HELP_HEAD")
    for c, ws in cats.items():
        yield T("SYS_HELP_ROW", cat=c, list=" · ".join("『%s』" % w for w in ws))
