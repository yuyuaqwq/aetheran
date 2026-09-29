# -*- coding: utf-8 -*-
"""《阿斯特兰》指令实现体 · 第五组：野外采集（B2-4）

采集 / 挖掘 / 垂钓 / 搜查 / 歇脚 / 拾取 —— 六个动词，同一套「找到点什么」的形状。

★ 出产是「种子驱动 · 可复现」的（P-26）：
    种子 = uid + `calendar.day_key(游戏日)`（时辰/天气那套的现成口）+ 点 id + 当日第几次
    ⇒ 同人 · 同日 · 同点 · 同一次 = 逐字节相同（不刷）；换人 / 跨日 / 换点 / 换次数 = 会变。
    随机源一律 `random.Random(种子)` —— 不许 `random.random()` 那种不可复现的口。
★ 反复采同一个点（P-26 的第二层口径 · 三句说清）：
    ① 当日第 N 次先从池里**去掉最稀罕的 N-1 条**（权重最低 = 最少见；「稀罕的先让人捡走了」，
       并列按池中原始顺序）⇒ 第 1 遍全池、第 2 遍只剩大路货（「零星」，一次最多给 1 个）
    ② 当日的**最后一遍**（第 `times_per_day` 遍，且这个点一天不止一遍）= 空手 —— 那儿翻空了
       （槽位 SYS_GATHER_BARE）
    ③ 一天只给一遍的点（挖掘那类）不走 ②：唯一一遍照常全池抽
★ 按档去重（fxm5-gather-unique）：池里**某一条目**写了 `unique: true` ⇒ **手上已有那一件
    就不再进池**（真源 `22_旧哨塔_逐间设计_v1` §二·10「拿半截号角（信物 `i_horn_half`）」·
    §二·12 塔顶「掉落 半截号角（**如果 10 房没拿**）」—— 同一件剧情信物**每档最多一件**，
    号角室那张石台（`gt_tw_search_4`）就是「10 房拿」那一侧）。**声明粒度 = 条目**：
    只排写了这一格的那些条目，同一点里的材料 / 药品即便手上已有照出不误；别的点一条都
    没写 ⇒ 一个字节不动。「手上有哪些件」走 `loot.held_ids` 那**唯一一口**（与掉落池那条
    路同一份账）。判据 `probe_gather ⑫`。
★ 抽取仍是 `loot.roll_pool` 那套权重（Σw + uniform(0,tot) + 累加命中）—— 这里只是把 `rnd`
  换成上面那个确定性 Random；机器键（`kind_key`）/ 名字 / 进包一律走 loot 那几口。
"""
from __future__ import annotations

import random

import io
import json
import os

from .cmds_ast import (_data, _p, _save, _map_of, _name_of_node, T, hp_cap_or_line,
                        _pois_here, rest_places, _in_fight)
from .cmds_codex import new_lines
from . import calendar as CAL
from . import codex as CX
from . import loot as LT


def _points_here(p, verb=None):
    out = []
    for gid, v in _data("gathering").items():
        if v.get("map") == p["loc"] and v.get("subarea") == p["node"]:
            if verb is None or v.get("verb") == verb:
                out.append((gid, v))
    return out


def _used(p, gid):
    return int(((p.get("flags") or {}).get("gather_used") or {}).get(gid, 0) or 0)


def _times_of(pt):
    """这个采集点**一天能翻几遍** —— 采集判定与「出处」提示的**唯一取件口**（审计 L2009-3）。

    口径：缺 `times_per_day` ⇒ 3；给了就照给的走；`0` 是策划明说的「今天一次都不给翻」
    （合法值，**不**被抬成 1/3）。回落**只认 `None`** —— `or 3` 会把合法 `0` 吞掉，
    玩家会看到「一天 0 回」而采集那边照旧能翻。
    """
    raw = pt.get("times_per_day") if isinstance(pt, dict) else None
    if raw is None:
        return 3
    n = int(raw)
    if n < 1:
        raise ValueError(f"采集点 {pt.get('id') or pt.get('name')!r} 的 times_per_day={n}"
                         f" 不合法（须 ≥ 1）")
    return n


