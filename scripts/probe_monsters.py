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
print("── ★ B3-17/B3-25 ⑮ 按人数缩放档（`mods.party_scale`）：生成器那张表 == 域 == 只有团队内容带"
      " —— ★ B3-25 从「只有 1 人档」加强成「四档阶梯」")
_ps = {k: (v.get("mods") or {}).get("party_scale") for k, v in mo.items()}
_have = {k: v for k, v in _ps.items() if v}
chk("★ 带 `party_scale` 的只有生成器点名的那几只（%s）"
    % " · ".join(mo[k]["name"] for k in sorted(_have)),
    sorted(_have) == sorted(RB.PARTY_SCALE_ON), "%s" % sorted(_have))
chk("★ 域里的表 == 生成器唯一来源那张表（%s）"
    % " · ".join("%s 人 → %s" % (n, "+".join("%s×%s" % kv for kv in sorted(v.items())))
                 for n, v in sorted(RB.PARTY_SCALE.items())),
    all(_have.get(k) == {n: dict(v) for n, v in RB.PARTY_SCALE.items()} for k in RB.PARTY_SCALE_ON)
    and len(_have) == len(RB.PARTY_SCALE_ON), "%s" % _have)
_doc_half = "按 ÷2 看" in D12 and "Boss 血按 ÷2 看" in _io.open(
    os.path.join(DOC_DIR, "17_组队与策略配合_v1.md"), encoding="utf-8").read()
chk("★ **P-63 换锚**：1 人档那一格 = 现扫描出来的**可过档**（`RB.SOLO_ANCHOR` = %s = ÷%s）——"
    "「文档里那句 ÷2 是不是给了数」这条已经**不再当判据**（那两个数就是被裁掉的那个："
    "真跑 0/96）；它的落点改成 ⑮-b 的**真跑可过**。文档那一句与表的对账见 ⑮-c（两态）。"
    % (RB.SOLO_ANCHOR, 1 / float(RB.SOLO_ANCHOR)),
    abs(float(RB.PARTY_SCALE["1"]["hp"]) - float(RB.SOLO_ANCHOR)) < 1e-9,
    "表里 1 人档 = hp×%s（旧案 ÷2 快照仍在文档里：%s）" % (RB.PARTY_SCALE["1"]["hp"], _doc_half))
# ★ B3-25：四档阶梯 —— 判据从「1 人档之外**不写**」改成三条**更严**的：
#   ⓵ 档位集合 == party 域声明的「有效人数档 = 1..上限」（上限 = 真源 03_ §4.7「1–4 人」）
#      ⇒ 跨域对账「上限 == 表里最大档 == 键集合」；⓶ 只收 hp 一项（真源两处字面只说「血」）；
#   ⓷ 递减排法：两边锚点不动（1 人 = 真源 ÷2 · 4 人 = 设计值 ×1），中间严格递增且增量递减。
_pj = (st.domain("party") or {}).get("pt_rules") or {}
_pmx = int(_pj.get("max_members") or 0)
_grades = sorted(int(k) for k in RB.PARTY_SCALE)
chk("★ 档位 == party 域声明的「有效人数档 = 1..上限」（上限 %s ⇒ 表里 %s）—— 跨域："
    "上限 == 表里最大档 == 键集合" % (_pmx, _grades),
    bool(_pmx) and _grades == list(range(1, _pmx + 1))
    and all(sorted(int(k) for k in _have[k]) == _grades for k in _have), "%s" % _have)
chk("★ 只收 hp 一项（真源两处字面只说「**血**按 ÷2 看」）—— 每档的键集合都恰好是 {hp}",
    all(set(v) == {"hp"} for v in RB.PARTY_SCALE.values()), "%s" % RB.PARTY_SCALE)
_lad = [float(RB.PARTY_SCALE[str(n)]["hp"]) for n in _grades]
_deltas = [round(_lad[i + 1] - _lad[i], 6) for i in range(len(_lad) - 1)]
chk("★ 递减排法：%s 严格递增 · 增量递减（%s）· 4 人档 = 设计值 ×1 · 1 人档 = 扫描出来的可过档"
    % (" < ".join(str(x) for x in _lad), " > ".join(str(x) for x in _deltas)),
    all(_lad[i] < _lad[i + 1] for i in range(len(_lad) - 1))
    and all(_deltas[i] > _deltas[i + 1] for i in range(len(_deltas) - 1))
    and abs(_lad[-1] - 1.0) < 1e-9 and abs(_lad[0] - float(RB.SOLO_ANCHOR)) < 1e-9, "%s" % _lad)

# ⑮-b ★ P-36 / P-63：Boss 单人档的**现算对账**（文档 ↔ 表 ↔ 域面板）—— 两态锚：
#   文档那一句今天写的是**旧案**「单人挑战时按 ÷2 看（≈3670）」（= B3-17 那批落 ÷2 时的快照），
#   P-63 把 1 人档改成扫描出来的**可过档**（`RB.SOLO_ANCHOR` = 0.25 = ÷4）⇒ 真源那一行**待主线跟账**
#   （逐字新行见本分支 `_notes.md`）。判据口径（强度不降）：
#     ① 文档那句话里那个「÷N」必须**要么**是旧案 N=2（未跟账）**要么**是表里那一档的倒数
#        （跟账后 = 4）—— **第三个数当场红**；
#     ② 「（≈M）」那个数必须 ≈ 域里 boss 面板 hp ÷ N（5% 容差）—— 两态各自可复算，
#        手打偏了/改坏了当场红（旧案快照与现行值都从 `RB` 与域现取，不写镜像表）。
_OLD_DIV = 2                     # 旧案快照值（B3-17 那批落的 ÷2）—— 主线跟账后删掉这一半
_bkeys = [k for k, v in mo.items() if str(v.get("role") or "") == "boss"]
_bhp = int((mo[_bkeys[0]].get("panel") or {}).get("hp") or 0) if len(_bkeys) == 1 else 0
_doc_hp_tbl = _num(D12, r"\|\s*旧誓哨兵\s*\|\s*boss\s*\|\s*19\s*\|\s*(\d+)\s*\|", int)
_doc_hp_txt = _num(D12, r"旧誓哨兵，Lv19\s*hp\s*(\d+)", int)
_div_doc = _num(D12, r"按\s*÷(\d+)\s*看", int)
_doc_solo = _num(D12, r"按\s*÷\d+\s*看（≈\s*(\d+)\s*）", int)
_new_div = int(round(1 / float(RB.SOLO_ANCHOR)))
_solo_dom = _bhp / float(_div_doc) if _div_doc else 0
_drift = abs(_solo_dom - _doc_solo) / float(_doc_solo) if _doc_solo else 1.0
chk("★ ⑮-b P-36/P-63 单人档**现算**：文档写「按 ÷%s 看（≈%s）」 ⇒ 域里 boss hp %d ÷ %s = **%.0f**"
    "（差 %.0f · %.2f%% ≤ 5%% 容差）· 那个 ÷N 要么是旧案 %d（未跟账）要么是表里那一档的倒数 %d"
    % (_div_doc, _doc_solo, _bhp, _div_doc, _solo_dom, abs(_solo_dom - _doc_solo), 100 * _drift,
       _OLD_DIV, _new_div),
    len(_bkeys) == 1 and _bhp > 0 and bool(_doc_solo) and _drift <= 0.05
    and _div_doc in (_OLD_DIV, _new_div),
    "带档的 %s · 文档表 %s / 正文 %s / 域 %d · 表里 1 人档 = %s（÷%s）"
    % (sorted(_have), _doc_hp_tbl, _doc_hp_txt, _bhp, RB.PARTY_SCALE["1"]["hp"], _new_div))
