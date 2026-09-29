# -*- coding: utf-8 -*-
"""探针：战斗 / 掉落 / 强化 —— 真人试玩那一批缺陷（第 45 支 · 本波 f4）。

来源：四个真人玩家试玩报告
  · P1 BUG-8  满血 `使用 伤药` 照样把药吃掉，只回「生命 +0」
  · P2 体验   `自动` 在没敌人时回场景口吻的「这一带暂时没有遇到什么」
  · P3 BUG-1  掉落种子 = uid+怪 id（不含次数/日期）⇒ 同一只怪对同一个人**永远掉同一件**
  · P3 BUG-2  `强化` 没有地点门禁 —— 野外骨田敲它照样报价（同批 `铁匠铺` 却拦）
  · P3 BUG-3  词条精英（`† 群居的田鼠 †`，3 只）奖励与打 1 只普通怪一字不差 ⇒ 精英纯亏
  · P3 BUG-4  打到的装备不能卖（`旧货` 回「这东西没价」）⇒ 多余装备只能占背包
  · P1 BUG-9 ① / P4 E-11  `帮助` 把十条战斗词平铺列出，读起来像逐回合出招 —— 实际一敲就是一场

判据（每条都带**两态 / 反证**，不许永真）
  ① 掉落种子含「这一只的第几次」
     1a 两态对照：老式子 `uid:怪id` 在 8 个次数上**全同结果**（= 病根）· 新式子至少 2 种
     1b 真跑 20 场：`flags.drops_seen[怪]` 逐场 +1 · 掉落序列 ≥2 种 · **强化要的「硬骨」刷得出来**
     1c 静态：`content/cmds_battle.py` 里老种子字面量没了、`drops_seen` 在
  ② 强化地点门禁：野外 / 镇上错站 / 站对了 —— 三档真敲 + 档逐字不动
     2b 反证：`enhance` 里**真调** `town_gate`（ast 扫）+ 那一站从 `npcs.funcs` 现取
  ③ 精英奖励：`reward_of` 三档（空词条全 1 · 有词条读表 · 表缺 ⇒ 抛）· 真跑同种子两臂逐数对账
     3b 反证：病根在 `role_key` —— 田鼠的 `role_key == normal` ⇒ 光靠它永远给不出精英加成
  ④ 满血不吃药：满血档 ⇒ 药一件没少 · 档一个字不动；半血档 ⇒ 药真扣、血真回
     4b 静态：那一行在 `_take` **之前**
  ⑤ 装备卖出价：真卖一件 · 逐件对账（带 slot 的都有价 · 不带的仍 0）· 量级（低于一瓶药）
     5b 反证：拿掉 `sell_gear` 那一块 ⇒ **抛**（fail-closed，不静默按 0 算）；老路给的是 0
  ⑥ `自动` 没敌人：回战斗族那一句（与 `打断`/`防御` 同一句）· `攻击` 那一句**一个字没动**
  ⑦ `帮助` 尾巴那句诚实说明：真敲出来的末行逐字 == 槽位渲染 · **不多带来一个『』词**

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_fix4_combat.py
"""
from __future__ import annotations

import ast
import io
import json
import os
import re
import sys

ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ENGINE)
sys.path.insert(0, REPO)

from saintess_engine.package import load_stack                       # noqa: E402
from saintess_engine.host.runtime import Host                        # noqa: E402

NL = chr(10)
TOWN = "windmill_town"
FIXED = 1790308800          # 2026-09-25 12:00 +08:00（与 probe_shop / probe_cmds 同一根假钟）
UID = "u_f4_probe"
GID = "g_f4_probe"
MID = "ms_field_mouse"      # 田鼠（lv 3 · role_key normal · drops = dp_trash_small）
MOUSE_LV = 3

OK, BAD = [], []


def ok(msg):
    OK.append(msg)
    print("  OK  %s" % msg)


def bad(msg):
    BAD.append(msg)
    print("  X   %s" % msg)


def chk(label, cond, extra=""):
    (ok if cond else bad)(label + (("  —— %s" % extra) if extra else ""))


class Ad(object):
    """最小适配器（照 scripts/e2e_drive.py 的真宿主契约）。"""

    def __init__(self, seed=None):
        self.out = []
        self.saved = {UID: dict(seed)} if seed else {}

    def recv(self):
        return None

    def load_player(self, uid):
        return self.saved.get(uid)

    def save_player(self, uid, data):
        self.saved[uid] = dict(data) if isinstance(data, dict) else data

    def say(self, to, text):
        self.out.append(str(text))


