# Packet C — R01/R04/R07 evidence summary

- run: `openrig-p0-hard-constraints-20261116` / round 1
- step: `impl_close_archive_render` (TDO-OC)
- objective: TASK §4 — `archive-gate` (dry-run guard), `wf_close_lint --strict` + `evidence-record` revision channel, `verify_render.py`, negative tests.
- result: **done** — targeted pytest `37 passed`, full pytest `259 passed`; each gate has an explicit negative case.

## Changed files

See `changed-files.txt`. New: `scripts/verify_render.py`, `tests/test_archive_gate.py`,
`tests/test_verify_render.py`, `tests/test_evidence_record.py`. Modified: `scripts/wf.py`
(`archive-gate`, `evidence-record`), `scripts/wf_close_lint.py` (`--strict`), `tests/test_wf_close_lint.py`.
`wf_close_lint.py` / `test_wf_close_lint.py` were pre-existing **untracked** files, so their
"before" hash is reported as `n/a` rather than invented.

## Commands and real rc

| command | rc | file |
| --- | --- | --- |
| targeted pytest (4 files) | 0 (37 passed) | `targeted-pytest.txt` |
| `.venv/bin/python -m pytest tests -q` | 0 (259 passed) | `full-pytest-smoke.txt` |
| `verify_render.py --run-dir runs/<run> --json` (live) | 0, `ok:false` (WARN, real drift) | `verify-render-live.txt` |
| `wf.py archive-gate <run> --json` (live, real guard) | 2, `ok:false`, guard rc=1 "manifest not found" | `archive-gate-live.txt` |
| `wf_close_lint.py --run <run> --strict --json` (live) | 1, `final_missing` + `closeout_missing` (close_round owns them) | `close-lint-strict-live.txt` |
| `verify_render.py` on copied+mutated run (default) | 0, `ok:false` | `verify-render-mutated-warn.txt` |
| `verify_render.py --strict` on mutated run | 1 | `verify-render-mutated-strict.txt` |
| `verify_render.py` with manifest removed | 2 | `verify-render-no-manifest.txt` |
| fake guard PARTIAL | 2, `ok:false`, `archiveStatus=PARTIAL`, `missing=[transcriptCapture]` | `archive-gate-partial.txt` |
| fake guard manifest-not-found (guard rc=1) | 2, `ok:false`, error passed through | `archive-gate-guard-rc1.txt` |
| guard file missing | 3, `ok:false`, "guard missing" | `archive-gate-missing.txt` |
| strict lint on run without FINAL/closeout | 1, both strict codes | `close-lint-strict-temp.txt` |
| `wf.py verify-baseline` after Packet C | 1, `statusAdded` = the 4 new Packet C files | `verify-baseline-after-packet-c.txt` |

## Observations (not caused by this packet)

- **Live render drift**: `verify-render-live.txt` reports `ok:false` for `rig.yaml`, `workflow.yaml`,
  `guidance/team.md`, `OPENRIG-BRIDGE.json` — these files changed after `renderedAt` (runtime/bridge
  writes). This is exactly the R07 WARN signal; default rc=0, `--strict` would be rc=1. Not repaired
  here (re-rendering is outside this packet and would overwrite runtime state).
- **Live archive gate**: no archive manifest for this run under the product guard's default archive
  root, so the gate correctly fails closed (rc=2) instead of pretending COMPLETE.
- **Live strict close**: `FINAL.md`/`closeout.json` are `close_round` deliverables; strict lint is
  expected to fail until MAIN records them through `wf.py evidence-record`.

## Negative cases (TASK R08)

- `test_archive_gate.py`: partial, guard rc=1, missing guard, and "guard never called with --execute".
- `test_wf_close_lint.py` (StrictCloseTests): missing FINAL, missing closeout, sha mismatch,
  revision chain broken, revision=0, FINAL after closedAt without REV, valid manifest PASS.
- `test_verify_render.py`: one-byte change default WARN / strict rc=1, missing file, missing manifest
  rc=2, bad JSON rc=2.
- `test_evidence_record.py`: bytes/sha computation, revision 2 keeps `replacesSha256`, revision must
  increase, missing file dies, produced closeout passes strict lint.

## Product repo

HEAD `e932ae94…`, status `3b64cf90…`, diff `dc564a37…`, 29 dirty — unchanged (`scope.txt`).
No teardown executed; archive-gate is dry-run only.
