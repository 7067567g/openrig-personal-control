# QA verdict — `qa_fixtures` round 1

- Packet: `qitem-20261116052502-0bbb4957`
- Workflow instance: `01M7HC05T9RMCJ00X6ZCE68BSF`
- Reviewer: `assurance-qa@openrig-s7-harness-redteam-20261116`
- Reviewed step: `build_fixtures` (owner `exec-tdo-oc`)
- Verdict: **FAIL** (fixture defect; RT-30 mutation coverage cannot reach 100%)
- Next hop: `build_fixtures` (TDO), per workflow `next_hop.on.failed`
- Write scope used: this file only (`tests/redteam/VERDICTS/qa-fixtures-round-1.md`). Fixtures were read-only; nothing outside `tests/redteam/**` was written.

Captured: `2026-11-16T05:30:08Z`.

---

## 1. Environment (measured, not copied)

| Fact | Value |
| --- | --- |
| canonical interpreter | `workflow-group/.venv/bin/python` = Python **3.12.15**, pytest **9.0.2** |
| system interpreter | `python3` = Python **3.14.4** (no openpyxl) |
| KB repo | HEAD **a1f6eaa**, tracked `git diff` sha256 prefix **1b48354a79122e55** (matches 00-plan B6) |
| product repo | `deepseek-项目/10-openrig-deepseek` HEAD **e932ae9**, dirty **34**, statusSha **011f382fba6cdc4f**, diffSha **697800868bcbf83d** (matches 00-plan B7) |
| S6 tree | `EXECUTION-TREE-v2.json` sha256 prefix **e01443e5** (matches 00-plan §2) |
| live mutation | none: I started no daemon/rig/seat/workflow/model; all test functions ran under the F-09 external-IO ban |

---

## 2. Commands actually run, with real counts and rc

All from `<WORKFLOW_GROUP>`:

```text
.venv/bin/python -m pytest tests/fixtures/supervisor -q      -> 141 passed, rc=0
.venv/bin/python -m pytest tests/fixtures/fake-rig   -q      ->  34 passed, rc=0
python3         -m pytest tests/fixtures/supervisor -q      -> 141 passed, rc=0
python3         -m pytest tests/fixtures/fake-rig   -q      ->  34 passed, rc=0
.venv/bin/python -m pytest tests -q                          -> 504 passed, rc=0
.venv/bin/python -m pytest tests --ignore=tests/fixtures -q  -> 329 passed, rc=0  (baseline reproduced)
.venv/bin/python -m pytest tests/fixtures/supervisor tests/fixtures/fake-rig -q -rsx
                                                              -> 175 passed, rc=0, 0 skipped, 0 xfailed
PYTHONHASHSEED=1/2/7 ... -q -p no:cacheprovider              -> 175 passed each, rc=0
PATH=/nonexistent .venv/bin/python -m pytest tests/fixtures/supervisor tests/fixtures/fake-rig -q
                                                              -> 175 passed, rc=0
```

- **Count honesty:** 175 = 141 + 34; 504 − 175 = 329 baseline, so the claimed +175 delta is real.
- **No hidden skips/xfails** in the fixture suites: `-rsx` reports zero. The only `pytest.skip` is `test_acceptance.py:105`, allowed by 00-plan §6 when the S6 tree is missing. The tree **is present** here, so the test ran: `68/68 parsed, unresolved=0, ok=True`, and the two `code=` rows resolve to `{archive_incomplete, continuity_blocked}`.
- `-q` counts match `--collect-only` (175 collected), so no test is silently shadowed.

---

## 3. "A fake must not silently become the real thing"

Verified independently, not from TDO's prose:

1. **Escape negatives are real.** `FakeRig` / `make_context` reject `$OPENRIG_HOME`, a directory containing `openrig.sqlite`, and a path outside the supplied temp root, with `FixtureEscape` and a named reason.
   - Mutation probe: replace `guards.assert_fixture_home` with an allow-all stub in a throwaway copy → **3 failed** (the three escape negatives flip red). The guard is load-bearing.
2. **External-IO ban is real.** `no_external_io()` intercepts `socket.connect`, `subprocess.Popen/run`, `os.system`, `urllib.request.urlopen`, `http.client.HTTPConnection`.
   - Mutation probe: replace `no_external_io()` with a no-op context manager → **6 failed**. The ban is load-bearing, not decorative.
