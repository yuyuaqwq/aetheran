# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 第三组：公会与委托（B2-1）

契约同 cmds_ast：async generator，签名 (env, sink, uid, player)，参数从 env.text 解析。
落档：改了玩家档就必须 _save(env)（引擎不再每条消息整档回写）。
"""
from __future__ import annotations

from .cmds_ast import _data, _p, _save, _map_of, _name_of_node, T
from .cmds_talk import _arg, _npc_here


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
    here = _npc_here(p["loc"], p["node"])
    yield "【公会】门面比镇上任何一家都像样：一块木牌，牌上画着一把断了的剑和一只手。"
    yield "柜台在挂板墙那边。玛莎坐在后头。"
    yield "「『悬赏』看板 · 『接 <编号>』接活 · 『我的委托』看进度 · 『交 <编号>』交活」"


async def board(env, sink, uid, player):
    p = _p(player)
    qs = _data("quests")
    done = _done(p)
    active = _mine(p)
    main = sorted([v for v in qs.values() if v["kind"] == "主线"], key=lambda v: v["order"])
    nxt = None
    for v in main:
        qid = [k for k, x in qs.items() if x is v][0]
        if qid not in done:
            nxt = (qid, v)
            break
    yield "【挂板墙】板上钉着一叠单子。最新的一张还有墨味。"
    if nxt is None:
        yield "主线上没有新的了。板子最底下那一栏（黄纸）还是没人动过。"
    else:
        qid, v = nxt
        mark = "（进行中）" if qid in active else ""
        yield "主线 %d · %s%s  等级 %s+" % (v["order"], v["name"], mark, v["min_level"])
        yield "  要做什么：%s" % v["objective"]
        if qid in active:
            yield "  交付：『交 %d』" % v["order"]
        else:
            yield "  接下来：『接 %d』" % v["order"]
    side = [v for v in qs.values() if v["kind"] == "支线" and v["giver"] in
            [k for k, _ in _npc_here(p["loc"], p["node"])]]
    if side:
        yield "这人手上还有："
        for v in side[:3]:
            yield "  · %s —— %s" % (v["name"], v["objective"])
    yield "「『接 <编号>』接活 · 『我的委托』看进度」"


async def quest_accept(env, sink, uid, player):
    p = _p(player)
    want = _arg(env)
    qs = _data("quests")
    if not want:
        yield "接哪一条？打『悬赏』看板上有什么。"
        return
    v = None
    if want.isdigit():
        n = int(want)
        for k, x in qs.items():
            if x["kind"] == "主线" and x["order"] == n:
                v = (k, x)
                break
    if v is None:
        for k, x in qs.items():
            if x["name"] == want:
                v = (k, x)
                break
    if v is None:
        yield "板上没有「%s」这条。" % want
        return
    k, x = v
    if k in _mine(p) or k in _done(p):
        yield "这条你已经接了（或交过了）。"
        return
    if p.get("level", 1) < x["min_level"]:
        yield "「%s」要 %s 级。你现在 %s 级。" % (x["name"], x["min_level"], p.get("level"))
        yield "玛莎没抬头：「接不了就别接。」"
        return
    _set(p, "quests_active", _mine(p) + [k])
    if player is not None:
        player.update(p)
    _save(env)
    yield "接下：%s" % x["name"]
    yield "  要做什么：%s" % x["objective"]
    if x.get("insight"):
        yield "  （这件事背后：%s）" % x["insight"]
    yield "接活就该出门了 —— 『提示』会告诉你往哪走。"


async def quest_deliver(env, sink, uid, player):
    p = _p(player)
    want = _arg(env)
    qs = _data("quests")
    act = _mine(p)
    if not act:
        yield "你手上没有活。"
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
        yield "你手上没这条。进行中的有："
        for kk in act:
            yield "  · %s" % qs.get(kk, {}).get("name", kk)
        return
    x = qs[k]
    if not _obj_ok(x, p):
        yield "还没做完。" + (x.get("progress_text") or x["objective"])
        return
    _set(p, "quests_active", [a for a in act if a != k])
    _set(p, "quests_done", _done(p) + [k])
    p["exp"] = p.get("exp", 0) + x["reward_exp"]
    p["gold"] = p.get("gold", 0) + x["reward_gold"]
    lv = p.get("level", 1)
    while p["exp"] >= lv * lv * 40:
        p["exp"] -= lv * lv * 40
        lv += 1
    if lv != p.get("level"):
        p["level"] = lv
        leveled = True
    else:
        leveled = False
    if player is not None:
        player.update(p)
    _save(env)
    yield "交了：%s" % x["name"]
    yield x.get("deliver_text") or ""
    yield "经验 +%s ｜ 铜板 +%s" % (x["reward_exp"], x["reward_gold"])
    if leveled:
        yield "★ 你升到 %s 级了。" % lv
    if x.get("hook"):
        yield "（「%s」）" % x["hook"]


def _obj_ok(x, p):
    """第一版判据：主线看等级（到等级 = 做完了），支线看 flag。"""
    if x["kind"] == "主线":
        return p.get("level", 1) >= x["min_level"]
    return bool((p.get("flags") or {}).get("side_" + x["name"]))


async def quest_abandon(env, sink, uid, player):
    p = _p(player)
    act = _mine(p)
    if not act:
        yield "你没接活。"
        return
    want = _arg(env)
    qs = _data("quests")
    k = act[0] if not want else next((a for a in act if qs.get(a, {}).get("name") == want
                                      or qs.get(a, {}).get("order") == (int(want) if want.isdigit() else -1)), None)
    if not k:
        yield "没有这一条。"
        return
    _set(p, "quests_active", [a for a in act if a != k])
    if player is not None:
        player.update(p)
    _save(env)
    yield "🗑️ 放弃了：%s" % qs.get(k, {}).get("name", k)


async def quest_mine(env, sink, uid, player):
    p = _p(player)
    qs = _data("quests")
    act, done = _mine(p), _done(p)
    if not act:
        yield "手上没有活。打『悬赏』看看板上有什么。"
    else:
        yield "【进行中】%d 条" % len(act)
        for k in act:
            x = qs.get(k, {})
            yield "· %s —— %s" % (x.get("name", k), x.get("objective", ""))
    if done:
        yield "【已交】%d 条" % len(done)
    yield "【评级】见习（交 5 条升铜 · 15 条 + 打掉 1 个头目升银）"
