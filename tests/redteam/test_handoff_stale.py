# -*- coding: utf-8 -*-
"""RT-24..RT-26 — freeze/review barriers and projection-after-write.

A reviewer must diff an immutable copy, never the live path; a hash-only
bundle proves integrity, not compliance; ``mode=initial`` requires the
authorized output inventory rather than inferring it from disk.
"""

from __future__ import annotations

import os

import pytest

from freeze import (
    FreezeError,
    StaleReview,
    capture,
    digest_bundle,
    freeze,
    self_diff,
    verify_compliance,
    verify_review_input,
)

CAPTURED_AT = "2023-11-15T00:00:00Z"
MTIME = 1700000000  # 2023-11-14T22:13:20Z


def write(base, name, content, mtime=MTIME):
    path = base / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


def frozen_tree(tmp_path, *, mode="revision", authorized_outputs=None):
    a = write(tmp_path, "reports/a.md", "alpha")
    b = write(tmp_path, "reports/b.md", "beta")
    return freeze(
        [a, b],
        base=tmp_path,
        run_id="rt-run",
        captured_at=CAPTURED_AT,
        actor="redteam",
        mode=mode,
        authorized_outputs=authorized_outputs,
    )


# ---------------------------------------------------------------------------
# RT-24 — a post-freeze write makes the live review input stale
# ---------------------------------------------------------------------------

def test_rt24_handoff_post_freeze_write_is_stale_review(tmp_path):
    frozen = frozen_tree(tmp_path)
    write(tmp_path, "reports/a.md", "changed after freeze")
    with pytest.raises(StaleReview) as excinfo:
        verify_review_input(frozen, tmp_path)
    assert "stale:reports/a.md" in excinfo.value.reasons


def test_rt24_control_frozen_copy_passes(tmp_path):
    frozen = frozen_tree(tmp_path)
    assert verify_review_input(frozen, tmp_path) is None


def test_rt24_mtime_rollback_does_not_hide_new_content(tmp_path):
    frozen = frozen_tree(tmp_path)
    path = tmp_path / "reports/a.md"
    path.write_text("new content", encoding="utf-8")
    os.utime(path, (MTIME, MTIME))  # rollback must not help
    with pytest.raises(StaleReview):
        verify_review_input(frozen, tmp_path)


def test_rt24_missing_artifact_is_stale(tmp_path):
    frozen = frozen_tree(tmp_path)
    (tmp_path / "reports/b.md").unlink()
    with pytest.raises(StaleReview) as excinfo:
        verify_review_input(frozen, tmp_path)
    assert "missing:reports/b.md" in excinfo.value.reasons


# ---------------------------------------------------------------------------
# RT-25 — hash equality alone is not compliance
# ---------------------------------------------------------------------------

def compliant_bundle(tmp_path, *, mode="revision"):
    frozen = frozen_tree(tmp_path, mode=mode, authorized_outputs=("reports/a.md", "reports/b.md"))
    diff = self_diff(frozen, tmp_path)
    gate = {"cmd": "coverage_gate", "rc": 0, "evidenceSha256": "b" * 64}
    delta = {
        "decisionIds": ["D-RT-01"],
        "allowedPaths": ["reports/a.md", "reports/b.md"],
        "summary": "redteam fixture",
    }
    return digest_bundle(frozen, diff=diff, gate=gate, authorized_delta=delta)


def test_rt25_hash_only_bundle_is_not_compliant(tmp_path):
    bundle = compliant_bundle(tmp_path)
    for key in ("selfDiff", "gate", "authorizedDelta"):
        bundle.pop(key)
    result = verify_compliance(bundle)
    assert result.compliant is False
    assert result.reason == "hash_only"


def test_rt25_control_full_bundle_is_compliant(tmp_path):
    result = verify_compliance(compliant_bundle(tmp_path))
    assert result.compliant is True
    assert result.reason == "compliant"


def test_rt25_failed_self_diff_is_not_compliant(tmp_path):
    bundle = compliant_bundle(tmp_path)
    bundle["selfDiff"]["rc"] = 1
    assert verify_compliance(bundle).reason == "self_diff_failed"


def test_rt25_failed_gate_is_not_compliant(tmp_path):
    bundle = compliant_bundle(tmp_path)
    bundle["gate"]["rc"] = 1
    assert verify_compliance(bundle).reason == "gate_failed"


def test_rt25_authorized_delta_must_cover_artifacts(tmp_path):
    bundle = compliant_bundle(tmp_path)
    bundle["authorizedDelta"]["allowedPaths"] = ["reports/a.md"]
    assert verify_compliance(bundle).reason == "authorized_delta_mismatch"


# ---------------------------------------------------------------------------
# RT-26 — mode=initial must carry the authorized output inventory
# ---------------------------------------------------------------------------

def test_rt26_initial_without_authorized_outputs_is_rejected(tmp_path):
    bundle = compliant_bundle(tmp_path, mode="initial")
    bundle.pop("authorizedOutputs")
    result = verify_compliance(bundle)
    assert result.compliant is False
    assert result.reason == "initial_missing_authorized_outputs"


def test_rt26_control_initial_with_authorized_outputs_is_compliant(tmp_path):
    result = verify_compliance(compliant_bundle(tmp_path, mode="initial"))
    assert result.compliant is True


def test_rt26_capture_rejects_artifact_outside_base(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("x", encoding="utf-8")
    with pytest.raises(FreezeError):
        capture(base, [outside], run_id="r", captured_at=CAPTURED_AT, actor="rt")
