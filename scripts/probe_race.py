# -*- coding: utf-8 -*-
"""探针：建号（选族）—— P-10。

判据（一条都不许松）：
  ① races 域 6 族齐 · 每族 2 正天赋 + 1 代价 · 每族都有 line（「为什么来」）
  ② order 是 1..6 且**互不相同**；菜单第一行是「人类」（照 02_种族体系 §四 表序）
  ③ 短名 → 域记录（`elf` → 精灵）—— 两处调用方共用 `_race_rec` 的口
  ④ 新号 `观察` 递菜单（不是风景）· 六族各一行
  ⑤ `我是 <族名>` 落档（race = 短名）· 回话含天赋与代价
  ⑥ 已经定过的族**不许改**（手滑换族会毁档）
  ⑦ 选了个不存在的族 ⇒ 报错但**不动档**
  ⑧ ★ 精灵 ⇒ eggs.ctx 的 `lore_scripts` 为真（彩蛋 3 的条件）；非精灵且没学铭文 ⇒ 假
  ⑨ ★ P-69（2026-09-26 · 本波 w-h-ux）：建号第 4 步「出身」**并进第 1 步**（裁决 + 依据见
     `content/cmds_ast.BUILD_STEPS` 的注释）—— 步表里没有 origin · 第 1 步里那句话出现两次 ·
     定完族递出的是第 2 步（没有「确认」那一屏）· `出身` 是回看口

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_race.py
"""
from __future__ import annotations

import io
import json
import os
import sys
import time

ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack            # noqa: E402
from saintess_engine.host.runtime import Host             # noqa: E402

OK, BAD = [], []


def ok(msg):
    OK.append(msg)
    print("  ✓ %s" % msg)


def bad(msg):
    BAD.append(msg)
    print("  ✗ %s" % msg)


class Ad:
    """最小适配器（照 scripts/e2e_drive.py 的真宿主契约）。"""

    def __init__(self):
        self.out = []
        self.saved = {}

    def recv(self):
        return None

    def load_player(self, uid):
        return self.saved.get(uid)

    def save_player(self, uid, data):
        self.saved[uid] = dict(data) if isinstance(data, dict) else data

    def say(self, to, text):
        self.out.append(str(text))


def drive(ad, host, text, uid="u_race_probe"):
    ad.out.clear()
    host.handle({"uid": uid, "group_id": "g_probe", "text": text})
    return list(ad.out)


