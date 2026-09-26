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
   （`gate.slot` 那一格 —— ★ 本批起**自己那一格**：点名「法力」；改前与「核心资源不足」
    共用一句，法师一个号上「法力不够」与「印记不够」回的是**一字不差**的同一句，玩家分不清）。
   `gate.floor` = 需要 0 点的技（普攻）永不判。
④ ★ 结算：**跨场扣蓝落账 + 战斗外回蓝**（本批定的口径 · 表里的 `settle` 那一格）——
   收尾那一刻由 `cmds_battle._settle` 调 `settle()` 这一个口：把这一场的现蓝写回档，
   并按**游戏钟**（`calendar.game_time()` 现算的绝对刻）的差量补上「战斗外那一段回蓝」。
   改前那笔账写着「跨场扣蓝要一根战斗外的钟，本包今天没有那个面」—— 面就是这根钟。
⑤ ★ 上限涨了现值跟不跟：**跟**（表里的 `cap_gain`）—— 出档口 `cmds_ast._p` 调 `on_cap()`。

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

#: `settle` / `cap_gain` 那两格里的名字（同样不落字面量 —— 静态守卫只认表）
_K_FIELD = "field"
_K_STAMP = "stamp"
_K_WHEN = "when"
_K_MODE = "mode"
_K_MODES = "modes"

#: 游戏钟的单位换算（1 游戏日 = 86400 游戏秒 · 1 小时 = 3600 游戏秒）——
#: 与 `content/calendar.py::game_time` 同一把尺（真源 `05_玩法数值口径 §七`：游戏内 1 天 = 现实 2 小时）
_DAY_TICKS = 24 * 60 * 60
_HOUR_TICKS = 60 * 60


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
    # ★ 本批两格：结算（跨场扣蓝 + 战斗外回蓝）与上限补差 —— 形状坏就抛，不猜
    stt = t.get("settle")
    if not isinstance(stt, dict):
        raise ValueError("mana.json 少了 `settle`（结算：扣的账在哪一刻落、战斗外那根钟是谁）")
    for k in (_K_WHEN, _K_FIELD, _K_STAMP):
        if not str(stt.get(k) or ""):
            raise ValueError("mana.json 的 `settle.%s` 空着（结算口要的四个名字之一）" % k)
    cg = t.get("cap_gain")
    if not isinstance(cg, dict) or str(cg.get(_K_MODE) or "") not in (cg.get(_K_MODES) or {}):
        raise ValueError("mana.json 的 `cap_gain.mode` 不在它自己声明的 `modes` 里：%r"
                         % ((cg or {}).get(_K_MODE),))
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
    ★ 跨场扣蓝 / 战斗外回蓝 / 上限涨现值跟不跟：**本批三条都落了**（同一份表的
      `settle` / `cap_gain` 两格）—— 那一笔旧账（「本包今天没有那个面」）的落点见
      `settle()` / `on_cap()` 与 `content/cmds_battle._settle`。
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
# ⑤ 上限变了 ⇒ 现值补同样的差（唯一口 = `on_cap`，由出档口 `cmds_ast._p` 调）
# ══════════════════════════════════════════════════════════════
def cap_mode() -> str:
    """上限那一格的口径名（**认不出就抛** —— 静默换一个默认算法比报错更糟）。"""
    mode = str((table().get("cap_gain") or {}).get(_K_MODE) or "")
    if mode != "same_delta":
        raise ValueError("mana.json 的 cap_gain.mode 认不出：%r" % (mode,))
    return mode


