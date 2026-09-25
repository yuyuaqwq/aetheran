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
print("===== %s =====" % ("★ P-27 三处一致 + 反证都过 ✅" if not fails else "P-27 有红 ❌ %s" % fails))
sys.exit(0 if ok else 1)
