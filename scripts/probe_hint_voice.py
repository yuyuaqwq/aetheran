# -*- coding: utf-8 -*-
"""探针：提示行的**人味**（copy-p5 车道 · 2026-09-29）——「去 AI 感」这一批的常驻门禁。

判据（口径：鱼鱼原话「想开始玩游戏啥的都没什么引导」+「文案不要有 ai 感」；病灶实测见本文件抬头）：

  ① **不许念指令清单** —— 一屏里出现 ≥2 个指令名（『…』包起来的那种）就红。
     病样本（已改前）：`SYS_LOOK_HINT`「『触摸』可以上手摸，『聆听』可以听，『地图』看全貌。」
     = 一屏三个指令名 + 每个都跟一句功能解释 ⇒ 玩家读到的是说明书，不是人话。
     ★ 只对 **HINT/ASK/TIP 族**判：这族按定义就是「人对这个玩家说话」的地方；
       战斗日志 / 招式说明 / 任务行文里有几个指令名是正常的话，不归这一刀。

  ② **功能描述式黑名单** —— 「可以上手摸」「看全貌」这类「解释这条指令能干什么」的说法。
     ★ 破折号不在名单里（这个世界观的正常笔法，370 处）—— 那是另一回事，别顺手删。

  ③ **复读率不许反弹** —— 全表归一骨架的重复行 ≤ 3.2%（P0 车道实测 3.2% = 1016 行 / 983 种）。
     逐条改提示行最容易犯的错就是「全改成同一个句式」⇒ 这条钉住。

  ④ **不许空洞副词堆砌** —— 一条里同时出现 ≥2 个「缓缓/静静/轻轻/默默/静静/悄然/无声」。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_hint_voice.py
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXTS = os.path.join(REPO, "content", "data", "texts.json")

#: 这一族 = 「系统在对玩家说话」的地方（按**族名**取，不手打键名清单）
FAMILY = re.compile(r"HINT|ASK|TIP")

#: ① 指令名只认 **『』**（规范 §7⑤：『』包指令与专名，「」是说话）
#:   → 一屏里 出现 ≥2 个 『』 = 念清单；形式不对就不算。
#:   （第一版把 「」 也算进来，把 `SYS_REG_ASKNAME`「「叫什么名字？」」误判成第二个指令名）
CMD_BRACKET = re.compile(r"『([^『』]+)』")

#: ② 功能描述式（「X 能干什么」）—— 判据按**词组**取，不锁死整句
BANNED = [
    "可以上手摸",          # 可以上手摸
    "可以听",                       # 可以听
    "看全貌",                       # 看全貌
    "可以看",                       # 可以看
    "可以用",                       # 可以用
    "可以穿",                       # 可以穿
    "可以打",                       # 可以打
]

#: ④ 空洞副词（同一条里 ≥2 个才红 —— 单独一个「轻轻推开门」是正常的）
HOLLOW = ["缓缓", "静静", "轻轻", "默默",
          "悄悄", "无声", "不加声"]

#: ③ 复读率上限（与 P0 车道实测基线同值，只许降不许升）
REPEAT_CAP = 0.032

#: 归一化：剥 emoji / 空白 / 『』引号 —— 复读率按**骨架**算
_EMOJI = re.compile("[🌀-🫿☀-➿⬀-⯿️]")


def _norm(s: str) -> str:
    s = _EMOJI.sub("", s or "")
    s = re.sub(r"[『「」』\"'\s、，。！？]", "", s)
    return s


def main() -> int:
    data = json.load(io.open(TEXTS, encoding="utf-8"))
    ok = True

    def chk(label, cond, extra=""):
        nonlocal ok
        ok = ok and bool(cond)
        print("  %s %s%s" % ("OK " if cond else "X  ", label, ("  —— %s" % extra) if extra else ""))

    fam = {k: v for k, v in data.items() if FAMILY.search(k) and isinstance(v, dict) and "value" in v}
    print("提示行人味（copy-p5）：测到 %d 条（HINT/ASK/TIP 族）" % len(fam))

    # ① 不许念指令清单：一屏里 ≥2 个『』「」包着的指令名
    bad_list = []
    for k, v in sorted(fam.items()):
        names = CMD_BRACKET.findall(v["value"])
        if len(names) >= 2:
            bad_list.append((k, len(names), v["value"][:48]))
    chk("① 一屏不许并列 ≥2 个指令名（不许念清单）",
        not bad_list, "; ".join("%s x%d" % (k, n) for k, n, _ in bad_list[:6]))

    # ② 功能描述式黑名单
    bad_ban = []
    for k, v in sorted(fam.items()):
        for pat in BANNED:
            if re.search(pat, v["value"]):
                bad_ban.append((k, pat))
                break
    chk("② 无功能描述式说法（「可以上手摸」这类）",
        not bad_ban, "; ".join("%s" % k for k, _ in bad_ban[:6]))

    # ③ 不许空洞副词堆砌（同一条 ≥2 个）
    bad_hol = []
    for k, v in sorted(fam.items()):
        n = sum(1 for w in HOLLOW if w in v["value"])
        if n >= 2:
            bad_hol.append((k, n, v["value"][:40]))
    chk("③ 一条里不许空洞副词堆砌（≥2 个）",
        not bad_hol, "; ".join("%s x%d" % (k, n) for k, n, _ in bad_hol[:6]))

    # ④ 复读率不许反弹（全表骨架）
    skel = {}
    for v in data.values():
        if not isinstance(v, dict):
            continue
        s = _norm(v.get("value", ""))
        if s:
            skel[s] = skel.get(s, 0) + 1
    total = sum(skel.values())
    uniq = len(skel)
    rate = (total - uniq) / float(total) if total else 0.0
    chk("④ 复读率 ≤ %.1f%%（现取：%.2f%% = %d 行 / %d 种骨架）"
        % (REPEAT_CAP * 100, rate * 100, total, uniq),
        rate <= REPEAT_CAP + 1e-9, "反弹了：把提示行全改成一个句式了")

    print("提示行人味：%s" % ("全绿" if ok else "有红"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
