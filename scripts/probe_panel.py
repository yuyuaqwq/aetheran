# -*- coding: utf-8 -*-
"""面板接线探针：骑士 10 级面板能不能由「数据 + 引擎形状」算出来；★ P-27 生命上限三处一致。

判据：与 03_职业与技能/06_六职业对照_v2.md 的骑士 10 级面板逐项对得上。

★ 2026-09-25 期望值更新（v1 打样 → v2 对照）：v2 重做时骑士上调为
  max_hp 438→462 · def 54.4→69.6（让「骑士 = 六职业最肉」这条取向成立）·
  atk 62.4→62.2（成长系数微调）。**数据没动，是探针的期望值过时**（面板探针此前一直没跑）。

★ P-27（2026-09-25）：**生命上限只有一个来源 = 职业面板**（`content/panel_build.py`）——
  这一节把「面板 / 档 / 战斗里那只 actor」三处钉在同一个数上（骑士 1 级 = 116），
  而且**都不是写死的常数**：

```
① 真造 actor（`combat.player_actor`）+ 真读档（`content/persistence` 落库再读回来）
   ⇒ 三处同一个数（L1 116 · L2 128 · L10 224；六职业 1 级 90–140）
② 加一次点 / 换一件带「生命上限」词条的装备 ⇒ 三处**一起**跟着涨（装备那份不再是死的）
③ 反证（fail-closed 有牙）：
   · 档上没有职业（建号第二步还没走完）⇒ 三处一起抛 `PanelMissing`（点名），
     不许拿 100 或别人的职业垫上；`状态` 那一面照实说「未定」（见 probe_copy ⑭）
   · 档上的职业不在 classes 域里（声明错了）⇒ 点名抛（列出域里有的）
④ 静态守卫：`content/*.py` 里不许再出现**写死的上限**（`"hp_max": 100` / `… or 100`）
   —— 原先两处写死 100（`apply.py` · `cmds_ast.py`）就是这么来的。
```

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_panel.py
"""
import asyncio
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, ENGINE)
sys.path.insert(0, os.path.join(ENGINE, "extends"))
sys.path.insert(0, PKG)                                    # ★ P-27：要 import content 那几口

from saintess_engine.package import load_stack          # noqa: E402

TMP = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp")
st = load_stack(PKG, exts=[os.path.join(ENGINE, "extends")], inject={"db_path": os.path.join(TMP, "ast_probe.db"), "clock": time.time})
st.install()

from content import panel_build                          # noqa: E402
from content import combat as CB                          # noqa: E402
from content import cmds_ast as CA                        # noqa: E402
from content import persistence as PS                     # noqa: E402
from saintess_engine import config                       # noqa: E402

print("panel_layers_fn 已挂:", config.get_hook("panel_layers_fn") is not None)

actor = panel_build.build_actor("cls_knight", 10, {"STR": 18, "VIT": 13, "WIL": 4})
print("栈 id:", actor["panel_stack"])

from ext_combat.battle.stats import actor_stats          # noqa: E402

panel = actor_stats(None, actor)
want = {"max_hp": 462, "max_mp": 66, "atk": 62.22, "def": 69.6, "mdef": 24.4,
        "spd": 109.0, "hit": 108.5, "block": 40.8}
print("")
print("  %-10s %-10s %-10s %s" % ("键", "引擎算出", "打样期望", "判定"))
ok = True
for k, v in want.items():
    got = panel.get(k)
    good = got is not None and abs(got - v) < 0.05
    ok &= good
    print("  %-10s %-10s %-10s %s" % (k, got, v, "✅" if good else "❌"))
print("")
print("  crit（数值 24 → 率 %.4f）:" % (24 / (24 + 500)), panel.get("crit"))
print("  面板全部键:", sorted(panel))
print("")
print("===== %s =====" % ("面板由数据+引擎形状算出，与打样一致 ✅" if ok else "有项对不上 ❌"))

# ══════════════════════════════════════════════════════════════
# ★ P-27：生命上限 —— 三处一致（面板 / 档 / 战斗里那只 actor）
# ══════════════════════════════════════════════════════════════
fails = []


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    if not cond:
        fails.append(label)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


