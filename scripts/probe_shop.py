# -*- coding: utf-8 -*-
"""探针：药铺 · 购买（B4-15）—— 第 39 支。

为什么有这条线（端到端玩出来的真缺口）
------------------------------------
`00_第一阶段内容总纲 §七` 写着「钱到哪去 ＝ 药水 · 修理 · 强化 · 住店」，
`03 §一` 写着 `药铺`（在镇上 · 买药），`04 §物品` 写着 `购买 <物品>`（别名 买 · 守卫 在铺子且钱够）——
可这一版里两条声明**都没有处理器**，而 `i_potion_heal`（药水 · `effect.hp_pct = 0.3`）
在掉落池 / 采集点 / 配方里**一处都没有** ⇒ 玩家能卖不能买、钱只进不出，药水一件都拿不到。

判据（一条都不许松）
  ① 口径表 `content/rules/shop.json` 的四个系数 == 真源 `00_…内容总纲_v1.md §六` 现解析值（逐字）
     · ★ P-55：**固定加价那一格**（`buy_markup`）必须在且是 ≥1 的数（缺格 / 烂值当场红 ——
       没有它买价就退回等于收价，「低买高卖」那条路又开了）
  ② 那一站从域里现取：`funcs` 带 `herb` 的人只有一位 ⇒ 他所在的节点既是药铺那一站、
     也是 maps 里真有的一站（站名从 maps 来）
  ③ 货架 = items 域里 `kind_key == tool` 且**有价**的那些（现算集合）· 每件价 = 基础价 × 品阶系数
     × 固定加价（没写 `quality` 按默认档）· 逐件对账 · ★ **买价 > 收价**（P-55：不许有
     「卖回去再买回来」不亏的路）
  ④ 真宿主三档真敲：野外 ⇒ 只回「这几处都在镇上」；镇上没走到那一站 ⇒ 指路（站名从 maps 现取）；
     站到了 ⇒ 面板四段逐行对账（抬头 / 人在 / 每件一行 / 钱袋那一行）
  ⑤ 面板是**只读**的：敲『药铺』前后档逐字相同
  ⑥ 真敲 `购买 <东西>`：钱按**现算价**减、背包 +1（回话与档上副作用都核）
  ⑦ 数量形态：`购买 <东西> 3` ⇒ 一次三件（钱按 3 倍）
  ⑧ 钱不够 ⇒ 只回一句 `SYS_SHOP_POOR`（差额现算）且**档一个字不动**
  ⑨ 柜上没有的（材料 / 装备）⇒ `SYS_SHOP_NOGOOD` 且档一字不动
  ⑩ 没带参（裸 `购买` / `买`）⇒ `SYS_SHOP_ASK` 且档一字不动（K71 第 2 条）
  ⑪ 连写取参（K71）：`购买药水` == `购买 药水`（回话与档上副作用逐字相同）
  ⑫ 静态守卫：全 `content/*.py` 里读铺子口径表的只有 `content/shop.py` 一处 ·
     「基础价 × 品阶系数 × 固定加价」那条算法也只许在它那里 · 代码里不许出现货架 id
  ⑬ 覆盖面：两条 handler 都**真调** `town_gate`（与 `probe_cmds ⑰` 同一套口径）
  ⑭ ★ 撤改验证（跑之前手工核过一遍 · 写在这儿给下一轮）：`buy_markup` 改回 1 ⇒ ① 与 ③
     当场红（买价 == 收价）；摘掉 `item_buy` 的 bind ⇒ ⑥⑦ 红
  ⑮ ★ P-16：**物价倍数**（世界事件效果栏 `price_mul`）真接在买价上 —— 注入一条假事件 ⇒
     面板那一行与『购买』扣的钱**同一眼同一个价**（都 ×1.25）、收价一个字不动；拿掉 ⇒ 回原价
  ⑯ ★ P-70（2026-09-26 · 本波 w-h-ux · **裁决：修理「本轮不做」**）：四个消耗口逐口取证
     （药水 / 强化 / 住店 ✅ · 修理 ❌）·「不做」的机器可见理由 = items 域零耐久字段 ·
     声明里不许再拿「修装备」当卖点 · 真源 `05 §七` 那一行跟账登记
  ⑰ ★ P-71（同一波 · **裁决：住店那一句复用现成槽位，不新开**）：真敲那一行逐字 ==
     `SYS_SHOP_POOR` 渲染 · texts 里没有住店专用的欠钱槽位 · 静态只有一处读它 · 两态真调

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_shop.py
"""
from __future__ import annotations

