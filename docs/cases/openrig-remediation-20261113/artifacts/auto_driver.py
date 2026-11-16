#!/usr/bin/env python3
"""月月bot SCTG host driver（remediation R3）。

权威状态：reports/sctg/RUN-STATE.json + reports/sctg/ROUNDS.jsonl
配置：tools/sctg/rounds.yaml (schema 2)
事务层：tools/sctg/kit/sctg.py

安全边界：
- 产品轮由 seat 执行；外部 Android 轮只标 external_pending；人工点停 NEED_MAIN。
- 只有 30/30 产品轮 PASS 且人工点 accepted 才写 DONE。
- 所有状态写入用临时文件 + os.replace / fcntl 锁。
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "tools/sctg/rounds.yaml"
DEFAULT_KIT = Path(os.environ.get("SCTG_KIT", ROOT / "tools/sctg/kit"))
DEFAULT_RUN = ROOT / ".sctg/runs/sctg-app-feel-auto-20261113"
DEFAULT_STATE = ROOT / "reports/sctg/RUN-STATE.json"
DEFAULT_ROUNDS = ROOT / "reports/sctg/ROUNDS.jsonl"
DEFAULT_SEAT = "dsh --profile headless"


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        try:
            dfd = os.open(path.parent, os.O_DIRECTORY)
            os.fsync(dfd)
            os.close(dfd)
        except OSError:
            pass
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_config(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if data.get("schema") != 2:
        raise SystemExit(f"{path}: 需要 rounds schema 2")
    product = data.get("product_rounds") or []
    prep = data.get("prep_rounds") or []
    if len(product) != 30:
        raise SystemExit(f"{path}: product_rounds 必须是 30，当前 {len(product)}")
    if {r.get("id") for r in prep} != {"R05.5", "R09.5", "R15.5"}:
        raise SystemExit(f"{path}: prep_rounds 必须是 R05.5/R09.5/R15.5")
    return data


def load_round_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception as exc:
            raise SystemExit(f"{path}: 非法 JSONL: {exc}") from exc
    return rows


def append_round(path: Path, record: dict[str, Any]) -> bool:
    """锁内追加；同一 round 已有 PASS 时不重复写。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        f.seek(0)
        existing = []
        for line in f.read().splitlines():
            if not line.strip():
                continue
            try:
                existing.append(json.loads(line))
            except Exception:
                pass
        if any(r.get("round") == record.get("round") and r.get("verdict") == "PASS" for r in existing):
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            return False
        f.seek(0, os.SEEK_END)
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return True


def validate_state(state: dict[str, Any], config: dict[str, Any], rows: list[dict[str, Any]]) -> list[str]:
    problems: list[str] = []
    product = config["product_rounds"]
    ids = [r.get("id") for r in product]
    if state.get("product_rounds_total") != 30:
        problems.append("product_rounds_total != 30")
    if len(ids) != 30 or len(set(ids)) != 30:
        problems.append("rounds.yaml product_rounds 不是 30 个唯一 id")
    row_ids = [r.get("round") for r in rows]
    if len(row_ids) != len(set(row_ids)):
        problems.append("ROUNDS.jsonl 有重复 round")
    unknown = sorted(set(row_ids) - set(ids))
    if unknown:
        problems.append(f"ROUNDS.jsonl 未知 round: {unknown}")
    passed = state.get("product_rounds_passed") or []
    if passed != row_ids:
        problems.append("RUN-STATE.product_rounds_passed 与 ROUNDS.jsonl 不一致")
    if state.get("active_round") not in set(ids) | {r.get("id") for r in config["prep_rounds"]}:
        problems.append("RUN-STATE.active_round 不在产品/准备轮")
    return problems


def version_string(cmd: list[str]) -> str:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return (p.stdout or p.stderr).strip().splitlines()[0] if (p.stdout or p.stderr).strip() else "unknown"
    except Exception:
        return "unavailable"


