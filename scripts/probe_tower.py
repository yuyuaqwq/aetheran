# -*- coding: utf-8 -*-
r"""探针：旧哨塔副本（B3-6）—— 12 间房真能走一遍 · 五条指令真接上 · 9 项可读物真拿得到。

真源 = `06_第一阶段垂直切片/22_旧哨塔_逐间设计_v1.md`（**探针自己解析它** —— 不手抄镜像表）。
判据：

  ① 落地：`maps.old_watchtower` 的 12 间房与 §二 逐间块**逐条对得上**（层名 / 房名 / 顺序）
     · 每间都有节点级场景正文（`SCENE_<节点>` ≥80 字）
  ② 分层声明：`floors` 覆盖 12 间不重不漏 · 每层那几间与 §一 表一致 · `entrance` 是真节点
     · `roles.entry` 点的那间 = 文档第 1 间（塔门）
  ③ ★ 真进塔（真宿主 · 逐条真敲）：镇上 → 塔门 → 『进塔』 → 12 间逐间『去 <房间>』
     —— 每一间都到得了，到的就是文档那一间；每间的**出口**与 §二 逐条对
     （一步邻居 / 文档写「二选一」的那间至少一条通达 / 塔外那一格由『撤退』验）
  ④ 五条指令都有人接 —— 真敲回来的是真话（不是 `SYS_CMD_SOON` · 不漏内部 key / 文件路径）
  ⑤ ★ 9 项可读物：§一 点名的那几项，在文档说的那一间真拿得到（『读 <名>』 · 房间里的
     『触摸』也全都在）
  ⑥ 『撤退』真的出塔（回到 `entrance` 那一格）· 塔外敲塔里的事 fail-closed 说人话
  ⑦ P-19：`SCENE_OLD_WATCHTOWER` 不再是死槽位 —— 『进塔』那一屏取的就是它（且与节点级
     的塔门那一屏不是同一段字）
  ⑧ 三档空档都说人话：没站到本层最后一间 / 已经在塔顶 / 那一间没有可读物

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_tower.py
"""
from __future__ import annotations

import io
import os
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
PLAN = os.environ.get("AST_PLAN", "C:/Users/yuyu/aetheran-plan")
sys.path.insert(0, str(REPO))
sys.path.insert(0, ENGINE)

from saintess_engine.host.runtime import Host                      # noqa: E402
from saintess_engine.package import load_stack                     # noqa: E402

TOWER = "old_watchtower"
DOC = os.path.join(PLAN, "06_第一阶段垂直切片", "22_旧哨塔_逐间设计_v1.md")
FLOORS = ("一层", "二层", "三层")          # §二 逐间块的写法
TABLE_FLOORS = ("一", "二", "三")          # §一 总览表那一列的写法
MISSING = "[MISSING TEXT"
LEAKS = ("包内声明", "未提供处理器", "content/commands.py", "handler", "saintess_engine")

ok = True


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("OK " if cond else "X  ", label, ("  —— %s" % extra) if extra else ""))


# ══════════════════════════════════════════════════════════════
# 一、解析 22 号文档（唯一真源）
# ══════════════════════════════════════════════════════════════
def _read(p):
    return io.open(p, encoding="utf-8").read()


def _cells(line):
    return [c.strip().replace("**", "").replace("`", "") for c in line.strip().strip("|").split("|")]


def _plain(s):
    """去掉括号里的话（「（二选一，钥匙在 3 里）」「（数到 47 天停了）」这些是注解，不是名字）。"""
    return re.sub(r"（[^）]*）", "", str(s)).strip()


def _room_name(s):
    """`门厅 —— **A3 行动序**` → `门厅`（节标题里那截是「这一间教什么」，不是房名）。"""
    return re.split(r"\s*——\s*", str(s))[0].strip()