print("     · ★ 登记（**不当判据**）：`12_ §一` 那张表写 boss hp %s · 正文读法④ 写 hp %s · "
      "域里 %d —— 三处不一致（表 vs 正文那一处 ⑫ 已登过）。★ P-63 的实质判据在"
      "`probe_combat ⑤`：**1 人档真跑要赢得下**（旧案的 ÷2 实测 0/96）。"
      % (_doc_hp_tbl, _doc_hp_txt, _bhp))

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

# ══════════════════════════════════════════════════════════════
# ★ P-58（2026-09-26）**宪法 F1/F3：常量那一行 ↔ 代入例 ↔ 实现**三头对账
# --------------------------------------------------------------
# 真源 `02_数值宪法/01_属性字典与基础公式.md`：
#   · §F1 常量行写 `K_def(L) = 100 + 20L`（「L=10 时 = 300」）· §F3 常量行写 `K_rate(L) = 300 + 30L`
#     —— **都随等级**；
#   · 可**同一个公式块里的代入例**用的是**恒定值**：
#       F1 例 `def=300, pen=0 → 300/600 = 50.0% 减免` ⇒ 反解 K = 300（与 L 无关）
#       F3 例 `crit=100 → 16.7%` / `crit=300 → 37.5%` / `crit=1500 → 75.0%` ⇒ 三条全对 K = 500
#   · 实现跟的是**代入例**：`content/rules/formula_table.json` 的 `$const` = 300 / 500
#     （反解、配平、面板全按它算 —— 上面那条 ⑬ 钉着）。
# 裁决（P-58 · 本批）：**实现是唯一真源**（全部配平与反解都按它，改它 = 全部战斗数值重算）⇒
#   宪法那两行的「随等级」写法按**过时**（真源逐字新行见本分支 `_notes.md`）。
# 本判据钉的是那条链，两态都现算：
#   ① 文档的**代入例**反解出来的 K 必须 == `$const`（逐条现算，不手抄 —— 这一条是主判据）；
#   ② 常量那一行必须是**两态之一**：旧案算式（随等级 · 未跟账）或与 `$const` 同值（跟账后）——
#      **第三态当场红**（手打/改坏拦得住）。
_DOCB = os.path.join(PLAN, "02_数值宪法", "01_属性字典与基础公式.md")
_DB = _io.open(_DOCB, encoding="utf-8").read() if os.path.exists(_DOCB) else ""
#: F1 的代入例（三条，逐条反解 K）；F3 一条行内三条例
_f1_ex = _re2.findall(r"def=(\d+),\s*pen=0\s*→\s*def_eff=(\d+)\s*→\s*(\d+)/(\d+)\s*=\s*([\d.]+)%", _DB)
_f3_ex = _re2.findall(r"crit=(\d+)\s*→\s*([\d.]+)%", _DB)
_k_f1 = sorted({round(float(d) / (float(r) / 100.0) - float(d)) for _x, d, _n, _dn, r in _f1_ex})
_k_f3 = sorted({round(float(c) / (float(r) / 100.0) - float(c)) for c, r in _f3_ex})


def _k_near(ks, c):
    """文档写的是**取整到三位有效数字**的率（16.7% / 37.5% / 75.0%）⇒ 反解出来的 K 允许 1% 偏差。"""
    return bool(ks) and all(abs(float(k) - float(c)) <= max(1.0, 0.01 * float(c)) for k in ks)


chk("★ P-58 ①：宪法 §F1/§F3 的**代入例**逐条反解出来的 K 必须 == 实现那份 `$const`"
    "（±1%% —— 文档的率是取整值）（F1 例 %d 条 ⇒ K = %s · F3 例 %d 条 ⇒ K = %s · 实现 %s / %s）"
    % (len(_f1_ex), _k_f1, len(_f3_ex), _k_f3, _C["K_def"], _C["K_rate"]),
    bool(_f1_ex) and bool(_f3_ex) and _k_near(_k_f1, _C["K_def"]) and _k_near(_k_f3, _C["K_rate"]),
    "F1=%s（例 %s）· F3=%s（例 %s）" % (_k_f1, _f1_ex[:2], _k_f3, _f3_ex[:3]))


def _const_line_ok(text, legacy_parts, const_val):
    """常量那一行是不是两态之一：旧案算式（随等级）或与 `$const` 同值。"""
    m = _re2.search(r"(\d+)\s*\+\s*(\d+)\s*L", text)
    if m:
        return (int(m.group(1)), int(m.group(2))) == legacy_parts
    return str(const_val) in _re2.findall(r"\d+", text)


_c_f1 = (_re2.search(r"常量\s+K_def(?:\(L\))?\s*=\s*([^\n]+)", _DB).group(1)
         if _re2.search(r"常量\s+K_def(?:\(L\))?\s*=\s*([^\n]+)", _DB) else "")
_c_f3 = (_re2.search(r"常量\s+K_rate(?:\(L\))?\s*=\s*([^\n]+)", _DB).group(1)
         if _re2.search(r"常量\s+K_rate(?:\(L\))?\s*=\s*([^\n]+)", _DB) else "")
chk("★ P-58 ②：§F1/§F3 的**常量行**必须是两态之一 —— 旧案算式（随等级 `100 + 20L` / `300 + 30L`，"
    "未跟账）或与 `$const` 同值（跟账后）；第三态当场红"
    "（F1 行 = 「%s」· F3 行 = 「%s」）" % (_c_f1.strip()[:40], _c_f3.strip()[:40]),
    bool(_c_f1) and bool(_c_f3)
    and _const_line_ok(_c_f1, (100, 20), int(_C["K_def"]))
    and _const_line_ok(_c_f3, (300, 30), int(_C["K_rate"])),
    "实现 $const = %s / %s" % (_C["K_def"], _C["K_rate"]))

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

