# -*- coding: utf-8 -*-
"""《阿斯特兰》存档层（`content/persistence.py`）—— 宿主**半边**之一。

宿主契约（`host/store_factory.py::StoreFactory.HALF`）要求本模块提供五个口：
`get_player` / `update_player` / `init_db` / `lock` / `connect`。缺一个宿主就
**拒绝静默空跑**（抛 RuntimeError）—— 这是有意的：宁可起不来，也不要静默存不上档。
★ **签名也算契约**：`update_player(group_id, uid, **fields)` —— 宿主逐字这么调
  （`HostStore.save_player` 把整档拆成字段传进来）；写成整档入参 `(g, u, data)` 当场就炸
  （2026-09-25 换包上线实测：`TypeError: unexpected keyword argument 'name'`）。

注入面（与奥兰迪亚同形，不另发明第三套）：
    宿主 `inject_handles()` → 引擎 `inject` → 引擎调包内 `bind_host(**inject)`
    → 本模块 `bind(**handles)`：**本模块只真读** `db_path`（必给）/ `clock` 两个；
      `log` / `tlog` / `attach_tlog` / `grant_reward` 那一批由 `content/facade.py` 的
      `HANDLES` 持有并消费（`facade.log()`），本模块零读取点（审计 L1702：别再登记）。

★ 不改动存档库路径的来历 —— 它是**部署信息**，由宿主解析后注入；包不知道自己在哪台机器上跑。
★★ 但**表名必须自带包前缀**（`aetheran_players` / `aetheran_meta`）：生产库是宿主共用的那一张，
  里面躺着奥兰迪亚的表（它也有 `players`，列是 qq_id/name/level/…）。2026-09-25 换包上线实测：
  本模块原先写 `CREATE TABLE IF NOT EXISTS players` ⇒ **撞上奥兰迪亚那张表后被静默跳过**，
  之后每次 `SELECT data FROM players` 都 `no such column: data` —— **每条指令都崩**。
  （137 个测试文件 + 探针全绿照不出来：它们用的是各自新建的空库；只有真启动才暴露。）
  ⇒ 建完表**核一遍列**（fail-closed），撞车/半截表当场喊出来，不再静默存不上档。
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time

__all__ = ["bind", "db_path", "clock", "init_db", "lock", "connect",
           "get_player", "update_player", "get_player_groups", "groups_of_player",
           "all_players",
           "meta_key", "group_get", "group_set", "group_del"]

#: 存档表名（★ 带包前缀，理由见模块开头）；列 = 存档那一行的形状
TBL = "aetheran_players"
COLS = ("group_id", "uid", "data", "updated_at")
#: ★ B3-26：**按群存的共同档**（「场」这种不是单玩家档的数据）—— 与上面那张同一个库
TBL_META = "aetheran_meta"
META_COLS = ("k", "v")

#: 共同档的键形状：`<scope>:<group_id>`（scope = 谁在用，如 `instance`；
#: 分隔符只有这一处定义 —— 键里的两截都不许再含它，否则会撞别人的行）
META_SEP = ":"

#: ★ 2026-10-01（鱼鱼口径「私聊/群聊数据要共享」）：**游戏世界里没有「群」这个维度** ——
#:   一个人（uid）一份档、一个世界。宿主传进来的 `group_id`（群号 / `"private"`）只是
#:   **会话路由**，存档键一律归一到 `WORLD`（实测：私聊 `private` 与群号各存一行 ⇒
#:   同一个 1454832774 互不可见 —— 私聊注册过、群里又能注册）。
#:   未来「多世界预留」（06_阶段交接指南）= 把 `_world()` 换成「群 → 世界」映射，**只此一处**。
WORLD = "world"


def _world(group_id=None) -> str:
    """会话 group_id → 世界键（今天恒 `WORLD`；将来多世界映射的唯一改动点）。"""
    return WORLD


#: 注入句柄的**本模块真源**。只列**本模块真读的**两个键 ——
#: `log` / `tlog` / `attach_tlog` / `grant_reward` 由 `content/facade.py` 的 `HANDLES`
#: 持有并消费（`facade.log()` 等），本模块零读取点（审计 L1702：纯写零读）。
#: ★ `bind(**handles)` 是**泛收**（`facade.bind_host` 会把整批句柄递进来）——
#:   多余的键照收不误但**不再登记**：登记一个从不读的键 = 让人以为本模块会用它。
_H = {"db_path": None, "clock": None}
_LOCK = threading.RLock()


def bind(**handles):
    """注入句柄（幂等；`None` / 缺省 = 不改）。返回本模块便于链式调用。"""
    for k, v in handles.items():
        if v is not None:
            _H[k] = v
    return _H


def db_path() -> str:
    p = _H.get("db_path")
    if not p:
        raise RuntimeError("content.persistence：db_path 句柄未注入（宿主 store_factory 负责注入）")
    return str(p)


def clock() -> float:
    fn = _H.get("clock")
    return float(fn() if callable(fn) else time.time())


# ── 连接 / 锁 ──────────────────────────────────────────────
def lock():
    return _LOCK


def connect():
    """新连接（调用方负责关闭）。表结构随第一次连接自动建好，建完**核一遍**（fail-closed）。"""
    p = db_path()
    d = os.path.dirname(p)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    c = sqlite3.connect(p, timeout=10.0)
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS %s (
        group_id TEXT NOT NULL, uid TEXT NOT NULL, data TEXT NOT NULL,
        updated_at REAL NOT NULL, PRIMARY KEY (group_id, uid))""" % TBL)
    c.execute("""CREATE TABLE IF NOT EXISTS %s (
        k TEXT PRIMARY KEY, v TEXT)""" % TBL_META)
    # ★ `IF NOT EXISTS` 撞上同名的**别人的**表时会**静默跳过**（2026-09-25 换包上线实测：
    #   奥兰迪亚的 `players` 在同一个库里 ⇒ 每次查询都 `no such column: data`）⇒ 当场核列、不对就抛。
    for _t, _cols in ((TBL, COLS), (TBL_META, META_COLS)):
        got = {r["name"] for r in c.execute("PRAGMA table_info(%s)" % _t)}
        if got != set(_cols):
            c.close()
            raise RuntimeError("%s：存档表 %s 的列不对（期望 %s，实际 %s）—— 撞上同名的别的表了？"
                               % (__name__, _t, sorted(_cols), sorted(got)))
    return c