DB = os.path.join(TMP, "ast_probe_panel_hp.db")
if os.path.exists(DB):
    os.remove(DB)
PS.bind(db_path=DB)                                       # 真存档半边（宿主那五个口之一）
PS.init_db()
_ITS = st.domain("items") or {}
_HP_ITEM = next((k for k in sorted(_ITS)
                 if any(a.get("stat") == "hp" for a in (_ITS[k].get("affixes") or []))), "")


def three(cls, level, tag="", **over):
    """(面板, 档, 战斗 actor) 三个数 —— 档是**真存进库再读回来**的那一份。"""
    uid = "u_hp_%s_%d%s" % (cls or "none", level, ("_" + tag) if tag else "")
    rec = {"cls": cls, "level": level}
    rec.update(over)
    _stored = CA._p(dict(rec))                             # 出档口派生之后那一份
    _stored.pop("uid", None)                               # uid 是行键，不进字段（update_player 的形参）
    PS.update_player("g_hp", uid, **_stored)               # 落档
    back = PS.get_player("g_hp", uid)                      # ← 真从库里读回来
    rec = back                                             # 后面那句面板/actor 都吃库里那一份
    gear, buffs = panel_build.gear_and_buffs(rec)
    cap_panel = int(panel_build.build_actor(rec["cls"], level, rec.get("alloc"),
                                            gear, buffs=buffs)["max_hp"])
    return cap_panel, int(back["hp_max"]), int(CB.player_actor(back)["max_hp"])


print("")
print("── ★ P-27 三处一致：面板 / 档（真读档）/ 战斗里那只 actor")
print("  %-8s %-8s %-8s %-8s %s" % ("档", "面板", "档上", "actor", "判定"))
for cls, lv, want_cap in (("cls_knight", 1, 116), ("cls_knight", 2, 128),
                          ("cls_knight", 10, 224)):
    a1, a2, a3 = three(cls, lv)
    good = (a1 == a2 == a3 == want_cap)
    chk("%s L%s 三处同一个数 = %s" % (cls, lv, want_cap), good, "%s / %s / %s" % (a1, a2, a3))

print("")
print("── 六职业 1 级（面板 / 档 / actor 三处一致；90–140 那一档）")
_row = []
for cls in sorted((st.domain("classes") or {})):
    if str(cls).startswith("_"):
        continue
    a1, a2, a3 = three(cls, 1)
    _row.append((cls, a1, a2, a3))
    chk("%s 三处一致（%s）" % (cls, a1), a1 == a2 == a3, "%s / %s / %s" % (a1, a2, a3))
print("  1 级上限：%s" % " · ".join("%s=%s" % (r[0], r[1]) for r in _row))

print("")
print("── ② 加点 / 换装：三处**一起**动（不是写死的常数）")
_a1, _a2, _a3 = three("cls_knight", 1, tag="alloc", alloc={"VIT": 3})
_b1, _b2, _b3 = three("cls_knight", 1)
chk("加点 VIT×3 ⇒ 三处一致且高于裸档（%s > %s）" % (_a1, _b1),
    _a1 == _a2 == _a3 and _a1 > _b1, "%s / %s / %s" % (_a1, _a2, _a3))
if _HP_ITEM:
    _g1, _g2, _g3 = three("cls_knight", 1, tag="gear", equipped={"weapon": _HP_ITEM})
    chk("换一件带生命上限词条的装（%s）⇒ 三处一起涨（%s > %s）" % (_HP_ITEM, _g1, _b1),
        _g1 == _g2 == _g3 and _g1 > _b1, "%s / %s / %s" % (_g1, _g2, _g3))
else:
    chk("items 域里有带 hp 词条的装备（找不到 ⇒ 这条测不了）", False, _HP_ITEM)

print("")
print("── ③ 反证（fail-closed 有牙）")
_capless = CA._p({"cls": "", "hp": 100, "hp_max": 100})    # 老档那两格写死的 100
chk("还没有职业的档：上限「未定」（`_p` 不写那一格，旧的 100 也不留）",
    "hp_max" not in _capless and "hp" not in _capless, "%s" % sorted(_capless))
