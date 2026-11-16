# OpenRig Advisor Refit team

This rig executes one bounded workflow-content refit for `{{RUN_ID}}`.
Project root: `{{PROJECT_ROOT}}`.

## Authority

- The control plane (`runs/{{RUN_ID}}/PROJECT.md`, `DECISIONS.md`, `STATUS`, `ISSUES`) owns goals, scope, decisions and acceptance.
- OpenRig owns queue packets, ownership, workflow state, transcript and recovery.
- Do not copy OpenRig queue contents into new control documents; record evidence pointers.

## Working rules

- Read the workflow packet body. It contains the exact `rig workflow project ...` command for the current packet.
- Write only inside the run directory and the explicit write scope in `SPEC.md`.
- Do not start/stop the daemon or rig; MAIN owns lifecycle.
- Do not modify the three advisor reports or `runs/advisor-report-fusion-20261023/**`.
- Do not weaken `safe-cleanup` M3, force M2 clearing, or apply a 25% document-shrink target.
- Each step must report command, exit code and evidence path. Do not claim tests you did not run.
- On success, use the packet's `rig workflow project` command with `--exit handoff` and an `--evidence-ref` pointing to the actual file.
- On a real blocker, use `--exit waiting` or `--exit failed` and name the blocker.
- Never put provider keys or auth data into reports, queue bodies or transcripts.
