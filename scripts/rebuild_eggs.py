# -*- coding: utf-8 -*-
"""eggs 域重建（B3-1 · 十条彩蛋）—— ★ 标题/两端/发现方式与文案全部从源文档解析，禁手打。

读这些真源（缺一段就当场抛，不猜、不兜底）：
  aetheran-plan/06_第一阶段垂直切片/19_世界热闹度与可发现物_v1.md  §三 B  十条彩蛋的标题 / 两端 / 发现方式
  aetheran-plan/00_总纲/15_彩蛋域口径_v1.md                         §二 条件 · §二-b 揭示文案 · §三 判定语汇

对账（对不上就抛）：
  · 三张表按 # 对齐（19 / 条件 / 文案），id 三处一致
  · 条件里的每个取值都在对应域里真存在（maps / pois / items / quests / monsters / races / texts 的时辰名）
  · 口径 §三 的键表与代码里的 ctx 字段一一对应（文档与代码不许各说各的）
  · 揭示文案 12–60 字 · pair 两端非空且互不相同

写：content/data/eggs.json
用法：python scripts/rebuild_eggs.py --dry   /   python scripts/rebuild_eggs.py
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

DOC19 = os.path.join(PLAN, "06_第一阶段垂直切片", "19_世界热闹度与可发现物_v1.md")
SPEC = os.path.join(PLAN, "00_总纲", "15_彩蛋域口径_v1.md")

#: 与（口径文档用 chr(38) 那一个字符连接子句）· 或（+）
AND = chr(38)
OR = "+"

#: 子句键 → ctx 字段（★ 与口径 §三 的键表一一对应，rebuild 会双向校验）
CTX_FIELD = {
    "where": "where", "map": "map", "race": "race", "lore": "lore_scripts",
    "read": "read", "been": "been", "hold": "hold", "worn": "worn",
    "set": "set", "done": "done", "kill": "kill", "hour": "hour", "weather": "weather",
}
#: 集合类键（值是 id，判「在集合里」）
MEMBER_KEYS = ("read", "been", "hold", "worn", "set", "done", "kill")
#: 单值键（判相等）
SCALAR_KEYS = ("where", "map", "race", "hour", "weather")
ID_RE = re.compile(r"^egg_[a-z0-9_]+$")


def rd(path: str) -> str:
    with io.open(path, encoding="utf-8", newline="") as f:
        return f.read()


def load(name: str):
    with io.open(os.path.join(DATA, name + ".json"), encoding="utf-8", newline="") as f:
        return json.load(f)


def sections(text: str, level: str = "## ") -> dict:
    """标题 → 该节正文（★ 不用裸 --- 切节 —— 表格分隔行里就有它）。"""
    out, cur = {}, None
    for ln in text.split("\n"):
        if ln.startswith(level) and not ln.startswith(level + "#"):
            cur = ln[len(level):].strip()
            out[cur] = []
        elif cur is not None:
            out[cur].append(ln)
    return {k: "\n".join(v) for k, v in out.items()}


def clean(cell: str) -> str:
    s = cell.replace("**", "").replace("`", "").strip()
    return re.sub(r"\s+", " ", s)


def table_rows(sec: str) -> list:
    """markdown 表格 → [[单元格…], …]（跳过分隔行）。"""
    rows = []
    for ln in sec.split("\n"):
        t = ln.strip()
        if not t.startswith("|"):
            continue
        cells = [clean(c) for c in t.strip("|").split("|")]
        if cells and re.fullmatch(r"[-: ]*", cells[0]):
            continue
        rows.append(cells)
    return rows


# ══════════════════════════════════════════════════════════════
# 条件：口径里的 键=值 子句 → 引擎通用算子的声明节点
# ══════════════════════════════════════════════════════════════
def clause_node(k: str, v: str, where: str):
    if k == "lore":
        if v != "scripts":
            raise SystemExit("口径 %s：lore 只认 scripts，收到 %r" % (where, v))
        return {"op": "truthy", "arg": {"field": [{"key": CTX_FIELD[k]}]}}
    if k in MEMBER_KEYS:
        nodes = [{"op": "contains", "elem": {"const": x},
                  "seq": {"field": [{"key": CTX_FIELD[k]}]}} for x in v.split(OR)]
        return nodes[0] if len(nodes) == 1 else {"op": "or", "args": nodes}
    if k in SCALAR_KEYS:
        return {"op": "eq", "left": {"field": [{"key": CTX_FIELD[k]}]}, "right": {"const": v}}
    raise SystemExit("口径 %s：不认识的子句键 %r（§三 的语汇里没有它）" % (where, k))


def cond_node(expr: str, where: str) -> dict:
    parts = [p.strip() for p in expr.split(AND) if p.strip()]
    if not parts:
        raise SystemExit("口径 %s：条件是空的" % where)
    nodes = []
    for p in parts:
        k, sep, v = p.partition("=")
        if not sep or not k.strip() or not v.strip():
            raise SystemExit("口径 %s：子句 %r 不是 键=值" % (where, p))
        nodes.append(clause_node(k.strip(), v.strip(), where))
    return nodes[0] if len(nodes) == 1 else {"op": "and", "args": nodes}


def main() -> None:
    dry = "--dry" in sys.argv
    d19, spec = rd(DOC19), rd(SPEC)

    # ── ① 19 文档 §三 B：标题 / 两端 / 发现方式 ───────────────────
    b_sec = None
    for title, body in sections(d19, "### ").items():
        if title.startswith("B.") and "彩蛋" in title:
            b_sec = body
    if b_sec is None:
        raise SystemExit("19 文档里找不到 §三 B 彩蛋那一节")
    src = {}
    for cells in table_rows(b_sec):
        if len(cells) != 4 or not cells[0].isdigit():
            continue
        no = int(cells[0])
        pair = [x.strip() for x in cells[2].split("↔")]
        if len(pair) != 2 or not pair[0] or not pair[1] or pair[0] == pair[1]:
            raise SystemExit("19 号 %d 的两端不对：%r" % (no, cells[2]))
        src[no] = {"title": cells[1], "pair": pair, "how": cells[3]}
    if not src:
        raise SystemExit("19 文档的彩蛋表一行都没解析出来（表格形状变了？）")

    # ── ② 口径 §二 条件 · §二-b 文案 · §三 语汇 ──────────────────
    s_sec, l_sec, k_sec = None, None, None
    for title, body in sections(spec, "## ").items():
        if title.startswith("二、"):
            s_sec = body
        elif title.startswith("二-b"):
            l_sec = body
        elif title.startswith("三、"):
            k_sec = body
    for name, sec in (("§二 条件", s_sec), ("§二-b 文案", l_sec), ("§三 语汇", k_sec)):
        if sec is None:
            raise SystemExit("口径文档里找不到 %s 那一节" % name)

    doc_keys = [r[0] for r in table_rows(k_sec) if len(r) == 4 and r[0] != "键"]
    if set(doc_keys) != set(CTX_FIELD):
        raise SystemExit("口径 §三 的键表与本模块 CTX_FIELD 不一致：文档 %r / 代码 %r"
                         % (sorted(doc_keys), sorted(CTX_FIELD)))

    conds, lines = {}, {}
    for cells in table_rows(s_sec):
        if len(cells) != 4 or not cells[0].isdigit():
            continue
        conds[int(cells[0])] = (cells[1], cond_node(cells[2], "条件 #%s" % cells[0]))
    for cells in table_rows(l_sec):
        if len(cells) != 3 or not cells[0].isdigit():
            continue
        lines[int(cells[0])] = (cells[1], cells[2])

    if set(conds) != set(src) or set(lines) != set(src):
        raise SystemExit("三张表对不上：19 %r / 条件 %r / 文案 %r"
                         % (sorted(src), sorted(conds), sorted(lines)))
    main2(src, conds, lines, dry)


# ══════════════════════════════════════════════════════════════
# 交叉对账：条件的每个取值都要在对应的域里真存在
# ══════════════════════════════════════════════════════════════
def walk(node, out):
    """声明节点 → [(ctx 字段, 取值)]。"""
    op = node.get("op")
    if op == "contains":
        out.append((node["seq"]["field"][0]["key"], node["elem"]["const"]))
    elif op == "eq":
        out.append((node["left"]["field"][0]["key"], node["right"]["const"]))
    elif op == "truthy":
        out.append((node["arg"]["field"][0]["key"], "scripts"))
    elif op in ("and", "or"):
        for a in node["args"]:
            walk(a, out)
    else:
        raise SystemExit("声明节点里有没见过的算子：%r" % (op,))
    return out


def value_ok(field: str, v: str, it, mp, po, qu, mo, ra, txs) -> bool:
    """ctx 字段 + 取值 → 这个取值在域里真的存在吗（字段名与 CTX_FIELD 反向对应）。"""
    key = [k for k, f in CTX_FIELD.items() if f == field]
    k = key[0] if key else field
    if k in ("where", "been"):
        loc, _, node = str(v).partition(":")
        return loc in mp and node in [n["id"] for n in mp[loc].get("nodes") or []]
    if k == "map":
        return v in mp
    if k == "race":
        return ("race_" + v) in ra
    if k == "read":
        return v in po and bool(po[v].get("into_codex"))
    if k in ("hold", "worn"):
        return v in it
    if k == "set":
        return any((rec or {}).get("set_id") == v for rec in it.values())
    if k == "done":
        return v in qu
    if k == "kill":
        return v in mo
    if k == "hour":
        return v in txs["hour"]
    if k == "weather":
        return v in txs["weather"]
    if k == "lore":
        return v == "scripts"
    return False


def main2(src, conds, lines, dry) -> None:      # noqa: C901 —— 一段直叙的重建流程
    it, mp = load("items"), load("maps")
    po, qu, mo, ra = load("pois"), load("quests"), load("monsters"), load("races")
    cal, wea, texts = load("calendar"), load("weather"), load("texts")
    txs = {"hour": {texts[e["slot"]]["value"] for k, e in cal.items() if not k.startswith("_")},
           "weather": {texts[e["slot"]]["value"] for k, e in wea.items() if not k.startswith("_")}}
    if not txs["hour"] or not txs["weather"]:
        raise SystemExit("时辰/天气的中文名取不到 —— texts 域缺槽位")

    # ★ L2376：`_meta` 只留说明性字段 —— **不写 count**。
    #   条数由 `content/eggs.py::total()` 现算（唯一一处）；域里再存一份就是两个维护点。
    out = {"_meta": {
        "title": "十条彩蛋（跨文本呼应）",
        "source": "06_第一阶段垂直切片/19_世界热闹度与可发现物_v1.md 三 B",
        "spec": "00_总纲/15_彩蛋域口径_v1.md",
    }}
    seen = set()
    for no in sorted(src):
        t_id, node = conds[no]
        l_id, line = lines[no]
        if not ID_RE.match(t_id or ""):
            raise SystemExit("号 %d 的 id 形状不对：%r" % (no, t_id))
        if t_id != l_id:
            raise SystemExit("号 %d 的 id 三处不一致：%r / %r" % (no, t_id, l_id))
        if t_id in seen:
            raise SystemExit("id 重复：%s" % t_id)
        seen.add(t_id)
        if len(line) < 12 or len(line) > 60:
            raise SystemExit("%s 的揭示文案 %d 字（要 12–60）：%s" % (t_id, len(line), line))
        if line == src[no]["how"]:
            raise SystemExit("%s 的揭示文案与「发现方式」一字不差（那就不是连起来那句话）" % t_id)
        for field, v in walk(node, []):
            if not value_ok(field, v, it, mp, po, qu, mo, ra, txs):
                raise SystemExit("%s 条件里的 %s=%s 在对应域里不存在" % (t_id, field, v))
        out[t_id] = {"no": no, "title": src[no]["title"], "line": line,
                     "pair": src[no]["pair"], "how": src[no]["how"], "cond": node}

    path = os.path.join(DATA, "eggs.json")
    if dry:
        print("[dry] 十条彩蛋：")
        for k, v in out.items():
            if k.startswith("_"):
                continue
            print("  %2d %-22s %s ｜ 两端 %s ｜ %s"
                  % (v["no"], k, v["title"][:22], "↔".join(v["pair"]), v["how"]))
        print("[dry] 不写盘")
        return
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("写 %s：%d 条" % (path, len(out) - 1))


if __name__ == "__main__":
    main()