def dry_run(config_path: Path, kit: Path, state_path: Path, rounds_path: Path, seat: list[str]) -> int:
    cfg = load_config(config_path)
    state = load_json(state_path) if state_path.exists() else {}
    rows = load_round_rows(rounds_path)
    missing = []
    if not (kit / "sctg.py").is_file():
        missing.append(f"SCTG kit 不存在: {kit}")
    if not (ROOT / "tools/sctg/check_round.py").is_file():
        missing.append("tools/sctg/check_round.py 不存在")
    if not (ROOT / "tools/sctg/normalize_submission.py").is_file():
        missing.append("tools/sctg/normalize_submission.py 不存在")
    if not state_path.exists():
        missing.append(f"RUN-STATE 不存在: {state_path}")
    if not shutil.which(seat[0]):
        missing.append(f"seat command 不在 PATH: {seat[0]}")
    problems = validate_state(state, cfg, rows) if state else ["RUN-STATE 不存在"]
    print(json.dumps({
        "ok": not missing and not problems,
        "schema": 2,
        "product_rounds": len(cfg["product_rounds"]),
        "prep_rounds": [r["id"] for r in cfg["prep_rounds"]],
        "prep_passed": state.get("prep_rounds_passed", []),
        "passed": state.get("product_rounds_passed", []),
        "active_round": state.get("active_round"),
        "terminal": state.get("terminal"),
        "seat": seat,
        "kit": str(kit),
        "missing": missing,
        "problems": problems,
        "tools": {
            "python": version_string([sys.executable, "--version"]),
            "node": version_string(["node", "--version"]),
            "dsh": version_string(["dsh", "--version"]),
        },
        "note": "dry-run 只校验配置/状态/工具；不调用 seat，不写任何状态。",
    }, ensure_ascii=False, indent=2))
    return 0 if not missing and not problems else 1


def sctg(kit: Path, *args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(kit / "sctg.py"), *args], cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)


