# -*- coding: utf-8 -*-
"""探针：存档半边（`content/persistence.py`）—— 表名不许撞生产库 · 存读往返 · fail-closed。

为什么有它（2026-09-25 换包上线实测的**真事故**）
------------------------------------------------
存档半边原先建的是**裸名 `players`** 表，而宿主那台生产库里已经躺着**奥兰迪亚的 `players`**
（列是 qq_id / name / level…）。`CREATE TABLE IF NOT EXISTS` 撞上它**静默跳过建表** ⇒ 之后每一次
`SELECT data FROM players` 都 `no such column: data` ⇒ **在线机器人每条指令都崩**（连「我是 人类」
都回异常）。137 个测试文件 + 当时 24 个探针全绿都照不出来 —— 它们各自用**新建的空库**；
只有「真上线、真撞上那张库」才暴露。⇒ 本探针**造一个生产库形态的库**（先放一张别人的 `players`）
来钉这一族。

判据
----
  ① 五个口都在（宿主 `StoreFactory.HALF` 契约：get_player / update_player / init_db / lock / connect）
  ② 存读往返一致 · 同一个 (group_id, uid) 覆盖不新增行
  ③ ★ 库里已有**别人的**同名表 ⇒ 包照样存得上读得回，且那张表一行不动
  ④ ★ 表名带包前缀（静态守卫：SQL 里不许出现裸 `players`）
  ⑤ ★ fail-closed：同名表列不对 ⇒ **当场抛**（不是等到查询时 `no such column`）
  ⑥ get_player_groups / all_players 与写进去的对得上

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_store.py
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys
import time
from pathlib import Path

import ast as _ast
import inspect as _inspect

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, ENGINE)

from content import persistence as PS                                  # noqa: E402

ok = True
TMP = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp")


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


def fresh(name, foreign_players=False, half_table=None):
    """造一个库：`foreign_players` = 先放一张**别人的** `players`（生产库形态）。"""
    p = os.path.join(TMP, "ast_probe_store_%s.db" % name)
    if os.path.exists(p):
        os.remove(p)
    c = sqlite3.connect(p)
    if foreign_players:
        c.execute("CREATE TABLE players (qq_id TEXT PRIMARY KEY, name TEXT, level INTEGER)")
        c.execute("INSERT INTO players VALUES('u_prod','老王',7)")
    if half_table:
        c.execute("CREATE TABLE %s (qq_id TEXT, name TEXT)" % PS.TBL)
    c.commit()
    c.close()
    PS.bind(db_path=p)
    return p


print("探针：存档半边（表名不许撞生产库 · fail-closed）")

print("① 宿主契约那五个口 + 签名")
missing = [n for n in ("get_player", "update_player", "init_db", "lock", "connect")
           if not callable(getattr(PS, n, None))]
chk("★ 五个口都在（缺一个宿主就拒绝启动）", not missing, missing)
_sig = _inspect.signature(PS.update_player)
chk("★ update_player 收 **fields（宿主 `save_player` 逐字 `update_player(g, u, **fields)`）",
    any(p.kind == p.VAR_KEYWORD for p in _sig.parameters.values()), str(_sig))
chk("★ get_player(group_id, uid) 两参", len(_inspect.signature(PS.get_player).parameters) == 2,
    str(_inspect.signature(PS.get_player)))

print("② 存读往返（空库）")
p0 = fresh("fresh")
chk("空库 + init_db 不抛", PS.init_db() is True)
chk("新号读回 None（引擎据此要初始档）", PS.get_player("g1", "u1") is None)
fill = {"level": 3, "bag": {"i_horn_half": 1}, "books": {"relic": {"i_horn_half": {"studied": True}}}}
PS.update_player("g1", "u1", **fill)
PS.update_player("g1", "u1", level=4)                                  # 字段式覆盖（读-改-写）
c = sqlite3.connect(p0)
rows = c.execute("SELECT COUNT(*) FROM %s" % PS.TBL).fetchone()[0]
c.close()
chk("★ 读回来逐字段一致（含中文/嵌套 · 覆盖写只动那一格）",
    PS.get_player("g1", "u1") == dict(fill, level=4), PS.get_player("g1", "u1"))
chk("★ 同一个 (group_id, uid) 覆盖不新增行", rows == 1, "行数 %d" % rows)

print("③ ★ 生产库形态：库里已经有别人的同名表")
p1 = fresh("foreign", foreign_players=True)
PS.update_player("g2", "u2", level=9)
gone = PS.get_player("g2", "u2")
c = sqlite3.connect(p1)
tabs = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
mine = c.execute("SELECT COUNT(*) FROM %s" % PS.TBL).fetchone()[0]
theirs = c.execute("SELECT qq_id, name, level FROM players").fetchall()
c.close()
chk("★ 包照样存得上读得回（不再 no such column）", gone == {"level": 9}, gone)
chk("★ 别人的 `players` 一行不动、列也没被改", theirs == [("u_prod", "老王", 7)], theirs)
chk("★ 包的表是带前缀的那张（两张表并存）", tabs == sorted(["aetheran_meta", PS.TBL, "players"]),
    "%s · 包的行数 %d" % (tabs, mine))

print("④ ★ 静态守卫：SQL 里的表名都带包前缀")
src = open(os.path.join(str(REPO), "content", "persistence.py"), encoding="utf-8").read()
tree = _ast.parse(src)
# 只看**代码里的字符串**（注释 / docstring 里提到旧名是有意的，不算违规）
_docs = set()
for _n in _ast.walk(tree):
    if isinstance(_n, (_ast.Module, _ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)):
        _d = _ast.get_docstring(_n, clean=False)
        if _d:
            _docs.add(_d)
_sqls = [n.value for n in _ast.walk(tree)
         if isinstance(n, _ast.Constant) and isinstance(n.value, str) and n.value not in _docs]
tbls = set()
for _s in _sqls:
    tbls |= set(re.findall(r"(?:FROM|INTO|EXISTS)\s+([A-Za-z_][A-Za-z_0-9]*|%s)", _s))
bad = sorted(t for t in tbls if t != "%s" and not t.startswith("aetheran_"))
chk("★ 代码里的 SQL 不出现裸表名（现取到：%s）" % (sorted(tbls),), not bad, bad)
chk("★ 表名常量带包前缀", str(PS.TBL).startswith("aetheran_"), PS.TBL)

print("⑤ ★ fail-closed：同名表列不对 ⇒ 当场抛")
fresh("half", half_table=True)
try:
    PS.get_player("g3", "u3")
    chk("★ 半截/异形的同名表 ⇒ 抛 RuntimeError", False, "居然没抛（会变成静默存不上档）")
except RuntimeError as e:
    chk("★ 半截/异形的同名表 ⇒ 抛 RuntimeError（说得清是哪张表）",
        PS.TBL in str(e) and "列不对" in str(e), e)
except Exception as e:                                                 # noqa: BLE001
    chk("★ 半截/异形的同名表 ⇒ 抛 RuntimeError", False, "%s: %s" % (type(e).__name__, e))

print("⑥ 附带查询")
p2 = fresh("many")
PS.update_player("g1", "u1", level=1)
PS.update_player("g1", "u2", level=2)
PS.update_player("g2", "u1", level=3)
PS.update_player("g3", "u9", level=9)                                    # 另一群人（两口必须分得开）
chk("★ groups_of_player（同一个人在哪几个群）", sorted(PS.groups_of_player("u1")) == ["g1", "g2"],
    PS.groups_of_player("u1"))
# ★ 审计 L1702：广播群表那口是**零参**宿主契约（引擎 host/shell.py::_group_table 逐字这么调）——
#   原先只有按 uid 那一支 ⇒ 升级即 TypeError，而包内零生产消费者、跑包内测试照不出来。
chk("★ get_player_groups 零参 = 全部群（引擎调用形状）",
    sorted(PS.get_player_groups()) == ["g1", "g2", "g3"], PS.get_player_groups())
chk("★ 两口不串：零参 != 按 uid", sorted(PS.get_player_groups()) != sorted(PS.groups_of_player("u1")),
    "零参=%s 按uid=%s" % (sorted(PS.get_player_groups()), sorted(PS.groups_of_player("u1"))))
allp = PS.all_players()
chk("★ all_players 全量 = 4 条", len(allp) == 4, len(allp))
chk("★ all_players 按群过滤", len(PS.all_players("g1")) == 2, PS.all_players("g1"))

# ⑦ ★ 审计 L1702 三条（引擎侧零覆盖）：本模块不许再登记**从不读**的注入键。
import re as _re
_PERS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "content", "persistence.py")
with open(_PERS_PATH, encoding="utf-8") as _f:
    _pers_src = _f.read()
_PCT = chr(37) + "s"          # DDL 里的占位符：真源常量走 % 插值，不写字面量
_h_block = _re.search(r"(?m)^_H = \{.*?\}", _pers_src, _re.S)
_h_keys = set(_re.findall(r'"(\w+)"', _h_block.group(0))) if _h_block else set()
chk("★ _H 只登记真读的两个键（log/tlog/attach_tlog/grant_reward 归 facade.HANDLES）",
    _h_keys == {"db_path", "clock"}, "登记了=%s" % sorted(_h_keys))
chk("★ threading.local 零消费者已删（_local 不再存在）",
    not _re.search(r"(?m)^_local\s*=", _pers_src), "_local 仍在")
_ddl = _re.search(r"CREATE TABLE IF NOT EXISTS (\S+) \(\s*k TEXT PRIMARY KEY, v TEXT", _pers_src)
_ddl_name = _ddl.group(1) if _ddl else None
chk("★ 元表建表 DDL 用真源常量 TBL_META（占位符插值），不写表名字面量",
    _ddl_name == _PCT, "DDL 里写的=%r（期待占位符 %r）" % (_ddl_name, _PCT))
#   反向：元表名在全文件只应作为 TBL_META 的定义出现一次；DDL/核列/读写都走常量。
chk("★ 元表名在全文件只出现一次（就是 TBL_META 的定义行；DDL/核列/读写都走它）",
    _pers_src.count(chr(34) + "aetheran_meta" + chr(34)) == 1,
    "字面量出现 %d 次" % _pers_src.count(chr(34) + "aetheran_meta" + chr(34)))

# ⑧ ★ 审计 L1702-同族（读口余量 · 0ca00bf 之后修）：all_players 的坏档不得被静默降级成 {}。
#    修之前：`except Exception: d = {}` ⇒ 三人库得榜 2 人，玩家从榜上凭空消失且零报错。
#    本组 4 条：① 坏 JSON 抛并点名 uid ② 顶层非 dict 抛 ③ 好档逐条原样（零行为变化）
#              ④ 静态守卫：全文件不许再有裸 `d = {}` 降级（第 25 轮纪律：判据要独立第三方读源）
print("⑧ all_players 坏档 fail-closed（不降级成空档）")
p3 = fresh("corrupt")
PS.update_player("g1", "u_ok1", name="甲", level=5, exp=99)
PS.update_player("g1", "u_ok2", name="乙", level=7, exp=99)
PS.update_player("g2", "u_far", name="丙", level=9, exp=99)
_c3 = sqlite3.connect(p3)
_c3.execute("INSERT INTO %s VALUES(?,?,?,?)" % PS.TBL, ("g1", "u_bad", "{not json", 0.0))
_c3.commit()
_c3.close()
try:
    PS.all_players("g1")
    chk("★ 坏档行 ⇒ all_players 当场抛（不静默降级）", False, "竟然正常返回了")
except RuntimeError as _ex:
    chk("★ 坏档行 ⇒ all_players 当场抛（不静默降级）", True)
    chk("★ 报错点名了出事那个 uid（'u_bad'）", "u_bad" in str(_ex), str(_ex)[:120])
_c4 = sqlite3.connect(p3)
_c4.execute("UPDATE %s SET data=? WHERE uid=?" % PS.TBL, ("[1,2,3]", "u_bad"))
_c4.commit()
_c4.close()
try:
    PS.all_players("g1")
    chk("★ data 顶层非 dict ⇒ 当场抛（不降级）", False, "竟然正常返回了")
except RuntimeError as _ex2:
    chk("★ data 顶层非 dict ⇒ 当场抛（不降级）", "u_bad" in str(_ex2), str(_ex2)[:120])
_good = {r["uid"]: r["data"] for r in PS.all_players("g2")}
chk("★ 好数据零行为变化（g2 那一条原样回来）",
    _good == {"u_far": {"name": "丙", "level": 9, "exp": 99}}, _good)
#  ④ 静态守卫（独立读源，不 import）：全文件不许再有「解析失败就造空档」的降级写法。
#     （第 25 轮纪律：判据要独立第三方读源，别拿被测对象自己比自己。）
_all_fn = _re.search(r"(?m)^def all_players\(.*?(?=^def |^# ──)", _pers_src, _re.S)
_body = _all_fn.group(0) if _all_fn else ""
if not _body:
    chk("★ 取得到 all_players 源码（fail-closed：取空即判红）", False, "函数体没取到")
else:
    chk("★ 取得到 all_players 源码（fail-closed：取空即判红）", True, "函数体 %d 字" % len(_body))
_hits = _re.findall(r"(?m)^\s*d = \{\}\s*$", _body)
chk("★ all_players 内不再有「解析失败 → d = {}」降级", not _hits,
    "仍有一行裸 d = {}" if _hits else "零处降级")

print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
