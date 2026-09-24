# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 第四组：战斗（B2-2 第一版 —— 自动打完）

第一版范围有意收窄：先把「遇敌 → 打完 → 拿日志与结果」打通。
轮流制（输入窗口）+ 技能选择留 B2-2b（引擎已支持 `Battle.human_act` / `focus()`）。
"""
from __future__ import annotations

from .cmds_ast import _data, _p, _save, _map_of, _name_of_node, T
from .cmds_talk import _arg
from .cmds_codex import new_lines
from . import codex as CX
from . import combat as CB
from . import loot as LT


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
    seen = CX.note_kill(p, pick[0])            # ★ 打过一次就进谱（输了也算「见过」）
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
        # ★ 掉落（B2-3）：按怪身上的 dp_* 池抽（可复现：种子 = 玩家 uid + 怪 id）
        drops = []
        for pool_id in (m.get("drops") or []):
            drops.extend(LT.roll_pool(pool_id, level=lv,
                                     rnd=__import__("random").Random("%s:%s" % (uid, pick[0]))))
        if drops:
            LT.add_to_bag(p, drops)
        new = CX.note_items(p, [d["id"] for d in drops]) if drops else []
        if player is not None:
            player.update(p)
        _save(env)
        yield "铜板 +%d（现在 %d）｜ 生命 %d" % (gold, p["gold"], hp_after)
        if drops:
            it = LT.items()
            for d in drops:
                nm = it.get(d["id"], {}).get("name", d["id"])
                ic = it.get(d["id"], {}).get("icon", "·")
                yield "拾取：%s %s ×%s" % (ic, nm, d.get("n", 1))
                if d.get("story"):
                    yield "  （%s）" % d["story"]
            for line in new_lines(new):
                yield line
    else:
        if seen:
            yield T("SYS_CODEX_NEW", book=CX.label("monster"), name=CX.name_of("monster", pick[0]))
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
