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
# ★ 审计残余 #13（2026-09-30）：`counter_ok` 的 heard 档要 `from content import prog`
#   （旗写端唯一真源）—— 生成器被当子进程跑时 `sys.path[0]` 是 scripts/，这里自举到仓根，
#   谁调（手跑 / probe_generators 子进程）都能 import content。
if PKG not in sys.path:
    sys.path.insert(0, PKG)
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


def _need_unsat(need, D, prog_mod) -> str:
    """`need` 的静态可达性：回空串 = 满足得了；否则一句为什么（★ 审计残余 #13 的牙）。

    键表与语义**跟读端 `cmds_talk._pick_indexed` 对齐**（唯一真源 = `cmds_talk.NEED_KINDS`，
    本地 import，不抄词表）：
      · `None`/缺 = 无条件；
      · `time`/`weather`：值在时辰表 / 天气表里（D 那两格现算）；
      · `flag`：有写端 —— `prog.map_slug` 认得出（表外 token 要先进本函数核过再落）；
      · `holding`：那件在 items 域；`equipped`：那个槽真有装备在用（槽名取自 items 域）；
      · `event`：在 events 域；`quest_done`：在 quests 域；
      · `hurt`：打一场就有伤 —— 恒可达；
      · `last`：写端还没核过 ⇒ fail-closed（域里今天 0 用，第一次用它的人先来核这档）；
      · 认不出的键（读端 `NEED_KINDS` 也没有）= fail-closed —— 与读端同一条理由：
        拼错的键会把这句洗成**无条件**（`_pick_indexed` 按不满足算，门禁按拿不到算）。
    """
    if need is None:
        return ""
    if not isinstance(need, dict):
        return "need 形状坏了（%s，要 dict 或 null）" % type(need).__name__
    from content.cmds_talk import NEED_KINDS as _KINDS   # 读端词表的唯一真源（本地 import）
    items = D.get("items") or {}
    slots = {str(v.get("slot")) for v in items.values()
             if isinstance(v, dict) and v.get("slot")}
    events = D.get("events") or {}
    quests = D.get("quests") or {}
    for k, v in need.items():
        vals = v if isinstance(v, list) else [v]
        if k == "time":
            for x in vals:
                if str(x) not in D["hours"]:
                    return "time=%r 不在时辰表" % (x,)
        elif k == "weather":
            for x in vals:
                if str(x) not in D["weathers"]:
                    return "weather=%r 不在天气表" % (x,)
        elif k == "flag":
            for x in vals:
                if prog_mod.map_slug(x) is None:
                    return "flag=%r 没有写端（prog 认不出）" % (x,)
        elif k == "holding":
            for x in vals:
                if str(x) not in items:
                    return "holding=%r 不在 items 域" % (x,)
        elif k == "equipped":
            for x in vals:
                if str(x) not in slots:
                    return "equipped=%r 没有任何一件装备用这个槽（槽名取自 items 域）" % (x,)
        elif k == "event":
            for x in vals:
                if str(x) not in events:
                    return "event=%r 不在 events 域" % (x,)
        elif k == "quest_done":
            for x in vals:
                if str(x) not in quests:
                    return "quest_done=%r 不在 quests 域" % (x,)
        elif k == "codex":
            # `<谱>:<条目>` —— 谱与条目都要在图鉴域里点得着（与读端 CX.has 的形状同口径）
            for x in vals:
                bk, _, rid = str(x).partition(":")
                book = (D.get("codex") or {}).get(bk)
                if not (bk and rid and isinstance(book, dict) and rid in book):
                    return "codex=%r 在图鉴域里点不着（要 <谱>:<条目>，谱与条目都要在域里）" % (x,)
        elif k == "hurt":
            pass                                        # 打一场就有伤：恒可达
        elif k == "last":
            return "need.last 的写端还没核过（域里今天 0 用 —— 第一次用它的人先把这档核进本函数）"
        else:
            if k not in _KINDS:
                return ("读端 NEED_KINDS 不认的键 %r（拼错的键会把这句洗成无条件 —— "
                        "_pick_indexed 按不满足算）" % (k,))
            return "认不出的 need 键 %r（这档门禁还没核过它）" % (k,)
    return ""


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
        # ★ 审计残余 #13（2026-09-30 · 台账 L2788「至少档」）：上面那道对拍是**恒真**的
        #   （`num` 本身就是生成器按 `n` 现算写的，见本称号 `why` 那格）⇒ 零牙。补一道
        #   **可达上界**：每条台词的 `need` 必须指得着真东西 —— 时辰/天气在域表里、
        #   `flag` 有写端（`prog.map_slug` 认得出）、`holding` 那件在 items 域。
        #   断言 = 门槛 <= 可达上界（= need 满足得了的条数；有指不着的 ⇒ 上界 < 门槛 ⇒ 当场红）。
        #   运行时那半（真敲 `_pick_layer` 数最差句数 / 每趟只出一句）归 probe_dialogues 的硬底线判据。
        from content import prog as _PROG                    # 旗写端的唯一真源（本地 import）
        bad = []
        for _nid, _nd in (tree.get("nodes") or {}).items():
            for _ti, _tx in enumerate(_nd.get("texts") or []):
                _why = _need_unsat(_tx.get("need"), D, _PROG)
                if _why:
                    bad.append("%s[%d] %s" % (_nid, _ti, _why))
        if bad:
            return ("heard@%s 可达上界 %d < 门槛 %d：有 %d 条台词的 need 指不着真东西"
                    "（这称号会拿不到）—— %s" % (target, n - len(bad), num, len(bad), "；".join(bad[:3])))
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
                              "codex", "dialogues", "events")}
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
