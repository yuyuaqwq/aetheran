# -*- coding: utf-8 -*-
"""探针：monsters 域 —— 字段齐全 · 八原型/五档位合法 · ★ panel 可复算 · Boss 有阶段卡。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_monsters.py
"""
from __future__ import annotations

import os
import time
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402
import rebuild_monsters as RB                                        # noqa: E402

ok = True
ARCHS = set(RB.ARCH)
ROLES = {"普通", "精英", "头目", "层主", "boss"}
PANEL_KEYS = {"hp", "atk", "def", "res", "spd", "hit", "eva", "crit"}


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


print("探针：monsters 域（16 只怪 + Boss）")
st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
st.install()
mo = st.domain("monsters")
chk("monsters 域读得到", mo is not None, "%d 条" % (len(mo) if mo else 0))
if not mo:
    sys.exit(1)

# ① 字段
bad1 = [k for k, v in mo.items() if not all(f in v for f in ("name", "archetype", "role", "lv", "panel", "mods"))]
chk("必填字段齐全", not bad1, " · ".join(bad1))

# ② 原型 / 档位合法
chk("archetype 都在八原型里", not [k for k, v in mo.items() if v["archetype"] not in ARCHS])
chk("role 都在五档位里", not [k for k, v in mo.items() if v["role"] not in ROLES])

# ②之二 ★ B3-6b-2d-keys-2：档位机器键 `role_key`（P-20 甲案第二刀）—— **三头对账**：
#   schema enum（唯一真源） ↔ 生成器那张表（`RB.ROLE_KEY`） ↔ 域里 17 条。
#   为什么三头都要核：表漂了 / enum 漂了 / 数据漂了，任何一种都会让「代码比 A、域里写 B」
#   静默不命中（改成 ASCII 键之后最怕的就是这个）。
import io as _io                                                       # noqa: E402
import json as _json                                                   # noqa: E402
_RK_ENUM = set(_json.load(_io.open(str(REPO / "schemas" / "monsters.schema.json"), encoding="utf-8"))
               ["patternProperties"]["^ms_[a-z_]+$"]["properties"]["role_key"]["enum"])
bad2b = [k for k, v in mo.items() if v.get("role_key") not in _RK_ENUM]
chk("★ 每只怪都带 `role_key` 且值都在 schema 的 enum 里（%s）" % "/".join(sorted(_RK_ENUM)),
    not bad2b, "缺/非法：%s" % bad2b)
chk("★ 生成器映射表 == schema enum（%s）"
    % " · ".join("%s→%s" % kv for kv in sorted(RB.ROLE_KEY.items())),
    set(RB.ROLE_KEY.values()) == _RK_ENUM,
    "表=%s / enum=%s" % (sorted(set(RB.ROLE_KEY.values()) - _RK_ENUM),
                         sorted(_RK_ENUM - set(RB.ROLE_KEY.values()))))
_r2k: dict = {}
for _v in mo.values():
    _r2k.setdefault(_v["role"], set()).add(_v.get("role_key"))
chk("★ 中文 role → ASCII role_key 是**单射**且与生成器表逐条一致（域自己就是那张映射表）",
    all(len(_s) == 1 and RB.ROLE_KEY[_r] == sorted(_s)[0] for _r, _s in _r2k.items()),
    "%s" % {a: sorted(b) for a, b in _r2k.items() if len(b) != 1})
chk("★ 五档全盖到（%s）" % "/".join(sorted({v["role_key"] for v in mo.values()})),
    {v["role_key"] for v in mo.values()} == _RK_ENUM)
_boss_ids = sorted(k for k, v in mo.items() if v.get("role_key") == "boss")
chk("★ 「是不是 BOSS」换键前后**同一只**（`role_key == \"boss\"` 命中的 = `role == \"boss\"` 命中的：%s）"
    % (_boss_ids or "一只都没有"),
    _boss_ids == sorted(k for k, v in mo.items() if v.get("role") == "boss") and len(_boss_ids) == 1)
_boss_zh = sorted(_r for _r, _k in RB.ROLE_KEY.items() if _k == "boss")
chk("★ `boss` 这个键只从**那唯一一档**来（表里 = %s）—— 头目 / 层主 的键不是 boss"
    % "/".join(_boss_zh),
    _boss_zh == ["boss"] and len(RB.ROLE_KEY) == len(set(RB.ROLE_KEY.values()))
    and not [k for k, v in mo.items() if v.get("role_key") == "boss" and v.get("role") != (_boss_zh or [""])[0]])

