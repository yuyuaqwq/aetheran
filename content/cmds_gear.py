# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 装备那三条（B3-9「装备与技能」那组）：装备 / 卸下 / 装备对比。

口径（真源 `06_第一阶段垂直切片/04_指令总表.md` §三 · §四）：

    装备 <装备>（别名 装 / 穿）  守卫「背包里有」  → 穿上
    卸下 <部位>（别名 卸 / 脱）  守卫「已装备」    → 脱
    对比 <物品>（别名 装备对比）                   → 换不换

三条动的是**同一格**：档上的 `equipped`（六格 weapon / armor_top / armor_bottom /
helmet / boots / accessory —— 词表在 `schemas/items.schema.json` 的 `slot.enum`）。
代码只认域里现成的 ASCII `slot`，**不引中文枚举**（K48 / P-20；probe_copy ⑮ 钉 0 处）。

★ 为什么不另开一套「装备数值」的口：面板侧只有 `content/gear.py` 那一个出口
  （`gear_stats` / `enhance_bonus` / `food_buff`）—— 本文件**全部借它**算加成与差值，
  自己一行数值口径都不写（数值不许手打）。所以「穿上之后面板真的变」是结构性的：
  改 `equipped` ⇒ `panel_build.hp_cap` / 战斗 actor 下一拍跟着变（P-27 起的派生口径，
  `probe_panel` ⑤ 真跑钉着「穿 → 三处一起涨 → 脱 → 逐字回原样」）。

★ 卸下回背包**不走 `loot.add_to_bag`**：那个口会顺手把东西记进 `codex`（掉落路径要它，
  卸下不要）—— 走它会让「穿一次再脱」凭空多一条图鉴记录，也不满足「逐字回原样」。
  这里按 `_take` 的逆写一格（同一层拷贝、不原地改 —— B3-12 的那个坑）。

★ 文案一律走 texts（`SYS_GEAR_*` / `SYS_CMP_*` / `SYS_STAT_*`）—— 本文件不内联中文。
  「换下来的那件收进背包」与「穿上 / 卸下」分开两句：换装时玩家要看得见**哪一件**下去了。

★ B3-19（2026-09-25）：**穿上要看加点**（鱼鱼：「装备应该也是要依赖加点才能穿的吧」）——
  `items.req` = `{attr, v, level}`（家族 × 品质 × 建议加点曲线算出来的最小值，见
  `scripts/rebuild_item_reqs.py`）；不够 ⇒ `SYS_GEAR_REQ` 那一行（还差几点），**不改档**。
  口径 = fail-closed，不做「能穿但减半」；`req` 缺字段 / 值坏了 ⇒ 当场抛（不当无门槛放过去）。
  只有「穿」这一条路判门槛：**已穿上的旧档不报错**（`卸下` / `对比` 也不受影响）。
