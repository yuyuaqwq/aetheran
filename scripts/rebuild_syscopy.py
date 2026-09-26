# -*- coding: utf-8 -*-
"""syscopy 落域脚本（B3-6b）：把「系统与移动」那批文案从口径文档解析进 texts 域。

源（唯一真源）：`00_总纲/17_文案收口口径_v1.md` 的槽位表（后续批继续往那份表加）
落点：`content/data/texts.json`（文案真源表）

规矩：
  · 只**新增**缺失的槽位；已存在的槽位必须**逐字相同**（不同就抛 —— 防两处口径打架）
  · 保持原表插入序（K27：别 sort_keys，一排序就是近千行假 diff）
  · 末尾补一个换行 · LF 落盘
  · 连跑两次数据不变（幂等自检；第二次应报「无新增」）
  · 占位与 params **双向对账**（声明的要有占位 · 占位要声明过）

用法：python scripts/rebuild_syscopy.py [--dry]
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.environ.get("AST_PLAN", "C:/Users/yuyu/aetheran-plan")
DOC = os.path.join(PLAN, "00_总纲", "17_文案收口口径_v1.md")
TEXTS = os.path.join(REPO, "content", "data", "texts.json")

#: ★ B4-16 起 `RANK_*` 也在这一族里（公会评级那几张档名 —— 键 = `RANK_<ASCII ID>`，
#:   拼法唯一在 `content/ranks.py::label_key`；档名本体是文案，所以它归 texts 域）。
KEY_RE = re.compile(r"^(SCENE|READ|NPC|COMBAT|QUEST|ITEM|SYS|TITLE|WORLD|HOUR|WEATHER|UNID|TALK|RANK)_[A-Z0-9_]+$")
PH = re.compile(r"\{(\w+)\}")
ROW_RE = re.compile(r"^\|\s*([A-Z][A-Z0-9_]*)\s*\|")

#: ★ g4-leftovers：**口径表待跟账**（真源那一行的值待主线改 · 两态互锁）。
#:
#:   为什么要有这一格：本脚本对已存在的槽位要求**逐字相同**（防两处口径打架），
#:   可这一轮要改的几条（建号那一步的玩家词 · `SYS_PAGE_NONE` 的列表候选）改的是**值**，
#:   而真源仓对本分支只读 ⇒ 不给这一格，就只有「换新槽位 + 退役登记」一条路
#:   （fix3 那次的走法），而那会给 texts 留一条永远没人读的旧句子。
#:
#:   口径（第三态当场抛 —— 「门禁只加强不削弱」）：
#:     · 表里那一格**要么**是旧值（主线还没跟账）· **要么**是新值（跟账后）；别的值 ⇒ 抛；
#:     · 落下时必须已经在域里（`add` 那一支不许借这一格混进来 —— 那会变成「表里没有、域里先有」）；
#:     · 域里那一条必须**逐字等于** `new`（旧值留在域里 ⇒ 抛）。
DOC_PENDING = {
    "SYS_CLS_NAME": {
        "old": "名字还没定 —— 打『改名 <名字>』，只改这一回。",
        "new": "名字还没定 —— 打『名字 <名字>』，只改这一回。",
        "why": "g4-③（P1 体验-1）：建号那一步的玩家词是『名字』（`04_指令总表` 的别名那一个，"
               "玩家照着敲得通），引导却把他指去『改名』—— 三处对齐（见分支 `_notes.md`）",
    },
    "SYS_REG_ASKNAME": {
        "old": "「叫什么名字？」—— 先打『改名 <名字>』，回头再来办证。",
        "new": "「叫什么名字？」—— 先打『名字 <名字>』，回头再来办证。",
        "why": "g4-③：同上（登记那一支也把『名字』递过去）",
    },
    "SYS_RENAME_ASK": {
        "old": "想叫什么？打『改名 <名字>』—— 一到八个字，只改这一回。",
        "new": "想叫什么？打『名字 <名字>』—— 一到八个字，只改这一回。",
        "why": "g4-③：同上（这条指令的 `usage` 也改成『名字』，『改名』留作别名）",
    },
    "SYS_PAGE_NONE": {
        "old": "先打开一个列表（『背包』看东西 ·『排行』看本群榜）—— 再敲『下一页』或『回 <页码>』。",
        "new": "先打开一个列表（{lists}）—— 再敲『下一页』或『回 <页码>』。",
        "why": "g4-④（P4 E-4 的另一半）：那句只点了『背包』『排行』两个列表，"
               "而分页今天有七列（`content/pager.py::LIST_KEYS`）—— 列表名从登记处现算，"
               "不再手打（见分支 `_notes.md`）",
    },
    "READ_TOWER_STELE_NAMES": {
        "old": "名字一排排往下刻。有三个，你在白桦林那棵树皮上见过 —— 重了。",
        "new": "名字一排排往下刻。刻痕很深，边角还利 —— 有几个名字眼熟，你想不起在哪儿见过。",
        "why": "g4-⑩（P2 BUG⑦ 时序）：旧那句对**没去过白桦林**的玩家也断言「你见过」——"
               "改成按真实经历分支：这一格是**没读过**白桦上那棵树名时的那一版，"
               "读过之后走变体槽位 `READ_TOWER_STELE_NAMES__POI_NAMED_BIRCH`（见分支 `_notes.md`）",
    },
    "SYS_INN_SLEEP": {
        "old": "你在角落那张床睡下 —— 再睁眼，日头已经换了地方。",
        "new": "你在角落那张床睡下 —— 睡得不沉，醒来外头还是那个时辰。",
        "why": "试玩问题 #15（P1 BUG-6）：时辰/天气是**现算**的（钟由宿主注入、整个进程一根钟）——"
               "住店推不动它，可旧那句断言「日头已经换了地方」⇒ 睡完 `时间` 还是同一个时辰，"
               "回话自己打脸（夜里住店的人以为能等到天亮，实际一步没挪）。"
               "改法 = 照实说（真推时间要先有**按人存的钟偏移**那一层，不是这一簇的事）——"
               "本分支只改这一句的值，见 `_notes.md` §真源行",
    },
    # ★ fix-c-newbie ①（新手进入面）：建号第一步那两行念的是「天赋 · …」「代价 · …」，
    #   而这两个词**都不是指令**（`04_指令总表 §三` 的角色栏里没有它们、`帮助` 里也没有）
    #   ⇒ 玩家照着屏上的词敲「天赋」只回「这句我没接住」（P-54 那句兜底）。
    #   最小改法 = 句尾加一句括注说清「已经在身上了、不用敲」（不是新增指令 —— 指令名属口径）。
    #   真源那一行（`17_文案收口口径_v1.md` 的这两格）**待主线跟账**成新值；真源仓对本分支只读。
    "SYS_RACE_TALENT": {
        "old": "天赋 · {name}：{effect}",
        "new": "天赋 · {name}：{effect}（已生效）",
        "why": "fix-c-newbie ①（新手进入面 · 狂战士试玩 b01）：建号第一屏把「天赋」当名词念，"
               "玩家会把它当**指令**敲（实跑：`我是 人类` 回话印「天赋 · 人脉 / 天赋 · 适应」，"
               "紧接 `天赋` ⇒ 「「天赋」这句我没接住。」）——`04 §三` 的角色栏与 `帮助` 里都没有这条词。"
               "改法 = 那两行句尾加「（已生效）」：不新增指令名、不动 `出身`（`04 §三` 那一行列的字段没它），"
               "只把那两行从「像是要敲的东西」改成「已经在身上」。见分支 `_notes.md §真源行`",
    },
    "SYS_RACE_COST": {
        "old": "代价 · {name}：{effect}",
        "new": "代价 · {name}：{effect}（已生效）",
        "why": "fix-c-newbie ① 同屏同族：`代价` 与 `天赋` 是同一形状（都不是指令、都印在同一屏），"
               "只标一半 ⇒ 玩家照着剩下的那个词照样敲得空。两条一起标，理由与上一格同",
    },
}


def pending_ok(key: str, doc_val: str) -> bool:
    """这一条待跟账、且**表里那一格处于允许的两态之一** → True（第三态 ⇒ False ⇒ 当场抛）。"""
    fx = DOC_PENDING.get(str(key))
    return bool(fx) and doc_val in (fx["old"], fx["new"])



def parse_doc(path=DOC):
    """读口径文档里**所有**槽位表 -> 每行一条（顺序 = 文档里的顺序）。

    ★ 后续批次继续往那份文档下面加表就行（脚本按行全扫）—— 别另开一份，免得两处口径。
    """
    if not os.path.exists(path):
        raise SystemExit("口径文档不在：%s" % path)
    lines = io.open(path, encoding="utf-8").read().split(chr(10))
    out = []
    for ln in lines:
        if not ROW_RE.match(ln):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) != 5:
            raise SystemExit("列数不是 5（别改列数）：%s" % ln)
        key, value, params, cat, srcname = cells
        # ★ 多行文案：表里写 `\n`（反斜杠 n）＝真换行（行内不许出现真换行 —— 真换行会把一行切成两行，
        #   第二行不是槽位行、**静默漏掉**）。JSON 落盘时它就是一个真换行（与 SCENE_* 那些多段正文同形）。
        value = value.replace("\\n", "\n")
        prm = [] if params in ("-", "") else [x.strip() for x in params.split(",") if x.strip()]
        out.append({"key": key, "value": value, "params": prm,
                    "category": cat, "src": srcname})
    if not out:
        raise SystemExit("槽位表是空的")
    return out


def check(rows):
    """键名 · 重复 · 占位与 params 双向对账 —— 错一条都不许落。"""
    bad = []
    seen = set()
    for r in rows:
        k, v = r["key"], r["value"]
        if not KEY_RE.match(k):
            bad.append("键名不合规则：%s" % k)
        if k in seen:
            bad.append("重复：%s" % k)
        seen.add(k)
        used = set(PH.findall(v))
        decl = set(r["params"])
        if used - decl:
            bad.append("%s：value 里的占位没声明 -> %s" % (k, sorted(used - decl)))
        if decl - used:
            bad.append("%s：声明了却没占位 -> %s" % (k, sorted(decl - used)))
        if not v.strip():
            bad.append("%s：文案是空的" % k)
        if "〔待填" in v:
            bad.append("%s：还是待填占位" % k)
    if bad:
        for b in bad:
            print("  x %s" % b)
        raise SystemExit("槽位表没过对账，没写任何东西")
    return True


def load_texts():
    return json.load(io.open(TEXTS, encoding="utf-8"))


def dump_texts(tx):
    with io.open(TEXTS, "w", newline=chr(10), encoding="utf-8") as f:
        json.dump(tx, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main(argv):
    dry = "--dry" in argv
    rows = parse_doc()
    check(rows)
    tx = load_texts()
    before = len(tx)
    add, same, clash = [], 0, []
    for r in rows:
        old = tx.get(r["key"])
        if old is None:
            if r["key"] in DOC_PENDING:
                raise SystemExit("%s：登记了待跟账却**域里没有**（域里先有才谈得上跟账）" % r["key"])
            add.append(r)
        elif old.get("value") == r["value"]:
            same += 1
        elif pending_ok(r["key"], r["value"]) and old.get("value") == DOC_PENDING[r["key"]]["new"]:
            same += 1                     # ★ g4：待跟账的两态之一（表里旧值 / 跟账后新值；域里是新值）
        else:
            fx = DOC_PENDING.get(r["key"])
            if fx and r["value"] not in (fx["old"], fx["new"]):
                clash.append((r["key"] + "（跟账第三态：表里既不是旧值也不是新值）",
                              old.get("value"), r["value"]))
            else:
                clash.append((r["key"], old.get("value"), r["value"]))
    if clash:
        for k, a, b in clash:
            print("  x %s 两处不一样：" % k)
            print("      表里：%s" % b)
            print("      域里：%s" % a)
        raise SystemExit("槽位与域里的字不一样 —— 先裁决再落（没写任何东西）")
    print("解析：%d 条（已存在且一致 %d · 要新增 %d · 待跟账 %d）"
          % (len(rows), same, len(add), len(DOC_PENDING)))
    if not add:
        print("  · 无新增 —— 数据不变（幂等）")
        return 0
    for r in add:
        tx[r["key"]] = {"value": r["value"], "params": r["params"],
                        "category": r["category"], "desc": r["src"]}
        print("  + %-22s %s" % (r["key"], r["value"][:34]))
    if dry:
        print("（--dry：没落盘；texts %d -> %d）" % (before, len(tx)))
        return 0
    dump_texts(tx)
    print("落地：texts %d -> %d 条  %s" % (before, len(tx), TEXTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
