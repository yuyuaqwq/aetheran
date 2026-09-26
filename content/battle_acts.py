# -*- coding: utf-8 -*-
"""《阿斯特兰》战斗中的那几手（B3-23）—— 内容侧机制动作，引擎零改动。

谁在用：`content/cmds_battle.py` 那六条战斗指令（打断 / 后撤 / 放技能 / 战斗中用物 /
集火 / 换武器）。本文件只管一件事：**在战斗中真把这一手做出来**，要说的那句话交给
`texts` 槽位（本文件零中文文案 —— probe_copy 对新文件的要求是 0）。

三处真源（都不在代码里写）：
    content/rules/action_base.json   行动类别 → 基准耗时（刻）：`interrupt` / `swap`
    content/rules/battle_cmds.json   本批的边界数：每场用物上限
    content/data/skills.json         本职业那个「打断动作」是哪一个（`mech == "interrupt"`）

引擎侧只用**一个既有契约**：`Battle.action_override`（非内置动作 → 内容侧回调，
形状见引擎 `battle/battle.py::act` 与 `games/orlandia/tests/test_battle_n5b4e_hooks.py`）：

    override(battle, action, actor, skill_name, target) -> (logs, cast, recover)

`cast` 给**行动类别名**（走上面那张声明表），`recover=None`（让类别自己的第二段生效）
—— 本文件不写任何数字时长（时间形状与数值全在内容侧声明里）。

★ 本层的两条口径（真源 `06_第一阶段垂直切片/02_战斗机制 §〇·五`：伪即时 CTB，绝对时刻制）：

    打断   ① 对方正在**出招窗口**（引擎 `actor["charging"]`）⇒ 清掉它那一手（引擎
           `effects.act_interrupt` 动词，含 `interrupt` 事件与霸体判定）⇒ 这一手它没打出来；
           ② 无论有没有拆掉那一手，都把它下一次行动的**到点时刻推后**「你这一手的耗时」
           （= 把对方的行动推到更晚的时刻；数字来自声明表，不手打）。
    用物   一场遭遇里同一件东西最多 `item_uses_per_battle` 次；用满之后那一手**回落成普攻**
           （不是白花，也不静默 —— 出槽位行说明为什么）。

★ 这一层**不做**的事（写在这儿免得下一轮当成已完，详见本工作树 `_notes.md`）：
    · `skills.mech` 的通用消费端（effect_rules）不在本批 —— 「断势」的伤害/破绽那半截仍走
      `技能 <名>` 那条路；本批只让「打断」这条**指令**是控制动作。
    · 面板在**开战时**就固化（`panel_build.build_actor` 写死了 panel_stack），所以
      「战斗中用物」只认**回血**那一类；食物/增益类落不到这一场（fail-closed，不假冒）。
    · 怪技没有中文名（`skills_lookup.monster_skill` 拿 id 当名字）⇒ 打断那一行的
      「它起手的那一下」报不出技名（报出来就是机器键）。
"""
from __future__ import annotations

import json
import os

from ext_combat.battle import actions as ACT
from ext_combat.battle import effects as EF
from ext_combat.battle import schedule as SCH
from ext_combat.battle import stats as ST
from ext_combat.battle.actors import ActCtx, actor_alive

from .cmds_ast import T

#: 行动类别名（引擎按类别查 `action_base.json`；类别名与真源「一次行动」那三个词一一对应）
CAT = {"interrupt": "interrupt", "item": "item", "swap": "swap", "retreat": "move"}

_RULES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules", "battle_cmds.json")
_RULES_CACHE = None


def rules() -> dict:
    """`content/rules/battle_cmds.json` —— fail-closed：读不到 / 键坏了就当场抛（不静默给默认）。"""
    global _RULES_CACHE
    if _RULES_CACHE is None:
        with open(_RULES, encoding="utf-8") as f:
            got = json.load(f)
        if not isinstance(got, dict):
            raise ValueError("battle_cmds.json 得是一张表：%r" % (got,))
        n = got.get("item_uses_per_battle")
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            raise ValueError("item_uses_per_battle 得是 1 以上的整数（没有默认值）：%r" % (n,))
        # ★ P-57：失败率也走同一道 fail-closed（写成 bool / 空 / 越界都当场抛 —— 不静默给默认）
        pct = got.get("flee_fail_pct")
        if isinstance(pct, bool) or not isinstance(pct, (int, float)) \
                or not 0.0 <= float(pct) <= 1.0:
            raise ValueError("flee_fail_pct 得是 0 到 1 之间的数（没有默认值）：%r" % (pct,))
        _RULES_CACHE = got
    return _RULES_CACHE


def flee_fail_pct() -> float:
    """`逃跑` 的失败率（唯一声明处 = `content/rules/battle_cmds.json` 的 `flee_fail_pct`）。

    ★ P-57：本文件与 `cmds_battle.flee` 都**不写这个数** —— 只读声明表（取值只有一个口）。
    """
    return float(rules()["flee_fail_pct"])


# ══════════════════════════════════════════════════════════════
# 取值小件
# ══════════════════════════════════════════════════════════════
def pick_target(battle, target=None) -> dict | None:
    """这一手对着谁 —— 给了活的就用它，否则取敌方第一个还有气的（没有 = None，不兜底）。"""
    if isinstance(target, dict) and actor_alive(target):
        return target
    for a in (battle.sides.get("enemy") or []):
        if actor_alive(a):
            return a
    return None


def hand_ticks(battle, actor, cat: str) -> float:
    """一手的总耗时（刻）= 两段相加 —— 形状与数值全走内容侧声明表（本文件不写数）。"""
    spd = ST.actor_spd(battle, actor)
    return (float(SCH.action_time(spd, SCH.action_base_of(cat)))
            + float(SCH.recover_time(spd, SCH.recover_base_of(cat))))


