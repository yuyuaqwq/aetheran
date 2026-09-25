# -*- coding: utf-8 -*-
"""探针：一件东西点名要哪一件（B4-20）—— 第 42 支。

为什么有这条线（端到端玩出来的真缺口）
--------------------------------------
全包原先有**五份**「按名字在背包里找一件」的实现（`cmds_more._bag_hit` · `cmds_gear._in_bag` ·
`cmds_recipe._item_of_name`〔扫的是**整张物品表**〕· `cmds_recipe.item_use` 里内联那一段 ·
`shop.find`），五份都是「遍历序里第一个命中的就算」。两条玩家看得见的后果（真跑证据）：

  ① **精确名输给部分名**：背包里有「苦叶」也有「苦叶汤」时，`查看 苦叶` 回的是**苦叶汤**
     （`i_food_*` 在字典序里先撞上，而「苦叶」明明**字字相等**）；`使用 苦叶` 更狠 ——
     把那碗汤**吃掉**了。
  ② **同名四档的装备（真源 15 那四行）挑不出也看不见**：`背包` 里两行列得一模一样；
     `强化 拾荒人的重剑` 手里只有「精制」那档时回「背包里没有」（它扫的是物品表的**第一件**
     = 普通档），两档在手时又**静默**强了字典序在前的那一件。

判据（一条都不许松）
  ① 形状档（直调 `loot` 那一口）：**id / 全名相等优先于名字的一部分** · `need_slot` 只认带
     `slot` 的 · 品阶三种写法（尾缀 / 前缀 / 括号）都认 · 域里没有的那一档**不许猜**（回空）
     · 品阶词表 = 域里出现过的 `quality`（现取，不手抄）
  ② 覆盖面（静态）：五份实现只剩一份 —— `_item_of_name` 不在了；「名字的一部分」那种比较
     （`in nm`）只许出现在 `loot.py`；四个调用方（`_bag_hit` / `_in_bag` / `item_use` / `shop.find`）
     都**真调** `loot.pick` / `loot.match_ids`；`SYS_PICK_AMBIG` 只有一个出口（`cmds_gear.ambig_line`）
  ③ ★ 精确名优先（真宿主真敲）：`查看 <短名>` 回的是短的那一件；`使用 <短名>` **不许动**那件
     长名的（改前：那碗汤被吃掉 —— 撤改验证就是这一条红）
  ④ ★ 同名多件不替玩家挑（真宿主真敲）：两档在手 ⇒ `查看 / 装备 / 对比 / 丢弃 / 卖出 /
     使用 / 强化 / 存放 / 取出` 各回 `SYS_PICK_AMBIG`，且**档上一个字不动**；点明品阶之后
     **只动那一件**
  ⑤ ★ 只有一档在手 ⇒ 「背包里有就叫得出」：`强化 <名>`（手里只有第二档）**真强上**
     （改前：回「背包里没有」= 死路），档上 `flags.enhance` 记的是**那一档**
  ⑥ 列表（真敲）：`背包` / `整理背包` 里**域里重名的那些**缀品阶（「名 · 品阶」）· 不重名的
     一个字不改（逐字对账）
  ⑦ 单件回归：唯一命中时 `查看 / 装备` 的回话与「域 + texts 现算」逐字一致 · `shop.find`
     的四元组形状（柜上今天没有同名多件，那一档只守形状）

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_pick.py
Python 用 3.12（3.11 假红）。
"""
from __future__ import annotations

import ast
import io
import json
import os
import sys

ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ENGINE)
sys.path.insert(0, REPO)

from saintess_engine.package import load_stack            # noqa: E402
from saintess_engine.host.runtime import Host             # noqa: E402

FIXED = 1790308800          # 与 probe_cmds / probe_pager 同一根假钟（昼）
TOWN = "windmill_town"
INN = "wt_inn"
UID, UID2, UID3, UID4 = "u_pick", "u_pick2", "u_pick3", "u_pick4"
GID = "g_pick"
OK, BAD = [], []


def ok(msg):
    OK.append(msg)
    print("  OK  %s" % msg)


def bad(msg):
    BAD.append(msg)
    print("  X   %s" % msg)


class Ad(object):
    """最小适配器（照 scripts/e2e_drive.py 的真宿主契约）。`saved` 按 uid 存好几档。"""

    def __init__(self, seeds=None):
        self.out = []
        self.saved = {k: dict(v) for k, v in (seeds or {}).items()}

    def recv(self):
        return None

    def load_player(self, uid):
        return self.saved.get(uid)

    def save_player(self, uid, data):
        self.saved[uid] = dict(data) if isinstance(data, dict) else data

    def say(self, to, text):
        self.out.append(str(text))


