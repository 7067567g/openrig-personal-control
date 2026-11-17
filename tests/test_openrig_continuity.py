# -*- coding: utf-8 -*-
"""S9 Wave B · N-CT-TST — continuity/lifecycle fixtures (CT-01..CT-19).

Every case builds its own run bundle inside pytest `tmp_path` (W-S8-12): no case shares a
namespace with another, and none depends on the matrix provisioning step. The fake rig
lives INSIDE each bundle and records every argv it receives, so "zero mutation" and
"`up <rig> --existing`" are assertions about observed process calls, not about intent.

Selector names required by the frozen AT rows:
  -k up_existing_argv      AT-S9-CT-08
  -k obs_hook_missing      AT-S9-OBS-01
  -k obs_no_path           AT-S9-OBS-02
  -k obs_absent            AT-S9-OBS-03
  -k obs_oracle_unknown    AT-S9-OBS-04
  -k obs_long_call         AT-S9-OBS-05
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

WG = Path(__file__).resolve().parents[1]
for extra in (WG / "scripts", WG / "tests" / "fixtures" / "s9"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import openrig_continuity as oc  # noqa: E402
import openrig_manifest as om  # noqa: E402
import openrig_run as orr  # noqa: E402
import provision_continuity as prov  # noqa: E402


# ------------------------------------------------------------------ helpers
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


def bundle(tmp_path, name, **kwargs):
    run = prov.build_run(tmp_path, name, **kwargs)
    if str(kwargs.get("archive") or "").upper() == "COMPLETE":
        bind_complete_archive(run)
    return run


def rig_calls(run_dir: Path) -> list[dict]:
    log = Path(run_dir) / "fake-rig.log"
    if not log.is_file():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line]


def tree_fingerprint(root: Path) -> dict:
    """Every file under `root` -> (bytes, sha256, mtime_ns). Used for read-only proofs."""
    out = {}
    for path in sorted(Path(root).rglob("*")):
        if path.is_file():
            stat = path.stat()
            out[str(path.relative_to(root))] = (
                stat.st_size,
                hashlib.sha256(path.read_bytes()).hexdigest(),
                stat.st_mtime_ns,
            )
    return out


def stopped(seats, instance="wf-fixture"):
    return {
        "daemonState": "stopped",
        "rigState": "stopped",
        "workflowInstanceId": instance,
        "seats": seats,
    }


def ready(seat, actual):
    return {**seat, "session": "present", "startupStatus": "ready", "actualOutcome": actual}


# ------------------------------------------------------- CT-01: start/resume split
def test_ct01_start_resume_is_refused_with_a_code(tmp_path, capsys):
    run = bundle(tmp_path, "FI-04", state=stopped([prov.seat("at-main", token=True)]))

    rc = orr.main(["start", "--run-dir", str(run), "--resume", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert payload["error"]["code"] == "invalid_arguments"
    assert "resume" in payload["error"]["hint"]
    # Nothing was read or written: the refusal happens before any path work.
    assert rig_calls(run) == []
    assert not (run / "reports" / "evidence" / "manifest" / "continuity-plan.json").exists()


# ------------------------------------------- CT-03: start refuses when a rig exists
def test_ct03b_start_refuses_when_a_rig_is_present(tmp_path, capsys):
    """§4.1: start creates, it never repairs. An existing rig is a `resume`, by name."""
    run = bundle(
        tmp_path,
        "FI-04",
        state={
            "daemonState": "running",
            "rigState": "present",
            "workflowInstanceId": "wf-fixture",
            "seats": [prov.seat("at-main", token=True, session="present", startup="ready")],
        },
    )

    rc = orr.main(["start", "--run-dir", str(run), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert payload["error"]["code"] == "rig_exists"
    assert "resume" in payload["error"]["hint"]
    assert rig_calls(run) == [], "a refused start must not spawn anything"


# ------------------------------------------- CT-02: no token => awaiting-decision
def test_ct02_no_token_is_blocked_with_zero_mutation(tmp_path, capsys):
    run = bundle(
        tmp_path, "FI-05", state=stopped([prov.seat("at-main", token=False), prov.seat("at-tdo", token=True)])
    )
    state_before = (run / "openrig" / "continuity-state.json").read_bytes()

    rc = orr.main(["resume", "--run-dir", str(run), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert payload["error"]["code"] == "continuity_blocked"
    seats = {s["logicalId"]: s for s in payload["continuity"]["seats"]}
    assert seats["at-main"]["expectedAction"] == "awaiting-decision"
    assert seats["at-tdo"]["expectedAction"] == "resume-original"
    assert payload["continuity"]["blockedSeats"]
    # Zero mutation: no rig process at all, and the observed state is byte-identical.
    assert rig_calls(run) == []
    assert (run / "openrig" / "continuity-state.json").read_bytes() == state_before
    # The refusal is still evidence: the plan exists and says blocked.
    plan = json.loads((run / oc.PLAN_REL).read_text(encoding="utf-8"))
    assert plan["decisionStatus"] == "blocked"


# ------------------------------------- CT-03: fresh outside the authorized list
def test_ct03_fresh_outside_authorization_is_mismatch(tmp_path, capsys):
    run = bundle(
        tmp_path,
        "FI-05b",
        state=stopped(
            [
                prov.seat("at-main", token=True, actual="fresh-primed",
                          session="present", startup="ready"),
                prov.seat("at-qa", token=False),
            ]
        ),
    )

    rc = orr.main(
        ["resume", "--run-dir", str(run), "--fresh", "at-qa", "--reason", "qa lost", "--json"]
    )
    payload = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert payload["error"]["code"] == "continuity_mismatch"
    assert [row["logicalId"] for row in payload["continuity"]["mismatchedSeats"]] == ["at-main"]
    assert rig_calls(run) == [], "a mismatch must not instantiate or start anything"


# ------------------------------------- CT-04: authorized fresh, with a real reason
def test_ct04_authorized_fresh_primes_and_verifies(tmp_path, capsys):
    run = bundle(
        tmp_path,
        "FI-06",
        state=stopped([prov.seat("at-main", token=True), prov.seat("at-qa", token=False)]),
        after_state=stopped(
            [
                prov.seat("at-main", token=True, actual="resumed", session="present", startup="ready"),
                prov.seat("at-qa", token=False, actual="fresh-primed", session="present", startup="ready"),
            ]
        ),
    )

    rc = orr.main(
        ["resume", "--run-dir", str(run), "--fresh", "at-qa", "--reason", "qa lost", "--json"]
    )
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0, payload
    seats = {s["logicalId"]: s for s in payload["continuity"]["seats"]}
    assert seats["at-qa"]["freshAuthorized"] is True
    assert seats["at-qa"]["freshReason"] == "qa lost"
    assert seats["at-qa"]["actualOutcome"] == "fresh-primed"
    assert seats["at-main"]["actualOutcome"] == "resumed"
    assert payload["continuity"]["actualOutcomeVerified"] is True
    assert payload["instantiated"] is False


# ------------------------------------------------- P-S10-02: manifest wiring
S11A_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "kickoff"
    / "openrig-round1-postrun-20261117"
    / "run-manifest.schema.s11a.json"
)


def _assert_s11a_shape(manifest: dict) -> None:
    schema = json.loads(S11A_SCHEMA_PATH.read_text(encoding="utf-8"))
    top = schema["properties"]
    assert set(manifest) <= set(top), "top-level additionalProperties:false violated"
    assert set(schema["required"]) <= set(manifest)
    assert manifest["status"] in top["status"]["enum"]
    if not manifest["seats"]:
        reason = manifest.get("seatsNotApplicableReason")
        assert isinstance(reason, str) and reason
    if not manifest["outputs"]:
        reason = manifest.get("outputsNotApplicableReason")
        assert isinstance(reason, str) and reason
    seat_props = top["seats"]["items"]["properties"]
    for seat in manifest["seats"]:
        assert set(seat) <= set(seat_props)
        assert seat["actualOutcome"] in seat_props["actualOutcome"]["enum"]
        assert seat["actualOutcome"] is not None
        if "session" in seat:
            assert seat["session"] in seat_props["session"]["enum"]
    assert isinstance(manifest["workflow"]["instanceId"], str)
    assert isinstance(manifest["workflow"]["entryQitemId"], str)
    try:
        import jsonschema
    except ImportError:
        return
    jsonschema.validate(manifest, schema)


def _written_manifest(run: Path) -> dict:
    return json.loads(
        (run / "reports" / "evidence" / "manifest" / "run-manifest.json").read_text()
    )


def _previous_manifest(run: Path, *, revision: int = 3, status: str = "stopped") -> dict:
    bridge, err = oc.load_bundle(run)
    assert err is None
    manifest = om.new_manifest(run, bridge, launch_id="launch-prev-stop")
    manifest["status"] = status
    manifest["revision"] = revision
    om.write_manifest(run, manifest)
    return manifest


def test_resume_success_updates_manifest_seats_outputs_and_revision(tmp_path):
    run = bundle(
        tmp_path,
        "FI-06",
        state=stopped([prov.seat("at-main", token=True), prov.seat("at-qa", token=False)]),
        after_state=stopped(
            [
                prov.seat("at-main", token=True, actual="resumed", session="present",
                          startup="ready"),
                prov.seat("at-qa", token=False, actual="fresh-primed", session="present",
                          startup="ready"),
            ]
        ),
    )
    previous = _previous_manifest(run, revision=3, status="stopped")

    report = oc.run_resume(Path(run), fresh=("at-qa",), reason="qa lost", live=False)

    assert report["ok"] is True, report
    manifest = _written_manifest(run)
    assert manifest["manifestId"] == previous["manifestId"]
    assert manifest["revision"] == 4, "resume must write a new manifest revision"
    assert manifest["status"] == "active"
    assert len(manifest["seats"]) == 2
    by_id = {seat["logicalId"]: seat for seat in manifest["seats"]}
    assert by_id["at-main"]["actualOutcome"] == "resumed"
    assert by_id["at-qa"]["actualOutcome"] == "fresh-primed"
    assert "seatsNotApplicableReason" not in manifest
    assert "outputsNotApplicableReason" not in manifest

    names = {Path(output["path"]).name for output in manifest["outputs"]}
    assert names == {"resume-receipt.json", "continuity-plan.json"}
    for output in manifest["outputs"]:
        path = Path(output["path"])
        assert path.is_file()
        assert output["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert output["bytes"] == path.stat().st_size
    receipt = json.loads(
        (run / "reports" / "evidence" / "resume-receipt.json").read_text()
    )
    assert receipt["status"] == "active"
    assert receipt["actualOutcomeVerified"] is True
    assert len(receipt["seats"]) == 2


def test_resume_large_output_spills_full_bytes_and_bounds_receipt(tmp_path, monkeypatch):
    """P-S10-03 resume success: full stream spilled, receipt/report keep tails only."""
    import openrig_runtime_output as ort

    run = bundle(
        tmp_path,
        "FI-BIG-RESUME",
        state={
            "daemonState": "running",
            "workflowInstanceId": "wf-fixture",
            "seats": [prov.seat("at-main", token=True, session="present", startup="ready")],
        },
        after_state=stopped(
            [prov.seat("at-main", token=True, actual="resumed", session="present", startup="ready")]
        ),
    )
    large = 2 * 1024 * 1024
    raw_stdout = json.dumps(
        {
            "status": "restored",
            "rigResult": "restored",
            "nodes": [{"logicalId": "at-main", "status": "resumed"}],
        }
    ) + "\n"
    raw_stderr = "E" * large + "\n"

    def fake_up(cmd, bridge, timeout=120):
        del bridge, timeout
        assert cmd[1:2] == ["up"]
        after_path = run / "openrig" / "continuity-state.after.json"
        (run / "openrig" / "continuity-state.json").write_text(
            after_path.read_text(encoding="utf-8"), encoding="utf-8"
        )
        return subprocess.CompletedProcess(cmd, 0, raw_stdout, raw_stderr)

    monkeypatch.setattr(oc, "_run", fake_up)
    report = oc.run_resume(Path(run), live=False)

    assert report["ok"] is True, report
    mutation = report["mutations"][-1]
    assert mutation["step"] == "up-existing"
    assert mutation["stdoutBytes"] == len(raw_stdout.encode("utf-8"))
    assert mutation["stderrBytes"] == len(raw_stderr.encode("utf-8"))
    assert mutation["stdoutTruncated"] is False and mutation["stderrTruncated"] is True
    assert len(mutation["stderrTail"].encode("utf-8")) <= ort.TAIL_BYTES
    assert Path(mutation["stderrPath"]).stat().st_size == mutation["stderrBytes"]
    assert hashlib.sha256(Path(mutation["stderrPath"]).read_bytes()).hexdigest() == mutation["stderrSha256"]
    sidecar = json.loads(Path(mutation["evidencePath"]).read_text(encoding="utf-8"))
    assert sidecar["streams"]["stderr"]["tailBytes"] == ort.TAIL_BYTES
    assert "E" * 10000 not in sidecar["streams"]["stderr"]["tail"]

    receipt_path = run / oc.RESUME_RECEIPT_REL
    import stat

    assert stat.S_IMODE(receipt_path.stat().st_mode) == 0o600
    receipt_text = receipt_path.read_text(encoding="utf-8")
    receipt = json.loads(receipt_text)
    receipt_step = receipt["mutationSteps"][-1]
    assert receipt_step["stderrBytes"] == mutation["stderrBytes"]
    assert receipt_step["stderrPath"] == mutation["stderrPath"]
    assert len(receipt_step["stderrTail"].encode("utf-8")) <= ort.TAIL_BYTES
    assert "E" * 10000 not in receipt_text
    assert "E" * 10000 not in json.dumps(report)


def test_resume_tolerated_partial_restore_keeps_bounded_output_evidence(tmp_path, monkeypatch):
    """P-S10-03 partial path: rc1 tolerated outcome still has bounded proof + spill."""
    run = bundle(
        tmp_path,
        "FI-BIG-PARTIAL",
        state={
            "daemonState": "running",
            "workflowInstanceId": "wf-fixture",
            "seats": [prov.seat("at-main", token=False, session="present", startup="ready")],
        },
        after_state=stopped(
            [prov.seat("at-main", token=False, actual="fresh-primed", session="present", startup="ready")]
        ),
    )
    large = 2 * 1024 * 1024
    raw_stdout = json.dumps(
        {
            "status": "restored",
            "rigResult": "partially_restored",
            "nodes": [{"logicalId": "at-main", "status": "fresh-primed"}],
        }
    ) + "\n"
    raw_stderr = "P" * large + "\n"

    def fake_up(cmd, bridge, timeout=120):
        del bridge, timeout
        after_path = run / "openrig" / "continuity-state.after.json"
        (run / "openrig" / "continuity-state.json").write_text(
            after_path.read_text(encoding="utf-8"), encoding="utf-8"
        )
        return subprocess.CompletedProcess(cmd, 1, raw_stdout, raw_stderr)

    monkeypatch.setattr(oc, "_run", fake_up)
    report = oc.run_resume(
        Path(run), fresh=("at-main",), reason="operator authorized", live=False
    )

    assert report["ok"] is True, report
    mutation = report["mutations"][-1]
    assert mutation["toleratedPartialRestore"] is True
    assert mutation["stderrTruncated"] is True
    assert Path(mutation["stderrPath"]).stat().st_size == len(raw_stderr.encode("utf-8"))
    receipt_text = (run / oc.RESUME_RECEIPT_REL).read_text(encoding="utf-8")
    assert "P" * 10000 not in receipt_text
    receipt = json.loads(receipt_text)
    assert receipt["mutationSteps"][-1]["toleratedPartialRestore"] is True


def test_stop_large_output_spills_full_bytes_and_bounds_receipt(tmp_path, monkeypatch):
    """P-S10-03 stop path: down output is spilled, receipt/manifest stay bounded."""
    import openrig_runtime_output as ort

    run = bundle(
        tmp_path,
        "FI-BIG-STOP",
        state=stopped(
            [prov.seat("at-main", token=True, session="present", startup="ready")]
        ),
        archive="COMPLETE",
    )
    large = 2 * 1024 * 1024
    raw_stdout = "S" * large + "\n"
    raw_stderr = "E" * large + "\n"

    def fake_down(cmd, bridge, timeout=120):
        del bridge, timeout
        assert cmd[1:2] == ["down"]
        state_path = run / "openrig" / "continuity-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        for seat in state.get("seats", []):
            seat["session"] = "absent"
            seat["activity"] = None
        state["daemonState"] = "stopped"
        state["rigState"] = "absent"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, raw_stdout, raw_stderr)

    monkeypatch.setattr(oc, "_run", fake_down)
    report = oc.run_stop(Path(run))

    assert report["ok"] is True, report
    mutation = report["mutations"][0]
    assert mutation["step"] == "rig-down"
    assert mutation["stdoutBytes"] == len(raw_stdout.encode("utf-8"))
    assert mutation["stdoutTruncated"] is True and mutation["stderrTruncated"] is True
    assert len(mutation["stdoutTail"].encode("utf-8")) <= ort.TAIL_BYTES
    assert Path(mutation["stdoutPath"]).stat().st_size == mutation["stdoutBytes"]
    receipt_path = run / oc.STOP_RECEIPT_REL
    import stat

    assert stat.S_IMODE(receipt_path.stat().st_mode) == 0o600
    receipt_text = receipt_path.read_text(encoding="utf-8")
    receipt = json.loads(receipt_text)
    assert receipt["mutationSteps"][0]["stdoutPath"] == mutation["stdoutPath"]
    assert receipt["mutationSteps"][0]["stdoutBytes"] == mutation["stdoutBytes"]
    assert "S" * 10000 not in receipt_text
    assert "E" * 10000 not in receipt_text
    manifest_text = (run / "reports" / "evidence" / "manifest" / "run-manifest.json").read_text(
        encoding="utf-8"
    )
    assert "S" * 10000 not in manifest_text
    assert "E" * 10000 not in manifest_text


def test_stop_success_updates_manifest_and_records_archive_and_receipt(tmp_path):
    run = bundle(
        tmp_path,
        "FI-09",
        state=stopped(
            [prov.seat("at-main", token=True, session="present", startup="ready")]
        ),
        archive="COMPLETE",
    )

    report = oc.run_stop(Path(run))

    assert report["ok"] is True, report
    manifest = _written_manifest(run)
    assert manifest["status"] == "stopped"
    assert len(manifest["seats"]) == 1
    assert "seatsNotApplicableReason" not in manifest
    names = {Path(output["path"]).name for output in manifest["outputs"]}
    assert names == {"ARCHIVE-MANIFEST.json", "stop-receipt.json"}
    for output in manifest["outputs"]:
        path = Path(output["path"])
        assert path.is_file()
        assert output["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert output["bytes"] == path.stat().st_size
    receipt = json.loads(
        (run / "reports" / "evidence" / "stop-receipt.json").read_text()
    )
    assert receipt["status"] == "stopped"
    assert receipt["archive"]["status"] == "COMPLETE"
    assert len(receipt["seats"]) == 1


def test_stop_failure_updates_manifest_as_failed_without_raw_token(tmp_path, monkeypatch):
    token = "down-stderr-secret-token"
    run = bundle(
        tmp_path,
        "FI-09-FAIL",
        state=stopped(
            [prov.seat("at-main", token=True, session="present", startup="ready")]
        ),
        archive="COMPLETE",
    )

    def fake_run(cmd, bridge, timeout=120):
        assert cmd[1:2] == ["down"]
        return subprocess.CompletedProcess(cmd, 2, "", f"down failed token={token}")

    monkeypatch.setattr(oc, "_run", fake_run)

    report = oc.run_stop(Path(run))

    assert report["ok"] is False and report["error"]["code"] == "down_failed"
    manifest = _written_manifest(run)
    assert manifest["status"] == "failed"
    assert len(manifest["seats"]) == 1, "pre-stop seats are evidence even for a failed stop"
    assert "seatsNotApplicableReason" not in manifest
    names = {Path(output["path"]).name for output in manifest["outputs"]}
    assert names == {"ARCHIVE-MANIFEST.json", "stop-receipt.json"}
    receipt_text = (run / "reports" / "evidence" / "stop-receipt.json").read_text()
    assert token not in receipt_text
    receipt = json.loads(receipt_text)
    assert receipt["status"] == "failed"
    assert receipt["code"] == "down_failed"
    assert receipt["detailSha256"]


def test_stop_without_manifest_creates_stop_only_manifest(tmp_path):
    run = bundle(
        tmp_path,
        "FI-09-NOMAN",
        state=stopped([]),
        archive="COMPLETE",
    )

    report = oc.run_stop(Path(run))

    assert report["ok"] is True, report
    manifest = _written_manifest(run)
    assert manifest["status"] == "stopped"
    assert manifest["seats"] == []
    assert manifest["seatsNotApplicableReason"]
    names = {Path(output["path"]).name for output in manifest["outputs"]}
    assert names == {"ARCHIVE-MANIFEST.json", "stop-receipt.json"}


def test_stop_only_empty_manifest_conforms_to_s11a_schema_shape(tmp_path):
    run = bundle(
        tmp_path,
        "FI-09-EMPTY",
        state=stopped([]),
        archive="COMPLETE",
    )

    report = oc.run_stop(Path(run))

    assert report["ok"] is True, report
    manifest = _written_manifest(run)
    assert S11A_SCHEMA_PATH.is_file()
    assert manifest["status"] == "stopped"
    assert manifest["seats"] == []
    assert manifest["seatsNotApplicableReason"]
    assert manifest["outputs"]
    _assert_s11a_shape(manifest)


# ----------------------------------------------- CT-05: fresh needs a real reason
@pytest.mark.parametrize("reason", ["", "   "])
def test_ct05_fresh_without_reason_is_refused(tmp_path, capsys, reason):
    run = bundle(
        tmp_path, "FI-06", state=stopped([prov.seat("at-main", token=True), prov.seat("at-qa", token=False)])
    )

    rc = orr.main(
        ["resume", "--run-dir", str(run), "--fresh", "at-qa", "--reason", reason, "--json"]
    )
    payload = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert payload["error"]["code"] == "fresh_reason_missing"
    assert rig_calls(run) == []
    assert not (run / oc.PLAN_REL).exists(), "an argument error precedes the plan"


# ------------------------------- CT-06: expected resume but observed fresh => mismatch
def test_ct06_expected_resume_actual_fresh_is_mismatch_with_partial(tmp_path, capsys):
    run = bundle(
        tmp_path,
        "FI-07",
        state=stopped([prov.seat("at-main", token=True)]),
        after_state=stopped(
            [prov.seat("at-main", token=True, actual="fresh-primed", session="present", startup="ready")]
        ),
    )

    rc = orr.main(["resume", "--run-dir", str(run), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert payload["error"]["code"] == "continuity_mismatch"
    assert "expected resume-original, observed fresh-primed" in payload["error"]["message"]
    assert (run / oc.PLAN_PARTIAL_REL).is_file()
    calls = rig_calls(run)
    assert [c["argv"][:1] for c in calls] == [["daemon"], ["up"]], "no instantiate on resume"
    assert not any(c["argv"][:2] == ["workflow", "instantiate"] for c in calls)


# ---------------------------------- CT-07/CT-09: status is honest and read-only
def test_ct07_status_ready_is_not_continuity(tmp_path, capsys):
    run = bundle(
        tmp_path,
        "FI-08",
        state=stopped(
            [prov.seat("at-main", token=False, session="detached", startup="ready")]
        ),
    )

    rc = orr.main(["status", "--run-dir", str(run), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert payload["error"]["code"] == "continuity_blocked"
    seat = payload["continuity"]["seats"][0]
    assert seat["expectedAction"] == "awaiting-decision"
    assert seat["session"] == "detached"
    # startupStatus=ready is present in the input and still does not authorize anything.
    state = json.loads((run / "openrig" / "continuity-state.json").read_text(encoding="utf-8"))
    assert state["seats"][0]["startupStatus"] == "ready"


def test_ct09_status_writes_nothing(tmp_path, capsys):
    run = bundle(
        tmp_path,
        "FI-08",
        state=stopped([prov.seat("at-main", token=False, session="detached", startup="ready")]),
    )
    before = tree_fingerprint(tmp_path)

    orr.main(["status", "--run-dir", str(run), "--json"])
    capsys.readouterr()

    assert tree_fingerprint(tmp_path) == before, "status must not create, touch or rewrite a file"
    assert rig_calls(run) == []


def test_status_live_capture_is_ephemeral_and_keeps_run_tree_unchanged(
    tmp_path, capsys
):
    """P-S10-03: live observation may stream/spill, but status must leave no run files."""
    run = bundle(
        tmp_path,
        "FI-08-LIVE",
        state=stopped([prov.seat("at-main", token=True, session="present", startup="ready")]),
    )
    # Force the live `ps` path; a fixture state would short-circuit before any child.
    (run / "openrig" / "continuity-state.json").unlink()
    before = {
        key: value
        for key, value in tree_fingerprint(tmp_path).items()
        if not key.endswith("fake-rig.log")
    }

    orr.main(["status", "--run-dir", str(run), "--live", "--json"])
    capsys.readouterr()

    after = {
        key: value
        for key, value in tree_fingerprint(tmp_path).items()
        if not key.endswith("fake-rig.log")
    }
    assert after == before, "status --live must not create runtime-output files in the run tree"
    assert rig_calls(run), "the live observation actually invoked the fake rig"
    assert not (run / "reports" / "evidence" / "runtime-output").exists()


# ------------------------------------------- CT-08: resume only uses up --existing
def test_ct08_up_existing_argv(tmp_path):
    run = bundle(
        tmp_path,
        "FI-06",
        state=stopped([prov.seat("at-main", token=True), prov.seat("at-qa", token=False)]),
        after_state=stopped(
            [
                prov.seat("at-main", token=True, actual="resumed", session="present", startup="ready"),
                prov.seat("at-qa", token=False, actual="fresh-primed", session="present", startup="ready"),
            ]
        ),
    )
    bridge, err = oc.load_bundle(run)
    assert err is None
    plan = oc.build_plan(
        bridge,
        json.loads((run / "openrig" / "continuity-state.json").read_text(encoding="utf-8")),
        explicit_fresh=("at-qa",),
        fresh_reason="qa lost",
    )
    argv = oc.resume_argv(bridge, plan)

    assert argv[1:] == ["up", bridge["rigName"], "--existing", "--json", "--fresh", "at-qa"]
    assert "--existing" in argv
    assert "rig.yaml" not in " ".join(argv), "resume must never pass a rig SPEC to up"
    assert not any(part.endswith(".yaml") for part in argv)


def test_ct08m_mutation_a_spec_argv_would_flip_the_assertion(tmp_path):
    """Control: the CT-08 assertions discriminate. Feed them the forbidden argv and they
    must fail, which is what makes CT-08 a real guard rather than a tautology."""
    run = bundle(tmp_path, "FI-06", state=stopped([prov.seat("at-main", token=True)]))
    bridge, _ = oc.load_bundle(run)
    legal = oc.resume_argv(bridge, {"seats": []})
    mutated = [*oc.cli_argv(bridge), "up", str(run / "openrig" / "rig.yaml")]

    assert legal[1:] == ["up", bridge["rigName"], "--existing", "--json"]
    assert not any(part.endswith(".yaml") for part in legal)
    # The same predicates, applied to the mutation, are red:
    assert any(part.endswith(".yaml") for part in mutated)
    assert mutated[2] != bridge["rigName"] or "--existing" not in mutated


# ------------------------------------------- CT-10: archive gate precedes teardown
def test_ct10_stop_refuses_incomplete_archive(tmp_path, capsys):
    run = bundle(
        tmp_path,
        "FI-09",
        state=stopped([prov.seat("at-main", token=True, session="present", startup="ready")]),
        archive="INCOMPLETE",
    )

    rc = orr.main(["stop", "--run-dir", str(run), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert payload["error"]["code"] == "archive_incomplete"
    assert payload["archive"]["status"] == "INCOMPLETE"
    assert rig_calls(run) == [], "the gate runs before any down/daemon stop"


def test_ct10b_stop_runs_after_archive_is_complete(tmp_path, capsys):
    run = bundle(
        tmp_path,
        "FI-09",
        state=stopped([prov.seat("at-main", token=True, session="present", startup="ready")]),
        archive="COMPLETE",
    )

    rc = orr.main(["stop", "--run-dir", str(run), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0, payload
    steps = [m["step"] for m in payload["mutations"]]
    assert steps[0] == "rig-down"
    assert payload["orphans"] == []


def test_ct10c_stop_without_archive_manifest_is_incomplete(tmp_path, capsys):
    run = bundle(tmp_path, "FI-09", state=stopped([prov.seat("at-main", token=True)]))
    rc = orr.main(["stop", "--run-dir", str(run), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert payload["error"]["code"] == "archive_incomplete"
    assert payload["archive"]["status"] == "MISSING"


# ------------------------------------------------------------- CT-11: next is a print
def test_ct11_next_prints_five_steps_and_writes_nothing(tmp_path, capsys):
    run = bundle(tmp_path, "FI-04", state=stopped([prov.seat("at-main", token=True)]))
    before = tree_fingerprint(tmp_path)

    rc = orr.main(["next", "--run-dir", str(run), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert len(payload["steps"]) == 5
    assert [s["id"] for s in payload["steps"]] == [
        "check", "start-dry-run", "start", "verify-render", "archive-gate",
    ]
    assert tree_fingerprint(tmp_path) == before
    assert rig_calls(run) == []


# ------------------------------------------------------- observation axes (§7, D-016..)
def test_ct15_obs_hook_missing(tmp_path):
    """A missing hook degrades EVIDENCE, never the activity it did observe."""
    observation = oc.normalize_observation(
        {
            "session": "present",
            "activity": "working",
            "evidence": "degraded",
            "evidenceReasons": ["hook_missing"],
        }
    )
    assert observation == {
        "session": "present",
        "activity": "working",
        "evidence": "degraded",
        "evidenceReasons": ["hook_missing"],
    }


def test_ct16_obs_no_path(tmp_path):
    """No addressable observation source: activity null AND degraded, not 'healthy'."""
    observation = oc.normalize_observation(
        {
            "session": "absent",
            "activity": None,
            "evidence": "degraded",
            "evidenceReasons": ["no_observation_path"],
        }
    )
    assert observation["activity"] is None
    assert observation["evidence"] == "degraded"
    assert "no_observation_path" in observation["evidenceReasons"]


def test_ct17_obs_absent(tmp_path):
    """Absence is not degradation: ps worked and found no session."""
    observation = oc.normalize_observation(
        {"session": "absent", "activity": "idle-at-prompt", "evidence": "observed", "evidenceReasons": []}
    )
    assert observation["session"] == "absent"
    assert observation["activity"] is None, "a non-present session carries no activity (D-019)"
    assert observation["evidence"] != "degraded"
    assert observation["evidenceReasons"] == []


def test_ct18_obs_oracle_unknown(tmp_path):
    """`unknown` is an honest activity value, not an evidence degradation."""
    observation = oc.normalize_observation(
        {
            "session": "present",
            "activity": "unknown",
            "evidence": "oracle",
            "evidenceReasons": ["oracle_unknown"],
        }
    )
    assert observation["activity"] == "unknown"
    assert observation["evidence"] != "degraded"
    assert "oracle_unknown" not in observation["evidenceReasons"]


def test_ct19_obs_long_call(tmp_path):
    """An old queue row plus live activity is work in progress, not a stall (D-014)."""
    working = oc.normalize_observation(
        {"session": "present", "activity": "working", "evidence": "observed"}
    )
    verdict = oc.stall_verdict(working, queue_age_seconds=9_000)
    assert verdict["stalled"] is False
    assert verdict["health"] == "observed"

    # And the honest negative: no signal is DEGRADED, never "healthy".
    silent = oc.normalize_observation(
        {
            "session": "absent",
            "activity": None,
            "evidence": "degraded",
            "evidenceReasons": ["no_observation_path"],
        }
    )
    assert oc.stall_verdict(silent, queue_age_seconds=1)["health"] == "degraded"


# ------------------------------------------------------- plan contract (CT-05/CT-06)
def test_plan_records_unknown_token_as_unknown_not_false(tmp_path):
    run = bundle(tmp_path, "FI-05", state=stopped([prov.seat("at-main", token="unknown")]))
    bridge, _ = oc.load_bundle(run)
    plan = oc.build_plan(
        bridge, json.loads((run / "openrig" / "continuity-state.json").read_text(encoding="utf-8"))
    )
    seat = plan["seats"][0]
    assert seat["resumeTokenPresent"] == "unknown"
    assert seat["expectedAction"] == "awaiting-decision", "unknown never authorizes a resume"
    assert plan["decisionStatus"] == "blocked"


def test_plan_reports_every_required_field(tmp_path):
    run = bundle(tmp_path, "FI-04", state=stopped([prov.seat("at-main", token=True)]))
    bridge, _ = oc.load_bundle(run)
    plan = oc.build_plan(
        bridge,
        json.loads((run / "openrig" / "continuity-state.json").read_text(encoding="utf-8")),
        explicit_fresh=("at-main",),
        fresh_reason="rebuild",
    )
    required = {
        "logicalId", "canonicalSessionName", "nodeId", "restorePolicy", "resumeTokenPresent",
        "expectedAction", "freshAuthorized", "freshReason", "evidencePath",
        "actualOutcome", "session", "activity", "evidence", "evidenceReasons",
    }
    assert required <= set(plan["seats"][0])
    assert plan["decisionStatus"] == "allow"
    assert plan["explicitFreshSeats"] == ["at-main"]


# ------------------------------------------------------------ S9-R-01 fixture root
def test_s9r01_unset_fixture_root_never_resolves_to_a_shared_default(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENRIG_S9_FIXTURES", raising=False)
    target = Path("FI-99")
    assert orr.resolve_fixture_run_dir(target) == target, "no silent /tmp default"
    assert orr.fixture_root() is None


def test_s9r01_set_fixture_root_resolves(tmp_path, monkeypatch):
    root = tmp_path / "fixtures"
    (root / "FI-99").mkdir(parents=True)
    monkeypatch.setenv("OPENRIG_S9_FIXTURES", str(root))
    assert orr.resolve_fixture_run_dir(Path("FI-99")) == root / "FI-99"


def test_s9r01_provisioner_refuses_without_env(monkeypatch, capsys):
    monkeypatch.delenv("OPENRIG_S9_FIXTURES", raising=False)
    rc = prov.main(["--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert payload["error"]["code"] == "fixture_root_unset"
    assert "S9-R-01" in payload["error"]["message"]
    assert "OPENRIG_S9_FIXTURES" in payload["error"]["hint"]


# ------------------------------------------- S10-F-01 / N-CT-02: the LIVE observation
# The real `rig ps --nodes --json` payload is a BARE LIST whose row carries
# `resumeTokenPresent` (bool) and no `actualOutcome`. Before N-CT-02 the wrapper assumed
# an object, read `tokenState`, and synth esised `actualOutcome: ready`, which made live
# resume refuse (continuity_blocked) and live `--fresh` mismatch. These cases pin the real
# shapes; N-CT-REPRO.txt keeps the pre-fix failure.

REAL_PS_ROW = {
    "logicalId": "cert",
    "canonicalSessionName": "cert@openrig-s10-cert",
    "runtime": "opencode",
    "model": "deepseek/deepseek-flash",
    "startupStatus": "ready",
    "sessionStatus": "running",
    "lifecycleState": "running",
    "resumeType": "opencode_session",
    "resumeTokenPresent": True,
    "intentionallyStopped": False,
}


def _completed(argv, rc=0, stdout="", stderr=""):
    import subprocess

    return subprocess.CompletedProcess(argv, rc, stdout, stderr)


def test_ct12_real_ps_row_is_resume_original():
    """AT-S10-CT-12: a real ps row (bare list + resumeTokenPresent) plans resume-original."""
    seats = oc._seats_from_ps([REAL_PS_ROW])

    assert seats[0]["resumeTokenPresent"] is True
    plan = oc.build_plan({"rigName": "r", "seatMap": {"cert": "cert@openrig-s10-cert"}},
                         {"seats": seats}, state_source="ps")
    assert plan["decisionStatus"] == "allow", plan.get("blockedSeats")
    assert plan["seats"][0]["expectedAction"] == "resume-original"


def test_ct12b_legacy_token_state_is_mapped_explicitly():
    present = oc._seats_from_ps({"nodes": [{"logicalId": "a", "tokenState": "present"}]})
    missing = oc._seats_from_ps({"nodes": [{"logicalId": "b", "tokenState": "missing"}]})

    assert present[0]["resumeTokenPresent"] is True
    assert missing[0]["resumeTokenPresent"] is False


def test_ct12c_absent_token_is_unknown_not_false():
    """No token field at all is `unknown` (rule 10), never a fabricated False/True."""
    seats = oc._seats_from_ps([{"logicalId": "a", "runtime": "opencode"}])

    assert seats[0]["resumeTokenPresent"] is None
    assert "actualOutcome" not in seats[0], "ps cannot be the source of an outcome"
    plan = oc.build_plan({"rigName": "r"}, {"seats": seats}, state_source="ps")
    assert plan["seats"][0]["expectedAction"] == "awaiting-decision"


def test_ct12d_live_state_proves_the_daemon_is_up(tmp_path, monkeypatch):
    """F-01d: a ps that answered is a running daemon, so resume must not start it again."""
    run = bundle(tmp_path, "FI-12d", state=stopped([prov.seat("at-main", token=True)]))
    (run / "openrig" / "continuity-state.json").unlink()
    calls: list[list[str]] = []

    def fake_run(argv, bridge, timeout=120):
        calls.append(list(argv))
        return _completed(argv, 0, json.dumps([REAL_PS_ROW | {"logicalId": "at-main",
                                                             "canonicalSessionName": "at-main@fixture"}]))

    monkeypatch.setattr(oc, "_run", fake_run)
    bridge, err = oc.load_bundle(run)
    assert err is None
    state, source = oc.load_observed_state(run, bridge, live=True)

    assert source == "ps"
    assert state["daemonState"] == "running"
    assert state["daemonStateProvenance"] == "ps --nodes answered"
    assert not any("daemon" in " ".join(c) for c in calls), "ps answered: no daemon probe"


def test_ct12e_actual_outcome_comes_from_up_existing_json(tmp_path, monkeypatch, capsys):
    """F-01c: the restore's own per-node status is the outcome, with provenance."""
    run = bundle(tmp_path, "FI-12e", state=stopped([prov.seat("at-main", token=True)]))
    (run / "openrig" / "continuity-state.json").unlink()
    # A live run has no continuity-state.json; `start` writes the instance into the manifest.
    manifest = run / "reports" / "evidence" / "manifest" / "run-manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"workflow": {"instanceId": "wf-live-1"}}), encoding="utf-8")

    def fake_run(argv, bridge, timeout=120):
        joined = " ".join(argv)
        if "ps" in argv:
            return _completed(argv, 0, json.dumps([REAL_PS_ROW | {
                "logicalId": "at-main", "canonicalSessionName": "at-main@fixture"}]))
        if "up" in argv:
            assert "--json" in argv, "the restore status is only observable via --json"
            return _completed(argv, 0, json.dumps({"ok": True, "nodes": [
                {"logicalId": "at-main", "status": "resumed"}]}))
        raise AssertionError(f"unexpected call: {joined}")

    monkeypatch.setattr(oc, "_run", fake_run)
    rc = orr.main(["resume", "--run-dir", str(run), "--live", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0, payload
    seats = {s["logicalId"]: s for s in payload["continuity"]["seats"]}
    assert seats["at-main"]["actualOutcome"] == "resumed"
    assert payload["continuity"]["actualOutcomeVerified"] is True
    assert payload["actualOutcomeProvenance"] == "up-existing-json"
    assert payload["workflowInstanceProvenance"] == "run-manifest"
    assert payload["attachedWorkflowInstance"] == "wf-live-1"
    assert payload["instantiated"] is False


def test_ct12f_a_missing_status_is_reported_not_fabricated(tmp_path, monkeypatch, capsys):
    """If the restore omits a seat, that seat keeps no outcome and the row is not green."""
    run = bundle(tmp_path, "FI-12f", state=stopped([prov.seat("at-main", token=True)]))
    (run / "openrig" / "continuity-state.json").unlink()

    def fake_run(argv, bridge, timeout=120):
        if "ps" in argv:
            return _completed(argv, 0, json.dumps([REAL_PS_ROW | {
                "logicalId": "at-main", "canonicalSessionName": "at-main@fixture"}]))
        return _completed(argv, 0, json.dumps({"ok": True, "nodes": []}))

    monkeypatch.setattr(oc, "_run", fake_run)
    rc = orr.main(["resume", "--run-dir", str(run), "--live", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert payload["error"]["code"] == "continuity_mismatch"
    assert payload["actualOutcomeProvenance"] == "up-existing-json"
    assert payload["actualOutcomeMissing"] == ["at-main"]
    assert "at-main" in payload["error"]["message"]


def test_ct12g_without_any_instance_source_resume_still_refuses(tmp_path, monkeypatch, capsys):
    """No manifest and no state means no instance: refuse, never instantiate."""
    run = bundle(tmp_path, "FI-12g", state=stopped([prov.seat("at-main", token=True)]))
    (run / "openrig" / "continuity-state.json").unlink()

    def fake_run(argv, bridge, timeout=120):
        if "ps" in argv:
            return _completed(argv, 0, json.dumps([REAL_PS_ROW | {
                "logicalId": "at-main", "canonicalSessionName": "at-main@fixture"}]))
        return _completed(argv, 0, json.dumps({"ok": True, "nodes": [
            {"logicalId": "at-main", "status": "resumed"}]}))

    monkeypatch.setattr(oc, "_run", fake_run)
    rc = orr.main(["resume", "--run-dir", str(run), "--live", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert payload["error"]["code"] == "workflow_instance_conflict"
    assert payload["workflowInstanceProvenance"] == "no-run-manifest"


def test_live_ps_maps_dsh_exited_and_null_without_inventing_present():
    base = {
        "logicalId": "at-main",
        "canonicalSessionName": "at-main@fixture",
        "runtime": "dsh",
        "pid": 4242,
        "startupStatus": "failed",
        "resumeTokenPresent": True,
    }

    exited = oc._seats_from_ps([{**base, "sessionStatus": "exited"}])[0]
    assert exited["session"] == "exited"
    assert exited["activity"] is None

    stopped = oc._seats_from_ps([{**base, "sessionStatus": "stopped"}])[0]
    assert stopped["session"] == "absent"

    unknown = oc._seats_from_ps([{**base, "sessionStatus": None}])[0]
    assert unknown["session"] is None
    assert unknown["evidence"] == "degraded"
    assert om.PS_SESSION_UNKNOWN_REASON in unknown["evidenceReasons"]
    assert unknown["session"] != "present"


def test_live_ps_maps_nested_agent_activity_working_and_idle():
    base = {
        "logicalId": "at-main",
        "canonicalSessionName": "at-main@fixture",
        "runtime": "dsh",
        "startupStatus": "ready",
        "sessionStatus": "running",
        "resumeTokenPresent": True,
    }

    working = oc._seats_from_ps(
        [{**base, "agentActivity": {"state": "running", "reason": "tool_use"}}]
    )[0]
    assert working["session"] == "present"
    assert working["activity"] == "working"
    assert working["evidence"] == "observed"

    idle = oc._seats_from_ps(
        [{**base, "agentActivity": {"state": "idle"}}]
    )[0]
    assert idle["activity"] == "idle-at-prompt"

    needs_input = oc._seats_from_ps(
        [{**base, "agentActivity": {"state": "needs_input"}}]
    )[0]
    assert needs_input["activity"] == "idle-at-prompt", (
        "a real prompt-waiting fact must not be degraded to unknown"
    )


@pytest.mark.parametrize(
    "payload",
    [None, {}, {"nodes": []}, {"rows": []}, {"unknown": []}, "bad-shape", [{"runtime": "dsh"}]],
)
def test_ps_rejects_empty_and_unknown_payload_shapes(payload):
    with pytest.raises(om.PsPayloadError):
        oc._seats_from_ps(payload)


def test_live_ps_rc0_empty_object_fails_closed(tmp_path, monkeypatch):
    run = bundle(tmp_path, "FI-PS-EMPTY", state=stopped([prov.seat("at-main", token=True)]))
    (run / "openrig" / "continuity-state.json").unlink()

    def fake_run(argv, bridge, timeout=120):
        del bridge, timeout
        return _completed(argv, 0, "{}", "")

    monkeypatch.setattr(oc, "_run", fake_run)
    bridge, err = oc.load_bundle(run)
    assert err is None

    state, source = oc.load_observed_state(run, bridge, live=True)
    assert state is None
    assert "payload shape is unusable" in source


def test_build_plan_blocks_when_bridge_seat_target_is_missing():
    bridge = {"rigName": "r", "seatMap": {"at-main": "at-main@fixture", "at-qa": "at-qa@fixture"}}
    state = {"seats": [prov.seat("at-main", token=True)]}

    plan = oc.build_plan(bridge, state, state_source="ps")

    assert plan["decisionStatus"] == "blocked"
    assert plan["code"] == oc.CODE_BLOCKED
    missing = [row for row in plan["blockedSeats"] if row.get("logicalId") == "at-qa"]
    assert missing and "was not observed" in missing[0]["reason"]


def test_build_plan_blocks_when_bridge_seatmap_is_missing_even_with_seat_rows():
    plan = oc.build_plan(
        {"rigName": "r"},
        {"seats": [prov.seat("at-main", token=True)]},
        state_source="ps",
    )
    assert plan["decisionStatus"] == "blocked"
    assert plan["code"] == oc.CODE_BLOCKED
    assert any("seatMap is missing" in row["reason"] for row in plan["blockedSeats"])


def test_compare_outcomes_never_treats_empty_plan_as_all_match():
    compared = oc.compare_outcomes(
        {"seats": []},
        {"seats": [prov.seat("at-main", token=True, session="present")]},
    )
    assert compared["all_match"] is False
    assert "no seat rows" in compared["reason"]


def test_compare_outcomes_requires_each_planned_seat_after_resume():
    plan = {
        "seats": [
            {
                "logicalId": "at-main",
                "expectedAction": "resume-original",
            }
        ]
    }
    compared = oc.compare_outcomes(plan, {"seats": []})
    assert compared["all_match"] is False
    assert "not observed after resume" in compared["reason"]


def test_managed_evidence_fallback_keeps_stale_provenance_without_outcome(
    tmp_path,
):
    run = bundle(
        tmp_path,
        "FI-MANAGED-FALLBACK",
        state=stopped([prov.seat("at-main", token=True, actual="fresh-primed")]),
    )
    bridge, err = oc.load_bundle(run)
    assert err is None
    manifest = om.new_manifest(run, bridge, launch_id="launch-managed-fallback")
    manifest["workflow"]["instanceId"] = "wf-managed-fallback"
    om.finalize_manifest(
        manifest,
        status="active",
        seats=[prov.seat("at-main", token=True, actual="fresh-primed")],
    )
    om.write_manifest(run, manifest)

    fallback = oc._state_from_managed_evidence(
        run, bridge, daemon_down_detail="Error: Daemon not running."
    )
    assert fallback is not None
    assert fallback["daemonState"] == "stopped"
    assert "managed-manifest" in fallback["stateProvenance"]
    seat = fallback["seats"][0]
    assert seat["observationStale"] is True
    assert "actualOutcome" not in seat, "an earlier outcome is not this attempt's outcome"
    assert seat["priorActualOutcome"] == "fresh-primed"


def test_continuity_atomic_json_uses_unique_temp_and_leaves_fixed_tmp_alone(
    tmp_path,
):
    target = tmp_path / oc.PLAN_REL
    fixed_tmp = target.with_name(f"{target.name}.tmp")
    fixed_tmp.mkdir(parents=True)

    oc._atomic_write_json(target, {"schemaVersion": 1, "decisionStatus": "allow"})

    assert json.loads(target.read_text(encoding="utf-8"))["decisionStatus"] == "allow"
    assert fixed_tmp.is_dir(), "a fixed .tmp collision must not be reused or removed"
    assert not any(
        path.is_file() and path.name.endswith(".tmp")
        for path in target.parent.iterdir()
    )


def test_p018_up_failure_records_stdout_and_message(tmp_path, monkeypatch):
    """P-018: a failed `up --existing` keeps its stdout on the mutation and in the detail."""
    import subprocess

    run = bundle(tmp_path, "FI-P018", state={
        "daemonState": "running",
        "seats": [prov.seat("at-main", token=True, session="present", startup="ready")],
    })

    def fake_run(cmd, bridge, timeout=120):
        return subprocess.CompletedProcess(
            cmd, 1,
            '{"ok": false, "error": {"code": "fresh_failed", "message": "boom"}}', "")

    monkeypatch.setattr(oc, "_run", fake_run)
    report = oc.run_resume(Path(run), live=False)

    assert report["error"]["code"] == "up_failed"
    mutation = report["mutations"][0]
    assert mutation["step"] == "up-existing"
    assert "boom" in mutation["stdoutTail"]
    assert mutation["stdoutSha256"]
    assert "boom" in report["error"]["message"]


def test_p020_partially_restored_fresh_primes_the_target(tmp_path, monkeypatch):
    """P-020: rc1 + nodes[target]=fresh-primed means the fresh actually happened."""
    import subprocess

    run = bundle(
        tmp_path, "FI-P020",
        state={"daemonState": "running", "workflowInstanceId": "wf-fixture",
               "seats": [prov.seat("at-main", token=True, session="present", startup="ready")]},
        after_state={"daemonState": "running", "workflowInstanceId": "wf-fixture",
                     "seats": [prov.seat("at-main", token=True, session="present",
                                         startup="ready", actual="fresh-primed")]},
    )

    def fake_run(cmd, bridge, timeout=120):
        return subprocess.CompletedProcess(
            cmd, 1,
            '{"status":"restored","rigResult":"partially_restored","nodes":'
            '[{"logicalId":"at-main","status":"fresh-primed"}]}', "")

    monkeypatch.setattr(oc, "_run", fake_run)
    report = oc.run_resume(Path(run), fresh=("at-main",), reason="operator authorized", live=False)

    assert report["ok"] is True, report
    up = next(m for m in report["mutations"] if m["step"] == "up-existing")
    assert up["toleratedPartialRestore"] is True
    assert up["rc"] == 1


# ------------------------------------- S10 F4/F5: unobserved seats fail closed
def test_seat_observed_boundary_requires_bool_true_and_fixture_only_missing():
    """Only a literal bool True is an observation; missing is fixture-only compat."""
    assert oc.seat_observed({}, state_source="fixture") == (True, None)
    assert oc.seat_observed({}, state_source="ps") == (False, None)
    assert oc.seat_observed({"observed": True}, state_source="ps") == (True, None)
    assert oc.seat_observed({"observed": False}, state_source="ps") == (False, None)
    assert oc.seat_observed({"observed": "false"}, state_source="fixture") == (
        False,
        "observed_not_boolean",
    )


@pytest.mark.parametrize("observed", [False, "false"])
def test_unobserved_seat_with_token_cannot_resume_or_satisfy_coverage(observed):
    """observed=False (and a non-bool lookalike) must not authorize a resume."""
    seat = {**prov.seat("at-main", token=True), "observed": observed}
    bridge = {"rigName": "r", "seatMap": {"at-main": "at-main@fixture"}}

    plan = oc.build_plan(bridge, {"seats": [seat]}, state_source="ps")

    assert plan["decisionStatus"] == "blocked"
    row = plan["seats"][0]
    assert row["expectedAction"] == "awaiting-decision"
    assert row["observed"] is False
    assert row["evidence"] == "degraded"
    coverage = [
        item
        for item in plan["blockedSeats"]
        if item.get("logicalId") == "at-main"
        and "bridge.seatMap target" in item["reason"]
        and "was not observed" in item["reason"]
    ]
    assert coverage, "an unobserved stub must not satisfy seatMap coverage"
    seat_block = [
        item
        for item in plan["blockedSeats"]
        if item.get("logicalId") == "at-main"
        and item not in coverage
        and ("seat was not observed" in item["reason"]
             or "observed_not_boolean" in item["reason"])
    ]
    assert seat_block, plan["blockedSeats"]
    if observed == "false":
        assert "observed_not_boolean" in row["evidenceReasons"]


def test_missing_observed_field_is_fixture_only_compatibility():
    """Legacy fixture rows without `observed` still resume; live rows fail closed."""
    seat = prov.seat("at-main", token=True)
    bridge = {"rigName": "r", "seatMap": {"at-main": "at-main@fixture"}}

    fixture = oc.build_plan(bridge, {"seats": [seat]}, state_source="fixture")
    assert fixture["decisionStatus"] == "allow"
    assert fixture["seats"][0]["expectedAction"] == "resume-original"
    assert fixture["seats"][0]["observed"] is True

    live = oc.build_plan(bridge, {"seats": [seat]}, state_source="ps")
    assert live["decisionStatus"] == "blocked"
    assert live["seats"][0]["expectedAction"] == "awaiting-decision"
    assert live["seats"][0]["observed"] is False


def test_observed_true_is_the_only_resume_participant():
    seat = {**prov.seat("at-main", token=True), "observed": True}
    bridge = {"rigName": "r", "seatMap": {"at-main": "at-main@fixture"}}

    plan = oc.build_plan(bridge, {"seats": [seat]}, state_source="ps")

    assert plan["decisionStatus"] == "allow"
    assert plan["seats"][0]["expectedAction"] == "resume-original"
    assert plan["seats"][0]["observed"] is True
    assert plan["seats"][0]["unobservedFresh"] is False


def test_unobserved_fresh_with_reason_is_allowed_but_marked():
    """Daemon-down recovery stays possible, but the fresh is visibly degraded."""
    seat = {
        **prov.seat("at-main", token=True),
        "observed": False,
        "observationStale": True,
        "evidence": "degraded",
        "evidenceReasons": ["ps_unavailable"],
    }
    bridge = {"rigName": "r", "seatMap": {"at-main": "at-main@fixture"}}

    plan = oc.build_plan(
        bridge,
        {"seats": [seat]},
        explicit_fresh=("at-main",),
        fresh_reason="daemon unreachable; operator is rebuilding the session",
        state_source="ps",
    )

    assert plan["decisionStatus"] == "allow", plan["blockedSeats"]
    row = plan["seats"][0]
    assert row["expectedAction"] == "fresh-primed"
    assert row["freshAuthorized"] is True
    assert row["observed"] is False
    assert row["unobservedFresh"] is True
    assert row["observationStale"] is True
    assert row["evidence"] == "degraded"


def test_unobserved_fresh_without_reason_remains_blocked():
    seat = {**prov.seat("at-main", token=True), "observed": False}
    bridge = {"rigName": "r", "seatMap": {"at-main": "at-main@fixture"}}

    plan = oc.build_plan(
        bridge,
        {"seats": [seat]},
        explicit_fresh=("at-main",),
        fresh_reason="",
        state_source="ps",
    )

    assert plan["decisionStatus"] == "blocked"
    assert plan["code"] == oc.CODE_BLOCKED
    row = plan["seats"][0]
    assert row["expectedAction"] == "fresh-primed"
    assert row["freshAuthorized"] is True
    assert row["unobservedFresh"] is True
    assert any("non-empty reason" in item["reason"] for item in plan["blockedSeats"])
