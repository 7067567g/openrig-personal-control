# -*- coding: utf-8 -*-
"""Packet C · R11 `openrig_run.py check/start` 单测（含负向）。

覆盖 TASK §3 / plan §4.4–4.5：
  - fake rig ready → check rc0；incomplete seat / daemon down → rc1
  - daemon down + --allow-daemon-down → rc0（降级 WARN）
  - bridge 缺失/坏 JSON → rc2
  - --strict-render 下 manifest mismatch → rc1（默认 WARN 不阻塞）
  - doctor rc≠0 / workflow validate rc≠0 → 阻塞
  - start --dry-run 只返回命令序列：**不调用 fake rig**
  - start 真实链路：daemon→up→poll→validate→instantiate，首步失败即停并给回滚提示
"""

import hashlib
import json
import os
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import openrig_run as orr  # noqa: E402

FAKE_RIG = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path

log = os.environ.get("FAKE_RIG_LOG")
if log:
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(" ".join(sys.argv[1:]) + "\n")

mode = os.environ.get("FAKE_RIG_MODE", "ready")
args = sys.argv[1:]

if args[:2] == ["workflow", "validate"]:
    fail = os.environ.get("FAKE_RIG_VALIDATE_FAIL") == "1"
    print(json.dumps({"ok": not fail, "error": None if not fail else "bad spec"}))
    sys.exit(0 if not fail else 1)

if args[:1] == ["ps"]:
    if mode == "daemon-down":
        print("daemon not running", file=sys.stderr)
        sys.exit(1)
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

if args[:2] == ["daemon", "start"] or args[:1] == ["up"] or args[:2] == ["workflow", "instantiate"]:
    if os.environ.get("FAKE_RIG_UP_FAIL") == "1" and args[:1] == ["up"]:
        print("up failed: seat launch error", file=sys.stderr)
        sys.exit(1)
    print(json.dumps({"ok": True}))
    sys.exit(0)

print("unexpected fake rig call: " + " ".join(args), file=sys.stderr)
sys.exit(9)
'''

FAKE_DOCTOR_OK = '''#!/usr/bin/env python3
import os, sys
if os.environ.get("FAKE_DOCTOR_FAIL") == "1":
    print("FAIL bridge rig mismatch")
    sys.exit(1)
