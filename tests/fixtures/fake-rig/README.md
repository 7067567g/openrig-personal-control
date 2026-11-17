# fake-rig fixture (F-01 + F-09)

**Not authoritative.**  The contract is `runs/openrig-s7-harness-redteam-20261116/reports/00-plan.md` §4.

Offline, deterministic substitute for the `rig` CLI.  No daemon, seat, model,
network, subprocess or real `$OPENRIG_HOME` is touched.

## Files

| file | role |
| --- | --- |
| `fake_rig.py` | `FakeRig`, `Step`, `Call`, `Clock`, `IdFactory`, `strip_allow_override` |
| `guards.py` | F-09 external-IO ban and `assert_fixture_home` (duplicated in `../supervisor/`) |
| `conftest.py` | self-contained path bootstrap + autouse IO ban |
| `test_fake_rig.py` | self-tests (capture, rc, repeats, escape, redaction, RT-02) |

## Invariants

1. An unscripted call returns `rc=2, code="fixture_unscripted_call"` — never
   a default `rc=0` (HF-055).
2. Repeated calls must declare a `repeat` mode: `consumed`, `idempotent` or
   `unscripted`.  Nothing is implicit.
3. Each `Call` carries `startedAt` **and** `endedAt`, stdout/stderr sha256,
   `phase`, `provenance="fixture"` and the fixture marker.
4. `home` must be a disposable temp directory: a real `$OPENRIG_HOME` or any
   directory containing `openrig.sqlite` raises `FixtureEscape`.
5. `--allow-direct` is stripped only *before* the subcommand; after the
   subcommand or after `--` it is left untouched.

## Run

```bash
cd workflow-group
.venv/bin/python -m pytest tests/fixtures/fake-rig -q
python3        -m pytest tests/fixtures/fake-rig -q
```
