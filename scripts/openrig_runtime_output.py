#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bounded runtime-output capture for the supervised OpenRig lifecycle.

P-S10-03 contract
-----------------
Every child stream is drained while the child runs.  The *full* bytes go to a
private spill file; the supervisor keeps only a SHA-256, byte count and a
bounded UTF-8 tail.  Manifest step receipts therefore never carry unbounded
stdout/stderr, while the original stream remains available for recomputation.

The module is deliberately dependency-free (standard library only) and returns
`subprocess.CompletedProcess` objects so existing call sites keep the familiar
`.returncode`, `.stdout` and `.stderr` attributes.  Extra attributes carry the
evidence projection:

    stdout_path / stderr_path / stdout_sha256 / stderr_sha256
    stdout_bytes / stderr_bytes / stdout_tail / stderr_tail
    stdout_truncated / stderr_truncated / evidence_path

For compatibility, `.stdout` and `.stderr` contain the complete decoded stream
when it fits `INLINE_LIMIT_BYTES`; an oversized stream exposes only its bounded
tail.  `*_inline_truncated` describes that compatibility field, while
`*_truncated` describes whether the bounded proof tail omitted original bytes.
Callers that need full JSON should treat an inline-truncated stream as unparsable
(fail closed) rather than raising memory use.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import selectors
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

SCHEMA_VERSION = 1
POLICY_NAME = "openrig-runtime-output"
POLICY_VERSION = 1

# Bounded proof projection.  4 KiB per stream is large enough for a useful tail
# without letting six lifecycle steps bloat a receipt.
TAIL_BYTES = 4096
# Compatibility/JSON-parsing budget.  The child's full stream is on disk; only
# this much can enter Python memory on a successful short stream.
INLINE_LIMIT_BYTES = 1024 * 1024
CHUNK_BYTES = 64 * 1024
DRAIN_SECONDS = 1.0
POLL_SECONDS = 0.05
FILE_MODE = 0o600
DIR_MODE = 0o700
SPILL_REL = Path("reports") / "evidence" / "runtime-output"

_SECRET_FLAGS = ("--env", "--token", "--api-key", "--password", "--secret")
_SECRET_HINTS = ("TOKEN", "SECRET", "PASSWORD", "PASSWD", "KEY", "CREDENTIAL")


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def safe_segment(value: object, *, fallback: str = "output") -> str:
    """A filesystem-safe, non-empty path segment."""
    raw = str(value or "")
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip(".-")
    return (text[:96] or fallback)


def command_label(cmd: list[object]) -> str:
    parts: list[str] = []
    for token in cmd[:3]:
        text = Path(str(token)).name if not parts else str(token)
        if text:
            parts.append(text)
    return safe_segment("-".join(parts), fallback="command")


def _private_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, DIR_MODE)
    except OSError:
        pass


def _atomic_write_json(path: Path, payload: dict) -> tuple[str, int]:
    """Write a private JSON file via temp+replace. Returns (sha256, bytes)."""
    _private_mkdir(path.parent)
    data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    tmp = Path(tmp_name)
    try:
        os.fchmod(fd, FILE_MODE)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
        os.chmod(path, FILE_MODE)
    except Exception:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    return hashlib.sha256(data).hexdigest(), len(data)


def _redaction_values(values: object) -> tuple[str, ...]:
    if isinstance(values, str):
        values = (values,)
    if not isinstance(values, (list, tuple, set)):
        return ()
    cleaned = {
        str(value)
        for value in values
        if isinstance(value, (str, int, float)) and str(value)
    }
    return tuple(sorted(cleaned, key=len, reverse=True))


_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)(\b(?:token|secret|password|passwd|api[_-]?key|credential)\b\s*[=:]\s*)([^\s,;&]+)"
)


def redact_text(value: object, *secrets: object) -> str:
    """Redact known values and token-shaped assignments in proof-bound text."""
    text = str(value or "")
    for secret in _redaction_values(secrets):
        text = text.replace(secret, "<redacted>")
    return _SENSITIVE_ASSIGNMENT_RE.sub(r"\1<redacted>", text)


