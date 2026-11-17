# -*- coding: utf-8 -*-
"""S9 Wave B · N-MAN-TST — RUN-MANIFEST / partial evidence / atomic write / revision.

Selectors the frozen rows use: `-k atomic_write`, `-k revision`, `-k secrets`,
`-k timestamps`.

This module also OWNS the FI-11..FI-17 fixture bundles the CLI rows name, because a
fixture provisioner belongs with the tests that assert on it and `tests/fixtures/s9/` is
another node's path. Provision once per verification:

    OPENRIG_S9_FIXTURES=$(mktemp -d) python tests/test_openrig_manifest.py --provision

DO NOT COPY A PROVISIONED BUNDLE — RE-PROVISION IT (QA W-CT-01 repro gotcha).
A bridge carries three ABSOLUTE paths into its own bundle — `openrigCli`, `openrigHome`,
`projectRoot`. `cp -r FI-16 elsewhere` therefore still executes the SOURCE fake rig, which
writes the SOURCE state, so a copied case can fail (or pass) on another case's data. It
hit CT-04 falsely mismatching. Re-provision per case; copying is broken in three
independent ways, not just one.
"""
import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

WG = Path(__file__).resolve().parents[1]
for extra in (WG / "scripts",):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import openrig_manifest as om  # noqa: E402
import openrig_gate as og  # noqa: E402
import openrig_run as orr  # noqa: E402

FIXTURE_ROOT_ENV = "OPENRIG_S9_FIXTURES"
FIXTURE_NAMES = ("FI-11", "FI-12", "FI-13", "FI-14", "FI-15", "FI-16", "FI-17")

FAKE_RIG = r'''#!/usr/bin/env python3
"""S9 manifest/gate fixture rig. Behaviour is driven by openrig/fixture.json."""
import json, os, sys
from pathlib import Path

run_dir = Path(__file__).resolve().parent
cfg_path = run_dir / "openrig" / "fixture.json"
cfg = json.loads(cfg_path.read_text()) if cfg_path.is_file() else {}
state_path = run_dir / "openrig" / "continuity-state.json"
log = run_dir / "fake-rig.log"

def record(argv):
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"argv": argv}) + "\n")

def state():
    return json.loads(state_path.read_text()) if state_path.is_file() else {"seats": []}

argv = sys.argv[1:]
record(argv)

if cfg.get("fail_step") and argv[:1] == [cfg["fail_step"]]:
    print(cfg.get("fail_message", "fixture failure"), file=sys.stderr)
    sys.exit(1)

if argv[:2] == ["daemon", "start"]:
    s = state(); s["daemonState"] = "running"; state_path.write_text(json.dumps(s))
    print(json.dumps({"ok": True, "pid": 424242})); sys.exit(0)

if argv[:2] == ["daemon", "stop"]:
    print(json.dumps({"ok": True})); sys.exit(0)

if argv[:1] == ["ps"]:
    rows = [{"canonicalSessionName": s.get("canonicalSessionName"),
             "logicalId": s.get("logicalId"),
             "startupStatus": "ready"} for s in state().get("seats", [])]
    print(json.dumps({"nodes": rows})); sys.exit(0)

if argv[:1] == ["up"]:
    print(json.dumps({"ok": True})); sys.exit(0)

if argv[:1] == ["workflow"]:
    print(json.dumps({"ok": True, "instanceId": "wf-fixture"})); sys.exit(0)

if argv[:1] == ["down"]:
    if not cfg.get("down_leaves_seats"):
        s = state()
        for seat in s.get("seats", []):
            seat["session"] = "absent"
            seat["activity"] = None
        state_path.write_text(json.dumps(s))
    print(json.dumps({"ok": True})); sys.exit(0)

print(json.dumps({"ok": True, "argv": argv})); sys.exit(0)
'''

DOCTOR = '''#!/usr/bin/env python3
import sys
if sys.argv[1:2] != ["doctor"]:
    sys.exit(2)
print("PASS fixture doctor (s9 manifest)")
sys.exit(0)
'''


# ------------------------------------------------------------------ fixture builder
def _seat(logical_id, *, token=True, session="absent", activity=None, runtime="opencode",
          compaction=None, actual="ready"):
    row = {
        "logicalId": logical_id,
        "canonicalSessionName": f"{logical_id}@fixture",
        "nodeId": f"node-{logical_id}",
        "restorePolicy": "resume_if_possible",
        "resumeTokenPresent": token,
        "session": session,
        "activity": activity,
        "evidence": "observed",
        "evidenceReasons": [],
        "startupStatus": "ready",
        "actualOutcome": actual,
        "runtime": runtime,
    }
    if compaction is not None:
        row["compaction"] = {"requested": True, "runtime": runtime}
    return row


