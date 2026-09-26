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

from .cmds_ast import _data, _p, _save, T, hp_cap_or_line, _name_of_node
from .town import _func_node, town_gate
from .cmds_talk import _arg
from .cmds_gear import affix_lines, ambig_line
from .cmds_codex import new_lines
from . import codex as CX
from . import loot as LT
from . import gear as GB
from . import shop as SH
from . import matsrc as MS          # ★ Q-22：料的「从哪儿来」（唯一一口，本文件只传槽位）


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


def _name_set(entries) -> str:
    """几样料的名字（去重、按出现序）—— 给「哪条线吃哪几样」那一行用（**不报数量**）。"""
    out = []
    for e in entries:
        nm = str(_item(e["id"]).get("name", e["id"]))
        if nm and nm not in out:
            out.append(nm)
    return " · ".join(out)


def _forge() -> dict:
    """能打的东西 —— items 域里带 `forge` 那一格的那些（域里现取，**代码不写死 id**）。"""
    return {k: v for k, v in _data("items").items()
            if isinstance(v, dict) and not str(k).startswith("_") and v.get("forge")}


def _forge_rec(iid) -> dict:
    """打造的那一格（`{"level","gold","inputs"}`）—— 缺格 / 形状不对 ⇒ 当场抛（fail-closed）。"""
    r = dict((_item(iid) or {}).get("forge") or {})
    ins = r.get("inputs")
    if not isinstance(ins, list) or not ins or not isinstance(r.get("gold"), int) \
            or isinstance(r.get("gold"), bool) or not isinstance(r.get("level"), int) \
            or isinstance(r.get("level"), bool):
        raise ValueError("物品 %s 的 forge 那一格坏了：%r —— 打造配方判不了（fail-closed）"
                         % (iid, r))
    for e in ins:
        if not isinstance(e, dict) or not e.get("id") or not isinstance(e.get("n"), int):
            raise ValueError("物品 %s 的 forge.inputs 有一条坏的：%r" % (iid, e))
    return {"level": int(r["level"]), "gold": int(r["gold"]), "inputs": ins}


def _lack_str(p, entries) -> str:
    lack = []
    for e in entries:
        d = int(e["n"]) - _have(p, e["id"])
        if d > 0:
            lack.append("%s ×%d" % (_item(e["id"]).get("name", e["id"]), d))
    return " · ".join(lack)


# ══════════════════════════════════════════════════════════════
# 料的「从哪儿来」（Q-22 · 出处现算 —— 唯一一口在 `content/matsrc.py`）
# ══════════════════════════════════════════════════════════════
def _src_of(iid: str) -> str:
    """一样料从哪儿来 —— 采集点 + 掉它的怪（两边都取不到 ⇒ 空串，由调用方照实说）。

    ★ 出处**现算**：`gathering`（池里有它的采集点）∪ `drop_pools` × `monsters`（挂了这个池的怪）——
      域里加一个出产点，这一行跟着变；不手抄任何「材料 → 地点」的对照表。
    ★ 中文动作词（采/挖/钓/搜）走 `SYS_GATHER_VERB_*` 槽位（本文件不写中文）。
    """
    parts = []
    for sp in MS.gather_spots(iid, _data("gathering"), _data("maps")):
        parts.append(T("SYS_SRC_GATHER",
                       verb=T("SYS_GATHER_VERB_%s" % str(sp.get("verb") or "").upper()),
                       node=_name_of_node(sp["map"], sp["node"]), point=sp["name"],
                       times=sp["times"]))
    foes, _pools = MS.kill_foes(iid, _data("drop_pools"), _data("monsters"))
    if foes:
        parts.append(T("SYS_SRC_KILL",
                       list=" · ".join(f["name"] for f in foes[:MS.MAX_KILL])))
    return " · ".join(parts)


def src_lines(entries) -> list:
    """几样料的出处行（一行表头 + 逐样一行）—— `铁匠铺` 与 `强化` 两处共用同一份。

    ★ 传进来的 `entries` 就是那一支自己的料表（`recipes.<id>.inputs` / `items.<件>.forge.inputs`）——
      不另开一份「强化料是哪些」的名单（两处各写一份 = 迟早对不上）。
    """
    out = []
    for e in entries:
        out.append(T("SYS_SMITH_SRC_ROW", name=_item(e["id"]).get("name", e["id"]),
                     where=_src_of(e["id"]) or T("SYS_SRC_UNKNOWN")))
    return ([T("SYS_SMITH_SRC_HEAD")] + out) if out else []


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
    ★ fix7-gear（2026-09-26 · 第一件装备那条线）：这一屏从「一张强化表」补成**三条**——
      ① 强化（原有那一张，一个字不动）② 柜上柯尔自己打的**粗货**（按等级卖）
      ③ **打造**（材料 + 钱 ⇒ 一件；料与产物全从 items 域现取）。
      两样料的名单摆在一起（`SYS_SMITH_MATS`）—— 名字像的那几样从此各自归哪条线一眼看得清。
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
    _shelf = SH.goods(p, shelf="smith")
    if _shelf:                                     # 柜上空的就不摆这一段（照实：一件都没有）
        yield T("SYS_SMITH_GOODS")
        for _g in _shelf:
            yield T("SYS_SHELF_ROW", icon=_g["rec"].get("icon") or "",
                    name=_g["rec"].get("name") or _g["id"], gold=_g["gold"],
                    level=SH.level_need(_g["rec"]))
    _step1 = _recipes().get("rc_enh_01") or {}
    _forge_names = [_name_set(_forge_rec(i)["inputs"]) for i in sorted(_forge())]
    yield T("SYS_SMITH_MATS", enh=_name_set(_step1.get("inputs") or []),
            craft=" · ".join(x for x in _forge_names if x))
    # ★ Q-22：料名后面立刻跟「这几样从哪儿来」—— 出处在 `gathering` / `drop_pools` × `monsters` 域里现算
    #   （P3 报告 体验-4：玩家看到料名却不知道该去哪弄；强化那一支同样挂这一份，见 `enhance`）。
    for _ln in src_lines(_step1.get("inputs") or []):
        yield _ln
    yield T("SYS_SMITH_CRAFT_HEAD")
    for _iid in sorted(_forge()):
        _f = _forge_rec(_iid)
        yield T("SYS_SMITH_CRAFT_ROW", name=_item(_iid).get("name", _iid),
                need=_need_str(_f["inputs"]), gold=_f["gold"], level=_f["level"])
    yield T("SYS_SMITH_CRAFT_ASK")


