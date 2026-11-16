# Packet B — R02/R03 evidence summary

- run: `openrig-p0-hard-constraints-20261116` / round 1
- step: `impl_baseline_evidence` (TDO-OC)
- objective: TASK §3 — `.run-meta.json`, `wf.py baseline`/`verify-baseline` with run-dir exclusion, `evidence_run.sh` with real rc/pipefail, negative tests.
- result: **done** — targeted pytest `11 passed`, full pytest `236 passed`; drift detection proven on a real run and in tests.

## Changed files

See `changed-files.txt`. New: `scripts/evidence_run.sh`, `tests/test_wf_baseline.py`, `tests/test_evidence_run.py`.
Modified: `scripts/wf.py` (new-run writes `.run-meta.json`; `baseline` / `verify-baseline` subcommands).
Baseline artifacts: `reports/evidence/00-baseline.json`, `00-baseline.txt`; the launcher's original
capture is preserved at `impl_baseline_evidence/00-baseline.startup.txt`.

## Commands and real rc

| command | rc | file |
| --- | --- | --- |
| `.venv/bin/python -m pytest tests/test_wf_baseline.py tests/test_evidence_run.py -q` | 0 (11 passed) | `targeted-pytest.txt` |
| `.venv/bin/python -m pytest tests -q` | 0 (236 passed) | `full-pytest-smoke.txt` |
| `wf.py baseline <run> --project-root <KB>` | 0 | `baseline.txt` |
| `wf.py verify-baseline <run>` (immediately after capture) | 0, `ok:true` | `verify-baseline.txt` |
| append 1 comment line to `scripts/wf.py`, then verify | 1, mismatch `diffSha256` | `verify-drift-detected.txt` |
| restore file byte-identical, verify | 0, `ok:true` | `verify-restored.txt` |
| `evidence_run.sh --shell 'printf x; exit 7'` | 7, file has `rc=7` | `evidence-run-exit7.txt` |
| `evidence_run.sh --shell 'false | tail'` | 1 (pipefail), hash fields present | `evidence-run-pipefail.txt` |
| `wf.py verify-baseline` after full pytest | 0 (pytest artifacts excluded) | `verify-after-full-pytest.txt` |

## Exclusion proof

- `excludePaths = ["workflow-group/runs/openrig-p0-hard-constraints-20261116"]`.
- `git status --porcelain -uall` is used so git cannot collapse the run dir into an untracked
  ancestor (`?? workflow-group/`), which would defeat the exclusion. This was caught by
  `tests/test_wf_baseline.py::test_legacy_run_accepts_explicit_project_root` before the fix.
- Adding files inside the run dir keeps `verify-baseline` rc=0
  (`tests/test_wf_baseline.py::test_new_file_inside_run_dir_does_not_break_baseline`).

## Negative cases (TASK R08)

- `test_wf_baseline.py::test_verify_detects_modified_file` → rc=1 + `statusAdded`
- `test_wf_baseline.py::test_new_file_inside_run_dir_does_not_break_baseline` → rc=0（排除生效）
- `test_wf_baseline.py::test_missing_project_root_dies`
- `test_evidence_run.py::test_shell_exit_code_is_preserved` → rc=7
- `test_evidence_run.py::test_pipefail_makes_pipeline_fail` → rc=1
- `test_evidence_run.py::test_stderr_is_not_swallowed`
- `test_evidence_run.py::test_missing_out_is_usage_error`

## Note for MAIN/QA — baseline semantics vs PROJECT §5.2

PROJECT §5.2 expects `verify-baseline` rc=1 after implementation "because scripts/tests were
modified". That is only true if the baseline was captured **before** those edits. `baseline`
captures a point-in-time snapshot, so the first capture here happened after Packets A/B were
written; verify immediately after capture is therefore rc=0 (correct: no drift), and the rc=1
case is demonstrated by the real drift run above plus tests. If QA re-runs `baseline` at close,
it resets the snapshot and verify becomes 0 by construction — compare the diff only when verify
returns 1, or capture baseline before further implementation. No check was weakened.

## Product repo

HEAD `e932ae94…`, status `3b64cf90…`, diff `dc564a37…`, 29 dirty — unchanged (`scope.txt`).
