# -*- coding: utf-8 -*-
r"""探针：指令路由（第 23 个）—— B3-14：触发词撞车 · **P-23：只列有处理器的指令**。

为什么有这条线（端到端玩出来的真 bug）
------------------------------------
`content/data/commands.json` 的 patterns 一律**行首锚定 + `\s*`**（触发词与参数之间不要求空白），
中文词之间又没有空白 ⇒ 短触发词会把**长词的首字**当成自己的参数吃掉：玩家敲文档
（`06_第一阶段垂直切片/04_指令总表.md`）上写着的那个词，命中的却是**另一条**指令。改前实测：

| 玩家敲的（文档上有） | 改前命中 | 应当命中 |
|---|---|---|
| `装备对比 <装备>`（04 §四 的别名） | equip（`装备` + `对比…`） | item_compare |
| `脱离`（04 §五 的别名） | unequip（`脱` + `离`） | flee |
| `买药`（04 §七 的触发词） | item_buy（`买` + `药`） | herbalist |
| `放弃`（不带编号） | skill_cast（`放` + `弃`）⇒ 回「放技能」 | 谁都不该命中（带编号才有效） |

修法（只动数据、不动引擎）：给「更长的触发词」那三条加 `priority`（引擎 B19d 起的排序语义 ——
priority 降序、同值按注册序，见引擎 `tests/test_host_priority_route.py`），并把 `放` 这个
**单字别名**收成必须带空白（`^放\s+…`）。下面四条判据把它钉住。

判据
----
  ① 每条可见声明的**每一个 pattern** 反推一个样例串，必须命中它**自己**
     （样例由 `re` 的语法树展开而来 ⇒ 样例跟着声明走，不手写镜像表）
  ② `04_指令总表` 点名的触发词 / 别名逐条 first_hit 到期望的那条（别名不许是死的）
  ③ 同名同形的**不可见**声明（`battle_item` 的「使用」）不参与路由 —— 路由只在可见声明里排
  ④ ★ 端到端（真宿主契约）：真敲那四条 —— 回话来自期望的声明；且裸「放弃」**不许动档**
     （`quest_abandon` 空参取 `act[0]` ⇒ 会静默丢掉第一条委托）
  ⑤ ★ P-23（真敲）：**「帮助」列的就是「可见 + 有处理器」那些** —— 逐条对账（多一条 = 玩家
     照着敲会撞空，少一条 = 能用的没告诉玩家）；43 条「声明了没处理器」一条都不许在表里
  ⑥ ★ P-23（真敲 43 条）：这些声明**回的是人话**（槽位 `SYS_CMD_SOON`）—— 不许再把
     **内部 key** 与「包内 content/commands.py 里没有它的 handler」漏给玩家
  ⑦ ★ P-23（真敲）：「读」这条**有处理器却没声明**的接上了 —— 抬头与正文都对；同一处两个
    可读物时按名字挑（点错名照「这儿没有能读的东西」说，**不随便塞一样**给玩家）
  ⑧ ★ B3-6（真敲）：副本那 5 条（进塔 / 下一层 / 副本地图 / 调查 / 撤退）都接上了 ——
     塔里 / 塔外两档回的都是真话，不是「还没接上」那一句（槽位 `SYS_CMD_SOON`）
  ⑨ ★ B3-9（真敲）：装备 / 卸下 / 装备对比 / 学习 / 技能 五条接上了 —— 回的都是填了槽位的真话
     （顺序：装备 → 状态 跟着面板走 → 对比（含别名）→ 卸下 → 穿脱回原样 → 学习 → 技能）；
     且「声明了、可见、还没实现」那一条**只许降**（B3-6 收口 45 → B3-9 收 33 → B3-12 收 25 →
     **本批 B3-16b 收 16**，`UNBOUND_MAX` 钉着）
  ⑩ ★ B3-9（直调）：学习 / 技能 的语义 —— 六职业 1 级解锁那一班 · 四道门（没有这条 / 不是本职业 /
     解锁等级没到 / 已经会了）· 落档后**档上那班 = 战斗真放的那班** · 用档上那班真打一场出伤害
  ⑪ ★ B3-9（直调）：`装备对比` 逐字对账 —— 期望值由 `gear.gear_stats`（唯一取值口）+ texts 现算，
     不手写镜像串；三档（有增有减 / 位子空着 / 全一样）各比一遍整段输出
  ⑫ ★ B3-12（真敲）：这一批新接的 8 条 —— 看 <编号> / 属性 / 查看 / 丢弃 / 卖出 / 整理背包 /
     存放·取出 / 成就。每一条**真宿主真敲**、整段与「域 + texts 现算的期望」逐字对账，
     档上副作用逐条核（bag / gold / flags.stash 的增减与摘条目），并扫「没有域 id / 没有
     取不到文案 / 不再回「还没接上」那一句」；其中「整理背包」钉**键序真重排 + 一件没少**、
     「存放·取出」钉**方向取自声明（单字别名同向）**、「属性」钉**生命上限 = `hp_cap` 那一个来源**
  ⑬ ★ B3-16b（真敲）：这一批新接的 9 条 —— 教堂 / 客栈 / 商队 / 旧货 / 登记 / 评级 / 改名 /
     排行 / 公告。同样**真宿主真敲**、逐字对槽位：镇上那几处按「野外 / 镇上没走到那一站 /
     站到了」分档（治疗与住店都钉**血真回到上限**，上限走 `hp_cap` 那唯一来源）· 商队两档
     （车在路上 / 车到了）钉「动静取自 `events` 域 + 外人在哪一站现算」· 旧货逐件与
     `items.price` 现算对账 · 登记 / 改名 / 评级钉**档上副作用**（`flags.card` 只在那一下写、
     `name` + `flags.renamed` 落档、只许改一次）· 排行钉「榜 = 本群存档（`all_players`）+
     自己那一行一定在」· 公告钉「包名/版本取自 `game.json`、已接条数现点声明表」；
     并扫「没有域 id / 没有取不到文案 / 不再回「还没接上」那一句」

跑法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_cmds.py
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, ENGINE)

try:                                                       # 3.12：re 的语法树子模块
    import re._parser as _parse
except ImportError:                                        # pragma: no cover
    import sre_parse as _parse                             # type: ignore

from saintess_engine.command import CommandRegistry         # noqa: E402
from saintess_engine.package import load_stack              # noqa: E402

ok = True


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


# ── 样例展开：pattern → 一个能命中它的串（每个交替分支各一条）──────
def _pieces(op, av, limit):
    n = str(op)
    if n == "LITERAL":
        return [chr(av)]
    if n == "NOT_LITERAL":
        return ["x"]
    if n == "IN":
        for sub_op, sub_av in av:
            if str(sub_op) == "CATEGORY":
                got = _pieces(sub_op, sub_av, limit)
                if got:
                    return got
            if str(sub_op) == "LITERAL":
                return [chr(sub_av)]
            if str(sub_op) == "RANGE":
                return [chr(sub_av[0])]
        return ["a"]
    if n == "ANY":
        return ["x"]
    if n == "AT":
        return [""]
    if n == "CATEGORY":
        name = str(av)
        if "SPACE" in name:
            return [" "]
        if "DIGIT" in name:
            return ["7"]
        return ["a"]
    if n in ("MAX_REPEAT", "MIN_REPEAT"):
        lo, _hi, body = av
        return [""] if not lo else _expand(body, limit)
    if n == "BRANCH":
        _kind, branches = av
        got = []
        for br in branches:
            got.extend(_expand(br, limit))
        return got[:limit]
    if n == "SUBPATTERN":
        return _expand(av[-1], limit)
    return [""]


def _expand(node, limit=24):
    out = [""]
    for op, av in node:
        nxt = []
        for pre in out:
            for piece in _pieces(op, av, limit):
                nxt.append(pre + piece)
        out = nxt[:limit]
    return out


def samples(pattern):
    return _expand(_parse.parse(pattern))


# ── 文档点名的触发词（`04_指令总表` 各节；别名一律算）──────────────
DOC = (
    ("§一 移动与世界", (
        ("进镇", "enter_town"), ("风车镇", "enter_town"), ("回镇", "enter_town"),
        ("北口", "go_north"), ("往北", "go_north"), ("出北门", "go_north"),
        ("往东", "go_east"), ("东边", "go_east"),
        ("往西", "go_west"), ("西边", "go_west"),
        ("返回", "go_back"), ("回", "go_back"), ("退回去", "go_back"),
        ("地图", "map"), ("m", "map"),
        ("观察", "look"), ("看", "look"), ("看四周", "look"),
        ("触摸", "touch"), ("摸", "touch"), ("碰", "touch"),
        ("聆听", "listen"), ("听", "listen"),
        ("问路", "ask_way"), ("打听", "ask_way"),
        ("时间", "time"), ("天", "time"), ("时辰", "time"),
    )),
    ("§二 公会与委托", (
        ("公会", "guild"), ("柜台", "guild"),
        ("登记", "register"), ("办证", "register"),
        ("悬赏", "board"), ("看板", "board"), ("委托", "board"),
        ("看 1", "board_show"),
        ("接 1", "quest_accept"), ("接取 1", "quest_accept"),
        ("交 1", "quest_deliver"), ("交活 1", "quest_deliver"),
        ("放弃 1", "quest_abandon"),
        ("我的委托", "quest_mine"), ("任务", "quest_mine"),
        ("评级", "rank"), ("我的等级", "rank"),
        ("升级证", "rank_up"), ("换证", "rank_up"),
    )),
    ("§三 角色", (
        ("状态", "status"), ("面板", "status"),
        ("属性", "attrs"),
        ("技能", "skills"), ("技能表", "skills"),
        ("学习 挥击", "skill_learn"), ("学 挥击", "skill_learn"),
        ("装备 拾荒人的重剑", "equip"), ("装 拾荒人的重剑", "equip"), ("穿 拾荒人的重剑", "equip"),
        ("卸下 拾荒人的重剑", "unequip"), ("卸 拾荒人的重剑", "unequip"),
        ("脱 拾荒人的重剑", "unequip"),
        ("称号", "titles"), ("头衔", "titles"),
        ("改名", "rename"), ("名字", "rename"),
    )),
    ("§四 背包与物品", (
        ("背包", "bag"), ("包", "bag"), ("包裹", "bag"), ("inv", "bag"),
        ("查看 伤药", "item_show"),
        ("使用 伤药", "item_use"), ("用 伤药", "item_use"), ("吃 伤药", "item_use"),
        ("丢弃 伤药", "item_drop"), ("丢 伤药", "item_drop"),
        ("卖出 伤药", "item_sell"), ("卖 伤药", "item_sell"),
        ("购买 伤药", "item_buy"), ("买 伤药", "item_buy"),
        ("存放 伤药", "stash"), ("取出 伤药", "stash"),
        ("存 伤药", "stash"), ("取 伤药", "stash"),
        ("整理背包", "bag_sort"), ("整理", "bag_sort"),
        ("对比 伤药", "item_compare"), ("装备对比 伤药", "item_compare"),
        ("钱袋", "money"), ("钱", "money"), ("金", "money"),
    )),
    ("§五 战斗", (
        ("攻击", "attack"), ("打", "attack"), ("a", "attack"),
        ("打断", "interrupt"), ("断", "interrupt"),
        ("防御", "defend"), ("防", "defend"), ("守", "defend"),
        ("后撤", "retreat"), ("退", "retreat"),
        ("技能 挥击", "skill_cast"), ("技 挥击", "skill_cast"), ("放 挥击", "skill_cast"),
        ("逃跑", "flee"), ("逃", "flee"), ("脱离", "flee"),
        ("集火 田鼠", "focus_fire"),
        ("换武器", "swap_weapon"),
        ("自动", "auto_battle"),
        ("战斗日志", "battle_log"),
    )),
    ("§六 野外", (
        ("采集", "gather"), ("采", "gather"),
        ("挖掘", "dig"), ("挖", "dig"),
        ("垂钓", "fish"), ("钓", "fish"),
        ("搜查", "search"), ("搜", "search"),
        ("歇脚", "rest"), ("点篝火", "rest"), ("歇", "rest"),
        ("拾取", "pick_up"), ("捡", "pick_up"),
        ("攀爬", "climb"), ("爬", "climb"), ("翻", "climb"),
        ("潜行", "sneak"), ("绕开", "sneak"),
    )),
    ("§七 生产与铺子", (
        ("铁匠铺", "smith"), ("铁匠", "smith"),
        ("强化 拾荒人的重剑", "enhance"),
        ("药铺", "herbalist"), ("买药", "herbalist"),
        ("教堂", "chapel"),
        ("旧货", "junk_shop"), ("收旧货", "junk_shop"),
        ("客栈", "inn"), ("商队", "caravan"),
    )),
    ("§八 图鉴与记录", (
        ("图鉴", "codex"), ("谱", "codex"),
        ("材料谱", "codex_material"), ("风味谱", "codex_flavor"),
        ("怪物谱", "codex_monster"), ("旧物谱", "codex_relic"),
        ("记录", "footprint"), ("足迹", "footprint"),
    )),
    ("§九 副本 / 社交 / 系统", (
        ("进塔", "tower_enter"), ("进副本", "tower_enter"),
        ("下一层", "tower_next"), ("副本地图", "tower_map"),
        ("调查", "tower_investigate"), ("撤退", "tower_leave"), ("撤", "tower_leave"),
        ("队伍", "party"), ("组队", "party"), ("离队", "party_leave"),
        ("帮助", "help"), ("指令", "help"),
        ("提示", "hint"), ("去哪", "hint"),
        ("公告", "notice"), ("反馈", "feedback"), ("设置", "settings"),
        ("自动战斗偏好", "battle_pref"),
        ("排行", "ranking"), ("榜", "ranking"), ("成就", "achievements"),
        ("搭话", "talk"), ("搭话 玛莎", "talk"), ("说话 玛莎", "talk"), ("聊 玛莎", "talk"),
        ("去 北口", "go_to"), ("走到 北口", "go_to"), ("前往 北口", "go_to"),
        ("烹饪 烤石斑", "cook"), ("做 烤石斑", "cook"), ("煮 烤石斑", "cook"),
        ("配方", "recipes"), ("菜谱", "recipes"), ("配方一览", "recipes"),
        ("彩蛋", "eggs"), ("连起来", "eggs"),
    )),
)


print("探针：指令路由（第 23 个 · B3-14 触发词撞车 · P-23 只列有处理器的指令）")
st = load_stack(str(REPO), inject={
    "db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_cmds.db"),
    "clock": time.time})
st.install()
DECL = st.command_declarations()
REG = CommandRegistry(name="probe_cmds").load(DECL)
TX = st.domain("texts") or {}

print("① 每条可见声明的每个 pattern 反推样例串 ⇒ 必须命中它自己")
miss, total, vis = [], 0, 0
for key, v in DECL.items():
    if v.get("visible", True) is False:
        continue
    vis += 1
    for pat in v.get("patterns") or []:
        for text in samples(pat):
            total += 1
            got = getattr(REG.first_hit(text, visible_only=True), "key", None)
            if got != key:
                miss.append((key, pat, text, got))
chk("★ 无撞车（%d 条可见声明 · %d 个样例，命中自己 %d 个）" % (vis, total, total - len(miss)),
    not miss, "撞车：%s" % (miss[:6],))

print("② 文档点名的触发词逐条命中期望的那条")
bad, n = [], 0
for sect, rows in DOC:
    for text, key in rows:
        n += 1
        got = getattr(REG.first_hit(text, visible_only=True), "key", None)
        if got != key:
            bad.append((sect, text, key, got))
chk("★ %d 条触发词全部命中期望（照 04_指令总表 九节逐条 first_hit）" % n, not bad, "错：%s" % (bad[:6],))

print("③ 同名同形的不可见声明不参与路由")
chk("battle_item 与 item_use 的 patterns 逐字相同，而 battle_item 是 invisible",
    DECL.get("battle_item", {}).get("visible") is False
    and list(DECL.get("battle_item", {}).get("patterns") or []) == list(DECL.get("item_use", {}).get("patterns") or []))
chk("★ `使用 伤药` 命中可见的 item_use（invisible 的 battle_item 不抢）",
    getattr(REG.first_hit("使用 伤药", visible_only=True), "key", None) == "item_use")

print("④ 端到端（真宿主契约）：真敲那四条")


class _Ad(object):
    """三函数 + say（照 host-api 契约的最小适配器 —— 与 scripts/e2e_drive.py 同形）。"""

    def __init__(self, texts, seed=None):
        self._msgs = [{"uid": "u_c", "group_id": "g_c", "text": t, "is_group": True} for t in texts]
        self.out = []
        self.saved = seed

    def recv(self):
        return self._msgs.pop(0) if self._msgs else None

    def load_player(self, uid):
        return self.saved if uid == "u_c" else None

    def save_player(self, uid, data):
        self.saved = dict(data) if isinstance(data, dict) else data

    def say(self, to, text):
        self.out.append(str(text))


from saintess_engine.host.runtime import Host          # noqa: E402

_db = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_cmds_e2e.db")
try:
    os.remove(_db)
except OSError:
    pass

STEPS = ["装备对比 拾荒人的重剑", "脱离", "买药", "放弃", "技能 挥击"]
lines, saved = {}, {}
try:
    _ad = _Ad(STEPS, seed={"level": 1, "gold": 30, "hp": 100, "bag": {}, "equipped": {}, "codex": {},
                           "flags": {"quests_active": ["q_main_01"]}})
    _host = Host(_ad, str(REPO), inject={"db_path": _db, "clock": time.time})
    _host.boot()
    for _t in STEPS:
        _ad.out.clear()
        _host.handle({"uid": "u_c", "group_id": "g_c", "text": _t})
        lines[_t] = list(_ad.out)
    saved = _ad.saved or {}
    chk("★ 端到端跑得起来（真宿主契约）", True)
except Exception as exc:                                               # noqa: BLE001 —— 起不来就是红
    chk("★ 端到端跑得起来（真宿主契约）", False, "%s: %s" % (type(exc).__name__, exc))


def _first(t):
    return (lines.get(t) or [""])[0]


def soon_text(key):
    """「声明了、包内还没实现」现在回的那一句人话（槽位 `SYS_CMD_SOON` + 这条声明的 usage）。

    ★ P-23 前这里比的是引擎回显的开头 `【<key>】`（那是**把内部 key 漏给玩家**）；
      现在比**整句人话逐字**——比原来更严（key 也顺着 usage 对上了）。
    """
    return (TX.get("SYS_CMD_SOON") or {}).get("value", "").replace(
        "{name}", str((DECL.get(key) or {}).get("usage") or ""))


def hit_sample(key):
    """反推一个「敲下去必命中这条声明」的样例串（与判据 ① 同一支展开，不手写镜像表）。"""
    for pat in (DECL.get(key) or {}).get("patterns") or []:
        for text in samples(pat):
            if getattr(REG.first_hit(text, visible_only=True), "key", None) == key:
                return text
    return ""


chk("★ `装备对比 拾荒人的重剑` 归 item_compare（改前被 equip 吃掉）—— ★ B3-9 接上实现体之后"
    "这条改成更硬的写法：回的是实现体那句人话，**不再是 soon 兜底句**",
    _first("装备对比 拾荒人的重剑")
    == (TX.get("SYS_GEAR_IN_BAG") or {}).get("value", "").replace("{name}", "拾荒人的重剑")
    and _first("装备对比 拾荒人的重剑") != soon_text("item_compare"),
    _first("装备对比 拾荒人的重剑"))
chk("★ `脱离` 回的是 flee（改前回 unequip）",
    bool(_first("脱离")) and "【unequip】" not in _first("脱离"), _first("脱离"))
chk("★ `买药` 回的是 herbalist（改前回 item_buy）",
    _first("买药") == soon_text("herbalist"), _first("买药"))
chk("★ 裸 `放弃` 不许命中 skill_cast（改前回「放技能 ／ 技能 <参数>」）",
    bool(lines.get("放弃")) and not any(x.startswith("【skill_cast】") for x in (lines.get("放弃") or [])),
    lines.get("放弃"))
chk("★ 裸 `放弃` 不许动档（quest_abandon 空参会取 act[0]，静默丢第一条委托）",
    ((saved.get("flags") or {}).get("quests_active") or []) == ["q_main_01"],
    (saved.get("flags") or {}).get("quests_active"))
chk("★ `技能 挥击` 仍归 skill_cast（主词与双字别名没被改坏）",
    _first("技能 挥击") == soon_text("skill_cast"), _first("技能 挥击"))

#: 可见 + 有 bind（「帮助」应当正好列这些）
BOUND_USAGES = [v.get("usage") for k, v in DECL.items()
                if v.get("bind") and v.get("visible", True) is not False]
#: 可见 + 没 bind（P-23 要钉住的那一批）
UNBOUND = {k: v for k, v in DECL.items()
           if not v.get("bind") and v.get("visible", True) is not False}

#: ★ 「声明了、可见、包内还没实现」的条数**只许降**（与 probe_copy 的 BUDGET 同一套纪律）——
#:   B3-6 收口时 45，B3-9（装备与技能那组）接下 装备 / 卸下 / 对比 / 学习 / 技能 5 条 ⇒ **38 → 33**；
#:   ★ B3-12（那一批）再接下 8 条（看 <编号> / 属性 / 查看 / 丢弃 / 卖出 / 整理背包 / 存放取出 / 成就）
#:   ⇒ **33 → 25**；★ B3-15（P-34）接下 `alloc`（加点）⇒ **25 → 24**；
#:   ★ B3-16b（同一波）再接下 9 条（教堂 / 客栈 / 商队 / 旧货 / 登记 / 评级 / 改名 /
#:   排行 / 公告）⇒ **24 → 15**。再往上加就是回退（要么是新声明没实现、要么是有人把 bind 摘了）。
UNBOUND_MAX = 15

print("⑤ ★ P-23：「帮助」只列**有处理器**的声明（真敲 · 逐条对账）")
try:
    _ad.out.clear()
    _host.handle({"uid": "u_c", "group_id": "g_c", "text": "帮助"})
    _help = list(_ad.out)
    _listed = [w for ln in _help for w in re.findall(r"『([^』]*)』", ln)]
    _ghost = sorted(set(w for w in _listed) & set(v.get("usage") for v in UNBOUND.values()))
    _keys_in_help = sorted(k for k in DECL for ln in _help if k in ln)
    _off = sorted(set(_listed) ^ set(BOUND_USAGES))
    chk("★ 「帮助」列的就是「可见 + 有处理器」那些（%d 条 · 真敲回来逐条对账）" % len(BOUND_USAGES),
        not _off and sorted(_listed) == sorted(BOUND_USAGES), "对不上：%s" % _off)
    chk("★ %d 条「声明了没处理器」的一条都不在「帮助」里（敲了没反应的别骗玩家去敲）" % len(UNBOUND),
        not _ghost, "%s" % _ghost[:6])
    chk("★ 「帮助」里没有内部 key（%d 行逐行扫 %d 个 key）" % (len(_help), len(DECL)),
        not _keys_in_help, "%s" % _keys_in_help[:6])
except Exception as exc:                                                   # noqa: BLE001 —— 起不来就是红
    chk("★ P-23 1/3「帮助只列有处理器的」跑得起来（真宿主契约）", False,
        "%s: %s" % (type(exc).__name__, exc))

print("⑥ ★ P-23：%d 条「声明了没处理器」真敲一遍 —— 回的是人话（不漏内部 key / 文件路径）" % len(UNBOUND))
_LEAKS = ("包内声明", "未提供处理器", "content/commands.py", "handler", "[MISSING TEXT")
try:
    _echo_bad, _echo_miss, _echo_leak = [], [], []
    for _k in sorted(UNBOUND):
        _sample = hit_sample(_k)
        if not _sample:
            _echo_miss.append(_k)
            continue
        _ad.out.clear()
        _host.handle({"uid": "u_c", "group_id": "g_c", "text": _sample})
        _got = list(_ad.out)
        if _got != [soon_text(_k)]:
            _echo_bad.append((_k, _sample, (_got or [""])[0][:44]))
        for _ln in _got:
            _echo_leak += [(_k, w) for w in _LEAKS if w in _ln]
            if _k in _ln:
                _echo_leak.append((_k, _k))
    chk("★ %d 条真敲：样例反推得出 · 回的都是同一句人话（逐字对账 %s）" % (len(UNBOUND), "SYS_CMD_SOON"),
        not _echo_bad and not _echo_miss, "反推不出：%s · 回话不对：%s" % (_echo_miss[:4], _echo_bad[:3]))
    chk("★ 这些回话里没有内部 key / 文件路径 /「未提供处理器」/ 取不到文案",
        not _echo_leak, "%s" % _echo_leak[:4])
except Exception as exc:                                                   # noqa: BLE001
    chk("★ P-23 2/3「没实现的只说人话」跑得起来（真宿主契约）", False,
        "%s: %s" % (type(exc).__name__, exc))

print("⑦ ★ P-23：「读」由「有处理器没声明」接上（真读到正文 · 点错名不塞东西）")
try:
    _r = DECL.get("read") or {}
    chk("★ 「读」有声明、绑到真实现体（%s）" % ((_r.get("bind") or {}).get("handler")),
        getattr(REG.first_hit("读", visible_only=True), "key", None) == "read"
        and (_r.get("bind") or {}).get("handler") == "content.cmds_ast:read_thing")
    # ★ 同一处两个可读物（骨田：半埋的碑 / 十一块碑）—— 点名挑、不给名字读第一条
    _READS = [("读", "windmill_town", "wt_gate_n", "poi_stone_scripts"),
              ("读 半埋的碑", "belt_north", "bn_bone", "poi_half_buried_stele"),
              ("读 十一块碑", "belt_north", "bn_bone", "poi_eleven_stones"),
              ("读 十一", "belt_north", "bn_bone", "poi_eleven_stones"),
              ("读 墙上的划痕", "old_watchtower", "tower_water_room", "poi_wall_marks"),
              ("读", "belt_north", "bn_bone", "poi_half_buried_stele")]
    _read_bad = []
    for _t, _loc, _node, _pid in _READS:
        _poi = (st.domain("pois") or {}).get(_pid) or {}
        _head = (TX.get("SYS_READ_HEAD") or {}).get("value", "").replace("{name}", _poi.get("name") or "")
        _body = (TX.get(_poi.get("read_text")) or {}).get("value", "")
        _ad.saved = dict(_ad.saved or {}, loc=_loc, node=_node)
        _ad.out.clear()
        _host.handle({"uid": "u_c", "group_id": "g_c", "text": _t})
        _got = list(_ad.out)
        if not _got or _got[0] != _head or _body not in _got:
            _read_bad.append((_t, _loc, _got[:2], _head))
    chk("★ 真敲 %d 条「读」：抬头与正文都对（含同一处两个可读物时按名字挑）" % len(_READS),
        not _read_bad, "%s" % _read_bad[:2])
    _ad.saved = dict(_ad.saved or {}, loc="windmill_town", node="wt_gate_n")
    _ad.out.clear()
    _host.handle({"uid": "u_c", "group_id": "g_c", "text": "读 这儿没有的东西"})
    _none = (TX.get("SYS_READ_NONE") or {}).get("value", "")
    chk("★ 点错名不塞东西：回的是「%s」" % _none, list(_ad.out) == [_none], list(_ad.out))
except Exception as exc:                                               # noqa: BLE001
    chk("★ P-23 3/3「读」那条接上了（真宿主契约）", False, "%s: %s" % (type(exc).__name__, exc))

print("⑧ ★ B3-6：副本那 5 条接上了（真敲 · 塔里 / 塔外两档）")
try:
    _DUNGEON = (("tower_enter", {"loc": "belt_north", "node": "bn_tower"}),
                ("tower_next", {"loc": "old_watchtower", "node": "tower_stair1"}),
                ("tower_map", {"loc": "old_watchtower", "node": "tower_gate"}),
                ("tower_investigate", {"loc": "old_watchtower", "node": "tower_water_room"}),
                ("tower_leave", {"loc": "old_watchtower", "node": "tower_top"}))
    _unbound = [k for k, _w in _DUNGEON if not (DECL.get(k) or {}).get("bind")]
    chk("★ 副本 5 条都挂了 bind（%s）" % " · ".join(k for k, _w in _DUNGEON), not _unbound,
        "%s" % _unbound)
    _db2 = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_cmds_tower.db")
    try:
        os.remove(_db2)
    except OSError:
        pass
    _seed = {"level": 3, "gold": 30, "hp": 100, "bag": {}, "equipped": {}, "codex": {},
             "flags": {}, "prev": [], "race": "human"}
    _ad2 = _Ad([], seed=_seed)
    _host2 = Host(_ad2, str(REPO), inject={"db_path": _db2, "clock": time.time})
    _host2.boot()
    _soon_bad, _soon_miss = [], []
    for _k, _where in _DUNGEON:
        _sample = hit_sample(_k)
        if not _sample:
            _soon_miss.append(_k)
            continue
        _ad2.saved = dict(_seed, **_where)          # 站到那一档（塔里 / 塔门口）
        _ad2.out.clear()
        _host2.handle({"uid": "u_c", "group_id": "g_c", "text": _sample})
        _got = list(_ad2.out)
        if not _got or _got == [soon_text(_k)]:
            _soon_bad.append((_k, _sample, (_got or [""])[0][:40]))
    chk("★ 真敲这 5 条：回的是真话（不是「%s」那一句）"
        % soon_text("tower_map").split("「")[0][:8], not _soon_bad and not _soon_miss,
        "反推不出：%s · 回的还是那句：%s" % (_soon_miss[:3], _soon_bad[:3]))
except Exception as exc:                                                   # noqa: BLE001
    chk("★ B3-6 副本 5 条跑得起来（真宿主契约）", False, "%s: %s" % (type(exc).__name__, exc))

# ══════════════════════════════════════════════════════════════
# ★ B3-9：装备与技能那组（装备 / 卸下 / 装备对比 / 学习 / 技能）
# ══════════════════════════════════════════════════════════════
from content import cmds_ast as CA9                                     # noqa: E402
from content import gear as GB                                          # noqa: E402
from content import panel_build as PB                                   # noqa: E402

#: 本批接下处理器的那 5 条
GEAR5 = ("equip", "unequip", "item_compare", "skills", "skill_learn")


def _r(key, **kw):
    """按 texts 现渲染一条槽位（期望值探针自己算，不手写镜像串 —— 与 §十 同一做法）。"""
    s = (TX.get(key) or {}).get("value", "")
    for k, v in kw.items():
        s = s.replace("{%s}" % k, str(v))
    return s


class _E9(object):
    """直调实现体：只要 env.save() + env.text（与别处同形）。"""

    def __init__(self, text=""):
        self.text = text

    def save(self):
        pass


def _drive9(fn, p, text=""):
    out = []

    async def _go():
        async for _ln in fn(_E9(text), None, "u_b3_9", p):
            out.append(str(_ln))

    asyncio.run(_go())
    return out


print("⑨ ★ B3-9（真宿主）：装备 / 卸下 / 对比 / 学习 / 技能 五条真敲 —— 回的都是真话")
_IT9 = st.domain("items") or {}
_SK9 = st.domain("skills") or {}
_CL9 = {k: v for k, v in (st.domain("classes") or {}).items() if not str(k).startswith("_")}
#: 两把**名字不同**的同格武器（对比才有增有减；名字相同的两条同名双源 —— probe_equip_events ① 那族）
_W1, _W2 = "i_weapon_knight_wall_refined", "i_weapon_knight_oath_refined"
chk("★ 两条真装备都在物品表里（%s / %s）" % (_W1, _W2), _W1 in _IT9 and _W2 in _IT9)
try:
    _W1N, _W2N = _IT9[_W1]["name"], _IT9[_W2]["name"]
    _KNT9 = sorted((int(v.get("lv") or 1), k, v) for k, v in _SK9.items()
                   if v.get("owner_class") == "cls_knight")
    _KNT9N = [v.get("name") for _l, _k, v in _KNT9]
    _KNT9LAB = _CL9["cls_knight"]["name"]
    _SEED9 = {"cls": "cls_knight", "race": "human", "level": 3, "hp": 100, "gold": 30,
              "bag": {_W1: 1, _W2: 1}, "equipped": {}, "codex": {}, "flags": {},
              "loc": "belt_north", "node": "bn_bone"}
    _cap0_9 = int(PB.hp_cap(CA9._p(dict(_SEED9))))
    _dhp9 = int(GB.gear_stats({"equipped": {"_one": _W1}, "enhance": {}}).get("hp", 0))
    _db9 = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_cmds_gear.db")
    try:
        os.remove(_db9)
    except OSError:
        pass
    _ad9 = _Ad([], seed=dict(_SEED9))
    _host9 = Host(_ad9, str(REPO), inject={"db_path": _db9, "clock": time.time})
    _host9.boot()

    def _say9(text):
        _ad9.out.clear()
        _host9.handle({"uid": "u_c", "group_id": "g_c", "text": text})
        return list(_ad9.out)

    _bad9 = []
    _wear9 = _say9("装备 %s" % _W1N)
    if not _wear9 or _wear9[0] != _r("SYS_GEAR_EQUIP_OK", icon=_IT9[_W1].get("icon", ""),
                                     name=_W1N, kind=_IT9[_W1].get("kind", "")):
        _bad9.append(("装备", _wear9[:1]))
    _sv9 = _ad9.saved or {}
    if int(_sv9.get("hp_max") or 0) != _cap0_9 + _dhp9 \
            or _sv9.get("equipped") != {_IT9[_W1]["slot"]: _W1}:
        _bad9.append(("装备 没改档上的 equipped / 面板派生的上限", _sv9.get("hp_max"),
                      _sv9.get("equipped")))
    _st9 = _say9("状态")
    _vv9 = _r("SYS_STATUS_VITALS", hp=_sv9.get("hp"), hp_max=_sv9.get("hp_max"),
              mo=_sv9.get("mo"), mo_max=_sv9.get("mo_max"), gold=_sv9.get("gold"))
    if _vv9 not in _st9:
        _bad9.append(("状态 没跟着面板走", _st9[1:2], _vv9))
    _cmp9 = _say9("对比 %s" % _W2N)
    if not _cmp9 or _cmp9[0] != _r("SYS_CMP_HEAD", name=_W2N, quality=_IT9[_W2].get("quality", ""),
                                   kind=_IT9[_W2].get("kind", ""), cur=_W1N):
        _bad9.append(("对比", _cmp9[:1]))
    if _say9("装备对比 %s" % _W2N) != _cmp9:
        _bad9.append(("「装备对比」与「对比」两条写法回的不是同一段",))
    _off9 = _say9("卸下 %s" % _W1N)
    if not _off9 or _off9[0] != _r("SYS_GEAR_UNEQUIP_OK", icon=_IT9[_W1].get("icon", ""),
                                   name=_W1N, kind=_IT9[_W1].get("kind", "")):
        _bad9.append(("卸下", _off9[:1]))
    _learn9 = _say9("学习 %s" % _KNT9N[0])
    if not _learn9 or _learn9[0] != _r("SYS_SKILL_ALREADY", name=_KNT9N[0]):
        _bad9.append(("学习", _learn9[:1]))
    _list9 = _say9("技能")
    if not _list9 or _list9[0] != _r("SYS_SKILL_HEAD", cls=_KNT9LAB,
                                     known=len(_KNT9N), locked=0):
        _bad9.append(("技能 抬头", _list9[:1]))
    _miss9 = [n for n in _KNT9N if not any(n in _ln for _ln in _list9)]
    if _miss9:
        _bad9.append(("技能 少了这几条", _miss9))
    chk("★ 真敲：装备 → 状态 → 对比 → 卸下 → 学习 → 技能，回的都是填了槽位的真话",
        not _bad9, "%s" % _bad9[:3])
    _all9 = _wear9 + _st9 + _cmp9 + _off9 + _learn9 + _list9
    chk("★ 这 5 条一条都不再回「还没接上」那一句",
        not [k for k in GEAR5 if any(soon_text(k) in _ln for _ln in _all9)])
    chk("★ 这 5 条都挂了 bind", not [k for k in GEAR5 if not (DECL.get(k) or {}).get("bind")])
    chk("★ 「声明了、可见、还没实现」**只许降**：B3-9 收 33 → 本批 %d 条（上限 %d）"
        % (len(UNBOUND), UNBOUND_MAX), len(UNBOUND) <= UNBOUND_MAX, "%s" % sorted(UNBOUND)[:6])
    _leak9 = [(k, _ln[:38]) for k in GEAR5 for _ln in _all9
              if any(w in _ln for w in (_W1, _W2, "SKILL_", "[MISSING TEXT"))]
    chk("★ 回话里没有物品 / 技能 id，也没有取不到文案", not _leak9, "%s" % _leak9[:3])
    _sv9b = _ad9.saved or {}
    chk("★ 穿一件再脱一件 ⇒ 档上逐字回原样（背包 / 身上）",
        _sv9b.get("bag") == _SEED9["bag"] and _sv9b.get("equipped") == _SEED9["equipped"],
        "%s / %s" % (_sv9b.get("bag"), _sv9b.get("equipped")))
    # ★ 两条真分开（④ 那条老判据钉不住的东西）：同一件东西、同一个档 ——
    #   `装备对比` 出对比抬头（位子空着）· `装备` 出穿上那一句；改前两条都归 equip。
    _db9b = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_cmds_cmp.db")
    try:
        os.remove(_db9b)
    except OSError:
        pass
    _ad9b = _Ad([], seed={"cls": "cls_knight", "race": "human", "level": 1, "hp": 100,
                          "bag": {_W1: 1}, "equipped": {}, "codex": {}, "flags": {}})
    _host9b = Host(_ad9b, str(REPO), inject={"db_path": _db9b, "clock": time.time})
    _host9b.boot()

    def _say9b(text):
        _ad9b.out.clear()
        _host9b.handle({"uid": "u_c", "group_id": "g_c", "text": text})
        return list(_ad9b.out)

    _cmpB = _say9b("装备对比 %s" % _W1N)
    _eqB = _say9b("装备 %s" % _W1N)
    chk("★ 同一件东西两条真分开：`装备对比` 回对比抬头（位子空着）· `装备` 回穿上那一句",
        _cmpB[:1] == [_r("SYS_CMP_HEAD", name=_W1N, quality=_IT9[_W1].get("quality", ""),
                         kind=_IT9[_W1].get("kind", ""), cur=_r("SYS_GEAR_SLOT_EMPTY"))]
        and _eqB[:1] == [_r("SYS_GEAR_EQUIP_OK", icon=_IT9[_W1].get("icon", ""), name=_W1N,
                            kind=_IT9[_W1].get("kind", ""))],
        "%s / %s" % (_cmpB[:1], _eqB[:1]))
except Exception as exc:                                               # noqa: BLE001 —— 起不来就是红
    chk("★ B3-9 五条真敲跑得起来（真宿主契约）", False, "%s: %s" % (type(exc).__name__, exc))


print("⑩ ★ B3-9（直调）：学习 / 技能 的语义 —— 解锁那一班 · 四道门 · 落档 · 真打一场")
try:
    from content import cmds_ast as CA9                                # noqa: E402
    from content import cmds_skill as CSK                              # noqa: E402
    from content import cmds_battle as CBAT9                           # noqa: E402
    from content import combat as CB9                                  # noqa: E402

    _SK10 = CA9._data("skills")        # ★ 走实现体真读的那一份（临时造一条也注入这里）
    _CL10 = st.domain("classes") or {}
    _rows10 = {c: CSK._of_class(c, 1) for c in sorted(_CL10) if not str(c).startswith("_")}
    _tot10 = sum(len(a) for a, _l in _rows10.values())
    _owned10 = [1 for v in _SK10.values() if v.get("owner_class")]
    chk("★ 六职业 1 级解锁的技能：%s（合 %d 条 = 域里挂 owner_class 的全部）"
        % (" · ".join("%s %d" % (_CL10[c]["name"], len(a)) for c, (a, _l) in sorted(_rows10.items())),
           _tot10), _tot10 == len(_owned10), "%d vs %d" % (_tot10, len(_owned10)))
    _hi10 = sorted((k, v.get("lv")) for k, v in _SK10.items() if int(v.get("lv") or 1) > 1)
    chk("★ 今天没有「解锁等级 > 1」的技能（%d 条全 lv=1）—— 11–20 级那 12 条补进来之后"
        "这一条会翻红，那时按新数据改它" % len(_SK10), not _hi10, "%s" % _hi10[:4])

    _knt10 = {"cls": "cls_knight", "level": 3, "race": "human", "hp": 100,
              "bag": {}, "equipped": {}, "flags": {}, "codex": {}}
    _name10 = [v.get("name") for _l, _k, v in sorted(
        (int(v.get("lv") or 1), k, v) for k, v in _SK10.items()
        if v.get("owner_class") == "cls_knight")]
    _lst10 = _drive9(CSK.skills, dict(_knt10))
    _head10 = _r("SYS_SKILL_HEAD", cls=_CL10["cls_knight"]["name"], known=len(_name10), locked=0)
    chk("★ 骑士档 `技能`：抬头「%s」· %d 条一条不落"
        % (_head10, len(_name10)),
        bool(_lst10) and _lst10[0] == _head10
        and not [n for n in _name10 if not any(n in _ln for _ln in _lst10)],
        "%s" % _lst10[:1])
    _idleak10 = [_ln[:34] for _ln in _lst10 if any(k in _ln for k in _SK10)]
    chk("★ `技能` 只出名字，不漏技能 id（%d 行逐行扫）" % len(_lst10), not _idleak10,
        "%s" % _idleak10[:2])

    # 落档那一条：档上只记了一条 ⇒ 学第二条 ⇒ **整班一起记上**（否则「学了新的丢掉默认那一班」）
    _one10 = dict(_knt10, skills=["SKILL_KNT_slash"])
    _learn10 = _drive9(CSK.skill_learn, _one10, "学习 %s" % _name10[1])
    _ids10 = list(_one10.get("skills") or [])
    _names10 = sorted(_SK10[i].get("name") for i in _ids10 if i in _SK10)
    chk("★ `学习 %s` 落档：档上那班 = 本职业此刻解锁的全部（%s）"
        % (_name10[1], " · ".join(sorted(_name10))),
        bool(_learn10) and _learn10[0] == _r("SYS_SKILL_LEARN", name=_name10[1], n=len(_name10))
        and _names10 == sorted(_name10), "%s / %s" % (_learn10[:1], _names10))
    chk("★ 档上那班 = 战斗真放的那班（actor[\"skills\"] 与档上一个字不差）",
        list(CB9.player_actor(_one10).get("skills") or []) == _ids10,
        "%s" % (CB9.player_actor(_one10).get("skills"),))
    chk("★ 再学同一条 ⇒ 「%s」（幂等，不动档）" % _r("SYS_SKILL_ALREADY", name=_name10[1]),
        _drive9(CSK.skill_learn, _one10, "学习 %s" % _name10[1])
        == [_r("SYS_SKILL_ALREADY", name=_name10[1])])

    _mage10 = next((v.get("name"), v.get("owner_class")) for v in _SK10.values()
                   if v.get("owner_class") == "cls_mage")
    chk("★ 门② 不是本职业的（%s）⇒ 点名是谁的" % _mage10[0],
        _drive9(CSK.skill_learn, dict(_knt10), "学习 %s" % _mage10[0])
        == [_r("SYS_SKILL_NOTMINE", name=_mage10[0], owner=_CL10[_mage10[1]]["name"])])
    chk("★ 门① 域里没有这条 ⇒ 明说没有",
        _drive9(CSK.skill_learn, dict(_knt10), "学习 没有这条技能")
        == [_r("SYS_SKILL_NONE", name="没有这条技能")])
    _nocls10 = _drive9(CSK.skills, {})
    _noclsL10 = _drive9(CSK.skill_learn, {}, "学习 横剑")
    chk("★ 档上还没职业：`技能` 与 `学习` 都点名（不猜职业）",
        _nocls10 == [_r("SYS_SKILL_NOCLS")] and _noclsL10 == [_r("SYS_SKILL_NOCLS")],
        "%s / %s" % (_nocls10[:1], _noclsL10[:1]))

    # 门③ 解锁等级没到 —— **只在内存里**造一条 lv=99 的（不动域里的文件）
    _fake10 = "SKILL_PROBE_high_level"
    _SK10[_fake10] = {"name": "探针高等级技", "kind": _name10 and (
        next(v.get("kind") for v in _SK10.values() if v.get("kind"))), "lv": 99,
        "owner_class": "cls_knight", "mp": 0, "cd": 0, "power": 1.0}
    try:
        _hi_learn = _drive9(CSK.skill_learn, dict(_knt10), "学习 %s" % _SK10[_fake10]["name"])
    finally:
        _SK10.pop(_fake10, None)
    chk("★ 门③ 解锁等级没到（内存里造一条 lv=99）⇒ 「%s」"
        % _r("SYS_SKILL_TOO_LOW", name="探针高等级技", lv=99, gap=96),
        _hi_learn == [_r("SYS_SKILL_TOO_LOW", name="探针高等级技", lv=99, gap=96)],
        "%s" % _hi_learn[:1])

    # 真打一场：走的就是档上那班技能 ⇒ 出真伤害（不是空放）
    _fight10 = dict(_one10)
    _fight10.update({"level": 3, "hp": 300, "loc": "belt_north", "node": "bn_bone",
                     "bag": {}, "codex": {}, "flags": {}})
    _lw10 = _drive9(CBAT9.attack, _fight10)
    _dmg10 = [_ln for _ln in _lw10 if "伤害" in _ln]
    chk("★ 真打一场（档上那班技能）：出 %d 行伤害 ⇒ 技能放得出来、不是空放" % len(_dmg10),
        bool(_dmg10), "%s" % _lw10[:3])
except Exception as exc:                                              # noqa: BLE001
    chk("★ B3-9 学习 / 技能 那条跑得起来（直调实现体）", False,
        "%s: %s" % (type(exc).__name__, exc))


print("⑪ ★ B3-9（直调）：`装备对比` 逐字对账 —— 期望值现算（gear_stats + texts），四档各比一遍")


def _cmp_want(cur_id, new_id):
    """对比该出哪些行 —— **从唯一取值口现算**（`gear.gear_stats` + texts），不手写镜像串。

    ★ 列哪几行按实现体的同一条规则现算：**不带 note 的数值词条**才算数值行（面板属性那一类），
      带 note 的走规则行 —— 所以带 note 的键（`res_element` / `dmg_half_chance` …）不该
      出现 `SYS_STAT_*` 标签需求（补一句：它们本来也没有标签槽位）。
    """
    new11 = GB.gear_stats({"equipped": {"_one": new_id}, "enhance": {}})
    cur11 = GB.gear_stats({"equipped": {"_one": cur_id}, "enhance": {}}) if cur_id else {}
    _pk = set()
    for _rr in (new_id, cur_id):
        for _a in ((_IT9[_rr].get("affixes") or []) if _rr else []):
            if not _a.get("note") and isinstance(_a.get("v"), (int, float)) \
                    and not isinstance(_a.get("v"), bool):
                _pk.add(_a["stat"])
    out = [_r("SYS_CMP_HEAD", name=_IT9[new_id]["name"], quality=_IT9[new_id].get("quality", ""),
              kind=_IT9[new_id].get("kind", ""),
              cur=(_IT9[cur_id]["name"] if cur_id else _r("SYS_GEAR_SLOT_EMPTY")))]
    if not cur_id:
        out.append(_r("SYS_CMP_EMPTY", kind=_IT9[new_id].get("kind", "")))
        for a in _IT9[new_id].get("affixes") or []:
            if a.get("note"):
                out.append(_r("SYS_GEAR_AFFIX_NOTE", note=str(a["note"])))
            else:
                out.append(_r("SYS_GEAR_AFFIX_ROW", label=_r("SYS_STAT_%s" % a["stat"].upper()),
                              value="%g" % float(a["v"])))
        return out
    up = down = same = 0
    for stat in sorted(_pk):
        a, b = float(cur11.get(stat, 0.0)), float(new11.get(stat, 0.0))
        if abs(a - b) < 1e-9:
            same += 1
            out.append(_r("SYS_CMP_ROW_SAME", label=_r("SYS_STAT_%s" % stat.upper()),
                          value="%g" % a))
            continue
        d = b - a
        up += 1 if d > 0 else 0
        down += 1 if d < 0 else 0
        out.append(_r("SYS_CMP_ROW", label=_r("SYS_STAT_%s" % stat.upper()), old="%g" % a,
                      new="%g" % b, sign=("+" if d > 0 else "-"), delta="%g" % abs(d)))
    for slotk, rr in (("SYS_CMP_NOTE_NEW", _IT9[new_id]), ("SYS_CMP_NOTE_CUR", _IT9[cur_id])):
        for a in rr.get("affixes") or []:
            if a.get("note"):
                out.append(_r(slotk, note=str(a["note"])))
    out.append(_r("SYS_CMP_VERDICT", up=up, down=down, same=same))
    return out


try:
    from content import cmds_gear as CG11                              # noqa: E402

    _CASES11 = [("有增有减（同格两把不同的武器）", _W1, _W2),
                ("位子空着", "", "i_armor_bottom_light_common"),
                ("全一样（同格两件同数值）", "i_armor_bottom_light_common",
                 "i_armor_bottom_weighted_common"),
                # ★ 带 note 的数值词条（`dmg_half_chance 10`）不进数值行、也不许要标签 ——
                #   这一条真跑过：改前它会出一行 `[MISSING TEXT: SYS_STAT_DMG_HALF_CHANCE]`
                ("带 note 的数值词条只出「改规则」那一行",
                 "i_armor_top_heavy_refined", "i_armor_top_heavy_rare")]
    _bad11 = []
    for _lab11, _cur11, _new11 in _CASES11:
        if _new11 not in _IT9:
            _bad11.append((_lab11, "夹具不在物品表里：%s" % _new11))
            continue
        _p11 = {"cls": "cls_knight", "level": 3, "hp": 100, "bag": {_new11: 1},
                "equipped": ({_IT9[_new11]["slot"]: _cur11} if _cur11 else {}),
                "flags": {}, "codex": {}}
        _got11 = _drive9(CG11.item_compare, _p11, "对比 %s" % _IT9[_new11]["name"])
        _want11 = _cmp_want(_cur11, _new11)
        if _got11 != _want11 or any("[MISSING TEXT" in _ln for _ln in _got11):
            _bad11.append((_lab11, _got11[:5], _want11[:5]))
    chk("★ 四档（有增有减 / 位子空着 / 全一样 / 带 note 的不进数值行）逐字对账："
        "整段输出 = `gear_stats` + texts 现算的期望，且一行 `[MISSING TEXT` 都没有",
        not _bad11, "%s" % _bad11[:2])
except Exception as exc:                                              # noqa: BLE001
    chk("★ B3-9 装备对比 那条跑得起来（直调实现体）", False,
        "%s: %s" % (type(exc).__name__, exc))

print("⑫ ★ B3-12（真宿主）：这一批新接的 8 条真敲 —— 逐字对槽位 · 档上副作用对 · 不漏机器键")
NEW12 = ("board_show", "attrs", "item_show", "item_drop", "item_sell",
         "bag_sort", "stash", "achievements")
_BAD12 = []


def _num12(v):
    """面板数的写法（整数不带小数点 · 小数一位）—— 期望值按这一条现算，不手写镜像串。"""
    f = float(v)
    return "%d" % int(f) if f.is_integer() else "%.1f" % f


def _decl_usage(key):
    """声明里那个 `usage` 的第一个词（玩家看见的那个词）—— 期望值从**声明**现读，不手写。"""
    return str((DECL.get(key) or {}).get("usage") or "").split(" ")[0].strip()


def _statlist13():
    """五个维名的呈现串（期望值从 texts 槽位现拼 —— 与实现体同一个口，不手写中文）。"""
    from content import alloc as _AL
    return " · ".join(_r("SYS_STAT_%s" % _s) for _s in _AL.STATS)


def _decl_usage_full(key):
    """声明里那条 `usage` **原样**（`加点 <属性> [次数]`）—— 提示行里递给玩家看的就是它。"""
    return str((DECL.get(key) or {}).get("usage") or "")


def _rows12(actor):
    return [_r("SYS_ATTR_ROW", label=_r("SYS_STAT_%s" % slot), value=_num12(actor[key]))
            for key, slot in _CM12.PANEL_ROWS if key in actor]


def _crit12(actor):
    for _L in (PB.stacks().get(str(actor.get("panel_stack") or "")) or {}).get("layers") or []:
        if _L.get("id") == "crit_rate":
            return float((_L.get("values") or {}).get("crit") or 0.0)
    return 0.0


try:
    from content import cmds_more as _CM12                                # noqa: E402
    from content import alloc as _AL13                                    # noqa: E402
    from content import loot as _LT12                                    # noqa: E402
    from content import codex as _CX12                                   # noqa: E402
    from content import eggs as _EG12                                    # noqa: E402
    from content import titles as _TT12                                  # noqa: E402
    from content import cmds_quest as _CQ12                              # noqa: E402

    chk("★ 这一批 %d 条都挂了 bind（%s）" % (len(NEW12), " · ".join(NEW12)),
        not [k for k in NEW12 if not (DECL.get(k) or {}).get("bind")],
        "%s" % [k for k in NEW12 if not (DECL.get(k) or {}).get("bind")])
    chk("★ 「声明了、可见、还没实现」33 → %d 条（%s）" % (len(UNBOUND), " · ".join(sorted(UNBOUND))),
        len(UNBOUND) == UNBOUND_MAX, "%s" % sorted(UNBOUND))

    _QS12 = _CQ12._quests()
    _NPCS12 = st.domain("npcs") or {}
    _POT12, _SCRAP12, _BONE12 = "i_potion_heal", "i_material_iron_scrap", "i_junk_bone"
    _WPN12 = _W1
    _SEED12 = {"cls": "cls_knight", "race": "human", "level": 3, "exp": 0, "hp": 100,
               "gold": 30, "loc": "windmill_town", "node": "wt_inn", "prev": [],
               "bag": {_POT12: 2, _SCRAP12: 5, _BONE12: 3, _WPN12: 1}, "equipped": {},
               "codex": {}, "flags": {}}
    _db12 = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_cmds_more.db")
    try:
        os.remove(_db12)
    except OSError:
        pass
    _ad12 = _Ad([], seed=dict(_SEED12))
    _h12 = Host(_ad12, str(REPO), inject={"db_path": _db12, "clock": time.time})
    _h12.boot()
    _said12 = []

    def _say12(text):
        _ad12.out.clear()
        _h12.handle({"uid": "u_c", "group_id": "g_c", "text": text})
        _said12.append((text, list(_ad12.out)))
        return list(_ad12.out)

    _sv12 = lambda: (_ad12.saved or {})                                  # noqa: E731 —— 档（真敲后读回）

    # ── 看 <编号>：单子全文（未接 / 已接 / 支线编号 / 没有这张）───────────────────
    def _want_show(order):
        _q = next(v for v in _QS12.values() if v.get("order") == order)
        out = [_r("SYS_BSHOW_HEAD", order=order, name=_q["name"], level=_q["min_level"])]
        _gv = (_NPCS12.get(str(_q.get("giver") or "")) or {}).get("name")
        if _gv:
            out.append(_r("SYS_BSHOW_GIVER", giver=_gv))
        out.append(_r("SYS_BOARD_TODO", objective=_q["objective"]))
        if _q.get("insight"):
            out.append(_r("SYS_JOB_INSIGHT", insight=_q["insight"]))
        out.append(_r("SYS_BSHOW_REWARD", exp=_q["reward_exp"], gold=_q["reward_gold"]))
        # ★ B3-13 合入之后：有些条目带 `require`（前置条件）⇒ 单子全文里会多出「还差…」那几行。
        #   期望值走**同一个口** `_CQ12._unmet`（前置条件那部分由域里的 require + 这份起手档现算），
        #   不手写镜像串 —— 本块钉的仍然是「单子全文与域 + texts 一致」。
        #   （缩进两格是呈现口径：`cmds_more.board_show` 也是这么拼的，见它 `yield "  " + line`）
        out.extend("  " + _ln for _ln in _CQ12._unmet(_SEED12, _q))
        return out

    _g1 = _say12("看 1")
    _w1 = _want_show(1) + [_r("SYS_BOARD_NEXT", order=1)]
    if _g1 != _w1:
        _BAD12.append(("看 1", _g1, _w1))
    _g13 = _say12("看 13")
    _w13 = _want_show(13) + [_r("SYS_BOARD_NEXT", order=13)]
    if _g13 != _w13:
        _BAD12.append(("看 13（支线编号也认）", _g13, _w13))
    _g99 = _say12("看 99")
    if _g99 != [_r("SYS_JOB_NOSUCH", name="99")]:
        _BAD12.append(("看 99", _g99))
    _say12("接 1")
    _g1b = _say12("看 1")
    _w1b = _want_show(1) + [_r("SYS_BOARD_ACTIVE"), _r("SYS_BOARD_DELIVER", order=1)]
    if _g1b != _w1b:
        _BAD12.append(("看 1（已接）", _g1b, _w1b))
    chk("★ `看 <编号>` 真敲四档：未接 / 支线编号 / 没有这张 / 已接 —— 整段与 quests 域 + texts 现算的期望"
        "逐字一致（编号就是 `order`，与『接』认的是同一个字段）",
        not [x for x in _BAD12 if x[0].startswith("看")],
        "%s" % [x for x in _BAD12 if x[0].startswith("看")][:2])

    # ── 属性：面板现算（与生命上限同一个口）────────────────────────────────
    _recA = _sv12()
    _grA, _bfA = PB.gear_and_buffs(_recA)
    _actA = PB.build_actor(str(_recA.get("cls")), int(_recA.get("level") or 1),
                           _AL13.of_record(_recA), _grA, buffs=_bfA)
    _capA = int(PB.hp_cap(dict(_recA)))
    _gA = _say12("属性")
    _wA = [_r("SYS_ATTR_HEAD", who=_r("SYS_NAME_UNKNOWN"), cls=_CL9["cls_knight"]["name"],
              level=_recA.get("level")),
           _r("SYS_ATTR_VITAL", hp=_num12(_actA.get("max_hp")), mo=_num12(_actA.get("max_mp")),
              crit=_num12(_crit12(_actA) * 100))] + _rows12(_actA) + [
           _r("SYS_ATTR_NOALLOC"),
           # ★ P-34：没投的点那一行（余额 > 0 才出）—— 甲案下这是"点数在手里"的提示
           _r("SYS_ATTR_LEFT", left=_AL13.left_of_record(_recA), usage=_decl_usage("alloc")),
           _r("SYS_ATTR_NOGEAR"), _r("SYS_ATTR_NOTE")]
    if _gA != _wA:
        _BAD12.append(("属性", _gA, _wA))
    _want_cap = _r("SYS_ATTR_VITAL", hp=_num12(_capA), mo=_num12(_actA.get("max_mp")),
                   crit=_num12(_crit12(_actA) * 100))
    if _want_cap not in _gA:
        _BAD12.append(("属性 的生命上限 != hp_cap（两个源）", _gA[:2], _want_cap))
    _labs12 = [_r("SYS_STAT_%s" % s) for _k, s in _CM12.PANEL_ROWS]
    # ★ P-34：尾注由三行变四行（多了一行「没投的点」）⇒ 二级属性那几行的范围**按行数取**，
    #   不再靠"尾部减 3"这种位置猜（判据的意思没变：九行都要认得出标签）。
    _n12 = len(_rows12(_actA))
    if not all(any(lab in _ln for lab in _labs12) for _ln in _gA[2:2 + _n12]):
        _BAD12.append(("属性 的二级属性行认不出标签", _gA[:3]))
    chk("★ `属性` 真敲：抬头 / 生命上限（= `hp_cap` 那唯一来源）/ 九行二级属性 / 加点 **+ 没投的点** / "
        "装备 —— 与 `panel_build` 现算的期望逐字一致",
        not [x for x in _BAD12 if x[0].startswith("属性")],
        "%s" % [x for x in _BAD12 if x[0].startswith("属性")][:2])

    # ── 查看 <物品>：详情逐字对账（分类 · 词条 · 说明 · 收价）──────────────
    def _detail12(rec):
        """抬头那截「分类 · 品阶」（品阶域里没有就不写 —— 与实现体同一条规则）。"""
        d = str(rec.get("kind") or "")
        return "%s · %s" % (d, rec["quality"]) if rec.get("quality") else d

    _pot = _IT9[_POT12]
    _gC = _say12("查看 药水")
    _wC = [_r("SYS_ITEM_HEAD", name=_pot["name"], icon=_pot.get("icon", ""),
              detail=_detail12(_pot), n=int(_SEED12["bag"][_POT12])),
           _r("SYS_ITEM_DESC", desc=_pot["desc"]),
           _r("SYS_ITEM_HEAL_PCT", pct=int(round(float(_pot["effect"]["hp_pct"]) * 100))),
           _r("SYS_ITEM_PRICE", gold=int(_pot["price"]))]
    if _gC != _wC:
        _BAD12.append(("查看 药水", _gC, _wC))
    _wpn = _IT9[_WPN12]
    _gW = _say12("查看 %s" % _wpn["name"])
    _wW = [_r("SYS_ITEM_HEAD", name=_wpn["name"], icon=_wpn.get("icon", ""),
              detail=_detail12(_wpn), n=1)] \
        + [_r("SYS_GEAR_AFFIX_ROW", label=_r("SYS_STAT_%s" % a["stat"].upper()),
              value="%g" % float(a["v"])) for a in _wpn.get("affixes") or []]
    if _gW != _wW:
        _BAD12.append(("查看 武器（词条）", _gW, _wW))
    _gNo = _say12("查看 不存在的")
    if _gNo != [_r("SYS_GEAR_IN_BAG", name="不存在的")]:
        _BAD12.append(("查看 没有的", _gNo))
    chk("★ `查看 <物品>` 真敲三档：药（分类 · 说明 · 按成回血 · 收价）/ 武器（词条走 `gear` 同一口）/ "
        "没有这件 —— 逐字对账",
        not [x for x in _BAD12 if x[0].startswith("查看")],
        "%s" % [x for x in _BAD12 if x[0].startswith("查看")][:2])

    # ── 丢弃：真掉 + 数量 + 掏空摘条目 + 档上副作用 ────────────────────────
    _bag0 = dict(_SEED12["bag"])
    _gD = _say12("丢弃 铁屑 2")
    _wD = [_r("SYS_DROP_OK", icon=_IT9[_SCRAP12].get("icon", ""), name=_IT9[_SCRAP12]["name"], n=2),
           _r("SYS_DROP_LEFT", n=3)]
    if _gD != _wD or _sv12().get("bag") != dict(_bag0, **{_SCRAP12: 3}):
        _BAD12.append(("丢弃 2", _gD, _sv12().get("bag")))
    _gD2 = _say12("丢弃 铁屑 99")
    if _gD2 != [_r("SYS_DROP_OK", icon=_IT9[_SCRAP12].get("icon", ""),
                   name=_IT9[_SCRAP12]["name"], n=3)] \
            or _SCRAP12 in (_sv12().get("bag") or {}):
        _BAD12.append(("丢弃 99（按手里的算 · 摘条目）", _gD2, _sv12().get("bag")))
    _gD3 = _say12("丢弃 不存在的东西")
    if _gD3 != [_r("SYS_GEAR_IN_BAG", name="不存在的东西")]:
        _BAD12.append(("丢弃 没有的", _gD3))
    chk("★ `丢弃` 真敲三档：按数量掉 / 超过手里的按手里的算（条目掏空即摘）/ 没有这件 —— "
        "回话逐字对账且**档上 bag 真变**",
        not [x for x in _BAD12 if x[0].startswith("丢弃")],
        "%s" % [x for x in _BAD12 if x[0].startswith("丢弃")][:3])

    # ── 卖出：价来自域 · 装备不收 · 野外不卖 ────────────────────────────
    _gS = _say12("卖出 骨头")
    _wS = [_r("SYS_SELL_OK", icon=_IT9[_BONE12].get("icon", ""), name=_IT9[_BONE12]["name"],
              n=1, gold=int(_IT9[_BONE12]["price"]))]
    if _gS != _wS or int(_sv12().get("gold") or 0) != 30 + int(_IT9[_BONE12]["price"]) \
            or int((_sv12().get("bag") or {}).get(_BONE12) or 0) != 2:
        _BAD12.append(("卖出 骨头", _gS, _sv12().get("gold"), _sv12().get("bag")))
    _gS2 = _say12("卖出 %s" % _wpn["name"])
    if _gS2 != [_r("SYS_SELL_NOPRICE", name=_wpn["name"])]:
        _BAD12.append(("卖出 没价的（域里没写 price）", _gS2))
    _db12b = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_cmds_more_b.db")
    try:
        os.remove(_db12b)
    except OSError:
        pass
    _ad12b = _Ad([], seed=dict(_SEED12, loc="belt_north", node="bn_bone"))
    _h12b = Host(_ad12b, str(REPO), inject={"db_path": _db12b, "clock": time.time})
    _h12b.boot()
    _ad12b.out.clear()
    _h12b.handle({"uid": "u_c", "group_id": "g_c", "text": "卖出 骨头"})
    _gS3 = list(_ad12b.out)
    if _gS3 != [_r("SYS_SELL_AWAY")] or (_ad12b.saved or {}).get("bag") != _SEED12["bag"]:
        _BAD12.append(("野外卖出", _gS3, (_ad12b.saved or {}).get("bag")))
    chk("★ `卖出` 真敲三档：域里有价 ⇒ 钱与背包同时变 / 域里没价（拿在手上的）⇒ 不收 / "
        "人在野外 ⇒ 明说铺子在镇上且**不动档**",
        not [x for x in _BAD12 if x[0].startswith("卖出")],
        "%s" % [x for x in _BAD12 if x[0].startswith("卖出")][:3])

    # ── 整理背包：真重排（键序 = 机器键分组 + 组内按名）+ 一件不少 ───────────
    _bagB4 = dict(_sv12().get("bag") or {})
    _grp4 = {}
    for _iid in _bagB4:
        _grp4.setdefault(_LT12.kind_key_of(_iid), []).append(_iid)
    _ord4 = []
    for _kk in sorted(_grp4):
        _ord4 += sorted(_grp4[_kk], key=lambda i: (str(_LT12.rec_of(i).get("name") or ""), i))
    _g4 = _say12("整理背包")
    _w4 = [_r("SYS_SORT_HEAD", n=len(_bagB4))]
    for _kk in sorted(_grp4):
        _ids = _grp4[_kk]
        _w4.append(_r("SYS_SORT_ROW", kind=_LT12.rec_of(_ids[0]).get("kind") or _kk, n=len(_ids),
                      list=" · ".join("%s ×%d" % (_LT12.rec_of(i).get("name") or i, _bagB4[i])
                                      for i in _ids)))
    _w4.append(_r("SYS_SORT_TAIL"))
    _bagA4 = dict(_sv12().get("bag") or {})
    if _g4 != _w4 or list(_bagA4) != _ord4 or _bagA4 != _bagB4:
        _BAD12.append(("整理背包", _g4, list(_bagA4), _ord4))
    chk("★ `整理背包` 真敲：回话逐字对账（分组名从域里透传）· **档上键序真重排**成 "
        "「机器键分组 + 组内按名」· 数量与集合一件没少",
        not [x for x in _BAD12 if x[0].startswith("整理")],
        "%s" % [x for x in _BAD12 if x[0].startswith("整理")][:2])

    # ── 存放 / 取出：方向取自声明 · 档上两个容器都对 ─────────────────────
    _gI = _say12("存放 药水")
    if _gI != [_r("SYS_STASH_IN_OK", icon=_pot.get("icon", ""), name=_pot["name"], n=1, have=1)] \
            or (_sv12().get("flags") or {}).get("stash") != {_POT12: 1} \
            or int((_sv12().get("bag") or {}).get(_POT12) or 0) != 1:
        _BAD12.append(("存放 药水", _gI, (_sv12().get("flags") or {}).get("stash"),
                       _sv12().get("bag")))
    _gI2 = _say12("存 药水")
    if _gI2 != [_r("SYS_STASH_IN_OK", icon=_pot.get("icon", ""), name=_pot["name"], n=1, have=2)] \
            or (_sv12().get("flags") or {}).get("stash") != {_POT12: 2}:
        _BAD12.append(("存 药水（单字别名同方向）", _gI2, (_sv12().get("flags") or {}).get("stash")))
    _gO = _say12("取出 药水")
    if _gO != [_r("SYS_STASH_OUT_OK", icon=_pot.get("icon", ""), name=_pot["name"], n=1, have=1)] \
            or (_sv12().get("flags") or {}).get("stash") != {_POT12: 1} \
            or int((_sv12().get("bag") or {}).get(_POT12) or 0) != 1:
        _BAD12.append(("取出 药水", _gO, (_sv12().get("flags") or {}).get("stash"),
                       _sv12().get("bag")))
    _gO2 = _say12("取出 药水")
    if _gO2 != [_r("SYS_STASH_OUT_OK", icon=_pot.get("icon", ""), name=_pot["name"], n=1, have=2)] \
            or (_sv12().get("flags") or {}).get("stash") is not None \
            or int((_sv12().get("bag") or {}).get(_POT12) or 0) != 2:
        _BAD12.append(("取出 药水 · 掏空箱子摘掉那一格", _gO2,
                       (_sv12().get("flags") or {}).get("stash"), _sv12().get("bag")))
    _gE = _say12("取出 骨头")
    _stash_now = (_sv12().get("flags") or {}).get("stash") or {}
    _wE = (_r("SYS_STASH_EMPTY") if not _stash_now
           else _r("SYS_STASH_MISS", name=_IT9[_BONE12]["name"]))
    if _gE != [_wE]:
        _BAD12.append(("取出 空箱里没有的", _gE, _wE))
    _ad12b.out.clear()
    _h12b.handle({"uid": "u_c", "group_id": "g_c", "text": "存放 骨头"})
    _gAway = list(_ad12b.out)
    if _gAway != [_r("SYS_STASH_AWAY")] or (_ad12b.saved or {}).get("bag") != _SEED12["bag"] \
            or ((_ad12b.saved or {}).get("flags") or {}).get("stash"):
        _BAD12.append(("不在客栈还想存", _gAway, (_ad12b.saved or {}).get("bag")))
    chk("★ `存放 / 取出` 真敲六档：存放 · 单字别名（方向取自声明 usage，不靠 pattern 先后）· "
        "取出两次（掏空箱子即摘掉那一格）· 取没有的 · 不在客栈 ⇒ 明说且**不动档**",
        not [x for x in _BAD12 if x[0].startswith(("存放", "取出", "存 ", "不在客栈"))],
        "%s" % [x for x in _BAD12 if x[0].startswith(("存放", "取出", "存 ", "不在客栈"))][:3])

    # ── 成就：档上那几本账现读（不新建容器）────────────────────────────
    _rec6 = _sv12()
    _sh6 = _CQ12._shadow(CA9._p(dict(_rec6)))
    _w6 = [_r("SYS_ACH_HEAD"),
           _r("SYS_ACH_ROW", name=str(_decl_usage("titles")), n=_TT12.count(_sh6),
              total=_TT12.total()),
           _r("SYS_ACH_ROW", name=str(_decl_usage("eggs")), n=_EG12.count(_sh6),
              total=_EG12.total())]
    for _bk in _CX12.BOOKS:
        _n6 = _CX12.count(_sh6, _bk)
        _t6 = int((_CX12.targets() or {}).get(_bk) or 0)
        _w6.append(_r("SYS_ACH_ROW", name=_CX12.label(_bk), n=_n6, total=_t6) if _t6 > 0
                   else _r("SYS_ACH_ROW_OPEN", name=_CX12.label(_bk), n=_n6))
    _w6 += [_r("SYS_ACH_QUEST", n=len(_CQ12._done(_sh6))), _r("SYS_ACH_TAIL")]
    _g6 = _say12("成就")
    _before6 = dict(_rec6)
    if _g6 != _w6 or _sv12() != _before6:
        _BAD12.append(("成就", _g6, _w6))
    chk("★ `成就` 真敲：称号 / 彩蛋 / 四本谱 / 交付 逐字对账（记满条数取自 `codex.targets`，"
        "不设记满的那本换一条行）且**看一眼成就 ≠ 往档里塞空容器**",
        not [x for x in _BAD12 if x[0] == "成就"],
        "%s" % [x for x in _BAD12 if x[0] == "成就"][:2])

    # ── ★ P-34：加点（真敲各档 + 逐字对账 + 余额对得上 + 失败不动档）───────────────
    #   口径：`content/alloc.py` 一个口（总点数 = 8 + 3×(级−1) · 余额 = 总点数 − 已花）；
    #   甲案（玩家自己加点，不自动平铺）⇒ 点数不是"发出来的"，是**按等级派生**的。
    from content import alloc as _AL13                                     # noqa: E402

    _lv13 = int(_sv12().get("level") or 1)
    _tot13 = _AL13.total_points(_lv13)

    def _ok13(stat, n, now, left):
        return [_r("SYS_ALLOC_OK", stat=_r("SYS_STAT_%s" % stat), n=n, now=now, left=left)]

    def _alloc13():
        return (_sv12().get("alloc") or {})

    _g13a = _say12("加点 力量 3")
    if _g13a != _ok13("STR", 3, 3, _tot13 - 3) or _alloc13() != {"STR": 3}:
        _BAD12.append(("加点 力量 3", _g13a, _alloc13()))
    _g13b = _say12("加点 STR 2")
    if _g13b != _ok13("STR", 2, 5, _tot13 - 5) or _alloc13() != {"STR": 5}:
        _BAD12.append(("加点 STR 2（ASCII 也认）", _g13b, _alloc13()))
    _asks = [("加点 运气 1", _r("SYS_ALLOC_BAD_STAT", want="运气", list=_statlist13()),
              "认不出的维"),
             ("加点 力量 0", _r("SYS_ALLOC_BAD_NUM", want="0"), "次数 0"),
             ("加点 力量 1 2", _r("SYS_ALLOC_BAD_NUM", want="1 2"), "次数写了两个"),
             ("加点 体质 99", _r("SYS_ALLOC_SHORT", stat=_r("SYS_STAT_VIT"), n=99,
                                left=_tot13 - 5, usage=_decl_usage_full("alloc")), "超余额")]
    for _t13, _w13, _why13 in _asks:
        _before13 = dict(_alloc13())
        _got13 = _say12(_t13)
        if _got13 != [_w13] or _alloc13() != _before13:
            _BAD12.append(("加点 %s" % _why13, _got13, _w13, _alloc13()))
    _g13c = _say12("加点")
    _w13c = [_r("SYS_ALLOC_ASK", usage=_decl_usage_full("alloc"), left=_tot13 - 5,
                list=_statlist13()),
             _r("SYS_ALLOC_SUGGEST", total=_tot13,
                list=" · ".join("%s %d" % (_r("SYS_STAT_%s" % _s), _n)
                                for _s, _n in _AL13.plan(_lv13, "cls_knight").items() if _n))]
    if _g13c != _w13c or _alloc13() != {"STR": 5}:
        _BAD12.append(("加点（不带参数）", _g13c, _w13c, _alloc13()))
    _g13d = _say12("加点 意志 %d" % (_tot13 - 5))
    if _g13d != _ok13("WIL", _tot13 - 5, _tot13 - 5, 0) or _AL13.left_of_record(_sv12()) != 0 \
            or _AL13.spent_of_record(_sv12()) != _tot13:
        _BAD12.append(("加点（投满）", _g13d, _alloc13(), _AL13.left_of_record(_sv12())))
    _g13e = _say12("加点")
    if _g13e != [_r("SYS_ALLOC_DONE", total=_tot13)]:
        _BAD12.append(("加点（投满了）", _g13e))
    _g13f = _say12("加点 力量 1")
    if _g13f != [_r("SYS_ALLOC_SHORT", stat=_r("SYS_STAT_STR"), n=1, left=0,
                    usage=_decl_usage_full("alloc"))]:
        _BAD12.append(("加点（余额 0 还想加）", _g13f))
    chk("★ P-34 `加点` 真敲 11 档：中文名 / ASCII 都认 · 逐字对账 · **余额对得上**"
        "（总点数 %d = 8 + 3×(级−1)）· 超余额 / 认不出的维 / 次数不是正整数 各回一行且**不动档**"
        " · 投满 ⇒ `DONE`" % _tot13,
        not [x for x in _BAD12 if str(x[0]).startswith("加点")],
        "%s" % [x for x in _BAD12 if str(x[0]).startswith("加点")][:2])

    # ── ★ P-34：档上那格坏掉 ⇒ 点名（fail-closed），不"当作没投过"接着加 ─────────
    _bad13 = _Ad([], seed=dict(_SEED12, level=1, alloc={"STR": 99}))
    _db13 = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_cmds_alloc.db")
    try:
        os.remove(_db13)
    except OSError:
        pass
    _h13 = Host(_bad13, str(REPO), inject={"db_path": _db13, "clock": time.time})
    _h13.boot()
    _bad13.out.clear()
    _h13.handle({"uid": "u_c", "group_id": "g_c", "text": "加点"})
    _g13g = list(_bad13.out)
    chk("★ P-34 档上 `alloc` 坏了（投了 99 点 / 1 级只有 8 点）⇒ 点名一行、**不动档**"
        "（不静默当没投过）",
        len(_g13g) == 1 and _g13g[0].startswith(str(TX["SYS_ALLOC_BAD_SAVE"]["value"]).split("{")[0])
        and (_bad13.saved or {}).get("alloc") == {"STR": 99},
        "%s / %s" % (_g13g, (_bad13.saved or {}).get("alloc")))

    # ── 收口三扫：不是 soon 句 · 不漏机器键 · 不缺文案 ────────────────────
    _all12 = [ln for _t, _o in _said12 for ln in _o] + _gS3 + _gAway
    chk("★ 这 8 条一条都不再回「还没接上」那一句",
        not [k for k in NEW12 for ln in _all12 if soon_text(k) in ln],
        "%s" % [k for k in NEW12 for ln in _all12 if soon_text(k) in ln][:3])
    _KEYS12 = [k for d in ("items", "monsters", "pois", "classes", "races", "quests",
                           "gathering", "drop_pools", "recipes", "npcs", "skills", "eggs",
                           "titles", "dialogues")
               for k in (st.domain(d) or {})]
    _leak12 = [ln[:38] for ln in _all12
               if any(kk in ln for kk in _KEYS12) or "[MISSING TEXT" in ln]
    chk("★ 这 8 条的回话里没有域 id、也没有取不到文案（%d 行逐行扫）" % len(_all12),
        not _leak12, "%s" % _leak12[:3])
except Exception as exc:                                              # noqa: BLE001
    chk("★ B3-12 那 8 条真敲跑得起来（真宿主契约）", False,
        "%s: %s" % (type(exc).__name__, exc))

print("⑬ ★ B3-16b（真宿主）：这一批新接的 9 条真敲 —— 逐字对槽位 · 档上副作用对 · 不再回「还没接上」")
#: 本批接下处理器的 9 条（镇上那几处 + 公会那三件 + 名与榜 + 公告）
NEW16 = ("chapel", "inn", "caravan", "junk_shop", "register", "rank", "rename", "ranking", "notice")
try:
    from content import calendar as CAL16                                 # noqa: E402
    from content import cmds_places as CPL16                              # noqa: E402
    from content import cmds_quest as CQ16                                # noqa: E402
    from content import codex as CX16                                     # noqa: E402
    from content import loot as LT16                                      # noqa: E402
    from content import persistence as PS16                               # noqa: E402

    chk("★ 这一批 %d 条都挂了 bind（%s）" % (len(NEW16), " · ".join(NEW16)),
        not [k for k in NEW16 if not (DECL.get(k) or {}).get("bind")],
        "%s" % [k for k in NEW16 if not (DECL.get(k) or {}).get("bind")])
    chk("★ 「声明了、可见、还没实现」25 → %d 条（%s）" % (len(UNBOUND), " · ".join(sorted(UNBOUND))),
        len(UNBOUND) == UNBOUND_MAX, "%s" % sorted(UNBOUND))

    _NP16 = st.domain("npcs") or {}
    _GUILD_NODE16 = ""
    _CHAPEL_NODE16 = ""
    for _k16, _v16 in _NP16.items():
        if not isinstance(_v16, dict) or _v16.get("map") != "windmill_town":
            continue
        if "board" in (_v16.get("funcs") or []):
            _GUILD_NODE16 = str(_v16.get("subarea") or "")
        if "heal" in (_v16.get("funcs") or []):
            _CHAPEL_NODE16 = str(_v16.get("subarea") or "")

    def _nname16(node):
        return CA9._name_of_node("windmill_town", node)

    _INN_NODE16 = CPL16.STASH_NODE

    _SEED16 = {"cls": "cls_knight", "race": "human", "level": 3, "exp": 0, "hp": 20, "gold": 30,
               "loc": "windmill_town", "node": "wt_gate_n", "prev": [],
               "bag": {"i_junk_bone": 3, "i_material_iron_scrap": 2}, "equipped": {},
               "codex": {}, "flags": {}}

    def _roster16(node, p):
        """这一站现在有谁（走 `_npcs_here` 那一个读口现算 —— 不手写镜像串）。"""
        rows = [v for _k, v in CA9._npcs_here("windmill_town", node, p=p)]
        return rows, " · ".join("『%s』%s" % (v.get("name"), v.get("icon", "")) for v in rows)

    _db16 = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_cmds_b316.db")
    try:
        os.remove(_db16)
    except OSError:
        pass
    _ad16 = _Ad([], seed=dict(_SEED16))
    _h16 = Host(_ad16, str(REPO), inject={"db_path": _db16, "clock": time.time})
    _h16.boot()
    _said16 = []
    _BAD16 = []

    def _say16(text):
        _ad16.out.clear()
        _h16.handle({"uid": "u_c", "group_id": "g_c", "text": text})
        _said16.append((text, list(_ad16.out)))
        return list(_ad16.out)

    def _cmp16(label, got, want):
        if got != want:
            _BAD16.append((label, got, want))

    def _sv16():
        return _ad16.saved or {}

    _cap16 = int(PB.hp_cap(CA9._p(dict(_sv16()))))

    # ── 教堂：镇上（没走到那一站）→ 站到了治疗（血回满）· 野外那一档 ────────
    _cmp16("教堂（人在北口）", _say16("教堂"), [_r("SYS_PLACE_AWAY", name=_nname16(_CHAPEL_NODE16))])
    _ad16.saved["loc"] = "belt_north"
    _ad16.saved["node"] = "bn_bone"
    _cmp16("教堂（人在野外）", _say16("教堂"), [_r("SYS_PLACE_NOTOWN")])
    _ad16.saved["loc"] = "windmill_town"
    _ad16.saved["node"] = "wt_gate_n"
    _say16("去 %s" % _nname16(_CHAPEL_NODE16))
    _rowsC16, _lineC16 = _roster16(_CHAPEL_NODE16, _sv16())
    _whoC16 = next((str(v.get("name")) for v in _rowsC16 if "heal" in (v.get("funcs") or [])), "")
    _cmp16("教堂（站到了 · 治疗）", _say16("教堂"),
           [_r("SYS_PLACE_HEAD", name=_nname16(_CHAPEL_NODE16)),
            _r("SYS_LOOK_WHO", list=_lineC16),
            _r("SYS_CHAPEL_HEAL", who=_whoC16),
            _r("SYS_REST_HEAL", add=_cap16 - 20, hp=_cap16, max=_cap16),
            _r("SYS_TALK_HOW", name=_whoC16)])
    _cmp16("教堂（身上没伤）", _say16("教堂"),
           [_r("SYS_PLACE_HEAD", name=_nname16(_CHAPEL_NODE16)),
            _r("SYS_LOOK_WHO", list=_lineC16),
            _r("SYS_CHAPEL_FULL", who=_whoC16),
            _r("SYS_TALK_HOW", name=_whoC16)])
    chk("★ `教堂` 真敲四档：野外 / 镇上没走到那一站 / 站到了治疗（上限走唯一来源 `hp_cap`）/ "
        "没伤那一档 —— 整段与 npcs + maps + texts 现算的期望逐字一致",
        not [x for x in _BAD16 if x[0].startswith("教堂")] and int(_sv16().get("hp") or 0) == _cap16,
        "%s（hp=%s/%s）" % ([x for x in _BAD16 if x[0].startswith("教堂")][:1],
                            _sv16().get("hp"), _cap16))

    # ── 客栈：那一站 = 箱子那一站（同一个节点）· 住店回满 · 箱子那两句 ──────
    _cmp16("客栈（人在白烛堂）", _say16("客栈"), [_r("SYS_PLACE_AWAY", name=_nname16(_INN_NODE16))])
    _say16("去 %s" % _nname16(_INN_NODE16))
    _rowsI16, _lineI16 = _roster16(_INN_NODE16, _sv16())
    _whoI16 = str((_rowsI16[0].get("name") if _rowsI16 else ""))
    _cmp16("客栈（不疼也不困）", _say16("客栈"),
           [_r("SYS_PLACE_HEAD", name=_nname16(_INN_NODE16)), _r("SYS_LOOK_WHO", list=_lineI16),
            _r("SYS_INN_FULL"), _r("SYS_INN_BOX"), _r("SYS_TALK_HOW", name=_whoI16)])
    _ad16.saved["hp"] = 20                              # 造一个带伤的档（真敲读回）
    _cmp16("客栈（住店）", _say16("客栈"),
           [_r("SYS_PLACE_HEAD", name=_nname16(_INN_NODE16)), _r("SYS_LOOK_WHO", list=_lineI16),
            _r("SYS_INN_SLEEP"), _r("SYS_REST_HEAL", add=_cap16 - 20, hp=_cap16, max=_cap16),
            _r("SYS_INN_BOX"), _r("SYS_TALK_HOW", name=_whoI16)])
    chk("★ `客栈` 真敲三档：指路 / 不用住店 / 住店睡得血回满 —— 且那一站与『存放』认的是同一个节点"
        "（`cmds_more.STASH_NODE`，一处只写一份）",
        not [x for x in _BAD16 if x[0].startswith("客栈")] and int(_sv16().get("hp") or 0) == _cap16
        and _INN_NODE16 == _CM12.STASH_NODE,
        "%s（hp=%s/%s · 客栈站=%s）" % ([x for x in _BAD16 if x[0].startswith("客栈")][:1],
                                        _sv16().get("hp"), _cap16, _INN_NODE16))

    # ── 旧货：收什么 = 域里有价的那些（逐件对账）· 看一眼 ≠ 动档 ────────────
    def _junk_want16(p):
        rows = []
        for iid in sorted(p.get("bag") or {}):
            rec = LT16.rec_of(iid)
            price = rec.get("price")
            if not isinstance(price, (int, float)) or isinstance(price, bool) or price <= 0:
                continue
            n = int((p.get("bag") or {}).get(iid) or 0)
            rows.append((str(rec.get("name") or iid), n, int(price) * n))
        out = [_r("SYS_JUNK_HEAD")]
        if rows:
            out.append(_r("SYS_JUNK_MINE"))
            out += [_r("SYS_JUNK_ROW", name=nm, n=n, gold=g) for nm, n, g in sorted(rows)]
        else:
            out.append(_r("SYS_JUNK_NONE"))
        out.append(_r("SYS_JUNK_RELIC",
                      n=CX16.count(CQ16._shadow(CA9._p(dict(p))), "relic")))
        out.append(_r("SYS_JUNK_HOW"))
        return out

    _bag16 = dict(_sv16().get("bag") or {})
    _snap16 = dict(_sv16())
    _cmp16("旧货（包里有东西）", _say16("旧货"), _junk_want16(_sv16()))
    _ad16.saved["bag"] = {}
    _cmp16("旧货（包里空的）", _say16("旧货"), _junk_want16(_sv16()))
    _ad16.saved["bag"] = _bag16
    chk("★ `旧货` 真敲两档（有东西 / 空的）：逐件与 `items.price` 现算的期望逐字一致，"
        "且**看一眼旧货铺不动档**（bag / flags 原样）",
        not [x for x in _BAD16 if x[0].startswith("旧货")]
        and (_sv16().get("bag") or {}) == (_snap16.get("bag") or {}),
        "%s" % [x for x in _BAD16 if x[0].startswith("旧货")][:2])

    # ── 商队：今天开着的世界级镇上事件 + 跟车来的人此刻在哪一站（两档）──────
    def _caravan_want16(p):
        st16 = CAL16.state()
        out = [_r("SYS_CARAVAN_HEAD")]
        news = [r for r in CAL16.events_now(st16, p)
                if str(r.get("scale_key")) == "world" and CAL16.where_hit(r, "windmill_town")]
        out += [_r(str(r["text"])) for r in news if r.get("text")]
        if not news:
            out.append(_r("SYS_CARAVAN_QUIET"))
        who = []
        for nd in ((st.domain("maps") or {}).get("windmill_town") or {}).get("nodes") or []:
            nid = str(nd.get("id") or "")
            for _kk, vv in CA9._npcs_here("windmill_town", nid, st16, p):
                if not ((vv.get("condition") or {}).get("event")):
                    continue
                who.append("%s（%s）" % (vv.get("name"), _nname16(nid)))
        if who:
            out += [_r("SYS_CARAVAN_WHO", list=" · ".join(who)), _r("SYS_CARAVAN_HOW")]
        return out

    _on16 = _say16("商队")
    _cmp16("商队（车还在路上）", _on16, _caravan_want16(_sv16()))
    _ad16.saved["flags"] = dict(_sv16().get("flags") or {}, quests_done=["q_main_03"])
    _arr16 = _say16("商队")
    _cmp16("商队（车到了）", _arr16, _caravan_want16(_sv16()))
    _who_line16 = [ln for ln in _arr16 if "（" in ln and "搭话" not in ln and "歇脚处" not in ln]
    chk("★ `商队` 真敲两档（车在路上 / 车到了）：动静取自 `events` 域那两条的槽位、"
        "「外人在哪一站」逐条现算（走 `_npcs_here` 那一口）—— 车到了那档**真多出**"
        "外人与细问那两行（不是同一段话念两遍）",
        not [x for x in _BAD16 if x[0].startswith("商队")]
        and bool(_who_line16) and _arr16 != _on16,
        "%s（%s）" % ([x for x in _BAD16 if x[0].startswith("商队")][:2], _who_line16[:1]))

    # ── 登记 / 改名 / 评级：在公会那一站 · 先要名字 · 证与进度 ──────────────
    _cmp16("登记（人在客栈）", _say16("登记"), [_r("SYS_PLACE_AWAY", name=_nname16(_GUILD_NODE16))])
    _say16("去 %s" % _nname16(_GUILD_NODE16))
    _cmp16("登记（档上还没名字）", _say16("登记"), [_r("SYS_REG_ASKNAME")])
    _cmp16("改名（没带名字）", _say16("改名"), [_r("SYS_RENAME_ASK")])
    _cmp16("改名（第一次）", _say16("改名 张三"), [_r("SYS_RENAME_DONE", name="张三")])
    _ren16 = (_sv16().get("flags") or {}).get("renamed")
    _cmp16("改名（只许一次）", _say16("改名 李四"), [_r("SYS_RENAME_USED")])
    _cmp16("登记（办下来）", _say16("登记"), [_r("SYS_REG_DONE")])
    _card16 = (_sv16().get("flags") or {}).get("card")
    _cmp16("登记（已经有证）", _say16("登记"), [_r("SYS_REG_HAS")])
    #: 「刚办证」那一档的已交条数**现读**（前面几档动过 `flags.quests_done` —— 期望值跟着档走）
    _cnt16 = len(((_sv16().get("flags") or {}).get("quests_done") or []))
    _cmp16("评级（刚办证）", _say16("评级"),
           [_r("SYS_MINE_RANK"), _r("SYS_MINE_DONE", n=_cnt16), _r("SYS_RANK_CHIEF", n=0)])
    _ad16.saved["flags"] = dict(_sv16().get("flags") or {},
                               quests_done=["q_main_01", "q_main_02", "q_main_03"])
    _chief16 = next((m for m, v in (st.domain("monsters") or {}).items()
                     if v.get("role_key") == "chief" and m in CX16.book("monster")), "")
    _ad16.saved["books"] = {"monster": {_chief16: {"day": 1, "kills": 2}}}
    _cmp16("评级（有进度）", _say16("评级"),
           [_r("SYS_MINE_RANK"), _r("SYS_MINE_DONE", n=3), _r("SYS_RANK_CHIEF", n=1)])
    chk("★ `登记 / 改名 / 评级` 真敲：改名的名字与 `flags.renamed` 落档 · 证只在**办下来**那一下写 "
        "`flags.card` · 评级逐字对槽位（已交条数取自 `flags.quests_done`、头目数按域里 "
        "`role_key == chief` 数）· 没带名字时登记不替玩家编一个",
        not [x for x in _BAD16 if x[0].startswith(("登记", "改名", "评级"))]
        and _sv16().get("name") == "张三" and _ren16 is not None and _card16 is not None
        and _chief16 != "",
        "%s（name=%s renamed=%s card=%s）" % (
            [x for x in _BAD16 if x[0].startswith(("登记", "改名", "评级"))][:2],
            _sv16().get("name"), _ren16, _card16))

    # ── 排行：本群榜（库里那两位 + 手上这一份）· 看一眼 ≠ 动档 ─────────────
    _snapP16 = dict(_sv16())
    PS16.update_player("g_c", "u_x", name="乙", level=5, exp=10)
    PS16.update_player("g_c", "u_y", name="丙", level=5, exp=99)
    _cmp16("排行（本群三个人）", _say16("排行"),
           [_r("SYS_RANKING_HEAD"),
            _r("SYS_RANKING_ROW", i=1, name="丙", level=5, exp=99),
            _r("SYS_RANKING_ROW", i=2, name="乙", level=5, exp=10),
            _r("SYS_RANKING_ROW", i=3, name="张三", level=3, exp=0),
            _r("SYS_RANKING_TAIL")])
    _rank_db16 = sorted((r["uid"], (r["data"] or {}).get("name"))
                        for r in PS16.all_players("g_c"))
    chk("★ `排行` 真敲：榜 = **本群**存档里那些定下名字的人（`persistence.all_players` 现读 · "
        "按等级/经验排）· 自己那一行一定在（库里没有就拿手上这份档补上）· 看一眼排行**不动档**",
        not [x for x in _BAD16 if x[0].startswith("排行")]
        and sorted(u for u, _n in _rank_db16) == ["u_x", "u_y"]
        and dict(_sv16()) == _snapP16,
        "%s（库里=%s）" % ([x for x in _BAD16 if x[0].startswith("排行")][:1], _rank_db16))

    # ── 公告：包名 / 版本 / 已接条数（现点声明表）────────────────────────
    _mf16 = json.loads((Path(str(REPO)) / "game.json").read_text(encoding="utf-8"))
    _nb16 = len([1 for v in DECL.values() if (v or {}).get("bind")])
    _cmp16("公告", _say16("公告"),
           [_r("SYS_NOTICE_HEAD"),
            _r("SYS_NOTICE_PKG", name=_mf16.get("name") or "", ver=_mf16.get("version") or ""),
            _r("SYS_NOTICE_CMDS", n=_nb16, total=len(DECL)),
            _r("SYS_NOTICE_TAIL")])
    chk("★ `公告` 真敲：包名 / 版本取自 `game.json`、已接条数**现点**声明表里真有 `bind` 的那几条"
        "（与『帮助』同一批口径）",
        not [x for x in _BAD16 if x[0].startswith("公告")],
        "%s" % [x for x in _BAD16 if x[0].startswith("公告")][:2])

    # ── 收口三扫：不是 soon 句 · 不漏机器键 · 不缺文案 ────────────────────
    _all16 = [ln for _t, _o in _said16 for ln in _o]
    _soon16 = [k for k in NEW16 for ln in _all16 if soon_text(k) in ln]
    chk("★ 这 9 条一条都不再回「还没接上」那一句", not _soon16, "%s" % _soon16[:3])
    _KEYS16 = [k for d in ("items", "monsters", "pois", "classes", "races", "quests", "gathering",
                           "drop_pools", "recipes", "npcs", "skills", "eggs", "titles", "dialogues")
               for k in (st.domain(d) or {})]
    _leak16 = [ln[:40] for ln in _all16
               if any(kk in ln for kk in _KEYS16) or "[MISSING TEXT" in ln]
    chk("★ 这 9 条的回话里没有域 id、也没有取不到文案（%d 行逐行扫）" % len(_all16),
        not _leak16, "%s" % _leak16[:3])
except Exception as exc:                                              # noqa: BLE001
    chk("★ B3-16b 那 9 条真敲跑得起来（真宿主契约）", False,
        "%s: %s" % (type(exc).__name__, exc))

print("")
print("结果：全绿 ✓" if ok else "结果：有红 ✗")
sys.exit(0 if ok else 1)
