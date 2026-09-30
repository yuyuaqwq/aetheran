# -*- coding: utf-8 -*-
"""探针：委托闭环与新手引导（QB 六条 —— 试玩 QA 那一批修的六件）。

来源：四个真人玩家的试玩报告（原样指令 + 原样回话）
  P1 BUG-1（委托 25 交不掉）· P1 BUG-2（悬赏 101 交不掉）· P1 BUG-3 / P4 E-1（『提示』不随委托走）·
  P1 BUG-13 / P4 BUG-7（老陶讲完三次后永久哑）· P4 E-10（『我的委托』不给进度）·
  P2 BUG⑨（`读 <名字>` 对不上时只说「这里没有能读的东西」）· P1 BUG-10（主线 1「试着读（读不懂）」）。

★ 每条**正例 + 反证**：反证一律在进程内把那一处**临时**关掉（跑完立刻还原），
  证明判据不是恒真 —— 修复被拆掉时这一支当场红。

  ① 卡死 1 · 委托 25「还石头」交得掉
     单子要 `i_token_stone_shard`（「刻字的石片」），玩家在骨田挖到的那件叫「一块刻着字的石片」
     —— 它是 `drop_pools` 上的**未鉴定容器** `unid_rare`（`hint` 与那件信物的 `lore` 逐字相同），
     池里**唯一**那件「故事类」就是它。真源：`15 §二` 第 2 行（hold=i_token_stone_shard ·
     小满的石头 = 骨田捡的刻字石片）+ `06 §1.2`（刻字的石片 ← 骨田「挖掘」挖出来）+ `27 §三`。
     正例：包里放**容器** ⇒ 交得掉（档上真写 `quests_done`）· 真信物那条老路照样通。
     反证：把 `_unid_carries` 关掉 ⇒ 拦住 ｜ 池里没有那件的容器（`unid_common`）⇒ 拦住 ｜
           同池两件故事类（合成池）⇒ 拦住 ｜ 材料类不许被顶掉（`unid_rare` 顶不掉「旧铁」）。
  ② 卡死 2 · 悬赏 101：点名那只要说清**出没在哪几站**
     报告里玩家在「野狗窝」杀了四回「拾荒野狗」，而单子要的是「野狗」（名字只差三个字）。
     正例：七种日子逐日真敲『交 101』⇒「还差…」后面跟着一条「（它出没在：…）」，站名与
           `monsters.habitat` × `maps` 现算出来的**逐字相同**。
     反证：把 `_habitat_of` 关掉 ⇒ 那一行不出现（判据不是恒真）· 那条新行**不许**含「还差」
           （不然 ㉑/㉛ 的「还差条数 = 条件条数」当场错位）。
  ③ 卡死 3 · 『提示』随委托走
     每条接活回话都写着「『提示』会告诉你往哪走」；真源 `04 §一`「`提示` ｜ 随时 ｜
     给一条**当前**该做什么的提示」。
     正例：手上有活 ⇒ 第一行 = `SYS_HINT_JOB` 填当前委托，后面是那一条「还差」的**同一批行**
           （同一个口 `_unmet`）；万事俱备 ⇒ 那句「打『交 <编号>』」；手上没活 ⇒ 建号那句逐字不变。
     反证：把 `_hint_lines` 关掉 ⇒ 退回建号那句（= 报告里那条 bug 的原样）。
  ④ 卡死 4（引导）· 老陶三次各讲一段
     原先他只有 `meet` 一层（14 棵树里唯一没有 `daily` 的）⇒ 第 3 次搭话正好「熟了」，
     `meet` 不再算数、又没有 `daily` ⇒ 「（他没说话。）」，而这一回**照样计入**判定。
     正例：真搭话 4 次 ⇒ 一次都不出现「（他没说话。）」｜ 4 次以内听满**三段不同**的话｜
           `flags.talked` 的计数口径不动（交 21 照样交得掉）。
     反证：把 `daily` / `main` 两层临时摘掉（= 改前那棵树）⇒ 第 3 次当场回「（他没说话。）」。
  ⑤ ·『我的委托』给进度计数 ＋ `读 <名字>` 对不上时点名并列出这站能读的
     正例：`（1/3）` / `（3/3）` 逐条对 · 没写 `require` 的老条目一个字不多 ·
           骨田 `读 不存在的东西` ⇒ 点名说对不上 + 列出这站能读的（现从 `pois` 域算）·
           对的名字照旧给正文（老路一个字不动）。
     反证：把 `_progress` 关掉 ⇒ 那一格消失 ｜ 名字对不上时**不许**再回「这里没有能读的东西」
           （那句只留给「这站真没有可读物」—— 空参那条路照旧）。
  ⑥ · 主线 1「试着读（读不懂）」与『读』当场给的正文对上
     objective 那一格是**真源 `24 §一` 主 1 的「步骤」行**（一个字不动）；对得上的是『读』这边 ——
     镇口那块石头的正文必须把「读不懂」落到屏幕上（源 `02 §一`「我不认得。旁边那个人也不认得。」）。
     正例：objective 含「试着读（读不懂）」· 读出来的正文含「一个也读不出来」。
     反证：把那句从正文槽位里拆掉 ⇒ 当场红（两边又打架）。

★ g3-quests2（2026-09-26）加的两条（三件「差最后一步」里的两件 —— 悬赏池收窄那一件在
  `scripts/probe_quests.py ㉛` 与本章 ② 里）：
  ⑦ 支线「还石头」**接活时真发东西**：`接 25` 真给到手上（包里真多一件 + 屏上「得到：…」），
     那件东西 = `15 §二` 彩蛋 2 那一行 `hold=` 现解析；反证：拿掉 `give` ⇒ 一个东西都不发。
  ⑧ 对话旗标族**补写端**：域里 12 条 slug 全接上真实进度（`content/prog.py`）· 写端三拍
     （接/交/放弃）· 读端真搭话 · 两条反证（没做到 ⇒ 不出 ｜ 只手塞脏旗标 ⇒ 照样不出）。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_qloop.py
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
PLAN = os.environ.get("AST_PLAN", "C:/Users/yuyu/aetheran-plan")
sys.path.insert(0, ENGINE)
sys.path.insert(0, REPO)

from saintess_engine.package import load_stack                       # noqa: E402

st = load_stack(str(REPO), inject={"db_path": os.path.join(
    os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
st.install()

from content import calendar as CAL                                  # noqa: E402
from content import cmds_ast as CA                                   # noqa: E402
from content import cmds_quest as CQ                                 # noqa: E402
from content import cmds_talk as CT                                  # noqa: E402
from content import facade as FC                                     # noqa: E402
from content import heard as HD                                      # noqa: E402
from content import loot as LT                                       # noqa: E402
from content import prog as PROG                                     # noqa: E402  ★ g3-quests2

QE = {k: v for k, v in st.domain("quests").items() if not str(k).startswith("_")}
MON = st.domain("monsters")
MAPS = st.domain("maps")
PO = st.domain("pois")
DP = st.domain("drop_pools")
NPCS = st.domain("npcs")
TX = st.domain("texts")

#: ★ P2-3（2026-09-29）：与 `probe_quests` 同一处收口 —— 「交活那一行」的判据
#:   原本把中文首字写死（`startswith("交了")`，本文件 3 处）⇒ 文案句首加了 `✔ `
#:   之后判据整体翻红，而行为一行没变。口径：前缀**从 texts 槽位现算**，
#:   判据断言强度不变（仍要钉「交得掉/交不掉」，只是不再钉中文首字）。
def _lead(slot: str) -> str:
    """那一格行首的锚（行首那一段连续的非中文前缀：emoji 与其后空格）。"""
    v = str((TX.get(slot) or {}).get("value") or "")
    head = v.split("　")[0]
    i = 0
    for ch in head:
        if ch in "✔✅📜🎁🗑️ ":
            i += 1
        else:
            break
    return v[:i] if i else head


_JOB_DELIVERED = _lead("SYS_JOB_DELIVERED")

_FC_SAVED = dict(FC.HANDLES)
_SCS = CAL.scale_seconds()


def _at_day(d, h=6.0):
    """假钟拨到「第 d 个游戏日 · 昼」—— 轮换与日期戳看的就是这根钟（照 probe_quests 那一手）。"""
    FC.bind_host(clock=lambda _e=(float(d) + h / 24.0) * _SCS: _e)


class _E:
    """实现体只要 env.text + env.save()。"""

    def __init__(self, text=""):
        self.text = text

    def save(self):
        pass


def _drive(fn, p, text=""):
    out = []

    async def go():
        async for line in fn(_E(text), None, "u_q", p):
            out.append(line)

    asyncio.run(go())
    return out


def _player(**kw):
    p = dict(CA.DEFAULT_PLAYER)
    p.update(kw)
    return p


def T(key, **slots):
    return CA.T(key, **slots)


MISSING = "[MISSING TEXT"
fails, CHECKS = [], [0]
ok = lambda m: (CHECKS.__setitem__(0, CHECKS[0] + 1), print("  ✓ " + m))
bad = lambda m: (fails.append(m), CHECKS.__setitem__(0, CHECKS[0] + 1), print("  ✗ " + m))

print("探针：委托闭环与新手引导（QB 六条）")

# ══════════════════════════════════════════════════════════════
# ⓪ 前提：这一批要修的那几条还在域里（不然下面几条判据会「静默通过」）
# ══════════════════════════════════════════════════════════════
_b0 = []
_q13 = QE.get("q_side_13") or {}
if [r for r in (CQ._require_of(_q13) if _q13 else []) if r.get("kind") == "item"] \
        != [{"kind": "item", "item": "i_token_stone_shard", "n": 1}]:
    _b0.append("q_side_13 的条件那一格变了：%s" % json.dumps(_q13.get("require"), ensure_ascii=False))
_bn = QE.get("q_bounty_normal") or {}
if not any(r.get("kind") == "kill" and r.get("daily") and r.get("role") for r in CQ._require_of(_bn)):
    _b0.append("q_bounty_normal 不再是「点档 + daily」")
_u = DP.get("unid_rare") or {}
if str(_u.get("kind_key")) != "unidentified":
    _b0.append("unid_rare 不再是未鉴定容器")
if (TX.get("READ_STONE_SCRIPTS") or {}).get("value", "").find("一个也读不出来") < 0 \
        and (MON.get("ms_wild_dog") or {}).get("habitat") is None:
    _b0.append("前置一格都没有（域形状变了）")
(ok if not _b0 else bad)("⓪ 前提：q_side_13 要 `i_token_stone_shard` · 悬赏 101 点档 + daily · "
                         "`unid_rare` 是未鉴定容器（坏 %s）" % (_b0 or "无"))

# ══════════════════════════════════════════════════════════════
# ① 委托 25「还石头」：手上是**未鉴定**的那一件也算（唯一那一件故事物件）
# ══════════════════════════════════════════════════════════════
_b1, _l1 = [], []


def _q13p(bag, foot=True):
    """站上骨田 + 背包里放那几样 —— 交 25 的那一份档。"""
    return _player(level=1, bag=bag, gold=0,
                   foot={"nodes": {"belt_north:bn_bone": 1}} if foot else {},
                   flags={"quests_active": ["q_side_13"]})


def _delivered(p, out):
    return any(ln.startswith(_JOB_DELIVERED) for ln in out) \
        and "q_side_13" in ((p.get("flags") or {}).get("quests_done") or [])


# 正例 ①-a：背包里是**容器**（骨田挖到的那件）
_pa = _q13p({"unid_rare": 1})
_oa = _drive(CQ.quest_deliver, _pa, "交 25")
if not _delivered(_pa, _oa):
    _b1.append(("容器那一档交不掉", _oa[:3]))
_l1.append("容器那件（unid_rare「一块刻着字的石片」）→ %s"
           % next((ln for ln in _oa if ln.startswith(_JOB_DELIVERED)), "?"))
# 正例 ①-b：真信物那条老路（逐字节不许动）
_pb = _q13p({"i_token_stone_shard": 1})
_ob = _drive(CQ.quest_deliver, _pb, "交 25")
if not _delivered(_pb, _ob):
    _b1.append(("真信物那一档反倒交不掉了", _ob[:3]))
# 反证 ①-c：把这一支关掉 ⇒ 拦住（= 报告里那条 bug 的原样）
_keep_unid = CQ._unid_carries
try:
    CQ._unid_carries = (lambda *_a: False)
    _pc = _q13p({"unid_rare": 1})
    _oc = _drive(CQ.quest_deliver, _pc, "交 25")
finally:
    CQ._unid_carries = _keep_unid
if _delivered(_pc, _oc) or not any("还差" in ln for ln in _oc):
    _b1.append(("反证没生效（关掉那一支还能交掉 / 没报还差）", _oc[:3]))
# 反证 ①-d：池里没有那一件的容器 ⇒ 不算（unid_common 里没有信物 / 线索）
if CQ._unid_carries("unid_common", "i_token_stone_shard") \
        or CQ._bag_n({"bag": {"unid_common": 1}}, "i_token_stone_shard"):
    _b1.append(("池里没有那件的容器也被算进来了", "unid_common"))
_pd = _q13p({"unid_common": 1})
_od = _drive(CQ.quest_deliver, _pd, "交 25")
if _delivered(_pd, _od):
    _b1.append(("拿一件开不出石片的容器也交得掉", _od[:3]))
# 反证 ①-e：容器自己那句与那件东西那句**不一样** ⇒ 不算（`unid_tower` 那句是凉的）
if CQ._unid_carries("unid_tower", "i_token_stone_shard"):
    _b1.append(("hint 不一样也被算了（该 fail-closed）", "unid_tower"))
# 反证 ①-f：材料 / 垃圾类不许被容器顶掉（不然「找一块旧铁」会被一件未鉴定顶过去）
if CQ._bag_n({"bag": {"unid_rare": 1}}, "i_material_old_iron") \
        or CQ._bag_n({"bag": {"unid_rare": 1}}, "i_junk_bone"):
    _b1.append(("材料/垃圾也被容器顶掉了（放宽过头）", "i_material_old_iron / i_junk_bone"))
# 正例 ①-g：那条判据挂在**数据**上（容器 `hint` == 那件东西的 `lore`）—— 逐字核一遍
_shard = (st.domain("items").get("i_token_stone_shard") or {})
_uni = (st.domain("drop_pools").get("unid_rare") or {})
if not _shard.get("lore") or _uni.get("hint") != _shard.get("lore"):
    _b1.append(("那条判据挂的数据断了（unid_rare.hint ≠ i_token_stone_shard.lore）",
                (_uni.get("hint"), _shard.get("lore"))))
if not any(str((e or {}).get("out") or "") == "i_token_stone_shard"
           for e in (_uni.get("pool") or [])):
    _b1.append(("unid_rare 的池里没有那件信物（数据面变了）", "i_token_stone_shard"))
(ok if not _b1 else bad)(
    "① 委托 25「还石头」：手上那件**未鉴定**的算数（容器自己那句 = 那件信物的那句，数据比数据）"
    "—— 真交得掉、奖励入档；真信物照旧；池里没有的 / hint 不一样的 / 材料类一律不算"
    "（反证 3 条 + 数据链 2 条 · 坏 %s）" % (_b1 or "无"))
for _ln in _l1:
    print("      %s" % _ln)

# ══════════════════════════════════════════════════════════════
# ② 悬赏 101：点名那只**按这一档的标称等级真碰得上**，并把出没地落到屏幕上（逐日真敲）
#    ★ g3-quests2：轮换池按**可遇性**收窄（旧规格 = 该档全部怪 ⇒ 可能点名一只 1 级档在
#      「野狗窝」根本撞不上的怪 —— 报告 P1 BUG-2：杀成 4 回「拾荒野狗」而单子要的「野狗」
#      一次没出）。尺子与实现各写一份：habitat 写明的**每一站**上，按该档 `min_level`
#      都进得了「等级最近前 3」。
# ══════════════════════════════════════════════════════════════
_b2, _l2 = [], []
_norm_ids = sorted(k for k, m in MON.items()
                   if not str(k).startswith("_") and m.get("role_key") == "normal")


def _mon_name(mid):
    return (MON.get(mid) or {}).get("name") or mid


def _tier_lv(role):
    """这一档悬赏自己标的等级（那条单子的 `min_level`；认不出回 0）。"""
    for _v in QE.values():
        for _r in CQ._require_of(_v):
            if _r.get("kind") == "kill" and str(_r.get("role") or "") == str(role or ""):
                return int(_v.get("min_level") or 0)
    return 0


def _top3(loc, node, level):
    """这一站上「说得上话的怪」按等级最近的前 3（照 `combat.pick_encounter` 自己写一遍）。"""
    cand = [k for k, m in MON.items() if not str(k).startswith("_")
            and loc in ((m.get("habitat") or {}).get("maps") or [])
            and (not ((m.get("habitat") or {}).get("nodes") or [])
                 or node in ((m.get("habitat") or {}).get("nodes") or []))]
    cand.sort(key=lambda k: abs(int(MON[k].get("lv", 1)) - level))
    return cand[:3]


def _spots_spec(mid):
    hb = (MON.get(mid) or {}).get("habitat") or {}
    ns = [str(x) for x in (hb.get("nodes") or []) if x]
    out = []
    for m in (hb.get("maps") or []):
        for nd in ((MAPS.get(str(m)) or {}).get("nodes") or []):
            nid = str((nd or {}).get("id") or "")
            if nid and (not ns or nid in ns):
                out.append((str(m), nid))
    return out


#: ★ 本波（2026-09-27 · 任务②）：**等级带** —— 探针自己读声明表 `content/rules/level_band.json`，
#:   判据自己写一遍（不与实现共用函数 —— 照 ⑬/⑳ 的老规矩）。
_BAND_MAX = int(json.load(io.open(os.path.join(REPO, "content", "rules", "level_band.json"),
                                 encoding="utf-8"))["max_level_diff"]["value"])


def _in_band(lv_mon, lv_ref):
    """|怪 lv − 参照等级| ≤ 带宽 ⇒ 带内（悬赏的参照 = 该档 `min_level`）。"""
    return abs(int(lv_mon) - int(lv_ref)) <= _BAND_MAX


def _pool_spec(role):
    """★ 这一档的**可遇集合**（探针自己算）：① 每一站上都进得了「等级最近前 3」；
    ② **且落在等级带内**（本波加的 —— 只站着 3 只怪的站上「前 3」= 全部，1 级档因此点到
    lv9 石滩螃蟹、5 级档点到 lv13 水里的东西）。"""
    lv = _tier_lv(role)
    out = []
    for mid in sorted(k for k, m in MON.items()
                      if not str(k).startswith("_") and m.get("role_key") == role):
        spots = _spots_spec(mid)
        if lv > 0 and spots and _in_band(MON[mid].get("lv"), lv) \
                and all(mid in _top3(_l, _n, lv) for _l, _n in spots):
            out.append(mid)
    return out


def _pool_spec_no_band(role):
    """只按旧尺子的可遇集合（反证用）。"""
    lv = _tier_lv(role)
    out = []
    for mid in sorted(k for k, m in MON.items()
                      if not str(k).startswith("_") and m.get("role_key") == role):
        spots = _spots_spec(mid)
        if lv > 0 and spots and all(mid in _top3(_l, _n, lv) for _l, _n in spots):
            out.append(mid)
    return out


_norm_pool = _pool_spec("normal")                      # ★ 新规格的池（不是全档）
if _pool_spec("normal") != list(CQ._pool_of("normal")):
    _b2.append(("规范池 %s ≠ 实现 %s" % (_norm_pool, list(CQ._pool_of("normal"))), ""))
_cut_norm = [m for m in _norm_ids if m not in _norm_pool]
if not _cut_norm:
    _b2.append(("普通档一只都没被剔掉 —— 可遇性/等级带过滤没生效", ""))
_lv_norm = _tier_lv("normal")
for _m in _norm_pool:                                   # ★ 正例：池里每一只都在带内
    if not _in_band(MON[_m].get("lv"), _lv_norm):
        _b2.append(("★ 池里「%s」（lv%s）在等级带外（标称 %s 级 · 带宽 %d）"
                    % (_mon_name(_m), MON[_m].get("lv"), _lv_norm, _BAND_MAX), ""))
_cut_band = [m for m in _norm_ids if not _in_band(MON[m].get("lv"), _lv_norm)]
if not _cut_band:
    _b2.append(("★ 普通档没有一只因「带外」被剔 —— 等级带那一半没生效（判据可能恒真）", ""))


def _where_of(mid):
    """这只怪出没的站名（探针自己从 monsters.habitat × maps 域算 —— 不看实现体）。"""
    ids = [n for n in ((MON.get(mid) or {}).get("habitat") or {}).get("nodes") or []]
    out = []
    for m, mv in MAPS.items():
        for nd in (mv.get("nodes") or []):
            if nd.get("id") in ids and (m, nd.get("id")) not in out:
                out.append((m, nd.get("id")))
    return [CA._name_of_node(m, n) or n for m, n in out]


for _d in range(1, len(_norm_pool) + 1):
    _at_day(_d)
    _spec = _norm_pool[(_d - 1) % len(_norm_pool)]                  # 探针自己算规格
    _p = _player(level=1, day=_d, flags={"quests_active": ["q_bounty_normal"]})
    _out = _drive(CQ.quest_deliver, _p, "交 101")
    if not any(("还差" in ln) and _mon_name(_spec) in ln for ln in _out):
        _b2.append((("第 %d 日的「还差」没点名 %s" % (_d, _mon_name(_spec))), _out[:4]))
    _want = _where_of(_spec)
    _line = T("SYS_JOB_REQ_MON_WHERE", list=" · ".join(_want)) if _want else ""
    if _want and _line not in [ln.strip() for ln in _out]:
        _b2.append((("第 %d 日没说 %s 出没在哪（该有「%s」）" % (_d, _mon_name(_spec), _line)), _out[:5]))
    if not _want and any("出没在" in ln for ln in _out):
        _b2.append((("第 %d 日没有出没地却硬塞了一行" % _d), _out[:5]))
    for ln in _out:
        if "出没在" in ln and "还差" in ln:
            _b2.append(("新那一行含「还差」——会错位 ㉑/㉛ 的条数对账", ln))
_l2.append("普通档池 %d/%d 只 · 剔掉：%s ｜ 逐日真敲：点名那只 + 出没地那一行都对上了（例：%s → %s）"
           % (len(_norm_pool), len(_norm_ids),
              " · ".join(_mon_name(m) for m in _cut_norm) or "无",
              _mon_name(_norm_pool[-1]), " · ".join(_where_of(_norm_pool[-1]))))
# 反证 ②-a：把 `_habitat_of` 关掉 ⇒ 那一行消失（判据不是恒真）
_keep_hab = CQ._habitat_of
try:
    CQ._habitat_of = (lambda *_a: [])
    _at_day(len(_norm_pool))
    _p = _player(level=1, day=len(_norm_pool), flags={"quests_active": ["q_bounty_normal"]})
    _out = _drive(CQ.quest_deliver, _p, "交 101")
finally:
    CQ._habitat_of = _keep_hab
if any("出没在" in ln for ln in _out) or not any("还差" in ln for ln in _out):
    _b2.append((("反证没生效（关掉出没地还能出那一行 / 拦住都没拦住）"), _out[:4]))
# 反证 ②-b（本波新增）：把可遇性过滤拿掉 ⇒ 池回到全档 ⇒ 逐个游戏日比至少一天点名不同
#   （报告里那一只「野狗」就是这么冒出来的：它在全档里，但按 1 级档在任何一站都挑不出来）
_keep_pool2 = CQ._pool_of
_off = 0
try:
    CQ._pool_of = (lambda role: sorted(k for k, m in MON.items()
                                       if not str(k).startswith("_") and m.get("role_key") == role))
    for _d in range(1, len(_norm_ids) + 1):
        _at_day(_d)
        if CQ._daily_pick("normal", {}) != _norm_pool[(_d - 1) % len(_norm_pool)]:
            _off += 1
finally:
    CQ._pool_of = _keep_pool2
if not _off:
    _b2.append(("★ 反证没生效：拿掉可遇性过滤后逐日比，竟然一天都不差（判据可能恒真）", ""))
if "ms_wild_dog" in CQ._pool_of("normal"):
    _b2.append(("★ 报告里那条：「野狗」还在普通档的池里（1 级档真挑不出来）", "ms_wild_dog"))
# ★ 本波：报告里那两条**原样**钉住 —— 1 级档点到 lv9 石滩螃蟹（knight 第 3 轮 b5）、
#   5 级档点到 lv13 水里的东西（ranger 第 4 轮 b156）—— 两个名字都不许再出现在各自的池里
for _bad_mid, _bad_role, _bad_lv in (("ms_stone_crab", "normal", 9),
                                     ("ms_thing_in_water", "elite", 13)):
    if _bad_mid in CQ._pool_of(_bad_role):
        _b2.append(("★ 病灶那只还在池里：「%s」（lv%d）出现在 %s 档的池里"
                    % (_mon_name(_bad_mid), _bad_lv, _bad_role), _bad_mid))
# 反证 ②-c（本波新增）：把**等级带**拿掉 ⇒ 池回到「只按旧尺子」⇒ 至少有一天点名到**带外**那一只
_keep_pool3 = CQ._pool_of
_off_band = 0
try:
    CQ._pool_of = (lambda role: _pool_spec_no_band(str(role or "")))
    for _d in range(1, len(_norm_ids) + 1):
        _at_day(_d)
        _p3 = CQ._daily_pick("normal", {})
        if _p3 and not _in_band(MON[_p3].get("lv"), _lv_norm):
            _off_band += 1
finally:
    CQ._pool_of = _keep_pool3
if not _off_band:
    _b2.append(("★ 反证 ②-c 没生效：拿掉等级带后逐日比，一天都没点到带外那一只", ""))
(ok if not _b2 else bad)(
    "② 悬赏 101：池按**「可遇 ∩ 等级带」**收窄（普通档 %d/%d 只 · 剔掉 %s）—— 逐日真敲："
    "点名的**那一只**写进「还差」，紧接着一行说它出没在哪几站（站名 = monsters.habitat × maps "
    "现算 · 逐字相同）；池里每一只都在带内 · 报告那两只（石滩螃蟹 lv9 / 水里的东西 lv13）"
    "都不在池里；关掉出没地那一支行立刻消失（反证 a）· 关掉可遇过滤逐日对不上 %d 天（反证 b）· "
    "关掉**等级带** ⇒ 逐日点到带外那一只 %d 天（反证 c · 坏 %s）"
    % (len(_norm_pool), len(_norm_ids), "·".join(_mon_name(m) for m in _cut_norm) or "无",
       _off, _off_band, _b2 or "无"))
for _ln in _l2:
    print("      %s" % _ln)


# ══════════════════════════════════════════════════════════════
# ③ 『提示』随委托走
# ══════════════════════════════════════════════════════════════
_b3, _l3 = [], []
_HINT_TOWN = T("SYS_HINT_TOWN")

# 正例 ③-a：镇上有活、条件没齐 ⇒ 第一行 = 当前委托那一条，后面是同一批「还差」行
_p = _player(level=1, loc=CA.TOWN, node="wt_gate_n",
             flags={"quests_active": ["q_side_13"]})
_out = _drive(CA.hint, _p, "提示")
_want_head = T("SYS_HINT_JOB", name=_q13.get("name"), objective=_q13.get("objective"))
if not _out or _out[0] != _want_head:
    _b3.append(("第一行不是当前委托那一条", _out[:3]))
if _HINT_TOWN in _out:
    _b3.append(("有活时还印着建号那一句（把它换掉才对）", _out[:3]))
_unmet_now = CQ._unmet(_p, _q13)
if [ln for ln in _out[1:] if ln.strip()] != ["  " + ln for ln in _unmet_now] or not _unmet_now:
    _b3.append(("后面那几行不是那一条「还差」的同一批行", _out[:5]))
_l3.append("镇上有活（缺「刻字的石片」）→ %s ｜ 后面 %d 行" % (_out[0] if _out else "?", len(_out) - 1))

# 正例 ③-b：万事俱备 ⇒ 那句「打『交 <编号>』」
_p = _player(level=1, loc=CA.TOWN, node="wt_gate_n", bag={"i_token_stone_shard": 1},
             foot={"nodes": {"belt_north:bn_bone": 1}}, flags={"quests_active": ["q_side_13"]})
_out = _drive(CA.hint, _p, "提示")
if T("SYS_HINT_JOB_READY", order=_q13.get("order")) not in [ln.strip() for ln in _out]:
    _b3.append(("万事俱备那一条没给出「打『交 …』」", _out[:3]))
# 正例 ③-c：手上没活 ⇒ 建号那一句逐字不变
_out = _drive(CA.hint, _player(level=1, loc=CA.TOWN, node="wt_gate_n"), "提示")
if _out != [_HINT_TOWN]:
    _b3.append(("手上没活时镇上那一句变了", _out[:3]))
# 正例 ③-d：野外有活 ⇒ 委托那几行 + 地形那一句（野外的方向句与进度无关，照给）
_p = _player(level=1, loc="belt_north", node="bn_bone", flags={"quests_active": ["q_side_13"]})
_out = _drive(CA.hint, _p, "提示")
if _out[-1] != T("SYS_HINT_WILD") or _out[0] != _want_head:
    _b3.append(("野外有活时那两句的先后不对", _out[:4]))
# 反证 ③-e：把 `_hint_lines` 关掉 ⇒ 退回建号那句（= 报告里那条 bug 的原样）
_keep_hint = CQ._hint_lines
try:
    CQ._hint_lines = (lambda _p: [])
    _out = _drive(CA.hint, _player(level=1, loc=CA.TOWN, node="wt_gate_n",
                                   flags={"quests_active": ["q_side_13"]}), "提示")
finally:
    CQ._hint_lines = _keep_hint
if _out != [_HINT_TOWN]:
    _b3.append(("反证没生效（关掉这一支竟然还随委托走）", _out[:3]))
(ok if not _b3 else bad)(
    "③ 『提示』随委托走（源 04 §一「给一条当前该做什么的提示」）：有活先给那一条 + 同一批"
    "「还差」行 · 万事俱备给「打『交 <编号>』」· 野外再补一句地形 · 手上没活时建号那句一字不变；"
    "关掉这一支立刻退回那句（反证 · 坏 %s）" % (_b3 or "无"))
for _ln in _l3:
    print("      %s" % _ln)

# ══════════════════════════════════════════════════════════════
# ④ 老陶三次各讲一段（不再有「（他没说话。）」）
# ══════════════════════════════════════════════════════════════
_b4, _l4 = [], []
_at_day(1)          # ★ 在场看那根钟（集日会把 NPC 吸走）—— 拨到「第 1 日 · 昼」再搭话
_DLG = str(((NPCS.get("npc_laotao") or {}).get("dialogue")) or "")
_NODES = ((st.domain("dialogues").get(_DLG) or {}).get("nodes") or {})
_SILENT = T("SYS_TALK_SILENT")
_SPOT = ("windmill_town", "wt_shed")

if not _DLG or not _NODES:
    _b4.append(("老陶那棵树取不到", _DLG))
else:
    # 正例 ④-a：真搭话 4 次 —— 一次都不许静默，且 4 次以内听满三段不同的话
    _p = _player(level=9, loc=_SPOT[0], node=_SPOT[1], flags={"card": 1})
    _here = [k for k, _v in CA._npcs_here(_SPOT[0], _SPOT[1], None, _p)]
    if "npc_laotao" not in _here:
        _b4.append(("老陶此刻不在 %s（夹具失效）" % (_SPOT,), _here))
    _bodies, _runs = [], []
    for _i in range(4):
        _out = _drive(CT.talk, _p, "搭话 老陶")
        _runs.append(_out)
        if _SILENT in _out:
            _b4.append(("第 %d 次搭话回了「（他没说话。）」" % (_i + 1), _out[:3]))
        for ln in _out[1:]:
            if not ln.startswith(("✦", "★", "·", "  ")) and ln not in _bodies:
                _bodies.append(ln)
    if len(_bodies) < 3:
        _b4.append(("4 次搭话里只听到 %d 段不同的话（该 ≥ 3）" % len(_bodies), _bodies))
    if CQ._talk_have(_p, "npc_laotao") != 4:
        _b4.append(("计数口径被动过了（flags.talked 该是 4）", CQ._talk_have(_p, "npc_laotao")))
    _l4.append("真搭话 4 次：静默 0 次 · 听到 %d 段不同的话 · flags.talked = %d"
               % (len(_bodies), CQ._talk_have(_p, "npc_laotao")))
    # 正例 ④-b：交 21 照样交得掉（三次那一条的条件与判定没被动过）
    _p2 = _player(level=9, flags={"quests_active": ["q_side_09"],
                                  "talked": {_DLG: 3}})
    _out = _drive(CQ.quest_deliver, _p2, "交 21")
    if not any(ln.startswith(_JOB_DELIVERED) for ln in _out):
        _b4.append(("听够三次却交不掉（计数口径被动了）", _out[:3]))
    # 反证 ④-c：把 daily / main 两层摘掉（= 改前那棵树）⇒ meet 三句听完当场干
    #   ★ 2026-09-30 方案 B 同步：原断言「第 3 次当场静默」的干点随 meet 留窗**后移到听完那刻**
    #     （那正是被方案 B 修掉的 bug 本尊）。反证仍钉「摘层必干」，并加一档 **B 回归哨**：
    #     第 3 次不许干（留窗生效）。确定性 = 反证专用夹具把 meet 的 time-need 桩掉
    #     （测的是层容量，不是 need —— 三句任何时刻都出得来 ⇒ 第 4 次必干，与跑表时辰无关）。
    _keep_data = CT._data

    def _old_data(name, _real=_keep_data, _dlg=_DLG, _nodes=_NODES):
        d = _real(name)
        if name == "dialogues" and _dlg in d:
            d = dict(d)
            _meet = {"texts": [dict(_t, need=None) for _t in _nodes["meet"]["texts"]]}
            d[_dlg] = {"nodes": {"meet": _meet}}
        return d

    try:
        CT._data = _old_data
        _p3 = _player(level=9, loc=_SPOT[0], node=_SPOT[1], flags={"card": 1})
        _r3 = [_drive(CT.talk, _p3, "搭话 老陶") for _i in range(5)]
    finally:
        CT._data = _keep_data
    if not (_SILENT in _r3[3]):
        _b4.append(("反证没生效（摘掉那两层后 meet 三句听完、第 4 次竟然还有话）", _r3[3][:3]))
    if _SILENT in _r3[2]:
        _b4.append(("第 3 次就干了 —— 方案 B 的 meet 留窗没生效（回归哨）", _r3[2][:3]))
    if _SILENT in _r3[0] or _SILENT in _r3[1]:
        _b4.append(("反证那一档的前两次不该静默", _r3[:2]))
(ok if not _b4 else bad)(
    "④ 老陶「听他讲完（三次）」：真搭话 4 次全有话说（静默 0 次）· 4 次内听满 ≥3 段不同的话 · "
    "计数口径与交 21 的判定一个字没动；把那两层临时摘掉 ⇒ 第 3 次当场「（他没说话。）」"
    "（反证 = 报告里那条 bug 的原样 · 坏 %s）" % (_b4 or "无"))
for _ln in _l4:
    print("      %s" % _ln)

# ══════════════════════════════════════════════════════════════
# ⑤ 『我的委托』进度 ＋ `读 <名字>` 对不上时点名
# ══════════════════════════════════════════════════════════════
_b5, _l5 = [], []
_q09 = QE.get("q_side_09") or {}
for _n, _want in ((0, "（0/3）"), (1, "（1/3）"), (3, "（3/3）"), (5, "（3/3）")):
    _p = _player(level=1, flags={"quests_active": ["q_side_09"],
                                 "talked": {_DLG: _n} if _n else {}})
    _out = _drive(CQ.quest_mine, _p, "我的委托")
    _row = next((ln for ln in _out if ln.startswith("· ")), "")
    _tok = T("SYS_MINE_PROGRESS", done=min(_n, 3), n=3)   # ★ 封顶：听够 5 回也只显示 3/3
    if _tok not in _row:
        _b5.append(("听过 %d 回那一档没给进度（该有「%s」）" % (_n, _tok), _row))
# 老条目（没写 require）一个字不多
_p = _player(level=1, flags={"quests_active": ["q_side_10"]})
_out = _drive(CQ.quest_mine, _p, "我的委托")
_row = next((ln for ln in _out if ln.startswith("· ")), "")
if "（0/" in _row or "（1/" in _row:
    _b5.append(("没写 require 的老条目也被塞了进度", _row))
# 反证 ⑤-a：把 `_progress` 关掉 ⇒ 那一格消失
#   ★ fxm3-questsnap：`_progress` 多了一个可选形参（条目 id —— 「接活后新达成」那一把尺子要它）；
#     这条反证钉的仍然是「关掉这一支 ⇒ 那一格消失」，签名跟着改，判据一个字没松。
_keep_prog = CQ._progress
try:
    CQ._progress = (lambda _x, _p, _k=None: "")
    _p = _player(level=1, flags={"quests_active": ["q_side_09"], "talked": {_DLG: 1}})
    _out = _drive(CQ.quest_mine, _p, "我的委托")
finally:
    CQ._progress = _keep_prog
if "（1/3）" in " ".join(_out):
    _b5.append(("反证没生效（关掉这一支还有进度）", _out[:3]))
_l5.append("『我的委托』：听过 0/1/3/5 回 → %s（封顶在需要的数上）"
           % " · ".join(["（%d/3）" % min(_n, 3) for _n in (0, 1, 3, 5)]))

# `读 <名字>` 对不上：点名 + 列出这站能读的（骨田那两件）
_SITE = ("belt_north", "bn_bone")
_at = [(k, v) for k, v in PO.items() if v.get("map") == _SITE[0]
       and v.get("subarea") == _SITE[1] and v.get("read_text")]
_want_names = [(v.get("name")) for _k, v in _at
               if CA._poi_cond(v, _player(level=1, loc=_SITE[0], node=_SITE[1]), None)[0] != "no"]
if len(_want_names) < 2:
    _b5.append(("骨田那两件可读物没凑齐（夹具失效）", [k for k, _v in _at]))
_p = _player(level=1, loc=_SITE[0], node=_SITE[1])
_out = _drive(CA.read_thing, _p, "读 不存在的东西")
if T("SYS_READ_NOSUCH", name="不存在的东西") not in _out:
    _b5.append(("名字对不上时没点名说对不上", _out[:3]))
if T("SYS_READ_HERE", list=" · ".join(_want_names)) not in _out:
    _b5.append(("没把这站能读的列出来（该有「%s」）"
                % T("SYS_READ_HERE", list=" · ".join(_want_names)), _out[:3]))
if T("SYS_READ_NONE") in _out:
    _b5.append(("名字对不上时仍回「这里没有能读的东西」（玩家会以为这站本来就没东西）", _out[:3]))
# 对的名字照旧给正文（老路一个字不动）
_k0, _v0 = _at[0]
_out = _drive(CA.read_thing, _player(level=1, loc=_SITE[0], node=_SITE[1]), "读 %s" % _v0.get("name"))
if T(_v0["read_text"]) not in _out:
    _b5.append(("对的名字反倒不给正文了", _out[:3]))
# 空参：只有一件时照旧直接给（老路不变）；这站有多件 ⇒ 仍给第一条（逐字不变）
_out = _drive(CA.read_thing, _player(level=1, loc=_SITE[0], node=_SITE[1]), "读")
if T(_v0["read_text"]) not in _out or T("SYS_READ_NOSUCH", name="") in _out:
    _b5.append(("空参那条路被动过了", _out[:3]))
# 这站真没有可读物 ⇒ 照旧「这里没有能读的东西」（两态）
_with_read = {(v.get("map"), v.get("subarea")) for v in PO.values()
              if v.get("map") and v.get("read_text")}
_empty = next(((m, nd["id"]) for m, mv in MAPS.items() for nd in (mv.get("nodes") or [])
               if (m, nd.get("id")) not in _with_read), (CA.TOWN, "wt_gate_n"))
_out = _drive(CA.read_thing, _player(level=1, loc=_empty[0], node=_empty[1]), "读 随便什么")
if T("SYS_READ_NONE") not in _out:
    _b5.append(("这站一件可读物都没有时，反倒不回「这里没有能读的东西」", _out[:3]))
_l5.append("骨田 `读 不存在的东西` → 「%s」/「%s」"
           % (T("SYS_READ_NOSUCH", name="不存在的东西"),
              T("SYS_READ_HERE", list=" · ".join(_want_names))))
(ok if not _b5 else bad)(
    "⑤ 『我的委托』给进度（同一个判定 `_req_ok` 数出来 · 老条目不多一个字）＋ `读 <名字>` 对不上时"
    "点名说对不上并列这站能读的（空参 / 对的名字 / 这站没读物三条老路都照旧 · 反证 1 条 · 坏 %s）"
    % (_b5 or "无"))
for _ln in _l5:
    print("      %s" % _ln)

# ══════════════════════════════════════════════════════════════
# ⑥ 主线 1「试着读（读不懂）」与『读』当场给的正文对上
# ══════════════════════════════════════════════════════════════
_b6, _l6 = [], []
_DOC24 = os.path.join(PLAN, "06_第一阶段垂直切片", "24_任务线_v1.md")
_doc = io.open(_DOC24, encoding="utf-8", newline="").read() if os.path.exists(_DOC24) else ""
_q1 = QE.get("q_main_01") or {}
_obj = str(_q1.get("objective") or "")
if "试着读（读不懂）" not in _obj:
    _b6.append(("main1 的 objective 不再带真源那一步：%s" % _obj))
if "试着读（读不懂）" not in _doc:
    _b6.append(("24 §一 主 1 的「步骤」行里也找不到那一步（真源变了？先裁决）"))
_poi = PO.get("poi_stone_scripts") or {}
_p = _player(level=1, loc=str(_poi.get("map") or "windmill_town"),
             node=str(_poi.get("subarea") or "wt_gate_n"))
_out = _drive(CA.read_thing, _p, "读")
_body = T(str(_poi.get("read_text") or ""))
if _body not in _out:
    _b6.append(("镇口那块石头的正文取不到", _out[:3]))
if "一个也读不出来" not in _body:
    _b6.append(("正文没把「读不懂」落到屏幕上（两边又打架）", _body))
if T("SYS_READ_NONE") in _out:
    _b6.append(("镇口这块石头竟然回「没有能读的东西」", _out[:3]))
_l6.append("main1 objective：「%s」" % _obj)
_l6.append("镇口『读』的正文（尾句）：「%s」" % _body[-24:])
(ok if not _b6 else bad)(
    "⑥ 主线 1：objective 照真源 `24 §一` 主 1「步骤」行一个字不动（含「试着读（读不懂）」）· "
    "镇口那块石头的正文把「读不懂」落在屏幕上（源 02 §一「我不认得」）—— 两边不再打架"
    "（反证 = 把那句拆掉当场红 · 坏 %s）" % (_b6 or "无"))
for _ln in _l6:
    print("      %s" % _ln)

FC.bind_host(**_FC_SAVED)                                            # ★ 拨回真钟

# ══════════════════════════════════════════════════════════════
# ⑦ ★ g3-quests2：支线「还石头」—— **接活那一下真发东西**（`quests.<id>.give`）
#   改前：`17 §QUEST_SIDE25_STORY` 写「**小满把那块石头塞给你** —— 它该回到缺着它的那块碑上去。」
#     而 `接 25` **一个东西都不发**（玩家只能自己跑去骨田挖 30% 的 `unid_rare`）⇒ 那句话是空话。
#   真源：`00_总纲/15_彩蛋域口径_v1.md §二` 第 2 行（彩蛋 2；依据栏自己写着「q_side_13「还石头」
#     的交待就是彩蛋 2，**小满的石头 = 骨田捡的刻字石片**」）＋ `17 §QUEST_SIDE25_STORY`。
#   判据（探针自己不抄实现）：
#     ① 域里 `q_side_13.give` == 15 §二 那一行 `hold=` 那件东西（文档现解析）
#     ② 真敲 `接 25` ⇒ 包里真多出那一件 + 屏上有 `SYS_JOB_GIVE` 那一行 + 档上写 `quests_active`
#     ③ 别的条目一个字没变：域里只有那一条带 `give`（没写的条目接活不发东西）
#     ④ **反证**：进程内把 `give` 拿掉（= 改前）⇒ 一个东西都不发、那一行也不出现
# ══════════════════════════════════════════════════════════════
import re as _re7                                                        # noqa: E402

_b7, _l7 = [], []
_DOC15 = os.path.join(PLAN, "00_总纲", "15_彩蛋域口径_v1.md")
_D15 = io.open(_DOC15, encoding="utf-8", newline="").read() if os.path.exists(_DOC15) else ""
_hold15 = ""
for _ln15 in _D15.split("\n"):
    _c = [x.strip() for x in _ln15.split("|")]
    if len(_c) < 5 or "q_side_13" not in _ln15 or "的交待就是彩蛋" not in _ln15:
        continue
    for _cl in _c[3].split("&"):
        _cl = _cl.strip()
        if _cl.startswith("hold="):
            _hold15 = _cl.split("=", 1)[1].strip()
if not _hold15:
    _b7.append(("15 §二 里解析不出 q_side_13 那一行的 hold= 那件东西", ""))
_q13 = QE.get("q_side_13") or {}
_want_give = [{"item": _hold15, "n": 1}] if _hold15 else []
if list(_q13.get("give") or []) != _want_give:
    _b7.append(("q_side_13.give = %s ≠ 15 §二 那一行 hold= 的 %s（两处口径）"
                % (_q13.get("give"), _want_give), ""))
_givers = sorted(k for k, v in QE.items() if v.get("give"))
if _givers != ["q_side_13"]:
    _b7.append(("带 `give` 的条目 = %s（今天只该有「还石头」一条 —— 多一条就是新开的形状没人裁）"
                % _givers, ""))
# ② 真敲「接 25」
_p0 = _player(level=1, flags={"card": 1})
_o0 = _drive(CQ.quest_accept, _p0, "接 25")
_rec = LT.rec_of(_hold15) if _hold15 else {}
_want_line = T("SYS_JOB_GIVE", icon=_rec.get("icon", "·"), name=_rec.get("name", _hold15), n=1)
if int((_p0.get("bag") or {}).get(_hold15) or 0) != 1:
    _b7.append(("接 25 之后包里没有那一件：bag=%s" % (_p0.get("bag"),), _o0[:4]))
if _want_line not in _o0:
    _b7.append(("接 25 的屏上没有那一行「%s」" % _want_line, _o0[:4]))
if "q_side_13" not in ((_p0.get("flags") or {}).get("quests_active") or []):
    _b7.append(("接 25 没落档", _p0.get("flags")))
_l7.append("接 25 ⇒ 「%s」｜ 包里 %s" % (_want_line, _p0.get("bag")))
# ④ 反证：把 `give` 拿掉（= 改前那一版）⇒ 一个东西都不发、那一行也不出现
_p1 = _player(level=1, flags={"card": 1})
_keep_q7 = CQ._quests
try:
    CQ._quests = (lambda: {k: ({kk: vv for kk, vv in v.items() if kk != "give"} if k == "q_side_13" else v)
                           for k, v in _keep_q7().items()})
    _o1 = _drive(CQ.quest_accept, _p1, "接 25")
finally:
    CQ._quests = _keep_q7
if (_p1.get("bag") or {}) or any("得到" in ln for ln in _o1):
    _b7.append(("★ 反证没生效（把 give 拿掉之后竟然还发了东西）", _o1[:4]))
_l7.append("反证（拿掉 give）：包里 %s · 屏上 %s（= 改前那一版：一个东西都不发）"
           % (_p1.get("bag") or "空", "没那行" if not any("得到" in ln for ln in _o1) else _o1[:2]))
(ok if not _b7 else bad)(
    "⑦ 支线「还石头」接活**真发东西**（源 15 §二 彩蛋 2 那一行 `hold=` ＋ `17 §QUEST_SIDE25_STORY`"
    "「小满把那块石头塞给你」）：域里 give == 文档现解析 · 真敲接 25 ⇒ 包里有那件 + 屏上「%s」"
    "· 只有这一条带 give · 反证拿掉 give ⇒ 一个东西都不发（坏 %s）"
    % (_want_line, _b7 or "无"))
for _ln in _l7:
    print("      %s" % _ln)

# ══════════════════════════════════════════════════════════════
# ⑧ ★ g3-quests2：对话旗标族（`main*_done` / `main*_active` / `quest_*_done` / `nameline_done`）
#   改前：那一族 slug 只有**读端**（`cmds_talk._pick_indexed` 的 `flag` 那一支）、**全仓没有写端**
#     ⇒ dialogues 域里 12 条台词（哈根 meet 三段 · 格雷/娜娜/贝拉/德里克/莉安/杜林/玛莎 的 main 层 ·
#       小满 daily · 艾德 hidden · 哈根 hidden）永久出不来（`grep` 零命中）。
#   落法：读端 = `content/prog.flag_ok`（那一族**以真实进度为准**）· 写端 = `content/prog.resync`
#     （接 / 交 / 放弃那三处照真实进度重写那一格）。
#   判据（两边都判）：
#     ① 域里用到的 slug **一个都不许落空**（`PROG.audit()` 空表）· 每条的 slug→委托映射现算得出 ·
#        映射到的委托真在域里 · 写端真存在（静态守卫：`prog.resync` 在 `cmds_quest` 里被调 ≥3 处）
#     ② 写端三拍：接 9 ⇒ `main09_active` 写 True ｜ 交 9 ⇒ `main09_active` 写回 False 且
#        `main09_done` True ｜ 放弃 9 ⇒ `main09_active` 写回 False（档上不留幽灵旗标）
#     ③ 读端真搭话（柯尔 · 熟了 · 手上有那块旧铁）：主 4 交掉 ⇒ 出的是「这不是这地方的铁」那一段
#     ④ 反证 a：**没做到** ⇒ 那一格没写、那一句**真搭话出不来**（出的是 daily 兜底那一段）
#     ⑤ 反证 b：只手塞一个**脏旗标**（`main04_done=True` 而进度不成立）⇒ 那一句**照样出不来**
#        （fail-closed：脏旗标不许把台词刷出来）
#     ⑥ 表外 token 照旧：`card` 那种走老口径（读那一格本身 —— 一个字没变）
# ══════════════════════════════════════════════════════════════
_b8, _l8 = [], []
_slugs = PROG.domain_slugs()
if not _slugs or PROG.audit():
    _b8.append(("域里用到的 flag slug = %s，认不出的 %s" % (_slugs, PROG.audit()), ""))
for _s in _slugs:
    _mp = PROG.map_slug(_s)
    if not _mp or _mp[0] not in QE or not PROG.why_of(_s):
        _b8.append(("slug %s 的映射/依据不完整：%s / %s" % (_s, _mp, PROG.why_of(_s)), ""))
# 写端真存在（静态守卫：那一族在 content 侧真有人写 —— 不是「只有读端」）
_src_cq8 = io.open(os.path.join(REPO, "content", "cmds_quest.py"), encoding="utf-8").read()
_n_write8 = _src_cq8.count("PROG.resync(")
_src_pr8 = io.open(os.path.join(REPO, "content", "prog.py"), encoding="utf-8").read()
if _n_write8 < 3 or "def resync(" not in _src_pr8:
    _b8.append(("写端不在了：prog.resync 在 cmds_quest 里被调 %d 处（接/交/放弃三处都要）" % _n_write8, ""))
# ② 写端三拍（真敲）
_pa = _player(level=20, flags={"card": 1})
_drive(CQ.quest_accept, _pa, "接 9")
if (_pa.get("flags") or {}).get("main09_active") is not True:
    _b8.append(("接 9 后 main09_active = %s（该写 True）" % (_pa.get("flags") or {}).get("main09_active"),
                _pa.get("flags")))
_pb = _player(level=20, flags={"card": 1, "quests_active": ["q_main_09"],
                               "talked": {CQ._dlg_of("npc_grey"): 1}, "main09_active": True})
_drive(CQ.quest_deliver, _pb, "交 9")
_fb = _pb.get("flags") or {}
if _fb.get("main09_done") is not True or _fb.get("main09_active") is not False:
    _b8.append(("交 9 后那一族不对：main09_done=%s · main09_active=%s"
                % (_fb.get("main09_done"), _fb.get("main09_active")), _fb))
_at_day(6)                                                # 放弃的冷却看那根钟 ⇒ 造「第 6 日」
_pc = _player(level=20, flags={"card": 1, "quests_active": ["q_main_09"], "main09_active": True})
_drive(CQ.quest_abandon, _pc, "放弃 9")
if (_pc.get("flags") or {}).get("main09_active") is not False:
    _b8.append(("放弃 9 后 main09_active = %s（该写回 False）" % (_pc.get("flags") or {}).get("main09_active"),
                _pc.get("flags")))
_l8.append("写端三拍：接 9 ⇒ main09_active=True ｜ 交 9 ⇒ done=True/active=False ｜ 放弃 9 ⇒ active=False")
# ③④⑤ 读端真搭话（柯尔：熟了 + 主 4 交掉 / 没交 / 只有脏旗标）
_SPOT8 = ("windmill_town", "wt_forge")
_DLG8 = str((NPCS.get("npc_cole") or {}).get("dialogue") or "")


def _cole(flags):
    return _player(level=9, loc=_SPOT8[0], node=_SPOT8[1],
                   flags=dict({"card": 1, "talked": {_DLG8: 3}}, **flags),
                   # ★ 2026-09-30 方案 B 同步：熟档夹具把 meet 三句**都标听过** —— 真实走过
                   #   见面期的档就是这样；原夹具 talked=3 却 heard 空 = 不可能态，方案 B 下
                   #   meet（头句没记）会回抢头名、把 daily 的旗标句压住（③④⑤ 三条一起偏）。
                   heard={_DLG8: {"meet#0": 1, "meet#1": 1, "meet#2": 1}})


def _pick8(flags):
    return CT._pick_layer((CT._data("dialogues").get(_DLG8) or {}).get("nodes") or {},
                          _cole(flags), CAL.state(), _DLG8)


_WITH = _pick8({"quests_done": ["q_main_04"]})              # ③ 真进度
_NONE8 = _pick8({})                                          # ④ 没做到
_DIRTY = _pick8({"main04_done": True})                       # ⑤ 脏旗标（进度不成立）
if _WITH[0] != "daily" or "这不是这地方的铁" not in str(_WITH[2] or ""):
    _b8.append(("③ 主 4 交掉之后，柯尔那一句没出（拿到的是 %s）" % (_WITH,), ""))
if "这不是这地方的铁" in str(_NONE8[2] or ""):
    _b8.append(("④ 没做到竟然也出了那一句（提前刷台词）%s" % (_NONE8,), ""))
if "这不是这地方的铁" in str(_DIRTY[2] or ""):
    _b8.append(("⑤ 只塞一个脏旗标就把那一句刷出来了（fail-closed 破了）%s" % (_DIRTY,), ""))
if _NONE8[2] != _DIRTY[2]:
    _b8.append(("⑤ 脏旗标那一档与「什么都没做」那一档竟然不一样：%s vs %s" % (_DIRTY, _NONE8), ""))
_l8.append("读端（柯尔 · 熟了）：主 4 交掉 ⇒ 出「这不是这地方的铁…」｜ 没做 ⇒ 兜底那一句｜ "
           "只手塞脏旗标 ⇒ 与「没做」逐字相同（都不出）")
# 真搭话一遍（把「读端」也真敲一次 —— 不是只调 `_pick_layer`）
_at_day(2)
_o8 = _drive(CT.talk, _cole({"quests_done": ["q_main_04"]}), "搭话 柯尔")
if not any("这不是这地方的铁" in ln for ln in _o8):
    _b8.append(("真搭话那一趟没出那一句：%s" % (_o8[:4],), ""))
# ⑥ 表外 token 照旧
if PROG.flag_ok({"flags": {"card": 1}}, "card") is not True \
        or PROG.flag_ok({"flags": {}}, "card") is not False \
        or PROG.flag_ok({"flags": {"lore_scripts": True}}, "lore_scripts") is not True:
    _b8.append(("表外 token 的老口径被动过了（card / lore_scripts）", ""))
_l8.append("域里 %d 条 slug 全部接上真实进度（0 条落空）：%s"
           % (len(_slugs), " · ".join(PROG.why_of(_s) for _s in sorted(_slugs))))
_l8.append("表外 token（card / lore_scripts）照旧：走老口径读那一格本身")
(ok if not _b8 else bad)(
    "⑧ 对话旗标族**写端**（改前：只有读端、全仓没有写端 ⇒ 12 条台词永久出不来）："
    "域里 %d 条 slug 全接上真实进度 · 写端三拍（接/交/放弃）· 读端真搭话 · 两条反证"
    "（没做到 ⇒ 不出 ｜ 脏旗标 ⇒ 照样不出）· 表外 token 照旧（坏 %s）" % (len(_slugs), _b8 or "无"))
for _ln in _l8:
    print("      %s" % _ln)
FC.bind_host(**_FC_SAVED)

print()
print("判据 %d 条：%s" % (CHECKS[0], "全绿 ✓" if not fails else "有红 ✗（%d 条）" % len(fails)))
sys.exit(1 if fails else 0)
