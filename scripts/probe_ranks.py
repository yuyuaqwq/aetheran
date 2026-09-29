# -*- coding: utf-8 -*-
"""探针：公会评级阶梯 · 换证（B4-16）—— 第 40 支。

为什么有这条线（文档里写着、代码里没做的真缺口）
--------------------------------------------------
`06_第一阶段垂直切片/04_指令总表.md §公会与委托` 写着 `升级证` `换证`（守卫 评级达标），
`06_第一阶段垂直切片/05_玩法数值口径_v1.md §一` 写着
「评级 ｜ 见习 → 铜（交 5 条）→ 银（交 15 条 + 打掉 1 个头目）→ 金（第一阶段到银为止）」，
`SYS_MINE_RANK` 还把这一整套阶梯印给玩家看 —— 可这一条声明**没有处理器**、
阶梯也**没有机器可读的那一份** ⇒ 玩家交够 5 条也换不了证：
公会那条线（登记 → 悬赏 → 接 → 交）走到「升级」就断了，而那句文案还一直印着「见习」。

判据（一条都不许松）
  ① 口径表 `content/rules/ranks.json` 的档序 / 门槛 == 真源 `05_玩法数值口径_v1.md §一`
     那一行**现解析**值（探针自己算，不引用生成器）
  ② 档名是文案：每一档的 `RANK_<ID>` 槽位都在 texts 里、非空、而且**逐档等于真源里那个中文名**
     （id 顺序 = 真源顺序 —— 两头都数一遍，防「表里一档、文案另一档」）
  ③ 阶梯形状：第一档 0/0 · 门槛一档比一档高 · 停标记那句说的是「到<最后一档>为止」
  ④ 静态守卫：读 `content/rules/ranks.json` 的只许 `content/ranks.py` · 档上那格 `flags["rank"]`
     只许在 `content/ranks.py` 里读 / 写（K74 那一族）· 台阶那句话不许再抄进代码或文案
  ⑤ 真宿主真敲六档（同一份档往下走）：无证 ⇒ `SYS_RANK_NOCARD` · 0 条 ⇒ 只回「下一档要什么」
     且**档一个字不动** · 够 5 条 ⇒ 升铜（回话 + 档上 `flags.rank` + 落档）·
     再敲 ⇒ 「下一档 银」且档不动 · 只补头目不够（两个门槛都要）· 15 条 + 1 头目 ⇒ 升银 ·
     再敲 ⇒ 到头了且档不动
  ⑥ `评级` 印的是**当前档**（换一份档再敲，第一行跟着变 —— 不是写死的那一档）·
     到顶时改印「到这儿为止」
  ⑦ `我的委托` 里那一行与 `评级` 第一行**逐字同一句**（同一个槽位 · tier 现取）
  ⑧ 覆盖面：`评级` / `换证` 两条 handler 都**真调** `content/ranks.py`；拼 `RANK_` 槽位的只许它一处

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_ranks.py
"""
from __future__ import annotations

import ast
import io
import json
import os
import re
import sys

ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.environ.get("AST_PLAN", "C:/Users/yuyu/aetheran-plan")
sys.path.insert(0, ENGINE)

from saintess_engine.host.runtime import Host             # noqa: E402  (真宿主契约)

NL = chr(10)
FIXED = 1790308800          # 2026-09-25 12:00 +08:00（昼 —— 与 probe_cmds / probe_shop 同一根假钟）
UID = "u_ranks_probe"
DOC = os.path.join(PLAN, "06_第一阶段垂直切片", "05_玩法数值口径_v1.md")

OK, BAD = [], []


def ok(msg):
    OK.append(msg)
    print("  OK  %s" % msg)


def bad(msg):
    BAD.append(msg)
    print("  X   %s" % msg)


class Ad(object):
    """最小适配器（照 scripts/e2e_drive.py 的真宿主契约）。"""

    def __init__(self, seed=None):
        self.out = []
        self.saved = {UID: dict(seed)} if seed else {}

    def recv(self):
        return None

    def load_player(self, uid):
        return self.saved.get(uid)

    def save_player(self, uid, data):
        self.saved[uid] = dict(data) if isinstance(data, dict) else data

    def say(self, to, text):
        self.out.append(str(text))


def drive(ad, host, text, uid=UID):
    ad.out = []
    host.handle({"uid": uid, "group_id": "g_ranks_probe", "text": text})
    return list(ad.out)