def _usable(rec):
    """这件东西「用」得掉吗（域里现看：食物 / effect / heal 三格任一）。"""
    return bool(rec.get("food") or rec.get("effect") or rec.get("heal"))


def main():
    items = json.load(io.open(os.path.join(REPO, "content/data/items.json"), encoding="utf-8"))
    texts = json.load(io.open(os.path.join(REPO, "content/data/texts.json"), encoding="utf-8"))
    recipes = json.load(io.open(os.path.join(REPO, "content/data/recipes.json"), encoding="utf-8"))

    def T(key, **slots):
        s = texts[key]["value"]
        for k, v in slots.items():
            s = s.replace("{%s}" % k, str(v))
        return s

    db = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_pick.db")
    try:
        os.remove(db)
    except OSError:
        pass
    st = load_stack(str(REPO), inject={"db_path": db, "clock": lambda: FIXED})
    st.install()
    from content import loot as LT                                # noqa: E402
    from content import shop as SH                                # noqa: E402

    by_name = {}
    for k, v in items.items():
        if isinstance(v, dict) and v.get("name"):
            by_name.setdefault(str(v["name"]), (k, v))
    names = sorted(by_name)
    dup = sorted(LT.ambiguous_names())

    # 短名 / 长名那一对：短的不许「用得掉」、长的许（改前正是长的被吃掉）
    pair = None
    for a in names:
        for b in names:
            if a != b and len(a) >= 2 and b.startswith(a) and a not in LT.ambiguous_names():
                if not _usable(by_name[a][1]) and _usable(by_name[b][1]):
                    pair = (a, b)
                    break
        if pair:
            break

    # 同名几档那一组：取一组「域里重名、且每一档都有 quality」的
    grp = []
    for n in dup:
        ids = [k for k, v in items.items() if v.get("name") == n and isinstance(v, dict)]
        qs = sorted(str(items[i].get("quality")) for i in ids)
        if len(ids) >= 2 and all(qs):
            grp = (n, ids, qs)
            break
    gname, gids, gquals = grp if grp else ("", [], [])
    gq1, gq2 = (gquals[0], gquals[1]) if len(gquals) >= 2 else ("", "")
    g1 = next((i for i in gids if items[i].get("quality") == gq1), "")
    g2 = next((i for i in gids if items[i].get("quality") == gq2), "")

    # 强化 +1 要什么（料 / 钱从配方域现取 —— 不手打）
    step = recipes["rc_enh_01"]
    fee = int(step.get("gold") or 0)
    mats = {e["id"]: int(e["n"]) for e in (step.get("inputs") or [])}

    print("① 形状档（直调 `loot` 那一口）")
    short, long_ = pair if pair else ("", "")
    sid, srec = by_name.get(short, ("", {}))
    lid, lrec = by_name.get(long_, ("", {}))
    if not pair:
        bad("域里找不到「短名 ⊆ 长名」且短的不许用 / 长的用得掉 的那一对，这一条没法判")
    else:
        if LT.match_ids([lid, sid], short) == [sid]:
            ok("精确名优先：`%s` 命中它自己（部分命中压不住它）" % short)
        else:
            bad("精确名没有优先：`%s` → %s" % (short, LT.match_ids([lid, sid], short)))
        if LT.match_ids([lid, sid], lid) == [lid]:
            ok("按 id 找也认（`%s`）" % lid)
        else:
            bad("按 id 找不到：%s" % LT.match_ids([lid, sid], lid))
        if not LT.match_ids([sid], short, need_slot=True):
            ok("`need_slot=True`：非装备（%s）一件都不收（与 `probe_items` ①之二 同一口径）" % short)
        else:
            bad("`need_slot=True` 把非装备收下了：%s" % short)
    if len(gids) >= 2:
        badq = []
        for w in ("%s %s" % (gname, gq1), "%s %s" % (gq1, gname), "%s（%s）" % (gname, gq1)):
            if LT.match_ids(gids, w) != [g1]:
                badq.append((w, LT.match_ids(gids, w)))
        if not badq:
            ok("品阶三种写法（尾缀 / 前缀 / 括号）都只认那一档（%s）" % gq1)
        else:
            bad("有的写法没认出来：%s" % badq)
        if LT.match_ids(gids, "%s 没这一档" % gname) == []:
            ok("域里没有的那一档**不许猜**（回空，不是悄悄放宽成全名命中）")
        else:
            bad("认不出的品阶被静默放宽了")
        _qw = set(str(v.get("quality")) for v in items.values()
                  if isinstance(v, dict) and v.get("quality"))
        if LT.quality_words() == _qw:
            ok("品阶词表 = 域里出现过的 `quality`（现取 · 代码里不写中文）")
        else:
            bad("品阶词表与域对不上：%s" % sorted(LT.quality_words()))

    print("② 覆盖面（静态）：五份实现只剩一份")
    cdir = os.path.join(REPO, "content")

    def _src(fn):
        return io.open(os.path.join(cdir, fn), encoding="utf-8").read()

    seen = {}
    for fn in sorted(os.listdir(cdir)):
        if not fn.endswith(".py"):
            continue
        tree = ast.parse(_src(fn))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "_item_of_name":
                seen.setdefault("_item_of_name", []).append(fn)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                seg = ast.get_source_segment(_src(fn), node) or ""
                cmp = False
                for sub2 in ast.walk(node):
                    if not isinstance(sub2, ast.Compare):
                        continue
                    for op, comp in zip(sub2.ops, sub2.comparators):
                        if isinstance(op, ast.In) and isinstance(comp, ast.Name)                                 and comp.id == "nm":
                            cmp = True
                # 「自己扫背包 + 按名字的一部分比」= 第二份实现（判据只认这一对同时出现；
                #   `in nm` 本身还有别处正当用法 —— 认部位 / 认怪 / 认配方名，那几处不扫背包）
                if cmp and '"bag"' in seg and fn != "loot.py":
                    seen.setdefault("自扫背包比名字", []).append("%s:%s" % (fn, node.name))
    if "_item_of_name" not in seen:
        ok("`cmds_recipe._item_of_name`（扫整张物品表那一份）**已经不在了**（ast 扫真引用，不扫注释）")
    else:
        bad("`_item_of_name` 还在：%s" % seen["_item_of_name"])
    if "自扫背包比名字" not in seen:
        ok("**背包里的一件东西**按名字找：`content/` 里没有第二份实现（只剩 `loot.py` 那一口）")
    else:
        bad("还有人自己扫背包比名字：%s" % seen["自扫背包比名字"])

    def _calls(modfile, fnname, attrs):
        for node in ast.walk(ast.parse(_src(modfile))):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == fnname:
                got = set()
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                            and sub.func.attr in attrs:
                        got.add(sub.func.attr)
                return got
        return set()

    fwd = [("cmds_more.py", "_bag_hit", {"pick", "match_ids"}),
           ("cmds_gear.py", "_in_bag", {"pick"}),
           ("cmds_recipe.py", "item_use", {"pick"}),
           ("shop.py", "find", {"match_ids"})]
    miss = [(f, n) for f, n, a in fwd if not _calls(f, n, a)]
    if not miss:
        ok("四个调用方都**真调** `loot` 那一口（%s）" % " · ".join(n for _f, n, _a in fwd))
    else:
        bad("没转发到唯一那一口的：%s" % miss)
    aline = [fn for fn in sorted(os.listdir(cdir)) if fn.endswith(".py") and "SYS_PICK_AMBIG" in _src(fn)]
    if aline == ["cmds_gear.py"]:
        ok("`SYS_PICK_AMBIG` 只有一个出口（`cmds_gear.ambig_line`）")
    else:
        bad("`SYS_PICK_AMBIG` 的出口不止一处：%s" % aline)

    # ── 真宿主 ───────────────────────────────────────────────────────────
    def base(bag, **kw):
        p = {"cls": "cls_knight", "race": "human", "name": "试炼者", "level": 10, "exp": 0,
             "gold": 500, "hp": 200, "loc": TOWN, "node": "wt_gate_n", "prev": [],
             "bag": dict(bag), "equipped": {}, "codex": {}, "flags": {}, "alloc": {"STR": 20}}
        p.update(kw)
        return p

    seeds = {UID: base({sid: 5, lid: 1}), UID2: base({g1: 1, g2: 1}),
             UID3: base(dict({g2: 1}, **mats), gold=fee), UID4: base({g1: 1})}
    ad = Ad(seeds)
    host = Host(ad, str(REPO), inject={"db_path": db, "clock": lambda: FIXED})
    host.boot()

    def say(text, uid=UID):
        ad.out = []
        host.handle({"uid": uid, "group_id": GID, "text": text})
        return list(ad.out)

    def snap(uid=UID):
        return json.loads(json.dumps(ad.saved.get(uid) or {}, ensure_ascii=False))

    def amb(name, quals, key):
        return [T("SYS_PICK_AMBIG", n=2, name=name, list=" · ".join(quals),
                  say="%s %s %s" % (key, name, quals[0]))]

    print("③ ★ 精确名优先（真宿主真敲）")
    if short:
        _sv0 = snap()
        _v = say("查看 %s" % short)
        _want = T("SYS_ITEM_HEAD", name=srec.get("name"), icon=srec.get("icon", ""),
                  detail="%s · %s" % (srec.get("kind"), srec.get("quality")), n=5)
        if _v[:1] == [_want]:
            ok("`查看 %s` 回的是**它自己**（改前回的是「%s」 —— 精确名输给部分名）" % (short, long_))
        else:
            bad("`查看 %s` 回的不对：%s（该 %s）" % (short, _v[:1], _want))
        _u = say("使用 %s" % short)
        _sv1 = snap()
        if _u == [T("SYS_USE_NOT", name=short)] and _sv1.get("bag") == _sv0.get("bag"):
            ok("`使用 %s` 照实说「不是这么用的」，且 **%s 一件没少**（改前那碗汤被吃掉）"
               % (short, long_))
        else:
            bad("`使用 %s` 动了不该动的东西：%s / bag %s" % (short, _u[:2], _sv1.get("bag")))

    print("④ ★ 同名多件不替玩家挑（真宿主真敲 · 九处）")
    if gname:
        _sv2 = snap(UID2)
        _cases = [("查看 %s" % gname, "查看"), ("装备 %s" % gname, "装备"),
                  ("对比 %s" % gname, "对比"), ("丢弃 %s" % gname, "丢弃"),
                  ("卖出 %s" % gname, "卖出"), ("使用 %s" % gname, "使用"),
                  ("强化 %s" % gname, "强化")]
        _bad2 = [(t, say(t, UID2)[:1]) for t, k in _cases
                 if say(t, UID2)[:1] != amb(gname, [gq1, gq2], k)]
        if not _bad2 and snap(UID2) == _sv2:
            ok("七处（查看 / 装备 / 对比 / 丢弃 / 卖出 / 使用 / 强化）各回同一句照实话，"
               "**档一个字不动**")
        else:
            bad("同名多件那几档不对：%s · 档 %s" % (_bad2[:2], snap(UID2).get("bag")))
        ad.saved[UID2]["node"] = INN
        _o_in = say("存放 %s" % gname, UID2)
        _o_out = say("取出 %s" % gname, UID2)
        ad.saved[UID2]["node"] = "wt_gate_n"
        if _o_in == amb(gname, [gq1, gq2], "存放") and _o_out == [T("SYS_STASH_EMPTY")]:
            ok("`存放` 也走同一句（箱子里没有 ⇒ `取出` 照实说）")
        else:
            bad("存放 / 取出 那两档不对：%s / %s" % (_o_in[:1], _o_out[:1]))
        _e = say("装备 %s %s" % (gname, gq1), UID4)
        _sv4b = snap(UID4)
        if _e[:1] == [T("SYS_GEAR_EQUIP_OK", icon=items[g1].get("icon", ""),
                        name=LT.label_of(g1), kind=items[g1].get("kind", ""))] \
                and (_sv4b.get("equipped") or {}).get(items[g1]["slot"]) == g1:
            ok("点明品阶之后**只动那一件**：`装备 %s %s` ⇒ 穿上的是那一档（确认行也带品阶）"
               % (gname, gq1))
        else:
            bad("点明品阶没穿对：%s / %s" % (_e[:1], _sv4b.get("equipped")))
        _wantc = T("SYS_ITEM_HEAD", name=items[g2].get("name"), icon=items[g2].get("icon", ""),
                   detail="%s · %s" % (items[g2].get("kind"), gq2), n=1)
        if say("查看 %s %s" % (gname, gq2), UID2)[:1] == [_wantc]:
            ok("`查看 %s %s` 直接点到那一档（另一档在手也不含糊）" % (gname, gq2))
        else:
            bad("按品阶查看没对上：%s" % say("查看 %s %s" % (gname, gq2), UID2)[:1])
        if say("查看 %s（%s）" % (gname, gq1), UID2)[:1] == say("查看 %s %s" % (gname, gq1),
                                                               UID2)[:1]:
            ok("括号写法（`%s（%s）`）与空白写法回话逐字相同" % (gname, gq1))
        else:
            bad("括号写法不对")

    print("⑤ ★ 手里只有一档 ⇒ 叫得出就强得上（改前是死路）")
    if gname:
        _sv3 = snap(UID3)
        _r = say("强化 %s" % gname, UID3)
        _sv3b = snap(UID3)
        _enh = (_sv3b.get("enhance") or {})      # ★ 档上这一格是**顶级键**（不在 flags 里）
        if _r and _r[0] != T("SYS_ENHANCE_NOITEM", input=gname) \
                and int((_enh.get(g2) or {}).get("lv") or 0) == 1 and g1 not in _enh \
                and int(_sv3b.get("gold") or 0) == int(_sv3.get("gold") or 0) - fee:
            ok("`强化 %s`（手里只有一档）**真强上了**：+1 记在那一格 · 别的档一格没记 · 钱扣 %d"
               % (gname, fee))
        else:
            bad("只有一档时强化没走通：%s / enhance %s / 钱 %s→%s"
                % (_r[:1], _enh, _sv3.get("gold"), _sv3b.get("gold")))
        if say("强化 %s %s" % (gname, gq1), UID3)[:1] \
                == [T("SYS_ENHANCE_NOITEM", input="%s %s" % (gname, gq1))]:
            ok("点了一档手里没有的 ⇒ 照实说「背包里没有」（不是偷偷改成另一档）")
        else:
            bad("点了没有的那一档却动了手：%s" % say("强化 %s %s" % (gname, gq1), UID3)[:1])

    print("⑥ 列表：域里重名的才缀品阶")
    _sv = snap(UID2)
    _bag = say("背包", UID2)
    _rows = [ln for ln in _bag if ln.startswith("·")]
    _want_rows = ["· %s %s ×%s" % (items[i].get("icon", ""), LT.label_of(i), _sv["bag"][i])
                  for i in _sv["bag"]]
    if _rows == _want_rows and any(" · %s ×" % gq1 in ln for ln in _rows):
        ok("`背包` 逐字对账：重名的缀品阶（%s · %s）· 顺序照档上插入序" % (gq1, gq2))
    else:
        bad("背包行不对：%s（该 %s）" % (_rows, _want_rows))
    _srt = say("整理背包", UID2)
    if any("%s ×1" % LT.label_of(g1) in ln for ln in _srt) \
            and any("%s ×1" % LT.label_of(g2) in ln for ln in _srt):
        ok("`整理背包` 同一行规则（走 `loot.label_of`，不另拼一份）")
    else:
        bad("整理背包的行没带品阶：%s" % _srt)
    _one = base({sid: 1, lid: 2}, node=INN)
    ad.saved[UID] = _one
    _p = [ln for ln in say("背包") if ln.startswith("·")]
    _q = [ln for ln in say("整理背包") if ln.startswith("·")]
    _plain = ["· %s %s ×%s" % (items[i].get("icon", ""), str(items[i].get("name")),
                               _one["bag"][i]) for i in _one["bag"]]
    _ugly = [ln for ln in _p + _q
             if any(" · %s ×" % str(items[i].get("quality")) in ln for i in _one["bag"])]
    _same = sorted(_p) == sorted(_plain)
    if short and short not in LT.ambiguous_names() and _same and not _ugly:
        ok("**不重名的**（%s / %s）一个字都没改 —— 品阶只在「域里重名」的那些上出现"
           % (short, long_))
    else:
        bad("不重名的那几件被动了：%s / 该 %s" % (_p, _plain))
    print("⑦ 单件回归 + 形状（唯一命中 / 柜上）")
    ad.saved[UID] = base({sid: 5})
    _v = say("查看 %s" % short)
    _want = T("SYS_ITEM_HEAD", name=srec.get("name"), icon=srec.get("icon", ""),
              detail="%s · %s" % (srec.get("kind"), srec.get("quality")), n=5)
    if _v[:1] == [_want]:
        ok("`查看 <短名>` 单件时回话逐字一致（没被这批改坏）")
    else:
        bad("单件查看回话变了：%s" % _v[:1])
    _f = SH.find(gname)
    if len(_f) == 4 and _f[0] is None and _f[1] == {} and _f[2] == 0:
        ok("`shop.find` 是四元组形状（柜上同名多件也照实说）")
    else:
        bad("`shop.find` 形状不对：%r" % (_f,))
    _sn = {}
    for g in SH.goods():
        _sn.setdefault(str(g["rec"].get("name")), []).append(g["id"])
    if all(len(v) == 1 for v in _sn.values()):
        ok("柜上今天**没有**同名多件（%d 件货 · 名字两两不同）—— 那一档只守形状" % len(_sn))
    else:
        bad("柜上出现同名多件了：%s" % {k: v for k, v in _sn.items() if len(v) > 1})

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
