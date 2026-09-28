# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 第二组（对话 / 战斗外的交互）

★ P-12（取句顺序）．**人先熟、事才说** —— 这一档的口径全在本文件里，两处：
  ① **层序**（`LAYERS`）：`meet`（初次）→ `daily`（熟了）→ `main`（主线推到）
     → `hidden`（隐藏条件满足）→ `idle`。
     原先是 `main → hidden → meet → daily` ⇒ 刚认识一个人，对方开口就说主线（剧透），
     底牌（彩蛋那一层）也一见面就漏；哈根的 hidden 兜底句还把 meet / daily 永久遮住
     （P-12 记：德里克的雨天那句只有直调 `_pick_line` 时出得来）。
     原先每棵树的 `start` 字段都写着 `"meet"` —— 排头就是它，那条「start 没人读」也对上了；
     ★ P-62（2026-09-26）已把那一格**从 dialogues 域与 schema 一起撤掉**（白写字段不留），
     取句顺序只认本文件的 `LAYERS` —— 谁再把那一格接回来就是开第二个口径。
  ② **熟不熟**：同一个对话树**搭过 ≥ `FAMILIAR_TALKS`（3）次话**（这一次也算）才轮到
     `daily`；头两次算「初次」（`meet` 那一档）。计数记在**档上**（纯数据字段，
     不新建容器、不动 texts）：
         `flags["talked"]["<对话树 id>"] = 搭过几次`
     `main` / `hidden` / `idle` **不加新门槛**（need 条件照旧：主线推到才说 · 隐藏条件
     满足才出 —— `_pick_indexed` 的判定一个字没改）。
  ③ **说过的句子让位给还没说过的层**：熟了以后，够层的几层里先挑「还没听过」的那一句
     （`heard` 那套现成容器）。不然 `daily` 的兜底句会把 `main` / `hidden` 永久遮住
     （P-12 的另一半：德里克的雨天句 · 哈根的 hidden）。全会说过了才回到层序上第一层。
     还不熟时**只有 `meet` 那一档会说话**（`daily` 的门没过 · `main` / `hidden` 排在后头）
     —— 主线与底牌要熟了才轮得到。