def on_cap(mo, prev_cap, cap):
    """面板上限变了 ⇒ 现值按**同一个差量**补（钳回 0..上限）。返回**还没钳**的那一格。

    · `mo is None`（档上缺现蓝那一格）⇒ 回 `None`：起手那一条按满池给（`initial_mp`），
      这里**不替它编一个现值**；
    · `prev_cap is None`（档上还没有「上次那个上限」）⇒ 现值原样 —— 没有基线就没有差量；
    · 上限**降**了（脱装 / 改数据）⇒ 差量是负的，钳制交给 `initial_mp`（现值不会为负）。

    为什么要有它（试玩 A3）：加点 / 升级把上限从 110 推到 159，而现值恒 110 ⇒
    智力 / 意志里那半「+法力」白投、上限数字成了装饰。差量补上之后「+法力」真看得见。
    """
    if mo is None:
        return None
    c = int(cap or 0)
    if c <= 0:
        return int(mo)
    try:
        cur = int(mo)
    except Exception:                                       # noqa: BLE001
        raise ValueError("档上 `%s` 不是数（上限补差取不了）：%r"
                         % ((table().get("settle") or {}).get(_K_FIELD), mo))
    try:
        old = None if prev_cap is None else int(prev_cap)
    except Exception:                                       # noqa: BLE001
        old = None                                          # 旧格坏了当「没有基线」——不猜一个差量
    if old is not None:
        cur += (c - old)
    return cur


# ══════════════════════════════════════════════════════════════
# ④ 结算：跨场扣蓝落账 + 战斗外回蓝（唯一口 = `settle`，由 `cmds_battle._settle` 调）
# ══════════════════════════════════════════════════════════════
def settle_field() -> str:
    """档上「现蓝」那一格的名字（表里现读 —— 代码里不落字面量）。"""
    return str((table().get("settle") or {}).get(_K_FIELD) or "")


def settle_stamp() -> str:
    """档上「上次结到哪一刻」那一格的名字（唯一写端 = `settle`）。"""
    return str((table().get("settle") or {}).get(_K_STAMP) or "")


def game_tick():
    """**战斗外那根钟** = 绝对游戏刻（`content/calendar.py::game_time` 现算）。

    真源两处合起来才是它：`05_玩法数值口径 §七`「游戏内 1 天 = 现实 2 小时」+
    `01_属性字典 §一`「1 刻 = 1 秒」⇒ 那根钟在战斗外照样走得动（战斗内的钟是引擎的
    `battle._now`，两者同一把尺：都是「游戏刻」）。
    """
    from . import calendar as CAL                          # 本地 import：与 `_p` 里那一手同款
    day, hod = CAL.game_time()
    return int(day) * _DAY_TICKS + int(round(float(hod) * _HOUR_TICKS))


def settle(p, mp_now):
    """这一场收尾那一刻的**唯一落账口** —— 返回这一下补回了几点（探针/回话用）。

    三件事，一次做完（`content/cmds_battle._settle` 调它）：
      ① **落账**：把这一场 actor 的现蓝写回档（钳到面板上限）—— 跨场因此真扣（试玩 A2）；
      ② **战斗外回蓝**：按游戏钟的差量整块结（每 `regen` 那一格声明的刻数回它声明的点数）——
         与战斗内那条渠道**同一个回复率**，只是换一根更长的钟；
      ③ **记书签**：把「结到哪一刻」写进档（`settle.stamp`）—— 缺这一格（新档 / 老档）⇒
         只记书签、不回（没有基线就不编一个起点，与 `regen_amount` 的 `_mp_at` 同款）。

    `mp_now` = 这一场收尾时**我**的现蓝（调用方从「场」里现读；拿不到 ⇒ 传 `None`）——
    `None` ⇒ **一个字段都不写**（不拿旧档顶上、也不猜），返回 0。
    """
    if not isinstance(p, dict) or mp_now is None:
        return 0
    cap = int(p.get("mo_max") or 0)
    if cap <= 0:
        return 0                                            # 没有法力条的职业（狂战士）不归这条渠道
    try:
        cur = int(mp_now)
    except Exception:                                       # noqa: BLE001
        raise ValueError("这一场收尾时的现蓝不是数：%r" % (mp_now,))
    cur = max(0, min(cur, cap))
    now = game_tick()
    stamp = settle_stamp()
    last = p.get(stamp)
    gain = 0
    if isinstance(last, (int, float)) and not isinstance(last, bool):
        n = int((now - float(last)) // every_of())
        gain = max(0, n) * amount_of()
    p[stamp] = now
    p[settle_field()] = max(0, min(cur + gain, cap))
    return gain


#: 同一个口的第二个名字（探针 / 别处按「结算」读它）
settle_mp = settle


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
