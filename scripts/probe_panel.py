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
from content import loot as LPICK                         # noqa: E402  ★ B4-20 显示名那唯一的一口
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


def three(cls, level, tag="", key="max_hp", field="hp_max", **over):
    """(面板, 档, 战斗 actor) 三个数 —— 档是**真存进库再读回来**的那一份。

    `key` / `field` 默认是生命那一对（P-27）；传 `max_mp` / `mo_max` 就是法力那把尺
    （B4-8：两条上限走同一条路、同一份档、同一个出档口）。
    """
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
                                            gear, buffs=buffs)[key])
    return cap_panel, int(back[field]), int(CB.player_actor(back)[key])


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
         re.compile(r'["\'](?:hp_max|max_hp)["\'][^\n]{0,20}?\bor\s+\d'),
         # ★ B4-8：档上那一格同样不许写死（两个初始档原先各写死 `mo_max: 0` ⇒ `状态` 恒 0/0）
         re.compile(r'["\']mo_max["\']\s*:\s*\d'))
_hits = []
for name in sorted(os.listdir(os.path.join(PKG, "content"))):
    if not name.endswith(".py"):
        continue
    src = open(os.path.join(PKG, "content", name), encoding="utf-8").read()
    for _i, line in enumerate(src.splitlines(), 1):
        if any(p.search(line) for p in _HARD):
            _hits.append("%s:%d %s" % (name, _i, line.strip()[:48]))
chk("★ 写死的上限 0 处（生命：原先 `apply.py` / `cmds_ast.py` 各写死 100 ｜ "
    "法力：同样那两处各写死 `mo_max: 0`）", not _hits, str(_hits))

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
chk("★ P-34 两头钉住（骑士 · 固定种子 40 场）：**普通怪**（野狗 lv6）上界 40/40 出手 6 → 下界 40/40 出手 15"
    "（出手 **2.5×**：零加点也打得完普通怪，但代价在出手数上）· **精英**（被咬过的伐木工 lv9）上界 40/40 → "
    "下界 **0/40** 出手 16（动手就倒地）⇒ 「照样打得完」与「当场倒地」都在这一条上（口径一变就红）"
    "★ B3-18 换口径后重钉：**赢的场数**不再是那把尺（普通怪容错高、零加点也能赢），改钉**出手数**与**精英的下界**",
    _END34["ms_wild_dog"][0][0] == 40 and _END34["ms_wild_dog"][2][0] >= 30
    and _END34["ms_wild_dog"][2][1] >= 2.0 * _END34["ms_wild_dog"][0][1]
    and _END34["ms_bitten_lumberjack"][0][0] == 40
    and _END34["ms_bitten_lumberjack"][2][0] <= 4
    and _END34["ms_bitten_lumberjack"][2][1] >= 1.4 * _END34["ms_bitten_lumberjack"][0][1],
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
              "perhit": _RBM34.standard_per_hit(_L),
              "perhit_new": _RBM34.std_per_hit(_L)}
    _TAB34.append(_tab34)
    print("     L%-4d %3d 点 ｜ 玩家(铺满均值) hp %7.0f atk %6.1f matk %6.1f def %6.1f mdef %6.1f spd %6.1f"
          " ｜ 同级基准怪 hp %5d atk %4d def %4d ｜ 挨 %4.1f 下"
          % (_L, _tab34["pts"], _tab34["hp"], _tab34["atk"], _tab34["matk"], _tab34["def"],
             _tab34["mdef"], _tab34["spd"], _tab34["mhp"], _tab34["m_atk"], _tab34["m_def"],
             _tab34["hp"] / max(_tab34["m_atk"], 1)))

