# -*- coding: utf-8 -*-
"""P0 resume recovery lease tests.

A stopped daemon needs a fresh launchId (the old daemon-start verb may be consumed);
a running daemon needs its existing launchId refreshed (the daemon's environment token
must still match). The lease is prepared before any child and closes on failure, while a
successful resume keeps the lease active.
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

SECRET = "resume-lease-secret-token-must-not-leak"
PAST_EXPIRES_AT = "2000-01-01T00:30:00Z"
INVALID_UTF8 = b'\x80\x81{"phase":"active"}\n'
CONSUMED_EVENT = {"verb": "daemon-start", "at": "2026-01-01T00:00:00Z", "pid": 123}
STARTUP_ENTRY_VERBS = [
    "daemon-start",
    "up",
    "restore-apply",
    "workflow-instantiate",
    "workflow-instantiate-lifecycle",
    "workflow-run",
]
CONTINUATION_ENTRY_VERBS = [
    "workflow-route",
    "workflow-resume",
    "workflow-abort",
    "workflow-revision",
    "workflow-project",
]
ENTRY_VERBS = STARTUP_ENTRY_VERBS + CONTINUATION_ENTRY_VERBS


def _state(daemon_state: str, *, instance: str | None = "wf-fixture") -> dict:
    running = daemon_state == "running"
    return {
        "daemonState": daemon_state,
        "rigState": "present" if running else "stopped",
        "workflowInstanceId": instance,
        "seats": [
            prov.seat(
                "at-main",
                token=True,
                session="present" if running else "absent",
                startup="ready" if running else "missing",
            )
        ],
    }


def _after_state(*, actual: str = "resumed", instance: str | None = "wf-fixture") -> dict:
    return {
        "daemonState": "running",
        "rigState": "present",
        "workflowInstanceId": instance,
        "seats": [
            prov.seat(
                "at-main",
                token=True,
                actual=actual,
                session="present",
                startup="ready",
            )
        ],
    }


def _managed_run(
    tmp_path: Path,
    name: str,
    *,
    state: dict,
    after_state: dict | None = None,
    marker_exists: bool = True,
    marker_raw: bytes | None = None,
    marker_overrides: dict | None = None,
    launch_exists: bool = True,
    launch_raw: bytes | None = None,
    launch_overrides: dict | None = None,
    phase: str = "active",
    expires_at: str = PAST_EXPIRES_AT,
):
    run = prov.build_run(tmp_path, name, state=state, after_state=after_state)
    bridge, err = oc.load_bundle(run)
    assert err is None
    home = Path(bridge["openrigHome"])
    entry = home / "entry"
    entry.mkdir(parents=True, exist_ok=True)

    marker_path = entry / "managed-run.json"
    if marker_exists:
        if marker_raw is not None:
            marker_path.write_bytes(marker_raw)
        else:
            marker = {
                "schemaVersion": 1,
                "runId": bridge["runId"],
                "rigName": bridge["rigName"],
            }
            if marker_overrides:
                marker.update(marker_overrides)
            marker_path.write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")

    launch_path = entry / "launch.json"
    if launch_exists:
        if launch_raw is not None:
            launch_path.write_bytes(launch_raw)
        else:
            launch = {
                "schemaVersion": 1,
                "launchId": "launch-original-resume",
                "home": str(home.resolve()),
                "runId": bridge["runId"],
                "rigName": bridge["rigName"],
                "workflowId": bridge["workflowId"],
                "verbs": list(ENTRY_VERBS),
                "consumed": [dict(CONSUMED_EVENT)],
                "phase": phase,
                "dryRun": False,
                "createdAt": "2026-01-01T00:00:00Z",
                "expiresAt": expires_at,
                "token": SECRET,
            }
            if launch_overrides:
                launch.update(launch_overrides)
            launch_path.write_text(json.dumps(launch, indent=2) + "\n", encoding="utf-8")
        launch_path.chmod(0o644)
    return run, bridge, home, launch_path


def _install_fake_run(
    monkeypatch,
    run_dir: Path,
    *,
    daemon_rc: int = 0,
    up_rc: int = 0,
    after_state: dict | None = None,
    up_payload: dict | None = None,
    on_daemon=None,
    on_up=None,
):
    calls: list[dict] = []

    def fake(cmd, bridge, timeout=120):
        call = {
            "cmd": list(cmd),
            "bridge": dict(bridge),
            "env": oc._env(bridge),
        }
        if cmd[1:2] == ["daemon"] and cmd[2:3] == ["start"]:
            call["step"] = "daemon-start"
            calls.append(call)
            if on_daemon is not None:
                on_daemon(call)
            return subprocess.CompletedProcess(
                cmd, daemon_rc, "", "daemon start failed" if daemon_rc else ""
            )
        if cmd[1:2] == ["up"]:
            call["step"] = "up-existing"
            calls.append(call)
            if on_up is not None:
                on_up(call)
            if up_rc:
                return subprocess.CompletedProcess(cmd, up_rc, "", "up failed")
            if after_state is not None:
                (run_dir / "openrig" / "continuity-state.json").write_text(
                    json.dumps(after_state, indent=2) + "\n", encoding="utf-8"
                )
            payload = (
                {"nodes": [{"logicalId": "at-main", "status": "resumed"}]}
                if up_payload is None
                else up_payload
            )
            return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), "")
        call["step"] = "other"
        calls.append(call)
        return subprocess.CompletedProcess(cmd, 0, "{}", "")

    monkeypatch.setattr(oc, "_run", fake)
    return calls


def _time(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def test_resume_verb_classes_stay_in_lockstep_with_managed_start():
    import openrig_run as orr

    assert oc.RESUME_STARTUP_ENTRY_VERBS == orr.STARTUP_ENTRY_VERBS
    assert oc.RESUME_CONTINUATION_ENTRY_VERBS == orr.CONTINUATION_ENTRY_VERBS
    assert oc.RESUME_ENTRY_VERBS == orr.ENTRY_VERBS
    assert set(oc.RESUME_ENTRY_VERBS) - set(oc.RESUME_STARTUP_ENTRY_VERBS) == set(
        oc.RESUME_CONTINUATION_ENTRY_VERBS
    )


def test_prepare_resume_lease_upgrades_legacy_verbs_without_consuming_continuation(
    tmp_path,
):
    run, bridge, _home, launch_path = _managed_run(
        tmp_path,
        "RESUME-CONTINUATION-UPGRADE",
        state=_state("running"),
        launch_overrides={"verbs": list(STARTUP_ENTRY_VERBS)},
    )

    result = oc.prepare_resume_lease(run, bridge, daemon_running=True)

    assert result["status"] == "prepared", result
    record = json.loads(launch_path.read_text(encoding="utf-8"))
    assert record["verbs"] == ENTRY_VERBS
    assert set(record["verbs"]) - set(STARTUP_ENTRY_VERBS) == set(
        CONTINUATION_ENTRY_VERBS
    )
    assert record["consumed"] == [CONSUMED_EVENT]
    assert not set(CONTINUATION_ENTRY_VERBS) & {
        row["verb"] for row in record["consumed"] if isinstance(row, dict)
    }


@pytest.mark.parametrize("phase", ["active", "closed"])
def test_prepare_resume_lease_daemon_running_reuses_same_launch(tmp_path, phase):
    run, bridge, _home, launch_path = _managed_run(
        tmp_path,
        f"RESUME-RUNNING-{phase}",
        state=_state("running"),
        phase=phase,
    )
    before = json.loads(launch_path.read_text(encoding="utf-8"))

    result = oc.prepare_resume_lease(
        run, bridge, daemon_running=True, ttl_seconds=1200
    )

    assert result["status"] == "prepared"
    assert result["launchId"] == before["launchId"]
    assert result["newLaunch"] is False
    record = json.loads(launch_path.read_text(encoding="utf-8"))
    assert record["launchId"] == before["launchId"]
    assert record["phase"] == "active"
    assert record["expiresAt"] == result["leaseExpiresAt"]
    expires = _time(record["expiresAt"])
    now = datetime.now(timezone.utc)
    assert now + timedelta(seconds=1100) < expires <= now + timedelta(seconds=1210)
    lease = record["resumeLease"]
    assert lease["reason"] == "run-resume"
    assert lease["daemonRunning"] is True
    assert lease["reusedLaunchId"] is True
    assert lease["newLaunch"] is False
    assert lease["previousPhase"] == phase
    assert lease["previousExpiresAt"] == PAST_EXPIRES_AT
    assert record["token"] == SECRET
    assert SECRET not in json.dumps(result)
    assert stat.S_IMODE(launch_path.stat().st_mode) == 0o600


def test_prepare_resume_lease_daemon_down_creates_new_launch_even_with_old_record(tmp_path):
    run, bridge, _home, launch_path = _managed_run(
        tmp_path, "RESUME-DOWN-OLD", state=_state("stopped")
    )
    old_id = json.loads(launch_path.read_text(encoding="utf-8"))["launchId"]

    result = oc.prepare_resume_lease(
        run, bridge, daemon_running=False, ttl_seconds=1200
    )

    assert result["status"] == "prepared"
    assert result["newLaunch"] is True
    assert result["launchId"].startswith("launch-")
    assert result["launchId"] != old_id
    assert result["previousLaunchId"] == old_id
    record = json.loads(launch_path.read_text(encoding="utf-8"))
    assert record["launchId"] == result["launchId"]
    assert record["phase"] == "active"
    assert record["createdBy"] == "openrig-run resume"
    assert record["verbs"] == ENTRY_VERBS
    assert record["consumed"] == []
    assert record["home"] == str(Path(bridge["openrigHome"]).resolve())
    assert record["runId"] == bridge["runId"]
    assert "token" not in record
    lease = record["resumeLease"]
    assert lease["reason"] == "run-resume"
    assert lease["previousLaunchId"] == old_id
    assert lease["daemonRunning"] is False
    assert lease["newLaunch"] is True
    assert stat.S_IMODE(launch_path.stat().st_mode) == 0o600
    assert SECRET not in json.dumps(result)


def test_prepare_resume_lease_daemon_down_without_old_launch_creates_new_record(tmp_path):
    run, bridge, _home, launch_path = _managed_run(
        tmp_path, "RESUME-DOWN-NONE", state=_state("stopped"), launch_exists=False
    )
    assert not launch_path.exists()

    result = oc.prepare_resume_lease(run, bridge, daemon_running=False, ttl_seconds=1200)

    assert result["status"] == "prepared"
    assert result["newLaunch"] is True
    assert result["previousLaunchId"] is None
    record = json.loads(launch_path.read_text(encoding="utf-8"))
    assert record["resumeLease"]["previousLaunchId"] is None
    assert record["verbs"] == ENTRY_VERBS
    assert stat.S_IMODE(launch_path.stat().st_mode) == 0o600


@pytest.mark.parametrize("daemon_running", [True, False])
def test_prepare_resume_lease_marker_missing_is_skipped(tmp_path, daemon_running):
    run, bridge, _home, launch_path = _managed_run(
        tmp_path,
        f"RESUME-UNMANAGED-{daemon_running}",
        state=_state("running" if daemon_running else "stopped"),
        marker_exists=False,
        launch_exists=False,
    )

    result = oc.prepare_resume_lease(run, bridge, daemon_running=daemon_running)

    assert result["status"] == "skipped"
    assert result["reason"] == "not a managed run home"
    assert not launch_path.exists()


@pytest.mark.parametrize("daemon_running", [True, False])
def test_prepare_resume_lease_accepts_absent_dry_run(tmp_path, daemon_running):
    run, bridge, _home, launch_path = _managed_run(
        tmp_path,
        f"RESUME-NO-DRYRUN-{daemon_running}",
        state=_state("running" if daemon_running else "stopped"),
    )
    old = json.loads(launch_path.read_text(encoding="utf-8"))
    old.pop("dryRun", None)
    launch_path.write_text(json.dumps(old, indent=2) + "\n", encoding="utf-8")

    result = oc.prepare_resume_lease(run, bridge, daemon_running=daemon_running)

    assert result["status"] == "prepared"
    record = json.loads(launch_path.read_text(encoding="utf-8"))
    assert record["phase"] == "active"


ERROR_CASES = [
    ("marker-invalid-json", {"marker_raw": b"{not-json"}),
    ("marker-invalid-utf8", {"marker_raw": INVALID_UTF8}),
    ("marker-run-mismatch", {"marker_overrides": {"runId": "another-run"}}),
    ("marker-run-missing", {"marker_overrides": {"runId": None}}),
    ("launch-invalid-json", {"launch_raw": b"{not-json"}),
    ("launch-invalid-utf8", {"launch_raw": INVALID_UTF8}),
    ("launch-home-mismatch", {"launch_overrides": {"home": "/tmp/other-home"}}),
    ("launch-home-relative", {"launch_overrides": {"home": "relative/home"}}),
    ("launch-run-mismatch", {"launch_overrides": {"runId": "another-run"}}),
    ("launch-schema-version", {"launch_overrides": {"schemaVersion": 2}}),
    ("launch-schema-bool", {"launch_overrides": {"schemaVersion": True}}),
    ("launch-phase-invalid", {"launch_overrides": {"phase": "expired"}}),
    ("launch-expires-invalid", {"launch_overrides": {"expiresAt": "not-a-time"}}),
    ("launch-verbs-not-list", {"launch_overrides": {"verbs": "daemon-start"}}),
    (
        "launch-verbs-invalid",
        {"launch_overrides": {"verbs": ["daemon-start", "not-a-product-verb"]}},
    ),
    ("launch-consumed-not-list", {"launch_overrides": {"consumed": "daemon-start"}}),
    ("launch-consumed-string", {"launch_overrides": {"consumed": ["daemon-start"]}}),
    (
        "launch-consumed-bad-verb",
        {"launch_overrides": {"consumed": [{"verb": "not-a-product-verb", "at": "2026-01-01T00:00:00Z"}]}},
    ),
    (
        "launch-consumed-no-at",
        {"launch_overrides": {"consumed": [{"verb": "daemon-start"}]}},
    ),
    (
        "launch-consumed-bad-at",
        {"launch_overrides": {"consumed": [{"verb": "daemon-start", "at": "not-a-time"}]}},
    ),
    ("launch-dryrun-true", {"launch_overrides": {"dryRun": True}}),
    ("launch-dryrun-malformed", {"launch_overrides": {"dryRun": 1}}),
    ("launch-dryrun-string-false", {"launch_overrides": {"dryRun": "false"}}),
]


@pytest.mark.parametrize("daemon_state", ["stopped", "running"])
@pytest.mark.parametrize("case_name,kwargs", ERROR_CASES, ids=[row[0] for row in ERROR_CASES])
def test_run_resume_authorization_errors_zero_child(
    tmp_path, monkeypatch, daemon_state, case_name, kwargs
):
    run, _bridge, _home, launch_path = _managed_run(
        tmp_path,
        f"RESUME-ERROR-{daemon_state}-{case_name}",
        state=_state(daemon_state),
        **kwargs,
    )
    launch_before = launch_path.read_bytes() if launch_path.exists() else None
    calls: list[list[str]] = []

    def child_if_called(cmd, _bridge, _timeout=120):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, "{}", "")

    monkeypatch.setattr(oc, "_run", child_if_called)

    report = oc.run_resume(run)

    assert report["ok"] is False
    assert report["rc"] == 2
    assert report["error"]["code"] == "resume_authorization_failed"
    assert report["mutations"] == []
    assert report["resumeAuthorization"]["status"] == "error"
    assert calls == []
    assert launch_path.read_bytes() == launch_before
    assert SECRET not in json.dumps(report)




def test_run_resume_marker_directory_is_structured_error_and_zero_child(
    tmp_path, monkeypatch
):
    run, bridge, home, _launch_path = _managed_run(
        tmp_path, "RESUME-MARKER-DIRECTORY", state=_state("running"), marker_exists=False
    )
    (home / "entry" / "managed-run.json").mkdir()

    direct = oc.prepare_resume_lease(run, bridge, daemon_running=True)
    assert direct["status"] == "error"
    assert direct["code"] == "managed_marker_invalid"

    calls: list[list[str]] = []

    def child_if_called(cmd, _bridge, _timeout=120):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, "{}", "")

    monkeypatch.setattr(oc, "_run", child_if_called)
    report = oc.run_resume(run)

    assert report["error"]["code"] == "resume_authorization_failed"
    assert report["resumeAuthorization"]["code"] == "managed_marker_invalid"
    assert calls == []
    assert report["mutations"] == []


@pytest.mark.parametrize("phase", ["active", "closed"])
def test_run_resume_daemon_running_reuses_lease_and_up_gets_token(
    tmp_path, monkeypatch, phase
):
    run, bridge, _home, launch_path = _managed_run(
        tmp_path,
        f"RESUME-RUNNING-INTEGRATION-{phase}",
        state=_state("running"),
        after_state=_after_state(),
        phase=phase,
    )
    old_id = json.loads(launch_path.read_text(encoding="utf-8"))["launchId"]
    calls = _install_fake_run(
        monkeypatch, run, after_state=_after_state()
    )

    report = oc.run_resume(run)

    assert report["ok"] is True, report
    assert report["rc"] == 0
    assert [call["step"] for call in calls] == ["up-existing"]
    up = calls[0]
    assert "--existing" in up["cmd"]
    assert up["env"]["OPENRIG_ENTRY_LAUNCH_ID"] == old_id
    assert up["env"]["OPENRIG_ENTRY_RUN_ID"] == bridge["runId"]
    assert "_entryLaunchId" in up["bridge"]
    auth = report["resumeAuthorization"]
    assert auth["status"] == "prepared"
    assert auth["launchId"] == "<redacted>"
    assert auth["newLaunch"] is False
    assert "leaseClosed" not in auth, "successful resume keeps the active lease"
    record = json.loads(launch_path.read_text(encoding="utf-8"))
    assert record["launchId"] == old_id
    assert record["phase"] == "active"
    assert SECRET not in json.dumps(report)
    assert SECRET not in (run / oc.PLAN_REL).read_text(encoding="utf-8")
    manifest_text = (
        run / "reports" / "evidence" / "manifest" / "run-manifest.json"
    ).read_text(encoding="utf-8")
    receipt_text = (run / "reports" / "evidence" / "resume-receipt.json").read_text(
        encoding="utf-8"
    )
    assert SECRET not in manifest_text
    assert SECRET not in receipt_text
    manifest = json.loads(manifest_text)
    assert manifest["status"] == "active"
    assert manifest["seats"]
    assert {Path(out["path"]).name for out in manifest["outputs"]} == {
        "continuity-plan.json",
        "resume-receipt.json",
    }


def test_run_resume_daemon_down_creates_launch_before_daemon_start_and_injects_token(
    tmp_path, monkeypatch
):
    run, bridge, _home, launch_path = _managed_run(
        tmp_path,
        "RESUME-DOWN-INTEGRATION",
        state=_state("stopped"),
        after_state=_after_state(),
    )
    old_id = json.loads(launch_path.read_text(encoding="utf-8"))["launchId"]
    seen: dict = {}

    def on_daemon(call):
        record = json.loads(launch_path.read_text(encoding="utf-8"))
        seen["recordAtDaemonStart"] = record
        seen["daemonEnv"] = call["env"]

    calls = _install_fake_run(
        monkeypatch,
        run,
        after_state=_after_state(),
        on_daemon=on_daemon,
    )

    report = oc.run_resume(run)

    assert report["ok"] is True, report
    assert [call["step"] for call in calls] == ["daemon-start", "up-existing"]
    record_at_start = seen["recordAtDaemonStart"]
    new_id = record_at_start["launchId"]
    assert new_id != old_id
    assert new_id.startswith("launch-")
    assert record_at_start["phase"] == "active"
    assert record_at_start["consumed"] == []
    assert record_at_start["verbs"] == ENTRY_VERBS
    assert seen["daemonEnv"]["OPENRIG_ENTRY_LAUNCH_ID"] == new_id
    assert seen["daemonEnv"]["OPENRIG_ENTRY_RUN_ID"] == bridge["runId"]
    up = calls[1]
    assert up["env"]["OPENRIG_ENTRY_LAUNCH_ID"] == new_id
    assert up["env"]["OPENRIG_ENTRY_RUN_ID"] == bridge["runId"]
    assert report["resumeAuthorization"]["newLaunch"] is True
    assert report["resumeAuthorization"]["previousLaunchId"] == "<redacted>"
    final = json.loads(launch_path.read_text(encoding="utf-8"))
    assert final["launchId"] == new_id
    assert final["phase"] == "active"
    assert final["resumeLease"]["previousLaunchId"] == old_id
    assert "leaseClosed" not in report["resumeAuthorization"]
    assert SECRET not in json.dumps(report)
    assert SECRET not in (run / oc.PLAN_REL).read_text(encoding="utf-8")


def test_run_resume_live_daemon_down_uses_manifest_evidence_and_reaches_daemon_start(
    tmp_path, monkeypatch
):
    """Fixture-free daemon-down recovery: no continuity-state.json, real live branch."""
    run = prov.build_run(
        tmp_path,
        "RESUME-LIVE-DOWN-MANIFEST",
        state=_state("stopped"),
    )
    bridge, err = oc.load_bundle(run)
    assert err is None
    fixture_state = json.loads(
        (run / "openrig" / "continuity-state.json").read_text(encoding="utf-8")
    )
    manifest = om.new_manifest(run, bridge, launch_id="launch-before-daemon-down")
    manifest["workflow"]["instanceId"] = "wf-live-down"
    om.finalize_manifest(
        manifest,
        status="active",
        seats=[fixture_state["seats"][0]],
    )
    om.write_manifest(run, manifest)
    (run / "openrig" / "continuity-state.json").unlink()
    assert not (run / "openrig" / "continuity-state.json").exists()

    calls: list[dict] = []
    ps_calls = 0

    def fake_run(cmd, exec_bridge, timeout=120):
        nonlocal ps_calls
        del exec_bridge, timeout
        calls.append({"cmd": list(cmd), "env": oc._env(oc._capture_bridge(
            bridge,
            "fake-bridge",
            persist=False,
        ))})
        if cmd[1:2] == ["ps"]:
            ps_calls += 1
            if ps_calls == 1:
                return subprocess.CompletedProcess(
                    cmd, 1, "", "Error: Daemon not running.\n"
                )
            return subprocess.CompletedProcess(
                cmd,
                0,
                json.dumps(
                    [
                        {
                            "logicalId": "at-main",
                            "canonicalSessionName": "at-main@fixture",
                            "runtime": "dsh",
                            "startupStatus": "ready",
                            "sessionStatus": "running",
                            "agentActivity": {"state": "running"},
                            "resumeTokenPresent": True,
                        }
                    ]
                ),
                "",
            )
        if cmd[1:3] == ["daemon", "start"]:
            return subprocess.CompletedProcess(cmd, 0, '{"ok":true}', "")
        if cmd[1:2] == ["up"]:
            return subprocess.CompletedProcess(
                cmd,
                0,
                json.dumps({"nodes": [{"logicalId": "at-main", "status": "resumed"}]}),
                "",
            )
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(oc, "_run", fake_run)

    report = oc.run_resume(run, live=True)

    assert report["ok"] is True, report
    assert [row["step"] for row in report["mutations"]] == [
        "daemon-start",
        "up-existing",
    ], "the live-down path must reach daemon-start rather than return early"
    assert ps_calls == 2, "one failed pre-resume ps and one post-up ps"
    plan = report["continuity"]
    assert plan["stateSource"].startswith("daemon-down-ps+managed-manifest")
    assert plan["stateBefore"]["daemonState"] == "stopped"
    assert plan["seats"][0]["observationStale"] is True
    assert plan["seats"][0]["actualOutcome"] == "resumed"
    assert report["workflowInstanceProvenance"] == "managed-manifest"
    assert report["attachedWorkflowInstance"] == "wf-live-down"
    written = json.loads(
        (run / "reports" / "evidence" / "manifest" / "run-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert written["status"] == "active"
    assert written["revision"] == 2
    assert written["seats"][0]["actualOutcome"] == "resumed"


def test_run_resume_daemon_down_without_old_launch_succeeds(tmp_path, monkeypatch):
    run, _bridge, _home, launch_path = _managed_run(
        tmp_path,
        "RESUME-DOWN-NO-OLD-INTEGRATION",
        state=_state("stopped"),
        after_state=_after_state(),
        launch_exists=False,
    )
    seen: dict = {}

    def on_daemon(call):
        seen["record"] = json.loads(launch_path.read_text(encoding="utf-8"))
        seen["env"] = call["env"]

    _install_fake_run(
        monkeypatch, run, after_state=_after_state(), on_daemon=on_daemon
    )

    report = oc.run_resume(run)

    assert report["ok"] is True, report
    assert report["resumeAuthorization"]["newLaunch"] is True
    assert report["resumeAuthorization"]["previousLaunchId"] is None
    assert seen["record"]["resumeLease"]["previousLaunchId"] is None
    assert seen["env"]["OPENRIG_ENTRY_LAUNCH_ID"] == seen["record"]["launchId"]
    assert json.loads(launch_path.read_text(encoding="utf-8"))["phase"] == "active"


def test_run_resume_marker_missing_skips_lease_and_keeps_fixture_flow(
    tmp_path, monkeypatch
):
    run, _bridge, _home, launch_path = _managed_run(
        tmp_path,
        "RESUME-SKIPPED",
        state=_state("stopped"),
        after_state=_after_state(),
        marker_exists=False,
        launch_exists=False,
    )
    monkeypatch.delenv("OPENRIG_ENTRY_LAUNCH_ID", raising=False)
    monkeypatch.delenv("OPENRIG_ENTRY_RUN_ID", raising=False)
    calls = _install_fake_run(monkeypatch, run, after_state=_after_state())

    report = oc.run_resume(run)

    assert report["ok"] is True, report
    assert report["resumeAuthorization"]["status"] == "skipped"
    assert [call["step"] for call in calls] == ["daemon-start", "up-existing"]
    assert "_entryLaunchId" not in calls[0]["bridge"]
    assert "OPENRIG_ENTRY_LAUNCH_ID" not in calls[0]["env"]
    assert not launch_path.exists()


def test_run_resume_dry_run_writes_no_lease_and_calls_no_child(tmp_path, monkeypatch):
    run, _bridge, _home, launch_path = _managed_run(
        tmp_path, "RESUME-DRY-RUN", state=_state("running")
    )
    before = launch_path.read_bytes()

    def forbidden(*_args, **_kwargs):
        pytest.fail("dry-run resume must not prepare a lease or invoke a child")

    monkeypatch.setattr(oc, "prepare_resume_lease", forbidden)
    monkeypatch.setattr(oc, "_run", forbidden)

    report = oc.run_resume(run, dry_run=True)

    assert report["ok"] is True
    assert report["rc"] == 0
    assert report["dryRun"] is True
    assert report["mutations"] == []
    assert report["resumeAuthorization"]["status"] == "dry-run"
    assert launch_path.read_bytes() == before


def test_run_resume_daemon_start_failure_closes_lease(tmp_path, monkeypatch):
    run, _bridge, _home, launch_path = _managed_run(
        tmp_path, "RESUME-DAEMON-FAIL", state=_state("stopped")
    )
    calls = _install_fake_run(monkeypatch, run, daemon_rc=2)

    report = oc.run_resume(run)

    assert report["ok"] is False
    assert report["rc"] == 2
    assert report["error"]["code"] == "daemon_start_failed"
    assert [call["step"] for call in calls] == ["daemon-start"]
    auth = report["resumeAuthorization"]
    assert auth["status"] == "prepared"
    assert auth["leaseClosed"]["status"] == "closed"
    assert auth["launchId"] == "<redacted>"
    record = json.loads(launch_path.read_text(encoding="utf-8"))
    assert record["phase"] == "closed"
    assert record["closedReason"]


def test_run_resume_up_failure_closes_lease(tmp_path, monkeypatch):
    run, _bridge, _home, launch_path = _managed_run(
        tmp_path, "RESUME-UP-FAIL", state=_state("running")
    )
    old_id = json.loads(launch_path.read_text(encoding="utf-8"))["launchId"]
    calls = _install_fake_run(monkeypatch, run, up_rc=2)

    report = oc.run_resume(run)

    assert report["ok"] is False
    assert report["rc"] == 2
    assert report["error"]["code"] == "up_failed"
    assert [call["step"] for call in calls] == ["up-existing"]
    auth = report["resumeAuthorization"]
    assert auth["status"] == "prepared"
    assert auth["leaseClosed"]["status"] == "closed"
    record = json.loads(launch_path.read_text(encoding="utf-8"))
    assert record["launchId"] == old_id
    assert record["phase"] == "closed"


def test_run_resume_post_up_no_state_closes_lease(tmp_path, monkeypatch):
    run, _bridge, _home, launch_path = _managed_run(
        tmp_path, "RESUME-POST-UP-NO-STATE", state=_state("running")
    )

    def delete_state_after_up(_call):
        (run / "openrig" / "continuity-state.json").unlink()

    _install_fake_run(monkeypatch, run, on_up=delete_state_after_up)

    report = oc.run_resume(run)

    assert report["ok"] is False
    assert report["rc"] == 2
    assert report["error"]["code"] == oc.CODE_NO_STATE
    auth = report["resumeAuthorization"]
    assert auth["status"] == "prepared"
    assert auth["leaseClosed"]["status"] == "closed"
    assert json.loads(launch_path.read_text(encoding="utf-8"))["phase"] == "closed"


def test_run_resume_daemon_down_up_failure_closes_new_lease(tmp_path, monkeypatch):
    run, _bridge, _home, launch_path = _managed_run(
        tmp_path, "RESUME-DOWN-UP-FAIL", state=_state("stopped")
    )
    old_id = json.loads(launch_path.read_text(encoding="utf-8"))["launchId"]
    calls = _install_fake_run(monkeypatch, run, up_rc=2)

    report = oc.run_resume(run)

    assert report["ok"] is False
    assert report["rc"] == 2
    assert report["error"]["code"] == "up_failed"
    assert [call["step"] for call in calls] == ["daemon-start", "up-existing"]
    auth = report["resumeAuthorization"]
    assert auth["newLaunch"] is True
    assert auth["previousLaunchId"] == "<redacted>"
    assert auth["leaseClosed"]["status"] == "closed"
    record = json.loads(launch_path.read_text(encoding="utf-8"))
    assert record["phase"] == "closed"


def test_run_resume_post_up_mismatch_closes_lease(tmp_path, monkeypatch):
    run, _bridge, _home, launch_path = _managed_run(
        tmp_path, "RESUME-MISMATCH", state=_state("running")
    )
    _install_fake_run(
        monkeypatch,
        run,
        after_state=_after_state(actual="fresh-primed"),
        up_payload={},
    )

    report = oc.run_resume(run)

    assert report["ok"] is False
    assert report["rc"] == 2
    assert report["error"]["code"] == "continuity_mismatch"
    auth = report["resumeAuthorization"]
    assert auth["status"] == "prepared"
    assert auth["leaseClosed"]["status"] == "closed"
    assert json.loads(launch_path.read_text(encoding="utf-8"))["phase"] == "closed"


def test_run_resume_no_instance_closes_lease(tmp_path, monkeypatch):
    run, _bridge, _home, launch_path = _managed_run(
        tmp_path,
        "RESUME-NO-INSTANCE",
        state=_state("running", instance=None),
        after_state=_after_state(instance=None),
    )
    _install_fake_run(
        monkeypatch, run, after_state=_after_state(instance=None)
    )

    report = oc.run_resume(run)

    assert report["ok"] is False
    assert report["rc"] == 2
    assert report["error"]["code"] == "workflow_instance_conflict"
    auth = report["resumeAuthorization"]
    assert auth["leaseClosed"]["status"] == "closed"
    assert json.loads(launch_path.read_text(encoding="utf-8"))["phase"] == "closed"


def test_close_resume_lease_does_not_overwrite_new_launch(tmp_path):
    run, bridge, _home, launch_path = _managed_run(
        tmp_path, "RESUME-CLOSE-NEW", state=_state("running")
    )
    lease = oc.prepare_resume_lease(run, bridge, daemon_running=True)
    assert lease["status"] == "prepared"

    new_record = {
        "schemaVersion": 1,
        "launchId": "launch-newer-than-lease",
        "phase": "starting",
        "home": str(Path(bridge["openrigHome"]).resolve()),
        "runId": bridge["runId"],
    }
    launch_path.write_text(json.dumps(new_record, indent=2) + "\n", encoding="utf-8")
    before = launch_path.read_bytes()

    result = oc.close_resume_lease(run, bridge, lease, reason="up rc=0")

    assert result["status"] == "skipped"
    assert launch_path.read_bytes() == before
    assert json.loads(launch_path.read_text(encoding="utf-8"))["launchId"] == new_record["launchId"]


def test_close_resume_lease_invalid_utf8_returns_structured_error(tmp_path):
    run, bridge, _home, launch_path = _managed_run(
        tmp_path, "RESUME-CLOSE-UTF8", state=_state("running")
    )
    lease = oc.prepare_resume_lease(run, bridge, daemon_running=True)
    launch_path.write_bytes(INVALID_UTF8)

    result = oc.close_resume_lease(run, bridge, lease, reason="up rc=0")

    assert result["status"] == "error"
    assert result["code"] == "launch_record_invalid"
    assert result["message"]
    assert launch_path.read_bytes() == INVALID_UTF8


def test_close_resume_lease_marker_directory_returns_structured_error(tmp_path):
    run, bridge, home, launch_path = _managed_run(
        tmp_path, "RESUME-CLOSE-MARKER-DIR", state=_state("running")
    )
    lease = oc.prepare_resume_lease(run, bridge, daemon_running=True)
    marker_path = home / "entry" / "managed-run.json"
    marker_path.unlink()
    marker_path.mkdir()
    before = launch_path.read_bytes()

    result = oc.close_resume_lease(run, bridge, lease, reason="up rc=0")

    assert result["status"] == "error"
    assert result["code"] == "managed_marker_invalid"
    assert launch_path.read_bytes() == before


def test_close_resume_lease_write_failure_returns_structured_error(
    tmp_path, monkeypatch
):
    run, bridge, _home, launch_path = _managed_run(
        tmp_path, "RESUME-CLOSE-WRITE-FAIL", state=_state("running")
    )
    lease = oc.prepare_resume_lease(run, bridge, daemon_running=True)
    assert lease["status"] == "prepared"
    before = launch_path.read_bytes()

    def fail_write(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(oc, "_atomic_write_json_private", fail_write)

    result = oc.close_resume_lease(run, bridge, lease, reason="up rc=0")

    assert result["status"] == "error"
    assert result["code"] == "launch_record_write_failed"
    assert result["message"]
    assert launch_path.read_bytes() == before


def test_env_injects_entry_launch_and_run_without_disabling_guard(tmp_path, monkeypatch):
    bridge = {
        "openrigHome": str(tmp_path / "home"),
        "daemonPort": 47998,
        "runId": "run-env-test",
        "_entryLaunchId": "launch-env-test",
    }
    monkeypatch.delenv("OPENRIG_ALLOW_DIRECT", raising=False)
    monkeypatch.delenv("OPENRIG_ENTRY_GUARD", raising=False)

    env = oc._env(bridge)

    assert env["OPENRIG_HOME"] == bridge["openrigHome"]
    assert env["OPENRIG_PORT"] == "47998"
    assert env["OPENRIG_ENTRY_LAUNCH_ID"] == "launch-env-test"
    assert env["OPENRIG_ENTRY_RUN_ID"] == "run-env-test"
    assert "OPENRIG_ALLOW_DIRECT" not in env
    assert "OPENRIG_ENTRY_GUARD" not in env


def test_redact_known_secrets_replaces_bridge_lease_and_explicit_values():
    bridge = {"_entryLaunchId": "launch-bridge-token"}
    text = (
        "bridge=launch-bridge-token lease=launch-lease-token "
        "explicit=explicit-secret-token"
    )

    redacted = oc._redact_known_secrets(
        text, bridge, "launch-lease-token", "explicit-secret-token"
    )

    assert "launch-bridge-token" not in redacted
    assert "launch-lease-token" not in redacted
    assert "explicit-secret-token" not in redacted
    assert redacted.count("<redacted>") == 3


def test_resume_daemon_start_failure_redacts_output_secrets(tmp_path, monkeypatch):
    run, _bridge, _home, launch_path = _managed_run(
        tmp_path, "RESUME-REDACT-DAEMON", state=_state("stopped")
    )
    raw: dict[str, str] = {}
    observed_launch_ids: list[str] = []

    def fake_daemon_start(cmd, bridge, timeout=120):
        del timeout
        assert cmd[1:2] == ["daemon"]
        launch_id = bridge["_entryLaunchId"]
        observed_launch_ids.append(launch_id)
        raw["stdout"] = f"daemon stdout launch={launch_id} token={SECRET}\n"
        raw["stderr"] = f"daemon stderr launch={launch_id} token={SECRET}\n"
        return subprocess.CompletedProcess(cmd, 2, raw["stdout"], raw["stderr"])

    monkeypatch.setattr(oc, "_run", fake_daemon_start)

    report = oc.run_resume(run)

    assert report["ok"] is False
    assert report["error"]["code"] == "daemon_start_failed"
    launch_id = observed_launch_ids[0]
    assert report["resumeAuthorization"]["launchId"] == "<redacted>"
    detail = report["error"]["message"]
    assert "<redacted>" in detail
    assert launch_id not in detail
    assert SECRET not in detail
    assert SECRET not in json.dumps(report)


def test_resume_up_failure_redacts_detail_and_tails_but_hashes_raw_output(
    tmp_path, monkeypatch
):
    run, _bridge, _home, launch_path = _managed_run(
        tmp_path, "RESUME-REDACT-UP", state=_state("running")
    )
    raw: dict[str, str] = {}
    observed_launch_ids: list[str] = []

    def fake_up(cmd, bridge, timeout=120):
        del timeout
        assert cmd[1:2] == ["up"]
        launch_id = bridge["_entryLaunchId"]
        observed_launch_ids.append(launch_id)
        raw["stdout"] = f"up stdout launch={launch_id} token={SECRET} restored\n"
        raw["stderr"] = f"up stderr launch={launch_id} token={SECRET} failed\n"
        return subprocess.CompletedProcess(cmd, 2, raw["stdout"], raw["stderr"])

    monkeypatch.setattr(oc, "_run", fake_up)

    report = oc.run_resume(run)

    assert report["ok"] is False
    assert report["error"]["code"] == "up_failed"
    launch_id = observed_launch_ids[0]
    assert report["resumeAuthorization"]["launchId"] == "<redacted>"
    detail = report["error"]["message"]
    mutation = report["mutations"][-1]
    assert mutation["step"] == "up-existing"
    assert mutation["stdoutBytes"] == len(raw["stdout"])
    assert mutation["stderrBytes"] == len(raw["stderr"])
    assert mutation["stdoutSha256"] == hashlib.sha256(raw["stdout"].encode()).hexdigest()
    assert mutation["stderrSha256"] == hashlib.sha256(raw["stderr"].encode()).hexdigest()
    for text in (detail, mutation["stdoutTail"], mutation["stderrTail"]):
        assert "<redacted>" in text
        assert launch_id not in text
        assert SECRET not in text
    assert SECRET not in json.dumps(report)


def test_resume_success_tails_are_redacted_without_changing_raw_hashes(
    tmp_path, monkeypatch
):
    run, _bridge, _home, _launch_path = _managed_run(
        tmp_path,
        "RESUME-REDACT-SUCCESS",
        state=_state("running"),
        after_state=_after_state(),
    )
    raw: dict[str, str] = {}
    observed_launch_ids: list[str] = []

    def fake_up(cmd, bridge, timeout=120):
        del timeout
        assert cmd[1:2] == ["up"]
        launch_id = bridge["_entryLaunchId"]
        observed_launch_ids.append(launch_id)
        payload = {
            "nodes": [{"logicalId": "at-main", "status": "resumed"}],
            "debug": f"launch={launch_id} token={SECRET}",
        }
        raw["stdout"] = json.dumps(payload) + "\n"
        raw["stderr"] = f"up note launch={launch_id} token={SECRET}\n"
        (run / "openrig" / "continuity-state.json").write_text(
            json.dumps(_after_state(), indent=2) + "\n", encoding="utf-8"
        )
        return subprocess.CompletedProcess(cmd, 0, raw["stdout"], raw["stderr"])

    monkeypatch.setattr(oc, "_run", fake_up)

    report = oc.run_resume(run)

    assert report["ok"] is True, report
    launch_id = observed_launch_ids[0]
    assert report["resumeAuthorization"]["launchId"] == "<redacted>"
    mutation = report["mutations"][-1]
    assert mutation["stdoutSha256"] == hashlib.sha256(raw["stdout"].encode()).hexdigest()
    assert mutation["stderrSha256"] == hashlib.sha256(raw["stderr"].encode()).hexdigest()
    for text in (mutation["stdoutTail"], mutation["stderrTail"]):
        assert "<redacted>" in text
        assert launch_id not in text
        assert SECRET not in text
    assert SECRET not in json.dumps(report)


def test_redact_report_value_recurses_without_changing_non_string_evidence():
    payload = {
        SECRET: "key-is-not-a-value",
        "message": f"token={SECRET}",
        "argv": ["rig", SECRET],
        "nested": {"reason": f"bad {SECRET}"},
        "tuple": ("ok", SECRET),
        "count": 7,
        "none": None,
    }

    redacted = oc._redact_report_value(payload, SECRET)

    assert SECRET in redacted, "dict keys must not be rewritten"
    assert redacted["message"] == "token=<redacted>"
    assert redacted["argv"] == ["rig", "<redacted>"]
    assert redacted["nested"]["reason"] == "bad <redacted>"
    assert redacted["tuple"] == ("ok", "<redacted>")
    assert redacted["count"] == 7
    assert redacted["none"] is None


def test_resume_authorization_message_redacts_record_runid_token(tmp_path):
    run, _bridge, _home, _launch_path = _managed_run(
        tmp_path,
        "RESUME-AUTH-REDACT",
        state=_state("running"),
        launch_overrides={"runId": SECRET, "token": SECRET},
    )

    report = oc.run_resume(run)

    assert report["ok"] is False
    assert report["error"]["code"] == "resume_authorization_failed"
    assert report["mutations"] == []
    assert "<redacted>" in report["error"]["message"]
    auth = report["resumeAuthorization"]
    assert auth["status"] == "error"
    assert "<redacted>" in auth["message"]
    assert SECRET not in auth["message"]
    assert SECRET not in json.dumps(report)


def test_resume_mutation_argv_and_plan_are_redacted(tmp_path, monkeypatch):
    run, _bridge, _home, _launch_path = _managed_run(
        tmp_path,
        "RESUME-ARGV-REDACT",
        state=_state("running"),
    )
    bridge_path = run / "openrig" / "OPENRIG-BRIDGE.json"
    bridge_payload = json.loads(bridge_path.read_text(encoding="utf-8"))
    bridge_payload["rigName"] = f"rig-{SECRET}"
    bridge_path.write_text(json.dumps(bridge_payload, indent=2) + "\n", encoding="utf-8")

    def fake_up(cmd, _bridge, timeout=120):
        del timeout
        assert cmd[1:2] == ["up"]
        return subprocess.CompletedProcess(cmd, 2, "", "up failed\n")

    monkeypatch.setattr(oc, "_run", fake_up)

    report = oc.run_resume(run)

    assert report["error"]["code"] == "up_failed"
    argv = report["mutations"][-1]["argv"]
    assert any("<redacted>" in part for part in argv)
    assert all(SECRET not in part for part in argv)
    assert report["continuity"]["rigName"] == "rig-<redacted>"
    assert SECRET not in json.dumps(report)
    assert SECRET not in (run / oc.PLAN_REL).read_text(encoding="utf-8")
