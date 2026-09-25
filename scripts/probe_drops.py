# -*- coding: utf-8 -*-
"""探针：drop_pools 域 + 掉落逻辑 —— 池合法 · ★ 所有 out 指向真物品 · 权重可抽 · 可复现。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_drops.py
"""
from __future__ import annotations

import io
import os
import random
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack          # noqa: E402

st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
st.install()

DP = st.domain("drop_pools")
IT = st.domain("items")
MON = st.domain("monsters")
LT = st.optional_submodule("loot")

fails = []
ok = lambda m: print("  ✓ " + m)
bad = lambda m: (fails.append(m), print("  ✗ " + m))

print("探针：drop_pools 域 + 掉落逻辑")

# ① 域读得到 + 分两类
pools = {k: v for k, v in DP.items() if k.startswith("dp_")}
unids = {k: v for k, v in DP.items() if k.startswith("unid_")}
(ok if pools and unids else bad)("掉落池 %d 个 · 未鉴定 %d 个" % (len(pools), len(unids)))

# ② 每条有 entries/pool + 权重字段
no_ent = [k for k, v in DP.items() if not (v.get("entries") or v.get("pool"))]
(ok if not no_ent else bad)("每条都有 entries/pool（缺 %s）" % (no_ent or "无"))

# ③ ★ 跨域：所有 out 指向真物品（动态 * 项除外）
bad_out = []
for k, v in DP.items():
    for e in (v.get("entries") or v.get("pool") or []):
        o = str(e.get("out") or "")
        if not o or o.startswith("*"):
            continue
        if o.startswith("dp_") or o.startswith("unid_"):
            if o not in DP:
                bad_out.append((k, o))
        elif o not in IT:
            bad_out.append((k, o))
(ok if not bad_out else bad)("★ 所有 out 指向真物品/真池（坏 %s）" % (bad_out or "无"))

# ④ ★ 怪的 drops 池都真实存在（跨域对账）
bad_ref = []
for mid, m in MON.items():
    for p in (m.get("drops") or []):
        if p not in DP:
            bad_ref.append((mid, p))
(ok if not bad_ref else bad)("★ 怪身上挂的池都存在（坏 %s）" % (bad_ref or "无"))

# ⑤ 未鉴定的四类出口都在（装备/材料/垃圾/信物/线索）
u = DP.get("unid_rare") or {}
kinds = {e.get("kind") for e in (u.get("pool") or [])}
want = {"装备", "材料", "垃圾", "信物", "线索"}
(ok if want <= kinds else bad)("★ 未鉴定四类出口齐（有 %s）" % sorted(kinds))

# ⑥ ★ 权重能抽出来（跑 2000 次，每类都出得来）
rnd = random.Random(42)
got = {}
for _ in range(2000):
    r = LT.open_unid("unid_rare", rnd=rnd)
    if r:
        got[r["kind"]] = got.get(r["kind"], 0) + 1
(ok if len(got) >= 4 else bad)("★ 2000 次开未鉴定，种类分布 = %s" % got)

# ⑦ ★ 可复现（同种子同结果）
a = LT.roll_pool("dp_trash_small", level=3, rnd=random.Random("s"))
b = LT.roll_pool("dp_trash_small", level=3, rnd=random.Random("s"))
(ok if a == b else bad)("★ 同种子掉落可复现（%s）" % a)

# ⑧ 动态挑选 *armor_random 能解析出真装备
r = LT.roll_pool("dp_elite_gear", level=5, rnd=random.Random(1))
ids = [x["id"] for x in r]
(ok if all(i in IT for i in ids) else bad)("动态项解析成真物品（%s）" % ids)

# ⑨ 重复掉落有用（材料能进背包、图鉴记第一次）
p = {"bag": {}, "codex": {}}
first = LT.add_to_bag(p, [{"id": "i_material_iron_chip", "n": 2}])
second = LT.add_to_bag(p, [{"id": "i_material_iron_chip", "n": 1}])
(ok if p["bag"]["i_material_iron_chip"] == 3 and first and not second
 else bad)("重复掉落累计进背包、图鉴只记第一次（%s）" % p["bag"])

