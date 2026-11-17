# -*- coding: utf-8 -*-
"""S8 Wave A · N-WRP-02 — `openrig_run.py` provenance / B4 / B5 / rollback tests.

Every fixture is built inside pytest `tmp_path`; nothing is written to
`tests/fixtures/**` (frozen S7 bytes) and no real `rig`, daemon, or seat is invoked.
The fake `rig` follows the S7 convention: an unorchestrated call is rc 2, never a
silent success.

Coverage:
  - entry records written BEFORE any rig subprocess; six single-use startup verbs plus
    the repeatable managed workflow-continuation verbs; TTL; runId/home
  - OPENRIG_PORT / OPENRIG_ENTRY_LAUNCH_ID / OPENRIG_ENTRY_RUN_ID on every child
  - B4 (--root-objective / --created-by) and B5 (--cwd/--yes; no implicit --non-interruptive)
  - failure closes the launch, writes partial evidence, auto-stops an unregistered
    daemon, and never deletes OPENRIG_HOME or the DB
  - `--rollback manual` keeps the print-only behaviour
"""
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import openrig_run as orr  # noqa: E402

# S10 r3 S1-2 — writer lockstep with packages/daemon/src/entry-guard.ts.
STARTUP_ENTRY_VERBS = {
    "daemon-start",
    "up",
    "restore-apply",
    "workflow-instantiate",
    "workflow-instantiate-lifecycle",
    "workflow-run",
}
CONTINUATION_ENTRY_VERBS = {
    "workflow-route",
    "workflow-resume",
    "workflow-abort",
    "workflow-revision",
    "workflow-project",
}
ENTRY_VERBS = STARTUP_ENTRY_VERBS | CONTINUATION_ENTRY_VERBS

FAKE_RIG = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path

log = os.environ.get("FAKE_RIG_LOG")
selected = {
    k: os.environ.get(k)
    for k in (
        "OPENRIG_HOME",
        "OPENRIG_PORT",
        "OPENRIG_ENTRY_LAUNCH_ID",
        "OPENRIG_ENTRY_RUN_ID",
    )
}
if log:
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"argv": sys.argv[1:], "env": selected}) + "\n")

args = sys.argv[1:]
fail_step = os.environ.get("FAKE_RIG_FAIL_STEP", "")
mode = os.environ.get("FAKE_RIG_MODE", "ready")


def fail(step):
    if fail_step == step:
        print("orchestrated failure at " + step, file=sys.stderr)
        sys.exit(1)


if args[:2] == ["daemon", "start"]:
    fail("daemon-start")
    print(json.dumps({"ok": True, "pid": 111}))
    sys.exit(0)

if args[:2] == ["daemon", "stop"]:
    fail("daemon-stop")
    print(json.dumps({"ok": True}))
    sys.exit(0)

if args[:1] == ["up"]:
    fail("up")
    print(json.dumps({"ok": True}))
    sys.exit(0)

if args[:2] == ["workflow", "validate"]:
    fail("workflow-validate")
    print(json.dumps({"ok": True}))
    sys.exit(0)

if args[:2] == ["workflow", "instantiate"]:
    fail("workflow-instantiate")
    print(json.dumps({"ok": True}))
    sys.exit(0)

if args[:1] == ["ps"]:
    targets = json.loads(os.environ.get("FAKE_RIG_SEATS", "[]"))
    status = "ready" if mode == "ready" else "starting"
    rows = [
        {"canonicalSessionName": t, "startupStatus": status, "sessionStatus": "running"}
        for t in targets
    ]
    if mode == "incomplete":
        rows = rows[:-1]
    print(json.dumps(rows))
    sys.exit(0)

