# -*- coding: utf-8 -*-
"""探针：内置守卫拦截句（P-11 · 第 54 支）—— 引擎 `guard_text_fn` 那一格的内容半边。

为什么有这条线
--------------------------------------------------
宿主 `main.py` 原先自己写着那两句中文（「未找到你的角色档 …」/「你现在不在战斗中。」）——
宿主面因此带游戏业务词，宿主自己的 `scripts/check_host_boundary.py`（零游戏知识边界）**恒红**。
P-11：宿主只传**中性键**（引擎 `host/runtime.py::GUARD_KEYS`），句子搬进包（texts 域），
引擎开一个读口 `guard_text_fn`（形状 `fn(key) -> str | None`）按键取句。

本支钉的是：那一格真挂上了 · 真出得来**改前逐字那两句** · 卸载 ⇒ 引擎当场抛（fail-closed 没放宽）·
且句子真源**只有** texts 域（代码里零中文）。

判据（两态：装了 / 卸掉 · 撤改验证）
--------------------------------------------------
① 装配期真挂上了：`install_engine()` 之后引擎那一格非空 —— 且**名字是引擎 `_HOOKS` 认识的那一个**
   （★ `config.set_hook` 对不认识的名字**静默忽略** ⇒ 只测「非空」会漏掉「包挂了个引擎不认识的
   钩子」这一态：灯亮着，线没接）；钩子身份 == `content/guard_text.py::line`，形状 `fn(key)`。
② 真跑：宿主按 P-11 口径配好（`register_hint` / `battle_hint` 传**中性键**、
   `battle_check` 明确「不在战斗中」）⇒ 引擎公开守卫口 `Host.builtin_guards()` 出的那两句
   **逐字 == 改前宿主那两句**（冻在这里当基准）**且**逐字 == texts 槽位渲染（现算，不手写镜像）；
   键被**原样**问过去（探针自己包一层记录）；走 `run_guards`（引擎真派发那条路）结果一致。
③ 反证（fail-closed 没放宽）：把那一格 `set_hook(..., None)` ⇒ 同一处**必抛** `EngineNotConfigured`
   （不静默编兜底、也**不回落到键名**）；装回去 ⇒ 逐字回到那两句。
   ★ 有牙的前提 = 装配幂等（`content/apply.py::_MOUNTED`）—— 否则惰性装配器会把钩子又挂回来。
④ 撤改验证：槽位从 texts 域里拿掉 / 键→槽位映射少一个键 ⇒ 装配期对账
   （`content/guard_text.py::check_domain`）当场红。
⑤ 注入生效（两态）：临时改 texts 那一条的值 ⇒ 回话跟着变（句子不是写死在代码里的），再还原。
⑥ 静态守卫：两句整句不许出现在 `content/*.py` 里；`line()` 源码零中文（句子真源只有 texts 域）。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_guard_text.py
"""
from __future__ import annotations

import ast
import inspect
import os
import re
import sys
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, ENGINE)

from saintess_engine import config as CFG                       # noqa: E402
from saintess_engine.host.runtime import GUARD_KEYS, Host       # noqa: E402
from saintess_engine.host.env import Env, run_guards            # noqa: E402

FIXED = 1790308800.0            # 2026-09-25 12:00 +08:00（与 probe_miss / probe_mana 同一口径）
HOOK = "guard_text_fn"
MISSING = "[MISSING TEXT"
CJK = re.compile(r"[\u4e00-\u9fff]")
#: ★ 基线（**改前**宿主 `main.py` 那两句，逐字冻结在这里当判据源）——
#:   这两句就是玩家原先会在守卫拦下时看到的话；P-11 之后必须**一字不变**地从包里出来。
#: ★ 2026-09-30（注册面改造 · 鱼鱼口径）：`GUARD_KEYS[0]` 的**产品句**换成了注册引导
#:   （「未找到你的角色档」→「你还不知道自己是谁。打『我是 <族名>』…」）⇒ 本处基准随之
#:   换新并继续冻结（P-11 的「句子真源只在 texts 域」不变；②依然逐字对新基准）。
FROZEN = {
    GUARD_KEYS[0]: "你还不知道自己是谁。\n打『我是 <族名>』，比如『我是 人类』。",
    GUARD_KEYS[1]: "你现在不在战斗中。",
}

ok = True


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


class _Ad:
    """真宿主契约的最小适配器（三函数 + `say`）—— 与 `scripts/probe_miss.py` 同款。"""

    def __init__(self):
        self.out = []

    def load_player(self, uid):
        return None

    def save_player(self, uid, data):
        pass

    def say(self, to, text):
        self.out.append(str(text))


print("探针：内置守卫拦截句（P-11 · texts 域 → content/guard_text.py → 引擎 `%s`）" % HOOK)

_ad = _Ad()
_db = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_guard.db")
try:
    os.remove(_db)
except OSError:
    pass
