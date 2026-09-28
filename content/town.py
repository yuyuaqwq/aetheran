# -*- coding: utf-8 -*-
"""镇上那一族：「哪一站」与「在不在那一站」的**唯一解析处**。

为什么单开这个模块（B4-12）
--------------------------
  · `_func_node`（镇上带某职能的人在哪一站）原先在 `cmds_places` 里，可 `cmds_quest` /
    `cmds_more` / `cmds_recipe` 也要用它 —— 而那三个模块 import `cmds_places` 会成环
    （`cmds_places` → `cmds_more` → `cmds_quest`）；
  · `town_gate`（`guard_desc` 写着「在镇上 / 在公会 / 在铺子 / 在客栈」那一族的**唯一执行面**）
    同样要能被上面那几个模块直接 import；
  · 放到基座 `cmds_ast` 里也不行 —— 它要读 `npcs` 域，会撞 `probe_npcs` 那条静态守卫
    （「`cmds_ast.py` 里 `_data("npcs")` 只许 1 处」：列谁在场只能走 `_npcs_here` 一口，K65）。

⇒ 本模块只 import 基座 `cmds_ast`（`TOWN` / `_data` / `_name_of_node` / `T`），**不被它 import**，
  因此谁都能用、怎么排 import 都不成环（与 `content/scene.py` / `content/argv.py` 同一个路子）。
"""
from __future__ import annotations

from .cmds_ast import TOWN, _data, _name_of_node, T

def _func_spots(func: str, loc: str = TOWN) -> dict:
    """这张图上带某个职能的人，按所在节点分组 → `{节点: [(人 id, 记录), …]}`。

    职能键 = `npcs.funcs` 里那几个 ASCII 词（heal / inn / board / smith…）—— 域里现成的一栏，
    不另建一张「哪个指令对哪个人」的表。
    ★ B4-12 从 `cmds_places` 搬到本模块：`cmds_quest` / `cmds_more` / `cmds_recipe` 也要用它，
      而那三个模块 import `cmds_places` 会成环（`cmds_places` → `cmds_more` → `cmds_quest`）。
    """
    out: dict = {}
    for k, v in _data("npcs").items():
        if not isinstance(v, dict) or v.get("map") != loc:
            continue
        if func not in (v.get("funcs") or []):
            continue
        out.setdefault(str(v.get("subarea") or ""), []).append((k, v))
    return out


def _func_node(func: str, loc: str = TOWN) -> str:
    """带这个职能的人所在的那一站 —— **叫不准就给空串**（没有 / 分在两处都不猜）。"""
    spots = _func_spots(func, loc)
    return next(iter(spots)) if len(spots) == 1 else ""


def _base_here(loc: str, node: str) -> dict:
    """这一站的**基位名单** -> `{npc id: 记录}`：域里写着 `subarea` 停在这儿的那几位（不看条件）。

    ★ L2474-3：原先这段判据**逐字两份**（`station_empty` / `absent_here` 各抄一遍），
      而两条的口径注释都自称「同一份判定」—— 改一边就分叉，分叉的后果正是 P1 BUG-5
      那一族（画面说「有人在旁边坐着」、名册说一个人都没有）。⇒ 收成这一口，两边都走它。
    ★ **不带 `or {}`**（L2474-4）：域是必存在的（`probe_npcs` K65 钉住读法；基座
      `cmds_ast.py:571` 同一份域读也不带）⇒ 域读不出来应当炸，不该静默当「空镇」。
    """
    return {k: v for k, v in _data("npcs").items()
            if isinstance(v, dict) and v.get("map") == loc and v.get("subarea") == node}


def station_empty(loc: str, node: str, p=None, st: dict | None = None) -> bool:
    """这一站**本该有人、此刻却一个都不在** → True（★ 本波 · P1 BUG-5）。

    为什么要有它：节点级场景是**静态文本**，可这一站的人有作息 / 会被事件吸走
      （哈根只在昏/夜；小满、老陶集日被 `effects.crowd` 吸到挂板墙）⇒ 画面里写着
      「有人在旁边坐着」，名册（『观察』的「人在」栏 / 『搭话』）里却一个人都没有 ——
      玩家被文案指去『搭话』，只得到「这儿没有别人」。

    判法：
      · **基位** = 域里写着的 `subarea`（这一位平时站哪儿 —— **不看条件**，条件别处判）
      · **到场** = 走唯一一口 `_npcs_here`（时辰 / 天气 / 事件三档一起看 —— 与『观察』同一处）
      ⇒ 「人不在那一版场景」（`scene.empty_key`）与「空屋回话」（31_NPC作息 §四）共用这一个判据。

    基位就没人（野外 / 塔内 / 两个镇口）⇒ 恒 False（不进这一支；空版场景也只是可选的）。
    """
    base = set(_base_here(loc, node))
    if not base:
        return False
    from .cmds_ast import _npcs_here                      # 本地 import：与 `town_gate` 同一个理由
    here = {k for k, _v in _npcs_here(loc, node, st, p)}
    return not (base & here)