def _bump_used(p, gid):
    f = dict(p.get("flags") or {})
    u = dict(f.get("gather_used") or {})
    u[gid] = int(u.get(gid, 0)) + 1
    f["gather_used"] = u
    p["flags"] = f


#: ★ 采集抽签的种子命名空间（与 `calendar.weather_of` 的 `aetheran:weather:` 同风格）
_SEED_NS = "aetheran:gather"

#: 采集口径那一侧的唯一真源（今天只有 `first_dig` 一条）
_RULES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules", "gather.json")


def _gather_rules() -> dict:
    """采集口径（`rules/gather.json`）—— 读不到 ⇒ `{}`（消费端那一格就当成没配 = 不补）。"""
    try:
        return json.load(io.open(_RULES, encoding="utf-8")) or {}
    except Exception:
        return {}


def _first_dig_fill(p, verb: str, got: list) -> list:
    """每天**第一次「挖掘」**的保底（口径在 `rules/gather.json::first_dig` · 见那儿的 `_src`）。

    为什么有它：三点一天各一铲，按域里权重现算日产 1.60 件、且「三点全空」占 32% ——
    试玩三家实测「三处挖光、0 件铁屑」⇒ 当天强化做不了（铁屑只有挖掘这一条源）。
    只补「这一铲没出铁屑」那一种情况 ⇒ **任何一铲的产出只增不减**，单点权重一格不动。
    档上只记「保底用在哪一天」（一个整数，不依赖 `flags` 的跨日清理）。

    ★ 台账 #198：原先「今天第几天」读的是档上那格 `p["day"]`（`today = int(p.get("day") or 0)`）——
      可它只是 `calendar.tick()` 留下的**跨日标记**，全仓只有几个入口在刷（`calendar.py:282`
      明写「别读 `p["day"]`」）。坏形态有两样，都会让**玩家白刷材料**：
        ① `p["day"]` 还是 0（这档还没 tick 过 / 别的入口没刷到）⇒ 下面那道
           `today != 0` 的自保把它当成「还没补过」⇒ **同一天连挖三铲各白拿 1 件铁屑**；
        ② 那是上一回 tick 那天的旧值 ⇒ 跨日之后额度算在昨天头上。
      处置：**日期戳一律走 `calendar.day_now()`**（与 `eggs.py:127` / `codex.today()` 同一把尺 ——
      现算，宿主注入的那根钟），档上那格 `p["day"]` 一个字都不读。判据 `probe_gather ⑬`。
    """
    r = _gather_rules().get("first_dig") or {}
    if str(r.get("verb") or "") != str(verb) or not r.get("out"):
        return []
    if any(str(d.get("id")) == str(r.get("out")) for d in got):
        return []                                   # 这一铲自己就出了 ⇒ 不补（不叠加）
    today = CAL.day_now()                          # ★ B4-9 / 台账 #198：现算，不读 p["day"]
    day_raw = (p.get("flags") or {}).get("gather_first_dig_day")
    # ★ 认**键在不在**，不拿 0 当「没补过」（`or 0` 那一下正是白刷的另一半：
    #   真游戏日 0 时补过一次之后，同日第二铲会因 `0 == 0` 但 `today == 0` 而放行）。
    if day_raw is not None and int(day_raw) == today:
        return []                                   # 今天已经补过
    f = dict(p.get("flags") or {})
    f["gather_first_dig_day"] = today
    p["flags"] = f
    oid = str(r.get("out"))
    return [{"id": oid, "n": int(r.get("n") or 1), "kind_key": LT.kind_key_of(oid, None)}]


def _seed(uid, day: int, gid: str, nth: int) -> str:
    """★ 采集抽签的种子 —— **唯一**来源：人 · 游戏日 · 点 · 当日第几次（P-26）。

    · 游戏日走 `calendar.day_key()`（时辰/天气那条线的现成口）—— 别自己拼时间
    · 同人同日同点同一次 ⇒ 逐字节相同（不刷）；换人 / 跨日 / 换点 / 换次数 ⇒ 变
    """
    return "%s:v2:%s:%s:%s:%d" % (_SEED_NS, str(uid), CAL.day_key(day), str(gid), int(nth))


