# -*- coding: utf-8 -*-
"""《阿斯特兰》掉落与未鉴定（B2-3）—— 纯函数，可复现（种子驱动）。

★ 设计口径（真源 27_掉落的惊喜感与未鉴定_v1.md）：
  · 随机的是「开出了什么」，**不是**「数值多高」—— 装备数值全部是固定值（配平表管住）
  · 未鉴定给**四类出口**：装备 30% / 材料 45% / 垃圾 15% / 信物 7% / 线索 3%
  · 同一类鉴定过一次之后，同类不再显示问号（`seen_after`）
  · 重复掉落三个去处：拆解（材料）/ 卖出（钱）/ 图鉴（第一次记一段文字）
"""
from __future__ import annotations

import json
import os
import random

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_C: dict = {}


def _d(name: str):
    if name not in _C:
        with open(os.path.join(_DIR, name + ".json"), encoding="utf-8") as f:
            _C[name] = json.load(f)
    return _C[name]


def pools() -> dict:
    return _d("drop_pools")


def items() -> dict:
    return _d("items")


#: ★ B3-6b-2d-keys-2：条目机器键的兜底（条目没写、物品表也没有时）—— **ASCII 键**，不是中文枚举。
#:   与 `items.schema.json` 的 `kind_key` enum 同值（`probe_drops` ⑭ 对账）；中文名那一栏在域里，
#:   代码一个字都不引（K48 / P-20 甲案第二刀）。
K_MATERIAL_KEY = "material"

#: 动态项 `*<格>_random` 里的**格**（ASCII，写在 drop_pools 的 out 上）→ 域里现成的 ASCII
#: `slot`（六格见 `schemas/items.schema.json` 的 `slot.enum`）。
#: ★ B3-6b-2d-b：装备的机器键一律走 `slot` —— `kind` 是**中文枚举**，不当筛选键（K48 / P-20：
#:   一字之差就静默挑不出东西）。格表在代码里，取值全部来自域。
_GRID_SLOTS = {
    "armor": ("armor_top", "armor_bottom", "helmet", "boots"),
    "weapon": ("weapon",),
}


def rec_of(oid: str) -> dict:
    """一件东西的显示记录 —— **唯一一口**：物品表 → 池表（未鉴定的 marker 挂在池上）。

    为什么要有它：`unid_*` 不在物品表里，name / icon / hint 只写在 `drop_pools` 的池上。
    呈现口（背包那几行 / 「得到」那一行 / 进谱归属）都走这里 ——
    别各自写一遍 items-or-pools（B3-3 前修补：背包原先只查物品表，把裸 id 显示给玩家）。
    """
    return items().get(oid) or pools().get(oid) or {}


def kind_key_of(oid: str, kind_key: str | None = None) -> str:
    """条目的**机器键**归一 —— **唯一的一口**：条目写的 → 物品表的 → 未鉴定池自己写的 → 兜底。

    ★ B3-6b-2d-keys-2（P-20 甲案第二刀）：返回的是 ASCII `kind_key`，**不再是中文 `kind`** ——
      原先调用方拿中文枚举当筛选键 / 兜底（K48 / K51：一字之差就静默挑不出东西）。
      中文 `kind` 还在域里（玩家看得见的分类名），但**不进代码**（`probe_copy` ⑮ 静态守卫钉 0 处）。
    ★ `unid_*` 不是物品表里的东西，它的 marker 写在 `drop_pools` 的池上（`kind_key`）——
      别在调用方手写「未鉴定」（K48 同族）。
    """
    k = kind_key or (items().get(oid) or {}).get("kind_key")
    if not k and str(oid).startswith("unid_"):
        k = (pools().get(oid) or {}).get("kind_key")
    return k or K_MATERIAL_KEY


def _pick(entries, rnd: random.Random):
    """按权重抽一条。"""
    if not entries:
        return None
    tot = sum(int(e.get("w", 1) or 1) for e in entries)
    r = rnd.uniform(0, tot)
    acc = 0.0
    for e in entries:
        acc += int(e.get("w", 1) or 1)
        if r <= acc:
            return e
    return entries[-1]