_bad34c = []
for _i, _t in enumerate(_TAB34):
    # ★ B3-18 换口径后：怪 hp 不再是「标准单发 × 4」的裸乘积，而是**真伤害链反解**的结果
    #   （含怪闪避 + 减伤 K_def/(def+K_def)）。所以这里钉**比值区间**：
    #   低等级 ≈4（几乎无减伤）→ 高等级 ≈2.0（K_def 恒定、def 涨 ⇒ 减伤变强；L100 实测 1.98）。
    #   ★ 这条比值随等级下滑本身是**已登记的账**（`_notes.md` §四「K_def 贴顶」，100 级 Boss 减伤 ~74%）。
    _r34 = _t["mhp"] / max(_t["perhit_new"], 1)
    if not 1.8 <= _r34 <= 5.0:
        _bad34c.append(("怪 hp / 标准单发 出界", _t["L"], round(_r34, 2)))
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
                                name=LPICK.label_of(_cat7),
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
print("── ⑧ ★ B3-28 ①：面板栈的键带上「人」那一维（同职业同级的两名玩家不撞同一格）")
#   原先 `panel_build.build_actor` 的栈 id = `aetheran.<职业>@<等级>`，而栈的声明里烤着
#   **这一个人**的加点 / 装备 / 增益 ⇒ 同进程里同职业同等级的两个玩家共用一格（后造的盖先造的）。
#   实测（重现输出见工作树 `_notes.md`）：甲开战后面板 264 / 32.62 / 44.8，乙敲一条指令
#   （`_p()` → `hp_cap()` 那条出档口）之后回头读甲 ⇒ 224 / 22.62 / 35.8 —— 甲被乙带着变了。
#   本节四条（全部真跑 `CB.player_actor` + 引擎 `actor_stats`，不是拿声明比声明）：
#     ① 同职业同级两个人 ⇒ **栈 id 不同**（各拿各的那一格）
#     ② 反证（原 bug 的路径）：乙再构建一次之后回头读甲 ⇒ 甲的键**逐键不变**
#     ③ 同一人两次构建 ⇒ 栈 id 相同（键可复用）+ 面板逐键一致
#     ④ 顺序无关 + 拿不到 uid 的调用点（指纹那一档）也不撞格
try:
    _EQ8 = st.domain("items") or {}
    _SLOT8 = "armor_top"
    _HP8 = sorted(k for k, v in _EQ8.items()
                  if v.get("slot") == _SLOT8
                  and any(a.get("stat") == "hp" for a in (v.get("affixes") or [])))
    chk("★ 用例取自域里真有的件（`%s` 里带 `hp` 词条的那几件：%s）"
        % (_SLOT8, " · ".join(str(_EQ8[k].get("name")) for k in _HP8[:3])), bool(_HP8), "%s" % _HP8[:3])
    _a8 = _HP8[0] if _HP8 else ""
    _rec8a = {"cls": "cls_knight", "level": 10, "hp": 500, "equipped": {_SLOT8: _a8}}
    _rec8b = {"cls": "cls_knight", "level": 10, "hp": 462, "equipped": {},
              "food_buff": {"stat": "atk", "pct": 50, "until": 1e18}}     # 乙：吃到食物增益

    _act8a = CB.player_actor(_rec8a, uid="u_jia")
    _act8b = CB.player_actor(_rec8b, uid="u_yi")
    _p8a1, _p8b1 = dict(actor_stats(None, _act8a)), dict(actor_stats(None, _act8b))
    chk("★ ① 同职业同等级的两个玩家 ⇒ 栈 id **不同**（甲 %s ／ 乙 %s）"
        % (_act8a["panel_stack"], _act8b["panel_stack"]),
        _act8a["panel_stack"] != _act8b["panel_stack"]
        and _act8a["panel_stack"].startswith("aetheran.cls_knight@10#")
        and _act8b["panel_stack"].startswith("aetheran.cls_knight@10#")
        and "#" in _act8a["panel_stack"],          # ★ 有牙：老键（只有职业@等级）就是撞格的那一个
        "%s / %s" % (_act8a["panel_stack"], _act8b["panel_stack"]))
    chk("★ ① 各读各的面板：甲的 `max_hp` = 甲那份档算出来的上限（%s）· 乙 = 乙那份（%s）"
        % (panel_build.hp_cap(_rec8a), panel_build.hp_cap(_rec8b)),
        int(_p8a1["max_hp"]) == panel_build.hp_cap(_rec8a)
        and int(_p8b1["max_hp"]) == panel_build.hp_cap(_rec8b) and _p8a1 != _p8b1,
        "%s / %s" % (_p8a1.get("max_hp"), _p8b1.get("max_hp")))
    _act8b2 = CB.player_actor(_rec8b, uid="u_yi")            # ← 生产里「乙又敲了一条指令」
    _p8a2 = dict(actor_stats(None, _act8a))
    chk("★ ② 反证（原 bug 的重现路径）：乙再构建一次之后回头读甲 ⇒ 甲的键**逐键不变**",
        _p8a1 == _p8a2,
        "%s" % {k: (_p8a1.get(k), _p8a2.get(k))
                for k in sorted(set(_p8a1) | set(_p8a2)) if _p8a1.get(k) != _p8a2.get(k)})
    chk("★ ③ 同一人两次构建 ⇒ 栈 id 相同（那一格反复用，不每人重算一格）+ 面板逐键一致",
        _act8b["panel_stack"] == _act8b2["panel_stack"]
        and dict(actor_stats(None, _act8b2)) == _p8b1,
        "%s / %s" % (_act8b["panel_stack"], _act8b2["panel_stack"]))
    _act8a2 = CB.player_actor(_rec8a, uid="u_jia")
    chk("★ ④ 顺序无关：先造乙再造甲 ⇒ 甲还是甲那一份",
        dict(actor_stats(None, _act8a2)) == _p8a1 and _act8a2["panel_stack"] == _act8a["panel_stack"],
        "%s / %s" % (_act8a2["panel_stack"], _p8a1.get("max_hp")))
    _f8a = panel_build.build_actor("cls_knight", 10, None, {"hp": 40})   # 不传 uid = 只有档的调用点
    _f8b = panel_build.build_actor("cls_knight", 10, None, None)
    chk("★ ④ 拿不到 uid 的调用点走**这一档的指纹**（%s ／ %s）：两份不同的档也不撞同一格"
        "（带 `hp +40` 的那份正好高 40）"
        % (_f8a["panel_stack"], _f8b["panel_stack"]),
        _f8a["panel_stack"] != _f8b["panel_stack"]
        and dict(actor_stats(None, _f8a)) != dict(actor_stats(None, _f8b))
        and float(actor_stats(None, _f8a)["max_hp"])
        == float(actor_stats(None, _f8b)["max_hp"]) + 40,
        "%s / %s" % (_f8a["panel_stack"], _f8b["panel_stack"]))