# ③ panel 键齐
bad3 = [k for k, v in mo.items() if set(v["panel"]) - PANEL_KEYS]
chk("panel 键都在约定集合里", not bad3, " · ".join(bad3))

# ④ ★ 可复算：用同一套算法重算，逐只对比
bad4 = []
for name, tier, lv, arch in RB.MOS:
    rec = next((v for v in mo.values() if v["name"] == name), None)
    if not rec:
        bad4.append("%s 不在域里" % name); continue
    want = RB.panel_of(lv, tier, arch)
    for k, wv in want.items():
        if abs(float(rec["panel"].get(k, -1)) - round(float(wv))) > 0.06:   # 取整口径
            bad4.append("%s.%s 包=%s 算=%s" % (name, k, rec["panel"].get(k), wv))
chk("★ panel 逐只可复算（档位 × 原型偏移）", not bad4, " · ".join(bad4[:4]))

# ⑤ 精英怪都有词条池（3 条）；Boss 不该有
by_role = {}
for v in mo.values():
    by_role.setdefault(v["role"], []).append(v)
bad5 = [v["name"] for v in by_role.get("普通", []) + by_role.get("精英", []) + by_role.get("头目", []) + by_role.get("层主", [])
        if len(v.get("elite_pool", [])) != 3]
chk("非 Boss 的怪都有 3 条精英词条", not bad5, " · ".join(bad5))
bad5b = [v["name"] for v in by_role.get("boss", []) if v.get("elite_pool")]
chk("Boss 不带精英词条（它自己的阶段就是机制）", not bad5b)

# ⑥ Boss 有阶段卡
boss = by_role.get("boss", [])
chk("Boss 存在且带阶段卡", bool(boss) and len(boss[0]["mods"].get("phases", [])) >= 3,
    "%s · %d 阶段" % (boss[0]["name"], len(boss[0]["mods"].get("phases", []))) if boss else "")

# ⑦ 档位分布
print("  · 档位分布：" + " · ".join("%s %d" % (r, len(vs)) for r, vs in sorted(by_role.items())))
print("  · 原型分布：" + " · ".join("%s %d" % (a, sum(1 for v in mo.values() if v["archetype"] == a))
                                    for a in sorted(ARCHS)))

# ⑧ ★ B3-7：`habitat` 的形状 + 跨域（monsters ↔ maps）—— 每条怪的栖息地都要落在真图上
MP = st.domain("maps") or {}
TOWER = "old_watchtower"
hb_bad = []
for k, v in mo.items():
    hb = v.get("habitat") or {}
    maps_ = [str(x) for x in (hb.get("maps") or [])]
    if not maps_:
        hb_bad.append((k, "没有 maps（哪儿都不出）"))
        continue
    for mk in maps_:
        if mk not in MP:
            hb_bad.append((k, "图不存在", mk))
    room_ids = {str(n.get("id")) for mk in maps_ if mk in MP
                for n in (MP[mk].get("nodes") or [])}
    for nd in (hb.get("nodes") or []):
        if str(nd) not in room_ids:
            hb_bad.append((k, "节点不在那几张图上", nd))
chk("★ 每条怪的 habitat.maps / habitat.nodes 都落在真图真节点上（%d 只）" % len(mo),
    not hb_bad, "%s" % hb_bad[:4])


def cands(loc, node):
    """这一格上按 `habitat` 算得进候选的那几只（与 `combat.pick_encounter` 同一套规则）。"""
    out = []
    for k, m in mo.items():
        hb = m.get("habitat") or {}
        if loc not in (hb.get("maps") or []):
            continue
        ns = hb.get("nodes") or []
        if ns and node not in ns:
            continue
        out.append(k)
    return out


# ⑨ 没有空挂的怪（每条怪在它自己说的那几张图的某个节点上真的算得进候选）
orphan = [k for k, m in mo.items()
          if not any(k in cands(mk, str(n.get("id")))
                     for mk in ((m.get("habitat") or {}).get("maps") or [])
                     for n in ((MP.get(mk) or {}).get("nodes") or []))]
chk("★ 没有空挂的怪（每条怪在它自己说的那几张图上都有落点）", not orphan, "%s" % orphan)

