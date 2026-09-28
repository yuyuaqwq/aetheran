# -*- coding: utf-8 -*-
"""铺子那几家：货架 · 买价 · 那一站 —— **唯一解析处**（B4-15 · fix7-gear 扩成「几家」）。

为什么单开一个模块（与 `content/town.py` / `content/argv.py` / `content/scene.py` 同一个路子）
------------------------------------------------------------
  · 三处要读同一份口径：`cmds_places.herbalist`（药铺面板）· `cmds_more.item_buy`（购买）
    · `scripts/probe_shop.py`（逐行对账）—— 放下面的模块会被另外两处 import 成环；
  · **代码里没有价、没有 id、没有节点名**：四个品阶系数 + 固定加价在 `content/rules/shop.json`
    （`scripts/rebuild_shop.py` 从真源 `06_…/00_第一阶段内容总纲_v1.md §六` 现解析进来的；
    加价那一格真源没给数 —— 取值理由与出处写在那个脚本的头注里），
    货架由 items 域现取（见下），那一站由 npcs 域的 `funcs` 现取；
  · 只 import 基座 `cmds_ast`（TOWN / _data）与 `content/town.py`，**不被它们 import**
    ⇒ 谁都能用、怎么排 import 都不成环。

★ fix7-gear（2026-09-26 · 第一件装备那条线）：这一层从「药铺一家」扩成「几家」，**一行旧行为都不动**：
```text
默认那一家（不传 key）= 顶层那两格（`stock_kind` = tool · `station_func` = herb）——
  与改前逐字相同（药铺那一路的判据 `probe_shop ③④⑨` 一个锚点都不用换）。
其余几家写在 `rules.shelves.<key>` 里，两种收法（都**从域里现取**，不写死 id）：
  · `stock_kind` = 按条目的 ASCII 机器键收（药铺那一家就是这么收的：`kind_key == tool`）；
  · `shop_key`   = 按条目自己的 `shop` 那一格收（装备那几家：柯尔打的粗货 · 商队到货）。
另外两扇闸（都写在口径表里，代码不写数）：
  · 等级那一刀**声明在货上**：条目自带 `level` 那一格的就按等级卖（真源
    `00_总纲/06_阶段交接指南_v3.md §3.1③`「费用按等级」）—— 买价 = 基础价 × 品阶系数 × 固定加价
    （普通档系数 1.00 + 加价 2 ⇒ 正好是 `12 × level`，凑整）。
    ★ 不传档（`p is None`）而这一家是等级闸 ⇒ **当场抛**（fail-closed：等级猜不出来，不静默全放）。
  · `event` = 这一格挂在哪个世界事件上（商队那一家：`ev_caravan_arrived` ⇒ 车到了才有货）。
    判定口走 `calendar.event_on` 那一个口（与 NPC 在场 / 对话 need 同一处）。
```
"""
from __future__ import annotations

import io
import json
import os

from .cmds_ast import TOWN, _data, _name_of_node
from . import calendar as CAL
from . import loot as LT
from . import town as TW

RULES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules", "shop.json")

_CACHE = None


def rules() -> dict:
    """`content/rules/shop.json`（唯一真源）—— 读一次，进程内复用。"""
    global _CACHE
    if _CACHE is None:
        if not os.path.exists(RULES):
            raise RuntimeError("铺子口径表不在：%s（跑 scripts/rebuild_shop.py）" % RULES)
        with io.open(RULES, encoding="utf-8") as f:
            _CACHE = json.load(f)
        if not isinstance(_CACHE, dict) or not _CACHE.get("quality_mult"):
            raise RuntimeError("铺子口径表形状不对：%s" % RULES)
    return _CACHE


# ══════════════════════════════════════════════════════════════
# 一、几家铺子（口径表里那几格 —— 默认那家 = 顶层那两格，向后兼容）
# ══════════════════════════════════════════════════════════════
def shelf_keys() -> list:
    """除默认那一家之外的几家（口径表 `shelves` 的键，**按表里的顺序**）。"""
    sh = rules().get("shelves") or {}
    return [k for k in sh]


