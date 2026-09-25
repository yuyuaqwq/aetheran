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

★ 悬赏交付条件的口径（B3-11 立 · **B3-13 收口成「指定的」**）：
  24 §二 写「打掉**指定的**普通 / 精英 / 头目怪」，并在同一条里点明「**指定的** = 悬赏板每天
  轮换挑一只」⇒ 条件落成 `{"kind": "kill", "role": <role_key>, "n": 1, "daily": true}`：
  该档的怪按 id 排序后，按**游戏日**取第 `(游戏日-1) % 档内只数 + 1` 只（`cmds_quest._daily_pick`）——
  ★ 同一日同档必是同结果、跨日必换（档内只数 > 1）；轮换是**算出来的**，不是写死哪一只。
  （b41 落的是「那一档任意一只打掉过」那个宽口径，本批收窄；依据仍是 24 §二 那两句话 ——
   两句少一句就当场抛，口径变要有人重新裁决。）
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


# ── 一-b、支线那 6 条的**形状语法**（B3-13）──────────────────────────
#   真源 = `24_任务线_v1.md §二` 的「步骤」列（`21_长期目标层_v1.md §二` 是同条的第二稿，两稿
#   逐字同句）；每条的**数**（+3 / 三次 / 三段 / 三道菜 / 三个人）从那一列**现取**，不是手打的。
#   ★ 一条正则都不中 ⇒ 当场抛（文档换了写法要有人重新裁决 —— 不许静默少一条条件）。
_CN_DIGIT = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
             "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_NUM = r"[一二两三四五六七八九十\d]"

#: 强化的级数：`把一件装备强化到 +3`
_PAT_ENHANCE = re.compile(r"把一件装备强化到\s*\+?\s*(\d+)")
#: 菜的道数：`做三道菜给贝拉尝`
_PAT_COOK_N = re.compile(r"做(" + _NUM + r"+)道菜")
#: 用某一品阶的食材做一次：`用稀有食材做一次`（品阶名从这一句里现取）
_PAT_COOK_Q = re.compile(r"用(\S+?)食材做(" + _NUM + r"*)[次回]")
#: 听某人讲 N 次 / N 段：`听他讲完（三次）` · `听他讲完三段（每段缺一块）`
_PAT_TALK_CI = re.compile(r"听[他她]讲完[（(](" + _NUM + r"+)次[）)]")
_PAT_TALK_DUAN = re.compile(r"听[他她]讲完(" + _NUM + r"+)段")
#: 问 N 个人：`帮她问三个人（限时：商队窗口）`
_PAT_ASK = re.compile(r"帮[他她]问(" + _NUM + r"+)个人")

#: ★ 支线条件规则表（**只有这一张**；键 = 任务 id）—— 每条的依据（文档那一句）写在 why 里
_SIDE_RULES = {
    # 支 1 柯尔的学徒 ·「把一件装备强化到 +3」⇒ 档上有一件装备的强化等级 ≥ 3
    #   （账 = `p.enhance[<装备>].lv`，写入口 `cmds_recipe.enhance`）
    "q_side_01": {"kind": "enhance", "pats": [_PAT_ENHANCE],
                  "why": "24 §二 支1「把一件装备强化到 +3」（21 §二 强化栏同条）"},
    # 支 5 客栈的招牌 ·「做三道菜给贝拉尝」⇒ 下过锅 ≥ 3 次（账 = `flags.cooked[<配方>]`）
    "q_side_05": {"kind": "cook", "pats": [_PAT_COOK_N],
                  "why": "24 §二 支5「做三道菜给贝拉尝」（21 §二 同条）"},
    # 支 6 下一顿 ·「用稀有食材做一次」⇒ 做过**用了那一品阶食材**的菜 ≥ 1 次
    #   （品阶名现取自这一句；判定时与 items 域的 quality 比 —— 代码不写中文品阶名）
    "q_side_06": {"kind": "cook_quality", "pats": [_PAT_COOK_Q],
                  "why": "24 §二 支6「用稀有食材做一次」（21 §二 同条）"},
    # 支 9 老陶的旧路 ·「听他讲完（三次）」⇒ 跟他搭过 ≥ 3 次话（账 = `flags.talked[<对话树>]`）
    "q_side_09": {"kind": "talk", "pats": [_PAT_TALK_CI, _PAT_TALK_DUAN],
                  "why": "24 §二 支9「听他讲完（三次）」"},
    # 支 16 断剑团的旧事 ·「听他讲完三段（每段缺一块）」⇒ 同上（段数从文档取）
    "q_side_16": {"kind": "talk", "pats": [_PAT_TALK_DUAN, _PAT_TALK_CI],
                  "why": "24 §二 支16「听他讲完三段（每段缺一块）」"},
    # 支 17 她在找的塔 ·「帮她问三个人（限时：商队窗口）」⇒ 搭过话的人 ≥ 3 个
    #   ★ 只落「问三个人」那半截：「限时：商队窗口」那半截（商队窗口）还没落地 ——
    #     口径缺口登记在工作树 `_notes.md`，宽的那一点不在这里偷偷当成满足。
    "q_side_17": {"kind": "ask", "pats": [_PAT_ASK],
                  "why": "24 §二 支17「帮她问三个人」"},
}

