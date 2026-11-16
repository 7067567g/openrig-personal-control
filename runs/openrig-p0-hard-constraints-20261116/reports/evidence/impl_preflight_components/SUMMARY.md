# Packet A — R05/R06 evidence summary

- run: `openrig-p0-hard-constraints-20261116` / round 1
- step: `impl_preflight_components` (TDO-OC)
- objective: TASK §2 — `required_components.py`, real preflight checks, `issues.py` import guard, `wf.py doctor` component check, negative tests.
- result: **done** — targeted pytest `86 passed`, full pytest `225 passed`, preflight fail-closed verified.

## Changed files

See `changed-files.txt` (path | action | before/after sha256). New: `scripts/required_components.py`,
`tests/test_required_components.py`, `tests/test_openrig_preflight.py`. Modified: `scripts/openrig_preflight.py`,
`scripts/issues.py`, `scripts/wf.py`, `tests/test_issues.py`, `tests/test_wf.py`.

## Commands and real rc

| command | rc | file |
| --- | --- | --- |
| `.venv/bin/python -m pytest tests/test_required_components.py tests/test_openrig_preflight.py tests/test_issues.py tests/test_wf.py -q` | 0 (86 passed) | `targeted-pytest.txt` |
| `.venv/bin/python -m pytest tests -q` | 0 (225 passed) | `full-pytest-smoke.txt` |
| `openrig_preflight.py --json` (no workspace/run-id) | 1, `ok:false` | `negative-no-context.txt` |
| `openrig_preflight.py --json --advisory` | 0, `ok:false` | `negative-advisory.txt` |
| `required_components.py --root /tmp/empty-wg-root --json` | 1, 8 required fail | `negative-required-components.txt` |
| `openrig_preflight.py --json --run-id ... --workspace <KB> --run-dir runs/...` | 0, `ok:true`, all 5 checks ok | `positive-injected.txt` |
| `.venv/bin/python scripts/wf.py doctor openrig-p0-hard-constraints-20261116 --json` | 0, `required-components: 13 个组件满足 required` | `doctor.txt` |

## Negative cases (pytest, TASK R08)

- `tests/test_required_components.py::test_missing_templates_make_required_components_fail`
- `tests/test_required_components.py::test_missing_openpyxl_detail_and_install_hint`
- `tests/test_openrig_preflight.py::test_no_context_fails_closed`
- `tests/test_openrig_preflight.py::test_advisory_keeps_rc0_but_not_ok`
- `tests/test_openrig_preflight.py::test_workspace_without_managed_block_fails`
- `tests/test_openrig_preflight.py::test_missing_run_docs_fails`
- `tests/test_issues.py::test_import_without_openpyxl_does_not_crash_and_reads_jsonl`
- `tests/test_wf.py::test_doctor_reports_required_components_error_not_none_type`
- `tests/test_wf.py::test_doctor_issues_error_is_explicit_when_openpyxl_missing_no_mirror`

## Authorized out-of-whitelist write

Only `AGENTS.md` at KB root, written by `openrig_preflight.py` managed-block injection (TASK §5):
before `629742bf…`, after `53eed071…` (`agents.md.sha256.before/after`).
Dashboard `target.json` also re-written by the script's existing monitor registration:
before `62ee9d57…`, after `2944b57d…` (`dashboard-target.sha256.before/after`).

## Product repo (must equal plan baseline)

HEAD `e932ae94…`, status sha256 `3b64cf90…`, diff sha256 `dc564a37…`, 29 dirty — unchanged (`scope.txt`).

## Notes

- `--advisory` never fakes `ok:true`; it only keeps rc=0.
- `verify-baseline` / close / render (Packets B/C) intentionally untouched.
- No commit/push; no other run/template/product writes.
