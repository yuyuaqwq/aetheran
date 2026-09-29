# -*- coding: utf-8 -*-
"""探针：本批文件面上 **5 个零引用公共函数已删**（afix2 第 17 轮 · Step 1 五项核查）。

台账没点名这 5 个 —— 它们是「扫零引用 def」这一族扫出来的（前三轮扫的族都干净）。
删除判据 = **Step 1 五项核查全空**：

  ① 生产代码 import / 调用      —— 三仓 + 宿主四根，`.py` 全量 0 命中
  ② 包 `__init__` 是否 re-export —— 四文件**都没有** `__all__`，也未出现在任何 import 行
  ③ **门禁 / 探针是否 import** —— `scripts/` + `tests/` 零命中（这是最容易漏、也最致命的一项：
     上一轮车道就因为只扫生产面而误归档过一份门禁共享助手）
  ④ 文档 / 文案 / 配置字符串    —— `.md` + `.json` 零命中
  ⑤ 动态派发面                 —— 全包无 `getattr(<mod>, "<name>")`、无 `__dict__` 遍历、
                                 无序列化白名单点名（逐个名字查过）

★ 为什么它们是**死代码**而不是「声明了没接线的功能」（Step 2a 那一类）：
  逐个读过消费端，**同一份语义在别处已经实现了**，它们是重复的旁路入口：
  · `party.is_captain`      —— 邀请路径 `invite()` 走的是 `membership(...)["role"]`（:412），
                              不是这个函数；`is_captain` 只是把同一行判断重写一遍
  · `affix.axes_of`         —— `roll()` 内联了一份同形的 `used_axes` 累加（:149），
                              抽出来的那个函数没人调
  · `eggs.pair_of`          —— 8 条 `pair` 数据在册，但**没有任何消费端**读它
  · `calendar.crowd_text_at`—— 事件文案走 `texts.json` 槽位直读
  · `calendar.last_refresh` —— `ev` 那一格由 `timed_events.py` 写、`crowd_roster` 读，
                              `last_refresh` 这条呈现口没接

本探针钉「别写回来」：同名符号重新出现（含改名绕开的同形）当场报红。
"""
from __future__ import annotations

import ast
import io
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
HOST = os.environ.get("GWEN_HOST", "C:/Users/yuyu/qqbot/data/plugins/dragonfall")
# ★ 第四根不算独立真源：宿主的 `framework/games/aetheran` 是本仓的
#   **symlink**（os.path.realpath 逐字相等），扫两遍只是同一份代码数两次
#   —— 就算两根全绿，也拒绝了一个名字在主机上被别复制的情形。
#   同一个教训（上一轮门禁 G1b）：“两个数完全一样”先疑同一份被数两遍。
ROOTS = [REPO, ENGINE, os.path.join(ENGINE, "games", "orlandia")]

fails: list = []
ok = lambda m: print("  \u2713 " + m)
bad = lambda m: (fails.append(m), print("  \u2717 " + m))
chk = lambda label, cond, extra="": (ok if cond else bad)(
    label + (("  \u2014\u2014 %s" % extra) if extra else ""))

TARGETS = {
    "content/party.py": "is_captain",
    "content/affix.py": "axes_of",
    "content/eggs.py": "pair_of",
    "content/calendar.py": "crowd_text_at",
    "content/calendar.py": "last_refresh",
}

# \u2500\u2500 \u4e00\u3001\u4e94\u9879\u6838\u67e5\u4ecd\u7136\u6210\u7acb\uff08\u5220\u9664\u524d\u5e94\u8be5\u6210\u7acb\uff0c\u4fee\u6b63\u540e\u4ecd\u5e94\u6210\u7acb\uff09
print("\u4e00\u3001\u5220\u9664\u5e94\u4e3a\u5f0f\uff1a\u4e94\u4e2a\u540d\u5b57\u5728\u4e24\u4e2a\u76ee\u6807\u6587\u4ef6\u91cc\u5df2\u4e0d\u5b58\u5728")
for rel, name in sorted(TARGETS.items()):
    path = os.path.join(REPO, rel)
    src = io.open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    names = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    chk("%-24s `def %s` 已消失（且全文件无同名 def）" % (rel, name), name not in names,
        sorted(x for x in names if x == name))

# \u2500\u2500 \u4e8c\u3001\u56db\u6839\u4e00\u8ddf\u96f6\u547d\u4e2d\uff08\u542b\u4e3b\u673a\u955c\u50cf\uff09
print("\n4e00\u3001\u56db\u6839\u4e00\u8ddf\u96f6\u547d\u4e2d\uff08\u8fd8\u8981\u6db5\u76d6 .py/.md/.json \u4e0e\u4e3b\u673a\u955c\u50cf\u4ed3\uff09")
SKIP = {"__pycache__", ".git", "node_modules"}
for rel, name in sorted(TARGETS.items()):
    hits = []
    for root in ROOTS:
        if not os.path.isdir(root):
            continue
        for dp, dn, fn in os.walk(root):
            if any(s in dp for s in SKIP):
                continue
            for f in fn:
                if not f.endswith((".py", ".md", ".json")):
                    continue
                p = os.path.join(dp, f)
                try:
                    txt = io.open(p, encoding="utf-8", errors="replace").read()
                except OSError:
                    continue
                for i, line in enumerate(txt.splitlines(), 1):
                    if re.search(r"\b%s\b" % re.escape(name), line):
                        # \u672c\u63a2\u9488\u81ea\u8eab\u5199\u4e86\u90a3\u4e94\u4e2a\u540d\u5b57\uff08\u6b63\u6587\u91cc\u5fc5\u987b\u5b58\u5728\uff09\uff0c\u4e0d\u81ea\u6b63
                        if os.path.abspath(p) == os.path.abspath(__file__):
                            continue
                        hits.append("%s:%d" % (p.replace("\\", "/"), i))
    chk("%-24s `%-16s` 四根零命中" % (rel, name), not hits, hits[:3])

# \u2500\u2500 \u4e09\u3001\u6d3b\u529f\u80fd\u672a\u53d7\u5f71\u54cd\uff08\u771f\u8dd1\uff09
print("\u4e09\u3001\u6d3b\u529f\u80fd\u4e00\u6b63\u4e00\u6837\uff1a\u771f\u8c03\u4e00\u6b21\u76f8\u5173\u63a2\u9488")
sys.path.insert(0, REPO)
sys.path.insert(0, ENGINE)
sys.path.insert(0, os.path.join(ENGINE, "extends"))
for mod, fn in (("content.party", "invite"), ("content.affix", "roll"),
                ("content.calendar", "crowd_roster"), ("content.eggs", "entry")):
    try:
        m = __import__(mod, fromlist=[fn])
        chk("%-18s.%s 仍可导入可调" % (mod, fn), callable(getattr(m, fn, None)))
    except Exception as e:                                             # noqa: BLE001
        bad("%-18s 导入失败：%r" % (mod, e))

print("\nTOTAL %d \u6761\u5224\u636e" % (len(TARGETS) * 2 + 4))
if fails:
    print("\u7ed3\u679c\uff1a%d \u6761\u62a5\u7ea2" % len(fails))
    sys.exit(1)
print("\u7ed3\u679c\uff1a\u5168\u7eff")
