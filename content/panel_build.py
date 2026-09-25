# -*- coding: utf-8 -*-
"""面板构造（内容侧）—— 把 (职业, 等级, 加点) 算成引擎 PanelStack 要的声明。

★ 分工：本文件只负责「准备每层的数」；逐键合并 / 钳制 / 归因由引擎形状 `PanelStack` 做。
★ 引擎键名映射也在这里（宪法名 → 战斗侧认的名字），crit 要率化（引擎的 crit 是率，不是数值）。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .cmds_ast import T     # 文案真源只有 texts 域（B3-6b-2d）：分段名只传槽位
from . import alloc as ALLOC   # ★ P-34：「这档实际分了多少」只走它（`of_record`）

_DATA = Path(__file__).resolve().parent / "data"
_CLASSES = None

K_DEF, K_RATE = 300, 500

KEYMAP = {
    "hp": "max_hp", "mo": "max_mp", "atk": "atk", "matk": "matk", "def": "def",
    "res": "mdef", "spd": "spd", "hit": "hit", "eva": "dodge", "block": "block",
    "heal_pow": "heal_pow", "critdmg": "crit_dmg",
}
INT_KEYS = ("max_hp", "max_mp")

#: ★ B3-14：**引擎把这两个当「率」读**（不是数值）——
#:   `ext_combat/battle/actions.py` 的 `random.random() < st["crit"]`、
#:   `landing.py:_roll_dodge` 的 `min(st["dodge"], 0.40)`。
#:   所以宪法键 `crit` / `eva`（**数值**，rating）必须率化后再进面板 ——
#:   原先只率化了 crit：`eva` 原样传（骑士 10、刺客 20）⇒ 引擎按率读、cap 到 0.40
#:   ⇒ **六职业恒定 40% 闪避**（数值差异全被 cap 吃掉）；怪物那边 `dodge` 干脆没接线。
RATE_KEYS = ("crit", "eva")


def rate_of(rating: float) -> float:
    """数值 → 率（宪法 F3 形状 `r/(r+K_rate)`）。**玩家与怪共用这一把尺**。"""
    r = float(rating or 0)
    if r <= 0:
        return 0.0
    return r / (r + K_RATE)

_REGISTRY: dict = {}          # 栈 id → decl（panel_layers_fn 的供体）
#: ★ B3-28 ①：栈 id 里**必须带「人」那一维**（`_person_tag`）——
#:   栈的声明里烤着这一个人的加点 / 装备 / 增益，原先键只有 `职业@等级`
#:   ⇒ 同进程里同职业同等级的两个玩家共用一格（后造的盖先造的：实测甲开战后面板
#:   被乙敲一条指令就带走，见 `_notes.md` §B3-28 ① 的重现输出）。
#:   可复用性照旧：同一个人的同一份档反复构建落在**同一个键**上（那一格反复用）。
#:   不做淘汰（`pop`）：已经开战的那只 actor 身上带着它的栈 id，淘汰它 = 那一场当场崩
#:   （引擎 `stats.py` 查不到栈就抛 `panel_layers 无此栈`）。条目数 = 见过的人数 × 职业等级，
#:   每条几 KB —— 先照实记着，要收再按「战斗结束」回收（本批没做）。


def _fingerprint(alloc, equipment, buffs) -> str:
    """这一档自己那几个数（加点 / 装备 / 增益）的指纹 —— 没有身份时的「人」那一维。"""
    parts = []
    for tag, d in (("a", alloc), ("g", equipment), ("b", buffs)):
        cells = sorted("%s=%r" % (k, v) for k, v in (d or {}).items())
        parts.append(tag + ":" + "|".join(cells))
    return hashlib.sha1(";".join(parts).encode("utf-8")).hexdigest()[:12]


def _person_tag(uid, alloc, equipment, buffs) -> str:
    """面板栈键里的**「人」那一维**（B3-28 ①）—— 有身份用身份，没身份用这一档的指纹。

    两档都不许省：省了就退回「同职业同等级共用一格」。为什么要留指纹这一档 ——
    `hp_cap(档)` / `actor_of_record(档)` 这类调用点手上**只有档、没有 ctx**（生产宿主
    读回来的档不含 `uid`：`host/store_factory.py::_IDENTITY_KEYS` 把身份列剔掉了；
    handler 那三个槽位 `group_id/uid/player` 才是拿得到身份的地方）。
    所以：**能拿到 uid 的调用点一律传进来**（战斗 / 属性页），拿不到的用指纹兜住 ——
    两种都不撞格，且都不编数。
    """
    u = str(uid or "").strip()
    if u:
        return "u-" + u
    return "f-" + _fingerprint(alloc, equipment, buffs)


class PanelMissing(Exception):
    """档上没有可用的面板 ⇒ 属性 / 生命上限算不出来。

    ★ 不猜数：面板是**唯一来源**（`classes` 域那条职业 + 等级 + 加点 + 装备 + 增益）——
      没有职业就没有面板，宁可当场喊出来，也不许拿 100 / 别人的职业垫上
      （`apply.initial_save` 与 `cmds_ast.DEFAULT_PLAYER` 原先各写死 100 就是这么来的）。
    """


def classes() -> dict:
    global _CLASSES
    if _CLASSES is None:
        _CLASSES = json.loads((_DATA / "classes.json").read_text(encoding="utf-8"))
    return _CLASSES


def cls_rec(cls_id: str) -> dict:
    """职业 id → `classes` 域里那条记录。

    ★ 两种失败都当场抛（fail-closed：`fail-closed-boundaries` §1）：
      空 = 「还没择业」（建号第二步还没落地）· 有值却不在域里 = 「声明错了」（点名 + 列出现有的）。
    """
    cid = str(cls_id or "").strip()
    if not cid:
        raise PanelMissing("档上没有职业（cls 空）—— 没有职业就没有面板，属性 / 生命上限算不出来")
    c = classes().get(cid)
    if c is None:
        raise PanelMissing("职业 %r 不在 classes 域里（有的：%s）"
                           % (cid, " · ".join(sorted(classes()))))
    return c


def panel_of(cls_id: str, level: int, alloc: dict | None = None) -> dict:
    """宪法键名的面板：基础 + 成长×(级-1) + 加点换算。"""
    c = cls_rec(cls_id)
    p = dict(c["base"])
    for k, v in c["growth"].items():
        p[k] = p.get(k, 0) + v * (level - 1)
    for stat, n in (alloc or {}).items():
        for k, v in (c["conv"].get(stat) or {}).items():
            p[k] = p.get(k, 0) + v * n
    return p


def to_engine(p: dict) -> dict:
    """宪法键名 → 引擎键名；crit / eva（数值）→ 率（引擎把这两个当率读）。

    闪避的率化在这儿只服务**没有面板栈**的调用点（`panel_of` 那些直接读数的地方）；
    战斗侧走 `build_actor` 的 `rate` 层（同一把尺 `rate_of`）。
    """
    out = {}
    for k, v in p.items():
        if k in RATE_KEYS:
            out[KEYMAP.get(k, k)] = rate_of(v)
            continue
        if k == "critdmg":
            out["crit_dmg"] = v
            continue
        if k in KEYMAP:
            out[KEYMAP[k]] = v
    return out


def _layers_of(cls_id: str, level: int, alloc: dict | None):
    """三层**数值**键（不含 crit / eva）：职业基础 / 成长 / 加点。
    `crit` / `eva` 是非线性率（F3），三层相加无意义 ⇒ 单独走 `set` 层（率化）。"""
    c = cls_rec(cls_id)
    base = dict(c["base"])
    grow = {k: v * (level - 1) for k, v in c["growth"].items()}
    attr: dict = {}
    for stat, n in (alloc or {}).items():
        for k, v in (c["conv"].get(stat) or {}).items():
            attr[k] = attr.get(k, 0) + v * n
    drop = RATE_KEYS
    # ★ 不再往层里塞等级：引擎 `stats.actor_stats` 已把 `level` 统一带出
    #   （真源 = actor["level"]，玩家与怪一视同仁）—— 内容侧只给面板属性。
    return (to_engine({k: v for k, v in base.items() if k not in drop}),
            to_engine({k: v for k, v in grow.items() if k not in drop}),
            to_engine({k: v for k, v in attr.items() if k not in drop}))


def build_actor(cls_id: str, level: int, alloc: dict | None = None,
                equipment: dict | None = None, buffs: dict | None = None,
                *, stack_prefix: str = "aetheran", uid: str | None = None) -> dict:
    """造一个玩家 actor：自带 panel_stack（栈 id）与战斗侧字段。

    `buffs` —— `{面板键: 乘数}`（B2-6 食物增益那类），走**最后**一层 `mul`：
      乘层必须排在加层之后（引擎逐层作用：先加后乘，值才是对的）；
      只乘列出的键（引擎面板栈的 per-key mul），不写 `apply: whole`。

    ★ B3-28 ①：`uid` = **身份**（handler 那三个槽位里的第二个）。拿得到就传 ——
      栈 id 会带上它（`_person_tag`）；拿不到（只有档的调用点）走这一档的指纹，
      同样不撞格。**两个不同的人（或两份不同的档）永远不会共用同一格。**
    """
    base_e, grow_e, attr_e = _layers_of(cls_id, level, alloc)
    gear_e = {KEYMAP.get(k, k): v for k, v in (equipment or {}).items()}

    p = panel_of(cls_id, level, alloc)
    # ★ B3-14：crit / eva 两条**数值 → 率**。率化的输入 = 面板三层 + **装备那一份**
    #   （装备词条里 `crit` / `eva` 是真有的：items 域 17 件带 crit、5 件带 eva）。
    #   原先只率化 crit 且**没带装备**（gear 的 crit 写在 add 层、随后被 set 层盖掉 ⇒ 白穿）；
    #   eva 干脆没率化 ⇒ 引擎按率读 10/20、cap 到 0.40 ⇒ 六职业恒定 40% 闪避。
    rate_vals = {
        "crit": rate_of(p.get("crit", 0) + float(gear_e.get("crit", 0) or 0)),
        "dodge": rate_of(p.get("eva", 0) + float(gear_e.get("dodge", 0) or 0)),
    }

    # ★ B3-28 ①：键 = `前缀.职业@等级`（**可复用的那一维**，同级同职业共用得到它）
    #   + `#<人那一维>`（身份或这一档的指纹）。原先只有前半截 ⇒ 撞格。
    sid = "%s.%s@%d#%s" % (stack_prefix, cls_id, level,
                           _person_tag(uid, alloc, equipment, buffs))
    keys = sorted(set(base_e) | set(grow_e) | set(attr_e) | set(gear_e))
    _REGISTRY[sid] = {
        "version": 1,
        "base": {"mode": "value", "value": {k: 0 for k in keys + ["crit", "dodge"]}},
        "layers": [
            {"id": "prof_base", "src": T("SYS_PANEL_PROF_BASE"), "group": "base", "mode": "add",
             "keys": keys, "values": {k: base_e.get(k, 0) for k in keys}},
            {"id": "growth", "src": T("SYS_PANEL_GROWTH"), "group": "base", "mode": "add",
             "keys": keys, "values": {k: grow_e.get(k, 0) for k in keys}},
            {"id": "attr", "src": T("SYS_PANEL_ATTR"), "group": "attr", "mode": "add",
             "keys": keys, "values": {k: attr_e.get(k, 0) for k in keys}},
            {"id": "gear", "src": T("SYS_PANEL_GEAR"), "group": "gear", "mode": "add",
             "keys": keys, "values": {k: gear_e.get(k, 0) for k in keys}},
            # crit / eva 是非线性率（F3），三层相加无意义 ⇒ 内容侧算好后用 set 层一次性写入
            {"id": "rate", "src": T("SYS_PANEL_CRIT_RATE"), "group": "rate", "mode": "set",
             "keys": ["crit", "dodge"], "values": dict(rate_vals)},
        ] + ([{"id": "food", "src": T("SYS_PANEL_FOOD"), "group": "buff", "mode": "mul",
               "keys": sorted(buffs), "values": dict(buffs)}] if buffs else []),
        "emit": {"int_keys": [k for k in INT_KEYS if k in keys], "round": 4},
    }
    actor = {k: sum((base_e, grow_e, attr_e, gear_e)[i].get(k, 0) for i in range(4)) for k in keys}
    actor.update({
        "class_name": cls_id,
        "level": level,
        "panel_stack": sid,
        "panel_refs": {},
        "panel_flags": {},
    })
    return actor


def stacks() -> dict:
    """panel_layers_fn 的供体：栈 id → decl。"""
    return _REGISTRY


# ══════════════════════════════════════════════════════════════
# ★ P-27：生命上限的**唯一来源**（就是本文件这个面板）
# ══════════════════════════════════════════════════════════════
def gear_and_buffs(record) -> tuple:
    """档 → `(装备面板数值, 食物增益乘数)` —— 走 `gear` 那两个唯一取值口。

    ★ 战斗 actor 与「档上的上限」必须吃**同一份**装备 / 增益，否则又是两个源。
    """
    from . import gear as GB                  # 本地 import：免得包装载期成环
    rec = record if isinstance(record, dict) else {}
    return (GB.gear_stats(rec) or None), (GB.food_buff(rec) or None)


def actor_of_record(record, *, uid: str | None = None) -> dict:
    """档 → 战斗那只 actor（职业 + 等级 + **档上实际那份加点** + 装备 + 增益）——**唯一口**。

    ★ P-34：上一批（P-27）把「装备 / 增益」收成了一个口（`gear_and_buffs`），
      这一批把「加点」也收了（`alloc.of_record`）。上游（战斗 / 生命上限 / 属性页 /
      下一批的**装备门槛**）要「这档的面板」一律走这里 —— 别再各自 `rec.get("alloc")`。
    ★ B3-28 ①：`uid` 透传给 `build_actor`（拿得到就传 —— 栈 id 带上身份；拿不到用指纹）。
    """
    rec = record if isinstance(record, dict) else {}
    cls = str(rec.get("cls") or "").strip()
    cls_rec(cls)                               # 空 / 不在域里 ⇒ 当场抛（fail-closed）
    lv = max(1, int(rec.get("level") or 1))
    gear, buffs = gear_and_buffs(rec)
    return build_actor(cls, lv, ALLOC.of_record(rec), gear, buffs=buffs, uid=uid)


def hp_cap(record, *, strict: bool = True, uid: str | None = None):
    """玩家档 → **生命上限**（宪法键 `hp_max`）。唯一来源：本函数（职业面板）。

    两种失败分开处置（fail-closed 纪律：`fail-closed-boundaries` §1）：

      · 档上 `cls` **空**（建号第二步「选职业」还没走完）= **还没声明** ⇒
        `strict=False` 回 `None`（呈现面照实说「未定」，不猜数）；`strict=True` 抛
        `PanelMissing` —— 需要数字的地方（回血 / 战斗）不许拿 100 或别的职业垫上。
      · 档上 `cls` **有值、但 classes 域里没有** = **声明错了** ⇒ 一律抛（点名 + 列出现有的）。

    档上那一格 `hp_max` 由本函数**派生**（原先 `apply.initial_save` 与 `cmds_ast.DEFAULT_PLAYER`
    各写死 100 ⇒ 与面板两个源；现在唯一的一处是 `cmds_ast._p`，出档口现算）。把门的是
    `cls_rec`（空 / 不在域里都点名）—— 本函数不再自己判一遍。
    """
    rec = record if isinstance(record, dict) else {}
    cls = str(rec.get("cls") or "").strip()
    if not cls and not strict:
        return None                            # 还没择业 ⇒ 上限未定（不猜数、也不崩）
    # ★ P-34：档 → 面板只走一个口（职业 + 等级 + **档上实际那份加点** + 装备 + 增益）
    # ★ B3-28 ①：uid 拿得到就传（栈 id 带上身份）；拿不到走这一档的指纹，一样不撞格。
    return int(actor_of_record(rec, uid=uid)["max_hp"])
