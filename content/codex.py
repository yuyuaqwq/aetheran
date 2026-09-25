# -*- coding: utf-8 -*-
"""《阿斯特兰》图鉴四谱（B2-7）—— 四本谱的**唯一**进出面。

四本谱（口径真源：`00_总纲/14_图鉴四谱口径_v1.md`）：
    材料谱 material · 风味谱 flavor · 怪物谱 monster · 旧物谱 relic

分工：
  · 数据（条目 + 「一句人话」）= `content/data/codex.json`（由 rebuild_codex.py 从源文档解析）
  · 记录（谁见过什么）= 玩家档的 `books` 一格 + `foot`（足迹）一格 —— ★ 只在这里写
  · 呈现 = `content/cmds_codex.py`（文案槽位在 texts 域）

★ 玩家档只多两个键（都是加出来的，老档不用迁移）：
    books = {"material": {...}, "flavor": {...}, "monster": {...}, "relic": {...}}
    foot  = {"nodes": {"<loc>:<node>": 第几个游戏日}, "kills": n, "reads": n, "gathers": n}

★ 旧物谱一条记**两格**（都是一次性的判断，落档后不可逆 · 都由本模块写）：
    known   —— 「问对人」认出来了（`known` / `reveal` / `revealable`：真名 + 来处那段）
    studied —— 「自己上手看过」了（`studied` / `study`：只看出物证那一层，P-8）
  两格**各给一半、不互相替代**：自己看不出「来处」（那要有人认得），
  问过人也不会替你省掉「这一件本身看得出来什么」。物证句的唯一来源见 `evidence()`。

★ `codex` 那个平表（id → True）是 loot 的「第一次见到」集合 —— 本模块**不碰**它（两处各管一头）。
"""
from __future__ import annotations

import json
import os

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_C: dict = {}

BOOKS = ("material", "flavor", "monster", "relic")

#: ★ B3-6b-2d-keys-2（P-20 甲案第二刀）：`kind_key`（ASCII 机器键）→ 归哪本谱。
#: 口径（05 §五 / 14_图鉴四谱口径_v1）：材料谱记「捡到的材料」= material / junk / clue；
#: 风味谱记「吃过的菜」= food；旧物谱 = keepsake（有来处的旧东西）+ unidentified（还不知道是什么）。
#: ★ 代码只比 ASCII 键（原先比的是域里的**中文枚举**「材料 / 垃圾 / 线索 / 食物 / 信物 / 未鉴定」，
#:   K48 / K51）；中文那一栏留在域里，`probe_copy` ⑮ 静态守卫钉着「代码里 0 处」。
KIND_BOOK = {"material": "material", "junk": "material", "clue": "material", "food": "flavor"}
#: 捡到就该进旧物谱的机器键
PICK_BOOK = {"keepsake": "relic", "unidentified": "relic"}


def _d(name: str):
    if name not in _C:
        with open(os.path.join(_DIR, name + ".json"), encoding="utf-8") as f:
            _C[name] = json.load(f)
    return _C[name]


def data() -> dict:
    return _d("codex")


def meta() -> dict:
    return dict(data().get("_meta") or {})


def book(name: str) -> dict:
    return dict(data().get(name) or {})


def label(name: str) -> str:
    """谱 id → 中文名（缺了回 id，不静默编一个）。"""
    return (meta().get("book_label") or {}).get(name) or name


def targets() -> dict:
    """记满条数（只有三本有；旧物谱不设记满 —— 问号本身就是钩子）。"""
    return dict(meta().get("targets") or {})


def entry(name: str, rid: str):
    return book(name).get(rid)


def name_of(name: str, rid: str) -> str:
    e = entry(name, rid)
    return (e or {}).get("name") or rid


def line_of(name: str, rid: str, key: str = "line") -> str:
    e = entry(name, rid) or {}
    return e.get(key) or ""


# ══════════════════════════════════════════════════════════════
# 玩家档那两格（读写都从这里过）
# ══════════════════════════════════════════════════════════════
def _books(p: dict) -> dict:
    b = p.get("books")
    if not isinstance(b, dict):
        b = {}
    for k in BOOKS:
        if not isinstance(b.get(k), dict):
            b[k] = {}
    p["books"] = b
    return b


def _foot(p: dict) -> dict:
    f = p.get("foot")
    if not isinstance(f, dict):
        f = {}
    if not isinstance(f.get("nodes"), dict):
        f["nodes"] = {}
    for k in ("kills", "reads", "gathers", "interrupts", "clears"):
        f[k] = int(f.get(k) or 0)
    if not isinstance(f.get("visits"), dict):     # ★ B3-2：去过几回（「骨田的常客」靠它）
        f["visits"] = {}
    p["foot"] = f
    return f


