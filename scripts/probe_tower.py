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
     （一步邻居 / 文档写「二选一」的那两间顺链可达且第一间就是下一步 / 塔外那一格由『撤退』验）
     · B3-10：**空手**走完全 12 间（P1 链式 = 无锁无分支；「钥匙」那条口径见 _notes.md §二）
  ④ 五条指令都有人接 —— 真敲回来的是真话（不是 `SYS_CMD_SOON` · 不漏内部 key / 文件路径）
  ⑤ ★ 9 项可读物：§一 点名的那几项，在文档说的那一间真拿得到（『读 <名>』 · 房间里的
     『触摸』也全都在）· 且**清单与 §一 那一列双向相等**（不多不少）
  ⑥ 『撤退』真的出塔（回到 `entrance` 那一格）· 塔外敲塔里的事 fail-closed 说人话
  ⑦ P-19：地图级槽位与进场那一间的节点级槽位是**同一处**（旧哨塔门口）—— 两个槽位名都由
     `content.scene` 现算（一个口 · 探针不手写槽位名）· 两屏逐字不同；真宿主里『进塔』给
     地图级（宽）· 站在这一间『观察』给节点级（窄），两屏各司其职、不打架
  ⑧ 三档空档都说人话：没站到本层最后一间 / 已经在塔顶 / 那一间没有可读物
  ⑨ ★ B3-7：塔内 12 间的「主要敌人」↔ `monsters.habitat` 逐间对齐（探针自己解析 §一 那一列 ·
     候选算法与 `combat.pick_encounter` 同一套）· 文档写「无」的那几间一只候选都算不出来
  ⑩ ★ B3-7：真敲『攻击』—— 12 间逐间遇上的就是文档说的那只；**层主 / Boss 那两间真打完一场**
     （原先档位白名单把它们挡在遭遇之外）· 镇上仍是安全区
  ⑪ ★ B3-7：三处容器（22 §二「可做」列里认出来的那三间）『搜查』真拿得到关键件 ——
     逐处换 24 个人 × 当日第 1/2 遍（`uid` 进采集种子）；到手那一刻旧物谱真多一行问号
  ⑫ ★ B3-10：塔内 9 项可读物分两档真跑 —— 就地线索 6 条（22 §二「可做」列）念得出正文但
     **旧物谱一条不加**；进谱的 3 条真多一行问号（照字出）
  ⑬ ★ P-66（2026-09-26 · 本波 w-h-ux · **裁决：两级槽位「不并」**）：每张图都有地图级槽位
     （「每图一条」的对称）· 节点级与地图级**是两条键**（不许一条退化成另一条的别名）·
     同一处两粒度两条都在、逐字不同（依据与真源行见本分支 `_notes.md §五`）
  ⑭ ★ fxa（P2 试玩 #2/#3）：**上楼那一道门两条路一起拦** —— 本层尽头那一间
     『下一层』与**房间级那一步**（`去 <上一层第一间>`）走同一个门（`_blocked_by` ⇒ 怪物谱）：
     没过手两处都拦（逐字同一句 · 位置不动）· 过了手两处都放行 · 往回走不拦（③-b 那一对）。
     且每一间『观察』都印「遇敌：」那一栏，**印出来的就是这一手真打的那只**（⑩ 里逐间比）。

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

from content import scene as SC                                    # noqa: E402

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
    """§二 逐间块 → {序号: {"floor":…, "name":…, "exit":…, "todo":…}}"""
    out, cur = {}, None
    for ln in text.split("\n"):
        h = re.match(r"^###\s+(\S+?)\s*·\s*(\d+)\s*·\s*(.+?)\s*$", ln)
        if h:
            cur = int(h.group(2))
            out[cur] = {"floor": h.group(1), "name": _room_name(h.group(3)), "exit": "", "todo": ""}
            continue
        if cur is None:
            continue
        if ln.startswith("```") or ln.startswith("###"):
            continue
        m = re.match(r"^(\S+)\s{2,}(.*)$", ln)
        if m and m.group(1) == "出口":
            out[cur]["exit"] = m.group(2).strip()
        elif m and m.group(1) == "可做":
            out[cur]["todo"] = m.group(2).strip()
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

# ⑦ P-19（★ 2026-09-26 本波 w5 收紧）：地图级槽位（宽）与进场那一间的节点级槽位（窄）是**同一处**
#   （旧哨塔门口 —— 地图 id `old_watchtower` / 那一间房 id `tower_gate`），原先两条键各写一份
#   `"SCENE_%s" % …upper()`，且地图级那条**代码里 0 引用**（死槽位）。现在：
#     · 两个槽位名**都由 `content.scene` 现算**（探针不再手写槽位名 —— K59/K65 那族）
#     · 同一个「场景」解析口有序分流：踏进这张图取**地图级**、站在节点上取**节点级**（先窄后宽兜底）
#     · 两屏**逐字不同**（同一处、两屏各司其职 —— 不许又变成「一条槽位两处写」）
_map_slot, _node_slot = SC.map_key(TOWER), SC.node_key(entry_node)
scene_slot, gate_slot = TX.get(_map_slot) or {}, TX.get(_node_slot) or {}
scene_val = scene_slot.get("value") or ""
gate_val = gate_slot.get("value") or ""
chk("★ P-19 地图级槽位 %s 有正文（%d 字 · 与节点级 %s 不是同一段字）"
    % (_map_slot, len(scene_val), _node_slot),
    80 <= len(scene_val) <= 200 and scene_val != gate_val, scene_val[:24])
