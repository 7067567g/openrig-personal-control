# -*- coding: utf-8 -*-
"""F-05 self-tests: A1..A5, D-032/D-033/D-037/D-045."""

from __future__ import annotations

import os

import pytest

from freeze import (
    FreezeError,
    StaleReview,
    capture,
    detect_claim_window_escape,
    digest_bundle,
    identity,
    self_diff,
    verify_compliance,
    verify_review_input,
)
from guards import is_fixture

CAPTURED_AT = "2023-11-15T00:00:00Z"
MTIME = 1700000000  # 2023-11-14T22:13:20Z


def write(base, name: str, content: str, mtime: int = MTIME):
    path = base / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


def freeze(base, names=("reports/a.md", "reports/b.md"), **kwargs):
    paths = [write(base, name, f"content of {name}") for name in names]
    return capture(
        base,
        paths,
        run_id=kwargs.pop("run_id", "run-1"),
        captured_at=kwargs.pop("captured_at", CAPTURED_AT),
        actor=kwargs.pop("actor", "fixture"),
        **kwargs,
    )


def test_capture_records_sha_bytes_and_mtime(tmp_path):
    frozen = freeze(tmp_path)
    assert [item.path for item in frozen.artifacts] == ["reports/a.md", "reports/b.md"]
    first = frozen.artifacts[0]
    assert first.bytes == len("content of reports/a.md")
    assert first.mtime == "2023-11-14T22:13:20Z"
    assert len(first.sha256) == 64
    assert is_fixture(frozen.to_dict())


def test_capture_before_last_write_fails_a1(tmp_path):
    path = write(tmp_path, "reports/a.md", "x")
    with pytest.raises(FreezeError, match="A1"):
        capture(tmp_path, [path], run_id="r", captured_at="2023-11-14T00:00:00Z", actor="f")


def test_capture_requires_artifacts(tmp_path):
    with pytest.raises(FreezeError):
        capture(tmp_path, [], run_id="r", captured_at=CAPTURED_AT, actor="f")


