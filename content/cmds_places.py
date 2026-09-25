# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 第八组：镇上那几处（教堂 / 客栈 / 商队歇脚处 / 旧货铺）

这一批接的四条都**不需要新形状**：每一处都能从现成的域里回答「在哪儿 · 谁在 · 能做什么」。

| 指令 | 那处从哪儿来 | 数据 |
|---|---|---|
| `教堂` | 镇上那位带 `heal` 职能的人所在的那一站（`npcs.funcs`） | 节点名（`maps`）· 在场的人（`npcs` + 出场条件） |
| `客栈` | 与箱子同一站（`cmds_more.STASH_NODE` —— 一个节点只写一份） | 同上 |
| `商队` | 世界级（`scale_key == "world"`）且落在镇上的事件 | `events` 域那两条的 `text` 槽位 |
| `旧货` | 不指人：**域里有价**的东西就是它肯收的（与『卖出』同一口） | `items.price` · `codex` 旧物谱 |

四条纪律（同包内各处）
--------------------
  · 文案一律走 texts（本文件 0 条内联中文 —— probe_copy ① 逐文件数）
  · 机器键只用域里真出现过的那些：职能键 `funcs`（ASCII）· 事件档位 `scale_key` ·
    地图 / 节点 id —— 中文名一律从域里透传，代码里一个字都不写
  · 落档只经 `player.update(p)` + `_save(env)`；出档一律 `_p()`（默认档不当草稿纸，K57）
  · 要数字的地方（回血）走**唯一来源**（`hp_cap_or_line` → 职业面板）：档上还没择业
    ⇒ 出一行点名的 fail-closed 行、这一支不做（P-27；不拿写死的数垫）

★ 为什么「回满」不算新数值：死亡那一路（`cmds_battle._wake_in_chapel`）本来就是
  「回白烛堂 · 血回满」—— 镇上这两处照同一个语义落地（治疗 / 睡一觉 = 回到上限），
  不另定一条曲线。
★ 住店的**价钱**今天没有机器可读的一格（`apply.initial_save` 的注释里写着 8 铜板，
  真源表里没有字段）⇒ 本批不收费，价目记进 `_notes.md` 的待补清单，不在这儿硬写一个数。