def today(p: dict) -> int:
    return int(p.get("day") or 0)


def has(p: dict, bk: str, rid: str) -> bool:
    return rid in _books(p).get(bk, {})


def count(p: dict, bk: str) -> int:
    return len(_books(p).get(bk, {}))


def known(p: dict, rid: str) -> bool:
    rec = _books(p).get("relic", {}).get(rid) or {}
    return bool(rec.get("known"))


def studied(p: dict, rid: str) -> bool:
    """自己上手看过没有（★ 与 `known` 分开：看过 = 看出物证那一层，认出来 = 有人给了来处）。"""
    rec = _books(p).get("relic", {}).get(rid) or {}
    return bool(rec.get("studied"))


def unknowns(p: dict) -> list:
    """旧物谱里还留着问号的那些（顺序 = 数据里的顺序）。"""
    b = _books(p).get("relic", {})
    order = list(book("relic").keys())
    return [k for k in order if k in b and not b[k].get("known")]


# ══════════════════════════════════════════════════════════════
# 记录（唯一入口 —— 调用方只管说「他见着了什么」）
# ══════════════════════════════════════════════════════════════
def mark_here(p: dict) -> None:
    """记下「他现在站的这个节点」（起始位置也算去过 —— 不然记录里永远是 0）。"""
    note_visit(p, str(p.get("loc") or ""), str(p.get("node") or ""))


def note_item(p: dict, iid: str) -> str | None:
    """一件东西到手 → 归谱（★ 只记第一次）。返回归到哪本（没归就不回）。"""
    from . import loot as LT                       # 本地 import：避免包装载期的环
    rec = LT.rec_of(iid)
    k = rec.get("kind_key")                        # ★ ASCII 机器键（未鉴定那类走池上的 kind_key）
    bk = KIND_BOOK.get(k) or PICK_BOOK.get(k)
    if not bk:
        return None
    # ★ 旧物谱先给一行问号（捡回来的旧东西，认没认出来是两回事）—— 别的谱到手就算记上
    return bk if _note(p, bk, iid, known=(bk != "relic")) else None


def note_items(p: dict, ids) -> list:
    """一批东西到手 → [(谱, id)]（只有首次记的那几条）。"""
    mark_here(p)
    out = []
    for i in ids:
        bk = note_item(p, str(i))
        if bk:
            out.append((bk, str(i)))
    return out


def sync_bag(p: dict) -> list:
    """跟背包对一次账：拿着的东西 = 见过的东西（★ 背包 ⊆ 谱，只补不删）。

    为什么要有它：老档里那些在谱之前就捡到的、以及任何一条我漏接的拿东西的路，
    开谱那一刻都会补齐 —— 谱只会比背包多（卖掉的、用掉的照样留着）。
    """
    out = []
    for iid in list((p.get("bag") or {}).keys()):
        bk = note_item(p, str(iid))
        if bk:
            out.append((bk, str(iid)))
    return out


def note_kill(p: dict, mid: str) -> bool:
    """打过一只怪（★ 输了也算见过 —— 见过就是见过，由调用方决定记不记）。"""
    mark_here(p)
    b = _books(p)
    if mid not in book("monster"):
        return False
    rec = b["monster"].get(mid)
    if rec:
        rec["kills"] = int(rec.get("kills") or 0) + 1
        _foot(p)["kills"] += 1
        return False
    b["monster"][mid] = {"day": today(p), "kills": 1}
    _foot(p)["kills"] += 1
    return True


def note_read(p: dict, poi_id: str) -> bool:
    """读了一处可读物 → 旧物谱（先给一行问号）。"""
    mark_here(p)
    if poi_id not in book("relic"):
        return False
    _foot(p)["reads"] += 1
    return _note(p, "relic", poi_id, known=False)


def note_pick(p: dict, rid: str) -> bool:
    """捡到一件旧东西（未鉴定/信物）→ 旧物谱（先给一行问号）。"""
    mark_here(p)
    if rid not in book("relic"):
        return False
    return _note(p, "relic", rid, known=False)


def note_visit(p: dict, loc: str, node: str) -> bool:
    """走到一个节点 → 记录（去过哪儿）。"""
    nodes = _foot(p)["nodes"]
    key = "%s:%s" % (loc, node)
    if key in nodes:
        return False
    nodes[key] = today(p)
    return True


