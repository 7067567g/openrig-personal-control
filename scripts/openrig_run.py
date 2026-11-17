#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""openrig_run.py — ordered, fail-closed wrapper around `rig` for one workflow run (R11).

Usage:
  openrig_run.py check --run-dir <run-dir> [--json] [--allow-daemon-down] [--strict-render]
  openrig_run.py start --run-dir <run-dir> [--dry-run] [--timeout 120] [--json]
  openrig_run.py next  --run-dir <run-dir> [--json]        (R14: read-only paved road)

`check` runs, in order, and stops classifying as PASS on the first blocked step:

  1. read `openrig/OPENRIG-BRIDGE.json`                      missing/bad  -> rc 2
  2. load/validate historical findings policy                 missing/bad  -> blocks
                                                              (env -> bundle -> workspace default)
  3. `verify_render.py --run-dir ...`                         mismatch     -> WARN, blocks only with --strict-render
                                                              manifest rc2 -> blocks
  4. `tools/openrig_bridge.py doctor --run-dir ...`            rc != 0      -> blocks
  5. `<openrigCli> workflow validate <workflowSpec> --json`    rc != 0      -> blocks
  6. `<openrigCli> ps --nodes --rig <rigName> --json`          daemon down  -> blocks (or WARN with --allow-daemon-down)
                                                              a seat not ready -> blocks

Output `{ok, checks[], next[]}`; `ok:false` -> rc 1. rc 0 only when every blocking check passed.
Nothing here replaces `workflow instantiate` idempotency: a repeated `start` is still the rig's
own error to raise.

`start`:
  * writes `entry/managed-run.json` (if absent) and a fresh `entry/launch.json`
    (phase=starting, six single-use startup verbs plus the repeatable managed
    workflow-continuation verbs, 30 min TTL) BEFORE any `rig` subprocess;
    a write failure is rc 2 and starts zero children;
  * dry-run prints the exact ordered commands and executes **no** live action (no daemon,
    no `up`, no `workflow validate`, no `workflow instantiate`, no `ps`) but still writes
    the provenance records, marks the record `dryRun: true`, and always closes it
    (`phase=closed`) before returning — a dry run never leaves a live authorization
    behind (S9 W-S8-14);
  * otherwise: `check --allow-daemon-down`, then `daemon start --no-kernel --port`,
    `up <rigSpec> --cwd <projectRoot> --yes`, poll `ps` until every
    seatMap target is ready (bounded by --timeout), `workflow validate`,
    `workflow instantiate --root-objective ... --created-by ... --json`;
  * every child carries `OPENRIG_PORT`, `OPENRIG_ENTRY_LAUNCH_ID`, `OPENRIG_ENTRY_RUN_ID`;
  * the first failure stops the chain, closes the launch record, writes partial evidence
    under `<run-dir>/reports/evidence/<launchId>-start-partial.json`, and (default
    `--rollback auto`) stops a daemon this launch started when the rig never registered.
    It never deletes OPENRIG_HOME or the daemon DB; `--rollback manual` keeps the old
    print-only behaviour.

Dependency-free: standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# S9 Wave B — the supervisor's evidence (manifest) and boundary (gate) modules. Imported
# as plain sibling modules: openrig_run.py is executed as a script from scripts/, so its
# own directory is sys.path[0], and pytest injects it via conftest.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
import openrig_manifest as om  # noqa: E402
import openrig_gate as og  # noqa: E402
import openrig_findings as of  # noqa: E402
import openrig_runtime_output as ort  # noqa: E402

DEFAULT_DOCTOR = (
    ROOT / "templates" / "specialized" / "openrig-workflow-master" / "tools" / "openrig_bridge.py"
)

# S9 acceptance-matrix affordance. The frozen AT commands name their run dir as a bare
# fixture id (`--run-dir FI-02`), which is not a path in any repository. Resolution is
# read-only, applies ONLY to a missing relative path whose name matches `FI-*`, and only
# when the fixture root actually holds it, so a real run dir is never rewritten.
#
# S9-R-01: there is NO default root. A shared /tmp fallback silently re-created the
# W-S8-12 defect (two verifiers erasing each other's fixtures), so an unset
# OPENRIG_S9_FIXTURES now leaves the given path untouched and the caller gets the coded
# 'run dir missing' + provisioning hint instead of a quiet cross-verifier collision.
FIXTURE_ROOT_ENV = "OPENRIG_S9_FIXTURES"
FIXTURE_RUN_RE = re.compile(r"^FI-[A-Za-z0-9_.-]+$")


def fixture_root() -> Path | None:
    value = os.environ.get(FIXTURE_ROOT_ENV, "").strip()
    return Path(value) if value else None


def resolve_fixture_run_dir(run_dir: Path) -> Path:
    """Map a bare `FI-*` fixture name onto the per-verification fixture root."""
    if run_dir.is_absolute() or run_dir.exists():
        return run_dir
    if not FIXTURE_RUN_RE.match(run_dir.name):
        return run_dir
    root = fixture_root()
    if root is None:
        return run_dir
    candidate = root / run_dir
    return candidate if candidate.exists() else run_dir
BRIDGE_REL = Path("openrig") / "OPENRIG-BRIDGE.json"
SCHEMA = 1
REQUIRED_BRIDGE_KEYS = ("runId", "rigName", "workflowId", "openrigCli", "seatMap")
START_RECEIPT_REL = Path("reports") / "evidence" / "start-receipt.json"


# ------------------------------------------------------------------ helpers
def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _load_bridge(run_dir: Path) -> tuple[dict | None, str | None]:
    path = run_dir / BRIDGE_REL
    if not path.is_file():
        return None, f"bridge missing: {path}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return None, f"bridge is not valid JSON: {path}: {exc}"
    if not isinstance(data, dict):
        return None, f"bridge is not a JSON object: {path}"
    missing = [k for k in REQUIRED_BRIDGE_KEYS if not data.get(k)]
    if missing:
        return None, f"bridge missing required key(s): {', '.join(missing)}"
    if not isinstance(data.get("seatMap"), dict) or not data["seatMap"]:
        return None, "bridge seatMap must be a non-empty object"
    # P-S10-03: every child started for this run can spill its raw stream under
    # the run evidence tree without changing the `_run(cmd, bridge, timeout)`
    # signature that callers and tests rely on.
    data["_runtimeOutput"] = {"runDir": str(Path(run_dir).resolve())}
    return data, None


def _cli(bridge: dict) -> list[str]:
    try:
        return shlex.split(bridge.get("openrigCli") or "rig")
    except ValueError as exc:
        raise SystemExit(f"bridge openrigCli is not a valid command line: {exc}")


def _env(bridge: dict) -> dict:
    env = dict(os.environ)
    home = bridge.get("openrigHome")
    if home:
        env["OPENRIG_HOME"] = str(home)
    # S8 Wave A — the entry guard needs the same three values on every child:
    # the port the launch is bound to, the launch token, and the run identity.
    port = bridge.get("daemonPort")
    if port:
        env["OPENRIG_PORT"] = str(port)
    launch_id = bridge.get("_entryLaunchId")
    if launch_id:
        env["OPENRIG_ENTRY_LAUNCH_ID"] = str(launch_id)
    run_id = bridge.get("runId")
    if run_id:
        env["OPENRIG_ENTRY_RUN_ID"] = str(run_id)
    return env


def _run(cmd: list[str], bridge: dict, timeout: int = 120) -> subprocess.CompletedProcess:
    """Run one child with bounded capture; full streams spill to private evidence.

    The signature is intentionally unchanged: S9/S10 tests monkeypatch `_run`, and
    the capture location/label travel in the private `_runtimeOutput` bridge key.
    """
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
    """Attach a P-S10-03 capture label without changing `_run`'s public signature."""
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


def _json_or_none(text: str):
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        return None


def _check(cid: str, status: str, detail: str, **extra) -> dict:
    item = {"id": cid, "status": status, "detail": detail}
    item.update(extra)
    return item


def _doctor_path(run_dir: Path) -> Path | None:
    for candidate in (
        run_dir / "openrig" / "tools" / "openrig_bridge.py",
        run_dir / "tools" / "openrig_bridge.py",
        DEFAULT_DOCTOR,
    ):
        if candidate.is_file():
            return candidate
    return None


def _spec_path(run_dir: Path, bridge: dict, key: str, default: str) -> Path:
    rel = bridge.get(key) or default
    base = Path(bridge.get("bundleDir") or ".")
    if base.is_absolute():
        candidate = base / rel
    else:
        candidate = run_dir / "openrig" / base / rel
    return candidate