for label, fn in (("PB.hp_cap 无职业", lambda: panel_build.hp_cap({"cls": ""})),
                  ("战斗 actor 无职业", lambda: CB.player_actor({"cls": "", "level": 1})),
                  ("cmds_ast.hp_cap 无职业", lambda: CA.hp_cap(_capless))):
    try:
        fn()
        chk("%s ⇒ 抛 PanelMissing" % label, False, "没抛（错）")
    except panel_build.PanelMissing as e:
        chk("%s ⇒ 抛 PanelMissing（点名：%s）" % (label, str(e)[:34]), True)
try:
    panel_build.hp_cap({"cls": "cls_berserk"})
    chk("档上的职业不在 classes 域里 ⇒ 抛 PanelMissing", False, "没抛（错）")
except panel_build.PanelMissing as e:
    chk("档上的职业不在域里 ⇒ 抛 PanelMissing（%s）" % str(e)[:34], True)
chk("无职业 strict=False ⇒ None（呈现面那一档）",
    panel_build.hp_cap({"cls": ""}, strict=False) is None)

print("")
print("── ④ 静态守卫：content/*.py 里不许再出现写死的生命上限")
_HARD = (re.compile(r'["\'](?:hp_max|max_hp)["\']\s*:\s*\d'),
         re.compile(r'["\'](?:hp_max|max_hp)["\'][^\n]{0,20}?\bor\s+\d'))
_hits = []
for name in sorted(os.listdir(os.path.join(PKG, "content"))):
    if not name.endswith(".py"):
        continue
    src = open(os.path.join(PKG, "content", name), encoding="utf-8").read()
    for _i, line in enumerate(src.splitlines(), 1):
        if any(p.search(line) for p in _HARD):
            _hits.append("%s:%d %s" % (name, _i, line.strip()[:48]))
chk("写死的上限 0 处（原先 apply.py / cmds_ast.py 各一处）", not _hits, str(_hits))

print("")
print("── ⑤ ★ B3-9：`装备` / `卸下` 真改 equipped ⇒ 面板 / 档 / 战斗 actor 三处一起动；"
      "脱了逐字回原样（幂等）")
