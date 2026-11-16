# SETUP — Workflow Group Personal Use

From a fresh clone to a passing test run, then to your first workflow run.

## 1. Requirements

| Tool | Version used for this snapshot | Notes |
| --- | --- | --- |
| Python | 3.12+ (3.14.4 on the build machine) | runtime scripts, gates and tests |
| `venv` / `pip` | stdlib | `python3 -m venv` is enough |
| pytest | `>=8,<10` | dev dependency (`requirements-dev.txt`) |
| openpyxl | `>=3.1,<4` | `scripts/issues.py` reads/writes `ISSUES.xlsx` |
| PyYAML | `>=6,<7` | `tests/test_workflow_rework.py` imports `yaml` at module level |
| bash | any POSIX bash | runtime scripts |
| Node.js | 22 or 24 | only if pairing with OpenRig Personal Local |

Everything the suite imports at module level is declared in
`requirements-dev.txt`; `runtime/bootstrap.sh` installs exactly that list, so a
clean clone needs nothing pre-warmed. If you see `ModuleNotFoundError` during
collection, the declaration list is incomplete — fix `requirements-dev.txt`
rather than installing into your own environment, otherwise a red suite can look
green on your machine only.

Optional partners: `uv` (faster venv), `opencode`, `dsh`, `tmux`, `psutil`
(best-effort memory reading in `wf.py`; the call site degrades to `None`).

## 2. Bootstrap

```bash
bash runtime/bootstrap.sh
```

It creates `.venv/`, installs `requirements-dev.txt`, runs
`python3 scripts/doc_consistency.py --check`, then `pytest -q`, and stops at the
first failure.

Manual equivalent:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python scripts/doc_consistency.py --check
pytest -q
```

## 3. Preflight and daily commands

```bash
source .venv/bin/activate

python3 scripts/openrig_preflight.py --json      # preflight before an OpenRig run
./scripts/test.sh                                # full test suite (falls back to system pytest)
python3 scripts/doc_consistency.py --check       # templates/indexes/references consistency
python3 scripts/wf.py doctor --run <run-id>      # run health
python3 scripts/wf_close_lint.py --run <run-id>  # close-semantics gate
python3 scripts/evidence_run.sh -- <cmd...>      # capture command output as evidence
```

## 4. Starting a run

```bash
source .venv/bin/activate
python3 scripts/wf.py new-run my-run-20261116 --goal "one-line goal" --tdo 2
python3 scripts/wf.py brief --role pmo --run my-run-20261116
```

`new-run` copies the four documents from `templates/` into `runs/<run-id>/` and
creates the lock directory. Paste the printed brief into your PMO seat — or, if
you are running the roles yourself, work through it in one terminal. Then follow
`WORKFLOW.md`.

Specialized templates (for example `templates/specialized/h-drive-cleanup`) add
gates and an independent safety reviewer; pass `--template` to use one.

## 5. Environment variables

| Variable | Purpose |
| --- | --- |
| `OPENRIG_HOME` | OpenRig runtime state root, when paired with OpenRig |
| `OPENRIG_DAEMON_DIST` | Path to a built OpenRig daemon `dist`, for render/archive gates |
| `OPENRIG_MASTER` / `OPENRIG_RENDER_MASTER` | Master run used when rendering a specialization |
| `OPENRIG_BRIDGE_DOCTOR` | Enable the OpenRig bridge doctor during preflight |
| `OPENRIG_TEARDOWN_GUARD` | Guard script used by the archive gate |
| `OPENCODE_BIN` | `opencode` binary when not on `PATH` |
| `PYTHONPATH` | Extra module roots; `scripts/test.sh` uses it to reach system pytest offline |

No provider keys are configured here. Each agent CLI authenticates itself. Never
put keys in this tree: `.env*` is git-ignored and scanned before publication.

## 6. Pairing with OpenRig

1. Clone and build **OpenRig Personal Local** (`runtime/install.sh`).
2. `rig daemon start`, then have the operator assemble a team.
3. Either render this run into an OpenRig workflow instance, or drive it from the
   operator seat while these four documents stay authoritative.

The method plane owns *what a round means*; the execution plane owns *who is
sitting where*.

## 7. Troubleshooting

| Symptom | Check |
| --- | --- |
| `ModuleNotFoundError: openpyxl` | venv not activated, or `requirements-dev.txt` not installed |
| `缺少 .../.venv/bin/python` (from `scripts/test.sh`) | run `bash runtime/bootstrap.sh` |
| `wf.py delegate` fails | the v1 HTTP channel only supports opencode 1.x; use `wf.py brief` with current `opencode` |
| Close gate refuses | `wf_close_lint.py --run <run-id>` prints the unmet closure conditions |
| `doc_consistency --check` fails | read its diff output before editing templates or indexes |
