# Timeline — 2026-11-13

| 时间 | 事件 | 证据 |
|---|---|---|
| 08:04 | SCTG pilot / R01 开始 | `.sctg/runs/sctg-app-feel-r01-20261113` |
| 08:06 | R01 PASS | `ROUNDS.jsonl` |
| 08:12 | R02 PASS | `ROUNDS.jsonl` |
| 08:51 | R03 PASS | `ROUNDS.jsonl` |
| 09:11–09:35 | R04–R09 PASS | `ROUNDS.jsonl` |
| 12:16–12:56 | R10–R15 PASS | `ROUNDS.jsonl` |
| 12:48 | 旧 `BLOCKED` 写入 R15 | `artifacts/BLOCKED.history.txt` |
| 12:56 | R15 PASS；旧 `DONE` 写入 | `artifacts/DONE.invalid-20261113.txt` |
| 14:58 | R15.5 ADB 真机验收报告完成，ADB PASS + 4 项 NEED_MAIN | `artifacts/R15.5.md` |
| 15:10 | 状态文件被外部过程/agent 部分对账：ROUNDS 增加 R01/R02、BLOCKED/DONE 改名 | 当前 `.sctg` 快照 |
| 15:19:28 | 全局 OOM，kernel 杀 Chrome pid 7661 | `oom-evidence.txt` |
| 15:19:45 | GNOME Shell 被 OOM kill | journal |
| 15:20:14 | `dsh-terminal-13200-f7a7...` 峰值 4.6G | journal |
| 15:20:15–16 | systemd-oomd 杀 WeChat 7 进程、Chromium 1 进程 | journal |
| 15:20:18 | WeChat scope `oom-kill` | journal |
| 15:20:20 | GNOME Shell scope `oom-kill`；dsh-web 重启 | journal |
| 15:30:56 | `-.slice` 再次 kernel OOM | journal |
| 15:33:42 | `dsh-terminal-13200-d968...` 峰值 11.1G / swap 2.2G，被停止 | journal |
| 15:38:44 | `memory-guard.service` 启动（事故后缓解，不是原因） | `memory-guard.log` |
| 15:44 | 本次只读审计开始 | 本记录 |