# ══════════════════════════════════════════════════════════════
# 四之二、打造（fix7-gear）—— 材料 + 钱 ⇒ 一件
# ══════════════════════════════════════════════════════════════
async def forge(env, sink, uid, player):
    """`打造 <东西>` —— 在柯尔的炉子上用**材料 + 钱**打出一件（真源 `06_…/06_装备获取…§5.3`）。

    口径（三条，都不是新编的）：
      · 产物**不比掉落强** —— 那一档的逐件数值照 `15_装备逐件数值 §二` 的槽位预算配（同档总量、
        分布不同 ⇒ 是取舍不是升级）；材料与钱只是把「做事」那一步补上（§5.3「定向补短板」）；
      · 料与钱只许来自**域**（产物自己的 `forge` 那一格：`level` / `gold` / `inputs`）——
        本文件不写 id、不写价、不写数量；
      · 四条 fail-closed：认不出名字 ⇒ 照实说；不够级 ⇒ 那一句；料不够 / 钱不够 ⇒ 合在一句里说清，
        **档一个字不动**（不给货、不扣料、不扣钱）。
    """
    p = _p(player)
    line = town_gate(p, _func_node("smith"))
    if line:
        yield line
        return
    want = _arg(env)
    table = _forge()
    if not want:
        yield T("SYS_SMITH_CRAFT_HEAD")
        for iid in sorted(table):
            f = _forge_rec(iid)
            yield T("SYS_SMITH_CRAFT_ROW", name=_item(iid).get("name", iid),
                    need=_need_str(f["inputs"]), gold=f["gold"], level=f["level"])
        yield T("SYS_SMITH_CRAFT_ASK")
        return
    hit = None
    for iid, rec in table.items():
        nm = str(rec.get("name") or "")
        if want == nm or (len(want) >= 2 and want in nm):
            hit = (iid, rec)
            break
    if not hit:
        yield T("SYS_FORGE_NOSUCH", name=want)
        return
    iid, rec = hit
    f = _forge_rec(iid)
    now = int(p.get("level") or 0)
    if now < f["level"]:
        yield T("SYS_SHELF_LOCK", name=rec.get("name", iid), level=f["level"], now=now)
        return
    lack = _lack_str(p, f["inputs"])
    if f["gold"] > int(p.get("gold") or 0):
        lack += (" · " if lack else "") + T("SYS_GOLD_X", n=f["gold"] - int(p.get("gold") or 0))
    if lack:
        yield T("SYS_SMITH_CRAFT_MISSING", name=rec.get("name", iid),
                need=_need_str(f["inputs"]), gold=f["gold"], lack=lack)
        return
    for e in f["inputs"]:                              # 料：先扣（这一段只走一次，不会扣一半）
        _take(p, e["id"], int(e["n"]))
    p["gold"] = int(p.get("gold") or 0) - f["gold"]
    LT.add_to_bag(p, [{"id": iid, "n": 1}])
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_SMITH_CRAFT_OK", icon=rec.get("icon") or "", name=rec.get("name", iid))
    for ln in affix_lines(rec):                        # 打出来的是什么，当场摊给玩家看
        yield ln
    yield T("SYS_MONEY", gold=int(p.get("gold") or 0))


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
        # ★ Q-22：缺料那一下把「从哪儿来」一并说清（只列真缺的那几样；只差钱 ⇒ 这里为空、不多话）
        for _ln in src_lines([e for e in ins if _have(p, e["id"]) < int(e["n"])]):
            yield _ln
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
    # ★ G2：**打起来的时候**这一手走战斗那一条（花掉你这一手、当场回血、记每场上限）
    #   —— 判据只有一个：此刻**真有一场在跑**（`instance.live`，与战斗那边同一个口）。
    #   面板在开战时固化 ⇒ 战斗里只认**回血**那一类；别的（食物 / 增益）照实说，
    #   **不消耗、不动档**（吃掉却没效果 = 骗人）。
    from . import instance as INST
    if INST.live(env, uid) is not None:
        _mx0 = hp_cap_or_line(p)[0] or 0        # 没面板 ⇒ 0（只影响 hp_pct 那一类的估值）
        if _heal_gain(p, rec, _mx0) is None:
            yield T("COMBAT_ITEM_ONLY_HEAL", name=rec.get("name", iid))
            return
        from . import cmds_battle as CBAT
        async for line in CBAT.battle_item(env, sink, uid, player):
            yield line
        return
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
