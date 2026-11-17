#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""openrig_lite.py — draft OpenRig lite mode (single seat, single task).

This is a *draft* product form, not the full workflow master:
  * one isolated rig
  * one member / one writer
  * one TASK.md
  * no workflow, no queue, no PMO/QA handoff
  * a small launch ledger and status/stop commands

Usage:
  openrig_lite.py init --run-dir <dir> --cwd <project> --task-file <file>
                       [--runtime opencode|dsh] [--model ...] [--port 47992]
                       [--openrig-cli rig] [--openrig-home ...] [--json]
  openrig_lite.py start --run-dir <dir> [--dry-run] [--timeout 120] [--json]
  openrig_lite.py status --run-dir <dir> [--json]
  openrig_lite.py stop --run-dir <dir> [--json] [--keep-home]

Draft boundaries:
  * runtime binaries resolve from --opencode-bin/--dsh-bin, then
    OPENRIG_OPENCODE_BIN/OPENRIG_DSH_BIN, then PATH; init fails rc2 if unresolved;
  * daemon/seat lifecycle is still executed by the existing `rig` CLI;
  * this module deliberately does not implement the full entry guard yet;
  * `stop` does not delete OPENRIG_HOME; archive remains an explicit next step.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 1
DEFAULT_PORT = 47992
DEFAULT_AGENT_TEMPLATE = (
    ROOT / "templates" / "specialized" / "openrig-workflow-master" / "templates" / "agent.yaml.tpl"
)
BRIDGE_REL = Path("openrig") / "OPENRIG-BRIDGE.json"
RIG_REL = Path("openrig") / "rig.yaml"
TASK_REL = Path("TASK.md")
LAUNCH_REL = Path("reports") / "evidence" / "launch.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _atomic_write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    if isinstance(data, bytes):
        tmp.write_bytes(data)
    else:
        tmp.write_text(data, encoding="utf-8")
    os.replace(tmp, path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _slug(value: str) -> str:
    out = re.sub(r"[^a-z0-9._-]+", "-", value.lower()).strip("-")
    return out or "lite"


def _load_bridge(run_dir: Path) -> tuple[dict | None, str | None]:
    p = run_dir / BRIDGE_REL
    if not p.is_file():
        return None, f"bridge missing: {p}"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return None, f"bridge is not valid JSON: {exc}"
    if not isinstance(data, dict) or data.get("mode") != "lite":
        return None, "bridge is not a lite bridge (mode != lite)"
    if not data.get("rigName") or not isinstance(data.get("seatMap"), dict):
        return None, "bridge missing rigName/seatMap"
    return data, None


def _cli(bridge: dict) -> list[str]:
    return shlex.split(str(bridge.get("openrigCli") or "rig"))


def _env(bridge: dict) -> dict:
    env = dict(os.environ)
    home = bridge.get("openrigHome")
    if home:
        env["OPENRIG_HOME"] = str(home)
    if bridge.get("daemonPort"):
        env["OPENRIG_PORT"] = str(bridge["daemonPort"])
    env["OPENRIG_ENTRY_MODE"] = "openrig-lite"
    env["OPENRIG_ENTRY_RUN_ID"] = str(bridge.get("runId") or "")
    return env


def _run(cmd: list[str], bridge: dict, timeout: int = 120) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, env=_env(bridge))
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


def _seat_rows(payload) -> list[dict]:
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in ("nodes", "rows", "seats"):
            if isinstance(payload.get(key), list):
                return [r for r in payload[key] if isinstance(r, dict)]
    return []


def _resolve_runtime_bin(explicit: str | None, env_name: str, command: str) -> str | None:
    """Resolve a runtime binary without baking in a developer home directory.

    Priority is explicit CLI value > environment variable > PATH lookup.  A value
    supplied by the caller or environment must itself resolve through ``which``;
    returning a missing path would defer a clear init-time error to a later start.
    """
    requested = explicit or os.environ.get(env_name)
    found = shutil.which(requested) if requested else shutil.which(command)
    return str(Path(found).resolve()) if found else None


def _default_agent_yaml() -> str:
    if DEFAULT_AGENT_TEMPLATE.is_file():
        return DEFAULT_AGENT_TEMPLATE.read_text(encoding="utf-8")
    return """name: openrig-lite-worker
version: "1.0.0"
description: Single worker for OpenRig lite.
resources:
  skills: []
profiles:
  default:
    uses:
      skills: []
startup:
  files: []
  actions: []
"""


