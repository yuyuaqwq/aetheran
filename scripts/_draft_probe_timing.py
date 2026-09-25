# -*- coding: utf-8 -*-
"""探针**草案**（B4-4 · 只读设计）：技能自己声明的两段耗时 —— 现算 vs 设计值，逐条对账。

★★ 合入时（2026-09-25 · 主线）改名：`scripts/probe_timing.py` → `scripts/_draft_probe_timing.py`。
   原因：本探针 ②④ 两组是**故意红着**的（它量的是「引擎还没接」这件事），而全量门禁跑器
   是 `scripts/probe_*.py` 通配 —— 让它进闸就是「门禁带一条已知红」，违反「探针全绿才算完」。
   接线那天（引擎 `segment_plan_fn` 有调用方了）把它**改回 `probe_timing.py`** 并纳入全量门禁。
   跑它：`GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/_draft_probe_timing.py`

背景（为什么这条探针必须先红着）
------------------------------------------------------------------
引擎的耗时模型只认**动作类别**：`ext_combat/battle/schedule.py` 的
`pending_begin(cast=action)` 与 `_after_act(actor, action)` 拿到的都是字符串
（`"skill"`）⇒ 一律查 `content/rules/action_base.json`（`skill` = 80 / 50），
**技能 dict 里自己写的 `cast.base` / `recover.base` 没有任何人读**。

后果（波九 B3-27 顺带挖出，本探针把它变成可复算的断言）：
    六职业 30 条技能，**每一条**的前摇/后摇都被压成同一档 —— 真源那套
    「引燃 200 刻前摇 vs 刺客 0–160 刻打断窗口」的博弈没有地基。

本探针**不做**的事
------------------------------------------------------------------
· 不改引擎、不改内容包 —— 它只**量**：把「现算」与「设计值」并排放出来，逐条对账。
· 它**不是**说「引擎错了」：今天 `segment_plan_fn`（E5，`saintess_engine/config.py`
  的 `_HOOKS` 里已声明）**没有任何调用方** —— 接线是设计案（本分支 `_notes.md` §一）
  的事。在接线之前，本探针的 ②④ 两组**如实红着**，红的原因写在行末。

判据分五组
------------------------------------------------------------------
① 形状档（真源 → 供体）：30 条技能的 cast/recover 形状合法（`{"base": 数值 ≥ 0}`）
② 现算档（引擎真跑 · 逐条对账）：`pending_begin` 量第一段 · `_after_act` 量两段合计；
   与「技能自己那两段」经**引擎既有时间模型**算出的设计值逐条比
③ 退化档（不传技能 = 与今天逐字相同）：`entry=None` 那条路必须一个数都不动
④ 装配档：内容侧供体在不在 · **引擎有没有消费它**（今天 0 次调用 ⇒ 红）
⑤ 反证档：引擎仓零改动（只读设计的自证）· 判据只加强（红的是「没接」，不是「接了算错」）

用法（Python 用 3.12；3.11 会假红）
    GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_timing.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

REPO = str(Path(__file__).resolve().parent.parent)
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, REPO)
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402

st = load_stack(str(REPO), inject={
    "db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"),
    "clock": time.time})
st.install()

from saintess_engine import config                                   # noqa: E402
from content import combat as CMB                                     # noqa: E402
from content import panel_build as PB                                 # noqa: E402
from content import skills_lookup as SL                               # noqa: E402
from content.apply import install_engine                              # noqa: E402
from ext_combat.battle import schedule as SCH                         # noqa: E402
from ext_combat.battle import stats as ST                             # noqa: E402
from ext_combat.battle.actors import ActCtx                           # noqa: E402

install_engine()

fails: list = []


def ok(m):
    print("  \u2713 " + m)


def bad(m):
    fails.append(m)
    print("  \u2717 " + m)


SKD = st.domain("skills")
MON = st.domain("monsters")
CLS = SL.classes()
MID = "ms_field_mouse"
LV = 10

#: 类别兜底（今天口径）—— 从内容侧自己的基准表读，不写死数
CAT = "skill"


def battle_of(cls: str):
    """六职业各起一场（玩家侧走 combat.player_actor：面板栈 / 触发器都在那儿挂）。

    ★ `alloc` 必须带上：不带 = 一个点没投（真源那六份表的 10 级行是**含示例加点**的），
      spd 会掉到基础行 —— 与真源 `03_职业与技能/*_v2.md` 的「一次行动（F6）」那一列对不上。
    """
    p = {"cls": cls, "level": LV, "uid": "u_timing", "name": "计时",
         "alloc": CLS[cls].get("suggest_alloc")}
    return CMB.build(p, [MID], MON, party=1)


def measure(battle, actor, action: str, entry):
    """**真引擎**跑一次（调用点与 `Battle.act` 逐字一致：`cast=action` / `recover=None`）。

    返回 (第一段现算, 两段合计现算) —— 单位 = 游戏秒。
    """
    actor["charging"] = None
    battle._now = 0.0
    slot = SCH.pending_begin(battle, ActCtx(caster=actor, action=action,
                                            skill_name=(entry or {}).get("_key"),
                                            info=entry),
                             cast=action, recover=None)
    seg1 = float(slot["cast_done_at"]) - float(battle._now)
    actor["charging"] = None
    battle._now = 0.0
    SCH._after_act(battle, actor, action)
    total = float(actor["ct"]) - float(battle._now)
    return seg1, total


# ══════════════════════════════════════════════════════════════
print("探针：技能自己声明的两段耗时（B4-4 · 只读设计）")
print("  hook：time_model_fn=%s · recover_model_fn=%s · action_base_fn=%s · "
      "recover_base_fn=%s · **segment_plan_fn=%s**" % (
          bool(config.get_hook("time_model_fn")), bool(config.get_hook("recover_model_fn")),
          bool(config.get_hook("action_base_fn")), bool(config.get_hook("recover_base_fn")),
          bool(config.get_hook("segment_plan_fn"))))

# ── ① 形状档 ─────────────────────────────────────────────────
print()
print("── ① 形状档：30 条技能的两段声明（`{\"base\": 数值 ≥ 0}`）")
bad_shape = []
for sid, v in SKD.items():
    for key in ("cast", "recover"):
        d = v.get(key)
        if (not isinstance(d, dict)) or set(d) != {"base"} \
                or isinstance(d.get("base"), bool) or not isinstance(d.get("base"), (int, float)) \
                or float(d["base"]) < 0:
            bad_shape.append((sid, key, d))
ok("30 条技能 cast/recover 形状全合法（%d 条技能 × 2 段）" % len(SKD)) if not bad_shape \
    else bad("形状不合法的声明：%s" % (bad_shape[:4],))

# ── ② 现算档：逐条对账（引擎真跑） ─────────────────────────────
print()
print("── ② 现算档：`pending_begin` / `_after_act` 真跑 vs 技能自己那两段")
TM = config.get_hook("time_model_fn")
RM = config.get_hook("recover_model_fn")
rows = []
mismatch = []
for cls in sorted(CLS):
    b = battle_of(cls)
    caster = b.focus()
    spd = ST.actor_spd(b, caster)
    for sid, v in sorted(SKD.items()):
        if v.get("owner_class") != cls:
            continue
        entry = SL.skill_by_key(sid)
        entry["_key"] = sid
        cb, rb = float(v["cast"]["base"]), float(v["recover"]["base"])
        seg1_des, total_des = TM(spd, cb), TM(spd, cb) + RM(spd, rb)
        seg1_now, total_now = measure(b, caster, CAT, entry)
        # 类别兜底（退化口径）：同一场里不传 entry
        seg1_cat, total_cat = measure(b, caster, CAT, None)
        rows.append((cls, sid, v["name"], spd, cb, rb,
                     seg1_des, seg1_now, total_des, total_now, seg1_cat, total_cat))
        if abs(seg1_now - seg1_des) > 1e-6 or abs(total_now - total_des) > 1e-6:
            mismatch.append((sid, v["name"], total_now, total_des,
                             abs(seg1_now - seg1_des) > 1e-6,
                             abs(total_now - total_des) > 1e-6))

print("    %-11s %-16s %5s | %6s %6s | %13s %13s | %s" % (
    "职业", "技能", "spd", "cast", "recv", "第一段 设计/现算", "两段 设计/现算", "差"))
for cls, sid, name, spd, cb, rb, s1d, s1n, td, tn, s1c, tc in rows:
    _d1 = "" if abs(s1n - s1d) < 1e-6 else "第一段"
    _d2 = "" if abs(tn - td) < 1e-6 else "两段"
    _tag = "✓" if not (_d1 or _d2) else "✗ " + "+".join(x for x in (_d1, _d2) if x)
    print("    %-11s %-16s %5d | %6.0f %6.0f | %6.1f/%6.1f | %6.1f/%6.1f | %+7.1f %s" % (
        cls.replace("cls_", ""), name, spd, cb, rb, s1d, s1n, td, tn, tn - td, _tag))

bad("逐条对账：%d/%d 条「现算 ≠ 设计值」—— 技能自己的 cast/recover 没有被读 "
    "（例：%s 设计 %.1f 刻 · 现算 %.1f 刻）" % (
        len(mismatch), len(rows),
        mismatch[0][1] if mismatch else "-", mismatch[0][3] if mismatch else 0.0,
        mismatch[0][2] if mismatch else 0.0)) if mismatch \
    else ok("30 条逐条对账：现算 == 设计值（技能自己的两段真被读了）")

# ── ③ 退化档：不传技能 = 与今天逐字相同 ───────────────────────
print()
print("── ③ 退化档：`entry=None`（普攻/怪技那条路）—— 一个数都不许动")
AB, RB = config.get_hook("action_base_fn"), config.get_hook("recover_base_fn")
drift = []
for cls, sid, name, spd, cb, rb, s1d, s1n, td, tn, s1c, tc in rows:
    want1 = TM(spd, AB(CAT))
    want2 = want1 + RM(spd, RB(CAT))
    if abs(s1c - want1) > 1e-6 or abs(tc - want2) > 1e-6:
        drift.append((cls, sid, s1c, want1, tc, want2))
ok("不传技能 ⇒ 第一段 = `action_base_of('%s')`、两段 = 类别两段（30 条逐条相同）" % CAT) \
    if not drift else bad("退化口径漂了：%s" % (drift[:4],))

# ── ④ 装配档：供体在不在 · 引擎有没有消费它 ────────────────────
print()
print("── ④ 装配档：内容侧供体 + 引擎侧调用点")
plan_fn = config.get_hook("segment_plan_fn")
ok("内容侧挂上了 `segment_plan_fn`（E5 供体）") if plan_fn \
    else bad("内容侧**没挂** `segment_plan_fn` —— 设计案 §一·1.2 的接法（`content/apply.py`）"
             "未落地 ⇒ 引擎即便接了也无处问")

calls = {"n": 0}
_prev = plan_fn


def _spy(actor, action, entry):
    calls["n"] += 1
    return _prev(actor, action, entry) if _prev else None


config.mount(segment_plan_fn=_spy)
_b = battle_of("cls_mage")
_c = _b.focus()
_b._now = 0.0
SCH.pending_begin(_b, ActCtx(caster=_c, action=CAT, skill_name="SKILL_MAG_ignite",
                             info=SL.skill_by_key("SKILL_MAG_ignite")))
_b._now = 0.0
SCH._after_act(_b, _c, CAT)
ok("引擎侧**真问了** `segment_plan_fn`（%d 次）" % calls["n"]) if calls["n"] > 0 \
    else bad("引擎侧**一次都没问** `segment_plan_fn` —— 该 hook 在 `saintess_engine/config.py` "
             "的 `_HOOKS`（第 80 行）里已声明，但**全仓零调用点**（`pending_begin` / "
             "`_segment_seconds` / `_after_act` 拿到的都是类别字符串）⇒ 这正是本设计案要接的那一刀")

# ── ⑤ 反证档：零改动 · 判据只加强 ──────────────────────────────
print()
print("── ⑤ 反证档")
try:
    out = subprocess.run(["git", "-C", ENGINE, "status", "--porcelain"],
                         capture_output=True, text=True, timeout=30)
    ok("引擎仓零改动（`git status --porcelain` 空）") if not out.stdout.strip() \
        else bad("引擎仓有改动：%s" % out.stdout.strip().splitlines()[:4])
except Exception as e:                                            # pragma: no cover
    print("  · 跳过引擎仓自证（%s）" % e)

#: 这一刀只把「没接」变「接上」，不放松任何判据
hard = ("② 逐条对账", "④ 引擎侧真问了")
print("  · 本探针的红只可能来自两点：%s —— 都是「没接」，不是「接了算错」；" % " / ".join(hard))
print("    接线后这两条必须转绿，③（退化）不许动一格（判据只加强）。")

# ── ⑥ 顺带量到的缝（登记用 · 不算红） ─────────────────────────
print()
print("── ⑥ 顺带量到的缝（登记进 `_notes.md` §三·影响面，不算红）")
_b2 = battle_of("cls_knight")
_c2 = _b2.focus()
_s2 = ST.actor_spd(_b2, _c2)
_b2._now = 0.0
_c2["charging"] = None
_slot_none = SCH.pending_begin(_b2, ActCtx(caster=_c2, action="skill", skill_name="SKILL_KNT_slash",
                                           info=SL.skill_by_key("SKILL_KNT_slash")),
                               cast=None, recover=None)
_seg_skill = TM(_s2, AB("skill"))
_seg_attack = TM(_s2, AB("attack"))
print("  · `pending_begin(cast=None)` 落 `DEFAULT_ACTION`（%s %.1f 刻），**不是** docstring 写的"
      "「None = 第一段按 `ctx.action` 类别」（skill 是 %.1f 刻）—— 今天 `Battle.act` 永远显式传"
      " `cast=action`，这条缝没人踩到；**接线时若走 None 分支，得先把这个口头契约与实现对齐**" % (
          SCH.DEFAULT_ACTION, _seg_attack, _seg_skill))
assert abs(float(_slot_none["cast_done_at"]) - _seg_attack) < 1e-6, "（口径自证失败）"
print("  · 怪技（`ms_skill_*`）与普攻都不带 cast/recover ⇒ 退化档就是它们那条路（今天不变，见 ③）")

# ── ⑦ 两态对照（真源点名的那几条 · 态 A = 今天 / 态 B = 接线后） ──
print()
print("── ⑦ 两态对照（态 A = 不接 ⇒ 现算列；态 B = 接了 ⇒ 必须挪到设计列）")
for cls, sid in (("cls_mage", "SKILL_MAG_ignite"), ("cls_mage", "SKILL_MAG_fallenstar"),
                 ("cls_assassin", "SKILL_SHD_sever"), ("cls_knight", "SKILL_KNT_standfast"),
                 ("cls_ranger", "SKILL_RNG_quickstep")):
    _row = [r for r in rows if r[1] == sid][0]
    _c, _i, _name, _spd, _cb, _rb, _s1d, _s1n, _td, _tn = _row[:10]
    print("    %-8s %-6s spd=%3d | cast/base+rec/base %5s+%-5s | 态A %6.1f 刻 → 态B %6.1f 刻 | %s" % (
        _c.replace("cls_", ""), _name, _spd, ("%.0f" % _cb), ("%.0f" % _rb), _tn, _td,
        "✗ 待接线（差 %+.1f）" % (_tn - _td) if abs(_tn - _td) > 1e-6 else "✓ 已等值"))
print("    · 态 B 那一列的数值就是本设计案 §一 的判据；接线后 **表里现算列必须逐条搬到它上面**，")
print("      `entry=None`（普攻/怪技）那一列（③）一格都不许动。")

# ── 对账表（给 `_notes.md` 直接抄） ───────────────────────────
print()
print("── 对账表（30 条 · 可直抄进 `_notes.md` §二）")
print("| 技能 id | 名 | 职业 | spd | cast/recv | 第一段·设计 | 第一段·现算 | 两段·设计 | 两段·现算 | 差 |")
print("|---|---|---|---|---|---|---|---|---|---|")
for cls, sid, name, spd, cb, rb, s1d, s1n, td, tn, s1c, tc in rows:
    print("| `%s` | %s | %s | %d | %s/%s | %.1f | %.1f | %.1f | %.1f | %+.1f |" % (
        sid, name, cls.replace("cls_", ""), spd, ("%.0f" % cb), ("%.0f" % rb),
        s1d, s1n, td, tn, tn - td))

print()
print("结果：%s（%d 条红）" % ("全绿" if not fails else "有红", len(fails)))
for f in fails:
    print("  ✗ " + f)
sys.exit(0 if not fails else 1)
