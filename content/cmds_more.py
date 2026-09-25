# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 第七组：单子详情 / 属性 / 物品 / 箱子 / 成就（B3-12）

这一批接的是「声明了、包内还没实现」里**不需要新形状**的那几条 —— 各自只读已有的域
（`quests` / `items` / `classes` / `npcs` / `titles` / `codex` / `eggs` / `commands`）
与档上既有的账。要新造一个域才能做的（评级阶梯 · 铺子存货 · 仓库之外的容器 …）留在
`_notes.md` 当遗留，不在这儿硬凑。

八条
----
  看 <编号>                 单子全文（抬头 / 委托人 / 要做什么 / 报酬 / 前置 / 能不能接）—— `board_show`
  属性                      面板与加点明细（职业基础 + 等级成长 + 加点 + 装备 · 现算）—— `attrs`
  查看 <物品>               一件东西的详情（分类 / 词条 / 说明 / 收价）—— `item_show`
  丢弃 <物品> [数量]        扔掉（真掉 —— 背包里减）—— `item_drop`
  卖出 <物品> [数量]        卖给铺子（价 = 域里的基础价，不手打）—— `item_sell`
  整理背包                  按类归好（**真重排**背包的键序）—— `bag_sort`
  存放 / 取出 <物品> [数量]  客栈后院那只旧木箱 —— `stash`
  成就                      本地成就一览（称号 / 彩蛋 / 四本谱 / 交付）—— `achievements`

三条纪律（同包内各处）
--------------------
  · 文案一律走 texts（本文件 0 条内联中文 —— probe_copy ① 逐文件数）
  · 数值一律从域 / 面板现算（不手打）
  · 落档只经 `player.update(p)` + `_save(env)`；出档一律 `_p()`（默认档不当草稿纸，K57）

取参：`content/argv.py` —— 全包**一个口**（B4-10）
----------------------------------------------
参怎么切跟着**声明自己的 patterns** 走（`arg_of(env)` 用 `env.key` 找那一条）——
`^存放\\s*(.+)$` 这种「词与参数之间不要求空白」的写法，`split()` 那一套会把「存放铁屑」取空。
★ 方向的真源是声明自己的 `usage`（`存放 <参数>` 那句的第一个词）：命中词是它的**子串**
  （`存` ⊆ `存放`）⇒ 同一个方向；否则是反方向。代码里一个中文都不写（中文是数据）。
