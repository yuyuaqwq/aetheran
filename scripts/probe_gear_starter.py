# -*- coding: utf-8 -*-
"""探针：第一件装备那条线（fix7-gear · 支 45）—— 铁匠铺卖入门装 · 材料+钱打造一件 · 商队到货。

为什么有这条线（端到端玩出来的真缺口 · 两份玩家报告）
--------------------------------------------------
p1 报告「体验-8」：镇上买不到任何装备，铁匠铺整张强化表对新玩家是空的 ——
  一个 3 级的玩家手里一件装备都没有；p1「体验-9」：`商队` 只有一句「没在镇上」、没有后续；
  p3 报告「体验-6」：强化卡在材料上，而背包里躺着三样**名字极像但用不了**的东西
  （铁渣 / 旧铁 / 骨头），界面也不说清 `铁屑 ≠ 铁渣`、`硬骨 ≠ 骨头`。

本探针守的**不是「有没有这几件东西」**，是那条链路：**列出来 → 买得起 → 穿得上 → 自己打得出**
（`content-pack-landing §2.1` 那一档「接线判据」：凡被展示出来的，必须有一条吃下它的消费端）。

口径真源（一个字都不新编）
  · `06_…/06_装备获取与支线玩法_v1.md §一 1.1`：**普通**档（系数 1.00）= 镇上铺子直接买 · 普通怪掉
  · 同文件 §一 两条纪律：① 好装备必须靠做事（**稀有以上没有一件是店里买的**，必掉 = 不值钱）
    ⇒ 柜上**只许普通档**；② 材料走生活渠道
  · 同文件 §5.4 表 + `07_装备体系_v2 §四`：低阶（普通 1.00）铺子能买 —— **兜底，让玩家不至于卡住**
  · 同文件 §5.3 制作定位：**不是「造更强的」**，是「定向补短板」—— 产出**同样强度、不同形状**
  · `15_装备逐件数值_v1.md` 抬头：主数值 = 参照属性 × 槽位占比 × 品阶系数（本探针现解析、现重算）
  · `00_总纲/06_阶段交接指南_v3.md §3.1③`：**凑整 · 费用按等级**
  · `29_世界事件_设计_v1.md §五`：商队在路上 / 商队到了（条件 = 主线 3）· `events` 域那两条
  · `18_铺子买卖口径_v1.md`：价 = 基础价 × 品阶系数 × 固定加价（收价 = `items.price`，一个字不动）

判据（一条都不许松）
  ① 货架**现算**：柯尔那家 = items 域里 `shop == "smith"` 的那些（域里现取，不是写死一张清单）
     · 柜上**只有普通档**（纪律①：店里不卖稀有以上）
  ② 价**按等级凑整**：每件 == 基础价 × 品阶系数 × 固定加价 == **12 × `level`**（整数 · 逐件对账）
     · 且每件**买价 > 收价**（P-55：不许「卖回去再买回来」不亏）
  ③ 面板逐行对账（站到 半截铁砧 · 1 级）：强化那 10 行一个字不动 + 货架那一段逐行现算
  ④ 真敲买一件：钱按现算价减、背包 +1、**穿上后面板真变**（走现成的唯一取值口）
  ⑤ 钱不够 ⇒ 只回一句、**档一个字不动**（两态：补够钱 ⇒ 买成）
  ⑥ ★ **按等级解锁**：越级 ⇒ 一句点名（还差几级）、档不动（两态：升到那一级 ⇒ 买成）
  ⑦ ★ 材料 + 钱 ⇒ **打出一件**：料与钱按域里 `forge` 那一格扣、产物进背包、回话逐字（两态）
  ⑧ 料不够 / 钱不够 ⇒ 一句说清差什么、**档一个字不动**（两态）
  ⑨ 打造不够级 ⇒ 同一句点名、档不动（两态）
  ⑩ ★ **商队二选一：真到货**（不是把牌位摘掉）—— 没到 ⇒ 那一句**说清在等什么**（条件从
     `events.period` 现取）；到了 ⇒ 柜上真有货、真买得着；把主线那一步撤回去 ⇒ 又买不到（两态）
  ⑪ ★ **反通胀**（本批最要紧的品味判据）：柜上那几件 + 打造那件的**每一条数值词条**都 ≤
     同槽位同品阶**掉落件**里该词条的最大值（店里卖的 / 自己打的都不许比外头捡的强）；
     且打造件按真源预算现算的 **PE 总量**在「同一档」的量级里（0.85–1.15 —— 同档总量、分布不同）
  ⑫ ★ 材料名不再撞车：**强化要的那几样**与**打造要的那几样**两组名字不相交，且没有
     「只差一个字 / 一方是另一方的子串」的那种对（p3 报告那条）
  ⑬ 静态守卫：代码里没有货架 id / 打造产物 id 的字面量（全从域里现取）· 价与等级只在
     `content/shop.py` 一处算 · 新指令 `打造` 的 handler 真调 `town_gate`
  ⑭ ★ 撤改验证（本探针自己跑「摸掉 ⇒ 当场红」）：
     摸掉 `items.<货>.shop` ⇒ ①④ 的集合与真敲当场变样；摸掉 `level` ⇒ ⑥ 不再拦（越级能买）；
     摸掉 `forge` ⇒ ⑦ 打不出东西来。三处撤改都在本探针里真跑一遍、撤完复原（幂等）。
  ⑮ fail-closed：等级那一刀**没档可判就别判** —— 不传档去问那一家 ⇒ **当场抛**
     （不猜等级、也不静默把带等级的整架摆出来）
  ⑯ 生成器不冲手写格：`scripts/rebuild_shop.py` 重跑一遍，手写的 `shelves`（柯尔那家 · 商队那家）
     原样还在（冲掉 = 铁匠铺那一屏整段消失 —— 静默丢功能，比报错还坏）

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_gear_starter.py
"""
from __future__ import annotations

import ast
import io
import json
import os
import re
import sys

ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.environ.get("AST_PLAN", "C:/Users/yuyu/aetheran-plan")
sys.path.insert(0, ENGINE)
sys.path.insert(0, REPO)

from saintess_engine.package import load_stack            # noqa: E402
from saintess_engine.host.runtime import Host             # noqa: E402

NL = chr(10)
TOWN = "windmill_town"
OK, BAD = [], []
FIXED = 1790308800          # 2026-09-25 12:00 +08:00（昼 —— 与 probe_shop / probe_cmds 同一根假钟）
UID = "u_gear_probe"
SHELF = "smith"             # 柯尔那一家在口径表里的键（**不是**物品 id —— 判据 ⑬ 另钉着）


def ok(msg):
    OK.append(msg)
    print("  OK  %s" % msg)


def bad(msg):
    BAD.append(msg)
    print("  X   %s" % msg)


class Ad(object):
    """最小适配器（照 scripts/e2e_drive.py 的真宿主契约）。"""

    def __init__(self, seed=None):
        self.out = []
        self.saved = {UID: dict(seed)} if seed else {}

    def recv(self):
        return None

    def load_player(self, uid):
        return self.saved.get(uid)

    def save_player(self, uid, data):
        self.saved[uid] = dict(data) if isinstance(data, dict) else data

    def say(self, to, text):
        self.out.append(str(text))


def drive(ad, host, text, uid=UID):
    ad.out = []
    host.handle({"uid": uid, "group_id": "g_gear_probe", "text": text})
    return list(ad.out)


def _load(rel):
    with io.open(os.path.join(REPO, rel), encoding="utf-8") as f:
        return json.load(f)


def _doc(*parts):
    p = os.path.join(PLAN, *parts)
    return io.open(p, encoding="utf-8").read() if os.path.exists(p) else ""