#: ★ 宿主按 P-11 口径配：两个参数传**中性键**（不是句子），并明确「不在战斗中」
host = Host(_ad, str(REPO), inject={"db_path": _db, "clock": lambda: FIXED},
            register_hint=GUARD_KEYS[0], battle_hint=GUARD_KEYS[1],
            battle_check=lambda uid, gid: False)
stack = host.boot()
TX = stack.domain("texts") or {}

from content import apply as A                                  # noqa: E402
from content import guard_text as GT                            # noqa: E402

_env_none = Env(uid="u_guard", group_id="g_guard", player={}, text="测试")
_env_have = Env(uid="u_guard", group_id="g_guard", player={"uid": "u_guard"}, text="测试")


def _guard(name, env):
    """走引擎**公开**守卫口（`Host.builtin_guards()`）—— 与 `Host.invoke` 里的派发同一处。"""
    return host.builtin_guards()[name](env)


# ══════════════════════════════════════════════════════════════
# ① 装配期真挂上了
# ══════════════════════════════════════════════════════════════
print("① 装配期挂上了（且挂的是引擎认识的那个名字）")
_hooked = CFG.optional_hook(HOOK)
chk("① `config` 那一格非空、且就是本包那一条（`content/guard_text.py::line`）",
    callable(_hooked) and _hooked is GT.line, "实得：%r" % (_hooked,))
chk("① 那个名字是引擎 `_HOOKS` **认识**的那一个（`set_hook` 对不认识的名字静默忽略）",
    HOOK in CFG._HOOKS, "名单里有 %d 个口" % len(CFG._HOOKS))
chk("① 形状 = `fn(key)`（引擎按中性键问；`line` 只收一个形参）",
    list(inspect.signature(GT.line).parameters) == ["key"],
    list(inspect.signature(GT.line).parameters))
chk("① 装配幂等（`install_engine` 只跑一次）—— ③ 那条反证有牙的前提",
    A._MOUNTED is True, repr(getattr(A, "_MOUNTED", None)))

# ══════════════════════════════════════════════════════════════
# ② 真跑：逐字 == 改前那两句 + 键被原样问过去
# ══════════════════════════════════════════════════════════════
print("② 真跑（宿主传键 ⇒ 引擎问读口 ⇒ texts 渲染）")
_seen = []
_real = CFG._HOOKS[HOOK]


def _spy(key):
    _seen.append(key)
    return _real(key)


CFG._HOOKS[HOOK] = _spy
try:
    _reg = _guard("player", _env_none)
    _bat = _guard("battle", _env_have)
finally:
    CFG._HOOKS[HOOK] = _real
chk("② 键被**原样**问过去（宿主给的是键，不是句子）",
    _seen == [GUARD_KEYS[0], GUARD_KEYS[1]], repr(_seen))
chk("★ ② 无档 ⇒ 拦截句**逐字 == 改前宿主那两句**（玩家看到的字一个没动）",
    _reg == FROZEN[GUARD_KEYS[0]] and _bat == FROZEN[GUARD_KEYS[1]],
    "实得 %r / %r" % (_reg, _bat))
chk("★ ② 逐字 == texts 槽位现算的渲染（不手写镜像：真源在表里）",
    _reg == str((TX.get(GT.SLOTS[GUARD_KEYS[0]]) or {}).get("value"))
    and _bat == str((TX.get(GT.SLOTS[GUARD_KEYS[1]]) or {}).get("value")),
    "%r / %r" % (GT.SLOTS[GUARD_KEYS[0]], GT.SLOTS[GUARD_KEYS[1]]))
chk("② 有档 ⇒ 不拦（读口只管拦截句，不参与放行判定）", _guard("player", _env_have) is None)
chk("② 走 `run_guards`（引擎真派发那条路）结果一致",
    run_guards(["player"], _env_none, builtin=host.builtin_guards()) == FROZEN[GUARD_KEYS[0]]
    and run_guards(["player"], _env_have, builtin=host.builtin_guards()) is None)
chk("② 两句都非空、也不是 `[MISSING TEXT`（引擎那头「给不出文本 ⇒ 抛」不许从这头绕过）",
    bool(_reg.strip()) and bool(_bat.strip()) and MISSING not in _reg + _bat)

# ══════════════════════════════════════════════════════════════
# ③ 反证：那一格卸掉 ⇒ 必抛（fail-closed 没放宽）
# ══════════════════════════════════════════════════════════════
print("③ 反证有牙：卸掉读口 ⇒ 必抛 EngineNotConfigured（不回落成键名）")
_saved = CFG._HOOKS.get(HOOK)
_raised = None
try:
    CFG._HOOKS[HOOK] = None
    try:
        _guard("player", _env_none)
    except CFG.EngineNotConfigured as _e:
        _raised = str(_e)
finally:
    CFG._HOOKS[HOOK] = _saved