def _load(rel):
    with io.open(os.path.join(REPO, rel), encoding="utf-8") as f:
        return json.load(f)


def parse_src():
    """真源那一行 -> `[(中文名, 交几条, 打掉几个头目), …]`（停标记那一档不算）。

    ★ 探针**自己解析**（不 import 生成器）—— 生成器与真源两处口径打架时这一条要能红。
    """
    txt = io.open(DOC, encoding="utf-8").read()
    hit = re.search(r"^\|\s*评级\s*\|([^|]+)\|\s*$", txt, re.M)
    if not hit:
        return None, "真源里找不到「| 评级 | … |」那一行"
    out = []
    for seg in [x.strip() for x in hit.group(1).split("→") if x.strip()]:
        if "第一阶段" in seg:
            break
        name = re.split(r"[（(]", seg)[0].strip()
        d = re.search(r"交\s*(\d+)\s*条", seg)
        c = re.search(r"打掉\s*(\d+)\s*个头目", seg)
        out.append((name, int(d.group(1)) if d else 0, int(c.group(1)) if c else 0))
    if not out:
        return None, "真源那一行切不出档来：%r" % hit.group(1)
    return out, ""


def code_strings(path):
    """源码里**不是 docstring** 的字符串常量（K46：别拿正则把注释 / 文档串也算成文案）。"""
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    doc_ids = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(n, "body", None) or []
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                doc_ids.add(id(body[0].value))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in doc_ids]


