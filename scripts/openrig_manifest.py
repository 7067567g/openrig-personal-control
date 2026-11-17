#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""openrig_manifest.py — RUN-MANIFEST, partial evidence, atomic writes (S9 Wave B).

Contract: `runs/openrig-completion-round-20261116/reports/IO-EVIDENCE-MANIFEST.md`
§2 (schema), §5 (write rules), §6 (observation axes).

The rules this file exists to make mechanical:

  1. Write a temp file, then rename. A failed rename leaves NO half file (§5.1).
  2. A failure writes `run-manifest.partial.json` — never stderr only (§5.3). A partial
     must name what ran, what failed, and what never ran, or it cannot be audited.
  3. `revision` increases and the OLD BYTES are preserved under `revisions/<n>.json`
     (§5.5); a correction never silently erases the state it replaced.
  4. `manifestId` survives a retry (§5.4); `launchId` is per attempt.
  5. `envKeys` carries NAMES ONLY, and every receipt records argv with secret values
     redacted (`redacted: true`) — a manifest that leaks an env value is worse than no
     manifest (§2.1/§2.4).
  6. Every duration records `startedAt` AND `endedAt`, not just the delta (§6.3).
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

try:  # POSIX
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - exercised structurally on POSIX
    _fcntl = None

try:  # Windows
    import msvcrt as _msvcrt
except ImportError:  # pragma: no cover - Linux import path
    _msvcrt = None

LOCK_TIMEOUT_SECONDS = 30.0

SCHEMA = 1


# ------------------------------------------------------------------ write errors
class ManifestWriteError(RuntimeError):
    """A lifecycle manifest write that refused to replace unverified evidence."""

    code = "manifest_write_failed"

    def __init__(self, message: str, **details: object) -> None:
        super().__init__(message)
        self.details = dict(details)


class ManifestRevisionError(ManifestWriteError):
    """The supplied revision cannot safely replace the current target."""

    code = "manifest_revision_conflict"


class ManifestPreservationError(ManifestWriteError):
    """The bytes being replaced could not be preserved under revisions/."""

    code = "manifest_revision_preservation_failed"

MANIFEST_REL = Path("reports") / "evidence" / "manifest" / "run-manifest.json"
PARTIAL_REL = Path("reports") / "evidence" / "manifest" / "run-manifest.partial.json"
REVISIONS_DIR = Path("reports") / "evidence" / "manifest" / "revisions"

# P-S10-02 — an empty evidence array must never be silent. A caller that genuinely has
# no seats/outputs writes one of these machine-readable reasons next to the empty list,
# so a reader can distinguish "nothing to report" from "the writer forgot".
SEATS_NOT_APPLICABLE_REASON = "seatsNotApplicableReason"
OUTPUTS_NOT_APPLICABLE_REASON = "outputsNotApplicableReason"
DEFAULT_SEATS_NOT_APPLICABLE_REASON = "no_seat_observation_available"
DEFAULT_OUTPUTS_NOT_APPLICABLE_REASON = "no_output_file_produced"
MAX_RECEIPT_BYTES = 256 * 1024

# The seat schema enum deliberately has no null. A ps/plan observation can still be
# missing, so the write path records that honestly as `n-a` plus provenance fields.
ACTUAL_OUTCOMES = (
    "resumed",
    "fresh-primed",
    "awaiting-decision",
    "attention_required",
    "failed",
    "ready",
    "n-a",
)
OUTCOME_NOT_OBSERVED_REASON = "outcome_not_observed"
EXPECTED_ACTIONS = (
    "resume-original",
    "fresh-primed",
    "awaiting-decision",
    "new",
    "stop",
    "n-a",
)
SESSIONS = ("present", "detached", "exited", "absent")
ACTIVITIES = ("working", "idle-at-prompt", "unknown")
EVIDENCE_LEVELS = ("oracle", "observed", "degraded")

REQUIRED_TOP_KEYS = (
    "schemaVersion",
    "manifestId",
    "runId",
    "launchId",
    "revision",
    "runContext",
    "envKeys",
    "inputs",
    "steps",
    "seats",
    "workflow",
    "archive",
    "outputs",
    "status",
)

STATUSES = ("starting", "active", "stopping", "stopped", "failed")

# Keys whose VALUES must never reach the manifest. Names are kept (§2.1).
SECRET_HINTS = ("TOKEN", "SECRET", "PASSWORD", "PASSWD", "KEY", "CREDENTIAL")

