# -*- coding: utf-8 -*-
"""探针：`battle_acts.Hand` 那个 `ok` 字段已删（审计 L1102 · 只写不读的死字段）。

台账原文：「`battle_acts.py:209,238,273` 的 `Hand.ok` 写 3 处、**读 0 处**」——
本探针把这个「读 0 处」钉成常驻判据，防下一个人把它写回来（它那行注释曾自称
「探针/回话用」，而全包零读点 ⇒ 那句话是**说谎的**，也正是它一直没人销号的原因）。

★ 本探针**刻意不装配**（不 `load_stack`）：`Hand` 只依赖 `ext_combat`，与那条正在
  收口的公式变量表回归（`F1_eff_def` 引用未声明的 `pene_flat`/`pene_pct`）无关，
  刻意不碰那条路，本探针就能一直跑。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_hand_ok_removed.py
"""
from __future__ import annotations

import ast
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, REPO)
sys.path.insert(0, ENGINE)
sys.path.insert(0, os.path.join(ENGINE, "extends"))

SRC = os.path.join(REPO, "content", "battle_acts.py")

fails = []
ok = lambda m: print("  ✓ " + m)
bad = lambda m: (fails.append(m), print("  ✗ " + m))
chk = lambda label, cond, extra="": (ok if cond else bad)(
    label + (("  —— %s" % extra) if extra else ""))

import content.battle_acts as BA                                             # noqa: E402

# ───────────────────────────────────────────── 一、真建一个 Hand，看它有没有那一格
print("一、实例上的字段（真建对象，不读源码）")
# ★ 审计残余 #16：interrupt 档 `p` 必填（fail-closed）—— 本探针只看字段面，给最小档。
h = BA.Hand("interrupt", p={"uid": "u1"})
attrs = sorted(vars(h))
chk("★ `Hand('interrupt')` 上没有 `ok` 那一格", not hasattr(h, "ok"), attrs)
# ★ 2026-09-30 收红批二：`slot_kw` 是 P0-1 续批五（ca04636）**有意**加的第六格
#   （未渲染的槽位实参 —— 给「要带【N 刻】」那一格用，渲染推迟到 override）。
#   清单随之五格 → 六格；仍然**精确相等**（防删防乱加，判据只紧不松）。
chk("★ 原有六格一件不少（kind/p/item/lines/slot_kw/used）",
    attrs == ["item", "kind", "lines", "p", "slot_kw", "used"], attrs)
chk("★ 零个字段名含 ok 那一族（防改名绕开这条判据）",
    not [a for a in attrs if a.lower() in ("ok", "is_ok", "success", "succeed", "done")], attrs)

# ───────────────────────────────────────────── 二、四种 kind 都不许长出那一格
print("二、四种 kind 逐个建一遍")
for k in ("interrupt", "item", "swap", "retreat"):
    hk = BA.Hand(k, p={"uid": "u1"}, item="x", lines=["l"], used={"x": 0})
    chk("★ kind=%-9s 同样没有 `ok`" % k, not hasattr(hk, "ok"))

# ───────────────────────────────────────────── 三、源码面：写点/读点都归零
print("三、源码面（AST，不靠 grep 的字面量运气）")
src = io_src = open(SRC, encoding="utf-8").read()
tree = ast.parse(src)
writes, reads = [], []
for n in ast.walk(tree):
    if isinstance(n, ast.Attribute) and n.attr == "ok":
        seg = ast.get_source_segment(src, n) or ""
        (writes if "=" in seg and seg.rstrip().split("=")[0].rstrip().endswith("ok") else reads).append(n.lineno)
chk("★ 文件里 `self.ok = …` 的**写点** 0 个", not writes, "行 %s" % writes)
chk("★ 文件里 `.ok` 的**读点** 0 个", not reads, "行 %s" % reads)
# ★ 刻意**剥掉所有 docstring/注释**再 grep：判据要盯的是「代码里有没有那一格」,
#   而第四节那份 docstring 正当要提到 `self.ok`（它记的就是这段历史）⇒ 不剥就恒红。
_TRIPLE = re.compile(r"(\"\"\"|''')[\s\S]*?\1")
_code = _TRIPLE.sub("", src)          # 去三引号块（docstring）
_code = re.sub(r"#[^\n]*", "", _code)  # 去行注释
chk("★ 剥掉 docstring/注释后字面 grep 同样 0 命中（AST 判据之外的第二道）",
    not re.search(r"\bok\b", _code), re.findall(r".*\bok\b.*", _code)[:3])

# ───────────────────────────────────────────── 四、类 docstring 记下了「为什么没有」
print("四、为什么没有它（写进 docstring，防下一个人写回来）")
doc = ast.get_docstring(next(n for n in ast.walk(tree)
                             if isinstance(n, ast.ClassDef) and n.name == "Hand")) or ""
chk("★ docstring 点名 `self.ok` 这段历史（含删掉的理由）", "self.ok" in doc and "L1102" in doc)
chk("★ docstring 指明回执该读 `override` 的返回值（给出替代口径）",
    "override" in doc and "logs" in doc)

# ───────────────────────────────────────────── 五、反证：模拟「写回来」，判据必须变红
print("五、反证（判据有牙吗）—— 手工把那一格塞回去，看上面哪几格会红")
class _Back(BA.Hand):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.ok = False                                   # ← 模拟有人写回来
_h2 = _Back("interrupt", p={"uid": "u1"})   # ★ 审计残余 #16：interrupt 档 p 必填（反证节同样要给）
chk("★ 一个长出 `ok` 的子类确实被第①节那格逮到（不是恒真断言）", hasattr(_h2, "ok"))

print("结果：%s" % ("全绿 ✓" if not fails else "有红 ✗"))
print("（%d 红）" % len(fails))
sys.exit(0 if not fails else 1)
