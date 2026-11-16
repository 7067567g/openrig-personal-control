workflow:
  id: {{WORKFLOW_ID}}
  version: 1
  objective: >
    Produce an evidence-backed hypothesis matrix for every unresolved or
    semi-parsed byte family in the 0x903 staged watchface packages. The work is
    read-only with respect to all .bin files and must distinguish observed
    structure from inferred firmware semantics.
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
    tdo_dsh:
      preferred_targets: [exec-tdo-dsh@{{RIG_NAME_RAW}}]
    qa:
      preferred_targets: [assurance-qa@{{RIG_NAME_RAW}}]
    main:
      preferred_targets: [control-main@{{RIG_NAME_RAW}}]
  steps:
    - id: plan
      actor_role: pmo
      objective: >
        Read 未解析字节盘点.md and 分析输出/未解析字段假设/README.md. Split the
        unresolved field families into Branch A (header/table/base/type2/type3/
        type4/type7/type8) and Branch B (type9 layout/style/action/tail).
        Define the exact output paths, evidence format, confidence labels, and
        a per-field falsification experiment. Do not execute either branch.
      allowed_exits: [handoff, waiting, failed]
    - id: implement_opencode
      actor_role: tdo_opencode
      depends_on: [plan]
      objective: >
        Branch A. Analyze every unresolved container/header/table/base/type2/
        type3/type4/type7/type8 field. Compare the source watchface, the 简辞
        0x903 sample, the confirmed-safe package, and the staged packages.
        Produce reports/branch-A-container-header.md plus reproducible evidence
        under evidence/. Every row must list offset, length, observed examples,
        candidate meanings, supporting and contradicting evidence, confidence,
        and a distinguishing test.
      allowed_exits: [handoff, waiting, failed]
    - id: implement_dsh
      actor_role: tdo_dsh
      depends_on: [plan]
      objective: >
        Branch B. Analyze every unresolved type9 layout/style field, including
        +0x24 preview/icon slots, action/count words, 12-byte-ref reserved
        bytes, type9#0 trailing 40 21 00 00, and the 64-byte style-item fields.
        Compare all source style items with the 简辞 sample and staged packages.
        Produce reports/branch-B-type9.md plus reproducible evidence under
        evidence/. Every row must list candidate meanings, confidence, and a
        discriminating experimental check.
      allowed_exits: [handoff, waiting, failed]
    - id: qa_opencode
      actor_role: qa
      depends_on: [implement_opencode]
      objective: >
        Verify only Branch A. Re-run key evidence, check that every inventory
        row is covered, reject unsupported semantic names, and require a
        falsification test for each hypothesis. Record S1/S2 corrections.
      allowed_exits: [handoff, waiting, failed]
      next_hop:
        on: { failed: implement_opencode }
    - id: qa_dsh
      actor_role: qa
      depends_on: [implement_dsh]
      objective: >
        Verify only Branch B. Re-run differential checks, confirm all style-item
        field offsets against golden samples, reject overclaimed semantics, and
        require explicit uncertainty for 40 21 00 00. Record S1/S2 corrections.
      allowed_exits: [handoff, waiting, failed]
      next_hop:
        on: { failed: implement_dsh }
    - id: qa_join
      actor_role: qa
      depends_on: [qa_opencode, qa_dsh]
      objective: >
        Join both branch reports into reports/UNPARSED-HYPOTHESES.md. Build one
        row per unresolved field family with observed bytes, candidate meanings,
        evidence, confidence, falsification test, and risk. Explicitly separate
        facts from firmware-semantic hypotheses and list residual unknowns.
      allowed_exits: [handoff, waiting, failed]
    - id: close_round
      actor_role: main
      depends_on: [qa_join]
      objective: >
        Review the joined matrix against SPEC.md. Confirm every inventory field
        is covered, evidence is reproducible, no .bin was modified, and the next
        probe list is ranked. Close the workflow with the report path and any
        named blockers.
      allowed_exits: [done, failed]
  invariants:
    continuation_required: true
    preserve_lineage: true
    closure_required: true
    allowed_exits: [handoff, waiting, done, failed]
  loop_guards:
    max_hops: 10
    spawn_budget: 0
  closure:
    success: All inventory field families have evidence-backed hypotheses with confidence and falsification tests.
    degraded: A named blocker stops one branch and the residual field list is explicit.
    failed: No reviewable matrix or evidence was produced.
