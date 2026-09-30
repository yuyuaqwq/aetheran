# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 第八组：镇上那几处（教堂 / 客栈 / 商队歇脚处 / 旧货铺）

这一批接的四条都**不需要新形状**：每一处都能从现成的域里回答「在哪儿 · 谁在 · 能做什么」。

| 指令 | 那处从哪儿来 | 数据 |
|---|---|---|
| `教堂` | 镇上那位带 `heal` 职能的人所在的那一站（`npcs.funcs`） | 节点名（`maps`）· 在场的人（`npcs` + 出场条件） |
| `客栈` | 与箱子同一站（`cmds_more.STASH_NODE` —— 一个节点只写一份） | 同上 |
| `商队` | 世界级（`scale_key == "world"`）且落在镇上的事件 | `events` 域那两条的 `text` 槽位 |
| `旧货` | 不指人：**收价 > 0** 的东西就是它肯收的（与『卖出』同一个口：`content/shop.py::sell_price_of`） | `items.price` + 装备收价那一格 · `codex` 旧物谱 |

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
★ 住店的**价钱**（P-55 下半 · 本批落的）：`content/rules/inn.json` 的 `fee` 那一格
  （`content/inn.py::fee()` 现读，**本文件不写数**）—— 真源 `05 §七` 把「住店」算作
  四个消耗口之一但没给数，取值理由与出处写在那份表里（乙档保守取：`initial_save` 头注
  那句「30 枚铜板 = 活三天的钱（住店 8 / 一顿饭 2）」）。教堂 / 篝火那两条免费口不受影响。
