# -*- coding: utf-8 -*-
"""RT-13..RT-15 — archive incomplete / forged DSH / required-item mismatch.

The default path for this rig is ``runtime_applicability="n/a"`` (no DSH seat).
``stop`` must refuse before calling ``down`` when the gate is not COMPLETE.
"""

from __future__ import annotations

import json

import pytest

from archive import ArchiveTamper, gate, require_complete, stop_allowed

from helpers import build, complete_manifest, context, down


def _manifest(**over):
    base = {
        "archiveStatus": "COMPLETE",
        "dshSession": None,
        "sessions": ["main", "tdo"],
        "required": {
            "tasks": True,
            "research": True,
            "report": True,
            "sessions": True,
            "dsh": False,
        },
        "items": {
            "tasks": True,
            "research": True,
            "report": True,
            "sessions": True,
            "dsh": False,
        },
    }
    base.update(over)
    return base


# ---------------------------------------------------------------------------
# RT-13 — PARTIAL archive cannot stop and must not call down
# ---------------------------------------------------------------------------

def test_rt13_partial_archive_refuses_stop_before_down(tmp_path):
    ctx = context(tmp_path, archive_manifest={"archiveStatus": "PARTIAL"})
    sim = build(ctx, [down(ctx)], base=tmp_path)
    sim.state = "RUNNING"

    outcome = sim.stop()
    assert outcome.ok is False
    assert outcome.rc == 2
    assert outcome.code == "archive_incomplete"
    assert outcome.mutated is False
    assert sim.runner.calls == []
    assert sim.state == "RUNNING"


def test_rt13_control_complete_archive_calls_down_and_keeps_home(tmp_path):
    ctx = context(tmp_path, archive_manifest=complete_manifest())
    sentinel = ctx.home / "keep.txt"
    sentinel.write_text("owner data", encoding="utf-8")
    sim = build(ctx, [down(ctx)], base=tmp_path)
    sim.state = "RUNNING"

    outcome = sim.stop()
    assert outcome.ok is True, outcome.code
    assert sim.state == "STOPPED"
    assert [call.argv[1] for call in sim.runner.calls] == ["down"]
    assert sentinel.read_text(encoding="utf-8") == "owner data"


# ---------------------------------------------------------------------------
# RT-14 — no DSH seat: a forged DSH session is tampering, n/a is the default
# ---------------------------------------------------------------------------

def test_rt14_claimed_dsh_session_missing_from_inventory_is_tamper():
    result = gate(_manifest(dshSession="dsh-1"), runtime_applicability="n/a")
    assert result.ok is False
    assert "ArchiveTamper" in result.violations
    assert result.runtimeApplicability == "n/a"


def test_rt14_inflating_applicability_to_escape_n_a_is_tamper():
    result = gate(_manifest(), runtime_applicability="applicable")
    assert result.ok is False
    assert "ArchiveTamper" in result.violations


def test_rt14_required_dsh_without_a_dsh_seat_is_tamper():
    required = _manifest()["required"] | {"dsh": True}
    result = gate(_manifest(required=required))
    assert result.ok is False
    assert "ArchiveTamper" in result.violations


def test_rt14_control_genuine_n_a_is_complete():
    result = gate(_manifest())
    assert result.ok is True
    assert result.status == "COMPLETE"
    assert result.runtimeApplicability == "n/a"
    assert result.required["dsh"] is False
    assert result.n_a_reason


# ---------------------------------------------------------------------------
# RT-15 — COMPLETE must agree with required items
# ---------------------------------------------------------------------------

def test_rt15_complete_with_a_missing_required_item_is_red():
    items = _manifest()["items"] | {"report": False}
    result = gate(_manifest(items=items))
    assert result.ok is False
    assert "status_required_mismatch" in result.violations
    assert stop_allowed(result) is False


def test_rt15_control_all_required_items_true_is_complete():
    result = gate(_manifest())
    assert result.ok is True
    assert stop_allowed(result) is True


def test_rt15_require_complete_raises_for_partial():
    with pytest.raises(ArchiveTamper):
        require_complete(gate(_manifest(archiveStatus="PARTIAL")))


def test_rt13_stop_writes_manifest_archive_status_on_success(tmp_path):
    ctx = context(tmp_path, archive_manifest=complete_manifest())
    sim = build(ctx, [down(ctx)], base=tmp_path)
    sim.state = "RUNNING"
    outcome = sim.stop()
    assert outcome.ok is True, outcome.code
    path = ctx.run_dir / "reports" / "evidence" / "manifest" / "run-manifest.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["archive"]["archiveStatus"] == "COMPLETE"
