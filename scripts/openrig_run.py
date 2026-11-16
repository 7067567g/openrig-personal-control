#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""openrig_run.py — ordered, fail-closed wrapper around `rig` for one workflow run (R11).

Usage:
  openrig_run.py check --run-dir <run-dir> [--json] [--allow-daemon-down] [--strict-render]
  openrig_run.py start --run-dir <run-dir> [--dry-run] [--timeout 120] [--json]
  openrig_run.py next  --run-dir <run-dir> [--json]        (R14: read-only paved road)

`check` runs, in order, and stops classifying as PASS on the first blocked step:

  1. read `openrig/OPENRIG-BRIDGE.json`                      missing/bad  -> rc 2
  2. `verify_render.py --run-dir ...`                         mismatch     -> WARN, blocks only with --strict-render
                                                              manifest rc2 -> blocks
  3. `tools/openrig_bridge.py doctor --run-dir ...`            rc != 0      -> blocks
  4. `<openrigCli> workflow validate <workflowSpec> --json`    rc != 0      -> blocks
  5. `<openrigCli> ps --nodes --rig <rigName> --json`          daemon down  -> blocks (or WARN with --allow-daemon-down)
                                                              a seat not ready -> blocks

Output `{ok, checks[], next[]}`; `ok:false` -> rc 1. rc 0 only when every blocking check passed.
Nothing here replaces `workflow instantiate` idempotency: a repeated `start` is still the rig's
own error to raise.

`start`:
  * dry-run prints the exact ordered commands and executes **no** live action (no daemon, no
    `up`, no `workflow validate`, no `workflow instantiate`, no `ps`);
  * otherwise: `check --allow-daemon-down`, then `daemon start --no-kernel --port`,
    `up <rigSpec>`, poll `ps` until every seatMap target is ready (bounded by --timeout),
    `workflow validate`, `workflow instantiate`;
  * the first failure stops the chain and returns a rollback hint. It never deletes
    OPENRIG_HOME or the daemon DB by itself.

Dependency-free: standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOCTOR = (
    ROOT / "templates" / "specialized" / "openrig-workflow-master" / "tools" / "openrig_bridge.py"
)
BRIDGE_REL = Path("openrig") / "OPENRIG-BRIDGE.json"
SCHEMA = 1
REQUIRED_BRIDGE_KEYS = ("runId", "rigName", "workflowId", "openrigCli", "seatMap")


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
    return env


def _run(cmd: list[str], bridge: dict, timeout: int = 120) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd, text=True, capture_output=True, timeout=timeout, env=_env(bridge)
        )
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(cmd, 127, "", f"command not found: {exc}")
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout if isinstance(exc.stdout, str) else ""
        return subprocess.CompletedProcess(cmd, 124, out, f"timeout after {timeout}s")
    except OSError as exc:
        return subprocess.CompletedProcess(cmd, 126, "", f"could not run: {exc}")


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


# ------------------------------------------------------------------ checks
def run_check(
    run_dir: Path,
    *,
    allow_daemon_down: bool = False,
    strict_render: bool = False,
    live: bool = True,
    timeout: int = 120,
) -> dict:
    """Return the check report. `live=False` skips every call that touches the rig."""
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
    checks.append(
        _check(
            "bridge",
            "ok",
            f"runId={bridge['runId']} rig={bridge['rigName']} seats={len(bridge['seatMap'])}",
        )
    )

    # 2. render manifest
    render_cmd = [sys.executable, str(ROOT / "scripts" / "verify_render.py"), "--run-dir", str(run_dir), "--json"]
    proc = _run(render_cmd, bridge, timeout)
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

    # 3. bundle doctor
    doctor = _doctor_path(run_dir)
    if doctor is None:
        checks.append(_check("doctor", "fail", "tools/openrig_bridge.py not found (run bundle or template)"))
        next_steps.append("restore templates/specialized/openrig-workflow-master/tools/openrig_bridge.py")
    else:
        proc = _run([sys.executable, str(doctor), "doctor", "--run-dir", str(run_dir)], bridge, timeout)
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
        # 4. daemon + seat readiness first: workflow validate may need the daemon
        #    (and its OPENRIG_HOME). Pre-launch checks must still be able to run
        #    with --allow-daemon-down without a live daemon.
        proc = _run([*cli, "ps", "--nodes", "--rig", str(bridge["rigName"]), "--json"], bridge, timeout)
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
            # 5. workflow validate (daemon is up)
            proc = _run([*cli, "workflow", "validate", str(workflow_spec), "--json"], bridge, timeout)
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

            # 6. seat readiness
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


