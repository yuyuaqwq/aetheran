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
    if hit6 == 6 and "还不知道自己是谁" in joined:
        ok("新号「观察」递六族菜单（命中 6/6）")
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