def secrets_from_env(env: dict | None) -> tuple[str, ...]:
    """Values of secret-looking env vars; names only would never leave the process."""
    if not env:
        return ()
    values: list[str] = []
    for name, value in env.items():
        upper = str(name).upper()
        if value and (
            any(hint in upper for hint in _SECRET_HINTS) or upper.startswith("OPENRIG_ENTRY_")
        ):
            values.append(str(value))
    return _redaction_values(values)


def secrets_from_cmd(cmd: list[object]) -> tuple[str, ...]:
    """Known secret values embedded in argv, including --env KEY=VALUE forms."""
    values: list[str] = []
    argv = [str(token) for token in cmd]
    for index, token in enumerate(argv):
        if token in _SECRET_FLAGS and index + 1 < len(argv):
            candidate = argv[index + 1]
            if token == "--env" and "=" in candidate:
                value = candidate.split("=", 1)[1]
                if value:
                    values.append(value)
            elif candidate:
                values.append(candidate)
        for flag in _SECRET_FLAGS:
            if token.startswith(f"{flag}="):
                value = token.split("=", 1)[1]
                if value:
                    values.append(value)
        if "=" in token:
            name, value = token.split("=", 1)
            if value and any(hint in name.upper() for hint in _SECRET_HINTS):
                values.append(value)
    return _redaction_values(values)


def _context(bridge: dict | None) -> dict:
    if not isinstance(bridge, dict):
        return {}
    context = bridge.get("_runtimeOutput")
    return dict(context) if isinstance(context, dict) else {}


def context_secrets(bridge: dict | None) -> tuple[str, ...]:
    values: list[str] = []
    if isinstance(bridge, dict):
        context = _context(bridge)
        raw = context.get("secrets")
        if isinstance(raw, (list, tuple, set)):
            values.extend(str(item) for item in raw if item)
        for key in ("_entryLaunchId", "token", "entryToken", "launchToken", "secret"):
            value = bridge.get(key)
            if isinstance(value, str) and value:
                values.append(value)
    return _redaction_values(values)


def with_capture(
    bridge: dict,
    *,
    run_dir: str | Path,
    label: str,
    capture_id: str | None = None,
    secrets: object = (),
    persist: bool = True,
) -> dict:
    """Return a shallow bridge copy carrying per-call capture context.

    Keeping this in the bridge preserves `_run(cmd, bridge, timeout)` signatures,
    which existing tests monkeypatch.  The private key is local-only and never
    written back to the bundle.
    """
    out = dict(bridge)
    existing = _context(out)
    merged_secrets = list(existing.get("secrets") or [])
    if isinstance(secrets, str):
        merged_secrets.append(secrets)
    elif isinstance(secrets, (list, tuple, set)):
        merged_secrets.extend(str(item) for item in secrets if item)
    out["_runtimeOutput"] = {
        **existing,
        "runDir": str(run_dir),
        "label": str(label),
        "captureId": str(capture_id) if capture_id else existing.get("captureId"),
        "secrets": _redaction_values(merged_secrets),
        "persist": bool(persist),
    }
    return out


def capture_kwargs(bridge: dict | None) -> dict:
    """Keyword arguments for `run_captured`, recovered from the bridge context."""
    context = _context(bridge)
    run_dir = context.get("runDir")
    return {
        "run_dir": Path(run_dir) if run_dir else None,
        "label": str(context.get("label") or ""),
        "capture_id": context.get("captureId"),
        "redaction_secrets": context_secrets(bridge),
        "persist": bool(context.get("persist", True)),
    }


def _decode_tail(raw: bytes) -> str:
    """Decode a byte tail without surfacing a broken leading UTF-8 sequence."""
    start = 0
    while start < len(raw) and (raw[start] & 0xC0) == 0x80:
        start += 1
    return raw[start:].decode("utf-8", "replace")


