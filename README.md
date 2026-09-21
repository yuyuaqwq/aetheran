# aetheran 数据包

> 《阿斯特兰：群雄纪》的数据包。**真源在策划案仓** `C:/Users/yuyu/aetheran-designer`，本包是它的单向导出。

## 怎么来的

```bash
python C:/Users/yuyu/aetheran-designer/_work/build_package.py C:/Users/yuyu/aetheran-package
```

构建器**不手打任何数值** —— 它 import 策划案仓的**权威脚本**：
| 本包的文件 | 来源 |
|---|---|
| `content/data/monsters.json` | `_work/W1E_monster_model.py` 的 `P1_ZONES` |
| `content/data/maps.json` | `_work/W2B_topology_check.py` 的 `NODES` / `OUT_EDGES` |

⇒ 策划案改了 → 重跑构建器 → 包跟着变（不会有第二套数据）。

## 怎么验证能加载

```bash
cd C:/Users/yuyu/framework-engine
python -c "from saintess_engine import package; print(package.load(r'C:/Users/yuyu/aetheran-package'))"
```

## 现状（P1 骨架）

- ✅ 能加载（manifest / entry / domains 齐）
- ✅ 两个域有真数据 + 包内 schema（编辑器可编）
- ⚠️ 只装配了「时间模型」一个 hook；公式族 F1–F12 / 面板聚合 / 技能表待 E1/E2 落地后接入
- ⬜ 待补域：skills / items / quests / npcs / drop_pools / classes / elements / wiki
