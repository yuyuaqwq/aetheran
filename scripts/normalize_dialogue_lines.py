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
import unicodedata

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(REPO, "content", "data", "dialogues.json")

#: 单行上限（**全尺宽**）—— 鱼鱼口径「一般一行只能放 14 个字」。
#: 旧值 40 数的是 **code point**：半角标点与拉丁字母各占 1，而它们在屏上只占半格
#: ⇒ 40 个字符那一行实际远窄于 40 全尺。排版问的是「屏上能放几个字」，
#: 所以必须量 `disp_width`（屏宽）而不是 `len()`。
LIMIT = 14

#: 硬上限（档①）—— 超过它 = 排版事故；只在**切不动**时才会留
#: （引号里那句一句到底、句末之间已超宽）
HARD_MAX = 20

#: 一组引号（「…」/『…』）—— 只认成对的；认不出的留给「非引号那一支」原样接上
_QUOTE = re.compile(r"[「『][^」』]*[」』]")
#: 句末（切长行用；标点在**后面**，所以整句带着标点走）
_SENT = re.compile(r"[^。！？…]*[。！？…]*")
#: 成对引号（「…」与『…』）—— 断开后每段各自戴回同一对
_BRACKETS = {"「": "」", "『": "』"}
#: 一段左括号引语（（…））
_NARR = re.compile(r"（[^）]*）")
#: 次级切点（逗号/顿号/／冒号）—— 句末切完**仍超宽**时的最后一手
#: （中文排版在逗号处换行是常规；仍然一个段超宽 ⇒ 真的切不动，留给门禁报）
_CLAUSE = re.compile(r"[^，、；：…]*[，、；：…]*")


def disp_width(s):
    """屏宽（全角算 1 · 半角/emoji 算 0.5）—— 排版口径量的不是字符数。
    """
    t = 0.0
    for ch in str(s):
        if 0x1F000 <= ord(ch) <= 0x1FAFF:        # emoji 区
            t += 0.5
        elif unicodedata.east_asian_width(ch) in ("W", "F", "A"):
            t += 1.0
        else:
            t += 0.5
    return t


def _tokens(s):
    """→ [(是不是引号, 那一截)] —— 引号段与其它段交替。

    ★ 这里只认**顶层**引号：嵌套的 『…』 跟着外层「…」 走，
    不允许内层单独被拆成另一行。
    """
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
    parts = _safe_parts(s, _SENT)
    if len(parts) < 2:                       # 一句到底 ⇒ 试次级切点
        parts = _safe_parts(s, _CLAUSE)
    out, cur = [], ""
    for p in parts:
        if cur and disp_width(cur) + disp_width(p) > limit:
            out.append(cur)
            cur = ""
        cur += p
    if cur:
        out.append(cur)
    return out or [s]


def _safe_parts(text, seps):
    """按 `seps` 切出的段序列 —— 切点**不得落在未闭合引号里**。

    ★ 为什么要这个（2026-09-29 实测抓到的真事故）
    ------------------------------------------
    一段台词里可以有「他说『你不懂』」这种**嵌套**引号，
    而 `_CLAUSE` 是「除正列切点外的任何字符」—— 它会在 『 里面切一下，
    切出来的前半段就是个**没有收尾的「**（实测：`「他说『你不懂』`）。
    保护：切前先看“这一段里有没有未闭合的引号”，有就不切。
    """
    segs = re.findall(seps, text)
    if len(segs) < 2:
        return [text] if text else []
    out, cur, depth = [], "", 0
    for seg in segs:
        cur += seg
        # 只计引号的开合（②）不计 （）—— 否则一句中途的引语
        # （例如「（终于转身）我告诉你：是我们自己的。」）会把 depth 压成不平衡
        depth += seg.count("「") - seg.count("」")
        depth += seg.count("『") - seg.count("』")
        if depth == 0:                      # 引号全闭了 ⇒ 这里才是一个合法切点
            out.append(cur)
            cur = ""
    if cur.strip():
        out.append(cur)                      # 尾段（如果不平衡，原样保留）
    return out if len(out) > 1 else [text]


