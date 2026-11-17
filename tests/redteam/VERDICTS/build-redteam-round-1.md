# Build red-team verdict — round 1

- Packet: `qitem-20261116053641-d487a9d5`
- Workflow instance: `01M7HC05T9RMCJ00X6ZCE68BSF`
- Author: `assurance-qa@openrig-s7-harness-redteam-20261116`
- Step: `build_redteam` (QA)
- Verdict: **PASS-WITH-WARN** (all RT-01..RT-30 present; 14/14 mutation coverage; no blocker)
- Next: `main_verify` (MAIN)
- Write scope used: `tests/redteam/**` only. Fixtures and product code were read-only.

Captured: `2026-11-16T05:42:27Z`.

---

## 1. Environment

| Fact | Value |
| --- | --- |
| canonical interpreter | `.venv/bin/python` = Python **3.12.15**, pytest **9.0.2** |
| system interpreter | `python3` = Python **3.14.4** |
| KB tracked diff | sha256 prefix **1b48354a79122e55** (plan baseline, unchanged) |
| product repo | HEAD **e932ae9**, dirty **34**, diffSha **697800868bcbf83d** (plan baseline, unchanged) |
| live mutation | none: no daemon/rig/seat/workflow/model started; every test runs under the F-09 external-IO ban |

---

## 2. Commands and real counts

```text
cd <WORKFLOW_GROUP>
.venv/bin/python -m pytest tests/redteam -q                         -> 106 passed, rc=0
python3         -m pytest tests/redteam -q                         -> 106 passed, rc=0
.venv/bin/python -m pytest tests/redteam -q -rsx                   -> 106 passed, 0 skipped, 0 xfailed
.venv/bin/python -m pytest tests -q                                -> 623 passed, rc=0
.venv/bin/python -m pytest tests -q -rsx                           -> 623 passed, 0 skipped, 0 xfailed
.venv/bin/python -m pytest tests --ignore=tests/fixtures --ignore=tests/redteam -q
                                                                    -> 329 passed, rc=0  (baseline)
PATH=/nonexistent .venv/bin/python -m pytest tests/redteam -q -p no:cacheprovider
                                                                    -> 106 passed, rc=0
PYTHONHASHSEED=1/2/7 .venv/bin/python -m pytest tests/redteam -q -p no:cacheprovider
                                                                    -> 106 passed each, rc=0
```

Tree acceptance commands (N-REDTEAM-01), run from the KB root exactly as specified:

```text
workflow-group/.venv/bin/python -m pytest workflow-group/tests/redteam -q -k guard       -> 28 passed, rc=0
workflow-group/.venv/bin/python -m pytest workflow-group/tests/redteam -q -k activity    -> 18 passed, rc=0
workflow-group/.venv/bin/python -m pytest workflow-group/tests/redteam -q -k stale_wake  ->  8 passed, rc=0
```

Counts add up: **623 = 329 baseline + 188 fixtures + 106 red-team**. No hidden skip/xfail.

---

## 3. RT coverage (RT-01..RT-30)

