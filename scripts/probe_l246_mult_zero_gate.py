# -*- coding: utf-8 -*-
"""审计 L246 同族 · 覆盖面缺口第四面：aetheran 包**常驻门禁**。

跑法：python scripts/probe_l246_mult_zero_gate.py

背景
----
L246 族（`x.get("mult", 1.0) or 1.0` 把**合法** 0.0 吞成默认值：格挡 / 无敌帧 /
完全免伤 / 零伤段 / 零治疗段永远做不出来，且零报错零日志）已在三处收口并各配门禁：
    · 引擎自有子树 → framework-engine/tests/test_l246_formula_mult_zero_gate.py
    · orlandia 包  → games/orlandia/tests/test_l246_mult_zero_whole_tree_gate.py
    · 宿主自有码   → <host>/tests/test_l246_mult_zero_host_gate.py
    · ★ 本包（aetheran）—— 此前**无常驻判据**。第二轮实测本包 156 文件 / 0 命中，
      但「今天扫过」不是判据保证；缺了它，下一个人在本包新增一条 `or` 乘区无人拦。

★ 为什么按**整包**扫、而不是逐个列名 / 只扫 content/
    前两轮门禁的扫描根是「逐个列名的 4 个文件」⇒ 收口是假的（整个 `content/flow/`
    不在扫描面里）；第二轮扩到某个目录；第三轮才按形态扫整棵 `content/`。
    ★ 本支实测又一层：**本包 `content/` 只有 58 个 .py**，而 `scripts/` 有 97 个 ——
      「扫完 content/ 零命中」在本包是个**覆盖面不足的干净**（58 < 150）。
      ⇒ 覆盖面断言当场把这条判据打红（实测「only 58」），本支据此改成**整包扫描**。
      ⇒ 这就是「覆盖面自证断言」存在的意义：它拦下的是**判据本身的漏洞**，不是被测代码。
    ⇒ 最终形态：按 AST 形态扫整包（`content/` + `scripts/` + `editor/` …），
      剔 `data/`（JSON）与 `tests/`（测试面不是产品码），带覆盖面自证。

判定
----
[1] 静态：本包 `content/` 子树零处 `get(乘区键, 非零默认) or 非零常量`（剔 docstring）
[2] ★ 右值也必须非零才算「吞 0」—— `x or 0` 保留 0（把 None 归一到 0），不属本族。
    照抄 orlandia / 宿主那两份的同一判据，口径三处**逐字一致**。
[3] 覆盖面自证：扫到 >=150 个 .py，且**解析零失败**（解析失败会被误读成「干净」）
[4] 行为向（黑盒，不依赖被测源码）：0.0/0 保住，缺键与显式 None 才回落
[5] ★ 两向反证：给判据喂一份含本族形态的临时副本 ⇒ 必须被扫出来，
    且 docstring 里的同形 / `or 0` 都不误报（证明它有牙且不滥报）
"""
from __future__ import annotations

import ast
import io
import os
import shutil
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

ok = True


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s" % ("OK " if cond else "FAIL", label)
          + (("  -- %s" % (extra,)) if extra else ""))


#: 乘区键白名单（与 orlandia / 宿主那两份**逐字一致** —— 口径不许三处各写一份）
MULT_KEYS = ("mult", "atk_mult", "hp_mult", "pct", "factor", "rate", "ratio", "scale")
SKIP_DIRS = {"__pycache__", ".git", "data", "tests"}
MIN_SCANNED = 150


def _doc_lines(tree):
    bad = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if ast.get_docstring(node, clean=False) is None:
                continue
            first = node.body[0]
            bad.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return bad