# ⑩ ★ 层主 / Boss 只在旧哨塔（真调 pick_encounter 扫种子 —— 野外五张图 + 村镇一只都挑不出来）
CB = st.optional_submodule("combat")
HEAVY = sorted(k for k, v in mo.items() if v.get("role") in ("层主", "boss"))
leak, tw_hits = [], {}
for mk, mv in MP.items():
    for n in (mv.get("nodes") or []):
        got = {tuple(CB.pick_encounter(mo, mk, str(n.get("id")), 14, seed=s)) for s in range(40)}
        hit = sorted(g[0] for g in got if g and g[0] in HEAVY)
        if not hit:
            continue
        if mk == TOWER:
            tw_hits[str(n.get("id"))] = hit
        else:
            leak.append((mk, str(n.get("id")), hit))
chk("★ 层主 / Boss 只在旧哨塔（野外与村镇真扫 40 个种子：一只都挑不出来）", not leak, "%s" % leak[:3])
chk("★ 塔里的层主 / Boss 真挑得出来（%s）"
    % " · ".join("%s=%s" % (k, "+".join(mo[x]["name"] for x in v)) for k, v in sorted(tw_hits.items())),
    sorted(x for v in tw_hits.values() for x in v) == HEAVY, "%s" % tw_hits)
print("  · 旧哨塔逐间候选（按 habitat 算）："
      + " · ".join("%s=%s" % (n.get("name"),
                              "+".join(mo[k]["name"] for k in cands(TOWER, str(n.get("id")))) or "（无）")
                   for n in ((MP.get(TOWER) or {}).get("nodes") or [])))
# ⑪ ★ B3-14：普攻口径那一把尺**两处同值**（本文件只读 JSON ⇒ 那份是副本）
#   `rebuild_monsters.K_RATE`（数值→率）必须 == `content/panel_build.K_RATE`（战斗侧真用的那个），
#   否则怪 hp 的反推式与实机伤害各按各的尺算 ⇒ 击杀行动数系统性偏（B3-14 实测差 ~30%）。
sys.path.insert(0, str(REPO))
from content import panel_build as _PB                                    # noqa: E402
chk("★ 数值→率那把尺两处同值（rebuild_monsters.K_RATE=%s == panel_build.K_RATE=%s）"
    % (RB.K_RATE, _PB.K_RATE), RB.K_RATE == _PB.K_RATE)
chk("★ 暴击期望系数与 `_budget.py` 同值（1 + 率 × 0.5）", RB.CRIT_EXP == 0.5)

# ══════════════════════════════════════════════════════════════════════════════
# ★ B3-17：真源 `12_怪物面板与精英词条池_v1.md` **逐只对账**（探针自己解析文档 —— 不手抄镜像表）
#   上一批（B3-14）把 `per_hit` 的口径换过一次（现值 = 六职业**中位实际通道**伤害），
#   真源那张表是**换之前那一版**的快照 —— 所以「对不上」的那一列必须能**两侧各自复算**，
#   否则分不清「口径变更」与「手打偏了」。这一节的判据就是照这个分法立的。
# ══════════════════════════════════════════════════════════════════════════════
import re as _re2                                                       # noqa: E402

PLAN = os.environ.get("AST_PLAN", "C:/Users/yuyu/aetheran-plan")
DOC_DIR = os.path.join(PLAN, "06_第一阶段垂直切片")
DOC12 = os.path.join(DOC_DIR, "12_怪物面板与精英词条池_v1.md")
DOC14 = os.path.join(DOC_DIR, "14_怪物原型_v1.md")
DOC22 = os.path.join(DOC_DIR, "22_旧哨塔_逐间设计_v1.md")
D12 = _io.open(DOC12, encoding="utf-8").read()
D14 = _io.open(DOC14, encoding="utf-8").read()
D22 = _io.open(DOC22, encoding="utf-8").read()
BY_NAME = {v["name"]: v for v in mo.values()}


def _table(sec: str, need=10):
    """把一小节里的 markdown 表切出来（跳过分隔行与表头）—— 一律**现解析**。"""
    out = []
    for ln in sec.splitlines():
        if not ln.startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if len(cells) < need:
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue
        out.append(cells)
    return out[1:]                     # 第一行是表头


