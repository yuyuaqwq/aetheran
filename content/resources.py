# -*- coding: utf-8 -*-
"""《阿斯特兰》职业资源的消费端 —— B4-1 只写了声明（`res_gain` / `res_cost`），这里补渠道。

口径（五条，与 `content/mech.py` 同一套规矩）
------------------------------------------------------------------
1. **单一真源** = `content/rules/resources.json`（谁涨、涨多少、上限几、自然回复）。
   本模块只读它：代码里不许出现资源名，也不许出现那些数字（探针现解析本表逐条对账）。
2. **两条路**：技能自己声明的 `res_gain`（出手那一刻，走引擎 `act_cast`）· 渠道表给的
   （受击 / 命中 / 友方受伤 / 自然回复，走引擎事件总线）。**写层只有一处 `add()`**。
3. **fail-closed**：域里出现表里没有的资源码 ⇒ 装配期当场抛（点名技能）；表形状坏、
   渠道名不认识、主人职业不在 `classes` 域 —— 同样当场抛。
4. **不装配 = 与接线前逐字相同**：表读不到 ⇒ 一个字段都不写（技能照放，只是不涨）。
5. **开战把资源条目摆成 0 层**（`battle_start`）：引擎的 `res_cost` 判据是「有该条目就必须足额，
   没条目不拦」—— 摆了 0 层才是真闸门（不然「资源不够也放得出来」）。

谁挂它：`content/combat.py::player_actor` 把 `triggers()` 合进 actor 的注入点；装配期由
`content/apply.py` 调 `check_domain()` 做跨域对账。引擎侧零改动（只用它既有的注入面与事件总线）。
"""
from __future__ import annotations

import io
import json
import os
import random

from ext_combat.battle import effects as EF
from ext_combat.battle import stats as ST

from .cmds_ast import T

_RULES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules", "resources.json")
_CACHE: dict = {}


# ══════════════════════════════════════════════════════════════
# 表：读 + 校验（形状坏就抛，不猜）
# ══════════════════════════════════════════════════════════════
def _read_table() -> dict:
    """读真源并**逐字**交给 `_validate` —— 读不到 / 读坏 一律点名抛（台账 L1680-#2）。

    ★ 这条口径与本模块 docstring 第 3 条（「表形状坏当场抛」）**逐字对齐**，也与
      同包 `mana.py::table()` 的同款缺陷同一族（那一处本轮不叠，属另一份真源）。
    ★ 原先的形态（`except Exception: raw = {}` + `_validate(raw) if raw else {}`）把
      **语法错 / 文件缺失 / 编码错 / 空表**四种一律降级成「表读不到」⇒
      `_validate` 对空 dict 反而被 `if raw else` 跳过（`resources` 键都查不到就放行）
      ⇒ `triggers()` 见 `if not table(): return {}` 整块渠道静默消失、
      职业资源全线退化成「不涨不花」，**装配期零报错**。
    """
    try:
        text = io.open(_RULES, encoding="utf-8").read()
    except OSError as e:
        raise ValueError("resources.json 读不到（路径 %s）：%s" % (_RULES, e)) from e
    try:
        raw = json.loads(text)
    except ValueError as e:
        raise ValueError("resources.json 不是合法 JSON（%s）：%s" % (_RULES, e)) from e
    return _validate(raw)


def table() -> dict:
    if "t" not in _CACHE:
        _CACHE["t"] = _read_table()
    return _CACHE["t"]


def _validate(t: dict) -> dict:
    """表形状与引用面逐条核 —— 不对就**点名**抛（装配期，不是运行期）。"""
    if not isinstance(t, dict) or not isinstance(t.get("resources"), dict):
        raise ValueError("resources.json 形状坏：要有顶层 `resources`（dict）")
    chans = t.get("channels") or {}
    if not isinstance(chans, dict) or not chans:
        raise ValueError("resources.json 形状坏：要有顶层 `channels`（渠道名 → 说明 / 参数）")
    for _cn, _cv in chans.items():
        if isinstance(_cv, dict):
            _note_of_channel(_cn, _cv)
    for key, rec in (t["resources"] or {}).items():
        if not isinstance(rec, dict):
            raise ValueError("资源 %r 的记录不是 dict" % key)
        mx = rec.get("max")
        if not isinstance(mx, (int, float)) or mx <= 0:
            raise ValueError("资源 %r 的 `max` 必须是正数（现在 %r）" % (key, mx))
        if not str(rec.get("owner_class") or ""):
            raise ValueError("资源 %r 少了 `owner_class`（主人职业）" % key)
        for ch in (rec.get("gain") or {}):
            if ch not in chans:
                raise ValueError("资源 %r 声明了没登记过的渠道 %r（channels 里有：%s）"
                                 % (key, ch, " · ".join(sorted(chans))))
        reg = rec.get("regen")
        if reg is not None:
            if not isinstance(reg, dict) or not str(reg.get("every") or ""):
                raise ValueError("资源 %r 的 `regen` 要写 `every`（每几刻回一次）" % key)
    return t