def shelf_rec(key=None) -> dict:
    """某一家的那几格声明；`key=None` = 默认那一家（顶层那两格，不读 `shelves`）。

    ★ 认不出的 key ⇒ 当场抛（fail-closed：不静默退回默认那家 —— 那会「买错柜上的东西」）。
    """
    if key is None:
        r = rules()
        return {"stock_kind": r.get("stock_kind"), "station_func": r.get("station_func"),
                "event": None}
    sh = rules().get("shelves") or {}
    if key not in sh:
        raise RuntimeError("铺子口径表里没有 %r 这一家（有：%s）" % (key, sorted(sh)))
    rec = dict(sh[key] or {})
    if not rec.get("stock_kind") and not rec.get("shop_key"):
        raise RuntimeError("铺子 %r 既没写 `stock_kind` 也没写 `shop_key` —— 收什么货判不了" % key)
    return rec


def station_func(key=None) -> str:
    """这一家那一站的职能键（`npcs.funcs` 里那几个 ASCII 词）；没有这一格 = 不核站。"""
    return str(shelf_rec(key).get("station_func") or "")


def station(key=None, loc: str = TOWN) -> str:
    """这一家那一站（节点 id）—— 叫不准（分在两处 / 一个都没有）就给空串。

    ★ 空串 = **拦**（`town_gate` 的 fail-closed 语义）：不假装自己在柜台上。
    """
    return TW._func_node(station_func(key), loc)


def station_name(key=None, loc: str = TOWN) -> str:
    """那一站**给玩家看**的名字（从 maps 现取，不写死）。"""
    return str(_name_of_node(loc, station(key, loc)) or "")


def shops_here(p, loc: str = TOWN) -> list:
    """脚下这一站有哪几家（**按口径表顺序**）—— 默认那家也一起算。

    ★ 没有 `station_func` 的那几家（商队：铺子与歇脚处没有单独一站 —— 与 `商队` 那条指令
      同一口径「不核那一站」）**不进这个名单**：它们要另判（见 `at_shop`）。
    """
    out = []
    if station(None, loc) and str((p or {}).get("node") or "") == station(None, loc):
        out.append(None)
    for k in shelf_keys():
        node = station(k, loc)
        if node and str((p or {}).get("node") or "") == node:
            out.append(k)
    return out


def stationless() -> list:
    """没有那一站、只靠「在镇上」就要找得着的那几家（今天 = 商队）。"""
    return [k for k in shelf_keys() if not station_func(k)]


# ══════════════════════════════════════════════════════════════
# 二、买价（唯一算法 —— 品阶系数 + 固定加价 + 物价倍数）
# ══════════════════════════════════════════════════════════════
def price_of(rec: dict, p=None, mul=None) -> int:
    """买价 = 基础价 × 品阶系数 × 固定加价 × **物价倍数**（真源 05 §六 + 口径表 + 事件层），取整到 1。

    品阶取条目的 `quality`；没写的一律按「普通」（`quality_default`，口径 §二②）。
    认不出的品阶 ⇒ **当场喊**（fail-closed，不静默当 0 —— K68）。
    ★ P-55：加价那一格（`buy_markup`）真源没给数（05 §六 只给「价 = 基础价 × 品阶系数」）⇒
      台账的倾向是「例：买价 = 收价 × 2」；普通档系数 1.00 ⇒ 正好是「买价 = 收价 × 2」
      （收价 = `items.price`，B3-12 落的那一路，一个字不动）。缺格 / 烂值 = 抛（fail-closed：
      没有它买价就退回等于收价，「低买高卖」那条路又开了）。
    ★ P-16：**物价倍数**接在这一格里 —— 世界事件效果栏 `price_mul`（如 1.2 = 「价格 +20%」，
      真源 21 §二）走事件层的唯一口 `calendar.price_mul`；今天数据里一条都没给 ⇒ 1.0
      （买价与改前逐字相同）。★ `p` 要传（世界级事件看主线进度）；`mul` 传了就用它
      （同一眼货架上的价得用**同一刻**的倍数 —— 由 `goods` / `find` 算一次传下来）。
    ★ 买价**永远 ≥ 收价**：算完再核一遍（口径 / 数据错了当场喊，不静默放一条刷钱的路过去）。
    """
    r = rules()
    mult = r.get("quality_mult") or {}
    mark = r.get("buy_markup")
    if isinstance(mark, bool) or not isinstance(mark, (int, float)) or mark < 1:
        raise RuntimeError("铺子口径表缺「固定加价」或不是 ≥1 的数：%r（%s）" % (mark, RULES))
    q = str((rec or {}).get("quality") or r.get("quality_default") or "")
    if q not in mult:
        raise RuntimeError("品阶 %r 不在铺子口径表里（%s）" % (q, sorted(mult)))
    base = float((rec or {}).get("price") or 0)
    pm = CAL.price_mul(p=p) if mul is None else float(mul)
    gold = int(round(base * float(mult[q]) * float(mark) * pm))
    if gold < int(base):
        raise RuntimeError("买价 %d 比收价 %d 还低 —— 铺子被刷了（口径 / 数据 / 物价倍数错了）"
                           % (gold, int(base)))
    return gold


