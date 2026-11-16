# ADDENDUM — MAIN ruling on before-hashes and baseline comparison (2026-11-16)

Applied to Packet A and B evidence **after** their SUMMARY.md files were digest-bound in the
workflow closure. `SUMMARY.md` is therefore left untouched (its sha256 is the recorded
`--evidence-digest`); this file is the durable record of what changed and why.

## Ruling received from MAIN

1. Do not spend effort reconstructing lost pre-A bytes.
2. Record `n/a (pre-existing untracked, no snapshot)` for untracked files whose before state was
   never captured — P0 precedent:
   `runs/openrig-p0-hard-constraints-20261116/reports/evidence/impl_close_archive_render/changed-files.txt` line 3
   (`scripts/wf_close_lint.py | modify … | n/a (pre-existing untracked, no snapshot) | 38ca354d…`).
3. Never invent a before hash.
4. Prove scope with (a) baseline path-set diff, (b) mtime sweep, (c) targeted pytest.
5. The plan-time baseline (untracked entries as directories) and the refreshed capture
   (file-level, `-uall`) are **not line-comparable** — compare path **sets** only.

## What changed in the evidence

| artifact | change |
| --- | --- |
| `changed-files.txt` (A) | reformatted to the P0 `path \| action \| before \| after` shape; every never-captured before is now the literal `n/a (pre-existing untracked, no snapshot)`; created files use `-`. No reconstructed/inferred hash anywhere. `scripts/wf.py` is labelled `n/a (pre-existing dirty tracked file, no A-start snapshot)` because it is tracked-but-dirty, not untracked — same treatment, more precise wording. |
| `changed-files.txt` (B) | same policy, plus one genuine before hash recovered without inference: `.github/workflows/wf-validate.yml` was **clean** at the plan baseline (absent from `00-baseline.original.txt`), so its pre-B bytes are exactly the git HEAD blob → `sha256 = d84743bb…3bc`, 1017 bytes. |
| `path-set-diff.txt` (new, this packet) | path-set-only comparison of the plan baseline against the current tree. It treats an original `?? <dir>/` entry as a prefix, and states the resulting blind spot explicitly: a file added inside an already-untracked directory cannot be seen this way. |
| `scope.txt` (existing) | unchanged; remains the mtime sweep that covers the blind spot above. |

## Path-set result

- original baseline: 245 entries = 191 exact paths + 54 untracked-directory prefixes
- current tree: 1923 entries (this run's directory excluded)
- **new since baseline: 8 paths, 0 outside the TASK §0 whitelist**
  - `.github/workflows/wf-validate.yml`
  - `scripts/{snapshot_files.py, audit_managed_blocks.py, openrig_run.py}`
  - `tests/{test_snapshot_files.py, test_audit_managed_blocks.py, test_openrig_run.py, test_wf_render_specialize.py}`
- **disappeared: none**

All eight are exactly the files Packets A–D were authorised to add, which is the claim: no
out-of-scope path was introduced.

## Residual honesty

This comparison cannot see files added *inside* `workflow-group/scripts/` or `workflow-group/tests/`
(both were already untracked directories at baseline). Those are covered only by the mtime sweep in
`scope.txt` plus per-file `after` hashes in `changed-files.txt`. That is a weaker instrument than a
true before/after pair, and it is the reason `scripts/snapshot_files.py` (W4) exists — from Packet C
onward the before/after pair is genuine (`evidence/C/`, `evidence/D/`).
