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
print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
