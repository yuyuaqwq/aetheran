# -*- coding: utf-8 -*-
"""探针：races 域读得到 · 六族形状对（2 正 1 负 · 至少一条可见性）· 数值天赋值域合理。

⑪ ★ P-60（本波 w5）：`home` / `lifespan` 两格 —— 数据都在 · 今天 0 读端 · 真源也没有要求
   显示它的口 ⇒ **只登记不接**（谁把它接到某个呈现口上，这条当场红）。

用法（在 aetheran-package 仓根跑）：
    GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_races.py
"""
from __future__ import annotations

import json
import io
import os
import time
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402

ok = True
KINDS = ("可见性", "数值", "经济")


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


print("探针：races 域（六族天赋）")
st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
st.install()

# ① 域读得到
rc = st.domain("races")
chk("races 域读得到", rc is not None, "%d 族" % (len(rc) if rc else 0))
if not rc:
    sys.exit(1)

# ② 六族
chk("六族齐全", len(rc) == 6, " · ".join(v["name"] for v in rc.values()))

# ③ 每族 2 正 1 负
bad = [k for k, v in rc.items() if len(v.get("talents", [])) != 2 or not v.get("cost")]
chk("每族 2 条正天赋 + 1 条负代价", not bad, "例外：%s" % bad if bad else "")

# ④ ★ 品味判据：每族正向里至少一条「可见性」
bad4 = [k for k, v in rc.items()
        if not any(t.get("kind") == "可见性" for t in v.get("talents", []))]
chk("★ 每族至少一条「可见性」正天赋", not bad4, "缺：%s" % bad4 if bad4 else "")

# ⑤ kind 合法
bad5 = []
for k, v in rc.items():
    for t in list(v.get("talents", [])) + [v.get("cost")]:
        if t and t.get("kind") not in KINDS:
            bad5.append("%s/%s=%s" % (k, t.get("id"), t.get("kind")))
chk("天赋类型合法（可见性/数值/经济）", not bad5, " · ".join(bad5))

# ⑥ id 唯一
ids = []
for k, v in rc.items():
    ids.append(k)
    ids += [t["id"] for t in v.get("talents", [])]
    ids.append(v["cost"]["id"])
chk("id 全局唯一", len(ids) == len(set(ids)), "%d 个 id" % len(ids))

# ⑦ 六句「为什么来」各不相同
lines = [v.get("line", "") for v in rc.values()]
chk("六句「为什么来」互不相同", len(set(lines)) == 6 and all(lines))

# ⑧ 数值类天赋的 values 值域（百分比 ±25 内）
bad8 = []
for k, v in rc.items():
    for t in list(v.get("talents", [])) + [v.get("cost")]:
        for key, val in (t or {}).get("values", {}).items():
            if "pct" in key and not (-25 <= val <= 25):
                bad8.append("%s.%s=%s" % (t["id"], key, val))
chk("数值类天赋百分比在 ±25 内", not bad8, " · ".join(bad8))

# ⑨ schema 在
sch = REPO / "schemas/races.schema.json"
chk("races.schema.json 在位", sch.exists(), str(sch.name))

# ⑩ 通路与反面都写了（设计判据：每族一条别人走不了的路 + 一条真的疼的代价）
bad10 = [k for k, v in rc.items() if not v.get("path") or not v.get("flip")]
chk("每族都写了「专属通路 + 反面」", not bad10, "缺：%s" % bad10 if bad10 else "")

# ⑪ ★ P-60（2026-09-26 · 本波 w5 · 顺带核 `races.home/lifespan` 有没有该显示的口）—— **登记档**
#   六族数据里都有 `home`（家乡）与 `lifespan`（寿数）两格；可真源里**没有一处**要求把它们
#   显示出来（`06_第一阶段垂直切片/04_指令总表 §三` 的 `出身` 只写「族 + 那一句为什么来」；
#   全仓 grep「寿数 / 家乡」零命中）⇒ 今天**不接**（往界面加 = 自己编口径），只登记：
#   这两格是**留给编辑器 / 下一阶段的形状**。判据 = K80 的自检问题「这两格，哪一行代码在读它？」
bad11 = [k for k, v in rc.items() if not v.get("home") or not v.get("lifespan")]
chk("★ P-60 · 六族的 `home` / `lifespan` 两格数据都在 —— %s"
    % " · ".join("%s=%s／%s" % (v["name"], v["home"], v["lifespan"]) for v in rc.values()),
    not bad11, "缺：%s" % bad11 if bad11 else "")
_READERS11 = []
# ★ 覆盖面要跟判据一起加（K61）：不只 `content/*.py` —— content 递归 + scripts + editor 全扫
#   （本探针自己除外：这几行注释与判据本来就写着这两个词）。「哪一行代码在读它？」要问全仓。
for _f11 in (sorted((REPO / "content").rglob("*.py")) + sorted((REPO / "scripts").glob("*.py"))
             + sorted((REPO / "editor").rglob("*"))):
    if not _f11.is_file() or _f11.name == "probe_races.py" or "__pycache__" in str(_f11):
        continue
    try:
        _t11 = _f11.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        continue
    _READERS11 += ["%s:%s" % (_f11.relative_to(REPO), _kw)
                   for _kw in ('"home"', "'home'", '"lifespan"', "'lifespan'") if _kw in _t11]
chk("★ P-60 · 登记：`home` / `lifespan` 今天**一个读端都没有**"
    "（content/ 递归 + scripts/ + editor/ 全扫 · 0 命中）"
    "—— 真源也没有要求显示它的口 ⇒ 不接、只登记；谁把它们接到某个呈现口上（没先改真源），这里当场红",
    not _READERS11, "%s" % _READERS11)
# 登记的另一半依据（真源那侧）：`04_指令总表 §三` 的 `出身` 只写「族 + 那为什么来」——
# 真源里**没有** home / lifespan 的位置。哪天真源定了「它出现在哪一屏」，这条当场红（提醒回来接上）。
_L11, _TAIL11 = [], os.environ.get("AST_PLAN", "C:/Users/yuyu/aetheran-plan")
_DOC0411 = os.path.join(_TAIL11, "06_第一阶段垂直切片", "04_指令总表.md")
if os.path.exists(_DOC0411):
    with io.open(_DOC0411, encoding="utf-8") as _fh11:
        _L11 = [_ln.strip() for _ln in _fh11 if "出身" in _ln and "|" in _ln]
chk("★ P-60 · 真源里也没有这个显示口（04 §三 `出身` 那一行 = %s）—— 往界面加 = 自己编口径 ⇒ "
    "登记不接；真源定了它出现在哪一屏再回来接"
    % ((_L11[0][:80]) if _L11 else "（没解析到）"),
    bool(_L11) and all("家乡" not in _ln and "寿数" not in _ln for _ln in _L11)
    and all("族" in _ln and "为什么来" in _ln for _ln in _L11))

print()
print("六族速览：")
for k, v in rc.items():
    plus = " · ".join("%s(%s)" % (t["name"], t["kind"]) for t in v["talents"])
    print("  %-16s %s  →  正：%s ｜ 负：%s(%s)" % (
        k, v["name"], plus, v["cost"]["name"], v["cost"]["kind"]))

print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
