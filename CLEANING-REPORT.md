# CLEANING-REPORT — workflow-group-personal-use

Package: `workflow-group-personal-use`
Step: `stage_packages` (workflow run `openrig-personal-publish-20261116`)
Date: 2026-11-16
Executed by: `exec-tdo-oc@openrig-personal-publish-20261116`
Source: personal `workflow-group` workspace (subtree of a private knowledge base),
HEAD `9fa8d27a95dba40c9f324f91497bc6754aa4b9ac`.

## 1. Include / exclude

| Item | Value |
| --- | --- |
| Staging root | `workflow-group-personal-use/` |
| Files staged | 553 (see `PACKAGE-MANIFEST.json`) |
| Bytes staged | 4,162,121 (3.97 MiB) |
| Runs shipped in full | 3 (`openrig-p0/p1/p2-…-20261116`) |
| Runs excluded | 60 (available in the evidence bundle) |
| Raw transcript directories in source `runs/` | 19 |
| `events.jsonl` files in source `runs/` | 7 |
| SQLite databases in source `runs/` | 0 |

Included: `scripts/`, `tests/`, `templates/` (baseline + contracts + specialized),
`roles/`, `kickoff/`, `burner/`, `docs/`, the three runs, the top-level documents
(`README.md`, `WORKFLOW.md`, `DESIGN.md`, `AGENTS.md`, `WORKFLOW-TAGS.md`,
`EXAMPLE.md`, `EVOLUTION.md`, `requirements-dev.txt`, `workflow-tags.json`) plus
the new `README-PERSONAL.md`, `SETUP.md`, `HISTORY-INDEX.md`, `runtime/bootstrap.sh`,
`.gitignore`.

Excluded by pattern:

```text
.venv/  .r7-work/  .pytest_cache/  __pycache__/  *.pyc  .omo/  .cache/
drafts/  delegations/  reports/  tools/
60 older runs (listed in HISTORY-INDEX.md, served by the evidence asset)
runs/**/openrig/**                      # render output with machine paths
runs/**/evidence/openrig-transcripts/** # raw transcripts
runs/**/.locks/**
*.sqlite*  *.db  *.log  *.tmp  .DS_Store  .env*
```

Rationale:

- `runs/**/openrig/` is run-time render state (rig/workflow YAML, bridge JSON,
  guidance copies) that embeds absolute paths and is not a historical fact.
- `drafts/`, `delegations/`, `reports/`, `tools/` at workspace level are personal
  scratch space and workspace-level tooling, not the control plane.
- `.venv/` is builder-bound; `SETUP.md` recreates it.

## 2. Hard gate — secret scan

### 2.0 Scan scope (including packaging documents)

Every scan below covers the **whole package tree**, which explicitly includes the
documents added at package time:

`README-PERSONAL.md`, `SETUP.md`, `HISTORY-INDEX.md`, `RELEASE-NOTES.md`,
`runtime/bootstrap.sh`, `CLEANING-REPORT.md`, `PACKAGE-MANIFEST.json`,
`SHA256SUMS`, `.gitignore`.

`RELEASE-NOTES.md` (the `--notes-file` for the `v2026.11.16` GitHub release) was
also checked by hand: it contains the product name, the tag, the release date,
the contents list, a quick-start pointer to `SETUP.md`, provenance without any
local absolute path, and the security statement referring back to this report. It
is counted in `PACKAGE-MANIFEST.json` and listed in `SHA256SUMS`.

Same command as the sibling package (see its §2). Result across the three
packages: **89 matches in 37 files, all individually reviewed as false positives**;
**zero matches inside this package** except the shared `SHA256SUMS` artefact.

```bash
rg -n --hidden --no-ignore -g '!.git/**' -g '!*.zst' -g '!*.xlsx' -e "$PAT" \
  workflow-group-personal-use
```

Result: **no output.**

Word-level review over the staged package:

```bash
rg -n -i --hidden --no-ignore -g '!.git/**' \
  -e 'bearer [A-Za-z0-9._-]{16,}' \
  -e '(api[_-]?key|secret|token|password)[[:space:]]*[:=][[:space:]]*[^[:space:]"'"'"']{8,}' \
  workflow-group-personal-use
```

Result: **4 files, 4 matches — all documentation or code, none a value.**

| File:line | Match | Classification |
| --- | --- | --- |
| `WORKFLOW.md:294` | `export OPENCODE_SERVER_PASSWORD=...` | (a) documentation placeholder (`...`) |
| `scripts/wf.py:1027` | `f"opencode:{pw}"` | code that builds a Basic Auth header from a caller-supplied variable — no literal |
| `templates/.../ARCHITECTURE.md:194` | `sk-<token>`, `Bearer <token>` | (a) description of the scanner's own patterns |
| `templates/.../validation/v1.1.0/TDO-DSH-REPORT.md:19` | table row text | (a) report prose |

Broader `token|password|secret|api_key` word search matches many files, but every
hit is a variable name (`token = …`), a doc placeholder, or a test fixture value
such as `test-token`, `dummy`, `example.invalid`. **Class (c) real credentials: 0.**

### 2.1 Credential-store read — removed in round 2 (TASK §6 review)

TASK §6 requires hits on `.credentials`-class references to be reviewed by hand.
One existed and was missed in round 1:

| File | Round-1 state | Round-2 action |
| --- | --- | --- |
| `burner/signaldeck-run.sh` | lines 5-6 exported `DEEPSEEK_API_KEY` / `OPENCODE_API_KEY` by parsing the user's credential store with an inline `python3 -c` **inside a public, executable script** | **removed**; the script now asserts `: "${DEEPSEEK_API_KEY:?export DEEPSEEK_API_KEY before running this script}"` and reads no file |

- No key **value** ever shipped (G1 stayed green throughout).
- What did leak was *layout*: the store path, its YAML shape and the key names —
  reconnaissance value on a compromised machine, and an avoidable public example.
- Verification: `grep -rn 'credentials\|\.bashrc' workflow-group-personal-use` now
  returns nothing outside this report.

Related, same round: `burner/run_queue.py` no longer falls back to scraping the
user's shell config for the key. `load_key()` reads the environment only, and the
docstring and error message that advertised the old fallback were rewritten.
The unused `import re` was dropped.

## 3. Hard gate — raw session / SQLite / home-snapshot scan

```bash
find workflow-group-personal-use \
  \( -name 'events.jsonl' -o -path '*/transcripts/*' -o -path '*/sessions/*' \
     -o -name '*.sqlite*' -o -name '*.db' -o -name '.credentials' -o -name 'auth.json' \
     -o -path '*/.dsh/*' -o -path '*/secrets/*' -o -name 'id_rsa*' \) -print
```

Result: **no output (0 hits).** Verified additionally that no `runs/**/openrig/`,
`runs/**/evidence/openrig-transcripts/`, `.venv/` or non-p0/p1/p2 run exists in
the package.

## 4. Local absolute paths

Hard gate (must be zero) over `README-PERSONAL.md`, `SETUP.md`, `RELEASE-NOTES.md`,
`runtime/**`, `PACKAGE-MANIFEST.json`:

```bash
rg -n '/home/[A-Za-z0-9._-]+' workflow-group-personal-use/{README-PERSONAL.md,SETUP.md,RELEASE-NOTES.md,runtime}
```

Result: **no output.**

### 4.1 Executable scripts — must contain no machine path

`00-plan.md` §4.4 forbids machine paths in executable scripts. Two scripts and one
data prompt originally violated this; all are now path-free.

```bash
rg -n '/home/[A-Za-z0-9._-]+' workflow-group-personal-use/burner workflow-group-personal-use/scripts
```

Result: **no output.**

