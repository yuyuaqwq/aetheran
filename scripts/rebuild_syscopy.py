# -*- coding: utf-8 -*-
"""syscopy 落域脚本（B3-6b）：把「系统与移动」那批文案从口径文档解析进 texts 域。

源（唯一真源）：`00_总纲/17_文案收口口径_v1.md` 的槽位表（后续批继续往那份表加）
落点：`content/data/texts.json`（文案真源表）

规矩：
  · 只**新增**缺失的槽位；已存在的槽位必须**逐字相同**（不同就抛 —— 防两处口径打架）
  · 保持原表插入序（K27：别 sort_keys，一排序就是近千行假 diff）
  · 末尾补一个换行 · LF 落盘
  · 连跑两次数据不变（幂等自检；第二次应报「无新增」）
  · 占位与 params **双向对账**（声明的要有占位 · 占位要声明过）

用法：python scripts/rebuild_syscopy.py [--dry]
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.environ.get("AST_PLAN", "C:/Users/yuyu/aetheran-plan")
DOC = os.path.join(PLAN, "00_总纲", "17_文案收口口径_v1.md")
TEXTS = os.path.join(REPO, "content", "data", "texts.json")

#: ★ B4-16 起 `RANK_*` 也在这一族里（公会评级那几张档名 —— 键 = `RANK_<ASCII ID>`，
#:   拼法唯一在 `content/ranks.py::label_key`；档名本体是文案，所以它归 texts 域）。
KEY_RE = re.compile(r"^(SCENE|READ|NPC|COMBAT|QUEST|ITEM|SYS|TITLE|WORLD|HOUR|WEATHER|UNID|TALK|RANK)_[A-Z0-9_]+$")
PH = re.compile(r"\{(\w+)\}")
ROW_RE = re.compile(r"^\|\s*([A-Z][A-Z0-9_]*)\s*\|")

def parse_doc(path=DOC):
    """读口径文档里**所有**槽位表 -> 每行一条（顺序 = 文档里的顺序）。

    ★ 后续批次继续往那份文档下面加表就行（脚本按行全扫）—— 别另开一份，免得两处口径。
    """
    if not os.path.exists(path):
        raise SystemExit("口径文档不在：%s" % path)
    lines = io.open(path, encoding="utf-8").read().split(chr(10))
    out = []
    for ln in lines:
        if not ROW_RE.match(ln):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) != 5:
            raise SystemExit("列数不是 5（别改列数）：%s" % ln)
        key, value, params, cat, srcname = cells
        # ★ 多行文案：表里写 `\n`（反斜杠 n）＝真换行（行内不许出现真换行 —— 真换行会把一行切成两行，
        #   第二行不是槽位行、**静默漏掉**）。JSON 落盘时它就是一个真换行（与 SCENE_* 那些多段正文同形）。
        value = value.replace("\\n", "\n")
        prm = [] if params in ("-", "") else [x.strip() for x in params.split(",") if x.strip()]
        out.append({"key": key, "value": value, "params": prm,
                    "category": cat, "src": srcname})
    if not out:
        raise SystemExit("槽位表是空的")
    return out


def check(rows):
    """键名 · 重复 · 占位与 params 双向对账 —— 错一条都不许落。"""
    bad = []
    seen = set()
    for r in rows:
        k, v = r["key"], r["value"]
        if not KEY_RE.match(k):
            bad.append("键名不合规则：%s" % k)
        if k in seen:
            bad.append("重复：%s" % k)
        seen.add(k)
        used = set(PH.findall(v))
        decl = set(r["params"])
        if used - decl:
            bad.append("%s：value 里的占位没声明 -> %s" % (k, sorted(used - decl)))
        if decl - used:
            bad.append("%s：声明了却没占位 -> %s" % (k, sorted(decl - used)))
        if not v.strip():
            bad.append("%s：文案是空的" % k)
        if "〔待填" in v:
            bad.append("%s：还是待填占位" % k)
    if bad:
        for b in bad:
            print("  x %s" % b)
        raise SystemExit("槽位表没过对账，没写任何东西")
    return True


def load_texts():
    return json.load(io.open(TEXTS, encoding="utf-8"))


def dump_texts(tx):
    with io.open(TEXTS, "w", newline=chr(10), encoding="utf-8") as f:
        json.dump(tx, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main(argv):
    dry = "--dry" in argv
    rows = parse_doc()
    check(rows)
    tx = load_texts()
    before = len(tx)
    add, same, clash = [], 0, []
    for r in rows:
        old = tx.get(r["key"])
        if old is None:
            add.append(r)
        elif old.get("value") == r["value"]:
            same += 1
        else:
            clash.append((r["key"], old.get("value"), r["value"]))
    if clash:
        for k, a, b in clash:
            print("  x %s 两处不一样：" % k)
            print("      表里：%s" % b)
            print("      域里：%s" % a)
        raise SystemExit("槽位与域里的字不一样 —— 先裁决再落（没写任何东西）")
    print("解析：%d 条（已存在且一致 %d · 要新增 %d）" % (len(rows), same, len(add)))
    if not add:
        print("  · 无新增 —— 数据不变（幂等）")
        return 0
    for r in add:
        tx[r["key"]] = {"value": r["value"], "params": r["params"],
                        "category": r["category"], "desc": r["src"]}
        print("  + %-22s %s" % (r["key"], r["value"][:34]))
    if dry:
        print("（--dry：没落盘；texts %d -> %d）" % (before, len(tx)))
        return 0
    dump_texts(tx)
    print("落地：texts %d -> %d 条  %s" % (before, len(tx), TEXTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