chk("★ P-19 槽位/地图级写法**一个口**：`SC.map_key(%r)=%s` · `SC.node_key(%r)=%s`（都由 "
    "`content.scene` 现算）· 解析口分流对得上（地图级只认 `resolve_map` · 节点级先认 `resolve`）"
    % (TOWER, _map_slot, entry_node, _node_slot),
    _map_slot == "SCENE_" + TOWER.upper() and _node_slot == "SCENE_" + str(entry_node).upper()
    and SC.resolve_map(TX, TOWER) == _map_slot and SC.resolve(TX, TOWER, entry_node) == _node_slot
    and _map_slot != _node_slot)
# ★ 静态守卫（P-19「一个口」那把锁）：槽位键的**写法**全仓只有一处 —— `content/scene.py::slot_key`
#   （scene.py 里出现两次 = 唯一的实现 + 说明它为什么收口的注释引用）。节点级与地图级两条键都由它
#   算 ⇒「两个名字」只是**同一处**在两个粒度上的读法，不是两份写法。谁在别处再手写一次就红。
_WRITERS = {}
for _f in sorted((REPO / "content").rglob("*.py")):
    _t = _f.read_text(encoding="utf-8")
    _n = _t.count('"SCENE_%s"') + _t.count("'SCENE_%s'")
    if _n:
        _WRITERS[_f.name] = _n
chk("★ P-19 槽位键的**写法只有一个口**（带「SCENE_%%s」字样的文件只剩 content/scene.py · %s —— "
    "别处再手写一次（另一个名字的写法）就红）" % _WRITERS,
    set(_WRITERS) == {"scene.py"}, "%s" % _WRITERS)

# ⑬ ★ P-66（2026-09-26 · 本波 w-h-ux · **裁决：地图级与节点级两槽位「不并」**）
#   那条老账问的是「要不要把两级并成一个槽位」。裁 **不并**，依据三条：
#     ① **两级回答的是两个问题**：踏进这张图的**第一眼**（宽 · 「进门之后那一眼」）vs
#        站在这一**间**的近景（窄 · 塔门那一屏）—— 合并之后只剩一条，另一屏要么没词、
#        要么把宽的那段塞进窄的那一格（那就是「一条槽位两处写」，`⑦` 一直在防的那种）。
#     ② 「每图一条」的**对称**：本包 `maps` 里每一张图都有自己的地图级槽位（下面 ①）——
#        并对掉其中一条 = 那一张图的到达一屏没了（`_map_scene` 只剩一行占位）。
#     ③ 收益只是「少一处文案」，代价是两个粒度 + `rebuild_scenes` 的对账 + `⑦` 那三条判据
#        （`content/scene.py` 的注释里也写着这一条：两个名字只是同一处两个粒度的读法）。
#   ⇒ 判据 = 下面三条（谁哪天把两级并掉 / 让一条退化成另一条的别名，当场红）。
_MAPSLOTS13 = {loc: SC.map_key(loc) for loc in sorted(MP)}
_NODESLOTS13 = {loc: [SC.node_key(n["id"]) for n in (MP.get(loc) or {}).get("nodes") or []]
                for loc in sorted(MP)}
_miss13 = [loc for loc, k in _MAPSLOTS13.items() if k not in TX]
chk("★ P-66 不并 ①：每张图都有自己的**地图级**槽位（「每图一条」的对称）—— %s"
    % " · ".join("%s=%s" % (loc, k) for loc, k in _MAPSLOTS13.items()),
    bool(_MAPSLOTS13) and not _miss13, "缺：%s" % _miss13)
_alias13 = [(loc, k) for loc, ks in _NODESLOTS13.items() for k in ks if k in _MAPSLOTS13.values()]
chk("★ P-66 不并 ②：节点级槽位与地图级槽位**是两条键**（同一张图里没有任何一间的节点级槽位"
    "就是那张图的地图级槽位 —— 并成一条就是「一条槽位两处写」）", not _alias13, "%s" % _alias13)
chk("★ P-66 不并 ③：同一处两粒度（%s 宽 · %s 窄）两条都在 texts 里、各自被各自那一个解析口认到"
    " —— 谁也**不是**谁的别名"
    % (_map_slot, _node_slot),
    _map_slot in TX and _node_slot in TX and _map_slot != _node_slot
    and SC.resolve_map(TX, TOWER) == _map_slot and SC.resolve(TX, TOWER, entry_node) == _node_slot
    and bool(scene_val) and bool(gate_val) and scene_val != gate_val)
print("  · 登记（P-66）：裁决 = **不并** —— 依据（两级两个问题 · 每图一条的对称 · 收益只是少一处文案）"
      "已写进真源行（见本分支 `_notes.md §五`）；合并要动 %d 张图的图级槽位 + `rebuild_scenes`"
      " 对账 + 上面这三条判据。" % len(_MAPSLOTS13))

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
        #: ★ B3-7：容器那几处要**换人再搜一遍**（`uid` 进采集种子 —— 换人 = 换一串抽签）
        self.by_uid = {}

    def recv(self):
        return self._msgs.pop(0) if self._msgs else None

    def load_player(self, uid):
        if uid == "u_t":
            return self.saved
        return self.by_uid.get(uid)

    def save_player(self, uid, data):
        rec = dict(data) if isinstance(data, dict) else data
        if uid == "u_t":
            self.saved = rec
        else:
            self.by_uid[uid] = rec

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


