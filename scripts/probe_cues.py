# -*- coding: utf-8 -*-
"""探针：表现事件（cue）订阅表（第 55 支）—— 引擎侧 cue 迁移下本包「不掉行、不静默」。

背景（为什么这条线必须钉）
------------------------------------------------------------------
产品线把「战斗结算里顺手拼一句玩家可见文案」改成「结算发 cue 事件、文案由内容侧订阅者渲染」。
引擎侧的形状已落地（`extends/ext_combat/battle/cues.py` + `saintess_engine/cues.py`）：
装配期对账（引擎 `CUE_NAMES` 声明的 cue 名**必须条条有订阅**）+ 同步就地 append +
「文案必须命中」（`render_required`：表不在 / 表里没那个 key ⇒ 抛）。
内容侧此前唯一的缺口就是「订阅表 + 挂 hook」这一层。缺了会怎样：
    · 一条都不订阅 ⇒ 引擎装配期对账当场抛（看得见，但玩家进不了战斗）；
    · 挂上了、但名单是**手抄的第二份** ⇒ 今天不出错 —— 引擎以后加一条点位，本包就静默丢一行。
⇒ 本支钉的是「订阅表 = 引擎 `CUE_NAMES` 的**现算**结果」（名单只有一份，在引擎那边）。

判据（每档都带反证 / 两态）
------------------------------------------------------------------
① 装配期真挂上了：`cue_subs_fn` 非空 · 就是本包那条 · 名字是引擎 `_HOOKS` 认识的 · 幂等 ·
   反「静默不装」的回读在装配源码里
② 订阅表 = 引擎 `CUE_NAMES` 现生成（逐条同序、同名、key==cue 名）；★ 静态守卫：已声明的
   cue 名**不许**在 `content/*.py` 里被手抄成字面量（唯一允许的例外是 `battle_text.py`
   里那一处既有特例 `battle.landing.damage`，与订阅表无关）；句子也不许出现在
   `content/cues.py`（订阅表只写 key）
③ 构造出来的 Battle 真带总线；总线持有的表就是本包注入 `Battle(text=…)` 的那一张
④ 三条原点位（dodged / element_immune / resist_reduce）**在引擎里真发一次**（走引擎自己的
   结算函数）⇒ 那一行逐字节 == 文案表那一条（槽位取引擎真发的、不手写）；再对**引擎声明的
   每一条** cue 逐条对拍「订阅表 × 文案表」这条链（引擎以后加成 20 条也不用改本支）
⑤ 反证：文案表缺 key ⇒ 构造 Battle **当场抛**并点名（两态：声明被删 / 那格是空的）
⑥ 反证：引擎声明里多一条**假** cue ⇒ 必抛并点名；★ 反向正证：引擎声明里多一条**真** cue
   （本包文案表里有那一格）⇒ 本包**自动跟上**（订阅表自己长出来、真发得出那一行）
⑦ 反证：订阅表少一条 / 多一条引擎不认的 ⇒ 装配期对账当场抛（引擎那一头有牙）
⑧ 反证（运行期）：把那条 key 从**这场战斗正在用的表**里拿掉 ⇒ 出来的**不是**文案表那句、
   而是引擎那行可读坏数据（⚠️）+ 进 `battle.diagnostics`（不静默丢行、不回落）；
   表被弄坏到「一渲染就抛」同理；两态都还原回绿；**结算一个字不改**（免疫照旧归 0）

用法：GWEN_ENGINE=C:/Users/yuyu/fw-wt/cue-rig python scripts/probe_cues.py
      （Python 3.12。引擎树必须有 cue 形状 —— 主线合入之前用 `cue-rig` 那棵；
        引擎树没有形状时本支**当场红**并打出上面这条命令，不静默跳过。）
"""
from __future__ import annotations

import ast
import contextlib
import os
import random
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
#: ★ 本会话 `LOCALAPPDATA` 可能被污染 ⇒ 库路径走**绝对路径**（可用 `AST_PROBE_TMP` 覆盖）
_TMP = os.environ.get("AST_PROBE_TMP", "C:/Users/yuyu/AppData/Local/Temp")
_DB = os.path.join(_TMP, "ast_probe_cues.db")
_CUE_SHAPE = os.path.join(ENGINE, "extends", "ext_combat", "battle", "cues.py")

