# -*- coding: utf-8 -*-
"""探针：镇内「在场感」那一批（★ 试玩 QA 修 · 2026-09-26）

四个「真人玩家」独立撞上的同一族毛病 —— **屏幕上的画面 / 名册 / 指令三处口径不一样**：

  ① 东西口复述北口的画面（P1 BUG-4 · P3 · P4 BUG-1）—— 三处镇口原先共用**地图级**那屏
     （写着「风车在镇子北口」+ 镇口那块石头）⇒ 站在东口读到的第一句是北口。
  ② 「观察」里明写有人在、「搭话」却回「这儿没有别人」（P1 BUG-5）—— 节点场景是**静态文本**，
     可这一站的人有作息 / 会被集日吸走 ⇒ 画面与名册打架。本波补「人不在那一版」场景
     （`SCENE_<节点>_EMPTY`；判据 = `content/town.py::station_empty`，口径 31_NPC作息 §四）。
  ③ 「触摸」只把「看得见」栏那条**锁定说明**当结果吐出来（P1 BUG-6）—— 一样都上不了手时，
     屏幕上没有「这里没有什么可以上手的」。
  ④ 三处隐藏点「触摸」是空壳（P2 BUG②）+ 三处篝火漏出占位文案（P2 BUG③）。
  ⑤ NPC 对白不看状态：柯尔评价刃口、艾德说「伤口我看看」（P1 BUG-7）—— 空手满血的档也照说。
  ⑥ 小事四件：锁定提示的主语（体验-10）· 怪物那一栏的表头（体验-11）· 搭话多人只举一个名字
     （体验-6）· 苦叶摊不卖苦叶（体验-14）。

★ 每条的判据都是**两态**（正例 + 反证）：反证 = 同一段代码换一份数据/状态/日子就该翻面 ——
  拆掉修复它当场红。反证不是注释：这里的「反证」都是**真跑**出来的（合成记录 / 摘掉那一格 /
  换时辰 / 换站 / 换日子）。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_onsite.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402

ok = True
DB = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_onsite.db")


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


print("探针：镇内「在场感」那一批")
st = load_stack(str(REPO), inject={"db_path": DB, "clock": lambda: 0.0})
st.install()
tx = st.domain("texts") or {}
po = st.domain("pois") or {}
dl = st.domain("dialogues") or {}
np_ = st.domain("npcs") or {}
mp = st.domain("maps") or {}
qs = st.domain("quests") or {}
ev = st.domain("events") or {}
mo = st.domain("monsters") or {}
chk("域都读得到（texts / pois / dialogues / npcs / maps / events）",
    bool(tx and po and dl and np_ and mp and ev))

from content import facade                                          # noqa: E402
from content import cmds_ast as CA                                   # noqa: E402
from content import cmds_places as CP                                # noqa: E402
from content import cmds_talk as CT                                  # noqa: E402
from content import calendar as CAL                                  # noqa: E402
from content import town as TW                                       # noqa: E402
from content import affix as AFFIX                                   # noqa: E402
from content.scene import resolve as SC_resolve, node_key as SC_nk, empty_key as SC_ek  # noqa: E402

TOWN = "windmill_town"


def V(slot, **slots):
    """槽位的**渲染值**（逐字从 texts 取 —— 探针里不抄一遍中文）。"""
    return CA.T(slot, **slots)


def parts(slot):
    """槽位模板按 `{占位}` 切头尾 —— 判「这一句是那个槽位渲染的」用（不手抄整句）。"""
    val = str((tx.get(slot) or {}).get("value") or "")
    head, _, tail = val.partition("{")
    _ph, _, tail = tail.partition("}")
    return head, tail


class _E(object):
    """`观察` / `触摸` 只要 env.save()（落档是处理器的责任）与 env.text（按名字挑）。"""

    def __init__(self, text=""):
        self.text = text

    def save(self):
        pass


def run(fn, p, text=""):
    out = []

    async def _go():
        async for line in fn(_E(text), None, "u_onsite", p):
            out.append(str(line))

    asyncio.run(_go())
    return out


def clock_at(day, hod):
    """第 day 个游戏日的 hod 点 —— 刻度从 calendar 域现读（不手打 7200）。"""
    return (day * 86400.0 + hod * 3600.0) * int(CAL.scale_seconds()) / 86400.0


def set_clock(day, hod):
    e = clock_at(day, hod)
    facade.bind_host(clock=lambda: e)
    return e


def at_epoch(e):
    facade.bind_host(clock=lambda: e)
    return e


def player(**kw):
    p = dict(CA.DEFAULT_PLAYER)
    p.update({"race": "human", "cls": "cls_knight", "name": "试玩",
              "loc": TOWN, "node": "wt_gate_n"})
    p.update(kw)
    return p


def scene_of(node):
    return str((tx.get(SC_nk(node)) or {}).get("value") or "")


def empty_of(node):
    return str((tx.get(SC_ek(node)) or {}).get("value") or "")


# ══════════════════════════════════════════════════════════════
# ① 三处镇口各有自己的画面（P1 BUG-4 · P3 · P4 BUG-1）
# ══════════════════════════════════════════════════════════════
print("① 三处镇口各有自己的画面（原先共用地图级那屏 ⇒ 东/西口读到「风车在镇子北口」）")
set_clock(100, 12.0)
_mscene = str((tx.get("SCENE_WINDMILL_TOWN") or {}).get("value") or "")
_g_bad = []
for _nd in ("wt_gate_e", "wt_gate_w", "wt_gate_n"):
    _out = run(CA.look, player(loc=TOWN, node=_nd))
    _want = scene_of(_nd) or _mscene          # 北口仍旧退地图级那屏（进镇第一眼）
    if not _out or _out[0] != _want:
        _g_bad.append("%s 第一行 %r" % (_nd, (_out or [""])[0][:20]))
chk("★ 观察 在三个镇口各自吐**这一站**的画面", not _g_bad, "；".join(_g_bad))
_e, _w, _n = scene_of("wt_gate_e"), scene_of("wt_gate_w"), scene_of("wt_gate_n") or _mscene
chk("★ 东口 / 西口各有自己的节点级槽位，且画面里**不许**再出现「北口」「石头」"
    "（那两句是北口的近景 —— 位置与画面打架）",
    bool(_e) and bool(_w) and "北口" not in _e and "石头" not in _e
    and "北口" not in _w and "石头" not in _w and len(_e) >= 80 and len(_w) >= 80,
    "东口含北口=%s 西口含北口=%s" % ("北口" in _e, "北口" in _w))
chk("★ 北口仍走地图级那屏（进镇第一眼 —— 一个字不动）", _n == _mscene and "北口" in _n)
# 反证：摘掉那两条槽位 ⇒ 解析退回**地图级**那一屏，而那屏逐字含「北口」/「石头」
_tmp = {k: v for k, v in tx.items() if k not in (SC_nk("wt_gate_e"), SC_nk("wt_gate_w"))}
_rev = [(nd, SC_resolve(_tmp, TOWN, nd)) for nd in ("wt_gate_e", "wt_gate_w")]
chk("★ 反证（拆掉修复）：摘掉那两个槽位 ⇒ 退回地图级 `SCENE_WINDMILL_TOWN`（逐字含「北口」）"
    "—— 上面那条当场红",
    all(k == "SCENE_WINDMILL_TOWN" for _nd, k in _rev)
    and "北口" in _mscene and "石头" in _mscene, "%s" % _rev)

# ══════════════════════════════════════════════════════════════
# ② 「这一站的人都不在」⇒ 走人不在那一版场景（P1 BUG-5）
# ══════════════════════════════════════════════════════════════
print("")
print("② 画面里写的人此刻不在 ⇒ 不许再在画面上写「有人在旁边坐着」（P1 BUG-5）")


def crowd_eid():
    """会**聚人**（`effects.crowd`）的那条事件 id —— 从域里现取（不手打「集日」这个名字）。"""
    for k, v in sorted(ev.items()):
        if isinstance(v, dict) and (v.get("effects") or {}).get("crowd"):
            return k
    return ""


def day_with(want_on, start=100, span=40):
    """那条聚人事件**开着 / 关着**的各挑一天 —— 现算 `CAL.event_on`（不手打「7 天一次」）。"""
    eid = crowd_eid()
    for d in range(start, start + span):
        at_epoch(clock_at(d, 12.0))
        if bool(CAL.event_on(eid, CAL.state(), player())) == want_on:
            return d, eid
    return None, eid


D_MARKET, _MKT_EID = day_with(True)
D_PLAIN, _ = day_with(False)
chk("两个日子都挑得出来（聚人事件 `%s`：开着 = 第 %s 天 / 关着 = 第 %s 天 · 现算）"
    % (_MKT_EID, D_MARKET, D_PLAIN),
    bool(crowd_eid()) and D_MARKET is not None and D_PLAIN is not None and D_MARKET != D_PLAIN)

# ②-a 哈根（作息 = 昏/夜）：昼 ⇒ 空版；夜 ⇒ 原版 + 名册里有人
set_clock(D_PLAIN, 12.0)
_look_day = run(CA.look, player(loc=TOWN, node="wt_wall"))
_talk_day = run(CT.talk, player(loc=TOWN, node="wt_wall"))
set_clock(D_PLAIN, 21.0)
_look_night = run(CA.look, player(loc=TOWN, node="wt_wall"))
_talk_night = run(CT.talk, player(loc=TOWN, node="wt_wall"))
set_clock(D_PLAIN, 12.0)
chk("★ 北墙根：昼（人不在）⇒ 第一行是 `%s`；夜（人在）⇒ 第一行回到 `%s`"
    % (SC_ek("wt_wall"), SC_nk("wt_wall")),
    _look_day[:1] == [empty_of("wt_wall")] and _look_night[:1] == [scene_of("wt_wall")],
    "昼=%r 夜=%r" % (_look_day[:1], _look_night[:1]))
chk("★ 画面与名册**同源**：昼那句里不许出现「有人在旁边坐着」、『搭话』回「这儿没有别人」；"
    "夜里画面照旧写他坐着、『搭话』认得他",
    "有人在旁边坐着" not in _look_day[0] and V("SYS_TALK_NOBODY") in _talk_day
    and "有人在旁边坐着" in _look_night[0] and "『哈根』" in "\n".join(_talk_night),
    "昼搭话=%s ／ 夜搭话=%s" % (_talk_day[:1], _talk_night[:2]))
chk("★ 空版那一句自己把话说清（他不在 + 他什么时候来）：%s" % empty_of("wt_wall")[-18:],
    "不在" in empty_of("wt_wall") and "天黑" in empty_of("wt_wall"))
# ②-b 老陶（集日被 `effects.crowd` 吸去挂板墙）：集日 ⇒ 空版；平日 ⇒ 原版
set_clock(D_MARKET, 12.0)
_sh_m = run(CA.look, player(loc=TOWN, node="wt_shed"))
_wall_m = run(CA.look, player(loc=TOWN, node="wt_board"))
set_clock(D_PLAIN, 12.0)
_sh_p = run(CA.look, player(loc=TOWN, node="wt_shed"))
chk("★ 歇脚棚：集日（老陶被吸走）⇒ 走 `%s`；平日 ⇒ 回到 `%s`（同一段代码 · 换日子翻面）"
    % (SC_ek("wt_shed"), SC_nk("wt_shed")),
    _sh_m[:1] == [empty_of("wt_shed")] and _sh_p[:1] == [scene_of("wt_shed")]
    and "一个老头在里面" not in _sh_m[0] and "一个老头在里面" in _sh_p[0],
    "集日=%r" % (_sh_m[:1],))
chk("★ 被吸走那位在**吸到的那一站**真出现（两头都动：这边空版、那边名册里有他）",
    "『老陶』" in "\n".join(_wall_m), "%s" % _wall_m[3:5])
# 反证①：绕开这一支（`empty=False`）⇒ 白天照样吐写着人的那句
set_clock(D_PLAIN, 12.0)
_bypass = CA._scene_line(TOWN, "wt_wall", CA._map_of(TOWN))
chk("★ 反证（拆掉修复）：不走这一支（`empty=False`）⇒ 白天的第一行回到写着人的那句"
    "（%s）" % _bypass.split(chr(10))[-1],
    _bypass == scene_of("wt_wall") and "有人在旁边坐着" in _bypass)
# 反证②：判法不是常量 —— 有人在的站 False，没人的站 True；且**没有空版槽位也照样出话**
chk("★ 反证②：`station_empty` 不是常量（白烛堂/艾德 = %s · 北墙根白天 = %s）；"
    "野外节点（骨田）没有空版槽位也照样吐原版（不静默给空）"
    % (TW.station_empty(TOWN, "wt_chapel", player()), TW.station_empty(TOWN, "wt_wall", player())),
    TW.station_empty(TOWN, "wt_chapel", player()) is False
    and TW.station_empty(TOWN, "wt_wall", player()) is True
    and CA._scene_line("belt_north", "bn_bone", None, empty=True) == scene_of("bn_bone"))

# ══════════════════════════════════════════════════════════════
# ③ 上手这一站一样都上不了手 ⇒ 明说（P1 BUG-6）
# ══════════════════════════════════════════════════════════════
print("")
print("③ 触摸：门槛全挡着的那一站，不许把「看得见」栏的锁定说明当结果（P1 BUG-6）")
_gated = next((k for k, v in sorted(po.items()) if (v.get("condition") or {}).get("quest")), "")
_qid = str((po.get(_gated) or {}).get("condition", {}).get("quest") or "")
_gname = str(po[_gated]["name"])
_ln, _nd = str(po[_gated]["map"]), str(po[_gated]["subarea"])
_lock = CA.T("SYS_POI_NOT_YET", name=CA._poi_label(po[_gated]),
             why=CA.T("SYS_POI_WHY_QUEST",
                      token=str((qs.get(_qid) or {}).get("name") or _qid)))
_no = run(CA.touch, player(loc=_ln, node=_nd))
_yes = run(CA.touch, player(loc=_ln, node=_nd, flags={"quests_done": [_qid]}))
_get_gated = V("SYS_TOUCH_GET", icon=po[_gated]["icon"], name=_gname)
chk("★ 门槛没过（%s · %s）：出点名行「%s」**并且**补一句「%s」—— 不再只剩一条锁定说明"
    % (_gname, _nd, _lock, V("SYS_TOUCH_NONE")),
    _lock in _no and V("SYS_TOUCH_NONE") in _no and _get_gated not in _no, "%s" % _no)
chk("★ 补上那笔账（`%s` 交过）⇒ **同一站**真摸得到：出「你摸到…」且**没有**那一句兜底"
    "（两态 = 同一段代码 · 换档就翻面）" % _qid,
    _get_gated in _yes and V("SYS_TOUCH_NONE") not in _yes, "%s" % _yes[:2])
_wide = run(CA.touch, player(loc="belt_north", node="bn_bone"))
chk("★ 反证：有东西摸得到的站（骨田 · 半埋的碑）**不许**出现那一句兜底 —— "
    "判据不是「总是说没有」",
    V("SYS_TOUCH_NONE") not in _wide
    and any(V("SYS_TOUCH_GET", icon="", name="").rstrip("。") in x for x in _wide),
    "%s" % _wide[:2])

# ══════════════════════════════════════════════════════════════
# ④ 隐藏点不再是空壳 + 篝火不漏内部话（P2 BUG②③）
# ══════════════════════════════════════════════════════════════
print("")
print("④ 隐藏点的正文 · 篝火的夜谈（P2 BUG②③）")
_hid = sorted(k for k, v in po.items() if v.get("kind") == "隐藏点")
_hbad = [(k, po[k].get("read_text")) for k in _hid if not po[k].get("read_text")]
chk("★ 三处隐藏点都有正文槽位（%s）" % " · ".join(po[k]["name"] for k in _hid), not _hbad, "%s" % _hbad)
_hbody = [(k, str((tx.get(po[k].get("read_text")) or {}).get("value") or "")) for k in _hid]
chk("★ 三处正文都不是空的（%s）" % " · ".join("%s %d 字" % (po[k]["name"], len(b)) for k, b in _hbody),
    all(b.strip() for _k, b in _hbody))


def epoch_satisfying(cond):
    """这一条 `condition` 满足了的那一刻（没有时辰/天气门槛 ⇒ 回 None，调用方用正午）。"""
    if not (cond.get("time") or cond.get("weather")):
        return None
    for d in range(100, 130):
        for h in range(24):
            e = clock_at(d, float(h) + 0.5)
            at_epoch(e)
            if CAL.allows(cond.get("time"), CAL.state()) and CAL.allows(cond.get("weather"), CAL.state()):
                return e
    return None


_shown = []
for _k in _hid:
    _cond = po[_k].get("condition") or {}
    _e = epoch_satisfying(_cond)
    if _e is not None:
        at_epoch(_e)
    elif not _cond:
        set_clock(100, 12.0)
    _p = player(loc=po[_k]["map"], node=po[_k]["subarea"])
    if _cond.get("read"):
        _p["books"] = {"relic": {str(_cond["read"]): {"known": False}}}
    _out = run(CA.touch, _p)
    _get = V("SYS_TOUCH_GET", icon=po[_k]["icon"], name=po[_k]["name"])
    if _get not in _out:
        _shown.append("%s（没摸到）" % po[_k]["name"])
        continue
    _i = _out.index(_get)
    _nxt = _out[_i + 1] if _i + 1 < len(_out) else ""
    if not _nxt or _nxt == _get or _nxt.startswith(V("SYS_TOUCH_GET", icon="", name="")[:4]):
        _shown.append("%s（上手是空壳 —— 后面没有内容）" % po[_k]["name"])
    elif str((tx.get(po[_k]["read_text"]) or {}).get("value")) not in _nxt:
        _shown.append("%s（后面那行不是它自己的正文）" % po[_k]["name"])
chk("★ 三处隐藏点逐处真敲『触摸』：逐行拿到**自己的正文**（不再是一行标题、零内容）",
    not _shown, "；".join(_shown))
_fires = sorted(k for k, v in po.items() if (v.get("effect") or {}).get("talk"))
_fbad = []
_head_missing = parts("SYS_POI_TALK_MISSING")[0]
for _k in _fires:
    _did = str(po[_k]["effect"]["talk"])
    if _did not in dl:
        _fbad.append("%s → %s 没有定义处" % (_k, _did))
        continue
    if not (dl[_did].get("nodes") or {}):
        _fbad.append("%s → %s 是空树" % (_k, _did))
        continue
    _line = str((dl[_did]["nodes"]["meet"]["texts"][0] or {}).get("text") or "")
    set_clock(100, 21.0)
    _out = run(CA.touch, player(loc=po[_k]["map"], node=po[_k]["subarea"]))
    if _head_missing in "\n".join(_out) or _line not in _out:
        _fbad.append("%s 上手没吐自己的话（%s）" % (po[_k]["name"], _out[-1:]))
chk("★ 三处篝火逐处真敲『触摸』：吐的是**它自己的夜谈**，不再漏「…边的话还没写下来。」"
    "（%d 处 · talk 键 %s）" % (len(_fires), " · ".join(po[k]["effect"]["talk"] for k in _fires)),
    bool(_fires) and not _fbad, "；".join(_fbad))
_rev_hid = {k: v for k, v in po[_hid[0]].items() if k != "read_text"}
chk("★ 反证（拆掉修复）：把隐藏点那一格正文抹掉 ⇒ 上手**不出声**（不再假装摸到）——"
    "`_poi_touch_gives` 当场翻面（%s）" % po[_hid[0]]["name"],
    CA._poi_touch_gives(_rev_hid) is False and CA._poi_touch_gives(po[_hid[0]]) is True)

# ══════════════════════════════════════════════════════════════
# ⑤ NPC 对白按状态分支（P1 BUG-7）
# ══════════════════════════════════════════════════════════════
print("")
print("⑤ 对白不许假定玩家有剑 / 有伤（P1 BUG-7）")
set_clock(100, 12.0)
_K, _E_ = str(np_["npc_cole"]["dialogue"]), str(np_["npc_ed"]["dialogue"])
_KMEET = dl[_K]["nodes"]["meet"]["texts"]
_EMEET = dl[_E_]["nodes"]["meet"]["texts"]
_K_SWORD = "\n".join(t["text"] for t in _KMEET if "equipped" in (t.get("need") or {}))
_E_HURT = "\n".join(t["text"] for t in _EMEET if "hurt" in (t.get("need") or {}))


def pick(did, **kw):
    p = player(**kw)
    return CT._pick_layer(dl[did]["nodes"], p, CAL.state(), did)[2] or ""


_t_hand = pick(_K, equipped={})
_t_sword = pick(_K, equipped={"weapon": "i_weapon_knight_wall_common"})
_cap = CA.hp_cap(player())
_t_full = pick(_E_, hp=_cap)
_t_hurt = pick(_E_, hp=max(1, _cap // 3))
chk("★ 柯尔：空手 ⇒ 不评价刃口（出的是兜底那一句）；手上有武器 ⇒ 才说「你的剑」",
    "你的剑" not in _t_hand and "你的剑" in _t_sword and _t_hand != _t_sword,
    "空手=%r" % _t_hand[:20])
chk("★ 艾德：满血 ⇒ 「没伤」（与 `教堂` 那句同口径：%s）；有伤 ⇒ 才说「伤口我看看」"
    % V("SYS_CHAPEL_FULL", who=str(np_["npc_ed"]["name"]))[:20],
    "伤口我看看" not in _t_full and "没伤" in _t_full
    and "伤口我看看" in _t_hurt and _t_full != _t_hurt,
    "满血=%r ／ 有伤=%r" % (_t_full[:16], _t_hurt[:16]))
chk("★ 那两句真挂在 need 上（equipped: weapon / hurt: true），且兜底那句仍排在最后"
    "（具体 → 宽松，`_pick_indexed` 挑第一条满足的）",
    any("equipped" in (t.get("need") or {}) for t in _KMEET)
    and any("hurt" in (t.get("need") or {}) for t in _EMEET)
    and _KMEET[-1]["need"] is None and _EMEET[-1]["need"] is None)
# 反证：把 need 抹掉（只留兜底那句）⇒ 空手满血也照说剑 / 伤口
_rev_k = CT._pick_indexed([{"need": None, "text": _K_SWORD}], player(), None)[1] or ""
_rev_e = CT._pick_indexed([{"need": None, "text": _E_HURT}], player(), None)[1] or ""
chk("★ 反证（拆掉修复）：把那一句还原成**修复前的形状**（唯一一条 · `need = None`："
    "这就是原先那份数据）⇒ 空手满血的档**又**听到剑 / 伤口 —— 判据真的判的是 need 那一格",
    "你的剑" in _rev_k and "伤口我看看" in _rev_e and _rev_k != _t_hand and _rev_e != _t_full,
    "还原后 空手=%r ／ 满血=%r" % (_rev_k[:12], _rev_e[:12]))

# ══════════════════════════════════════════════════════════════
# ⑥ 小事四件（体验-10 / 11 / 6 / 14）
# ══════════════════════════════════════════════════════════════
print("")
print("⑥ 小事四件（体验-10 / 11 / 6 / 14）")
chk("★ 锁定那两句带上主语（与「看得见」同一形：『名字』图标）—— 不再是一行没有主语的裸名字",
    _lock.startswith("『%s』%s" % (_gname, po[_gated]["icon"]))
    and CA._poi_label({"name": "X", "icon": ""}) == "X",
    "%s" % _lock[:24])
# ⑥-b 怪物那一栏有表头 —— 找一天真有精英的站（现算，不手打）
_foe_lab = V("SYS_LOOK_FOE")
_foe_ok, _foe_extra, _foe_plain = "", "", ""
for _d in range(100, 130):
    set_clock(_d, 12.0)
    _gd = CAL.state().get("game_day")
    for _loc, _m in mp.items():
        for _n in (_m.get("nodes") or []):
            _nid = str(_n.get("id"))
            for _lv in (3, 5, 8):
                _el = AFFIX.elite_of(mo, _loc, _nid, "u_onsite", _gd, _lv)
                if not _el:
                    continue
                _o = run(CA.look, player(loc=_loc, node=_nid, level=_lv))
                _want = AFFIX.elite_line(str((mo.get(_el[0]) or {}).get("name", _el[0])), _el[1])
                _foe_ok = (_foe_lab in _o and _o.index(_foe_lab) + 1 < len(_o)
                           and _o[_o.index(_foe_lab) + 1] == _want)
                _foe_extra = "%s/%s L%d ⇒ %r" % (_loc, _nid, _lv, _want[:16])
                break
            if _foe_extra:
                break
        if _foe_extra:
            break
    if _foe_extra:
        break
chk("★ 观察 里那一栏怪物有表头「%s」，紧跟其后才是怪那一行（%s）" % (_foe_lab, _foe_extra), _foe_ok)
_foe_plain = run(CA.look, player(loc=TOWN, node="wt_gate_n"))
chk("★ 反证：这一站今天没有精英 ⇒ **不出**表头（判据不是「总要有一行」）",
    _foe_lab not in _foe_plain, "%s" % _foe_plain[-2:])
# ⑥-c 搭话多人：把名字都写进教法那一句
set_clock(D_PLAIN, 12.0)
_HOW_MANY_HEAD, HOW_MANY_TAIL = parts("SYS_TALK_HOW_MANY")
_two = run(CT.talk, player(loc=TOWN, node="wt_chapel"))
_one = run(CT.talk, player(loc=TOWN, node="wt_herbs"))
_names2 = [str(v.get("name")) for _k, v in CA._npcs_here(TOWN, "wt_chapel", p=player())]
_names1 = [str(v.get("name")) for _k, v in CA._npcs_here(TOWN, "wt_herbs", p=player())]
_how2 = _two[-1] if _two else ""
chk("★ 一站两个人（%s）⇒ 教法那一句把**都**写上：%s" % (" · ".join(_names2), _how2),
    len(_names2) > 1 and _how2.startswith(_HOW_MANY_HEAD) and _how2.endswith(HOW_MANY_TAIL)
    and all(("『%s』" % n) in _how2 for n in _names2), "%s" % _two[-1:])
chk("★ 一个人时照旧走老那一句（不硬凑「都行」）",
    len(_names1) == 1 and (_one[-1] if _one else "").endswith(parts("SYS_TALK_HOW")[1])
    and (_one[-1] if _one else "").startswith(parts("SYS_TALK_HOW")[0]), "%s" % _one[-1:])
# ⑥-d 药铺：柜上有什么与摊名不是一回事
_nana_node = str(np_["npc_nana"]["subarea"])
_shop = run(CP.herbalist, player(loc=TOWN, node=_nana_node))
chk("★ 药铺面板里说明「摊上只卖药」（%s）" % V("SYS_SHOP_HERB_NOTE"),
    V("SYS_SHOP_HERB_NOTE") in _shop, "%s" % _shop)

print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
