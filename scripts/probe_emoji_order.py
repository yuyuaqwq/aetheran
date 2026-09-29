# -*- coding: utf-8 -*-
"""探针：玩家可见文案的**图标规整度**（文案修复车道 P2-3）

为什么有这条线
--------------------------------------------------
鱼鱼口径（原话，别搞反）：
  「emoji 是可以的，就像奥兰迪亚那种，只要很规整观感好问题就不大」
  「我甚至觉得适当的 emoji 会更好」
⇒ **emoji 是认可的正规手法**；「该配图标而没配」是缺口，
  「同一语义在同一界面内用了两个写法」是真缺陷。
⇒ **emoji 少不是缺陷、emoji 多也不是缺陷。**

★ 本探针**只钉一致性，从不钉覆盖率**。钉覆盖率会让别的车道一改文案就红，
  而「少图标」本身不是缺陷 —— 那是文案车道的口味活，不是门禁该管的事。
  想看覆盖率：`python scripts/probe_emoji_order.py --cov`（只打印，不判红）。

判据（三条，全部取自真源，不自创）
--------------------------------------------------
①  同屏 · 同一图标 → 同一连接形
    真源 26_ §2.2 的 emoji 表只规定「图标 + 语义」，没规定图标后面怎么接文字。
    于是同一个图标在**同一屏**里出现「⚔ 你…」与「⚔【…」两种接法，
    就是「不规整 / 观感不好」的字面证据。
    ★ 按**屏**分组，不按全局分组：跨界面不同本来就正常（§7d）。
②  同屏 · 同一图标 → 同一行首字形（含 VS16 U+FE0F）
    `⚔` 与 `⚔️` 是同一个图标的两种字形；同屏混用 = 观感不齐。
    ★ 注意**不是**「同屏所有图标必须相同」—— 同屏里 💥(伤害) 与 🛡(减伤) 并存是对的，
      26_ §2.2 的表本来就是一张「多语义」表。这里只管**同一个**图标的字形与接法自身一致。
③  同屏 · 并列行（`_ROW`）行首锚点一致
    一组并列行要么都带行首锚，要么都不带。已成立的口径（见提交 7a61c83）：
    「行首一个锚（`· `，或槽位自带的 ① / ✦）作条目锚点」，
    同屏不许一半有一半没有。

★ 「同一语义两个 emoji」（🚧 还没接上 vs ⚠️ 出错）**不在这三条里**：
  那要逐条裁定语义归属，属文案判断；本探针只管能机械判的写法一致性。

反证（判据必须真抓得住）
--------------------------------------------------
临时把某条槽位改成违规写法（emoji 后接空格 / 换另一种字形），
重跑 ⇒ 同屏当场红；还原 ⇒ 回绿。判据只加强，不放宽。

用法：python scripts/probe_emoji_order.py [--cov] [--selftest]
"""
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXTS = os.path.join(ROOT, "content", "data", "texts.json")

VS16 = "️"
DOT = "·"
BRACKET_OPEN = "【("


def is_emoji(ch):
    o = ord(ch)
    return ((0x1F000 <= o <= 0x1FAFF) or (0x2600 <= o <= 0x27BF)
            or (0x2B00 <= o <= 0x2BFF) or o == 0x2728)


def lead(line):
    """行首图标 -> (图标本体, 含 VS16 的完整字形, 连接形)。非图标行返回 None。"""
    if not line or not is_emoji(line[0]):
        return None
    n = 2 if len(line) > 1 and line[1] == VS16 else 1
    icon = line[0]
    glyph = line[:n]
    rest = line[n:]
    if rest[:1] == " ":
        form = "SPACE"
    elif rest[:1] in BRACKET_OPEN:
        form = "BRACKET"
    else:
        form = "OTHER:" + rest[:1]
    return icon, glyph, form


def screen_of(slot):
    """一个「屏」= 一个界面的那几行：取槽名前两段（COMBAT_LANDING_X -> COMBAT_LANDING）。"""
    p = slot.split("_")
    return "_".join(p[:2]) if len(p) > 2 else slot


def row_anchor(val, got):
    """并列行的行首锚形态：EMO(带图标) / DOT(带 · 锚) 的组合。"""
    head = val[len(got[1]):] if got else val
    return ("EMO" if got else "") + ("DOT" if head.startswith(DOT) else "")


def collect(texts):
    forms = defaultdict(dict)     # 屏 -> 槽位 -> (图标, 字形, 连接形)
    rows = defaultdict(dict)      # 屏 -> 槽位 -> 锚形态
    for slot in sorted(texts):
        rec = texts[slot]
        val = rec.get("value", "") if isinstance(rec, dict) else ""
        if not val:
            continue
        for line in val.split("\n"):
            got = lead(line)
            if got:
                forms[screen_of(slot)][slot] = got
                break
        if slot.endswith("_ROW"):
            got = lead(val)
            rows[screen_of(slot)][slot] = row_anchor(val, got)
    return forms, rows


