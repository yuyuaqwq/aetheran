# -*- coding: utf-8 -*-
"""可读物量账的**唯一解析口**（12 类）—— 探针与生成器共用这一份，谁都不许再手打那个数。

为什么要有这一份：`12` 这个数在**五处**出现，四处是文档、一处是域里现算 ——

```text
10 §一A   地图元素库「读东西」那一类（编号 1–12）           → 12 种
19 §三A   第一阶段铺的读东西（已定 3 类 + 该扩 9 类）        → 12 条（每条钉在一处地点）
21 §一    称号「认得三种字的人」的「怎么拿到」：读完全部 12 类 → 12
16 §二    称号条件 `read_all>=12`                          → 12
域里      pois 里 into_codex 的条数 = 旧物谱（读的）条数      → 现算
```

★ 五处只要有一处跟别处不一样，就是「**两个数各说一套**」—— 本模块把它们**现解析**出来
  逐处比对；探针拿 `audit()` 的 `bad` 直接报红，生成器拿 `assert_agree()` 当场抛。

★ 为什么对账只能对**条数**、不能对名字：10 §一A 的 12 种与 19 §三A 的 12 条**不是同一批**
  （10 有「地图残片」没「水下的石阶」，19 反过来），而 14 §五 旧物谱那 12 条的名字
  又只有 6 条与 19 的类名同名/包含 ⇒ 强行逐名对账会一路红。**数目一致**才是这里要盯的东西。

真源（只读）：
  aetheran-plan/06_第一阶段垂直切片/10_地图探索元素库_v1.md   §一 A · 读东西
  aetheran-plan/06_第一阶段垂直切片/19_世界热闹度与可发现物_v1.md §三 A
  aetheran-plan/06_第一阶段垂直切片/21_长期目标层_v1.md        §一 称号表
  aetheran-plan/00_总纲/16_称号域口径_v1.md                    §二 条件表
"""
from __future__ import annotations

import io
import os
import re
import sys

PLAN = (os.environ.get("AST_PLAN") or os.environ.get("AETHERAN_PLAN")
        or "C:/Users/yuyu/aetheran-plan")

DOC10 = os.path.join(PLAN, "06_第一阶段垂直切片", "10_地图探索元素库_v1.md")
DOC19 = os.path.join(PLAN, "06_第一阶段垂直切片", "19_世界热闹度与可发现物_v1.md")
DOC21 = os.path.join(PLAN, "06_第一阶段垂直切片", "21_长期目标层_v1.md")
DOC16 = os.path.join(PLAN, "00_总纲", "16_称号域口径_v1.md")
DOC22 = os.path.join(PLAN, "06_第一阶段垂直切片", "22_旧哨塔_逐间设计_v1.md")

CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"


def rd(path: str) -> str:
    with io.open(path, encoding="utf-8", newline="") as f:
        return f.read()


def _section(text: str, pattern: str, where: str) -> str:
    """取一个 `### …` 小节的正文（到下一个 `###` 为止）。"""
    m = re.search(pattern, text, re.M)
    if not m:
        raise SystemExit("解析不到小节：%s（模式 %s）" % (where, pattern))
    body = text[m.end():]
    nxt = re.search(r"^###\s", body, re.M)
    return body[:nxt.start()] if nxt else body


def kinds_10(text: str) -> list:
    """10 §一A「读东西」那 12 种 → [(编号, 名字), …]（现数，编号要 1–12 连号）。"""
    body = _section(text, r"^###\s*A\s*[·.]\s*读东西.*$", "10 §一A 读东西")
    out = [(int(n), nm) for n, nm in re.findall(r"^\s*(\d+)\s+(\S+)", body, re.M)]
    if [n for n, _ in out] != list(range(1, len(out) + 1)) or not out:
        raise SystemExit("10 §一A 的编号不是 1..N 连号：%s" % [n for n, _ in out])
    return out


def kinds_19(text: str) -> dict:
    """19 §三A（已定 3 类 + 该扩 9 类）→ 与文档自己写的那两个数逐一对账。"""
    body = _section(text, r"^###\s*A\s*[.·]\s*读东西.*$", "19 §三A 读东西")
    m = re.search(r"已定\s*(\d+)\s*类\s*(.+)", body)
    if not m:
        raise SystemExit("19 §三A 少了「已定 N 类」那一行")
    fixed_n, fixed = int(m.group(1)), [x.strip() for x in m.group(2).split("·") if x.strip()]
    if len(fixed) != fixed_n:
        raise SystemExit("19 §三A 写着「已定 %d 类」，实际列了 %d 个：%s" % (fixed_n, len(fixed), fixed))
    m2 = re.search(r"该扩的\s*(\d+)\s*类", body)
    if not m2:
        raise SystemExit("19 §三A 少了「该扩的 N 类」那一行")
    expand_n = int(m2.group(1))
    items = re.findall(r"^\s*([%s])\s+(\S+)" % CIRCLED, body, re.M)
    if len(items) != expand_n:
        raise SystemExit("19 §三A 写着「该扩的 %d 类」，实际列了 %d 个" % (expand_n, len(items)))
    return {"fixed": fixed, "fixed_n": fixed_n, "expand": [nm for _c, nm in items], "expand_n": expand_n}