class _StreamSink:
    def __init__(self, final_path: Path, *, tail_bytes: int) -> None:
        _private_mkdir(final_path.parent)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{final_path.name}.", suffix=".tmp", dir=final_path.parent
        )
        self.fd: int | None = fd
        self.tmp_path = Path(tmp_name)
        self.final_path = final_path
        self.tail_bytes = max(int(tail_bytes), 0)
        self.hasher = hashlib.sha256()
        self.bytes = 0
        self.tail = bytearray()
        self.error: str | None = None
        try:
            os.fchmod(fd, FILE_MODE)
        except OSError:
            pass

    def feed(self, chunk: bytes) -> None:
        if not chunk:
            return
        if self.fd is None:
            raise OSError("stream sink is already closed")
        view = memoryview(chunk)
        while view:
            written = os.write(self.fd, view)
            if written <= 0:
                raise OSError("short write while spilling child output")
            view = view[written:]
        self.hasher.update(chunk)
        self.bytes += len(chunk)
        self.tail.extend(chunk)
        overflow = len(self.tail) - self.tail_bytes
        if overflow > 0:
            del self.tail[:overflow]

    def _close_fd(self) -> None:
        if self.fd is not None:
            try:
                os.close(self.fd)
            finally:
                self.fd = None

    def finish(self) -> None:
        self._close_fd()
        os.replace(self.tmp_path, self.final_path)
        os.chmod(self.final_path, FILE_MODE)

    def abort(self) -> None:
        self._close_fd()
        try:
            self.tmp_path.unlink()
        except OSError:
            pass

    @property
    def truncated(self) -> bool:
        return self.bytes > len(self.tail)

    @property
    def tail_text(self) -> str:
        return _decode_tail(bytes(self.tail))

    def public(self) -> dict:
        return {
            "path": str(self.final_path.resolve()),
            "sha256": self.hasher.hexdigest(),
            "bytes": self.bytes,
            "tail": self.tail_text,
            "tailBytes": len(self.tail),
            "tailLimitBytes": self.tail_bytes,
            "truncated": self.truncated,
            "omittedBytes": max(self.bytes - len(self.tail), 0),
        }


def _registry_paths(
    run_dir: Path | None,
    capture_id: str,
) -> tuple[Path, Path, Path]:
    root = Path(run_dir) if run_dir is not None else Path(tempfile.gettempdir()) / "openrig-runtime-output"
    capture_dir = root / SPILL_REL / safe_segment(capture_id)
    stem = safe_segment(capture_id)
    return capture_dir, capture_dir / f"{stem}.stdout.log", capture_dir / f"{stem}.stderr.log"


def _stream_text(sink: _StreamSink, inline_limit: int) -> tuple[str, bool]:
    if sink.bytes <= inline_limit:
        try:
            return Path(sink.final_path).read_text(
                encoding="utf-8", errors="replace"
            ), False
        except OSError:
            # A failed finalize still leaves the bounded tail available.
            return sink.tail_text, True
    return sink.tail_text, True


def _base_attrs(
    proc: subprocess.CompletedProcess,
    *,
    sinks: dict[str, _StreamSink],
    sidecar_path: Path,
    sidecar_sha: str,
    sidecar_bytes: int,
    started_at: str,
    ended_at: str,
    timed_out: bool,
    capture_id: str,
    inline_limit: int,
    capture_errors: list[str],
    secrets: tuple[str, ...] = (),
) -> subprocess.CompletedProcess:
    for name, sink in sinks.items():
        text, truncated = _stream_text(sink, inline_limit)
        setattr(proc, name, text)
        setattr(proc, f"{name}_path", str(sink.final_path.resolve()))
        setattr(proc, f"{name}_sha256", sink.hasher.hexdigest())
        setattr(proc, f"{name}_bytes", sink.bytes)
        setattr(proc, f"{name}_tail", redact_text(sink.tail_text, *secrets))
        setattr(proc, f"{name}_inline_truncated", truncated)
        # Proof truncation: whether the bounded tail omits any original bytes.
        setattr(proc, f"{name}_truncated", sink.truncated)
        setattr(proc, f"{name}_omitted_bytes", max(sink.bytes - len(sink.tail), 0))
    proc.evidence_path = str(sidecar_path.resolve())
    proc.evidence_sha256 = sidecar_sha
    proc.evidence_bytes = sidecar_bytes
    proc.capture_id = capture_id
    proc.started_at = started_at
    proc.ended_at = ended_at
    proc.timed_out = bool(timed_out)
    proc.capture_errors = list(capture_errors)
    return proc