"""
from __future__ import annotations

from .cmds_ast import _data, _p, _save, T
from .cmds_talk import _arg
from . import gear as GB


# ══════════════════════════════════════════════════════════════
# 取值小件（本文件只有这一层：不碰数值口径，全借 gear.py 那一个口）
# ══════════════════════════════════════════════════════════════
def _item(iid) -> dict:
    return _data("items").get(iid) or {}


def _num(a) -> float | None:
    """词条的数值（不是数的 = None：效果类 / 笼统类那一档 —— 改的是规则，不是数字）。"""
    v = a.get("v")
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _fmt(v) -> str:
    """数值 → 一行里那种写法（9.0 → 9 · 0.5 → 0.5）。"""
    return "%g" % float(v)


def stat_label(stat) -> str:
    """词条数值键 → 中文名 —— 唯一来源是 texts 的 `SYS_STAT_*` 槽位（代码不内联中文）。

    ★ fail-closed：槽位缺了就照 `T()` 的规矩回 `[MISSING TEXT: …]`（当场看得见）——
      `probe_items` ⑨ 把「装备用到的每个数值键都有槽位」钉住，不许悄悄漏给玩家。
    """
    return T("SYS_STAT_%s" % str(stat or "").upper().replace("-", "_"))


def affix_lines(rec) -> list:
    """一件装备的词条 → 给玩家看的行。

    带 `note` 的走 `note` 原文（效果类 / 笼统类：说不成 +N 的那种，域里本来就写着人话）；
    其余的走「中文名 + 数值」。两类在 items 域是互斥的（有 note 的不写裸数值）。
    """
    out = []
    for a in rec.get("affixes") or []:
        note = str(a.get("note") or "")
        v = _num(a)
        if note:
            out.append(T("SYS_GEAR_AFFIX_NOTE", note=note))
        elif v is not None:
            out.append(T("SYS_GEAR_AFFIX_ROW", label=stat_label(a.get("stat")), value=_fmt(v)))
    return out


# ══════════════════════════════════════════════════════════════
# 门槛（B3-19）：装备要依赖加点才穿得上 —— 不够就穿不上（fail-closed）
# ══════════════════════════════════════════════════════════════
def req_of(iid) -> dict | None:
    """这件装备的属性门槛（域里的 `req` 那一格）；**没有那一格 = 无门槛**。

    ★ 门槛值不在这一层算 —— `scripts/rebuild_item_reqs.py` 从「家族 × 品质 × 建议加点曲线」
      算好落进域里（数值不许手打，判据 `probe_panel` ⑦ / `probe_items` ⑩ 逐件重算对账）。
      这一层只判「够不够」。
    ★ 有那一格但坏了（缺 `attr` / `v` 不是正整数）⇒ **当场抛**，不许当无门槛放过去
      （fail-closed：坏数据静默变宽松 = 门槛失效，那正是这一批要根除的病）。
    """
    r = _item(iid).get("req")
    if not r:
        return None
    attr, v = str(r.get("attr") or ""), r.get("v")
    if not attr or not isinstance(v, int) or isinstance(v, bool) or int(v) < 1:
        raise ValueError("物品 %s 的 req 坏了：%r —— 门槛判不了（fail-closed，不当无门槛）"
                         % (iid, r))
    return {"attr": attr, "v": int(v), "level": int(r.get("level") or 0)}


def attr_points(p, attr) -> int:
    """档上该五维属性**加了多少点** —— 唯一口径 = `alloc` 那一格。

    ★ 建号那 8 点的**起始五维**真源里还没有（`05_玩法数值口径 §二` 同款问题：
      「五维起始值」没有出处）⇒ 这里不编一个起点，只算玩家自己加的
      （`cmds_more.attrs` 那一页说的也是「加过哪些点」）。见 `_notes.md` 的待补项。
    """
    return int((p.get("alloc") or {}).get(str(attr)) or 0)


def unmet_req(p, iid) -> dict | None:
    """没够的门槛：`{name, attr, need, have, gap}`；够了 / 无门槛 ⇒ None。

    `attr` 那一格是**中文名**（走 `SYS_STAT_*` 槽位，代码不内联中文）。
    """
    req = req_of(iid)
    if not req:
        return None
    have = attr_points(p, req["attr"])
    if have >= req["v"]:
        return None
    return {"name": _item(iid).get("name", iid), "attr": stat_label(req["attr"]),
            "need": req["v"], "have": have, "gap": req["v"] - have}


def stats_of(p, iid) -> dict:
    """一件东西**穿上后**进面板的数值 —— 走现成的唯一取值口（`gear.gear_stats`）。

    ★ 不另写一份叠加规则：主词条吃强化加成、其余词条原样 —— 与面板 / 战斗同一个口
      （`panel_build.gear_and_buffs` 也走这里）⇒ 对比出来的差值就是面板真会动的那几个数。
    ★ 槽位键对 `gear_stats` 无意义（它只遍历值），所以这里随便给一个占位键。
    """
    return GB.gear_stats({"equipped": {"_one": iid}, "enhance": p.get("enhance") or {}})


def plain_stats(rec) -> set:
    """一件装备里**不带 note 的数值词条键** —— 对比只比这些（带 note 的走「改规则」那几行）。

    ★ 为什么这么切：带 note 的是**规则**（`11_装备特色词条池_v1 §六` 那一类「效果类」），
      数值之差说不成人话（`dmg_half_chance 10 → 0` 到底算好还是坏？），语义由域里那句 `note`
      原样带出来；不带 note 的那些才是面板属性 —— 它们的差值就是面板真会动的数。
    ★ 取值仍然全部来自 `gear_stats`（同一个口）—— 本函数只决定**列哪几行**，不改任何数值。
    """
    out = set()
    for a in rec.get("affixes") or []:
        if a.get("note") or _num(a) is None:
            continue
        out.add(a.get("stat"))
    return out


def _cap_with(p, equipped) -> int | None:
    """那份档（换过 equipped 的）的生命上限 —— 走 P-27 那唯一一个来源；没职业 ⇒ None。"""
    from . import panel_build as PB
    rec = dict(p)
    rec["equipped"] = equipped
    return PB.hp_cap(rec, strict=False)


def _to_bag(p, iid, n: int = 1) -> None:
    """往背包放回一件（`_take` 的逆 —— 同一层拷贝、不原地改）。"""
    bag = dict(p.get("bag") or {})
    bag[iid] = int(bag.get(iid) or 0) + int(n)
    p["bag"] = bag


def _take(p, iid, n: int = 1) -> None:
    """从背包拿掉一件（与 `cmds_recipe._take` 同形：减到 0 就摘掉条目）。"""
    bag = dict(p.get("bag") or {})
    left = int(bag.get(iid) or 0) - int(n)
    if left > 0:
        bag[iid] = left
    else:
        bag.pop(iid, None)
    p["bag"] = bag


def _in_bag(p, want, need_slot: bool = False):
    """背包里按名字（或 id）找一件；`need_slot=True` 时只认能穿的。返回 `(iid, rec)`。

    ★ 「≥2 字才算部分匹配」与 `cmds_recipe._item_of_name` 同一口径（一个字太容易误中）。
    """
    want = str(want or "").strip()
    if not want:
        return (None, None)
    for iid in sorted(p.get("bag") or {}):
        rec = _item(iid)
        if need_slot and not rec.get("slot"):
            continue
        nm = str(rec.get("name") or "")
        if want == iid or (nm and (want == nm or (len(want) >= 2 and want in nm))):
            return (iid, rec)
    return (None, None)


def _worn(p, want):
    """身上那一件：按 名字 / id / 部位名 / 部位键 认。返回 `(slot, iid, rec)`。"""
    want = str(want or "").strip()
    for slot in sorted(p.get("equipped") or {}):
        iid = (p.get("equipped") or {})[slot]
        rec = _item(iid)
        nm = str(rec.get("name") or "")
        if not want:
            continue
        if want in (str(iid), slot, str(rec.get("kind") or "")) \
                or (nm and (want == nm or (len(want) >= 2 and want in nm))):
            return (slot, iid, rec)
    return (None, None, None)


def _not_there(p, want):
    """认不出目标时统一出口：穿在身上了 / 不是能穿的 / 背包里根本没有（三档分开说）。"""
    _s, worn_iid, worn_rec = _worn(p, want)
    if worn_iid:
        return T("SYS_GEAR_WORN", name=worn_rec.get("name", worn_iid))
    other, orec = _in_bag(p, want)
    if other:
        return T("SYS_GEAR_NOT_WEARABLE", name=orec.get("name", other))
    return T("SYS_GEAR_IN_BAG", name=want)


# ══════════════════════════════════════════════════════════════
# 一、装备
# ══════════════════════════════════════════════════════════════
async def equip(env, sink, uid, player):
    """`装备 <装备>` —— 背包里的能穿的东西进 `equipped[slot]`；同一位子已有 ⇒ **换下**。

    换下的那件回背包（先说换上了哪件、再说换下了哪件）—— 六格各一件，不叠穿。

    ★ B3-19：先过**属性门槛**（`items.req`：家族 × 品质 × 建议加点曲线）——
      不够 ⇒ 一句「还差几点」，**档上一个字都不动**（fail-closed）。
      已经穿在身上的旧档不受影响：门槛只在**穿**这一条路上判，所以旧档不会因为
      这条新规矩突然「身上那件不合规」（只是脱下来之后要够门槛才穿得回去）。
    """
    p = _p(player)
    want = _arg(env)
    if not want:                       # ★ B4-10：没带东西就照实说
        yield T("SYS_GEAR_EQUIP_ASK")
        return
    iid, rec = _in_bag(p, want, need_slot=True)
    if not iid:
        yield _not_there(p, want)
        return

    short = unmet_req(p, iid)
    if short:
        yield T("SYS_GEAR_REQ", **short)
        return

    slot = str(rec.get("slot"))
    eq = dict(p.get("equipped") or {})
    old = eq.get(slot)
    cap0 = _cap_with(p, dict(eq))
    _take(p, iid, 1)
    if old and old != iid:
        _to_bag(p, old, 1)                  # 换下的先回背包
    eq[slot] = iid
    p["equipped"] = eq
    cap1 = _cap_with(p, eq)
    p = _p(p)                       # ★ 上限/现血只有一个来源（`_p` 按新 equipped 重新派生）
    if player is not None:
        player.update(p)
    _save(env)

    yield T("SYS_GEAR_EQUIP_OK", icon=rec.get("icon", ""), name=rec.get("name", iid),
            kind=rec.get("kind", ""))
    for line in affix_lines(rec):
        yield line
    if old and old != iid:
        yield T("SYS_GEAR_SWAP_OUT", name=_item(old).get("name", old))
    if cap0 is not None and cap1 is not None and int(cap0) != int(cap1):
        yield T("SYS_GEAR_HP_CAP", old=int(cap0), new=int(cap1))


# ══════════════════════════════════════════════════════════════
# 二、卸下
# ══════════════════════════════════════════════════════════════
async def unequip(env, sink, uid, player):
    """`卸下 <部位>` —— 身上的那件回背包（名字 / id / 部位名 / 部位键四种写法都认）。

    空参（或直接敲「卸下」）先报身上穿着什么 —— 六格各一件，摆出来让玩家挑。
    """
    p = _p(player)
    want = _arg(env)
    eq = dict(p.get("equipped") or {})
    if not want:
        if not eq:
            yield T("SYS_GEAR_NAKED")
            return
        yield T("SYS_GEAR_WEARING", list=" · ".join(
            "『%s』" % _item(eq[s]).get("name", eq[s]) for s in sorted(eq)))
        return

    slot, iid, rec = _worn(p, want)
    if not iid:
        yield T("SYS_GEAR_NOT_WORN", name=want)
        return

    cap0 = _cap_with(p, dict(eq))
    eq.pop(slot, None)
    p["equipped"] = eq
    _to_bag(p, iid, 1)
    cap1 = _cap_with(p, eq)
    p = _p(p)                       # ★ 同上：上限/现血按新的 equipped 重新派生
    if player is not None:
        player.update(p)
    _save(env)

    yield T("SYS_GEAR_UNEQUIP_OK", icon=rec.get("icon", ""), name=rec.get("name", iid),
            kind=rec.get("kind", ""))
    if cap0 is not None and cap1 is not None and int(cap0) != int(cap1):
        yield T("SYS_GEAR_HP_CAP", old=int(cap0), new=int(cap1))


# ══════════════════════════════════════════════════════════════
# 三、装备对比
# ══════════════════════════════════════════════════════════════
async def item_compare(env, sink, uid, player):
    """`对比 <物品>` —— 手里这件 vs 同一位子上现在这件，**逐词条说人话**。

    · 数值那半边：只比**不带 note 的数值词条**（面板属性那一类），值走 `gear_stats`
      （所以列出来的就是面板真会动的那几项）；带 note 的是规则，不进数值行（见 `plain_stats`）；
    · 规则那半边：带 `note` 的词条**两边各列一次**（域里那句人话原样带出来）；
    · 收尾给一句计数（更好 N 项 / 更差 N 项 / 一样 N 项）—— **不合成总分**：
      词条之间没有可比权重（那要 PE 尺，属数值口径，不在这一层拍脑袋）。
    """
    p = _p(player)
    want = _arg(env)
    iid, rec = _in_bag(p, want, need_slot=True)
    if not iid:
        yield _not_there(p, want)
        return

    slot = str(rec.get("slot"))
    cur = (p.get("equipped") or {}).get(slot)
    cur_rec = _item(cur) if cur else {}
    yield T("SYS_CMP_HEAD", name=rec.get("name", iid), quality=rec.get("quality", ""),
            kind=rec.get("kind", ""),
            cur=(cur_rec.get("name") if cur else T("SYS_GEAR_SLOT_EMPTY")))
    if not cur:
        yield T("SYS_CMP_EMPTY", kind=rec.get("kind", ""))
        for line in affix_lines(rec):
            yield line
        return

    new, now = stats_of(p, iid), stats_of(p, cur)
    up = down = same = 0
    for stat in sorted(plain_stats(rec) | plain_stats(cur_rec)):
        a, b = float(now.get(stat, 0.0)), float(new.get(stat, 0.0))
        label = stat_label(stat)
        if abs(a - b) < 1e-9:
            same += 1
            yield T("SYS_CMP_ROW_SAME", label=label, value=_fmt(a))
            continue
        d = b - a
        up += 1 if d > 0 else 0
        down += 1 if d < 0 else 0
        yield T("SYS_CMP_ROW", label=label, old=_fmt(a), new=_fmt(b),
                sign=("+" if d > 0 else "-"), delta=_fmt(abs(d)))
    for slot_key, rr in (("SYS_CMP_NOTE_NEW", rec), ("SYS_CMP_NOTE_CUR", cur_rec)):
        for a2 in rr.get("affixes") or []:
            if a2.get("note"):
                yield T(slot_key, note=str(a2["note"]))
    yield T("SYS_CMP_VERDICT", up=up, down=down, same=same)