def send_as(uid, text):
    """★ B3-7：换一个人敲同一条（容器那几处要换 uid —— 它进采集种子）。"""
    ad.out.clear()
    host.handle({"uid": uid, "group_id": "g_t", "text": text})
    got = list(ad.out)
    rec = ad.by_uid.get(uid) or {}
    LOG.append((text, got, (rec.get("loc"), rec.get("node"))))
    return got


# ★ G2（2026-09-26）：战斗改成**一手一推进** ⇒ 「这一场」跨指令落盘（单人的键 = `<群>#<uid>`）
_GID, _TUID = "g_t", "u_t"


def _field():
    """这一群里的那场（单人按人的那一格；没有 ⇒ None）。"""
    from content import instance as _INST
    return _INST.load(_INST.key_of(_GID, _TUID, [_TUID]))


def _clear_field():
    from content import instance as _INST
    _INST.clear(_INST.key_of(_GID, _TUID, [_TUID]))


def fight_over(cap=60):
    """把当前这一场**真收掉**（一条 `攻击` 只推一手）—— 返回收尾那几行。

    ★ 不收掉的话，下一间敲 `攻击` 会**接着上一场打**（遇不到这一间那只怪）。
    """
    got, n = [], 0
    while _field() is not None and n < cap:
        n += 1
        got += send("自动")
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

# ⑦ 进塔那一屏 = 地图级那一屏（死槽位复活）· 同一处**两屏各司其职**（真宿主）
out = send("进塔")
chk("★ P-19『进塔』那一屏取的就是地图级槽位 %s（不再是死槽位）" % _map_slot,
    txt("SYS_TOWER_ENTER") in out and scene_val in out and bool(out),
    "%s" % [x[:20] for x in out])
out_obs = send("观察")                       # 同一间（塔门）再『观察』⇒ 该给节点级那一屏
chk("★ P-19 同一处两屏不打架（真宿主）：『进塔』给地图级（宽）· 站在这一间『观察』给节点级（窄，%s）"
    % _node_slot,
    bool(out_obs) and bool(gate_val) and gate_val in out_obs and scene_val not in out_obs,
    "%s" % [x[:20] for x in out_obs])
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
# ★ B3-10：清单**双向相等** —— 塔内 kind=可读物 的那几条与 22 §一 那一列一模一样（不多不少；
#   多一条（比如顺手加的可读物）或少一条都会当场红）。
_want_names = sorted(r[1] for r in DOC_READS)
_got_names = sorted(str(v.get("name")) for v in PO.values()
                    if v.get("map") == TOWER and v.get("kind") == "可读物")
chk("★ 塔内可读物的清单 ↔ 22 §一「可读物」那一列**双向相等**（%d 项 · 不多不少）" % len(_want_names),
    _want_names == _got_names, "对不上的：%s" % sorted(set(_want_names) ^ set(_got_names)))

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
# ★ fxa（P2 试玩 #2/#3）：本层尽头那三间的**上楼闸**现在两条路都拦 —— 『下一层』
#   （fix5-nav 那一支）与**房间级那一步**（`去 <上一层第一间>`；原先直通，绕一步就把整层
#   守卫跳过去了）。所以这一节验的是**链本身**（12 间可达 / 无锁 / 每间出口对得上），
#   前提是**每层的守卫已经过手**（怪物谱那本账 —— 与 `_blocked_by` 判的是同一本账，
#   与『下一层』过了手才上得去那一支同理）。两态本身另有判据（下面 ③-b 那一对）。
_GUARDS = [f[1][-1] for f in fl]                       # 每一层尽头那一间（按数据现算）
_MID_ALL = st.domain("monsters") or {}


def _room_cands(node):
    """这一间按 `habitat` 算得出的候选（与 `combat.pick_encounter` 同一套规则）。"""
    return sorted(mid for mid, m in _MID_ALL.items()
                  if TOWER in [str(x) for x in ((m.get("habitat") or {}).get("maps") or [])]
                  and node in [str(x) for x in ((m.get("habitat") or {}).get("nodes") or [])])


_GUARD_MIDS = sorted({mid for _g in _GUARDS for mid in _room_cands(_g)})
ad.saved = dict(ad.saved, loc=TOWER, node=NODES[0], prev=[], bag={}, equipped={},
                books={"monster": {mid: {"day": 1, "kills": 1} for mid in _GUARD_MIDS}})
_bag_before = dict(ad.saved.get("bag") or {})
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
# ★ B3-10 收口：22 §二·2 出口写着「3 武器架室 / 4 楼梯前（二选一，**钥匙在 3 里**）」、
#   §三① 写「钥匙在每层的『资源房』里」—— 本批裁决：**P1 链式、不锁不分支**
#   （22 §三① 自己写「3 层线性推进」；3 / 8 号房本来就在必经路上 ⇒ 无门可锁）。
#   判据按文档那一行**逐条核**，但核的方式比原来严：
#     · 不带「二选一」的出口 = 链上**一步邻居**；
#     · 带「二选一」的两间 = 都在链上**顺链可达**（本步之后的某一间），且**第一间就是下一步**。
#   ⇒ 空手（`bag` 空）走完全 12 间那一条（上面那条判据）就是「无锁」的实证。
chk("★ 空手走完 12 间（没有任何锁 / 钥匙拦着 —— P1 链式的实证）",
    not _bag_before and not ad.saved.get("bag"), "走之前背包 %s" % _bag_before)

