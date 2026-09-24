#!/usr/bin/env bash
# 阿斯特兰一键盘点：三仓状态 + 全量探针 + 端到端 + 机器人
# 用法：bash scripts/ecosystem_check.sh
set -u
PY="C:/Users/yuyu/AppData/Local/Programs/Python/Python312/python.exe"
ENGINE="C:/Users/yuyu/framework-engine"
PKG="C:/Users/yuyu/aetheran-package"
PLAN="C:/Users/yuyu/aetheran-plan"
export GWEN_ENGINE="$ENGINE"

echo "==== 1. 三仓状态 ===="
for r in "$PLAN" "$PKG" "$ENGINE"; do
  printf "%-40s " "$(basename "$r")"
  d=$(git -C "$r" status --short 2>/dev/null | grep -v '\.db$' | head -3)
  if [ -z "$d" ]; then echo "干净 ✓"; else echo "脏："; echo "$d" | sed 's/^/      /'; fi
done

echo
echo "==== 2. 全量探针 ===="
cd "$PKG" || exit 1
pass=0; fail=0
for f in scripts/probe_*.py; do
  n=$(basename "$f")
  if "$PY" "$f" > "$TEMP/p.out" 2>&1; then pass=$((pass+1)); else
    fail=$((fail+1)); echo "  ✗ $n"; tail -3 "$TEMP/p.out" | sed 's/^/      /'
  fi
done
echo "  探针：$pass 绿 / $fail 红"

echo
echo "==== 3. 端到端冒烟 ===="
"$PY" scripts/e2e_drive.py "观察" "往东" "观察" "返回" 2>&1 | tail -8

echo
echo "==== 4. 机器人 ===="
netstat -ano 2>/dev/null | grep 6185 | head -1 || echo "  (6185 无监听 —— AstrBot 没在跑)"
grep -n "注册 [0-9]* 条" "$HOME/qqbot/data/logs/astrbot.log" 2>/dev/null | tail -1 | cut -c1-150
