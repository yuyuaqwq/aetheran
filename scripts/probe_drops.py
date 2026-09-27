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
# ⑤之二 ★ B3-6b-2d-keys-2：同一批出口的**机器键**（代码只认 ASCII 那一栏）
kkeys = {e.get("kind_key") for e in (u.get("pool") or [])}
wantk = {"gear", "material", "junk", "keepsake", "clue"}
(ok if wantk <= kkeys else bad)("★ 未鉴定四类出口的**机器键**齐（有 %s）" % sorted(kkeys))

# ⑥ ★ 权重能抽出来（跑 2000 次，每类都出得来）
rnd = random.Random(42)
got = {}
for _ in range(2000):
    r = LT.open_unid("unid_rare", rnd=rnd)
    if r:
        got[r["kind_key"]] = got.get(r["kind_key"], 0) + 1
(ok if len(got) >= 4 else bad)("★ 2000 次开未鉴定，机器键分布 = %s" % got)

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


class _EBag(object):
    """背包那个呈现口要的最小环境（★ B4-17：它现在会分页
    ⇒ `env.page` / `env.page_items` 是引擎契约里的两个输入面，替身要照实给）。"""

    text = ""
    key = ""
    group_id = "g_probe_drops"
    uid = "u_probe"

    def save(self):
        pass

    def page(self, raw=None, default=1):
        from saintess_engine.command import parse_page
        return int(parse_page(self.text if raw is None else raw) or default)

    def page_items(self, items, page=1, per_page=10):
        from saintess_engine.command import page_items
        return page_items(items, page, per_page=per_page)


async def _go_bag():
    p10 = dict(CA.DEFAULT_PLAYER, bag={"unid_rare": 1, "i_material_iron_chip": 2})
    async for ln in CA.bag(_EBag(), None, "u_probe", p10):
        _bag_out.append(str(ln))


asyncio.run(_go_bag())
_joined = "\n".join(_bag_out)
_want_pool = (DP.get("unid_rare") or {}).get("name")
_want_item = (IT.get("i_material_iron_chip") or {}).get("name")
(ok if _want_pool and _want_pool in _joined and _want_item in _joined and "unid_" not in _joined
 else bad)("★ 背包真跑：未鉴定显示池上的名字「%s」、不裸 id（%s）" % (_want_pool, _bag_out))

# ⑪ ★ rec_of 是唯一一口（物品表 → 池表）：背包里可能出现的每条 id 都取得到名字
_bagable = list(IT) + [k for k, v in DP.items() if v.get("kind_key") == "unidentified"]
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

# ⑭ ★ B3-6b-2d-keys-2：`kind_key`（ASCII 机器键 · P-20 甲案第二刀）—— **三头对账 + 跨域 + 真跑**
#   ① 记录级（未鉴定那 2 个池）与**条目级**（每条 entry / pool 项）都带 ASCII 键
#   ② schema enum（唯一真源） == 生成器那张表（`scripts/rebuild_kind_keys.py`）
#   ③ 域里「中文 kind → ASCII kind_key」是单射且与表逐条一致（域自己就是那张映射表）
#   ④ ★ 跨域：条目里那 5 个键与 items 的 `kind_key` **同值**（一个词表两处用）
#   ⑤ ★ 真跑：`loot.kind_key_of()` 对每件东西 / 未鉴定池都回**域里那一格**；认不出的回兜底键
import json as _json2                                                            # noqa: E402
sys.path.insert(0, os.path.join(REPO, "scripts"))
import rebuild_kind_keys as _RK                                                  # noqa: E402

_ENUM = set(_json2.load(io.open(os.path.join(REPO, "schemas", "drop_pools.schema.json"),
                                encoding="utf-8"))
            ["patternProperties"]["^(dp_|unid_)[a-z0-9_]+$"]["properties"]["kind_key"]["enum"])
(ok if set(_RK.POOL_KIND_KEY.values()) == _ENUM else bad)(
    "★ 生成器映射表 == schema enum（池侧 %d 类：%s）"
    % (len(_ENUM), "/".join(sorted(_ENUM))))
_ent = [(k, e) for k, v in DP.items()
        for e in (list(v.get("entries") or []) + list(v.get("pool") or []))]
