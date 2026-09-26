# -*- coding: utf-8 -*-
"""探针：texts 域（文案槽位表）—— 键名规则 · params 与 value 的占位对账 · 待填进度。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_texts.py
"""
from __future__ import annotations

import os
import time
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402

ok = True
#: ★ B4-16 起 `RANK_*` 也在这一族里（公会评级那几张档名 —— 与 `scripts/rebuild_syscopy.py`
#:   的 KEY_RE 逐字同形：两处必须一起改，否则一个认一个不认）
KEY_RE = re.compile(r"^(SCENE|READ|NPC|COMBAT|QUEST|ITEM|SYS|TITLE|WORLD|HOUR|WEATHER|UNID|TALK|RANK)_[A-Z0-9_]+$")
PH = re.compile(r"\{(\w+)(?::[^{}]*)?\}")   #: ★ B4-23：占位可带格式符（`{cur:.0f}`）—— 与 `scripts/rebuild_syscopy.py` 的 PH 逐字同形（两处一起改）


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


print("探针：texts 域（文案槽位表）")
st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
st.install()
tx = st.domain("texts")
chk("texts 域读得到", tx is not None, "%d 条" % (len(tx) if tx else 0))
if not tx:
    sys.exit(1)

# ① 每条结构
bad1 = [k for k, v in tx.items()
        if not isinstance(v, dict) or "value" not in v or "category" not in v]
chk("每条都有 value/category", not bad1, " · ".join(bad1[:5]))

# ② 键名规则
bad2 = [k for k in tx if not KEY_RE.match(k)]
chk("键名都符合 「类_对象_状态」规则", not bad2, " · ".join(bad2[:6]))

# ③ ★ params 声明的参数，value 里必须有对应占位
bad3 = []
for k, v in tx.items():
    used3 = set(PH.findall(v["value"]))          #: ★ B4-23：按占位**名**认（带不带格式符都算）
    for prm in v.get("params", []):
        if prm not in used3:
            bad3.append("%s 缺 {%s}" % (k, prm))
chk("★ 声明的 params 都在 value 里有占位", not bad3, " · ".join(bad3[:5]))

# ④ ★ value 里出现的占位，都声明过 params（防漏声明 + 防打错）
bad4 = []
for k, v in tx.items():
    used = set(PH.findall(v["value"]))
    decl = set(v.get("params", []))
    if used - decl:
        bad4.append("%s 未声明：%s" % (k, sorted(used - decl)))
chk("★ value 里的占位都已声明 params", not bad4, " · ".join(bad4[:5]))

# ⑤ 待填进度（不是错误，是工单进度）
todo = [k for k, v in tx.items() if "〔待填" in v["value"]]
print("  · 待填 %d 条 / 已写 %d 条" % (len(todo), len(tx) - len(todo)))

# ⑥ 分类计数
by_cat = {}
for k, v in tx.items():
    by_cat.setdefault(v.get("category", "?"), 0)
    by_cat[v["category"]] += 1
print("  · " + " · ".join("%s %d" % (c, n) for c, n in sorted(by_cat.items(), key=lambda x: -x[1])))

# ⑦ ★ B3-6a：场景口 —— 每个节点都取得到场景槽位（观察取的就是它）
from content.scene import resolve as _resolve, node_key as _nk        # noqa: E402

mp = st.domain("maps") or {}
nodes = [(loc, n["id"]) for loc, m in mp.items() for n in (m.get("nodes") or [])]
unr = [(loc, nd) for loc, nd in nodes if not _resolve(tx, loc, nd)]
chk("★ 地图上 %d 个节点都能取到场景槽位（节点级 %d）"
    % (len(nodes), len([1 for _l, nd in nodes if _nk(nd) in tx])), not unr, "取不到：%s" % unr)

# ⑧ ★ 真调「观察」（造档逐节点）—— 第一位那行必须就是该节点的场景正文
#    ★ 本波（P1 BUG-5）：节点级场景多了一版「这一站的人此刻都不在」（`SCENE_<节点>_EMPTY`，
#      判据在 `content/town.py::station_empty`）⇒ 期望值 = **两版里的哪一版**：
#      「本该有人却一个都没到场」⇒ 必须逐字是空版；否则必须逐字是正版。
#      **钟先钉死**（判据不许看真钟 —— K79 那一族），人名单按域现算（不是照代码抄）。
import asyncio                                                        # noqa: E402

