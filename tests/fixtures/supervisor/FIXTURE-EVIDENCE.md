# build_fixtures evidence (TDO) — round 2 (fixes qa_fixtures B1)

Captured: 2026-11-16T05:33:52Z
Owner: `exec-tdo-oc@openrig-s7-harness-redteam-20261116`
Step: `build_fixtures` (workflow `openrig-workflow-openrig-s7-harness-redteam-20261116@1`)
Addresses: `tests/redteam/VERDICTS/qa-fixtures-round-1.md` blocker **B1** + W1–W5.

Non-authoritative handoff evidence. Authoritative contract:
`runs/openrig-s7-harness-redteam-20261116/reports/00-plan.md` §4/§6.

## Environment (D-S7-03)

* `.venv/bin/python` = Python 3.12.15, pytest 9.0.2
* `python3` = Python 3.14.4 (no openpyxl)
* no daemon/rig/seat/workflow/model started or mutated; no network/subprocess
  from fixtures (F-09 ban active and negative-tested)

## Acceptance results (exact §6 commands)

```text
cd <WORKFLOW_GROUP>

.venv/bin/python -m pytest tests/fixtures/supervisor -q   -> 149 passed, rc=0
.venv/bin/python -m pytest tests/fixtures/fake-rig   -q   ->  39 passed, rc=0
python3         -m pytest tests/fixtures/supervisor -q   -> 149 passed, rc=0
python3         -m pytest tests/fixtures/fake-rig   -q   ->  39 passed, rc=0

.venv/bin/python -m pytest tests -q                       -> 517 passed, rc=0
   baseline 329; delta +188; 0 skipped / 0 xfailed in the fixture suites

PYTHONHASHSEED=1/2/7 ... -q -p no:cacheprovider           -> 188 passed each, rc=0
PATH=/nonexistent .venv/bin/python -m pytest tests/fixtures/supervisor tests/fixtures/fake-rig -q
                                                          -> 188 passed, rc=0
```

F-08 still recounts the S6 tree: **68/68 parsed**, `unresolved=0`, `ok=true`.

## B1 fix — every named guard is load-bearing (RT-30 = 14/14)

Reproduced QA's mutation procedure on a throwaway copy (append
`def guard_x(*a, **k): return True` to `supervisor_sim.py`, rerun the suite).
Baseline copy: 148 passed + 1 skipped (S6 tree absent in the copy).
Result: **14/14 guards flip the suite to rc≠0** — 0 misses.

```text
guard_archive_complete     2 failed   guard_launch_ttl         4 failed
guard_bridge_sha           2 failed   guard_no_legacy_run      1 failed
guard_continuity_allow     1 failed   guard_node_identity      1 failed
guard_daemon_identity      2 failed   guard_port_collision     1 failed
guard_fresh_authorized     1 failed   guard_rig_absent         1 failed
guard_home_match           1 failed   guard_seat_outcome_match 3 failed
guard_verb_unconsumed      2 failed   guard_workflow_absent    1 failed
```

Fixes:

1. `guard_seat_outcome_match` is now the decision gate for per-seat resume
   outcomes (`expected_outcome_map` + `_call_guard`); `verify_outcomes` only
   supplies the detailed code. A mismatch test fails if the guard is bypassed.
2. `guard_node_identity` now runs **before** `continuity_allow` in `resume`,
   so its false branch (not the plan block) rejects with `continuity_mismatch`.
   The previous blocked-reason remap was removed.
3. `guard_fresh_authorized` has a fixture-level negative using a crafted
   `ContinuityPlan(decisionStatus="allow", fresh-primed/freshAuthorized=False)`;
   the test fails when the guard is replaced by `return True`.
4. `COMMAND_GUARDS` is now a live coverage map (W1) consumed by
   `test_command_guards_is_a_live_coverage_map`: every listed guard exists and
   every named guard is listed.

## Other verdict items

| Item | Disposition |
| --- | --- |
| W2 blocked resume wrote plan/launch files | Fixed: launch record and `continuity-plan.json` are written only **after** the allow decision (still before live mutation). A blocked resume writes no files. Negative test asserts both paths absent. |
| W3 `make_context` used global `/tmp` | Fixed: `tmp_root` defaults to the run directory's parent and is passed to both `assert_fixture_home` calls. |
| W4 test wrote outside `tmp_path` | Fixed: the outside-base artifact is created under the test's own `tmp_path`. |
| W5 no `unknown_option` / claim-window surface | Added real seams: `fake_rig.check_launch_options` (verb/option allow-list; rejects `start --resume`, `--skip-validate`, `--skip-archive`, `resume --force`) and `freeze.detect_claim_window_escape` (hash decides; mtime rollback does not clear it; mtime-only drift is recorded separately). Both have positive controls. |
| W6 plan §6.1 command 6 wording | Not a fixture defect; left to `main_verify` (use count/sha comparison, not "empty"). |

## Scope / zero-delta

* Written paths: only `tests/fixtures/fake-rig/**` and
  `tests/fixtures/supervisor/**`.
* No `tests/fixtures/conftest.py`; `tests/redteam/**` not written by TDO
  (QA's verdict file accounts for that untracked path).
* Product repo: **34 dirty, HEAD e932ae9, unchanged**.
* KB `git status` outside `tests/fixtures/` and `tests/redteam/`: **275 lines,
  the plan baseline** (total is 277 = 275 + one untracked fixture line + one
  untracked redteam line).

## Honest gaps

* `tests/redteam/**` remains QA's step (RT-01..RT-30 cases and the verdict).
* `handoff_gate.py` product gaps W7–W11 are modelled semantically, not patched.
* Live E2E remains out of scope for S7.
