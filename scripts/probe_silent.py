# -*- coding: utf-8 -*-
r"""探针：审计 B 车道「静默失败 / 静默降级」三条（2026-09-28）—— 落档点名 · 打断落档 · 变体正文。

真源 = `workspace/AUDIT_台账.md` 的 ①（`cmds_ast.py:236-239` `except Exception: pass`）·
②（`codex.py:107/392` + `battle_acts.py:236` `interrupts` 零写手）·
④（`cmds_tower.py:359` `read_text` 直读绕过 slot 机制）。
高③（`skills_lookup.py:209` 死函数）由本探针的静态守卫钉住（那两个函数不许再回来）。

判据（每条都带**反证**——把修复拆掉 / 把落档 mock 成抛，判据当场红）：

  ① ★★ 落档失败**必须点名**（这是本包唯一落档口 `cmds_ast._save`）
     · ①-a `_save` 的返回值：`None`（存上了）/ 非空原因串（没存上）—— 不再是「吞掉」
     · ①-b 真宿主（`Host.handle` 走真引擎）：把适配器的 `save_player` 弄抛 ⇒
          玩家**必须**收到 `SYS_SAVE_FAIL` 那一行，且**收不到**「做成了」那一行
     · ①-c 两态互锁：存上了 ⇒ 一行 `SYS_SAVE_FAIL` 都没有，逐字照旧（回归）
     · ①-d **反证**：把 `_save` 换回旧口径（吞异常）⇒ ①-b 立刻红（玩家零可见 = 原缺陷）
     · ①-e 覆盖面：包内 16 个文件共 60 个 `_save(env)` 调用点**全部**仍走这一个口
       （不许谁在别处自己包一层 try，也不许谁绕过它直接 `env.save()`）
     · ①-f 文案真源：`SYS_SAVE_FAIL` 在 texts 域且**代码里零内联中文**
       （`probe_copy` 的 SEALED 判据之外再加一条：`_save` 这一族不许内联）

  ② ★ 打断真断成 ⇒ `foot.interrupts` 真的加一（真跑 `Hand._interrupt`，两态）
     · ②-a 对方在起手（`broke=True`）⇒ 计数 +1，且回话是 `COMBAT_INT_BREAK`
     · ②-b 对方没起手（`broke=False`，只推后到点时刻）⇒ 计数**不动**（不虚高）
     · ②-c 读口通：`codex.foot()` 汇总到它、`titles.ctx()` 那一格读到它（称号「十次打断」的载体）
     · ②-d **反证**：把 `note_interrupt` 猴补丁成空实现 ⇒ ②-a 立刻红
     · ②-e 静态守卫：`interrupts` 在 `content/` 里的**写点**存在（不是「只读不写」）

  ③ ★ 高③（技能等级）：`skills_lookup` 里那两个零消费者死出口**不许再回来**
     · ③-a `skill_level_of` / `skill_up` 在本包**零定义**（不留兼容壳）
     · ③-b 本包**零挂载** `skill_level_of_fn` / `skill_up_fn`（真源没定口径就不装）
     · ③-c 登记：引擎那个读口的恒 1 回落**仍然存在**（本车道不碰引擎仓）
           —— 判据是「把这个事实写下来」，不是「假装已经修好」

  ④ ★ 塔内『调查』取正文走 `_poi_read_slot`（按真实经历取正文的那一个口）
     · ④-a 域里那条变体槽位**取得到**（`poi_stele_names` 读过白桦树后换一条）
     · ④-b 真宿主：塔里那间敲『调查』，读过白桦树 ⇒ 屏上是**变体那一句**
     · ④-c **反证**：把 `tower_investigate` 猴补丁回 `v["read_text"]` 直读 ⇒ ④-b 立刻红
     · ④-d 覆盖面：全仓 `read_text` 直读**零处**（`_poi_read_slot` 内部那处 `rec.get`
           是取 base 的源头，不算绕过；判据只查「渲染那一行」的直读）

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_silent.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, ENGINE)
sys.path.insert(0, str(Path(ENGINE) / "extends"))

from saintess_engine.host.runtime import Host          # noqa: E402

from content import battle_acts as BA                 # noqa: E402
from content import cmds_ast as CA                    # noqa: E402
from content import codex as CX                       # noqa: E402
from content import combat as CB                      # noqa: E402
from content import cmds_tower as CT                    # noqa: E402
from content import scene as SC                       # noqa: E402
from content import skills_lookup as SL               # noqa: E402
from content import titles as TT                      # noqa: E402

ok = True
TOWER = "old_watchtower"
MISSING = "[MISSING TEXT"


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("OK " if cond else "X  ", label, ("  —— %s" % extra) if extra else ""))


#: ★ P0-1 续（2026-09-29 · aep0）：战斗日志行逐字带【N 刻】（真源 26_ §三 优化 1），
#:   那一格是**战斗绝对时刻**、只有读端知道 ⇒ 夹具现渲染时换通配、断言走 `_hit`。
#:   ★ 强度不降：通配只覆盖刻数那一格，图标、句子、行尾全部逐字对。
_STAMP_S = __import__("re").compile(r"^[^【]*【[^】]*刻】")


def txt(key, **slots):
    rec = CA._texts().get(key) or {}
    s = rec.get("value", "")
    for k, v in slots.items():
        s = s.replace("{%s}" % k, str(v))
    if "{t" in s:
        assert _STAMP_S.match(s), "战斗日志行首必须带【…刻】：%r" % s
        s = s.replace("{t}", "*")
    return s


def _hit(exp, out):
    """无通配走 `in`（逐字），有通配走正则整行 —— 与 probe_cmds / probe_party 同一手法。"""
    if "*" in exp:
        import re
        rx = re.compile("^" + ".*".join(re.escape(p) for p in exp.split("*")) + "$")
        return any(rx.match(str(x).strip()) for x in out)
    return exp in out


def txts():
    return CA._texts()


def txts_of(key):
    return txts().get(key) or {}


# ══════════════════════════════════════════════════════════════
# ① 落档失败必须点名
# ══════════════════════════════════════════════════════════════
print("① 落档失败点名（cmds_ast._save 是本包唯一落档口）")

FAILSLOT = "SYS_SAVE_FAIL"
r1 = txts_of(FAILSLOT)


def _code_only(block):
    """只留**可执行行**：注释（含行尾 `#`）与 docstring 里的中文不算内联文案（与 `probe_copy.scan` 同口径）。"""
    out, in_doc = [], None
    for ln in block.split("\n"):
        st = ln.strip()
        if in_doc is not None:
            if in_doc in st:
                in_doc = None
            continue
        if st[:3] in ('"""', chr(39) * 3):
            q = st[:3]
            if not (len(st) > 3 and st.endswith(q)):
                in_doc = q
            continue
        if st.startswith("#"):
            continue
        out.append(st.split("  #", 1)[0].rstrip())     # 行尾注释也不算
    return out