def parse_overview(text):
    """§一 那张总览表 → [(层, 序号, 房名, 教什么, 敌人, [可读物名…]), …]"""
    out = []
    for ln in text.split("\n"):
        s = ln.strip()
        if not s.startswith("|"):
            continue
        cs = _cells(s)
        if len(cs) != 5 or cs[0] not in TABLE_FLOORS:
            continue
        m = re.match(r"^(\d+)\s+(.+)$", cs[1])
        if not m:
            continue
        reads = [x.strip() for x in re.split(r"[·+]", _plain(cs[4])) if x.strip() and x.strip() != "——"]
        out.append((FLOORS[TABLE_FLOORS.index(cs[0])], int(m.group(1)), m.group(2).strip(),
                    cs[2], cs[3], reads))
    return out


def parse_rooms(text):
    """§二 逐间块 → {序号: {"floor":…, "name":…, "出口":…}}"""
    out, cur = {}, None
    for ln in text.split("\n"):
        h = re.match(r"^###\s+(\S+?)\s*·\s*(\d+)\s*·\s*(.+?)\s*$", ln)
        if h:
            cur = int(h.group(2))
            out[cur] = {"floor": h.group(1), "name": _room_name(h.group(3)), "exit": ""}
            continue
        if cur is None:
            continue
        if ln.startswith("```") or ln.startswith("###"):
            continue
        m = re.match(r"^(\S+)\s{2,}(.*)$", ln)
        if m and m.group(1) == "出口":
            out[cur]["exit"] = m.group(2).strip()
    return out


def exit_targets(raw, names):
    """`3 武器架室 / 4 楼梯前（二选一，钥匙在 3 里）` → ["武器架室", "楼梯前"]

    ★ 房名自己就带括号（哨所（外））⇒ 先按**真名字**匹配，匹配不上再当注解剥括号。
    """
    out = []
    for part in str(raw).split("/"):
        t = re.sub(r"^\s*\d+\s*", "", part).strip()
        if not t:
            continue
        hit = [n for n in names if t.startswith(n)]
        out.append(max(hit, key=len) if hit else _plain(t))
    return out


overview = parse_overview(doc := _read(DOC))
rooms = parse_rooms(doc)
by_no = {r[1]: r for r in overview}
chk("★ 22 号文档解析：§一 总览 12 行 · §二 逐间 12 块（层 / 房名 两处一致）",
    len(overview) == 12 and len(rooms) == 12
    and all(rooms[n]["floor"] == by_no[n][0] and rooms[n]["name"] == by_no[n][2] for n in rooms),
    "%d 行 / %d 块" % (len(overview), len(rooms)))
DOC_READS = []
for _f, _no, rname, _teach, _enemy, reads in overview:
    for rd in reads:
        DOC_READS.append((rname, rd))
chk("★ §一 点名的可读物 9 项（塔内那 9 项一块数）", len(DOC_READS) == 9,
    " · ".join(r[1] for r in DOC_READS))

# ══════════════════════════════════════════════════════════════
# 二、域（maps / pois / texts）
# ══════════════════════════════════════════════════════════════
st = load_stack(str(REPO), inject={
    "db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_tower.db"),
    "clock": time.time})
st.install()
MP = st.domain("maps") or {}
PO = st.domain("pois") or {}
TX = st.domain("texts") or {}
DECL = st.command_declarations()
TW = MP.get(TOWER) or {}
NODES = [n["id"] for n in (TW.get("nodes") or [])]
NAME_OF = {n["id"]: n["name"] for n in (TW.get("nodes") or [])}
ID_OF = {v: k for k, v in NAME_OF.items()}
GNAME = {n["id"]: n["name"] for m in MP.values() for n in (m.get("nodes") or [])}
ROOM_NAMES = [rooms[n]["name"] for n in sorted(rooms)]
chk("maps 域读得到旧哨塔（%d 间）" % len(NODES), bool(TW) and len(NODES) == 12)

print("① 12 间房落地（§二 逐间 · 逐条对）")
bad = []
for no in sorted(rooms):
    r = rooms[no]
    nd = NODES[no - 1] if no <= len(NODES) else ""
    if NAME_OF.get(nd) != r["name"]:
        bad.append("%d %s != %s" % (no, r["name"], NAME_OF.get(nd)))
