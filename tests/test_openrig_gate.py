# -*- coding: utf-8 -*-
"""S9 Wave B · N-MAN-TST — archive / orphan / port / compaction / handover / retire.

Every case builds its own bundle in `tmp_path`; the CLI-level rows reuse the FI-13..FI-17
bundles provisioned by `test_openrig_manifest.provision` (one provisioner, one owner).

The four boundaries here are the ones where a wrong default is irreversible: teardown
before the archive is proven, retiring before either, "managed compaction" claimed by a
runtime that cannot do it, and a handover that cannot name its successor.
"""
import json
import sys
from pathlib import Path

import pytest

WG = Path(__file__).resolve().parents[1]
if str(WG / "scripts") not in sys.path:
    sys.path.insert(0, str(WG / "scripts"))
if str(WG / "tests") not in sys.path:
    sys.path.insert(0, str(WG / "tests"))

import openrig_gate as og  # noqa: E402
import openrig_run as orr  # noqa: E402
import test_openrig_manifest as tman  # noqa: E402


# ------------------------------------------------------------------ bound archive fixtures
def _archive_sha(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _write_bound_archive(
    run: Path,
    *,
    run_id: str | None = None,
    product_mutator=None,
    binding_mutator=None,
    sums_lines_override=None,
    write_sums: bool = True,
):
    """Build a genuinely bound product archive under `run` for gate-positive tests.

    The helper deliberately writes the real two-layer shape:
      <machine-root>/runs/<run-id>/MANIFEST.json + SHA256SUMS + files
      <run>/reports/evidence/archive/ARCHIVE-MANIFEST.json (binding path+sha256)
    Negative tests mutate one layer at a time so each failure is attributable.
    """
    import shutil

    run = Path(run)
    run_id = run_id or run.name
    product_root = run / "test-product-archive"
    shutil.rmtree(product_root, ignore_errors=True)
    machine_root = product_root / "machines" / "machine-a"
    run_archive = machine_root / "runs" / run_id
    run_archive.mkdir(parents=True, exist_ok=True)

    base_texts = {
        "RECORD.md": "# test archive\n",
        "run/openrig/OPENRIG-BRIDGE.json": json.dumps({"runId": run_id}) + "\n",
        "home/README.txt": "snapshot\n",
    }
    for rel, text in base_texts.items():
        target = run_archive / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    files = []
    for rel in sorted(base_texts):
        target = run_archive / rel
        raw = target.read_bytes()
        files.append({"path": rel, "bytes": len(raw), "sha256": _archive_sha(raw), "scope": "run"})

    product = {
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
        "files": files,
    }
    if product_mutator is not None:
        product_mutator(product, run_archive, machine_root)

    manifest_path = run_archive / "MANIFEST.json"
    manifest_path.write_text(json.dumps(product, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if write_sums:
        if sums_lines_override is None:
            lines = [
                f"{row['sha256']}  {row['path']}"
                for row in product.get("files", [])
                if isinstance(row, dict)
                and isinstance(row.get("sha256"), str)
                and isinstance(row.get("path"), str)
            ]
        elif callable(sums_lines_override):
            lines = sums_lines_override(product, run_archive)
        else:
            lines = list(sums_lines_override)
        (run_archive / "SHA256SUMS").write_text(
            "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
        )

    binding = {
        "schemaVersion": 1,
        "runId": run_id,
        "status": "COMPLETE",
        "reason": "fixture binding to a real product MANIFEST.json",
        "manifestPath": str(manifest_path.resolve()),
        "manifestSha256": _archive_sha(manifest_path.read_bytes()),
    }
    if binding_mutator is not None:
        binding_mutator(binding, manifest_path)
    binding_path = run / og.ARCHIVE_MANIFEST_REL
    binding_path.parent.mkdir(parents=True, exist_ok=True)
    binding_path.write_text(json.dumps(binding, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "product": product,
        "binding": binding,
        "manifestPath": manifest_path,
        "runArchive": run_archive,
        "machineRoot": machine_root,
    }


def _rebind_product_manifest(run: Path, manifest_path: Path) -> None:
    """Update the run-local binding after moving or rewriting a product manifest."""
    manifest_path = Path(manifest_path).resolve()
    binding_path = Path(run) / og.ARCHIVE_MANIFEST_REL
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    binding["manifestPath"] = str(manifest_path)
    binding["manifestSha256"] = _archive_sha(manifest_path.read_bytes())
    binding_path.write_text(json.dumps(binding, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _bind_existing_complete_fixture(run: Path) -> None:
    """Upgrade `test_openrig_manifest.build_run(..., archive='COMPLETE')` in place.

    The shared fixture module stays untouched (another teammate owns it); this local
    upgrade gives gate tests a real bound archive without weakening production code.
    """
    binding_path = Path(run) / og.ARCHIVE_MANIFEST_REL
    if not binding_path.is_file():
        return
    try:
        existing = json.loads(binding_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return
    if not isinstance(existing, dict) or str(existing.get("status") or "").upper() != "COMPLETE":
        return
    _write_bound_archive(Path(run), run_id=str(existing.get("runId") or Path(run).name))


# ------------------------------------------------------------------ archive gate
@pytest.mark.parametrize("status,ok", [("COMPLETE", True), ("INCOMPLETE", False),
                                       ("PARTIAL", False), ("MISSING", False)])
def test_archive_gate_only_complete_opens(tmp_path, status, ok):
    run = tman.build_run(tmp_path, "G1", archive=None if status == "MISSING" else status)
    if status == "COMPLETE":
        _write_bound_archive(run)
    gate = og.archive_gate(run)
    assert gate["ok"] is ok
    assert gate["status"] == status
    if not ok:
        assert gate["code"] == "archive_incomplete"


def test_archive_gate_treats_a_corrupt_manifest_as_incomplete(tmp_path):
    run = tman.build_run(tmp_path, "G2", archive="COMPLETE")
    (run / og.ARCHIVE_MANIFEST_REL).write_text("{not json", encoding="utf-8")
    gate = og.archive_gate(run)
    assert gate["ok"] is False and gate["status"] == "INCOMPLETE"


def test_archive_gate_accepts_a_fully_bound_complete_archive(tmp_path):
    run = tman.build_run(tmp_path, "BOUND", archive="COMPLETE")
    info = _write_bound_archive(run)

    gate = og.archive_gate(run)
    assert gate["ok"] is True, gate
    assert gate["status"] == "COMPLETE"
    assert info["manifestPath"].is_file()


@pytest.mark.parametrize("payload", [None, [], "COMPLETE", 42, True])
def test_archive_status_never_crashes_on_valid_non_object_json(tmp_path, payload):
    run = tman.build_run(tmp_path, "NON-OBJECT", archive="COMPLETE")
    (run / og.ARCHIVE_MANIFEST_REL).write_text(json.dumps(payload), encoding="utf-8")

    state = og.archive_status(run)  # must not raise AttributeError
    assert state["status"] == "INCOMPLETE"
    assert "root must be a JSON object" in state["reason"]
    assert og.archive_gate(run)["code"] == "archive_incomplete"


def test_archive_gate_rejects_binding_run_id_mismatch(tmp_path):
    run = tman.build_run(tmp_path, "RUNID", archive="COMPLETE")
    _write_bound_archive(
        run,
        binding_mutator=lambda binding, _manifest: binding.__setitem__("runId", "some-other-run"),
    )

    state = og.archive_status(run)
    assert state["status"] == "INCOMPLETE"
    assert "runId" in state["reason"] and "bridge" in state["reason"]


def test_archive_gate_rejects_bridge_run_id_mismatch(tmp_path):
    run = tman.build_run(tmp_path, "BRIDGE-RUNID", archive="COMPLETE")
    _write_bound_archive(run)
    bridge_path = run / "openrig" / "OPENRIG-BRIDGE.json"
    bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
    bridge["runId"] = "bridge-other"
    bridge_path.write_text(json.dumps(bridge), encoding="utf-8")

    assert "bridge runId" in og.archive_status(run)["reason"]


def test_archive_gate_rejects_product_run_id_mismatch(tmp_path):
    run = tman.build_run(tmp_path, "PRODUCT-RUNID", archive="COMPLETE")
    _write_bound_archive(
        run,
        product_mutator=lambda product, _archive, _machine: product.__setitem__("runId", "product-other"),
    )

    state = og.archive_status(run)
    assert state["status"] == "INCOMPLETE"
    assert "product manifest runId" in state["reason"]


def test_archive_gate_rejects_product_manifest_outside_runs_directory(tmp_path):
    run = tman.build_run(tmp_path, "MANIFEST-WRONG-PARENT", archive="COMPLETE")
    info = _write_bound_archive(run)

    assert og.archive_status(run)["status"] == "COMPLETE", "baseline must be complete"

    moved = info["machineRoot"] / "not-runs" / info["runArchive"].name
    moved.parent.mkdir(parents=True, exist_ok=True)
    info["runArchive"].rename(moved)
    _rebind_product_manifest(run, moved / "MANIFEST.json")

    state = og.archive_status(run)
    assert state["status"] == "INCOMPLETE"
    assert "<machine-root>/runs/<runId>/MANIFEST.json" in state["reason"]


def test_archive_gate_rejects_product_manifest_directory_run_id_mismatch(tmp_path):
    run = tman.build_run(tmp_path, "MANIFEST-WRONG-RUNID", archive="COMPLETE")
    info = _write_bound_archive(run)

    assert og.archive_status(run)["status"] == "COMPLETE", "baseline must be complete"

    moved = info["runArchive"].parent / "not-the-run-id"
    info["runArchive"].rename(moved)
    _rebind_product_manifest(run, moved / "MANIFEST.json")

    state = og.archive_status(run)
    assert state["status"] == "INCOMPLETE"
    assert "directory" in state["reason"] and "runId" in state["reason"]


def test_archive_gate_rejects_product_manifest_filename_mismatch(tmp_path):
    run = tman.build_run(tmp_path, "MANIFEST-WRONG-NAME", archive="COMPLETE")
    info = _write_bound_archive(run)

    assert og.archive_status(run)["status"] == "COMPLETE", "baseline must be complete"

    moved = info["runArchive"] / "PRODUCT-MANIFEST.json"
    info["manifestPath"].rename(moved)
    _rebind_product_manifest(run, moved)

    state = og.archive_status(run)
    assert state["status"] == "INCOMPLETE"
    assert "MANIFEST.json" in state["reason"]


def test_archive_gate_requires_a_real_product_manifest_path(tmp_path):
    run = tman.build_run(tmp_path, "NO-MANIFEST", archive="COMPLETE")
    missing = tmp_path / "not-there" / "MANIFEST.json"
    _write_bound_archive(
        run,
        binding_mutator=lambda binding, _manifest: binding.__setitem__("manifestPath", str(missing)),
    )

    state = og.archive_status(run)
    assert state["status"] == "INCOMPLETE"
    assert "manifestPath is not a real file" in state["reason"]


def test_archive_gate_rejects_non_hex_manifest_sha(tmp_path):
    run = tman.build_run(tmp_path, "SHA-SHAPE", archive="COMPLETE")
    _write_bound_archive(
        run,
        binding_mutator=lambda binding, _manifest: binding.__setitem__("manifestSha256", "deadbeef"),
    )

    assert "manifestSha256 must be 64-hex" in og.archive_status(run)["reason"]


def test_archive_gate_rejects_manifest_sha_mismatch(tmp_path):
    run = tman.build_run(tmp_path, "SHA-MISMATCH", archive="COMPLETE")
    _write_bound_archive(
        run,
        binding_mutator=lambda binding, _manifest: binding.__setitem__("manifestSha256", "0" * 64),
    )

    state = og.archive_status(run)
    assert state["status"] == "INCOMPLETE"
    assert "does not match product MANIFEST.json bytes" in state["reason"]


def test_archive_gate_rejects_product_manifest_that_is_not_an_object(tmp_path):
    run = tman.build_run(tmp_path, "PRODUCT-LIST", archive="COMPLETE")
    info = _write_bound_archive(run)
    info["manifestPath"].write_text("[]\n", encoding="utf-8")
    binding_path = run / og.ARCHIVE_MANIFEST_REL
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    binding["manifestSha256"] = _archive_sha(info["manifestPath"].read_bytes())
    binding_path.write_text(json.dumps(binding), encoding="utf-8")

    state = og.archive_status(run)
    assert state["status"] == "INCOMPLETE"
    assert "product MANIFEST.json root must be a JSON object" in state["reason"]


@pytest.mark.parametrize("status_key", ["archiveStatus", "status"])
def test_archive_gate_requires_product_status_complete(tmp_path, status_key):
    run = tman.build_run(tmp_path, f"PRODUCT-{status_key}", archive="COMPLETE")

    def mutate(product, _archive, _machine):
        if status_key == "archiveStatus":
            product["archiveStatus"] = "PARTIAL"
        else:
            product.pop("archiveStatus", None)
            product["status"] = "PARTIAL"

    _write_bound_archive(run, product_mutator=mutate)
    state = og.archive_status(run)
    assert state["status"] == "INCOMPLETE"
    assert status_key in state["reason"] and "COMPLETE" in state["reason"]


def test_archive_gate_rejects_product_status_keys_that_disagree(tmp_path):
    run = tman.build_run(tmp_path, "PRODUCT-DISAGREE", archive="COMPLETE")
    _write_bound_archive(
        run,
        product_mutator=lambda product, _archive, _machine: product.update(
            {"archiveStatus": "COMPLETE", "status": "PARTIAL"}
        ),
    )

    state = og.archive_status(run)
    assert state["status"] == "INCOMPLETE"
    assert "archiveStatus and status disagree" in state["reason"]


@pytest.mark.parametrize(
    "member", ["runSnapshot", "transcriptCapture", "openrigState", "homeSnapshot"]
)
def test_archive_gate_requires_each_required_member(tmp_path, member):
    run = tman.build_run(tmp_path, f"REQUIRED-{member}", archive="COMPLETE")
    _write_bound_archive(
        run,
        product_mutator=lambda product, _archive, _machine: product["required"].__setitem__(member, False),
    )

    state = og.archive_status(run)
    assert state["status"] == "INCOMPLETE"
    assert f"required.{member} must be true" in state["reason"]


def test_archive_gate_accepts_session_snapshots_explicitly_not_applicable(tmp_path):
    run = tman.build_run(tmp_path, "SESSIONS-NA", archive="COMPLETE")
    _write_bound_archive(run)

    state = og.archive_status(run)
    assert state["status"] == "COMPLETE", state
    product = json.loads((run / "test-product-archive/machines/machine-a/runs/SESSIONS-NA/MANIFEST.json").read_text())
    assert product["required"]["sessionSnapshots"] is False
    assert product["notApplicable"]["sessionSnapshots"] is True


def test_archive_gate_requires_session_snapshots_without_not_applicable(tmp_path):
    run = tman.build_run(tmp_path, "SESSIONS-REQUIRED", archive="COMPLETE")

    def mutate(product, _archive, _machine):
        product["required"]["sessionSnapshots"] = False
        product["notApplicable"] = {}

    _write_bound_archive(run, product_mutator=mutate)
    state = og.archive_status(run)
    assert state["status"] == "INCOMPLETE"
    assert "required.sessionSnapshots must be true" in state["reason"]


def test_archive_gate_requires_empty_missing_list(tmp_path):
    run = tman.build_run(tmp_path, "MISSING-LIST", archive="COMPLETE")
    _write_bound_archive(
        run,
        product_mutator=lambda product, _archive, _machine: product.__setitem__(
            "missing", ["homeSnapshot"]
        ),
    )

    state = og.archive_status(run)
    assert state["status"] == "INCOMPLETE"
    assert "missing must be []" in state["reason"]


@pytest.mark.parametrize(
    "mutate_bytes",
    [
        pytest.param(lambda row: row.pop("bytes", None), id="missing"),
        pytest.param(lambda row: row.__setitem__("bytes", "12"), id="string"),
        pytest.param(lambda row: row.__setitem__("bytes", True), id="bool"),
        pytest.param(lambda row: row.__setitem__("bytes", -1), id="negative"),
    ],
)
def test_archive_gate_rejects_invalid_manifest_file_bytes(tmp_path, mutate_bytes):
    run = tman.build_run(tmp_path, "FILE-BYTES-INVALID", archive="COMPLETE")
    info = _write_bound_archive(run)

    assert og.archive_status(run)["status"] == "COMPLETE", "baseline must be complete"

    product = json.loads(info["manifestPath"].read_text(encoding="utf-8"))
    mutate_bytes(product["files"][0])
    info["manifestPath"].write_text(
        json.dumps(product, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _rebind_product_manifest(run, info["manifestPath"])

    state = og.archive_status(run)
    assert state["status"] == "INCOMPLETE"
    assert ".bytes must be a non-negative integer" in state["reason"]


def test_archive_gate_rejects_manifest_file_bytes_mismatch(tmp_path):
    run = tman.build_run(tmp_path, "FILE-BYTES-MISMATCH", archive="COMPLETE")
    info = _write_bound_archive(run)

    assert og.archive_status(run)["status"] == "COMPLETE", "baseline must be complete"

    product = json.loads(info["manifestPath"].read_text(encoding="utf-8"))
    product["files"][0]["bytes"] += 1
    info["manifestPath"].write_text(
        json.dumps(product, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _rebind_product_manifest(run, info["manifestPath"])

    state = og.archive_status(run)
    assert state["status"] == "INCOMPLETE"
    assert ".bytes mismatch" in state["reason"]


def test_archive_gate_rejects_manifest_file_hash_mismatch(tmp_path):
    run = tman.build_run(tmp_path, "FILE-SHA", archive="COMPLETE")
    info = _write_bound_archive(run)
    (info["runArchive"] / "RECORD.md").write_text("tampered bytes\n", encoding="utf-8")

    state = og.archive_status(run)
    assert state["status"] == "INCOMPLETE"
    assert "sha256 mismatch" in state["reason"]


def test_archive_gate_rejects_manifest_file_that_is_not_real(tmp_path):
    run = tman.build_run(tmp_path, "FILE-MISSING", archive="COMPLETE")
    info = _write_bound_archive(run)
    (info["runArchive"] / "RECORD.md").unlink()

    state = og.archive_status(run)
    assert state["status"] == "INCOMPLETE"
    assert "does not name a real file" in state["reason"]


def test_archive_gate_rejects_manifest_file_outside_machine_root(tmp_path):
    run = tman.build_run(tmp_path, "FILE-ESCAPE", archive="COMPLETE")

    def mutate(product, run_archive, machine_root):
        outside = machine_root.parent / "escape.txt"
        outside.write_text("outside the machine root\n", encoding="utf-8")
        raw = outside.read_bytes()
        product["files"].append(
            {"path": "../../../escape.txt", "bytes": len(raw), "sha256": _archive_sha(raw)}
        )

    _write_bound_archive(run, product_mutator=mutate)
    state = og.archive_status(run)
    assert state["status"] == "INCOMPLETE"
    assert "escapes the archive machine root" in state["reason"]


def test_archive_gate_accepts_session_files_inside_machine_root(tmp_path):
    run = tman.build_run(tmp_path, "SESSION-INSIDE", archive="COMPLETE")

    def mutate(product, _run_archive, machine_root):
        session = machine_root / "sessions" / "sess-1" / "transcript.jsonl"
        session.parent.mkdir(parents=True, exist_ok=True)
        session.write_text("session bytes\n", encoding="utf-8")
        raw = session.read_bytes()
        product["files"].append(
            {
                "path": "../../sessions/sess-1/transcript.jsonl",
                "bytes": len(raw),
                "sha256": _archive_sha(raw),
                "scope": "session",
            }
        )

    _write_bound_archive(run, product_mutator=mutate)
    state = og.archive_status(run)
    assert state["status"] == "COMPLETE", state


def test_archive_gate_rejects_missing_sha256sums(tmp_path):
    run = tman.build_run(tmp_path, "NO-SUMS", archive="COMPLETE")
    _write_bound_archive(run, write_sums=False)

    state = og.archive_status(run)
    assert state["status"] == "INCOMPLETE"
    assert "SHA256SUMS missing" in state["reason"]


def test_archive_gate_rejects_malformed_sha256sums(tmp_path):
    run = tman.build_run(tmp_path, "BAD-SUMS", archive="COMPLETE")
    _write_bound_archive(run, sums_lines_override=["not a checksum line"])

    state = og.archive_status(run)
    assert state["status"] == "INCOMPLETE"
    assert "SHA256SUMS line 1" in state["reason"]


def test_archive_gate_rejects_sha256sums_hash_mismatch(tmp_path):
    run = tman.build_run(tmp_path, "SUMS-SHA", archive="COMPLETE")
    _write_bound_archive(
        run,
        sums_lines_override=lambda _product, _archive: [f"{'0' * 64}  RECORD.md"],
    )

    state = og.archive_status(run)
    assert state["status"] == "INCOMPLETE"
    assert "SHA256SUMS line 1 sha256 mismatch" in state["reason"]


def test_archive_gate_requires_sums_to_cover_every_manifest_file(tmp_path):
    run = tman.build_run(tmp_path, "SUMS-COVER", archive="COMPLETE")
    _write_bound_archive(run, sums_lines_override=[])

    state = og.archive_status(run)
    assert state["status"] == "INCOMPLETE"
    assert "SHA256SUMS does not cover product manifest file" in state["reason"]


def test_archive_gate_rejects_extra_sums_file_that_is_missing(tmp_path):
    run = tman.build_run(tmp_path, "SUMS-EXTRA", archive="COMPLETE")

    def lines(product, _archive):
        default = [
            f"{row['sha256']}  {row['path']}"
            for row in product["files"]
            if isinstance(row, dict)
        ]
        return default + [f"{'0' * 64}  extra-missing.txt"]

    _write_bound_archive(run, sums_lines_override=lines)
    state = og.archive_status(run)
    assert state["status"] == "INCOMPLETE"
    assert "does not name a real file" in state["reason"]


# ------------------------------------------------------------------ retire gate
def test_retire_requires_a_complete_archive():
    incomplete = og.retire_gate({"retire": {"requested": True, "logicalId": "at-main"}},
                                {"status": "INCOMPLETE"})
    assert incomplete["ok"] is False
    assert incomplete["code"] == "retire_requires_archive"

    complete = og.retire_gate({"retire": {"requested": True, "logicalId": "at-main"}},
                              {"status": "COMPLETE"})
    assert complete["ok"] is True


def test_no_retire_request_never_blocks():
    assert og.retire_gate({}, {"status": "MISSING"})["ok"] is True
    assert og.retire_gate(None, {"status": "MISSING"})["ok"] is True


# ------------------------------------------------------------------ compaction matrix
@pytest.mark.parametrize("runtime,managed", [("claude-code", True), ("claude", True),
                                             ("opencode", False), ("dsh", False),
                                             ("codex", False), ("", False)])
def test_only_claude_code_claims_managed_compaction(runtime, managed):
    verdict = og.compact_verdict(runtime, requested=True)
    assert verdict["managed"] is managed
    assert verdict["ok"] is managed
    if not managed:
        assert verdict["code"] == "compact_not_managed"


def test_a_compaction_request_never_implies_a_teardown():
    """compact != teardown: the verdict is a capability statement with no actions."""
    for runtime in ("claude-code", "opencode"):
        verdict = og.compact_verdict(runtime, requested=True)
        # Structural, not substring: a capability verdict carries no action/teardown field.
        assert set(verdict) == {"managed", "ok", "code", "runtime", "reason"}
        assert not any(key in verdict for key in ("action", "teardown", "stop", "kill", "retire"))


def test_compaction_is_independent_of_the_lifecycle_state():
    """A seat can be compacted and the RUN still be alive: nothing here changes status."""
    verdict = og.compact_verdict("claude-code", requested=True)
    assert verdict["ok"] is True
    assert "status" not in verdict and "state" not in verdict


def test_compaction_report_names_the_blocking_seat():
    state = {"seats": [
        {"logicalId": "at-main", "runtime": "claude-code", "compaction": {"requested": True}},
        {"logicalId": "at-qa", "runtime": "opencode", "compaction": {"requested": True}},
    ]}
    report = og.compaction_report(state)
    assert report["ok"] is False
    assert [row["logicalId"] for row in report["blocked"]] == ["at-qa"]


# ------------------------------------------------------------------ handover
def test_handover_needs_all_five_fields():
    good = {"source": "s1", "reason": "r", "previous": "p", "successor": "s2",
            "actualHandoverResult": "ok"}
    assert og.validate_handover(good)["ok"] is True

    for field in og.HANDOVER_REQUIRED:
        partial = {k: v for k, v in good.items() if k != field}
        verdict = og.validate_handover(partial)
        assert verdict["ok"] is False
        assert verdict["code"] == "handover_incomplete"
        assert verdict["missing"] == [field]


def test_no_handover_record_is_not_a_failure():
    assert og.validate_handover(None)["ok"] is True


# ------------------------------------------------------------------ port
def test_port_collision_when_something_else_answers(tmp_path):
    verdict = og.check_port(7433, tmp_path, state=None, in_use=lambda port: True)
    assert verdict["ok"] is False
    assert verdict["code"] == "port_collision"


def test_port_free_when_nothing_answers(tmp_path):
    verdict = og.check_port(7433, tmp_path, state=None, in_use=lambda port: False)
    assert verdict["ok"] is True and verdict["code"] is None


def test_fixture_port_claims_are_honoured(tmp_path):
    assert og.check_port(7433, tmp_path, state={"ports": {"7433": "foreign"}})["code"] == "port_collision"
    assert og.check_port(7433, tmp_path, state={"ports": {"7433": "owned"}})["ok"] is True
    assert og.check_port(7433, tmp_path, state={"ports": {"7433": "free"}})["ok"] is True


# ------------------------------------------------------------------ orphans
def test_orphans_are_reported_never_killed():
    verdict = og.orphan_report({"seats": [
        {"logicalId": "at-main", "session": "present"},
        {"logicalId": "at-tdo", "session": "absent"},
    ]})
    assert verdict["ok"] is False
    assert verdict["code"] == "orphan_after_stop"
    assert [row["logicalId"] for row in verdict["orphans"]] == ["at-main"]
    assert "no kill" in verdict["action"]


def test_clean_stop_has_no_orphans():
    assert og.orphan_report({"seats": [{"logicalId": "a", "session": "absent"}]})["ok"] is True


# ------------------------------------------------------------------ CLI rows (FI-13..17)
def _fixture(name, tmp_path, monkeypatch):
    root = tmp_path / "fixtures"
    monkeypatch.setenv(tman.FIXTURE_ROOT_ENV, str(root))
    tman.provision(root)
    run = root / name
    _bind_existing_complete_fixture(run)
    return run


def test_gate01_stop_reports_orphans_rc1(tmp_path, monkeypatch, capsys):
    run = _fixture("FI-13", tmp_path, monkeypatch)
    rc = orr.main(["stop", "--run-dir", str(run), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["error"]["code"] == "orphan_after_stop"
    # Nothing was killed or deleted: the down step ran and the seat is still there.
    calls = [json.loads(line)["argv"] for line in
             (run / "fake-rig.log").read_text().splitlines() if line.strip()]
    assert calls[0][:1] == ["down"]
    assert not any("kill" in " ".join(argv) for argv in calls)


def test_gate02_start_refuses_a_foreign_port(tmp_path, monkeypatch, capsys):
    run = _fixture("FI-14", tmp_path, monkeypatch)
    rc = orr.main(["start", "--run-dir", str(run), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert payload["error"]["code"] == "port_collision"
    assert not (run / "fake-rig.log").exists(), "a port refusal must spawn nothing"


def test_gate03_status_refuses_an_unmanaged_compact_claim(tmp_path, monkeypatch, capsys):
    run = _fixture("FI-15", tmp_path, monkeypatch)
    rc = orr.main(["status", "--run-dir", str(run), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert payload["error"]["code"] == "compact_not_managed"
    assert payload["gates"]["compaction"]["blocked"][0]["logicalId"] == "at-main"


def test_gate04_status_accepts_a_complete_handover(tmp_path, monkeypatch, capsys):
    run = _fixture("FI-16", tmp_path, monkeypatch)
    rc = orr.main(["status", "--run-dir", str(run), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0, payload.get("error")
    assert payload["gates"]["handover"]["ok"] is True
    assert payload["gates"]["handover"]["record"]["successor"] == "main@new"


def test_gate05_stop_refuses_retire_without_archive(tmp_path, monkeypatch, capsys):
    run = _fixture("FI-17", tmp_path, monkeypatch)
    rc = orr.main(["stop", "--run-dir", str(run), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert payload["error"]["code"] == "retire_requires_archive"
    assert not (run / "fake-rig.log").exists(), "retire refusal precedes every rig call"


# ------------------------------------------------------------------ io rows (FI-11/12)
def test_io01_start_writes_a_complete_manifest(tmp_path, monkeypatch, capsys):
    run = _fixture("FI-11", tmp_path, monkeypatch)
    rc = orr.main(["start", "--run-dir", str(run), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0, payload.get("error")

    manifest = json.loads((run / "reports" / "evidence" / "manifest" / "run-manifest.json").read_text())
    assert set(["schemaVersion", "manifestId", "runId", "launchId", "revision", "runContext",
                "envKeys", "inputs", "steps", "seats", "workflow", "archive", "outputs",
                "status"]) <= set(manifest)
    assert manifest["status"] == "active"
    assert manifest["steps"], "a successful start records its steps"
    for step in manifest["steps"]:
        assert step["startedAt"] and step["endedAt"]
        assert step["redacted"] is True


def test_io02_failed_start_writes_a_partial_manifest(tmp_path, monkeypatch, capsys):
    run = _fixture("FI-12", tmp_path, monkeypatch)
    rc = orr.main(["start", "--run-dir", str(run), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["error"]["code"] == "up_failed"

    partial_path = run / "reports" / "evidence" / "manifest" / "run-manifest.partial.json"
    partial = json.loads(partial_path.read_text())
    assert partial["partial"] is True
    assert partial["failure"]["rc"] == 1
    assert partial["failure"]["stdoutSha256"]
    assert partial["failure"]["unexecutedSteps"], "the steps that never ran must be named"
    assert "workflow-instantiate" in partial["failure"]["unexecutedSteps"]


def test_io05_second_start_refuses_with_run_exists(tmp_path, monkeypatch, capsys):
    run = _fixture("FI-11", tmp_path, monkeypatch)
    assert orr.main(["start", "--run-dir", str(run), "--json"]) == 0
    capsys.readouterr()

    rc = orr.main(["start", "--run-dir", str(run), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["error"]["code"] == "run_exists"
    assert payload["error"]["operationId"], "the retry must be able to reuse the operation id"


# ------------------------------------------------------------------ mutation controls
# A control is only worth having if REMOVING the guard makes the case go red. Each test
# below disables one boundary and asserts the row's expected code/rc changes, which is
# what proves the negative rows above are load-bearing rather than decorative.

def test_mutation_retire_gate_removed_falls_through_to_archive(tmp_path, monkeypatch, capsys):
    """Disable the retire gate: FI-17 must then fail on the ARCHIVE gate, not retire."""
    run = _fixture("FI-17", tmp_path, monkeypatch)
    monkeypatch.setattr(og, "retire_gate", lambda state, archive: {"ok": True, "code": None, "requested": True})
    rc = orr.main(["stop", "--run-dir", str(run), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert payload["error"]["code"] == "archive_incomplete", "with retire disabled the NEXT gate must catch it"
    assert payload["error"]["code"] != "retire_requires_archive", "the row would flip code -> control is live"


def test_mutation_archive_gate_weakened_lets_teardown_start(tmp_path, monkeypatch, capsys):
    """Make the archive gate accept anything: the stop now proceeds to a real rig call,
    so AT-GATE-05/CT-10 (rc2 archive_incomplete) would flip.

    S10 D-007: `stop` reaches the ONE reader through
    `openrig_continuity.archive_status` (a pure delegate), so weakening that name removes
    the guard from the executed path — which is exactly the control this row needs.
    """
    import openrig_continuity as oc
    run = _fixture("FI-17", tmp_path, monkeypatch)
    monkeypatch.setattr(
        oc, "archive_status", lambda run_dir: {"status": "COMPLETE", "path": "x", "reason": ""}
    )
    monkeypatch.setattr(og, "retire_gate", lambda state, archive: {"ok": True, "code": None, "requested": True})
    rc = orr.main(["stop", "--run-dir", str(run), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc != 2 or payload.get("error", {}).get("code") != "archive_incomplete"
    assert (run / "fake-rig.log").exists(), "the weakened gate let a rig call through"


def test_mutation_compact_matrix_accepting_everything_flips_gate03(tmp_path, monkeypatch, capsys):
    """Let any runtime claim managed compaction: GATE-03's rc2 compact_not_managed flips."""
    run = _fixture("FI-15", tmp_path, monkeypatch)
    monkeypatch.setattr(
        og, "compaction_report",
        lambda state: {"ok": True, "code": None, "seats": [], "blocked": []},
    )
    rc = orr.main(["status", "--run-dir", str(run), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0, "without the matrix the claim is accepted -> the negative row flips"
    assert payload.get("error") is None


def test_mutation_orphan_report_ignoring_orphans_flips_gate01(tmp_path, monkeypatch, capsys):
    """Ignore orphans after down: GATE-01's rc1 orphan_after_stop flips to success.

    `stop` uses CONTINUITY's orphan scan, so the control must disable that one.
    """
    import openrig_continuity as oc
    run = _fixture("FI-13", tmp_path, monkeypatch)
    monkeypatch.setattr(oc, "_orphans_after", lambda state: [])
    rc = orr.main(["stop", "--run-dir", str(run), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0, "an ignoring report turns a reported orphan into a clean stop"


def test_mutation_handover_validator_disabled_flips_gate04(tmp_path, monkeypatch, capsys):
    """Accept any handover: an incomplete record would pass, so the FIVE-field rule is live."""
    state = {"source": "s1", "reason": "r", "previous": "p", "successor": ""}
    assert og.validate_handover(state)["ok"] is False
    monkeypatch.setattr(og, "validate_handover", lambda record: {"ok": True, "code": None, "missing": []})
    assert og.validate_handover(state)["ok"] is True, "control shows the validator is load-bearing"


def test_archive_reader_is_delegated_to_the_gate(tmp_path, monkeypatch):
    """D-007 (S9-R-03): S10 removed the second archive reader.

    S9 pinned only "the two independent readers agree"; agreement is not a single source.
    Now `openrig_continuity.archive_status` has no rule of its own — it calls
    `openrig_gate.archive_status`. The proof is structural: patching the gate reader is
    visible through the continuity name.
    """
    import openrig_continuity as oc

    run = tman.build_run(tmp_path, "DELEGATED", archive="PARTIAL")
    assert oc.archive_status(run)["status"] == "PARTIAL"

    monkeypatch.setattr(
        og, "archive_status", lambda run_dir: {"status": "COMPLETE", "path": "patched", "reason": ""}
    )
    assert oc.archive_status(run)["status"] == "COMPLETE", (
        "continuity re-derived the rule instead of calling the gate reader"
    )


def test_archive_reader_refuses_everything_but_complete(tmp_path):
    """Four states + corrupt, read through the continuity name `stop` executes.

    Same decision AND the same label now (PARTIAL stays PARTIAL): the two readers can no
    longer disagree even in what they print.
    """
    import openrig_continuity as oc

    for status in ("COMPLETE", "PARTIAL", "INCOMPLETE", "MISSING"):
        run = tman.build_run(tmp_path, f"REFUSE-{status}",
                             archive=None if status == "MISSING" else status)
        if status == "COMPLETE":
            _write_bound_archive(run)
        gate = og.archive_status(run)
        delegated = oc.archive_status(run)
        assert delegated == gate, f"continuity and gate must read {status} identically"
        assert (delegated["status"] == "COMPLETE") is (status == "COMPLETE")

    corrupt = tman.build_run(tmp_path, "REFUSE-CORRUPT", archive="COMPLETE")
    (corrupt / og.ARCHIVE_MANIFEST_REL).write_text("{not json", encoding="utf-8")
    assert oc.archive_status(corrupt)["status"] == "INCOMPLETE"
    assert og.archive_gate(corrupt)["ok"] is False


@pytest.mark.parametrize("archive", ["PARTIAL", "INCOMPLETE", None, "CORRUPT"])
def test_stop_still_refuses_any_incomplete_archive(tmp_path, monkeypatch, capsys, archive):
    """`stop` keeps its rule: only COMPLETE is torn down (AT-S10-ARC-01)."""
    import openrig_continuity as oc  # noqa: F401  (import proves the delegation path loads)

    run = tman.build_run(tmp_path, f"STOP-{str(archive).upper()}", archive=archive)
    if archive == "CORRUPT":
        (run / og.ARCHIVE_MANIFEST_REL).write_text("{not json", encoding="utf-8")

    rc = orr.main(["stop", "--run-dir", str(run), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert payload["error"]["code"] == "archive_incomplete"
    assert not (run / "fake-rig.log").exists(), "an unproven archive must not start a teardown"


@pytest.mark.parametrize("session,expect_ids", [
    ("present", ["at-main"]),
    ("detached", ["at-main"]),
    ("exited", []),
    ("absent", []),
])
def test_orphan_scan_equivalence(session, expect_ids):
    """Per-state equivalence of the delegated scan (AT-S10-ARC-01)."""
    import openrig_continuity as oc

    state = {"seats": [{"logicalId": "at-main", "canonicalSessionName": "main@fixture",
                        "session": session}]}
    gate_ids = [row["logicalId"] for row in og.orphan_report(state)["orphans"]]
    continuity_ids = oc._orphans_after(state)

    assert sorted(gate_ids) == sorted(continuity_ids), "the two scans must name the same seats"
    assert sorted(continuity_ids) == sorted(expect_ids)


def test_orphan_scan_delegates_to_the_gate(monkeypatch):
    """D-007: `stop`'s scan IS `og.orphan_report`; a local copy would ignore the patch."""
    import openrig_continuity as oc

    monkeypatch.setattr(
        og, "orphan_report",
        lambda state: {"ok": False, "code": "orphan_after_stop",
                       "orphans": [{"logicalId": "from-gate"}], "action": "reported"},
    )
    assert oc._orphans_after({"seats": [{"logicalId": "ignored", "session": "present"}]}) == ["from-gate"]