def note_step(p: dict, loc: str, node: str) -> int:
    """**走到**一个节点 → 累计去过几回（★ 与 note_visit 的「第一回到」分开：这条每次都加）。

    为什么单独一个口：note_visit 还挂在「拿东西 / 读书 / 打怪」那些地方（mark_here），
    拿它当次数会把「路过一次捡了个东西」也算成一趟 —— 所以计数只认**真的走到**。
    返回这个节点累计去过的回数。
    """
    v = _foot(p)["visits"]
    key = "%s:%s" % (loc, node)
    v[key] = int(v.get(key) or 0) + 1
    return v[key]


def note_gather(p: dict, n: int = 1) -> None:
    _foot(p)["gathers"] += int(n)


def reveal(p: dict, rid: str) -> bool:
    """问对人 → 问号换成名字（返回这条是不是刚认出来的）。"""
    b = _books(p).get("relic") or {}
    rec = b.get(rid)
    if not rec or rec.get("known"):
        return False
    rec["known"] = True
    return True


# ══════════════════════════════════════════════════════════════
# 自己看（P-8）—— 没有 NPC 也能往前挪一格的那条路
# ══════════════════════════════════════════════════════════════
def _held(rid: str) -> dict:
    """这一件的**实物记录**（items 域；`unid_*` 那种挂在池表上的走 loot 一个口）。"""
    from . import loot as LT                       # 本地 import：避免包装载期的环
    return dict(LT.rec_of(str(rid)) or {})


def held_name(rid: str) -> str:
    """手上这一件**手上的**名字（实物域写的那个 —— 玩家在背包里看见的就是它）。

    兜底回谱里的名字（别给裸 id）。
    """
    return str(_held(rid).get("name") or name_of("relic", str(rid)))


def evidence(rid: str) -> str:
    """自己上手能坐实的那一层（**物证句**）—— ★ 唯一来源：实物域写得出的那一句。

    取法（两级，都只在实物域里找）：`lore`（信物 / 遗物那类：「断口往里卷。不是用坏的 ——
    是被人掰断的。」）→ 兜底池表的 `hint`（未鉴定的那两件挂在 `drop_pools` 上：
    「硬的。有点锈。埋在下面很久了。」）。

    为什么是它们：这两句写的都是「这件东西**本身**看得出来什么」，推不出「它从哪儿来」——
    来处那一段永远在 codex 的 `known` 里、只能问对人（`reveal`）。
    两处都没有就回空串（fail-closed：**不编一句**）—— 调用方据此对他说「手上没有这一件」。
    """
    h = _held(rid)
    return str(h.get("lore") or h.get("hint") or "")


def study(p: dict, rid: str) -> bool:
    """自己上手看一遍 → 落档（返回这一遍是不是**头一回**看）。

    ★ 不可逆 · 幂等：看过就是看过 —— 第二遍不再动档（也不会第二次「落档」）；
      看过的**不是**认出来（`known` 那一格一个字不动）。
    """
    rec = _books(p).get("relic", {}).get(str(rid))
    if not rec or rec.get("studied"):
        return False
    rec["studied"] = True
    return True


def revealable(p: dict, npc_id: str) -> list:
    """这个人在场时，玩家那几行问号里他能认出的（旧物谱顺序）。"""
    out = []
    b = _books(p).get("relic", {})
    for rid in book("relic"):
        rec = b.get(rid)
        if not rec or rec.get("known"):
            continue
        if npc_id in (entry("relic", rid) or {}).get("ask", []):
            out.append(rid)
    return out


def _note(p: dict, bk: str, rid: str, known: bool = True) -> bool:
    """进谱（★ 只记第一次；返回这次是不是新记的）。"""
    b = _books(p)
    if rid in b[bk]:
        return False
    rec = {"day": today(p)}
    if bk == "relic":
        rec["known"] = bool(known)
    b[bk][rid] = rec
    return True


def kills_of(p: dict, rid: str) -> int:
    return int((_books(p).get("monster", {}).get(rid) or {}).get("kills") or 0)


def progress(p: dict) -> dict:
    """四本谱的进度：{谱: {"n": 条数, "target": 记满}}(旧物谱 target = 0) + 问号数。"""
    tgt = targets()
    out = {}
    for bk in BOOKS:
        out[bk] = {"n": count(p, bk), "target": int(tgt.get(bk) or 0)}
    out["relic"]["unknown"] = len(unknowns(p))
    return out


def foot(p: dict) -> dict:
    f = _foot(p)
    days = sorted(set(int(d) for d in f["nodes"].values()))
    return {"nodes": dict(f["nodes"]), "kills": f["kills"], "reads": f["reads"],
            "gathers": f["gathers"], "visits": dict(f["visits"]),
            "interrupts": f["interrupts"], "clears": f["clears"], "days": max(1, len(days))}
