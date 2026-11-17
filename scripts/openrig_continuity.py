#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""openrig_continuity.py — CONTINUITY-PLAN + fail-closed lifecycle verbs (S9 Wave B).

Contract: `runs/openrig-completion-round-20261116/reports/CONTINUITY-AND-COMPACTION.md`
§3 (plan), §4 (start/resume/stop algorithms), §7 (observation quality).
`openrig_run.py` owns the CLI; this module owns the decisions so `status`, `resume` and
`stop` cannot drift apart the way two copies of a rule always do.

The invariants this file exists to enforce:

  1. A plan is built BEFORE any live mutation, and it is written to disk as evidence
     (`reports/evidence/manifest/continuity-plan.json`) even when the answer is "no".
  2. `decisionStatus != allow` means ZERO live action: no daemon, no `up`, no
     instantiate. `rc=2` and one remediation per blocked seat.
  3. No token (or an UNVERIFIABLE token) never becomes a silent fresh. It becomes
     `awaiting-decision`, which a human or an explicit `--fresh` resolves.
  4. `resume` may only use `up <rigName> --existing`. Using `up <spec>` starts a new
     team and archives the old one, which is the failure this verb exists to prevent.
  5. `resumed` is only ever claimed from an observed outcome. `startupStatus=ready`
     proves a process is up, not that continuity held.
  6. Observation is three separate axes — `session`, `activity`, `evidence` — and
     absence is not degradation (D-016..D-019).

