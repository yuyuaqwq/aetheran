# -*- coding: utf-8 -*-
"""长列表分页的唯一口（`content/pager.py` · B4-17）。

真源
----
* `06_第一阶段垂直切片/03_风车镇_指令与回复.md` §〇 排版纪律：
  「一次回复 不超过 400 字（手机上三屏以内）」「超长的内容 分页：『下一页』/『回 <页码>』」
* `06_第一阶段垂直切片/04_指令总表.md` §背包 / §社交与系统：`背包` → 打开（分页）·
  `下一页` / `回 <页码>` → 翻页

为什么有这一层（B4-17 端到端玩出来的）
--------------------------------------
改前全仓**没有任何分页**：`背包` 列到第 20 种就写一行「…（还有 N 种）」，
**第 21 种起玩家再也看不到**（items 域 122 件，刷得出来；实测 25 种只看得见 20 种）。
而引擎早就备好了 `command/paging.py`（`page_items` / `parse_page`）与
`Env.page()` / `Env.page_items()` —— 本包**零调用方**。这一批把它接上：
切片 / 夹页 / 解析都走引擎那两个纯函数，包里**不重造第二份**（K66 的纪律）。

口径（首版 · 一处可调）
----------------------
* 一页几行 = `PER_PAGE`（背包 20 · 本群榜 10）—— 真源只给了「不超过 400 字」这个上界，
  20 行 × 每行 ≤20 字 ≈ 一屏。
* 页码的写法：列表自己带（`背包 2` / `排行 2`）· `下一页`（在**上一次看的那一列**上翻）·
  `回 <页码>`。后两条靠**光标**记着「上一次看的是哪一列」。
* ★ 光标存在**内存**里（按 group + uid 存 · **不落档**）：看一眼列表是**只读**动作
  （`probe_copy` / `probe_cmds` 都钉着「看一眼不动档」）⇒ 光标丢了最多重敲一次列表名。
* 光标**只在真的分了页**（`pages > 1`）时记：一页装得下的列表不记
  —— 那时敲『下一页』得到的是『先打开一个列表…』那句**引导**
  （它是一句指路，不是对玩家刚才做了什么的断言）。
* 页码越界**夹取**（引擎 `page_items` 的口径：夹到 `[1, pages]`）—— 不报错、不回空。
"""
from __future__ import annotations

from .argv import arg_of

__all__ = ["PER_PAGE", "per_page", "page_no", "render", "cursor", "forget",
           "page_next", "page_back"]

#: 每个列表一页多少行（★ 唯一登记处：新加一个分页列表就在这儿加一行）
PER_PAGE = {"bag": 20, "ranking": 10}

#: 一页几行的默认值（`PER_PAGE` 里没登记的 kind 用这个 —— 今天没有这样的 kind）
PER_PAGE_DEFAULT = 20

#: 光标最多记多少个人（进程内小表；超了从最早那条开始丢 —— 与 `instance` 的护栏同一个意思）
CURSOR_MAX = 512

#: (group_id, uid) -> (kind, page, pages) —— **不落档**（见模块头注）
_CURSOR: dict = {}


def per_page(kind: str) -> int:
    """这一列一页几行。"""
    return int(PER_PAGE.get(str(kind or ""), PER_PAGE_DEFAULT))


def page_no(env, default: int = 1) -> int:
    """本条消息里写的页码。

    参按**这条指令自己的声明**剥（`content/argv.py`，不是按空白切），
    剥出来的数字交引擎 `Env.page`（`command.parse_page`）解 —— 解不出就是 `default`。
    """
    try:
        return int(env.page(arg_of(env), default=default) or default)
    except Exception:                                        # noqa: BLE001 —— 解不出就当 default
        return int(default or 1)


def _key(env):
    """光标挂在谁身上（群 + 人）。"""
    return (str(getattr(env, "group_id", "") or ""), str(getattr(env, "uid", "") or ""))


def remember(env, kind: str, page: int, pages: int) -> None:
    """记下「这个人上一次看的是哪一列、第几页」。"""
    _CURSOR[_key(env)] = (str(kind), int(page), int(pages))
    while len(_CURSOR) > CURSOR_MAX:
        _CURSOR.pop(next(iter(_CURSOR)), None)


def cursor(env):
    """(`kind`, `page`, `pages`)；没翻过任何列表 = `("", 0, 0)`。"""
    return _CURSOR.get(_key(env)) or ("", 0, 0)


def forget(env) -> None:
    """忘掉这个人的光标（测试 / 换列时用）。"""
    _CURSOR.pop(_key(env), None)


def render(env, kind: str, head, rows, page=None, tail=None) -> list:
    """一页的完整输出：抬头 + 本页条目 + 尾注 +（分了页才有）页脚；同时记下光标。

    `head` / `rows` / `tail` 都由调用方给（行怎么拼是各列表自己的事）—— 这一层只管切页。
    分母（共几页）与夹过的页码都由引擎 `page_items` 现算，页脚显示的也是**夹过的**页码。
    ★ 页脚**永远是最后一行**（奥兰迪亚 v130.3 那笔——「背包页数移底部」）
      ⇒ 列表自己的尾注（如榜那句「只记到本群」）走 `tail` 传进来，别在外面 `yield`。
    """
    from .cmds_ast import T                            # 本地 import：免得包装载期成环
    want = page_no(env) if page is None else int(page)
    page_rows, pages, page = env.page_items(list(rows), want, per_page=per_page(kind))
    out = list(head) + list(page_rows) + list(tail or [])
    if pages > 1:
        out.append(T("SYS_PAGE_FOOT", page=page, pages=pages))
        remember(env, kind, page, pages)
    return out


def _again(env, sink, uid, player, kind):
    """某一列「再渲染一遍」的入口（★ 唯一登记处：新加一个分页列表就在这儿加一行）。

    统一成「给一个页码 → 吐这一页」的形状；声明里参数不同的（榜是五参帧）在这一层补齐
    —— 不让 pager 去猜调用形状。
    """
    if kind == "bag":
        from .cmds_ast import bag_page
        return lambda page: bag_page(env, sink, uid, player, page)
    if kind == "ranking":
        from .cmds_self import ranking_page
        gid = str(getattr(env, "group_id", "") or "")
        return lambda page: ranking_page(env, sink, gid, uid, player, page)
    return None


async def _turn(env, sink, uid, player, kind, page):
    """翻到 `kind` 这一列的第 `page` 页（页码交引擎夹取）。"""
    from .cmds_ast import T
    more = _again(env, sink, uid, player, kind)
    if not more:
        yield T("SYS_PAGE_NONE")
        return
    async for line in more(page):
        yield line


async def page_next(env, sink, uid, player):
    """`下一页` —— 在上一次看的那一列上翻一页。"""
    kind, page, _pages = cursor(env)
    async for line in _turn(env, sink, uid, player, kind, page + 1):
        yield line


async def page_back(env, sink, uid, player):
    """`回 <页码>` —— 回上一次看的那一列的第 N 页。"""
    kind, _page, _pages = cursor(env)
    async for line in _turn(env, sink, uid, player, kind, page_no(env, default=1)):
        yield line