print("PASS bridge fake=ok")
sys.exit(0)
'''


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_run(tmp_path: Path, *, seats=None, manifest="good") -> Path:
    run = tmp_path / "runs" / "t-run"
    openrig = run / "openrig"
    (openrig / "tools").mkdir(parents=True)
    (openrig / "rig.yaml").write_text("rig: t\n", encoding="utf-8")
    (openrig / "workflow.yaml").write_text("workflow: t\n", encoding="utf-8")
    seats = seats or {"main": "main@t", "tdo": "tdo@t"}
    bridge = {
        "schemaVersion": 2,
        "runId": "t-run",
        "rigName": "t-rig",
        "workflowId": "t-workflow",
        "rigSpec": "rig.yaml",
        "workflowSpec": "workflow.yaml",
        "openrigCli": str(tmp_path / "fake-rig"),
        "openrigHome": str(tmp_path / "home"),
        "daemonPort": 12345,
        "seatMap": seats,
    }
    (openrig / "OPENRIG-BRIDGE.json").write_text(json.dumps(bridge), encoding="utf-8")
    files = {}
    for rel in ("rig.yaml", "workflow.yaml"):
        p = openrig / rel
        sha = _sha(p) if manifest == "good" else "0" * 64
        files[rel] = {"bytes": len(p.read_bytes()), "sha256": sha}
    (openrig / "render-manifest.json").write_text(
        json.dumps({"schemaVersion": 1, "runId": "t-run", "files": files}), encoding="utf-8"
    )
    (openrig / "tools" / "openrig_bridge.py").write_text(FAKE_DOCTOR_OK, encoding="utf-8")

    rig = tmp_path / "fake-rig"
    rig.write_text(FAKE_RIG, encoding="utf-8")
    rig.chmod(0o755)
    return run


def _env(monkeypatch, tmp_path, **kw):
    log = tmp_path / "fake-rig.log"
    values = {
        "FAKE_RIG_LOG": str(log),
        "FAKE_RIG_MODE": "ready",
        "FAKE_RIG_SEATS": json.dumps(["main@t", "tdo@t"]),
    }
    values.update(kw)
    for k, v in values.items():
        monkeypatch.setenv(k, v)
    return log


def _statuses(report):
    return {c["id"]: c["status"] for c in report["checks"]}


def test_check_ready_passes(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    log = _env(monkeypatch, tmp_path)
    report = orr.run_check(run)
    assert report["ok"] is True and report["rc"] == 0
    assert _statuses(report) == {
        "bridge": "ok",
        "render": "ok",
        "doctor": "ok",
        "workflow_validate": "ok",
        "seats": "ok",
    }
    assert report["next"] == []
    assert log.read_text(encoding="utf-8").count("ps --nodes") == 1


def test_check_incomplete_seat_fails(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    _env(monkeypatch, tmp_path, FAKE_RIG_MODE="incomplete")
    report = orr.run_check(run)
    assert report["ok"] is False and report["rc"] == 1
    seats = next(c for c in report["checks"] if c["id"] == "seats")
    assert seats["status"] == "fail"
    assert "missing=['tdo']" in seats["detail"]


def test_check_daemon_down_blocks_unless_allowed(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    _env(monkeypatch, tmp_path, FAKE_RIG_MODE="daemon-down")
    blocked = orr.run_check(run)
    assert blocked["ok"] is False and blocked["rc"] == 1
    assert _statuses(blocked)["seats"] == "fail"

    allowed = orr.run_check(run, allow_daemon_down=True)
    assert allowed["ok"] is True and allowed["rc"] == 0
    assert _statuses(allowed)["seats"] == "warn"
    assert _statuses(allowed)["workflow_validate"] == "skipped"
    assert any("daemon start" in n for n in allowed["next"])


def test_check_missing_bridge_is_rc2(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    _env(monkeypatch, tmp_path)
    (run / "openrig" / "OPENRIG-BRIDGE.json").unlink()
    report = orr.run_check(run)
    assert report["rc"] == 2 and report["ok"] is False
    assert report["checks"][0]["id"] == "bridge"


def test_check_bad_bridge_json_is_rc2(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    _env(monkeypatch, tmp_path)
    (run / "openrig" / "OPENRIG-BRIDGE.json").write_text("{not json", encoding="utf-8")
    assert orr.run_check(run)["rc"] == 2


def test_check_render_mismatch_warns_by_default_blocks_when_strict(tmp_path, monkeypatch):
    run = _make_run(tmp_path, manifest="bad")
    _env(monkeypatch, tmp_path)
    default = orr.run_check(run)
    assert default["rc"] == 0 and _statuses(default)["render"] == "warn"
    strict = orr.run_check(run, strict_render=True)
    assert strict["rc"] == 1 and _statuses(strict)["render"] == "fail"


def test_check_doctor_failure_blocks(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    _env(monkeypatch, tmp_path, FAKE_DOCTOR_FAIL="1")
    report = orr.run_check(run)
    assert report["rc"] == 1
    assert _statuses(report)["doctor"] == "fail"


def test_check_workflow_validate_failure_blocks(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    _env(monkeypatch, tmp_path, FAKE_RIG_VALIDATE_FAIL="1")
    report = orr.run_check(run)
    assert report["rc"] == 1
    assert _statuses(report)["workflow_validate"] == "fail"


def test_start_dry_run_calls_no_live_command(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    log = _env(monkeypatch, tmp_path)
    report = orr.run_start(run, dry_run=True)
    assert report["ok"] is True and report["rc"] == 0
    assert report["dryRun"] is True
    steps = [p["step"] for p in report["plan"]]
    assert steps == [
        "daemon-start",
        "up",
        "wait-ready",
        "workflow-validate",
        "workflow-instantiate",
    ]
    joined = " ".join(" ".join(p["cmd"]) for p in report["plan"])
    assert "daemon start --no-kernel --port 12345" in joined
    assert "workflow instantiate" in joined
    assert report["executed"] == []
    assert not log.exists(), "dry-run must not invoke the rig CLI"


def test_start_dry_run_still_reports_bad_bridge(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    _env(monkeypatch, tmp_path)
    (run / "openrig" / "OPENRIG-BRIDGE.json").unlink()
    report = orr.run_start(run, dry_run=True)
    assert report["rc"] == 2 and report["ok"] is False and report["plan"] == []


def test_start_runs_ordered_chain(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    log = _env(monkeypatch, tmp_path)
    report = orr.run_start(run, dry_run=False, timeout=5)
    assert report["ok"] is True and report["rc"] == 0
    steps = [e["step"] for e in report["executed"]]
    assert steps[0] == "precheck"
    assert steps[1:] == [
        "daemon-start",
        "up",
        "wait-ready",
        "workflow-validate",
        "workflow-instantiate",
    ]
    calls = log.read_text(encoding="utf-8").splitlines()
    assert any(c.startswith("daemon start --no-kernel --port 12345") for c in calls)
    assert any(c.startswith("up ") for c in calls)
    # precheck also calls ps + workflow validate before the chain starts
    assert calls.count("workflow validate " + str(run / "openrig" / "workflow.yaml") + " --json") == 2


def test_start_stops_at_first_failure_with_rollback(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    _env(monkeypatch, tmp_path, FAKE_RIG_UP_FAIL="1")
    report = orr.run_start(run, dry_run=False, timeout=5)
    assert report["ok"] is False and report["rc"] == 1
    assert report["failedStep"] == "up"
    steps = [e["step"] for e in report["executed"]]
    assert steps[-1] == "up"
    assert "daemon-start" in steps
    assert "workflow-instantiate" not in steps
    assert "down t-rig" in report["rollback"]
    assert "delete nothing automatically" in report["rollback"]


def test_start_fails_when_precheck_fails(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    log = _env(monkeypatch, tmp_path, FAKE_RIG_MODE="incomplete")
    report = orr.run_start(run, dry_run=False, timeout=5)
    assert report["rc"] == 1 and report["failedStep"] == "precheck"
    calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    assert not any(c.startswith("daemon start") for c in calls)
    assert "nothing was started" in report["rollback"]


# ---------------------------------------------------------------- R14 next (paved road)
NEXT_COMMANDS = [
    "openrig-run check --run-dir {rd}",
    "openrig-run start --run-dir {rd} --dry-run",
    "openrig-run start --run-dir {rd}",
    "verify_render.py --run-dir {rd} --strict",
    "wf.py archive-gate t-run",
]


def _tree_snapshot(root: Path) -> dict:
    return {
        str(path.relative_to(root)): _sha(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_next_prints_canonical_order(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    _env(monkeypatch, tmp_path)
    report = orr.run_next(run)
    assert report["ok"] is True and report["rc"] == 0
    assert [s["order"] for s in report["steps"]] == [1, 2, 3, 4, 5]
    expected = [cmd.format(rd=run) for cmd in NEXT_COMMANDS]
    assert [s["command"] for s in report["steps"]] == expected
    assert [s["id"] for s in report["steps"]] == [
        "check",
        "start-dry-run",
        "start",
        "verify-render",
        "archive-gate",
    ]
    assert len(report["modeHints"]) == 2
    assert any("local-only" in hint for hint in report["modeHints"])
    assert any("hybrid" in hint for hint in report["modeHints"])


def test_next_makes_no_live_calls(tmp_path, monkeypatch, capsys):
    run = _make_run(tmp_path)
    log = _env(monkeypatch, tmp_path)
    calls = {"run": 0, "popen": 0}

    def boom_run(*args, **kwargs):  # pragma: no cover - must never fire
        calls["run"] += 1
        raise AssertionError("next must not call subprocess.run")

    def boom_popen(*args, **kwargs):  # pragma: no cover - must never fire
        calls["popen"] += 1
        raise AssertionError("next must not call subprocess.Popen")

    monkeypatch.setattr(orr.subprocess, "run", boom_run)
    monkeypatch.setattr(orr.subprocess, "Popen", boom_popen)

    report = orr.run_next(run)
    assert report["ok"] is True
    rc = orr.main(["next", "--run-dir", str(run), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0 and payload["ok"] is True
    assert calls == {"run": 0, "popen": 0}
    assert not log.exists(), "next must not invoke the rig CLI"


def test_next_missing_bridge_is_rc2(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    _env(monkeypatch, tmp_path)
    (run / "openrig" / "OPENRIG-BRIDGE.json").unlink()
    report = orr.run_next(run)
    assert report["rc"] == 2 and report["ok"] is False
    assert report["steps"] == []
    assert "bridge" in report["error"]


def test_next_writes_no_files(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    _env(monkeypatch, tmp_path)
    before = _tree_snapshot(run)
    orr.run_next(run)
    orr.main(["next", "--run-dir", str(run), "--json"])
    assert _tree_snapshot(run) == before