def _left_after(entries: list, nth: int) -> list:
    """当日第 `nth` 次（1-based）还剩哪些条目 —— 「稀罕的先让人捡走了」。

    去掉**权重最低**的 `nth - 1` 条（权重 = 有多常见 ⇒ 最低 = 最稀罕的那几条；
    权重升序，并列按池中原始顺序 —— 稳定 ⇒ 可复现）。
    ⇒ 第 1 遍全池、第 2 遍只剩大路货（「零星」）；全被捡走 = 空列表。
    """
    if nth <= 1:
        return list(entries)
    order = sorted(range(len(entries)), key=lambda i: (int(entries[i].get("w", 1) or 1), i))
    gone = set(order[:nth - 1])
    return [e for i, e in enumerate(entries) if i not in gone]


async def _do_gather(env, sink, uid, player, verb: str, word: str):
    p = _p(player)
    # ★ fix-q（试玩 · 与 `歇脚` 那条同一条闸）：「采集 / 挖掘 / 垂钓 / 搜查」原先只判「脚下有没有
    #   这个动词的点」，**战斗中照样放行** —— 实测（真宿主 · 骨田）：一场里敲 `挖掘` 照出
    #   「铁屑 ×1 + 碎石 ×1」、`采集`/`搜查` 照进背包与旧物谱，档当场被改（`bag` / `flags.gather_used`
    #   / `codex`），而这一手**不花**（场上那一手是另一条路）⇒ 等于给玩家一个战斗中的免费口。
    #   处置 = 与出镇 / 带间 / 返回 / 去 / 塔门 / 歇脚同一道**持态闸**（`SYS_MOVE_IN_FIGHT`，
    #   fail-closed）：先把这一场打完，或者『逃跑』/『后撤』脱身。
    #   ★ `拾取` 不在这一闸里：那一支一个字都不写（`SYS_PICKUP_NONE`），拦它只会换一句话。
    #   ★ 判据只紧：不打架时那四点照旧真出东西（`probe_cmds` ㉑③c 两态互锁）。
    _lock = _in_fight(env, uid)
    if _lock:
        yield _lock
        return
    pts = _points_here(p, verb)
    if not pts:
        yield T("SYS_GATHER_NONE", word=word)
        return
    gid, pt = pts[0]
    st = CAL.tick(p)                       # ★ 时辰/天气现算；跨（游戏）日把采集次数归零
    if not CAL.allows(pt.get("time"), st):          # 整点门槛：夜明砂那类
        if player is not None:
            player.update(p)
        _save(env)
        yield T("SYS_TIME_GATED", what=pt["name"], when=pt["time"])
        return
    times = _times_of(pt)                              # 这个点一天能翻几遍（唯一取件口）
    if _used(p, gid) >= times:
        yield T("SYS_GATHER_USED_TODAY", name=pt["name"])
        return
    nth = _used(p, gid) + 1                          # 当日第几次（1-based）—— 进种子
    rnd = random.Random(_seed(uid, st["game_day"], gid, nth))
    # 采集点自己就是一张池（形状与 dp_* 一致）
    got = []
    pool = pt.get("pool") or []
    # ★ 条目级门槛 `when`（「稀有鱼只在夜里」这种按条算的）
    entries = [e for e in pool if CAL.allows(e.get("when"), st)]
    if not entries:
        if player is not None:
            player.update(p)
        _save(env)
        yield T("SYS_TIME_GATED", what=pt["name"],
                when=" · ".join(sorted({str(e.get("when")) for e in pool if e.get("when")})))
        return
    # ★ fxm5-gather-unique：条目写了 `unique: true` ⇒ **按档去重**（手上已有那一件就不再进池）。
    #   真源 `22_旧哨塔_逐间设计_v1` §二·10「拿半截号角（信物）」+ §二·12「掉落 半截号角
    #   （**如果 10 房没拿**）」—— 同一件剧情信物**每档最多一件**；这一支就是「10 房拿」
    #   那一侧，而它原先是**每档一天最多再出 1~2 件**（池里 `w=100`）——与 Boss 那条路
    #   （`loot.roll_pool` 的 `unique` · fxm2-horn）本来是同一条口径，这里跟账。
    #   · ★ 声明在**条目**上（不是整点）：只排**写了这一格的那些条目** —— 同一点里的材料 /
    #     药品即便手上已有照出不误（`27_掉落的惊喜感与未鉴定 §四`：重复掉落本身不消灭）；
    #   · 别的点（今天 21 个）一条条目都没写 ⇒ 一个字节不动；
    #   · 「手上有哪几件」走 `loot.held_ids`（**唯一一口**，与掉落池那条路同一份账）；
    #   · 排的是**条目**（静态 id）⇒ 池里剩下那些条目的权重与**相对**几率一字不动；
    #   · `left`（越翻越少）**先算再排** —— 「稀罕的先让人捡走了」是这一站当天的事，与背包无关。
    keep = LT.held_ids(p) if any(e.get("unique") for e in entries) else set()
    # ★ 反复采：越翻越少（去掉最稀罕的几条）；当日的**最后一遍**那儿已经翻空了 = 空手。
    #   一天只给一遍的点（挖掘那类）不适用 —— 唯一一遍照常全池抽。
    left = [] if (times > 1 and nth >= times) else _left_after(entries, nth)
    if keep:
        left = [e for e in left if not (e.get("unique") and str(e.get("out")) in keep)]
    if left:
        tot = sum(int(e.get("w", 1) or 1) for e in left)
        r = rnd.uniform(0, tot or 1)
        acc = 0.0
        for e in left:
            acc += int(e.get("w", 1) or 1)
            if r <= acc:
                oid = e["out"]
                n = 1
                rng = e.get("n")
                if isinstance(rng, list) and len(rng) == 2:
                    n = rnd.randint(int(rng[0]), int(rng[1]))
                if nth > 1:
                    n = min(n, 1)        # ★ 翻过一遍了 ⇒ 只给零星（第 2 遍起一次最多 1 个）
                # 机器键归一（未鉴定那类走池自己的 marker）—— 唯一的一口在 loot.kind_key_of
                got.append({"id": oid, "n": n, "kind_key": LT.kind_key_of(oid, e.get("kind_key"))})
                break
    # ★ Q-22：每天第一次「挖掘」的保底（口径在 `rules/gather.json::first_dig`）——
    #   只补「这一铲没出铁屑」，任何一铲的产出只增不减。
    got.extend(_first_dig_fill(p, verb, got))
    _bump_used(p, gid)
    if got:
        LT.add_to_bag(p, got)
    new = CX.note_items(p, [d["id"] for d in got]) if got else []
    CX.note_gather(p)
    p["hp"] = p.get("hp", 1)
    if player is not None:
        player.update(p)
    _save(env)
    yield "【%s】%s" % (pt["name"], pt.get("desc") or "")
    if pt.get("time"):
        yield T("SYS_TIME_ONLY", when=pt["time"])
    if nth > 1 and left:
        yield T("SYS_GATHER_AGAIN")
    if not got:
        yield T("SYS_GATHER_BARE", name=pt["name"])
    for d in got:
        rec = LT.rec_of(d["id"])
        yield T("SYS_GATHER_GET", icon=rec.get("icon", "·"), name=rec.get("name", d["id"]),
                n=d.get("n", 1))
        if rec.get("hint"):
            yield "  （%s）" % rec["hint"]
    for line in new_lines(new):
        yield line


