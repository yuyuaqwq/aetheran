# -*- coding: utf-8 -*-
"""判据：加点这条线**零机器键上屏**（台账 L2154）。

★ 不变量（两条，都是玩家可见面）：
  ① 任何坏档（坏维 / 非数字 / 负数 / 有限数 / 小数 / 超投 / 坏等级）都必须
     **回到玩家一句中文**（`SYS_ALLOC_BAD_SAVE` 句壳），**不许裸异常逃出指令**。
  ② 那一行**零机器键 / 零数据面值**（`'ZZZ'` / `'体力'` / `'abc'` / 裸负数都不得出现）。
     五维名 STR/AGI/… 不算机器键（玩家在「加点 力量」里认得，且显示面本来就翻中文）。
  ③ 机器侧原话**必须仍可查**（`str(exc)` 带坏值 + 日志留痕）—— 治上屏不等于把诊断扔了。
  ④ 正常路径**逐字不变**（零回归）。
"""
import asyncio, io, json, logging, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
os.environ.setdefault("GWEN_FRAMEWORK_DIR", r"C:/Users/yuyu/framework-engine")
os.environ.setdefault("GWEN_HOST_DIR", r"C:/Users/yuyu/qqbot/data/plugins/dragonfall")

from content import alloc as AL
from content import cmds_ast as CA

PASS, FAIL = [], []


def check(ok, label, extra=""):
    (PASS if ok else FAIL).append(label)
    print("  %s %s%s" % ("✓" if ok else "✗", label, ("  " + str(extra)) if extra else ""))


# 坏值里**故意**混玩家看得懂的与非机器键，唯一要判的是「不该出现在屏幕上」
MACHINE = ["ZZZ", "体力", "abc", "-5", "PanelMissing", "AllocError", "Traceback",
           "content/", ".py", "classes 域", "suggest_alloc", "alloc 不是"]

BAD = [("坏维-ZZZ", {"alloc": {"ZZZ": 3}}),
       ("坏维-中文", {"alloc": {"体力": 3}}),
       ("非数字", {"alloc": {"STR": "abc"}}),
       ("负数", {"alloc": {"STR": -5}}),
       ("非有限", {"alloc": {"STR": float("inf")}}),
       ("超投", {"alloc": {"STR": 99}}),
       ("坏等级", {"level": "abc", "alloc": {}}),
       ("alloc非表", {"alloc": "oops"})]


async def run(**kw):
    env = type("E", (), {})()
    out = []
    async def sink(s):
        out.append(s)
    pl = {"cls": "cls_knight", "level": 3, "alloc": {}}
    pl.update(kw)
    try:
        async for s in CA.alloc_points(env, sink, "u1", pl):
            out.append(s)
    except Exception as e:
        out.append("!!EXC:%r" % (e,))
    return out