print("探针：表现事件（cue）订阅表（第 55 支）")
if not os.path.exists(_CUE_SHAPE):
    print("  ✗ 引擎树（%s）没有 cue 形状 —— 本支要在**带 cue 的引擎树**上跑：" % ENGINE)
    print("      GWEN_ENGINE=C:/Users/yuyu/fw-wt/cue-rig python scripts/probe_cues.py")
    sys.exit(1)

sys.path.insert(0, REPO)
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                      # noqa: E402
from saintess_engine.text import safe_format                        # noqa: E402

FIXED = 1790308800.0        # 2026-09-25 12:00 +08:00（与 probe_combat / probe_guard_text 同口径）

failures: list = []


def chk(label, cond, extra=""):
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))
    if not cond:
        failures.append(label)
    return bool(cond)


st = load_stack(REPO, inject={"db_path": _DB, "clock": lambda: FIXED})
st.install()

import ext_combat.battle.cues as ECU                                # noqa: E402
from ext_combat.battle import landing as LD                          # noqa: E402
from ext_combat.battle import stats as ST                            # noqa: E402
from saintess_engine import config as CFG                            # noqa: E402
from content import apply as A                                       # noqa: E402
from content import battle_text as BT                                # noqa: E402
from content import combat as CMB                                    # noqa: E402
from content import cues as CU                                       # noqa: E402

MON = st.domain("monsters")
TX = st.domain("texts") or {}
NAMES = CU.cue_names()
SUBS = CU.subs()
#: ★ 三条**原点位**（B1 最小切片那一批）—— 本支给它们写「真触发」夹具（其余按逐条对拍）。
_ORIGINAL = ("battle.landing.dodged", "battle.landing.element_immune",
             "battle.landing.resist_reduce")


def _build():
    """造一场真战斗（本包的组场口）—— 构造期就是引擎的装配期对账点。"""
    return CMB.build({"cls": "cls_knight", "level": 3, "hp": 140, "uid": "u_cue"},
                     ["ms_field_mouse"], MON, uid="u_cue")


def _raise_of(fn):
    """跑一次、把「抛了什么」原样取回来（没抛 ⇒ None）—— 反证档统一用它。"""
    try:
        fn()
    except Exception as _e:                                          # noqa: BLE001
        return "%s: %s" % (type(_e).__name__, _e)
    return None


@contextlib.contextmanager
def _fx(stats: dict, rand: float):
    """夹具（与 `probe_engine_knobs` 同一套口径）：面板读数 + 随机数**都钉死**。

    判据只看「这行是谁渲染的」，不允许靠掷硬币。
    """
    _rs, _rr = ST.actor_stats, random.random
    ST.actor_stats = lambda battle, actor: dict(stats)
    random.random = lambda: rand
    try:
        yield
    finally:
        ST.actor_stats, random.random = _rs, _rr


def _want(name: str, payload: dict) -> str:
    """文案表那一条 + 给定的槽位 —— 判据的期望值**现算**（不手写镜像句）。"""
    _tpl = str((TX.get(BT.slots()[name]) or {}).get("value") or "")
    return safe_format(_tpl, payload)


class _SpyBus:
    """包一层总线：把引擎**真发**的 (cue 名 → 槽位) 原样记下来，然后交给真总线。

    ★ 为什么要它：槽位名不许在探针里手写一份（那就是第二份接口表）——期望值要用
      「引擎真发的槽位」+「文案表那一条」现算出来，才照得出「引擎发 A、文案表却写 B」。
    """

    def __init__(self, real):
        self._real = real
        self.sent: dict = {}

    def __getattr__(self, name):                # subs / table / subs_of … 一律透传
        return getattr(self._real, name)

    def emit(self, logs, name, payload=None):
        self.sent.setdefault(str(name), dict(payload or {}))
        return self._real.emit(logs, name, payload)