class E(object):
    """直调 handler 的最小环境（只要 `save()`）。"""

    text = ""
    group_id = GID

    def __init__(self, text=""):
        self.text = text
        self.saved = 0

    def save(self):
        self.saved += 1


def load(rel):
    with io.open(os.path.join(REPO, rel), encoding="utf-8") as f:
        return json.load(f)


TEXTS = load("content/data/texts.json")
ITEMS = load("content/data/items.json")
NPCS = load("content/data/npcs.json")
MAPS = load("content/data/maps.json")


def T(key, **slots):
    s = TEXTS[key]["value"]
    for k, v in slots.items():
        s = s.replace("{%s}" % k, str(v))
    return s


# ── 栈装起来（`content/*` 要能 import）──────────────────────────────────
DEVDB = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_fix4.db")
st = load_stack(str(REPO), inject={"db_path": DEVDB, "clock": lambda: FIXED})
st.install()

from content import cmds_ast as CA                                   # noqa: E402
from content import cmds_battle as CBAT                              # noqa: E402
from content import cmds_recipe as CR                                # noqa: E402
from content import affix as AFFIX                                   # noqa: E402
from content import combat as CBmod                                  # noqa: E402
from content import loot as LT                                       # noqa: E402
from content import shop as SH                                       # noqa: E402
from content.town import _func_node                                  # noqa: E402

MON = load("content/data/monsters.json")
ER = load("content/rules/elite.json")
DP = load("content/data/drop_pools.json")


def drive(fn, p, uid=UID):
    out = []
    # ★ G2：战斗改**一手一推进** ⇒ 「这一场」跨指令落盘（`instance` 的「场」）——
    #   夹具要的是「从零开一场」⇒ 每一拍之前先清掉那一格（`_E` 没有群 ⇒ 键 = `#uid`）。
    try:
        from content import instance as _INST
        _INST.clear(_INST.key_of("", uid, [uid]))
    except Exception:                                            # noqa: BLE001
        pass

    async def _go():
        async for line in fn(E(), None, uid, p):
            out.append(str(line))

    import asyncio
    asyncio.run(_go())
    return out


def _snap_ad(ad, uid=UID):
    return json.dumps(ad.saved.get(uid) or {}, ensure_ascii=False, sort_keys=True)


print("探针：战斗 / 掉落 / 强化（本波 f4 · 试玩缺陷那六条）")

# ══════════════════════════════════════════════════════════════
# ① 掉落种子：含「这一只的第几次」（P3 BUG-1）
# ══════════════════════════════════════════════════════════════
print(NL + "① 掉落种子含次数（P3 BUG-1）")
_pool = (MON[MID].get("drops") or [""])[0]
_pool = _pool if _pool else "dp_trash_small"


def _roll(seed, pool_id=None):
    import random
    r = LT.roll_pool(pool_id or _pool, level=1, rnd=random.Random(seed))
    return [(d["id"], int(d.get("n", 1))) for d in r]


# 1a 两态对照：老式子（uid + 怪 id，不含次数）在 8 个次数上全同结果 —— 这就是病根
_old = [_roll("%s:%s" % (UID, MID)) for _ in range(8)]
_new = [_roll("%s:%s:%d:0" % (UID, MID, n)) for n in range(8)]
chk("★ 1a 两态对照：老种子 `uid:怪id`（不含次数）8 次全同（%s）· 新种子 `uid:怪id:第几次:轮` "
    "出得来 %d 种 —— 病根（P3 BUG-1）与修法都当场看得见"
    % (_old[0], len(set(map(str, _new)))),
    len(set(map(str, _old))) == 1 and len(set(map(str, _new))) >= 2,
    "老 %d 种 / 新 %d 种" % (len(set(map(str, _old))), len(set(map(str, _new)))))

# 1b 真跑 20 场（同一个人 · 同一只怪）—— 掉落序列真会变，且「硬骨」刷得出来
_p = dict(CA.DEFAULT_PLAYER)
_p.update({"cls": "cls_knight", "level": 20, "hp": 9999, "gold": 0, "exp": 0,
           "loc": "belt_north", "node": "bn_bone", "bag": {}, "codex": {}, "flags": {}})