try:
    from content import cmds_gear as CG                              # noqa: E402
    from content import gear as GBM                                  # noqa: E402

    class _E9(object):
        """直调实现体：只要 env.save() + env.text（与别处同形）。"""

        def __init__(self, text=""):
            self.text = text

        def save(self):
            pass

    def _dr9(fn, p, text=""):
        out9 = []

        async def _go():
            async for _l in fn(_E9(text), None, "u_gear", p):
                out9.append(str(_l))

        asyncio.run(_go())
        return out9

    if not _HP_ITEM:
        chk("items 域里有带 hp 词条的装备（找不到 ⇒ 这条测不了）", False, _HP_ITEM)
    else:
        _it9 = _ITS[_HP_ITEM]
        _slot9 = _it9["slot"]
        _dhp9 = int(GBM.gear_stats({"equipped": {"_one": _HP_ITEM}, "enhance": {}}).get("hp", 0))
        _start9 = {"cls": "cls_knight", "level": 1, "hp": 100, "gold": 0,
                   "bag": {_HP_ITEM: 1}, "equipped": {}, "codex": {}, "flags": {}}

        def _store9(uid, rec):
            _r9 = CA._p(dict(rec))                     # 出档口派生之后那一份
            _r9.pop("uid", None)                       # uid 是行键，不进字段
            PS.update_player("g_gear", uid, **_r9)     # 落档
            return PS.get_player("g_gear", uid)        # ← 真从库里读回来

        _b0 = _store9("u_gear_0", _start9)
        _cap0g = int(_b0["hp_max"])
        _live = dict(_b0)
        _out_w = _dr9(CG.equip, _live, "装备 %s" % _it9["name"])
        _cap1g = int(_live.get("hp_max") or 0)
        _pan1 = int(panel_build.hp_cap(_live))
        _act1 = int(CB.player_actor(_live)["max_hp"])
        chk("★ 穿一件带 hp 词条的装（%s · +%s）：面板 / 档 / actor 三处一起涨（%s → %s）"
            % (_it9["name"], _dhp9, _cap0g, _cap0g + _dhp9),
            _cap1g == _pan1 == _act1 == _cap0g + _dhp9
            and _live.get("equipped") == {_slot9: _HP_ITEM} and not (_live.get("bag") or {}),
            "%s / %s / %s" % (_cap1g, _pan1, _act1))

        _b1 = _store9("u_gear_1", _live)
        chk("★ 穿上之后真落库再读回来：档上那格就是同一个数（%s）· 身上那格也对"
            % _b1.get("hp_max"),
            int(_b1["hp_max"]) == _cap0g + _dhp9 and _b1.get("equipped") == {_slot9: _HP_ITEM},
            "%s / %s" % (_b1.get("hp_max"), _b1.get("equipped")))

        _live2 = dict(_b1)
        _out_o = _dr9(CG.unequip, _live2, "卸下 %s" % _it9["name"])
        chk("★ 卸下：上限回到 %s · 背包 / 身上逐字回原样 · 现血不动" % _cap0g,
            int(_live2["hp_max"]) == _cap0g and _live2.get("bag") == _start9["bag"]
            and _live2.get("equipped") == _start9["equipped"]
            and int(_live2["hp"]) == int(_b0["hp"]),
            "%s / %s / %s" % (_live2.get("hp_max"), _live2.get("bag"), _live2.get("equipped")))

        _live3 = dict(_b0)
        _out_w2 = _dr9(CG.equip, _live3, "装备 %s" % _it9["name"])
        _out_o2 = _dr9(CG.unequip, _live3, "卸下 %s" % _it9["name"])
        _keys9 = ("cls", "level", "hp", "hp_max", "mo", "mo_max", "gold", "bag", "equipped")
        chk("★ 幂等：同一个起手档再跑一遍 —— 穿 / 脱两段**逐字相同**、档上那几格也一模一样",
            _out_w == _out_w2 and _out_o == _out_o2
            and all(_live3.get(k) == _live2.get(k) for k in _keys9),
            "%s vs %s" % (_out_w[:1], _out_w2[:1]))
        chk("★ 穿上那一句里报了「生命上限 %s → %s」" % (_cap0g, _cap0g + _dhp9),
            any(("生命上限 %s → %s" % (_cap0g, _cap0g + _dhp9)) in x for x in _out_w),
            "%s" % _out_w[:3])
except Exception as exc:                                            # noqa: BLE001
    chk("★ B3-9 装备进面板那条跑得起来（直调实现体 + 真存档）", False,
        "%s: %s" % (type(exc).__name__, exc))

print("")
print("── ⑥ ★ B3-14：`crit` / `eva` 两条**数值 → 率**（引擎把这两个当率读）")
#   引擎 `landing._roll_dodge` 读的是 `min(dodge, 0.40)`、暴击读的是 `random.random() < crit`
#   ⇒ 面板上必须是**率**。原先只率化了 crit：`eva` 原样传（骑士 10 / 刺客 20）⇒ 引擎 cap 到
#   0.40 ⇒ **六职业恒定 40% 闪避**（数值差异全被吃掉）。装备带的 crit / eva 也被 `set` 层盖掉。
_RATE_ROWS = []
for _cid in sorted((st.domain("classes") or {})):
    if str(_cid).startswith("_"):
        continue
    _a6 = panel_build.build_actor(_cid, 10, (st.domain("classes")[_cid] or {}).get("suggest_alloc"))
    _s6 = actor_stats(None, _a6)
    _RATE_ROWS.append((_cid, float(_s6.get("crit", 0)), float(_s6.get("dodge", 0)),
                       float(panel_build.panel_of(_cid, 10, (st.domain("classes")[_cid] or {}).get("suggest_alloc"))["eva"])))
chk("六职业的 crit / dodge 都是**率**（crit ∈ [0, 0.75] · dodge ∈ [0, 0.40]）",
    all(0.0 <= c <= 0.75 and 0.0 <= d <= 0.40 for _, c, d, _ in _RATE_ROWS),
    " · ".join("%s crit=%.4f dodge=%.4f" % (c.split("_")[-1], cr, dg) for c, cr, dg, _ in _RATE_ROWS))
