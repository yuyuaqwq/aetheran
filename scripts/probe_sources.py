# -*- coding: utf-8 -*-
"""探针：出产渠道（B3-22）—— ★「一件东西从哪来」的**端到端**门禁。

为什么要有它（台账 P-7 / P-11 那两条账的教训，2026-09-25 复核）
------------------------------------------------------------------
那两条账（「强化材料没有出产渠道」「九件套装件没有出产渠道」）**当时已结**，
但全仓**没有一条判据**守着「玩家真拿得到」—— 出产条目可以挂在走不到的节点上、
挂在碰不上的怪身上、或被时辰门槛整条挡掉，四档老判据一条都不红。
⇒ 这条探针补的就是它（判据只加强，不替旧判据）。

五档判据
--------
① 形状档   三个域读得到（gathering / drop_pools / monsters / recipes）
② 跨域档   ★ 每个「必须有渠道」的 id 至少有一条产出口 —— **五路现算，不手写镜像表**：
             采集点池 · 怪掉池（含嵌套池 + `*<格>_random` 动态格）· 配方出产 · 委托奖励
③ 可复算档 ★ 每条产出口的**位置可达**：采集点 (map, subarea) 在图上、怪栖息地有真节点，
             且从风车镇出发真走得到（现算：出北/东/西 + 图内拓扑（star 互通 · chain 前后）+ 进塔）
④ 接线档   ★ **真跑 handler**：采集真进背包 · 战斗真进背包（换人 × 换日 × 换时辰扫到出现为止）
⑤ 品味档   ★ 同名两件（非装备里不许有两件同名）· ★ 图鉴那一栏的名字与物品表**同一个名**

「必须有渠道」是谁定的（不手写清单）
  · 强化材料 = recipes 里 `enhance` 那 10 档的 inputs（现算）
  · 套装件   = items 里 `i_set_*`
  · 配方原料 = recipes 里 8 道菜的 inputs（「配方真做得出来」= 每样食材都有渠道）
  · 配方成品 = 8 道菜的 out（由配方那一路供着）

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_sources.py
Python 用 3.12（3.11 假红）。
"""
from __future__ import annotations

import asyncio
import os
import random
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, REPO)
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                      # noqa: E402

DB = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db")
FIXED = [100.0 * 7200 + 3600.0]

st = load_stack(str(REPO), inject={"db_path": DB, "clock": lambda: FIXED[0]})
st.install()

from content import calendar as CAL                                 # noqa: E402
from content import cmds_ast as CA                                  # noqa: E402
from content import cmds_battle as CB                               # noqa: E402
from content import combat as CMB                                   # noqa: E402
from content import cmds_gather as CG                               # noqa: E402
from content import loot as LT                                      # noqa: E402

SCALE = CAL.scale_seconds()
CAL.facade.bind_host(clock=lambda: FIXED[0])

G = st.domain("gathering")
DP = st.domain("drop_pools")
IT = st.domain("items")
MON = st.domain("monsters")
MAPS = st.domain("maps")
RC = st.domain("recipes")
Q = st.domain("quests")
CX = st.domain("codex")

fails = []
ok = lambda m: print("  ✓ " + m)
bad = lambda m: (fails.append(m), print("  ✗ " + m))

print("探针：出产渠道（强化材料 / 套装件 / 配方原料）")

# ── ① 形状档 ──────────────────────────────────────────────────────
enh = {k: v for k, v in RC.items() if v.get("kind_key") == "enhance"}
cook = {k: v for k, v in RC.items() if v.get("kind_key") == "cook"}
(ok if (G and DP and MON and enh and cook) else bad)(
    "三个域读得到 —— 采集 %d 点 · 掉落池 %d · 怪 %d · 强化 %d 档 · 烹饪 %d 道"
    % (len(G), len(DP), len(MON), len(enh), len(cook)))

#: 「必须有渠道」的那批 id —— **全部现算**（不写死清单）
MATS = sorted({e["id"] for v in enh.values() for e in (v.get("inputs") or [])})
SETS = sorted(k for k in IT if str(k).startswith("i_set_"))
INGS = sorted({e["id"] for v in cook.values() for e in (v.get("inputs") or [])})
FOODS = sorted({v["out"] for v in cook.values()})
MUST = sorted(set(MATS) | set(SETS) | set(INGS) | set(FOODS))
print("  · 强化材料 %s · 套装件 %d 件 · 配方原料 %d 样 · 配方成品 %d 道 ⇒ 合 %d 个 id"
      % (MATS, len(SETS), len(INGS), len(FOODS), len(MUST)))