def init_db():
    """建表 + 迁移（幂等）。"""
    with _LOCK:
        c = connect()
        try:
            c.commit()
        finally:
            c.close()
    return True


# ── 读写档 ─────────────────────────────────────────────────
def get_player(group_id, uid):
    """读档（dict | None）。`None` = 新玩家（引擎会问包要初始档）。

    ★ 2026-10-01（数据共享）：键按 `_world()` 归一 —— 私聊/群聊同一份档（签名不变，
      宿主照旧传真实 group_id，本半边只认世界键）。
    """
    with _LOCK:
        c = connect()
        try:
            row = c.execute("SELECT data FROM %s WHERE group_id=? AND uid=?" % TBL,
                            (_world(group_id), str(uid or ""))).fetchone()
        finally:
            c.close()
    # ★ 审计 L1701：原为 `except Exception: return None`。**`None` 的含义被这一处偷走了** ——
    # 上面 docstring 写明「`None` = 新玩家（引擎会问包要初始档）」，而坏档（存档半截 / 编码坏 /
    # 迁移中断）与「查无此人」塌成同一个值 ⇒ 引擎把一个玩了几十小时的档**当成新玩家**，
    # 走建号初始化，下一次落档就把原档**覆盖销毁**（实测：7 级 / 9999 金币的档被改成
    # 1 级 / 0 金币，全程零报错）。真值判据 = 「这一行不存在」，坏档不是「不存在」。
    # ★ 2026-09-30 审计残余 #44（**归档·低**）：读档走 `connect()` 会顺带跑
    #   `CREATE TABLE IF NOT EXISTS` ×2 + `PRAGMA` 核列 —— 读路径动 schema，职责/性能口径
    #   可议但**功能正确**，且撞上同名表当场抛的 fail-closed 核列在读路径同样生效。
    #   有意保留（不是 bug、也不是死码）：真要收敛到只在 `init_db` 建表，须连这层核列
    #   一起挪、并补「生产库形态」探针覆盖 —— 单独删 = 丢兜底。
    if not row:
        return None
    try:
        v = json.loads(row["data"])
    except Exception as _e:
        raise RuntimeError(
            "content.persistence.get_player：存档行存在但 JSON 解析失败（group_id=%r uid=%r）——"
            "拒绝返回 None（None = 新玩家，引擎会走建号初始化并覆盖销毁原档）"
            % (group_id, uid)
        ) from _e
    if not isinstance(v, dict):
        raise RuntimeError(
            "content.persistence.get_player：存档行的 data 顶层不是 dict（group_id=%r uid=%r，"
            "实际 %s）—— 拒绝当作无存档返回 None（否则同上一条：覆盖销毁原档）"
            % (group_id, uid, type(v).__name__)
        )
    return v