# ══════════════════════════════════════════════════════════════
# ① 装配期真挂上了
# ══════════════════════════════════════════════════════════════
print("① 装配期真挂上了（且挂的是引擎认识的那个名字）")
_hook = CFG.optional_hook("cue_subs_fn")
chk("① `config` 那一格非空、且就是本包那条（`content/cues.py::cue_subs`）",
    callable(_hook) and _hook is CU.cue_subs, "实得：%r" % (_hook,))
chk("① 那个名字是引擎 `_HOOKS` **认识**的那一个（`set_hook` 对不认识的名字静默忽略）",
    "cue_subs_fn" in CFG._HOOKS, "名单里有 %d 个口" % len(CFG._HOOKS))
chk("① 引擎树真有 cue 形状（`content/cues.py::engine_has_cues()`）", CU.engine_has_cues(), ENGINE)
chk("① 装配幂等（`install_engine` 只跑一次）—— 反证档有牙的前提", A._MOUNTED is True)
_src_apply = open(os.path.join(REPO, "content", "apply.py"), encoding="utf-8").read()
chk('① 反「静默不装」的回读在装配源码里（`config.optional_hook("cue_subs_fn")`）',
    'config.optional_hook("cue_subs_fn")' in _src_apply)

# ══════════════════════════════════════════════════════════════
# ② 订阅表 = 引擎 CUE_NAMES 现生成（不是手抄的第二份名单）
# ══════════════════════════════════════════════════════════════
print("② 订阅表是引擎声明的**现算**结果（引擎加一条，本表自动长一条）")
_engine_names = tuple(str(x) for x in ECU.CUE_NAMES)
chk("② 订阅表的键序逐条 == 引擎 `CUE_NAMES`（现读，不是镜像）",
    tuple(SUBS) == _engine_names, "订阅表 %d 条 / 引擎 %d 条" % (len(SUBS), len(_engine_names)))
chk("② 每条 = 恰好一个 `kind=\"text\"` 订阅者、`key` == cue 名（同名即接口，不造映射表）",
    all(v == ({"kind": "text", "key": k},) for k, v in SUBS.items()))


def _code_literals(path: str) -> set:
    """文件里**代码字面量**的字符串集合（docstring / 注释不算 —— 讲解里提到 cue 名是允许的）。"""
    tree = ast.parse(open(path, encoding="utf-8").read())
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            _d = ast.get_docstring(node, clean=False)
            if _d is not None:
                docs.add(_d)
    return {n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value not in docs}


#: ★ 唯一允许的例外（**既有的**、与订阅表无关的一处）：`battle_text.py` 的
#:   `_ENGINE_DAMAGE_KEY` —— 自付血那一笔要顶掉引擎的通用伤害行（`_QuietOnce`）。
_CUE_LITERAL_EXC = {("battle_text.py", "battle.landing.damage")}
_PY = sorted(f for f in os.listdir(os.path.join(REPO, "content")) if f.endswith(".py"))
_hard = {}
for _f in _PY:
    _hit = sorted((_code_literals(os.path.join(REPO, "content", _f)) & set(_engine_names))
                  - {n for c, n in _CUE_LITERAL_EXC if c == _f})
    if _hit:
        _hard[_f] = _hit
chk("★ ② 已声明的 cue 名**不许**在 `content/*.py` 里被手抄成字面量（手抄名单 = 双源温床）",
    not _hard, "%s（共扫 %d 个文件）" % (_hard or "无", len(_PY)))
_src_cues = open(os.path.join(REPO, "content", "cues.py"), encoding="utf-8").read()
_sentences = [str((TX.get(BT.slots()[n]) or {}).get("value") or "") for n in _engine_names]
chk("★ ② 订阅表里**只写 key、不写句子**（那些文案一句都不在 `content/cues.py` 里）",
    not [s for s in _sentences if s and s in _src_cues],
    "扫了 %d 句" % len([s for s in _sentences if s]))

