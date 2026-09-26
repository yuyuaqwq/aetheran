# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 第六组：配方与生产（B2-6 —— 烹饪 / 强化）

四个动词 + 一个「吃」：

  配方              看会做什么（没学会的那几道给「谁教会你」）
  烹饪 <菜名>       2–3 样食材 → 一份菜（进背包；吃下去给 15 分钟增益）
  铁匠铺            柯尔的报价单（每一档要什么料、多少钱、成率）
  强化 <装备名>     吃材料 + 钱；+1..+5 必成，+6 起看运气（失败只吃材料）
  使用 / 吃 <东西>  药水回血 · 菜给增益（增益在战斗面板里生效）

数值全部从 `recipes` 域来（域由 `scripts/rebuild_recipes.py` 从源文档解析生成）。
药水回多少写在 **items 域的 `effect`** 里（数值不在代码里）：`{"hp": 30}` = 固定多少 ·
`{"hp_pct": 0.3}` = 上限的几成；`heal` 是同一个口的老写法 —— 由生成器从 desc「回 N 点生命」解析。
文案全部从 `texts` 域来 —— 本文件只传槽位。
"""
from __future__ import annotations

import random

from .cmds_ast import _data, _p, _save, T, hp_cap_or_line
from .town import _func_node, town_gate
from .cmds_talk import _arg
from .cmds_gear import ambig_line
from .cmds_codex import new_lines
from . import codex as CX
from . import loot as LT
from . import gear as GB


def _recipes() -> dict:
    return {k: v for k, v in _data("recipes").items() if not str(k).startswith("_")}


def _meta() -> dict:
    return dict((_data("recipes").get("_meta") or {}).get("enhance") or {})


def _item(iid: str) -> dict:
    return _data("items").get(iid) or {}


def _quest_name(qid: str) -> str:
    return (_data("quests").get(qid) or {}).get("name") or qid


def _bag(p) -> dict:
    return p.get("bag") or {}


def _have(p, iid: str) -> int:
    return int(_bag(p).get(iid) or 0)


def _take(p, iid: str, n: int) -> None:
    bag = dict(_bag(p))
    left = int(bag.get(iid) or 0) - int(n)
    if left > 0:
        bag[iid] = left
    else:
        bag.pop(iid, None)
    p["bag"] = bag


def _need_str(entries) -> str:
    return " · ".join("%s ×%d" % (_item(e["id"]).get("name", e["id"]), int(e["n"])) for e in entries)


def _lack_str(p, entries) -> str:
    lack = []
    for e in entries:
        d = int(e["n"]) - _have(p, e["id"])
        if d > 0:
            lack.append("%s ×%d" % (_item(e["id"]).get("name", e["id"]), d))
    return " · ".join(lack)


def _knows(p, rec: dict) -> bool:
    learn = rec.get("learn") or {}
    qid = learn.get("quest")
    if not qid:
        return True
    return qid in ((p.get("flags") or {}).get("quests_done") or [])


def _learn_from(rec: dict) -> str:
    learn = rec.get("learn") or {}
    return _quest_name(learn.get("quest")) if learn.get("quest") else ""


def _buff_label(rec: dict) -> str:
    b = rec.get("buff") or {}
    return "%s +%d%%" % (b.get("stat_name") or b.get("stat"), int(b.get("pct") or 0))


def _cookable() -> dict:
    """能下锅的菜 —— ★ B3-6b-2d-keys-2：按 ASCII `kind_key` 挑（原先比中文枚举「烹饪」）。"""
    return {k: v for k, v in _recipes().items() if v.get("kind_key") == "cook"}


# ══════════════════════════════════════════════════════════════
# 一、配方一览
# ══════════════════════════════════════════════════════════════
async def recipe_list(env, sink, uid, player):
    p = _p(player)
    cooks = _cookable()
    known = [(k, v) for k, v in sorted(cooks.items()) if _knows(p, v)]
    locked = [(k, v) for k, v in sorted(cooks.items()) if not _knows(p, v)]
    yield T("SYS_RECIPE_HEAD", known=len(known), locked=len(locked))
    for _k, v in known:
        ing = " + ".join("%s×%d" % (_item(e["id"]).get("name", e["id"]), int(e["n"]))
                         for e in (v.get("inputs") or []))
        yield T("SYS_RECIPE_ROW", icon=v.get("icon", "🍲"), name=v.get("name", _k),
                ing=ing, buff=_buff_label(v))
    for _k, v in locked:
        # `from` 是 Python 关键字 ⇒ 槽位只能走 **{} 传
        yield T("SYS_RECIPE_LOCKED", **{"from": _learn_from(v)})


# ══════════════════════════════════════════════════════════════
# 二、烹饪
# ══════════════════════════════════════════════════════════════
async def cook(env, sink, uid, player):
    p = _p(player)
    want = _arg(env)
    if not want:
        async for line in recipe_list(env, sink, uid, player):
            yield line
        return
    hit = None
    for rid, rec in _cookable().items():
        nm = str(rec.get("name") or "")
        if want == nm or (len(want) >= 2 and want in nm):
            hit = (rid, rec)
            break
    if not hit:
        yield T("SYS_COOK_UNKNOWN", input=want)
        return
    rid, rec = hit
    if not _knows(p, rec):
        yield T("SYS_COOK_LOCKED", name=rec.get("name", rid), **{"from": _learn_from(rec)})
        return
    ins = rec.get("inputs") or []
    lack = _lack_str(p, ins)
    if lack:
        yield T("SYS_COOK_MISSING", name=rec.get("name", rid), need=_need_str(ins), lack=lack)
        return
    for e in ins:
        _take(p, e["id"], int(e["n"]))
    out = rec.get("out")
    n = int(rec.get("out_n") or 1)
    LT.add_to_bag(p, [{"id": out, "n": n}])
    new = CX.note_items(p, [out])              # ★ 做出来就进风味谱
    f = dict(p.get("flags") or {})
    cooked = dict(f.get("cooked") or {})
    cooked[rid] = int(cooked.get(rid, 0)) + 1
    f["cooked"] = cooked
    p["flags"] = f
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_COOK_OK", name=rec.get("name", rid), icon=rec.get("icon", "🍲"),
            buff=_buff_label(rec), minutes=int((rec.get("buff") or {}).get("seconds", 0)) // 60)
    for line in new_lines(new):
        yield line


# ══════════════════════════════════════════════════════════════
# 三、铁匠铺（柯尔的报价单）
# ══════════════════════════════════════════════════════════════
async def smith(env, sink, uid, player):
    """`铁匠铺` —— 柯尔的炉子（声明里的 `guard_desc` = 在镇上 · 那一站 = 半截铁砧）。

    ★ B4-12：原先这一条不判脚下 ⇒ 人站在骨田也能把强化价目表看个遍（镇上其它几处都判）。
      守卫走唯一执行面 `cmds_ast.town_gate`，那一站从 `npcs.funcs` 的 `smith` 现取（不写死节点 id）。
    """
    p = _p(player)
    line = town_gate(p, _func_node("smith"))
    if line:
        yield line
        return
    meta = _meta()
    cap = int(meta.get("cap") or 0)
    yield T("SYS_ENHANCE_SHOP")
    for lv in range(1, cap + 1):
        step = _recipes().get("rc_enh_%02d" % lv) or {}
        yield T("SYS_ENHANCE_ROW", lv=lv, need=_need_str(step.get("inputs") or []),
                gold=int(step.get("gold") or 0),
                rate="%d%%" % round(float(step.get("rate") or 0) * 100))


# ══════════════════════════════════════════════════════════════
# 四、强化
# ══════════════════════════════════════════════════════════════
async def enhance(env, sink, uid, player):
    p = _p(player)
    # ★ P3 BUG-2（本波 f4）：**地点门禁** —— 强化是铁匠铺的服务，本该与『铁匠铺』同口径。
    #   原先这一条一句都不判脚下 ⇒ 人站在骨田（野外）敲 `强化 <装备>` 照样把报价与缺料
    #   摊出来（同一批里『铁匠铺』却正确拦下 —— 规则不一致）。守卫走唯一执行面
    #   `cmds_ast.town_gate`，那一站从 `npcs.funcs` 的 `smith` 现取（不写死节点 id；
    #   与 `cmds_recipe.smith` 逐字同一条口）。空参那一支（报价表）也一并拦 —— 它就是那张表。
    line = town_gate(p, _func_node("smith"))
    if line:
        yield line
        return
    want = _arg(env)
    if not want:
        yield T("SYS_ENHANCE_SHOP")
        return
    # ★ B4-20：认的是**背包里**的那一件（`need_slot` = 域里 ASCII `slot` 那六格）。
    #   原先扫的是**整张物品表**的第一个同名 —— 手里只有「精制」那档时会回「背包里没有」，
    #   两档在手时又静默强了字典序在前的那一件。
    iid, rec, cands = LT.pick(sorted(p.get("bag") or {}), want, need_slot=True)
    if not iid:
        if cands:                      # ★ B4-20：同名好几件 ⇒ 照实说，不替玩家挑
            yield ambig_line("enhance", want, cands)
        else:
            yield T("SYS_ENHANCE_NOITEM", input=want)
        return
    meta = _meta()
    cap = int(meta.get("cap") or 0)
    lv_now = int(((p.get("enhance") or {}).get(iid) or {}).get("lv") or 0)
    nxt = lv_now + 1
    if nxt > cap:
        yield T("SYS_ENHANCE_CAP", item=rec.get("name", iid), cap=cap)
        return
    step = _recipes().get("rc_enh_%02d" % nxt) or {}
    ins = step.get("inputs") or []
    fee = int(step.get("gold") or 0)
    lack = _lack_str(p, ins)
    if fee > int(p.get("gold") or 0):
        lack += (" · " if lack else "") + T("SYS_GOLD_X", n=fee - int(p.get("gold") or 0))
    if lack:
        yield T("SYS_ENHANCE_MISSING", lv=nxt, need=_need_str(ins), gold=fee, lack=lack)
        return
    # 第 n 次尝试 → 同种子可复现（探针要能对着率表算分布）
    f = dict(p.get("flags") or {})
    tries = dict(f.get("enhance_tries") or {})
    key = "%s@%d" % (iid, nxt)
    n_try = int(tries.get(key, 0))
    tries[key] = n_try + 1
    f["enhance_tries"] = tries
    p["flags"] = f
    rnd = random.Random("%s:%s:%d:%d" % (uid, iid, nxt, n_try))
    done = rnd.random() < float(step.get("rate") or 0)
    for e in ins:                                   # 材料：成功失败都吃
        _take(p, e["id"], int(e["n"]))
    cap_label = "%.1f" % (float(meta.get("bonus_per_level") or 0.0) * cap * 100)   # % 由槽位带
    if done:
        p["gold"] = int(p.get("gold") or 0) - fee   # 钱：成了才收（「失败只吃材料」）
        fl = float(step.get("float") or 0.0)
        jitter = (1.0 + rnd.uniform(-fl, fl)) if fl else 1.0
        bonus = round(float(meta.get("bonus_per_level") or 0.0) * nxt * jitter, 6)
        enh = dict(p.get("enhance") or {})
        enh[iid] = {"lv": nxt, "bonus": bonus}
        p["enhance"] = enh
        line = T("SYS_ENHANCE_OK", item=rec.get("name", iid), lv=nxt,
                 bonus="+%.1f%%" % (bonus * 100), cap=cap_label)
    else:
        line = T("SYS_ENHANCE_FAIL", item=rec.get("name", iid), lv=lv_now)
    if player is not None:
        player.update(p)
    _save(env)
    yield line
    yield T("SYS_MONEY", gold=int(p.get("gold") or 0))


# ══════════════════════════════════════════════════════════════
# 五、吃 / 喝（药水回血 · 菜给 15 分钟增益）
# ══════════════════════════════════════════════════════════════
def _stat_label(iid: str, stat: str) -> str:
    """增益的中文名 —— 真源在配方的 `buff.stat_name`（代码不另抄一份对照表）。"""
    rid = (_item(iid).get("from_recipe") or "")
    return str((( _recipes().get(rid) or {}).get("buff") or {}).get("stat_name") or stat)


#: 药水的效果词表 —— **数值一律来自数据**（items 域那条记录的 `effect`），代码只认键名：
#:   {"hp": 30}       固定回多少
#:   {"hp_pct": 0.3}  上限的几成（药水的 desc 里没有数字可解析 ⇒ 效果就声明在数据里）
#: 认不出效果的（键不认识 / 压根没写）一律回「不是这么用的」—— fail-closed，不静默按 0 算。


def _heal_gain(p, rec: dict, mx: int):
    """这条东西用下去回多少血（认不出效果给 None）。

    ★ P-27 收口：上限只走**唯一的那个来源**（职业面板，`cmds_ast.hp_cap`）—— 原先这里读的是
    档上那个写死 100 的值（与面板两个源 ⇒ 喝药封顶在 100）。与 `cmds_gather.rest` 同口径。
    `mx` 由调用方从那个口取好（档上还没职业时给 0 ⇒ 本函数只认 `hp` 那一路）。
    `heal` 是**生成器**的口（`scripts/rebuild_recipes.py ⑦` 从 desc「回 N 点生命」解析，禁手打）——
    这里把它归一到同一套算法，所以「伤药」与「药水」走的是同一条路。
    """
    eff = rec.get("effect")
    if eff is None and rec.get("heal"):
        eff = {"hp": rec.get("heal")}
    if not isinstance(eff, dict):
        return None
    gain, hit = 0, False
    if "hp" in eff:
        hit, gain = True, gain + int(eff.get("hp") or 0)
    if "hp_pct" in eff:
        hit, gain = True, gain + int(round(mx * float(eff.get("hp_pct") or 0)))
    if not hit:
        return None
    return max(0, gain)


async def item_use(env, sink, uid, player):
    p = _p(player)
    want = _arg(env)
    if not want:
        # ★ B4-13：裸「使用」/「用」/「吃」—— 原先回「『（空）』不是这么用的」（空引号错话）
        yield T("SYS_USE_ASK")
        return
    iid, rec, cands = LT.pick(sorted(_bag(p)), want)     # ★ B4-20：一件东西只认一个口
    if not iid and cands:                  # ★ B4-20：同名好几件 ⇒ 照实说（别吃错东西）
        yield ambig_line("item_use", want, cands)
        return
    hit = (iid, rec) if iid else None
    if not hit or _have(p, hit[0]) <= 0:
        # ★ B4-8：**手上没有这件**与「有、但认不出效果」是两件事 —— 原先两句共用
        #   `SYS_USE_NOT`（「药水不是这么用的」），玩家手里压根没有药水时听到这句，
        #   等于被糊了一句假话。缺件走 `查看` / `丢弃` / `装备` 同一个口（口径表里那一行）。
        yield T("SYS_GEAR_IN_BAG", name=want)
        return
    iid, rec = hit
    food = rec.get("food") or {}
    if food:
        from . import facade
        p["food_buff"] = {"stat": food.get("stat"), "pct": int(food.get("pct") or 0),
                          "until": float(facade.clock()) + int(food.get("seconds") or 0)}
        CX.note_items(p, [iid])                # ★ 吃过也算（买来的菜也记）
        _take(p, iid, 1)
        if player is not None:
            player.update(p)
        _save(env)
        yield T("SYS_USE_FOOD", name=rec.get("name", iid),
                buff="%s +%d%%" % (_stat_label(iid, str(food.get("stat"))), int(food.get("pct") or 0)),
                minutes=int(food.get("seconds") or 0) // 60)
        return
    # ★ P-27：上限只有一个来源 = 职业面板。档上还没有职业 ⇒ **不出假数**：出一行点名的
    #   fail-closed 行（`hp_cap_or_line`），这一支不做（药水也不消耗）。
    mx, _line = hp_cap_or_line(p)
    gain = _heal_gain(p, rec, mx or 0)
    if gain is not None:
        if _line:
            yield _line
            return
        hp0 = int(p.get("hp") or mx)
        # ★ P1 BUG-8（本波 f4）：**满血不吃药** —— 原先 `使用 伤药`（112/112）照样把药吃掉、
        #   只回一句「生命 +0（112/112）」：24 铜板一次，新手钱很少（实测同一档踩了两次）。
        #   现在满血 ⇒ 照实说一句、**道具一件不动**（不扣、不落档）；缺那一句就退回现在这毛病。
        if hp0 >= mx:
            yield T("SYS_USE_FULL", name=rec.get("name", iid))
            return
        hp = min(mx, hp0 + gain)                 # ★ 回血封顶：不许超过上限
        p["hp"] = hp
        _take(p, iid, 1)                         # ★ 用了就消耗（减到 0 由 _take 摘掉条目）
        if player is not None:
            player.update(p)
        _save(env)
        # ★ 报的是**真回了多少**（被上限截掉的那部分不算）—— 否则「+40（100/100）」是句假话
        yield T("SYS_USE_HEAL", name=rec.get("name", iid), heal=max(0, hp - hp0), hp=hp, hp_max=mx)
        return
    yield T("SYS_USE_NOT", name=rec.get("name", iid))