3. **No product coupling.** Fixture modules import only stdlib and their own modules; no `openrig_run`, no `wf`, no product package. `tests/fixtures/{fake-rig,supervisor}/guards.py` are byte-identical (`cmp` = equal).
4. **No hard-coded real paths.** `grep` for `/home/`, `OPENRIG_HOME`, `openrig.sqlite`, `/tmp/` finds only the deliberate rejection logic and its tests. Every test home is a `tmp_path` derivative.
5. **No tracked-repo mutation.** KB `git diff` sha256 is unchanged from the plan baseline; product `status`/`diff` sha256 are unchanged; there are no `^ D` (tracked-delete) entries. KB `status` total 276 = 275 baseline + the untracked `tests/fixtures/` line.

Conclusion: the core "fake ≠ real" property holds for **F-01/F-09**. This part of the fixture step is sound.

---

## 4. Negative controls under RT-30 mutation (the failure)

I copied the two fixture directories to a throwaway `/tmp` tree, overrode **one named guard at a time** with `return True` (the module resolves guards via `globals()` at call time), and ran `pytest tests/fixtures/supervisor` in the copy. Baseline copy: 140 passed, 1 skipped (the S6-tree test skips only because the copy has no `runs/`; the real tree is 141 passed).

| Guard overridden to `return True` | Result | Flips? |
| --- | --- | --- |
| `guard_bridge_sha` | 2 failed | yes |
| `guard_home_match` | 1 failed | yes |
| `guard_no_legacy_run` | 1 failed | yes |
| `guard_rig_absent` | 1 failed | yes |
| `guard_workflow_absent` | 1 failed | yes |
| `guard_daemon_identity` | 2 failed | yes |
| `guard_port_collision` | 1 failed | yes |
| `guard_launch_ttl` | 4 failed | yes |
| `guard_verb_unconsumed` | 2 failed | yes |
| `guard_continuity_allow` | 1 failed | yes |
| `guard_archive_complete` | 2 failed | yes |
| **`guard_fresh_authorized`** | **140 passed, 1 skipped** | **NO** |
| **`guard_node_identity`** | **140 passed, 1 skipped** | **NO** |
| **`guard_seat_outcome_match`** | **140 passed, 1 skipped** | **NO** |

**11/14 = 78.6%**, not the 100% required by 00-plan §5 RT-30 / DoD #2. The three non-flipping guards are not equivalent:

- `guard_fresh_authorized`: **called but never returns `False`** in any test. Overriding it to `False` fails 3 tests, so it is wired; but no test reaches the unauthorized-fresh branch. The `fresh_not_authorized` outcomes asserted by tests come from `continuity.plan()` / `verify_outcomes()`, not from this guard.
- `guard_node_identity`: **called but never returns `False`** in any test. `continuity.plan()` blocks a node mismatch first (`decisionStatus="blocked"`), so `guard_continuity_allow` rejects before this guard can decide; the `except` block then maps the blocked reasons back to `continuity_mismatch`. The guard's false branch is never the reason a test fails.
- `guard_seat_outcome_match`: **never called anywhere.** It is defined (`supervisor_sim.py:216`), registered in `GUARD_CODES`/`GUARD_REGISTRY`, and listed in `COMMAND_GUARDS["resume"]`, but `resume()` calls only `guard_continuity_allow`, `guard_fresh_authorized`, `guard_node_identity` (`supervisor_sim.py:1100-1105`). `COMMAND_GUARDS` itself has **no reader** in the whole fixture tree.

This is exactly the failure mode 00-plan §5 warns about: a negative that stays green when its named guard is bypassed is decoration. A red-team case that passed under these three mutations would not prove the guard protects anything.

### Minimal reproduction (no repo writes; throwaway copy only)

```bash
cd <WORKFLOW_GROUP>
tmp=$(mktemp -d)
cp -r tests/fixtures/supervisor "$tmp/supervisor"
cp -r tests/fixtures/fake-rig   "$tmp/fake-rig"
printf '\n\ndef guard_seat_outcome_match(*a, **k):\n    return True\n' \
  >> "$tmp/supervisor/supervisor_sim.py"
.venv/bin/python -m pytest "$tmp/supervisor" -q -p no:cacheprovider
# observed: 140 passed, 1 skipped, rc=0  <-- expected: failures, because the guard was bypassed
rm -rf "$tmp"
```

Repeat with `guard_fresh_authorized` and `guard_node_identity`; both also stay green. Control: the same procedure with `guard_bridge_sha` yields `2 failed, rc=1`.

---

## 5. Other findings (WARN, not the blocker)