| File | Was | Now |
| --- | --- | --- |
| `burner/signaldeck-run.sh` | 4 machine paths (`cd <abs>`, `PATH=<abs>`, two `.credentials.yaml` reads) | `WG` resolved from `${BASH_SOURCE[0]}`; key required from the environment via `: "${DEEPSEEK_API_KEY:?...}"`; no file read |
| `burner/signaldeck-heartbeat.sh` | `WG="/home/<user>/…/workflow-group"` | `WG` resolved from `${BASH_SOURCE[0]}`; run id from `$1` or `BURNER_RUN_ID` |
| `burner/signaldeck-prompt.txt` | line 2 stated an absolute working directory | `<WORKFLOW_GROUP_DIR>` placeholder |
| `scripts/openrig_preflight.py` | line 37 `DEFAULT_DASHBOARD` hardcoded a dashboard path | env-driven (see §4.2) |

### 4.2 `scripts/openrig_preflight.py` monitor target

Resolution order, most specific first — no machine path anywhere:

1. `YUEYUE_MONITOR_TARGETS` / `OPENRIG_MONITOR_TARGETS` — explicit `target.json` path
2. `OPENRIG_DASHBOARD` / `YUEYUE_DASHBOARD` — directory, target is `<dir>/target.json`
3. fallback `~/.openrig/monitor/target.json`

The chosen source is reported as `targetFileSource` in the injection result
(`env:YUEYUE_MONITOR_TARGETS` / `env:dashboard` / `default`), so an unconfigured
fallback is visible instead of silent. Existing `YUEYUE_MONITOR_TARGETS` behaviour
is unchanged, and `tests/test_openrig_preflight.py` passes (7/7).

### 4.3 Rewritten template paths

| File | Original | Now |
| --- | --- | --- |
| `templates/specialized/yueyue-governance/PROJECT.md` | `/home/<user>/…/月月bot` (×3) | `<DS_ROOT>/月月bot/…` |
| `templates/specialized/wechat-yueyue-redesign/PROJECT.md` | `/home/<user>/…/月月bot` | `<DS_ROOT>/月月bot` |
| `templates/specialized/signaldeck-refactor/SPEC.md` | `/home/<user>/…/deepseek-项目/10-signaldeck/**` | `<DS_ROOT>/deepseek-项目/10-signaldeck/**` |

### 4.4 Historical paths retained — measured, not estimated

```bash
grep -rlE '/home/[A-Za-z0-9._-]+' . | wc -l      # 169 files
grep -rnE '/home/[A-Za-z0-9._-]+' . | wc -l      # 523 occurrences
```

| Directory | Files | Lines | Nature |
| --- | ---: | ---: | --- |
| `runs/**` | 123 | 407 | Historical run evidence (logs, `file:line` citations). Rewriting would falsify the record. |
| `templates/**` | 22 | 47 | Template background and `render_master.py` example placeholders (`/home/dev`, not this machine) |
| `kickoff/**` | 19 | 60 | Historical kickoff briefs, e.g. `kickoff/signaldeck-runtime-verify.md:8,10,19` (`/home/dev/Desktop/…`). Retained per `00-plan.md` §4.4; listed here explicitly so it is a recorded allowance, not an oversight. |
| `docs/**` | 4 | 8 | Historical case documents |
| `EVOLUTION.md` | 1 | 1 | Illustrative example in method history |
| `burner/**` | 0 | 0 | **Now clean** — see §4.1 |

`HISTORY-INDEX.md` states explicitly that historical paths are not current
configuration.

### 4.5 Machine identifiers in `workflow-tags.json`

`workflow-tags.json` contains 7 occurrences of the archiving machine id
(`<hostname>-<user>`) inside historical archive paths. These are provenance
identifiers, not credentials and not paths that any code resolves. They are
retained so the tag index stays consistent with the archived records; this entry
is the explicit record QA asked for. A consumer that needs a scrubbed view can run
`s/<hostname>-<user>/<MACHINE>/g` without ambiguity.

## 5. Large files