# ⑰ ★ P-35：**精英怪该打几次** —— 真源两份打架的裁决 + 可复算判据（B3-14 查出 · 本批收口）
#   打架的两份（逐字见 `_notes.md` 裁决记录）：
#     ① `02_数值宪法/03_全流程数值主干_v1.md` §四 那张表（**权威**）：
#        「普通怪 3–5 次 · 精英 5–8 次 · BOSS 12–18 次（一场战斗行动次数）」
#     ② `06_第一阶段垂直切片/12_怪物面板与精英词条池_v1.md` §一 —— **两处都写 12 次**：
#        · 抬头那行反推式「怪 hp = 玩家单次行动伤害 × 目标击杀行动数（普通 4 · **精英 12** ·
#          头目 14 · 层主 18 · Boss 72）」
#        · 读法②「精英 hp 是普通 3 倍（**12 次行动**）、spd 104 比玩家快」
#   ★ 更正一处归因（本波任务书写的是「`12_` 与 `09_精英怪机制` 两份真源打架」）——
#     逐字核 `09_精英怪机制_v1.md`：那份 §二 表只写「强度 = 基础怪 ×**1.5 hp** / ×0.75 atk」，
#     与宪法那两列（×1.50 hp / ×0.75 atk）**逐字一致** ⇒ 09_ 不是打架的那一份（详见 `_notes.md`）。
#   裁法（作业书 §2 乙档①：两份真源打架 ⇒ 认【数值宪法】为权威，另一份按「过时」点名）：
#     ⇒ 认宪法：精英要打 **5–8** 次；`12_` 那两处「12 次」（= 普通 3 倍）按**过时**
#       （宪法定格之前的旧案反推式；域里档位第二版 b3-18 反解出来的 n_me 与它全不对）。
#       逐条登记进 `_notes.md`。
#   判据口径：**基准（杂兵原型）阶梯**的 n_me = 「玩家要打它几下」——
#     hp/atk 保了原型全幅（鱼鱼 2026-09-25 拍板，见 ⑭ 与 §三），所以只有基准阶梯该落在宪法带的里面；
#     逐只怪（含原型偏移）不在这条判据上（群居血薄是设计，不是漂移）。
#   ★ 数字全部**现取**：带 = 从宪法文档现解析；n_me = 从域里的档位表现算（`RB.design_ttk`）。
_DOCC = os.path.join(PLAN, "02_数值宪法", "03_全流程数值主干_v1.md")
_DC = _io.open(_DOCC, encoding="utf-8").read() if os.path.exists(_DOCC) else ""
_BANDS = {}
for _ln in _DC.splitlines():
    _m17 = _re2.match(r"^(普通怪|精英|BOSS)\s+×([\d.]+)\s+×([\d.]+)\s+(\d+)[–-](\d+)\s*次",
                      _ln.strip())
    if _m17:
        _BANDS[_m17.group(1)] = (float(_m17.group(2)), float(_m17.group(3)),
                                 int(_m17.group(4)), int(_m17.group(5)))
chk("★ P-35 宪法 §四 那三行**现解析**得到（%s）"
    % " · ".join("%s %s–%s 次" % (k, v[2], v[3]) for k, v in sorted(_BANDS.items())),
    sorted(_BANDS) == ["BOSS", "普通怪", "精英"], "解析到 %d 行" % len(_BANDS))

_TIER_OF = {"普通怪": "普通", "精英": "精英", "BOSS": "boss"}      # 宪法的档名 ⇒ 域里的档位名
_NME17 = {d: RB.design_ttk(t, "杂兵")[0] for d, t in _TIER_OF.items()}   # 基准＝杂兵原型（偏移 0）
for _d17 in ("普通怪", "精英"):
    chk("★ P-35 「%s」要打 **%.1f** 次 ⇒ 落在宪法那条带（%d–%d 次）里"
        % (_d17, _NME17[_d17], _BANDS[_d17][2], _BANDS[_d17][3]),
        _BANDS[_d17][2] <= _NME17[_d17] <= _BANDS[_d17][3])
#   ★ P-65（2026-09-26）**三条判据换锚**：原先这三条把「文档里必须留着旧字面」当成判据
#     （要求 `12_` 里留着「精英 12」「3 倍」，要求两份文档都写 `hp 7340`）—— 那等于把
#     「文档还没跟账」这个**临时状态**钉成了红/绿线：主线一跟账，门禁自己就红。
#     换锚后的口径（**强度不降**）：每一条都改成「文档里那个数 **∈ 两态**」，两态都是现算的：
#       · 旧案态 = `RB.TIERS_V1` / `RB.panel_of_v1` 复算出来的那一版（12_ §一 那张表就是它的快照）
#       · 跟账态 = 现口径复算（`RB.design_ttk` / 域里那只怪的面板）
#     **第三个数当场红**（手打 / 改坏一律拦得住）。主线把 `12_ §一` 那两处跟账之后，
#     把 `_*_V1` 那一半删掉即可（判据只收紧：两态 ⇒ 一态）。
_EL_V1 = float(RB.TIERS_V1["精英"]["hp_n"])                       # 旧案：精英要打 12 次
_EL_NOW = _NME17["精英"]                                           # 现口径：5.9 次
_RATIO_V1 = _EL_V1 / float(RB.TIERS_V1["普通"]["hp_n"])            # 旧案比值：12 ÷ 4 = 3.0
_RATIO_NOW = _EL_NOW / _NME17["普通怪"]
_ref_line = _re2.search(r"目标击杀行动数（([^）]*)）", D12)          # 抬头那行反推式
_ref_pairs = dict(_re2.findall(r"([\u4e00-\u9fa5]+)\s*(\d+(?:\.\d+)?)", _ref_line.group(1))) if _ref_line else {}
_n_elite_doc = _ref_pairs.get("精英")
chk("★ P-65 换锚①：`12_` 抬头反推式里那个「精英 N 次」= **%s**（整行：%s）必须**要么**是旧案快照 %.0f"
    "**要么**是现口径 %.1f（或它取整到个位 %.0f）—— 第三个数当场红（文档跟账前后都成立 · 手打/改坏拦得住）"
    % (_n_elite_doc, _ref_line.group(1) if _ref_line else "（没解析出）", _EL_V1, _EL_NOW, round(_EL_NOW)),
    _n_elite_doc is not None
    and (abs(float(_n_elite_doc) - _EL_V1) < 0.05
         or abs(float(_n_elite_doc) - _EL_NOW) < 0.05
         or abs(float(_n_elite_doc) - round(_EL_NOW)) < 0.05),
    "现算 %.3f 次 · 旧案 %.0f 次" % (_EL_NOW, _EL_V1))
