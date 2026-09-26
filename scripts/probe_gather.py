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
        _p1 = {"day": 777001, "flags": {}, "bag": {}}
        _r1 = _CG._first_dig_fill(_p1, str(_rule.get("verb")), [])
        _r2 = _CG._first_dig_fill(_p1, str(_rule.get("verb")), [])
        _r3 = _CG._first_dig_fill({"day": 777002, "flags": dict(_p1["flags"])}, str(_rule.get("verb")), [])
        _r4 = _CG._first_dig_fill({"day": 777003, "flags": {}}, str(_rule.get("verb")),
                                  [{"id": _out, "n": 1}])
        (ok if [d["id"] for d in _r1] == [_out] else bad)("⑪ 空手那一铲 ⇒ 补 %r" % ([d["id"] for d in _r1],))
        (ok if _r2 == [] else bad)("⑪ 同一天第二铲不补（当天额度只一次）⇒ %r" % (_r2,))
        (ok if [d["id"] for d in _r3] == [_out] else bad)("⑪ 次日第一铲又补 ⇒ %r" % ([d["id"] for d in _r3],))
        (ok if _r4 == [] else bad)("⑪ 这一铲自己就出了 ⇒ 不叠加 ⇒ %r" % (_r4,))
print()

print("按地图：%s" % by_map)
print("结果：%s" % ("全绿 ✓" if not fails else "有红 ✗（%d）" % len(fails)))
sys.exit(1 if fails else 0)
