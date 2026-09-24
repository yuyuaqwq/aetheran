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
        return "【缺文案：%s】" % key
    s = rec.get("value", "")
    for k, v in slots.items():
        s = s.replace("{%s}" % k, str(v))
    return s


# ── 玩家档（形状：location/level/race/class/name/hp…）──────────────
DEFAULT_PLAYER = {
    "name": "", "race": "", "cls": "", "level": 1, "exp": 0,
    "loc": "windmill_town", "node": "wt_gate_n", "prev": [],
    "hp": 100, "hp_max": 100, "mo": 0, "mo_max": 0,
    "gold": 30, "bag": {}, "equipped": {}, "flags": {}, "codex": {},
}


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


def _map_of(loc):
    return _data("maps").get(loc)


def _node_of(loc, node):
    m = _map_of(loc) or {}
    for n in m.get("nodes") or []:
        if n.get("id") == node:
            return n
    return None


def _neighbors(loc, node):
    """按拓扑算邻居：chain 取前后，star 取首节点为中心。"""
    m = _map_of(loc) or {}
    nodes = [n.get("id") for n in (m.get("nodes") or [])]
    if node not in nodes:
        return []
    i = nodes.index(node)
    if (m.get("topology") or "chain") == "star":
        center = nodes[0]
        return [x for x in nodes if x != node] if node == center else [center]
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
    return p


# ══════════════════════════════════════════════════════════════
# 一、移动与世界
# ══════════════════════════════════════════════════════════════
async def look(env, sink, uid, player):
    p = _p(player)
    loc, node = p["loc"], p["node"]
    m = _map_of(loc) or {}
    yield T("SCENE_" + loc.upper(), name=m.get("name", loc)) if ("SCENE_" + loc.upper()) in _texts() \
        else "【%s · %s】" % (m.get("name", loc), _name_of_node(loc, node))
    yield "━" * 12
    nb = [_name_of_node(loc, x) for x in _neighbors(loc, node)]
    yield "往哪走：" + " · ".join("『%s』" % x for x in nb) if nb else "这里是尽头。"
    poi_here = [v for v in _data("pois").values()
                if v.get("map") == loc and v.get("subarea") == node]
    if poi_here:
        yield "看得见：" + " · ".join("『%s』%s" % (v.get("name"), v.get("icon", "")) for v in poi_here)
    npc_here = [v for v in _data("npcs").values()
                if v.get("map") == loc and v.get("subarea") == node]
    if npc_here:
        yield "人在：" + " · ".join("『%s』%s" % (v.get("name"), v.get("icon", "")) for v in npc_here)
    yield "「『触摸』可以上手摸，『聆听』可以听，『地图』看全貌。」"


async def map_view(env, sink, uid, player):
    p = _p(player)
    loc, node = p["loc"], p["node"]
    m = _map_of(loc) or {}
    nodes = m.get("nodes") or []
    yield "【%s（%s）】" % (m.get("name", loc), "村镇" if m.get("topology") == "star" else "野外")
    for n in nodes:
        mark = "▸" if n.get("id") == node else " "
        yield "%s %s%s" % (mark, n.get("name"), "（你现在在这儿）" if mark == "▸" else "")


async def listen(env, sink, uid, player):
    p = _p(player)
    yield T("WORLD_LISHEN_%s" % p["loc"].upper()) if ("WORLD_LISHEN_%s" % p["loc"].upper()) in _texts() \
        else "风声。远处有水声。没有别的声音。"


async def time_now(env, sink, uid, player):
    yield "现在是白昼。这一带的天黑得早，入夜之后外面会有别的东西走动。"


async def go_north(env, sink, uid, player):
    p = _p(player)
    p = _move(p, "belt_north", "bn_bone", sink)
    if player is not None:
        player.update(p)
    _save(env)
    yield "你走出北门。风车在背后慢慢转，声音越来越远。"
    yield "【骨田】半埋的碑一块挨着一块，土是灰的。往北是拾荒营地与旧哨塔。"


async def go_east(env, sink, uid, player):
    p = _p(player)
    p = _move(p, "belt_east", "be_birch", sink)
    if player is not None:
        player.update(p)
    _save(env)
    yield "你往东走。路两边很快全是白桦，树皮上刻着东西。"
    yield "【白桦林】鸟叫得很密。往深处还有空地。"


async def go_west(env, sink, uid, player):
    p = _p(player)
    p = _move(p, "belt_west", "bw_old_ferry", sink)
    if player is not None:
        player.update(p)
    _save(env)
    yield "你往西走。脚下的土越来越湿，能听见水。"
    yield "【浅滩渡口】水退下去了一块，露出一段石阶，一级一级往水里去。"


