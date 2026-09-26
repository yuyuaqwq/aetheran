# -*- coding: utf-8 -*-
"""探针：**每一支生成器都必须能重跑**（生成器幂等门禁 · P-41 起常驻）。

为什么要有它（P-41 的教训）
--------------------------------------------------
`rebuild_equip_events.py` 在 B3-21 给 items 补完机器键 `kind_key` 之后**重跑即炸**：

    RuntimeError: 已存在且与本次口径逐字不同：{... 'kind_key': 'keepsake' ...}

它不在任何探针门禁里 ⇒ 这处「产物与生成器两处口径打架」从波九一路留到 P-41，
期间台账每轮都写「生成器复跑 0 漂移」—— 那一遍里就没有它。
**门禁不覆盖的地方就是会烂的地方**：数据包里的表多半是生成物，「能重跑」= 那批数据的生命线。

判据
--------------------------------------------------
① 覆盖面：仓库里的 `scripts/rebuild_*.py` 与**期望名单**逐支一致（多一支 / 少一支都红）。
② `--dry` 下 **rc=0**，而且**连跑两遍都要绿** —— 第一遍红多半就是「两处口径打架」，
   第二遍红才是自身不幂等。
③ 干跑**一个字节都不许写**：跑之前 / 之后比对 `content/` 下每个文件的 **md5 与 mtime_ns**。
   （只看 md5 不够 —— 「写了一份一样的」也过；mtime 才证明 `--dry` 真被认下来了。）
④ 名单里每一支的源码里必须出现 `--dry` 这个字面量 —— 否则「rc=0 且没写」可能只是
   因为它在 `--dry` 下压根不做那一步。

用法：`GWEN_ENGINE=... python scripts/probe_generators.py`（Python 3.12）
"""
import glob
import hashlib
import os
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENG = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
PY = sys.executable

#: ★ 期望名单（= `scripts/rebuild_*.py`，逐支跑 `--dry`）。**新生成器进来要同时改这里**：
#:   这一行就是「哪些产物有重跑门禁」的明细 —— 别让生成器在暗处长出来。
EXPECT = [
    "rebuild_bare_patterns.py",
    "rebuild_calendar.py",
    "rebuild_codex.py",
    "rebuild_eggs.py",
    "rebuild_equip_events.py",
    "rebuild_events.py",
    "rebuild_gathering.py",
    "rebuild_item_reqs.py",
    "rebuild_kind_keys.py",
    "rebuild_monsters.py",
    "rebuild_place_alias.py",
    "rebuild_prof_quests.py",
    "rebuild_quest_gates.py",
    "rebuild_ranks.py",
    "rebuild_recipes.py",
    "rebuild_scenes.py",
    "rebuild_shop.py",
    "rebuild_skills.py",
    "rebuild_syscopy.py",
    "rebuild_titles.py",
]

_pass, _fail = [], []


def chk(name, cond, seen=""):
    (_pass if cond else _fail).append(name)
    print("  %s %s%s" % (chr(0x2713) if cond else chr(0x2717), name,
                        ("  —— %s" % (seen,)) if seen else ""))


def _snapshot():
    """`content/` 下每个文件（不含 .pyc）的 (md5, mtime_ns, size)。"""
    out = {}
    for root, _dirs, files in os.walk(os.path.join(REPO, "content")):
        if os.sep + "__pycache__" in root:
            continue
        for fn in files:
            if fn.endswith(".pyc"):
                continue
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, REPO).replace(os.sep, "/")
            with open(p, "rb") as f:
                h = hashlib.md5(f.read()).hexdigest()
            st = os.stat(p)
            out[rel] = (h, st.st_mtime_ns, st.st_size)
    return out


def _diff(a, b):
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def _run(script):
    env = dict(os.environ)
    env["PYTHONPATH"] = ENG + os.pathsep + env.get("PYTHONPATH", "")
    env["GWEN_ENGINE"] = ENG
    t0 = time.time()
    p = subprocess.run([PY, os.path.join("scripts", script), "--dry"], cwd=REPO, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900)
    tail = ""
    body = p.stdout.decode("utf-8", "replace").strip().splitlines()
    if body:
        tail = body[-1].strip()[:160]
    return p.returncode, tail, time.time() - t0


print("══ ① 覆盖面：仓库里的生成器 == 期望名单（%d 支）" % len(EXPECT))
_found = sorted(os.path.basename(x) for x in glob.glob(os.path.join(REPO, "scripts", "rebuild_*.py")))
chk("① 逐支一致（多出来的 %s · 名单里有而仓库没有的 %s）"
    % (sorted(set(_found) - set(EXPECT)) or "无", sorted(set(EXPECT) - set(_found)) or "无"),
    _found == sorted(EXPECT), "实测 %d 支" % len(_found))

print()
print("══ ④ 每一支都真认 `--dry`（源码里有这个字面量）")
_noflag = []
for s in EXPECT:
    src = open(os.path.join(REPO, "scripts", s), encoding="utf-8").read()
    if '"--dry"' not in src:
        _noflag.append(s)
chk("④ %d 支全都认识 `--dry`" % len(EXPECT), not _noflag, "缺的：%s" % (_noflag or "无"))

print()
print("══ ②③ 逐支干跑两遍：rc=0 且一个字节都不许写（md5 + mtime 两样都看）")
_t0 = time.time()
_written_total = 0
for s in EXPECT:
    b = _snapshot()
    rc1, tail1, dt1 = _run(s)
    m = _snapshot()
    rc2, tail2, dt2 = _run(s)
    a = _snapshot()
    w = _diff(b, m) + _diff(m, a)
    _written_total += len(w)
    detail = ""
    if rc1 != 0 or rc2 != 0:
        detail = "rc=%d/%d · %s" % (rc1, rc2, (tail1 or tail2))
    elif w:
        detail = "写了：%s" % (w[:4],)
    chk("②③ %-24s 干跑两遍 rc=0 且零写入" % s,
        rc1 == 0 and rc2 == 0 and not w,
        detail or "rc=%d/%d · 写入 0 处 · %.1fs + %.1fs" % (rc1, rc2, dt1, dt2))
chk("③ 全部生成器干跑期间 `content/` 零写入（%d 个文件被盯着）" % len(_snapshot()),
    _written_total == 0, "写入 %d 处" % _written_total)

print()
print("══ 汇总（总耗时 %.1fs）" % (time.time() - _t0))
print("  通过 %d · 失败 %d" % (len(_pass), len(_fail)))
if _fail:
    for x in _fail:
        print("  %s %s" % (chr(0x2717), x))
    sys.exit(1)
print("  结果：全绿 %s" % chr(0x2713))