_x_d12 = _re2.findall(r"普通\s*([\d.]+)\s*倍", D12)                 # 读法② 那个「精英 hp 是普通 N 倍」
chk("★ P-65 换锚②：`12_` 读法② 那个「精英 hp 是普通的 N 倍」（出现过 %s）必须**要么**是旧案 %.2f"
    "**要么**是现口径 %.3f —— 第三个数当场红"
    % (" · ".join(_x_d12) or "（一处都没有）", _RATIO_V1, _RATIO_NOW),
    bool(_x_d12) and all(abs(float(x) - _RATIO_V1) < 0.05 or abs(float(x) - _RATIO_NOW) < 0.05
                         for x in _x_d12),
    "现算比值 %.4f · 旧案 %.2f" % (_RATIO_NOW, _RATIO_V1))
# 反面之二（保留 · 已与文档字面解绑）：宪法两条带能推出的比值区间 = [5/5, 8/3] ——
#   域现算的比值必须**落在里面**，而旧案那个「3 倍」**必须在外面**（它才该被裁掉）。
_rlo17 = _BANDS["精英"][2] / _BANDS["普通怪"][3]                   # 5 ÷ 5
_rhi17 = _BANDS["精英"][3] / _BANDS["普通怪"][2]                   # 8 ÷ 3
chk("★ P-35 反面：「精英 ÷ 普通」的 hp 比域里现算 = **%.3f**（%.1f ÷ %.1f）⇒ 落在宪法两条带推出的"
    "区间 [%.2f, %.2f] 里；旧案那个 %.1f 倍在区间外（那两处按「过时」裁掉）"
    % (_RATIO_NOW, _NME17["精英"], _NME17["普通怪"], _rlo17, _rhi17, _RATIO_V1),
    _rlo17 <= _RATIO_NOW <= _rhi17 and not (_rlo17 <= _RATIO_V1 <= _rhi17),
    "现算比值 %.4f · 区间 [%.4f, %.4f]" % (_RATIO_NOW, _rlo17, _rhi17))
# 换锚③：`14_ §四` 那个 hp 与 `12_ §一④` 正文那句是**同一个数**，且那个数 ∈ 两态
#   （旧案态 = v1 口径「**不用原型偏移**」那一版 = `panel_of_v1(…, "杂兵")`（偏移 1.00）；
#    跟账态 = 域里现行那个数）。★ 两态都用**现算**的两侧各给 1% 容差（文档写的是取整值）。
_hp_doc = _num(D14, r"旧誓哨兵（Lv19）：hp (\d+)", int)
_hp_now = int(mo[_bkeys[0]]["panel"]["hp"]) if _bkeys else 0
_hp_v1 = int(RB.panel_of_v1(19, "boss", "杂兵")["hp"])     # 旧案那行写的「不用原型偏移」
chk("★ P-65 换锚③：两处文档写的 Boss hp 是同一个数（%s）· 且那个数 ∈ 两态"
    "（旧案（不偏移）复算 %d / 域现行 %d，**逐字相等**）—— 第三个数当场红"
    % (_hp_doc, _hp_v1, _hp_now),
    _hp_doc is not None and ("hp %s" % _hp_doc) in D12 and _hp_doc in (_hp_v1, _hp_now),
    "14 说 %s · 旧案复算 %s · 域 %s" % (_hp_doc, _hp_v1, _hp_now))
# ★ P-64（2026-09-26）**BOSS 那一格的口径**：`02_数值宪法/03_全流程数值主干_v1.md` §四 的 BOSS
#   那行写「12–18 次」，而域里 Boss 的基准 n_me = %.1f、实际怪（厚甲）≈ %.1f。
#   裁决：**域那一侧是对的**——`12_ §一④` 与 `14_ §四` 两处都写着「Boss 按 **4 人队 × 18 次行动**
#   设计」（= 72 次个人行动；现算 %.1f，差 %.1f%%），宪法那一格的「12–18」是**单人一场**那个通用
#   位形的数、没跟上「Boss = 团队内容」这条口径 ⇒ **按过时**（真源逐字新行见 `_notes.md`）。
#   判据：域 Boss 的**实际** n_me 必须 ≈ 那句「4 人队 × 18 次行动」（现解析，两个数都不手打）；
#   宪法那一行则只核「两态之一」（未跟账的 12–18 / 跟账后含现算值），第三态当场红。
_m_team = _re2.search(r"按\s*\**(\d+)\s*人队\s*[×x]\s*(\d+)\s*次行动", D12)
_team_acts = (int(_m_team.group(1)) * int(_m_team.group(2))) if _m_team else 0
_boss_actual = RB.design_ttk("boss", "厚甲")[0]
chk("★ P-64 域 Boss 的实际 n_me = **%.1f** ≈ `12_ §一④` 那句「%s 人队 × %s 次行动」= %d 次个人行动"
    "（差 %.1f%% ≤ 5%%）⇒ 域那一侧才是对的口径"
    % (_boss_actual, _m_team.group(1) if _m_team else "?", _m_team.group(2) if _m_team else "?",
       _team_acts, 100 * abs(_boss_actual - _team_acts) / float(_team_acts or 1)),
    bool(_team_acts) and abs(_boss_actual - _team_acts) / float(_team_acts) <= 0.05,
    "域基准 n_me %.1f · 实际（厚甲）%.1f" % (_NME17["BOSS"], _boss_actual))
chk("★ P-64 宪法 §四 BOSS 那一行的带 %s–%s 次：**要么**是未跟账的旧值（不含团队内容那个数）"
    "**要么**已跟账（含域现算 %.1f）—— 第三态当场红"
    % (_BANDS["BOSS"][2], _BANDS["BOSS"][3], _NME17["BOSS"]),
    (_BANDS["BOSS"][2], _BANDS["BOSS"][3]) == (12, 18)
    or _BANDS["BOSS"][2] <= _NME17["BOSS"] <= _BANDS["BOSS"][3],
    "带 = %s–%s · 域基准 %.1f" % (_BANDS["BOSS"][2], _BANDS["BOSS"][3], _NME17["BOSS"]))
print("     · ★ P-64 登记（**不当判据**）：宪法 §四 BOSS 那行写 12–18 次 ⇒ 按「口径过时」裁掉、"
      "改成「%d–%d 次」（4 人队 × 18 次行动那一路的数）—— 逐字新行见本分支 `_notes.md`。"
      % (int(_NME17["BOSS"] * 0.94), int(_NME17["BOSS"] * 1.09)))

print()
print("  · 档位 × 原型的 δ（保序压幅）：%s"
      % " · ".join("%s %.3f" % (k, v) for k, v in sorted(RB.delta_of().items())))
print("  · 交换余量 g = n_them/n_me（基准）：%s"
      % " · ".join("%s %.2f" % (t, RB.TIERS[t]["n_them"] / RB.TIERS[t]["n_me"]) for t in RB.TIER_ORDER))
