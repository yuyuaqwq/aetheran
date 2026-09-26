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
                    ("骨头", "i_junk_bone")],
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
print("按地图：%s" % by_map)
print("结果：%s" % ("全绿 ✓" if not fails else "有红 ✗（%d）" % len(fails)))
sys.exit(1 if fails else 0)