# ⑩ ★ 背包呈现口（真调 handler）：未鉴定的 marker 显示**池上的名字**，不是裸 id
import asyncio                                                          # noqa: E402
sys.path.insert(0, REPO)
from content import cmds_ast as CA                                      # noqa: E402

_bag_out = []


async def _go_bag():
    p10 = dict(CA.DEFAULT_PLAYER, bag={"unid_rare": 1, "i_material_iron_chip": 2})
    async for ln in CA.bag(None, None, "u_probe", p10):
        _bag_out.append(str(ln))


asyncio.run(_go_bag())
_joined = "\n".join(_bag_out)
_want_pool = (DP.get("unid_rare") or {}).get("name")
_want_item = (IT.get("i_material_iron_chip") or {}).get("name")
(ok if _want_pool and _want_pool in _joined and _want_item in _joined and "unid_" not in _joined
 else bad)("★ 背包真跑：未鉴定显示池上的名字「%s」、不裸 id（%s）" % (_want_pool, _bag_out))

# ⑪ ★ rec_of 是唯一一口（物品表 → 池表）：背包里可能出现的每条 id 都取得到名字
_bagable = list(IT) + [k for k, v in DP.items() if v.get("kind") == "未鉴定"]
_miss = [k for k in _bagable if not (LT.rec_of(k) or {}).get("name")]
(ok if not _miss else bad)("★ rec_of 覆盖能进背包的每一条（物品 %d + 未鉴定 %d 条 · 缺名字 %s）"
                           % (len(IT), len(_bagable) - len(IT), _miss or "无"))
(ok if LT.rec_of("i_nope_nothing_at_all") == {} else bad)("rec_of 对不认识的 id 回空表（不编一个）")

# ⑫ ★ 「唯一一口」防回退：四个呈现口都走 loot.rec_of（别再各写一遍 items-or-pools）
_view = ("cmds_ast.py", "cmds_gather.py", "cmds_battle.py", "codex.py")
_no = sorted(n for n in _view
             if "rec_of(" not in io.open(os.path.join(REPO, "content", n), encoding="utf-8").read())
(ok if not _no else bad)("★ 呈现口都走 loot.rec_of（没走的：%s）" % (_no or "无"))

# ⑬ ★ B3-6b-2d-b：动态项 `*<格>_random` 按 ASCII `slot` 挑（原按 `kind` 的中文枚举挑）——
#   ① 挑出来的每一件都真带 `slot`、且落在该格对应的那几格
#   ② 两格不串味（armor 那一格永远挑不出武器）
#   ③ 认不出的格 ⇒ None（不猜、不兜底）
_ARMOR_SLOTS = ("armor_top", "armor_bottom", "helmet", "boots")
_cand = {k for k, v in IT.items() if v.get("slot") in _ARMOR_SLOTS}
_wcand = {k for k, v in IT.items() if v.get("slot") == "weapon"}
_picked, _wpicked = set(), set()
for _s in range(1, 201):
    _picked.add(LT._resolve("*armor_random", {}, 5, random.Random(_s), IT))
    _wpicked.add(LT._resolve("*weapon_random", {}, 5, random.Random(_s), IT))
(ok if (_picked <= _cand and len(_picked) >= 4) else bad)(
    "★ `*armor_random` 200 种子挑出的 %d 件全在「四格」那一批里（候选 %d 件 · 四格都挑到过）"
    % (len(_picked), len(_cand)))
(ok if (_wpicked <= _wcand and not (_picked & _wpicked)) else bad)(
    "★ `*weapon_random` 同上（%d 件）· 两格**零交集**（按 slot 挑不串味）"
    % len(_wpicked))
(ok if LT._resolve("*grid_nope", {}, 1, random.Random(1), IT) is None else bad)(
    "★ 认不出的格 ⇒ None（不猜、不兜底）")
_ge = [x["id"] for x in LT.roll_pool("dp_elite_gear", level=5, rnd=random.Random(7))]
(ok if all(IT[i].get("slot") for i in _ge if i in IT) else bad)(
    "★ dp_elite_gear 真抽一遍：动态项解出来的都是真装备（件件带 slot · %s）" % _ge)

print()
print("结果：%s" % ("全绿 ✓" if not fails else "有红 ✗"))
sys.exit(1 if fails else 0)