_bad_rec = [k for k, v in DP.items() if v.get("kind") and v.get("kind_key") != _RK.POOL_KIND_KEY.get(v["kind"])]
_bad_ent = ["%s.%s" % (k, e.get("out")) for k, e in _ent
            if e.get("kind") and e.get("kind_key") != _RK.POOL_KIND_KEY.get(e["kind"])]
(ok if not _bad_rec and not _bad_ent else bad)(
    "★ 每条带 `kind` 的（池 %d 条 · 条目 %d 条）都带对的 `kind_key`（坏 %s）"
    % (len([k for k, v in DP.items() if v.get("kind")]), len([1 for _, e in _ent if e.get("kind")]),
       (_bad_rec + _bad_ent)[:4] or "无"))
_k2k = {}
for _k, _e in list(DP.items()) + _ent:
    if _e.get("kind"):
        _k2k.setdefault(_e["kind"], set()).add(_e.get("kind_key"))
(ok if all(len(_s) == 1 and _RK.POOL_KIND_KEY[_k] == sorted(_s)[0] for _k, _s in _k2k.items())
 else bad)("★ 中文 kind → ASCII kind_key 是**单射**且与生成器表逐条一致（%s）"
           % " · ".join("%s→%s" % (_k, sorted(_s)[0]) for _k, _s in sorted(_k2k.items())))
(ok if all(str(_v).isascii() for _s in _k2k.values() for _v in _s) else bad)(
    "★ 机器键全是 ASCII（没有一个汉字）")
_SHARED = {"material", "tool", "junk", "keepsake", "clue"}
_itk = {v.get("kind_key") for v in IT.values()}
_pk = {_e.get("kind_key") for _, _e in _ent}
(ok if _SHARED <= _itk and _SHARED <= _pk else bad)(
    "★ 跨域：条目那 5 个键（%s）与 items 的 `kind_key` **同值**（一个词表两处用）" % "/".join(sorted(_SHARED)))
_bad_run = [k for k, v in IT.items() if LT.kind_key_of(k) != v.get("kind_key")]
_bad_run += [k for k, v in DP.items() if str(k).startswith("unid_") and LT.kind_key_of(k) != v.get("kind_key")]
(ok if not _bad_run else bad)(
    "★ 真跑 `kind_key_of()`：每件东西 / 未鉴定池都回**域里那一格**（对不上 %s）" % (_bad_run[:4] or "无"))
(ok if LT.kind_key_of("i_nope_nothing_at_all") == LT.K_MATERIAL_KEY else bad)(
    "★ 认不出的 id ⇒ 兜底键 `%s`（ASCII，不编中文、也不回空串）" % LT.K_MATERIAL_KEY)
(ok if LT.kind_key_of("i_material_iron_chip", "gear") == "gear" else bad)(
    "★ 条目写了键就优先用它（动态装备那一类：池侧说 gear ≠ 物品自己的 weapon）")

# ── ⑮ ★ P-60：`level_gated` 真被读（池上那句「按等级抽一件」原先是一句空话）——
#   病根：`loot._resolve(out, entry, level, …)` **收了 `level` 却一次都没用**（死参数），
#         于是 `dp_elite_gear` 从**全部同格**的件里等概率挑 ⇒ 1 级的人也能抽到 7 级才穿得上的。
#   四条：① 池声明 → 真抽（1..20 级 × 2000 次，逐件核 `items.req.level <= 该级`）
#         ② 两态对照（判据不是永真：同一个种子不按等级挑 ⇒ 真出得来越级件）
#         ③ fail-closed（够不着 ⇒ 不放 · 不退回全档 · 不编一个更低档的）
#         ④ 静态守卫（`level_gated` 的读端只有 `loot.roll_pool` 一处；传进来的是**玩家自己的
#            等级**——`cmds_battle._settle` 那两行，原先那格传的是怪的等级、而且收的人没用过）
_gate_bad, _gate_lines = [], []
_LV_ALL = list(range(1, 21))
_N_GATE = 2000
for _L in _LV_ALL:
    _over, _got = [], 0
    _rnd = random.Random(20260926 + _L)
    for _ in range(_N_GATE):
        for _d in LT.roll_pool("dp_elite_gear", level=_L, rnd=_rnd):
            _got += 1
            _o = str(_d["id"])
            if _o in IT:                                     # 未鉴定（`unid_*`）没有穿戴门槛
                _r = int((IT[_o].get("req") or {}).get("level") or 0)
                if _r > _L:
                    _over.append((_L, _o, _r))
    if _over or not _got:
        _gate_bad.append((_L, _over[:3], _got))
    _gate_lines.append("L%d 抽 %d 件/越级 %d" % (_L, _got, len(_over)))
