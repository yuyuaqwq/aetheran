# -*- coding: utf-8 -*-
"""探针：长列表分页（B4-17）—— 第 41 支。

为什么有这条线（端到端玩出来的真缺口）
--------------------------------------
`06_第一阶段垂直切片/03_风车镇_指令与回复.md` §〇 排版纪律写着
「一次回复 不超过 400 字（手机上三屏以内）」「超长的内容 分页：『下一页』/『回 <页码>』」，
`04_指令总表.md` 背包那一行写着「打开（分页）」，`content/data/commands.json` 里 `bag` 的
`desc` 也写着「打开背包（分页）」—— 可**代码里一条分页都没有**：列到第 20 种就写一行
「…（还有 N 种）」，**第 21 种起玩家再也看不到**（实测 25 种只看得见 20 种）。
引擎早就备好了 `command/paging.py`（`page_items` / `parse_page`）与
`Env.page()` / `Env.page_items()`，本包**零调用方**。

判据（一条都不许松）
  ① 形状档：`content/pager.py::PER_PAGE` 是**唯一登记处**（背包 20 · 本群榜 10）·
     切片 / 解析只走引擎（`content/` 里 `page_items` / `parse_page` 只许出现在 pager）
  ② ★ 一个都不许丢：25 种的背包，两页看得见的名字**并集 = 全部 25 种**（逐 id 对 `loot.rec_of`）
  ③ 真宿主真敲：`背包` ⇒ 20 行 + 页脚「第 1/2 页」· `下一页` ⇒ 第 2 页 · `回 1` ⇒ 回第 1 页
  ④ 页码按**自己的声明**剥（`argv` 那一支）：`背包 2` == `包 2` == `包裹 2`（回话逐字相同）
  ⑤ 越界**夹取**（引擎口径）：`回 99` ⇒ 第 2/2 页 · 在最后一页敲 `下一页` ⇒ 仍是第 2/2 页
  ⑥ 还没翻过任何列表 ⇒ `SYS_PAGE_NONE`，且**档一个字不动**
  ⑦ 本群榜：库里 12 个人 + 自己 ⇒ 第 1 页正好一页 + 页脚 · `排行 2` 翻得到**自己那一行**
     （改前 `board[:10]` 直接切掉 ⇒ 排在第 11 位的人**永远看不到自己**）
  ⑧ 看一眼列表是**只读**的（背包 / 排行 / 下一页 / 回 各跑一遍，档逐字相同）
  ⑨ 静态守卫：两个列表口（`bag_page` / `ranking_page`）都**真调** `pager.render`
  ⑩ 死槽位 0：`SYS_BAG_MORE` 已不在 texts、也不在代码里；两个新槽位都在 texts 且被引用

★ F6（QA P4 E-4）追加的判据（`帮助` 里宣传的『下一页』/『回 <页码>』改前在别的长列表上是死指令）：
  ⑪ ★ 四本谱（材料谱 / 风味谱 / 怪物谱 / 旧物谱）与 `图鉴` 一览都接进同一口 —— 静态守卫逐支核
     「真调 `pager.render`」（`_one_book` / `codex` 那两处，不许谁自己 `rows[0:10]` 切）
  ⑫ ★ **两态**：超过一页 ⇒ 页脚 + 『下一页』/『回 1』都翻得动，且翻完**一条都不许丢**
     （两页并集 = 谱里那几条）；一行都不超 ⇒ **不出页脚**、光标也不记（敲『下一页』还是引导那句）
  ⑬ ★ `图鉴 2` 这类**带页码**的写法按自己的声明剥参（与 `背包 2` 同一个口）；谱自己的尾注
     （`SYS_CODEX_RELIC_ASK_HINT`）与页脚同时出现时，**页脚仍必须是最后一行**

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_pager.py
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

FIXED = 1790308800          # 2026-09-25 12:00 +08:00（昼 · 与 probe_cmds 同一根假钟）
UID = "u_pager_probe"
GID = "g_pager_probe"
OK, BAD = [], []


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


def main():
    items = json.load(io.open(os.path.join(REPO, "content/data/items.json"), encoding="utf-8"))
    texts = json.load(io.open(os.path.join(REPO, "content/data/texts.json"), encoding="utf-8"))

    def T(key, **slots):
        s = texts[key]["value"]
        for k, v in slots.items():
            s = s.replace("{%s}" % k, str(v))
        return s

    db = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_pager.db")
    try:
        os.remove(db)
    except OSError:
        pass
    st = load_stack(str(REPO), inject={"db_path": db, "clock": lambda: FIXED})
    st.install()
    from content import cmds_ast as CA                          # noqa: E402
    from content import loot as LT                               # noqa: E402
    from content import pager as PG                              # noqa: E402
    from content import persistence as PS                        # noqa: E402

    ids = list(items)
    seed = {"cls": "cls_knight", "race": "human", "name": "试炼者", "level": 3, "exp": 0,
            "gold": 200, "hp": 116, "loc": "windmill_town", "node": "wt_gate_n",
            "prev": [], "bag": {k: 1 for k in ids[:25]}, "equipped": {}, "codex": {}, "flags": {}}
    ad = Ad(seed=seed)
    host = Host(ad, str(REPO), inject={"db_path": db, "clock": lambda: FIXED})
    host.boot()

    def say(text, uid=UID, group_id=GID):
        ad.out = []
        host.handle({"uid": uid, "group_id": group_id, "text": text})
        return list(ad.out)

    def snap(uid=UID):
        return json.loads(json.dumps(ad.saved.get(uid) or {}, ensure_ascii=False))

    # ── ① 形状档：一页几行只有一个登记处 · 切片与解析都走引擎
    print("① 形状档：一页几行只有一个登记处 · 切片走引擎")
    pp = PG.PER_PAGE
    if pp.get("bag") == 20 and pp.get("ranking") == 10:
        ok("`pager.PER_PAGE` 是唯一登记处：背包 %d 行 / 本群榜 %d 行" % (pp["bag"], pp["ranking"]))
    else:
        bad("PER_PAGE 不对：%r" % (pp,))
    who = {}
    cdir = os.path.join(REPO, "content")
    for fn in sorted(os.listdir(cdir)):
        if not fn.endswith(".py"):
            continue
        src = io.open(os.path.join(cdir, fn), encoding="utf-8").read()
        for w in ("page_items", "parse_page"):
            if w in src:
                who.setdefault(w, []).append(fn)
    if who.get("page_items") == ["pager.py"] and who.get("parse_page") == ["pager.py"]:
        ok("切片 / 解析都走引擎：`content/` 里 `page_items` / `parse_page` 只出现在 pager.py")
    else:
        bad("有人自己造了第二份分页：%r" % (who,))

    def _calls(modfile, fnname, attr):
        tree = ast.parse(io.open(os.path.join(cdir, modfile), encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == fnname:
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                            and sub.func.attr == attr:
                        return True
        return False

    _miss = [x for x in (("cmds_ast.py", "bag_page"), ("cmds_self.py", "ranking_page"))
             if not _calls(x[0], x[1], "render")]
    if not _miss:
        ok("两个列表口（`bag_page` / `ranking_page`）都**真调** `pager.render`")
    else:
        bad("这两个口没走分页那一处：%s" % _miss)

    # ── ② 一个都不许丢：25 种 ⇒ 两页并起来正好 25 种
    print("② ★ 25 种的背包：两页看得见的并集 = 全部 25 种")
    names = [LT.rec_of(k).get("name") for k in ids[:25]]
    p1 = say("背包")
    p2 = say("下一页")
    rows1 = [ln for ln in p1 if ln.startswith("· ")]
    rows2 = [ln for ln in p2 if ln.startswith("· ")]
    seen = {}
    for ln in rows1 + rows2:
        for nm in names:
            if nm and nm in ln:
                seen[nm] = seen.get(nm, 0) + 1
    _lost = [nm for nm in names if seen.get(nm, 0) < names.count(nm)]
    if not _lost and len(rows1) + len(rows2) == 25:
        ok("改前只看得见 20 种 ⇒ 现在两页并起来 %d 行、25 种一个不漏" % (len(rows1) + len(rows2)))
    else:
        bad("还看不见的：%s（第 1 页 %d 行 · 第 2 页 %d 行）" % (_lost, len(rows1), len(rows2)))

    # ── ③ 真宿主真敲：抬头 / 页脚 / 下一页 / 回 <页码>
    print("③ 真宿主真敲：背包 ⇒ 页脚 · 下一页 ⇒ 第 2 页 · 回 1 ⇒ 回第 1 页")
    if p1[0] == T("SYS_BAG_HEAD", n=25):
        ok("第 1 页抬头 == texts 的 `SYS_BAG_HEAD`（25 种）")
    else:
        bad("抬头不对：%r" % (p1[0] if p1 else None,))
    _f1 = T("SYS_PAGE_FOOT", page=1, pages=2)
    _f2 = T("SYS_PAGE_FOOT", page=2, pages=2)
    if p1[-1] == _f1 and len(rows1) == 20:
        ok("第 1 页 = 20 行 + 页脚「%s」" % _f1)
    else:
        bad("第 1 页不对：末行 %r · %d 行" % (p1[-1] if p1 else None, len(rows1)))
    if p2[-1] == _f2 and len(rows2) == 5:
        ok("『下一页』⇒ 第 2 页 = 5 行 + 页脚「%s」" % _f2)
    else:
        bad("第 2 页不对：末行 %r · %d 行" % (p2[-1] if p2 else None, len(rows2)))
    if say("回 1") == p1:
        ok("『回 1』⇒ 与第 1 页逐字相同")
    else:
        bad("『回 1』没回到第 1 页")

    # ── ④ 页码按自己的声明剥（连写 / 别名都算同一个参）
    print("④ 页码按自己的声明剥：背包 2 == 包 2 == 包裹 2")
    _same = [t for t in ("背包 2", "包 2", "包裹 2") if say(t) != p2]
    if not _same:
        ok("`背包 2` / `包 2` / `包裹 2` 三条都翻到第 2 页（回话逐字相同）")
    else:
        bad("这几条的参没剥对：%s" % _same)

    # ── ⑤ 越界夹取（引擎 `page_items` 的口径）
    print("⑤ 越界夹取：回 99 ⇒ 末页 · 末页敲下一页 ⇒ 还是末页")
    if say("回 99") == p2 and say("回 0") == p1:
        ok("页码越界由引擎夹到 [1, pages]（`回 99` ⇒ 2/2 · `回 0` ⇒ 1/2）")
    else:
        bad("越界页码没夹住")
    say("回 2")
    if say("下一页") == p2:
        ok("已经在末页再敲『下一页』⇒ 原地不动（仍 2/2），不越界不出错")
    else:
        bad("末页敲『下一页』出问题了")

    # ── ⑥ 还没翻过任何列表 · 空背包不分页
    print("⑥ 没翻过列表 ⇒ 点名那一句；空背包 ⇒ 不分页")
    _none = T("SYS_PAGE_NONE")
    _o_none = say("下一页", uid="u_fresh")
    _fresh_txt = json.dumps(ad.saved.get("u_fresh") or {}, ensure_ascii=False)
    if _o_none == [_none] and "pager" not in _fresh_txt:
        ok("没翻过任何列表敲『下一页』⇒ 回 `SYS_PAGE_NONE`，"
           "且光标**不落档**（档里没有 pager 这一格）")
    else:
        bad("没光标那一条不对：%r · 档=%r" % (_o_none[:2], _fresh_txt[:60]))
    _empty = say("背包", uid="u_fresh")
    if _empty == [T("SYS_BAG_EMPTY")]:
        ok("空背包 ⇒ 只回 `SYS_BAG_EMPTY`（不分页、不出页脚）")
    else:
        bad("空背包那条不对：%r" % (_empty,))

    # ── ⑦ 本群榜：一页 10 人 · 自己那一行**翻得到**（改前 `board[:10]` 直接切掉）
    print("⑦ 本群榜：库里 12 人 + 自己 ⇒ 第 1 页 10 行 · 第 2 页翻得到自己")
    for i in range(1, 13):
        PS.update_player(GID, "u_%02d" % i, name="榜上%02d" % i, level=21 - i, exp=0)
    r1 = say("排行")
    r2 = say("排行 2")
    _r1rows = [ln for ln in r1 if ln.startswith("1. ") or ". " in ln[:4]]
    _r2rows = [ln for ln in r2 if ". " in ln[:4]]
    _mine = "试炼者"
    _in2 = any(_mine in ln for ln in r2)
    _in1 = any(_mine in ln for ln in r1)
    if (r1[0] == T("SYS_RANKING_HEAD") and len(_r1rows) == 10
            and r1[-2] == T("SYS_RANKING_TAIL") and r1[-1] == _f1):
        ok("第 1 页 = 榜头 + 10 行 + 尾注 + 页脚（库里 12 人 + 自己 · 第 11 名起翻页看）")
    else:
        bad("第 1 页不对：%r" % (r1[:2] + r1[-2:],))
    if _in2 and not _in1:
        ok("排在 13 位的自己（%s）**翻得到**（改前 `board[:10]` 把他整条切掉）" % _mine)
    else:
        bad("自己那一行：第 2 页有=%s · 第 1 页有=%s" % (_in2, _in1))
    if r2[-2] == T("SYS_RANKING_TAIL") and r2[-1] == _f2:
        ok("第 2 页 = 尾注 + 页脚（**页脚永远是最后一行** —— 奥兰迪亚 v130.3 那笔同一个口径）")
    else:
        bad("第 2 页收尾不对：%r" % (r2[-2:],))

    # ── ⑧ 看一眼列表是只读的（档逐字相同）
    print("⑧ 看一眼列表／翻一页 ⇒ 档一个字不动")
    _before = snap()
    for t in ("背包", "下一页", "回 1", "排行", "排行 2"):
        say(t)
    if snap() == _before:
        ok("五条（背包 / 下一页 / 回 1 / 排行 / 排行 2）跑完，档逐字相同（光标在内存里，不落档）")
    else:
        bad("这几条动了档：%s" % [k for k in snap() if snap().get(k) != _before.get(k)])

    # ── ⑨ 死槽位 0 + 新槽位都被引用
    print("⑨ 槽位：`SYS_BAG_MORE` 撕干净 · 两个新槽位都在 texts 且被代码引用")
    _refs = []
    for fn in sorted(os.listdir(cdir)):
        if fn.endswith(".py"):
            _refs.append(io.open(os.path.join(cdir, fn), encoding="utf-8").read())
    _allsrc = "\n".join(_refs)
    if "SYS_BAG_MORE" not in texts and "SYS_BAG_MORE" not in _allsrc:
        ok("`SYS_BAG_MORE`（那条「还有 N 种看不到」）在 texts 与代码里**都不在了**")
    else:
        bad("`SYS_BAG_MORE` 还在：texts=%s · 代码=%s"
            % ("SYS_BAG_MORE" in texts, "SYS_BAG_MORE" in _allsrc))
    _want_slots = [k for k in ("SYS_PAGE_FOOT", "SYS_PAGE_NONE") if k in texts]
    _hit_slots = [k for k in ("SYS_PAGE_FOOT", "SYS_PAGE_NONE") if 'T("%s"' % k in _allsrc]
    if len(_want_slots) == 2 and len(_hit_slots) == 2:
        ok("两个新槽位都在 texts 里、也都被 `content/` 真引用（%s）" % " / ".join(_want_slots))
    else:
        bad("新槽位不对：在 texts %s · 被引用 %s" % (_want_slots, _hit_slots))

    # ══════════════════════════════════════════════════════════
    # ★ F6（QA P4 E-4）：四本谱与图鉴一览真分页
    # ══════════════════════════════════════════════════════════
    print("⑪ ★ F6：五条口（图鉴 / 四本谱）都真走 `pager.render`（谁也别自己切）")
    _tree = ast.parse(io.open(os.path.join(cdir, "cmds_codex.py"), encoding="utf-8").read())

    def _calls_any(fnname, attrs):
        for node in ast.walk(_tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == fnname:
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) \
                            and sub.func.id in attrs:
                        return True
        return False

    _miss2 = [fn for fn in ("codex", "codex_material", "codex_flavor",
                            "codex_monster", "codex_relic")
              if not _calls_any(fn, ("_page", "_one_book"))]
    if not _miss2:
        ok("图鉴 + 四本谱五条口都经 `_page` / `_one_book` 走 `pager.render`（`PER_PAGE` 是唯一登记处）")
    else:
        bad("这几个口自己切了：%s" % _miss2)
    _kinds = [k for k in ("codex", "codex_material", "codex_flavor", "codex_monster",
                          "codex_relic") if k not in PG.PER_PAGE]
    if not _kinds:
        ok("`pager.PER_PAGE` 里五个 kind 都登记了（%s）"
           % " · ".join("%s %d" % (k, PG.PER_PAGE[k]) for k in
                        ("codex", "codex_material", "codex_flavor", "codex_monster", "codex_relic")))
    else:
        bad("这几个 kind 没登记一页几行：%s" % _kinds)
    _again2 = [k for k in ("codex", "codex_material", "codex_flavor", "codex_monster",
                           "codex_relic") if not PG._again(ad, None, UID, None, k)]
    if not _again2:
        ok("『下一页』/『回 <页码>』在这五列上都接得上（`pager._again` 五条都在）")
    else:
        bad("这几列翻不动：%s" % _again2)

    print("⑫ ★ F6 两态 A：超过一页 ⇒ 页脚 · 『下一页』翻得动 · 翻完一条都不许丢")
    _cx = json.load(io.open(os.path.join(REPO, "content/data/codex.json"), encoding="utf-8"))
    _book = {"material": list(_cx["material"]), "flavor": list(_cx["flavor"]),
             "monster": list(_cx["monster"]), "relic": list(_cx["relic"])}
    _BUID = "u_pager_books"
    _bseed = dict(seed)
    _bseed.update({"bag": {}, "books": {
        "material": {k: {"day": 1} for k in _book["material"]},
        "monster": {k: {"day": 1, "kills": 1} for k in _book["monster"][:12]},
        "relic": {k: {"day": 1, "known": True} for k in _book["relic"][:11]},
        "flavor": {}}})
    ad.saved[_BUID] = _bseed

    def say2(text):
        ad.out = []
        host.handle({"uid": _BUID, "group_id": GID, "text": text})
        return list(ad.out)

    def _rows(out):
        return [x for x in out if x.startswith("· ")]

    _foot1 = T("SYS_PAGE_FOOT", page=1, pages=2)
    _foot2 = T("SYS_PAGE_FOOT", page=2, pages=2)
    # 材料谱：12 条 / 一页 10 行
    _m1 = say2("材料谱")
    _m2 = say2("下一页")
    if _m1[0] == T("SYS_CODEX_BOOK_HEAD", book="材料谱", n=12, target=10) \
            and len(_rows(_m1)) == 10 and _m1[-1] == _foot1:
        ok("`材料谱`（12 条）⇒ 抬头 + 10 行 + 页脚「%s」" % _foot1)
    else:
        bad("材料谱第 1 页不对：%r 行 %d" % (_m1[:1] + _m1[-1:], len(_rows(_m1))))
    if len(_rows(_m1)) + len(_rows(_m2)) == 12 and _m2[-1] == _foot2:
        ok("『下一页』⇒ 第 2 页；两页并起来 12 行（一条不漏）")
    else:
        bad("材料谱第 2 页不对：%d + %d 行 · 末行 %r"
            % (len(_rows(_m1)), len(_rows(_m2)), _m2[-1] if _m2 else None))
    if say2("回 1") == _m1:
        ok("『回 1』⇒ 与第 1 页逐字相同")
    else:
        bad("『回 1』没回材料谱第 1 页")
    if _m2 == say2("材料谱 2"):
        ok("`材料谱 2` 与『下一页』翻到的是同一页（页码按自己的声明剥 —— 与 `背包 2` 同一个口）")
    else:
        bad("`材料谱 2` 没翻对")
    # 怪物谱：12 条 / 一页 10 行 —— 带页码的写法 + 越界夹取
    _g1 = say2("怪物谱")
    if len(_rows(_g1)) == 10 and _g1[-1] == _foot1 and say2("怪物谱 2")[-1] == _foot2:
        ok("`怪物谱`（12 条）⇒ 10 行 + 页脚 · `怪物谱 2` ⇒ 第 2 页")
    else:
        bad("怪物谱分页不对：%r" % (_g1[-1:],))
    if say2("怪物谱 99") == say2("怪物谱 2"):
        ok("页码越界仍由引擎夹取（`怪物谱 99` ⇒ 末页）")
    else:
        bad("怪物谱越界页码没夹住")
    # 旧物谱：11 条已知 / 一页 10 行 —— 谱自己的尾注要与页脚共存，且页脚**仍必须是最后一行**
    _q1 = say2("旧物谱")
    _q2 = say2("下一页")
    if len(_rows(_q1)) == 10 and _q1[-1] == _foot1 and len(_rows(_q2)) == 1 and _q2[-1] == _foot2:
        ok("`旧物谱`（11 条）⇒ 10 + 1 行跨两页（未认出的那几条一个都不丢）")
    else:
        bad("旧物谱分页不对：%d + %d 行 · 末行 %r"
            % (len(_rows(_q1)), len(_rows(_q2)), _q2[-1] if _q2 else None))

    print("⑬ ★ F6 两态 B：不超一页 ⇒ 不出页脚 · 光标也不记（『下一页』还是引导那句）")
    def _set_mat(ks):
        """把这一档的「材料谱记了几条」改成 `ks`（★ 从**当前**那一档上取，别假定对象没被换过）。"""
        cur = dict(ad.saved.get(_BUID) or {})
        bk = dict(cur.get("books") or {})
        bk["material"] = {k: {"day": 1} for k in ks}
        cur["books"] = bk
        ad.saved[_BUID] = cur

    _set_mat(_book["material"][:3])
    _c1 = say2("材料谱")
    if len(_rows(_c1)) == 3 and not [x for x in _c1 if "第" in x and "页" in x]:
        ok("只记 3 条 ⇒ 一页装下、**不出页脚**（两态的另一半）")
    else:
        bad("不超一页却出了页脚：%r" % (_c1,))
    # 光标只在**真分了页**时记（B4-17 的登记口径）：一页装下的列表不记旧光标 ——
    # 拿一个**全新的人**来钉这一条（他看过的唯一一列就是一页装得下的材料谱）。
    _BUID2 = "u_pager_flat"
    _flat = dict(_bseed)
    _flat["books"] = {"material": {k: {"day": 1} for k in _book["material"][:3]},
                      "flavor": {}, "monster": {}, "relic": {}}
    ad.saved[_BUID2] = _flat

    def say3(text):
        ad.out = []
        host.handle({"uid": _BUID2, "group_id": GID, "text": text})
        return list(ad.out)

    if len(_rows(say3("材料谱"))) == 3 and say3("下一页") == [T("SYS_PAGE_NONE")] \
            and say3("回 9") == [T("SYS_PAGE_NONE")]:
        ok("一页装下的列表**不记光标**：随后敲『下一页』/『回 9』⇒ 仍是引导那句"
           "（`SYS_PAGE_NONE`），不是凭空翻出一页")
    else:
        bad("没分页时那两下不对：%r / %r" % (say3("下一页"), say3("回 9")))
    # 图鉴一览：4 本谱 ⇒ 一页，永远不出页脚
    _k0 = say2("图鉴")
    if _k0[0] == T("SYS_CODEX_HEAD") and not [x for x in _k0 if "页" in x and "第" in x]:
        ok("`图鉴`（四本谱四行）⇒ 一页，不出页脚（这一列没有超一页的那天）")
    else:
        bad("图鉴一览不对：%r" % (_k0,))
    # 空谱：只回空谱那句（不分页、不出页脚）
    if say2("风味谱") == [T("SYS_CODEX_EMPTY_FLAVOR")]:
        ok("空的风味谱 ⇒ 只回 `SYS_CODEX_EMPTY_FLAVOR`（不分页）")
    else:
        bad("空风味谱那条不对：%r" % (say2("风味谱"),))

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
