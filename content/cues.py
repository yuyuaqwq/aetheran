# -*- coding: utf-8 -*-
"""表现事件（cue）订阅声明 —— 「结算发事实、表现由订阅方渲染」的内容半边。

引擎那一侧迁了什么
------------------------------------------------------------------
引擎把「战斗结算里顺手拼一句玩家可见文案」改成**发一条表现事件**（cue）；发出来之后
那句话由**内容侧订阅者**渲染（形状与三条硬规矩见引擎 `saintess_engine/cues.py`）。
引擎只管三件事：装配期对账（声明的 cue 名必须条条有订阅）· 同步就地 append · 出问题抛。

本包这一侧只声明一件东西
------------------------------------------------------------------
    {cue 名: ({"kind": "text", "key": <文案表 key>},)}

**句子不在这里** —— 句子在 `content/data/texts.json`，格子名（引擎槽位）在
`content/rules/battle_text.json`。本文件只把「哪个 cue 用哪一格」这一张对应关系说清，
`key` 与 cue 名**同名**（同名即接口，不造映射表 —— 映射表 = 双源温床）。

★ 名单不抄第二份（单一真源）
------------------------------------------------------------------
已迁移的 cue 名集合是**引擎的真源**（`ext_combat.battle.cues.CUE_NAMES`，随批次增长）。
本包在**装配期现读**它来生成订阅表 ⇒ 引擎加一条点位，本表**自动跟上**（这里不用改一行）。
代价与配套：自动跟上的前提是「本包文案表里有那一格」；引擎声明了一条而
`content/rules/battle_text.json` 里没有对应槽位（或那一格在本包里是空的）⇒
`check_domain()` 在装配期**点名抛**（`CueSubsError`）。
为什么必须点名而不是跳过：跳过 = 订阅表里少一条 ⇒ 引擎装配期对账当场抛（那还看得见）；
而「声明在、值是空的」这一态更隐蔽 —— 引擎那条路要求**必须命中**（`render_required`），
表里没这一格 ⇒ 这条 cue 每发一次只出一行坏数据（不静默，但玩家看不到话）。
判决口径：**装配期点名抛** > 运行期一行坏数据 > 静默兜一句。

三条纪律（与 `content/battle_text.py` 同一口径）
------------------------------------------------------------------
1. ⚠️ **绝不静默**：缺槽位 / 空值都在**装配期**现形（`check_domain`），不在这里兜一句自造的话。
2. **不新增第二份文案真源**：本文件零中文文案、零 cue 名字符串（探针有静态守卫那一条）。
3. **不装配 = 引擎走旧路**：引擎树还没有 cue 形状时（`ext_combat.battle.cues` 导不进来）
   本包照跑 —— 那时已迁移点位内部落回 `render_via`，而那张表**也是本包的**（`battle_text.py`）
   ⇒ 屏上逐字节不变。本文件在那种引擎树上不做任何事。
"""
from __future__ import annotations

__all__ = ["CueSubsError", "engine_has_cues", "cue_names", "cue_slots", "check_domain",
           "subs", "cue_subs"]


class CueSubsError(RuntimeError):
    """订阅表装配不出来（引擎声明了 cue、本包却没有对应文案格）—— 装配期当场抛，不静默。"""


def engine_has_cues() -> bool:
    """引擎树有没有 cue 形状（`ext_combat.battle.cues`）—— 判「引擎侧迁移在不在」。"""
    try:
        import ext_combat.battle.cues  # noqa: F401
    except ImportError:
        return False
    return True


def cue_names() -> tuple:
    """引擎侧**已迁移**的 cue 名（唯一真源 = 引擎，本包不抄一份名单）。

    现读（不是 import 期绑定）⇒ 引擎那边加一条点位，本表下一次装配就跟上；探针也靠这一条
    猴补一个假名字进 `CUE_NAMES` 来做反证。
    """
    from ext_combat.battle.cues import CUE_NAMES
    return tuple(str(n) for n in CUE_NAMES)


def cue_slots() -> dict:
    """cue 名 → 本包声明的引擎槽位名（`battle_text.json::slots`；没声明 ⇒ `None`）。"""
    from . import battle_text as BT
    slots = BT.slots()
    return {n: slots.get(n) for n in cue_names()}


def check_domain() -> dict:
    """装配期对账（fail-closed）：引擎声明的每条 cue 都得在本包**取得到话**。

    答不上来 = 玩家那一行只会是一行坏数据（或这条 cue 压根发不出来）⇒ 当场抛并点名是哪条
    cue / 哪一格。返回「cue 名 → 槽位名」（供探针与装配日志用）。
    """
    from . import battle_text as BT
    from . import name_map as _NM          # ★ P2-4b：机器键 → 显示名对账（装配期 fail-closed）
    _NM.check_domain()                     #   少一条显示名 ⇒ 当场点名抛，不静默漏
    names = cue_names()
    decl = BT.slots()                       # `content/rules/battle_text.json::slots`
    tbl = BT.table()                        # 本包真正注入 `Battle(text=…)` 的那张表
    missing = [n for n in names if n not in decl]
    if missing:
        raise CueSubsError(
            "引擎声明了 cue、`content/rules/battle_text.json` 里却没有它的槽位：%s"
            "（引擎侧每加一条点位，本包要同步声明 `%s` → texts 域一格）"
            % ("、".join(missing), missing[0]))
    empty = [n for n in names if not str(tbl.get(n) or "").strip()]
    if empty:
        raise CueSubsError(
            "cue 的文案格在本包表里是空的：%s（引擎那条路要求**必须命中**：表里没这一格 ⇒ "
            "这条 cue 每发一次只出一行坏数据，玩家看不到那句话；去 texts 域把那几格补上）"
            % "、".join("%s → %s" % (n, decl[n]) for n in empty))
    return {n: decl[n] for n in names}


def subs() -> dict:
    """订阅表（引擎形状：`{cue 名: (订阅者, ...)}`，顺序 = 渲染顺序）。

    每条 cue 一个 `kind="text"` 订阅者，`key` == cue 名（同名即接口）——订的是**格子**，
    句子仍在 `battle_text.json` / texts 域里，本文件一个字都不写。
    """
    check_domain()
    return {n: ({"kind": "text", "key": n},) for n in cue_names()}


def cue_subs() -> dict:
    """引擎 hook `cue_subs_fn` 的供体（装配点见 `content/apply.py::install_engine`）。"""
    return subs()