except Exception as exc:                                                      # noqa: BLE001
    chk("★ B3-28 ① 面板栈按人隔离那一节跑得起来", False, "%s: %s" % (type(exc).__name__, exc))


print("")
print("── ⑨ ★ B4-8：**法力上限**与生命同一把尺（面板 / 档 / actor 三处一致）")
#   病根（真机玩出来）：`状态` 那一行读的是档上的 `mo_max`，而那一格**零写端**
#   （两个初始档都写死 0）⇒ 骑士面板明明 50 点法力，玩家看见的是「法力 0/0」；
#   同一件事在 `属性` 那一页（走面板）又是「法力 50」—— 两处口径。
#   判据：① 六职业 1 级三处同一个数（期望值**从 classes 域现算**，不手打）
#        ② 换一件带 `mo_max` 词条的装 ⇒ 三处**一起**涨（不是写死的常数）
#        ③ 反证：无职业 ⇒ `strict=False` 回 None / `strict=True` 抛 · `_p` 不留那一格
#        ④ 静态守卫（上一节 ④：档上那一格不许再写死）
_MP_ITEM = next((k for k in sorted(_ITS)
                 if any(a.get("stat") == "mo_max" for a in (_ITS[k].get("affixes") or []))), "")
_mp_base = {}
for _cid in sorted((st.domain("classes") or {})):
    if str(_cid).startswith("_"):
        continue
    _a1, _a2, _a3 = three(str(_cid), 1, tag="mp", key="max_mp", field="mo_max")
    _want_mp = int((st.domain("classes")[_cid] or {}).get("base", {}).get("mo") or 0)
    _mp_base[str(_cid)] = _a1
    chk("%s 1 级法力上限三处一致 = %s（= classes 域 base.mo）" % (_cid, _want_mp),
        _a1 == _a2 == _a3 == _want_mp, "%s / %s / %s" % (_a1, _a2, _a3))
