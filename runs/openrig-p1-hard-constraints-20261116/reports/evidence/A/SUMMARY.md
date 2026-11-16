# Packet A — W2 / W3 / W4 evidence summary

> run `openrig-p1-hard-constraints-20261116` · step `impl_preflight_evidence` · writer TDO-OC
> scope: `workflow-group/scripts/**`, `workflow-group/tests/**`, this run's `reports/**` only
> no commit/push · no product-repo writes · no money budget

## 1. What was implemented

| ID | File | Change |
| --- | --- | --- |
| W2 | `scripts/openrig_preflight.py` | read-only pre-check (`preflight_file` / `required_components` / `run_context` / `run_docs`) runs first; any required failure returns immediately with `injectedAgents=null`, `monitor=null`, `workspace_context` marked `skipped:true`. `inject_agents` + `register_monitor` only run after the pre-check passes, then `check_workspace_context` runs. `ok = all(required checks)` unchanged; `--advisory` only relaxes rc, never fakes `ok:true`. New payload field `precheck:{ok,failed[]}`. |
| W3 | `scripts/wf.py` | new `meta-set <run-id> --project-root PATH [--scope TEXT] [--json]` writing/updating `.run-meta.json` (preserves `template`/`createdAt`, rejects a non-git root, `run_exists` check). `baseline` missing-`projectRoot` error now prints **both** repair paths (`meta-set` and `--project-root`). `new-run` meta behaviour untouched. |
| W4 | `scripts/snapshot_files.py` (new) | `--out/--label before|after/--path` (repeatable, dirs recursive, `.git` skipped, dedup, stable order). One entry per file: `{path,bytes,sha256,mtime,label,capturedAt,exists}`; missing path → `exists:false`, no raise; only the `--out` file is written. |

## 2. Test evidence (real rc)

| artefact | command | rc |
| --- | --- | --- |
| `targeted-pytest.txt` | `.venv/bin/python -m pytest tests/test_openrig_preflight.py tests/test_wf_baseline.py tests/test_snapshot_files.py -q` | **0** (22 passed) |
| `full-pytest.txt` | `.venv/bin/python -m pytest tests -q` | **0** (**270 passed**, baseline was 259) |
| `entrypoint-preflight-advisory.txt` | `scripts/openrig_preflight.py --json --advisory` | **0**, `ok:false` (no run context) — advisory keeps rc0 without faking ok |
| `entrypoint-meta-set-help.txt` | `scripts/wf.py meta-set --help` | **0** |

## 3. Negative / positive evidence

| artefact | scenario | result |
| --- | --- | --- |
| `negative-preflight-invalid-run.txt` | non-existent `--run-id` + temp workspace carrying a user `AGENTS.md` | rc **1**, `ok:false`, `precheck.failed=[run_context,run_docs]`, `injectedAgents=null`, `monitor=null`, **AGENTS.md sha unchanged** (`ec6464…` before/after), **dashboard target.json sha unchanged** (`62ee9d…` before/after), zero `subprocess` calls |
| `negative-preflight-advisory.txt` | same, with `--advisory` | rc **0** but `ok:false`, `injectedAgents=null`, AGENTS.md sha unchanged — advisory never injects |
| `positive-preflight-injection.txt` | valid run + fresh temp workspace | rc **0**, `precheck.ok:true`, all 5 checks ok, injection happened (`bytes:939`), `monitor` skipped via `--no-monitor` |
| `negative-wf-baseline-legacy.txt` | `wf.py baseline burn-postmortem-20261014` (no `.run-meta.json`, no `--project-root`) | rc **1**; stderr contains **both** `meta-set` and `--project-root`; no meta file written |
| `positive-meta-set-baseline.txt` | temp **copy** of that legacy run → `meta-set` → `baseline` **without** `--project-root` | `meta-set.rc=0`, meta written, `baseline.rc=0`; the real run dir untouched (`real-run-meta.untouched=yes`) |
| `positive-snapshot-before-after.txt` | untracked file, before/after | both recorded; sha256 `2d27fb…` → `2805e4…` (distinct), bytes 3 → 11 |
| `negative-snapshot-missing.txt` | missing path; bad `--label` | rc **0** with `exists:false,sha256:null`; bad label → rc **2** |
| pytest `test_missing_run_docs_fails` | run docs removed, workspace present | rc 1, `workspace_context.skipped:true`, `AGENTS.md` **not created** (in-process sandbox; the CLI-level variant of run_docs-only needs a fake `runs/<id>`, which would be an out-of-scope write) |

## 4. Scope (G5 / M9)

`scope.txt`: every file newer than the plan baseline, classified against TASK §0.

- in-scope: `scripts/{openrig_preflight.py,wf.py,snapshot_files.py}`, `tests/{test_openrig_preflight.py,test_wf_baseline.py,test_snapshot_files.py}`
- expected, not authored by A: `AGENTS.md` (documented drift, plan §2.1), `workflow-group/kickoff/openrig-p1-hard-constraints-20261116.txt` (control-main, plan time)
- product repo three values all match plan §2: HEAD `e932ae9…`, status sha `3b64cf9…` (29 pre-existing dirty), diff sha `2cbcef6…`
- no new file under `templates/**`, `roles/**`, other `runs/**`, `workflow-group/README.md`, or `.github/**`

## 5. WARN — honest gaps

- **W-A1 before-hash not captured.** `workflow-group/scripts/**` is untracked in the KB repo and no pre-A copy existed, so `changed-files.txt` records `after` sha256 only. `baseline-refresh-note.md` explains why and what replaces it (mtime sweep + product three-value check + real rc evidence). W4 (built in this packet) is the fix for B/C/D; A could not use its own tool retroactively.
- **W-A2 baseline instrument drift.** Plan-time `00-baseline.txt` lists untracked entries as directories (245 lines); the refreshed capture is file-level (1917 lines). The two are not line-comparable. Original preserved as `00-baseline.original.txt`.
- **W-A3** The refreshed baseline necessarily contains Packet A (captured after A's edits). Treat it as the forward reference for B/C/D/QA, not as A's independence proof.

## 6. Reproduce

```bash
cd /home/a7067567g/下载/deepseek/deepseek-知识库/workflow-group
.venv/bin/python -m pytest tests -q                    # expect 270 passed, rc0
.venv/bin/python -m pytest tests/test_openrig_preflight.py tests/test_wf_baseline.py \
    tests/test_snapshot_files.py -q                    # expect 22 passed, rc0
.venv/bin/python scripts/openrig_preflight.py --json --advisory
.venv/bin/python scripts/snapshot_files.py --out /tmp/b.json --label before --path README.md
.venv/bin/python scripts/wf.py meta-set --help
```
