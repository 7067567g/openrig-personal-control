#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""openrig_gate.py — archive / orphan / port / compaction / handover / retire (S9 Wave B).

Contract: `runs/openrig-completion-round-20261116/reports/CONTINUITY-AND-COMPACTION.md`
§2 (runtime × action matrix), §5 (compaction / handover / retire), §4.3 (stop).

Four boundaries, each of which exists because the alternative is irreversible:

  * ARCHIVE BEFORE TEARDOWN — an unproven archive is not a complete one, so `stop`
    refuses and nothing is torn down (`archive_incomplete`). "Tear down, then archive"
    is the failure this gate makes impossible (HF-048).
  * RETIRE BEFORE ARCHIVE — retiring a seat is even less reversible than stopping a run,
    so a retire request additionally requires COMPLETE (`retire_requires_archive`).
  * COMPACTION IS NOT TEARDOWN, AND IS NOT UNIVERSAL — only a Claude Code seat can claim
    OpenRig-managed compaction; opencode/dsh/codex must say so instead of pretending
    (`compact_not_managed`). A compact never implies a teardown and vice versa.
  * ORPHANS ARE REPORTED, NEVER KILLED — a `stop` that leaves a seat alive returns
    `orphan_after_stop` (rc 1) and reports it; it never escalates to kill -9, and it
    never deletes the home, the DB or a transcript.

Port ownership is checked before a start: a port held by a process that is not this
run's home is a refusal (`port_collision`), not a reason to retry on another port
silently.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import socket
from pathlib import Path

CODE_ARCHIVE_INCOMPLETE = "archive_incomplete"
CODE_RETIRE_REQUIRES_ARCHIVE = "retire_requires_archive"
CODE_ORPHAN_AFTER_STOP = "orphan_after_stop"
CODE_PORT_COLLISION = "port_collision"
CODE_COMPACT_NOT_MANAGED = "compact_not_managed"
CODE_HANDOVER_INCOMPLETE = "handover_incomplete"

# §2 runtime × action matrix: managed in-place compaction is a Claude Code capability.
COMPACT_MANAGED_RUNTIMES = ("claude-code", "claude")

# §5.2 handover must record all five, or the successor's history is unverifiable.
HANDOVER_REQUIRED = ("source", "reason", "previous", "successor", "actualHandoverResult")

ARCHIVE_MANIFEST_REL = Path("reports") / "evidence" / "archive" / "ARCHIVE-MANIFEST.json"


# ------------------------------------------------------------------ archive
ARCHIVE_REQUIRED_MEMBERS = (
    "runSnapshot",
    "sessionSnapshots",
    "transcriptCapture",
    "openrigState",
    "homeSnapshot",
)
HEX64_RE = re.compile(r"^[0-9a-fA-F]{64}$")
SHA256SUMS_RE = re.compile(r"^([0-9a-fA-F]{64})  (.+)$")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(Path(path).read_bytes())


def _read_json_object(path: Path, label: str, errors: list[str]) -> dict | None:
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        errors.append(f"{label} unreadable: {path}: {exc}")
        return None
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label} is not valid UTF-8 JSON: {path}: {exc}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{label} root must be a JSON object; got {type(value).__name__}")
        return None
    return value


def _normalise_rel(raw: object, label: str, errors: list[str]) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        errors.append(f"{label} must be a non-empty string path")
        return None
    if "\x00" in raw:
        errors.append(f"{label} contains a NUL byte")
        return None
    path = Path(raw)
    if path.is_absolute():
        errors.append(f"{label} must be relative to the archive, got absolute path {raw!r}")
        return None
    # Lexically normalise so MANIFEST.files and SHA256SUMS compare the same way.
    rel = os.path.normpath(raw).replace(os.sep, "/")
    if rel in ("", "."):
        errors.append(f"{label} must name a file")
        return None
    return rel