# argv flags whose value is secret-bearing, redacted positionally.
SECRET_FLAGS = ("--env", "--token", "--api-key", "--password", "--secret")


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str | None:
    try:
        return sha256_bytes(Path(path).read_bytes())
    except OSError:
        return None


# ------------------------------------------------------------------ redaction
def redact_cmd(cmd: list[str]) -> tuple[list[str], bool]:
    """Return (redacted_cmd, redacted?). Never mutates the input."""
    out: list[str] = []
    changed = False
    redact_next = False
    for token in cmd:
        if redact_next:
            out.append("<redacted>")
            changed = True
            redact_next = False
            continue
        if token in SECRET_FLAGS:
            out.append(token)
            redact_next = True
            continue
        if any(token.startswith(f"{flag}=") for flag in SECRET_FLAGS):
            flag = token.split("=", 1)[0]
            out.append(f"{flag}=<redacted>")
            changed = True
            continue
        if "=" in token:
            name = token.split("=", 1)[0]
            if any(hint in name.upper() for hint in SECRET_HINTS):
                out.append(f"{name}=<redacted>")
                changed = True
                continue
        out.append(token)
    return out, changed


def env_keys(env: dict | None) -> list[str]:
    """Names only, sorted. A value never leaves this function."""
    if not env:
        return []
    return sorted(str(name) for name in env)


# ------------------------------------------------------------------ atomic write
def _json_bytes(payload: dict) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _ensure_windows_lock_byte(fd: int) -> None:
    if os.fstat(fd).st_size == 0:
        os.write(fd, b"\0")
        os.fsync(fd)
    os.lseek(fd, 0, os.SEEK_SET)


def _acquire_windows_lock(fd: int) -> None:
    assert _msvcrt is not None
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    while True:
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            _msvcrt.locking(fd, _msvcrt.LK_NBLCK, 1)
            return
        except OSError as exc:
            if time.monotonic() >= deadline:
                raise ManifestWriteError(
                    f"timed out after {LOCK_TIMEOUT_SECONDS:g}s acquiring file lock",
                    backend="msvcrt",
                ) from exc
            time.sleep(0.05)


@contextmanager
def _path_lock(path: Path):
    """Serialize writers of one target across threads and processes.

    POSIX uses `fcntl.flock`; Windows uses a one-byte `msvcrt.locking` region. The lock
    file is intentionally persistent: unlinking a lock inode lets a third writer open
    a fresh inode while a second writer is still queued on the old one, which would
    break serialization exactly when it matters. If neither backend exists the write
    fails closed with ManifestWriteError rather than failing at module import.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f".{path.name}.lock")
    if _fcntl is None and _msvcrt is None:
        raise ManifestWriteError(
            "no portable file-locking backend is available; refusing an unserialized write",
            backend=None,
        )
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_BINARY", 0)
    fd = os.open(lock_path, flags, 0o600)
    try:
        if _fcntl is not None:
            _fcntl.flock(fd, _fcntl.LOCK_EX)
            try:
                yield lock_path
            finally:
                _fcntl.flock(fd, _fcntl.LOCK_UN)
        else:
            _ensure_windows_lock_byte(fd)
            _acquire_windows_lock(fd)
            try:
                yield lock_path
            finally:
                os.lseek(fd, 0, os.SEEK_SET)
                assert _msvcrt is not None
                _msvcrt.locking(fd, _msvcrt.LK_UNLCK, 1)
    finally:
        os.close(fd)


def _write_bytes_unlocked(
    path: Path,
    data: bytes,
    *,
    _replace=os.replace,
    mode: int | None = None,
) -> str:
    """Unique-temp write. Caller owns the path lock (if one is required)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    tmp = Path(tmp_name)
    replaced = False
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if mode is not None:
            os.chmod(tmp, int(mode))
        _replace(tmp, path)
        replaced = True
        if mode is not None:
            try:
                os.chmod(path, int(mode))
            except OSError:
                pass
        return sha256_bytes(data)
    finally:
        if not replaced:
            try:
                tmp.unlink()
            except OSError:
                pass