chk("①-a0 文案槽位 %s 在 texts 域（真源；代码里不写中文）" % FAILSLOT,
    bool(r1.get("value")) and "{why}" in r1.get("value", "") and r1.get("category") == "系统",
    "params=%s" % (r1.get("params"),))


class _Boom(object):
    """一个 `env.save` 一定抛的替身（真抛，不是打日志）。"""

    def __init__(self, msg="db is locked"):
        self.msg = msg
        self.n = 0

    def save(self):
        self.n += 1
        raise RuntimeError(self.msg)


class _Ok(object):
    def __init__(self):
        self.n = 0

    def save(self):
        self.n += 1


_b, _o = _Boom(), _Ok()
chk("①-a 落档失败时 `_save` 把**原因**交回调用方（不是 `pass`）",
    isinstance(CA._save(_b), str) and "RuntimeError" in CA._save(_b),
    "返回=%r" % (CA._save(_b),))
chk("①-a2 原因里带原话（玩家看得见错在哪，不是笼统一句「存不上」）",
    "db is locked" in (CA._save(_b) or ""), "%r" % (CA._save(_b),))
chk("①-a3 存上了 ⇒ 返回 None（成功那一支一点不变）", CA._save(_o) is None and _o.n == 1)
chk("①-a4 空消息的异常也有可读下文（不会印出一个空白的「：」）",
    CA._save_why(Exception()) == "Exception",
    repr(CA._save_why(Exception())))
chk("①-a5 `env` 为空（不改档的读路径）按「存上了」算，不当成失败",
    CA._save(None) is None)