def _confined_file(
    base: Path,
    rel: str,
    label: str,
    errors: list[str],
    *,
    machine_root: Path,
) -> Path | None:
    try:
        base_resolved = Path(base).resolve()
        machine_root_resolved = Path(machine_root).resolve()
        candidate = (base_resolved / rel).resolve()
    except (OSError, RuntimeError) as exc:
        errors.append(f"{label} cannot be resolved: {rel!r}: {exc}")
        return None
    if candidate != machine_root_resolved and not candidate.is_relative_to(machine_root_resolved):
        errors.append(
            f"{label} escapes the archive machine root: {rel!r} -> {str(candidate)!r}"
        )
        return None
    if not candidate.is_file():
        errors.append(f"{label} does not name a real file: {rel!r}")
        return None
    return candidate


def _validate_archive_files(
    product: dict,
    *,
    manifest_path: Path,
    machine_root: Path,
    errors: list[str],
) -> None:
    archive_dir = manifest_path.parent
    files = product.get("files")
    if not isinstance(files, list):
        errors.append("product manifest files must be a list")
        return
    if not files:
        errors.append("product manifest files must not be empty for a COMPLETE archive")
        return

    manifest_files: dict[str, str] = {}
    for index, row in enumerate(files):
        label = f"product manifest files[{index}]"
        if not isinstance(row, dict):
            errors.append(f"{label} must be a JSON object")
            continue
        rel = _normalise_rel(row.get("path"), f"{label}.path", errors)
        declared_sha = row.get("sha256")
        if not isinstance(declared_sha, str) or HEX64_RE.fullmatch(declared_sha) is None:
            errors.append(f"{label}.sha256 must be a 64-hex sha256; got {declared_sha!r}")
            declared_sha = None
        if rel is None:
            continue
        if rel in manifest_files:
            errors.append(f"product manifest files contains duplicate path {rel!r}")
            continue
        candidate = _confined_file(
            archive_dir, rel, f"{label}.path", errors, machine_root=machine_root
        )
        if candidate is None:
            continue
        actual_sha = _sha256_file(candidate)
        if declared_sha is not None and actual_sha.lower() != declared_sha.lower():
            errors.append(
                f"{label}.sha256 mismatch for {rel!r}: declared {declared_sha}, actual {actual_sha}"
            )
        bytes_declared = row.get("bytes")
        if (
            not isinstance(bytes_declared, int)
            or isinstance(bytes_declared, bool)
            or bytes_declared < 0
        ):
            errors.append(
                f"{label}.bytes must be a non-negative integer; got {bytes_declared!r}"
            )
        else:
            actual_bytes = candidate.stat().st_size
            if bytes_declared != actual_bytes:
                errors.append(
                    f"{label}.bytes mismatch for {rel!r}: declared {bytes_declared}, actual {actual_bytes}"
                )
        if declared_sha is not None:
            manifest_files[rel] = declared_sha.lower()

    sums_path = archive_dir / "SHA256SUMS"
    if not sums_path.is_file():
        errors.append(f"SHA256SUMS missing beside product manifest: {sums_path}")
        return
    try:
        sums_text = sums_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"SHA256SUMS unreadable: {sums_path}: {exc}")
        return

    sums_files: dict[str, str] = {}
    for line_number, line in enumerate(sums_text.splitlines(), start=1):
        if not line.strip():
            continue
        match = SHA256SUMS_RE.fullmatch(line)
        if match is None:
            errors.append(
                f"SHA256SUMS line {line_number} is not '<64-hex sha256>  <relative path>': {line!r}"
            )
            continue
        declared_sha, raw_rel = match.group(1), match.group(2)
        rel = _normalise_rel(raw_rel, f"SHA256SUMS line {line_number} path", errors)
        if rel is None:
            continue
        if rel in sums_files:
            errors.append(f"SHA256SUMS contains duplicate path {rel!r}")
            continue
        candidate = _confined_file(
            archive_dir, rel, f"SHA256SUMS line {line_number} path", errors,
            machine_root=machine_root,
        )
        if candidate is None:
            continue
        actual_sha = _sha256_file(candidate)
        if actual_sha.lower() != declared_sha.lower():
            errors.append(
                f"SHA256SUMS line {line_number} sha256 mismatch for {rel!r}: "
                f"declared {declared_sha}, actual {actual_sha}"
            )
        sums_files[rel] = declared_sha.lower()

    for rel, declared_sha in sorted(manifest_files.items()):
        if rel not in sums_files:
            errors.append(f"SHA256SUMS does not cover product manifest file {rel!r}")
        elif sums_files[rel] != declared_sha:
            errors.append(
                f"SHA256SUMS digest disagrees with product manifest for {rel!r}: "
                f"manifest {declared_sha}, sums {sums_files[rel]}"
            )


