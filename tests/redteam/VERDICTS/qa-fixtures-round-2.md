# QA verdict — `qa_fixtures` round 2

- Packet: `qitem-20261116053416-16fa38d1`
- Workflow instance: `01M7HC05T9RMCJ00X6ZCE68BSF`
- Reviewer: `assurance-qa@openrig-s7-harness-redteam-20261116`
- Reviewed step: `build_fixtures` round 2 (owner `exec-tdo-oc`)
- Verdict: **PASS-WITH-WARN** (round-1 blocker B1 is closed; no fixture blocker)
- Next step: `build_redteam` (QA)
- Write scope used: this file only (`tests/redteam/VERDICTS/qa-fixtures-round-2.md`). Fixtures were read-only.

Captured: `2026-11-16T05:36:26Z`.

---

## 1. Environment (measured)

| Fact | Value |
| --- | --- |
| canonical interpreter | `.venv/bin/python` = Python **3.12.15**, pytest **9.0.2** |
| system interpreter | `python3` = Python **3.14.4** (no openpyxl) |
| KB tracked diff | sha256 prefix **1b48354a79122e55** (plan baseline, unchanged) |
| product repo | HEAD **e932ae9**, dirty **34**, statusSha **011f382fba6cdc4f**, diffSha **697800868bcbf83d** (plan baseline, unchanged) |
| S6 tree | sha256 prefix **e01443e5**; 68/68 parsed, unresolved=0, ok=true |
| live mutation | none: no daemon/rig/seat/workflow/model started; all tests under the F-09 external-IO ban |

---

## 2. Independent re-run (not TDO's numbers)

```text
cd <WORKFLOW_GROUP>
.venv/bin/python -m pytest tests/fixtures/supervisor -q      -> 149 passed, rc=0
.venv/bin/python -m pytest tests/fixtures/fake-rig   -q      ->  39 passed, rc=0
python3         -m pytest tests/fixtures/supervisor -q      -> 149 passed, rc=0
python3         -m pytest tests/fixtures/fake-rig   -q      ->  39 passed, rc=0
.venv/bin/python -m pytest tests -q                          -> 517 passed, rc=0
.venv/bin/python -m pytest tests --ignore=tests/fixtures -q  -> 329 passed, rc=0
.venv/bin/python -m pytest tests/fixtures/supervisor tests/fixtures/fake-rig -q -rsx
                                                              -> 188 passed, rc=0, 0 skipped, 0 xfailed
PYTHONHASHSEED=1/2/7 ... -q -p no:cacheprovider              -> 188 passed each, rc=0
PATH=/nonexistent ... -q -p no:cacheprovider                 -> 188 passed, rc=0
```

- 188 = 149 + 39; 517 − 188 = 329 baseline; the +188 delta is real.
- No hidden `skip`/`xfail` in the fixture suites. The only `pytest.skip` remains the allowed S6-tree-missing guard; the tree is present here, so the 68/68 test ran.
- `--collect-only` reports 188; no duplicate test names.

---

## 3. Round-1 blocker B1 is closed: RT-30 = 14/14

Reproduced QA's own mutation procedure on a throwaway `/tmp` copy (append `def guard_x(*a, **k): return True` to `supervisor_sim.py`; copy baseline is 148 passed + 1 skipped because the S6 tree is absent from the copy). Every named guard now flips the suite to rc≠0:

| guard | copy result | guard | copy result |
| --- | --- | --- | --- |
| `guard_archive_complete` | 2 failed, 146 passed | `guard_launch_ttl` | 4 failed, 144 passed |
| `guard_bridge_sha` | 2 failed, 146 passed | `guard_no_legacy_run` | 1 failed, 147 passed |
| `guard_continuity_allow` | 1 failed, 147 passed | `guard_node_identity` | 1 failed, 147 passed |
| `guard_daemon_identity` | 2 failed, 146 passed | `guard_port_collision` | 1 failed, 147 passed |
| `guard_fresh_authorized` | 1 failed, 147 passed | `guard_rig_absent` | 1 failed, 147 passed |
| `guard_home_match` | 1 failed, 147 passed | `guard_seat_outcome_match` | 3 failed, 145 passed |
| `guard_verb_unconsumed` | 2 failed, 146 passed | `guard_workflow_absent` | 1 failed, 147 passed |

**14/14, 0 misses.** The three round-1 misses are now real:

