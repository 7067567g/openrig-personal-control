# -*- coding: utf-8 -*-
"""F-06 self-tests: IO-05 / CT-11 / D-S7-09 archive applicability."""

from __future__ import annotations

import pytest

from archive import ArchiveTamper, gate, require_complete, stop_allowed
from guards import is_fixture


def manifest(
    *,
    status="COMPLETE",
    dsh_session=None,
    sessions=("main", "tdo"),
    required=None,
    items=None,
):
    required = required or {
        "tasks": True,
        "research": True,
        "report": True,
        "sessions": True,
        "dsh": False,
    }
    items = items or {
        "tasks": True,
        "research": True,
        "report": True,
        "sessions": True,
        "dsh": False,
    }
    return {
        "archiveStatus": status,
        "dshSession": dsh_session,
        "sessions": list(sessions),
        "required": required,
        "items": items,
    }


def test_no_dsh_is_default_n_a_and_complete():
    result = gate(manifest())
    assert result.ok is True
    assert result.status == "COMPLETE"
    assert result.runtimeApplicability == "n/a"
    assert result.required["dsh"] is False
    assert result.n_a_reason
    assert result.violations == ()


def test_claimed_dsh_session_missing_from_inventory_is_tamper():
    result = gate(manifest(dsh_session="dsh-1"), runtime_applicability="n/a")
    assert result.ok is False
    assert "ArchiveTamper" in result.violations


def test_inflating_runtime_applicability_is_tamper():
    result = gate(manifest(), runtime_applicability="applicable")
    assert result.ok is False
    assert "ArchiveTamper" in result.violations


def test_partial_archive_cannot_stop():
    result = gate(manifest(status="PARTIAL"))
    assert result.ok is False
    assert "archive_incomplete" in result.violations
    assert stop_allowed(result) is False


def test_missing_archive_cannot_stop():
    result = gate(manifest(status="MISSING"))
    assert result.ok is False
    assert "archive_incomplete" in result.violations


def test_complete_status_with_missing_required_item_is_red():
    items = {"tasks": True, "research": True, "report": False, "sessions": True, "dsh": False}
    result = gate(manifest(items=items))
    assert result.ok is False
    assert "status_required_mismatch" in result.violations


def test_required_dsh_without_a_dsh_seat_is_tamper():
    required = {"tasks": True, "research": True, "report": True, "sessions": True, "dsh": True}
    result = gate(manifest(required=required))
    assert result.ok is False
    assert "ArchiveTamper" in result.violations


def test_genuine_dsh_applicability_can_pass():
    result = gate(
        manifest(
            dsh_session="dsh-1",
            sessions=("main", "dsh-1"),
            required={"tasks": True, "research": True, "report": True, "sessions": True, "dsh": True},
            items={"tasks": True, "research": True, "report": True, "sessions": True, "dsh": True},
        ),
        runtime_applicability="applicable",
    )
    assert result.ok is True
    assert result.runtimeApplicability == "applicable"


def test_forged_complete_with_dsh_in_sessions_is_still_tamper_for_this_rig():
    forged = manifest(
        dsh_session="session-forged",
        sessions=("main", "session-forged"),
        required={"tasks": True, "research": True, "report": True, "sessions": True, "dsh": True},
        items={"tasks": True, "research": True, "report": True, "sessions": True, "dsh": True},
    )
    result = gate(forged, runtime_applicability="n/a")
    assert result.ok is False
    assert "ArchiveTamper" in result.violations


def test_require_complete_raises_for_partial():
    with pytest.raises(ArchiveTamper):
        require_complete(gate(manifest(status="PARTIAL")))


def test_gate_payload_is_marked_and_carries_required_and_n_a_reason():
    payload = gate(manifest()).to_dict()
    assert is_fixture(payload)
    assert payload["required"]["dsh"] is False
    assert payload["n_a_reason"]
    assert payload["runtimeApplicability"] == "n/a"