# ------------------------------------------------------------------ start
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
        {"step": "up", "cmd": [*cli, "up", str(rig_spec)]},
        {
            "step": "wait-ready",
            "cmd": [*cli, "ps", "--nodes", "--rig", str(bridge["rigName"]), "--json"],
            "poll": True,
        },
        {"step": "workflow-validate", "cmd": [*cli, "workflow", "validate", str(workflow_spec), "--json"]},
        {"step": "workflow-instantiate", "cmd": [*cli, "workflow", "instantiate", str(workflow_spec), "--json"]},
    ]


def _poll_ready(run_dir: Path, bridge: dict, timeout: int, cli: list[str]) -> tuple[bool, str]:
    deadline = time.time() + max(int(timeout), 0)
    last = "no attempt"
    while True:
        proc = _run([*cli, "ps", "--nodes", "--rig", str(bridge["rigName"]), "--json"], bridge, 60)
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
            return True, "all seats ready"
        last = ", ".join(pending)
        if time.time() >= deadline:
            return False, f"timeout after {timeout}s waiting for {last}"
        time.sleep(2)


def run_start(run_dir: Path, *, dry_run: bool, timeout: int = 120) -> dict:
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
    plan = build_start_plan(run_dir, bridge)

    if dry_run:
        precheck = run_check(run_dir, allow_daemon_down=True, live=False, timeout=timeout)
        ok = precheck["ok"]
        return {
            "schemaVersion": SCHEMA,
            "mode": "start",
            "dryRun": True,
            "runDir": str(run_dir),
            "runId": bridge["runId"],
            "rigName": bridge["rigName"],
            "ok": ok,
            "plan": plan,
            "executed": [],
            "precheck": precheck,
            "note": "dry-run: no daemon start, no up, no workflow validate/instantiate, no ps",
            "rc": 0 if ok else 1,
            "capturedAt": _now(),
        }

    executed: list[dict] = []
    precheck = run_check(run_dir, allow_daemon_down=True, timeout=timeout)
    executed.append({"step": "precheck", "rc": precheck["rc"], "ok": precheck["ok"]})
    if not precheck["ok"]:
        return {
            "schemaVersion": SCHEMA,
            "mode": "start",
            "dryRun": False,
            "runDir": str(run_dir),
            "runId": bridge["runId"],
            "rigName": bridge["rigName"],
            "ok": False,
            "failedStep": "precheck",
            "precheck": precheck,
            "executed": executed,
            "rollback": "nothing was started; fix the failing check and re-run",
            "rc": 1,
            "capturedAt": _now(),
        }

    cli = _cli(bridge)
    for item in plan:
        step = item["step"]
        if item.get("poll"):
            ok, detail = _poll_ready(run_dir, bridge, timeout, cli)
            executed.append({"step": step, "rc": 0 if ok else 1, "detail": detail})
            if not ok:
                return _start_failed(run_dir, bridge, executed, step, detail, timeout)
            continue
        proc = _run(item["cmd"], bridge, timeout)
        exec_item = {"step": step, "rc": proc.returncode, "ok": proc.returncode == 0}
        if proc.returncode != 0:
            exec_item["stderr"] = (proc.stderr or "")[:400]
        executed.append(exec_item)
        if proc.returncode != 0:
            return _start_failed(
                run_dir,
                bridge,
                executed,
                step,
                (proc.stderr or proc.stdout or "").strip()[:300] or f"rc={proc.returncode}",
                timeout,
            )

    return {
        "schemaVersion": SCHEMA,
        "mode": "start",
        "dryRun": False,
        "runDir": str(run_dir),
        "runId": bridge["runId"],
        "rigName": bridge["rigName"],
        "ok": True,
        "executed": executed,
        "rc": 0,
        "capturedAt": _now(),
    }


def _start_failed(run_dir, bridge, executed, step, detail, timeout) -> dict:
    return {
        "schemaVersion": SCHEMA,
        "mode": "start",
        "dryRun": False,
        "runDir": str(run_dir),
        "runId": bridge["runId"],
        "rigName": bridge["rigName"],
        "ok": False,
        "failedStep": step,
        "detail": detail,
        "executed": executed,
        "rollback": (
            f"stopped at '{step}'. Roll back with: "
            f"{' '.join(_cli(bridge))} down {bridge['rigName']}  "
            "(keeps OPENRIG_HOME and the daemon DB; delete nothing automatically)."
            f" Do not re-run instantiate blindly — the rig rejects duplicates itself."
        ),
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


# ------------------------------------------------------------------ cli
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

    n = sub.add_parser("next", help="print the canonical paved road (read-only, executes nothing)")
    n.add_argument("--run-dir", required=True)
    n.add_argument("--json", action="store_true")

    args = ap.parse_args(argv)
    run_dir = Path(args.run_dir).expanduser()
    if not run_dir.is_dir():
        payload = {
            "schemaVersion": SCHEMA,
            "mode": args.command,
            "runDir": str(run_dir),
            "ok": False,
            "error": "run dir missing",
            "rc": 2,
        }
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

    report = run_start(run_dir, dry_run=args.dry_run, timeout=args.timeout)
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
