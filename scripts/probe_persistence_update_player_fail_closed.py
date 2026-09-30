# -*- coding: utf-8 -*-
"""Audit L1701-sibling probe: content/persistence.py::update_player must not rebuild a save from {}.

The sibling read port (``get_player``) was made fail-closed for a corrupt save in the same audit
line (L1701).  The **write** port still collapsed the same corrupt row into ``{}``:

    cur = {}
    if row:
        try:
            cur = json.loads(row["data"])
        except Exception:            # <-- "库里那行坏了 => 从头来（不把坏数据当档）"
            cur = {}
    ...
    cur.update(fields)               # <-- read-modify-write on top of that empty dict

**Real cost (measured on the pre-fix code, not assumed).**  ``update_player`` is the write
side of the same save; a row that EXISTS but is unparseable became an empty dict, and then the
very next ordinary save operation (any command writing one field) overwrote the original
character sheet:

    1. normal save                 -> {'name': '鱼鱼', 'level': 7, 'gold': 9999}
    2. corrupt the JSON            -> update_player returns True (zero errors)
    3. read it back                -> {'name': '新名字', 'level': 1, 'gold': 0}   original destroyed

Same destruction as L1701, different entry point.  Making the read port fail-closed while the
write port keeps manufacturing empty saves leaves the hole open from the other side.

Fix: a row that exists with unparseable content (or a non-dict top level) raises, exactly as the
read port now does.  "No save" remains "the row does not exist" -- and that still creates a save
from ``{}`` legitimately, because a *new* player has no prior sheet to destroy.

This probe pins fail-closed semantics only; it does not relax any assertion.  It deliberately
does not assemble the package (the cross-lane formula regression makes every assembling probe
die at import time), so it drives the real production ports directly.
"""
from __future__ import annotations
import glob
import json
import os
import sqlite3
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, str(REPO))
sys.path.insert(0, os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine"))

ok = True


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s" % ("OK " if cond else "FAIL", label) + (("  -- %s" % (extra,)) if extra else ""))


DB = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "b2_probe_1701s.db")
for _f in glob.glob(DB + "*"):
    try:
        os.remove(_f)
    except OSError:
        pass

import content.persistence as PS  # noqa: E402

# Same injection shape as the host (host/store_factory.py -> inject_handles -> engine ->
# bind_host -> bind).  db_path is a plain path string, not a callable.
PS.bind(db_path=DB, clock=lambda: 0.0)


def _seed(gid, uid, **fields):
    """Create a normal save through the production ports (no hand-written table rows).

    ★ 2026-10-01（数据共享归一后）：所有 gid 落同一条 world 行 —— 各用例**自己隔离**：
      起手先删上一个用例留下的行（含 _corrupt 造的坏档），否则坏档漏给下一个 seed。
    """
    with PS.lock():
        c = PS.connect()
        try:
            c.execute("DELETE FROM %s WHERE group_id=? AND uid=?" % PS.TBL,
                      (PS.WORLD, str(uid)))
            c.commit()
        finally:
            c.close()
    PS.get_player(gid, uid)
    PS.update_player(gid, uid, **fields)
    return fields


def _corrupt(gid, uid, blob):
    c = sqlite3.connect(DB)
    c.execute("UPDATE %s SET data=? WHERE group_id=? AND uid=?" % PS.TBL, (blob, PS._world(gid), uid))
    c.commit()
    c.close()


def _raw(gid, uid):
    return sqlite3.connect(DB).execute(
        "SELECT data FROM %s WHERE group_id=? AND uid=?" % PS.TBL, (PS._world(gid), uid)).fetchone()[0]


# ── 1. the normal path must be byte-for-byte unchanged (read-modify-write keeps old cells) ──
print("[1] normal read-modify-write")
_seed("g1", "u1", name="鱼鱼", level=7, gold=9999)
chk("seed wrote the whole save", PS.get_player("g1", "u1") == {"name": "鱼鱼", "level": 7, "gold": 9999},
    repr(PS.get_player("g1", "u1")))
PS.update_player("g1", "u1", level=8)
chk("a one-field update keeps the other cells (read-modify-write, not replace)",
    PS.get_player("g1", "u1") == {"name": "鱼鱼", "level": 8, "gold": 9999},
    repr(PS.get_player("g1", "u1")))

# ── 2. a NEW player still legitimately starts from {} (do not over-constrain) ──
print("[2] a genuinely absent row still creates a save")
chk("no row -> get_player returns None (new player contract)",
    PS.get_player("g-brandnew", "u") is None)
chk("no row -> update_player still works (it is the create path)",
    PS.update_player("g-brandnew", "u", name="新人", level=1) is True)
chk("created save reads back", (PS.get_player("g-brandnew", "u") or {}).get("name") == "新人",
    repr(PS.get_player("g-brandnew", "u")))

# ── 3. THE DEFECT: a corrupt row must not be silently replaced by a fresh empty save ──
print("[3] corrupt row -> write port raises, original bytes untouched")
for tag, bad in (("unparseable JSON", "{坏JSON"), ("non-dict top level", '"我是字符串"'),
                 ("JSON array", "[1,2,3]")):
    gid = "g-" + tag.replace(" ", "-")
    _seed(gid, "u", name="鱼鱼", level=7, gold=9999)
    _corrupt(gid, "u", bad)
    before = _raw(gid, "u")
    try:
        PS.update_player(gid, "u", name="新名字", level=1, gold=0)
        chk("%s: update_player raises" % tag, False, "it returned silently (rc=True)")
    except RuntimeError as _e:
        chk("%s: update_player raises" % tag, True)
    chk("%s: the failed write left the row bytes unchanged" % tag, _raw(gid, "u") == before,
        repr(_raw(gid, "u")[:60]))

# ── 4. the sibling read port must agree (both ports share one caliber) ──
print("[4] read and write ports share one caliber")
_corrupt("g1", "u1", "{坏JSON")
try:
    PS.get_player("g1", "u1")
    chk("get_player raises on the same corrupt row", False, "it returned None (= new player)")
except RuntimeError:
    chk("get_player raises on the same corrupt row", True)

# ── 5. anti-regression: the pre-fix collapse must not come back through any shape ──
print("[5] anti-regression: no silent 'from scratch' path left in the write port")
src = open(os.path.join(REPO, "content", "persistence.py"), encoding="utf-8").read()
body = src.split("def update_player", 1)[1]
body = body.split("\ndef ", 1)[0]
# the only tolerated 'cur = {}' is the one that runs when there is NO row (the create path);
# a second one, or any 'except ... : cur = {}', would resurrect the defect.
except_blocks = [ln.strip() for ln in body.splitlines() if ln.strip().startswith("except")]
chk("the write port has no 'except -> cur = {}' swallow left",
    not any("cur = {}" in ln for ln in except_blocks), repr(except_blocks))
chk("the write port never rebuilds from {} when a row existed",
    body.count("raise RuntimeError") >= 2,
    "raise RuntimeError x%d" % body.count("raise RuntimeError"))
chk("the write port still creates from {} for a genuinely absent row",
    "cur = {}" in body)

print("RESULT: %s" % ("PASS" if ok else "FAIL"))
sys.exit(0 if ok else 1)