def _validate_complete_binding(run_dir: Path, binding_path: Path, binding: dict) -> list[str]:
    """Validate the run-local binding and the product archive it claims to bind.

    Every problem is returned as a string; the caller converts any non-empty list into
    INCOMPLETE.  This function must not raise for manifest *content* problems.
    """
    errors: list[str] = []
    run_dir = Path(run_dir)

    if "schemaVersion" in binding:
        schema = binding.get("schemaVersion")
        if schema != 1 or isinstance(schema, bool):
            errors.append(f"binding schemaVersion must be 1; got {schema!r}")

    run_id = binding.get("runId")
    if not isinstance(run_id, str) or not run_id.strip():
        errors.append("binding runId must be a non-empty string")
        run_id = None

    bridge_path = run_dir / "openrig" / "OPENRIG-BRIDGE.json"
    bridge = _read_json_object(bridge_path, "OPENRIG-BRIDGE.json", errors)
    bridge_run_id = None
    if bridge is not None:
        bridge_run_id = bridge.get("runId")
        if not isinstance(bridge_run_id, str) or not bridge_run_id.strip():
            errors.append("bridge runId must be a non-empty string")
            bridge_run_id = None
        elif run_id is not None and bridge_run_id != run_id:
            errors.append(
                f"binding runId {run_id!r} does not match bridge runId {bridge_run_id!r}"
            )

    raw_manifest_path = binding.get("manifestPath")
    manifest_path: Path | None = None
    if not isinstance(raw_manifest_path, str) or not raw_manifest_path.strip():
        errors.append("binding manifestPath must be a non-empty string")
    else:
        candidate = Path(raw_manifest_path).expanduser()
        if not candidate.is_absolute():
            candidate = run_dir / candidate
        try:
            candidate = candidate.resolve()
        except (OSError, RuntimeError) as exc:
            errors.append(f"binding manifestPath cannot be resolved: {raw_manifest_path!r}: {exc}")
        else:
            if not candidate.is_file():
                errors.append(f"binding manifestPath is not a real file: {raw_manifest_path!r}")
            else:
                manifest_path = candidate

    declared_sha = binding.get("manifestSha256")
    if not isinstance(declared_sha, str) or HEX64_RE.fullmatch(declared_sha) is None:
        errors.append(f"binding manifestSha256 must be 64-hex; got {declared_sha!r}")
        declared_sha = None

    if manifest_path is None:
        return errors

    actual_manifest_sha = _sha256_file(manifest_path)
    if declared_sha is not None and declared_sha.lower() != actual_manifest_sha:
        errors.append(
            "binding manifestSha256 does not match product MANIFEST.json bytes: "
            f"declared {declared_sha}, actual {actual_manifest_sha}"
        )

    run_archive_dir = manifest_path.parent
    machine_root = run_archive_dir.parent.parent
    if manifest_path.name != "MANIFEST.json":
        errors.append(
            "product manifestPath must name MANIFEST.json; "
            f"got {manifest_path.name!r}"
        )
    if run_archive_dir.parent.name != "runs":
        errors.append(
            "product manifestPath must be under <machine-root>/runs/<runId>/MANIFEST.json; "
            f"got {manifest_path}"
        )
    elif run_id is not None and run_archive_dir.name != run_id:
        errors.append(
            f"product manifest directory {run_archive_dir.name!r} does not "
            f"match binding runId {run_id!r}"
        )
    product = _read_json_object(manifest_path, "product MANIFEST.json", errors)
    if product is None:
        return errors

    product_run_id = product.get("runId")
    if not isinstance(product_run_id, str) or not product_run_id.strip():
        errors.append("product manifest runId must be a non-empty string")
    else:
        if run_id is not None and product_run_id != run_id:
            errors.append(
                f"product manifest runId {product_run_id!r} does not match binding runId {run_id!r}"
            )
        if bridge_run_id is not None and product_run_id != bridge_run_id:
            errors.append(
                f"product manifest runId {product_run_id!r} does not match bridge runId {bridge_run_id!r}"
            )
        if run_archive_dir.name != product_run_id:
            errors.append(
                f"product manifest runId {product_run_id!r} does not match "
                f"its parent directory {run_archive_dir.name!r}"
            )

    present_statuses: list[tuple[str, str]] = []
    for key in ("archiveStatus", "status"):
        if key in product:
            value = product.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"product manifest {key} must be a non-empty string")
            else:
                present_statuses.append((key, value.strip().upper()))
    if not present_statuses:
        errors.append("product manifest archiveStatus/status is missing")
    for key, value in present_statuses:
        if value != "COMPLETE":
            errors.append(f"product manifest {key} must be COMPLETE; got {value!r}")
    if len(present_statuses) == 2 and present_statuses[0][1] != present_statuses[1][1]:
        errors.append(
            "product manifest archiveStatus and status disagree: "
            f"{present_statuses[0][1]!r} vs {present_statuses[1][1]!r}"
        )

    required = product.get("required")
    not_applicable = product.get("notApplicable", {})
    if not isinstance(not_applicable, dict):
        errors.append("product manifest notApplicable must be a JSON object")
        not_applicable = {}
    else:
        for key, value in not_applicable.items():
            if value is not True:
                errors.append(
                    f"product manifest notApplicable.{key} must be true when present; got {value!r}"
                )
    if not isinstance(required, dict):
        errors.append("product manifest required must be a JSON object")
    else:
        for member in ARCHIVE_REQUIRED_MEMBERS:
            if member == "sessionSnapshots" and not_applicable.get(member) is True:
                continue
            if required.get(member) is not True:
                suffix = ""
                if member == "sessionSnapshots":
                    suffix = " (or set notApplicable.sessionSnapshots=true)"
                errors.append(f"product manifest required.{member} must be true{suffix}")

    missing = product.get("missing")
    if not isinstance(missing, list):
        errors.append("product manifest missing must be a list")
    elif missing:
        errors.append(f"product manifest missing must be []; got {missing!r}")

    _validate_archive_files(
        product,
        manifest_path=manifest_path,
        machine_root=machine_root,
        errors=errors,
    )
    return errors


