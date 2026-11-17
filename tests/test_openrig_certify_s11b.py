# -*- coding: utf-8 -*-
"""Focused regression tests for the S11-B live harness wrappers."""
from __future__ import annotations

import hashlib
import json
import sys

import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import openrig_certify_s11b as s11b  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_s10_globals():
    """Never let these unit tests mutate openrig_certify's shared module globals."""
    s11b.configure_s10()
    try:
        yield
    finally:
        s11b.restore_s10()


def _ctx(tmp_path: Path) -> dict:
    work = tmp_path / "openrig-s11b-cert-unit"
    ev = tmp_path / "evidence"
    ev.mkdir()
    home = work / "home"
    (home / "entry").mkdir(parents=True)
    return {
        "workDir": work,
        "home": home,
        "runDir": work / "run",
        "workspace": work / "workspace",
        "marker": work / "MARKER.json",
        "archiveRoot": work / "archive",
        "evidenceDir": ev,
        "attemptId": "unit-attempt",
        "attemptDir": ev / "attempts" / "unit-attempt",
        "port": 48210,
        "portBase": 48210,
        "portSpan": 10,
        "launchId": "unit-launch",
        "rigName": "openrig-s11b-cert-unit",
        "workflowId": "wf-unit",
        "seatId": "cert.cert",
        "seatPod": "cert",
        "seatMember": "cert",
        "seatSession": "cert-cert@openrig-s11b-cert-unit",
        "nonce": "a" * 32,
        "approvalPath": "",
        "approvalSha256": "",
    }


def _approval(tmp_path: Path, *, words: str = s11b.APPROVAL_WORDS) -> Path:
    now = datetime.now(timezone.utc)
    p = tmp_path / "approval.json"
    p.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "approvalId": "unit-approval",
                "actionClasses": [
                    "first_live_e2e",
                    "managed_lifecycle_mutation",
                    "archive_and_teardown",
                ],
                "approvedBy": "user (unit test)",
                "approvedAt": (now - timedelta(minutes=1)).isoformat(),
                "expiresAt": (now + timedelta(hours=1)).isoformat(),
                "executor": "lead (unit test)",
                "approvalSource": "unit test",
                "approvalWords": words,
                "llmSelfSigned": False,
            }
        ),
        encoding="utf-8",
    )
    return p


def _cmd(label: str) -> dict:
    return {
        "label": label,
        "argv": ["fixture", label],
        "rc": 0,
        "stdoutSha256": hashlib.sha256(b"").hexdigest(),
        "stderrSha256": hashlib.sha256(b"").hexdigest(),
        "stdoutBytes": 0,
        "stderrTail": [],
        "startedAt": "2026-11-18T00:00:00Z",
        "endedAt": "2026-11-18T00:00:00Z",
        "log": f"logs/{label}.out",
        "errLog": f"logs/{label}.err",
    }


def test_approval_row_passes_and_records_rc0(tmp_path):
    approval = _approval(tmp_path)
    ctx = _ctx(tmp_path)
    ctx["approvalPath"] = str(approval)
    ctx["approvalSha256"] = hashlib.sha256(approval.read_bytes()).hexdigest()
    cert = s11b.S11BCertifier(ctx)
    row = cert.s11b_05_approval()
    assert row["pass"] is True
    assert row["rc"] == 0
    assert row["error"] is None
    assert row["observed"]["approvalWordsExact"] is True
    assert row["observed"]["llmSelfSigned"] is False


def test_approval_row_rejects_wrong_words(tmp_path):
    approval = _approval(tmp_path, words="not the user text")
    ctx = _ctx(tmp_path)
    ctx["approvalPath"] = str(approval)
    ctx["approvalSha256"] = hashlib.sha256(approval.read_bytes()).hexdigest()
    cert = s11b.S11BCertifier(ctx)
    row = cert.s11b_05_approval()
    assert row["pass"] is False
    assert row["rc"] == 2
    assert row["error"]["code"] == "approval_invalid"


def test_harness_env_uses_explicit_loopback_bind(tmp_path):
    ctx = _ctx(tmp_path)
    cert = s11b.S11BCertifier(ctx)
    env = cert.env()
    assert env["OPENRIG_BIND_HOST"] == "127.0.0.1"
    assert "127.0.0.1" in env["NO_PROXY"].split(",")


def test_s11b_01_restores_ticket_with_module_helper(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path)
    approval = _approval(tmp_path)
    ctx["approvalPath"] = str(approval)
    ctx["approvalSha256"] = hashlib.sha256(approval.read_bytes()).hexdigest()
    launch = Path(ctx["home"]) / "entry" / "launch.json"
    launch.write_text(
        json.dumps({"launchId": "unit-launch", "phase": "active"}), encoding="utf-8"
    )
    cert = s11b.S11BCertifier(ctx)
    calls = {"restore": 0}

    def close_ticket():
        record = json.loads(launch.read_text(encoding="utf-8"))
        record["phase"] = "closed"
        launch.write_text(json.dumps(record), encoding="utf-8")
        return _cmd("close-ticket")

    real_restore = s11b.s10._restore_launch_phase

    def restore_spy(path, phase):
        calls["restore"] += 1
        return real_restore(path, phase)

    def http_json(method, port, path, body=None):
        del method, port, body
        return {
            "status": 403,
            "body": {"ok": False, "error": {"code": "entry_guard_http_denied"}},
            "path": path,
            "method": "POST",
            "startedAt": "2026-11-18T00:00:00Z",
            "endedAt": "2026-11-18T00:00:00Z",
        }

    monkeypatch.setattr(cert, "_close_ticket", close_ticket)
    monkeypatch.setattr(s11b.s10, "_http_json", http_json)
    monkeypatch.setattr(s11b.s10, "_restore_launch_phase", restore_spy)
    monkeypatch.setattr(
        cert,
        "_stale_launch_probe",
        lambda: {**_cmd("stale-launch"), "codeSeen": "entry_guard_expired", "rc": 2},
    )

    row = cert.s11b_01_entry_guard()

    assert row["pass"] is True, row
    assert row["rc"] == 0
    assert calls["restore"] == 1
    assert json.loads(launch.read_text(encoding="utf-8"))["phase"] == "active"
    assert row["observed"]["encodedMutationRc"] == 403
    assert row["observed"]["plainMutationRc"] == 403
    assert row["observed"]["staleLaunchRc"] == 2