# —— 真宿主两态 ——
class _Ad(object):
    def __init__(self, boom):
        self.boom = bool(boom)
        self.out = []
        self.saved = {"loc": "windmill_town", "node": "wt_gate_n", "race": "human",
                      "level": 3, "gold": 50, "bag": {}, "equipped": {}, "codex": {},
                      "flags": {}, "prev": [], "foot": {}}

    def recv(self):
        return None

    def load_player(self, uid):
        return self.saved

    def save_player(self, uid, data):
        if self.boom:
            raise RuntimeError("db is locked")
        self.saved = dict(data)

    def say(self, to, text):
        self.out.append(str(text))


def drive(boom, text="往北"):
    db = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_silent_%s.db" % boom)
    try:
        os.remove(db)
    except OSError:
        pass
    ad = _Ad(boom)
    host = Host(ad, str(REPO), inject={"db_path": db, "clock": time.time})
    host.boot()
    ad.out.clear()
    host.handle({"uid": "u_s", "group_id": "g_s", "text": text})
    return list(ad.out)


ok_out = drive(False)
bad_out = drive(True)
fail_line = txt(FAILSLOT, why="RuntimeError: db is locked")
moved = txt("SYS_MOVE_OUT_NORTH")

chk("①-c 两态互锁 · 存上了：逐字照旧（『往北』那一句 + 那屏场景，一个字没动）",
    moved in ok_out and not any(FAILSLOT in x or "没存上" in x for x in ok_out)
    and len(ok_out) == 2,
    "%d 行" % len(ok_out))
chk("①-b1 落档失败：玩家**看得见**那一行点名（不是静默）",
    len(bad_out) == 1 and bad_out[0] == fail_line,
    "收到 %d 行：%r" % (len(bad_out), bad_out))
chk("①-b2 落档失败：那句「做成了」**作废**（不许一边说做成了、一边没存上）",
    moved not in bad_out and not any("你走出北门" in x for x in bad_out),
    "%r" % (bad_out,))
chk("①-b3 落档失败：那屏场景描述也不出（不当作「什么都没发生」）",
    len(bad_out) == 1 and "骨田比想的大" not in "\n".join(bad_out))

# —— 反证：把修复拆掉（换回 `except Exception: pass`）⇒ ①-b 应当红 ——
_saved_orig = CA._save


def _swallow(env):
    """旧口径：吞掉异常（审计里的原样）。"""
    try:
        env.save()
    except Exception:                                     # noqa: BLE001
        pass


CA._save = _swallow
repro = drive(True)
CA._save = _saved_orig
chk("★ ①-d 反证：换回 `except Exception: pass` ⇒ 玩家收到 %d 行「做成了」（判据 ①-b 当场红）"
    % len(repro),
    len(repro) == 2 and moved in repro and fail_line not in repro,
    "%r" % (repro[:1],))

# —— ①-e 覆盖面：全包唯一落档口 ——
_call = []
for f in sorted((REPO / "content").glob("*.py")):
    t = f.read_text(encoding="utf-8")
    # 落档那一行：裸 `_save(env)`（不接返回值那一支）或 `_bad = _save(env)`（点名那一支）
    _call.append((f.name, len(re.findall(r"^\s*(?:_bad\s*=\s*)?_save\(env\)\s*$", t, re.M))))
_tot = sum(n for _f, n in _call)
_bare = [f for f, n in _call if n]
chk("①-e1 全包落档**全部**经 `_save(env)`（%d 个调用点 / %d 个文件）—— 没有谁另起炉灶"
    % (_tot, len(_bare)), _tot >= 60, "分布：%s" % (" · ".join("%s %d" % c for c in _call if c[1])))

# 谁绕过 _save 直接 env.save()？（`instance.py` 自带一份 —— 台账已登记为中档，不在本车道）
_direct = []
_ast = (REPO / "content" / "cmds_ast.py").read_text(encoding="utf-8").split("\n")
for f in sorted((REPO / "content").glob("*.py")):
    if f.name == "instance.py":
        continue
    lines_ = f.read_text(encoding="utf-8").split("\n")
    if f.name == "cmds_ast.py":                          # 扣掉 `_save` 自己那一份（包内唯一实现）
        i0 = _ast.index("def _save(env):")
        i1 = next((j for j in range(i0 + 1, len(_ast))
                   if _ast[j].startswith("#: ") or _ast[j].startswith("def ")), len(_ast))
        lines_ = _ast[:i0] + _ast[i1:]
    for ln in _code_only("\n".join(lines_)):
        if re.search(r"(?<![\w.])env\.save\(\)", ln):
            _direct.append("%s :: %s" % (f.name, ln.strip()[:52]))
