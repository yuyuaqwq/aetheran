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
print("── ⑦ ★ B3-19：装备**属性门槛** —— 值 = 品质倍数 × `alloc_of` 那个口 · 双向穿戴矩阵 · 六锚点")
#   真源：主线 2026-09-25 裁决（「装备应该也是要依赖加点才能穿的吧」）——
#   门槛挂在「家族 × 品质」上，值 = 倍数 × 该门槛级按建议加点铺满时主属性的值。
#   本节判四件事：
#     ① 域里每个 `v` 都由探针**现算**（倍率 × `rebuild_monsters.alloc_of`）—— 手改域里那个数就翻红
#     ② 双向：铺满该属性 ⇒ 门槛级到了就穿得上；把点全丢到别的属性 ⇒ 一件都穿不上
#     ③ 六锚点（1/20/40/60/80/100）：门槛/建议加点 = 倍率，**与等级无关** ⇒
#        既不会「高级永远穿不上」，也不会「高级门槛形同虚设」（对**同阶**装备而言）
#     ④ 真跑两个方向（直调 `cmds_gear.equip`）—— 不够那一句逐字来自 texts + 档**一个字没动**
try:
    import math as _m7                                                        # noqa: E402
    sys.path.insert(0, os.path.join(PKG, "scripts"))
    import rebuild_monsters as _RBM7                                          # noqa: E402
    import rebuild_item_reqs as _RIR7                                         # noqa: E402
    from content import cmds_gear as _CG7                                     # noqa: E402

    _CLS7 = {k: v for k, v in (st.domain("classes") or {}).items()
             if not str(k).startswith("_")}
    _MON7 = st.domain("monsters") or {}
    _EQ7 = {k: v for k, v in (st.domain("items") or {}).items() if v.get("slot")}
    _LV7 = {q: _RIR7.req_level_of(q, _MON7) for q in ("精制", "稀有", "遗物")}
    _TOT7 = lambda L: 8 + 3 * (L - 1)          # 建号 8 点 + 每级 3 点（07_装备体系_v2 §一）
    _PL7 = (1, 6, 10, 20)                      # 判据给的四档（主线口径）
    _PAIR7 = ((1, "普通"), (6, "精制"), (10, "稀有"), (20, "遗物"))

    # ① 逐件重算
    _bad7a, _n7a = [], 0
    for _k7, _v7 in sorted(_EQ7.items()):
        _r7 = _v7.get("req")
        if not _r7:
            continue
        _n7a += 1
        _cid7 = _RIR7.ref_class_for_item(_CLS7, _k7, _r7["attr"])
        _ref7 = float(_RBM7.alloc_of(_r7["level"], _cid7)[_r7["attr"]])
        _exp7 = max(1, int(_m7.floor(_RIR7.QUALITY_MULT[_v7["quality"]] * _ref7 + 0.5)))
        if _exp7 != _r7["v"]:
            _bad7a.append((_k7, _r7["v"], _exp7))
    chk("★ ① 逐件重算（%d 件）：`v` = 四舍五入(倍率 × `alloc_of`(门槛级, 参考职业)[属性])"
        % _n7a, not _bad7a, "%s" % _bad7a[:3])

    # ①之二 家族 × 品质 → （门槛级, 值）
    _TBL7: dict = {}
    for _k7, _v7 in sorted(_EQ7.items()):
        _r7 = _v7.get("req")
        if not _r7:
            continue
        _TBL7.setdefault((_RIR7.family_of(_k7), _r7["attr"], _v7["quality"]), set()).add(
            (_r7["level"], _r7["v"]))
    print("     家族 × 品质 →（门槛级 · 值）：")
    for (_f7, _a7, _q7), _s7 in sorted(_TBL7.items()):
        _lv7_, _vv7 = sorted(_s7)[0]
        print("       %-24s %-4s %-3s ≥ %-3s（门槛级 %s）" % (_f7, _q7, _a7, _vv7, _lv7_))

    # ② 双向穿戴矩阵：六职业 × 四档等级 × 四档品质
    def _rep7(cid, q):
        """该职业在该品质下能用的**代表件**：自己那两把武器 + 通用防具那五个有门槛的家族。"""
        out = []
        for _k, _v in sorted(_EQ7.items()):
            if _v.get("quality") != q:
                continue
            _fam = _RIR7.family_of(_k)
            if _fam.startswith("weapon_"):
                if _fam.split("_")[1] != cid[4:]:
                    continue
            elif _fam not in _RIR7.FAMILY_ATTR:
                continue
            out.append(_k)
        return out

    _bad7b = []
    print("     双向穿戴矩阵（铺满该件要的那一维 / 把点全丢到别处）：")
    for _cid7 in sorted(_CLS7):
        for _L7 in _PL7:
            _cells7 = []
            for _q7 in ("普通", "精制", "稀有", "遗物"):
                _its7 = _rep7(_cid7, _q7)
                _needs7 = [(_k, _EQ7[_k]["req"]) for _k in _its7 if _EQ7[_k].get("req")]
                if not _its7:
                    _cells7.append("%s:（没有这一档）" % _q7)
                    continue
                if not _needs7:
                    _cells7.append("%s:无门槛" % _q7)
                    continue
                _lvneeded7 = max(_r["level"] for _k, _r in _needs7)
                _most7 = max(_r["v"] for _k, _r in _needs7)
                if _lvneeded7 > _L7:                      # 装备还没到手（门槛级没到）
                    _cells7.append("%s:未到门槛级（L%s）" % (_q7, _lvneeded7))
                    continue
                if _TOT7(_L7) < _most7:                   # ★ 门槛级到了却铺满也穿不上 = 真红
                    _bad7b.append(("铺满也穿不上", _cid7, _L7, _q7, _most7, _TOT7(_L7)))
                if min(_r["v"] for _k, _r in _needs7) < 1:  # 反方向要有牙：v ≥ 1 ⇒ 0 点必穿不上
                    _bad7b.append(("门槛值 < 1（0 点也穿得上）", _cid7, _L7, _q7))
                _cells7.append("%s:可（≥%s）" % (_q7, _most7))
            print("       %-14s L%-3s %s" % (_cid7, _L7, " ｜ ".join(_cells7)))
    chk("★ ② 正方向：凡「门槛级 ≤ 该等级」的格子，把点数**铺满**那一维 ⇒ 都穿得上",
        not [x for x in _bad7b if x[0] == "铺满也穿不上"], "%s" % _bad7b[:3])
    chk("★ ② 反方向：凡有门槛的件，`v ≥ 1` ⇒ 把点**全丢到别的属性**（0 点）一件都穿不上",
        not [x for x in _bad7b if x[0].startswith("门槛值 < 1")], "%s" % _bad7b[:3])
    _pair7 = []
    for _L7, _q7 in _PAIR7:
        for _cid7 in sorted(_CLS7):
            _its7 = _rep7(_cid7, _q7)
            if not _its7:
                _pair7.append((_cid7, _L7, _q7, "这一档一件都没有（覆盖有洞）"))
                continue
            _nd7 = [_EQ7[k]["req"]["v"] for k in _its7 if _EQ7[k].get("req")]
            if _nd7 and _TOT7(_L7) < max(_nd7):      # 普通那一档没有 req ⇒ 无门槛，天然穿得上
                _pair7.append((_cid7, _L7, _q7, "铺满也穿不上"))
    chk("★ ② 配对档（L1/普通 · L6/精制 · L10/稀有 · L20/遗物 · 六职业 × %d 格）= 铺满都穿得上且覆盖非空"
        % len(_PAIR7), not _pair7, "%s" % _pair7[:3])

    # ③ 六锚点：门槛/建议加点 = 倍率（与等级无关）—— 两个方向的自检
    print("     六锚点（门槛若按该锚点当门槛级 · 精制/稀有/遗物）：")
    _bad7c = []
    for _L7 in (1, 20, 40, 60, 80, 100):
        _cells7 = []
        for _a7 in ("STR", "AGI", "VIT", "INT", "WIL"):
            _cid7 = _RIR7.ref_class_of(_CLS7, _a7)
            _sug7 = float(_RBM7.alloc_of(_L7, _cid7)[_a7])
            _vs7 = [_RIR7.req_value(_a7, _q7, _L7, _CLS7, _cid7) for _q7 in ("精制", "稀有", "遗物")]
            for _q7, _v7v in zip(("精制", "稀有", "遗物"), _vs7):
                if abs(_v7v / _sug7 - _RIR7.QUALITY_MULT[_q7]) > 0.5 / _sug7 + 1e-9:
                    _bad7c.append((_L7, _a7, _q7, _v7v, _sug7))
            if not (0.6 <= min(_vs7) / _sug7 <= 1.15):      # 够得着（≤1.05）也不虚设（≥0.7）
                _bad7c.append((_L7, _a7, "比例出界", min(_vs7) / _sug7))
            _cells7.append("%s:%s" % (_a7, "/".join("%d" % x for x in _vs7)))
        print("       L%-4s %s（建议加点 = %s）"
              % (_L7, " ".join(_cells7),
                 "/".join("%d" % _RBM7.alloc_of(_L7, _RIR7.ref_class_of(_CLS7, _a7))[_a7]
                          for _a7 in ("STR", "VIT", "INT"))))
    chk("★ ③ 六锚点：门槛/建议加点**恒 = 倍率**（0.70 / 0.90 / 1.05 · 与等级无关）+ 比例落在 [0.6, 1.15]"
        "（不会永远穿不上 · 也不会形同虚设）", not _bad7c, "%s" % _bad7c[:3])

    # ④ 真跑两个方向（直调实现体）：不够那一句 + 档一个字没动 / 够了那一句 + 真穿上
    class _E7(object):
        def __init__(self, text=""):
            self.text = text

        def save(self):
            pass

    def _dr7(fn, p, text=""):
        _out7 = []

        async def _go7():
            async for _l7 in fn(_E7(text), None, "u_req7", p):
                _out7.append(str(_l7))

        asyncio.run(_go7())
        return _out7

    _cat7 = next((k for k in sorted(_EQ7)
                  if _EQ7[k].get("req") and k.endswith("_refined")), "")
    if not _cat7:
        _cat7 = next((k for k in sorted(_EQ7) if _EQ7[k].get("req")), "")
    _rq7 = _EQ7[_cat7]["req"]
    _cw7 = _RIR7.ref_class_for_item(_CLS7, _cat7, _rq7["attr"])
    _start7 = {"cls": _cw7, "level": _rq7["level"], "hp": 100, "bag": {_cat7: 1},
               "equipped": {}, "codex": {}, "flags": {}}
    _lack7 = dict(_start7, alloc={})
    _enuf7 = dict(_start7, alloc={_rq7["attr"]: int(_rq7["v"])})
    _weak7 = "装备 %s" % _EQ7[_cat7].get("name", _cat7)
    _out_lack7 = _dr7(_CG7.equip, _lack7, _weak7)
    _out_enuf7 = _dr7(_CG7.equip, _enuf7, _weak7)
    _want_lack7 = CA.T("SYS_GEAR_REQ", name=_EQ7[_cat7].get("name", _cat7),
                       attr=CA.T("SYS_STAT_%s" % _rq7["attr"]), need=int(_rq7["v"]),
                       have=0, gap=int(_rq7["v"]))
    chk("★ ④ 真跑 `装备`（%s · 要 %s %s）：不够 ⇒ 逐字「%s」· 档上一个字没动（bag / equipped / hp_max）"
        % (_cat7, _rq7["attr"], _rq7["v"], _want_lack7),
        _out_lack7 == [_want_lack7]
        and _lack7.get("bag") == {_cat7: 1} and _lack7.get("equipped") == {}
        and "hp_max" not in _lack7,
        "%s / %s" % (_out_lack7[:1], {k: _lack7.get(k) for k in ("bag", "equipped")}))
    chk("★ ④ 真跑 `装备` 另一个方向：加点够了 ⇒ 穿上那一句 + 真进 `equipped`"
        % (),
        _out_enuf7[:1] == [CA.T("SYS_GEAR_EQUIP_OK", icon=_EQ7[_cat7].get("icon", ""),
                                name=_EQ7[_cat7].get("name", _cat7),
                                kind=_EQ7[_cat7].get("kind", ""))]
        and _enuf7.get("equipped") == {_EQ7[_cat7]["slot"]: _cat7},
        "%s / %s" % (_out_enuf7[:1], _enuf7.get("equipped")))
    # 旧档：那件已经穿在身上、点数又不够 ⇒ 照「已经穿在身上了」说（门槛不在这一格报）
    _old7 = {"cls": _cw7, "level": _rq7["level"], "hp": 100, "bag": {}, "alloc": {},
             "equipped": {_EQ7[_cat7]["slot"]: _cat7}, "codex": {}, "flags": {}}
    _out_old7 = _dr7(_CG7.equip, _old7, "装备 %s" % _EQ7[_cat7].get("name", _cat7))
    chk("★ ④ 旧档（身上那件、点数为 0）：`装备` 同一件照「已经穿在身上了」说 —— 不报门槛、不强制脱",
        _out_old7 == [CA.T("SYS_GEAR_WORN", name=_EQ7[_cat7].get("name", _cat7))]
        and _old7.get("equipped") == {_EQ7[_cat7]["slot"]: _cat7},
        "%s" % _out_old7[:1])
except Exception as exc:                                                      # noqa: BLE001
    chk("★ B3-19 装备门槛那一节跑得起来", False, "%s: %s" % (type(exc).__name__, exc))

print("")
print("===== %s =====" % ("★ P-27 三处一致 + 反证都过 ✅" if not fails else "P-27 有红 ❌ %s" % fails))
sys.exit(0 if ok else 1)
