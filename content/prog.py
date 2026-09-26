# -*- coding: utf-8 -*-
"""对话旗标族（`main*_done` / `main*_active` / `quest_*_done` / `nameline_done`）——
**slug ↔ 真实进度** 的唯一一处：读端、写端都走它。

★ 为什么要有这一份（改前的事实）：`content/data/dialogues.json` 里有 12 条台词挂在
  `{"flag": "<slug>"}` 上（哈根的 `meet` 三段、格雷/娜娜/贝拉/德里克/莉安/杜林/玛莎的
  `main` 层、小满与艾德的 `daily`/`hidden`、哈根的 `hidden`……），而**全仓 + 引擎的写端数为 0**
  —— 那些 slug 一处在写着、一处在读着，中间那一步没人做 ⇒ 整族对白永久出不来
  （`cmds_talk._pick_indexed` 里 `flag` 那一支只读不写）。

★ 口径（本波立的单一真源 · 写在唯一一处）：

```text
slug 的形状            ↔  真实进度（读的还是那几本**已经在档上**的账）
main<NN>_done          ←→  q_main_<NN> **交掉**（账 = flags.quests_done / flags.quests[<id>].done）
main<NN>_active        ←→  q_main_<NN> **在手上、还没交**（账 = flags.quests_active）
quest_return_stone_done ←→ q_side_13 交掉（支 13「还石头」· 小满）
quest_lamp_oil_done    ←→  q_side_07 交掉（支 7「白烛堂的灯」· 艾德）
nameline_done          ←→  q_main_11 交掉（主 11 的交付行 =「隐藏线「名字」推进 → 莉安的长独白」）
asked_for_rain_herb    ←→  q_side_04「雨后的东西」**接过或交掉**（= 问过娜娜那种雨后才出的菌）
```

  · 前两组是**语法**（`main<NN>` ↔ 主 `<NN>` —— 真源 `24_任务线_v1.md §一` 的编号），
    不需要为每一条再手抄一行；后四组名字里对不出机器键，逐条写在 `_NAMED` 里。
  · ★ **域里现在用到的 slug 一个都不许落空**：`audit()` 现扫 dialogues 域，凡认不出的当场点名
    （谁哪天在域里写一个新 slug，探针先红 —— 不许再开一个「写了等于没写」的死旗标）。
  · ★ **写端** = `resync(p, qid)`：这条委托的状态每变一次（接 / 交 / 放弃）就把它名下的 slug
    **照真实进度**重写一遍（成立写 True，不成立写回 False）。谁也不许手写那几格
    ——「同一件事只有一处写」。
  · ★ **读端** = `flag_ok(p, token)`：表里的 slug 一律**以真实进度为准**
    （老档里进度在、旗标那格当年没写 ⇒ 照样成立；旗标写着而进度不成立 ⇒ **不算满足**，
    不刷出不该出的台词）。表里没有的 token（`card` / `lore_scripts` / `horn_fixed` 那一族）
    走老口径：读那一格本身，一个字没变。

★ 与 `flags.side_<名字>` 那条死路径**不是一件事**：那条路是 `_obj_ok` 拿来判交付的
  （`probe_quests` 钉着「字面量只许 1 处」）；这一份只服务**对话的 need 条件**。

★ 那四条对不出机器键的 slug —— **依据逐条列在这里**（真源只读，行号与本包落点写全）：

  · `nameline_done` ← `q_main_11`
      真源 `06_第一阶段垂直切片/24_任务线_v1.md §一` 主 11「白桦上的名字」那一块的
      「交付 隐藏线「名字」推进 → 莉安的长独白」（第 126 行）—— 主 11 交掉 = 名字线推进。
  · `quest_return_stone_done` ← `q_side_13`
      真源 `24_任务线_v1.md §二` 支线表第 13 行「还石头 ｜ 小满 ｜ 把石头还给该还的地方
      ｜ ★ 彩蛋 2（碑缺的一角）」（第 164 行）—— 交掉这条就是「还回去了」。
  · `quest_lamp_oil_done` ← `q_side_07`
      真源 `24_任务线_v1.md §二` 支线表第 7 行「白烛堂的灯 ｜ 艾德 ｜ 送灯油 → 陪他配一次
      ｜ ★ 听他念全本祷词（彩蛋 7）」（第 158 行）—— 交掉这条 = 灯油送到了。
  · `asked_for_rain_herb` ← `q_side_04`（接过或交掉）
      真源 `06_第一阶段垂直切片/23_NPC设定_v6.md §3 娜娜` 那一段的题注「（你问一个她昨天就
      说过没有的东西）」（第 115 行）—— 那条问的就是 `24 §二` 支线表第 4 行「雨后的东西」
      （雨天去采稀有的菌）；「问过」在本包的账上 = **接过或交掉** q_side_04。
      ★ 真源只写了「问一个她昨天就说过没有的东西」，没给机器键 ⇒ 这一条的映射是本件的
      **裁决**（要新开一本「问过」的账 = 新容器，属另一件），登记在 `_notes.md`。
"""
from __future__ import annotations

