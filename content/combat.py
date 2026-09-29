# -*- coding: utf-8 -*-
"""《阿斯特兰》战斗接线（B2-2）—— 包侧唯一出口。

形状在扩展包（`ext_combat`：CTB 调度 / 行动结算 / 效果叠层 / 面板公式），
本文件只做三件事：**造 actor · 组战斗 · 推动**。取值全从本包数据来（面板 / 怪 / 技能）。

★ 第一版范围（有意收窄）：先打通「遇敌 → 自动打完 → 拿日志与结果」。
  轮流制（等玩家输入窗口）+ 技能选择的交互层留到 B2-2b（引擎已支持，见
  `Battle.human_act` / `focus()`；奥兰迪亚的实现在 `content/cmds_instance_router.py`）。
"""
from __future__ import annotations

import json
import os
import random
import re

from ext_combat import Battle
from ext_combat.battle.actors import make_actor

from . import panel_build as PB
from . import alloc as ALLOC          # ★ P-34：档上那份加点只走它（`of_record`）
from . import affix as AFFIX          # ★ B3-24：精英词条（面板乘 / 先手 / 开场盾 / 血量阈值）
from . import absorb as ABS           # ★ 状态容器收口第2批：吸收型（护盾）写口 + 读口（两态门）
from . import mech as MECH            # ★ B3-27：技能机制层（触发器 + 选目标注入点）
from . import elements as ELE         # ★ P-1：元素通道（样例怪身上的免疫/弱点表）
from . import battle_text as BT       # ★ P-1：战斗日志的文案槽位（`Battle(text=…)` 那一口）

PLAYER_SIDE = "player"
ENEMY_SIDE = "enemy"

_PARTY_KEY = re.compile(r"[1-9][0-9]*")

# ══════════════════════════════════════════════════════════════
# ★ Boss 阶段卡（内容侧 · 唯一消费端在下方的 `_boss_phase_hook`）
# ══════════════════════════════════════════════════════════════
#: 怪 actor 上那一格：`monsters.mods.phases` 的声明（照抄一份挂在 actor 上 ⇒ 落进场的存档里，
#: 恢复之后还在 —— 见 `_restore` 里重新挂钩子那一步）。
PH_CARD = "_boss_phases"
#: 运行期那一格（第几阶 / 本阶走了几手 / 基数面板 / 已生效的修正）—— 同一个道理随 actor 落盘。
PH_RUN = "_boss_ph"
#: 阶段条目里**改面板**的那几个键（只声明了的才改 —— 没声明的沿用上一阶）。
_PH_NUMS = ("atk_mult", "def_add", "dmg_taken_mult", "act_rate_mult")
#: 一个阶段条目没声明时的那一套（= 与接线前逐字相同：atk/def/spd 原样、承伤无乘区、出手）。
_PH_DEFAULTS = {"atk_mult": 1.0, "def_add": 0.0, "dmg_taken_mult": None,
                "act_rate_mult": 1.0, "hold": False}
#: 演出那一行缺不得的几格（装配期当场抛 —— 缺了就是「👁️ 」半句空话）
_PH_REQUIRED = ("name", "line", "tip")


def party_scale_of(m: dict, party: int | None) -> dict:
    """取「这个人数下，这只怪的面板倍数」（域里的 `mods.party_scale`）。

    ★ 真源四处（**只有一处给了数**）：
      `12_怪物面板与精英词条池_v1.md` §一④「Boss …按 4 人队 × 18 次行动设计 —— 单人打会很吃力
      （有意的，它是团队内容）；**单人挑战时按 ÷2 看（≈3670）**」·
      `17_组队与策略配合_v1.md` §五「单人　能过（**Boss 血按 ÷2 看**）」·
      `22_旧哨塔_逐间设计_v1.md` §三④「**组队时按人数缩放**（P1 单人也能过）」·
      台账 P-36（设计原话「单人打 Boss 伤害 ÷2」）。

    ★ B3-25 起这张表是**四档**（1/2/3/4 人）：两边锚点都不许动 —— 4 人档 = 设计值（真源
      「按 4 人队设计」）、1 人档 = 真源写死的 ÷2；中间两档（2/3 人）按主线拍板的**递减排法**
      内插（每多一个人加得少一点：**+0.35 / +0.25 / +0.15** —— 照表 1/2/3/4 人 = 0.25/0.6/0.85/1.0
      算出来的递增量，真源 `17_组队与策略配合_v1.md §五` 同款）。表写在生成器
      `scripts/rebuild_monsters.PARTY_SCALE` → 数据 `mods.party_scale`（唯一来源）；
      「有效人数档 = 1..上限」的另一半在 `content/data/party.json`（跨域对账在 probe_party）。
      ★ **只收 `hp` 一项**：四处真源里两处字面写的是「**血**按 ÷2 看」——
      伤害 / 防御 / 速度那几项文档没说，一律不动。

    ★ fail-closed 四条（不许静默）：
      · `party is None`（不知道几个人）⇒ **不缩放**（返回 `{}`）：那走的就是设计值（4 人档），
        绝不会因为「不知道」而悄悄把 Boss 削弱；
      · 表在、但键不是正整数 / 是别的东西 ⇒ **当场抛**（数据坏了不兜底）；
      · `party` **超过表里最大档** ⇒ 当场抛（队伍上限就是表里最大那一档；静默按设计值
        = 悄悄改难度）；
      · 要缩的那一项**必须真在面板里**（键名对不上 ⇒ 抛，不静默当 0）—— 那一半在
        `monster_actor` 里落（本函数只回答「缩哪些项、缩多少」）。
    """
    tbl = (m.get("mods") or {}).get("party_scale")
    if not tbl:
        return {}
    if isinstance(tbl, bool) or not isinstance(tbl, dict):
        raise ValueError("party_scale 必须是「人数 → 面板倍数」的表：%r" % (tbl,))
    for k in tbl:
        if not _PARTY_KEY.fullmatch(str(k)):
            raise ValueError("party_scale 的键必须是正整数人数：%r" % (k,))
    if party is None:
        return {}
    if isinstance(party, bool) or not isinstance(party, int) or party < 1:
        raise ValueError("队伍人数必须是正整数（不知道就传 None）：%r" % (party,))
    top = max(int(k) for k in tbl)
    if party > top:
        raise ValueError("队伍人数 %r 超过表里最大档（%d 人）—— 那几档没数，不许编"
                         "（上限见 content/data/party.json 的 pt_rules.max_members）" % (party, top))
    return {str(k): float(v) for k, v in (tbl.get(str(party)) or {}).items()}


