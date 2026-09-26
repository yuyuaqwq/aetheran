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
  ⑰ ★ B4-12（真敲三档 + 静态）：**地点守卫一个口** —— `guard_desc` 写着「在镇上 / 在公会 /
     在铺子 / 在客栈」那一族：野外一条都不许放行（各自只回自己那一句）· 镇上没走到那一站
     一律**指路**（站名从 `maps` 现取）· 站到了放行；覆盖面两条：handler 必须**真调**
     `town_gate`（ast 扫真调用）· 镇子 id 的字面量只许一处

  ⑳ ★ B4-21（真敲 + 真源现算）：`属性` 那一页的两个**非线性**的数 —— 「暴击率」那一格 =
     宪法 F3 现算（六职业各不相同、都不是 0、换 crit 装跟着涨）· 二级属性里「闪避」那一行
     真在且 = 宪法数值现算（换 eva 装跟着涨）；静态守卫：`cmds_more` 不再自己钻面板栈

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
# ★ F6（QA P4 E-7）：`看` 这个单字别名原先**同时**挂在观察（§一）与查看（§四）上，
#   裸 `看` 走的是 §一那一支（= 一整段场景描写）⇒ 玩家敲「看」看不出自己少写了参数，
#   而 `看 abc` 又悄悄当成「查看」回「背包里没有…」。本批收敛成：**裸 `看` 归查看**
#   （照 §〇⑥「单字只做别名」+ §四 `查看 <物品>`（别名 看）），`看 <编号>` 照 §二 归委托。
#   ⇒ 工作树 `_notes.md` §F6 记着「真源 §一 那一行的 `看` 待摘」（真源仓单写，本分支只改包）。
DOC = (
    ("§一 移动与世界", (
        ("进镇", "enter_town"), ("风车镇", "enter_town"), ("回镇", "enter_town"),
        # ★ fix5-nav：`北口` 归**站点名**那一族（= 『去 北口』）—— 拍定口径「站名归站点」，
        #   出镇口令 = `往北` / `出北门`（真源 04 §一 那一行的后两个词照旧）。见 probe_nav ①。
        ("北口", "go_to"), ("往北", "go_north"), ("出北门", "go_north"),
        ("往东", "go_east"), ("东边", "go_east"),
        ("往西", "go_west"), ("西边", "go_west"),
        ("返回", "go_back"), ("回", "go_back"), ("退回去", "go_back"),
        ("地图", "map"), ("m", "map"),
        ("观察", "look"), ("看四周", "look"),
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
        ("我是 人类", "be_race"), ("选族 精灵", "be_race"),
        ("选职业 骑士", "be_class"), ("选职业", "be_class"), ("职业", "be_class"),
    )),


    ("§四 背包与物品", (
        ("背包", "bag"), ("包", "bag"), ("包裹", "bag"), ("inv", "bag"),
        ("查看 伤药", "item_show"),
        ("看", "item_show"),                     # ★ F6：裸 `看` 收敛到「查看」
        ("看 伤药", "item_show"),                #   与 `^看\s*(.+)$` 同一个口
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
        # ★ B4-17：04 §十 新添的两行（长列表分页）—— 触发词照样逐条 first_hit
        ("下一页", "page_next"), ("下页", "page_next"), ("翻页", "page_next"),
        ("回 2", "page_back"),
        ("搭话", "talk"), ("搭话 玛莎", "talk"), ("说话 玛莎", "talk"), ("聊 玛莎", "talk"),
        ("去 北口", "go_to"), ("走到 北口", "go_to"), ("前往 北口", "go_to"),
        ("烹饪 烤石斑", "cook"), ("做 烤石斑", "cook"), ("煮 烤石斑", "cook"),
        ("配方", "recipes"), ("菜谱", "recipes"), ("配方一览", "recipes"),
        ("彩蛋", "eggs"), ("连起来", "eggs"),
    )),
)


print("探针：指令路由（第 23 个 · B3-14 触发词撞车 · P-23 只列有处理器的指令）")
#: ★ 探针的时钟**钉死**：早先这里写的是 `time.time` ⇒ 换个时刻跑，天气/日期相关的遭遇就会变，
#:   门禁跟着绿红跳（同一天上午绿、下午红）。口径与 `probe_weather` 一致：`clock` 注入一个常量。
_FIXED = 1790308800          # 2026-09-25 12:00 +08:00

st = load_stack(str(REPO), inject={
    "db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_cmds.db"),
    "clock": lambda: _FIXED})
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
from content import loot as LPICK                       # noqa: E402  ★ B4-20 显示名那唯一的一口

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
    _host = Host(_ad, str(REPO), inject={"db_path": _db, "clock": lambda: _FIXED})
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
from content import shop as _SH15                                     # noqa: E402
chk("★ `买药` 归 herbalist（改前被 item_buy 吃掉）—— ★ B4-15 把 `药铺` 接上实现体之后，"
    "这条改成更硬的写法：回的是**药铺面板**那一行（站名从 maps 现取），不再是 soon 兜底句",
    _first("买药") == (TX.get("SYS_SHOP_HEAD") or {}).get("value", "").replace("{name}", _SH15.station_name())
    and _first("买药") != soon_text("herbalist"), _first("买药"))
chk("★ 裸 `放弃` 不许命中 skill_cast（改前回「放技能 ／ 技能 <参数>」）",
    bool(lines.get("放弃")) and not any(x.startswith("【skill_cast】") for x in (lines.get("放弃") or [])),
    lines.get("放弃"))
chk("★ 裸 `放弃` 不许动档（quest_abandon 空参会取 act[0]，静默丢第一条委托）",
    ((saved.get("flags") or {}).get("quests_active") or []) == ["q_main_01"],
    (saved.get("flags") or {}).get("quests_active"))
