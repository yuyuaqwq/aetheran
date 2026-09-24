# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 第四组：战斗（B2-2 第一版 —— 自动打完）

第一版范围有意收窄：先把「遇敌 → 打完 → 拿日志与结果」打通。
轮流制（输入窗口）+ 技能选择留 B2-2b（引擎已支持 `Battle.human_act` / `focus()`）。
"""
from __future__ import annotations

from .cmds_ast import _data, _p, _save, _map_of, _name_of_node, T
from .cmds_talk import _arg
from . import combat as CB


def _encounter(p, uid, seed=None):
    """按当前位置与等级挑一个遭遇。"""
    ms = _data("monsters")
    return CB.pick_encounter(ms, p["loc"], p["node"], int(p.get("level", 1)), seed=seed)


def _fmt(logs, limit=12):
    """日志压到一屏（超了给省略）。"""
    out = list(logs)
    if len(out) > limit:
        out = out[:limit] + ["…（还有 %d 条 —— 『战斗日志』看全部）" % (len(logs) - limit)]
    return out


async def attack(env, sink, uid, player):
    """★ 第一版：遇敌 → 自动打完（把「攻击」当「打一场」）。"""
    p = _p(player)
    ms = _data("monsters")
    pick = _encounter(p, uid)
    if not pick:
        yield "这一带暂时没有遇到什么。"
        return
    yield "⚠️ 遭遇：%s" % ms[pick[0]].get("name", pick[0])
    res, logs, hp_after = CB.run_auto(p, pick, ms)
    for line in _fmt(logs):
        yield line
    yield "━" * 12
    if res == "victory":
        yield "✔ 打完了。"
        # 掉钱（第一版：按怪等级给，普通 3×lv / 精英 8×lv）
        m = ms[pick[0]]
        lv = int(m.get("lv", 1))
        gold = lv * (8 if m.get("role") == "精英" else (20 if m.get("role") in ("头目", "层主", "boss") else 3))
        p["gold"] = int(p.get("gold", 0)) + gold
        p["hp"] = hp_after
        if player is not None:
            player.update(p)
        _save(env)
        yield "铜板 +%d（现在 %d）｜ 生命 %d" % (gold, p["gold"], hp_after)
    else:
        yield "✖ 你倒下了。" if res == "defeat" else "（战斗结束：%s）" % res
        p["hp"] = max(1, hp_after)
        if player is not None:
            player.update(p)
        _save(env)
        yield "（野外血空回白烛堂 —— 掉当前等级经验的 10%，不掉装备）"


async def defend(env, sink, uid, player):
    yield "（第一版还没接轮流制 —— 先打『攻击』打完一场。）"


async def auto_battle(env, sink, uid, player):
    async for line in attack(env, sink, uid, player):
        yield line


async def battle_log(env, sink, uid, player):
    p = _p(player)
    last = (p.get("flags") or {}).get("last_battle")
    if not last:
        yield "还没有打过。"
        return
    yield "【上一场】%s" % last.get("enemy")
    for line in last.get("logs") or []:
        yield line


async def flee(env, sink, uid, player):
    yield "（第一版还没接轮流制。）"