chk("★ 12 间房按文档顺序落在 maps 上（房名逐条对）", not bad, "%s" % bad[:4])
short = [(nd, len((TX.get("SCENE_%s" % nd.upper()) or {}).get("value") or ""))
         for nd in NODES if len((TX.get("SCENE_%s" % nd.upper()) or {}).get("value") or "") < 80]
chk("★ 每间都有节点级场景正文（SCENE_<节点> ≥80 字）", not short, "%s" % short[:4])

print("② 分层与进塔那一格（数据声明）")
fl = [(str(f.get("name")), [str(x) for x in (f.get("rooms") or [])]) for f in (TW.get("floors") or [])]
flat = [r for _n, rs in fl for r in rs]
doc_by_floor = {f: [n for n in sorted(rooms) if rooms[n]["floor"] == f] for f in FLOORS}
chk("★ floors 覆盖 12 间 · 不重不漏（%s）" % " / ".join("%s %d" % (n, len(rs)) for n, rs in fl),
    flat == NODES and len(set(flat)) == 12,
    "floors=%s nodes=%s" % (flat, NODES))
chk("★ 每层的间序与 §一 表一致（层名 / 房名 逐条）",
    [n for n, _ in fl] == list(FLOORS)
    and all(fl[i][1] == [NODES[no - 1] for no in doc_by_floor[FLOORS[i]]] for i in range(len(fl))))
ent = TW.get("entrance") or {}
ent_ok = (ent.get("map") in MP
          and ent.get("node") in [n["id"] for n in (MP.get(ent.get("map")) or {}).get("nodes", [])])
chk("★ entrance 是真节点（跨图那一格 %s:%s）" % (ent.get("map"), ent.get("node")), ent_ok)
entry_role = (TW.get("roles") or {}).get("entry")
entry_node = next((n["id"] for n in (TW.get("nodes") or []) if n.get("role") == entry_role), None)
chk("★ roles.entry 点的那间 = 文档第 1 间「%s」" % rooms[1]["name"],
    NAME_OF.get(entry_node) == rooms[1]["name"], "%r" % entry_node)

scene_slot, gate_slot = TX.get("SCENE_OLD_WATCHTOWER") or {}, TX.get("SCENE_TOWER_GATE") or {}
scene_val = scene_slot.get("value") or ""
chk("★ P-19 地图级槽位 SCENE_OLD_WATCHTOWER 有正文（%d 字 · 不是塔门那一屏）" % len(scene_val),
    80 <= len(scene_val) <= 200 and scene_val != (gate_slot.get("value") or ""),
    scene_val[:24])

# ══════════════════════════════════════════════════════════════
# 三、真宿主：镇上 → 塔门 → 进塔 → 12 间逐间走 → 调查 → 撤退
# ══════════════════════════════════════════════════════════════
print("③ 真宿主走一遍（真敲 · 逐条对文档）")


class _Ad(object):
    """三函数 + say（照 host-api 契约的最小适配器 —— 与 scripts/e2e_drive.py 同形）。"""

    def __init__(self):
        self._msgs = []
        self.out = []
        self.saved = {"loc": "windmill_town", "node": "wt_gate_n", "race": "human",
                      "level": 3, "gold": 50, "bag": {}, "equipped": {}, "codex": {},
                      "flags": {}, "prev": []}

    def recv(self):
        return self._msgs.pop(0) if self._msgs else None

    def load_player(self, uid):
        return self.saved if uid == "u_t" else None

    def save_player(self, uid, data):
        self.saved = dict(data) if isinstance(data, dict) else data

    def say(self, to, text):
        self.out.append(str(text))


_db = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_tower_e2e.db")
try:
    os.remove(_db)
except OSError:
    pass
ad = _Ad()
host = Host(ad, str(REPO), inject={"db_path": _db, "clock": time.time})
host.boot()
LOG = []


def send(text):
    ad.out.clear()
    host.handle({"uid": "u_t", "group_id": "g_t", "text": text})
    got = list(ad.out)
    LOG.append((text, got, (ad.saved.get("loc"), ad.saved.get("node"))))
    return got


