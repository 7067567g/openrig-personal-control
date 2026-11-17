# -*- coding: utf-8 -*-
"""P0 stop lease: refresh the same launch record around `rig down`.

The stop gate is already archive-gated. These tests cover the second, independent
admission boundary: once the daemon's original 30-minute launch TTL has elapsed, the
supervisor may grant a short lease by rewriting the *same* launchId, then must close it
again after the raw down attempt (success or failure).
"""
from __future__ import annotations

import hashlib
import json
import stat
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

WG = Path(__file__).resolve().parents[1]
for extra in (WG / "scripts", WG / "tests" / "fixtures" / "s9"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import openrig_continuity as oc  # noqa: E402
import openrig_manifest as om  # noqa: E402
import provision_continuity as prov  # noqa: E402

TOKEN = "stop-lease-test-token-do-not-report"
PAST_EXPIRES_AT = "2000-01-01T00:30:00Z"
INVALID_UTF8 = b'\x80\x81{"phase":"active"}\n'
CONSUMED_EVENT = {"verb": "daemon-start", "at": "2026-01-01T00:00:00Z", "pid": 123}


def bind_complete_archive(run: Path) -> Path:
    """Bind the fixture's COMPLETE claim to a real, hash-covered product archive."""
    run = Path(run)
    bridge = json.loads((run / "openrig" / "OPENRIG-BRIDGE.json").read_text(encoding="utf-8"))
    run_id = str(bridge["runId"])
    machine_root = run / "test-product-archive" / "machines" / "machine-a"
    archive_dir = machine_root / "runs" / run_id
    archive_dir.mkdir(parents=True, exist_ok=True)
    artifact = archive_dir / "RECORD.md"
    artifact.write_text("# fixture product archive\n", encoding="utf-8")
    artifact_sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    product_manifest = archive_dir / "MANIFEST.json"
    product_manifest.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "archiveStatus": "COMPLETE",
                "runId": run_id,
                "required": {
                    "runSnapshot": True,
                    "sessionSnapshots": False,
                    "transcriptCapture": True,
                    "openrigState": True,
                    "homeSnapshot": True,
                },
                "notApplicable": {"sessionSnapshots": True},
                "missing": [],
                "files": [
                    {
                        "path": "RECORD.md",
                        "bytes": artifact.stat().st_size,
                        "sha256": artifact_sha,
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (archive_dir / "SHA256SUMS").write_text(
        f"{artifact_sha}  RECORD.md\n", encoding="utf-8"
    )
    binding = run / "reports" / "evidence" / "archive" / "ARCHIVE-MANIFEST.json"
    binding.parent.mkdir(parents=True, exist_ok=True)
    binding.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "runId": run_id,
                "status": "COMPLETE",
                "reason": "fixture archive bound to a real product archive",
                "manifestPath": str(product_manifest),
                "manifestSha256": hashlib.sha256(product_manifest.read_bytes()).hexdigest(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return run


def tree_fingerprint(root: Path) -> dict:
    """File bytes plus mtime so a dry-run that rewrites identical bytes is visible."""
    return {
        str(path.relative_to(root)): (
            path.stat().st_size,
            hashlib.sha256(path.read_bytes()).hexdigest(),
            path.stat().st_mtime_ns,
        )
        for path in sorted(Path(root).rglob("*"))
        if path.is_file()
    }


def _stopped_state():
    return {
        "daemonState": "stopped",
        "rigState": "stopped",
        "workflowInstanceId": "wf-stop-lease",
        "seats": [
            prov.seat(
                "at-main",
                token=True,
                session="absent",
                startup="missing",
            )
        ],
    }


def _managed_run(
    tmp_path: Path,
    name: str,
    *,
    phase: str = "active",
    expires_at: str = PAST_EXPIRES_AT,
    archive: str | None = "COMPLETE",
    record_overrides: dict | None = None,
    launch_exists: bool = True,
    marker_exists: bool = True,
):
    """Build a fixture run plus an S1 managed home and one launch record."""
    run = prov.build_run(tmp_path, name, state=_stopped_state(), archive=archive)
    if str(archive or "").upper() == "COMPLETE":
        bind_complete_archive(run)
    bridge, err = oc.load_bundle(run)
    assert err is None
    home = Path(bridge["openrigHome"])
    entry = home / "entry"
    entry.mkdir(parents=True, exist_ok=True)
    marker = {
        "schemaVersion": 1,
        "runId": bridge["runId"],
        "rigName": bridge["rigName"],
    }
    if marker_exists:
        (entry / "managed-run.json").write_text(
            json.dumps(marker, indent=2) + "\n", encoding="utf-8"
        )

    launch_path = entry / "launch.json"
    launch = {
        "schemaVersion": 1,
        "launchId": "launch-stop-lease-001",
        "home": str(home.resolve()),
        "runId": bridge["runId"],
        "rigName": bridge["rigName"],
        "workflowId": bridge["workflowId"],
        "verbs": ["daemon-start", "up", "workflow-run"],
        "consumed": [dict(CONSUMED_EVENT)],
        "phase": phase,
        "dryRun": False,
        "createdAt": "2026-01-01T00:00:00Z",
        "expiresAt": expires_at,
        # Present so the no-token-in-report assertion is meaningful.
        "token": TOKEN,
    }
    if record_overrides:
        launch.update(record_overrides)
    if launch_exists:
        launch_path.write_text(json.dumps(launch, indent=2) + "\n", encoding="utf-8")
        launch_path.chmod(0o644)
    return run, bridge, home, launch_path


def _iso(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _fake_run(monkeypatch, *, rc: int = 0, on_down=None):
    calls: list[list[str]] = []
    real_run = oc._run if hasattr(oc, "_run") else None

    def fake(cmd, bridge, timeout=120):
        calls.append(list(cmd))
        if cmd[1:2] == ["down"] and on_down is not None:
            on_down(cmd, bridge, timeout)
        return subprocess.CompletedProcess(cmd, rc, "", "fixture down failed" if rc else "")

    monkeypatch.setattr(oc, "_run", fake)
    return calls, real_run


@pytest.mark.parametrize("phase", ["active", "closed"])
def test_prepare_stop_lease_reactivates_same_launch_and_records_archive(tmp_path, phase):
    run, bridge, _home, launch_path = _managed_run(
        tmp_path, f"LEASE-{phase}", phase=phase, expires_at=PAST_EXPIRES_AT
    )
    before = json.loads(launch_path.read_text(encoding="utf-8"))
    assert before["phase"] == phase
    assert _iso(before["expiresAt"]) < datetime.now(timezone.utc)
    archive = oc.archive_status(run)
    assert archive["status"] == "COMPLETE"

    result = oc.prepare_stop_lease(run, bridge, archive, ttl_seconds=120)

    assert result["status"] == "prepared"
    assert result["launchId"] == "launch-stop-lease-001"
    assert result["path"] == str(launch_path)
    record = json.loads(launch_path.read_text(encoding="utf-8"))
    assert record["launchId"] == "launch-stop-lease-001"
    assert record["phase"] == "active"
    assert record["previousPhase"] == phase
    assert record["previousExpiresAt"] == PAST_EXPIRES_AT
    assert record["expiresAt"] == record["leaseExpiresAt"] == result["leaseExpiresAt"]
    now = datetime.now(timezone.utc)
    expires = _iso(record["expiresAt"])
    assert now + timedelta(seconds=90) < expires <= now + timedelta(seconds=125)

    lease = record["stopLease"]
    assert lease["launchId"] == "launch-stop-lease-001"
    assert lease["reason"] == "run-stop"
    assert lease["archiveStatus"] == "COMPLETE"
    assert lease["archiveManifest"] == archive["path"]
    expected_sha = hashlib.sha256(Path(archive["path"]).read_bytes()).hexdigest()
    assert lease["archiveManifestSha256"] == expected_sha == result["archiveManifestSha256"]
    assert lease["runId"] == bridge["runId"]
    assert lease["rigName"] == bridge["rigName"]
    assert lease["previousPhase"] == phase
    assert lease["previousExpiresAt"] == PAST_EXPIRES_AT
    assert _iso(lease["grantedAt"]) <= _iso(lease["expiresAt"])
    # Other launch fields must survive the rewrite.
    assert record["verbs"] == ["daemon-start", "up", "workflow-run"]
    assert record["consumed"] == [CONSUMED_EVENT]
    assert stat.S_IMODE(launch_path.stat().st_mode) == 0o600


def test_close_stop_lease_closes_same_launch_with_mode_0600(tmp_path):
    run, bridge, _home, launch_path = _managed_run(tmp_path, "LEASE-CLOSE")
    lease = oc.prepare_stop_lease(run, bridge, oc.archive_status(run), ttl_seconds=120)

    closed = oc.close_stop_lease(run, bridge, lease, reason="down rc=0")

    assert closed["status"] == "closed"
    assert closed["launchId"] == lease["launchId"]
    record = json.loads(launch_path.read_text(encoding="utf-8"))
    assert record["launchId"] == lease["launchId"]
    assert record["phase"] == "closed"
    assert record["closedReason"] == "down rc=0"
    assert record["closedAt"]
    assert stat.S_IMODE(launch_path.stat().st_mode) == 0o600


def test_close_stop_lease_skips_when_the_record_is_gone(tmp_path):
    run, bridge, _home, launch_path = _managed_run(tmp_path, "LEASE-CLOSE-MISSING")
    lease = oc.prepare_stop_lease(run, bridge, oc.archive_status(run), ttl_seconds=120)
    launch_path.unlink()

    result = oc.close_stop_lease(run, bridge, lease, reason="down rc=0")

    assert result["status"] == "skipped"
    assert result["launchId"] == lease["launchId"]
    assert not launch_path.exists()


def test_close_stop_lease_never_overwrites_a_new_launch(tmp_path):
    run, bridge, _home, launch_path = _managed_run(tmp_path, "LEASE-NEW")
    lease = oc.prepare_stop_lease(run, bridge, oc.archive_status(run), ttl_seconds=120)

    new_record = {
        "schemaVersion": 1,
        "launchId": "launch-after-stop",
        "phase": "starting",
        "runId": bridge["runId"],
        "home": str(Path(bridge["openrigHome"]).resolve()),
    }
    launch_path.write_text(json.dumps(new_record, indent=2) + "\n", encoding="utf-8")
    before = launch_path.read_bytes()

    result = oc.close_stop_lease(run, bridge, lease, reason="down rc=0")

    assert result["status"] == "skipped"
    assert launch_path.read_bytes() == before
    assert json.loads(launch_path.read_text(encoding="utf-8"))["launchId"] == "launch-after-stop"


@pytest.mark.parametrize("down_rc", [0, 2])
def test_run_stop_prepares_before_down_and_closes_after_either_outcome(
    tmp_path, monkeypatch, down_rc
):
    run, bridge, _home, launch_path = _managed_run(tmp_path, f"LEASE-STOP-{down_rc}")
    observed_at_down = {}

    def on_down(cmd, _bridge, _timeout):
        record = json.loads(launch_path.read_text(encoding="utf-8"))
        observed_at_down.update(record)

    calls, _ = _fake_run(monkeypatch, rc=down_rc, on_down=on_down)

    report = oc.run_stop(run)

    assert [call[1:2] for call in calls] == [["down"]]
    assert observed_at_down["launchId"] == "launch-stop-lease-001"
    assert observed_at_down["phase"] == "active"
    assert observed_at_down["stopLease"]["reason"] == "run-stop"
    assert observed_at_down["stopLease"]["archiveStatus"] == "COMPLETE"

    record = json.loads(launch_path.read_text(encoding="utf-8"))
    assert record["launchId"] == "launch-stop-lease-001"
    assert record["phase"] == "closed"
    auth = report["stopAuthorization"]
    assert auth["status"] == "prepared"
    assert auth["leaseClosed"]["status"] == "closed"
    if down_rc == 0:
        assert report["ok"] is True and report["rc"] == 0
    else:
        assert report["ok"] is False
        assert report["rc"] == 2
        assert report["error"]["code"] == "down_failed"
    assert TOKEN not in json.dumps(report)


@pytest.mark.parametrize(
    "overrides",
    [
        {"home": "/definitely/not/this/home"},
        {"runId": "some-other-run"},
        {"launchId": ""},
        {"dryRun": True},
        {"dryRun": "true"},
        {"dryRun": 1},
        {"dryRun": 0},
        {"dryRun": None},
    ],
)
def test_prepare_stop_lease_refuses_bad_managed_records_without_modifying(
    tmp_path, overrides
):
    run, bridge, _home, launch_path = _managed_run(
        tmp_path, "LEASE-BAD", record_overrides=overrides
    )
    before = launch_path.read_bytes()

    result = oc.prepare_stop_lease(run, bridge, oc.archive_status(run), ttl_seconds=120)

    assert result["status"] == "error"
    assert result["code"]
    assert result["message"]
    assert launch_path.read_bytes() == before




@pytest.mark.parametrize("include_dry_run", [True, False])
def test_prepare_stop_lease_accepts_false_or_absent_dry_run(tmp_path, include_dry_run):
    run, bridge, _home, launch_path = _managed_run(
        tmp_path, f"LEASE-DRY-FLAG-{include_dry_run}"
    )
    if not include_dry_run:
        record = json.loads(launch_path.read_text(encoding="utf-8"))
        record.pop("dryRun", None)
        launch_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        launch_path.chmod(0o644)

    result = oc.prepare_stop_lease(run, bridge, oc.archive_status(run), ttl_seconds=120)

    assert result["status"] == "prepared"
    record = json.loads(launch_path.read_text(encoding="utf-8"))
    assert record["phase"] == "active"


def test_run_stop_missing_managed_launch_fails_closed_before_down(tmp_path, monkeypatch):
    run, _bridge, _home, launch_path = _managed_run(
        tmp_path, "LEASE-MISSING-RECORD", launch_exists=False
    )
    assert not launch_path.exists()

    def forbidden_run(*_args, **_kwargs):
        pytest.fail("raw down must not run when managed launch authorization fails")

    monkeypatch.setattr(oc, "_run", forbidden_run)

    report = oc.run_stop(run)

    assert report["ok"] is False
    assert report["rc"] == 2
    assert report["error"]["code"] == "stop_authorization_failed"
    assert report["mutations"] == []
    assert report["stopAuthorization"]["status"] == "error"
    assert not launch_path.exists()
    assert TOKEN not in json.dumps(report)


def test_non_managed_fixture_home_is_skipped_and_existing_stop_flow_continues(
    tmp_path, monkeypatch
):
    run, _bridge, home, launch_path = _managed_run(
        tmp_path, "LEASE-UNMANAGED", marker_exists=False, launch_exists=False
    )
    assert not (home / "entry" / "managed-run.json").exists()
    calls, _ = _fake_run(monkeypatch, rc=0)

    report = oc.run_stop(run)

    assert report["ok"] is True
    assert [call[1:2] for call in calls] == [["down"]]
    assert report["stopAuthorization"]["status"] == "skipped"
    assert not launch_path.exists()


@pytest.mark.parametrize("archive_status", ["MISSING", "INCOMPLETE"])
def test_archive_gate_runs_before_stop_lease_and_down(
    tmp_path, monkeypatch, archive_status
):
    run, _bridge, _home, launch_path = _managed_run(
        tmp_path, f"LEASE-GATE-{archive_status}", archive=archive_status
    )
    before = launch_path.read_bytes()

    def forbidden(*_args, **_kwargs):
        pytest.fail("no lease or raw down may happen before the archive gate passes")

    monkeypatch.setattr(oc, "prepare_stop_lease", forbidden)
    monkeypatch.setattr(oc, "_run", forbidden)

    report = oc.run_stop(run)

    assert report["ok"] is False
    assert report["rc"] == 2
    assert report["error"]["code"] == "archive_incomplete"
    assert report["archive"]["status"] in {"MISSING", "INCOMPLETE"}
    assert "stopAuthorization" not in report
    assert launch_path.read_bytes() == before


def test_atomic_write_private_uses_unique_temp_and_leaves_collision_alone(tmp_path):
    run, bridge, _home, launch_path = _managed_run(tmp_path, "LEASE-UNIQUE-TEMP")
    fixed_tmp = launch_path.with_name("launch.json.tmp")
    fixed_tmp.mkdir()

    result = oc.prepare_stop_lease(run, bridge, oc.archive_status(run), ttl_seconds=120)

    assert result["status"] == "prepared"
    assert fixed_tmp.is_dir()
    entry = launch_path.parent
    assert sorted(path.name for path in entry.iterdir()) == [
        "launch.json",
        "launch.json.tmp",
        "managed-run.json",
    ]


def test_dry_run_writes_no_lease_and_calls_no_down(tmp_path, monkeypatch):
    run, _bridge, _home, launch_path = _managed_run(tmp_path, "LEASE-DRY-RUN")
    before = launch_path.read_bytes()

    def forbidden(*_args, **_kwargs):
        pytest.fail("dry-run stop must not prepare a lease or invoke rig down")

    monkeypatch.setattr(oc, "prepare_stop_lease", forbidden)
    monkeypatch.setattr(oc, "_run", forbidden)

    report = oc.run_stop(run, dry_run=True)

    assert report["ok"] is True
    assert report["rc"] == 0
    assert report["dryRun"] is True
    assert report["mutations"] == []
    assert report["stopAuthorization"]["status"] == "dry-run"
    assert launch_path.read_bytes() == before

def test_prepare_invalid_utf8_launch_fails_closed_before_down(tmp_path, monkeypatch):
    run, bridge, _home, launch_path = _managed_run(tmp_path, "LEASE-INVALID-UTF8")
    launch_path.write_bytes(INVALID_UTF8)
    before = launch_path.read_bytes()

    prepared = oc.prepare_stop_lease(run, bridge, oc.archive_status(run), ttl_seconds=120)

    assert prepared["status"] == "error"
    assert prepared["code"] == "launch_record_invalid"
    assert prepared["message"]
    assert launch_path.read_bytes() == before

    calls: list[list[str]] = []

    def forbidden_run(cmd, _bridge, _timeout=120):
        calls.append(list(cmd))
        pytest.fail("invalid UTF-8 launch must not reach raw down")

    monkeypatch.setattr(oc, "_run", forbidden_run)
    report = oc.run_stop(run)

    assert calls == []
    assert report["ok"] is False
    assert report["rc"] == 2
    assert report["error"]["code"] == "stop_authorization_failed"
    assert report["mutations"] == []
    assert report["stopAuthorization"]["status"] == "error"
    assert report["stopAuthorization"]["code"] == "launch_record_invalid"


def test_close_stop_lease_invalid_utf8_returns_structured_error(tmp_path):
    run, bridge, _home, launch_path = _managed_run(tmp_path, "LEASE-CLOSE-UTF8")
    lease = oc.prepare_stop_lease(run, bridge, oc.archive_status(run), ttl_seconds=120)
    launch_path.write_bytes(INVALID_UTF8)

    result = oc.close_stop_lease(run, bridge, lease, reason="down rc=0")

    assert result["status"] == "error"
    assert result["code"] == "launch_record_invalid"
    assert result["message"]
    assert launch_path.read_bytes() == INVALID_UTF8


@pytest.mark.parametrize("down_rc", [0, 2])
def test_run_stop_reports_close_error_when_down_corrupts_launch(
    tmp_path, monkeypatch, down_rc
):
    run, _bridge, _home, launch_path = _managed_run(
        tmp_path, f"LEASE-CLOSE-AFTER-DOWN-{down_rc}"
    )

    def corrupt_after_down(_cmd, _bridge, _timeout):
        launch_path.write_bytes(INVALID_UTF8)

    calls, _ = _fake_run(monkeypatch, rc=down_rc, on_down=corrupt_after_down)

    report = oc.run_stop(run)

    assert [call[1:2] for call in calls] == [["down"]]
    auth = report["stopAuthorization"]
    assert auth["status"] == "prepared"
    assert auth["leaseClosed"]["status"] == "error"
    assert auth["leaseClosed"]["code"] == "launch_record_invalid"
    assert launch_path.read_bytes() == INVALID_UTF8
    if down_rc == 0:
        assert report["ok"] is True
        assert report["rc"] == 0
    else:
        assert report["ok"] is False
        assert report["rc"] == 2
        assert report["error"]["code"] == "down_failed"



def test_stop_down_failure_redacts_launch_id_and_record_token(tmp_path, monkeypatch):
    run, _bridge, _home, launch_path = _managed_run(
        tmp_path, "LEASE-STOP-REDACT"
    )
    record = json.loads(launch_path.read_text(encoding="utf-8"))
    launch_id = record["launchId"]

    def fake_down(cmd, _bridge, timeout=120):
        del timeout
        assert cmd[1:2] == ["down"]
        return subprocess.CompletedProcess(
            cmd,
            2,
            f"down stdout launch={launch_id} token={TOKEN}\n",
            f"down stderr launch={launch_id} token={TOKEN}\n",
        )

    monkeypatch.setattr(oc, "_run", fake_down)

    report = oc.run_stop(run)

    assert report["ok"] is False
    assert report["error"]["code"] == "down_failed"
    detail = report["error"]["message"]
    assert "<redacted>" in detail
    assert launch_id not in detail
    assert TOKEN not in detail
    assert TOKEN not in json.dumps(report)

    manifest_text = (
        run / "reports" / "evidence" / "manifest" / "run-manifest.json"
    ).read_text(encoding="utf-8")
    receipt_text = (run / "reports" / "evidence" / "stop-receipt.json").read_text(
        encoding="utf-8"
    )
    assert TOKEN not in manifest_text
    assert TOKEN not in receipt_text
    manifest = json.loads(manifest_text)
    assert manifest["status"] == "failed"
    assert manifest["seats"]
    assert {Path(out["path"]).name for out in manifest["outputs"]} == {
        "ARCHIVE-MANIFEST.json",
        "stop-receipt.json",
    }


def test_stop_authorization_message_redacts_record_runid_token(tmp_path):
    run, _bridge, _home, _launch_path = _managed_run(
        tmp_path,
        "LEASE-STOP-AUTH-REDACT",
        record_overrides={"runId": TOKEN, "token": TOKEN},
    )

    report = oc.run_stop(run)

    assert report["ok"] is False
    assert report["error"]["code"] == "stop_authorization_failed"
    assert "<redacted>" in report["error"]["message"]
    auth = report["stopAuthorization"]
    assert auth["status"] == "error"
    assert "<redacted>" in auth["message"]
    assert TOKEN not in auth["message"]
    assert TOKEN not in json.dumps(report)


def test_stop_mutation_argv_is_redacted(tmp_path, monkeypatch):
    run, _bridge, _home, _launch_path = _managed_run(
        tmp_path, "LEASE-STOP-ARGV-REDACT"
    )
    bridge_path = run / "openrig" / "OPENRIG-BRIDGE.json"
    bridge_payload = json.loads(bridge_path.read_text(encoding="utf-8"))
    bridge_payload["rigName"] = f"rig-{TOKEN}"
    bridge_path.write_text(json.dumps(bridge_payload, indent=2) + "\n", encoding="utf-8")

    def fake_down(cmd, _bridge, timeout=120):
        del timeout
        assert cmd[1:2] == ["down"]
        return subprocess.CompletedProcess(cmd, 2, "", "down failed\n")

    monkeypatch.setattr(oc, "_run", fake_down)

    report = oc.run_stop(run)

    assert report["error"]["code"] == "down_failed"
    argv = report["mutations"][0]["argv"]
    assert any("<redacted>" in part for part in argv)
    assert all(TOKEN not in part for part in argv)
    assert TOKEN not in json.dumps(report)


# ------------------------------------------------------------------ S1-4 / S2-4
@pytest.mark.parametrize(
    ("archive_status", "expected_ok", "expected_rc"),
    [("COMPLETE", True, 0), ("INCOMPLETE", False, 2)],
)
def test_stop_dry_run_writes_nothing_and_preserves_prior_seat_evidence(
    tmp_path, monkeypatch, archive_status, expected_ok, expected_rc
):
    run, bridge, _home, _launch_path = _managed_run(
        tmp_path, f"LEASE-DRY-FINGERPRINT-{archive_status}", archive=archive_status
    )
    prior_seat = {
        "logicalId": "at-main",
        "canonicalSessionName": "at-main@fixture",
        "expectedAction": "resume-original",
        "actualOutcome": "resumed",
        "session": "present",
        "activity": "working",
        "evidence": "observed",
    }
    prior = om.new_manifest(run, bridge, launch_id="launch-prior-stop-evidence")
    prior["workflow"]["instanceId"] = "wf-prior-stop"
    om.finalize_manifest(prior, status="active", seats=[prior_seat])
    om.write_manifest(run, prior)
    om.write_receipt(
        run,
        oc.STOP_RECEIPT_REL,
        {
            "schemaVersion": 1,
            "kind": "stop-receipt",
            "status": "active",
            "workflow": {"instanceId": "wf-prior-stop"},
            "seats": [prior_seat],
        },
    )
    prior_manifest_bytes = (run / om.MANIFEST_REL).read_bytes()
    prior_manifest_loaded = json.loads(prior_manifest_bytes)
    prior_normalized_seat = prior_manifest_loaded["seats"][0]
    before = tree_fingerprint(run)

    def forbidden(*_args, **_kwargs):
        pytest.fail("dry-run stop must not prepare a lease or invoke a child")

    monkeypatch.setattr(oc, "prepare_stop_lease", forbidden)
    monkeypatch.setattr(oc, "_run", forbidden)

    report = oc.run_stop(run, dry_run=True)

    assert report["ok"] is expected_ok, report
    assert report["rc"] == expected_rc
    assert report["mutations"] == []
    assert report["writes"] == []
    assert tree_fingerprint(run) == before, "stop --dry-run must write nothing at all"
    assert (run / om.MANIFEST_REL).read_bytes() == prior_manifest_bytes
    assert json.loads((run / om.MANIFEST_REL).read_text())["seats"][0] == prior_normalized_seat
    receipt = json.loads((run / oc.STOP_RECEIPT_REL).read_text())
    assert receipt["workflow"]["instanceId"] == "wf-prior-stop"
    assert receipt["seats"][0]["actualOutcome"] == "resumed"


def test_failed_stop_preserves_active_seat_evidence_when_state_is_unavailable(
    tmp_path, monkeypatch
):
    run, bridge, _home, _launch_path = _managed_run(
        tmp_path, "LEASE-FAILED-STOP-PRESERVE"
    )
    prior_seat = {
        "logicalId": "at-main",
        "canonicalSessionName": "at-main@fixture",
        "expectedAction": "resume-original",
        "actualOutcome": "resumed",
        "session": "present",
        "activity": "working",
        "evidence": "observed",
    }
    prior = om.new_manifest(run, bridge, launch_id="launch-prior-active")
    prior["workflow"]["instanceId"] = "wf-prior-active"
    om.finalize_manifest(prior, status="active", seats=[prior_seat])
    om.write_manifest(run, prior)
    (run / "openrig" / "continuity-state.json").unlink()
    (run / oc.PLAN_REL).unlink(missing_ok=True)

    calls, _ = _fake_run(monkeypatch, rc=2)
    report = oc.run_stop(run)

    assert report["ok"] is False
    assert report["error"]["code"] == "down_failed"
    assert [call[1:2] for call in calls] == [["down"]]
    manifest = json.loads((run / om.MANIFEST_REL).read_text())
    assert manifest["status"] == "failed"
    assert manifest["workflow"]["instanceId"] == "wf-prior-active"
    assert len(manifest["seats"]) == 1
    assert manifest["seats"][0]["logicalId"] == "at-main"
    assert manifest["seats"][0]["actualOutcome"] == "resumed"
    receipt = json.loads((run / oc.STOP_RECEIPT_REL).read_text())
    assert receipt["status"] == "failed"
    assert receipt["workflow"]["instanceId"] == "wf-prior-active"
    assert receipt["seats"][0]["logicalId"] == "at-main"


def test_stop_fails_closed_when_post_stop_observation_is_incomplete(
    tmp_path, monkeypatch
):
    run, _bridge, _home, _launch_path = _managed_run(
        tmp_path, "LEASE-STOP-OBS-INCOMPLETE"
    )
    _fake_run(monkeypatch, rc=0)

    def incomplete(*_args, **_kwargs):
        return {
            "schemaVersion": 1,
            "complete": False,
            "sources": {
                "tmux": {
                    "axis": "tmux",
                    "status": "unavailable",
                    "complete": False,
                    "detail": "injected tmux observation unavailable",
                }
            },
            "residue": [],
            "provenance": "injected incomplete observation",
        }

    monkeypatch.setattr(oc, "_observe_post_stop_residue", incomplete)
    report = oc.run_stop(run)

    assert report["ok"] is False
    assert report["rc"] == 2
    assert report["error"]["code"] == oc.CODE_POST_STOP_OBSERVATION_UNAVAILABLE
    assert "orphans" not in report, "unavailable observation must not report an empty orphan list"
    assert report["postStopObservation"]["complete"] is False
    manifest = json.loads((run / om.MANIFEST_REL).read_text())
    assert manifest["status"] == "failed"
    assert manifest["seats"], "pre-stop seat evidence survives the failed observation"


def test_stop_clean_result_reports_independent_observation_provenance(
    tmp_path, monkeypatch
):
    run, _bridge, _home, _launch_path = _managed_run(
        tmp_path, "LEASE-STOP-OBS-CLEAN"
    )
    _fake_run(monkeypatch, rc=0)
    monkeypatch.setattr(
        oc,
        "_probe_tmux_residue",
        lambda *_args, **_kwargs: {
            "axis": "tmux",
            "status": "observed",
            "complete": True,
            "matchedSessions": [],
            "observedSessions": [],
            "expectedSessions": ["at-main@fixture"],
            "detail": "injected tmux clean observation",
        },
    )
    monkeypatch.setattr(
        oc,
        "_probe_process_home_residue",
        lambda *_args, **_kwargs: {
            "axis": "process-home",
            "status": "observed",
            "complete": True,
            "matches": [],
            "detail": "injected process clean observation",
        },
    )
    monkeypatch.setattr(
        oc,
        "_probe_port_residue",
        lambda *_args, **_kwargs: {
            "axis": "port",
            "status": "observed",
            "complete": True,
            "listening": False,
            "port": 47999,
            "detail": "injected port clean observation",
        },
    )

    report = oc.run_stop(run)

    assert report["ok"] is True, report
    assert report["rc"] == 0
    assert report["orphans"] == []
    observation = report["postStopObservation"]
    assert observation["complete"] is True
    assert set(observation["sources"]) == {"tmux", "process-home", "port"}
    assert observation["sources"]["tmux"]["status"] == "observed"
    assert observation["sources"]["process-home"]["status"] == "observed"
    assert observation["sources"]["port"]["listening"] is False
    assert "independent post-stop observation" in observation["provenance"]


def test_stop_daemon_stop_nonzero_fails_closed_before_post_observation(
    tmp_path, monkeypatch
):
    run, _bridge, _home, _launch_path = _managed_run(
        tmp_path, "LEASE-DAEMON-STOP-FAIL"
    )
    state_path = run / "openrig" / "continuity-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["daemonState"] = "running"
    state["rigState"] = "present"
    state["seats"][0]["session"] = "present"
    state["seats"][0]["activity"] = "working"
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    steps: list[str] = []

    def fake(cmd, _bridge, timeout=120):
        del _bridge, timeout
        if cmd[1:2] == ["down"]:
            steps.append("down")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd[1:3] == ["daemon", "stop"]:
            steps.append("daemon-stop")
            return subprocess.CompletedProcess(cmd, 2, "", "daemon stop refused")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(oc, "_run", fake)
    monkeypatch.setattr(
        oc,
        "_observe_post_stop_residue",
        lambda *_args, **_kwargs: pytest.fail(
            "post-stop observation must not turn a failed daemon-stop into a clean result"
        ),
    )

    report = oc.run_stop(run)

    assert steps == ["down", "daemon-stop"]
    assert report["ok"] is False
    assert report["rc"] == 2
    assert report["error"]["code"] == oc.CODE_DAEMON_STOP_FAILED
    assert "orphans" not in report
    assert report["postStopObservation"]["complete"] is False
    assert [row["step"] for row in report["mutations"]] == ["rig-down", "daemon-stop"]


def test_post_stop_probe_fixture_downgrade_never_applies_to_live(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        oc,
        "_probe_tmux_residue",
        lambda *_args, **_kwargs: {
            "axis": "tmux",
            "status": "unavailable",
            "complete": False,
            "matchedSessions": [],
            "detail": "injected tmux unavailable",
        },
    )
    monkeypatch.setattr(
        oc,
        "_probe_process_home_residue",
        lambda *_args, **_kwargs: {
            "axis": "process-home",
            "status": "observed",
            "complete": True,
            "matches": [],
            "detail": "injected process clean",
        },
    )
    monkeypatch.setattr(
        oc,
        "_probe_port_residue",
        lambda *_args, **_kwargs: {
            "axis": "port",
            "status": "observed",
            "complete": True,
            "listening": False,
            "detail": "injected port clean",
        },
    )
    bridge = {"rigName": "fixture-rig", "_fixture": "declared fixture"}
    state = {"seats": []}

    fixture = oc._observe_post_stop_residue(tmp_path, bridge, state, live=False)
    assert fixture["complete"] is True
    assert fixture["fixtureMode"] is True
    assert fixture["sources"]["tmux"]["status"] == "not-applicable"

    live = oc._observe_post_stop_residue(tmp_path, bridge, state, live=True)
    assert live["complete"] is False
    assert live["fixtureMode"] is False
    assert live["sources"]["tmux"]["status"] == "unavailable"


def test_real_non_fixture_stop_without_daemon_port_fails_closed(tmp_path, monkeypatch):
    """F4: the port-axis fixture downgrade is keyed on declared fixture, not --live."""
    run, _bridge, _home, _launch_path = _managed_run(
        tmp_path, "LEASE-STOP-NO-PORT-NONFIXTURE"
    )
    bridge_path = run / "openrig" / "OPENRIG-BRIDGE.json"
    bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
    bridge.pop("_fixture", None)
    bridge.pop("daemonPort", None)
    bridge_path.write_text(json.dumps(bridge, indent=2) + "\n", encoding="utf-8")

    _fake_run(monkeypatch, rc=0)
    monkeypatch.setattr(
        oc,
        "_probe_tmux_residue",
        lambda *_args, **_kwargs: {
            "axis": "tmux",
            "status": "observed",
            "complete": True,
            "matchedSessions": [],
            "detail": "injected tmux clean observation",
        },
    )
    monkeypatch.setattr(
        oc,
        "_probe_process_home_residue",
        lambda *_args, **_kwargs: {
            "axis": "process-home",
            "status": "observed",
            "complete": True,
            "matches": [],
            "detail": "injected process clean observation",
        },
    )

    # Deliberately no --live: plain stop is the path that used to false-clean.
    report = oc.run_stop(run)

    assert report["ok"] is False
    assert report["rc"] == 2
    assert report["error"]["code"] == oc.CODE_POST_STOP_OBSERVATION_UNAVAILABLE
    port = report["postStopObservation"]["sources"]["port"]
    assert port["status"] == "unavailable"
    assert port["complete"] is False
    assert "real run has no daemonPort" in port["detail"]


def test_fixture_without_daemon_port_remains_not_applicable():
    """The declared-fixture compatibility downgrade remains explicit and complete."""
    result = oc._probe_port_residue({}, declared_fixture=True)
    assert result["status"] == "not-applicable"
    assert result["complete"] is True
    assert result["listening"] is False