chk("①-e2 除已登记的 `instance.py` 外，**零处**绕过 `_save` 直接 `env.save()`"
    "（`cmds_party._commit` 只是转发 `_save`）", not _direct, "%s" % (_direct[:4],))
# 谁自己包了一层 try 包住 env.save()？
_swallow2 = []
for f in sorted((REPO / "content").glob("*.py")):
    t = f.read_text(encoding="utf-8")
    for m in re.finditer(r"try:\s*\n\s*env\.save\(\)\s*\n\s*except[^\n]*:\s*\n(?:\s*(?:pass|continue|return)[^\n]*\n)+", t):
        _swallow2.append(f.name)
chk("①-e3 全仓**零处**「try: env.save() / except: pass」同款吞法（`cmds_ast._save` 也不许）",
    not _swallow2 and "except Exception:\n        pass" not in
    (REPO / "content" / "cmds_ast.py").read_text(encoding="utf-8"),
    "%s" % (_swallow2[:4],))

# —— ①-f 文案真源：这一族不许内联中文 ——
_src = (REPO / "content" / "cmds_ast.py").read_text(encoding="utf-8")
_family = _src[_src.index("def _save_why"):_src.index("def _save(env):")]
_cn = re.findall(r"[一-鿿]", "".join(_code_only(_family)))
chk("①-f `_save` 一族的**可执行行**里零内联中文（中文只在注释与 texts 域）",
    not _cn, "%s" % ("".join(_cn)[:20],))
chk("①-f2 玩家可见的那一句真的取自 texts 域（`T(%r)`）" % FAILSLOT,
    ('T("%s"' % FAILSLOT) in _src)


# ══════════════════════════════════════════════════════════════
# ② 打断真断成 ⇒ 足迹真的加一
# ══════════════════════════════════════════════════════════════
print("② 打断计数落档（battle_acts → codex.note_interrupt → foot.interrupts）")


def _break_once(charging):
    """真跑一次 `Hand.override`（走引擎的 `action_override` 契约）。"""
    from ext_combat.battle import schedule as SCH
    p = CA._p({"cls": "cls_knight", "level": 5, "loc": "belt_north", "node": "bn_bone"})
    ms = SL.monsters()
    b = CB.build(p, ["ms_field_mouse"], ms, party=1, affixes=[], hp_mults=[None], uid="u_p")
    SCH.advance(b, [])
    foe = (b.sides.get(CB.ENEMY_SIDE) or [{}])[0]
    foe["charging"] = {"skill": "x", "unstoppable": False} if charging else None
    me = b.focus() or (b.sides.get(CB.PLAYER_SIDE) or [{}])[0]
    hand = BA.Hand("interrupt", p=p)
    lines, _cat, _rec = hand.override(b, "interrupt", me, "", None)
    return lines, int((p.get("foot") or {}).get("interrupts") or 0), p


_l1, _n1, _p1 = _break_once(True)
_l0, _n0, _p0 = _break_once(False)
chk("②-a 对方在起手（真断成）⇒ 足迹 `interrupts` **+1** 且回话是「截断」那一句",
    _n1 == 1 and len(_l1) == 1 and _hit(txt("COMBAT_INT_BREAK"), _l1),
    "计数=%d 回话=%r" % (_n1, _l1))
chk("②-b 对方没起手（只把到点时刻推后）⇒ 计数**不动**（不虚高）",
    _n0 == 0 and (len(_l0) == 1 and _hit(txt("COMBAT_INT_PUSH", ticks=58), _l0)
                 or (len(_l0) == 1 and not _hit(txt("COMBAT_INT_BREAK"), _l0))),
    "计数=%d 回话=%r" % (_n0, _l0))
chk("②-c1 读口通：`codex.foot()` 汇总得到它", CX.foot(_p1)["interrupts"] == 1)
chk("②-c2 读口通：称号那一格（`titles.ctx`）读到它 —— 「十次打断」不再是空的",
    TT.ctx(_p1, {})["interrupt"] == 1, "titles.ctx=%r" % (TT.ctx(_p1, {}).get("interrupt"),))
# 造够 10 次 ⇒ 那个称号真能拿到（域里 right.const = 10）
_p10 = CA._p({"cls": "cls_knight", "level": 5, "loc": "belt_north", "node": "bn_bone"})
for _ in range(10):
    CX.note_interrupt(_p10)
