# -*- coding: utf-8 -*-
"""探针：全屏行宽（鱼鱼口径「一般一行只能放 14 个字」）—— 三档 + 零漏 + 棘轮。

背景
----
2026-09-29 鱼鱼原话：「排版，所有消息模板和文案要全部扫一遍，**不要漏**」
「排版要考虑玩家体验，**一般一行只能放 14 个字**」。
14 是**软目标**（不是一刀切硬上限），所以分三档：

  档① 硬上限 20  面板行 / 列表行 / 战斗行 / 提示行 —— 凡是**非长文体**的一行。
                  超过 20 全角宽 = **排版事故，硬红**。
  档② 软目标 14  提示 / 问句族（HINT/ASK/TIP/BAD/TOAST…）：14–20 **只记警告**，
                  不判红 —— 这一档的处置权在文案车道（改它要动措辞）。
  档③ 长文体     SCENE / READ / HELP / NOTE：不按行宽判红，只查
                  **有没有按 ≤14 分段**（整段 100 字一行 = 屏上糊成一坨）。

量的是**全角宽**不是字符数（全角 1 · 半角/emoji 0.5）：理由见
`normalize_dialogue_lines.disp_width` 的 docstring。**本探针与切行器共用
同一把尺**（`NL.disp_width`），全仓不留第二份行宽算法。

★ 棘轮（为什么不是「现在就该全绿」）
------------------------------------
档①/档③ 现在的实测值还远大于 0（`texts.json` 那一族是并发车道在改的共享面，
本车道不碰）。所以这里用**棘轮**而不是「现状即合格」：

  · 判据本身一字未松（档① >20 仍判红、档③ >14 仍判红）
  · 只把**当前条数**钉成上限（`_RATCHET`），并要求「不许变多」
  · 下一批修一处就把上限往下挪一格 ⇒ 修完自动变绿，**倒退立刻红**

这比「没有门」强得多（没有门 = 下一个人把行宽删了也没人知道），
也比「先放宽阈值让它绿」强（那叫把成果供着）。
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import normalize_dialogue_lines as NL          # noqa: E402  —— 共用同一把尺

SOFT = NL.LIMIT          # 14（与切行器同一常量，不写死第二份）
HARD = NL.HARD_MAX       # 20（档① 硬上限）

#: 档② 家族（提示 / 问句）—— 14–20 只记警告
FAM_SOFT = re.compile(r"_(HINT|ASK|TIP|BAD|TOAST)$", re.I)
#: 档③ 家族（长文体）—— 不断行本身就是缺陷
FAM_PROSE = re.compile(r"^(SCENE|READ|HELP|NOTE)_", re.I)

#: ★ 棘轮上限（2026-09-29 本车道实测钉下；每修一处就往下挪一格）
_RATCHET = {"hard": 538, "prose": 110}

ok = True


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


def w(s):
    return NL.disp_width(s)


def audit(pairs):
    """pairs = [(槽位名, 那一行)] → 三档计数。档② 只认 FAM_SOFT 家族。"""
    st = {"n": 0, "hard": [], "soft": 0, "prose": []}
    for key, ln in pairs:
        st["n"] += 1
        ww = w(ln)
        if FAM_PROSE.match(key):
            if ww > SOFT:                    # 档③：长文体的每一行都得是 ≤14 的**段**
                st["prose"].append((key, ww, ln[:28]))
            continue
        if ww > HARD:                        # 档①：非长文体 >20 = 排版事故
            st["hard"].append((key, ww, ln[:28]))
        elif FAM_SOFT.search(key) and ww > SOFT:
            st["soft"] += 1                  # 档②：只统计
    return st


print("探针：全屏行宽（档①>%d 硬红 · 档② %d–%d 只记警告 · 档③ 长文体按 ≤%d 分段）"
      % (HARD, SOFT, HARD, SOFT))

# ---------------- ① texts 域（零漏） ----------------
TX = json.load(io.open(str(REPO / "content" / "data" / "texts.json"), encoding="utf-8"))
tx_pairs = []
for _k, _v in TX.items():
    _val = _v.get("value") if isinstance(_v, dict) else str(_v)
    for _ln in str(_val).split("\n"):
        if _ln.strip():
            tx_pairs.append((_k, _ln))
st_tx = audit(tx_pairs)
_n_slots = sum(1 for _k, _v in TX.items()
               if str((_v.get("value") if isinstance(_v, dict) else _v) or "").strip())
chk("① texts 域**零漏**：%d 个非空槽位逐槽位扫到（渲染行 %d 行 · 不抽样）"
    % (_n_slots, st_tx["n"]), len(TX) == _n_slots and st_tx["n"] >= _n_slots,
    "域内槽位 %d" % len(TX))

# ---------------- ② dialogues 域 ----------------
DL = json.load(io.open(str(REPO / "content" / "data" / "dialogues.json"), encoding="utf-8"))
dl_pairs, _n_blocks = [], 0
for _t, _r in DL.items():
    for _nd in (_r.get("nodes") or {}).values():
        for _x in (_nd.get("texts") or []):
            _n_blocks += 1
            for _ln in (_x.get("text") or "").split("\n"):
                if _ln.strip():
                    dl_pairs.append((_t, _ln))
st_dl = audit(dl_pairs)
chk("② dialogues 域：%d 条台词 / %d 棵树逐行扫到（渲染行 %d 行）"
    % (_n_blocks, len(DL), st_dl["n"]), st_dl["n"] > 0)

# ---------------- ③ 档①（棘轮：只许变少） ----------------
_hard = sorted(st_tx["hard"] + st_dl["hard"], key=lambda x: -x[1])
chk("③ 档① 硬上限 %d：非长文体行超宽 = 排版事故 ⇒ 现值 **%d 行**（棘轮上限 %d，不许变多）"
    % (HARD, len(_hard), _RATCHET["hard"]), len(_hard) <= _RATCHET["hard"],
    "最宽 3 条：" + "；".join("%s %.0f宽" % (k, v) for k, v, _ in _hard[:3]))

# ---------------- ④ 档③（棘轮：只许变少） ----------------
_pu = sorted(st_tx["prose"] + st_dl["prose"], key=lambda x: -x[1])
chk("④ 档③ 长文体（SCENE/READ/HELP/NOTE）每段 ≤ %d：现值 **%d 段超**（棘轮上限 %d，不许变多）"
    % (SOFT, len(_pu), _RATCHET["prose"]), len(_pu) <= _RATCHET["prose"],
    "最宽 3 段：" + "；".join("%s %.0f宽" % (k, v) for k, v, _ in _pu[:3]))

# ---------------- ⑤ 档② 只统计（不判红） ----------------
print("  · 档② 提示/问句（HINT/ASK/TIP/BAD/TOAST）14–%d：**%d 行**超软目标"
      " —— 只统计不判红（改它要动措辞，归文案车道）" % (HARD, st_tx["soft"] + st_dl["soft"]))

# ---------------- ⑥ 反证（判据不恒真） ----------------
_c = audit([("COMBAT_TEST", "啊" * 40), ("SCENE_TEST", "一" * 40), ("SYS_HINT_TEST_HINT", "啊" * 16)])
chk("⑥ 反证：塞进「超宽面板行 / 没分段的 SCENE / 超软目标的提示行」三条假数据 ⇒ "
    "档①抓 %d、档③抓 %d、档②计 %d（判据不恒真）"
    % (len(_c["hard"]), len(_c["prose"]), _c["soft"]),
    len(_c["hard"]) == 1 and len(_c["prose"]) == 1 and _c["soft"] == 1)

# ---------------- ⑦ 幂等可复算 ----------------
_st2 = audit(tx_pairs)
chk("⑦ 幂等可复算：同一份数据连算两次三档数字一致（档① %d / 档② %d / 档③ %d）"
    % (len(st_tx["hard"]), st_tx["soft"], len(st_tx["prose"])),
    (len(st_tx["hard"]), st_tx["soft"], len(st_tx["prose"]))
    == (len(_st2["hard"]), _st2["soft"], len(_st2["prose"])))

print()
print("实测：texts 槽位 %d · 渲染行 %d（>14 %d · >20 %d）｜ dialogues 台词 %d · 渲染行 %d（>14 %d · >20 %d）"
      % (len(TX), st_tx["n"], sum(1 for _k, _l in tx_pairs if w(_l) > SOFT), len(st_tx["hard"]),
         _n_blocks, st_dl["n"], sum(1 for _k, _l in dl_pairs if w(_l) > SOFT), len(st_dl["hard"])))
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