def build_run(root: Path, name: str, *, fixture=None, state=None, archive=None) -> Path:
    """One run bundle: bridge + render manifest + fake rig + optional state/archive."""
    run = Path(root) / name
    openrig = run / "openrig"
    (openrig / "tools").mkdir(parents=True, exist_ok=True)
    home = run / "home"
    home.mkdir(exist_ok=True)

    rig = run / "fake-rig"
    rig.write_text(FAKE_RIG, encoding="utf-8")
    rig.chmod(0o755)
    (openrig / "fixture.json").write_text(json.dumps(fixture or {}), encoding="utf-8")

    (openrig / "rig.yaml").write_text(f"rig: s9-{name.lower()}\n", encoding="utf-8")
    (openrig / "workflow.yaml").write_text(f"workflow: s9-{name.lower()}\n", encoding="utf-8")
    files = {
        rel: {"bytes": len((openrig / rel).read_bytes()),
              "sha256": om.sha256_file(openrig / rel)}
        for rel in ("rig.yaml", "workflow.yaml")
    }
    (openrig / "render-manifest.json").write_text(
        json.dumps({"schemaVersion": 1, "runId": name, "files": files}), encoding="utf-8"
    )
    (openrig / "tools" / "openrig_bridge.py").write_text(DOCTOR, encoding="utf-8")

    payload = state if state is not None else {
        "daemonState": "stopped",
        "rigState": "stopped",
        "workflowInstanceId": "wf-fixture",
        "seats": [_seat("at-main", token=True)],
    }
    (openrig / "continuity-state.json").write_text(json.dumps(payload), encoding="utf-8")

    bridge = {
        "schemaVersion": 2,
        "runId": name,
        "rigName": f"s9-{name.lower()}",
        "workflowId": f"s9-{name.lower()}",
        "rigSpec": "rig.yaml",
        "workflowSpec": "workflow.yaml",
        "openrigCli": str(rig),
        "openrigHome": str(home),
        "projectRoot": str(run / "project-root"),
        "daemonPort": 47999,
        "seatMap": {s["logicalId"]: s["canonicalSessionName"] for s in payload["seats"]},
        "bundleDir": "openrig",
        "_fixture": "S9 manifest/gate fixture; not a real run",
    }
    (openrig / "OPENRIG-BRIDGE.json").write_text(json.dumps(bridge, indent=2), encoding="utf-8")

    if archive is not None:
        manifest = run / "reports" / "evidence" / "archive" / "ARCHIVE-MANIFEST.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps({"schemaVersion": 1, "runId": name, "status": archive}), encoding="utf-8"
        )
    return run


def provision(root: Path) -> dict:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    import shutil

    for name in FIXTURE_NAMES:
        shutil.rmtree(root / name, ignore_errors=True)

    created = {}
    # FI-11 — a start that succeeds, and therefore a manifest to read (IO-01) and a
    # second start to refuse (IO-05).
    created["FI-11"] = str(build_run(root, "FI-11"))
    # FI-12 — the `up` step fails: partial manifest + up_failed (IO-02).
    created["FI-12"] = str(build_run(root, "FI-12", fixture={"fail_step": "up",
                                                             "fail_message": "fixture up refused"}))
    # FI-13 — down leaves a seat alive: orphan reported, never killed (GATE-01).
    created["FI-13"] = str(
        build_run(
            root, "FI-13",
            fixture={"down_leaves_seats": True},
            state={"daemonState": "running", "rigState": "present",
                   "workflowInstanceId": "wf-fixture",
                   "seats": [_seat("at-main", session="present", activity="working")]},
            archive="COMPLETE",
        )
    )
    # FI-14 — the port is held by something that is not this run (GATE-02).
    created["FI-14"] = str(
        build_run(root, "FI-14", state={"daemonState": "stopped", "rigState": "stopped",
                                        "ports": {"47999": "foreign"},
                                        "seats": [_seat("at-main")]})
    )
    # FI-15 — an opencode seat claiming a MANAGED compaction (GATE-03).
    created["FI-15"] = str(
        build_run(root, "FI-15", state={"daemonState": "stopped", "rigState": "stopped",
                                        "seats": [_seat("at-main", runtime="opencode",
                                                        compaction=True)]})
    )
    # FI-16 — a complete handover record (GATE-04, rc0).
    created["FI-16"] = str(
        build_run(root, "FI-16", state={
            "daemonState": "stopped", "rigState": "stopped",
            "seats": [_seat("at-main")],
            "handover": {"source": "seat-1", "reason": "occupant compacted",
                         "previous": "main@old", "successor": "main@new",
                         "actualHandoverResult": "successor verified ready"},
        })
    )
    # FI-17 — retire requested with an incomplete archive (GATE-05).
    created["FI-17"] = str(
        build_run(root, "FI-17", state={"daemonState": "stopped", "rigState": "stopped",
                                        "seats": [_seat("at-main")],
                                        "retire": {"requested": True, "logicalId": "at-main"}},
                  archive="INCOMPLETE")
    )
    return created


# ------------------------------------------------------------------ IO-03 atomic write
def test_atomic_write_leaves_no_half_file(tmp_path):
    target = tmp_path / "reports" / "evidence" / "manifest" / "run-manifest.json"
    om.write_atomic(target, {"revision": 1, "status": "active"})
    assert json.loads(target.read_text())["revision"] == 1

    def exploding_replace(src, dst):
        raise OSError("rename refused (injected)")

    with pytest.raises(OSError):
        om.write_atomic(target, {"revision": 2, "status": "active"}, _replace=exploding_replace)

    # No half file, and the previous bytes survived untouched.
    assert not list(target.parent.glob("*.tmp"))
    assert json.loads(target.read_text())["revision"] == 1