Fixture-only in S9: the observed state is read from the run bundle
(`openrig/continuity-state.json`). When that file is absent the module falls back to
`<cli> ps --nodes --rig <rigName> --json`, which is the live path MAIN's S10 E2E will
exercise; no live call is made by this round's tests (D-005).
"""
from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# S10 D-007 (S9-R-03) — ONE archive/orphan implementation. `openrig_gate` owns both
# readers; this module delegates instead of re-deriving the rule. The scripts directory
# is sys.path[0] when run as a script, and pytest injects it via conftest.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
import openrig_gate  # noqa: E402
import openrig_manifest as om  # noqa: E402
import openrig_runtime_output as ort  # noqa: E402

SCHEMA = 1

# --- decision codes (one per refusal; AT rows assert these, not just rc) -----------
CODE_BLOCKED = "continuity_blocked"
CODE_MISMATCH = "continuity_mismatch"
CODE_FRESH_REASON = "fresh_reason_missing"
CODE_FRESH_NOT_AUTHORIZED = "fresh_not_authorized"
CODE_ARCHIVE_INCOMPLETE = "archive_incomplete"
CODE_ORPHAN_AFTER_STOP = "orphan_after_stop"
CODE_RIG_EXISTS = "rig_exists"
CODE_NO_STATE = "continuity_state_unavailable"
CODE_INSTANCE_CONFLICT = "workflow_instance_conflict"
CODE_POST_STOP_OBSERVATION_UNAVAILABLE = "stop_observation_unavailable"
CODE_DAEMON_STOP_FAILED = "daemon_stop_failed"

# --- observation axes (§7) --------------------------------------------------------
SESSIONS = ("present", "detached", "exited", "absent")
ACTIVITIES = ("working", "idle-at-prompt", "unknown", None)
EVIDENCE_LEVELS = ("oracle", "observed", "degraded")
EVIDENCE_REASONS = (
    "hook_missing",
    "relay_401",
    "relay_503",
    "ps_unavailable",
    "transcript_unreadable",
    "no_observation_path",
    "ps_session_unknown",
    "observed_not_boolean",
)

PLAN_REL = Path("reports") / "evidence" / "manifest" / "continuity-plan.json"
PLAN_PARTIAL_REL = Path("reports") / "evidence" / "manifest" / "continuity-plan.partial.json"
STATE_REL = Path("openrig") / "continuity-state.json"
ARCHIVE_MANIFEST_REL = Path("reports") / "evidence" / "archive" / "ARCHIVE-MANIFEST.json"
RESUME_RECEIPT_REL = Path("reports") / "evidence" / "resume-receipt.json"
STOP_RECEIPT_REL = Path("reports") / "evidence" / "stop-receipt.json"

# Actions a seat may be *expected* to take, and outcomes we may *observe* (§3.1).
EXPECTED_ACTIONS = ("resume-original", "fresh-primed", "awaiting-decision", "new", "n-a")
ACTUAL_OUTCOMES = (
    "resumed",
    "fresh-primed",
    "awaiting-decision",
    "attention_required",
    "failed",
    "ready",
    "n-a",
)


# ------------------------------------------------------------------ helpers
def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _atomic_write_json(path: Path, payload: dict) -> None:
    """Locked unique-temp write shared with manifest/receipt writers."""
    om.write_atomic(path, payload)


def _redact_report_value(value: object, *secrets: object) -> object:
    """Recursively redact string values without changing keys or numeric evidence."""
    secret_values = sorted(
        {
            secret
            for secret in secrets
            if isinstance(secret, str) and secret and secret != "<redacted>"
        },
        key=len,
        reverse=True,
    )

    def walk(node: object) -> object:
        if isinstance(node, str):
            redacted = node
            for secret in secret_values:
                redacted = redacted.replace(secret, "<redacted>")
            return redacted
        if isinstance(node, dict):
            return {key: walk(item) for key, item in node.items()}
        if isinstance(node, list):
            return [walk(item) for item in node]
        if isinstance(node, tuple):
            return tuple(walk(item) for item in node)
        return node

    return walk(value)


def _redact_known_secrets(
    text: object, bridge: dict | None, *extra_secrets: object
) -> str:
    """Redact known authorization values from report-bound text only.

    Raw stdout/stderr is still hashed and counted before this projection so the
    evidence hashes keep their original meaning.
    """
    secrets: list[object] = []
    if isinstance(bridge, dict):
        secrets.append(bridge.get("_entryLaunchId"))
    secrets.extend(extra_secrets)
    return str(_redact_report_value(text, *secrets))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_bundle(run_dir: Path) -> tuple[dict | None, str | None]:
    """Read `openrig/OPENRIG-BRIDGE.json` (the same file openrig_run.py validates)."""
    path = run_dir / "openrig" / "OPENRIG-BRIDGE.json"
    if not path.is_file():
        return None, f"bridge missing: {path}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return None, f"bridge is not valid JSON: {path}: {exc}"
    if not isinstance(data, dict):
        return None, f"bridge is not a JSON object: {path}"
    # P-S10-03: private capture context; never written back to the bundle.
    data["_runtimeOutput"] = {"runDir": str(Path(run_dir).resolve())}
    return data, None


def cli_argv(bridge: dict) -> list[str]:
    import shlex

    return shlex.split(bridge.get("openrigCli") or "rig")


def _env(bridge: dict) -> dict:
    env = dict(os.environ)
    if bridge.get("openrigHome"):
        env["OPENRIG_HOME"] = str(bridge["openrigHome"])
    if bridge.get("daemonPort"):
        env["OPENRIG_PORT"] = str(bridge["daemonPort"])
    launch_id = bridge.get("_entryLaunchId")
    if launch_id:
        env["OPENRIG_ENTRY_LAUNCH_ID"] = str(launch_id)
    run_id = bridge.get("runId")
    if run_id:
        env["OPENRIG_ENTRY_RUN_ID"] = str(run_id)
    return env


def _run(cmd: list[str], bridge: dict, timeout: int = 120) -> subprocess.CompletedProcess:
    """Run one child with the shared P-S10-03 bounded/spill capture policy."""
    return ort.run_captured(
        cmd,
        env=_env(bridge),
        timeout=timeout,
        **ort.capture_kwargs(bridge),
    )


def _capture_bridge(
    bridge: dict,
    label: str,
    *,
    capture_id: str | None = None,
    secrets: object = (),
    persist: bool = True,
) -> dict:
    context = bridge.get("_runtimeOutput") if isinstance(bridge.get("_runtimeOutput"), dict) else {}
    run_dir = Path(str(context.get("runDir") or Path.cwd()))
    return ort.with_capture(
        bridge,
        run_dir=run_dir,
        label=label,
        capture_id=capture_id,
        secrets=secrets,
        persist=persist,
    )


def _capture_mutation(
    step: str,
    proc: subprocess.CompletedProcess,
    *,
    run_dir: Path,
    label: str,
    argv: list[str],
    redaction_secrets: tuple[str, ...] = (),
) -> dict:
    """Bounded mutation evidence; full bytes remain in the 0600 spill files."""
    ort.ensure_evidence(
        proc,
        run_dir=run_dir,
        label=label,
        redaction_secrets=redaction_secrets,
    )
    return ort.receipt_mutation(
        step,
        proc,
        argv=argv,
        redaction_secrets=redaction_secrets,
    )


# ------------------------------------------------------- observed state (fixture/live)
def _ps_failure_proves_daemon_down(proc: subprocess.CompletedProcess) -> bool:
    """Only a failed ps whose own output names an unreachable daemon may fall back."""
    if int(getattr(proc, "returncode", 0) or 0) == 0:
        return False
    text = f"{getattr(proc, 'stdout', '') or ''}\n{getattr(proc, 'stderr', '') or ''}".lower()
    markers = (
        "daemon not running",
        "daemon is not running",
        "daemon is down",
        "connection refused",
        "econnrefused",
        "failed to connect",
        "cannot connect to daemon",
    )
    return any(marker in text for marker in markers)


def _state_from_managed_evidence(
    run_dir: Path,
    bridge: dict,
    *,
    daemon_down_detail: str,
) -> dict | None:
    """Derive pre-resume state from persisted lifecycle evidence, without outcomes.

    A live ps failure proves the daemon is not reachable; it does not erase the bridge
    seat map or the last manifest rows. Those rows are copied as explicitly stale prior
    observations. `actualOutcome*` is deliberately dropped: it describes an earlier
    restore, not this attempt. A bridge target with no prior row is kept with an
    unknown token and `observed=false`, which blocks a silent fresh rather than
    inventing a seat or a token.
    """
    manifest = om.load_manifest(run_dir)
    seat_map = bridge.get("seatMap")
    manifest_rows = [
        row for row in ((manifest or {}).get("seats") or []) if isinstance(row, dict)
    ]
    by_id: dict[str, dict] = {}
    by_target: dict[str, dict] = {}
    for row in manifest_rows:
        if row.get("logicalId"):
            by_id[str(row["logicalId"])] = row
        if row.get("canonicalSessionName"):
            by_target[str(row["canonicalSessionName"])] = row

    def stale_row(row: dict, *, source: str, observed: bool) -> dict:
        seat = dict(row)
        if "actualOutcome" in seat:
            seat["priorActualOutcome"] = seat.get("actualOutcome")
        for key in (
            "actualOutcome",
            "actualOutcomeObserved",
            "actualOutcomeReason",
            "outcomeMatched",
        ):
            seat.pop(key, None)
        seat["observed"] = bool(observed)
        seat["observationSource"] = source
        seat["observationStale"] = True
        seat["evidence"] = "degraded"
        reasons = [
            str(reason)
            for reason in (seat.get("evidenceReasons") or [])
            if isinstance(reason, str)
        ]
        if "ps_unavailable" not in reasons:
            reasons.append("ps_unavailable")
        if not observed and "no_observation_path" not in reasons:
            reasons.append("no_observation_path")
        seat["evidenceReasons"] = list(dict.fromkeys(reasons))
        return seat

    seats: list[dict] = []
    covered_ids: set[str] = set()
    covered_targets: set[str] = set()
    valid_map = isinstance(seat_map, dict) and bool(seat_map)
    if valid_map:
        for role, target in seat_map.items():
            role = str(role)
            target = str(target)
            row = by_id.get(role) or by_target.get(target)
            if row is None:
                seats.append(
                    stale_row(
                        {
                            "logicalId": role,
                            "canonicalSessionName": target,
                            "nodeId": None,
                            "resumeTokenPresent": None,
                            "session": None,
                            "activity": None,
                            "evidenceReasons": [],
                        },
                        source="bridge.seatMap",
                        observed=False,
                    )
                )
            else:
                seats.append(stale_row(row, source="managed-manifest", observed=True))
            covered_ids.add(role)
            covered_targets.add(target)
    # Preserve manifest rows beyond the current bridge map as prior evidence as well;
    # coverage validation still uses the bridge map as the authority.
    for row in manifest_rows:
        logical_id = str(row.get("logicalId") or "")
        target = str(row.get("canonicalSessionName") or "")
        if logical_id in covered_ids or target in covered_targets:
            continue
        seats.append(stale_row(row, source="managed-manifest", observed=True))

    if not seats and manifest is None and not valid_map:
        return None

    sources = ["daemon-down-ps"]
    if manifest is not None:
        sources.append("managed-manifest")
    if valid_map:
        sources.append("bridge.seatMap")
    provenance = "+".join(sources)
    instance = str(((manifest or {}).get("workflow") or {}).get("instanceId") or "")
    if not instance:
        instance = str(bridge.get("workflowInstanceId") or "")
    return {
        "seats": seats,
        "source": provenance,
        "stateProvenance": provenance,
        "daemonState": "stopped",
        "daemonStateProvenance": f"ps --nodes failed and named an unreachable daemon: {daemon_down_detail}",
        "rigState": "unknown",
        "workflowInstanceId": instance or None,
    }


def load_observed_state(
    run_dir: Path,
    bridge: dict,
    *,
    live: bool = False,
    timeout: int = 120,
    allow_daemon_down_fallback: bool = False,
) -> tuple[dict | None, str]:
    """Return (state, source).

    A fixture bundle carries `openrig/continuity-state.json`; `source` is reported so the
    evidence never implies a live `ps` it did not make. Only when that file is absent and
    the caller allows live calls does this shell out to `ps --nodes`.

    `allow_daemon_down_fallback` is used only for PRE-resume/pre-stop state. A failed ps
    that itself says the daemon is unreachable may then be replaced by persisted manifest
    and bridge-seat evidence, with an explicit stale provenance. Post-up calls leave the
    flag false: stale evidence can never prove a fresh outcome.
    """
    path = run_dir / STATE_REL
    if path.is_file():
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            return None, f"continuity-state.json is not valid JSON: {exc}"
        if not isinstance(state, dict):
            return None, "continuity-state.json is not an object"
        state.setdefault("seats", [])
        return state, "fixture"
    if not live:
        return None, f"no observed state at {path} (fixture-only mode; pass live=True for ps)"
    observe_bridge = _capture_bridge(
        bridge,
        "observe-ps",
        capture_id=f"{bridge.get('_entryLaunchId') or bridge.get('runId') or 'run'}-observe-ps",
        persist=False,
    )
    proc = _run(
        [*cli_argv(bridge), "ps", "--nodes", "--rig", str(bridge.get("rigName")), "--json"],
        observe_bridge,
        timeout,
    )
    safe_stderr = _redact_known_secrets(
        proc.stderr or "", bridge, *_launch_record_redaction_secrets(bridge)
    )
    safe_stdout = _redact_known_secrets(
        proc.stdout or "", bridge, *_launch_record_redaction_secrets(bridge)
    )
    daemon_down = _ps_failure_proves_daemon_down(proc)
    if int(proc.returncode or 0) != 0:
        if daemon_down and allow_daemon_down_fallback:
            detail = (safe_stderr.strip() or safe_stdout.strip() or f"rc={proc.returncode}")[:300]
            fallback = _state_from_managed_evidence(
                run_dir, bridge, daemon_down_detail=detail
            )
            if fallback is not None:
                return fallback, str(fallback["stateProvenance"])
            return (
                None,
                "ps --nodes proved the daemon is down, but no managed manifest or "
                f"non-empty bridge.seatMap is available for pre-resume evidence: {detail}",
            )
        return None, f"ps --nodes failed (rc={proc.returncode}): {safe_stderr[:200]}"
    try:
        payload = json.loads(proc.stdout)
    except Exception:  # noqa: BLE001
        return (
            None,
            f"ps --nodes returned rc=0 but not JSON: {safe_stderr[:200] or safe_stdout[:200]}",
        )
    try:
        seats = _seats_from_ps(payload)
    except om.PsPayloadError as exc:
        return None, f"ps --nodes payload shape is unusable: {exc}"
    shape = "bare-list" if isinstance(payload, list) else "object"
    # S10-F-01d (N-CT-02): a ps that ANSWERED proves the daemon is reachable. Without this
    # the live state had no `daemonState`, so resume always tried `rig daemon start` — a
    # single-use verb that a managed start has already consumed.
    return (
        {
            "seats": seats,
            "source": "ps",
            "psPayloadShape": shape,
            "daemonState": "running",
            "daemonStateProvenance": "ps --nodes answered",
        },
        "ps",
    )


def _seats_from_ps(payload) -> list[dict]:
    """Map a live ps answer onto the seat contract without inventing presence/activity.

    Product rows carry `sessionStatus` and nested `agentActivity.state`; presence is
    never inferred from `runtime` or `pid`. A null/unknown sessionStatus is surfaced as
    no session plus a degraded reason, which `build_plan` then treats as a blocked
    observation instead of a hopeful "present".
    """
    rows = om.ps_rows(payload)
    out: list[dict] = []
    for row in rows:
        session = om.map_ps_session(row)
        activity = om.map_ps_activity(row)
        if session != "present":
            activity = None
        elif activity is None:
            activity = "unknown"

        reasons = row.get("evidenceReasons")
        if not isinstance(reasons, list):
            reasons = []
        reasons = [str(reason) for reason in reasons if isinstance(reason, str)]
        if session is None and om.PS_SESSION_UNKNOWN_REASON not in reasons:
            reasons.append(om.PS_SESSION_UNKNOWN_REASON)

        evidence = row.get("evidence")
        if evidence not in EVIDENCE_LEVELS:
            if session is None:
                evidence = "degraded"
            else:
                evidence = "observed" if row.get("startupStatus") == "ready" else "degraded"

        seat = {
            "logicalId": row.get("logicalId"),
            "canonicalSessionName": row.get("canonicalSessionName"),
            "nodeId": row.get("nodeId"),
            "startupStatus": row.get("startupStatus"),
            "restorePolicy": row.get("restorePolicy"),
            "session": session,
            "activity": activity,
            "evidence": evidence,
            "evidenceReasons": list(dict.fromkeys(reasons)),
            "resumeTokenPresent": om._map_ps_token(row),
            "observed": True,
            "observationSource": "ps",
        }
        if row.get("actualOutcome") in ACTUAL_OUTCOMES:
            seat["actualOutcome"] = row["actualOutcome"]
        out.append(seat)
    return out


def _outcomes_from_up(proc) -> tuple[dict[str, str], str]:
    """Per-node restore status from the REAL `up --existing --json` payload.

    S10-F-01c (N-CT-02): `ps` has no actualOutcome; the restore path does. The vocabulary
    is the product's (`resumed` / `fresh-primed` / `awaiting-decision` / `failed`), copied
    verbatim — never inferred from a session name, a timestamp, or the command's rc.
    """
    try:
        payload = json.loads(proc.stdout or "")
    except Exception:  # noqa: BLE001
        return {}, "no-up-json"
    if not isinstance(payload, dict):
        return {}, "no-up-json"
    rows = payload.get("nodes")
    if not isinstance(rows, list):
        return {}, "no-up-nodes"
    out: dict[str, str] = {}
    for row in rows:
        if isinstance(row, dict) and row.get("logicalId") and row.get("status"):
            out[str(row["logicalId"])] = str(row["status"])
    return out, "up-existing-json"


def _instance_from_manifest(run_dir: Path) -> tuple[str | None, str]:
    """The workflow instance `openrig-run start` recorded, for live resume (S10-F-01f)."""
    path = Path(run_dir) / "reports" / "evidence" / "manifest" / "run-manifest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, "no-run-manifest"
    instance = str(((data or {}).get("workflow") or {}).get("instanceId") or "")
    return (instance or None), "run-manifest"


def _apply_actual_outcomes(state: dict, outcomes: dict[str, str]) -> dict:
    """Overlay the restore status onto the observation; never fill a missing one."""
    seats: list[dict] = []
    missing: list[str] = []
    for seat in state.get("seats") or []:
        logical_id = str(seat.get("logicalId") or "")
        if logical_id in outcomes:
            seats.append({**seat, "actualOutcome": outcomes[logical_id]})
        else:
            missing.append(logical_id)
            seats.append(seat)
    return {
        **state,
        "seats": seats,
        "actualOutcomeProvenance": "up-existing-json",
        "actualOutcomeMissing": [lid for lid in missing if lid],
    }


# ------------------------------------------------------------------ observation axes
def normalize_observation(seat: dict) -> dict:
    """Split one seat's three axes and apply §7's rules. Never turns absence into
    degradation, never turns `unknown` into `idle`, never lets a non-present session
    carry an activity value (D-019)."""
    session = seat.get("session")
    if session not in SESSIONS:
        session = "absent" if not session else "detached"

    reasons = [r for r in (seat.get("evidenceReasons") or []) if r in EVIDENCE_REASONS]
    evidence = seat.get("evidence")
    if evidence not in EVIDENCE_LEVELS:
        evidence = "observed" if seat.get("activity") is not None else "degraded"

    activity = seat.get("activity")
    if session != "present":
        # D-019: null is not a fourth activity; a non-present session carries no activity.
        activity = None
        if evidence == "degraded" and not reasons:
            reasons = []
    elif activity not in ACTIVITIES:
        activity = "unknown"
    if activity == "unknown" and "oracle_unknown" in reasons:
        # §7.4: unknown is an activity fact, not an evidence degradation reason.
        reasons = [r for r in reasons if r != "oracle_unknown"]

    return {
        "session": session,
        "activity": activity,
        "evidence": evidence,
        "evidenceReasons": sorted(set(reasons)),
    }


# ------------------------------------------------------------------ stall (D-014)
def stall_verdict(observation: dict, queue_age_seconds: float | None) -> dict:
    """§7.5: age alone never proves a stall, and the absence of a signal is never health.

    - live activity  -> not stalled, whatever the queue age (a long tool call is work);
    - no live signal -> not stalled either, but the HEALTH is `degraded`, not `healthy`
      (an unobserved seat is not a proven-idle seat);
    - a genuinely idle seat with an old queue row is the only rung that can say `stalled`.
    """
    activity = observation.get("activity")
    if activity in ("working", "idle-at-prompt"):
        return {
            "stalled": False,
            "health": "observed",
            "reason": f"live activity ({activity}) — queue age does not prove a stall",
        }
    if activity is None or observation.get("evidence") == "degraded":
        return {
            "stalled": False,
            "health": "degraded",
            "reason": "no live observation; an unobserved seat is not a proven idle one",
        }
    if activity == "unknown":
        return {
            "stalled": False,
            "health": "unknown",
            "reason": "oracle could not classify the seat; age alone is not a stall",
        }
    return {
        "stalled": True,
        "health": "observed",
        "reason": "idle seat with an old queue row and a live observation",
    }


# ------------------------------------------------------------------ CONTINUITY-PLAN
def seat_observed(seat: dict, *, state_source: str) -> tuple[bool, str | None]:
    """Return whether a seat row carries a real observation.

    Historical fixture rows predate the explicit ``observed`` field; that omission is
    tolerated only when the state came from the fixture file. Live/fallback producers
    must say ``observed: true`` or the seat cannot participate in resume/coverage.
    Any present non-boolean (including the string ``"false"``) is an unobserved seat.
    """
    if "observed" not in seat:
        return (state_source == "fixture", None)
    value = seat["observed"]
    if not isinstance(value, bool):
        return (False, "observed_not_boolean")
    return (value, None)


def build_plan(
    bridge: dict,
    state: dict,
    *,
    explicit_fresh: tuple[str, ...] | list[str] = (),
    fresh_reason: str = "",
    state_source: str = "fixture",
) -> dict:
    """Build the §3.1 plan. Pure: no disk, no subprocess, no mutation."""
    fresh = [str(x) for x in explicit_fresh]
    seats_out: list[dict] = []
    blocked: list[dict] = []
    degraded: list[dict] = []
    mismatch: list[dict] = []

    seat_map = bridge.get("seatMap")
    valid_seat_map = isinstance(seat_map, dict) and bool(seat_map)
    target_to_role = {
        str(target): str(role)
        for role, target in (seat_map.items() if valid_seat_map else ())
        if str(role).strip() and str(target).strip()
    }
    seats_in: list[dict] = []
    for raw_seat in state.get("seats") or []:
        if not isinstance(raw_seat, dict):
            blocked.append(
                {
                    "logicalId": None,
                    "reason": "observed state contains a non-object seat row",
                    "remediation": "re-run the observation; malformed seat evidence is not a plan",
                }
            )
            continue
        seat = dict(raw_seat)
        if not seat.get("logicalId") and seat.get("canonicalSessionName"):
            inferred = target_to_role.get(str(seat["canonicalSessionName"]))
            if inferred:
                seat["logicalId"] = inferred
        seats_in.append(seat)

    known_ids = [str(s.get("logicalId")) for s in seats_in if s.get("logicalId")]
    unknown_fresh = [fid for fid in fresh if fid not in known_ids]

    if not valid_seat_map:
        blocked.append(
            {
                "logicalId": None,
                "reason": "bridge.seatMap is missing or empty; required seats cannot be proven",
                "remediation": "restore the managed bridge seatMap before retrying resume/status",
            }
        )
    else:
        observed_ids: set[str] = set()
        observed_targets: set[str] = set()
        for seat in seats_in:
            observed, _reason = seat_observed(seat, state_source=state_source)
            if not observed:
                continue
            logical_id = seat.get("logicalId")
            if logical_id:
                observed_ids.add(str(logical_id))
            target = seat.get("canonicalSessionName")
            if target:
                observed_targets.add(str(target))

        # An explicit fresh decision with a readable reason may stand in for an
        # observation that is unavailable (daemon-down recovery). It never does so
        # silently: the seat row is marked unobservedFresh and stays degraded.
        fresh_override_ids = {
            str(fid) for fid in fresh if fresh_reason.strip()
        }
        for role, target in seat_map.items():
            role_text = str(role)
            target_text = str(target)
            if role_text in observed_ids or target_text in observed_targets:
                continue
            if role_text in fresh_override_ids:
                continue
            blocked.append(
                {
                    "logicalId": role_text,
                    "reason": (
                        f"bridge.seatMap target {target_text!r} was not observed; "
                        "a missing seat is never a zero-seat success"
                    ),
                    "remediation": (
                        "re-establish the observation source or explicitly resolve the "
                        "missing target before resuming"
                    ),
                }
            )

    for seat in seats_in:
        logical_id = seat.get("logicalId")
        if not logical_id:
            continue
        observed, obs_reason = seat_observed(seat, state_source=state_source)
        observation = normalize_observation(seat)
        if not observed:
            reasons = list(observation["evidenceReasons"])
            if obs_reason:
                reasons.append(obs_reason)
            if "no_observation_path" not in reasons:
                reasons.append("no_observation_path")
            observation["evidence"] = "degraded"
            observation["evidenceReasons"] = sorted(
                {reason for reason in reasons if reason in EVIDENCE_REASONS}
            )
        restore_policy = seat.get("restorePolicy") or "resume_if_possible"
        token = seat.get("resumeTokenPresent")
        # `unknown` is neither true nor false (rule 10); it is recorded verbatim.
        if token is True:
            token_state = True
        elif token is False:
            token_state = False
        else:
            token_state = "unknown"

        observed_outcome = seat.get("actualOutcome")

        if not observed:
            # Only an explicit, reasoned fresh can resolve an unobserved seat.
            expected = "fresh-primed" if logical_id in fresh else "awaiting-decision"
        elif restore_policy == "n-a":
            expected = "n-a"
        elif logical_id in fresh:
            expected = "fresh-primed"
        elif token_state is True:
            expected = "resume-original"
        else:
            expected = "awaiting-decision"

        # Rule 5 — a seat observed as fresh without being authorized is a MISMATCH, and
        # it is not repairable by proceeding: a new teammate already exists.
        if observed_outcome == "fresh-primed" and logical_id not in fresh:
            mismatch.append(
                {
                    "logicalId": logical_id,
                    "reason": (
                        "observed fresh-primed outside the authorized --fresh list; "
                        "a successor session already exists"
                    ),
                    "remediation": (
                        f"re-run with --fresh {logical_id} --reason <why> to adopt it, or "
                        "restore the original session before resuming"
                    ),
                }
            )

        # Rule 3/6 — nothing to resume and nobody authorized a fresh: a human decides.
        if expected == "awaiting-decision":
            if not observed:
                reason = obs_reason or "seat was not observed"
                remediation = (
                    "re-observe the seat, or explicitly authorize "
                    f"resume --fresh {logical_id} --reason "
                    "'<why the original session is unrecoverable>'"
                )
            else:
                reason = (
                    "resume token is "
                    + ("absent" if token_state is False else "unverifiable (unknown)")
                    + "; a fresh seat is never chosen automatically"
                )
                remediation = (
                    f"confirm the session can be restored, or authorize explicitly: "
                    f"resume --fresh {logical_id} --reason '<why the old session is gone>'"
                )
            blocked.append(
                {
                    "logicalId": logical_id,
                    "reason": reason,
                    "remediation": remediation,
                }
            )
        elif expected == "fresh-primed" and not fresh_reason.strip():
            # Defensive: resume refuses this earlier, but the plan never hides it.
            blocked.append(
                {
                    "logicalId": logical_id,
                    "reason": "explicit fresh requires a non-empty reason",
                    "remediation": "pass --reason '<why the original session is unrecoverable>'",
                }
            )

        if observation["evidence"] == "degraded":
            degraded.append(
                {"logicalId": logical_id, "reasons": observation["evidenceReasons"]}
            )

        seats_out.append(
            {
                "logicalId": logical_id,
                "canonicalSessionName": seat.get("canonicalSessionName"),
                "nodeId": seat.get("nodeId"),
                "restorePolicy": restore_policy,
                "resumeTokenPresent": token_state,
                "expectedAction": expected,
                "freshAuthorized": logical_id in fresh,
                "freshReason": fresh_reason if logical_id in fresh else "",
                "evidencePath": str(PLAN_REL),
                "actualOutcome": observed_outcome,
                "observationSource": seat.get("observationSource"),
                "observed": observed,
                "observationStale": bool(seat.get("observationStale")) or not observed,
                "unobservedFresh": bool(not observed and logical_id in fresh),
                **observation,
            }
        )

    if unknown_fresh:
        blocked.append(
            {
                "logicalId": None,
                "reason": f"--fresh names seat(s) not present in this run: {unknown_fresh}",
                "remediation": "check `status`, then name a seat that exists",
            }
        )

    if mismatch:
        decision_status = "blocked"
        code = CODE_MISMATCH
    elif blocked:
        decision_status = "blocked"
        code = CODE_BLOCKED
    else:
        decision_status = "allow"
        code = None

    return {
        "schemaVersion": SCHEMA,
        "generatedAt": now(),
        "runId": bridge.get("runId"),
        "rigName": bridge.get("rigName"),
        "stateSource": state_source,
        "decisionStatus": decision_status,
        "code": code,
        "explicitFreshSeats": fresh,
        "freshReason": fresh_reason,
        "blockedSeats": blocked,
        "mismatchedSeats": mismatch,
        "degraded": degraded,
        "seats": seats_out,
        "stateBefore": _state_fingerprint({**state, "seats": seats_in}),
    }


def _state_fingerprint(state: dict) -> dict:
    """The comparable "before" image for the zero-mutation assertion: per-seat identity
    and observed status only — timestamps are deliberately excluded so a read cannot
    look like a change."""
    seats = {}
    for seat in state.get("seats") or []:
        logical_id = seat.get("logicalId")
        if not logical_id:
            continue
        seats[str(logical_id)] = {
            "nodeId": seat.get("nodeId"),
            "session": seat.get("session"),
            "startupStatus": seat.get("startupStatus"),
            "actualOutcome": seat.get("actualOutcome"),
        }
    return {
        "daemonState": state.get("daemonState"),
        "rigState": state.get("rigState"),
        "workflowInstanceId": state.get("workflowInstanceId"),
        "seats": seats,
    }


# ------------------------------------------------------------------ resume
def resume_argv(bridge: dict, plan: dict) -> list[str]:
    """`up <rigName> --existing` — never `up <spec>` (rule 9)."""
    # S10-F-01e (N-CT-02): `--json` is what makes `nodes[].status` observable. The
    # invariant this argv protects is unchanged: the target is the rig NAME + --existing,
    # never a rig SPEC file.
    argv = [*cli_argv(bridge), "up", str(bridge.get("rigName")), "--existing", "--json"]
    fresh = [s["logicalId"] for s in plan["seats"] if s["expectedAction"] == "fresh-primed"]
    if fresh:
        argv.extend(["--fresh", *fresh])
    return argv


def daemon_start_argv(bridge: dict) -> list[str]:
    argv = [*cli_argv(bridge), "daemon", "start", "--no-kernel"]
    if bridge.get("daemonPort"):
        argv.extend(["--port", str(bridge["daemonPort"])])
    return argv


def instantiate_argv(bridge: dict, run_dir: Path) -> list[str]:
    return [
        *cli_argv(bridge),
        "workflow",
        "instantiate",
        str(run_dir / "openrig" / "workflow.yaml"),
        "--root-objective",
        str(bridge.get("rootObjective") or bridge.get("objective") or f"Run {bridge.get('runId')}"),
        "--created-by",
        str(bridge.get("createdBy") or "openrig-run resume"),
        "--json",
    ]


def _manifest_attempt_launch_id(
    run_dir: Path, bridge: dict, explicit: object, intent: str
) -> str:
    """Stable-enough per-attempt launchId for a resume/stop manifest revision.

    The managed lease's launchId wins; a prior manifest is the next-best provenance;
    only then does the supervisor mint an id. It never copies a token.
    """
    if isinstance(explicit, str) and explicit:
        return explicit
    previous = om.load_manifest(run_dir)
    if previous and previous.get("launchId"):
        return str(previous["launchId"])
    entry_launch_id = bridge.get("_entryLaunchId")
    if isinstance(entry_launch_id, str) and entry_launch_id:
        return entry_launch_id
    return f"{intent}-{uuid.uuid4()}"


def _seat_evidence_summary(seats: list[dict]) -> list[dict]:
    """Small receipt projection of the manifest seats (no commands, no env values)."""
    keys = (
        "logicalId",
        "canonicalSessionName",
        "nodeId",
        "expectedAction",
        "actualOutcome",
        "session",
        "activity",
        "evidence",
        "evidenceReasons",
        "outcomeMatched",
    )
    rows = []
    for seat in seats:
        if not isinstance(seat, dict):
            continue
        rows.append({key: seat.get(key) for key in keys if key in seat})
    return rows


_MUTATION_EVIDENCE_KEYS = (
    "step",
    "rc",
    "argv",
    "stdoutSha256",
    "stderrSha256",
    "stdoutBytes",
    "stderrBytes",
    "stdoutPath",
    "stderrPath",
    "stdoutTail",
    "stderrTail",
    "stdoutTruncated",
    "stderrTruncated",
    "stdoutOmittedBytes",
    "stderrOmittedBytes",
    "evidencePath",
    "evidenceSha256",
    "evidenceBytes",
    "timedOut",
    "toleratedPartialRestore",
    "note",
)


def _mutation_evidence_summary(mutations: list[dict]) -> list[dict]:
    """Receipt projection: bounded tails and references only, never raw streams."""
    return [
        {key: row.get(key) for key in _MUTATION_EVIDENCE_KEYS if key in row}
        for row in mutations
        if isinstance(row, dict)
    ]


def _stop_manifest_seats(run_dir: Path, state: dict | None) -> list[dict]:
    """Pre-stop seat evidence, then plan, then the prior manifest.

    A failed stop must not erase the last active-seat observation merely because the
    immediate post/pre-stop state is unavailable. The manifest fallback is deliberately
    last: fresher observations win, while the prior bytes remain authoritative evidence.
    """
    seats = [seat for seat in (state or {}).get("seats") or [] if isinstance(seat, dict)]
    if seats:
        return seats
    plan = read_plan(run_dir)
    if isinstance(plan, dict):
        plan_seats = [seat for seat in plan.get("seats") or [] if isinstance(seat, dict)]
        if plan_seats:
            return plan_seats
    previous = om.load_manifest(run_dir)
    if isinstance(previous, dict):
        return [seat for seat in previous.get("seats") or [] if isinstance(seat, dict)]
    return []


def _record_resume_manifest(
    run_dir: Path,
    bridge: dict,
    plan: dict,
    *,
    launch_id: str,
    instance: str,
    mutations: list[dict],
    redaction_secrets: tuple[str, ...] = (),
) -> dict:
    """Revisioned RUN-MANIFEST update for a successful resume.

    seats[] comes from the plan's actual outcomes; outputs[] gets the continuity-plan
    and the resume receipt only when those files actually exist. The receipt is
    atomically written first and recorded by its real path/sha256/bytes.
    """
    manifest = om.revised_manifest(
        run_dir, bridge, launch_id=launch_id, intent="resume"
    )
    manifest["workflow"]["instanceId"] = str(instance or "")
    archive = archive_status(run_dir)
    om.set_archive(
        manifest,
        str(archive.get("status") or "MISSING"),
        manifest_path=str(archive.get("path") or ""),
    )

    output_specs: list[dict] = []
    plan_path = Path(run_dir) / PLAN_REL
    if plan_path.is_file():
        output_specs.append(
            {
                "path": str(plan_path),
                "producer": "openrig-continuity resume",
                "consumer": "archive/operator",
                "retention": "run",
            }
        )

    seat_rows = list(plan.get("seats") or [])
    receipt_payload = {
        "schemaVersion": SCHEMA,
        "kind": "resume-receipt",
        "runId": bridge.get("runId"),
        "launchId": launch_id,
        "capturedAt": now(),
        "status": "active",
        "manifestId": manifest.get("manifestId"),
        "revision": manifest.get("revision"),
        "workflow": {"instanceId": str(instance or "")},
        "decisionStatus": plan.get("decisionStatus"),
        "actualOutcomeVerified": bool(plan.get("actualOutcomeVerified")),
        "seats": _seat_evidence_summary(seat_rows),
        "mutationSteps": _mutation_evidence_summary(mutations),
        "stepCount": len(mutations),
    }
    receipt_payload = _redact_report_value(receipt_payload, *redaction_secrets)
    receipt = om.write_receipt(run_dir, RESUME_RECEIPT_REL, receipt_payload)
    output_specs.append(
        {
            "path": receipt["path"],
            "producer": "openrig-continuity resume",
            "consumer": "archive/operator",
            "retention": "run",
        }
    )

    om.finalize_manifest(
        manifest,
        status="active",
        seats=seat_rows,
        outputs=output_specs,
        seats_not_applicable_reason="continuity_plan_has_no_seat_rows",
        outputs_not_applicable_reason="resume_receipt_not_written",
    )
    written = om.write_manifest(run_dir, manifest)
    return {
        "ok": True,
        "path": written["path"],
        "sha256": written["sha256"],
        "revision": written["revision"],
        "manifestId": manifest.get("manifestId"),
        "seats": len(manifest.get("seats") or []),
        "outputs": len(manifest.get("outputs") or []),
        "receipt": receipt,
    }


def _record_stop_manifest(
    run_dir: Path,
    bridge: dict,
    *,
    status: str,
    ok: bool,
    code: str | None,
    detail: str,
    state: dict | None,
    archive: dict | None,
    launch_id: str,
    mutations: list[dict],
    redaction_secrets: tuple[str, ...] = (),
) -> dict:
    """Revisioned RUN-MANIFEST update for stop success or failure.

    `status` is the lifecycle truth (`stopped`/`failed`); seats[] is the pre-stop
    observation (or the plan), and outputs[] gets the archive manifest when present plus
    the stop receipt. A stop-only manifest is created when none existed.
    """
    previous = om.load_manifest(run_dir)
    manifest = om.revised_manifest(
        run_dir, bridge, launch_id=launch_id, intent="stop"
    )
    instance = str(
        (state or {}).get("workflowInstanceId")
        or ((previous or {}).get("workflow") or {}).get("instanceId")
        or bridge.get("workflowInstanceId")
        or ""
    )
    if instance:
        manifest["workflow"]["instanceId"] = instance
    if isinstance(archive, dict):
        om.set_archive(
            manifest,
            str(archive.get("status") or "MISSING"),
            manifest_path=str(archive.get("path") or ""),
        )

    output_specs: list[dict] = []
    archive_path = str((archive or {}).get("path") or "")
    if archive_path and Path(archive_path).is_file():
        output_specs.append(
            {
                "path": archive_path,
                "producer": "archive gate",
                "consumer": "archive/operator",
                "retention": "run",
            }
        )

    seat_rows = _stop_manifest_seats(run_dir, state)
    receipt_payload = {
        "schemaVersion": SCHEMA,
        "kind": "stop-receipt",
        "runId": bridge.get("runId"),
        "launchId": launch_id,
        "capturedAt": now(),
        "status": status,
        "ok": bool(ok),
        "code": code,
        # Never copy raw command output into the receipt: only its digest. A stop
        # failure message can quote a launch token we do not know by value.
        "detailSha256": hashlib.sha256(str(detail or "").encode("utf-8")).hexdigest(),
        "archive": {
            "status": (archive or {}).get("status"),
            "path": archive_path or None,
        },
        "workflow": {"instanceId": instance},
        "seats": _seat_evidence_summary(seat_rows),
        "mutationSteps": _mutation_evidence_summary(mutations),
    }
    receipt_payload = _redact_report_value(receipt_payload, *redaction_secrets)
    receipt = om.write_receipt(run_dir, STOP_RECEIPT_REL, receipt_payload)
    output_specs.append(
        {
            "path": receipt["path"],
            "producer": "openrig-continuity stop",
            "consumer": "archive/operator",
            "retention": "run",
        }
    )

    om.finalize_manifest(
        manifest,
        status=status,
        seats=seat_rows,
        outputs=output_specs,
        seats_not_applicable_reason="stop_has_no_seat_observation_or_continuity_plan",
        outputs_not_applicable_reason="stop_receipt_not_written",
    )
    written = om.write_manifest(run_dir, manifest)
    return {
        "ok": True,
        "path": written["path"],
        "sha256": written["sha256"],
        "revision": written["revision"],
        "manifestId": manifest.get("manifestId"),
        "seats": len(manifest.get("seats") or []),
        "outputs": len(manifest.get("outputs") or []),
        "receipt": receipt,
    }


def run_resume(
    run_dir: Path,
    *,
    fresh: tuple[str, ...] | list[str] = (),
    reason: str = "",
    live: bool = False,
    timeout: int = 120,
    dry_run: bool = False,
) -> dict:
    """§4.2. Returns a report; `rc`/`error.code` carry the refusal."""
    bridge, err = load_bundle(run_dir)
    if bridge is None:
        return _report("resume", run_dir, ok=False, rc=2, code="bridge_invalid", detail=err)

    known_redaction_secrets = _report_redaction_secrets(bridge)

    # Refuse before reading any state: an empty reason is an argument error, not a
    # continuity verdict, and it must not be softened into one.
    if fresh and not reason.strip():
        return _report(
            "resume",
            run_dir,
            ok=False,
            rc=2,
            code=CODE_FRESH_REASON,
            detail="--fresh requires a non-empty --reason; a fresh seat is a decision someone must be able to read later",
            redaction_secrets=known_redaction_secrets,
        )

    state, source = load_observed_state(
        run_dir,
        bridge,
        live=live,
        timeout=timeout,
        allow_daemon_down_fallback=True,
    )
    if state is None:
        return _report(
            "resume", run_dir, ok=False, rc=2, code=CODE_NO_STATE, detail=source,
            redaction_secrets=known_redaction_secrets,
        )

    plan = build_plan(
        bridge, state, explicit_fresh=tuple(fresh), fresh_reason=reason, state_source=source
    )

    # The plan is evidence of the DECISION, so it is written even when the answer is no.
    _atomic_write_json(
        run_dir / PLAN_REL,
        _redact_report_value(plan, *known_redaction_secrets),
    )

    if plan["decisionStatus"] != "allow":
        return _report(
            "resume",
            run_dir,
            ok=False,
            rc=2,
            code=plan["code"] or CODE_BLOCKED,
            detail=_refusal_detail(plan),
            plan=plan,
            extra={"mutations": [], "stateBefore": plan["stateBefore"], "stateAfter": plan["stateBefore"]},
            redaction_secrets=known_redaction_secrets,
        )

    if dry_run:
        return _report(
            "resume",
            run_dir,
            ok=True,
            rc=0,
            plan=plan,
            extra={
                "mutations": [],
                "dryRun": True,
                "resumeAuthorization": {
                    "status": "dry-run",
                    "reason": "dry-run resume does not grant a resume lease",
                },
            },
            redaction_secrets=known_redaction_secrets,
        )

    daemon_running = state.get("daemonState") == "running"
    authorization = prepare_resume_lease(
        run_dir, bridge, daemon_running=daemon_running
    )
    authorization_launch_id = (
        str(authorization.get("launchId"))
        if isinstance(authorization, dict) and authorization.get("launchId")
        else None
    )
    redaction_secrets = _report_redaction_secrets(
        bridge, authorization_launch_id, *known_redaction_secrets
    )
    resume_authorization = _redact_report_value(
        _public_resume_lease_result(authorization), *redaction_secrets
    )
    authorization_status = (
        str(authorization.get("status") or "") if isinstance(authorization, dict) else ""
    )
    if authorization_status not in ("prepared", "skipped"):
        detail = ""
        if isinstance(authorization, dict):
            detail = str(authorization.get("message") or authorization.get("reason") or "")
        detail = str(_redact_report_value(detail, *redaction_secrets))
        return _report(
            "resume",
            run_dir,
            ok=False,
            rc=2,
            code="resume_authorization_failed",
            detail=detail or "managed launch record does not authorize resume",
            plan=plan,
            extra={"mutations": [], "resumeAuthorization": resume_authorization},
            redaction_secrets=redaction_secrets,
        )

    lease = authorization if authorization_status == "prepared" else None
    exec_bridge = dict(bridge)
    lease_launch_id: str | None = None
    if lease is not None:
        lease_launch_id = str(lease["launchId"])
        exec_bridge["_entryLaunchId"] = lease_launch_id

    def redact_report_text(value: object) -> str:
        return str(_redact_report_value(value, *redaction_secrets))

    def close_prepared_resume(close_reason: str) -> None:
        if lease is None:
            return
        try:
            closed = close_resume_lease(run_dir, exec_bridge, lease, close_reason)
        except Exception as exc:  # noqa: BLE001 - report close failure, never hide it
            closed = _lease_error(
                "resume_lease_close_failed",
                f"resume lease close raised {type(exc).__name__}",
            )
        resume_authorization["leaseClosed"] = _redact_report_value(
            _public_resume_lease_result(closed), *redaction_secrets
        )

    mutations: list[dict] = []
    lease_or_attempt = str(lease_launch_id or authorization_launch_id or "resume")
    if not daemon_running:
        daemon_argv = daemon_start_argv(exec_bridge)
        daemon_bridge = _capture_bridge(
            exec_bridge,
            "daemon-start",
            capture_id=f"{lease_or_attempt}-daemon-start",
            secrets=redaction_secrets,
        )
        proc = _run(daemon_argv, daemon_bridge, timeout)
        mutation = _capture_mutation(
            "daemon-start",
            proc,
            run_dir=run_dir,
            label="daemon-start",
            argv=daemon_argv,
            redaction_secrets=redaction_secrets,
        )
        mutations.append(mutation)
        if proc.returncode != 0:
            close_prepared_resume(f"daemon start rc={proc.returncode}")
            detail = mutation.get("stderrTail") or mutation.get("stdoutTail") or ""
            return _report(
                "resume", run_dir, ok=False, rc=2, code="daemon_start_failed",
                detail=str(detail)[:300] or f"daemon start rc={proc.returncode}", plan=plan,
                extra={"mutations": mutations, "resumeAuthorization": resume_authorization},
                redaction_secrets=redaction_secrets,
            )

    up_argv = resume_argv(exec_bridge, plan)
    up_bridge = _capture_bridge(
        exec_bridge,
        "up-existing",
        capture_id=f"{lease_or_attempt}-up-existing",
        secrets=redaction_secrets,
    )
    proc = _run(up_argv, up_bridge, timeout)
    mutation = _capture_mutation(
        "up-existing",
        proc,
        run_dir=run_dir,
        label="up-existing",
        argv=up_argv,
        redaction_secrets=redaction_secrets,
    )
    mutations.append(mutation)
    # S10-F-01c/P-020: the restore status is the product's own per-node verdict. The CLI
    # exits 1 for `partially_restored` even when the target seat reached the expected
    # outcome, so rc alone is not the verdict.
    outcomes, outcome_source = _outcomes_from_up(proc)
    expected = {
        s["logicalId"]: ("fresh-primed" if s["expectedAction"] == "fresh-primed" else "resumed")
        for s in plan["seats"]
        if s.get("expectedAction") in ("resume-original", "fresh-primed")
    }
    tolerated = bool(
        proc.returncode != 0 and outcomes and expected
        and all(outcomes.get(lid) == want for lid, want in expected.items())
    )
    mutations[-1]["toleratedPartialRestore"] = tolerated
    if proc.returncode != 0 and not tolerated:
        close_prepared_resume(f"up existing rc={proc.returncode}")
        failure_output = mutation.get("stderrTail") or mutation.get("stdoutTail") or ""
        return _report(
            "resume", run_dir, ok=False, rc=2, code="up_failed",
            detail=str(failure_output)[:600] or "<no output from rig up>",
            plan=plan,
            extra={"mutations": mutations, "resumeAuthorization": resume_authorization},
            redaction_secrets=redaction_secrets,
        )
    if tolerated:
        mutations[-1]["note"] = (
            "rig up exited nonzero but every expected seat reached its planned outcome; "
            "partially_restored tolerated (P-020)")


    # Continuity is an OBSERVED outcome, never an assumption from the command's rc.
    after, after_source = load_observed_state(
        run_dir, exec_bridge, live=live, timeout=timeout
    )
    if after is not None and outcome_source == "up-existing-json":
        # Applied even when the restore named no seat: "it answered, and said nothing" is
        # evidence, and the missing ids are recorded instead of guessed.
        after = _apply_actual_outcomes(after, outcomes)
        after_source = f"{after_source}+{outcome_source}"
    if after is None:
        close_prepared_resume("post-up observation unavailable")
        return _report(
            "resume", run_dir, ok=False, rc=2, code=CODE_NO_STATE,
            detail=f"post-up observation unavailable: {redact_report_text(after_source)}",
            plan=plan,
            extra={"mutations": mutations, "resumeAuthorization": resume_authorization},
            redaction_secrets=redaction_secrets,
        )

    compared = compare_outcomes(plan, after)
    plan["seats"] = compared["seats"]
    plan["stateAfter"] = _state_fingerprint(after)
    plan["actualOutcomeVerified"] = compared["all_match"]
    _atomic_write_json(
        run_dir / PLAN_REL,
        _redact_report_value(plan, *redaction_secrets),
    )

    if not compared["all_match"]:
        close_prepared_resume("resume outcome mismatch")
        partial = {**plan, "partial": True, "mismatchReason": compared["reason"]}
        _atomic_write_json(
            run_dir / PLAN_PARTIAL_REL,
            _redact_report_value(partial, *redaction_secrets),
        )
        return _report(
            "resume", run_dir, ok=False, rc=2, code=CODE_MISMATCH,
            detail=redact_report_text(compared["reason"]), plan=plan,
            extra={"mutations": mutations, "stateAfter": plan["stateAfter"], "partial": str(PLAN_PARTIAL_REL),
                   "actualOutcomeProvenance": (after or {}).get("actualOutcomeProvenance"),
                   "actualOutcomeMissing": (after or {}).get("actualOutcomeMissing") or [],
                   "resumeAuthorization": resume_authorization},
            redaction_secrets=redaction_secrets,
        )

    # Rule: attach/verify an existing instance; never re-instantiate on resume.
    instance = (after or {}).get("workflowInstanceId") or state.get("workflowInstanceId")
    if (after or {}).get("workflowInstanceId") or not instance:
        instance_source = "observed-state" if instance else None
    else:
        state_provenance = str(
            state.get("stateProvenance") or state.get("source") or ""
        )
        instance_source = (
            "managed-manifest"
            if "managed-manifest" in state_provenance
            else "observed-state"
        )
    if not instance:
        # S10-F-01f: a live `ps` observation carries no workflow instance. The managed
        # run manifest is written by `start` for exactly this purpose, so resume reuses it
        # instead of refusing a live run it cannot see.
        instance, instance_source = _instance_from_manifest(run_dir)
    if not instance:
        close_prepared_resume("no workflow instance to attach")
        return _report(
            "resume", run_dir, ok=False, rc=2, code=CODE_INSTANCE_CONFLICT,
            detail="no workflow instance to attach; resume never instantiates a new one",
            plan=plan,
            extra={"mutations": mutations, "workflowInstanceProvenance": instance_source,
                   "actualOutcomeProvenance": (after or {}).get("actualOutcomeProvenance"),
                   "resumeAuthorization": resume_authorization},
            redaction_secrets=redaction_secrets,
        )

    # P-S10-02: a successful resume is a manifest revision, not a no-op. The plan's
    # observed seats and the two on-disk artifacts (continuity-plan, resume receipt) are
    # recorded by real path + sha256 + bytes; lifecycle rc/error semantics stay unchanged.
    try:
        resume_manifest = _record_resume_manifest(
            run_dir,
            bridge,
            plan,
            launch_id=_manifest_attempt_launch_id(
                run_dir, bridge, lease_launch_id or authorization_launch_id, "resume"
            ),
            instance=instance,
            mutations=mutations,
            redaction_secrets=redaction_secrets,
        )
    except Exception as exc:  # noqa: BLE001 - never lose a completed resume to evidence I/O
        resume_manifest = {
            "ok": False,
            "error": str(_redact_report_value(str(exc), *redaction_secrets)),
        }

    return _report(
        "resume",
        run_dir,
        ok=True,
        rc=0,
        plan=plan,
        extra={
            "mutations": mutations,
            "attachedWorkflowInstance": instance,
            "instantiated": False,
            "stateAfter": plan["stateAfter"],
            "actualOutcomeProvenance": (after or {}).get("actualOutcomeProvenance"),
            "actualOutcomeMissing": (after or {}).get("actualOutcomeMissing") or [],
            "workflowInstanceProvenance": instance_source,
            "resumeAuthorization": resume_authorization,
            "manifest": resume_manifest,
        },
        redaction_secrets=redaction_secrets,
    )


def compare_outcomes(plan: dict, after_state: dict) -> dict:
    """Match observed outcomes to expected actions (§4.2). `resumed` must be observed.

    Zero planned seats is a failed observation, not universal agreement: there is no
    seat whose outcome was proven. Each planned seat must also appear in the after
    observation; a missing row is not an implicit match.
    """
    planned = [seat for seat in plan.get("seats") or [] if isinstance(seat, dict)]
    if not planned:
        return {
            "seats": [],
            "all_match": False,
            "reason": "continuity plan has no seat rows; zero seats cannot prove success",
        }
    after = {
        str(s.get("logicalId")): s
        for s in after_state.get("seats") or []
        if isinstance(s, dict) and s.get("logicalId")
    }
    seats: list[dict] = []
    problems: list[str] = []
    for seat in planned:
        logical_id = seat["logicalId"]
        row = after.get(logical_id)
        if row is None:
            match = False
            outcome = "n-a"
            problems.append(f"{logical_id}: expected {seat['expectedAction']}, not observed after resume")
        else:
            outcome = row.get("actualOutcome") or "n-a"
            expected = seat["expectedAction"]
            match = _outcome_matches(expected, outcome)
            if not match:
                problems.append(f"{logical_id}: expected {expected}, observed {outcome}")
        seats.append({**seat, "actualOutcome": outcome, "outcomeMatched": match})
    return {
        "seats": seats,
        "all_match": not problems,
        "reason": "; ".join(problems) if problems else "every seat matched",
    }


def _outcome_matches(expected: str, outcome: str) -> bool:
    if expected == "resume-original":
        return outcome == "resumed"
    if expected == "fresh-primed":
        return outcome == "fresh-primed"
    if expected == "awaiting-decision":
        # We never got here with a blocked plan; treat it as a mismatch if we do.
        return outcome == "awaiting-decision"
    if expected == "n-a":
        return True
    if expected == "new":
        return outcome in ("ready", "resumed")
    return False


def _refusal_detail(plan: dict) -> str:
    parts: list[str] = []
    for row in plan.get("mismatchedSeats") or []:
        parts.append(f"{row['logicalId']}: {row['reason']}")
    for row in plan.get("blockedSeats") or []:
        label = row["logicalId"] or "fresh-list"
        parts.append(f"{label}: {row['reason']}")
    return "; ".join(parts) or "continuity plan is not allow"


# ------------------------------------------------------------------ status (read-only)
def run_status(run_dir: Path, *, live: bool = False, timeout: int = 120) -> dict:
    """Read-only. Writes nothing at all — not even a plan — so `status` can be run
    against a live run without leaving a trace (AT-S9-CT-09)."""
    bridge, err = load_bundle(run_dir)
    if bridge is None:
        return _report("status", run_dir, ok=False, rc=2, code="bridge_invalid", detail=err)
    state, source = load_observed_state(run_dir, bridge, live=live, timeout=timeout)
    if state is None:
        return _report("status", run_dir, ok=False, rc=2, code=CODE_NO_STATE, detail=source)

    plan = build_plan(bridge, state, state_source=source)
    allow = plan["decisionStatus"] == "allow"
    return _report(
        "status",
        run_dir,
        ok=allow,
        rc=0 if allow else 2,
        code=None if allow else (plan["code"] or CODE_BLOCKED),
        detail="all seats have a decision" if allow else _refusal_detail(plan),
        plan=plan,
        extra={"writes": []},
    )


# ------------------------------------------------------------------ stop
def archive_status(run_dir: Path) -> dict:
    """D-007 (S9-R-03): delegate to the ONE archive reader in `openrig_gate`.

    Deliberately no local logic: the rule ("only COMPLETE may be torn down") lives in
    exactly one place, so `stop` and the manifest step cannot read two different verdicts.
    """
    return openrig_gate.archive_status(run_dir)


def stop_argv(bridge: dict) -> list[str]:
    return [*cli_argv(bridge), "down", str(bridge.get("rigName"))]


def daemon_stop_argv(bridge: dict) -> list[str]:
    return [*cli_argv(bridge), "daemon", "stop"]


def _iso_utc(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _lease_error(code: str, message: str) -> dict:
    return {"status": "error", "code": code, "message": message}


def _launch_paths(bridge: dict) -> tuple[Path | None, Path | None, dict | None]:
    raw_home = bridge.get("openrigHome")
    if not raw_home:
        return (
            None,
            None,
            _lease_error(
                "openrig_home_missing",
                "bridge.openrigHome is required to authorize a managed stop lease",
            ),
        )
    try:
        home = Path(str(raw_home)).expanduser().resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        return None, None, _lease_error(
            "openrig_home_invalid", f"cannot resolve bridge.openrigHome: {exc}"
        )
    return home, home / "entry" / "launch.json", None


def _read_launch_record(path: Path) -> tuple[dict | None, dict | None]:
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None, _lease_error("launch_record_missing", f"launch record is missing: {path}")
    except OSError as exc:
        return None, _lease_error(
            "launch_record_unreadable", f"cannot read launch record {path}: {exc}"
        )
    try:
        # json.loads(bytes) raises UnicodeDecodeError (a ValueError) for invalid
        # UTF-8. Keep that on the structured-error path instead of letting it escape.
        record = json.loads(raw)
    except (UnicodeError, TypeError, ValueError) as exc:
        return None, _lease_error(
            "launch_record_invalid", f"launch record is not valid JSON: {path}: {exc}"
        )
    if not isinstance(record, dict):
        return None, _lease_error(
            "launch_record_invalid", f"launch record is not a JSON object: {path}"
        )
    return record, None


def _launch_record_redaction_secrets(bridge: dict) -> tuple[str, ...]:
    """Best-effort known token values for report redaction; never returns them in reports."""
    candidates: list[str] = []
    for key in ("token", "entryToken", "_entryToken", "launchToken", "secret"):
        value = bridge.get(key)
        if isinstance(value, str) and value:
            candidates.append(value)
    try:
        _home, launch_path, path_error = _launch_paths(bridge)
        if path_error is None and launch_path is not None and launch_path.is_file():
            record, record_error = _read_launch_record(launch_path)
            if record_error is None and record is not None:
                for key in (
                    "launchId",
                    "token",
                    "entryToken",
                    "_entryToken",
                    "launchToken",
                    "secret",
                ):
                    value = record.get(key)
                    if isinstance(value, str) and value:
                        candidates.append(value)
    except Exception:  # noqa: BLE001 - redaction is best-effort and must not break lifecycle
        pass
    return tuple(dict.fromkeys(candidates))


def _report_redaction_secrets(bridge: dict, *extra_secrets: object) -> tuple[str, ...]:
    """Collect all known launch/token values for recursive report projection."""
    candidates: list[str] = []
    entry_launch_id = bridge.get("_entryLaunchId")
    if isinstance(entry_launch_id, str) and entry_launch_id:
        candidates.append(entry_launch_id)
    candidates.extend(_launch_record_redaction_secrets(bridge))
    for secret in extra_secrets:
        if isinstance(secret, str) and secret:
            candidates.append(secret)
    return tuple(dict.fromkeys(candidates))


def _archive_manifest_sha256(archive: dict) -> str | None:
    if not isinstance(archive, dict):
        return None
    raw_path = archive.get("path")
    if not raw_path:
        return None
    try:
        path = Path(str(raw_path))
        if path.is_file():
            return _sha256(path)
    except (OSError, ValueError):
        return None
    return None


def _atomic_write_json_private(path: Path, payload: dict) -> None:
    """Atomically replace a JSON file, with mode 0600 on both temp and target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        os.chmod(path, 0o600)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


