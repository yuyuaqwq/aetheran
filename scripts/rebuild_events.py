# -*- coding: utf-8 -*-
"""events 域落域脚本（B3-5）：把《29_世界事件_设计_v1.md §五》的四条事件从**文档解析**进域。

源（唯一真源）：`06_第一阶段垂直切片/29_世界事件_设计_v1.md`
落点：`content/data/events.json`（世界事件表 · 三尺度：世界 / 限时 / 每日）

规矩（与 `rebuild_syscopy.py` / `rebuild_scenes.py` 同款）：
  · **数值一律从文档解析**（`每 7 游戏日 · 持续 1 日` 这类触发串直接解析成 period），不手打
  · 中文名 / 节点 / 天气 / 委托 一律**按名字回查别的域**拿 id（中文名 → id 不靠人记）
  · 连跑两次数据不变（幂等；第二次报「无变化」）
  · 保持插入序（K27：别 sort_keys）
  · 末尾补一个换行 · LF 落盘
  · 缺件（槽位 / 节点 / npc / 天气 / 委托 / 触发串认不出）**当场抛** —— 不许静默少一条

用法：python scripts/rebuild_events.py [--dry]
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.environ.get("AST_PLAN", "C:/Users/yuyu/aetheran-plan")
DOC = os.path.join(PLAN, "06_第一阶段垂直切片", "29_世界事件_设计_v1.md")
OUT = os.path.join(REPO, "content", "data", "events.json")

#: §五 表里的那一行：`| \`ev_x\` | 名字 | 尺度 | 触发 | 表征 |`
ROW = re.compile(r"^\|\s*`(ev_[a-z0-9_]+)`\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|\s*$")

#: 触发串 → period（★ 四个数都在这一层解析出来；认不出的触发串当场抛）
TRIGGERS = (
    (re.compile(r"^主线\s*(\d+)\s*之前$"), "until_main"),
    (re.compile(r"^主线\s*(\d+)\s*之后$"), "from_main"),
    (re.compile(r"^每\s*(\d+)\s*游戏日\s*·\s*持续\s*(\d+)\s*日$"), "every_days"),
    (re.compile(r"^第\s*(\d+)\s*游戏日之后\s*·\s*持续\s*(\d+)\s*日$"), "from_day"),
)

#: 语境栏（§三 的形状 + §四 的消费端 + §五 的表征）—— 只有 id / 槽位名 / 中文名，没有数值
LAYOUT = {
    # §五 第 1–2 行：世界级开关，表徵是「谁在镇上」⇒ where = 风车镇（全图不给 = 到处都是）
    "ev_caravan": {"where_maps": ["windmill_town"], "effects": {}},
    "ev_caravan_arrived": {"where_maps": ["windmill_town"], "effects": {}},
    # §五 第 3 行 + §四 ③：集日 ⇒ 挂板墙那边人多（多两位「临时在场」）+ 板上多一张纸。
    # ★ 挂到「挂板墙」是 §八① 的口径（风车镇 11 个节点里没有广场）；那两位是谁文档没点名
    #   ⇒ 选 小满（小孩 · 31 §三 写他在北口「看人」）+ 老陶（商队老人 · 集日到板子那边讲路上的事），
    #   依据与待确认写进 _meta.notes（`_notes.md` 也记一条）。
    "ev_market_day": {"where_crowd": True,
                      "effects": {"crowd": {"node_name": "挂板墙",
                                            "npcs": ["npc_xiaoman", "npc_laotao"],
                                            "text": "SYS_EV_MARKET_CROWD"}}},
    # §五 第 4 行：初雪 ⇒ 天气表里「初雪」的窗口拉长 + 一句进林描述。
    # ★ 倍数文档没给（只写「窗口拉长」）⇒ 借同案 §四 那条「翻倍」的数（见 doc_multiple()），
    #   口径登记在 _meta.notes + _notes.md，等主线拍板。
    "ev_first_snow": {"where_wild": True,
                      "effects": {"weather_mul": {"初雪": None}}},
}

#: 尺度：文档里的中文尺度 → ASCII 机器键（★ P-20 家族：中文枚举不当筛选键；
#  照 quests.chain / gathering.verb 的作法给域补一个 ASCII 维度 —— 代码只比值，不写死中文）
SCALE_KEY = {"世界": "world", "限时": "timed", "每日": "daily"}

#: 表征文案槽位（真源在 texts 域；这里只传槽位名）
TEXT = {
    "ev_caravan": "SYS_EV_CARAVAN",
    "ev_caravan_arrived": "SYS_EV_CARAVAN_ARRIVED",
    "ev_market_day": "SYS_EV_MARKET",
    "ev_first_snow": "SYS_EV_FIRST_SNOW",
}


def _load(name):
    with io.open(os.path.join(REPO, "content", "data", name + ".json"), encoding="utf-8") as f:
        return json.load(f)


def _doc_lines():
    if not os.path.exists(DOC):
        raise SystemExit("设计案不在：%s" % DOC)
    return io.open(DOC, encoding="utf-8").read().split("\n")


def doc_multiple(doc):
    """文档里给出的**倍数词** → 数（本包只有这一处的倍数写法：「翻倍」/「×2」）。

    ★ 为什么这么做：29 §五 只说「窗口拉长」，没给倍数；同案 §四② 写「骸骨出现率翻倍」。
      取值从文档字符来（不是手打的数），找不到倍数词就抛 —— 宁可不落，也不许脑补。
    """
    for word, n in (("翻倍", 2), ("×2", 2)):
        if word in doc:
            return word, n
    raise SystemExit("29 文档里找不到倍数词（翻倍 / ×2）—— 不给初雪窗口的倍数，别脑补")


def main_quest_by_order(order):
    """主线第 N 条（chain=main 且 order=N）→ quest id（★ 中文「主线 3」落成 id 靠这一口）。"""
    qs = _load("quests")
    hit = [k for k, v in qs.items() if v.get("chain") == "main" and int(v.get("order") or 0) == int(order)]
    if len(hit) != 1:
        raise SystemExit("主线第 %s 条不唯一（%s）—— 表错了" % (order, hit))
    return hit[0]


def node_by_name(name):
    """节点**中文名** → (map_id, node_id)（集日挂哪儿从文档里那个名字回查，不记 id）。"""
    maps = _load("maps")
    hit = [(mk, n["id"]) for mk, mv in maps.items() for n in (mv.get("nodes") or [])
           if n.get("name") == name]
    if len(hit) != 1:
        raise SystemExit("节点名 %r 不唯一 / 不存在（%s）—— 表错了" % (name, hit))
    return hit[0]


def weather_by_name(name):
    """天气**中文名** → weather id（初雪那条从 texts 里的名字回查）。"""
    wx, tx = _load("weather"), _load("texts")
    hit = [k for k, v in wx.items()
           if (tx.get(v.get("slot")) or {}).get("value") == name]
    if len(hit) != 1:
        raise SystemExit("天气名 %r 不唯一 / 不存在（%s）—— 表错了" % (name, hit))
    return hit[0]


def wild_maps():
    """野外三带（`belt_*`，topology=chain）—— 「一句进林描述」落在这儿。"""
    maps = _load("maps")
    hit = sorted(k for k, v in maps.items()
                 if str(k).startswith("belt_") and (v.get("topology") or "chain") == "chain")
    if not hit:
        raise SystemExit("maps 域里找不到野外三带（belt_*）—— 表错了")
    return hit


def parse_period(trigger):
    """触发串 → period（★ 文档给的四个数在这里解析；认不出当场抛）。"""
    for rx, kind in TRIGGERS:
        m = rx.match(trigger)
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        if kind in ("until_main", "from_main"):
            return {kind: main_quest_by_order(g[0])}
        if kind == "every_days":
            return {"every_days": g[0], "last_days": g[1]}
        if kind == "from_day":
            return {"from_day": g[0], "last_days": g[1]}
    raise SystemExit("触发串认不出（别改口径，改脚本）：%r" % trigger)


def build():
    doc = "\n".join(_doc_lines())
    word, mul = doc_multiple(doc)
    tx, npcs = _load("texts"), _load("npcs")
    out, seen = {}, []

    for ln in _doc_lines():
        m = ROW.match(ln)
        if not m:
            continue
        eid, name, scale, trigger, look = [c.strip() for c in m.groups()]
        name = name.replace("**", "").strip()
        if eid in seen:
            raise SystemExit("事件 id 重复：%s" % eid)
        seen.append(eid)
        lay = LAYOUT.get(eid)
        if lay is None:
            raise SystemExit("设计案里多了一条事件 %r，脚本的 LAYOUT 没它的效果栏 —— 先裁决" % eid)
        if scale not in ("世界", "限时", "每日"):
            raise SystemExit("尺度认不出：%s → %r" % (eid, scale))
        slot = TEXT[eid]
        if slot not in tx:
            raise SystemExit("%s 的文案槽位 %r 不在 texts 域里（先补槽位再落域）" % (eid, slot))

        effects = dict(lay["effects"])
        where = list(lay.get("where_maps") or [])
        if lay.get("where_crowd"):
            mk, nk = node_by_name(effects["crowd"]["node_name"])
            where = [mk]
            effects["crowd"] = dict(effects["crowd"], node=nk)
            effects["crowd"].pop("node_name", None)
            bad = [n for n in effects["crowd"]["npcs"] if n not in npcs]
            if bad:
                raise SystemExit("集日临时在场名单里有不存在的 NPC：%s" % bad)
        if lay.get("where_wild"):
            where = wild_maps()
        if effects.get("weather_mul"):
            # 天气**按名字**回查 id（域里写的是 初雪 这个中文名，不是 id）+ 倍数从文档来
            effects["weather_mul"] = {weather_by_name(k): mul
                                      for k in effects["weather_mul"]}

        out[eid] = {
            "no": len(seen),
            "name": name,
            "scale": scale,
            "scale_key": SCALE_KEY[scale],
            "period": parse_period(trigger),
            "text": slot,
            "where": where,
            "effects": effects,
            "look": look.replace("**", "").strip(),
            "source": "06_第一阶段垂直切片/29_世界事件_设计_v1.md §五 第 %d 行（触发：%s）"
                      % (len(seen), trigger),
        }

    out["_meta"] = {
        "title": "世界事件（三尺度：世界 / 限时 / 每日）",
        "source": "06_第一阶段垂直切片/29_世界事件_设计_v1.md",
        "generator": "scripts/rebuild_events.py（数值与触发全部从 §五 表解析；"
                     "中文名 / 节点 / 天气 / 委托 按名字回查别的域拿 id）",
        "scale_note": "世界=跟着主线进度走的开关（一次翻转）· 限时=到点自己开合的周期 · "
                      "每日=每天重来（29 §二）。三者都只是「当前是否成立」的一个布尔，"
                      "谁都不存历史 —— 历史那一格由 flags 记（content/timed_events.py）。",
        "period_keys": {
            "every_days+last_days": "窗 = 游戏日 % every_days < last_days（锚点 = 第 0 个游戏日）",
            "from_day+last_days": "窗 = from_day <= 游戏日 < from_day + last_days",
            "from_main": "主线过了就成立（读 flags.quests_done / flags.quests.<id>.done）",
            "until_main": "★ 镜像键：主线**没过**才成立（29 §三 只列了 from_main；"
                          "§五 的两条「商队在路上 / 到了」是一对互补开关，本批按它补出这一面）",
            "daily": "每天都成立（键按天重置）—— 第一阶段数据里没有每日条目（29 §二 说那层归时辰 / 对话）",
        },
        "effect_keys": {
            "crowd": "哪一站聚人（node）+ 临时在场的 npc 名单 + 那一下的文案槽位 "
                     "⇒ 消费端 content/cmds_ast.py::_npcs_here（移出基位 / 在那儿算在场）+ event_lines",
            "weather_mul": "天气加权（按游戏日）⇒ 消费端 content/calendar.py::weather_weights",
            "encounter_mul": "遇敌候选加权 ⇒ 消费端 content/combat.py::pick_encounter（没给 = 零变化）",
            "price_mul": "★ 未接（没有铺子 / 价目表 —— 21 §二「杜林给一张价目单」未落）："
                         "本域今天不用这个键；谁写进来，probe_events 会点名「这份数据今天没人读」",
        },
        "notes": [
            "① 集日那两位（临时在场）设计案没点名 ⇒ 选 小满 + 老陶（小孩往人堆里去 / "
            "商队老人集日到板子那边讲路上的事）；与 31_NPC作息 的时段表按「事件优先」合成，"
            "31 落地时照这条（_notes.md 记了）。",
            "② 初雪的天气倍数文档没给 ⇒ 借同案 §四 的倍数词「%s」= ×%d（从文档字符取值，不是手打）" % (word, mul),
            "③ 首版数据里没有一条用 encounter_mul（§五 的四条不含遇敌类；21 §三 那几条属 B3-6d 铺量）"
            "—— 那一层已经建好并真加权，探针直调证明。",
            "④ 每日尺度第一阶段没有条目：29 §二 说它（传闻换一批 / 稀有鱼只在夜里）已由时辰层与"
            "对话 need 层承担；形状仍在域与判定口里（探针注入一条假每日事件证明那条路可算）。",
        ],
    }
    return out


def dump(data):
    with io.open(OUT, "w", newline=chr(10), encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main(argv):
    dry = "--dry" in argv
    data = build()
    old = None
    if os.path.exists(OUT):
        with io.open(OUT, encoding="utf-8") as f:
            old = json.load(f)
    n = len([k for k in data if not str(k).startswith("_")])
    if old == data:
        print("解析：%d 条事件 —— 与域里逐字节相同（幂等 · 没写任何东西）" % n)
        return 0
    for k, v in data.items():
        if str(k).startswith("_"):
            continue
        print("  %-20s %s · %s · %s · 效果 %s"
              % (k, v["name"], v["scale"], json.dumps(v["period"], ensure_ascii=False),
                 json.dumps(v["effects"], ensure_ascii=False)))
    if dry:
        print("（--dry：没落盘）")
        return 0
    dump(data)
    print("落地：events %s（%d 条）" % (OUT, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