_real_pick, _real_elite = CBmod.pick_encounter, AFFIX.elite_of
CBmod.pick_encounter = lambda *a, **k: [MID]
AFFIX.elite_of = lambda *a, **k: None
_seen, _seq = [], []
try:
    for _i in range(20):
        _bag0 = dict(_p.get("bag") or {})
        # ★ G2（2026-09-26 · 本波）：战斗改成**一手一推进**之后，一条 `攻击` 只推一手
        #   ⇒ 这一节要的是「一场的落账」，夹具改走 `自动`（**一次打完**那条，落账同一个口）。
        #   判据一个字没动（drops_seen 逐场 +1 · 掉落序列 ≥2 种 · 硬骨刷得出来）。
        drive(CBAT.auto_battle, _p, uid="u_f4_drop")
        _got = {k: int(v) - int(_bag0.get(k, 0)) for k, v in (_p.get("bag") or {}).items()
                if int(v) - int(_bag0.get(k, 0)) > 0}
        _seq.append(tuple(sorted(_got)))
        _seen.append(int((( _p.get("flags") or {}).get("drops_seen") or {}).get(MID) or 0))
finally:
    CBmod.pick_encounter, AFFIX.elite_of = _real_pick, _real_elite
_dist = len(set(_seq))
_hard = "i_material_hard_bone"
_hard_n = int((_p.get("bag") or {}).get(_hard) or 0)
chk("★ 1b 真跑 20 场（同人同怪）：`flags.drops_seen[%s]` 走到 %d（逐场 +1 · 落档了）"
    % (MID, _seen[-1]), _seen == list(range(1, 21)), "seen=%s" % (_seen[:4] + ["…", _seen[-1]]))
chk("★ 1b 掉落序列真的有 %d 种（老种子必是 1 种 —— 见 1a）" % _dist, _dist >= 2,
    "前 4 场：%s" % (_seq[:4],))
chk("★ 1b 强化要的「硬骨」真刷得出来（20 场里到手 %d 个 · 权重 %s/%s）"
    % (_hard_n,
       [e.get("w") for e in (DP.get(_pool) or {}).get("entries") or [] if e.get("out") == _hard],
       sum(int(e.get("w", 1) or 1) for e in (DP.get(_pool) or {}).get("entries") or [])),
    _hard_n >= 1,
    "背包=%s" % (_p.get("bag") or {}))

# 1c 静态：老种子字面量没了 · 计数格在
_src_cb = io.open(os.path.join(REPO, "content", "cmds_battle.py"), encoding="utf-8").read()
chk("★ 1c 静态：老种子 `%s:%s`（uid+怪 id）那个字面量不在 `cmds_battle.py` 里了 · "
    "`drops_seen` 这个计数格在" % ("%s", "%s"),
    ('Random("%s:%s" % (uid, pick[0]))' not in _src_cb) and '"drops_seen"' in _src_cb,
    "老式子还在=%s · drops_seen=%s"
    % ('Random("%s:%s" % (uid, pick[0]))' in _src_cb, '"drops_seen"' in _src_cb))

# ══════════════════════════════════════════════════════════════
# ② 强化地点门禁（P3 BUG-2）—— 真宿主三档
# ══════════════════════════════════════════════════════════════
print(NL + "② 强化地点门禁（P3 BUG-2）")
db = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_fix4_host.db")
try:
    os.remove(db)
except OSError:
    pass

STEP1 = load("content/data/recipes.json")["rc_enh_01"]
MATS = {e["id"]: int(e["n"]) for e in (STEP1.get("inputs") or [])}
FEE = int(STEP1.get("gold") or 0)
WEAPON = sorted(k for k, v in ITEMS.items() if v.get("slot") == "weapon")[0]
WNAME = str(ITEMS[WEAPON].get("name"))
SMITH_NODE = _func_node("smith")
SMITH_NAME = next((n.get("name") for n in MAPS[TOWN]["nodes"] if n.get("id") == SMITH_NODE), "")
seed = {"cls": "cls_knight", "race": "race_human", "name": "试锻者", "level": 10, "exp": 0,
        "gold": FEE + 5, "hp": 200, "prev": [], "bag": dict({WEAPON: 1}, **MATS),
        "equipped": {}, "codex": {}, "flags": {}, "loc": TOWN, "node": "wt_gate_n"}
ad = Ad(seed)
host = Host(ad, REPO, inject={"db_path": db, "clock": lambda: FIXED})
host.boot()