def absent_here(loc: str, node: str, p=None, st: dict | None = None) -> list:
    """这一站**基位有人、此刻按作息还没来**的那几位 → `[(npc id, 记录)]`（★ g4-⑨）。

    口径 = `station_empty` 的同一份判定（基位 ∪ 到场），只是这里要**哪几位**：
      · 基位 = 域里写着的 `subarea`（不看条件）
      · 到场 = 唯一一口 `_npcs_here`（时辰 / 天气 / 事件三档一起看）
    消费端 = `cmds_ast.npc_gone_lines`（观察 / 搭话在「一个人都没有」时逐位点名 +
    他什么时候在 —— 31_NPC作息 §四）。位次 = 域里的插入序（稳定、可复现）。
    """
    base = list(_base_here(loc, node).items())
    if not base:
        return []
    from .cmds_ast import _npcs_here                      # 本地 import：与 `town_gate` 同一个理由
    here = {k for k, _v in _npcs_here(loc, node, st, p)}
    return [(k, v) for k, v in base if k not in here]


def town_gate(p, node=None, notown: str = "SYS_PLACE_NOTOWN", away: str = "SYS_PLACE_AWAY",
                away_unset: str = "SYS_PLACE_AWAY_UNSET") -> str:
    """「回镇上 / 走到那一站」这一族守卫的**唯一执行面**（`guard_desc`：在镇上 · 在公会 · 在铺子 · 在客栈）。

    返回该回的那一句（空串 = 放行）：
      · 不在镇上 ⇒ `notown`（默认「这几处都在镇上 —— 出了镇就找不到了。」）
      · 在镇上、但没走到那一站 ⇒ `away`（指路）。`node` 三种写法：
          `None` = 这一族**不核**那一站（旧货 / 商队 / 卖出 —— 铺子与歇脚处没有单独一站）；
          节点 id = 必须站到那一站；空串 = 叫不准那一站（也拦 —— fail-closed，不假装在）。

    ★ L2474：「叫不准那一站」原先是**把空串灌进 `away`的 `{name}` 槽——
      玩家看见的是『不在这儿 —— 打『去 』走一趟。』（**打出一个不存在的命令**）。
      玩家手上没有任何句子可以引导他。现在走 `away_unset`（**无 `{name}` 参**）
      —— 口径不变（仍然拦），只是不再玩家面上出现一个拼不凑的指引。

    ★ 为什么收成一个口（B4-12 · 端到端玩出来的真 bug）：同一条 `guard_desc` 原先**两种实现** ——
      客栈 / 教堂 / 旧货 / 登记 / 商队判脚下，而 **公会 / 悬赏 / 看 <编号> / 铁匠铺 一句都不判**：
      实测人站在骨田照样能把挂板墙看个遍、把活接了（同一个位置『登记』回的是「这几处都在镇上」）。
    ★ **这道守卫管的是哪一族**（L2474-2 订正 · 原注释在这里说过头了）：
      判据 `probe_cmds ⑰` 覆盖面①是**按 `guard_desc` 字样**筛的 ——
      `在镇上 / 在公会 / 在铺子 / 在客栈` 那 16 条**拦路型**声明才在它眼里。
      ⇒ 原话「谁再自己写一遍 `p["loc"] != TOWN`，当场红」**不成立**：`hint` 的
      `guard_desc = "随时"`（`commands.json`）根本不在那一族里，而
      `cmds_ast.py::hint` 恰恰**合法地**手写了这一句 —— 它不是「拦路」，
      是**报信**（野外时补一句「这儿是野外」），拦了就等于把指令整条封掉，语义不同。
      真实边界现已由门禁钉住（`probe_onsite` ⑯-边界）：**手写 `p["loc"] != TOWN` 只许出现在
      `hint` 这一个报信函数里**；别处再写一份（不论新指令还是新一族）当场红。
      —— 即：原来那句是**虚假的安全感**（下一个人照它加手写守卫不会被拦），现在是真的。
    """
    if p.get("loc") != TOWN:
        return T(notown)
    if node is None:
        return ""
    if not node:
        # 叫不准那一站（函能人分在两处 / 一个都没有）——
        # 不能拿空串去填 `away` 的 `{name}`：那会输出『打『去 』走一趟』。
        return T(away_unset)
    if p.get("node") != node:
        return T(away, name=_name_of_node(TOWN, node))
    return ""