def sell_price_of(rec: dict) -> int:
    """★ P3 BUG-4（本波 f4）：**铺子收一件东西给多少** —— 唯一一口（『卖出』与『旧货』都走它）。

    三档，fail-closed：
      · 域里写了 `price`（> 0）⇒ **就是它**（B3-12 落的那一路，一个字不动）；
      · 域里没写价、但**是装备**（有域里那个 `slot` —— 六格 ASCII）⇒ 按 `sell_gear` 现算：
        基础价（品阶）× 等级档（`items.req.level`，读口 = `loot._req_level`，不另取一格）；
      · 其余（信物 / 线索 / 没价的东西）⇒ **0** = 不收（调用方回 `SYS_SELL_NOPRICE`）。

    病根（P3 BUG-4 · 玩出来的真话）：`拾荒者的短刃` 这类**掉出来的装备**域里一个价都没有
    ⇒ 收价恒 0 ⇒ 铺子永远回「这东西没价」，打到的多余装备只能占背包（实测三把同名剑）。
    ★ 与真源的关系：`05 §七` 写的是「钱从哪来：悬赏 + 卖材料 + 卖旧物（**不靠卖装备**）」——
    那是**取向**（装备不是钱的来源），不是「装备不能卖」；本表的取值就照那条取向取**小价**
    （见 `sell_gear` 的 `_src`，另登记为真源待补行 · 本分支 `_notes.md`）。
    """
    r = rules()
    # ★ 死参数 `iid` 已删（审计 L1484）：全仓 14 处调用点**无一**传它
    #   （cmds_more:352 · cmds_places:267 · probe_cmds 2 · probe_fix4_combat 5 ·
    #   rebuild_shop 注释），原先那个 `rec = rec or LT.rec_of(str(iid))` 分支
    #   是**零可达**的死路 —— 留着它只让人以为「可以只给 id 问价」。
    base = (rec or {}).get("price")
    if isinstance(base, (int, float)) and not isinstance(base, bool) and base > 0:
        return int(base)
    g = r.get("sell_gear")
    if not isinstance(g, dict):
        raise RuntimeError("铺子口径表缺 `sell_gear` 那一块：%s（跑 scripts/rebuild_shop.py）" % RULES)
    if not str((rec or {}).get(str(g.get("slot_field") or "")) or ""):
        return 0                                     # 不是装备 ⇒ 不收（不编一口价出来）
    q = str((rec or {}).get("quality") or r.get("quality_default") or "")
    by_q = g.get("base_by_quality") or {}
    if q not in by_q:
        raise RuntimeError("品阶 %r 不在收价表里（%s）" % (q, sorted(by_q)))
    lv = LT._req_level(rec or {})                    # 等级那一格：唯一读口（P-60）
    mul = None
    for band in (g.get("level_mult_by_band") or []):
        if int(band.get("min_lv") or 0) <= lv <= int(band.get("max_lv") or 0):
            mul = float(band.get("mul") or 0)
            break
    if mul is None:
        raise RuntimeError("等级 %d 不在收价表的档里（%s）" % (lv, g.get("level_mult_by_band")))
    return max(1, int(round(float(by_q[q]) * mul)))


# ══════════════════════════════════════════════════════════════
# 三、货架（几个口：默认那家 · 某一家 · 找遍几家）
# ══════════════════════════════════════════════════════════════
def level_need(rec) -> int:
    """这件货**从几级起卖**（条目自带 `level`）；没写 = 0（不上等级闸）。"""
    v = (rec or {}).get("level")
    if v is None:
        return 0
    if isinstance(v, bool) or not isinstance(v, int) or v < 1:
        raise RuntimeError("条目 %r 的 `level` 坏了：%r（等级闸判不了 —— fail-closed）"
                           % ((rec or {}).get("name"), v))
    return int(v)