| RT | File / test family | Negative | Paired control |
| --- | --- | --- | --- |
| 01 | `test_guard_bypass.py` | S1 managed run: `lifecycle_not_authorized`, rc=2, audit deny | S2 legacy home warns (not deny); unmanaged allowed |
| 02 | same | `--allow-direct` after subcommand / after `--` is **not** stripped | before-subcommand is stripped + audited; plain `rig up` has no record |
| 03 | same | `start --resume` -> `unknown_option`, rc=2 | plain `start` accepted |
| 04 | same | `--skip-validate`, `--skip-archive`, `resume --force` -> `unknown_option` | normal `resume --fresh --reason` accepted; unknown verb distinct |
| 05 | `test_fresh_as_resume.py` | no token -> `continuity_blocked`, rc=2, zero mutation, no plan/launch files | valid token -> `resumed` |
| 06 | same | expected resume, actual fresh -> `continuity_mismatch`, rc=2, partial, `FAILED` | matching actual -> ok |
| 07 | same | fresh outside authorized set -> `fresh_not_authorized`, rc=2, partial; planner blocks unknown/empty-reason seat | authorized fresh + reason -> ok |
| 08 | same | healthy observation + unknown token -> `needs-human`, `awaiting-decision` (not resumed) | real token -> `resume-original` |
| 09 | `test_provenance.py` | stale start launch; resume TTL is 20 min (21 min -> `stale_launch`) | fresh start launch; 19 min resume accepted |
| 10 | same | consumed start verb; second resume -> `launch_verb_consumed`, no extra runner call | unconsumed start; first resume accepted |
| 11 | same | forged `OPENRIG_ENTRY_LAUNCH_ID` is overridden + audited, never accepted | legitimate launch has no override audit |
| 12 | same | closed launch is not reused; a new launch id is minted | fresh launch is active and consumed |
| 13 | `test_rt_archive.py` | `PARTIAL` archive -> `archive_incomplete`, rc=2, no `down` | `COMPLETE` -> `down`, state `STOPPED`, home sentinel kept |
| 14 | same | claimed DSH session missing from inventory / inflated applicability / required DSH -> `ArchiveTamper` | genuine n/a -> `COMPLETE`, `dsh=False`, non-empty reason |
| 15 | same | `COMPLETE` with a missing required item -> `status_required_mismatch`; `require_complete` raises | all required items true -> `COMPLETE` |
| 16 | `test_stale_wake.py` | activity changed at delivery -> `stale_at_delivery`, not delivered | same activity -> `delivered` |
| 17 | same | old episode -> `stale_episode` | current episode -> `delivered` |
| 18 | same | live `unknown` -> `deferred/activity_unknown`; `judge_stall` health `unknown` (not healthy) | `working` -> delivered; health `healthy` |
| 19 | `test_activity.py` | hook missing + ps working -> `working` + `degraded(hook_missing)`, not unknown | all sources -> `oracle` |
| 20 | same | no addressable source -> `None` + `degraded(no_observation_path)` | addressable source has a value |
| 21 | same | ps available, no session -> `absent`, `activity=None`, not degraded | present session -> `present` |
| 22 | same | true `oracle_unknown` -> `unknown`, `oracle`, reasons exclude `oracle_unknown` | known activity -> `working` |
| 23 | same | long tool call (high queue age + working) -> not stall; high age + no activity -> `unknown`, not healthy | idle over threshold -> stall; idle within -> healthy |
| 24 | `test_handoff_stale.py` | post-freeze write -> `StaleReview`; mtime rollback does not help; missing artifact stale | frozen copy accepted |
| 25 | same | hash-only bundle -> `compliant=False, reason="hash_only"`; failed selfDiff/gate/delta -> named reasons | full bundle -> compliant |
| 26 | same | `mode=initial` without authorized outputs -> `initial_missing_authorized_outputs`; artifact outside base -> `FreezeError` | initial with authorized outputs -> compliant |
| 27 | `test_claim_window.py` | rewrite after close + mtime rollback -> `claim_window_escape`; missing artifact -> escape | clean snapshot -> ok; mtime-only drift recorded, not an escape; hash snapshot also detects |
| 28 | `test_fixture_escape.py` | real `$OPENRIG_HOME` / `openrig.sqlite` / outside tmp root -> `FixtureEscape`; in-suite subprocess/socket -> `ExternalIOForbidden` | plain `tmp_path` runs the script; nested ban restores the outer ban |
| 29 | `test_mutation_controls.py` | in-suite proof that process/network IO is forbidden | pure `guard_launch_ttl` control; external `PATH=/nonexistent` run is in §2 |
| 30 | same | each named guard: baseline negative fails, then `return True` bypass changes it | 14/14 table; coverage test prints the GUARD↔RT map |

Every RT family has at least one failing negative and a passing control. Sim-level negatives assert `rc` + `code`; pure-function negatives assert the typed status/violation; "zero mutation" is asserted where a supervisor/sim is involved.

---

## 4. RT-30 mutation table (printed by the suite)