def player_actor(player: dict, stack_prefix: str = "aetheran", *,
                 uid: str | None = None) -> dict:
    """玩家档 → 战斗 actor（面板走本包的面板栈）。

    ★ B3-28 ①：`uid` = 身份，**从 handler 那三个槽位传进来**（生产宿主读回来的档里
      没有 `uid`：`host/store_factory.py::_IDENTITY_KEYS` 把身份列剔掉了 ⇒ 只靠
      `player.get("uid")` 会在生产里恒等于同一个值 = 照样撞格）。拿得到就传。
    """
    # ★ P-27：职业**不兜底**（原先 `player.get("cls") or "cls_knight"` —— 等于替没择业的玩家
    #   挑了个职业，档与面板从这一行起就分家）。没有职业 ⇒ `panel_build` 当场抛 `PanelMissing`
    #   （生命上限只有一个来源：职业面板）。
    cls = str(player.get("cls") or "")
    lv = int(player.get("level", 1) or 1)
    # ★ 装备与强化走唯一取值口（B2-6，`panel_build.gear_and_buffs` → `gear` 那两个口）：
    #   `gear_stats` 会按强化等级放大主词条；食物增益走最后一层 mul（时效过了自动失效 ——
    #   时钟是宿主注入的那根）。★ P-27：与「档上的上限」（`panel_build.hp_cap`）吃**同一份**
    #   取值口 ⇒ 面板 / 档 / 战斗 actor 三处同一个数。
    gear, buffs = PB.gear_and_buffs(player)
    # ★ P-34：「这档实际分了多少」只走 `alloc.of_record`（归一化 + fail-closed）——
    #   原先这里写的是 `player.get("alloc")`：档上那一格坏了（认不出的维 / 小数 / 超投）
    #   战斗会当没投过照样开打，而「属性」页 / 生命上限却按别的数算 ⇒ 三处对不上。
    a = PB.build_actor(cls, lv, ALLOC.of_record(player), gear, buffs=buffs,
                       stack_prefix=stack_prefix, uid=uid)
    from .cmds_ast import T                    # ★ B4-19：本地 import（免得包装载期成环）
    a["uid"] = str(uid or player.get("uid") or "p1")
    a["name"] = player.get("name") or T("SYS_NAME_UNKNOWN")
    a["side"] = PLAYER_SIDE
    a["kind"] = "player"
    a["human_controlled"] = True
    a["level"] = lv
    # ★ 实时血量必给（引擎读 a["hp"]，缺了会拿 max_hp 当当前值）
    #   ★ P-27：钳制用的上限就是**面板算出来的那一个**（`a["max_hp"]`）—— 现血来自同一份档
    #     （`cmds_ast._p` 已按同一个上限钳过）⇒ 不再「档上写死 100 压住面板 116」那种两个源混用。
    if not isinstance(a.get("max_hp"), (int, float)) or isinstance(a.get("max_hp"), bool):
        raise PB.PanelMissing("面板没给出生命上限（max_hp · 职业数据少了 hp？）：%r"
                              % (a.get("class_name"),))
    mx = int(a["max_hp"])
    hp = int(player.get("hp") or mx)
    a["hp"] = max(1, min(hp, mx))
    # ★ B4-8：**现蓝**与现血走同一条路（读档）—— 上限那一格由面板给出（`build_actor`），
    #   现蓝那一格归档（`_p` 已按同一个上限钳过）。
    # ★ P-51（2026-09-26）：起手口径已定 —— 走唯一一口 `mana.initial_mp`（档上有现蓝那一格
    #   ⇒ 照它；**缺格** ⇒ 按面板上限满池，= 战斗外回满）。与 `cmds_ast._p` **同一口**
    #   ⇒ 面板 / 档 / actor 三处一个数。原先 `int(player.get("mo") or 0)` 等于「每场都从 0 起手」
    #   ⇒ 耗法技能开局一个都放不出来（与技能表印着耗法自相矛盾）。口径与理由见
    #   `content/rules/mana.json`（真源 04_法师_v2 §二/§三 的账按满池起算）。
    from . import mana as _MANA
    a["mp"] = _MANA.initial_mp(player.get("mo"), a.get("max_mp"))
    a.setdefault("max_mp", int(a.get("max_mp") or 0))
    # ★ 技能表必给（缺了引擎会挑默认技 —— 实测挑成了「圣光治愈」，双方打不死）
    a["skills"] = list(player.get("skills") or _default_skills(cls, lv))
    # ★ B3-27：机制层的两个注入点（引擎给内容侧的位）—— 出手瞬间（act_cast）与承伤乘区
    #   （taken_calc）。只有「这一条技能真带 route=cast 的 mech / 身上真有减免态」时才动手，
    #   其余一律一个字段都不写 ⇒ 不挂 = 与接线前逐字相同。
    a["triggers"] = MECH.player_triggers()
    return a