# ③-b ★ fxa（P2 试玩 #3「楼梯前那道守卫能整条绕过」）：**本层尽头那一步**的两态 ——
#   同一时刻『下一层』被挡着、`去 <上一层第一间>` 却直通 = 两条路给出互相矛盾的规则。
#   现在两处走**同一个门**（`_blocked_by` ⇒ 怪物谱那本账 · 名字同一个口 `foe_here`）：
#     · 没过手 ⇒ 同一句拦下（位置与历史一个字不动）；
#     · 过了手 ⇒ 真上到上一层第一间（反证：这一句不是「一律拦」）；
#     · 往回走那一步（不通往上一层）⇒ 一个字都不拦（反证：闸不是「这一间一律不许走」）。
print("③-b 本层尽头那一步（『去 <上一层第一间>』）的两态 + 往回走不拦")
step_bad = []
for fi in range(len(fl) - 1):
    _g = fl[fi][1][-1]                         # 这一层尽头那一间（楼梯口）
    _nxt, _prev = fl[fi + 1][1][0], fl[fi][1][-2]
    _gids = _room_cands(_g)
    if len(_gids) != 1:                        # 点名要点得准 ⇒ 守卫房只该有一只候选
        step_bad.append((_g, "这一间的候选不是一只（点名点不准）", _gids))
        continue
    _gname = str((_MID_ALL.get(_gids[0]) or {}).get("name") or _gids[0])
    _where, _want_blk = NAME_OF[_nxt], txt("SYS_TOWER_BLOCKED", name=_gname)
    ad.saved = dict(ad.saved, loc=TOWER, node=_g, books={}, prev=[])
    _blk = send("去 %s" % _where)
    if _blk != [_want_blk] or ad.saved.get("node") != _g:
        step_bad.append((_g, "没过手却走得动", _blk[:2], ad.saved.get("node")))
    ad.saved = dict(ad.saved, loc=TOWER, node=_g, prev=[],
                    books={"monster": {_gids[0]: {"day": 1, "kills": 1}}})
    _up = send("去 %s" % _where)
    if ad.saved.get("node") != _nxt or txt("SYS_MOVE_TO", name=_where) not in _up:
        step_bad.append((_g, "过了手却走不动", _up[:2], ad.saved.get("node")))
    ad.saved = dict(ad.saved, loc=TOWER, node=_g, books={}, prev=[])
    send("去 %s" % NAME_OF[_prev])
    if ad.saved.get("node") != _prev:
        step_bad.append((_g, "往回走那一步也被拦了（那一步不通往上一层）", NAME_OF[_prev]))
chk("★ fxa：本层尽头那一步（『去 <上一层第一间>』）与『下一层』**同一个门** —— "
    "没过手拦住（逐字同一句 · 位置不动）· 过了手真上到上一层第一间 · 往回走不拦",
    not step_bad, "%s" % (step_bad[:2] or "无"))

exit_bad = []
for no in sorted(rooms):
    here, raw = NODES[no - 1], rooms[no]["exit"]
    tg = exit_targets(raw, ROOM_NAMES)
    nb = CA._neighbors(TOWER, here)
    i = NODES.index(here)
    ahead = NODES[i + 1:]                      # 顺链走得到的（本步之后的每一间）
    into = [t for t in tg if t in ID_OF]
    out_of = [t for t in tg if t not in ID_OF]
    if "二选一" in raw:
        if not into or [t for t in into if ID_OF[t] not in ahead]:
            exit_bad.append((no, raw, "二选一那两间不都在链上顺链可达", into))
        elif ID_OF[into[0]] != (ahead[0] if ahead else ""):
            exit_bad.append((no, raw, "二选一的第一间不是链上的下一步", into, nb))
    else:
        for t in into:
            if ID_OF[t] not in nb:
                exit_bad.append((no, raw, t, nb))
    for t in out_of:                       # 塔外那一格（塔下）—— 由『撤退』验，不在图里
        if t not in GNAME.get(ent.get("node"), ""):
            exit_bad.append((no, raw, t))
chk("★ 每间的出口与 §二 逐条对得上（一步邻居 / 二选一两间顺链可达且第一间是下一步 / 塔外那格是 entrance）",
    not exit_bad, "%s" % exit_bad[:3])

# ⑧ 下一层：没站到本层最后一间 · 已经在塔顶
ad.saved = dict(ad.saved, loc=TOWER, node=NODES[1], books={})
far = send("下一层")
chk("★ 没站到本层尽头：『下一层』说清最后一间是「%s」" % rooms[4]["name"],
    far == [txt("SYS_TOWER_NEXT_FAR", room=rooms[4]["name"])], "%s" % far[:1])
# ★ fix5-nav（P2 体验）：最后一间**挡着东西**时真拦 —— 真源 22 §二·4 写的是「可做 战斗后上楼」
#   （那一屏正文也写着「楼梯口堵着一个人……从他身边过不去」）。原先『下一层』一律放行 = 话白说。
_ms = st.domain("monsters") or {}
_block_node = NODES[3]
_foes = sorted(mid for mid, m in _ms.items()
               if TOWER in [str(x) for x in ((m.get("habitat") or {}).get("maps") or [])]
               and _block_node in [str(x) for x in ((m.get("habitat") or {}).get("nodes") or [])])
chk("★ fix5-nav：本层尽头那一间（%s）确实有挡路的怪（%d 只 · 怪物谱那本账按它判）"
    % (rooms[4]["name"], len(_foes)), bool(_foes), "%s" % _foes)
