# -*- coding: utf-8 -*-
"""引导层（copy-p5 车道 · 2026-09-29）—— B 档「有目标感」的**唯一实现面**。

★ 鱼鱼原话：「想开始玩游戏啥的都没什么引导」+「可以加点仪式感」。
  实测底账（本车道开工时现取）：引导族槽位 **0 个**
  （`grep -E "GUIDE|ONBOARD|WELCOME|TUTOR|INTRO" content/data/texts.json` 零命中）
  ⇒ 病根不是「引导不够丰富」，是**根本没有这一层**。

★ 交付形状 = A 档 + B 档（`text-rpg-interface-spec` §8 的三档方案，本车道按他那条
  「选 B 档」的口径落 B；**C 档「锁前 N 分钟」明确不做** —— 它要新状态机 + 新存档字段，
  且与已定产品口径 P-69「建号这段每多一步都在掉人」正面冲突）：

    A  ① 开场白（新槽位）   ② 建号三步各一个**标题块**
    B  ③ 第一件委托**自动派**（建号完成即挂上）  ④ 面板顶栏「当前该做：⋯」

★ **不加新步骤**（守 P-69）：标题块是**加在原有那三步的头顶**，不是新步骤。
  建号仍是 `cmds_ast.BUILD_STEPS = ("race", "class", "name", "town")` 四格，一个没多。

★ **新状态只落一格** `flags.current_goal`（键 = 机器键，玩家看不到；抄 `flags.card` /
  `flags.quests_active` 那族既有形状）—— **不新建状态机**：
  · 那一格**是派生态**（现算得出来 ⇒ 谁是权威？），但真源要求它**落档**（玩家在野外、
    换进程回来时顶栏要跟着走）⇒ 写档 + 每次读档前**现算校正**（`refresh_goal`）。
  · 判据 = `scripts/probe_onboard.py`（本层 5 条，见文件抬头）。
  · 承载槽位一律走 `T(...)`，本模块**不写一个字中文**（呈现口只传槽位）。
"""
from __future__ import annotations

#: 顶栏那行前缀 —— 槽位名现算（`SYS_ONBOARD_GOAL`）不放这里，值全在 texts 域。
#: ★ 机器键（不是中文）：代码只许比 `kind_key` 那一族，机器键由本层**一个口**现算。

#: 建号四步（`cmds_ast.BUILD_STEPS`）在本层要用的**槽位前缀**：
#:   第一步 = 定族 / 第二步 = 定职业 / 第三步 = 取名 / 第四步 = 进镇
#: ★ 与 `cmds_ast.BUILD_STEPS` 同序同长 —— 那一条是唯一真源，本层**只读不改**。

#: 第一件委托（自动派的那一条）—— **现取**自 quests 域的 `order == 1` 主线，
#: 本模块不写死 id（域里改了就跟着改）。
FIRST_ORDER = 1


#: 建号那一步的**呈现名**（顶栏那一句用）—— ★ 不是机器键：机器键绝不许上屏
#: （`content/probe_machine_key_names.py` 那一族钉着，顶栏也在它的视野里）。
#: 一格一句，各说各的（不许三条同句式 —— 那会立刻顶高复读率）。
STEP_WHAT = {
    "race":  "SYS_ONBOARD_WHAT1",
    "class": "SYS_ONBOARD_WHAT2",
    "name":  "SYS_ONBOARD_WHAT3",
}


def step_of(p) -> str:
    """建号走到第几步（`race` / `class` / `name` / `town` / `""` 已完成）。

    ★ 与 `cmds_ast.BUILD_STEPS` 同一条：返回的每个值都是那四格里的一格，
      `""` 表示**四步都走完了**（`town` 那格 = 已进镇）。不新造状态机 —— 它**现算**。
    """
    if not (p or {}).get("race"):
        return "race"
    if not (p or {}).get("cls"):
        return "class"
    if not str((p or {}).get("name") or "").strip():
        return "name"
    return "town"


def _has_text(key) -> bool:
    """那一格文案**取得到吗**（渲染口 fail-closed ⇒ 取不到 = 当场显形，不静默编一句）。

    ★ 为什么要自己判一遍：顶栏那一行是**可选显示**的（不显示比印一行占位符好），
      但直接 `T()` 会在缺文案时把 `[MISSING TEXT …]` **印到玩家屏上** —— 那是
      开发口吻漏到屏上。⇒ 这一层自己先判，取不到就**不显示这一行**，
      并由 `probe_onboard` ④ 钉住「不许出现缺文案标记」。
    """
    from .cmds_ast import T, _texts, MISSING_MARK
    probe = T(key)
    return not str(probe).startswith(MISSING_MARK)