print()
print("── ★ B3-17 ⑫ 真源 §一 那张面板表 ↔ 域（逐只 · 逐列）")
_R1 = _table(D12.split("## 一、")[1].split("## 二、")[0])
_COLS = (("atk", "atk"), ("def", "def"), ("spd", "spd"), ("hit", "hit"), ("eva", "eva"), ("crit", "crit"))
chk("★ §一 表 17 行 · 名字与域两边相等（不多不少）",
    len(_R1) == 17 and {r[0] for r in _R1} == set(BY_NAME), "%d 行" % len(_R1))
_bad_a, _bad_hp_v1, _bad_hp_now = [], [], []
for _r in _R1:
    _name, _tier, _lv = _r[0], _r[1], int(_r[2])
    _v = BY_NAME.get(_name)
    if not _v:
        _bad_a.append("%s 不在域里" % _name)
        continue
    _arch = _v["archetype"]
    if _v["lv"] != _lv or _v["role"] != _tier:
        _bad_a.append("%s 档/级 域=%s/%s 档=%s/%s" % (_name, _v["role"], _v["lv"], _tier, _lv))
    _v1 = RB.panel_of_v1(_lv, _tier, _arch)
    for _i, (_dk, _pk) in enumerate(_COLS, 4):          # hp 在第 3 列（下标 3），其余从下标 4 起
        if int(_r[_i]) != int(_v1[_pk]):
            _bad_a.append("%s.%s v1算=%s 档=%s" % (_name, _pk, _v1[_pk], _r[_i]))
    if int(_r[3]) != RB.panel_of_v1(_lv, _tier, _arch)["hp"]:
        _bad_hp_v1.append("%s 档=%s 旧口径算=%s" % (_name, _r[3], RB.panel_of_v1(_lv, _tier, _arch)["hp"]))
    if int(_v["panel"]["hp"]) != RB.panel_of(_lv, _tier, _arch)["hp"]:
        _bad_hp_now.append(_name)
chk("★ §一 的非 hp 列（atk/def/spd/hit/eva/crit）**逐只 == 上一版口径复算**（`RB.panel_of_v1`）"
    "⇒ 那张表**整个**是 v1 快照（★ B3-18 换口径后域不再是 v1 ⇒ 该跟表对的是 v1，不是域）",
    not _bad_a, " · ".join(_bad_a[:4]))
chk("★ §一 的 hp 列**逐只 == 上一版口径复算**（`RB.panel_of_v1`）⇒ 它是那一版的快照，**不是手打偏的**",
    not _bad_hp_v1, " · ".join(_bad_hp_v1[:3]))
chk("★ 域的 hp**逐只 == 现口径复算**（`RB.panel_of`）⇒ 差异的两侧各自可复算（= 一次口径变更）",
    not _bad_hp_now, "%s" % _bad_hp_now[:3])
_n_diff = sum(1 for _r in _R1 if int(_r[3]) != int(BY_NAME[_r[0]]["panel"]["hp"]))
print("     · hp 列对不上的有 %d/%d 只（那一列的差 = B3-14 那次 per_hit 口径修正，逐只可复算）"
      % (_n_diff, len(_R1)))

print()
print("── ★ B3-17 ⑬ 真源 §二 那张词条池表 ↔ 域（逐只）")
_R2 = _table(D12.split("## 二、")[1].split("## 三、")[0], need=3)
chk("★ §二 表 17 行 · 名字与域两边相等（不多不少）",
    len(_R2) == 17 and {r[0] for r in _R2} == set(BY_NAME), "%d 行" % len(_R2))
_bad_pool = []
for _r in _R2:
    _v = BY_NAME.get(_r[0])
    if not _v:
        _bad_pool.append("%s 不在域里" % _r[0])
        continue
    _cell = _r[2]
    _dom = list(_v.get("elite_pool") or [])
    if _cell.startswith("（"):                    # Boss 那一格写的是说明，不是池子
        if _dom:
            _bad_pool.append("%s 档那格是说明、域里却有 %s" % (_r[0], _dom))
        continue
    _n = len([x for x in _re2.split(r"[·、]", _cell) if x.strip()])
    if _n != len(_dom) or _n != 3:
        _bad_pool.append("%s 档 %d 条 / 域 %d 条" % (_r[0], _n, len(_dom)))
chk("★ 每只怪的词条池**条数**与文档一致（3 条）· Boss 那一格是说明 ⇒ 域里必须空",
    not _bad_pool, " · ".join(_bad_pool[:4]))