def _default_skills(cls_id: str, level=1):
    """本职业**此刻解锁**的技能 id（按 `(解锁等级, id)` 升序）—— 与 `技能` 那一条同源。

    ★ B4-1 两处收口（原先这一支是「本职业全部技能，不分等级、不分主动被动」——
      30 条全 lv=1 时看不出差别，11–20 那 18 条一进来就露）：

      ① **按解锁等级挑**：`skills.lv <= 等级`（域里的 `lv` 就是解锁等级，真源
         `02_技能体系规划_v1.md §四`）。这一支原先**不看等级**，而 `cmds_skill._of_class`
         看等级 —— 两处口径不同，玩家会在「技能」页看见 5 条、打起来却拿到 7 条
         （文档里那句「与 `combat._default_skills` 同一支、同一序」当时是**没兑现的**）。
      ② **被动不进球场**：`kind_key == "passive"` 的那些是常驻的（开战时由事件总线挂上，
         见 `content/mech.py`），**不是能"放"出来的技** —— 放进 actor 的技能表，引擎/AI
         就会把它当一手来使（那一手什么也不产生，白费一次行动）。判据先看 `kind_key`
         （ASCII 机器键，由 `scripts/rebuild_skills.py` 算出来），不认中文类别名。
    """
    import json
    import os
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "skills.json")
    try:
        with open(p, encoding="utf-8") as f:
            sk = json.load(f)
    except OSError:
        return []
    lv = int(level or 1)
    mine = [(int(v.get("lv") or 1), k) for k, v in sk.items()
            if v.get("owner_class") == cls_id
            and int(v.get("lv") or 1) <= lv
            and v.get("kind_key") != "passive"]
    mine.sort()
    return [k for _, k in mine]


def monster_actor(mid: str, m: dict, *, party: int | None = None, affixes=None,
                  hp_mult: float | None = None) -> dict:
    """怪数据（monsters 域）→ 战斗 actor。

    ★ B3-14：**域里那套键名要翻成引擎消费端那一套**（键名契约 —— 照域里的名字传，
      引擎读不到就当 0/1，全程不报错）。域（真源 `12_怪物面板与精英词条池_v1.md`）写的是
      `hp / res / eva / crit`，而引擎 `make_actor` + `stats._monster_base_stats` 读的是
      `max_hp / mdef / dodge / crit**率**`：

        · `hp`  → 引擎只认 `max_hp` ⇒ 实测 `actor_stats` 给出 **max_hp = 1**（真血靠
          `a["hp"]` 走，所以「一击必死」没暴露，但按 max_hp 算的东西全错：
          斩杀线 / hp% 技 / 护盾 / Boss 阶段阈值）。
        · `res` → 引擎只认 `mdef` ⇒ **怪魔防恒 0**（法师/修女 的伤害无视「法系」原型那 1.6 倍法抗）。
        · `eva` → 引擎只认 `dodge`，而且**当率读**（`landing._roll_dodge`：`min(dodge, 0.40)`）⇒
          怪**永不闪避**（「快速」原型的 1.3 倍闪避白给）。
        · `crit`→ 引擎当**率**读（`random.random() < crit`）⇒ 域里 13/47/94 这些**数值**
          被当成率 ⇒ **怪必然暴击**（`13 > 1` 恒真）。
      ⇒ 四个键一律在这儿换名 + 率化（率化共用 `panel_build.rate_of`，与玩家同一把尺）。

    ★ B3-17 起的「按人数缩放」：`party` = 这一场的队伍人数 —— 走 `party_scale_of`
      （1/2/3/4 档 · 4 人 = 设计值 · 1 人 = 真源写死的 ÷2）。缩放加在**域那一套键名**上
      （`hp` / `atk`），换名之前；**不传 = 不知道 ⇒ 不缩放**（设计值 = 4 人档），见
      `party_scale_of` 的 fail-closed 四条。
    """
    panel = dict(m.get("panel") or {})
    for _k, _v in party_scale_of(m, party).items():
        if _k not in panel:
            raise KeyError("party_scale 要缩的面板键不在 panel 里（键名对不上不静默）：%s.%s" % (mid, _k))
        panel[_k] = int(round(float(panel[_k]) * _v))
    # ★ B3-24：精英词条的面板乘（改数值那一类）—— 同样加在**域那一套键名**上、换名之前；
    #   键名对不上由 `affix.apply_panel` 当场抛（与 party_scale 同一条 fail-closed 纪律）。
    panel = AFFIX.apply_panel(panel, affixes, mid)
    if hp_mult is not None:                        # 群居：第二只半血（每只单独给倍数）
        panel["hp"] = max(1, int(round(float(panel["hp"]) * float(hp_mult))))
    panel["max_hp"] = panel.pop("hp", panel.get("max_hp"))
    panel["mdef"] = panel.pop("res", panel.get("mdef"))
    panel["dodge"] = PB.rate_of(panel.pop("eva", 0))
    panel["crit"] = PB.rate_of(panel.pop("crit", 0))
    panel.setdefault("mp", 0)
    panel.setdefault("max_mp", 0)
    a = make_actor(uid=mid, name=m.get("name", mid), side=ENEMY_SIDE, kind="monster",
                   level=int(m.get("lv", 1) or 1), **panel)
    # ★ B3-6b-2d-keys-2（P-20 甲案第二刀）：`role` 是**内容侧词汇**（策划案原文的档位名，引擎里那份
    #   `role` 限定规则是逐字比对的）⇒ 照旧从域里透传；**机器判定**一律走 ASCII `role_key`。
    #   缺了档位名 ⇒ 拿机器键顶上（两个都不在 ⇒ 空串，两条路在引擎那边都是「不是 boss」）。
    a["role"] = m.get("role") or m.get("role_key") or ""
    a["is_boss"] = (m.get("role_key") == "boss")   # 原先比 `a["role"] == "boss"`（那一档的值恰好是 ASCII）
    # ★ P-1（元素通道）：承伤方的免疫/弱点表 —— 引擎落地层读的就是这两个字段
    #   （`ext_combat/battle/landing.py` 的 N10-B4：`element_immune` 含该元素 ⇒ 伤害归 0；
    #   `element_weak[元素] > 1` ⇒ ×倍率）。**挂什么由声明说话**（`content/rules/elements.json`
    #   的 `sample` 那一块）：没声明 / 关掉 / 不是那只怪 ⇒ 返回 `{}` ⇒ 一个字段都不写
    #   ⇒ actor 与接线前**逐字相同**（探针有反证那一条）。P-1 只在**一只既有怪**上试水。
    _el = ELE.sample_fields(mid)
    if _el:
        a.update(_el)
    # ★ B3-24：精英词条 —— 名字（`† 硬壳的田鼠 †`，走 texts 槽位）与开场盾（**吸收型**：状态容器里
    #   一条声明了 `absorb` 的条目）。没有词条 ⇒ 名字原样、一个字段都不写（= 与接线前逐字相同）。
    if affixes:
        a["name"] = AFFIX.display_name(str(m.get("name", mid)), affixes)
        # 开场盾按**生命上限**算 ⇒ 上限取不到就不给盾（fail-closed：不拿 1 / 100 垫上）
        _mx = a.get("max_hp")
        if not isinstance(_mx, (int, float)) or isinstance(_mx, bool) or float(_mx) <= 0:
            raise ValueError("精英词条要发开场盾，但 actor 没有可用的生命上限：%s" % (mid,))
        # ★ 状态容器收口第 2 批（2026-09-28 · 设计案 §2.1/§2.2）：**这一行是包侧真正的写口**。
        #   旧形状 = 写引擎那个要被删掉的 `shields` 容器（`a["shields"] = …`）；新形状 = 往
        #   **状态容器**（`effects`）里写一条**带 value 的条目**，且它**声明为吸收型** ——
        #   声明在 `content/rules/elite.json` 的 `absorb` 里（引擎不硬编码任何游戏专名）。
        #   ★ 写口走 `content/absorb.py::open_shield`（引擎状态容器唯一写入口 `open_entry`，
        #     全关键字传参；引擎侧同批新增 `value` 形参）；那一口自带**形状门**：引擎那半没到
        #     就退回旧容器 ⇒ 与接线前逐字相同。**行为零变化**（引擎那边照旧吸收/扣血/清空）。
        for _sk, _sv in AFFIX.shield_entries_of(affixes, int(_mx)).items():
            ABS.open_shield(a, _sk, _sv, expire=None)
        a["_affixes"] = list(affixes)              # 阈值那类词条要在 `build` 里挂导演钩子
    if m.get("skills"):
        a["skills"] = list(m["skills"])
    # ★ Boss 阶段卡（本波）：`mods.phases` 从「只对账的数据」变成**运行期消费的声明** ——
    #   照抄一份挂在 actor 上，由 `_boss_phase_hook` 逐阶消费（它挂在 `Battle.script_hook`
    #   那个引擎现成的注入点上，精英词条走的是同一个口）。
    #   **没有 phases 的怪一个字段都不写** ⇒ 与接线前逐字相同（判据钉着这一条）。
    _ph = (m.get("mods") or {}).get("phases")
    if _ph:
        a[PH_CARD] = [dict(x) for x in _ph]
    return a