def _note_of_channel(name: str, cv: dict) -> str:
    """渠道条目的说明 —— 字符串形态直接是它，对象形态取 `note` 那一格（台账 L1680-#4）。

    ★ 渠道条目现在是**两种形态并存**：纯说明的写字符串（ ``on_cast`` 等六条），
      带参数的写成 `{"note": …, "over_pct": …}`（ ``ally_hurt`` —— 那个 15% 阈值
      原来**在代码里是裸常量**、表里也写了一份说明，两处维护；台账 L1680-#4）。
      两种都合法，但**带参数的那条必须把 `note` 写出来**（说明是本表的既有约定，
      丢了就成了「阈值在表里、口径不知道从哪来」）。
    """
    note = str(cv.get("note") or "").strip()
    if not note:
        raise ValueError("渠道 %r 用了对象形态却没写 `note`（说明是这张表的既有约定）" % name)
    return note


def hurt_over_pct() -> float:
    """`ally_hurt` 那条渠道的「受伤超过上限百分之几」—— **单一取值口**（台账 L1680-#4）。

    ★ 原先是 `resources.py:269` 的裸常量 `mx * 0.15`，而 `resources.json` 的
      `channels.ally_hurt` 说明里也把 15% 写死了一份 ⇒ **同一阈值两处维护**
      （改表不改代码 = 表的说明骗人；改代码不改表 = 反过来）。本函数是唯一的读口。
    ★ 认不出 / 形状坏 ⇒ **当场抛并点名**（本项目铁律：不留静默兜底）。
    """
    cv = channels().get("ally_hurt")
    if not isinstance(cv, dict):
        raise ValueError("渠道 `ally_hurt` 必须是对象形态（要带 over_pct 这个阈值），现在 %r"
                         % type(cv).__name__)
    raw = cv.get("over_pct")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError("渠道 `ally_hurt` 的 `over_pct` 必须是数字（现在 %r）" % (raw,))
    if not (0.0 < float(raw) < 1.0):
        raise ValueError("渠道 `ally_hurt` 的 `over_pct` 必须在 0 与 1 之间（现在 %r）" % (raw,))
    return float(raw)


def resources() -> dict:
    return table().get("resources") or {}


def channels() -> dict:
    return table().get("channels") or {}


def of(key: str) -> dict:
    rec = resources().get(key)
    if rec is None:
        return {}
    return rec


def max_of(key: str) -> int:
    return int(of(key).get("max") or 0)


def gain_of(key: str, channel: str) -> int:
    """渠道表里那一条的增量（没声明 = 0 = 这条渠道不涨这个资源）。"""
    return int((of(key).get("gain") or {}).get(channel) or 0)


def res_of_class(cls: str) -> str:
    """这个职业的资源码（一个职业最多一条 —— 多过一条在 `check_domain` 里点名）。"""
    if not cls:
        return ""
    hits = [k for k, r in resources().items() if r.get("owner_class") == cls]
    return hits[0] if len(hits) == 1 else ""


def _res_of_actor(actor) -> str:
    if not isinstance(actor, dict):
        return ""
    return res_of_class(str(actor.get("class_name") or ""))


