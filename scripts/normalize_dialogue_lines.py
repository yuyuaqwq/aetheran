# -*- coding: utf-8 -*-
"""对话台词「一句一行」归一化（fix3-⑤）—— 把 dialogues 域里那些「一坨」的台词切成多行。

为什么要有它（玩家报告 P1 体验-5 / P4 E-2 同族）
--------------------------------------------------
`搭话` 的回话是「一个 NPC 一段台词」。台词在域里是**一行字符串**，几十上百字，里面塞着
6–8 组「」和（旁白）—— 界面上读起来是一坨（实测最长的 138 字、6 组引号）。
而『观察』（SCENE_* 正文自带换行）与『悬赏』（一行一条槽位）早就做到了一句一行。

口径：**排版随文案走**（与 SCENE_* 同一条路）—— 换行写进对话台词本身，
呈现口（`content/cmds_talk.talk` 的 `split("\\n")`）一个字不用改。

三条切行规则（可复现、幂等）
--------------------------------------------------
① 一组「」一行：**当前行已经有「」时，再遇一组就换行**；
② 旁白/动作（……）**贴在它前面那句后面**（`「……」`（他翻了两下）（压低声音） 同行）；
③ 单行超过 `LIMIT` 字就在句末断开（。！？…）—— 防「一组引号里塞三句」那种长句。

用法：python scripts/normalize_dialogue_lines.py [--dry]
      ★ 幂等：连跑两次数据逐字节不变（跑第二遍「改动 0 处」）。
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(REPO, "content", "data", "dialogues.json")

#: 单行上限（字）—— 「一句」的上界；超过就在句末断开
LIMIT = 40

#: 一组引号（「…」/『…』）—— 只认成对的；认不出的留给「非引号那一支」原样接上
_QUOTE = re.compile(r"[「『][^」』]*[」』]")
#: 句末（切长行用；标点在**后面**，所以整句带着标点走）
_SENT = re.compile(r"[^。！？…]*[。！？…]*")


def _tokens(s):
    """→ [(是不是引号, 那一截)] —— 引号段与其它段交替。"""
    out, i = [], 0
    for m in _QUOTE.finditer(s):
        if m.start() > i:
            out.append((False, s[i:m.start()]))
        out.append((True, m.group(0)))
        i = m.end()
    if i < len(s):
        out.append((False, s[i:]))
    return out


def _wrap(s, limit=LIMIT):
    """长行按句末断开（一句都不切碎 —— 切不动就原样留着，让探针去报）。"""
    parts = [p for p in _SENT.findall(s) if p]
    out, cur = [], ""
    for p in parts:
        if cur and len(cur) + len(p) > limit:
            out.append(cur)
            cur = ""
        cur += p
    if cur:
        out.append(cur)
    return out or [s]


def speak(text, limit=LIMIT):
    """一段台词 → 行表（已 strip；空行丢掉）。"""
    lines = []
    for piece in str(text).split("\n"):
        piece = piece.strip()
        if not piece:
            continue
        cur = ""
        for is_quote, chunk in _tokens(piece):
            if is_quote and "「" in cur:
                lines.append(cur)
                cur = ""
            elif not is_quote and not chunk.strip() and cur:
                cur += chunk                       # 引号之间的空隙 / 顿点：贴着上一句
                continue
            cur += chunk
        if cur:
            lines.append(cur)
    # ③ 长行再按句末断一次 —— ★ 只断**没有引号**的行：引号里的那句不许从中间切开
    #    （切了会造出「半句 + 」」这种半截行）
    out = []
    for ln in lines:
        if len(ln) > limit and "「" not in ln:
            out.extend(_wrap(ln, limit))
        else:
            out.append(ln)
    return out


def rewrite(doc, limit=LIMIT):
    """就地改 dialogues 域 → (改动的条数, 明细)。"""
    changed = []
    for tree, rec in doc.items():
        for node, nd in (rec.get("nodes") or {}).items():
            for i, t in enumerate(nd.get("texts") or []):
                old = t.get("text") or ""
                new = "\n".join(speak(old, limit))
                if new != old:
                    t["text"] = new
                    changed.append(("%s/%s[%d]" % (tree, node, i), len(old), len(new)))
    return changed


def main(argv):
    dry = "--dry" in argv
    with io.open(PATH, encoding="utf-8") as f:
        doc = json.load(f)
    before = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    changed = rewrite(doc)
    after = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    print("对话台词切行：改动 %d 条（上限 %d 字/行）" % (len(changed), LIMIT))
    for name, a, b in changed:
        print("  · %-22s %3d → %3d 字" % (name, a, b))
    if dry:
        print("（--dry：没落盘）")
        return 0
    if after == before:
        print("  · 数据不变（幂等）")
        return 0
    with io.open(PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(after)
    print("落地：%s" % PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