def _affix_threshold_hook(battle: Battle):
    """★ B3-24：把「血量阈值」那类词条挂成**战斗导演钩子**（引擎的 `Battle.script_hook` 注入点）。

    引擎在自动 actor 每一动之前调它（`callable(battle, actor, logs) -> bool`），返回 False =
    不拦这一动。这里只做一件事：词条声明的阈值一越过，就按声明改面板（原地的 actor 字段 ——
    引擎每次结算都现读 `actor_stats`，所以改了就真生效）。

    ★ `once` 那条必须自己守：钩子**每一动都会被调**，不守就会一路上乘（实测 12 → 60）。
    ★ 返回 `None` = 这一场一个带阈值的词条都没有 ⇒ 连钩子都不挂（与接线前逐字相同）。
    """
    defs = []
    for a in battle.sides.get(ENEMY_SIDE, []):
        for aid, th in AFFIX.thresholds_of(a.get("_affixes")):
            defs.append((a, aid, th))
    if not defs:
        return None

    def hook(b, actor, logs):
        for target, aid, th in defs:
            if actor is not target:
                continue
            # 上限取不到 = 这一动什么都不改（fail-closed：不猜一个数当分母）
            _mx_raw = target.get("max_hp")
            _mx = float(_mx_raw) if _mx_raw else 0.0
            if _mx <= 0:
                return False
            hp_now = float(target.get("hp") or 0)
            if hp_now / _mx > float(th.get("hp_below", 0) or 0):
                continue
            mark = "_afx_" + str(aid)
            if th.get("once") and target.get(mark):
                continue
            target[mark] = True
            # ★ L246 同族：atk_mult=0.0 是**合法**配置（该阈值发动后 atk 归零 = 缴械），
            #   而 `0.0 or 1` 会被吞成 1 ⇒ 先取原值，只有 None 才回落 1.0。
            _av = th.get("atk_mult")
            mult = 1.0 if _av is None else float(_av)
            target["atk"] = int(round(float(target.get("atk", 0) or 0) * mult))
            return False
        return False

    return hook


