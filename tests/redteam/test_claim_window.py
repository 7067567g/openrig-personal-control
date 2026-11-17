# -*- coding: utf-8 -*-
"""RT-27 (A6) — claim-window escape: a post-close write is caught by hash.

mtime is auxiliary and may not be the sole evidence.  A rolled-back mtime does
not clear the escape; an mtime-only drift is recorded but is not an escape.
"""

from __future__ import annotations

import os

import pytest

from freeze import (
    StaleReview,
    detect_claim_window_escape,
    freeze,
    verify_review_input,
)

CAPTURED_AT = "2023-11-15T00:00:00Z"
MTIME = 1700000000


def write(base, name, content, mtime=MTIME):
    path = base / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


def frozen_tree(tmp_path):
    a = write(tmp_path, "reports/a.md", "alpha")
    b = write(tmp_path, "reports/b.md", "beta")
    return freeze([a, b], base=tmp_path, captured_at=CAPTURED_AT, actor="redteam")


def test_rt27_claim_window_rewrite_with_mtime_rollback_is_an_escape(tmp_path):
    frozen = frozen_tree(tmp_path)
    path = tmp_path / "reports/a.md"
    path.write_text("written after the packet closed", encoding="utf-8")
    os.utime(path, (MTIME, MTIME))  # rollback must not help

    verdict = detect_claim_window_escape(frozen, tmp_path, closed_at=CAPTURED_AT)
    assert verdict.ok is False
    assert verdict.code == "claim_window_escape"
    assert "claim_window_escape:reports/a.md" in verdict.violations
    assert verdict.mtimeDrift == ()


def test_rt27_control_clean_snapshot_has_no_violation(tmp_path):
    frozen = frozen_tree(tmp_path)
    verdict = detect_claim_window_escape(frozen, tmp_path, closed_at=CAPTURED_AT)
    assert verdict.ok is True
    assert verdict.code is None
    assert verdict.violations == ()
    assert verdict.mtimeDrift == ()


def test_rt27_missing_artifact_is_an_escape(tmp_path):
    frozen = frozen_tree(tmp_path)
    (tmp_path / "reports/b.md").unlink()
    verdict = detect_claim_window_escape(frozen, tmp_path, closed_at=CAPTURED_AT)
    assert verdict.ok is False
    assert verdict.code == "claim_window_escape"
    assert "missing:reports/b.md" in verdict.violations


def test_rt27_mtime_only_drift_is_recorded_not_an_escape(tmp_path):
    frozen = frozen_tree(tmp_path)
    path = tmp_path / "reports/a.md"
    os.utime(path, (MTIME + 7200, MTIME + 7200))  # same bytes, mtime after close
    verdict = detect_claim_window_escape(frozen, tmp_path, closed_at=CAPTURED_AT)
    assert verdict.ok is True
    assert verdict.code is None
    assert verdict.violations == ()
    assert "late_write_identity:reports/a.md" in verdict.mtimeDrift


def test_rt27_hash_snapshot_also_detects_the_same_write(tmp_path):
    frozen = frozen_tree(tmp_path)
    write(tmp_path, "reports/a.md", "changed")
    with pytest.raises(StaleReview):
        verify_review_input(frozen, tmp_path)