# ── ② 产出口：五路现算 ────────────────────────────────────────────
def _grid_ids(grid: str, qual):
    """动态项 `*<格>_random` → 真能挑出来的那批 id（格表走 loot._GRID_SLOTS 单一真源）。"""
    slots = next((s for g, s in LT._GRID_SLOTS.items() if grid.startswith(g)), None)
    if slots is None:
        return []
    out = [k for k, v in IT.items() if v.get("slot") in slots]
    if qual:
        f = [k for k in out if IT[k].get("quality") in qual]
        if f:
            out = f
    return out


SITES: dict = {}


def _add(iid, kind, where, **kw):
    SITES.setdefault(iid, []).append(dict(kind=kind, where=where, **kw))


for gid, v in G.items():
    for e in (v.get("pool") or []):
        _add(str(e.get("out")), "gather", gid, w=int(e.get("w", 1) or 1),
             map=v.get("map"), node=v.get("subarea"), verb=v.get("verb"),
             times=int(v.get("times_per_day") or 1))
for mid, m in MON.items():
    def _walk(pid, seen):
        if pid in seen:
            return
        seen.add(pid)
        p = DP.get(pid) or {}
        for e in (p.get("entries") or []) + (p.get("pool") or []):
            o = str(e.get("out"))
            w = int(e.get("w", 1) or 1)
            if o.startswith("*"):
                for k in _grid_ids(o[1:], e.get("quality")):
                    _add(k, "monster", mid, pool=pid, w=w, grid=True,
                         maps=m.get("habitat") or {})
            elif o.startswith("dp_"):
                _walk(o, seen)
            else:
                _add(o, "monster", mid, pool=pid, w=w, maps=m.get("habitat") or {})
                if o.startswith("unid_"):
                    _walk(o, seen)
    for pid in (m.get("drops") or []):
        _walk(pid, set())
for rid, r in RC.items():
    if r.get("out"):
        _add(str(r["out"]), "recipe", rid)
for qid, q in Q.items():
    for r in (q.get("rewards") or []):
        if isinstance(r, dict) and r.get("item"):
            _add(str(r["item"]), "quest", qid)

_no_site = [k for k in MUST if not SITES.get(k)]
(ok if not _no_site else bad)("★ 每个必须有渠道的 id 都有产出口（%d 个 id · 产出口 %d 条 · 没有的 %s）"
                              % (len(MUST), sum(len(v) for v in SITES.values()), _no_site or "无"))

# ── ③ 可复算档：位置可达 ─────────────────────────────────────────
REACH = {("windmill_town", "wt_gate_n")}
for loc, node in (("belt_north", "bn_bone"), ("belt_east", "be_birch"), ("belt_west", "bw_old_ferry")):
    REACH.add((loc, node))                      # 三条出门路（handler 里的落点）
_ch = True
while _ch:                                      # 图内：star 互通 / chain 前后
    _ch = False
    for (loc, node) in list(REACH):
        for nb in CA._neighbors(loc, node):
            if (loc, nb) not in REACH:
                REACH.add((loc, nb))
                _ch = True
_ent = (MAPS.get("old_watchtower") or {}).get("entrance") or {}
if (_ent.get("map"), _ent.get("node")) in REACH:        # 进塔 + 塔内 12 间
    for n in (MAPS.get("old_watchtower") or {}).get("nodes") or []:
        REACH.add(("old_watchtower", n["id"]))

_unreach = []
for iid in MUST:
    for s in SITES.get(iid, []):
        if s["kind"] == "gather":
            if (s["map"], s["node"]) not in REACH:
                _unreach.append((iid, s["where"], s["map"], s["node"]))
        elif s["kind"] == "monster":
            hb = s["maps"] or {}
            if not any((mp, nd) in REACH for mp in (hb.get("maps") or []) for nd in (hb.get("nodes") or [])):
                _unreach.append((iid, s["where"], hb.get("maps"), hb.get("nodes")))
(ok if not _unreach else bad)("★ 每条产出口都在**走得到**的地方（可达节点 %d 个 · 走不到的 %s）"
                              % (len(REACH), _unreach[:4] or "无"))

