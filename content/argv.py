# -*- coding: utf-8 -*-
"""指令取参的唯一口（`content/argv.py`）。

参怎么切，跟着**该指令自己的声明**走（`commands` 域里的 `patterns`）——
不另抄一份镜像表，也不按「第一个空白」硬切。

    `装备 铁剑` / `装 铁剑` / `装铁剑`   ->   `铁剑`
    `装备`（裸指令名）                    ->   ``（参是空的 —— 调用方按「没带参」处理）

做法 = 取 pattern 里 `^` 之后**连着写的字面量**（最长命中的那一条），从原文里剥掉它。
声明里「词与参之间不要求空白」（`^装\\s*(.+)$`）与「要求空白」（`^搭话\\s+(.+)$`）
两种写法都照着走：连写的形态因此取得到参（原先按空白切会把 `装铁剑` 取空）。

★ 裸指令名（`装备`）会命中单字别名 `^装\\s*(.+)$` —— 剥掉声明里那条更长的前缀
  （`装备` 自身）之后，参正好是空串 ⇒ 调用方说「没带参」，不会拿后一个字当参
  （原先会把「备」当名字，回一句带空引号的错话）。

本文件的代码里一个中文都没有（中文只出现在**声明**这份数据里 —— probe_copy ②）。
"""
from __future__ import annotations

from .cmds_ast import _data

__all__ = ["decl", "lit_prefix", "hit_prefix", "arg_of"]

#: 正则里的元字符（`lit_prefix` 扫到它就停 —— 前缀是「连着写的那几个字」）
_META = chr(92) + "[](){}.*+?|$^"          # 反斜杠不进源码（避转义）

_DECL_CACHE: dict = {}


def decl(key: str) -> dict:
    """一条声明（`commands` 域里的那一条）—— 取参 / 呈现都读它，不另抄。"""
    if key not in _DECL_CACHE:
        _DECL_CACHE[key] = (_data("commands") or {}).get(key) or {}
    return _DECL_CACHE[key]


def lit_prefix(pat: str) -> str:
    """`^存放\\s*(.+)$` -> `存放`：取 `^` 之后**连着写的字面量**，遇元字符就停。"""
    s = str(pat or "")
    i = 1 if s.startswith("^") else 0
    out = []
    while i < len(s) and s[i] not in _META:
        out.append(s[i])
        i += 1
    return "".join(out)


def hit_prefix(key: str, raw: str) -> str:
    """原文命中了哪条 pattern 的**字面量前缀**（最长的一条）—— 一条都没命中给空串。"""
    best = ""
    for pat in (decl(key).get("patterns") or []):
        pre = lit_prefix(pat)
        if pre and raw.startswith(pre) and len(pre) > len(best):
            best = pre
    return best


def arg_of(env, key: str = "", default: str = "") -> str:
    """从玩家原文取参。

    `key` 不给就用 `env.key`（本次命中的那条声明）。声明认不出（探针直调 / 老调用方）
    就退回「按第一个空白切」的老口径 —— 两种切法对**带空白**的输入结果一样。
    """
    raw = (getattr(env, "text", "") or "").strip()
    key = key or getattr(env, "key", "") or ""
    pre = hit_prefix(key, raw) if key else ""
    if pre:
        return raw[len(pre):].strip()
    parts = raw.split(None, 1)
    return parts[1].strip() if len(parts) > 1 else default