def main():
    items = _load("content/data/items.json")
    maps = _load("content/data/maps.json")
    quests = _load("content/data/quests.json")
    events = _load("content/data/events.json")
    texts = _load("content/data/texts.json")
    recipes = _load("content/data/recipes.json")
    rules = _load("content/rules/shop.json")
    decl = _load("content/data/commands.json")

    def T(key, **slots):
        s = texts[key]["value"]
        for k, v in slots.items():
            s = s.replace("{%s}" % k, str(v))
        return s

    # ── 真源现解析：品阶四档 + 槽位预算（参照属性 × 槽位占比 × 品阶系数）
    _d00 = _doc("06_第一阶段垂直切片", "00_第一阶段内容总纲_v1.md")
    hit = re.search(r"品阶四档：\s*普通\s*([0-9.]+)\s*/\s*精制\s*([0-9.]+)"
                    r"\s*/\s*稀有\s*([0-9.]+)\s*/\s*遗物\s*([0-9.]+)", _d00)
    QMULT = dict(zip(("普通", "精制", "稀有", "遗物"),
                     [float(x) for x in hit.groups()])) if hit else {}
    _d15 = _doc("06_第一阶段垂直切片", "15_装备逐件数值_v1.md")
    _refh = re.search(r"参照\s*=\s*10\s*级六职业平均面板：(.+)", _d15)
    REF = {k: float(v) for k, v in re.findall(r"([a-z_]+)\s+([0-9.]+)", _refh.group(1))} if _refh else {}
    _sh = {}
    _m = re.search(r"槽位占比：武器\s*([0-9]+)%\s*·\s*上甲/下甲各\s*([0-9]+)%\s*·\s*头盔/靴子/饰品各\s*([0-9]+)%", _d15)
    if _m:
        _w, _ab, _h = [int(x) for x in _m.groups()]
        _sh = {"weapon": _w, "armor_top": _ab, "armor_bottom": _ab,
               "helmet": _h, "boots": _h, "accessory": _h}
    if QMULT and REF and _sh:
        ok("真源现解析：品阶四档 %s · 参照面板 %d 项 · 槽位占比 %s（预算那一层现算，不抄一份）"
           % (QMULT, len(REF), {k: "%d%%" % v for k, v in sorted(_sh.items())}))
    else:
        bad("真源解析失败（00 §六 品阶四档 / 15 §一 参照面板与槽位占比）—— 预算重算不了")

    def pe_of(rec):
        """真源 15 §一：主数值 = 参照属性 × 槽位占比 × 品阶系数 ⇒ PE = Σ v / 该属性预算。"""
        slot = str(rec.get("slot") or "")
        base = float(_sh.get(slot, 0)) / 100.0 * float(QMULT.get(str(rec.get("quality")), 1.0))
        tot = 0.0
        for a in rec.get("affixes") or []:
            if a.get("note") or a.get("v") is None:
                continue
            ref = REF.get(str(a.get("stat")))
            if not ref or not base:
                continue
            tot += float(a["v"]) / (ref * base)
        return tot

    st = load_stack(str(REPO), inject={"db_path": ":memory:", "clock": lambda: FIXED})
    del st
    from content import shop as SH                                        # noqa: E402
    from content import cmds_ast as CA                                    # noqa: E402
    from content import town as TW                                        # noqa: E402

    SMITH_NODE = TW._func_node("smith")
    if SMITH_NODE and SMITH_NODE in [n.get("id") for n in maps[TOWN]["nodes"]]:
        ok("柯尔那一站从域里现取：%s（%s）" % (SMITH_NODE, SH.station_name(SHELF)))
    else:
        bad("柯尔那一站取不出来（%r）—— 守卫没法 fail-closed" % SMITH_NODE)

    MK = rules.get("buy_markup")

    # ══════════════════════════════════════════════════════════════
    # ① 货架现算 + ② 价（12 × level）+ ① 纪律①（只有普通档）
    # ══════════════════════════════════════════════════════════════
    P5 = {"cls": "cls_knight", "race": "race_human", "name": "试甲", "level": 5, "exp": 0,
          "gold": 999, "prev": [], "bag": {}, "equipped": {}, "codex": {}, "flags": {}}
    want_ids = [i for i, r in items.items()
                if isinstance(r, dict) and r.get("shop") == SHELF and not str(i).startswith("_")]
    got = SH.goods(P5, shelf=SHELF)
    got_ids = [g["id"] for g in got]
    if want_ids and got_ids == want_ids:
        ok("① 货架现算（5 级）：items 域里 `shop == %r` 的 %d 件 —— %s（域里现取，不写死 id）"
           % (SHELF, len(got_ids), " · ".join(got_ids)))
    else:
        bad("① 货架对不上：探针 %s / 域里 %s" % (got_ids, want_ids))
    _badq = [(g["id"], g["rec"].get("quality")) for g in got if g["rec"].get("quality") != "普通"]
    if got and not _badq:
        ok("① 纪律①（好装备必须靠做事）：柜上**只有普通档**（%d 件全是普通 —— 稀有以上一件都没上柜）"
           % len(got))
    else:
        bad("① 柜上出现了普通档以外的东西（店里卖稀有以上 = 破坏「好装备必须靠做事」）：%s" % _badq)

    _wrong, _flat, _odd = [], [], []
    for g in got:
        q = str(g["rec"].get("quality") or rules.get("quality_default"))
        lv = int(g["rec"].get("level") or 0)
        exp = int(round(float(g["rec"]["price"]) * float(QMULT.get(q, 1.0)) * float(MK)))
        if g["gold"] != exp:
            _wrong.append((g["id"], g["gold"], exp))
        if exp != 12 * lv:                       # ★ 凑整 · 费用按等级（真源 00_v3 §3.1③）
            _odd.append((g["id"], exp, "12 × %d = %d" % (lv, 12 * lv)))
        if g["gold"] <= int(g["rec"]["price"]):
            _flat.append((g["id"], g["gold"], int(g["rec"]["price"])))
    if got and not _wrong:
        ok("② 每件价 = 基础价 × 品阶系数（%.2f）× 固定加价（%s）—— 逐件对账 %d 件"
           % (QMULT.get("普通", 1.0), MK, len(got)))
    else:
        bad("② 价对不上：%s" % _wrong)
    if got and not _odd:
        ok("② ★ 价**按等级凑整**：逐件 == 12 × `level`（%s）—— 全是 12 的整数倍"
           % " · ".join("%s=%d" % (g["rec"]["name"], g["gold"]) for g in got))
    else:
        bad("② 价不是 12 × level 的整数倍（凑整口径破了）：%s" % _odd)
    if got and not _flat:
        ok("② 每件买价 > 收价（P-55：不许「卖回去再买回来」不亏）")
    else:
        bad("② 这几件买价 ≤ 收价（能刷钱）：%s" % _flat)

    # ══════════════════════════════════════════════════════════════
    # ③ 面板逐行对账
    # ══════════════════════════════════════════════════════════════
    db = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_gear.db")
    try:
        os.remove(db)
    except OSError:
        pass
    seed = dict(P5)
    seed.update({"level": 1, "gold": 30, "loc": TOWN, "node": SMITH_NODE})
    ad = Ad(seed)
    host = Host(ad, REPO, inject={"db_path": db, "clock": lambda: FIXED})
    host.boot()

    def stand(loc, node):
        ad.saved[UID]["loc"] = loc
        ad.saved[UID]["node"] = node

    def snap():
        return (ad.saved[UID].get("gold"), dict(ad.saved[UID].get("bag") or {}))

    meta = dict((recipes.get("_meta") or {}).get("enhance") or {})
    _forge_ids = [i for i, r in items.items()
                  if isinstance(r, dict) and r.get("forge") and not str(i).startswith("_")]

    def _src_own(iid):
        """一样料的「从哪儿来」—— **探针另写一份**（不调 `content/matsrc.py`，免得两边同错）。

        ★ Q-22：口径 = `gathering`（池里有它的采集点）+ `drop_pools` × `monsters`（挂了这个池的怪，
          按等级升序、同等级按 id —— 与实现体同一条稳定序）；采集点按 `maps` 的图序 / 节点序摆；
          怪最多点 3 只（实现体的 `MAX_KILL`）。
        """
        _g = _load("content/data/gathering.json")
        _dp = _load("content/data/drop_pools.json")
        _mo = _load("content/data/monsters.json")
        _order = [k for k in maps if not str(k).startswith("_")]

        def _road(_loc, _node):
            _mi = _order.index(_loc) if _loc in _order else len(_order)
            _ns = [n.get("id") for n in (maps.get(_loc) or {}).get("nodes") or []]
            return (_mi, _ns.index(_node) if _node in _ns else len(_ns))

        _spots = []
        for _gid, _v in sorted(_g.items()):
            if _gid.startswith("_"):
                continue
            if not any(str(_e.get("out")) == iid for _e in (_v.get("pool") or [])):
                continue
            _spots.append((_road(_v.get("map"), _v.get("subarea")), _gid, _v))
        parts = []
        for _o, _gid, _v in sorted(_spots)[:3]:            # ★ 采集点也最多 3 处（实现体的 MAX_SPOT）
            _nd = next((n.get("name") for n in (maps.get(_v.get("map")) or {}).get("nodes") or []
                        if n.get("id") == _v.get("subarea")), None)
            parts.append(T("SYS_SRC_GATHER",
                           verb=T("SYS_GATHER_VERB_%s" % str(_v.get("verb") or "").upper()),
                           node=_nd or _v.get("subarea"), point=_v.get("name"),
                           times=int(_v.get("times_per_day") or 1)))
        if len(_spots) > 3:                                 # 余下折进「等 N 处」
            parts.append(str(T("SYS_SRC_GATHER_MORE", n=len(_spots) - 3)).strip())
        _pl = [p for p, v in sorted(_dp.items()) if not p.startswith("_")
               and any(str(_e.get("out")) == iid
                       for _e in list(v.get("entries") or []) + list(v.get("pool") or []))]
        _fo = sorted([(int(m.get("lv") or 0), k, m.get("name")) for k, m in _mo.items()
                      if isinstance(m, dict) and set(_pl).intersection(m.get("drops") or [])])
        if _fo:
            parts.append(T("SYS_SRC_KILL", list=" · ".join(x[2] for x in _fo[:3])))
        return " · ".join(parts)

    def panel_lines(p):
        out = [T("SYS_ENHANCE_SHOP")]
        for lv in range(1, int(meta.get("cap") or 0) + 1):
            stp = recipes.get("rc_enh_%02d" % lv) or {}
            need = " · ".join("%s ×%d" % (items[e["id"]]["name"], int(e["n"]))
                              for e in stp.get("inputs") or [])
            out.append(T("SYS_ENHANCE_ROW", lv=lv, need=need, gold=int(stp.get("gold") or 0),
                         rate="%d%%" % round(float(stp.get("rate") or 0) * 100)))
        rows = SH.goods(p, shelf=SHELF)
        if rows:
            out.append(T("SYS_SMITH_GOODS"))
            for g in rows:
                out.append(T("SYS_SHELF_ROW", icon=g["rec"].get("icon") or "",
                             name=g["rec"].get("name") or g["id"], gold=g["gold"],
                             level=SH.level_need(g["rec"])))
        _st1 = recipes.get("rc_enh_01") or {}
        _enh = []
        for e in _st1.get("inputs") or []:
            nm = items[e["id"]]["name"]
            if nm not in _enh:
                _enh.append(nm)
        _cr = []
        for _i in sorted(_forge_ids):
            for e in (_forge_rec(items[_i])["inputs"]):
                nm = items[e["id"]]["name"]
                if nm not in _cr:
                    _cr.append(nm)
        out.append(T("SYS_SMITH_MATS", enh=" · ".join(_enh), craft=" · ".join(_cr)))
        # ★ Q-22：料名后面那一栏「这几样料从哪儿来」（实现体在 `cmds_recipe.smith` —— 出处现算）
        out.append(T("SYS_SMITH_SRC_HEAD"))
        for e in _st1.get("inputs") or []:
            out.append(T("SYS_SMITH_SRC_ROW", name=items[e["id"]]["name"],
                         where=_src_own(e["id"]) or T("SYS_SRC_UNKNOWN")))
        out.append(T("SYS_SMITH_CRAFT_HEAD"))
        for _i in sorted(_forge_ids):
            _f = _forge_rec(items[_i])
            need = " · ".join("%s ×%d" % (items[e["id"]]["name"], int(e["n"]))
                              for e in _f["inputs"])
            out.append(T("SYS_SMITH_CRAFT_ROW", name=items[_i]["name"], need=need,
                         gold=_f["gold"], level=_f["level"]))
        out.append(T("SYS_SMITH_CRAFT_ASK"))
        return out

    def _forge_rec(rec):
        f = dict(rec.get("forge") or {})
        return {"level": int(f.get("level") or 0), "gold": int(f.get("gold") or 0),
                "inputs": list(f.get("inputs") or [])}

    ad.saved[UID]["gold"] = 30
    ad.saved[UID]["bag"] = {}
    before = json.dumps(ad.saved[UID], ensure_ascii=False, sort_keys=True)
    lines = drive(ad, host, "铁匠铺")
    want = panel_lines(ad.saved[UID])
    if lines == want:
        ok("③ 站到 柯尔那儿敲『铁匠铺』⇒ 面板逐行对账过（%d 行：强化 %d 行一个字不动 + 货架 + "
           "两条线的料 + 打造 %d 行）" % (len(lines), int(meta.get("cap") or 0), len(_forge_ids)))
    else:
        _d = [(i, a, b) for i, (a, b) in enumerate(zip(lines, want)) if a != b]
        bad("③ 面板对不上：len %d vs %d · %s" % (len(lines), len(want), _d[:2]))
    if json.dumps(ad.saved[UID], ensure_ascii=False, sort_keys=True) == before:
        ok("③ 面板是**只读**的（敲『铁匠铺』前后档逐字相同）")
    else:
        bad("③ 敲『铁匠铺』动了档")

    # ── ② 之一：1 级只看得见「够级」的那几件（货架按等级解锁）
    lv1_ids = [g["id"] for g in SH.goods(ad.saved[UID], shelf=SHELF)]
    lv5_ids = [g["id"] for g in SH.goods(P5, shelf=SHELF)]
    if lv1_ids and set(lv1_ids) < set(lv5_ids):
        ok("② 货架按等级解锁：1 级看得见 %d 件，5 级看得见 %d 件（越级的那几件不摆出来）"
           % (len(lv1_ids), len(lv5_ids)))
    else:
        bad("② 等级闸没生效：1 级 %s / 5 级 %s" % (lv1_ids, lv5_ids))

    # ══════════════════════════════════════════════════════════════
    # ④ 买 + ⑤ 钱不够 + ⑥ 越级
    # ══════════════════════════════════════════════════════════════
    g0 = next(g for g in SH.goods(ad.saved[UID], shelf=SHELF) if g["id"] == lv1_ids[0])
    g0name = str(g0["rec"]["name"])
    ad.saved[UID]["gold"] = 30
    ad.saved[UID]["bag"] = {}
    lines = drive(ad, host, "购买 " + g0name)
    exp = [T("SYS_SHOP_BUY_OK", icon=g0["rec"].get("icon") or "", name=g0name,
             n=1, gold=g0["gold"], left=30 - g0["gold"])]
    if lines == exp and snap() == (30 - g0["gold"], {g0["id"]: 1}):
        ok("④ 真买一件（%s · %d 铜板）：钱 30 → %d · 背包 %s ×1（回话与档都对）"
           % (g0name, g0["gold"], 30 - g0["gold"], g0["id"]))
    else:
        bad("④ 买一件不对：回话 %s · 档 %r" % (lines[:2], snap()))

    # ④ 之二：穿上后面板真变（走现成的唯一取值口，不另算一遍）
    from content import panel_build as PB                                  # noqa: E402
    cap0 = PB.hp_cap(ad.saved[UID], strict=False)
    lines = drive(ad, host, "装备 " + g0name)
    cap1 = PB.hp_cap(ad.saved[UID], strict=False)
    eq = (ad.saved[UID].get("equipped") or {}).get(str(g0["rec"].get("slot")))
    _chg = cap1 != cap0 if g0["rec"].get("affixes") and g0["rec"]["affixes"][0].get("stat") == "hp" else True
    if eq == g0["id"] and _chg:
        ok("④ 穿上那件：`equipped[%s]` 真落（%s）—— 与面板同一个取值口（`gear_stats`）"
           % (g0["rec"].get("slot"), eq))
    else:
        bad("④ 穿上没落档 / 面板没动：%s · 上限 %s → %s · 回话 %s" % (eq, cap0, cap1, lines[:2]))

    # ⑤ 钱不够（两态）
    ad.saved[UID]["gold"] = g0["gold"] - 1
    ad.saved[UID]["bag"] = {}
    b4 = snap()
    lines = drive(ad, host, "购买 " + g0name)
    if lines == [T("SYS_SHOP_POOR", lack=1)] and snap() == b4:
        ok("⑤ 钱不够 ⇒ 只回「铜板不够 —— 还差 1 个。」且**档一个字不动**（不扣钱、不给货）")
    else:
        bad("⑤ 钱不够那一下：%s · 档 %r" % (lines[:2], snap()))
    ad.saved[UID]["gold"] = 30
    ad.saved[UID]["bag"] = {}
    _ok5b = drive(ad, host, "购买 " + g0name) == exp
    if _ok5b:
        ok("⑤ 两态：把差的那一枚补上 ⇒ 同一句指令当场买成（钱/背包都对）")
    else:
        bad("⑤ 两态那一半没过（补够钱还是买不成）：%s" % snap())

    # ⑥ 越级（两态）
    _top = [g for g in SH.goods(P5, shelf=SHELF) if g["id"] not in lv1_ids]
    if _top:
        gT = sorted(_top, key=lambda g: int(g["rec"].get("level") or 0))[0]
        gTname = str(gT["rec"]["name"])
        ad.saved[UID]["gold"] = 999
        ad.saved[UID]["bag"] = {}
        b4 = snap()
        lines = drive(ad, host, "购买 " + gTname)
        exp = [T("SYS_SHELF_LOCK", name=gTname, level=SH.level_need(gT["rec"]),
                 now=int(ad.saved[UID].get("level") or 0))]
        if lines == exp and snap() == b4:
            ok("⑥ ★ 按等级解锁：1 级点名买「%s」⇒ 一句点名（要 %d 级）、**档一个字不动**"
               % (gTname, SH.level_need(gT["rec"])))
        else:
            bad("⑥ 越级那一下：%s · 档 %r" % (lines[:2], snap()))
        ad.saved[UID]["level"] = SH.level_need(gT["rec"])
        ad.saved[UID]["gold"] = 999
        ad.saved[UID]["bag"] = {}
        lines = drive(ad, host, "购买 " + gTname)
        if snap() == (999 - gT["gold"], {gT["id"]: 1}):
            ok("⑥ 两态：升到那一级 ⇒ 同一句指令当场买成（%d 铜板）" % gT["gold"])
        else:
            bad("⑥ 两态那一半没过：%s · 档 %r" % (lines[:2], snap()))
    else:
        bad("⑥ 柜上找不出一件「越级」的货 —— 这条判据没跑")

    # ══════════════════════════════════════════════════════════════
    # ⑦ 打造（两态）+ ⑧ 料/钱不够 + ⑨ 不够级
    # ══════════════════════════════════════════════════════════════
    if not _forge_ids:
        bad("⑦ 域里一件带 `forge` 的都没有 —— 打造那条线没落地")
    else:
        fid = sorted(_forge_ids)[0]
        frec = items[fid]
        f = _forge_rec(frec)
        fname = str(frec["name"])
        ad.saved[UID]["level"] = f["level"]
        ad.saved[UID]["gold"] = f["gold"] + 10
        ad.saved[UID]["bag"] = {e["id"]: int(e["n"]) for e in f["inputs"]}
        lines = drive(ad, host, "打造 " + fname)
        _want = [T("SYS_SMITH_CRAFT_OK", icon=frec.get("icon") or "", name=fname)]
        for a in frec.get("affixes") or []:
            if a.get("note"):
                _want.append(T("SYS_GEAR_AFFIX_NOTE", note=a["note"]))
            else:
                _want.append(T("SYS_GEAR_AFFIX_ROW",
                               label=T("SYS_STAT_%s" % str(a["stat"]).upper()),
                               value="%g" % float(a["v"])))
        _want.append(T("SYS_MONEY", gold=10))
        _left = {k: v for k, v in (ad.saved[UID]["bag"] or {}).items() if v}
        if lines == _want and ad.saved[UID]["gold"] == 10 \
                and _left == {fid: 1}:
            ok("⑦ ★ 材料 + 钱 ⇒ 打成一件（%s）：料按 `forge.inputs` 扣（%s 扣光）、钱 %d → 10、"
               "产物进背包 —— 回话与词条逐字"
               % (fname, " · ".join("%s×%d" % (items[e["id"]]["name"], int(e["n"]))
                                    for e in f["inputs"]), f["gold"] + 10))
        else:
            bad("⑦ 打造那一下不对：回话 %s · 档 %r" % (lines[:4], snap()))
        if snap()[1].get(fid) == 1:
            ok("⑦ 打造产物落的是**背包**（不是直接穿上 —— 穿不穿由玩家自己敲『装备』）")

        # ⑧ 料不够 / 钱不够（两态）
        for _case, _bag, _gold, _lack in (
                ("料不够", {}, f["gold"] + 10,
                 " · ".join("%s ×%d" % (items[e["id"]]["name"], int(e["n"])) for e in f["inputs"])),
                ("钱不够", {e["id"]: int(e["n"]) for e in f["inputs"]}, 0,
                 T("SYS_GOLD_X", n=f["gold"]))):
            ad.saved[UID]["bag"] = dict(_bag)
            ad.saved[UID]["gold"] = _gold
            b4 = snap()
            lines = drive(ad, host, "打造 " + fname)
            _need = " · ".join("%s ×%d" % (items[e["id"]]["name"], int(e["n"])) for e in f["inputs"])
            # ★ Q-22 补（试玩 P3 复测 F-3）：缺料那一支现在**跟着出处**（表头 + 逐样一行 · 只列真缺的），
            #   判据跟着加严 —— 回话必须**恰好**是「差什么那一句 + 缺那几样的出处行」。
            _lack_e = [e for e in f["inputs"] if int(dict(_bag).get(e["id"], 0)) < int(e["n"])]
            exp = [T("SYS_SMITH_CRAFT_MISSING", name=fname, need=_need, gold=f["gold"], lack=_lack)]
            if _lack_e:
                exp.append(T("SYS_SMITH_SRC_HEAD"))
                for e in _lack_e:
                    exp.append(T("SYS_SMITH_SRC_ROW", name=items[e["id"]]["name"],
                                 where=_src_own(e["id"]) or T("SYS_SRC_UNKNOWN")))
            if lines == exp and snap() == b4:
                ok("⑧ %s ⇒ 一句说清差什么、**档一个字不动**（%s）" % (_case, lines[0][:46]))
            else:
                bad("⑧ %s 那一下：%s · 档 %r" % (_case, lines[:2], snap()))
        ad.saved[UID]["bag"] = {e["id"]: int(e["n"]) for e in f["inputs"]}
        ad.saved[UID]["gold"] = f["gold"] + 10
        _ok8b = drive(ad, host, "打造 " + fname) == _want
        if _ok8b:
            ok("⑧ 两态：把料与钱都补齐 ⇒ 同一句指令当场打成")
        else:
            bad("⑧ 两态那一半没过：%s" % snap())

        # ⑨ 不够级（两态）
        if f["level"] > 1:
            ad.saved[UID]["level"] = 1
            ad.saved[UID]["bag"] = {e["id"]: int(e["n"]) for e in f["inputs"]}
            ad.saved[UID]["gold"] = f["gold"] + 10
            b4 = snap()
            lines = drive(ad, host, "打造 " + fname)
            exp = [T("SYS_SHELF_LOCK", name=fname, level=f["level"], now=1)]
            if lines == exp and snap() == b4:
                ok("⑨ 打造也按等级：1 级上手 ⇒ 一句点名（要 %d 级）、档不动" % f["level"])
            else:
                bad("⑨ 打造越级那一下：%s · 档 %r" % (lines[:2], snap()))
            ad.saved[UID]["level"] = f["level"]
            if drive(ad, host, "打造 " + fname) == _want:
                ok("⑨ 两态：升到那一级 ⇒ 同一句指令当场打成")
            else:
                bad("⑨ 两态那一半没过：%s" % snap())

    # ══════════════════════════════════════════════════════════════
    # ⑩ 商队：真到货（两态）
    # ══════════════════════════════════════════════════════════════
    ckeys = [k for k in SH.shelf_keys() if SH.shelf_rec(k).get("event")]
    if not ckeys:
        bad("⑩ 口径表里没有挂在事件上的那一家 —— 商队那条判据没跑")
    else:
        ck = ckeys[0]
        cids = [i for i, r in items.items() if isinstance(r, dict) and r.get("shop") == ck]
        _ev = str(SH.shelf_rec(ck).get("event"))
        _per = (events.get(_ev) or {}).get("period") or {}
        _qid = str(_per.get("from_main") or _per.get("until_main") or "")
        _qname = str((quests.get(_qid) or {}).get("name") or "")
        if cids and _qname:
            cid = sorted(cids)[0]
            crec = items[cid]
            cname = str(crec["name"])
            # 没到：那一句**说清在等什么**
            ad.saved[UID]["flags"] = {}
            ad.saved[UID]["level"] = max(5, SH.level_need(crec))
            ad.saved[UID]["gold"] = 999
            ad.saved[UID]["bag"] = {}
            stand(TOWN, "wt_gate_n")
            lines = drive(ad, host, "商队")
            if T("SYS_CARAVAN_WHY", name=_qname) in lines:
                ok("⑩ 商队没到 ⇒ 那一句**说清在等什么**（现取：走完『%s』那条 · p1 报告「体验-9」）"
                   % _qname)
            else:
                bad("⑩ 商队没到时那句话不对：%s" % lines[:4])
            b4 = snap()
            lines = drive(ad, host, "购买 " + cname)
            if lines == [T("SYS_CARAVAN_WHY", name=_qname)] and snap() == b4:
                ok("⑩ 没到货就买不到：同一句话（不是「柜上没有」）+ 档不动")
            else:
                bad("⑩ 没到货那一下：%s · 档 %r" % (lines[:2], snap()))
            # 到了：真有货、真买得着
            ad.saved[UID]["flags"] = {"quests_done": [_qid]} if _qid else {}
            ad.saved[UID]["gold"] = 999
            ad.saved[UID]["bag"] = {}
            lines = drive(ad, host, "商队")
            _row = T("SYS_SHELF_ROW", icon=crec.get("icon") or "", name=cname,
                     gold=SH.price_of(crec, p=ad.saved[UID]), level=SH.level_need(crec))
            if T("SYS_CARAVAN_GOODS") in lines and _row in lines:
                ok("⑩ 商队到了 ⇒ 柜上真有货（%s）—— 那一屏里逐字对得上" % cname)
            else:
                bad("⑩ 到货那一屏不对：%s" % lines[:5])
            _price = SH.price_of(crec, p=ad.saved[UID])
            lines = drive(ad, host, "购买 " + cname)
            if snap() == (999 - _price, {cid: 1}):
                ok("⑩ 到货那件**真买得着**（%d 铜板 · 走铺子同一个价那个口）" % _price)
            else:
                bad("⑩ 到货那件买不着：%s · 档 %r" % (lines[:2], snap()))
            ad.saved[UID]["flags"] = {}                      # 撤回去 ⇒ 又买不到（两态）
            ad.saved[UID]["gold"] = 999
            ad.saved[UID]["bag"] = {}
            lines = drive(ad, host, "购买 " + cname)
            if lines == [T("SYS_CARAVAN_WHY", name=_qname)] and snap() == (999, {}):
                ok("⑩ 两态：把主线那一步撤回去 ⇒ 同一句指令又买不到（事件那一格真在管这件事）")
            else:
                bad("⑩ 两态那一半没过：%s" % lines[:2])
        else:
            bad("⑩ 商队那一家没挂货 / 条件取不出来：%s / %r" % (cids, _qid))

    # ══════════════════════════════════════════════════════════════
    # ⑪ 反通胀（逐词条 + 预算量级）
    # ══════════════════════════════════════════════════════════════
    shop_gear = [i for i in want_ids] + list(_forge_ids)
    _strong, _pe_bad = [], []
    for iid in shop_gear:
        rec = items[iid]
        slot, q = str(rec.get("slot") or ""), str(rec.get("quality") or "")
        peers = [r for k, r in items.items()
                 if isinstance(r, dict) and k not in shop_gear and r.get("slot") == slot
                 and r.get("quality") == q]
        for a in rec.get("affixes") or []:
            if a.get("note") or not isinstance(a.get("v"), (int, float)):
                continue
            vals = [float(b["v"]) for r in peers for b in (r.get("affixes") or [])
                    if b.get("stat") == a["stat"] and not b.get("note")
                    and isinstance(b.get("v"), (int, float))]
            if vals and float(a["v"]) > max(vals):
                _strong.append((iid, a["stat"], a["v"], max(vals)))
        if iid in _forge_ids:
            pe = pe_of(rec)
            if not (0.85 <= pe <= 1.15):
                _pe_bad.append((iid, round(pe, 3)))
    if shop_gear and not _strong:
        ok("⑪ ★ 反通胀：柜上那 %d 件 + 打造那 %d 件，**每一条数值词条**都不超过同槽位同品阶"
           "掉落件里该词条的最高值（店里卖的 / 自己打的都不比外头捡的强）"
           % (len(want_ids), len(_forge_ids)))
    else:
        bad("⑪ 有东西比同档掉落件更强（那是「必得的东西变值钱」，破坏反通胀）：%s" % _strong)
    if _forge_ids and not _pe_bad:
        ok("⑪ ★ 打造件按真源预算现算的 PE 总量落在**同档**量级里（0.85–1.15 ⇒ 「同样强度、"
           "不同形状」而不是「造更强的」）：%s"
           % " · ".join("%s PE=%.3f" % (items[i]["name"], pe_of(items[i])) for i in _forge_ids))
    elif _forge_ids:
        bad("⑪ 打造件的 PE 总量不在同档量级：%s（真源 §5.3：不许造更强的）" % _pe_bad)
    else:
        bad("⑪ 没有打造件 —— 这一条没跑")

    # ══════════════════════════════════════════════════════════════
    # ⑫ 材料名不再撞车（两组料不相交 + 没有近名对）
    # ══════════════════════════════════════════════════════════════
    enh_mats = [e["id"] for e in (recipes.get("rc_enh_01") or {}).get("inputs") or []]
    cr_mats = [e["id"] for i in _forge_ids for e in (_forge_rec(items[i])["inputs"])]
    enh_names = [str(items[i]["name"]) for i in enh_mats]
    cr_names = [str(items[i]["name"]) for i in sorted(set(cr_mats))]
    _pair = []
    for a in enh_names:
        for b in cr_names:
            if a in b or b in a or (len(a) >= 2 and len(b) >= 2 and a[-1] == b[-1]):
                _pair.append("%s / %s" % (a, b))
    if enh_names and cr_names and not _pair:
        ok("⑫ ★ 两组料的名字不相交、也没有「一方是另一方的子串 / 同一个字收尾」的近名对 —— "
           "强化要 %s ｜ 打造要 %s（p3 报告那条「铁屑≠铁渣 · 硬骨≠骨头」从此看得清）"
           % (" · ".join(enh_names), " · ".join(cr_names)))
    else:
        bad("⑫ 两组料里还有近名（玩家会看错）：%s ｜ %s → %s" % (enh_names, cr_names, _pair))
    # ★ 名字仍近（如 `铁渣` vs `铁屑`）—— 那就让**每件东西自己说清归哪条线**：
    #   ① 强化料的 `desc` 必须写明强化（两样都没有别的去处）、不许提打造；
    #   ② 打造料的 `desc` 不许提强化（不许被那条线认领）；
    #   ③ **与强化料共用一个字**的那几样（今天 = 铁渣 · 骨头 —— p3 报告点名的近名对）
    #      必须在 `desc` 里写明打造（`查看 <东西>` 那一屏就是这一条的证据）。
    #   判据现算（谁与谁同字是数据算出来的，不是写死一张名单）。
    _used, _conf = [], [i for i in sorted(set(cr_mats))
                        if any(set(str(items[i]["name"])) & set(str(items[j]["name"]))
                               for j in enh_mats)]
    for i in enh_mats:
        d0 = str(items[i].get("desc") or "")
        if "强化" not in d0 or "打造" in d0:
            _used.append((items[i]["name"], d0[:30]))
    for i in sorted(set(cr_mats)):
        d0 = str(items[i].get("desc") or "")
        if "强化" in d0 or (i in _conf and "打造" not in d0):
            _used.append((items[i]["name"], d0[:30]))
    if not _used:
        ok("⑫ ★ 每样料在『查看』那一屏也分得开：强化料写明强化、打造料不提强化，"
           "而与强化料**共用一个字**的那几样（%s）各自写明了打造 —— 判据现算（不看名单）"
           % " · ".join(items[i]["name"] for i in _conf))
    else:
        bad("⑫ 这几样料的 `desc` 说不清归哪条线（或写到对面那条线上）：%s" % _used)

    # ══════════════════════════════════════════════════════════════
    # ⑬ 静态守卫
    # ══════════════════════════════════════════════════════════════
    _lit, _lvl, _readers = [], [], []
    _ids = set(want_ids) | set(_forge_ids)
    for fn in sorted(os.listdir(os.path.join(REPO, "content"))):
        if not fn.endswith(".py"):
            continue
        src = io.open(os.path.join(REPO, "content", fn), encoding="utf-8").read()
        for i in _ids:
            if re.search(r"['\"]%s['\"]" % re.escape(i), src):
                _lit.append("%s:%s" % (fn, i))
        if re.search(r"['\"]shelves['\"]", src) and fn != "shop.py":
            _lvl.append(fn)
        if "shop.json" in src:
            _readers.append(fn)
    if not _lit:
        ok("⑬ 静态：代码里没有货架 / 打造产物的 id 字面量（%d 个 id 一个都没写进代码 —— 全从域里现取）"
           % len(_ids))
    else:
        bad("⑬ 代码里写死了 id：%s" % _lit)
    if not _lvl:
        ok("⑬ 静态：几家铺子那两张表（`shelves`）只在 content/shop.py 被读 —— 别处不另判一遍")
    else:
        bad("⑬ 别处也在读 `shelves` 那张表：%s" % _lvl)
    if _readers == ["shop.py"]:
        ok("⑬ 静态：读铺子口径表的只有 content/shop.py 一处（价 / 等级 / 货架一个口）")
    else:
        bad("⑬ 读铺子口径表的地方不止一处：%s" % _readers)
    _h = str((decl.get("forge") or {}).get("bind", {}).get("handler") or "")
    calls = set()
    if _h:
        _mod, _fn = _h.split(":")
        tree = ast.parse(io.open(os.path.join(REPO, "content", _mod.split(".")[-1] + ".py"),
                                 encoding="utf-8").read())
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == _fn:
                calls = {getattr(x.func, "id", "") for x in ast.walk(n)
                         if isinstance(x, ast.Call)}
    if _h and "town_gate" in calls:
        ok("⑬ 新指令 `%s` 的 handler（%s）真调 `town_gate`（守卫一个口 —— 与 probe_cmds ⑰ 同款）"
           % ("打造", _h))
    else:
        bad("⑬ 新指令的 handler 没走 town_gate：%r · %s" % (_h, sorted(calls)))

    # ══════════════════════════════════════════════════════════════
    # ⑮ fail-closed：等级那一刀没档可判就别判（不许猜、不许整架放行）
    # ══════════════════════════════════════════════════════════════
    _raised = ""
    try:
        SH.goods(None, shelf=SHELF)
        _raised = "（没抛）"
    except RuntimeError as exc:
        _raised = str(exc)
    except Exception as exc:                                          # noqa: BLE001
        _raised = "抛的不是 RuntimeError：%r" % (exc,)
    if _raised and "没抛" not in _raised and "RuntimeError" not in _raised:
        ok("⑮ ★ fail-closed：不传档去问那一家（货上有 `level`）⇒ **当场抛**（不猜等级、"
           "也不静默把整架摆出来）—— %s" % _raised[:52])
    else:
        bad("⑮ 不传档也没抛 —— 等级那一刀会静默失效：%s" % _raised)

    # ══════════════════════════════════════════════════════════════
    # ⑯ 生成器不许把「手写那几家」冲掉（重跑 rebuild_shop 之后 shops 还在）
    # ══════════════════════════════════════════════════════════════
    sys.path.insert(0, os.path.join(REPO, "scripts"))
    try:
        import rebuild_shop as RBSH                                       # noqa: E402
        _obj = RBSH.build(RBSH.parse_coeffs(), _load("content/data/items.json"),
                          _load("content/data/npcs.json"))
        _merged = RBSH.merge_hand_shelves(_obj, rules)
        _same = _merged.get("shelves") == rules.get("shelves") and bool(_merged.get("shelves"))
    except Exception as exc:                                              # noqa: BLE001
        _same = False
        bad("⑯ 生成器那一关跑不起来：%r" % (exc,))
    if _same:
        ok("⑯ ★ `scripts/rebuild_shop.py` 重跑一遍，**手写那几家（`shelves`）原样还在**"
           "（%s）—— 生成物不冲手写格（冲掉 = 铁匠铺那一屏整段消失，静默丢功能）"
           % " · ".join(sorted(rules["shelves"])))
    else:
        bad("⑯ 生成器会把 `shelves` 冲掉 —— 得先给 rebuild_shop 加「带过去」那一支")

    # ══════════════════════════════════════════════════════════════
    # ⑭ 撤改验证（摸掉 ⇒ 当场红 —— 撤完复原，幂等）
    # ══════════════════════════════════════════════════════════════
    _tbl = CA._data("items")
    _miss = []
    _keep = dict(_tbl[g0["id"]])
    _tbl[g0["id"]].pop("shop", None)                      # ① 摸掉 shop 那一格
    try:
        _shelf_after = [x["id"] for x in SH.goods(P5, shelf=SHELF)]
        ad.saved[UID]["lod"] = 0
        ad.saved[UID]["level"] = 5
        ad.saved[UID]["gold"] = 999
        ad.saved[UID]["bag"] = {}
        stand(TOWN, SMITH_NODE)
        _lines = drive(ad, host, "购买 " + g0name)
        if g0["id"] not in _shelf_after and _lines == [T("SYS_SHOP_NOGOOD", name=g0name)]:
            ok("⑭ 撤改验证：把 `%s.shop` 摸掉 ⇒ 货架当场少一件、人也买不着（判据 ①④ 确实守着这一格）"
               % g0["id"])
        else:
            bad("⑭ 摸掉 shop 之后没反应（判据飘了）：货架 %s · 回话 %s" % (_shelf_after, _lines[:2]))
    finally:
        _tbl[g0["id"]].update(_keep)
    _keep = dict(_tbl[gT["id"]])
    _tbl[gT["id"]].pop("level", None)                     # ② 摸掉 level 那一格
    try:
        ad.saved[UID]["level"] = 1
        ad.saved[UID]["gold"] = 999
        ad.saved[UID]["bag"] = {}
        _lines = drive(ad, host, "购买 " + gTname)
        if snap() == (999 - gT["gold"], {gT["id"]: 1}):
            ok("⑭ 撤改验证：把 `%s.level` 摸掉 ⇒ 1 级也能买到那件（等级那一格真的在拦）" % gT["id"])
        else:
            bad("⑭ 摸掉 level 之后没反应：%s · 档 %r" % (_lines[:2], snap()))
    finally:
        _tbl[gT["id"]].update(_keep)
    if _forge_ids:
        _keep = {k: v for k, v in _tbl[fid].items()}
        _tbl[fid].pop("forge", None)                      # ③ 摸掉 forge 那一格
        try:
            _after = [i for i, r in _tbl.items()
                      if isinstance(r, dict) and r.get("forge")]
            ad.saved[UID]["level"] = 9
            ad.saved[UID]["gold"] = 999
            ad.saved[UID]["bag"] = {e["id"]: int(e["n"]) for e in f["inputs"]}
            _lines = drive(ad, host, "打造 " + fname)
            if fid not in _after and _lines == [T("SYS_FORGE_NOSUCH", name=fname)]:
                ok("⑭ 撤改验证：把 `%s.forge` 摸掉 ⇒ 炉子上打不出这件了（判据 ⑦ 确实守着这一格）"
                   % fid)
            else:
                bad("⑭ 摸掉 forge 之后没反应：%s · 回话 %s" % (_after, _lines[:2]))
        finally:
            _tbl[fid] = _keep
    # 复原核对（幂等）：把三处撤改都撤回去之后，货架与打造都得回原样
    _back = sorted(x["id"] for x in SH.goods(P5, shelf=SHELF))
    _backf = sorted(i for i, r in _tbl.items() if isinstance(r, dict) and r.get("forge"))
    if _back == sorted(want_ids) and _backf == sorted(_forge_ids):
        ok("⑭ 三处撤改撤完 ⇒ 货架与打造名单**逐字回原样**（本探针幂等，不留副作用）")
    else:
        bad("⑭ 撤改没复原干净：货架 %s / 打造 %s" % (_back, _backf))

    # ══════════════════════════════════════════════════════════════
    # ★ g4-②：随机装甲不再抢打造位（`no_drop`）
    #   真源核实（06 §一 1.1）：普通档「镇上三家铺子直接买 · 普通怪掉」**两路都有**
    #     ⇒ 铺子那三件入门装**照旧可被动态格抽到**（那是真源授权的，见下一条正面判据）；
    #   而打造件那条真源行（`06 §1.1-b`）给的路只有「打造」，不在 §一 1.1 那 16 件里
    #     ⇒ 真源没授权它掉落 ⇒ 本批按 fail-closed 排掉（`items.no_drop`）。
    # ══════════════════════════════════════════════════════════════
    from content import loot as LT22                                      # noqa: E402
    _sch22 = json.load(io.open(os.path.join(REPO, "schemas", "items.schema.json"), encoding="utf-8"))
    _nd_prop = (((_sch22.get("patternProperties") or {}).get("^i_[a-z0-9_]+$") or {})
                .get("properties") or {}).get("no_drop")
    _nd_ids = sorted(i for i, r in items.items() if isinstance(r, dict) and r.get("no_drop"))
    if _nd_prop and _nd_ids == [fid]:
        ok("⑰ ★ `no_drop` 那一格：schema 里声明了（`items.schema.json`）· 域里只有打造件那一件（%s）"
           % " · ".join(_nd_ids))
    else:
        bad("⑰ `no_drop` 那一格不对：schema=%s · 域里=%s" % (bool(_nd_prop), _nd_ids))
    _no_route = [i for i in _nd_ids if not (items[i].get("shop") or items[i].get("forge"))]
    if not _no_route:
        ok("⑰ ★ fail-closed：带 `no_drop` 的每一件都**另有获取路**（`shop` / `forge`）—— "
           "排掉落不等于把一件东西锁死（今天 %d 件）" % len(_nd_ids))
    else:
        bad("⑰ 这几件既不能掉、又没别的路（玩家永远拿不到）：%s" % _no_route)
    # 真跑：动态格抽 400 次，打造件一次都不许出现；铺子那三件**必须**抽得到（真源授权两路）
    _seen22 = set()
    import random as _R22                                                 # noqa: E402
    _rnd22 = _R22.Random(20260926)
    for _i22 in range(400):
        for _pool22 in ("unid_common", "unid_tower"):
            for _e22 in (LT22.pools().get(_pool22) or {}).get("pool") or []:
                if str(_e22.get("out") or "").startswith("*"):
                    _got22 = LT22._resolve(str(_e22["out"]), _e22, 9, _rnd22, items)
                    if _got22:
                        _seen22.add(_got22)
    _leak = sorted(x for x in _nd_ids if x in _seen22)
    _shop_hit = sorted(x for x in (want_ids or []) if x in _seen22)
    if not _leak:
        ok("⑰ ★ 真跑 400 轮动态格（`unid_common` / `unid_tower` 的 `*armor_random`）：打造件 "
           "一次都没被抽出来（%d 件候选里抽到 %d 种）" % (len(items), len(_seen22)))
    else:
        bad("⑰ 打造件还是能被随机装甲抽到：%s" % _leak)
    if len(_shop_hit) == len(set(want_ids)):
        ok("⑰ ★ 另一面（真源授权的那一半）：铺子那 %d 件入门装**照旧抽得到** —— "
           "真源 `06 §一 1.1` 明写普通档「铺子买 · 普通怪掉」两路都有（不排它们）"
           % len(_shop_hit))
    else:
        bad("⑰ 铺子那几件被排掉了（真源授权两路都有，排掉 = 越权）：抽到 %s / 应有 %s"
            % (_shop_hit, sorted(want_ids)))
    # 反证（有牙）：临时把那一格摘掉 ⇒ 打造件当场出现在动态格里
    _keep22 = dict(items[fid])
    try:
        items[fid].pop("no_drop", None)
        _again22 = set()
        _rnd22 = _R22.Random(20260926)
        for _i22 in range(400):
            for _pool22 in ("unid_common", "unid_tower"):
                for _e22 in (LT22.pools().get(_pool22) or {}).get("pool") or []:
                    if str(_e22.get("out") or "").startswith("*"):
                        _g22 = LT22._resolve(str(_e22["out"]), _e22, 9, _rnd22, items)
                        if _g22:
                            _again22.add(_g22)
        if fid in _again22:
            ok("⑰ 反证（撤改验证）：把 `%s.no_drop` 摘掉 ⇒ 它当场从动态格里冒出来"
               "（这一格真的在管事，不是注释）" % fid)
        else:
            bad("⑰ 反证不成立：摘掉 `no_drop` 之后打造件仍抽不到（那一格没被读）")
    finally:
        items[fid] = _keep22

    # ══════════════════════════════════════════════════════════════
    # ★ g4-①：两条线的料名**彻底分开**（p3 报告 体验-6 · 改名跟账）
    #   `铁屑/铁渣/旧铁` 与 `硬骨/骨头` 那两组「名字极像但用不了的东西」——
    #   本批把**打造那一路**的两样改名（`矿渣` / `兽骨`），与强化那两样（`铁屑` / `硬骨`）
    #   从「同字 / 子串 / 只差一个字」里彻底出来。判据**现算**（谁与谁像由数据算，不写名单）。
    # ══════════════════════════════════════════════════════════════
    _enh22 = [str(items[i]["name"]) for i in enh_mats]
    _cr22 = [str(items[i]["name"]) for i in sorted(set(cr_mats))]

    def _near22(a, b):
        """两个名字像不像（空串 = 不像，否则回那一句像在哪 —— 判据的**唯一**一处）。"""
        if a == b:
            return "同名"
        if a in b or b in a:
            return "一个套着另一个"
        if a and b and a[-1] == b[-1]:
            return "同一个字收尾"
        if set(a) & set(b):
            return "共用了字（%s）" % "".join(sorted(set(a) & set(b)))
        if len(a) == len(b) and sum(1 for x, y in zip(a, b) if x != y) == 1:
            return "只差一个字"
        return ""

    _pair22 = ["%s ↔ %s（%s）" % (a, b, _near22(a, b))
               for a in _enh22 for b in _cr22 if _near22(a, b)]
    if _enh22 and _cr22 and not _pair22:
        ok("① ★ 两条线的料名彻底分得开（强化 %s ｜ 打造 %s）：不共用字 · 不互为子串 · 不同字收尾 · "
           "不「只差一个字」—— 判据现算（不看名单）" % (" · ".join(_enh22), " · ".join(_cr22)))
    else:
        bad("① 两条线里还有像的名字：%s" % _pair22)
    # 材料 / 垃圾 / 线索 这几类里不许重名（玩家按名字在铁匠铺 / 打造屏上点它们）——
    # ★ 装备那边有四品阶同名一族（`重上甲` ×4 —— B4-20：显示时缀品阶），那是**有意的**，不在此列。
    _dup22 = {}
    for _i22, _r22v in items.items():
        if isinstance(_r22v, dict) and _r22v.get("name") \
                and str(_r22v.get("kind_key") or "") in ("material", "junk", "clue", "food", "tool"):
            _dup22.setdefault(str(_r22v["name"]), []).append(_i22)
    _dup22 = {k: v for k, v in _dup22.items() if len(v) > 1}
    if not _dup22:
        ok("① ★ 材料 / 垃圾 / 线索 / 食物这几类里没有重名两件（玩家按名字点得准 —— "
           "装备四品阶同名那一族不在此列，显示时缀品阶）")
    else:
        bad("① 这几类里有重名：%s" % _dup22)
    # 反证（有牙）：改名**之前**那一组（铁屑/铁渣 · 硬骨/骨头）在同一判词下当场被点出四处
    _old_pair = ["%s ↔ %s（%s）" % (a, b, _near22(a, b))
                 for a, b in (("铁屑", "铁渣"), ("硬骨", "骨头")) if _near22(a, b)]
    if len(_old_pair) == 2:
        ok("① 反证（有牙）：改名前的两组（铁屑 ↔ 铁渣 · 硬骨 ↔ 骨头）在同一判词下当场红 —— %s"
           % " ｜ ".join(_old_pair))
    else:
        bad("① 反证不成立（旧名字居然不算像）：%s" % _old_pair)
    # 两态互锁的那一半：生成器登记了改名 + 谱里那句「攒着能修东西」不再上屏
    import rebuild_codex as RBX22                                         # noqa: E402
    _fx22 = getattr(RBX22, "NAME_FIXUP", {})
    _cx22 = json.load(io.open(os.path.join(REPO, "content", "data", "codex.json"), encoding="utf-8"))
    _bad22b = [i for i in _fx22
               if str((_cx22.get("material") or {}).get(i, {}).get("name")) != _fx22[i]["new"]]
    _oldp = sorted({str((_cx22.get("material") or {}).get(i, {}).get("name"))
                    for i in _fx22} & {_fx22[i]["old"] for i in _fx22})
    if _fx22 and not _bad22b and not _oldp:
        ok("① ★ 改名跟账三处对齐：生成器登记 %d 条（两态互锁）· 材料谱里是新名 · "
           "旧名在材料谱里一个字都不剩" % len(_fx22))
    else:
        bad("① 改名没对齐：登记 %s · 材料谱没跟上 %s · 材料谱里还留着旧名 %s"
            % (sorted(_fx22), _bad22b, _oldp))

    # ══════════════════════════════════════════════════════════════
    # ⑱ ★ Q-22：料的出处（现算 —— 铁屑只在挖掘里出是**设计**，不是漏）
    #   真源 `05_玩法数值口径_v1 §三`：「强化材料 采矿产「铁屑」· 怪掉「硬骨」」两句话分两条路。
    #   本节的三个方向：
    #     ① 强化料每一样都算得出出处（不许走 `SYS_SRC_UNKNOWN` 那一句 —— 它是 fail-closed 的哨兵，
    #        只该在域里真没给出产路时出现）
    #     ② 那两句真源行在域里**成立**：铁屑 不许出现在任何 `drop_pools` 里（= 它靠采）·
    #        硬骨 必须至少有一个池装着（= 它靠怪掉）
    #     ③ 「一天能刷几个」现算打印（**不设阈值**：`05_ §九` 把「一天能采到多少」列在待校准里
    #        ⇒ 本批只把数摆出来，权重一格不动）
    # ══════════════════════════════════════════════════════════════
    _eh = [e["id"] for e in ((recipes.get("rc_enh_01") or {}).get("inputs") or [])]
    _no_src = [i for i in _eh if not _src_own(i)]
    if _eh and not _no_src:
        ok("⑱ ★ Q-22 料的出处：强化那 %d 样（%s）每一样都**算得出**出处 —— 不走 fail-closed 那句"
           % (len(_eh), " · ".join(items[i]["name"] for i in _eh)))
    else:
        bad("⑱ 这几样强化料算不出出处（玩家会看到 fail-closed 那句）：%s" % (_no_src or "（没有强化料）"))
    _dp_all = _load("content/data/drop_pools.json")
    _mo_all = _load("content/data/monsters.json")
    _g_all = _load("content/data/gathering.json")

    def _spots18(iid):
        """这件料出在几个采集点上（探针自己扫域 —— 不看 `content/matsrc.py`）。"""
        return [gid for gid, v in sorted(_g_all.items()) if not gid.startswith("_")
                and any(str(e.get("out")) == iid for e in (v.get("pool") or []))]

    _dangling, _routeless, _routes = [], [], []
    for _m in _eh:
        _pl = [p for p, v in _dp_all.items() if not str(p).startswith("_")
               and any(str(e.get("out")) == _m for e in list(v.get("entries") or []) + list(v.get("pool") or []))]
        _ft = sorted({m.get("name") for m in _mo_all.values()
                      if isinstance(m, dict) and set(_pl).intersection(m.get("drops") or [])})
        _sp = _spots18(_m)
        if _pl and not _ft:
            _dangling.append((_m, _pl))                     # 挂在池上、可没有怪掉它
        if not _pl and not _sp:
            _routeless.append(_m)                           # 两条路都没有 = 拿不到
        _routes.append("%s ← %s" % (items[_m]["name"],
                                    " · ".join(x for x in (
                                        ("%d 个采集点" % len(_sp)) if _sp else "",
                                        ("%d 只怪掉" % len(_ft)) if _ft else
                                        ("（池 %s）" % " · ".join(_pl) if _pl else "")) if x)))
    if not _dangling and not _routeless:
        ok("⑱ ★ 每一样强化料都有**至少一条出产路**，且凡挂在掉落池上的都有怪真掉它（没有悬空引用）—— %s"
           % " ｜ ".join(_routes))
    else:
        bad("⑱ 强化料的出产路有问题（悬空池 %s · 一条路都没有 %s）" % (_dangling, _routeless))
    _g18 = _load("content/data/gathering.json")

    def _daily18(iid):
        """这件料的一天期望产出（件/游戏日）—— 池权重 × n 均值 × 一天能翻的遍数（现算，不手打）。"""
        _t = 0.0
        for _gid, _v in sorted(_g18.items()):
            if _gid.startswith("_"):
                continue
            _pool = _v.get("pool") or []
            _w = sum(int(e.get("w", 1) or 1) for e in _pool)
            for _e in _pool:
                if str(_e.get("out")) != iid:
                    continue
                _rng = _e.get("n")
                _en = (_rng[0] + _rng[1]) / 2.0 if isinstance(_rng, list) else 1.0
                _n = int(_v.get("times_per_day") or 1)
                # 反复采那一层（第 2 遍起只给零星、最后一遍空手）—— 挖掘点一天 1 遍，不走那两层
                _t += int(_e.get("w", 1) or 1) / float(_w) * _en * (_n if _n == 1 else (_n - 1) * 0.5)
        return _t
    print("     · 「一天能刷几个」（**采集那一路**的日产期望 · 件/游戏日）：%s"
          % " ｜ ".join("%s ⇒ %s" % (items[_m]["name"], "%.2f" % _daily18(_m)) for _m in _eh))
    print("       （怪掉那一路是「每杀一只几只」—— 数据在 `drop_pools` 的池权重里，本探针不另算一份）")
    print("       （真源 `05 §九` 把「一天能采到多少」列在**待校准**里 —— 本批只把数摆出来，权重一格不动）")

    print(NL + "----")
    print("通过 %d / 失败 %d" % (len(OK), len(BAD)))
    if BAD:
        print("红的是：")
        for b in BAD:
            print("  - %s" % b)
        return 1
    print("结果：全绿 ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