print("unexpected fake rig call: " + " ".join(args), file=sys.stderr)
sys.exit(2)
'''

FAKE_DOCTOR_OK = '''#!/usr/bin/env python3
import sys
print("PASS bridge fake=ok")
sys.exit(0)
'''


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_run(tmp_path: Path) -> Path:
    run = tmp_path / "runs" / "t-run"
    openrig = run / "openrig"
    (openrig / "tools").mkdir(parents=True)
    (openrig / "rig.yaml").write_text("rig: t\n", encoding="utf-8")
    (openrig / "workflow.yaml").write_text("workflow: t\n", encoding="utf-8")
    seats = {"main": "main@t", "tdo": "tdo@t"}
    home = tmp_path / "home"
    home.mkdir()
    # A sentinel the rollback must never delete.
    (home / "daemon.sqlite").write_text("db\n", encoding="utf-8")
    rig = tmp_path / "fake-rig"
    rig.write_text(FAKE_RIG, encoding="utf-8")
    rig.chmod(0o755)
    bridge = {
        "schemaVersion": 2,
        "runId": "t-run",
        "rigName": "t-rig",
        "workflowId": "t-workflow",
        "rigSpec": "rig.yaml",
        "workflowSpec": "workflow.yaml",
        "openrigCli": str(rig),
        "openrigHome": str(home),
        "projectRoot": str(tmp_path / "project-root"),
        "daemonPort": 12399,
        "seatMap": seats,
    }
    (openrig / "OPENRIG-BRIDGE.json").write_text(json.dumps(bridge), encoding="utf-8")
    files = {}
    for rel in ("rig.yaml", "workflow.yaml"):
        path = openrig / rel
        files[rel] = {"bytes": len(path.read_bytes()), "sha256": _sha(path)}
    (openrig / "render-manifest.json").write_text(
        json.dumps({"schemaVersion": 1, "runId": "t-run", "files": files}), encoding="utf-8"
    )
    (openrig / "tools" / "openrig_bridge.py").write_text(FAKE_DOCTOR_OK, encoding="utf-8")
    return run


def _env(monkeypatch, tmp_path, **kw):
    log = tmp_path / "fake-rig.log"
    values = {
        "FAKE_RIG_LOG": str(log),
        "FAKE_RIG_MODE": "ready",
        "FAKE_RIG_SEATS": json.dumps(["main@t", "tdo@t"]),
        "FAKE_RIG_FAIL_STEP": "",
    }
    values.update(kw)
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return log


def _calls(log: Path) -> list[dict]:
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line]


def _launch(home: Path) -> dict:
    return json.loads((home / "entry" / "launch.json").read_text(encoding="utf-8"))


def test_dry_run_writes_records_with_startup_and_continuation_verbs(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    log = _env(monkeypatch, tmp_path)
    report = orr.run_start(run, dry_run=True)
    assert report["dryRun"] is True
    home = tmp_path / "home"
    marker = json.loads((home / "entry" / "managed-run.json").read_text(encoding="utf-8"))
    launch = _launch(home)
    assert marker["runId"] == "t-run" and marker["entryCommand"] == "openrig-run start"
    assert launch["schemaVersion"] == 1
    assert launch["launchId"].startswith("launch-")
    assert launch["runId"] == "t-run"
    assert Path(launch["home"]).resolve() == home.resolve()
    assert set(orr.STARTUP_ENTRY_VERBS) == STARTUP_ENTRY_VERBS
    assert set(orr.CONTINUATION_ENTRY_VERBS) == CONTINUATION_ENTRY_VERBS
    assert set(orr.ENTRY_VERBS) == ENTRY_VERBS
    assert set(launch["verbs"]) == ENTRY_VERBS
    assert set(launch["verbs"]) >= CONTINUATION_ENTRY_VERBS
    assert launch["consumed"] == []
    created = datetime.strptime(launch["createdAt"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    expires = datetime.strptime(launch["expiresAt"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    ttl_minutes = (expires - created).total_seconds() / 60
    assert 29 <= ttl_minutes <= 31
    assert log.exists() is False, "dry-run must not invoke the rig CLI"


def test_env_carries_port_launch_and_run(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    log = _env(monkeypatch, tmp_path)
    report = orr.run_start(run, dry_run=False, timeout=5)
    assert report["ok"] is True and report["rc"] == 0
    launch = _launch(tmp_path / "home")
    calls = _calls(log)
    assert calls, "the ordered chain must have invoked the fake rig"
    daemon_calls = [c for c in calls if c["argv"][:2] == ["daemon", "start"]]
    assert daemon_calls
    for call in calls:
        env = call["env"]
        assert env["OPENRIG_HOME"] == str(tmp_path / "home")
        assert env["OPENRIG_PORT"] == "12399"
        assert env["OPENRIG_ENTRY_LAUNCH_ID"] == launch["launchId"]
        assert env["OPENRIG_ENTRY_RUN_ID"] == "t-run"
    assert launch["phase"] == "active"


def test_launch_record_authorizes_managed_workflow_continuation(tmp_path):
    """S1-2: the live launch ticket must carry the repeatable continuation verbs.

    Without these entries the daemon's L0 guard denies the documented seat closure
    command (`rig workflow project`) even though `write_entry_records` wrote a live
    ticket. The startup/continuation split is asserted so a future edit cannot fold
    the continuation verbs into the single-consumption class silently.
    """
    run = _make_run(tmp_path)
    bridge, err = orr._load_bridge(run)
    assert err is None
    launch_id = orr.write_entry_records(run, bridge)
    launch = _launch(tmp_path / "home")
    assert launch["launchId"] == launch_id
    assert set(launch["verbs"]) == ENTRY_VERBS
    for verb in ("workflow-project", "workflow-route", "workflow-resume", "workflow-abort", "workflow-revision"):
        assert verb in launch["verbs"]
    assert set(launch["verbs"]) - STARTUP_ENTRY_VERBS == CONTINUATION_ENTRY_VERBS


def test_b4_and_b5_plan_contract(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    _env(monkeypatch, tmp_path)
    bridge, err = orr._load_bridge(run)
    assert err is None
    plan = orr.build_start_plan(run, bridge)
    up = plan[1]
    assert up["step"] == "up"
    assert {"--cwd", "--yes"} <= set(up["cmd"])
    assert "--non-interruptive" not in up["cmd"]
    assert up["cmd"][up["cmd"].index("--cwd") + 1] == str(tmp_path / "project-root")
    instantiate = plan[4]
    assert instantiate["step"] == "workflow-instantiate"
    assert "--root-objective" in instantiate["cmd"]
    assert "--created-by" in instantiate["cmd"]
    created_by = instantiate["cmd"][instantiate["cmd"].index("--created-by") + 1]
    assert "@" in created_by
    objective = instantiate["cmd"][instantiate["cmd"].index("--root-objective") + 1]
    assert objective.strip()


def test_write_failure_is_rc2_and_starts_no_rig(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    log = _env(monkeypatch, tmp_path)
    bridge_path = run / "openrig" / "OPENRIG-BRIDGE.json"
    bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x", encoding="utf-8")
    bridge["openrigHome"] = str(blocker / "home")
    bridge_path.write_text(json.dumps(bridge), encoding="utf-8")
    report = orr.run_start(run, dry_run=False, timeout=5)
    assert report["rc"] == 2 and report["ok"] is False
    assert "cannot write entry provenance" in report["error"]
    assert not log.exists(), "a provenance write failure must start zero children"


def test_marker_for_another_run_is_rc2(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    log = _env(monkeypatch, tmp_path)
    entry = tmp_path / "home" / "entry"
    entry.mkdir(parents=True)
    (entry / "managed-run.json").write_text(
        json.dumps({"schemaVersion": 1, "runId": "other-run"}), encoding="utf-8"
    )
    report = orr.run_start(run, dry_run=False, timeout=5)
    assert report["rc"] == 2
    assert "belongs to run" in report["error"]
    assert not log.exists()


def test_missing_openrig_home_is_rc2(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    log = _env(monkeypatch, tmp_path)
    bridge_path = run / "openrig" / "OPENRIG-BRIDGE.json"
    bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
    bridge.pop("openrigHome", None)
    bridge_path.write_text(json.dumps(bridge), encoding="utf-8")
    monkeypatch.delenv("OPENRIG_HOME", raising=False)
    report = orr.run_start(run, dry_run=False, timeout=5)
    assert report["rc"] == 2
    assert "openrigHome" in report["error"]
    assert not log.exists(), "a missing home must fail before any rig call"


def test_fake_rig_up_failure_rolls_back_and_writes_partial(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    log = _env(monkeypatch, tmp_path, FAKE_RIG_FAIL_STEP="up")
    report = orr.run_start(run, dry_run=False, timeout=5)
    assert report["rc"] == 1 and report["ok"] is False
    assert report["failedStep"] == "up"
    assert report["rollbackActions"] == [
        {"step": "daemon-stop", "rc": 0, "ok": True, "detail": '{"ok": true}'}
    ]
    steps = [c["argv"][:2] for c in _calls(log)]
    assert ["daemon", "start"] in steps
    assert ["daemon", "stop"] in steps
    launch = _launch(tmp_path / "home")
    assert launch["phase"] == "closed"
    assert "up" in launch["closureReason"]
    partial = Path(report["partialEvidence"])
    assert partial.is_file()
    data = json.loads(partial.read_text(encoding="utf-8"))
    assert data["failedStep"] == "up" and data["rollback"] and data["executed"]
    assert (tmp_path / "home" / "daemon.sqlite").is_file(), "rollback must never delete the DB"


def test_fake_rig_daemon_start_failure_skips_daemon_stop(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    log = _env(monkeypatch, tmp_path, FAKE_RIG_FAIL_STEP="daemon-start")
    report = orr.run_start(run, dry_run=False, timeout=5)
    assert report["rc"] == 1 and report["failedStep"] == "daemon-start"
    assert report["rollbackActions"] == []
    steps = [c["argv"][:2] for c in _calls(log)]
    assert ["daemon", "start"] in steps
    assert ["daemon", "stop"] not in steps


def test_manual_rollback_prints_only(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    log = _env(monkeypatch, tmp_path, FAKE_RIG_FAIL_STEP="up")
    report = orr.run_start(run, dry_run=False, timeout=5, rollback_mode="manual")
    assert report["rc"] == 1 and report["rollbackActions"] == []
    steps = [c["argv"][:2] for c in _calls(log)]
    assert ["daemon", "stop"] not in steps
    assert "down t-rig" in report["rollback"]
    assert "delete nothing automatically" in report["rollback"]


def test_precheck_failure_writes_no_chain(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    log = _env(monkeypatch, tmp_path, FAKE_RIG_MODE="incomplete")
    report = orr.run_start(run, dry_run=False, timeout=5)
    assert report["rc"] == 1 and report["failedStep"] == "precheck"
    steps = [c["argv"][:2] for c in _calls(log)]
    assert ["daemon", "start"] not in steps
    assert "nothing was started" in report["rollback"]
    assert _launch(tmp_path / "home")["phase"] == "closed"


def test_unorchestrated_fake_rig_call_is_rc2(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    _env(monkeypatch, tmp_path)
    rig = tmp_path / "fake-rig"
    proc = subprocess.run([str(rig), "send", "seat", "hi"], capture_output=True, text=True)
    assert proc.returncode == 2
    assert "unexpected fake rig call" in proc.stderr