chk("②-c3 打断满 10 次 ⇒ 「十次打断」那一条**真拿得到**（之前恒 0、玩家永远看不到它）",
    "title_ten_interrupts" in TT.scan(_p10, {}),
    "扫到：%s" % (TT.scan(_p10, {}),))

# —— 反证：把 note_interrupt 打成空实现 ⇒ ②-a 立刻红 ——
_ni = CX.note_interrupt
CX.note_interrupt = lambda p, n=1: None
try:
    _lr, _nr, _pr = _break_once(True)
finally:
    CX.note_interrupt = _ni
chk("★ ②-d 反证：把 `note_interrupt` 打成空实现 ⇒ 真跑打断后计数 = %d（判据 ②-a 当场红）" % _nr,
    _nr == 0, "计数=%d（修复前就是这样）" % _nr)

# —— ②-e 静态守卫：写点真的存在 ——
_w = []
for f in sorted((REPO / "content").glob("*.py")):
    t = f.read_text(encoding="utf-8")
    for i, ln in enumerate(t.split("\n"), 1):
        if re.search(r'\["interrupts"\]\s*\+=|note_interrupt\(', ln) and not ln.strip().startswith("#"):
            _w.append("%s:%d" % (f.name, i))
chk("②-e `interrupts` 在 `content/` 里有**生产写点**（不再「备好但没人写」）",
    len(_w) >= 2, "写点：%s" % (_w,))


# ══════════════════════════════════════════════════════════════
# ⑤ 称号「说出口的数」不许与「真条件」对不上（审计 L3874 · 玩家可见的名实不符）
#
#   起因：`title_three_interrupts` 名字印「三次打断」而 cond 要 **10** 次
#   （`how`/`why`/写点注释三处都写 10）⇒ 玩家攒够 10 次，名字后面印「三次打断」。
#   修法 = 名字与 id 跟 cond 对齐（改**数**才是改设计，那要鱼鱼拍板）。
#   判据两条，**都是逐条现算**（不硬编码任何称号 id）：
#     A「说明」口径：`how` 里写出来的阿拉伯数字（条件阈值，玩家看得见的那句）
#       必须等于 `cond` 的 const —— 治「阈值改了、说明没跟」这一族。
#     B「名字」口径：名字里「N次」那个 N（N 是中文数字）必须等于 const ——
#       「次」就是次数，治「名字自称几次、条件要几次」这一族（本次那条就是它）。
#     名字里不带次数的说法（「认得三种字的人」那种文字游戏）不在 B 口径内，
#     但它在 A 口径里 ⇒ 阈值仍被钉住。
_TITLES = json.loads((REPO / "content" / "data" / "titles.json").read_text(encoding="utf-8"))
_CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7,
           "八": 8, "九": 9, "十": 10, "两": 2}


def _const_of(cond):
    """条件阈值（只看「字段 >= 常量」那一种形状）；其它形状回 None（无从判）。"""
    if not isinstance(cond, dict):
        return None
    right = cond.get("right")
    return right["const"] if isinstance(right, dict) and "const" in right else None


def _said_gaps(titles):
    """逐条现算「称号说出口的数」与 `cond` 阈值的差。"""
    out = []
    for k, v in titles.items():
        if not isinstance(v, dict) or k.startswith("_"):
            continue
        cst = _const_of(v.get("cond"))
        if cst is None:
            continue
        how_nums = [str(x) for x in re.findall(r"[0-9]+", str(v.get("how") or ""))]
        if how_nums and how_nums != [str(cst)]:
            out.append("%s how 写 %s 而 cond 是 %r" % (k, how_nums, cst))
        m = re.search(r"([一二两三四五六七八九十])次", str(v.get("name") or ""))
        if m and _CN_NUM.get(m.group(1)) != cst:
            out.append("%s 名字说「%s次」而 cond 是 %r" % (k, m.group(1), cst))
    return out


_bad = _said_gaps(_TITLES)
chk("⑤ 称号「说出口的数（how / 名字里的N次）」与 cond 阈值**逐条对得上**（玩家可见的名实不符）",
    not _bad, "对不上：%s" % (_bad,))