```text
GUARD <-> RT mutation coverage
  guard_archive_complete         -> RT-13/RT-14/RT-15
  guard_bridge_sha               -> RT-01
  guard_continuity_allow         -> RT-05
  guard_daemon_identity          -> RT-09/RT-12
  guard_fresh_authorized         -> RT-07
  guard_home_match               -> RT-01
  guard_launch_ttl               -> RT-09
  guard_no_legacy_run            -> RT-01
  guard_node_identity            -> RT-08
  guard_port_collision           -> RT-12
  guard_rig_absent               -> RT-01
  guard_seat_outcome_match       -> RT-06/RT-07
  guard_verb_unconsumed          -> RT-10
  guard_workflow_absent          -> RT-01
  coverage: 14/14 = 100%
```

The parameterized test creates a fresh context for the baseline and for the
bypassed run, so a stale launch/consumed verb from the baseline cannot mask the
bypass. `guard_node_identity`'s bypass falls through to `continuity_blocked`
(still a refusal), which is why that one case asserts "the specific negative
code changed" rather than "ok is True".

---

## 5. Deviations and WARNs (non-blocking)

1. **File rename to avoid a pytest basename collision.** The plan's layout names
   `tests/redteam/test_archive.py`, but `tests/fixtures/supervisor/test_archive.py`
   has the same basename. With no `__init__.py` and default `prepend` import mode,
   `pytest tests` fails collection with an import-file mismatch. I renamed the
   red-team file to `tests/redteam/test_rt_archive.py`. `-k guard/activity/
   stale_wake` and all RT names are unaffected.
2. **RT-03/04 are parser-level.** `fake_rig.check_launch_options` is a real
   allow-list parser (not a scripted rc=2), and the tests assert its
   `unknown_option`/`unknown_verb` results. The fixture has no generic CLI
   dispatcher, so there is no `SupervisorSim` call to make for an unknown option;
   "zero mutation" is structural (the parser is pure). Mutating the parser to
   always-ok makes 4 of these tests fail (verified in the fixture round).
3. **RT-12 is P1 and modeled as no-reuse.** The fixture guarantees a closed
   launch is never reused (new `launchId`, `start` consumed) rather than exposing
   a dedicated "daemon restart" verb. The security property (old launch cannot
   authorize a restart) is tested; a literal refusal code is not modeled. Named
   P1 residual for S8.
4. **RT-29 is acceptance-level plus an in-suite offline proof.** Re-running pytest
   from inside a test would require `subprocess`, which the F-09 ban forbids. The
   in-suite test asserts the ban is active; the real `PATH=/nonexistent` run is
   recorded in §2.
5. **RT-07 has a pre/post split.** The planner reports `fresh_not_authorized` for
   an unknown/empty-reason seat with `decisionStatus="blocked"`; the supervisor
   aggregates pre-mutation plan blocks to `continuity_blocked`. The
   `fresh_not_authorized` supervisor code is asserted on the post-mutation
   outcome path (a seat outside the authorized set actually came up fresh), which
   is the path that writes partial evidence (`RT-07` "写 partial").
6. **W6 from the fixture verdict remains for `main_verify`:** 00-plan §6.1
   command 6 cannot be "empty" because the KB has 275 pre-existing dirty entries;
   use the count/sha comparison (total 277 = 275 baseline + fixtures + redteam;
   tracked `git diff` unchanged).

---

## 6. Scope / zero-delta

- Written paths: only `tests/redteam/**` (10 test modules, `conftest.py`,
  `helpers.py`, this verdict, and the two prior fixture verdicts).
- `tests/fixtures/**` untouched (evidence sha256 still `27ed0ace…`).
- Product repo: 34 dirty, HEAD `e932ae9`, diffSha `697800868bcbf83d` — unchanged.
- KB tracked diff: `1b48354a79122e55` — unchanged; `git status` total 277 = 275
  baseline + `tests/fixtures/` + `tests/redteam/`.
- No live E2E; S8 has not started; no product guard/supervisor code was written.

---

## 7. Verdict

**PASS-WITH-WARN.** The red-team matrix is executable, offline, deterministic,
and has a real failing negative plus a control for every RT family. The RT-30
mutation control covers all 14 named guards at 100%. The residual items are
scope/modeling warnings for `main_verify` and S8, not blockers for the next step.