ad.saved = dict(ad.saved, loc=TOWER, node=_block_node, books={}, prev=[])
_blocked = send("下一层")
_want_blk = txt("SYS_TOWER_BLOCKED", name=" · ".join(
    str((_ms.get(_m) or {}).get("name") or _m) for _m in _foes))
chk("★ fix5-nav：挡路的**没打过** ⇒ 『下一层』拦下并点名（不是照样上去）",
    _blocked == [_want_blk] and ad.saved.get("node") == _block_node,
    "%s" % _blocked[:1])
# 反证：把那一间的怪记进怪物谱（= 在那一间真动过手）⇒ 同一句不再出、那一层真上得去
ad.saved = dict(ad.saved, loc=TOWER, node=_block_node,
                books={"monster": {_foes[0]: {"day": 1, "kills": 1}}}, prev=[])
up = send("下一层")
chk("★ fix5-nav 反证：打过了（怪物谱上有它）⇒ 拦那一句一个字不出、真上到 %s 的「%s」（并给新一屏）"
    % (FLOORS[1], rooms[5]["name"]),
    _want_blk not in up
    and up[0] == txt("SYS_TOWER_UP", floor=FLOORS[1], room=rooms[5]["name"])
    and (TX.get("SCENE_%s" % NODES[4].upper()) or {}).get("value") in up
    and ad.saved.get("node") == NODES[4], "%s" % up[:2])
ad.saved = dict(ad.saved, loc=TOWER, node=NODES[11])
top = send("下一层")
chk("★ 已经在塔顶：说「没有上一层了」（不是沉默 / 不是报错）",
    top == [txt("SYS_TOWER_TOP_NONE")], "%s" % top[:1])

# ③-c ★ fxa：**塔门那两条**（『进塔』/『撤退』）也吃「场在跑」那道闸（`SYS_MOVE_IN_FIGHT`，
#   与移动族同一条）—— 原先这两条落在塔外那一族之外：一场没结也能进塔 / 出塔，
#   没结的那一场跟着玩家跨图（P2 那条链就是从野外打进来、在塔里接着打的）。
#   两态：场在跑 ⇒ 两条都拦（只那一句 · 位置不动）· 收掉之后两条真放行（反证）。
print("③-c 塔门那两条（『进塔』/『撤退』）在「场在跑」时拦下 · 收掉之后放行")
_FIGHT = dict(ad.saved, cls="cls_knight", level=14, hp=999, exp=0, gold=0, bag={}, flags={},
              prev=[])
ad.saved = dict(_FIGHT, loc=TOWER, node=NODES[1])          # 门厅（这一间有怪）
send("攻击")                                               # 一条 `攻击` 只推一手 ⇒ 场留在库里
_door_bad = []
_li = send("撤退")
if _li != [txt("SYS_MOVE_IN_FIGHT")] or ad.saved.get("node") != NODES[1]:
    _door_bad.append(("撤退", _li[:1], ad.saved.get("node")))
ad.saved = dict(ad.saved, loc=ent.get("map"), node=ent.get("node"))    # 人挪到塔门口（场照留）
_en = send("进塔")
if _en != [txt("SYS_MOVE_IN_FIGHT")] \
        or (ad.saved.get("loc"), ad.saved.get("node")) != (ent.get("map"), ent.get("node")):
    _door_bad.append(("进塔", _en[:1], (ad.saved.get("loc"), ad.saved.get("node"))))
_clear_field()                                             # 反证：这一场收掉 ⇒ 两条都放行
_go_in = send("进塔")
if ad.saved.get("loc") != TOWER or txt("SYS_TOWER_ENTER") not in _go_in:
    _door_bad.append(("进塔（收掉之后该放行）", _go_in[:1], ad.saved.get("loc")))
_out = send("撤退")
if (ad.saved.get("loc"), ad.saved.get("node")) != (ent.get("map"), ent.get("node")):
    _door_bad.append(("撤退（收掉之后该放行）", _out[:1], ad.saved.get("loc")))
chk("★ fxa：手上还有一场没打完 ⇒ 『进塔』/『撤退』一律拦下（只那一句 · 位置不动）· "
    "收掉之后两条真放行", not _door_bad, "%s" % (_door_bad[:2] or "无"))

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

# ══════════════════════════════════════════════════════════════
# ⑨ ★ B3-7：塔内 12 间的「主要敌人」↔ `monsters.habitat` 逐间对齐
#    真源那一列 = §一 总览表第 4 列（**探针自己解析**，不手抄镜像表）。
#    候选算法与 `combat.pick_encounter` 同一套：这一间在图里 ∧ （没写 nodes ∨ 这一间在 nodes 里）。
# ══════════════════════════════════════════════════════════════
print("⑨ 塔内 12 间的「主要敌人」↔ monsters.habitat（逐间对）")
MS = st.domain("monsters") or {}
ROLE_OF = {k: v.get("role") for k, v in MS.items()}


def enemy_tokens(raw):
    """`游荡的骸骨 ×2` / `拾荒人（精英）` / `骸骨 ×3 + 水鬼 ×1` / `无` → 名字 token 列表。"""
    out = []
    for part in re.split(r"[+·/、]", _plain(str(raw))):
        t = re.sub(r"[×xX]\s*\d+", "", part).strip()
        t = re.sub(r"^\d+\s*", "", t).strip()
        if t and t != "无":
            out.append(t)
    return out