_part = [k for k, v in _TITLES.items()
         if isinstance(v, dict) and not k.startswith("_")
         and (re.findall(r"[0-9]+", str(v.get("how") or ""))
               or re.search(r"[一二两三四五六七八九十]次", str(v.get("name") or "")))
         and _const_of(v.get("cond")) is not None]
chk("⑤-b 判据**不是空转**：至少 3 条称号真的参与了对账（说了数字的）",
    len(_part) >= 3, "参与对账 %d 条：%s" % (len(_part), _part))
# —— 反证：把名字改回「三次打断」⇒ 同一个对账器当场判红（证明判据不是恒真）——
_fake = dict(_TITLES)
_fake["title_ten_interrupts"] = dict(_fake.get("title_ten_interrupts") or {},
                                     name="三次打断")
_bad_fake = _said_gaps(_fake)
chk("★ ⑤-c 反证：名字再写回「三次打断」，同一条对账**判得出**（判据不是恒真）",
    any("三次" in s for s in _bad_fake), "对账器对旧名的判词：%s" % (_bad_fake,))


# ══════════════════════════════════════════════════════════════
# ③ 高③：技能等级那两个死出口不许回来（本车道只删，不装）
# ══════════════════════════════════════════════════════════════
print("③ 技能等级（死函数已删 · 引擎那一半的 fail-closed 归别的车道）")
_sl_src = (REPO / "content" / "skills_lookup.py").read_text(encoding="utf-8")
_code = [ln for ln in _sl_src.split("\n")
         if re.match(r"\s*(async )?def (skill_level_of|skill_up)\b", ln)]
chk("③-a `skills_lookup` 里 `skill_level_of` / `skill_up` **零定义**（不留兼容壳）",
    not _code, "%s" % (_code,))
_mount = []
for f in sorted((REPO / "content").glob("*.py")):
    t = f.read_text(encoding="utf-8")
    for i, ln in enumerate(t.split("\n"), 1):
        if re.search(r"skill_level_of_fn\s*=|skill_up_fn\s*=|mount\([^)]*skill_level_of", ln):
            _mount.append("%s:%d" % (f.name, i))
chk("③-b 本包**零挂载** `skill_level_of_fn` / `skill_up_fn`（真源没定口径就不装）",
    not _mount, "%s" % (_mount,))
chk("③-b2 本包玩家档上**没有** `skill_levels` 那一格（没有可读的真值）",
    not [f.name for f in (REPO / "content").glob("*.py")
         if re.search(r'["\']skill_levels["\']\s*[=:]', f.read_text(encoding="utf-8"))])
# ③-c 登记：引擎那一半的恒 1 回落**仍然在**（本车道不碰引擎仓 —— 写下来，别装成已修好）
try:
    from ext_combat.battle import formulas as _F
    _eng = _F.skill_level_of({"class_name": "cls_knight"}, "横剑")
    _eng_doc = "未装配 → 1" in (_F.skill_level_of.__doc__ or "")
except Exception as e:                                      # noqa: BLE001
    _eng, _eng_doc = None, False
chk("③-c 登记：引擎读口 `formulas.skill_level_of` 恒 1 的回落**仍然存在**（本车道不碰引擎仓"
    " —— 这一半要车道 A/D 收，本探针如实钉住「还没修」）", _eng == 1, "实测=%r" % (_eng,))


# ══════════════════════════════════════════════════════════════
# ④ 塔内『调查』按真实经历取正文（走 _poi_read_slot 那一个口）
# ══════════════════════════════════════════════════════════════
print("④ 塔内正文走变体槽位（cmds_tower.tower_investigate → _poi_read_slot）")
PO = CA._data("pois")
TX = txts()
_v = PO["poi_stele_names"]
_base = str(_v.get("read_text") or "")
_tv = _v.get("text_variant") or {}
_p_fresh = {"books": {"relic": {}}}
_p_seen = {"books": {"relic": {"poi_named_birch": {"day": 1, "known": False}}}}
_s_fresh = CA._poi_read_slot(_v, _p_fresh)
_s_seen = CA._poi_read_slot(_v, _p_seen)
chk("④-a0 域里那格带着变体声明（`text_variant.read`）", _tv == {"read": "poi_named_birch"}, "%s" % (_tv,))
chk("④-a1 未读过白桦树 ⇒ 取基础槽位", _s_fresh == _base, "%s" % (_s_fresh,))
chk("④-a2 读过白桦树 ⇒ 取**变体**槽位（那一格以前塔里永远取不到）",
    _s_seen == SC.variant_slot(TX, _base, "poi_named_birch") and _s_seen != _base,
    "%s" % (_s_seen,))