_dg = {c: d for c, _, d, _ in _RATE_ROWS}
chk("★ dodge 跟着 `eva` 数值走（刺客 > 骑士 —— 原先两边都是 0.40，差异被 cap 吃掉）",
    _dg["cls_assassin"] > _dg["cls_knight"] > 0, "刺客 %.4f > 骑士 %.4f" % (_dg["cls_assassin"], _dg["cls_knight"]))

_CRIT_ITEM = next((k for k in sorted(_ITS)
                   if any(a.get("stat") == "crit" for a in (_ITS[k].get("affixes") or []))), "")
if not _CRIT_ITEM:
    chk("items 域里有带 crit 词条的装备（找不到 ⇒ 这条测不了）", False, _CRIT_ITEM)
else:
    _cv = int(next(a.get("v") for a in _ITS[_CRIT_ITEM]["affixes"] if a.get("stat") == "crit"))
    from content import gear as _GB                                       # noqa: E402
    _gear6 = _GB.gear_stats({"equipped": {_ITS[_CRIT_ITEM]["slot"]: _CRIT_ITEM}, "enhance": {}})
    _c0 = float(actor_stats(None, panel_build.build_actor("cls_knight", 1, None))["crit"])
    _c1 = float(actor_stats(None, panel_build.build_actor("cls_knight", 1, None, _gear6))["crit"])
    chk("★ 穿一件带 crit 词条的装（%s · +%s）⇒ 暴击率真涨（%.4f → %.4f）—— 原先 gear 那份被 set 层盖掉"
        % (_ITS[_CRIT_ITEM]["name"], _cv, _c0, _c1), _c1 > _c0)

print("")
print("── ⑦ ★ P-34（甲案：玩家自己加点）：点数只有一个口 · **上界（铺满）与下界（零加点）两头都用数字钉住**")
#   真源：`00_总纲/05_系统总表与阶段开放_v1.md`「五维加点（建号 8 + 每级 3）」
#        `06_第一阶段垂直切片/04_指令总表.md`「加点 <属性> [次数]」
#   裁决（2026-09-25 鱼鱼拍板 · 甲案）：**玩家自己加点**，不做「新档自动平铺」——
#   依据 `18_建号与新手引导_v1.md` §四「升到 2 级并加点」· `16_玩家体验走查_v1.md`「他能做什么 …加点」。
#   于是配平那把尺（怪面板 = 按建议权重**铺满**反推）是**参照上界**，玩家档上可以一个点都没投 = **下界**。
if os.path.join(PKG, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(PKG, "scripts"))
import rebuild_monsters as _RBM34                                     # noqa: E402
from content import alloc as _AL34                                    # noqa: E402

_L34 = list(range(1, 21)) + [40, 60, 80, 100]
_CLS34 = [c for c in sorted(panel_build.classes()) if not c.startswith("_")]

# ① 点数公式是**等级的线性函数**（不逐级硬编码）—— 扩到 100 级也成立
_bad34a = [_L for _L in _L34
           if _AL34.total_points(_L) != _AL34.LV1_POINTS + _AL34.PER_LEVEL_POINTS * (_L - 1)]
chk("★ P-34 点数 = `LV1_POINTS(%d) + PER_LEVEL_POINTS(%d) × (级−1)` —— 1/20/100 级 = %d/%d/%d 点"
    "（公式是等级的线性函数，不是逐级表：五阶段扩到 100 级照样成立）"
    % (_AL34.LV1_POINTS, _AL34.PER_LEVEL_POINTS, _AL34.total_points(1),
       _AL34.total_points(20), _AL34.total_points(100)),
    not _bad34a and (_AL34.total_points(1), _AL34.total_points(20), _AL34.total_points(100)) == (8, 65, 305),
    "%s" % _bad34a)

# ② `plan`（建议整数投法）与 `flat`（配平铺满）**都恰好把点投完**；两者每维差 < 1
_bad34b = []
for _L in _L34:
    for _cid in _CLS34:
        _p34, _f34 = _AL34.plan(_L, _cid), _AL34.flat(_L, _cid)
        if sum(_p34.values()) != _AL34.total_points(_L) or _AL34.balance(_L, _p34) != 0 \
                or abs(sum(_f34.values()) - _AL34.total_points(_L)) > 1e-9 \
                or max(abs(_p34[_s] - _f34[_s]) for _s in _f34) >= 1:
            _bad34b.append((_L, _cid, _p34, _f34))