def _rig_yaml(*, rig_name: str, cwd: str, runtime: str, model: str | None) -> str:
    rows = [
        "version: '0.2'",
        f"name: {json.dumps(rig_name, ensure_ascii=False)}",
        "summary: 'OpenRig lite: one seat, one task, one writer.'",
        "pods:",
        "- id: solo",
        "  label: Solo",
        "  members:",
        "  - id: worker",
        "    agent_ref: local:./agents/worker",
        "    profile: default",
        f"    runtime: {runtime}",
        "    role: tdo",
        f"    cwd: {json.dumps(cwd, ensure_ascii=False)}",
    ]
    if runtime == "opencode" and model:
        rows.append(f"    model: {json.dumps(model, ensure_ascii=False)}")
    rows += [
        "  edges: []",
        "edges: []",
        "startup:",
        "  files: []",
    ]
    return "\n".join(rows) + "\n"


def cmd_init(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    task_file = Path(args.task_file).expanduser().resolve()
    cwd = Path(args.cwd).expanduser().resolve()
    if not task_file.is_file():
        print(f"[ERROR] task file missing: {task_file}", file=sys.stderr)
        return 2
    if not cwd.is_dir():
        print(f"[ERROR] cwd is not a directory: {cwd}", file=sys.stderr)
        return 2
    if run_dir.exists() and any(run_dir.iterdir()) and not args.force:
        print(f"[ERROR] run dir is not empty: {run_dir} (use --force)", file=sys.stderr)
        return 2

    run_id = _slug(run_dir.name)
    rig_name = f"openrig-lite-{run_id}"
    home = Path(args.openrig_home).expanduser().resolve() if args.openrig_home else Path(f"/tmp/{rig_name}")
    runtime = args.runtime
    model = args.model if runtime == "opencode" else None
    if runtime == "opencode" and not model:
        model = "deepseek/deepseek-flash"

    if runtime == "opencode":
        runtime_bin = _resolve_runtime_bin(args.opencode_bin, "OPENRIG_OPENCODE_BIN", "opencode")
        bin_flag = "--opencode-bin"
        bin_env = "OPENRIG_OPENCODE_BIN"
    else:
        runtime_bin = _resolve_runtime_bin(args.dsh_bin, "OPENRIG_DSH_BIN", "dsh")
        bin_flag = "--dsh-bin"
        bin_env = "OPENRIG_DSH_BIN"
    if runtime_bin is None:
        print(
            f"[ERROR] {runtime} binary not found; pass {bin_flag} or set {bin_env}",
            file=sys.stderr,
        )
        return 2

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "openrig" / "agents" / "worker").mkdir(parents=True, exist_ok=True)
    (run_dir / "reports" / "evidence").mkdir(parents=True, exist_ok=True)
    _atomic_write(run_dir / TASK_REL, task_file.read_text(encoding="utf-8"))
    _atomic_write(run_dir / RIG_REL, _rig_yaml(rig_name=rig_name, cwd=str(cwd), runtime=runtime, model=model))
    _atomic_write(run_dir / "openrig" / "agents" / "worker" / "agent.yaml", _default_agent_yaml())

    bridge = {
        "schemaVersion": 2,
        "mode": "lite",
        "runId": run_id,
        "projectRoot": str(cwd),
        "bundleDir": ".",
        "rigName": rig_name,
        "openrigCli": args.openrig_cli,
        "openrigHome": str(home),
        "daemonPort": int(args.port),
        "seatMap": {"worker": f"worker@{rig_name}"},
        "runtimeEnv": ({
            "OPENRIG_OPENCODE_BIN": runtime_bin,
            "OPENRIG_OPENCODE_MODEL": model,
        } if runtime == "opencode" else {"OPENRIG_DSH_BIN": runtime_bin, "OPENRIG_DSH_PROFILE": "headless"}),
        "lite": {
            "contract": "single-seat / single-task / single-writer / no workflow queue",
            "runtime": runtime,
            "model": model,
            "taskPath": "TASK.md",
        },
    }
    _atomic_write(run_dir / BRIDGE_REL, json.dumps(bridge, ensure_ascii=False, indent=2) + "\n")
    _atomic_write(run_dir / "LITE.md", (
        "# OpenRig lite draft\n\n"
        "- one seat: `worker`\n- one task: `TASK.md`\n- one writer\n"
        "- no workflow / queue / PMO / QA handoff\n"
        "- `start` launches the rig and sends TASK.md to the worker\n"
        "- `status` shows seat readiness and last runner state\n"
        "- `stop` stops the rig; archive is an explicit follow-up\n"
    ))
    payload = {
        "schemaVersion": SCHEMA,
        "mode": "lite-init",
        "ok": True,
        "runDir": str(run_dir),
        "runId": run_id,
        "rigName": rig_name,
        "openrigHome": str(home),
        "daemonPort": int(args.port),
        "runtime": runtime,
        "model": model,
        "taskSha256": _sha256(run_dir / TASK_REL),
        "bridgePath": str(run_dir / BRIDGE_REL),
        "rc": 0,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else f"lite initialized: {run_dir}")
    return 0