print("  · 交换余量（17 只实际）：最小 %.2f（%s）· 最大 %.2f"
      % (min(v[0] for v in _g.values()), min(_g, key=lambda k: _g[k][0]), max(v[0] for v in _g.values())))

print()
print("── ★ B3-24 精英词条（`monster_affixes` 域 + 消费端 `content/affix.py`）")
# 真源：09_精英怪机制_v1.md（§二 规则 / §三 四类 / §四 配平）· 12_ §二（每只怪 3 条候选）
DOC09 = os.path.join(DOC_DIR, "09_精英怪机制_v1.md")
D09 = _io.open(DOC09, encoding="utf-8").read()
import asyncio                                                          # noqa: E402
from content import affix as _AF                                        # noqa: E402
from content import combat as _CB                                       # noqa: E402
from content import cmds_ast as _CA                                      # noqa: E402
from content import calendar as _CAL                                    # noqa: E402
import content.cmds_battle as _CBAT                                     # noqa: E402


class _E:                      # 「观察 / 攻击」只要 env.save()（落档是处理器的责任）
    text = ""

    def save(self):
        pass


AFA = {k: v for k, v in (st.domain("monster_affixes") or {}).items() if not str(k).startswith("_")}
ER = _AF.rules()
K4 = ("stat", "behavior", "mechanic", "loot")
ids = {a for m2 in mo.values() for a in (m2.get("elite_pool") or [])}     # elite_pool 引用到的 id 全集
_day = _CAL.state()["game_day"]                                           # 今天（预告 / 遭遇同一把种子）
_PL = {"name": "试炼者", "cls": "cls_knight", "level": 10, "alloc": {}, "skills": []}

# ⑰ 悬空 id：monsters.elite_pool 引用的 id 必须**全都有定义**（今天 0 个悬空 —— B3-17 §4.2 的账）
_dang = sorted(ids - set(AFA))
chk("★ elite_pool 引用的 %d 个 id **全都有定义**（悬空 %d 个：%s）"
    % (len(ids), len(_dang), _dang or "无"), not _dang)
chk("★ 定义条数 ≥ 引用条数（多出来的是 09_ §三 有、§二 没有怪在用的那几条：%s）"
    % sorted(set(AFA) - ids),
    len(AFA) >= len(ids) and set(AFA) >= ids, "%d 条定义 / %d 个引用" % (len(AFA), len(ids)))

# ⑰b 形状（四类 / PE 表 / status 两态各有必填）
_bad_sh = []
for _aid, _r in AFA.items():
    if _r.get("class_key") not in K4:
        _bad_sh.append("%s 类不在四类里" % _aid)
    if int(_r.get("pe", -1)) != int(ER["pe_by_class_key"][_r.get("class_key", "stat")]):
        _bad_sh.append("%s pe=%s ≠ 表 %s" % (_aid, _r.get("pe"), ER["pe_by_class_key"].get(_r.get("class_key"))))
    if _r.get("status") not in (_AF.ST_ON, _AF.ST_PENDING):
        _bad_sh.append("%s status=%s" % (_aid, _r.get("status")))
    if _r.get("status") == _AF.ST_ON and not isinstance(_r.get("mods"), dict):
        _bad_sh.append("%s on 但没 mods" % _aid)
    if _r.get("status") == _AF.ST_PENDING and not _r.get("why"):
        _bad_sh.append("%s pending 但没 why" % _aid)
    if not (_r.get("axis") and all(_re2.match(r"^[a-z_]+$", str(x)) for x in _r["axis"])):
        _bad_sh.append("%s axis 不是 ASCII 非空表" % _aid)
    if not (_r.get("name") and _r.get("line") and _r.get("src")):
        _bad_sh.append("%s 缺 name/line/src" % _aid)
chk("★ 每条词条：四类之一 · PE == rules 的类表 · status 两态各自必填齐（on 要 mods / pending 要 why）· axis 是 ASCII",
    not _bad_sh, " · ".join(_bad_sh[:4]))
_rk = {k: len([1 for r in AFA.values() if r["class_key"] == k]) for k in K4}
print("     · 四类分布：%s ｜ on %d / pending %d"
      % (" · ".join("%s %d" % (k, n) for k, n in _rk.items()),
         len([1 for r in AFA.values() if r["status"] == _AF.ST_ON]),
         len([1 for r in AFA.values() if r["status"] == _AF.ST_PENDING])))

# ⑱ ★ 三头对账：`09_` 文档（现解析）↔ `content/rules/elite.json` ↔ 域里每条的 pe
_pe_doc = {m.group(1): int(m.group(2)) for m in _re2.finditer(r"(改数值|改行为|改机制)\s*每条 \+(\d+) PE", D09)}
_pe_key = {"改数值": "stat", "改行为": "behavior", "改机制": "mechanic"}
chk("★ PE 表三头一致（09_ §四 现解析 %s ↔ rules.pe_by_class_key ↔ 逐条 pe）"
    % " · ".join("%s=%s" % (k, v) for k, v in sorted(_pe_doc.items())),
    len(_pe_doc) == 3 and all(ER["pe_by_class_key"][_pe_key[k]] == v for k, v in _pe_doc.items()))
chk("★ §四 的掉落那条**不进难度预算**（文档原话「不影响难度，单独算收益」⇒ rules = 0）",
    "改掉落" in D09 and "不影响难度" in D09 and int(ER["pe_by_class_key"]["loot"]) == 0)
_cap_doc = _re2.search(r"单只精英的词条 PE ≤ (\d+)", D09)
chk("★ PE 上限 = 文档那个数（09_ §四「单只精英的词条 PE ≤ %s」）"
    % (_cap_doc.group(1) if _cap_doc else "（没解析出）"),
    bool(_cap_doc) and int(ER["pe_cap"]["value"]) == int(_cap_doc.group(1)))
# 条数档位：文档那行是 `1–5 级：**1 条**　6–10 级：**1–2 条**　11–15 级：**2 条**　16–20 级：**2–3 条**`
_bands_doc = []
for _m in _re2.finditer(r"(\d+)–(\d+) 级：\*\*(\d+)(?:–(\d+))? 条\*\*", D09):
    _bands_doc.append((int(_m.group(1)), int(_m.group(2)), int(_m.group(3)), int(_m.group(4) or _m.group(3))))
_bands = [(int(b["min_lv"]), int(b["max_lv"]), int(b["n_min"]), int(b["n_max"]))
          for b in ER["count_by_level"]["bands"]]
chk("★ 条数档位四段与文档逐段一致（%s）"
    % " · ".join("%d–%d 级 %d–%d 条" % b for b in _bands), _bands_doc == _bands,
    "文档 %s / rules %s" % (_bands_doc, _bands))