def tower_reads(text: str) -> dict:
    """22 §一 总览表「可读物」那一列 → 塔内那 9 项（`·` / `+` 分开，`——` 不算）。

    ★ 这一列是**「这一间能读/能看的东西」**，不等于四谱口径里的「可读物」：
      其中 3 项（墙上的划痕 / 拾荒人留的字条 / 没寄出的信）在旧物谱（读的）里，
      其余 6 项是**就地线索**（22 §二「可做」列）—— 本批的裁决就是这一条（见 `_notes.md`）。
    """
    rows = []
    for ln in text.split("\n"):
        s = ln.strip()
        if not s.startswith("|"):
            continue
        cs = [c.strip().replace("**", "").replace("`", "") for c in s.strip("|").split("|")]
        if len(cs) != 5 or cs[0] not in ("一", "二", "三"):
            continue
        m = re.match(r"^(\d+)\s+(.+)$", cs[1])
        if not m:
            continue
        room = re.split(r"\s*——\s*", m.group(2))[0].strip()
        cell = re.sub(r"（[^）]*）", "", cs[4])
        for x in re.split(r"[·+]", cell):
            nm = x.strip()
            if nm and nm != "——":
                rows.append((room, nm))
    return {"rows": rows, "names": [nm for _r, nm in rows], "n": len(rows)}


def title_21(text: str) -> int:
    """21 §一 称号表里那句「读完全部 N 类可读物」的 N。"""
    m = re.search(r"读完全部\s*(\d+)\s*类可读物", text)
    if not m:
        raise SystemExit("21 §一 里找不到「读完全部 N 类可读物」那一格")
    return int(m.group(1))


def title_16(text: str) -> int:
    """16 §二 条件表里 `read_all>=N` 的 N（只许有一个取值）。"""
    got = sorted({int(x) for x in re.findall(r"read_all\s*>=\s*(\d+)", text)})
    if len(got) != 1:
        raise SystemExit("16 §二 的 read_all 门槛不是唯一一个数：%s" % got)
    return got[0]


def docs() -> dict:
    """四处文档现解析（缺文件当场抛 —— fail-closed，不拿默认值顶上）。"""
    k10 = kinds_10(rd(DOC10))
    k19 = kinds_19(rd(DOC19))
    return {
        "10": len(k10), "10_names": [nm for _n, nm in k10],
        "19_fixed": k19["fixed_n"], "19_expand": k19["expand_n"],
        "19_names": k19["fixed"] + k19["expand"],
        "21": title_21(rd(DOC21)),
        "16": title_16(rd(DOC16)),
    }


def audit(pois: dict | None = None, relic_read=None, titles: dict | None = None) -> dict:
    """文档四处 + 域里现算 → `{"n": 12, "doc": {…}, "live": {…}, "bad": [一句人话…]}`。

    探针侧：把 `bad` 挂到一条 `chk()` 上（一条判据管住五处）。
    生成器侧：`assert_agree()` 直接抛。
    """
    d = docs()
    bad = []
    four = {"10 §一A": d["10"], "19 §三A": d["19_fixed"] + d["19_expand"],
            "21 §一": d["21"], "16 §二": d["16"]}
    if len(set(four.values())) != 1:
        bad.append("文档里那几个数不一样：%s" % four)
    n = sorted(four.values())[0]
    live = {}
    if pois is not None:
        live["pois.into_codex"] = len([1 for v in pois.values() if v.get("into_codex")])
        if live["pois.into_codex"] != n:
            bad.append("pois 里 into_codex 有 %d 条，文档说是 %d 类" % (live["pois.into_codex"], n))
    if relic_read is not None:
        live["codex.relic[from=read]"] = len(list(relic_read))
        if live["codex.relic[from=read]"] != n:
            bad.append("旧物谱（读的）有 %d 条，文档说是 %d 类" % (live["codex.relic[from=read]"], n))
    if titles:
        vals = sorted({int(val) for k, rec in titles.items() if not str(k).startswith("_")
                       for _f, val, _t in _read_all_vals((rec or {}).get("cond") or {})})
        if vals:
            live["titles.read_all"] = vals
            if vals != [n]:
                bad.append("titles 里 read_all 的门槛是 %s，文档说是 %d" % (vals, n))
    return {"n": n, "doc": d, "live": live, "bad": bad}


def _read_all_vals(node):
    """从 titles 的条件声明节点里挖出 `read_all>=N` 那几处。"""
    out = []
    if not isinstance(node, dict):
        return out
    op = node.get("op")
    if op == "ge":
        steps = ((node.get("left") or {}).get("field") or [])
        if steps and steps[0].get("key") == "read_all":
            out.append(("read_all", (node.get("right") or {}).get("const"), None))
    for a in node.get("args") or []:
        out += _read_all_vals(a)
    sub = node.get("arg")
    if isinstance(sub, dict):
        out += _read_all_vals(sub)
    return out


def assert_agree(pois=None, relic_read=None, titles=None) -> int:
    """生成器侧：对不上当场抛（不写任何东西）。"""
    r = audit(pois=pois, relic_read=relic_read, titles=titles)
    if r["bad"]:
        raise SystemExit("可读物那个数对不上（%s）—— 先裁决再落：%s"
                         % (r["doc"], "；".join(r["bad"])))
    return r["n"]


if __name__ == "__main__":                       # 手动看一遍：python scripts/read_kinds.py
    _r = audit()
    print("文档四处：10 §一A %(10)d 种 · 19 §三A %(19_fixed)d+%(19_expand)d 条 · "
          "21 §一 %(21)d · 16 §二 %(16)d" % _r["doc"])
    print("19 §三A 的 12 条：%s" % " · ".join(_r["doc"]["19_names"]))
    print("结果：%s" % ("一致 ✓  n=%d" % _r["n"] if not _r["bad"] else "有红 ✗ %s" % _r["bad"]))
    sys.exit(0 if not _r["bad"] else 1)