def prepare_stop_lease(
    run_dir: Path, bridge: dict, archive: dict, ttl_seconds: int = 120
) -> dict:
    """Grant a short S1 stop lease on the *same* managed launch record.

    This is deliberately not a launch. It only refreshes the expiry/phase fields the
    daemon's L3 admission check reads, after the archive gate has already passed. A
    non-managed fixture home is skipped so existing lifecycle fixtures stay valid; a
    managed home with a missing/mismatched/unsafe record fails closed.
    """
    _ = run_dir  # kept in the signature for audit call-sites and future evidence paths
    home, launch_path, path_error = _launch_paths(bridge)
    if path_error is not None:
        return path_error
    assert home is not None and launch_path is not None

    marker = home / "entry" / "managed-run.json"
    if not marker.is_file():
        return {"status": "skipped", "reason": "not a managed run home"}

    record, record_error = _read_launch_record(launch_path)
    if record_error is not None:
        return record_error
    assert record is not None

    record_home_raw = record.get("home")
    if not record_home_raw:
        return _lease_error("launch_home_missing", "managed launch record has no home")
    try:
        record_home = Path(str(record_home_raw)).expanduser().resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        return _lease_error(
            "launch_home_invalid", f"cannot resolve launch record home {record_home_raw!r}: {exc}"
        )
    if record_home != home:
        return _lease_error(
            "launch_home_mismatch",
            f"launch record home {record_home} does not match bridge home {home}",
        )

    bridge_run_id = str(bridge.get("runId") or "")
    if not bridge_run_id:
        return _lease_error("bridge_run_id_missing", "bridge.runId is required for a stop lease")
    if str(record.get("runId") or "") != bridge_run_id:
        return _lease_error(
            "launch_run_mismatch",
            f"launch record runId {record.get('runId')!r} does not match bridge runId {bridge_run_id!r}",
        )

    launch_id = record.get("launchId")
    if not isinstance(launch_id, str) or not launch_id.strip():
        return _lease_error("launch_id_missing", "managed launch record has no launchId")
    if "dryRun" in record and record["dryRun"] is not False:
        return _lease_error(
            "launch_record_dry_run",
            "managed launch record dryRun must be false or absent; malformed/true "
            "values cannot authorize a live stop",
        )

    try:
        ttl = max(int(ttl_seconds), 1)
    except (TypeError, ValueError):
        return _lease_error("stop_lease_ttl_invalid", f"invalid stop lease TTL: {ttl_seconds!r}")

    previous_phase = record.get("phase")
    previous_expires_at = record.get("expiresAt")
    archive_payload = archive if isinstance(archive, dict) else {}
    archive_status = str(archive_payload.get("status") or "")
    archive_manifest = archive_payload.get("path")
    archive_manifest_sha256 = _archive_manifest_sha256(archive_payload)

    granted_dt = datetime.now(timezone.utc).replace(microsecond=0)
    granted_at = _iso_utc(granted_dt)
    lease_expires_at = _iso_utc(granted_dt + timedelta(seconds=ttl))
    stop_lease = {
        "schemaVersion": 1,
        "launchId": launch_id,
        "grantedAt": granted_at,
        "expiresAt": lease_expires_at,
        "leaseExpiresAt": lease_expires_at,
        "reason": "run-stop",
        "archiveStatus": archive_status,
        "archiveManifest": archive_manifest,
        "archiveManifestSha256": archive_manifest_sha256,
        "runId": bridge_run_id,
        "rigName": str(bridge.get("rigName") or ""),
        "previousPhase": previous_phase,
        "previousExpiresAt": previous_expires_at,
    }

    record["previousPhase"] = previous_phase
    record["previousExpiresAt"] = previous_expires_at
    record["phase"] = "active"
    record["expiresAt"] = lease_expires_at
    record["leaseExpiresAt"] = lease_expires_at
    record["stopLease"] = stop_lease

    try:
        _atomic_write_json_private(launch_path, record)
    except (OSError, TypeError, ValueError) as exc:
        return _lease_error(
            "launch_record_write_failed", f"cannot write stop lease to {launch_path}: {exc}"
        )

    return {
        "status": "prepared",
        "launchId": launch_id,
        "path": str(launch_path),
        "grantedAt": granted_at,
        "leaseExpiresAt": lease_expires_at,
        "archiveStatus": archive_status,
        "archiveManifest": archive_manifest,
        "archiveManifestSha256": archive_manifest_sha256,
        "runId": bridge_run_id,
        "rigName": str(bridge.get("rigName") or ""),
    }


