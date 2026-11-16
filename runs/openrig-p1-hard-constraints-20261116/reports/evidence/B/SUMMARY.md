# Packet B — R09 / R10 evidence summary

> run `openrig-p1-hard-constraints-20261116` · step `impl_ci_blocks` · writer TDO-OC
> scope: `WORKFLOW-TAGS.md`, `.github/workflows/wf-validate.yml`, `scripts/**`, `tests/**`,
> this run's `reports/**` · no commit/push · no product-repo writes

## 1. What was implemented

| ID | File | Change |
| --- | --- | --- |
| R09 | `WORKFLOW-TAGS.md` | top-of-file 时效声明 `当前 canonical=55` → **`canonical=62`** (measured `ls -d runs/*/ \| wc -l` = 62; baseline=9 / specialized=26 unchanged). Historical sentence kept dated: `2026-11-11 曾为 37；2026-11-15 实测 55；2026-11-16 实测 62`. |
| R09 | `.github/workflows/wf-validate.yml` | two steps appended **after** `pytest`: `doc_consistency.py --check` and `tests/test_doc_consistency.py`. Trigger block (`on:`) untouched; no new dependencies (both are stdlib-only). |
| R10 | `scripts/audit_managed_blocks.py` (new) | read-only enumerator: `--path` repeatable (dir recursive, `.git` skipped, dedup), pairs `BEGIN`/`END`, emits `{files:[{path,bytes,blocks:[{id,startLine,endLine,kind,ownerRig,warning}]}], summary, strict}`. `kind ∈ {preflight, managed, unknown}`; `ownerRig` inferred **only** from `rig:<name>…` ids, otherwise `null`. Default rc0; `--strict` rc1 on non-preflight block with `ownerRig == null` or unterminated block. rc2 on unreadable input. |

## 2. Test evidence (real rc)

| artefact | command | rc |
| --- | --- | --- |
| `targeted-pytest.txt` | `pytest tests/test_audit_managed_blocks.py tests/test_doc_consistency.py -q` | **0** (16 passed) |
| `full-pytest.txt` | `pytest tests -q` | **0** (**278 passed**; A left 270) |
| `positive-doc-consistency.txt` | `doc_consistency.py --check` / `tests/test_doc_consistency.py` | **0 / 0** (was rc1 before the count fix) |
| `negative-doc-count-55.txt` | tamper canonical back to 55 → check → restore | **1** then **0**; `byte-identical-restore=yes` (`c2f01cad…` before and after) |
| `audit-real-agents.txt` | real `AGENTS.md` | default **0** (7 blocks, `orphanManaged=7`), `--strict` **1**, no-block file → `blocks=0` rc **0** |
| `ci-wiring-diff.txt` | `git diff .github/workflows/wf-validate.yml` | only the two appended steps; `(no trigger changes in diff)` |

## 3. R10 finding on the real repo (this is the point of the tool)

```
summary= {'files': 1, 'filesWithBlocks': 1, 'blocks': 7, 'byKind': {'managed': 7},
          'orphanManaged': 7, 'warnings': 0, 'unterminated': 0, 'errors': 0}
CULTURE-default.md / guidance/team.md / openrig-start.md / openrig-onboarding-01.md /
openrig-onboarding-02.md / guidance/main-approver.md / guidance/tdo-b.md   → ownerRig=None
```

Every block id currently in `AGENTS.md` is a package/doc name, not a rig-qualified id, so
all seven are orphans and `--strict` fails. **That is the reported state, not a regression**
(TASK: strict is opt-in "用于后续接线"). Wiring owners would need a naming convention change
on the product side, which is explicitly out of scope (no `managed-blocks.ts` edits, no
namespace migration).

## 4. Scope (G5 / M9)

`scope.txt`: files newer than Packet A's evidence freeze = exactly the four B files
(+ `__pycache__` / `.pytest_cache`). Product repo three values still match plan §2:
HEAD `e932ae9…`, status `3b64cf9…`, diff `2cbcef6…`.

## 5. WARN

- **W-B1 before-hash.** `WORKFLOW-TAGS.md` is untracked and the CI file's pre-B bytes were not
  snapshotted before editing, so `changed-files.txt` has `after` only. Mitigations recorded:
  the exact 2-line edit is reversible and its effect is proven by `negative-doc-count-55.txt`
  (tamper → rc1, restore → byte-identical sha), and the CI change is shown as a full
  `git diff` (`ci-wiring-diff.txt`).
- **W-B2** From Packet C on this is fixed by construction: `snapshot-after-B.json` (captured
  with `scripts/snapshot_files.py`) is the **before** reference for C, including
  `ENTRYPOINTS.md` (`ffb387ba…`) and the two not-yet-existing `openrig_run` files
  (`exists:false`).
- **W-B3** `summary` is an object with a `blocks` counter (TASK's "summary=0" for the no-block
  case is satisfied as `summary.blocks == 0`); a scalar could not also carry the per-kind
  counts TASK asks for.

## 6. Reproduce

```bash
cd /home/a7067567g/下载/deepseek/deepseek-知识库/workflow-group
.venv/bin/python -m pytest tests -q                                   # 278 passed
.venv/bin/python scripts/doc_consistency.py --check                   # 0 errors
.venv/bin/python scripts/audit_managed_blocks.py --path ../AGENTS.md          # rc0
.venv/bin/python scripts/audit_managed_blocks.py --path ../AGENTS.md --strict # rc1
```
