# -*- coding: utf-8 -*-
"""RT-19..RT-23 — activity unknown / no observation path / long tool calls.

The three axes (session, activity, evidence) stay separate.  A missing source
is recorded as a transport reason; it never silently becomes ``idle`` or
``healthy``.
"""

from __future__ import annotations

import pytest

from observation import (
    ALLOWED_REASONS,
    Observation,
    ObservationInvariant,
    Sources,
    evaluate,
    judge_stall,
)


def obs(**kwargs) -> Observation:
    return evaluate(Sources(**kwargs))


# ---------------------------------------------------------------------------
# RT-19 — hook missing but ps sees working: keep working, record hook_missing
# ---------------------------------------------------------------------------

def test_rt19_activity_hook_missing_ps_working_is_not_unknown():
    result = obs(session="present", ps_activity="working", hook_present=False)
    assert result.session == "present"
    assert result.activity == "working"
    assert result.evidence == "degraded"
    assert result.evidenceReasons == ("hook_missing",)


def test_rt19_control_all_sources_available_is_oracle():
    result = obs(session="present", hook_present=True, hook_activity="working")
    assert result.activity == "working"
    assert result.evidence == "oracle"
    assert result.evidenceReasons == ()


# ---------------------------------------------------------------------------
# RT-20 — no addressable source: unknown + no_observation_path
# ---------------------------------------------------------------------------

def test_rt20_activity_no_addressable_source_is_degraded_no_observation_path():
    result = obs(addressable=False)
    assert result.session is None
    assert result.activity is None
    assert result.evidence == "degraded"
    assert result.evidenceReasons == ("no_observation_path",)


def test_rt20_control_addressable_source_has_a_value():
    result = obs(session="present", ps_activity="working")
    assert result.session == "present"
    assert result.activity == "working"
    assert "no_observation_path" not in result.evidenceReasons


# ---------------------------------------------------------------------------
# RT-21 — ps available, no session: absent is an observation, not degraded
# ---------------------------------------------------------------------------

def test_rt21_activity_ps_available_without_session_is_absent_not_degraded():
    result = obs(ps_available=True, session=None)
    assert result.session == "absent"
    assert result.activity is None
    assert result.evidence == "observed"
    assert result.evidence != "degraded"
    assert result.evidenceReasons == ()


def test_rt21_control_present_session_is_present():
    result = obs(session="present", hook_present=True, hook_activity="working")
    assert result.session == "present"
    assert result.activity == "working"


# ---------------------------------------------------------------------------
# RT-22 — true oracle_unknown is honest, not a degraded transport reason
# ---------------------------------------------------------------------------

def test_rt22_activity_true_oracle_unknown_is_not_degraded():
    result = obs(session="present", hook_present=True, hook_activity="unknown")
    assert result.activity == "unknown"
    assert result.evidence == "oracle"
    assert result.evidence != "degraded"
    assert "oracle_unknown" not in result.evidenceReasons


def test_rt22_control_known_activity_is_working():
    result = obs(session="present", hook_present=True, hook_activity="working")
    assert result.activity == "working"
    assert result.evidence == "oracle"


# ---------------------------------------------------------------------------
# RT-23 — long tool call: queue age alone never decides a stall
# ---------------------------------------------------------------------------

def test_rt23_activity_long_tool_call_is_not_a_stall():
    result = obs(session="present", hook_present=True, hook_activity="working")
    verdict = judge_stall(result, queue_age_seconds=99999, threshold_seconds=60)
    assert verdict.stall is False
    assert verdict.reason == "live_activity"
    assert verdict.health != "stalled"


def test_rt23_activity_high_age_without_activity_is_not_healthy():
    result = obs(addressable=False)
    verdict = judge_stall(result, queue_age_seconds=99999, threshold_seconds=60)
    assert verdict.stall is False
    assert verdict.health == "unknown"
    assert verdict.health != "healthy"


def test_rt23_activity_idle_over_threshold_is_a_stall():
    result = obs(session="present", hook_present=True, hook_activity="idle-at-prompt")
    assert judge_stall(result, queue_age_seconds=61, threshold_seconds=60).stall is True


def test_rt23_activity_idle_within_threshold_is_healthy():
    result = obs(session="present", hook_present=True, hook_activity="idle-at-prompt")
    verdict = judge_stall(result, queue_age_seconds=10, threshold_seconds=60)
    assert verdict.stall is False
    assert verdict.health == "healthy"


# ---------------------------------------------------------------------------
# Axis invariants (construction guard)
# ---------------------------------------------------------------------------

def test_activity_axes_are_never_mixed():
    matrix = [
        obs(addressable=False),
        obs(session="present", hook_present=True, hook_activity="working"),
        obs(session="detached"),
        obs(session="absent"),
        obs(ps_available=False, hook_activity="idle-at-prompt"),
    ]
    for result in matrix:
        assert (result.activity is None) == (result.session != "present"), result
        assert (result.evidence == "degraded") == bool(result.evidenceReasons), result
        assert set(result.evidenceReasons) <= ALLOWED_REASONS


def test_activity_construction_rejects_cross_axis_values():
    with pytest.raises(ObservationInvariant):
        Observation("absent", "idle-at-prompt", "observed", ())
    with pytest.raises(ObservationInvariant):
        Observation("present", "working", "degraded", ())
    with pytest.raises(ObservationInvariant):
        Observation("present", "unknown", "degraded", ("oracle_unknown",))