def cands_at(node):
    """这一间按 `habitat` 算得出的候选（与 `combat.pick_encounter` 同一套规则）。"""
    out = []
    for k, m in MS.items():
        hb = m.get("habitat") or {}
        if TOWER not in (hb.get("maps") or []):
            continue
        ns = hb.get("nodes") or []
        if ns and node not in ns:
            continue
        out.append(k)
    return out


align_bad, room_cand = [], {}
for _f, _no, rname, _teach, enemy, _reads in overview:
    nd = ID_OF.get(rname)
    got = cands_at(nd)
    room_cand[rname] = got
    toks = enemy_tokens(enemy)
    hit = [t for t in toks if any(t in (MS[k].get("name") or "") for k in got)]
    extra = [k for k in got if not any(t in (MS[k].get("name") or "") for t in toks)]
    if len(hit) != len(toks) or extra:
        align_bad.append((rname, enemy, "缺 %s" % [t for t in toks if t not in hit],
                          "多 %s" % [MS[k]["name"] for k in extra]))
chk("★ §一「主要敌人」逐间对得上（12 间 · 点名的都在 · 没多点名的）", not align_bad, "%s" % align_bad[:3])
_empty = [rname for _f, _no, rname, _t, enemy, _reads in overview if not enemy_tokens(enemy)]
chk("★ 文档写「无」的那几间（%s）一只候选都算不出来" % " · ".join(_empty),
    bool(_empty) and all(not room_cand[r] for r in _empty), "%s" % {r: room_cand[r] for r in _empty})
print("  · 逐间候选：" + " · ".join("%s=%s" % (r, "+".join(MS[k]["name"] for k in room_cand[r]) or "（无）")
                                  for _f, _no, r, _t, _e, _rd in overview))

# ══════════════════════════════════════════════════════════════
# ⑩ ★ 真敲『攻击』：12 间逐间遇上的就是 §一 说的那只；层主 / Boss 那两间**真打完**一场
#    （原先档位白名单把 层主 / Boss 挡在遭遇之外 ⇒ 那两间只回「这一带暂时没有遇到什么」）
# ══════════════════════════════════════════════════════════════
print("⑩ 真敲『攻击』（12 间逐间 · 村镇仍是安全区）")
FIGHT = dict(ad.saved, cls="cls_knight", level=14, hp=999, gold=0, exp=0, flags={})
fight_bad, fight_seen = [], []
look_bad = []                      # ★ fxa：这一间的『观察』与真开打的那只对不对得上
_clear_field()                     # ★ G2：上一次运行 / 上一节留下的场先清掉
for _f, _no, rname, _teach, enemy, _reads in overview:
    nd = ID_OF.get(rname)
    toks = enemy_tokens(enemy)
    ad.saved = dict(FIGHT, loc=TOWER, node=nd, prev=[])
    # ★ fxa（P2 试玩 #2）：这一间的『观察』也要把「遇敌」写在屏幕上（塔内不刷精英 ⇒
    #   原先这一栏一格不出），而且写的就是**这一手真要打的那只** —— 两句话放在同一次
    #   真跑里比：『观察』「遇敌：」下面那一行 vs『攻击』那一条「⚠️ 遭遇」。
    _obs = send("观察")
    _hdr = txt("SYS_LOOK_FOE")
    _obs_foe = _obs[_obs.index(_hdr) + 1].strip() if _hdr in _obs else ""
    if bool(toks) != bool(_obs_foe):
        look_bad.append((rname, "有怪的没印遇敌行 / 没怪的印了", _obs_foe, toks))
    elif _obs_foe and _obs_foe not in [str((_MID_ALL.get(k) or {}).get("name") or k)
                                       for k in cands_at(nd)]:
        look_bad.append((rname, "遇敌行印的不是这一间的怪", _obs_foe))
    got = send("攻击")
    # ★ G2：一条 `攻击` = 推一手 ⇒ 逐间这一场要**真收掉**（下一间才是新的一间）
    got += fight_over()
    head = [x for x in got if "遭遇" in x]
    if toks and _obs_foe and head and _obs_foe not in head[0]:
        look_bad.append((rname, "『观察』说的那只 ≠『攻击』真打的那只", _obs_foe, head[0]))
    if not toks:
        if head or len(got) != 1:
            fight_bad.append((rname, "文档写「无」却打起来了", got[:1]))
        continue
    if not head or not any(t in head[0] for t in toks):
        fight_bad.append((rname, enemy, got[:1]))
        continue
    mid = next((k for k in cands_at(nd) if MS[k]["name"] in head[0]), "")
    fight_seen.append((rname, MS[mid]["name"], ROLE_OF[mid]))
    if ROLE_OF[mid] in ("层主", "boss"):          # ★ 层主 / Boss 这一场要真出结果（日志成篇）
        #   三种收尾都算「打得上」：打赢了 / 倒地 / 战斗提前结束（Boss 的「回塔」那一阶段）
        end = [x for x in got if any(w in x for w in ("打完了", "眼前一黑", "战斗结束"))]
        if not (end and any("还有" in x for x in got)):
            fight_bad.append((rname, "%s 这场没打完" % MS[mid]["name"], got[-2:]))
        else:
            fight_seen[-1] = (rname, MS[mid]["name"], "%s · %s" % (ROLE_OF[mid], end[0].strip()))
