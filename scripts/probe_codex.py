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
  ⑫ ★ B3-7 旧物谱入口：新那条（`unid_tower`）真拿得到（有出产）· 塔内那 6 条就地线索不进谱（12 类不动）
  ⑬ ★ B3-10：12 条「读的」旧物逐条真跑『旧物谱』—— 问号行 / 认出后那行**照字出**（逐字取自 14 号文档）
  ⑭ ★ B4-9 日期戳 + 2026-09-30 审计残余 #34：**同一节点跨天**也计进「N 个游戏日」（原口径只取 `nodes` 第一回到 ⇒ 恒 1）
  ⑰ ★ 2026-09-30 审计残余 #15：`_meta.book_label ⊇ BOOKS`（现算不手抄）· `codex.label()` fail-closed

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
sys.path.insert(0, str(REPO / "scripts"))           # read_kinds（可读物那个数的唯一解析口）
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402

import read_kinds as RK                                              # noqa: E402

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

# ③ 反向：可读物 ↔ 旧物谱（读的）—— ★ 条数**不许手打**：`scripts/read_kinds.py` 从四处文档
#    现解析（10 §一A 的编号项 · 19 §三A 的 3+9 · 21 §一 称号那句 · 16 §二 的条件），
#    再与域里现算（pois.into_codex / 旧物谱 from=read / titles.read_all）逐处比对。
_rk = RK.audit(pois=PO, relic_read=read_ids, titles=(st.domain("titles") or {}))
want = {k for k, v in PO.items() if v.get("into_codex")}
chk("★ 每个 into_codex 的可读物都在旧物谱里 · 且条数 = 文档那 12 类"
    "（10 §一A %(10)d · 19 §三A %(f)d+%(e)d · 21 §一 %(21)d · 16 §二 %(16)d · 域里 %(rr)s）"
    % {"10": _rk["doc"]["10"], "f": _rk["doc"]["19_fixed"], "e": _rk["doc"]["19_expand"],
       "21": _rk["doc"]["21"], "16": _rk["doc"]["16"],
       "rr": _rk["live"].get("codex.relic[from=read]")},
    want == set(read_ids) and not _rk["bad"],
    "pois %d / 谱 %d；缺 %s；%s" % (len(want), len(read_ids), sorted(want - set(read_ids)), _rk["bad"]))

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


class _E(object):               # 「端详」只要 env.text（真取参数）、env.save（落档）与分页那一口
    def __init__(self, text):
        self.text = text
        self.saved = 0

    def save(self):
        self.saved += 1

    # ★ F6：旧物谱也走 `content/pager.py` 那一口了 ⇒ 桩要把这两格的**契约**补齐
    #   （照引擎 `host/env.py::Env` 的签名；切页本体仍是引擎那两个纯函数，桩里不重造一份）
    def page(self, raw=None, default=1):
        from saintess_engine.command import paging as _PG
        return _PG.parse_page(raw) if str(raw or "").strip() else int(default)

    def page_items(self, items, page=1, per_page=10):
        from saintess_engine.command import paging as _PG
        return _PG.page_items(list(items), page, per_page=per_page)


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

# ⑫ ★ B3-7：旧物谱入口那一条（`unid_tower` —— 旧哨塔门厅那件不认得的）
#    ① 「捡的」那几条**都在某个域的出产里**（谱里不许有拿不到的条目）—— 这一批新加的那条靠塔内的可搜物；
#    ② 塔内那 5 条新可读物（正文槽位 READ_TOWER_*）一条都不进谱 —— 12 类那个数不动
#       （要改口径 = 真源 `14_图鉴四谱口径_v1 §relic` 加行 + `10_地图探索元素库 §一A` 那 12 类一起动，
#        建议行写在**工作树 `_notes.md` §二**，本批代码里一行都没加）；
#    ③ 端详那条线接得上：物证句就是池表上那一句（与 probe_codex ⑪ 同一个口，这条核新那一件）。
_produced = set()
for _g in GA.values():
    for _e in (_g.get("pool") or []):
        _produced.add(str(_e.get("out")))
for _p in DP.values():
    for _e in (_p.get("entries") or []) + (_p.get("pool") or []):
        _produced.add(str(_e.get("out")))
