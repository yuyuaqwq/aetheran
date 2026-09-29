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
# ★★ 候选**按槽位名排好序**再逐个试（原来直接取 `we[0]`，而 `we` 来自 set 迭代
#   ⇒ 每次跑抽到哪一条随机 ⇒ 同一棵树时红时绿。实测：连跑 5 次红 2 绿 3，
#   `PYTHONHASHSEED=0` 固定后 6/6 全绿 —— 判据没错，是**抽样不确定**）。
#   排序 = 抽样可复现；**逐个试到真会红** = 挑中的那个必定造得出不一致（反证才有牙）。
#   判据只加强：下面每个候选都要真命中才算数，取不到就照旧报「判据可能恒绿」。
_cands = []
for (rel, name), info in sorted(funcs.items()):
    allslots = {x for x in _collect(rel, name, funcs) if x in TX}
    by_role = {}
    for x in sorted(allslots):
        by_role.setdefault(_role(x, _val(x)), []).append(x)
    for role, group in sorted(by_role.items()):
        if role == OTHER_ROLE or len(group) < MIN_ROWS:
            continue
        for x in sorted(group):
            if _has_emo(x):
                _cands.append((rel, name, role, x))
_probe = None
for _c in _cands:
    _r, _n, _ro, _slot = _c
    _keep = TX[_slot]["value"]
    try:
        TX[_slot]["value"] = EMO.sub(u"", _keep, count=1)
        if scan(funcs):
            _probe = _c
            break
    finally:
        TX[_slot]["value"] = _keep

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

# ── ④ 同一屏同一角色的若干行「全都带图标」时，行首锚必须是**同一个** emoji ──
# ① 只判「有的带、有的不带」；skill §7d 的另一种真问题是「同一语义在不同槽位用了不同
# emoji」（例：同屏两条 section_head 分别用 📜 与 🔨）。那一类 ① 结构上抓不到
# （它只看有无，不看是哪一个）⇒ 本条补上，判据只加强、不替代 ①。
# ★ 刻意只对「全带」的组开：既有「有/无」不齐的归 ①，这里只管「带的不是同一个」。
__EMO_FINDALL = set()
for _s in TX:
    __EMO_FINDALL.update(EMO.findall(_val(_s)))


def _lead(v):
    m = EMO.match(v.strip())
    return m.group(0) if m else None


def scan_diff_emo(funcs):
    """产出 [(相对路径, 函数名, 行号, 角色, {emoji: [槽位…]})] —— 同屏同角色全带图标却不同锚。"""
    out = []
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
            ems = {}
            for s in group:
                e = _lead(_val(s))
                if e:
                    ems.setdefault(e, []).append(s)
            # 全带才判（部分带 ⇒ 归 ①）
            if ems and sum(len(v) for v in ems.values()) == len(group) and len(ems) > 1:
                out.append((rel, name, info[2], role, ems))
    return out


print(u"④ 同屏同角色的行**全都带图标**时，行首锚必须是同一个 emoji（① 只判有无，抓不到这一类）")
_diff_hits = scan_diff_emo(funcs)
for rel, fn, line, role, ems in _diff_hits:
    print(u"  ✗ %s :: %s (L%d) 角色=%s" % (rel, fn, line, role))
    for e, ss in sorted(ems.items()):
        print(u"      %s %s" % (e, ss))
        for s in ss:
            print(u"           %-26s %s" % (s, _val(s)[:46]))
chk(u"④ 同屏同角色的行首锚不一致 = 0 处", not _diff_hits, u"%d 处" % len(_diff_hits))

# ④ 的反证：真盘 0 缺陷时没有现成的不一致组 ⇒ 自己造一个 ——
# 找一组「全带且本来同锚」的，把其中一行的锚换成**表里已存在的另一个** emoji。
_p4 = None
for (rel, name), _info in sorted(funcs.items()):
    allslots = {s for s in _collect(rel, name, funcs) if s in TX}
    if len(allslots) < MIN_ROWS:
        continue
    by_role = {}
    for s in allslots:
        by_role.setdefault(_role(s, _val(s)), []).append(s)
    for role, group in sorted(by_role.items()):
        if role == OTHER_ROLE or len(group) < MIN_ROWS:
            continue
        ems = {}
        for s in group:
            e = _lead(_val(s))
            if e:
                ems.setdefault(e, []).append(s)
        if (ems and sum(len(v) for v in ems.values()) == len(group)
                and len(ems) == 1):
            only = list(ems)[0]
            other = next((x for x in sorted(__EMO_FINDALL) if x != only), None)
            if other:
                _p4 = (rel, name, role, group[0], only, other)
                break
    if _p4:
        break

if not _p4:
    chk(u"④ 找得到反证注入点", False, u"★ 判据可能恒绿，请核")