def main():
    rules = _load("content/rules/ranks.json")
    texts = _load("content/data/texts.json")
    tiers = rules.get("tiers") or []

    # ── ① 口径表 == 真源现解析（探针自己算）
    src, why = parse_src()
    if not src:
        bad("真源那边读不出来：%s" % why)
        src = []
    same = (len(src) == len(tiers) and len(src) > 0
            and all(str(t.get("id")) and a[1] == int(t.get("need_done") or 0)
                    and a[2] == int(t.get("need_chief") or 0) for a, t in zip(src, tiers)))
    if same:
        ok("口径表档序 / 门槛 == 真源 05 §一 现解析值：%s"
           % " → ".join("%s（交 %d 条 + 打 %d 个头目）" % a for a in src))
    else:
        bad("口径表与真源对不上：表 %r / 真源 %r"
            % ([(t.get("id"), t.get("need_done"), t.get("need_chief")) for t in tiers], src))

    # ── ② 档名是文案：RANK_<ID> 槽位在 texts 里、逐档等于真源那个中文名
    tpl = str(rules.get("label_tpl") or "")
    miss, dif = [], []
    for i, t in enumerate(tiers):
        key = tpl % str(t.get("id")).upper()
        rec = texts.get(key)
        if not rec or not str(rec.get("value") or "").strip():
            miss.append(key)
        elif i < len(src) and str(rec.get("value")) != src[i][0]:
            dif.append((key, rec.get("value"), src[i][0]))
    if tpl != "RANK_%s":
        bad("口径表里的槽位模板不是 RANK_%%s：%r（`content/ranks.py` 按它拼键）" % tpl)
    if not miss and not dif:
        ok("档名是文案：%d 档的 RANK_<ID> 槽位都在 texts 里、逐档等于真源那个中文名（%s）"
           % (len(tiers),
              " / ".join(str(texts[tpl % str(t.get("id")).upper()]["value"]) for t in tiers)))
    else:
        bad("档名槽位对不上：缺 %s · 不一样 %s" % (miss, dif))

    # ── ③ 阶梯形状
    shape = []
    dxt = io.open(DOC, encoding="utf-8").read()
    if not tiers:
        shape.append("一档都没有")
    else:
        if int(tiers[0].get("need_done") or 0) or int(tiers[0].get("need_chief") or 0):
            shape.append("第一档带门槛：%r" % tiers[0])
        for a, b in zip(tiers, tiers[1:]):
            if int(b.get("need_done") or 0) < int(a.get("need_done") or 0) \
                    or int(b.get("need_chief") or 0) < int(a.get("need_chief") or 0):
                shape.append("门槛倒挂：%r -> %r" % (a, b))
        if [int(t.get("order") or 0) for t in tiers] != list(range(1, len(tiers) + 1)):
            shape.append("order 不是 1..n：%r" % [t.get("order") for t in tiers])
        last = str(texts.get(tpl % str(tiers[-1].get("id")).upper(), {}).get("value") or "")
        if ("到%s为止" % last) not in dxt:
            shape.append("真源里没有「到%s为止」那句（第一阶段开到哪一档叫不准）" % last)
    if not shape:
        ok("阶梯形状：第一档 0/0 · 门槛单调 · order 1..n · 真源写着「到%s为止」"
           % texts[tpl % str(tiers[-1]["id"]).upper()]["value"])
    else:
        bad("阶梯形状不对：%s" % shape)

    # ── ④ 静态守卫
    readers, flag_uses = [], []
    for fn in sorted(os.listdir(os.path.join(REPO, "content"))):
        if not fn.endswith(".py"):
            continue
        path = os.path.join(REPO, "content", fn)
        src_txt = io.open(path, encoding="utf-8").read()
        src_txt = io.open(path, encoding="utf-8").read()
        for lit in code_strings(path):          # 只看真代码里的字符串（注释 / 文档串不算）
            if "ranks.json" in lit:
                readers.append(fn)
            if lit == "rank":                   # 档上那一格的键名（ranks.py 里的 FLAG）
                flag_uses.append("%s:%s" % (fn, lit))


    if readers == ["ranks.py"]:
        ok("静态守卫：读 `content/rules/ranks.json` 的只许 `content/ranks.py` 一处")
    else:
        bad("读那份口径表的不止 ranks.py：%s" % readers)
    if flag_uses and all(x.startswith("ranks.py:") for x in flag_uses):
        ok("静态守卫：档上那一格（键名字面量 rank）只许在 `content/ranks.py` 里出现"
           "（%d 处 —— 读 / 写都经那一个 FLAG 常量）" % len(flag_uses))
    else:
        bad("那一格有第二处出口：%s" % [x for x in flag_uses
                                  if not x.startswith("ranks.py:")])

    ladder_src = re.compile(r"交\s*\d+\s*条")
    dup = []
    for fn in sorted(os.listdir(os.path.join(REPO, "content"))):
        if fn.endswith(".py"):
            for s in code_strings(os.path.join(REPO, "content", fn)):
                if ladder_src.search(s):
                    dup.append("%s: %s" % (fn, s[:30]))
    for k, v in texts.items():
        if ladder_src.search(str(v.get("value") or "")):
            dup.append("texts.%s" % k)
    if not dup:
        ok("静态守卫：台阶那句话（「交 N 条…」）不许再抄进代码或文案 —— 只在真源与口径表里")
    else:
        bad("台阶那句话被抄了第二份（两处口径会打架）：%s" % dup)

    # ── ⑤ 真宿主真敲六档
    db = os.path.join(REPO, "_ranks_probe.db")
    try:
        os.remove(db)
    except OSError:
        pass
    seed = {"cls": "cls_knight", "race": "race_human", "name": "换证的人", "level": 3, "exp": 0,
            "gold": 0, "prev": [], "bag": {}, "equipped": {}, "codex": {}, "flags": {}}
    ad = Ad(seed)
    host = Host(ad, REPO, inject={"db_path": db, "clock": lambda: FIXED})
    host.boot()

    monsters = _load("content/data/monsters.json")
    codex = _load("content/data/codex.json")
    mbook = codex.get("monster") or {}
    chiefs = [m for m, v in monsters.items()
              if isinstance(v, dict) and v.get("role_key") == "chief" and m in mbook]

    def T(key, **slots):
        s = texts[key]["value"]
        for k, v in slots.items():
            s = s.replace("{%s}" % k, str(v))
        return s

    name_of = {str(t["id"]): texts[tpl % str(t["id"]).upper()]["value"] for t in tiers}
    seq = [str(t["id"]) for t in tiers]

    def chief_now():
        bk = (ad.saved[UID].get("books") or {}).get("monster") or {}
        return len([c for c in chiefs if int((bk.get(c) or {}).get("kills") or 0) > 0])

    def need_line(i):
        """第 i 档（0 基）要什么（门槛从口径表现取）+ 现在多少。"""
        t = tiers[i]
        st = ad.saved[UID].get("flags") or {}
        return T("SYS_RANK_NEED", tier=name_of[str(t["id"])], done=t["need_done"],
                 chief=t["need_chief"], have=len(st.get("quests_done") or []), killed=chief_now())

    def fsnap():
        return json.dumps(ad.saved[UID].get("flags") or {}, sort_keys=True, ensure_ascii=False)

    # 档一：没有证
    before = fsnap()
    got = drive(ad, host, "换证")
    if got == [T("SYS_RANK_NOCARD")] and fsnap() == before:
        ok("真敲『换证』（没办证）⇒ 只回「你还没有证」且档一字不动")
    else:
        bad("没办证时『换证』回的是：%s · 档动了吗 %s" % (got[:2], fsnap() != before))

    # 档二：有证 · 0 条
    ad.saved[UID]["flags"] = {"card": 1}
    before = fsnap()
    got = drive(ad, host, "换证")
    if got == [need_line(1)] and fsnap() == before:
        ok("真敲『换证』（有证 · 0 条）⇒ 只回「下一档 %s：…（你现在 0 条 · 0 只）」且档一字不动"
           % name_of[seq[1]])
    else:
        bad("不够门槛时『换证』回的是：%s · 档动了吗 %s" % (got[:2], fsnap() != before))

    # 档三：5 条 ⇒ 升铜（回话 + 档上那一格 + 落档）
    done5 = ["q_main_01", "q_main_02", "q_main_03", "q_side_13", "q_side_14"]
    ad.saved[UID]["flags"] = {"card": 1, "quests_done": list(done5)}
    got = drive(ad, host, "换证")
    rk = (ad.saved[UID].get("flags") or {}).get("rank")
    if got == [T("SYS_RANK_UP", tier=name_of[seq[1]])] and rk == seq[1]:
        ok("真敲『换证』（5 条）⇒ 升「%s」· 档上那一格 = %r（真落档）" % (name_of[seq[1]], rk))
    else:
        bad("够门槛那一下回的是：%s · 档上那格 = %r" % (got[:2], rk))

    # 档四：再敲 ⇒ 下一档要 15 条 + 1 个头目，档不动
    before = fsnap()
    got = drive(ad, host, "换证")
    if got == [need_line(2)] and fsnap() == before:
        ok("再敲『换证』⇒ 只回「下一档 %s：…（你现在 5 条 · 0 只）」且档一字不动" % name_of[seq[2]])
    else:
        bad("第二档门槛那一下回的是：%s · 档动了吗 %s" % (got[:2], fsnap() != before))

    # 档五：只补头目不够（两个门槛都要）
    if chiefs:
        ad.saved[UID]["books"] = {"monster": {chiefs[0]: {"day": 1, "kills": 1}}}
    before = fsnap()
    got = drive(ad, host, "换证")
    if got == [need_line(2)] and fsnap() == before:
        ok("头目够了但只交 5 条 ⇒ 照样拦（两个门槛都要，不是二选一）")
    else:
        bad("只补头目那一档回的是：%s · 档动了吗 %s" % (got[:2], fsnap() != before))

    # 档六：15 条 + 1 头目 ⇒ 升银；再敲 ⇒ 到头了
    done15 = done5 + ["q_side_%02d" % i for i in range(15, 25)]
    # ★ 交够 15 条时**保留刚才那一档** —— 换证一次只往上挪一格，不跳级
    ad.saved[UID]["flags"] = dict(ad.saved[UID].get("flags") or {},
                                  quests_done=list(done15))
    got = drive(ad, host, "换证")
    rk = (ad.saved[UID].get("flags") or {}).get("rank")
    if got == [T("SYS_RANK_UP", tier=name_of[seq[2]])] and rk == seq[2]:
        ok("15 条 + 1 个头目 ⇒ 升「%s」（第一阶段最后一档）" % name_of[seq[2]])
    else:
        bad("升最后一档那一下回的是：%s · 档上那格 = %r" % (got[:2], rk))
    before = fsnap()
    got = drive(ad, host, "换证")
    if got == [T("SYS_RANK_TOP", tier=name_of[seq[2]])] and fsnap() == before:
        ok("到顶之后再敲『换证』⇒ 只回「到「%s」为止」且档一字不动" % name_of[seq[2]])
    else:
        bad("到顶那一档回的是：%s · 档动了吗 %s" % (got[:2], fsnap() != before))

    # ── ⑥ 评级 印的是当前档
    got = drive(ad, host, "评级")
    want = [T("SYS_MINE_RANK", tier=name_of[seq[2]]),
            T("SYS_MINE_DONE", n=len(done15)),
            T("SYS_RANK_CHIEF", n=1),
            T("SYS_RANK_TOP", tier=name_of[seq[2]])]
    if got == want:
        ok("真敲『评级』（已经是最后一档）⇒ 第一行就是当前档、逐字对槽位、末尾照实说「到这儿为止」")
    else:
        bad("『评级』到顶那一档：%s / 期望 %s" % (got, want))

    # 换一份档再看一次（证明印的是**当前档**，不是写死的那一档）
    ad.saved[UID]["flags"] = {"card": 1, "quests_done": ["q_main_01"]}
    ad.saved[UID]["books"] = {}
    got = drive(ad, host, "评级")
    want2 = [T("SYS_MINE_RANK", tier=name_of[seq[0]]), T("SYS_MINE_DONE", n=1),
             T("SYS_RANK_CHIEF", n=0), need_line(1)]
    if got == want2 and got[0] != want[0]:
        ok("换个档再敲『评级』（见习 · 1 条）⇒ 第一行跟着变回「%s」，末尾改印「下一档 %s」"
           % (name_of[seq[0]], name_of[seq[1]]))
    else:
        bad("换档之后的『评级』：%s / 期望 %s" % (got, want2))

    # ── ⑦ 我的委托 里那一行 == 评级 第一行
    mine = drive(ad, host, "我的委托")
    rank_first = T("SYS_MINE_RANK", tier=name_of[seq[0]])
    if rank_first in mine:
        ok("`我的委托` 里那一行与 `评级` 第一行**逐字同一句**（%s）" % rank_first)
    else:
        bad("`我的委托` 里没有那一行：%s" % mine[-3:])

    # ── ⑨ ★ 台账 #218：门槛**坏值 ⇒ 当场抛**（fail-closed），绝不用 `or 0` 静默吞成 0
    #   病根（`meets` 原先那两行）：
    #       `int(tier.get("need_done") or 0) >= int(tier.get("need_chief") or 0)`
    #   `or 0` 把**缺键 / `""`** 全吞成 0 ⇒ 门槛静默变 0 ⇒ **没交委托的玩家能直接升到银档**
    #   （真源 `05_玩法数值口径 §一`：铜 = 交 5 条 · 银 = 交 15 条 + 打掉 1 头目）。
    #   `rules()` 只校验「键存在」不校验「值是 ≥0 的整数」⇒ 值坏了只有消费端判得出。
    #   判据三条：① 坏门槛五种形态都抛并点名（缺键/""/字符串/负数/bool）
    #            ② 静态守卫：`meets` 里**一个 `or` 都不许有**在门槛那一侧
    #            ③ 真表逐档两态照旧（合法 `0` 门槛是合法的，不当缺键）
    sys.path.insert(0, REPO)
    try:
        from content import ranks as _RK                     # noqa: E402
    except Exception as _e:
        _RK = None
        bad("⑨ content.ranks 导不进来：%s" % _e)
    if _RK is not None:
        # 每种坏形态配一个**必须在点名里出现**的串（值本身，不是标签 —— 标签谁都行）
        _badtiers = ((('need_done',), {"id": "t", "need_done": "", "need_chief": 0}, "''"),
                     (('need_done',), {"id": "t", "need_chief": 0}, "缺键 ⇒ None"),
                     (('need_chief',), {"id": "t", "need_done": 3}, "缺键 ⇒ None"),
                     (('need_done',), {"id": "t", "need_done": "15", "need_chief": 0}, "'15'"),
                     (('need_done',), {"id": "t", "need_done": -1, "need_chief": 0}, "-1"),
                     (('need_done',), {"id": "t", "need_done": True, "need_chief": 0}, "True"))
        _silent, _raised = [], []
        for _keys, _t, _why in _badtiers:
            try:
                _res = _RK.meets({"done": 0, "chief": 0}, _t)
                _silent.append("%s ⇒ %r（没抛）" % (_why, _res))
            except Exception as _e2:
                _msg = "%s %s" % (str(_e2), repr(_e2))
                _hit = all(str(k) in _msg for k in _keys)
                if _hit:
                    _raised.append(_why)
                else:
                    _silent.append("%s 抛了但没点名是哪一格（%s）" % (_why, _e2))
        if not _silent:
            ok("⑨ 门槛坏值六形态（`\"\"` / need_done 缺键 / need_chief 缺键 / 字符串 / 负数 / bool）"
               "⇒ 全部当场抛并点名是哪一格：%s" % "、".join(_raised))
        else:
            bad("⑨ 门槛坏值没全抛并点名：%s" % _silent)
        # 真表两态照旧（合法的 0 门槛是合法门槛，不是缺键）
        _mism = []
        for _t in _RK.ladder():
            _want0 = (int(_t["need_done"]) == 0 and int(_t["need_chief"]) == 0)
            if _RK.meets({"done": 999, "chief": 999}, _t) is not True:
                _mism.append("%s · 999/999 没过" % _t["id"])
            if _RK.meets({"done": 0, "chief": 0}, _t) is not _want0:
                _mism.append("%s · 0/0 ⇒ %r（门槛 %s/%s）"
                             % (_t["id"], _RK.meets({"done": 0, "chief": 0}, _t),
                                _t["need_done"], _t["need_chief"]))
        if not _mism:
            ok("⑨ 真表逐档两态照旧（0/0 那档门槛合法为 0 ⇒ 够；其余不够）")
        else:
            bad("⑨ 真表两态翻了：%s" % _mism)
        # 静态守卫：门槛那一侧**不许**再出现 `X.get("need_done"|"need_chief") or …` ——
        #   那个 `or` 就是「缺键 / `""` 被吞成 0」的病根。`stats` 那侧的 `or 0` 是**合法**的
        #   （没交委托就是 0 条 —— 玩家自己的账，正是「你还差 5 条」那一句）⇒ 只按键名钉。
        _rtree = ast.parse(io.open(os.path.join(REPO, "content", "ranks.py"), encoding="utf-8").read())
        _or218 = []
        for _x in ast.walk(_rtree):
            if not (isinstance(_x, ast.BoolOp) and isinstance(_x.op, ast.Or)):
                continue
            for _v in _x.values:
                if (isinstance(_v, ast.Call) and isinstance(_v.func, ast.Attribute)
                        and _v.func.attr == "get" and _v.args
                        and isinstance(_v.args[0], ast.Constant)
                        and _v.args[0].value in ("need_done", "need_chief")):
                    _or218.append(ast.dump(_x)[:80])
        if not _or218:
            ok("⑨ 静态守卫：全仓**没有** `X.get(\"need_done\"/\"need_chief\") or …` 那种吞门槛的写法"
               "（`stats` 那侧的 `or 0` 是合法的，不算）")
        else:
            bad("⑨ 门槛一侧又有 `or` 兜底 ⇒ 门槛会静默变 0：%s" % _or218)

    # ── ⑧ 覆盖面：两条 handler 都真调 ranks 模块
    decl = _load("content/data/commands.json")
    want_fn = {}
    for key in ("rank", "rank_up"):
        mod, fname = str(decl[key]["bind"]["handler"]).split(":")
        want_fn.setdefault(mod.split(".")[-1] + ".py", set()).add(fname)
    used = {}
    for fn in sorted(os.listdir(os.path.join(REPO, "content"))):
        if not fn.endswith(".py"):
            continue
        tree = ast.parse(io.open(os.path.join(REPO, "content", fn), encoding="utf-8").read())
        for n in ast.walk(tree):
            if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for x in ast.walk(n):
                if (isinstance(x, ast.Name) and x.id == "RK") \
                        or (isinstance(x, ast.Attribute) and getattr(x.value, "id", "") == "RK") \
                        or (isinstance(x, ast.Attribute) and getattr(x.value, "id", "") == "ranks"):
                    used.setdefault(fn, set()).add(n.name)
    miss = [k for k, fns in want_fn.items() for f in fns if f not in used.get(k, set())]
    if not miss:
        ok("覆盖面：`评级` / `换证` 两条 handler 都真调 `content/ranks.py`（档名与门槛一个口）")
    else:
        bad("这两条没走 ranks 那个口：%s" % miss)

    try:
        os.remove(db)
    except OSError:
        pass

    print()
    print("----")
    print("通过 %d / 失败 %d" % (len(OK), len(BAD)))
    if BAD:
        print("红：")
        for b in BAD:
            print("  -", b)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
