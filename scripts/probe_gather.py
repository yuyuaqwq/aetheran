# -*- coding: utf-8 -*-
"""探针：gathering 域 —— 点合法 · ★ 位置在真图上 · ★ pool 指向真物品 · 密度分布。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_gather.py
"""
from __future__ import annotations

import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack          # noqa: E402

st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
st.install()

G = st.domain("gathering")
MAPS = st.domain("maps")
IT = st.domain("items")
DP = st.domain("drop_pools")

fails = []
ok = lambda m: print("  ✓ " + m)
bad = lambda m: (fails.append(m), print("  ✗ " + m))

print("探针：gathering 域（采集点）")
print("  ✓ gathering 域读得到  —— %d 个点" % len(G))

# ① 四类齐全
kinds = {}
for v in G.values():
    kinds[v["kind"]] = kinds.get(v["kind"], 0) + 1
want = {"采药", "挖掘", "垂钓", "搜查"}
(ok if want <= set(kinds) else bad)("四类齐全  —— %s" % kinds)

# ② ★ 跨域：位置在真图上、节点在图里
bad_loc = []
for gid, v in G.items():
    m = MAPS.get(v.get("map"))
    if not m:
        bad_loc.append((gid, v.get("map")))
        continue
    ids = [n.get("id") for n in (m.get("nodes") or [])]
    if v.get("subarea") not in ids:
        bad_loc.append((gid, v.get("subarea")))
(ok if not bad_loc else bad)("★ 位置都在真图真节点上（坏 %s）" % (bad_loc or "无"))

# ③ ★ pool 指向真物品/真未鉴定
bad_out = []
for gid, v in G.items():
    for e in (v.get("pool") or []):
        o = str(e.get("out") or "")
        if o.startswith("unid_"):
            if o not in DP:
                bad_out.append((gid, o))
        elif o not in IT:
            bad_out.append((gid, o))
(ok if not bad_out else bad)("★ pool 指向真物品/真未鉴定（坏 %s）" % (bad_out or "无"))

# ④ 每条都有出产（不能空手）
no_pool = [k for k, v in G.items() if not v.get("pool")]
(ok if not no_pool else bad)("每个点都有出产（空 %s）" % (no_pool or "无"))

# ⑤ ★ 密度刻意不均（真源：没有空，密就不显）
by_map = {}
for v in G.values():
    by_map[v["map"]] = by_map.get(v["map"], 0) + 1
lo, hi = min(by_map.values()), max(by_map.values())
(ok if hi >= lo * 2 else bad)("★ 密度刻意不均（%s；最密 %d vs 最疏 %d）" % (by_map, hi, lo))

# ⑥ 有次数上限（不能无限刷）
no_cap = [k for k, v in G.items() if not v.get("times_per_day")]
(ok if not no_cap else bad)("每个点都有每日上限（缺 %s）" % (no_cap or "无"))

# ⑦ 有带时辰限制的点（夜明砂/无鳞鱼那类）
timed = [k for k, v in G.items() if v.get("time")]
(ok if timed else bad)("有时辰/天气限制的点（%s）" % (timed or "无"))

# ⑧ ★ B3-7：塔里那三处「可拿物」（22 号文档 §二 的「可做」）真的落在采集点上，池里真有关键件
#    出处：`22_旧哨塔_逐间设计_v1.md` §二·2「战斗后『调查』门厅（→ 旧物谱第一个问号）」·
#          §二·8「开箱（→ 旧哨塔的遗物之一）」· §二·10「拿半截号角（剧情物）」。
#    关键件 id 的出处：`06_装备获取与支线玩法_v1 §1.2`（哨兵的护手 ← 副本二层）与
#          `14_图鉴四谱口径` 旧物表（半截号角 = 信物 · `i_horn_half`）。
TOWER_NODES = ("tower_hall", "tower_storage", "tower_horn_room")
KEY = {"tower_hall": "unid_tower",              # 门厅那件不认得的旧东西（进旧物谱先给一行问号）
       "tower_storage": "i_set_sentry_gauntlet",  # 储藏室的箱子 → 哨兵的护手
       "tower_horn_room": "i_horn_half"}          # 号角室的石台 → 半截号角
