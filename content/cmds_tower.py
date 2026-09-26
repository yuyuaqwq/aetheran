# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 第九组：副本（旧哨塔 · B3-6）

五条声明（`content/data/commands.json` 的「副本」那一节）在这里接上实现体：
**进塔 · 下一层 · 副本地图 · 调查 · 撤退**。塔内是**三张图之外**的第五张图
（`maps.old_watchtower`，12 间房 · chain 拓扑），12 间房的名字 / 描述 / 出口 / 可读物
照 `06_第一阶段垂直切片/22_旧哨塔_逐间设计_v1.md`（唯一真源）。

★ 一条都不写死在本文件里（代码常量里不许出现内容侧取值）：
  · 12 间房与三层的分组 = `maps.old_watchtower.floors`（数据声明）
  · 进塔的那一格 = `maps.old_watchtower.entrance` = {map, node}（跨图：从「旧哨塔下」进）
  · 塔顶那一间 = `roles.entry` 点的那间（进塔之后站哪儿，不写死 id）
  · 玩家可见文案 = 一律走 `T(槽位)`（文案真源只有 texts 域；本文件 0 条内联中文）

塔内的走动**没有新造动词**：走房间用现成的『去 <房间名>』（`cmds_ast.go_to` 按 chain 邻居走），
读东西用现成的『触摸』/『读』。本文件只管四件塔才有的事：
  进塔（跨图那一步）· 上一层（一层走到头才能上）· 看这一层（副本地图）· 撤退（出塔）。