async def gather(env, sink, uid, player):
    async for line in _do_gather(env, sink, uid, player, "herb", T("SYS_GATHER_VERB_HERB")):
        yield line


async def dig(env, sink, uid, player):
    async for line in _do_gather(env, sink, uid, player, "dig", T("SYS_GATHER_VERB_DIG")):
        yield line


async def fish(env, sink, uid, player):
    async for line in _do_gather(env, sink, uid, player, "fish", T("SYS_GATHER_VERB_FISH")):
        yield line


async def search(env, sink, uid, player):
    async for line in _do_gather(env, sink, uid, player, "search", T("SYS_GATHER_VERB_SEARCH")):
        yield line


#: ★ B4-25：`歇脚` 的守卫「有篝火」原先**没有执行面** —— 声明自己的 `guard_desc`（有篝火）、
#:   `06_第一阶段垂直切片/04_指令总表 §六` 那一行、以及 `pois` 域给三处营地挂的 `effect.rest`
#:   三处都写着这一条，可这一支原先**在哪儿都能歇**（镇上、骨田、塔里一律回血）⇒ 篝火形同虚设。
#:   ★ 判法只此一处：脚下这一站有没有 `effect.rest` 的 poi。名单**不手写** —— 列 poi 走
#:     `_pois_here` **唯一那一口**（K65 / P-31 那一族：谁再自己扫一遍 `pois` 域，就会漏掉门槛判定）。
def _fire_here(p):
    """脚下这一站的火（`effect.rest`）—— 空列表 = 这儿没有篝火。"""
    return [rec for _pid, rec, state, _ln in _pois_here(p["loc"], p["node"], p)
            if (rec.get("effect") or {}).get("rest") and state != "no"]


