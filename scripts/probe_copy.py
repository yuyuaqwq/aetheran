# -*- coding: utf-8 -*-
"""探针：代码内联文案（B3-6b）—— 文案真源只有 texts 域，代码只传槽位。

判据（口径：`00_总纲/17_文案收口口径_v1.md` §一）：
  ① 扫 content/*.py 的**含汉字的字符串字面量**（docstring / 注释 / 异常消息 放行）→ 逐文件计数
  ② 收口文件（SEALED）必须 0
  ③ 其余文件 ≤ 快照上限（BUDGET，只降不升）；不在表里的（含新加的文件）默认必须 0
  ④ 代码里 T("KEY") 引用的键都在 texts 里（写错键名 = 运行时静默缺文案，这里拦）
  ⑤ 口径文档里每条槽位都在 texts 里、且被代码引用（防「写了等于没写」）
  ⑥ 真跑一遍实现体（含公会 / 悬赏 / 接 / 交 / 放弃 / 我的委托 六个）：产出的行里不许出现 [MISSING TEXT 标记
  ⑦ quests 域按 chain（ASCII）判别主/支线 —— 数据里挑不出 main / side 就红（B3-6b-2b）
  ⑧ gathering 域按 verb（ASCII）判别采集点 —— 挑不出 herb / dig / fish / search 就红（B3-6b-2c）
  ⑨ 面板分层名（B3-6b-2d）真造一个 actor 逐层核 `src` —— 必须正好是 texts 里那 6 条的字
  ⑩ 去(脚下这一站) 回「到了」不回「过不去」（B3-10 ① —— HERE 那一支真取到）
  ⑪ 呈现口不漏机器键的覆盖面：战斗 / 配方 / 图鉴 / 称号 / 彩蛋 / 时间 也逐行扫（B3-10 ②）

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_copy.py [--inventory]
"""
from __future__ import annotations

import ast
import asyncio
import io
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
PLAN = os.environ.get("AST_PLAN", "C:/Users/yuyu/aetheran-plan")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402

MISSING = "[MISSING TEXT"

#: ★ 已收口（必须 0）—— 收口一个就往这里搬一个
SEALED = ("cmds_ast.py", "cmds_talk.py", "cmds_quest.py", "cmds_gather.py", "panel_build.py")

#: 快照上限（B3-6b 收口时的实测值；**只降不升**，不在表里的文件必须 0）
BUDGET = {                      # B3-6b 收口时实测（124 条）；下一批往下压，只能降
    "cmds_battle.py": 14,       # 战斗结算与日志（B3-8 收掉死亡那两句：改走 SYS_DEATH_*）
    "loot.py": 11,              # 掉落 / 未鉴定 / 鉴定那几句话（B3-7 收掉一条）
    "cmds_recipe.py": 9,        # 配方 / 烹饪 / 强化
    "codex.py": 6,              # 谱的分类名
    "combat.py": 5,             # 战斗里的兜底名
    "apply.py": 2,              # 技能标签（挥击 / 主动）
    "skills_lookup.py": 2,      # 技能标签
}

ok = True


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("OK " if cond else "X  ", label, ("  —— %s" % extra) if extra else ""))


def _docstring_ids(tree):
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                ids.add(id(body[0].value))
    return ids


def _diagnostic_ids(tree):
    """异常消息（raise / *Error / *Exception / *Warning）—— 给写代码的人看的，放行。"""
    ids = set()
    for node in ast.walk(tree):
        hit = isinstance(node, ast.Raise)
        if isinstance(node, ast.Call):
            fn = node.func
            name = getattr(fn, "id", None) or getattr(fn, "attr", None) or ""
            hit = hit or name.endswith("Error") or name.endswith("Exception") or name.endswith("Warning")
        if hit:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    ids.add(id(sub))
    return ids


