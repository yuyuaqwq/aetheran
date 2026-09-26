# -*- coding: utf-8 -*-
"""探针：races 域读得到 · 六族形状对（2 正 1 负 · 至少一条可见性）· 数值天赋值域合理。

⑪⑫ ★ P-68（2026-09-26 · 本波 w-h-ux · **裁决：出现在玩家眼前**）：`home` / `lifespan`
   两格放进「出身」那一屏、一行 —— 读端**只有一处**（`content/cmds_ast.py::origin`）·
   两态一致（半截 = 红）· 真源 `04 §三` 那一行与槽位**两态互锁** · 造记录 + 临时注入直调接线。

用法（在 aetheran-package 仓根跑）：
    GWEN_ENGINE=C:/Users/yuyu/framework-engine python scripts/probe_races.py
"""
from __future__ import annotations

import json
import io
import os
import time
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENGINE = os.environ.get("GWEN_ENGINE", "C:/Users/yuyu/framework-engine")
sys.path.insert(0, str(REPO))
sys.path.insert(0, ENGINE)

from saintess_engine.package import load_stack                       # noqa: E402

ok = True
KINDS = ("可见性", "数值", "经济")


def chk(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("  %s %s%s" % ("✓" if cond else "✗", label, ("  —— %s" % extra) if extra else ""))


print("探针：races 域（六族天赋）")
st = load_stack(str(REPO), inject={"db_path": os.path.join(os.environ.get("LOCALAPPDATA", "/tmp"), "Temp", "ast_probe.db"), "clock": time.time})
st.install()

# ① 域读得到
rc = st.domain("races")
chk("races 域读得到", rc is not None, "%d 族" % (len(rc) if rc else 0))
if not rc:
    sys.exit(1)

# ② 六族
chk("六族齐全", len(rc) == 6, " · ".join(v["name"] for v in rc.values()))

# ③ 每族 2 正 1 负
bad = [k for k, v in rc.items() if len(v.get("talents", [])) != 2 or not v.get("cost")]
chk("每族 2 条正天赋 + 1 条负代价", not bad, "例外：%s" % bad if bad else "")

# ④ ★ 品味判据：每族正向里至少一条「可见性」
bad4 = [k for k, v in rc.items()
        if not any(t.get("kind") == "可见性" for t in v.get("talents", []))]
chk("★ 每族至少一条「可见性」正天赋", not bad4, "缺：%s" % bad4 if bad4 else "")

# ⑤ kind 合法
bad5 = []
for k, v in rc.items():
    for t in list(v.get("talents", [])) + [v.get("cost")]:
        if t and t.get("kind") not in KINDS:
            bad5.append("%s/%s=%s" % (k, t.get("id"), t.get("kind")))
chk("天赋类型合法（可见性/数值/经济）", not bad5, " · ".join(bad5))

# ⑥ id 唯一
ids = []
for k, v in rc.items():
    ids.append(k)
    ids += [t["id"] for t in v.get("talents", [])]
    ids.append(v["cost"]["id"])
chk("id 全局唯一", len(ids) == len(set(ids)), "%d 个 id" % len(ids))

# ⑦ 六句「为什么来」各不相同
lines = [v.get("line", "") for v in rc.values()]
chk("六句「为什么来」互不相同", len(set(lines)) == 6 and all(lines))

# ⑧ 数值类天赋的 values 值域（百分比 ±25 内）
bad8 = []
for k, v in rc.items():
    for t in list(v.get("talents", [])) + [v.get("cost")]:
        for key, val in (t or {}).get("values", {}).items():
            if "pct" in key and not (-25 <= val <= 25):
                bad8.append("%s.%s=%s" % (t["id"], key, val))
chk("数值类天赋百分比在 ±25 内", not bad8, " · ".join(bad8))

# ⑨ schema 在
sch = REPO / "schemas/races.schema.json"
chk("races.schema.json 在位", sch.exists(), str(sch.name))

# ⑩ 通路与反面都写了（设计判据：每族一条别人走不了的路 + 一条真的疼的代价）
bad10 = [k for k, v in rc.items() if not v.get("path") or not v.get("flip")]
chk("每族都写了「专属通路 + 反面」", not bad10, "缺：%s" % bad10 if bad10 else "")

# ⑪ ★ P-68（2026-09-26 · 本波 w-h-ux · **裁决：出现在玩家眼前**）—— 六族数据里都有 `home`（家乡）
#   与 `lifespan`（寿数）；本波裁：**放进「出身」那一屏（`04 §三`）、一行**（第三行）。
#   依据：① 这两格是玩家认识自己角色的第一批信息，而 `出身` 正是那一屏（`观察` 是「眼下这一站」、
#   `状态` 是「这一会话的数字」—— 两处都不带族谱那一层）；② 一行就够（前缀 `家乡 · … ｜ 寿数 · …`）。
#   ⇒ 读端**只有一处**：`content/cmds_ast.py::origin`（谁在别处再读一次就红 —— 位置只有一处）。
bad11 = [k for k, v in rc.items() if not v.get("home") or not v.get("lifespan")]
chk("★ P-68 · 六族的 `home` / `lifespan` 两格数据都在 —— %s"
    % " · ".join("%s=%s／%s" % (v["name"], v["home"], v["lifespan"]) for v in rc.values()),
    not bad11, "缺：%s" % bad11 if bad11 else "")
_READERS11 = {}
# ★ 覆盖面要跟判据一起加（K61）：不只 `content/*.py` —— content 递归 + scripts + editor 全扫
#   （本探针自己除外：它的注释与判据本来就写着这两个词）。
for _f11 in (sorted((REPO / "content").rglob("*.py")) + sorted((REPO / "scripts").glob("*.py"))
             + sorted((REPO / "editor").rglob("*"))):
    if not _f11.is_file() or _f11.name == "probe_races.py" or "__pycache__" in str(_f11):
        continue
    try:
        _t11 = _f11.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        continue
    _hit11 = [_kw for _kw in ('"home"', "'home'", '"lifespan"', "'lifespan'") if _kw in _t11]
    if _hit11:
        _READERS11[str(_f11.relative_to(REPO)).replace("\\", "/")] = _hit11
_ALLOWED11 = {"content/cmds_ast.py"}          # ★ P-68：唯一的读端（`origin` —— 出身那一屏那一行）
_extra11 = {k: v for k, v in _READERS11.items() if k not in _ALLOWED11}
chk("★ P-68 · `home` / `lifespan` 的读端**只有一处** —— `content/cmds_ast.py::origin`"
    "（出身那一屏那一行）；别处再读一次（`观察` / `状态` / 面板…）就红",
    _ALLOWED11 <= set(_READERS11) and not _extra11, "%s" % _READERS11)
# 登记的另一半依据（真源那侧）：`04_指令总表 §三` 的 `出身` 那一行 —— **两态互锁**：
#   槽位没铺 ⇒ 真源那一行还是旧写法（族 + 那句「为什么来」）；槽位铺了 ⇒ 那一行必须已含
#   「家乡 · 寿数」。哪一头单独动了，这里都当场红（提醒另一头跟上）。
_L11, _TAIL11 = [], os.environ.get("AST_PLAN", "C:/Users/yuyu/aetheran-plan")
_DOC0411 = os.path.join(_TAIL11, "06_第一阶段垂直切片", "04_指令总表.md")
if os.path.exists(_DOC0411):
    with io.open(_DOC0411, encoding="utf-8") as _fh11:
        _L11 = [_ln.strip() for _ln in _fh11 if "出身" in _ln and "|" in _ln]
_DOC11 = " ".join(_L11)
_DOC_SYNC11 = ("家乡" in _DOC11 and "寿数" in _DOC11)
print("  · 真源 `04 §三` 的 `出身` 那一行：%s" % (_L11[0][:96] if _L11 else "（没解析到）"))

# ⑫ ★ P-68（同一裁决的另一半）：**两态一致（半截 = 红）** + 真机那一屏真敲一次
#   （与 `probe_class ⑭` 同一套形状：键名钉住 · 两头必须一起在 · 造记录 + 临时注入直调接线）
from saintess_engine.host.runtime import Host as _Host12                    # noqa: E402
from content import cmds_ast as _CA12                                       # noqa: E402


class _Ad12(object):
    """最小适配器（照 `scripts/e2e_drive.py` 的真宿主契约）—— 本探针只在 ⑫ 真敲两下。"""

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


def _drive12(ad, host, text, uid):
    ad.out = []
    host.handle({"uid": uid, "group_id": "g_races_probe", "text": text})
    return list(ad.out)


_SK12 = _CA12.PENDING_SLOTS.get("origin_home")
chk("★ P-68 待槽位的**键名** = SYS_ORIGIN_HOME", _SK12 == "SYS_ORIGIN_HOME", "%r" % _SK12)
_half12 = [k for k, v in rc.items() if bool(v.get("home")) != bool(v.get("lifespan"))]
chk("★ P-68 六族的两格一起在（只写一格 = 半截 ⇒ 那一行不出）", not _half12, "%s" % _half12)
_tx12 = st.domain("texts") or {}
_slot12 = _SK12 in _tx12
_exp12 = {k: _CA12._origin_home_line(v) for k, v in rc.items()}
_exp12 = {k: v for k, v in _exp12.items() if v}
chk("★ P-68 两头一致：域里两格 %d 族 · texts 那条槽位 %s —— %s"
    % (len(rc), "在" if _slot12 else "不在",
       "（真源行已落，那一行开始出现在出身那一屏）" if _slot12
       else "今天**都没铺**（真源行还没写 —— 本路不碰共享面）"),
    bool(_exp12) == bool(_slot12), "域出 %d 行 · 槽位 %s" % (len(_exp12), _slot12))
chk("★ P-68 槽位%s ⇒ 真源 `04 §三` 的 `出身` 那一行%s（两态互锁：一头动了另一头必须跟上）"
    % ("已铺" if _slot12 else "未铺",
       "**必须**已含「家乡 · 寿数」" if _slot12 else "今天还是旧写法（族 + 那句「为什么来」）"),
    (_DOC_SYNC11 if _slot12 else (not _DOC_SYNC11)) and bool(_L11))
_ad12 = _Ad12()
_host12 = _Host12(_ad12, str(REPO), inject={"db_path": ":memory:", "clock": time.time})
_host12.boot()
_u12 = "u_races_p68"
_drive12(_ad12, _host12, "我是 人类", _u12)
_or12 = "\n".join(_drive12(_ad12, _host12, "出身", _u12))
_line12 = _exp12.get("race_human")
if _line12:
    chk("★ P-68 槽位与域都在 ⇒ 出身那一屏真出那一行（逐字）", _line12 in _or12, _or12[:140])
else:
    chk("★ P-68 两头都没铺 ⇒ 出身那一屏**没有**「家乡 / 寿数」字样"
        "（真源没给句 ⇒ 不许先印 —— 更不许自己编一行顶上）",
        "家乡" not in _or12 and "寿数" not in _or12, _or12[:140])
_TXT12 = _CA12._texts()
_REC12 = {"home": "（探针造的）家乡", "lifespan": "（探针造的）寿数"}
_TPL12 = "<H>{home}</L>{life}"        # 探针自己给的模板（不镜像真源那一行）
_had12 = _TXT12.get(_SK12)
_cases12 = []
# ★ 2026-09-26 主线落槽位后改口径：「缺槽位」那一态要**自己撤走**才算数
#   （原来写的是「今天这一态」，真源行一落就假红）。撤 / 注都真调，强度只增不减。
if _had12 is not None:                # 真源那条在 ⇒ 先真撤走 = 「缺槽位」那一态
    _TXT12.pop(_SK12, None)
try:
    _cases12.append(("撤走槽位 ⇒ 不出那一行", _CA12._origin_home_line(_REC12) is None))
finally:
    if _had12 is not None:
        _TXT12[_SK12] = _had12
_TXT12[_SK12] = {"value": _TPL12, "params": ["home", "life"], "category": "系统",
                 "desc": "（probe_races 临时注入 —— 用完即撤）"}
try:
    _cases12.append(("槽位在 · 域里缺一格 ⇒ 也不出",
                     _CA12._origin_home_line({"home": "只有家乡"}) is None))
    _cases12.append(("两头全 ⇒ 逐字渲染（槽位模板 + 域里那两格）",
                     _CA12._origin_home_line(_REC12)
                     == "<H>%s</L>%s" % (_REC12["home"], _REC12["lifespan"])))
finally:
    if _had12 is None:
        _TXT12.pop(_SK12, None)
    else:
        _TXT12[_SK12] = _had12
if _had12 is None:                    # 真源行还没落：照旧「没有那一行」
    _cases12.append(("真源那条槽位仍不在 ⇒ 不出那一行", _CA12._origin_home_line(_REC12) is None))
else:                                 # 真源行已落：用**真源那条模板**渲染，逐字对账
    _cases12.append(("真源那条槽位在 ⇒ 真模板逐字渲染那一行",
                     _CA12._origin_home_line(_REC12)
                     == _had12["value"].format(home=_REC12["home"], life=_REC12["lifespan"])))
_bad12 = [n for n, o in _cases12 if not o]
chk("★ P-68 接线两态真调（造记录 · 临时注入即撤）：%s" % " ｜ ".join(n for n, _ in _cases12),
    not _bad12, "%s" % _bad12)

print()
print("六族速览：")
for k, v in rc.items():
    plus = " · ".join("%s(%s)" % (t["name"], t["kind"]) for t in v["talents"])
    print("  %-16s %s  →  正：%s ｜ 负：%s(%s)" % (
        k, v["name"], plus, v["cost"]["name"], v["cost"]["kind"]))

print()
print("结果：%s" % ("全绿 ✓" if ok else "有红 ✗"))
sys.exit(0 if ok else 1)
