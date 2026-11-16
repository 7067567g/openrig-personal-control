# Packet A · baseline refresh note (plan §2.1) — implemented with one documented deviation

## What plan §2.1 asked

1. copy `reports/evidence/00-baseline.txt` → `00-baseline.original.txt`; ✅ done
2. re-run `wf.py baseline openrig-p1-hard-constraints-20261116 --json`; ✅ done
3. new baseline is the comparison basis for scope diff; ⚠️ see deviation below
4. QA verifies the drift is limited to `AGENTS.md`. ✅ honoured (see scope.txt)

## Deviation (why the refresh is not a true pre-A baseline)

`workflow-group/scripts/**` is **untracked** in the KB repo:

```
$ git ls-files workflow-group/scripts
workflow-group/scripts/issues.py
workflow-group/scripts/wf.py
$ git status --porcelain workflow-group/scripts
 M workflow-group/scripts/issues.py
 M workflow-group/scripts/wf.py
?? workflow-group/scripts/openrig_preflight.py
?? workflow-group/scripts/required_components.py
...
```

Consequences:

- A pre-A capture would have required the pre-A working tree. No copy of the untracked
  files existed anywhere (no HEAD blob, no stash, no backup), so it could not be
  reconstructed after the first edit without fabricating state.
- Therefore the refreshed `00-baseline.txt/json` was captured **after** Packet A's edits.
  It is a valid **forward** reference for Packet B/C/D and QA, but it must **not** be
  read as proof that Packet A stayed in scope — that is what `scope.txt` and
  `changed-files.txt` are for.
- Do not use the new baseline to "prove" A. It contains A by construction.

## Additional instrument drift (discovered, not caused by A)

The plan-time baseline listed untracked entries as **directories**
(`?? workflow-group/templates/baseline/`), while the refreshed capture records one line
per file (`-uall` semantics). So the two baselines are **not line-comparable**; only
aggregate values and the mtime sweep are usable.

| field | plan-time (00-baseline.original.txt) | refreshed (00-baseline.txt) |
| --- | --- | --- |
| HEAD | `9fa8d27a95dba40c9f324f91497bc6754aa4b9ac` | same |
| status lines | 245 | 1917 (file-level) |
| status sha256 | `b4b8dca1caa3091e8fc56b902fe281e299b09f9fa0256ac64c00f6331951367e` | `63989671125d2cedbe3a70f5cd5aa01cc464bd61ac449f308657ff2b6bf0fccc` |
| diff sha256 | `cd0c7c3397b697dbb15df4c92c3fe69c27d25247e3015d157a9ba168f4c271db` | `cd3ed1af22d2f8d64571dd0eb0e0386ff6c4649f13a71b04c660eff091879d4e` |
| status count vs plan §2 | plan recorded "29 pre-existing dirty" for the **product** repo, not KB | — |

The `diff_sha256` change is expected: `AGENTS.md` drift (plan §2.1) + Packet A's
`scripts/wf.py` hunks (the only tracked file A touched).

## What replaces the missing pre-A hash

For Packet A's own scope claim:

1. `scope.txt` — mtime sweep of every file newer than the plan baseline, classified
   against the TASK §0 whitelist (product repo untouched: HEAD + status + diff all match
   plan §2).
2. `changed-files.txt` — exact `after` sha256/bytes for the six files A touched.
3. `negative-*.txt` / `positive-*.txt` — real rc, shas and JSON for each behaviour.

## Recommendation (for B/C/D and QA)

Packet A **is** the tool that prevents this (W4 `scripts/snapshot_files.py`). It did not
exist when A started, so A could not snapshot itself. From Packet B onward:

```bash
.venv/bin/python scripts/snapshot_files.py --out reports/evidence/B/before.json \
    --label before --path scripts/openrig_preflight.py --path scripts/wf.py ...
```

That makes every later packet's before/after hash a first-class artefact.
