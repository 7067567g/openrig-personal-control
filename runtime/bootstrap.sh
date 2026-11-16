#!/usr/bin/env bash
# Bootstrap the workflow-group control plane on a fresh machine.
#
# Creates .venv, installs dev dependencies, then runs the consistency gate and
# the test suite. Exits non-zero at the first failure.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
VENV="$ROOT/.venv"
PY="$VENV/bin/python"

say() { printf '==> %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

say "Checking Python"
command -v python3 >/dev/null 2>&1 || die "python3 is required"
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' \
  || die "Python >= 3.10 is required"
printf '    %s\n' "$(python3 --version)"

if [ ! -x "$PY" ]; then
  say "Creating virtual environment at .venv"
  if command -v uv >/dev/null 2>&1; then
    uv venv --python 3.12 "$VENV"
  else
    python3 -m venv "$VENV"
  fi
fi

say "Installing development dependencies"
if command -v uv >/dev/null 2>&1; then
  uv pip install --python "$PY" -r "$ROOT/requirements-dev.txt"
else
  "$PY" -m ensurepip >/dev/null 2>&1 || true
  "$PY" -m pip install --upgrade pip >/dev/null 2>&1 || true
  "$PY" -m pip install -r "$ROOT/requirements-dev.txt"
fi

say "Checking document consistency"
(cd "$ROOT" && "$PY" scripts/doc_consistency.py --check)

say "Running the test suite"
(cd "$ROOT" && "$PY" -m pytest tests -q)

cat <<'EOF'

Bootstrap complete.

Next steps:
  source .venv/bin/activate
  python3 scripts/openrig_preflight.py --json
  python3 scripts/wf.py new-run my-run-YYYYMMDD --goal "one-line goal" --tdo 2
  python3 scripts/wf.py brief --role pmo --run my-run-YYYYMMDD

See SETUP.md and WORKFLOW.md.
EOF
