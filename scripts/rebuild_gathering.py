# -*- coding: utf-8 -*-
"""gathering 域重建（B3-6b-2c）：给每个采集点补一个 **ASCII 动词键**（`verb`）。

为什么要有 `verb`
------------------
`kind`（采药 / 挖掘 / 垂钓 / 搜查）是给人看的中文枚举；代码里拿它当筛选键就成了
「中文字面量当机器键」（同 quests 的 `kind` vs `chain`，见 K48）。
⇒ 采集点补一个 ASCII 键 `verb`，四个动词各一个：

    采药 → herb · 挖掘 → dig · 垂钓 → fish · 搜查 → search
    （预留：巢 → nest · 矿脉 → vein —— kind 枚举里有、数据里还没用）

规矩
----
· 一个点只归一个动词（点自己就是一张池，动词 = 谁能采它）
· **连跑两次数据不变**（幂等自检）
· 保留原插入序 · `indent=2` · LF 落盘 · 末尾一个换行
· 自带对账：`verb` 必须与点 id 中间那一段一致（`gt_bn_dig_1` → `dig`）—— 数据自身的一致性

用法：python scripts/rebuild_gathering.py [--dry]
"""
from __future__ import annotations

import io
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(REPO, "content", "data", "gathering.json")

#: kind（中文枚举 · 给人看）→ verb（ASCII 键 · 给代码用）
KIND_VERB = {
    "采药": "herb",
    "挖掘": "dig",
    "垂钓": "fish",
    "搜查": "search",
    "巢": "nest",
    "矿脉": "vein",
}


def rebuild(tbl):
    """返回 (新表, 改动条数) —— 只补/纠正 verb，别的字段原样。"""
    out, changed = {}, 0
    for gid, v in tbl.items():
        kind = v.get("kind")
        if kind not in KIND_VERB:
            raise SystemExit("kind 没登记的动词（先补 KIND_VERB）：%s -> %r" % (gid, kind))
        verb = KIND_VERB[kind]
        parts = gid.split("_")
        if len(parts) > 2 and parts[2] != verb:
            raise SystemExit("点 id 与动词对不上：%s（id 里是 %r，算出来是 %r）" % (gid, parts[2], verb))
        rec = {}
        for k, val in v.items():
            rec[k] = val
            if k == "kind":
                rec["verb"] = verb               # 贴在 kind 后面（同一件事挨着写）
        if v.get("verb") != verb or "verb" not in v:
            changed += 1
        out[gid] = rec
    return out, changed


def main(argv):
    dry = "--dry" in argv
    tbl = json.loads(io.open(PATH, encoding="utf-8").read())
    new, changed = rebuild(tbl)
    print("gathering：%d 个点 · 要写 verb 的 %d 个" % (len(new), changed))
    if not changed:
        print("  · 无变化 —— 数据不变（幂等）")
        return 0
    for gid, v in new.items():
        print("  · %-18s %-4s -> %s" % (gid, v["kind"], v["verb"]))
    if dry:
        print("（--dry：没落盘）")
        return 0
    with io.open(PATH, "w", newline=chr(10), encoding="utf-8") as f:
        json.dump(new, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("落地：%s" % PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