def _req_level(rec: dict) -> int:
    """一件装备的**穿戴门槛**（`items.req.level`；没写 = 0 ⇒ 谁都能穿）。

    ★ P-60：这一格原先全仓只有 items 域自己写着、**没有任何读端** ——
      「按等级抽一件」那条声明（`drop_pools.dp_elite_gear.level_gated`）也就跟着落了空。
    """
    return int((rec.get("req") or {}).get("level") or 0)


def _resolve(out: str, entry: dict, level: int, rnd: random.Random, items_tbl: dict,
             gated: bool = False):
    """把 `*armor_random` 这种动态项解析成具体物品 id。

    ★ B3-6b-2d-b：按域里现成的 ASCII `slot` 挑（原先按 `kind` 的**中文枚举**挑 ——
      「中文枚举当机器键」，一字之差就静默一件都挑不出，K48 / P-20）。格 → 槽位集合见
      `_GRID_SLOTS`（格名本来就是 ASCII，写在 drop_pools 的 out 上）。

    ★ P-60（B4-25 记的那笔账 · 本批落）：`gated=True` = **这个池自己声明了 `level_gated`**
      ⇒ 只在「这一级穿得上」的那批里挑。原先 `level` 这个参数**收了却一次都没用**
      （死参数就是欠账的指纹）⇒ 池子 `label` 上写着的「按等级抽一件」是空话：
      3 级玩家打掉一只精英，照样可能抽到 17 级才穿得上的遗物。
      · 门槛来自 `items.req.level`（**现取**，不手打任何等级表）；
      · **够不着 ⇒ 不放**（返回 None · fail-closed）：不退回「全档」——
        退回等于这条声明白写；也不编一个更低档的东西出来（那是自造口径）。
        代价与今天的可达性见 `_notes.md`（每一级都抽得到：普通/精制那两档里
        另有一批 `req.level = 0` 的）。
    """
    if not out.startswith("*"):
        return out
    want = out[1:]
    slots = next((s for grid, s in _GRID_SLOTS.items() if want.startswith(grid)), None)
    if slots is None:
        return None
    qual = entry.get("quality")
    cand = [k for k, v in items_tbl.items() if v.get("slot") in slots]
    if gated:                                        # ★ P-60：按等级那一刀（先于品阶偏好）
        cand = [k for k in cand if _req_level(items_tbl[k]) <= int(level or 1)]
    if qual:
        f = [k for k in cand if items_tbl[k].get("quality") in qual]
        if f:
            cand = f
    if not cand:
        return None
    return rnd.choice(sorted(cand))


def roll_pool(pool_id: str, *, level: int = 1, rnd: random.Random | None = None) -> list:
    """按池抽掉落，返回 [{id, n, kind_key, story?}]。同一池不许抽重（unique）。

    ★ B3-6b-2d-keys-2：那一格叫 `kind_key`（ASCII 机器键），不再是中文 `kind` —— 它与域里
      新增的 `kind_key` 同名同值（中文分类名留在域里，代码不引）。
    ★ P-60：`level` 这一格现在**真被读** —— 池自己写了 `level_gated: true`（唯一读口就是
      **本函数这一行**）时，动态格只在「这一级穿得上」的那批里挑（见 `_resolve`）。
      `level` 缺省 1（与调用方一致）；嵌套池把 `level` 原样传下去（`dp_trash_mid` → `dp_elite_gear`
      那条路就是靠它）。
    """
    rnd = rnd or random.Random()
    p = pools().get(pool_id)
    if not p:
        return []
    it = items()
    out, seen = [], set()
    rolls = int(p.get("rolls", 1) or 1)
    gated = bool(p.get("level_gated"))                # ★ P-60：池侧声明 → 动态格那一刀
    for _ in range(rolls):
        e = _pick(p.get("entries") or [], rnd)
        if not e:
            continue
        if e.get("kind_key") == "pool":                 # 嵌套池（ASCII 机器键；原先比中文枚举）
            out.extend(roll_pool(e["out"], level=level, rnd=rnd))
            continue
        oid = _resolve(str(e.get("out")), e, level, rnd, it, gated=gated)
        if not oid:
            continue
        if p.get("unique") and oid in seen:
            continue
        seen.add(oid)
        n = 1
        rng = e.get("n")
        if isinstance(rng, list) and len(rng) == 2:
            n = rnd.randint(int(rng[0]), int(rng[1]))
        rec = {"id": oid, "n": n, "kind_key": kind_key_of(oid, e.get("kind_key"))}
        if e.get("story"):
            rec["story"] = e["story"]
        out.append(rec)
    return out