chk("④-a3 变体槽位在 texts 域里真有正文（不是空壳）",
    len((TX.get(_s_seen) or {}).get("value") or "") >= 20 and MISSING not in str(TX.get(_s_seen)),
    "正文=%r" % ((TX.get(_s_seen) or {}).get("value") or "")[:46])


class _Ad2(object):
    def __init__(self):
        self.out = []
        self.saved = None

    def recv(self):
        return None

    def load_player(self, uid):
        return self.saved

    def save_player(self, uid, data):
        self.saved = dict(data)

    def say(self, to, text):
        self.out.append(str(text))


def tower_investigate_lines(seen_birch, force_direct=False):
    """真宿主里站到塔里那间，敲『调查』，看正文取的是哪一条。

    `force_direct=True` = 把 `tower_investigate` 猴补丁回旧口径（`v["read_text"]` 直读）——
    引擎的处理器表是在 `host.boot()` 时从 `content.commands` 解析的，所以要在 boot **之前**换。
    """
    from content import instance as _INST
    _INST.clear(_INST.key_of("g_t", "u_t", ["u_t"]))
    ad2 = _Ad2()
    ad2.saved = {"loc": TOWER, "node": "tower_horn_room", "prev": [], "race": "human",
                 "level": 6, "gold": 30, "bag": {}, "equipped": {}, "codex": {}, "flags": {},
                 "cls": "cls_knight", "foot": {"nodes": {}, "visits": {}},
                 "books": {"relic": ({"poi_named_birch": {"day": 1, "known": False}}
                                    if seen_birch else {})}}
    db = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_silent_tower.db")
    try:
        os.remove(db)
    except OSError:
        pass
    holder = {}
    if force_direct:
        # 引擎的处理器表在**装载期**就把 `bind_handler` 包出来的闭包存进了
        # `content.commands.COMMANDS`（它收 `(env)`，签名与实现体不同）——
        # 所以反证要换的是那一张表里的那一格，而且要用**同一个形状**重新包一层：
        # `lead=lambda env: (env,)`（本包 `commands.py:load_declared_bindings` 就是这么包的，
        # 调用帧 = `fn(env, sink, uid, player)`）、`resolve` 指向那个旧口径的实现体。
        from content import commands as _CM
        from saintess_engine.command.binding import bind_handler, BindSpec
        holder["orig"] = _CM.COMMANDS["tower_investigate"]["handler"]
        _CM.COMMANDS["tower_investigate"]["handler"] = bind_handler(
            BindSpec(handler="content.cmds_tower:tower_investigate", call="run",
                     args=("uid", "player")),
            lead=lambda env: (env,),
            resolve=lambda _ref: _direct_investigate,
            where="probe_silent 反证（read_text 直读）")
    try:
        host = Host(ad2, str(REPO), inject={"db_path": db, "clock": time.time})
        host.boot()
        ad2.out.clear()
        host.handle({"uid": "u_t", "group_id": "g_t", "text": "调查"})
    finally:
        if force_direct:
            _CM.COMMANDS["tower_investigate"]["handler"] = holder["orig"]
    return list(ad2.out)


async def _direct_investigate(env, sink, uid, player):
    """★ 反证用：审计里的原样 —— 正文直读 `v["read_text"]`（绕过 slot 机制）。"""
    p = CA._p(player)
    if not CT._inside(p):
        yield CA.T("SYS_TOWER_NOT_IN", name=CA._name_of_node(*CT._entrance()))
        return
    here = [(pid, v, st_, ln_) for pid, v, st_, ln_ in CA._pois_here(TOWER, p["node"], p)
            if v.get("read_text")]
    if not here:
        yield CA.T("SYS_TOWER_INV_NONE")
        return
    got = []
    for pid, v, st_, ln_ in here:
        if ln_:
            yield ln_
        if st_ == "no":
            continue
        yield CA.T("SYS_READ_HEAD", name=v.get("name"))
        yield CA.T(v["read_text"])                        # ← 直读（修复前的那一行）
        if v.get("into_codex") and CX.note_read(p, pid):
            got.append(pid)
    if got:
        if player is not None:
            player.update(p)
        _bad = CA._save(env)
        if _bad:
            yield CA.T("SYS_SAVE_FAIL", why=_bad)
            return
        for pid in got:
            yield CA.T("SYS_CODEX_NEW", book=CX.label("relic"), name=CX.name_of("relic", pid))