def archive_status(run_dir: Path) -> dict:
    """The ONE archive-gate reader (fail-closed). `openrig_continuity.stop` uses it too.

    A COMPLETE claim is not trusted by shape: it must be bound to a real product
    archive manifest by path + sha256, and that manifest plus its files, SHA256SUMS,
    required members and machine-root confinement are validated.  Any content
    problem returns INCOMPLETE with a reason; this function never raises for a
    valid-but-wrong JSON root.
    """
    path = Path(run_dir) / ARCHIVE_MANIFEST_REL
    if not path.is_file():
        return {"status": "MISSING", "path": str(path), "reason": "no archive manifest"}
    try:
        raw = path.read_bytes()
    except Exception as exc:  # noqa: BLE001 - unreadable is an INCOMPLETE observation
        return {"status": "INCOMPLETE", "path": str(path), "reason": f"unreadable: {exc}"}
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"status": "INCOMPLETE", "path": str(path), "reason": f"unreadable: {exc}"}

    if not isinstance(data, dict):
        return {
            "status": "INCOMPLETE",
            "path": str(path),
            "reason": (
                "archive manifest root must be a JSON object; "
                f"got {type(data).__name__}"
            ),
        }

    raw_status = data.get("status")
    status = raw_status.strip().upper() if isinstance(raw_status, str) else ""
    reason_value = data.get("reason")
    reason = reason_value.strip() if isinstance(reason_value, str) else ""
    if status not in ("COMPLETE", "PARTIAL", "INCOMPLETE", "MISSING"):
        return {
            "status": "INCOMPLETE",
            "path": str(path),
            "reason": f"unsupported archive status {raw_status!r}",
        }
    if status != "COMPLETE":
        return {"status": status, "path": str(path), "reason": reason}

    try:
        errors = _validate_complete_binding(Path(run_dir), path, data)
    except Exception as exc:  # noqa: BLE001 - fail closed, never crash a valid manifest
        errors = [f"archive binding validation crashed: {type(exc).__name__}: {exc}"]
    if errors:
        detail = "; ".join(errors)
        return {
            "status": "INCOMPLETE",
            "path": str(path),
            "reason": f"complete binding invalid: {detail}",
            "bindingErrors": errors,
        }
    return {
        "status": "COMPLETE",
        "path": str(path),
        "reason": reason or "complete binding verified",
    }