cont_bad = []
for nd, key in KEY.items():
    pts = [(gid, v) for gid, v in G.items()
           if v.get("map") == "old_watchtower" and v.get("subarea") == nd and v.get("verb") == "search"]
    if len(pts) != 1:
        cont_bad.append((nd, "可搜物 %d 个" % len(pts)))
        continue
    gid, pt = pts[0]
    pool = pt.get("pool") or []
    outs = [str(e.get("out")) for e in pool]
    if key not in outs:
        cont_bad.append((nd, gid, "池里没有 %s" % key))
        continue
    ws = {str(e.get("out")): int(e.get("w", 1) or 1) for e in pool}
    if ws[key] < max(ws.values()):
        cont_bad.append((nd, gid, "%s 不是最高权重（%s）" % (key, ws)))
    if key.startswith("unid_") and key not in DP:
        cont_bad.append((nd, gid, "未鉴定 marker %s 不在池表" % key))
    elif not key.startswith("unid_") and key not in IT:
        cont_bad.append((nd, gid, "%s 不在物品表" % key))
(ok if not cont_bad else bad)("★ 塔内三处「可拿物」（门厅 → 旧物谱第一个问号 · 储藏室 → 开箱 · 号角室 →"
                              " 拿半截号角）：三间各有一个可搜物 · 池里真有关键件且权重最高（%s）%s"
                              % (" · ".join("%s→%s" % (nd, KEY[nd]) for nd in TOWER_NODES),
                                 ("" if not cont_bad else "；对不上：%s" % cont_bad)))

# ⑨ ★ B3-7：一个节点 + 一个动词只许有一个点 —— 采集那条路取的是 `pts[0]`（`cmds_gather._do_gather`），
#    多一个点就等于把另一个**永久遮住**（塔里那三间各只能放一个「搜查」点就是这个原因）。
_multi = {}
for gid, v in G.items():
    _k = (v.get("map"), v.get("subarea"), v.get("verb"))
    _multi.setdefault(_k, []).append(gid)
_multi = {k: v for k, v in _multi.items() if len(v) > 1}
(ok if not _multi else bad)("★ 同节点同动词只有一个点（多一个就把另一个遮住）—— %s" % (_multi or "无"))

# ⑩ ★ fix3-⑦：采集点正文点名的东西 ↔ 它自己的掉落池 —— **双向**对账
#   玩家报的原状（P2 BUG⑩）：伐木棚『挖掘』正文只承诺「崩掉的斧刃、弯了的铁钉」，
#   实际给的是 🦴 骨头 —— 收集向玩家会怀疑自己看错。
#   真源口径 = `10_地图探索元素库_v1.md §四①`「显示必可触发：正文提到的物件，都要能在
#   该节点被指令碰到」——把它落到采集点这一半，做成两条：
#     · 池里有、正文没提 ⇒ 玩家拿到会以为看错（就是这条 bug）
#     · 正文点名、池里没有 ⇒ 正文在承诺拿不到的东西
#   登记表 = 点 id → [(正文里的锚词, 池里对应的那一条)]（锚词是人写的，登记在这一处）。
LOOT_IN_PROSE = {
    "gt_be_dig_1": [("斧刃", "i_material_old_iron"),
                    ("铁钉", "i_material_iron_scrap"),
                    ("残骸", "i_junk_bone")],
}


def _prose_bad(desc, pool_outs, pairs):
    """这一条正文与池子对不上几处（空表 = 对得上）。"""
    out = []
    for word, item in pairs:
        if item in pool_outs and word not in desc:
            out.append("池里有 %s，正文没提「%s」" % (item, word))
        if word in desc and item not in pool_outs:
            out.append("正文点名「%s」，池里没有 %s" % (word, item))
    return out


_prose_bad_all = []
for _gid, _pairs in LOOT_IN_PROSE.items():
    _pt = G.get(_gid)
    if not _pt:
        _prose_bad_all.append((_gid, "点不在域里"))
        continue
    _outs = set(str(e.get("out")) for e in (_pt.get("pool") or []))
    _b = _prose_bad(str(_pt.get("desc") or ""), _outs, _pairs)
    if _b:
        _prose_bad_all.append((_gid, _b))
(ok if not _prose_bad_all else bad)(
    "★ 采集点正文 ↔ 掉落池 双向对账（%d 个点登记：正文点名的都能拿到 · 池里有的都点过名）%s"
    % (len(LOOT_IN_PROSE), ("；对不上：%s" % _prose_bad_all) if _prose_bad_all else ""))

# 反证：这条判据抓得住玩家报的那条原状（旧正文只提斧刃/铁钉，一个字没提骨头）
_OLD_DIG_DESC = "棚子后面那片土被刨过。崩掉的斧刃、弯了的铁钉 —— 都堆在这儿，没人捡。"
_old_b = _prose_bad(_OLD_DIG_DESC, set(str(e.get("out")) for e in (G["gt_be_dig_1"]["pool"] or [])),
                    LOOT_IN_PROSE["gt_be_dig_1"])
