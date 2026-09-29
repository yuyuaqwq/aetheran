# -*- coding: utf-8 -*-
"""titles 域重建（B3-2 · 十个称号）—— ★ 名/怎么拿到/条件/显示位置全部从源文档解析，禁手打。

读这些真源（缺一段就当场抛，不猜、不兜底）：
  aetheran-plan/06_第一阶段垂直切片/21_长期目标层_v1.md  §一  十个称号的 名 / 怎么拿到 / 玩家看到
  aetheran-plan/00_总纲/16_称号域口径_v1.md               §一 显示规则 · §二 条件 · §三 判定语汇 · §五 文案槽位

对账（对不上就抛）：
  · 两张表按 # 对齐（21 / 条件），id 与称号名两处一致
  · 条件里的每个取值都在对应域里真存在（maps / pois / items / quests / monsters / races / codex / dialogues / 时辰名）
  · 计数器的那个数**不许手打**：read_all 的数 = pois 里 into_codex 的条数；
    heard 的数 = 那棵对话树全部台词条数；visited 的目标 = 地图节点（现算）
  · 口径 §三 的键表与代码里的 ctx 字段一一对应（文档与代码不许各说各的）
  · 口径 §五 的文案槽位表与代码里的 SLOTS 一字不差
  · 三件「等前置」的计数口，依据里必须写出它将来由谁写（PRODUCER）

写：content/data/titles.json
用法：python scripts/rebuild_titles.py --dry   /   python scripts/rebuild_titles.py
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

DOC21 = os.path.join(PLAN, "06_第一阶段垂直切片", "21_长期目标层_v1.md")
SPEC = os.path.join(PLAN, "00_总纲", "16_称号域口径_v1.md")

#: 与（口径文档用 chr(38) 那一个字符连接子句）· 或 · 计数的两个记号
AND = chr(38)
OR = "+"
GE = ">="
AT = "@"

#: 子句键 → ctx 字段（★ 与口径 §三 的键表一一对应，rebuild 会双向校验）
CTX_FIELD = {
    "where": "where", "map": "map", "race": "race", "lore": "lore_scripts",
    "read": "read", "been": "been", "hold": "hold", "worn": "worn",
    "set": "set", "done": "done", "kill": "kill", "hour": "hour", "weather": "weather",
    "mat": "mat", "read_all": "read_all", "visited": "visited", "heard": "heard",
    "interrupt": "interrupt", "clean": "clean", "horn": "horn",
}
#: 集合类键（值是 id，判「在集合里」）
MEMBER_KEYS = ("read", "been", "hold", "worn", "set", "done", "kill", "mat")
#: 单值键（判相等）
SCALAR_KEYS = ("where", "map", "race", "hour", "weather")
#: 计数键（没有目标：键>=数）
COUNT_KEYS = ("read_all", "interrupt", "clean", "horn")
#: 带目标的计数键（键@目标>=数）
COUNT_AT_KEYS = ("visited", "heard")
#: ★ 三件「等前置」的计数口将来由谁写（依据里必须写出来）
PRODUCER = {"interrupt": "foot.interrupts", "clean": "foot.clears", "horn": "flags.horn_fixed"}
#: §五 的文案槽位（与口径文档 §五 一字不差）
SLOTS = ("SYS_TITLE_FOUND", "SYS_TITLE_BY_NAME", "SYS_TITLE_HEAD",
         "SYS_TITLE_ROW", "SYS_TITLE_TAIL", "SYS_TITLE_NONE")
#: 显示位置（口径 §一 的唯一一条显示规则）
WHERE = "名字后面（观察 / 状态）"
ID_RE = re.compile(r"^title_[a-z0-9_]+$")


def rd(path: str) -> str:
    with io.open(path, encoding="utf-8", newline="") as f:
        return f.read()


def load(name: str):
    with io.open(os.path.join(DATA, name + ".json"), encoding="utf-8", newline="") as f:
        return json.load(f)


def sections(text: str, level: str = "## ") -> dict:
    """标题 → 该节正文（★ 不用裸 --- 切节 —— 表格分隔行里就有它，K23）。"""
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
def _seq(key: str, target: str | None = None) -> dict:
    """ctx 取数链：带目标的多一步（visited@图:节点 / heard@对话树）。"""
    steps = [{"key": CTX_FIELD[key]}]
    if target is not None:
        steps.append({"key": target, "default": 0})
    return {"field": steps}


def clause_node(part: str, where: str) -> dict:
    if GE in part:
        left, _, num = part.partition(GE)
        key, has_at, target = left.partition(AT)
        key, target = key.strip(), (target.strip() or None)
        if key not in COUNT_KEYS + COUNT_AT_KEYS:
            raise SystemExit("口径 %s：%r 不是计数键（带 >= 的只能是 %s）"
                             % (where, key, list(COUNT_KEYS + COUNT_AT_KEYS)))
        if key in COUNT_KEYS and has_at:
            raise SystemExit("口径 %s：%s 不该带目标（写成 键>=数）" % (where, key))
        if key in COUNT_AT_KEYS and not has_at:
            raise SystemExit("口径 %s：%s 要写成 键@目标>=数（少了目标就没处判）" % (where, key))
        if num.strip() == "*":
            # ★ 2026-09-29 收口（P1-49 推荐落法②）: `*` = 「全部 = 现算」——禁手抄数字
            #   （手抄数每轮都会被自己打破：9 → 23 → 26）。目前只对 heard@对话树开放
            #   （read_all / visited 的「数」与多文档一致性对账纠缠，且被 ⑨ 判据独立看护，
            #   维持手抄+对账形态）。归一化在 main2 组装前一并做（_resolve_all）。
            if key != "heard":
                raise SystemExit("口径 %s：%r —— `*`（现算全部）只适用于 heard@对话树" % (where, part))
            return {"op": "ge", "left": _seq(key, target), "right": {"const": "*"}}
        if not num.strip().lstrip("-").isdigit():
            raise SystemExit("口径 %s：%r 的数是手滑了吗（要整数）" % (where, part))
        return {"op": "ge", "left": _seq(key, target), "right": {"const": int(num.strip())}}
    k, sep, v = part.partition("=")
    k, v = k.strip(), v.strip()
    if not sep or not k or not v:
        raise SystemExit("口径 %s：子句 %r 不是 键=值" % (where, part))
    if k == "lore":
        if v != "scripts":
            raise SystemExit("口径 %s：lore 只认 scripts，收到 %r" % (where, v))
        return {"op": "truthy", "arg": _seq(k)}
    if k in MEMBER_KEYS:
        nodes = [{"op": "contains", "elem": {"const": x},
                  "seq": _seq(k)} for x in v.split(OR)]
        return nodes[0] if len(nodes) == 1 else {"op": "or", "args": nodes}
    if k in SCALAR_KEYS:
        return {"op": "eq", "left": _seq(k), "right": {"const": v}}
    raise SystemExit("口径 %s：不认识的子句键 %r（§三 的语汇里没有它）" % (where, k))


def cond_node(expr: str, where: str) -> dict:
    parts = [p.strip() for p in expr.split(AND) if p.strip()]
    if not parts:
        raise SystemExit("口径 %s：条件是空的" % where)
    nodes = [clause_node(p, where) for p in parts]
    return nodes[0] if len(nodes) == 1 else {"op": "and", "args": nodes}


def _resolve_all(node: dict, D: dict) -> dict:
    """`heard@树>=*` 的「全部」→ 现算条数（写口唯一化：星号只在生成这一步落成数字）。

    ★ 2026-09-29 收口（P1-49）：`*` = 该树全部台词条数——**禁手抄数字**（手抄数每轮
    都会被自己打破：9 → 23 → 26）。归一化放「解析之后、对账/写域之前」：下游
    （counter_ok / titles.json）见到的永远是数字，**本模块是唯一写口**。
    """
    op = node.get("op")
    if op in ("and", "or"):
        return {"op": op, "args": [_resolve_all(x, D) for x in (node.get("args") or [])]}
    r = node.get("right")
    if op == "ge" and isinstance(r, dict) and r.get("const") == "*":
        steps = node["left"]["field"]
        target = steps[1]["key"] if len(steps) > 1 else None
        tree = (D.get("dialogues") or {}).get(str(target)) or {}
        if not tree:
            raise SystemExit("heard@%s>=* 不是一棵对话树" % target)
        n = sum(len(nd.get("texts") or []) for nd in (tree.get("nodes") or {}).values())
        out = dict(node)
        out["right"] = {"const": int(n)}
        return out
    return node


# ══════════════════════════════════════════════════════════════
# 交叉对账：条件的每个取值都要在对应的域里真存在
# ══════════════════════════════════════════════════════════════
def walk(node, out):
    """声明节点 → [(ctx 字段, 取值, 目标)]（目标只有 visited / heard 那类有）。"""
    op = node.get("op")
    if op == "contains":
        out.append((node["seq"]["field"][0]["key"], node["elem"]["const"], None))
    elif op == "eq":
        out.append((node["left"]["field"][0]["key"], node["right"]["const"], None))
    elif op == "ge":
        steps = node["left"]["field"]
        target = steps[1]["key"] if len(steps) > 1 else None
        out.append((steps[0]["key"], int(node["right"]["const"]), target))
    elif op == "truthy":
        out.append((node["arg"]["field"][0]["key"], "scripts", None))
    elif op in ("and", "or"):
        for a in node["args"]:
            walk(a, out)
    else:
        raise SystemExit("声明节点里有没见过的算子：%r" % (op,))
    return out


def _key_of(field: str) -> str:
    key = [k for k, f in CTX_FIELD.items() if f == field]
    return key[0] if key else field


def value_ok(field: str, v, target, D: dict) -> str:
    """ctx 字段 + 取值 → 这个取值在域里真的存在吗。回 "" 就是好，否则一句人话。"""
    k = _key_of(field)
    mp, po, it, qu, mo, ra = D["maps"], D["pois"], D["items"], D["quests"], D["monsters"], D["races"]
    if k in ("where", "been"):
        loc, _, node = str(v).partition(":")
        if loc not in mp or node not in [n["id"] for n in (mp[loc].get("nodes") or [])]:
            return "%s=%s 不是地图上的节点" % (k, v)
        return ""
    if k == "map":
        return "" if v in mp else "%s=%s 不是地图" % (k, v)
    if k == "race":
        return "" if ("race_" + str(v)) in ra else "race=%s 不在 races 域" % v
    if k == "read":
        if v not in po or not po[v].get("into_codex"):
            return "read=%s 不是可读物（pois 里没它或没进谱）" % v
        return ""
    if k in ("hold", "worn"):
        return "" if v in it else "%s=%s 不在 items 域" % (k, v)
    if k == "set":
        return "" if any((rec or {}).get("set_id") == v for rec in it.values()) else "set=%s 没有这件套装" % v
    if k == "done":
        return "" if v in qu else "done=%s 不在 quests 域" % v
    if k == "kill":
        return "" if v in mo else "kill=%s 不在 monsters 域" % v
    if k == "hour":
        return "" if v in D["hours"] else "hour=%s 不是四时辰之一" % v
    if k == "weather":
        return "" if v in D["weathers"] else "weather=%s 不是四天气之一" % v
    if k == "mat":
        return "" if v in (D["codex"].get("material") or {}) else "mat=%s 不在材料谱里" % v
    if k == "lore":
        return "" if v == "scripts" else "lore=%s 只认 scripts" % v
    return "不认识的字段 %s" % field


def counter_ok(key: str, num: int, target, why: str, D: dict) -> str:
    """计数子句的对账：★ 那个数不许手打 —— 能从数据现算的必须与现算值相等。"""
    if num < 1:
        return "%s 的门槛小于 1（那这条称号一开头就白送）" % key
    if key == "read_all":
        n = len([1 for _k, v in D["pois"].items() if v.get("into_codex")])
        if num != n:
            return "read_all 写的是 %d，而 pois 里可读物有 %d 条（现算）" % (num, n)
        # ★ B3-10：这个数还要与**文档那 12 类**对上 —— 10 §一A 的编号项 · 19 §三A 的 3+9 ·
        #   21 §一 那句话（四处不一致就是「两个数各说一套」，那条称号会悄悄变成拿不到 / 白送）。
        import read_kinds as _RK
        _d = _RK.docs()
        _nums = {"10 §一A": _d["10"], "19 §三A": _d["19_fixed"] + _d["19_expand"], "21 §一": _d["21"]}
        if len(set(_nums.values()) | {num}) != 1:
            return "read_all 那个数与文档对不上：%s / 条件里写 %d" % (_nums, num)
    elif key == "visited":
        if not target:
            return "visited 少了目标（图:节点）"
        loc, _, node = str(target).partition(":")
        if loc not in D["maps"] or node not in [n["id"] for n in (D["maps"][loc].get("nodes") or [])]:
            return "visited@%s 不是地图上的节点" % target
    elif key == "heard":
        if not target:
            return "heard 少了目标（对话树 id）"
        tree = D["dialogues"].get(str(target)) or {}
        if not tree:
            return "heard@%s 不是一棵对话树" % target
        n = sum(len(nd.get("texts") or []) for nd in (tree.get("nodes") or {}).values())
        if num != n:
            return "heard@%s 写的是 %d，而那棵树有 %d 条台词（现算）" % (target, num, n)
    else:
        tok = PRODUCER.get(key)
        if not tok or tok not in why:
            return "%s 的计数口将来由谁写，依据里没写（要有 %r）" % (key, tok)
    return ""


def main() -> None:
    dry = "--dry" in sys.argv
    d21, spec = rd(DOC21), rd(SPEC)

    # ── ① 21 §一：名 / 怎么拿到 / 玩家看到 ─────────────────────────
    secs21 = sections(d21, "## ")
    s21 = None
    for title, body in secs21.items():
        if title.startswith("一、") and "称号" in title:
            s21 = body
    if s21 is None:
        raise SystemExit("21 文档里找不到 §一 称号那一节")
    src = {}
    no = 0
    for cells in table_rows(s21):
        if len(cells) != 3 or cells[0] == "称号":
            continue
        no += 1
        if not cells[0] or not cells[1]:
            raise SystemExit("21 §一 第 %d 行少了称号名或「怎么拿到」" % no)
        src[no] = {"name": cells[0], "how": cells[1], "seen": cells[2]}
    if len(src) != 10:
        raise SystemExit("21 §一 的称号表解析出 %d 行（要 10）" % len(src))

    # ── ② 口径 §一 显示规则 · §二 条件 · §三 语汇 · §五 槽位 ───────
    secs = sections(spec, "## ")
    s1 = s2 = s3 = s5 = None
    for title, body in secs.items():
        if title.startswith("一、"):
            s1 = body
        elif title.startswith("二、"):
            s2 = body
        elif title.startswith("三、"):
            s3 = body
        elif title.startswith("五、"):
            s5 = body
    for name, sec in (("§一 显示规则", s1), ("§二 条件", s2), ("§三 语汇", s3), ("§五 槽位", s5)):
        if sec is None:
            raise SystemExit("口径文档里找不到 %s 那一节" % name)
    if "跟着名字走" not in s1 or "观察" not in s1 or "状态" not in s1:
        raise SystemExit("口径 §一 的显示规则变了（本模块的 WHERE=%r 要跟着改）" % WHERE)

    slots = [m.group(1) for m in re.finditer(r"^(SYS_TITLE_[A-Z_]+)\s+\S", s5, re.M)]
    if set(slots) != set(SLOTS):
        raise SystemExit("口径 §五 的槽位与本模块 SLOTS 不一致：文档 %r / 代码 %r"
                         % (slots, list(SLOTS)))

    doc_keys = [r[0] for r in table_rows(s3) if len(r) == 4 and r[0] != "键"]
    if set(doc_keys) != set(CTX_FIELD):
        raise SystemExit("口径 §三 的键表与本模块 CTX_FIELD 不一致：文档 %r / 代码 %r"
                         % (sorted(doc_keys), sorted(CTX_FIELD)))

    conds = {}
    for cells in table_rows(s2):
        if len(cells) != 5 or not cells[0].isdigit():
            continue
        conds[int(cells[0])] = (cells[1], cells[2], cells[3], cells[4])

    if set(conds) != set(src):
        raise SystemExit("两张表对不上：21 %r / 条件 %r" % (sorted(src), sorted(conds)))
    main2(src, conds, dry)


def main2(src, conds, dry) -> None:      # noqa: C901 —— 一段直叙的重建流程
    cal, wea, texts = load("calendar"), load("weather"), load("texts")
    D = {n: load(n) for n in ("maps", "pois", "items", "quests", "monsters", "races",
                              "codex", "dialogues")}
    D["hours"] = {str((texts[e["slot"]] or {}).get("value")) for k, e in cal.items() if not str(k).startswith("_")}
    D["weathers"] = {str((texts[e["slot"]] or {}).get("value")) for k, e in wea.items() if not str(k).startswith("_")}
    if not D["hours"] or not D["weathers"]:
        raise SystemExit("时辰/天气的中文名取不到 —— texts 域缺槽位")

    out = {"_meta": {
        "count": len(src),
        "title": "十个称号（长期目标层 · 不给数值）",
        "source": "06_第一阶段垂直切片/21_长期目标层_v1.md 一",
        "spec": "00_总纲/16_称号域口径_v1.md",
        "display": WHERE,
        "note": "名/怎么拿到/条件全部由 scripts/rebuild_titles.py 从源文档解析 —— 别手改本文件",
    }}
    seen = set()
    for no in sorted(src):
        cid, cname, expr, why = conds[no]
        if not ID_RE.match(cid or ""):
            raise SystemExit("号 %d 的 id 形状不对：%r" % (no, cid))
        if cname != src[no]["name"]:
            raise SystemExit("号 %d 的称号名两处不一致：21 %r / 口径 %r" % (no, src[no]["name"], cname))
        if len(why) < 12:
            raise SystemExit("%s 的「依据」太短 —— 判定可回查是硬要求：%r" % (cid, why))
        if cid in seen:
            raise SystemExit("id 重复：%s" % cid)
        seen.add(cid)
        node = _resolve_all(cond_node(expr, "条件 #%d" % no), D)
        for field, val, target in walk(node, []):
            k = _key_of(field)
            if k in COUNT_KEYS + COUNT_AT_KEYS:
                msg = counter_ok(k, int(val), target, why, D)
            else:
                msg = value_ok(field, val, target, D)
            if msg:
                raise SystemExit("%s 的条件对不上：%s" % (cid, msg))
        out[cid] = {"no": no, "name": src[no]["name"], "how": src[no]["how"],
                    "seen": src[no]["seen"], "where": WHERE, "why": why, "cond": node}

    path = os.path.join(DATA, "titles.json")
    if dry:
        print("[dry] 十个称号：")
        for k, v in out.items():
            if k.startswith("_"):
                continue
            print("  %2d %-22s %s ｜ %s" % (v["no"], k, v["name"], v["how"]))
        print("[dry] 不写盘")
        return
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("写 %s：%d 条" % (path, len(out) - 1))


if __name__ == "__main__":
    main()
