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
  ⑫ 四条出口（北口/往东/往西/进镇）站在**目的地**上敲 = 回 HERE、不演出门、不塞历史（B3-11 · K60）
  ⑬ 默认档不许被就地改（B3-12 · K57）：真跑完一遍后 bag/equipped/flags/codex 必须原样；
     半截老档（缺这几个键）采集一趟，不许把东西写进默认档、也不许串给下一个人
  ⑭ ★ P-27：还没择业的档（无职业）= 没有面板 ⇒ `状态` 的生命上限照实说「未定」，
     要数字的地方（打架 / 歇脚）出一行点名行、不许显示那两个写死的 100
     （三处一致 + 反证那几条在 probe_panel 里）
  ⑮ ★ B3-6b-2d-b / keys-2：静态守卫 —— content/*.py 里不许再**拿中文枚举当机器键**
     （K48 / K51 / P-20：黑名单 = 域里现成的枚举字段取值）。**两刀收完 ⇒ 必须 0 处**
     （装备走 ASCII `slot` · 技能走 `owner_class` · 其余走域里新增的 `kind_key` / `role_key`）。
     另钉一份「已收口的取值」清单（ENUM_DONE，只许变长）。
  ⑯ ★ B3-6b-2d-keys-2：代码里比的 ASCII 机器键**都在域里真出现过**
     （role_key / kind_key / pool / unidentified / cook —— 与 ⑦ chain / ⑧ verb 同款）。
  ⑰ ★ B3-9（装备与技能那组）：新接的 5 条（装备 / 卸下 / 装备对比 / 学习 / 技能）也进用例表 ——
     主要支路各跑一遍（穿 / 换下同格 / 已经穿着 / 不是能穿的 / 身上没有 / 位子空着 /
     还没择业），于是 ⑥ 的「不缺文案」与「不漏机器键」两条**自动**罩到它们身上。
  ⑱ ★ B3-16b（这一批）：新接的 9 条里能按四参帧直调的那 8 条（教堂 / 客栈 / 商队 / 旧货 /
     登记 / 评级 / 改名 / 公告）也进用例表，主要支路各跑一遍（野外 / 镇上没走到那一站 /
     档上还没择业 / 有证没证 / 改过没改过 …）；`排行` 是五参帧（group_id + uid + player），
     单独真跑两档 —— 同样过 ⑥ 那两条，也一并进 ⑬ 的「默认档不许被就地改」。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_copy.py [--inventory]
"""
from __future__ import annotations

import ast
import asyncio
import copy
import io
import json
import os
import re
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
SEALED = ("cmds_ast.py", "cmds_talk.py", "cmds_quest.py", "cmds_gather.py", "panel_build.py",
          "skills_lookup.py",          # ← B3-6b-2d-b（技能那半走 ASCII `owner_class`）
          "codex.py")                  # ← B3-6b-2d-keys-2（图鉴归属走 ASCII `kind_key`）

#: 快照上限（B3-6b 收口时的实测值；**只降不升**，不在表里的文件必须 0）
BUDGET = {                      # B3-6b 收口时实测（124 条）；下一批往下压，只能降
    "cmds_battle.py": 11,       # ← 6b-2d-keys-2：14 → 11（掉钱分档 3 处中文 role 枚举改走 ASCII `role_key`）
    "loot.py": 3,               # ← 6b-2d-b 11 → 6（装备 5 处）· 6b-2d-keys-2 6 → 3（兜底 / 池 / 未鉴定）
    "cmds_recipe.py": 2,        # ← 6b-2d-b 9 → 3（强化白名单 6 处）· keys-2 3 → 2（「烹饪」）
    "combat.py": 1,             # ← 6b-2d-keys-2：5 → 1（怪 role 兜底与两支筛选 4 处；余「无名者」）
    "apply.py": 1,              # ← 6b-2d-b：2 → 1（技能类别值改从 skills 域取；余「挥击」）
}

#: ★ B3-6b-2d-b / keys-2：「中文枚举当机器键」的收口快照（＝每个 content/*.py 里还剩几处）——
#: ★ 第二刀（B3-6b-2d-keys-2）已把它**整体清空**：判据从「≤ 快照」改成「**必须 0**」。
#: 黑名单见 `_enum_words()`：只收**域里现成的枚举字段取值**（items.kind/quality · monsters.role ·
#: recipes.kind · skills.kind · gathering.kind/verb · drop_pools 的 kind 与条目 kind），纯文案不算。
#: 两刀一共收掉 31 处：装备那半 items.kind → ASCII `slot`（loot 5 · cmds_recipe 6）·
#: 技能那半 skills.kind → ASCII `owner_class` + 域里那一份值（skills_lookup 2 · apply 1）·
#: 非装备 items.kind → `kind_key`（codex 6 · loot 1）· monsters.role → `role_key`（combat 4 ·
#: cmds_battle 3）· recipes.kind → `kind_key`（cmds_recipe 1）· drop_pools 的池 / 未鉴定
#: → `kind_key`（loot 2）。
ENUM_KEYS = {}

#: ★ 已收口的那些中文枚举取值 —— 哪个文件里都不许再当机器键出现（清单只许变长，不许变短）。
#: 第一刀：装备六类 `kind`（替身 = `slot`）与技能类别「主动」（替身 = `owner_class`）。
#: 第二刀：非装备六类 `kind` + 池侧 `kind` + 怪的五档 `role` + 配方的两类 `kind`
#: （替身 = `kind_key` / `role_key`；取值口径见 `scripts/rebuild_kind_keys.py` /
#: `rebuild_monsters.py` / `rebuild_recipes.py` 里那三张表）。
ENUM_DONE = ("武器", "上甲", "下甲", "头盔", "靴子", "饰品", "主动",
             "材料", "食物", "道具", "垃圾", "信物", "线索", "未鉴定", "池", "装备",
             "普通", "精英", "头目", "层主",
             "烹饪", "强化")

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
    # ★ 槽位键**以字符串字面量出现**也算「被代码引用」（不限于 `T("…")` 直调）：
    #   例（B3-5「异动」）：`slot = "SYS_EV_ROW_NEW" if 新开 else "SYS_EV_ROW"` 之后再 `T(slot, …)`
    #   —— 静态只认 `T("…")` 会把它误判成「写了等于没写」。
    import re as _re                                                       # noqa: E402
    _lit = _re.compile(r'["\']([A-Z][A-Z0-9_]{3,})["\']')
    ref_lit = set()          # ★ 只给「每条都被引用」那条用（不是 T(…) 直调，别混进 ④）
    #   · 槽位名**由模板拼出来**的也算引用：形如 `"QUEST_MAIN%02d_%s" % (order, part)`
    #     —— 键在那份文本里搜不到字面量，但它确实是代码算出来的那个键。
    _spec = _re.compile(r"%[-+ #0-9.]*[a-zA-Z]")
    _tl = _re.compile(r'["\']([A-Za-z][A-Za-z0-9_%]{4,})["\']')
    _tpl_rx = []
    for p in files:
        txt = p.read_text(encoding="utf-8")
        for lit in _lit.findall(txt):
            ref_lit.add(lit)
        for lit in _tl.findall(txt):
            if not _spec.search(lit):
                continue
            chunks = [c for c in _spec.split(lit) if c]
            if chunks:
                _tpl_rx.append(_re.compile("^" + ".*".join(_re.escape(c) for c in chunks) + ".*$"))
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

    # ⑮ ★ B3-6b-2d-b：静态守卫 —— 不许再**拿中文枚举当机器键**（K48 / K51 / P-20）
    #   黑名单 = **域里现成的枚举字段取值**（只收这几族，纯文案天然不进来）：
    #     items.kind / items.quality · monsters.role · recipes.kind · skills.kind ·
    #     gathering.kind / gathering.verb · drop_pools 的 kind 与条目 kind
    #   装备那半（items.kind → ASCII `slot`）与技能那半（skills.kind → ASCII `owner_class`
    #   + 域里那一份值）本批已收口；其余钉在 ENUM_KEYS 上，**只降不升**。
    _cjk = re.compile(r"[\u4e00-\u9fff]")
    _EF = ("kind", "role", "quality", "verb")
    _enum_words: dict = {}

    def _collect_enum(v, path):
        if isinstance(v, dict):
            for _k, _x in v.items():
                if isinstance(_x, str):
                    if _k in _EF and _cjk.search(_x):
                        _enum_words.setdefault(_x, set()).add("%s.%s" % (path, _k))
                elif isinstance(_x, (dict, list)):
                    _collect_enum(_x, "%s.%s" % (path, _k))
        elif isinstance(v, list):
            for _x in v:
                if isinstance(_x, dict):
                    _collect_enum(_x, path)

    for _d in ("items", "monsters", "recipes", "skills", "gathering", "drop_pools"):
        _collect_enum(st.domain(_d) or {}, _d)
    _ehits = {}
    for p in files:                       # 同一个扫描面 = content/*.py（与 ①②③ 一致）
        _hits, _ = scan(p)
        _bad = [(ln, w) for ln, w in _hits if w in _enum_words]
        if _bad:
            _ehits[p.name] = _bad
    _etotal = sum(len(v) for v in _ehits.values())
    print("  · 中文枚举当机器键（%d 个黑名单取值）：%s · 合 %d 处"
          % (len(_enum_words),
             " · ".join("%s %d" % (k, len(v)) for k, v in sorted(_ehits.items())) or "一处都没有",
             _etotal))
    # ★ B3-6b-2d-keys-2：**必须 0 处**（原先「≤ 快照 ENUM_KEYS」）—— 两刀把这几族全收口了：
    #   装备走 `slot` · 技能走 `owner_class` · 非装备 items.kind / recipes.kind / drop_pools 的池与
    #   未鉴定走 `kind_key` · monsters.role 走 `role_key`。再出现一处就是**回退**。
    chk("★ 代码里「拿中文枚举当机器键」**必须 0 处**（%d 个黑名单取值；装备走 `slot` · 技能走 "
        "`owner_class` · 其余走 `kind_key` / `role_key`）" % len(_enum_words),
        not _ehits, "有 %d 处：%s" % (_etotal, {k: v[:3] for k, v in sorted(_ehits.items())}))
    _done_bad = {}
    for _f, _v in _ehits.items():
        for _w in ENUM_DONE:
            if any(_x[1] == _w for _x in _v):
                _done_bad.setdefault(_w, []).append(_f)
    chk("★ 已收口的枚举取值不许再当机器键（%s；ASCII 替身 = slot / owner_class / kind_key / role_key）"
        % " / ".join(ENUM_DONE), not _done_bad, "%s" % _done_bad)

    # ⑯ ★ B3-6b-2d-keys-2：代码里比的 ASCII 机器键**都在域里真出现过**（与 ⑦ chain / ⑧ verb 同款）——
    #   机器键最怕「代码比 A、域里写 B」：一个字之差就静默不命中（promo 里那 7 处就是这么来的）。
    _rk = {v.get("role_key") for v in (st.domain("monsters") or {}).values()}
    _miss_rk = sorted({"normal", "elite", "chief", "warden", "boss"} - _rk)
    chk("★ 代码按 role_key 判档位：monsters 里真有 normal / elite / chief / warden / boss（%d 只怪）"
        % len(st.domain("monsters") or {}), not _miss_rk, "缺：%s" % _miss_rk)
    _ik = {v.get("kind_key") for v in (st.domain("items") or {}).values()}
    _miss_ik = sorted({"material", "junk", "clue", "food", "keepsake"} - _ik)
    chk("★ 代码按 kind_key 判图鉴归属：items 里真有 material / junk / clue / food / keepsake（%d 件）"
        % len(st.domain("items") or {}), not _miss_ik, "缺：%s" % _miss_ik)
    _dl = st.domain("drop_pools") or {}
    _pk = {v.get("kind_key") for v in _dl.values()} | {
        e.get("kind_key") for v in _dl.values()
        for e in (list(v.get("entries") or []) + list(v.get("pool") or [])) if isinstance(e, dict)}
    _miss_pk = sorted({"pool", "unidentified"} - _pk)
    chk("★ 代码按 kind_key 判嵌套池 / 未鉴定：drop_pools 里真有 pool / unidentified（%d 个池）"
        % len(_dl), not _miss_pk, "缺：%s" % _miss_pk)
    _ck = {v.get("kind_key") for v in (st.domain("recipes") or {}).values()}
    chk("★ 代码按 kind_key 判可下锅的菜：recipes 里真有 cook（%d 条配方）"
        % len([k for k in (st.domain("recipes") or {}) if not str(k).startswith("_")]),
        "cook" in _ck, "recipes 的 kind_key = %s" % sorted(x for x in _ck if x))

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

    # ⑤ ★ 数据里取件也算「被引用」：文案可以从**数据**来 —— 域里那一格写的就是槽位名
    #    （B3-5 起：事件的 4 条表征 + 场地那条挂在 `events.json` 的 `text` 上，代码只 `T(数据取到的键)`）。
    #    只扫**字符串值**（不是整份 JSON 文本）⇒ 注释里提一句不会算数。
    data_ref = set()
    _ddir = os.path.join(str(REPO), "content", "data")
    for _fn in sorted(os.listdir(_ddir)):
        if not _fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(_ddir, _fn), encoding="utf-8") as _f:
                _obj = json.load(_f)
        except Exception:                                             # noqa: BLE001 —— 坏文件由别处报
            continue
        _stack = [_obj]
        while _stack:
            _v = _stack.pop()
            if isinstance(_v, dict):
                _stack.extend(_v.values())
            elif isinstance(_v, list):
                _stack.extend(_v)
            elif isinstance(_v, str) and _v in tx:
                data_ref.add(_v)

    rows = RS.parse_doc()
    notx = [r["key"] for r in rows if r["key"] not in tx]
    diff = [r["key"] for r in rows if r["key"] in tx and tx[r["key"]]["value"] != r["value"]]
    def _by_tpl(k):
        return any(rx.match(k) for rx in _tpl_rx)
    unused = [r["key"] for r in rows
              if r["key"] not in ref and r["key"] not in ref_lit and r["key"] not in data_ref
              and not _by_tpl(r["key"])]
    chk("★ 口径表 %d 条都落在 texts 里" % len(rows), not notx, "%s" % notx[:6])
    chk("★ 口径表与 texts 逐字一致（防两处口径）", not diff, "%s" % diff[:6])
    chk("★ 口径表每条都被引用（代码 `T(\"…\")` / 代码字面量 / **模板拼出来** / **数据里取件**）"
        "（T() %d · 字面量 %d · 模板 %d · 数据 %d）"
        % (len(ref), len(ref_lit), len(_tpl_rx), len(data_ref)), not unused, "%s" % unused[:6])

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
    from content import cmds_tower as CTW                                 # noqa: E402
    from content import cmds_gear as CGR                                  # noqa: E402
    from content import cmds_skill as CSK                                 # noqa: E402
    from content import cmds_more as CMO                                  # noqa: E402
    from content import cmds_places as CPLA                                # noqa: E402
    from content import cmds_self as CSEL                                  # noqa: E402

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
    # ★ B3-6b-2d-b：挑一件武器做 fixture 走 ASCII `slot`（原先按 kind 的中文枚举挑）
    _wpn = sorted(k for k, v in _its.items() if v.get("slot") == "weapon")
    _wpn = (_wpn or [""])[0]
    # ★ B3-9（装备与技能那组）的 fixture：同格**另一把不同名**的武器（对比才有增有减）·
    #   一件非装备（「不是能穿的」那一支）· 骑士班最靠前的那条技能（学习 / 技能）
    _w2 = next((k for k in sorted(k for k, v in _its.items() if v.get("slot") == "weapon")
                if _its[k].get("name") != _its.get(_wpn, {}).get("name")), _wpn)
    _plain = next((k for k in sorted(_its) if not _its[k].get("slot")), "")
    # ★ B3-12 的 fixture（都从域里挑，不手写 id）：域里带价的（卖得掉）· 域里没写价的（拿在手上的）
    _pric = next((k for k in sorted(_its) if isinstance(_its[k].get("price"), (int, float))
                  and not isinstance(_its[k].get("price"), bool) and _its[k]["price"] > 0), "")
    _nopric = next((k for k in sorted(_its)
                    if not isinstance(_its[k].get("price"), (int, float))), "")
    _knt_sk = sorted((int(v.get("lv") or 1), k, v) for k, v in (st.domain("skills") or {}).items()
                     if v.get("owner_class") == "cls_knight")
    _knt_name = _knt_sk[0][2].get("name") if _knt_sk else ""
    _tid = next((k for k in sorted(st.domain("titles") or {}) if not str(k).startswith("_")), "")
    _eid = next((k for k in sorted(st.domain("eggs") or {}) if not str(k).startswith("_")), "")
    # ★ B3-5：今天那个游戏日（「异动」标「新开的 / 收了」要看维护门那一格是不是今天的）
    _ev_today = int(CA.CAL.state()["game_day"])
    # ★ B3-16b：镇上那几处的**那一站**从 npcs 域的职能键现读（heal / board）—— 不手写镜像
    _NP16C = st.domain("npcs") or {}
    _HEAL_NODE = next((str(v.get("subarea") or "") for v in _NP16C.values()
                       if isinstance(v, dict) and v.get("map") == "windmill_town"
                       and "heal" in (v.get("funcs") or [])), "wt_chapel")
    _GUILD_NODE = next((str(v.get("subarea") or "") for v in _NP16C.values()
                        if isinstance(v, dict) and v.get("map") == "windmill_town"
                        and "board" in (v.get("funcs") or [])), "wt_board")

    def _rich(**kw):
        """一口袋全物品 + 等级/族/职业都定过的档（背包 / 图鉴 / 配方 那几条要用）。"""
        over = {"bag": {k: 1 for k in _its}, "codex": {}, "gold": 999, "level": 10,
                "cls": "cls_knight", "race": "elf", "hp": 200, "hp_max": 200,
                "flags": {"quests_done": []}}
        over.update(kw)
        return _player(**over)
    cases = [
        ("观察", CA.look, "", {"loc": "windmill_town", "node": "wt_gate_n", "race": "human"}),
        ("地图", CA.map_view, "", {"loc": "windmill_town", "node": "wt_gate_n", "race": "human"}),
        ("聆听", CA.listen, "", {"loc": "windmill_town", "node": "wt_gate_n", "race": "human"}),
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
        ("去(没给地方)", CA.go_to, "去", {"loc": "windmill_town", "node": "wt_gate_n", "race": "human"}),
        ("去(走到)", CA.go_to, "去 %s" % town[3], {"loc": "windmill_town", "node": "wt_gate_n", "race": "human"}),
        ("去(不是邻居)", CA.go_to, "去 %s" % belt[-1], {"loc": "belt_north", "node": "bn_bone"}),
        ("去(没这地方)", CA.go_to, "去 高塔", {"loc": "windmill_town", "node": "wt_gate_n", "race": "human"}),
        ("北口", CA.go_north, "", {"loc": "windmill_town", "node": "wt_gate_n", "race": "human"}),
        ("往东", CA.go_east, "", {"loc": "windmill_town", "node": "wt_gate_n", "race": "human"}),
        ("往西", CA.go_west, "", {"loc": "windmill_town", "node": "wt_gate_n", "race": "human"}),
        ("进镇", CA.enter_town, "", {"loc": "belt_north", "node": "bn_bone"}),
        ("返回(有上一处)", CA.go_back, "", {"loc": "belt_east", "node": "be_birch",
                                          "prev": [["windmill_town", "wt_gate_n"]]}),
        ("返回(没上一处)", CA.go_back, "", {"loc": "windmill_town", "node": "wt_gate_n", "prev": []}),
        ("搭话(这儿有谁)", CT.talk, "搭话", {"loc": "windmill_town", "node": "wt_gate_n", "race": "human"}),
        ("搭话(没有这个人)", CT.talk, "搭话 不存在的人", {"loc": "windmill_town", "node": "wt_gate_n", "race": "human"}),
        ("搭话(这儿没人)", CT.talk, "搭话", {"loc": "belt_north", "node": "bn_bone"}),
        ("问路(镇上)", CT.ask_way, "", {"loc": "windmill_town", "node": "wt_gate_n", "race": "human"}),
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
        ("采集(这儿没有)", CG.gather, "", {"loc": "windmill_town", "node": "wt_gate_n", "race": "human"}),
        ("采集(今天翻过了)", CG.gather, "", {"loc": "windmill_town", "node": "wt_wall",
                                              "flags": {"gather_used": {"gt_wt_herb_1": 3}}}),
        ("挖掘(有)", CG.dig, "", {"loc": "belt_north", "node": "bn_bone"}),
        ("垂钓(有)", CG.fish, "", {"loc": "belt_west", "node": "bw_old_ferry"}),
        ("搜查(有)", CG.search, "", {"loc": "belt_east", "node": "be_birch"}),
        # ★ P-27：上限只有面板一个来源 ⇒ 这几条要**定过职业**（没职业的档上限「未定」，
        #   回血 / 用药 / 战斗那些要数字的地方当场 fail-closed —— 见 probe_panel 那一节）。
        ("歇脚(不累)", CG.rest, "", {"cls": "cls_knight", "hp": 999}),
        ("歇脚(歇下了)", CG.rest, "", {"cls": "cls_knight", "hp": 40}),
        # ★ P-27：还没择业的档 —— 要数字的地方（打架 / 歇脚）**不出假数**，出一行点名行
        ("歇脚(还没择业)", CG.rest, "", {"loc": "windmill_town", "node": "wt_gate_n"}),
        ("攻击(还没择业)", CBL.attack, "",
         {"loc": "belt_north", "node": "bn_bone", "bag": {}, "codex": {}, "flags": {}}),
        ("拾取", CG.pick_up, "", {}),
        # ★ B3-5：世界事件（异动）—— 三尺度那个呈现口
        ("异动(没刷新过)", CA.event_now, "", {"loc": "windmill_town", "node": "wt_gate_n", "race": "human"}),
        ("异动(刷新过·有收了的)", CA.event_now, "",
         {"loc": "windmill_town", "node": "wt_gate_n", "race": "human",
          "flags": {"ev": {"day": _ev_today, "on": [], "prev_day": _ev_today - 1,
                           "prev_on": ["ev_first_snow:w:g00000020:3"]}}}),
        # ★ B3-10 ①：去「脚下这一站」（原先错走 SYS_MOVE_FAR 那一支）
        ("去(就在这儿)", CA.go_to, "去 %s" % cur, {"loc": "windmill_town", "node": "wt_gate_n", "race": "human"}),
        # ★ B3-10 ②：K56 族的另一半 —— 这些呈现口原先没被逐行扫过
        ("时间", CA.time_now, "", {"loc": "windmill_town", "node": "wt_gate_n", "race": "human"}),
        ("背包(满)", CA.bag, "", _rich()),
        ("攻击(野外)", CBL.attack, "",
         {"loc": "belt_north", "node": "bn_bone", "cls": "cls_knight", "level": 3, "hp": 80,
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
        ("使用(药水)", CR.item_use, "使用 药水", {"cls": "cls_knight", "bag": {"i_potion_heal": 1}}),
        ("使用(伤药)", CR.item_use, "使用 伤药",
         {"cls": "cls_knight", "bag": {"i_potion_minor": 1}, "hp": 10}),
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
        # ★ B3-11：站在目的地上再敲那四条出口（原先会再演一遍出门 · 往历史里塞自己）
        ("北口(就在骨田)", CA.go_north, "", {"loc": "belt_north", "node": "bn_bone"}),
        ("往东(就在白桦林)", CA.go_east, "", {"loc": "belt_east", "node": "be_birch"}),
        ("往西(就在旧渡口)", CA.go_west, "", {"loc": "belt_west", "node": "bw_old_ferry"}),
        ("进镇(就在镇口)", CA.enter_town, "", {"loc": "windmill_town", "node": "wt_gate_n", "race": "human"}),
        # ★ B3-6：副本（旧哨塔）五条 —— 塔内 / 塔外 / 空档三档都扫一遍（K56 覆盖面）
        ("进塔(在塔门口)", CTW.tower_enter, "", {"loc": "belt_north", "node": "bn_tower"}),
        ("进塔(不在塔门口)", CTW.tower_enter, "", {"loc": "belt_north", "node": "bn_bone"}),
        ("进塔(已经在塔里)", CTW.tower_enter, "", {"loc": "old_watchtower", "node": "tower_gate"}),
        ("下一层(没走到尽头)", CTW.tower_next, "", {"loc": "old_watchtower", "node": "tower_hall"}),
        ("下一层(站到尽头)", CTW.tower_next, "", {"loc": "old_watchtower", "node": "tower_stair1"}),
        ("下一层(塔顶)", CTW.tower_next, "", {"loc": "old_watchtower", "node": "tower_top"}),
        ("副本地图(塔里)", CTW.tower_map, "", {"loc": "old_watchtower", "node": "tower_water_room"}),
        ("调查(有可读物)", CTW.tower_investigate, "",
         {"loc": "old_watchtower", "node": "tower_water_room"}),
        ("调查(没有可读物)", CTW.tower_investigate, "",
         {"loc": "old_watchtower", "node": "tower_hall"}),
        ("撤退(塔里)", CTW.tower_leave, "", {"loc": "old_watchtower", "node": "tower_top"}),
        ("撤退(塔外)", CTW.tower_leave, "", {"loc": "belt_north", "node": "bn_bone"}),
        ("副本地图(塔外)", CTW.tower_map, "", {"loc": "belt_north", "node": "bn_bone"}),
        # ★ B3-9（装备与技能那组）：新接的 5 条 —— 每一支都真跑一遍（含「认不出 / 不是能穿的 /
        #   身上没有 / 位子空着 / 还不是本职业 / 还没择业」这些支路），逐行扫机器键与缺文案
        ("装备(穿上一件)", CGR.equip, "装备 %s" % _its.get(_wpn, {}).get("name", ""),
         {"cls": "cls_knight", "bag": {_wpn: 1}}),
        ("装备(同一位子换下)", CGR.equip, "装备 %s" % _its.get(_w2, {}).get("name", ""),
         {"cls": "cls_knight", "bag": {_w2: 1}, "equipped": {"weapon": _wpn}}),
        ("装备(已经穿在身上)", CGR.equip, "装备 %s" % _its.get(_wpn, {}).get("name", ""),
         {"cls": "cls_knight", "equipped": {"weapon": _wpn}}),
        ("装备(不是能穿的)", CGR.equip, "装备 %s" % _its.get(_plain, {}).get("name", ""),
         {"bag": {_plain: 1}}),
        ("装备(背包里没有)", CGR.equip, "装备 不存在的东西", {"cls": "cls_knight"}),
        ("卸下(身上那件)", CGR.unequip, "卸下 %s" % _its.get(_wpn, {}).get("name", ""),
         {"cls": "cls_knight", "equipped": {"weapon": _wpn}}),
        ("卸下(没点名·列身上)", CGR.unequip, "卸下",
         {"cls": "cls_knight", "equipped": {"weapon": _wpn}}),
        ("卸下(空身)", CGR.unequip, "卸下", {"cls": "cls_knight"}),
        ("卸下(身上没这件)", CGR.unequip, "卸下 不存在的甲",
         {"cls": "cls_knight", "equipped": {"weapon": _wpn}}),
        ("对比(换不换)", CGR.item_compare, "对比 %s" % _its.get(_w2, {}).get("name", ""),
         {"cls": "cls_knight", "bag": {_w2: 1}, "equipped": {"weapon": _wpn}}),
        ("对比(位子空着)", CGR.item_compare, "对比 %s" % _its.get(_w2, {}).get("name", ""),
         {"cls": "cls_knight", "bag": {_w2: 1}}),
        ("对比(背包里没有)", CGR.item_compare, "对比 不存在的东西", {}),
        ("技能(骑士)", CSK.skills, "", {"cls": "cls_knight", "level": 1}),
        ("技能(还没择业)", CSK.skills, "", {}),
        ("学习(本职业·已在册)", CSK.skill_learn, "学习 %s" % _knt_name,
         {"cls": "cls_knight", "level": 1}),
        ("学习(学一条新的·落档)", CSK.skill_learn, "学习 %s" % _knt_name,
         {"cls": "cls_knight", "level": 1, "skills": ["SKILL_KNT_slash"]}),
        ("学习(不是本职业)", CSK.skill_learn, "学习 冰棱", {"cls": "cls_knight", "level": 1}),
        ("学习(没这条)", CSK.skill_learn, "学习 没有这条技能", {"cls": "cls_knight"}),
        ("学习(还没择业)", CSK.skill_learn, "学习 横剑", {}),
        # ★ B3-12（这一批新接的 8 条）：每一支都真跑一遍 —— ⑥ 的「不缺文案 / 不漏机器键」
        #   与 ⑬ 的「默认档不被就地改」从此**自动**罩到它们身上
        ("看(单子)", CMO.board_show, "看 1", {"level": 3}),
        ("看(支线编号)", CMO.board_show, "看 13", {"level": 3}),
        ("看(已接)", CMO.board_show, "看 1", {"level": 3, "flags": {"quests_active": ["q_main_01"]}}),
        ("看(没有这张)", CMO.board_show, "看 999", {"level": 3}),
        ("属性(还没择业)", CMO.attrs, "", {}),
        ("属性(骑士)", CMO.attrs, "", {"cls": "cls_knight", "level": 3, "race": "elf"}),
        ("属性(加过点)", CMO.attrs, "", {"cls": "cls_knight", "level": 10, "race": "elf",
                                        "alloc": {"STR": 18, "VIT": 13}}),
        ("查看(背包里的武器)", CMO.item_show, "查看 %s" % _its.get(_wpn, {}).get("name", ""),
         {"bag": {_wpn: 1}}),
        ("查看(带价的成品)", CMO.item_show, "查看 %s" % _its.get(_pric, {}).get("name", ""),
         {"bag": {_pric: 2}} if _pric else {}),
        ("查看(没有这件)", CMO.item_show, "查看 不存在的东西", {}),
        ("丢弃(丢一件)", CMO.item_drop, "丢弃 %s" % _its.get(_wpn, {}).get("name", ""),
         {"bag": {_wpn: 2}}),
        ("丢弃(超过手里的)", CMO.item_drop, "丢弃 %s 9" % _its.get(_wpn, {}).get("name", ""),
         {"bag": {_wpn: 2}}),
        ("丢弃(没有这件)", CMO.item_drop, "丢弃 不存在的东西", {}),
        ("卖出(有价的)", CMO.item_sell, "卖出 %s" % (_its.get(_pric, {}).get("name", "") or "药水"),
         {"loc": "windmill_town", "bag": {_pric: 2}} if _pric else {}),
        ("卖出(域里没价)", CMO.item_sell, "卖出 %s" % _its.get(_nopric, {}).get("name", ""),
         {"loc": "windmill_town", "bag": {_nopric: 1}}),
        ("卖出(人在野外)", CMO.item_sell, "卖出 %s" % (_its.get(_pric, {}).get("name", "") or "药水"),
         {"loc": "belt_north", "node": "bn_bone", "bag": {_pric: 1}} if _pric else {}),
        ("整理背包(空)", CMO.bag_sort, "", {"bag": {}}),
        ("整理背包(满)", CMO.bag_sort, "", _rich()),
        ("存放(不在客栈)", CMO.stash, "存放 %s" % _its.get(_wpn, {}).get("name", ""),
         {"loc": "belt_north", "node": "bn_bone", "bag": {_wpn: 1}}),
        ("存放(在客栈)", CMO.stash, "存放 %s" % _its.get(_wpn, {}).get("name", ""),
         {"loc": "windmill_town", "node": "wt_inn", "bag": {_wpn: 2}}),
        ("取出(箱里有的)", CMO.stash, "取出 %s" % _its.get(_wpn, {}).get("name", ""),
         {"loc": "windmill_town", "node": "wt_inn", "bag": {},
          "flags": {"stash": {_wpn: 1}}}),
        ("取出(空箱)", CMO.stash, "取出 不存在的", {"loc": "windmill_town", "node": "wt_inn"}),
        ("成就(空档)", CMO.achievements, "", {}),
        ("成就(有账)", CMO.achievements, "", _rich()),
        # ★ B3-16b（这一批新接的 9 条里能按四参帧直调的那 8 条）：每一支都真跑一遍 ——
        #   ⑥ 的「不缺文案 / 不漏机器键」与 ⑬ 的「默认档不被就地改」从此**自动**罩到它们身上
        #   （`排行` 那一条是五参帧，单独在下面跑）
        ("教堂(野外)", CPLA.chapel, "", {"loc": "belt_north", "node": "bn_bone"}),
        ("教堂(镇上没走到那一站)", CPLA.chapel, "", {"loc": "windmill_town", "node": "wt_gate_n"}),
        ("教堂(站到了·治疗)", CPLA.chapel, "",
         {"loc": "windmill_town", "node": _HEAL_NODE, "cls": "cls_knight", "hp": 10}),
        ("教堂(档上还没择业)", CPLA.chapel, "", {"loc": "windmill_town", "node": _HEAL_NODE}),
        ("客栈(不在客栈)", CPLA.inn, "", {"loc": "windmill_town", "node": "wt_gate_n"}),
        ("客栈(住店)", CPLA.inn, "",
         {"loc": "windmill_town", "node": CMO.STASH_NODE, "cls": "cls_knight", "hp": 10}),
        ("商队(车还在路上)", CPLA.caravan, "",
         {"loc": "windmill_town", "node": "wt_gate_n", "flags": {}}),
        ("商队(车到了)", CPLA.caravan, "",
         {"loc": "windmill_town", "node": "wt_gate_n", "flags": {"quests_done": ["q_main_03"]}}),
        ("旧货(包里有东西)", CPLA.junk_shop, "",
         {"loc": "windmill_town", "node": "wt_inn", "bag": {"i_junk_bone": 2}}),
        ("旧货(包里空的)", CPLA.junk_shop, "",
         {"loc": "windmill_town", "node": "wt_inn", "bag": {}}),
        ("登记(野外)", CSEL.register, "", {"loc": "belt_north", "node": "bn_bone"}),
        ("登记(档上还没名字)", CSEL.register, "", {"loc": "windmill_town", "node": _GUILD_NODE}),
        ("登记(办下来)", CSEL.register, "",
         {"loc": "windmill_town", "node": _GUILD_NODE, "name": "考据的人", "flags": {}}),
        ("登记(已经有证)", CSEL.register, "",
         {"loc": "windmill_town", "node": _GUILD_NODE, "name": "考据的人", "flags": {"card": 1}}),
        ("评级(还没登记)", CSEL.rank, "", {"flags": {}}),
        ("评级(有证)", CSEL.rank, "",
         {"flags": {"card": 1, "quests_done": ["q_main_01"]}}),
        ("改名(没带名字)", CSEL.rename, "改名", {"flags": {}}),
        ("改名(改好了)", CSEL.rename, "改名 考据的人", {"flags": {}}),
        ("改名(改过了)", CSEL.rename, "改名 别人", {"flags": {"renamed": 1}}),
        ("公告", CSEL.notice, "", {}),
    ]
    bad, empty, sample = [], [], []
    leaked = []
    _KEYS = [k for d in ("items", "monsters", "pois", "classes", "races", "quests",
                         "gathering", "drop_pools", "recipes", "npcs", "skills", "eggs",
                         "titles", "dialogues")
             for k in (st.domain(d) or {})]
    # ★ B3-12：跑之前先给默认档那四个容器拍快照（跑完必须一模一样）
    _MUT = ("bag", "equipped", "flags", "codex")
    _DEF_SNAP = {_k: copy.deepcopy(CA.DEFAULT_PLAYER.get(_k)) for _k in _MUT}
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

    # ★ B3-16b：`排行` 是**五参帧**（声明 args = group_id / uid / player）—— 单独真跑一遍，
    #   同样过「不缺文案 / 不漏机器键」两条（连档上还没名字那一档一起）
    def _drive5(fn, p, text="", group_id="g_copy", uid="u_copy"):
        out = []

        async def go():
            async for _ln in fn(_E(text), None, group_id, uid, p):
                out.append(str(_ln))

        asyncio.run(go())
        return out

    _rank_bad = []
    for _labR, _pR in (("排行(有名字·库里没有别人)", _player(name="考据的人", level=7, exp=5)),
                       ("排行(还没名字)", _player(level=2))):
        _outR = _drive5(CSEL.ranking, _pR, "")
        if not _outR or any(MISSING in _ln for _ln in _outR) \
                or any(k in _ln for _ln in _outR for k in _KEYS):
            _rank_bad.append((_labR, _outR[:3]))
    chk("★ `排行` 真跑两档（有名字 / 档上还没名字）：出榜头与尾注 · 不漏机器键 · 不缺文案",
        not _rank_bad, "%s" % _rank_bad[:2])

    # ⑬ B3-12 ★ 默认档不许被就地改（K57 的活口）：跑完这么多实现体，那四个容器必须没动
    _soiled = [(_k, _DEF_SNAP[_k], CA.DEFAULT_PLAYER.get(_k)) for _k in _MUT
               if CA.DEFAULT_PLAYER.get(_k) != _DEF_SNAP[_k]]
    chk("★ 默认档不许被就地改（跑完 %d 个实现体后 bag / equipped / flags / codex 原样）" % len(cases),
        not _soiled, "%s" % _soiled[:2])

    # ⑬-b 半截老档（缺 bag / flags / codex）采集一趟 —— 不许写进默认档，也不许串给下一个人
    _pA = {"loc": "windmill_town", "node": "wt_wall", "hp": 100, "hp_max": 100}
    _drive(CG.gather, _pA, "")
    _pB = {"loc": "windmill_town", "node": "wt_gate_n", "hp": 100, "hp_max": 100}
    _bagB = _drive(CA.bag, _pB, "")
    chk("★ 半截老档采集：默认档没被写 · 下一个人的背包还是空的",
        CA.DEFAULT_PLAYER.get("bag") == _DEF_SNAP["bag"]
        and CA.DEFAULT_PLAYER.get("codex") == _DEF_SNAP["codex"]
        and _pB.get("bag") in ({}, None)
        and any("空的" in ln for ln in _bagB),
        "默认=%s 下一个人的包=%s %s" % (CA.DEFAULT_PLAYER.get("bag"), _pB.get("bag"), _bagB[:1]))

    # ⑭ ★ P-27：上限只有一个来源（职业面板）—— 还没择业的档照实说「未定」，
    #   不许再出那两个写死的 100（面板 116 的骑士原先显示 100/100）。
    _noCls = _drive(CA.status, _player(loc="windmill_town", node="wt_gate_n", race="human",
                                       hp=100, hp_max=100))   # 老档那两格写死的 100 还在
    chk("★ P-27 还没择业的档 `状态`：生命上限出「未定」（不拿写死的 100 垫）",
        any(("生命" in ln and "未定" in ln) for ln in _noCls) and "100/100" not in "\n".join(_noCls),
        "%s" % _noCls[:2])
    _noClsAtk = _drive(CBL.attack, _player(loc="belt_north", node="bn_bone", bag={}, flags={}),
                       "")
    chk("★ P-27 还没择业的档 `攻击`：不开那一场、出一行点名行（职业基础 · 不猜数）",
        bool(_noClsAtk) and any("职业基础" in ln for ln in _noClsAtk)
        and not any("遭遇" in ln for ln in _noClsAtk), "%s" % _noClsAtk[:2])
    # ★ P-27：POI 回血那一支（神龛 · `effect.buff` 只写了名字 ⇒ 走「上限的 20%」安全默认）
    _shr = next((k for k, v in (st.domain("pois") or {}).items()
                 if isinstance(v.get("effect"), dict) and v["effect"].get("buff")), "")
    if _shr:
        _pv = (st.domain("pois") or {})[_shr]
        _shCls = _drive(CA.touch, _player(cls="cls_knight", loc=_pv.get("map"), node=_pv.get("subarea")))
        _shNo = _drive(CA.touch, _player(loc=_pv.get("map"), node=_pv.get("subarea")))
        chk("★ P-27 POI 回血走同一个口（%s）：有职业 ⇒ 真回血 · 没职业 ⇒ 点名行不回血" % _shr,
            any("生命 +" in ln for ln in _shCls) and any("职业基础" in ln for ln in _shNo)
            and not any("生命 +" in ln for ln in _shNo),
            "%s / %s" % (_shCls[-1:], _shNo[-1:]))

    # ⑩ B3-10 ①：`去 <脚下这一站>` —— 回的是「到了」，不是「过不去」
    here_out = _drive(CA.go_to, _player(loc="windmill_town", node="wt_gate_n"), "去 %s" % cur)
    here_want = tx["SYS_MOVE_HERE"]["value"].replace("{name}", cur)
    far_txt = tx["SYS_MOVE_FAR"]["value"].replace("{name}", cur)
    chk("★ 去(脚下这一站 %s)：出 HERE 那一句、不出 FAR" % cur,
        bool(here_out) and here_out[0] == here_want and far_txt not in chr(10).join(here_out),
        "%s" % (here_out[:2] if here_out else ["(空)"]))

    # ⑫ B3-11 ★ 四条出口的「脚下这一站」（K60 家族）：站在目的地再敲一次 —— 不许演「又走了一趟」
    _EXITS = [("北口", "belt_north", "bn_bone", "SYS_MOVE_OUT_NORTH", CA.go_north),
              ("往东", "belt_east", "be_birch", "SYS_MOVE_OUT_EAST", CA.go_east),
              ("往西", "belt_west", "bw_old_ferry", "SYS_MOVE_OUT_WEST", CA.go_west),
              ("进镇", "windmill_town", "wt_gate_n", None, CA.enter_town)]
    exit_bad = []
    for label, loc, node, out_slot, fn in _EXITS:
        pp = _player(loc=loc, node=node, prev=[])
        out = _drive(fn, pp, "")
        want_here = tx["SYS_MOVE_HERE"]["value"].replace("{name}", CA._name_of_node(loc, node))
        why = []
        if not out or out[0] != want_here:
            why.append("首行不是 HERE：%s" % (out[:1] or ["(空)"]))
        if out_slot and tx[out_slot]["value"] in chr(10).join(out):
            why.append("还在演出门那一屏")
        if (pp.get("loc"), pp.get("node")) != (loc, node):
            why.append("位置被挪动了 %s" % ((pp.get("loc"), pp.get("node")),))
        if pp.get("prev"):
            why.append("往历史里塞了自己 %s" % (pp.get("prev"),))
        back = _drive(CA.go_back, pp, "")
        if not back or back[0] != tx["SYS_MOVE_BACK_NONE"]["value"]:
            why.append("紧接着的『返回』不是「没什么可回」：%s" % (back[:1] or ["(空)"]))
        if why:
            exit_bad.append((label, why))
    chk("★ 站在目的地敲『北口 / 往东 / 往西 / 进镇』：回 HERE · 不演出门 · 不塞历史（4 条）",
        not exit_bad, "%s" % exit_bad[:2])


    print("  · 打样：%s" % " ｜ ".join(sample))

    print("")
    print("探针：%s" % ("全绿 ✓" if ok else "有红 ✗"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
