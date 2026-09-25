# -*- coding: utf-8 -*-
"""探针：引擎里那些**该可声明的数字**真被声明表读着（审计 E2 起）。

第一把旋钮 = 闪避上限（原先 `landing._roll_dodge` 里硬编码 `min(dodge, 0.40)`）。

判据（三档，两态）
--------------------------------------------------
① 默认值逐字等于原硬编码值（0.40）—— 「不声明 = 今天一字不差」
② 声明生效（两态）：把骨架里的 `dodge.cap` 改小 ⇒ 同一个 dodge 值**不再触发闪避**；改回 ⇒ 照旧触发。
   用固定随机数（0.30）做判别，不用统计，结论不含运气。
③ 反证：`landing.py` 源码里**不再出现** `0.40` 这个字面量（硬编码搬走了，不是复制一份）

用法：`GWEN_ENGINE=... python scripts/probe_engine_knobs.py`（Python 3.12）
"""
import io
import os
import random
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENG = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, ENG)
sys.path.insert(0, REPO)
from saintess_engine.package import load_stack          # noqa: E402

st = load_stack(REPO, inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp",
                                                     "ast_probe_knobs.db"),
                              "clock": lambda: 1790308800.0})
st.install()
CMB = st.optional_submodule("combat")
MON = st.domain("monsters")
from ext_combat.battle import formulas as F              # noqa: E402
from ext_combat.battle import landing as LD              # noqa: E402
from saintess_engine import config as CFG                # noqa: E402

_pass, _fail = [], []


def chk(name, cond, seen=""):
    (_pass if cond else _fail).append(name)
    print("  %s %s%s" % ("✓" if cond else "✗", name, ("  —— %s" % (seen,)) if seen else ""))


print("══ ① 默认值 = 原硬编码值")
chk("① 未声明时 `dodge_cap()` == 0.40（与旧 `min(dodge, 0.40)` 逐字一致）",
    abs(float(F.dodge_cap()) - 0.40) < 1e-9, "实测 %s" % F.dodge_cap())

print()
print("══ ② 声明生效（两态：固定随机数 0.30 做判别）")
_b = CMB.build({"cls": "cls_assassin", "level": 16, "name": "探", "uid": "u_knob"}, ["ms_bone_wanderer"],
               MON, uid="u_knob")
_c = _b.focus()
#: ★ fixture：面板 dodge 是**聚合**出来的（裸写 `_c["dodge"]` 不生效 —— 探针自己踩过一次），
#:   这里把聚合读数直接固定成 0.50，让这条判据只考「上限有没有跟着声明走」这一件事。
from ext_combat.battle import stats as ST                # noqa: E402

_real_stats = ST.actor_stats
ST.actor_stats = lambda battle, actor: {"dodge": 0.50}

_real_random = random.random
random.random = lambda: 0.30                           # 定值：0.30 < 0.40 ⇒ 该闪；0.30 > 0.05 ⇒ 不该闪
try:
    CFG.mount(formula_skeleton_fn=lambda: {"dodge": {"cap": 0.40}})
    _hit_hi = bool(LD._roll_dodge(_b, _c, []))
    CFG.mount(formula_skeleton_fn=lambda: {"dodge": {"cap": 0.05}})
    chk("② 声明 cap=0.05 ⇒ 同一照面**不再闪避**（引擎真读了声明）", not LD._roll_dodge(_b, _c, []))
    CFG.mount(formula_skeleton_fn=lambda: {"dodge": {"cap": 0.40}})
    chk("② 声明 cap=0.40 ⇒ 照旧闪避（两端都跟着声明走，不是单向巧合）",
        bool(LD._roll_dodge(_b, _c, [])), "前一轮 cap=0.40 时闪避 = %s" % _hit_hi)
finally:
    random.random = _real_random
    ST.actor_stats = _real_stats
    CFG.mount(formula_skeleton_fn=lambda: {})

print()
print("══ ③ 反证：硬编码真的搬走了（不是复制一份）")
_src = io.open(os.path.join(ENG, "extends/ext_combat/battle/landing.py"), encoding="utf-8").read()
chk("③ 原硬编码那句表达式整句消失（`min(float(st.get(\"dodge\", 0) or 0), 0.40)`）",
    'min(float(st.get("dodge", 0) or 0), 0.40)' not in _src)
chk("③ 读点走的是声明 API（`_F.dodge_cap()`）", "_F.dodge_cap()" in _src)

print()
print("══ ④ 引擎不带玩家可见文案（E2b）：没声明就 fail-closed，声明了就用声明的那句")
import asyncio                                            # noqa: E402
from saintess_engine.command import guards as G           # noqa: E402
from saintess_engine.config import EngineNotConfigured    # noqa: E402


class _NoDecl:                                            # 没声明任何文案的命令基类
    def _uid(self, event):
        return ("g", "u")

    def _player(self, gid, uid):
        return None

    def _in_any_battle(self, gid, uid):
        return False


class _Decl(_NoDecl):
    register_hint = "【阿斯特兰】先给自己起个名字 —— 敲「开始」。"
    battle_none_hint = "【阿斯特兰】这地方现在没什么好打的。"


async def _run(owner, deco):
    out = []
    async def _cmd(self, event):
        yield "下游"
    async for x in deco(_cmd)(owner, _EV):
        out.append(x)
    return out


class _Ev:                                                # 只带 plain_result 的最小事件桩
    def plain_result(self, text):
        return text


_EV = _Ev()
_raised = None
try:
    asyncio.run(_run(_NoDecl(), G.require_player()))
except EngineNotConfigured as e:
    _raised = str(e)
chk("④ 没声明守卫文案 ⇒ 当场抛 `EngineNotConfigured`（不静默编一句玩家文案）",
    bool(_raised), (_raised or "")[:60])
_hit = asyncio.run(_run(_Decl(), G.require_player()))
chk("④ 声明了 ⇒ 用声明的那句（逐字）", _hit == [_Decl.register_hint], repr(_hit))
_hit2 = asyncio.run(_run(_Decl(), G.require_battle()))
chk("④ 战斗守卫同理", _hit2 == [_Decl.battle_none_hint], repr(_hit2))
_eng_txt = ""
for _f in ("command/guards.py", "command/tips.py", "host/runtime.py"):
    _eng_txt += io.open(os.path.join(ENG, "saintess_engine", _f), encoding="utf-8").read()
chk("④ 引擎源码里不再有那几句玩家文案（只在注释里留了「搬去哪」的说明）",
    not any(k in _eng_txt for k in ('= "你还没有角色！"', '= "你附近没有敌人！"',
                                    '= "未找到你的角色档', '= "你现在不在战斗中。"',
                                    '= "看看『帮助』了解更多"')))

print()
print("══ 汇总")
print("  通过 %d · 失败 %d" % (len(_pass), len(_fail)))
if _fail:
    for x in _fail:
        print("  ✗ %s" % x)
    sys.exit(1)
print("  结果：全绿 ✓")