async def main():
    print("—— A 段 · 坏档必须回到玩家一句中文（零裸异常）")
    for name, kw in BAD:
        r = await run(**kw)
        escaped = [x for x in r if str(x).startswith("!!EXC:")]
        body = [x for x in r if not str(x).startswith("!!EXC:")]
        check(not escaped, "A %s 不裸逃逸" % name, r if escaped else "")
        check(len(body) == 1 and body[0].startswith("档上的加点这一格不对"),
              "A %s 回玩家句壳" % name, body)
        if body:
            hits = [m for m in MACHINE if m in body[0]]
            check(not hits, "A %s 零机器键" % name, hits)

    print("—— B 段 · 机器侧诊断必须仍可查（没把证据扔掉）")
    for fn, arg in [("spent", {"STR": "abc"}), ("spent", {"ZZZ": 1})]:
        try:
            AL.spent(arg)
            check(False, "B %s 应抛" % (arg,))
        except AL.AllocError as e:
            check("abc" in str(e) or "ZZZ" in str(e), "B str(exc) 带坏值 %r" % (arg,), str(e))
            check(bool(e.player_reason) and "ZZZ" not in e.player_reason
                  and "abc" not in e.player_reason,
                  "B player_reason 零坏值 %r" % (arg,), e.player_reason)

    print("—— C 段 · 静态：两个 catch 一律填 player_reason（不许再填 e）")
    for f in ("content/cmds_ast.py",):
        src = io.open(os.path.join(ROOT, f), encoding="utf-8").read()
        check("SYS_ALLOC_BAD_SAVE\", why=e)" not in src,
              "C %s 无 why=e 残留" % f)
        n_player = src.count("SYS_ALLOC_BAD_SAVE\", why=e.player_reason)")
        n_catch = src.count("except AL.AllocError as e:")
        check(n_player >= 3 and n_player == n_catch,
              "C %s 每个 AllocError catch 都填 player_reason（%d/%d）" % (f, n_player, n_catch),
              "player=%d catch=%d" % (n_player, n_catch))
    asrc = io.open(os.path.join(ROOT, "content/alloc.py"), encoding="utf-8").read()
    check("def _classify(" in asrc, "C alloc.py 有 _classify")
    import ast as _ast
    _tree = _ast.parse(asrc)
    _doc = set()
    for _n in _ast.walk(_tree):
        if isinstance(_n, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef, _ast.Module)):
            if _n.body and isinstance(_n.body[0], _ast.Expr) and                     isinstance(_n.body[0].value, _ast.Constant) and                     isinstance(_n.body[0].value.value, str):
                _doc.update(range(_n.body[0].lineno, _n.body[0].end_lineno + 1))
    _impl = [ln for i, ln in enumerate(asrc.splitlines(), 1)
             if i not in _doc and ln.strip() and not ln.strip().startswith("#")]
    check(not any("_LOG" in ln or "logging" in ln for ln in _impl),
          "C alloc.py 实现里不记日志（诊断由消费方那 5 个 catch 记，标准库依赖不增）",
          [ln for ln in _impl if "_LOG" in ln or "logging" in ln])
    check("import logging" in io.open(os.path.join(ROOT, f), encoding="utf-8").read(),
          "C %s 用标准库 logging 留痕" % f)

    print("—— D 段 · 正常路径逐字不变（零回归）")
    r = await run(alloc={"STR": 3})
    check(r == ["加点 <属性> [次数] ｜ 还剩 11 点没投 ｜ 可加：力量 · 敏捷 · 智力 · 体质 · 意志",
                "推荐分配（14 点铺满）：力量 7 · 体质 5 · 意志 2"], "D 无参档逐字不变", r)
    r2 = await run(alloc={})
    check(r2 == ["加点 <属性> [次数] ｜ 还剩 14 点没投 ｜ 可加：力量 · 敏捷 · 智力 · 体质 · 意志",
                 "推荐分配（14 点铺满）：力量 7 · 体质 5 · 意志 2"], "D 空档逐字不变", r2)
    check(AL.balance(3, {"STR": 3}) == 11, "D balance 正常值不变")
    check(AL.spent({"STR": 3, "AGI": 2}) == 5, "D spent 正常值不变")
    check(AL.apply({"STR": 3}, "AGI", 2) == {"STR": 3, "AGI": 2}, "D apply 正常值不变")

    print("—— E 段 · 日志留痕真的发出去了（不是只写了一行代码）")
    recs = []
    h = logging.Handler()
    h.emit = lambda r: recs.append(r)
    lg = CA._LOG                      # ★ 诊断由消费方那 5 个 catch 记（alloc.py 自身不记）
    lg.addHandler(h)
    lg.setLevel(logging.WARNING)
    lg.propagate = False
    try:
        await run(alloc={"ZZZ": 3})
    finally:
        lg.removeHandler(h)
    check(len(recs) >= 1, "E 坏档产生日志记录", len(recs))
    check(any("ZZZ" in r.getMessage() for r in recs), "E 日志里带得到坏键 'ZZZ'",
          [r.getMessage() for r in recs])
    check(any(r.exc_info for r in recs), "E 日志带 exc_info（栈可追）")

    print()
    print("结果：通过 %d / 失败 %d" % (len(PASS), len(FAIL)))
    if FAIL:
        print("红：")
        for f in FAIL:
            print("  ✗ " + f)
    return 1 if FAIL else 0


sys.exit(asyncio.run(main()))