print("     · ★ 19 个 `af_*` id **全仓库没有定义表**（09_ §七 点名要建 `elite` 域 / `monster_mods` 表，"
      "09_ §三 只写了 16 条词条口径、而 §二 用了 19 个名字）⇒ 建表要补 4 条效果与 PE，属**待拍板**，"
      "本批只登记（见 _notes.md §四·1）")

print()
print("── ★ B3-17 ⑭ Boss 阶段卡 ↔ 真源（`22_ §二·12` 的四阶段 + `14_ §四` 那行）")
_blk22 = D22.split("### 三层 · 12 · 塔顶")[1].split("### ")[0]
_ph22 = " ".join(_re2.findall(r"^\s*(?:Boss|→).*$", _blk22, _re2.M)) or \
        " ".join(ln.strip() for ln in _blk22.splitlines() if ln.strip().startswith(("Boss", "→")))
_line14 = next((ln.strip() for ln in D14.splitlines() if ln.strip().startswith("站桩：")), "")
# 22 那一行是「Boss 旧誓哨兵（四阶段卡）：站桩 → 列阵（…）→ 散架（…）→ 回塔（…）」
#   ⇒ 按「→」切成 4 段；**第一段**的名字在「：」之后，其余段的名字在「（」之前
#     （★ skill §十 的坑①：小标题/括注那一截不是名字，先切掉再用）。
_seg22 = _ph22.split("→") if _ph22.count("→") >= 3 else []
_names22 = ([_seg22[0].split("：")[-1].strip()] +
            [_re2.split(r"（", x.strip())[0].strip() for x in _seg22[1:]]) if _seg22 else []
#: 每段自己的那段字（数只在**这一段**里找 —— 跨段搜会把 列阵 的 def+60 当成 散架 的）
_txt22 = {_names22[i]: _seg22[i] for i in range(len(_names22))} if _seg22 else {}
_names14 = [x.split("：")[0].strip() for x in _line14.split("→")] if _line14 else []
_phases = (boss[0]["mods"].get("phases") or []) if boss else []
chk("★ 两处文档给的阶段名序列一致且 == 域里那 4 阶（%s）"
    % " → ".join(p.get("name", "") for p in _phases),
    _names22 == _names14 == [p.get("name") for p in _phases] == ["站桩", "列阵", "散架", "回塔"],
    "22=%s / 14=%s" % (_names22, _names14))


def _num(text, pat, cast=float):
    m = _re2.search(pat, text)
    return cast(m.group(1)) if m else None


_want = (("列阵", "atk_mult", r"列阵（atk×([\d.]+)"), ("列阵", "def_add", r"def\+(\d+)"),
         ("列阵", "turns", r"def\+\d+ · (\d+) 次"), ("散架", "atk_mult", r"散架（atk×([\d.]+)"),
         ("散架", "def_add", r"def([−+-])(\d+)"), ("散架", "dmg_taken_mult", r"受伤×([\d.]+)"),
         ("散架", "act_rate_mult", r"频率×([\d.]+)"), ("散架", "turns", r"频率×[\d.]+ · (\d+) 次"))
_by_ph = {p.get("name"): p for p in _phases}
_bad_ph = []
for _pn, _k, _pat in _want:
    _txt = _txt22.get(_pn, "")
    if _k == "def_add" and _pn == "散架":          # 减号（全角 U+2212 / 半角）要连符号一起认
        _m = _re2.search(_pat, _txt)
        _doc = -(float(_m.group(2))) if _m else None
    else:
        _doc = _num(_txt, _pat)
    _dom = _by_ph.get(_pn, {}).get(_k)
    if _doc is None:
        _bad_ph.append("22 里没解析出 %s.%s（pattern=%s）" % (_pn, _k, _pat))
    elif abs(float(_dom if _dom is not None else -999) - float(_doc)) > 1e-6:
        _bad_ph.append("%s.%s 域=%s 档=%s" % (_pn, _k, _dom, _doc))
    if _pn == "散架" and _k in ("dmg_taken_mult", "turns"):
        _d14 = _num(_line14, r"受伤×([\d.]+)") if _k == "dmg_taken_mult" else \
            _num(_line14, r"受伤×[\d.]+ · (\d+) 次行动")
        if _d14 is not None and abs(float(_dom or -999) - float(_d14)) > 1e-6:
            _bad_ph.append("散架.%s 14 号那份=%s 域=%s" % (_k, _d14, _dom))
