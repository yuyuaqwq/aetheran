# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 第二组（对话 / 战斗外的交互）

★ P-12（取句顺序）．**人先熟、事才说** —— 这一档的口径全在本文件里，两处：
  ① **层序**（`LAYERS`）：`meet`（初次）→ `daily`（熟了）→ `main`（主线推到）
     → `hidden`（隐藏条件满足）→ `idle`。
     原先是 `main → hidden → meet → daily` ⇒ 刚认识一个人，对方开口就说主线（剧透），
     底牌（彩蛋那一层）也一见面就漏；哈根的 hidden 兜底句还把 meet / daily 永久遮住
     （P-12 记：德里克的雨天那句只有直调 `_pick_line` 时出得来）。
     每棵树的 `start` 字段都写着 `"meet"` —— 排头就是它，那条「start 没人读」也对上了。
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

from .cmds_ast import _data, _p, _save, _map_of, _name_of_node, T, _texts, _npcs_here
from .cmds_ast import egg_lines, title_lines
from . import calendar as CAL
from . import codex as CX
from . import heard as HD


def _arg(env, default=""):
    """从玩家原文取参数：`搭话 哈根` → `哈根`。"""
    t = (getattr(env, "text", "") or "").strip()
    parts = t.split(None, 1)
    return parts[1].strip() if len(parts) > 1 else default


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
                if not flags.get(v):
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
            elif k == "codex":
                # `codex: "<谱>:<条目>"` —— 谱里有了才出这句（B2-7：图鉴与对话接上）
                bk, _, rid = str(v).partition(":")
                if not (bk and rid and CX.has(p, bk, rid)):
                    ok = False
            else:
                ok = True
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
    cands = []                                     # 够层的那几层，按层序
    for layer in LAYERS:
        if layer not in nodes or not _layers_ok(layer, familiar):
            continue
        idx, txt = _pick_indexed(nodes[layer].get("texts"), p, st)
        if txt:
            cands.append((layer, idx, txt))
    if not cands:
        return None, None, None
    if familiar:
        for layer, idx, txt in cands:
            if "%s#%s" % (layer, idx) not in heard:
                return layer, idx, txt             # 还没听过的那一层先说
    return cands[0]                                # 层序上第一层（初次那一档也走这儿）


async def talk(env, sink, uid, player):
    p = _p(player)
    st = CAL.state()                       # 现在几时、什么天气（一次，全用它）
    here = _npcs_here(p["loc"], p["node"], st, p)          # ★ B3-5：世界级事件看主线进度（同一个口）
    if not here:
        yield T("SYS_TALK_NOBODY")
        return
    want = _arg(env)
    if not want:
        yield T("SYS_TALK_HERE", list=" · ".join("『%s』" % v.get("name") for _, v in here))
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
    if spoke:
        first = True
        for rid in CX.revealable(p, k):
            if CX.reveal(p, rid):
                if player is not None:
                    player.update(p)
                _save(env)
                if first:                       # 那句话一次对话只说一遍
                    yield T("SYS_CODEX_ASK", who=npc.get("name"))
                    first = False
                yield T("SYS_CODEX_REVEAL", name=CX.name_of("relic", rid))
                yield T("SYS_CODEX_RELIC_KNOWN", name=CX.name_of("relic", rid),
                        known=CX.line_of("relic", rid, "known"))
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
