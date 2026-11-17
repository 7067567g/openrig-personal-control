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
import stat
import sys
import threading
import time
from pathlib import Path

import pytest

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
large_step = os.environ.get("FAKE_RIG_LARGE_STEP", "")
large_bytes = int(os.environ.get("FAKE_RIG_LARGE_BYTES", "0") or "0")
echo_secret_env = os.environ.get("FAKE_RIG_ECHO_SECRET_ENV", "")
if echo_secret_env:
    print("fixture secret=" + os.environ.get(echo_secret_env, ""), file=sys.stderr)
    sys.stderr.flush()

def emit_large(step):
    if large_step == step and large_bytes > 0:
        sys.stdout.write("S" * large_bytes + "\n")
        sys.stdout.flush()
        sys.stderr.write("E" * large_bytes + "\n")
        sys.stderr.flush()

if args[:2] == ["workflow", "validate"]:
    fail = os.environ.get("FAKE_RIG_VALIDATE_FAIL") == "1"
    emit_large("workflow-validate")
    print(json.dumps({"ok": not fail, "error": None if not fail else "bad spec"}))
    sys.exit(0 if not fail else 1)

if args[:1] == ["ps"]:
    emit_large("wait-ready")
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

if args[:2] == ["workflow", "instantiate"] and os.environ.get("FAKE_RIG_INSTANTIATE_FAIL") == "1":
    emit_large("workflow-instantiate")
    print("instantiate failed: fixture refusal", file=sys.stderr)
    sys.exit(1)

if args[:2] == ["workflow", "instantiate"] and os.environ.get("FAKE_RIG_INSTANTIATE_NESTED") == "1":
    emit_large("workflow-instantiate")
    print(json.dumps({"instance": {"instanceId": "wf-live-1",
                                   "currentFrontier": ["qitem-live-1"]}}))
    sys.exit(0)

if args[:2] == ["daemon", "start"] or args[:1] == ["up"] or args[:2] == ["workflow", "instantiate"]:
    step = "daemon-start" if args[:2] == ["daemon", "start"] else ("up" if args[:1] == ["up"] else "workflow-instantiate")
    emit_large(step)
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


REAL_ACCEPTANCE_IDS = [
    "AT-DESIGN-INHERIT-01",
    "AT-DESIGN-INHERIT-02",
    "AT-DESIGN-HUMAN-GATE-01",
    "AT-DESIGN-SOURCE-COVERAGE-01",
    "AT-DESIGN-QA-HISTORY-01",
    "AT-DESIGN-QA-HISTORY-02",
    "AT-DESIGN-QA-HISTORY-03",
    "AT-DESIGN-QA-HISTORY-04",
    "AT-DESIGN-QA-HISTORY-05",
    "AT-DESIGN-QA-HISTORY-06",
    "AT-DESIGN-QA-HISTORY-07",
    "AT-DESIGN-QA-HISTORY-08",
    "AT-DESIGN-INTERFACE-01",
    "AT-DESIGN-START-01",
    "AT-DESIGN-START-02",
    "AT-DESIGN-STATE-MACHINE-01",
    "AT-DESIGN-SUPERVISOR-01",
    "AT-DESIGN-SUPERVISOR-02",
    "AT-DESIGN-READY-01",
    "AT-DESIGN-RESTORE-OUTCOME-01",
    "AT-DESIGN-DEADLINE-01",
    "AT-DESIGN-SCOPE-01",
    "AT-DESIGN-HOPS-01",
    "AT-DESIGN-AUTOMATION-01",
    "AT-DESIGN-AUTOMATION-02",
    "AT-DESIGN-AUTOMATION-03",
    "AT-DESIGN-PREFLIGHT-01",
    "AT-DESIGN-EVIDENCE-01",
    "AT-DESIGN-EVIDENCE-02",
    "AT-DESIGN-GATE-ORDER-01",
    "AT-DESIGN-RENDER-DRIFT-01",
    "AT-DESIGN-TOKEN-GOV-01",
    "AT-DESIGN-CONTEXT-BUDGET-01",
    "AT-DESIGN-CONTINUITY-01",
    "AT-DESIGN-CONTINUITY-02",
    "AT-DESIGN-CONTINUITY-03",
    "AT-DESIGN-CONTINUITY-04",
    "AT-DESIGN-COMPACTION-01",
    "AT-DESIGN-HANDOVER-01",
    "AT-DESIGN-ARCHIVE-01",
    "AT-DESIGN-SEAT-WRITE-01",
    "AT-DESIGN-HUMAN-GATE-02",
    "AT-DESIGN-MANIFEST-01",
    "AT-DESIGN-TOKEN-JOIN-01",
    "AT-DESIGN-TOKEN-READSURFACE-01",
    "AT-DESIGN-TREE-SCHEMA-01",
    "AT-DESIGN-E2E-01",
    "AT-DESIGN-WORKFLOW-INVARIANTS-01",
    "AT-DESIGN-CLOSEOUT-01",
    "AT-DESIGN-CLOSEOUT-02",
    "AT-DESIGN-DUAL-FINAL-01",
    "AT-DESIGN-INTEGRITY-01",
    "AT-DESIGN-INTEGRITY-02",
    "AT-DESIGN-INTEGRITY-03",
    "AT-DESIGN-INTEGRITY-04",
    "AT-DESIGN-INTEGRITY-05",
    "AT-DESIGN-BASELINE-01",
]
REAL_SOURCE_SHA256 = (
    "e01443e5a8c76bd9465b8c9b0cfca043411324d8d249ab90b884c401486d36e9"
)