def say(text, uid=UID):
    ad.out = []
    host.handle({"uid": uid, "group_id": GID, "text": text})
    return list(ad.out)


def stand(loc, node):
    ad.saved[UID]["loc"] = loc
    ad.saved[UID]["node"] = node


chk("② 那一站从域里现取（`npcs.funcs` 带 smith 的人所在节点）：%s「%s」"
    % (SMITH_NODE, SMITH_NAME), bool(SMITH_NODE) and bool(SMITH_NAME))

_b0 = None
stand("belt_north", "bn_bone")
_b0 = _snap_ad(ad)
_f1 = say("强化 %s" % WNAME)
_f2 = say("强化")
_fs = _snap_ad(ad)
chk("★ ②-a 野外（骨田）敲 `强化 <装备>` ⇒ == 同族那句「这几处都在镇上」· `强化`（空参·报价表）同 · "
    "**档一个字不动**",
    _f1 == [T("SYS_PLACE_NOTOWN")] and _f2 == [T("SYS_PLACE_NOTOWN")] and _fs == _b0,
    "装备那一下 %s · 空参 %s" % (_f1[:1], _f2[:1]))

stand(TOWN, "wt_gate_n")
_b0 = _snap_ad(ad)
_g1 = say("强化 %s" % WNAME)
_gs = _snap_ad(ad)
chk("★ ②-b 站在镇上**别的站**（北口）⇒ 指路（站名从 maps 现取：「%s」）且档不动" % SMITH_NAME,
    _g1 == [T("SYS_PLACE_AWAY", name=SMITH_NAME)] and _gs == _b0,
    "回的是 %s" % (_g1[:1],))

stand(TOWN, SMITH_NODE)
_h1 = say("强化 %s" % WNAME)
chk("★ ②-c 站到「%s」⇒ 不再拦（这一档材料够 ⇒ 真强化，回 %s）"
    % (SMITH_NAME, "SYS_ENHANCE_OK" if _h1 and "强化" not in _h1[1] else _h1[0][:14]),
    bool(_h1) and _h1[0] != T("SYS_PLACE_NOTOWN")
    and not _h1[0] == T("SYS_PLACE_AWAY", name=SMITH_NAME),
    "回的是 %s" % (_h1[:1],))

# ② 反证（静态）：`enhance` 里真调 town_gate · 那一站不是手写的
_tree = ast.parse(io.open(os.path.join(REPO, "content", "cmds_recipe.py"), encoding="utf-8").read())


