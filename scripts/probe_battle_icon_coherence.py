# -*- coding: utf-8 -*-
"""探针：**战斗日志那一屏**的「同语义不同锚」（P2-13 · 补 `probe_icon_consistency` 的结构盲区）

为什么有这条线
--------------------------------------------------
鱼鱼口径原话：「emoji 是可以的……只要很规整观感好问题就不大」「我甚至觉得适当的 emoji 会更好」
=> **emoji 多与少都不是缺陷**；真判据 = **同一界面内用法一致**。

★ 上一支（`probe_icon_consistency` ①~⑥）够不着的地方
--------------------------------------------------
那一支靠 AST 扫 `content/*.py` 里的 `T("槽位", …)` 调用点来拼「同一屏」。
但**战斗日志那 62 条**（`content/rules/battle_text.json::slots` 全量）在本包里**零个 `T()` 调用点**
—— 它们的取件口是引擎 `_cue(battle, logs, "battle.x.y", {...})` → 订阅表 → 引擎 `render_*`
（`content/battle_text.py` 文件头「引擎这一侧现在长什么样」那一节写的正是这件事）。
⇒ **整个战斗屏在那一支的结构上隐形**：它报「全绿」时压根没看过这 62 条。
★ 这是「门禁的盲区常常是印而不判」的同族 —— 不是判据写松了，是**判据够不着**。

本支怎么补
--------------------------------------------------
① **「同一屏」不靠猜**：对战斗日志有更硬的定义 —— **同一个引擎函数里连着发的那几条 cue
   = 玩家看到它们挨着印的那一屏**。定义域现扫引擎源码（AST 取每个 `_cue(…)` 第三段实参所在
   的函数），**不手写名单**（域/表跟装载口·定义方走）。
② **★ 为什么不直接判「同屏所有行首锚必须同一个」** —— 那是**假红**，本支第一版真踩了：
   真源 26_ §2.2 的 emoji 语义分组表本来就有 16 个语义、覆盖一整场战斗；
   引擎 `effects.py::act_apply` 一个函数就发 8 条（增益 / 免疫 / 叠层 / 命中就绪四族），
   按「同屏同锚」判会把**本来就该不同的**判成红（实测 4 处全是这类）。
   ⇒ 判据收成**「同一语义不许两个锚」**：把屏内那些行按**句中那个语义动词**分组
   （现算：句子里出现同一个语义词的算一族），**只对一族内锚不统一的开**。
③ ★ **不钉「emoji 覆盖率」**（鱼鱼口径：emoji 少不是缺陷）——只判一致性。

本支不替代 `probe_icon_consistency`：那边管「有的带锚有的不带」与命令层的角色分组，
这边管战斗屏那一族的「同语义不同锚」。两条并着跑。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_battle_icon_coherence.py
"""
from __future__ import annotations

