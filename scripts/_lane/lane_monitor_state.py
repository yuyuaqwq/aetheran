# -*- coding: utf-8 -*-
"""车道锁状态门控（cron `monitor` 用）——输出必须**周期性变化**且不含逐 tick 变动的数字。

放法：`~/AppData/Local/hermes/scripts/lane_monitor_state.py`
      → cron job 的 `monitor` 写相对名 `lane_monitor_state.py`（cronjob action=update, monitor=...）

机制：每 tick 先跑本脚本；输出与上一 tick **逐字节相同** ⇒ 整轮跳过、不唤醒 agent（零 LLM 成本）；
      输出变化 ⇒ 唤醒 agent 并把 diff 注入 prompt。
⇒ 锁被占着时零成本等待，锁一释放 ≤ 触发间隔（建议 5 分钟）就接上。

★★ 2026-09-19 事故与修正（**这一版的核心改动，别改回去**）★★
  旧版空闲时打印裸 `LANE_FREE`（恒定不变）⇒ 若某一轮 agent 干完**没写锁**（例如它判断无事可做、
  只汇报了一句、或另一条线把锁删了），monitor 的输出就**永远停在同一个 FREE** ⇒ 每 tick 都
  判「没变化」⇒ **永久抑制、再也不唤醒**。实测两条自推进线（文案批 + 审计）从 18:16 起集体
  静默休眠，输出一串 `no_change (agent run suppressed)`，看起来像"没活干"，实际是**门控把自己
  锁死了**（之前能跑只是因为 agent 每轮都「写锁→干活→删锁」天然制造了 BUSY↔FREE 变化）。
  教训一句话：**「空闲」是稳态、不是事件** —— 靠变化触发的门控必须给空闲态装一个心跳，
  否则稳态就是坟场。
  修法：空闲态输出带 **5 分钟时间桶**（`LANE_FREE_0` / `LANE_FREE_1` 交替）⇒ 至少每 5 分钟
  必然变化一次（兜底唤醒）；忙碌态仍输出固定 `LANE_BUSY`（继续省钱）。
  桶里**只有桶号、没有当前时间**，所以不违反「不带逐 tick 变动的数字」这条硬规矩。

三态：
  LANE_FREE_<n>  无锁 → 唤醒（可以开工；n 每 5 分钟翻转，保证兜底唤醒）
  LANE_STALE     锁超过 TTL → 唤醒（残锁可抢；agent 自己会再核一次）
  LANE_BUSY      锁还新鲜 → 不唤醒（有人在干活）

★ 五条硬规矩（踩过才写下来，改这个脚本时别破坏）：
 1) **忙碌态输出必须恒定**：不能带 age / 时间戳 / pid → 带了就每 tick 都「变了」= 白烧 LLM。
    （空闲态例外：必须带时间桶，见上。区分点 = 忙碌态要"静"、空闲态要"动"。）
 2) **TTL 必须与两条自推进线 prompt 里的 TTL 一致**（当前 90 分钟）。TTL 不一致会出现
    「一边判残锁可抢、另一边还在用它」的错配 ⇒ 双写。
 3) **不做 pid 存活判断**：MSYS/git-bash 的 `$$` 是 MSYS 内部 pid，与 Windows pid 不同空间，
    `tasklist /FI "PID eq <msys-pid>"` 恒查不到 ⇒ 会把**正在干活**的轮次误判成残锁 ⇒ 双写。
    误判 STALE 的代价远大于多等一会儿，故只按 mtime+TTL 判。
 4) **多线相位错开**：共用一把锁的两个作业，**在 monitor 脚本里做相位偏移**比用 cron 表达式错开
    更稳（表达式一改就可能又撞上）——同目录放一份 `_b` 版，把桶号 `+1` 即可：
      主线：`(int(time.time()) // 300) % 2`        审计线：`((int(time.time()) // 300) + 1) % 2`
    ⇒ 两条线的「变化时刻」相差 5 分钟，同 tick 一起被唤醒的概率 ≈ 0。
 5) **monitor 只读、不抢锁**：它只做探测。抢锁是 agent 第 0 步的事（见 lane_lock.py 的原子 acquire）。
    若哪天改成 monitor 代抢，先想清楚「agent 没被成功唤醒时锁谁来放」——否则又是一次永久占道。

顺带：若哪天又要写 `tasklist` 的输出解析，注意**中文 Windows 的 tasklist 输出是 GBK**，
      Python 里 `subprocess.run(..., text=True)` 用 utf-8 解码会抛 UnicodeDecodeError
      （表现为线程里一堆 Traceback，异常被吞后静默走错分支）—— 用 bytes 模式再 `in` 比较。
"""
import os
import sys
import time

LANE = r'C:/Users/yuyu/AppData/Local/hermes/workspace/overnight/_cron_lane.lock'
TTL = 90 * 60          # 必须与两道 cron prompt 里的 TTL 一致
BUCKET = 5 * 60        # 空闲态心跳周期（5 分钟）
PHASE = 0              # ★ 多线错峰用：第二条线（审计）传 1 ⇒ 与主线相位相反


def _free_token():
    """空闲态令牌：带 5 分钟桶号 ⇒ 相邻两桶必不同 ⇒ 至少每 BUCKET 秒唤醒一次。"""
    return 'LANE_FREE_%d' % (((int(time.time()) // BUCKET) + PHASE) % 2)


def main():
    if not os.path.exists(LANE):
        print(_free_token())
        return
    try:
        age = time.time() - os.path.getmtime(LANE)
    except OSError:
        print(_free_token())
        return
    if age > TTL:
        print('LANE_STALE')
        return
    print('LANE_BUSY')


if __name__ == '__main__':
    # 第二条线：`python lane_monitor_state.py --phase 1`（或在 _b 副本里把 PHASE 设成 1）
    if '--phase' in sys.argv:
        try:
            PHASE = int(sys.argv[sys.argv.index('--phase') + 1])
        except (IndexError, ValueError):
            pass
    main()
    sys.stdout.flush()