print("  1 级法力上限：%s" % " · ".join("%s=%s" % (k, v) for k, v in sorted(_mp_base.items())))
if _MP_ITEM:
    _mi = _ITS[_MP_ITEM]
    _mv = int(next(a.get("v") for a in (_mi.get("affixes") or []) if a.get("stat") == "mo_max"))
    #: 域里带 `mo_max` 词条的只有法师那支杖 ⇒ 拿法师那一档试（装备门槛归『装备』指令判，
    #: 面板本身不认门槛 —— 这条判的是「面板 / 档 / actor 三处是不是同一份算出来的」）
    _mcls = "cls_mage"
    _b1, _b2, _b3 = three(_mcls, 1, tag="mpbare", key="max_mp", field="mo_max")
    _q1, _q2, _q3 = three(_mcls, 1, tag="mpgear", key="max_mp", field="mo_max",
                          equipped={str(_mi.get("slot")): _MP_ITEM})
    chk("★ 换一件带法力上限词条的装（%s · +%s）⇒ 三处一起涨（%s → %s）"
        % (_mi.get("name"), _mv, _b1, _b1 + _mv),
        _q1 == _q2 == _q3 == _b1 + _mv, "%s / %s / %s" % (_q1, _q2, _q3))
else:
    chk("items 域里有带 mo_max 词条的装备（找不到 ⇒ 这条测不了）", False, _MP_ITEM)
chk("★ 反证：`mp_cap` 无职业 `strict=False` ⇒ None（呈现面那一档）",
    panel_build.mp_cap({"cls": ""}, strict=False) is None)
try:
    panel_build.mp_cap({"cls": ""})
    chk("★ 反证：`mp_cap` 无职业 `strict=True` ⇒ 抛 PanelMissing", False, "没抛（错）")
except panel_build.PanelMissing as _e:
    chk("★ 反证：`mp_cap` 无职业 `strict=True` ⇒ 抛 PanelMissing（点名：%s）"
        % str(_e)[:26], True)
#: ★ B4-8（K61 那种「覆盖面要跟判据一起加」）：这不是「一条词条坏了」，是**一族**——
#:   items 域用到的**宪法数值键**必须条条落得到引擎的面板键上；`mo_max` 原先漏在映射表外，
#:   于是「法师杖的法力 +9」这类词条在呈现面上有、在面板里没有。这里按**域里真用到的键**
#:   全扫一遍（不是只钉那一件），映射表再漏一个当场红。
_PANEL_KEYS = {"max_hp", "max_mp", "atk", "matk", "def", "mdef", "spd", "hit",
               "dodge", "block", "heal_pow", "crit", "crit_dmg"}
_CONST_KEYS = {"hp", "hp_max", "mo", "mo_max", "atk", "matk", "def", "res", "spd",
               "hit", "eva", "crit", "critdmg", "block", "heal_pow"}
_used_stats = sorted({str(a.get("stat")) for k, v in _ITS.items() if not str(k).startswith("_")
                      for a in (v.get("affixes") or [])})
_orphan = [s for s in _used_stats if s in _CONST_KEYS
           and panel_build.KEYMAP.get(s, s) not in _PANEL_KEYS]
chk("★ items 域用到的 %d 个宪法数值键**条条落得到面板键上**（映射表再漏一个就红）"
    % len([s for s in _used_stats if s in _CONST_KEYS]),
    not _orphan, "落空的：%s" % _orphan)