ad.saved = dict(FIGHT, loc="windmill_town", node="wt_gate_n", prev=[])
_clear_field()                     # ★ G2：镇上那一敲要的是「安全区」这一档 ⇒ 先清干净
_safe = send("攻击")
chk("★ 12 间逐间真敲『攻击』：遇上的就是文档说的那只（层主 / Boss 也真打完一场）",
    not fight_bad, "%s" % fight_bad[:3])
chk("★ fxa：塔内每一间『观察』都印「遇敌：」那一栏（有怪的那几间）· 没怪的那两间不印 · "
    "**印出来的就是这一手真打的那只**（与『攻击』的「⚠️ 遭遇」逐间比 —— P2 试玩 #2）",
    not look_bad, "%s" % (look_bad[:3] or "无"))
chk("★ 镇上（安全区）敲『攻击』一条「遭遇」都没有",
    len(_safe) == 1 and not any("遭遇" in x for x in _safe), "%s" % _safe[:1])
print("  · 逐间遭遇：" + " · ".join("%s→%s(%s)" % x for x in fight_seen))

# ══════════════════════════════════════════════════════════════
# ⑪ ★ 三处容器『搜查』真拿得到（真宿主 · 逐处换 24 个人 × 当日第 1/2 次 —— uid 进采集种子）
#    真源：22 §二 的「可做」列（探针自己从那一列认出这三间）。
#    关键件的出处：`06_装备获取与支线玩法_v1 §1.2`（哨兵的护手 ← 副本二层）·
#                `14_图鉴四谱口径` 旧物表（半截号角 = 信物 `i_horn_half`）·
#                门厅那件 = 未鉴定（不读书、只给一条问号 —— 池表 `unid_tower`）。
#    到手那一刻就该在旧物谱里留一行问号（装备那类不进谱，另核）。
# ══════════════════════════════════════════════════════════════
print("⑪ 三处容器『搜查』真拿得到（逐处 24 个人 × 2 遍）")
CX = st.domain("codex") or {}
TODO_KEY = (("开箱", "i_set_sentry_gauntlet"), ("拿半截号角", "i_horn_half"),
            ("旧物谱第一个问号", "unid_tower"))
TARGET = {}
for _no, _r in sorted(rooms.items()):
    for _kw, _iid in TODO_KEY:
        if _kw in _r.get("todo", ""):
            TARGET[_r["name"]] = (_kw, _iid)
chk("★ 22 §二「可做」列里认出三处可拿物（%s）" % " · ".join("%s=%s" % v for v in TARGET.values()),
    len(TARGET) == 3, "%s" % TARGET)
cont_bad, cont_ok = [], {}
for rname, (kw, iid) in TARGET.items():
    nd = ID_OF.get(rname)
    hit = None
    for i in range(24):
        uid = "u_c%d" % i
        ad.by_uid[uid] = dict(FIGHT, loc=TOWER, node=nd, bag={}, codex={}, books={}, foot={},
                              prev=[], flags={})
        for nth in range(2):
            send_as(uid, "搜查")
            if str(iid) in (ad.by_uid[uid].get("bag") or {}):
                hit = (uid, nth + 1)
                break
        if hit:
            break
    if not hit:
        cont_bad.append((rname, iid, "24 人 × 2 遍都没拿到"))
        continue
    cont_ok[rname] = (iid, hit)
    uid, nth = hit
    books = ((ad.by_uid[uid].get("books") or {}).get("relic") or {})
    if iid.startswith("i_set_"):                    # 装备那类：不进谱（只进背包）
        if iid in books:
            cont_bad.append((rname, iid, "装备不该进谱", list(books)))
        continue
    rec = books.get(iid)
    if not (rec and rec.get("known") is False):
        cont_bad.append((rname, iid, "没进旧物谱 / 不是从问号起步", rec))
        continue
    hint = str(((CX.get("relic") or {}).get(iid) or {}).get("hint") or "")
    book = send_as(uid, "旧物谱")
    if not hint or not any(hint in x for x in book):
        cont_bad.append((rname, iid, "旧物谱里没出那一行问号", book))
chk("★ 三处容器真拿得到（背包里真进了那件）· 旧物谱那条线也接上（问号行照字出）",
    not cont_bad, "%s" % (cont_bad[:2] or ["无"]))
print("  · 逐处：" + " · ".join("%s→%s（%s 第 %d 遍）" % (r, iid, uid, nth)
                              for r, (iid, (uid, nth)) in sorted(cont_ok.items())))

# ══════════════════════════════════════════════════════════════
# ⑫ ★ B3-10：塔内那 9 项可读物里，「进谱的 3 条」与「就地线索 6 条」**各真跑一遍**：
#    · 就地线索（22 §二「可做」列）真敲『读』→ 正文逐字拿到 · **旧物谱一条都不加**（读完不留痕）；
#    · 已进谱的 3 条（墙上的划痕 / 拾荒人留的字条 / 没寄出的信）真敲『读』→ 旧物谱真多一行**问号**，
#      且那一行的字就是 14 号文档那一格（照字出）。
#    判据是行为 —— 谁进谱不是靠注释说的，是真敲出来的。
# ══════════════════════════════════════════════════════════════
print("⑫ 塔内 9 项可读物：进谱的 3 条 / 就地线索 6 条（真敲『读』逐条）")
_L12 = st.domain("codex") or {}
_LOCAL = sorted(k for k, v in PO.items() if v.get("kind") == "可读物" and v.get("map") == TOWER
                and not v.get("into_codex"))
_INCX = sorted(k for k, v in PO.items() if v.get("kind") == "可读物" and v.get("map") == TOWER
               and v.get("into_codex"))
