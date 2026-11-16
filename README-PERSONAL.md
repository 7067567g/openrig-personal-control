# Workflow Group Personal Use

**Workflow Group Personal Use** is a personal, portable copy of the
*workflow-group* control plane: a documentation-as-interface way of running a
small team of agents (PMO / TDO / QA, optionally an independent SAFETY reviewer)
over a project, where every hand-off is a file rather than a chat message.

The group is driven by four documents per run — `PROJECT.md` (goal, scope,
acceptance), `DECISIONS.md` (settled boundaries), `SPEC.md` (contracts) and
`STATUS-Round-*.md` (round status) — plus a `reports/` directory that carries the
evidence each role produces. The main session delegates, collects results and
makes the calls; sub-agents only talk to each other through those files.

This repository is the **control plane**: runtime scripts, contracts, templates,
roles, tests, and a cleaned slice of run history. It does not include any agent
runtime; pair it with **OpenRig Personal Local**
(`https://github.com/7067567g/openrig-personal-local`), which supplies the seats
and the queue, or run it by hand from a single terminal.

## Quick start

```bash
# 1. Python environment + dev dependencies + a first test run
bash runtime/bootstrap.sh

# 2. Read the operating manual
less WORKFLOW.md
less roles/MAIN.md

# 3. Start a run
source .venv/bin/activate
python3 scripts/wf.py new-run my-run-20261116 --goal "one-line goal" --tdo 2
python3 scripts/wf.py brief --role pmo --run my-run-20261116
```

Full environment, credential and troubleshooting notes: **`SETUP.md`**.

## What is in the box

| Path | Contents |
| --- | --- |
| `WORKFLOW.md` | The workflow contract: rounds, roles, gates, closure semantics |
| `DESIGN.md`, `EVOLUTION.md` | Design rationale and how the method evolved |
| `WORKFLOW-TAGS.md` / `workflow-tags.json` | Tag vocabulary used by runs |
| `roles/` | Role manuals: MAIN, PMO, TDO, QA, SAFETY, advisor |
| `templates/` | Baseline and specialized run templates, plus contracts |
| `scripts/` | Python runtime: `wf.py`, preflight, evidence, gates, doc consistency |
| `tests/` | pytest suite for the control plane |
| `kickoff/`, `burner/` | Bootstrap material and disposable-run helpers |
| `docs/` | Method notes and cross-repository documentation map |
| `runs/` | Three recent OpenRig hard-constraints runs, control documents only |
| `HISTORY-INDEX.md` | Every run, where it lives, and what is excluded |
| `SETUP.md` | Install, environment variables, preflight, troubleshooting |

## Relationship to OpenRig

OpenRig is the *execution plane*: it owns seats, terminals, the durable queue and
the workflow runtime. This repository is the *method plane*: it owns the documents
that say what a round is, who may write what, and when a run may close.

They compose. A run directory here can be driven manually, or rendered into an
OpenRig workflow instance so the seats enforce the same contract.

## History

Only three runs ship in full here. The remaining 60 runs' control documents are
in the release evidence asset `openrig-personal-evidence-20261116.tar.zst`.
See `HISTORY-INDEX.md` for the complete table and the exclusion rules.

## Security

No secrets, API keys, raw agent transcripts, SQLite databases or home-directory
snapshots are included. `CLEANING-REPORT.md` records the scans that were run and
every allowlisted match.

## License

See `LICENSE` in this repository (Apache-2.0 for the OpenRig code line) and the
provenance note in `HISTORY-INDEX.md` for historical run content.