for _r in RC.values():
    if _r.get("out"):
        _produced.add(str(_r["out"]))
_no_src = [k for k in pick_ids if k not in _produced]
chk("★ 旧物谱里「捡的」每一条都在某个域的出产里（%d 条 · 缺出产的：%s）" % (len(pick_ids), _no_src or "无"),
    not _no_src, " · ".join(pick_ids))
_TW22 = RK.tower_reads(RK.rd(RK.DOC22))          # 22 §一「可读物」那一列（塔内 9 项）
_in_tw = [k for k in read_ids if PO[k].get("map") == "old_watchtower"]
_loc = sorted(k for k, v in PO.items() if v.get("kind") == "可读物"
              and v.get("map") == "old_watchtower" and not v.get("into_codex"))
chk("★ 塔内那 %d 条就地线索一条都不进旧物谱（= 22 §一 那 %d 项 − 其中已进谱的 %d 条）· 12 类那个数不动"
    % (len(_loc), _TW22["n"], len(_in_tw)),
    len(_loc) == _TW22["n"] - len(_in_tw)
    and not [k for k in _loc if k in BOOK["relic"] or PO[k].get("into_codex")], _loc)
chk("★ 新那条（unid_tower）的物证句 = 池表上那一句（端详那条线接得上）",
    bool(CM.evidence("unid_tower")) and CM.evidence("unid_tower") == (DP.get("unid_tower") or {}).get("hint"),
    "%s" % CM.evidence("unid_tower"))

# ⑬ ★ B3-10：**谱里那一行照字出** —— 12 条「读的」旧物逐条真跑 `旧物谱`：
#    没认出来时那一行 = 14 号文档的 `hint`（逐字）· 认出来之后那一行 = `known`（逐字）。
#    这不是读 `codex.json` 自述（那是产物）—— 是**真跑呈现口**（cmds_codex.codex_relic）。
print("⑬ 12 条「读的」旧物逐条真跑『旧物谱』：那一行照字出")
_line_bad = []
for _rid in sorted(read_ids):
    _rec = BOOK["relic"][_rid]
    _p13 = {"day": 1, "loc": "windmill_town", "node": "wt_gate_n",
            "books": {"relic": {_rid: {"known": False}}}, "foot": {}}
    _q = _run("旧物谱", _p13, CC.codex_relic)
    _p13["books"]["relic"][_rid]["known"] = True
    _k = _run("旧物谱", _p13, CC.codex_relic)
    if not [x for x in _q if str(_rec.get("hint") or "") in x]:
        _line_bad.append((_rid, "问号行没照字出", _q[-1:]))
    elif not [x for x in _k if str(_rec.get("known") or "") in x]:
        _line_bad.append((_rid, "认出后那行没照字出", _k[-1:]))
chk("★ 12 条「读的」旧物：谱里那一行逐字取自 14 号文档（问号行 hint · 认出后 known）",
    not _line_bad, "%s" % (_line_bad[:2] or "%d 条都对" % len(read_ids)))

# ⑭ ★ B4-9：日期戳走「此刻」那一个口 —— `记录` 里的「N 个游戏日」不许把
#   「不知道哪天」（档上那格还是 0）算成一天。实测（真机 + 假钟）：全新角色同一分钟里
#   `往北` → `采集` → `往东` ⇒ `记录` 报「2 个游戏日」（其中一个就是那个 0）。
from content import calendar as CAL2                                   # noqa: E402
from content import facade as FAC2                                     # noqa: E402

_HANDLES = dict(FAC2.HANDLES)                                          # 动完这根钟要还原
_FIX = 100 * CAL2.scale_seconds() + (12.0 / 24.0) * CAL2.scale_seconds()
FAC2.bind_host(clock=lambda: _FIX)
_D0 = CAL2.day_now()
_p14 = {"loc": "windmill_town", "node": "wt_gate_n", "foot": {}}       # 全新档：day 那格还没 tick 过
CM.note_visit(_p14, "windmill_town", "wt_gate_n")
CM.note_visit(_p14, "belt_north", "bn_bone")
chk("★ 全新档（`day` 那格还没 tick 过）：日期戳**不是 0** —— 记下来的是此刻那一天（%s）" % _D0,
    set(int(d) for d in CM.foot(_p14)["nodes"].values()) == {_D0}
    and CM.foot(_p14)["days"] == 1, CM.foot(_p14))