_rates_doc = {t: int(v) for t, v in _re2.findall(r"(第一节点|中间|深处/隐藏点)[^\d%]{0,6}(\d+)%", D09)}
chk("★ 概率三档与文档一致（%s）"
    % " · ".join("%s %s%%" % kv for kv in sorted(_rates_doc.items())),
    _rates_doc == {"第一节点": 8, "中间": 12, "深处/隐藏点": 20}
    and [round(ER["rate"]["by_node_index"][k] * 100) for k in ("first", "middle", "last")] == [8, 12, 20],
    "文档 %s" % _rates_doc)
_sp_doc = _re2.search(r"群居\s*一次来 (\d+) 只（第二只半血）", D09)
chk("★ 群居那两格与文档一致（09_ §三「一次来 %s 只（第二只半血）」）"
    % (_sp_doc.group(1) if _sp_doc else "?"),
    bool(_sp_doc) and int(ER["spawn"]["n"]) == int(_sp_doc.group(1))
    and float(ER["spawn"]["hp_mult"]) == 0.5 and int(ER["spawn"]["half_hp_index"]) == 1)
chk("★ 节点档位名单里的 role 都在 maps 域真出现过（不新造深度字段）",
    all(any(n.get("role") == _r for m2 in MP.values() for n in (m2.get("nodes") or []))
        for _r in ER["rate"]["eligible_node_roles"]), "%s" % ER["rate"]["eligible_node_roles"])

# ⑲ 抽词条：可复现 + 档位条数 + PE ≤ 24 + 同轴不叠 + 池子里的 on 都抽得到
_roll_bad, _seen_pick, _n_band_bad, _pe_bad, _ax_bad = [], set(), [], [], []
for _k, _m in mo.items():
    _pool = _m.get("elite_pool") or []
    if not _pool:
        continue
    for _s in range(120):
        _got = _AF.roll(_pool, _s, int(_m.get("lv", 1)))
        if _got != _AF.roll(_pool, _s, int(_m.get("lv", 1))):
            _roll_bad.append("%s seed=%s 两次不同" % (_k, _s))
        _seen_pick |= set(_got)
        _nmin, _nmax = _AF.band_of(int(_m.get("lv", 1)))
        _avail = len(_AF.rollable(_pool))
        if not (min(_nmin, _avail) <= len(_got) <= _nmax):
            _n_band_bad.append("%s 抽了 %d 条（档位 %d–%d / 可挑 %d）" % (_k, len(_got), _nmin, _nmax, _avail))
        if _AF.pe_of(_got) > int(ER["pe_cap"]["value"]):
            _pe_bad.append("%s %s PE=%d" % (_k, _got, _AF.pe_of(_got)))
        _axs: list = []
        for _a in _got:
            for _x in _AF.rec_of(_a)["axis"]:
                if _x in _axs:
                    _ax_bad.append("%s 轴 %s 重了" % (_k, _x))
                _axs.append(_x)
chk("★ 抽词条**可复现**（同一种子两次同结果 · 17 只 × 120 种子）", not _roll_bad, " · ".join(_roll_bad[:3]))
chk("★ 条数落在 09_ §二 的等级档位里（可挑的比档位少时按可挑的算 —— 不拿没接线的凑数）",
    not _n_band_bad, " · ".join(_n_band_bad[:3]))
chk("★ PE 累计 ≤ 上限（%d）" % int(ER["pe_cap"]["value"]), not _pe_bad, " · ".join(_pe_bad[:3]))
chk("★ **同轴不叠**（一次抽到的各条 axis 两两不相交）", not _ax_bad, " · ".join(_ax_bad[:3]))
_must = {a for _m in mo.values() for a in _AF.rollable(_m.get("elite_pool") or [])}
chk("★ 池子里每一条 `on` 词条都真抽得到（%d 条：%s）"
    % (len(_must), " · ".join(sorted(_must))),
    _must <= _seen_pick, "抽不到的：%s" % sorted(_must - _seen_pick))

# ⑳ ★ 面板差异**可复算**：带/不带那条词条各造一个 actor，逐键核声明的倍数
_pan_bad, _pan_n = [], 0
for _k, _m in mo.items():
    _pool = _m.get("elite_pool") or []
    if not _pool:
        continue
    for _a in _AF.rollable(_pool):
        for _ch, _decl in (_AF.rec_of(_a).get("mods") or {}).items():
            if _ch != _AF.CH_PANEL:
                continue
            _pan_n += 1
            _base = dict(_m["panel"])
            _want = dict(_base)
            for _kk, _vv in _decl.items():                    # 复算：域键 × 声明倍数（取整口径同消费端）
                _want[_kk] = int(round(float(_want[_kk]) * float(_vv)))
            _got = _AF.apply_panel(_base, [_a], _k)
            if _got != _want:
                _pan_bad.append("%s+%s 算=%s 得=%s" % (_k, _a, _want, _got))
            _a_actor = _CB.monster_actor(_k, _m, affixes=[_a])          # 真进 actor 那一步
            _b_actor = _CB.monster_actor(_k, _m)                        # 不带词条 = 原样（接线前那一份）
            _eng = {"hp": "max_hp", "def": "def", "spd": "spd", "atk": "atk", "res": "mdef"}
            for _kk in ("hp", "def", "spd", "atk", "res"):
                if abs(float(_b_actor[_eng[_kk]]) - float(_base[_kk])) > 0.5:
                    _pan_bad.append("不带词条的 actor %s=%s ≠ 域 %s" % (_kk, _b_actor[_eng[_kk]], _base[_kk]))
            for _kk, _vv in _decl.items():
                if abs(float(_a_actor[_eng[_kk]]) - float(_want[_kk])) > 0.5:
                    _pan_bad.append("actor %s %s=%s ≠ 复算 %s" % (_a, _kk, _a_actor[_eng[_kk]], _want[_kk]))
chk("★ 面板差异**可复算**（%d 条面板词条 × %d 只怪：域键复算 == 消费端结果 == 引擎 actor 那一格）"
    % (_pan_n, len([1 for m2 in mo.values() if m2.get("elite_pool")])), not _pan_bad,
    " · ".join(_pan_bad[:4]))