def txt(slot, **kw):
    s = (TX.get(slot) or {}).get("value") or ""
    for k, v in kw.items():
        s = s.replace("{%s}" % k, str(v))
    return s


# 镇 → 塔门（跨两张图的那两步）
send("往北")
send("去 拾荒营地")
send("去 旧哨塔下")
chk("★ 从镇上走到塔门口（%s）" % GNAME.get(ent.get("node")),
    (ad.saved.get("loc"), ad.saved.get("node")) == (ent.get("map"), ent.get("node")),
    "%s" % ((ad.saved.get("loc"), ad.saved.get("node")),))

# ⑦ 进塔那一屏 = SCENE_OLD_WATCHTOWER（死槽位复活）
out = send("进塔")
chk("★ P-19『进塔』那一屏取的就是 SCENE_OLD_WATCHTOWER（不再是死槽位）",
    txt("SYS_TOWER_ENTER") in out and scene_val in out and bool(out),
    "%s" % [x[:20] for x in out])
entered = (ad.saved.get("loc"), ad.saved.get("node"))
chk("★ 进塔落在那间 = 文档第 1 间「%s」" % rooms[1]["name"],
    ad.saved.get("loc") == TOWER and ad.saved.get("node") == NODES[0], "%s" % (entered,))

# ⑤ 9 项可读物：逐项按名字『读』到（在文档说的那一间）
print("⑤ 9 项可读物（在文档说的那一间真拿得到）")
read_bad, read_seen = [], []
for rname, rd in DOC_READS:
    hits = [k for k, v in PO.items() if v.get("name") == rd]
    pid = hits[0] if len(hits) == 1 else ""
    rec = PO.get(pid) or {}
    slot = rec.get("read_text") or ""
    body = (TX.get(slot) or {}).get("value") or ""
    if (rec.get("kind") != "可读物" or rec.get("map") != TOWER
            or rec.get("subarea") != ID_OF.get(rname) or not body):
        read_bad.append((rd, len(hits), rec.get("map"), rec.get("subarea"), slot))
        continue
    # 把玩家挪到那一间（照文档那一间 —— 探针自己算 id，不靠手写表）
    node = ID_OF.get(rname)
    ad.saved = dict(ad.saved, loc=TOWER, node=node)
    got = send("读 %s" % rd)
    if txt("SYS_READ_HEAD", name=rd) not in got or body not in got:
        read_bad.append((rd, node, got[:2]))
        continue
    read_seen.append((rd, rname))
chk("★ §一 的 9 项可读物都能在文档说的那一间『读』到（逐条真敲）", not read_bad,
    "%s" % read_bad[:3])
chk("★ 9 项一条都不落在塔外（「拾荒人留的字条」已从 bn_camp 正位到 %s）"
    % NAME_OF.get(ID_OF.get("储藏室")),
    len(read_seen) == 9
    and not [(k, v.get("map")) for k, v in PO.items()
             if v.get("name") in [r[1] for r in DOC_READS] and v.get("map") != TOWER])

# 触摸：水房那两项一次全出（文档说这一间有两项）
water = ID_OF.get("水房")
ad.saved = dict(ad.saved, loc=TOWER, node=water)
touched = send("触摸")
blob = "\n".join(touched)
want_w = [(v.get("name"), (TX.get(v.get("read_text")) or {}).get("value"))
          for v in PO.values() if v.get("map") == TOWER and v.get("subarea") == water]
chk("★ 水房『触摸』把这一间的两项都念出来（%s）" % " · ".join(n for n, _v in want_w),
    len(want_w) == 2 and all(n in blob and v in blob for n, v in want_w))

# ③ 12 间逐间走（从塔门起，按文档顺序）+ 每间的出口对账
print("③ 真走：12 间逐间『去』+ 每间出口与 §二 逐条对")
ad.saved = dict(ad.saved, loc=TOWER, node=NODES[0], prev=[])
walk_bad, walked = [], [NODES[0]]
from content import cmds_ast as CA                                  # noqa: E402