def _sidecar_payload(
    *,
    capture_id: str,
    label: str,
    cmd: list[object],
    cwd: str,
    rc: int,
    started_at: str,
    ended_at: str,
    timed_out: bool,
    timeout: int | None,
    sinks: dict[str, _StreamSink],
    redacted_cmd: list[str],
    argv_redacted: bool,
    capture_errors: list[str],
    tail_bytes: int,
    inline_limit: int,
) -> dict:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "runtime-output-evidence",
        "policy": {
            "name": POLICY_NAME,
            "version": POLICY_VERSION,
            "tailBytes": int(tail_bytes),
            "inlineLimitBytes": int(inline_limit),
            "spillRoot": str(SPILL_REL),
            "fileMode": "0600",
        },
        "captureId": capture_id,
        "label": label,
        "cmd": redacted_cmd,
        "argvRedacted": bool(argv_redacted),
        "cwd": cwd,
        "startedAt": started_at,
        "endedAt": ended_at,
        "rc": int(rc),
        "timedOut": bool(timed_out),
        "timeoutSeconds": timeout,
        "streams": {name: sink.public() for name, sink in sinks.items()},
        "captureErrors": list(capture_errors),
    }


def _redact_command(cmd: list[object], secrets: tuple[str, ...]) -> tuple[list[str], bool]:
    """Redact secret-bearing argv without importing openrig_manifest (no cycles)."""
    out: list[str] = []
    redact_next = False
    changed = False
    for raw in cmd:
        token = str(raw)
        if redact_next:
            out.append("<redacted>")
            redact_next = False
            changed = True
            continue
        if token in _SECRET_FLAGS:
            out.append(token)
            redact_next = True
            continue
        replaced = redact_text(token, *secrets)
        if replaced != token:
            changed = True
        out.append(replaced)
    return out, changed


