# CLEANING-REPORT — openrig-personal-control

Package: `openrig-personal-control`
Update date: 2026-11-18
Scope: sync the sanitized public control package with the current S10 workflow-group scripts and tests.
Prior report: `CLEANING-REPORT-20261116.md` (archived copy of the previous `CLEANING-REPORT.md`).

## 1. Source provenance

| Item | Value |
| --- | --- |
| Source branch | `main` |
| Source HEAD | `a1f6eaa982ac9b92f9e360d9c0bab7496524a16d` |
| Source worktree | private `workflow-group` workspace, read-only during this update |
| Public clone base | `c805f9b7230b03d98ece2c32d3a2f40b459b5490` on `main` |
| Shipped runs | 3, unchanged: `openrig-p0-hard-constraints-20261116`, `openrig-p1-hard-constraints-20261116`, `openrig-p2-closure-20261116` |
| Package files | 623 files covered by `SHA256SUMS` and `PACKAGE-MANIFEST.json` (the two metadata files are not listed in themselves) |

The source worktree is a private knowledge-base subtree. Only its current `scripts/` and `tests/` content was read for this update; the public clone and this report are the only write targets. No source repository commit, staging, push, or deletion was performed.

## 2. Update contents

### 2.1 Scripts

`scripts/` now contains 28 files: **8 new**, **6 updated**, **14 unchanged**.

New scripts:

- `scripts/openrig_certify.py`
- `scripts/openrig_certify_s11b.py`
- `scripts/openrig_continuity.py`
- `scripts/openrig_findings.py`
- `scripts/openrig_gate.py`
- `scripts/openrig_lite.py`
- `scripts/openrig_manifest.py`
- `scripts/openrig_runtime_output.py`

Updated scripts:

- `scripts/contract_lock.py`
- `scripts/doc_consistency.py`
- `scripts/openrig_preflight.py`
- `scripts/openrig_run.py`
- `scripts/wf.py`
- `scripts/wf_close_lint.py`

### 2.2 Tests

`tests/` now contains 84 files: **54 new**, **6 updated**, **24 unchanged**.

Updated tests:

- `tests/conftest.py`
- `tests/test_doc_consistency.py`
- `tests/test_openrig_run.py`
- `tests/test_wf.py`
- `tests/test_wf_close_lint.py`
- `tests/test_workflow_rework.py`

New test content is grouped as follows:

- 13 top-level OpenRig test files (`tests/test_openrig_*.py`);
- 26 fixture files under `tests/fixtures/` (fake-rig, S9 continuity, supervisor simulation, and the packaged historical-findings policy used only by tests);
- 15 redteam files under `tests/redteam/` including the mutation-coverage driver and verdict reference notes.

The test-only historical-findings policy is packaged at `tests/fixtures/historical-findings-policy.json` so the public package can run its own tests without the private product checkout. The test conftest points the runtime policy environment at that packaged fixture when present.

### 2.3 Necessary package support updates

The current scripts/tests require the following non-root support data and consistency updates:

- `DOC-BUDGET.json` and `DOC-BUDGET.md` were added as the single documentation-budget source and short guide now required by `scripts/doc_consistency.py`.
- `roles/common-contract.md` and `roles/QA.md` received the minimal current budget pointers/rules.
- `templates/PROJECT.md`, `templates/DECISIONS.md`, and `templates/STATUS-Round-n.md` received their `doc_budget:` headers.
- `templates/baseline/REGISTRY.json`, the nine `templates/baseline/*/BASELINE.md` files, and `templates/contracts/FREEZE-NOTES.md` were advanced only from base-master `1.2.0` to `1.2.1`.
- `templates/contracts/LOCK.json` was regenerated from the final package worktree with `python3 scripts/contract_lock.py write --force`.
- `templates/specialized/openrig-workflow-master/templates/workflow.yaml.tpl`, `render_master.py`, `README.md`, `PREFLIGHT.md`, and `ENTRYPOINTS.md` received the current 12-hop/managed-supervisor requirements.
- `kickoff/openrig-s10-certification-20261116/CERT-MATRIX.json`,
  `kickoff/openrig-round1-postrun-20261117/run-manifest.schema.s11a.json`, and
  `kickoff/openrig-round1-postrun-20261117/runtime-output-evidence.schema.s11b.json`
  were added because them as read-only reference inputs in their tests.

These are the minimum necessary changes to keep the package's existing sanitized root documents, roles, and templates compatible with the synchronized scripts/tests. The package-specific root documents (`README*`, `SETUP.md`, `HISTORY-INDEX.md`, `RELEASE-NOTES.md`, `STACK.json`, `WORKFLOW.md`, `WORKFLOW-TAGS.md`, `workflow-tags.json`, `AGENTS.md`, `DESIGN.md`, `.gitignore`, `runtime/`, and the existing run set) were not replaced.

## 3. Include / exclude policy

Included:

- current `scripts/` and `tests/` content, minus the exclusions below;
- the existing three shipped run directories and their historical control evidence;
- existing sanitized package documents, roles, templates, runtime, kickoff, and burner content;
- the minimal support updates listed in §2.3.

Excluded from this update:

```text
.venv/  .r7-work/  .pytest_cache/  __pycache__/  *.pyc  .omo/  .cache/
drafts/  delegations/  reports/  tools/
all source runs/** (not copied)
runs/**/evidence/openrig-transcripts/**
runs/**/openrig/**
runs/**/.locks/**
*.sqlite*  *.db  *.log  *.tmp  .DS_Store  .env*
```

