# Packet C — R11 / R12 evidence summary

> run `openrig-p1-hard-constraints-20261116` · step `impl_wrapper_boundary` · writer TDO-OC
> scope: `scripts/**`, `tests/**`, master `ENTRYPOINTS.md`, this run's `reports/**`
> no commit/push · no product-repo writes · no live rig start (only dry-run + fakes)

## 1. What was implemented

| ID | File | Change |
| --- | --- | --- |
| R11 | `scripts/openrig_run.py` (new) | `check` executes five ordered steps and reports `{ok, checks[], next[]}`: bridge read (missing/bad → **rc2**) → `verify_render.py` (mismatch WARN by default, blocked by `--strict-render`; manifest error always blocks) → `tools/openrig_bridge.py doctor` (rc≠0 blocks) → `<cli> workflow validate <spec> --json` (rc≠0 blocks) → `<cli> ps --nodes --rig <rig> --json` (daemon down blocks unless `--allow-daemon-down`; otherwise every `seatMap` target must exist with `startupStatus == "ready"`). `start` = `check --allow-daemon-down` → `daemon start --no-kernel --port` → `up <rigSpec>` → bounded `ps` poll → `workflow validate` → `workflow instantiate`; first failure stops the chain with a rollback hint; `--dry-run` emits the exact command list and executes **nothing** (no daemon, no up, no validate/instantiate, no ps). Never deletes `OPENRIG_HOME`/DB; never replaces instantiate idempotency. |
| R12 | `templates/.../openrig-workflow-master/ENTRYPOINTS.md` | new §4.1 “复制 vs 生成”：human-written control-plane docs are copied + hand-maintained; the machine bundle (`openrig/**`) is rendered by `render_master.py` and must not be hand-edited; run specializations must be recorded via `wf.py render-specialize` (checked by `verify_render.py`); upgrades re-render new runs only, never a running run's binding graph; start order collapses to `openrig_run.py check/start`. |

## 2. Test evidence (real rc)

| artefact | command | rc |
| --- | --- | --- |
| `targeted-pytest.txt` | `pytest tests/test_openrig_run.py -q` | **0** (13 passed) |
| `full-pytest.txt` | `pytest tests -q` | **0** (**291 passed**; B left 278) |
| `entrypoint-check-live.txt` | `openrig_run.py check --run-dir runs/<this> --json --allow-daemon-down` | **0** — bridge ok, render **warn** (4 files differ from manifest), doctor ok, workflow validate ok, 3/3 seats ready |
| `entrypoint-start-dryrun.txt` | `openrig_run.py start --run-dir runs/<this> --dry-run --json` | **0** — plan = `daemon start --no-kernel --port 47978`, `up …/rig.yaml`, `ps`, `workflow validate`, `workflow instantiate`; `executed: []` |

## 3. Negative evidence (fake rig, isolated temp run, no live calls)

| artefact | scenario | result |
| --- | --- | --- |
| `negative-check-daemon-down.txt` | fake `ps` fails | default rc **1** (`seats: fail`) with `next:` hinting `daemon start`; `--allow-daemon-down` rc **0** (`seats: warn`) |
| `negative-strict-render.txt` | manifest bytes tampered | default rc **0** (`render: warn`, `ok:true`); `--strict-render` rc **1** (`render: fail`, mismatches listed) |
| `negative-bridge-and-render.txt` | bridge deleted / bridge corrupted | **rc2** both, `checks=[{bridge: fail}]`, `ok:false` |
| `negative-dryrun-no-live-call.txt` | fake rig + call log | dry-run: rc **0**, **call-count=0**, `executed: []`; control non-dry `start` on the same fake: **8** calls (validate, ps, daemon start, up, poll×4) then rc1 on timeout → proves the poll is bounded and the chain really invokes the CLI |
| pytest `test_start_stops_at_first_failure_with_rollback` | `up` fails | `failedStep=up`, `workflow-instantiate` never ran, rollback text names `down t-rig` + “delete nothing automatically” |
| pytest `test_start_fails_when_precheck_fails` | seats incomplete | `failedStep=precheck`, **no** `daemon start` call, “nothing was started” |

## 4. Before / after (W4 used for real this time)

`snapshot-before-C.json` (= `evidence/B/snapshot-after-B.json`) → `snapshot-after-C.json`:

| path | before | after | changed |
| --- | --- | --- | --- |
| `templates/specialized/openrig-workflow-master/ENTRYPOINTS.md` | `ffb387ba59fc…` | `6782e1ff9e1e…` | yes |
| `scripts/openrig_run.py` | absent | `e2209d5c6571…` | created |
| `tests/test_openrig_run.py` | absent | `01a6cccce3c1…` | created |

## 5. Scope (G5 / M9)

`scope.txt`: only the three C files are new/modified (+ caches). Product repo three values
still match plan §2 (HEAD `e932ae9…`, status `3b64cf9…`, diff `2cbcef6…`).

## 6. WARN

- **W-C1** The **live** run's render manifest is already drifted: `rig.yaml`, `workflow.yaml`,
  `guidance/team.md`, `OPENRIG-BRIDGE.json` differ from `render-manifest.json`
  (rendered 16:47:32Z). `check` reports this as **WARN** by default, which is exactly why
  `--strict-render` exists. Re-rendering a running run's bundle is prohibited by R12/§4.1 and by
  project §5 (don't rebind a live run), so this drift is reported, not fixed.
- **W-C2** `templates/specialized/openrig-workflow-master/BASELINE-post.sha256` was **already**
  stale before this packet (`README.md`, `SPEC.md` fail). R12 requires editing
  `ENTRYPOINTS.md`, which adds a third failing entry. Refreshing that sha baseline is a master
  version-bump action (`VERSION`, `CHANGELOG`) outside TASK §0's whitelist → reported only.
  Anyone running the documented `sha256sum -c BASELINE-post.sha256` read-only entry path will see
  three FAILED lines; that is pre-existing + this one, not a product change.
- **W-C3** `start` was never executed for real in this packet (deliberate: a live rig is already
  running and instantiating twice is the rig's own error). Only `--dry-run` and fake-rig chains
  were exercised.

## 7. Reproduce

```bash
cd /home/a7067567g/下载/deepseek/deepseek-知识库/workflow-group
.venv/bin/python -m pytest tests -q                                         # 291 passed
.venv/bin/python scripts/openrig_run.py check --run-dir runs/openrig-p1-hard-constraints-20261116 --json --allow-daemon-down
.venv/bin/python scripts/openrig_run.py check --run-dir runs/openrig-p1-hard-constraints-20261116 --json --strict-render   # rc1 (render drift)
.venv/bin/python scripts/openrig_run.py start --run-dir runs/openrig-p1-hard-constraints-20261116 --dry-run --json
```