FAC2.bind_host(clock=lambda: _FIX + CAL2.scale_seconds())              # 钟推过一整个游戏日
CM.note_visit(_p14, "belt_east", "be_birch")
chk("★ 钟推过一个游戏日再走一个新节点 ⇒ 「2 个游戏日」（跨日真数得出来）",
    CM.foot(_p14)["days"] == 2, CM.foot(_p14))
_p14b = {"loc": "windmill_town", "node": "wt_gate_n", "foot": {
    "nodes": {"windmill_town:wt_gate_n": 0, "belt_north:bn_bone": 0}}}  # B4-9 之前留下的老档
chk("★ 老档里那些「0 = 不知道哪天」不算一个游戏日（全都不知道 ⇒ 至少 1）",
    CM.foot(_p14b)["days"] == 1, CM.foot(_p14b))
# ★ 2026-09-30 审计残余 #34：**同一节点跨天**也算天数 —— 原口径 `days` 只从 `nodes` 取，
#   而 `nodes` 只在**第一回到**时写（`note_visit` 首次才落）⇒ 3 个游戏日反复走同一个节点
#   （镇口磨剑 / 骨田刷怪就是这个形态）⇒ `visits={'wt_gate_n':3}` 而 `days=1`，
#   玩家可见的 `SYS_FOOT_HEAD` 直印这个数。修法 = `nodes` ∪ `day_seen` 并集（`_note_day` 每次走到/站到记一笔）。
#   ★ 上面三条断言口径**没变**，理由：并集只多记「同一节点又来的那天」——初档只有一天、
#     跨日那次是**新节点**（`be_birch` 的 day 本来就在 `nodes` 里）、老档 `day_seen` 缺省为空
#     ⇒ 三条各自的结果逐字不变（此处继续断言它们，就是钉住「没顺手改坏老口径」）。
_p14c = {"loc": "windmill_town", "node": "wt_gate_n", "foot": {}}
#   ★ 照**真走路**那两条腿记（`cmds_ast` 里 `note_visit` + `note_step` 成对调）：
CM.note_visit(_p14c, "windmill_town", "wt_gate_n")
CM.note_step(_p14c, "windmill_town", "wt_gate_n")             # 第 1 天走这一处
FAC2.bind_host(clock=lambda: _FIX + 2 * CAL2.scale_seconds())  # 钟再推过一整个游戏日
CM.note_visit(_p14c, "windmill_town", "wt_gate_n")
CM.note_step(_p14c, "windmill_town", "wt_gate_n")             # 第 2 天**同一个节点**
FAC2.bind_host(clock=lambda: _FIX + 3 * CAL2.scale_seconds())
CM.note_visit(_p14c, "windmill_town", "wt_gate_n")
CM.note_step(_p14c, "windmill_town", "wt_gate_n")             # 第 3 天还是它
_f14c = CM.foot(_p14c)
chk("★ #34 同一节点连走 3 个游戏日 ⇒ 「3 个游戏日」（原口径恒 1 · `nodes` 仍只记第一回到）",
    _f14c["days"] == 3 and len(_f14c["nodes"]) == 1
    and _f14c["visits"].get("windmill_town:wt_gate_n") == 3, _f14c)
FAC2.bind_host(**_HANDLES)                                             # 还原（含 db_path 与真钟）

#: 静态守卫：**玩家档上那一格** `p["day"]` 只许 `calendar.tick()` 读（它是跨日标记，
#: 采集次数靠它归零）—— 日期戳一律走 `calendar.day_now()`（`codex.today` / `heard.today`
#: 都转发到它）。★ 只认**变量名 `p` 的那一份**：`flags.ev["day"]` / 称号记录里的 `day`
#: / `seen["day"]` 是别的字段，各有各的用处（宽了会一片假红 —— K46 那类）。
_DAY_RE = _re.compile(r"""p\.get\(['"]day['"]\)|p\[['"]day['"]\]""")
_day_hits = []
for _name in sorted(os.listdir(os.path.join(str(REPO), "content"))):
    if not _name.endswith(".py"):
        continue
    _src = open(os.path.join(str(REPO), "content", _name), encoding="utf-8").read()
    for _i, _line in enumerate(_src.splitlines(), 1):
        if _DAY_RE.search(_line):
            _day_hits.append("%s:%d %s" % (_name, _i, _line.strip()[:46]))