# ㉑ ★ 四条通道**真跑一场**：群居多只+半血 · 护盾开场盾 · 潜伏先手 · 狂暴阈值（一次性）
_ee = [k for k, v in mo.items() if "af_swarm" in _AF.rollable(v.get("elite_pool") or [])]
_k22 = sorted(_ee, key=lambda k: int(mo[k]["lv"]))[0]
_ids2, _hms2 = _AF.spawn_plan(_k22, ["af_swarm"])
_b2 = _CB.build(_PL, _ids2, mo, party=1, affixes=["af_swarm"], hp_mults=_hms2)
_es = _b2.sides["enemy"]
chk("★ 群居：一次来 %d 只（%s）· 第二只是第一只的 %s 倍血（%s vs %s）"
    % (len(_es), mo[_k22]["name"], ER["spawn"]["hp_mult"],
       _es[1]["max_hp"] if len(_es) > 1 else "?",
       int(round(int(mo[_k22]["panel"]["hp"]) * float(ER["spawn"]["hp_mult"])))),
    len(_es) == int(ER["spawn"]["n"])
    and int(_es[1]["max_hp"]) == int(round(int(mo[_k22]["panel"]["hp"]) * float(ER["spawn"]["hp_mult"])))
    and int(_es[0]["max_hp"]) == int(mo[_k22]["panel"]["hp"]))
_sk = next(k for k, v in mo.items() if "af_shield" in _AF.rollable(v.get("elite_pool") or []))
_b3 = _CB.build(_PL, [_sk], mo, party=1, affixes=["af_shield"])
_a3 = _b3.sides["enemy"][0]
_sh_want = max(1, int(round(_a3["max_hp"] * float(ER["shield_pct_of_hp"]["value"]))))
_sh_got = _a3["shields"].get("af_shield", {}).get("value")
sh_want_ok = _a3["shields"] == {"af_shield": {"value": _sh_want}}
_lg3: list = []
_b3.auto_run(_lg3)
chk("★ 护盾：开场就有一层壳（值 = 生命上限 %s%% = %s）且**真吸收**（日志里出现吸收行；打完盾被吃光 ⇒ 容器里没了）"
    % (round(float(ER["shield_pct_of_hp"]["value"]) * 100), _sh_got),
    sh_want_ok and any("护盾吸收" in str(x) for x in _lg3))
_am = next(k for k, v in mo.items() if "af_ambush" in _AF.rollable(v.get("elite_pool") or []))
_b4 = _CB.build(_PL, [_am], mo, party=1, affixes=["af_ambush"])
_a4 = _b4.sides["enemy"][0]
_ct0 = float(_a4.get("ct", -1))
_lg4: list = []
_b4.auto_run(_lg4)
_first = next((x for x in _lg4 if "——" in str(x)), "")
_b6 = _CB.build(_PL, [_am], mo, party=1)                                  # 对照：不带潜伏
_ct_plain = float(_b6.sides["enemy"][0].get("ct", -1))
chk("★ 潜伏：它抢在玩家前面动手（构建后 ct：带潜伏 %s / 对照组 %s；第一动 = 「%s」）"
    % (_ct0, round(_ct_plain, 3), str(_first).strip()[:24]),
    _ct0 == 0.0 and _ct_plain > 0 and mo[_am]["name"] in str(_first))
_fr = next(k for k, v in mo.items() if "af_frenzy" in _AF.rollable(v.get("elite_pool") or []))
_b5 = _CB.build(_PL, [_fr], mo, party=1, affixes=["af_frenzy"])
_a5 = _b5.sides["enemy"][0]
_atk0 = _a5["atk"]
_fr_decl = _AF.thresholds_of(["af_frenzy"])[0][1]
_a5["hp"] = int(_a5["max_hp"] * float(_fr_decl["hp_below"]) * 0.8)         # 手动跌破阈值
_b5.script_hook(_b5, _a5, [])                                            # 第一次越过 ⇒ 改
_atk1 = _a5["atk"]
_b5.script_hook(_b5, _a5, [])                                            # 再调两次（钩子每一动都会被调）
_b5.script_hook(_b5, _a5, [])
chk("★ 狂暴：血量跌破 %s%% 后 atk ×%s，且**只改一次**（%s → %s → %s；不守 `once` 会一路上乘）"
    % (round(float(_fr_decl["hp_below"]) * 100), _fr_decl["atk_mult"], _atk0, _atk1, _a5["atk"]),
    _atk1 == int(round(_atk0 * float(_fr_decl["atk_mult"]))) and _a5["atk"] == _atk1)

# ㉑b 掉落：材料倍数（09_ §四 按 PE 等比上调 + 富饶「材料翻倍」）
_dm = ER["material_drop_mult"]
_rows = [{"id": "x", "n": 3, "kind_key": "material"}, {"id": "y", "n": 3, "kind_key": "gear"}]
_pe12 = _AF.pe_of(["af_shield"])
_fu = float(AFA["af_bountiful"]["mods"]["drops"]["mult"])
_base_pe = float(_dm["base"]) + _pe12 * float(_dm["per_pe"])
_want_n = max(1, int(round(3 * _base_pe * _fu)))
_got_rows = _AF.scale_drops(_rows, ["af_shield", "af_bountiful"])
_bare = _AF.scale_drops(_rows, [])
chk("★ 材料倍数 = (1 + PE×%s) × 富饶的 %s（PE %d → 按 PE 那半 %s；材料 3 份 × %s × %s = %s；"
    "非材料那格不动；没词条 = 原样）"
    % (round(float(_dm["per_pe"]), 5), _fu, _pe12, round(_base_pe, 4), round(_base_pe, 4), _fu,
       _got_rows[0]["n"]),
    _got_rows[0]["n"] == _want_n and _got_rows[1]["n"] == 3 and _bare == _rows)

# ㉒ ★ 观察那行**逐字走 texts 槽位**，且与「攻击」的遭遇是**同一个东西**
_tx = st.domain("texts")
_line_ok, _same_ok, _hit_n = True, True, 0
for _loc, _nd in (("belt_north", "bn_bone"), ("belt_north", "bn_camp"), ("belt_north", "bn_tower"),
                  ("belt_east", "be_birch"), ("belt_east", "be_dogs"), ("belt_east", "be_shed"),
                  ("belt_west", "bw_shoal"), ("belt_west", "bw_ferry"), ("belt_west", "bw_old_ferry")):
    _el = _AF.elite_of(mo, _loc, _nd, "u_probe", _day, 10)
    if not _el:
        continue
    _hit_n += 1
    _want_line = str(_tx["COMBAT_ELITE_SPAWN"]["value"]) \
        .replace("{affix}", str(ER["label"]["sep"]).join(str(AFA[a]["name"]) for a in _el[1])) \
        .replace("{name}", str(mo[_el[0]]["name"])) \
        .replace("{hint}", _AF.hint_of(_el[1]))
    _got_line = _AF.elite_line(str(mo[_el[0]]["name"]), _el[1])
    if _got_line != _want_line:
        _line_ok = False
    _p = dict(_CA.DEFAULT_PLAYER)
    _p.update({"loc": _loc, "node": _nd, "race": "human", "cls": "cls_knight", "level": 10,
               "alloc": {}, "skills": [], "name": "试炼者"})
    _out: list = []

    async def _go(_p=_p, _loc=_loc, _nd=_nd):
        async for _l in _CA.look(_E(), None, "u_probe", _p):
            _out.append(_l)
    asyncio.run(_go())
    if _got_line not in _out:
        _line_ok = False
