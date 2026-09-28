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
    # ★ g4-leftovers（item 2）：`no_drop` 的那几件**不进动态格** —— 一格的唯一用途是「铺子买」
    #   或「自己造」的东西（今天只有打造件 `i_forge_chest`）不该从随机防具里掉出来：
    #   打造（料 + 钱）与「白捡一件一样的」不能并存，否则那一条指令就是白写的。
    #   ★ 为什么只排**打造件**：真源 `06_装备获取与支线玩法_v1.md §一 1.1` 明写普通档
    #     「镇上三家铺子直接买 · **普通怪掉**」两路都有 ⇒ 铺子那三件入门装照旧可掉（不算错）；
    #     打造件那一条的真源行（`06 §1.1-b`）给的路只有「打造」，不在 §一 1.1 那 16 件里
    #     ⇒ 真源没授权它掉落，本批按 fail-closed 排掉（详见分支 `_notes.md`）。
    cand = [k for k, v in items_tbl.items()
            if v.get("slot") in slots and not v.get("no_drop")]
    if gated:                                        # ★ P-60：按等级那一刀（先于品阶偏好）
        cand = [k for k in cand if _req_level(items_tbl[k]) <= int(level or 1)]
    if qual:
        f = [k for k in cand if items_tbl[k].get("quality") in qual]
        if f:
            cand = f
    if not cand:
        return None
    return rnd.choice(sorted(cand))


def held_ids(player) -> set:
    """玩家**手上已有哪些件**（`bag` 的键）—— 唯一一口 · `unique` 池「按档去重」的输入。

    ★ fxm2-horn：为什么要收成一口 —— 「手上有哪几件」别处都问 `bag` 那一格（`sorted(p["bag"])`
      之类走 `loot.worn_ids` / `match_ids` 那一族），只有**掉落这一支**从来没问过它：
      `dp_boss_minor`（`unique: true` · 单条目 w=100）挂在五只**可反复打**的头目怪上 ⇒
      每杀一只必掉一个「半截号角」（夜试玩实测：同一只怪反复打，进包 225 个）。
      这一口只回答「手上有哪些 id」——**不判任何规则**（规则在 `roll_pool` 的 `unique` 那一条）。
    · `bag` 不是 dict（半截老档 / 坏档）⇒ 空集（fail-closed：不猜、不编）。
    """
    bag = (player or {}).get("bag")
    return set(str(k) for k in bag) if isinstance(bag, dict) else set()


def roll_pool(pool_id: str, *, level: int = 1, rnd: random.Random | None = None,
              held=None) -> list:
    """按池抽掉落，返回 [{id, n, kind_key, story?}]。同一池不许抽重（unique）。

    ★ B3-6b-2d-keys-2：那一格叫 `kind_key`（ASCII 机器键），不再是中文 `kind` —— 它与域里
      新增的 `kind_key` 同名同值（中文分类名留在域里，代码不引）。
    ★ P-60：`level` 这一格现在**真被读** —— 池自己写了 `level_gated: true`（唯一读口就是
      **本函数这一行**）时，动态格只在「这一级穿得上」的那批里挑（见 `_resolve`）。
      `level` 缺省 1（与调用方一致）；嵌套池把 `level` 原样传下去（`dp_trash_mid` → `dp_elite_gear`
      那条路就是靠它）。
    ★ fxm2-horn：`unique: true` 的池是**「按档去重」**，不只是「同一次抽取内不重」——
      `held`（`held_ids(player)`）里**已经有一件**的条目**不再进池**。真源
      `22_旧哨塔_逐间设计_v1 §12 塔顶`：「掉落 半截号角（**如果 10 房没拿**）· 刻字的石片 · …
      」—— 信物只该有一件（`09` 那条线的 `q_main_08` / 彩蛋 4 都只要「手里拿着它」）。
      原先那一格只防「**同一次抽取内**重复」⇒ 一条单条目 w=100 的池挂在五只可反复打的头目怪上
      = 每杀一只必掉一个（夜试玩实测 225 个）。
      · **只对 `unique` 池生效** ⇒ 没写这一格的池（今天 6 条 `dp_*` 里的 5 条）一个字节都不动；
      · 排的是**条目**（按条目自己那份静态 `out` 的 id）⇒ 池里剩下那些条目的权重与**相对**
        几率一字不动（`_pick` 的 Σw 只对剩下的那几条求和）、抽签次数照旧 ⇒
        「同一条池里别的东西照掉」。今天唯一的 `unique` 池（`dp_boss_minor`）条目全是静态 id，
        `probe_drops ⑯` 把这一条钉成常驻判据（哪天有池给 `unique` 池塞了 `*动态`/嵌套项当场红）；
      · 动态项（`*armor_random` 那种）**不排**：它要现抽才知道是哪一件，而现抽要消耗随机流 ——
        排它会改动**别的条目**的签（那是另外一件事，见 `_resolve`）；
      · `held` 缺省 = **不排**（池长什么样就抽什么样）：判据 / 工具那些「看池子本身」的调用
        不该被玩家的背包影响。★ 谁**必须**传 = 静态守卫 `probe_drops ⑯④`：`content/*.py` 里
        每一个 `roll_pool(` 调用点都得带 `held=`（免得哪天新加的调用点把这半条规则漏掉）。
    """
    rnd = rnd or random.Random()
    p = pools().get(pool_id)
    if not p:
        return []
    it = items()
    out, seen = [], set()
    rolls = int(p.get("rolls", 1) or 1)
    gated = bool(p.get("level_gated"))                # ★ P-60：池侧声明 → 动态格那一刀
    # ★ fxm2-horn：手上已有的那几件（只有 `unique` 池认这一格 —— 别的池零变化）
    keep = {str(x) for x in (held or ())} if p.get("unique") else set()
    for _ in range(rolls):
        entries = p.get("entries") or []
        if keep:                                      # 已有 ⇒ 那一条**不进池**（静态 id 才排得动）
            entries = [x for x in entries if str(x.get("out")) not in keep]
        e = _pick(entries, rnd)
        if not e:
            continue
        if e.get("kind_key") == "pool":                 # 嵌套池（ASCII 机器键；原先比中文枚举）
            out.extend(roll_pool(e["out"], level=level, rnd=rnd, held=held))
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