for no in range(2, 13):
    want = rooms[no]["name"]
    got = send("去 %s" % want)
    if ad.saved.get("node") != ID_OF.get(want) or txt("SYS_MOVE_TO", name=want) not in got:
        walk_bad.append((no, want, ad.saved.get("node"), got[:2]))
    walked.append(ad.saved.get("node"))

chk("★ 从塔门逐间走得到全部 12 间（按文档顺序 · 每一间都真敲『去』）",
    len(walked) == 12 and len(set(walked)) == 12 and not walk_bad, "%s" % walk_bad[:3])

exit_bad = []
for no in sorted(rooms):
    here, raw = NODES[no - 1], rooms[no]["exit"]
    tg = exit_targets(raw, ROOM_NAMES)
    nb = CA._neighbors(TOWER, here)
    into = [t for t in tg if t in ID_OF]
    out_of = [t for t in tg if t not in ID_OF]
    if "二选一" in raw:
        hit = [t for t in into if ID_OF[t] in nb]
        if not hit:
            exit_bad.append((no, raw, nb))
    else:
        for t in into:
            if ID_OF[t] not in nb:
                exit_bad.append((no, raw, t, nb))
    for t in out_of:                       # 塔外那一格（塔下）—— 由『撤退』验，不在图里
        if t not in GNAME.get(ent.get("node"), ""):
            exit_bad.append((no, raw, t))
chk("★ 每间的出口与 §二 逐条对得上（一步邻居 / 二选一至少一条 / 塔外那格是 entrance）",
    not exit_bad, "%s" % exit_bad[:3])

# ⑧ 下一层：没站到本层最后一间 · 已经在塔顶
ad.saved = dict(ad.saved, loc=TOWER, node=NODES[1])
far = send("下一层")
chk("★ 没站到本层尽头：『下一层』说清最后一间是「%s」" % rooms[4]["name"],
    far == [txt("SYS_TOWER_NEXT_FAR", room=rooms[4]["name"])], "%s" % far[:1])
ad.saved = dict(ad.saved, loc=TOWER, node=NODES[3])
up = send("下一层")
chk("★ 站到本层尽头：『下一层』上到 %s 的「%s」（并给新一屏）"
    % (FLOORS[1], rooms[5]["name"]),
    up[0] == txt("SYS_TOWER_UP", floor=FLOORS[1], room=rooms[5]["name"])
    and (TX.get("SCENE_%s" % NODES[4].upper()) or {}).get("value") in up
    and ad.saved.get("node") == NODES[4], "%s" % up[:2])
ad.saved = dict(ad.saved, loc=TOWER, node=NODES[11])
top = send("下一层")
chk("★ 已经在塔顶：说「没有上一层了」（不是沉默 / 不是报错）",
    top == [txt("SYS_TOWER_TOP_NONE")], "%s" % top[:1])

# 副本地图：抬头 + 这一层那几间 + 走过标记 + 尾注
ad.saved = dict(ad.saved, loc=TOWER, node=NODES[0], foot={"nodes": {"%s:%s" % (TOWER, NODES[1]): 1}})
mp_out = send("副本地图")
head = txt("SYS_TOWER_MAP_HEAD", name=TW.get("name"), floor=FLOORS[0], n=1, all=len(FLOORS))
rows = [x for x in mp_out[1:] if x.strip().endswith(")")]
chk("★ 副本地图：抬头 =【%s · %s】· 这一层四间逐行 · 脚下那间标 HERE · 走过的标（走过）"
    % (TW.get("name"), FLOORS[0]),
    mp_out[0] == head
    and len([x for x in mp_out if any(NAME_OF[r] in x for r in fl[0][1])]) == 4
    and any(NAME_OF[NODES[0]] in x and txt("SYS_MAP_HERE") in x for x in mp_out)
    and any(NAME_OF[NODES[1]] in x and txt("SYS_TOWER_MAP_SEEN") in x for x in mp_out)
    and txt("SYS_TOWER_MAP_TAIL", left=2) in mp_out, "%s" % mp_out)