import re

from . import calendar as CAL             # ★ 主线交没交的唯一读口（`main_done`）
from .cmds_ast import _data               # ★ 域读口（与别处同一个）

#: `main<NN>_done` / `main<NN>_active` 的**语法**（编号 ↔ 任务 id 的对应就写在这里一处）
_MAIN_SLUG = re.compile(r"^main(\d+)_(done|active)$")

#: 对不出机器键的那四条（依据见模块抬头那一节 —— **逐条真源行**）
_NAMED = {
    "nameline_done": ("q_main_11", "done"),
    "quest_return_stone_done": ("q_side_13", "done"),
    "quest_lamp_oil_done": ("q_side_07", "done"),
    "asked_for_rain_herb": ("q_side_04", "taken"),
}

#: 状态三种：`done` 交掉 · `active` 在手上 · `taken` 接过或交掉
STATES = ("done", "active", "taken")


def map_slug(slug):
    """slug → `(委托 id, 状态)`；认不出回 `None`（fail-closed：不猜）。"""
    n = str(slug or "")
    if n in _NAMED:
        return _NAMED[n][0], _NAMED[n][1]
    m = _MAIN_SLUG.match(n)
    if not m:
        return None
    return "q_main_%02d" % int(m.group(1)), m.group(2)


def why_of(slug) -> str:
    """这一条 slug 的**落点**（给探针印出来看）：`<slug> -> <委托 id>:<状态>`；认不出回空串。

    ★ 依据的**真源行**写在模块抬头那一节里（这一格只回答「接到哪条委托、看哪本账」——
      机器可核的那一半）。
    """
    m = map_slug(slug)
    return "%s -> %s:%s" % (str(slug), m[0], m[1]) if m else ""


def domain_slugs() -> list:
    """dialogues 域里**真正用到**的 flag slug（现扫域 —— 一个镜像表都不手抄）。

    用法是 `{"need": {"flag": "<slug>"}}`；别的 need 键（`holding` / `time` …）不在此列。
    """
    out = []
    for _k, v in sorted(_data("dialogues").items()):
        for _nd in ((v.get("nodes") or {}) if isinstance(v, dict) else {}).values():
            for t in ((_nd or {}).get("texts") or []):
                need = (t or {}).get("need")
                if not isinstance(need, dict):
                    continue
                f = need.get("flag")
                if f and str(f) not in out:
                    out.append(str(f))
    return out


def audit() -> list:
    """域里用到的 slug 里**认不出真实进度**的那些（空表 = 整族都有来源 · fail-closed 名单）。"""
    return [s for s in domain_slugs() if map_slug(s) is None]


def slugs_of(qid) -> list:
    """这条委托名下**域里在用**的那几个 slug（写端只写这些 —— 不塞没人读的键）。"""
    return sorted(s for s in domain_slugs() if (map_slug(s) or (None,))[0] == str(qid))


def truth(p, slug) -> bool:
    """这一条 slug 的**真实进度**成不成立（只看那几本已经在档上的账 —— 不看旗标那一格）。

    `done` / `active` / `taken` 三种状态各看各的账；认不出的 slug ⇒ False（fail-closed）。
    """
    m = map_slug(slug)
    if not m:
        return False
    qid, state = m
    done = bool(CAL.main_done(p, qid))
    if state == "done":
        return done
    act = qid in (((p or {}).get("flags") or {}).get("quests_active") or [])
    if state == "active":
        return bool(act)
    return bool(done or act)


def flag_ok(p, token) -> bool:
    """★ 对话 `need` 里 `{"flag": token}` 的**唯一判定口**。

    · 表里的 slug（那一族）⇒ 以**真实进度**为准：老档（进度在、旗标那格没写）照样成立；
      旗标写着而进度不成立 ⇒ 不算满足（脏旗标不许把台词刷出来）。
    · 表外的 token ⇒ 走老口径 `bool(flags[token])`（`card` / `lore_scripts` / `horn_fixed`
      那些各有各的写端，本模块一个字不碰）。
    """
    if map_slug(token):
        return truth(p, token)
    return bool(((p or {}).get("flags") or {}).get(token))


def resync(p, qid) -> list:
    """★ **写端唯一一口**：把这条委托名下的 slug 照真实进度重写一遍，返回写到的 slug 清单。

    调用时机（状态一变的每一处）：`quest_accept`（接活）· `quest_deliver`（交活）·
    `quest_abandon`（放弃）。三处都调 ⇒ 「接了就算完成」这种半拍状态不会被写下来
    （`main09_active` 在交掉那一刻会被写回 False，放弃那一刻也是）。
    ★ 换新对象写（K57：别把别人那份 flags 一起改脏）；进度不成立 ⇒ 写回 False，不留幽灵旗标。
    """
    f = dict((p or {}).get("flags") or {})
    p["flags"] = f
    out = []
    for slug in slugs_of(qid):
        v = truth(p, slug)
        if bool(f.get(slug)) != v:
            f[slug] = v
        out.append(slug)
    return out