"""
from __future__ import annotations

import random

from .cmds_ast import (_data, _p, _save, _map_of, _name_of_node, T, _texts, _npcs_here,
                       hp_cap_or_line, npc_gone_lines)
from . import argv as AV
from .cmds_ast import egg_lines, title_lines
from . import calendar as CAL
from . import codex as CX
from . import heard as HD
from . import loot as LT
from . import prog as PROG     # ★ 本波：对话旗标族（`main*_done` 那一族）的唯一判定口


def _arg(env, default=""):
    """从玩家原文取参数（**唯一口** = `content/argv.py`）：`搭话 哈根` → `哈根`。

    ★ B4-10：原先按第一个空白切 ⇒ `装铁剑` 这种「别名与参**连写**」会被取空
      （声明里 `^装\\s*(.+)$` 本来就允许连写）。现在跟着**该指令自己的声明**剥前缀
      （最长命中的那条），连写与带空白两种写法取到同一个参；
      裸指令名（`装备`）取到空串 = 「没带参」（原先会拿第二个字当参）。
    """
    return AV.arg_of(env, default=default)


#: ★★ P1-27（2026-09-29 · 文案车道 P1）：**条件键词表的唯一一份**。
#: 读端认得哪些键，就在这里列全 —— `scripts/probe_dialogues.py` ③ 直接 import 它
#: （原先那份是探针自己抄的常量，两份各写各的，已经漂了：见同提交里的取证）。
#: ★ 一行一个分支，**顺序 = `_pick_indexed` 里判定的顺序**，别当无序集合看。
NEED_KINDS = ("flag", "holding", "time", "weather", "event", "last",
              "quest_done", "hurt", "equipped", "codex")


def _pick_indexed(lines, p, st=None):
    """按 need 条件择优：**按顺序挑第一条满足的**（照奥兰迪亚的精华）。

    ★ 时辰 / 天气是真判断（名 → 时辰或天气，唯一出口 = `calendar`）；判不过就是判不过。
    ★ 返回 `(序号, 台词)`；一条都挑不出就 `(None, None)` —— 序号给「听过哪一句」记账用（B3-2）。
    """
    flags = p.get("flags") or {}
    for i, ln in enumerate(lines or []):
        need = ln.get("need")
        if not need:
            return i, ln.get("text")
        ok = True
        for k, v in need.items():
            if k == "flag":
                # ★ 本波（g3-quests2）：走**真实进度**那一口（`content/prog.flag_ok`）——
                #   改前这里只是 `bool(flags.get(v))`，而 `main04_done` 那一族**全仓没有写端**
                #   ⇒ 域里 12 条台词永久出不来。现在：表里的 slug 以真实进度为准（老档里
                #   进度在、旗标那格当年没写 ⇒ 照样成立；旗标写着而进度不成立 ⇒ 不算满足，
                #   不刷出不该出的台词）；表外的 token（`card` / `lore_scripts` …）走老口径。
                if not PROG.flag_ok(p, v):
                    ok = False
            elif k == "holding":
                if not (p.get("bag") or {}).get(v):
                    ok = False
            elif k == "time" or k == "weather":
                if not CAL.allows(v, st):        # ★ B2-5：真判断（原来是「先当满足」）
                    ok = False
            elif k == "event":
                # ★ B3-5：原先读 `flags["event_<名字>"]` —— 那是**没人写**的一格（读端有、写端没有）
                #   ⇒ 现在走事件层的唯一口（世界级看主线、限时看游戏日窗）
                if not CAL.event_on(v, st, p):
                    ok = False
            elif k == "last":
                ok = bool(flags.get("last_" + str(v)))
            elif k == "quest_done":
                ok = bool(flags.get(v))
            elif k == "hurt":
                # ★ 本波（P1 BUG-7）：**有伤才说那一句** —— 上限只有一个来源（职业面板）。
                #   档上还没择业（建号第二步没走完）⇒ 判不了 = 不算满足（fail-closed：
                #   宁可落到兜底那一句，也不在一个还不知道自己有多少血的档上假定「有伤」）。
                _cap, _line = hp_cap_or_line(p)
                if _cap is None or int(p.get("hp") or _cap) >= int(_cap):
                    ok = False
            elif k == "equipped":
                # ★ 本波（P1 BUG-7）：**那一格上真有东西**才说那一句（`equipped` 的形状 =
                #   `{槽: 件 id}`，槽名是 ASCII 机器键 —— `weapon` / `armor_top` …）。
                #   写这一条是因为柯尔那句「（他看了一眼你的剑）」在空手玩家身上也照说。
                if not (p.get("equipped") or {}).get(str(v)):
                    ok = False
            elif k == "codex":
                # `codex: "<谱>:<条目>"` —— 谱里有了才出这句（B2-7：图鉴与对话接上）
                bk, _, rid = str(v).partition(":")
                if not (bk and rid and CX.has(p, bk, rid)):
                    ok = False
            else:
                # ★★ P1-27（2026-09-29 · 文案车道 P1）：**认不出的键按不满足算**（fail-closed）。
                #   原先这里是 `ok = True` —— 认不出 = **当成满足** ⇒ 一个拼错的键
                #   （`tim` 之于 `time`）会让那一句**无条件地说给所有档听**，
                #   而域里/ schema 里**没有任何一处能拦住它**（schema 不约束 need 的键名，
                #   探针 ③ 词表也只查「域里已用的键」，管不到「拼错的键」）。
                #   那正是「条件句被静默洗成兜底句」的最短路径：条件越严越该更早说，
                #   拼错一次 = 这一句对所有人无条件开放。
                #   取舍：宁可落到兜底那一句（域里每层末位都有 need=null）也不越权放行。
                ok = False
        if ok:
            return i, ln.get("text")
    return None, None


def _pick_line(lines, p, st=None):
    """（老签名保持不变：只要那句话说啥 —— 探针与别处都在用它）"""
    return _pick_indexed(lines, p, st)[1]


# ── ★ P-12（取句顺序）：人先熟、事才说 ────────────────────────────────
#: 层序（口径见模块开头 ①）：初次 → 熟了 → 主线推到 → 隐藏条件满足（`idle` 仍旧排尾）。
LAYERS = ("meet", "daily", "main", "hidden", "idle")

#: 「熟了」的口径（②）：同一个对话树**搭过 ≥ 这么多次话**（这一次也算）才轮到 daily。
FAMILIAR_TALKS = 3


def _layers_ok(layer, familiar) -> bool:
    """这一层这一趟轮不轮得到（★ 只加「熟了才出 daily」这一道门，need 判定不碰）。

    · `meet`  —— 只在**还不熟**时出（初次见面那一档）
    · `daily` —— 只在**熟了**时出
    · `main` / `hidden` / `idle` —— 不加新门槛：主线推到那儿才说 · 隐藏条件满足才出
    """
    if layer == "meet":
        return not familiar
    if layer == "daily":
        return familiar
    return True


def _talk_count(p, dlg_id) -> int:
    """这位（这棵树）搭过几次话 —— 档上的计数（没记过 = 0）。"""
    t = (p.get("flags") or {}).get("talked")
    if not isinstance(t, dict):
        return 0
    try:
        return int(t.get(str(dlg_id)) or 0)
    except (TypeError, ValueError):
        return 0


def _note_talk(p, dlg_id) -> None:
    """这一趟搭话记上一笔（数你搭了几次，不看他答没答）。

    ★ 换新对象写：`_p` 只把 flags 拷一层，直接改里头的 dict 会把别人那份 flags
      一起改脏（B3-12 · K57 同族 —— 默认档不许被就地改）。
    """
    flags = p.get("flags")
    if not isinstance(flags, dict):
        flags = {}
        p["flags"] = flags
    t = dict(flags.get("talked") or {})
    t[str(dlg_id)] = _talk_count(p, dlg_id) + 1
    flags["talked"] = t


def _pick_layer(nodes, p, st, dlg_id):
    """挑这一趟说**哪一层、哪一句** → `(层, 序号, 台词)`；一句都说不出就 `(None, None, None)`。

    ★ P-12：**人先熟、事才说** —— 层序走 `LAYERS`（meet → daily → main → hidden → idle），
      `meet` 只在还不熟时算数、`daily` 只要熟了算数（模块开头 ②）。
      ⇒ **还不熟时只有 `meet` 那一档会说话**（`daily` 的门没过 · `main` / `hidden` 排在后面
      且前面有兜底句）：主线与底牌要**熟了**才轮得到 —— 这就是「人先熟、事才说」。
    ★ 每层**内部**仍是老口径：`_pick_indexed` 按 need 条件取第一条满足的（一个字没改）。
    ★ 熟了以后：够层的几层里**先挑还没听过的那一句**（`heard` 现成容器）—— 说过的兜底句
      不该把 `main` / `hidden` 永久遮住（P-12 的另一半：德里克的雨天句 · 哈根的 hidden）；
      全会说过了才回到层序上第一层（说的还是老那一句）。
    """
    familiar = _talk_count(p, dlg_id) >= FAMILIAR_TALKS
    heard = set(HD.lines(p, dlg_id))
    # ── ① 层间选层：**P-12 老口径，一字未改** ────────────────────────────────
    #    层序 / 熟了才轮到 daily / 每层只取 `_pick_indexed` 的头一条 /
    #    说过的层让位给没说的层 —— 全部照旧（装备事件那句与支线旗标都靠它送达）。
    cands = []                                     # 够层的那几层，按层序
    for layer in LAYERS:
        if layer not in nodes or not _layers_ok(layer, familiar):
            continue
        idx, txt = _pick_indexed(nodes[layer].get("texts"), p, st)
        if txt:
            cands.append((layer, idx, txt))
    if not cands:
        return None, None, None
    # ★ P1-7（2026-09-28）：去重**不再只对熟了的人生效**。
    #   原先整段挂在 `if familiar:` 下面 ⇒ 「还不熟」时（只有 meet 会说话）
    #   每次都返回同一句，玩家连敲两下看到一模一样的回话。
    #   规格 25_ §一②「重复对话要轮换」管的正是这一段。
    #   ★ 数据本来就在：`HD.note` 每趟都记（不论熟不熟），只是读端被门挡住了。
    _layer, _idx, _txt = cands[0]
    for _l, _i, _t in cands:
        if "%s#%s" % (_l, _i) not in heard:
            _layer, _idx, _txt = _l, _i, _t        # 还没听过的那一层先说
            break
    # ── ② 层内轮换（P1-16 · 2026-09-29 · 文案车道）────────────────────────────
    #   只有**老口径挑中的那句玩家已经听过了**，才在这一层里另找一句顶上。
    #   ★ 为什么必须挂在「说过之后」：① 每层只取头一条 ⇒ 层一旦选定，句也就定死了；
    #     同一个世界状态（时辰 / 天气 / 进度都不变）下连敲「搭话」，同一句反复出。
    #     端到端实测（`e2e_drive.py "搭话 杜林" ×5`）：第 3/4/5 趟**逐字相同** ——
    #     这正是鱼鱼说的「观感不好」（规格 25_ §一②「重复对话要轮换」）。
    #   ★ ★ 三轮踩坑（都撞了别线已验收的真判据，教训留在这里）：
    #     ① 「每层各挑一句再让层比」⇒ daily 有 4 句就永远让不完，hidden 饿死
    #        （`probe_equip_events`：「带着那件 ⇒ 4 遍内必拿到那句」红）。
    #     ② 「层选定后无条件层内换句」⇒ meet 换句后头一条还没听过，整个 meet 舍不得走，
    #        4 遍全耗在 meet/daily，hidden 还是排不上（同一份契约，第二次红）。
    #     ③ 「让位单位改成整层听完」⇒ 改坏了 P-12 语义（听过 `daily#0` 应当**换层**），
    #        `probe_dialogues ⑧` 立刻红 —— 那是台账 P-12 亲自定的口径，不能动。
    #     ⇒ 终版：**让位仍旧只看老口径那一格**（`heard` 记的就是它），
    #        层内换句只顶「这一趟说哪句」，**不碰**让位计数。
    if "%s#%s" % (_layer, _idx) in heard:
        for _i2, _ln2 in enumerate(nodes[_layer].get("texts") or []):
            if _i2 == _idx or "%s#%s" % (_layer, _i2) in heard:
                continue
            if _pick_indexed([_ln2], p, st)[1] is None:
                continue                          # 这句此刻出不来（need 不满足）
            _idx, _txt = _i2, _ln2.get("text")
            break
        else:
            # ── ③ 层内换句**够不着**时的一格兜底（P1-19 · 2026-09-29 · 文案车道）─────
            #   ★ 原状是「这一层找不到顶替 ⇒ 老那一句原样说出去」，而**别的层里
            #     还躺着没说过的句子** —— 实测 talk 5 的玛莎：`daily` 一句不剩，
            #     而 `hidden` 里有 3 句既没听过、此刻也出得来，永远排不上
            #     （要让位得先让**老口径**挑中它们那一层，而老口径总挑 `daily` 的头一条）。
            #     屏上的症状：第 5/6/7/8 趟**逐字相同** —— 种类数合格（⑰ 绿），
            #     排布是坏的（⑲ 红）。这就是鱼鱼说的「观感不好」。
            #   ★ 只动**这一格兜底**：层序仍是 `LAYERS`、让位单位仍是老口径那一格、
            #     `heard` 记的仍是老口径那一格（⑧ 的 P-12 语义一个字没动）——
            #     本条只在「老口径那一句玩家已经听过了」之后改变**这一趟说哪句**。
            #   ★ 扫的是**够层**的那些层（`_layers_ok` 那道门照旧）⇒
            #     「不熟时只有 meet 会说话」不被破：meet 在这里仍被门挡住。
            #   ★ 层序用 `LAYERS` 变量（不是字面量）—— ⑯-a 的静态守卫就认这一格。
            for _l3 in LAYERS:
                if _l3 not in nodes or not _layers_ok(_l3, familiar):
                    continue
                for _i3, _ln3 in enumerate(nodes[_l3].get("texts") or []):
                    if "%s#%s" % (_l3, _i3) in heard:
                        continue
                    if _pick_indexed([_ln3], p, st)[1] is None:
                        continue                  # 这句此刻出不来（need 不满足）
                    return _l3, _i3, _ln3.get("text")
            # ── ④ ★ P1-26（2026-09-29 · 文案车道）：全都说过了 —— **在这一层里轮换** ──
            #   走到这一格 = 「老口径那一句听过」+「整棵树里没有一句是没听过且此刻出得来的」。
            #   原状：把老那一句**原样说出去** ⇒ 玩家从第 9~11 趟起（中期存档实测）到第 80 趟
            #   看到的永远是同一句。14 位 NPC **无一例外**。
            #   ★ 为什么既有 21 条判据全绿也看不见它：⑰ / ⑲ / ⑳ 量的是「**没听过时**能轮几句」
            #     且只连敲 8 下 —— 8 句之内用不完一个池子 ⇒ 结构性地测不到「全听过之后」这一档。
            #   ★ 只动这一格：**层的选择一个字没改**（仍是 `_layers_ok` 过的层序第一档），
            #     `heard` 记的仍是这一趟真说出去的那句，P-12 语义（⑧）不动。
            #   ★ 轮换口径用 `_talk_count`（搭话次数，含这一趟）—— 那是**档上现成的纯数据**，
            #     不新建容器、不改存档形状；`⑧` 的假树每层各 1 句 ⇒ 可用集合只有 1 个 ⇒ 原样返回。
            _avail = [_i4 for _i4, _ln4 in enumerate(nodes[_layer].get("texts") or [])
                      if _pick_indexed([_ln4], p, st)[1] is not None]
            if len(_avail) > 1:
                _i4 = _avail[_talk_count(p, dlg_id) % len(_avail)]
                return _layer, _i4, (nodes[_layer]["texts"][_i4] or {}).get("text")
            # 一句都找不到 ⇒ 真的没得说了，重复是诚实的（照旧把老那一句说出去）
    return _layer, _idx, _txt


# ══════════════════════════════════════════════════════════════
# ★ 未鉴定容器：拿给「识货的人」看 ⇒ 当场开出来（B2-3 留的最后一格）
# ══════════════════════════════════════════════════════════════
# 为什么路口就落在**现成的『搭话』**上（不另造动词）—— 真源写得最直：
#   · `27_掉落的惊喜感与未鉴定_v1.md §3.3`「拿给谁看（★ 这一步本身就是玩法）」：
#     杜林认锻造物 · 柯尔只认铁 · 艾德认教会的器物与文字 · 莉安认铭文；认不出来也有味道；
#   · `27 §3.5`「你把那块东西放在柜台上。杜林拿起来……」⇒ 一块看不出用途的旧东西 → 刻字的石片；
#   · `06_装备获取与支线玩法_v1.md §1.1`：「捡到不认得的东西 → 拿给修士/铁匠/莉安看 → 认出来」。
# ★ 接线之前：`loot.open_unid` / `loot.help_text_of` 全仓**没有调用端** ⇒ 那几件东西
#   （骨田挖的 / 浅滩捞的 / 塔里搜的）永远开不出来。**这里就是那两个口的唯一调用端。**
def _unid_held(p) -> list:
    """手上的**未鉴定容器**（域里 `kind_key` = `unidentified` 的那几条）—— id 升序（稳定序）。"""
    out = []
    for iid, n in sorted((p.get("bag") or {}).items()):
        try:
            if int(n or 0) <= 0:
                continue
        except (TypeError, ValueError):
            continue
        if (LT.pools().get(str(iid)) or {}).get("kind_key") == "unidentified":
            out.append(str(iid))
    return out


def _unid_seed(uid, day, unid_id, left) -> str:
    """鉴定抽签的种子 —— ★ 与采集（P-26）/ 逃跑（B3-11）同一条纪律：**一律稳定标识拼**，
    不许 `random.random()` 那种不可复现的口。

    种子 = 人 · 游戏日 · 容器 · **手上还剩几件**（`left` 就是「这是这一类的第几件」——
    手里两件连着开，第 1 件与第 2 件各抽各的；开掉一件就少一件，所以**同一件开两遍不是一个结果**
    的漏洞不存在）。游戏日走 `codex.today()`（日期戳那一口），不自己拼时间。
    """
    return "aetheran:unid:v1:%s:%s:%s:%d" % (str(uid), CAL.day_key(int(day)),
                                             str(unid_id), int(left))


async def _identify_lines(p, npc_id, who, uid, player, env, just=()):
    """他在场 ⇒ 手上那几件未鉴定的，他认得出的**当场开出来**（开出真东西 · 容器消失）。

    逐件（id 升序）：
      ① 他认不认得这一门 ⇒ `loot.help_text_of()` 给那一句（认得 / 看不出 / 她没说话）。
         ★ F6 同族（同一件事别贴两遍）：他要是**这一趟刚在旧物谱那一支里**说过这句
           （这一位在这一件的「认得出」名单里 · 且这一件**就是这一趟**在谱里认出来的 —— `just`），
           这里就不再重复；下一趟谱里已经认出来了、旧物谱那一支不再说话，这一句就重新由这里出。
      ② 他在**鉴定名单**里（`loot.appraisers_of` ← 域里的 `identify_by`）⇒ 抽一件出来：
         池子 = 域里现成那一份（`loot.open_unid`，本支不另写池）；抽签种子见 `_unid_seed`。
         开得出来 ⇒ 容器少一件、开出来的**真进背包**（+ 该进谱的进谱）、旧物谱那一条**问号换真名**；
         开不出来 ⇒ **什么都不动**（fail-closed：不吞容器、也不编一件出来）。
      ③ 他不在名单里 ⇒ 只说①那一句，东西照旧留在手上（「认不出来也有味道」）。

    一次搭话**每件容器只开一件**（手上两件 = 说两句、开两件要搭两次话）—— 他一次只看一件。
    """
    from .cmds_codex import new_lines            # 本地 import：免得包装载期成环（cmds_codex 引本模块）
    just = {str(x) for x in (just or ())}
    for uid_id in _unid_held(p):
        asks = tuple(str(x) for x in ((CX.entry("relic", uid_id) or {}).get("ask") or []))
        line = LT.help_text_of(uid_id, npc_id)
        if line and not (npc_id in asks and uid_id in just):
            yield line
        if npc_id not in LT.appraisers_of(uid_id):
            continue                             # 认不出 ⇒ 只说了那一句，东西照旧留着
        bag = dict(p.get("bag") or {})
        try:
            left = int(bag.get(uid_id) or 0)
        except (TypeError, ValueError):
            left = 0
        if left <= 0:
            continue
        # ★ 审计 L1122：把**玩家自己的等级**交给 `open_unid`（`gated=True` 吃那把按等级的刀）。
        #   缺省是 `level=1 / gated=False` ⇒ 不传就等于「永远按 1 级抽」＝白捡穿不上的档。
        got = LT.open_unid(uid_id, level=int(p.get("level") or 1), gated=True,
                           rnd=random.Random(_unid_seed(uid, CX.today(p), uid_id, left)))
        if not got:
            continue                             # ★ fail-closed
        if left > 1:
            bag[uid_id] = left - 1
        else:
            bag.pop(uid_id, None)
        p["bag"] = bag
        LT.add_to_bag(p, [got])                  # 开出来的真进背包（顺带记 loot 那个「第一次见到」平表）
        new = CX.note_items(p, [got["id"]])      # 该进谱的进谱（材料谱 / 风味谱 / 旧物谱）
        CX.reveal(p, uid_id)                     # ★ 旧物谱那一条：问号换真名（不可逆 · 幂等）
        if player is not None:
            player.update(p)
        _save(env)
        yield T("SYS_UNID_OPENED", who=who)
        item = LT.rec_of(got["id"])
        yield T("SYS_GATHER_GET", icon=item.get("icon", "·"),
                name=item.get("name", got["id"]), n=got.get("n", 1))
        if got.get("story"):
            yield T("SYS_UNID_STORY", story=got["story"])
        for row in new_lines(new):
            yield row


async def talk(env, sink, uid, player):
    p = _p(player)
    st = CAL.state()                       # 现在几时、什么天气（一次，全用它）
    here = _npcs_here(p["loc"], p["node"], st, p)          # ★ B3-5：世界级事件看主线进度（同一个口）
    if not here:
        # ★ g4-⑨（31_NPC作息 §四）：这一站的人按作息还没来 ⇒ 不只是一句「这儿没有别人」，
        #   逐位说清「这个点他不在 + 他什么时候在」（与观察那一支同一处 · `npc_gone_lines`）。
        _gone = npc_gone_lines(p["loc"], p["node"], p, st)
        for _g in _gone:
            yield _g
        if not _gone:
            yield T("SYS_TALK_NOBODY")
        return
    want = _arg(env)
    if not want:
        yield T("SYS_TALK_HERE", list=" · ".join("『%s』" % v.get("name") for _, v in here))
        # ★ 本波（P1 体验-6）：这一站不止一个人时，原先只举**第一个**名字当例子 ——
        #   玩家以为只有他。两个人以上就把名字**都**写进教法那一句。
        if len(here) > 1:
            yield T("SYS_TALK_HOW_MANY",
                    list=" · ".join("『%s』" % v.get("name") for _, v in here))
        else:
            yield T("SYS_TALK_HOW", name=here[0][1].get("name"))
        return
    hit = None
    for k, v in here:
        if want == v.get("name") or want in (v.get("name") or ""):
            hit = (k, v)
            break
    if not hit:
        yield T("SYS_TALK_NOSUCH", name=want)
        yield T("SYS_TALK_HERE", list=" · ".join("『%s』" % v.get("name") for _, v in here))
        return
    k, npc = hit
    dlg = _data("dialogues").get(npc.get("dialogue") or "")
    yield "%s %s" % (npc.get("icon", "💬"), npc.get("name"))
    if not dlg:
        yield npc.get("desc") or T("SYS_TALK_NO_LINES")
        return
    nodes = dlg.get("nodes") or {}
    dlg_id = npc.get("dialogue") or ""
    # ★ P-12：这一趟就算「搭过一次话」（熟了才出 daily 靠这个计数 —— 头两次算初次）
    _note_talk(p, dlg_id)
    spoke = False
    # ★ P-12 节点择优：层序 = meet（初次）→ daily（熟了）→ main（主线推到）→ hidden（隐藏条件满足）
    layer, idx, txt = _pick_layer(nodes, p, st, dlg_id)
    if txt:
        for line in str(txt).split("\n"):
            yield line
        spoke = True
        # ★ B3-2：听过哪一句记下来（称号「听完哈根的全部对话」靠它）
        HD.note(p, dlg_id, layer, idx)
    if not spoke:
        yield T("SYS_TALK_SILENT")
    # ★ 落档：这一趟的计数总在动 ⇒ 每趟都落（原先只在「新听一句」时才落）
    if player is not None:
        player.update(p)
        _save(env)
    # ★ B2-7：他要是认得你谱里那些还留着问号的旧东西 —— 名字当场说出来
    just = set()                               # 这一趟**真**在谱里认出来的那几条（F6：同一句别贴两遍）
    if spoke:
        first = True
        for rid in CX.revealable(p, k):
            if CX.reveal(p, rid):
                just.add(str(rid))
                if player is not None:
                    player.update(p)
                _save(env)
                if first:                       # 那句话一次对话只说一遍
                    yield T("SYS_CODEX_ASK", who=npc.get("name"))
                    first = False
                yield T("SYS_CODEX_REVEAL", name=CX.name_of("relic", rid))
                yield T("SYS_CODEX_RELIC_KNOWN", name=CX.name_of("relic", rid),
                        known=CX.line_of("relic", rid, "known"))
    # ★ 未鉴定容器（本件接的那一格）：他在场 ⇒ 手上那几件他认得出的**当场开出来**
    #   （27 §3.3「拿给谁看」· 唯一调用端见 `_identify_lines`）
    async for line in _identify_lines(p, k, npc.get("name"), uid, player, env, just=just):
        yield line
    for line in egg_lines(p, player, env):      # ★ B3-1：人 + 东西，可能就在这一下连起来
        yield line
    for line in title_lines(p, player, env):    # ★ B3-2：话说完，名字可能就挂上来了
        yield line


async def ask_way(env, sink, uid, player):
    p = _p(player)
    here = _npcs_here(p["loc"], p["node"], p=p)            # ★ B3-5：同上（原先两处口径不一样）
    if not here:
        yield T("SYS_ASK_NOBODY")
        return
    nb = []
    m = _map_of(p["loc"]) or {}
    for n in m.get("nodes") or []:
        if n.get("id") != p["node"]:
            nb.append(n.get("name"))
    yield T("SYS_ASK_HEAD")
    yield T("SYS_ASK_ANSWER", who=here[0][1].get("name"),
            list=" · ".join("『%s』" % x for x in nb[:3]) if nb else T("SYS_ASK_ONLY_WAY"))
    # ★ 夜班试玩 w3 p1：原先只报 3 处、也不说按什么挑的（镇上一共 10 处）—— 读起来像「路全在这儿」。
    #   三处的取舍（近的三处）与屏宽都不动，只把**这件事说清**并指到看全部的那条指令（不新增遍历口）。
    if len(nb) > 3:
        yield T("SYS_ASK_MORE", n=len(nb))