def check_domain(raise_on_unknown: bool = True) -> dict:
    """跨域对账（装配期）：域里每条技能的 `res_gain` / `res_cost` 码都得在表里。

    返回 `{资源码: [技能 id, ...]}`（现算，不写镜像表）。这一条就是防「技能声明了资源、
    渠道没这张表」的常驻判据：新写一条带资源的技能忘了补表 ⇒ 装配当场红。
    """
    from . import skills_lookup as SL

    seen: dict = {}
    unknown: list = []
    for sid, rec in SL.skills().items():
        if str(sid).startswith("_") or not isinstance(rec, dict):
            continue
        keys = list((rec.get("res_gain") or {}).keys()) + list((rec.get("res_cost") or {}).keys())
        for k in keys:
            seen.setdefault(k, []).append(sid)
            if k not in resources():
                unknown.append((sid, k))
    if unknown and raise_on_unknown:
        raise KeyError("这些技能声明了资源，而 resources.json 里没有那一条（不认得的资源不许静默不涨）：%s"
                       % " · ".join("%s=%s" % (s, k) for s, k in unknown))
    # 一个职业只能有一条资源（多了就是两处口径）
    by_cls: dict = {}
    for k, r in resources().items():
        by_cls.setdefault(str(r.get("owner_class") or ""), []).append(k)
    dup = {c: ks for c, ks in by_cls.items() if len(ks) > 1}
    if dup and raise_on_unknown:
        raise ValueError("同一个职业挂了两条资源（一个职业只该有一条）：%s" % dup)
    return seen


# ══════════════════════════════════════════════════════════════
# 写层：只有这一处（加层 / 夹 0..max）
# ══════════════════════════════════════════════════════════════
def add(battle, actor, key: str, n, logs=None) -> int:
    """给这个 actor 的那条资源加 n 层（夹在 0..max），返回**加完之后**的层数。

    资源条目形状与引擎的栈资源同族：`{"stacks": n, "expire": None}`（永久条目，
    不带 `mode` ⇒ 净罪那类「解控制」不会误清它；`_skill_usable` 直接读 `.stacks`）。
    """
    if not isinstance(actor, dict) or not key:
        return 0
    cap = max_of(key)
    if cap <= 0:
        return 0
    try:
        cur = int((((actor.get("effects") or {}).get(key)) or {}).get("stacks") or 0)
    except Exception:                                       # noqa: BLE001
        cur = 0
    new = max(0, min(cap, cur + int(n)))
    if new != cur:
        actor.setdefault("effects", {})[key] = {"stacks": new, "expire": None}
    return new


def set_to(actor, key: str, n) -> int:
    """直接摆成 n 层（开战初始化用；同样夹在 0..max）。"""
    if not isinstance(actor, dict) or not key:
        return 0
    cap = max_of(key)
    new = max(0, min(cap, int(n)))
    actor.setdefault("effects", {})[key] = {"stacks": new, "expire": None}
    return new


def _now(battle) -> float:
    try:
        return float(battle._now)
    except Exception:                                       # noqa: BLE001
        return 0.0


def _info(battle) -> dict:
    """技能 dict —— **从事件 ctx 读**，不是从 handler 的 `params` 读。

    ★ 引擎的事件 ctx（`{"actor","target","info","dmg",…}`）**不会**并进每个动作的 `params`
      （`params` 只带那条效果自己的键）—— 读 ctx 的口子是 `battle._fire_ctx`
      （`fire()` 直接透传同一个对象，嵌套安全；见 `effect_triggers.fire` 的 2026-09-11 说明）。
      本模块与 `content/mech.py::aeth_on_cast` 用同一处（不许各读各的）。
    """
    return _ctx(battle).get("info") or {}


def _ctx(battle) -> dict:
    if battle is None:
        return {}
    v = getattr(battle, "_fire_ctx", None)
    return v if isinstance(v, dict) else {}


# ══════════════════════════════════════════════════════════════
# 五条注入面（引擎事件总线 → 这一层）
# ══════════════════════════════════════════════════════════════
@EF.register_action("aeth_res_start")
def aeth_res_start(battle, caster, target, params, logs):
    """开战：把本职业那条资源摆成 0 层（引擎的资源闸门才真的存在）。"""
    key = _res_of_actor(caster)
    if key:
        set_to(caster, key, 0)


@EF.register_action("aeth_res_on_cast")
def aeth_res_on_cast(battle, caster, target, params, logs):
    """出手那一刻：读技能自己声明的 `res_gain`（例：横剑 +3 守誓 · 焰痕 +2 印记）。"""
    info = _info(battle)
    gain = info.get("res_gain") or {}
    if not isinstance(gain, dict):
        return
    for k, n in gain.items():
        add(battle, caster, str(k), n, logs)


