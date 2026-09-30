# -*- coding: utf-8 -*-
"""加点（五维分配）的**唯一算术出口**（P-34）。

真源口径
--------
· 总点数 = 建号 8 + 每级 3 —— `00_总纲/05_系统总表与阶段开放_v1.md`「五维加点（建号 8 + 每级 3）」
  （同口径另见 `03_职业与技能/00_重做总纲_v2.md` §数值口径：加点 1 级 8 点、每级 +3）
· 建议权重 = 六职业详案那份示例加点 ⇒ 落在 `classes.json` 的 `suggest_alloc`
· 「1 级行 = 职业基础值（**建号 8 点未投**）」（`03_职业与技能/*_v2.md` 表头口径）
  ⇒ 平铺 `flat()` 是**配平基准**（怪物面板就是照它反推的），不是往玩家档上自动填的东西；
  玩家真能投的那个口是 `plan()`（**整数** · 最大余数分摊 · 和恰好 = 总点数）。

为什么单开一个模块（P-34 的病根）
--------------------------------
生成器（`scripts/rebuild_monsters.py`）· 面板（`content/panel_build.py`）· 命令层 · 探针
四处都要「总点数 / 已花 / 余额」。各算一份就是四把尺 —— 这里一个口，别处不许再写一遍。

★ 本模块**只用标准库**（生成器在没挂引擎的路径下也要 import 得动）；也**不 import 包内别的模块**
（免得 `panel_build` ↔ `cmds_ast` 那种环）。五个维名是 ASCII（与 `classes.json` 的
`conv` / `suggest_alloc` 同一套键）—— 中文名走 texts 槽位 `SYS_STAT_*`，代码里不写中文。
"""
from __future__ import annotations

import json
import os

#: 五维（=`classes.json` 的 `conv` / `suggest_alloc` 用的那五个键 · 顺序即呈现顺序）
STATS = ("STR", "AGI", "INT", "VIT", "WIL")

#: 建号给的点 · 每级再给的点（真源见模块抬头；改这两行就是改整条线）
LV1_POINTS = 8
PER_LEVEL_POINTS = 3

_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_CLASSES = None


class AllocError(Exception):
    """加点这条线上的两类错 —— 都当场点名（`fail-closed-boundaries` §1）：

      · **档坏了**：`alloc` 里认不出的维 / 负数 / 小数、或者已花 > 总点数（不可能由本包写出来）
      · **声明错了**：档上的职业不在 `classes` 域里 / 域里那条没有 `suggest_alloc`

    两类都不许静默兜底（"当作没投过"最坏：玩家以为投了、面板没变）。

    ★ **两条文案（台账 L2154）**
      · `str(exc)` = **机器侧原话**，带坏值与字段名，**只进日志**（`_LOG.warning(..., exc_info=True)`）
      · `exc.player_reason` = **玩家那一行的槽位名**（`SYS_ALLOC_SAVE_*` —— ★ 2026-09-29
        收尾批槽位化），只说「哪一类坏」+ 玩家自己看得懂的口径，
        **零机器键 / 零字段名**。`cmds_ast.alloc_points` 的两个 catch 一律填 `player_reason`。

    保留原构造签名（`AllocError("…")` 一字不改）⇒ 17 个既有抛点不必全改；
    缺 `player_reason` 时由 `__init__` 按**参数个数**回落到一个分类句（见下）。
    """

    def __init__(self, msg: str, player_reason: str = None):
        super().__init__(msg)
        self.player_reason = player_reason or _classify(msg)

    def __repr__(self):            # 让黑盒探针/异常树里能一眼看到玩家那一行
        return "AllocError(%r, player_reason=%r)" % (str(self), self.player_reason)


