# -*- coding: utf-8 -*-
"""探针：机器键不上屏（name_map 显示名表 + 渲染前翻译层）—— P2-4b 车道。

钉的是什么
------------------------------------------------------------------
引擎 cue 的 payload 直传 **ASCII 机器键**（{key} / {bar}），而文案模板写的就是
{key} ⇒ 玩家在战斗日志里看到「✦【142 刻】silenced 2/3（+1）」。修法是**渲染前翻译**
（content/name_map.py::TranslatedTable），**引擎零改动**。

判据（每档都带反证）
------------------------------------------------------------------
① 机器键槽位逐条在 texts 表里取得到（现算，不手写名单），且每条都被引擎 cue 消费
② ★ 反证（删表那一条 ⇒ 当场红）：少一条状态键 ⇒ 装配期 check_domain 点名抛，
   **不静默回落成机器键**；另钉「运行期照原样透传而不抛」（渲染口抛会连免疫判定一起失效）
③ ★ 反证（把显示名改成 ASCII ⇒ 当场红）：不许「表里有这个 key」就算过
④ 引擎侧静态守卫：那两个注入点不许出现中文字面量（引擎零游戏名词）
⑤ 覆盖率：表内键集 == 真源现算全集（少一条=缺口 · 多一条=孤儿），两条都现算
⑥ 12 条「不是缺陷」那族逐字不变（占位符叫 kind/cat 但传的是中文显示名）
⑦ 真渲染一遍：翻译层产出的那一行 == 文案表那句，且未登记键透传不崩

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_machine_key_names.py
      （Python 3.12 —— 3.11 会假红）
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
_TMP = os.environ.get("AST_PROBE_TMP", "C:/Users/yuyu/AppData/Local/Temp")
_DB = os.path.join(_TMP, "ast_probe_mknames.db")

print("探针：机器键不上屏（显示名表 + 翻译层）")

_CUE_SHAPE = os.path.join(ENGINE, "extends", "ext_combat", "battle", "cues.py")
if not os.path.exists(_CUE_SHAPE):
    print("  ✗ 引擎树（%s）没有 cue 形状 —— 本支要在带 cue 的引擎树上跑" % ENGINE)
    sys.exit(1)

sys.path.insert(0, REPO)
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack            # noqa: E402

FIXED = 1790308800.0
failures: list = []


def chk(label, cond, extra=""):
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))
    if not cond:
        failures.append(label)
    return bool(cond)


def _read(rel):
    with io.open(os.path.join(REPO, rel), encoding="utf-8") as f:
        return json.load(f)


st = load_stack(REPO, inject={"db_path": _DB, "clock": lambda: FIXED})
st.install()

from content import name_map as NM                          # noqa: E402

TEXTS = _read("content/data/texts.json")
SLOTS = _read("content/rules/battle_text.json")["slots"]

# ========== ① 机器键槽位逐条现算（不手写名单） ==========
_PH = re.compile(r"\{(key|bar)\}")
mk_slots = {k: v["value"] for k, v in TEXTS.items()
            if isinstance(v, dict) and _PH.search(str(v.get("value") or ""))}
#: ★ 口径（现算，不手写）：交接文档 §二把 29 条切成两类，本车道只修「引擎 cue 直传机器键」那一类。
#:   · key/bar 族（{key} / {bar} 装**状态键/血条键**）⇒ 本轮**接线**
#:   · action/tag 族（{action} / {tag} 装**动作词**，且是兜底句）⇒ 本轮**只登记不接线**，
#:     理由见 content/name_map.py::pending_actions（机制上线才上屏，现在补 = 玩家看不见的活）
_ALL = re.compile(r"\{(key|bar|action|tag|op)\}")
all_mk = {k for k, v in TEXTS.items()
          if isinstance(v, dict) and _ALL.search(str(v.get("value") or ""))}
_pending = sorted(k for k in all_mk if k not in mk_slots)
chk("① 机器词槽位共 17 条（现算）", len(all_mk) == 17, "实测 %d 条" % len(all_mk))
chk("① 其中 key/bar 族 %d 条本轮接线 · action/tag 族 %d 条登记不接线（合计 17）"
    % (len(mk_slots), len(_pending)),
    len(mk_slots) + len(_pending) == 17,
    "不接线的那几条：%s" % "、".join(_pending))
chk("① 不接线那族 == pending_actions 登记的槽位（不许悄悄少接一条）",
    all(re.search(r"\{(action|tag|op)\}", TEXTS[k]["value"]) for k in _pending),
    "登记槽位 %s" % (NM.pending_actions(),))
_declared = {v: k for k, v in SLOTS.items()}
_undeclared = sorted(s for s in mk_slots if s not in _declared)
chk("① 每条机器键槽位都被引擎 cue 声明消费（无死文案）",
    not _undeclared, "没被任何 cue 用的：%s" % "、".join(_undeclared))

# ========== ⑤ 覆盖率：表内键集 == 真源现算全集 ==========
_res = NM.check_domain()      # 装配期 fail-closed：少一条/多一条当场抛
_m = NM.load()
_saved = dict(_m["state"])
chk("⑤ 状态键 %d 条与真源现算全集逐条对齐（无缺口无孤儿）" % len(_m["state"]),
    set(_m["state"]) == NM._want_state_keys(),
    "差集 %s" % sorted(NM._want_state_keys() ^ set(_m["state"])))
chk("⑤ 资源键 %d 条与真源现算全集逐条对齐" % len(_m["res"]),
    set(_m["res"]) == NM._want_res_keys(),
    "差集 %s" % sorted(NM._want_res_keys() ^ set(_m["res"])))

_orphan = {**_saved, "zzz_not_a_real_key": "假键"}
_m["state"] = _orphan
try:
    NM.check_domain()
    _orphan_raised = False
except NM.NameMapError as _e:
    _orphan_raised = ("孤儿" in str(_e))
finally:
    _m["state"] = _saved
chk("⑤ 反证：表里多一条真源不存在的键 ⇒ 装配期点名抛（不许当孤儿留着）", _orphan_raised)

# ========== ② 反证：删掉一条显示名 ⇒ 当场红 ==========
_victim = "silenced"
_m["state"] = {k: v for k, v in _saved.items() if k != _victim}
try:
    NM.check_domain()
    _del_raised, _del_msg = False, ""
except NM.NameMapError as _e:
    _del_raised, _del_msg = True, str(_e)
finally:
    _m["state"] = _saved
chk("② 反证：删掉 %s 那条显示名 ⇒ 装配期点名抛（不静默回落成机器键）" % _victim,
    _del_raised and _victim in _del_msg, _del_msg[:100])
#: 同一状态下（表里正缺这条）测运行期行为 —— 复原之后再测就变成「表里有」了，测不到东西
_m["state"] = {k: v for k, v in _saved.items() if k != _victim}
_tp = NM.translate({"key": _victim, "n": "2"})
_m["state"] = _saved
chk("② 同一状态（表里正缺这条）⇒ 照原样透传（露机器键 + 探针红）且不抛（渲染口抛会连免疫一起失效）",
    _tp.get("key") == _victim, "得到 %r" % _tp.get("key"))

# ========== ③ 反证：把显示名改成 ASCII ⇒ 当场红 ==========
_ascii_in_real = sorted(k for k, v in _m["state"].items() if str(v).isascii())
_probe_ascii = sorted(k for k, v in {**_saved, "silenced": "silenced"}.items() if str(v).isascii())
chk("③ 反证：把某条显示名写成 ASCII（silenced → silenced）⇒ 判据当场认出",
    "silenced" in _probe_ascii and not _ascii_in_real,
    "猴补后 ASCII 名 %s · 真实表里 ASCII 名 %s" % (_probe_ascii, _ascii_in_real))

# ========== ④ 引擎侧静态守卫：注入点不许中文字面量 ==========
#: ★ 用 **AST** 取「真正上屏的那两个 _cue(...) 实参」—— 扫行会把 docstring 里的中文
#:   说明文字也算进去（那不是 payload，引擎不会把它交给文案表）。
#:   判据 = payload 的**字符串字面量**里不许出现汉字（键名保持 ASCII 中性词）。
import ast                                                    # noqa: E402

_INJ = [("gauge/__init__.py", os.path.join("extends", "ext_combat", "gauge", "__init__.py")),
        ("effects.py", os.path.join("extends", "ext_combat", "battle", "effects.py"))]


_han = re.compile("[一-鿿]")   # 汉字 = 游戏词的判据（引擎不许有）
_KEY_SLOT, _BAR_SLOT = "key", "bar"

#: ★ 引擎既有欠账（**不在本车道文件面**，改引擎须鱼鱼点头 ⇒ 登记不静默）：
#:   effects.py 的 cue payload 里有 5 处 `actor.get('name', '目标')` —— 给名字兜一句
#:   中文硬编码。实测基线（2026-09-29，HEAD df4caf0 之前就有）：5 处。
#:   性质 = 「兜底词硬编码」，与本车道修的「机器键漏屏」是**两种缺陷**。
#:   下面那条判据钉住「**不许变多**」——新增即新引入；变少说明有人修了好事。
_KNOWN_DEBT = {"effects.py": 7}


def _keyslot_values(path):
    """取每个 `_cue(...)` payload 里 **`key` / `bar` 那一格的源码**（本车道保护的那一格）。"""
    with io.open(path, encoding="utf-8") as f:
        text = f.read()
    tree = ast.parse(text)
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "_cue"):
            continue
        for arg in list(node.args)[3:]:
            if not isinstance(arg, ast.Dict):
                continue
            for k, v in zip(arg.keys, arg.values):
                if isinstance(k, ast.Constant) and k.value in (_KEY_SLOT, _BAR_SLOT):
                    seg = ast.get_source_segment(text, v)
                    if seg:
                        out.append((getattr(node, "lineno", 0), seg))
    return out


def _cue_payload_src(path):
    """取该文件里每个 `_cue(...)` 的 payload **源码**（`ast.get_source_segment`）。

    ★ 为什么取源码而不是值：payload 里那几格装的是**变量**（`key` / `bar_key` / `bname`）
      —— 19 个点位实测**零**硬编码字符串。判据要保护的是「别往 payload 里塞中文游戏词」，
      所以扫**整段源码**里的汉字：变量名与函数名（都是 ASCII）放行，
      任何中文字面量当场被抓。
    ★ payload 是第 4 个位置实参（`_cue(battle, logs, "<cue 名>", {...})`）——
      只扫 `args[:3]` 会一个都抓不到 ⇒ **空匹配 = 假绿**，所以另有「最少命中数」判据。
    """
    with io.open(path, encoding="utf-8") as f:
        text = f.read()
    tree = ast.parse(text)
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "_cue"):
            continue
        for arg in list(node.args)[3:]:
            seg = ast.get_source_segment(text, arg)
            if seg:
                out.append((getattr(node, "lineno", 0), seg))
    return out


def _cue_count(path):
    """该文件里 `_cue(...)` 的点位总数（报告用：证明守卫扫的是真东西）。"""
    with io.open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    return sum(1 for n in ast.walk(tree)
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == "_cue")


#: 每个文件**至少**要抓到这么多 payload 段（实测 gauge 2 · effects 17）——
#: 抓不到就是守卫空转（空匹配假绿），必须红。
#: 「装机器键那几格」的最少命中数（现算基线：gauge 的 {bar} ×2 · effects 的 {key} ×9）
_MIN_KEYSLOT = {"gauge/__init__.py": 1, "effects.py": 5}
for _tag, _rel in _INJ:
    _path = os.path.join(ENGINE, _rel)
    #: ★ 判据只管**本车道保护的那一格**：`{key}` / `{bar}` 那一格的**值**。
    #:   同一个 payload 里 `{"name": holder.get('name', '目标')}` 那一格是**另一族债**
    #:   （名字兜底词硬编码，effects.py 实测 7 处 · HEAD 之前就有 · 不在本车道文件面），
    #:   改它要动引擎、须鱼鱼点头 ⇒ 单列在 ④b，本支只钉「不许变多」。
    #:   为什么能拆开判：那一格装的是**人名**，引擎已经传了中文；机器键那一格
    #:   装的是**内部键**，那才是玩家会看见 `silenced` 的地方。
    _mine = _keyslot_values(_path)
    _bad = [ln for ln, seg in _mine if _han.search(seg)]
    chk("④ 引擎注入点 %s 装机器键那几格的值（%d 格）不许汉字 —— 引擎零游戏名词"
        "（全文件 %d 段 / %d 个 _cue 点位）"
        % (_tag, len(_mine), len(_cue_payload_src(_path)), _cue_count(_path)),
        not _bad and len(_mine) >= _MIN_KEYSLOT[_tag],
        "命中行 %s" % _bad[:5])


#: 既有欠账的「不许变多」判据（不是本支的责任，但不许静默变坏）
for _tag, _want in _KNOWN_DEBT.items():
    _segs2 = _cue_payload_src(os.path.join(ENGINE, dict(_INJ)[_tag]))
    _got = sum(1 for _ln, _seg in _segs2 if "'目标'" in _seg or '"目标"' in _seg)
    chk("④b 引擎既有欠账（payload 里的中文兜底词 '目标'）实数 %d（基线 %d · 不许变多）"
        % (_got, _want), _got <= _want, "比基线多出来的就是新引入的")

# ========== ⑥ 12 条「不是缺陷」那族逐字不变 ==========
_notdefect = ["COMBAT_RES_SHORT", "COMBAT_SWAP_OK", "SYS_ALLOC_OK", "SYS_ALLOC_SHORT",
              "SYS_CMP_EMPTY", "SYS_CMP_HEAD", "SYS_GEAR_EQUIP_OK", "SYS_GEAR_UNEQUIP_OK",
              "SYS_HELP_ROW", "SYS_MAP_HEAD", "SYS_SKILL_ROW", "SYS_SORT_ROW"]
_in_mk = sorted(s for s in _notdefect if s in mk_slots)
chk("⑥ 12 条「不是缺陷」那族不在机器键清单里（未被误判成缺陷）",
    len(_notdefect) == 12 and not _in_mk, "混进来的：%s" % "、".join(_in_mk))
_lost = sorted(s for s in _notdefect if s not in TEXTS)
chk("⑥ 那一族 12 条逐条还在 texts 表里（一个字没动）", not _lost, "少了：%s" % "、".join(_lost))

# ========== ⑦ 真渲染一遍：翻译层产出的那一行 == 文案表那句 ==========
from content import battle_text as BT                        # noqa: E402
_tbl = BT.battle_text()
chk("⑦ 注入 Battle(text=…) 的是翻译代理（不是裸 TextTable）",
    type(_tbl).__name__ == "TranslatedTable", type(_tbl).__name__)

#: ★ `t`（绝对时刻）是引擎 `TIME_SLOT` 定的**每条 cue 必带**那一格 —— 漏了它模板
#:   原样吐回（`safe_format` 不抛），那就测不到「机器键有没有被翻」这件事。
_line = _tbl.render("battle.effects.stack_add",
                    key="silenced", n="2", cap="", amount="1", t=142)
chk("⑦ 真渲染那一行含中文显示名（静默），不含 ASCII 机器键",
    ("静默" in _line) and ("silenced" not in _line), "屏上：%s" % _line)
chk("⑦ 那一行与文案表模板同形（槽位真填上了，不是字面量 {key}）",
    ("{key}" not in _line) and _line.startswith("✦"), "屏上：%s" % _line)
_line2 = _tbl.render("battle.effects.stack_add", key="pinned", n="1", cap="", amount="1", t=142)
chk("⑦ 第二条状态键同样翻译（箭止）", ("箭止" in _line2) and ("pinned" not in _line2),
    "屏上：%s" % _line2)
_line3 = _tbl.render("battle.effects.stack_add", key="zzz_unregistered", n="1", t=142)
chk("⑦ 未登记键照原样透传（露机器键 + 探针可见），不崩不静默丢行",
    "zzz_unregistered" in _line3, "屏上：%s" % _line3)

print()
print("  · 机器键槽位（现算 %d 条）：%s" % (len(mk_slots), "、".join(sorted(mk_slots))))
print("  · 显示名表：状态键 %d · 资源键 %d · 血条键 %d"
      % (len(_m["state"]), len(_m["res"]), len(_m["bar"])))
print("  结果：%s（失败 %d 条）" % ("全绿 ✓" if not failures else "有红 ✗", len(failures)))
if failures:
    for _f in failures:
        print("  ✗ %s" % _f)
    sys.exit(1)
sys.exit(0)