def test_atomic_write_is_byte_stable_for_identical_payloads(tmp_path):
    target = tmp_path / "manifest.json"
    first = om.write_atomic(target, {"a": 1})
    second = om.write_atomic(target, {"a": 1})
    assert first == second


# ------------------------------------------------------------------ IO-04 revision
def test_revision_increases_and_old_bytes_are_preserved(tmp_path):
    run = build_run(tmp_path, "R1")
    manifest = om.new_manifest(run, json.loads((run / "openrig" / "OPENRIG-BRIDGE.json").read_text()),
                              launch_id="launch-a")
    manifest["status"] = "starting"
    first = om.write_manifest(run, manifest)
    assert first["revision"] == 1
    first_bytes = (run / om.MANIFEST_REL).read_bytes()

    manifest2 = om.new_manifest(run, json.loads((run / "openrig" / "OPENRIG-BRIDGE.json").read_text()),
                               launch_id="launch-b")
    assert manifest2["revision"] == 2, "revision must increment, never reuse"
    assert manifest2["manifestId"] == manifest["manifestId"], "manifestId survives a retry"
    manifest2["status"] = "active"
    second = om.write_manifest(run, manifest2)
    assert second["revision"] == 2

    preserved = run / om.REVISIONS_DIR / "1.json"
    assert preserved.is_file(), "the replaced bytes must be kept"
    assert preserved.read_bytes() == first_bytes


def test_partial_manifest_is_loadable_and_names_the_gap(tmp_path):
    run = build_run(tmp_path, "R2")
    bridge = json.loads((run / "openrig" / "OPENRIG-BRIDGE.json").read_text())
    manifest = om.new_manifest(run, bridge, launch_id="launch-c")
    partial = om.write_partial(
        run, manifest, reason="up: fixture refused", rc=1,
        executed=[], unexecuted=["workflow-validate", "workflow-instantiate"],
    )
    loaded = json.loads(Path(partial["path"]).read_text())
    assert loaded["partial"] is True
    assert loaded["status"] == "failed"
    assert loaded["failure"]["rc"] == 1
    assert loaded["failure"]["unexecutedSteps"] == ["workflow-validate", "workflow-instantiate"]
    assert isinstance(loaded["failure"]["stdoutSha256"], str)


# ------------------------------------------------------------------ IO-06 secrets
def test_secrets_never_enter_the_manifest(tmp_path):
    run = build_run(tmp_path, "R3")
    bridge = json.loads((run / "openrig" / "OPENRIG-BRIDGE.json").read_text())
    env = {"OPENRIG_HOME": str(run / "home"), "OPENRIG_AUTH_BEARER_TOKEN": "sup3r-s3cret",
           "MY_API_KEY": "also-secret"}
    manifest = om.new_manifest(run, bridge, launch_id="launch-d", env=env)

    # Names only: no value, ever.
    assert manifest["envKeys"] == ["MY_API_KEY", "OPENRIG_AUTH_BEARER_TOKEN", "OPENRIG_HOME"]
    assert "sup3r-s3cret" not in json.dumps(manifest)
    assert "also-secret" not in json.dumps(manifest)

    receipt = om.step_receipt(
        "daemon-start",
        ["rig", "daemon", "start", "--token", "sup3r-s3cret", "--env", "API_KEY=abc"],
        cwd=str(run), rc=0, started_at=om.now_iso(), ended_at=om.now_iso(),
    )
    assert receipt["redacted"] is True
    assert "sup3r-s3cret" not in json.dumps(receipt)
    assert "API_KEY=abc" not in json.dumps(receipt)
    assert "<redacted>" in json.dumps(receipt)


# ------------------------------------------------------------------ IO-07 timestamps
def test_every_receipt_carries_both_timestamps(tmp_path):
    import re

    started = "2026-11-16T08:00:00Z"
    ended = "2026-11-16T08:00:07Z"
    receipt = om.step_receipt(
        "up", ["rig", "up", "x.yaml"], cwd=str(tmp_path), rc=0,
        started_at=started, ended_at=ended,
    )
    iso = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    assert receipt["startedAt"] == started
    assert receipt["endedAt"] == ended
    assert iso.match(receipt["startedAt"]) and iso.match(receipt["endedAt"])
    # A duration alone is not enough (§6.3): there is no "durationMs"-only shape here.
    assert "duration" not in json.dumps(receipt).lower()


# ------------------------------------------------------------------ manifest contract
def test_manifest_has_every_required_top_level_key(tmp_path):
    run = build_run(tmp_path, "R4")
    bridge = json.loads((run / "openrig" / "OPENRIG-BRIDGE.json").read_text())
    manifest = om.new_manifest(run, bridge, launch_id="launch-e")
    assert set(om.REQUIRED_TOP_KEYS) <= set(manifest)
    assert manifest["runContext"]["bridgeSha256"] == om.sha256_file(
        run / "openrig" / "OPENRIG-BRIDGE.json"
    )
    assert manifest["status"] in om.STATUSES