def _seat_rows(payload) -> list[dict]:
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in ("nodes", "rows", "seats"):
            if isinstance(payload.get(key), list):
                return [r for r in payload[key] if isinstance(r, dict)]
    return []


def _historical_findings_check(run_dir: Path, bridge: dict) -> dict:
    """The one runtime mount of the 106-entry findings policy (D24).

    A missing or invalid policy is a fail-closed check, never a skipped check.  The
    summary's path/sha and counts are copied into the check payload so a later auditor
    can tell exactly which matrix was loaded without re-reading the source corpus.
    """
    try:
        policy_path, reason = of.resolve_policy_path(bridge, run_dir)
        if policy_path is None:
            return _check(
                "historical_findings",
                "fail",
                "historical findings policy unavailable: " + (reason or "unknown reason"),
                reason=reason,
                blocking=True,
            )
        summary, error = of.load_policy(policy_path)
        if summary is None:
            return _check(
                "historical_findings",
                "fail",
                error or "historical findings policy failed validation",
                path=str(policy_path),
                reason=error,
                blocking=True,
            )
        detail = (
            f"findings={summary['findingsCount']} mapped={summary['mappedCount']} "
            f"deferred={summary['deferredCount']} path={summary['path']} "
            f"sha256={summary['sha256'][:12]}"
        )
        return _check("historical_findings", "ok", detail, **summary)
    except Exception as exc:  # noqa: BLE001 — a policy read must never crash the check
        return _check(
            "historical_findings",
            "fail",
            f"historical findings policy check crashed: {type(exc).__name__}: {exc}",
            reason=str(exc),
            blocking=True,
        )


# ------------------------------------------------------------------ checks
def run_check(
    run_dir: Path,
    *,
    allow_daemon_down: bool = False,
    strict_render: bool = False,
    live: bool = True,
    timeout: int = 120,
    launch_id: str | None = None,
) -> dict:
    """Return the check report. `live=False` skips every call that touches the rig.

    `launch_id` is threaded from `start` so its precheck children carry the same
    OPENRIG_ENTRY_LAUNCH_ID as the rest of the chain; a standalone `check` passes None.
    """
    checks: list[dict] = []
    next_steps: list[str] = []

    bridge, err = _load_bridge(run_dir)
    if bridge is None:
        checks.append(_check("bridge", "fail", err or "bridge unusable"))
        return {
            "schemaVersion": SCHEMA,
            "mode": "check",
            "runDir": str(run_dir),
            "ok": False,
            "checks": checks,
            "next": ["write openrig/OPENRIG-BRIDGE.json (rig name, cli, seatMap) before starting"],
            "capturedAt": _now(),
            "rc": 2,
        }
    if launch_id:
        bridge["_entryLaunchId"] = launch_id
    checks.append(
        _check(
            "bridge",
            "ok",
            f"runId={bridge['runId']} rig={bridge['rigName']} seats={len(bridge['seatMap'])}",
        )
    )

    # 2. historical findings policy: a static, blocking mount before any child process.
    #    Failing here returns immediately so `start` cannot reach daemon/up/instantiate.
    findings_check = _historical_findings_check(run_dir, bridge)
    checks.append(findings_check)
    if findings_check["status"] == "fail":
        next_steps.append(
            "provide a valid historical findings policy: set "
            f"{of.ENV_VAR} or place {of.POLICY_REL} in the run bundle "
            "(schemaVersion=1, findings=106, mapped>=90, deferred>=1)"
        )
        return {
            "schemaVersion": SCHEMA,
            "mode": "check",
            "runDir": str(run_dir),
            "runId": bridge["runId"],
            "rigName": bridge["rigName"],
            "workflowSpec": str(_spec_path(run_dir, bridge, "workflowSpec", "workflow.yaml")),
            "ok": False,
            "checks": checks,
            "next": next_steps,
            "capturedAt": _now(),
            "rc": 1,
        }

    # 3. render manifest
    render_cmd = [sys.executable, str(ROOT / "scripts" / "verify_render.py"), "--run-dir", str(run_dir), "--json"]
    proc = _run(render_cmd, _capture_bridge(bridge, "check-render", capture_id=f"{launch_id or 'check'}-check-render"), timeout)
    render = _json_or_none(proc.stdout) or {}
    if proc.returncode == 2 or render.get("error"):
        checks.append(
            _check(
                "render",
                "fail",
                f"verify_render needs a valid manifest: {render.get('error') or proc.stderr.strip()[:200]}",
                rc=proc.returncode,
            )
        )
        next_steps.append(
            f"render the bundle into {run_dir}/openrig (render_master.py) so render-manifest.json matches"
        )
    elif render.get("mismatches"):
        status = "fail" if strict_render else "warn"
        checks.append(
            _check(
                "render",
                status,
                f"{len(render['mismatches'])} file(s) differ from render-manifest.json"
                + ("" if strict_render else " (WARN: pass --strict-render to block)"),
                rc=0,
                mismatches=[m.get("path") for m in render["mismatches"]],
            )
        )
        next_steps.append("verify_render.py --run-dir <run-dir> --json  (or re-render the bundle)")
    else:
        checks.append(_check("render", "ok", f"{len(render.get('checked') or [])} file(s) match the manifest", rc=0))

    # 4. bundle doctor
    doctor = _doctor_path(run_dir)
    if doctor is None:
        checks.append(_check("doctor", "fail", "tools/openrig_bridge.py not found (run bundle or template)"))
        next_steps.append("restore templates/specialized/openrig-workflow-master/tools/openrig_bridge.py")
    else:
        proc = _run(
            [sys.executable, str(doctor), "doctor", "--run-dir", str(run_dir)],
            _capture_bridge(bridge, "check-doctor", capture_id=f"{launch_id or 'check'}-check-doctor"),
            timeout,
        )
        detail = (proc.stdout or proc.stderr or "").strip().splitlines()
        checks.append(
            _check(
                "doctor",
                "ok" if proc.returncode == 0 else "fail",
                detail[0] if detail else f"rc={proc.returncode}",
                rc=proc.returncode,
                tool=str(doctor),
            )
        )
        if proc.returncode != 0:
            next_steps.append(f"{doctor} doctor --run-dir {run_dir}")

    cli = _cli(bridge)
    workflow_spec = _spec_path(run_dir, bridge, "workflowSpec", "workflow.yaml")

    if not live:
        checks.append(_check("workflow_validate", "skipped", "not executed (local-only mode)"))
        checks.append(_check("seats", "skipped", "not executed (local-only mode)"))
    else:
        # 5. daemon + seat readiness first: workflow validate may need the daemon
        #    (and its OPENRIG_HOME). Pre-launch checks must still be able to run
        #    with --allow-daemon-down without a live daemon.
        proc = _run(
            [*cli, "ps", "--nodes", "--rig", str(bridge["rigName"]), "--json"],
            _capture_bridge(bridge, "check-ps", capture_id=f"{launch_id or 'check'}-check-ps"),
            timeout,
        )
        payload = _json_or_none(proc.stdout)
        daemon_down = proc.returncode != 0 or payload is None
        if daemon_down:
            status = "warn" if allow_daemon_down else "fail"
            checks.append(
                _check(
                    "seats",
                    status,
                    f"daemon unreachable (rc={proc.returncode})"
                    + (" — downgraded by --allow-daemon-down" if allow_daemon_down else ""),
                    rc=proc.returncode,
                )
            )
            # Validate cannot be trusted while the daemon/home is unavailable.
            # If the caller explicitly allows daemon-down, defer it to start.
            checks.append(
                _check(
                    "workflow_validate",
                    "skipped",
                    "daemon unreachable; validate after daemon start",
                )
            )
            next_steps.append(
                f"{' '.join(cli)} daemon start --no-kernel --port {bridge.get('daemonPort', '<port>')}"
            )
            next_steps.append(f"{' '.join(cli)} up {_spec_path(run_dir, bridge, 'rigSpec', 'rig.yaml')}")
            next_steps.append(f"{' '.join(cli)} workflow validate {workflow_spec} --json")
        else:
            # 6. workflow validate (daemon is up)
            proc = _run(
                [*cli, "workflow", "validate", str(workflow_spec), "--json"],
                _capture_bridge(bridge, "check-workflow-validate", capture_id=f"{launch_id or 'check'}-check-workflow-validate"),
                timeout,
            )
            ok = proc.returncode == 0
            if ok:
                try:
                    parsed = json.loads(proc.stdout)
                    ok = bool(parsed.get("ok", True))
                except Exception:  # noqa: BLE001
                    ok = True
            checks.append(
                _check(
                    "workflow_validate",
                    "ok" if ok else "fail",
                    f"spec={workflow_spec.name} rc={proc.returncode}"
                    + ("" if ok else f" stderr={proc.stderr.strip()[:200]}"),
                    rc=proc.returncode,
                )
            )
            if not ok:
                next_steps.append(f"{' '.join(cli)} workflow validate {workflow_spec} --json")

            # 7. seat readiness
            rows = _seat_rows(payload)
            by_session = {r.get("canonicalSessionName"): r for r in rows}
            missing, not_ready = [], []
            for role, target in bridge["seatMap"].items():
                row = by_session.get(target)
                if row is None:
                    missing.append(role)
                elif str(row.get("startupStatus")) != "ready":
                    not_ready.append(f"{role}={row.get('startupStatus')}")
            ok = not missing and not not_ready
            checks.append(
                _check(
                    "seats",
                    "ok" if ok else "fail",
                    (
                        f"{len(bridge['seatMap'])}/{len(bridge['seatMap'])} seats ready"
                        if ok
                        else f"missing={missing or '[]'} not_ready={not_ready or '[]'}"
                    ),
                    rc=proc.returncode,
                )
            )
            if not ok:
                next_steps.append(f"{' '.join(cli)} ps --nodes --rig {bridge['rigName']} --json")
                next_steps.append("wait for every seatMap target to reach startupStatus=ready")

    ok = not any(c["status"] == "fail" for c in checks)
    return {
        "schemaVersion": SCHEMA,
        "mode": "check",
        "runDir": str(run_dir),
        "runId": bridge["runId"],
        "rigName": bridge["rigName"],
        "workflowSpec": str(workflow_spec),
        "ok": ok,
        "checks": checks,
        "next": next_steps,
        "capturedAt": _now(),
        "rc": 0 if ok else 1,
    }