# ══════════════════════════════════════════════════════════════
# ③ Battle 带总线
# ══════════════════════════════════════════════════════════════
print("③ 构造出来的 Battle 带总线，且总线用的就是本包那张表")
B = _build()
_REAL_BUS = ECU.cue_of(B)
chk("③ 引擎 `cue_of(battle)` 非空（这款游戏**接了** cue）", _REAL_BUS is not None, repr(_REAL_BUS))
chk("③ 总线里的订阅表 == 本包声明的那一张", dict(getattr(_REAL_BUS, "subs", {}) or {}) == SUBS)
#: ★ P2-4b：`Battle(text=…)` 外面套了一层**显示名翻译代理**（`name_map.TranslatedTable`），
#:   所以 identity 链多一跳 —— 断言的**意图一字未改**（仍是「句子真源只有一处」），
#:   只是把这一跳写进去，并额外钉住「代理不持有第二份文案」（拆包后就是那一张）。
_tbl_inj = B.text
_tbl_real = getattr(_tbl_inj, "wrapped", _tbl_inj)
chk("③ 总线持有的表 is 注入 `Battle(text=…)` 的那一张 is `battle_text.table()`（句子真源一处）",
    getattr(_REAL_BUS, "table", None) is B.text and _tbl_real is BT.table())
chk("③ 翻译代理只是**翻译层**、不持有第二份文案（拆包后逐字是那一张）",
    not hasattr(_tbl_inj, "_specs") or _tbl_inj._specs is _tbl_real._specs,
    "代理类型 %s" % type(_tbl_inj).__name__)

# ══════════════════════════════════════════════════════════════
# ④ 真发一次（三条原点位）⇒ 逐字节 == 文案表那一条
# ══════════════════════════════════════════════════════════════
print("④ 三条原点位**在引擎里真发一次**（走引擎自己的结算函数，不手填槽位）")
_SPY = _SpyBus(_REAL_BUS)
B.cues = _SPY
_LINE: dict = {}


def _emit(name: str):
    """真发一次那条 cue，返回 (日志行列表, 结算回执)。"""
    if name == "battle.landing.dodged":
        _t = {"name": "试桩", "level": 1, "hp": 50, "effects": {}}
        _l = []
        with _fx({"dodge": 0.5}, 0.0):
            _got = LD._roll_dodge(B, _t, _l)
        return _l, _got
    if name == "battle.landing.element_immune":
        _t = {"name": "试桩", "level": 1, "hp": 50, "effects": {}, "element_immune": ["fire"]}
        _l = []
        with _fx({"dodge": 0.0}, 1.0):
            _got = LD.deal_damage(B, None, _t, 50, _l, element="fire")
        return _l, (_got, _t.get("hp"))
    if name == "battle.landing.resist_reduce":
        _t = {"name": "试桩", "level": 1, "hp": 50, "effects": {}}
        _l = []
        with _fx({"dodge": 0.0, "elem_res": 0.3}, 1.0):
            _got = LD.deal_damage(B, None, _t, 50, _l, element="ice")
        return _l, (_got, _t.get("hp"))
    raise AssertionError("本探针只给三条原点位写了真触发夹具：%r" % (name,))


for _n in _ORIGINAL:
    _logs, _got = _emit(_n)
    _LINE[_n] = _logs[0] if _logs else None
    _d = getattr(B, "diagnostics", None) or []
    _err = " / ".join("%s:%s" % (x.get("stage"), str(x.get("msg"))[:60]) for x in _d[-1:])
    chk("★ ④ `%s` ⇒ 那一行逐字节 == 文案表 `%s` 渲染（槽位取引擎真发的）"
        % (_n, BT.slots()[_n]),
        bool(_logs) and _logs[0] == _want(_n, _SPY.sent.get(_n, {})),
        "实得 %r%s" % (_LINE[_n], ("  [这一调后引擎诊断：%s]" % _err) if _err and not _logs else ""))
chk("★ ④ 三条原点位都在引擎里真发过（点位到得了发事件那一口）",
    set(_SPY.sent) >= set(_ORIGINAL), "真发过：%s" % (sorted(_SPY.sent),))

# ④b：**引擎声明的每一条** cue 逐条对拍「订阅表 × 文案表」（引擎以后加成 20 条也不用改本支）
_l4: list = []
_mismatch: list = []
for _n in _engine_names:
    _rec = TX.get(BT.slots()[_n]) or {}
    _pl = {str(p): "P_" + str(p) for p in (_rec.get("params") or [])}
    _l = []
    ECU.cue(B, _l, _n, payload=_pl)
    _exp = _want(_n, _pl)
    if _l != [_exp]:
        _mismatch.append("%s：实得 %r / 期望 %r" % (_n, _l, [_exp]))
    _l4.append(_n)