def build_start_plan(run_dir: Path, bridge: dict) -> list[dict]:
    cli = _cli(bridge)
    rig_path = run_dir / RIG_REL
    session = next(iter(bridge["seatMap"].values()))
    task = (run_dir / TASK_REL).read_text(encoding="utf-8")
    return [
        {"step": "daemon-start", "cmd": [*cli, "daemon", "start", "--no-kernel", "--port", str(bridge["daemonPort"])]},
        {"step": "up", "cmd": [*cli, "up", str(rig_path), "--cwd", str(bridge["projectRoot"]), "--yes", "--json"]},
        {"step": "wait-ready", "cmd": [*cli, "ps", "--nodes", "--rig", str(bridge["rigName"]), "--json"], "poll": True},
        {"step": "send-task", "cmd": [*cli, "send", str(session), task, "--json"]},
    ]


def _poll_ready(bridge: dict, timeout: int) -> tuple[bool, str]:
    deadline = time.time() + max(timeout, 0)
    target = next(iter(bridge["seatMap"].values()))
    last = "no attempt"
    while True:
        proc = _run([*_cli(bridge), "ps", "--nodes", "--rig", str(bridge["rigName"]), "--json"], bridge, 60)
        rows = _seat_rows(_json_or_none(proc.stdout) or [])
        row = next((r for r in rows if r.get("canonicalSessionName") == target), None)
        if row is not None and str(row.get("startupStatus")) == "ready" and str(row.get("sessionStatus")) == "running":
            return True, f"{target} ready"
        last = "absent" if row is None else f"startup={row.get('startupStatus')} session={row.get('sessionStatus')}"
        if time.time() >= deadline:
            return False, f"timeout after {timeout}s: {last}"
        time.sleep(2)


