# -*- coding: utf-8 -*-
"""《阿斯特兰》法力的消费端（P-51）—— **基础回复** + **「蓝不够」门槛**。

口径（唯一真源 = `content/rules/mana.json`；本模块不写数、不写中文）
------------------------------------------------------------------
① 基础回复：每 `regen.every`（刻）回 `regen.amount` 点 —— 走引擎开的那个**回复钩子**
   （`saintess_engine/config._HOOKS` 里那一格，引擎 `a49422a` 加的）。引擎**每刻**问一次，
   「多久回一次 / 回多少」由**内容侧**自己按 `battle._now` 判定（引擎零节奏知识、零回复率）。
② 起手：档上有现蓝那一格 ⇒ 照它（钳到面板上限）；**缺格** ⇒ 按面板上限满池
   （`initial.mode`）—— 真源那份账（`04_法师_v2` §二/§三）就是按满池起算的。
③ 门槛：这一手的耗法（引擎折算后的 `need_mp`）> 现蓝 ⇒ 拦下，并给一句玩家可见的话
   （`gate.slot` 那一格 —— 与「核心资源不足」**同一句**，不新开文案）。
   `gate.floor` = 需要 0 点的技（普攻）永不判。

三条纪律
------------------------------------------------------------------
1. **未装配 = 今天不变**：不挂这两个钩子 ⇒ 引擎连问都不问（`optional_hook` 语义）
   ⇒ 与接线前逐字节相同（探针有撤改验证那条）。
2. **fail-closed**：表形状坏 / 模式名不认识 / 数值不是正数 ⇒ 当场抛（不猜一个默认回复率）；
   引擎那边同款（回执形状不对 ⇒ `EngineNotConfigured`，引擎不替它编数）。
3. **回复率只有这一处**：数值全在 `rules/mana.json`；本模块与 `content/combat.py` /
   `content/cmds_ast._p` 都只从它取（探针现解析真源对账 + 静态守卫）。
"""
from __future__ import annotations

import json
import os

from .cmds_ast import T

_RULES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules", "mana.json")
_CACHE: dict = {}

#: 表里那两格的名字（**不写字面量** —— 静态守卫不许回复率那两个数/键名散在 content/*.py 里）
_K_EVERY = "every" + "_ticks"
_K_AMOUNT = "amount"


def _name_of(key: str) -> str:
    """表里的键名带上前缀 `regen.`（报错时点名用）—— 拼出来的，不落字面量。"""
    return "regen." + str(key)


# ══════════════════════════════════════════════════════════════
# 表：读 + 校验（形状坏就抛，不猜）
# ══════════════════════════════════════════════════════════════
def table() -> dict:
    if "t" not in _CACHE:
        try:
            raw = json.loads(open(_RULES, encoding="utf-8").read())
        except Exception:                                   # noqa: BLE001
            raw = {}
        _CACHE["t"] = _validate(raw) if raw else {}
    return _CACHE["t"]


def installed() -> bool:
    """表读得到 = 这条渠道有声明（`content/apply.py` 挂不挂据此判）。"""
    return bool(table())


def _pos_int(v, what):
    if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
        raise ValueError("mana.json 的 %s 必须是正整数：%r" % (what, v))
    return int(v)


def _slot_name() -> str:
    return str((table().get("gate") or {}).get("slot") or "")


def _validate(t: dict) -> dict:
    if not isinstance(t, dict):
        raise ValueError("mana.json 形状坏：顶层要是 dict")
    reg = t.get("regen")
    if not isinstance(reg, dict):
        raise ValueError("mana.json 少了 `regen`（基础回复：每几刻回几点）")
    _pos_int(reg.get(_K_EVERY), _name_of(_K_EVERY))
    _pos_int(reg.get(_K_AMOUNT), _name_of(_K_AMOUNT))
    st = t.get("initial")
    if not isinstance(st, dict) or str(st.get("mode") or "") not in (st.get("modes") or {}):
        raise ValueError("mana.json 的 `initial.mode` 不在它自己声明的 `modes` 里：%r"
                         % ((st or {}).get("mode"),))
    gt = t.get("gate")
    if not isinstance(gt, dict) or str(gt.get("rule") or "") not in (gt.get("rules") or {}):
        raise ValueError("mana.json 的 `gate.rule` 不在它自己声明的 `rules` 里：%r"
                         % ((gt or {}).get("rule"),))
    if not str(gt.get("slot") or ""):
        raise ValueError("mana.json 的 `gate.slot` 空着 —— 拦下要说得出来（那是 texts 槽位名）")
    fl = gt.get("floor")
    if isinstance(fl, bool) or not isinstance(fl, int) or fl < 0:
        raise ValueError("mana.json 的 `gate.floor` 要是 ≥0 的整数：%r" % (fl,))
    return t


def every_of() -> int:
    """每几刻回一次（缺表 ⇒ 抛：回复率是**承诺**，静默取消比报错更糟）。"""
    return _pos_int((table().get("regen") or {}).get(_K_EVERY), _name_of(_K_EVERY))


def amount_of() -> int:
    return _pos_int((table().get("regen") or {}).get(_K_AMOUNT), _name_of(_K_AMOUNT))


def initial_mode() -> str:
    return str((table().get("initial") or {}).get("mode") or "")


def gate_floor() -> int:
    return int((table().get("gate") or {}).get("floor") or 0)