chk("★ 阶段卡的数**逐项**对得上（列阵 atk×1.3 / def+60 / 8 次 · 散架 atk×0.8 / def−120 / "
    "受伤×1.4 / 频率×0.5 / 5 次）—— 22_ §二·12 与 14_ §四 两处都核", not _bad_ph,
    " · ".join(_bad_ph[:4]))
_hp_doc14 = _num(D14, r"旧誓哨兵（Lv19）：hp (\d+)", int)
_ar = RB.ARCH[boss[0]["archetype"]] if boss else {}
_rel = [k for k, m in (("hp", _ar.get("hp")), ("atk", _ar.get("atk")),
                       ("def", _ar.get("def")), ("spd", _ar.get("spd"))) if m and abs(m - 1.0) > 1e-9]
print("     · ★ 已经登记的**真源两处打架**（不当判据 · 只登记）：14_ §四 写 Boss「不用原型偏移」"
      "（hp 7340 · atk 32.6 · def 62.5 · spd 102 = 域那一套 ÷原型偏移 %s），而 12_ §一 表那行的数"
      "是**带原型偏移**的（域今天也是带偏移的）⇒ 见 _notes.md §四·2"
      % ("/".join("%s×%s" % (k, _ar[k]) for k in ("hp", "atk", "def", "spd")) if _rel else "无"))
chk("★ `14_ §四` 那个 hp 与 `12_ §一④` 正文那句 hp 是**同一个数**（两处互相印证，只是都跟表打架）",
    _hp_doc14 is not None and ("hp %s" % _hp_doc14) in D12.split("## 二、")[0],
    "14 说 %s" % _hp_doc14)

print()
print("── ★ B3-17 ⑮ 单人档（`mods.party_scale`）：生成器那张表 == 域 == 只有团队内容带")
_ps = {k: (v.get("mods") or {}).get("party_scale") for k, v in mo.items()}
_have = {k: v for k, v in _ps.items() if v}
chk("★ 带 `party_scale` 的只有生成器点名的那几只（%s）"
    % " · ".join(mo[k]["name"] for k in sorted(_have)),
    sorted(_have) == sorted(RB.PARTY_SCALE_ON), "%s" % sorted(_have))
chk("★ 域里的单人档 == 生成器唯一来源那张表（%s）"
    % " · ".join("%s 人 → %s" % (n, "+".join("%s×%s" % kv for kv in sorted(v.items())))
                 for n, v in sorted(RB.PARTY_SCALE.items())),
    all(_have.get(k) == {n: dict(v) for n, v in RB.PARTY_SCALE.items()} for k in RB.PARTY_SCALE_ON)
    and len(_have) == len(RB.PARTY_SCALE_ON), "%s" % _have)
_doc_half = "按 ÷2 看" in D12 and "Boss 血按 ÷2 看" in _io.open(
    os.path.join(DOC_DIR, "17_组队与策略配合_v1.md"), encoding="utf-8").read()
chk("★ 那个 ÷2 是文档给的数（12_ §一④「单人挑战时按 ÷2 看」· 17_ §五「Boss 血按 ÷2 看」）"
    "⇒ 表里 = 0.5（不手打、不猜）",
    _doc_half and all(abs(float(RB.PARTY_SCALE["1"]["hp"]) - 0.5) < 1e-9 for _ in (0,)), "hp×0.5")
chk("★ 文档**没给数**的人数（2 / 3 人）表里不写 ⇒ 查不到就按设计值走（fail-closed 在 `combat.party_scale_of`）",
    set(RB.PARTY_SCALE) == {"1"}, "%s" % sorted(RB.PARTY_SCALE))

# ⑬ ★ B3-18：**常数三头对账** —— 反解用的 K_def/K_rate 必须来自公式表 `$const`
#   （引擎真读的那一份），而 panel_build 那份副本也必须同值。任何一头漂了 ⇒ 三把尺。
import io as _io2                                                         # noqa: E402
import json as _json2                                                     # noqa: E402
_C = _json2.loads(_io2.open(str(REPO / "content" / "rules" / "formula_table.json"),
                            encoding="utf-8").read())["$const"]