async def enter_town(env, sink, uid, player):
    p = _p(player)
    p["prev"] = (p.get("prev") or [])[-8:] + [(p.get("loc"), p.get("node"))]
    p["loc"] = "windmill_town"
    p["node"] = "wt_gate_n"
    if player is not None:
        player.update(p)
    _save(env)
    yield "风车镇。三架风车，一条土路，镇口有块刻着字的石头。"
    yield "「『观察』看细节，『往东』『往西』『北口』出门，『公会』在挂板墙。」"


async def go_back(env, sink, uid, player):
    p = _p(player)
    prev = p.get("prev") or []
    if not prev:
        yield "再往回就是你来时的地方了 —— 没什么可回的。"
        return
    loc, node = prev[-1]
    p["prev"] = prev[:-1]
    p["loc"], p["node"] = loc, node
    if player is not None:
        player.update(p)
    _save(env)
    yield "你退回 %s。" % _name_of_node(loc, node)


# ══════════════════════════════════════════════════════════════
# 二、角色
# ══════════════════════════════════════════════════════════════
async def status(env, sink, uid, player):
    p = _p(player)
    nm = p.get("name") or "无名者"
    yield "【%s】%s · %s · %s 级" % (nm, p.get("race") or "未定", p.get("cls") or "未定", p.get("level"))
    yield "生命 %s/%s ｜ 法力 %s/%s ｜ 铜板 %s" % (p.get("hp"), p.get("hp_max"),
                                                    p.get("mo"), p.get("mo_max"), p.get("gold"))
    yield "经验 %s ｜ 在 %s" % (p.get("exp"), _map_of(p["loc"]).get("name", p["loc"]) if _map_of(p["loc"]) else p["loc"])


async def origin(env, sink, uid, player):
    p = _p(player)
    if not p.get("race"):
        yield "你还没决定自己是谁。"
        return
    rs = _data("races").get("race_" + (p.get("race") or "").lower()) or {}
    yield "你是%s。" % rs.get("name", p.get("race"))
    yield "你为什么来：%s" % rs.get("why", "（这一句还没写）")


async def bag(env, sink, uid, player):
    p = _p(player)
    items = p.get("bag") or {}
    if not items:
        yield "背包是空的。"
        return
    yield "【背包】%d 种" % len(items)
    for k, v in list(items.items())[:20]:
        it = _data("items").get(k) or {}
        yield "· %s %s ×%s" % (it.get("icon", ""), it.get("name", k), v)
    if len(items) > 20:
        yield "…（还有 %d 种）" % (len(items) - 20)


async def money(env, sink, uid, player):
    p = _p(player)
    yield "你身上有 %s 枚铜板。" % p.get("gold")


# ══════════════════════════════════════════════════════════════
# 三、可读物（触摸）
# ══════════════════════════════════════════════════════════════
async def touch(env, sink, uid, player):
    p = _p(player)
    here = [v for v in _data("pois").values()
            if v.get("map") == p["loc"] and v.get("subarea") == p["node"]]
    if not here:
        yield "这里没有什么可以上手的。"
        return
    for v in here:
        yield "%s你摸到%s。" % (v.get("icon", ""), v.get("name"))
        rt = v.get("read_text")
        if rt:
            yield "「%s」" % T(rt)


async def read_thing(env, sink, uid, player):
    """按编号读一样东西（第一阶段先给第一条）。"""
    p = _p(player)
    here = [(k, v) for k, v in _data("pois").items()
            if v.get("map") == p["loc"] and v.get("subarea") == p["node"] and v.get("read_text")]
    if not here:
        yield "这里没有能读的东西。"
        return
    k, v = here[0]
    yield "【%s】" % v.get("name")
    yield T(v["read_text"])
    if v.get("into_codex"):
        yield "（这一条已经进你的%s）" % v["into_codex"]


async def hint(env, sink, uid, player):
    p = _p(player)
    if p["loc"] == "windmill_town":
        yield "先『观察』看看镇口那块石头，再去『公会』接一件小活。"
    else:
        yield "往北是骨田和旧哨塔，往东是白桦林，往西是浅滩渡口。『返回』回上一个地方。"


async def help_cmd(env, sink, uid, player):
    cmds = _data("commands")
    cats = {}
    for k, v in cmds.items():
        if v.get("visible") is False:
            continue
        cats.setdefault(v.get("category", "其它"), []).append(v.get("usage") or k)
    yield "【指令表】"
    for c, ws in cats.items():
        yield "· %s：%s" % (c, " · ".join("『%s』" % w for w in ws))