def _valid_findings_policy() -> dict:
    """Synthetic 106-finding policy with the current 95 mapped / 11 deferred shape.

    The closure fields mirror the real policy contract: disposition/mapping are
    compatible, every acceptanceTestId resolves to the embedded 57-id inventory,
    and counts exactly match the matrix.  This is a fixture, not a weaker schema.
    """
    acceptance_ids = list(REAL_ACCEPTANCE_IDS)
    findings = []
    for index in range(95):
        disposition = "adopt" if index < 50 else "already-covered"
        findings.append(
            {
                "findingId": f"HF-{index + 1:03d}",
                "severity": ("S1", "S2", "S3")[index % 3],
                "disposition": disposition,
                "findingClass": "design_gap" if disposition == "adopt" else "already_covered",
                "acceptanceTestId": acceptance_ids[index % len(acceptance_ids)],
                "implementationAnchor": f"fixture implementation anchor {index + 1}",
                "mapping": {
                    "kind": "defense",
                    "defenseId": f"D{index % 25 + 1:02d}",
                },
            }
        )
    for offset in range(11):
        index = 95 + offset
        findings.append(
            {
                "findingId": f"HF-{index + 1:03d}",
                "severity": "S2",
                "disposition": "defer",
                "findingClass": "unimplemented",
                "acceptanceTestId": acceptance_ids[index % len(acceptance_ids)],
                "implementationAnchor": f"fixture deferral anchor {index + 1}",
                "mapping": {
                    "kind": "deferred",
                    "decisionId": "H-01",
                    "reason": "explicit historical decision deferral with a named owner",
                },
            }
        )
    counts = {"DEFERRED": 11}
    for finding in findings:
        mapping = finding["mapping"]
        if mapping["kind"] == "defense":
            key = mapping["defenseId"]
            counts[key] = counts.get(key, 0) + 1
    return {
        "schemaVersion": 1,
        "acceptanceTestInventory": {
            "source": "fixture://EXECUTION-TREE-v2.json#acceptanceMap",
            "sourceSchema": "acceptanceMap",
            "sourceSha256": REAL_SOURCE_SHA256,
            "testIds": acceptance_ids,
        },
        "counts": {key: counts[key] for key in sorted(counts)},
        "findings": findings,
    }


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
    (openrig / "HISTORICAL-FINDINGS-POLICY.json").write_text(
        json.dumps(_valid_findings_policy()), encoding="utf-8"
    )
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
    monkeypatch.delenv(orr.of.ENV_VAR, raising=False)
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
        "historical_findings": "ok",
        "render": "ok",
        "doctor": "ok",
        "workflow_validate": "ok",
        "seats": "ok",
    }
    assert report["next"] == []
    assert log.read_text(encoding="utf-8").count("ps --nodes") == 1