#: 支线表的一行：`| 1 | 柯尔的学徒 | 柯尔 | 把一件装备强化到 +3 | 强化费打折 |`
_ROW_SIDE = re.compile(r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|"
                       r"\s*([^|]+?)\s*\|\s*$")


def parse_side_rows():
    """24 §二 → {序号: {"name","who","steps","reward"}}（只取悬赏板之前的那张支线表）。"""
    lines = _read(os.path.join(SLICE, "24_任务线_v1.md")).split("\n")
    on, stop, out = False, None, {}
    for i, ln in enumerate(lines):
        if ln.startswith("## 二、"):
            on = True
            continue
        if on and ln.startswith("## 三、"):
            stop = i
            break
    if not on or stop is None:
        raise SystemExit("24 §二 那一段解析不出（`## 二、` / `## 三、` 有一个不在）")
    for ln in lines[:stop]:
        if not on:
            continue
        m = _ROW_SIDE.match(ln)
        if not m or ln.startswith("| #"):
            continue
        if "---" in ln or "悬赏板" in ln:
            continue
        out[int(m.group(1))] = {"name": m.group(2), "who": m.group(3),
                                "steps": m.group(4), "reward": m.group(5)}
    if not out:
        raise SystemExit("24 §二 的支线表一行都没解析出来")
    return out


def _num(token):
    """数词（一…十 / 阿拉伯数字）→ int；认不出当场抛。"""
    t = str(token or "").strip()
    if t.isdigit():
        return int(t)
    if t in _CN_DIGIT:
        return _CN_DIGIT[t]
    raise SystemExit("数词「%s」认不出（只认 一…十 与阿拉伯数字）" % t)


def _npc_of(npcs, who):
    """「谁给」那一栏的中文名 → npc id（域里必须正好一条；对不上当场抛）。"""
    hit = [k for k, v in npcs.items() if v.get("name") == who]
    if len(hit) != 1:
        raise SystemExit("24 §二 里「%s」在 npcs 域匹配到 %d 条" % (who, len(hit)))
    return hit[0]


def side_require(qid, rule, steps, who, npcs):
    """按规则从「步骤」列现取数 → `require`（正则一条都不中 ⇒ 当场抛）。"""
    for pat in rule["pats"]:
        m = pat.search(steps)
        if not m:
            continue
        kind = rule["kind"]
        if kind == "enhance":
            return [{"kind": "enhance", "n": _num(m.group(1))}]
        if kind == "cook":
            return [{"kind": "cook", "n": _num(m.group(1))}]
        if kind == "cook_quality":
            return [{"kind": "cook", "quality": m.group(1), "n": _num(m.group(2) or "一")}]
        if kind == "talk":
            npc = _npc_of(npcs, who)
            if not str((npcs.get(npc) or {}).get("dialogue") or ""):
                raise SystemExit("%s 要的是「跟%s搭话」的条件，但 npcs 域里 %s 没挂对话树"
                                 % (qid, who, npc))
            return [{"kind": "talk", "npc": npc, "n": _num(m.group(1))}]
        if kind == "ask":
            return [{"kind": "ask", "n": _num(m.group(1))}]
        raise SystemExit("%s 的规则 kind「%s」没有对应的条件造法" % (qid, kind))
    raise SystemExit("%s：步骤列「%s」一条规则都不中（文档换写法了？先裁决再落）" % (qid, steps))