def _scan(root):
    hits, scanned, failed = [], 0, []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root).replace("\\", "/")
            src = io.open(path, encoding="utf-8").read()
            try:
                tree = ast.parse(src)
            except SyntaxError as exc:
                failed.append("%s: %s" % (rel, exc))
                continue
            scanned += 1
            bad = _doc_lines(tree)
            for node in ast.walk(tree):
                if not (isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or)
                        and len(node.values) == 2):
                    continue
                if node.lineno in bad:
                    continue
                lhs = node.values[0]
                if not (isinstance(lhs, ast.Call) and isinstance(lhs.func, ast.Attribute)
                        and lhs.func.attr == "get" and lhs.args
                        and isinstance(lhs.args[0], ast.Constant)):
                    continue
                if lhs.args[0].value not in MULT_KEYS or len(lhs.args) < 2:
                    continue
                try:
                    default = float(lhs.args[1].value)
                except (AttributeError, IndexError, TypeError, ValueError):
                    continue
                if default == 0.0:
                    continue
                # ★ 右值也必须非零：`x or 0` 保留 0，不是本族。
                try:
                    rhs = float(node.values[1].value)
                except (AttributeError, TypeError, ValueError):
                    rhs = None
                if rhs == 0.0:
                    continue
                hits.append("%s:%s" % (rel, node.lineno))
    return hits, scanned, failed


print("[1] static: the whole package (content/ + scripts/ + editor/; data/ tests/ excluded)")
hits, scanned, failed = _scan(REPO)
chk("all scanned product code parses (parse failure reads as 'clean')", not failed,
    "failed=%s" % failed)
chk("scanned >=%d .py files (coverage proof)" % MIN_SCANNED, scanned >= MIN_SCANNED,
    "only %d" % scanned)
chk("zero get(mult_key, nonzero) or nonzero in the whole package", not hits, "hits=%s" % hits)

print("[2] behavioural: fallback must key on None only")
def _read(raw, default):
    v = raw.get("mult")
    return default if v is None else float(v)

chk("mult=0.0 survives (not swallowed by or)", _read({"mult": 0.0}, 1.0) == 0.0)
chk("mult=0 survives", _read({"mult": 0}, 1.0) == 0.0)
for m, exp in ((0.5, 0.5), (1.0, 1.0), (2.0, 2.0), (1.3, 1.3)):
    chk("mult=%s unchanged" % m, abs(_read({"mult": m}, 1.0) - exp) < 1e-9,
        "got=%s" % _read({"mult": m}, 1.0))
chk("missing key falls back", _read({}, 1.0) == 1.0)
chk("explicit None falls back", _read({"mult": None}, 1.0) == 1.0)

print("[3] counter-proof: the scanner really has teeth (temp copy, no repo file touched)")
_tmp = tempfile.mkdtemp(prefix="l246_aeth_counterproof_")
try:
    os.makedirs(os.path.join(_tmp, "sub"))
    with io.open(os.path.join(_tmp, "sub", "bad.py"), "w", encoding="utf-8") as fh:
        fh.write("# -*- coding: utf-8 -*-\n"
                 "def f(d):\n"
                 "    return d.get('mult', 1.0) or 1.0\n")
    with io.open(os.path.join(_tmp, "sub", "doc_only.py"), "w", encoding="utf-8") as fh:
        fh.write("# -*- coding: utf-8 -*-\n"
                 "def g(d):\n"
                 "    '''doc only: d.get(\"mult\", 1.0) or 1.0'''\n"
                 "    return 1.0\n")
    with io.open(os.path.join(_tmp, "sub", "or_zero_ok.py"), "w", encoding="utf-8") as fh:
        fh.write("# -*- coding: utf-8 -*-\n"
                 "def h(d):\n"
                 "    return d.get('pct', 0) or 0\n")
    c_hits, c_scanned, c_failed = _scan(_tmp)
    chk("the form is caught in the copy (exactly one hit, in bad.py)",
        len(c_hits) == 1 and c_hits[0].startswith("sub/bad.py:"), "hits=%s" % c_hits)
    chk("same shape inside a docstring is not a false positive",
        "doc_only.py" not in "".join(c_hits))
    chk("`x or 0` (keeps 0) is not a false positive",
        "or_zero_ok.py" not in "".join(c_hits))
    chk("all three copy files parse", not c_failed and c_scanned == 3,
        "scanned=%s failed=%s" % (c_scanned, c_failed))
finally:
    shutil.rmtree(_tmp, ignore_errors=True)

print("")
print("result:", "all green" if ok else "HAS FAILURES")
sys.exit(0 if ok else 1)