def write_atomic(
    path: Path, payload: dict, *, _replace=os.replace, mode: int | None = None
) -> str:
    """Locked unique-temp + rename. Returns sha256 of the bytes written.

    On a failed rename the temp file is removed and the ORIGINAL target is untouched:
    a reader must never observe a truncated manifest (§5.1).  `mode` lets private
    runtime receipts use 0600; schema/manifest callers keep the historical default.
    """
    path = Path(path)
    data = _json_bytes(payload)
    with _path_lock(path):
        return _write_bytes_unlocked(path, data, _replace=_replace, mode=mode)


def load_manifest(run_dir: Path) -> dict | None:
    path = Path(run_dir) / MANIFEST_REL
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    return data if isinstance(data, dict) else None


def load_partial(run_dir: Path) -> dict | None:
    path = Path(run_dir) / PARTIAL_REL
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    return data if isinstance(data, dict) else None


# ------------------------------------------------------------------ builder
def new_manifest(
    run_dir: Path,
    bridge: dict,
    *,
    launch_id: str,
    intent: str = "fresh",
    operation_id: str | None = None,
    env: dict | None = None,
) -> dict:
    """Skeleton with every required top-level key, plus runContext (§2.2)."""
    run_dir = Path(run_dir)
    bridge_path = run_dir / "openrig" / "OPENRIG-BRIDGE.json"
    previous = load_manifest(run_dir)
    manifest_id = (
        (previous or {}).get("manifestId")
        or operation_id
        or f"manifest-{uuid.uuid4()}"
    )
    return {
        "schemaVersion": SCHEMA,
        "manifestId": manifest_id,
        "runId": str(bridge.get("runId")),
        "launchId": launch_id,
        "intent": intent,
        "generatedAt": now_iso(),
        "revision": int((previous or {}).get("revision") or 0) + 1,
        "runContext": {
            "runDir": str(run_dir),
            "bridgePath": str(bridge_path),
            "bridgeSha256": sha256_file(bridge_path),
            "openrigHome": str(bridge.get("openrigHome") or ""),
            "daemonPort": bridge.get("daemonPort"),
            "openrigCli": str(bridge.get("openrigCli") or "rig"),
            "supervisorVersion": str(bridge.get("supervisorVersion") or "openrig_run.py"),
            "productGitSha": str(bridge.get("productGitSha") or ""),
            "workflowGroupGitSha": str(bridge.get("workflowGroupGitSha") or ""),
        },
        "envKeys": env_keys(env),
        "inputs": [],
        "steps": [],
        "seats": [],
        "workflow": {
            "instanceId": str(bridge.get("workflowInstanceId") or ""),
            "entryQitemId": str(bridge.get("entryQitemId") or ""),
            "specPath": str(bridge.get("workflowSpec") or ""),
            "specSha256": sha256_file(run_dir / "openrig" / str(bridge.get("workflowSpec") or "workflow.yaml")),
            "operationKey": str(bridge.get("operationKey") or ""),
        },
        "archive": {
            "manifestPath": str(run_dir / "reports" / "evidence" / "archive" / "ARCHIVE-MANIFEST.json"),
            "archiveStatus": "MISSING",
            "required": {},
            "checkedAt": None,
        },
        "outputs": [],
        "status": "starting",
    }


def add_input(
    manifest: dict,
    run_dir: Path,
    rel_or_path: str | Path,
    *,
    kind: str,
    required: bool = True,
    source_id: str | None = None,
) -> dict:
    """Record one input by PATH + HASH only — never by copying its body (HF-099)."""
    path = Path(rel_or_path)
    if not path.is_absolute():
        path = Path(run_dir) / path
    entry = {
        "kind": kind,
        "path": str(path),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size if path.is_file() else None,
        "required": required,
    }
    if source_id:
        entry["sourceId"] = source_id
    manifest["inputs"].append(entry)
    return manifest


