# -*- coding: utf-8 -*-
"""探针：codex 域（图鉴四谱 + 记录）—— 条目对账 · 拿到的算数 · 记录与认出的行为。

判据（★ = 跨域/行为，最要紧）：
  ① 四本谱齐全 · 每本都有条目 · 条数 ≥ 记满（材料 10 / 风味 8 / 怪物 12）
  ② ★ 跨域对账：材料/风味 id 在 items 域且 kind 对得上 · 怪物 id 在 monsters 域 ·
     旧物（读的）在有 into_codex 的 pois 里 · 旧物（捡的）在 items / drop_pools 里 · ask 里的人在 npcs 域
  ③ ★ 反向：pois 里每个 into_codex 的条目都在旧物谱里（= 12 类可读物，21_长期目标层那条称号的载体）
  ④ ★ 材料谱里「真拿得到」的条数 ≥ 记满（出产 = 采集池 / 掉落池 / 配方产出 —— 本探针**自己**从三个域重算）
  ⑤ 每本谱每条都有一句人话：非空 · 12–60 字 · 不带数值表腔（不含 hp/atk/def/×/％）
  ⑥ 旧物谱：hint 与 known 都在且不相同 · ask 至少一个人 · from ∈ {read, pick}
  ⑦ ★ 记录行为：到手进谱且只记第一次 · 打过累加 · 走过节点不重复
  ⑧ ★ 认出行为：名单外的人不给认 · 名单里的人把问号换掉（不认第二遍）
  ⑨ ★ 六条指令都接在 content.cmds_codex 上，且实现体真的存在
  ⑩ 图鉴用到的文案槽位都在 texts 域
  ⑪ ★ P-8 行为：自己看（端详）—— 看过 ≠ 认出来 · 不可逆 · 手上没有不给看 · 物证句来自实物域

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_codex.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402

ok = True


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


print("探针：codex 域（图鉴四谱 + 记录）")
st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
st.install()

CX = st.domain("codex")
IT = st.domain("items")
MR = st.domain("monsters")
PO = st.domain("pois")
NP = st.domain("npcs")
GA = st.domain("gathering")
DP = st.domain("drop_pools")
RC = st.domain("recipes")
TX = st.domain("texts")
chk("codex 域读得到", CX is not None, "%d 本谱" % len([k for k in (CX or {}) if not k.startswith("_")]))

BOOKS = ("material", "flavor", "monster", "relic")
LABEL = {"material": "材料谱", "flavor": "风味谱", "monster": "怪物谱", "relic": "旧物谱"}
BOOK = {b: dict(CX.get(b) or {}) for b in BOOKS}
TARGET = dict((CX.get("_meta") or {}).get("targets") or {})

# ① 四本谱齐全 · 条数 ≥ 记满
chk("四本谱都有条目", all(BOOK[b] for b in BOOKS),
    " · ".join("%s %d" % (LABEL[b], len(BOOK[b])) for b in BOOKS))
chk("三本谱的记满数写着（材料 10 / 风味 8 / 怪物 12）",
    TARGET == {"material": 10, "flavor": 8, "monster": 12}, TARGET)
short = {b: (len(BOOK[b]), TARGET[b]) for b in TARGET if len(BOOK[b]) < TARGET[b]}
chk("条数都过记满线", not short, short or "全过")

# ② 跨域对账
bad_mat = [k for k in BOOK["material"] if k not in IT or (IT[k].get("kind_key") or "") not in ("material", "junk", "clue")]
chk("★ 材料谱条目都在 items 域且机器键是 material/junk/clue", not bad_mat, bad_mat[:4])
bad_fla = [k for k in BOOK["flavor"] if k not in IT or IT[k].get("kind_key") != "food"]
chk("★ 风味谱条目都在 items 域且机器键是 food", not bad_fla, bad_fla[:4])
bad_mon = [k for k in BOOK["monster"] if k not in MR]
chk("★ 怪物谱条目都在 monsters 域", not bad_mon, bad_mon[:4])
read_ids = [k for k, v in BOOK["relic"].items() if v.get("from") == "read"]
pick_ids = [k for k, v in BOOK["relic"].items() if v.get("from") == "pick"]
bad_read = [k for k in read_ids if k not in PO or not PO[k].get("into_codex")]
chk("★ 旧物谱（读的）都指向有 into_codex 的 pois", not bad_read, bad_read[:4])
bad_pick = [k for k in pick_ids if k not in IT and k not in DP]
chk("★ 旧物谱（捡的）都在 items / drop_pools 里", not bad_pick, bad_pick[:4])
bad_ask = [k for k, v in BOOK["relic"].items() if [a for a in v.get("ask") or [] if a not in NP]]
chk("★ 旧物谱的 ask 都在 npcs 域", not bad_ask, bad_ask[:4])

# ③ 反向：可读物 ↔ 旧物谱（读的）
want = {k for k, v in PO.items() if v.get("into_codex")}
chk("★ 每个 into_codex 的可读物都在旧物谱里（12 类）",
    want == set(read_ids), "pois %d / 谱 %d；缺 %s" % (len(want), len(read_ids), sorted(want - set(read_ids))))

# ④ ★ 材料谱里「真拿得到」的条数 ≥ 记满（探针自己从三个域重算）
produced = set()
for g in GA.values():
    for e in (g.get("pool") or []):
        produced.add(str(e.get("out")))
for p_ in DP.values():
    for e in (p_.get("entries") or []) + (p_.get("pool") or []):
        produced.add(str(e.get("out")))
for r in RC.values():
    if r.get("out"):
        produced.add(str(r["out"]))
reach = sorted(k for k in BOOK["material"] if k in produced)
chk("★ 材料谱能真拿到的 ≥ 记满 %d 条" % TARGET["material"],
    len(reach) >= TARGET["material"],
    "%d/%d 拿得到；拿不到的：%s" % (len(reach), len(BOOK["material"]), sorted(set(BOOK["material"]) - set(reach)) or "无"))

# ⑤ 一句人话（非空 · 12–60 字 · 不是数值表）
BAD_WORDS = ("hp", "atk", "def", "spd", "crit", "×", "％")
bad_line = []
for b in BOOKS:
    for k, v in BOOK[b].items():
        for key in (("line",) if b != "relic" else ("hint", "known")):
            s = str(v.get(key) or "")
            if not (12 <= len(s) <= 60) or any(w in s for w in BAD_WORDS):
                bad_line.append("%s.%s.%s(%d 字)" % (LABEL[b], k, key, len(s)))
chk("每一条都是一句人话（12–60 字 · 不含数值表腔）", not bad_line, bad_line[:4])

# ⑥ 旧物谱的形状
bad_rel = [k for k, v in BOOK["relic"].items()
           if v.get("from") not in ("read", "pick") or not v.get("hint") or not v.get("known")
           or v.get("hint") == v.get("known") or not (v.get("ask") or [])]
chk("旧物谱都是「问号行 + 认出后 + 至少一个问的人」", not bad_rel, bad_rel[:4])

# ⑦⑧ 行为：记录与认出（直接调唯一记录口 —— 它才是三个调用方共用的那一层）
from content import codex as CM                                      # noqa: E402

p = {"day": 3, "loc": "windmill_town", "node": "wt_gate_n", "books": {}, "foot": {}}
mat_rid = sorted(BOOK["material"])[0]
fla_rid = sorted(BOOK["flavor"])[0]
mon_rid = sorted(BOOK["monster"])[0]
read_rid = sorted(read_ids)[0]
pick_rid = sorted(pick_ids)[0]

new1 = CM.note_items(p, [mat_rid, mat_rid, fla_rid])
chk("★ 到手进谱（同一件不记两遍）",
    len(new1) == 2 and CM.count(p, "material") == 1 and CM.count(p, "flavor") == 1, new1)
chk("★ 装备那类不进谱（谱只收材料/食物/信物 · 装备 = 带 `slot` 的那些）",
    CM.note_items(p, [sorted(k for k in IT if IT[k].get("slot"))[0]]) == [])

# ⑨ ★ B3-6b-2d-keys-2：图鉴归属的机器键（P-20 甲案第二刀）—— 代码表 ↔ 域 ↔ **逐件真跑**
#   ① 代码那两张表（KIND_BOOK / PICK_BOOK）只许有 ASCII 键、且键都在域里真出现过、两表不许撞键
#   ② 逐件真跑 `note_item`：归属 == 表算出来的（122 件物品 + 2 个未鉴定池 + 1 个认不出的 id）
#   ③ 换键前后是**同一批书**：装备那半（带 slot 的）一件都不进谱
_BOOK_OF = {}
_dupk = sorted(set(CM.KIND_BOOK) & set(CM.PICK_BOOK))
_BOOK_OF.update(CM.KIND_BOOK)
_BOOK_OF.update(CM.PICK_BOOK)
chk("★ 代码那两张表只有 ASCII 键、且两表不撞键（%d 个键）" % len(_BOOK_OF),
    all(str(k).isascii() for k in _BOOK_OF) and not _dupk, "撞键：%s" % _dupk)
_POOLK = {v.get("kind_key") for v in DP.values()} | {
    e.get("kind_key") for v in DP.values()
    for e in (list(v.get("entries") or []) + list(v.get("pool") or []))}
_HAS = {v.get("kind_key") for v in IT.values()} | _POOLK
chk("★ 表里的键都在域里真出现过（items / drop_pools 的 `kind_key`）",
    set(_BOOK_OF) <= _HAS, "域里没有的：%s" % sorted(set(_BOOK_OF) - _HAS))
_attr_bad = []
for _iid, _v in IT.items():
    _want = _BOOK_OF.get(_v.get("kind_key"))
    _got = CM.note_item({}, _iid)
    if _got != _want:
        _attr_bad.append((_iid, _v.get("kind_key"), _want, _got))
for _pid, _p in DP.items():
    if str(_pid).startswith("unid_"):
        _want = _BOOK_OF.get(_p.get("kind_key"))
        _got = CM.note_item({}, _pid)
        if _got != _want:
            _attr_bad.append((_pid, _p.get("kind_key"), _want, _got))
chk("★ 真跑 %d 件 + %d 个未鉴定池：归属 == 表算出来的（换键前后同一批书）"
    % (len(IT), len([k for k in DP if str(k).startswith("unid_")])),
    not _attr_bad, "%s" % (_attr_bad[:4] or "无"))
chk("★ 认不出的 id 不进任何谱（fail-closed，不猜一本）",
    CM.note_item({}, "i_nope_nothing_at_all") is None)
chk("★ 装备那半（带 slot 的 %d 件）一件都不进谱"
    % len([k for k, v in IT.items() if v.get("slot")]),
    not [k for k, v in IT.items() if v.get("slot") and _BOOK_OF.get(v.get("kind_key"))])

CM.note_kill(p, mon_rid)
CM.note_kill(p, mon_rid)
chk("★ 打过累加（怪物谱只一条、次数两次）",
    CM.has(p, "monster", mon_rid) and CM.kills_of(p, mon_rid) == 2, CM.kills_of(p, mon_rid))

CM.note_visit(p, "belt_north", "bn_bone")
CM.note_visit(p, "belt_north", "bn_bone")
CM.note_gather(p)
f = CM.foot(p)
chk("★ 足迹：站的这一格算去过 · 同一个节点不重复记 · 打过/采过有数",
    len(f["nodes"]) == 2 and "windmill_town:wt_gate_n" in f["nodes"]
    and f["kills"] == 2 and f["gathers"] == 1 and f["days"] == 1, f)

chk("读到的旧物先给问号", CM.note_read(p, read_rid) and not CM.known(p, read_rid))
chk("捡到的旧物先给问号", CM.note_pick(p, pick_rid) and not CM.known(p, pick_rid))
asks = BOOK["relic"][read_rid].get("ask") or []
outsider = next((n for n in NP if n not in asks), None)
chk("★ 名单外的人不给认（他不会瞎认）",
    not CM.revealable(p, outsider) if outsider else True, "外人=%s" % outsider)
chk("★ 名单里的人能认出（返回可认的条目）", reads_ok := (read_rid in CM.revealable(p, asks[0])), asks)
chk("★ 认出后问号没了 · 也不认第二遍",
    CM.reveal(p, read_rid) and CM.known(p, read_rid) and not CM.reveal(p, read_rid))

# ⑦b 背包对账（背包 ⊆ 谱 —— 老档/漏接的路在开谱那一刻补上）
p2 = {"day": 1, "loc": "windmill_town", "node": "wt_gate_n",
      "bag": {mat_rid: 2, mon_rid: 1, fla_rid: 1}, "books": {}, "foot": {}}
fresh = CM.sync_bag(p2)
chk("★ 开谱跟背包对账（拿着的东西算见过 · 装备不进谱）",
    sorted(fresh) == sorted([("material", mat_rid), ("flavor", fla_rid)])
    and CM.sync_bag(p2) == [], fresh)

pr = CM.progress(p)
chk("★ 进度：四本谱都有数（材料 1 · 风味 1 · 怪物 1 · 旧物 2 · 问号 1）",
    pr["material"]["n"] == 1 and pr["flavor"]["n"] == 1 and pr["monster"]["n"] == 1
    and pr["relic"]["n"] == 2 and pr["relic"]["unknown"] == 1, pr["relic"])

# ⑨ 六条指令真的接在 content.cmds_codex 上（声明 → 实现体都在）
import importlib                                                      # noqa: E402
import json as _json                                                  # noqa: E402
import re as _re                                                      # noqa: E402

CMDS = _json.load(open(os.path.join(str(REPO), "content", "data", "commands.json"), encoding="utf-8"))
WANT = {"codex": "codex", "codex_material": "codex_material", "codex_flavor": "codex_flavor",
        "codex_monster": "codex_monster", "codex_relic": "codex_relic", "footprint": "footprint"}
bad_bind = []
for key, fn in WANT.items():
    spec = ((CMDS.get(key) or {}).get("bind") or {}).get("handler") or ""
    if spec != "content.cmds_codex:%s" % fn:
        bad_bind.append("%s → %r" % (key, spec))
mod = importlib.import_module("content.cmds_codex")
missing_fn = [fn for fn in WANT.values() if not callable(getattr(mod, fn, None))]
chk("★ 图鉴六条指令都接上 content.cmds_codex", not bad_bind, bad_bind)
chk("六个实现体都在", not missing_fn, missing_fn)

# ⑩ 用到的文案槽位都在 texts 域（从实现体的 T(...) 调用面静态取）
src = open(os.path.join(str(REPO), "content", "cmds_codex.py"), encoding="utf-8").read()
slots = set(_re.findall(r'T\(\s*"([A-Z0-9_]+)"', src))
slots |= {s for s in (TX or {}) if s.startswith("SYS_CODEX_EMPTY_")}
slots |= {"SYS_FOOT_HEAD", "SYS_FOOT_MORE", "SYS_FOOT_BOOKS", "SYS_FOOT_EMPTY",
          "SYS_CODEX_HEAD", "SYS_CODEX_ROW", "SYS_CODEX_ROW_RELIC", "SYS_CODEX_HINT",
          "SYS_CODEX_BOOK_HEAD", "SYS_CODEX_BOOK_HEAD_OPEN", "SYS_CODEX_ENTRY",
          "SYS_CODEX_ENTRY_KILL", "SYS_CODEX_RELIC_UNKNOWN", "SYS_CODEX_RELIC_KNOWN",
          "SYS_CODEX_RELIC_ASK_HINT", "SYS_CODEX_NEW", "SYS_CODEX_REVEAL", "SYS_CODEX_ASK",
          "SYS_CODEX_FULL", "SYS_CODEX_TODO"}
miss_slot = sorted(s for s in slots if s not in TX)
chk("★ 图鉴/记录的文案槽位都在 texts 域（%d 个）" % len(slots), not miss_slot, miss_slot)

# ⑪ ★ P-8：旧物谱的**另一条路** —— 自己看（`端详 <旧物>`），不靠 NPC 也能往前挪一格
#    判据是**行为**（不是结构）：看过 ≠ 认出来 · 不可逆 · 幂等 · 手上没有不给看 · 物证句来自实物域
import asyncio                                                        # noqa: E402
import copy as _copy                                                  # noqa: E402

from content import cmds_codex as CC                                  # noqa: E402


class _E(object):               # 「端详」只要 env.text（真取参数）与 env.save（落档）
    def __init__(self, text):
        self.text = text
        self.saved = 0

    def save(self):
        self.saved += 1


def _run(text, p, fn=None):
    out = []

    async def _go():
        async for line in (fn or CC.relic_study)(_E(text), None, "u_study", p):
            out.append(line)

    asyncio.run(_go())
    return out


EV_ITEM = str((IT.get("i_horn_half") or {}).get("lore") or "")        # 信物：物证在 items 域
EV_POOL = str((DP.get("unid_common") or {}).get("hint") or "")        # 未鉴定：物证挂在池表上
chk("物证句取得到（信物那条走 items · 未鉴定那条走池表）",
    bool(EV_ITEM) and bool(EV_POOL), "%s / %s" % (EV_ITEM[:14], EV_POOL[:14]))
chk("★ 物证句就是实物域那一句（不是代码里编的）",
    CM.evidence("i_horn_half") == EV_ITEM and CM.evidence("unid_common") == EV_POOL)
chk("★ 手上没有 / 看不出所以然 ⇒ 回空串（fail-closed）",
    CM.evidence("poi_named_birch") == "" and CM.evidence("不存在的 id") == "")

p3 = {"day": 2, "loc": "windmill_town", "node": "wt_gate_n",
      "bag": {"i_horn_half": 1, "unid_common": 1}, "books": {}, "foot": {}}
CM.sync_bag(p3)
chk("★ 自己看：看出一层就落档（studied 那一格）",
    CM.study(p3, "i_horn_half") and CM.studied(p3, "i_horn_half"))
chk("★ 不可逆 · 幂等：第二遍不再动档", not CM.study(p3, "i_horn_half"))
chk("★ 看过 ≠ 认出来：known 一个字没动 · 那个人照样能认出它",
    not CM.known(p3, "i_horn_half") and "i_horn_half" in CM.revealable(p3, "npc_durin"),
    CM.revealable(p3, "npc_durin"))
chk("★ 两格都在时互不抵消（问人之后 studied 不被打回）",
    CM.reveal(p3, "i_horn_half") and CM.known(p3, "i_horn_half") and CM.studied(p3, "i_horn_half"))
chk("★ 没进过谱的 id 不落档（study 认谱）", not CM.study({"books": {"relic": {}}}, "i_horn_half"))

p4 = {"day": 2, "loc": "windmill_town", "node": "wt_gate_n",
      "bag": {"i_horn_half": 1}, "books": {}, "foot": {}}
CM.sync_bag(p4)
bare = _run("旧物谱", p4)
seen = _run("端详 半截号角", p4)
snap1 = _copy.deepcopy(p4["books"])
after = _run("旧物谱", p4)
again = _run("端详 半截号角", p4)
chk("★ 没看过时，旧物谱那条只有问号行（没有「看出来的」那行）",
    any(TX["SYS_CODEX_RELIC_UNKNOWN"]["value"].split("{")[0] in x for x in bare)
    and not any(EV_ITEM in x for x in bare), bare)
chk("★ 自己看那一句**走槽位**（= texts 里 SYS_CODEX_RELIC_SEEN 填上物证句）",
    TX["SYS_CODEX_RELIC_SEEN"]["value"].replace("{line}", EV_ITEM) in seen, seen)
chk("★ 看完之后旧物谱多出那一行 · 问号行照旧（没认出来）",
    any(EV_ITEM in x for x in after)
    and any(TX["SYS_CODEX_RELIC_UNKNOWN"]["value"].split("{")[0] in x for x in after)
    and not any(str(BOOK["relic"]["i_horn_half"].get("known") or "") in x for x in after)
    and ((snap1.get("relic") or {}).get("i_horn_half") or {}).get("known") is False, after)
chk("★ 第二遍看：回话一字不差 · 档上不动", again == seen and p4["books"] == snap1,
    "回话%s / 档%s" % ("同" if again == seen else "不同", "同" if p4["books"] == snap1 else "不同"))
chk("★ 自己看不漏「来处」：看完仍然提醒他问人（尾注还在）",
    TX["SYS_CODEX_RELIC_ASK_HINT"]["value"] in seen, seen)
nohold = _run("端详 镇口的石头", p4)
chk("★ 手上没有这一件 ⇒ 走自己的槽位（SYS_CODEX_RELIC_NOHOLD）· 不落档",
    TX["SYS_CODEX_RELIC_NOHOLD"]["value"].replace("{input}", "镇口的石头") in nohold
    and "poi_named_birch" not in (p4.get("books") or {}).get("relic", {}), nohold)
p5 = {"day": 2, "loc": "windmill_town", "node": "wt_gate_n",
      "bag": {"unid_common": 1}, "books": {}, "foot": {}}
CM.sync_bag(p5)
seen5 = _run("端详 一块看不出用途的旧东西", p5)
chk("★ 未鉴定那两件（物证挂池表）也看得出", len(seen5) > 1 and seen5[1].endswith(EV_POOL)
    and ((p5["books"].get("relic") or {}).get("unid_common") or {}).get("studied") is True, seen5)

print()
print("按谱：%s" % " · ".join("%s %d" % (LABEL[b], len(BOOK[b])) for b in BOOKS))
print("旧物谱：读的 %d · 捡的 %d" % (len(read_ids), len(pick_ids)))
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(1 if not ok else 0)