_cur_b = _prose_bad(str(G["gt_be_dig_1"].get("desc") or ""),
                    set(str(e.get("out")) for e in (G["gt_be_dig_1"]["pool"] or [])),
                    LOOT_IN_PROSE["gt_be_dig_1"])
(ok if (_old_b and not _cur_b) else bad)(
    "★ 反证：旧伐木棚正文（提斧刃铁钉、不提骨头）会被判红 —— %s；现正文 = %s"
    % (_old_b or "没抓住", _cur_b or "对得上"))

print()
# ══════════════════════════════════════════════════════════════
# ⑪ ★ Q-22：每天第一次「挖掘」的保底（口径在 `content/rules/gather.json::first_dig`）
#   为什么有它（现算，不拍脑袋）：
#     · 三点一天各一铲 ⇒ 日产期望 = Σ p(铁屑)×E[件数] = 0.900 + 0.310 + 0.389 = **1.60 件**
#     · 「三点全空」= Π(1-p) = 0.55 × 0.793 × 0.741 = **32%** ⇒ 每 3 个新玩家就有 1 个第一天
#       一件铁屑都挖不到 ⇒ 当天强化做不了（铁屑只有挖掘这一条源）—— 试玩三家实测撞上的就是这个
#     · 设计目标（本条判据的来源）：一阶段（1–20）内玩家能把一件装备推到 **+5**（要 9 个料，
#       `13_配方域口径 §五`）⇒ 日产需 ≳ 1.9 件。⇒ 每天第一铲「没出铁屑就补 1 件」。
#   判据四条：规则在域里认得出 · 空手那一铲必补 · 同一天第二铲不补 · 次日第一铲又补。
# ══════════════════════════════════════════════════════════════
print("⑪ ★ 每天第一次「挖掘」的保底（rules/gather.json::first_dig）")
import io as _io                                          # noqa: E402
import json as _json                                      # noqa: E402
import ast as _ast                                        # noqa: E402


def _imp_calendar():
    """`content.calendar` —— 本节要拨它的假钟（判据 #198 要「今天」现算 ⇒ 得控钟）。"""
    from content import calendar as _c                 # noqa: E402
    return _c

_R = os.path.join(str(REPO), "content", "rules", "gather.json")
try:
    _rule = (_json.load(_io.open(_R, encoding="utf-8")) or {}).get("first_dig") or {}
except Exception as _e:
    _rule = {}
    bad("⑪ 规则文件读不到（%s）：%s" % (_R, _e))