# ⑧ 调查：有可读物那间逐条读出来 · 没有那间说没有
inv_bad = []
for no in sorted(rooms):
    rname = rooms[no]["name"]
    ad.saved = dict(ad.saved, loc=TOWER, node=ID_OF.get(rname))
    got = send("调查")
    mine = [rd for rn, rd in DOC_READS if rn == rname]
    if mine:
        for rd in mine:
            pid = next((k for k, v in PO.items() if v.get("name") == rd), "")
            body = (TX.get((PO.get(pid) or {}).get("read_text")) or {}).get("value") or ""
            if txt("SYS_READ_HEAD", name=rd) not in got or body not in got:
                inv_bad.append((rname, rd, got[:2]))
    elif got != [txt("SYS_TOWER_INV_NONE")]:
        inv_bad.append((rname, got[:2]))
chk("★ 『调查』：有可读物那几间逐条念出来 · 没有那几间说「没什么可查的」（12 间逐条真敲）",
    not inv_bad, "%s" % inv_bad[:3])

# ⑥ 撤退：真的出塔（回到 entrance 那一格）
ad.saved = dict(ad.saved, loc=TOWER, node=NODES[11], prev=[[ent.get("map"), ent.get("node")]])
lv = send("撤退")
chk("★ 『撤退』真的出塔（回到「%s」）" % GNAME.get(ent.get("node")),
    (ad.saved.get("loc"), ad.saved.get("node")) == (ent.get("map"), ent.get("node"))
    and txt("SYS_TOWER_LEAVE", name=GNAME.get(ent.get("node"))) in lv,
    "%s %s" % ((ad.saved.get("loc"), ad.saved.get("node")), lv[:1]))
back = send("返回")
chk("★ 出塔之后紧接着的『返回』不把玩家「返回」到他正站着的地方（prev 上那条弹掉了）",
    back and back[0] == txt("SYS_MOVE_BACK_NONE"), "%s" % back[:1])

# ⑥ 塔外敲塔里的事：五条都说同一句人话（fail-closed）
outs = {}
for cmd in ("进塔", "下一层", "副本地图", "调查", "撤退"):
    ad.saved = dict(ad.saved, loc="belt_north", node="bn_bone")
    outs[cmd] = send(cmd)
want_line = txt("SYS_TOWER_NOT_IN", name=GNAME.get(ent.get("node")))
chk("★ 塔外敲这五条：一律说「塔门在『%s』」那一句（不静默 · 不崩）" % GNAME.get(ent.get("node")),
    all(outs[c] == [want_line] for c in outs), "%s" % {c: outs[c][:1] for c in outs})

# ④ 五条指令真接上：不是 SYS_CMD_SOON · 不漏内部 key / 文件路径 / 取不到文案
soon = (TX.get("SYS_CMD_SOON") or {}).get("value") or ""
keys = [k for d in ("items", "monsters", "pois", "classes", "races", "quests", "gathering",
                    "drop_pools", "recipes", "npcs", "skills", "eggs", "titles", "dialogues",
                    "maps", "texts", "commands") for k in (st.domain(d) or {})]
leak = []
for cmd, got in list(outs.items()) + [(t, o) for t, o, _s in LOG]:
    for line in got:
        if MISSING in line or any(w in line for w in LEAKS):
            leak.append((cmd, line[:40]))
        if soon and soon.replace("{name}", "").split("「")[0] in line:
            leak.append((cmd, line[:40]))
chk("★ 五条指令都接上了（声明的 bind 到位 · 回话里没有 %s）" % MISSING, not leak, "%s" % leak[:3])
bound = [k for k in ("tower_enter", "tower_next", "tower_map", "tower_investigate", "tower_leave")
         if (DECL.get(k) or {}).get("bind")]
chk("★ 副本那 5 条声明都挂了 bind（%s）"
    % " · ".join((DECL.get(k) or {}).get("bind", {}).get("handler", "") for k in bound),
    len(bound) == 5)
handlers = len(st.command_handlers())
chk("★ 引擎认的处理器数是 %d（副本那 5 条在内）" % handlers, handlers >= 59)

print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