| ID | Finding | Impact / recommendation |
| --- | --- | --- |
| W1 | `COMMAND_GUARDS` (`supervisor_sim.py:96`) is a dead constant and its `resume` row claims `guard_seat_outcome_match` is used; it is not. | Misleading contract. Either wire the guard or remove the row/constant. |
| W2 | `resume()` writes `home/entry/launch.json` (`_prepare_launch`) and `reports/evidence/manifest/continuity-plan.json` **before** `guard_continuity_allow` rejects. `test_resume_without_token_is_blocked_with_zero_mutation` says "zero mutation" but then reads the plan file it just wrote. | "Zero mutation" is true only for `mutation_count` / `runner.calls`; it is not true for the filesystem. Either document that pre-decision evidence is not a mutation, or move the write after the allow decision. RT-05's wording ("零 mutation") must not be read as "no files written". |
| W3 | `make_context()` calls `assert_fixture_home()` without `tmp_root`, so its "outside temp root" check is against global `/tmp`, not the test's `tmp_path`. | Not a live escape here: the real rig home is `/tmp/openrig-workflow-...` and is rejected because it contains `openrig.sqlite`; `OPENRIG_HOME` is also rejected. Still weaker than F-01's "home must be under `tmp_path`". |
| W4 | `test_capture_rejects_artifact_outside_base` writes `tmp_path.parent / "outside.txt"` and does not remove it. | Minor test hygiene; it writes outside the test-owned `tmp_path`. |
| W5 | No fixture surface for `unknown_option` (RT-03/RT-04) or `claim_window_escape` (RT-27). There is no argv/option validator and no claim-window primitive; a red-team test that simply scripts `rc=2 code=unknown_option` through `FakeRig` would be a tautology. | Decide in `build_redteam`: either add a minimal validator/hash-snapshot seam (TDO scope) or record these as named WARN residuals with an explicit owner. Do not claim them PASS by scripting the expected rc. |
| W6 | 00-plan §6.1 command 6 (`git status --porcelain \| grep -v ... # expect: 空`) cannot be empty: the KB has 275 pre-existing dirty entries. It also filters the run directory, which was already part of the 275 baseline, so its numeric answer is 274, not 275. | For `main_verify`: use TDO's count/sha comparison (`status` total 276 = 275 baseline + fixtures; tracked `diff` sha unchanged), not an "empty" expectation. This is a plan-command wording defect, not a fixture defect. |

---

## 6. Named blocker and required fix (owner: `exec-tdo-oc`, step `build_fixtures`)

**Blocker B1 — dead/mutation-insensitive guards prevent RT-30 100% coverage.**

- File: `tests/fixtures/supervisor/supervisor_sim.py`
- Assertion gap: with `guard_seat_outcome_match`, `guard_fresh_authorized`, or `guard_node_identity` replaced by `return True`, the full fixture suite stays green (`140 passed, 1 skipped` in the copy; `141 passed` in the real tree). There is no negative whose failure depends on those three guards.
- Expected: each guard named in 00-plan §4 F-02 invariant 3 has a negative that flips red under `return True` (RT-30, 100%).
- Actual: 11/14 guards flip; `guard_seat_outcome_match` has no call site at all.

**Required fix (choose explicitly, then state it in the evidence):**

1. `guard_seat_outcome_match`: wire it into `resume()` (or `verify_outcomes`) so that the per-seat outcome comparison is actually guarded, **and** add a negative that flips when the guard is bypassed; or remove it from `GUARD_CODES`/`GUARD_REGISTRY`/`COMMAND_GUARDS` and declare RT-30 coverage as 13/13 named-and-wired guards. Do not leave a declared-but-dead guard.
2. `guard_fresh_authorized`: add a fixture-level negative that reaches the false branch (e.g., a crafted `ContinuityPlan` with `decisionStatus="allow"`, a `fresh-primed` seat, `freshAuthorized=False`/empty reason) and assert `fresh_not_authorized`; or stop claiming that guard is the source of `fresh_not_authorized`.
3. `guard_node_identity`: either make the node-mismatch path reach this guard (so bypassing it changes the outcome), or remove it from the RT-30 coverage claim and keep `continuity.plan()`'s block as the single source of truth.

After the fix: re-run the exact §2 commands (both interpreters) and re-submit `qa_fixtures`. The rest of this verdict's §2/§3 evidence can be reused only if the fixture bytes are unchanged; any change to fixture bytes requires a fresh run.

---

## 7. What is not in question

- Test counts and rc are real (141/34/175/504/329; no hidden skip/xfail; 68/68 S6 rows).
- Fixtures are deterministic across hash seeds and run with `PATH=/nonexistent`.
- No real daemon/rig/model/network is used; F-01 escape and F-09 external-IO negatives are load-bearing under mutation.
- Product repo and all tracked files are byte-identical to the plan baseline.
- S8 has not started; no product guard/supervisor code was implemented or modified.
