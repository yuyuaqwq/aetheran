# -*- coding: utf-8 -*-
"""重建「场景文案（节点级）」 —— B3-6a（源文档 → texts 域）

为什么：地图级槽位 SCENE_<地图> 是「踏进这张图的第一眼」（宽）；节点级 SCENE_<节点>
  是「站在这个点上的近景」（窄）。B1-5 立下的 29 个节点槽位一直没有正文、也没接上
  `观察` —— 玩家站在拾荒营地，看到的还是骨田那一段。本脚本补正文；接线在 cmds_ast。

源（每条带出处，锚点词必须能在源文档里找到 —— 防编造）：
  · 22_旧哨塔_逐间设计_v1.md        §二 12 房（描述 · 这一间教什么）
  · 00_第一阶段内容总纲_v1.md       §1.2 三条带 · 地标 · 主力怪
  · 12_怪物面板与精英词条池_v1.md   各节点的精英与头目

口径：
  · 03_风车镇_指令与回复.md §〇：场景描写 80–150 字，一屏读完 · 短句 · 有具体物件 · 不抒情
  · 10_地图探索元素库_v1.md §四①「显示必可触发」：正文提到的物件，都要能在该节点被指令碰到
    ⇒ 只写 pois / gathering 里真有的东西；22 文档点名而数据还没补的，留一句 note 给副本那一批
  · 正文是人写的（源文档给事实与处境），脚本负责：落表 · 对账 · 幂等

用法：python scripts/rebuild_scenes.py [--dry]      （连跑两次数据不变）
"""
from __future__ import annotations

import io
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = "C:/Users/yuyu/aetheran-plan/06_第一阶段垂直切片"
TEXTS = os.path.join(REPO, "content", "data", "texts.json")
MAPS = os.path.join(REPO, "content", "data", "maps.json")

MIN_LEN, MAX_LEN = 80, 200

#: key -> (正文, 源文档文件名, 锚点词)
SCENES = {
    # ── 北带：骨田 → 拾荒营地 → 旧哨塔下 ──────────────────────────
    "SCENE_BN_BONE": (
        "碑一块挨着一块，大半埋进土里。露出来的那截都被凿过，凿痕是旧的那种，边角磨圆了。"
        "十一块碑排成一排，前九块上有名字，后两块空着。碑缝里长着草，草根那儿的土是松的 —— 有人挖过。"
        "风过麦茬，沙沙响，像有人在远处翻东西。",
        "00_第一阶段内容总纲_v1.md", "半埋的碑"),
    "SCENE_BN_CAMP": (
        "营地是斜的：几块篷布搭在杆子上，风一来就往一边倒。火堆在中间，灰是散的，还温着，没人在守。"
        "东西捆好了分堆放，木头一堆、铁片一堆、骨头一堆，分得清清楚楚 —— 分给人看的。"
        "有人翻过这里，翻得很急，一样都没拿走。",
        "12_怪物面板与精英词条池_v1.md", "拾荒人"),
    "SCENE_BN_TOWER": (
        "塔近了比远处看着矮，也粗得多。石头一块块垒上去，缝里没长草 —— 垒它的人挑过石头。"
        "门前一块地是平的，平得像天天有人扫。门是铁的，关着，闩在里侧。"
        "往上看，塔顶缺的那一块正朝天敞着，风从那儿进，从那儿出。",
        "12_怪物面板与精英词条池_v1.md", "旧哨塔的守兵"),
    # ── 东带：白桦林 → 野狗窝 → 伐木棚 ───────────────────────────
    "SCENE_BE_BIRCH": (
        "林子里的白桦一般粗，只有靠里的几棵例外。路是人踩出来的，踩在落叶上，浅得只有一层。"
        "树皮上的刻痕一处比一处高 —— 刻的人一年比一年够得着更高。"
        "树根边冒出来一片菌，有几朵被踩坏了，断口还是新的。",
        "00_第一阶段内容总纲_v1.md", "刻着名字的树"),
    "SCENE_BE_DOGS": (
        "这块地不一样：草是倒的，压出三层圈来，最里那层最实。骨头散在圈边上，都是小块的，咬碎的。"
        "树上刻着记号，歪歪扭扭一个，隔几棵又一个 —— 一共七处，都是同一个手刻的。"
        "圈外生过火，火坑是凉的，灰被雨压平了。",
        "12_怪物面板与精英词条池_v1.md", "头狗"),
    "SCENE_BE_SHED": (
        "棚顶是后补的：新木条压在旧茅草上，压得马虎。棚里的料码得整齐，锯口是新茬 —— 活停在半道，人不在。"
        "地上摊着半本泡过水的东西，纸粘成一块，边上翘起来。斧子不在棚里，也不在棚外。",
        "12_怪物面板与精英词条池_v1.md", "被咬过的伐木工"),
    # ── 西带：浅滩 → 石滩渡口 → 旧渡口 ───────────────────────────
    "SCENE_BW_SHOAL": (
        "水退过一层，滩上留着湿泥。泥上有印子，拖出来的长条，不是脚。水边横着一道石缝，缝里塞着东西，露出来一点颜色。"
        "水里站着个什么，只露背，不动 —— 你不动，它也不动。水到小腿，底下的石头滑。",
        "12_怪物面板与精英词条池_v1.md", "浅滩水鬼"),
    "SCENE_BW_FERRY": (
        "渡口剩一块平台，木板缝里嵌着碎石，踩上去会晃。桩子断了两根，断口在水面底下，水一动就能看见。"
        "岸上的绳还系着，系法讲究，顺着水涨的方向 —— 系它的人懂水。石头上爬着东西，硬壳，一碰就缩成一块石头。",
        "12_怪物面板与精英词条池_v1.md", "石滩螃蟹"),
    "SCENE_BW_OLD_FERRY": (
        "旧渡口没有船了。栈桥剩几根黑桩斜插在水里，露水面一截。退潮的时候，水底下能看见台阶，一级一级往下，通到最深的地方 —— "
        "台阶是整齐的，边上有过栏杆，栏杆没了。水面一点动静都没有，风也不往这边来。",
        "12_怪物面板与精英词条池_v1.md", "沉尸"),
}

