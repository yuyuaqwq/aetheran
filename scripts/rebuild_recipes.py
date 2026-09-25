# -*- coding: utf-8 -*-
"""recipes 域重建（B2-6 · 烹饪 / 强化）—— ★ 数值全部从源文档解析，禁手打。

读这些真源（缺一段就当场抛，不猜、不兜底）：
  aetheran-plan/06_第一阶段垂直切片/05_玩法数值口径_v1.md       烹饪 / 强化 / 强化材料 三行
  aetheran-plan/06_第一阶段垂直切片/13_装备玩法与随机性_v1.md    强化浮动（+6 起 ±10%）
  aetheran-plan/06_第一阶段垂直切片/24_任务线_v1.md              支线名（「支线 4」→ 任务 id）
  aetheran-plan/00_总纲/13_配方域口径_v1.md                    费 / 率 / 档位 / 卖价 + 八道菜表
  aetheran-designer/_归档_2026-09-22/06_装备道具/00_装备体系与PE预算.md   强化加成 0.004/级

写：
  content/data/recipes.json   8 条烹饪 + 10 档强化
  content/data/items.json     补 8 道菜（kind 食物）+ 药水的 heal（从 desc 解析）

用法：
  python scripts/rebuild_recipes.py --dry      # 只打印，不写
  python scripts/rebuild_recipes.py            # 写（连跑两次数据不变）
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

PLAN = os.environ.get("AETHERAN_PLAN", "C:/Users/yuyu/aetheran-plan")
ARCHIVE = os.environ.get("AETHERAN_ARCHIVE", "C:/Users/yuyu/aetheran-designer/_归档_2026-09-22")
PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(PKG, "content", "data")

S05 = os.path.join(PLAN, "06_第一阶段垂直切片", "05_玩法数值口径_v1.md")
S13 = os.path.join(PLAN, "06_第一阶段垂直切片", "13_装备玩法与随机性_v1.md")
S24 = os.path.join(PLAN, "06_第一阶段垂直切片", "24_任务线_v1.md")
SPEC = os.path.join(PLAN, "00_总纲", "13_配方域口径_v1.md")
OLD = os.path.join(ARCHIVE, "06_装备道具", "00_装备体系与PE预算.md")

STAT_KEY = {"攻击": "atk", "防御": "def", "生命上限": "hp"}
QUAL_RANK = {"普通": 0, "精制": 1, "稀有": 2, "遗物": 3}
#: ★ B3-6b-2d-keys-2：配方 `kind`（中文）→ ASCII **机器键** `kind_key`（P-20 甲案第二刀）。
#:   取值与 `_meta` 的两块**同名**（`cook` / `enhance` —— 域里本来就这么叫）；代码只比 ASCII 键
#:   （原先 `cmds_recipe._cookable` 比的是中文「烹饪」）。表是唯一来源：`probe_recipes` ⑬ 三头对账。
KIND_KEY = {"烹饪": "cook", "强化": "enhance"}
#: 菜（items 域）的机器键 —— 与 `scripts/rebuild_kind_keys.py` 的 `ITEM_KIND_KEY["食物"]` 同值
#: （那边管整个 items 域，这边只管它自己造的 8 道菜；`probe_items` ⑧ 两头对账）。
DISH_KIND_KEY = "food"


def rd(path: str) -> str:
    with io.open(path, encoding="utf-8", newline="") as f:
        return f.read()


def load(name: str):
    with io.open(os.path.join(DATA, name + ".json"), encoding="utf-8", newline="") as f:
        return json.load(f)


def grab(pattern: str, text: str, where: str, flags=0):
    m = re.search(pattern, text, flags)
    if not m:
        raise SystemExit("解析不到：%s\n  模式：%s" % (where, pattern))
    return m.groups() if len(m.groups()) > 1 else m.group(1)


def round_half_up(v: float) -> int:
    """四舍五入（Python 的 round 是银行家舍入，7.5 → 8 但 6.5 → 6 —— 口径要对玩家一致）。"""
    return int(v + 0.5) if v >= 0 else -int(-v + 0.5)


def round_to(v: float, step: int) -> int:
    return round_half_up(v / float(step)) * step


def main(argv) -> int:
    dry = "--dry" in argv

    # ── ① 源文档：形状 ────────────────────────────────────────
    t05, t13, t24, spec, old = rd(S05), rd(S13), rd(S24), rd(SPEC), rd(OLD)

    cook_line = grab(r"\|\s*烹饪\s*\|\s*(.+?)\s*\|", t05, "05 §三 烹饪行")
    n_min, n_max = (int(x) for x in grab(r"(\d+)–(\d+) 个食材", cook_line, "烹饪 食材数"))
    minutes = int(grab(r"增益 \*\*(\d+) 分钟\*\*", cook_line, "烹饪 时长"))
    choices = [x.strip() for x in grab(r"（(.+?)三选一）", cook_line, "烹饪 三选一").split("/")]

    enh_line = grab(r"\|\s*强化\s*\|\s*(.+?)\s*\|", t05, "05 §三 强化行")
    g1 = grab(r"\+(\d+) 到 \+(\d+) 必成", enh_line, "必成段")
    sure_a, sure_b = int(g1[0]), int(g1[1])
    cap = int(grab(r"上限 \*\*\+(\d+)\*\*", enh_line, "强化上限"))
    m_line = grab(r"\|\s*强化材料\s*\|\s*(.+?)\s*\|", t05, "05 §三 强化材料行")
    mat_a, mat_b = grab(r"「(.+?)」· 怪掉「(.+?)」", m_line, "两条材料名")
    need = [int(x) for x in grab(r"每级需求 \*\*([\d/]+)\*\*", m_line, "每级材料曲线").split("/")]

    g2 = grab(r"\+(\d+) 起每级数值 \*\*±(\d+)%\*\*", t13, "13 §1.2 强化浮动")
    float_from, float_pct = int(g2[0]), int(g2[1])
    bonus_per_level = float(grab(r"装备PE × \(1 \+ ([\d.]+) × 强化等级\)", old, "旧案 强化 PE 口径"))

    # ── ② 首版口径（13_配方域口径）────────────────────────────
    g3 = grab(r"强化费\s*=\s*材料市价合计 × (\d+)　（取整到 (\d+)）", spec, "强化费公式")
    fee_mult, fee_step = int(g3[0]), int(g3[1])
    g4 = grab(r"强化率\s*=\s*\+1\.\.\+(\d+) 必成；\+(\d+) 起 ([\d/]+)（每级 -(\d+)%，下限 (\d+)）",
              spec, "强化率规则")
    sure_until, rate_from, rate_list, rate_drop, rate_floor = g4
    rates = [int(x) / 100.0 for x in str(rate_list).split("/")]
    sure_until, rate_from = int(sure_until), int(rate_from)
    rate_drop, rate_floor = int(rate_drop), int(rate_floor)
    g5 = grab(r"菜品增益 = 普通 (\d+) / 精制 (\d+) / 稀有 (\d+)", spec, "菜品增益档位")
    tier = {q: int(v) for q, v in zip(("普通", "精制", "稀有"), g5)}
    sell_mult = float(grab(r"菜品卖价 = 食材市价合计 × ([\d.]+)", spec, "菜品卖价公式"))

    # ── ③ 源文档：八道菜表 ────────────────────────────────────
    rows = []
    for line in spec.splitlines():
        if not line.startswith("| `i_food_"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append({"id": cells[0].strip("`"), "name": cells[1], "icon": cells[2],
                     "ing": cells[3], "buff": cells[4], "learn": cells[5],
                     "line": cells[6], "note": cells[7]})
    if len(rows) != 8:
        raise SystemExit("八道菜表解析出 %d 行（应为 8）" % len(rows))

    # ── ④ 名字 → id（items 域；重名要能判定，判不了就抛）──────
    items = load("items")
    by_name: dict = {}
    for iid, v in items.items():
        if str(iid).startswith("_"):
            continue
        by_name.setdefault(v.get("name"), []).append(iid)

    def resolve(name: str, must: str = "") -> str:
        cand = by_name.get(name) or []
        if len(cand) > 1 and must:
            cand = [c for c in cand if must in str((items[c] or {}).get("desc") or "")]
        if len(cand) != 1:
            raise SystemExit("材料名「%s」解析不到唯一物品（候选 %s）" % (name, cand))
        return cand[0]

    ing_a, ing_b = resolve(mat_a, must="强化"), resolve(mat_b, must="强化")

    # ── ⑤ 支线号 → 任务 id（24 文档的表 + quests 域的名字）────
    side_sec = t24.split("## 二、支线", 1)
    if len(side_sec) < 2:
        raise SystemExit("24 文档里找不到「## 二、支线」那一节")
    side_no_name = {}
    for line in side_sec[1].split("\n---", 1)[0].splitlines():   # ★ 别用裸 "---" 切：markdown 表格分隔行里就有它
        m = re.match(r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|", line)
        if m:
            side_no_name[int(m.group(1))] = m.group(2).strip()
    quests = load("quests")
    qid_by_name = {v.get("name"): k for k, v in quests.items()
                   if isinstance(v, dict) and v.get("kind") == "支线"}

    def quest_of(token: str):
        m = re.match(r"^支线\s*(\d+)$", str(token).strip())
        if not m:
            return None
        no = int(m.group(1))
        nm = side_no_name.get(no)
        if not nm or nm not in qid_by_name:
            raise SystemExit("支线 %d 在 24 文档/quests 域里对不上（名 %r）" % (no, nm))
        return qid_by_name[nm]

    # ── ⑥ 造 recipes 域 ──────────────────────────────────────
    def price(iid: str) -> float:
        return float((items[iid] or {}).get("price") or 0)

    recipes: dict = {}
    dish_meta: dict = {}
    for r in rows:
        ins = []
        for part in [p.strip() for p in r["ing"].split("+")]:
            m = re.match(r"^(.+?)×(\d+)$", part)
            if not m:
                raise SystemExit("食材写法看不懂：%r（行 %s）" % (part, r["id"]))
            ins.append({"id": resolve(m.group(1)), "n": int(m.group(2))})
        if not (n_min <= len(ins) <= n_max):
            raise SystemExit("%s 的食材 %d 样，超出源文档的 %d–%d" % (r["id"], len(ins), n_min, n_max))
        sm = re.match(r"^(.+?)\s+(\d+)%$", r["buff"])
        if not sm:
            raise SystemExit("增益写法看不懂：%r" % r["buff"])
        stat_name, pct = sm.group(1).strip(), int(sm.group(2))
        if stat_name not in choices:
            raise SystemExit("%s 的增益「%s」不在 05 的三选一 %s 里" % (r["id"], stat_name, choices))
        top = max(ins, key=lambda e: QUAL_RANK.get((items[e["id"]] or {}).get("quality") or "普通", 0))
        top_q = (items[top["id"]] or {}).get("quality") or "普通"
        if tier.get(top_q) != pct:
            raise SystemExit("%s 的增益 %d%% 与档位规则对不上（最贵那样食材 = %s ⇒ 该是 %s%%）"
                             % (r["id"], pct, top_q, tier.get(top_q)))
        learn = quest_of(r["learn"])
        rid = "rc_cook_" + r["id"][len("i_food_"):]
        recipes[rid] = {
            "name": r["name"], "kind": "烹饪", "kind_key": KIND_KEY["烹饪"], "icon": r["icon"],
            "inputs": ins, "out": r["id"], "out_n": 1,
            "buff": {"stat": STAT_KEY[stat_name], "stat_name": stat_name,
                     "pct": pct, "seconds": minutes * 60},
            "learn": ({"quest": learn} if learn else None),
            "desc": r["line"], "source": "13_配方域口径_v1 §三",
        }
        dish_meta[r["id"]] = {
            "name": r["name"], "icon": r["icon"], "kind": "食物", "kind_key": DISH_KIND_KEY,
            "price": round_half_up(sum(price(e["id"]) * e["n"] for e in ins) * sell_mult),
            "desc": r["line"],
            "food": {"stat": STAT_KEY[stat_name], "pct": pct, "seconds": minutes * 60},
            "from_recipe": rid,
        }

    for lv in range(1, cap + 1):
        n = need[lv - 1]
        fee = round_to(fee_mult * n * (price(ing_a) + price(ing_b)), fee_step)
        i = lv - rate_from
        if lv <= sure_until:
            rate = 1.0
        elif 0 <= i < len(rates):
            rate = rates[i]
        else:
            raise SystemExit("+%d 没有成功率（率表只覆盖 %d–%d）" % (lv, rate_from, rate_from + len(rates) - 1))
        recipes["rc_enh_%02d" % lv] = {
            "name": "强化 +%d" % lv, "kind": "强化", "kind_key": KIND_KEY["强化"], "level": lv,
            "inputs": [{"id": ing_a, "n": n}, {"id": ing_b, "n": n}],
            "gold": fee, "rate": rate,
            "float": (float_pct / 100.0 if lv >= float_from else 0.0),
            "source": "13_配方域口径_v1 §二 §六",
        }

    recipes["_meta"] = {
        "note": "数值全部由 scripts/rebuild_recipes.py 从源文档解析 —— 别手改本文件",
        "cook": {"ingredients": [n_min, n_max], "seconds": minutes * 60, "choices": choices},
        "enhance": {"cap": cap, "sure_until": sure_until, "rate_from": rate_from,
                    "drop_pct_per_level": rate_drop, "rate_floor_pct": rate_floor,
                    "float_from": float_from, "float_pct": float_pct,
                    "fee_mult": fee_mult, "fee_step": fee_step,
                    "bonus_per_level": bonus_per_level,
                    "bonus_at_cap_pct": round(bonus_per_level * cap * 100, 2)},
        "source": ["05_玩法数值口径_v1 §三", "13_装备玩法与随机性_v1 §1.2",
                   "24_任务线_v1 §二", "00_总纲/13_配方域口径_v1", "旧案 00_装备体系与PE预算 §7.2"],
    }

    # ── ⑦ 药水：能从 desc 里解析出数才写（禁手打）────────────
    heal_patch = {}
    for iid, v in items.items():
        if str(iid).startswith("_"):
            continue
        m = re.search(r"回 (\d+) 点生命", str(v.get("desc") or ""))
        if m:
            heal_patch[iid] = int(m.group(1))

    print("== rebuild_recipes ==")
    print("  烹饪 %d 条（食材 %d–%d 样 · %d 秒增益 · 三选一 %s）"
          % (len(rows), n_min, n_max, minutes * 60, "/".join(choices)))
    print("  强化 %d 档（必成到 +%d · 上限 +%d · %s/%s 各 %s）"
          % (cap, sure_until, cap, mat_a, mat_b, need))
    print("  费：" + str([recipes["rc_enh_%02d" % i]["gold"] for i in range(1, cap + 1)]))
    print("  率：" + str([recipes["rc_enh_%02d" % i]["rate"] for i in range(1, cap + 1)]))
    print("  菜价：" + " · ".join("%s %d" % (dish_meta[k]["name"], dish_meta[k]["price"]) for k in dish_meta))
    print("  药水 heal（解析 desc）：%s" % heal_patch)
    if dry:
        print("  --dry：不写盘")
        return 0

    out = {k: recipes[k] for k in sorted(recipes)}
    with io.open(os.path.join(DATA, "recipes.json"), "w", encoding="utf-8", newline="") as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=2) + "\n")

    changed = []
    for iid, meta in dish_meta.items():
        if items.get(iid) != meta:
            items[iid] = meta
            changed.append(iid)
    for iid, h in heal_patch.items():
        if (items.get(iid) or {}).get("heal") != h:
            items[iid]["heal"] = h
            changed.append(iid + ".heal")
    with io.open(os.path.join(DATA, "items.json"), "w", encoding="utf-8", newline="") as f:
        f.write(json.dumps(items, ensure_ascii=False, indent=2) + "\n")
    print("  写入 recipes.json（%d 条）· items.json 变 %d 处：%s"
          % (len(out), len(changed), changed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
