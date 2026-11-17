# -*- coding: utf-8 -*-
"""RT-09..RT-12 — expired and forged launch provenance.

TTL windows: start 30 min, resume 20 min (CONTRACT §7).  A consumed verb is
rejected.  An externally supplied launch id is overridden and audited.  A
closed launch is never reused (RT-12 is P1; the fixture guarantees no reuse,
not a dedicated daemon-restart verb).
"""

from __future__ import annotations

from supervisor_sim import Launch

from helpers import build, context, seats, start_steps, up_existing


# ---------------------------------------------------------------------------
# RT-09 — TTL expiry
# ---------------------------------------------------------------------------

def test_rt09_stale_start_launch_is_refused_before_mutation(tmp_path):
    ctx = context(tmp_path)
    sim = build(ctx, start_steps(ctx), base=tmp_path)
    sim._write_launch(Launch("old-launch", "start", "2020-01-01T00:00:00Z"))

    outcome = sim.start()
    assert outcome.ok is False
    assert outcome.rc == 2
    assert outcome.code == "stale_launch"
    assert sim.mutation_count == 0
    assert sim.runner.calls == []


def test_rt09_control_fresh_start_launch_is_accepted(tmp_path):
    ctx = context(tmp_path)
    sim = build(ctx, start_steps(ctx), base=tmp_path)
    sim._write_launch(Launch("fresh-launch", "start", sim.clock.peek()))
    outcome = sim.start()
    assert outcome.ok is True, outcome.code


def test_rt09_resume_ttl_is_twenty_minutes_not_thirty(tmp_path):
    ctx = context(tmp_path, seat_list=seats("main", token=True))
    sim = build(ctx, [up_existing(ctx)], base=tmp_path)
    sim.state = "STOPPED"
    sim._write_launch(
        Launch("old-resume", "resume", "2026-01-01T00:00:00Z", ttlSeconds=1200)
    )
    # 21 minutes later: expired for resume even though a start would still pass.
    sim.clock.advance(21 * 60)
    outcome = sim.resume()
    assert outcome.ok is False
    assert outcome.rc == 2
    assert outcome.code == "stale_launch"
    assert sim.mutation_count == 0


def test_rt09_control_resume_inside_twenty_minutes_is_accepted(tmp_path):
    ctx = context(tmp_path, seat_list=seats("main", token=True))
    sim = build(ctx, [up_existing(ctx)], base=tmp_path)
    sim.state = "STOPPED"
    sim._write_launch(
        Launch("fresh-resume", "resume", "2026-01-01T00:00:00Z", ttlSeconds=1200)
    )
    sim.clock.advance(19 * 60)
    outcome = sim.resume()
    assert outcome.ok is True, outcome.code


# ---------------------------------------------------------------------------
# RT-10 — a launch verb can be consumed only once
# ---------------------------------------------------------------------------

def test_rt10_consumed_start_verb_is_refused(tmp_path):
    ctx = context(tmp_path)
    sim = build(ctx, start_steps(ctx), base=tmp_path)
    sim._write_launch(
        Launch("old-launch", "start", sim.clock.peek(), consumed=("start",))
    )
    outcome = sim.start()
    assert outcome.ok is False
    assert outcome.rc == 2
    assert outcome.code == "launch_verb_consumed"
    assert sim.mutation_count == 0
    assert sim.runner.calls == []


def test_rt10_control_unconsumed_start_is_accepted(tmp_path):
    ctx = context(tmp_path)
    sim = build(ctx, start_steps(ctx), base=tmp_path)
    outcome = sim.start()
    assert outcome.ok is True, outcome.code


def test_rt10_second_resume_is_refused_as_consumed(tmp_path):
    ctx = context(tmp_path, seat_list=seats("main", token=True))
    sim = build(ctx, [up_existing(ctx)], base=tmp_path)
    sim.state = "STOPPED"

    first = sim.resume()
    assert first.ok is True, first.code
    # Rewind only the state, not the launch record: the verb stays consumed.
    sim.state = "STOPPED"
    second = sim.resume()
    assert second.ok is False
    assert second.rc == 2
    assert second.code == "launch_verb_consumed"
    assert sim.runner.calls and len(sim.runner.calls) == 1


# ---------------------------------------------------------------------------
# RT-11 — forged external launch id is overridden, never accepted
# ---------------------------------------------------------------------------

def test_rt11_forged_launch_id_is_overridden_and_audited(tmp_path):
    ctx = context(tmp_path)
    sim = build(ctx, start_steps(ctx), base=tmp_path)
    outcome = sim.start(env={"OPENRIG_ENTRY_LAUNCH_ID": "forged-launch"})
    assert outcome.ok is True, outcome.code
    assert sim.launch is not None
    assert sim.launch.launchId != "forged-launch"
    assert sim.audit == [
        {
            "event": "provenance_overridden",
            "envKey": "OPENRIG_ENTRY_LAUNCH_ID",
            "forged": "forged-launch",
            "actual": sim.launch.launchId,
        }
    ]


def test_rt11_control_legitimate_launch_has_no_override_audit(tmp_path):
    ctx = context(tmp_path)
    sim = build(ctx, start_steps(ctx), base=tmp_path)
    outcome = sim.start()
    assert outcome.ok is True, outcome.code
    assert sim.audit == []


# ---------------------------------------------------------------------------
# RT-12 (P1) — a closed launch is not reused for a new lifecycle start
# ---------------------------------------------------------------------------

def test_rt12_closed_launch_is_not_reused(tmp_path):
    ctx = context(tmp_path)
    sim = build(ctx, start_steps(ctx), base=tmp_path)
    sim._write_launch(
        Launch(
            "old-closed",
            "start",
            sim.clock.peek(),
            phase="closed",
            consumed=("start",),
        )
    )
    outcome = sim.start()
    assert outcome.ok is True, outcome.code
    assert sim.launch is not None
    assert sim.launch.launchId != "old-closed"
    assert "start" in sim.launch.consumed


def test_rt12_control_fresh_launch_is_minted(tmp_path):
    ctx = context(tmp_path)
    sim = build(ctx, start_steps(ctx), base=tmp_path)
    outcome = sim.start()
    assert outcome.ok is True, outcome.code
    assert sim.launch is not None
    assert sim.launch.launchId
    assert sim.launch.phase != "closed"