def can_sell(rec: dict, key=None, p=None) -> bool:
    """这一家收不收这件货（**只看收不收，不看等级**）。

    · `stock_kind` 那一路：条目的 `kind_key` 对得上、而且**有价**（口径 §二①：柜上的东西有价）；
    · `shop_key` 那一路：条目自己的 `shop` 那一格 == 这一家的键；
          （同样**要有价**；两条收法都走 `_stock_rule` 那一个口，不各保一份）
    · 挂在事件上的那一家：事件不成立 ⇒ 这件货**不在柜上**（商队那一家）。
    """
    if not isinstance(rec, dict):
        return False
    sp = shelf_rec(key)
    if not _stock_rule(rec, sp):
        return False
    ev = str(sp.get("event") or "")
    if ev and p is not None and not CAL.event_on(ev, p=p):
        return False
    return True


def _gate_level(key, p, rec) -> bool:
    """等级闸 —— **声明在货上**：条目自带 `level` 那一格的就按等级卖（口径表不必再写一格）。

    这一件有等级、而档没传 ⇒ 当场抛（不猜等级，fail-closed —— 猜出来的等级会让「越级」静默放行）。
    """
    lv = level_need(rec)
    if not lv:
        return True
    if p is None:
        raise RuntimeError("这一件（%s · %s）按等级卖，可 `p` 没传 —— 等级猜不出来（铺子 %r）"
                           % (rec.get("name"), level_need(rec), key))
    return int((p or {}).get("level") or 0) >= lv


def _rows(key, p, gate=True) -> list:
    """这一家柜上摆着的那些（**现算**）—— `[{"id","rec","gold"}, …]`（按 items 域自己的顺序）。

    `gate=False` = **不摆等级那一刀**（`goods_at` 要用它说「你几级才卖你」—— 话得说得出，
    东西仍然不给：给货那一步在 `item_buy` 里另判）。
    """
    pm = CAL.price_mul(p=p)
    out = []
    for iid, rec in (_data("items") or {}).items():
        if str(iid).startswith("_") or not isinstance(rec, dict):
            continue
        if not can_sell(rec, key, p):
            continue
        if gate and not _gate_level(key, p, rec):
            continue
        out.append({"id": iid, "rec": rec, "gold": price_of(rec, mul=pm)})
    return out


def goods(p=None, shelf=None) -> list:
    """柜上有什么 —— `[{"id", "rec", "gold"}, …]`（按 items 域自己的顺序，不重排）。

    货架 = 域里 `kind_key == stock_kind`（默认那家）或 `shop == shop_key`（其余几家）的那些（口径 §二①）；
    带 `level` 的那几件，**不够级的不摆出来**（见模块头注）。
    `gold` = 买价（基础价 × 品阶系数 × 固定加价 × 物价倍数 —— 与『购买』扣的是同一个数）。
    ★ P-16：物价倍数**算一次**传下去（同一眼货架上的价必须是同一刻的；`p` 要传 ——
      世界级事件看主线；不传 = 按「没有世界级事件」算，调用方别这么干）。
    """
    return _rows(shelf, p)


def goods_at(shelf, p=None) -> list:
    """这一家柜上**全部**的货（含**你还不到级**的那几件）—— 用来把「几级才卖你」说出口。

    ★ 只给**说**用：真给货那一步在 `item_buy`（按等级另判，不够级拿不走）。
    """
    return _rows(shelf, p, gate=False)


def find(name, p=None, shelf=None) -> tuple:
    """柜上按名字 / id 找一件 —— `(id, rec, gold, cands)`；找不到 `(None, {}, 0, [])`。

    ★ B4-20：比法走**全包唯一的一口** `loot.match_ids`（原先这里自己写了一份「遍历序里
      第一个命中的就算」）。`cands` 非空 = 柜上有**好几件同一个名字** ⇒ 调用方照实说，
      不替玩家挑（今天柜上那两件名字不重，但这一格归了口就不会再各自跑偏）。
    ★ P-16：`p` 一路传给 `goods`（物价倍数按这一档的事件算 —— 与面板同一眼同一个价）。
    """
    hits = LT.match_ids([g["id"] for g in _rows(shelf, p)], name)
    if len(hits) > 1:
        return (None, {}, 0, sorted(hits))
    if not hits:
        return (None, {}, 0, [])
    g = next(x for x in _rows(shelf, p) if x["id"] == hits[0])
    return (g["id"], g["rec"], g["gold"], [])


