# -*- coding: utf-8 -*-
"""Audit L1701 probe: content/persistence.py::get_player must not return None for a corrupt save.

Original code:
    if not row:
        return None
    try:
        v = json.loads(row["data"])
    except Exception:
        return None
    return v if isinstance(v, dict) else None

**Real cost (measured, not assumed).** The docstring one line above states the contract:
``None`` = new player (the engine will then ask the package for an initial save).  The
``except: return None`` therefore steals that meaning: a row that EXISTS but is unparseable
(storage truncated / encoding damage / interrupted migration) collapses into the *same* value
as "no such player" => the engine treats a long-running character as brand new, runs the
creation path, and the **next write permanently overwrites the original save**.

Measured on the pre-fix code (see the numbers in the commit message):
    1. normal save      -> {'name': '鱼鱼', 'level': 7, 'gold': 9999}
    2. corrupt the JSON -> get_player returns None   (indistinguishable from new player)
    3. engine re-creates-> row now {"name":"新名字","level":1,"gold":0}   original destroyed

The correct predicate for "no save" is **the row does not exist** -- a corrupt row is not
"absent".  This probe pins fail-closed semantics only; it does not relax any assertion.
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


DB = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "b2_probe_1701.db")
for _f in glob.glob(DB + "*"):
    try:
        os.remove(_f)
    except OSError:
        pass

import content.persistence as PS  # noqa: E402

# The host injects the handles (host/store_factory.py -> inject_handles -> engine -> bind_host
# -> bind).  Same shape here; db_path is a plain path string, not a callable.
PS.bind(db_path=DB, clock=lambda: 0.0)

# ---- 1. normal path, byte-for-byte unchanged (regression protection) ----
print("[1] normal path unchanged")
PS.update_player("g1", "u1", name="鱼鱼", level=7, gold=9999)
chk("save then read back", PS.get_player("g1", "u1") == {"name": "鱼鱼", "level": 7, "gold": 9999},
    repr(PS.get_player("g1", "u1")))
chk("absent player still returns None (NOT a failure)",
    PS.get_player("g1", "u_never_existed") is None, repr(PS.get_player("g1", "u_never_existed")))

# ---- 2. fail-closed: a corrupt row must raise, not masquerade as "new player" ----
print("[2] corrupt row must not collapse into None (= new player)")
for label, payload in (("truncated JSON", '{"name": "鱼鱼", "level":'),
                       ("not JSON at all", "\x00\x01garbage"),
                       ("top level is a list", '["a", "b"]'),
                       ("top level is a number", "12345")):
    c = PS.connect()
    c.execute("UPDATE %s SET data=? WHERE group_id=? AND uid=?" % PS.TBL, (payload, PS.WORLD, "u1"))
    c.commit()
    c.close()
    raised = None
    got = "<never assigned: it raised>"
    try:
        got = PS.get_player("g1", "u1")
    except Exception as e:                                    # noqa: BLE001 -- that is what we pin
        raised = e
    chk("%s => raises" % label, raised is not None, "returned %r (= new player)" % (got,))
    chk("%s => message names the save file" % label,
        raised is not None and "get_player" in str(raised), repr(raised))
    # 只有 json.loads 那一格才谈得上 __cause__；顶层非 dict 是我们自己抛的，没有底层异常。
    if label in ("truncated JSON", "not JSON at all"):
        chk("%s => original cause preserved" % label,
            raised is not None and raised.__cause__ is not None, repr(getattr(raised, "__cause__", None)))

# ---- 3. the cost the fix prevents: after a failed read, nothing gets written ----
# The engine's reaction to None is "ask the package for an initial save", and the first
# write that follows replaces the row.  So the thing to prove is: a failed read does not
# itself touch the row, and the pre-existing (corrupt but intact) bytes are still there --
# i.e. the save is recoverable, not silently overwritten.
print("[3] a failed read must not write anything / must leave the row intact")
PS.update_player("g2", "u2", name="阿斯特兰", level=42, gold=123456)
c = PS.connect()
c.execute("UPDATE %s SET data=? WHERE group_id=? AND uid=?" % PS.TBL,
          ('{"name": "阿斯特兰", "level":', PS.WORLD, "u2"))
c.commit()
c.close()
before = sqlite3.connect(DB).execute(
    "SELECT data FROM %s WHERE group_id='world' AND uid='u2'" % PS.TBL).fetchone()[0]
try:
    PS.get_player("g2", "u2")
    chk("corrupt save read raises (so the engine never re-creates it)", False, "read returned silently")
except Exception:                                             # noqa: BLE001
    chk("corrupt save read raises (so the engine never re-creates it)", True)
after = sqlite3.connect(DB).execute(
    "SELECT data FROM %s WHERE group_id='world' AND uid='u2'" % PS.TBL).fetchone()[0]
chk("the failed read wrote nothing (row bytes unchanged)", after == before, repr(after[:90]))

print("RESULT: %s" % ("PASS" if ok else "FAIL"))
sys.exit(0 if ok else 1)