chk("★ 读**玩家档上那一格** `p[day]` 的只剩 `calendar.tick()` —— 日期戳全走 `day_now()`",
    [x for x in _day_hits if not x.startswith("calendar.py")] == [], str(_day_hits))

# ══════════════════════════════════════════════════════════════
# ⑮ ★ F6（QA P4 BUG-4 / P3）：旧物谱三行排版 + 端详能重看谱里那一条
#    改前：未认出的**捡的**那件只出一句裸问号行（没有器物名 ⇒ 看不出是哪一件），
#    紧跟着又把『端详』的物证句当谱条目贴一遍（同一件事写两行）。
# ══════════════════════════════════════════════════════════════
print("⑮ ★ F6：旧物谱三行排版（认出来 / 没认出·读的 / 没认出·捡的）+ 端详能重看")


def _book_of(p, fn=None):
    return _run("旧物谱", p, fn)


# ① 捡的（未认出、没看过）：带**手上的名字**；还没看 ⇒ 没有「看出来了」那行
_p15a = {"day": 1, "loc": "windmill_town", "node": "wt_gate_n",
         "bag": {"unid_common": 1}, "books": {}, "foot": {}}
CM.sync_bag(_p15a)
_b15a = _book_of(_p15a, CC.codex_relic)
_held15 = CM.held_name("unid_common")
chk("★ 没认出·**捡的**那一条带上器物名（`%s` —— 玩家在背包里看见的就是它）" % _held15,
    any(x == TX["SYS_CODEX_RELIC_UNKNOWN_HELD"]["value"].replace("{name}", _held15)
        .replace("{hint}", BOOK["relic"]["unid_common"]["hint"]) for x in _b15a), _b15a)
chk("★ 没看过 ⇒ 谱里那件只有问号那一行（没有「看出来了」那行）",
    not any(EV_POOL in x for x in _b15a), _b15a)

# ② 看过之后：物证句与问号行**说的是同一件事** ⇒ 不再贴第二遍（BUG-4 的直接病灶）
_seen15 = _run("端详 %s" % _held15, _p15a, CC.relic_study)
_b15b = _book_of(_p15a, CC.codex_relic)
chk("★ 端详那一句照旧出得来（交互回话不受影响）",
    TX["SYS_CODEX_RELIC_SEEN"]["value"].replace("{line}", EV_POOL) in _seen15, _seen15)
chk("★ 同一件事不贴两遍：问号行已说过的物证句**不再**当谱条目贴一行",
    not any(EV_POOL in x for x in _b15b) and any(x.startswith("？ ") for x in _b15b), _b15b)

# ③ 反证（真源 `14_图鉴四谱口径_v1 §五`「没认出来时只显示一行问号（**名字不写**）」）：
#    **读的**那几条仍然不写名字 —— 名字本身就是认出后的答案
_p15c = {"day": 1, "loc": "windmill_town", "node": "wt_gate_n",
         "books": {"relic": {"poi_stone_scripts": {"day": 1, "known": False}}}, "foot": {}}
_b15c = _book_of(_p15c, CC.codex_relic)
chk("★ 反证：没认出的**读的**那一条**不写名字**（真源 §五「名字不写」—— 拆掉的只是捡的那半边）",
    any(x == TX["SYS_CODEX_RELIC_UNKNOWN"]["value"]
        .replace("{hint}", BOOK["relic"]["poi_stone_scripts"]["hint"]) for x in _b15c)
    and not any(BOOK["relic"]["poi_stone_scripts"]["name"] in x for x in _b15c), _b15c)

# ④ 信物那件：物证句是**另一层**（不是问号行已说的那句）⇒ 照 B3-16 口径仍然多出一行
_p15d = {"day": 1, "loc": "windmill_town", "node": "wt_gate_n",
         "bag": {"i_horn_half": 1}, "books": {}, "foot": {}}
