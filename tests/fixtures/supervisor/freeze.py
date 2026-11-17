# -*- coding: utf-8 -*-
"""F-05 — freeze / handoff digests (A1..A5, D-029..D-037, D-045).

Semantics only: this module does not import or modify the product
``handoff_gate.py``.  Content, not mtime, decides integrity; mtime is an
auxiliary identity field (W3/D-045).
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from fake_rig import format_dt, parse_dt
from guards import fixture_mark

FIXTURE_ID = "F-05"

MODES = ("initial", "revision")


class FreezeError(RuntimeError):
    pass


class StaleReview(RuntimeError):
    def __init__(self, reasons: Sequence[str]) -> None:
        self.reasons = tuple(reasons)
        super().__init__("stale review input: " + ", ".join(self.reasons))


@dataclass(frozen=True)
class Artifact:
    path: str
    sha256: str
    bytes: int
    mtime: str

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "bytes": self.bytes,
            "mtime": self.mtime,
        }


@dataclass(frozen=True)
class DigestSet:
    runId: str
    mode: str
    capturedAt: str
    capturedBy: str
    artifacts: tuple[Artifact, ...]
    authorizedOutputs: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return fixture_mark(
            FIXTURE_ID,
            runId=self.runId,
            mode=self.mode,
            capturedAt=self.capturedAt,
            capturedBy=self.capturedBy,
            artifacts=[artifact.to_dict() for artifact in self.artifacts],
            authorizedOutputs=list(self.authorizedOutputs),
        )

    def digest(self) -> str:
        joined = "\n".join(f"{a.path}:{a.sha256}:{a.bytes}" for a in self.artifacts)
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SelfDiff:
    baseline: str
    baselineDigest: str
    rc: int
    removed: tuple[str, ...]
    added: tuple[str, ...]
    fieldDiff: int
    refDiff: int

    def to_dict(self) -> dict:
        return fixture_mark(
            FIXTURE_ID,
            baseline=self.baseline,
            baselineDigest=self.baselineDigest,
            rc=self.rc,
            removed=list(self.removed),
            added=list(self.added),
            fieldDiff=self.fieldDiff,
            refDiff=self.refDiff,
        )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Compliance:
    compliant: bool
    reason: str

    def to_dict(self) -> dict:
        return fixture_mark(FIXTURE_ID, compliant=self.compliant, reason=self.reason)


def _mtime(path: Path) -> str:
    moment = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return format_dt(moment)


def _relative(base: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError as exc:
        raise FreezeError(f"artifact outside base: {path}") from exc


def capture(
    base: Path,
    paths: Iterable[Path],
    *,
    run_id: str,
    captured_at: str,
    actor: str,
    mode: str = "initial",
    authorized_outputs: Iterable[str] | None = None,
) -> DigestSet:
    """A1: capture sha256 + bytes + mtime for every artifact."""
    if mode not in MODES:
        raise FreezeError(f"bad mode: {mode!r}")
    base = Path(base).resolve()
    artifacts: list[Artifact] = []
    for raw in paths:
        path = Path(raw)
        path = path if path.is_absolute() else base / path
        if not path.is_file():
            raise FreezeError(f"artifact missing: {path}")
        data = path.read_bytes()
        artifacts.append(
            Artifact(
                path=_relative(base, path),
                sha256=_sha256(data),
                bytes=len(data),
                mtime=_mtime(path),
            )
        )
    artifacts.sort(key=lambda item: item.path)
    if not artifacts:
        raise FreezeError("no artifacts to capture")

    capture_moment = parse_dt(captured_at)
    latest = max(parse_dt(artifact.mtime) for artifact in artifacts)
    if capture_moment < latest:
        raise FreezeError("capturedAt precedes the last write (A1)")

    return DigestSet(
        runId=run_id,
        mode=mode,
        capturedAt=captured_at,
        capturedBy=actor,
        artifacts=tuple(artifacts),
        authorizedOutputs=tuple(authorized_outputs or ()),
    )


def _common_base(paths: Iterable[Path]) -> Path:
    parents = [str(Path(path).resolve().parent) for path in paths]
    if not parents:
        return Path(".").resolve()
    return Path(os.path.commonpath(parents))


def _infer_base(frozen: "DigestSet", items: Sequence[Path]) -> Path:
    """Find the ancestor that makes the frozen relative paths resolve."""
    if items:
        first = Path(items[0]).resolve()
        for parent in (first.parent, *first.parents):
            if all((parent / artifact.path).is_file() for artifact in frozen.artifacts):
                return parent
    return _common_base(items)


def self_diff(frozen: DigestSet, candidate, *, extra_paths: Iterable[Path] = ()) -> SelfDiff:
    """A2: content diff of the live tree against the frozen digest.

    ``candidate`` may be a base directory, an iterable of artifact paths, or a
    mapping ``{relative_path: bytes|str}``; the latter shapes follow
    ``self_diff(frozen, candidate)`` from 00-plan §4 F-05.
    """
    if isinstance(candidate, (str, os.PathLike)):
        base = Path(candidate).resolve()
        mappings: Mapping | None = None
    elif isinstance(candidate, Mapping):
        base = Path(".").resolve()
        mappings = candidate
    else:
        items = [Path(path) for path in candidate]
        base = _infer_base(frozen, items)
        extra_paths = tuple(list(extra_paths) + items)
        mappings = None

    if mappings is not None:
        removed = [artifact.path for artifact in frozen.artifacts if artifact.path not in mappings]
        changed = 0
        for artifact in frozen.artifacts:
            value = mappings.get(artifact.path)
            if value is None:
                continue
            raw = value.encode("utf-8") if isinstance(value, str) else bytes(value)
            if _sha256(raw) != artifact.sha256:
                changed += 1
        added = [str(path) for path in (extra_paths or ())]
        return SelfDiff(
            baseline=f"{frozen.mode}:{frozen.runId}",
            baselineDigest=frozen.digest(),
            rc=1 if (removed or added or changed) else 0,
            removed=tuple(sorted(removed)),
            added=tuple(sorted(added)),
            fieldDiff=changed,
            refDiff=0,
        )

    removed: list[str] = []
    added: list[str] = []
    changed = 0
    identity_drift = 0
    for artifact in frozen.artifacts:
        path = base / artifact.path
        if not path.is_file():
            removed.append(artifact.path)
            continue
        data = path.read_bytes()
        if _sha256(data) != artifact.sha256 or len(data) != artifact.bytes:
            changed += 1
        elif _mtime(path) != artifact.mtime:
            identity_drift += 1
    known = {artifact.path for artifact in frozen.artifacts}
    for raw in extra_paths:
        path = Path(raw)
        path = path if path.is_absolute() else base / path
        rel = _relative(base, path)
        if rel not in known:
            added.append(rel)
    rc = 1 if (removed or added or changed) else 0
    return SelfDiff(
        baseline=f"{frozen.mode}:{frozen.runId}",
        baselineDigest=frozen.digest(),
        rc=rc,
        removed=tuple(sorted(removed)),
        added=tuple(sorted(added)),
        fieldDiff=changed,
        refDiff=identity_drift,
    )


def _verify_base(packet: DigestSet, base: Path) -> list[str]:
    reasons: list[str] = []
    for artifact in packet.artifacts:
        path = base / artifact.path
        if not path.is_file():
            reasons.append(f"missing:{artifact.path}")
            continue
        data = path.read_bytes()
        if _sha256(data) != artifact.sha256:
            reasons.append(f"stale:{artifact.path}")
        elif len(data) != artifact.bytes:
            reasons.append(f"size:{artifact.path}")
    return reasons


def verify_review_input(packet: DigestSet, disk) -> None:
    """A5: the reviewer must diff an immutable copy, never the live path.

    ``disk`` may be a base directory, a mapping ``{relative_path: bytes|str}``
    or an iterable of artifact paths.
    """
    if isinstance(disk, (str, os.PathLike)):
        reasons = _verify_base(packet, Path(disk).resolve())
    elif isinstance(disk, Mapping):
        reasons = []
        for artifact in packet.artifacts:
            value = disk.get(artifact.path)
            if value is None:
                reasons.append(f"missing:{artifact.path}")
                continue
            raw = value.encode("utf-8") if isinstance(value, str) else bytes(value)
            if _sha256(raw) != artifact.sha256:
                reasons.append(f"stale:{artifact.path}")
    else:
        items = [Path(path) for path in disk]
        reasons = _verify_base(packet, _infer_base(packet, items))
    if reasons:
        raise StaleReview(reasons)


def freeze(
    paths: Iterable[Path],
    *,
    captured_at: str,
    actor: str,
    run_id: str = "fixture-run",
    base: Path | None = None,
    mode: str = "initial",
    authorized_outputs: Iterable[str] | None = None,
) -> DigestSet:
    """A1 with the 00-plan §4 F-05 signature."""
    items = [Path(path) for path in paths]
    resolved_base = Path(base).resolve() if base is not None else _common_base(items)
    return capture(
        resolved_base,
        items,
        run_id=run_id,
        captured_at=captured_at,
        actor=actor,
        mode=mode,
        authorized_outputs=authorized_outputs,
    )


def identity(run_id: str, relative_path: str, sha256: str, size: int, mtime: str) -> dict:
    """D-033 identity tuple; absolute paths never enter the contract."""
    return fixture_mark(
        FIXTURE_ID,
        runId=run_id,
        path=relative_path,
        sha256=sha256,
        bytes=size,
        mtime=mtime,
    )


@dataclass(frozen=True)
class ClaimWindowVerdict:
    ok: bool
    code: str | None
    violations: tuple[str, ...] = ()
    mtimeDrift: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return fixture_mark(
            FIXTURE_ID,
            ok=self.ok,
            code=self.code,
            violations=list(self.violations),
            mtimeDrift=list(self.mtimeDrift),
        )


def detect_claim_window_escape(
    frozen: DigestSet,
    base: Path,
    *,
    closed_at: str,
) -> ClaimWindowVerdict:
    """RT-27/A6: a post-close write is caught by hash, never by mtime alone.

    * content differs from the frozen snapshot (even with a rolled-back mtime)
      -> ``claim_window_escape``;
    * content is identical but mtime moved past ``closed_at``
      -> recorded as ``mtimeDrift``, not as an escape (mtime is auxiliary).
    """
    base = Path(base).resolve()
    violations: list[str] = []
    drift: list[str] = []
    closed = parse_dt(closed_at)
    for artifact in frozen.artifacts:
        path = base / artifact.path
        if not path.is_file():
            violations.append(f"missing:{artifact.path}")
            continue
        data = path.read_bytes()
        if _sha256(data) != artifact.sha256:
            violations.append(f"claim_window_escape:{artifact.path}")
            continue
        if parse_dt(_mtime(path)) > closed:
            drift.append(f"late_write_identity:{artifact.path}")
    ok = not violations
    return ClaimWindowVerdict(
        ok=ok,
        code=None if ok else "claim_window_escape",
        violations=tuple(violations),
        mtimeDrift=tuple(drift),
    )


def digest_bundle(
    frozen: DigestSet,
    *,
    diff: SelfDiff,
    gate: dict,
    authorized_delta: dict,
) -> dict:
    """Compose the bundle consumed by :func:`verify_compliance` (D-032)."""
    bundle = frozen.to_dict()
    bundle["selfDiff"] = diff.to_dict()
    bundle["gate"] = {
        "cmd": gate.get("cmd", ""),
        "rc": gate.get("rc", 1),
        "evidenceSha256": gate.get("evidenceSha256"),
    }
    bundle["authorizedDelta"] = dict(authorized_delta)
    return bundle


def verify_compliance(digest: dict) -> Compliance:
    """Integrity alone is not compliance (D-032)."""
    if not isinstance(digest, dict):
        return Compliance(False, "invalid_bundle")
    artifacts = digest.get("artifacts")
    mode = digest.get("mode")
    if not isinstance(artifacts, list) or not artifacts:
        return Compliance(False, "incomplete_bundle")
    for artifact in artifacts:
        if not isinstance(artifact, dict) or not isinstance(artifact.get("sha256"), str):
            return Compliance(False, "incomplete_bundle")

    diff = digest.get("selfDiff")
    gate = digest.get("gate")
    delta = digest.get("authorizedDelta")

    if mode not in MODES:
        return Compliance(False, "invalid_mode")
    if mode == "initial":
        authorized = digest.get("authorizedOutputs")
        if not authorized:
            return Compliance(False, "initial_missing_authorized_outputs")

    if not isinstance(diff, dict) or not isinstance(gate, dict) or not isinstance(delta, dict):
        # hashes may be intact, but this proves integrity only
        return Compliance(False, "hash_only")

    if diff.get("rc") != 0 or diff.get("removed") or diff.get("added") or diff.get("fieldDiff"):
        return Compliance(False, "self_diff_failed")
    if gate.get("rc") != 0:
        return Compliance(False, "gate_failed")

    allowed = delta.get("allowedPaths") or []
    decisions = delta.get("decisionIds") or []
    if not allowed or not decisions:
        return Compliance(False, "authorized_delta_mismatch")
    artifact_paths = {artifact.get("path") for artifact in artifacts}
    if not artifact_paths.issubset(set(allowed)):
        return Compliance(False, "authorized_delta_mismatch")

    return Compliance(True, "compliant")
