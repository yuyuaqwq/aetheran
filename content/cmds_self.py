# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 第九组：公会那三件 + 名与榜 + 公告

这一批接的五条，各自只读**已有的账**，不新建容器、不新造数值：

| 指令 | 读的是 | 落档 |
|---|---|---|
| `登记` | 公会那一站（`npcs.funcs` 里的 `board`）· 档上有没有名字 | `flags.card = <游戏日>` |
| `评级` | 上面那一格 + `flags.quests_done`（已交条数）+ 图鉴怪物谱里 `role_key == "chief"` 的战绩 | 只读 |
| `改名` | 档上 `name` + `flags.renamed`（只改一次） | `name` / `flags.renamed` |
| `排行` | 本群存档（`content/persistence.all_players(group_id)` —— 包自己的存档半边） | 只读 |
| `公告` | `game.json`（名字 / 版本）+ `commands` 域的声明数 | 只读 |

四条纪律（同包内各处）
--------------------
  · 文案一律走 texts（本文件 0 条内联中文 —— probe_copy ① 逐文件数）
  · 数值一律现算：交了几条来自 `flags.quests_done` · 头目数按域的 `role_key` 数 ·
    已接指令数按声明表里真有 `bind` 的条数点 —— 一个都不手打（连「几级几经验」也是现读）
  · 读图鉴那两处走**影子档**（`cmds_quest._shadow`）：codex 的读口会把缺的格子补齐，
    在真档上调它等于「看一眼评级 / 旧货铺」就往玩家档里塞空容器（K57 那族）
  · 落档只经 `player.update(p)` + `_save(env)`；出档一律 `_p()`（默认档不当草稿纸）

★ 为什么不接 `升级证`（换证）：阶梯（交 5 条升铜 / 15 条 + 1 个头目升银）今天只活在
  一句文案里，机器可读的那份（档位名 / 门槛 / 换证条件）**一个域都没有** ——
  造它是新形状，记进 `_notes.md` 当遗留；`评级` 只说**现状与已交条数**，不替它许愿。
