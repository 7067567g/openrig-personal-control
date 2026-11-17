# -*- coding: utf-8 -*-
"""F-02 — supervisor state machine, guards, receipts and partial evidence.

Design-only substitute: this module executes **scripted** runner calls
(``fake_rig.FakeRig``), never a real daemon/rig/workflow.  Every refusal
happens before mutation (``rc=2``, ``mutation_count`` unchanged).  Failures
after mutation write ``run-manifest.partial.json`` and never delete home/DB.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Sequence

import archive
import continuity
from fake_rig import Clock, IdFactory, parse_dt
from guards import assert_fixture_home, fixture_mark
from observation import Observation

FIXTURE_ID = "F-02"
MANIFEST_SCHEMA_VERSION = 1
DEFAULT_TTL = {"start": 1800, "resume": 1200}

STATES = (
    "EMPTY",
    "PREPARED",
    "DAEMON_READY",
    "RIG_READY",
    "VALIDATED",
    "INSTANTIATED",
    "RUNNING",
    "STOPPING",
    "STOPPED",
    "CONTINUITY_PLAN",
    "RESUMING",
    "FAILED",
    "ARCHIVED",
)

COMMAND_STATES = {
    "check": ("EMPTY",),
    "start": ("EMPTY", "PREPARED"),
    "resume": ("STOPPED",),
    "stop": ("RUNNING",),
    "archive": ("STOPPED",),
    "status": STATES,
    "next": STATES,
}

CANONICAL_NEXT = (
    "check",
    "start-dry-run",
    "start",
    "verify-render",
    "archive-gate",
)

GUARD_CODES = {
    "guard_bridge_sha": "bridge_invalid",
    "guard_home_match": "run_home_mismatch",
    "guard_no_legacy_run": "run_exists",
    "guard_rig_absent": "rig_exists",
    "guard_workflow_absent": "workflow_duplicate",
    "guard_daemon_identity": "daemon_identity_mismatch",
    "guard_port_collision": "port_collision",
    "guard_launch_ttl": "stale_launch",
    "guard_verb_unconsumed": "launch_verb_consumed",
    "guard_continuity_allow": "continuity_blocked",
    "guard_fresh_authorized": "fresh_not_authorized",
    "guard_node_identity": "continuity_mismatch",
    "guard_seat_outcome_match": "continuity_mismatch",
    "guard_archive_complete": "archive_incomplete",
}

GUARD_HINTS = {
    "guard_bridge_sha": "bridge bytes do not match the declared sha256; re-render",
    "guard_home_match": "OPENRIG_HOME does not match the bridge; use the run's home",
    "guard_no_legacy_run": "run already exists; use `resume` instead of `start`",
    "guard_rig_absent": "same-name rig already exists; use `resume`",
    "guard_workflow_absent": "workflow instance already exists; attach, do not instantiate",
    "guard_daemon_identity": "healthz pid differs from daemon.json; do not continue",
    "guard_port_collision": "port is owned by another home",
    "guard_launch_ttl": "launch record expired; start a new supervised launch",
    "guard_verb_unconsumed": "this verb was already consumed by the launch",
    "guard_continuity_allow": "continuity plan is not `allow`; zero mutation",
    "guard_fresh_authorized": "--fresh requires an authorized seat and a non-empty reason",
    "guard_node_identity": "nodeId changed for the same logical seat",
    "guard_seat_outcome_match": "actual outcome differs from the expected action",
    "guard_archive_complete": "archive gate is not COMPLETE; stop is refused",
}

COMMAND_GUARDS = {
    "check": (
        "guard_bridge_sha",
        "guard_home_match",
        "guard_no_legacy_run",
        "guard_rig_absent",
        "guard_workflow_absent",
    ),
    "start": (
        "guard_bridge_sha",
        "guard_home_match",
        "guard_no_legacy_run",
        "guard_rig_absent",
        "guard_workflow_absent",
        "guard_daemon_identity",
        "guard_port_collision",
        "guard_launch_ttl",
        "guard_verb_unconsumed",
    ),
    "resume": (
        "guard_launch_ttl",
        "guard_verb_unconsumed",
        "guard_continuity_allow",
        "guard_fresh_authorized",
        "guard_node_identity",
        "guard_seat_outcome_match",
    ),
    "stop": ("guard_archive_complete",),
    "archive": ("guard_archive_complete",),
    "status": (),
    "next": (),
}


class Rejection(Exception):
    """Refusal before mutation: rc=2 and mutation_count unchanged."""

    def __init__(self, code: str, hint: str = "", rc: int = 2) -> None:
        self.code = code
        self.hint = hint
        self.rc = rc
        super().__init__(f"{code}: {hint}")


class ExecutionFailure(Exception):
    def __init__(self, code: str, receipt: "StepReceipt") -> None:
        self.code = code
        self.receipt = receipt
        super().__init__(f"{code}: step {receipt.stepId} rc={receipt.rc}")


# ---------------------------------------------------------------------------
# guards (named pure functions so red-team mutation control can patch them)
# ---------------------------------------------------------------------------

def guard_bridge_sha(ctx: "Context") -> bool:
    if ctx.expected_bridge_sha256 is None:
        return True
    return ctx.bridge_sha256 == ctx.expected_bridge_sha256


def guard_home_match(ctx: "Context") -> bool:
    if ctx.home_expected is None:
        return True
    return Path(ctx.home).resolve() == Path(ctx.home_expected).resolve()


def guard_no_legacy_run(ctx: "Context") -> bool:
    return not ctx.run_exists


def guard_rig_absent(ctx: "Context") -> bool:
    return not ctx.rig_exists


def guard_workflow_absent(ctx: "Context") -> bool:
    return not ctx.workflow_exists


def guard_daemon_identity(ctx: "Context") -> bool:
    if not ctx.daemon_running:
        return True
    return ctx.daemon_pid is not None and ctx.daemon_pid == ctx.healthz_pid


def guard_port_collision(ctx: "Context") -> bool:
    if ctx.port_owner_home is None:
        return True
    return Path(ctx.port_owner_home).resolve() == Path(ctx.home).resolve()


def guard_launch_ttl(launch: "Launch", now: str, ttl_seconds: int | None = None) -> bool:
    limit = ttl_seconds if ttl_seconds is not None else launch.ttlSeconds
    age = (parse_dt(now) - parse_dt(launch.createdAt)).total_seconds()
    return 0 <= age <= limit


def guard_verb_unconsumed(launch: "Launch", verb: str) -> bool:
    return verb not in launch.consumed


def guard_continuity_allow(plan_obj: continuity.ContinuityPlan) -> bool:
    return plan_obj.decisionStatus == "allow"


def guard_fresh_authorized(plan_obj: continuity.ContinuityPlan) -> bool:
    for seat in plan_obj.seats:
        if seat["expectedAction"] == "fresh-primed":
            if not seat.get("freshAuthorized") or not (seat.get("freshReason") or "").strip():
                return False
    return True


def guard_node_identity(seats: Sequence[continuity.SeatFacts]) -> bool:
    for seat in seats:
        if seat.plannedNodeId is not None and seat.nodeId is not None and seat.plannedNodeId != seat.nodeId:
            return False
    return True


def guard_seat_outcome_match(expected: dict, actual: dict) -> bool:
    return all(actual.get(key) == value for key, value in expected.items())


def guard_archive_complete(gate_result: archive.ArchiveGate) -> bool:
    return gate_result.ok and gate_result.status == "COMPLETE"


GUARD_REGISTRY = {
    name: value
    for name, value in globals().items()
    if name.startswith("guard_") and callable(value)
}


# ---------------------------------------------------------------------------
# context
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SeatStatus:
    logicalId: str
    canonicalSessionName: str
    nodeId: str | None = None
    observation: Observation | None = None
    resumeTokenPresent: bool | str = "unknown"
    restorePolicy: str = "resume_if_possible"
    plannedNodeId: str | None = None

    @property
    def ready(self) -> bool:
        return self.observation is None or self.observation.session == "present"


@dataclass(frozen=True)
class Context:
    run_dir: Path
    home: Path
    project: Path
    rig_name: str = "fixture-rig"
    workflow_id: str = "fixture-workflow"
    port: int = 39411
    bridge: dict = field(default_factory=dict)
    bridge_sha256: str = ""
    expected_bridge_sha256: str | None = None
    home_expected: Path | None = None
    run_exists: bool = False
    rig_exists: bool = False
    workflow_exists: bool = False
    daemon_running: bool = False
    daemon_pid: int | None = None
    healthz_pid: int | None = None
    port_owner_home: Path | None = None
    seats: tuple[SeatStatus, ...] = ()
    orphans: tuple[str, ...] = ()
    archive_manifest: dict | None = None
    runtime_applicability: str | None = None
    state_unknown: bool = False

    @property
    def bridge_path(self) -> Path:
        return Path(self.run_dir) / "openrig" / "OPENRIG-BRIDGE.json"

    @property
    def rig_spec(self) -> Path:
        return Path(self.run_dir) / "openrig" / "rig.yaml"

    @property
    def workflow_spec(self) -> Path:
        return Path(self.run_dir) / "openrig" / "workflow.yaml"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_context(
    run_dir: Path,
    *,
    home: Path | None = None,
    project: Path | None = None,
    rig_name: str = "fixture-rig",
    workflow_id: str = "fixture-workflow",
    run_id: str = "fixture-run",
    port: int = 39411,
    bridge: dict | None = None,
    write_marker: bool = True,
    seats: Sequence[SeatStatus] = (),
    tmp_root: Path | None = None,
    **flags: object,
) -> Context:
    """Create a disposable run home + bridge (and S1 marker by default)."""
    root = Path(tmp_root) if tmp_root is not None else Path(run_dir).resolve().parent
    run_dir = assert_fixture_home(run_dir, tmp_root=root)
    home = Path(home) if home is not None else run_dir / "home"
    home = assert_fixture_home(home, tmp_root=root)
    project = Path(project) if project is not None else run_dir / "project"
    project.mkdir(parents=True, exist_ok=True)
    (run_dir / "openrig").mkdir(parents=True, exist_ok=True)
    home.mkdir(parents=True, exist_ok=True)

    bridge_doc = {
        "schemaVersion": 2,
        "runId": run_id,
        "rigName": rig_name,
        "workflowId": workflow_id,
        "home": str(home),
        "port": port,
        "project": str(project),
    }
    if bridge:
        bridge_doc.update(bridge)
    bridge_path = run_dir / "openrig" / "OPENRIG-BRIDGE.json"
    bridge_path.write_text(json.dumps(bridge_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if write_marker:
        entry = home / "entry"
        entry.mkdir(parents=True, exist_ok=True)
        (entry / "managed-run.json").write_text(
            json.dumps(
                {
                    "runId": bridge_doc["runId"],
                    "rigName": bridge_doc["rigName"],
                    "workflowId": bridge_doc["workflowId"],
                    "home": str(home),
                    "port": bridge_doc["port"],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    sha = _sha256_file(bridge_path)
    base = Context(
        run_dir=run_dir,
        home=home,
        project=project,
        rig_name=rig_name,
        workflow_id=workflow_id,
        bridge=bridge_doc,
        bridge_sha256=sha,
        expected_bridge_sha256=sha,
        home_expected=home,
        seats=tuple(seats),
    )
    known = {
        "run_exists": False,
        "rig_exists": False,
        "workflow_exists": False,
        "daemon_running": False,
        "daemon_pid": None,
        "healthz_pid": None,
        "port_owner_home": None,
        "orphans": (),
        "archive_manifest": None,
        "runtime_applicability": None,
        "state_unknown": False,
    }
    unknown = {key: value for key, value in flags.items() if key not in known}
    if unknown:
        raise TypeError(f"unknown context flag(s): {sorted(unknown)}")
    return replace(base, **flags)  # type: ignore[arg-type]


@dataclass(frozen=True)
class ContextVerdict:
    tier: str
    bridge: dict | None
    marker: dict | None
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return fixture_mark(FIXTURE_ID, tier=self.tier, warnings=list(self.warnings))


def detect_context(run_dir: Path) -> ContextVerdict:
    """Classify a run home as S1 (marker) / S2 (legacy name) / unmanaged."""
    bridge_path = Path(run_dir) / "openrig" / "OPENRIG-BRIDGE.json"
    if not bridge_path.is_file():
        return ContextVerdict("unmanaged", None, None, ("bridge_missing",))
    bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
    home = Path(bridge.get("home") or Path(run_dir) / "home")
    marker_path = home / "entry" / "managed-run.json"
    marker = json.loads(marker_path.read_text(encoding="utf-8")) if marker_path.is_file() else None

    if marker is not None and marker.get("runId") == bridge.get("runId"):
        return ContextVerdict("S1", bridge, marker, ())
    if marker is not None:
        return ContextVerdict("unmanaged", bridge, marker, ("marker_run_mismatch",))
    if home.name.startswith("openrig-workflow-"):
        return ContextVerdict("S2", bridge, None, ("legacy_home_warning",))
    return ContextVerdict("unmanaged", bridge, None, ("no_managed_run_marker",))


@dataclass(frozen=True)
class DirectCall:
    ok: bool
    rc: int
    code: str | None
    warning: str | None = None

    def to_dict(self) -> dict:
        return fixture_mark(FIXTURE_ID, ok=self.ok, rc=self.rc, code=self.code, warning=self.warning)


def authorize_direct(
    verdict: ContextVerdict,
    verb: str,
    audit: list | None = None,
) -> DirectCall:
    """Raw lifecycle verbs: deny on S1, warn+audit on S2 (HF-053)."""
    if verdict.tier == "S1":
        if audit is not None:
            audit.append({"event": "deny_lifecycle_verb", "verb": verb, "tier": "S1"})
        return DirectCall(False, 2, "lifecycle_not_authorized")
    if verdict.tier == "S2":
        if audit is not None:
            audit.append({"event": "allow_direct_warn", "verb": verb, "tier": "S2"})
        return DirectCall(True, 0, None, "legacy_home_warning")
    if audit is not None:
        audit.append({"event": "unmanaged_direct", "verb": verb, "tier": "unmanaged"})
    return DirectCall(True, 0, None, None)


# ---------------------------------------------------------------------------
# launch / receipts / outcome
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Launch:
    launchId: str
    intent: str
    createdAt: str
    phase: str = "starting"
    consumed: tuple[str, ...] = ()
    ttlSeconds: int = 1800

    def to_dict(self) -> dict:
        return fixture_mark(
            FIXTURE_ID,
            launchId=self.launchId,
            intent=self.intent,
            createdAt=self.createdAt,
            phase=self.phase,
            consumed=list(self.consumed),
            ttlSeconds=self.ttlSeconds,
        )

    def with_consumed(self, verb: str) -> "Launch":
        return replace(self, consumed=tuple(list(self.consumed) + [verb]))


@dataclass(frozen=True)
class StepReceipt:
    operationId: str
    stepId: str
    cmd: tuple[str, ...]
    cwd: str
    startedAt: str
    endedAt: str
    rc: int
    stdoutSha256: str | None
    stderrSha256: str | None
    evidencePath: str
    stateBefore: str
    stateAfter: str
    partial: bool = False
    redacted: bool = False

    def to_dict(self) -> dict:
        return {
            "operationId": self.operationId,
            "stepId": self.stepId,
            "cmd": list(self.cmd),
            "cwd": self.cwd,
            "startedAt": self.startedAt,
            "endedAt": self.endedAt,
            "rc": self.rc,
            "stdoutSha256": self.stdoutSha256,
            "stderrSha256": self.stderrSha256,
            "evidencePath": self.evidencePath,
            "stateBefore": self.stateBefore,
            "stateAfter": self.stateAfter,
            "partial": self.partial,
            "redacted": self.redacted,
        }


@dataclass
class Outcome:
    ok: bool
    rc: int
    code: str | None = None
    hint: str | None = None
    mutated: bool = False
    steps: list[StepReceipt] = field(default_factory=list)
    manifestPath: str | None = None
    state: str = ""
    payload: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return fixture_mark(
            FIXTURE_ID,
            ok=self.ok,
            rc=self.rc,
            code=self.code,
            hint=self.hint,
            mutated=self.mutated,
            steps=[step.to_dict() for step in self.steps],
            manifestPath=self.manifestPath,
            state=self.state,
            payload=self.payload,
        )


# ---------------------------------------------------------------------------
# simulator
# ---------------------------------------------------------------------------

class SupervisorSim:
    def __init__(
        self,
        ctx: Context,
        *,
        runner,
        clock: Clock,
        ids: IdFactory,
        run_id: str | None = None,
    ) -> None:
        self.ctx = ctx
        self.runner = runner
        self.clock = clock
        self.ids = ids
        self.run_id = run_id or ctx.bridge.get("runId", "fixture-run")
        self.state = "EMPTY"
        self.mutation_count = 0
        self.receipts: list[StepReceipt] = []
        self.manifest_path: Path | None = None
        self.manifest: dict | None = None
        self.launch: Launch | None = None
        self.audit: list[dict] = []
        self.workflow: dict | None = None
        self.manifest_id = f"FIX-{self.ids.next()}"
        self._operation_id = self.ids.next()

    # -- guards ---------------------------------------------------------
    def _run_guards(self, checks) -> None:
        for name, args, kwargs in checks:
            guard = globals().get(name)
            if guard is None:  # pragma: no cover - defensive
                raise Rejection("guard_missing", hint=name)
            if not guard(*args, **kwargs):
                raise Rejection(GUARD_CODES[name], hint=GUARD_HINTS.get(name, ""))

    def _context_checks(self):
        return [
            ("guard_bridge_sha", (self.ctx,), {}),
            ("guard_home_match", (self.ctx,), {}),
            ("guard_no_legacy_run", (self.ctx,), {}),
            ("guard_rig_absent", (self.ctx,), {}),
            ("guard_workflow_absent", (self.ctx,), {}),
            ("guard_daemon_identity", (self.ctx,), {}),
            ("guard_port_collision", (self.ctx,), {}),
        ]

    def _require_state(self, command: str) -> None:
        allowed = COMMAND_STATES[command]
        if self.state not in allowed:
            raise Rejection(
                "illegal_transition",
                hint=f"{command} requires {list(allowed)}; current state is {self.state}",
            )

    # -- launch ---------------------------------------------------------
    @property
    def entry_dir(self) -> Path:
        return Path(self.ctx.home) / "entry"

    def _launch_path(self) -> Path:
        return self.entry_dir / "launch.json"

    def _load_launch(self) -> Launch | None:
        path = self._launch_path()
        if not path.is_file():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Launch(
            launchId=raw["launchId"],
            intent=raw.get("intent", "start"),
            createdAt=raw["createdAt"],
            phase=raw.get("phase", "starting"),
            consumed=tuple(raw.get("consumed") or ()),
            ttlSeconds=int(raw.get("ttlSeconds", DEFAULT_TTL.get(raw.get("intent", "start"), 1800))),
        )

    def _write_launch(self, launch: Launch) -> None:
        path = self._launch_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(launch.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)

    def _call_guard(self, name: str, *args, **kwargs) -> bool:
        guard = globals().get(name)
        if guard is None:  # pragma: no cover - defensive
            raise Rejection("guard_missing", hint=name)
        return guard(*args, **kwargs)

    def _prepare_launch(self, intent: str, env: dict | None) -> Launch:
        env = env or {}
        loaded = self._load_launch()
        if loaded is not None and loaded.intent == intent and loaded.phase != "closed":
            if not self._call_guard("guard_launch_ttl", loaded, self.clock.peek()):
                raise Rejection("stale_launch", hint=GUARD_HINTS["guard_launch_ttl"])
            if not self._call_guard("guard_verb_unconsumed", loaded, intent):
                raise Rejection("launch_verb_consumed", hint=GUARD_HINTS["guard_verb_unconsumed"])
            launch = loaded
        else:
            # a different intent gets a new launchId; daemon restarts never
            # reuse a previous launch record (CONTRACT §7)
            launch = Launch(
                launchId=self.ids.next(),
                intent=intent,
                createdAt=self.clock.now(),
                ttlSeconds=DEFAULT_TTL.get(intent, 1800),
            )
        forged = env.get("OPENRIG_ENTRY_LAUNCH_ID")
        if forged:
            self.audit.append(
                {
                    "event": "provenance_overridden",
                    "envKey": "OPENRIG_ENTRY_LAUNCH_ID",
                    "forged": str(forged),
                    "actual": launch.launchId,
                }
            )
        self.launch = launch
        return launch

    def _activate_launch(self) -> None:
        """Write the launch record only after the decision to mutate is allow."""
        if self.launch is None:  # pragma: no cover - defensive
            raise Rejection("launch_missing")
        self._write_launch(self.launch)

    def _consume(self, verb: str) -> None:
        if self.launch is None:  # pragma: no cover - defensive
            raise Rejection("launch_missing")
        self.launch = self.launch.with_consumed(verb)
        self._write_launch(self.launch)

    # -- evidence -------------------------------------------------------
    def _evidence_dir(self) -> Path:
        return Path(self.ctx.run_dir) / "reports" / "evidence"

    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)

    def _commit_step(self, receipt: StepReceipt) -> None:
        self.receipts.append(receipt)
        self.mutation_count += 1
        index = len(self.receipts) - 1
        path = self._evidence_dir() / "steps" / f"{index:02d}-{receipt.stepId}.json"
        self._write_json(path, receipt.to_dict())

    def _execute(
        self,
        step_id: str,
        argv: Sequence[str],
        *,
        before: str,
        after: str,
        verb: str | None = None,
    ) -> StepReceipt:
        call = self.runner.run(tuple(argv), cwd=str(self.ctx.project))
        index = len(self.receipts)
        receipt = StepReceipt(
            operationId=self._operation_id,
            stepId=step_id,
            cmd=tuple(argv),
            cwd=str(self.ctx.project),
            startedAt=call.startedAt,
            endedAt=call.endedAt,
            rc=call.rc,
            stdoutSha256=call.stdoutSha256,
            stderrSha256=call.stderrSha256,
            evidencePath=f"reports/evidence/steps/{index:02d}-{step_id}.json",
            stateBefore=before,
            stateAfter=after if call.rc == 0 else before,
            partial=call.rc != 0,
            redacted=call.redacted,
        )
        self._commit_step(receipt)
        if call.rc != 0:
            raise ExecutionFailure(call.code or "step_failed", receipt)
        if verb is not None:
            self._consume(verb)
        self.state = after
        return receipt

    # -- manifests ------------------------------------------------------
    def _run_context(self) -> dict:
        return {
            "runDir": str(self.ctx.run_dir),
            "bridgePath": str(self.ctx.bridge_path),
            "bridgeSha256": self.ctx.bridge_sha256,
            "openrigHome": str(self.ctx.home),
            "daemonPort": self.ctx.port,
            "openrigCli": "fixture",
            "supervisorVersion": "fixture-F-02",
            "productGitSha": None,
            "workflowGroupGitSha": None,
            "fixture": True,
            "contractVersion": 1,
            "fixtureId": FIXTURE_ID,
        }

    def _inputs(self) -> list[dict]:
        candidates = (
            (self.ctx.bridge_path, "bridge", True),
            (self.ctx.rig_spec, "rig-spec", True),
            (self.ctx.workflow_spec, "workflow-spec", False),
            (Path(self.ctx.run_dir) / "openrig" / "render-manifest.json", "render-manifest", False),
            (self.entry_dir / "managed-run.json", "managed-run-marker", False),
        )
        rows: list[dict] = []
        for path, kind, required in candidates:
            path = Path(path)
            if not path.is_file():
                continue
            rows.append(
                {
                    "kind": kind,
                    "path": str(path),
                    "sha256": _sha256_file(path),
                    "bytes": path.stat().st_size,
                    "required": required,
                }
            )
        return rows

    def _seat_rows(self, *, expected: str = "new", actual: str = "ready") -> list[dict]:
        rows: list[dict] = []
        for seat in self.ctx.seats:
            row = {
                "logicalId": seat.logicalId,
                "canonicalSessionName": seat.canonicalSessionName,
                "nodeId": seat.nodeId,
                "expectedAction": expected,
                "actualOutcome": actual,
                "freshAuthorized": False,
                "freshReason": None,
                "evidencePath": None,
                "resumeTokenPresent": seat.resumeTokenPresent,
            }
            if seat.observation is not None:
                row.update(
                    {
                        "session": seat.observation.session,
                        "activity": seat.observation.activity,
                        "evidence": seat.observation.evidence,
                        "evidenceReasons": list(seat.observation.evidenceReasons),
                    }
                )
            rows.append(row)
        return rows

    def _archive_row(self) -> dict:
        manifest = self.ctx.archive_manifest or {"archiveStatus": "MISSING"}
        return {
            "manifestPath": None,
            "archiveStatus": manifest.get("archiveStatus", "MISSING"),
            "required": dict(manifest.get("required") or {}),
            "checkedAt": None,
        }

    def _manifest_doc(self, *, status: str, seats: list[dict] | None = None, env: dict | None = None) -> dict:
        doc = {
            "schemaVersion": MANIFEST_SCHEMA_VERSION,
            "manifestId": self.manifest_id,
            "runId": self.run_id,
            "launchId": self.launch.launchId if self.launch else "no-launch",
            "intent": "resume" if (self.launch and self.launch.intent == "resume") else "fresh",
            "generatedAt": self.clock.peek(),
            "revision": 1,
            "runContext": self._run_context(),
            "envKeys": sorted((env or {}).keys()),
            "inputs": self._inputs(),
            "steps": [receipt.to_dict() for receipt in self.receipts],
            "seats": self._seat_rows() if seats is None else seats,
            "workflow": self.workflow
            or {
                "instanceId": "not-instantiated",
                "entryQitemId": "not-instantiated",
                "specPath": str(self.ctx.workflow_spec),
            },
            "archive": self._archive_row(),
            "outputs": [],
            "status": status,
        }
        return doc

    def write_manifest(self, *, status: str, seats: list[dict] | None = None, env: dict | None = None) -> Path:
        path = self._evidence_dir() / "manifest" / "run-manifest.json"
        doc = self._manifest_doc(status=status, seats=seats, env=env)
        self._write_json(path, doc)
        self.manifest = doc
        self.manifest_path = path
        return path

    def _write_partial(
        self,
        *,
        failed: StepReceipt | None,
        executed: Sequence[StepReceipt],
        not_executed: Sequence[str],
        code: str,
    ) -> Path:
        path = self._evidence_dir() / "manifest" / "run-manifest.partial.json"
        payload = fixture_mark(
            FIXTURE_ID,
            schemaVersion=MANIFEST_SCHEMA_VERSION,
            partial=True,
            status="failed",
            runId=self.run_id,
            launchId=self.launch.launchId if self.launch else "no-launch",
            generatedAt=self.clock.now(),
            error={"code": code},
            failed=failed.to_dict() if failed is not None else None,
            executed=[receipt.to_dict() for receipt in executed],
            notExecuted=list(not_executed),
        )
        self._write_json(path, payload)
        return path

    # -- outcomes -------------------------------------------------------
    def _ok(self, *, payload: dict | None = None, rc: int = 0, manifest: Path | None = None) -> Outcome:
        return Outcome(
            True,
            rc,
            mutated=self.mutation_count > 0,
            steps=list(self.receipts),
            manifestPath=str(manifest or self.manifest_path) if (manifest or self.manifest_path) else None,
            state=self.state,
            payload=payload or {},
        )

    def _reject(self, rejection: Rejection) -> Outcome:
        return Outcome(
            False,
            rejection.rc,
            code=rejection.code,
            hint=rejection.hint,
            mutated=False,
            steps=[],
            manifestPath=None,
            state=self.state,
            payload={},
        )

    def _fail(
        self,
        *,
        code: str,
        hint: str,
        failed: StepReceipt | None,
        executed: Sequence[StepReceipt],
        not_executed: Sequence[str],
        rc: int = 1,
        state: str | None = None,
    ) -> Outcome:
        partial = self._write_partial(
            failed=failed, executed=executed, not_executed=not_executed, code=code
        )
        if state is not None:
            self.state = state
        return Outcome(
            False,
            rc,
            code=code,
            hint=hint,
            mutated=True,
            steps=list(executed) + ([failed] if failed else []),
            manifestPath=str(partial),
            state=self.state,
            payload={"partial": True},
        )

    # -- commands -------------------------------------------------------
    def check(self) -> Outcome:
        try:
            self._require_state("check")
            self._run_guards(self._context_checks())
        except Rejection as rejection:
            return self._reject(rejection)
        self.state = "PREPARED"
        return self._ok(
            payload={
                "checks": [{"id": "bridge", "ok": True}],
                "next": list(CANONICAL_NEXT),
                "degraded": [],
            }
        )

    def next(self) -> Outcome:
        steps = [
            {"name": name, "ordinal": index + 1} for index, name in enumerate(CANONICAL_NEXT)
        ]
        return self._ok(payload={"steps": steps})

    def start(
        self,
        *,
        env: dict | None = None,
        root_objective: str = "fixture objective",
        created_by: str = "fixture@fixture",
    ) -> Outcome:
        try:
            self._require_state("start")
            self._run_guards(self._context_checks())
            launch = self._prepare_launch("start", env)
        except Rejection as rejection:
            return self._reject(rejection)
        self._activate_launch()

        canonical = ["daemon-start", "up", "seats-ready", "workflow-validate", "workflow-instantiate"]

        def remaining_after(stage: str) -> list[str]:
            return canonical[canonical.index(stage) + 1 :]

        executed: list[StepReceipt] = []

        if self.state == "EMPTY":
            self.state = "PREPARED"

        # daemon (CT-02: a running daemon is not a deadlock)
        if not self.ctx.daemon_running:
            try:
                receipt = self._execute(
                    "daemon-start",
                    ("rig", "daemon", "start", "--no-kernel", "--port", str(self.ctx.port)),
                    before="PREPARED",
                    after="DAEMON_READY",
                )
            except ExecutionFailure as failure:
                return self._fail(
                    code=failure.code,
                    hint="daemon start failed; partial evidence written",
                    failed=failure.receipt,
                    executed=executed,
                    not_executed=remaining_after("daemon-start"),
                )
            executed.append(receipt)
            self.state = "DAEMON_READY"
        else:
            self.state = "DAEMON_READY"

        try:
            up_receipt = self._execute(
                "up",
                ("rig", "up", str(self.ctx.rig_spec), "--cwd", str(self.ctx.project), "--yes"),
                before="DAEMON_READY",
                after="RIG_READY",
                verb="start",
            )
        except ExecutionFailure as failure:
            return self._fail(
                code=failure.code,
                hint="rig up failed; partial evidence written",
                failed=failure.receipt,
                executed=executed,
                not_executed=remaining_after("up"),
            )
        executed.append(up_receipt)

        # seat readiness (program probe, not LLM narrative)
        pending = [seat.logicalId for seat in self.ctx.seats if not seat.ready]
        if not self.ctx.seats:
            pending = ["<no seats declared>"]
        if pending:
            return self._fail(
                code="seats_not_ready",
                hint=f"seats not ready: {pending}",
                failed=None,
                executed=executed,
                not_executed=remaining_after("seats-ready"),
            )
        self.state = "VALIDATED"

        try:
            validate_receipt = self._execute(
                "workflow-validate",
                ("rig", "workflow", "validate", "--rig", self.ctx.rig_name),
                before="VALIDATED",
                after="VALIDATED",
            )
        except ExecutionFailure as failure:
            return self._fail(
                code=failure.code,
                hint="workflow validate failed; partial evidence written",
                failed=failure.receipt,
                executed=executed,
                not_executed=remaining_after("workflow-validate"),
            )
        executed.append(validate_receipt)

        try:
            instantiate_receipt = self._execute(
                "workflow-instantiate",
                (
                    "rig",
                    "workflow",
                    "instantiate",
                    "--root-objective",
                    root_objective,
                    "--created-by",
                    created_by,
                    "--rig",
                    self.ctx.rig_name,
                ),
                before="VALIDATED",
                after="INSTANTIATED",
            )
        except ExecutionFailure as failure:
            return self._fail(
                code=failure.code,
                hint="workflow instantiate failed; partial evidence written",
                failed=failure.receipt,
                executed=executed,
                not_executed=remaining_after("workflow-instantiate"),
            )
        executed.append(instantiate_receipt)
        self.state = "INSTANTIATED"
        self.workflow = {
            "instanceId": f"wf-{self.launch.launchId}",
            "entryQitemId": f"qitem-{self.launch.launchId}",
            "specPath": str(self.ctx.workflow_spec),
            "specSha256": None,
            "operationKey": self._operation_id,
        }
        manifest = self.write_manifest(status="active", env=env)
        return self._ok(
            payload={
                "instanceId": self.workflow["instanceId"],
                "entryQitemId": self.workflow["entryQitemId"],
                "launchId": self.launch.launchId if self.launch else None,
                "audit": list(self.audit),
            },
            manifest=manifest,
        )

    def resume(
        self,
        *,
        explicit_fresh: Sequence[tuple[str, str]] = (),
        actual_outcomes: dict | None = None,
        env: dict | None = None,
    ) -> Outcome:
        try:
            self._require_state("resume")
            launch = self._prepare_launch("resume", env)
        except Rejection as rejection:
            return self._reject(rejection)

        facts = [
            continuity.SeatFacts(
                logicalId=seat.logicalId,
                canonicalSessionName=seat.canonicalSessionName,
                nodeId=seat.nodeId,
                plannedNodeId=seat.plannedNodeId,
                resumeTokenPresent=seat.resumeTokenPresent,
                restorePolicy=seat.restorePolicy,
                observation=seat.observation,
            )
            for seat in self.ctx.seats
        ]
        plan_obj = continuity.plan(
            facts,
            explicit_fresh,
            run_id=self.run_id,
            launch_id=launch.launchId,
            generated_at=self.clock.peek(),
        )
        plan_path = self._evidence_dir() / "manifest" / "continuity-plan.json"

        try:
            self._run_guards(
                [
                    # node identity decides first so its false branch is load-bearing
                    ("guard_node_identity", (facts,), {}),
                    ("guard_continuity_allow", (plan_obj,), {}),
                    ("guard_fresh_authorized", (plan_obj,), {}),
                ]
            )
        except Rejection as rejection:
            return self._reject(rejection)

        # decision is allow: evidence write happens before the live mutation
        self._write_json(plan_path, plan_obj.to_dict())
        self.state = "CONTINUITY_PLAN"
        self._activate_launch()
        self._consume("resume")
        try:
            receipt = self._execute(
                "up-existing",
                ("rig", "up", self.ctx.rig_name, "--existing"),
                before="CONTINUITY_PLAN",
                after="RESUMING",
            )
        except ExecutionFailure as failure:
            return self._fail(
                code=failure.code,
                hint="rig up --existing failed; partial evidence written",
                failed=failure.receipt,
                executed=[],
                not_executed=["verify-outcomes", "attach-workflow"],
            )

        actual = dict(actual_outcomes) if actual_outcomes is not None else continuity.default_outcomes(plan_obj)
        expected_map = continuity.expected_outcome_map(plan_obj)
        matched = self._call_guard("guard_seat_outcome_match", expected_map, actual)
        if not matched:
            check = continuity.verify_outcomes(plan_obj, actual)
            return self._fail(
                code=check.code or "continuity_mismatch",
                hint="actual outcome differs from expectedAction; not instantiating",
                failed=receipt,
                executed=[],
                not_executed=["attach-workflow"],
                rc=2,
                state="FAILED",
            )

        self.state = "RUNNING"
        seats = []
        for row in plan_obj.seats:
            seat_row = dict(row)
            seat_row["actualOutcome"] = actual.get(seat_row["logicalId"], seat_row["actualOutcome"])
            seats.append(seat_row)
        manifest = self.write_manifest(status="active", seats=seats, env=env)
        return self._ok(
            payload={
                "continuityPlanPath": str(plan_path),
                "decisionStatus": plan_obj.decisionStatus,
                "actualOutcomes": actual,
                "audit": list(self.audit),
            },
            manifest=manifest,
        )

    def status(self) -> Outcome:
        drifts: list[dict] = []
        if not guard_daemon_identity(self.ctx):
            drifts.append({"code": "daemon_identity_mismatch"})
        if not guard_home_match(self.ctx):
            drifts.append({"code": "run_home_mismatch"})
        if not guard_port_collision(self.ctx):
            drifts.append({"code": "port_collision"})
        if self.ctx.orphans:
            drifts.append({"code": "orphan_detected", "items": list(self.ctx.orphans)})
        if self.ctx.state_unknown:
            drifts.append({"code": "run_state_unknown"})
        if self.launch is not None and not guard_launch_ttl(self.launch, self.clock.peek()):
            drifts.append({"code": "stale_launch"})
        seats = [seat.observation.to_dict() if seat.observation else {} for seat in self.ctx.seats]
        return Outcome(
            ok=not drifts,
            rc=0 if not drifts else 1,
            mutated=False,
            steps=[],
            manifestPath=None,
            state=self.state,
            payload={"drifts": drifts, "seats": seats, "next": list(CANONICAL_NEXT)},
        )

    def stop(self, *, env: dict | None = None) -> Outcome:
        try:
            self._require_state("stop")
            gate_result = archive.gate(
                self.ctx.archive_manifest or {"archiveStatus": "MISSING"},
                runtime_applicability=self.ctx.runtime_applicability,
            )
            self._run_guards([("guard_archive_complete", (gate_result,), {})])
        except Rejection as rejection:
            return self._reject(rejection)

        executed: list[StepReceipt] = []
        try:
            down_receipt = self._execute(
                "down",
                ("rig", "down", self.ctx.rig_name),
                before="RUNNING",
                after="STOPPING",
            )
        except ExecutionFailure as failure:
            return self._fail(
                code=failure.code,
                hint="rig down failed; partial evidence written",
                failed=failure.receipt,
                executed=executed,
                not_executed=["daemon-stop", "orphan-check", "close-launch"],
            )
        executed.append(down_receipt)

        if self.ctx.daemon_running:
            try:
                stop_receipt = self._execute(
                    "daemon-stop",
                    ("rig", "daemon", "stop", "--home", str(self.ctx.home)),
                    before="STOPPING",
                    after="STOPPING",
                )
            except ExecutionFailure as failure:
                return self._fail(
                    code=failure.code,
                    hint="daemon stop failed; partial evidence written",
                    failed=failure.receipt,
                    executed=executed,
                    not_executed=["orphan-check", "close-launch"],
                )
            executed.append(stop_receipt)

        if self.ctx.orphans:
            return self._fail(
                code="orphan_after_stop",
                hint=f"orphans remain: {list(self.ctx.orphans)}; not killing them",
                failed=None,
                executed=executed,
                not_executed=["close-launch"],
                state="STOPPING",
            )

        self.state = "STOPPED"
        if self.launch is not None:
            self.launch = replace(self.launch, phase="closed")
            self._write_launch(self.launch)
        manifest = self.write_manifest(status="stopped", env=env)
        return self._ok(
            payload={
                "archiveGate": gate_result.to_dict(),
                "stoppedSteps": [receipt.stepId for receipt in executed],
            },
            manifest=manifest,
        )

    def archive_run(self) -> Outcome:
        """STOPPED -> ARCHIVED (after re-checking the gate)."""
        try:
            self._require_state("archive")
            gate_result = archive.gate(
                self.ctx.archive_manifest or {"archiveStatus": "MISSING"},
                runtime_applicability=self.ctx.runtime_applicability,
            )
            self._run_guards([("guard_archive_complete", (gate_result,), {})])
        except Rejection as rejection:
            return self._reject(rejection)
        self.state = "ARCHIVED"
        return self._ok(payload={"archiveGate": gate_result.to_dict()})


# Alias matching the contract verb name without shadowing ``archive`` module.
SupervisorSim.archive = SupervisorSim.archive_run  # type: ignore[attr-defined]