else:
    _rel, _fn, _role_, _strip, _only, _other = _p4
    _orig4 = TX[_strip]["value"]
    try:
        TX[_strip]["value"] = EMO.sub(_other, _orig4, count=1)
        _h4 = scan_diff_emo(funcs)
        chk(u"④ %s::%s（%s）把 %s 的行首锚 %s 换成 %s ⇒ 判据当场红（有牙）"
            % (_rel, _fn, _role_, _strip, _only, _other), bool(_h4), u"命中 %d 处" % len(_h4))
        if _h4:
            print(u"      反证命中：%s :: %s" % (_h4[0][0], _h4[0][1]))
    finally:
        TX[_strip]["value"] = _orig4
    chk(u"④ 还原 ⇒ 红集回到 0（判据没留下残留）", not scan_diff_emo(funcs))

# ── ⑤ 「资源读数行」（label + {a}/{b} 比例、全屏都行尽的那一类）──────────
# ④ 与 ④ 的缺口：那两条采用的 `_role` 把「不带括号、不以 ·/① 起头、不是 _ROW/_HEAD」
# 的行归到 `OTHER_ROLE` ⇒ **结构上就看不到**。但它们是同一屏上相连的两行读数（
# P2-10：`COMBAT_TURN_MP` · ⚡）与 `COMBAT_TURN_RES`（原来 🔹）—— 两行都是「资源读数」一个语义，
# 图标却各用一个，一屏两行读数一个上一个下。
# 定义域现算（不手写名单）：单行且以 `【…】` / 简短标签 + `{a}/{b}` 比例结尾（后面不再有句子）。
# ★ 判据只加强不替代：只对「同屏里全部带图标」的组开（部分带 → 归 ①）；
#   ★ 不钉「emoji 覆盖率」（鱼鱼口径：emoji 少不是缺陷，只判一致性）。
METER = re.compile(u"^\s*\S+\s*(?:【[^】]{0,12}】|\S{1,8}?)?\s*"
                   u"\{[A-Za-z_][\w.:\[\]]*\}/\{[A-Za-z_][\w.:\[\]]*\}\s*$")


def _is_meter(slot):
    return bool(METER.match(_val(slot)))


def scan_meter_emo(funcs):
    """产出 [相对路径, 函数名, {emoji: [槽位…]}] —— 同屏读数行全带图标却不同锚。"""
    out = []
    for (rel, name), info in sorted(funcs.items()):
        allslots = {s for s in _collect(rel, name, funcs) if s in TX}
        grp = [s for s in allslots if _is_meter(s)]
        if len(grp) < 2:
            continue
        ems = {}
        for s in grp:
            e = _lead(_val(s))
            if e:
                ems.setdefault(e, []).append(s)
        if ems and sum(len(v) for v in ems.values()) == len(grp) and len(ems) > 1:
            out.append((rel, name, info[2], ems))
    return out


print(u"⑤ 同屏里那几行「资源读数」（label + 比例）全部带图标时，"
      u"行首锚必须是同一个 emoji（①④都归 OTHER_ROLE，结构上看不到这一类）")
_meter_hits = scan_meter_emo(funcs)
for rel, fn, line, ems in _meter_hits:
    print(u"  ✗ %s :: %s (L%d)" % (rel, fn, line))
    for e, ss in sorted(ems.items()):
        print(u"      %s %s" % (e, ss))
        for s in ss:
            print(u"           %-26s %s" % (s, _val(s)[:46]))
chk(u"⑤ 同屏资源读数行的行首锚不一致 = 0 处", not _meter_hits,
    u"%d 处" % len(_meter_hits))

# ⑤ 的反证：真盘 0 缺陷时没有现成的不一致组 ⇒ 自己造一个——
# 找一组「本来同锚」的读数行，把其中一行的锚换成**表里已存在的另一个** emoji。
_p5 = None
for (rel, name), info in sorted(funcs.items()):
    allslots = {s for s in _collect(rel, name, funcs) if s in TX}
    grp = [s for s in allslots if _is_meter(s)]
    if len(grp) < 2:
        continue
    ems = {}
    for s in grp:
        e = _lead(_val(s))
        if e:
            ems.setdefault(e, []).append(s)
    if ems and len(ems) == 1 and sum(len(v) for v in ems.values()) == len(grp):
        _p5 = (rel, name, list(ems)[0], grp[0])
        break
if not _p5:
    chk(u"⑤ 找得到反证注入点", False, u"★ 判据可能恒绿，请核")
