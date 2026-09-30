# -*- coding: utf-8 -*-
"""P0 常驻门禁：战斗时间轴（真源 `26_消息模板_v1.md` §三 优化 1「所有战斗日志行统一以【N 刻】开头」）。

判据（只加强、不削弱）：

  D1  凡 `COMBAT_` 槽位带【N 刻】（纯 `{t}` 那一族），它的**每一个生产读端都必须真传 `t=`**
      —— 理由是渲染口 `content/cmds_ast.py::T` 只做 `s.replace("{t}", …)`：
      读端忘传 ⇒ 字面量 `{t}` **原样打上玩家屏**（本门禁立项时实测抓到 2 处：
      `COMBAT_RETREAT_OK` / `COMBAT_ITEM_CAP`）。
  D2  反证：把 `t=` 摘掉 ⇒ 本门禁必须转红（不许变成永远绿的摆设）。
  D3  ★ P0-1 续批五（2026-09-29 · aep0）：**真跑一遍，把落进持久战斗日志的那些行
      逐条核「带不带【N 刻】」** —— D1 只钉「声明了刻就必须真有刻」，**管不到漏声明的那一族**：
      立项时 `COMBAT_SWAP_OK` 就是「不带刻 + 读端也没法补」的组合（前四批一直漏它），
      D1 判它是绿的（它压根没声明 `{t}`）⇒ 只能靠**真跑出来的日志**才照得出来。
      ★ 取件**不许看模板串**：真开一场 + 真敲两下 + 真读『战斗日志』落档的那些行。
      ★ 反证：把 `COMBAT_SWAP_OK` 换回不带刻的旧值 ⇒ D3 必须转红点名那一行。
      ★★ 2026-09-30 收红批三（折行版）：P4 档①（31db85b）把 90 个 COMBAT 槽按 ≤20
        折成多行 ⇒「一条一手」的日志条目**可含多个物理行**。判据随之从「逐物理行核」
        更新为**按条目核首行**：条目首行必须带刻；续行不背刻（也无处背）—— 真源
        26_ §三 优化 1 约束的是「日志行」= 一手一条，不是折出来的物理行。
        条目边界 = 驱动器缩进（`e2e_drive.py` 对每条回话加 `"   " + " "` 前缀，
        续行没有；全仓 texts 的续行都不以 4 连空格开头，已扫证 0 命中）。
        真缺陷照旧抓：漏刻的条目（旧 `COMBAT_SWAP_OK` 那种）红在它自己的条目首行上。

★ 引擎 cue 那一族（`content/rules/battle_text.json` 映射的 62 条）**不在此判**：
  它们走引擎 `cues.with_now()`，时刻由 `cue()` 唯一出口注入 ⇒ 恒有 `t`（判据在 probe_cues）。
★ **不判「每条都得带刻」**：菜单行 / 抬头 / 结算面板本来就不带刻（真源样例只约束战斗日志行），
  硬要它们也带刻会把「规整」改成「噪声」。本门禁只钉**声明了刻就必须真有刻**。
"""
import glob
import io
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXTS = os.path.join(ROOT, "content", "data", "texts.json")
BATTLE_TEXT = os.path.join(ROOT, "content", "rules", "battle_text.json")

CALL = re.compile(r'T\(\s*"(COMBAT_[A-Z0-9_]+)"')


def call_args(text, m):
    """从 `T("KEY"` 之后按**括号配平**截出整个实参段（能跨嵌套 `int(round(...))`）。"""
    depth = 1
    tail = text[m.end():]
    for i, ch in enumerate(tail):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                return tail[:i]
    return tail


def slots():
    texts = json.load(io.open(TEXTS, encoding="utf-8"))
    engine = set(json.load(io.open(BATTLE_TEXT, encoding="utf-8"))["slots"].values())
    need = set()
    for k, rec in texts.items():
        if not k.startswith("COMBAT_") or k in engine:
            continue
        v = rec.get("value", "") if isinstance(rec, dict) else (rec or "")
        if re.search(r"\{t(?![:.a-zA-Z_])", v):        # 纯 {t}（不是引擎那族 {t:.0f}）
            need.add(k)
    return need


def read_ends(need):
    """扫 `content/*.py` 里每一个 `T("COMBAT_…")` 生产读端 ⇒ 没传 t 的那些。"""
    bad = []
    for p in sorted(glob.glob(os.path.join(ROOT, "content", "*.py"))):
        fn = os.path.basename(p)
        text = io.open(p, encoding="utf-8").read()
        for m in CALL.finditer(text):
            key = m.group(1)
            if key not in need:
                continue
            if not re.search(r"\bt\s*=", call_args(text, m)):
                bad.append((fn, text[:m.start()].count(chr(10)) + 1, key))
    return bad


# ★ 取件是**已渲染的那一行**（刻数已被 T() 替掉）⇒ 同时认两种形态：模板串 `【{t} 刻】`（D1 那一族）与 `【N 刻】`（已渲染）。
STAMP = re.compile(r"【(?:\{t(?::[^{}]*)?\}|[-+0-9][0-9._]*) ?刻】")