chk("★ P-34 六职业 × (%d 个等级)：`plan`（整数投法）与 `flat`（配平铺满）都**余额 0**"
    "· 每维差 < 1（建议投法 = 配平基准的取整）；且生成器 `rebuild_monsters.alloc_of` 与本口同源"
    % len(_L34),
    not _bad34b, "%s" % _bad34b[:1])

# ③ 真敲「加点」（真存档半边）：档上那格真变 ⇒ 面板 / 档 / actor 三处一起动 · 余额对得上
class _E34(object):
    """直调实现体：只要 env.save() + env.text（与别处同形）。"""

    def __init__(self, text=""):
        self.text = text

    def save(self):
        pass


def _drive34(fn, rec, text=""):
    out34 = []

    async def _go():
        async for _l in fn(_E34(text), None, "u_p34", rec):
            out34.append(str(_l))

    asyncio.run(_go())
    return out34


_uid34 = "u_p34_alloc"
_rec34 = {"cls": "cls_knight", "level": 6, "hp": 0, "gold": 0, "bag": {}, "equipped": {}, "codex": {}, "flags": {}}


def _store34(rec):
    _r34 = CA._p(dict(rec))
    _r34.pop("uid", None)
    PS.update_player("g_hp", _uid34, **_r34)                     # 落档
    return PS.get_player("g_hp", _uid34)                         # ← 真从库里读回来


_b34 = _store34(_rec34)
_cap0_34 = int(_b34["hp_max"])
_live34 = dict(_b34)
_out34 = []
for _t34 in ("加点 力量 3", "加点 体质 2", "加点 意志 1"):
    _out34 += _drive34(CA.alloc_points, _live34, _t34)
_want34 = {_s: _n for _s, _n in (("STR", 3), ("VIT", 2), ("WIL", 1))}
_pan34 = int(panel_build.hp_cap(_live34))
_act34 = int(CB.player_actor(_live34)["max_hp"])
chk("★ P-34 真敲三次「加点」（骑士 6 级 · 共 %d 点）⇒ 档上那格真变 %s · 面板 / 档 / actor **三处同一个数**"
    "（%s → %s）· 余额 %s = 总点数 − 已花"
    % (_AL34.total_points(6), _want34, _cap0_34, _pan34, _AL34.left_of_record(_live34)),
    _AL34.of_record(_live34) == _want34 and _pan34 == int(_live34["hp_max"]) == _act34 > _cap0_34
    and _AL34.left_of_record(_live34) == _AL34.total_points(6) - 6, "%s / %s / %s" % (
        _AL34.of_record(_live34), _live34.get("hp_max"), _act34))

_want34lines = [CA.T("SYS_ALLOC_OK", stat=CA.T("SYS_STAT_STR"), n=3, now=3, left=20),
                CA.T("SYS_ALLOC_OK", stat=CA.T("SYS_STAT_VIT"), n=2, now=2, left=18),
                CA.T("SYS_ALLOC_OK", stat=CA.T("SYS_STAT_WIL"), n=1, now=1, left=17)]
chk("★ P-34 那三行回话**逐字**取自 texts 槽位（`SYS_ALLOC_OK`）：%s" % _out34[0],
    _out34 == _want34lines, "%s" % _out34)

_b34b = _store34(_live34)                                        # 加了点之后真落库再读回来
chk("★ P-34 加了点再落库读回：档上那格 = 面板 = actor（%s）—— 玩家加的点**真进了战斗面板**"
    % _b34b.get("hp_max"),
    int(_b34b["hp_max"]) == int(panel_build.hp_cap(_b34b)) == int(CB.player_actor(_b34b)["max_hp"]) == _pan34,
    "%s / %s" % (_b34b.get("hp_max"), _b34b.get("alloc")))

# ④ 战力两头（固定种子 40 场）：上界 / 建议投法 / 下界 —— 数字钉死，别再"感觉差一倍"
_MON34 = st.domain("monsters") or {}


