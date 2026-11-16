version: "0.2"
name: {{RIG_NAME}}
summary: >
  Workflow content refit: 4-seat managed-isolated rig. control/main+pmo,
  exec/tdo, assurance/qa. Generated for {{RUN_ID}} from
  openrig-advisor-refit.

pods:
  - id: control
    label: Control
    members:
      - id: main
        agent_ref: "local:./agents/worker"
        profile: default
        runtime: opencode
        role: main
        cwd: {{PROJECT_ROOT_YAML}}
        model: {{OPENCODE_MODEL_YAML}}
      - id: pmo
        agent_ref: "local:./agents/worker"
        profile: default
        runtime: opencode
        role: pmo
        cwd: {{PROJECT_ROOT_YAML}}
        model: {{OPENCODE_MODEL_YAML}}
    edges:
      - kind: delegates_to
        from: main
        to: pmo

  - id: exec
    label: Execution
    members:
      - id: tdo-oc
        agent_ref: "local:./agents/worker"
        profile: default
        runtime: opencode
        role: tdo
        cwd: {{PROJECT_ROOT_YAML}}
        model: {{OPENCODE_MODEL_YAML}}
    edges: []

  - id: assurance
    label: Assurance
    members:
      - id: qa
        agent_ref: "local:./agents/worker"
        profile: default
        runtime: opencode
        role: qa
        cwd: {{PROJECT_ROOT_YAML}}
        model: {{OPENCODE_MODEL_YAML}}
    edges: []

edges:
  - kind: delegates_to
    from: control.pmo
    to: exec.tdo-oc
  - kind: can_observe
    from: assurance.qa
    to: exec.tdo-oc

startup:
  files:
    - path: guidance/team.md
      delivery_hint: guidance_merge
      required: true