def step_receipt(
    step_id: str,
    cmd: list[str],
    *,
    cwd: str,
    rc: int,
    stdout: str = "",
    stderr: str = "",
    started_at: str,
    ended_at: str,
    state_before: dict | None = None,
    state_after: dict | None = None,
    partial: bool = False,
    stdout_sha256: str | None = None,
    stderr_sha256: str | None = None,
    evidence_path: str | None = None,
) -> dict:
    """One step receipt (§2.4). argv is redacted here, not by the caller.

    P-S10-03: a bounded runtime capture already knows the digests of the FULL
    child streams.  `stdout_sha256` / `stderr_sha256` let the receipt carry those
    digests without the caller handing the full bytes back to this function.
    `evidence_path` points at the private sidecar that holds the spill paths and
    bounded tails.
    """
    redacted_cmd, redacted = redact_cmd([str(part) for part in cmd])
    return {
        "stepId": step_id,
        "cmd": redacted_cmd,
        "cwd": str(cwd),
        "startedAt": started_at,
        "endedAt": ended_at,
        "rc": int(rc),
        "stdoutSha256": stdout_sha256 or sha256_bytes((stdout or "").encode("utf-8")),
        "stderrSha256": stderr_sha256 or sha256_bytes((stderr or "").encode("utf-8")),
        "evidencePath": evidence_path,
        "stateBefore": state_before,
        "stateAfter": state_after,
        "partial": bool(partial),
        "redacted": redacted or True,
    }


def _seat_outcome_fields(seat: dict) -> tuple[str, bool, str | None]:
    """Normalize a seat outcome to the schema enum + explicit observation provenance.

    `actualOutcome` is never null in a manifest. Missing/null/unknown values become
    `n-a` with `actualOutcomeObserved=false`; an explicit `actualOutcomeObserved=false`
    from an observation mapper is preserved. Real product outcomes keep their value and
    are marked observed.
    """
    raw = seat.get("actualOutcome")
    explicit = seat.get("actualOutcomeObserved")
    reason = seat.get("actualOutcomeReason")
    if explicit is False:
        outcome = raw if raw in ACTUAL_OUTCOMES else "n-a"
        return str(outcome), False, str(reason or OUTCOME_NOT_OBSERVED_REASON)
    if raw in ACTUAL_OUTCOMES:
        return str(raw), True, None
    return "n-a", False, str(reason or OUTCOME_NOT_OBSERVED_REASON)


def add_seats(manifest: dict, seats: list[dict]) -> dict:
    """Copy the continuity plan's per-seat rows (already three-axis — §6).

    `startupStatus`/`observed`/`observationSource` are carried only when the caller
    supplied them. They let a start observation be distinguished from a continuity
    outcome without inventing an `actualOutcome` the product never sent.
    """
    out: list[dict] = []
    for seat in seats:
        actual_outcome, outcome_observed, outcome_reason = _seat_outcome_fields(seat)
        expected_action = seat.get("expectedAction")
        if expected_action not in EXPECTED_ACTIONS:
            # A pre-stop observation has no planned action; `n-a` is the honest enum
            # value and keeps the seat schema-compatible.
            expected_action = "n-a"
        row = {
            "logicalId": str(seat.get("logicalId") or ""),
            "canonicalSessionName": str(seat.get("canonicalSessionName") or ""),
            "nodeId": seat.get("nodeId"),
            "expectedAction": expected_action,
            "actualOutcome": actual_outcome,
            "actualOutcomeObserved": outcome_observed,
            "freshAuthorized": bool(seat.get("freshAuthorized")),
            "freshReason": str(seat.get("freshReason") or ""),
            "evidencePath": seat.get("evidencePath"),
            "evidenceReasons": list(seat.get("evidenceReasons") or []),
        }
        if outcome_reason is not None:
            row["actualOutcomeReason"] = outcome_reason
        # Null is not an enum member of session/activity/evidence in the S11a schema.
        # Omit an unknown axis instead of writing `None`; absence is itself the
        # observation.
        for axis, allowed in (
            ("session", SESSIONS),
            ("activity", ACTIVITIES),
            ("evidence", EVIDENCE_LEVELS),
        ):
            value = seat.get(axis)
            if value in allowed:
                row[axis] = value
        for key in (
            "startupStatus",
            "resumeTokenPresent",
            "restorePolicy",
            "outcomeMatched",
            "observed",
            "observationSource",
        ):
            if key not in seat:
                continue
            value = seat.get(key)
            if key == "resumeTokenPresent" and isinstance(value, str):
                value = value == "present"
            if key in ("outcomeMatched", "observed", "resumeTokenPresent"):
                if isinstance(value, bool):
                    row[key] = value
            elif key in ("startupStatus", "restorePolicy", "observationSource"):
                if isinstance(value, str):
                    row[key] = value
        out.append(row)
    manifest["seats"] = out
    return manifest