def write_task(run_dir: Path, row: dict[str, Any]) -> Path:
    task = {
        "id": row["id"],
        "title": f'{row["title"]}\n\n{row["details"]}',
        "seat": "lead",
        "max_attempts": int(row.get("max_attempts", 2)),
        "inputs": row.get("inputs", []),
        "write_scope": row.get("write_scope", []),
        "deliverable": {
            "schema": "sctg/schemas/submission.schema.json",
            "required": ["task_id", "card_hash", "summary", "findings", "changed_files", "produced_files", "commands", "test_command", "test_expect_exit", "evidence_paths", "status"],
        },
        "gates": row.get("gates", ["g0_schema", "g1_scope", "g2_evidence", "g3_command"]),
    }
    p = run_dir / "sctg/tasks" / f'{row["id"]}.yaml'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(task, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return p


def ensure_run(run_dir: Path, kit: Path, run_id: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    if not (run_dir / "sctg/gates/g0_schema.py").is_file():
        r = sctg(kit, "init", str(run_dir), "--with-kit")
        if r.returncode != 0:
            raise SystemExit(f"init failed: {r.stdout}{r.stderr}")
    pattern = run_dir / "sctg/pattern.yaml"
    if not pattern.is_file():
        pattern.write_text(f"run_id: {run_id}\nmode: lite\n", encoding="utf-8")


def run_seat(seat: list[str], prompt: str, timeout: int) -> tuple[int, str]:
    """运行 seat；超时杀整个进程组，不把超时当 PASS。"""
    try:
        p = subprocess.Popen(
            [*seat, prompt],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
    except FileNotFoundError as exc:
        return 127, str(exc)
    try:
        out, _ = p.communicate(timeout=timeout)
        return p.returncode, out or ""
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            time.sleep(2)
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        out, _ = p.communicate()
        return 124, (out or "") + "\nTIMEOUT"


def wait_submission(path: Path, timeout: int) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return True
        time.sleep(2)
    return False


def update_state(state_path: Path, state: dict[str, Any], **changes: Any) -> None:
    state.update(changes)
    state["updated_at"] = now()
    atomic_write_json(state_path, state)


def mark_blocked(run_dir: Path, state_path: Path, state: dict[str, Any], rid: str, reason: str, kind: str = "BLOCKED") -> None:
    atomic_write(run_dir / kind, f"{rid}: {reason}\n")
    state.setdefault("blocked_rounds", [])
    if rid not in state["blocked_rounds"]:
        state["blocked_rounds"].append(rid)
    update_state(state_path, state, active_round=rid, terminal=False, last_error=reason)


def execute_round(run_dir: Path, kit: Path, row: dict[str, Any], seat: list[str], timeout: int) -> tuple[bool, str]:
    rid = row["id"]
    if row.get("runs_via") == "external":
        return True, "external_pending"
    if row.get("manual_checkpoint"):
        return False, "NEED_MAIN"
    if row.get("host_only"):
        r = subprocess.run(row["check_cmd"], shell=True, cwd=str(ROOT), capture_output=True, text=True, timeout=300)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    if not row.get("ready"):
        return False, "BLOCKED"
    write_task(run_dir, row)
    for attempt in (1, 2):
        for cmd in (("render", str(run_dir), rid, "--attempt", str(attempt)),
                    ("start", str(run_dir), rid, str(attempt)),
                    ("dispatch", str(run_dir), rid, str(attempt), "--driver-id", "sctg-auto")):
            r = sctg(kit, *cmd)
            print(f"{rid} {cmd[0]} rc={r.returncode} {(r.stdout + r.stderr).strip()[:200]}")
            if r.returncode != 0:
                return False, "SCTG_FAILED"
        card = run_dir / "sctg/channels/lead" / f"{rid}.md"
        prompt = f'''你是 SCTG 执行体。只读 Task Card `{card}`，严格按卡中的 write_scope/交付格式/gates 执行。
完成后只把 submission 写到卡指定路径并停止；不要进入下一轮，不要改卡外文件。
test_command 必须是：{row["check_cmd"]}
如果无法完成，status 写 BLOCKED 并说明原因。'''
        rc, out = run_seat(seat, prompt, timeout)
        print(f"{rid} seat rc={rc} {out.strip()[:300]}")
        sub = run_dir / f"sctg/submissions/{rid}/attempt-{attempt}.json"
        if not wait_submission(sub, timeout):
            print(f"TIMEOUT {rid} attempt {attempt}")
            continue
        norm = subprocess.run([sys.executable, str(ROOT / "tools/sctg/normalize_submission.py"), str(run_dir), rid, str(attempt)], cwd=str(ROOT), capture_output=True, text=True, timeout=60)
        print(f"{rid} normalize rc={norm.returncode} {(norm.stdout + norm.stderr).strip()[:200]}")
        if norm.returncode != 0:
            continue
        r = sctg(kit, "collect", str(run_dir), rid, str(attempt), "--timeout", "30", "--driver-id", "sctg-auto")
        print(f"{rid} collect rc={r.returncode} {(r.stdout + r.stderr).strip()[:200]}")
        r = sctg(kit, "gate", str(run_dir), rid, str(attempt))
        print(f"{rid} gate rc={r.returncode} {(r.stdout + r.stderr).strip()[:400]}")
        if r.returncode != 0:
            continue
        r = subprocess.run(row["check_cmd"], shell=True, cwd=str(ROOT), capture_output=True, text=True, timeout=300)
        print(f"{rid} check rc={r.returncode} {(r.stdout + r.stderr).strip()[:400]}")
        if r.returncode == 3:
            return False, "NEED_MAIN"
        return r.returncode == 0, "PASS" if r.returncode == 0 else "CHECK_FAILED"
    return False, "BLOCKED"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--kit", type=Path, default=DEFAULT_KIT)
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    ap.add_argument("--state", type=Path, default=DEFAULT_STATE)
    ap.add_argument("--rounds-file", type=Path, default=DEFAULT_ROUNDS)
    ap.add_argument("--seat-command", default=os.environ.get("SCTG_SEAT_COMMAND", DEFAULT_SEAT))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--round", dest="round_id")
    ap.add_argument("--rounds", dest="round_ids")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--continue-past-need-main", action="store_true")
    ap.add_argument("--retry-blocked", action="store_true")
    a = ap.parse_args()
    seat = a.seat_command.split()
    if a.dry_run:
        return dry_run(a.config, a.kit, a.state, a.rounds_file, seat)

    cfg = load_config(a.config)
    state = load_json(a.state)
    rows = load_round_rows(a.rounds_file)
    problems = validate_state(state, cfg, rows)
    if problems:
        raise SystemExit("状态不一致，拒绝执行：\n" + "\n".join(problems))
    all_rows = cfg["product_rounds"] + cfg["prep_rounds"]
    if a.round_ids:
        wanted = [x.strip() for x in a.round_ids.split(",") if x.strip()]
        selected = [r for r in all_rows if r["id"] in wanted]
        if len(selected) != len(wanted):
            raise SystemExit(f"unknown round in: {a.round_ids}")
    elif a.round_id:
        selected = [r for r in all_rows if r["id"] == a.round_id]
        if not selected:
            raise SystemExit(f"unknown round: {a.round_id}")
    elif a.all:
        selected = list(cfg["product_rounds"])
    else:
        raise SystemExit("需要 --round / --rounds / --all（或 --dry-run）")

    ensure_run(a.run_dir, a.kit, cfg.get("run_id", a.run_dir.name))
    update_state(a.state, state, seat_command=a.seat_command,
                 tool_versions={"python": version_string([sys.executable, "--version"]),
                                "node": version_string(["node", "--version"]),
                                "dsh": version_string(["dsh", "--version"])},
                 last_started_at=now())
    completed = {r.get("round") for r in rows if r.get("verdict") == "PASS"}
    blocked = set(state.get("blocked_rounds") or [])
    stop = False
    for row in selected:
        rid = row["id"]
        if rid in completed:
            print(f"SKIP {rid} (already PASS)")
            continue
        if rid in blocked and not a.retry_blocked:
            print(f"SKIP {rid} (blocked; pass --retry-blocked)")
            if not a.continue_past_need_main:
                stop = True
                break
            continue
        ok, verdict = execute_round(a.run_dir, a.kit, row, seat, a.timeout)
        if verdict == "external_pending":
            state.setdefault("external_pending", [])
            if rid not in state["external_pending"]:
                state["external_pending"].append(rid)
            update_state(a.state, state)
            print(f"EXTERNAL_PENDING {rid}")
            continue
        if verdict == "NEED_MAIN":
            mark_blocked(a.run_dir, a.state, state, rid, "manual checkpoint NEED_MAIN", "NEED_MAIN")
            print(f"NEED_MAIN {rid}")
            if not a.continue_past_need_main:
                stop = True
                break
            continue
        if not ok:
            mark_blocked(a.run_dir, a.state, state, rid, verdict, "BLOCKED")
            print(f"BLOCKED {rid}: {verdict}")
            stop = True
            break
        append_round(a.rounds_file, {"schema": 1, "round": rid, "kind": "product" if row in cfg["product_rounds"] else "prep", "verdict": "PASS", "at": now()})
        state.setdefault("product_rounds_passed" if row in cfg["product_rounds"] else "prep_rounds_passed", [])
        bucket = state["product_rounds_passed"] if row in cfg["product_rounds"] else state["prep_rounds_passed"]
        if rid not in bucket:
            bucket.append(rid)
        update_state(a.state, state, active_round=rid, terminal=False)
        completed.add(rid)
        print(f"PASS {rid}")

    passed_all = set(state.get("product_rounds_passed", [])) >= {r["id"] for r in cfg["product_rounds"]}
    accepted = set(state.get("human_checkpoints_accepted", [])) >= set(cfg["human_checkpoints"])
    if passed_all and accepted:
        atomic_write(a.run_dir / "DONE", f"product_rounds_passed=30/30\ncompleted_at={now()}\n")
        update_state(a.state, state, terminal=True, active_round=None)
    else:
        state["terminal"] = False
        update_state(a.state, state)
    return 1 if stop else 0


if __name__ == "__main__":
    raise SystemExit(main())