"""
from __future__ import annotations

from .cmds_ast import _data, _p, _save, T, _npcs_here, _name_of_node, hp_cap_or_line, TOWN
from .town import _func_node, town_gate
from .cmds_more import STASH_NODE
from . import calendar as CAL
from . import inn as INN
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
    ★ P-55 下半（本批）：住店**收钱** —— 价在 `content/inn.json`（`content/inn.py::fee()` 现读，
      本文件里一个数都没有）。三档各自照实说：
        · 本来就满血 ⇒ **不收**（`SYS_INN_FULL`：睡都没睡，不该扣钱）
        · 有伤但**钱不够** ⇒ 只回一句（复用现成槽位 `SYS_SHOP_POOR` —— 同一件事「钱不够」
          同一句话）且**档一个字不动**：不睡、不回血、不扣钱（fail-closed，与『购买』同形）
        · 真的睡下 ⇒ **先扣钱、再回血、一笔落档**（不会出现回了血却没扣钱的半截档），
          再把剩下的钱报一句（`SYS_MONEY_POUCH` —— 就是『钱袋』那一句）
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
    mx, fail = hp_cap_or_line(p)
    if fail:
        yield fail
    elif int(p.get("hp") or mx) >= mx:
        yield T("SYS_INN_FULL")
    else:
        fee = INN.fee()
        have = int(p.get("gold") or 0)
        if have < fee:
            yield T("SYS_SHOP_POOR", lack=fee - have)
        else:
            hp = int(p.get("hp") or mx)
            p["gold"] = have - fee
            p["hp"] = mx
            if player is not None:
                player.update(p)
            _save(env)
            yield T("SYS_INN_SLEEP")
            yield T("SYS_REST_HEAL", add=max(0, mx - hp), hp=mx, max=mx)
            yield T("SYS_MONEY_POUCH", gold=int(p.get("gold") or 0))
    yield T("SYS_INN_BOX")
    if rows:
        yield T("SYS_TALK_HOW", name=rows[0].get("name"))


async def caravan(env, sink, uid, player):
    """`商队` —— 歇脚处打听消息 · ★ fix7-gear 起**真到货**。

    三条都**现算**、都不手写：
      · 今天的动静 = 事件层里**世界级**（`scale_key == "world"`）且落在镇上的那几条 ——
        数据里就是「商队在路上 / 商队到了」那一对（口径 `29_世界事件 §五`）
      · 跟车来的人现在在哪一站 = `npcs` 里带 `condition.event` 的那几位，逐个核**此刻真的在场**
        （走 `_npcs_here` 一口：时辰 / 天气 / 事件三档一起看）—— 没到场就不列
      · ★ fix7-gear：**货** = 柜上挂着事件的那一家（口径表 `shelves.*.event`，今天 = 商队那家）。
        车没到 ⇒ 照实说**在等什么**（那件事等的是哪条委托，从 `events.period` 现取 —— 原先这一句
        只说「今天没有车来」，玩家看不到后续，p1 报告「体验-9」）；车到了 ⇒ 柜上那几件真列出来，
        `购买` 也真买得着（走 `content/shop.py` 那一个口，价与药铺同一个算法）。
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
    for key in SH.stationless():                   # ★ fix7-gear：挂在事件上的那一家
        ev = str(SH.shelf_rec(key).get("event") or "")
        if not ev:
            continue
        if not CAL.event_on(ev, p=p):
            who = SH.event_wait(key)
            if who:
                yield T("SYS_CARAVAN_WHY", name=who)
            continue
        rows = SH.goods(p, shelf=key)
        if rows:
            yield T("SYS_CARAVAN_GOODS")
            for g in rows:
                yield T("SYS_SHELF_ROW", icon=g["rec"].get("icon") or "",
                        name=g["rec"].get("name") or g["id"], gold=g["gold"],
                        level=SH.level_need(g["rec"]))
            continue
        for g in SH.goods_at(key, p):           # 车到了、可你还不到级：照实说（不静默）
                                                 # ★ 审计残余 #2：`p` 要带 —— 事件橱上不带档 = 猜事件状态（fail-closed 会当场抛）
            yield T("SYS_SHELF_LOCK", name=g["rec"].get("name") or g["id"],
                    level=SH.level_need(g["rec"]), now=int(p.get("level") or 0))
            break
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
    for g in SH.goods(p):
        rec = g["rec"]
        yield T("SYS_SHOP_ROW", icon=rec.get("icon") or "", name=rec.get("name") or g["id"],
                gold=g["gold"])
    # ★ 本波（P1 体验-14）：摊名（苦叶摊）与货架不是一回事 —— 柜上只有药，材料是自己采的
    #   （口径 = 真源 18_铺子买卖口径 §二①：货架 = `kind_key == tool`；卖材料那条走『卖出』）。
    #   不说这一句，玩家站在「苦叶摊」的柜前问「苦叶呢」，得到的是「柜上没有」。
    yield T("SYS_SHOP_HERB_NOTE")
    yield T("SYS_SHOP_TAIL", gold=int(p.get("gold") or 0))


async def junk_shop(env, sink, uid, player):
    """`旧货` —— 卖旧东西 · 看旧物谱。

    ★ 「它肯收什么」不另立一张存货表：**收价 > 0** 的就是铺子收的 —— 与『卖出』认的是
      **同一个口** `content/shop.py::sell_price_of`（材料 / 旧物 = `items.price`；
      ★ P3 BUG-4：装备按品阶 × 等级档现算 —— 原先装备一个价都没有，这一页也就永远
      不列它）。列出来的价 = 那一口 × 件数。
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
        price = SH.sell_price_of(rec)          # ★ P3 BUG-4：与『卖出』同一个口
        if price <= 0:
            continue
        n = int((p.get("bag") or {}).get(iid) or 0)
        rows.append((LT.label_of(iid), n, int(price) * n))   # ★ B4-20：重名的缀品阶
    if rows:
        yield T("SYS_JUNK_MINE")
        for name, n, gold in sorted(rows):
            yield T("SYS_JUNK_ROW", name=name, n=n, gold=gold)
    else:
        yield T("SYS_JUNK_NONE")
    yield T("SYS_JUNK_RELIC", n=CX.count(_shadow(p), "relic"))
    yield T("SYS_JUNK_HOW")