def update_player(group_id, uid, **fields):
    """落档 —— ★ **字段式**：宿主逐字就是 `half().update_player(group_id, uid, **fields)`
    （`host/store_factory.py::HostStore.save_player`，一条消息一次、整档拆成字段传进来）。

    ★★ 形状别改成 `(group_id, uid, data)` 那种整档入参 —— 2026-09-25 换包上线实测：
      签名错位 ⇒ **每条指令都 `TypeError: unexpected keyword argument 'name'`**（与
      「表名撞车」同一轮抓出来的第二处；奥兰迪亚半边也是 `(g, qq_id, **fields)`）。
    口径 = **读-改-写**：把这几格盖到库里那一行上（与奥兰迪亚那半边的字段式 UPDATE 同义）。

    ★ 不另抄一份「合法字段」白名单：玩家档那个 dict 的形状真源在包里（`cmds_ast.DEFAULT_PLAYER`
      + 各域自己那几格），本半边只负责把它整块存下来。
    """
    if not fields:
        return False
    with _LOCK:
        c = connect()
        try:
            row = c.execute("SELECT data FROM %s WHERE group_id=? AND uid=?" % TBL,
                            (_world(group_id), str(uid or ""))).fetchone()
            cur = {}
            if row:
                # ★ 审计 L1701-同族（写口）：读口 get_player 已在同一次修复里 fail-closed，
                #   而这里仍把坏档塌成 {} —— 读-改-写会拿这个空 dict 当底，**下一次任意
                #   落档就把原档覆盖销毁**（实测：7 级 / 9999 金币 → 1 级 / 0 金币，rc=True、
                #   零报错）。两处必须同口径：行存在而内容坏 ⇒ 抛，绝不自己造一个空档。
                try:
                    cur = json.loads(row["data"])
                except Exception as _e:
                    c.close()
                    raise RuntimeError(
                        "content.persistence.update_player：存档行存在但 JSON 解析失败"
                        "（group_id=%r uid=%r）—— 拒绝从空档重建（会把原档覆盖销毁）"
                        % (group_id, uid)
                    ) from _e
                if not isinstance(cur, dict):
                    c.close()
                    raise RuntimeError(
                        "content.persistence.update_player：存档行的 data 顶层不是 dict"
                        "（group_id=%r uid=%r，实际 %s）—— 拒绝从空档重建（会把原档覆盖销毁）"
                        % (group_id, uid, type(cur).__name__)
                    )
            if not isinstance(cur, dict):
                cur = {}
            cur.update(fields)
            blob = json.dumps(cur, ensure_ascii=False, separators=(",", ":"))
            c.execute("INSERT INTO %s(group_id, uid, data, updated_at) VALUES(?,?,?,?) "
                      "ON CONFLICT(group_id, uid) DO UPDATE SET data=excluded.data, "
                      "updated_at=excluded.updated_at" % TBL,
                      (_world(group_id), str(uid or ""), blob, clock()))
            # ★ 2026-10-01（数据共享 · 归一的另一半）：档行归一后 players 表里不再有真实群号，
            #   而 `get_player_groups()`（引擎广播扇出的**零参契约口**）要的正是「哪些群活跃过」
            #   ⇒ 真实群号**顺手记一条 meta**（raw 键，不经 `group_get/set` —— 那两个口的
            #   group_id 参数是**域侧复合键**（如 `instance` 的 `群#uid`），归一归在域侧
            #   `key_of`，这里记的真群号不能被抹）。私聊（`"private"`）不算群，不记。
            _g = str(group_id or "")
            if _g and _g != "private" and _g != WORLD:
                c.execute("INSERT INTO %s(k, v) VALUES(?,?) "
                          "ON CONFLICT(k) DO UPDATE SET v=excluded.v" % TBL_META,
                          ("active_group%s%s" % (META_SEP, _g), "1"))
            c.commit()
        finally:
            c.close()
    return True


