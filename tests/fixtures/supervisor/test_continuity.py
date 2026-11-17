# -*- coding: utf-8 -*-
"""F-04 self-tests: CT-04..CT-08, token tri-state, node identity."""

from __future__ import annotations

from continuity import (
    ContinuityPlan,
    SeatFacts,
    default_outcomes,
    expected_outcome_map,
    plan,
    verify_outcomes,
)
from guards import is_fixture
from observation import Sources, evaluate


def seat(seat_id: str, token: bool | str = True, **kwargs) -> SeatFacts:
    return SeatFacts(
        logicalId=seat_id,
        canonicalSessionName=f"sess-{seat_id}",
        nodeId=kwargs.pop("nodeId", "node-1"),
        resumeTokenPresent=token,
        **kwargs,
    )


def test_all_tokens_valid_allows_resume_original():
    plan_obj = plan([seat("main"), seat("tdo")])
    assert plan_obj.decisionStatus == "allow"
    assert [row["expectedAction"] for row in plan_obj.seats] == ["resume-original", "resume-original"]
    assert plan_obj.blockedSeats == []


def test_unknown_token_needs_human_and_is_not_false():
    plan_obj = plan([seat("main", token="unknown")])
    row = plan_obj.seats[0]
    assert plan_obj.decisionStatus == "needs-human"
    assert row["resumeTokenPresent"] == "unknown"
    assert row["expectedAction"] == "awaiting-decision"
    assert row["expectedAction"] != "fresh-primed"


def test_false_token_without_fresh_needs_human():
    plan_obj = plan([seat("main", token=False)])
    assert plan_obj.decisionStatus == "needs-human"
    assert plan_obj.seats[0]["expectedAction"] == "awaiting-decision"


def test_explicit_fresh_with_reason_is_allowed():
    plan_obj = plan([seat("main", token=False)], [("main", "snapshot unreadable")])
    row = plan_obj.seats[0]
    assert plan_obj.decisionStatus == "allow"
    assert row["expectedAction"] == "fresh-primed"
    assert row["freshAuthorized"] is True
    assert row["freshReason"] == "snapshot unreadable"
    assert plan_obj.explicitFreshSeats == ["main"]


def test_explicit_fresh_with_empty_reason_is_blocked():
    plan_obj = plan([seat("main", token=False)], [("main", "   ")])
    assert plan_obj.decisionStatus == "blocked"
    assert plan_obj.blockedSeats[0]["reason"] == "fresh_not_authorized"


def test_explicit_fresh_for_unknown_seat_is_blocked():
    plan_obj = plan([seat("main")], [("ghost", "reason")])
    assert plan_obj.decisionStatus == "blocked"
    assert plan_obj.blockedSeats[0]["logicalId"] == "ghost"
    assert plan_obj.blockedSeats[0]["reason"] == "fresh_not_authorized"


def test_node_identity_change_blocks_the_plan():
    plan_obj = plan([seat("main", nodeId="new-node", plannedNodeId="old-node")])
    assert plan_obj.decisionStatus == "blocked"
    assert plan_obj.blockedSeats[0]["reason"] == "continuity_mismatch"


def test_degraded_observation_is_reported_separately_from_absence():
    degraded = evaluate(Sources(session="present", hook_present=False, ps_activity="working"))
    absent = evaluate(Sources(session="absent"))
    plan_obj = plan([seat("deg", observation=degraded), seat("away", observation=absent)])
    assert [item["logicalId"] for item in plan_obj.degraded] == ["deg"]
    assert plan_obj.degraded[0]["reasons"] == ["hook_missing"]


def test_verify_outcomes_all_match():
    plan_obj = plan([seat("main"), seat("tdo")])
    check = verify_outcomes(plan_obj, default_outcomes(plan_obj))
    assert check.ok is True
    assert check.code is None


def test_expected_resume_but_actual_fresh_is_a_mismatch():
    plan_obj = plan([seat("main")])
    check = verify_outcomes(plan_obj, {"main": "fresh-primed"})
    assert check.ok is False
    assert check.code == "continuity_mismatch"
    assert check.mismatches[0]["reason"] == "fresh_primes_over_resume"


def test_unauthorized_fresh_after_fresh_for_another_seat_is_fresh_not_authorized():
    plan_obj = plan([seat("main"), seat("tdo")], [("main", "authorized reason")])
    check = verify_outcomes(plan_obj, {"main": "fresh-primed", "tdo": "fresh-primed"})
    assert check.ok is False
    assert check.code == "fresh_not_authorized"


def test_missing_actual_outcome_is_a_mismatch():
    plan_obj = plan([seat("main")])
    check = verify_outcomes(plan_obj, {})
    assert check.ok is False
    assert check.mismatches[0]["reason"] == "missing_actual_outcome"


def test_plan_payload_has_schema_shape_and_marker():
    payload = plan([seat("main")], run_id="r1", launch_id="l1").to_dict()
    assert is_fixture(payload)
    for key in (
        "schemaVersion",
        "runId",
        "launchId",
        "intent",
        "generatedAt",
        "decisionStatus",
        "seats",
        "blockedSeats",
        "degraded",
    ):
        assert key in payload
    assert payload["decisionStatus"] in {"allow", "blocked", "needs-human"}
    assert payload["schemaVersion"] == 1
    row = payload["seats"][0]
    for key in (
        "logicalId",
        "canonicalSessionName",
        "restorePolicy",
        "expectedAction",
        "freshAuthorized",
    ):
        assert key in row


def test_plan_returns_typed_object():
    assert isinstance(plan([seat("main")]), ContinuityPlan)


def test_expected_outcome_map_is_the_single_action_to_outcome_mapping():
    plan_obj = plan([seat("main"), seat("tdo", token=False)], [("tdo", "reason")])
    assert expected_outcome_map(plan_obj) == {
        "main": "resumed",
        "tdo": "fresh-primed",
    }