def goal_text(p) -> str:
    """面板顶栏「当前该做：⋯」那一格的**正文**（不含前缀，前缀在槽位里）。

    ★ 四档（从上往下第一个成立的）：
      ① 建号没走完  → 指那一步（**不给指令名**：一屏只许有一个，判据见 probe_onboard ②）
      ② 手上有活    → 委托名 + objective（与『提示』`_hint_lines` **同一把尺**）
      ③ 一条没接    → 第一件委托（自动派之前那一瞬的兜底）
      ④ 都没了      → 回落句（`SYS_ONBOARD_GOAL_IDLE`）
    """
    from .cmds_ast import T
    from .cmds_quest import _hint_lines, _quests, _mine
    step = step_of(p)
    if step in STEP_WHAT:
        # ★ 2026-09-29 文案收口收尾：STEP_WHAT 值改槽位名（内联清零）——嵌套取一遍。
        return T("SYS_ONBOARD_GOAL_STEP", what=T(STEP_WHAT[step]))
    qs = _quests()
    act = _mine(p)
    if act:
        k = act[0]
        x = qs.get(k) or {}
        return T("SYS_ONBOARD_GOAL_JOB", name=x.get("name", k),
                 objective=x.get("objective", ""))
    first = first_quest_id()
    if first and first not in (p.get("flags") or {}).get("quests_done", []):
        return T("SYS_ONBOARD_GOAL_FIRST", name=(qs.get(first) or {}).get("name", first))
    return T("SYS_ONBOARD_GOAL_IDLE")


def goal_line(p) -> str:
    """顶栏那一整行（`SYS_ONBOARD_GOAL` = 前缀 + 正文）。空串 = **不许显示**。"""
    from .cmds_ast import T
    if not _has_text("SYS_ONBOARD_GOAL"):
        return ""                        # ★ 缺文案 ⇒ 这一行不显示（绝不印缺文案标记）
    body = goal_text(p)
    if not body:
        return ""
    return T("SYS_ONBOARD_GOAL", body=body)


def first_quest_id() -> str:
    """第一件委托的 id —— **现算**（`quests` 域里 `order == FIRST_ORDER` 的那条）。

    ★ 不写死 `q_main_01`：域里换 id / 加一条更早的，这一句跟着改。
      取不到（域缺 / 没有 order=1）⇒ 回 `""`（调用方当「没有第一件」，不静默编一条）。
    """
    from .cmds_quest import _quests
    best, bo = "", None
    for k, x in (_quests() or {}).items():
        o = x.get("order")
        if o == FIRST_ORDER:
            return k
        if isinstance(o, int) and (bo is None or o < bo):
            best, bo = k, o
    return best


def refresh_goal(p) -> bool:
    """把顶栏那格**校正**到现算值 —— 返回「有没有变」（变了 = 调用方要落档）。

    ★ 为什么每次都要现算：那一格是**派生态**（建号进度 / 手上的活随时在变）。
      只在「写进去那一刻」算一次 ⇒ 建号走完第二步顶栏还指着「你怎么打」。
      落档用**同一个键**、同一个算法 ⇒ 不存在两处口径。
    """
    fl = dict(p.get("flags") or {})
    body = goal_text(p)
    if fl.get("current_goal") == body:
        return False
    fl["current_goal"] = body
    p["flags"] = fl
    return True


def auto_first_quest(p, quests) -> bool:
    """第一件委托**自动派**（建号走完那一刻）—— 返回「有没有派」。

    ★ 口径（B 档 ③）：
      · 派**哪一条** = `first_quest_id()`（域里 order==1 那条，现算）
      · **不绕 `quest_accept` 的三道门**（见习证 / 等级 / 已接过）—— 那是「玩家自己去接活」
        的守卫；这一件是**系统派给他上手的第一件事**，在公会谈活之前、在城里，
        照 B4-27 那道门会把玩家卡在「先办证」上 ⇒ 第一件没有证。
        ⇒ 但**不是把守卫删掉**：只对这一条、只在「一件都没接过」时派，且**必须能重复调用**
          （幂等：已派过 / 交过 / 手上已有活 ⇒ 一律不回派）。
      · **发不发东西** = 走 `quest_accept` 那同一对 `_hand_over` / `_set_base`（不重写一遍），
        否则第一件委托接时不给东西 = 玩家看见一件没有起步道具的活。
    """
    from .cmds_quest import _mine as _mine_q
    if _mine_q(p):
        return False
    if (p.get("flags") or {}).get("quests_done"):
        return False                       # 交过活的人不是新玩家，不再补第一件
    k = first_quest_id()
    if not k:
        return False
    x = (quests or {}).get(k) or {}
    if not x:
        return False
    if int(p.get("level", 1) or 1) < int(x.get("min_level", 1) or 1):
        return False                       # 等级不够就不派（不绕那一道）
    fl = dict(p.get("flags") or {})
    act = list(fl.get("quests_active") or [])
    if k in act:
        return False
    from .cmds_quest import _hand_over, _require_of, _set_base
    if _require_of(x):
        _set_base(p, k, x)
    gained = _hand_over(p, x)
    fl["quests_active"] = act + [k]
    p["flags"] = fl
    return bool(gained) or True
