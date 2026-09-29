# -*- coding: utf-8 -*-
"""P0 常驻门禁：战斗时间轴（真源 `26_消息模板_v1.md` §三 优化 1「所有战斗日志行统一以【N 刻】开头」）。

判据（只加强、不削弱）：

  D1  凡 `COMBAT_` 槽位带【N 刻】（纯 `{t}` 那一族），它的**每一个生产读端都必须真传 `t=`**
      —— 理由是渲染口 `content/cmds_ast.py::T` 只做 `s.replace("{t}", …)`：
      读端忘传 ⇒ 字面量 `{t}` **原样打上玩家屏**（本门禁立项时实测抓到 2 处：
      `COMBAT_RETREAT_OK` / `COMBAT_ITEM_CAP`）。
  D2  反证：把 `t=` 摘掉 ⇒ 本门禁必须转红（不许变成永远绿的摆设）。

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