#: 坏值 → 玩家那一行（**零机器键**）。
#: ★ 顺序敏感：先按「消息里出现的是哪一类坏值形状」判，判不出再回落通用句。
#:   刻意**不**把坏值本身写进来 —— 那正是 L2154 要治的（`'ZZZ'` / `'abc'` 上屏）。
#:   五维名（STR/AGI/…）**不算**机器键（它们是玩家在「加点 力量」里认得的键，
#:   且 `_stat_slot` 本来就把它们翻成中文显示名），但**坏掉的键**不是。
def _classify(msg: str) -> str:
    """机器侧原话 → 玩家那一行的**槽位名**（分类句，零机器键）。

    ★ 2026-09-29 文案收口收尾：返回值从「内联句子」改成**槽位名**（`SYS_ALLOC_SAVE_*`
    —— 真源 17_「收尾批」十六条）—— 消费点 `T("SYS_ALLOC_BAD_SAVE", why=T(e.player_reason))`
    负责取文案（`T()` 是字面 replace，嵌套一层即可）。内联清零（probe_copy ② 红转绿）。"""
    if "不是一份表" in msg:
        return "SYS_ALLOC_SAVE_SHAPE"
    if "认不出的维" in msg:
        return "SYS_ALLOC_SAVE_STAT"
    if "不是有限数" in msg:
        return "SYS_ALLOC_SAVE_NAN"
    if "不是数字" in msg:
        return "SYS_ALLOC_SAVE_NOTNUM"
    if "是负数" in msg:
        return "SYS_ALLOC_SAVE_NEG"
    if "是小数" in msg:
        return "SYS_ALLOC_SAVE_FRAC"
    if "不是整数" in msg:
        return "SYS_ALLOC_SAVE_LVINT"
    if "不是一个数" in msg:
        return "SYS_ALLOC_SAVE_LVNUM"
    if "至少 1" in msg:
        return "SYS_ALLOC_SAVE_ONE"
    if "已花" in msg and "总点数" in msg:
        return "SYS_ALLOC_SAVE_OVER"
    if "不在 classes 域里" in msg:
        return "SYS_ALLOC_SAVE_CLASS"
    if "没有 suggest_alloc" in msg:
        return "SYS_ALLOC_SAVE_SUGGEST"
    return "SYS_ALLOC_SAVE_UNKNOWN"


def classes() -> dict:
    """`classes` 域（本模块只读它一份 JSON —— 不 import `panel_build`，免得成环）。"""
    global _CLASSES
    if _CLASSES is None:
        with open(os.path.join(_DATA, "classes.json"), encoding="utf-8") as f:
            _CLASSES = json.load(f)
    return _CLASSES


# ══════════════════════════════════════════════════════════════
# 一、点数：等级 → 总点数 − 已花 = 余额（**唯一口**）
# ══════════════════════════════════════════════════════════════
def level_of(level) -> int:
    """等级取值的**唯一校验口**：正常化到 ≥1 的整数，认不出就点名抛。

    ★ 台账 L2153-3：`total_points` 原来是裸的 `max(1, int(level or 1))`，
      坏等级会带着 **CPython 原生** `ValueError: invalid literal for int() ...`
      / `TypeError: int() argument must be ...` 逃出本模块 —— 而 `AllocError`
      的类 docstring 承诺的是「加点这条线上的两类错……**都当场点名**」。
      调用方 `content/cmds_ast.py:1494` 只 `except AL.AllocError`
      ⇒ 坏 `level` 直接冒泡，玩家看到裸英文异常文案。
      这里只把**认不出的等级**收成 `AllocError`（本模块自己那一类），
      合法等级（含 `"3"` 这种字符串数字）的取值逐字节不变。
    """
    if level is None or level == "":
        return 1
    if isinstance(level, bool) or not isinstance(level, (int, float, str)):
        raise AllocError("等级不是一个数：%r" % (level,))
    try:
        lv = int(level)
    except (TypeError, ValueError):
        raise AllocError("等级不是一个整数：%r" % (level,)) from None
    return lv if lv >= 1 else 1


def total_points(level) -> int:
    """该等级一共该有多少点（建号 8 + 每级 3）。**不落档** —— 等级改了它自动跟着改。"""
    return LV1_POINTS + PER_LEVEL_POINTS * (level_of(level) - 1)


def spent(alloc) -> int:
    """档上那一格 `alloc` 已经投出去多少点（认不出的维 / 非数字 / 负数 ⇒ `AllocError`）。

    ★ 值可以是整数，也可以是**小数** —— 小数只可能来自**配平基准 / 测试档**
      （`flat()` 是浮点平铺：怪物面板就是照它反推的），玩家自己投的永远是整数
      （写入那一步由 `apply()` 把关）。读取这一口**不截断**（截断就是静默改数）。
    """
    if alloc in (None, "", {}):
        return 0
    if not isinstance(alloc, dict):
        raise AllocError("alloc 不是一份表（%r）" % (alloc,))
    total = 0
    for stat, n in alloc.items():
        if str(stat) not in STATS:
            raise AllocError("认不出的维：%r（五维：%s）" % (stat, " / ".join(STATS)))
        if isinstance(n, bool) or not isinstance(n, (int, float)):
            raise AllocError("%s 那一格不是数字：%r" % (stat, n))
        if float(n) != float(n) or float(n) in (float("inf"), float("-inf")):
            raise AllocError("%s 那一格不是有限数：%r" % (stat, n))
        if float(n) < 0:
            raise AllocError("%s 那一格是负数：%r" % (stat, n))
        total += n
    return int(total) if float(total).is_integer() else total


