# Packet D — W5 / R04b evidence summary

> run `openrig-p1-hard-constraints-20261116` · step `impl_close_render` · writer TDO-OC
> scope: `scripts/**`, `tests/**`, this run's `reports/**` · no commit/push · no product-repo writes

## 1. What was implemented

| ID | File | Change |
| --- | --- | --- |
| W5 | `scripts/verify_render.py` | new `--specializations <json>` (default `<run-dir>/openrig/render-specializations.json`). A manifest/disk mismatch whose entry matches disk **bytes + sha256 exactly and carries a non-empty `reason`** becomes a legal specialization: `ok:true`, item `specialized:true`, listed under `specialized[]`/`specializations.applied[]`, and `--strict` stays **rc0**. Stale entries (bytes/sha differ, or no reason) do **not** rescue the mismatch and are listed under `specializations.stale[]`. Corrupt/invalid specialization file → **rc2** (fail closed). No specialization file → previous behaviour, byte-for-byte. |
| W5 | `scripts/wf.py` | new `render-specialize <run-id> --path <rel> --reason TEXT [--json]`: resolves `<run-dir>/openrig/<rel>`, refuses paths escaping `openrig/`, refuses unknown files, refuses an empty reason, records `{bytes,sha256,reason,recordedAt}` under `files[rel]`, preserves other entries and the run id. |
| R04b | `scripts/wf_close_lint.py` | `resolve_final()` accepts **`reports/FINAL.md` first, then root `FINAL.md`**; `final_missing` only when both are absent; `final_after_closeout` now reports the resolved relative path and accepts a revision record under either label. `closeout.json`, sha256 and revision-chain checks are untouched (an entry must still name the exact path it hashes). |

## 2. Test evidence (real rc)

| artefact | command | rc |
| --- | --- | --- |
| `targeted-pytest.txt` | `pytest tests/test_wf_render_specialize.py tests/test_verify_render.py tests/test_wf_close_lint.py -q` | **0** (46 passed) |
| `full-pytest.txt` | `pytest tests -q` | **0** (**310 passed**; C left 291) |
| `entrypoint-verify-render.txt` | `verify_render.py --run-dir runs/<this> --json` | **0**, `ok:false`, 4 mismatches, `specializations.present=false` (no specialization registered for the live run — correct: its drift is *not* an intended specialization) |

## 3. W5 matrix (CLI, temp copy of this run's bundle, nothing live touched)

| step | result |
| --- | --- |
| no specialization | rc **0**, `ok:false`, mismatches = `rig.yaml, workflow.yaml, guidance/team.md, OPENRIG-BRIDGE.json` |
| record `rig.yaml` + `workflow.yaml` via `wf.py render-specialize` | two entries written; re-verify → `ok:false` for the **remaining two only**, `specialized=[rig.yaml, workflow.yaml]`, `stale=[]` |
| mutate a recorded file afterwards | `--strict` rc **1**, stale entry reported `stale specialization (bytes differ)` — **stale does not rescue** |
| record all four | `--strict` rc **0**, `ok:true`, `specialized` = all four, `mismatches=[]` |

Artifacts: `positive-specialization-flow.txt`, `positive-specialization-all-green.txt`.
Unit-level matrix (no spec / exact / stale / no-reason / bad JSON / `--specializations` override) is in
`tests/test_wf_render_specialize.py` (13 tests).

## 4. R04b matrix (`close-lint-dual-final.txt`, temp runs-root with the four-piece docs present)

| temp run | result |
| --- | --- |
| only `reports/FINAL.md` (+ matching closeout entry) | rc **0**, no findings |
| only root `FINAL.md` | rc **0**, no findings |
| both present, closeout entry for `reports/FINAL.md` | rc **0** → reports/ wins; the stale root copy is ignored |
| neither | rc **1**, `final_missing` |
| live run (pre-close) | rc **1**, `final_missing` + `closeout_missing` — expected per plan §6.1; not made green by deleting checks |

Plus unit coverage in `tests/test_wf_close_lint.py`: reports-only PASS, root-only PASS, both-prefers-reports,
`reports/FINAL.md` hash mismatch → ERROR, `reports/FINAL.md` after `closedAt` → `final_after_closeout` (and
covered by a `REV-*.json` record with `path: reports/FINAL.md`).

## 5. Before / after (W4)

`snapshot-before-D.json` → `snapshot-after-D.json`, recorded in `changed-files.txt`:
`verify_render.py fa812300…→14e5dd03…`, `wf.py ac349a02…→0e5130e8…`,
`wf_close_lint.py 38ca354d…→2e8d70db…`, `test_wf_close_lint.py c8e4b755…→68da9291…`,
`test_wf_render_specialize.py` created, `test_verify_render.py` **unchanged** (W5 tests live in the new file).

## 6. Scope (G5 / M9)

`scope.txt`: only the five D files changed (+ caches). Product repo three values still match
plan §2 (HEAD `e932ae9…`, status `3b64cf9…`, diff `2cbcef6…`).

## 7. WARN

- **W-D1** The live run's bundle still has **four unrecorded drift** entries. W5 now *can* legalize them,
  but doing so would assert an intent nobody authored: the drift appeared after rendering, and R12/§4.1
  forbids re-binding a running run. So Packet D deliberately did **not** register specializations for the
  live run; QA/close must decide whether to re-render at close time or record a real reason.
- **W-D2** `verify_render.py` is also consumed by `openrig_run.py` (Packet C). The new rc2-on-corrupt-
  specialization path therefore makes `openrig_run.py check` block (fail-closed) if someone leaves a broken
  specialization file behind — intended, and it only triggers when the file exists.
- **W-D3** `test_verify_render.py` was in the plan's "modify" list but needed no change; the W5 tests went to
  `tests/test_wf_render_specialize.py` instead (same assertions, plus `wf.py` side). Recorded as unchanged,
  not silently dropped.

## 8. Reproduce

```bash
cd /home/a7067567g/下载/deepseek/deepseek-知识库/workflow-group
.venv/bin/python -m pytest tests -q                                              # 310 passed
.venv/bin/python scripts/verify_render.py --run-dir runs/openrig-p1-hard-constraints-20261116 --json
.venv/bin/python scripts/wf.py render-specialize --help
.venv/bin/python scripts/wf.py render-specialize <run-id> --path rig.yaml --reason "…"   # on a copy only
```