def run_captured(
    cmd: list[object],
    *,
    env: dict | None = None,
    timeout: int | None = 120,
    run_dir: str | Path | None = None,
    label: str = "",
    capture_id: str | None = None,
    cwd: str | Path | None = None,
    tail_bytes: int = TAIL_BYTES,
    inline_limit: int = INLINE_LIMIT_BYTES,
    redaction_secrets: object = (),
    persist: bool = True,
) -> subprocess.CompletedProcess:
    """Run one child, spilling full stdout/stderr and returning bounded evidence.

    `persist=False` is for read-only probes (`status --live`): the same bounded
    streaming path is used, but its temporary spill directory is removed before
    return so the command leaves the run tree byte-identical.
    """
    argv = [str(part) for part in cmd]
    label_text = safe_segment(label or command_label(argv), fallback="command")
    capture_text = safe_segment(
        capture_id
        or f"{label_text}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{uuid.uuid4().hex[:8]}"
    )
    capture_root = Path(run_dir) if run_dir is not None else None
    if not persist:
        capture_root = Path(tempfile.mkdtemp(prefix="openrig-runtime-readonly-"))
    _capture_dir, stdout_path, stderr_path = _registry_paths(capture_root, capture_text)
    sidecar_path = stdout_path.parent / f"{safe_segment(capture_text)}.evidence.json"
    started_at = now_iso()
    started_mono = time.monotonic()
    sinks = {
        "stdout": _StreamSink(stdout_path, tail_bytes=tail_bytes),
        "stderr": _StreamSink(stderr_path, tail_bytes=tail_bytes),
    }
    capture_errors: list[str] = []
    timed_out = False
    rc = 126
    proc: subprocess.Popen | None = None
    real_cwd = str(cwd) if cwd is not None else os.getcwd()
    secrets = _redaction_values(
        list(secrets_from_env(env))
        + list(secrets_from_cmd(argv))
        + list(_redaction_values(redaction_secrets))
    )
    try:
        proc = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=real_cwd,
            bufsize=0,
        )
    except FileNotFoundError as exc:
        message = f"command not found: {exc}".encode("utf-8")
        sinks["stderr"].feed(message)
        rc = 127
    except OSError as exc:
        message = f"could not run: {exc}".encode("utf-8")
        sinks["stderr"].feed(message)
        rc = 126

    if proc is not None:
        selector = selectors.DefaultSelector()
        by_fd: dict[int, _StreamSink] = {}
        for name, stream in (("stdout", proc.stdout), ("stderr", proc.stderr)):
            if stream is None:
                continue
            fd = stream.fileno()
            os.set_blocking(fd, False)
            selector.register(fd, selectors.EVENT_READ, name)
            by_fd[fd] = sinks[name]

        drain_deadline: float | None = None
        try:
            while True:
                if not timed_out and timeout is not None and started_mono + max(int(timeout), 0) <= time.monotonic():
                    timed_out = True
                    try:
                        proc.kill()
                    except OSError:
                        pass

                for key, _events in selector.select(POLL_SECONDS):
                    name = str(key.data)
                    sink = by_fd.get(key.fd)
                    if sink is None:
                        continue
                    try:
                        chunk = os.read(key.fd, CHUNK_BYTES)
                    except BlockingIOError:
                        continue
                    except OSError as exc:
                        capture_errors.append(f"{name}: read failed: {exc}")
                        try:
                            selector.unregister(key.fd)
                        except Exception:  # noqa: BLE001
                            pass
                        continue
                    if chunk:
                        try:
                            sink.feed(chunk)
                        except OSError as exc:
                            capture_errors.append(f"{name}: spill failed: {exc}")
                            try:
                                selector.unregister(key.fd)
                            except Exception:  # noqa: BLE001
                                pass
                    else:
                        try:
                            selector.unregister(key.fd)
                        except Exception:  # noqa: BLE001
                            pass

                if proc.poll() is not None and drain_deadline is None:
                    drain_deadline = time.monotonic() + DRAIN_SECONDS
                if proc.poll() is not None and drain_deadline is not None:
                    if not selector.get_map() or time.monotonic() >= drain_deadline:
                        break
                if timed_out and drain_deadline is not None and time.monotonic() >= drain_deadline:
                    break
        finally:
            selector.close()
            for stream in (proc.stdout, proc.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass
            try:
                wait_timeout = max(DRAIN_SECONDS, 1.0)
                rc = int(proc.wait(timeout=wait_timeout))
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except OSError:
                    pass
                try:
                    rc = int(proc.wait(timeout=wait_timeout))
                except subprocess.TimeoutExpired:
                    capture_errors.append("child did not reap after kill")
                    rc = 124
        if timed_out:
            rc = 124

    for sink in sinks.values():
        try:
            sink.finish()
        except OSError as exc:
            capture_errors.append(f"finalize failed for {sink.final_path}: {exc}")

    stdout_text, stdout_truncated = _stream_text(sinks["stdout"], inline_limit)
    stderr_text, stderr_truncated = _stream_text(sinks["stderr"], inline_limit)
    if timed_out and timeout is not None:
        suffix = f"timeout after {timeout}s"
        stderr_text = f"{stderr_text.rstrip()}\n{suffix}".lstrip() if stderr_text else suffix
        # The timeout marker is operational metadata, not part of the original spill.
        stderr_truncated = True if sinks["stderr"].bytes > len(sinks["stderr"].tail) else stderr_truncated

    completed = subprocess.CompletedProcess(argv, rc, stdout_text, stderr_text)
    redacted_cmd, argv_redacted = _redact_command(argv, secrets)
    payload = _sidecar_payload(
        capture_id=capture_text,
        label=label_text,
        cmd=argv,
        cwd=real_cwd,
        rc=rc,
        started_at=started_at,
        ended_at=now_iso(),
        timed_out=timed_out,
        timeout=timeout,
        sinks=sinks,
        redacted_cmd=redacted_cmd,
        argv_redacted=argv_redacted,
        capture_errors=capture_errors,
        tail_bytes=tail_bytes,
        inline_limit=inline_limit,
    )
    # Redact only the proof projection; full raw bytes remain in the 0600 spill.
    for name in ("stdout", "stderr"):
        stream_payload = payload["streams"][name]
        stream_payload["tail"] = redact_text(stream_payload.get("tail"), *secrets)
    try:
        sidecar_sha, sidecar_bytes = _atomic_write_json(sidecar_path, payload)
    except OSError as exc:
        capture_errors.append(f"sidecar write failed: {exc}")
        sidecar_sha, sidecar_bytes = "", 0
    result = _base_attrs(
        completed,
        sinks=sinks,
        sidecar_path=sidecar_path,
        sidecar_sha=sidecar_sha,
        sidecar_bytes=sidecar_bytes,
        started_at=started_at,
        ended_at=now_iso(),
        timed_out=timed_out,
        capture_id=capture_text,
        inline_limit=inline_limit,
        capture_errors=capture_errors,
        secrets=secrets,
    )
    # Compatibility fields are for parsing/error text; preserve the timeout marker
    # even though the raw spill itself remains untouched.
    result.stdout = stdout_text
    result.stderr = stderr_text
    result.persist = bool(persist)
    if not persist:
        result.stdout_path = None
        result.stderr_path = None
        result.evidence_path = None
        result.evidence_sha256 = None
        result.evidence_bytes = None
        try:
            shutil.rmtree(_capture_dir, ignore_errors=True)
            if capture_root is not None and capture_root != Path(run_dir or ""):
                shutil.rmtree(capture_root, ignore_errors=True)
        except OSError:
            pass
    return result


def materialize_completed_process(
    proc: subprocess.CompletedProcess,
    *,
    run_dir: str | Path,
    label: str,
    cwd: str | Path | None = None,
    redaction_secrets: object = (),
) -> subprocess.CompletedProcess:
    """Attach spill/sidecar evidence to a CompletedProcess returned by a test fake.

    Production `_run` calls `run_captured` directly.  Tests frequently monkeypatch
    `_run`; this adapter keeps the same evidence contract without re-running the
    child or keeping a second code path for proof.
    """
    if getattr(proc, "evidence_path", None) and Path(str(proc.evidence_path)).is_file():
        return proc
    argv = [str(part) for part in (getattr(proc, "args", []) or [label])]
    display_stdout = str(getattr(proc, "stdout", "") or "")
    display_stderr = str(getattr(proc, "stderr", "") or "")
    capture_text = safe_segment(f"{label}-{uuid.uuid4().hex[:8]}")
    _capture_dir, stdout_path, stderr_path = _registry_paths(Path(run_dir), capture_text)
    sink_stdout = _StreamSink(stdout_path, tail_bytes=TAIL_BYTES)
    sink_stderr = _StreamSink(stderr_path, tail_bytes=TAIL_BYTES)
    sink_stdout.feed(str(getattr(proc, "stdout", "") or "").encode("utf-8"))
    sink_stderr.feed(str(getattr(proc, "stderr", "") or "").encode("utf-8"))
    sink_stdout.finish()
    sink_stderr.finish()
    timestamp = now_iso()
    secrets = _redaction_values(
        list(secrets_from_cmd(argv))
        + list(_redaction_values(redaction_secrets))
    )
    redacted_cmd, argv_redacted = _redact_command(argv, secrets)
    sidecar_path = stdout_path.parent / f"{capture_text}.evidence.json"
    payload = _sidecar_payload(
        capture_id=capture_text,
        label=safe_segment(label),
        cmd=argv,
        cwd=str(cwd) if cwd is not None else os.getcwd(),
        rc=int(getattr(proc, "returncode", 1) or 0),
        started_at=timestamp,
        ended_at=timestamp,
        timed_out=False,
        timeout=None,
        sinks={"stdout": sink_stdout, "stderr": sink_stderr},
        redacted_cmd=redacted_cmd,
        argv_redacted=argv_redacted,
        capture_errors=[],
        tail_bytes=TAIL_BYTES,
        inline_limit=INLINE_LIMIT_BYTES,
    )
    for name in ("stdout", "stderr"):
        payload["streams"][name]["tail"] = redact_text(
            payload["streams"][name].get("tail"), *secrets
        )
    sidecar_sha, sidecar_bytes = _atomic_write_json(sidecar_path, payload)
    result = _base_attrs(
        proc,
        sinks={"stdout": sink_stdout, "stderr": sink_stderr},
        sidecar_path=sidecar_path,
        sidecar_sha=sidecar_sha,
        sidecar_bytes=sidecar_bytes,
        started_at=timestamp,
        ended_at=timestamp,
        timed_out=False,
        capture_id=capture_text,
        inline_limit=INLINE_LIMIT_BYTES,
        capture_errors=[],
        secrets=secrets,
    )
    # Test fakes already hold the full string.  Preserve their compatibility fields;
    # proof consumers still read only the bounded attrs / sidecar above.
    result.stdout = display_stdout
    result.stderr = display_stderr
    return result


def ensure_evidence(
    proc: subprocess.CompletedProcess,
    *,
    run_dir: str | Path,
    label: str,
    cwd: str | Path | None = None,
    redaction_secrets: object = (),
) -> subprocess.CompletedProcess:
    return materialize_completed_process(
        proc,
        run_dir=run_dir,
        label=label,
        cwd=cwd,
        redaction_secrets=redaction_secrets,
    )


def capture_fields(
    proc: subprocess.CompletedProcess,
    *,
    redaction_secrets: object = (),
) -> dict:
    """Flat bounded projection for reports, manifests and receipts."""
    secrets = list(_redaction_values(redaction_secrets))
    out: dict = {
        "evidencePath": getattr(proc, "evidence_path", None),
        "evidenceSha256": getattr(proc, "evidence_sha256", None),
        "evidenceBytes": getattr(proc, "evidence_bytes", None),
        "timedOut": bool(getattr(proc, "timed_out", False)),
    }
    for name in ("stdout", "stderr"):
        path = getattr(proc, f"{name}_path", None)
        has_capture_attrs = hasattr(proc, f"{name}_sha256") and hasattr(proc, f"{name}_bytes")
        if path is None and not getattr(proc, "evidence_path", None) and not has_capture_attrs:
            raw = str(getattr(proc, name, "") or "").encode("utf-8")
            tail_raw = raw[-TAIL_BYTES:]
            out.update(
                {
                    f"{name}Path": None,
                    f"{name}Sha256": hashlib.sha256(raw).hexdigest(),
                    f"{name}Bytes": len(raw),
                    f"{name}Tail": redact_text(_decode_tail(tail_raw), *secrets),
                    f"{name}Truncated": len(raw) > len(tail_raw),
                    f"{name}OmittedBytes": max(len(raw) - len(tail_raw), 0),
                }
            )
            continue
        raw_tail = str(getattr(proc, f"{name}_tail", "") or "")
        out.update(
            {
                f"{name}Path": path,
                f"{name}Sha256": getattr(proc, f"{name}_sha256", None),
                f"{name}Bytes": getattr(proc, f"{name}_bytes", None),
                f"{name}Tail": redact_text(raw_tail, *secrets),
                f"{name}Truncated": bool(getattr(proc, f"{name}_truncated", False)),
                f"{name}OmittedBytes": getattr(proc, f"{name}_omitted_bytes", 0),
            }
        )
    return out


def receipt_mutation(
    step: str,
    proc: subprocess.CompletedProcess,
    *,
    argv: list[object] | None = None,
    redaction_secrets: object = (),
) -> dict:
    raw_argv = [str(part) for part in (argv or getattr(proc, "args", []) or [])]
    secrets = _redaction_values(redaction_secrets)
    redacted_argv, _changed = _redact_command(raw_argv, secrets)
    payload = {
        "step": str(step),
        "rc": int(getattr(proc, "returncode", 1) or 0),
        "argv": redacted_argv,
    }
    payload.update(capture_fields(proc, redaction_secrets=redaction_secrets))
    return payload


def read_spill_text(path: str | Path, *, limit: int = INLINE_LIMIT_BYTES) -> str:
    """Read at most `limit` bytes of a spill for JSON parsing, never unbounded."""
    try:
        with Path(path).open("rb") as handle:
            raw = handle.read(max(int(limit), 0))
    except OSError:
        return ""
    return raw.decode("utf-8", "replace")
