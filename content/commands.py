# -*- coding: utf-8 -*-
"""《阿斯特兰》包内命令表（`content/commands.py`）。

一套表，两处用
--------------
* 宿主运行时：引擎 `Package.command_handlers()` 读本模块的 `COMMANDS`
  （→ 守卫 → `Env` → handler → 回话）；
* 编辑器：同一张表拿指令清单，不另抄。

本包**不写薄壳**：实现体在 `content/cmds_ast.py`，声明表
（`content/data/commands.json`）的每条指令用 `bind` 点名它：

    "look": {"patterns": ["^观察$", "..."],
             "bind": {"handler": "content.cmds_ast:look", "call": "run",
                      "args": ["uid", "player"]}}

`bind.call` 三种（引擎 `saintess_engine.command.binding`）：`run` / `messages` / `sync`；
`bind.args` 三槽位：`group_id` / `uid` / `player`。调用帧 `handler(sink, *args)` ——
实现体是 async generator，`yield` 出行文本。

★ 没有 `bind` 的指令（声明了、包内还没实现）：引擎原本回显声明本身
（`saintess_engine/host/runtime.py::declared_echo`：`【<key>】(包内声明) …` + 「包内
content/commands.py 里没有它的 handler」）—— 那是**把内部 key 与文件路径漏给玩家**。
P-23 起由包侧接住（`load_declared_soon`）：这些声明也登记一个处理器，只说槽位文案
（`SYS_CMD_SOON`），玩家看到的是人话。**声明本身一条不动**（台账可见：96 声明 / 45 无实现），
只是「43 条没实现」不再由玩家来发现。
"""
from __future__ import annotations

import os

from saintess_engine.command import CommandRegistry, CommandSpec, bind_handler, load_table

__all__ = ["COMMANDS", "REGISTRY", "DECLARATION_PATH", "load_declared_bindings", "BOUND_KEYS",
           "load_declared_soon", "UNBOUND_KEYS"]

#: 命令表：key → {"guards", "params", "handler"}（引擎 `Package.command_handlers()` 读它）
COMMANDS: dict = {}

#: 处理器登记表（引擎形状）
REGISTRY = CommandRegistry(name="aetheran.commands")

#: 声明真源（引擎 `Package.command_declarations()` 也读它）
DECLARATION_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "data", "commands.json")


def _declare(key: str, handler, guards=(), params=()):
    if key in COMMANDS:
        raise KeyError("content.commands：命令 %r 重复登记" % key)
    REGISTRY.bind(key, handler, guards=tuple(guards), params=tuple(params))
    COMMANDS[key] = {"guards": tuple(guards), "params": tuple(params), "handler": handler}


def load_declared_bindings() -> tuple:
    """把声明表里带 `bind` 的条目登记成处理器，返回被登记的 key（升序）。

    fail-closed：`bind` 形状不合规 / 实现体解析不到 → import 期抛错（绝不静默少一条命令）。
    """
    table = load_table(DECLARATION_PATH)
    bound = []
    for key in sorted(table):
        entry = table[key]
        if not isinstance(entry, dict) or not entry.get("bind"):
            continue
        spec = CommandSpec.from_dict(dict(entry, key=key))
        fn = bind_handler(spec.bind, lead=lambda env: (env,),
                          where="commands.json[%s]" % key)
        params = tuple(entry.get("params") or ())
        _declare(key, fn, (), params)
        bound.append(key)
    return tuple(bound)


def _soon_handler(env):
    """「声明了、包内还没实现」的兜底处理器（形状与 `bind_handler` 的产物一致：env → list）。"""
    from . import cmds_ast as CA           # 本地 import：免得包装载期成环
    return CA.declared_soon(env)


def load_declared_soon() -> tuple:
    """把声明表里**没有 `bind`** 的条目也登记一个处理器 —— 只说人话（P-23），返回这些 key。

    fail-closed：这些声明**一条都不改**（不动 `visible`、不删声明、不编造实现），
    只是不再让引擎那句「该声明未提供处理器：包内 content/commands.py …」落到玩家眼里。
    """
    table = load_table(DECLARATION_PATH)
    soon = []
    for key in sorted(table):
        entry = table[key]
        if not isinstance(entry, dict) or entry.get("bind"):
            continue
        _declare(key, _soon_handler, (), tuple(entry.get("params") or ()))
        soon.append(key)
    return tuple(soon)


#: 由声明表 `bind` 登记的 key
BOUND_KEYS = load_declared_bindings()

#: 声明了、包内还没实现的 key（引擎不再回显内部 key —— 包侧接住）
UNBOUND_KEYS = load_declared_soon()
