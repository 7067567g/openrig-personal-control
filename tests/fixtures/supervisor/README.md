# supervisor fixture (F-02..F-08)

**Not authoritative.**  The contract is
`runs/openrig-s7-harness-redteam-20261116/reports/00-plan.md` §4.  This file is
an orientation for the QA red-team step; it grants no extra scope.

Everything is in-process and offline: no daemon, rig, seat, workflow, model,
socket, subprocess or real `$OPENRIG_HOME`.

## Modules

| file | contract | key entry points |
| --- | --- | --- |
| `supervisor_sim.py` | F-02 | `make_context`, `detect_context`, `authorize_direct`, `SupervisorSim.{check,start,resume,status,stop,archive_run,next}` |
| `observation.py` | F-03 | `Sources`, `evaluate`, `judge_stall` |
| `continuity.py` | F-04 | `SeatFacts`, `plan`, `verify_outcomes`, `default_outcomes` |
| `freeze.py` | F-05 | `capture`/`freeze`, `self_diff`, `verify_review_input`, `detect_claim_window_escape`, `digest_bundle`, `verify_compliance`, `identity` |
| `archive.py` | F-06 | `gate`, `stop_allowed`, `require_complete` |
| `wake.py` | F-07 | `Wake`, `deliver` |
| `acceptance.py` | F-08 | `parse`, `parse_one`, `verify_tree`, `ShapeError` |
| `guards.py` | F-09 | `no_external_io`, `assert_fixture_home`, `fixture_mark` |

`fake-rig/fake_rig.py` also provides the RT-02 `--allow-direct` pre-parse
(`strip_allow_override`) and the RT-03/RT-04 option validator
(`check_launch_options`).

`guards.py` is byte-identical in `../fake-rig/`; either copy may resolve.

## Supervisor invariants

* every refusal is `rc=2`, `Outcome.mutated is False`, `mutation_count` unchanged;
* `mutation_count` only moves inside `_commit_step`;
* a failure after mutation writes `reports/evidence/manifest/run-manifest.partial.json`
  with `failed`, `executed` and `notExecuted`, and never deletes home/DB;
* `status` is read-only and only returns `drifts[]`;
* `resume` writes `continuity-plan.json` only after the allow decision and
  before any live mutation (a blocked decision writes nothing);
* `resume` decides per-seat outcome matching through
  `guard_seat_outcome_match`, so that guard is the load-bearing negative;
* guard order in `resume` is `node_identity` → `continuity_allow` →
  `fresh_authorized`, so each guard's false branch can decide a test.

## Mutation control (RT-30)

`GUARD_REGISTRY` lists every named guard and `GUARD_CODES` maps it to the
rejection code.  `COMMAND_GUARDS` is the coverage map consumed by
`test_command_guards_is_a_live_coverage_map` (every listed guard must exist and
every named guard must be listed by at least one command).  Guards are looked
up from module globals at call time, so
`monkeypatch.setattr(supervisor_sim, "guard_x", lambda *a, **k: True)` makes the
corresponding negative test flip from red to green — which is exactly what RT-30
must observe.  A 14/14 mutation sweep is part of the fixture evidence.

## Scripting a supervisor run

```python
from fake_rig import Clock, FakeRig, IdFactory, Step

ctx = make_context(tmp_path / "run", seats=(SeatStatus("main", "sess-main"),))
script = [
    Step(argv=("rig", "daemon", "start", "--no-kernel", "--port", str(ctx.port)), repeat="consumed"),
    Step(argv=("rig", "up", str(ctx.rig_spec), "--cwd", str(ctx.project),
               "--yes"), repeat="consumed"),
    Step(argv=("rig", "workflow", "validate", "--rig", ctx.rig_name), repeat="consumed"),
    Step(argv=("rig", "workflow", "instantiate", "--root-objective", "...",
               "--created-by", "...", "--rig", ctx.rig_name), repeat="consumed"),
]
clock, ids = Clock(), IdFactory()
runner = FakeRig(tmp_path / "runner-home", script, clock, ids, tmp_root=tmp_path)
sim = SupervisorSim(ctx, runner=runner, clock=clock, ids=ids)
assert sim.start().ok
```

## Run

```bash
cd workflow-group
.venv/bin/python -m pytest tests/fixtures/supervisor -q
python3        -m pytest tests/fixtures/supervisor -q
```