# ── ④ 接线档：真跑 handler ───────────────────────────────────────
UID_CAP = 24            # 换多少人
DAY_CAP = 8             # 换多少个游戏日
HODS = (12, 23, 6, 19)  # 换几个时辰（夜 20→5 · 昼 8→18）
BATTLE_ATT = 60         # 同一人最多打几场（遇敌那一挑是随机的）


def run_ag(ag):
    async def _d():
        return [str(x) async for x in ag]
    return asyncio.run(_d())


def _at(day: int, hod: float):
    """把宿主钟拨到「第 day+N 个游戏日的 hod 点」。"""
    FIXED[0] = (100 + day) * SCALE + (hod / 24.0) * SCALE
    CAL.facade.bind_host(clock=lambda: FIXED[0])


def _gear(level: int) -> dict:
    """一身体面的**普通**装备（试兵器用；按该等级能穿的来 ⇒ 不越门槛）。

    纯夹具：只为了让「真打一场」打得赢 —— 不是判据的一部分。
    """
    eq = {}
    for slot in ("weapon", "armor_top", "armor_bottom", "helmet", "boots", "accessory"):
        cand = [(k, v) for k, v in IT.items()
                if v.get("slot") == slot and v.get("quality") == "普通"
                and int((v.get("req") or {}).get("level") or 0) <= int(level)]
        if not cand:
            continue
        best = max(cand, key=lambda kv: (sum(int(a.get("v") or 0) for a in (kv[1].get("affixes") or [])),
                                         kv[0]))
        eq[slot] = best[0]
    return eq


def _fresh(loc, node, level):
    return {"name": "探针", "race": "human", "cls": "cls_knight", "level": int(level), "exp": 0,
            "loc": loc, "node": node, "prev": [], "gold": 0, "bag": {}, "equipped": _gear(level),
            "flags": {}, "codex": {}}


def _battle_level(mid: str, loc: str, node: str, lv: int) -> int:
    """打那只怪用几级去 —— **高一点打得赢**，但不能高到它挑不进候选（遇敌只取最近的三只）。"""
    for lvl in (lv + 3, lv + 1, lv):
        for seed in range(60):
            if CMB.pick_encounter(MON, loc, node, lvl, seed=seed) == [mid]:
                return lvl
    return lv


def _hit(p, iid):
    return int((p.get("bag") or {}).get(iid, 0)) > 0


def _hod_order(gid: str):
    """时辰/天气门槛决定先试哪个点 —— 夜里的点先试夜（不然白扫一整天）。"""
    pt = G.get(gid) or {}
    toks = [pt.get("time")] if pt.get("time") else []
    toks += [e.get("when") for e in (pt.get("pool") or []) if e.get("when")]
    toks = [t for t in toks if t]
    if not toks:
        return list(HODS)
    for hod in HODS:
        _at(0, hod)
        if all(CAL.allows(t, CAL.state()) for t in toks):
            return [hod] + [h for h in HODS if h != hod]
    return list(HODS)


def gather_try(iid, s, levels=()):
    """真跑采集：站到那个点上敲那个动词，扫人 × 日 × 时辰，直到该 id 真进背包。"""
    n, gated, blank = 0, 0, 0
    for hod in _hod_order(s["where"]):
        for d in range(DAY_CAP):
            for i in range(UID_CAP):
                _at(d, hod)
                for nth in range(1, s["times"] + 1):
                    p = _fresh(s["map"], s["node"], 5)
                    out = run_ag(CG._do_gather(None, None, "u_src%02d" % i, p, s["verb"], ""))
                    n += 1
                    if _hit(p, iid):
                        return True, n, gated, blank
                    if any("时辰" in x or "这一带" in x for x in out):
                        gated += 1
                    elif not (p.get("bag") or {}):
                        blank += 1
    return False, n, gated, blank


