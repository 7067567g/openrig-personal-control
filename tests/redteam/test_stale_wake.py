# -*- coding: utf-8 -*-
"""RT-16..RT-18 — stale wake delivery and unknown activity (D-023/D-046/D-014).

A wake is delivered only after re-validating the live observation.  The two
staleness kinds are distinct, and ``activity=unknown`` is never read as idle
or healthy.
"""

from __future__ import annotations

from observation import Sources, evaluate, judge_stall
from wake import Wake, deliver

NOW = "2026-01-01T00:01:00Z"
CREATED = "2026-01-01T00:00:00Z"


def live(activity="working", session="present"):
    if session != "present":
        return evaluate(Sources(session=session))
    return evaluate(Sources(session="present", hook_present=True, hook_activity=activity))


def wake(episode=1, activity="working"):
    return Wake("w-1", episode, activity, CREATED, "seat-main")


def test_rt16_stale_wake_activity_changed_at_delivery_is_stale_not_delivered():
    result = deliver(wake(activity="working"), now=NOW, live=live("idle-at-prompt"), episode=1)
    assert result.status == "stale_at_delivery"
    assert result.reason == "activity_changed_at_delivery"
    assert result.delivered is False


def test_rt16_control_same_activity_is_delivered():
    result = deliver(wake(activity="working"), now=NOW, live=live("working"), episode=1)
    assert result.status == "delivered"
    assert result.delivered is True
    assert result.deliveredAt == NOW


def test_rt17_old_episode_is_stale_episode():
    result = deliver(wake(episode=1), now=NOW, live=live("working"), episode=2)
    assert result.status == "stale_episode"
    assert result.reason == "episode_changed"
    assert result.delivered is False


def test_rt17_control_current_episode_is_delivered():
    result = deliver(wake(episode=2), now=NOW, live=live("working"), episode=2)
    assert result.status == "delivered"


def test_rt16_rt17_two_staleness_kinds_are_distinct():
    at_delivery = deliver(wake(activity="working"), now=NOW, live=live("idle-at-prompt"), episode=1)
    episode = deliver(wake(episode=1), now=NOW, live=live("working"), episode=2)
    assert at_delivery.status != episode.status


def test_rt18_unknown_activity_is_deferred_not_idle_or_healthy():
    result = deliver(wake(activity="idle-at-prompt"), now=NOW, live=live("unknown"), episode=1)
    assert result.status == "deferred"
    assert result.reason == "activity_unknown"
    assert result.delivered is False

    verdict = judge_stall(live("unknown"), queue_age_seconds=99999, threshold_seconds=60)
    assert verdict.health == "unknown"
    assert verdict.health != "healthy"
    assert verdict.stall is False


def test_rt18_control_working_activity_is_delivered_and_healthy():
    result = deliver(wake(activity="working"), now=NOW, live=live("working"), episode=1)
    assert result.status == "delivered"
    verdict = judge_stall(live("working"), queue_age_seconds=99999, threshold_seconds=60)
    assert verdict.health == "healthy"
    assert verdict.stall is False


def test_rt16_future_now_is_rejected():
    import pytest

    with pytest.raises(ValueError):
        deliver(wake(), now="2025-12-31T23:59:59Z", live=live(), episode=1)