import ast
import io
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = Path(os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine"))
sys.path.insert(0, str(REPO))

#: emoji / 图标字符（与 probe_icon_consistency 同一份口径，逐字抄，别两处各写一套）
EMO = re.compile(u"[☀-➿⬀-⯿\U0001F000-\U0001FAFF"
                 u"✅❌⚠✔✦️]")

TX = json.load(io.open(REPO / "content" / "data" / "texts.json", encoding="utf-8"))
SLOTS = json.load(io.open(REPO / "content" / "rules" / "battle_text.json",
                          encoding="utf-8"))["slots"]      # 引擎 cue 名 → texts 槽位名

#: 语义分组词 —— ★ 判据的**收紧点**：不按「同屏」判（同屏本来就该有多种语义），
#: 按「同屏 + 同一个语义词」判。词表只放**语义唯一**的那些动词（全表圈下来只有一族）；
#: ★ 每个词都是**当跑核对过的**（见下方表）。反例：「生效」一个词同时圈住
#:   `COMBAT_EFFECTS_ON_HIT_READY`（「手出效果就绪，X 刻内生效」=被动生效）与 `COMBAT_ACTIONS_EFFECT_ON`（「{key} 生效」），
#:   而 `COMBAT_EFFECTS_IMMUNE_*`（「未生效」=被免疫挡下来）——**三个语义**。故改用「未生效」，
#:   它全表只圈住那两条免疫行（正好就是本条判据的那族）。
SEM_KW = ("减免", "减伤", "恢复", "治疗", "未生效", "触发", "免疫")


def _val(slot):
    e = TX.get(slot)
    return (e.get("value", "") if isinstance(e, dict) else e) or ""


def _lead(v):
    m = EMO.match(v.strip())
    return m.group(0) if m else None


# ── 「同一屏」= 同一个引擎函数里连着发的那些 cue（现扫，不手写）────────────────
def _engine_cue_screens():
    """{引擎相对路径: {函数名: [cue 名, …]}} —— 每个 `_cue(...)` 的第三段实参。"""
    out = {}
    if not ENGINE.is_dir():
        return out
    for p in sorted(ENGINE.rglob("*.py")):
        if "__pycache__" in p.parts or p.as_posix().endswith("battle/cues.py"):
            continue                       # cues.py 是「cue 的定义处」，不是「发射处」
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        fns = {}
        for n in tree.body:
            if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            names = []
            for sub in ast.walk(n):
                if not isinstance(sub, ast.Call):
                    continue
                fn = sub.func
                nm = fn.id if isinstance(fn, ast.Name) else (
                    fn.attr if isinstance(fn, ast.Attribute) else None)
                if nm != "_cue" or len(sub.args) < 3:
                    continue
                a = sub.args[2]
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    names.append(a.value)
            if names:
                fns[n.name] = names
        if fns:
            out[p.relative_to(ENGINE).as_posix()] = fns
    return out


def scan():
    """产出 [(引擎文件, 函数, 语义词, {锚: [槽位…]})] —— 同屏同语义却不止一个锚。"""
    hits = []
    for rel, fns in sorted(_engine_cue_screens().items()):
        for fname, cues in sorted(fns.items()):
            rows = [SLOTS[c] for c in cues if c in SLOTS and SLOTS[c] in TX]
            if len(rows) < 2:
                continue                      # 孤零零一行不构成「并列」
            for kw in SEM_KW:
                grp = [s for s in rows if kw in _val(s)]
                if len(grp) < 2:
                    continue
                ems = {}
                for s in grp:
                    e = _lead(_val(s))
                    if e:
                        ems.setdefault(e, []).append(s)
                # ★ 只对「全带锚」的组开：部分带归 probe_icon_consistency ①
                if ems and sum(len(v) for v in ems.values()) == len(grp) and len(ems) > 1:
                    hits.append((rel, fname, kw, ems))
    return hits


ok = True


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print(u"  %s %s%s" % (u"✓" if cond else u"✗", label,
                           (u"  —— %s" % extra) if extra else u""))


print(u"探针：战斗屏「同语义不同锚」（P2-13）")
print(u"  · 引擎 cue 声明 %d 条 · 文案槽位 %d 条 · 语义分组词 %d 个"
      % (len(SLOTS), len(TX), len(SEM_KW)))
print(u"  · 补的是上一支的结构盲区：那 62 条在 content/*.py 里零个 T() 调用点")
print(u"  · ★ 不按「同屏同锚」判（假红：真源 §2.2 本来就 16 个语义，act_apply 一个函数发 8 条）")

print(u"① 同屏 + 同一语义词 ⇒ 行首锚不许不统一")
_hits = scan()
chk(u"① 战斗屏同语义多锚 = 0 处", not _hits,
    u"" if not _hits
    else u"\n".join(u"      %s::%s「%s」 %s"
                     % (h[0], h[1], h[2],
                        u" · ".join(u"%s→%s" % (e, "/".join(v)) for e, v in sorted(h[3].items())))
          for h in _hits))

# ① 的反证：真盘 0 缺陷时没有现成的不一致组 ⇒ 自己造一个（把某条的锚换成表里已有的另一个）。
_p = None
for rel, fns in sorted(_engine_cue_screens().items()):
    for fname, cues in sorted(fns.items()):
        rows = [SLOTS[c] for c in cues if c in SLOTS and SLOTS[c] in TX]
        for kw in SEM_KW:
            grp = [s for s in rows if kw in _val(s)]
            if len(grp) < 2:
                continue
            ems = {}
            for s in grp:
                e = _lead(_val(s))
                if e:
                    ems.setdefault(e, []).append(s)
            if len(ems) == 1 and sum(len(v) for v in ems.values()) == len(grp):
                _p = (rel, fname, kw, list(ems)[0], grp[0])
                break
        if _p:
            break
    if _p:
        break

_all_emo = set()
for _s in TX:
    _all_emo.update(EMO.findall(_val(_s)))

if not _p:
    chk(u"① 找得到反证注入点", False, u"★ 判据可能恒绿，请核")
else:
    _rel, _fn, _kw, _only, _strip = _p
    _other = next((x for x in sorted(_all_emo) if x != _only), None)
    if not _other:
        chk(u"① 反证用 emoji 得到", False, u"表里只有一种行首锚")
    else:
        _orig = TX[_strip]["value"]
        try:
            TX[_strip]["value"] = EMO.sub(_other, _orig, count=1)
            _h = scan()
            chk(u"① %s::%s 把 %s 的行首锚 %s 换成 %s ⇒ 判据当场红（有牙）"
                % (_rel, _fn, _strip, _only, _other), bool(_h), u"命中 %d 处" % len(_h))
        finally:
            TX[_strip]["value"] = _orig
        chk(u"① 还原 ⇒ 红集回到 0（判据没留下残留）", not scan())

print(u"结果：%s" % (u"全绿 ✓" if ok else u"有红 ✗"))
sys.exit(0 if ok else 1)
