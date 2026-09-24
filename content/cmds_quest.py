# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 第三组：公会与委托（B2-1）

契约同 cmds_ast：async generator，签名 (env, sink, uid, player)，参数从 env.text 解析。
落档：改了玩家档就必须 _save(env)（引擎不再每条消息整档回写）。
"""
from __future__ import annotations

from .cmds_ast import _data, _p, _save, _map_of, _name_of_node, T, exp_need
from .cmds_talk import _arg
from .cmds_ast import _npcs_here


def _mine(p):
    """进行中的委托（id 列表）。"""
    v = (p.get("flags") or {}).get("quests_active")
    return list(v) if isinstance(v, list) else []


def _done(p):
    v = (p.get("flags") or {}).get("quests_done")
    return list(v) if isinstance(v, list) else []


def _set(p, key, val):
    f = dict(p.get("flags") or {})
    f[key] = val
    p["flags"] = f


async def guild(env, sink, uid, player):
    p = _p(player)
    here = _npcs_here(p["loc"], p["node"])
    yield T("SYS_GUILD_HEAD")
    yield T("SYS_GUILD_DESK")
    yield T("SYS_GUILD_HOW")


async def board(env, sink, uid, player):
    p = _p(player)
    qs = _data("quests")
    done = _done(p)
    active = _mine(p)
    main = sorted([v for v in qs.values() if v["chain"] == "main"], key=lambda v: v["order"])
    nxt = None
    for v in main:
        qid = [k for k, x in qs.items() if x is v][0]
        if qid not in done:
            nxt = (qid, v)
            break
    yield T("SYS_BOARD_HEAD")
    if nxt is None:
        yield T("SYS_BOARD_NOMAIN")
    else:
        qid, v = nxt
        mark = T("SYS_BOARD_ACTIVE") if qid in active else ""
        yield T("SYS_BOARD_MAIN_ROW", order=v["order"], name=v["name"], mark=mark, level=v["min_level"])
        yield "  " + T("SYS_BOARD_TODO", objective=v["objective"])
        if qid in active:
            yield "  " + T("SYS_BOARD_DELIVER", order=v["order"])
        else:
            yield "  " + T("SYS_BOARD_NEXT", order=v["order"])
    side = [v for v in qs.values() if v["chain"] == "side" and v["giver"] in
            [k for k, _ in _npcs_here(p["loc"], p["node"])]]
    if side:
        yield T("SYS_BOARD_SIDE_HEAD")
        for v in side[:3]:
            yield "  · %s —— %s" % (v["name"], v["objective"])
    yield T("SYS_BOARD_HOW")


async def quest_accept(env, sink, uid, player):
    p = _p(player)
    want = _arg(env)
    qs = _data("quests")
    if not want:
        yield T("SYS_JOB_ASK")
        return
    v = None
    if want.isdigit():
        n = int(want)
        for k, x in qs.items():
            if x["chain"] == "main" and x["order"] == n:
                v = (k, x)
                break
    if v is None:
        for k, x in qs.items():
            if x["name"] == want:
                v = (k, x)
                break
    if v is None:
        yield T("SYS_JOB_NOSUCH", name=want)
        return
    k, x = v
    if k in _mine(p) or k in _done(p):
        yield T("SYS_JOB_ALREADY")
        return
    if p.get("level", 1) < x["min_level"]:
        yield T("SYS_JOB_LOWLEVEL", name=x["name"], need=x["min_level"], now=p.get("level"))
        yield T("SYS_JOB_MARTHA")
        return
    _set(p, "quests_active", _mine(p) + [k])
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_JOB_TAKEN", name=x["name"])
    yield "  " + T("SYS_JOB_TODO", objective=x["objective"])
    if x.get("insight"):
        yield "  " + T("SYS_JOB_INSIGHT", insight=x["insight"])
    yield T("SYS_JOB_GO")


async def quest_deliver(env, sink, uid, player):
    p = _p(player)
    want = _arg(env)
    qs = _data("quests")
    act = _mine(p)
    if not act:
        yield T("SYS_JOB_NONE")
        return
    k = None
    if want.isdigit():
        for kk in act:
            if qs.get(kk, {}).get("order") == int(want):
                k = kk
                break
    else:
        for kk in act:
            if qs.get(kk, {}).get("name") == want:
                k = kk
                break
    if k is None:
        yield T("SYS_JOB_NOT_MINE")
        for kk in act:
            yield "  · %s" % qs.get(kk, {}).get("name", kk)
        return
    x = qs[k]
    if not _obj_ok(x, p):
        yield T("SYS_JOB_NOT_DONE") + (x.get("progress_text") or x["objective"])
        return
    _set(p, "quests_active", [a for a in act if a != k])
    _set(p, "quests_done", _done(p) + [k])
    p["exp"] = p.get("exp", 0) + x["reward_exp"]
    p["gold"] = p.get("gold", 0) + x["reward_gold"]
    lv = p.get("level", 1)
    while p["exp"] >= exp_need(lv):                 # ★ 曲线只有 cmds_ast.exp_need 一个口
        p["exp"] -= exp_need(lv)
        lv += 1
    if lv != p.get("level"):
        p["level"] = lv
        leveled = True
    else:
        leveled = False
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_JOB_DELIVERED", name=x["name"])
    yield x.get("deliver_text") or ""
    yield T("SYS_JOB_REWARD", exp=x["reward_exp"], gold=x["reward_gold"])
    if leveled:
        yield T("SYS_JOB_LEVELUP", level=lv)
    if x.get("hook"):
        yield "（「%s」）" % x["hook"]


def _obj_ok(x, p):
    """第一版判据：主线看等级（到等级 = 做完了），支线看 flag。"""
    if x["chain"] == "main":
        return p.get("level", 1) >= x["min_level"]
    return bool((p.get("flags") or {}).get("side_" + x["name"]))


async def quest_abandon(env, sink, uid, player):
    p = _p(player)
    act = _mine(p)
    if not act:
        yield T("SYS_JOB_NO_ACTIVE")
        return
    want = _arg(env)
    qs = _data("quests")
    k = act[0] if not want else next((a for a in act if qs.get(a, {}).get("name") == want
                                      or qs.get(a, {}).get("order") == (int(want) if want.isdigit() else -1)), None)
    if not k:
        yield T("SYS_JOB_NO_ACTIVE_ONE")
        return
    _set(p, "quests_active", [a for a in act if a != k])
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_JOB_ABANDONED", name=qs.get(k, {}).get("name", k))


async def quest_mine(env, sink, uid, player):
    p = _p(player)
    qs = _data("quests")
    act, done = _mine(p), _done(p)
    if not act:
        yield T("SYS_MINE_NONE")
    else:
        yield T("SYS_MINE_HEAD", n=len(act))
        for k in act:
            x = qs.get(k, {})
            yield "· %s —— %s" % (x.get("name", k), x.get("objective", ""))
    if done:
        yield T("SYS_MINE_DONE", n=len(done))
    yield T("SYS_MINE_RANK")