def balance(level, alloc) -> int:
    """还剩几点 = 总点数 − 已花。**超投 ⇒ `AllocError`**（那是档坏了，不是"不够"）。"""
    total = total_points(level)
    used = spent(alloc)
    if used > total:
        raise AllocError("已花 %s 点 > 该等级的总点数 %d（等级 %s）" % (used, total, level))
    left = total - used
    return int(left) if float(left).is_integer() else round(left, 3)


def apply(alloc, stat, n) -> dict:
    """把 n 点投到 stat 上 —— 返回**新表**（不动入参）。

    ★ 只有**整数**能进这一口：玩家投的点不可分。档上若原本带着小数（配平基准 / 测试档），
      这里**当场抛**（`AllocError`）而不是悄悄截断 —— 截断就是静默改数（fail-closed §1）。
    """
    key = str(stat or "")
    if key not in STATS:
        raise AllocError("认不出的维：%r（五维：%s）" % (stat, " / ".join(STATS)))
    # ★ 台账 L2153-1：这一行原来是 `cnt = int(n)` —— 与本函数 docstring 第一段
    #   （「只有**整数**能进这一口……当场抛而不是悄悄截断」）**直接矛盾**，实测
    #   `apply({"STR":10},"STR",1.7)` ⇒ `{'STR':11}`（1.7 静默截成 1）、
    #   `apply({"STR":10},"STR",-5)` ⇒ `{'STR':5}`（**收负数 = 白扣 5 点**）、
    #   `apply({"STR":10},"STR",True)` ⇒ `{'STR':11}`（bool 被 `int()` 当 1 收）。
    #   静默改数正是本模块承诺要治的那件事（fail-closed §1），故当场点名抛。
    #   与下面「档上每一格」那段**同一把尺**：bool 不算数字、小数不放行、非正数不收。
    if isinstance(n, bool) or not isinstance(n, (int, float)):
        raise AllocError("要投的点数不是数字：%r" % (n,))
    if float(n) != float(n) or float(n) in (float("inf"), float("-inf")):
        raise AllocError("要投的点数不是有限数：%r" % (n,))
    if float(n) != int(n):
        raise AllocError("要投的点数是小数（%r）—— 点不可分，档上只有整数才敢往上加" % (n,))
    cnt = int(n)
    if cnt < 1:
        raise AllocError("要投的点数必须至少 1（%r）—— 投 0 或负数不是「加点」" % (n,))
    out = {}
    for k, v in (alloc or {}).items():
        k = str(k)
        if k not in STATS:
            raise AllocError("认不出的维：%r（五维：%s）" % (k, " / ".join(STATS)))
        if float(v) != int(v):
            raise AllocError("%s 那一格是小数（%r）—— 档上只有整数才敢往上加" % (k, v))
        out[k] = int(v)
    out[key] = out.get(key, 0) + cnt
    return {k: out[k] for k in STATS if k in out}          # 稳定顺序（呈现不用再排）


# ══════════════════════════════════════════════════════════════
# 一之二、**「这一档实际分了多少」的唯一口**（★ P-34 的接口名，见 `_notes.md`）
# ══════════════════════════════════════════════════════════════
#: 上游（装备门槛 · 呈现 · 战斗）要问「这档分了多少 / 还剩几点」时**只走下面三个**：
#:     alloc.of_record(record)         → 分配结果  {维: 点数}（缺 = 空表；坏档 ⇒ AllocError）
#:     alloc.spent_of_record(record)   → 这档实际分了多少点（= sum(分配结果)）
#:     alloc.left_of_record(record)    → 还剩几点（总点数 − 已花；超投 ⇒ AllocError）
#: 与 `flat()` / `plan()` 的分工：那两个是**按职业 + 等级**推的参照上界 / 建议投法；
#: 这三个是**按档**读的现实。别处不许再 `record.get("alloc")` 之后自己算（那就是第二把尺）。
def of_record(record) -> dict:
    """档 → **这档的加点**（归一化成 `{维: 点数}`；稳序；`alloc` 那一格坏 ⇒ `AllocError`）。

    ★ 「归一化」= 只留五维、按 `STATS` 稳序、缺 = 空表；**值不截断**（小数照原样读出来 ——
      那只能是配平基准 / 测试档；玩家档上是整数，写入由 `apply()` 把关）。
    """
    rec = record if isinstance(record, dict) else {}
    raw = rec.get("alloc")
    if raw in (None, "", {}):
        return {}
    spent(raw)                                  # 校验走同一个口（认不出的维 / 非数 / 负数都抛）
    return {s: raw[s] for s in STATS if s in raw}