#: 悬赏「指定的」那两句（轮换口径的**依据**，两处都写着才算数）
_DAILY_CERTAIN = re.compile(r"打掉\s*\**\s*指定的")
_DAILY_ROTATE = re.compile(r"每天轮换挑一只")


def parse_bounty_daily():
    """24 §二 悬赏板 → 悬赏条件要不要带 `daily`（★ B3-13：轮换落地）。

    依据（现解析，两处都写着才算数）：`打掉**指定的**普通 / 精英 / 头目怪` ＋
    「**指定的** = 悬赏板每天轮换挑一只」。少一句 ⇒ 当场抛（轮换口径变了要有人重新裁决）。
    """
    blk = _bounty_block()
    if not (_DAILY_CERTAIN.search(blk) and _DAILY_ROTATE.search(blk)):
        raise SystemExit("24 §二 悬赏板里「指定的」/「每天轮换挑一只」有一处不在 —— "
                         "轮换口径变了：先裁决再落数据")
    return True


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
    npcs = {k: v for k, v in json.load(io.open(os.path.join(REPO, "content", "data", "npcs.json"),
                                               encoding="utf-8")).items()
            if not str(k).startswith("_")}
    old_text = _read(QFILE)                                   # ★ newline="" ⇒ 原样（全 LF）
    dom = json.loads(old_text)
    num, den = parse_exp_ratio()
    rng = parse_ranges()
    tiers = parse_tiers(monsters)
    egg_gates = parse_egg_gates()
    daily = parse_bounty_daily()                              # ★ B3-13：悬赏「指定的」= 每天轮换
    side_rows = parse_side_rows()                             # ★ B3-13：支线表的「步骤」列
    by_name = {r["name"]: r for r in side_rows.values()}

    planned = {}
    print("真源：经验 = 同级升级需求的 %d/%d（05 §一 ＝ 24 §二）· 报酬区间 %s" % (num, den, rng))
    print("五档表（00 §三 → role_key）：%s" % tiers)
    print("悬赏「指定的」= 每天轮换挑一只：%s（24 §二 那两句都在）" % daily)
    print("24 §二 支线表：%d 行" % len(side_rows))

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
        if daily:                                             # ★ B3-13：只算**当天点名的那一只**
            req[0]["daily"] = True
        cur = v.get("require")
        if cur != req or v.get("reward_exp") != exp:
            planned[k] = {"require": req, "reward_exp": exp,
                          "why": "min_level %d 需求 %d × %d/%d = %d（原 %s）"
                                 "%s" % (v["min_level"], need_, num, den, exp, v.get("reward_exp"),
                                         " · 条件带 daily（每天轮换挑一只）" if daily else "")}

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

    # ③ ★ B3-13：支线那 6 条 —— 按「形状语法」从 24 §二 的「步骤」列现取（数从文档来）
    for qid, rule in sorted(_SIDE_RULES.items()):
        if qid not in dom:
            raise SystemExit("规则表点了 %s，但域里没有这条任务" % qid)
        v = dom[qid]
        row = by_name.get(str(v.get("name") or ""))
        if not row:
            raise SystemExit("%s「%s」不在 24 §二 的支线表里" % (qid, v.get("name")))
        # ★ 条件是从那一格文本推出来的 ⇒ 那一格必须**就是**玩家看到的那句 objective
        #   （对不上 = 两处口径，先裁决；不拿别的措辞去凑条件）
        if row["steps"].replace(" ", "") != str(v.get("objective") or "").replace(" ", ""):
            raise SystemExit("%s：24 §二 步骤「%s」≠ 域 objective「%s」（两处口径，先裁决）"
                             % (qid, row["steps"], v.get("objective")))
        req = side_require(qid, rule, row["steps"], row["who"], npcs)
        if v.get("require") != req:
            planned.setdefault(qid, {})["require"] = req
            planned[qid]["why"] = "%s ⇒ %s" % (rule["why"], json.dumps(req, ensure_ascii=False))

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