@EF.register_action("aeth_res_on_taken")
def aeth_res_on_taken(battle, caster, target, params, logs):
    """挨打之后（引擎 `on_taken`，承伤后）：渠道表里那条 `on_taken` / `ally_hurt`。

    ★ 主体 = **受击者自己**（引擎只跑主体自己声明的 triggers）⇒ 表里那条 `ally_hurt`
      （修女：友方一次受伤超过其上限 15%）今天按「**含自己**」算；真队友受伤那一路
      要等多人战斗常用起来（那时得让同队的修女能看到别人的承伤，见 resources.json 的 _note）。
    ★ 「倒下清空」也在这里：这次挨完 hp ≤ 0 ⇒ 把资源清回 0。
    """
    key = _res_of_actor(caster)
    if not key:
        return
    dmg = 0.0
    try:
        dmg = float(_ctx(battle).get("dmg") or 0)           # ★ 这一下的**真实**伤害（承伤后）
    except Exception:                                       # noqa: BLE001
        dmg = 0.0
    got = gain_of(key, "on_taken")
    if got:
        add(battle, caster, key, got, logs)
    pct = gain_of(key, "ally_hurt")
    if pct:
        mx = 0
        try:
            mx = int(ST.actor_max_hp(battle, caster) or 0)
        except Exception:                                   # noqa: BLE001
            mx = 0
        if mx > 0 and dmg > mx * hurt_over_pct():
            add(battle, caster, key, pct, logs)
    # ★ 倒下清空**不在这里**：濒死的这一下 `on_taken` 根本不触发
    #   （`landing` 里 `if target.get("hp", 0) > 0:` 才 fire —— 死者走 on_death/on_kill）
    #   ⇒ 清空挂在 `on_death` 上（见 aeth_res_on_death）。


@EF.register_action("aeth_res_on_death")
def aeth_res_on_death(battle, caster, target, params, logs):
    """倒下 ⇒ 资源清空（真源：修女「队友倒下清空」，这里按含自己落）。"""
    key = _res_of_actor(caster)
    if key:
        set_to(caster, key, 0)


@EF.register_action("aeth_res_on_hit")
def aeth_res_on_hit(battle, caster, target, params, logs):
    """命中：普攻走 `attack_hit`（+3）· 技能走 `skill_hit`（+5）—— 照渠道表的两个名字。"""
    key = _res_of_actor(caster)
    if not key:
        return
    info = _info(battle)
    ch = "hit_basic" if info.get("_basic") else "hit_skill"
    got = gain_of(key, ch)
    if got:
        add(battle, caster, key, got, logs)


@EF.register_action("aeth_res_regen")
def aeth_res_regen(battle, caster, target, params, logs):
    """自然回复（修女那条：每 300 刻回 1）。书签写在 actor 自己的 `_res_at` 上。"""
    key = _res_of_actor(caster)
    if not key:
        return
    reg = of(key).get("regen") or {}
    every = float(reg.get("every") or 0)
    amount = int(reg.get("amount") or 0)
    if every <= 0 or amount <= 0:
        return
    now = _now(battle)
    due = float(caster.get("_res_at") or 0)
    if due <= 0:
        caster["_res_at"] = now + every
        return
    if now < due:
        return
    n = 1 + int((now - due) // every)             # 这一步跨过了几个「该回的点」
    caster["_res_at"] = due + n * every            # 书签按 due 推，不按 now 推（否则漂移持续累积）
    add(battle, caster, key, amount * n, logs)


def triggers() -> dict:
    """玩家 actor 要挂的注入面（与 mech 那一条合并后交给引擎）。"""
    if not table():
        return {}
    return {
        "battle_start": [{"action": "aeth_res_start"}],
        "act_cast": [{"action": "aeth_res_on_cast"}],
        "on_taken": [{"action": "aeth_res_on_taken"}],
        "attack_hit": [{"action": "aeth_res_on_hit"}],
        "skill_hit": [{"action": "aeth_res_on_hit"}],
        "on_death": [{"action": "aeth_res_on_death"}],
        "time_advance": [{"action": "aeth_res_regen"}],
    }