got_seen = tower_investigate_lines(True)
chk("④-b1 真宿主：读过白桦树后敲『调查』⇒ 屏上是**变体那一句**",
    (TX.get(_s_seen) or {}).get("value") in got_seen, "%r" % (got_seen,))
chk("④-b2 同一次里**不再**印基础那一句（变体是真替换，不是两句都出）",
    (TX.get(_base) or {}).get("value") not in got_seen, "%r" % (got_seen,))

# —— 反证：把 tower_investigate 换回 `v["read_text"]` 直读 ⇒ ④-b 立刻红 ——
repro4 = tower_investigate_lines(True, force_direct=True)
chk("★ ④-c 反证：换回 `v[\"read_text\"]` 直读 ⇒ 变体那一句**取不到**（判据 ④-b 当场红）"
    "；印的是基础那一句",
    (TX.get(_s_seen) or {}).get("value") not in repro4
    and (TX.get(_base) or {}).get("value") in repro4,
    "直读时印的是：%r" % ([x for x in repro4 if "名字一排排" in x][:1],))

# —— ④-d 覆盖面：全仓 `read_text` 渲染直读零处 ——
_direct_reads = []
for f in sorted((REPO / "content").glob("*.py")):
    if f.name == "cmds_ast.py":                           # `_poi_read_slot` 内部那处是**取 base**的源头
        continue
    for ln in _code_only(f.read_text(encoding="utf-8")):
        if re.search(r'T\(\s*[vr]\w*\[\s*[\'"]read_text[\'"]\s*\]', ln):
            _direct_reads.append("%s :: %s" % (f.name, ln.strip()[:50]))
chk("④-d 全仓「渲染正文那一行」**零处** `read_text` 直读（都走 `_poi_read_slot`）",
    not _direct_reads, "%s" % (_direct_reads,))
_n_slot = sum(len(re.findall(r"_poi_read_slot\(", (f).read_text(encoding="utf-8")))
              for f in (REPO / "content").glob("*.py"))
chk("④-d2 `_poi_read_slot` 有 3 个调用点（触摸 / 读 / 塔内调查）—— 同一个口",
    _n_slot >= 4, "%d 处（含定义）" % _n_slot)

# ⑥ 判据打在**公开那一口** `station_level` 上（不打 `_mon_lv` 那个新助手 ——
# 打助手的话，把 `station_level` 那一行改回 `or 1` 而助手还留着，判据照样全绿 = 假绿）。
# 用 `encounter_cand` 猴补把候选钉成「一只 0 级的」⇒ 不依赖真实域数据。
_EX = __import__("content.explore", fromlist=["station_level"])
_CB = __import__("content.combat", fromlist=["encounter_cand"])
_cb0, _sl0 = _CB.encounter_cand, _EX.station_level
try:
    _CB.encounter_cand = lambda ms, loc, node, lv: (["m_zero"], [])   # 一只 0 级的怪
    _r_zero = _sl0({"m_zero": {"lv": 0}}, "belt_north", "bn_bone", 3)
    _CB.encounter_cand = lambda ms, loc, node, lv: (["m_nokey"], [])   # 那只**没填** lv
    _r_nokey = _sl0({"m_nokey": {}}, "belt_north", "bn_bone", 3)
    _CB.encounter_cand = lambda ms, loc, node, lv: (["m_seven"], [])   # 正常值
    _r_seven = _sl0({"m_seven": {"lv": 7}}, "belt_north", "bn_bone", 3)
finally:
    _CB.encounter_cand = _cb0
chk("⑥ 站基准：怪**没填** lv ⇒ 回落 1（旧默认，零行为变化）", _r_nokey == 1, "%s" % (_r_nokey,))
chk("⑥-b ★ 怪**lv=0** ⇒ 站基准就是 0（不再被 `or 1` 吞成 1）",
    _r_zero == 0, "%s" % (_r_zero,))
chk("⑥-c 正常值原样（零行为变化的边界）", _r_seven == 7, "%s" % (_r_seven,))
print()
print("结果：%s" % ("有红 ✗" if not ok else "全绿 ✓"))
sys.exit(0 if ok else 1)
