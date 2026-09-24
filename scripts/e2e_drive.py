# -*- coding: utf-8 -*-
"""端到端驱动：用**真宿主契约**（注入面齐全）跑本包，模拟玩家敲指令。

为什么不用 host-skeleton：它不给 inject，而本包声明了 bind（引擎 fail-closed 会拒）。
用法：python scripts/e2e_drive.py "观察" "往东" "观察"

★ `AST_E2E_SEED='{"bag":{...},"gold":200,"equipped":{...}}'` —— 给冒烟一个起手档
  （有些流程要手里先有东西才走得通：烹饪要有食材、强化要有装备与材料）。
"""
from __future__ import annotations

import os
import sys
import time

ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack            # noqa: E402
from saintess_engine.host.runtime import Host             # noqa: E402


class FakeAdapter:
    """三函数 + say + 两个可选钩子（照 host-api 契约的最小适配器）。"""

    def __init__(self, texts):
        self._msgs = [{"uid": "u_e2e", "group_id": "g_e2e", "text": t, "is_group": True}
                      for t in texts]
        self.out = []
        self.saved = None

    def recv(self):
        return self._msgs.pop(0) if self._msgs else None

    def load_player(self, uid):
        return self.saved if uid == "u_e2e" else None

    def save_player(self, uid, data):
        self.saved = dict(data) if isinstance(data, dict) else data

    def say(self, to, text):
        self.out.append(str(text))


def run(texts):
    ad = FakeAdapter(texts)
    seed = os.environ.get("AST_E2E_SEED")
    if seed:
        import json
        ad.saved = json.loads(seed)          # 起手档（宿主 load_player 会拿它当玩家档）
        print("  （起手档：%s）" % sorted(ad.saved))
    db = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_e2e.db")
    try:
        os.remove(db)
    except OSError:
        pass
    #: ★ 假钟：AST_E2E_EPOCH=<epoch> 可以让「时辰/天气」这条线可复现（默认走系统钟）
    fixed = os.environ.get("AST_E2E_EPOCH")
    clock = (lambda: float(fixed)) if fixed else time.time
    host = Host(ad, PKG, inject={"db_path": db, "clock": clock})
    if fixed:
        print("  （假钟 epoch=%s）" % fixed)
    stack = host.boot()
    print("== 装配 ==")
    print("  包:", stack.id, "| 域:", len(stack.domains),
          "| 指令声明:", len(stack.command_declarations()),
          "| 处理器:", len(stack.command_handlers()))
    print("== 走一遍 ==")
    n = 0
    for t in texts:
        ad.out.clear()
        host.handle({"uid": "u_e2e", "group_id": "g_e2e", "text": t})
        print("» %s" % t)
        for line in ad.out:
            print("   ", line)
        n += 1
    print("== 落档 ==")
    print("  ", {k: v for k, v in (ad.saved or {}).items() if k in ("loc", "node", "level", "gold")})
    return 0


if __name__ == "__main__":
    args = sys.argv[1:] or ["观察", "地图", "往东", "观察", "触摸", "返回", "观察", "搭话", "状态"]
    raise SystemExit(run(args))
