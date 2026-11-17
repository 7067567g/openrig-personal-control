# -*- coding: utf-8 -*-
"""F-03 — observation quality: session / activity / evidence (D-014..D-019).

The three axes are never mixed (CONTRACT §5):

* ``session``  — process presence: present|detached|exited|absent
* ``activity`` — working|idle-at-prompt|unknown, or ``None`` iff session != present
* ``evidence`` — oracle|observed|degraded, orthogonal to activity
* ``evidenceReasons`` — transport-layer reasons only, never ``oracle_unknown``
"""

from __future__ import annotations

from dataclasses import dataclass

from guards import fixture_mark

FIXTURE_ID = "F-03"

SESSIONS = ("present", "detached", "exited", "absent")
ACTIVITIES = ("working", "idle-at-prompt", "unknown")
EVIDENCE = ("oracle", "observed", "degraded")
REASON_ORDER = (
    "hook_missing",
    "relay_401",
    "relay_503",
    "ps_unavailable",
    "transcript_unreadable",
    "no_observation_path",
)
ALLOWED_REASONS = frozenset(REASON_ORDER)


class ObservationInvariant(ValueError):
    """Raised when an observation mixes axes (D-016..D-019)."""


@dataclass(frozen=True)
class Sources:
    """Raw observation inputs.

    ``ps_activity`` models a process-table source that can report activity;
    ``hook_activity`` is the oracle; ``transcript_activity`` is observed.
    """

    addressable: bool = True
    ps_available: bool = True
    session: str | None = None
    ps_activity: str | None = None
    hook_present: bool = False
    hook_activity: str | None = None
    transcript_readable: bool = True
    transcript_activity: str | None = None
    relay_status: int | None = None


@dataclass(frozen=True)
class Observation:
    session: str | None
    activity: str | None
    evidence: str
    evidenceReasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.session is not None and self.session not in SESSIONS:
            raise ObservationInvariant(f"bad session: {self.session!r}")
        if self.activity is not None and self.activity not in ACTIVITIES:
            raise ObservationInvariant(f"bad activity: {self.activity!r}")
        if self.evidence not in EVIDENCE:
            raise ObservationInvariant(f"bad evidence: {self.evidence!r}")
        bad = set(self.evidenceReasons) - ALLOWED_REASONS
        if bad:
            raise ObservationInvariant(f"reason(s) not allowed: {sorted(bad)}")
        # invariant 1: activity is None iff session != present
        if (self.activity is None) != (self.session != "present"):
            raise ObservationInvariant("activity must be None iff session != present (D-019)")
        # invariant 2: degraded iff reasons non-empty
        if (self.evidence == "degraded") != bool(self.evidenceReasons):
            raise ObservationInvariant("evidence=degraded iff evidenceReasons non-empty")
        # oracle is only claimable for a present session with a value
        if self.evidence == "oracle" and self.session != "present":
            raise ObservationInvariant("oracle evidence requires a present session")

    def to_dict(self) -> dict:
        return fixture_mark(
            FIXTURE_ID,
            session=self.session,
            activity=self.activity,
            evidence=self.evidence,
            evidenceReasons=list(self.evidenceReasons),
        )

    @property
    def degraded(self) -> bool:
        return self.evidence == "degraded"


def _ordered(reasons: set[str]) -> tuple[str, ...]:
    return tuple(reason for reason in REASON_ORDER if reason in reasons)


def evaluate(sources: Sources) -> Observation:
    """Evaluate one seat's observation quality."""
    if not sources.addressable:
        # invariant 6: no addressable source at all
        return Observation(None, None, "degraded", ("no_observation_path",))

    session: str | None
    if sources.ps_available:
        session = sources.session or "absent"
    elif sources.hook_activity is not None:
        session = "present"
    elif sources.transcript_activity is not None:
        session = "present"
    else:
        # invariant 6: nothing addressable produced a value
        return Observation(None, None, "degraded", ("no_observation_path",))

    if session != "present":
        # D-018: absence is an observation, not a degradation
        return Observation(session, None, "observed", ())

    reasons: set[str] = set()
    if not sources.ps_available:
        reasons.add("ps_unavailable")
    if sources.hook_activity is None:
        reasons.add("hook_missing")
    if sources.relay_status == 401:
        reasons.add("relay_401")
    elif sources.relay_status == 503:
        reasons.add("relay_503")
    if sources.transcript_readable is False:
        reasons.add("transcript_unreadable")

    activity: str | None = None
    source_kind: str | None = None
    for value, kind in (
        (sources.hook_activity, "oracle"),
        (sources.ps_activity, "observed"),
        (sources.transcript_activity, "observed"),
    ):
        if value is not None:
            activity = value
            source_kind = kind
            break

    if activity is None:
        # invariant 4: honest unknown; never substitute idle-at-prompt
        activity = "unknown"
        source_kind = "observed"

    if reasons:
        evidence = "degraded"
    elif source_kind == "oracle":
        evidence = "oracle"
    else:
        evidence = "observed"

    return Observation(session, activity, evidence, _ordered(reasons))


@dataclass(frozen=True)
class StallVerdict:
    stall: bool
    health: str
    reason: str

    def to_dict(self) -> dict:
        return fixture_mark(FIXTURE_ID, stall=self.stall, health=self.health, reason=self.reason)


def judge_stall(
    observation: Observation,
    *,
    queue_age_seconds: float,
    threshold_seconds: float = 300.0,
) -> StallVerdict:
    """D-014: queue age alone never decides a stall."""
    if observation.session != "present":
        health = "unknown" if observation.session is None else "absent"
        return StallVerdict(False, health, "no_session")
    if observation.activity == "working":
        health = "degraded" if observation.degraded else "healthy"
        return StallVerdict(False, health, "live_activity")
    if observation.activity in (None, "unknown"):
        return StallVerdict(False, "unknown", "activity_unknown")
    # idle-at-prompt
    if queue_age_seconds > threshold_seconds:
        return StallVerdict(True, "stalled", "idle_over_threshold")
    health = "degraded" if observation.degraded else "healthy"
    return StallVerdict(False, health, "idle_within_threshold")
