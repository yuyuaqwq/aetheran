# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 第四组：战斗（B2-2 第一版 —— 自动打完）
                                                                  ★ B3-23：战斗中那六条接上

第一版范围有意收窄：先把「遇敌 → 打完 → 拿日志与结果」打通。

★ B3-23（2026-09-25）：`04_指令总表 §五` 那张战斗表上**声明了、看得见、没有处理器**的六条
  真接上了 —— 打断 / 后撤 / 放技能 / 战斗中用物 / 集火 / 换武器（外加把「防御」那条桩句
  接成真动作）。口径一句话：

      本作的战斗是**伪即时 CTB**（绝对时刻制，`02_战斗机制 §〇·五`）——
      一条战斗指令 = **一场遭遇里的「你这一手」**：遇敌那一下先由快的对方行动
      （`schedule.advance` 推到你的决策点），然后**你这一手**做你说的事，接着这一场
      自动打完、照旧落账。所以：

      · 打断     清掉对方**出招窗口**里那一手（引擎 `interrupt` 动词）+ 把对方的到点时刻
                 推后「你这一手的耗时」—— 就是「把对方的行动推到更晚的时刻」。
      · 后撤     条件成立才跑得掉：**它那一下的到点时刻 − 现在 > 你这一手的耗时**（真算，
                 不许无脑逃跑）；跑不掉 ⇒ 这一手白花，照打。
      · 放技能   真放（守护四道门：不是本职业 / 认不出 / 等级没到 / 没学过）；mp 与冷却
                 由引擎自己判。
      · 用物     一场遭遇**每件最多 `item_uses_per_battle` 次**（`content/rules/battle_cmds.json`）
                 —— 带得多不等于用得多；用满之后那一手回落成普攻（不静默）。
      · 换武器   背包里另一件武器真换上（照 B3-19 的门槛判），**这一手花在换手上**。
      · 集火     组队概念（`04_指令总表 §五`「多人时指定」）—— 单人给明确回话，
                 不假装锁定了谁。

★ 这一批**没做**的（写在这儿免得下一轮当成已完，台账在 `_notes.md`）：
  · 真源 `03_风车镇_指令与回复 §二` 那四段式战斗回复（「◆ 野狗正在蓄力…还剩 N 刻 / ① 攻击
    ② 打断…」）要**一场战斗跨多条指令**的持久状态 —— 那是「轮流制」（组队那批，`_notes.md`
    留问）。本批是「一条指令 = 一场遭遇」，六条各自真生效、可观测、可判据。
  · 逃跑（flee）那条桩句没动：真源只写「可能失败」，**没给失败率** —— 不编数（见 `_notes.md`）。

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
    exp_of_kill, add_exp, hp_cap, hp_cap_or_line)
from .cmds_talk import _arg, _pick_indexed
from .cmds_codex import new_lines
from . import calendar as CAL
from . import codex as CX
from . import battle_acts as BA
from . import combat as CB
from . import cmds_gear as CG
from . import loot as LT
from . import affix as AFFIX        # ★ B3-24：精英词条（遭遇抽词条 / 名字与那一行走 texts 槽位）
from . import party as PT           # ★ B3-25：队伍（进战那一刻现算真实人数 —— 唯一来源）