def archive_gate(run_dir: Path) -> dict:
    state = archive_status(run_dir)
    ok = state["status"] == "COMPLETE"
    return {
        "ok": ok,
        "code": None if ok else CODE_ARCHIVE_INCOMPLETE,
        "status": state["status"],
        "path": state["path"],
        "reason": "" if ok else (
            f"archive status is {state['status']}"
            + (f": {state.get('reason')}" if state.get("reason") else "")
        ),
    }


def retire_gate(state: dict | None, archive: dict) -> dict:
    """A retire request is only admissible on a COMPLETE archive (§5.3)."""
    retire = (state or {}).get("retire") or {}
    requested = bool(retire.get("requested"))
    if not requested:
        return {"ok": True, "code": None, "requested": False}
    if archive.get("status") != "COMPLETE":
        return {
            "ok": False,
            "code": CODE_RETIRE_REQUIRES_ARCHIVE,
            "requested": True,
            "reason": (
                f"retire requested for {retire.get('logicalId') or 'a seat'} but archive "
                f"status is {archive.get('status')}; retire is not reversible and requires COMPLETE"
            ),
        }
    return {"ok": True, "code": None, "requested": True}


# ------------------------------------------------------------------ compaction
def compact_verdict(runtime: str | None, *, requested: bool) -> dict:
    """§2/§5.1: only Claude Code may claim OpenRig-managed in-place compaction."""
    runtime = (runtime or "").strip().lower()
    if not requested:
        return {
            "managed": runtime in COMPACT_MANAGED_RUNTIMES,
            "ok": True,
            "code": None,
            "runtime": runtime,
            "reason": "no compaction requested",
        }
    if runtime in COMPACT_MANAGED_RUNTIMES:
        return {
            "managed": True,
            "ok": True,
            "code": None,
            "runtime": runtime,
            "reason": "Claude Code supports OpenRig-managed in-place compaction",
        }
    return {
        "managed": False,
        "ok": False,
        "code": CODE_COMPACT_NOT_MANAGED,
        "runtime": runtime,
        "reason": (
            f"{runtime or 'unknown runtime'} cannot claim OpenRig-managed compaction; "
            "compact there is a runtime-native action, not a managed one (and never a teardown)"
        ),
    }


