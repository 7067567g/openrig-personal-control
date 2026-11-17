# -*- coding: utf-8 -*-
"""F-06 — archive gate and runtime applicability (IO-05, CT-11, D-S7-09).

This rig has no DSH seat, so ``runtime_applicability="n/a"`` is the default
path, not a special case.  Claiming a DSH session that is not in the sessions
list is tampering, never a way to reach ``COMPLETE``.
"""

from __future__ import annotations

from dataclasses import dataclass

from guards import fixture_mark

FIXTURE_ID = "F-06"

STATUSES = ("COMPLETE", "PARTIAL", "MISSING")
N_A_REASON = "no dsh seat is declared for this rig; runtime applicability is n/a"


class ArchiveTamper(ValueError):
    def __init__(self, reasons: tuple[str, ...]) -> None:
        self.reasons = reasons
        super().__init__("ArchiveTamper: " + ", ".join(reasons))


@dataclass(frozen=True)
class ArchiveGate:
    status: str
    required: dict
    n_a_reason: str | None
    ok: bool
    violations: tuple[str, ...]
    runtimeApplicability: str

    def to_dict(self) -> dict:
        return fixture_mark(
            FIXTURE_ID,
            status=self.status,
            required=dict(self.required),
            n_a_reason=self.n_a_reason,
            ok=self.ok,
            violations=list(self.violations),
            runtimeApplicability=self.runtimeApplicability,
        )

    @property
    def tampered(self) -> bool:
        return "ArchiveTamper" in self.violations


def derive_applicability(manifest: dict) -> str:
    return "n/a" if manifest.get("dshSession") is None else "applicable"


def gate(manifest: dict, *, runtime_applicability: str | None = None) -> ArchiveGate:
    """Evaluate the archive gate for one manifest."""
    status = manifest.get("archiveStatus", "MISSING")
    if status not in STATUSES:
        raise ValueError(f"bad archiveStatus: {status!r}")

    derived = derive_applicability(manifest)
    applicable = runtime_applicability if runtime_applicability is not None else derived
    required = dict(manifest.get("required") or {})
    sessions = list(manifest.get("sessions") or [])
    items = dict(manifest.get("items") or {})
    dsh_session = manifest.get("dshSession")
    violations: list[str] = []

    # runtime applicability must not be inflated away from n/a
    if applicable != derived:
        violations.append("ArchiveTamper")

    # a claimed DSH session must exist in the session inventory
    if dsh_session is not None and dsh_session not in sessions:
        violations.append("ArchiveTamper")

    # no DSH seat => dsh must not be required
    if derived == "n/a" and required.get("dsh") is True:
        violations.append("ArchiveTamper")

    n_a_reason = N_A_REASON if derived == "n/a" else None
    if derived == "n/a" and not n_a_reason:  # pragma: no cover - defensive
        violations.append("ArchiveTamper")

    # status must agree with required items
    missing = sorted(key for key, needed in required.items() if needed and not items.get(key))
    if status == "COMPLETE" and missing:
        violations.append("status_required_mismatch")
    if status != "COMPLETE":
        violations.append("archive_incomplete")

    # de-duplicate while preserving the declared order
    seen: list[str] = []
    for violation in violations:
        if violation not in seen:
            seen.append(violation)

    ok = status == "COMPLETE" and not seen
    return ArchiveGate(
        status=status,
        required=required,
        n_a_reason=n_a_reason,
        ok=ok,
        violations=tuple(seen),
        runtimeApplicability=applicable,
    )


def stop_allowed(gate_result: ArchiveGate) -> bool:
    return gate_result.ok and gate_result.status == "COMPLETE"


def require_complete(gate_result: ArchiveGate) -> None:
    if not stop_allowed(gate_result):
        raise ArchiveTamper(gate_result.violations or ("archive_incomplete",))