def main():
    st = load_stack(str(REPO), inject={"db_path": ":memory:", "clock": time.time})

    with io.open(os.path.join(REPO, "content", "data", "races.json"), encoding="utf-8") as f:
        R = json.load(f)

    # ① 六族齐 · 2 正天赋 + 1 代价 · 有 line
    if len(R) == 6:
        ok("races 域 6 族")
    else:
        bad("races 域不是 6 族：%d" % len(R))
    miss = [k for k, v in R.items()
            if len(v.get("talents") or []) != 2 or not v.get("cost") or not v.get("line")]
    if not miss:
        ok("每族 2 正天赋 + 1 代价 + line（「为什么来」）")
    else:
        bad("这几族缺项：%s" % miss)

    # ② order
    orders = sorted(v.get("order") for v in R.values())
    if orders == [1, 2, 3, 4, 5, 6]:
        ok("order = 1..6 互不相同")
    else:
        bad("order 不对：%s" % orders)
    first = min(R.items(), key=lambda kv: kv[1].get("order") or 99)[0]
    if first == "race_human":
        ok("菜单第一行是人类（照文档表序）")
    else:
        bad("菜单第一行是 %s，应为 race_human" % first)

    # ③ 短名 → 域记录
    from content import cmds_ast as A
    got = A._race_rec("elf")
    if got.get("name") == "精灵":
        ok("短名 elf → 域记录（精灵）")
    else:
        bad("_race_rec('elf') 查不到：%r" % got)

    # ④~⑦ 走真宿主
    ad = Ad()
    host = Host(ad, REPO, inject={"db_path": ":memory:", "clock": time.time})
    stack = host.boot()
    uid = "u_race_probe"

    lines = drive(ad, host, "观察", uid)
    joined = "\n".join(lines)
    hit6 = sum(1 for n in ("人类", "精灵", "矮人", "兽人", "龙裔", "亚人") if n in joined)
    # ★ 2026-09-30（注册面改造）：菜单头与「怎么选」从 texts 域**现读** —— 文案再改这句跟着走；
    #   判据只管「菜单完整」（六族在 + 头句在 + 选法在），不再钉旧文案字面。
    with io.open(os.path.join(REPO, "content", "data", "texts.json"), encoding="utf-8") as _f:
        _TX_R = json.load(_f)
    _head_r = (_TX_R.get("SYS_RACE_HEAD") or {}).get("value", "")
    _how_r = (_TX_R.get("SYS_RACE_HOW") or {}).get("value", "")
    if hit6 == 6 and _head_r and _head_r in joined and _how_r and _how_r in joined:
        ok("新号「观察」递六族菜单（命中 6/6；头句与选法 = texts 域现值）")
    else:
        bad("新号第一眼不是菜单（命中 %d/6）：%s" % (hit6, joined[:140]))
    if "往哪走" not in joined:
        ok("新号第一眼**不是风景**（没给「往哪走」）")
    else:
        bad("新号第一眼仍然给了风景")

    lines = drive(ad, host, "我是 精灵", uid)
    j2 = "\n".join(lines)
    if "铭文之眼" in j2 and ("代价" in j2 or "体质单薄" in j2):
        ok("「我是 精灵」回话含天赋与代价")
    else:
        bad("选族回话缺天赋/代价：%s" % j2[:160])
    if (ad.saved.get(uid) or {}).get("race") == "elf":
        ok("落档 race = elf（短名）")
    else:
        bad("档上 race 不对：%r" % (ad.saved.get(uid) or {}).get("race"))

    j3 = "\n".join(drive(ad, host, "出身", uid))
    if "精灵" in j3 and "那块石头" in j3:
        ok("「出身」读得到「为什么来」（原来读 why，域里字段叫 line）")
    else:
        bad("「出身」没给出「为什么来」：%s" % j3[:140])

    # ⑨ ★ P-69（2026-09-26 · 本波 w-h-ux · **裁决：并进第 1 步，不拆**）
    #   真源 `18_建号与新手引导_v1.md §一` 把第 4 步「出身」写成**单独一步**（「只给一个选项（确认）」）——
    #   可那一屏的内容就是这句「为什么来」，而它**本来就出在第 1 步**：六族菜单每一行末尾带的就是它，
    #   定族那一下（`SYS_RACE_DONE`）再念一次。⇒ 拆出去 = 同一句话问两遍 + 一个纯点击的屏。
    #   本路裁：**不拆**（少一屏就少一个放弃点）。判据三条：
    #     ① 建号步表里**没有** origin（`content/cmds_ast.BUILD_STEPS` —— 那个常量就是这条裁决的落点）
    #     ② 并进的实证：第 1 步里那句话出现**两次**（菜单行 + 定族回话）
    #     ③ 定完族等着玩家的是**第 2 步**（中间没有「确认」那一屏）；`出身` 是**回看口**不是第 4 步入口
    from content import cmds_ast as _CA9                                        # noqa: E402
    _steps9 = tuple(getattr(_CA9, "BUILD_STEPS", ()))
    if _steps9 == ("race", "class", "name", "town") and "origin" not in _steps9:
        ok("★ P-69 建号步表 = %s —— **出身不单列**（并进第 1 步）" % (_steps9,))
    else:
        bad("★ P-69 建号步表不对：%r（应当 = ('race','class','name','town') 且不含 origin）"
            % (_steps9,))
    ad9 = Ad()
    host9 = Host(ad9, REPO, inject={"db_path": ":memory:", "clock": time.time})
    host9.boot()
    u9 = "u_race_probe9"
    _menu9 = drive(ad9, host9, "观察", u9)
    _done9 = drive(ad9, host9, "我是 人类", u9)
    _why9 = R["race_human"].get("line") or ""
    _in_menu9 = any(_why9 in ln for ln in _menu9)
    _in_done9 = any(_why9 in ln for ln in _done9)
    if _in_menu9 and _in_done9:
        ok("★ P-69 并进实证：那句「为什么来」在第 1 步里出现**两次**（菜单那一行 + 定族那一下）"
           "—— 第 4 步的内容已经在第 1 步里，再拆一屏就是把它问两遍")
    else:
        bad("★ P-69 并进实证不对：菜单里 %s · 定族回话里 %s" % (_in_menu9, _in_done9))
    _next9 = [ln for ln in _done9 if "还差一步" in ln]
    if _next9:
        ok("★ P-69 定完族等着玩家的是**第 2 步**（%s）—— 中间没有「确认」那一屏" % _next9[0][:34])
    else:
        bad("★ P-69 定完族没有递出第 2 步：%s" % (" | ".join(_done9))[:140])
    _orig9 = "\n".join(drive(ad9, host9, "出身", u9))
    if "人类" in _orig9 and _why9 in _orig9 and _orig9 != _orig9.replace(_why9, ""):
        ok("★ P-69 「出身」（`04 §三` · 守卫「随时」）是**回看口**：建完号照样读到同一句"
           "—— 它不是建号第 4 步的那个入口")
    else:
        bad("★ P-69 「出身」不像回看口：%s" % _orig9[:120])

    j4 = "\n".join(drive(ad, host, "状态", uid))
    if "精灵" in j4 and "race_elf" not in j4:
        ok("状态面板显示「精灵」（不漏机器键）")
    else:
        bad("面板没显示族中文名：%s" % j4[:140])

    j5 = "\n".join(drive(ad, host, "我是 兽人", uid))
    if "已经定了" in j5:
        ok("已定族不许改（回「你已经定了」）")
    else:
        bad("能改族：%s" % j5[:140])

    ad2 = Ad()
    host2 = Host(ad2, REPO, inject={"db_path": ":memory:", "clock": time.time})
    host2.boot()
    j6 = "\n".join(drive(ad2, host2, "我是 半精灵", "u_race_probe2"))
    if "没有叫" in j6:
        ok("不存在的族报错")
    else:
        bad("不存在的族没报错：%s" % j6[:140])
    cur = ad2.saved.get("u_race_probe2") or {}
    if not cur.get("race"):
        ok("不存在的族**不动档**（race 仍空）")
    else:
        bad("档被写了：%r" % cur.get("race"))

    # ⑧ 精灵 ⇒ lore_scripts（彩蛋 3 的条件）
    from content import eggs as EG
    if EG.ctx({"race": "elf"}).get("lore_scripts"):
        ok("精灵 ⇒ eggs.ctx 的 lore_scripts 为真（彩蛋 3 撞得上）")
    else:
        bad("精灵没有 lore_scripts")
    if not EG.ctx({"race": "orc"}).get("lore_scripts"):
        ok("非精灵没学铭文 ⇒ lore_scripts 为假")
    else:
        bad("非精灵也有 lore_scripts")

    print("\n----")
    print("通过 %d / 失败 %d" % (len(OK), len(BAD)))
    if BAD:
        print("红：")
        for b in BAD:
            print("  -", b)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