def _party_now(env, p, uid):
    """★ B3-25：这一场的人数 —— **进战那一刻现算**（在队 + 同节点 + 活人，含自己）。

    ★ 三种答案分得清清楚楚（fail-closed 在两边都接得住）：
      · 我没队 ⇒ **1**（单人那条老路：与 B3-17 接线之前逐字相同，连存档都不用读）；
      · 我在队里 ⇒ 现算「此刻真站在一起的人」（`content/party.present_count`）；
      · 我在队里但**存档读不出来** ⇒ **None** = 「不知道几个人」——
        `content/combat.party_scale_of` 拿到 None 就**不缩放**（走设计值），
        绝不因为「不知道」而悄悄把团队内容（Boss）削弱。
    """
    try:
        rows = PT.rows_of(getattr(env, "group_id", ""))
    except PT.PartyError:
        rows = None
    return PT.present_count(p, uid, rows)


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
    ★ P-27：「血回满」的那个上限只有**一个来源**（职业面板，`cmds_ast.hp_cap`）——
      原先读档上写死的 100（面板 116 的骑士醒来只有 100）。
    """
    p["loc"], p["node"] = CHAPEL
    p["prev"] = []
    p["hp"] = hp_cap(p)
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


# ══════════════════════════════════════════════════════════════
# ★ B3-23：一场遭遇 · 你的第一手 · 落账（六条指令共用这一条路径）
# ══════════════════════════════════════════════════════════════
def _meet(p, uid):
    """遇敌那一步 —— 返回 `(pick, monsters)`；`pick` 空 = 这一带没有能打的东西。"""
    ms = _data("monsters")
def _meet(p, uid):
    """遇敌那一步 —— 返回 `(pick, monsters, affixes, 开场那行)`；`pick` 空 = 这一带没有能打的东西。

    ★ B3-24：这一格今天出精英 ⇒ 遭遇就是它（怪与词条都由 `affix.elite_of` 现算；
      「观察」读的是**同一个口**（同一 uid / 图 / 节点 / 游戏日 ⇒ 同一个种子）——
      所以观察那行是真预告，不是另抽一次。词条池里一条都没接线 ⇒ 回 `[]`（不出精英）。
    """
    ms = _data("monsters")
    pick = _encounter(p, uid)
    affixes = []
    _el = AFFIX.elite_of(ms, p["loc"], p["node"], uid,
                         CAL.state().get("game_day"), int(p.get("level", 1) or 1))
    if _el:
        pick, affixes = [_el[0]], list(_el[1])
    if not pick:
        return [], ms, [], ""
    if affixes:                                    # 精英：名字行 + 一句话效果（逐字走 texts 槽位）
        return pick, ms, affixes, AFFIX.elite_line(str(ms[pick[0]].get("name", pick[0])), affixes)
    return pick, ms, affixes, T("COMBAT_MEET", name=ms[pick[0]].get("name", pick[0]))


def _run_hand(p, pick, ms, affixes=(), hand=None, action=None, skill=None, party=None, uid=None):
    """打这一场：**先推到你的决策点**（快的对方先动），你出一手，再自动打完。

    返回 `(单场状态, 结果, 日志, 玩家战后血量)` —— 单场状态给「后撤」那种要先看时刻的
    条件判定用（`hand` 为空 = 纯自动那一支，与 B2-2 逐字相同）。
    ★ B3-24：这一场打几只由词条说话（群居那条让池子里多站两只，第二只半血）；
      没词条 ⇒ `([mid], [None])` = 与接线前逐字相同。
    ★ B3-25：`party` = 这一场的队伍人数（调用方**进战那一刻现算**；单人 = 1、不知道 = None）。
    ★ B3-28 ①：`uid` 透传给战斗——面板栈的键带上「人」那一维（不撞同职业同级的别人）。
    """
    _ids, _hm = AFFIX.spawn_plan(pick[0], list(affixes))
    b = CB.build(p, _ids, ms, party=party, affixes=list(affixes), hp_mults=_hm,
                 override=(hand.override if hand is not None else None), uid=uid)
    logs: list = []
    if hand is not None or action:
        from ext_combat.battle import schedule as SCH
        if hand is not None:
            # ★ 「用物」是**每一手**的立场（上限那一层由 battle_acts 的记账挡着）；
            #   其余几手都是「抢一手」⇒ 只在你这一手走非内置动作，后面自动普攻。
            caster = b.focus()
            if caster is not None and hand.kind == "item":
                caster["auto_act"] = {"act": {"type": "item", "skill": hand.item}}
        SCH.advance(b, logs)                       # 推到你的决策点（对方该动的先动）
        caster = b.focus()
        if b.result is None and caster is not None:
            if hand is not None:
                _sub, _ended, _who = b.human_act(str(hand.kind), hand.item, caster)   # 非内置动作
            else:
                _sub, _ended, _who = b.human_act(str(action), skill, caster)          # 引擎内置
            logs.extend(str(x) for x in (_sub or []))
    b.auto_run(logs)
    pa = (b.sides.get(CB.PLAYER_SIDE) or [{}])[0]
    return b, b.result, [str(x) for x in logs], int(pa.get("hp", 0))


async def _settle(env, p, uid, pick, ms, res, logs, hp_after, seen, player, affixes=()):
    """这一场的落账（攻击 / 六条战斗指令**共用**：钱 / 经验 / 掉落 / 死亡 / 战斗日志）。

    ★ B3-24：战斗日志里那格怪名用**精英显示名**（带 `† … †`）；没词条时 = 原样名。
    """
    # ★ B3-24：这一场记进日志时用的怪名（精英带 `† … †`；没词条 = 原样名）
    _ename = AFFIX.display_name(str(ms[pick[0]].get("name", pick[0])), list(affixes))
    yield "━" * 12
    if res == "victory":
        yield "✔ 打完了。"
        # 掉钱（第一版：按怪等级给，普通 3×lv / 精英 8×lv / 头目·层主·Boss 20×lv）
        # ★ B3-6b-2d-keys-2：分档比 ASCII `role_key`（原先比中文枚举「精英 / 头目 / 层主 / boss」）
        m = ms[pick[0]]
        lv = int(m.get("lv", 1))
        rk = m.get("role_key")
        gold = lv * (8 if rk == "elite" else (20 if rk in ("chief", "warden", "boss") else 3))
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
        # ★ B3-24：掉落按词条 PE 等比上调 + 富饶那条的「材料翻倍」（倍数在 rules/elite.json）
        drops = AFFIX.scale_drops(drops, affixes)
        if drops:
            LT.add_to_bag(p, drops)
        new = CX.note_items(p, [d["id"] for d in drops]) if drops else []
        _note_battle(p, _ename, logs, res)
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
        elif res == "fled":
            p["hp"] = max(1, hp_after)              # 跑掉了：血是打完当下的血，不掉经验
        else:
            yield "（战斗结束：%s）" % res
            p["hp"] = max(1, hp_after)
        _note_battle(p, _ename, logs, res)
        if player is not None:
            player.update(p)
        _save(env)


async def _open_and_hand(env, p, uid, player, head, hand=None, action=None, skill=None):
    """★ B3-23 的公共骨架：遇敌 → 报这一手 → 打 → 落账（六条指令都走它）。

    `head` 是这一手要说的那句话（已经渲染好的槽位行）；没遇敌 ⇒ 换成
    `COMBAT_NEED_FOE` 那一句，**什么都不动**（fail-closed，不白打一场）。
    """
    pick, ms, affixes, _mline = _meet(p, uid)
    if not pick:
        yield T("COMBAT_NEED_FOE")
        return
    yield _mline
    for line in encounter_lines(ms[pick[0]], p):
        yield line
    if head:
        yield head
    seen = CX.note_kill(p, pick[0])
    _b, res, logs, hp_after = _run_hand(p, pick, ms, affixes=affixes, hand=hand,
                                        action=action, skill=skill,
                                        party=_party_now(env, p, uid), uid=uid)
    for line in _fmt(logs):
        yield line
    async for line in _settle(env, p, uid, pick, ms, res, logs, hp_after, seen, player,
                                  affixes=affixes):
        yield line


# ══════════════════════════════════════════════════════════════
# 一、攻击（自动打完那一条 —— B2-2 起的老路，一个字没改）
# ══════════════════════════════════════════════════════════════
async def attack(env, sink, uid, player):
    """★ 第一版：遇敌 → 自动打完（把「攻击」当「打一场」）。"""
    p = _p(player)
    # ★ P-27：打一场要靠面板（上限 / 属性 / 技能都从它来）。档上还没有职业（建号第二步没走完）
    #   ⇒ **不出假数**：出一行点名的 fail-closed 行，这一场不开（`combat.player_actor` 那条路
    #   同样是 fail-closed —— 职业不兜底）。
    _mx, _line = hp_cap_or_line(p)
    if _line:
        yield _line
        return
    # ★ B3-26：这一敲要不要走「场」（多人轮流制）那道 —— 单人 / 没场 ⇒ False，
    #   接着往下走**今天这条老路**（一个字不变；判据见 `scripts/probe_instance.py` ⑤）。
    from . import instance as INST
    if INST.route_needed(env, uid):
        async for line in INST.take_turn(env, p, uid, player, action="attack"):
            yield line
        return
    pick, ms, affixes, _mline = _meet(p, uid)
    if not pick:
        yield T("COMBAT_NONE")
        return
    yield _mline
    # ★ B3-4：怪身上挂着「先开口」的台词时，它先说话（数据驱动 —— 本文件不写文案）
    for line in encounter_lines(ms[pick[0]], p):
        yield line
    seen = CX.note_kill(p, pick[0])            # ★ 打过一次就进谱（输了也算「见过」）
    # ★ B3-25：人数 = **进战那一刻现算**（在队 + 同节点 + 活人，含自己）——单人 = 1，
    #   与 B3-17 接线之前逐字相同；它只对「团队内容」那几只怪生效（Boss 的面板按人数缩放）。
    _ids, _hm = AFFIX.spawn_plan(pick[0], list(affixes))
    res, logs, hp_after = CB.run_auto(p, _ids, ms, party=_party_now(env, p, uid),
                                      affixes=list(affixes), hp_mults=_hm, uid=uid)
    for line in _fmt(logs):
        yield line
    async for line in _settle(env, p, uid, pick, ms, res, logs, hp_after, seen, player,
                                  affixes=affixes):
        yield line


# ══════════════════════════════════════════════════════════════
# 二、打断（B3-23）
# ══════════════════════════════════════════════════════════════
async def interrupt(env, sink, uid, player):
    """`打断` —— 你这一手掐对方的起手（真源 `04_指令总表 §五`「打断动作（名称随职业）」）。

    效果两层（都在 `content/battle_acts.py`，引擎零改动）：
      ① 对方正在**出招窗口** ⇒ 清掉它那一手（引擎 `interrupt` 动词，含霸体判定与事件）；
      ② 无论断没断成，把对方下一次行动的**到点时刻推后**「你这一手的耗时」。
    「本门那个动作叫什么」取自 `skills` 域（`mech == "interrupt"` 且属于本职业）——
    今天只有刺客挂着（断势）；其余五门走通用那一句，**不在这儿编名字**（`_notes.md` 待补）。
    ★ 与 `防御` / `放技能` 不同：打断这一手**不出伤**（它是控制那一类）—— 这一场接着自动打完。
    """
    p = _p(player)
    _mx, _line = hp_cap_or_line(p)
    if _line:
        yield _line
        return
    act = BA.interrupt_action_of(p)
    head = T("COMBAT_INT_HEAD", skill=act.get("name", "")) if act else T("COMBAT_INT_PLAIN")
    hand = BA.Hand("interrupt", p=p)
    # ★ B3-26：在场里 ⇒ 走「场」那道（打断要「花掉你这一手」，得先轮到你）
    from . import instance as INST
    if INST.route_needed(env, uid):
        async for line in INST.take_turn(env, p, uid, player, head=head, hand=hand):
            yield line
        return
    async for line in _open_and_hand(env, p, uid, player, head, hand=hand):
        yield line


# ══════════════════════════════════════════════════════════════
# 三、后撤（B3-23）
# ══════════════════════════════════════════════════════════════
async def retreat(env, sink, uid, player):
    """`后撤` —— 条件成立才退得开（`04_指令总表 §五`「换位」）。

    **「能跑掉」看的是对方**这一刻在不在出招**（引擎现成状态 `actor["charging"]`，不编数）**：
    它**没押着手**（这一拍它没在出招）⇒ 你这一步退得开；它**正押着一手**（前摇里，那一下正朝你
    落下来）⇒ 退不开（那一手白花、这一场照打）—— 不许无脑逃跑：挨着的那一下还没落地，
    你就是退不开。真源 `03_风车镇_指令与回复 §二` 那四段式把「后撤」摆在「对方正在做什么」
    同一屏里给玩家看，判的就是这个。真源 04 §五 只写了「换位」（成/不成没写）⇒ 见 `_notes.md`。

    退得掉 ⇒ 这一场**不打**（没有掉落 / 没有经验 —— 这就是代价），只写 `last_battle` 一条
    `fled` 记录给『战斗日志』看；退不掉 ⇒ 走完整场（与 `攻击` 同一条收尾）。
    """
    p = _p(player)
    _mx, _line = hp_cap_or_line(p)
    if _line:
        yield _line
        return
    pick, ms, affixes, _mline = _meet(p, uid)
    if not pick:
        yield T("COMBAT_NEED_FOE")
        return
    yield _mline
    for line in encounter_lines(ms[pick[0]], p):
        yield line
    yield T("COMBAT_RETREAT_HEAD")
    from ext_combat.battle import schedule as SCH
    from ext_combat.battle.actors import actor_alive
    hand = BA.Hand("retreat", p=p)
    _ids, _hm = AFFIX.spawn_plan(pick[0], list(affixes))
    b = CB.build(p, _ids, ms, party=_party_now(env, p, uid), affixes=list(affixes),
                 hp_mults=_hm, override=hand.override, uid=uid)
    logs: list = []
    SCH.advance(b, logs)                       # 推到你的决策点（快的对方该动的先动）
    caster = b.focus()
    now = float(getattr(b, "_now", 0) or 0)
    busy = None                                # 对方押着的那一手（前摇里 = 它的手被占着）
    for a in (b.sides.get(CB.ENEMY_SIDE) or []):
        if actor_alive(a) and SCH.pending_left(a, now) > 0:
            busy = a
            break
    if b.result is None and busy is None:
        # ── 能跑掉：这一拍它没在出招 ⇒ 这一场不打（`fled`），血照当下的血
        b.result = "fled"
        pa = (b.sides.get(CB.PLAYER_SIDE) or [{}])[0]
        p["hp"] = max(1, int(pa.get("hp", 0) or p.get("hp") or 1))
        for line in _fmt(logs):
            yield line
        yield T("COMBAT_RETREAT_OK")
        _note_battle(p, ms[pick[0]].get("name", pick[0]), logs, "fled")
        if player is not None:
            player.update(p)
        _save(env)
        return
    # ── 退不开：这一手白花（走 move 那一档耗时），这一场照打
    hand.lines = [T("COMBAT_RETREAT_BLOCK", name=ms[pick[0]].get("name", pick[0]))]
    if caster is not None and b.result is None:
        _sub, _ended, _who = b.human_act("retreat", None, caster)
        logs.extend(str(x) for x in (_sub or []))
    seen = CX.note_kill(p, pick[0])
    b.auto_run(logs)
    pa = (b.sides.get(CB.PLAYER_SIDE) or [{}])[0]
    for line in _fmt([str(x) for x in logs]):
        yield line
    async for line in _settle(env, p, uid, pick, ms, b.result, [str(x) for x in logs],
                              int(pa.get("hp", 0)), seen, player):
        yield line


# ══════════════════════════════════════════════════════════════
# 四、放技能（B3-23）
# ══════════════════════════════════════════════════════════════
async def skill_cast(env, sink, uid, player):
    """`技能 <名>`（别名 技 / 放）—— 你这一手真放出来（`04_指令总表 §五`「放技能」）。

    四道门都在**指令这一层**先判（不与引擎那道重复判语义，只判「这一手有没有资格」）：
      ① 没定职业 ⇒ `SYS_SKILL_NOCLS`  ② 认不出 / 不是本职业 / 没学过 ⇒ `COMBAT_SKILL_BAD`
      ③ 解锁等级没到 ⇒ `SYS_SKILL_TOO_LOW`
    过了就交给引擎那条技能路（mp / 冷却 / 伤害 / 治疗 / 增益都是它自己的事）。

    ★ B4-1 第五道门：**被动不是能"放"的**（`kind_key == "passive"` ⇒ `COMBAT_SKILL_BAD`）。
      被动开战时由事件总线挂上（`content/mech.py` 的 `route=trigger`），放进球场只会白费一次
      行动。判据看 ASCII 机器键，不看中文类别名（K48/K51 同族）。
    """
    from .cmds_skill import _by_name, _skills, known_ids
    p = _p(player)
    cls = str(p.get("cls") or "")
    if not cls:
        yield T("SYS_SKILL_NOCLS")                 # 先报「技能跟着职业走」，比面板那句更贴身
        return
    _mx, _line = hp_cap_or_line(p)
    if _line:
        yield _line
        return
    want = _arg(env)
    if not want:
        # ★ B4-13：裸「技」/「放」走到这儿（裸「技能」= 技能表那条）—— 照实说「放哪一手」
        yield T("SYS_SKILL_CAST_ASK")
        return
    sid, rec = _by_name(_skills(), want)
    if not sid:
        yield T("COMBAT_SKILL_BAD", name=want)
        return
    if rec.get("kind_key") == "passive":
        yield T("COMBAT_SKILL_BAD", name=rec.get("name", sid))
        return
    owner = str(rec.get("owner_class") or "")
    if (owner and owner != cls) or sid not in known_ids(p):
        yield T("COMBAT_SKILL_BAD", name=rec.get("name", sid))
        return
    lv = int(rec.get("lv") or 1)
    if lv > int(p.get("level") or 1):
        yield T("SYS_SKILL_TOO_LOW", name=rec.get("name", sid), lv=lv,
                gap=lv - int(p.get("level") or 1))
        return
    _head = T("COMBAT_SKILL_HEAD", name=rec.get("name", sid))
    # ★ B3-26：在场里 ⇒ 走「场」那道（放技能要「花掉你这一手」，得先轮到你）
    from . import instance as INST
    if INST.route_needed(env, uid):
        async for line in INST.take_turn(env, p, uid, player, head=_head,
                                         action="skill", skill=sid):
            yield line
        return
    async for line in _open_and_hand(env, p, uid, player, _head, action="skill", skill=sid):
        yield line


# ══════════════════════════════════════════════════════════════
# 五、战斗中用物（B3-23）
# ══════════════════════════════════════════════════════════════
async def battle_item(env, sink, uid, player):
    """`使用 <药>`（别名 用 / 吃）—— **战斗中**这一手用药（`04_指令总表 §五`「药与道具」）。

    ★ 约束（本批新落的口径）：一场遭遇**每件最多 `item_uses_per_battle` 次**
      （`content/rules/battle_cmds.json`）—— 背包里带 20 瓶也只能一场喝 1 瓶；用满之后
      那一手**回落成普攻**（出 `COMBAT_ITEM_CAP` 说明为什么，不静默）。
    ★ 只认**回血**那一类（口径见 `content/battle_acts.py` 抬头：面板在开战时固化，
      食物/增益类落不到这一场 ⇒ fail-closed 出一句「用不了」，不假冒）。
    ★ 路由：`使用` 这个词的第一命中是**可见的** `item_use`（`probe_cmds` ③ 钉着）；
      本条（`battle_item`，声明里 `visible: false`）是它的**战斗中那一半** ——
      本批把这一半真接上（真调真跑），可达性留给「有真战斗中状态」的那批，见 `_notes.md`。
    """
    p = _p(player)
    _mx, _line = hp_cap_or_line(p)
    if _line:
        yield _line
        return
    want = _arg(env)
    iid, rec = CG._in_bag(p, want)
    if not iid:
        yield T("COMBAT_ITEM_BAD", name=want)
        return
    hand = BA.Hand("item", p=p, item=iid)
    _head = T("COMBAT_ITEM_HEAD", name=rec.get("name", iid))
    # ★ B3-26：在场里 ⇒ 走「场」那道（用物要「花掉你这一手」，得先轮到你）
    from . import instance as INST
    if INST.route_needed(env, uid):
        async for line in INST.take_turn(env, p, uid, player, head=_head, hand=hand):
            yield line
        return
    async for line in _open_and_hand(env, p, uid, player, _head, hand=hand):
        yield line


# ══════════════════════════════════════════════════════════════
# 六、集火（B3-23）
# ══════════════════════════════════════════════════════════════
async def focus_fire(env, sink, uid, player):
    """`集火 <目标>` —— 多人时指定目标（`04_指令总表 §五`）。

    ★ B4-18：三档，按**此刻真在不在队里**分（人数走现成的唯一口径 `_party_now`，
      与战斗那边同一个来源 —— 不另开一份判断）：

      · 单人（1）⇒ 点了名的那只在 `monsters` 域里认得出来就说认得出来（不假装锁上了谁），
        认不出的名字照实说认不出。**不动档、不开战斗。**
      · 有队（≥2）⇒ 「全队打同一个目标」那一层（`17_组队与策略配合 §三·8`）**还没落地**
        ⇒ 照实说（`COMBAT_FOCUS_PARTY`），不假装已经锁上了谁。
      · 队在、但存档读不出来（`None` = 不知道几个人）⇒ 同「有队」那一句
        （fail-closed：不拿单人那两句去说一支读不出来的队）。

    ★ 原先「组队还没接线」那句自我说明（含 texts 里 `COMBAT_FOCUS_SOLO` 的句尾）在
      B3-25 组队落地那天就成了假话（`_notes.md` §一·1.2 庚 已点「真源那一行待改」）—— 本批改掉。
    """
    p = _p(player)
    want = _arg(env)
    if _party_now(env, p, uid) != 1:
        yield T("COMBAT_FOCUS_PARTY")
        return
    ms = _data("monsters")
    hit = None
    for mid, m in ms.items():
        if str(mid).startswith("_"):
            continue
        nm = str(m.get("name") or "")
        if want and (want == mid or (nm and (want == nm or (len(want) >= 2 and want in nm)))):
            hit = (mid, m)
            break
    if hit:
        yield T("COMBAT_FOCUS_NAMED", name=hit[1].get("name", hit[0]))
        return
    yield T("COMBAT_FOCUS_SOLO")


# ══════════════════════════════════════════════════════════════
# 七、换武器（B3-23）
# ══════════════════════════════════════════════════════════════
async def swap_weapon(env, sink, uid, player):
    """`换武器` —— 换主手那一件（`04_指令总表 §五`「吃一次行动」）。

    ★ 声明里这一条**没有参数**（`^换武器$`，真源 04 §五 的写法就是这三个字）⇒ 换哪一件由
      数据自己说话：背包里 `slot == "weapon"` 的按 id 序，取**第一件不是手上那件**的换上
      （手上空着就取第一件）。要精准点名哪一件 ⇒ 走现成的『装备 <名字>』（同一条口径）。
      候选不止一件时另出一行把它们列出来（只提示，不改方向）。
    三件一起办（口径都借现成的口，本文件不写数值）：
      · 门槛：照 B3-19 判（不够 ⇒ `SYS_GEAR_REQ`，**档上不动**）；
      · 换手：换下的那件回背包（与 `装备` 同口径，走 `cmds_gear` 那几个小件）。
    ★ 「吃一次行动」只有在**打起来的时候**才算数 ⇒ 这一带能遇敌就把这一手花在换手上
      （遇敌那一屏 + `COMBAT_SWAP_OK` + 这一场照打）；村镇 / 没挂怪的图 ⇒ 只换手
      （回现成的 `SYS_GEAR_EQUIP_OK`），不硬开一场。
    """
    p = _p(player)
    eq0 = dict(p.get("equipped") or {})
    mine = sorted(k for k in (p.get("bag") or {})
                  if str((CG._item(k) or {}).get("slot") or "") == "weapon")
    cand = [k for k in mine if k != eq0.get("weapon")]
    if not cand:
        yield T("COMBAT_SWAP_NONE")
        return
    iid = cand[0]
    rec = CG._item(iid)
    short = CG.unmet_req(p, iid)
    if short:
        yield T("SYS_GEAR_REQ", **short)
        return
    old = eq0.get("weapon")
    CG._take(p, iid, 1)
    if old:
        CG._to_bag(p, old, 1)
    eq0["weapon"] = iid
    p["equipped"] = eq0
    p = _p(p)                                  # ★ 上限/现血按新的 equipped 重新派生（P-27）
    ok = T("COMBAT_SWAP_OK", icon=rec.get("icon", ""), name=rec.get("name", iid),
           kind=rec.get("kind", ""))
    pick, ms, affixes, _mline = _meet(p, uid)
    if not pick:
        # 这一带没有能打的东西 ⇒ 手换上了，没处花（不硬开一场）
        if player is not None:
            player.update(p)
        _save(env)
        yield T("SYS_GEAR_EQUIP_OK", icon=rec.get("icon", ""), name=rec.get("name", iid),
                kind=rec.get("kind", ""))
        return
    if len(cand) > 1:                          # 还有别的能换（只提示 —— 换哪一件由数据说话）
        yield T("COMBAT_SWAP_ASK", list=" · ".join(
            "『%s』" % (CG._item(k) or {}).get("name", k) for k in cand[1:]))
    hand = BA.Hand("swap", p=p, lines=[ok])
    yield _mline
    for line in encounter_lines(ms[pick[0]], p):
        yield line
    # ★ 「你换上了…」由**这一手落地那一刻**说出来（`hand.lines` 走 B 段那条路）——
    #   不在抬头处重复一遍（换手本身就是这一手，报两次是两句话一件事）。
    seen = CX.note_kill(p, pick[0])
    _b, res, logs, hp_after = _run_hand(p, pick, ms, affixes=affixes, hand=hand, uid=uid)
    for line in _fmt(logs):
        yield line
    async for line in _settle(env, p, uid, pick, ms, res, logs, hp_after, seen, player,
                                  affixes=affixes):
        yield line


# ══════════════════════════════════════════════════════════════
# 八、防御（B3-23 顺手接上那条桩句 —— 引擎内置那一档，口径「少挨一半，后摇短」）
# ══════════════════════════════════════════════════════════════
async def defend(env, sink, uid, player):
    """`防御`（别名 防 / 守）—— 你这一手摆防御姿态（引擎内置动作，本文件不写任何机制）。

    ★ 原先是一句桩（「第一版还没接轮流制 —— 先打『攻击』打完一场」）；本批接成真动作。
      引擎的 `defend` 给 `defending=True`（承伤减半那一档在引擎里）+ 类别耗时 40/30 刻
      （`content/rules/action_base.json`）—— 两样都不是本文件写的。
    """
    p = _p(player)
    _mx, _line = hp_cap_or_line(p)
    if _line:
        yield _line
        return
    # ★ B3-26：在场里 ⇒ 走「场」那道（防御也是「你这一手」；超时保底就是它）
    from . import instance as INST
    if INST.route_needed(env, uid):
        async for line in INST.take_turn(env, p, uid, player, action="defend"):
            yield line
        return
    async for line in _open_and_hand(env, p, uid, player, "", action="defend"):
        yield line


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
    """`逃跑` —— 真源 `04_指令总表 §五` 只写「可能失败」、**没给失败率** ⇒ 不编数。

    ★ B4-18：原先回的是**代码里的一句内联桩句**「（第一版还没接轮流制。）」——
      玩家看到的是开发注记，而且指不到任何一条真能用的路（同一族的『后撤』早在 B3-8
      就接成了真动作，还能跑 / 跑不掉两态分明）。现在走槽位 `COMBAT_FLEE_TODO`：
      照实说 + 指向**真能用**的『后撤』。
      要不要给「逃跑」一个失败率、或者干脆并进『后撤』—— 等真源一句话（台账 §3 · P-57）。
    """
    yield T("COMBAT_FLEE_TODO")
