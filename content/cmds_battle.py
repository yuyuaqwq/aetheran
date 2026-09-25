# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 第四组：战斗（B2-2 第一版 —— 自动打完）

第一版范围有意收窄：先把「遇敌 → 打完 → 拿日志与结果」打通。
轮流制（输入窗口）+ 技能选择留 B2-2b（引擎已支持 `Battle.human_act` / `focus()`）。

★ B3-8 战斗收尾：输了要**真的落地**（回白烛堂 · 血回满 · 掉当前等级经验的 10% ·
  不掉装备 —— 口径 `00_总纲/03_主要玩法 §4.9`，曲线走 `cmds_ast.exp_need` 一个口）；
  倒地与掉经验的话走向 `texts` 槽位（`SYS_DEATH_WILD` / `SYS_DEATH_QUEST_LOSS`）；
  每场结束写 `flags.last_battle` —— 那是『战斗日志』**唯一**的来源（原先只有读端）。
★ B3-13 补上产出那一半：**胜利给经验**（= 同级升级需求的 1/40 · `cmds_ast.exp_of_kill`），升级判定走
  `cmds_ast.add_exp`（与交活同一个口）—— 原先打怪只给钱与掉落，升级只能靠交活。
"""
from __future__ import annotations

from .cmds_ast import (
    _data, _p, _save, _map_of, _name_of_node, T, CHAPEL, exp_need,
    exp_of_kill, add_exp)
from .cmds_talk import _arg, _pick_indexed
from .cmds_codex import new_lines
from . import calendar as CAL
from . import codex as CX
from . import combat as CB
from . import loot as LT


def _flags(p):
    """档上的 flags 拷一份再改 —— `_p()` 是浅拷贝，就地改会污染默认档（跨玩家串档）。"""
    f = dict(p.get("flags") or {})
    p["flags"] = f
    return f


def encounter_lines(monster, p):
    """怪身上的战内台词（B3-4 装备事件）—— 它**先开口**的那几句。

    条目的形状与 dialogues 域同（`need` 条件择优），判定也走**同一口**
    `cmds_talk._pick_indexed`（holding 那一支读的就是档上的背包）—— 不另写一套求值器。
    没有这一格 / 一条都不满足 ⇒ 空列表（fail-closed，不兜底）。
    """
    idx, text = _pick_indexed((monster or {}).get("encounter_lines"), p)
    return str(text).split("\n") if text else []


def _note_battle(p, enemy, logs, res):
    """把这一场记进 flags —— 『战斗日志』读的就是它（原先只在读端、没人写）。"""
    _flags(p)["last_battle"] = {"enemy": enemy, "result": res,
                                "logs": [str(x) for x in logs]}


def _wake_in_chapel(p):
    """★ 死亡落地（03 §4.9）：回白烛堂 · 血回满 · 掉当前等级经验的 10% · 不掉装备。

    「当前等级经验」= 该级升级所需经验（与升级判定同一个口 `exp_need`）；扣到 0 为止。
    返回掉掉的经验（给回话/探针用）。★ 醒来不是「走到」白烛堂 ⇒ 不记 `note_step`。
    """
    p["loc"], p["node"] = CHAPEL
    p["prev"] = []
    p["hp"] = int(p.get("hp_max") or 100)
    had = int(p.get("exp") or 0)
    lost = min(had, int(exp_need(int(p.get("level", 1) or 1)) * 0.1))
    p["exp"] = had - lost
    return lost


def _encounter(p, uid, seed=None):
    """按当前位置与等级挑一个遭遇。

    ★ B3-5：遇敌权重那一层挂上来了 —— 现在开场的事件给了 `encounter_mul` 就按它加权；
      **没给 / 没有事件 = 与改前逐字相同**（同一个种子挑出同一只）。
    """
    ms = _data("monsters")
    mul = CAL.encounter_mul(p=p)
    return CB.pick_encounter(ms, p["loc"], p["node"], int(p.get("level", 1)),
                             seed=seed, mul=mul or None)


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
    # ★ B3-4：怪身上挂着「先开口」的台词时，它先说话（数据驱动 —— 本文件不写文案）
    for line in encounter_lines(ms[pick[0]], p):
        yield line
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
        # ★ B3-13：打怪给经验（原先只有交活给 —— 「接活→出门→打怪→交活」这条循环里，
        #   打怪那一半是白打的）。公式走 `exp_of_kill`，升级走 `add_exp` —— 都只有一个口。
        exp_gain = exp_of_kill(lv)
        ups = add_exp(p, exp_gain)
        # ★ 掉落（B2-3）：按怪身上的 dp_* 池抽（可复现：种子 = 玩家 uid + 怪 id）
        drops = []
        for pool_id in (m.get("drops") or []):
            drops.extend(LT.roll_pool(pool_id, level=lv,
                                     rnd=__import__("random").Random("%s:%s" % (uid, pick[0]))))
        if drops:
            LT.add_to_bag(p, drops)
        new = CX.note_items(p, [d["id"] for d in drops]) if drops else []
        _note_battle(p, m.get("name", pick[0]), logs, res)
        if player is not None:
            player.update(p)
        _save(env)
        yield T("SYS_REWARD", exp=exp_gain, gold=gold)      # ★ 现成槽位（26_消息模板 §5）
        yield "铜板 %d ｜ 生命 %d ｜ 经验 %d" % (p["gold"], hp_after, p["exp"])
        if ups:
            yield T("SYS_JOB_LEVELUP", level=p["level"])
        if drops:
            for d in drops:
                rec = LT.rec_of(d["id"])     # ★ 未鉴定的 marker 名字在池上（唯一一口）
                nm = rec.get("name", d["id"])
                ic = rec.get("icon", "·")
                yield "拾取：%s %s ×%s" % (ic, nm, d.get("n", 1))
                if d.get("story"):
                    yield "  （%s）" % d["story"]
            for line in new_lines(new):
                yield line
    else:
        if seen:
            yield T("SYS_CODEX_NEW", book=CX.label("monster"), name=CX.name_of("monster", pick[0]))
        if res == "defeat":
            _wake_in_chapel(p)                      # ★ 真的回白烛堂（原先只说了这句话）
            yield T("SYS_DEATH_WILD")
            yield T("SYS_DEATH_QUEST_LOSS")
        else:
            yield "（战斗结束：%s）" % res
            p["hp"] = max(1, hp_after)
        _note_battle(p, ms[pick[0]].get("name", pick[0]), logs, res)
        if player is not None:
            player.update(p)
        _save(env)


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