chk("③ 卸掉读口 ⇒ **必抛 `EngineNotConfigured`**（点名 `%s`）" % HOOK,
    bool(_raised) and HOOK in _raised, (_raised or "（没抛）")[:90])
chk("③ 装回去 ⇒ 同一处逐字回到那两句（两态都测，不是单向巧合）",
    CFG.optional_hook(HOOK) is _saved and _guard("player", _env_none) == FROZEN[GUARD_KEYS[0]])

# ══════════════════════════════════════════════════════════════
# ④ 撤改验证：槽位没了 / 映射缺键 ⇒ 装配期对账当场红
# ══════════════════════════════════════════════════════════════
print("④ 撤改验证：对账（`check_domain`）在缺料时当场红")
_bag = GT._table()
_slot0 = GT.SLOTS[GUARD_KEYS[0]]
_backup = _bag.get(_slot0)
_backup_slots = dict(GT.SLOTS)
_r1 = _r2 = None
try:
    _bag.pop(_slot0, None)
    try:
        GT.check_domain()
    except Exception as _e:                     # noqa: BLE001 —— 只要「当场抛」这一件事
        _r1 = "%s: %s" % (type(_e).__name__, _e)
    _bag[_slot0] = _backup
    GT.SLOTS.pop(GUARD_KEYS[1])
    try:
        GT.check_domain()
    except Exception as _e:                     # noqa: BLE001
        _r2 = "%s: %s" % (type(_e).__name__, _e)
finally:
    GT.SLOTS.clear()
    GT.SLOTS.update(_backup_slots)
    if _backup is None:
        _bag.pop(_slot0, None)
    else:
        _bag[_slot0] = _backup
chk("④ 槽位拿掉 ⇒ 装配期对账当场抛（%s）" % ((_r1 or "没抛")[:52],), bool(_r1))
chk("④ 键→槽位映射缺一个键 ⇒ 也当场抛（%s）" % ((_r2 or "没抛")[:52],), bool(_r2))
# ★ L2614-#4：check_domain 现在**只校验不产出**（返 None）⇒ 这里改成「不抛就算过」，
#   不再用 bool(返回值) —— 那是拿一个已删的产物当判据。
_ok4 = True
try:
    GT.check_domain()
except Exception:
    _ok4 = False
chk("④ 撤改验证后装回去 ⇒ 对账又绿（两态 · 不抛 = 过）",
    _ok4 and _guard("player", _env_none) == FROZEN[GUARD_KEYS[0]])

# ══════════════════════════════════════════════════════════════
# ⑤ 注入生效：改表值 ⇒ 回话跟着变（句子真源只有表）
# ══════════════════════════════════════════════════════════════
print("⑤ 注入生效（两态）：改 texts 那一条的值 ⇒ 回话跟着变")
_rec = _bag[_slot0]
_saved_value = _rec.get("value")
_probe_word = "探针替换"
try:
    _rec["value"] = _probe_word
    _hit = _guard("player", _env_none)
finally:
    _rec["value"] = _saved_value
chk("⑤ 改表值 ⇒ 回话跟着变（句子不是写死在代码里的）", _hit == _probe_word, repr(_hit))
chk("⑤ 还原 ⇒ 逐字回到改前那两句", _guard("player", _env_none) == FROZEN[GUARD_KEYS[0]])

# ══════════════════════════════════════════════════════════════
# ⑥ 静态守卫：句子真源只有 texts 域
# ══════════════════════════════════════════════════════════════
print("⑥ 静态守卫：`content/*.py` 里没有那两句整句、`line()` 源码零中文")
_hits = [p.name for p in sorted((REPO / "content").glob("*.py"))
         if any(s and s in p.read_text(encoding="utf-8") for s in FROZEN.values())]
chk("⑥ 两句整句不许出现在 `content/*.py` 里（代码只传槽位）", not _hits, "%s" % (_hits,))
_chk_src = Path(inspect.getsourcefile(GT.line))
_src = _chk_src.read_text(encoding="utf-8")
_tree = ast.parse(textwrap.dedent(inspect.getsource(GT.line)))
_fdef = _tree.body[0]
_doc = ast.get_docstring(_fdef, clean=False)
_lits = [n.value for n in ast.walk(_fdef)
         if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value != _doc]
chk("⑥ `line()` 源码零中文（句子真源在 texts 域）",
    not [s for s in _lits if CJK.search(s)], [s for s in _lits if CJK.search(s)][:3])
chk("⑥ 那两句在 texts 域里、且 `category` 都是「系统」",
    all(str((TX.get(GT.SLOTS[k]) or {}).get("category")) == "系统" for k in GUARD_KEYS),
    "%s" % ({GT.SLOTS[k]: (TX.get(GT.SLOTS[k]) or {}).get("category") for k in GUARD_KEYS},))
print("  · 槽位：%s" % " · ".join("%s → %s" % (k, GT.SLOTS[k]) for k in GUARD_KEYS))
print("  · 逐字：%s / %s" % (_reg, _bat))

print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