(ok if not _gate_bad else bad)(
    "★ ① 池真按等级抽：`dp_elite_gear` 1..20 级各 %d 次 ⇒ **越级 0 件**（%s）"
    % (_N_GATE, " · ".join(_gate_lines[::5]) + " … 逐级见上"))

# ② 两态对照：同一批种子，**不按等级**那一臂（= 改前）必须真出得来越级件 —— 否则这条判据永真
def _ungated_hits(level, n=400):
    out = []
    for _s in range(n):
        oid = LT._resolve("*weapon_random", {"w": 30, "quality": ["精制"]}, level,
                          random.Random(_s), IT, gated=False)
        if oid and int((IT[oid].get("req") or {}).get("level") or 0) > level:
            out.append((oid, int(IT[oid]["req"]["level"])))
    return out


_ctl = _ungated_hits(3)
(ok if _ctl else bad)(
    "★ ② 两态对照：**不按等级**那一臂（改前）在 3 级真挑得出来越级件（%s）⇒ ① 不是永真"
    % (_ctl[:3]))

# ③ fail-closed：够不着 ⇒ 不放。今天的数据里每一级都够得着（普通 / 精制那两档里有一批
#    `req.level = 0` 的）⇒ 拿**只装遗物武器**的那张物品表造出「全越级」那一档（构造用例，
#    不是今天真会发生的路）：门槛之上照抽、门槛之下**不放**（返回 None，不退回全档）。
_rel = [k for k, v in IT.items() if v.get("slot") == "weapon" and v.get("quality") == "遗物"]
_rel_tbl = {k: IT[k] for k in _rel}
_lo = min([int((IT[k].get("req") or {}).get("level") or 0) for k in _rel] or [0])
_none_arm = LT._resolve("*weapon_random", {"w": 30}, _lo - 1, random.Random(1), _rel_tbl, gated=True)
_same_arm = LT._resolve("*weapon_random", {"w": 30}, _lo, random.Random(1), _rel_tbl, gated=True)
(ok if (_rel and _none_arm is None and _same_arm in _rel) else bad)(
    "★ ③ fail-closed：够不着那一档 ⇒ **不放**（构造用例：表里只留遗物武器〔最低 req %d〕，"
    "%d 级的人抽 = %r）· 够得着照抽（%d 级 = %s）"
    % (_lo, _lo - 1, _none_arm, _lo, _same_arm))

# ④ 静态守卫（两条）：`level_gated` 这个**键字面量**的读端只许一处 · 那一处拿的是玩家自己的等级
def _key_lines(rel):
    """某个键字面量（带引号）在 content/*.py 里出现在哪几行 —— 注释 / 文档串里那种不带引号的不算。"""
    hits = []
    cdir = os.path.join(REPO, "content")
    for _f in sorted(os.listdir(cdir)):
        if not _f.endswith(".py"):
            continue
        for _i, _ln in enumerate(io.open(os.path.join(cdir, _f), encoding="utf-8").read().split("\n")):
            if rel in _ln:
                hits.append((_f, _i + 1, _ln.strip()[:60]))
    return hits


_lg = _key_lines('"level_gated"')
_src_cb = io.open(os.path.join(REPO, "content", "cmds_battle.py"), encoding="utf-8").read()
_gate_static = [
    ("读口只许 loot.py 一处", len(_lg) == 1 and _lg[0][0] == "loot.py"),
    ("`_settle` 传的是玩家自己的等级", ('plv = int(p.get("level")' in _src_cb and "level=plv" in _src_cb)),
]
_bad_static = [n for n, v in _gate_static if not v]
(ok if not _bad_static else bad)(
    '★ ④ 静态守卫：`"level_gated"` 在 content/*.py 里只有 %d 处读（%s）· `_settle` 那两行在'
    " —— 坏 %s" % (len(_lg), _lg or "无", _bad_static or "无"))