from content import cmds_ast as CA                                    # noqa: E402
from content import calendar as _CAL                                  # noqa: E402
from content import facade as _FAC                                    # noqa: E402
from content import town as _TW                                       # noqa: E402
from content.scene import empty_key as _ek                            # noqa: E402

_FIX = 100 * _CAL.scale_seconds() + 0.5 * _CAL.scale_seconds()        # 第 100 个游戏日 · 正午
_FAC.bind_host(clock=lambda: _FIX)


class _E:               # 「观察」只要 env.save()（落档是处理器的责任）
    text = ""

    def save(self):
        pass


def _look_first(loc, node):
    p = dict(CA.DEFAULT_PLAYER)
    p.update({"loc": loc, "node": node, "race": "human"})  # ★ P-10：档上要有族，否则第一眼是「选族菜单」而不是场景（探针测的是已建号的玩家）
    out = []

    async def _go():
        async for line in CA.look(_E(), None, "u_scene", p):
            out.append(line)

    asyncio.run(_go())
    return out


wrong, _tally = [], {"正版": 0, "空版": 0}
for loc, nd in nodes:
    _p = dict(CA.DEFAULT_PLAYER)
    _p.update({"loc": loc, "node": nd, "race": "human", "cls": "cls_knight"})
    _empty = bool(_TW.station_empty(loc, nd, _p))
    _key = _ek(nd) if _empty else _resolve(tx, loc, nd)
    if _key not in tx:                                 # 空版没写 ⇒ 照旧走正版（不静默给空）
        _key = _resolve(tx, loc, nd)
    _tally["空版" if _key == _ek(nd) else "正版"] += 1
    first = _look_first(loc, nd)[0]
    if first != tx[_key]["value"]:
        wrong.append((nd, first[:24]))
chk("★ 观察 逐节点产出的就是该节点的场景正文（%d 个节点；本波起「有人版 / 人不在版」两版，"
    "钟钉在正午 · 按域现算该走哪一版：正版 %d · 空版 %d）"
    % (len(nodes), _tally["正版"], _tally["空版"]), not wrong, "对不上：%s" % wrong[:4])

# ⑨ 节点级场景是正文（≥80 字 —— 工单占位只有 7~16 字，一跑就露）
#    ★ 本波：空版也算节点级场景的正文之一（两版都要立得住 —— 短的/占位的一跑就露）
_empties = sorted(k for k in tx if k.endswith("_EMPTY") and k.startswith("SCENE_"))
short = [(k, len(tx[k]["value"])) for _l, nd in nodes if _nk(nd) in tx and len(tx[_nk(nd)]["value"]) < 80]
short += [(k, len(tx[k]["value"])) for k in _empties if len(tx[k]["value"]) < 80]
chk("★ 节点级场景都是正文（≥80 字；含 %d 条「人不在版」：%s）" % (len(_empties), " · ".join(_empties)),
    not short, "%s" % short[:5])

# ⑩ 场景类没有待填（这一批的工单清完了）
todo_scene = [k for k, v in tx.items() if v.get("category") == "场景" and "〔待填" in v["value"]]
chk("场景类 0 条待填", not todo_scene, "%s" % todo_scene[:5])

# ⑪ ★ fix3-④：聆听 —— 每个节点都听得到**这一站自己的**那一句
#   原先代码只按 `p["loc"]`（图）取 `WORLD_LISHEN_<图>`，而 texts 域里一张图都没有这一族
#   ⇒ 玩家在镇上 11 个站点听到的是同一句 `SYS_LISTEN_DEFAULT`（P1 体验-3：与同站『观察』
#   写的东西对不上 —— 观察写着雨、炉火、草汁、白烛，聆听只有一句「风声。远处有水声。」）。
#   口径与 `scene.resolve` 一致：节点级 → 地图级 → 通用句；判据 = **逐节点真跑** + 互不相同。
import asyncio as _a11                                                    # noqa: E402


class _E11:                # `聆听` 不要 env（只取档）
    text = ""


def _listen_lines(loc, node):
    p = dict(CA.DEFAULT_PLAYER)
    p.update({"loc": loc, "node": node, "race": "human"})
    out = []

    async def _go():
        async for ln in CA.listen(_E11(), None, "u_listen", p):
            out.append(ln)

    _a11.run(_go())
    return out


_lk = [(loc, nd, "WORLD_LISHEN_%s" % nd.upper()) for loc, nd in nodes]
_missing = [(nd, k) for _l, nd, k in _lk if k not in tx]
_leaked = [(loc, nd, _listen_lines(loc, nd)[0]) for loc, nd, _k in _lk
           if _listen_lines(loc, nd)[0] == tx["SYS_LISTEN_DEFAULT"]["value"]]