if _rule:
    ok("⑪ 规则在：verb=%s · out=%s ×%s" % (_rule.get("verb"), _rule.get("out"), _rule.get("n")))
    if str(_rule.get("out")) not in IT:
        bad("⑪ 规则点的产出 %r 不在 items 域里" % _rule.get("out"))
    else:
        ok("⑪ 规则点的产出在 items 域里（%s）" % IT[str(_rule["out"])].get("name"))

    # 三点现算：日产期望（不含保底 / 含保底）＋「三点全空」概率
    def _n(v):
        if isinstance(v, list) and v:
            return sum(float(x) for x in v) / len(v)
        s = str(v if v is not None else 1)
        if "-" in s:
            a, b = s.split("-")[:2]
            return (float(a) + float(b)) / 2.0
        return float(s or 1)

    _per, _miss, _ps = 0.0, 1.0, []
    for _gid, _v in G.items():
        if str(_gid).startswith("_") or str(_v.get("verb")) != str(_rule.get("verb")):
            continue
        _pool = _v.get("pool") or []
        _W = sum(float(e.get("w") or 0) for e in _pool)
        _hit = [e for e in _pool if str(e.get("out")) == str(_rule.get("out"))]
        if not _hit or not _W:
            continue
        _p = sum(float(e.get("w") or 0) for e in _hit) / _W
        _ps.append(_p)
        _per += _p * (sum(_n(e.get("n")) for e in _hit) / len(_hit))
        _miss *= (1 - _p)
    # 保底那一补是「当天**第一铲**没出铁屑就补」⇒ 增量 = (1 - p_第一铲) —— 第一铲在哪一点由玩家路线决定，
    # 所以日产是一段区间：先挖最瘦的点（骨田）⇒ 增量最大；先挖最肥的点（伐木棚）⇒ 最小。
    _lo = _per + (1 - max(_ps))                            # 先挖最肥那一点（伐木棚）⇒ 下限
    _hi = _per + (1 - min(_ps))                            # 先挖最瘦那一点（骨田）⇒ 上限
    if _lo >= 1.9:
        ok("⑪ 日产期望 %.2f 件（不含保底）→ **%.2f~%.2f 件**（含保底 · 三点全空的 %.0f%% 那天不再空手）"
           " ≥ 目标线 1.9 件/日 ⇒ 9 个料 ≈ %.1f~%.1f 游戏日"
           % (_per, _lo, _hi, 100 * _miss, 9 / _hi, 9 / _lo))
    else:
        bad("⑪ 含保底的下限 %.2f 件 < 目标线 1.9 件/日（9 个料要 %.1f 游戏日）" % (_lo, 9 / _lo))

    # 真跑那四态：直接调实现体那一个口（同进程 · 不依赖宿主）
    try:
        from content import cmds_gather as _CG                         # noqa: E402
    except Exception as _e:
        _CG = None
        bad("⑪ content.cmds_gather 导不进来：%s" % _e)
    if _CG is not None:
        _out = str(_rule.get("out"))
        # ★ 台账 #198：「今天第几天」改走 `calendar.day_now()`（现算）之后，本节那四态
        #   **不能靠档上 `p["day"]` 摆日子**了 ⇒ 假钟直接拨（`facade.bind_host` 那条现成口），
        #   用游戏日 777001 / 777002 / 777003 三天逐个验，判据只加强不削弱。
        _CAL = sys.modules.get("content.calendar") or _imp_calendar()
        _SCALE = float(_CAL.scale_seconds())
        _fac = _CAL.facade
        _clock0 = _fac.clock()
        try:
            _fac.bind_host(clock=lambda: _SCALE * 777001.5)      # 游戏日 777001（当日正午）
            _p1 = {"day": 777001, "flags": {}, "bag": {}}
            _r1 = _CG._first_dig_fill(_p1, str(_rule.get("verb")), [])
            _r2 = _CG._first_dig_fill(_p1, str(_rule.get("verb")), [])
            _fac.bind_host(clock=lambda: _SCALE * 777002.5)      # 跨到次日
            _r3 = _CG._first_dig_fill({"day": 777002, "flags": dict(_p1["flags"])},
                                      str(_rule.get("verb")), [])
            _fac.bind_host(clock=lambda: _SCALE * 777003.5)
            _r4 = _CG._first_dig_fill({"day": 777003, "flags": {}}, str(_rule.get("verb")),
                                      [{"id": _out, "n": 1}])
        finally:
            _fac.bind_host(clock=_clock0)
        (ok if [d["id"] for d in _r1] == [_out] else bad)("⑪ 空手那一铲 ⇒ 补 %r" % ([d["id"] for d in _r1],))
        (ok if _r2 == [] else bad)("⑪ 同一天第二铲不补（当天额度只一次）⇒ %r" % (_r2,))
        (ok if [d["id"] for d in _r3] == [_out] else bad)("⑪ 次日第一铲又补 ⇒ %r" % ([d["id"] for d in _r3],))
        (ok if _r4 == [] else bad)("⑪ 这一铲自己就出了 ⇒ 不叠加 ⇒ %r" % (_r4,))

        # ── ⑬ ★ 台账 #198：保底「今天」的**唯一口径** = `calendar.day_now()`（现算），
        #      档上那格 `p["day"]` 一个字都不许读（`calendar.py:282` 的 B4-9：它只是 `tick()`
        #      留下的跨日标记，只有几个入口在刷 ⇒ 读它要么拿到 0、要么拿到上一回 tick 的旧值）。
        #      病根形态（改前都成立）：① `p["day"]` 是 0 ⇒ `today != 0` 那道自保失效 ⇒
        #      **同一天连挖三铲各白拿 1 件铁屑**；② 旧值 ⇒ 跨日额度算在昨天头上。
        #      判据三条：真游戏日 0 连三铲只补一次 · 静态守卫「一个 `p["day"]` 字面量都不许有」
        #      · 假钟往前一天仍只补一次（钉住「现算」而不是「读档」）。
        _fac.bind_host(clock=lambda: 0.0)
        try:
            _dg0 = int(_CAL.day_now())
            _p0 = {"day": 0, "flags": {}, "bag": {}}
            _g3 = [[d["id"] for d in _CG._first_dig_fill(_p0, str(_rule.get("verb")), [])]
                   for _ in range(3)]
            _n3 = sum(1 for x in _g3 if x)
            (ok if (_dg0 == 0 and _n3 == 1) else bad)(
                "⑬ 真游戏日 0 连挖三铲 ⇒ 只补 %d 次（%r）—— 白刷已堵"
                % (_n3, [len(x) for x in _g3]))
            _fac.bind_host(clock=lambda: _SCALE * 1.5)          # 游戏日 0 → 1（同一份档接着补）
            _g4 = [[d["id"] for d in _CG._first_dig_fill(_p0, str(_rule.get("verb")), [])]
                   for _ in range(3)]
            (ok if sum(1 for x in _g4 if x) == 1 else bad)(
                "⑬ 假钟拨到游戏日 1 ⇒ 只补 %d 次（%r）—— 走的是现算不是档上那格"
                % (sum(1 for x in _g4 if x), [len(x) for x in _g4]))
        finally:
            _fac.bind_host(clock=_clock0)
        _src13g = _io.open(os.path.join(str(REPO), "content", "cmds_gather.py"), encoding="utf-8").read()
        _tree13g = _ast.parse(_src13g)
        _pday13 = [n for n in _ast.walk(_tree13g)
                   if isinstance(n, _ast.Subscript) and isinstance(n.value, _ast.Name)
                   and n.value.id == "p" and isinstance(n.slice, _ast.Constant)
                   and n.slice.value == "day"]
        _pday13 += [n for n in _ast.walk(_tree13g)
                    if isinstance(n, _ast.Call) and getattr(n.func, "attr", None) == "get"
                    and isinstance(n.func.value, _ast.Name) and n.func.value.id == "p"
                    and n.args and isinstance(n.args[0], _ast.Constant) and n.args[0].value == "day"]
        (ok if not _pday13 else bad)(
            "⑬ 静态守卫：`cmds_gather.py` 里**读档上 `p[\"day\"]` 的点 %d 个**（须 0 —— "
            "那格只是 `tick()` 的跨日标记，读它就白刷）" % (len(_pday13),))