def _phase_enter(battle, actor: dict, run: dict, ph: dict, i: int, logs: list) -> None:
    """进第 `i` 阶：把这一阶的面板修正落到 actor 上 + 出一句演出。

    ★ 面板一律**从基数重算**（`run["base"]` 是这一场开场那一刻的 atk/def/spd），而且
      **没声明的格 = 回到原面板**（不沿用上一阶）—— 因为阶段会**来回走**（列阵⇄散架），
      沿用上一阶的话「回到列阵」会把散架的 def−120 / 频率×0.5 一路带回去。
      每一阶都是一份**写全的姿态**（数据里逐格声明，见 `monsters.mods.phases`）。
    ★ 演出那一行走 texts 槽位 `COMBAT_BOSS_PHASE`（`⚠️【{t} 刻】{name} 进入「{phase}」/
      👁️ {note} / 💡 {tip}`）—— 本文件一个中文都不写，`line` / `tip` 两格从数据来。
    ★ 刻数（真源 26_ §三 优化 1「所有战斗日志行统一以【N 刻】开头」）：这一行经
      `logs.append` 进**持久战斗日志**，与同族 23 条行动行同面 ⇒ 必须带刻。
      刻源 = `battle._now`（战斗绝对时刻，引擎给的原值，不自己算）。
      ★ 写 `t=int(round(...))` 而不是格式符 `{t:.0f}` —— 内容侧 `T()` 是字面 replace
      （`content/cmds_ast.py:53-55`），格式符不会被替换、会把 `{t:.0f}` 原样打上屏。
    """
    m = run["m"]
    for k in _PH_NUMS:
        m[k] = ph.get(k, _PH_DEFAULTS[k])
    m["hold"] = ph.get("hold", False)              # 逐阶声明（站桩 "block" / 回塔 True / 其余 False）
    b0 = run["base"]
    actor["atk"] = int(round(float(b0["atk"]) * float(m["atk_mult"])))
    actor["def"] = int(round(float(b0["def"]) + float(m["def_add"])))
    actor["spd"] = int(round(float(b0["spd"]) * float(m["act_rate_mult"])))
    if m["dmg_taken_mult"] is None:
        actor.pop("_dmg_taken_mult", None)         # 引擎那个承伤乘区（`landing` 现读）
    else:
        actor["_dmg_taken_mult"] = float(m["dmg_taken_mult"])
    # ★ `hold` 的两态（数据里的两种取值，不是同一个东西）：
    #   · `"block"`（站桩「不攻击，只挡」）⇒ 它这一手出**防御**：引擎的 `defend`
    #     开一格姿态窗口（`effects["defend"]`，承伤减半 —— 这才叫「挡」），且它照样进前摇窗口
    #     （所以「对方正押着一手 ⇒ 后撤退不开」那条判据在站桩里仍然成立）。
    #   · `True`（回塔「不再攻击，走向塔边」）⇒ 本刻**不出手**（钩子回 True 拦下），
    #     它只是在走。
    if m["hold"] == "block":
        actor["auto_act"] = {"act": {"type": "defend"}}
    else:
        actor.pop("auto_act", None)                # 下一阶要还手了（不还手的态由上面那句表达）
    run["i"], run["n"] = int(i), 0
    from .cmds_ast import T                        # ★ 本地 import（免得包装载期成环）
    logs.append(T("COMBAT_BOSS_PHASE", t=int(round(float(getattr(battle, "_now", 0.0) or 0.0))),
                  name=actor.get("name", ""), phase=ph.get("name", ""),
                  note=ph.get("line", ""), tip=ph.get("tip", "")))


def _phase_frame(battle, actor: dict, logs: list) -> bool:
    """这一动：该不该换阶（换了就出演出并**拦下本刻**）/ 不换就照这一阶的 `hold` 决定出不出手。

    ★ 换阶只认**血那一档**（`hp_below`）—— 四阶 = 四条触发，逐条照真源
      `06_第一阶段垂直切片/00_第一阶段内容总纲_v1.md §四` 的「触发」列：
      站桩（开场 / hp 满）→ 列阵（玩家第一次打到它 = hp < 100%）→
      散架（hp < 50%）→ 回塔（hp < 20%，终局）。
      `turns`（列阵 8 次 / 散架 5 次）**本波不参与换阶**：它与血阈自相矛盾 —— 照它落地
      （列阵走完 8 手就换散架）会让散架的「疲态窗口」在七成血就打开，**设计档单人**从
      「全败」变成可过（真跑 lv19 3/96、lv20 6/96）⇒ 撞 `probe_combat` 那条「Boss 是团队内容、
      缩放之前单人过不了」的硬判据。本波按血阈落地、把这一格留给主线裁（见 `_notes.md §真源行`）。
    """
    card = actor.get(PH_CARD) or []
    # ★ 两步取值（`probe_panel ④` 那条静态守卫扫的是「`"max_hp"` 后面紧跟 `or <数字>`」那种
    #   **写死上限**的写法 —— 与 `_affix_threshold_hook` / `instance.turn_lines` 同一款写法）。
    _mx_raw = actor.get("max_hp")
    _mx = float(_mx_raw) if _mx_raw else 0.0
    if _mx <= 0:
        return False
    run = actor.get(PH_RUN)
    if not isinstance(run, dict):
        run = {"i": -1,
               "base": {"atk": float(actor.get("atk", 0) or 0),
                        "def": float(actor.get("def", 0) or 0),
                        "spd": float(actor.get("spd", 0) or 0)},
               "m": dict(_PH_DEFAULTS)}
        actor[PH_RUN] = run
    # ★ `or -1` 那种写法要不得：`0` 是**合法阶号**（第 0 阶），`0 or -1` 会被吞成 -1 ⇒
    #   每一动都当成「还没进过第 0 阶」⇒ 演出每动重播一遍、永远停在站桩（实测踩到）。
    _i = run.get("i")
    i = -1 if _i is None else int(_i)
    nxt = 0 if i < 0 else None                     # 第一次进来 = 进第 0 阶（开场那一阶）
    if nxt is None and 0 <= i < len(card):
        _below = card[i].get("hp_below")
        if _below is not None and (float(actor.get("hp", 0) or 0) / _mx) < float(_below):
            nxt = i + 1                            # 血掉过这一档 ⇒ 换下一阶（顺序 = 真源那四阶）
    if nxt is not None and nxt < len(card):
        _phase_enter(battle, actor, run, card[nxt], nxt, logs)
        return True                                # ★ 演出刻：本刻不出手，照推 ct（照导演帧的语义）
    # 不换阶：照这一阶的姿态出手 / 不出手（`hold` 的三态见 `_phase_enter`）
    return run["m"].get("hold") is True            # 回塔「不再攻击」= 本刻拦下；其余照常出手


