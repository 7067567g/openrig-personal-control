# -*- coding: utf-8 -*-
"""F-07 self-tests: D-023 / D-046 wake re-validation."""

from __future__ import annotations

import pytest

from guards import is_fixture
from observation import Sources, evaluate
from wake import Wake, deliver

NOW = "2026-01-01T00:01:00Z"
CREATED = "2026-01-01T00:00:00Z"


def live(activity="working", session="present"):
    if session != "present":
        return evaluate(Sources(session=session))
    return evaluate(Sources(session="present", hook_present=True, hook_activity=activity))


def wake(episode=1, activity="working"):
    return Wake("w-1", episode, activity, CREATED, "seat-main")


def test_matching_episode_and_activity_is_delivered():
    result = deliver(wake(), now=NOW, live=live("working"), episode=1)
    assert result.delivered is True
    assert result.status == "delivered"
    assert result.deliveredAt == NOW


def test_activity_changed_at_delivery_is_stale_at_delivery():
    result = deliver(wake(activity="working"), now=NOW, live=live("idle-at-prompt"), episode=1)
    assert result.status == "stale_at_delivery"
    assert result.delivered is False


def test_old_episode_is_stale_episode():
    result = deliver(wake(episode=1), now=NOW, live=live("working"), episode=2)
    assert result.status == "stale_episode"


def test_two_staleness_kinds_are_distinct():
    at_delivery = deliver(wake(activity="working"), now=NOW, live=live("idle-at-prompt"), episode=1)
    episode = deliver(wake(episode=1), now=NOW, live=live("working"), episode=2)
    assert at_delivery.status != episode.status


def test_unknown_activity_is_deferred_not_read_as_idle():
    result = deliver(wake(activity="idle-at-prompt"), now=NOW, live=live("unknown"), episode=1)
    assert result.status == "deferred"
    assert result.reason == "activity_unknown"
    assert result.delivered is False


def test_absent_session_is_deferred():
    result = deliver(wake(), now=NOW, live=live(session="absent"), episode=1)
    assert result.status == "deferred"
    assert result.reason == "session_not_present"


def test_future_now_is_rejected():
    with pytest.raises(ValueError):
        deliver(wake(), now="2025-12-31T23:59:59Z", live=live(), episode=1)


def test_wake_without_activity_at_creation_can_be_delivered():
    result = deliver(wake(activity=None), now=NOW, live=live("working"), episode=1)
    assert result.delivered is True


def test_missing_episode_is_deferred():
    result = deliver(wake(episode=1), now=NOW, live=live("working"), episode=None)
    assert result.status == "deferred"
    assert result.reason == "episode_unknown"


def test_delivery_payload_is_marked():
    assert is_fixture(deliver(wake(), now=NOW, live=live(), episode=1).to_dict())
