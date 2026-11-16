#!/usr/bin/env bash
# Heartbeat writer for a running burner pack.
#
# Resolves the workspace from this script's location; no machine paths.
#
# Usage:
#   bash burner/signaldeck-heartbeat.sh [run-id]
#   BURNER_RUN_ID=<run-id> bash burner/signaldeck-heartbeat.sh
set -u

WG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN="${1:-${BURNER_RUN_ID:-}}"
if [ -z "$RUN" ]; then
  echo "usage: $0 <run-id>   (or export BURNER_RUN_ID)" >&2
  exit 2
fi

RD="$WG/runs/$RUN"
LOG="$WG/burner/signaldeck-heartbeat.log"
mkdir -p "$RD/logs"

while true; do
  ts=$(date '+%Y-%m-%d %H:%M:%S')
  pid=$(pgrep -f "opencode run --format json --auto" | head -1 || true)
  round=$(grep -m1 '^round:' "$RD/PROJECT.md" 2>/dev/null | sed 's/^round: *//')
  state=$(grep -m1 '^state:' "$RD/PROJECT.md" 2>/dev/null | sed 's/^state: *//')
  printf '%s pid=%s round=%s state=%s\n' "$ts" "${pid:-none}" "${round:-?}" "${state:-?}" >> "$LOG"
  [ -f "$WG/burner/STOP" ] && exit 0
  sleep 60
done