def _boss_phase_hook(battle: Battle):
    """★ 本波：把 `monsters.mods.phases`（Boss 阶段卡）接上运行期 —— 返回钩子 / `None`。

    真源：`06_第一阶段垂直切片/22_旧哨塔_逐间设计_v1.md §二·12`（四阶段卡）·
      `06_第一阶段垂直切片/14_怪物原型_v1.md §四`（Boss 用阶段卡 + 技能序列）·
      `06_第一阶段垂直切片/00_第一阶段内容总纲_v1.md §四`（触发那一列）。
    引擎侧一个字没改：用的就是它给内容侧的注入点（`Battle.script_hook`）。

    与 `_affix_threshold_hook` **合成一条**（`attach_script_hooks`）—— 两者都在改 actor 面板，
      一条链上先词条后阶段；返回 True 的语义都是「本刻拦下」。
    ★ 装配期四条 fail-closed（当场抛，不许出一行「👁️ 」空话、也不许运行到一半才发现）：
      · 每一阶都得有 `name` / `line` / `tip`；
      · 除最后一阶外，每一阶都得有 `hp_below`，而且**严格递减**（阶段 = 血带，
        顺序就是真源那四阶 —— 顺序写乱了当场红）。
    """
    cards = [a for a in battle.sides.get(ENEMY_SIDE, []) if a.get(PH_CARD)]
    if not cards:
        return None
    for a in cards:
        card = a[PH_CARD]
        for ph in card:
            miss = [k for k in _PH_REQUIRED if not str(ph.get(k) or "").strip()]
            if miss:
                raise ValueError("阶段卡缺 %s（%s 的第 %r 阶）—— 演出那两行与阶段名都得有"
                                 % (miss, a.get("uid"), ph.get("name") or card.index(ph)))
        _band = [ph.get("hp_below") for ph in card[:-1]]
        if any(x is None for x in _band) \
                or any(float(_band[k]) <= float(_band[k + 1]) for k in range(len(_band) - 1)):
            raise ValueError("阶段卡的血带不对（%s）：除最后一阶外，每阶的 hp_below 都得有且"
                             "**严格递减**（站桩 1.0 → 列阵 0.5 → 散架 0.2 → 回塔 无）"
                             % (_band,))
        _hold_bad = [ph.get("hold") for ph in card
                     if ph.get("hold") not in (False, True, "block", None)]
        if _hold_bad:
            raise ValueError("阶段卡的 `hold` 只有三种取值（不写 / true = 本刻不出手 / \"block\" = "
                             "只挡）：%r" % (_hold_bad,))

    def hook(b, actor, logs):
        for a in cards:
            if a is actor:
                return _phase_frame(b, a, logs)
        return False

    return hook


def attach_script_hooks(battle: Battle) -> None:
    """把内容侧那几条**导演钩子**挂到这一场上（引擎现成的注入点 `Battle.script_hook`）。

    ★ 为什么要有这个函数：钩子是**运行回调** —— 引擎的 `serialize.from_state` 明写
      「这些钩子需要在恢复后自己重新挂」（`docs/engine-wiki/guides/serialize-and-resume.md`）。
      「场」是落盘的一场（机器人重启 / 换一个进程接着打都靠它），所以 `instance._restore`
      恢复之后必须再走一次这里 —— 与 `panel_build.ensure_stack` 补登记是同一个道理。
    ★ 一条都不挂 ⇒ `script_hook = None`（= 与接线前逐字相同：引擎连问都不问）。
    """
    hooks = [h for h in (_affix_threshold_hook(battle), _boss_phase_hook(battle)) if h]
    if not hooks:
        battle.script_hook = None
        return

    def hook(b, actor, logs):
        for fn in hooks:
            if fn(b, actor, logs):
                return True
        return False

    battle.script_hook = hook