def test_inputs_are_referenced_by_hash_not_copied(tmp_path):
    run = build_run(tmp_path, "R5")
    bridge = json.loads((run / "openrig" / "OPENRIG-BRIDGE.json").read_text())
    manifest = om.new_manifest(run, bridge, launch_id="launch-f")
    om.add_input(manifest, run, Path("openrig") / "rig.yaml", kind="rig-spec")
    entry = manifest["inputs"][0]
    assert entry["sha256"] and entry["bytes"]
    assert "content" not in entry and "body" not in entry


# ------------------------------------------------------------------ P-S10-02 evidence arrays
def test_add_seats_carries_observation_and_clears_stale_na_reason(tmp_path):
    manifest = {
        "seats": [],
        "outputs": [],
        om.SEATS_NOT_APPLICABLE_REASON: "stale",
    }
    om.add_seats(
        manifest,
        [
            {
                "logicalId": "at-main",
                "canonicalSessionName": "main@t",
                "nodeId": "node-1",
                "expectedAction": "new",
                "actualOutcome": None,
                "session": "present",
                "activity": "unknown",
                "evidence": "observed",
                "evidenceReasons": [],
                "startupStatus": "ready",
                "observed": True,
                "observationSource": "ps",
            }
        ],
    )
    assert manifest["seats"][0]["startupStatus"] == "ready"
    assert manifest["seats"][0]["observed"] is True
    # finalize is the helper that owns stale-reason cleanup
    om.finalize_manifest(manifest, status="active")
    assert om.SEATS_NOT_APPLICABLE_REASON not in manifest
    # The empty outputs array still gets its own machine-readable reason.
    assert manifest[om.OUTPUTS_NOT_APPLICABLE_REASON] == (
        om.DEFAULT_OUTPUTS_NOT_APPLICABLE_REASON
    )


def test_add_output_records_real_file_and_refuses_missing(tmp_path):
    manifest = {"seats": [], "outputs": []}
    target = tmp_path / "reports" / "evidence" / "start-receipt.json"
    target.parent.mkdir(parents=True)
    target.write_bytes(b'{"kind":"start-receipt"}\n')

    om.add_output(
        manifest,
        target,
        producer="openrig-run start",
        consumer="archive/operator",
    )
    entry = manifest["outputs"][0]
    assert entry["path"] == str(target.resolve())
    assert entry["sha256"] == om.sha256_file(target)
    assert entry["bytes"] == len(target.read_bytes())

    with pytest.raises(FileNotFoundError):
        om.add_output(
            manifest,
            tmp_path / "missing.json",
            producer="test",
            consumer="test",
        )


def test_finalize_manifest_makes_empty_arrays_explicit_and_clears_on_evidence(tmp_path):
    manifest = {"seats": [], "outputs": []}
    om.finalize_manifest(
        manifest,
        status="failed",
        seats=[],
        outputs=[],
        seats_not_applicable_reason="start_failed_before_seat_observation",
        outputs_not_applicable_reason="start_failed_before_success_output",
    )
    assert manifest["status"] == "failed"
    assert manifest[om.SEATS_NOT_APPLICABLE_REASON] == "start_failed_before_seat_observation"
    assert manifest[om.OUTPUTS_NOT_APPLICABLE_REASON] == "start_failed_before_success_output"

    receipt = tmp_path / "receipt.json"
    receipt.write_text("{}\n", encoding="utf-8")
    om.finalize_manifest(
        manifest,
        status="active",
        seats=[{"logicalId": "at-main", "session": "present"}],
        outputs=[
            {"path": str(receipt), "producer": "test", "consumer": "test"}
        ],
    )
    assert manifest["seats"] and manifest["outputs"]
    assert om.SEATS_NOT_APPLICABLE_REASON not in manifest
    assert om.OUTPUTS_NOT_APPLICABLE_REASON not in manifest


def test_write_receipt_is_atomic_bounded_and_reports_actual_bytes(tmp_path):
    receipt = om.write_receipt(
        tmp_path,
        "reports/evidence/resume-receipt.json",
        {"kind": "resume-receipt", "n": 1},
    )
    path = Path(receipt["path"])
    assert path.is_file()
    assert receipt["sha256"] == om.sha256_file(path)
    assert receipt["bytes"] == path.stat().st_size
    assert json.loads(path.read_text(encoding="utf-8"))["kind"] == "resume-receipt"
    assert not list(path.parent.glob("*.tmp"))

    with pytest.raises(ValueError):
        om.write_receipt(tmp_path, "too-big.json", {"padding": "x" * 100}, max_bytes=10)