CM.sync_bag(_p15d)
_run("端详 半截号角", _p15d, CC.relic_study)
_b15d = _book_of(_p15d, CC.codex_relic)
chk("★ 反证：物证句真**多说了一层**时照旧另起一行（`半截号角` —— B3-16 那笔没被这刀削掉）",
    any(EV_ITEM in x for x in _b15d), _b15d)

# ④b ★ fix-n-small ②：**已经认出名字**的那一条底下**不再贴**「端详自己看出那一层」——
#     认名那一行（`known`）本来就高于自己看出那一层，而且端详那一句正是**认名前那行问号**
#     说的同一件事（`hint` == 物证句）⇒ 认名把整行换掉之后再贴一遍，看着就是「问号句又回来了」。
#     QA 两轮报到的两个样本原样钉在这：`一块刻着字的石片`（unid_rare）/`一块看不出用途的旧东西`
#     （unid_common）—— 加上信物那件（它的物证句与问号行不是同一句，最能证「认名之后一律不贴」）。
#     ★ 反证在上面 ④ 与下面两条：「未认名时照旧要出」+「`端详` 随时还能重看那一件」。
#     为什么不丢信息：端详那一刻玩家已经看到过（`studied` 那一格就是那一下落的档），
#     认名之后 `端详 <名>` 仍能重看（`relic_study` 的 known 那一支）。
_p16 = {"day": 1, "loc": "windmill_town", "node": "wt_gate_n",
        "bag": {"unid_rare": 1, "unid_common": 1, "i_horn_half": 1}, "books": {}, "foot": {}}
CM.sync_bag(_p16)
_run("端详 %s" % CM.held_name("i_horn_half"), _p16, CC.relic_study)   # 先看（此时还没认出来）
_b16a = _book_of(_p16, CC.codex_relic)
chk("★ 反证（未认名）：自己看出那一层真多说了一层时照旧另起一行 —— `%s`" % CM.held_name("i_horn_half"),
    any(EV_ITEM in x for x in _b16a), _b16a)
for _rid16 in ("unid_rare", "unid_common", "i_horn_half"):
    _run("端详 %s" % CM.held_name(_rid16), _p16, CC.relic_study)
    CM.reveal(_p16, _rid16)
_b16b = _book_of(_p16, CC.codex_relic)
_ev16 = {_r: CM.evidence(_r) for _r in ("unid_rare", "unid_common", "i_horn_half")}
_has16 = [x for x in _b16b for _e in _ev16.values() if str(_e) and str(_e) in x]
chk("★ fix-n-small ② **认名之后不再贴端详那一层**（三个样本都试过：%s / %s / %s）· 认出后那一行照字出"
    % (_ev16["unid_rare"], _ev16["unid_common"], _ev16["i_horn_half"]),
    not _has16
    and all(any(str(BOOK["relic"][_r]["known"]) in x for x in _b16b) for _r in _ev16),
    "%s ← 残留：%s" % (_b16b, _has16))

# ⑤ 端详能重看**谱里已认出**的那一条（QA P3：旧物谱里正列着它，端详却回「背包里没有」）
_p15e = {"day": 1, "loc": "windmill_town", "node": "wt_gate_n",
         "books": {"relic": {"poi_stone_scripts": {"day": 1, "known": True}}}, "foot": {}}
_re15 = _run("端详 %s" % BOOK["relic"]["poi_stone_scripts"]["name"], _p15e, CC.relic_study)
chk("★ 手上没有、但**谱里记着**的那一条：端详照旧重看一遍（出「认出后那一行」，不再回「背包里没有」）",
    _re15 == [TX["SYS_CODEX_RELIC_KNOWN"]["value"]
              .replace("{name}", BOOK["relic"]["poi_stone_scripts"]["name"])
              .replace("{known}", BOOK["relic"]["poi_stone_scripts"]["known"])], _re15)
chk("★ 反证：谱里**没有**的名字仍旧 fail-closed（`SYS_CODEX_RELIC_NOHOLD`）· 也不落档",
    _run("端详 从来没见过的东西", _p15e, CC.relic_study)
    == [TX["SYS_CODEX_RELIC_NOHOLD"]["value"].replace("{input}", "从来没见过的东西")]
    and CM.count(_p15e, "relic") == 1, _p15e["books"])