chk("★ ④ 引擎声明的**每一条** cue 都经「总线 → 文案表」渲染出行（%d 条，逐条对拍）"
    % len(_engine_names), not _mismatch, " ; ".join(_mismatch[:3]) or "全对")

# ══════════════════════════════════════════════════════════════
# ⑤ 反证：文案表缺 key ⇒ 构造 Battle 当场抛并点名
# ══════════════════════════════════════════════════════════════
print("⑤ 反证：文案表缺 key ⇒ 装配期（构造 Battle）当场抛并点名")
_drop = _engine_names[0]
_bag = BT._rules()
_saved_slot = _bag["slots"].pop(_drop)
BT._CACHE.pop("table", None)
try:
    _r = _raise_of(_build)
finally:
    _bag["slots"][_drop] = _saved_slot
    BT._CACHE.pop("table", None)
chk("⑤ 从 `battle_text.json` 删掉那条声明 ⇒ 构造 Battle 必抛",
    bool(_r), (_r or "（没抛 —— 静默漏行！）")[:110])
chk("★ ⑤ 抛的话要点名：那条 cue + 「去 battle_text.json 补声明」都在消息里",
    bool(_r) and _drop in _r and "battle_text.json" in _r)

_tx_raw = BT._texts()
_saved_val = _tx_raw.pop(_saved_slot)
BT._CACHE.pop("table", None)
try:
    _r2 = _raise_of(_build)
finally:
    _tx_raw[_saved_slot] = _saved_val
    BT._CACHE.pop("table", None)
chk("⑤ 声明还在、但那一格在表里是**空的** ⇒ 也必抛（挡的是「键在、话没了」那一态）",
    bool(_r2) and _drop in _r2, (_r2 or "（没抛）")[:110])
chk("★ ⑤ 这一态还得点名**缺的那一格**（cue 名 → 槽位名，修的人不用猜）",
    bool(_r2) and _saved_slot in _r2, "槽位 = %s" % _saved_slot)
chk("⑤ 还原 ⇒ 又绿（两态，不是单向巧合）",
    _raise_of(CU.check_domain) is None and _raise_of(_build) is None)

# ══════════════════════════════════════════════════════════════
# ⑥ 引擎声明里多条 cue：假的必抛、真的自动跟上
# ══════════════════════════════════════════════════════════════
print("⑥ 引擎声明多一条 cue：假的必抛，真的**本包自动跟上**（不用改一行代码）")
_saved_names = ECU.CUE_NAMES
try:
    ECU.CUE_NAMES = tuple(_saved_names) + ("battle.landing.probe_fake",)
    _r3 = _raise_of(_build)
finally:
    ECU.CUE_NAMES = _saved_names
chk("⑥ 猴补一个假名字进引擎 `CUE_NAMES` ⇒ 构造 Battle 必抛（本包文案表里没有它那一格）",
    bool(_r3) and "battle.landing.probe_fake" in _r3, (_r3 or "（没抛）")[:110])

#: ★ 2026-09-27（引擎侧 B1–B5 走完之后）：本包文案表与引擎声明**逐条对齐**（60 == 60），
#:   不再有「多出来备用的一格」可挑 ⇒ 这里**进程内现造**一格当「引擎以后加的那条点位」，
#:   与 ⑤ 段同款手法（往 slots 与 texts 各插一条、清表缓存、`finally` 还原，不动任何数据文件）。
_BONUS = "battle.landing.probe_bonus"
_BONUS_SLOT = "COMBAT_PROBE_BONUS"
_bonus_entry = {"value": "探针点 {name}", "params": ["name"], "category": "战斗",
                "desc": "本支 ⑥ 段进程内现造（模拟「引擎以后多加一条真 cue」）"}