"""
from __future__ import annotations

from .cmds_ast import _data, _p, _save, T, _npcs_here, _name_of_node, hp_cap_or_line, TOWN
from .town import _func_node, town_gate
from .cmds_more import STASH_NODE
from . import calendar as CAL
from . import shop as SH

#: ★ B4-12：镇子 id 收在基座 `cmds_ast`（`TOWN`）；「属于哪一站」（`_func_node`）与
#:   「在镇上 / 在公会」那一族守卫（`town_gate`）收在 `content/town.py` ——
#:   五个模块共用一份，本文件不再各写一遍（原先那两份搬过去了，import 即用）。


def _node_name(node: str) -> str:
    return str(_name_of_node(TOWN, node) or node)


def _roster(node: str, p) -> list:
    """这一站现在有谁 —— 走 `_npcs_here` 同一口（出场条件现看：时辰 / 天气 / 事件）。"""
    return [v for _k, v in _npcs_here(TOWN, node, p=p)]


def _roster_line(rows: list) -> str:
    return " · ".join("『%s』%s" % (v.get("name"), v.get("icon", "")) for v in rows)


def _heal_to_cap(p, env, player):
    """镇上那两处的「回满」—— 上限走唯一来源（职业面板）。

    返回 `(fail_line, add, max)`：`fail_line` = 档上还没择业时那一行点名的 fail-closed 行
    （那一支整段不做，P-27）；`add` = 这一下回了多少（0 = 本来就没伤，档没动）。
    """
    mx, line = hp_cap_or_line(p)
    if line:
        return (line, 0, 0)
    hp = int(p.get("hp") or mx)
    if hp >= mx:
        return ("", 0, mx)
    p["hp"] = mx
    if player is not None:
        player.update(p)
    _save(env)
    return ("", max(0, mx - hp), mx)


async def chapel(env, sink, uid, player):
    """`教堂` —— 治疗 · 问事。

    守卫（`guard_desc` = 在镇上）走**唯一执行面** `cmds_ast.town_gate`（B4-12）：不在镇上就明说；
    在镇上但没走到那一站就**指路**（那一站的名字从 `maps` 来）；站到了才治疗（回满，与「回白烛堂」同一个语义）。
    「问事」= 把在场的人递过去（『搭话 <名字>』）—— 说什么由 dialogues 域决定，本文件不替它说。
    """
    p = _p(player)
    node = _func_node("heal")
    line = town_gate(p, node)
    if line:
        yield line
        return
    rows = _roster(node, p)
    who = next((str((v.get("name") or "")) for v in rows
                if "heal" in (v.get("funcs") or [])), "")
    yield T("SYS_PLACE_HEAD", name=_node_name(node))
    if rows:
        yield T("SYS_LOOK_WHO", list=_roster_line(rows))
    got = _heal_to_cap(p, env, player)
    if got[0]:
        yield got[0]
    elif got[1] > 0:
        yield T("SYS_CHAPEL_HEAL", who=who)
        yield T("SYS_REST_HEAL", add=got[1], hp=got[2], max=got[2])
    else:
        yield T("SYS_CHAPEL_FULL", who=who)
    if who:
        yield T("SYS_TALK_HOW", name=who)


async def inn(env, sink, uid, player):
    """`客栈` —— 住店 · 打听。

    ★ 那一站 = **箱子那一站**（`cmds_more.STASH_NODE`：「客栈后院有个旧木箱」）——
      同一个节点不写第二份 id。站到了才住店（睡一觉 = 回到上限），并把箱子那两句递过去。
    """
    p = _p(player)
    node = STASH_NODE
    line = town_gate(p, node)
    if line:
        yield line
        return
    rows = _roster(node, p)
    yield T("SYS_PLACE_HEAD", name=_node_name(node))
    if rows:
        yield T("SYS_LOOK_WHO", list=_roster_line(rows))
    got = _heal_to_cap(p, env, player)
    if got[0]:
        yield got[0]
    elif got[1] > 0:
        yield T("SYS_INN_SLEEP")
        yield T("SYS_REST_HEAL", add=got[1], hp=got[2], max=got[2])
    else:
        yield T("SYS_INN_FULL")
    yield T("SYS_INN_BOX")
    if rows:
        yield T("SYS_TALK_HOW", name=rows[0].get("name"))


async def caravan(env, sink, uid, player):
    """`商队` —— 歇脚处打听消息。

    两条都**现算**、都不手写：
      · 今天的动静 = 事件层里**世界级**（`scale_key == "world"`）且落在镇上的那几条 ——
        数据里就是「商队在路上 / 商队到了」那一对（口径 `29_世界事件 §五`）
      · 跟车来的人现在在哪一站 = `npcs` 里带 `condition.event` 的那几位，逐个核**此刻真的在场**
        （走 `_npcs_here` 一口：时辰 / 天气 / 事件三档一起看）—— 没到场就不列
    """
    p = _p(player)
    line = town_gate(p)
    if line:
        yield line
        return
    yield T("SYS_CARAVAN_HEAD")
    st = CAL.state()
    news = [r for r in CAL.events_now(st, p)
            if str(r.get("scale_key")) == "world" and CAL.where_hit(r, TOWN)]
    for rec in news:
        t = str(rec.get("text") or "")
        if t:
            yield T(t)
    if not news:
        yield T("SYS_CARAVAN_QUIET")
    outsiders = []
    for node in ((_data("maps") or {}).get(TOWN) or {}).get("nodes") or []:
        nid = str(node.get("id") or "")
        for _k, v in _npcs_here(TOWN, nid, st, p):
            if not ((v.get("condition") or {}).get("event")):
                continue
            outsiders.append("%s（%s）" % (v.get("name"), _node_name(nid)))
    if outsiders:
        yield T("SYS_CARAVAN_WHO", list=" · ".join(outsiders))
        yield T("SYS_CARAVAN_HOW")


async def herbalist(env, sink, uid, player):
    """`药铺` —— 柜上有什么、怎么买（B4-15）。

    守卫（声明 `guard_desc` =「在镇上」）走唯一执行面 `town_gate`（**不核那一站** ——
    与旧货 / 商队同族）：在镇上哪一处都问得着价；真正买（『购买』）那一边才核站（口径 §三）。
    货架与价一律从 `content/shop.py` 来（域里的 `kind_key` + 基础价 × 品阶系数）——
    本文件不写价、不写 id。★ 这一页是**只读**的：敲『药铺』一个字都不落档。
    """
    p = _p(player)
    line = town_gate(p)
    if line:
        yield line
        return
    yield T("SYS_SHOP_HEAD", name=SH.station_name())
    rows = _roster(SH.station(), p)
    if rows:
        yield T("SYS_LOOK_WHO", list=_roster_line(rows))
    for g in SH.goods():
        rec = g["rec"]
        yield T("SYS_SHOP_ROW", icon=rec.get("icon") or "", name=rec.get("name") or g["id"],
                gold=g["gold"])
    yield T("SYS_SHOP_TAIL", gold=int(p.get("gold") or 0))


async def junk_shop(env, sink, uid, player):
    """`旧货` —— 卖旧东西 · 看旧物谱。

    ★ 「它肯收什么」不另立一张存货表：**域里有价**（`items.price`）的就是铺子收的 ——
      与『卖出』认的是同一个字段（指令那边也只认这一格）。列出来的价 = 那一格 × 件数。
    ★ 旧物谱那一行走**影子档**读（`cmds_quest._shadow`）：codex 的读口会把缺的格子补齐，
      在真档上调它等于「看一眼旧货铺」就往玩家档里塞空容器（K57 那族）。
    """
    p = _p(player)
    line = town_gate(p)
    if line:
        yield line
        return
    from . import codex as CX
    from . import loot as LT
    from .cmds_quest import _shadow

    yield T("SYS_JUNK_HEAD")
    rows = []
    for iid in sorted((p.get("bag") or {})):
        rec = LT.rec_of(iid)
        price = rec.get("price")
        if not isinstance(price, (int, float)) or isinstance(price, bool) or price <= 0:
            continue
        n = int((p.get("bag") or {}).get(iid) or 0)
        rows.append((str(rec.get("name") or iid), n, int(price) * n))
    if rows:
        yield T("SYS_JUNK_MINE")
        for name, n, gold in sorted(rows):
            yield T("SYS_JUNK_ROW", name=name, n=n, gold=gold)
    else:
        yield T("SYS_JUNK_NONE")
    yield T("SYS_JUNK_RELIC", n=CX.count(_shadow(p), "relic"))
    yield T("SYS_JUNK_HOW")