# ⑤ 「不按等级」那一族的池一个字没动：同一个种子两态逐字相同（`dp_trash_small` 不带声明）
_a5 = LT.roll_pool("dp_trash_small", level=3, rnd=random.Random("s"))
_b5 = LT.roll_pool("dp_trash_small", level=17, rnd=random.Random("s"))
(ok if _a5 == _b5 else bad)(
    "★ ⑤ 没写 `level_gated` 的池**按等级也是同结果**（`dp_trash_small` 3 级 vs 17 级：%s）"
    % [d["id"] for d in _a5])

# ── ⑯ ★ fxm2-horn：`unique` 池**按档去重**（剧情信物「半截号角」不许无限刷）——
#   病根（夜试玩 mage 第 3 轮 · b250）：`dp_boss_minor` = `{rolls: 2, unique: true,
#     entries: [{out: i_horn_half, w: 100}]}` —— 一条**单条目 w=100** 的池，挂在**五只可反复打**
#     的头目怪上（头狗 10 / 守兵 14 / 沉尸 15 / 守塔的骨架 17 / 旧誓哨兵 19）；而 `roll_pool`
#     那格 `unique` **只防「同一次抽取内重复」** ⇒ 跨次抽取挡不住 = 每杀一只必掉一个
#     （实测：同一只怪反复打，进包 **225** 个）。
#   修法（真源 `22_旧哨塔_逐间设计_v1 §12 塔顶`：「掉落 半截号角（**如果 10 房没拿**）· …」）：
#     手上已经有这一件 ⇒ 那一条**不再进池**；池里别的东西照掉、掉率不动。
#   判据四条（每条都带**两态 / 反证**，不许永真）：
#     ① 池级两态：不传 `held` ⇒ 照旧出号角；`held={号角}` ⇒ **一条都不出**；
#        而 `held` 里放**别的东西** ⇒ 号角照旧进池（排的是「已有那件」，不是「有背包」）
#     ② 真跑 3 场（同一个人 · 同一只头目 · 走真落账那条路）：第 1 场号角进包、第 2/3 场**不再出**；
#        与「袋里先有号角」那一臂**逐条相同**（除号角那一条）—— 这就是「别的东西照掉、掉率不动」
#     ③ 别的池零误伤：全仓**每一条没写 `unique` 的池**，同种子传 / 不传 `held` ⇒ 逐条相同
#     ④ 静态守卫三条：`content/*.py` 每个 `roll_pool(` 调用点都带 `held=`（AST 扫）·
#        `unique` 池的条目全是**静态 id**（动态 `*` 项 / 嵌套池那一类排不动）·
#        「同一件唯一信物只挂在**一条** `dp_*` 池上」（同一场两个池各给一件在结构上不可能）
print()
print("⑯ ★ fxm2-horn：`unique` 池按档去重（剧情信物不许无限刷）")

# ① 池级两态（反证：不传 held 就出）
_a16 = [d["id"] for d in LT.roll_pool("dp_boss_minor", level=1, rnd=random.Random(7))]
_b16 = [d["id"] for d in LT.roll_pool("dp_boss_minor", level=1, rnd=random.Random(7),
                                      held={"i_horn_half"})]
_c16 = [d["id"] for d in LT.roll_pool("dp_boss_minor", level=1, rnd=random.Random(7),
                                      held={"i_material_old_iron", "unid_rare"})]
(ok if (_a16 == ["i_horn_half"] and _b16 == [] and _c16 == ["i_horn_half"]) else bad)(
    "★ ① 池级两态：`dp_boss_minor` 不传 `held` ⇒ %s ｜ `held={号角}` ⇒ %s（**一条都不出**）｜ "
    "`held` 里放别的东西 ⇒ %s（排的是「手上已有那件」，不是「有背包」）" % (_a16, _b16, _c16))

# ③ 别的池零误伤：逐池两臂对账（同种子 ⇒ 逐条相同）
_MILE = ("i_set_sentry_gauntlet", "unid_rare", "i_material_old_iron", "i_potion_minor",
         "unid_common", "i_material_iron_chip", "i_material_hard_bone", "i_junk_bone",
         "i_material_herb_common", "i_set_scavenger_blade", "i_horn_half")