def _item_rec(iid) -> dict:
    from .cmds_ast import _data
    return (_data("items") or {}).get(iid) or {}


def _take(p, iid, n=1) -> None:
    """从背包拿掉一件（与 `cmds_gear._take` 同形：同一层拷贝、减到 0 就摘掉条目）。"""
    bag = dict((p or {}).get("bag") or {})
    left = int(bag.get(iid) or 0) - int(n)
    if left > 0:
        bag[iid] = left
    else:
        bag.pop(iid, None)
    (p or {})["bag"] = bag


def _plain_attack(battle, actor) -> list:
    """普攻那一条路（引擎自己那条 `actions.do_attack`）—— 用物超限时那一手照打。"""
    ctx = ActCtx(caster=actor, action="attack", target=pick_target(battle))
    return list(ACT.do_attack(battle, ctx))


# ══════════════════════════════════════════════════════════════
# 一手
# ══════════════════════════════════════════════════════════════
class Hand:
    """玩家的「这一手」—— 一条指令一个实例，`override` 交给引擎的 `action_override`。

    · `kind`  : interrupt / item / swap / retreat（本批四种非内置动作）
    · `p`     : 玩家档（用物要从它的背包里扣）
    · `item`  : 用物那一件（id）
    · `lines` : 由调用方渲染好的槽位行（换手 / 退不开 那两种「这一手 = 说一句」的动作）
    · `used`  : **这一场**里用了几次（物品 id → 次）—— 上限的记账就在这儿，跨手有效
    """

    def __init__(self, kind, *, p=None, item=None, lines=None):
        self.kind = str(kind)
        self.p = p
        self.item = item
        self.lines = list(lines or [])
        self.used = {}
        self.ok = False                     # 这一手是否真的做成了（探针/回话用）

    # ---------------------------------------------------------- 引擎回调
    def override(self, battle, action, actor, skill_name, target):
        if self.kind == "interrupt":
            return self._interrupt(battle, actor, target)
        if self.kind == "item":
            return self._item(battle, actor, skill_name or self.item)
        if self.kind == "swap":
            return (list(self.lines), CAT["swap"], None)
        if self.kind == "retreat":
            return (list(self.lines), CAT["retreat"], None)
        return ([], None, None)

    # ---------------------------------------------------------- 打断
    def _interrupt(self, battle, actor, target):
        cat = CAT["interrupt"]
        tgt = pick_target(battle, target)
        if tgt is None:
            return ([T("COMBAT_INT_PLAIN")], cat, None)
        push = hand_ticks(battle, actor, cat)
        slot = tgt.get("charging")
        broke = isinstance(slot, dict) and not slot.get("unstoppable")
        if broke:
            # 引擎动词：清掉待发 + 广播 interrupt 事件（霸体那一档它自己会拒绝）——
            # 它自己那句日志丢掉（玩家看到的那句走下方槽位，措辞归内容侧）。
            EF.act_interrupt(battle, actor, tgt, {}, [])
        tgt["ct"] = float(tgt.get("ct") or 0) + push
        self.ok = True
        line = T("COMBAT_INT_BREAK") if broke else T("COMBAT_INT_PUSH", ticks=int(push))
        return ([line], cat, None)

    # ---------------------------------------------------------- 战斗中用物
    def _item(self, battle, actor, iid):
        cat = CAT["item"]
        cap = int(rules().get("item_uses_per_battle") or 1)
        rec = _item_rec(iid)
        name = str(rec.get("name") or iid)
        if int(self.used.get(iid, 0)) >= cap:
            # 上限用满：这一手**回落成普攻**（白纸黑字，不静默、也不白花）
            return ([T("COMBAT_ITEM_CAP", name=name)] + _plain_attack(battle, actor), "attack", None)
        from .cmds_recipe import _heal_gain                  # 回血口径唯一一口
        mx = ST.actor_max_hp(battle, actor)
        gain = _heal_gain(self.p, rec, mx)
        if gain is None:
            return ([T("SYS_USE_NOT", name=name)], cat, None)
        hp0 = int(actor.get("hp") or mx)
        actor["hp"] = min(int(mx), hp0 + int(gain))
        _take(self.p, iid, 1)
        self.used[iid] = int(self.used.get(iid, 0)) + 1
        self.ok = True
        # 报的是**真回了多少**（被上限截掉的不算）—— 与 `使用` 那条路同一个槽位
        return ([T("SYS_USE_HEAL", name=name, heal=max(0, actor["hp"] - hp0),
                   hp=actor["hp"], hp_max=int(mx))], cat, None)


def interrupt_action_of(p) -> dict | None:
    """本职业那个「打断动作」—— `skills` 域里 `mech == "interrupt"` 且属于这一门的那一条。

    真源 `06_第一阶段垂直切片/04_指令总表 §五`：「打断 —— 打断动作（名称随职业）」。
    ★ 今天域里**只有刺客**挂了这一条（`SKILL_SHD_sever` 断势）⇒ 其余五门拿不到名字，
      回话走通用那一句，并把「五门待补」登记进 `_notes.md`（不在这儿编名字）。
    """
    from .cmds_ast import _data
    cls = str((p or {}).get("cls") or "")
    if not cls:
        return None
    for k, v in (_data("skills") or {}).items():
        if str(k).startswith("_") or not isinstance(v, dict):
            continue
        if v.get("mech") == "interrupt" and str(v.get("owner_class") or "") == cls:
            return dict(v, id=k)
    return None