def open_unid(unid_id: str, *, rnd: random.Random | None = None) -> dict:
    """开一件未鉴定：返回 {id, kind_key, story?}（「开出了什么」）。"""
    rnd = rnd or random.Random()
    u = pools().get(unid_id)
    if not u or u.get("kind_key") != "unidentified":
        return {}
    it = items()
    e = _pick(u.get("pool") or [], rnd)
    if not e:
        return {}
    oid = _resolve(str(e.get("out")), e, 1, rnd, it)
    if not oid:
        return {}
    r = {"id": oid, "kind_key": kind_key_of(oid, e.get("kind_key")), "from_unid": unid_id}
    if e.get("story"):
        r["story"] = e["story"]
    return r


def help_text_of(uid_id: str, npc_id: str) -> str | None:
    """谁认得出这个（杜林认锻造物 / 莉安认铭文 / 柯尔只认铁 / 艾德认教会器物）。

    ★ B4-19：三句话都走 texts 槽位（原先这里是三句内联 —— 文案真源只有 texts 域）。
    """
    from .cmds_ast import T                    # ★ B4-19：本地 import（免得包装载期成环）
    u = pools().get(uid_id) or {}
    if npc_id in (u.get("identify_by") or []):
        return T("TALK_IDENTIFY_KNOWN")
    if npc_id == "npc_durin":
        return T("TALK_IDENTIFY_NONE")
    if npc_id == "npc_lian":
        return T("TALK_IDENTIFY_LIAN")
    return None


def add_to_bag(player: dict, drops: list) -> list:
    """把掉落并进背包（原地改 player["bag"]），返回「第一次见到的」清单。"""
    bag = player.setdefault("bag", {})
    codex = player.setdefault("codex", {})
    first = []
    for d in drops:
        bag[d["id"]] = int(bag.get(d["id"], 0)) + int(d.get("n", 1))
        if d["id"] not in codex:
            codex[d["id"]] = True
            first.append(d["id"])
    return first


# ══════════════════════════════════════════════════════════════
# ★ B4-20：玩家点名的**一件东西** —— 「名字 / id → 那一个 id」收成一个口
# ══════════════════════════════════════════════════════════════
# 为什么要有这一节：全包原先有**五份**「按名字在背包里找一件」的实现
#   （`cmds_more._bag_hit` · `cmds_gear._in_bag` · `cmds_recipe._item_of_name`〔扫的是**整张物品表**〕·
#     `cmds_recipe.item_use` 内联那一段 · `shop.find`），五份都是「**遍历序里第一个命中的就算**」——
#   两条玩家看得见的后果（都有真跑证据）：
#     ① **精确名输给部分名**：`查看 苦叶` 回的却是「苦叶汤」（`i_food_*` 在字典序里先撞上，
#        而「苦叶」明明**字字相等**）；`使用 苦叶` 更狠 —— 把那碗汤**吃掉**了。
#     ② **同名四档的装备挑不出也看不见**：`拾荒人的重剑` 四档同名（真源 15 那四行），
#        背包里两行列得一模一样；`强化 拾荒人的重剑` 只有精制那档时会回「背包里没有」
#        （它扫的是物品表的第一件 = 普通档），两档在手时又**静默**强了普通那件。
#   ⇒ 这一节是**唯一的一口**：id / 全名相等优先，名字的一部分次之；命中**多件就照实说**
#     （不替玩家挑 —— 挑错就是白花材料 / 穿错装备，K69 同族：先把事实说清）。
def quality_words() -> set:
    """品阶词表（普通 / 精制 / 稀有 / 遗物 …）—— **从域里现取**，代码里一个中文都不写。

    来处：`items` 域里出现过的 `quality` 值（`schemas/items.schema.json` 的 enum 是同一套）。
    域里添了新一档，「重剑 <新档>」这种写法当场就认（K48 / P-20 甲案）。
    """
    out = set()
    for rec in items().values():
        if isinstance(rec, dict) and rec.get("quality"):
            out.add(str(rec["quality"]))
    return out


