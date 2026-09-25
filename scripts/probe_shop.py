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
  ② 那一站从域里现取：`funcs` 带 `herb` 的人只有一位 ⇒ 他所在的节点既是药铺那一站、
     也是 maps 里真有的一站（站名从 maps 来）
  ③ 货架 = items 域里 `kind_key == tool` 且**有价**的那些（现算集合）· 每件价 = 基础价 × 品阶系数
     （没写 `quality` 按默认档）· 逐件对账 · 买价 ≥ 收价
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
     「基础价 × 品阶系数」那条算法也只许在它那里 · 代码里不许出现货架 id
  ⑬ 覆盖面：两条 handler 都**真调** `town_gate`（与 `probe_cmds ⑰` 同一套口径）

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
    for g in got:
        q = str(g["rec"].get("quality") or rules.get("quality_default"))
        exp = int(round(float(g["rec"]["price"]) * float(rules["quality_mult"][q])))
        if g["gold"] != exp or g["gold"] < int(g["rec"]["price"]):
            wrong.append((g["id"], g["gold"], exp))
    if got and not wrong:
        ok("每件价 = 基础价 × 品阶系数（取整），且买价 ≥ 收价")
    else:
        bad("价对不上：%s" % wrong)

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

    # ── ⑫ 静态守卫（价与货架只许在一处算 · 代码里不许写死货架 id）
    algo, literals, readers = [], [], []
    for fn in sorted(os.listdir(os.path.join(REPO, "content"))):
        if not fn.endswith(".py"):
            continue
        src = io.open(os.path.join(REPO, "content", fn), encoding="utf-8").read()
        if "quality_mult" in src and fn != "shop.py":
            algo.append(fn)
        if re.search("i_potion", src):
            literals.append(fn)
        if "shop.json" in src:
            readers.append(fn)
    if not algo:
        ok("静态：品阶系数（`quality_mult`）只在 content/shop.py 被读 —— 别处不算第二遍价")
    else:
        bad("这几个文件也在算品阶系数：%s" % algo)
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