"""
from __future__ import annotations

import json
import os

from .cmds_ast import _data, _p, _save, T
from .town import _func_node, town_gate
from . import argv as AV
from . import calendar as CAL

#: 榜上最多列几条（一屏内 —— 呈现口径，不是数值；与 `cmds_quest.board` 的 `[:3]` 同族）
TOP = 10


def _flags(p) -> dict:
    """档上的 flags 拷一份再改 —— `_p()` 是浅拷贝，就地改会污染默认档（跨玩家串档）。"""
    f = dict(p.get("flags") or {})
    p["flags"] = f
    return f


def _day() -> int:
    """现在第几个游戏日（唯一出口 = `calendar`）。"""
    return int(CAL.state().get("game_day") or 0)


def has_card(p) -> bool:
    """档上那格 `flags.card`（`登记` 写的那一下）—— **唯一判法**。

    ★ B4-14：这一格原先有**两处读**（`评级` 读、`我的委托` 不读）⇒ 同一个档在同一刻
      一边回「你还没有证」、一边印「【评级】见习」。谁要问「这人办过证没有」都走这一个口；
      判据 = `probe_cmds ⑲`（真敲无证 / 有证两档 + 静态守卫：读那一格只许在本函数里）。
    ★ 只读、不建容器（K57：看一眼评级不该往玩家档里塞东西）。
    """
    return bool((p.get("flags") or {}).get("card"))




async def register(env, sink, uid, player):
    """`登记` —— 办见习证（守卫：在公会 · 未登记）。

    ★ 「问名字 → 发证」（`03 §一` 那张表）：档上还没名字就先把『改名』递过去 ——
      名字是**建号第三步**的产物，证上要写它，所以这一步不替玩家编一个。
    ★ 那一站 = 镇上带 `board` 职能的那位所在处（数据里就是挂板墙 / 玛莎）—— 不写死节点 id。
    """
    p = _p(player)
    line = town_gate(p, _func_node("board"))      # ★ B4-12：守卫走唯一执行面
    if line:
        yield line
        return
    if has_card(p):
        yield T("SYS_REG_HAS")
        return
    if not str(p.get("name") or "").strip():
        yield T("SYS_REG_ASKNAME")
        return
    _flags(p)["card"] = _day()
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_REG_DONE")


async def rank(env, sink, uid, player):
    """`评级` —— 见习 / 铜 / 银 的现状与进度（守卫：已登记）。

    ★ 阶梯那半句走**现成槽位** `SYS_MINE_RANK`（真源 `17_文案收口口径 §四` 就是它，
      `我的委托` 也读同一格 —— 不另抄一份口径）。
    ★ 进度两条都现算：交了几条 = `flags.quests_done` 的条数（与『交活』同一本账）；
      头目数 = 图鉴怪物谱里那些 `role_key == "chief"` 的战绩（机器键取自 `monsters` 域）。
    """
    p = _p(player)
    if not has_card(p):
        yield T("SYS_RANK_NOCARD")
        return
    from .cmds_quest import _done, _shadow
    from . import codex as CX

    s = _shadow(p)
    yield T("SYS_MINE_RANK")
    yield T("SYS_MINE_DONE", n=len(_done(s)))
    ms = _data("monsters") or {}
    n = 0
    for mid in CX.book("monster"):
        if int(CX.kills_of(s, mid) or 0) <= 0:
            continue
        if str((ms.get(mid) or {}).get("role_key") or "") == "chief":
            n += 1
    yield T("SYS_RANK_CHIEF", n=n)


async def rename(env, sink, uid, player):
    """`改名` —— 改一次名字（守卫：未用过）。

    ★ 名字的真源在档上（`name`）；这一格是**呈现口**到处都在读的那一格
      （`name_with_title` / 面板抬头 / 战斗 actor 的 `name`）。
    ★ 「一到八个字」那句规则走槽位（`03 §一` 的建号第三步）—— 长度不在这儿手打一个数：
      真源表里没有机器可读的上下限，代码不编一个（记进 `_notes.md` 待补）。
    """
    p = _p(player)
    want = AV.arg_of(env)
    f = _flags(p)
    if f.get("renamed"):
        yield T("SYS_RENAME_USED")
        return
    if not want:
        yield T("SYS_RENAME_ASK")
        return
    p["name"] = want
    f["renamed"] = _day()
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_RENAME_DONE", name=want)


async def ranking(env, sink, group_id, uid, player):
    """`排行` —— 本群榜（第一阶段只到本群为止）。

    ★ 榜 = **本群**存档里那些定下名字的人（`persistence.all_players(group_id)`）——
      包自己的存档半边就是这一格的来源，不新建容器、不另存一份快照。
    ★ 排序键 = 等级 · 经验（都是档上已有的账，现读现排；并列按名字）。
    ★ 自己那一行**一定在**：库里没有（探针 / 刚建号还没落库）就拿手上这份档补上 ——
      「榜上没你」是玩家最不能忍的那种榜。
    ★ 读不到库（存档半边没接上）⇒ 出一行点名的 fail-closed 行，不假装榜是空的。
    """
    p = _p(player)
    from . import persistence as PS

    try:
        rows = PS.all_players(str(group_id or ""))
    except Exception:                                          # noqa: BLE001 —— 读不到就说读不到
        yield T("SYS_RANKING_OFF")
        return
    board = []
    for r in rows:
        d = r.get("data") if isinstance(r, dict) else None
        d = d if isinstance(d, dict) else {}
        nm = str(d.get("name") or "").strip()
        if not nm:
            continue
        board.append((int(d.get("level") or 1), int(d.get("exp") or 0), nm))
    mine = str(p.get("name") or "").strip()
    if str(uid) not in {str(r.get("uid")) for r in rows}:
        board.append((int(p.get("level") or 1), int(p.get("exp") or 0),
                      mine or T("SYS_NAME_UNKNOWN")))
    board.sort(key=lambda x: (-x[0], -x[1], x[2]))
    yield T("SYS_RANKING_HEAD")
    for i, (_lv, _exp, nm) in enumerate(board[:TOP], 1):
        yield T("SYS_RANKING_ROW", i=i, name=nm, level=_lv, exp=_exp)
    yield T("SYS_RANKING_TAIL")


def _manifest() -> dict:
    """本包那一份说明（`game.json`）—— 名字 / 版本，别处不抄第二份。"""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "game.json")
    try:
        with open(path, encoding="utf-8") as f:
            v = json.load(f)
    except OSError:
        return {}
    return v if isinstance(v, dict) else {}


async def notice(env, sink, uid, player):
    """`公告` —— 服务器消息：这一版跑的是哪一份、接上了多少条。

    ★ 「服务器消息」在本包里 = **这一份包自己的状态**（名字 / 版本 / 已接指令数）——
      世界上的动静是另一条线（『异动』），这里只报包与指令面，不替事件层说话。
    ★ 已接条数**现点**：声明表里真有 `bind` 的那几条（与 `帮助` 列的是同一批口径）。
    """
    mf = _manifest()
    cmds = _data("commands") or {}
    n = len([1 for v in cmds.values() if isinstance(v, dict) and v.get("bind")])
    yield T("SYS_NOTICE_HEAD")
    yield T("SYS_NOTICE_PKG", name=mf.get("name") or "", ver=mf.get("version") or "")
    yield T("SYS_NOTICE_CMDS", n=n, total=len(cmds))
    yield T("SYS_NOTICE_TAIL")