else:
    _rel, _fn, _only, _strip = _p5
    _other = next((x for x in sorted(__EMO_FINDALL) if x != _only), None)
    if not _other:
        chk(u"⑤ 反证用 emoji 得到", False, u"★ 表里只有一种行首锚")
    else:
        _orig5 = TX[_strip]["value"]
        try:
            TX[_strip]["value"] = EMO.sub(_other, _orig5, count=1)
            _h5 = scan_meter_emo(funcs)
            chk(u"⑤ %s::%s 把 %s 的行首锚 %s 换成 %s ⇒ 判据当场红（有牙）"
                % (_rel, _fn, _strip, _only, _other), bool(_h5), u"命中 %d 处" % len(_h5))
        finally:
            TX[_strip]["value"] = _orig5
        chk(u"⑤ 还原 ⇒ 红集回到 0（判据没留下残留）", not scan_meter_emo(funcs))

print()
# ── ⑥ 「物品事务结果行」（行首形如 `{icon}{name}` 那一族）────────────────────
# P2-11：全包里「动作成了」的结果行分两拨 —— 买/卖/丢/存取/打造都有行首语义锚（💰🗑️📦🔨），
# 而穿上/卸下/换手/做饭那四条只是 `{icon}{name}` 起头 —— 那个 `{icon}` 是**物品自己的图标**
# （内容数据的 icon 字段），不是行首锚；玩家一屏里两种子写法不一致。
# 定义域现算（不手写名单）：行首形如 `{icon}{name}`（物品图标与名字相邻）。
# ★ 不钉「emoji 覆盖率」（鱼鱼口径：emoji 少不是缺陷，只判一致性）——
#   本条只判「同族结果行行首锚不统一」；归一组里部分行本来就没锚时，不开此依据。
ITEM_ICON_PAIR = re.compile(r"\{icon\}\{name\}")


def _is_item_row(slot):
    return bool(ITEM_ICON_PAIR.search(_val(slot)))


def scan_item_anchor(funcs):
    """产出 [相对路径, 函数名, 行号, {emoji: [槽位…]}] —— 同屏物品事务结果行锚不统一。"""
    out = []
    for (rel, name), info in sorted(funcs.items()):
        allslots = {s for s in _collect(rel, name, funcs) if s in TX}
        grp = [s for s in allslots if _is_item_row(s)]
        if len(grp) < 2:
            continue
        ems = {}
        for s in grp:
            e = _lead(_val(s))
            if e:
                ems.setdefault(e, []).append(s)
        if ems and sum(len(v) for v in ems.values()) == len(grp) and len(ems) > 1:
            out.append((rel, name, info[2], ems))
    return out


print(u"⑥ 同屏里那几行「物品事务的结果」（行首形如 {icon}{name}）")
print(u"  · 定义域现算：分屏上落到 {icon}{name} 的槽位")
_item_hits = scan_item_anchor(funcs)
chk(u"⑥ 同屏物品事务结果行的行首锚不一致 = 0 处", not _item_hits,
    u"" if not _item_hits
    else u"\n".join(u"      %s::%s %s" % (h[0], h[1], h[3]) for h in _item_hits))

# ⑥ 的反证：真盘 0 缺陷时没现成的不一致组 ⇒ 自己造一个（抽掉某一行锚，与 ④ 同法）。
_p6 = None
for (rel, name), info in sorted(funcs.items()):
    allslots = {x for x in _collect(rel, name, funcs) if x in TX}
    grp = [x for x in allslots if _is_item_row(x)]
    if len(grp) < 2:
        continue
    ems = {}
    for x in grp:
        e = _lead(_val(x))
        if e:
            ems.setdefault(e, []).append(x)
    if len(ems) == 1 and sum(len(v) for v in ems.values()) == len(grp):
        _p6 = (rel, name, list(ems)[0], grp[0])
        break
if not _p6:
    chk(u"⑥ 找得到反证注入点", False, u"★ 判据可能恒绿，请核")
else:
    _rel6, _fn6, _only6, _strip6 = _p6
    _other6 = next((x for x in sorted(__EMO_FINDALL) if x != _only6), None)
    if not _other6:
        chk(u"⑥ 反证用 emoji 得到", False, u"表里只有一种行首锚")
    else:
        _orig6 = TX[_strip6]["value"]
        try:
            TX[_strip6]["value"] = EMO.sub(_other6, _orig6, count=1)
            _h6 = scan_item_anchor(funcs)
            chk(u"⑥ %s::%s 把 %s 的行首锚 %s 换成 %s ⇒ 判据当场红（有牙）"
                % (_rel6, _fn6, _strip6, _only6, _other6), bool(_h6), u"命中 %d 处" % len(_h6))
        finally:
            TX[_strip6]["value"] = _orig6
        chk(u"⑥ 还原 ⇒ 红集回到 0（判据没留下残留）", not scan_item_anchor(funcs))

print(u"结果：%s" % (u"全绿 ✓" if ok else u"有红 ✗"))
sys.exit(0 if ok else 1)