def compaction_requests(state: dict | None) -> list[dict]:
    """Per-seat compaction claims carried by the observed state."""
    out: list[dict] = []
    for seat in (state or {}).get("seats") or []:
        claim = seat.get("compaction") or {}
        out.append(
            {
                "logicalId": seat.get("logicalId"),
                "runtime": claim.get("runtime") or seat.get("runtime"),
                "requested": bool(claim.get("requested")),
            }
        )
    return out


def compaction_report(state: dict | None) -> dict:
    rows = [compact_verdict(row["runtime"], requested=row["requested"]) | {"logicalId": row["logicalId"]}
            for row in compaction_requests(state)]
    blocked = [row for row in rows if row.get("code")]
    return {
        "ok": not blocked,
        "code": CODE_COMPACT_NOT_MANAGED if blocked else None,
        "seats": rows,
        "blocked": blocked,
    }


# ------------------------------------------------------------------ handover
def validate_handover(record: dict | None) -> dict:
    """§5.2: all five fields, each non-empty, or the handover is not recordable."""
    if not record:
        return {"ok": True, "code": None, "missing": [], "note": "no handover recorded"}
    missing = [field for field in HANDOVER_REQUIRED if not record.get(field)]
    ok = not missing
    return {
        "ok": ok,
        "code": None if ok else CODE_HANDOVER_INCOMPLETE,
        "missing": missing,
        "record": {field: record.get(field) for field in HANDOVER_REQUIRED},
    }


# ------------------------------------------------------------------ ports
def _port_in_use(port: int, host: str = "127.0.0.1", timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_port(
    port: int | None,
    home: str | Path,
    *,
    state: dict | None = None,
    in_use=None,
) -> dict:
    """Refuse a port that some OTHER home holds.

    Live runs probe the socket. Fixture runs may carry `ports` in the observed-state file
    (`free` | `owned` | `foreign`) because a fixture cannot own a real listener across
    processes; the mapping is an explicit claim in the fixture, not an inference.
    """
    if port is None:
        return {"ok": True, "code": None, "port": None, "owner": "unknown",
                "reason": "no daemonPort declared in the bridge"}
    claimed = ((state or {}).get("ports") or {}).get(str(port))
    if claimed in ("free", "owned", "foreign"):
        if claimed == "foreign":
            return {
                "ok": False,
                "code": CODE_PORT_COLLISION,
                "port": int(port),
                "owner": "foreign",
                "reason": f"port {port} is held by a process that is not {home}",
            }
        return {"ok": True, "code": None, "port": int(port), "owner": claimed, "reason": "fixture claim"}
    probe = in_use or _port_in_use
    if probe(int(port)):
        return {
            "ok": False,
            "code": CODE_PORT_COLLISION,
            "port": int(port),
            "owner": "unknown",
            "reason": (
                f"port {port} already answers and this run cannot prove it owns it; "
                "inspect the listener before starting"
            ),
        }
    return {"ok": True, "code": None, "port": int(port), "owner": "free", "reason": "port free"}


# ------------------------------------------------------------------ orphans
def orphan_report(state: dict | None) -> dict:
    """Report, never kill (§4.3). A live seat after `down` is a finding, not a cleanup."""
    alive: list[dict] = []
    for seat in (state or {}).get("seats") or []:
        session = seat.get("session")
        if session in ("present", "detached"):
            alive.append(
                {
                    "logicalId": seat.get("logicalId"),
                    "canonicalSessionName": seat.get("canonicalSessionName"),
                    "session": session,
                }
            )
    return {
        "ok": not alive,
        "code": CODE_ORPHAN_AFTER_STOP if alive else None,
        "orphans": alive,
        "action": "reported only: no kill, no delete, no restart",
    }


if __name__ == "__main__":  # pragma: no cover
    print("openrig_gate is a library; openrig_run.py enforces the gates")
    raise SystemExit(2)