"""
from __future__ import annotations

from .cmds_ast import _data, _p, _save, T, name_with_title, _cls_label
from .town import _func_node, town_gate
from . import argv as AV
from .cmds_quest import _done, _mine, _quests, _shadow, _unmet
from .cmds_recipe import _have, _take
from .cmds_gear import affix_lines, ambig_line, stat_label
from . import alloc as ALLOC
from . import codex as CX
from . import eggs as EG
from . import gear as GB
from . import loot as LT
from . import panel_build as PB
from . import titles as TT
from . import shop as SH

#: 声明表的唯一读口 = `content/argv.py`（取参 / 给玩家看的那几个词都在声明里，代码不另抄一份）

#: 客栈：`存放 / 取出` 的守卫是「在客栈」（`03_风车镇_指令与回复` 一）—— 风车镇那个节点
STASH_NODE = "wt_inn"

#: 面板（引擎键）→ 属性名槽位后缀。只列**面板上真有**的那些；键在域里、槽位在 texts 里。
#: ⚠ 引擎键与槽位名不是一一对应：抗性那一格引擎叫 `mdef`、槽位是 `SYS_STAT_RES`（见 `panel_build.KEYMAP`）。
PANEL_ROWS = (
    ("atk", "ATK"), ("matk", "MATK"), ("def", "DEF"), ("mdef", "RES"),
    ("spd", "SPD"), ("hit", "HIT"), ("dodge", "EVA"), ("block", "BLOCK"),
    ("heal_pow", "HEAL_POW"),
)



def _split_n(arg: str):
    """`铁屑 3` → `("铁屑", 3)`；不写数字就是 1 份（数量只认末尾那个纯数字）。"""
    parts = str(arg or "").split()
    if len(parts) >= 2 and parts[-1].isdigit():
        return (" ".join(parts[:-1]).strip(), max(1, int(parts[-1])))
    return (" ".join(parts).strip(), 1)


def _bag_hit(p, want):
    """背包里按名字 / id 找一件 —— **转发到全包唯一的一口** `loot.pick`（B4-20）。

    走 `loot.rec_of`（未鉴定的名字挂在**池**上，物品表里没有它）。返回三元组：`cands` 非空
    = 这名字在背包里对着好几件 ⇒ 调用方走 `ambig_line` 照实说。
    """
    return LT.pick(sorted(p.get("bag") or {}), want)


def _fmt(v) -> str:
    """面板上的数：整数不带小数点（14.0 → 14），小数留一位（14.36 → 14.4）。"""
    f = float(v)
    return "%d" % int(f) if f.is_integer() else "%.1f" % f


def _panel_rows(actor: dict) -> list:
    """面板 → 要出的那几行（值全从 actor 来；键缺席就不出那一行）。"""
    out = []
    for key, slot in PANEL_ROWS:
        if key in actor:
            out.append(T("SYS_ATTR_ROW", label=T("SYS_STAT_%s" % slot), value=_fmt(actor[key])))
    return out


def _crit_rate(actor: dict) -> float:
    """暴击**率** —— 从面板栈那条 `crit_rate` 层现读（F3 的换算在 `panel_build.build_actor`）。

    ★ 为什么不读 `actor["crit"]`：`crit` 是**非线性率**，内容侧按 F3 算好后用 `set` 层一次性写入
      （见 `panel_build` 那段注释）—— `actor` 里那一格只是各层相加的中间值，不是率。引擎读的是
      栈里那一层 ⇒ 这里也读它（同一个真源，不另算一遍）。
    """
    decl = PB.stacks().get(str(actor.get("panel_stack") or "")) or {}
    for layer in decl.get("layers") or []:
        if layer.get("id") == "crit_rate":
            return float((layer.get("values") or {}).get("crit") or 0.0)
    return 0.0


# ══════════════════════════════════════════════════════════════
# 一、公会与委托：看 <编号>
# ══════════════════════════════════════════════════════════════
async def board_show(env, sink, uid, player):
    """`看 <编号>` —— 挂板墙上一张单子的全文。

    ★ 编号 = `quests` 域那条的 `order`（主线 1–12 · 支线 13–30 · 生活 31–38 · 悬赏 101–103），
      与『接 <编号>』认的是同一个字段 —— 不另建一套编号。
    ★ 「还差什么」走 P-25 的同一口（`cmds_quest._unmet`）：条件判定的真源只有一处。
    ★ 守卫（声明里的 `guard_desc` = 在公会）走**唯一执行面** `cmds_ast.town_gate`（B4-12）：
      这里原先写着「不设地点守卫 …… 包内没有守卫执行面」—— 那句话是错的（客栈 / 教堂 / 登记
      一直都在判脚下）⇒ 同一条 `guard_desc` 两种实现的根就在这句里，已收口。
    """
    p = _p(player)
    line = town_gate(p, _func_node("board"))
    if line:
        yield line
        return
    want, _n = _split_n(AV.arg_of(env, "board_show"))
    qs = _quests()
    hit = None
    for k in sorted(qs, key=lambda kk: (qs[kk].get("order") or 0, kk)):
        if str(qs[k].get("order")) == want:
            hit = (k, qs[k])
            break
    if hit is None:
        yield T("SYS_JOB_NOSUCH", name=want)
        return
    k, x = hit
    yield T("SYS_BSHOW_HEAD", order=x.get("order"), name=x.get("name"),
            level=x.get("min_level"))
    giver = (_data("npcs").get(str(x.get("giver") or "")) or {}).get("name")
    if giver:
        yield T("SYS_BSHOW_GIVER", giver=giver)
    yield T("SYS_BOARD_TODO", objective=x.get("objective"))
    if x.get("insight"):
        yield T("SYS_JOB_INSIGHT", insight=x["insight"])
    yield T("SYS_BSHOW_REWARD", exp=x.get("reward_exp"), gold=x.get("reward_gold"))
    for line in _unmet(p, x):
        yield "  " + line
    if k in _done(p):
        yield T("SYS_TRADE_MARK_DONE")
    elif k in _mine(p):
        yield T("SYS_BOARD_ACTIVE")
        yield T("SYS_BOARD_DELIVER", order=x.get("order"))
    else:
        yield T("SYS_BOARD_NEXT", order=x.get("order"))


# ══════════════════════════════════════════════════════════════
# 二、角色：属性
# ══════════════════════════════════════════════════════════════
async def attrs(env, sink, uid, player):
    """`属性` —— 五维加点的分布 + 二级属性明细。

    ★ 面板**现算**：走 `panel_build.build_actor`（职业基础 + 等级成长 + 加点 + 装备 + 增益），
      与战斗 / 生命上限吃的是同一份 —— 不另算一遍（`03_全流程数值主干 §三` 那六张锚点表）。
    ★ 五维的**绝对值**今天取不到（建号那一步还没落地，「五维起始值」真源里没有）——
      所以这一页说的是**加过哪些点**，不编一个起点出来（见 `_notes.md`）。
    """
    p = _p(player)
    cls = str(p.get("cls") or "").strip()
    if not cls:
        yield T("SYS_ATTR_NOCLS")
        return
    gear, buffs = PB.gear_and_buffs(p)                 # ★ 与面板 / 战斗同一个取值口
    actor = PB.build_actor(cls, max(1, int(p.get("level") or 1)), ALLOC.of_record(p),
                           gear, buffs=buffs, uid=uid)  # ★ B3-28 ①：栈 id 带上这个人
    yield T("SYS_ATTR_HEAD", who=name_with_title(p), cls=_cls_label(cls), level=p.get("level"))
    yield T("SYS_ATTR_VITAL", hp=_fmt(actor.get("max_hp", 0)), mo=_fmt(actor.get("max_mp", 0)),
            crit=_fmt(_crit_rate(actor) * 100))
    for line in _panel_rows(actor):
        yield line
    al = ALLOC.of_record(p)                            # ★ P-34：这一档实际分了多少（唯一口）
    if al:
        yield T("SYS_ATTR_ALLOC",
                list=" · ".join("%s %d" % (stat_label(k), int(v)) for k, v in sorted(al.items())),
                n=ALLOC.spent_of_record(p))
    else:
        yield T("SYS_ATTR_NOALLOC")
    # ★ P-34：还剩几点 —— 甲案（玩家自己加点）下这一行是"点数真的在手里"的唯一提示；
    #   投满了就不出（不占屏）。
    _left = ALLOC.left_of_record(p)
    if _left > 0:
        yield T("SYS_ATTR_LEFT", left=_left, usage=AV.usage("alloc"))
    eq = [LT.rec_of(iid).get("name") or iid for iid in (p.get("equipped") or {}).values()]
    yield T("SYS_ATTR_GEAR", list=" · ".join(eq)) if eq else T("SYS_ATTR_NOGEAR")
    yield T("SYS_ATTR_NOTE")


# ══════════════════════════════════════════════════════════════
# 三、背包：查看 / 丢弃 / 卖出 / 整理
# ══════════════════════════════════════════════════════════════
async def item_show(env, sink, uid, player):
    """`查看 <物品>` —— 一件东西摊开来看（分类 · 词条 · 说明 · 收价）。

    ★ 词条那一支走 `cmds_gear.affix_lines`（装备面板用的同一个口）—— 不另写一份「+N」的拼法。
    """
    p = _p(player)
    want, _n = _split_n(AV.arg_of(env, "item_show"))
    if not want:
        # ★ B4-13：裸「查看」—— 照实说「没带东西」（原先拿空名字查表 ⇒ 「背包里没有『』。」）
        yield T("SYS_ITEM_SHOW_ASK")
        return
    iid, rec, cands = _bag_hit(p, want)
    if not iid:
        if cands:                      # ★ B4-20：同名好几件 ⇒ 照实说，不替玩家挑
            yield ambig_line("item_show", want, cands)
        else:
            yield T("SYS_GEAR_IN_BAG", name=want)
        return
    detail = str(rec.get("kind") or "")
    if rec.get("quality"):
        detail = "%s · %s" % (detail, rec.get("quality"))
    yield T("SYS_ITEM_HEAD", name=rec.get("name") or iid, icon=rec.get("icon") or "",
            detail=detail, n=int((p.get("bag") or {}).get(iid) or 0))
    for line in affix_lines(rec):
        yield line
    if rec.get("desc"):
        yield T("SYS_ITEM_DESC", desc=rec.get("desc"))
    if rec.get("lore"):
        yield T("SYS_ITEM_LORE", lore=rec.get("lore"))
    fd = rec.get("food")
    if isinstance(fd, dict) and fd:
        yield T("SYS_ITEM_FOOD",
                buff="%s +%d%%" % (stat_label(fd.get("stat")), int(fd.get("pct") or 0)),
                minutes=int(fd.get("seconds") or 0) // 60)
    eff = rec.get("effect")
    if isinstance(eff, dict) and eff:
        if eff.get("hp"):
            yield T("SYS_ITEM_HEAL", hp=int(eff.get("hp") or 0))
        if eff.get("hp_pct"):
            yield T("SYS_ITEM_HEAL_PCT", pct=int(round(float(eff.get("hp_pct") or 0) * 100)))
    price = rec.get("price")
    if isinstance(price, (int, float)) and not isinstance(price, bool) and price > 0:
        yield T("SYS_ITEM_PRICE", gold=int(price))


async def item_drop(env, sink, uid, player):
    """`丢弃 <物品> [数量]` —— 真掉（背包里减；减到 0 那条就没了）。

    ★ 数量缺省 1；写了数字就按数字（多过手里的按手里的算 —— 与 `_take` 同一口径）。
    """
    p = _p(player)
    name, n = _split_n(AV.arg_of(env, "item_drop"))
    if not name:                       # ★ B4-10：没带东西就照实说
        yield T("SYS_DROP_ASK")
        return
    _hits = LT.match_ids(sorted(p.get("bag") or {}), name)
    if len(_hits) > 1:                 # ★ B4-20：同名好几件 ⇒ 照实说，不替玩家挑
        yield ambig_line("item_drop", name, _hits)
        return
    iid, rec = (_hits[0], LT.rec_of(_hits[0])) if _hits else (None, {})
    have = int((p.get("bag") or {}).get(iid) or 0) if iid else 0
    if not iid or have <= 0:
        yield T("SYS_GEAR_IN_BAG", name=name)
        return
    n = min(int(n), have)
    _take(p, iid, n)
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_DROP_OK", icon=rec.get("icon") or "", name=rec.get("name") or iid, n=n)
    left = int((p.get("bag") or {}).get(iid) or 0)
    if left:
        yield T("SYS_DROP_LEFT", n=left)


async def item_sell(env, sink, uid, player):
    """`卖出 <物品> [数量]` —— 卖给铺子。

    ★ 价 = `items` 域里的 `price`（**基础价**，域里的数，不手打）。域里没写价的收不了
      （拿在手上的东西 —— `05 §七`「钱从哪来：悬赏 + 卖材料 + 卖旧物，**不靠卖装备**」）。
    ★ 铺子在镇上（`05 §六`「铺子：镇上 3 家」）—— 在野外卖不了，这里照实说一句。
    """
    p = _p(player)
    name, n = _split_n(AV.arg_of(env, "item_sell"))
    if not name:                       # ★ B4-10：没带东西就照实说
        yield T("SYS_SELL_ASK")
        return
    _hits = LT.match_ids(sorted(p.get("bag") or {}), name)
    if len(_hits) > 1:                 # ★ B4-20：同名好几件 ⇒ 照实说，不替玩家挑
        yield ambig_line("item_sell", name, _hits)
        return
    iid, rec = (_hits[0], LT.rec_of(_hits[0])) if _hits else (None, {})
    have = int((p.get("bag") or {}).get(iid) or 0) if iid else 0
    if not iid or have <= 0:
        yield T("SYS_GEAR_IN_BAG", name=name)
        return
    price = rec.get("price")
    if not isinstance(price, (int, float)) or isinstance(price, bool) or price <= 0:
        yield T("SYS_SELL_NOPRICE", name=rec.get("name") or iid)
        return
    line = town_gate(p, notown="SYS_SELL_AWAY")     # ★ B4-12：守卫走唯一执行面（用这一族自己的话）
    if line:
        yield line
        return
    n = min(int(n), have)
    gold = int(price) * n
    _take(p, iid, n)
    p["gold"] = int(p.get("gold") or 0) + gold
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_SELL_OK", icon=rec.get("icon") or "", name=rec.get("name") or iid,
            n=n, gold=gold)


async def item_buy(env, sink, uid, player):
    """`购买 <物品> [数量]` —— 在药铺柜上买（B4-15）。

    守卫（声明 `guard_desc` =「在铺子且钱够」）分两半：
      · 地点走唯一执行面 `town_gate` —— 那一站从 `content/shop.py::station()` 现取
        （npcs 域里带 `herb` 的那个人所在节点；叫不准就拦，不猜）
      · 钱在下面按**现算价**判 —— 不够只回一句，**档一个字不动**（不扣钱、不给货）
    ★ 价与货架全从 `content/shop.py` 来（基础价 × 品阶系数 —— 真源 05 §六 / 00 §六）：
      本文件不写价、不写 id、不写节点名。
    ★ 「柜上没有」与「背包里没有」是两句不同的话（K69 同族）—— 买走的是**柜上**那件，
      与包里有没有同名东西无关。
    """
    p = _p(player)
    line = town_gate(p, SH.station(), away="SYS_SHOP_AWAY")
    if line:
        yield line
        return
    name, n = _split_n(AV.arg_of(env, "item_buy"))
    if not name:                                   # ★ B4-10：没带东西就照实说
        yield T("SYS_SHOP_ASK")
        return
    iid, rec, gold, cands = SH.find(name)
    if not iid:
        if cands:                      # ★ B4-20：柜上同名好几件 ⇒ 照实说，不替玩家挑
            yield ambig_line("item_buy", name, cands)
        else:
            yield T("SYS_SHOP_NOGOOD", name=name)
        return
    total = int(gold) * int(n)
    have = int(p.get("gold") or 0)
    if total > have:
        yield T("SYS_SHOP_POOR", lack=total - have)
        return
    p["gold"] = have - total
    bag = dict(p.get("bag") or {})
    bag[iid] = int(bag.get(iid) or 0) + int(n)
    p["bag"] = bag
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_SHOP_BUY_OK", icon=rec.get("icon") or "", name=rec.get("name") or iid,
            n=int(n), gold=total, left=int(p["gold"]))


async def bag_sort(env, sink, uid, player):
    """`整理背包` —— 按类归好，**真重排**背包的键序（『背包』以后照这个顺序列）。

    ★ 分类键 = `loot.kind_key_of` 的 ASCII 机器键（`weapon` / `material` …），组内按名字排 ——
      组序只按机器键定，代码里一个中文类名都不写；中文分类名从**域里透传**（那件东西自己的 `kind`）。
    ★ 东西一件不少：只重排键序，数量与集合逐字不变（判据：probe_cmds 的『整理背包』那一节）。
    """
    p = _p(player)
    bag = dict(p.get("bag") or {})
    if not bag:
        yield T("SYS_BAG_EMPTY")
        return
    groups: dict = {}
    for iid in bag:
        groups.setdefault(LT.kind_key_of(iid), []).append(iid)
    for kk in groups:
        groups[kk].sort(key=lambda i: (str(LT.rec_of(i).get("name") or ""), i))
    order = sorted(groups)
    p["bag"] = {iid: bag[iid] for kk in order for iid in groups[kk]}
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_SORT_HEAD", n=len(p["bag"]))
    for kk in order:
        ids = groups[kk]
        rec0 = LT.rec_of(ids[0])
        yield T("SYS_SORT_ROW", kind=rec0.get("kind") or kk, n=len(ids),
                list=" · ".join("%s ×%d" % (LT.label_of(i), bag[i]) for i in ids))
    yield T("SYS_SORT_TAIL")


# ══════════════════════════════════════════════════════════════
# 四、客栈那只旧木箱（存放 / 取出）
# ══════════════════════════════════════════════════════════════
def _box(p) -> dict:
    """仓库（`flags.stash`）—— 形状与背包同：`{物品 id: 份数}`。"""
    v = (p.get("flags") or {}).get("stash")
    return dict(v) if isinstance(v, dict) else {}


def _set_box(p, box: dict) -> None:
    f = dict(p.get("flags") or {})
    if box:
        f["stash"] = box
    else:
        f.pop("stash", None)                     # 空的就摘掉那一格（不留空容器）
    p["flags"] = f


def _move(src: dict, dst: dict, iid: str, n: int) -> int:
    """从一份计数表搬到另一份（减到 0 就摘掉条目）；返回真搬了几件。"""
    have = int(src.get(iid) or 0)
    n = max(0, min(int(n), have))
    if n <= 0:
        return 0
    left = have - n
    if left:
        src[iid] = left
    else:
        src.pop(iid, None)
    dst[iid] = int(dst.get(iid) or 0) + n
    return n


async def stash(env, sink, uid, player):
    """`存放 <物品> [数量]` / `取出 <物品> [数量]` —— 客栈后院那只旧木箱。

    ★ 方向取自**声明自己**：`usage`（`存放 <参数>`）的第一个词就是「放进去」那一向，
      命中的 pattern 前缀是它的子串（`存` ⊆ `存放`）⇒ 同一向；否则是取出来那一向。
      ⇒ 代码里不写中文，也不靠 pattern 的先后位置（改声明顺序这一支照样对）。
    ★ 守卫「在客栈」（`03 §一`）：不在那站就说一句实话，不动档。
    """
    p = _p(player)
    raw = (getattr(env, "text", "") or "").strip()
    line = town_gate(p, STASH_NODE, notown="SYS_STASH_AWAY", away="SYS_STASH_AWAY")
    if line:
        yield line
        return
    hit = AV.hit_prefix("stash", raw)
    into = bool(hit) and hit in AV.usage("stash")
    name, n = _split_n(raw[len(hit):].strip() if hit else "")
    if not name:
        yield T("SYS_STASH_ASK")
        return
    box = _box(p)
    if into:
        iid, rec, cands = _bag_hit(p, name)
        if not iid:
            if cands:                  # ★ B4-20：同名好几件 ⇒ 照实说，不替玩家挑
                yield ambig_line("stash", name, cands)
            else:
                yield T("SYS_STASH_NONE", name=name)
            return
        bag = dict(p.get("bag") or {})
        move = _move(bag, box, iid, n)
        p["bag"] = bag
        _set_box(p, box)
        if player is not None:
            player.update(p)
        _save(env)
        yield T("SYS_STASH_IN_OK", icon=rec.get("icon") or "", name=rec.get("name") or iid,
                n=move, have=int(box.get(iid) or 0))
        return
    if not box:
        yield T("SYS_STASH_EMPTY")
        return
    iid, _rec, cands = LT.pick(sorted(box), name)      # ★ B4-20：箱子这一边也归同一个口
    if not iid:
        if cands:                      # ★ B4-20：同名好几件 ⇒ 照实说，不替玩家挑
            yield ambig_line("stash", name, cands)
        else:
            yield T("SYS_STASH_MISS", name=name)
        return
    rec = LT.rec_of(iid)
    bag = dict(p.get("bag") or {})
    move = _move(box, bag, iid, n)
    p["bag"] = bag
    _set_box(p, box)
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_STASH_OUT_OK", icon=rec.get("icon") or "", name=rec.get("name") or iid,
            n=move, have=int(bag.get(iid) or 0))


# ══════════════════════════════════════════════════════════════
# 五、成就（第一阶段的本地账）
# ══════════════════════════════════════════════════════════════
async def achievements(env, sink, uid, player):
    """`成就` —— 现在能记的都在这儿（称号 · 彩蛋 · 四本谱 · 交付）。

    ★ 第一阶段**没有** achievements 域（那是 P2 的系统，`20 §五` / `05_系统总表`）——
      这一页只说**已经在档上记着的那几本账**，数全部现读（不新建容器、不另存一份）。
    ★ 读 `codex` 那几本走**影子档**（`cmds_quest._shadow`）：读口会把缺的格子补齐，
      在真档上调它等于「看一眼成就」就往玩家档里塞空容器（K57 那族）。
    """
    p = _p(player)
    s = _shadow(p)
    yield T("SYS_ACH_HEAD")
    yield T("SYS_ACH_ROW", name=AV.usage("titles"), n=TT.count(s), total=TT.total())
    yield T("SYS_ACH_ROW", name=AV.usage("eggs"), n=EG.count(s), total=EG.total())
    tgt = CX.targets()
    for bk in CX.BOOKS:
        n = CX.count(s, bk)
        total = int(tgt.get(bk) or 0)
        # ★ 没有「记满」那一档的册子（旧物谱：问号本身就是钩子，`codex.targets` 里就没有它）
        #   不许写成「0/0」—— 换一条只报已记条数的行。
        yield (T("SYS_ACH_ROW", name=CX.label(bk), n=n, total=total) if total > 0
               else T("SYS_ACH_ROW_OPEN", name=CX.label(bk), n=n))
    yield T("SYS_ACH_QUEST", n=len(_done(s)))
    yield T("SYS_ACH_TAIL")