def open_unid(unid_id: str, *, level: int = 1, rnd: random.Random | None = None,
              gated: bool = False) -> dict:
    """开一件未鉴定：返回 {id, kind_key, story?}（「开出了什么」）。

    ★ P-60 同族（审计 L1122）：`level` / `gated` 与 `roll_pool` **同一对形参、同一个读法**
      （那边读池上的 `level_gated`，这边由调用方显式传）。原先这里**硬传 `level=1` 且不传
      `gated`** ⇒ 1 级玩家开未鉴定开出穿不上的装备：实跑 `unid_rare` 3000 次
      **444 次（14.8%）** 是 `req.level > 1` 的档（遗物档 17 级 / 稀有档 10 级）。
      玩家侧读起来是「白捡一件 17 级遗物却穿不上」；`roll_pool` 那一侧 P-60 已立同一条口径
      （`dp_elite_gear` 声明 `level_gated` 后实跑只出这一级穿得上的）。
      · 缺省 `level=1 / gated=False` = 判据与工具那些「看池子本身」的调用**一字不变**；
      · 门禁写 `scripts/probe_drops.py ⑯-之五`：`content/*.py` 里 `open_unid(` 的调用点
        唯一（`cmds_talk`），且它**必须**带 `level=` + `gated=`（免得下个读者照旧漏）。
    """
    rnd = rnd or random.Random()
    u = pools().get(unid_id)
    if not u or u.get("kind_key") != "unidentified":
        return {}
    it = items()
    e = _pick(u.get("pool") or [], rnd)
    if not e:
        return {}
    oid = _resolve(str(e.get("out")), e, level, rnd, it, gated=gated)
    if not oid:
        return {}
    r = {"id": oid, "kind_key": kind_key_of(oid, e.get("kind_key")), "from_unid": unid_id}
    if e.get("story"):
        r["story"] = e["story"]
    return r


def appraisers_of(unid_id: str) -> tuple:
    """这一件**谁能鉴定**（`unid_id`）—— **唯一的一口**：域里那份「谁认得出这一门」。

    来处：`drop_pools[].identify_by`（真源 `27_掉落的惊喜感与未鉴定_v1.md §六` 的 `appraiser`
    那一格 —— 骨田那件写的就是 `["npc_durin", "npc_cole"]`），填的是谁，逐条见
    `00_总纲/14_图鉴四谱口径_v1.md §五` 旧物谱那三行「谁认得出」那一列。

    ★ 读端只许这一个口：`help_text_of`（他认不认得这一门）与「拿给人看 ⇒ 当场开出来」
      那一支（`cmds_talk._identify_lines`）都走它 —— 别在调用方再 `pools().get(...)` 读一遍
      `identify_by`（K65 / P-31 同族：谁再自己扫一遍域，口径迟早分叉）。
      名单为空 = **谁也鉴定不了**（fail-closed：不猜、不退回「随便谁都能开」）。
    """
    return tuple(str(x) for x in ((pools().get(str(unid_id)) or {}).get("identify_by") or []))