def add_output(
    manifest: dict,
    path: str | Path,
    *,
    producer: str,
    consumer: str,
    retention: str = "run",
) -> dict:
    """Record an EXISTING generated file by absolute path + actual sha256 + bytes.

    A missing file raises instead of producing an output entry with `sha256: null`:
    outputs are attested artifacts, not a wish list. Re-adding the same path replaces
    its old entry so a revisioned manifest cannot accumulate stale hashes.
    """
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"manifest output does not exist: {resolved}")
    digest = sha256_file(resolved)
    if not digest:
        raise OSError(f"manifest output is unreadable: {resolved}")
    entry = {
        "path": str(resolved),
        "sha256": digest,
        "bytes": resolved.stat().st_size,
        "producer": producer,
        "consumer": consumer,
        "retention": retention,
    }
    outputs = [
        old
        for old in list(manifest.get("outputs") or [])
        if str(old.get("path")) != str(resolved)
    ]
    outputs.append(entry)
    manifest["outputs"] = outputs
    return manifest


def revised_manifest(
    run_dir: Path,
    bridge: dict,
    *,
    launch_id: str,
    intent: str = "revision",
) -> dict:
    """A new revision that preserves the manifest's identity and prior evidence.

    `new_manifest()` owns revision/manifestId arithmetic; this helper adds the
    carry-forward rules resume/stop need. It never mutates the loaded previous dict.
    """
    previous = load_manifest(run_dir)
    manifest = new_manifest(
        run_dir, bridge, launch_id=launch_id, intent=intent
    )
    if not previous:
        return manifest
    for key in ("inputs", "steps", "outputs", "envKeys"):
        value = previous.get(key)
        if isinstance(value, list):
            manifest[key] = copy.deepcopy(value)
    previous_workflow = previous.get("workflow")
    if isinstance(previous_workflow, dict):
        for key, value in previous_workflow.items():
            if value not in (None, "") and manifest["workflow"].get(key) in (None, ""):
                manifest["workflow"][key] = value
    previous_archive = previous.get("archive")
    if isinstance(previous_archive, dict):
        manifest["archive"] = copy.deepcopy(previous_archive)
    return manifest


def finalize_manifest(
    manifest: dict,
    *,
    status: str | None = None,
    seats: list[dict] | None = None,
    outputs: list[dict] | None = None,
    seats_not_applicable_reason: str | None = None,
    outputs_not_applicable_reason: str | None = None,
) -> dict:
    """One write-path guard: status + seats + outputs + explicit N/A reasons.

    An empty `seats`/`outputs` always carries a reason. A non-empty list always drops
    the stale reason. Output specs are `{path, producer, consumer, retention?}` and must
    point at real files (`add_output` enforces that).
    """
    if status is not None:
        if status not in STATUSES:
            raise ValueError(f"invalid manifest status: {status!r}")
        manifest["status"] = status
    manifest.setdefault("seats", [])
    manifest.setdefault("outputs", [])
    if seats is not None:
        manifest["seats"] = list(seats)
    # Normalize even a pre-populated seats[] so a direct write cannot persist a null
    # actualOutcome or a null session enum.
    add_seats(manifest, list(manifest.get("seats") or []))
    for spec in outputs or []:
        add_output(
            manifest,
            spec["path"],
            producer=str(spec.get("producer") or "unknown"),
            consumer=str(spec.get("consumer") or "unknown"),
            retention=str(spec.get("retention") or "run"),
        )

    if not manifest.get("seats"):
        manifest[SEATS_NOT_APPLICABLE_REASON] = str(
            seats_not_applicable_reason
            or manifest.get(SEATS_NOT_APPLICABLE_REASON)
            or DEFAULT_SEATS_NOT_APPLICABLE_REASON
        )
    else:
        manifest.pop(SEATS_NOT_APPLICABLE_REASON, None)

    if not manifest.get("outputs"):
        manifest[OUTPUTS_NOT_APPLICABLE_REASON] = str(
            outputs_not_applicable_reason
            or manifest.get(OUTPUTS_NOT_APPLICABLE_REASON)
            or DEFAULT_OUTPUTS_NOT_APPLICABLE_REASON
        )
    else:
        manifest.pop(OUTPUTS_NOT_APPLICABLE_REASON, None)
    return manifest