print()
# ══════════════════════════════════════════════════════════════
# ⑫ ★ fxm5-gather-unique：`unique` 采集点**按档去重**（号角室石台 → 半截号角）
#   病根（fxm2 留给主线那条 [裁]）：`gathering.json::gt_tw_search_4`（号角室 · `搜查` ·
#     一天 3 遍）的池里 `i_horn_half w=100` —— 同一天按 `_left_after` 能翻两遍（第 3 遍
#     「翻空了」）、跨天重置 ⇒ **一天最多再拿 1~2 件**；而同一件信物的**另一条路**
#     （`dp_boss_minor`）从 fxm2 起已经**按档去重** ⇒ 同一件剧情信物两条渠道两种口径。
#   真源（本批跟账的依据）：`22_旧哨塔_逐间设计_v1` §二·10 号角室「可做 **拿** 半截号角
#     （信物 i_horn_half）」（**一次「拿」**，不是可反复翻的素材点；设计里它也没有
#     「一天 3 遍」那一格）+ §二·12 塔顶「掉落 半截号角（**如果 10 房没拿**）」
#     ⇒ 同一件信物每档最多一件 —— 与 fxm2 用的是**同一句话**、同一条口径。
#   判据五条（每条都带两态 / 反证，不许永真）：
#     ① 声明与范围：全仓只有 `gt_tw_search_4` 池里 `i_horn_half` **那一条目**写了 `unique`
#        （★ 粒度是**条目**、不是整个点 —— 采集点的池里还混着材料/药品，整点去重会连
#        `27_掉落的惊喜感与未鉴定 §四`「不消灭重复」那条一起顶掉）· schema 登记了条目这一格
#     ② 真宿主真敲两态（固定钟 · 6 个档 · 同一站连敲 3 遍 = 一天的上限）：空袋那一臂出过号角；
#        袋里先有号角那一臂**一遍都不出**，而别的条目照出（池没被排空）；
#        袋里放齐**另外三样**那一臂与空袋那一臂**逐条（连回话）相同**（排的是「已有那件」，
#        而不是「有背包」，也不是「同一点里别的东西」）
#     ③ 零误伤：同形但**没写** `unique` 的点（塔内另外三处 `搜查`）带上它们的关键件 ⇒
#        与空袋那一臂**逐条相同**（回话也逐字相同）
#     ④ 反证：把那一条目上的声明从**实现体真读的那一份域表**上撤掉 ⇒ 袋里先有号角又出号角
#        （再还原）
#     ⑤ 跨渠道 + 静态守卫：全仓**每一条**出 `i_horn_half` 的渠道都带按档去重声明 ·
#        `cmds_gather.py` 里 `unique` 只读两处 · 「手上有哪些件」只走 `loot.held_ids` 那一口
# ══════════════════════════════════════════════════════════════
print("⑫ ★ fxm5-gather-unique：`unique` 采集点按档去重（号角室石台 · 半截号角）")