def close_stop_lease(run_dir: Path, bridge: dict, lease: dict, reason: str) -> dict:
    """Close a prepared lease only if the launch record still has the same launchId.

    A different launchId means a newer launch owns the file. It is never overwritten.
    """
    _ = run_dir
    if not isinstance(lease, dict):
        return _lease_error("stop_lease_invalid", "stop lease is not an object")
    launch_id = lease.get("launchId")
    if not isinstance(launch_id, str) or not launch_id.strip():
        return _lease_error("stop_lease_invalid", "stop lease has no launchId")

    home, launch_path, path_error = _launch_paths(bridge)
    if path_error is not None:
        return path_error
    assert home is not None and launch_path is not None

    marker = home / "entry" / "managed-run.json"
    if not marker.is_file():
        return {
            "status": "skipped",
            "launchId": launch_id,
            "reason": "not a managed run home",
        }

    record, record_error = _read_launch_record(launch_path)
    if record_error is not None:
        if record_error.get("code") == "launch_record_missing":
            return {
                "status": "skipped",
                "launchId": launch_id,
                "reason": record_error.get("message", "launch record is missing"),
            }
        return record_error
    assert record is not None

    current_launch_id = record.get("launchId")
    if current_launch_id != launch_id:
        return {
            "status": "skipped",
            "expectedLaunchId": launch_id,
            "launchId": current_launch_id,
            "reason": "launchId changed; refusing to close a different launch",
        }

    closed_at = now()
    record["phase"] = "closed"
    record["closedAt"] = closed_at
    record["closedReason"] = str(reason)
    try:
        _atomic_write_json_private(launch_path, record)
    except (OSError, TypeError, ValueError) as exc:
        return _lease_error(
            "launch_record_write_failed", f"cannot close stop lease at {launch_path}: {exc}"
        )

    return {
        "status": "closed",
        "launchId": launch_id,
        "path": str(launch_path),
        "closedAt": closed_at,
        "reason": str(reason),
    }