def scan(path):
    """一个 .py 里的「含汉字的字符串字面量」（docstring / 异常消息 不算）+ T("KEY") 的键。"""
    src = io.open(str(path), encoding="utf-8").read()
    tree = ast.parse(src)
    skip = _docstring_ids(tree) | _diagnostic_ids(tree)
    hits, keys = [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            if any("\u4e00" <= ch <= "\u9fff" for ch in node.value):
                hits.append((node.lineno, node.value))
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "T" and node.args:
            a0 = node.args[0]
            if isinstance(a0, ast.Constant) and isinstance(a0.value, str):
                keys.append(a0.value)
    return hits, keys


class _E:
    """实现体只要 env.save() + env.text（落档是处理器的责任）。"""

    def __init__(self, text=""):
        self.text = text

    def save(self):
        pass


def _drive(fn, p, text=""):
    out = []

    async def go():
        async for line in fn(_E(text), None, "u_copy", p):
            out.append(str(line))

    asyncio.run(go())
    return out


def _node_names(st, loc):
    m = (st.domain("maps") or {}).get(loc) or {}
    return [n.get("name") for n in (m.get("nodes") or [])]


def _main_ids():
    """主线那几条（按 chain=main 挑 —— 与 cmds_quest 同一个判别符）。"""
    from content import cmds_ast as CA
    qs = CA._data("quests")
    return [k for k, v in qs.items() if v.get("chain") == "main"]


def _player(**kw):
    from content import cmds_ast as CA
    p = dict(CA.DEFAULT_PLAYER)
    p.update(kw)
    return p


def main():
    inv = "--inventory" in sys.argv
    print("探针：代码内联文案（B3-6b · 文案真源只有 texts 域）")
    files = sorted((REPO / "content").glob("*.py"))
    counts, ref = {}, {}
    for p in files:
        hits, keys = scan(p)
        counts[p.name] = len(hits)
        for k in keys:
            ref.setdefault(k, []).append(p.name)
    print("  · 内联中文文案：%s" % (" · ".join("%s %d" % (k, v) for k, v in sorted(counts.items()) if v) or "一处都没有"))
    if inv:
        for k, v in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
            if v:
                print("      %-22s %d" % (k, v))
        return 0

    # ② 收口文件必须 0
    dirty = [(k, counts.get(k)) for k in SEALED if counts.get(k)]
    chk("★ 已收口的文件内联中文文案 0 条（%s）" % " / ".join(SEALED), not dirty, "%s" % dirty)

    # ③ 其余文件 ≤ 快照上限（只降不升；不在表里的默认 0）
    over = [(k, v, 0 if k in SEALED else BUDGET.get(k, 0))
            for k, v in counts.items() if v > (0 if k in SEALED else BUDGET.get(k, 0))]
    chk("★ 其余文件不超过快照上限（只降不升 · 新文件默认 0）", not over,
        "超了：%s" % [(k, v, b) for k, v, b in over])

    st = load_stack(str(REPO), inject={
        "db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_copy.db"),
        "clock": time.time})
    st.install()
    tx = st.domain("texts") or {}

    # ⑦ 主/支线判别符（B3-6b-2b：中文枚举 kind -> ASCII chain）
    qs = st.domain("quests") or {}
    have_chain = {v.get("chain") for v in qs.values()}
    miss_chain = sorted({"main", "side"} - have_chain)
    chk("★ 代码按 chain 判别主线/支线：数据里真有 main / side（%d 条委托）" % len(qs),
        not miss_chain, "缺：%s" % miss_chain)

    # ⑧ 采集动词键（B3-6b-2c：中文 kind -> ASCII verb）
    g = st.domain("gathering") or {}
    have_verb = {v.get("verb") for v in g.values()}
    miss_verb = sorted({"herb", "dig", "fish", "search"} - have_verb)
    chk("★ 代码按 verb 判别采集点：数据里真有 herb / dig / fish / search（%d 个点）" % len(g),
        not miss_verb, "缺：%s" % miss_verb)

    # ⑨ 面板分层名（B3-6b-2d）：真造一个 actor（骑士 10 级 + 食物增益 ⇒ 六层全在），逐层核 src
    from content import panel_build as PBL                                # noqa: E402

    pal = sorted(k for k in tx if k.startswith("SYS_PANEL_"))
    want_src = {tx[k]["value"] for k in pal}
    pact = PBL.build_actor("cls_knight", 10, {"STR": 18, "VIT": 13, "WIL": 4}, buffs={"atk": 1.1})
    psrc = [L.get("src") for L in ((PBL.stacks().get(pact["panel_stack"]) or {}).get("layers") or [])]
    chk("★ 面板真跑：%d 层的分段名逐层取自 texts（%s）" % (len(psrc), " / ".join(str(s) for s in psrc)),
        len(pal) == 6 and len(psrc) == 6 and set(psrc) == want_src
        and not any(MISSING in str(s) for s in psrc),
        "槽位 %d · 层 %d · 对不上 %s" % (len(pal), len(psrc), sorted(set(psrc) ^ want_src)))

    # ④ 代码引用的键都在 texts 里
    miss = sorted(k for k in ref if k not in tx)
    chk("★ 代码里 T(\"…\") 引用的键都在 texts 里（%d 个键）" % len(ref), not miss, "%s" % miss[:6])

    # ⑤ 口径表：在 texts 里 · 逐字一致 · 被代码引用
    import rebuild_syscopy as RS                                          # noqa: E402

    rows = RS.parse_doc()
    notx = [r["key"] for r in rows if r["key"] not in tx]
    diff = [r["key"] for r in rows if r["key"] in tx and tx[r["key"]]["value"] != r["value"]]
    unused = [r["key"] for r in rows if r["key"] not in ref]
    chk("★ 口径表 %d 条都落在 texts 里" % len(rows), not notx, "%s" % notx[:6])
    chk("★ 口径表与 texts 逐字一致（防两处口径）", not diff, "%s" % diff[:6])
    chk("★ 口径表每条都被代码引用（防「写了等于没写」）", not unused, "%s" % unused[:6])

    # ⑥ 真跑实现体：产出的行里不许有取不到文案的标记
    from content import cmds_ast as CA                                    # noqa: E402
    from content import cmds_talk as CT                                   # noqa: E402
    from content import cmds_quest as CQ                                  # noqa: E402
    from content import cmds_gather as CG                                 # noqa: E402

    from content import cmds_battle as CBL                                # noqa: E402
    from content import cmds_recipe as CR                                 # noqa: E402
    from content import cmds_codex as CC                                  # noqa: E402
    from content import cmds_title as CTT                                 # noqa: E402
    from content import cmds_egg as CE                                    # noqa: E402

    town = _node_names(st, "windmill_town")
    belt = _node_names(st, "belt_north")
    pois = st.domain("pois") or {}
    read_at = next(((v.get("map"), v.get("subarea"), v.get("name")) for v in pois.values()
                    if v.get("read_text")), ("windmill_town", town[0] and "wt_gate_n", "?"))
    rmap, rnode, rname = read_at
    touch_at = next(((v.get("map"), v.get("subarea")) for v in pois.values()), (rmap, rnode))
    # ★ B3-10：脚下这一站的名字 · 一堆「塞满了东西」的档（呈现口那几条要有内容才扫得出漏键）
    cur = CA._name_of_node("windmill_town", "wt_gate_n")
    _its = {k: v for k, v in (st.domain("items") or {}).items() if not str(k).startswith("_")}
    _wpn = sorted(k for k, v in _its.items() if v.get("kind") == "武器")
    _wpn = (_wpn or [""])[0]
    _tid = next((k for k in sorted(st.domain("titles") or {}) if not str(k).startswith("_")), "")
    _eid = next((k for k in sorted(st.domain("eggs") or {}) if not str(k).startswith("_")), "")

    def _rich(**kw):
        """一口袋全物品 + 等级/族/职业都定过的档（背包 / 图鉴 / 配方 那几条要用）。"""
        over = {"bag": {k: 1 for k in _its}, "codex": {}, "gold": 999, "level": 10,
                "cls": "cls_knight", "race": "elf", "hp": 200, "hp_max": 200,
                "flags": {"quests_done": []}}
        over.update(kw)
        return _player(**over)
    cases = [
        ("观察", CA.look, "", {"loc": "windmill_town", "node": "wt_gate_n"}),
        ("地图", CA.map_view, "", {"loc": "windmill_town", "node": "wt_gate_n"}),
        ("聆听", CA.listen, "", {"loc": "windmill_town", "node": "wt_gate_n"}),
        ("状态", CA.status, "", {"loc": "windmill_town", "node": "wt_gate_n", "level": 3}),
        ("状态(族与职业都定过)", CA.status, "",
         {"loc": "windmill_town", "node": "wt_gate_n", "level": 3, "cls": "cls_knight", "race": "elf"}),
        ("出身", CA.origin, "", {"race": "elf"}),
        ("背包(空)", CA.bag, "", {"bag": {}}),
        ("背包(有东西)", CA.bag, "", {"bag": {"i_material_iron_chip": 2}}),
        ("钱袋", CA.money, "", {"gold": 42}),
        ("提示(镇上)", CA.hint, "", {"loc": "windmill_town"}),
        ("提示(野外)", CA.hint, "", {"loc": "belt_north"}),
        ("帮助", CA.help_cmd, "", {}),
        ("触摸", CA.touch, "", {"loc": touch_at[0], "node": touch_at[1]}),
        ("读", CA.read_thing, "", {"loc": rmap, "node": rnode}),
        ("去(没给地方)", CA.go_to, "去", {"loc": "windmill_town", "node": "wt_gate_n"}),
        ("去(走到)", CA.go_to, "去 %s" % town[3], {"loc": "windmill_town", "node": "wt_gate_n"}),
        ("去(不是邻居)", CA.go_to, "去 %s" % belt[-1], {"loc": "belt_north", "node": "bn_bone"}),
        ("去(没这地方)", CA.go_to, "去 高塔", {"loc": "windmill_town", "node": "wt_gate_n"}),
        ("北口", CA.go_north, "", {"loc": "windmill_town", "node": "wt_gate_n"}),
        ("往东", CA.go_east, "", {"loc": "windmill_town", "node": "wt_gate_n"}),
        ("往西", CA.go_west, "", {"loc": "windmill_town", "node": "wt_gate_n"}),
        ("进镇", CA.enter_town, "", {"loc": "belt_north", "node": "bn_bone"}),
        ("返回(有上一处)", CA.go_back, "", {"loc": "belt_east", "node": "be_birch",
                                          "prev": [["windmill_town", "wt_gate_n"]]}),
        ("返回(没上一处)", CA.go_back, "", {"loc": "windmill_town", "node": "wt_gate_n", "prev": []}),
        ("搭话(这儿有谁)", CT.talk, "搭话", {"loc": "windmill_town", "node": "wt_gate_n"}),
        ("搭话(没有这个人)", CT.talk, "搭话 不存在的人", {"loc": "windmill_town", "node": "wt_gate_n"}),
        ("搭话(这儿没人)", CT.talk, "搭话", {"loc": "belt_north", "node": "bn_bone"}),
        ("问路(镇上)", CT.ask_way, "", {"loc": "windmill_town", "node": "wt_gate_n"}),
        ("问路(野外)", CT.ask_way, "", {"loc": "belt_north", "node": "bn_bone"}),
        # 公会与委托（B3-6b-2b：34 个槽位逐个真跑一遍 —— 不许出现取不到文案）
        ("公会", CQ.guild, "", {}),
        ("悬赏(下一条)", CQ.board, "", {"level": 3}),
        ("悬赏(已接)", CQ.board, "", {"level": 3, "flags": {"quests_active": ["q_main_01"]}}),
        ("悬赏(主线走完)", CQ.board, "", {"flags": {"quests_done": _main_ids()}}),
        ("接(没给编号)", CQ.quest_accept, "接", {"level": 5}),
        ("接(接下了)", CQ.quest_accept, "接 1", {"level": 5}),
        ("接(等级不够)", CQ.quest_accept, "接 12", {"level": 1}),
        ("接(没这条)", CQ.quest_accept, "接 99", {"level": 5}),
        ("接(已经接过)", CQ.quest_accept, "接 1", {"level": 5, "flags": {"quests_active": ["q_main_01"]}}),
        ("交(手上没有)", CQ.quest_deliver, "交 1", {"level": 5}),
        ("交(不在手上)", CQ.quest_deliver, "交 99", {"level": 5, "flags": {"quests_active": ["q_main_01"]}}),
        ("交(还没做完)", CQ.quest_deliver, "交 12", {"level": 5, "flags": {"quests_active": ["q_main_12"]}}),
        ("交(交掉了·升级)", CQ.quest_deliver, "交 1", {"level": 1, "exp": 39,
                                                        "flags": {"quests_active": ["q_main_01"]}}),
        ("放弃(手上没活)", CQ.quest_abandon, "放弃", {}),
        ("放弃(没这条)", CQ.quest_abandon, "放弃 不存在这条", {"flags": {"quests_active": ["q_main_01"]}}),
        ("放弃(放弃了)", CQ.quest_abandon, "放弃", {"flags": {"quests_active": ["q_main_01"]}}),
        ("我的委托(空的)", CQ.quest_mine, "", {}),
        ("我的委托(有活)", CQ.quest_mine, "", {"flags": {"quests_active": ["q_main_01"],
                                                          "quests_done": ["q_main_02"]}}),
        # 野外采集（B3-6b-2c：11 个槽位逐个真跑一遍）
        ("采集(有)", CG.gather, "", {"loc": "windmill_town", "node": "wt_wall"}),
        ("采集(这儿没有)", CG.gather, "", {"loc": "windmill_town", "node": "wt_gate_n"}),
        ("采集(今天翻过了)", CG.gather, "", {"loc": "windmill_town", "node": "wt_wall",
                                              "flags": {"gather_used": {"gt_wt_herb_1": 3}}}),
        ("挖掘(有)", CG.dig, "", {"loc": "belt_north", "node": "bn_bone"}),
        ("垂钓(有)", CG.fish, "", {"loc": "belt_west", "node": "bw_old_ferry"}),
        ("搜查(有)", CG.search, "", {"loc": "belt_east", "node": "be_birch"}),
        ("歇脚(不累)", CG.rest, "", {"hp": 100, "hp_max": 100}),
        ("歇脚(歇下了)", CG.rest, "", {"hp": 40, "hp_max": 100}),
        ("拾取", CG.pick_up, "", {}),
        # ★ B3-10 ①：去「脚下这一站」（原先错走 SYS_MOVE_FAR 那一支）
        ("去(就在这儿)", CA.go_to, "去 %s" % cur, {"loc": "windmill_town", "node": "wt_gate_n"}),
        # ★ B3-10 ②：K56 族的另一半 —— 这些呈现口原先没被逐行扫过
        ("时间", CA.time_now, "", {"loc": "windmill_town", "node": "wt_gate_n"}),
        ("背包(满)", CA.bag, "", _rich()),
        ("攻击(野外)", CBL.attack, "",
         {"loc": "belt_north", "node": "bn_bone", "level": 3, "hp": 80, "hp_max": 100,
          "bag": {}, "codex": {}, "flags": {}}),
        ("防御", CBL.defend, "", {}),
        ("逃跑", CBL.flee, "", {}),
        ("战斗日志(没打过)", CBL.battle_log, "", {}),
        ("战斗日志(有)", CBL.battle_log, "",
         {"flags": {"last_battle": {"enemy": "灰狼", "result": "victory",
                                      "logs": ["你挥了一刀", "灰狼倒下了"]}}}),
        ("配方(会做与没学会)", CR.recipe_list, "", {"flags": {"quests_done": []}}),
        ("配方(全学会)", CR.recipe_list, "", _rich()),
        ("烹饪(没给菜名)", CR.cook, "烹饪", {}),
        ("烹饪(没有这道)", CR.cook, "烹饪 不存在的菜", {}),
        ("烹饪(有料)", CR.cook, "烹饪 苦叶汤", _rich()),
        ("铁匠铺", CR.smith, "", {}),
        ("强化(没给)", CR.enhance, "强化", {}),
        ("强化(没有这件)", CR.enhance, "强化 不存在的剑", {}),
        ("强化(料不够)", CR.enhance, "强化 %s" % _its.get(_wpn, {}).get("name", "剑"),
         {"bag": {_wpn: 1}} if _wpn else {}),
        ("使用(没给东西)", CR.item_use, "使用", {}),
        ("使用(药水)", CR.item_use, "使用 药水", {"bag": {"i_potion_heal": 1}}),
        ("使用(伤药)", CR.item_use, "使用 伤药", {"bag": {"i_potion_minor": 1}, "hp": 10, "hp_max": 100}),
        ("图鉴(空)", CC.codex, "", {}),
        ("图鉴(满)", CC.codex, "", _rich()),
        ("材料谱(空)", CC.codex_material, "", {}),
        ("材料谱(有)", CC.codex_material, "", _rich()),
        ("风味谱(有)", CC.codex_flavor, "", _rich()),
        ("怪物谱(空)", CC.codex_monster, "", {}),
        ("旧物谱(有)", CC.codex_relic, "", _rich()),
        ("记录", CC.footprint, "", _rich()),
        ("称号(一个都没有)", CTT.titles_book, "", {}),
        ("称号(有)", CTT.titles_book, "", {"titles": {_tid: {"day": 1}}} if _tid else {}),
        ("彩蛋(一个都没有)", CE.eggs_book, "", {}),
        ("彩蛋(有)", CE.eggs_book, "", {"eggs": {_eid: {"day": 2}}} if _eid else {}),
    ]
    bad, empty, sample = [], [], []
    leaked = []
    _KEYS = [k for d in ("items", "monsters", "pois", "classes", "races", "quests",
                         "gathering", "drop_pools", "recipes", "npcs", "skills", "eggs",
                         "titles", "dialogues")
             for k in (st.domain(d) or {})]
    for label, fn, text, over_ in cases:
        out = _drive(fn, _player(**over_), text)
        for line in out:                       # ★ B3-9：呈现口不许漏机器键（B3-7 同族）
            hit = [k for k in _KEYS if k in line]
            if hit:
                leaked.append((label, hit[:2], line[:40]))
        if not out:
            empty.append(label)
        if any(MISSING in ln for ln in out):
            bad.append(label)
        if len(sample) < 3:
            sample.append("%s -> %s" % (label, out[0][:26] if out else "(空)"))
    chk("★ 真跑 %d 个实现体：每一个都出话（没有空回）" % len(cases), not empty, "%s" % empty)
    chk("★ 一个取不到文案的都没有（不出现 %s）" % MISSING, not bad, "%s" % bad)
    chk("★ 呈现口不漏机器键（%d 个域键 · %d 条用例逐行扫）" % (len(_KEYS), len(cases)), not leaked,
        "%s" % leaked[:4])
    # ⑩ B3-10 ①：`去 <脚下这一站>` —— 回的是「到了」，不是「过不去」
    here_out = _drive(CA.go_to, _player(loc="windmill_town", node="wt_gate_n"), "去 %s" % cur)
    here_want = tx["SYS_MOVE_HERE"]["value"].replace("{name}", cur)
    far_txt = tx["SYS_MOVE_FAR"]["value"].replace("{name}", cur)
    chk("★ 去(脚下这一站 %s)：出 HERE 那一句、不出 FAR" % cur,
        bool(here_out) and here_out[0] == here_want and far_txt not in chr(10).join(here_out),
        "%s" % (here_out[:2] if here_out else ["(空)"]))

    print("  · 打样：%s" % " ｜ ".join(sample))

    print("")
    print("探针：%s" % ("全绿 ✓" if ok else "有红 ✗"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
