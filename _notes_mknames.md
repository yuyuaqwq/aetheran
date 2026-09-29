# P2-4b 机器键上屏 · 本车道交接（copy-p3 · 2026-09-29）

## 交了什么

```
commit 4b0dc56（包仓）· 引擎零改动
新增  content/rules/name_map.json   机器键 → 显示名（23 状态键 + 4 资源键 + 0 血条键）
新增  content/name_map.py           翻译层（TranslatedTable 代理 + 装配期 check_domain）
新增  scripts/probe_machine_key_names.py   判据（全绿 0 失败）
改    content/battle_text.py        battle_text() 返回翻译代理
改    content/cues.py               check_domain 里加 name_map 对账
改    scripts/probe_cues.py         ③ identity 链多一跳（补钉「代理不持第二份文案」）
```

## ★ 与交接文档假设不同的一点（下一个人别再按旧假设做）

文档说「要改的是引擎 cue 的 payload（把 key 换成 name）⇒ 违反铁律，须鱼鱼点头」。
**实测下来不需要改引擎**：渲染那一层本来就是内容侧（`content/cues.py` 订阅表 +
`BT.battle_text()` 注入），机器键只是**传进 payload 的 ASCII 值**。
在**渲染前**翻译即可 —— 引擎只发中性键，两款游戏共用，换游戏只换 `name_map.json`。
⇒ 「第二款游戏不改一行能用」这条判据天然成立。

## 还没做的（下一批的活，按优先级）

```
① gauge 那 4 条（GAUGE_GAIN/TRIGGER/SHAKEN/PHASE_PRESERVE）
   现状：name_map 的 bar 段是空的 —— 因为 mech_cfg("enemy_bar") 包内零声明，
   玩家根本碰不到。★ 机制上线时填 bar 段即自动接上，翻译层不用改。
② action/tag 那 2 条（COMBAT_CORE_UNKNOWN_ACTION / COMBAT_ACTIONS_ENCHANT_FOLLOWUP）
   现状：登记在 name_map.pending_actions()，刻意不接线（要么等机制上线、要么是兜底句）。
   接线时把它们挪进 name_map.json 的 action 段即可。
③ ★ 引擎既有欠账（**要鱼鱼点头才能动**）：
   effects.py 的 cue payload 里有 7 处 actor.get('name', '目标') —— 名字兜底词硬编码中文。
   性质 = 「兜底词硬编码」，与本车道修的「机器键漏屏」是两种缺陷。
   探针 ④b 钉住「不许变多」（实测基线 7），但**没修** —— 改引擎须单独立项。
```

## 踩过的坑（下批别再犯）

```
① ★ 探针 ④ 扫行找中文会把 docstring 里的说明文字算进去 ⇒ 改用 AST 取 payload 源码段。
   且 payload 是 _cue() 的**第 4 个位置实参**（args[3:]）；只扫 args[:3] 会「抓到 0 个」
   而判据照样绿 ⇒ **空匹配必须自己判红**（本支用 _MIN_KEYSLOT 下限钉住）。
② ★ 探针夹具要记得传 `t`（引擎 TIME_SLOT 定的每条 cue 必带那格）——
   漏了它 safe_format 不抛，模板原样吐回，会让人误以为翻译没生效。
③ ★ 代理类不能写 __slots__：既有探针（probe_cues ⑧）会在实例上猴补 render_or。
④ ★ 代理的缓存必须跟着真表走：探针猴补槽位时会 BT._CACHE.pop("table") 重建，
   代理若自己缓存一张，就会端过期表发那一行（实测 probe_cues ⑥ 由此红）。
⑤ ★ 基线数字必须现测，不能眼估：我眼估「'目标' 5 处」，实测 7 处。
```

## 门禁现状（提交后现跑）

```
probe_machine_key_names  rc=0 全绿（21 条判据）
probe_cues               rc=0 全绿
probe_texts / copy / combat  rc=0 全绿
probe_dialogues          rc=1（1 红）—— 既有基线，stash 本批后复跑逐条同因
probe_mech               rc=1（2 红）—— 既有基线：引擎仓被别车道弄脏（脏树红）
e2e 真宿主               建号→往北→遭遇田鼠→打完，战斗日志 ASCII 机器键 0 命中
覆盖扫                   15 槽位 × 23 键 = 345 组，ASCII 漏出 0 · 槽位未填 0
```