_rules_raw = BT._rules()
_rules_raw["slots"][_BONUS] = _BONUS_SLOT      # ★ 插在 `slots` 子表里（`slots()` 每次返回副本）
_tx_raw[_BONUS_SLOT] = _bonus_entry
TX[_BONUS_SLOT] = _bonus_entry
BT._CACHE.pop("table", None)
try:
    _bonus = _BONUS
    _pl_bonus = {str(p): "P_" + str(p)
                 for p in ((TX.get(BT.slots()[_bonus]) or {}).get("params") or [])}
    B2 = None
    _l2: list = []
    _b2_err = None
    try:
        ECU.CUE_NAMES = tuple(_saved_names) + (_bonus,)
        try:
            B2 = _build()                       # 引擎声明多一条 ⇒ 本包订阅表跟着长，构造**不抛**
        except Exception as _e:                 # noqa: BLE001 —— 抛了就是这一档红
            _b2_err = "%s: %s" % (type(_e).__name__, _e)
        if B2 is not None:
            ECU.cue(B2, _l2, _bonus, payload=_pl_bonus)
    finally:
        ECU.CUE_NAMES = _saved_names
    # ★ 判据要在**还原之前**跑：`_want()` 会现读 `BT.slots()[_bonus]`，
    #   而现造的那一格在 finally 里就被摘掉了（从前这一支靠「文案表里多出来的备用格」，
    #   现在没有备用格 ⇒ 顺序错了就是 KeyError）。
    _bus2 = ECU.cue_of(B2) if B2 is not None else None
    chk("★ ⑥ 引擎声明里多一条**真** cue（`%s`，文案表有那一格）⇒ 本包自动跟上、构造不抛"
        % _bonus,
        _bus2 is not None and bool(_bus2.subs_of(_bonus)),
        "构造回执：%s" % (_b2_err or ("总线带它 = %s" % bool(_bus2 is not None),)))
    chk("★ ⑥ 且真发得出那一行（逐字节 == 文案表那一格）",
        bool(_l2) and _l2[0] == _want(_bonus, _pl_bonus), "实得 %r" % (_l2,))
finally:
    _rules_raw["slots"].pop(_BONUS, None)
    _tx_raw.pop(_BONUS_SLOT, None)
    TX.pop(_BONUS_SLOT, None)
    BT._CACHE.pop("table", None)

# ══════════════════════════════════════════════════════════════
# ⑦ 反证：订阅表少一条 / 多一条引擎不认的 ⇒ 装配期对账当场抛
# ══════════════════════════════════════════════════════════════
print("⑦ 反证：引擎那一头的装配期对账有牙（缺订阅 / 多订阅各抛一次）")
_saved_hook = CFG._HOOKS["cue_subs_fn"]
try:
    CFG._HOOKS["cue_subs_fn"] = lambda: {k: v for k, v in CU.cue_subs().items() if k != _drop}
    _r4 = _raise_of(_build)
    CFG._HOOKS["cue_subs_fn"] = lambda: dict(CU.cue_subs(),
                                             **{"battle.cue.bogus": ({"kind": "text",
                                                                      "key": "battle.cue.bogus"},)})
    _r5 = _raise_of(_build)
finally:
    CFG._HOOKS["cue_subs_fn"] = _saved_hook
chk("⑦ 订阅表删掉一条 ⇒ 构造 Battle 必抛（缺订阅 = 玩家会少一行）",
    bool(_r4) and _drop in _r4, (_r4 or "（没抛）")[:110])
chk("⑦ 订阅表多一条引擎不认的名字 ⇒ 也必抛（拼写漂移当场现形）",
    bool(_r5) and "battle.cue.bogus" in _r5, (_r5 or "（没抛）")[:110])
chk("⑦ 装回去 ⇒ 又绿（两态）", _raise_of(_build) is None)