- `guard_seat_outcome_match` is the decision gate for per-seat resume outcomes (`continuity.expected_outcome_map` + `_call_guard`; `verify_outcomes` only supplies the detailed code). Bypassing it lets a `fresh-primed` outcome be accepted as success — the new negative catches that.
- `guard_node_identity` now runs **before** `continuity_allow`; the blocked-reason remap is gone. Bypassing it changes the rejection from `continuity_mismatch` to `continuity_blocked`, so the negative flips.
- `guard_fresh_authorized` has a crafted `ContinuityPlan(decisionStatus="allow", fresh-primed/freshAuthorized=False)` negative; bypassing the guard turns the expected `fresh_not_authorized` into a successful resume.

I also verified the new seams are load-bearing, not decorative:

| New seam | Mutation | Result |
| --- | --- | --- |
| `fake_rig.check_launch_options` | return always-ok | **4 failed**, 35 passed |
| `freeze.detect_claim_window_escape` | return always-ok | **3 failed**, 145 passed, 1 skipped |

F-01/F-09 remain load-bearing after the changes: `assert_fixture_home` → allow-all ⇒ **3 failed**; `no_external_io` → no-op ⇒ **6 failed**. `guards.py` is still byte-identical in the two fixture dirs.

---

## 4. Round-1 WARNs: disposition checked

| Item | Independent check |
| --- | --- |
| W1 `COMMAND_GUARDS` dead | Now consumed by `test_command_guards_is_a_live_coverage_map`; the table's union equals `GUARD_REGISTRY`. The behavioral proof remains the 14/14 mutation result, not the static table. |
| W2 blocked resume wrote files | Fixed: `_prepare_launch` no longer writes; `_activate_launch()` and `continuity-plan.json` are written only after `allow`. `test_resume_without_token_is_blocked_with_zero_mutation` asserts both paths absent, `mutation_count == 0`, `runner.calls == []`. |
| W3 `make_context` used global `/tmp` | Fixed: `tmp_root` defaults to the run directory's parent and is passed to both `assert_fixture_home` calls. Tests use `tmp_path`. |
| W4 test wrote outside `tmp_path` | Fixed: the outside-base artifact is under the test's own `tmp_path` (`tmp_path/base` vs `tmp_path/outside.txt`). |
| W5 no `unknown_option` / claim-window surface | Added and negative-tested: `start --resume`, `--skip-validate`, `--skip-archive`, `resume --force` → `unknown_option`; unknown verb → `unknown_verb`; claim-window rewrite with mtime rollback → `claim_window_escape`, mtime-only drift recorded separately, clean/missing controls present. |

---

## 5. Residual WARNs (no blocker; for `build_redteam` / `main_verify`)

1. **W6 is still a plan-command defect, not a fixture defect.** 00-plan §6.1 command 6 (`git status --porcelain | grep -v ... # expect: 空`) can never be empty: KB has 275 pre-existing dirty entries, and the command also filters the run directory that is already part of that 275. Current measured state: total 277 = 275 baseline + `tests/fixtures/` + `tests/redteam/`; excluding fixtures+redteam = **275** (baseline); tracked `git diff` sha unchanged. `main_verify` must use the count/sha comparison, not "empty".
2. **`COMMAND_GUARDS["status"] = ()`** while `status()` calls `guard_daemon_identity`, `guard_home_match`, `guard_port_collision`, `guard_launch_ttl` to build `drifts`. This is read-only drift reporting, not rejection, so it is not an RT-30 miss; just note the table is a rejection-coverage map, not a call graph.
3. **`guard_seat_outcome_match` ignores extra keys in `actual`.** `expected_outcome_map` covers planned seats only; an unexpected extra seat outcome is not flagged (the `n-a` seats are deliberately skipped in both the guard and `verify_outcomes`). Consistent today; `build_redteam` should not read extra-key silence as coverage.
4. **`check_launch_options` does not treat `--` as end-of-options** (`--` itself is collected as an unknown `--` token). RT-02's `--` boundary is handled by `strip_allow_override`, not this helper; do not route RT-02 through `check_launch_options` without fixing that.
5. Trivial: `start()` assigns `launch` from `_prepare_launch()` but does not use the local (line 941); harmless lint.

---

## 6. Verdict

**PASS-WITH-WARN.** The fixture harness now meets the `qa_fixtures` objective:

- fake objects cannot silently become real (F-01/F-09 negatives load-bearing under mutation);
- negative controls fail for the right reason (14/14 guards flip; the three round-1 misses are now wired and covered);
- counts, rc, determinism, offline behavior, and zero product delta are real and independently reproduced.

The remaining items are documented warnings for `build_redteam` and `main_verify`; none blocks the red-team step. S8 has not started; no product code was changed.
