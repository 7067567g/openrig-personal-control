# -*- coding: utf-8 -*-
"""RT-05..RT-08 — a fresh start must never masquerade as a resume.

Negatives assert the refusal code, rc and zero/failed mutation state; each has
a paired control that reaches ``resumed``/``allow``.
"""

from __future__ import annotations

import json

from continuity import SeatFacts, plan as continuity_plan
from observation import Sources, evaluate

from helpers import context, seats, up_existing, build


# ---------------------------------------------------------------------------
# RT-05 — no token and no --fresh: awaiting-decision, zero mutation
# ---------------------------------------------------------------------------

def test_rt05_resume_without_token_is_blocked_before_mutation(tmp_path):
    ctx = context(tmp_path, seat_list=seats("main", token="unknown"))
    sim = build(ctx, [up_existing(ctx)], base=tmp_path)
    sim.state = "STOPPED"

    outcome = sim.resume()
    assert outcome.ok is False
    assert outcome.rc == 2
    assert outcome.code == "continuity_blocked"
    assert sim.mutation_count == 0
    assert sim.runner.calls == []
    assert not (
        ctx.run_dir / "reports" / "evidence" / "manifest" / "continuity-plan.json"
    ).exists()
    assert not (ctx.home / "entry" / "launch.json").exists()


def test_rt05_control_valid_token_reaches_resumed(tmp_path):
    ctx = context(tmp_path, seat_list=seats("main", token=True))
    sim = build(ctx, [up_existing(ctx)], base=tmp_path)
    sim.state = "STOPPED"

    outcome = sim.resume()
    assert outcome.ok is True, outcome.code
    assert sim.state == "RUNNING"
    assert outcome.payload["decisionStatus"] == "allow"
    assert outcome.payload["actualOutcomes"] == {"main": "resumed"}


# ---------------------------------------------------------------------------
# RT-06 — expected resume, actual fresh: mismatch, partial, no instantiate
# ---------------------------------------------------------------------------

def test_rt06_actual_fresh_over_resume_is_a_mismatch_with_partial(tmp_path):
    ctx = context(tmp_path, seat_list=seats("main", token=True))
    sim = build(ctx, [up_existing(ctx)], base=tmp_path)
    sim.state = "STOPPED"

    outcome = sim.resume(actual_outcomes={"main": "fresh-primed"})
    assert outcome.ok is False
    assert outcome.rc == 2
    assert outcome.code == "continuity_mismatch"
    assert outcome.mutated is True
    assert sim.state == "FAILED"
    partial = (
        ctx.run_dir / "reports" / "evidence" / "manifest" / "run-manifest.partial.json"
    )
    assert partial.is_file()
    payload = json.loads(partial.read_text(encoding="utf-8"))
    assert payload["partial"] is True
    assert payload["failed"]["stepId"] == "up-existing"
    assert not (
        ctx.run_dir / "reports" / "evidence" / "manifest" / "run-manifest.json"
    ).is_file()


def test_rt06_control_matching_resume_outcome_proceeds(tmp_path):
    ctx = context(tmp_path, seat_list=seats("main", token=True))
    sim = build(ctx, [up_existing(ctx)], base=tmp_path)
    sim.state = "STOPPED"

    outcome = sim.resume(actual_outcomes={"main": "resumed"})
    assert outcome.ok is True, outcome.code
    assert sim.state == "RUNNING"
    assert sim.mutation_count == 1


# ---------------------------------------------------------------------------
# RT-07 — fresh outside the authorized set
# ---------------------------------------------------------------------------

def test_rt07_fresh_outside_authorized_set_is_fresh_not_authorized(tmp_path):
    ctx = context(tmp_path, seat_list=seats("main", "tdo", token=True))
    sim = build(ctx, [up_existing(ctx)], base=tmp_path)
    sim.state = "STOPPED"

    outcome = sim.resume(
        explicit_fresh=[("main", "authorized reason")],
        actual_outcomes={"main": "fresh-primed", "tdo": "fresh-primed"},
    )
    assert outcome.ok is False
    assert outcome.rc == 2
    assert outcome.code == "fresh_not_authorized"
    assert outcome.mutated is True
    assert (
        ctx.run_dir / "reports" / "evidence" / "manifest" / "run-manifest.partial.json"
    ).is_file()


def test_rt07_planner_blocks_fresh_for_an_unknown_seat():
    plan_obj = continuity_plan([SeatFacts("main", "sess-main")], [("ghost", "reason")])
    assert plan_obj.decisionStatus == "blocked"
    assert plan_obj.blockedSeats[0]["logicalId"] == "ghost"
    assert plan_obj.blockedSeats[0]["reason"] == "fresh_not_authorized"
    assert plan_obj.explicitFreshSeats == []


def test_rt07_control_authorized_fresh_with_reason_passes(tmp_path):
    ctx = context(tmp_path, seat_list=seats("main", "tdo", token=True))
    sim = build(ctx, [up_existing(ctx)], base=tmp_path)
    sim.state = "STOPPED"

    outcome = sim.resume(
        explicit_fresh=[("main", "snapshot unreadable")],
        actual_outcomes={"main": "fresh-primed", "tdo": "resumed"},
    )
    assert outcome.ok is True, outcome.code
    assert outcome.payload["actualOutcomes"] == {"main": "fresh-primed", "tdo": "resumed"}


# ---------------------------------------------------------------------------
# RT-08 — a healthy "ready" observation is not evidence of continuity
# ---------------------------------------------------------------------------

def test_rt08_healthy_observation_alone_is_not_a_resume():
    observation = evaluate(
        Sources(session="present", hook_present=True, hook_activity="working")
    )
    plan_obj = continuity_plan(
        [
            SeatFacts(
                logicalId="main",
                canonicalSessionName="sess-main",
                nodeId="node-1",
                resumeTokenPresent="unknown",
                observation=observation,
            )
        ]
    )
    assert plan_obj.decisionStatus == "needs-human"
    assert plan_obj.seats[0]["expectedAction"] == "awaiting-decision"
    assert plan_obj.seats[0]["expectedAction"] != "resume-original"


def test_rt08_control_real_token_is_resumed():
    plan_obj = continuity_plan([SeatFacts("main", "sess-main", resumeTokenPresent=True)])
    assert plan_obj.decisionStatus == "allow"
    assert plan_obj.seats[0]["expectedAction"] == "resume-original"