def write_receipt(
    run_dir: Path,
    rel_or_path: str | Path,
    payload: dict,
    *,
    max_bytes: int = MAX_RECEIPT_BYTES,
) -> dict:
    """Atomically write a bounded JSON receipt and return path + sha256 + bytes."""
    path = Path(rel_or_path)
    if not path.is_absolute():
        path = Path(run_dir) / path
    data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(data) > max_bytes:
        raise ValueError(
            f"receipt {path} is {len(data)} bytes, over the {max_bytes}-byte cap"
        )
    digest = write_atomic(path, payload, mode=0o600)
    return {
        "path": str(path.resolve()),
        "sha256": digest,
        "bytes": path.stat().st_size,
    }


# ------------------------------------------------------------------ ps product mapping
PS_SESSION_UNKNOWN_REASON = "ps_session_unknown"

_PS_SESSION_STATUS = {
    "running": "present",
    "present": "present",
    "detached": "detached",
    "exited": "exited",
    "stopped": "absent",
}
_PS_ACTIVITY_STATE = {
    "running": "working",
    "working": "working",
    "idle": "idle-at-prompt",
    "needs_input": "idle-at-prompt",
    "idle-at-prompt": "idle-at-prompt",
    "unknown": "unknown",
}


class PsPayloadError(ValueError):
    """The live `rig ps --nodes --json` answer has no usable product shape."""


def ps_rows(payload) -> list[dict]:
    """Return product node rows or raise on empty/unknown-shaped payloads.

    Accepted roots are the product's bare list and the legacy object with a
    non-empty ``nodes``/``rows``/``seats`` list.  A parseable-but-empty object is
    not evidence of a zero-seat run; callers must fail closed instead.
    """
    rows = None
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        for key in ("nodes", "rows", "seats"):
            value = payload.get(key)
            if isinstance(value, list) and value:
                rows = value
                break
        if rows is None:
            raise PsPayloadError(
                "ps payload object has no non-empty nodes/rows/seats list"
            )
    else:
        raise PsPayloadError(
            f"ps payload root must be a list or object, got {type(payload).__name__}"
        )
    if not rows:
        raise PsPayloadError("ps payload contains no node rows")
    result: list[dict] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise PsPayloadError(f"ps node row {index} is not an object")
        if not row.get("logicalId") and not row.get("canonicalSessionName"):
            raise PsPayloadError(
                f"ps node row {index} has neither logicalId nor canonicalSessionName"
            )
        result.append(row)
    return result


def map_ps_session(row: dict) -> str | None:
    """Map the product's sessionStatus enum; never infer presence from runtime/pid."""
    explicit = row.get("session")
    if explicit in SESSIONS:
        return str(explicit)
    status = row.get("sessionStatus")
    if isinstance(status, str):
        return _PS_SESSION_STATUS.get(status.strip().lower())
    return None


def map_ps_activity(row: dict) -> str | None:
    """Map nested ``agentActivity.state`` onto the continuity activity enum."""
    nested = row.get("agentActivity")
    if isinstance(nested, dict):
        state = nested.get("state")
        if isinstance(state, str):
            return _PS_ACTIVITY_STATE.get(state.strip().lower())
    flat = row.get("activity")
    if flat in ACTIVITIES:
        return str(flat)
    return None


def _map_ps_token(row: dict) -> bool | None:
    token = row.get("resumeTokenPresent", row.get("tokenState"))
    if isinstance(token, bool):
        return token
    if isinstance(token, str):
        lowered = token.strip().lower()
        if lowered in ("present", "true"):
            return True
        if lowered in ("missing", "absent", "false"):
            return False
    return None


