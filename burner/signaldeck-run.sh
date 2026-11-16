#!/usr/bin/env bash
# Launch a single burner pack manually (bypasses run_queue.py).
#
# All paths are resolved from this script's location; nothing machine-specific
# is baked in. The API key is REQUIRED from the environment: this script never
# reads a credential file.
#
# Usage:
#   export DEEPSEEK_API_KEY=...          # required
#   export OPENCODE_API_KEY=...          # required if your opencode build needs it
#   export OPENCODE_MODEL=deepseek/deepseek-flash   # optional
#   export BURNER_PROMPT=burner/<pack>-prompt.txt   # optional, default below
#   bash burner/signaldeck-run.sh
#
# For the batch path over burner/queue.json, use burner/run_queue.py instead.
set -euo pipefail

WG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WG"

: "${DEEPSEEK_API_KEY:?export DEEPSEEK_API_KEY before running this script}"
if [ -n "${OPENCODE_API_KEY:-}" ]; then
  export OPENCODE_API_KEY
fi

PROMPT="${BURNER_PROMPT:-burner/signaldeck-prompt.txt}"
MODEL="${OPENCODE_MODEL:-deepseek/deepseek-flash}"

[ -f "$PROMPT" ] || { echo "missing prompt file: $PROMPT" >&2; exit 2; }
[ -x .venv/bin/activate ] && . .venv/bin/activate

RUN_ID="${BURNER_RUN_ID:-manual-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "runs/$RUN_ID/logs"
echo "run=$RUN_ID model=$MODEL prompt=$PROMPT" >&2

exec opencode run --format json --auto --model "$MODEL" "$(cat "$PROMPT")"