import ast as _ast12                                                              # noqa: E402
import io as _io12                                                                # noqa: E402
import json as _json12                                                            # noqa: E402
from saintess_engine.host.runtime import Host                                     # noqa: E402

_HORN12 = "i_horn_half"
_PT12 = "gt_tw_search_4"                 # 号角室石台 —— 写了 `unique` 的那一点
_PT12S = ("gt_tw_search_1", "gt_tw_search_2", "gt_tw_search_hall")   # 同形、没写（零误伤那一臂）
_FIXED12 = 1790308800                    # 2026-09-25 12:00 +08:00（**固定钟** ⇒ 种子与「今天」无关）

# ① 声明与范围（静态）：全仓只许「半截号角」那一条目写 `unique`，且 schema 里登记了这一格
_decl12 = sorted({(gid, str(e.get("out"))) for gid, v in G.items()
                  for e in (v.get("pool") or []) if e.get("unique")})
_sch12 = os.path.join(str(REPO), "schemas", "gathering.schema.json")
try:
    _sprops12 = ((_json12.load(_io12.open(_sch12, encoding="utf-8"))
                  .get("patternProperties", {}).get("^gt_[a-z0-9_]+$", {})
                  .get("properties", {}).get("pool", {}).get("items", {}).get("properties", {})) or {})
except Exception as _e12:                                                         # noqa: BLE001
    _sprops12 = {}
    bad("⑫ ① schema 读不到（%s）：%s" % (_sch12, _e12))
(ok if (_decl12 == [(_PT12, _HORN12)] and "unique" in _sprops12) else bad)(
    "★ ① 声明与范围：写了 `unique` 的**条目** = %s（只许 `(%s, %s)` 一处）｜ schema 登记了条目"
    "这一格 = %s" % (_decl12 or "无", _PT12, _HORN12, "unique" in _sprops12))


class _Ad12(object):
    """三函数 + say（照 host-api 契约的最小适配器 —— 与 `probe_cmds` / `e2e_drive` 同形）。"""

    def __init__(self, texts, uid, seed=None):
        self.uid = uid
        self._msgs = [{"uid": uid, "group_id": "g_c", "text": t, "is_group": True} for t in texts]
        self.out = []
        self.saved = seed

    def recv(self):
        return self._msgs.pop(0) if self._msgs else None

    def load_player(self, uid):
        return self.saved if uid == self.uid else None

    def save_player(self, uid, data):
        self.saved = dict(data) if isinstance(data, dict) else data

    def say(self, to, text):
        self.out.append(str(text))


#: 档的形状照 `probe_cmds` ㉓ 那份（同一族真宿主真敲）；`node` 由每一臂自己给
_SEED12 = {"cls": "cls_knight", "race": "human", "name": "试炼者", "level": 12, "exp": 0,
           "gold": 0, "hp": 60, "loc": "old_watchtower", "node": "tower_horn_room",
           "prev": [], "bag": {}, "equipped": {}, "codex": {}, "flags": {}}
_UNIDS12 = ("u_h1", "u_h2", "u_h3", "u_h4", "u_h5", "u_h6")


def _say12(node, bag, uids=_UNIDS12, times=3):
    """真宿主真敲：`uids` 里每个档在 `node` 那站连敲 `times` 遍『搜查』。

    返回 [(uid, [逐遍 {lines, got}])] —— `got` 是**那一刻背包的增量**（走真落账那条路）。
    """
    _db = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_gather_u.db")
    out = []
    for _uid in uids:
        try:
            os.remove(_db)
        except OSError:
            pass
        _ad = _Ad12(["搜查"] * times, _uid, seed=dict(_SEED12, node=node, bag=dict(bag)))
        _h = Host(_ad, str(REPO), inject={"db_path": _db, "clock": lambda: _FIXED12})
        _h.boot()
        rows = []
        for _i in range(times):
            _b0 = dict((_ad.saved or {}).get("bag") or {})
            _ad.out.clear()
            _h.handle({"uid": _uid, "group_id": "g_c", "text": "搜查"})
            _b1 = dict((_ad.saved or {}).get("bag") or {})
            rows.append({"lines": list(_ad.out),
                         "got": sorted((k, int(v) - int(_b0.get(k, 0))) for k, v in _b1.items()
                                       if int(v) - int(_b0.get(k, 0)) > 0)})
        out.append((_uid, rows))
    return out