# ------------------------------------------------------- entry provenance (E0)
# S8 Wave A: `openrig-run start` is the ONE writer of the managed-run marker and the
# single-launch authorization. They are written BEFORE any `rig` subprocess so a
# denied/failed start can never look like an authorized one (D-S8-05/§4.6).
# S10 r3 S1-2 — the launch ticket carries two security classes:
#  - STARTUP_ENTRY_VERBS are single-consumption. The TS guard claims each one
#    in the launch-scoped ledger so a replay in a later process is denied.
#  - CONTINUATION_ENTRY_VERBS are repeatable for the lifetime of the same launch
#    record. A managed seat closes its workflow steps with `rig workflow project`
#    (and may route/resume/abort/revise) many times. The guard still requires this
#    live record, its TTL, phase, home and OPENRIG_ENTRY_LAUNCH_ID token; it simply
#    does not consume the single-use ledger for these verbs.
# Keep this tuple in lockstep with packages/daemon/src/entry-guard.ts.
STARTUP_ENTRY_VERBS = (
    "daemon-start",
    "up",
    "restore-apply",
    "workflow-instantiate",
    "workflow-instantiate-lifecycle",
    "workflow-run",
)
CONTINUATION_ENTRY_VERBS = (
    "workflow-route",
    "workflow-resume",
    "workflow-abort",
    "workflow-revision",
    "workflow-project",
)
ENTRY_VERBS = STARTUP_ENTRY_VERBS + CONTINUATION_ENTRY_VERBS
ENTRY_MARKER_REL = Path("entry") / "managed-run.json"
ENTRY_LAUNCH_REL = Path("entry") / "launch.json"
DEFAULT_LAUNCH_TTL_SECONDS = 30 * 60


class EntryRecordError(RuntimeError):
    """The provenance records could not be written/validated; no rig call is allowed."""


def _entry_home(bridge: dict) -> Path:
    home = bridge.get("openrigHome") or os.environ.get("OPENRIG_HOME")
    if not home:
        raise EntryRecordError(
            "bridge.openrigHome is missing; refusing to guess a run home for entry provenance"
        )
    return Path(str(home)).expanduser()


