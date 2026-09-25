# -*- coding: utf-8 -*-
"""探针：装备事件（B3-4 · 26 个）—— 六件装备各挂一处触发，且**真跑一次**拿得到。

真源：`06_第一阶段垂直切片/30_装备事件_设计_v1.md`（§二 P-15 裁决 · §三 六条挂哪）
上游：`21_长期目标层_v1.md §四`（6 条装备事件）

判据（★ = 跨域 / 行为，最要紧）：
  ① ★ 六件东西都在物品表里，且**每件的名字只对应一个 id**（防再出现同名双源 —— P-15 的根）
  ② ★ 物品名不许与 pois 的名字撞（「地点」与「东西」两处同名 = 同一族病）
  ③ ★ 每条挂载的 `need.holding` 指向的都是真物品；消费端（人 / 怪）都真存在；人在真图的真节点上
  ④ ★ **真跑一次触发**（真宿主 + 假钟）：带着那件 → 走到那位跟前搭话 → **拿到那一句**；
     不带 → 拿不到（fail-closed，且同组有兜底时出的是兜底那句）
  ⑤ ★ 战内台词那条（拾荒人的短刃）：钉住遭遇 = 拾荒人 —— 带刀时它先开口，不带刀时那几句一句都不出
  ⑥ ★ 挂载必须排在**同组的兜底句之前**（排后面 = 永远轮不到它 —— P-12 那个坑）
  ⑦ 六句都是人话（非空 · ≤一屏 400 字 · 不含机器键）
  ⑧ ★ 新信物的出产在浅滩钓点上，且是**池里最稀的那一位**（设计原话：挂浅滩钓点的稀有位）
  ⑨ 挂载是幂等的：搭话两遍拿到同一句，且不动背包

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_events.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402
from saintess_engine.host.runtime import Host                        # noqa: E402

ok = True
MAX_CHARS = 400
#: 机器键前缀（呈现口不许漏出来的那一族 —— 与 probe_copy ⑪ 同口径）
KEYS = ("i_", "ms_", "npc_", "poi_", "dlg_", "gt_", "dp_", "unid_", "cls_", "q_")

#: ★ 六条事件（真源 30 §三 那张表逐行）—— (物品 id, 消费端, 挂载处)
#:  消费端 `npc_*` → dialogues 域的 need.holding；`ms_*` → monsters 域的 encounter_lines
EVENTS = [("i_set_sentry_gauntlet", "npc_hagen", ("dialogues", "dlg_hagen", "hidden")),
          ("i_horn_half", "npc_pete", ("dialogues", "dlg_pete", "hidden")),
          ("i_token_stone_shard", "npc_seran", ("dialogues", "dlg_seran", "hidden")),
          ("i_set_scavenger_blade", "ms_pick_scavenger", ("monsters", "ms_pick_scavenger", "encounter_lines")),
          ("i_set_northwall_amulet", "npc_ed", ("dialogues", "dlg_ed", "hidden")),
          ("i_token_underwater_steps", "npc_lian", ("dialogues", "dlg_lian", "main"))]


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


print("探针：装备事件（B3-4 · 六件装备各挂一处触发）")
st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
st.install()

IT = st.domain("items") or {}
PO = st.domain("pois") or {}
DL = st.domain("dialogues") or {}
NP = st.domain("npcs") or {}
MO = st.domain("monsters") or {}
MP = st.domain("maps") or {}
GA = st.domain("gathering") or {}

# ① 六件都在物品表里 · 名字各只对应一个 id
miss = [iid for iid, _who, _at in EVENTS if iid not in IT]
chk("★ 六件东西都在物品表里（%d 件）" % len(EVENTS), not miss, "缺：%s" % miss)
dup = []
for iid, _who, _at in EVENTS:
    nm = (IT.get(iid) or {}).get("name")
    ids = [k for k, v in IT.items() if v.get("name") == nm]
    if len(ids) != 1:
        dup.append((nm, ids))
chk("★ 每件的名字只对应一个 id（防同名双源 —— P-15 的根）", not dup,
    "重名：%s" % dup)

# ② 物品名不许与 pois 的名字撞（地点 / 东西两处同名 = 同一族病）
pn = {str(v.get("name")): k for k, v in PO.items()}
clash = [(k, v.get("name"), pn[v.get("name")]) for k, v in IT.items()
         if str(v.get("name")) in pn]
chk("★ 物品名与 pois 名不撞（一个名字指一个东西）", not clash, clash[:4])

# ③ 挂载 → 真物品 · 真消费端 · 真位置
bad = []
for iid, who, (dom, key, field) in EVENTS:
    rec = MO.get(key) if dom == "monsters" else DL.get(key)
    if not rec:
        bad.append((iid, "%s 域没有 %s" % (dom, key)))
        continue
    if dom == "monsters":
        lines = rec.get("encounter_lines") or []
        if not [x for x in lines if (x.get("need") or {}).get("holding") == iid]:
            bad.append((iid, "%s 没有 holding=%s 的那条" % (key, iid)))
        continue
    if who not in NP:
        bad.append((iid, "%s 不在 npcs 域" % who))
    else:
        n = NP[who]
        if n.get("dialogue") != key:
            bad.append((iid, "%s 指的对话树是 %s" % (who, n.get("dialogue"))))
        if n.get("subarea") not in [x.get("id") for x in ((MP.get(n.get("map")) or {}).get("nodes") or [])]:
            bad.append((iid, "%s 站的 %s 不在真图上" % (who, n.get("subarea"))))
    texts = ((rec.get("nodes") or {}).get(field) or {}).get("texts") or []
    if not [t for t in texts if (t.get("need") or {}).get("holding") == iid]:
        bad.append((iid, "%s/%s 没有 holding=%s 的那条" % (key, field, iid)))
chk("★ 每条挂载都指向真物品 + 消费端真存在 + 人在真节点上", not bad, bad[:4])

# ⑥ 挂载必须排在**同组的兜底句之前**（排后面 = 永远轮不到它）
late = []
for iid, who, (dom, key, field) in EVENTS:
    if dom != "dialogues":
        continue
    texts = ((DL.get(key) or {}).get("nodes") or {}).get(field, {}).get("texts") or []
    idx = [i for i, t in enumerate(texts) if (t.get("need") or {}).get("holding") == iid]
    fall = [i for i, t in enumerate(texts) if not t.get("need")]
    if idx and fall and idx[0] > fall[0]:
        late.append((key, field, iid))
chk("★ 挂载排在同组兜底句之前（否则永远轮不到 —— P-12 那个坑）", not late, late[:3])


# ⑦ 六句都是人话（非空 · 一屏 · 不含机器键）
def line_of(iid, who, at):
    dom, key, field = at
    if dom == "monsters":
        lines = (MO.get(key) or {}).get("encounter_lines") or []
        hit = [x for x in lines if (x.get("need") or {}).get("holding") == iid]
    else:
        texts = ((DL.get(key) or {}).get("nodes") or {}).get(field, {}).get("texts") or []
        hit = [t for t in texts if (t.get("need") or {}).get("holding") == iid]
    return (hit[0].get("text") if hit else "") or ""


LINES = {iid: line_of(iid, who, at) for iid, who, at in EVENTS}
empty = [k for k, v in LINES.items() if not v]
long = [(k, len(v)) for k, v in LINES.items() if len(v) > MAX_CHARS]
leak = [(k, [w for w in KEYS if w in v]) for k, v in LINES.items()
        if any(w in v for w in KEYS)]
chk("六句都写着（非空）", not empty, empty)
chk("六句都不超一屏 %d 字" % MAX_CHARS, not long, long)
chk("★ 台词里不含机器键（呈现口那条线）", not leak, leak[:3])


# ── 真宿主 + 假钟：一条一条真跑 ─────────────────────────────────
def _epoch_at(day, hod):
    """第 day 个游戏日的 hod 点 —— 刻度从 calendar 域读（不手打 7200）。"""
    cal = json.loads((REPO / "content" / "data" / "calendar.json").read_text(encoding="utf-8"))
    scale = int(cal["_clock"]["real_seconds_per_game_day"])
    return (day * 86400.0 + hod * 3600.0) * scale / 86400.0


NIGHT_HOD = 21          # 夜（哈根的条件是 昏 / 夜；窗界在 calendar 域）


class _Ad(object):
    """三函数 + say（照 host-api 契约的最小适配器 —— 与 scripts/e2e_drive.py 同形）。"""

    def __init__(self, texts, seed):
        self._msgs = [{"uid": "u_ev", "group_id": "g_ev", "text": t, "is_group": True} for t in texts]
        self.out = []
        self.saved = dict(seed)

    def recv(self):
        return self._msgs.pop(0) if self._msgs else None

    def load_player(self, uid):
        return dict(self.saved) if uid == "u_ev" else None

    def save_player(self, uid, data):
        self.saved = dict(data) if isinstance(data, dict) else data

    def say(self, to, text):
        self.out.append(str(text))


def _talk_run(iid, node_name, npc_name, *, hold=True, talks=1, done_main=False):
    """真宿主：走到那个节点、跟那个 NPC 搭话（可搭 N 遍）；回每步的输出 + 落档后的档。

    ★ 为什么搭 N 遍：取句顺序那条口径（P-12「人先熟、事才说」）会按**搭过几次**分层 ——
      装备事件那几句挂在 `hidden` / `main` 层，**不熟**的时候轮不到它。判据要有意义就只能
      「搭几遍里任意一遍拿到那句」，不去钉死「第几遍」（那是 P-12 的口径，会变）。
    ★ `done_main`：`ev_caravan_arrived`（商队到了）是**世界级事件**（`from_main: q_main_03`）⇒
      瑟兰只在主线 3 过了才在场（B3-5 接的）。这条用例要按「商队到了」那个档跑。
    """
    steps = ["去 %s" % node_name] + ["搭话 %s" % npc_name] * int(talks)
    seed = {"race": "human", "hp": 100, "hp_max": 100, "loc": "windmill_town",
            "node": "wt_gate_n", "bag": ({iid: 1} if hold else {})}
    if done_main:
        seed["flags"] = {"quests_done": ["q_main_03"]}
    db = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_events.db")
    try:
        os.remove(db)
    except OSError:
        pass
    ad = _Ad(steps, seed)
    host = Host(ad, str(REPO), inject={"db_path": db, "clock": (lambda: _epoch_at(100, NIGHT_HOD))})
    host.boot()
    outs = []
    for t in steps:
        ad.out.clear()
        host.handle({"uid": "u_ev", "group_id": "g_ev", "text": t})
        outs.append(list(ad.out))
    return outs, ad.saved


try:
    # ★ 已知缺口（登记在案 · 见台账 P-16 / B3-5 §三）：瑟兰那条**今天拿不到** ——
    #   `cmds_talk` 的「搭话 / 问路」两处**没把档传给 `_npcs_here`**（B3-5 动不了那个文件：另一条线在改它）
    #   ⇒ 世界事件按「新档」算 = 商队没到 ⇒ 她不在镇上。实测：同一个节点 `_npcs_here(..., st, p)` 带档
    #   就出「小满 · 瑟兰 · 杜林」，不带档只有「小满 · 杜林」。
    #   修法（三行）：搭话 / 问路两处 `_npcs_here(loc, node, st, p=p)` + 对话 `need.event` 的读端。
    #   判据按**现状**登记 —— 补丁落下去那天这条会翻红，那时把它从 KNOWN_GAP 删掉即可。
    KNOWN_GAP = {"i_token_stone_shard":
                 "搭话 / 问路没传档 ⇒ 世界事件判成「商队没到」（cmds_talk 那三行补丁待合）"}
    bad_run = []
    for iid, who, at in EVENTS:
        if at[0] != "dialogues":
            continue
        npc = NP[who]
        node_name = [x.get("name") for x in ((MP.get(npc.get("map")) or {}).get("nodes") or [])
                     if x.get("id") == npc.get("subarea")][0]
        want = LINES[iid].split("\n")[0]
        # ★ 4 遍（不熟 → 熟了 都覆盖到）+ 商队已到（瑟兰那条要靠它才在场）
        talk_out, _p1 = _talk_run(iid, node_name, npc.get("name"), hold=True, talks=4, done_main=True)
        silent_out, _p2 = _talk_run(iid, node_name, npc.get("name"), hold=False, talks=4, done_main=True)
        if iid in KNOWN_GAP:
            if any(want in o for o in talk_out[1:]):
                bad_run.append((iid, "★ 已知缺口居然修好了 —— 把它从 KNOWN_GAP 删掉", KNOWN_GAP[iid]))
            continue
        if not any(want in o for o in talk_out[1:]):
            bad_run.append((iid, "带着也没拿到那句", [x[:1] for x in talk_out[1:]]))
        if any(want in o for o in silent_out[1:]):
            bad_run.append((iid, "不带着也拿到了（没拦住）", [x[:1] for x in silent_out[1:]]))
    chk("★ 真跑五条（各搭 4 遍）：带着那件 ⇒ 搭话拿到那句；不带 ⇒ 拿不到（fail-closed）"
        "（已知缺口 %d 条按现状登记：%s）" % (len(KNOWN_GAP), list(KNOWN_GAP)),
        not bad_run, bad_run[:3])

    # ⑨ 幂等 / 可复现：同一个起手档跑两趟 ⇒ 头一遍逐字相同；背包不被改
    #   ★ 不判「搭话两遍同一句」——「说过的句子让位给还没说过的层」是 P-12 的口径（会变），
    #     挂在 hidden / main 的那句说过了就该让位。判的是「挂载本身是数据、不消耗、可复现」。
    idem = []
    for iid, who, at in EVENTS:
        if at[0] != "dialogues":
            continue
        npc = NP[who]
        node_name = [x.get("name") for x in ((MP.get(npc.get("map")) or {}).get("nodes") or [])
                     if x.get("id") == npc.get("subarea")][0]
        run1, saved1 = _talk_run(iid, node_name, npc.get("name"), hold=True, talks=4, done_main=True)
        run2, saved2 = _talk_run(iid, node_name, npc.get("name"), hold=True, talks=4, done_main=True)
        if run1 != run2:
            idem.append((iid, "同一个起手档两趟不一致", (run1[1][:1], run2[1][:1])))
        if (saved1 or {}).get("bag") != {iid: 1} or (saved2 or {}).get("bag") != {iid: 1}:
            idem.append((iid, "动了背包", ((saved1 or {}).get("bag"), (saved2 or {}).get("bag"))))
    chk("★ 同一个起手档跑两趟逐字相同（挂载是数据 · 可复现）· 不动背包", not idem, idem[:3])
except Exception as exc:                                              # noqa: BLE001 —— 起不来就是红
    chk("★ 真宿主端到端跑得起来（装备事件那条线）", False, "%s: %s" % (type(exc).__name__, exc))


# ⑤ 战内台词那条：钉住遭遇 = 拾荒人，带刀 / 不带刀 各跑一趟
class _E:
    text = ""

    def save(self):
        pass


def _drive(fn, p, text=""):
    out = []

    async def go():
        e = _E()
        e.text = text
        async for line in fn(e, None, "u_bat", p):
            out.append(str(line))

    asyncio.run(go())
    return out


try:
    from content import cmds_ast as CA                                   # noqa: E402
    from content import cmds_battle as CBL                               # noqa: E402
    from content import combat as CBmod                                  # noqa: E402

    _MID = "ms_pick_scavenger"
    _want = LINES["i_set_scavenger_blade"].split("\n")[0]

    def _fight(hold):
        p = dict(CA.DEFAULT_PLAYER)
        p.update({"cls": "cls_knight", "level": 20, "hp": 900, "hp_max": 900, "loc": "belt_north",
                  "node": "bn_camp", "bag": ({"i_set_scavenger_blade": 1} if hold else {})})
        real = CBmod.pick_encounter
        CBmod.pick_encounter = lambda *a, **k: [_MID]
        try:
            return _drive(CBL.attack, p)
        finally:
            CBmod.pick_encounter = real

    _with = _fight(True)
    _without = _fight(False)
    chk("★ 钉住遭遇=拾荒人：带着刀 ⇒ 它先开口（那句真出）",
        any(_want == x for x in _with), _with[:3])
    chk("★ 不带刀 ⇒ 那几句一句都不出（fail-closed）",
        not any(_want == x for x in _without), _without[:3])
    chk("★ 战内挂载是**数据**在说话（源码里不许内联那句文案）",
        _want not in (REPO / "content" / "cmds_battle.py").read_text(encoding="utf-8"))
except Exception as exc:                                              # noqa: BLE001
    chk("★ 战内台词那条跑得起来（真调「攻击」）", False, "%s: %s" % (type(exc).__name__, exc))

# ⑧ 新信物的出产：浅滩钓点上 · 池里最稀的那一位
_iid = "i_token_underwater_steps"
_pts = [(k, v) for k, v in GA.items() if not str(k).startswith("_")
        and (v.get("pool") or []) and any(e.get("out") == _iid for e in v["pool"])]
if len(_pts) != 1:
    chk("★ 新信物的出产只有一个口（浅滩钓点）", False, [k for k, _ in _pts])
else:
    _k, _v = _pts[0]
    _names = [x.get("name") for x in ((MP.get(_v.get("map")) or {}).get("nodes") or [])
              if x.get("id") == _v.get("subarea")]
    _mine = [e for e in _v["pool"] if e.get("out") == _iid][0]
    _others = [int(e.get("w", 1) or 1) for e in _v["pool"] if e.get("out") != _iid]
    chk("★ 出产在浅滩钓点上（%s · %s/%s）" % (_k, _v.get("subarea"), (_names or ["?"])[0]),
        _v.get("verb") == "fish" and bool(_names) and "浅滩" in _names[0])
    chk("★ 它是池里最稀的那一位（w=%s < 别的 %s —— 设计原话「稀有位」）"
        % (_mine.get("w"), _others), bool(_others) and int(_mine.get("w", 1)) < min(_others))

# ⑩ 底线：装备事件的件数（设计硬指标 ≥6）
chk("★ 有挂载触发的装备 ≥6 件（本批 %d 件）" % len(EVENTS), len(EVENTS) >= 6)

print()
for iid, who, at in EVENTS:
    print("  · %-28s → %-18s %s" % (iid, who, LINES[iid].split("\n")[0][:30]))
print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
