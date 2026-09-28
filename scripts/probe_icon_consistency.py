# -*- coding: utf-8 -*-
"""探针：同屏同角色的图标一致性（P2-3 · 排版观感车道）

为什么有这条线
--------------------------------------------------
鱼鱼口径原话：「emoji 是可以的……只要很规整观感好问题就不大」「我甚至觉得适当的 emoji 会更好」
=> **emoji 多与少都不是缺陷**；真判据 = **同一界面内用法一致**。
只读审计曾按「覆盖率」给分（SYS 6% / COMBAT 51%），本支明确**不采信覆盖率**当指标 ——
那是把优点当 KPI，会逼别的线为凑数乱加图标。

本支只钉一件：**同一屏、同一角色的若干行里，有的带图标、有的不带**。
角色只按**槽位名与值的形状**判，**绝不看它有没有 emoji** —— 否则「缺图标」那一行
会被归成「不是这类行」，判据自己把自己废掉（★ 本支第一版真踩过这个坑，见 REVERSE-PROOF）。

怎么算「同一屏」
--------------------------------------------------
一个「屏」= 某个 handler 函数 + 它（递归）调用的本地 helper 里出现的全部槽位。
★ **不按角色名后缀分组**（`_CAP` / `_HEAD` 那类）：实测那会把不同屏的槽位凑成一组
（`SYS_GEAR_HP_CAP` 在属性页 · `SYS_ENHANCE_CAP` 在铁匠铺）=> 假阳性。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_icon_consistency.py
"""
from __future__ import annotations

import ast
import io
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

TX = json.load(io.open(REPO / "content" / "data" / "texts.json", encoding="utf-8"))

#: emoji / 图标字符（含 VS16 与本包自用的 dingbat 族 ✦ ✔）
EMO = re.compile(u"[\u2600-\u27BF\u2B00-\u2BFF\U0001F000-\U0001FAFF"
                 u"\u2705\u274C\u26A0\u2714\u2726\uFE0F]")

#: 屏内「分节抬头」类槽位（按**名字**判，不看值）
HEAD_SUF = ("_HEAD", "_GOODS", "_SHOP", "_SRC_HEAD", "_BOUNTY_HEAD", "_SIDE_HEAD", "_LEAD")

#: ★ 刻意不比的那一族：成功/结果行 vs 提示/拒绝行。
#:   那些行**实屏不同屏**（敲「丢 破布」只出提示行，不会与成功行同屏），统一反而错。
OTHER_ROLE = "other"

#: 屏内行数的下限：孤零零一行不构成「并列」，不判（本支不为覆盖率发难）
MIN_ROWS = 2

T_CALL = ("T", "text", "_T")


def _val(slot):
    e = TX.get(slot)
    return (e.get("value", "") if isinstance(e, dict) else e) or ""


def _has_emo(slot):
    return bool(EMO.search(_val(slot)))


def _role(slot, v):
    """行在屏上的**角色**。★ 只看槽位名与值的形状，**绝不看有没有 emoji**。"""
    if slot.endswith("_ROW"):
        return "row"
    if re.match(r"^\s*\u3010", v):
        return "screen_head"
    if slot.endswith(HEAD_SUF):
        return "section_head"
    if re.match(r"^\s*[\u00b7\u2022]\s", v) or re.match(r"^\s*[\u2460-\u2469]\s", v):
        return "row"
    return OTHER_ROLE