_bad16, _n16 = [], 0
for _pid, _pv in sorted(DP.items()):
    if not _pid.startswith("dp_") or _pv.get("unique"):
        continue
    for _L in (1, 20):
        _arm1 = [(d["id"], d.get("n")) for d in
                 LT.roll_pool(_pid, level=_L, rnd=random.Random("k16:" + _pid + str(_L)))]
        _arm2 = [(d["id"], d.get("n")) for d in
                 LT.roll_pool(_pid, level=_L, rnd=random.Random("k16:" + _pid + str(_L)),
                              held=set(_MILE))]
        _n16 += 1
        if _arm1 != _arm2:
            _bad16.append((_pid, _L, _arm1, _arm2))
(ok if not _bad16 else bad)(
    "★ ③ 别的池零误伤：抹掉 `unique` 的 %d 条池 × 2 级（1/20 · 共 %d 次对账）⇒ "
    "传 `held` 与不传**逐条相同**（坏 %s）"
    % (_n16 // 2, _n16, _bad16[:2] or "无"))

# ② 真跑 3 场（同一只头目 · 同一个人 · 两臂只差「袋里先有没有号角」）
import asyncio as _a16io                                                         # noqa: E402
import ast as _ast16                                                             # noqa: E402
from content import alloc as _AL16                                               # noqa: E402
from content import cmds_battle as _CB16                                         # noqa: E402
from content import combat as _CM16                                              # noqa: E402
from content import instance as _IN16                                            # noqa: E402

_HORN16 = "i_horn_half"
_CHIEF16 = "ms_tower_guard"          # 头目 · drops = [dp_boss_minor, dp_tower_keep]


class _E16(object):
    """直调 handler 的最小环境（只要 `save()`）—— 照 `probe_fix4_combat` 的夹具。"""

    text = ""
    group_id = "g_probe_drops"

    def save(self):
        pass


def _chief_runs(bag, kills, uid):
    """同一个档连打 `kills` 场 `ms_tower_guard` —— 逐场列出「掉落 / 钱 / 经验」（走真落账那条路）。"""
    p = dict(CA.DEFAULT_PLAYER)
    p.update({"cls": "cls_knight", "level": 20, "alloc": _AL16.plan(20, "cls_knight"),
              "hp": 999, "gold": 0, "exp": 0, "bag": dict(bag), "codex": {}, "flags": {},
              "loc": "old_watchtower", "node": "tower_outpost_in"})
    p = CA._p(p)
    rows = []
    for _ in range(kills):
        try:                                                 # 从零开一场（先清掉这一格「场」）
            _IN16.clear(_IN16.key_of("", uid, [uid]))
        except Exception:                                    # noqa: BLE001
            pass
        _b0, _g0, _e0 = dict(p.get("bag") or {}), int(p.get("gold") or 0), int(p.get("exp") or 0)
        _lines = []

        async def _go():
            async for _ln in _CB16.auto_battle(_E16(), None, uid, p):
                _lines.append(str(_ln))

        _a16io.run(_go())
        _b1 = dict(p.get("bag") or {})
        rows.append({
            "got": {k: int(v) - int(_b0.get(k, 0)) for k, v in _b1.items()
                    if int(v) - int(_b0.get(k, 0)) > 0},
            "gold": int(p.get("gold") or 0) - _g0,
            "exp": int(p.get("exp") or 0) - _e0,
            "rows": [x for x in _lines if x.startswith("拾取")],
        })
    return rows


_rp16, _re16 = _CM16.pick_encounter, None
try:
    from content import affix as _AF16                                          # noqa: E402
    _re16 = _AF16.elite_of
    _AF16.elite_of = lambda *a, **k: None        # 词条精英那一层关掉（本判据只看掉落池那一条线）
    _CM16.pick_encounter = lambda *a, **k: [_CHIEF16]
    _A16 = _chief_runs({}, 3, "u_probe_drops_horn")                # 空袋那一臂
    _B16 = _chief_runs({_HORN16: 1}, 3, "u_probe_drops_horn")      # ★ 同一个 uid ⇒ 同一个种子
finally:
    _CM16.pick_encounter = _rp16
    try:
        _AF16.elite_of = _re16
    except NameError:
        pass

_same16 = all(
    {k: v for k, v in _A16[_i]["got"].items() if k != _HORN16}
    == {k: v for k, v in _B16[_i]["got"].items() if k != _HORN16}
    and _A16[_i]["gold"] == _B16[_i]["gold"]
    and _A16[_i]["exp"] == _B16[_i]["exp"]
    for _i in range(3))
(ok if _same16 else bad)(
    "★ ② 别的东西照掉（两臂逐条对账）：空袋那一臂 %s ｜ 袋里先有号角那一臂 %s "
    "⇒ 除号角外**逐条相同**、钱 %s / 经验 %s 也一分不差"
    % ([r["got"] for r in _A16], [r["got"] for r in _B16],
       [r["gold"] for r in _A16], [r["exp"] for r in _A16]))
(ok if (_A16[0]["got"].get(_HORN16) == 1 and _HORN16 not in _A16[1]["got"]
        and _HORN16 not in _A16[2]["got"]) else bad)(
    "★ ② 真跑 3 场：第 1 场号角进包、第 2/3 场**不再出** —— %s"
    % ["×".join("%s:%d" % (k, v) for k, v in sorted(r["got"].items())) or "（无掉落）" for r in _A16])
(ok if all(_HORN16 not in r["got"] for r in _B16) else bad)(
    "★ ② 反证（袋里先有）：3 场一场都没出号角 —— %s"
    % ["×".join("%s:%d" % (k, v) for k, v in sorted(r["got"].items())) or "（无掉落）" for r in _B16])
(ok if all(_A16[i]["rows"] for i in range(3)) else bad)(
    "★ ② 屏上那几行照旧（逐场要点）：%s"
    % " ｜ ".join("第%d场 %s" % (i + 1, r["rows"]) for i, r in enumerate(_A16)))

# ④ 静态守卫（三条）
_bad_calls16 = []
_cdir16 = os.path.join(REPO, "content")
for _f in sorted(os.listdir(_cdir16)):
    if not _f.endswith(".py"):
        continue
    _tree16 = _ast16.parse(io.open(os.path.join(_cdir16, _f), encoding="utf-8").read())
    for _n in _ast16.walk(_tree16):
        if isinstance(_n, _ast16.Call) and getattr(_n.func, "attr", None) == "roll_pool":
            if not any(_k.arg == "held" for _k in _n.keywords):
                _bad_calls16.append("%s:%d" % (_f, _n.lineno))
_uniq16 = {k: v for k, v in DP.items() if v.get("unique") and k.startswith("dp_")}
_dyn16 = ["%s.%s" % (k, e.get("out")) for k, v in _uniq16.items()
          for e in (v.get("entries") or [])
          if str(e.get("out") or "").startswith("*") or e.get("kind_key") == "pool"]
_uids16 = {str(e.get("out")) for v in _uniq16.values() for e in (v.get("entries") or [])}
_dup16 = sorted({"%s 也挂在 %s" % (u, k) for k, v in DP.items() if k not in _uniq16
                 for e in ((v.get("entries") or []) + (v.get("pool") or []))
                 if str(e.get("out")) in _uids16})
(ok if (not _bad_calls16 and not _dyn16 and not _dup16 and _uniq16) else bad)(
    "★ ④ 静态守卫：`content/*.py` 的 `roll_pool(` 调用点**都带 `held=`**（缺 %s）· "
    "`unique` 池（%s）条目全是静态 id（动态/嵌套 %s）· 唯一信物只挂**一条** `dp_*` 池（重 %s）"
    % (_bad_calls16 or "无", " · ".join(sorted(_uniq16)) or "无", _dyn16 or "无", _dup16 or "无"))
print("  · 登记（不当判据）：同一件信物**另有采集点**一条渠道 —— `gathering.json::gt_tw_search_4`"
      "（号角室石台 · `搜查` · 一天 3 遍）的池里也有 `i_horn_half`。本批只按真源"
      "「Boss 池按档去重」这一条修，采集点那条渠道按域里没声明 `unique` 就**不动**（见分支 `_notes.md`）。")

print()
print("结果：%s" % ("全绿 ✓" if not fails else "有红 ✗"))
sys.exit(1 if fails else 0)