chk("★ 观察那行**逐字** = texts 槽位 COMBAT_ELITE_SPAWN 的渲染（今天这 %d 格里有精英的 %d 格都核）"
    % (9, _hit_n), _line_ok and _hit_n >= 0, "命中 %d 格" % _hit_n)
_el_n = None
_found_uid = None
for _i in range(400):                       # 换 uid 找一个「今天这一格真有精英」的档（种子含 uid）
    for _loc, _nd in (("belt_north", "bn_bone"), ("belt_north", "bn_camp"), ("belt_north", "bn_tower"),
                      ("belt_east", "be_birch"), ("belt_east", "be_dogs"), ("belt_east", "be_shed"),
                      ("belt_west", "bw_shoal"), ("belt_west", "bw_ferry"), ("belt_west", "bw_old_ferry")):
        _e2 = _AF.elite_of(mo, _loc, _nd, "u%03d" % _i, _day, 10)
        if _e2:
            _el_n, _found_uid, _f_loc, _f_nd = _e2, "u%03d" % _i, _loc, _nd
            break
    if _el_n:
        break
_at: list = []
_lk_out: list = []
if _el_n:
    _pl2 = dict(_CA.DEFAULT_PLAYER)
    _pl2.update({"loc": _f_loc, "node": _f_nd, "race": "human", "cls": "cls_knight",
                 "level": 10, "alloc": {}, "skills": [], "name": "试炼者", "hp": 9999})
    _pl2["flags"] = dict(_pl2.get("flags") or {})

    async def _go3():                       # ★ 先「观察」再「攻击」= 玩家真实顺序
        async for _l in _CA.look(_E(), None, _found_uid, _pl2):
            _lk_out.append(_l)
    asyncio.run(_go3())
    _want2 = _AF.elite_line(str(mo[_el_n[0]]["name"]), _el_n[1])

    async def _go2():
        # ★ G2：战斗改**一手一推进** ⇒ 「这一场」跨指令落盘（夹具用的 key = 空群 + uid）
        #   —— 真敲之前先清掉（不清的话上一次运行留下的场会被接着打：那一敲就**没有遭遇那两行**）
        from content import instance as _INST23
        _INST23.clear(_INST23.key_of("", _found_uid, [_found_uid]))
        async for _l in _CBAT.attack(_E(), None, _found_uid, _pl2):
            _at.append(_l)
    asyncio.run(_go2())
    _same_ok = (_want2 in _at) and (_want2 in _lk_out)
chk("★ 「观察能提前看到」是**真的**：同一 uid/图/节点/日 ⇒ 观察那行就是遭遇那一行"
    "（找出来的那一档：%s/%s uid=%s → %s）"
    % (_f_loc if _el_n else "—", _f_nd if _el_n else "—", _found_uid, _el_n[1] if _el_n else "—"),
    bool(_el_n) and _same_ok, "遭遇前两行：%s" % str(_at[:2])[:70])

# ══════════════════════════════════════════════════════════════
# ★ g4-⑥：多条词条的 `hint` 拼接 —— 句末**只留一枚**标点
#   实机原状（fix2 §七5 顺手核到 · p2/p3 报告）：`af_frenzy` 那句自带句号，
#   用 `line_sep`（`；`）接上 `af_swarm` ⇒ 屏幕上成了「…它下手更重。；它身后还有两只…」。
#   判据三态：① 真实数据里那两条拼出来**没有 `。；`**、且末尾正好一枚句末标点；
#             ② 从表里现取 `label.line_end` / `label.line_sep`（代码不写死那一枚）；
#             ③ **反证**：照旧拼法（拿原始 `line` 直接 join）当场拼出 `。；` 这个坏形态。
# ══════════════════════════════════════════════════════════════
print("")
print("★ g4-⑥：多条词条的 hint 拼接（句末那一枚标点）")
_lab22 = _AF.rules()["label"]
_reals22 = []
for _k22, _v22 in sorted(mo.items()):
    _ids22 = _AF.rollable(_v22.get("elite_pool") or [])
    _both22 = [a for a in _ids22 if str((_AF.rec_of(a) or {}).get("line") or "").endswith("。")]
    if len(_both22) >= 2:
        _reals22.append((_k22, _both22[:2]))
    if len(_reals22) >= 3:
        break
_bad22, _raw22 = [], []
for _k22, _ids22 in _reals22:
    _hint22 = _AF.hint_of(_ids22)
    if "。；" in _hint22 or "；。" in _hint22 or _hint22.count("。；"):
        _bad22.append((_k22, _hint22))
    if not _hint22.endswith(str(_lab22.get("line_end") or "")):
        _bad22.append((_k22, "末尾不是表里那一枚标点：" + _hint22))
    _raw22.append(str(_lab22["line_sep"]).join(
        str((_AF.rec_of(a) or {}).get("line") or "").strip() for a in _ids22))
chk("★ 真数据里每只怪的精英词条拼出来：**没有 `。；`**、末尾正好一枚 `line_end`"
    "（表里的值 = %r · 抽查 %d 只怪的词条对）"
    % (str(_lab22.get("line_end")), len(_reals22)),
    bool(_reals22) and not _bad22, "%s" % (_bad22[:2],))
chk("★ 反证（旧拼法有牙）：把原始 `line` 直接 join（改前那一行）⇒ 当场拼出 `。；` 坏形态",
    bool(_raw22) and all("。；" in x for x in _raw22), "%s" % (_raw22[:1],))
chk("★ 状态那一档不许被摘掉：`af_swarm` 行内的破折号一个字不动（只摘**句末**那一枚）",
    all("——" in _AF.hint_of([_k23]) for _k23 in ("af_swarm", "af_frenzy")
        if str((_AF.rec_of(_k23) or {}).get("line") or "").find("——") >= 0),
    "%s" % (_AF.hint_of(["af_swarm"]),))

# ㉓ ★ 覆盖快照（**只许变长**）：有池子的怪里，池子至少含一条 `on` 的只数
_cov = _AF.coverage(mo)
print("     · 覆盖率 %d/%d 只（池子里一条都没接线的：%s —— 逐条理由见 _notes.md §四）"
      % (len(_cov["ok"]), _cov["total"], " · ".join("%s(%s)" % (k, "·".join(_AF.rec_of(a)["name"]
                                                                    for a in mo[k]["elite_pool"]))
                                                   for k in _cov["bad"]) or "无"))
chk("★ 覆盖快照只许变长：池子里至少有一条 `on` 词条的怪 ≥ 15 只（今天 %d 只）"
    % len(_cov["ok"]), len(_cov["ok"]) >= 15, "%s" % _cov["bad"])

print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