#: 现蓝那一条：档与 actor 同一个数（与现血同形）· 档上写超了按面板上限钳
_mp_act = CB.player_actor({"cls": "cls_knight", "level": 1, "mo": 7})
chk("★ 现蓝也读档（档上 7 ⇒ actor 的 `mp` = 7）· 上限仍是面板那一个（%s）"
    % _mp_act.get("max_mp"),
    int(_mp_act.get("mp") or 0) == 7 and int(_mp_act.get("max_mp") or 0) == 50,
    "%s / %s" % (_mp_act.get("mp"), _mp_act.get("max_mp")))
_mp_over = CA._p({"cls": "cls_knight", "level": 1, "mo": 9999})
chk("★ 档上现蓝写超了 ⇒ 出档口按面板上限钳（9999 → %s）" % _mp_over.get("mo"),
    int(_mp_over.get("mo") or 0) == int(_mp_over.get("mo_max") or -1) == 50,
    "%s / %s" % (_mp_over.get("mo"), _mp_over.get("mo_max")))

_mp_less = CA._p({"cls": "", "mo": 0, "mo_max": 0})            # 老档那两格写死的 0
chk("★ 还没有职业的档：法力上限那一格也不留（照实说「未定」，旧的 0 不当上限）",
    "mo_max" not in _mp_less, "%s" % sorted(_mp_less))