『调查』= 把**脚下这一间**能读的东西一次读出来（塔里的线索都在这类指令后面 —— 04 §九），
读到的照样进旧物谱（与「触摸」同一个口 `codex.note_read`，不另立一套规则）。
"""
from __future__ import annotations

from . import codex as CX
from .cmds_ast import (_data, _in_fight, _map_scene, _move, _name_of_node, _node_of, _p, _save,
                       _scene_line, _map_of, T, _pois_here)

__all__ = ["tower_enter", "tower_next", "tower_map", "tower_investigate", "tower_leave",
           "door_hint_lines", "foe_lines_here", "step_guard_line"]

#: 副本那张图的 id（内容侧取值里唯一一个是 ASCII 的 —— 别的都从数据来）
TOWER = "old_watchtower"


def _decl() -> dict:
    m = _map_of(TOWER)
    if not m:
        raise RuntimeError("%s：maps 域里没有 %s 这张图" % (__name__, TOWER))
    return m


def _floors() -> list:
    """三层 = 数据声明（`floors`）：[(层名, [节点 id…]), …]（顺序 = 走进去的顺序）。"""
    out = []
    for f in (_decl().get("floors") or []):
        rooms = [str(x) for x in (f.get("rooms") or [])]
        if rooms:
            out.append((str(f.get("name") or ""), rooms))
    if not out:
        raise RuntimeError("%s：%s 没声明 floors（上一层要用）" % (__name__, TOWER))
    return out


def _entrance() -> tuple:
    """进塔的那一格（跨图 · 数据声明）：(map_id, node_id)。缺了 / 不在图上 = 声明错。"""
    e = _decl().get("entrance") or {}
    loc, node = str(e.get("map") or ""), str(e.get("node") or "")
    if not loc or not node or loc not in (_data("maps") or {}) or not _node_of(loc, node):
        raise RuntimeError("%s：%s 的 entrance 没声明或不在图上（%r · %r）"
                           % (__name__, TOWER, loc, node))
    return loc, node


def _entry_node() -> str:
    """进塔之后站在哪一间 —— `roles.entry` 点的那一间（不写死 id）。"""
    m, want = _decl(), (_decl().get("roles") or {}).get("entry")
    for n in (m.get("nodes") or []):
        if want is not None and n.get("role") == want:
            return str(n.get("id"))
    raise RuntimeError("%s：%s 的 roles.entry 没落在任何一间房上（%r）"
                       % (__name__, TOWER, want))


def _inside(p) -> bool:
    return str(p.get("loc") or "") == TOWER


def door_hint_lines(p) -> list:
    """站在**塔门口那一格**（`maps.old_watchtower.entrance` —— 数据声明）时，给一句「能进去」。

    ★ fix5-nav（P2 体验 · 真试玩撞出来的）：第一阶段的主线去处就是这座塔，可那一屏正文只写着
      「门是铁的、关着」，`往哪走` 只有一条退路、`触摸` 回「这里没有什么可以上手的」
      ⇒ 玩家以为塔是背景板（报告原话：「我是靠翻『帮助』里的『进塔』才知道能进去的」）。
      「门在哪一格」照旧从数据现读（`entrance`），本函数**不写死任何节点 id**；
      人已经在塔里就不再说（那时由进塔那一屏的尾注说话）。
    """
    if _inside(p):
        return []
    if (str(p.get("loc") or ""), str(p.get("node") or "")) != _entrance():
        return []
    return [T("SYS_TOWER_DOOR")]


def foe_lines_here(p, uid, elite_row: bool = False) -> list:
    """『观察』「遇敌」那一栏 —— 塔内走 `SYS_LOOK_FOE_ROOM` / 野外与镇上走 `SYS_LOOK_FOE_ROW`。

    ★ fxa（P2 试玩 #2）：**塔内不刷精英**（`rules/elite.json` 的 `eligible_node_roles` 只列
      野外 / 深处 —— 塔门 / 塔内 / 塔顶 一律不刷），而『观察』那一栏原先**只有精英那一条路**
      ⇒ 塔里 16 间房一次都没印过「遇敌：」，玩家按『下一层』那句去「打它」，屏幕上却看不见
      目标（野外 9 站反而印得出来）。塔里这一栏与野外**同一个形状**（表头 + 名字行），
      差别只在名字行走哪个槽位：精英那行是 `COMBAT_ELITE_SPAWN`（塔里出不来），
      塔内这一行走 `SYS_LOOK_FOE_ROOM`。
    ★ fxexp（本波）：**野外 / 镇上那一档也接上读端** —— 槽位 `SYS_LOOK_FOE_ROW`
      原先零读端（那一行在 `texts` 里躺着，没人印）。两档**同一个口**
      （`cmds_battle.foe_here` —— 『攻击』真开的那一场也是它 ⇒ 「说的 = 打的」），
      差别只在槽位：野外那一档的名字行走 `SYS_LOOK_FOE_ROW`（`{list}` 形状）。
      `elite_row=True`（这一站今天有精英、那两行已经由观察那一支出过了）⇒ 空表（不重复）。
    不在这张图 / 这一间没有怪 / 这一带一只候选都挑不出来 ⇒ 空表（fail-closed：没东西可遇
    就不多说一行 —— 镇上与塔内空房就是这一档）。
    """
    if elite_row:
        return []
    from .cmds_battle import foe_here
    name = foe_here(p, uid)
    if not name:
        return []
    if _inside(p):
        return [T("SYS_LOOK_FOE"), T("SYS_LOOK_FOE_ROOM", name=name)]
    return [T("SYS_LOOK_FOE"), T("SYS_LOOK_FOE_ROW", list="『%s』" % name)]


def _room_foes(node) -> list:
    """这一间会出场的怪（`monsters.habitat` 里认这张图 + 这一间）—— 挡路的那个就是它们。"""
    out = []
    for mid, m in (_data("monsters") or {}).items():
        h = (m or {}).get("habitat") or {}
        if TOWER in [str(x) for x in (h.get("maps") or [])] \
                and str(node) in [str(x) for x in (h.get("nodes") or [])]:
            out.append(str(mid))
    return out


def _blocked_by(p, uid) -> str:
    """挡在路前、还没交过手的那些怪（显示名；空串 = 没有东西挡着 / 已经交过手）。

    ★ fix5-nav（P2 体验）：那一屏写着「楼梯口堵着一个人……从他身边过不去」，可『下一层』
      照旧放行 —— 话就白说了。真源 `22 §二·4` 写的是「可做 **战斗后上楼**」（§二·8 / §二·12
      同理：每一层最后一间都有一只挡路的）。
      ★ 本版的门 = **怪物谱上有它**（= 在那一间真动过手，`codex.note_kill` 那本账）。
        「非得打赢才算」要另开一个容器（今天只有 `flags.last_battle` 一场的账）—— 真源没给
        这一格，⇒ 不自己编（见本分支 `_notes.md §五`）。判据 probe_nav ⑦（正例 + 反证）。
    ★ fxa（P2 试玩 #2「说的和打的对不上」）：**点名的那只就是会开打的那只** ——
      名字走 `cmds_battle.foe_here`（与『攻击』那一次抽**同一个口**：副本里那一格由
      稳定标识定下来，见 `cmds_battle._encounter`）。原先这儿自己拼了一遍 `habitat` 名单
      （把这一间所有候选连起来）⇒ 说的一只、打的另一只。
      候选全抽不出来时（数据坏了）照名单点名 —— **宁可说得笼统，也不许把一扇门悄悄开着**。
    """
    foes = _room_foes(p["node"])
    if not foes:
        return ""
    book = ((p.get("books") or {}).get("monster") or {})
    if any(mid in book for mid in foes):
        return ""
    from .cmds_battle import foe_here                    # 本地 import：两条指令模块互相叫得到
    who = foe_here(p, uid)
    if who:
        return who
    ms = _data("monsters") or {}
    return " · ".join(str((ms.get(mid) or {}).get("name") or mid) for mid in foes)


def _floor_of(node):
    """这一间属于第几层 → (下标, 层名, [这一层的节点 id…])。不在任何一层 = 声明不全。"""
    for i, (name, rooms) in enumerate(_floors()):
        if str(node) in rooms:
            return i, name, rooms
    raise RuntimeError("%s：%s 这一间不在 floors 的任何一层里" % (__name__, node))


def _chain_index(node) -> int:
    """这一间在图上的序号（`maps.<图>.nodes` 的顺序 = 链的顺序；不在图上 ⇒ -1）。

    ★ 与 `floors` 用的是**同一个顺序**（探针 ② 逐条钉着）⇒ 「往下走」= 序号变大，
      不另造深度字段（与 `22 §一` 的总览表同序）。
    """
    ids = [str(n.get("id")) for n in (_decl().get("nodes") or [])]
    return ids.index(str(node)) if str(node) in ids else -1


def step_guard_line(p, uid, dest) -> str:
    """塔内**往外走**那一步 —— 被本层守卫拦下时给那一句（能走 / 不在塔里 ⇒ 空串）。

    ★ fxa（P2 试玩 #3「守卫能整条绕过」）：同一时刻『下一层』被挡着，`去 哨所（外）` 却
      直通二层 —— **房间级那条路没有闸**，玩家绕一步就把整层的守卫跳过去了（两条路给出
      互相矛盾的规则）。真源 `22 §二·4`「可做 **战斗后上楼**」/ §三①「一层通了才能上二层」
      说的是同一件事 ⇒ 本层尽头那一间**往上（顺链往前走）**都得先过手。
    往回走 / 原地不动**不拦**（那一步不通往上一层）。判据与『下一层』同一本账（`_blocked_by`
    ⇒ 怪物谱）；拦下时位置与历史一个字不动。
    """
    if not _inside(p):
        return ""
    cur = str(p.get("node") or "")
    _i, _fname, rooms = _floor_of(cur)      # 与『下一层』同一条 fail-closed（声明不全当场抛）
    if cur != rooms[-1]:
        return ""                            # 只有本层尽头那一间是楼梯口
    if _chain_index(dest) <= _chain_index(cur):
        return ""                            # 往回走 / 站在原地 —— 不拦
    who = _blocked_by(p, uid)
    return T("SYS_TOWER_BLOCKED", name=who) if who else ""


def _go(p, node, sink):
    """塔内走一格 —— 与别的移动共用 `_move`（prev / 去过 / 趟数一处不落）。"""
    return _move(p, TOWER, node, sink)


async def tower_enter(env, sink, uid, player):
    """`进塔`（别名 进副本）—— 在塔门口（`entrance` 那一格）推门进去。

    已经在塔里：按「脚下这一站」那一支说（K60 —— 别演出「又进了一次」）。
    不在塔门口：点名那一格在哪儿（fail-closed，不替玩家挪位置）。
    ★ fxa：**手上还有一场没打完就不让进门** —— 与 `往北` / `进镇` / `去` / `返回` 同一道闸
      （`cmds_ast._in_fight`）。不拦的话，野外那一场会跟着玩家进塔（P2 原文：出镇打「拾荒人」
      → 进塔 → 去 楼梯前 → `攻击` ⇒ 「第 3 手 …… 拾荒人 229/244」）—— 那也是副本里
      「说的那只 ≠ 打的那只」的来源之一。
    """
    _lock = _in_fight(env, uid)
    if _lock:
        yield _lock
        return
    p = _p(player)
    if _inside(p):
        yield T("SYS_MOVE_HERE", name=_name_of_node(TOWER, p["node"]))
        yield T("SYS_TOWER_HINT")
        return
    if (str(p.get("loc") or ""), str(p.get("node") or "")) != _entrance():
        yield T("SYS_TOWER_NOT_IN", name=_name_of_node(*_entrance()))
        return
    p = _go(p, _entry_node(), sink)
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_TOWER_ENTER")
    yield _map_scene(TOWER)                      # ★ 地图级 =「进门之后那一眼」（P-19 改写）
    yield T("SYS_TOWER_HINT")


async def tower_next(env, sink, uid, player):
    """`下一层` —— 站到**本层最后一间**再敲（「一层通了才能上二层」，22 §三①）。

    下一层的开头那一间就是新的一屏（照「先给一屏，再看细节」的次序）。
    塔顶再敲：没有上一层了 —— 说清楚（要出塔是『撤退』）。

    ★ 本波：**手上还留着一场没打完**（`instance.fighting()`）⇒ 与出镇 / 带间 / 返回同一档拦下
      （`SYS_MOVE_IN_FIGHT`，位置与历史一个字不动）—— 这一条也动位置（换一间房），
      跟『撤退』那个洞是同一个（试玩报告 §5④：闸原先只接在世界级移动上）。
    """
    _lock = _in_fight(env, uid)
    if _lock:
        yield _lock
        return
    p = _p(player)
    if not _inside(p):
        yield T("SYS_TOWER_NOT_IN", name=_name_of_node(*_entrance()))
        return
    fl = _floors()
    i, _fname, rooms = _floor_of(p["node"])
    if str(p["node"]) != rooms[-1]:
        yield T("SYS_TOWER_NEXT_FAR", room=_name_of_node(TOWER, rooms[-1]))
        return
    if i + 1 >= len(fl):
        yield T("SYS_TOWER_TOP_NONE")
        return
    # ★ fix5-nav：本层最后一间**还挡着东西** ⇒ 先动手（真源 `22 §二·4`「可做 战斗后上楼」）。
    #   原先『下一层』一律放行，而那一屏写着「从他身边过不去」—— 话白说了（P2 体验）。
    #   ★ fxa（P2 试玩 #3）：同一个门也罩着**房间级那条路**（`去 <上一层第一间>`）——
    #   见 `step_guard_line`（人在楼梯前也能 `去 哨所（外）` 直接绕过整层守卫）。
    _who = _blocked_by(p, uid)
    if _who:
        yield T("SYS_TOWER_BLOCKED", name=_who)
        return
    fname, dest = fl[i + 1][0], fl[i + 1][1][0]
    p = _go(p, dest, sink)
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_TOWER_UP", floor=fname, room=_name_of_node(TOWER, dest))
    yield _scene_line(TOWER, dest)


async def tower_map(env, sink, uid, player):
    """`副本地图` —— 看**这一层**（哪几间 · 哪间是脚下 · 哪几间走过 · 还剩几间）。"""
    p = _p(player)
    if not _inside(p):
        yield T("SYS_TOWER_NOT_IN", name=_name_of_node(*_entrance()))
        return
    fl = _floors()
    i, fname, rooms = _floor_of(p["node"])
    yield T("SYS_TOWER_MAP_HEAD", name=_decl().get("name") or TOWER, floor=fname,
            n=i + 1, all=len(fl))
    seen = ((p.get("foot") or {}).get("nodes") or {})          # ★ 走过没走过 = 足迹那一格（不另存一份）
    left = 0
    for r in rooms:
        nm = _name_of_node(TOWER, r)
        if r == p["node"]:
            yield "%s %s%s" % ("▸", nm, T("SYS_MAP_HERE"))
        elif ("%s:%s" % (TOWER, r)) in seen:
            yield "%s %s%s" % (" ", nm, T("SYS_TOWER_MAP_SEEN"))
        else:
            yield "%s %s" % (" ", nm)
            left += 1
    yield T("SYS_TOWER_MAP_TAIL", left=left) if left else T("SYS_TOWER_MAP_TAIL_DONE")


async def tower_investigate(env, sink, uid, player):
    """`调查` —— 查**这一间**（04 §九：塔里的线索多在这类指令后面）。

    这一间有可读的东西 ⇒ 一条条念出来（抬头 + 正文），读到的照样进旧物谱；
    没有 ⇒ 说没有（fail-closed，不随手塞一样给玩家 —— 同一规则见 `cmds_ast.read_thing`）。
    """
    p = _p(player)
    if not _inside(p):
        yield T("SYS_TOWER_NOT_IN", name=_name_of_node(*_entrance()))
        return
    # ★ P-31：列 poi 走唯一一口（门槛现看）—— 与「观察 / 去 / 触摸 / 读」同一处判定。
    #   塔内今天没有带 `condition` 的可读物 ⇒ 输出逐字不变（回归），但口径不再各写一份。
    here = [(pid, v, st_, ln_) for pid, v, st_, ln_ in _pois_here(TOWER, p["node"], p)
            if v.get("read_text")]
    if not here:
        yield T("SYS_TOWER_INV_NONE")
        return
    got = []
    for pid, v, st_, ln_ in here:
        if ln_:                                  # 门槛那句（判不了的点名 · 不成立的也在这一句里）
            yield ln_
        if st_ == "no":                          # 门槛判得出不成立 ⇒ 这一条不读
            continue
        yield T("SYS_READ_HEAD", name=v.get("name"))
        yield T(v["read_text"])
        if v.get("into_codex") and CX.note_read(p, pid):
            got.append(pid)
    if got:
        if player is not None:
            player.update(p)
        _save(env)
        for pid in got:
            yield T("SYS_CODEX_NEW", book=CX.label("relic"), name=CX.name_of("relic", pid))


async def tower_leave(env, sink, uid, player):
    """`撤退`（别名 撤）—— 出塔，回到进塔的那一格（`entrance`）。

    出塔 = 把那一次进塔**退回去**（prev 上那条对得上就弹掉）—— 免得紧接着的『返回』
    把玩家「返回」到他正站着的地方。★ 记一趟（`note_step`）的口径与 `go_back` 一致：
    这一条是真的走到塔下 —— 与进塔那一步（`_move` 记的是塔里那一间）分开算。
    ★ fxa：**手上还有一场没打完就不让出门** —— 与 `进塔` 及移动族同一道闸（`_in_fight`）；
      不然塔里那一场会跟着玩家出塔（人在塔门口接着打塔里那一只）。

    ★ 本波：**手上还留着一场没打完** ⇒ 与出镇 / 带间 / 返回**同一档**拦下（同一句槽位、
      位置与历史一个字不动）。原先这一闸只接在世界级移动上，副本出口没接 ——
      实测「打着一场就走出了塔，那一场跟着人跨图继续」（试玩报告 §5④：人在塔外
      「旧哨塔下」，照样在打塔顶的 Boss）。
    """
    _lock = _in_fight(env, uid)
    if _lock:
        yield _lock
        return
    p = _p(player)
    if not _inside(p):
        yield T("SYS_TOWER_NOT_IN", name=_name_of_node(*_entrance()))
        return
    loc, node = _entrance()
    p["loc"], p["node"] = loc, node
    # ★ fix5-nav（P4 BUG-5）：把**这一趟进塔**整段从历史上回滚 —— 原先只弹掉「顶上那条正好
    #   等于塔门口」的那一条：人只要在塔里走过房间，`prev` 顶上就是塔内那一间，条件不成立
    #   ⇒ 紧接着的一次『返回』把玩家**送回塔内那一间**（「撤退白做」）。
    #   现在把顶上一连串「塔内那一间」与「进塔那一步压的塔门口」一起弹掉
    #   ⇒ 『返回』回到进塔之前那一格（判据 probe_nav ⑥：正例 + 反证）。
    prev = list(p.get("prev") or [])
    while prev and (tuple(prev[-1]) == (loc, node) or str(prev[-1][0] or "") == TOWER):
        prev.pop()
    p["prev"] = prev
    CX.note_visit(p, loc, node)
    CX.note_step(p, loc, node)
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_TOWER_LEAVE", name=_name_of_node(loc, node))
    yield _scene_line(loc, node)