def check(texts):
    forms, rows = collect(texts)
    bad = []

    for scr, m in sorted(forms.items()):
        by_icon = defaultdict(set)
        for slot, got in m.items():
            by_icon[got[0]].add(got[2])
        for icon, fset in sorted(by_icon.items()):
            if len(fset) > 1:
                bad.append(("①", scr, "%r 两种接法" % icon, sorted(fset),
                            sorted(s for s, g in m.items() if g[2] in fset)))

        by_icon_glyph = defaultdict(set)
        for slot, got in m.items():
            by_icon_glyph[got[0]].add(got[1])
        for icon, gset in sorted(by_icon_glyph.items()):
            if len(gset) > 1:
                bad.append(("②", scr, "%r 两种字形" % icon, sorted(gset),
                            sorted(s for s, g in m.items() if g[1] in gset)))

    for scr, m in sorted(rows.items()):
        if len(set(m.values())) > 1:
            bad.append(("③", scr, "并列行锚点不齐", sorted(set(m.values())), sorted(m)))

    return bad, forms, rows


def coverage(texts):
    tot = emo = 0
    per = defaultdict(lambda: [0, 0])
    for slot, rec in texts.items():
        val = rec.get("value", "") if isinstance(rec, dict) else ""
        if not val:
            continue
        tot += 1
        has = any(lead(l) for l in val.split("\n"))
        s = screen_of(slot)
        per[s][0] += 1
        if has:
            per[s][1] += 1
            emo += 1
    print("覆盖率（只打印、不判红 —— 少图标不是缺陷）：%d/%d = %.0f%%"
          % (emo, tot, 100.0 * emo / max(tot, 1)))
    for s in sorted(per, key=lambda x: -per[x][0])[:20]:
        t, e = per[s]
        print("  %-16s %3d/%-3d %3.0f%%" % (s, e, t, 100.0 * e / max(t, 1)))


def selftest(texts):
    """反证：判据必须真抓得住违规写法（**全程在内存里改，不落盘、不碰 texts.json**）。

    并发车道共用 texts.json，真去改文件会既污染别人的面又制造整份 json 的重排 diff。
    """
    base, _, _ = check(texts)
    base_n = len(base)
    cases = [
        ("① 同一图标换成另一种接法",
         "SYS_STATUS_VITALS", "📊（生命", True),
        # ② 要「同一个图标、两种字形」：📊 全部带 VS16，去掉其中一个的 VS16
        ("② 同一图标去掉 VS16（两种字形）",
         "SYS_STATUS_VITALS", "📊️生命 {hp}", True),
        # ③ 要同屏**有两条以上**并列行才谈得上「齐不齐」：SYS_BOARD 有三条
        ("③ 并列行锚点不齐（同屏三条改一条）",
         "SYS_BOARD_SIDE_ROW", "📜 · {order} {name} —— {objective}", True),
        ("④ 对照组：只改措辞、三个锚点形态都不碰",
         "SYS_STATUS_VITALS", "📊 气血 {hp}/{hp_max} ｜ 法力 {mo}/{mo_max} ｜ 铜板 {gold}", False),
    ]
    ok = True
    print("自检：基线缺陷 %d 处（改之前）" % base_n)
    for why, slot, newval, should_catch in cases:
        t2 = json.loads(json.dumps(texts))
        old_val = t2[slot]["value"]
        t2[slot]["value"] = newval
        got, _, _ = check(t2)
        # 比「同一屏的缺陷条数」，不比总数 —— 仓里本来就有 3 处既存缺陷，
        # 用总数比会永远「抓不住」（新缺陷恰好在另一屏时）。
        def forms_of(items, scr):
            """该屏每条缺陷**分歧出来的形式数**之和。
            ① 把同一图标的所有分歧并成一条，槽位数不变、形式数会变 ——
            所以要数形式（detail[0]），不是数槽位。"""
            return sum(len(it[3]) for it in items if it[1] == scr)
        base_here = forms_of(base, screen_of(slot))
        caught = forms_of(got, screen_of(slot)) > base_here
        flag = "抓得住" if caught else "没抓到"
        mark = "✓" if caught == should_catch else "✗"
        if caught != should_catch:
            ok = False
        print("  %s %-34s %s" % (mark, why, flag))
        t2[slot]["value"] = old_val
    tail = chr(10)
    print(tail + "%s 自检%s（判据有牙；对照组必须**不**被抓，否则判据过宽）"          % ("✓" if ok else "✗", "通过" if ok else "失败"))
    return 0 if ok else 1


def main():
    with open(TEXTS, encoding="utf-8") as fh:
        texts = json.load(fh)
    if "--cov" in sys.argv:
        coverage(texts)
        return 0
    if "--selftest" in sys.argv:
        return selftest(texts)
    bad, forms, rows = check(texts)
    print("槽位 %d · 有图标的屏 %d · 并列行屏 %d"
          % (len(texts), len(forms), len(rows)))
    if not bad:
        print("\n✓ 图标规整度通过（同屏同图标同接法 · 同屏同接法同字形 · 并列行锚点齐）")
        return 0
    print("\n✗ 规整度缺陷 %d 处（只算同屏内；跨屏不同不算问题）" % len(bad))
    for tag, scr, key, detail, slots in bad:
        print("\n  [%s] 屏 %s — %s：%s" % (tag, scr, key, detail))
        for s in slots:
            v = texts[s].get("value", "").split("\n")[0]
            print("      %-32s %s" % (s, v[:50]))
    return 1


if __name__ == "__main__":
    sys.exit(main())
