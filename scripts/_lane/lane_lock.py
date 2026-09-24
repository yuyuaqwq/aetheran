# -*- coding: utf-8 -*-
"""单车道锁（**原子**）：无人值守作业（cron）与交互会话共用一条「工作车道」，谁先拿谁干。

为什么需要：cron 与交互会话可能同时编辑/提交同一个仓库 ⇒ 两次 commit/push 交错、文件互相覆盖。
只查「工作树脏不脏」是**单向**防护（拦不住交互侧主动开工）—— 必须有一个显式的锁。

★★ 2026-09-19 事故与修正（**这一版的核心改动，别改回去**）★★
  旧版是「读锁文件 → 判断空闲 → 写锁」三步 —— **那不是原子的**（TOCTOU）：两个 agent 若在同一
  瞬间都读到「空闲」，就会双双动手。实测撞了两次：
    ① 审计线在文案批持锁期间照样写包仓（两条线的"共锁"实际没生效）；
    ② 主线自己用 `echo > 锁文件` **覆盖写**（绕开了工具），把 cron 正在跑的锁抢了，
       紧接着 `git apply` 打在对方的**未提交中间态**上（幸好 dry-run + 全或无救了回来）。
  修法两层：
    · 工具层：`O_CREAT|O_EXCL` 一步原子创建 —— 抢不到就是抢不到，没有"都以为自己拿到了"。
    · 纪律层：**任何一方（包括主线自己）都不许手写/手删锁文件**，一律走本工具。
      ★ 这条最容易被自己破：主线收口时图省事 `echo '{"owner":...}' > lock` 就撞车了。
        记住 —— **立了规矩的人第一个要守**；手写锁 = 放弃原子性 = 双写。
  另外：`release` 报 `NO_LOCK` 时**不是普通无事**，它是「锁被别人删了」的信号
  （实测审计线持锁 19:07→19:17 之间被第三方清掉，release 回 NO_LOCK）⇒ 该轮要意识到
  **互斥实际没 hold 住**，收尾时按"可能并发"的假设复核产物（显式清单 add / 干净配对验收）。

用法（shell）：
    python lane_lock.py acquire "<owner>"     # 拿到 → 退出 0；被占 → 退出 2（本轮退让）
    python lane_lock.py release "<owner>"     # 只有持有者能释放
    python lane_lock.py status                # 看谁占着（含已占多久 / 是否超 TTL）
    python lane_lock.py force                 # 强删（仅残锁；用前先确认持锁进程真没了）

接入干活脚本（bash）：
    PY=...; LANE=<此文件路径>; OWNER="${LANE_OWNER:-shell-$TAG}"
    "$PY" "$LANE" acquire "$OWNER" || { echo "车道被占 → 本轮退让"; exit 2; }
    trap '"$PY" "$LANE" release "'"$OWNER"'" >/dev/null 2>&1 || true' EXIT

设计要点：
  · **原子**：acquire 用 `O_CREAT|O_EXCL` 创建；失败只可能是"真的被别人拿着"。
  · TTL 默认 **90 分钟**（与 monitor 脚本的 TTL **必须一致**）：上一轮跑挂不会永久占道，
    超时可接管；不一致会出现「一边判残锁可抢、另一边还在用它」的错配 ⇒ 双写。
  · 同 owner 可重复 acquire（刷新时间戳）—— 长批次中途续拿不会自锁。
  · ★ **每落一个单元 `touch` 一次锁文件当心跳**：长轮不刷新会被 TTL 判成残锁 → 放进第二个轮次
    → 双写（判据只看 mtime，心跳就是唯一的"我还活着"信号）。
  · 锁文件是普通 JSON，人能直接看懂谁在跑、跑了多久。
  · owner 命名建议带来源：`wenan-<job前4位>` / `audit-<job前4位>` / `main-<批名>`，
    从汇报里就能认出是谁退让给的谁。
  · pid 写 `os.getpid()`（真 Windows pid），**别写 shell 的 `$$`**（MSYS 内部 pid，Windows 侧查不到）。
"""
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LOCK = os.environ.get('LANE_LOCK_FILE') or os.path.join(HERE, '_lane.lock')
TTL = int(os.environ.get('LANE_TTL_SEC', 90 * 60))


def _read():
    try:
        with io.open(LOCK, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _age():
    try:
        return time.time() - os.path.getmtime(LOCK)
    except OSError:
        return None


def _try_create(owner):
    """★ 原子创建。成功 True；已被占 False（不带任何竞争窗口）。"""
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        return False
    except OSError as exc:                      # 目录不存在等
        print('ERR：无法创建锁文件（%s）' % exc)
        raise
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump({'owner': owner, 'ts': int(time.time()), 'pid': os.getpid(),
                   'at': time.strftime('%Y-%m-%d %H:%M:%S')}, f, ensure_ascii=False)
    return True


def acquire(owner):
    cur, age = _read(), _age()
    if cur is not None and age is not None and age < TTL:
        print('BUSY：车道被 %s 占着（%.1f 分钟前，TTL %.0f 分钟）'
              % (cur.get('owner'), age / 60.0, TTL / 60.0))
        return 2
    if age is not None and age >= TTL:
        print('STALE：上一轮（%s，%.1f 分钟前）已超 TTL，本轮接管'
              % ((cur or {}).get('owner'), age / 60.0))
        try:
            os.remove(LOCK)
        except OSError:
            pass
    elif cur is None and age is not None:
        print('残锁文件不可解析（%.1f 分钟前）⇒ 接管' % (age / 60.0))
        try:
            os.remove(LOCK)
        except OSError:
            pass
    if _try_create(owner):
        print('OK：车道已归 %s' % owner)
        return 0
    cur = _read() or {}
    print('BUSY：并发抢占失败（当前 %s）' % cur.get('owner'))
    return 2


def release(owner):
    cur = _read()
    if cur is None:
        print('NO_LOCK：锁不存在 —— ★ 不是普通无事：说明锁被第三方删过，本轮互斥没 hold 住，'
              '收尾请按"可能并发"复核产物')
        return 0
    if owner and cur.get('owner') != owner:
        print('拒绝：锁在 %s 手里，%s 不能释放' % (cur.get('owner'), owner))
        return 3
    try:
        os.remove(LOCK)
    except OSError:
        pass
    print('OK：车道已空（%s 释放）' % owner)
    return 0


def status():
    cur, age = _read(), _age()
    if cur is None and age is None:
        print('FREE：车道空')
        return 0
    if cur is None:
        print('STALE：锁文件不可解析（%.1f 分钟前）' % (age / 60.0))
        return 0
    print('BUSY：%s（%.1f 分钟前，pid %s）%s'
          % (cur.get('owner'), (age or 0) / 60.0, cur.get('pid'),
             '  ← 已超 TTL，可接管' if (age or 0) >= TTL else ''))
    return 0


def force():
    try:
        os.remove(LOCK)
    except OSError:
        pass
    print('FORCED_REMOVED')
    return 0


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'status'
    owner = sys.argv[2] if len(sys.argv) > 2 else 'unknown'
    sys.exit({'acquire': lambda: acquire(owner),
              'release': lambda: release(owner),
              'status': status,
              'force': force}.get(cmd, lambda: 1)())
