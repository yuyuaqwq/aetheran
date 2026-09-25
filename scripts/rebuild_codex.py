# -*- coding: utf-8 -*-
"""codex 域重建（B2-7 · 图鉴四谱）—— ★ 条目与文案全部从源文档解析，禁手打。

读这些真源（缺一段就当场抛，不猜、不兜底）：
  aetheran-plan/00_总纲/14_图鉴四谱口径_v1.md                    四本谱的条目与「一句人话」
  aetheran-plan/06_第一阶段垂直切片/05_玩法数值口径_v1.md §五     记满条数（材料/风味/怪物）

对账（对不上就抛）：
  · 材料 / 风味 / 旧物（捡的）的 id 在 items 域，且名字与 items 域一致
  · 旧物（读的）的 id 在 pois 域且 `into_codex` 非空；反过来每个 into_codex 的 poi 都要在谱里
  · 怪物的 id 在 monsters 域，名字一致
  · `ask` 里的人在 npcs 域
  · 三本谱条数 ≥ 05 §五 的记满条数；材料谱里「真拿得到」的条数 ≥ 记满条数
    （拿得到 = 出产在 采集池 / 掉落池 / 配方产出 里出现过）

写：content/data/codex.json（material · flavor · monster · relic + _meta）
用法：python scripts/rebuild_codex.py --dry   /   python scripts/rebuild_codex.py
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

PLAN = os.environ.get("AETHERAN_PLAN", "C:/Users/yuyu/aetheran-plan")
PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(PKG, "content", "data")

SPEC = os.path.join(PLAN, "00_总纲", "14_图鉴四谱口径_v1.md")
S05 = os.path.join(PLAN, "06_第一阶段垂直切片", "05_玩法数值口径_v1.md")

BOOK_LABEL = {"material": "材料谱", "flavor": "风味谱", "monster": "怪物谱", "relic": "旧物谱"}
RELIC_FROM = {"读": "read", "捡": "pick"}


def rd(path: str) -> str:
    with io.open(path, encoding="utf-8", newline="") as f:
        return f.read()


def load(name: str):
    with io.open(os.path.join(DATA, name + ".json"), encoding="utf-8", newline="") as f:
        return json.load(f)


def grab(pattern: str, text: str, where: str, flags=0):
    m = re.search(pattern, text, flags)
    if not m:
        raise SystemExit("解析不到：%s\n  模式：%s" % (where, pattern))
    return m.groups() if len(m.groups()) > 1 else m.group(1)


def sections(text: str) -> dict:
    """`## 标题` → 该节正文（★ 不用裸 `---` 切节 —— 表格分隔行里就有它）。"""
    out, cur = {}, None
    for ln in text.split("\n"):
        if ln.startswith("## "):
            cur = ln[3:].strip()
            out[cur] = []
        elif cur is not None:
            out[cur].append(ln)
    return {k: "\n".join(v) for k, v in out.items()}


def table_rows(sec: str, where: str) -> list:
    """取 markdown 表格的行（跳过分隔行）；返回每行单元格（strip + 去反引号）。"""
    rows = []
    for ln in sec.split("\n"):
        s = ln.strip()
        if not s.startswith("|"):
            continue
        cs = [c.strip() for c in s.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cs if c):
            continue                                  # 分隔行
        rows.append([c.replace("`", "").strip() for c in cs])
    if len(rows) < 2:
        raise SystemExit("解析不到表格：%s" % where)
    return rows


def cells(row: list, n: int, where: str) -> list:
    if len(row) < n:
        raise SystemExit("表格列数不够（%s）：%r" % (where, row))
    return row[:n]


def book_sections(spec: str) -> dict:
    """四张表各在哪一节（按标题序号认，不按出现顺序）。"""
    pick = {}
    for name, body in sections(spec).items():
        for prefix, book in (("二", "material"), ("三", "flavor"), ("四", "monster"), ("五", "relic")):
            if name.startswith(prefix + "、"):
                pick.setdefault(book, body)
    miss = [b for b in BOOK_LABEL if b not in pick]
    if miss:
        raise SystemExit("源文档里找不到这几节：%s" % miss)
    return pick


def check_name(tbl: dict, tid: str, name: str, where: str) -> None:
    if tid not in tbl:
        raise SystemExit("%s 条目 %r 不在 %s 里" % (where, tid, where))
    if tbl[tid].get("name") != name:
        raise SystemExit("%s %s 名字对不上：谱里 %r / 真域 %r"
                         % (where, tid, name, tbl[tid].get("name")))


def main(argv) -> int:
    dry = "--dry" in argv

    spec, t05 = rd(SPEC), rd(S05)
    items, monsters, pois, npcs = load("items"), load("monsters"), load("pois"), load("npcs")
    gathering, drops, recipes = load("gathering"), load("drop_pools"), load("recipes")

    # ── ① 05 §五：记满条数（数字从源文档来）─────────────────────
    targets = {}
    for book in ("material", "flavor", "monster"):
        targets[book] = int(grab(r"\|\s*%s\s*\|[^|]*\|\s*(\d+)\s*条\s*\|" % BOOK_LABEL[book],
                                 t05, "05 §五 %s 记满" % BOOK_LABEL[book]))

    # ── ② 四张表 ──────────────────────────────────────────────
    secs = book_sections(spec)
    codex: dict = {}

    mat = {}
    for row in table_rows(secs["material"], "材料谱")[1:]:
        iid, name, line = cells(row, 3, "材料谱行")
        check_name(items, iid, name, "items")
        mat[iid] = {"name": name, "line": line}
    codex["material"] = mat

    fla = {}
    for row in table_rows(secs["flavor"], "风味谱")[1:]:
        iid, name, line = cells(row, 3, "风味谱行")
        check_name(items, iid, name, "items")
        if items[iid].get("kind") != "食物":
            raise SystemExit("风味谱 %s 不是食物（kind=%r）" % (iid, items[iid].get("kind")))
        fla[iid] = {"name": name, "line": line}
    codex["flavor"] = fla

    mon = {}
    for row in table_rows(secs["monster"], "怪物谱")[1:]:
        mid, name, line = cells(row, 3, "怪物谱行")
        check_name(monsters, mid, name, "monsters")
        mon[mid] = {"name": name, "line": line}
    codex["monster"] = mon

    rel = {}
    for row in table_rows(secs["relic"], "旧物谱")[1:]:
        rid, src, name, hint, known, ask = cells(row, 6, "旧物谱行")
        if src not in RELIC_FROM:
            raise SystemExit("旧物谱 %s 的来路看不懂：%r（只认 读 / 捡）" % (rid, src))
        if RELIC_FROM[src] == "read":
            check_name(pois, rid, name, "pois")
            if not pois[rid].get("into_codex"):
                raise SystemExit("旧物谱（读的）%s 在 pois 域里没有 into_codex" % rid)
        else:
            # 捡的旧物：成品在 items 域，未鉴定的「一块看不出用途的旧东西」在 drop_pools 域
            if rid in items:
                check_name(items, rid, name, "items")
            elif rid in drops:
                check_name(drops, rid, name, "drop_pools")
            else:
                raise SystemExit("旧物谱（捡的）%r 既不在 items 也不在 drop_pools" % rid)
        asks = [a for a in ask.split() if a]
        bad = [a for a in asks if a not in npcs]
        if bad:
            raise SystemExit("旧物谱 %s 的 ask 里有不存在的 NPC：%s" % (rid, bad))
        if not asks:
            raise SystemExit("旧物谱 %s 没有 ask（认不出来也得写明）" % rid)
        rel[rid] = {"name": name, "from": RELIC_FROM[src],
                    "hint": hint, "known": known, "ask": asks}
    codex["relic"] = rel

    # ── ③ 反向对账：pois 里每个 into_codex 都要在谱里 ──────────
    want_read = {k for k, v in pois.items() if v.get("into_codex")}
    have_read = {k for k, v in rel.items() if v["from"] == "read"}
    if want_read != have_read:
        raise SystemExit("可读物与旧物谱（读的）对不上：缺 %s / 多 %s"
                         % (sorted(want_read - have_read), sorted(have_read - want_read)))

    # ── ③b ★ B3-10：那个数还要与**文档那 12 类**对上（10 §一A / 19 §三A / 21 §一 / 16 §二）——
    #    四处不一致就是「两个数各说一套」；塔内那几条**就地线索**本来就不在这 12 里（见 22 §二）。
    import read_kinds as _RK3
    _RK3.assert_agree(pois=pois, relic_read=have_read)

    # ── ④ 条数 ≥ 记满（05 §五）────────────────────────────────
    short = {k: (len(codex[k]), v) for k, v in targets.items() if len(codex[k]) < v}
    if short:
        raise SystemExit("条数不够记满：%s" % short)

    # ── ⑤ 材料谱「真拿得到」的条数 ≥ 记满 ─────────────────────
    produced = set()
    for g in gathering.values():
        for e in (g.get("pool") or []):
            produced.add(str(e.get("out")))
    for p_ in drops.values():
        for e in (p_.get("entries") or []) + (p_.get("pool") or []):
            produced.add(str(e.get("out")))
    for r in recipes.values():
        if r.get("out"):
            produced.add(str(r["out"]))
    reach = sorted(k for k in mat if k in produced)
    if len(reach) < targets["material"]:
        raise SystemExit("材料谱能真拿到的只有 %d 条，不到记满的 %d 条"
                         % (len(reach), targets["material"]))
    unreach = sorted(set(mat) - set(reach))

    codex["_meta"] = {
        "note": "四本谱的条目与文案由 scripts/rebuild_codex.py 从源文档解析 —— 别手改本文件",
        "book_label": BOOK_LABEL,
        "targets": targets,
        "counts": {k: len(codex[k]) for k in BOOK_LABEL},
        "material_reachable": reach,
        "material_unreachable": unreach,
        "source": ["00_总纲/14_图鉴四谱口径_v1.md",
                   "06_第一阶段垂直切片/05_玩法数值口径_v1.md §五",
                   "06_第一阶段垂直切片/19_世界热闹度与可发现物_v1.md §三A"],
    }

    for b in ("material", "flavor", "monster", "relic"):
        print("  %-6s %2d 条%s" % (BOOK_LABEL[b], len(codex[b]),
                                   ("（记满 %d）" % targets[b]) if b in targets else "（不设记满）"))
    print("  材料谱能真拿到 %d/%d（拿不到的：%s）" % (len(reach), len(mat), unreach or "无"))

    if dry:
        print("（--dry：没写盘）")
        return 0

    out = os.path.join(DATA, "codex.json")
    with io.open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(codex, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    print("写：%s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
