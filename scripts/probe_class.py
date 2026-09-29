# -*- coding: utf-8 -*-
"""探针：建号第二步（选职业）—— B4-7。

为什么有这条线（端到端玩出来的真缺口）
------------------------------------
档上 `cls` 原先**没有任何写端**：建号只走完了第一步（选族）⇒ 新号没有面板 ——
`状态` 的生命是「未定」，「攻击」「歇脚」这类要数字的地方全被 fail-closed 挡掉
（回「职业基础 还没接上」）。玩家照样能走能看能搭话，但**打不了**。

判据（一条都不许松）
  ① classes 域 6 条 · 每条 name/role/desc/mech/icon/order 都齐（菜单那几栏的字都在域里）
  ② order = 1..6 互不相同 · 菜单第一行是「骑士」（照 03_职业与技能/08_六职业对照_v2 §一 表序）
  ③ 中文名 / 短名（knight）/ 全 id（cls_knight）三种写法都认（`_cls_match` 一口）
  ④ 第一步没走完（没族）就选职业 ⇒ 拦一句 + **不动档**
  ⑤ 选完族那一下回话里递出「还差一步」；裸 `选职业` 递菜单：六种各两行（名/定位/自述 + 节奏）
  ⑥ 菜单里的每个名字 / 定位 / 自述 / 节奏**逐字来自域**（本探针自己从 classes.json 取，不写死）
  ⑦ `选职业 骑士` 落档 `cls = cls_knight` · 回话含 名 / 节奏 / 生命上限
  ⑧ 落档之后三处一致：面板上限 == 档上 `hp_max` == 现血起手满（P-27 唯一来源）
  ⑨ 已经定过的不许改：再敲别的职业 ⇒ 回「已经定了」+ cls 一个字不动
  ⑩ 认不出的职业 ⇒ 报错 + 不动档（fail-closed）
  ⑪ 裸 `职业`：定过 = 看你这一门（带域里的自述与节奏）；没定过 = 菜单
  ⑫ 推荐星跟着**族**走（精灵 ⇒ 法师 / 游侠两行带星 · 人类那条写「任意」⇒ 一行都不带）
  ⑬ ★ 真打一场：建号两步走完 ⇒ `攻击` 不再回「职业基础 还没接上」，整场真打完并落账
  ⑭ ★ P-50（2026-09-26 · 本波 w-h-ux）：建号第二步那一栏「优势 / 弱点」—— **裁决：补真源行，
     代码先接线**。键名钉住 `SYS_CLS_EDGE` · **两态一致（半截 = 红）** · 拿造出来的记录 +
     临时注入的槽位直调接线（用完即撤）· 域里不许有自己编的那两格。逐字句子见
     `_notes.md §真源行`（本路不碰共享面 `texts.json`）。

用法：GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_class.py
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import time

ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ENGINE)

_PH = re.compile(r"\{[^{}]*\}")   # 判据锚点切分用（`_anchor` 用它剔掉 `{…}`）

from saintess_engine.package import load_stack            # noqa: E402
from saintess_engine.host.runtime import Host             # noqa: E402

NL = chr(10)
OK, BAD = [], []


def ok(msg):
    OK.append(msg)
    print("  OK  %s" % msg)


def bad(msg):
    BAD.append(msg)
    print("  X   %s" % msg)


class Ad(object):
    """最小适配器（照 scripts/e2e_drive.py 的真宿主契约）。"""

    def __init__(self):
        self.out = []
        self.saved = {}

    def recv(self):
        return None

    def load_player(self, uid):
        return self.saved.get(uid)

    def save_player(self, uid, data):
        self.saved[uid] = dict(data) if isinstance(data, dict) else data

    def say(self, to, text):
        self.out.append(str(text))


def drive(ad, host, text, uid):
    ad.out = []
    host.handle({"uid": uid, "group_id": "g_class_probe", "text": text})
    return list(ad.out)


def main():
    with io.open(os.path.join(REPO, "content", "data", "classes.json"), encoding="utf-8") as f:
        C = json.load(f)
    with io.open(os.path.join(REPO, "content", "data", "texts.json"), encoding="utf-8") as f:
        TX = json.load(f)

    def _anchor(value, minlen=6):
        """判据锚点 = 模板里**最长的字面片段**（把 `{…}` 占位符整段剔掉）。
        ★ 为什么不是 `split("{")[0]`：`SYS_HP_UNSET` 的值是「（{name}：……」——
          占位符在**最前**，切出来只剩一个全角括号 = **退化锚点**（判据等于没有）。
        ★ 与 `scripts/probe_copy.py::_anchor` 同一口径（两处各抄一份，判据与被测物独立）。
        """
        best = max((s for s in _PH.split(str(value or "")) if s.strip()), key=len, default="")
        if len(best.strip()) < minlen:
            raise AssertionError("判据锚点退化（%r → %r）" % (value, best))
        return best.strip()

    def T(key, **slots):
        s = TX[key]["value"]
        for k, v in slots.items():
            s = s.replace("{%s}" % k, str(v))
        return s

    # (1) 六条齐 · 菜单那几栏的字都在域里
    if len(C) == 6:
        ok("classes 域 6 条")
    else:
        bad("classes 域不是 6 条：%d" % len(C))
    miss = [k for k, v in C.items()
            if not all(v.get(f) for f in ("name", "role", "desc", "mech", "icon", "order"))]
    if not miss:
        ok("每一条 name / role / desc / mech / icon / order 都齐（菜单的字都有真源）")
    else:
        bad("这几条缺项：%s" % miss)

    # (2) order · 第一行
    orders = sorted(v.get("order") for v in C.values())
    if orders == [1, 2, 3, 4, 5, 6]:
        ok("order = 1..6 互不相同")
    else:
        bad("order 不对：%s" % orders)
    ordered = sorted(C.items(), key=lambda kv: (kv[1].get("order") or 99, kv[0]))
    if ordered[0][0] == "cls_knight":
        ok("菜单第一行是骑士（照 08_六职业对照_v2 §一 表序，不是 id 字母序）")
    else:
        bad("菜单第一行是 %s，应为 cls_knight" % ordered[0][0])

    st = load_stack(str(REPO), inject={"db_path": ":memory:", "clock": time.time})
    del st

    # (3) 三种写法都认
    from content import cmds_ast as A_                                 # noqa: E402

    got = [A_._cls_match("骑士"), A_._cls_match("knight"), A_._cls_match("cls_knight")]
    if all(g and g[0] == "cls_knight" for g in got):
        ok("中文名 / 短名 / 全 id 三种写法都认（_cls_match 一口）")
    else:
        bad("_cls_match 认不全：%r" % got)
    if A_._cls_match("不存在这门") is None:
        ok("认不出的词 ⇒ None（不瞎猜）")
    else:
        bad("认不出的词也有命中")

    ad = Ad()
    host = Host(ad, REPO, inject={"db_path": ":memory:", "clock": time.time})
    host.boot()
    uid = "u_class_probe"

    # (4) 第一步没走完就选职业
    j = NL.join(drive(ad, host, "选职业 骑士", uid))
    if T("SYS_CLS_NORACE") in j:
        ok("没定族就选职业 ⇒ 拦一句（先定族）")
    else:
        bad("没族也能选职业：%s" % j[:160])
    if not (ad.saved.get(uid) or {}).get("cls"):
        ok("那一下**不动档**（cls 仍空）")
    else:
        bad("档被写了：%r" % (ad.saved.get(uid) or {}).get("cls"))

    # (5) 选族那一下递出下一步 + 裸选职业递菜单
    j = NL.join(drive(ad, host, "我是 精灵", uid))
    if T("SYS_CLS_ASK") in j:
        ok("选完族那一下递出「还差一步」（建号第二步在等着）")
    else:
        bad("选族回话里没有第二步那一行：%s" % j[:160])
    lines = drive(ad, host, "选职业", uid)
    j = NL.join(lines)
    hit6 = sum(1 for _k, v in ordered if v["name"] in j)
    if hit6 == 6:
        ok("裸『选职业』递六种菜单（命中 6/6）")
    else:
        bad("菜单不齐（命中 %d/6）：%s" % (hit6, j[:160]))
    if "往哪走" not in j:
        ok("菜单那一下**不是风景**（没给「往哪走」）")
    else:
        bad("递菜单时还给了风景")

    # (6) 菜单逐字来自域（★ 星也跟着族走 —— 期望值现算，不写死）
    with io.open(os.path.join(REPO, "content", "data", "races.json"), encoding="utf-8") as f:
        R = json.load(f)
    star_elf = sorted(v["name"] for v in C.values()
                      if v["name"] in (R["race_elf"].get("recommend") or []))
    wrong = []
    for i, (k, v) in enumerate(ordered, 1):
        star = T("SYS_CLS_STAR") if v["name"] in star_elf else ""
        row = T("SYS_CLS_ROW", i="①②③④⑤⑥"[i - 1], star=star, icon=v["icon"], name=v["name"],
                role=v["role"], desc=v["desc"])
        mech = T("SYS_CLS_MECH", mech=v["mech"])
        if row.replace("  ", " ") not in j.replace("  ", " "):
            wrong.append(("行", k, row[:40]))
        if mech not in j:
            wrong.append(("节奏", k, mech[:40]))
    if not wrong:
        ok("六行名字 · 定位 · 自述 · 节奏逐字来自 classes 域（%d 行现取）" % len(ordered))
    else:
        bad("与域对不上：%s" % wrong[:4])

    # (12) 推荐星跟着族走（这一档是精灵 ⇒ 法师 / 游侠；人类的「任意」不算推荐）
    got_star = sorted(v["name"] for _k, v in ordered
                      if any((v["name"] in l and T("SYS_CLS_STAR") in l) for l in lines))
    if got_star == star_elf and star_elf:
        ok("推荐星 = 族推荐那份名单（精灵 ⇒ %s）" % " / ".join(star_elf))
    else:
        bad("星不一致：菜单挂星 %s · races.recommend 给的是 %s" % (got_star, star_elf))

    # (7) 落档
    j = NL.join(drive(ad, host, "选职业 法师", uid))
    if (ad.saved.get(uid) or {}).get("cls") == "cls_mage":
        ok("『选职业 法师』落档 cls = cls_mage")
    else:
        bad("档上 cls 不对：%r" % (ad.saved.get(uid) or {}).get("cls"))
    if T("SYS_CLS_DONE", name=C["cls_mage"]["name"]) in j and C["cls_mage"]["mech"] in j:
        ok("回话含 名 + 节奏（同一句来自域）")
    else:
        bad("定职回话缺名/节奏：%s" % j[:200])

    # (8) 三处一致（面板 == 档 == 现血起手满）
    from content import panel_build as PB                              # noqa: E402

    cap = PB.hp_cap(ad.saved[uid])
    cur = ad.saved[uid]
    if cur.get("hp_max") == cap and cur.get("hp") == cap:
        ok("三处一致：面板上限 %d == 档上 hp_max == 现血（起手满）" % cap)
    else:
        bad("三处不一致：面板 %r · 档上 hp_max %r · hp %r" % (cap, cur.get("hp_max"), cur.get("hp")))
    if T("SYS_CLS_HP", hp=cap, max=cap) in j:
        ok("定职那一下把生命那条报出来了（逐字槽位）")
    else:
        bad("没报生命那条：%s" % j[:200])

    # (11) 裸『职业』= 看你这一门
    j = NL.join(drive(ad, host, "职业", uid))
    if C["cls_mage"]["desc"] in j and C["cls_mage"]["mech"] in j:
        ok("定过之后裸『职业』= 看你这一门（自述 + 节奏）")
    else:
        bad("『职业』没给出这一门：%s" % j[:160])

    # (9) 定过不许改
    before = ad.saved[uid].get("cls")
    j = NL.join(drive(ad, host, "选职业 骑士", uid))
    if T("SYS_CLS_HAS", name=C["cls_mage"]["name"]) in j:
        ok("已经定过的：再选别的 ⇒ 回「已经定了」（手滑换门会毁档）")
    else:
        bad("能换门：%s" % j[:160])
    if ad.saved[uid].get("cls") == before:
        ok("那一下 cls 一个字不动（%s）" % before)
    else:
        bad("档被换了：%r" % ad.saved[uid].get("cls"))

    # (10) 认不出的职业
    ad2 = Ad()
    host2 = Host(ad2, REPO, inject={"db_path": ":memory:", "clock": time.time})
    host2.boot()
    u2 = "u_class_probe2"
    drive(ad2, host2, "我是 人类", u2)
    j = NL.join(drive(ad2, host2, "选职业 大魔王", u2))
    if "大魔王" in j and "大魔王" not in [v["name"] for v in C.values()]:
        ok("认不出的职业 ⇒ 那句里点了玩家写的词（%s）" % j[:60])
    else:
        bad("认不出的职业没报错：%s" % j[:160])
    if not (ad2.saved.get(u2) or {}).get("cls"):
        ok("认不出的职业**不动档**（fail-closed）")
    else:
        bad("档被写了：%r" % (ad2.saved.get(u2) or {}).get("cls"))

    # (13) 真打一场：建号两步走完 ⇒ 打得动（原先卡在「职业基础 还没接上」）
    ad3 = Ad()
    # ★ G2：战斗改成**一手一推进**之后，「这一场」要在两条指令之间**真存住**
    #   （`persistence.group_*` 每条指令各开一次连接 ⇒ `:memory:` 那种库下一次读不回来，
    #   开场那一敲会看起来「只回了一行」）⇒ 这一节用真文件库（其余几节不碰战斗，照旧 `:memory:`）。
    _db3 = os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe_class_battle.db")
    try:
        os.remove(_db3)
    except OSError:
        pass
    host3 = Host(ad3, REPO, inject={"db_path": _db3, "clock": time.time})
    host3.boot()
    u3 = "u_class_probe3"
    drive(ad3, host3, "我是 人类", u3)
    drive(ad3, host3, "选职业 骑士", u3)
    # ★ 2026-09-30（注册面改造）：守卫口径 —— 建号三步走完才有「手」（半档敲攻击会被
    #   引去起名）。攻击类用例先把第三步（起名）走完，测的仍是「两步之后的真能打」。
    drive(ad3, host3, "名字 试刀", u3)
    drive(ad3, host3, "往北", u3)
    # ★ G2：一条 `攻击` = 推一手 ⇒ 连敲两次，把「你这一手 + 对方那一手」都收进来再判
    j = NL.join(drive(ad3, host3, "攻击", u3) + drive(ad3, host3, "攻击", u3))
    #  ★ P0-2：反证锚点改成**按槽位取前缀**（那句话的值改过一次，写死中文必红）。
    #    判据方向一个字没变：两步走完 ⇒ 那一行**不许再出**（出 = 职业没真定上）。
    _hp_prefix = _anchor(T("SYS_HP_UNSET"))
    if _hp_prefix and _hp_prefix in j:
        bad("两步走完还是「没定职业」那一行：%s" % j[:160])
    elif ("伤害" in j and "受到" in j) or T("COMBAT_NONE") in j:
        ok("两步走完 ⇒ 『攻击』真能打（这一场：%s）" % ("有伤害" if "受到" in j else "这一带没东西"))
    else:
        bad("『攻击』没有结果：%s" % j[:200])

    # (14) ★ P-50（2026-09-26 · 本波 w-h-ux · **本波裁决：补真源行，代码先接线**）
    #   真源 `18_建号与新手引导_v1.md §一 第 2 步` 要那一栏「优势 / 弱点」，可六份职业详案与
    #   `08_六职业对照_v2` 到今天也没有逐条的句 —— 而本路**不碰共享面**（`content/data/texts.json`）
    #   ⇒ 本轮把**接线**做好、把**缺的那一头**印出来、把**两态**钉死：
    #     ① 键名钉住（`SYS_CLS_EDGE` —— 真源行落进 17 号口径表时要用这一个键）；
    #     ② **两态一致（半截 = 红）**：域里两句 + texts 里槽位「都在 ⇒ 菜单里有那一行、
    #        逐字对得上」·「都缺 ⇒ 菜单里一行都没有、一个字都不出现」·
    #        「只有一头 ⇒ 红」（加了域没加槽位 / 加了槽位没加域，都不许存在）；
    #     ③ 拿**探针自己造的记录 + 临时注入的槽位**直调接线（用完即撤）—— 证明那不是死代码，
    #        也不写死一张镜像模板（临时那条模板是本探针自己给的）；
    #     ④ 逐字句子（真源行的交付物）印在下面那张待补清单里（见本分支 `_notes.md §真源行`）。
    from content import cmds_ast as _CA14                                  # noqa: E402
    PENDING = {"优势 / 弱点": "真源 06_第一阶段垂直切片/18_建号与新手引导_v1.md §一 第 2 步写着"
                              "「显示 职业名 · 节奏来源一句话 · 优势 / 弱点 · 一句自述」，"
                              "而 03_职业与技能/0X_*_v2.md 与 08_六职业对照_v2 里没有逐条的句子"}
    print("  ★ 待补清单（真源没写的那一欄 —— 本批只登记，不自己编）：")
    for _k, _why in sorted(PENDING.items()):
        print("      · %s → %s" % (_k, _why))
    print("      真源行落进 `00_总纲/17_文案收口口径_v1.md` 的槽位表（新开一节）要用这一条：")
    print("      | SYS_CLS_EDGE | 优势 · {adv} ｜ 弱点 · {weak} | adv,weak | 系统 | P-50 建号第二步 · "
          "每门一句优势 + 一句弱点（句在 classes 域：adv / weak） |")
    _tmp14 = _CA14.PENDING_SLOTS.get("cls_edge")
    if _tmp14 == "SYS_CLS_EDGE":
        ok("★ P-50 待槽位的**键名** = SYS_CLS_EDGE（真源行落进 17 号口径表就用这一个键）")
    else:
        bad("★ P-50 待槽位键名不对：%r（应当是 SYS_CLS_EDGE）" % _tmp14)
    _dom14 = sorted(k for k, v in C.items() if v.get("adv") or v.get("weak"))
    _half14 = sorted(k for k, v in C.items() if bool(v.get("adv")) != bool(v.get("weak")))
    _slot14 = _tmp14 in TX                                   # texts 里有没有那条槽位
    _exp14 = {k: _CA14._cls_edge_line(v) for k, v in C.items()}
    _exp14 = {k: ln for k, ln in _exp14.items() if ln}
    if _half14:
        bad("★ P-50 半截：这几门只写了优势或只写了弱点（%s）—— 两句都在才出那一行，"
            "缺一句就是缺一行（不许只印半句）" % _half14)
    if bool(_dom14) != bool(_slot14):
        bad("★ P-50 **半截**：域里有 adv/weak 的 %d 门 · texts 里那条槽位 %s —— 两头必须一起在"
            "（先补真源行 → 跑 rebuild_syscopy → 再补域里那两句；反序也红）"
            % (len(_dom14), "在" if _slot14 else "不在"))
    else:
        ok("★ P-50 两头一致：域里 adv/weak %d 门 · texts 那条槽位%s"
           % (len(_dom14), "在" if _slot14 else "不在"))
    ad4 = Ad()
    host4 = Host(ad4, REPO, inject={"db_path": ":memory:", "clock": time.time})
    host4.boot()
    u4 = uid + "_menu2"
    drive(ad4, host4, "我是 人类", u4)
    jm = NL.join(drive(ad4, host4, "选职业", u4))
    if _exp14:
        _miss14 = [k for k, ln in _exp14.items() if ln not in jm]
        if _miss14:
            bad("★ P-50 域与槽位都在 ⇒ 菜单里每一门都要有那一行，缺：%s" % _miss14)
        else:
            ok("★ P-50 菜单里 %d 门都出了「优势 / 弱点」那一行（逐字对得上）" % len(_exp14))
    elif "优势" not in jm and "弱点" not in jm:
        ok("★ P-50 两头都没铺 ⇒ 第二步那一眼**没有**「优势 / 弱点」字样"
           "（真源没给句 ⇒ 菜单也就不许先印那两栏 —— 更不许自己编一句顶上）")
    else:
        bad("★ P-50 菜单里出现了「优势 / 弱点」而真源还没有那两句：%s" % jm[:200])
    # ③ 两态（探针自己造记录 + 临时**撤/注**槽位，用完即还原 —— 不靠「今天本来有没有」）
    #    ★ 2026-09-26 主线落槽位后改口径：真源行已落（SYS_CLS_EDGE 在表里）⇒「缺槽位」那一态
    #      要**自己撤走**才算数（原来写的是「今天这一态」，落完就假红）。撤/注都真调，强度只增不减。
    _TXT14 = _CA14._texts()
    _REC14 = {"adv": "（探针造的）优势那一句", "weak": "（探针造的）弱点那一句"}
    _TPL14 = "[A]{adv}[B]{weak}"              # 探针自己给的模板（不镜像真源那一行）
    _had14 = _TXT14.get(_tmp14)
    _cases14 = []
    if _had14 is not None:                    # 真源那条在 ⇒ 先真撤走 = 「缺槽位」那一态
        _TXT14.pop(_tmp14, None)
    try:
        _cases14.append(("撤走槽位 ⇒ 不出那一行", _CA14._cls_edge_line(_REC14) is None))
    finally:
        if _had14 is not None:
            _TXT14[_tmp14] = _had14
    _TXT14[_tmp14] = {"value": _TPL14, "params": ["adv", "weak"], "category": "系统",
                      "desc": "（probe_class 临时注入 —— 用完即撤）"}
    try:
        _cases14.append(("槽位在 · 域里缺一句 ⇒ 也不出（不许只印半句）",
                         _CA14._cls_edge_line({"adv": "只有优势"}) is None))
        _cases14.append(("两头全 ⇒ 逐字渲染（槽位模板 + 域里那两句）",
                         _CA14._cls_edge_line(_REC14)
                         == "[A]%s[B]%s" % (_REC14["adv"], _REC14["weak"])))
    finally:
        if _had14 is None:
            _TXT14.pop(_tmp14, None)
        else:
            _TXT14[_tmp14] = _had14
    if _had14 is None:                        # 真源行还没落：照旧「没有那一行」
        _cases14.append(("真源那条槽位仍不在 ⇒ 不出那一行", _CA14._cls_edge_line(_REC14) is None))
    else:                                     # 真源行已落：用**真源那条模板**渲染，逐字对账
        _cases14.append(("真源那条槽位在 ⇒ 真模板逐字渲染那一行",
                         _CA14._cls_edge_line(_REC14)
                         == _had14["value"].format(adv=_REC14["adv"], weak=_REC14["weak"])))
    _bad14 = [n for n, o in _cases14 if not o]
    if not _bad14:
        ok("★ P-50 接线两态真调（造记录 · 临时注入即撤）：%s" % " ｜ ".join(n for n, _ in _cases14))
    else:
        bad("★ P-50 接线两态有一条不过：%s" % _bad14)
    _leak14 = sorted({str(k) for k, v in C.items() for f in ("advantage", "flaw", "优势", "弱点")
                      if f in v})
    if not _leak14:
        ok("★ P-50 域里**没有**自己编的「优势 / 弱点」格（另一套字段名也不行："
           "先补真源行，句进 adv / weak 两格）")
    else:
        bad("★ P-50 域里自己编了「优势 / 弱点」：%s（真源没写 ⇒ 先补真源行）" % _leak14)

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
