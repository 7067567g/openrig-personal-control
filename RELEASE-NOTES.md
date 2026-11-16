# Workflow Group Personal Use

**Release tag:** `v2026.11.16`
**Release date:** 2026-11-16

A personal, portable copy of the workflow-group control plane: a
documentation-as-interface method for running a small team of agents
(PMO / TDO / QA, optionally an independent SAFETY reviewer) over a project, where
every hand-off is a file rather than a chat message.

## What is inside

| Area | Contents |
| --- | --- |
| `WORKFLOW.md` | The workflow contract: rounds, roles, gates, closure semantics |
| `DESIGN.md`, `EVOLUTION.md`, `EXAMPLE.md` | Design rationale, history and a worked example |
| `WORKFLOW-TAGS.md` / `workflow-tags.json` | Tag vocabulary used by runs |
| `roles/` | Role manuals: MAIN, PMO, TDO, QA, SAFETY, advisor |
| `templates/` | Baseline, contract and specialized run templates |
| `scripts/` | Python runtime: `wf.py`, preflight, evidence, gates, doc consistency |
| `tests/` | pytest suite for the control plane |
| `kickoff/`, `burner/`, `docs/` | Bootstrap material, disposable-run helpers, method notes |
| `runs/` | Three recent OpenRig hard-constraints runs, control documents only |
| `runtime/bootstrap.sh`, `SETUP.md` | Environment bootstrap and setup guide |
| `HISTORY-INDEX.md` | Every run, where it lives, and what is excluded |

One release asset accompanies this tag:

- `openrig-personal-evidence-20261116.tar.zst` — cleaned control documents for the
  other 60 runs plus the OpenRig run-archive index.

## Quick start

```bash
bash runtime/bootstrap.sh
source .venv/bin/activate
python3 scripts/wf.py new-run my-run-20261116 --goal "one-line goal" --tdo 2
```

Requirements: Python 3.10+; `pytest` and `openpyxl` (installed by the bootstrap).

Environment variables, preflight, credential handling and troubleshooting are in
**`SETUP.md`**.

## Provenance

- Upstream: the workflow-group method as developed in a personal knowledge base.
- This repository is an exported subtree; it has no independent upstream git
  history, so the release starts from a single first commit.
- Source snapshot: 2026-11-16. The publishing run itself
  (`openrig-personal-publish-20261116`) is excluded from the shipped history.
- `HISTORY-INDEX.md` maps all 63 historical runs to their location, and
  `PACKAGE-MANIFEST.json` records file count, bytes, largest files and exclusions.

## Security

This repository contains **no** secrets, API keys, credentials, raw agent
transcripts or sessions, SQLite databases, or home-directory snapshots.

- Three runs ship in full; the remaining 60 exist only as cleaned control
  documents in the evidence asset.
- `runs/**/openrig/`, `.locks/`, transcripts and databases are excluded by
  construction.
- `CLEANING-REPORT.md` documents the secret scan, the raw-session scan and the
  machine-path scan, and justifies every allowlisted match individually.
