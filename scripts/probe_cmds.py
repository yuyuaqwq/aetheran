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

跑法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_cmds.py
"""
from __future__ import annotations

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


chk("★ `装备对比 拾荒人的重剑` 回的是 item_compare（改前回 equip）",
    _first("装备对比 拾荒人的重剑") == soon_text("item_compare"), _first("装备对比 拾荒人的重剑"))
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
except Exception as exc:                                                   # noqa: BLE001
    chk("★ P-23 3/3「读」那条接上了（真宿主契约）", False, "%s: %s" % (type(exc).__name__, exc))

print("")
print("结果：全绿 ✓" if ok else "结果：有红 ✗")
sys.exit(0 if ok else 1)
