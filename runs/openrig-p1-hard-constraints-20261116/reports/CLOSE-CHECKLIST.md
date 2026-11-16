# CLOSE CHECKLIST — openrig-p1-hard-constraints-20261116 (owned by MAIN)

Prepared 2026-11-15T17:06Z. Run only after `qa_final` hands off.

## 0. Preconditions

- `qa_final` (`qitem-20261115170024-c98f0ab1`) handed off; frontier = `close_round`.
- `reports/QA-VERDICT.md` exists and is PASS or PASS-WITH-WARN. FAIL returns to `impl_close_render`.
- Tree quiet: no writer active except MAIN.

## 1. Deliveries to count as proof (receipts, not row state)

| Packet | Evidence receipt sha256 |
| --- | --- |
| A | `ccc2fb09544820dc9fd29dc3a7950c66c0b77cd9bad7fb3d435b92f31a2caaaa` |
| B | `4ddb6c03a97867ee19d77c99feba3bac4cbe008f38ace72474e37d1d62dfb37d` |
| C | `887ccd4a9fafa70a1053f9536c30e23b6ea8b788bb0ec2495d61fe2b24809868` |
| D | `50a5e913db3a04c40abbe739f2586b831238de2721d75f9a108db9e14d8f1735` |

Row state is deliberately NOT evidence: A/B/C are `done` after the target repair, D is `handed-off`.

## 2. Re-run acceptance (all real rc, no pipes swallowing status)

```bash
cd /home/a7067567g/下载/deepseek/deepseek-知识库/workflow-group
.venv/bin/python -m pytest tests -q
.venv/bin/python scripts/doc_consistency.py --check
.venv/bin/python scripts/openrig_preflight.py --json --advisory
.venv/bin/python scripts/audit_managed_blocks.py --path /home/a7067567g/下载/deepseek/deepseek-知识库/AGENTS.md --json
.venv/bin/python scripts/openrig_run.py check --run-dir runs/openrig-p1-hard-constraints-20261116 --json --allow-daemon-down
.venv/bin/python scripts/openrig_run.py start --run-dir runs/openrig-p1-hard-constraints-20261116 --dry-run --json
.venv/bin/python scripts/verify_render.py --run-dir runs/openrig-p1-hard-constraints-20261116 --json
```

Expected: 310+ passed rc0; doc rc0; preflight advisory rc0 with `ok:false` (missing workspace/run-id is legitimate); audit rc0; check rc0 with `--allow-daemon-down`; dry-run rc0; verify_render `ok:false` BEFORE step 3.

## 3. Register render specializations (D-004)

Four rels, each with non-empty `--reason` stating: applied by the launch path 26 s after render
(00:47:58), coherent 3-seat linear specialization, intent per `SPEC.md` §9, recorded at close.

```bash
.venv/bin/python scripts/wf.py render-specialize openrig-p1-hard-constraints-20261116 \
  --path rig.yaml --reason '...' --json
# repeat for: workflow.yaml, guidance/team.md, OPENRIG-BRIDGE.json
```

Mechanics (confirmed against the implementation):
- writes `<run-dir>/openrig/render-specializations.json`; the file is NOT in `render-manifest.json`,
  so `verify_render` neither checks nor complains about it, and the run dir is excluded from baseline
  scope — list it in close evidence as delivered state;
- default `--specializations` path is exactly `<run-dir>/openrig/render-specializations.json`; if the
  flag is passed, point it at the same file or the entries silently do not apply;
- `--strict` stays rc0 only while all four entries match disk byte-for-byte. If any of the four is
  rewritten later (leftover process, late render), strict drops to rc1 naming the stale file. That is
  intended fail-closed behaviour, not a bug.

Then: `.venv/bin/python scripts/verify_render.py --run-dir runs/openrig-p1-hard-constraints-20261116 --strict`
→ expect rc0, four items `specialized:true`.

## 4. Close artefacts

- `reports/FINAL.md` — outcome, gate-by-gate status, known limitations (D-005/D-006), follow-ups
  (launch-path never calls render-specialize; same-seat `closure_target` projection; BASELINE-post stale).
- `reports/evidence/closeout.json` — per entry: path/bytes/sha256/command/rc/revision/reason.
- Update `DECISIONS.md` (D-004 executed) and `STATUS-Round-1.md`.
- `.venv/bin/python scripts/wf_close_lint.py --run openrig-p1-hard-constraints-20261116 --strict` → rc0.

## 5. Honest-claim boundaries

- Do not claim A/B scope is content-hash proven (D-006).
- Do not claim P2/R13/R14 implemented.
- Do not claim the product repo changed or was fixed.
- `verify_render` green is a recorded-specialization result, and the reason string says so.
- Product repo three values must still equal plan §2: HEAD `e932ae9…`, status `3b64cf9…`, diff `2cbcef6…`.