def seats_from_ps(bridge: dict, payload) -> list[dict]:
    """Map `rig ps --nodes --json` rows onto manifest seats without inventing values.

    The bridge `seatMap` names the roles and canonical session targets a start must
    observe. A target absent from the ps answer is kept with `observed: false`,
    `session: null` and a machine-readable `no_observation_path` reason; a present row
    keeps the product's own fields.
    """
    rows = ps_rows(payload)
    seat_map = bridge.get("seatMap")
    if not isinstance(seat_map, dict) or not seat_map:
        raise PsPayloadError("bridge.seatMap must be a non-empty object")

    by_session: dict[str, dict] = {}
    by_logical: dict[str, dict] = {}
    for row in rows:
        session_name = row.get("canonicalSessionName")
        if session_name:
            by_session[str(session_name)] = row
        logical_id = row.get("logicalId")
        if logical_id:
            by_logical[str(logical_id)] = row

    seats: list[dict] = []
    for role, target in seat_map.items():
        role = str(role)
        target = str(target)
        row = by_session.get(target) or by_logical.get(role)
        if row is None:
            seats.append(
                {
                    "logicalId": role,
                    "canonicalSessionName": target,
                    "nodeId": None,
                    "expectedAction": "new",
                    "actualOutcome": "n-a",
                    "actualOutcomeObserved": False,
                    "actualOutcomeReason": OUTCOME_NOT_OBSERVED_REASON,
                    "freshAuthorized": False,
                    "freshReason": "",
                    "evidencePath": None,
                    "evidence": "degraded",
                    "evidenceReasons": ["no_observation_path"],
                    "observed": False,
                    "observationSource": "ps",
                }
            )
            continue

        session = map_ps_session(row)
        activity = map_ps_activity(row)
        if session != "present":
            activity = None
        elif activity is None:
            # A present session without a recognizable activity is `unknown`, never a
            # null enum and never an invented working/idle state.
            activity = "unknown"
        reasons = row.get("evidenceReasons")
        if not isinstance(reasons, list):
            reasons = []
        reasons = [str(reason) for reason in reasons]
        if session is None and PS_SESSION_UNKNOWN_REASON not in reasons:
            reasons.append(PS_SESSION_UNKNOWN_REASON)
        evidence = row.get("evidence")
        if evidence not in ("oracle", "observed", "degraded"):
            if session is None:
                evidence = "degraded"
            else:
                evidence = "observed" if row.get("startupStatus") == "ready" else "degraded"
        actual_outcome, outcome_observed, outcome_reason = _seat_outcome_fields(row)
        seat_row = {
            "logicalId": role,
            "canonicalSessionName": str(row.get("canonicalSessionName") or target),
            "nodeId": row.get("nodeId"),
            "expectedAction": "new",
            "actualOutcome": actual_outcome,
            "actualOutcomeObserved": outcome_observed,
            "freshAuthorized": False,
            "freshReason": "",
            "evidencePath": None,
            "evidence": evidence,
            "evidenceReasons": list(dict.fromkeys(reasons)),
            "observed": True,
            "observationSource": "ps",
        }
        if outcome_reason is not None:
            seat_row["actualOutcomeReason"] = outcome_reason
        # The schema enum has no null. An unknown session/activity is omitted rather
        # than serialized as `null`; `observed` still says ps answered for this target.
        if session is not None:
            seat_row["session"] = session
        if activity is not None:
            seat_row["activity"] = activity
        startup_status = row.get("startupStatus")
        if isinstance(startup_status, str):
            seat_row["startupStatus"] = startup_status
        token = _map_ps_token(row)
        if token is not None:
            seat_row["resumeTokenPresent"] = token
        seats.append(seat_row)
    return seats


def set_archive(manifest: dict, status: str, *, manifest_path: str | None = None) -> dict:
    manifest["archive"]["archiveStatus"] = status
    manifest["archive"]["checkedAt"] = now_iso()
    if manifest_path:
        manifest["archive"]["manifestPath"] = manifest_path
    return manifest


# ------------------------------------------------------------------ writing
def _preserve_previous(
    run_dir: Path,
    previous: dict | None,
    *,
    previous_bytes: bytes | None = None,
) -> dict | None:
    """Keep the exact bytes this write replaces under revisions/<n>.json (§5.5).

    This helper runs while the caller holds the manifest-target lock.  It never
    swallows a preservation failure: replacing the live manifest without the prior
    revision would destroy the evidence the revision number promises.
    """
    if not previous:
        return None
    revision = previous.get("revision")
    if not isinstance(revision, int) or revision < 1:
        raise ManifestRevisionError(
            "existing manifest has no valid positive integer revision; "
            "refusing to replace it without a revision-preservation target",
            revision=revision,
        )
    target = Path(run_dir) / REVISIONS_DIR / f"{revision}.json"
    data = previous_bytes if previous_bytes is not None else _json_bytes(previous)
    if target.is_file():
        try:
            existing = target.read_bytes()
        except OSError as exc:
            raise ManifestPreservationError(
                f"cannot read existing revision evidence {target}: {exc}",
                revision=revision,
                path=str(target),
            ) from exc
        if existing != data:
            raise ManifestPreservationError(
                f"revision evidence {target} already exists with different bytes",
                revision=revision,
                path=str(target),
            )
        return {"path": str(target), "sha256": sha256_bytes(data), "bytes": len(data)}
    try:
        digest = _write_bytes_unlocked(target, data)
    except OSError as exc:
        raise ManifestPreservationError(
            f"cannot preserve revision {revision} at {target}: {exc}",
            revision=revision,
            path=str(target),
        ) from exc
    return {"path": str(target), "sha256": digest, "bytes": len(data)}