```bash
find workflow-group-personal-use -type f -size +20M -printf '%s %p\n'
```

Result: **no output.** Largest file is `workflow-tags.json` (~148 KB).

## 6. Executable bits

```bash
find workflow-group-personal-use/runtime -name '*.sh' ! -perm -u+x -print
```

Result: **no output.** `runtime/bootstrap.sh` and `scripts/evidence_run.sh` are
executable; other source scripts keep their original modes.

## 7. Known gaps

1. This subtree has no independent git history — it is exported from a larger
   private knowledge base. The new repository therefore starts with a single
   first commit; `HISTORY-INDEX.md` records provenance.
2. 60 older runs are not in this repository. Their control documents are in
   `openrig-personal-evidence-20261116.tar.zst`; the `HISTORY-INDEX.md` table maps
   every run to its location.
3. `.run-meta.json` files exist for only 2 of the 3 shipped runs (the p0 run has
   none in the source tree). They were not fabricated.
4. Historical absolute paths remain in run evidence logs by design — they are
   evidence, and rewriting them would falsify the record.

### 7.1 `WORKFLOW-TAGS.md` canonical count corrected (round 2)

The shipped subtree contains 3 canonical runs (all older runs live in the evidence
asset), while `WORKFLOW-TAGS.md` declared the source workspace's 63. That made
`scripts/doc_consistency.py --check` fail — which meant `runtime/bootstrap.sh`
would fail on a fresh clone, before any user did anything wrong.

Fixed by declaring `canonical=3` (matching `runs/`) and adding a delivery-boundary
note stating that 3 of the original 63 runs ship here and the other 60 are in
`openrig-personal-evidence-20261116.tar.zst`. Verified:

```bash
python3 scripts/doc_consistency.py --check   # 0 error(s), 0 warning(s)
python3 -m pytest tests -q                   # 321 passed, 8 skipped
```

### 7.2 `requirements-dev.txt` was incomplete — false green caught by round 3

Round 2 reported "321 passed / 8 skipped". That result was produced in an
environment that already had PyYAML installed. `tests/test_workflow_rework.py:35`
imports `yaml` at module level, but `requirements-dev.txt` did not declare it, so
`runtime/bootstrap.sh` on a clean copy failed at pytest **collection**:

```text
E   ModuleNotFoundError: No module named 'yaml'
```

This is the most dangerous class of defect in this package: every gate we ran
(G1-G6) was green, the suite was green *on my machine*, and the install path was
still broken for every other machine. Fixed:

| File | Change |
| --- | --- |
| `requirements-dev.txt` | added `PyYAML>=6,<7`; documented `psutil` as optional (its call site in `wf.py` is wrapped in try/except and degrades to `None`) |
| `SETUP.md` | added PyYAML to the requirements table and a note that any `ModuleNotFoundError` during collection means the declaration list is incomplete |

Verification, in a **clean copy** at `/tmp/opencode/p2-bootstrap-check` with no
pre-existing venv:

```bash
cp -a workflow-group-personal-use /tmp/opencode/p2-bootstrap-check
cd /tmp/opencode/p2-bootstrap-check && rm -rf .venv
bash runtime/bootstrap.sh      # rc=0
# venv built solely from requirements-dev.txt
# doc_consistency: 0 error(s), 0 warning(s)
# 321 passed, 8 skipped
```

Dependency audit performed to catch siblings of this defect: all top-level
imports across `scripts/` and `tests/` were enumerated and diffed against the
stdlib and the local packages. Third-party imports found: `pytest`, `openpyxl`,
`yaml` (now declared) and `psutil` (optional, scored as such).

## 8. Provenance

| Field | Value |
| --- | --- |
| Source workspace | personal `workflow-group` (private knowledge-base subtree) |
| Source HEAD | `9fa8d27a95dba40c9f324f91497bc6754aa4b9ac` |
| Staged | 2026-11-16 |
| Staged by | `exec-tdo-oc@openrig-personal-publish-20261116` |