def _write_launch(run_dir: Path, bridge: dict, launch_id: str, status: str, **extra) -> Path:
    path = run_dir / LAUNCH_REL
    old = _json_or_none(path.read_text(encoding="utf-8")) if path.is_file() else {}
    payload = {
        **old,
        "schemaVersion": SCHEMA,
        "mode": "lite",
        "launchId": launch_id,
        "runId": bridge["runId"],
        "rigName": bridge["rigName"],
        "session": next(iter(bridge["seatMap"].values())),
        "status": status,
        "updatedAt": _now(),
        **extra,
    }
    _atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def cmd_start(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    bridge, err = _load_bridge(run_dir)
    if bridge is None:
        print(json.dumps({"schemaVersion": SCHEMA, "mode": "lite-start", "ok": False, "error": err, "rc": 2}, ensure_ascii=False, indent=2) if args.json else f"[ERROR] {err}", file=sys.stderr if not args.json else sys.stdout)
        return 2
    task_path = run_dir / TASK_REL
    if not task_path.is_file():
        print(f"[ERROR] TASK.md missing: {task_path}", file=sys.stderr)
        return 2
    plan = build_start_plan(run_dir, bridge)
    launch_id = uuid.uuid4().hex[:16]
    if args.dry_run:
        payload = {
            "schemaVersion": SCHEMA, "mode": "lite-start", "dryRun": True, "ok": True,
            "runId": bridge["runId"], "rigName": bridge["rigName"], "plan": plan,
            "executed": [], "note": "dry-run: no daemon/up/send/ps", "rc": 0,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else "\n".join(p["step"] for p in plan))
        return 0

    _write_launch(run_dir, bridge, launch_id, "starting", taskSha256=_sha256(task_path), plan=plan)
    executed: list[dict] = []
    for item in plan:
        if item.get("poll"):
            ok, detail = _poll_ready(bridge, args.timeout)
            executed.append({"step": item["step"], "rc": 0 if ok else 1, "detail": detail})
            if not ok:
                _write_launch(run_dir, bridge, launch_id, "failed", failedStep=item["step"], detail=detail, executed=executed)
                print(json.dumps({"schemaVersion": SCHEMA, "mode": "lite-start", "ok": False, "failedStep": item["step"], "detail": detail, "executed": executed, "rc": 1}, ensure_ascii=False, indent=2) if args.json else f"[FAIL] {detail}")
                return 1
            continue
        proc = _run(item["cmd"], bridge, args.timeout)
        executed.append({"step": item["step"], "rc": proc.returncode, "ok": proc.returncode == 0})
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()[:300] or f"rc={proc.returncode}"
            _write_launch(run_dir, bridge, launch_id, "failed", failedStep=item["step"], detail=detail, executed=executed)
            print(json.dumps({"schemaVersion": SCHEMA, "mode": "lite-start", "ok": False, "failedStep": item["step"], "detail": detail, "executed": executed, "rc": 1}, ensure_ascii=False, indent=2) if args.json else f"[FAIL] {item['step']}: {detail}")
            return 1
    path = _write_launch(run_dir, bridge, launch_id, "running", executed=executed)
    payload = {"schemaVersion": SCHEMA, "mode": "lite-start", "ok": True, "runId": bridge["runId"], "rigName": bridge["rigName"], "session": next(iter(bridge["seatMap"].values())), "launchId": launch_id, "launchPath": str(path), "executed": executed, "rc": 0}
    print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else f"lite started: {payload['session']}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    bridge, err = _load_bridge(run_dir)
    if bridge is None:
        print(json.dumps({"schemaVersion": SCHEMA, "mode": "lite-status", "ok": False, "error": err, "rc": 2}, ensure_ascii=False, indent=2) if args.json else f"[ERROR] {err}")
        return 2
    proc = _run([*_cli(bridge), "ps", "--nodes", "--rig", str(bridge["rigName"]), "--json"], bridge, 60)
    rows = _seat_rows(_json_or_none(proc.stdout) or [])
    target = next(iter(bridge["seatMap"].values()))
    row = next((r for r in rows if r.get("canonicalSessionName") == target), None)
    state_path = Path(str(bridge["openrigHome"])) / "state" / str(bridge.get("lite", {}).get("runtime") or "opencode") / target / "runner-state.json"
    state = _json_or_none(state_path.read_text(encoding="utf-8")) if state_path.is_file() else None
    payload = {
        "schemaVersion": SCHEMA, "mode": "lite-status",
        "runId": bridge["runId"], "rigName": bridge["rigName"], "session": target,
        "daemonRc": proc.returncode, "seat": row,
        "runnerStatePath": str(state_path), "runnerState": state,
        "ok": row is not None and proc.returncode == 0,
        "rc": 0 if row is not None and proc.returncode == 0 else 1,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else f"{target}: {row or 'absent'}")
    return payload["rc"]


def cmd_stop(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    bridge, err = _load_bridge(run_dir)
    if bridge is None:
        print(json.dumps({"schemaVersion": SCHEMA, "mode": "lite-stop", "ok": False, "error": err, "rc": 2}, ensure_ascii=False, indent=2) if args.json else f"[ERROR] {err}")
        return 2
    cli = _cli(bridge)
    executed = []
    for step, cmd in (
        ("down", [*cli, "down", str(bridge["rigName"]), "--json"]),
        ("daemon-stop", [*cli, "daemon", "stop"]),
    ):
        proc = _run(cmd, bridge, 60)
        executed.append({"step": step, "rc": proc.returncode, "ok": proc.returncode == 0})
    payload = {
        "schemaVersion": SCHEMA, "mode": "lite-stop", "ok": all(e["rc"] == 0 for e in executed),
        "runId": bridge["runId"], "rigName": bridge["rigName"], "executed": executed,
        "home": bridge["openrigHome"], "homeKept": bool(args.keep_home),
        "note": "archive is an explicit follow-up; this draft never deletes OPENRIG_HOME",
        "rc": 0 if all(e["rc"] == 0 for e in executed) else 1,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else f"lite stopped: {bridge['rigName']}")
    return payload["rc"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="OpenRig lite draft: one seat, one task")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--cwd", required=True)
    p.add_argument("--task-file", required=True)
    p.add_argument("--runtime", choices=("opencode", "dsh"), default="opencode")
    p.add_argument("--model", default="deepseek/deepseek-flash")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--openrig-cli", default="rig")
    p.add_argument("--openrig-home", default="")
    p.add_argument("--opencode-bin", default=None)
    p.add_argument("--dsh-bin", default=None)
    p.add_argument("--force", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("start")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_start)

    p = sub.add_parser("status")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("stop")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--keep-home", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_stop)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
