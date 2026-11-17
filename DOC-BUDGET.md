# DOC-BUDGET — workflow-group documentation budget

> Single source of numbers: `DOC-BUDGET.json`. This page is only the short human view.
> Source decision: `runs/openrig-doc-budget-20261116/DECISIONS.md` D-004..D-010.

## Rule

Prose is budgeted by family; APPENDIX belongs to the same family. Put canonical detail in JSON/YAML and cite it by path. A fact appears once. A generated markdown view must carry `generated-from:` and stay <=4KB.

## Caps

| family | cap | mode |
|---|---:|---|
| plan | 6KB | soft |
| decision | 6KB | soft |
| qa (whole run) | 6KB | soft |
| final | 2KB | soft |
| status (per file) | 4KB | soft |
| project / spec | 8KB each | soft |
| generated view | 4KB | hard |
| other narrative | 4KB | soft |
| JSON/YAML/CSV + evidence | unlimited | machine-readable |

## Exceptions

- E1 frozen inputs / external source: cite path only.
- E2 JSON/YAML/CSV and `reports/evidence/**`: unlimited.
- E3 over-cap prose: declare `budget_exception: <reason>`; max 2 per run.
- E4 user-mandated content: mark `user-mandated` with provenance.

## Plan declaration

```text
doc_bytes: table=workflow-group/DOC-BUDGET.json; plan=actual/6144; qa=actual/6144; exceptions=none
```

## Enforcement

- `wf.py new-run` marks runs with `docBudgetPolicy: DOC-BUDGET-v1` and adds `doc_budget:` to PROJECT/DECISIONS/STATUS headers.
- Plan: `reports/00-plan.md` carries `doc_bytes:` and points to `DOC-BUDGET.json`.
- QA: records `doc_bytes: <family> <actual>/<cap>` plus `wc -c`.
- `wf_close_lint`: family caps, exceptions, generated-view checks.
- `doc_consistency`: validates this table, the role pointer, and this page's <=2KB size.

## Scope

Not retroactive: S6/S7/S8 remain historical evidence. Effective for new runs and S9 onward.
