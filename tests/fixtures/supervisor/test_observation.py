# -*- coding: utf-8 -*-
"""F-03 self-tests: CT-15..CT-19 / D-014..D-019."""

from __future__ import annotations

import pytest

from guards import is_fixture
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


def test_clean_oracle_observation():
    result = obs(session="present", hook_present=True, hook_activity="working")
    assert result.session == "present"
    assert result.activity == "working"
    assert result.evidence == "oracle"
    assert result.evidenceReasons == ()


def test_hook_missing_but_ps_sees_working_is_not_unknown():
    result = obs(session="present", ps_activity="working", hook_present=False)
    assert result.activity == "working"
    assert result.evidence == "degraded"
    assert result.evidenceReasons == ("hook_missing",)


def test_no_addressable_source_is_degraded_with_no_observation_path():
    result = obs(addressable=False)
    assert result.session is None
    assert result.activity is None
    assert result.evidence == "degraded"
    assert result.evidenceReasons == ("no_observation_path",)


def test_ps_available_without_session_is_absent_not_degraded():
    result = obs(ps_available=True, session=None)
    assert result.session == "absent"
    assert result.activity is None
    assert result.evidence != "degraded"
    assert result.evidenceReasons == ()


def test_true_oracle_unknown_is_honest_and_not_degraded():
    result = obs(session="present", hook_present=True, hook_activity="unknown")
    assert result.activity == "unknown"
    assert result.evidence != "degraded"
    assert "oracle_unknown" not in result.evidenceReasons


def test_activity_is_none_iff_session_not_present():
    matrix = [
        obs(addressable=False),
        obs(session="present", hook_present=True, hook_activity="working"),
        obs(session="detached"),
        obs(session="exited"),
        obs(session="absent"),
        obs(ps_available=False, hook_activity="idle-at-prompt"),
    ]
    for result in matrix:
        assert (result.activity is None) == (result.session != "present"), result


def test_degraded_iff_reasons_non_empty():
    matrix = [
        obs(session="present", hook_present=True, hook_activity="working"),
        obs(session="present", hook_present=False, ps_activity="working"),
        obs(addressable=False),
        obs(session="absent"),
    ]
    for result in matrix:
        assert (result.evidence == "degraded") == bool(result.evidenceReasons), result


def test_reasons_come_only_from_the_transport_enum():
    for kwargs in (
        {"session": "present", "hook_present": False, "ps_activity": "working"},
        {"session": "present", "relay_status": 401},
        {"addressable": False},
    ):
        result = obs(**kwargs)
        assert set(result.evidenceReasons) <= ALLOWED_REASONS


def test_relay_401_and_503_are_distinct_reasons():
    assert "relay_401" in obs(session="present", relay_status=401).evidenceReasons
    assert "relay_503" in obs(session="present", relay_status=503).evidenceReasons


def test_transcript_unreadable_reason():
    result = obs(session="present", transcript_readable=False)
    assert "transcript_unreadable" in result.evidenceReasons


def test_ps_unavailable_still_keeps_live_activity():
    result = obs(ps_available=False, hook_present=True, hook_activity="working")
    assert result.session == "present"
    assert result.activity == "working"
    assert "ps_unavailable" in result.evidenceReasons
    assert result.evidence == "degraded"


def test_degraded_records_only_missing_sources():
    result = obs(
        ps_available=False,
        hook_present=True,
        hook_activity="working",
        transcript_readable=False,
    )
    assert result.activity == "working"
    assert set(result.evidenceReasons) == {"ps_unavailable", "transcript_unreadable"}


# -- stall judgement (D-014) ------------------------------------------------

def test_long_tool_call_is_not_a_stall():
    observation = obs(session="present", hook_present=True, hook_activity="working")
    verdict = judge_stall(observation, queue_age_seconds=99999, threshold_seconds=60)
    assert verdict.stall is False
    assert verdict.reason == "live_activity"
    assert verdict.health != "stalled"


def test_high_age_without_activity_is_not_healthy():
    observation = obs(addressable=False)
    verdict = judge_stall(observation, queue_age_seconds=99999, threshold_seconds=60)
    assert verdict.stall is False
    assert verdict.health == "unknown"


def test_unknown_activity_is_not_stalled_and_not_healthy():
    observation = obs(session="present", hook_present=True, hook_activity="unknown")
    verdict = judge_stall(observation, queue_age_seconds=99999, threshold_seconds=60)
    assert verdict.stall is False
    assert verdict.health == "unknown"
    assert verdict.health != "healthy"


def test_idle_over_threshold_is_a_stall():
    observation = obs(session="present", hook_present=True, hook_activity="idle-at-prompt")
    assert judge_stall(observation, queue_age_seconds=61, threshold_seconds=60).stall is True


def test_idle_within_threshold_is_healthy():
    observation = obs(session="present", hook_present=True, hook_activity="idle-at-prompt")
    verdict = judge_stall(observation, queue_age_seconds=10, threshold_seconds=60)
    assert verdict.stall is False
    assert verdict.health == "healthy"


def test_absent_session_is_not_healthy():
    observation = obs(ps_available=True, session="absent")
    assert judge_stall(observation, queue_age_seconds=10).health == "absent"


# -- construction guards ------------------------------------------------------

def test_construction_rejects_activity_for_non_present_session():
    with pytest.raises(ObservationInvariant):
        Observation("absent", "idle-at-prompt", "observed", ())


def test_construction_rejects_degraded_without_reasons():
    with pytest.raises(ObservationInvariant):
        Observation("present", "working", "degraded", ())


def test_construction_rejects_oracle_unknown_as_reason():
    with pytest.raises(ObservationInvariant):
        Observation("present", "unknown", "degraded", ("oracle_unknown",))


def test_observation_payload_is_marked():
    assert is_fixture(obs(session="absent").to_dict())
