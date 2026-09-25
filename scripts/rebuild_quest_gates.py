# -*- coding: utf-8 -*-
"""生成器（B3-11）：quests 域里两类「门槛」—— 悬赏三档的**数值**与**交付条件** · 支线「还石头」的交付条件。

★ 为什么有这份生成器：悬赏 `reward_exp`（125 / 640 / 3920）从来没有任何真源写着的算法对得上，
  是手打的旧数；而「经验 = 同级升级需求的 1/8」却**两处真源都写着**（05 §一 · 24 §二）
  ⇒ 数值一律从文档现算，手打的两处口径必打架（AGENTS.md 铁律）。

源（全部**现解析**，一个数都不手打）：
  · `06_第一阶段垂直切片/05_玩法数值口径_v1.md §一`   悬赏报酬区间 + 「经验 = 同级升级需求的 N/D」
  · `06_第一阶段垂直切片/24_任务线_v1.md §二 悬赏板块`  同一条的另一份写法（两处必须写着且一致）
  · `06_第一阶段垂直切片/00_第一阶段内容总纲_v1.md §七`  升级曲线（真源 ⇒ 包内 `cmds_ast.exp_need` 那一个口）
  · `06_第一阶段垂直切片/00_第一阶段内容总纲_v1.md §三`  怪物五档表（档名 ↔ 怪名）
  · `content/data/monsters.json`                      `role`（中文档名）/ `role_key`（ASCII 机器键）
  · `00_总纲/15_彩蛋域口径_v1.md §二`                  彩蛋条件（「依据」栏点名了某个任务 ⇒ 那就是它的交付条件）

落点：`content/data/quests.json`（**只动点名的那几行**，其余逐字节不变 · 全 LF）

跑法：
  python scripts/rebuild_quest_gates.py --dry     # 只看要改什么（不写盘）
  python scripts/rebuild_quest_gates.py           # 落
  ★ 连跑两次数据不变（幂等）；解析不出 / 两处真源打架 / 钱跑出区间 —— 一律当场抛（不静默）

★ 悬赏交付条件的口径（本批新立 · 待鱼鱼拍板见工作树 `_notes.md`）：
  24 §二 写「打掉指定的普通怪 / 精英怪 / 头目」—— 「指定的」= 悬赏板每天轮换挑一只，
  而**轮换（每日挑怪）这一步在数据面上还没有** ⇒ 本批先落成「**那一档的怪，任意一只打掉过**」：
  `{"kind": "kill", "role": <role_key>, "n": 1}`（role_key 从 monsters 域透传，代码不认中文）。
  这比原来的「`flags.side_悬赏·普通` 那条没人写的死路径」强（真查档上的击杀账），
  但仍比「指定的那一只」宽 —— 轮换落地时把 role 换成 monster 即可（一行数据）。
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.environ.get("AST_PLAN", "C:/Users/yuyu/aetheran-plan")
SLICE = os.path.join(PLAN, "06_第一阶段垂直切片")
OUTLINE = os.path.join(PLAN, "00_总纲")
QFILE = os.path.join(REPO, "content", "data", "quests.json")
MFILE = os.path.join(REPO, "content", "data", "monsters.json")
sys.path.insert(0, REPO)

from content.cmds_ast import exp_need                              # noqa: E402  ★ 曲线唯一口


def _read(path):
    if not os.path.exists(path):
        raise SystemExit("真源文档不在：%s" % path)
    return io.open(path, encoding="utf-8", newline="").read()


# ── 一、真源解析 ────────────────────────────────────────────────
#: 「经验 = 同级需求的 N/D」/「经验 = 同级升级需求的 N/D」—— 05 §一 与 24 §二 是同一件事的两份写法
_EXP = re.compile(r"经验\s*=\s*同级(?:升级)?需求的\s*(\d+)\s*/\s*(\d+)")
#: 24 §二 悬赏板块的报酬区间
_RANGE24 = re.compile(r"报酬\s*(\d+)[–\-~](\d+)（普通）\s*/\s*(\d+)[–\-~](\d+)（精英）"
                      r"\s*/\s*(\d+)[–\-~](\d+)（头目）")
#: 05 §一 同一行的报酬区间
_RANGE05 = re.compile(r"按目标档位：普通\s*\**\s*(\d+)[–\-~](\d+)\s*\**\s*币\s*·\s*"
                      r"精英\s*\**\s*(\d+)[–\-~](\d+)\s*\**\s*·\s*"
                      r"头目\s*\**\s*(\d+)[–\-~](\d+)\s*\**")
#: 00 §三 怪物五档表的一行：`| 普通 | **田鼠** | 骨田 | …`
_ROW_TIER = re.compile(r"^\|\s*([^|*]+?)\s*\|\s*\*\*([^|*]+?)\*\*\s*\|")
#: 15 §二 彩蛋条件表的一行：`| 2 | egg_stone_corner | hold=… & where=… | 依据…q_side_13… |`
_ROW_EGG = re.compile(r"^\|\s*\d+\s*\|\s*(egg_[a-z_]+)\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*$")


def _section(path, start, stop_prefix):
    """文档里 §X 那一节的正文（`start` 行开头 → `stop_prefix` 行开头之前；解析不出当场抛）。"""
    lines = _read(path).split("\n")
    a = next((i for i, ln in enumerate(lines) if ln.startswith(start)), None)
    if a is None:
        raise SystemExit("%s 里找不到「%s」那一节" % (os.path.basename(path), start))
    b = next((i for i in range(a + 1, len(lines)) if lines[i].startswith(stop_prefix)), None)
    if b is None:
        raise SystemExit("%s 的「%s」那一节没有收尾" % (os.path.basename(path), start))
    return "\n".join(lines[a:b])


def _bounty_block():
    """24 §二 的悬赏板块原文（从 `**悬赏板**` 到 §三 之前）。"""
    lines = _read(os.path.join(SLICE, "24_任务线_v1.md")).split("\n")
    on, blk, stop = False, [], None
    for i, ln in enumerate(lines):
        if ln.startswith("## 二、"):
            on = True
            continue
        if on and ln.startswith("## 三、"):
            stop = i
            break
        if on and ln.startswith("**悬赏板**"):
            blk = i
    if blk is None or stop is None:
        raise SystemExit("24 §二 的悬赏板块解析不出（`**悬赏板**` / `## 三、` 有一个不在）")
    return "\n".join(lines[blk:stop])


def parse_exp_ratio():
    """经验占比 → (N, D)。★ 两处真源（05 §一 · 24 §二）都写着，且必须一致。"""
    a = _EXP.search(_read(os.path.join(SLICE, "05_玩法数值口径_v1.md")))
    b = _EXP.search(_bounty_block())
    if not a or not b:
        raise SystemExit("悬赏经验口径解析不出：05 §一 %s · 24 §二 %s"
                         % ("有" if a else "无", "有" if b else "无"))
    if a.groups() != b.groups():
        raise SystemExit("★ 两处真源打架：05 §一 写 %s/%s，24 §二 写 %s/%s —— 先裁决再落数据"
                         % (a.group(1), a.group(2), b.group(1), b.group(2)))
    num, den = int(a.group(1)), int(a.group(2))
    if den <= 0 or num <= 0:
        raise SystemExit("经验占比不是正分数：%d/%d" % (num, den))
    return num, den


def parse_ranges():
    """报酬区间 {档名: (lo, hi)} —— 05 §一 与 24 §二 两处一致。"""
    a = _RANGE24.search(_bounty_block())
    b = _RANGE05.search(_read(os.path.join(SLICE, "05_玩法数值口径_v1.md")))
    if not a or not b:
        raise SystemExit("悬赏报酬区间解析不出（05 §一 %s · 24 §二 %s）"
                         % ("有" if b else "无", "有" if a else "无"))
    if a.groups() != b.groups():
        raise SystemExit("★ 两处真源打架：24 §二 %s vs 05 §一 %s" % (a.groups(), b.groups()))
    g = [int(x) for x in a.groups()]
    return {"普通": (g[0], g[1]), "精英": (g[2], g[3]), "头目": (g[4], g[5])}


def parse_tiers(monsters):
    """00 §三 五档表 → {档名: role_key}（怪名 → 域里的怪 → role_key；一档里必须同一个 role_key）。"""
    sec = _section(os.path.join(SLICE, "00_第一阶段内容总纲_v1.md"),
                   "## 三、怪物十六只", "## 四、")
    out = {}
    for ln in sec.split("\n"):
        m = _ROW_TIER.match(ln)
        if not m:
            continue
        tier, mname = m.group(1).strip(), m.group(2).strip()
        if tier in ("档",) or tier.startswith("-"):
            continue
        hit = [k for k, v in monsters.items() if v.get("name") == mname]
        if len(hit) != 1:
            raise SystemExit("00 §三 的怪「%s」在 monsters 域里匹配到 %d 条" % (mname, len(hit)))
        rk = monsters[hit[0]].get("role_key")
        if not rk:
            raise SystemExit("怪「%s」没有 role_key" % mname)
        if out.get(tier) not in (None, rk):
            raise SystemExit("00 §三 的「%s」档里 role_key 不一致（%s vs %s）" % (tier, out[tier], rk))
        out[tier] = rk
    if not out:
        raise SystemExit("00 §三 的怪物五档表一行都没解析出来")
    return out


#: 彩蛋表的「依据」栏里「某个**任务**的交待就是这个彩蛋」那一句的**语法**（明写在这里，别用模糊匹配）：
#:   例（15 §二 第 2 行）`q_side_13「还石头」的交待就是彩蛋 2`
_EGG_IS_QUEST = re.compile(r"(q_[a-z0-9_]+)\s*「([^」]+)」\s*的交待就是彩蛋\s*(\d+)")


def parse_egg_gates():
    """15 §二 → {任务 id: (任务名, [(子句键, 值), …])}。

    ★ 规则（写在明面上 · 只认这一种句子形状）：「<q_…>「<名字>」的交待就是彩蛋 <n>」——
      「交待」= 玩家交付那一步要交出去的东西；所以那条彩蛋的条件就是那个任务的交付条件。
      `read=` 那一步是**彩蛋自己**的「读过才连得起来」，任务不取（任务只管「把石头还到那儿」）。
    ★ 一句都找不着 ⇒ 当场抛（文档换说法要有人重新裁决，不许静默少一条条件）。
    """
    out = {}
    for ln in _read(os.path.join(OUTLINE, "15_彩蛋域口径_v1.md")).split("\n"):
        m = _ROW_EGG.match(ln)
        if not m:
            continue
        cond, why = m.group(2), m.group(3)
        j = _EGG_IS_QUEST.search(why)
        if not j:
            continue
        clauses = []
        for cl in cond.split("&"):
            cl = cl.strip()
            if "=" not in cl:
                continue
            k, v = cl.split("=", 1)
            if k.strip() == "read":
                continue
            clauses.append((k.strip(), v.strip()))
        if not clauses:
            raise SystemExit("彩蛋 %s 被点名成 %s 的交待，但条件里没有可用的子句：%s"
                             % (m.group(1), j.group(1), cond))
        out.setdefault(j.group(1), (j.group(2), clauses))
    if not out:
        raise SystemExit("15 §二 里一条「<任务>「<名字>」的交待就是彩蛋 <n>」都没解析出来 —— "
                         "文档换说法了？先裁决再落数据")
    return out


# ── 二、算 ──────────────────────────────────────────────────────
def to_require(clauses):
    """子句 → `require` 条件（fail-closed：认不出的子句键当场抛）。"""
    reqs = []
    for k, v in clauses:
        if k == "hold":                       # 在身上 → item
            reqs.append({"kind": "item", "item": v, "n": 1})
        elif k == "where":                    # 站在这个节点 → visit
            m, _, nd = v.partition(":")
            if not (m and nd):
                raise SystemExit("where 子句要写「图:节点」，实得 %s" % v)
            reqs.append({"kind": "visit", "map": m, "node": nd})
        elif k == "kill":                     # 打过某只怪 → kill（点名那只）
            reqs.append({"kind": "kill", "monster": v, "n": 1})
        else:
            raise SystemExit("子句键「%s」还没有对应的条件形状（要新形状得单独立项）" % k)
    return reqs


# ── 三、写（只动点名的行）────────────────────────────────────────
def _block_span(lines, key):
    """顶层条目 `"key": {` … `  },` 的行号区间（含首尾）。"""
    head = '  "%s": {' % key
    try:
        a = lines.index(head)
    except ValueError:
        raise SystemExit("域里找不到条目 %s" % key)
    for b in range(a + 1, len(lines)):
        if lines[b] == "  }," or lines[b] == "  }":
            return a, b
    raise SystemExit("条目 %s 的收尾行找不到" % key)


def _dump_require(reqs, indent="    "):
    """按域里现成的写法（与 `q_trade_01` 逐字同形）铺开一串条件。"""
    out = [indent + '"require": [']
    for i, r in enumerate(reqs):
        keys = list(r.keys())
        out.append(indent + "  {")
        for j, k in enumerate(keys):
            out.append(indent + '    "%s": %s%s' % (k, json.dumps(r[k], ensure_ascii=False),
                                                    "," if j < len(keys) - 1 else ""))
        out.append(indent + "  }" + ("," if i < len(reqs) - 1 else ""))
    out.append(indent + "],")
    return out


def apply_to_text(text, planned):
    """`planned` = {quest_id: {"lines": 新增/替换的几行, "reward_exp": 新值或 None}}。返回新文本。"""
    lines = text.split("\n")
    for qid in sorted(planned, key=lambda q: -_block_span(lines, q)[0]):   # 从后往前插，行号不漂
        plan = planned[qid]
        a, b = _block_span(lines, qid)
        blk = lines[a:b + 1]
        # ① reward_exp 那一行（只在这一条里换数字）
        if plan.get("reward_exp") is not None:
            for i, ln in enumerate(blk):
                if ln.strip().startswith('"reward_exp":'):
                    want = '    "reward_exp": %d,' % plan["reward_exp"]
                    if ln != want:
                        blk[i] = want
                    break
            else:
                raise SystemExit("%s 里没有 reward_exp 那一行" % qid)
        # ② require（有就整块换掉，没有就插在 objective 之后 —— 与 q_trade_* 同位置）
        if plan.get("require"):
            want = _dump_require(plan["require"])
            i = next((j for j, ln in enumerate(blk) if ln.strip().startswith('"require"')), None)
            if i is not None:
                j = next(j for j in range(i + 1, len(blk)) if blk[j].startswith("    ]"))
                blk[i:j + 1] = want
            else:
                i = next((j for j, ln in enumerate(blk) if ln.strip().startswith('"objective"')), None)
                if i is None:
                    raise SystemExit("%s 里没有 objective 那一行，插不进 require" % qid)
                blk[i + 1:i + 1] = want
        lines[a:b + 1] = blk
    return "\n".join(lines)


def main(dry=False):
    monsters = {k: v for k, v in json.load(io.open(MFILE, encoding="utf-8")).items()
                if not str(k).startswith("_")}
    old_text = _read(QFILE)                                   # ★ newline="" ⇒ 原样（全 LF）
    dom = json.loads(old_text)
    num, den = parse_exp_ratio()
    rng = parse_ranges()
    tiers = parse_tiers(monsters)
    egg_gates = parse_egg_gates()

    planned = {}
    print("真源：经验 = 同级升级需求的 %d/%d（05 §一 ＝ 24 §二）· 报酬区间 %s" % (num, den, rng))
    print("五档表（00 §三 → role_key）：%s" % tiers)

    # ① 悬赏三档：经验 = exp_need(该档 min_level) × N/D（整数；除不尽当场抛，不许四舍五入糊过去）
    for k, v in sorted(dom.items(), key=lambda kv: kv[1].get("order") or 0):
        if str(k).startswith("_") or v.get("chain") != "bounty":
            continue
        tier = v["name"].split("·")[-1]
        if tier not in tiers:
            raise SystemExit("%s 的档位「%s」不在 00 §三 的五档表里" % (k, tier))
        need_ = exp_need(v["min_level"])
        if need_ * num % den:
            raise SystemExit("%s：需求 %d × %d/%d 不是整数" % (k, need_, num, den))
        exp = need_ * num // den
        lo, hi = rng[tier]
        if not (lo <= int(v["reward_gold"]) <= hi):
            raise SystemExit("%s 的报酬 %s 跑出文档区间 %s（钱也得跟账）"
                             % (k, v["reward_gold"], (lo, hi)))
        req = [{"kind": "kill", "role": tiers[tier], "n": 1}]
        cur = v.get("require")
        if cur != req or v.get("reward_exp") != exp:
            planned[k] = {"require": req, "reward_exp": exp,
                          "why": "min_level %d 需求 %d × %d/%d = %d（原 %s）"
                                 % (v["min_level"], need_, num, den, exp, v.get("reward_exp"))}

    # ② 15 §二「<任务>「<名字>」的交待就是彩蛋 <n>」⇒ 那个任务的交付条件
    for qid, (qname, clauses) in sorted(egg_gates.items()):
        if qid not in dom:
            raise SystemExit("15 §二 点名了 %s，但域里没有这条任务" % qid)
        if dom[qid].get("name") != qname:
            raise SystemExit("15 §二 说的「%s」与域里 %s 的名字「%s」对不上"
                             % (qname, qid, dom[qid].get("name")))
        req = to_require(clauses)
        if dom[qid].get("require") != req:
            planned.setdefault(qid, {})["require"] = req
            planned[qid]["why"] = "15 §二「%s「%s」的交待」那一条 ⇒ %s" % (
                qid, qname, json.dumps(req, ensure_ascii=False))

    if not planned:
        print("★ 无需改动（域里已经是真源算出来的那一族）—— 幂等 ✓")
        return 0

    for qid in sorted(planned, key=lambda q: dom[q].get("order") or 0):
        print("  · %-18s %s" % (qid, planned[qid]["why"]))
    if dry:
        print("★ --dry：一行都没写。")
        return 0

    new_text = apply_to_text(old_text, planned)
    new = json.loads(new_text)
    # ★ 闸：只许动点名的两件（require / reward_exp），别的键逐条相等；条数与键序都不许变
    if len(new) != len(dom):
        raise SystemExit("条数变了（%d → %d）—— 停下" % (len(dom), len(new)))
    for qid in sorted(set(list(dom) + list(new))):
        if list(dom.get(qid, {})) != list(new.get(qid, {})) and qid not in planned:
            raise SystemExit("%s 的键序 / 键集被动到了 —— 停下" % qid)
        for f in set(list(dom.get(qid, {})) + list(new.get(qid, {}))):
            if dom.get(qid, {}).get(f) != new.get(qid, {}).get(f):
                if qid not in planned or f not in planned[qid]:
                    raise SystemExit("%s.%s 被动了（不在计划里）—— 停下" % (qid, f))
    if "\r\n" in new_text:
        raise SystemExit("落出来带 CRLF —— 全 LF 是硬口径")
    with io.open(QFILE, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_text)
    print("★ 落了 %d 条：%s" % (len(planned), ", ".join(sorted(planned))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(dry="--dry" in sys.argv or "--dry-run" in sys.argv))