def _horns12(arm):
    """这一臂里「号角出现在哪几遍」（uid → 遍号列表）。"""
    return {uid: [i + 1 for i, r in enumerate(rows) if any(k == _HORN12 for k, _n in r["got"])]
            for uid, rows in arm}


def _others12(arm, upto=2):
    """这一臂头 `upto` 遍里拿到过哪些**别的**东西（除号角）。"""
    return sorted({k for _uid, rows in arm for r in rows[:upto] for k, _n in r["got"] if k != _HORN12})


print()
# ② 真宿主真敲两态（同一批档 · 同一站 · 连敲 3 遍）
_A12 = _say12("tower_horn_room", {})                        # 空袋那一臂
_B12 = _say12("tower_horn_room", {_HORN12: 1})              # 袋里先有号角那一臂
_C12 = _say12("tower_horn_room", {"i_junk_bone": 3, "i_set_sentry_horn": 1,
                                  "i_potion_minor": 4})     # 袋里有「另外三样」那一臂
_hA12, _hB12, _hC12 = _horns12(_A12), _horns12(_B12), _horns12(_C12)
(ok if (any(_hA12.values()) and not any(_hB12.values())) else bad)(
    "★ ② 真宿主真敲两态（固定钟 · 6 个档 · 号角室石台 · 连敲 3 遍）：空袋那一臂 号角出现在 %s"
    " ⇒ 这条渠道照旧拿得到；袋里先有号角那一臂 %s ⇒ **一遍都不出**"
    % ({k: v for k, v in _hA12.items() if v} or "（一遍都没有 —— 两态没牙）",
       {k: v for k, v in _hB12.items() if v} or "一遍都没出"))
(ok if _others12(_B12) else bad)(
    "★ ② 别的条目照出（池没被排空）：袋里先有号角那一臂 拿到 %s" % (_others12(_B12),))
def _shape12(arm):
    """一臂的「逐 uid · 逐遍（拿到什么 + 回话）」—— 两臂对账用。"""
    return [(uid, [(r["got"], r["lines"]) for r in rows]) for uid, rows in arm]


(ok if (_shape12(_A12) == _shape12(_C12) and any(_hC12.values())) else bad)(
    "★ ② 反证（声明在**条目**上 · 排的是「已有那件」不是「有背包」）：袋里放齐**另外三样**"
    "（残骸 ×3 · 生锈的号角 ×1 · 伤药 ×4）⇒ 号角照出，且与空袋那一臂**逐条（连回话）相同**"
    " —— 号角出现在 %s" % ({k: v for k, v in _hC12.items() if v},))
(ok if all(rows[1]["got"] for _uid, rows in _A12) else bad)(
    "★ ② 屏上那几行照旧（逐遍要点）：%s"
    % " ｜ ".join("%s 第1遍 %s / 第2遍 %s / 第3遍 %s"
                  % (uid, [x[0] for x in rows[0]["got"]] or "（空手）",
                     [x[0] for x in rows[1]["got"]] or "（空手）",
                     [x[0] for x in rows[2]["got"]] or "（空手）")
                  for uid, rows in _A12[:2]))

print()
# ③ 零误伤：同形但没写 `unique` 的点 —— 带上它们的关键件，结果与空袋那一臂逐条相同
_bad12 = []
for _gid in _PT12S:
    _pt = G.get(_gid) or {}
    _pool = _pt.get("pool") or []
    if not _pool:
        _bad12.append((_gid, "点不在域里 / 池空"))
        continue
    _key = str(max(_pool, key=lambda e: int(e.get("w", 1) or 1)).get("out"))
    _a3 = _say12(_pt["subarea"], {}, uids=("u_z1", "u_z2"))
    _b3 = _say12(_pt["subarea"], {_key: 1}, uids=("u_z1", "u_z2"))
    if [(uid, [(r["got"], r["lines"]) for r in rows]) for uid, rows in _a3] \
            != [(uid, [(r["got"], r["lines"]) for r in rows]) for uid, rows in _b3]:
        _bad12.append((_gid, _key, "两臂不同"))