#: 旧哨塔 12 房 —— 描述与「这一间教什么」都照 22_旧哨塔_逐间设计_v1.md §二
#: （塔顶 SCENE_TOWER_TOP 已有正文，不在表里）
TOWER_SCENES = {
    "SCENE_TOWER_GATE": (
        "门是虚掩着的，闩在里侧 —— 有人从里面闩上它，然后没再出来。门缝里透出一点光，不是天光。"
        "门上砸过的印子都在同一个地方，砸了很多下，门没开。门闩上有三道划痕，都新，不像旧痕。",
        "22_旧哨塔_逐间设计_v1.md", "门闩在里面"),
    "SCENE_TOWER_HALL": (
        "门厅空着，地上站着两具东西。你进去，它们才动 —— 动得比你慢半拍。"
        "地上散着几块甲片，扣子还系着 —— 是从甲上拆下来的，拆得很干净。屋顶是完整的，雨没漏进来。"
        "这地方比外头看着完整得多。",
        "22_旧哨塔_逐间设计_v1.md", "慢半拍"),
    "SCENE_TOWER_ARMORY": (
        "架子还在，一格格排到墙那头。格子全空着，武器一件不剩 —— 不是被抢走的，是一件件收走的，收得很齐。"
        "每格下沿刻着一个名字，刻法都不一样，显然不是一个人刻的。地上摊着一块布，摊开过，又叠了回去。",
        "22_旧哨塔_逐间设计_v1.md", "架子上的名字"),
    "SCENE_TOWER_STAIR1": (
        "楼梯口堵着一个人。他背对着你，肩膀一下一下地动 —— 像在啃什么。"
        "楼梯贴着墙旋上去，扶手磨得发亮，是有人走了很多年才磨出来的。他把楼梯口占满了，从他身边过不去。",
        "22_旧哨塔_逐间设计_v1.md", "像在啃什么"),
    "SCENE_TOWER_OUTPOST_OUT": (
        "马道修在墙外侧，宽到两个人并排。三条影子在三个方向站着，头都朝着这边。"
        "你往边上退一步，墙就挡掉一条；再退，只剩一条还看得见你。道上的土是湿的，脚印踩得深，方向都朝里。",
        "22_旧哨塔_逐间设计_v1.md", "三条影子"),
    "SCENE_TOWER_OUTPOST_IN": (
        "里面站着一个还没散架的人形。甲扣得很齐，盾举在身前，脚是分开的，站得很稳。"
        "它不动 —— 你动，它才抬手挡一下，挡完又放下。盾面上一层薄锈，边缘却是亮的。"
        "它脚边的地磨出一圈浅印，绕着半间房。",
        "22_旧哨塔_逐间设计_v1.md", "纹丝不动"),
    "SCENE_TOWER_WATER_ROOM": (
        "水到小腿，踩下去只出你一个人的圈。有两个站在水里，只露上半身 —— 腿那截看不见。"
        "水面上漂着一页纸，湿透了，没沉。墙上有一道道浅痕，一排一排，从上往下，数到一半就停了。",
        "22_旧哨塔_逐间设计_v1.md", "半人深的水"),
    "SCENE_TOWER_STORAGE": (
        "东西是从别处搬来的，摆得比搬家还整齐：箱子摞到人高，绳索盘成一圈，木料按长短排开。"
        "整齐得不像逃难的人留下的 —— 有人在这儿住过，还打算一直住下去。架子最上层空出一格，被擦过。",
        "22_旧哨塔_逐间设计_v1.md", "有人在这儿住过很久"),
    "SCENE_TOWER_EMPTY_ROOM": (
        "床铺是整理过的。不是逃走的乱，是睡完觉、叠好被子、然后走了的那种整齐。"
        "桌上摊着一封信，写到一半就停了，收信人的名字被划掉。窗是关着的，插销插上了 —— 从里面插的。",
        "22_旧哨塔_逐间设计_v1.md", "叠好被子"),
    "SCENE_TOWER_HORN_ROOM": (
        "小厅正中一个石台，台上放着半截号角。断口是齐的 —— 像被切开的，不像摔断的。"
        "旁边立着一块碑，名字一排排往下刻，最后一个只刻了一半。石台前面的地被磨出一个浅坑，磨了很多年。",
        "22_旧哨塔_逐间设计_v1.md", "半截号角"),
    "SCENE_TOWER_STAIR2": (
        "窄梯贴着墙旋上去，宽到刚好一个肩膀。梯道上散着东西，没散完：一节骨、一片甲、一颗扣子，都靠边放着 —— "
        "有人走过，把挡路的踢到了边上。上面有光亮着，但塔顶那个缺口不朝这边。",
        "22_旧哨塔_逐间设计_v1.md", "两侧还有东西没散"),
}
SCENES.update(TOWER_SCENES)