def test_check_mounts_106_finding_policy_with_path_and_sha(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    _env(monkeypatch, tmp_path)
    report = orr.run_check(run)

    check = next(c for c in report["checks"] if c["id"] == "historical_findings")
    policy_path = run / "openrig" / "HISTORICAL-FINDINGS-POLICY.json"
    assert check["status"] == "ok"
    assert check["findingsCount"] == 106
    assert check["mappedCount"] == 95
    assert check["deferredCount"] == 11
    assert check["path"] == str(policy_path)
    assert check["sha256"] == _sha(policy_path)
    assert "findings=106 mapped=95 deferred=11" in check["detail"]
    assert str(policy_path) in check["detail"]
    assert check["sha256"][:12] in check["detail"]


def test_check_invalid_policy_blocks_before_any_child(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    policy = _valid_findings_policy()
    policy["findings"].pop()
    (run / "openrig" / "HISTORICAL-FINDINGS-POLICY.json").write_text(
        json.dumps(policy), encoding="utf-8"
    )
    log = _env(monkeypatch, tmp_path)

    report = orr.run_check(run)

    assert report["ok"] is False and report["rc"] == 1
    assert [check["id"] for check in report["checks"]] == ["bridge", "historical_findings"]
    check = report["checks"][-1]
    assert check["status"] == "fail"
    assert "exactly 106 entries; got 105" in check["detail"]
    assert check.get("blocking") is True
    assert not log.exists(), "a blocked static policy must not invoke any rig child"


def test_check_missing_policy_blocks_before_any_child(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    (run / "openrig" / "HISTORICAL-FINDINGS-POLICY.json").unlink()
    monkeypatch.setattr(orr.of, "DEFAULT_POLICY_PATH", tmp_path / "missing-default.json")
    log = _env(monkeypatch, tmp_path)

    report = orr.run_check(run)

    assert report["ok"] is False and report["rc"] == 1
    check = report["checks"][-1]
    assert check["id"] == "historical_findings" and check["status"] == "fail"
    assert "policy unavailable" in check["detail"]
    assert orr.of.ENV_VAR in check["detail"]
    assert not log.exists(), "a missing policy must not be silently skipped"


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


def test_start_with_invalid_policy_stops_at_precheck_with_zero_rig_children(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    policy = _valid_findings_policy()
    policy["schemaVersion"] = 2
    (run / "openrig" / "HISTORICAL-FINDINGS-POLICY.json").write_text(
        json.dumps(policy), encoding="utf-8"
    )
    log = _env(monkeypatch, tmp_path)

    report = orr.run_start(run, dry_run=False, timeout=5)

    assert report["ok"] is False and report["rc"] == 1
    assert report["failedStep"] == "precheck"
    assert [step["step"] for step in report["executed"]] == ["precheck"]
    assert "historical findings policy" in report["detail"]
    assert not log.exists(), "no daemon/up/validate/instantiate child may start"


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



# ------------------------------------------------------- P-S10-02: manifest wiring
S11A_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "kickoff"
    / "openrig-round1-postrun-20261117"
    / "run-manifest.schema.s11a.json"
)


def _assert_s11a_shape(manifest: dict) -> None:
    """Shape assertions always run; full jsonschema validation runs when available."""
    schema = json.loads(S11A_SCHEMA_PATH.read_text(encoding="utf-8"))
    top = schema["properties"]
    assert set(manifest) <= set(top), "top-level additionalProperties:false violated"
    assert set(schema["required"]) <= set(manifest)
    assert manifest["status"] in top["status"]["enum"]
    if manifest["seats"]:
        seat_props = top["seats"]["items"]["properties"]
        for seat in manifest["seats"]:
            assert set(seat) <= set(seat_props)
            assert seat["actualOutcome"] in seat_props["actualOutcome"]["enum"]
            assert seat["actualOutcome"] is not None
            if "session" in seat:
                assert seat["session"] in seat_props["session"]["enum"]
            if "activity" in seat:
                assert seat["activity"] in seat_props["activity"]["enum"]
    assert isinstance(manifest["workflow"]["instanceId"], str)
    assert isinstance(manifest["workflow"]["entryQitemId"], str)
    for output in manifest["outputs"]:
        assert {"path", "sha256", "bytes", "producer"} <= set(output)
    try:
        import jsonschema
    except ImportError:
        return
    jsonschema.validate(manifest, schema)


def _manifest(run: Path) -> dict:
    return json.loads(
        (run / "reports" / "evidence" / "manifest" / "run-manifest.json").read_text()
    )


def test_start_success_manifest_has_real_seats_and_start_receipt(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    _env(monkeypatch, tmp_path, FAKE_RIG_INSTANTIATE_NESTED="1")

    report = orr.run_start(run, dry_run=False, timeout=5)

    assert report["ok"] is True, report
    manifest = _manifest(run)
    assert manifest["status"] == "active"
    assert manifest["workflow"]["instanceId"] == "wf-live-1"
    assert len(manifest["seats"]) == 2
    assert {s["logicalId"] for s in manifest["seats"]} == {"main", "tdo"}
    assert all(s["observed"] is True for s in manifest["seats"])
    assert all(s["startupStatus"] == "ready" for s in manifest["seats"])
    assert "seatsNotApplicableReason" not in manifest
    assert "outputsNotApplicableReason" not in manifest

    assert manifest["outputs"], "a successful start must attest a real output"
    receipt_output = next(
        out for out in manifest["outputs"] if out["path"].endswith("start-receipt.json")
    )
    receipt_path = Path(receipt_output["path"])
    assert receipt_path.is_file()
    assert receipt_output["sha256"] == _sha(receipt_path)
    assert receipt_output["bytes"] == receipt_path.stat().st_size
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["runId"] == "t-run"
    assert receipt["launchId"]
    assert receipt["workflow"]["instanceId"] == "wf-live-1"
    assert len(receipt["seats"]) == 2
    assert receipt["stepCount"] == len(manifest["steps"])
    assert receipt["capturedAt"]


def test_start_redacts_known_secret_from_runtime_tails_and_receipts(
    tmp_path, monkeypatch
):
    """P-S10-03: raw bytes may be private evidence, but proof tails carry no secret."""
    secret = "p-s10-03-start-secret"
    run = _make_run(tmp_path)
    _env(
        monkeypatch,
        tmp_path,
        FAKE_RIG_INSTANTIATE_NESTED="1",
        FAKE_RIG_ECHO_SECRET_ENV="OPENRIG_FIXTURE_SECRET_TOKEN",
    )
    monkeypatch.setenv("OPENRIG_FIXTURE_SECRET_TOKEN", secret)

    report = orr.run_start(run, dry_run=False, timeout=5)

    assert report["ok"] is True, report
    assert secret not in json.dumps(report)
    assert secret not in (run / "reports" / "evidence" / "manifest" / "run-manifest.json").read_text(
        encoding="utf-8"
    )
    assert secret not in (run / "reports" / "evidence" / "start-receipt.json").read_text(
        encoding="utf-8"
    )
    for entry in report["executed"]:
        path = entry.get("evidencePath")
        if path:
            assert secret not in Path(path).read_text(encoding="utf-8")
    assert any("fixture secret=<redacted>" in e.get("stderrTail", "") for e in report["executed"])


def test_start_large_child_output_spills_full_bytes_and_bounds_proof(
    tmp_path, monkeypatch
):
    """P-S10-03 success path: 2 MiB streams, 4 KiB tails, real spill on disk."""
    import stat

    import openrig_runtime_output as ort

    run = _make_run(tmp_path)
    large = 2 * 1024 * 1024
    _env(
        monkeypatch,
        tmp_path,
        FAKE_RIG_INSTANTIATE_NESTED="1",
        FAKE_RIG_LARGE_STEP="daemon-start",
        FAKE_RIG_LARGE_BYTES=str(large),
    )

    report = orr.run_start(run, dry_run=False, timeout=10)

    assert report["ok"] is True, report
    executed = next(e for e in report["executed"] if e["step"] == "daemon-start")
    assert "stdout" not in executed and "stderr" not in executed
    assert executed["stdoutBytes"] >= large + 1
    assert executed["stderrBytes"] >= large + 1
    assert len(executed["stdoutTail"].encode()) <= ort.TAIL_BYTES
    assert executed["stdoutTruncated"] is True
    stdout_spill = Path(executed["stdoutPath"])
    assert stdout_spill.stat().st_size == executed["stdoutBytes"]
    assert _sha(stdout_spill) == executed["stdoutSha256"]
    assert stat.S_IMODE(stdout_spill.stat().st_mode) == 0o600

    sidecar = json.loads(Path(executed["evidencePath"]).read_text(encoding="utf-8"))
    assert sidecar["streams"]["stdout"]["bytes"] == executed["stdoutBytes"]
    assert sidecar["streams"]["stdout"]["truncated"] is True
    assert sidecar["streams"]["stdout"]["tailBytes"] == ort.TAIL_BYTES

    manifest = _manifest(run)
    step = next(s for s in manifest["steps"] if s["stepId"] == "daemon-start")
    assert step["stdoutSha256"] == executed["stdoutSha256"]
    assert step["evidencePath"] == executed["evidencePath"]
    receipt_path = run / "reports" / "evidence" / "start-receipt.json"
    assert stat.S_IMODE(receipt_path.stat().st_mode) == 0o600
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt_step = next(s for s in receipt["steps"] if s["step"] == "daemon-start")
    assert receipt_step["stdoutBytes"] == executed["stdoutBytes"]
    assert receipt_step["stdoutPath"] == str(stdout_spill.resolve())
    assert "S" * 10000 not in json.dumps(report)
    assert "S" * 10000 not in json.dumps(receipt)
    assert "S" * 10000 not in json.dumps(manifest)


def test_start_large_failure_writes_bounded_partial_and_keeps_spill(
    tmp_path, monkeypatch
):
    """P-S10-03 failure/partial path: full stream on disk, no blob in failure proof."""
    import openrig_runtime_output as ort

    run = _make_run(tmp_path)
    large = 2 * 1024 * 1024
    _env(
        monkeypatch,
        tmp_path,
        FAKE_RIG_UP_FAIL="1",
        FAKE_RIG_LARGE_STEP="up",
        FAKE_RIG_LARGE_BYTES=str(large),
    )

    report = orr.run_start(run, dry_run=False, timeout=10)

    assert report["ok"] is False and report["failedStep"] == "up"
    failed = report["executed"][-1]
    assert failed["step"] == "up" and failed["stdoutBytes"] == large + 1
    assert len(failed["stdoutTail"].encode()) <= ort.TAIL_BYTES
    assert Path(failed["stdoutPath"]).stat().st_size == large + 1
    partial_path = run / "reports" / "evidence" / "manifest" / "run-manifest.partial.json"
    partial_text = partial_path.read_text(encoding="utf-8")
    partial = json.loads(partial_text)
    assert "S" * 10000 not in partial_text
    assert "E" * 10000 not in partial_text
    up_step = next(s for s in partial["steps"] if s["stepId"] == "up")
    assert up_step["evidencePath"] == failed["evidencePath"]
    sidecar = json.loads(Path(up_step["evidencePath"]).read_text(encoding="utf-8"))
    assert sidecar["streams"]["stdout"]["bytes"] == large + 1
    assert sidecar["streams"]["stdout"]["truncated"] is True
    assert sidecar["streams"]["stdout"]["tailBytes"] == ort.TAIL_BYTES
    assert len(partial_text.encode("utf-8")) < 200_000


def test_start_failure_partial_writes_machine_readable_na_reasons(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    _env(monkeypatch, tmp_path, FAKE_RIG_UP_FAIL="1")

    report = orr.run_start(run, dry_run=False, timeout=5)

    assert report["ok"] is False and report["failedStep"] == "up"
    partial = json.loads(
        (run / "reports" / "evidence" / "manifest" / "run-manifest.partial.json").read_text()
    )
    assert partial["status"] == "failed"
    assert partial["seats"] == []
    assert partial["seatsNotApplicableReason"] == "start_failed_before_seat_observation"
    assert partial["outputs"] == []
    assert partial["outputsNotApplicableReason"] == "start_failed_before_success_output"


def test_start_failure_after_ready_keeps_observed_seats(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    _env(monkeypatch, tmp_path, FAKE_RIG_INSTANTIATE_FAIL="1")

    report = orr.run_start(run, dry_run=False, timeout=5)

    assert report["ok"] is False and report["failedStep"] == "workflow-instantiate"
    partial = json.loads(
        (run / "reports" / "evidence" / "manifest" / "run-manifest.partial.json").read_text()
    )
    assert len(partial["seats"]) == 2, "a ready poll is real seat evidence even on failure"
    assert "seatsNotApplicableReason" not in partial
    assert partial["outputs"] == []
    assert partial["outputsNotApplicableReason"] == "start_failed_before_success_output"


def test_start_manifest_conforms_to_s11a_schema_shape(tmp_path, monkeypatch):
    run = _make_run(tmp_path)
    _env(monkeypatch, tmp_path, FAKE_RIG_INSTANTIATE_NESTED="1")

    report = orr.run_start(run, dry_run=False, timeout=5)

    assert report["ok"] is True, report
    manifest = _manifest(run)
    assert S11A_SCHEMA_PATH.is_file()
    _assert_s11a_shape(manifest)
    assert manifest["status"] == "active"
    assert manifest["workflow"]["instanceId"] == "wf-live-1"


# ---------------------------------------------------------------- P-011: live identity
def test_start_records_instance_and_entry_qitem_from_instantiate_stdout(tmp_path, monkeypatch):
    """A live start must attest its instance; `continuity-state.json` is fixture-only.

    Attempt 3 (2026-11-16T11:05Z) started successfully — instance 01M7J0H3... in the
    instantiate stdout, entry qitem on the frontier — yet the manifest recorded null, so
    CERT-01 read workflowInstantiated=false on a run that had in fact instantiated.
    """
    run = _make_run(tmp_path)
    _env(monkeypatch, tmp_path, FAKE_RIG_INSTANTIATE_NESTED="1")
    report = orr.run_start(run, dry_run=False, timeout=5)

    assert report["ok"] is True, report
    manifest = json.loads(
        (run / "reports" / "evidence" / "manifest" / "run-manifest.json").read_text())
    assert manifest["workflow"]["instanceId"] == "wf-live-1"
    assert manifest["workflow"]["entryQitemId"] == "qitem-live-1"
    assert report["manifest"]["missingKeys"] == []


def test_start_does_not_fabricate_an_instance_id(tmp_path, monkeypatch):
    """No nested payload and no fixture state: record empty, never a guess."""
    run = _make_run(tmp_path)
    _env(monkeypatch, tmp_path)
    report = orr.run_start(run, dry_run=False, timeout=5)

    assert report["ok"] is True
    manifest = json.loads(
        (run / "reports" / "evidence" / "manifest" / "run-manifest.json").read_text())
    assert manifest["workflow"]["instanceId"] == ""
    assert manifest["workflow"]["entryQitemId"] == ""
    assert manifest["status"] == "active"


def test_instantiate_identity_parser_shapes():
    assert orr._instantiate_identity(
        '{"instance": {"instanceId": "wf-1", "currentFrontier": ["q-1"]}}'
    ) == ("wf-1", "q-1")
    assert orr._instantiate_identity('{"instance": {"instanceId": "wf-2"}}') == ("wf-2", None)
    assert orr._instantiate_identity('{"ok": true}') == (None, None)
    assert orr._instantiate_identity("not json") == (None, None)
    assert orr._instantiate_identity("") == (None, None)


def test_workflow_identity_ignores_a_failed_instantiate_step(tmp_path):
    """A failed instantiate step cannot attest an instance, even if its stdout looks right."""
    executed = [{"step": "workflow-instantiate", "rc": 1,
                 "stdout": '{"instance": {"instanceId": "wf-ghost", "currentFrontier": ["q-ghost"]}}'}]
    instance_id, entry_qitem = orr._workflow_identity(tmp_path, executed)
    assert instance_id is None and entry_qitem is None

    executed[0]["rc"] = 0
    instance_id, entry_qitem = orr._workflow_identity(tmp_path, executed)
    assert (instance_id, entry_qitem) == ("wf-ghost", "q-ghost")


def test_workflow_identity_fails_closed_when_failed_step_has_fixture_state(tmp_path):
    """A failed step must not fall back to a fixture continuity-state.json (P-011b)."""
    (tmp_path / "openrig").mkdir()
    (tmp_path / "openrig" / "continuity-state.json").write_text(
        json.dumps({"workflowInstanceId": "wf-fixture"}), encoding="utf-8")
    executed = [{"step": "workflow-instantiate", "rc": 1,
                 "stdout": '{"instance": {"instanceId": "wf-ghost", "currentFrontier": ["q-ghost"]}}'}]
    assert orr._workflow_identity(tmp_path, executed) == (None, None)


def test_workflow_identity_prefers_successful_step_over_fixture_state(tmp_path):
    """A successful step wins; the fixture value never merges into it."""
    (tmp_path / "openrig").mkdir()
    (tmp_path / "openrig" / "continuity-state.json").write_text(
        json.dumps({"workflowInstanceId": "wf-fixture"}), encoding="utf-8")
    executed = [{"step": "workflow-instantiate", "rc": 0,
                 "stdout": '{"instance": {"instanceId": "wf-real", "currentFrontier": ["q-real"]}}'}]
    assert orr._workflow_identity(tmp_path, executed) == ("wf-real", "q-real")


def test_workflow_identity_uses_fixture_only_when_no_step_ran(tmp_path):
    (tmp_path / "openrig").mkdir()
    (tmp_path / "openrig" / "continuity-state.json").write_text(
        json.dumps({"workflowInstanceId": "wf-fixture"}), encoding="utf-8")
    assert orr._workflow_identity(tmp_path, []) == ("wf-fixture", None)


# --------------------------------------------------- F7: ManifestWriteError mapping
def _injected_manifest_write_error(*_args, **_kwargs):
    raise orr.om.ManifestWriteError("injected manifest write lock failure")


def test_write_entry_records_maps_manifest_write_error_to_entry_record_error(
    tmp_path, monkeypatch
):
    """A lock/rename refusal must become EntryRecordError, never a traceback."""
    run = _make_run(tmp_path)
    bridge, error = orr._load_bridge(run)
    assert error is None
    monkeypatch.setattr(orr.om, "write_atomic", _injected_manifest_write_error)

    with pytest.raises(orr.EntryRecordError) as excinfo:
        orr.write_entry_records(run, bridge, dry_run=True)

    assert "cannot write entry provenance" in str(excinfo.value)
    assert "injected manifest write lock failure" in str(excinfo.value)
    assert not (Path(bridge["openrigHome"]) / "entry" / "launch.json").exists()


def test_rewrite_launch_maps_manifest_write_error_to_false(tmp_path, monkeypatch):
    """The phase flip keeps its old degraded semantics: False, not an exception."""
    run = _make_run(tmp_path)
    bridge, error = orr._load_bridge(run)
    assert error is None
    home = orr._entry_home(bridge)
    launch_id = orr.write_entry_records(run, bridge, dry_run=True)
    launch_path = home / "entry" / "launch.json"
    before = launch_path.read_bytes()

    monkeypatch.setattr(orr.om, "write_atomic", _injected_manifest_write_error)

    assert orr._rewrite_launch(home, launch_id, phase="closed") is False
    assert launch_path.read_bytes() == before, "a refused rewrite must not change the record"


def test_start_failure_partial_evidence_write_error_does_not_mask_original_failure(
    tmp_path, monkeypatch
):
    """Evidence-write failure on the failure path must not replace the start error."""
    run = _make_run(tmp_path)
    _env(monkeypatch, tmp_path, FAKE_RIG_UP_FAIL="1")
    real_write_atomic = orr.om.write_atomic

    def fail_only_partial_evidence(path, payload, **kwargs):
        if str(path).endswith("-start-partial.json"):
            raise orr.om.ManifestWriteError("injected partial evidence write failure")
        return real_write_atomic(path, payload, **kwargs)

    monkeypatch.setattr(orr.om, "write_atomic", fail_only_partial_evidence)

    report = orr.run_start(run, dry_run=False, timeout=5)

    assert report["ok"] is False and report["rc"] == 1
    assert report["failedStep"] == "up"
    assert report["error"]["code"] == "up_failed"
    assert "up failed: seat launch error" in report["detail"]
    assert report["partialEvidence"] is None
    assert "injected partial evidence write failure" in report["partialError"]
    assert report["partialManifest"] is not None, "the manifest partial write still succeeded"


def test_start_port_refusal_partial_manifest_write_error_preserves_original_error(
    tmp_path, monkeypatch
):
    """A refused partial-manifest write must not replace the port-refusal report."""
    run = _make_run(tmp_path)
    _env(monkeypatch, tmp_path)
    monkeypatch.setattr(
        orr.og,
        "check_port",
        lambda *_args, **_kwargs: {
            "ok": False,
            "code": "port_conflict",
            "reason": "fixture port 12345 is already in use",
        },
    )

    def failing_write_partial(*_args, **_kwargs):
        raise orr.om.ManifestWriteError("injected partial manifest write failure")

    monkeypatch.setattr(orr.om, "write_partial", failing_write_partial)

    report = orr.run_start(run, dry_run=False, timeout=5)

    assert report["ok"] is False and report["rc"] == 2
    assert report["error"]["code"] == "port_conflict"
    assert "fixture port 12345 is already in use" in report["error"]["message"]
    assert report["port"]["code"] == "port_conflict"
    assert report["partialManifest"] is None
    assert "injected partial manifest write failure" in report["partialManifestError"]


def test_start_failure_partial_manifest_write_error_preserves_original_failure(
    tmp_path, monkeypatch
):
    """A refused run-manifest.partial write must keep the real failed-step report."""
    run = _make_run(tmp_path)
    _env(monkeypatch, tmp_path, FAKE_RIG_UP_FAIL="1")

    def failing_write_partial(*_args, **_kwargs):
        raise orr.om.ManifestWriteError("injected partial manifest write failure")

    monkeypatch.setattr(orr.om, "write_partial", failing_write_partial)

    report = orr.run_start(run, dry_run=False, timeout=5)

    assert report["ok"] is False and report["rc"] == 1
    assert report["failedStep"] == "up"
    assert report["error"]["code"] == "up_failed"
    assert "up failed: seat launch error" in report["detail"]
    assert report["partialEvidence"] is not None, "the evidence file still writes"
    assert report["partialError"] is None
    assert report["partialManifest"] is None
    assert "injected partial manifest write failure" in report["partialManifestError"]


def _write_managed_run_marker(tmp_path: Path, text: str) -> None:
    entry = tmp_path / "home" / "entry"
    entry.mkdir(parents=True, exist_ok=True)
    (entry / "managed-run.json").write_text(text, encoding="utf-8")


def test_corrupt_managed_run_marker_is_rc2_and_starts_no_rig(tmp_path, monkeypatch):
    """Corrupt marker JSON is a provenance failure, not an escaping JSONDecodeError."""
    run = _make_run(tmp_path)
    log = _env(monkeypatch, tmp_path)
    _write_managed_run_marker(tmp_path, "{not-json")

    report = orr.run_start(run, dry_run=False, timeout=5)

    assert report["ok"] is False and report["rc"] == 2
    assert "managed-run marker is not valid JSON" in report["error"]
    assert report["executed"] == []
    assert not log.exists(), "a corrupt marker must start zero rig children"


def test_non_object_managed_run_marker_is_rc2_and_starts_no_rig(tmp_path, monkeypatch):
    """The existing non-object marker contract stays fail-closed and child-free."""
    run = _make_run(tmp_path)
    log = _env(monkeypatch, tmp_path)
    _write_managed_run_marker(tmp_path, "[]")

    report = orr.run_start(run, dry_run=False, timeout=5)

    assert report["ok"] is False and report["rc"] == 2
    assert "managed-run marker is not an object" in report["error"]
    assert report["executed"] == []
    assert not log.exists(), "a non-object marker must start zero rig children"