def _rec34_of(level, cid, mode):
    _al34 = {"flat": lambda: _AL34.flat(level, cid), "plan": lambda: _AL34.plan(level, cid),
             "none": lambda: {}}[mode]()
    _pl34 = {"cls": cid, "level": level, "uid": "u_b34", "name": "试", "alloc": _al34,
             "bag": {}, "gold": 0}
    _pl34["hp"] = CA.hp_cap(_pl34)
    return _pl34


def _run34(mid, level, cid, mode, n=40):
    _w34, _acts34 = 0, []
    for _s34 in range(n):
        _pl34 = _rec34_of(level, cid, mode)
        _r34, _logs34, _hp34 = CB.run_auto(_pl34, [mid], _MON34, seed=1000 + _s34)
        _w34 += 1 if _r34 == "victory" else 0
        _acts34.append(sum(1 for _x in _logs34 if ("🌀 %s 开始出招" % _pl34["name"]) in _x))
    _acts34.sort()
    return _w34, _acts34[len(_acts34) // 2]


_END34 = {}
for _mid34, _lv34, _cid34, _tag34 in (("ms_wild_dog", 6, "cls_knight", "普通·野狗 lv6"),
                                      ("ms_bitten_lumberjack", 9, "cls_knight", "精英·被咬过的伐木工 lv9")):
    _u34 = _run34(_mid34, _lv34, _cid34, "flat")
    _p34 = _run34(_mid34, _lv34, _cid34, "plan")
    _d34 = _run34(_mid34, _lv34, _cid34, "none")
    _END34[_mid34] = (_u34, _p34, _d34)
    print("     %-22s 上界（铺满）%2d/40 出手 %2d ｜ 建议整数投法 %2d/40 出手 %2d ｜ 下界（零加点）%2d/40 出手 %2d"
          % (_tag34, _u34[0], _u34[1], _p34[0], _p34[1], _d34[0], _d34[1]))
chk("★ P-34 两头钉住（骑士 · 固定种子 40 场）：**普通怪**（野狗 lv6）上界 40/40 出手 6 → 下界 13/40 出手 15"
    "（出手 2.5×）· **精英**（被咬过的伐木工 lv9）上界 40/40 → 下界 0/40 ⇒ 「照样打得完」与"
    "「当场倒地」都在这一条上（口径一变就红）",
    _END34["ms_wild_dog"][0][0] == 40 and _END34["ms_wild_dog"][2][0] <= 20
    and _END34["ms_wild_dog"][2][1] >= 1.5 * _END34["ms_wild_dog"][0][1]
    and _END34["ms_bitten_lumberjack"][0][0] == 40
    and _END34["ms_bitten_lumberjack"][2][0] <= 4,
    "%s / %s" % (_END34["ms_wild_dog"], _END34["ms_bitten_lumberjack"]))

print("")
print("── ⑧ ★ P-34 跨 100 级：面板成长与上限也用**等级函数**表达（1/20/40/60/80/100 六个锚点）")
_ANC34 = (1, 20, 40, 60, 80, 100)
_TAB34 = []
for _L in _ANC34:
    _a34 = _RBM34.avg_panel(_L)
    _m34 = _RBM34.panel_of(_L, "普通", "杂兵")
    _tab34 = {"L": _L, "pts": _AL34.total_points(_L), "hp": _a34["hp"], "atk": _a34["atk"],
              "matk": _a34["matk"], "def": _a34["def"], "mdef": _a34["res"],
              "spd": sum(_RBM34.player_panel(_L, _c)["spd"] for _c in _CLS34) / len(_CLS34),
              "mhp": _m34["hp"], "m_atk": _m34["atk"], "m_def": _m34["def"], "m_res": _m34["res"],
              "perhit": _RBM34.standard_per_hit(_L)}
    _TAB34.append(_tab34)
    print("     L%-4d %3d 点 ｜ 玩家(铺满均值) hp %7.0f atk %6.1f matk %6.1f def %6.1f mdef %6.1f spd %6.1f"
          " ｜ 同级基准怪 hp %5d atk %4d def %4d ｜ 挨 %4.1f 下"
          % (_L, _tab34["pts"], _tab34["hp"], _tab34["atk"], _tab34["matk"], _tab34["def"],
             _tab34["mdef"], _tab34["spd"], _tab34["mhp"], _tab34["m_atk"], _tab34["m_def"],
             _tab34["hp"] / max(_tab34["m_atk"], 1)))

_bad34c = []
for _i, _t in enumerate(_TAB34):
    # 怪 hp 就是照「标准单次行动伤害 × 4」反推的（配平口径是等级的 ⇒ L100 也照样成立）
    if _t["mhp"] != round(_t["perhit"] * 4):
        _bad34c.append(("怪 hp 与 per_hit×4 对不上", _t["L"], _t["mhp"], round(_t["perhit"] * 4)))
    if _i:                                    # 面板单调增（不出现"某级之后往回掉"）
        _p34 = _TAB34[_i - 1]
        for _k34 in ("hp", "atk", "matk", "def", "mdef", "spd"):
            if _t[_k34] <= _p34[_k34]:
                _bad34c.append(("面板不增", _t["L"], _k34))
    # 玩家挨的怪攻击次数稳定（不秒杀 · 也不无敌）· 通道 ÷ 怪防不倒挂
    if not 8.0 <= _t["hp"] / max(_t["m_atk"], 1) <= 30.0:
        _bad34c.append(("挨几下出界", _t["L"], _t["hp"] / max(_t["m_atk"], 1)))
    for _c in _CLS34:
        _p34 = _RBM34.player_panel(_t["L"], _c)
        _ch34 = panel_build.classes()[_c]["dmg_channel"]
        _basis34 = _p34["atk"] if _ch34 == "phys" else _p34["matk"]
        _prot34 = _t["m_def"] if _ch34 == "phys" else _t["m_res"]
        if _basis34 < 1.5 * _prot34:
            _bad34c.append(("通道被怪防压住", _t["L"], _c, _basis34, _prot34))
_HP34 = _TAB34[-1]["hp"] / _TAB34[0]["hp"]
_AT34 = _TAB34[-1]["atk"] / _TAB34[0]["atk"]
chk("★ P-34 六个锚点（1/20/40/60/80/100 级）：面板**单调增 · 不爆**（hp %0.2f× · atk %0.2f× 拉满 100 级）"
    "· 同级基准怪 hp 仍 = 标准单发×4（配平是等级函数 ⇒ L100 照样成立）· 玩家挨的怪攻击 %0.1f~%0.1f 下"
    "（跨 100 级稳定）· 六职业的伤害通道都在怪防 1.5 倍以上（不倒挂）"
    % (_HP34, _AT34, min(_t["hp"] / max(_t["m_atk"], 1) for _t in _TAB34),
       max(_t["hp"] / max(_t["m_atk"], 1) for _t in _TAB34)),
    not _bad34c and _HP34 < 25.0 and _AT34 < 35.0, "%s" % _bad34c[:3])

# ⑤ L100 也真敲一次（余额 / 上限的校验不许在低等级写死常数）
_l100 = _rec34_of(100, "cls_knight", "none")
_o100 = _drive34(CA.alloc_points, _l100, "加点 力量 1")
_o100b = _drive34(CA.alloc_points, _l100, "加点 力量 %d" % (_AL34.total_points(100) + 1))
chk("★ P-34 100 级真敲：加 1 点 ⇒ 还剩 %d 点（%d − 1）· 想加 %d 点（超总点数）⇒ 只说不够、**不动档**"
    % (_AL34.total_points(100) - 1, _AL34.total_points(100), _AL34.total_points(100) + 1),
    _o100 == [CA.T("SYS_ALLOC_OK", stat=CA.T("SYS_STAT_STR"), n=1, now=1,
                   left=_AL34.total_points(100) - 1)]
    and _o100b == [CA.T("SYS_ALLOC_SHORT", stat=CA.T("SYS_STAT_STR"),
                        n=_AL34.total_points(100) + 1, left=_AL34.total_points(100) - 1,
                        usage=str((CA._data("commands").get("alloc") or {}).get("usage") or ""))]
    and _AL34.of_record(_l100) == {"STR": 1},
    "%s / %s / %s" % (_o100, _o100b, _AL34.of_record(_l100)))

print("")
print("===== %s =====" % ("★ P-27 三处一致 + 反证都过 ✅" if not fails else "P-27 有红 ❌ %s" % fails))
sys.exit(0 if ok else 1)