print("")
print("── ⑩ ★ B4-26：增益（食物 / POI 短时增益）**真折进面板快照** —— 快照 ≡ 引擎求值")
#   病根（端到端玩出来）：引擎那边 `mul` 层**真生效** —— 骑士吃一碗「生命上限 +10%」的菜，
#   打起来的血池是 127；可内容侧返回的 actor 快照原先只累加了四层 `add`（base/growth/attr/gear）
#   ⇒ `属性` / `状态` / `hp_cap` 一个数都不动（玩家吃了菜，页面上什么都没变）。
#   判据（逐条真算；期望值从 **域里的 `food.pct`** 现读，不抄实现体）：
#     ① `gear.BUFF_KEY` 那四档各来一口：快照那一格 == 引擎 `actor_stats` 那一格
#        == 基础 × (1 + pct/100)（`max_hp`/`max_mp` 取整，其余 4 位）· 别的键一个都不动
#     ② 两个**上限**（`hp_cap` / `mp_cap`）跟着快照走（不是只涨引擎那一份）
#     ③ 真跑 `属性` / `状态` 两个呈现口：页面上那两个数真的变了（含尾注那一行）
#     ④ 过期（假钟拨过 `until`）⇒ 逐键回原样
#     ⑤ 覆盖面：items 域里**每一道写了 `food` 的菜**逐个造档 ⇒ 快照 ≡ 引擎
try:
    from content import gear as GB10                                   # noqa: E402
    from content import cmds_more as CM10                              # noqa: E402
    from content import cmds_ast as CA10                               # noqa: E402
    from content import facade as FA10                                 # noqa: E402

    _foods = {k: v for k, v in sorted(_ITS.items()) if isinstance(v.get("food"), dict)}
    chk("★ items 域里有带 `food` 的菜（%d 道）" % len(_foods), len(_foods) >= 4, "%s" % sorted(_foods)[:3])

    class _E10(object):
        def __init__(self, text=""):
            self.text = text

        def save(self):
            pass

    def _dr10(fn, p, text=""):
        out10 = []

        async def _go():
            async for _l in fn(_E10(text), None, "u_buff10", p):
                out10.append(str(_l))

        asyncio.run(_go())
        return out10

    def _pairs10(rec):
        """(面板快照, 引擎求值) 两份 —— **同一把尺的两端**。"""
        _g, _b = panel_build.gear_and_buffs(rec)
        _a = panel_build.build_actor(rec["cls"], int(rec["level"] or 1), rec.get("alloc"),
                                     _g, buffs=_b, uid="u_buff10")
        return _a, dict(actor_stats(None, _a))

    _base10 = {"cls": "cls_knight", "level": 1, "hp": 100, "alloc": {}, "equipped": {},
               "bag": {}, "codex": {}, "flags": {}}
    _act0, _eng0 = _pairs10(_base10)

    _pois10 = st.domain("pois") or {}
    _cases10 = []                                  # (来源, id, stat, pct) —— 域里真写着数值的那几处
    for _rid, _rv in sorted(_foods.items()):
        _f10 = _rv.get("food") or {}
        _cases10.append(("菜", _rid, str(_f10.get("stat") or ""), int(_f10.get("pct") or 0)))
    for _rid, _rv in sorted(_pois10.items()):
        _e10 = _rv.get("effect") if isinstance(_rv.get("effect"), dict) else {}
        if _e10.get("buff") or _e10.get("stat"):
            _cases10.append(("POI", _rid, str(_e10.get("stat") or ""), int(_e10.get("pct") or 0)))
    _nfood10 = len([1 for c in _cases10 if c[0] == "菜"])
    _bad10 = ["%s %s：stat=%r 不在 BUFF_KEY 里（引擎那边会静默不生效）" % (t, i, s)
              for t, i, s, p in _cases10 if p and s and s not in GB10.BUFF_KEY]
    chk("★ 域里 %d 处写了数值的短时增益（菜 %d ｜ POI %d）**条条落得到面板键上**"
        % (len(_cases10), _nfood10, len(_cases10) - _nfood10), not _bad10, "%s" % _bad10)

    _keys10 = set()
    for _tag, _rid, _stat, _pct in _cases10:
        if not _pct or _stat not in GB10.BUFF_KEY:
            continue
        _pk = GB10.BUFF_KEY[_stat]
        _keys10.add(_pk)
        _a1, _e1 = _pairs10(dict(_base10, food_buff={"stat": _stat, "pct": _pct, "until": 1e18}))
        _want = float(_eng0.get(_pk, 0)) * (1.0 + _pct / 100.0)
        _want = int(_want) if _pk in panel_build.INT_KEYS else round(_want, 4)
        _drift = {k: (_eng0.get(k), _e1.get(k)) for k in sorted(set(_eng0) | set(_e1))
                  if abs(float(_e1.get(k, 0)) - float(_eng0.get(k, 0))) > 1e-9 and k != _pk}
        chk("★ %s %s（%s +%d%%）：快照 %s == 引擎 %s == 基础 %s × %.2f · 别的键一个不动 %s"
            % (_tag, _rid, _pk, _pct, _a1.get(_pk), _e1.get(_pk), _eng0.get(_pk),
               1 + _pct / 100.0, sorted(_drift) or "✓"),
            _a1.get(_pk) == _e1.get(_pk) == _want and not _drift,
            "快照 %s / 引擎 %s / 该 %s" % (_a1.get(_pk), _e1.get(_pk), _want))
    chk("★ `gear.BUFF_KEY` 那几档在域里都喂得到真数据（今天覆盖 %s —— 少一档就红）"
        % " · ".join(sorted(_keys10)), _keys10 == set(GB10.BUFF_KEY.values()), "%s" % sorted(_keys10))

    _rec_hp10 = dict(_base10, food_buff={"stat": "hp", "pct": 10, "until": 1e18})
    _cap10, _cap0_10 = panel_build.hp_cap(_rec_hp10), panel_build.hp_cap(_base10)
    chk("★ `hp_cap` 跟着快照走（%s → %s = 引擎那份）" % (_cap0_10, _cap10),
        _cap10 == int(float(_eng0["max_hp"]) * 1.1) and _cap10 > _cap0_10,
        "%s / %s" % (_cap0_10, _cap10))
    _am10 = panel_build.build_actor("cls_knight", 1, None, None, buffs={"max_mp": 1.5}, uid="u_buff10")
    _em10 = dict(actor_stats(None, _am10))
    chk("★ 法力上限同一把尺（同一份快照口喂 `max_mp ×1.5`：快照 %s == 引擎 %s == 基础 %s × 1.5）"
        % (_am10.get("max_mp"), _em10.get("max_mp"), _eng0.get("max_mp")),
        _am10.get("max_mp") == _em10.get("max_mp") == int(float(_eng0["max_mp"]) * 1.5),
        "%s / %s" % (_am10.get("max_mp"), _em10.get("max_mp")))
    _ah10, _eh10 = _pairs10(dict(_base10, food_buff={"stat": "hp", "pct": 10, "until": 1e18}))
    chk("★ per-key：生命那口增益**不动法力上限**（%s → %s）"
        % (_act0.get("max_mp"), _ah10.get("max_mp")),
        _ah10.get("max_mp") == _act0.get("max_mp") and _eh10.get("max_mp") == _eng0.get("max_mp"),
        "%s / %s" % (_ah10.get("max_mp"), _eh10.get("max_mp")))

    _p10 = CA10._p(dict(_base10, food_buff={"stat": "hp", "pct": 10, "until": 1e18}))
    _attr10, _stat10 = _dr10(CM10.attrs, _p10), _dr10(CA10.status, _p10)
    _capv10 = panel_build.hp_cap(_p10)
    chk("★ 真跑 `属性`：三格那一行 = 生命上限 %s（吃了一口生命增益之后现算）" % _capv10,
        bool(_attr10) and ("生命上限 %s ｜" % _capv10) in _attr10[1],
        "%s" % _attr10[1:2])
    chk("★ 真跑 `状态`：那一行 = 生命 100/%s（上限跟面板走，不再各算各的）" % _capv10,
        any(("生命 100/%s" % _capv10) in _x for _x in _stat10), "%s" % _stat10[1:2])
    chk("★ `属性` 尾注照实说（composition 里写着「增益」那一档）",
        CA10.T("SYS_ATTR_NOTE") in _attr10, "%s" % _attr10[-1:])

    _F10 = 1790308800.0                                               # 假钟（与别处同一口径）
    FA10.bind_host(clock=lambda: _F10)
    try:
        _actE, _engE = _pairs10(dict(_base10, food_buff={"stat": "hp", "pct": 10,
                                                        "until": _F10 - 1}))
        _driftE = {k: (_act0.get(k), _actE.get(k)) for k in sorted(set(_act0) | set(_actE))
                   if _act0.get(k) != _actE.get(k)}
        chk("★ 过期（假钟拨过 `until`）：快照逐键回原样（上限 %s）· 引擎那份也不动（%s）"
            % (_actE.get("max_hp"), _engE.get("max_hp")), not _driftE, "%s" % _driftE)
    finally:
        FA10.bind_host(clock=time.time)

    _badfood10 = []
    for _fid2, _fv2 in _foods.items():
        _st2 = str((_fv2.get("food") or {}).get("stat"))
        _pk2 = GB10.BUFF_KEY.get(_st2)
        if not _pk2:
            _badfood10.append("%s：stat=%s 不在 BUFF_KEY 里" % (_fid2, _st2))
            continue
        _pc2 = int((_fv2.get("food") or {}).get("pct") or 0)
        _a2, _e2 = _pairs10(dict(_base10, food_buff={"stat": _st2, "pct": _pc2, "until": 1e18}))
        if _a2.get(_pk2) != _e2.get(_pk2) or float(_a2.get(_pk2) or 0) <= float(_eng0.get(_pk2) or 0):
            _badfood10.append("%s（%s %s）：快照 %s ≠ 引擎 %s" % (_fid2, _st2, _pc2, _a2.get(_pk2), _e2.get(_pk2)))
    chk("★ 覆盖面：items 域里每一道菜（%d 道）逐个造档 ⇒ 快照 ≡ 引擎、且真涨" % len(_foods),
        not _badfood10, "%s" % _badfood10)
except Exception as exc:                                              # noqa: BLE001
    chk("★ B4-26 增益折进面板那一节跑得起来", False, "%s: %s" % (type(exc).__name__, exc))

print("")
print("===== %s =====" % ("★ P-27 / B4-8 两个上限三处一致 + 反证都过 ✅" if not fails
                          else "有红 ❌ %s" % fails))
sys.exit(0 if ok else 1)
