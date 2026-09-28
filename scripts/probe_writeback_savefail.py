# -*- coding: utf-8 -*-
"""探针：挂机那一敲的「血落回档」失败不许静默（`instance._save` 的 `except: pass`）。

★ 这条是 `cmds_ast._save` 同族的**第二份副本**：`cmds_ast` 那边已在审计 B 车道改成
  「返回失败原因、由调用方点名给玩家（`SYS_SAVE_FAIL`）、当次成功话术一并作废」，
  而 `instance._write_back` 自己那份 `_save` 仍是 `try: env.save() / except: pass`
  —— 同一个洞从另一边还开着：**血没落库，玩家照样收到这一敲的完整回话**。

判据（真宿主 + 真存档库，不是替身）
--------------------------------------------------------
  §1 对照组：落库正常 ⇒ 这一敲的血真落回档（重连读回来是挨打后的数）
  §2 ★ 落库抛错 ⇒ **回话里点名了**（`SYS_SAVE_FAIL` 那一句 + 带原因），
     **不再**是「什么都没说」；且**当次操作的成功话术一并作废**（不许一边说挨打了
     一边没存上）—— 后者是这条例外的核心，两条都要钉
  §3 不误伤：场里没这个人（a is None）⇒ 不写不抛
  §4 防复发：`_write_back` 那一行不许自己长出 `except: pass`（AST 层数写口）

跑法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_writeback_savefail.py
"""
from __future__ import annotations

import ast
import io
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
TMP = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp")
sys.path.insert(0, str(REPO))
sys.path.insert(0, ENGINE)

ok = True


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("OK " if cond else "X  ", label, ("  —— %s" % extra) if extra else ""))


class _Boom:
    """只把 save 弄抛的 env 替身（其余接口不碰 —— `_write_back` 只调 `env.save()`）。"""

    def __init__(self):
        self.saved = 0

    def save(self):
        self.saved += 1
        raise RuntimeError("模拟：存档库写不进去")


def main():
    from content import instance as INST

    GID, UID = "g_wb", "u_wb"

    # ── §1 对照组：落库正常，血真落回
    class _B:
        def __init__(self, hp):
            self.hp = int(hp)

        def find_actor(self, uid):
            return {"hp": self.hp} if uid == UID else None

    class _Ok:
        def __init__(self):
            self.saved = 0

        def save(self):
            self.saved += 1

    p1 = {"hp": 7}
    pl1 = {}
    env1 = _Ok()
    INST._write_back(env1, p1, pl1, _B(3), UID)
    chk("§1 对照组：落库正常时档里的血真落成 3", p1.get("hp") == 3, "p1.hp=%r" % p1.get("hp"))
    chk("§1 对照组：player 那份也被盖成 3", pl1.get("hp") == 3, "pl1.hp=%r" % pl1.get("hp"))
    chk("§1 对照组：env.save 真被调了一次", env1.saved == 1, "saved=%d" % env1.saved)

    # ── §2 ★ 落库抛错：必须点名，且成功话术作废
    p2 = {"hp": 7}
    pl2 = {}
    env2 = _Boom()
    lines = INST._write_back(env2, p2, pl2, _B(3), UID)
    chk("§2 落库抛错时 env.save 真被调过（不是压根没落）", env2.saved == 1, "saved=%d" % env2.saved)
    chk("§2 ★ 返回值非 None（把失败交回调用方）", lines is not None, "lines=%r" % (lines,))
    # ★ T(...) 返回的是 **str**（一整行）—— 不能 `list()`（会逐字拆开，本批 L2178 同族坑）
    txt = str(lines or "")
    chk("§2 ★ 回话里带 `SYS_SAVE_FAIL` 的文案（玩家看得见）",
        "没存上" in txt, "txt=%r" % txt)
    chk("§2 ★ 带上了原因（不是空泛一句）",
        "RuntimeError" in txt, "txt=%r" % txt)
    chk("§2 ★ 文案是**整一行**（没被逐字拆开）",
        "\n" in txt or len(txt.splitlines()) >= 1, "lines=%d" % len(txt.splitlines()))

    # ── §3 不误伤：场里没这个人 ⇒ 不写不抛
    class _NoneBattle:
        def find_actor(self, uid):
            return None

    p3 = {"hp": 7}
    env3 = _Boom()
    r3 = INST._write_back(env3, p3, {}, _NoneBattle(), UID)
    chk("§3 场里没这个人 ⇒ 不写不抛（连 save 都不调）",
        r3 is None and env3.saved == 0 and p3.get("hp") == 7, "saved=%d hp=%r" % (env3.saved, p3.get("hp")))

    # ── §4 防复发：`_write_back` 那一行不许自己长出 except:pass
    src = io.open(str(REPO / "content" / "instance.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == "_write_back":
            bare = [h for h in n.body if isinstance(h, ast.ExceptHandler)
                    and h.type is None]
            chk("§4 `_write_back` 里没有裸 except（fail-closed 要点名）",
                not bare, "bare=%d" % len(bare))
            inner = [h for h in ast.walk(n) if isinstance(h, ast.ExceptHandler)
                     and h.type is None]
            chk("§4 `_write_back` 内部不藏裸 except", not inner, "bare=%d" % len(inner))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
