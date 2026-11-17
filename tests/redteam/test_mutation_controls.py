# -*- coding: utf-8 -*-
"""RT-29/RT-30 — offline proof and per-guard mutation controls.

RT-30 is the anti-vacuous-green rule: for every named guard, the negative
case must fail when that guard is replaced by ``return True``.  The table below
is checked for full coverage (14/14) and printed.

RT-29 ("no PATH / no network still rc=0") is an acceptance-level command, not
a pytest case: the suite itself runs under the F-09 ban, and the external
``PATH=/nonexistent pytest tests/redteam -q`` run is recorded in the verdict.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, replace

import pytest

import continuity
import supervisor_sim
from guards import ExternalIOForbidden
from supervisor_sim import COMMAND_GUARDS, GUARD_REGISTRY, Launch, guard_launch_ttl

from helpers import build, context, down, seats, start_steps, up_existing


def _bypass(monkeypatch, guard_name: str) -> None:
    # Different guards have different arities; a varargs stub is the bypass.
    monkeypatch.setattr(supervisor_sim, guard_name, lambda *args, **kwargs: True)


@dataclass(frozen=True)
class Case:
    fn: object
    code: str
    rt: str


# ---------------------------------------------------------------------------
# Per-guard negative scenario builders (baseline fails; bypass changes it)
# ---------------------------------------------------------------------------

def _case_bridge_sha(base, mp, mutated):
    ctx = replace(context(base), expected_bridge_sha256="0" * 64)
    if mutated:
        _bypass(mp, "guard_bridge_sha")
    sim = build(ctx, start_steps(ctx), base=base)
    return sim.start(), sim


def _case_home_match(base, mp, mutated):
    ctx = replace(context(base), home_expected=base / "other-home")
    if mutated:
        _bypass(mp, "guard_home_match")
    sim = build(ctx, start_steps(ctx), base=base)
    return sim.start(), sim


def _case_no_legacy_run(base, mp, mutated):
    ctx = context(base, run_exists=True)
    if mutated:
        _bypass(mp, "guard_no_legacy_run")
    sim = build(ctx, start_steps(ctx), base=base)
    return sim.start(), sim


def _case_rig_absent(base, mp, mutated):
    ctx = context(base, rig_exists=True)
    if mutated:
        _bypass(mp, "guard_rig_absent")
    sim = build(ctx, start_steps(ctx), base=base)
    return sim.start(), sim


def _case_workflow_absent(base, mp, mutated):
    ctx = context(base, workflow_exists=True)
    if mutated:
        _bypass(mp, "guard_workflow_absent")
    sim = build(ctx, start_steps(ctx), base=base)
    return sim.start(), sim


def _case_daemon_identity(base, mp, mutated):
    ctx = context(base, daemon_running=True, daemon_pid=1, healthz_pid=2)
    if mutated:
        _bypass(mp, "guard_daemon_identity")
    sim = build(ctx, start_steps(ctx)[1:], base=base)  # daemon already running
    return sim.start(), sim


def _case_port_collision(base, mp, mutated):
    ctx = replace(context(base), port_owner_home=base / "other-home")
    if mutated:
        _bypass(mp, "guard_port_collision")
    sim = build(ctx, start_steps(ctx), base=base)
    return sim.start(), sim


def _case_launch_ttl(base, mp, mutated):
    ctx = context(base)
    sim = build(ctx, start_steps(ctx), base=base)
    sim._write_launch(Launch("old-launch", "start", "2020-01-01T00:00:00Z"))
    if mutated:
        _bypass(mp, "guard_launch_ttl")
    return sim.start(), sim


def _case_verb_unconsumed(base, mp, mutated):
    ctx = context(base)
    sim = build(ctx, start_steps(ctx), base=base)
    sim._write_launch(
        Launch("old-launch", "start", sim.clock.peek(), consumed=("start",))
    )
    if mutated:
        _bypass(mp, "guard_verb_unconsumed")
    return sim.start(), sim


def _case_continuity_allow(base, mp, mutated):
    ctx = context(base, seat_list=seats("main", token="unknown"))
    if mutated:
        _bypass(mp, "guard_continuity_allow")
    sim = build(ctx, [up_existing(ctx)], base=base)
    sim.state = "STOPPED"
    return sim.resume(), sim


def _case_fresh_authorized(base, mp, mutated):
    ctx = context(base, seat_list=seats("main", token=True))
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
    crafted = continuity.ContinuityPlan("allow", [row], [], [], [])
    mp.setattr(continuity, "plan", lambda *args, **kwargs: crafted)
    if mutated:
        _bypass(mp, "guard_fresh_authorized")
    sim = build(ctx, [up_existing(ctx)], base=base)
    sim.state = "STOPPED"
    return sim.resume(), sim


def _case_node_identity(base, mp, mutated):
    ctx = context(base, seat_list=seats("main", token=True, node="new-node"))
    ctx = replace(ctx, seats=(replace(ctx.seats[0], plannedNodeId="old-node"),))
    if mutated:
        _bypass(mp, "guard_node_identity")
    sim = build(ctx, [], base=base)
    sim.state = "STOPPED"
    return sim.resume(), sim


def _case_seat_outcome_match(base, mp, mutated):
    ctx = context(base, seat_list=seats("main", token=True))
    if mutated:
        _bypass(mp, "guard_seat_outcome_match")
    sim = build(ctx, [up_existing(ctx)], base=base)
    sim.state = "STOPPED"
    return sim.resume(actual_outcomes={"main": "fresh-primed"}), sim


def _case_archive_complete(base, mp, mutated):
    ctx = context(base, archive_manifest={"archiveStatus": "PARTIAL"})
    if mutated:
        _bypass(mp, "guard_archive_complete")
    sim = build(ctx, [down(ctx)], base=base)
    sim.state = "RUNNING"
    return sim.stop(), sim


CASES = {
    "guard_bridge_sha": Case(_case_bridge_sha, "bridge_invalid", "RT-01"),
    "guard_home_match": Case(_case_home_match, "run_home_mismatch", "RT-01"),
    "guard_no_legacy_run": Case(_case_no_legacy_run, "run_exists", "RT-01"),
    "guard_rig_absent": Case(_case_rig_absent, "rig_exists", "RT-01"),
    "guard_workflow_absent": Case(_case_workflow_absent, "workflow_duplicate", "RT-01"),
    "guard_daemon_identity": Case(
        _case_daemon_identity, "daemon_identity_mismatch", "RT-09/RT-12"
    ),
    "guard_port_collision": Case(_case_port_collision, "port_collision", "RT-12"),
    "guard_launch_ttl": Case(_case_launch_ttl, "stale_launch", "RT-09"),
    "guard_verb_unconsumed": Case(
        _case_verb_unconsumed, "launch_verb_consumed", "RT-10"
    ),
    "guard_continuity_allow": Case(
        _case_continuity_allow, "continuity_blocked", "RT-05"
    ),
    "guard_fresh_authorized": Case(
        _case_fresh_authorized, "fresh_not_authorized", "RT-07"
    ),
    "guard_node_identity": Case(
        _case_node_identity, "continuity_mismatch", "RT-08"
    ),
    "guard_seat_outcome_match": Case(
        _case_seat_outcome_match, "continuity_mismatch", "RT-06/RT-07"
    ),
    "guard_archive_complete": Case(
        _case_archive_complete, "archive_incomplete", "RT-13/RT-14/RT-15"
    ),
}


def test_rt30_mutation_table_covers_every_named_guard():
    assert set(CASES) == set(GUARD_REGISTRY)
    assert len(CASES) == len(GUARD_REGISTRY)
    assert set(GUARD_REGISTRY) <= set(COMMAND_GUARDS.get("start", ())) | set(
        COMMAND_GUARDS.get("resume", ())
    ) | set(COMMAND_GUARDS.get("stop", ())) | set(COMMAND_GUARDS.get("check", ()))


@pytest.mark.parametrize("guard_name", sorted(CASES))
def test_rt30_guard_mutation_flips_its_negative(guard_name, tmp_path, monkeypatch):
    case = CASES[guard_name]

    baseline, base_sim = case.fn(tmp_path / "baseline", monkeypatch, False)
    assert baseline.ok is False, (guard_name, baseline.code)
    assert baseline.code == case.code, (guard_name, baseline.code)

    bypassed, _ = case.fn(tmp_path / "bypass", monkeypatch, True)
    assert bypassed.code != case.code, (guard_name, bypassed.code)
    if guard_name != "guard_node_identity":
        # node_identity's bypass falls through to continuity_blocked, which is
        # still a refusal; every other guard's negative disappears entirely.
        assert bypassed.ok is True, (guard_name, bypassed.code)


def test_rt30_mutation_coverage_is_one_hundred_percent(capsys):
    covered = len(CASES)
    total = len(GUARD_REGISTRY)
    coverage = covered / total if total else 0
    with capsys.disabled():
        print("\nGUARD <-> RT mutation coverage")
        for name in sorted(GUARD_REGISTRY):
            print(f"  {name:30s} -> {CASES[name].rt}")
        print(f"  coverage: {covered}/{total} = {coverage:.0%}")
    assert covered == total
    assert coverage == 1.0


# ---------------------------------------------------------------------------
# RT-29 — offline proof (the PATH=/nonexistent run is external, see verdict)
# ---------------------------------------------------------------------------

def test_rt29_redteam_suite_cannot_use_process_or_network_io():
    assert subprocess.run.__name__.startswith("forbidden_")
    with pytest.raises(ExternalIOForbidden):
        subprocess.run(["true"], check=False)
    with pytest.raises(ExternalIOForbidden):
        __import__("socket").socket().connect(("127.0.0.1", 9))


def test_rt29_control_launch_ttl_is_pure_and_offline():
    # A pure guard call is the control: no process/network, deterministic.
    assert guard_launch_ttl(
        Launch("l", "start", "2026-01-01T00:00:00Z"), "2026-01-01T00:29:00Z"
    ) is True
