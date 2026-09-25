# -*- coding: utf-8 -*-
"""B3-4 装备事件 · 物品表裁决（P-15）与出产 —— 脚本落域，禁手打数值。

真源：`aetheran-plan/06_第一阶段垂直切片/30_装备事件_设计_v1.md`
      （§二 = P-15 四条裁决 · §三 = 6 条事件挂在哪 · §六 = 落地清单）
上游：`21_长期目标层_v1.md §四`（6 条装备事件）· `15_装备逐件数值_v1.md`（逐件数值）

本脚本只做**两件有数 / 有 id 的事**（文案与挂载不在这里 —— 见下）：
  ① items 域：P-15 四条裁决落地 ——
     · 新做信物「石阶缺的那一级」（= 21 §四「水下的石阶（钓上的那件）」）
     · 套装件 `i_set_northwall_shard` 改名「北墙根的碎石」（原名与信物 `i_token_stone_shard` 撞名）
     · 删掉没人读的道具号角 `i_item_horn_half`（与信物 `i_horn_half` 撞名）
     · 护符留数据里的名「老人的护符」（裁决 ④：**改 21 文档去对齐数据**，不是反过来）
  ② gathering 域：新信物的出产挂**浅滩钓点的稀有位** —— 点与权重都从数据现算：
     点 = 垂钓点里节点名含「浅滩」的那一个；权重 = 该域「关键物」的现成惯例（5 个搜查点的套装件都是 10），
     并要求它确实比该池里别的条目都小（= 最稀的那一位 ⇒ 反复采时最先被捡走）。

★ 机器键：新信物那条记录里 `kind` 与 `kind_key` **成对写**，表 = `rebuild_kind_keys.ITEM_KIND_KEY`
  （单一来源 · 不抄第二份）—— 落完再跑 `rebuild_kind_keys.py` 是 0 处要补（幂等）。

不在本脚本里的（**因为它们不是表**）：
  · 6 处挂载（dialogues 域 5 处 `need.holding` · monsters 域 1 处战内台词）= 手写在域里。
    理由（B1-4 先例）：对话文案的真源就是 dialogues 域自身，给它再加一层生成器 = 两处口径。
    本脚本只**守卫**这几处逐字在位（缺了就抛，不静默）。
  · 那 6 句文案 = 域内联（域形状只认 `text` 字符串，没有槽位字段 —— 见 `_notes.md`）。

用法：
  python scripts/rebuild_equip_events.py --dry     # 只看要改什么，不写
  python scripts/rebuild_equip_events.py           # 落域（幂等：连跑两次数据不变）
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

#: ★ 机器键那张表（中文 kind → ASCII kind_key）的**唯一来源**就是这支生成器 ——
#:   这里 import 它，不另抄一份（P-41：两处口径打架的根因）。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rebuild_kind_keys as KK                                     # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.environ.get("AST_PLAN", "C:/Users/yuyu/aetheran-plan")
DOC = os.path.join(PLAN, "06_第一阶段垂直切片", "30_装备事件_设计_v1.md")
DATA = os.path.join(REPO, "content", "data")

#: 新信物 —— 名字**不叫**「水下的石阶」（那是 pois 域里那处地方的名字）。
#: 照 P-15 的判定原则「哪一边更像『东西本身』就留哪边」：地点留「水下的石阶」，
#: 钓上来的这件东西叫「石阶缺的那一级」—— 两处同名 = 又一对双源（探针判据 ③ 拦它）。
#: `desc` 是真源两句话的合并：21 §四「水下的石阶（钓上的那件）」+ 28 §q_trade_06
#: 「在浅滩钓到一个不是鱼的东西」；`lore`（来处）直接取包内 codex 旧物谱那一条（同一真源，不另写）。
NEW_ITEM_ID = "i_token_underwater_steps"
NEW_ITEM_NAME = "石阶缺的那一级"
NEW_ITEM_DESC = "浅滩钓上来的那块。退潮的时候，水底下那截石阶少了一级。"
NEW_ITEM_ICON = "🪨"                       # 石头类（信物里的石片用的就是它）
NEW_ITEM_SRC = "poi_underwater_steps"      # 那处地方：pois 域 + codex 旧物谱

#: 挂载守卫（手写在域里；本脚本只核它们逐字在位）
MOUNTS = [("dlg_hagen", "hidden", "i_set_sentry_gauntlet"),
          ("dlg_pete", "hidden", "i_horn_half"),
          ("dlg_seran", "hidden", "i_token_stone_shard"),
          ("dlg_ed", "hidden", "i_set_northwall_amulet"),
          ("dlg_lian", "main", NEW_ITEM_ID)]
BATTLE_MOUNT = ("ms_pick_scavenger", "i_set_scavenger_blade")


def _load(name):
    return json.loads(io.open(os.path.join(DATA, name + ".json"), encoding="utf-8").read())


def _dump(name, obj):
    io.open(os.path.join(DATA, name + ".json"), "w", encoding="utf-8", newline="\n").write(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def _doc():
    with io.open(DOC, encoding="utf-8") as f:
        return f.read()


def verdict_rows(doc):
    """§二 P-15 那四条裁决 —— 值 = [21 文档写的, 物品表实况, 建议]。缺一条就抛。"""
    rows = {}
    for line in doc.splitlines():
        m = re.match(r"^\|\s*([①②③④])\s*\|(.+)\|\s*$", line)
        if m:
            rows[m.group(1)] = [c.strip() for c in m.group(2).split("|")]
    miss = [k for k in "①②③④" if k not in rows]
    if miss:
        raise RuntimeError("真源 §二 缺裁决行：%s" % miss)
    return rows


def event_rows(doc):
    """§三 6 条事件的挂载表 —— 序号 → [装备, 谁的哪句话, 落哪]。"""
    rows = {}
    for line in doc.splitlines():
        m = re.match(r"^\|\s*([1-6])\s*\|(.+)\|\s*$", line)
        if m:
            rows[int(m.group(1))] = [c.strip() for c in m.group(2).split("|")]
    if len(rows) != 6:
        raise RuntimeError("真源 §三 应有 6 行，实得 %d" % len(rows))
    return rows


def _ids(cell):
    return re.findall(r"`(i_[a-z0-9_*]+)`", cell)


_QUOTED = re.compile(r"「([^」]+)」")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")


def _resolve_glob(items, cell):
    """§三 一格「装备」→ items 里的 id。

    优先反引号里的**具体** id；带 `*` 的（`i_set_sentry_*` / `i_set_scavenger_*`）按
    「前缀 + 名字尾两个字」唯一命中 —— 真源这边写「拾荒人的短刃」、数据里叫「拾荒者的短刃」
    （人 / 者），不能靠逐字相等。
    """
    ids = _ids(cell)
    exact = [i for i in ids if not i.endswith("*")]
    if exact:
        if len(exact) != 1:
            raise RuntimeError("§三 这一格反引号里不止一个 id：%r" % cell)
        if exact[0] not in items:
            raise RuntimeError("§三 点名的 id 不在物品表里：%s" % exact[0])
        return exact[0]
    name = _BOLD.sub(r"\1", re.sub(r"（[^）]*）", "", cell)).replace("`", "").strip()
    hit = [k for k, v in items.items() if v.get("name") == name]
    if len(hit) == 1:
        return hit[0]
    glob = [i for i in ids if i.endswith("*")]
    if len(glob) == 1:
        pre, tail = glob[0][:-1], name[-2:]
        cand = [k for k, v in items.items()
                if k.startswith(pre) and tail and tail in str(v.get("name") or "")]
        if len(cand) == 1:
            return cand[0]
        raise RuntimeError("§三 「%s」在 %s 里对不上一件（命中 %s）" % (name, glob[0], cand))
    raise RuntimeError("§三 这一格对不出一件东西：%r（逐字命中 %s）" % (cell, hit))


def _mount_of(cell):
    """§三 一格「落哪」→ 消费端：NPC（`npc_xxx`）或战内的怪（`ms_xxx`）。"""
    for kind in ("npc_", "ms_"):
        m = re.search(r"`(" + kind + r"[a-z_]+)`", cell)
        if m:
            return m.group(1)
    raise RuntimeError("§三 这一格既没有 npc 也没有怪：%r" % cell)


def _refs_elsewhere(needle, skip):
    """除 skip 这几份文件之外还有谁提到这个 id —— 删数据前必须证明它没人读。

    （跳过的那两份：items.json 自己那一行、以及本脚本 —— 它就是宣告要删谁的地方。）
    """
    skip = {os.path.abspath(x) for x in ((skip,) if isinstance(skip, str) else skip)}
    out = []
    for root, _dirs, files in os.walk(REPO):
        if os.sep + ".git" in root:
            continue
        for fn in files:
            if not fn.endswith((".py", ".json", ".md")):
                continue
            p = os.path.join(root, fn)
            if os.path.abspath(p) in skip:
                continue
            try:
                if needle in io.open(p, encoding="utf-8").read():
                    out.append(os.path.relpath(p, REPO))
            except (OSError, UnicodeDecodeError):
                continue
    return out


def main():
    dry = "--dry" in sys.argv
    doc = _doc()
    V = verdict_rows(doc)
    EV = event_rows(doc)
    items = _load("items")
    gath = _load("gathering")
    codex = _load("codex")
    pois = _load("pois")
    changes = []

    # ── 裁决 ①：新做「水下的石阶（钓上的那件）」= 信物 ────────────────────────
    if "做出来" not in V["①"][2]:
        raise RuntimeError("真源 ① 的建议不是「做出来」：%r" % V["①"][2])
    kind_m = _BOLD.search(V["①"][2].split("归")[-1]) if "归" in V["①"][2] else None
    kind = (kind_m.group(1) if kind_m else "").strip()
    if kind not in ("信物",):
        raise RuntimeError("真源 ① 没写「归信物」（拿到 %r）—— 新东西的 kind 要照它" % kind)
    if "浅滩钓点" not in V["①"][2] or "稀有位" not in V["①"][2]:
        raise RuntimeError("真源 ① 没写出产挂「浅滩钓点的稀有位」：%r" % V["①"][2])
    src = (codex.get("relic") or {}).get(NEW_ITEM_SRC) or {}
    if not src.get("hint"):
        raise RuntimeError("codex 旧物谱里没有 %s 的 hint（来处没处取）" % NEW_ITEM_SRC)
    if NEW_ITEM_SRC not in pois:
        raise RuntimeError("pois 里没有 %s —— 新信物正是那处地方的东西" % NEW_ITEM_SRC)
    # ★ P-41：机器键 `kind_key` 与中文 `kind` **成对写**（表取自 rebuild_kind_keys.ITEM_KIND_KEY）。
    #   缺这一格 ⇒ `rebuild_kind_keys` 补完之后本脚本重跑即炸（逐字比对不过 · 波九就记过一笔）。
    kind_key = KK.ITEM_KIND_KEY.get(kind)
    if not kind_key:
        raise RuntimeError("★ kind=%r 不在机器键表里（先补 rebuild_kind_keys.ITEM_KIND_KEY 与 schema enum）"
                           % kind)
    want_item = {"name": NEW_ITEM_NAME, "icon": NEW_ITEM_ICON, "kind": kind, "kind_key": kind_key,
                 "quality": "遗物", "price": 0, "lore": src["hint"], "desc": NEW_ITEM_DESC}
    if NEW_ITEM_ID in items:
        if items[NEW_ITEM_ID] != want_item:
            raise RuntimeError("★ %s 已存在且与本次口径逐字不同：%s" % (NEW_ITEM_ID, items[NEW_ITEM_ID]))
    else:
        items[NEW_ITEM_ID] = want_item
        changes.append("items: 新增%s %s（%s）—— 来处取自 codex.relic.%s.hint"
                       % (kind, NEW_ITEM_ID, NEW_ITEM_NAME, NEW_ITEM_SRC))

    # ── 裁决 ②：套装件改名（原名与信物 `i_token_stone_shard` 撞名）────────────
    pair = _ids(V["②"][1])
    if len(pair) != 2:
        raise RuntimeError("真源 ② 应当点名两个同名 id，实得 %s" % pair)
    keep_shard = [i for i in pair if (items.get(i) or {}).get("kind") == "信物"]
    drop_shard = [i for i in pair if i not in keep_shard]
    if len(keep_shard) != 1 or len(drop_shard) != 1:
        raise RuntimeError("真源 ② 的两个 id 在物品表里看不出「信物 / 套装件」：%s" % pair)
    keep_shard, rename_shard = keep_shard[0], drop_shard[0]
    q = re.search(r"改名[^「]*「([^」]+)」", V["②"][2])
    if not q:
        raise RuntimeError("真源 ② 没写改名的目标名")
    want = q.group(1)
    if keep_shard != "i_token_stone_shard" or items[keep_shard].get("name") != "刻字的石片":
        raise RuntimeError("★ 留名的那件应当是信物 i_token_stone_shard「刻字的石片」，实得 %s"
                           % keep_shard)
    cur = items[rename_shard].get("name")
    if cur != want:
        if cur != "刻字的石片":
            raise RuntimeError("★ %s 的名字是 %r —— 既不是旧名也不是目标名，停（先裁决谁对）"
                               % (rename_shard, cur))
        items[rename_shard]["name"] = want
        changes.append("items.%s.name: 刻字的石片 → %s" % (rename_shard, want))

    # ── 裁决 ③：半截号角只留信物那个 id ──────────────────────────────────────
    pair = _ids(V["③"][1])
    keep_horn = _ids(V["③"][2])
    if len(pair) != 2 or len(keep_horn) != 1:
        raise RuntimeError("真源 ③ 应当点名两个同名 id 并指明留哪一个（%s / %s）" % (pair, keep_horn))
    keep_horn, drop_horn = keep_horn[0], [i for i in pair if i != keep_horn[0]]
    if keep_horn != "i_horn_half" or (items.get(keep_horn) or {}).get("kind") != "信物":
        raise RuntimeError("★ ③ 留的应当是信物 %s" % keep_horn)
    for dead in drop_horn:
        if dead not in items:
            continue
        refs = _refs_elsewhere(dead, [os.path.join(DATA, "items.json"), os.path.abspath(__file__)])
        if refs:
            raise RuntimeError("★ %s 还有人引用（%s）—— 不能删" % (dead, refs[:4]))
        del items[dead]
        changes.append("items: 删 %s（与信物 %s 撞名 · 全仓零引用）" % (dead, keep_horn))

    # ── 裁决 ④：护符留数据里的名（改 21 文档去对齐数据）──────────────────────
    amulet = _ids(V["④"][1])
    if len(amulet) != 1:
        raise RuntimeError("真源 ④ 应当点名一个 id，实得 %s" % amulet)
    q = re.search(r"数据留[^「]*「([^」]+)」", V["④"][2])
    if not q:
        raise RuntimeError("真源 ④ 没写留哪个名")
    if (items.get(amulet[0]) or {}).get("name") != q.group(1):
        raise RuntimeError("★ %s 的名字不是「%s」—— 裁决 ④ 是「留数据侧」，别动"
                           % (amulet[0], q.group(1)))

    # ── §三 6 行：挂载对账（id 都指向真物品；消费端真存在）───────────────────
    maps = _load("maps")
    npcs = _load("npcs")
    mounts = []
    for no in sorted(EV):
        cells = EV[no]
        if no == 6:
            iid = NEW_ITEM_ID                     # 真源写「（新做的那件）」
        else:
            iid = _resolve_glob(items, cells[0])
        who = _mount_of(cells[2])
        mounts.append((no, iid, who))
        if who.startswith("npc_"):
            npc = npcs.get(who)
            if not npc:
                raise RuntimeError("§三 第 %d 条点名的人不在 npcs 域：%s" % (no, who))
            node = npc.get("subarea")
            if node not in [n.get("id") for n in ((maps.get(npc.get("map")) or {}).get("nodes") or [])]:
                raise RuntimeError("§三 第 %d 条的 %s 站的位置不在真图上（%s）" % (no, who, node))
    print("  · 真源 §三 → 数据：")
    for no, iid, who in mounts:
        print("      %d) %-28s → %-22s %s" % (no, iid, who,
                                              (items.get(iid) or {}).get("name", "")))

    # ── 出产：浅滩钓点的稀有位 ─────────────────────────────────────────────
    fish = [(k, v) for k, v in gath.items() if not str(k).startswith("_") and v.get("verb") == "fish"]
    def _node_name(v):
        return [n.get("name") for n in ((maps.get(v.get("map")) or {}).get("nodes") or [])
                if n.get("id") == v.get("subarea")]
    hit = [(k, v) for k, v in fish if _node_name(v) and "浅滩" in _node_name(v)[0]]
    if len(hit) != 1:
        raise RuntimeError("真源说「浅滩钓点」，可垂钓点里对得上浅滩的有 %d 个（%s）"
                           % (len(hit), [k for k, _ in fish]))
    point_id, pt = hit[0]
    key_w = [int(e.get("w", 1) or 1) for g in gath.values() if not str(g).startswith("_")
             for e in (g.get("pool") or []) if str(e.get("out") or "").startswith("i_set_")]
    if not key_w:
        raise RuntimeError("gathering 域里取不到「关键物」的权重惯例")
    rare_w = min(key_w)
    others = [int(e.get("w", 1) or 1) for e in pt.get("pool") or [] if e.get("out") != NEW_ITEM_ID]
    if others and rare_w >= min(others):
        raise RuntimeError("★ w=%d 压不过 %s 池里别的条目（%s）—— 那就不是「稀有位」"
                           % (rare_w, point_id, others))
    want_entry = {"out": NEW_ITEM_ID, "w": rare_w, "n": [1, 1]}
    pool = pt.setdefault("pool", [])
    same = [e for e in pool if e.get("out") == NEW_ITEM_ID]
    if same:
        if same[0] != want_entry:
            raise RuntimeError("★ %s 的出产条目已存在且不同：%s" % (point_id, same[0]))
    else:
        pool.append(want_entry)
        changes.append("gathering.%s.pool: +%s（w=%d = 该域关键物惯例 < 池里最小的 %d ⇒ 最稀的那一位）"
                       % (point_id, NEW_ITEM_ID, rare_w, min(others or [0])))

    # ── 守卫：6 处挂载必须逐字在位 ─────────────────────────────────────────
    dl = json.loads(io.open(os.path.join(DATA, "dialogues.json"), encoding="utf-8").read())
    for tree, node_key, iid in MOUNTS:
        texts = ((dl.get(tree) or {}).get("nodes") or {}).get(node_key, {}).get("texts") or []
        if not [t for t in texts if (t.get("need") or {}).get("holding") == iid]:
            raise RuntimeError("★ 挂载缺：%s/%s 没有 holding=%s 的那条（手写在域里）"
                               % (tree, node_key, iid))
    mon = json.loads(io.open(os.path.join(DATA, "monsters.json"), encoding="utf-8").read())
    lines = (mon.get(BATTLE_MOUNT[0]) or {}).get("encounter_lines") or []
    if not [x for x in lines if (x.get("need") or {}).get("holding") == BATTLE_MOUNT[1]]:
        raise RuntimeError("★ 战内台词缺：%s 没有 holding=%s 的那条" % BATTLE_MOUNT)

    # ── 落域 ──────────────────────────────────────────────────────────────
    for c in changes:
        print("  · " + c)
    if not changes:
        print("  · 没有要改的（幂等：已经是这一版）")
    if dry:
        print("（--dry：没写文件）")
        return 0
    _dump("items", items)
    _dump("gathering", gath)
    print("落域完成：items %d 条 · %s 池 %d 条" % (len(items), point_id, len(gath[point_id]["pool"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