def test_capture_rejects_artifact_outside_base(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("x", encoding="utf-8")
    with pytest.raises(FreezeError):
        capture(base, [outside], run_id="r", captured_at=CAPTURED_AT, actor="f")


def test_capture_rejects_unknown_mode(tmp_path):
    path = write(tmp_path, "a.md", "x")
    with pytest.raises(FreezeError):
        capture(tmp_path, [path], run_id="r", captured_at=CAPTURED_AT, actor="f", mode="guess")


def test_self_diff_clean_is_rc_zero(tmp_path):
    frozen = freeze(tmp_path)
    diff = self_diff(frozen, tmp_path)
    assert diff.rc == 0
    assert diff.removed == ()
    assert diff.added == ()
    assert diff.fieldDiff == 0


def test_self_diff_detects_changed_content(tmp_path):
    frozen = freeze(tmp_path)
    write(tmp_path, "reports/a.md", "tampered")
    diff = self_diff(frozen, tmp_path)
    assert diff.rc == 1
    assert diff.fieldDiff == 1


def test_self_diff_detects_removed_artifact(tmp_path):
    frozen = freeze(tmp_path)
    (tmp_path / "reports/a.md").unlink()
    diff = self_diff(frozen, tmp_path)
    assert diff.removed == ("reports/a.md",)


def test_self_diff_detects_added_artifact(tmp_path):
    frozen = freeze(tmp_path)
    extra = write(tmp_path, "reports/extra.md", "new")
    diff = self_diff(frozen, tmp_path, extra_paths=[extra])
    assert diff.added == ("reports/extra.md",)


def test_verify_review_input_accepts_frozen_copy(tmp_path):
    frozen = freeze(tmp_path)
    assert verify_review_input(frozen, tmp_path) is None


def test_verify_review_input_rejects_live_diff(tmp_path):
    frozen = freeze(tmp_path)
    write(tmp_path, "reports/a.md", "changed after freeze")
    with pytest.raises(StaleReview) as excinfo:
        verify_review_input(frozen, tmp_path)
    assert "stale:reports/a.md" in excinfo.value.reasons


def test_verify_review_input_rejects_missing_file(tmp_path):
    frozen = freeze(tmp_path)
    (tmp_path / "reports/b.md").unlink()
    with pytest.raises(StaleReview) as excinfo:
        verify_review_input(frozen, tmp_path)
    assert "missing:reports/b.md" in excinfo.value.reasons


def test_new_content_with_old_mtime_is_detected_by_hash(tmp_path):
    frozen = freeze(tmp_path)
    path = tmp_path / "reports/a.md"
    path.write_text("new content", encoding="utf-8")
    os.utime(path, (MTIME, MTIME))  # mtime rollback must not help
    with pytest.raises(StaleReview):
        verify_review_input(frozen, tmp_path)


def test_identity_tuple_contains_run_relative_path_and_hash():
    payload = identity("run-1", "reports/a.md", "a" * 64, 3, CAPTURED_AT)
    assert is_fixture(payload)
    assert payload["runId"] == "run-1"
    assert payload["path"] == "reports/a.md"
    assert payload["bytes"] == 3


def compliant_bundle(tmp_path, *, mode="revision"):
    frozen = freeze(
        tmp_path,
        mode=mode,
        authorized_outputs=("reports/a.md", "reports/b.md"),
    )
    diff = self_diff(frozen, tmp_path)
    gate = {"cmd": "coverage_gate", "rc": 0, "evidenceSha256": "b" * 64}
    delta = {
        "decisionIds": ["D-S7-01"],
        "allowedPaths": ["reports/a.md", "reports/b.md"],
        "summary": "fixture",
    }
    return digest_bundle(frozen, diff=diff, gate=gate, authorized_delta=delta)


def test_full_bundle_is_compliant(tmp_path):
    result = verify_compliance(compliant_bundle(tmp_path))
    assert result.compliant is True
    assert result.reason == "compliant"


def test_hash_only_bundle_is_not_compliant(tmp_path):
    bundle = compliant_bundle(tmp_path)
    for key in ("selfDiff", "gate", "authorizedDelta"):
        bundle.pop(key)
    result = verify_compliance(bundle)
    assert result.compliant is False
    assert result.reason == "hash_only"


def test_initial_mode_without_authorized_outputs_fails(tmp_path):
    bundle = compliant_bundle(tmp_path, mode="initial")
    bundle.pop("authorizedOutputs")
    result = verify_compliance(bundle)
    assert result.compliant is False
    assert result.reason == "initial_missing_authorized_outputs"


def test_failed_self_diff_is_not_compliant(tmp_path):
    bundle = compliant_bundle(tmp_path)
    bundle["selfDiff"]["rc"] = 1
    assert verify_compliance(bundle).reason == "self_diff_failed"


def test_failed_gate_is_not_compliant(tmp_path):
    bundle = compliant_bundle(tmp_path)
    bundle["gate"]["rc"] = 1
    assert verify_compliance(bundle).reason == "gate_failed"


def test_authorized_delta_must_cover_artifacts(tmp_path):
    bundle = compliant_bundle(tmp_path)
    bundle["authorizedDelta"]["allowedPaths"] = ["reports/a.md"]
    assert verify_compliance(bundle).reason == "authorized_delta_mismatch"


def test_authorized_delta_requires_decision_ids(tmp_path):
    bundle = compliant_bundle(tmp_path)
    bundle["authorizedDelta"]["decisionIds"] = []
    assert verify_compliance(bundle).reason == "authorized_delta_mismatch"


def test_invalid_mode_is_rejected(tmp_path):
    bundle = compliant_bundle(tmp_path)
    bundle["mode"] = "whatever"
    assert verify_compliance(bundle).reason == "invalid_mode"


# -- RT-27 claim-window (A6) -------------------------------------------------

def test_claim_window_detects_rewrite_with_mtime_rollback(tmp_path):
    frozen = freeze(tmp_path)
    path = tmp_path / "reports/a.md"
    path.write_text("written after the packet closed", encoding="utf-8")
    os.utime(path, (MTIME, MTIME))  # roll mtime back: mtime alone must not clear it
    verdict = detect_claim_window_escape(frozen, tmp_path, closed_at=CAPTURED_AT)
    assert verdict.ok is False
    assert verdict.code == "claim_window_escape"
    assert "claim_window_escape:reports/a.md" in verdict.violations


def test_claim_window_clean_snapshot_has_no_violation(tmp_path):
    frozen = freeze(tmp_path)
    verdict = detect_claim_window_escape(frozen, tmp_path, closed_at=CAPTURED_AT)
    assert verdict.ok is True
    assert verdict.code is None
    assert verdict.violations == ()


def test_claim_window_missing_artifact_is_an_escape(tmp_path):
    frozen = freeze(tmp_path)
    (tmp_path / "reports/a.md").unlink()
    verdict = detect_claim_window_escape(frozen, tmp_path, closed_at=CAPTURED_AT)
    assert verdict.code == "claim_window_escape"
    assert "missing:reports/a.md" in verdict.violations


def test_claim_window_mtime_only_drift_is_recorded_not_an_escape(tmp_path):
    frozen = freeze(tmp_path)
    path = tmp_path / "reports/a.md"
    os.utime(path, (1700010000, 1700010000))  # 2023-11-15T01:00:00Z, after capture
    verdict = detect_claim_window_escape(frozen, tmp_path, closed_at=CAPTURED_AT)
    assert verdict.ok is True
    assert verdict.code is None
    assert verdict.mtimeDrift == ("late_write_identity:reports/a.md",)


# -- 00-plan §4 F-05 shaped API ---------------------------------------------

def test_plan_shaped_freeze_and_candidate_diff(tmp_path):
    from freeze import freeze

    a = write(tmp_path, "reports/a.md", "alpha")
    b = write(tmp_path, "reports/b.md", "beta")
    frozen = freeze([a, b], base=tmp_path, captured_at=CAPTURED_AT, actor="fixture")
    assert [item.path for item in frozen.artifacts] == ["reports/a.md", "reports/b.md"]
    assert self_diff(frozen, [a, b]).rc == 0
    assert verify_review_input(frozen, [a, b]) is None


def test_verify_review_input_accepts_a_mapping(tmp_path):
    frozen = freeze(tmp_path)
    mapping = {
        "reports/a.md": "content of reports/a.md",
        "reports/b.md": "content of reports/b.md",
    }
    assert verify_review_input(frozen, mapping) is None
    mapping["reports/a.md"] = "changed"
    with pytest.raises(StaleReview):
        verify_review_input(frozen, mapping)