def _split_quoted(g, limit):
    """一组**超宽**的「…」按句末再断一次，每段各自戴回引号。

    为什么要它（2026-09-29 P4 排版车道实测）
    ---------------------------------------
    话本里有 182 组「」**单组就超 20 全尺宽**（实测最宽 52），
    而原 ③ 那一支写死「只断没有引号的行」⇒ 它们在历次归一化里
    一直超宽，一行粘在屏上。

    ★ 只**插入换行符**，一个汉字都不改：切点只落在句末标点后，
    切出来的每一段都原样戴着它自己的「」。
    """
    if disp_width(g) <= limit or len(g) < 2 or g[0] not in _BRACKETS:
        return [g]
    # 嵌套引号（「…『…』…」）整组不拆：拆了会把外层「的收尾归到内层句子那边
    # ⇒ 两段各自戴上内层的 』，而外层的 」又浮在最后一段末尾 ⇒ **引号不配对**
    # （实测输出里出现过「我问他那是啥，』）。拆嵌套引号 = 改写法，越过「只改排版」。
    if "『" in g or "』" in g:
        return [g]
    inner = g[1:-1]
    parts = _safe_parts(inner, _SENT)
    if len(parts) < 2:                       # 一句到底 ⇒ 再试次级切点（逗号）
        parts = _safe_parts(inner, _CLAUSE)
    if len(parts) < 2:
        return [g]                            # 真的切不动 ⇒ 原样留，交门禁报
    out, cur = [], ""
    for q in parts:
        if cur and disp_width(cur) + disp_width(q) + 2 > limit:
            out.append(g[0] + cur + g[-1])
            cur = q
        else:
            cur += q
    if cur:
        out.append(g[0] + cur + g[-1])
    return out


def _split_narration(s, limit):
    """行里挤着多段 （…） 旁白 ⇒ 按括号切开，每段一行。

    切点只在**右括号之后**，所以每个 （…） 都原样保住。
    """
    if disp_width(s) <= limit or "（" not in s:
        return [s]
    parts = _NARR.findall(s)
    if len(parts) < 2:
        return [s]
    out, cur = [], ""
    for q in parts:
        # 一个 （） 内部也超宽 ⇒ 按句末 / 次级切点再断（括号本身不动）
        subs = _wrap(q, limit) if disp_width(q) > limit else [q]
        for sub in subs:
            if cur and disp_width(cur) + disp_width(sub) > limit:
                out.append(cur)
                cur = ""
            cur += sub
    if cur:
        out.append(cur)
    return out if len(out) > 1 else [s]


def _fit(line, limit):
    """一行拆到全部行都 ≤ limit 宽（尽力；切不动就原样返回）。

    ★ 关键：切裂在**一次调用里**循环到不再变。如果返回的行还超宽
    就再拆一遍（两种拆法会互相触发：先括号又句末、或先句末又括号）。
    不这么做的话「跑一遍归一化 + 跑第二遍又改」⇒ **数据不幂等**，
    而项目把幂等写进了 `probe_dialogues ⑨`。
    """
    out = [line]
    for _ in range(6):                        # 6 轮足够（实测最多 2 轮就到不动点）
        nxt = []
        changed = False
        for ln in out:
            if disp_width(ln) <= limit:
                nxt.append(ln)
                continue
            changed = True
            # ④ 无引号 → 先括号、再句末
            if "「" not in ln and "『" not in ln:
                for piece in _split_narration(ln, limit):
                    nxt.extend(_wrap(piece, limit))
                continue
            # ④ 有引号 → 引号自己断；旁白只在放得下时贴
            cur = ""
            for is_quote, chunk in _tokens(ln):
                if is_quote:
                    pieces = _split_quoted(chunk, limit)
                    if cur.strip():
                        nxt.append(cur)
                        cur = ""
                    if len(pieces) == 1:
                        cur = pieces[0]
                    else:
                        nxt.extend(pieces)
                        cur = ""
                else:
                    if (cur.strip() and ("「" in cur or "『" in cur)
                            and disp_width(cur) + disp_width(chunk) > limit):
                        nxt.append(cur)
                        cur = ""
                    cur += chunk
            if cur:
                nxt.append(cur)
        out = nxt
        if not changed:
            break
    return out


def speak(text, limit=LIMIT):
    """一段台词 → 行表（已 strip；空行丢掉）。"""
    out = []
    for piece in str(text).split(chr(10)):
        piece = piece.strip()
        if not piece:
            continue
        # ① 一组「」一行：当前行已有「」时，再遇一组就换行
        # ② 旁白贴在它前面那句后面
        cur = ""
        for is_quote, chunk in _tokens(piece):
            if is_quote and ("「" in cur or "『" in cur):
                out.append(cur)
                cur = ""
            elif not is_quote and not chunk.strip() and cur:
                cur += chunk
                continue
            cur += chunk
        if cur:
            out.append(cur)
    # ③ 再拆一次到全部 ≤ limit（幂等：内部循环到不再变）
    final = []
    for ln in out:
        final.extend(_fit(ln, limit))
    return final


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
