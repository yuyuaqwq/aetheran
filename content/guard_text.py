# -*- coding: utf-8 -*-
"""《阿斯特兰》内置守卫拦截句（P-11 · 2026-09-27）—— 引擎 `guard_text_fn` 的内容半边。

口径（唯一真源 = texts 域那两条槽位；本模块不写中文文案）
------------------------------------------------------------------
引擎 `saintess_engine/host/runtime.py::Host._guard_text()` 按 P-11 起把**内置守卫**
（`player` / `battle`）的拦截句交给内容侧渲染：宿主在 `Host(register_hint=…, battle_hint=…)`
上只传**中性键**（引擎 `GUARD_KEYS` 全集：`guard.register_missing` / `guard.battle_missing`），
句子由内容侧经 `config.mount(guard_text_fn=fn)` 给 —— 形状 `fn(key) -> str | None`。

⇒ **本包不挂这个口**，守卫拦下的那一句就当场抛（`EngineNotConfigured`）：
引擎既不替它编兜底、也**不把键名当句子投给玩家**（宿主面因此一个游戏词都不带）。
原先这两句是宿主 `main.py` 里的中文常量（宿主面因此带「角色」「战斗」这类业务词，
宿主自己的零游戏知识门禁恒红）—— P-11 把句子搬进包、宿主只留键。

三件
------------------------------------------------------------------
① `line(key)`   —— `guard_text_fn` 供体：引擎给的中性键 → 一句玩家看得见的话（槽位渲染）。
   代码里零中文（句子真源在 texts 域；本模块只认槽位名）；
② `SLOTS`       —— 中性键 → 本包槽位名（**键名取自引擎 `GUARD_KEYS`**，不手写镜像句子）；
③ `check_domain()` —— 装配期对账（fail-closed）：映射的键集 == 引擎的中性键全集
   + 两条槽位都在 texts 域里且真有字（撤改验证那一条在 `scripts/probe_guard_text.py`）。
"""
from __future__ import annotations

from saintess_engine.host.runtime import GUARD_KEYS

from .cmds_ast import MISSING_MARK, T
#: texts 域的**唯一**读口（与 `T` 同一份缓存 —— 本模块不再自己读一遍文件）
from .cmds_ast import _texts as _table

#: 中性键 → texts 槽位。★ 键名**从引擎那份全集取**（不手写字符串镜像）：
#:   引擎加了键 / 改了名，`check_domain()` 当场红，而不是等玩家撞上。
#: ★ 键→槽位只认**键名**，不认下标（审计 L2614-1：原先写 `GUARD_KEYS[0]/[1]`）。
#:   引擎那个元组是**位置元组**（`runtime.py:53`）、两键的语义只靠下标约定 ⇒ 一换序就是
#:   **两句玩家可见文案整体对调**，而 `check_domain()` 只比 `set()` → 照样绿。
#:   引擎不导出这两个键的**名字常量**，只有全集 ⇒ 故下这两个本包认的键名，
#:   并在 `check_domain()` 里逐键**点名**比对（第 1 条建议）。
GUARD_REGISTER_KEY = "guard.register_missing"
GUARD_BATTLE_KEY = "guard.battle_missing"
SLOTS = {
    GUARD_REGISTER_KEY: "SYS_GUARD_REGISTER",
    GUARD_BATTLE_KEY: "SYS_GUARD_BATTLE",
}

#: 取不到文案时 `T` 回的那串标记 —— 真源在 `cmds_ast.MISSING_MARK`（审计 L2614：原先逐字硬编码）
_MARK = MISSING_MARK


def _missing(slot):
    """取不到文案时的异常（消息里带槽位名 —— 给写代码的人看，不是玩家文案）。"""
    return KeyError("守卫拦截句取不到文案（槽位 %r 不在 texts 域里）" % (slot,))


def slot_of(key) -> str:
    """中性键 → 槽位名（不在映射里 ⇒ 抛：引擎问了个本包不认的键）。"""
    slot = SLOTS.get(str(key))
    if slot is None:
        raise KeyError("引擎问的守卫键不在本包的槽位映射里：%r" % (key,))
    return slot


def line(key) -> str:
    """`guard_text_fn` 供体：引擎给的中性键 → 一句玩家看得见的话（槽位渲染）。

    ★ 取不到文案 ⇒ 当场抛（**不把那串标记漏给玩家**）：这一格是引擎守卫的唯一句源，
      引擎那头「装了却给不出文本 ⇒ 抛」的同一条规矩，本包这一头照办。
    """
    slot = slot_of(key)
    # ★ 判据打在**记录**上，不打在渲染结果上（审计 L2614 · 高）：守卫句不嵌玩家输入，
    #   但「渲染结果里没有标记串」并不等于「取到了文案」—— 上游把标记文案一改，
    #   这条检查就静默失效、标记串被原样投给玩家（docstring 承诺过绝不漏）。
    #   真正该问的是「那一条槽位在不在 texts 域里、有没有字」。
    rec = _table().get(slot) or {}
    if not rec or _MARK in str(rec.get("value") or "") or not str(rec.get("value") or "").strip():
        raise _missing(slot)
    return str(T(slot))


def check_domain() -> dict:
    """装配期对账（fail-closed）：① 映射的键集 == 引擎的中性键全集 ② 两条槽位都真有字。 ③ 逐键点名对应槽位。

    ② 是这一条的要点：宿主只传键，**句子在这两条槽位里** —— 缺一条，守卫拦下时玩家拿到的
    是抛错，不是一句人话。① 防的是「引擎加了键、本包没跟」（那时会静默少一句）。
    ③ 防的是「键对不对应槽位」（集合相等看不出，需逐键点名）。
    """
    keys, want = set(SLOTS), set(GUARD_KEYS)
    if keys != want:
        raise KeyError("守卫键映射与引擎的中性键全集不一致：本包 %s / 引擎 %s"
                       % (sorted(keys), sorted(want)))
    # ★ L2614-1：逐键**点名**比对——集合相等只能防「加/删键」，防不住
    #   「锠射错位」（下标对调 / 键名对调）。两句文案是**玩家可见**的，
    #   对调了也看不出来（文案都有字、键集也相等）——故此处逐键报名。
    for key, want_slot in ((GUARD_REGISTER_KEY, "SYS_GUARD_REGISTER"),
                           (GUARD_BATTLE_KEY, "SYS_GUARD_BATTLE")):
        got = SLOTS.get(key)
        if got != want_slot:
            raise KeyError("守卫键 %r 应对应槽位 %r，现映的是 %r（两句玩家可见文案会"
                           "整体对调）" % (key, want_slot, got))
    out = {}
    for key in sorted(SLOTS):
        slot = SLOTS[key]
        value = str((_table().get(slot) or {}).get("value") or "")
        if not value.strip() or _MARK in value:
            raise KeyError("守卫拦截句槽位 %r 不在 texts 域里（或空着）—— 守卫拦下时玩家"
                           "拿到的会是抛错，不是一句人话" % (slot,))
        out[key] = _table()[slot]
    return out