def _calls(name):
    for n in ast.walk(_tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return [getattr(x.func, "id", "") for x in ast.walk(n) if isinstance(x, ast.Call)]
    return []


_cr = _calls("enhance")
chk("★ ② 反证（静态）：`cmds_recipe.enhance` 真调 `town_gate`（并让 `smith` 那一站现取）—— "
    "把这行删掉 ②-a/②-b 当场红",
    "town_gate" in _cr and "_func_node" in _cr, "enhance 里调了：%s" % sorted(set(_cr)))

# ② 登记（**不硬锁**）：声明侧那一格还停在「有材料」——与真源 `04 §七` 那一行逐字一致；
#   真源把它改成「在铁匠铺且材料够」之后，跟着改 `commands.json::enhance.guard_desc`
#   并把它数进 `probe_cmds ⑰` 的地点覆盖面（`_LOCWORDS17` 那一族）。
#   —— 与 `probe_shop ⑯` 对 `05 §七` 那行的做法同一个形状：这里只**打印**跟账状态。
_ed = load("content/data/commands.json")
_gd_enh = str((_ed.get("enhance") or {}).get("guard_desc") or "")
_gd_smith = str((_ed.get("smith") or {}).get("guard_desc") or "")
print("  · 登记（P3 BUG-2）：声明侧 `enhance.guard_desc` = 「%s」（`smith` = 「%s」）—— "
      "实现侧已经要求「在铁匠铺那一站」；真源 `04 §七` 那一行改成「在铁匠铺且材料够」之后，"
      "跟着改这一格（本波只登记 · 跟账见本分支 `_notes.md §一·5`）" % (_gd_enh, _gd_smith))

# ══════════════════════════════════════════════════════════════
# ③ 精英奖励（P3 BUG-3）
# ══════════════════════════════════════════════════════════════
print(NL + "③ 精英奖励（P3 BUG-3）")
_rw = ER.get("reward") or {}
chk("③ 三档：没词条 ⇒ 全 1（与接线前逐字相同）" ,
    AFFIX.reward_of([]) == {"gold_mult": 1.0, "exp_mult": 1.0, "drop_rounds": 1})
chk("③ 有词条 ⇒ 读 `rules/elite.json::reward`（钱 ×%s · 经验 ×%s · 掉落 %s 轮）"
    % (_rw.get("gold_mult"), _rw.get("exp_mult"), _rw.get("drop_rounds")),
    AFFIX.reward_of(["af_swarm"]) == {"gold_mult": float(_rw["gold_mult"]),
                                      "exp_mult": float(_rw["exp_mult"]),
                                      "drop_rounds": int(_rw["drop_rounds"])})
# 反证：表缺那一块 ⇒ 抛（不许静默按 1 算 —— 那等于精英纯亏又回来了）
_erd = AFFIX.rules()
_saved_rw = _erd.pop("reward")
try:
    _threw = False
    try:
        AFFIX.reward_of(["af_swarm"])
    except Exception:                                                   # noqa: BLE001
        _threw = True
finally:
    _erd["reward"] = _saved_rw
chk("★ ③ 反证：拿掉表里那一块 ⇒ **抛**（fail-closed —— 不静默退成 ×1 把精英纯亏放回来）", _threw)

# 3b 真跑两臂：同一 uid / 同一只怪 / 同一颗种子 —— 只有「有没有词条」这一个变量
def _one_battle(aids, uid="u_f4_elite", p_in=None):
    q = dict(CA.DEFAULT_PLAYER)
    q.update({"cls": "cls_knight", "level": 20, "hp": 9999, "gold": 0, "exp": 0,
              "loc": "belt_north", "node": "bn_bone", "bag": {}, "codex": {}, "flags": {}})
    if p_in is not None:
        q = p_in
    _bag0 = dict(q.get("bag") or {})
    _rp, _re = CBmod.pick_encounter, AFFIX.elite_of
    CBmod.pick_encounter = lambda *a, **k: [MID]
    AFFIX.elite_of = (lambda *a, **k: (MID, list(aids))) if aids else (lambda *a, **k: None)
    try:
        # ★ G2：一条 `攻击` 只推一手 ⇒ 这一节的「一场对照」改走 `自动`（一次打完，落账同口）
        lines = drive(CBAT.auto_battle, q, uid=uid)
    finally:
        CBmod.pick_encounter, AFFIX.elite_of = _rp, _re
    _got = tuple(sorted(k for k, v in (q.get("bag") or {}).items()
                        if int(v) - int(_bag0.get(k, 0)) > 0))
    return q, lines, _got


_pq, _plain_lines, _plain_drop = _one_battle(None)
_eq, _elite_lines, _elite_drop = _one_battle(["af_swarm"])
_elite_q = dict(CA.DEFAULT_PLAYER)
_elite_q.update({"cls": "cls_knight", "level": 20, "hp": 9999, "gold": 0, "exp": 0,
                 "loc": "belt_north", "node": "bn_bone", "bag": {}, "codex": {}, "flags": {}})
_elite_seq = []
for _i in range(8):
    _b0e = dict(_elite_q.get("bag") or {})
    _one_battle(["af_swarm"], uid="u_f4_elite_multi", p_in=_elite_q)
    _elite_seq.append(tuple(sorted(k for k, v in (_elite_q.get("bag") or {}).items()
                                   if int(v) - int(_b0e.get(k, 0)) > 0)))
_lv = int(MON[MID].get("lv", 1))
_rk = MON[MID].get("role_key")
_g_plain = int(round(float(_lv * (8 if _rk == "elite" else (20 if _rk in ("chief", "warden", "boss") else 3)))))
_x_plain = int(CA.exp_of_kill(_lv))
chk("★ 3b 真跑对照（同 uid / 同怪 / 只差有没有词条）：普通 钱 +%d 经验 +%d ⇒ 精英 钱 +%d 经验 +%d"
    "（= 普通 ×%s / ×%s，逐数对账）"
    % (_g_plain, _x_plain, int(_eq.get("gold") or 0), int(_eq.get("exp") or 0),
       _rw.get("gold_mult"), _rw.get("exp_mult")),
    int(_pq.get("gold") or 0) == _g_plain and int(_pq.get("exp") or 0) == _x_plain
    and int(_eq.get("gold") or 0) == int(round(_g_plain * float(_rw["gold_mult"])))
    and int(_eq.get("exp") or 0) == int(round(_x_plain * float(_rw["exp_mult"]))),
    "普通 %s/%s · 精英 %s/%s" % (_pq.get("gold"), _pq.get("exp"), _eq.get("gold"), _eq.get("exp")))
chk("★ 3b 精英那一场「掉落多一轮」（表：%s 轮）：真跑 8 场，其中 %d 场掉出**一件以上不重样**"
    "（同种子两轮各一份种子 —— 一轮的话永远只有 1 件）"
    % (_rw.get("drop_rounds"),
       sum(1 for _s in _elite_seq if len(_s) >= 2)),
    int(_rw["drop_rounds"]) == 2 and int(AFFIX.reward_of([])["drop_rounds"]) == 1
    and any(len(_s) >= 2 for _s in _elite_seq),
    "8 场里每场的件数：%s" % [len(_s) for _s in _elite_seq])
# 3b 反证：病根在 `role_key` —— 田鼠的 role_key 不是 elite ⇒ 光靠它永远给不出精英加成
chk("★ 3b 反证（病根）：被词条精英化的基础怪 `%s` 的 `role_key` = %r（**不是** elite）"
    "⇒ 原来那条「比 role_key」的路对它**永远不触发**（钱/经验恒按普通算）"
    % (MID, _rk), _rk != "elite")

# 3c 覆盖面（静态 · ast）：`_settle` 的**每一个**调用点都把词条透进去 ——
#    原先 `后撤`（退不开那一支）与 `逃跑`（被拦下那一支）漏了 `affixes=`：
#    同一场精英怪，从「攻击」进去有加成、从「后撤」进去没有（同一条命两种价）。
_bat_tree = ast.parse(io.open(os.path.join(REPO, "content", "cmds_battle.py"),
                             encoding="utf-8").read())
_settle_calls, _settle_noaf = 0, []
for _n in ast.walk(_bat_tree):
    if isinstance(_n, ast.Call) and getattr(_n.func, "id", "") == "_settle":
        _settle_calls += 1
        if not any(k.arg == "affixes" for k in _n.keywords):
            _settle_noaf.append(getattr(_n, "lineno", 0))
chk("★ 3c 覆盖面（静态）：`_settle` 的 %d 个调用点**全都**把 `affixes=` 透进去"
    "（漏的那几处 = 同一场精英怪两种价：攻击有加成、后撤/逃跑没有）"
    % _settle_calls,
    _settle_calls >= 4 and not _settle_noaf,
    "漏的调用点行号：%s" % (_settle_noaf or "无"))

# ══════════════════════════════════════════════════════════════
# ④ 满血不吃药（P1 BUG-8）
# ══════════════════════════════════════════════════════════════
print(NL + "④ 满血不吃药（P1 BUG-8）")
POT = "i_potion_minor"
POTNAME = str(ITEMS[POT].get("name"))
_mx_p = CA.hp_cap({"cls": "cls_knight", "level": 10})
_gain0 = CR._heal_gain({"cls": "cls_knight", "level": 10}, ITEMS[POT], _mx_p)

stand(TOWN, "wt_gate_n")
ad.saved[UID]["cls"] = "cls_knight"
ad.saved[UID]["level"] = 10
ad.saved[UID]["hp"] = _mx_p
ad.saved[UID]["bag"] = {POT: 2}
_b4 = _snap_ad(ad)
_l_full = say("使用 %s" % POTNAME)
_a4 = _snap_ad(ad)
chk("★ ④-a 满血（%d/%d）敲 `使用 %s` ⇒ 回「%s」· **药一件没少**（还是 2 个）· 档逐字不动"
    % (_mx_p, _mx_p, POTNAME, T("SYS_USE_FULL", name=POTNAME)),
    _l_full == [T("SYS_USE_FULL", name=POTNAME)]
    and int((ad.saved[UID].get("bag") or {}).get(POT) or 0) == 2
    and ad.saved[UID].get("hp") == _mx_p
    and _a4 == _b4,
    "回话 %s · bag %s · hp %s" % (_l_full[:1], ad.saved[UID].get("bag"), ad.saved[UID].get("hp")))

ad.saved[UID]["hp"] = max(1, _mx_p // 2)
ad.saved[UID]["bag"] = {POT: 2}
_l_hurt = say("使用 %s" % POTNAME)
_hp_now = int(ad.saved[UID].get("hp") or 0)
_lost = int((ad.saved[UID].get("bag") or {}).get(POT) or 0)
chk("★ ④-b 两态对照（半血 %d/%d）⇒ 药**真扣**（2 → %d）· 血真回（→ %d，= +%s）"
    % (max(1, _mx_p // 2), _mx_p, _lost, _hp_now, _gain0),
    _lost == 1 and _hp_now == min(_mx_p, max(1, _mx_p // 2) + int(_gain0)),
    "回话 %s" % (_l_hurt[:1],))

_src_cr = io.open(os.path.join(REPO, "content", "cmds_recipe.py"), encoding="utf-8").read()
_i_full = _src_cr.find('T("SYS_USE_FULL"')
_i_take = _src_cr.find("_take(p, iid, 1)", _i_full)
chk("★ ④ 反证（静态）：满血那一行在**回血那一支的** `_take(p, iid, 1)` **之前**"
    "（%d < %d —— 上一处 `_take` 是「吃东西」那一支的）—— 顺序反了药又白吃"
    % (_i_full, _i_take), 0 <= _i_full < _i_take)

# ══════════════════════════════════════════════════════════════
# ⑤ 装备卖出价（P3 BUG-4）
# ══════════════════════════════════════════════════════════════
print(NL + "⑤ 装备卖出价（P3 BUG-4）")
GEAR = sorted(k for k, v in ITEMS.items() if v.get("slot"))
NONGEAR_NOPRICE = sorted(k for k, v in ITEMS.items()
                         if not v.get("slot") and not v.get("price"))
_prices = {k: SH.sell_price_of(ITEMS[k]) for k in GEAR}
chk("★ ⑤ 逐件对账：域里 %d 件装备**每件都算得出收价 > 0**（%d..%d 铜板）· 不在收价表里的品阶当场抛"
    % (len(GEAR), min(_prices.values()), max(_prices.values())),
    all(v > 0 for v in _prices.values()),
    "档位 %s" % sorted(set(_prices.values())))
chk("⑤ 不是装备又没价的（%d 件：%s）⇒ 收价 0 = 不收（不编一口价）"
    % (len(NONGEAR_NOPRICE), " · ".join(NONGEAR_NOPRICE[:3])),
    all(SH.sell_price_of(ITEMS[k]) == 0 for k in NONGEAR_NOPRICE),
    "%s" % {k: SH.sell_price_of(ITEMS[k]) for k in NONGEAR_NOPRICE[:6]})
_pot_buy = int(round(float(ITEMS["i_potion_minor"]["price"]) * 2))     # 药铺那一格：收价 × 加价 2
_cheapest = min(SH.sell_price_of(ITEMS[k]) for k in GEAR
                if not ((ITEMS[k].get("req") or {}).get("level")))
chk("⑤ 量级（真源 `05 §七`「不靠卖装备」）：最便宜的那一档装备收价 %d 铜板 < 一瓶伤药买价 %d —— "
    "装备能变现、但绝不成钱的来源" % (_cheapest, _pot_buy), _cheapest < _pot_buy)

SHORT = "i_set_scavenger_blade"
SNAME = str(ITEMS[SHORT].get("name"))
_ad_p = SH.sell_price_of(ITEMS[SHORT])
stand(TOWN, "wt_gate_n")
ad.saved[UID]["bag"] = {SHORT: 2}
ad.saved[UID]["gold"] = 100
ad.saved[UID]["hp"] = 100
_l_sell = say("卖出 %s" % SNAME)
chk("★ ⑤ 真卖一件 `%s`（精制 · 无穿戴门槛）：到手 %d 铜板 · 背包 2 → %s · 档上钱 %d → %s"
    % (SNAME, _ad_p, int((ad.saved[UID].get("bag") or {}).get(SHORT) or 0),
       int(ad.saved[UID].get("gold") or 0), int(ad.saved[UID].get("gold") or 0)),
    _l_sell == [T("SYS_SELL_OK", icon=ITEMS[SHORT].get("icon") or "", name=SNAME,
                  n=1, gold=_ad_p)]
    and int((ad.saved[UID].get("bag") or {}).get(SHORT) or 0) == 1
    and int(ad.saved[UID].get("gold") or 0) == 100 + _ad_p,
    "回话 %s · bag %s · gold %s" % (_l_sell[:1], ad.saved[UID].get("bag"),
                                    ad.saved[UID].get("gold")))
# 5b 反证：拿掉 `sell_gear` 那一块 ⇒ 抛（不是静默按 0 算）· 老路（`items.price`）给的是 0
_rec = ITEMS[SHORT]
chk("★ 5b 反证（病根）：域里那件装备 `price` 一栏 = %r ⇒ 老口径（域里有价才收）算出来是 **0** = 不收"
    % (_rec.get("price"),), int(_rec.get("price") or 0) == 0,
    "price=%r" % (_rec.get("price"),))
_sr = SH.rules()
_saved_sg = _sr.pop("sell_gear")
try:
    _threw5 = False
    try:
        SH.sell_price_of(_rec)
    except Exception:                                                   # noqa: BLE001
        _threw5 = True
finally:
    _sr["sell_gear"] = _saved_sg
chk("★ 5b 拿掉 `sell_gear` 那一块 ⇒ **抛**（fail-closed：不静默按 0 卖、也不编一口价）", _threw5)
_rd = [f for f in sorted(os.listdir(os.path.join(REPO, "content")))
       if f.endswith(".py")
       and "sell_gear" in io.open(os.path.join(REPO, "content", f), encoding="utf-8").read()]
chk("★ 5b 静态：读那张表的地方只有 `content/shop.py` 一处（收价一个口 —— 『卖出』『旧货』共用）",
    _rd == ["shop.py"], "读它的：%s" % _rd)

# ══════════════════════════════════════════════════════════════
# ⑥ `自动` 没敌人那一句（P2 体验）
# ══════════════════════════════════════════════════════════════
print(NL + "⑥ `自动` 没敌人那一句（P2 体验）")
stand(TOWN, "wt_gate_n")                       # 镇上 = 安全区（`habitat` 里一只都挑不出来）
ad.saved[UID]["cls"] = "cls_knight"
ad.saved[UID]["level"] = 10
ad.saved[UID]["hp"] = 100
ad.saved[UID]["bag"] = {}
_l_auto = say("自动")
_l_atk = say("攻击")
_l_int = say("打断")
chk("★ ⑥ 镇上（没得打）敲 `自动` ⇒ 回**战斗族那一句**（与 `打断` 同一句），不再是场景口吻的"
    "「%s」" % T("COMBAT_NONE"),
    _l_auto == [T("COMBAT_NEED_FOE")] and _l_int == [T("COMBAT_NEED_FOE")],
    "自动 %s · 打断 %s" % (_l_auto[:1], _l_int[:1]))
chk("★ ⑥ 两态对照：`攻击` 在同一处**一个字没动**（照旧回场景口吻那一句）",
    _l_atk == [T("COMBAT_NONE")], "攻击 %s" % (_l_atk[:1],))

# ══════════════════════════════════════════════════════════════
# ⑦ `帮助` 尾巴那句诚实说明（P1 BUG-9 ① / P4 E-11）
# ══════════════════════════════════════════════════════════════
print(NL + "⑦ `帮助` 里战斗那栏的尾巴（P1 BUG-9 ① / P4 E-11 · ★ G2 换向）")
# ★ 2026-09-30（帮助面板改造）：帮助 = 主面板 + 分类子面板；战斗那栏的尾巴在
#   『帮助 战斗』子面板里。旧槽位 SYS_HELP_BATTLE_TURN / SYS_HELP_BATTLE_NOTE 已随
#   改造退场（退役登记见 probe_copy.py::RETIRED_DOC / 帮助节）。
_l_help = say("帮助 战斗")
chk("★ ⑦ 敲 `帮助 战斗` ⇒ 尾巴说的是本波口径（「一手一手」那句在末行）",
    bool(_l_help) and "一手一手" in _l_help[-1], "末行 %s" % (_l_help[-1:] or ["（空）"]))
# ⑦-反证（『』词表与「可见 + 有处理器」逐条相等的对账）随帮助改造移交 probe_cmds ⑤
# （主面板 + 子面板 · 占位名归一后对账），此处不再重复一份镜像。

print(NL + "结果：%s" % ("全绿 ✓" if not BAD else "有红 ✗（%d 条）" % len(BAD)))
for m in BAD:
    print("   ✗ %s" % m)
sys.exit(1 if BAD else 0)