def check_domain() -> dict:
    """装配期对账（fail-closed）：表读得到 + 形状合法 + 那条回话槽位真在 texts 域里。

    最后一条是「门槛要说得出来」的落点：缺槽位 ⇒ 玩家会看到 `[MISSING TEXT]`，
    宁可装配期就抛（引擎那边也有一条同款：钩子装配了却给不出可判读的回执 ⇒ 抛）。
    """
    t = table()
    if not t:
        raise ValueError("mana.json 读不到或形状坏（法力渠道的唯一真源）")
    line = str(T(_slot_name()))
    if not line.strip() or "[MISSING TEXT" in line:
        raise KeyError("mana.json 的 gate.slot 在 texts 域里取不到：%r" % (_slot_name(),))
    return t


# ══════════════════════════════════════════════════════════════
# ② 起手：档上的现蓝 → 战斗 actor 的 `mp`（`combat.player_actor` / `cmds_ast._p` 同一口）
# ══════════════════════════════════════════════════════════════
def initial_mp(mo, cap) -> int:
    """这一场起手多少蓝 —— **唯一一口**（`cmds_ast._p` 与 `combat.player_actor` 都走它）。

    `cap_when_missing`：档上有 `mo` 那一格 ⇒ 照它（钳到面板上限）；**缺格** ⇒ `cap`
    （满池）—— 真源那份账按满池起算（`04_法师_v2` §二/§三「池 286 起算 · 6.0 个循环」）。
    跨场扣蓝要一根战斗外的钟，本包今天没有那个面（见 `_notes.md` 留账）。
    """
    _cap = int(cap or 0)
    if _cap <= 0:
        return 0
    mode = initial_mode()
    if mode == "cap_when_missing":
        if mo is None:
            return _cap
        try:
            return max(0, min(int(mo), _cap))
        except Exception:                                   # noqa: BLE001
            raise ValueError("档上 `mo` 不是数（起手蓝取不了）：%r" % (mo,))
    raise ValueError("mana.json 的 initial.mode 认不出：%r" % (mode,))


#: 同一个口的第二个名字（`combat` / `_p` 那边按「起手」读它，别各叫各的）
start_mp = initial_mp


# ══════════════════════════════════════════════════════════════
# ① 基础回复：引擎回复钩子的供体
# ══════════════════════════════════════════════════════════════
def regen_amount(battle, actor):
    """每刻被引擎问一次「这一拍回多少」——**本函数自己判定多久回一次**。

    引擎零节奏知识（它只负责问 + 写回 + clamp），所以「每 N 刻回 1 点」必须在这里落成
    **整块结账**：一次结算可能跨过好几个 N（CTB 一步 ≈ 一次行动 ≈ 95–100 刻），
    只回 1 点会把「按刻的慢回」变成「≈1 点/次行动」（差 5 倍）——探针 ③ 就钉这一条。

    书签 = actor 自己的 `_mp_at`（下一个该回的点在哪一刻）——与职业资源那条
    `content/resources.py::aeth_res_regen` 的 `_res_at` **同款**（缺书签 ⇒ 记上、这一拍不回）。
    没有法力条的（狂战士 / 怪）：不碰、不写书签。
    """
    if not isinstance(actor, dict):
        return None
    if float(actor.get("max_mp") or 0) <= 0:
        return None                                    # 没有法力条的那一类不归这条渠道
    if actor.get("mp") is None:
        return None                                    # 引擎侧同款守卫（不给 actor 加字段）
    every = every_of()
    amount = amount_of()
    try:
        now = float(battle._now)
    except Exception:                                   # noqa: BLE001
        return None
    due = actor.get("_mp_at")
    if not isinstance(due, (int, float)) or isinstance(due, bool) or float(due) <= 0:
        actor["_mp_at"] = now + every                   # 第一次结算：记书签，这一拍不回
        return None
    if now < float(due):
        return None
    n = 1 + int((now - float(due)) // every)            # 这一步跨过了几个「该回的点」
    actor["_mp_at"] = float(due) + n * every
    return {"mp": n * amount}


#: 同一个钩子的第二个名字（`apply.py` 挂哪一个都指这一条路）
regen_fn = regen_amount


# ══════════════════════════════════════════════════════════════
# ③ 门槛：引擎门槛钩子的供体（`need_mp` 由引擎折算后转述）
# ══════════════════════════════════════════════════════════════
def gate_line(battle, actor, info, need_mp):
    """「蓝不够就放不出来」—— 回 `None` = 放行；回一句 = 拦下并把这句当回话。

    判定线 = 这一手的耗法；`gate.floor` 以下（默认 0 = 不耗法的普攻）**永不判**
    ⇒ 「普攻永远放得出」不靠引擎的特殊分支，靠这里。
    """
    rule = str((table().get("gate") or {}).get("rule") or "")
    if rule != "need":
        raise ValueError("mana.json 的 gate.rule 认不出：%r" % (rule,))
    try:
        need = int(need_mp or 0)
    except Exception:                                   # noqa: BLE001
        raise ValueError("引擎给的 need_mp 不是整数：%r" % (need_mp,))
    if need <= gate_floor():
        return None
    cur = int(actor.get("mp") or 0)
    if cur >= need:
        return None
    # 回话 = texts 域那一句（与「核心资源不足」同一句 · 不点资源名）。那个槽位带格式符
    # （`{rv:.0f}` 这类）⇒ 走 format 渲染，不走 T 的朴素替换（T 只替换 `{名字}`，
    # 会把这几个格式符原样漏给玩家）。渲染不出来 ⇒ 当场抛（fail-closed，不吐坏模板）。
    tmpl = T(_slot_name())
    try:
        return str(tmpl).format(rv=float(need), cur=float(cur))
    except Exception as _e:                             # noqa: BLE001
        raise ValueError("门槛回话槽位 %r 渲染不出来（%s）：%r" % (_slot_name(), _e, tmpl))


#: 同一个钩子的第二个名字（`apply.py` 挂哪一个都指这一条路）
gate_fn = gate_line