def build(player: dict, monster_ids, monsters: dict, *, party: int | None = None,
          override=None, affixes=None, hp_mults=None, players=None,
          uid: str | None = None) -> Battle:
    """组一场战斗：玩家 1 人 vs 指定的怪。

    `party` = 队伍人数（★ B3-25 起由 `cmds_battle._party_now` **进战那一刻现算**：
    在队 + 同节点 + 活人 —— 单人 = 1、不知道 = None）——
    它只影响「团队内容」那几只怪的面板（`mods.party_scale`），别的怪一格不动。
    `override` = **非内置动作**的回调（引擎 `Battle.action_override` 那一个注入面）——
    B3-23 那几手（打断 / 用物 / 换手）走它；不传 = 与改前逐字相同（引擎不认识任何游戏词）。
    `uid` = 身份（B3-28 ①），透传 `player_actor` —— 面板栈的键带上它，不撞别人的格。

    ★ B3-24（精英词条的落点，全部可选；**不传 = 与接线前逐字相同**）：
      · `affixes` —— 这一场敌人的精英词条 id（`affix.roll` 抽出来的那一组）；
      · `hp_mults` —— 与 `monster_ids` 等长的「每只的生命倍数」（群居的第二只半血）。

    ★ B3-26（多人轮流制那一批）：`players` = 这一场**进场的那几份玩家档**（每人一份，
      按入队序）—— 每份都走同一个 `player_actor`，`sides["player"]` 就是这一串
      （引擎每边本来就是列表，引擎零改动）。**不传 = 与改前逐字相同**（只放 `player` 一个）。
      每份档上的 `uid` 必须各不相同（引擎靠它找「该谁动」与落账）—— 由调用方保证。
    """
    if players is not None:
        _pl = list(players)
        if not _pl:
            raise ValueError("players 给了但是空的（要单人就不要传这个参数）：%r" % (players,))
        _uids = [str(x.get("uid") or "") for x in _pl]
        if any(not u for u in _uids) or len(set(_uids)) != len(_uids):
            raise ValueError("players 里每份档都得带**各不相同**的 uid：%r" % (_uids,))
        # ★ 审计 L966：这一路原先**不传 uid** ⇒ `player_actor` 拿到 `uid=None`
        #   ⇒ `panel_build._person_tag` 退回**档指纹**（`f-…`）。而上面 489 行刚校验过
        #   「每份档都带**各不相同**的 uid」—— 身份就在手边却没往下传。
        #   代价（实测 · 端到端跑出来的）：**同职业同等级同加点同装备的两个玩家共用
        #   同一格面板栈**（`aetheran.cls_knight@10#f-c3cfe0dd80a0`，两人完全相同），
        #   后造的盖先造的 ⇒ 甲开战后被乙改一份档就带走面板（B3-28 ① 当初修掉的那个
        #   「同进程里同职业同等级共用一格」原样复发，且只在**多人那条路**上）。
        #   ★ 单人那条路本来是对的（`player_actor(player, uid=uid)`）—— 只有这一行漏了。
        ps = [player_actor(x, uid=str(x.get("uid") or "")) for x in _pl]
    else:
        ps = [player_actor(player, uid=uid)]
    es = []
    for i, mid in enumerate(monster_ids):
        m = monsters.get(mid)
        if not m:
            continue
        hm = (list(hp_mults)[i] if hp_mults and i < len(hp_mults) else None)
        a = monster_actor(mid, m, party=party, affixes=affixes, hp_mult=hm)
        es.append(a)
    b = Battle("monster", sides={PLAYER_SIDE: ps, ENEMY_SIDE: es}, action_override=override,
               # ★ B3-27：选目标注入点（引擎给内容侧的位）—— 挑战咆哮那一条要用它。
               #   没挂嘲讽态 ⇒ 回 None ⇒ 引擎走原来的目标解析（与接线前逐字相同）。
               target_picker=MECH.taunt_picker,
               # ★ P-1：战斗日志的文案槽位（引擎 `Battle(text=…)` 那一口）。
               #   表里**只有声明过的那几条**（`content/rules/battle_text.json`）⇒ 其余日志
               #   走引擎兜底模板、逐字节不变（引擎 `render_or` 的既定语义）。
               text=BT.battle_text())
    # ★ B3-24 两条词条通道要**在 Battle 造好之后**落（引擎构造期会给全体播种初始 ct）：
    ct = AFFIX.opening_ct(affixes)
    if ct is not None:
        for a in es:                               # 潜伏：第一动排在所有行动之前（先手）
            a["ct"] = float(ct)
    # ★ 导演钩子（引擎 `Battle.script_hook` 那一个注入点）：精英词条的血量阈值 + Boss 阶段卡。
    #   一条都不挂 ⇒ `script_hook` 是 None ⇒ 与接线前逐字相同。
    attach_script_hooks(b)
    return b


def run_auto(player: dict, monster_ids, monsters: dict, *, seed: int | None = None,
             party: int | None = None, affixes=None, hp_mults=None,
             uid: str | None = None):
    """★ 第一版主路径：自动打完，返回 (结果, 日志行, 玩家战后血量)。"""
    if seed is not None:
        random.seed(seed)                       # 可复现（探针用）
    b = build(player, monster_ids, monsters, party=party, affixes=affixes,
              hp_mults=hp_mults, uid=uid)
    logs: list = []
    b.auto_run(logs)
    pa = b.sides[PLAYER_SIDE][0]
    return b.result, [str(x) for x in logs], int(pa.get("hp", 0))


#: ★ 本波（2026-09-27 · 任务②③）：**等级带**那一格的唯一读口 —— 声明表 `content/rules/level_band.json`
_BAND_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules", "level_band.json")
_BAND_CACHE = None


def band_rules() -> dict:
    """`content/rules/level_band.json`（读一次；读不到 / 形状坏 ⇒ 当场抛 —— 没有默认值）。"""
    global _BAND_CACHE
    if _BAND_CACHE is None:
        with open(_BAND_PATH, encoding="utf-8") as f:
            got = json.load(f)
        if not isinstance(got, dict):
            raise ValueError("level_band.json 得是一张表：%r" % (got,))
        _BAND_CACHE = got
    return _BAND_CACHE


