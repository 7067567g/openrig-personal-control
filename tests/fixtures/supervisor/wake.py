# -*- coding: utf-8 -*-
"""F-07 — wake delivery with re-validation (D-023, D-046, D-014).

Two distinct staleness outcomes:

* ``stale_at_delivery`` — the live activity changed between creation and delivery;
* ``stale_episode``     — the wake was built from an older episode.

``activity=unknown`` is never read as ``idle`` or as healthy.
"""

from __future__ import annotations

from dataclasses import dataclass

from guards import fixture_mark
from observation import Observation

FIXTURE_ID = "F-07"

DELIVERY_STATUSES = ("delivered", "stale_at_delivery", "stale_episode", "deferred")


@dataclass(frozen=True)
class Wake:
    wakeId: str
    episode: int | None
    activityAtCreation: str | None
    createdAt: str
    target: str
    payload: str = ""


@dataclass(frozen=True)
class Delivery:
    status: str
    reason: str
    deliveredAt: str | None = None

    def to_dict(self) -> dict:
        return fixture_mark(
            FIXTURE_ID,
            status=self.status,
            reason=self.reason,
            deliveredAt=self.deliveredAt,
        )

    @property
    def delivered(self) -> bool:
        return self.status == "delivered"


def deliver(
    wake: Wake,
    *,
    now: str,
    live: Observation,
    episode: int | None = None,
) -> Delivery:
    """Deliver a wake only after re-validating the live observation."""
    if now < wake.createdAt:
        raise ValueError("now must not precede wake.createdAt")

    if wake.episode is not None:
        if episode is None:
            return Delivery("deferred", "episode_unknown")
        if episode != wake.episode:
            return Delivery("stale_episode", "episode_changed")

    if live.session != "present":
        return Delivery("deferred", "session_not_present")

    if live.activity in (None, "unknown"):
        # D-023: unknown is not idle and not healthy
        return Delivery("deferred", "activity_unknown")

    if wake.activityAtCreation is not None and live.activity != wake.activityAtCreation:
        return Delivery("stale_at_delivery", "activity_changed_at_delivery")

    return Delivery("delivered", "revalidated", deliveredAt=now)