def split_quality(want: str):
    """玩家写的那个名字里有没有**点明品阶** —— 三种写法都认，返回 `(名字, 品阶 or None)`。

    `拾荒人的重剑 精制` / `精制 拾荒人的重剑` / `拾荒人的重剑（精制）`（半角括号也认）。
    没点名就是 `(原名, None)`。名字与品阶都是**域里的词**，这一层不做任何归一化。
    """
    w = str(want or "").strip()
    for q in quality_words():
        for l, r in (("（", "）"), ("(", ")")):
            if len(w) > len(l + q + r) and w.endswith(l + q + r):
                return (w[: -len(l + q + r)].strip(), q)
    parts = w.split()
    if len(parts) >= 2:
        if parts[-1] in quality_words():
            return (" ".join(parts[:-1]).strip(), parts[-1])
        if parts[0] in quality_words():
            return (" ".join(parts[1:]).strip(), parts[0])
    return (w, None)


def match_ids(ids, want: str, *, need_slot: bool = False) -> list:
    """名字 / id → **命中的那些** id（可能 0 个、可能多件）—— 命中的判定只在这一处。

    · **id 或全名相等**优先于**名字的一部分**（一条东西叫「苦叶」、另一条叫「苦叶汤」时，
      玩家写「苦叶」要拿到苦叶 —— 原先撞上哪一条取决于遍历序，K71 同族）；
    · `need_slot=True` 只认能穿的（域里 ASCII `slot`，同 `probe_items` ①之二）；
    · 点明品阶的只认那一档。
    """
    name, q = split_quality(want)
    if not name:
        return []
    exact, part = [], []
    for iid in ids:
        rec = rec_of(iid) or {}
        if need_slot and not rec.get("slot"):
            continue
        if q and str(rec.get("quality") or "") != q:
            continue
        nm = str(rec.get("name") or "")
        if name == iid or (nm and name == nm):
            exact.append(iid)
        elif nm and len(name) >= 2 and name in nm:
            part.append(iid)
    return exact or part


def pick(ids, want: str, *, need_slot: bool = False):
    """`(id, 记录, 候选)` —— 唯一命中就用它；**命中多件不挑**（候选交回调用方照实说）。"""
    hits = match_ids(ids, want, need_slot=need_slot)
    if len(hits) == 1:
        return (hits[0], rec_of(hits[0]), [])
    if len(hits) > 1:
        return (None, {}, sorted(hits))
    return (None, {}, [])


def ambiguous_names() -> set:
    """**一个名字在域里对得着好几件**的那些名字 —— 从域里现算（谁都不许手抄一份）。"""
    n: dict = {}
    for rec in items().values():
        if isinstance(rec, dict) and rec.get("name"):
            nm = str(rec["name"])
            n[nm] = n.get(nm, 0) + 1
    return set(k for k, v in n.items() if v > 1)


def label_of(oid: str) -> str:
    """**列表里**那一行的名字 —— 「这名字在域里对得着好几件」时缀上品阶（「拾荒人的重剑 · 精制」）。

    为什么：同名四档的装备在列表里原本长得**一模一样**（两行都是「⚔️ 拾荒人的重剑 ×1」），
    玩家既分不清手里是哪几档、也说不出要动哪一件（B4-20）。
    ★ 缀不缀**只看「名字重不重」**（域里现算），不看这一格的背包里有什么 ——
      同一条东西在谁的背包里都长一个样（判据好钉，玩家也好学）。
      一名一件的（材料 / 食物 / 道具）一个字不改。
    """
    rec = rec_of(oid) or {}
    nm = str(rec.get("name") or oid)
    q = str(rec.get("quality") or "")
    return ("%s · %s" % (nm, q)) if (q and nm in ambiguous_names()) else nm


def cands_label(ids) -> str:
    """候选那几件 → 一行里点得出的名字（「普通 · 精制」）。没有品阶的退回名字。"""
    out = []
    for i in ids:
        rec = rec_of(i) or {}
        out.append(str(rec.get("quality") or rec.get("name") or i))
    return " · ".join(out)