async def rest(env, sink, uid, player):
    p = _p(player)
    # ★ fix-p-restfight（试玩 ⛔ · assassin b110/b115/b118/b119）：「歇脚」原先只判「脚下有没有
    #   篝火」，**战斗中照样放行** —— 而这一支的回血落点是**玩家档那一份** `p["hp"]`
    #   （`player.update(p)`），这一场的血却在「场」里 ⇒ **一人两套血**：屏上被报到 120/120，
    #   下一手实战仍从旧血接着算（实测 82 − 23），b115 就是靠它把屏上血量报满之后当场被打死。
    #   处置 = 与出镇 / 带间 / 返回 / 去 / 塔门同一道**持态闸**（`SYS_MOVE_IN_FIGHT`，fail-closed）：
    #   先把这一场打完，或者『逃跑』/『后撤』脱身 —— 那一手在场上才花得掉。
    #   ★ 判据只紧：不打架时那一站照旧真回血（`probe_cmds` ㉑② 两态互锁）。
    _lock = _in_fight(env, uid)
    if _lock:
        yield _lock
        return
    # ★ B4-25：**先看脚下有没有火** —— 这是声明里写着的守卫（`guard_desc` = 有篝火），
    #   不是装饰：没有火就照实说，档一个字都不动（不扣血、不推进天数、不落库）。
    #   ★ F6（QA P4 E-3）：光说「这儿没有篝火」不够 —— 「歇脚棚」这个名字天然让玩家以为能歇，
    #     回话得**指出哪儿有火**（名单从 pois 域现读，不手写镜像）。
    if not _fire_here(p):
        yield T("SYS_REST_NOFIRE")
        fires = rest_places()             # ★ 名单从 pois 域现读（读口在 `cmds_ast`，本模块不扫）
        if fires:
            yield T("SYS_REST_FIRE_HINT", list=" · ".join("『%s』" % x for x in fires))
        return
    # ★ P-27：上限只有一个来源 = 职业面板。档上还没有职业（建号第二步没走完）⇒ **不出假数**：
    #   出一行点名的 fail-closed 行，歇脚这一支整段不做。
    mx, _line = hp_cap_or_line(p)
    if _line:
        yield _line
        return
    hp = int(p.get("hp") or mx)
    if hp >= mx:
        yield T("SYS_REST_FULL")
        return
    heal = max(1, int(mx * 0.2))
    p["hp"] = min(mx, hp + heal)
    if player is not None:
        player.update(p)
    _save(env)
    yield T("SYS_REST_DONE")
    yield T("SYS_REST_HEAL", add=heal, hp=p["hp"], max=mx)


async def pick_up(env, sink, uid, player):
    yield T("SYS_PICKUP_NONE")