# ── 附带查询（宿主/编辑器用） ───────────────────────────────
def get_player_groups():
    """**广播群表**（引擎零参调的那一口，审计 L1702）—— 所有有玩家注册/活跃过的群号。

    ★ 签名是**宿主契约**，不是随手写的：引擎 `host/shell.py::_group_table()` 逐字
      `self._store.get_player_groups()`（**零参**），`_broadcast()` 的扇出全走它
      ⇒ 原先写成 `get_player_groups(uid)` 时升级即 `TypeError`，而包内**零生产消费者**
      （只有探针按 uid 调）⇒ 跑包内测试永远照不出来。
      奥兰迪亚那份同名口（`content/persistence/players.py::get_player_groups`）也是零参，
      两款游戏同一契约。
    ★ 2026-10-01（数据共享）：档行归一到 `WORLD` 后，players 表里没有真实群号了 ⇒
      本口改扫 **meta 的 `active_group:*`**（写档时顺手记的活跃群）——返回内容与原语义
      一致（「有玩家活跃过的群号」），广播扇出不受数据共享影响。
    """
    with _LOCK:
        c = connect()
        try:
            rows = c.execute(
                "SELECT k FROM %s WHERE k LIKE ?" % TBL_META,
                ("active_group" + META_SEP + "%",)).fetchall()
        finally:
            c.close()
    out = []
    for r in rows:
        k = str(r["k"])
        g = k.split(META_SEP, 1)[1] if META_SEP in k else ""
        if g and g not in out:
            out.append(g)
    return out


def groups_of_player(uid):
    """某个 uid 落在哪个世界（**不是**广播群表 —— 那口是 `get_player_groups`）。

    ★ 2026-10-01（数据共享）：档只有一份（键 = `WORLD`）⇒ 单世界语义下恒 `[WORLD]`；
      「他活跃过哪些群」是广播表的问题，归 `get_player_groups` —— 两套语义各走各的口。
    """
    with _LOCK:
        c = connect()
        try:
            rows = c.execute("SELECT group_id FROM %s WHERE uid=?" % TBL,
                             (str(uid or ""),)).fetchall()
        finally:
            c.close()
    return [r["group_id"] for r in rows]