loc_bad = []
for pid in _LOCAL:
    v = PO[pid]
    body = (TX.get(v.get("read_text")) or {}).get("value") or ""
    ad.saved = dict(FIGHT, loc=TOWER, node=v.get("subarea"), prev=[], bag={},
                    books={"relic": {}}, foot={})
    got = send("读 %s" % v.get("name"))
    books = ((ad.saved.get("books") or {}).get("relic") or {})
    if txt("SYS_READ_HEAD", name=v.get("name")) not in got or body not in got:
        loc_bad.append((pid, "正文没拿到", got[:2]))
    elif books:
        loc_bad.append((pid, "就地线索不该进旧物谱", books))
chk("★ 塔内那 %d 条就地线索真敲『读』：正文逐字拿到 · 旧物谱一条不加（22 §二 的「可做」不进谱）"
    % len(_LOCAL), not loc_bad, "%s" % (loc_bad[:2] or " · ".join(_LOCAL)))

inc_bad = []
for pid in _INCX:
    v = PO[pid]
    ad.saved = dict(FIGHT, loc=TOWER, node=v.get("subarea"), prev=[], bag={},
                    books={"relic": {}}, foot={})
    got = send("读 %s" % v.get("name"))
    books = ((ad.saved.get("books") or {}).get("relic") or {})
    hint = str(((_L12.get("relic") or {}).get(pid) or {}).get("hint") or "")
    if not (books.get(pid) or {}).get("known") is False:
        inc_bad.append((pid, "没进谱 / 不是问号起步", books))
        continue
    if txt("SYS_CODEX_NEW", book="旧物谱", name=v.get("name")) not in got:
        inc_bad.append((pid, "没报「新进谱」", got[-2:]))
        continue
    book = send("旧物谱")
    if not hint or not any(hint in x for x in book):
        inc_bad.append((pid, "旧物谱里没出那一行问号", book))
chk("★ 塔内那 %d 条进谱的（划痕 / 字条 / 信）真敲『读』：旧物谱真多一行问号（照字出）" % len(_INCX),
    not inc_bad, "%s" % (inc_bad[:2] or " · ".join(_INCX)))

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

# ══════════════════════════════════════════════════════════════
# ⑬ ★ 本波：**副本出口也接上「场在跑」那道闸**（与出镇 / 带间 / 返回同一档）
#    起因（试玩报告 §5④）：原来这一闸只接在**世界级移动**上（往北 / 进镇 / 进塔），
#    副本出口『撤退』没接 —— 实测「打着一场就走出了塔，那一场跟着人跨图继续」
#    （人在塔外「旧哨塔下」，照样在打塔顶的 Boss）。『下一层』同理（它也动位置）。
#    判据（真敲 · 真宿主）：持态中敲『撤退』/『下一层』⇒ 出 `SYS_MOVE_IN_FIGHT`、
#    **位置与历史一个字不动**、这一场照旧；把这一场收掉之后 ⇒ 『撤退』照旧出塔。
# ══════════════════════════════════════════════════════════════
print("⑬ 本波：持态中『撤退』『下一层』被同一档拦下（位置与历史一个字不动）")
_GATE = []
_ENT2 = (ent.get("map"), ent.get("node"))
ad.saved = dict(FIGHT, loc=TOWER, node="tower_stair1", prev=[])      # 楼梯前：那只挡路的
_clear_field()
send("攻击")                                   # 开一场（这一手打不完它 —— 血厚）
_g_f = _field()
if _g_f is None:
    _GATE.append(("前提：这一敲没开出这一场", None))
else:
    _pos0 = (dict(ad.saved).get("loc"), dict(ad.saved).get("node"))
    _prev0 = list(ad.saved.get("prev") or [])
    _o_leave = send("撤退")
    if _o_leave != [txt("SYS_MOVE_IN_FIGHT")]:
        _GATE.append(("持态中『撤退』没被拦", _o_leave[:2]))
    _o_next = send("下一层")
    if _o_next != [txt("SYS_MOVE_IN_FIGHT")]:
        _GATE.append(("持态中『下一层』没被拦", _o_next[:2]))
    if ((dict(ad.saved).get("loc"), dict(ad.saved).get("node"))) != _pos0 \
            or list(ad.saved.get("prev") or []) != _prev0:
        _GATE.append(("被拦下却动了位置 / 历史",
                      ((dict(ad.saved).get("loc"), dict(ad.saved).get("node")), _pos0)))
    if _field() is None:
        _GATE.append(("被拦下却把这一场弄没了", None))
    fight_over()                               # 收掉这一场 ⇒ 出口照旧
    _o_leave2 = send("撤退")
    if not any(x.startswith(txt("SYS_TOWER_LEAVE").split("{")[0]) for x in _o_leave2):
        _GATE.append(("收掉之后『撤退』反倒出不去了", _o_leave2[:2]))
    if (dict(ad.saved).get("loc"), dict(ad.saved).get("node")) != _ENT2:
        _GATE.append(("出塔没回到进塔那一格",
                      (dict(ad.saved).get("loc"), dict(ad.saved).get("node")), _ENT2))
chk("★ 副本出口那一闸：持态中『撤退』『下一层』被 `SYS_MOVE_IN_FIGHT` 拦下"
    "（位置 / 历史 / 这一场一字不动）· 这一场收掉之后出塔照旧", not _GATE, "%s" % _GATE[:2])

print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