chk("★ `技能 挥击` 仍归 skill_cast（主词与双字别名没被改坏）—— ★ B3-23 接上实现体之后"
    "这条改成更硬的写法：回的是实现体那句真话（无职业档 = 「%s」），不再是 soon 兜底句"
    % (TX.get("SYS_SKILL_NOCLS") or {}).get("value", ""),
    _first("技能 挥击") == (TX.get("SYS_SKILL_NOCLS") or {}).get("value", "")
    and _first("技能 挥击") != soon_text("skill_cast"),
    _first("技能 挥击"))

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
#:   ★ B3-23（战斗那六条）接下 打断 / 后撤 / 放技能 / 战斗中用物 / 集火 / 换武器 六条 ⇒ **15 → 10**。
#:     注意 `battle_item` 是 `visible: false`（它的触发词与 item_use 逐字相同、路由归 item_use，
#:     见 ③）⇒ 它本来就不在这一格里；这一批**能数进这一格的是 5 条**，第 6 条（battle_item）
#:     在同一批里真接了实现体、走 ⑭ 那条真调判据。
#:   ★ B3-25（组队那一条）接下 `party`（队伍/组队）与 `party_leave`（离队）⇒ **10 → 8**。
#:     同一批里 `party_invite`（本批从 invisible 开成可见）与**新加的** `party_accept`（同意）
#:     一落就带 bind ⇒ 两条都不进这一格（它们走 probe_party 的真敲判据）。
#:   ★ B4-15（药铺那一条）接下 `herbalist`（药铺）与 `item_buy`（购买）⇒ **8 → 6**。
#:   ★ B4-16（公会评级那一条）接下 `rank_up`（升级证 / 换证）⇒ **6 → 5**。
#:     余下 5 条：climb（攀爬）· sneak（潜行）· feedback · settings · battle_pref。
UNBOUND_MAX = 5

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
    # ★ QB-6（本波 fix1-quests · 试玩报告 P2 BUG⑨）：这一条原先钉的是「点错名 ⇒ 回
    #   `SYS_READ_NONE`（这里没有能读的东西）」。报告实测：站在**有两件可读物**的骨田敲
    #   `读 不存在的东西`，玩家照这句会以为「这站本来就没东西」，转身走掉。
    #   ⇒ 判据**换锚不降强度**（P-31 换锚④那一族的做法）：点错名时
    #     ① 不许给任何一件的正文（原来那条「不塞东西」照钉）
    #     ② 必须点名说对不上（`SYS_READ_NOSUCH` · 填进玩家敲的那个名字）
    #     ③ 必须把这站**现在真能读的**列出来（`SYS_READ_HERE` · 名字从 pois 域现取）
    #     ④ **不许**再回那句「这里没有能读的东西」—— 那句只留给「这站真没有可读物」（两态里的另一态，
    #        判据在 scripts/probe_qloop.py ⑤）。
    _ad.saved = dict(_ad.saved or {}, loc="windmill_town", node="wt_gate_n")
    _ad.out.clear()
    _host.handle({"uid": "u_c", "group_id": "g_c", "text": "读 这儿没有的东西"})
    _got = list(_ad.out)
    _none = (TX.get("SYS_READ_NONE") or {}).get("value", "")
    _nosuch = (TX.get("SYS_READ_NOSUCH") or {}).get("value", "").replace("{name}", "这儿没有的东西")
    _po = st.domain("pois") or {}
    _here_names = [v.get("name") for v in _po.values()
                   if v.get("map") == "windmill_town" and v.get("subarea") == "wt_gate_n"
                   and v.get("read_text") and v.get("name")]
    _here = (TX.get("SYS_READ_HERE") or {}).get("value", "").replace("{list}", " · ".join(_here_names))
    _any_body = [k for v in _po.values() if v.get("read_text")
                 for k in [(TX.get(str(v.get("read_text"))) or {}).get("value", "")]
                 if k and k in _got]
    _read_bad2 = []
    if _any_body:
        _read_bad2.append("点错名却给了某一件的正文")
    if _nosuch not in _got:
        _read_bad2.append("没点名说对不上（该有「%s」）" % _nosuch)
    if _here not in _got:
        _read_bad2.append("没把这站能读的列出来（该有「%s」）" % _here)
    if _none and _none in _got:
        _read_bad2.append("又回了那句「%s」（玩家会以为这站本来就没东西）" % _none)
    chk("★ 点错名不塞东西（换锚不降强度 · QB-6）：「%s」+「%s」· 一件正文都不给 · "
        "不糊「%s」" % (_nosuch, _here, _none), not _read_bad2, "%s" % (_read_bad2 or _got[:3]))
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
    _host2 = Host(_ad2, str(REPO), inject={"db_path": _db2, "clock": lambda: _FIXED})
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
    #: ★ B4-1：这个档是 **3 级**，所以「已会」= lv<=3 的那几条、「还没到等级」= 11/14/16 那几条。
    #:   判据从「域里全部」改成**按等级现算**（`_of_class` 就是实现体读的那一口，不另写镜像）。
    #: （这一节在 ⑩ 之前，`CSK` 还没 import ⇒ 就地取一次，别依赖别处的绑定）
    from content import cmds_skill as _CSK9                              # noqa: E402
    _KNT9AV, _KNT9LK = _CSK9._of_class("cls_knight", 3)
    _KNT9N_AV = [v.get("name") for _k, v in _KNT9AV]
    _KNT9N_LK = [(v.get("name"), _l) for _k, v, _l in _KNT9LK]
    # ★ B3-19（本批加）：档上要**够门槛**才穿得上 —— 这两把都是精制武器（`req` = 力量 9 ·
    #   门槛级 7；值见 `scripts/rebuild_item_reqs.py`）⇒ 起手档给一个真会加点的档
    #   （3 级 = 14 点，力量 9 ≥ 9）。这不是放宽判据：是让 fixture 符合游戏规则
    #   （一个 0 加点的档本来就穿不上精制装备）。
    _ALLOC9 = {"STR": 9}
    _SEED9 = {"cls": "cls_knight", "race": "human", "level": 3, "hp": 100, "gold": 30,
              "alloc": dict(_ALLOC9),
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
    _host9 = Host(_ad9, str(REPO), inject={"db_path": _db9, "clock": lambda: _FIXED})
    _host9.boot()

    def _say9(text):
        _ad9.out.clear()
        _host9.handle({"uid": "u_c", "group_id": "g_c", "text": text})
        return list(_ad9.out)

    _bad9 = []
    _wear9 = _say9("装备 %s" % _W1N)
    if not _wear9 or _wear9[0] != _r("SYS_GEAR_EQUIP_OK", icon=_IT9[_W1].get("icon", ""),
                                     name=LPICK.label_of(_W1),
                                     kind=_IT9[_W1].get("kind", "")):
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
                                     known=len(_KNT9N_AV), locked=len(_KNT9N_LK)):
        _bad9.append(("技能 抬头", _list9[:1]))
    _miss9 = [n for n in _KNT9N_AV if not any(n in _ln for _ln in _list9)]
    #: ★ B4-1：没到等级的那几条也要**看得见**（19_ §五 的「玩家看得见再升几级会多出什么」）
    _miss9 += [(n, l) for n, l in _KNT9N_LK
               if not any(_r("SYS_SKILL_LOCKED", name=n, lv=l) in _ln for _ln in _list9)]
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
    _ad9b = _Ad([], seed={"cls": "cls_knight", "race": "human", "level": 3, "hp": 100,
                          "alloc": dict(_ALLOC9), "bag": {_W1: 1},
                          "equipped": {}, "codex": {}, "flags": {}})
    _host9b = Host(_ad9b, str(REPO), inject={"db_path": _db9b, "clock": lambda: _FIXED})
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
        and _eqB[:1] == [_r("SYS_GEAR_EQUIP_OK", icon=_IT9[_W1].get("icon", ""),
                            name=LPICK.label_of(_W1),
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
    #: ★ B4-1：等级段这一条**改成真账**（原先那句「今天没有 lv>1 的技能」是当时的现状描述，
    #:  B4-1 把 11–20 那 18 条补进来之后它必然翻红 —— 按新数据换成下面这套**更强**的判据：
    #:    ① 1 级解锁的那班 == 域里 lv<=1 的那些（不是"全部"了）
    #:    ② 到 20 级 ⇒ 本职业**满编**（7 主动 + 1 被动 = 8）
    #:    ③ 六职业合 48 条 · 每条都落在 [1, 20]
    _CLS10 = [c for c in sorted(_CL10) if not str(c).startswith("_")]
    _rows10 = {c: CSK._of_class(c, 1) for c in _CLS10}
    _tot10 = sum(len(a) for a, _l in _rows10.values())
    _lv1_10 = [1 for v in _SK10.values() if v.get("owner_class") and int(v.get("lv") or 1) <= 1]
    chk("★ 六职业 1 级解锁的技能：%s（合 %d 条 = 域里 lv<=1 的那些 %d 条）"
        % (" · ".join("%s %d" % (_CL10[c]["name"], len(a)) for c, (a, _l) in sorted(_rows10.items())),
           _tot10, len(_lv1_10)), _tot10 == len(_lv1_10), "%d vs %d" % (_tot10, len(_lv1_10)))
    _full10, _badfull10 = {}, []
    for c in _CLS10:
        _a20, _l20 = CSK._of_class(c, 20)
        _full10[c] = (len(_a20), len(_l20))
        if _l20:
            _badfull10.append((c, "%d 条到 20 级还没解锁" % len(_l20)))
    _owned10 = [v for v in _SK10.values() if v.get("owner_class")]
    _act10 = [v for v in _owned10 if v.get("kind_key") == "active"]
    _pas10 = [v for v in _owned10 if v.get("kind_key") == "passive"]
    _bad_band10 = [(k, v.get("lv")) for k, v in _SK10.items()
                   if v.get("owner_class") and not (1 <= int(v.get("lv") or 0) <= 20)]
    chk("★ ★ B4-1：六职业到 20 级**满编** —— %s（每条 = 7 主动 + 1 被动；域里合 %d 条 = "
        "%d 主动 + %d 被动）"
        % (" · ".join("%s %d+%d" % (_CL10[c]["name"], _full10[c][0] - 1, 1) for c in _CLS10),
           len(_owned10), len(_act10), len(_pas10)),
        all(v == (8, 0) for v in _full10.values()) and len(_owned10) == 48
        and len(_act10) == 42 and len(_pas10) == 6 and not _bad_band10,
        "%s / %s" % (_badfull10 or _full10, _bad_band10[:3]))
    _hi10 = sorted((k, v.get("lv")) for k, v in _SK10.items()
                   if v.get("owner_class") and int(v.get("lv") or 1) > 1)
    chk("★ ★ B4-1：11–20 段那 %d 条**真带解锁等级**（lv 取值 %s）—— 它们靠 `skills.lv` "
        "逐级放行，不手写门槛"
        % (len(_hi10), " / ".join(str(x) for x in sorted({l for _k, l in _hi10}))),
        len(_hi10) == 18 and sorted({l for _k, l in _hi10}) == [11, 14, 16],
        "%s" % _hi10[:4])

    _knt10 = {"cls": "cls_knight", "level": 3, "race": "human", "hp": 100,
              "bag": {}, "equipped": {}, "flags": {}, "codex": {}}
    _av10, _lk10 = CSK._of_class("cls_knight", 3)
    _name10 = [v.get("name") for _k, v in _av10]           # 3 级此刻解锁的（不是全职业那 8 条）
    _lkname10 = [(v.get("name"), _l) for _k, v, _l in _lk10]
    _lst10 = _drive9(CSK.skills, dict(_knt10))
    _head10 = _r("SYS_SKILL_HEAD", cls=_CL10["cls_knight"]["name"], known=len(_name10),
                 locked=len(_lkname10))
    _misslock10 = [(n, l) for n, l in _lkname10
                   if not any(_r("SYS_SKILL_LOCKED", name=n, lv=l) in _ln for _ln in _lst10)]
    chk("★ 骑士 3 级档 `技能`：抬头「%s」· 解锁的 %d 条一条不落 · 没到的 %d 条走「到 N 级才能学」"
        % (_head10, len(_name10), len(_lkname10)),
        bool(_lst10) and _lst10[0] == _head10
        and not [n for n in _name10 if not any(n in _ln for _ln in _lst10)]
        and not _misslock10,
        "%s / %s" % (_lst10[:1], _misslock10[:2]))
    _idleak10 = [_ln[:34] for _ln in _lst10 if any(k in _ln for k in _SK10)]
    chk("★ `技能` 只出名字，不漏技能 id（%d 行逐行扫）" % len(_lst10), not _idleak10,
        "%s" % _idleak10[:2])

    # 落档那一条：档上只记了一条 ⇒ 学第二条 ⇒ **整班一起记上**（否则「学了新的丢掉默认那一班」）
    _one10 = dict(_knt10, skills=["SKILL_KNT_slash"])
    _learn10 = _drive9(CSK.skill_learn, _one10, "学习 %s" % _name10[1])
    _ids10 = list(_one10.get("skills") or [])
    _names10 = sorted(_SK10[i].get("name") for i in _ids10 if i in _SK10)
    chk("★ `学习 %s` 落档：档上那班 = 本职业**此刻解锁**的全部（%s —— 3 级的号拿不到 11/16 那几条）"
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
    """面板**数值**的写法：整数显示（`02_数值宪法 §一` · 台账 K9）—— 取整口径与
    `rebuild_monsters` 一致（`round()`）。期望值按这一条现算，不手写镜像串。"""
    return "%d" % round(float(v))


def _pct12(v):
    """面板**率**的写法：百分比、一位小数（同一份 §一）。"""
    return "%.1f" % float(v)


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


#: ★ B4-21：那两个「非线性」的数（暴击率 / 闪避那一行）**不许拿实现体抄一遍** ——
#:   期望值从真源现算：数值 = classes 域那条（base + growth×(级-1) + conv×加点）+ 装备那一份
#:   （`gear.gear_stats` 给的宪法键名）；率 = 宪法 F3 `r / (r + K_rate)`，K 取
#:   `content/rules/formula_table.json` 的 `$const`（那一份才是引擎打起来真用的常量）。
_CONST21 = json.loads((REPO / "content" / "rules" / "formula_table.json")
                      .read_text(encoding="utf-8"))["$const"]


def _rating21(cls_id, field, level, alloc, gear=None):
    """宪法数值现算（rating）：职业那条 base / growth / conv + 装备那一份。"""
    _c = _CL9[cls_id]
    _r = float(_c["base"].get(field) or 0) + float(_c["growth"].get(field) or 0) * (int(level) - 1)
    for _st, _n in (alloc or {}).items():
        _r += float((_c["conv"].get(_st) or {}).get(field) or 0) * float(_n)
    for _k, _v in (gear or {}).items():
        if _k == field:
            _r += float(_v)
    return _r


def _rate21(rating):
    """数值 → 率（宪法 F3）—— 常量取真源表，不读实现体那个模块常量。"""
    _r = float(rating or 0)
    return 0.0 if _r <= 0 else _r / (_r + float(_CONST21["K_rate"]))


def _crit_pct21(cls_id, level, alloc, gear=None):
    """`属性` 页「暴击率」那一格该印的数（**率** ⇒ 百分比、一位小数 —— 宪法 §一）。"""
    return _pct12(_rate21(_rating21(cls_id, "crit", level, alloc, gear)) * 100)


def _eva_row21(cls_id, level, alloc, gear=None):
    """`属性` 页二级属性里「闪避」那一行该印的整行（数值，不是率）。"""
    return _r("SYS_ATTR_ROW", label=_r("SYS_STAT_EVA"),
              value=_num12(_rating21(cls_id, "eva", level, alloc, gear)))


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
               "codex": {}, "flags": {"card": 1}}          # ★ B4-27：接活那道门要证
    _db12 = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_cmds_more.db")
    try:
        os.remove(_db12)
    except OSError:
        pass
    _ad12 = _Ad([], seed=dict(_SEED12))
    _h12 = Host(_ad12, str(REPO), inject={"db_path": _db12, "clock": lambda: _FIXED})
    _h12.boot()
    _said12 = []

    def _say12(text):
        _ad12.out.clear()
        _h12.handle({"uid": "u_c", "group_id": "g_c", "text": text})
        _said12.append((text, list(_ad12.out)))
        return list(_ad12.out)

    _sv12 = lambda: (_ad12.saved or {})                                  # noqa: E731 —— 档（真敲后读回）

    # ── 看 <编号>：单子全文（未接 / 已接 / 支线编号 / 没有这张）───────────────────
    #   ★ B4-12：『看 <编号>』的守卫 = 在公会（挂板墙）—— 这一批起**真判脚下** ⇒ 先站到那一站
    #   （站名从 `npcs.funcs` 的 `board` 现取，不写死节点 id）。本块钉的仍然是「单子全文
    #   与 quests 域 + texts 现算一致」这一条，只是把起手档站到合法的那一站。
    from content import town as TW12                                    # noqa: E402
    _BOARD12 = TW12._func_node("board")
    _ad12.saved["node"] = _BOARD12
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

    _ad12.saved["node"] = _SEED12["node"]        # ★ B4-12：回客栈（后面『存放 / 取出』要用）

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
              crit=_crit_pct21(str(_recA.get("cls")), int(_recA.get("level") or 1),
                                _AL13.of_record(_recA), _grA))] + _rows12(_actA) + [
           _r("SYS_ATTR_NOALLOC"),
           # ★ P-34：没投的点那一行（余额 > 0 才出）—— 甲案下这是"点数在手里"的提示
           _r("SYS_ATTR_LEFT", left=_AL13.left_of_record(_recA), usage=_decl_usage("alloc")),
           _r("SYS_ATTR_NOGEAR"), _r("SYS_ATTR_NOTE")]
    if _gA != _wA:
        _BAD12.append(("属性", _gA, _wA))
    _want_cap = _r("SYS_ATTR_VITAL", hp=_num12(_capA), mo=_num12(_actA.get("max_mp")),
                   crit=_crit_pct21(str(_recA.get("cls")), int(_recA.get("level") or 1),
                                    _AL13.of_record(_recA), _grA))
    if _want_cap not in _gA:
        _BAD12.append(("属性 的生命上限 != hp_cap（两个源）", _gA[:2], _want_cap))
    _labs12 = [_r("SYS_STAT_%s" % s) for _k, s in _CM12.PANEL_ROWS]
    # ★ P-34：尾注由三行变四行（多了一行「没投的点」）⇒ 二级属性那几行的范围**按行数取**，
    #   不再靠"尾部减 3"这种位置猜（判据的意思没变：九行都要认得出标签；B4-21 起「闪避」那一行终于真出 —— PANEL_ROWS 九条整）。
    _n12 = len(_rows12(_actA))
    if not all(any(lab in _ln for lab in _labs12) for _ln in _gA[2:2 + _n12]):
        _BAD12.append(("属性 的二级属性行认不出标签", _gA[:3]))
    chk("★ `属性` 真敲：抬头 / 生命上限（= `hp_cap` 那唯一来源）/ 九行二级属性 / 加点 **+ 没投的点** / "
        "装备 —— 与 `panel_build` 现算的期望逐字一致",
        not [x for x in _BAD12 if x[0].startswith("属性")],
        "%s" % [x for x in _BAD12 if x[0].startswith("属性")][:2])

    #: ── ★ B4-21：`属性` 那一页的两个「非线性」的数（端到端玩出来的两处 · 同一页）──────
    #:   ① 「暴击率」那一格**恒 0%**：页面自己钻面板栈、按 `"crit_rate"` 找层（那是 texts 槽位名
    #:      `SYS_PANEL_CRIT_RATE` 的半截），栈里那条层 id 是 `rate` ⇒ 取不到就 `return 0.0`
    #:      ⇒ 六职业 / 任何等级 / 任何装备都印 0%（而引擎打起来读的就是那一层，真值 3% 上下）。
    #:   ② 二级属性里的「闪避」那一行**从没出过**：`PANEL_ROWS` 点名 `("dodge","EVA")`，可 B3-14
    #:      把 eva 率化（从三层里摘掉）之后 actor 上再没有这一格 ⇒ 死行（宪法 §〇①：
    #:      面板上要放的是**数值**「闪避 +12」，不是率）。
    #:   预期值一律 **真源现算**（classes 域 + 装备那一份 + F3 + `$const.K_rate`）。
    _B21: list = []
    _recB = _sv12()
    _alB = _AL13.of_record(_recB)
    _grB, _bfB = PB.gear_and_buffs(_recB)
    _eqB = dict(_recB.get("equipped") or {})
    _lvB = int(_recB.get("level") or 1)
    _clsB = str(_recB.get("cls") or "")

    _gp = _say12("属性")
    if _crit_pct21(_clsB, _lvB, _alB, _grB) + "%" not in "".join(_gp):
        _B21.append(("①-1 暴击率那一格 != 真源现算（%s）" % _crit_pct21(_clsB, _lvB, _alB, _grB),
                     [ln for ln in _gp if "暴击" in ln]))
    if _eva_row21(_clsB, _lvB, _alB, _grB) not in _gp:
        _B21.append(("①-2 闪避那一行不在页面上 / 值不对", _eva_row21(_clsB, _lvB, _alB, _grB),
                     [ln for ln in _gp if "闪避" in ln]))

    #: ② 六职业（真敲六趟）：那一格**各不相同、都不是 0**（原先六职业一律 0.0）
    _six21 = {}
    for _cid in sorted(_CL9):
        _ad12.saved["cls"] = _cid
        _ad12.saved["level"] = 1
        _six21[_cid] = next((ln.split("暴击率 ")[1].split("%")[0]
                             for ln in _say12("属性") if "暴击率" in ln), "")
    _ad12.saved["cls"] = _clsB
    _ad12.saved["level"] = _lvB
    _want21 = {c: _crit_pct21(c, 1, {}) for c in sorted(_CL9)}
    _bad21 = [(c, _six21.get(c), _want21.get(c)) for c in sorted(_CL9) if _six21.get(c) != _want21[c]]
    chk("★ ② 六职业各真敲一趟 `属性`：那一格 = 宪法 F3 现算（%s）—— 谁认错层 / 再回常数 0 就红"
        % " · ".join("%s %s%%" % (c.split("_")[-1], _want21[c]) for c in sorted(_CL9)),
        not _bad21, "%s" % _bad21[:3])

    #: ③ 装备那一份（真穿真敲，穿完还原）：crit 词条 ⇒ 暴击率涨 · eva 词条 ⇒ 闪避那一行涨
    def _first21(field):
        for _k in sorted(_IT9):
            if str(_k).startswith("_"):
                continue
            if any(a.get("stat") == field for a in (_IT9[_k].get("affixes") or [])):
                return _k
        return ""

    _badG21 = []
    for _field, _tag in (("crit", "暴击率"), ("eva", "闪避")):
        _iid = _first21(_field)
        if not _iid:
            _badG21.append(("items 域里没有带 %s 词条的装（这条测不了）" % _field, _field))
            continue
        _slot = str(_IT9[_iid].get("slot") or "")
        _gear21 = GB.gear_stats({"equipped": {_slot: _iid}, "enhance": {}})
        _ad12.saved["equipped"] = {_slot: _iid}
        _g21 = _say12("属性")
        _ad12.saved["equipped"] = dict(_eqB)
        if _tag == "暴击率":
            _w21 = _crit_pct21(_clsB, _lvB, _alB, _gear21) + "%"
            if _w21 not in "".join(_g21):
                _badG21.append(("穿 %s（crit+%s）⇒ 暴击率那一格 != 真源现算" % (_iid, _gear21.get("crit")),
                                _w21, [ln for ln in _g21 if "暴击" in ln]))
        else:
            _w21 = _eva_row21(_clsB, _lvB, _alB, _gear21)
            if _w21 not in _g21:
                _badG21.append(("穿 %s（eva+%s）⇒ 闪避那一行 != 真源现算" % (_iid, _gear21.get("eva")),
                                _w21, [ln for ln in _g21 if "闪避" in ln]))
    chk("★ ③ 换一件带词条的装（真穿真敲）：crit ⇒ 暴击率那一格跟着走 · eva ⇒ 闪避那一行跟着走"
        "（两处都按真源现算逐字比）", not _badG21, "%s" % _badG21[:2])

    #: ④ 静态守卫：页面**不许自己钻面板栈**（率只有一个读数口 `panel_build.rate_of_actor`
    #:    —— 这一条正是本批那个 bug 的形状：自己扫层 + 认错 id + 静默回 0）
    import ast as _ast21
    _cm21 = (REPO / "content" / "cmds_more.py").read_text(encoding="utf-8")
    _tree21 = _ast21.parse(_cm21)
    _stk21 = sorted({n.id for n in _ast21.walk(_tree21)
                     if isinstance(n, _ast21.Name) and n.id == "stacks"}
                    | {n.attr for n in _ast21.walk(_tree21)
                       if isinstance(n, _ast21.Attribute) and n.attr == "stacks"})
    chk("★ ④ 静态守卫：`cmds_more` 不再自己钻面板栈（要率走 `panel_build.rate_of_actor`）"
        "—— 谁再自己扫层（本批那个 bug 的形状）当场红", not _stk21, "%s" % _stk21)

    chk("★ B4-21 `属性` 那一页的两个非线性数（真敲 + 真源现算）：暴击率那一格 = 宪法 F3 现算"
        "（六职业各不相同 · 都不是 0 · 换 crit 装跟着涨）· 二级属性里「闪避」那一行真在且 = 真源"
        "现算（换 eva 装跟着涨）", not _B21, "%s" % _B21[:2])

    #: ── ★ B4-22：那一页的**数值**一律整数显示（`02_数值宪法 §一`「数值 = 整数显示，内部浮点」·
    #:   台账 K9「面板 / 怪数值取整」）—— 十行逐行与**真源现算**比，且行值里不许出现小数点。
    #:   原先 `_fmt` 是「小数留一位」（14.36 → 14.4）—— 那是 `_旧案参考` 的写法（旧案「ATK/MATK
    #:   保留 1 位」）；怪面板那一侧早就全字段取整，只有玩家这一页还在印 16.4 / 20.4 / 5.6。
    _ENG2CONST22 = {v: k for k, v in PB.KEYMAP.items()}          # 引擎键名 → 宪法键名（唯一次映射）
    _gp22 = _say12("属性")
    _badInt22 = []
    for _k22, _slot22 in _CM12.PANEL_ROWS:
        _field22 = _ENG2CONST22.get(_k22, _k22)
        _want22 = _r("SYS_ATTR_ROW", label=_r("SYS_STAT_%s" % _slot22),
                     value="%d" % round(_rating21(_clsB, _field22, _lvB, _alB, _grB)))
        if _want22 not in _gp22:
            _badInt22.append((_slot22, _want22,
                              [ln for ln in _gp22 if _r("SYS_STAT_%s" % _slot22) in ln]))
    _vals22 = [ln[2:].rsplit(" ", 1)[-1] for ln in _gp22 if ln.startswith("· ")]
    if any("." in _v22 for _v22 in _vals22):
        _badInt22.append(("行值里有小数点（不是整数显示）", _vals22))
    chk("★ B4-22 二级属性那 %d 行**逐行 = 真源现算的整数**（classes 域 base/growth/conv + 装备那一份，"
        "取整口径与 `rebuild_monsters` 同一条），且行值里一个小数点都没有" % len(_CM12.PANEL_ROWS),
        not _badInt22, "%s" % _badInt22[:2])

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
    # ★ P3 BUG-4（本波 f4）：**装备现在有收价** —— 唯一一口 `content/shop.py::sell_price_of`
    #   （品阶 × 等级档；材料 / 旧物那一格照旧 = `items.price`）。原先装备域里一个价都没有
    #   ⇒ 这里回的是「这东西没价」，打到的多余装备只能占背包（实测三把同名剑）。
    _wpn_gold12 = int(_SH15.sell_price_of(_wpn))
    if _gS2 != [_r("SYS_SELL_OK", icon=_wpn.get("icon") or "", name=_wpn["name"], n=1,
                   gold=_wpn_gold12)] \
            or _WPN12 in (_sv12().get("bag") or {}) \
            or int(_sv12().get("gold") or 0) != 30 + int(_IT9[_BONE12]["price"]) + _wpn_gold12:
        _BAD12.append(("卖出 装备（收价表现算）", _gS2, _wpn_gold12, _sv12().get("bag"),
                       _sv12().get("gold")))
    _db12b = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_cmds_more_b.db")
    try:
        os.remove(_db12b)
    except OSError:
        pass
    _ad12b = _Ad([], seed=dict(_SEED12, loc="belt_north", node="bn_bone"))
    _h12b = Host(_ad12b, str(REPO), inject={"db_path": _db12b, "clock": lambda: _FIXED})
    _h12b.boot()
    _ad12b.out.clear()
    _h12b.handle({"uid": "u_c", "group_id": "g_c", "text": "卖出 骨头"})
    _gS3 = list(_ad12b.out)
    if _gS3 != [_r("SYS_SELL_AWAY")] or (_ad12b.saved or {}).get("bag") != _SEED12["bag"]:
        _BAD12.append(("野外卖出", _gS3, (_ad12b.saved or {}).get("bag")))
    chk("★ `卖出` 真敲三档：域里有价 ⇒ 钱与背包同时变 / **装备按收价表现算的价真收到**"
        "（P3 BUG-4 · 与『旧货』同一个口）/ "
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
                      list=" · ".join("%s ×%d" % (_LT12.label_of(i), _bagB4[i])
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
             _r("SYS_ALLOC_PLAN", total=_tot13,
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
    _h13 = Host(_bad13, str(REPO), inject={"db_path": _db13, "clock": lambda: _FIXED})
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
    _h16 = Host(_ad16, str(REPO), inject={"db_path": _db16, "clock": lambda: _FIXED})
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

    # ── 客栈：那一站 = 箱子那一站（同一个节点）· 住店**收钱**（P-55）· 箱子那两句 ──────
    _cmp16("客栈（人在白烛堂）", _say16("客栈"), [_r("SYS_PLACE_AWAY", name=_nname16(_INN_NODE16))])
    _say16("去 %s" % _nname16(_INN_NODE16))
    _rowsI16, _lineI16 = _roster16(_INN_NODE16, _sv16())
    _whoI16 = str((_rowsI16[0].get("name") if _rowsI16 else ""))
    _goldI16 = int(_sv16().get("gold") or 0)
    _cmp16("客栈（不疼也不困）", _say16("客栈"),
           [_r("SYS_PLACE_HEAD", name=_nname16(_INN_NODE16)), _r("SYS_LOOK_WHO", list=_lineI16),
            _r("SYS_INN_FULL"), _r("SYS_INN_BOX"), _r("SYS_TALK_HOW", name=_whoI16)])
    _fullI16 = (int(_sv16().get("gold") or 0), int(_sv16().get("hp") or 0))
    #: ★ P-55 下半：住一宿的价钱**从口径表现读**（不写死 8 —— 改一格这一条跟着走）
    with open(os.path.join(str(REPO), "content", "rules", "inn.json"), encoding="utf-8") as _f:
        _fee16 = int(json.load(_f)["fee"])
    _ad16.saved["hp"] = 20                              # 造一个带伤的档（真敲读回）
    _ad16.saved["gold"] = _fee16 + 7                    # 钱刚够（剩下那 7 个给判据看着）
    _cmp16("客栈（住店 · 钱够）", _say16("客栈"),
           [_r("SYS_PLACE_HEAD", name=_nname16(_INN_NODE16)), _r("SYS_LOOK_WHO", list=_lineI16),
            _r("SYS_INN_SLEEP"), _r("SYS_REST_HEAL", add=_cap16 - 20, hp=_cap16, max=_cap16),
            _r("SYS_MONEY_POUCH", gold=7), _r("SYS_INN_BOX"), _r("SYS_TALK_HOW", name=_whoI16)])
    _paidI16 = (int(_sv16().get("gold") or 0), int(_sv16().get("hp") or 0))
    _ad16.saved["hp"] = 20                              # 再带一次伤；这回钱只够欠着
    _ad16.saved["gold"] = _fee16 - 3
    _snapI16 = json.dumps(_sv16(), ensure_ascii=False, sort_keys=True)
    _cmp16("客栈（住店 · 钱不够）", _say16("客栈"),
           [_r("SYS_PLACE_HEAD", name=_nname16(_INN_NODE16)), _r("SYS_LOOK_WHO", list=_lineI16),
            _r("SYS_SHOP_POOR", lack=3), _r("SYS_INN_BOX"), _r("SYS_TALK_HOW", name=_whoI16)])
    chk("★ `客栈` 真敲四档（指路 / 不用住店 / 住店 / 钱不够）—— 且那一站与『存放』认的是同一个节点"
        "（`cmds_more.STASH_NODE`，一处只写一份）",
        not [x for x in _BAD16 if x[0].startswith("客栈")] and _paidI16[1] == _cap16
        and _INN_NODE16 == _CM12.STASH_NODE,
        "%s（住店那档 hp=%s/%s · 客栈站=%s）" % ([x for x in _BAD16 if x[0].startswith("客栈")][:1],
                                                _paidI16[1], _cap16, _INN_NODE16))
    chk("★ 住店**真收钱**（P-55 下半 · fee 从口径表现读 = %d）：满血那一档**一分不扣**（睡都没睡）· "
        "住店那一档档上真扣 fee（gold %d → %d）且血回满 · 钱不够那一档**档一个字不动**"
        "（不睡 / 不回血 / 不扣钱 —— fail-closed）"
        % (_fee16, _fee16 + 7, _paidI16[0]),
        _fullI16 == (_goldI16, _cap16) and _paidI16 == (7, _cap16)
        and json.dumps(_sv16(), ensure_ascii=False, sort_keys=True) == _snapI16,
        "满血档 %s（应 = %s）· 住店档 gold/hp %s（应 = (7, %s)）· 钱不够档 gold/hp %s（应 = (%d, 20)）"
        % (_fullI16, (_goldI16, _cap16), _paidI16, _cap16,
           (int(_sv16().get("gold") or 0), int(_sv16().get("hp") or 0)), _fee16 - 3))
    _ad16.saved["hp"] = _cap16                          # 还原成进来时的样子（后面的用例不看血与钱）
    _ad16.saved["gold"] = _goldI16

    # ── 旧货：收什么 = 域里有价的那些（逐件对账）· 看一眼 ≠ 动档 ────────────
    def _junk_want16(p):
        rows = []
        for iid in sorted(p.get("bag") or {}):
            rec = LT16.rec_of(iid)
            # ★ P3 BUG-4（本波 f4）：收价走**唯一一口**（`content/shop.py::sell_price_of`）——
            #   材料 / 旧物那一格照旧 = `items.price`，**装备**按品阶 × 等级档现算
            #   （原先这里是 `rec.get("price")`：装备域里没价 ⇒ 永远不列它）
            price = _SH15.sell_price_of(rec)
            if price <= 0:
                continue
            n = int((p.get("bag") or {}).get(iid) or 0)
            rows.append((LT16.label_of(iid), n, int(price) * n))   # 名字也走那一口（重名的缀品阶）
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
    # ★ P3 BUG-4（本波 f4）：**装备那一档** —— 包里一件装备时，`旧货` 也得照收价表列出来
    #   （原先装备没价 ⇒ 这一页永远不列它，玩家以为铺子不收装备）
    _GEAR16 = next((k for k, v in (st.domain("items") or {}).items()
                    if isinstance(v, dict) and v.get("slot") and not v.get("price")), "")
    if _GEAR16:
        _ad16.saved["bag"] = {_GEAR16: 1}
        _cmp16("旧货（包里一件装备）", _say16("旧货"), _junk_want16(_sv16()))
    _ad16.saved["bag"] = _bag16
    chk("★ `旧货` 真敲三档（有东西 / 空的 / **一件装备**）：逐件与收价那一口现算的期望逐字一致，"
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
        # ★ fix7-gear：商队那一家**真到货** —— 车没到 ⇒ 说清在等哪条委托；到了 ⇒ 柜上那几件
        #   （一家一家现算：`shop == 键` + 等级那一刀；条件从 `events.period` 现取，不写死委托名）
        #   位置：与 `cmds_places.caravan` 同序 —— **在「外人在哪一站」之前**
        from content import shop as _SH16                                     # noqa: E402
        for _ck16 in _SH16.shelf_keys():
            _ev16 = str(_SH16.shelf_rec(_ck16).get("event") or "")
            if not _ev16:
                continue
            if not CAL16.event_on(_ev16, p=p):
                _who16 = _SH16.event_wait(_ck16)
                if _who16:
                    out.append(_r("SYS_CARAVAN_WHY", name=_who16))
                continue
            _rows16 = _SH16.goods(p, shelf=_ck16)
            if _rows16:
                out.append(_r("SYS_CARAVAN_GOODS"))
                for _g16 in _rows16:
                    out.append(_r("SYS_SHELF_ROW", icon=_g16["rec"].get("icon") or "",
                                  name=_g16["rec"].get("name") or _g16["id"], gold=_g16["gold"],
                                  level=_SH16.level_need(_g16["rec"])))
                continue
            for _g16 in _SH16.goods_at(_ck16, p):
                out.append(_r("SYS_SHELF_LOCK", name=_g16["rec"].get("name") or _g16["id"],
                              level=_SH16.level_need(_g16["rec"]),
                              now=int((p or {}).get("level") or 0)))
                break
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
    #: ★ B4-16：评级那一屏的档名与门槛都**从口径表现取**（探针自己读 rules/ranks.json，
    #:   不写死「见习 / 交 5 条」—— 真源一改这一条跟着走）
    with open(os.path.join(str(REPO), "content", "rules", "ranks.json"), encoding="utf-8") as _f:
        _RK16 = json.load(_f)
    _RT16 = _RK16["tiers"]
    _RN16 = [TX[_RK16["label_tpl"] % str(t["id"]).upper()]["value"] for t in _RT16]

    def _need16(i, have, killed):
        t = _RT16[i]
        return _r("SYS_RANK_NEED", tier=_RN16[i], done=t["need_done"], chief=t["need_chief"],
                  have=have, killed=killed)

    _cmp16("评级（刚办证）", _say16("评级"),
           [_r("SYS_MINE_RANK", tier=_RN16[0]), _r("SYS_MINE_DONE", n=_cnt16),
            _r("SYS_RANK_CHIEF", n=0), _need16(1, _cnt16, 0)])
    _ad16.saved["flags"] = dict(_sv16().get("flags") or {},
                               quests_done=["q_main_01", "q_main_02", "q_main_03"])
    _chief16 = next((m for m, v in (st.domain("monsters") or {}).items()
                     if v.get("role_key") == "chief" and m in CX16.book("monster")), "")
    _ad16.saved["books"] = {"monster": {_chief16: {"day": 1, "kills": 2}}}
    _cmp16("评级（有进度）", _say16("评级"),
           [_r("SYS_MINE_RANK", tier=_RN16[0]), _r("SYS_MINE_DONE", n=3),
            _r("SYS_RANK_CHIEF", n=1), _need16(1, 3, 1)])
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

    # ── 公告：包名 / 版本 / 手边能敲什么 ────────────────────────────────
    #   ★ fix3-⑥：原先这里还印一行「已经接上的指令：N / M 条」（内部完成度 · P1 BUG-15）
    #     ⇒ 换成 SYS_NOTICE_WHAT；旧槽位退役登记见 `scripts/probe_copy.py::RETIRED_DOC`。
    _mf16 = json.loads((Path(str(REPO)) / "game.json").read_text(encoding="utf-8"))
    _cmp16("公告", _say16("公告"),
           [_r("SYS_NOTICE_HEAD"),
            _r("SYS_NOTICE_PKG", name=_mf16.get("name") or "", ver=_mf16.get("version") or ""),
            _r("SYS_NOTICE_WHAT"),
            _r("SYS_NOTICE_TAIL")])
    chk("★ `公告` 真敲：包名 / 版本取自 `game.json` · **不再报内部完成度**"
        "（「N / M 条」这种构建期计数不上屏）",
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

print("⑬ ★ B3-19（真敲）：`装备` 的**属性门槛** —— 不够 ⇒ 穿不上 + 一行提示（档不动）· 够了 ⇒ 穿上")
#   真源：主线 2026-09-25 裁决（门槛 = 家族 × 品质 × 建议加点曲线 · 值不手打）。
#   四档真敲：
#     ① 加点不够 ⇒ `SYS_GEAR_REQ` 那一行（槽位 + 三个数逐字对账）· **档逐格没动**
#     ② 加点够了 ⇒ 穿上那一句 + 真进 `equipped`
#     ③ 无门槛件（普通品阶）：0 加点也穿得上（门槛不是「一律要有加点」）
#     ④ 旧档（身上那件、点数为 0）：照「已经穿在身上了」说 —— 不报门槛、不强制脱
try:
    import sys as _s13
    _s13.path.insert(0, str(Path(__file__).resolve().parent))
    import rebuild_item_reqs as _RIR13                                       # noqa: E402
    _CL13 = {k: v for k, v in (st.domain("classes") or {}).items()
             if not str(k).startswith("_")}
    _IT13 = st.domain("items") or {}
    _EQ13 = {k: v for k, v in _IT13.items() if v.get("slot")}
    _W13 = next(k for k in sorted(_EQ13)
                if _EQ13[k].get("req") and _RIR13.family_of(k).startswith("weapon_"))
    _R13 = _EQ13[_W13]["req"]
    _A13, _V13 = _R13["attr"], int(_R13["v"])
    _C13 = _RIR13.ref_class_for_item(_CL13, _W13, _A13)                      # 武器 ⇒ 它自己那个职业
    _F13 = next(k for k in sorted(_EQ13)
                if not _EQ13[k].get("req")
                and _RIR13.family_of(k).split("_")[1] == _C13[4:])           # 同职业的无门槛件（普通）
    # ★ 同一家族的四个品阶**共用一个名字**（真源：装备的全名 = 名字 + 路线）⇒ 每个起手档里只放一件，
    #   否则 `装备 <名字>` 会命中背包里排序在前的那一件（那是既有口径，不是本批的事）。
    _BASE13 = {"cls": _C13, "race": "human", "level": _R13["level"], "hp": 100, "gold": 30,
               "bag": {_W13: 1}, "equipped": {}, "codex": {}, "flags": {}}

    def _run13(seed, text):
        """一个起手档 + 一条指令：真宿主真敲一遍（uid 必须叫 `u_c` —— `_Ad.load_player` 只认它）。"""
        _db13 = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp",
                             "ast_probe_cmds_req.db")
        try:
            os.remove(_db13)
        except OSError:
            pass
        _ad13 = _Ad([], seed=dict(seed))
        _h13 = Host(_ad13, str(REPO), inject={"db_path": _db13, "clock": lambda: _FIXED})
        _h13.boot()
        _ad13.out.clear()
        _h13.handle({"uid": "u_c", "group_id": "g_c", "text": text})
        return list(_ad13.out), (_ad13.saved or {})

    _b13 = []
    _want13 = _r("SYS_GEAR_REQ", name=_IT13[_W13]["name"], attr=_r("SYS_STAT_%s" % _A13),
                 need=_V13, have=0, gap=_V13)
    _o_lack, _s_lack = _run13(dict(_BASE13, alloc={}), "装备 %s" % _IT13[_W13]["name"])
    if _o_lack != [_want13]:
        _b13.append(("加点不够回的不是那一行", _o_lack, _want13))
    if _s_lack != dict(_BASE13, alloc={}):          # ★ 一个字都没动（handler 早早 return，没 save）
        _b13.append(("加点不够却动了档", _s_lack))
    _o_enuf, _s_enuf = _run13(dict(_BASE13, alloc={_A13: _V13}), "装备 %s" % _IT13[_W13]["name"])
    if _o_enuf[:1] != [_r("SYS_GEAR_EQUIP_OK", icon=_IT13[_W13].get("icon", ""),
                          name=LPICK.label_of(_W13),
                          kind=_IT13[_W13].get("kind", ""))] \
            or _s_enuf.get("equipped") != {_IT13[_W13]["slot"]: _W13} \
            or (_s_enuf.get("bag") or {}):
        _b13.append(("加点够了却没穿上 / 没摘背包", _o_enuf[:1], _s_enuf.get("equipped"),
                     _s_enuf.get("bag")))
    _o_free, _s_free = _run13({"cls": _C13, "race": "human", "level": 1, "hp": 100, "gold": 30,
                               "bag": {_F13: 1}, "equipped": {}, "codex": {}, "flags": {},
                               "alloc": {}}, "装备 %s" % _IT13[_F13]["name"])
    if _o_free[:1] != [_r("SYS_GEAR_EQUIP_OK", icon=_IT13[_F13].get("icon", ""),
                          name=LPICK.label_of(_F13),
                          kind=_IT13[_F13].get("kind", ""))] \
            or _s_free.get("equipped") != {_IT13[_F13]["slot"]: _F13}:
        _b13.append(("无门槛件 0 加点穿不上", _o_free[:1], _s_free.get("equipped")))
    _OLD13 = dict(_BASE13, alloc={}, bag={}, equipped={_IT13[_W13]["slot"]: _W13})
    _o_old, _s_old = _run13(_OLD13, "装备 %s" % _IT13[_W13]["name"])
    if _o_old != [_r("SYS_GEAR_WORN", name=_IT13[_W13]["name"])] \
            or _s_old.get("equipped") != {_IT13[_W13]["slot"]: _W13}:
        _b13.append(("旧档报了门槛 / 被强制脱", _o_old, _s_old.get("equipped")))
    chk("★ 四档真敲（%s · 要 %s %s）：不够「%s」（档逐格没动）· 够了穿上 · 无门槛件 0 加点也穿得上 · "
        "旧档不报门槛" % (_W13, _A13, _V13, _want13), not _b13, "%s" % _b13[:2])
    chk("★ 门槛那两句里没有物品 id、也没有取不到文案（%d 行逐行扫）"
        % len(_o_lack + _o_enuf + _o_free + _o_old),
        not [ln[:40] for ln in _o_lack + _o_enuf + _o_free + _o_old
             if _W13 in ln or _F13 in ln or "[MISSING TEXT" in ln],
        "%s" % [ln[:40] for ln in _o_lack + _o_enuf + _o_free + _o_old
                if _W13 in ln or "[MISSING TEXT" in ln][:2])
except Exception as exc:                                              # noqa: BLE001
    chk("★ B3-19 那四档真敲跑得起来（真宿主契约）", False,
        "%s: %s" % (type(exc).__name__, exc))

# ══════════════════════════════════════════════════════════════
# ★ B3-23：战斗那六条（打断 / 后撤 / 放技能 / 战斗中用物 / 集火 / 换武器）
# --------------------------------------------------------------
# 口径（真源 `06_第一阶段垂直切片/02_战斗机制 §〇·五` 伪即时 CTB · `04_指令总表 §五` 战斗表）：
#   一条战斗指令 = **一场遭遇里的「你这一手」** —— 遇敌那一下先由快的对方行动，然后你这一手
#   做你说的事，接着这一场自动打完、照旧落账（钱/经验/掉落/死亡/`flags.last_battle`）。
# 判据分三层：① 真宿主真敲（逐字对槽位 + 档上副作用）② 直调那几条（`battle_item` 的路由被
#   item_use 挡着，见 ③；受控战斗状态下的「断成 / 压后」两种情形也只有直调才钉得住）
#   ③ 现算（期望值走与实现同一个口：`battle_acts.hand_ticks` / `rules()` / 域里的名字）。
# ══════════════════════════════════════════════════════════════
from content import battle_acts as BA23                                   # noqa: E402
from content import cmds_battle as CBAT23                                 # noqa: E402
from content import combat as CBO23                                       # noqa: E402
import ext_combat.battle.schedule as _S23                                 # noqa: E402

BATTLE6 = ("interrupt", "retreat", "skill_cast", "battle_item", "focus_fire", "swap_weapon")

print("⑭ ★ B3-23：战斗那六条真敲 —— 逐字对槽位 · 档上副作用逐条核（真宿主契约）")
try:
    _MON23 = st.domain("monsters") or {}
    _MS23, _MF23 = "ms_field_mouse", "ms_birch_crow"        # 田鼠（3 级 · 慢）· 林鸦（4 级 · 快）
    _POT23, _WPN23 = "i_potion_minor", "i_weapon_assassin_venom_common"
    _BASE23 = {"cls": "cls_assassin", "race": "human", "level": 5, "exp": 0, "gold": 0, "hp": 40,
               "loc": "belt_north", "node": "bn_bone", "prev": [], "bag": {_POT23: 3},
               "equipped": {}, "codex": {}, "flags": {}}
    chk("★ 六条都挂了 bind（%s）" % " · ".join(BATTLE6),
        not [k for k in BATTLE6 if not (DECL.get(k) or {}).get("bind")],
        "%s" % [k for k in BATTLE6 if not (DECL.get(k) or {}).get("bind")])

    def _say23(seed, text, pin=_MS23):
        """真宿主真敲一条：**遭遇钉死**在 `pin` 上（战斗内部抽怪 ⇒ 不钉住不可复现）。

        `pin=None` = 这一带挑不出怪（演「没遇敌」那一档）。
        """
        _db23 = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp",
                             "ast_probe_cmds_b23.db")
        try:
            os.remove(_db23)
        except OSError:
            pass
        _real = CBO23.pick_encounter
        CBO23.pick_encounter = (lambda *a, **k: [pin]) if pin else (lambda *a, **k: [])
        try:
            _ad23 = _Ad([], seed=dict(seed))
            _h23 = Host(_ad23, str(REPO), inject={"db_path": _db23, "clock": lambda: _FIXED})
            _h23.boot()
            _ad23.out.clear()
            _h23.handle({"uid": "u_c", "group_id": "g_c", "text": text})
            return list(_ad23.out), (_ad23.saved or {})
        finally:
            CBO23.pick_encounter = _real

    def _direct23(fn, seed, text="", pin=_MS23):
        """直调实现体（真宿主那一屏之外的那几条 —— 与 probe_combat 的 `_drive` 同形）。"""
        out = []

        async def _go():
            _real = CBO23.pick_encounter
            CBO23.pick_encounter = (lambda *a, **k: [pin]) if pin else (lambda *a, **k: [])
            try:
                async for _ln in fn(_E9(text), None, "u_c", seed):
                    out.append(str(_ln))
            finally:
                CBO23.pick_encounter = _real

        asyncio.run(_go())
        return out

    _B23 = []
    _MEET23 = _r("COMBAT_MEET", name=_MON23[_MS23]["name"])
    _INT_NAME = (BA23.interrupt_action_of(_BASE23) or {}).get("name", "")

    # ★ G2（2026-09-26）：战斗改成**一手一推进** ⇒ 「这一场」跨指令落盘
    #   （`_say23` 走群 `g_c` + uid `u_c` ⇒ 单人键 `g_c#u_c`；直调那一支 `_E9` 没有群 ⇒ 键 `#u_c`）
    def _field23(uid="u_c", gid="g_c"):
        from content import instance as _INST23
        return _INST23.load(_INST23.key_of(gid, uid, [uid]))

    def _clear23(uid="u_c", gid=""):
        from content import instance as _INST23
        _INST23.clear(_INST23.key_of(gid, uid, [uid]))

    # ── 一、打断：本门的动作名 + 真做出来（断成 / 压后 两种情形直调钉住）──────────
    #   ★ G2：一条战斗指令 = **推一手** ⇒ 真敲那一档看的是「这一场真起来了吗 + 那两句在不在」
    #     （不再看 `last_battle` —— 那是**结算期**才写的账，这一场还没打完）
    _o_int, _s_int = _say23(dict(_BASE23), "打断")
    _f_int = _field23()
    _PUSH23 = (TX.get("COMBAT_INT_PUSH") or {}).get("value", "").split("{ticks}")[0]
    if _o_int[:1] != [_MEET23] \
            or _r("COMBAT_INT_HEAD", skill=_INT_NAME) not in _o_int \
            or not (_r("COMBAT_INT_BREAK") in _o_int
                    or any(ln.startswith(_PUSH23) for ln in _o_int)):
        _B23.append(("打断 真敲", _o_int[:3]))
    if _f_int is None or int(_f_int.get("hands") or 0) != 1:
        _B23.append(("打断 真敲没把这一场推起来（手数 = %s）"
                     % (None if _f_int is None else _f_int.get("hands"))))
    # 受控两档（直调回调本体）：对方**在出招窗口里** ⇒ 那一手作废；没在窗口里 ⇒ 只压后
    _rec23 = dict(_BASE23)
    _b23a = CBO23.build(dict(_BASE23), [_MS23], _MON23)
    _foe23 = _b23a.sides[CBO23.ENEMY_SIDE][0]
    _pl23 = _b23a.focus()
    _b23a.human_act("attack", None, _foe23)              # 让它起手（待发槽里那一手）
    _was_charging = isinstance(_foe23.get("charging"), dict)
    _ticks23 = BA23.hand_ticks(_b23a, _pl23, BA23.CAT["interrupt"])
    _ct0 = float(_foe23.get("ct") or 0)
    _logs23a = BA23.Hand("interrupt", p=_rec23).override(_b23a, "interrupt", _pl23, None, None)[0]
    if not _was_charging or _foe23.get("charging") is not None \
            or _logs23a != [_r("COMBAT_INT_BREAK")] \
            or abs(float(_foe23.get("ct") or 0) - (_ct0 + _ticks23)) > 1e-6:
        _B23.append(("打断 断成那一档", _was_charging, _foe23.get("charging"),
                     abs(float(_foe23.get("ct") or 0) - (_ct0 + _ticks23))))
    _b23b = CBO23.build(dict(_BASE23), [_MS23], _MON23)
    _foe23b = _b23b.sides[CBO23.ENEMY_SIDE][0]
    _pl23b = _b23b.focus()
    _ct0b = float(_foe23b.get("ct") or 0)
    _ticks23b = BA23.hand_ticks(_b23b, _pl23b, BA23.CAT["interrupt"])
    _logs23b = BA23.Hand("interrupt", p=_rec23).override(_b23b, "interrupt", _pl23b, None, None)[0]
    if _foe23b.get("charging") is not None \
            or _logs23b != [_r("COMBAT_INT_PUSH", ticks=int(_ticks23b))] \
            or abs(float(_foe23b.get("ct") or 0) - (_ct0b + _ticks23b)) > 1e-6:
        _B23.append(("打断 压后那一档", _logs23b,
                     abs(float(_foe23b.get("ct") or 0) - (_ct0b + _ticks23b))))
    chk("★ `打断` 真敲（本门动作名 = 「%s」）+ 直调两档：**出招窗口里的那一手真作废**（引擎 "
        "interrupt 动词）· 没在窗口里就**把到点时刻推后 %d 刻**（= 你这一手的耗时，现算）"
        % (_INT_NAME, int(_ticks23)), not [x for x in _B23 if x[0].startswith("打断")],
        "%s" % [x for x in _B23 if x[0].startswith("打断")][:2])

    # ── 二、后撤：「能跑掉」= 对方这一拍**没押着手**（没在出招）—— 与实现同一个判据现算 ──
    def _can_flee23(pin):
        """这一档跑不跑得掉 —— 与 `cmds_battle.retreat` 同一个口现算（不手打期望值）。"""
        _b = CBO23.build(dict(_BASE23), [pin], _MON23)
        _S23.advance(_b, [])
        _now = float(getattr(_b, "_now", 0) or 0)
        return not any(_S23.pending_left(_a, _now) > 0
                       for _a in (_b.sides.get(CBO23.ENEMY_SIDE) or []) if _a.get("hp", 0) > 0)

    _exp_slow, _exp_fast = _can_flee23(_MS23), _can_flee23(_MF23)
    #   ★ 第三个 pin = 塔顶 Boss（spd 136 > 玩家）：它**先动** ⇒ 到你决策点时它正押着一手
    #     ⇒ 走「退不开」那一档（两档都真出现，判据才叫把分支盖住）
    _MB23 = "ms_boss_oath_sentry"
    _saw23 = set()
    for _pin, _exp in ((_MS23, _exp_slow), (_MF23, _exp_fast), (_MB23, _can_flee23(_MB23))):
        _o, _s = _say23(dict(_BASE23), "后撤", pin=_pin)
        _fled = (_s.get("flags") or {}).get("last_battle", {}).get("result") == "fled"
        _saw23.add(_fled)
        if _exp and not (_r("COMBAT_RETREAT_OK") in _o and _fled):
            _B23.append(("后撤 该跑得掉却打了", _pin, _o[:3]))
        if (not _exp) and not any(ln.startswith((TX.get("COMBAT_RETREAT_BLOCK") or {}).get(
                "value", "").split("{name}")[0]) for ln in _o):
            _B23.append(("后撤 该退不开却跑了", _pin, _o[:3]))
        if _fled and ((_s.get("bag") or {}).get(_POT23) != 3 or int(_s.get("exp") or 0)
                      or int(_s.get("gold") or 0)):
            _B23.append(("后撤 跑掉了却拿了收益", _pin, _s))
        if not _fled and _s.get("flags", {}).get("last_battle", {}).get("result") == "fled":
            _B23.append(("后撤 没跑掉却记成 fled", _pin))
    chk("★ `后撤`：**能跑掉才跑得掉**（三个 pin 各自现算：田鼠 %s / 林鸦 %s / 塔顶 Boss %s）"
        "—— 退掉了那一档记成 `fled`、**没有掉落没有经验**；退不开那一档白花一手、这一场照打"
        % ("跑得掉" if _exp_slow else "退不开", "跑得掉" if _exp_fast else "退不开",
           "跑得掉" if _can_flee23(_MB23) else "退不开"),
        not [x for x in _B23 if x[0].startswith("后撤")] and len(_saw23) == 2,
        "" if (not [x for x in _B23 if x[0].startswith("后撤")] and len(_saw23) == 2)
        else "%s" % ([x for x in _B23 if x[0].startswith("后撤")][:2]
                     or ["两档没都出现：%s" % _saw23]))

    # ── 三、放技能：四道门 + 真放出来 ────────────────────────────────────────────
    _o_sk_bad, _s_sk_bad = _say23(dict(_BASE23), "技能 没有这条技能")
    _o_sk_nocls, _s_sk_nocls = _say23({"level": 3, "bag": {}, "flags": {}}, "技能 挥击")
    _o_sk_ok, _s_sk_ok = _say23(dict(_BASE23), "技能 %s" % _INT_NAME)
    if _o_sk_bad != [_r("COMBAT_SKILL_BAD", name="没有这条技能")]:
        _B23.append(("放技能 认不出", _o_sk_bad))
    if _o_sk_nocls != [_r("SYS_SKILL_NOCLS")]:
        _B23.append(("放技能 没择业", _o_sk_nocls))
    if _o_sk_ok[:1] != [_MEET23] \
            or _r("COMBAT_SKILL_HEAD", name=_INT_NAME) not in _o_sk_ok \
            or _field23() is None or int((_field23() or {}).get("hands") or 0) != 1 \
            or len(_o_sk_ok) < 6:
        _B23.append(("放技能 真放", _o_sk_ok[:3]))
    chk("★ `技能 <名>`：认不出 / 没择业 各回各自那句（逐字）· 本门「%s」真放出来"
        "（这一手真花掉、这一场真起来）" % _INT_NAME,
        not [x for x in _B23 if x[0].startswith("放技能")],
        "%s" % [x for x in _B23 if x[0].startswith("放技能")][:2])

    # ── 四、战斗中用物：一场每件只算一次（带得多 ≠ 用得多）──────────────────────
    #   ★ G2：一条指令 = 一手 ⇒ 这一档要**在同一个场里敲两次**才看得见「上限」
    #     （清一次场 → 第 1 次真喝、第 2 次照实说「这一场用过了」并回落普攻）
    _p_item = dict(_BASE23, hp=20)
    _clear23(gid="")                              # 直调那一支 env 没有群 ⇒ 键 `#u_c`
    _o_item = _direct23(CBAT23.battle_item, _p_item, "使用 伤药")
    _used_left = (_p_item.get("bag") or {}).get(_POT23)
    _f_item = _field23(gid="")
    _o_item2 = _direct23(CBAT23.battle_item, _p_item, "使用 伤药")
    _used_left2 = (_p_item.get("bag") or {}).get(_POT23)
    _o_none = _direct23(CBAT23.battle_item, dict(_BASE23, bag={}), "使用 伤药")
    if _o_item[:1] != [_MEET23] \
            or _r("COMBAT_ITEM_HEAD", name="伤药") not in _o_item \
            or _used_left != 2 \
            or not (_r("COMBAT_ITEM_CAP", name="伤药") in _o_item2) \
            or _used_left2 != 2 \
            or _f_item is None or int(_f_item.get("items_used", {}).get(_POT23, 0)) != 1 \
            or len([ln for ln in _o_item if "伤药" in ln and "喝下" in ln]) != 1:
        _B23.append(("用物 上限那一档", _o_item[:3], _used_left, _used_left2,
                     [ln for ln in _o_item if "喝下" in ln]))
    if _o_none != [_r("COMBAT_ITEM_BAD", name="伤药")]:
        _B23.append(("用物 没带", _o_none))
    _clear23(gid="")
    chk("★ `使用 <药>`（战斗口径 · 直调 · G2 起一手一手）：第 1 手真喝（背包 3 → %s）· "
        "同一场第 2 手出「%s」并回落成普攻（背包仍是 %s）· 没带就一句实话（不开打）"
        % (_used_left, (TX.get("COMBAT_ITEM_CAP") or {}).get("value", "")[:10], _used_left2),
        not [x for x in _B23 if str(x[0]).startswith("用物")],
        "%s" % [x for x in _B23 if str(x[0]).startswith("用物")][:2])

    # ── 五、集火：单人明确回话（不动档、不开战斗）────────────────────────────────
    #   ★ F6（QA P3）：**三档分得开** —— 认得出 / 认不出这个名字 / 空着没点名。
    #     改前「认不出」与「空着」回的是**同一句**（掉进「没组队」那句），玩家以为自己点对了。
    _o_focus1, _s_focus1 = _say23(dict(_BASE23), "集火 %s" % _MON23[_MS23]["name"])
    _o_focus2, _s_focus2 = _say23(dict(_BASE23), "集火 谁都不认识的名字")
    _o_focus3, _s_focus3 = _say23(dict(_BASE23), "集火")
    if _o_focus1 != [_r("COMBAT_FOCUS_NAMED", name=_MON23[_MS23]["name"])] \
            or _o_focus2 != [_r("COMBAT_FOCUS_MISS", name="谁都不认识的名字")] \
            or _o_focus3 != [_r("COMBAT_FOCUS_SOLO")] \
            or _o_focus1 == _o_focus2 or _o_focus2 == _o_focus3 \
            or _s_focus1 != dict(_BASE23) or _s_focus2 != dict(_BASE23) \
            or _s_focus3 != dict(_BASE23):
        _B23.append(("集火", _o_focus1, _o_focus2, _o_focus3))
    chk("★ `集火 <目标>`：域里认得出来的那只 ⇒ 一句明确回话（不假装锁上了谁）· 认不出 ⇒ 另一句 ·"
        "**三档三句话各不相同**（认得出 / 认不出 / 空着）· **三档都不动档、都不开战斗**",
        not [x for x in _B23 if x[0].startswith("集火")],
        "%s" % [x for x in _B23 if x[0].startswith("集火")][:2])

    # ── 六、换武器：真换上 + 吃一手（野外）/ 只换手（镇里）──────────────────────
    #    ★ 声明里这条没有参数（`^换武器$`）⇒ 换哪一件由数据说话（背包里 id 序第一件、
    #      且不是手上那件）—— 判据照这个现算，不手打期望值
    _wpn_name = (_IT9.get(_WPN23) or {}).get("name", _WPN23)
    _o_town, _s_town = _say23(dict(_BASE23, loc="windmill_town", node="wt_gate_n",
                                   bag={_WPN23: 1}), "换武器", pin=None)
    _o_wild, _s_wild = _say23(dict(_BASE23, bag={_WPN23: 1}), "换武器")
    _f_wild = _field23()
    _o_none2, _s_none2 = _say23(dict(_BASE23), "换武器")
    _o_ask, _s_ask = _say23(dict(_BASE23), "换武器", pin=None)
    if _o_town[:1] != [_r("SYS_GEAR_EQUIP_OK", icon=(_IT9.get(_WPN23) or {}).get("icon", ""),
                          name=LPICK.label_of(_WPN23),
                          kind=(_IT9.get(_WPN23) or {}).get("kind", ""))] \
            or (_s_town.get("equipped") or {}).get("weapon") != _WPN23 \
            or (_s_town.get("bag") or {}):
        _B23.append(("换武器 镇里", _o_town[:2], _s_town.get("equipped")))
    if (_s_wild.get("equipped") or {}).get("weapon") != _WPN23 \
            or _f_wild is None or int(_f_wild.get("hands") or 0) != 1 \
            or _o_wild[:1] != [_MEET23] \
            or not any(ln.startswith((TX.get("COMBAT_SWAP_OK") or {}).get("value", "")
                                     .split("{icon}")[0] or "\0") for ln in _o_wild):
        _B23.append(("换武器 野外·吃一手", _o_wild[:3], _s_wild.get("equipped"),
                     None if _f_wild is None else _f_wild.get("hands")))
    # 带两件 ⇒ 换上 id 序第一件、另一件只提示（不静默吞掉）
    _wpn2 = sorted(k for k, v in (_IT9 or {}).items()
                   if isinstance(v, dict) and v.get("slot") == "weapon" and k < _WPN23)[:1]
    if _wpn2:
        _o_two, _s_two = _say23(dict(_BASE23, bag={_WPN23: 1, _wpn2[0]: 1}), "换武器")
        if (_s_two.get("equipped") or {}).get("weapon") != _wpn2[0] \
                or _r("COMBAT_SWAP_ASK", list="『%s』" % LPICK.label_of(_WPN23)) not in _o_two:
            _B23.append(("换武器 带两件", _o_two[:3], _s_two.get("equipped")))
    if _o_none2 != [_r("COMBAT_SWAP_NONE")] or _s_none2.get("equipped"):
        _B23.append(("换武器 没得换", _o_none2))
    if _o_ask != [_r("COMBAT_SWAP_NONE")] or _s_ask.get("equipped"):
        _B23.append(("换武器 背包里没武器", _o_ask))
    chk("★ `换武器` 真敲：没得打那儿只换手（%s · 回现成的装备那一句）· 野外**换上了 + 这一手"
        "花在换手上**（这一场真起来、真花掉一手）· 带两件时换第一件并把另一件列出来 · "
        "没得换一句实话" % _wpn_name,
        not [x for x in _B23 if x[0].startswith("换武器")],
        "%s" % [x for x in _B23 if x[0].startswith("换武器")][:2])

    # ── 七、没遇敌那一档 + `攻击` 那一支 + 文案面扫一遍 ──────────────────────────
    _o_nofoe, _s_nofoe = _say23(dict(_BASE23), "打断", pin=None)
    if _o_nofoe != [_r("COMBAT_NEED_FOE")] or _s_nofoe != dict(_BASE23):
        _B23.append(("没遇敌那一档", _o_nofoe))
    # ★ G2 换向：`攻击` 不再一次打完 —— 判据改成「同一套：遇敌 + 四段式那一屏 + 这一场起来」
    #   （改前那两条读法：`打完` / 死亡那一行 + 写 `last_battle`；分段之后那是**结算期**的事）
    _o_atk, _s_atk = _say23(dict(_BASE23), "攻击")
    _f_atk = _field23()
    _TURN_PRE23 = (TX.get("COMBAT_TURN_STATE") or {}).get("value", "").split("{")[0]
    if _o_atk[:1] != [_MEET23] or _f_atk is None \
            or int(_f_atk.get("hands") or 0) != 1 \
            or not any(str(ln).startswith(_TURN_PRE23) for ln in _o_atk):
        _B23.append(("攻击 那一支", _o_atk[:3]))
    chk("★ 没遇敌 ⇒ 一句「%s」（**档一个字不动**）· `攻击` 那一支照同一套（遇敌 + 四段式那一屏"
        "«现状/谁先动/对方在干什么/你的选项» + 这一场起来、真花掉一手）"
        % (TX.get("COMBAT_NEED_FOE") or {}).get("value", "")[:12],
        not [x for x in _B23 if x[0] in ("没遇敌那一档", "攻击 那一支")],
        "%s" % [x for x in _B23 if x[0] in ("没遇敌那一档", "攻击 那一支")][:2])

    _ALL23 = (_o_int + _o_sk_bad + _o_sk_nocls + _o_sk_ok + _o_item + _o_none
              + _o_focus1 + _o_focus2 + _o_ask + _o_town + _o_wild + _o_none2
              + _o_nofoe + _o_atk)
    _leak23 = [ln[:44] for ln in _ALL23
               if "[MISSING TEXT" in ln or _POT23 in ln or _WPN23 in ln
               or _MS23 in ln or _MF23 in ln or "ms_skill" in ln]
    chk("★ 六条 + 对照那一批回话（%d 行）里没有取不到文案 / 没有物品·怪·怪的技能 id"
        % len(_ALL23), not _leak23, "%s" % _leak23[:3])

    # ── 八、声明面（本批新加的那两份 rules）现解析对账 ──────────────────────────
    with open(os.path.join(str(REPO), "content", "rules", "battle_cmds.json"),
              encoding="utf-8") as _f23:
        _RULES23 = json.load(_f23)
    with open(os.path.join(str(REPO), "content", "rules", "action_base.json"),
              encoding="utf-8") as _f23b:
        _AB23 = json.load(_f23b)
    chk("★ 上限只有一个口：声明表 `item_uses_per_battle` = %s ↔ 实现真读到的 %s（不手打）"
        % (_RULES23.get("item_uses_per_battle"), BA23.rules().get("item_uses_per_battle")),
        BA23.rules().get("item_uses_per_battle") == _RULES23.get("item_uses_per_battle"))
    # ★ P-57：`逃跑` 的失败率也走同一张声明表（同一个读口）——
    #   「代码里不写这个数」那条由 `probe_party ⑦` 的 ast 守卫钉着（那一手里除 0/1 没有别的数）
    chk("★ P-57 失败率也只有一个口：声明表 `flee_fail_pct` = %s ↔ `battle_acts.flee_fail_pct()` = %s"
        % (_RULES23.get("flee_fail_pct"), BA23.flee_fail_pct()),
        _RULES23.get("flee_fail_pct") == BA23.flee_fail_pct())
    chk("★ 本批新加的两个行动类别都在声明表里（interrupt / swap 各两段耗时）：%s"
        % ", ".join("%s=%s/%s" % (c, _AB23["cast"].get(c), _AB23["recover"].get(c))
                    for c in ("interrupt", "swap")),
        all(c in _AB23["cast"] and c in _AB23["recover"] for c in ("interrupt", "swap")))
except Exception as exc:                                                  # noqa: BLE001
    chk("★ B3-23 战斗那六条跑得起来（真宿主契约）", False,
        "%s: %s" % (type(exc).__name__, exc))


# ══════════════════════════════════════════════════════════════
# ★ B4-10：取参**一个口**（`content/argv.py`）—— 别名与参连写 + 裸指令名
# ══════════════════════════════════════════════════════════════
print("⑮ ★ B4-10：参跟着该指令**自己的声明**走 —— 连写也取得到参 · 裸指令名照实说")
try:
    from content import argv as AV15                                    # noqa: E402
    _IT15 = st.domain("items") or {}
    _SK15 = st.domain("skills") or {}
    _W15 = "i_weapon_knight_wall_common"
    _M15 = "i_material_iron_scrap"
    _L15 = max((int(v.get("lv") or 1), k, v) for k, v in _SK15.items()
               if v.get("owner_class") == "cls_knight")
    _L15N, _L15LV = _L15[2].get("name"), int(_L15[2].get("lv") or 1)
    _LV15 = 5
    chk("★ 三条 fixture 都在域里（%s / %s / %s 要到 %d 级）"
        % (_W15, _M15, _L15N, _L15LV),
        _W15 in _IT15 and _M15 in _IT15 and bool(_L15N) and _L15LV > _LV15)

    def _usage15(key):
        """玩家看见的那个词（`usage` 第一个词）—— 从声明取，不手写。"""
        return str((AV15.decl(key).get("usage") or "")).split(" ")[0]

    _SEED15 = {"cls": "cls_knight", "race": "human", "name": "试炼者", "level": _LV15,
               "exp": 0, "gold": 0, "hp": 116, "loc": "windmill_town", "node": "wt_gate_n",
               "prev": [], "bag": {_W15: 1, _M15: 2}, "equipped": {}, "codex": {}, "flags": {}}

    def _say15(seed, text):
        """真宿主真敲一条（造档起手 · 钟钉死）—— 与别处同形，不新建形状。"""
        _db15 = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp",
                             "ast_probe_cmds_b410.db")
        try:
            os.remove(_db15)
        except OSError:
            pass
        _ad15 = _Ad([], seed=dict(seed))
        _h15 = Host(_ad15, str(REPO), inject={"db_path": _db15, "clock": lambda: _FIXED})
        _h15.boot()
        _ad15.out.clear()
        _h15.handle({"uid": "u_c", "group_id": "g_c", "text": text})
        return list(_ad15.out), (_ad15.saved or {})

    # ── 一、别名与参**连写** == 主词 + 空白（回话与档上副作用逐字相同）
    _B15 = []
    for _k15, _sp15, _nm15 in (("equip", "装", _IT15[_W15].get("name")),
                               ("item_drop", "丢", _IT15[_M15].get("name")),
                               ("item_sell", "卖", _IT15[_M15].get("name")),
                               ("skill_learn", "学", _L15N)):
        _a_o15, _a_s15 = _say15(_SEED15, "%s %s" % (_usage15(_k15), _nm15))
        _b_o15, _b_s15 = _say15(_SEED15, "%s%s" % (_sp15, _nm15))
        if not _a_o15 or _b_o15 != _a_o15 or _b_s15 != _a_s15:
            _B15.append((_k15, _nm15, _b_o15[:2], _a_o15[:2]))
    chk("★ 别名与参**连写**（装/丢/卖/学 + 名字，不给空白）取到同一个参：回话与档上副作用"
        "与「主词 + 空白」逐字相同（原先连写取到空参 ⇒ 回带空引号的错话）",
        not _B15, "%s" % _B15[:2])

    # ── 二、裸指令名 ⇒ 各自那一句 ASK（逐字对账 texts）· 档一个字不动
    _BARE15 = (("equip", "SYS_GEAR_EQUIP_ASK"), ("item_drop", "SYS_DROP_ASK"),
               ("item_sell", "SYS_SELL_ASK"), ("skill_learn", "SYS_SKILL_LEARN_ASK"))
    _bb15 = []
    for _k15, _slot15 in _BARE15:
        _o15, _s15 = _say15(_SEED15, _usage15(_k15))
        if _o15 != [_r(_slot15)] or _s15 != dict(_SEED15):
            _bb15.append((_k15, _o15[:2], [k for k in (_s15 or {}) if
                                           _s15.get(k) != _SEED15.get(k)]))
    chk("★ 裸指令名（%s —— 帮助里就写着这几个词）各自回那一句 ASK，且**档一个字不动**"
        "（原先回「背包里没有『』」这类空引号错话）"
        % " · ".join(_usage15(k) for k, _s in _BARE15),
        not _bb15, "%s" % _bb15[:2])

    # ── 三、覆盖面（静态）：凡带「单字别名」的声明，别名与参连写都要取得到参
    _one15 = []
    for _k15, _d15 in sorted(DECL.items()):
        if not (_d15 or {}).get("visible", True):
            continue
        _al15 = [p for p in (_d15.get("patterns") or []) if len(AV15.lit_prefix(p)) == 1]
        if not _al15:
            continue
        _e15 = type("_E15", (object,), {"text": "x", "key": _k15})()
        _e15.text = AV15.lit_prefix(_al15[0]) + "某个名字"
        _got15 = AV15.arg_of(_e15)
        if _got15 != "某个名字":
            _one15.append((_k15, AV15.lit_prefix(_al15[0]), _got15))
    chk("★ 覆盖面：凡带「单字别名」的声明都按**自己声明的**前缀剥参（%d 条）——"
        " 别名与参连写取得到参，取不到就红（K64 ① 那一族）"
        % len([1 for _k, _d in DECL.items()
               if (_d or {}).get("visible", True)
               and any(len(AV15.lit_prefix(p)) == 1 for p in (_d.get("patterns") or []))]),
        not _one15, "%s" % _one15[:3])
except Exception as exc:                                                  # noqa: BLE001
    chk("★ B4-10 取参那个口跑得起来（真宿主契约）", False,
        "%s: %s" % (type(exc).__name__, exc))


# ══════════════════════════════════════════════════════════════
# ★ B4-11：`cmds_ast` 里那几处手切也收进同一个口（建号两条 / 去 / 加点 / 读）
# ══════════════════════════════════════════════════════════════
print("⑯ ★ B4-11：`cmds_ast` 的手切收进 `content/argv.py` —— 连写 == 带空白（真宿主真敲）")
try:
    _BASE16 = {"cls": "cls_knight", "race": "human", "name": "试炼者", "level": 3,
               "exp": 0, "gold": 0, "hp": 116, "loc": "windmill_town", "node": "wt_gate_n",
               "prev": [], "bag": {"i_material_iron_scrap": 2}, "equipped": {},
               "codex": {}, "flags": {}}
    _POI16 = "镇口的石头"
    _C16 = (("我是", "我是%s", {"cls": "cls_knight", "level": 1, "loc": "windmill_town",
                                "node": "wt_gate_n", "bag": {}, "equipped": {},
                                "codex": {}, "flags": {}}, "人类"),
            ("选职业", "选职业%s", _BASE16, "骑士"),
            ("去", "去%s", _BASE16, "北墙根"),
            ("加点", "加点%s", _BASE16, "智力 2"),
            ("读", "读%s", _BASE16, _POI16))
    _B16 = []
    for _w16, _form, _sd16, _arg16 in _C16:
        _a_o16, _a_s16 = _say15(_sd16, "%s %s" % (_w16, _arg16))
        _b_o16, _b_s16 = _say15(_sd16, _form % _arg16)
        if not _a_o16 or _b_o16 != _a_o16 or _b_s16 != _a_s16:
            _B16.append((_w16, _arg16, _b_o16[:2], _a_o16[:2]))
    chk("★ 五条（我是 / 选职业 / 去 / 加点 / 读）别名与参**连写** == 主词 + 空白："
        "回话与**档上副作用**逐字相同（原先连写被当成「没带参」⇒ 静默丢掉玩家写的词）",
        not _B16, "%s" % _B16[:2])

    # ── 覆盖面（静态）：剥指令词那种手切只许在 `content/argv.py` 里（一个口）
    _p16 = REPO / "content"
    _files16 = sorted(_p16.glob("*.py"))
    _hand16 = {}
    for _f16 in _files16:
        _txt16 = _f16.read_text(encoding="utf-8")
        if "split(None, 1)" in _txt16:
            _hand16[_f16.name] = _txt16.count("split(None, 1)")
    chk("★ 覆盖面：剥指令词的 `split(None, 1)` 只许在 `content/argv.py` 里（%d 个 content/*.py 全扫）"
        "—— 谁在别处再手切一次，这里当场红（K71 ②）"
        % len(_files16),
        list(_hand16) == ["argv.py"], "%s" % _hand16)
except Exception as exc:                                                  # noqa: BLE001
    chk("★ B4-11 那五条跑得起来（真宿主契约）", False,
        "%s: %s" % (type(exc).__name__, exc))

# ══════════════════════════════════════════════════════════════
# ★ B4-12：地点守卫**一个口**（`guard_desc` 写着「在镇上 / 在公会 / 在铺子 / 在客栈」那一族）
# --------------------------------------------------------------
# 真 bug（端到端玩出来的）：同一条 `guard_desc` 原先有**两种实现** —— 客栈 / 教堂 / 旧货 / 登记 /
# 商队判脚下，而 **公会 / 悬赏 / 看 <编号> / 铁匠铺 一句都不判**：人站在骨田照样把挂板墙看个遍、
# 把活接了，而同一个位置『登记』回的是「这几处都在镇上」。现在全部走 `cmds_ast.town_gate`。
# 判据三层：
#   ① 真宿主三档（野外 / 镇上没走到那一站 / 站到了）逐条真敲、整段逐字对账
#   ② 覆盖面（静态）：凡 `guard_desc` 点名地点的那几条，handler 必须调 `town_gate`（ast 扫真调用）
#   ③ 镇子 id 的字面量只许在 `cmds_ast.py`（TOWN 那一行）与 `apply.py`（宿主那半边初始档）
# ══════════════════════════════════════════════════════════════
print("⑰ ★ B4-12：地点守卫一个口 —— 三档真敲（野外 / 镇上错站 / 站到了）+ 覆盖面")
try:
    import ast as _ast17
    from content import cmds_ast as CA17                               # noqa: E402
    from content import cmds_places as CPL17                           # noqa: E402
    from content import town as TW17                                   # noqa: E402

    _WILD17 = ("belt_north", "bn_bone")
    _GATE17 = ("windmill_town", "wt_gate_n")
    _IRON17 = "i_material_iron_scrap"
    _IRONN17 = str((st.domain("items") or {}).get(_IRON17, {}).get("name") or "")

    def _nn17(node):
        return str(CA17._name_of_node(TW17.TOWN, node))

    _BRD17 = TW17._func_node("board")          # 挂板墙（玛莎）
    _FRG17 = TW17._func_node("smith")          # 半截铁砧（柯尔）
    _HRS17 = TW17._func_node("heal")           # 白烛堂（艾德）
    _INN17 = CPL17.STASH_NODE                  # 转叶客栈（箱子那一站）
    chk("★ 四个站点现算得出来（挂板墙 %s / 铁匠铺 %s / 教堂 %s / 客栈 %s）—— 数据驱动，不写死节点 id"
        % (_BRD17, _FRG17, _HRS17, _INN17),
        all((_BRD17, _FRG17, _HRS17, _INN17)) and len({_BRD17, _FRG17, _HRS17, _INN17}) == 4)

    _db17 = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_cmds_b412.db")
    try:
        os.remove(_db17)
    except OSError:
        pass
    _SEED17 = {"cls": "cls_knight", "race": "human", "name": "试炼者", "level": 3, "exp": 0,
               "gold": 50, "hp": 116, "prev": [], "bag": {_IRON17: 2}, "equipped": {},
               "codex": {}, "flags": {}}
    _ad17 = _Ad([], seed=dict(_SEED17))
    _h17 = Host(_ad17, str(REPO), inject={"db_path": _db17, "clock": lambda: _FIXED})
    _h17.boot()

    def _say17(text):
        _ad17.out.clear()
        _h17.handle({"uid": "u_c", "group_id": "g_c", "text": text})
        return list(_ad17.out)

    def _stand17(loc, node):
        _ad17.saved["loc"] = loc
        _ad17.saved["node"] = node

    #    label         敲的          那一站(None = 不核站)  不在镇上那一句        站到了首行
    _CASES17 = (
        ("公会", "公会", _BRD17, "SYS_PLACE_NOTOWN", "SYS_GUILD_HEAD"),
        ("悬赏", "悬赏", _BRD17, "SYS_PLACE_NOTOWN", "SYS_BOARD_HEAD"),
        ("看 <编号>", "看 1", _BRD17, "SYS_PLACE_NOTOWN", None),
        ("铁匠铺", "铁匠铺", _FRG17, "SYS_PLACE_NOTOWN", "SYS_ENHANCE_SHOP"),
        ("登记", "登记", _BRD17, "SYS_PLACE_NOTOWN", None),
        ("客栈", "客栈", _INN17, "SYS_PLACE_NOTOWN", "SYS_PLACE_HEAD"),
        ("教堂", "教堂", _HRS17, "SYS_PLACE_NOTOWN", "SYS_PLACE_HEAD"),
        ("旧货", "旧货", None, "SYS_PLACE_NOTOWN", "SYS_JUNK_HEAD"),
        ("商队", "商队", None, "SYS_PLACE_NOTOWN", "SYS_CARAVAN_HEAD"),
        ("卖出", "卖出 %s" % _IRONN17, None, "SYS_SELL_AWAY", None),
        ("存放", "存放 %s" % _IRONN17, _INN17, "SYS_STASH_AWAY", None),
    )

    _badA17, _badB17, _badC17 = [], [], []
    for _lab, _txt, _sta, _nt, _head in _CASES17:
        # ── 一、野外：这一族**一条都不许放行**，且回话只有那一句（不许顺手出面板）
        _stand17(*_WILD17)
        _ad17.saved["bag"] = {_IRON17: 2}
        _got = _say17(_txt)
        if _got != [_r(_nt)]:
            _badA17.append((_lab, _got[:2], [_r(_nt)]))
        if _sta is not None:
            # ── 二、在镇上、没走到那一站 ⇒ 指路（站名从 maps 现取）
            _stand17(*_GATE17)
            _ad17.saved["bag"] = {_IRON17: 2}
            _away_slot = "SYS_STASH_AWAY" if _nt == "SYS_STASH_AWAY" else "SYS_PLACE_AWAY"
            _got = _say17(_txt)
            if _got != [_r(_away_slot, name=_nn17(_sta))]:
                _badB17.append((_lab, _got[:2], [_r(_away_slot, name=_nn17(_sta))]))
        # ── 三、站到了 ⇒ 不许再回那两句（放行，且头一行是它自己的那一句）
        _stand17(TW17.TOWN, _sta if _sta is not None else "wt_gate_n")
        _ad17.saved["bag"] = {_IRON17: 2}
        _got = _say17(_txt)
        _blocked = (_r("SYS_PLACE_NOTOWN"), _r(_nt), _r("SYS_STASH_AWAY"),
                    _r("SYS_PLACE_AWAY", name=_nn17(_sta)) if _sta else "")
        if not _got or _got[0] in _blocked:
            _badC17.append((_lab, _got[:2], "放行（首行不是被拦的那几句）"))
        _want17 = _r(_head, name=_nn17(_sta)) if _head == "SYS_PLACE_HEAD" else (_r(_head) if _head else "")
        if not _got or _got[0] in _blocked:
            _badC17.append((_lab, _got[:2], "放行（首行不是被拦的那几句）"))
        elif _want17 and _got[0] != _want17:
            _badC17.append((_lab, _got[:1], _want17))

    chk("★ 野外（骨田）：这一族 **%d 条**一条都不放行 —— 各自只回自己那一句（面板一句都不许漏）"
        % len(_CASES17), not _badA17, "%s" % _badA17[:3])
    chk("★ 镇上但没走到那一站（北口）：公会 / 悬赏 / 看 / 铁匠铺 / 登记 / 客栈 / 教堂 / 存放 "
        "⇒ 一律**指路**（站名从 `maps` 现取）", not _badB17, "%s" % _badB17[:3])
    chk("★ 站到了 ⇒ 放行（首行是它自己那一句，不再是那两句拦话）", not _badC17, "%s" % _badC17[:3])

    # ── 覆盖面（静态）①：凡 `guard_desc` 点名地点的声明，handler 必须**真调** `town_gate`
    _CALL17 = {}
    for _f in sorted((REPO / "content").glob("*.py")):
        _tree = _ast17.parse(_f.read_text(encoding="utf-8"))
        for _n in _ast17.walk(_tree):
            if isinstance(_n, (_ast17.FunctionDef, _ast17.AsyncFunctionDef)):
                if any(isinstance(x, _ast17.Call) and getattr(x.func, "id", "") == "town_gate"
                       for x in _ast17.walk(_n)):
                    _CALL17.setdefault(_f.name, set()).add(_n.name)
    _LOCWORDS17 = ("在镇上", "在公会", "在铺子", "在客栈")
    _miss17, _n17, _skip17 = [], 0, []
    for _k, _d in sorted(DECL.items()):
        if not any(w in str(_d.get("guard_desc") or "") for w in _LOCWORDS17):
            continue
        _hs = str((_d.get("bind") or {}).get("handler") or "")
        if not _hs:                       # 还没接处理器的（⑨ 的 UNBOUND 名单管着）—— 守卫无处可落
            _skip17.append(_k)
            continue
        _n17 += 1
        _mod, _fn = _hs.split(":")
        if _fn not in _CALL17.get(_mod.split(".")[-1] + ".py", set()):
            _miss17.append((_k, _hs))
    chk("★ 覆盖面①：凡 `guard_desc` 点名地点、且**已接处理器**的那 %d 条，handler 都**真调**"
        " `town_gate`（ast 扫真调用，不扫注释/文档串）—— 谁再自己写一遍 `p[\"loc\"] != TOWN`，"
        "这里当场红（还没接处理器的那 %d 条不在内：%s）"
        % (_n17, len(_skip17), " · ".join(_skip17)),
        not _miss17, "%s" % _miss17[:4])

    # ── 覆盖面（静态）②：镇子 id 的字面量只许在基座模块与宿主那半边的初始档
    _lit17 = {}
    for _f in sorted((REPO / "content").glob("*.py")):
        _t17 = _f.read_text(encoding="utf-8")
        if "\"windmill_town\"" in _t17:
            _lit17[_f.name] = _t17.count("\"windmill_town\"")
    chk("★ 覆盖面②：镇子 id 的字面量只许在 `cmds_ast.py`（`TOWN` 那一行）与 `apply.py`"
        "（宿主那半边初始档）—— 谁再抄一份，这里红", _lit17 == {"cmds_ast.py": 1, "apply.py": 1},
        "%s" % _lit17)
except Exception as exc:                                                  # noqa: BLE001
    chk("★ B4-12 地点守卫那一族跑得起来（真宿主契约）", False,
        "%s: %s" % (type(exc).__name__, exc))


# ══════════════════════════════════════════════════════════════
# ★ B4-13：裸触发词照实说（第 2 刀）—— 覆盖面 + 真宿主真敲
# ══════════════════════════════════════════════════════════════
print("⑱ ★ B4-13：裸触发词（帮助里写着的那些词**本身**）照实说 —— 覆盖面 + 真宿主真敲")
try:
    from content.argv import lit_prefix as _lp18

    # ── ① 覆盖面：凡可见声明的每个 pattern 的**字面量前缀**，单独出现都必须被某条可见声明接住
    _words18, _miss18 = {}, []
    for _k, _d in sorted(DECL.items()):
        if (_d or {}).get("visible", True) is False:
            continue
        for _p in (_d.get("patterns") or []):
            _w = _lp18(_p)
            if _w:
                _words18.setdefault(_w, []).append(_k)
    for _w in _words18:
        if getattr(REG.first_hit(_w, visible_only=True), "key", None) is None:
            _miss18.append((_w, _words18[_w]))
    chk("★ 覆盖面：每个触发词 / 别名**单独出现**都接得住（%d 个词）—— 一个都不许落到宿主那句"
        "「没有命中包内任何指令声明；输入 /help 看宿主命令」（K71 第 2 刀）" % len(_words18),
        not _miss18, "落空：%s" % (_miss18[:6],))

    # ── ② 真宿主真敲：这一批补的那些词（= 自己那条声明**要参**、而它同时有 `^词$` 裸 pattern 的）
    _batch18 = sorted(_w for _w in _words18
                      if any(("^" + _w + "$") in (DECL[_k].get("patterns") or []) for _k in _words18[_w])
                      and any("(" in _p for _k in _words18[_w]
                              for _p in (DECL[_k].get("patterns") or [])))
    _SEED18 = {"cls": "cls_knight", "race": "human", "name": "试炼者", "level": 5,
               "exp": 0, "gold": 100, "hp": 116, "loc": "windmill_town", "node": "wt_inn",
               "prev": [], "bag": {}, "equipped": {}, "codex": {}, "flags": {}}
    _DIRTY18 = ("没有命中包内任何指令声明", "/help", "content/", "commands.py", "『』")
    # ★ fix5-nav：屏幕上的**站名**也是一族裸触发词（敲了 = 『去 <名>』，名字从 maps 现读）——
    #   它们**本来就该动档**，动的是「人在哪」那几格。于是这一条判据**加严**成两档：
    #     · 站名        ⇒ 只许动移动那四格（loc / node / prev / foot），别的格一个字不许动；
    #     · 其余裸触发词 ⇒ 照旧**一个字不动**（裸「放弃」拿 act[0] 顶上那类会当场红）。
    _PLACE18 = {str(_n.get("name")) for _m in (st.domain("maps") or {}).values()
                for _n in (_m.get("nodes") or [])}
    _MOVE18 = ("loc", "node", "prev", "foot")
    # ★ fix5-nav：`_p()` 出档时会**派生**几格（生命/法力上限与现值 —— 唯一来源是职业面板）。
    #   那不是「这条指令动了档」，是出档口按面板算出来的 ⇒ 逐键对账时把这几格排除
    #   （排除的是**派生键**这个集合本身，不是某一个写死的名字）。
    from content.cmds_ast import _p as _p18
    _DERIVED18 = set(_p18(dict(_SEED18))) - set(_SEED18)
    _bad18, _n18 = [], 0
    for _w in _batch18:
        _o18, _s18 = _say15(_SEED18, _w)
        _n18 += 1
        _txt = "\n".join(_o18)
        _dirty = [d for d in _DIRTY18 if d in _txt]
        _moved = [k for k in set(list(_SEED18) + list(_s18 or {}))
                  if k not in _DERIVED18 and (_s18 or {}).get(k) != _SEED18.get(k)]
        _illegal = [k for k in _moved if not (_w in _PLACE18 and k in _MOVE18)]
        if not _o18 or _dirty or _illegal:
            _bad18.append((_w, _dirty, _o18[:2], _illegal))
    chk("★ 真敲这一批的 %d 个裸触发词：回话都是人话（没漏宿主那句兜底 / `/help` / 内部路径 / "
        "空引号「『』」）—— 站名只许动移动那四格（%s），其余裸触发词**档一个字不动**"
        "（裸「放弃」原先会拿 `act[0]` 顶上 ⇒ 当场丢一条委托）"
        % (_n18, " / ".join(_MOVE18)), not _bad18, "%s" % (_bad18[:4],))
except Exception as exc:                                                  # noqa: BLE001
    chk("★ B4-13 裸触发词那一族跑得起来（真宿主契约）", False,
        "%s: %s" % (type(exc).__name__, exc))


# ══════════════════════════════════════════════════════════════
# ★ B4-14：登记那一个门 —— 「办过证没有」只有一个判法
# ══════════════════════════════════════════════════════════════
print("⑲ ★ B4-14：`登记` 的证是**一个门** —— 无证档 `我的委托` 不许印「【评级】见习」")
try:
    import ast as _ast19

    _SEED19 = {"cls": "cls_knight", "race": "human", "name": "试炼者", "level": 3, "exp": 0,
               "gold": 0, "hp": 116, "loc": "windmill_town", "node": "wt_gate_n",
               "prev": [], "bag": {}, "equipped": {}, "codex": {}, "flags": {}}
    _rank19 = _r("SYS_MINE_RANK", tier=TX["RANK_APPRENTICE"]["value"])

    # ── ① 无证档：`我的委托` 不印那半句 · `评级` 回「你还没有证」
    _o19a, _s19a = _say15(_SEED19, "我的委托")
    _o19b, _ = _say15(_SEED19, "评级")
    _BAD_Y19 = ("【评级】", "见习")
    _bad19 = []
    _txt19a = "\n".join(_o19a)
    if any(x in _txt19a for x in _BAD_Y19):
        _bad19.append(("无证 · 我的委托 印了评级那半句", _o19a[-2:]))
    if _o19b != [_r("SYS_RANK_NOCARD")]:
        _bad19.append(("无证 · 评级", _o19b[:2]))
    chk("★ 无证档（没打过『登记』）：`我的委托` **不印**那半句评级（原先照印「【评级】见习」—— "
        "与同一刻的『评级』回话直接打架）· `评级` 照旧回「你还没有证」",
        not _bad19, "%s" % (_bad19[:2],))

    # ── ② 有证档：两处印的**是同一句**（同一个槽位、逐字）
    _o19c, _ = _say15(dict(_SEED19, flags={"card": 1}), "我的委托")
    _o19d, _ = _say15(dict(_SEED19, flags={"card": 1}), "评级")
    chk("★ 有证档：`我的委托` 与 `评级` 印的**是同一句**（同一个槽位 `SYS_MINE_RANK`，逐字）"
        "—— 一件事一个门、一处文案",
        _rank19 in _o19c and _o19d and _o19d[0] == _rank19, "%s / %s" % (_o19c[-1:], _o19d[:1]))

    # ── ③ 覆盖面（静态）：读 `flags["card"]` 只许一处（has_card）· 写只许一处（register）
    _read19, _write19 = [], []
    for _f in sorted((REPO / "content").glob("*.py")):
        _tree19 = _ast19.parse(_f.read_text(encoding="utf-8"))
        for _n in _ast19.walk(_tree19):
            if (isinstance(_n, _ast19.Call) and isinstance(_n.func, _ast19.Attribute)
                    and _n.func.attr == "get" and _n.args
                    and getattr(_n.args[0], "value", None) == "card"):
                _read19.append("%s:%d" % (_f.name, _n.lineno))
            if (isinstance(_n, _ast19.Subscript) and isinstance(_n.ctx, _ast19.Store)
                    and getattr(_n.slice, "value", None) == "card"):
                _write19.append("%s:%d" % (_f.name, _n.lineno))
    chk("★ 覆盖面（静态）：**读** `flags[\"card\"]` 只有一处（`cmds_self.has_card`）· "
        "**写** 只有一处（`cmds_self.register`）—— 谁再自己读一遍那一格，这里当场红",
        len(_read19) == 1 and _read19[0].startswith("cmds_self.py")
        and len(_write19) == 1 and _write19[0].startswith("cmds_self.py"),
        "读 %s · 写 %s" % (_read19, _write19))
except Exception as exc:                                                  # noqa: BLE001
    chk("★ B4-14 登记那一个门跑得起来（真宿主契约）", False,
        "%s: %s" % (type(exc).__name__, exc))


# ══════════════════════════════════════════════════════════════
# ★ B4-25：`歇脚` 的「有篝火」守卫 —— 声明里写着（`guard_desc` = 有篝火 · 04 总表 §六 同一句），
#   原先代码里**没有执行面**（镇上 / 骨田 / 塔里一律回 20% 血）⇒ 三处营地篝火形同虚设。
# ══════════════════════════════════════════════════════════════
print("㉑ ★ B4-25：`歇脚` 的「有篝火」守卫（原先在哪儿都能歇 —— 声明里那条守卫没有执行面）")
try:
    import ast as _ast21

    _POIS21 = st.domain("pois") or {}
    _MAP21 = st.domain("maps") or {}
    _FIRES21 = sorted((str(v.get("map") or ""), str(v.get("subarea") or ""))
                      for v in _POIS21.values()
                      if isinstance(v, dict) and (v.get("effect") or {}).get("rest"))
    chk("★ 「能歇的地方」从 pois 域现读 —— %d 处（%s）· 名单一个字都不手写"
        % (len(_FIRES21), _FIRES21), len(_FIRES21) >= 1)
    _FM21, _FN21 = _FIRES21[0]
    _nodes21 = [n.get("id") for n in ((_MAP21.get(_FM21) or {}).get("nodes") or [])]
    chk("★ 那几处**都是真图上的真节点**（%s：%s ⇒ 图里 %s）"
        % (_FM21, _FN21, "在" if _FN21 in _nodes21 else "不在"), _FN21 in _nodes21)

    _SEED21 = {"cls": "cls_knight", "race": "human", "name": "试炼者", "level": 10, "exp": 0,
               "gold": 0, "hp": 60, "loc": "windmill_town", "node": "wt_gate_n",
               "prev": [], "bag": {}, "equipped": {}, "codex": {}, "flags": {}}

    def _say21(seed, text):
        _db21 = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp",
                             "ast_probe_cmds_b425.db")
        try:
            os.remove(_db21)
        except OSError:
            pass
        _ad21 = _Ad([], seed=dict(seed))
        _h21 = Host(_ad21, str(REPO), inject={"db_path": _db21, "clock": lambda: _FIXED})
        _h21.boot()
        _ad21.out.clear()
        _h21.handle({"uid": "u_c", "group_id": "g_c", "text": text})
        return list(_ad21.out), (_ad21.saved or {})

    _NOFIRE21 = _r("SYS_REST_NOFIRE")
    # ★ F6（QA P4 E-3）：没有火时**还要指出哪儿有火** —— 名单照 ㉑④ 同一口径**现算**
    #   （pois 域里挂 `effect.rest` 的那几处 → 它们所在节点的名字走 maps 域现读，一个字都不手写）。
    _FIRE_NODES21 = []
    for _v21 in _POIS21.values():
        if not (isinstance(_v21, dict) and (_v21.get("effect") or {}).get("rest")):
            continue
        _nm21 = next((str(n.get("name")) for n in
                      ((_MAP21.get(str(_v21.get("map") or "")) or {}).get("nodes") or [])
                      if n.get("id") == _v21.get("subarea")), "")
        if _nm21 and _nm21 not in _FIRE_NODES21:
            _FIRE_NODES21.append(_nm21)
    _HINT21 = _r("SYS_REST_FIRE_HINT", list=" · ".join("『%s』" % x for x in _FIRE_NODES21))
    chk("★ F6：没火那几档的回话里**指名哪儿有火**（名单现算 = %s；一个节点名都不手写）"
        % (" · ".join(_FIRE_NODES21) or "（域里没有火？）"), bool(_FIRE_NODES21), _HINT21)

    # ── ① 没有篝火的三档（镇上 / 骨田 / 塔里）⇒ 逐字回那一句 · 档一个字不动
    _bad21 = []
    for _lab21, _loc21, _nd21 in (("镇上（北口）", "windmill_town", "wt_gate_n"),
                                  ("骨田", "belt_north", "bn_bone"),
                                  ("塔里（塔门）", "old_watchtower", "tower_gate")):
        _o21, _s21 = _say21(dict(_SEED21, loc=_loc21, node=_nd21), "歇脚")
        if _o21 != [_NOFIRE21, _HINT21] or _s21.get("hp") != 60:
            _bad21.append((_lab21, _o21[:2], _s21.get("hp")))
    chk("★ 没有篝火的三档（镇上 / 骨田 / 塔里）⇒ 逐字回 `SYS_REST_NOFIRE` **+ 指路那一行**"
        "（★ F6：`歇脚棚` 那类地名会让人以为能歇 —— 光说「这儿没有」不够，得说清哪儿有），"
        "档**一个字不动**（血还是 60）—— 原先这三档一律回「生命 +20%」", not _bad21,
        "%s" % (_bad21[:2],))

    # ── ② 篝火那一站 ⇒ 真回血（上限的 20%，与 poI 那条 `effect.rest` 同一支）
    _mx21, _line21 = CA17.hp_cap_or_line(dict(_SEED21, hp=60))
    _want21 = 60 + max(1, int(_mx21 * 0.2)) if _mx21 else 0
    _o21b, _s21b = _say21(dict(_SEED21, loc=_FM21, node=_FN21), "歇脚")
    chk("★ 篝火那一站（%s / %s）⇒ 真回血：60 -> %d（上限 %s 的两成 · 期望值由 `hp_cap` 现算）"
        % (_FM21, _FN21, _want21, _mx21),
        bool(_mx21) and _s21b.get("hp") == _want21, "%s / hp=%s" % (_o21b[:2], _s21b.get("hp")))

    # ── ③ 同一个守卫也罩着『触摸篝火』那条路（`pois.effect.rest` 的消费端）
    _o21c, _s21c = _say21(dict(_SEED21, loc=_FM21, node=_FN21), "触摸")
    chk("★ 篝火那一站『触摸』照样能歇（`effect.rest` 那一条路与 `歇脚` 是同一支 `cmds_gather.rest`）",
        _s21c.get("hp") == _want21, "%s / hp=%s" % (_o21c[:3], _s21c.get("hp")))

    # ── ④ 覆盖面（静态）：`cmds_gather.py` 不许自己扫 `pois` 域；`rest` 必须真调 `_fire_here`
    _gf21 = (REPO / "content" / "cmds_gather.py").read_text(encoding="utf-8")
    _t21 = _ast21.parse(_gf21)
    _scan21, _call21 = [], []
    for _n21 in _ast21.walk(_t21):
        if (isinstance(_n21, _ast21.Call) and isinstance(_n21.func, _ast21.Name)
                and _n21.func.id == "_data" and _n21.args
                and getattr(_n21.args[0], "value", None) == "pois"):
            _scan21.append(_n21.lineno)
        if (isinstance(_n21, _ast21.Call) and isinstance(_n21.func, _ast21.Name)
                and _n21.func.id == "_fire_here"):
            _call21.append(_n21.lineno)
    _rest21 = next((_n for _n in _ast21.walk(_t21) if isinstance(_n, _ast21.AsyncFunctionDef)
                    and _n.name == "rest"), None)
    _in_rest21 = bool(_rest21) and any(
        isinstance(_n, _ast21.Call) and isinstance(_n.func, _ast21.Name)
        and _n.func.id == "_fire_here" and _n.lineno >= _rest21.lineno
        for _n in _ast21.walk(_rest21))
    chk("★ 覆盖面（静态）：`cmds_gather.py` 里**没有** `_data(\"pois\")`（脚下有没有火走 "
        "`_pois_here` 唯一那一口）· `rest` 自己真调 `_fire_here`（%s 处调用）"
        % len(_call21), not _scan21 and _in_rest21,
        "自扫 pois %s · rest 里真调 %s" % (_scan21, _in_rest21))
except Exception as exc:                                                  # noqa: BLE001
    chk("★ B4-25 歇脚那一条守卫跑得起来（真宿主契约）", False,
        "%s: %s" % (type(exc).__name__, exc))


# ══════════════════════════════════════════════════════════════
# ★ F6（QA P2 BUG⑧）：`触摸` 吃参数 —— 与同一 POI 上的 `读` 同一待遇
#   改前：`触摸 半埋的碑` 回「这句我没接住」，而 `读 半埋的碑` 通 ——
#   玩家想只摸某一件做不到，还得连带把整站的增益/消耗一并领走。
# ══════════════════════════════════════════════════════════════
print("㉒ ★ F6：`触摸 <东西>` 点名只摸那一件 · 名字对不上照实说（不静默换成「这儿没有可以上手的」）")
try:
    _POIS22 = st.domain("pois") or {}
    _by22 = {}
    for _pid22, _v22 in _POIS22.items():
        if isinstance(_v22, dict):
            _by22.setdefault((str(_v22.get("map") or ""), str(_v22.get("subarea") or "")),
                             []).append((str(_pid22), _v22))
    _spot22 = next((k for k, v in sorted(_by22.items()) if len(v) >= 2), None)
    chk("★ ① 域里真有「同一站两件以上」的地方（现算 · 不手写节点 id）：%s / %s ⇒ %d 件"
        % ((_spot22 or ("?", "?"))[0], (_spot22 or ("?", "?"))[1],
           len(_by22.get(_spot22) or [])),
        _spot22 is not None)

    # ── ② 声明面：`触摸` 与 `读` 取参的形状**一致**（都有带参的写法）
    _tp22 = list((DECL.get("touch") or {}).get("patterns") or [])
    _rp22 = list((DECL.get("read") or {}).get("patterns") or [])
    chk("★ ② 声明面：`触摸` 与 `读` 都带「点名」那一支（触摸 %d 条 / 读 %d 条 pattern · 都含 `(.+)`）"
        % (len(_tp22), len(_rp22)),
        any("(" in p for p in _tp22) and any("(" in p for p in _rp22), "%s" % (_tp22,))

    _SEED22 = {"cls": "cls_knight", "race": "human", "name": "试炼者", "level": 5, "exp": 0,
               "gold": 100, "hp": 116, "loc": _spot22[0], "node": _spot22[1],
               "prev": [], "bag": {}, "equipped": {}, "codex": {}, "flags": {}}
    _db22 = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_cmds_f6.db")

    def _say22(text, loc=None, node=None):
        _ad22 = _Ad([], seed=dict(_SEED22, loc=loc or _SEED22["loc"], node=node or _SEED22["node"]))
        _h22 = Host(_ad22, str(REPO), inject={"db_path": _db22, "clock": lambda: _FIXED})
        _h22.boot()
        _ad22.out.clear()
        _h22.handle({"uid": "u_c", "group_id": "g_c", "text": text})
        return list(_ad22.out)

    # ★ 挑地方：**不手写节点 id**，也不假定第一处两件都能上手（带门槛的那几件在这一刻可能
    #   `state == "no"`）—— 现算一个「裸『触摸』真摸到两件」的地方，再考取参那一支。
    _PREFIX22 = _r("SYS_TOUCH_GET", icon="\u0000", name="\u0000").split("\u0000")[0]
    _spot2 = _hit2 = None
    for _k22 in sorted(_by22):
        if len(_by22[_k22]) < 2:
            continue
        _o22 = _say22("触摸", loc=_k22[0], node=_k22[1])
        _hits22 = [_v for _pid, _v in _by22[_k22]
                   if any(x.startswith(_PREFIX22) and str(_v.get("name")) in x for x in _o22)]
        if len(_hits22) >= 2:
            _spot2, _hit2 = _k22, _hits22
            break
    chk("★ ① 现算出一个「裸『触摸』真摸到两件以上」的地方（不手写节点 id）：%s / %s ⇒ %s"
        % ((_spot2 or ("?", "?"))[0], (_spot2 or ("?", "?"))[1],
           " · ".join(str(v.get("name")) for v in (_hit2 or [])) or "（一处都没摸到两件？）"),
        _hit2 is not None)

    _one22 = _hit2[0].get("name")
    _other22 = _hit2[1].get("name")
    _got22 = _say22("触摸 %s" % _one22, loc=_spot2[0], node=_spot2[1])
    chk("★ ③ 点名 `触摸 %s` ⇒ **只**摸这一件（另一件「%s」一个字都不出）"
        % (_one22, _other22),
        _r("SYS_TOUCH_GET", icon=_hit2[0].get("icon", ""), name=_one22) in _got22
        and not any(_other22 in x for x in _got22), _got22)
    _all22 = _say22("触摸", loc=_spot2[0], node=_spot2[1])
    chk("★ ④ 反证：不带参照旧**全摸**（两件都在 ⇒ 取参那一支没把老口径顶掉）",
        _r("SYS_TOUCH_GET", icon=_hit2[0].get("icon", ""), name=_one22) in _all22
        and any(_other22 in x for x in _all22), _all22)
    _miss22 = _say22("触摸 压根没有这一件", loc=_spot2[0], node=_spot2[1])
    chk("★ ⑤ 名字对不上 ⇒ 自己的槽位（点名 + 把**能上手的**列出来），不是「这儿没有可以上手的」",
        _miss22 == [_r("SYS_TOUCH_MISS", name="压根没有这一件",
                       list=" · ".join("『%s』" % v.get("name") for v in _hit2))]
        and _r("SYS_TOUCH_NONE") not in _miss22, _miss22)
except Exception as exc:                                                  # noqa: BLE001
    chk("★ F6 `触摸` 取参那一族跑得起来（真宿主契约）", False,
        "%s: %s" % (type(exc).__name__, exc))


print("")
print("结果：全绿 ✓" if ok else "结果：有红 ✗")
sys.exit(0 if ok else 1)