def _slot_value(key):
    tx = json.load(io.open(TEXTS, encoding="utf-8"))
    rec = tx.get(key) or {}
    return rec.get("value", "") if isinstance(rec, dict) else str(rec)


def drive_log():
    """D3：真开一场、把每个**进战斗日志**的动作各敲一遍，逐条核带不带【N 刻】。

    ★ 为什么必须真跑：`COMBAT_` 槽位有一大半**本来就不该带刻**（菜单 / 抬头 / 结算），
    静态判据分不出「该不该带」；而「谁真的进了日志」只有跑一遍才确定。
    ★ 走的是**指令那一路**（`e2e_drive.py` 用的同一套真宿主契约），不是探针常用的 `human_act`。
    ★ 折行版（2026-09-30 · 收红批三）：核**条目首行**；条目 = 一条一手（可多物理行），
    边界靠驱动器缩进认（每条回话前缀 `"    "`、续行没有）。理由见文件头 D3 段。
    """
    old = os.environ.get("AEP0_D3")
    # ① 静态侧：声明带刻的那一族，取件用 texts 的值 —— 与 D1 互补（这里查「模板形状」）
    stamped = [k for k in slots()]
    print("D3 声明带【N 刻】的内容侧槽位：%d" % len(stamped))
    try:
        import subprocess
        import sys
        py = sys.executable
        env = dict(os.environ)
        env["AST_E2E_SEED"] = json.dumps({"cls": "cls_knight", "race": "human", "name": "试刀",
                                          "level": 9, "gold": 500,
                                          "bag": {"i_weapon_knight_wall_common": 1},
                                          "equipped": {"weapon": "i_weapon_knight_oath_common"}})
        r = subprocess.run([py, os.path.join(ROOT, "scripts", "e2e_drive.py"),
                            "往东", "攻击", "换武器", "战斗日志"],
                           capture_output=True, env=env)
        out = r.stdout.decode("utf-8", "replace")
    except Exception as exc:                              # noqa: BLE001
        print("D3 真跑失败（不放过）：%s" % exc)
        return 1
    tail = out.split("» 战斗日志")[-1]
    # 只取括号开头的回话段：驱动器最后还有一段「== 落档 ==」
    # （存档回显那一行 python dict）——它不是战斗日志行。
    body = tail.split("==")[0]
    raw = [ln for ln in body.split(chr(10))[1:] if ln.strip()]
    # ★ 折行版（2026-09-30 · 收红批三）：条目 = 一手一条，**可含多物理行**（档① 折出来的
    #   续行）。条目边界 = 驱动器缩进：`e2e_drive.py` 对**每条回话**加 `"   " + " "` 前缀、
    #   续行没有（全仓 texts 的续行都不以 4 连空格开头，已扫证 0 命中）。
    #   ⇒ 只核**条目首行**带不带【N 刻】；续行不背刻（真源约束的是「日志行」= 一手一条）。
    #   （本场景条目 < 每页 20 ⇒ 分页尾行不出现；若将来场景变大、尾行现身，它不是条目，按同口径豁免。）
    leads_all = [ln for ln in raw if ln.startswith("    ")]
    cont = len(raw) - len(leads_all)
    # 【这一场】/【上一场】那两行是**日志抬头**（不是一手、不应带刻）
    # 【】是日志本身的括号、与【N 刻】不是一族 ⇒ 先切掉
    leads = [ln for ln in leads_all if not ln.strip().startswith("【")]
    bad = [ln.strip() for ln in leads if not STAMP.search(ln)]
    print("D3 落档的战斗日志条目：%d（折行续行 %d）· 其中**首行**不带【N 刻】：%d"
          % (len(leads), cont, len(bad)))
    for ln in bad:
        print("   ✗ 条目首行不带【N 刻】：%s" % ln)
    if not leads:
        print("   ✗ 一条都没取到 —— 判据取件失败（不许当成「全绿」）")
        return 1
    # ★ 反证：旧写法（不带刻）作条目首行必须被上面那条抓住
    if not bad:
        oldline = "📦 你换上了⚔️重剑（普通）—— 这一手花在换手上。"
        assert STAMP.search(oldline) is None, "反证样本本身带刻"
        _probe_bad = [x for x in ["    " + oldline] if not STAMP.search(x.strip())]
        assert _probe_bad, "反证样本没被抓住 —— 判据恒真"
        print("   · 反证样本（旧写法）作条目首行不带【N 刻】⇒ 上面那条判据抓得住它")
    return 1 if bad else 0


def main():
    need = slots()
    bad = read_ends(need)
    print("需要 t 的内容侧槽位：%d（引擎 cue %d 条走 with_now，不在此判）"
          % (len(need), len(json.load(io.open(BATTLE_TEXT, encoding="utf-8"))["slots"])))
    if bad:
        print("✗ 读端没传 t —— 会把字面量 {t} 打上屏：%d" % len(bad))
        for fn, line, key in bad:
            print("   %s:%d  %s" % (fn, line, key))
        return 1
    print("✓ 每一个【N 刻】槽位的生产读端都真传了 t")
    return 0 if drive_log() == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