def help_text_of(uid_id: str, npc_id: str) -> str | None:
    """他看这一件会回什么：认得出这一门 / 他那句句子 / 不说话（`None` = 他没反应）。

    ★ B4-19：话都走 texts 槽位（原先这里是内联字面量 —— 文案真源只有 texts 域）。
    ★ 「认得这一门的那个人」的判据 = `appraisers_of()`（域里的 `identify_by`，唯一一口）。
    ★ L1123：认得出那一口优先；下面只剩「莉安另有一句」一个字面量（她不在任何池的
      `identify_by` 里，却另有一句「看了很久」），其余一律回 `None`。
      曾经还有一个 `npc_durin` 字面量并带着槽位 `TALK_IDENTIFY_NONE` ——
      它**永远走不到**（杜林在三个 unid 池的 `identify_by` 里全部在列），已删。
    """
    from .cmds_ast import T                    # ★ B4-19：本地 import（免得包装载期成环）
    if npc_id in appraisers_of(uid_id):
        return T("TALK_IDENTIFY_KNOWN")
    if npc_id == "npc_lian":
        # ★ 这一支是**活的**（她不在那两个池的 identify_by 里，却另有一句「看了很久」）
        # —— 删它就是删一个玩家反复能看到的反应。
        return T("TALK_IDENTIFY_LIAN")
    # ★ L1123：原先这里还内联了 npc_durin，而它**永远走不到**。
    # 取证（契约口 + 实跑）：手上口只认 kind_key == "unidentified"，全仓只有三个这样的池，
    # 而 npc_durin 在**三个的 identify_by 里全部在列**（道具 / 箭声 / 塔）
    # ⇒ 上面那一口一定先回。实跑三池 × npc_durin = 3/3 全部返回 TALK_IDENTIFY_KNOWN，
    #   无一次落到被删的那一支。
    # 不留兼容壳：分支与它唯一的文案槽位 TALK_IDENTIFY_NONE 一起删（
    #   那句『翻了两下』玩家一辈都拿不到）。
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


def worn_ids(p) -> list:
    """**身上穿着的那几件**的 id（档上 `equipped` 六格的值，稳定序）—— 「身上」的第二处。

    ★ 为什么要有它（试玩报告 P1 BUG-3）：全包的「按名字找一件东西」都只看背包那一格
      （`sorted(p["bag"])`）⇒ 穿在身上的东西对『强化 / 查看 / 卖出 / 存放 / 丢弃 / 使用』
      一律回「背包里没有」、对『卸下』却认得出（只有『对比』单独去看了身上那格）。
      玩家穿上一件装备之后，同一条指令两种回答，且猜不到是「穿着的看不见」。
      ⇒ 六格的值收成一个口（与 `bag` 并列），调用方照自己的守卫决定「认出来了怎么答」。
    ★ 认不出的（`equipped` 不是 dict / 空串那一格）一律跳过 —— 这一层不猜。
    """
    eq = p.get("equipped")
    if not isinstance(eq, dict):
        return []
    return sorted(str(v) for v in eq.values() if v)


def ambiguous_names() -> set:
    """**一个名字在域里对得着好几件**的那些名字 —— 从域里现算（谁都不许手抄一份）。"""
    n: dict = {}
    for rec in items().values():
        if isinstance(rec, dict) and rec.get("name"):
            nm = str(rec["name"])
            n[nm] = n.get(nm, 0) + 1
    return set(k for k, v in n.items() if v > 1)


def label_of(oid: str) -> str:
    """**列表里**那一行的名字 —— 「这名字在域里对得着好几件」时缀上品阶（「拾荒人的重剑（精制）」）。

    为什么：同名四档的装备在列表里原本长得**一模一样**（两行都是「⚔️ 拾荒人的重剑 ×1」），
    玩家既分不清手里是哪几档、也说不出要动哪一件（B4-20）。
    ★ 缀不缀**只看「名字重不重」**（域里现算），不看这一格的背包里有什么 ——
      同一条东西在谁的背包里都长一个样（判据好钉，玩家也好学）。
      一名一件的（材料 / 食物 / 道具）一个字不改。

    ★★ P2-7（文案修复车道 · 2026-09-28）：品阶那一截从「名字 · 品阶」改成「名字（品阶）」。
      起因**不是排版洁癖，是一条真缺陷（可复现）**——
      「`装备 拾荒人的重剑 · 精制`」在屏上打不出来：`split_quality` 的三种写法是
      「名字 品阶」/「品阶 名字」/「名字（品阶）」，**没有一种收「名字 · 品阶」**，
      于是它把名字那一半判成「拾荒人的重剑 ·」（尾巴那个 `·` 还在）⇒ 一样都命不中，
      回一句「背包里没有『拾荒人的重剑 · 精制』」。
      ⇒ 列表给玩家看的那个名字，**本身就是一句能敲回去的话**（`『%s』` 包着的那些
      「『拾荒人的重剑（精制）』」现在真的敲得通）。
      ★ 顺带满足 P2-1 定的口径（行首 `· ` 作条目锚点、**行内不出现 `·`**）——
        这一条原先只在 texts.json 里收口，代码拼出来的那几处（`label_of`）漏在外面。
    """
    rec = rec_of(oid) or {}
    nm = str(rec.get("name") or oid)
    q = str(rec.get("quality") or "")
    return ("%s（%s）" % (nm, q)) if (q and nm in ambiguous_names()) else nm


def cands_label(ids) -> str:
    """候选那几件 → 一行里点得出的名字（「普通 · 精制」）。没有品阶的退回名字。"""
    out = []
    for i in ids:
        rec = rec_of(i) or {}
        out.append(str(rec.get("quality") or rec.get("name") or i))
    return " · ".join(out)