No raw transcript, SQLite database, live daemon state, OpenRig render tree, session capture, or local virtualenv was added. The existing three run directories were not modified by this update.

## 4. Hard-gate scans

All commands were run from the package root unless noted.

### 4.1 Raw session / database scan

```bash
find . -path './.git' -prune -o \
  \( -name 'events.jsonl' -o -path '*/transcripts/*' -o -path '*/sessions/*' \
     -o -name '*.sqlite*' -o -name '*.db' -o -name '.credentials' -o -name 'auth.json' \
     -o -path '*/.dsh/*' -o -path '*/secrets/*' -o -name 'id_rsa*' \
     -o -path './runs/*/openrig/*' -o -path './runs/*/evidence/openrig-transcripts/*' \) -print
```

Result: **0 hits**. Cache/artifact scan for `.venv`, `.pytest_cache`, `__pycache__`, `*.pyc`, `.omo`, `.cache`, `*.log`, and `*.tmp`: **0 hits**. Shipped run directory count: **3**.

### 4.2 Secret scan

Patterns covered bearer-like values, `api_key`/`secret`/`token`/`password` assignments, high-entropy key prefixes, private-key headers, and credential-store references:

```bash
rg -n -i --hidden --no-ignore -g '!.git/**' -g '!*.xlsx' -g '!*.zst' \
  -e 'bearer [A-Za-z0-9._-]{16,}' \
  -e '(api[_-]?key|secret|token|password)[[:space:]]*[:=][[:space:]]*[^[:space:]"'\'' ]{8,}' .
```

Additional key/credential patterns were scanned with:

```bash
rg -n --hidden -g '!.git/**' -g '!*.xlsx' -g '!*.zst' \
  -e 'sk-[A-Za-z0-9_-]{20,}' -e 'ghp_[A-Za-z0-9]{20,}' \
  -e 'AKIA[0-9A-Z]{16}' -e '-----BEGIN (RSA|OPENSSH|EC|PGP) PRIVATE KEY-----' \
  -e '\.credentials' -e 'auth\.json' .
```

Result: **48 broad-pattern matches in the package tree, all reviewed as false positives; 0 real credential values.** The matches are variable names (`token = ...`), redaction tests (`token=<redacted>`), synthetic fixture literals such as `test-token`, `sk-runtime-output-secret`, and documentation placeholders such as `Bearer <token>` or `OPENCODE_SERVER_PASSWORD=...`. The additional key-prefix/private-key scan produced 10 matches, all test prose or the two cleaning reports; no key material was present.

### 4.3 Home-path scan

```bash
rg -n --hidden -g '!.git/**' -e '/home/[A-Za-z0-9._-]+' .
```

Result: **528 occurrences in 172 files**. Classification:

| Area | Files | Status |
| --- | ---: | --- |
| `runs/**` | 123 | Historical run evidence; preserved unchanged |
| `templates/**` | 22 | Historical `/home/dev` examples/placeholders already present in the sanitized package |
| `kickoff/**` | 19 | Historical kickoff briefs; preserved |
| `docs/**` | 4 | Historical remediation case notes; preserved |
| `tests/**` | 1 | Synthetic `/tmp/.../home/state/opencode` test string, not a machine path |
| `EVOLUTION.md` | 1 | Historical example |
| `CLEANING-REPORT*.md` | 2 | Current and archived cleaning-report scan descriptions |

Exact local-user-path scan:

```bash
rg -n --hidden -g '!.git/**' '<MACHINE_HOME>' .
```

Result: 411 occurrences in 126 files, all in the preserved run evidence, historical kickoff/template examples, docs, or archived prior cleaning report. **No match was introduced in the synchronized scripts/tests or in this fresh report.** The public package does not use a local machine path as current configuration.

## 5. Validation

```bash
cd openrig-personal-control
python3 scripts/doc_consistency.py --check
# doc_consistency: 0 error(s), 0 warning(s)  rc=0

python3 scripts/contract_lock.py check
# [OK] ... workflow-group-base@1.2.1 + atomic-contract-set@1.0.0 (13 files)  rc=0

PYTHONDONTWRITEBYTECODE=1 "$WORKFLOW_GROUP_PYTHON" -m pytest -p no:cacheprovider tests -q
# 1129 passed, 21 skipped  rc=0
```

The 21 skips are offline/package-environment skips (live daemon, external product checkout, or optional runtime integration); they are not treated as passes. The final `PACKAGE-MANIFEST.json` records the current 623-file payload and `SHA256SUMS` covers every payload file except the two metadata files themselves.

## 6. Known gaps / residuals

1. Historical machine paths remain in the three shipped run directories, kickoff briefs, template examples, case docs, and the archived prior cleaning report. They are provenance/evidence, not current executable configuration; rewriting them would falsify the historical record.
2. The public clone has no live daemon and no private product checkout, so live lifecycle/model-backed probes are not run here. The package test suite is offline and records those skips.
3. The package-specific root documents were preserved in sanitized form. Only the minimal role/template/header changes required by the synchronized scripts and tests were applied.
4. `PACKAGE-MANIFEST.json` and `SHA256SUMS` intentionally do not hash themselves; every other package file is covered.

## 7. Pointer

The prior package cleaning report is archived verbatim as `CLEANING-REPORT-20261116.md`. It remains the authority for the original 2026-11-16 package provenance and its earlier exclusion review.