def battle_try(iid, s):
    """真跑战斗：站到那只怪的栖息地真节点上敲「攻击」，扫人 × 场次，直到该 id 真进背包。

    · 掉落那一步是 `uid:怪 id` 恒定 ⇒ 先按**生产函数**挑出「这个人打这只怪会出这件」的人，
      再拿真 handler 打一场验它（不是对表：验的是「真进背包」）。
    · 遇敌那一挑**不跟人走**（`pick_encounter(seed=None)` 是真随机）⇒ 同一人多打几场，
      场次封顶 40。
    """
    hb = s["maps"] or {}
    spot = next(((mp, nd) for mp in (hb.get("maps") or []) for nd in (hb.get("nodes") or [])
                 if (mp, nd) in REACH), None)
    if not spot:
        return False, 0, 0
    lv = _battle_level(str(s["where"]), spot[0], spot[1],
                       int((MON.get(s["where"]) or {}).get("lv") or 5))
    uids = []
    for i in range(400):
        uid = "u_srcb%03d" % i
        drops = LT.roll_pool(s["pool"], level=lv,
                             rnd=random.Random("%s:%s" % (uid, s["where"])))
        if any(d["id"] == iid for d in drops):
            uids.append(uid)
        if len(uids) >= 3:
            break
    tries = 0
    for uid in uids:
        for _ in range(BATTLE_ATT):
            p = _fresh(spot[0], spot[1], lv)
            # ★ 别给 uid 加后缀：`attack` 的掉落种子是 `uid:怪 id`，加了后缀就与上面那次抽签错位
            run_ag(CB.attack(None, None, uid, p))
            tries += 1
            if _hit(p, iid):
                return True, tries, lv
    return False, tries, lv


print()
print("  ── 真跑（handler 级）逐件核 ──")
runs = {}
for iid in MUST:
    ss = SITES.get(iid) or []
    gs = [s for s in ss if s["kind"] == "gather"]
    ms = [s for s in ss if s["kind"] == "monster"]
    got, how, extra = False, "", ""
    if gs:                                             # 先走采集（确定：种子 = 人·日·点·次数）
        s = max(gs, key=lambda x: x["w"])
        got, n, gated, blank = gather_try(iid, s)
        how = "采集 %s（%s/%s w=%d）" % (s["where"], s["map"], s["node"], s["w"])
        extra = "样本 %d（时辰/天气挡掉 %d）" % (n, gated)
    if not got and ms:                                 # 再走战斗
        # ★ 优先「池里直接写着它」的那条（动态格 `*weapon_random` 只是**可能**挑到它 ⇒ 先放着）
        s = max(ms, key=lambda x: (not x.get("grid"), x["w"]))
        got, n, lv = battle_try(iid, s)
        how = "战斗 %s 掉 %s（lv%d）" % (s["where"], s["pool"], lv)
        extra = "打了 %d 场" % n
    if not got and not gs and not ms:                  # 只由配方/委托出产的那类（②已证它在）
        kd = (ss[0]["kind"] if ss else "?")
        got = kd in ("recipe", "quest")
        how = "%s出产（%s）" % ({"recipe": "配方", "quest": "委托"}.get(kd, kd),
                               ss[0]["where"] if ss else "—")
    runs[iid] = (got, how, extra)
    (ok if got else bad)("%-28s %-12s %s  —— %s%s"
                         % (iid, IT.get(iid, {}).get("name"), "✓ 真拿到" if got else "✗ 拿不到",
                            how, ("  " + extra) if extra else ""))

# ── ⑤ 品味档 ─────────────────────────────────────────────────────
_byname: dict = {}
for k, v in IT.items():
    if v.get("slot"):                                  # 装备同名多品阶是设计（`common/refined/...`）
        continue
    _byname.setdefault(str(v.get("name")), []).append(k)
_dup = {n: ks for n, ks in _byname.items() if len(ks) > 1}
(ok if not _dup else bad)("★ 非装备里没有同名两件（例：`i_material_iron_scrap` / `i_material_iron_chip` "
                          "两个 id 一名那次）—— %s" % (_dup or "无"))

_bad_codex = []
for book in ("material", "flavor"):
    for k, v in (CX.get(book) or {}).items():
        if k in IT and v.get("name") != IT[k].get("name"):
            _bad_codex.append((book, k, v.get("name"), IT[k].get("name")))
(ok if not _bad_codex else bad)("★ 图鉴那一栏的名字与物品表**同一个名**（改一处必须改两处）—— 对不上 %s"
                                % (_bad_codex[:4] or "无"))

print()
print("按图：%d 个可达节点 · 产出口 %d 条" % (len(REACH), sum(len(v) for v in SITES.values())))
print("结果：%s" % ("全绿 ✓" if not fails else "有红 ✗（%d）" % len(fails)))
sys.exit(1 if fails else 0)
