# Specialized workflow for advisor-driven workflow-content refit.
# Linearized bounded-rework path:
#   plan -> implement_docs -> qa_docs
#        -> implement_templates -> qa_templates -> close_round
# QA failure returns only to the immediately preceding TDO step.
workflow:
  id: {{WORKFLOW_ID}}
  version: 1
  objective: >
    Optimize current workflow content from advisor reports through a bounded
    OpenRig run: reduce retired-term noise, add machine checks, demote
    issue-sync to a specialized adapter, verify, then hand off to MAIN.
  target:
    rig: {{RIG_NAME}}
  entry:
    role: pmo
  exception_routing:
    orchestrator_role: main
  coordination_terminal_turn_rule: hot_potato
  roles:
    pmo:
      preferred_targets: [control-pmo@{{RIG_NAME_RAW}}]
    tdo_opencode:
      preferred_targets: [exec-tdo-oc@{{RIG_NAME_RAW}}]
    qa:
      preferred_targets: [assurance-qa@{{RIG_NAME_RAW}}]
    main:
      preferred_targets: [control-main@{{RIG_NAME_RAW}}]
  steps:
    - id: plan
      actor_role: pmo
      objective: Read the three reports and fused register as read-only inputs; write reports/00-sources.md and the round plan; do not change product files.
      allowed_exits: [handoff, waiting, failed]
    - id: implement_docs
      actor_role: tdo_opencode
      depends_on: [plan]
      objective: Implement WS-1 retired-term de-duplication, add tests/test_doc_noise.py, bump workflow-group-base to 1.1.0 and re-sign LOCK; run focused tests.
      allowed_exits: [handoff, waiting, failed]
    - id: qa_docs
      actor_role: qa
      depends_on: [implement_docs]
      objective: Verify WS-1 only; a failed verdict returns that step to the TDO.
      allowed_exits: [handoff, waiting, failed]
      next_hop:
        on: { failed: implement_docs }
    - id: implement_templates
      actor_role: tdo_opencode
      depends_on: [qa_docs]
      objective: Implement WS-2 issue-sync baseline-to-specialized demotion and registry/map/test updates; preserve safe-cleanup and maturity.
      allowed_exits: [handoff, waiting, failed]
    - id: qa_templates
      actor_role: qa
      depends_on: [implement_templates]
      objective: Verify WS-2 and the combined evidence; a failed verdict returns that step to the TDO.
      allowed_exits: [handoff, waiting, failed]
      next_hop:
        on: { failed: implement_templates }
    - id: close_round
      actor_role: main
      depends_on: [qa_templates]
      objective: Review QA verdicts, finalize control-plane evidence, and close the round; archive and teardown happen only after this step.
      allowed_exits: [done, failed]
  invariants:
    continuation_required: true
    preserve_lineage: true
    closure_required: true
    allowed_exits: [handoff, waiting, done, failed]
  loop_guards:
    max_hops: 12
    spawn_budget: 0
  closure:
    success: Both content workstreams verified and main closeout recorded.
    degraded: Round stopped with a named blocker.
    failed: Round failed with evidence.