chk("★ 反解常数 = 公式表 $const（K_def=%s / K_rate=%s）· 与 panel_build 那份副本同值"
    % (_C["K_def"], _C["K_rate"]),
    RB.K_DEF == int(_C["K_def"]) and RB.K_RATE == int(_C["K_rate"])
    and RB.K_DEF == _PB.K_DEF and RB.K_RATE == _PB.K_RATE)

# ⑭ ★ B3-18：**档位单调** —— 「普通 < 精英 < 头目 < 层主 < boss」逐项成立。
#   ★ 2026-09-25 鱼鱼拍板分两条（`_notes.md` §三）：
#     def/spd：**跨原型全空间**（8 原型 × 5 档 × 6 锚点）—— 任意原型的高一档 > 任意原型的低一档；
#             原表的病灶正在这里（lv9 石滩螃蟹 def 29 > 精英伐木工 def 20）。
#     hp/atk ：只要**基准阶梯**（杂兵）严格；原型保 14 号原表全幅（δ=1）——
#             跨族倒挂是设计的一部分（群居血薄，它一次来 3–4 只）。
_mono_bad = RB.check_monotone(verbose=False)
chk("★ 档位单调（def/spd 跨原型全空间 + hp/atk 基准阶梯 · 8 原型 × 5 档 × %d 锚点）："
    "任意原型的高一档 > 任意原型的低一档（def/spd）· 基准高档 > 基准低档（hp/atk）"
    % len(RB.ANCHORS), not _mono_bad, " · ".join(_mono_bad[:3]))

# ⑮ ★ B3-18：**交换余量**（打得过的预算）—— n_them/n_me 是「它杀我要几下 / 我要打它几下」之比。
#   实机扫描（`scripts/balance_sweep.py` 的层主扫描）测得「单刷能赢」的边界 ≈ 1.0–1.2，
#   这条钉 **≥ 1.05**；★ 按**域里真实存在的那 17 只**逐只算（hp/atk 保了原型全幅之后，
#   基准值本身不再是「那只怪」）—— 精细验收仍归 probe_combat ④（真跑 36 局）。
#   Boss 反过来必须 < 0.8（它是 4 人队内容 ⇒ 单人必倒地）。
_g = {}
for _name, _tier, _lv, _arch in RB.MOS:
    _g[_name] = (RB.TIERS[_tier]["n_them"] / RB.design_ttk(_tier, _arch)[0], _tier)
_solo = {k: v[0] for k, v in _g.items() if v[1] != "boss"}
_boss_g = next(v[0] for v in _g.values() if v[1] == "boss")
chk("★ 16 只非 Boss 的交换余量 ≥ 1.05（最小 %.2f：%s）"
    % (min(_solo.values()), min(_solo, key=_solo.get)),
    all(v >= 1.05 for v in _solo.values()))
chk("★ Boss 的交换余量 < 0.8（%.2f —— 单人必倒地，4 人队才打得完）"
    % _boss_g, _boss_g < 0.8)

# ⑯ ★ B3-18：**单源** —— 档位/原型两张表只在 `content/rules/monster_tiers.json` 里，
#   代码不许再抄第二份（`ARCH`/`TIERS` 必须是那个文件的对象本身，不是重建的副本）。
_tj = _json2.loads(_io2.open(str(REPO / "content" / "rules" / "monster_tiers.json"),
                             encoding="utf-8").read())
chk("★ 档位/原型表唯一来源 = content/rules/monster_tiers.json（%d 档 × %d 原型）"
    % (len(_tj["tiers"]), len(_tj["arch"])),
    RB.TIERS == _tj["tiers"] and RB.ARCH == _tj["arch"]
    and set(RB.TIERS) == set(RB.TIER_ORDER) and set(RB.ARCH) == set(ARCHS))

print()
print("  · 档位 × 原型的 δ（保序压幅）：%s"
      % " · ".join("%s %.3f" % (k, v) for k, v in sorted(RB.delta_of().items())))
print("  · 交换余量 g = n_them/n_me（基准）：%s"
      % " · ".join("%s %.2f" % (t, RB.TIERS[t]["n_them"] / RB.TIERS[t]["n_me"]) for t in RB.TIER_ORDER))
print("  · 交换余量（17 只实际）：最小 %.2f（%s）· 最大 %.2f"
      % (min(v[0] for v in _g.values()), min(_g, key=lambda k: _g[k][0]), max(v[0] for v in _g.values())))

print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
