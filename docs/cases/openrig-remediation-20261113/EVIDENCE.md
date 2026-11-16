# Evidence

## 轮次

```text
rounds.yaml slots: 33
product: R01–R30
prep: R05.5, R09.5, R15.5
needs_main: R16, R25, R29, R30
external: R21, R22, R23, R28
ROUNDS.jsonl PASS: R01–R15 = 15
R15.5: report exists, not in ROUNDS.jsonl
```

## 时间

```text
R03 08:51:34 -> R15 12:56:10 = 4h04m36s / 13 rounds ≈ 18.8 min/round
R10 12:16:45 -> R15 12:56:10 = 39m25s / 5 rounds ≈ 7.9 min/round
```

## 内存事故

```text
15:19:28 kernel OOM: killed chrome pid 7661
15:20:15 systemd-oomd: killed wechat (7 procs)
15:20:16 systemd-oomd: killed chromium (1 proc)
15:20:20 gnome-shell oom-kill
15:20:14 dsh-terminal-13200-f7a7... peak 4.6G
14:57:40 dsh-terminal-13200-0602... peak 7.0G
15:33:42 dsh-terminal-13200-d968... peak 11.1G / swap 2.2G
```

## 当前快照

- `artifacts/ROUNDS.jsonl`
- `artifacts/BLOCKED.history.txt`
- `artifacts/DONE.invalid-20261113.txt`
- `artifacts/rounds.yaml`
- `artifacts/auto_driver.py`
- `artifacts/round_checks.py`
- `artifacts/R15.5.md` / `.json`（已脱敏）
- `artifacts/memory-snapshot.txt`
- `artifacts/oom-evidence.txt`
- `artifacts/git-status.txt`

## 关键命令（只读复现）

```bash
cd /home/a7067567g/下载/deepseek/月月bot/wechat-bridge-v2
python3 - <<'PY'
import yaml
d=yaml.safe_load(open('tools/sctg/rounds.yaml'))
print(len(d['rounds']), [r['id'] for r in d['rounds'] if r.get('needs_main')], [r['id'] for r in d['rounds'] if r.get('external')])
PY
cat .sctg/runs/sctg-app-feel-auto-20261113/ROUNDS.jsonl
journalctl -k --since '2026-11-13 15:15:00' --until '2026-11-13 15:40:00' | grep -iE 'oom|killed process'
journalctl --user --since '2026-11-13 15:15:00' --until '2026-11-13 15:40:00' | grep -iE 'dsh-terminal|oom|memory-guard'
```