def test_seats_from_ps_uses_bridge_seatmap_and_marks_absent_observed_false():
    bridge = {"seatMap": {"main": "main@t", "tdo": "tdo@t"}}
    seats = om.seats_from_ps(
        bridge,
        {
            "nodes": [
                {
                    "canonicalSessionName": "main@t",
                    "nodeId": "node-1",
                    "startupStatus": "ready",
                    "sessionStatus": "running",
                }
            ]
        },
    )
    by_id = {row["logicalId"]: row for row in seats}
    assert by_id["main"]["observed"] is True
    assert by_id["main"]["session"] == "present"
    assert by_id["main"]["startupStatus"] == "ready"
    assert by_id["tdo"]["observed"] is False
    assert "session" not in by_id["tdo"], "the schema enum has no null session"
    assert by_id["tdo"]["actualOutcome"] == "n-a"
    assert by_id["tdo"]["actualOutcomeObserved"] is False
    assert by_id["tdo"]["actualOutcomeReason"] == "outcome_not_observed"
    assert by_id["tdo"]["evidenceReasons"] == ["no_observation_path"]


def test_seats_from_ps_omits_unknown_session_and_never_writes_null_outcome():
    bridge = {"seatMap": {"main": "main@t"}}
    seats = om.seats_from_ps(
        bridge,
        [{"canonicalSessionName": "main@t", "startupStatus": "ready"}],
    )
    row = seats[0]
    assert "session" not in row, "unknown session must be omitted, not serialized as null"
    assert row["actualOutcome"] == "n-a"
    assert row["actualOutcomeObserved"] is False
    assert row["actualOutcomeReason"] == "outcome_not_observed"


def test_add_seats_normalizes_unobserved_outcome_to_na_and_marks_provenance():
    manifest = {"seats": [], "outputs": []}
    om.add_seats(
        manifest,
        [
            {"logicalId": "missing", "canonicalSessionName": "missing@t",
             "expectedAction": "new"},
            {"logicalId": "null", "canonicalSessionName": "null@t",
             "expectedAction": "new", "actualOutcome": None},
            {"logicalId": "unknown", "canonicalSessionName": "unknown@t",
             "expectedAction": "new", "actualOutcome": "not-an-enum"},
            {"logicalId": "real", "canonicalSessionName": "real@t",
             "expectedAction": "new", "actualOutcome": "resumed"},
            {"logicalId": "explicit", "canonicalSessionName": "explicit@t",
             "expectedAction": "new", "actualOutcome": "n-a",
             "actualOutcomeObserved": False},
            {"logicalId": "no-session", "canonicalSessionName": "ns@t",
             "expectedAction": "new", "session": None, "activity": None},
        ],
    )
    by_id = {row["logicalId"]: row for row in manifest["seats"]}
    for logical_id in ("missing", "null", "unknown", "explicit"):
        row = by_id[logical_id]
        assert row["actualOutcome"] == "n-a"
        assert row["actualOutcomeObserved"] is False
        assert row["actualOutcomeReason"] == "outcome_not_observed"
    assert by_id["real"]["actualOutcome"] == "resumed"
    assert by_id["real"]["actualOutcomeObserved"] is True
    assert "actualOutcomeReason" not in by_id["real"]
    assert "session" not in by_id["no-session"]
    assert "activity" not in by_id["no-session"]


def test_new_manifest_workflow_ids_are_strings_and_revision_inherits_env_keys(tmp_path):
    run = build_run(tmp_path, "R-S11A")
    bridge = json.loads((run / "openrig" / "OPENRIG-BRIDGE.json").read_text())
    bridge.pop("workflowInstanceId", None)
    bridge.pop("entryQitemId", None)
    manifest = om.new_manifest(
        run, bridge, launch_id="launch-s11a", env={"TOKEN_NAME": "must-not-be-written"}
    )
    assert manifest["workflow"]["instanceId"] == ""
    assert manifest["workflow"]["entryQitemId"] == ""
    assert isinstance(manifest["workflow"]["instanceId"], str)
    assert isinstance(manifest["workflow"]["entryQitemId"], str)
    assert manifest["envKeys"] == ["TOKEN_NAME"]

    manifest["status"] = "active"
    om.write_manifest(run, manifest)
    revised = om.revised_manifest(run, bridge, launch_id="launch-s11a-2", intent="resume")

    assert revised["envKeys"] == ["TOKEN_NAME"]
    assert revised["manifestId"] == manifest["manifestId"]
    assert revised["revision"] == manifest["revision"] + 1


def test_direct_write_manifest_normalizes_unobserved_seat_axes(tmp_path):
    run = build_run(tmp_path, "R-DIRECT-SEAT")
    bridge = json.loads((run / "openrig" / "OPENRIG-BRIDGE.json").read_text())
    manifest = om.new_manifest(run, bridge, launch_id="launch-direct-seat")
    manifest["status"] = "active"
    manifest["seats"] = [
        {
            "logicalId": "at-main",
            "canonicalSessionName": "at-main@fixture",
            "expectedAction": "new",
            "actualOutcome": None,
            "session": None,
            "activity": None,
            "evidence": None,
        }
    ]
    om.write_manifest(run, manifest)
    loaded = json.loads((run / om.MANIFEST_REL).read_text())
    seat = loaded["seats"][0]
    assert seat["actualOutcome"] == "n-a"
    assert seat["actualOutcomeObserved"] is False
    assert seat["actualOutcomeReason"] == "outcome_not_observed"
    for key in ("session", "activity", "evidence"):
        assert key not in seat, f"{key} must be omitted, never null"