chk("★ 重看是只读的：该档一个字没动（`studied` 也没被写上）",
    _run("端详 %s" % BOOK["relic"]["poi_stone_scripts"]["name"], _p15e, CC.relic_study) == _re15
    and not CM.studied(_p15e, "poi_stone_scripts"))

# ⑯ ★ 宿主注入是增量口径（引擎 L2711）—— `facade.HANDLES` 与 `persistence._H`
#   不得对同一批句柄给出不同答案；且二贡调用不得把前一次的句柄抹掉。
_fac2_seen = []
_fac2_log = lambda _m, *_a, **_k: _fac2_seen.append(_m)      # noqa: E731
FAC2.bind_host(clock=lambda: _FIX, log=_fac2_log, db_path=_HANDLES["db_path"])
_fac2_first_keys = set(FAC2.HANDLES)                             # 首次注入的键集
FAC2.bind_host(clock=lambda: _FIX)                                # 只给钟（增量）
FAC2.log("after-second-bind")
chk("★ 宿主句柄是增量的：只重绑钟不得抹掉前一次的 `log`（旧写法静默丢日志）",
    _fac2_seen == ["after-second-bind"], "实收到：%s" % _fac2_seen)
#   形态：旧写法下 `HANDLES` 只剩 `{clock}`、`_H` 仍有 6 键 ⇒ 两边不一致。
#   口径用「注入过的键都还在 HANDLES 里」表述 —— 不用「`HANDLES` 包含 `_H`」
#   那个方向（`persistence.bind(**HANDLES)` 永远保证它，写成判据就是恒真）。
chk("★ 两边句柄不出两个真相：注入过的键一个都不能从 `HANDLES` 里消失",
    set(_fac2_first_keys) <= set(FAC2.HANDLES),
    "首次注入=%s / 二次后 HANDLES=%s" % (sorted(_fac2_first_keys), sorted(FAC2.HANDLES)))
FAC2.bind_host(**_HANDLES)                                        # 还原

print()
print("⑰ ★ 2026-09-30 审计残余 #15：`book_label` 盖满 `BOOKS` · `label()` fail-closed")
#   ★ 为什么门禁放**这里**（不是 `rebuild_codex.py` 自检）：`book_label` 是生成器写出来的
#     那一格，但「产出缺一格」要看的是**产物**（`content/data/codex.json`）—— 本探针每轮
#     基线都跑、牙齿常驻；生成器只在有人重跑时自检，手编/漏跑都照不到。
#   ★ `BOOKS` 一律现算 `content.codex.BOOKS`（不抄本文件上面那个同名元组 —— 抄一份就两处口径）。
_bl17 = dict((CM.meta() or {}).get("book_label") or {})
chk("★ ⑰ `_meta.book_label ⊇ BOOKS`（现算 = `codex.BOOKS`：%s）—— 缺一格那本谱的谱名就没出处"
    % (list(CM.BOOKS),), set(CM.BOOKS) <= set(_bl17),
    "缺：%s" % (sorted(set(CM.BOOKS) - set(_bl17)) or "无"))
try:
    _names17 = {b: CM.label(b) for b in CM.BOOKS}
    _err17 = ""
except Exception as exc:                                             # noqa: BLE001 —— 抛就是红
    _names17, _err17 = {}, "%s: %s" % (type(exc).__name__, exc)
chk("★ ⑰ 四本谱的谱名都取得到 · 都不是机器键（`label()` 的正向跑）",
    not _err17 and all(str(v).strip() and v != b for b, v in _names17.items()),
    _err17 or _names17)
#   反证：喂一个 `book_label` 里没有的谱 id ⇒ 必须**当场抛**（`or name` 那条回落路已封）。
try:
    CM.label("__no_such_book__")
    _err17b = "没抛 —— 机器键回落又活了"
except KeyError:
    _err17b = ""
except Exception as exc:                                             # noqa: BLE001
    _err17b = "抛是抛了，但不是 KeyError：%s: %s" % (type(exc).__name__, exc)
chk("★ ⑰ 反证：谱名缺格当场抛（不回落成机器键）", not _err17b, _err17b)

print()
print("按谱：%s" % " · ".join("%s %d" % (LABEL[b], len(BOOK[b])) for b in BOOKS))
print("旧物谱：读的 %d · 捡的 %d" % (len(read_ids), len(pick_ids)))
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(1 if not ok else 0)