def _manifest_from_bytes(raw: bytes) -> dict | None:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _validate_revision(manifest: dict, previous: dict | None) -> None:
    revision = manifest.get("revision")
    if not isinstance(revision, int) or revision < 1:
        raise ManifestRevisionError(
            f"manifest revision must be a positive integer, got {revision!r}",
            revision=revision,
        )
    if previous is None:
        return
    previous_revision = previous.get("revision")
    if not isinstance(previous_revision, int) or previous_revision < 1:
        raise ManifestRevisionError(
            "existing manifest has no valid revision; refusing an unsafe replacement",
            previousRevision=previous_revision,
        )
    expected = previous_revision + 1
    if revision != expected:
        raise ManifestRevisionError(
            f"stale manifest revision {revision}; current on-disk revision is "
            f"{previous_revision}, next revision must be {expected}",
            revision=revision,
            previousRevision=previous_revision,
            expectedRevision=expected,
        )


def write_manifest(run_dir: Path, manifest: dict, *, _replace=os.replace) -> dict:
    """Locked write: validate revision -> preserve exact old bytes -> replace.

    The lock covers the complete read-of-previous, revision-preservation and replace
    sequence.  Two writers that both prepared revision N therefore cannot interleave:
    the first wins and the second fails closed with ManifestRevisionError instead of
    returning a digest for bytes it no longer owns.
    """
    run_dir = Path(run_dir)
    finalize_manifest(manifest)
    target = run_dir / MANIFEST_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    with _path_lock(target):
        previous_bytes = target.read_bytes() if target.is_file() else None
        previous = None
        if previous_bytes is not None:
            previous = _manifest_from_bytes(previous_bytes)
            if previous is None:
                raise ManifestWriteError(
                    f"existing manifest {target} is not a JSON object; refusing to replace it",
                    path=str(target),
                )
        _validate_revision(manifest, previous)
        _preserve_previous(run_dir, previous, previous_bytes=previous_bytes)
        manifest["generatedAt"] = now_iso()
        digest = _write_bytes_unlocked(target, _json_bytes(manifest), _replace=_replace)
    missing = [key for key in REQUIRED_TOP_KEYS if key not in manifest]
    return {
        "path": str(target),
        "sha256": digest,
        "revision": manifest.get("revision"),
        "missingKeys": missing,
    }


def write_partial(
    run_dir: Path,
    manifest: dict,
    *,
    reason: str,
    rc: int,
    executed: list[dict] | None = None,
    unexecuted: list[str] | None = None,
    stdout: str = "",
    _replace=os.replace,
) -> dict:
    """A failure is evidence, not a stack trace (§5.3).

    `partial` records the failed step, the rc, the stdout digest and the steps that never
    ran — which is exactly what a reader needs to resume an investigation.
    """
    run_dir = Path(run_dir)
    partial = {
        **manifest,
        "status": "failed",
        "partial": True,
        "failure": {
            "reason": str(reason),
            "rc": int(rc),
            "stdoutSha256": sha256_bytes((stdout or "").encode("utf-8")),
            "capturedAt": now_iso(),
            "executedSteps": [step.get("stepId") for step in (executed or [])],
            "unexecutedSteps": list(unexecuted or []),
        },
    }
    # Direct callers get the same N/A contract as the live start failure path. The
    # partial status is already `failed`; finalize only repairs empty-array reasons.
    finalize_manifest(partial)
    digest = write_atomic(run_dir / PARTIAL_REL, partial, _replace=_replace)
    return {
        "path": str(run_dir / PARTIAL_REL),
        "sha256": digest,
        "rc": int(rc),
        "unexecutedSteps": list(unexecuted or []),
    }


def manifest_sha256(run_dir: Path) -> str | None:
    return sha256_file(Path(run_dir) / MANIFEST_REL)


if __name__ == "__main__":  # pragma: no cover
    print("openrig_manifest is a library; openrig_run.py writes the manifest")
    raise SystemExit(2)