def _safe_record_stop_manifest(
    run_dir: Path,
    bridge: dict,
    *,
    status: str,
    ok: bool,
    code: str | None,
    detail: str,
    state: dict | None,
    archive: dict | None,
    launch_id: str,
    mutations: list[dict],
    redaction_secrets: tuple[str, ...],
) -> dict:
    """Evidence write must never change stop's rc/error verdict; report its own error."""
    try:
        return _record_stop_manifest(
            run_dir,
            bridge,
            status=status,
            ok=ok,
            code=code,
            detail=detail,
            state=state,
            archive=archive,
            launch_id=launch_id,
            mutations=mutations,
            redaction_secrets=redaction_secrets,
        )
    except Exception as exc:  # noqa: BLE001 - stop verdict already decided
        return {
            "ok": False,
            "error": str(_redact_report_value(str(exc), *redaction_secrets)),
        }


# Keep these tuples in lockstep with openrig_run.ENTRY_VERBS and the TS entry guard.
# Startup verbs are single-consumption; continuation verbs stay repeatable for the
# lifetime of the same launch record and must survive a resume.
RESUME_STARTUP_ENTRY_VERBS = (
    "daemon-start",
    "up",
    "restore-apply",
    "workflow-instantiate",
    "workflow-instantiate-lifecycle",
    "workflow-run",
)
RESUME_CONTINUATION_ENTRY_VERBS = (
    "workflow-route",
    "workflow-resume",
    "workflow-abort",
    "workflow-revision",
    "workflow-project",
)
RESUME_ENTRY_VERBS = RESUME_STARTUP_ENTRY_VERBS + RESUME_CONTINUATION_ENTRY_VERBS
_RESUME_ENTRY_VERB_SET = frozenset(RESUME_ENTRY_VERBS)
_RESUME_PHASES = frozenset(("starting", "active", "closed"))