def _func_index():
    """(相对路径, 函数名) -> (槽位集合, 同模块被调函数集合, 行号)"""
    out = {}
    for p in sorted((REPO / "content").rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        src = p.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        rel = p.relative_to(REPO).as_posix()
        mf = {n.name: n for n in tree.body
              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for name, node in mf.items():
            slots, calls = set(), set()
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Call):
                    continue
                fn = sub.func
                nm = fn.id if isinstance(fn, ast.Name) else (
                    fn.attr if isinstance(fn, ast.Attribute) else None)
                if nm in T_CALL:
                    if (sub.args and isinstance(sub.args[0], ast.Constant)
                            and isinstance(sub.args[0].value, str)):
                        slots.add(sub.args[0].value)
                elif nm and nm in mf:
                    calls.add(nm)
            if slots:
                out[(rel, name)] = (slots, calls, node.lineno)
    return out


def _collect(rel, name, funcs, seen=None):
    seen = set() if seen is None else seen
    k = (rel, name)
    if k in seen or k not in funcs:
        return set()
    seen.add(k)
    slots, calls, _ = funcs[k]
    out = set(slots)
    for c in calls:
        out |= _collect(rel, c, funcs, seen)
    return out


def scan(funcs):
    """产出 [(相对路径, 函数名, 行号, 角色, 带图标的, 不带的)]"""
    hits = []
    for (rel, name), info in sorted(funcs.items()):
        allslots = {s for s in _collect(rel, name, funcs) if s in TX}
        if len(allslots) < MIN_ROWS:
            continue
        by_role = {}
        for s in allslots:
            by_role.setdefault(_role(s, _val(s)), []).append(s)
        for role, group in sorted(by_role.items()):
            if role == OTHER_ROLE or len(group) < MIN_ROWS:
                continue
            with_emo = sorted(s for s in group if _has_emo(s))
            without = sorted(s for s in group if not _has_emo(s))
            if with_emo and without:
                hits.append((rel, name, info[2], role, with_emo, without))
    return hits


ok = True


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print(u"  %s %s%s" % (u"\u2713" if cond else u"\u2717", label,
                           (u"  —— %s" % extra) if extra else u""))


print(u"探针：同屏同角色的图标一致性（P2-3）")
funcs = _func_index()
hits = scan(funcs)
_nslot = len(TX)
_nrow = sum(1 for s in TX if s.endswith("_ROW"))
print(u"  · 文案槽位 %d 条 · 带 `_ROW` 的 %d 条 · 抽到槽位的函数 %d 个"
      % (_nslot, _nrow, len(funcs)))

print(u"① 主判据：同屏同角色内，不许「有的带图标、有的不带」")
for rel, fn, line, role, we, wo in hits:
    print(u"  ✗ %s :: %s (L%d) 角色=%s" % (rel, fn, line, role))
    for s in we:
        print(u"      [有] %-26s %s" % (s, _val(s)[:46]))
    for s in wo:
        print(u"      [无] %-26s %s" % (s, _val(s)[:46]))
chk(u"① 同角色同屏的图标不一致 = 0 处", not hits, u"%d 处" % len(hits))

print(u"② 反证（判据有牙）：真盘 0 缺陷时没有现成的「有/无」对可注入 ⇒ "
      u"自己造一个：找一组同角色、**本已全带图标**的行，抽掉其中一行的图标")
_probe = None
for (rel, name), info in sorted(funcs.items()):
    allslots = {x for x in _collect(rel, name, funcs) if x in TX}
    by_role = {}
    for x in allslots:
        by_role.setdefault(_role(x, _val(x)), []).append(x)
    for role, group in sorted(by_role.items()):
        if role == OTHER_ROLE or len(group) < MIN_ROWS:
            continue
        we = [x for x in group if _has_emo(x)]
        if len(we) >= MIN_ROWS:          # 全带图标那一组 ⇒ 抽掉一个就造出不一致
            _probe = (rel, name, role, we[0])
            break
    if _probe:
        break

if not _probe:
    chk(u"② 找得到反证注入点", False, u"★ 判据可能恒绿，请核")
else:
    _rel, _fn, _role_, strip = _probe
    _orig = TX[strip]["value"]
    try:
        TX[strip]["value"] = EMO.sub(u"", _orig, count=1)
        _hits2 = scan(funcs)
        chk(u"② %s::%s（%s）抽掉 %s 的图标 ⇒ 判据当场红（有牙）"
            % (_rel, _fn, _role_, strip), bool(_hits2), u"命中 %d 处" % len(_hits2))
        if _hits2:
            print(u"      反证命中：%s :: %s" % (_hits2[0][0], _hits2[0][1]))
    finally:
        TX[strip]["value"] = _orig
    chk(u"② 还原 ⇒ 红集回到 0（判据没留下残留）", not scan(funcs))

print(u"③ 字形形态：同一 codepoint 不许带/不带 VS16 两种形态并存（P2-6 口径，钉住不回退）")
_mixed = {}
for s in TX:
    v = _val(s)
    for i, ch in enumerate(v):
        o = ord(ch)
        if not (0x2600 <= o <= 0x27BF or 0x2B00 <= o <= 0x2BFF
                or 0x1F000 <= o <= 0x1FAFF):
            continue
        nxt = v[i + 1] if i + 1 < len(v) else u""
        _mixed.setdefault(o, set()).add(nxt == u"️")
_mixed_bad = dict((k, sorted(v)) for k, v in _mixed.items() if len(v) > 1)
for k, v in sorted(_mixed_bad.items()):
    print(u"      U+%04X 形态混用：%s" % (k, v))
chk(u"③ 带/不带 VS16 混用的 codepoint = 0 个", not _mixed_bad, u"%s" % (_mixed_bad,))

print()
print(u"结果：%s" % (u"全绿 ✓" if ok else u"有红 ✗"))
sys.exit(0 if ok else 1)
