# -*- coding: utf-8 -*-
"""F-04 — continuity plan and per-seat outcome verification (CT-01..CT-19).

Hard rules (CONTINUITY §3, D-019):

* ``resumeTokenPresent`` is three-valued: ``true`` / ``false`` / ``unknown``;
  ``unknown`` is neither ``false`` nor ``true``.
* no token and no explicit ``--fresh`` ⇒ ``awaiting-decision`` (never silent fresh);
* ``freshAuthorized=True`` requires a non-empty reason;
* ``fresh-primed`` outside the authorized set ⇒ mismatch;
* a ``nodeId`` change for the same ``logicalId`` blocks the plan;
* ``decisionStatus != allow`` ⇒ zero live mutation (enforced by the supervisor).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from guards import fixture_mark
from observation import Observation

FIXTURE_ID = "F-04"

TOKEN_VALUES = (True, False, "unknown")
RESTORE_POLICIES = ("resume_if_possible", "fresh_required", "n-a")
EXPECTED_ACTIONS = ("resume-original", "fresh-primed", "awaiting-decision", "new", "n-a")
ACTUAL_OUTCOMES = ("resumed", "fresh-primed", "awaiting-decision", "attention_required", "failed", "ready", "n-a")
DECISION_STATUSES = ("allow", "blocked", "needs-human")


@dataclass(frozen=True)
class SeatFacts:
    logicalId: str
    canonicalSessionName: str
    nodeId: str | None = None
    plannedNodeId: str | None = None
    resumeTokenPresent: bool | str = "unknown"
    restorePolicy: str = "resume_if_possible"
    observation: Observation | None = None

    def __post_init__(self) -> None:
        if self.resumeTokenPresent not in TOKEN_VALUES:
            raise ValueError("resumeTokenPresent must be true/false/unknown")
        if self.restorePolicy not in RESTORE_POLICIES:
            raise ValueError(f"bad restorePolicy: {self.restorePolicy!r}")


@dataclass
class ContinuityPlan:
    decisionStatus: str
    seats: list[dict]
    blockedSeats: list[dict]
    explicitFreshSeats: list[str]
    degraded: list[dict]
    schemaVersion: int = 1
    runId: str = "fixture-run"
    launchId: str = "fixture-launch"
    intent: str = "resume"
    generatedAt: str = "2026-01-01T00:00:00Z"

    @property
    def allowed(self) -> bool:
        return self.decisionStatus == "allow"

    def seat(self, logical_id: str) -> dict | None:
        for seat in self.seats:
            if seat["logicalId"] == logical_id:
                return seat
        return None

    def to_dict(self) -> dict:
        return fixture_mark(
            FIXTURE_ID,
            schemaVersion=self.schemaVersion,
            runId=self.runId,
            launchId=self.launchId,
            intent=self.intent,
            generatedAt=self.generatedAt,
            decisionStatus=self.decisionStatus,
            seats=[dict(seat) for seat in self.seats],
            explicitFreshSeats=list(self.explicitFreshSeats),
            blockedSeats=[dict(item) for item in self.blockedSeats],
            degraded=[dict(item) for item in self.degraded],
            notes=None,
        )


def plan(
    seats: Iterable[SeatFacts],
    explicit_fresh: Iterable[tuple[str, str]] = (),
    *,
    run_id: str = "fixture-run",
    launch_id: str = "fixture-launch",
    generated_at: str = "2026-01-01T00:00:00Z",
    intent: str = "resume",
) -> ContinuityPlan:
    facts = list(seats)
    known = {seat.logicalId: seat for seat in facts}
    blocked: list[dict] = []
    fresh: dict[str, str] = {}

    for seat_id, reason in explicit_fresh:
        if seat_id not in known:
            blocked.append(
                {
                    "logicalId": seat_id,
                    "reason": "fresh_not_authorized",
                    "remediation": "name a seat that exists in the bridge before using --fresh",
                }
            )
            continue
        if not reason or not reason.strip():
            blocked.append(
                {
                    "logicalId": seat_id,
                    "reason": "fresh_not_authorized",
                    "remediation": "provide a non-empty --reason for every --fresh seat",
                }
            )
            continue
        fresh[seat_id] = reason

    seat_rows: list[dict] = []
    degraded: list[dict] = []
    for seat in facts:
        row = {
            "logicalId": seat.logicalId,
            "canonicalSessionName": seat.canonicalSessionName,
            "nodeId": seat.nodeId,
            "restorePolicy": seat.restorePolicy,
            "resumeTokenPresent": seat.resumeTokenPresent,
            "expectedAction": "awaiting-decision",
            "actualOutcome": None,
            "freshAuthorized": False,
            "freshReason": None,
            "evidencePath": None,
        }
        if seat.observation is not None:
            row.update(
                {
                    "session": seat.observation.session,
                    "activity": seat.observation.activity,
                    "evidence": seat.observation.evidence,
                    "evidenceReasons": list(seat.observation.evidenceReasons),
                }
            )
            if seat.observation.degraded:
                degraded.append(
                    {
                        "logicalId": seat.logicalId,
                        "reasons": list(seat.observation.evidenceReasons),
                    }
                )

        if seat.plannedNodeId is not None and seat.nodeId is not None and seat.plannedNodeId != seat.nodeId:
            blocked.append(
                {
                    "logicalId": seat.logicalId,
                    "reason": "continuity_mismatch",
                    "remediation": "nodeId changed for the same logical seat; re-instantiate or re-prime",
                }
            )
            seat_rows.append(row)
            continue

        if seat.logicalId in fresh:
            row["expectedAction"] = "fresh-primed"
            row["freshAuthorized"] = True
            row["freshReason"] = fresh[seat.logicalId]
        elif seat.restorePolicy == "fresh_required":
            row["expectedAction"] = "awaiting-decision"
        elif seat.resumeTokenPresent is True:
            row["expectedAction"] = "resume-original"
        elif seat.restorePolicy == "n-a":
            row["expectedAction"] = "n-a"
        else:
            # false and unknown both require a human decision; unknown is not false
            row["expectedAction"] = "awaiting-decision"
        seat_rows.append(row)

    if blocked:
        decision = "blocked"
    elif any(row["expectedAction"] == "awaiting-decision" for row in seat_rows):
        decision = "needs-human"
    else:
        decision = "allow"

    return ContinuityPlan(
        decisionStatus=decision,
        seats=seat_rows,
        blockedSeats=blocked,
        explicitFreshSeats=sorted(fresh),
        degraded=degraded,
        runId=run_id,
        launchId=launch_id,
        intent=intent,
        generatedAt=generated_at,
    )


EXPECTED_TO_ACTUAL = {
    "resume-original": "resumed",
    "fresh-primed": "fresh-primed",
    "awaiting-decision": "awaiting-decision",
    "new": "ready",
    "n-a": "n-a",
}


def expected_outcome_map(plan_obj: ContinuityPlan) -> dict[str, str]:
    """The expected ``actualOutcome`` for each seat (single source for guards)."""
    return {
        seat["logicalId"]: EXPECTED_TO_ACTUAL[seat["expectedAction"]]
        for seat in plan_obj.seats
        if seat["expectedAction"] != "n-a"
    }


@dataclass(frozen=True)
class OutcomeCheck:
    ok: bool
    code: str | None
    mismatches: tuple[dict, ...] = ()

    def to_dict(self) -> dict:
        return fixture_mark(
            FIXTURE_ID,
            ok=self.ok,
            code=self.code,
            mismatches=[dict(item) for item in self.mismatches],
        )


def verify_outcomes(plan_obj: ContinuityPlan, actual: dict[str, str]) -> OutcomeCheck:
    """Compare per-seat ``actualOutcome`` with ``expectedAction``.

    Code precedence is deliberate:

    * expected resume-original but actual fresh-primed => ``continuity_mismatch``
      (RT-06: a fresh outcome is never silently read as resume);
    * an unauthorized fresh outcome while ``--fresh`` was used for some other
      seat => ``fresh_not_authorized`` (RT-07).
    """
    mismatches: list[dict] = []
    saw_unauthorized_fresh = False
    for seat in plan_obj.seats:
        seat_id = seat["logicalId"]
        expected = seat["expectedAction"]
        if expected == "n-a":
            continue
        wanted = EXPECTED_TO_ACTUAL[expected]
        observed = actual.get(seat_id)
        if observed is None:
            mismatches.append(
                {"logicalId": seat_id, "expected": expected, "actual": None, "reason": "missing_actual_outcome"}
            )
            continue
        if observed != wanted:
            reason = "expected_action_mismatch"
            if observed == "fresh-primed" and expected == "resume-original":
                reason = "fresh_primes_over_resume"
            if observed == "fresh-primed" and not seat.get("freshAuthorized"):
                if plan_obj.explicitFreshSeats:
                    saw_unauthorized_fresh = True
                if expected != "resume-original":
                    reason = "fresh_outside_authorized_set"
            mismatches.append(
                {"logicalId": seat_id, "expected": expected, "actual": observed, "reason": reason}
            )

    if not mismatches:
        return OutcomeCheck(True, None, ())

    if saw_unauthorized_fresh and plan_obj.explicitFreshSeats:
        code = "fresh_not_authorized"
    else:
        code = "continuity_mismatch"
    return OutcomeCheck(False, code, tuple(mismatches))


def default_outcomes(plan_obj: ContinuityPlan) -> dict[str, str]:
    """Deterministic 'everything went as planned' outcome map (for controls)."""
    mapping = {
        "resume-original": "resumed",
        "fresh-primed": "fresh-primed",
        "awaiting-decision": "awaiting-decision",
        "new": "ready",
        "n-a": "n-a",
    }
    return {
        seat["logicalId"]: mapping[seat["expectedAction"]] for seat in plan_obj.seats
    }