import ast
import io
import json
import os
import re
import sys

ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.environ.get("AST_PLAN", "C:/Users/yuyu/aetheran-plan")
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack            # noqa: E402
from saintess_engine.host.runtime import Host             # noqa: E402

NL = chr(10)
TOWN = "windmill_town"
OK, BAD = [], []
FIXED = 1790308800          # 2026-09-25 12:00 +08:00（昼 —— 与 probe_cmds 同一根假钟）
UID = "u_shop_probe"


def ok(msg):
    OK.append(msg)
    print("  OK  %s" % msg)


def bad(msg):
    BAD.append(msg)
    print("  X   %s" % msg)


class Ad(object):
    """最小适配器（照 scripts/e2e_drive.py 的真宿主契约）。"""

    def __init__(self, seed=None):
        self.out = []
        self.saved = {UID: dict(seed)} if seed else {}

    def recv(self):
        return None

    def load_player(self, uid):
        return self.saved.get(uid)

    def save_player(self, uid, data):
        self.saved[uid] = dict(data) if isinstance(data, dict) else data

    def say(self, to, text):
        self.out.append(str(text))


def drive(ad, host, text, uid=UID):
    ad.out = []
    host.handle({"uid": uid, "group_id": "g_shop_probe", "text": text})
    return list(ad.out)


def _load(rel):
    with io.open(os.path.join(REPO, rel), encoding="utf-8") as f:
        return json.load(f)