def where(name, p=None) -> dict | None:
    """点名的这件在**哪一家的柜上**、够不够级、车来了没有 —— `{key,iid,rec,level,gold,why}`。

    `why`（取不出 = 空串）三种：
      · ``level``  —— 找到这件、但**等级不够**（点名买不到的那一句）
      · ``event``  —— 找到这件、可它挂的事还没发生（商队那一家：车没到）
      · ``away``   —— 找到这件、在**另外一家**的柜上（指路）
    ★ 找的顺序 = 默认那家在前，其余按口径表顺序（**确定**的：同一件货在两家柜上时，
      以先找着的那家为准；今天没有一件同时在两家柜上 —— `probe_gear_starter ⑫` 钉着）。
    """
    keys = [None] + shelf_keys()
    hit = None
    for k in keys:
        iid = LT.match_ids([i for i, r in (_data("items") or {}).items()
                            if isinstance(r, dict) and not str(i).startswith("_")
                            and _on_any_shelf_rule(r, k)], name)
        if not iid:
            continue
        iid = sorted(iid)[0]
        rec = (_data("items") or {}).get(iid) or {}
        sp = shelf_rec(k)
        ev = str(sp.get("event") or "")
        why = ""
        if ev and p is not None and not CAL.event_on(ev, p=p):
            why = "event"
        elif not _gate_level(k, p, rec):
            why = "level"
        hit = {"key": k, "iid": iid, "rec": rec,
               "level": level_need(rec), "why": why,
               "gold": price_of(rec, p=p) if rec.get("price") else 0}
        break
    if hit is None:
        return None
    if not hit["why"] and hit["key"] not in shops_here(p) + stationless():
        hit["why"] = "away"
    return hit


def event_wait(key) -> str:
    """这一家挂的那件事**在等哪条委托**（`period.from_main` / `until_main` 那一格的委托名）。

    取不出（没挂事件 / 那一格没写 / 委托名查不到）⇒ 空串 —— 调用方照实说「车没来」，
    **不编一个条件**（fail-closed：编条件 = 骗玩家）。
    """
    ev = str(shelf_rec(key).get("event") or "")
    if not ev:
        return ""
    per = (CAL.event(ev) or {}).get("period") or {}
    qid = str(per.get("from_main") or per.get("until_main") or "")
    if not qid:
        return ""
    return str(((_data("quests") or {}).get(qid) or {}).get("name") or "")


def _stock_rule(rec: dict, sp: dict) -> bool:
    """货**归不归这一家收** —— 「收法」的唯一判定口（台账 L1481 单源化）。

    两家两种收法，**两条都要有价**（口径 §二①：柜上的东西有价）：

    * `stock_kind` 那一家：按条目的 ASCII 机器键收；
    * `shop_key`   那几家：按条目自己的 `shop` 那一格收。

    改前 `shop_key` 那一路**漏了有价判定**，与同模块 `stock_kind` 那一路口径不对称
    （实测：造一件 `shop="smith"` 而无 `price` 的货 → 改前 `can_sell` 判 True 收下，
    同一模块 `kind_key` 路判 False 拒收；域里今天 0 件这样的货，改数据即漏网）。
    等级闸与事件闸不在这里 —— 它们是另外两扇门（`_gate_level` 是抛、事件不成立即不在柜上）。
    """
    sk = sp.get("stock_kind")
    if sk:
        return rec.get("kind_key") == sk and bool(rec.get("price"))
    return rec.get("shop") == sp.get("shop_key") and bool(rec.get("price"))


def _on_any_shelf_rule(rec, key) -> bool:
    """这件货**归不归这一家的收法**（不看等级 / 不看事件 —— `where` 要用它说出「为什么」）。"""
    return _stock_rule(rec, shelf_rec(key))