def _parse_iso_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp must be a non-empty ISO string")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def _read_managed_marker(path: Path) -> tuple[dict | None, dict | None]:
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None, _lease_error("managed_marker_missing", f"managed marker is missing: {path}")
    except OSError as exc:
        return None, _lease_error(
            "managed_marker_unreadable", f"cannot read managed marker {path}: {exc}"
        )
    try:
        marker = json.loads(raw)
    except (UnicodeError, TypeError, ValueError) as exc:
        return None, _lease_error(
            "managed_marker_invalid", f"managed marker is not valid JSON: {path}: {exc}"
        )
    if not isinstance(marker, dict):
        return None, _lease_error(
            "managed_marker_invalid", f"managed marker is not a JSON object: {path}"
        )
    return marker, None


def _load_resume_marker(
    home: Path, bridge: dict
) -> tuple[dict | None, dict | None, bool]:
    """Return (marker, error, missing) with fail-closed managed-home semantics."""
    marker_path = home / "entry" / "managed-run.json"
    if marker_path.is_file():
        marker, error = _read_managed_marker(marker_path)
        if error is not None:
            return None, error, False
        assert marker is not None
        bridge_run_id = str(bridge.get("runId") or "")
        if not bridge_run_id:
            return None, _lease_error(
                "bridge_run_id_missing",
                "bridge.runId is required for a resume lease",
            ), False
        if str(marker.get("runId") or "") != bridge_run_id:
            return None, _lease_error(
                "managed_marker_run_mismatch",
                f"managed marker runId {marker.get('runId')!r} does not match bridge runId {bridge_run_id!r}",
            ), False
        return marker, None, False
    if marker_path.exists() or marker_path.is_symlink():
        return None, _lease_error(
            "managed_marker_invalid",
            f"managed marker is not a regular file: {marker_path}",
        ), False
    return None, None, True


def _validate_resume_launch_record(
    record: dict, bridge: dict, home: Path
) -> tuple[str | None, dict | None]:
    schema_version = record.get("schemaVersion")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version != 1
    ):
        return None, _lease_error(
            "launch_schema_version_invalid",
            "managed launch record schemaVersion must be integer 1",
        )

    launch_id = record.get("launchId")
    if not isinstance(launch_id, str) or not launch_id.strip():
        return None, _lease_error("launch_id_missing", "managed launch record has no launchId")

    record_home_raw = record.get("home")
    if not isinstance(record_home_raw, str) or not record_home_raw.strip():
        return None, _lease_error("launch_home_missing", "managed launch record has no home")
    try:
        record_home_path = Path(record_home_raw).expanduser()
        if not record_home_path.is_absolute():
            return None, _lease_error(
                "launch_home_invalid",
                f"launch record home must be an absolute path: {record_home_raw!r}",
            )
        record_home = record_home_path.resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        return None, _lease_error(
            "launch_home_invalid",
            f"cannot resolve launch record home {record_home_raw!r}: {exc}",
        )
    if record_home != home:
        return None, _lease_error(
            "launch_home_mismatch",
            f"launch record home {record_home} does not match bridge home {home}",
        )

    bridge_run_id = str(bridge.get("runId") or "")
    if not bridge_run_id:
        return None, _lease_error(
            "bridge_run_id_missing", "bridge.runId is required for a resume lease"
        )
    if str(record.get("runId") or "") != bridge_run_id:
        return None, _lease_error(
            "launch_run_mismatch",
            f"launch record runId {record.get('runId')!r} does not match bridge runId {bridge_run_id!r}",
        )

    phase = record.get("phase")
    if not isinstance(phase, str) or phase not in _RESUME_PHASES:
        return None, _lease_error(
            "launch_phase_invalid",
            "managed launch record phase must be one of starting, active, closed",
        )

    try:
        _parse_iso_timestamp(record.get("expiresAt"))
    except (TypeError, ValueError):
        return None, _lease_error(
            "launch_expires_at_invalid",
            "managed launch record expiresAt must be an ISO timestamp",
        )

    verbs = record.get("verbs")
    if not isinstance(verbs, list) or any(
        not isinstance(verb, str) or verb not in _RESUME_ENTRY_VERB_SET for verb in verbs
    ):
        return None, _lease_error(
            "launch_verbs_invalid",
            "managed launch record verbs must be a list of known entry verbs",
        )

    consumed = record.get("consumed")
    if not isinstance(consumed, list):
        return None, _lease_error(
            "launch_consumed_invalid",
            "managed launch record consumed must be a list",
        )
    for item in consumed:
        if not isinstance(item, dict):
            return None, _lease_error(
                "launch_consumed_invalid",
                "managed launch record consumed entries must be objects",
            )
        verb = item.get("verb")
        if not isinstance(verb, str) or verb not in _RESUME_ENTRY_VERB_SET:
            return None, _lease_error(
                "launch_consumed_invalid",
                "managed launch record consumed entries need a known verb",
            )
        try:
            _parse_iso_timestamp(item.get("at"))
        except (TypeError, ValueError):
            return None, _lease_error(
                "launch_consumed_invalid",
                "managed launch record consumed entries need a valid at timestamp",
            )

    if "dryRun" in record and record["dryRun"] is not False:
        return None, _lease_error(
            "launch_record_dry_run",
            "managed launch record dryRun must be false or absent; malformed/true "
            "values cannot authorize a live resume",
        )
    return launch_id, None


def _ensure_resume_continuation_verbs(record: dict) -> None:
    """Add repeatable continuation verbs without touching single-use consumed history."""
    verbs = list(record.get("verbs") or [])
    for verb in RESUME_CONTINUATION_ENTRY_VERBS:
        if verb not in verbs:
            verbs.append(verb)
    record["verbs"] = list(dict.fromkeys(verbs))


def _resume_archive_evidence(run_dir: Path) -> tuple[str, str | None, str | None]:
    archive = archive_status(run_dir)
    status = str(archive.get("status") or "")
    manifest = archive.get("path")
    return status, manifest, _archive_manifest_sha256(archive)


def prepare_resume_lease(
    run_dir: Path, bridge: dict, *, daemon_running: bool, ttl_seconds: int = 1200
) -> dict:
    """Prepare a resume authorization without changing CLI/daemon behavior.

    A running daemon must keep the launchId its environment token was issued under;
    a stopped daemon must get a fresh launchId because the old daemon-start verb may
    already be consumed. Every path is fail-closed on a suspicious managed record.
    """
    home, launch_path, path_error = _launch_paths(bridge)
    if path_error is not None:
        return path_error
    assert home is not None and launch_path is not None

    _marker, marker_error, marker_missing = _load_resume_marker(home, bridge)
    if marker_error is not None:
        return marker_error
    if marker_missing:
        return {"status": "skipped", "reason": "not a managed run home"}
    bridge_run_id = str(bridge.get("runId") or "")

    try:
        ttl = max(int(ttl_seconds), 1)
    except (TypeError, ValueError):
        return _lease_error("resume_lease_ttl_invalid", f"invalid resume lease TTL: {ttl_seconds!r}")

    prepared_dt = datetime.now(timezone.utc).replace(microsecond=0)
    prepared_at = _iso_utc(prepared_dt)
    lease_expires_at = _iso_utc(prepared_dt + timedelta(seconds=ttl))
    archive_status_value, archive_manifest, archive_manifest_sha256 = _resume_archive_evidence(
        run_dir
    )

    if daemon_running:
        record, record_error = _read_launch_record(launch_path)
        if record_error is not None:
            return record_error
        assert record is not None
        launch_id, record_error = _validate_resume_launch_record(record, bridge, home)
        if record_error is not None:
            return record_error
        assert launch_id is not None
        # Legacy launch records predate repeatable workflow continuation. Upgrade the
        # verb set in place; `consumed` is left untouched, so startup verbs remain
        # single-use evidence and continuation verbs are not consumed.
        _ensure_resume_continuation_verbs(record)

        previous_phase = record.get("phase")
        previous_expires_at = record.get("expiresAt")
        resume_lease = {
            "schemaVersion": 1,
            "reason": "run-resume",
            "preparedAt": prepared_at,
            "expiresAt": lease_expires_at,
            "daemonRunning": True,
            "reusedLaunchId": True,
            "newLaunch": False,
            "previousPhase": previous_phase,
            "previousExpiresAt": previous_expires_at,
            "archiveStatus": archive_status_value,
            "archiveManifest": archive_manifest,
            "archiveManifestSha256": archive_manifest_sha256,
            "runId": bridge_run_id,
            "rigName": str(bridge.get("rigName") or ""),
        }
        record["previousPhase"] = previous_phase
        record["previousExpiresAt"] = previous_expires_at
        record["phase"] = "active"
        record["expiresAt"] = lease_expires_at
        record["leaseExpiresAt"] = lease_expires_at
        record["resumeLease"] = resume_lease
        try:
            _atomic_write_json_private(launch_path, record)
        except (OSError, TypeError, ValueError) as exc:
            return _lease_error(
                "launch_record_write_failed",
                f"cannot write resume lease to {launch_path}: {exc}",
            )
        return {
            "status": "prepared",
            "launchId": launch_id,
            "path": str(launch_path),
            "preparedAt": prepared_at,
            "leaseExpiresAt": lease_expires_at,
            "newLaunch": False,
            "daemonRunning": True,
            "archiveStatus": archive_status_value,
            "archiveManifest": archive_manifest,
            "archiveManifestSha256": archive_manifest_sha256,
        }

    previous_launch_id: str | None = None
    if launch_path.exists() or launch_path.is_symlink():
        old_record, record_error = _read_launch_record(launch_path)
        if record_error is not None:
            return record_error
        assert old_record is not None
        previous_launch_id, record_error = _validate_resume_launch_record(
            old_record, bridge, home
        )
        if record_error is not None:
            return record_error

    launch_id = f"launch-{uuid.uuid4()}"
    resume_lease = {
        "schemaVersion": 1,
        "reason": "run-resume",
        "preparedAt": prepared_at,
        "expiresAt": lease_expires_at,
        "daemonRunning": False,
        "reusedLaunchId": False,
        "newLaunch": True,
        "previousLaunchId": previous_launch_id,
        "archiveStatus": archive_status_value,
        "archiveManifest": archive_manifest,
        "archiveManifestSha256": archive_manifest_sha256,
        "runId": bridge_run_id,
        "rigName": str(bridge.get("rigName") or ""),
    }
    record = {
        "schemaVersion": 1,
        "launchId": launch_id,
        "home": str(home),
        "runId": bridge_run_id,
        "rigName": str(bridge.get("rigName") or ""),
        "workflowId": str(bridge.get("workflowId") or ""),
        "verbs": list(RESUME_ENTRY_VERBS),
        "consumed": [],
        "phase": "active",
        "dryRun": False,
        "createdAt": prepared_at,
        "createdBy": "openrig-run resume",
        "expiresAt": lease_expires_at,
        "leaseExpiresAt": lease_expires_at,
        "resumeLease": resume_lease,
    }
    try:
        _atomic_write_json_private(launch_path, record)
    except (OSError, TypeError, ValueError) as exc:
        return _lease_error(
            "launch_record_write_failed",
            f"cannot write recovery launch record to {launch_path}: {exc}",
        )
    return {
        "status": "prepared",
        "launchId": launch_id,
        "path": str(launch_path),
        "preparedAt": prepared_at,
        "leaseExpiresAt": lease_expires_at,
        "newLaunch": True,
        "previousLaunchId": previous_launch_id,
        "daemonRunning": False,
        "archiveStatus": archive_status_value,
        "archiveManifest": archive_manifest,
        "archiveManifestSha256": archive_manifest_sha256,
    }


