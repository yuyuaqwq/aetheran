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

★ 没有 `bind` 的指令：引擎回显声明（`【key】desc / 用法：…`）—— 这是有意的，
  让"声明了但没实现"看得见，而不是静默少一条。
"""
from __future__ import annotations

import os

from saintess_engine.command import CommandRegistry, CommandSpec, bind_handler, load_table

__all__ = ["COMMANDS", "REGISTRY", "DECLARATION_PATH", "load_declared_bindings", "BOUND_KEYS"]

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


#: 由声明表 `bind` 登记的 key
BOUND_KEYS = load_declared_bindings()
