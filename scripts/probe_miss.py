# -*- coding: utf-8 -*-
"""探针：路由未命中的回话（P-54 · 第 44 支）—— 引擎那一格**必需注入**的内容半边。

为什么有这条线
--------------------------------------------------
引擎（`saintess_engine/host/runtime.py::_miss_reply`）按 P-54 起**不再自带玩家文案**：
玩家敲的词没命中任何包内声明时，它去问 `config` 里那一格 `route_miss_text_fn`；
**没装配（或装了却给不出文本）⇒ 抛 `EngineNotConfigured`** —— 引擎既不自带中文，
句子里那个「本服不一定有」的宿主命令名（`<prefix>help`）也一并去掉了。

本包原先没装这个口 ⇒ 新引擎一上线，玩家敲一个没命中的词**一句话都拿不到**。
本支钉的是：那一句真挂上了、真出得来、真给了一条**存在的**下一步，且引擎那头 fail-closed
一个字都没放宽。

判据（两态：装了 / 卸掉 · 撤改验证）
--------------------------------------------------
① 装配期真挂上了：`install_engine()` 之后引擎那一格非空 —— 且**名字是引擎 `_HOOKS` 认识的
   那一个**（★ `config.set_hook` 对不认识的名字**静默忽略** ⇒ 只测「非空」会漏掉「包挂了个
   引擎不认识的钩子」这一态：灯亮着，线没接）
② 真宿主真敲一个**不命中**的词（先现算它确实不命中）：回话非空 · 不是 `[MISSING TEXT` ·
   **不含宿主前缀**（`/help` 那类写法一个字都没有 —— P-54 的另一半）· 把玩家敲的那个词原样
   带回来 · 且那句里引号指向的指令名**真能路由**（`Host.declared_hit()` 现算 + 必须可见；
   期望那一句由 texts 域现算，不手写镜像串）
③ 反证（fail-closed 没放宽）：把那一格 `set_hook(..., None)` ⇒ `Host.route()` **必抛**
   `EngineNotConfigured`（不静默编一句兜底）；装回去 ⇒ 那一句照旧出得来
④ 撤改验证：槽位从 texts 域里拿掉 / 那句改指一条**不存在**的指令 ⇒ 装配期那条对账
   （`content/miss_text.py::check_domain`）当场红 —— 「指向哪儿都不许编」这一头有人守
⑤ 静态守卫：那一句里**没有 ASCII**（`/` 与宿主命令名那类写法都不是中文）；且整句不许出现在
   `content/*.py` 里（文案真源只有 texts 域）

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_miss.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, ENGINE)

from saintess_engine import config as CFG                       # noqa: E402
from saintess_engine.host.runtime import Host                   # noqa: E402

FIXED = 1790308800.0            # 2026-09-25 12:00 +08:00（与 probe_mana / probe_cmds 同一口径）
MISSING = "[MISSING TEXT"
#: 候选「没接住」的词 —— 由**现算**挑：真不命中 + 不带宿主前缀的那个才用（都不是 ⇒ 本支红）。
#: 不写死成一个词，是因为将来某一批把某个词收成声明之后，这里要**自己换一个**再跑
#: （写死 = 那次改动会把它判成「回话坏了」，其实是判据的 fixture 过期了）。
CANDS = ("唱歌", "睡觉", "跳舞", "发呆", "游泳", "数星星", "唱个歌")

ok = True


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


class _Ad:
    """真宿主契约的最小适配器（三函数 + `say`）—— 与 `scripts/e2e_drive.py` 同款。"""

    def __init__(self):
        self.out = []
        self.saved = None

    def load_player(self, uid):
        return None

    def save_player(self, uid, data):
        self.saved = dict(data) if isinstance(data, dict) else data

    def say(self, to, text):
        self.out.append(str(text))


print("探针：路由未命中的回话（P-54 · texts 域 `%s` → content/miss_text.py → 引擎 route_miss_text_fn）"
      % "SYS_CMD_MISS")

_ad = _Ad()
_db = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_miss.db")
try:
    os.remove(_db)
except OSError:
    pass
host = Host(_ad, str(REPO), inject={"db_path": _db, "clock": lambda: FIXED})
stack = host.boot()
TX = stack.domain("texts") or {}

from content import miss_text as MT                              # noqa: E402

SLOT = str(MT.SLOT)
_ctx = {"uid": "u_miss", "group_id": "g_miss"}

# ══════════════════════════════════════════════════════════════
# ① 装配期真挂上了（且挂的是引擎**认识**的那个名字）
# ══════════════════════════════════════════════════════════════
_hooked = CFG.optional_hook("route_miss_text_fn")
chk("① 装配期挂上了：`config` 那一格非空、且就是本包那一条（`content/miss_text.py::line`）",
    callable(_hooked) and _hooked is MT.line, "实得：%r" % (_hooked,))
chk("① 那个名字是引擎 `_HOOKS` **认识**的那一个（`set_hook` 对不认识的名字静默忽略）",
    "route_miss_text_fn" in CFG._HOOKS, "名单里有 %d 个口" % len(CFG._HOOKS))

# ══════════════════════════════════════════════════════════════
# ② 真敲一个不命中的词
# ══════════════════════════════════════════════════════════════
_miss = next((w for w in CANDS
              if w.strip() and not str(w).startswith(host.prefix)
              and host.declared_hit(w) is None), None)
chk("② 现算一个**真不命中**的测试词（先证明它不命中 —— 不然下面考的不是这条线）",
    _miss is not None, "候选 %s 全被声明接住了？" % (list(CANDS),))
if _miss is None:
    print()
    print("结果：有红 ✗")
    sys.exit(1)

_ad.out.clear()
host.handle(dict(_ctx, text=_miss))
_reply = list(_ad.out)
_line = _reply[0] if _reply else ""
_want = str((TX.get(SLOT) or {}).get("value") or "")
_want_line = _want.replace("{word}", str(_miss))
chk("② 真敲「%s」⇒ 回话逐字 = texts 槽位 `%s` 渲染（%d 段）" % (_miss, SLOT, len(_reply)),
    len(_reply) == 1 and _line == _want_line, "期望 %r / 实得 %r" % (_want_line, _line))
chk("② 非空、且不是 `[MISSING TEXT`（引擎那边「给不出文本 ⇒ 抛」这一条不许从这头绕过）",
    bool(_line.strip()) and MISSING not in _line, repr(_line))
chk("② **不含宿主前缀**（`%s` 那类宿主命令名一个字都没有 —— P-54 的另一半）" % host.prefix,
    bool(_line) and host.prefix not in _line and not re.search(r"/[A-Za-z]", _line), repr(_line))
chk("② 把玩家敲的那个词原样带回来（回话真是照着**这个词**说的，不是一句万能套话）",
    str(_miss) in _line, "找 %r" % (_miss,))
_refs = [x for x in re.findall("[\u300c\u300e]([^\u300d\u300f]+)[\u300d\u300f]", _line) if x != _miss]
_bad_refs = []
for _r in _refs:
    _spec = host.declared_hit(_r)                  # 现算：这个词真能路由（同一条注册表口径）
    if _spec is None or str(getattr(_spec, "usage", "")) != _r or not getattr(_spec, "visible", False):
        _bad_refs.append((_r, _spec))
chk("② 那句指向的指令名在本包**可见声明**里、且真能路由（%s）"
    % ("、".join("「%s」" % r for r in _refs) or "一个都没指"),
    bool(_refs) and not _bad_refs, "对不上的：%s" % (_bad_refs,))
#: 「它指的是帮助」这句话不许在代码里另写一份 —— 只许从文案里现读（文案一改判据跟着动）
chk("② 「指向哪条指令」是从**文案现读**出来的（不在代码里写死镜像）",
    MT.referenced_commands(_want) == _refs, "模块读到 %s" % (MT.referenced_commands(_want),))

# ══════════════════════════════════════════════════════════════
# ③ 反证：那一格卸掉 ⇒ 必抛（fail-closed 没放宽）
# ══════════════════════════════════════════════════════════════
_saved = CFG._HOOKS.get("route_miss_text_fn")
_raised = None
try:
    CFG.set_hook("route_miss_text_fn", None)
    try:
        host.route(dict(_ctx), {}, str(_miss))
    except CFG.EngineNotConfigured as _e:
        _raised = str(_e)
finally:
    CFG.set_hook("route_miss_text_fn", _saved)
chk("③ 反证：那一格卸掉 ⇒ `Host.route()` **必抛 `EngineNotConfigured`**（不静默编一句兜底）",
    bool(_raised), (_raised or "（没抛）")[:78])
chk("③ 装回去 ⇒ 同一句话照旧出得来（两态都测，不是单向巧合）",
    CFG.optional_hook("route_miss_text_fn") is _saved
    and host.route(dict(_ctx), {}, str(_miss)) == [_want_line])

# ══════════════════════════════════════════════════════════════
# ④ 撤改验证：槽位没了 / 指向不存在的指令 ⇒ 装配期对账当场红
# ══════════════════════════════════════════════════════════════
_bag = MT._load(MT._TEXT)                       # 模块自己那份缓存（同一份 texts 域）
_backup = _bag.get(SLOT)
_r1 = _r2 = None
try:
    _bag.pop(SLOT, None)
    try:
        MT.check_domain()
    except Exception as _e:                     # noqa: BLE001 —— 只要「当场抛」这一件事
        _r1 = "%s: %s" % (type(_e).__name__, _e)
    _bag[SLOT] = {"value": _want.replace("帮助", "掷骰子"), "params": ["word"],
                  "category": "系统", "desc": ""}
    try:
        MT.check_domain()
    except Exception as _e:                     # noqa: BLE001
        _r2 = "%s: %s" % (type(_e).__name__, _e)
finally:
    if _backup is None:
        _bag.pop(SLOT, None)
    else:
        _bag[SLOT] = _backup
chk("④ 撤改验证：槽位拿掉 ⇒ 装配期对账当场抛（%s）" % ((_r1 or "没抛")[:56],), bool(_r1))
chk("④ 撤改验证：那句改指一条**不存在**的指令（帮助 → 掷骰子）⇒ 也当场抛（%s）"
    % ((_r2 or "没抛")[:56],), bool(_r2))
chk("④ 撤改验证后装回去 ⇒ 对账又绿（两态）", bool(MT.check_domain()))

# ══════════════════════════════════════════════════════════════
# ⑤ 静态守卫
# ══════════════════════════════════════════════════════════════
_bare = re.sub(r"\{\w+\}", "", _want)
chk("⑤ 那一句里**没有 ASCII**（`/`、`help` 那类宿主命令名写法都不是中文）：%s" % (_bare,),
    bool(_bare.strip()) and not re.search(r"[A-Za-z/\\]", _bare))
_src_hits = [p.name for p in sorted((REPO / "content").glob("*.py"))
             if _line and _line in p.read_text(encoding="utf-8")]
chk("⑤ 文案真源只有 texts 域：整句（渲染后逐字）不许出现在 `content/*.py` 里",
    not _src_hits, "%s" % (_src_hits,))
print("  · 回话逐字：%s" % _line)
print("  · 指向的指令名：%s ⇒ 可见声明 usage 现读 = %s"
      % ("、".join(_refs) or "—", sorted(MT.declared_usages())[:6]))

print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