(ok if not _bad12 else bad)(
    "★ ③ 零误伤：同形但**没写** `unique` 的 %d 处（%s）带上各自的关键件 ⇒ 与空袋那一臂"
    "（连回话）**逐条相同**（坏 %s）"
    % (len(_PT12S), " · ".join(_PT12S), _bad12 or "无"))

print()
# ④ 反证：把声明从**实现体真读的那一份域表**上撤掉 ⇒ 袋里先有号角又出号角（再还原）
try:
    from content import cmds_ast as _CA12
except Exception as _e12b:                                                         # noqa: BLE001
    _CA12 = None
    bad("⑫ ④ content.cmds_ast 导不进来：%s" % (_e12b,))
_hOff12, _hBack12 = {}, {}
if _CA12 is not None:
    _tbl12 = _CA12._data("gathering")                    # ★ 真源只读：这里改的是**进程内那一份**
    _ent12 = next((e for e in (((_tbl12.get(_PT12) or {}).get("pool")) or [])
                   if str(e.get("out")) == _HORN12), None)
    if _ent12 is None:
        bad("⑫ ④ 实现体那一份域表里找不到 `%s.%s` 那一条目" % (_PT12, _HORN12))
    _had12 = _ent12.pop("unique", None) if _ent12 is not None else None
    try:
        _hOff12 = _horns12(_say12("tower_horn_room", {_HORN12: 1}, uids=("u_h1", "u_h2", "u_h3")))
    finally:
        if _ent12 is not None:
            if _had12 is not None:
                _ent12["unique"] = _had12
            else:                                         # 撤之前本来就没有（不许留脏）
                _ent12.pop("unique", None)
    _hBack12 = _horns12(_say12("tower_horn_room", {_HORN12: 1}, uids=("u_h1", "u_h2", "u_h3")))
    assert _ent12 is None or _ent12.get("unique") is True, "还原没落回去"
(ok if (any(_hOff12.values()) and not any(_hBack12.values())) else bad)(
    "★ ④ 反证（这一条判据有牙）：把 `unique` 从实现体那一份域表上撤掉 ⇒ 袋里先有号角**又出号角**"
    "（%s）；还原后再跑仍是「一遍都不出」（%s）"
    % ({k: v for k, v in _hOff12.items() if v} or "（撤掉也没出）",
       {k: v for k, v in _hBack12.items() if v} or "一遍都没出"))

print()
# ⑤ 跨渠道 + 静态守卫：全仓每一条出「半截号角」的渠道都带按档去重声明
_CH12 = []
for _pid, _pv in sorted(DP.items()):
    if any(str(e.get("out")) == _HORN12 for e in ((_pv.get("entries") or []) + (_pv.get("pool") or []))):
        if not _pv.get("unique"):
            _CH12.append(_pid)
for _gid, _gv in sorted(G.items()):
    for _e in (_gv.get("pool") or []):
        if str(_e.get("out")) == _HORN12 and not _e.get("unique"):
            _CH12.append("%s.%s" % (_gid, _e.get("out")))
_src12g = _io12.open(os.path.join(str(REPO), "content", "cmds_gather.py"), encoding="utf-8").read()
_tree12g = _ast12.parse(_src12g)
_n12 = sum(1 for _node in _ast12.walk(_tree12g)
           if isinstance(_node, _ast12.Constant) and _node.value == "unique")
_h12 = sum(1 for _node in _ast12.walk(_tree12g)
           if isinstance(_node, _ast12.Call) and getattr(_node.func, "attr", None) == "held_ids")
(ok if (not _CH12 and _n12 == 2 and _h12 == 1) else bad)(
    "★ ⑤ 跨渠道 + 静态守卫：出 `%s` 的渠道（掉落池 %s · 采集点条目 %s）**每一条都写了按档去重**"
    "（漏声明的：%s）· `cmds_gather.py` 里 `unique` 只读 %d 处（判「有没有」+ 排那一条）·"
    " `held_ids` 只调 %d 次"
    % (_HORN12,
       [k for k, v in DP.items() if v.get("unique")],
       ["%s.%s" % (k, e.get("out")) for k, v in G.items() for e in (v.get("pool") or []) if e.get("unique")],
       _CH12 or "无", _n12, _h12))

print()

print("按地图：%s" % by_map)
print("结果：%s" % ("全绿 ✓" if not fails else "有红 ✗（%d）" % len(fails)))
sys.exit(1 if fails else 0)