def spent_of_record(record) -> int:
    """档 → 已投的点数（= `sum(of_record(record).values())`）。"""
    return spent(of_record(record))


def left_of_record(record) -> int:
    """档 → 还剩几点可投（等级决定总点数；超投 ⇒ `AllocError`）。"""
    rec = record if isinstance(record, dict) else {}
    return balance(rec.get("level"), of_record(rec))


# ══════════════════════════════════════════════════════════════
# 二、建议：权重 → 平铺（配平基准）· 整数投法（玩家真能敲的那个）
# ══════════════════════════════════════════════════════════════
def weights(cls_id) -> dict:
    """职业的**建议权重**（六职业详案那份示例加点 · `classes.json` 的 `suggest_alloc`）。"""
    cid = str(cls_id or "").strip()
    rec = classes().get(cid)
    if rec is None:
        raise AllocError("职业 %r 不在 classes 域里（有的：%s）"
                         % (cid, " · ".join(sorted(classes()))))
    sug = rec.get("suggest_alloc")
    if not isinstance(sug, dict) or not sug:
        raise AllocError("职业 %r 没有 suggest_alloc（建议权重是唯一来源，缺了不猜）" % cid)
    # ★ 2026-09-30 审计残余 #8（fail-closed 最后一道口）：键 ⊆ STATS + 值是**正有限数**。
    #   坏数据在源头拦住——以前直接 `dict(sug)` 返回，下游 `flat()`/`plan()` 会
    #   ZeroDivisionError（全 0 权重）/ 负权重 / TypeError 逃出本模块，而 `AllocError`
    #   的类承诺「加点这条线上的错都当场点名」。这两条不变式同时保证 flat/plan 的除数
    #   `base = sum(值) > 0` —— 那两处不再各兜一道（审计建议的两条校验合并在本口）。
    for _k, _v in sug.items():
        if _k not in STATS:
            raise AllocError("职业 %r 的 suggest_alloc 有认不出的维：%r（五维：%s）"
                             % (cid, _k, " / ".join(STATS)))
        if isinstance(_v, bool) or not isinstance(_v, (int, float)):
            raise AllocError("职业 %r 的 suggest_alloc[%s] 不是数字：%r" % (cid, _k, _v))
        if float(_v) != float(_v) or float(_v) in (float("inf"), float("-inf")):
            raise AllocError("职业 %r 的 suggest_alloc[%s] 不是有限数：%r" % (cid, _k, _v))
        if float(_v) <= 0:
            raise AllocError("职业 %r 的 suggest_alloc[%s] 不是正数：%r（全 0 ⇒ 平铺要除以 0）"
                             % (cid, _k, _v))
    return dict(sug)


def flat(level, cls_id) -> dict:
    """按建议权重把该等级的点**平铺**出去（浮点 · 配平基准）。

    ★ 与 `scripts/rebuild_monsters.py` 那把尺**逐字同形**（那边已改成调本函数）——
      怪物面板就是照它反推的：改这里 = 改配平。
    """
    sug = weights(cls_id)
    base = sum(sug.values())
    total = total_points(level)
    return {stat: total * w / base for stat, w in sug.items()}


def plan(level, cls_id) -> dict:
    """**建议投法**（整数 · 和恰好 = 该等级的总点数）——「照它投就是配平基线」那一份。

    最大余数分摊：先按权重取整（向下），余下的点按**小数部分**从大到小补（并列按权重降序、
    再按 `STATS` 顺序定死 —— 同一份输入永远同一份输出）。
    """
    sug = weights(cls_id)
    base = sum(sug.values())
    total = total_points(level)
    exact = {s: total * w / base for s, w in sug.items()}
    out = {s: int(v) for s, v in exact.items()}
    rest = total - sum(out.values())
    order = sorted(exact, key=lambda s: (-(exact[s] - int(exact[s])), -sug[s],
                                         STATS.index(s) if s in STATS else len(STATS)))
    for s in order[:max(0, rest)]:
        out[s] += 1
    return {k: out[k] for k in STATS if k in out}
