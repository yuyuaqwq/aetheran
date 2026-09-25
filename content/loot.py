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


def _resolve(out: str, entry: dict, level: int, rnd: random.Random, items_tbl: dict):
    """把 `*armor_random` 这种动态项解析成具体物品 id。

    ★ B3-6b-2d-b：按域里现成的 ASCII `slot` 挑（原先按 `kind` 的**中文枚举**挑 ——
      「中文枚举当机器键」，一字之差就静默一件都挑不出，K48 / P-20）。格 → 槽位集合见
      `_GRID_SLOTS`（格名本来就是 ASCII，写在 drop_pools 的 out 上）。
    """
    if not out.startswith("*"):
        return out
    want = out[1:]
    slots = next((s for grid, s in _GRID_SLOTS.items() if want.startswith(grid)), None)
    if slots is None:
        return None
    qual = entry.get("quality")
    cand = [k for k, v in items_tbl.items() if v.get("slot") in slots]
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
    """
    rnd = rnd or random.Random()
    p = pools().get(pool_id)
    if not p:
        return []
    it = items()
    out, seen = [], set()
    rolls = int(p.get("rolls", 1) or 1)
    for _ in range(rolls):
        e = _pick(p.get("entries") or [], rnd)
        if not e:
            continue
        if e.get("kind_key") == "pool":                 # 嵌套池（ASCII 机器键；原先比中文枚举）
            out.extend(roll_pool(e["out"], level=level, rnd=rnd))
            continue
        oid = _resolve(str(e.get("out")), e, level, rnd, it)
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