def max_level_diff() -> int:
    """**等级带**的宽度（唯一一口 = `rules/level_band.json::max_level_diff.value`）。

    `|怪的等级 − 那个等级| ≤ 它` ⇒ 带内。这个数**不在代码里**（表缺 / 写成 bool / 负数 ⇒ 当场抛）。
    边界「5」的来历（差 ≥ 5 ⇒ 出带）与两个读口见那份表的抬头。
    """
    n = (band_rules().get("max_level_diff") or {}).get("value")
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise ValueError("level_band.json 的 max_level_diff.value 得是 0 以上的整数（没有默认值）：%r" % (n,))
    return n


def in_band(mon_lv, level) -> bool:
    """这只怪的等级落在「这个等级」的带里吗 —— **两个读口共用这一条**（悬赏池 / 『观察』那句）。

    · 悬赏轮换池（`cmds_quest._encounterable`）：`level` = 该档标称等级（单子上印的那个数）；
    · 『观察』那一栏（`cmds_tower.foe_lines_here`）：`level` = 这一站的站基准（最弱那一只）。
    fail-closed：等级取不到 / ≤ 0 ⇒ False（不猜、不兜底）。
    """
    try:
        a, b = int(mon_lv), int(level)
    except (TypeError, ValueError):
        return False
    if a <= 0 or b <= 0:
        return False
    return abs(a - b) <= max_level_diff()


def encounter_cand(monsters: dict, loc: str, node: str, level: int, keep: int = 3):
    """这一格上「说得上话」的怪 → `(全部候选, 按等级最近的前 keep 只)`。

    ★ 两处共用这一处（同一把尺子）：
       · 遇敌挑选 `pick_encounter`（玩家敲『攻击』那一下真挑哪一只）；
      · **悬赏轮换池的可遇性**（`cmds_quest._encounterable` / `_pool_of` —— 单子点名的怪
        必须在这一站按这一档的等级真碰得上）。
      两处要回答的是同一件事；各写一份 = 迟早对不上（K74 那一族）。
      ★ 探针那边**另写一份**（`scripts/probe_quests.py` ㉛ / `probe_qloop.py` ②）——
        两处的错不会互相掩盖（照 ⑬/⑳ 的老规矩）。

    门（与 `pick_encounter` 的抬头同一段）：`habitat.maps` 必给（不含这一张图 ⇒ 不是候选），
    给了 `habitat.nodes` 再收窄到那几个节点；候选为空就回**空表**（村镇 / 没挂怪的图）。
    """
    cand = []
    for k, m in monsters.items():
        hb = m.get("habitat") or {}
        if loc not in (hb.get("maps") or []):
            continue                                  # ★ 不属于这张图的怪，一律不出现
        ns = hb.get("nodes") or []
        if ns and node not in ns:
            continue                                  # ★ 收窄到节点
        cand.append(k)
    near = sorted(cand, key=lambda k: abs(int(monsters[k].get("lv", 1)) - int(level)))
    return cand, near[:max(0, int(keep))]


def pick_encounter(monsters: dict, loc: str, node: str, level: int, *, seed: int | None = None,
                   mul: dict | None = None):
    """从怪里挑一只「这一带、这个等级」的（第一版：按等级最近 + 可复现随机）。

    ★ 「说得上话的怪 + 按等级最近的前 3」这一半 = `encounter_cand`（**唯一一处**）——
      悬赏轮换池的可遇性（`cmds_quest._encounterable`）问的就是它；这里只多做「挑一只」。

    ★ P-30：地点**真的参与挑选**了 —— 每条怪在 monsters 域里挂着 `habitat`：
      `maps` = 会出现的图（必给，空 = 哪儿都不出）；`nodes` = 再收窄到这几个节点
      （可选 / 空 = 该图任意节点）。先按图筛（给了 nodes 再按节点筛），再按等级最近挑。
      **候选为空就返回 `[]`，不兜底**：村镇是安全区，指令那边会回「这一带暂时没有遇到什么」。

    ★ B3-7：**档位不再当门**（原先只放 普通/精英/头目 ⇒ 号角室的层主房与塔顶那两间**一只都
      挑不出来**：敲『攻击』只回「这一带暂时没有遇到什么」）。现在**唯一的门是 `habitat`**
      —— 地点说得上话的怪就能碰上（层主 / Boss 也是怪）。这么改有三条好处：
        · 档位这一栏不再是代码里的机器键（P-20 第二刀的方向：取值全从域里来）；
        · 野外不会多出怪 —— 层主与 Boss 的 `habitat` 只写着旧哨塔那两张节点，图/节点对不上的
          一律不是候选（`probe_monsters` ⑨⑩ 钉着这一条）；
        · 要收窄哪个档位，让它自己的 `habitat` 说话（数据层决定，不在这里加白名单）。

    ★ B3-5：`mul` = 现在开场事件给的遇敌加权（`{怪 id: 倍数}`，来源 `calendar.encounter_mul`）。
      **没给 = 零变化**（还是 `choice` 那一支，同一个种子挑出同一只 —— 判据钉着这一条）；
      给了就按权重挑（倍数为 0 的候选天然挑不中）。
    """
    cand, top = encounter_cand(monsters, loc, node, level)
    if not cand:
        return []                                     # ★ 不兜底（村镇 / 没挂怪的图）
    rnd = random.Random(seed)
    if not mul:
        return [rnd.choice(top)]                      # ★ 没给 = 与改前逐字相同
    weights = [max(0, int(mul.get(k, 1) or 0)) for k in top]
    if sum(weights) <= 0:
        return [rnd.choice(top)]
    return [rnd.choices(top, weights=weights, k=1)[0]]