#: 22_旧哨塔_逐间设计_v1.md §一 的「教什么」列 —— 落到 desc（槽位说明里要能看出这间房教什么）
TEACH = {
    "SCENE_TOWER_GATE": "入口（不教机制，只给一个不对劲的感觉）",
    "SCENE_TOWER_HALL": "A3 行动序",
    "SCENE_TOWER_ARMORY": "探索资源（奖励房）",
    "SCENE_TOWER_STAIR1": "A1 打断",
    "SCENE_TOWER_OUTPOST_OUT": "D1 射程",
    "SCENE_TOWER_OUTPOST_IN": "A2 霸体",
    "SCENE_TOWER_WATER_ROOM": "环境（水面导电 · 水里 spd 降）",
    "SCENE_TOWER_STORAGE": "B1 资源",
    "SCENE_TOWER_EMPTY_ROOM": "叙事（最安静的一间）",
    "SCENE_TOWER_HORN_ROOM": "C1 印记（层主房）",
    "SCENE_TOWER_STAIR2": "连贯（前面四课合起来用一次）",
}
STALE = "（每间房要回答「这一间教什么」）"


def _load(path):
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


def _apply(tx):
    """把 SCENES 落到表上（值 + desc）—— 回改动的键。"""
    changed = []
    for k, (val, _fn, _a) in SCENES.items():
        rec = tx[k]
        d = (rec.get("desc") or "").replace(STALE, "").split(" ｜教：")[0]
        d = d.replace(" · ★ 已写正文", "").strip()
        if k in TEACH:
            d = d + " ｜教：" + TEACH[k]
        d = d + " · ★ 已写正文"          # 幂等：每次都从「主体 + 教什么」重算
        if rec.get("value") != val or rec.get("desc") != d:
            rec["value"] = val
            rec["params"] = rec.get("params") or []
            rec["desc"] = d
            changed.append(k)
    return changed