def _iso_utc(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write_json(path: Path, payload: dict) -> None:
    """Atomic 0600 JSON write for launch records and partial runtime evidence.

    Shares the locked unique-temp writer with manifest/receipt writers: a fixed
    ``<name>.tmp`` path races concurrent launch writers, and a rename failure must
    not leave a half file behind.
    """
    om.write_atomic(path, payload, mode=0o600)


def write_entry_records(
    run_dir: Path,
    bridge: dict,
    *,
    ttl_seconds: int = DEFAULT_LAUNCH_TTL_SECONDS,
    dry_run: bool = False,
) -> str:
    """Write the S1 marker (if absent) and a fresh phase=starting launch record.

    Returns the new launchId. Raises EntryRecordError on any failure; the caller
    turns that into rc 2 with zero subprocesses started.

    `dry_run=True` marks the record `dryRun: true` at write time, so even a crash
    before the writer can close it leaves a record the guard refuses (W-S8-14).
    """
    home = _entry_home(bridge)
    run_id = str(bridge["runId"])
    marker_path = home / ENTRY_MARKER_REL
    try:
        if marker_path.is_file():
            try:
                marker = json.loads(marker_path.read_text(encoding="utf-8"))
            except ValueError as exc:  # JSONDecodeError / UnicodeDecodeError
                raise EntryRecordError(
                    f"managed-run marker is not valid JSON: {marker_path}: {exc}"
                ) from exc
            if not isinstance(marker, dict):
                raise EntryRecordError(f"managed-run marker is not an object: {marker_path}")
            if str(marker.get("runId") or "") != run_id:
                raise EntryRecordError(
                    f"managed-run marker belongs to run {marker.get('runId')!r}, not {run_id!r}: {marker_path}"
                )
        else:
            _atomic_write_json(
                marker_path,
                {
                    "schemaVersion": 1,
                    "runId": run_id,
                    "rigName": str(bridge.get("rigName") or ""),
                    "workflowId": str(bridge.get("workflowId") or ""),
                    "bundleDir": str(bridge.get("bundleDir") or "."),
                    "createdAt": _iso_utc(datetime.now(timezone.utc)),
                    "createdBy": "openrig-run start",
                    "entryCommand": "openrig-run start",
                },
            )

        launch_id = f"launch-{uuid.uuid4()}"
        now = datetime.now(timezone.utc)
        launch = {
            "schemaVersion": 1,
            "launchId": launch_id,
            "home": str(home.resolve()),
            "runId": run_id,
            "rigName": str(bridge.get("rigName") or ""),
            "workflowId": str(bridge.get("workflowId") or ""),
            "verbs": list(ENTRY_VERBS),
            "consumed": [],
            "phase": "starting",
            "dryRun": bool(dry_run),
            "createdAt": _iso_utc(now),
            "expiresAt": _iso_utc(now + timedelta(seconds=max(int(ttl_seconds), 1))),
        }
        _atomic_write_json(home / ENTRY_LAUNCH_REL, launch)
        return launch_id
    except EntryRecordError:
        raise
    except (OSError, om.ManifestWriteError) as exc:
        raise EntryRecordError(f"cannot write entry provenance under {home}: {exc}") from exc


def _rewrite_launch(home: Path, launch_id: str, **changes) -> bool:
    path = home / ENTRY_LAUNCH_REL
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(data, dict) or data.get("launchId") != launch_id:
        return False
    data.update(changes)
    try:
        _atomic_write_json(path, data)
    except (OSError, om.ManifestWriteError):
        return False
    return True


def activate_entry_records(home: Path, launch_id: str) -> bool:
    return _rewrite_launch(
        home, launch_id, phase="active", activatedAt=_iso_utc(datetime.now(timezone.utc))
    )


def close_entry_records(home: Path, launch_id: str, reason: str) -> bool:
    return _rewrite_launch(
        home,
        launch_id,
        phase="closed",
        closedAt=_iso_utc(datetime.now(timezone.utc)),
        closureReason=reason,
    )


def _entry_report(home: Path, launch_id: str) -> dict:
    return {
        "launchId": launch_id,
        "home": str(home),
        "managedRun": str(home / ENTRY_MARKER_REL),
        "launchRecord": str(home / ENTRY_LAUNCH_REL),
    }


# ------------------------------------------------------------------ start
def _root_objective(bridge: dict) -> str:
    for key in ("rootObjective", "objective", "missionObjective"):
        value = bridge.get(key)
        if value:
            return str(value)
    return f"Run {bridge['runId']}"


def _created_by(bridge: dict) -> str:
    explicit = bridge.get("createdBy")
    if explicit:
        return str(explicit)
    seats = bridge.get("seatMap") or {}
    for role in ("main", "pmo", "pm", "operator"):
        if seats.get(role):
            return str(seats[role])
    if seats:
        return str(next(iter(seats.values())))
    return f"main@{bridge.get('rigName') or 'rig'}"


def _project_root(run_dir: Path, bridge: dict) -> str:
    value = bridge.get("projectRoot") or bridge.get("bundleDir")
    if not value:
        return str(run_dir)
    path = Path(str(value)).expanduser()
    return str(path if path.is_absolute() else (run_dir / path))


def build_start_plan(run_dir: Path, bridge: dict) -> list[dict]:
    cli = _cli(bridge)
    rig_spec = _spec_path(run_dir, bridge, "rigSpec", "rig.yaml")
    workflow_spec = _spec_path(run_dir, bridge, "workflowSpec", "workflow.yaml")
    port = bridge.get("daemonPort")
    return [
        {
            "step": "daemon-start",
            "cmd": [*cli, "daemon", "start", "--no-kernel", *(["--port", str(port)] if port else [])],
        },
        {
            "step": "up",
            # B5: a managed start must never sit on a harness prompt and must
            # launch seats in the run's project root, not the caller's cwd.
            "cmd": [
                *cli,
                "up",
                str(rig_spec),
                "--cwd",
                _project_root(run_dir, bridge),
                "--yes",
            ],
        },
        {
            "step": "wait-ready",
            "cmd": [*cli, "ps", "--nodes", "--rig", str(bridge["rigName"]), "--json"],
            "poll": True,
        },
        {"step": "workflow-validate", "cmd": [*cli, "workflow", "validate", str(workflow_spec), "--json"]},
        {
            "step": "workflow-instantiate",
            # B4: instantiate REQUIRES these two options (workflow.ts requiredOption).
            "cmd": [
                *cli,
                "workflow",
                "instantiate",
                str(workflow_spec),
                "--root-objective",
                _root_objective(bridge),
                "--created-by",
                _created_by(bridge),
                "--json",
            ],
        },
    ]


def _poll_ready_details(
    run_dir: Path, bridge: dict, timeout: int, cli: list[str]
) -> tuple[bool, str, list[dict], subprocess.CompletedProcess]:
    """Poll `ps --nodes` until every seatMap target is ready.

    Returns the last observed rows *and* the last process capture.  P-S10-03 needs
    the capture because the failed poll is often the only child output on a partial
    start; the private capture id is stable so repeated polls replace, rather than
    accumulate, their spill files.
    """
    _ = run_dir
    deadline = time.time() + max(int(timeout), 0)
    last = "no attempt"
    rows: list[dict] = []
    launch_id = str(bridge.get("_entryLaunchId") or "wait")
    capture_id = f"{launch_id}-wait-ready"
    last_proc: subprocess.CompletedProcess | None = None
    while True:
        poll_bridge = _capture_bridge(bridge, "wait-ready", capture_id=capture_id)
        proc = _run(
            [*cli, "ps", "--nodes", "--rig", str(bridge["rigName"]), "--json"],
            poll_bridge,
            60,
        )
        last_proc = proc
        rows = _seat_rows(_json_or_none(proc.stdout) or [])
        by_session = {r.get("canonicalSessionName"): r for r in rows}
        pending = []
        for role, target in bridge["seatMap"].items():
            row = by_session.get(target)
            if row is None:
                pending.append(f"{role}=absent")
            elif str(row.get("startupStatus")) != "ready":
                pending.append(f"{role}={row.get('startupStatus')}")
        if not pending:
            return True, "all seats ready", rows, proc
        last = ", ".join(pending)
        if time.time() >= deadline:
            return False, f"timeout after {timeout}s waiting for {last}", rows, proc
        time.sleep(2)


def _poll_ready(run_dir: Path, bridge: dict, timeout: int, cli: list[str]) -> tuple[bool, str]:
    """Backward-compatible two-value wrapper around `_poll_ready_details`."""
    ok, detail, _rows, _proc = _poll_ready_details(run_dir, bridge, timeout, cli)
    return ok, detail


def run_start(
    run_dir: Path, *, dry_run: bool, timeout: int = 120, rollback_mode: str = "auto"
) -> dict:
    bridge, err = _load_bridge(run_dir)
    if bridge is None:
        return {
            "schemaVersion": SCHEMA,
            "mode": "start",
            "dryRun": bool(dry_run),
            "runDir": str(run_dir),
            "ok": False,
            "error": err,
            "plan": [],
            "executed": [],
            "rc": 2,
            "capturedAt": _now(),
        }

    # E0: provenance BEFORE any rig subprocess. A write failure is rc 2 with zero
    # children started — never a start that runs without an authorization record.
    try:
        home = _entry_home(bridge)
        launch_id = write_entry_records(run_dir, bridge, dry_run=dry_run)
    except EntryRecordError as exc:
        return {
            "schemaVersion": SCHEMA,
            "mode": "start",
            "dryRun": bool(dry_run),
            "runDir": str(run_dir),
            "runId": bridge["runId"],
            "rigName": bridge["rigName"],
            "ok": False,
            "error": str(exc),
            "plan": [],
            "executed": [],
            "rc": 2,
            "capturedAt": _now(),
        }
    bridge["_entryLaunchId"] = launch_id
    provenance = _entry_report(home, launch_id)
    plan = build_start_plan(run_dir, bridge)

    # IO-EVIDENCE-MANIFEST §5.4 — a run that already started is not started again. The
    # manifest is the proof (a prior completed start); the observed rig state is the
    # weaker signal used below when no manifest exists.
    previous_manifest = om.load_manifest(run_dir)
    if previous_manifest is not None and str(previous_manifest.get("status")) in ("starting", "active"):
        close_entry_records(home, launch_id, "start refused: run already started")
        return {
            "schemaVersion": SCHEMA,
            "mode": "start",
            "dryRun": bool(dry_run),
            "runDir": str(run_dir),
            "runId": bridge["runId"],
            "rigName": bridge["rigName"],
            "ok": False,
            "error": {
                "code": "run_exists",
                "message": (
                    f"run {bridge['runId']} already has a manifest (status="
                    f"{previous_manifest.get('status')}, revision={previous_manifest.get('revision')}); "
                    "a retry reuses its operationId instead of starting a second run"
                ),
                "hint": f"openrig-run resume --run-dir {run_dir} --json",
                "manifest": str(run_dir / om.MANIFEST_REL),
                "operationId": previous_manifest.get("manifestId"),
                "launchId": previous_manifest.get("launchId"),
            },
            "plan": plan,
            "executed": [],
            "provenance": provenance,
            "rc": 1,
            "capturedAt": _now(),
        }

    # §4.1 — `start` creates; it never repairs. If the run bundle says a rig is still
    # present, the only honest answer is "resume", with the exact command.
    existing = _existing_rig_state(run_dir)
    if existing is not None and existing.get("rigState") == "present":
        close_entry_records(home, launch_id, "start refused: rig already exists")
        return {
            "schemaVersion": SCHEMA,
            "mode": "start",
            "dryRun": bool(dry_run),
            "runDir": str(run_dir),
            "runId": bridge["runId"],
            "rigName": bridge["rigName"],
            "ok": False,
            "error": {
                "code": "rig_exists",
                "message": (
                    f"rig {bridge['rigName']} is present; start creates a new run and would "
                    "archive the existing team"
                ),
                "hint": f"openrig-run resume --run-dir {run_dir} --json",
            },
            "plan": plan,
            "executed": [],
            "provenance": provenance,
            "rc": 2,
            "capturedAt": _now(),
        }

    if dry_run:
        precheck = run_check(
            run_dir, allow_daemon_down=True, live=False, timeout=timeout, launch_id=launch_id
        )
        ok = precheck["ok"]
        # S9 W-S8-14 — a dry run must not leave a live authorization behind, whether or
        # not its precheck passed. Closing is the last thing it does; a close that fails
        # is itself a failure (the ticket would still be live), never a silent success.
        closed = close_entry_records(
            home,
            launch_id,
            "dry-run: no live action" if ok else "dry-run precheck failed",
        )
        provenance = {
            **provenance,
            "phase": "closed" if closed else "starting",
            "dryRun": True,
        }
        report = {
            "schemaVersion": SCHEMA,
            "mode": "start",
            "dryRun": True,
            "runDir": str(run_dir),
            "runId": bridge["runId"],
            "rigName": bridge["rigName"],
            "ok": ok and closed,
            "plan": plan,
            "executed": [],
            "precheck": precheck,
            "provenance": provenance,
            "note": "dry-run: no daemon start, no up, no workflow validate/instantiate, no ps",
            "rc": 0 if (ok and closed) else 1,
            "capturedAt": _now(),
        }
        if not closed:
            report["ok"] = False
            report["error"] = {
                "code": "entry_guard_close_failed",
                "message": (
                    f"dry-run wrote {provenance['launchRecord']} but could not close it; "
                    "treat the launch as live and inspect the home before any start"
                ),
            }
            report["rc"] = 2
        return report

    executed: list[dict] = []
    observed_seats: list[dict] = []

    # IO §2 — the manifest exists from the FIRST live action, so a failure can always
    # write a partial instead of only stderr. The port gate runs before anything spawns.
    manifest = om.new_manifest(
        run_dir,
        bridge,
        launch_id=launch_id,
        intent="fresh",
        operation_id=str((previous_manifest or {}).get("manifestId") or ""),
        env=dict(os.environ),
    )
    for rel, kind in (
        (Path("openrig") / "OPENRIG-BRIDGE.json", "bridge"),
        (Path("openrig") / str(bridge.get("rigSpec") or "rig.yaml"), "rig-spec"),
        (Path("openrig") / str(bridge.get("workflowSpec") or "workflow.yaml"), "workflow-spec"),
        (Path("openrig") / "render-manifest.json", "render-manifest"),
    ):
        om.add_input(manifest, run_dir, rel, kind=kind)
    om.add_input(manifest, home, home / ENTRY_MARKER_REL, kind="entry-marker", required=False)

    port_check = og.check_port(
        bridge.get("daemonPort"), home, state=_existing_rig_state(run_dir)
    )
    if not port_check["ok"]:
        close_entry_records(home, launch_id, f"start refused: {port_check['code']}")
        om.finalize_manifest(
            manifest,
            status="failed",
            seats=[],
            outputs=[],
            seats_not_applicable_reason="start_refused_before_seat_observation",
            outputs_not_applicable_reason="start_refused_before_output_receipt",
        )
        partial = None
        partial_manifest_error = None
        try:
            partial = om.write_partial(
                run_dir,
                manifest,
                reason=port_check["reason"],
                rc=2,
                executed=[],
                unexecuted=[item["step"] for item in plan],
            )
        except (OSError, om.ManifestWriteError) as exc:
            # The port refusal is the real start failure; a refused evidence write is
            # reported alongside it, never allowed to replace it with a traceback.
            partial_manifest_error = str(exc)
        return {
            "schemaVersion": SCHEMA,
            "mode": "start",
            "dryRun": False,
            "runDir": str(run_dir),
            "runId": bridge["runId"],
            "rigName": bridge["rigName"],
            "ok": False,
            "error": {
                "code": port_check["code"],
                "message": port_check["reason"],
                "hint": "inspect the listener (rig daemon status) or start on another port",
            },
            "port": port_check,
            "plan": plan,
            "executed": [],
            "partialManifest": (partial or {}).get("path"),
            "partialManifestError": partial_manifest_error,
            "rc": 2,
            "capturedAt": _now(),
        }
    _t0 = om.now_iso()
    precheck = run_check(
        run_dir, allow_daemon_down=True, timeout=timeout, launch_id=launch_id
    )
    executed.append(
        {
            "step": "precheck",
            "rc": precheck["rc"],
            "ok": precheck["ok"],
            "cmd": ["openrig-run", "check", "--run-dir", str(run_dir), "--allow-daemon-down"],
            "startedAt": _t0,
            "endedAt": om.now_iso(),
        }
    )
    if not precheck["ok"]:
        failed_checks = [
            check for check in precheck.get("checks") or [] if check.get("status") == "fail"
        ]
        if failed_checks:
            first = failed_checks[0]
            precheck_detail = (
                f"precheck failed at {first.get('id')}: {first.get('detail')}; "
                "no daemon, up, or instantiate was attempted"
            )
        else:
            precheck_detail = "precheck failed; no daemon, up, or instantiate was attempted"
        return _start_failed(
            run_dir,
            bridge,
            executed,
            "precheck",
            precheck_detail,
            timeout,
            launch_id=launch_id,
            home=home,
            rollback_mode=rollback_mode,
            provenance=provenance,
            manifest=manifest,
            plan=plan,
            observed_seats=observed_seats,
        )

    cli = _cli(bridge)
    for item in plan:
        step = item["step"]
        if item.get("poll"):
            _t0 = om.now_iso()
            ok, detail, ps_rows, poll_proc = _poll_ready_details(
                run_dir, bridge, timeout, cli
            )
            ort.ensure_evidence(
                poll_proc,
                run_dir=run_dir,
                label=step,
                redaction_secrets=ort.context_secrets(bridge),
            )
            poll_entry = {
                "step": step,
                "rc": 0 if ok else 1,
                "ok": ok,
                "detail": detail,
                "cmd": om.redact_cmd(item["cmd"])[0],
                "startedAt": _t0,
                "endedAt": om.now_iso(),
                "psRows": ps_rows,
                **ort.capture_fields(
                    poll_proc, redaction_secrets=ort.context_secrets(bridge)
                ),
            }
            executed.append(poll_entry)
            if ok:
                # P-S10-02: seats[] is the real ps answer mapped through bridge.seatMap,
                # not a count and not a fixture guess. Failure before this point leaves
                # observed_seats empty and _start_failed writes a machine-readable reason.
                observed_seats = om.seats_from_ps(bridge, ps_rows)
            if not ok:
                return _start_failed(
                    run_dir,
                    bridge,
                    executed,
                    step,
                    detail,
                    timeout,
                    launch_id=launch_id,
                    home=home,
                    rollback_mode=rollback_mode,
                    provenance=provenance,
                    manifest=manifest,
                    plan=plan,
                    observed_seats=observed_seats,
                )
            continue
        _t0 = om.now_iso()
        step_bridge = _capture_bridge(
            bridge, step, capture_id=f"{launch_id}-{step}"
        )
        proc = _run(item["cmd"], step_bridge, timeout)
        ort.ensure_evidence(
            proc,
            run_dir=run_dir,
            label=step,
            redaction_secrets=ort.context_secrets(bridge),
        )
        captured = ort.capture_fields(
            proc, redaction_secrets=ort.context_secrets(bridge)
        )
        exec_item = {
            "step": step,
            "rc": proc.returncode,
            "ok": proc.returncode == 0,
            "cmd": om.redact_cmd(item["cmd"])[0],
            "startedAt": _t0,
            "endedAt": om.now_iso(),
            "cwd": os.getcwd(),
            **captured,
        }
        executed.append(exec_item)
        if proc.returncode != 0:
            detail = (captured.get("stderrTail") or captured.get("stdoutTail") or "").strip()[:300]
            return _start_failed(
                run_dir,
                bridge,
                executed,
                step,
                detail or f"rc={proc.returncode}",
                timeout,
                launch_id=launch_id,
                home=home,
                rollback_mode=rollback_mode,
                provenance=provenance,
                manifest=manifest,
                plan=plan,
                observed_seats=observed_seats,
            )

    activated = activate_entry_records(home, launch_id)
    provenance = {**provenance, "phase": "active" if activated else "starting"}

    # IO §2 — the success manifest. Every step carries both timestamps (§6.3), argv is
    # redacted, and inputs are referenced by path+hash rather than copied (§2.3).
    manifest["steps"] = [
        om.step_receipt(
            str(entry.get("step")),
            entry.get("cmd") or [str(entry.get("step"))],
            cwd=str(entry.get("cwd") or run_dir),
            rc=int(entry.get("rc") or 0),
            started_at=str(entry.get("startedAt") or om.now_iso()),
            ended_at=str(entry.get("endedAt") or om.now_iso()),
            stdout_sha256=entry.get("stdoutSha256"),
            stderr_sha256=entry.get("stderrSha256"),
            evidence_path=entry.get("evidencePath"),
        )
        for entry in executed
    ]
    manifest["status"] = "active"
    om.set_archive(manifest, og.archive_status(run_dir)["status"])
    # P-011: read the identity from the instantiate step's own stdout. A successful live
    # start that records instanceId=null is not an attestable manifest, whatever its rc.
    instance_id, entry_qitem_id = _workflow_identity(run_dir, executed)
    manifest["workflow"]["instanceId"] = (
        instance_id or manifest["workflow"].get("instanceId") or "")
    manifest["workflow"]["entryQitemId"] = (
        entry_qitem_id or manifest["workflow"].get("entryQitemId") or "")
    om.add_input(manifest, home, home / ENTRY_LAUNCH_REL, kind="entry-launch", required=False)
    om.add_input(
        manifest,
        run_dir,
        run_dir / "reports" / "evidence" / "manifest" / "continuity-plan.json",
        kind="continuity-plan",
        required=False,
    )

    # P-S10-02: a success start writes a real receipt FIRST, then records that exact
    # file (path + sha256 + bytes) in outputs[]. The receipt has no env/cmd body, so a
    # launch token cannot leak into it.
    start_receipt = None
    receipt_error = None
    try:
        receipt_payload = {
            "schemaVersion": SCHEMA,
            "kind": "start-receipt",
            "runId": bridge.get("runId"),
            "launchId": launch_id,
            "workflow": {
                "instanceId": manifest["workflow"].get("instanceId"),
                "entryQitemId": manifest["workflow"].get("entryQitemId"),
            },
            "seats": manifest.get("seats") or observed_seats,
            "stepCount": len(manifest["steps"]),
            "steps": _step_evidence_summary(executed),
            "status": "active",
            "manifestId": manifest.get("manifestId"),
            "revision": manifest.get("revision"),
            "capturedAt": om.now_iso(),
        }
        start_receipt = om.write_receipt(run_dir, START_RECEIPT_REL, receipt_payload)
        om.finalize_manifest(
            manifest,
            status="active",
            seats=observed_seats,
            outputs=[
                {
                    "path": start_receipt["path"],
                    "producer": "openrig-run start",
                    "consumer": "archive/operator",
                    "retention": "run",
                }
            ],
            seats_not_applicable_reason="start_succeeded_without_a_seat_observation",
            outputs_not_applicable_reason="start_receipt_not_written",
        )
    except (OSError, ValueError, FileNotFoundError) as exc:
        # Never fake an output: keep the manifest honest, fail the attestation, and
        # carry the machine-readable reason for the empty array.
        receipt_error = str(exc)
        om.finalize_manifest(
            manifest,
            status="active",
            seats=observed_seats,
            outputs=[],
            seats_not_applicable_reason="start_succeeded_without_a_seat_observation",
            outputs_not_applicable_reason=f"start_receipt_write_failed: {exc}",
        )

    written = om.write_manifest(run_dir, manifest)
    report = {
        "schemaVersion": SCHEMA,
        "mode": "start",
        "dryRun": False,
        "runDir": str(run_dir),
        "runId": bridge["runId"],
        "rigName": bridge["rigName"],
        "ok": True,
        "executed": executed,
        "provenance": provenance,
        "manifest": written,
        "startReceipt": start_receipt,
        "rc": 0,
        "capturedAt": _now(),
    }
    if receipt_error:
        report["ok"] = False
        report["error"] = {
            "code": "start_receipt_failed",
            "message": receipt_error,
        }
        report["rc"] = 1
    if written.get("missingKeys"):
        # A manifest missing a required key is not a success we can attest (§2.1).
        report["ok"] = False
        report["error"] = {
            "code": "manifest_incomplete",
            "message": f"manifest missing required key(s): {written['missingKeys']}",
        }
        report["rc"] = 1
    return report


def _workflow_instance_from(run_dir: Path) -> str | None:
    """Best-effort read of the instance id from the FIXTURE state file.

    Live runs have no `continuity-state.json`, which is why `start` used to write
    `workflow.instanceId: null` on a successful live start (P-011). Kept as a fixture
    fallback only; `_workflow_identity` is the live-capable reader.
    """
    state = _existing_rig_state(run_dir)
    if state and state.get("workflowInstanceId"):
        return str(state["workflowInstanceId"])
    return None


def _instantiate_identity(stdout: str) -> tuple[str | None, str | None]:
    """(instanceId, entryQitemId) from `workflow instantiate --json` stdout.

    The product answers with `{"instance": {"instanceId": ..., "currentFrontier": [...]}}`;
    the first frontier entry is the entry-step qitem. Returns (None, None) rather than
    inventing anything when the payload is not that shape.
    """
    try:
        payload = json.loads(stdout or "")
    except Exception:  # noqa: BLE001
        return None, None
    instance = payload.get("instance") if isinstance(payload, dict) else None
    if not isinstance(instance, dict):
        return None, None
    frontier = instance.get("currentFrontier") or []
    entry_qitem = str(frontier[0]) if isinstance(frontier, list) and frontier else None
    instance_id = str(instance["instanceId"]) if instance.get("instanceId") else None
    return instance_id, entry_qitem


_STEP_EVIDENCE_KEYS = (
    "step",
    "rc",
    "ok",
    "cmd",
    "cwd",
    "startedAt",
    "endedAt",
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
)


def _step_evidence_summary(executed: list[dict]) -> list[dict]:
    """Bounded per-step evidence for receipts; no raw stdout/stderr and no env."""
    return [
        {key: entry.get(key) for key in _STEP_EVIDENCE_KEYS if key in entry}
        for entry in executed
        if isinstance(entry, dict)
    ]


def _executed_stdout(entry: dict) -> str:
    """Return a bounded view of a step's stdout for identity parsing.

    New captures keep full bytes on disk (`stdoutPath`) and may expose only a tail
    in the compatibility field.  Small outputs are read from the spill so the
    instantiate JSON is still available without a second in-memory copy.
    """
    direct = entry.get("stdout")
    if isinstance(direct, str) and direct:
        return direct
    path = entry.get("stdoutPath")
    if isinstance(path, str) and path:
        return ort.read_spill_text(path)
    return ""


def _workflow_identity(run_dir: Path, executed: list[dict]) -> tuple[str | None, str | None]:
    """Identity for the manifest: the instantiate STEP first, the fixture state only when
    no instantiate step was executed at all.

    A failed instantiate step fails CLOSED: its stdout is an error payload, and falling back
    to a fixture `continuity-state.json` would let a failed run inherit a fake instance id
    (S10 P-011b, N-CT-03). The fixture path remains for fixture-only runs with no step.
    """
    step_seen = False
    step_instance: str | None = None
    step_qitem: str | None = None
    for entry in executed:
        if entry.get("step") != "workflow-instantiate":
            continue
        step_seen = True
        if int(entry.get("rc") or 0) != 0:
            return (None, None)
        instance_id, qitem_id = _instantiate_identity(_executed_stdout(entry))
        step_instance, step_qitem = instance_id, qitem_id
        if step_instance:
            break
    if step_seen:
        return (step_instance, step_qitem)
    return (_workflow_instance_from(run_dir), None)


def _auto_rollback(bridge: dict, executed: list[dict], rollback_mode: str) -> list[dict]:
    """Stop a daemon this launch started when the rig never registered.

    Never deletes OPENRIG_HOME or the daemon DB. `--rollback manual` skips this and
    leaves the operator the printed hint (the pre-S8 behaviour).
    """
    if rollback_mode == "manual":
        return []
    daemon_started = any(
        e.get("step") == "daemon-start" and e.get("ok") for e in executed
    )
    rig_registered = any(e.get("step") == "up" and e.get("ok") for e in executed)
    if not daemon_started or rig_registered:
        return []
    cli = _cli(bridge)
    launch_id = str(bridge.get("_entryLaunchId") or "rollback")
    rollback_bridge = _capture_bridge(
        bridge,
        "rollback-daemon-stop",
        capture_id=f"{launch_id}-rollback-daemon-stop",
    )
    proc = _run([*cli, "daemon", "stop"], rollback_bridge, 60)
    captured = ort.capture_fields(
        proc, redaction_secrets=ort.context_secrets(bridge)
    )
    detail = (captured.get("stderrTail") or captured.get("stdoutTail") or "").strip()[:300]
    return [
        {
            "step": "daemon-stop",
            "rc": proc.returncode,
            "ok": proc.returncode == 0,
            "detail": detail or f"rc={proc.returncode}",
        }
    ]


def _existing_rig_state(run_dir: Path) -> dict | None:
    """The bundle's own observation of "is a rig already here?" (§4.1).

    Read-only and fixture-friendly: the same file `openrig_continuity` reads. Absent means
    "nothing claims a rig exists", which keeps `start` working on a fresh bundle.
    """
    path = run_dir / "openrig" / "continuity-state.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    return data if isinstance(data, dict) else None


def _start_failed(
    run_dir,
    bridge,
    executed,
    step,
    detail,
    timeout,
    *,
    launch_id=None,
    home=None,
    rollback_mode="auto",
    provenance=None,
    manifest=None,
    plan=None,
    observed_seats=None,
) -> dict:
    actions = _auto_rollback(bridge, executed, rollback_mode)
    closed = False
    if home is not None and launch_id:
        closed = close_entry_records(home, launch_id, f"start failed at {step}")

    rollback = (
        f"stopped at '{step}'. Roll back with: "
        f"{' '.join(_cli(bridge))} down {bridge['rigName']}  "
        "(keeps OPENRIG_HOME and the daemon DB; delete nothing automatically)."
        f" Do not re-run instantiate blindly — the rig rejects duplicates itself."
    )
    if step == "precheck":
        rollback = "nothing was started; fix the failing check and re-run"
    if actions:
        summary = ", ".join(f"{a['step']} rc={a['rc']}" for a in actions)
        rollback = f"{rollback} Auto rollback: {summary}."

    partial_path = None
    partial_error = None
    if launch_id:
        target = run_dir / "reports" / "evidence" / f"{launch_id}-start-partial.json"
        try:
            _atomic_write_json(
                target,
                {
                    "schemaVersion": SCHEMA,
                    "launchId": launch_id,
                    "runId": bridge.get("runId"),
                    "rigName": bridge.get("rigName"),
                    "failedStep": step,
                    "detail": detail,
                    "executed": executed,
                    "rollbackActions": actions,
                    "rollbackMode": rollback_mode,
                    "entryClosed": closed,
                    "rollback": rollback,
                    "provenance": provenance,
                    "capturedAt": _now(),
                },
            )
            partial_path = str(target)
        except (OSError, om.ManifestWriteError) as exc:
            # The start already failed.  A refused evidence write must be reported,
            # never allowed to replace that original failure with a traceback.
            partial_path = None
            partial_error = str(exc)

    # IO §2.4/§5.3 — a failure is evidence. The code is derived from the step so a
    # reader (and the acceptance matrix) can name the boundary that refused:
    # 'up' -> up_failed, 'daemon-start' -> daemon_start_failed, 'workflow-instantiate'
    # -> workflow_instantiate_failed.
    failure_code = f"{str(step).replace('-', '_')}_failed"
    executed_steps = [entry.get("step") for entry in executed]
    planned_steps = [item.get("step") for item in (plan or [])]
    unexecuted = [name for name in planned_steps if name not in executed_steps]
    partial_manifest = None
    partial_manifest_error = None
    if manifest is not None:
        receipts = [
            om.step_receipt(
                str(entry.get("step")),
                entry.get("cmd") or [str(entry.get("step"))],
                cwd=str(entry.get("cwd") or run_dir),
                rc=int(entry.get("rc") or 0),
                started_at=str(entry.get("startedAt") or om.now_iso()),
                ended_at=str(entry.get("endedAt") or om.now_iso()),
                partial=not entry.get("ok", True),
                stdout_sha256=entry.get("stdoutSha256"),
                stderr_sha256=entry.get("stderrSha256"),
                evidence_path=entry.get("evidencePath"),
            )
            for entry in executed
        ]
        manifest["steps"] = receipts
        om.set_archive(manifest, og.archive_status(run_dir)["status"])
        # P-S10-02: a failed start never leaves seats/outputs silently empty. If a
        # ready poll really happened the observed rows are kept; otherwise the arrays
        # carry a machine-readable N/A reason (never a fabricated seat or output).
        om.finalize_manifest(
            manifest,
            status="failed",
            seats=list(observed_seats or []),
            outputs=[],
            seats_not_applicable_reason="start_failed_before_seat_observation",
            outputs_not_applicable_reason="start_failed_before_success_output",
        )
        try:
            partial_manifest = om.write_partial(
                run_dir,
                manifest,
                reason=f"{step}: {detail}",
                rc=1,
                executed=receipts,
                unexecuted=unexecuted,
                stdout=str(detail),
            )
        except (OSError, om.ManifestWriteError) as exc:
            # A refused run-manifest.partial write must not erase the original
            # failed-step report; surface the write failure as a sibling field.
            partial_manifest = None
            partial_manifest_error = str(exc)

    return {
        "schemaVersion": SCHEMA,
        "mode": "start",
        "dryRun": False,
        "runDir": str(run_dir),
        "runId": bridge["runId"],
        "rigName": bridge["rigName"],
        "ok": False,
        "error": {"code": failure_code, "message": str(detail)},
        "failedStep": step,
        "detail": detail,
        "executed": executed,
        "rollback": rollback,
        "rollbackMode": rollback_mode,
        "rollbackActions": actions,
        "entryClosed": closed,
        "partialEvidence": partial_path,
        "partialError": partial_error,
        "partialManifest": (partial_manifest or {}).get("path"),
        "partialManifestError": partial_manifest_error,
        "unexecutedSteps": unexecuted,
        "rc": 1,
        "capturedAt": _now(),
    }


# ------------------------------------------------------------------ next
NEXT_MODE_HINTS = (
    "local-only：单机 tmux 座位 + 本机 daemon，probe/check/next 全部离线；不需要跨主机。" "先按本清单前两行走，通过再执行第三行。",
    "hybrid：需要跨主机 / 远端座位时才用同一 bridge 的 daemon+seat；两种模式都由 `openrig-run check` 判定，本命令只打印不阻断。",
)


def build_next_plan(run_dir: Path, bridge: dict) -> list[dict]:
    """Canonical paved road for one run — printed only, never executed."""
    rd = str(run_dir)
    run_id = str(bridge["runId"])
    roadmap = (
        ("check", f"openrig-run check --run-dir {rd}"),
        ("start-dry-run", f"openrig-run start --run-dir {rd} --dry-run"),
        ("start", f"openrig-run start --run-dir {rd}"),
        ("verify-render", f"verify_render.py --run-dir {rd} --strict"),
        ("archive-gate", f"wf.py archive-gate {run_id}"),
    )
    return [
        {"order": index, "id": step_id, "command": command}
        for index, (step_id, command) in enumerate(roadmap, start=1)
    ]


def run_next(run_dir: Path) -> dict:
    """Read-only paved-road printer (R14). No daemon, no rig, no subprocess, no writes."""
    bridge, err = _load_bridge(run_dir)
    if bridge is None:
        return {
            "schemaVersion": SCHEMA,
            "mode": "next",
            "runDir": str(run_dir),
            "ok": False,
            "steps": [],
            "modeHints": list(NEXT_MODE_HINTS),
            "note": "bridge missing or invalid; nothing printed to execute",
            "error": err,
            "rc": 2,
            "capturedAt": _now(),
        }
    return {
        "schemaVersion": SCHEMA,
        "mode": "next",
        "runDir": str(run_dir),
        "runId": bridge["runId"],
        "rigName": bridge["rigName"],
        "ok": True,
        "steps": build_next_plan(run_dir, bridge),
        "modeHints": list(NEXT_MODE_HINTS),
        "note": "printed only: this command executes nothing and writes nothing",
        "rc": 0,
        "capturedAt": _now(),
    }


# ------------------------------------------------------------------ gate wiring
def _observed_state(run_dir: Path, *, live: bool, timeout: int) -> dict | None:
    from openrig_continuity import load_bundle, load_observed_state

    bridge, err = load_bundle(run_dir)
    if bridge is None:
        return None
    state, _ = load_observed_state(run_dir, bridge, live=live, timeout=timeout)
    return state


def _gate_preflight_stop(run_dir: Path, *, live: bool, timeout: int) -> dict | None:
    """Refuse a stop that must not happen. Returns a report, or None to proceed."""
    archive = og.archive_status(run_dir)
    state = _observed_state(run_dir, live=live, timeout=timeout)
    retire = og.retire_gate(state, archive)
    if retire["ok"]:
        return None
    return {
        "schemaVersion": SCHEMA,
        "mode": "stop",
        "runDir": str(run_dir),
        "ok": False,
        "error": {"code": retire["code"], "message": retire["reason"]},
        "archive": archive,
        "retire": retire,
        "mutations": [],
        "rc": 2,
        "capturedAt": _now(),
    }


def _annotate_gates(report: dict, run_dir: Path) -> dict:
    """Add the boundary verdicts to a status report WITHOUT weakening its own refusal.

    Continuity's decision wins: if that already refused, this only adds information.
    """
    archive = og.archive_status(run_dir)
    state = _observed_state(run_dir, live=False, timeout=0)
    compaction = og.compaction_report(state)
    handover = og.validate_handover((state or {}).get("handover"))
    report["gates"] = {
        "archive": archive,
        "compaction": compaction,
        "handover": handover,
        "retire": og.retire_gate(state, archive),
    }
    if report.get("ok"):
        for key in ("compaction", "handover"):
            gate = report["gates"][key]
            if not gate["ok"]:
                report["ok"] = False
                report["error"] = {
                    "code": gate["code"],
                    "message": gate.get("reason") or f"{key} gate refused: {gate.get('missing')}",
                    "hint": (
                        "only a Claude Code seat may claim OpenRig-managed compaction"
                        if key == "compaction"
                        else "handover needs source/reason/previous/successor/actualHandoverResult"
                    ),
                }
                report["rc"] = 2
                break
    return report


# ------------------------------------------------------------------ cli
def _print_continuity(report: dict) -> None:
    """Human view: one line per seat, one line per refusal with its remediation."""
    mode = report.get("mode")
    plan = report.get("continuity") or {}
    print(f"mode={mode} decision={plan.get('decisionStatus')} ok={report.get('ok')} rc={report.get('rc')}")
    for seat in plan.get("seats") or []:
        print(
            f"  {seat['logicalId']}: expected={seat['expectedAction']}"
            f" actual={seat.get('actualOutcome')}"
            f" session={seat['session']} activity={seat['activity']} evidence={seat['evidence']}"
        )
    for row in plan.get("mismatchedSeats") or []:
        print(f"  MISMATCH {row['logicalId']}: {row['reason']}")
        print(f"    fix: {row['remediation']}")
    for row in plan.get("blockedSeats") or []:
        print(f"  BLOCKED {row['logicalId'] or 'fresh-list'}: {row['reason']}")
        print(f"    fix: {row['remediation']}")
    err = report.get("error")
    if err:
        print(f"  error {err['code']}: {err['message']}")
    for item in report.get("mutations") or []:
        print(f"  ran {item['step']}: rc={item['rc']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ordered fail-closed openrig run wrapper")
    sub = ap.add_subparsers(dest="command", required=True)

    c = sub.add_parser("check", help="static + live precondition checks, ordered")
    c.add_argument("--run-dir", required=True)
    c.add_argument("--json", action="store_true")
    c.add_argument("--allow-daemon-down", action="store_true")
    c.add_argument("--strict-render", action="store_true")
    c.add_argument("--timeout", type=int, default=120)

    s = sub.add_parser("start", help="bring the rig up and instantiate the workflow")
    s.add_argument("--run-dir", required=True)
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--timeout", type=int, default=120)
    s.add_argument("--json", action="store_true")
    s.add_argument(
        "--rollback",
        choices=("auto", "manual"),
        default="auto",
        help="on failure: auto stops a daemon this launch started when the rig never registered; "
        "manual only prints the hint (pre-S8 behaviour). Never deletes OPENRIG_HOME or the DB.",
    )

    n = sub.add_parser("next", help="print the canonical paved road (read-only, executes nothing)")
    n.add_argument("--run-dir", required=True)
    n.add_argument("--json", action="store_true")

    # S9 Wave B — the supervisor lifecycle verbs. `start` is NEW-only by contract
    # (CONTINUITY-AND-COMPACTION §4.1); `--resume` exists solely to be refused loudly
    # instead of being silently accepted by the parser as a typo.
    s.add_argument(
        "--resume",
        action="store_true",
        help="NOT a start option: start creates, resume restores. Using it is refused (rc 2).",
    )

    r = sub.add_parser("resume", help="restore a stopped run from its CONTINUITY-PLAN")
    r.add_argument("--run-dir", required=True)
    r.add_argument("--fresh", nargs="+", default=[], metavar="LOGICAL_ID",
                   help="explicitly authorize a fresh seat (requires --reason)")
    r.add_argument("--reason", default="", help="why the original session is unrecoverable")
    r.add_argument("--json", action="store_true")
    r.add_argument("--live", action="store_true", help="read seat state from `ps --nodes`")
    r.add_argument("--dry-run", action="store_true", help="build + write the plan, mutate nothing")
    r.add_argument("--timeout", type=int, default=120)

    st = sub.add_parser("status", help="read-only continuity status (writes nothing)")
    st.add_argument("--run-dir", required=True)
    st.add_argument("--json", action="store_true")
    st.add_argument("--live", action="store_true")
    st.add_argument("--timeout", type=int, default=120)

    sp = sub.add_parser("stop", help="archive-gated teardown of this run")
    sp.add_argument("--run-dir", required=True)
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--live", action="store_true")
    sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("--timeout", type=int, default=120)

    # Draft lite mode: a separate single-seat product form. The full entry guard
    # will eventually make this a first-class subcommand with the same provenance.
    lite = sub.add_parser("lite", help="draft one-seat / one-task lite mode")
    lite.add_argument("lite_args", nargs=argparse.REMAINDER)

    args = ap.parse_args(argv)
    if args.command == "lite":
        from openrig_lite import main as lite_main
        return lite_main(args.lite_args)

    # §4.1: `start` creates, `resume` restores. Refuse the conflation by name BEFORE any
    # path or state work, so `start --resume` can never look like a resume that ran.
    if args.command == "start" and getattr(args, "resume", False):
        payload = {
            "schemaVersion": SCHEMA,
            "mode": "start",
            "runDir": str(Path(args.run_dir).expanduser()),
            "ok": False,
            "error": {
                "code": "invalid_arguments",
                "message": (
                    "`start --resume` does not exist: start creates a new run/rig, "
                    "resume restores a stopped one"
                ),
                "hint": f"openrig-run resume --run-dir {args.run_dir} --json",
            },
            "rc": 2,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json
              else f"[REFUSED] start --resume: use `openrig-run resume --run-dir {args.run_dir}`")
        return 2

    raw_run_dir = Path(args.run_dir).expanduser()
    run_dir = resolve_fixture_run_dir(raw_run_dir)
    if not run_dir.is_dir():
        payload = {
            "schemaVersion": SCHEMA,
            "mode": args.command,
            "runDir": str(run_dir),
            "ok": False,
            "error": "run dir missing",
            "rc": 2,
        }
        if FIXTURE_RUN_RE.match(raw_run_dir.name):
            root = fixture_root()
            where = str(root) if root else f"${FIXTURE_ROOT_ENV} (unset)"
            payload["hint"] = (
                f"fixture run dir not found; export {FIXTURE_ROOT_ENV}=<per-verification dir>, "
                f"then provision it with: npx tsx "
                f"packages/daemon/test/s9-drivers/provision-fixtures.ts "
                f"(S9 entry fixtures) or python workflow-group/tests/fixtures/s9/provision_continuity.py "
                f"(S9 continuity fixtures) — looked under {where}"
            )
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else f"[FAIL] run dir missing: {run_dir}")
        return 2

    if args.command == "check":
        report = run_check(
            run_dir,
            allow_daemon_down=args.allow_daemon_down,
            strict_render=args.strict_render,
            timeout=args.timeout,
        )
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            for chk in report["checks"]:
                print(f"[{chk['status'].upper():4}] {chk['id']}: {chk['detail']}")
            for nxt in report["next"]:
                print(f"next: {nxt}")
            print(f"RESULT {'PASS' if report['ok'] else 'FAIL'} rc={report['rc']}")
        return report["rc"]

    if args.command == "next":
        report = run_next(run_dir)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            if not report["ok"]:
                print(f"[FAIL] {report.get('error')}")
            for step in report["steps"]:
                print(f"{step['order']}. {step['command']}")
            for hint in report["modeHints"]:
                print(f"hint: {hint}")
            print(f"note: {report['note']}")
            print(f"rc={report['rc']}")
        return report["rc"]

    if args.command in ("resume", "status", "stop"):
        from openrig_continuity import run_resume, run_status, run_stop

        if args.command == "resume":
            report = run_resume(
                run_dir,
                fresh=tuple(args.fresh or ()),
                reason=args.reason,
                live=args.live,
                timeout=args.timeout,
                dry_run=args.dry_run,
            )
        elif args.command == "status":
            report = run_status(run_dir, live=args.live, timeout=args.timeout)
            report = _annotate_gates(report, run_dir)
        else:
            # Boundary gates run BEFORE the teardown (§4.3/§5.3): retire is even less
            # reversible than stop, so it is refused before a single rig call.
            blocked = _gate_preflight_stop(run_dir, live=args.live, timeout=args.timeout)
            if blocked is not None:
                report = blocked
            else:
                report = run_stop(
                    run_dir, live=args.live, timeout=args.timeout, dry_run=args.dry_run
                )
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            _print_continuity(report)
        return report["rc"]

    report = run_start(
        run_dir, dry_run=args.dry_run, timeout=args.timeout, rollback_mode=args.rollback
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"mode=start dryRun={report.get('dryRun')} ok={report.get('ok')}")
        for item in report.get("plan") or []:
            print(f"  {item['step']}: {' '.join(item['cmd'])}")
        for item in report.get("executed") or []:
            print(f"  ran {item['step']}: rc={item['rc']}")
        if report.get("failedStep"):
            print(f"FAILED at {report['failedStep']}: {report.get('detail')}")
            print(report.get("rollback"))
        print(f"rc={report.get('rc')}")
    return report.get("rc", 0)


if __name__ == "__main__":
    sys.exit(main())
