# -*- coding: utf-8 -*-
"""《阿斯特兰》路由未命中的回话（P-54）—— 引擎那一格**必需注入**的内容半边。

口径（唯一真源 = texts 域那一条槽位；本模块不写中文文案）
------------------------------------------------------------------
引擎 `saintess_engine/host/runtime.py::_miss_reply()` 按 P-54（2026-09-26）起**不再自带
玩家文案**：玩家敲的词没命中任何包内声明时，它去问 `config` 里那一格
`route_miss_text_fn`（形状 `fn(text, prefix) -> str | 序列`）；**没装配 —— 或装了却给不出
文本 —— 就抛 `EngineNotConfigured`**（不静默编一句兜底）。

⇒ 本包不挂这个口，新引擎一上线，玩家敲一个没命中的词**一句话都拿不到**。原先引擎内置的
那句中文里还带着一个本服不一定有的**宿主命令名**（`<prefix>help`），那半也一并去掉了：
这一句**只许指向本包自己声明的指令** —— 指向哪儿都不许编（说「敲 X」而 X 不存在 =
把玩家支去再撞一次空）。

三件
------------------------------------------------------------------
① `line(text, prefix)` —— `route_miss_text_fn` 供体：那一句（槽位渲染，把玩家敲的那个词嵌
   进去）。代码里零中文：这里只传槽位名 `SLOT`；
② `declared_usages()`  —— 本包**可见**声明里那些指令名（现读 `content/data/commands.json`，
   不手写镜像表）；
③ `check_domain()`     —— 装配期对账（fail-closed）：槽位在不在 texts 域里 + 那一句引号里
   指向的指令名**是不是本包可见声明里的那一个** —— 答不上来当场抛
   （撤改验证那一条在 `scripts/probe_miss.py`）。

`prefix` 是引擎给过来的宿主前缀（默认 `/`）—— **本模块故意不用它**：这一句里不许出现宿主
命令名（写死一个 `/help` = P-54 要治的那个病）。形参留着只为与引擎的钩子形状逐字对齐。
"""
from __future__ import annotations

import io
import json
import os
import re

from .cmds_ast import T

_DIR = os.path.dirname(os.path.abspath(__file__))
_TEXT = os.path.join(_DIR, "data", "texts.json")
_CMDS = os.path.join(_DIR, "data", "commands.json")

#: 那一句的槽位名。★ 键名由「真源那份槽位表 → `scripts/rebuild_syscopy.py`」认
#:   （KEY_RE = `^(SCENE|…|SYS)_[A-Z0-9_]+$`）；本模块只引用它，文案在 texts 域。
SLOT = "SYS_CMD_MISS"

#: 槽位里引号括起来的那一族（`「…」` / `『…』`）—— 核「指向的指令真存在」用它。
#: 占位那一格（`{word}`）不算引用：它不是指令名。
_QUOTED = re.compile("[\u300c\u300e]([^\u300d\u300f]+)[\u300d\u300f]")

#: 取不到文案时 `T` 回的那串标记（fail-closed：宁可当场抛，也不把这串东西给玩家）
_MARK = "[MISSING TEXT"

#: 回显那个词最多留几个字（★ F6 · QA P4 E-13）
#: 玩家敲 32 字长句时，原先是**整句原样回显**一遍 —— 在群里等于刷一长条。
#: 截断只动**那半句回显**（省略号是排版符号，不是文案）：文案本体仍在 texts 域那一条槽位里。
ECHO_MAX = 15

_CACHE: dict = {}


def _load(path: str):
    """读一份包内数据表（缓存；坏文件当场抛 —— 别静默当空表）。"""
    if path not in _CACHE:
        _CACHE[path] = json.loads(io.open(path, encoding="utf-8").read())
    return _CACHE[path]


def slot_record() -> dict:
    """texts 域里那一条槽位（缺 ⇒ 空 dict）。"""
    return _load(_TEXT).get(SLOT) or {}


def declared_usages() -> set:
    """本包**可见**声明里那些指令名（`commands.json` 的 `usage`）—— 现读，不手写镜像表。

    只看 `visible=True` 的：不可见声明是平台内部 gate（不是给玩家敲的词），指向它等于指错。
    """
    out = set()
    for rec in _load(_CMDS).values():
        if not isinstance(rec, dict) or not rec.get("visible"):
            continue
        u = str(rec.get("usage") or "").strip()
        if u:
            out.add(u)
    return out


def referenced_commands(value=None) -> list:
    """那一句里**引号指向的指令名**（占位那一格不算）。

    ★ 「它指的是哪条指令」只许从文案里现读 —— 别在代码里另写一份「它指的是帮助」：
      文案一改，判据跟着动（探针 `scripts/probe_miss.py` 就是拿它现算的）。
    """
    v = str(slot_record().get("value") if value is None else value)
    return [x for x in _QUOTED.findall(v) if "{" not in x and "}" not in x]


def line(text, prefix=None) -> str:              # noqa: ARG002 —— prefix 只为对齐钩子形状
    """`route_miss_text_fn` 供体：没接住的那个词 → 一句玩家看得见的话（槽位渲染）。

    ★ 取不到文案 ⇒ 当场抛（**不把那串标记漏给玩家**）：这一格是引擎的必需注入，
      它自己已经「装了却给不出文本 ⇒ 抛」，本包这一头照同一条规矩办。
    ★ F6：回显的那个词超长就截断（`ECHO_MAX`）—— 别把玩家那句 32 字原样贴回群里。
    """
    out = str(T(SLOT, word=echoed(text)))
    if _MARK in out:
        raise KeyError("路由未命中的回话取不到文案（槽位 %r 不在 texts 域里）" % (SLOT,))
    return out


def echoed(text) -> str:
    """回话里那个词（★ F6）：超 `ECHO_MAX` 字就截断成「<前 N 字>…」。"""
    w = str(text or "").strip()
    return w if len(w) <= ECHO_MAX else w[:ECHO_MAX] + "…"


def check_domain() -> dict:
    """装配期对账（fail-closed）：① 槽位在 texts 域里且真有字 ② 指向的指令真在本包声明表里。

    ② 是这一条的要点：那一句给玩家的**下一步**必须真存在 —— 指向一条不存在的指令，玩家照着
    敲只会再撞一次空。（引擎守住了「不许编兜底」，这一头得内容侧自己守。）
    """
    rec = slot_record()
    value = str(rec.get("value") or "")
    if not value.strip() or _MARK in value:
        raise KeyError("路由未命中的回话槽位 %r 不在 texts 域里（或空着）—— 玩家敲一个没命中的"
                       "词会一句话都拿不到（引擎那一格是必需注入）" % (SLOT,))
    refs = referenced_commands(value)
    known = declared_usages()
    bad = [x for x in refs if x not in known]
    if bad or not refs:
        raise KeyError("路由未命中的回话（槽位 %r）指向了不存在的指令 %s —— 本包可见声明里没有"
                       "（把玩家支去撞空这一条当场拦下）" % (SLOT, bad or "（一个都没指）"))
    return rec
