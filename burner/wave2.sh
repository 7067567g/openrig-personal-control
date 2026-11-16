#!/usr/bin/env bash
# 空位即补：同时运行 runner 数 < 5 时，依次启动 P12、P13；15:00 或 STOP 退出
cd "$(dirname "$0")/.." || exit 1
started12=0; started13=0
while true; do
  [ -f burner/STOP ] && echo "[wave2] STOP" && exit 0
  [ "$(date +%H)" -ge 15 ] && echo "[wave2] 到 15:00 退出" && exit 0
  n=$(pgrep -fc 'run_queue.py --from' 2>/dev/null || echo 0)
  if [ "$started12" = 0 ] && [ "$n" -lt 5 ]; then
    BURNER_PORT=4717 setsid nohup python3 burner/run_queue.py --from 12 --once >> burner/runner-P12.out 2>&1 &
    started12=1; echo "[wave2] $(date '+%H:%M') 启动 P12（当时 runner=$n）"
  fi
  if [ "$started13" = 0 ] && [ "$started12" = 1 ] && [ "$n" -lt 5 ]; then
    BURNER_PORT=4718 setsid nohup python3 burner/run_queue.py --from 13 --once >> burner/runner-P13.out 2>&1 &
    started13=1; echo "[wave2] $(date '+%H:%M') 启动 P13（当时 runner=$n）"
  fi
  [ "$started12" = 1 ] && [ "$started13" = 1 ] && echo "[wave2] 两包均已派出，退出守护" && exit 0
  sleep 120
done