def close_resume_lease(run_dir: Path, bridge: dict, lease: dict, reason: str) -> dict:
    """Close a resume lease only when its launchId still owns launch.json."""
    _ = run_dir
    if not isinstance(lease, dict):
        return _lease_error("resume_lease_invalid", "resume lease is not an object")
    launch_id = lease.get("launchId")
    if not isinstance(launch_id, str) or not launch_id.strip():
        return _lease_error("resume_lease_invalid", "resume lease has no launchId")

    home, launch_path, path_error = _launch_paths(bridge)
    if path_error is not None:
        return path_error
    assert home is not None and launch_path is not None

    _marker, marker_error, marker_missing = _load_resume_marker(home, bridge)
    if marker_error is not None:
        return marker_error
    if marker_missing:
        return {
            "status": "skipped",
            "launchId": launch_id,
            "reason": "not a managed run home",
        }

    record, record_error = _read_launch_record(launch_path)
    if record_error is not None:
        if record_error.get("code") == "launch_record_missing":
            return {
                "status": "skipped",
                "launchId": launch_id,
                "reason": record_error.get("message", "launch record is missing"),
            }
        return record_error
    assert record is not None

    current_launch_id = record.get("launchId")
    if current_launch_id != launch_id:
        return {
            "status": "skipped",
            "expectedLaunchId": launch_id,
            "launchId": current_launch_id,
            "reason": "launchId changed; refusing to close a different launch",
        }

    closed_at = now()
    record["phase"] = "closed"
    record["closedAt"] = closed_at
    record["closedReason"] = str(reason)
    try:
        _atomic_write_json_private(launch_path, record)
    except (OSError, TypeError, ValueError) as exc:
        return _lease_error(
            "launch_record_write_failed", f"cannot close resume lease at {launch_path}: {exc}"
        )

    return {
        "status": "closed",
        "launchId": launch_id,
        "path": str(launch_path),
        "closedAt": closed_at,
        "reason": str(reason),
    }


_SAFE_RESUME_LEASE_KEYS = (
    "status",
    "reason",
    "code",
    "message",
    "launchId",
    "expectedLaunchId",
    "path",
    "preparedAt",
    "leaseExpiresAt",
    "newLaunch",
    "previousLaunchId",
    "daemonRunning",
    "archiveStatus",
    "archiveManifest",
    "archiveManifestSha256",
    "closedAt",
)


def _public_resume_lease_result(result: object) -> dict:
    """Project a resume lease result onto an allow-list (never leak launch tokens)."""
    if not isinstance(result, dict):
        return {
            "status": "error",
            "code": "resume_lease_result_invalid",
            "message": "resume lease helper returned no result",
        }
    projected = {"status": str(result.get("status") or "error")}
    for key in _SAFE_RESUME_LEASE_KEYS[1:]:
        if key in result:
            projected[key] = result[key]
    return projected


_SAFE_STOP_LEASE_KEYS = (
    "status",
    "reason",
    "code",
    "message",
    "launchId",
    "expectedLaunchId",
    "path",
    "grantedAt",
    "leaseExpiresAt",
    "archiveStatus",
    "archiveManifest",
    "archiveManifestSha256",
    "runId",
    "rigName",
    "closedAt",
)


def _public_stop_lease_result(result: object) -> dict:
    """Project a lease result onto an allow-list (never leak launch tokens)."""
    if not isinstance(result, dict):
        return {
            "status": "error",
            "code": "stop_lease_result_invalid",
            "message": "stop lease helper returned no result",
        }
    projected = {"status": str(result.get("status") or "error")}
    for key in _SAFE_STOP_LEASE_KEYS[1:]:
        if key in result and result[key] is not None:
            projected[key] = result[key]
    return projected


def _expected_tmux_sessions(bridge: dict, state: dict | None) -> list[str]:
    targets: set[str] = set()
    for seat in (state or {}).get("seats") or []:
        if isinstance(seat, dict) and seat.get("canonicalSessionName"):
            targets.add(str(seat["canonicalSessionName"]))
    seat_map = bridge.get("seatMap")
    if isinstance(seat_map, dict):
        for target in seat_map.values():
            if str(target).strip():
                targets.add(str(target))
    return sorted(targets)


def _probe_tmux_residue(
    bridge: dict, state: dict | None, *, timeout: int = 5
) -> dict:
    """List tmux sessions without asking the daemon; fail closed if tmux cannot answer."""
    expected = _expected_tmux_sessions(bridge, state)
    argv = ["tmux", "list-sessions", "-F", "#{session_name}"]
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "axis": "tmux",
            "status": "unavailable",
            "complete": False,
            "expectedSessions": expected,
            "matchedSessions": [],
            "detail": f"tmux probe failed: {type(exc).__name__}: {exc}",
        }
    stderr = str(proc.stderr or "")
    if proc.returncode == 0:
        sessions = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
        observed = True
        detail = "tmux list-sessions answered"
    elif proc.returncode == 1 and any(
        marker in stderr.lower()
        for marker in (
            "no server running",
            "failed to connect to server",
            "error connecting to",
            "no sessions",
        )
    ):
        sessions = []
        observed = True
        detail = "tmux reported no running server/sessions"
    else:
        return {
            "axis": "tmux",
            "status": "unavailable",
            "complete": False,
            "expectedSessions": expected,
            "matchedSessions": [],
            "detail": f"tmux list-sessions rc={proc.returncode}: {stderr[:300]}",
        }
    rig_name = str(bridge.get("rigName") or "")
    matched = [
        session
        for session in sessions
        if session in expected
        or (rig_name and (session == rig_name or session.endswith(f"@{rig_name}")))
    ]
    return {
        "axis": "tmux",
        "status": "observed" if observed else "unavailable",
        "complete": observed,
        "expectedSessions": expected,
        "observedSessions": sessions,
        "matchedSessions": matched,
        "detail": detail,
    }


def _probe_process_home_residue(
    run_dir: Path, bridge: dict, *, timeout: int = 5
) -> dict:
    """Observe surviving processes by run home/CLI, plus readable env where present."""
    home_raw = str(bridge.get("openrigHome") or "").strip()
    needles: set[str] = set()
    if home_raw:
        needles.add(str(Path(home_raw).resolve()))
    cli = str(bridge.get("openrigCli") or "").strip()
    if cli:
        needles.add(str(Path(cli).resolve()))
    # The invoking shell/test process may name the run directory while stopping.
    # That is not proof that a process belongs to this run. Home and the managed CLI
    # are run-specific; the loopback port is probed independently.
    port = bridge.get("daemonPort")
    port_needles = (
        (f"--port {port}", f"OPENRIG_PORT={port}")
        if isinstance(port, int) and not isinstance(port, bool)
        else ()
    )
    try:
        proc = subprocess.run(
            ["ps", "-eo", "pid=,args="],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "axis": "process-home",
            "status": "unavailable",
            "complete": False,
            "matches": [],
            "detail": f"ps probe failed: {type(exc).__name__}: {exc}",
        }
    if proc.returncode != 0:
        return {
            "axis": "process-home",
            "status": "unavailable",
            "complete": False,
            "matches": [],
            "detail": f"ps rc={proc.returncode}: {(proc.stderr or '')[:300]}",
        }

    matches: list[dict] = []
    own_pid = os.getpid()
    for line in (proc.stdout or "").splitlines():
        fields = line.strip().split(None, 1)
        if len(fields) != 2 or not fields[0].isdigit():
            continue
        pid = int(fields[0])
        if pid == own_pid:
            continue
        command = fields[1]
        if not any(needle and needle in command for needle in needles) and not any(
            needle in command for needle in port_needles
        ):
            continue
        matches.append({"pid": pid, "command": command[:500]})

    # Environment is an independent second ingress for the same home. Unreadable
    # processes are counted, not silently treated as belonging to this run.
    environ_readable = 0
    environ_unreadable = 0
    env_matches: set[int] = set()
    try:
        proc_dirs = [entry for entry in os.listdir("/proc") if entry.isdigit()]
    except OSError as exc:
        return {
            "axis": "process-home",
            "status": "unavailable",
            "complete": False,
            "matches": matches,
            "detail": f"/proc unavailable for environment scan: {exc}",
        }
    for pid_text in proc_dirs:
        pid = int(pid_text)
        if pid == own_pid:
            continue
        try:
            raw = Path(f"/proc/{pid}/environ").read_bytes()
        except OSError:
            environ_unreadable += 1
            continue
        environ_readable += 1
        text = raw.replace(b"\x00", b"\n").decode("utf-8", "replace")
        if any(needle and needle in text for needle in needles) or any(
            needle in text for needle in port_needles
        ):
            env_matches.add(pid)
    by_pid = {int(row["pid"]): row for row in matches}
    for pid in sorted(env_matches):
        by_pid.setdefault(
            pid,
            {
                "pid": pid,
                "command": "<environment match; command line unavailable/clean>",
            },
        )
    return {
        "axis": "process-home",
        "status": "observed",
        "complete": True,
        "observationMethod": "ps args + readable /proc/<pid>/environ",
        "needles": sorted(needle for needle in needles if needle),
        "matches": list(by_pid.values()),
        "environReadableProcesses": environ_readable,
        "environUnreadableProcesses": environ_unreadable,
        "detail": "process/home observation completed",
    }


def _probe_port_residue(
    bridge: dict, *, declared_fixture: bool = False, timeout_seconds: float = 0.25
) -> dict:
    raw_port = bridge.get("daemonPort")
    if raw_port is None:
        if declared_fixture:
            return {
                "axis": "port",
                "status": "not-applicable",
                "complete": True,
                "port": None,
                "listening": False,
                "detail": "declared fixture bridge has no daemonPort to observe",
            }
        return {
            "axis": "port",
            "status": "unavailable",
            "complete": False,
            "port": None,
            "listening": None,
            "detail": "real run has no daemonPort; TCP residue cannot be observed",
        }
    if not isinstance(raw_port, int) or isinstance(raw_port, bool) or not (1 <= raw_port <= 65535):
        return {
            "axis": "port",
            "status": "unavailable",
            "complete": False,
            "port": raw_port,
            "listening": None,
            "detail": f"bridge daemonPort is not a valid TCP port: {raw_port!r}",
        }
    try:
        results: list[tuple[str, int]] = []
        infos = socket.getaddrinfo("127.0.0.1", raw_port, type=socket.SOCK_STREAM)
        for family, socktype, proto, _canonname, sockaddr in infos[:1]:
            sock = socket.socket(family, socktype, proto)
            sock.settimeout(timeout_seconds)
            try:
                results.append(("127.0.0.1", sock.connect_ex(sockaddr)))
            finally:
                sock.close()
        # Also observe the IPv6 loopback when available; either listener is residue.
        try:
            v6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            v6.settimeout(timeout_seconds)
            try:
                results.append(("::1", v6.connect_ex(("::1", raw_port))))
            finally:
                v6.close()
        except OSError:
            pass
    except OSError as exc:
        return {
            "axis": "port",
            "status": "unavailable",
            "complete": False,
            "port": raw_port,
            "listening": None,
            "detail": f"port probe failed: {exc}",
        }
    if any(code == 0 for _host, code in results):
        return {
            "axis": "port",
            "status": "observed",
            "complete": True,
            "port": raw_port,
            "listening": True,
            "connectResults": [{"host": host, "errno": code} for host, code in results],
            "detail": f"TCP port {raw_port} still accepts connections",
        }
    closed_errnos = {111, 104, 113, 101, 99, 61}
    if results and all(code in closed_errnos for _host, code in results):
        return {
            "axis": "port",
            "status": "observed",
            "complete": True,
            "port": raw_port,
            "listening": False,
            "connectResults": [{"host": host, "errno": code} for host, code in results],
            "detail": f"no listener accepted on TCP port {raw_port}",
        }
    return {
        "axis": "port",
        "status": "unavailable",
        "complete": False,
        "port": raw_port,
        "listening": None,
        "connectResults": [{"host": host, "errno": code} for host, code in results],
        "detail": f"port probe was inconclusive on TCP port {raw_port}",
    }


def _observe_post_stop_residue(
    run_dir: Path, bridge: dict, state: dict | None, *, live: bool = False
) -> dict:
    """Independent post-stop observation: tmux, process/home, and loopback port.

    The daemon is normally gone at this point, so `rig ps` cannot be the proof. Each
    axis reports its own provenance; a single unavailable axis makes the whole
    observation incomplete and callers must fail closed.

    A declared fixture run (`bridge._fixture`, non-live) has no real daemon/tmux by
    construction. The tmux axis is then recorded as not-applicable rather than
    pretending a real session was observed; the explicit fixture continuity state still
    supplies the after-down seat evidence. Live runs never receive this downgrade.
    """
    declared_fixture = bool(bridge.get("_fixture"))
    tmux = _probe_tmux_residue(bridge, state)
    process = _probe_process_home_residue(run_dir, bridge)
    port = _probe_port_residue(bridge, declared_fixture=declared_fixture)
    fixture_mode = declared_fixture and not live
    if fixture_mode and tmux.get("status") == "unavailable":
        tmux = {
            **tmux,
            "status": "not-applicable",
            "complete": True,
            "fixtureMode": True,
            "detail": (
                "declared fixture run has no real tmux server; "
                "the fixture continuity state is the after-down seat observation"
            ),
        }
    residue: list[dict] = []
    for session in tmux.get("matchedSessions") or []:
        residue.append({"kind": "tmux", "id": session})
    for row in process.get("matches") or []:
        residue.append(
            {"kind": "process-home", "id": str(row.get("pid")), "pid": row.get("pid")}
        )
    if port.get("listening"):
        residue.append({"kind": "port", "id": str(port.get("port")), "port": port.get("port")})
    sources = [tmux, process, port]
    return {
        "schemaVersion": 1,
        "complete": all(source.get("complete") is True for source in sources),
        "sources": {source["axis"]: source for source in sources},
        "residue": residue,
        "fixtureMode": fixture_mode,
        "provenance": (
            "independent post-stop observation: tmux list-sessions; "
            "ps args + readable /proc environ for run home/paths; "
            "TCP connect to loopback daemonPort"
            + ("; fixture-mode tmux axis is not-applicable" if fixture_mode else "")
        ),
    }


