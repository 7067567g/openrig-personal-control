#!/usr/bin/env bash
# evidence_run.sh — run a command/pipeline and keep real rc + stdout/stderr hashes.
#
# Usage:
#   scripts/evidence_run.sh --out <file> --label <name> -- <cmd...>
#   scripts/evidence_run.sh --out <file> --label <name> --shell '<shell pipeline>'
#
# Header written to <file>:
#   command=, label=, cwd=, started_at=, finished_at=, rc=,
#   stdout_sha256=, stderr_sha256=
# followed by raw "--- stdout ---" / "--- stderr ---" sections.
# The wrapper exits with the command's real rc.
set -uo pipefail

usage() {
  sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
}

out=""
label=""
mode=""
shell_cmd=""

while [ $# -gt 0 ]; do
  case "$1" in
    --out) out="${2:-}"; shift 2 ;;
    --label) label="${2:-}"; shift 2 ;;
    --shell) mode="shell"; shell_cmd="${2:-}"; shift 2 ;;
    --) shift; [ -n "$mode" ] || mode="cmd"; break ;;
    -h|--help) usage ;;
    *) echo "unknown argument: $1" >&2; usage ;;
  esac
done

[ -n "$out" ] || { echo "--out is required" >&2; exit 2; }
[ -n "$label" ] || { echo "--label is required" >&2; exit 2; }
if [ "$mode" = "shell" ] && [ -z "$shell_cmd" ]; then
  echo "--shell needs a non-empty command string" >&2
  exit 2
fi
if [ "$mode" = "cmd" ] && [ $# -eq 0 ]; then
  echo "-- needs at least one command" >&2
  exit 2
fi

mkdir -p "$(dirname -- "$out")"
stdout_tmp="$(mktemp)"
stderr_tmp="$(mktemp)"
cleanup() { rm -f -- "$stdout_tmp" "$stderr_tmp"; }
trap cleanup EXIT

cwd="$(pwd)"
started_at="$(date -Is)"

if [ "$mode" = "shell" ]; then
  command_repr="bash -o pipefail -c $(printf '%q' "$shell_cmd")"
  bash -o pipefail -c "$shell_cmd" >"$stdout_tmp" 2>"$stderr_tmp"
  rc=$?
else
  command_repr="$(printf '%q ' "$@")"
  command_repr="${command_repr% }"
  "$@" >"$stdout_tmp" 2>"$stderr_tmp"
  rc=$?
fi

finished_at="$(date -Is)"
stdout_sha256="$(sha256sum "$stdout_tmp" | cut -d' ' -f1)"
stderr_sha256="$(sha256sum "$stderr_tmp" | cut -d' ' -f1)"

{
  echo "command=$command_repr"
  echo "label=$label"
  echo "cwd=$cwd"
  echo "started_at=$started_at"
  echo "finished_at=$finished_at"
  echo "rc=$rc"
  echo "stdout_sha256=$stdout_sha256"
  echo "stderr_sha256=$stderr_sha256"
  echo "--- stdout ---"
  sed -e '$a\' "$stdout_tmp"
  echo "--- stderr ---"
  sed -e '$a\' "$stderr_tmp"
} >"$out"

exit "$rc"