_vals = {}
for _l, _nd, _k in _lk:
    if _k in tx:
        _vals.setdefault(tx[_k]["value"], []).append(_nd)
_dupes = {v: who for v, who in _vals.items() if len(who) > 1}
_bad11 = [(nd, len(tx[k]["value"]), tx[k]["value"]) for _l, nd, k in _lk
          if k in tx and (len(tx[k]["value"]) > 40 or "\n" in tx[k]["value"])]
chk("★ 聆听：%d 个节点**各有自己一句**（槽位 `WORLD_LISHEN_<节点>` 逐个在 texts 里）"
    % len(nodes), not _missing, "缺：%s" % (_missing[:4] or "无"))
chk("★ 聆听：没有哪个节点还落回通用句 `SYS_LISTEN_DEFAULT`（旧口径 = 镇上 11 站同一句）",
    not _leaked, "%s" % (_leaked[:3] or "0 个节点"))
chk("★ 聆听：%d 句两两不同（同一张图上也是）」" % len(_vals), not _dupes,
    "%s" % (_dupes or "无重复"))
chk("★ 聆听：每句都是**一行**、且 ≤ 40 字（一屏一行读得完）", not _bad11,
    "%s" % (_bad11[:3] or "全在 40 字以内"))
chk("★ 聆听 真跑逐节点产出的就是该节点那一句（%d 个节点）" % len(nodes),
    not [1 for _l, _nd, _k in _lk if _k in tx and _listen_lines(_l, _nd)[0] != tx[_k]["value"]],
    "%s" % [(_nd, _listen_lines(_l, _nd)[0][:12]) for _l, _nd, _k in _lk
            if _k in tx and _listen_lines(_l, _nd)[0] != tx[_k]["value"]][:3])

# ⑫ ★ fix3-③：**门控产出不许被「观察」提前承诺** —— 场景正文提到被时辰/天气锁住的产出时，
#   必须同现那道门槛的词。玩家报的原状（P2 BUG⑥）：白桦林`观察`写「树根边冒出来一片菌」，
#   而同站采集点的门槛是「只在雨出」，晴天去采只会得到「树根边的菌只在「雨」出」。
#   登记表 = (场景槽位, 会踩到这道门的锚词, 必须同现的门槛词, 那条被锁住的采集点)。
from content import calendar as _CAL12                                    # noqa: E402

GATED_SCENE = [
    ("SCENE_BE_BIRCH", ("菌", "断口"), "雨", "gt_be_herb_1"),
    ("SCENE_BN_TOWER", ("白茅",), "夜", "gt_bn_herb_2"),
]
_gs_bad = []
for _sk, _anchors, _gate, _gid in GATED_SCENE:
    _txt = (tx.get(_sk) or {}).get("value") or ""
    _hit = [a for a in _anchors if a in _txt]
    if _hit and _gate not in _txt:
        _gs_bad.append("%s 提到 %s 却没写门槛「%s」" % (_sk, _hit, _gate))
    _pt = ((st.domain("gathering") or {}).get(_gid) or {}).get("time")
    if _CAL12.resolve(_gate)[1] is None or _pt != _gate:
        _gs_bad.append("%s 登记的采集点 %s 门槛对不上（域里是 %r）" % (_sk, _gid, _pt))
chk("★ 门控产出：场景正文提到被判了门槛的产出时，得同现那道门槛的词"
    "（雨后的菌 / 夜里的白茅 —— 正文与采集点不许两套口径）", not _gs_bad,
    "%s" % (_gs_bad or "两处都同现门槛词"))

# 反证：这条判据抓得住旧文案（旧正文提了菌、一个字没提门槛）
_OLD_BIRCH = ("林子里的白桦一般粗，只有靠里的几棵例外。路是人踩出来的，踩在落叶上，浅得只有一层。"
              "树皮上的刻痕一处比一处高 —— 刻的人一年比一年够得着更高。"
              "树根边冒出来一片菌，有几朵被踩坏了，断口还是新的。")
_old_hit = [a for a in ("菌", "断口") if a in _OLD_BIRCH]
chk("★ 反证：旧白桦林正文（提「菌」不提门槛）会被判红", bool(_old_hit) and "雨" not in _OLD_BIRCH,
    "锚词命中 %s · 门槛词「雨」在不在：%s" % (_old_hit, "雨" in _OLD_BIRCH))

print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