# ══════════════════════════════════════════════════════════════
# ⑧ 反证（运行期）：表里那条 key 没了 ⇒ 可读坏数据 + diagnostics（不静默丢行）
# ══════════════════════════════════════════════════════════════
print("⑧ 反证（运行期）：这场战斗正用的表里那条 key 没了 ⇒ 不静默、不回落、结算不改")
_k = _ORIGINAL[1]                                     # element_immune：真触发里最稳的那条
_tbl = _REAL_BUS.table                                # ★ 总线手里那张（⑤ 清过缓存，别拿新的）
chk("⑧ 夹具前提：要动的那张表就是这场战斗正用的（`总线.table is B.text`）", _tbl is B.text)
_specs = _tbl._specs                                  # noqa: SLF001 —— 夹具动内部记账，跑完还原
_saved_spec = _specs.pop(_k)
_before = len(getattr(B, "diagnostics", None) or [])
_l3: list = []
_t3 = {"name": "试桩", "level": 1, "hp": 50, "effects": {}, "element_immune": ["fire"]}
_got3 = None
try:
    with _fx({"dodge": 0.0}, 1.0):
        _got3 = LD.deal_damage(B, None, _t3, 50, _l3, element="fire")
finally:
    _specs[_k] = _saved_spec
_diag = list(getattr(B, "diagnostics", None) or [])[_before:]
chk("⑧ key 没了 ⇒ **不静默丢行**：出的是一行可读的坏数据（⚠️，引擎自己写的）",
    len(_l3) == 1 and "⚠️" in str(_l3[0]), "实得 %r" % (_l3,))
chk("★ ⑧ 那一行**不是**文案表那句（没命中就现形，绝不替内容侧编一句）",
    bool(_l3) and _l3[0] != _want(_k, _SPY.sent.get(_k, {"name": "试桩", "element": "fire"})),
    "坏数据 %r" % (_l3[:1],))
chk("⑧ 进了 `battle.diagnostics`（stage 带 cue）—— 缺口不许只留在屏上",
    any("cue" in str(d.get("stage", "")) for d in _diag),
    "%s" % ([d.get("stage") for d in _diag],))
chk("★ ⑧ 结算一个字不改：表里没这格、免疫**照样**归 0、血量一点没掉",
    _got3 == 0 and _t3.get("hp") == 50, "回执 %r / hp %r" % (_got3, _t3.get("hp")))
chk("⑧ 表还原 ⇒ 同一处又逐字回到文案表那一条（两态）", _emit(_k)[0][0] == _want(
    _k, _SPY.sent.get(_k, {})))

print("⑧b 表坏到「一渲染就抛」同理：可读坏数据 + diagnostics，结算不改")
_before = len(getattr(B, "diagnostics", None) or [])
_l5: list = []
_got5 = None
_t5 = {"name": "试桩", "level": 1, "hp": 50, "effects": {}, "element_immune": ["fire"]}


def _boom(key, default, /, **slots):
    raise RuntimeError("探针故意把文案表弄坏（这一档测的就是「表坏了会怎样」）")


_tbl.render_or = _boom
try:
    with _fx({"dodge": 0.0}, 1.0):
        _got5 = LD.deal_damage(B, None, _t5, 50, _l5, element="fire")
finally:
    del _tbl.render_or                      # 实例属性删掉 ⇒ 回到类方法
_diag5 = list(getattr(B, "diagnostics", None) or [])[_before:]
chk("⑧b 渲染就抛 ⇒ 一行可读坏数据（⚠️）+ 进 diagnostics，不静默丢行",
    len(_l5) == 1 and "⚠️" in str(_l5[0]) and bool(_diag5),
    "行 %r / 诊断 %s" % (_l5, [d.get("stage") for d in _diag5]))
chk("★ ⑧b 结算一个字不改：免疫照样归 0、血量一点没掉",
    _got5 == 0 and _t5.get("hp") == 50, "回执 %r / hp %r" % (_got5, _t5.get("hp")))
chk("⑧b 还原 ⇒ 又绿（两态）", _emit(_k)[0][0] == _want(_k, _SPY.sent.get(_k, {})))

# ══════════════════════════════════════════════════════════════
# 收尾
# ══════════════════════════════════════════════════════════════
B.cues = _REAL_BUS
print()
print("  · 引擎声明 %d 条 cue；本包槽位映射（现算）：%s"
      % (len(_engine_names), " · ".join("%s → %s" % (n, BT.slots()[n]) for n in _engine_names)))
print("  结果：%s（失败 %d 条）" % ("全绿 ✓" if not failures else "有红 ✗", len(failures)))
if failures:
    for _f in failures:
        print("  ✗ %s" % _f)
    sys.exit(1)
sys.exit(0)