def test_direct_write_manifest_and_partial_make_empty_arrays_explicit(tmp_path):
    run = build_run(tmp_path, "R-N-A")
    bridge = json.loads((run / "openrig" / "OPENRIG-BRIDGE.json").read_text())
    manifest = om.new_manifest(run, bridge, launch_id="launch-write")
    manifest["status"] = "active"
    om.write_manifest(run, manifest)
    loaded = json.loads((run / om.MANIFEST_REL).read_text())
    assert loaded["status"] == "active"
    assert loaded["seats"] == [] and loaded["outputs"] == []
    assert loaded["seatsNotApplicableReason"] == om.DEFAULT_SEATS_NOT_APPLICABLE_REASON
    assert loaded["outputsNotApplicableReason"] == om.DEFAULT_OUTPUTS_NOT_APPLICABLE_REASON

    partial_manifest = om.new_manifest(run, bridge, launch_id="launch-partial")
    partial = om.write_partial(
        run, partial_manifest, reason="direct partial", rc=1,
        executed=[], unexecuted=["up"],
    )
    loaded_partial = json.loads(Path(partial["path"]).read_text())
    assert loaded_partial["status"] == "failed"
    assert loaded_partial["partial"] is True
    assert loaded_partial["seatsNotApplicableReason"] == om.DEFAULT_SEATS_NOT_APPLICABLE_REASON
    assert loaded_partial["outputsNotApplicableReason"] == om.DEFAULT_OUTPUTS_NOT_APPLICABLE_REASON


# ------------------------------------------------------------------ S2-5 writer safety
def test_atomic_write_uses_unique_temp_and_ignores_fixed_tmp_collision(tmp_path):
    target = tmp_path / "run-manifest.json"
    fixed_tmp = target.with_name("run-manifest.json.tmp")
    fixed_tmp.mkdir()

    digest = om.write_atomic(target, {"writer": "unique-temp"})

    assert digest == om.sha256_file(target)
    assert json.loads(target.read_text(encoding="utf-8"))["writer"] == "unique-temp"
    assert fixed_tmp.is_dir(), "a pre-existing fixed .tmp path must not be touched"
    assert not any(
        path.is_file() and path.name.endswith(".tmp") for path in tmp_path.iterdir()
    )


def test_path_lock_has_a_windows_msvcrt_branch(tmp_path, monkeypatch):
    class FakeMsvcrt:
        LK_NBLCK = 1
        LK_UNLCK = 2

        def __init__(self):
            self.calls = []

        def locking(self, fd, mode, nbytes):
            self.calls.append((fd, mode, nbytes))

    fake = FakeMsvcrt()
    monkeypatch.setattr(om, "_fcntl", None)
    monkeypatch.setattr(om, "_msvcrt", fake)

    with om._path_lock(tmp_path / "portable-target") as lock_path:
        assert lock_path.is_file()

    assert [mode for _fd, mode, _nbytes in fake.calls] == [
        FakeMsvcrt.LK_NBLCK,
        FakeMsvcrt.LK_UNLCK,
    ]
    assert all(nbytes == 1 for _fd, _mode, nbytes in fake.calls)


def test_path_lock_without_any_backend_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(om, "_fcntl", None)
    monkeypatch.setattr(om, "_msvcrt", None)

    with pytest.raises(om.ManifestWriteError, match="locking backend"):
        with om._path_lock(tmp_path / "unlocked-target"):
            pytest.fail("the context body must not run without a lock backend")