def main():
    items = _load("content/data/items.json")
    npcs = _load("content/data/npcs.json")
    maps = _load("content/data/maps.json")
    texts = _load("content/data/texts.json")
    rules = _load("content/rules/shop.json")

    def T(key, **slots):
        s = texts[key]["value"]
        for k, v in slots.items():
            s = s.replace("{%s}" % k, str(v))
        return s

    def snap():
        return (ad.saved[UID].get("gold"), dict(ad.saved[UID].get("bag") or {}))

    # ── ① 口径表 == 真源（探针自己解析真源文档，不写死）
    doc = io.open(os.path.join(PLAN, "06_第一阶段垂直切片",
                               "00_第一阶段内容总纲_v1.md"), encoding="utf-8").read()
    hit = re.search(r"品阶四档：\s*普通\s*([0-9.]+)\s*/\s*精制\s*([0-9.]+)"
                    r"\s*/\s*稀有\s*([0-9.]+)\s*/\s*遗物\s*([0-9.]+)", doc)
    want = dict(zip(("普通", "精制", "稀有", "遗物"),
                    [float(x) for x in hit.groups()])) if hit else None
    if want and rules.get("quality_mult") == want:
        ok("口径表四个系数 == 真源 00_总纲 §六 现解析值：%s" % want)
    else:
        bad("口径表与真源对不上：表 %r / 真源 %r" % (rules.get("quality_mult"), want))

    # ── ①之二 ★ P-55：固定加价那一格（真源没给数 ⇒ 表是唯一真源，缺格当场红）
    mk = rules.get("buy_markup")
    if isinstance(mk, bool) or not isinstance(mk, (int, float)) or mk < 1:
        bad("口径表缺「固定加价」那一格或不是 ≥1 的数：%r（买价会退回等于收价 —— P-55 那毛病）" % (mk,))
    else:
        ok("★ 固定加价那一格（P-55）：买价 = 收价 × 品阶系数 × %s（普通档 = 「收价 × %s」）" % (mk, mk))

    # ── ② 那一站从域里现取
    func = rules.get("station_func")
    spots = {}
    for k, v in npcs.items():
        if isinstance(v, dict) and func in (v.get("funcs") or []):
            spots.setdefault(str(v.get("subarea") or ""), []).append(k)
    node, nname = "", ""
    if len(spots) == 1:
        node = next(iter(spots))
        hitn = [n.get("name") for n in maps[TOWN]["nodes"] if n.get("id") == node]
        nname = hitn[0] if hitn else ""
    if node and nname:
        ok("那一站从域里现取：%s（%s —— %s 在这站）" % (node, nname, spots[node][0]))
    else:
        bad("那一站叫不准（%s）：守卫没法 fail-closed" % sorted(spots))

    st = load_stack(str(REPO), inject={"db_path": ":memory:", "clock": lambda: FIXED})
    del st
    from content import shop as SH                                    # noqa: E402

    if SH.station() == node and SH.station_name() == nname:
        ok("`shop.station()` / `station_name()` 与域里那两处一致")
    else:
        bad("shop 那两个口给的是 %r / %r（期望 %r / %r）"
            % (SH.station(), SH.station_name(), node, nname))

    # ── ③ 货架（现算集合 + 逐件价）
    want_ids = [i for i, r in items.items()
                if isinstance(r, dict) and r.get("kind_key") == rules.get("stock_kind")
                and r.get("price")]
    got = SH.goods()
    got_ids = [g["id"] for g in got]
    if got_ids and got_ids == want_ids:
        ok("货架 == items 域里 `kind_key == %r` 且有价的那些（%d 件：%s）"
           % (rules.get("stock_kind"), len(got_ids), " · ".join(got_ids)))
    else:
        bad("货架对不上：探针 %s / 域里 %s" % (got_ids, want_ids))
    wrong = []
    flat = []
    for g in got:
        q = str(g["rec"].get("quality") or rules.get("quality_default"))
        exp = int(round(float(g["rec"]["price"]) * float(rules["quality_mult"][q]) * float(mk)))
        if g["gold"] != exp:
            wrong.append((g["id"], g["gold"], exp))
        if g["gold"] <= int(g["rec"]["price"]):          # ★ P-55：收价能原价买回来 = 开了刷钱的路
            flat.append((g["id"], g["gold"], int(g["rec"]["price"])))
    if got and not wrong:
        ok("每件价 = 收价 × 品阶系数 × 加价（取整）—— 逐件对账 %d 件" % len(got))
    else:
        bad("价对不上：%s" % wrong)
    if got and not flat:
        ok("★ 每件都是**买比卖贵**（买价 > 收价 —— P-55 要堵的那条路今天不存在）")
    else:
        bad("这几件买价 ≤ 收价（原价买得回来 ⇒ 能刷钱）：%s" % flat)

    # ── ④ 真宿主三档（野外 / 镇上错站 / 站到了）
    db = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_shop.db")
    try:
        os.remove(db)
    except OSError:
        pass
    seed = {"cls": "cls_knight", "race": "race_human", "name": "试药者", "level": 3, "exp": 0,
            "gold": 100, "prev": [], "bag": {}, "equipped": {}, "codex": {}, "flags": {}}
    ad = Ad(seed)
    host = Host(ad, REPO, inject={"db_path": db, "clock": lambda: FIXED})
    host.boot()
    g0 = got[0]
    gname = str(g0["rec"]["name"])

    def stand(loc, node_):
        ad.saved[UID]["loc"] = loc
        ad.saved[UID]["node"] = node_

    stand("belt_north", "bn_bone")
    for txt in ("药铺", "购买 " + gname):
        ad.saved[UID]["gold"] = 100
        ad.saved[UID]["bag"] = {}
        lines = drive(ad, host, txt)
        if lines == [T("SYS_PLACE_NOTOWN")] and snap() == (100, {}):
            ok("野外敲『%s』⇒ 只回「这几处都在镇上」且不动档" % txt)
        else:
            bad("野外敲『%s』回的是：%s · 档 %r" % (txt, lines[:2], snap()))

    stand(TOWN, "wt_gate_n")
    ad.saved[UID]["gold"] = 100
    ad.saved[UID]["bag"] = {}
    lines = drive(ad, host, "购买 " + gname)
    if lines == [T("SYS_SHOP_AWAY", name=nname)] and snap() == (100, {}):
        ok("镇上没走到那一站 ⇒ 指路（站名从 maps 现取：%s）且不动档" % nname)
    else:
        bad("错站那一下回的是：%s · 档 %r" % (lines[:2], snap()))

    stand(TOWN, node)
    ad.saved[UID]["gold"] = 100
    ad.saved[UID]["bag"] = {}
    roster = [v for v in npcs.values()
              if isinstance(v, dict) and v.get("map") == TOWN and v.get("subarea") == node]
    exp_panel = [T("SYS_SHOP_HEAD", name=nname),
                 T("SYS_LOOK_WHO", list=" · ".join("『%s』%s" % (v.get("name"), v.get("icon", ""))
                                                   for v in roster))]
    exp_panel += [T("SYS_SHOP_ROW", icon=g["rec"].get("icon") or "",
                    name=g["rec"].get("name") or g["id"], gold=g["gold"]) for g in got]
    exp_panel += [T("SYS_SHOP_TAIL", gold=100)]
    before = json.dumps(ad.saved[UID], ensure_ascii=False, sort_keys=True)
    lines = drive(ad, host, "药铺")
    if lines == exp_panel:
        ok("站到了『药铺』⇒ 面板逐行对账过（%d 行：抬头 / 人在 / %d 件货 / 钱袋）"
           % (len(lines), len(got)))
    else:
        diff = [(i, a, b) for i, (a, b) in enumerate(zip(lines, exp_panel)) if a != b]
        bad("面板对不上：len %d vs %d · %s" % (len(lines), len(exp_panel), diff[:2]))
    if json.dumps(ad.saved[UID], ensure_ascii=False, sort_keys=True) == before:
        ok("面板是**只读**的（敲『药铺』前后档逐字相同）")
    else:
        bad("敲『药铺』动了档")

    # ── ⑥ 真买一件
    ad.saved[UID]["gold"] = 100
    ad.saved[UID]["bag"] = {}
    lines = drive(ad, host, "购买 " + gname)
    exp = [T("SYS_SHOP_BUY_OK", icon=g0["rec"].get("icon") or "", name=gname,
             n=1, gold=g0["gold"], left=100 - g0["gold"])]
    if lines == exp and snap() == (100 - g0["gold"], {g0["id"]: 1}):
        ok("真买一件（%s）：钱 100 → %d · 背包 %s ×1（回话与档都对）"
           % (gname, 100 - g0["gold"], g0["id"]))
    else:
        bad("买一件不对：回话 %s · 档 %r" % (lines[:2], snap()))

    # ── ⑦ 数量形态
    ad.saved[UID]["gold"] = 100
    ad.saved[UID]["bag"] = {}
    lines = drive(ad, host, "购买 %s 3" % gname)
    exp = [T("SYS_SHOP_BUY_OK", icon=g0["rec"].get("icon") or "", name=gname,
             n=3, gold=g0["gold"] * 3, left=100 - g0["gold"] * 3)]
    if lines == exp and snap() == (100 - g0["gold"] * 3, {g0["id"]: 3}):
        ok("数量形态『购买 %s 3』⇒ 一次三件（钱按 3 倍）" % gname)
    else:
        bad("三件那一下不对：%s · 档 %r" % (lines[:2], snap()))

    # ── ⑧ 钱不够
    ad.saved[UID]["gold"] = max(0, g0["gold"] - 1)
    ad.saved[UID]["bag"] = {}
    b4 = snap()
    lines = drive(ad, host, "购买 " + gname)
    if lines == [T("SYS_SHOP_POOR", lack=1)] and snap() == b4:
        ok("钱不够 ⇒ 只回「铜板不够 —— 还差 1 个。」且**档一个字不动**")
    else:
        bad("钱不够那一下：%s · 档 %r" % (lines[:2], snap()))

    # ── ⑨ 柜上没有（拿域里有价、但不在货架上的那件来试）
    off = [i for i, r in items.items()
           if isinstance(r, dict) and r.get("price") and not str(i).startswith("_")
           and r.get("kind_key") != rules.get("stock_kind")]
    ad.saved[UID]["gold"] = 999
    b4 = snap()
    if off:
        offname = str(items[off[0]].get("name") or off[0])
        lines = drive(ad, host, "购买 " + offname)
        if lines == [T("SYS_SHOP_NOGOOD", name=offname)] and snap() == b4:
            ok("柜上没有的（%s）⇒ 一句实话 + 档一字不动" % offname)
        else:
            bad("柜上没有那条不对：%s · 档 %r" % (lines[:2], snap()))
    else:
        bad("域里找不出一件「有价但不在货架」的东西 —— 这条判据没跑")

    # ── ⑩ 没带参
    for txt in ("购买", "买"):
        ad.saved[UID]["gold"] = 999
        b4 = snap()
        lines = drive(ad, host, txt)
        if lines == [T("SYS_SHOP_ASK")] and snap() == b4:
            ok("裸『%s』⇒ 回 ASK 且档一字不动" % txt)
        else:
            bad("裸『%s』回的是：%s · 档 %r" % (txt, lines[:2], snap()))

    # ── ⑪ 连写取参（K71：参跟声明自己的 patterns 走）
    ad.saved[UID]["gold"] = 100
    ad.saved[UID]["bag"] = {}
    a_lines = drive(ad, host, "购买" + gname)
    a_state = snap()
    ad.saved[UID]["gold"] = 100
    ad.saved[UID]["bag"] = {}
    b_lines = drive(ad, host, "购买 " + gname)
    b_state = snap()
    if a_lines == b_lines and a_state == b_state and a_state == (100 - g0["gold"], {g0["id"]: 1}):
        ok("连写『购买%s』== 『购买 %s』（回话与档上副作用逐字相同）" % (gname, gname))
    else:
        bad("连写取参不一致：%s / %s · %r / %r" % (a_lines[:1], b_lines[:1], a_state, b_state))

    # ── ⑮ ★ P-16：物价倍数接在买价上（注入一条带 `price_mul` 的假事件 —— 与 probe_events ⑪ 同一个手法）
    from content import calendar as CALP                              # noqa: E402
    _PM = 1.25
    _rawP = CALP._d("events")                     # ★ 缓存里那张表本体（注入要动它）
    _shelfA = [(g["id"], g["gold"]) for g in SH.goods(ad.saved[UID])]
    _rawP["ev_probe_price_shop"] = {"no": 98, "name": "probe", "scale": "每日", "scale_key": "daily",
                                    "period": {"daily": True}, "text": "SYS_EV_NONE", "where": [],
                                    "effects": {"price_mul": _PM}}
    try:
        _shelfB = [(g["id"], g["gold"]) for g in SH.goods(ad.saved[UID])]
        ad.saved[UID]["gold"] = 999
        ad.saved[UID]["bag"] = {}
        _panelB = drive(ad, host, "药铺")
        ad.saved[UID]["gold"] = 999
        ad.saved[UID]["bag"] = {}
        _buyB = drive(ad, host, "购买 " + gname)
        _buyB_state = snap()
    finally:
        _rawP.pop("ev_probe_price_shop", None)
    _shelfC = [(g["id"], g["gold"]) for g in SH.goods(ad.saved[UID])]
    _paidB = 999 - int(_buyB_state[0] or 0)
    _wantB = [(i, int(round(v * _PM))) for i, v in _shelfA]
    _upB = int(round(g0["gold"] * _PM))
    _rowB = T("SYS_SHOP_ROW", icon=g0["rec"].get("icon") or "", name=gname,
              gold=_upB)
    _wantBuyB = [T("SYS_SHOP_BUY_OK", icon=g0["rec"].get("icon") or "", name=gname,
                   n=1, gold=_upB, left=999 - _upB)]
    _price_now = [int(g["rec"]["price"]) for g in SH.goods(ad.saved[UID])]
    _price0 = [int(x["rec"]["price"]) for x in got]
    if (_shelfB == _wantB and _shelfC == _shelfA and _rowB in _panelB and _buyB == _wantBuyB
            and _buyB_state == (999 - _upB, {g0["id"]: 1}) and _price_now == _price0):
        ok("★ 物价倍数真接在买价上（P-16 · 注入 `price_mul` = %s）：判定口给 %s ⇒ 每件买价 ×%s"
           "（%s → %s）· 面板那一行与『购买』扣的钱是**同一眼同一个价**（那一下扣 %d）· "
           "拿掉 ⇒ 回原价 · **收价一个字不动**（%s）"
           % (_PM, _PM, _PM, [v for _i, v in _shelfA], [v for _i, v in _shelfB],
              _paidB, _price_now))
    else:
        bad("物价倍数那条对不上：A %s · B %s · C %s · 面板有那行=%s · 那一下 %s · 收价 %s/%s"
            % (_shelfA, _shelfB, _shelfC, _rowB in _panelB, _buyB[:1], _price_now, _price0))

    # ── ⑫ 静态守卫（价与货架只许在一处算 · 代码里不许写死货架 id）
    algo, literals, readers, marks = [], [], [], []
    for fn in sorted(os.listdir(os.path.join(REPO, "content"))):
        if not fn.endswith(".py"):
            continue
        src = io.open(os.path.join(REPO, "content", fn), encoding="utf-8").read()
        if "quality_mult" in src and fn != "shop.py":
            algo.append(fn)
        if "buy_markup" in src and fn != "shop.py":
            marks.append(fn)
        if re.search("i_potion", src):
            literals.append(fn)
        if "shop.json" in src:
            readers.append(fn)
    if not algo:
        ok("静态：品阶系数（`quality_mult`）只在 content/shop.py 被读 —— 别处不算第二遍价")
    else:
        bad("这几个文件也在算品阶系数：%s" % algo)
    if not marks:
        ok("静态：固定加价（`buy_markup`）也只在 content/shop.py 被读（第二遍价 = 第二个源）")
    else:
        bad("这几个文件也在读加价那一格：%s" % marks)
    if not literals:
        ok("静态：代码里没有货架 id 字面量（货架全从 items 域现取）")
    else:
        bad("代码里写死了货架 id：%s" % literals)
    if readers == ["shop.py"]:
        ok("静态：读铺子口径表的只有 content/shop.py 一处")
    else:
        bad("读铺子口径表的地方不止一处：%s" % readers)

    # ── ⑬ 覆盖面：两条 handler 都真调 town_gate（守卫一个口）
    decl = _load("content/data/commands.json")
    calls = {}
    for fn in sorted(os.listdir(os.path.join(REPO, "content"))):
        if not fn.endswith(".py"):
            continue
        tree = ast.parse(io.open(os.path.join(REPO, "content", fn), encoding="utf-8").read())
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if any(isinstance(x, ast.Call) and getattr(x.func, "id", "") == "town_gate"
                       for x in ast.walk(n)):
                    calls.setdefault(fn, set()).add(n.name)
    miss = []
    for key in ("item_buy", "herbalist"):
        mod, fname = str(decl[key]["bind"]["handler"]).split(":")
        if fname not in calls.get(mod.split(".")[-1] + ".py", set()):
            miss.append(key)
    if not miss:
        ok("覆盖面：`购买` / `药铺` 两条 handler 都**真调** town_gate（守卫一个口）")
    else:
        bad("这两条没走 town_gate：%s" % miss)

    # ⑯ ★ P-70（2026-09-26 · 本波 w-h-ux · **裁决：「修理」本轮不做**）
    #   真源 `05_玩法数值口径_v1.md §七` 把钱算四个去处（药水 · 修理 · 强化 · 住店），
    #   而「修理」这一口**没有任何域存它**（items 域没有耐久字段）⇒ 本路裁：**本轮不做**
    #   —— 它**不是漏做**，是**另一批**（要做先有耐久设计：耐久怎么掉 · 修理费按什么 ·
    #   修不好怎么办）。这一条判据干三件事，免得下一轮又把它当成「欠着的第四口」：
    #     ① 已落的那三个口逐口当场取证（药水 / 强化 / 住店）
    #     ② 「不做」要有**机器可见**的理由：items 域不许有耐久字段（谁加了就先红 —— 提醒回来设计）
    #     ③ 声明里不许再拿「修装备」当卖点（`smith.desc` 已回正 —— 与 P-52「声明回正」同款）
    _ITEMS16 = _load("content/data/items.json")
    _DURW16 = ("durability", "dur", "耐久", "wear", "repair", "修理", "损耗")
    _keys16 = sorted({k for v in _ITEMS16.values() if isinstance(v, dict) for k in v})
    _dur16 = sorted({k for k in _keys16 if any(w in str(k).lower() for w in _DURW16)})
    _inn16 = _load("content/rules/inn.json")
    _fee16 = _inn16.get("fee")
    _ok16 = {
        "药水": bool((decl.get("item_buy") or {}).get("bind"))
                and bool((decl.get("herbalist") or {}).get("bind")),
        "强化": bool((decl.get("enhance") or {}).get("bind"))
                and bool((decl.get("smith") or {}).get("bind")),
        "住店": bool((decl.get("inn") or {}).get("bind"))
                and isinstance(_fee16, int) and not isinstance(_fee16, bool) and _fee16 >= 1,
    }
    if all(_ok16.values()):
        ok("★ P-70 四个消耗口逐口状态：药水 ✅（购买 + 药铺两条都有 bind）· 强化 ✅（强化 + 铁匠铺）· "
           "住店 ✅（fee=%s 从 `content/rules/inn.json` 现读）· 修理 ❌ **本轮不做**" % _fee16)
    else:
        bad("★ P-70 已落的那三个口有掉链子的：%s" % _ok16)
    if not _dur16:
        ok("★ P-70 「修理本轮不做」的**机器可见理由**：items 域没有任何耐久字段"
           "（%d 条记录 · %d 个键 · 黑名单「%s」零命中）—— 真做是**新形状**（另立一批），"
           "不是本波漏做" % (len(_ITEMS16), len(_keys16), " / ".join(_DURW16)))
    else:
        bad("★ P-70 items 域里出现了耐久字段 %s —— 有人开始做修理了：先把真源 `05 §七` 那一行"
            "改成「修理」的落地口径（耐久怎么掉 · 修理费按什么），再把本探针改成真敲 `修理` 的判据"
            % _dur16)
    _repair16 = sorted(k for k, v in decl.items()
                       if any(w in (str((v or {}).get("desc") or "")
                                    + str((v or {}).get("usage") or ""))
                              for w in ("修装备", "修理")))
    if not _repair16:
        ok("★ P-70 声明里不再拿「修装备」当卖点（`smith.desc` 已回正为只写「强化」—— "
           "与 P-52「声明回正」同款：声明 ≡ 实现）")
    else:
        bad("★ P-70 声明里还写着「修装备 / 修理」：%s —— 那是本波**裁过不做**的那一口，"
            "回正成「强化」（真源 `04 §七` 那一格的跟账见本分支 `_notes.md §八`）" % _repair16)
    # 真源那一侧（登记 · 两态互锁的另一半）：`05 §七`「钱到哪去」那一行跟没跟账
    _D0516 = os.path.join(PLAN, "06_第一阶段垂直切片", "05_玩法数值口径_v1.md")
    _L16 = []
    if os.path.exists(_D0516):
        with io.open(_D0516, encoding="utf-8") as _fh16:
            _L16 = [_ln.strip() for _ln in _fh16 if "钱到哪去" in _ln]
    _ln16 = _L16[0] if _L16 else ""
    print("  · 登记（P-70）：真源 `05 §七`「钱到哪去」那一行 = %s" % (_ln16[:84] or "（没解析到）"))
    print("      %s —— 本路裁「修理：本轮不做」的真源行见本分支 `_notes.md §八`；"
          % ("**已跟账**" if "不做" in _ln16 else "**还没跟账**（今天仍把「修理」列在四个去处里）"))
    print("      真源跟账后，「修理不做」就从「待跟账的裁决」转成正式口径（本探针那两条跟着转正）。")

    # ⑰ ★ P-71（2026-09-26 · 本波 w-h-ux · **裁决：住店那一句复用现成槽位，不新开**）
    #   老账问的是「住店费（钱不够）要不要一个**专门**的槽位」。本路裁 —— **不新开**：复用
    #   `SYS_SHOP_POOR`。依据三条：
    #     ① **同一件事同一句话**：钱不够就是钱不够。差额 `{lack}` 本来就是现算的
    #        —— 住店要的「带上价钱」那半本来就有，没有一句是住店独有的。
    #     ② 多开一条槽位就多一条要跟账的真源行（17 号口径表 + texts），换来的是**零**玩家差别
    #        （两句都是「铜板不够 —— 还差 N 个。」）—— 少一处文案就少一处以后会打架的地方。
    #     ③ 同族先例：`SYS_MINE_RANK` / `SYS_REST_HEAL` / `SYS_LOOK_WHO` 那几格本来就是两处共用一个
    #        槽位（B3-16b 的登记里写的是「借现成槽位，不新增」）。
    #   判据四条（下面）：真敲那一行逐字 == 同一格 · texts 里没有住店专用的欠钱槽位 ·
    #   静态只有一处读它 · **两态**（临时改那一格的值 ⇒ 住店那句跟着变 = 真是同一格）。
    from content import cmds_ast as _CA17                                      # noqa: E402
    from content.cmds_more import STASH_NODE as _STASH17                       # noqa: E402

    _POOR17 = "SYS_SHOP_POOR"
    _inn17 = sorted(k for k in texts if str(k).startswith("SYS_INN_"))
    _poor17 = [k for k in _inn17
               if ("POOR" in str(k).upper() or "NOGOLD" in str(k).upper()
                   or "钱不够" in str((texts.get(k) or {}).get("value") or ""))]
    if not _poor17:
        ok("★ P-71 texts 域里**没有**住店专用的「钱不够」槽位（住店那几张只有 %s —— "
           "共用 `%s` 这一格）" % (" / ".join(_inn17), _POOR17))
    else:
        bad("★ P-71 texts 域里冒出了住店专用的欠钱槽位 %s —— 本路裁过「复用 `%s`，不新开」："
            "真要新开，先改 `18_铺子买卖口径_v1.md` 与 17 号口径表（并把这一条判据改成两格逐字对）"
            % (_poor17, _POOR17))
    _src17 = io.open(os.path.join(REPO, "content", "cmds_places.py"), encoding="utf-8").read()
    _n17 = _src17.count('"%s"' % _POOR17)
    if _n17 == 1:
        ok("★ P-71 静态：`content/cmds_places.py`（客栈那一支）里读的欠钱槽位**只有一处** —— "
           "`%s`（与『购买』同一格，一个字都不另写）" % _POOR17)
    else:
        bad("★ P-71 `cmds_places.py` 里 `%s` 出现 %d 次（应当恰好 1 处 —— 客栈那一支）"
            % (_POOR17, _n17))
    _fee17 = int(_fee16 or 0)
    _ad17 = Ad()
    _host17 = Host(_ad17, REPO, inject={"db_path": ":memory:", "clock": lambda: FIXED})
    _host17.boot()
    _u17 = UID + "_p71"
    _gold17 = max(0, _fee17 - 3)
    _ad17.saved[_u17] = {"race": "human", "cls": "cls_knight", "name": "试",
                         "loc": TOWN, "node": _STASH17, "prev": [], "flags": {},
                         "hp": 1, "gold": _gold17}
    _out17 = drive(_ad17, _host17, "客栈", _u17)
    _want17 = T(_POOR17, lack=_fee17 - _gold17)
    if _want17 in _out17:
        ok("★ P-71 真敲『客栈』（人在客栈那一站 + 有伤 + 钱不够）：那一行**逐字 ==** "
           "`%s` 渲染（%r）—— 住店与『购买』共用同一句话" % (_POOR17, _want17))
    else:
        bad("★ P-71 住店钱不够那一行不是 `%s`：%s" % (_POOR17, (_out17 or [])[:3]))
    if _ad17.saved[_u17].get("gold") == _gold17 and int(_ad17.saved[_u17].get("hp") or 0) == 1:
        ok("★ P-71 那一趟**档一个字不动**（fail-closed：不睡 / 不回血 / 不扣钱）")
    else:
        bad("★ P-71 欠钱那一趟动了档：%s" % {k: _ad17.saved[_u17].get(k) for k in ("gold", "hp")})
    _live17 = _CA17._texts()
    _had17 = _live17.get(_POOR17)
    _live17[_POOR17] = {"value": "[P]{lack}", "params": ["lack"], "category": "系统",
                        "desc": "（probe_shop 临时注入 —— 用完即撤）"}
    try:
        _out17b = drive(_ad17, _host17, "客栈", _u17)
        _same17 = "[P]%d" % (_fee17 - _gold17) in _out17b
    finally:
        if _had17 is None:
            _live17.pop(_POOR17, None)
        else:
            _live17[_POOR17] = _had17
    if _same17 and _want17 in drive(_ad17, _host17, "客栈", _u17):
        ok("★ P-71 两态真调：临时改掉 `%s` 那一格 ⇒ 住店那一行**跟着变**（= 真是同一格，"
           "不是碰巧同字）；撤掉注入 ⇒ 回到原句" % _POOR17)
    else:
        bad("★ P-71 两态不过：改掉那一格之后住店那句没跟着变（住店可能自己写了一句）")

    print()
    print("----")
    print("通过 %d / 失败 %d" % (len(OK), len(BAD)))
    if BAD:
        print("红：")
        for b in BAD:
            print("  -", b)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