def run_stop(
    run_dir: Path, *, live: bool = False, timeout: int = 120, dry_run: bool = False
) -> dict:
    """§4.3. Archive gate first; dry-run writes nothing; post-stop proof is independent.

    A stopped daemon cannot answer `ps`, so the clean/not-clean verdict comes from the
    independent tmux/process-home/port observation. If any axis cannot be observed the
    stop fails closed and never emits an empty orphan list as proof.
    """
    bridge, err = load_bundle(run_dir)
    if bridge is None:
        return _report("stop", run_dir, ok=False, rc=2, code="bridge_invalid", detail=err)

    known_redaction_secrets = _report_redaction_secrets(bridge)
    gate = archive_status(run_dir)

    # A dry-run is an inspection, never evidence creation. It comes before every
    # manifest/receipt write, including the archive-incomplete failure branch.
    if dry_run:
        if gate["status"] != "COMPLETE":
            detail = (
                f"archive status is {gate['status']} ({gate['path']}); "
                "dry-run is read-only and refuses teardown"
            )
            return _report(
                "stop",
                run_dir,
                ok=False,
                rc=2,
                code=CODE_ARCHIVE_INCOMPLETE,
                detail=detail,
                extra={
                    "archive": gate,
                    "mutations": [],
                    "dryRun": True,
                    "writes": [],
                },
                redaction_secrets=known_redaction_secrets,
            )
        state, source = load_observed_state(
            run_dir,
            bridge,
            live=live,
            timeout=timeout,
            allow_daemon_down_fallback=True,
        )
        return _report(
            "stop",
            run_dir,
            ok=True,
            rc=0,
            extra={
                "archive": gate,
                "stateSource": source,
                "stateAvailable": state is not None,
                "mutations": [],
                "dryRun": True,
                "writes": [],
                "stopAuthorization": {
                    "status": "dry-run",
                    "reason": "dry-run stop does not grant a stop lease",
                },
            },
            redaction_secrets=known_redaction_secrets,
        )

    if gate["status"] != "COMPLETE":
        detail = f"archive status is {gate['status']} ({gate['path']}); refusing to tear down"
        stop_manifest = _safe_record_stop_manifest(
            run_dir,
            bridge,
            status="failed",
            ok=False,
            code=CODE_ARCHIVE_INCOMPLETE,
            detail=detail,
            state=None,
            archive=gate,
            launch_id=_manifest_attempt_launch_id(run_dir, bridge, None, "stop"),
            mutations=[],
            redaction_secrets=known_redaction_secrets,
        )
        return _report(
            "stop",
            run_dir,
            ok=False,
            rc=2,
            code=CODE_ARCHIVE_INCOMPLETE,
            detail=detail,
            extra={"archive": gate, "mutations": [], "manifest": stop_manifest},
            redaction_secrets=known_redaction_secrets,
        )

    state, source = load_observed_state(
        run_dir,
        bridge,
        live=live,
        timeout=timeout,
        allow_daemon_down_fallback=True,
    )
    mutations: list[dict] = []

    authorization = prepare_stop_lease(run_dir, bridge, gate)
    authorization_launch_id = (
        str(authorization.get("launchId"))
        if isinstance(authorization, dict) and authorization.get("launchId")
        else None
    )
    redaction_secrets = _report_redaction_secrets(
        bridge, authorization_launch_id, *known_redaction_secrets
    )
    stop_authorization = _redact_report_value(
        _public_stop_lease_result(authorization), *redaction_secrets
    )
    authorization_status = (
        str(authorization.get("status") or "") if isinstance(authorization, dict) else ""
    )
    if authorization_status not in ("prepared", "skipped"):
        detail = ""
        if isinstance(authorization, dict):
            detail = str(authorization.get("message") or authorization.get("reason") or "")
        detail = str(_redact_report_value(detail, *redaction_secrets))
        auth_detail = detail or "managed launch record does not authorize raw down"
        stop_manifest = _safe_record_stop_manifest(
            run_dir,
            bridge,
            status="failed",
            ok=False,
            code="stop_authorization_failed",
            detail=auth_detail,
            state=state,
            archive=gate,
            launch_id=_manifest_attempt_launch_id(
                run_dir, bridge, authorization_launch_id, "stop"
            ),
            mutations=[],
            redaction_secrets=redaction_secrets,
        )
        return _report(
            "stop",
            run_dir,
            ok=False,
            rc=2,
            code="stop_authorization_failed",
            detail=auth_detail,
            extra={
                "archive": gate,
                "stateSource": source,
                "mutations": [],
                "stopAuthorization": stop_authorization,
                "manifest": stop_manifest,
            },
            redaction_secrets=redaction_secrets,
        )

    lease = authorization if authorization_status == "prepared" else None
    stop_attempt = str(authorization_launch_id or "stop")
    down_argv = stop_argv(bridge)
    down_bridge = _capture_bridge(
        bridge,
        "rig-down",
        capture_id=f"{stop_attempt}-rig-down",
        secrets=redaction_secrets,
    )
    proc = _run(down_argv, down_bridge, timeout)
    down_mutation = _capture_mutation(
        "rig-down",
        proc,
        run_dir=run_dir,
        label="rig-down",
        argv=down_argv,
        redaction_secrets=redaction_secrets,
    )
    mutations.append(down_mutation)

    if lease is not None:
        # Close immediately after the raw down attempt, whether it succeeded or failed.
        # A close failure is reported, never allowed to mask/override the down result.
        try:
            closed = close_stop_lease(
                run_dir, bridge, lease, reason=f"rig down rc={proc.returncode}"
            )
        except Exception as exc:  # noqa: BLE001 - a down report must never be lost to cleanup
            closed = _lease_error(
                "stop_lease_close_failed",
                f"stop lease close raised {type(exc).__name__}",
            )
        stop_authorization["leaseClosed"] = _redact_report_value(
            _public_stop_lease_result(closed), *redaction_secrets
        )

    if proc.returncode != 0:
        down_detail = str(
            down_mutation.get("stderrTail") or down_mutation.get("stdoutTail") or ""
        )[:300] or f"rig down rc={proc.returncode}"
        stop_manifest = _safe_record_stop_manifest(
            run_dir,
            bridge,
            status="failed",
            ok=False,
            code="down_failed",
            detail=down_detail,
            state=state,
            archive=gate,
            launch_id=_manifest_attempt_launch_id(
                run_dir, bridge, authorization_launch_id, "stop"
            ),
            mutations=mutations,
            redaction_secrets=redaction_secrets,
        )
        return _report(
            "stop",
            run_dir,
            ok=False,
            rc=2,
            code="down_failed",
            detail=down_detail,
            extra={
                "archive": gate,
                "stateSource": source,
                "mutations": mutations,
                "stopAuthorization": stop_authorization,
                "manifest": stop_manifest,
            },
            redaction_secrets=redaction_secrets,
        )

    if (state or {}).get("daemonState") == "running" and (state or {}).get("daemonOwnedByRun", True):
        daemon_argv = daemon_stop_argv(bridge)
        daemon_bridge = _capture_bridge(
            bridge,
            "daemon-stop",
            capture_id=f"{stop_attempt}-daemon-stop",
            secrets=redaction_secrets,
        )
        proc = _run(daemon_argv, daemon_bridge, timeout)
        daemon_mutation = _capture_mutation(
            "daemon-stop",
            proc,
            run_dir=run_dir,
            label="daemon-stop",
            argv=daemon_argv,
            redaction_secrets=redaction_secrets,
        )
        mutations.append(daemon_mutation)
        if proc.returncode != 0:
            daemon_detail = str(
                daemon_mutation.get("stderrTail")
                or daemon_mutation.get("stdoutTail")
                or ""
            )[:300] or f"daemon stop rc={proc.returncode}"
            stop_manifest = _safe_record_stop_manifest(
                run_dir,
                bridge,
                status="failed",
                ok=False,
                code=CODE_DAEMON_STOP_FAILED,
                detail=daemon_detail,
                state=state,
                archive=gate,
                launch_id=_manifest_attempt_launch_id(
                    run_dir, bridge, authorization_launch_id, "stop"
                ),
                mutations=mutations,
                redaction_secrets=redaction_secrets,
            )
            return _report(
                "stop",
                run_dir,
                ok=False,
                rc=2,
                code=CODE_DAEMON_STOP_FAILED,
                detail=daemon_detail,
                extra={
                    "archive": gate,
                    "stateSource": source,
                    "mutations": mutations,
                    "stopAuthorization": stop_authorization,
                    "manifest": stop_manifest,
                    "postStopObservation": {
                        "complete": False,
                        "reason": "daemon stop failed before residue observation",
                    },
                },
                redaction_secrets=redaction_secrets,
            )

    # Orphans are REPORTED, never killed (§4.3: no kill -9, never rm -rf home/DB).
    # The daemon is normally gone now, so use observation sources that outlive it.
    residue_observation = _observe_post_stop_residue(
        run_dir, bridge, state, live=live
    )
    if residue_observation.get("complete") is not True:
        unavailable = [
            f"{axis}: {row.get('detail')}"
            for axis, row in (residue_observation.get("sources") or {}).items()
            if isinstance(row, dict) and row.get("complete") is not True
        ]
        observation_detail = (
            "post-stop residue observation is incomplete; refusing to claim a clean stop"
            + (f": {'; '.join(unavailable)}" if unavailable else "")
        )
        stop_manifest = _safe_record_stop_manifest(
            run_dir,
            bridge,
            status="failed",
            ok=False,
            code=CODE_POST_STOP_OBSERVATION_UNAVAILABLE,
            detail=observation_detail,
            state=state,
            archive=gate,
            launch_id=_manifest_attempt_launch_id(
                run_dir, bridge, authorization_launch_id, "stop"
            ),
            mutations=mutations,
            redaction_secrets=redaction_secrets,
        )
        return _report(
            "stop",
            run_dir,
            ok=False,
            rc=2,
            code=CODE_POST_STOP_OBSERVATION_UNAVAILABLE,
            detail=observation_detail,
            extra={
                "archive": gate,
                "stateSource": source,
                "mutations": mutations,
                "stopAuthorization": stop_authorization,
                "manifest": stop_manifest,
                "postStopObservation": residue_observation,
            },
            redaction_secrets=redaction_secrets,
        )

    after, after_source = load_observed_state(
        run_dir, bridge, live=live, timeout=timeout
    )
    orphans = [
        f"{row.get('kind')}:{row.get('id')}"
        for row in residue_observation.get("residue") or []
    ]
    if after is not None:
        for logical_id in _orphans_after(after):
            if logical_id not in orphans:
                orphans.append(logical_id)
    if orphans:
        orphan_detail = str(
            _redact_report_value(
                f"still alive after stop: {orphans}", *redaction_secrets
            )
        )
        stop_manifest = _safe_record_stop_manifest(
            run_dir,
            bridge,
            status="failed",
            ok=False,
            code=CODE_ORPHAN_AFTER_STOP,
            detail=orphan_detail,
            state=state,
            archive=gate,
            launch_id=_manifest_attempt_launch_id(
                run_dir, bridge, authorization_launch_id, "stop"
            ),
            mutations=mutations,
            redaction_secrets=redaction_secrets,
        )
        return _report(
            "stop",
            run_dir,
            ok=False,
            rc=1,
            code=CODE_ORPHAN_AFTER_STOP,
            detail=orphan_detail,
            extra={
                "archive": gate,
                "stateSource": source,
                "afterStateSource": after_source,
                "mutations": mutations,
                "orphans": orphans,
                "postStopObservation": residue_observation,
                "stopAuthorization": stop_authorization,
                "manifest": stop_manifest,
            },
            redaction_secrets=redaction_secrets,
        )

    stop_manifest = _safe_record_stop_manifest(
        run_dir,
        bridge,
        status="stopped",
        ok=True,
        code=None,
        detail="",
        state=state,
        archive=gate,
        launch_id=_manifest_attempt_launch_id(
            run_dir, bridge, authorization_launch_id, "stop"
        ),
        mutations=mutations,
        redaction_secrets=redaction_secrets,
    )
    return _report(
        "stop",
        run_dir,
        ok=True,
        rc=0,
        extra={
            "archive": gate,
            "stateSource": source,
            "afterStateSource": after_source,
            "mutations": mutations,
            "orphans": [],
            "postStopObservation": residue_observation,
            "stopAuthorization": stop_authorization,
            "manifest": stop_manifest,
        },
        redaction_secrets=redaction_secrets,
    )


def _orphans_after(state: dict | None) -> list[str]:
    """D-007 (S9-R-03): delegate to the gate's one orphan scan; keep stop's id list."""
    report = openrig_gate.orphan_report(state)
    return [
        str(row.get("logicalId") or row.get("canonicalSessionName") or "?")
        for row in report["orphans"]
    ]


# ------------------------------------------------------------------ report
def _report(
    mode: str,
    run_dir: Path,
    *,
    ok: bool,
    rc: int,
    code: str | None = None,
    detail: str = "",
    plan: dict | None = None,
    extra: dict | None = None,
    redaction_secrets: tuple[str, ...] = (),
) -> dict:
    payload: dict = {
        "schemaVersion": SCHEMA,
        "mode": mode,
        "runDir": str(run_dir),
        "ok": ok,
        "rc": rc,
        "capturedAt": now(),
    }
    if code:
        payload["error"] = {"code": code, "message": detail}
    elif detail:
        payload["detail"] = detail
    if plan is not None:
        payload["continuity"] = plan
        payload["decisionStatus"] = plan.get("decisionStatus")
    if extra:
        payload.update(extra)
    if ok:
        payload.setdefault("note", "no live action is implied beyond the recorded mutations")
    if redaction_secrets:
        payload = _redact_report_value(payload, *redaction_secrets)
    return payload


# ------------------------------------------------------------------ plan file helper
def read_plan(run_dir: Path) -> dict | None:
    path = run_dir / PLAN_REL
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


if __name__ == "__main__":  # pragma: no cover - the CLI is openrig_run.py
    print("openrig_continuity is a library; use openrig_run.py resume|status|stop|next")
    sys.exit(2)