def test_concurrent_manifest_writers_serialize_and_one_stale_revision_fails(tmp_path):
    run = build_run(tmp_path, "R-CONCURRENT")
    bridge = json.loads((run / "openrig" / "OPENRIG-BRIDGE.json").read_text())
    initial = om.new_manifest(run, bridge, launch_id="launch-concurrent-0")
    initial["status"] = "active"
    om.write_manifest(run, initial)
    initial_bytes = (run / om.MANIFEST_REL).read_bytes()

    manifest_a = om.new_manifest(run, bridge, launch_id="launch-concurrent-a")
    manifest_b = om.new_manifest(run, bridge, launch_id="launch-concurrent-b")
    assert manifest_a["revision"] == manifest_b["revision"] == 2
    manifest_a["status"] = manifest_b["status"] = "active"
    manifest_a["inputs"] = [{"writer": "A"}]
    manifest_b["inputs"] = [{"writer": "B"}]

    barrier = threading.Barrier(2)
    results: dict[str, dict] = {}

    def writer(name: str, manifest: dict) -> None:
        barrier.wait(timeout=5)
        try:
            results[name] = {"ok": True, **om.write_manifest(run, manifest)}
        except Exception as exc:  # noqa: BLE001 - assertion inspects exact failure type
            results[name] = {"ok": False, "error": exc}

    threads = [
        threading.Thread(target=writer, args=("A", manifest_a)),
        threading.Thread(target=writer, args=("B", manifest_b)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert all(not thread.is_alive() for thread in threads)
    successes = {name: row for name, row in results.items() if row["ok"]}
    failures = {name: row for name, row in results.items() if not row["ok"]}
    assert len(successes) == 1, results
    assert len(failures) == 1, results
    winner_name, winner = next(iter(successes.items()))
    loser = next(iter(failures.values()))
    assert isinstance(loser["error"], om.ManifestRevisionError)

    target = run / om.MANIFEST_REL
    assert winner["sha256"] == om.sha256_file(target)
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded["revision"] == 2
    assert loaded["inputs"] == [{"writer": winner_name}]
    assert (run / om.REVISIONS_DIR / "1.json").read_bytes() == initial_bytes
    assert not any(
        path.is_file() and path.name.endswith(".tmp")
        for path in run.rglob("*")
    )


def test_write_manifest_surfaces_preservation_failure_and_keeps_live_bytes(
    tmp_path, monkeypatch
):
    run = build_run(tmp_path, "R-PRESERVE-FAIL")
    bridge = json.loads((run / "openrig" / "OPENRIG-BRIDGE.json").read_text())
    first = om.new_manifest(run, bridge, launch_id="launch-preserve-1")
    first["status"] = "active"
    om.write_manifest(run, first)
    target = run / om.MANIFEST_REL
    before = target.read_bytes()

    second = om.new_manifest(run, bridge, launch_id="launch-preserve-2")
    second["status"] = "active"
    real_write = om._write_bytes_unlocked

    def fail_revision_write(path, data, **kwargs):
        if Path(path).parent.name == om.REVISIONS_DIR.name:
            raise OSError("injected revision preservation failure")
        return real_write(path, data, **kwargs)

    monkeypatch.setattr(om, "_write_bytes_unlocked", fail_revision_write)
    with pytest.raises(om.ManifestPreservationError):
        om.write_manifest(run, second)
    assert target.read_bytes() == before, "the live manifest must not be replaced"


def test_write_manifest_preserves_exact_prior_bytes_not_reserialization(tmp_path):
    run = build_run(tmp_path, "R-RAW-PRESERVE")
    target = run / om.MANIFEST_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    prior_bytes = b'{"schemaVersion":1, "revision":1,"status":"active","manifestId":"raw"}\n'
    target.write_bytes(prior_bytes)
    bridge = json.loads((run / "openrig" / "OPENRIG-BRIDGE.json").read_text())

    revised = om.new_manifest(run, bridge, launch_id="launch-raw-preserve")
    revised["status"] = "active"
    om.write_manifest(run, revised)

    preserved = run / om.REVISIONS_DIR / "1.json"
    assert preserved.read_bytes() == prior_bytes


# ------------------------------------------------------------------ S2-6 live ps mapping
def test_seats_from_ps_maps_session_status_and_nested_activity_explicitly():
    bridge = {"seatMap": {"main": "main@t"}}
    base = {
        "logicalId": "main",
        "canonicalSessionName": "main@t",
        "runtime": "dsh",
        "pid": 4242,
        "startupStatus": "ready",
        "resumeTokenPresent": True,
    }

    exited = om.seats_from_ps(
        bridge, [{**base, "sessionStatus": "exited", "lifecycleState": "stopped"}]
    )[0]
    assert exited["session"] == "exited"
    assert "activity" not in exited

    detached = om.seats_from_ps(
        bridge, [{**base, "sessionStatus": "detached", "lifecycleState": "recoverable"}]
    )[0]
    assert detached["session"] == "detached"
    assert "activity" not in detached

    working = om.seats_from_ps(
        bridge,
        [
            {
                **base,
                "sessionStatus": "running",
                "agentActivity": {"state": "running", "reason": "tool_use"},
            }
        ],
    )[0]
    assert working["session"] == "present"
    assert working["activity"] == "working"

    idle = om.seats_from_ps(
        bridge,
        [
            {
                **base,
                "sessionStatus": "running",
                "agentActivity": {"state": "idle"},
            }
        ],
    )[0]
    assert idle["activity"] == "idle-at-prompt"

    needs_input = om.seats_from_ps(
        bridge,
        [
            {
                **base,
                "sessionStatus": "running",
                "agentActivity": {"state": "needs_input"},
            }
        ],
    )[0]
    assert needs_input["activity"] == "idle-at-prompt"


def test_seats_from_ps_null_session_status_does_not_invent_present():
    bridge = {"seatMap": {"main": "main@t"}}
    row = om.seats_from_ps(
        bridge,
        [
            {
                "logicalId": "main",
                "canonicalSessionName": "main@t",
                "runtime": "dsh",
                "pid": 4242,
                "sessionStatus": None,
                "startupStatus": "failed",
                "resumeTokenPresent": True,
            }
        ],
    )[0]
    assert "session" not in row
    assert row["evidence"] == "degraded"
    assert om.PS_SESSION_UNKNOWN_REASON in row["evidenceReasons"]


@pytest.mark.parametrize(
    "payload",
    [None, {}, {"nodes": []}, {"unknown": []}, "not-json-shape", [{"runtime": "dsh"}]],
)
def test_seats_from_ps_rejects_empty_or_unknown_shapes(payload):
    with pytest.raises(om.PsPayloadError):
        om.seats_from_ps({"seatMap": {"main": "main@t"}}, payload)


def test_seats_from_ps_rejects_missing_bridge_seatmap():
    with pytest.raises(om.PsPayloadError):
        om.seats_from_ps(
            {},
            [{"logicalId": "main", "canonicalSessionName": "main@t", "sessionStatus": "running"}],
        )


# ------------------------------------------------------------------ provisioner CLI
def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    root = os.environ.get(FIXTURE_ROOT_ENV, "").strip()
    if not root:
        payload = {
            "ok": False,
            "error": {"code": "fixture_root_unset",
                      "message": f"{FIXTURE_ROOT_ENV} is unset; refusing to share a fixture root (S9-R-01)",
                      "hint": f"{FIXTURE_ROOT_ENV}=$(mktemp -d) python tests/test_openrig_manifest.py --provision"},
            "rc": 2,
        }
        print(json.dumps(payload) if "--json" in argv else f"[FAIL] {payload['error']['message']}")
        return 2
    created = provision(Path(root))
    print(json.dumps({"ok": True, "fixtureRoot": root, "runs": created, "rc": 0})
          if "--json" in argv else "\n".join(f"{k}: {v}" for k, v in created.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# ------------------------------------------- F7: openrig_run shares the safe writer
def test_openrig_run_atomic_writer_ignores_fixed_tmp_collision(tmp_path):
    """The launch-record writer must not depend on a predictable sibling .tmp path."""
    target = tmp_path / "entry" / "launch.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    fixed_tmp = target.with_name("launch.json.tmp")
    fixed_tmp.mkdir()

    orr._atomic_write_json(target, {"launchId": "launch-collision", "phase": "starting"})

    assert fixed_tmp.is_dir(), "the pre-existing fixed .tmp path must not be touched"
    assert json.loads(target.read_text(encoding="utf-8"))["launchId"] == "launch-collision"
    assert (target.stat().st_mode & 0o777) == 0o600
    assert (target.parent / ".launch.json.lock").is_file()
    assert not any(
        path.is_file() and path.name.endswith(".tmp") for path in target.parent.iterdir()
    )


def test_openrig_run_atomic_writer_concurrent_threads_keep_one_complete_json(
    tmp_path, monkeypatch
):
    """8 writers race; every write succeeds and the target is always one full document.

    ``os.replace`` is slowed only to amplify the OLD fixed-``.tmp`` race: this test
    must fail against that implementation.  The new implementation delegates to
    ``om.write_atomic`` whose default ``_replace`` is bound at definition time, so the
    delay is not part of the new write path.
    """
    target = tmp_path / "entry" / "launch.json"
    real_write_atomic = orr.om.write_atomic
    calls = []

    def counting_write_atomic(path, payload, **kwargs):
        calls.append((Path(path), dict(kwargs)))
        return real_write_atomic(path, payload, **kwargs)

    monkeypatch.setattr(orr.om, "write_atomic", counting_write_atomic)
    real_replace = os.replace

    def slow_replace(src, dst):
        time.sleep(0.01)
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", slow_replace)

    writers = 8
    barrier = threading.Barrier(writers)
    errors: list[BaseException] = []

    def writer(index: int) -> None:
        barrier.wait(timeout=10)
        try:
            orr._atomic_write_json(
                target, {"writer": index, "payload": "x" * 2048}
            )
        except BaseException as exc:  # noqa: BLE001 - assertion reports the exact type
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(index,)) for index in range(writers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    assert all(not thread.is_alive() for thread in threads)
    assert errors == []
    assert len(calls) == writers
    assert all(kwargs.get("mode") == 0o600 for _path, kwargs in calls)
    final = json.loads(target.read_text(encoding="utf-8"))
    assert final["writer"] in range(writers)
    assert final["payload"] == "x" * 2048
    assert (target.stat().st_mode & 0o777) == 0o600
    assert not any(
        path.is_file() and path.name.endswith(".tmp") for path in target.parent.iterdir()
    )


def test_openrig_run_atomic_writer_failure_keeps_original_and_cleans_temp(
    tmp_path, monkeypatch
):
    """A rename refusal must leave the previous bytes and no half file behind."""
    target = tmp_path / "entry" / "launch.json"
    orr._atomic_write_json(target, {"revision": 1, "phase": "starting"})
    before = target.read_bytes()
    real_write_atomic = orr.om.write_atomic

    def exploding_replace(_src, _dst):
        raise OSError("rename refused (injected)")

    def failing_write_atomic(path, payload, **kwargs):
        return real_write_atomic(
            path, payload, _replace=exploding_replace, mode=kwargs.get("mode")
        )

    monkeypatch.setattr(orr.om, "write_atomic", failing_write_atomic)

    with pytest.raises(OSError, match="rename refused"):
        orr._atomic_write_json(target, {"revision": 2, "phase": "closed"})

    assert target.read_bytes() == before
    assert not any(
        path.is_file() and path.name.endswith(".tmp") for path in target.parent.iterdir()
    )