def main():
    dry = "--dry" in sys.argv
    tx = _load(TEXTS)
    maps = _load(MAPS)
    docs = {}
    for _k, (_v, fn, _a) in SCENES.items():
        if fn not in docs:
            docs[fn] = io.open(os.path.join(DOCS, fn), encoding="utf-8").read()

    fails = []
    def ok(m): print("  ✓ " + m)
    def bad(m): fails.append(m); print("  ✗ " + m)

    print("场景文案（节点级）—— 源文档 → texts 域" + ("（dry 跑）" if dry else ""))

    # ① 表里的槽位都真存在（不许凭空造槽位）
    miss = [k for k in SCENES if k not in tx]
    (bad if miss else ok)("槽位都在 texts 域：%s" % miss if miss else
                          "表里 %d 个槽位都在 texts 域" % len(SCENES))

    # ② 正文成篇（03 §〇：一屏读完）
    off = sorted((k, len(v)) for k, (v, _f, _a) in SCENES.items() if not (MIN_LEN <= len(v) <= MAX_LEN))
    (bad if off else ok)("字数越界：%s" % off if off else
                         "正文都在 %d–%d 字（最短 %d / 最长 %d）"
                         % (MIN_LEN, MAX_LEN, min(len(v) for v, _f, _a in SCENES.values()),
                            max(len(v) for v, _f, _a in SCENES.values())))

    # ③ 锚点词在源文档里找得到 —— 防编造（正文里的事实必须有出处）
    fake = [(k, a, fn) for k, (_v, fn, a) in SCENES.items() if a not in docs[fn]]
    (bad if fake else ok)("锚点词对不上源文档：%s" % fake if fake else
                          "每条正文的锚点词都在它引的源文档里（%d 份文档）" % len(docs))

    # ④ 应用（内存里先算一遍；dry 不落盘）
    changed = _apply(tx)

    # ⑤ 覆盖：地图上每个节点都能取到场景槽位（节点级 或 地图级兜底）
    sys.path.insert(0, REPO)                      # 与线上同一个解析口（content/scene.py，零依赖）
    from content.scene import resolve, node_key
    nodes = [(loc, n["id"]) for loc, m in maps.items() for n in (m.get("nodes") or [])]
    unr = [(loc, nd) for loc, nd in nodes if not resolve(tx, loc, nd)]
    nn = [1 for _l, nd in nodes if node_key(nd) in tx]
    (bad if unr else ok)("取不到场景的节点：%s" % unr if unr else
                         "★ %d 个节点都能取到场景（节点级 %d · 其余退地图级第一眼）" % (len(nodes), len(nn)))

    # ⑥ 场景类没有待填了（这一批的工单清完）
    todo = [k for k, v in tx.items() if v.get("category") == "场景" and "〔待填" in (v.get("value") or "")]
    (bad if todo else ok)("场景类还有待填：%s" % todo if todo else "场景类 0 条待填（%d 条都有正文）"
                          % len([1 for v in tx.values() if v.get("category") == "场景"]))

    print()
    print("  · 本次改动 %d 处%s" % (len(changed), "（dry：未写盘）" if dry else ""))
    if changed and not dry:
        with io.open(TEXTS, "w", encoding="utf-8", newline="\n") as f:
            json.dump(tx, f, ensure_ascii=False, indent=2)
            f.write("\n")
        again = _apply(_load(TEXTS))
        print("  · 幂等复跑：再应用一次改动 %d 处" % len(again))
        if again:
            bad("幂等复跑还有改动：%s" % again)

    print()
    print("结果：%s" % ("全绿 ✓" if not fails else "有红 ✗（%d）" % len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
