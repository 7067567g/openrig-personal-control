# -*- coding: utf-8 -*-
"""F-02 self-tests: state machine, guards, partial evidence, manifests."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

import continuity
import supervisor_sim
from continuity import ContinuityPlan
from fake_rig import Clock, FakeRig, IdFactory, Step
from guards import is_fixture
from observation import Sources, evaluate
from supervisor_sim import (
    COMMAND_GUARDS,
    GUARD_CODES,
    GUARD_REGISTRY,
    Context,
    Launch,
    Rejection,
    SeatStatus,
    SupervisorSim,
    authorize_direct,
    detect_context,
    guard_launch_ttl,
    guard_verb_unconsumed,
    make_context,
)

OBJECTIVE = "fixture objective"
CREATED_BY = "fixture@fixture"


# ---------------------------------------------------------------------------
# builders
# ---------------------------------------------------------------------------

def seats(*ids, token=True, session="present", node="node-1") -> tuple[SeatStatus, ...]:
    observation = evaluate(Sources(session=session, hook_present=True, hook_activity="working"))
    return tuple(
        SeatStatus(
            logicalId=seat_id,
            canonicalSessionName=f"sess-{seat_id}",
            nodeId=node,
            observation=observation if session is not None else None,
            resumeTokenPresent=token,
        )
        for seat_id in ids
    )


def context(tmp_path, *, seat_list=None, **flags) -> Context:
    return make_context(
        tmp_path / "run",
        seats=seat_list if seat_list is not None else seats("main"),
        **flags,
    )


def start_steps(ctx: Context) -> list[Step]:
    return [
        Step(
            argv=("rig", "daemon", "start", "--no-kernel", "--port", str(ctx.port)),
            repeat="consumed",
        ),
        Step(
            argv=(
                "rig",
                "up",
                str(ctx.rig_spec),
                "--cwd",
                str(ctx.project),
                "--yes",
            ),
            repeat="consumed",
        ),
        Step(argv=("rig", "workflow", "validate", "--rig", ctx.rig_name), repeat="consumed"),
        Step(
            argv=(
                "rig",
                "workflow",
                "instantiate",
                "--root-objective",
                OBJECTIVE,
                "--created-by",
                CREATED_BY,
                "--rig",
                ctx.rig_name,
            ),
            repeat="consumed",
        ),
    ]


def build(ctx: Context, script, make_runner, *, clock=None, ids=None) -> SupervisorSim:
    clock = clock or Clock()
    ids = ids or IdFactory()
    runner = make_runner(script, clock=clock, ids=ids)
    return SupervisorSim(ctx, runner=runner, clock=clock, ids=ids)


def complete_manifest() -> dict:
    return {
        "archiveStatus": "COMPLETE",
        "dshSession": None,
        "sessions": ["main", "tdo"],
        "required": {"tasks": True, "research": True, "report": True, "sessions": True, "dsh": False},
        "items": {"tasks": True, "research": True, "report": True, "sessions": True, "dsh": False},
    }


# ---------------------------------------------------------------------------
# check / next
# ---------------------------------------------------------------------------

def test_check_prepares_without_mutation_or_writes(tmp_path, make_runner):
    ctx = context(tmp_path)
    sim = build(ctx, [], make_runner)
    outcome = sim.check()
    assert outcome.ok is True
    assert sim.state == "PREPARED"
    assert sim.mutation_count == 0
    assert outcome.mutated is False
    assert not (ctx.run_dir / "reports").exists()


def test_next_returns_canonical_five_steps_without_writing(tmp_path, make_runner):
    ctx = context(tmp_path)
    sim = build(ctx, [], make_runner)
    outcome = sim.next()
    assert outcome.ok is True
    assert [step["name"] for step in outcome.payload["steps"]] == [
        "check",
        "start-dry-run",
        "start",
        "verify-render",
        "archive-gate",
    ]
    assert sim.mutation_count == 0
    assert not (ctx.run_dir / "reports").exists()


# ---------------------------------------------------------------------------
# start: happy path
# ---------------------------------------------------------------------------

def test_start_walks_the_contracted_chain(tmp_path, make_runner):
    ctx = context(tmp_path)
    sim = build(ctx, start_steps(ctx), make_runner)
    outcome = sim.start()
    assert outcome.ok is True, outcome.code
    assert outcome.rc == 0
    assert sim.state == "INSTANTIATED"
    assert sim.mutation_count == 4
    assert [call.argv[1:3] for call in sim.runner.calls] == [
        ("daemon", "start"),
        ("up", str(ctx.rig_spec)),
        ("workflow", "validate"),
        ("workflow", "instantiate"),
    ]
    assert outcome.payload["instanceId"].startswith("wf-")


def test_start_running_daemon_is_not_a_deadlock(tmp_path, make_runner):
    ctx = context(tmp_path, daemon_running=True, daemon_pid=111, healthz_pid=111)
    script = start_steps(ctx)[1:]  # no daemon-start call
    sim = build(ctx, script, make_runner)
    outcome = sim.start()
    assert outcome.ok is True
    assert sim.state == "INSTANTIATED"
    assert sim.runner.calls[0].argv[1] == "up"


def test_start_writes_a_schema_shaped_manifest(tmp_path, make_runner):
    ctx = context(tmp_path)
    sim = build(ctx, start_steps(ctx), make_runner)
    sim.start()
    manifest_path = ctx.run_dir / "reports" / "evidence" / "manifest" / "run-manifest.json"
    assert manifest_path.is_file()
    doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    for key in (
        "schemaVersion",
        "manifestId",
        "runId",
        "launchId",
        "intent",
        "generatedAt",
        "revision",
        "runContext",
        "envKeys",
        "inputs",
        "steps",
        "seats",
        "workflow",
        "archive",
        "outputs",
        "status",
    ):
        assert key in doc
    assert doc["schemaVersion"] == 1
    assert doc["status"] == "active"
    assert doc["intent"] == "fresh"
    assert doc["runContext"]["fixture"] is True
    assert doc["runContext"]["bridgeSha256"] == ctx.bridge_sha256
    assert doc["steps"][0]["stateBefore"] == "PREPARED"
    assert doc["steps"][0]["stateAfter"] == "DAEMON_READY"


def test_manifest_records_env_keys_only_never_values(tmp_path, make_runner):
    ctx = context(tmp_path)
    sim = build(ctx, start_steps(ctx), make_runner)
    sim.start(env={"API_TOKEN": "super-secret-value", "PLAIN": "x"})
    text = (ctx.run_dir / "reports" / "evidence" / "manifest" / "run-manifest.json").read_text(
        encoding="utf-8"
    )
    doc = json.loads(text)
    assert doc["envKeys"] == ["API_TOKEN", "PLAIN"]
    assert "super-secret-value" not in text


# ---------------------------------------------------------------------------
# start: pre-mutation refusals
# ---------------------------------------------------------------------------

def _assert_refusal(outcome, sim, code, *, expected_state="EMPTY"):
    assert outcome.ok is False
    assert outcome.rc == 2
    assert outcome.code == code
    assert outcome.mutated is False
    assert sim.mutation_count == 0
    assert sim.runner.calls == []
    assert sim.state == expected_state


def test_start_refuses_when_run_exists(tmp_path, make_runner):
    ctx = context(tmp_path, run_exists=True)
    sim = build(ctx, start_steps(ctx), make_runner)
    _assert_refusal(sim.start(), sim, "run_exists")


def test_start_refuses_when_rig_exists(tmp_path, make_runner):
    ctx = context(tmp_path, rig_exists=True)
    sim = build(ctx, start_steps(ctx), make_runner)
    _assert_refusal(sim.start(), sim, "rig_exists")


def test_start_refuses_bridge_sha_mismatch(tmp_path, make_runner):
    ctx = replace(context(tmp_path), expected_bridge_sha256="0" * 64)
    sim = build(ctx, start_steps(ctx), make_runner)
    _assert_refusal(sim.start(), sim, "bridge_invalid")


def test_start_refuses_home_mismatch(tmp_path, make_runner):
    ctx = replace(context(tmp_path), home_expected=tmp_path / "other-home")
    sim = build(ctx, start_steps(ctx), make_runner)
    _assert_refusal(sim.start(), sim, "run_home_mismatch")


def test_start_refuses_port_collision(tmp_path, make_runner):
    ctx = replace(context(tmp_path), port_owner_home=tmp_path / "other-home")
    sim = build(ctx, start_steps(ctx), make_runner)
    _assert_refusal(sim.start(), sim, "port_collision")


def test_start_refuses_daemon_identity_mismatch(tmp_path, make_runner):
    ctx = context(tmp_path, daemon_running=True, daemon_pid=1, healthz_pid=2)
    sim = build(ctx, start_steps(ctx), make_runner)
    _assert_refusal(sim.start(), sim, "daemon_identity_mismatch")


def test_start_refuses_workflow_duplicate(tmp_path, make_runner):
    ctx = context(tmp_path, workflow_exists=True)
    sim = build(ctx, start_steps(ctx), make_runner)
    _assert_refusal(sim.start(), sim, "workflow_duplicate")


def test_start_refuses_stale_launch(tmp_path, make_runner):
    ctx = context(tmp_path)
    sim = build(ctx, start_steps(ctx), make_runner)
    sim._write_launch(Launch("old-launch", "start", "2020-01-01T00:00:00Z"))
    _assert_refusal(sim.start(), sim, "stale_launch")


def test_start_refuses_reused_verb(tmp_path, make_runner):
    ctx = context(tmp_path)
    sim = build(ctx, start_steps(ctx), make_runner)
    sim._write_launch(
        Launch("old-launch", "start", Clock().peek(), consumed=("start",))
    )
    _assert_refusal(sim.start(), sim, "launch_verb_consumed")


def test_closed_launch_is_not_reused_for_a_new_start(tmp_path, make_runner):
    ctx = context(tmp_path)
    sim = build(ctx, start_steps(ctx), make_runner)
    sim._write_launch(
        Launch("old-launch", "start", Clock().peek(), phase="closed", consumed=("start",))
    )
    outcome = sim.start()
    assert outcome.ok is True
    assert sim.launch.launchId != "old-launch"


def test_check_output_has_ok_checks_next_and_degraded(tmp_path, make_runner):
    ctx = context(tmp_path)
    payload = build(ctx, [], make_runner).check().payload
    assert set(payload) == {"checks", "next", "degraded"}


# ---------------------------------------------------------------------------
# start: post-mutation failures write partial evidence
# ---------------------------------------------------------------------------

def test_up_failure_writes_partial_manifest_and_keeps_home(tmp_path, make_runner):
    ctx = context(tmp_path)
    script = [
        start_steps(ctx)[0],
        Step(argv=start_steps(ctx)[1].argv, repeat="consumed", rc=1, code="up_failed"),
    ]
    sim = build(ctx, script, make_runner)
    sentinel = ctx.home / "keep.txt"
    sentinel.write_text("owner data", encoding="utf-8")
    outcome = sim.start()
    assert outcome.ok is False
    assert outcome.rc == 1
    assert outcome.mutated is True
    assert sim.state == "DAEMON_READY"
    partial = ctx.run_dir / "reports" / "evidence" / "manifest" / "run-manifest.partial.json"
    payload = json.loads(partial.read_text(encoding="utf-8"))
    assert payload["partial"] is True
    assert payload["failed"]["stepId"] == "up"
    assert [step["stepId"] for step in payload["executed"]] == ["daemon-start"]
    assert payload["notExecuted"] == ["seats-ready", "workflow-validate", "workflow-instantiate"]
    assert sentinel.read_text(encoding="utf-8") == "owner data"


def test_seats_not_ready_writes_partial(tmp_path, make_runner):
    ctx = context(tmp_path, seat_list=seats("main", session="absent"))
    sim = build(ctx, start_steps(ctx)[:2], make_runner)
    outcome = sim.start()
    assert outcome.rc == 1
    assert outcome.code == "seats_not_ready"
    assert outcome.mutated is True
    partial = json.loads(
        (
            ctx.run_dir / "reports" / "evidence" / "manifest" / "run-manifest.partial.json"
        ).read_text(encoding="utf-8")
    )
    assert partial["notExecuted"] == ["workflow-validate", "workflow-instantiate"]


def test_validate_failure_writes_partial(tmp_path, make_runner):
    ctx = context(tmp_path)
    steps = start_steps(ctx)
    steps[2] = Step(argv=steps[2].argv, repeat="consumed", rc=2, code="validate_failed")
    sim = build(ctx, steps[:3], make_runner)
    outcome = sim.start()
    assert outcome.rc == 1
    assert outcome.mutated is True
    partial = json.loads(
        (
            ctx.run_dir / "reports" / "evidence" / "manifest" / "run-manifest.partial.json"
        ).read_text(encoding="utf-8")
    )
    assert partial["notExecuted"] == ["workflow-instantiate"]


def test_instantiate_failure_writes_partial(tmp_path, make_runner):
    ctx = context(tmp_path)
    steps = start_steps(ctx)
    steps[3] = Step(argv=steps[3].argv, repeat="consumed", rc=1, code="instantiate_failed")
    sim = build(ctx, steps, make_runner)
    outcome = sim.start()
    assert outcome.rc == 1
    assert sim.state == "VALIDATED"


# ---------------------------------------------------------------------------
# resume
# ---------------------------------------------------------------------------

def test_resume_with_valid_tokens_reaches_running(tmp_path, make_runner):
    ctx = context(tmp_path, seat_list=seats("main", "tdo", token=True))
    script = [Step(argv=("rig", "up", ctx.rig_name, "--existing"), repeat="consumed")]
    sim = build(ctx, script, make_runner)
    sim.state = "STOPPED"
    outcome = sim.resume()
    assert outcome.ok is True, outcome.code
    assert sim.state == "RUNNING"
    assert outcome.payload["decisionStatus"] == "allow"
    assert outcome.payload["actualOutcomes"] == {"main": "resumed", "tdo": "resumed"}
    plan_path = ctx.run_dir / "reports" / "evidence" / "manifest" / "continuity-plan.json"
    assert plan_path.is_file()
    assert json.loads(plan_path.read_text(encoding="utf-8"))["decisionStatus"] == "allow"


def test_resume_without_token_is_blocked_with_zero_mutation(tmp_path, make_runner):
    ctx = context(tmp_path, seat_list=seats("main", token="unknown"))
    sim = build(ctx, [], make_runner)
    sim.state = "STOPPED"
    outcome = sim.resume()
    assert outcome.ok is False
    assert outcome.rc == 2
    assert outcome.code == "continuity_blocked"
    assert sim.mutation_count == 0
    assert sim.runner.calls == []
    # a blocked decision writes no continuity plan and no launch record
    assert not (
        ctx.run_dir / "reports" / "evidence" / "manifest" / "continuity-plan.json"
    ).exists()
    assert not (ctx.home / "entry" / "launch.json").exists()
    plan = continuity.plan(
        [
            continuity.SeatFacts(
                logicalId="main",
                canonicalSessionName="sess-main",
                nodeId="node-1",
                resumeTokenPresent="unknown",
            )
        ]
    )
    assert plan.decisionStatus == "needs-human"
    assert plan.seats[0]["expectedAction"] == "awaiting-decision"


def test_resume_expected_resume_actual_fresh_is_mismatch_with_partial(tmp_path, make_runner):
    ctx = context(tmp_path, seat_list=seats("main", token=True))
    script = [Step(argv=("rig", "up", ctx.rig_name, "--existing"), repeat="consumed")]
    sim = build(ctx, script, make_runner)
    sim.state = "STOPPED"
    outcome = sim.resume(actual_outcomes={"main": "fresh-primed"})
    assert outcome.ok is False
    assert outcome.rc == 2
    assert outcome.code == "continuity_mismatch"
    assert outcome.mutated is True
    assert sim.state == "FAILED"
    partial = ctx.run_dir / "reports" / "evidence" / "manifest" / "run-manifest.partial.json"
    assert partial.is_file()


def test_unauthorized_fresh_with_explicit_auth_elsewhere(tmp_path, make_runner):
    ctx = context(tmp_path, seat_list=seats("main", "tdo", token=True))
    script = [Step(argv=("rig", "up", ctx.rig_name, "--existing"), repeat="consumed")]
    sim = build(ctx, script, make_runner)
    sim.state = "STOPPED"
    outcome = sim.resume(
        explicit_fresh=[("main", "authorized reason")],
        actual_outcomes={"main": "fresh-primed", "tdo": "fresh-primed"},
    )
    assert outcome.ok is False
    assert outcome.code == "fresh_not_authorized"
    assert outcome.mutated is True


def test_resume_node_identity_change_is_blocked(tmp_path, make_runner):
    ctx = context(tmp_path, seat_list=seats("main", token=True, node="new-node"))
    ctx = replace(ctx, seats=(replace(ctx.seats[0], plannedNodeId="old-node"),))
    sim = build(ctx, [], make_runner)
    sim.state = "STOPPED"
    outcome = sim.resume()
    assert outcome.ok is False
    assert outcome.code == "continuity_mismatch"
    assert sim.mutation_count == 0


def test_fresh_authorized_guard_reaches_its_false_branch(tmp_path, make_runner, monkeypatch):
    ctx = context(tmp_path, seat_list=seats("main", token=True))
    row = {
        "logicalId": "main",
        "canonicalSessionName": "sess-main",
        "nodeId": "node-1",
        "restorePolicy": "resume_if_possible",
        "resumeTokenPresent": True,
        "expectedAction": "fresh-primed",
        "actualOutcome": None,
        "freshAuthorized": False,
        "freshReason": None,
        "evidencePath": None,
    }
    crafted = ContinuityPlan("allow", [row], [], [], [])
    monkeypatch.setattr(continuity, "plan", lambda *args, **kwargs: crafted)
    script = [Step(argv=("rig", "up", ctx.rig_name, "--existing"), repeat="consumed")]
    sim = build(ctx, script, make_runner)
    sim.state = "STOPPED"
    outcome = sim.resume()
    assert outcome.ok is False
    assert outcome.code == "fresh_not_authorized"
    assert outcome.mutated is False
    assert sim.mutation_count == 0
    assert sim.runner.calls == []


def test_resume_from_wrong_state_is_illegal(tmp_path, make_runner):
    ctx = context(tmp_path)
    sim = build(ctx, [], make_runner)
    sim.state = "RUNNING"
    outcome = sim.resume()
    assert outcome.code == "illegal_transition"
    assert outcome.rc == 2
    assert sim.mutation_count == 0


# ---------------------------------------------------------------------------
# stop / archive
# ---------------------------------------------------------------------------

def test_stop_with_partial_archive_is_refused_before_down(tmp_path, make_runner):
    ctx = context(tmp_path, archive_manifest={"archiveStatus": "PARTIAL"})
    sim = build(ctx, [], make_runner)
    sim.state = "RUNNING"
    outcome = sim.stop()
    assert outcome.code == "archive_incomplete"
    assert outcome.rc == 2
    assert outcome.mutated is False
    assert sim.runner.calls == []


def test_stop_with_complete_archive_calls_down_and_keeps_home(tmp_path, make_runner):
    ctx = context(
        tmp_path,
        archive_manifest=complete_manifest(),
        daemon_running=True,
        daemon_pid=11,
        healthz_pid=11,
    )
    script = [
        Step(argv=("rig", "down", ctx.rig_name), repeat="consumed"),
        Step(argv=("rig", "daemon", "stop", "--home", str(ctx.home)), repeat="consumed"),
    ]
    sim = build(ctx, script, make_runner)
    sim.state = "RUNNING"
    sentinel = ctx.home / "db.sqlite.keep"
    sentinel.write_text("keep", encoding="utf-8")
    outcome = sim.stop()
    assert outcome.ok is True
    assert sim.state == "STOPPED"
    assert [call.argv[1] for call in sim.runner.calls] == ["down", "daemon"]
    assert sentinel.is_file()
    manifest = json.loads(
        (ctx.run_dir / "reports" / "evidence" / "manifest" / "run-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["status"] == "stopped"
    assert manifest["archive"]["archiveStatus"] == "COMPLETE"


def test_stop_with_orphans_reports_but_does_not_kill(tmp_path, make_runner):
    ctx = context(
        tmp_path,
        archive_manifest=complete_manifest(),
        orphans=("tmux:rig-main",),
    )
    script = [Step(argv=("rig", "down", ctx.rig_name), repeat="consumed")]
    sim = build(ctx, script, make_runner)
    sim.state = "RUNNING"
    outcome = sim.stop()
    assert outcome.ok is False
    assert outcome.rc == 1
    assert outcome.code == "orphan_after_stop"
    assert sim.state == "STOPPING"


def test_archive_after_stop_reaches_archived(tmp_path, make_runner):
    ctx = context(tmp_path, archive_manifest=complete_manifest())
    sim = build(ctx, [], make_runner)
    sim.state = "STOPPED"
    outcome = sim.archive_run()
    assert outcome.ok is True
    assert sim.state == "ARCHIVED"


# ---------------------------------------------------------------------------
# status (read-only) and launch rules
# ---------------------------------------------------------------------------

def test_status_is_read_only(tmp_path, make_runner):
    ctx = context(tmp_path)
    sim = build(ctx, start_steps(ctx), make_runner)
    sim.start()
    mutations = sim.mutation_count
    calls = len(sim.runner.calls)
    outcome = sim.status()
    assert outcome.ok is True
    assert sim.mutation_count == mutations
    assert len(sim.runner.calls) == calls


def test_status_reports_stale_launch_drift(tmp_path, make_runner):
    ctx = context(tmp_path)
    sim = build(ctx, [], make_runner)
    sim.launch = Launch("old", "start", "2020-01-01T00:00:00Z")
    outcome = sim.status()
    assert outcome.ok is False
    assert outcome.rc == 1
    assert {"code": "stale_launch"} in outcome.payload["drifts"]


def test_status_reports_orphans_and_daemon_identity(tmp_path, make_runner):
    ctx = context(
        tmp_path,
        orphans=("tmux:one",),
        daemon_running=True,
        daemon_pid=1,
        healthz_pid=2,
    )
    sim = build(ctx, [], make_runner)
    codes = {drift["code"] for drift in sim.status().payload["drifts"]}
    assert {"orphan_detected", "daemon_identity_mismatch"} <= codes


def test_launch_ttl_guards_start_and_resume_windows():
    start = Launch("l1", "start", "2026-01-01T00:00:00Z", ttlSeconds=1800)
    resume = Launch("l2", "resume", "2026-01-01T00:00:00Z", ttlSeconds=1200)
    assert guard_launch_ttl(start, "2026-01-01T00:29:00Z") is True
    assert guard_launch_ttl(start, "2026-01-01T00:31:00Z") is False
    assert guard_launch_ttl(resume, "2026-01-01T00:19:00Z") is True
    assert guard_launch_ttl(resume, "2026-01-01T00:21:00Z") is False


def test_verb_unconsumed_guard():
    launch = Launch("l1", "start", "2026-01-01T00:00:00Z", consumed=("start",))
    assert guard_verb_unconsumed(launch, "start") is False
    assert guard_verb_unconsumed(launch, "resume") is True


def test_external_launch_id_is_overridden_and_audited(tmp_path, make_runner):
    ctx = context(tmp_path)
    sim = build(ctx, start_steps(ctx), make_runner)
    outcome = sim.start(env={"OPENRIG_ENTRY_LAUNCH_ID": "forged-launch"})
    assert outcome.ok is True
    assert sim.launch.launchId != "forged-launch"
    assert sim.audit[0]["event"] == "provenance_overridden"
    assert sim.audit[0]["forged"] == "forged-launch"


# ---------------------------------------------------------------------------
# managed-run context / direct lifecycle verbs (RT-01)
# ---------------------------------------------------------------------------

def test_s1_direct_lifecycle_verb_is_denied(tmp_path):
    ctx = context(tmp_path)
    verdict = detect_context(ctx.run_dir)
    assert verdict.tier == "S1"
    audit: list[dict] = []
    result = authorize_direct(verdict, "up", audit)
    assert result.ok is False
    assert result.rc == 2
    assert result.code == "lifecycle_not_authorized"
    assert audit[0]["event"] == "deny_lifecycle_verb"


def test_s2_legacy_home_warns_but_does_not_deny(tmp_path):
    ctx = context(tmp_path, home=tmp_path / "openrig-workflow-legacy", write_marker=False)
    verdict = detect_context(ctx.run_dir)
    assert verdict.tier == "S2"
    audit: list[dict] = []
    result = authorize_direct(verdict, "up", audit)
    assert result.ok is True
    assert result.code is None
    assert result.warning == "legacy_home_warning"
    assert audit[0]["event"] == "allow_direct_warn"


def test_unmanaged_context_is_not_denied(tmp_path):
    verdict = detect_context(tmp_path / "nothing-here")
    assert verdict.tier == "unmanaged"
    assert "bridge_missing" in verdict.warnings
    assert authorize_direct(verdict, "up").ok is True


# ---------------------------------------------------------------------------
# mutation controls (RT-30 shape): a bypass must flip the negative test
# ---------------------------------------------------------------------------

def test_bridge_sha_negative_depends_on_its_guard(tmp_path, make_runner, monkeypatch):
    tampered = replace(context(tmp_path), expected_bridge_sha256="0" * 64)
    baseline = build(tampered, start_steps(tampered), make_runner)
    assert baseline.start().code == "bridge_invalid"

    monkeypatch.setattr(supervisor_sim, "guard_bridge_sha", lambda ctx: True)
    bypassed = build(tampered, start_steps(tampered), make_runner)
    outcome = bypassed.start()
    assert outcome.code != "bridge_invalid"
    assert outcome.ok is True


def test_archive_negative_depends_on_its_guard(tmp_path, make_runner, monkeypatch):
    ctx = context(tmp_path, archive_manifest={"archiveStatus": "PARTIAL"})
    baseline = build(ctx, [], make_runner)
    baseline.state = "RUNNING"
    assert baseline.stop().code == "archive_incomplete"

    monkeypatch.setattr(supervisor_sim, "guard_archive_complete", lambda gate: True)
    bypassed = build(
        ctx,
        [Step(argv=("rig", "down", ctx.rig_name), repeat="consumed")],
        make_runner,
    )
    bypassed.state = "RUNNING"
    outcome = bypassed.stop()
    assert outcome.code != "archive_incomplete"
    assert outcome.ok is True


def test_stale_launch_negative_depends_on_its_guard(tmp_path, make_runner, monkeypatch):
    ctx = context(tmp_path)
    baseline = build(ctx, start_steps(ctx), make_runner)
    baseline._write_launch(Launch("old-launch", "start", "2020-01-01T00:00:00Z"))
    assert baseline.start().code == "stale_launch"

    monkeypatch.setattr(supervisor_sim, "guard_launch_ttl", lambda launch, now, ttl=None: True)
    bypassed = build(ctx, start_steps(ctx), make_runner)
    outcome = bypassed.start()
    assert outcome.code != "stale_launch"
    assert outcome.ok is True


def test_seat_outcome_negative_depends_on_its_guard(tmp_path, make_runner, monkeypatch):
    ctx = context(tmp_path, seat_list=seats("main", token=True))
    script = [Step(argv=("rig", "up", ctx.rig_name, "--existing"), repeat="consumed")]
    baseline = build(ctx, script, make_runner)
    baseline.state = "STOPPED"
    assert baseline.resume(actual_outcomes={"main": "fresh-primed"}).code == "continuity_mismatch"

    monkeypatch.setattr(supervisor_sim, "guard_seat_outcome_match", lambda expected, actual: True)
    (ctx.home / "entry" / "launch.json").unlink()
    bypassed = build(ctx, script, make_runner)
    bypassed.state = "STOPPED"
    outcome = bypassed.resume(actual_outcomes={"main": "fresh-primed"})
    assert outcome.code != "continuity_mismatch"
    assert outcome.ok is True


def test_command_guards_is_a_live_coverage_map():
    covered: set[str] = set()
    for command, names in COMMAND_GUARDS.items():
        assert set(names) <= set(GUARD_REGISTRY), command
        covered |= set(names)
    assert covered == set(GUARD_REGISTRY)


def test_guard_registry_covers_the_declared_code_table():
    assert set(GUARD_CODES) == set(GUARD_REGISTRY)