def all_players(group_id=None):
    """本世界所有玩家档 —— 榜 / 名册的唯一原料（`group_id` 参数保签名但**不再筛世界**）。

    ★ 2026-10-01（数据共享）：档行归一到 `WORLD` ⇒「按群过滤」这个维度在游戏里不存在了，
      任何 group_id（含私聊的 `private`）进来都回**全表** —— 榜/名册本来就是全服口径。
      签名不改：宿主与包内调用方（`排行` / 名册）照旧传，语义由本 docstring 定义。

    ★ fail-closed（★ 审计 L1702-同族，读口余量）：原为 `except Exception: d = {}` ——
      **坏档被静默降级成空档**。`{}` 在下面两个消费端里**与「这个人没有档」完全同义**：

        · `content/cmds_self.py::_board_rows`  `d.get("name")` 空 ⇒ 整行 `continue`
          ⇒ 玩了几十小时的玩家**从榜上消失**（实测：三人库得榜 2 人，零报错）；
        · `content/party.py::rows_of` 名册 docstring 白纸黑字写着「读不到 ⇒ 抛」，
          却在 `d if isinstance(d, dict) else {}` 那一步又被降级一次
          ⇒ **同族反例**（本模块 :128 / :179 / group_get 三处早已 fail-closed，唯独这里漏了）。

      与 `get_player` / `update_player` / `group_get` 同一把尺：**行在、但值读不出来
      ≠ 没有存档**。宁可整口喊出来（点名 uid），也不要让一个人的档被当成空白。
    """
    with _LOCK:
        c = connect()
        try:
            rows = c.execute("SELECT group_id, uid, data FROM %s" % TBL).fetchall()
        finally:
            c.close()
    out = []
    for r in rows:
        try:
            d = json.loads(r["data"])
        except Exception as exc:                                # noqa: BLE001
            raise RuntimeError(
                "%s：存档行读不出来（group_id=%r uid=%r）—— 拒绝降级成空档"
                "（{} 在榜/名册里与「没有这个人」同义 ⇒ 玩家会从榜上凭空消失）：%s"
                % (__name__, r["group_id"], r["uid"], exc)
            ) from exc
        if not isinstance(d, dict):
            raise RuntimeError(
                "%s：存档行的 data 顶层不是 dict（group_id=%r uid=%r，实际 %s）"
                "—— 拒绝降级成空档（同上）"
                % (__name__, r["group_id"], r["uid"], type(d).__name__)
            )
        out.append({"group_id": r["group_id"], "uid": r["uid"], "data": d})
    return out


# ── 按群存的共同档（★ B3-26：多人在场时的「场」这类数据） ─────────
def meta_key(scope, group_id) -> str:
    """共同档的键 `<scope>:<group_id>` —— 形状只有这一处，别在调用方拼。"""
    s = str(scope or "").strip()
    if not s or META_SEP in s:
        raise ValueError("scope 必须是非空且不含 %r 的简单词：%r" % (META_SEP, scope))
    return "%s%s%s" % (s, META_SEP, str(group_id or ""))


def group_get(scope, group_id):
    """读一条按群存的共同档（没写过 → None）。

    ★ fail-closed 两档（与 `get_player` 有意不同，理由在下面）：
      · 行不在 = **没写过** ⇒ None（调用方按「没有这一场」处理）；
      · 行在、但值不是 JSON 对象 = **写坏了** ⇒ 当场抛 —— 静默回 None 会让
        「这一场」凭空消失（打到一半的战斗被当成没开过），宁可喊出来。
    """
    with _LOCK:
        c = connect()
        try:
            row = c.execute("SELECT v FROM %s WHERE k=?" % TBL_META,
                            (meta_key(scope, group_id),)).fetchone()
        finally:
            c.close()
    if not row:
        return None
    try:
        v = json.loads(row["v"])
    except Exception as e:                                   # noqa: BLE001
        raise RuntimeError("%s：共同档 %s 读不出来（数据坏了，不当成「没有」）：%s"
                           % (__name__, meta_key(scope, group_id), e))
    if not isinstance(v, dict):
        raise RuntimeError("%s：共同档 %s 不是一个对象（%r）"
                           % (__name__, meta_key(scope, group_id), type(v).__name__))
    return v


def group_set(scope, group_id, value) -> bool:
    """写一条按群存的共同档（整条覆盖；值必须是 JSON 对象）。"""
    if not isinstance(value, dict):
        raise ValueError("共同档只存对象（不是对象就别塞）：%r" % (type(value).__name__,))
    blob = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    with _LOCK:
        c = connect()
        try:
            c.execute("INSERT INTO %s(k, v) VALUES(?,?) "
                      "ON CONFLICT(k) DO UPDATE SET v=excluded.v" % TBL_META,
                      (meta_key(scope, group_id), blob))
            c.commit()
        finally:
            c.close()
    return True


def group_del(scope, group_id) -> bool:
    """删一条按群存的共同档（没写过也回 True —— 幂等）。"""
    with _LOCK:
        c = connect()
        try:
            c.execute("DELETE FROM %s WHERE k=?" % TBL_META, (meta_key(scope, group_id),))
            c.commit()
        finally:
            c.close()
    return True


def player_handles():
    """包内取件口（正本 = 本模块）。"""
    return _H
