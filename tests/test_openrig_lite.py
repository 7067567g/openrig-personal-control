# -*- coding: utf-8 -*-
"""Draft OpenRig lite mode: single-seat, one-task contract."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import types
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import openrig_lite as lite  # noqa: E402

FAKE_RIG = r'''#!/usr/bin/env python3
import json, os, sys
log = os.environ.get("FAKE_RIG_LOG")
if log:
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(" ".join(sys.argv[1:]) + "\n")
args = sys.argv[1:]
if args[:2] == ["daemon", "start"] or args[:1] in (["up"], ["send"], ["down"]) or args[:2] == ["daemon", "stop"]:
    print(json.dumps({"ok": True}))
    sys.exit(0)
if args[:1] == ["ps"]:
    seat = os.environ.get("FAKE_RIG_SEAT", "")
    print(json.dumps([{"canonicalSessionName": seat, "startupStatus": "ready", "sessionStatus": "running"}]))
    sys.exit(0)
print("unexpected fake rig call: " + " ".join(args), file=sys.stderr)
sys.exit(9)
'''


def _executable(tmp_path: Path, name: str) -> Path:
    p = tmp_path / "bin" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    p.chmod(0o755)
    return p


@pytest.fixture(autouse=True)
def _default_runtime_bins(tmp_path, monkeypatch):
    """Keep existing tests deterministic regardless of host PATH."""
    for name in ("opencode", "dsh"):
        monkeypatch.setenv(f"OPENRIG_{name.upper()}_BIN", str(_executable(tmp_path, name)))


def _init_lite(tmp_path: Path, run_name: str, *extra: str) -> tuple[int, Path]:
    task = tmp_path / f"task-{run_name}.md"
    task.write_text("do one thing\n", encoding="utf-8")
    run = tmp_path / "runs" / run_name
    rc = lite.main([
        "init", "--run-dir", str(run), "--cwd", str(tmp_path),
        "--task-file", str(task), "--json", *extra,
    ])
    return rc, run


def _load_entry_residuals_module():
    path = Path(__file__).with_name("test_openrig_run_entry_residuals.py")
    spec = importlib.util.spec_from_file_location("_entry_residuals_under_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_HOME_PATH = re.compile(r"(?<![/A-Za-z0-9._-])/home/[A-Za-z0-9._-]+/")
_CODE_SUFFIXES = {".py", ".sh", ".ps1", ".js", ".mjs", ".ts", ".tsx"}


def _home_path_hits(root: Path) -> list[str]:
    """Find person-specific home paths in executable/test source, not run evidence."""
    hits: list[str] = []
    for dirname in ("scripts", "tests"):
        base = root / dirname
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in _CODE_SUFFIXES:
                continue
            if "runs" in path.parts:
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for lineno, line in enumerate(lines, 1):
                if _HOME_PATH.search(line):
                    hits.append(f"{path}:{lineno}: {line.strip()}")
    return hits


def _fake_rig(tmp_path: Path) -> Path:
    p = tmp_path / "fake-rig"
    p.write_text(FAKE_RIG, encoding="utf-8")
    p.chmod(0o755)
    return p


def _run_json(capsys, func, args) -> dict:
    rc = func(args)
    out = capsys.readouterr().out.strip()
    assert out, "expected JSON output"
    return {"rc": rc, **json.loads(out)}


def test_init_creates_single_seat_bundle(tmp_path):
    task = tmp_path / "task.md"
    task.write_text("do one thing\n", encoding="utf-8")
    run = tmp_path / "runs" / "my-lite"
    rc = lite.main([
        "init", "--run-dir", str(run), "--cwd", str(tmp_path),
        "--task-file", str(task), "--port", "47993", "--openrig-cli", "rig", "--json",
    ])
    assert rc == 0
    bridge = json.loads((run / "openrig" / "OPENRIG-BRIDGE.json").read_text())
    assert bridge["mode"] == "lite"
    assert bridge["seatMap"] == {"worker": "worker@openrig-lite-my-lite"}
    assert "one seat" in (run / "LITE.md").read_text().lower()
    rig = (run / "openrig" / "rig.yaml").read_text()
    assert "id: worker" in rig and "id: solo" in rig
    assert (run / "TASK.md").read_text() == "do one thing\n"


def test_start_dry_run_executes_nothing(tmp_path, capsys):
    task = tmp_path / "task.md"
    task.write_text("do one thing\n", encoding="utf-8")
    run = tmp_path / "runs" / "lite-dry"
    fake = _fake_rig(tmp_path)
    assert lite.main([
        "init", "--run-dir", str(run), "--cwd", str(tmp_path), "--task-file", str(task),
        "--openrig-cli", str(fake), "--json",
    ]) == 0
    capsys.readouterr()
    payload = _run_json(capsys, lite.cmd_start, type("A", (), {
        "run_dir": str(run), "dry_run": True, "timeout": 5, "json": True,
    })())
    assert payload["rc"] == 0 and payload["dryRun"] is True
    assert [p["step"] for p in payload["plan"]] == ["daemon-start", "up", "wait-ready", "send-task"]
    assert not (run / "reports" / "evidence" / "launch.json").exists()


def test_start_runs_daemon_up_ready_send_and_writes_launch(tmp_path, monkeypatch, capsys):
    task = tmp_path / "task.md"
    task.write_text("do one thing\n", encoding="utf-8")
    run = tmp_path / "runs" / "lite-start"
    fake = _fake_rig(tmp_path)
    log = tmp_path / "fake.log"
    monkeypatch.setenv("FAKE_RIG_LOG", str(log))
    monkeypatch.setenv("FAKE_RIG_SEAT", "worker@openrig-lite-lite-start")
    assert lite.main([
        "init", "--run-dir", str(run), "--cwd", str(tmp_path), "--task-file", str(task),
        "--openrig-cli", str(fake), "--json",
    ]) == 0
    capsys.readouterr()
    payload = _run_json(capsys, lite.cmd_start, type("A", (), {
        "run_dir": str(run), "dry_run": False, "timeout": 5, "json": True,
    })())
    assert payload["rc"] == 0 and payload["ok"] is True
    assert [e["step"] for e in payload["executed"]] == ["daemon-start", "up", "wait-ready", "send-task"]
    launch = json.loads((run / "reports" / "evidence" / "launch.json").read_text())
    assert launch["status"] == "running"
    assert launch["session"] == "worker@openrig-lite-lite-start"
    calls = log.read_text().splitlines()
    assert any(c.startswith("daemon start --no-kernel --port") for c in calls)
    assert any(c.startswith("up ") and "--cwd" in c for c in calls)
    assert any(c.startswith("send worker@openrig-lite-lite-start") for c in calls)


def test_stop_stops_down_and_daemon_without_deleting_home(tmp_path, monkeypatch, capsys):
    task = tmp_path / "task.md"
    task.write_text("do one thing\n", encoding="utf-8")
    run = tmp_path / "runs" / "lite-stop"
    fake = _fake_rig(tmp_path)
    monkeypatch.setenv("FAKE_RIG_SEAT", "worker@openrig-lite-lite-stop")
    assert lite.main([
        "init", "--run-dir", str(run), "--cwd", str(tmp_path), "--task-file", str(task),
        "--openrig-cli", str(fake), "--json",
    ]) == 0
    capsys.readouterr()
    payload = _run_json(capsys, lite.cmd_stop, type("A", (), {
        "run_dir": str(run), "keep_home": True, "json": True,
    })())
    assert payload["rc"] == 0
    assert [e["step"] for e in payload["executed"]] == ["down", "daemon-stop"]
    bridge = json.loads((run / "openrig" / "OPENRIG-BRIDGE.json").read_text())
    assert Path(bridge["openrigHome"]).exists() is False  # never created by the fake


def test_lite_is_reachable_from_openrig_run(tmp_path):
    task = tmp_path / "task.md"
    task.write_text("do one thing\n", encoding="utf-8")
    import openrig_run
    rc = openrig_run.main(["lite", "init", "--run-dir", str(tmp_path / "runs" / "via-run"),
                           "--cwd", str(tmp_path), "--task-file", str(task), "--json"])
    assert rc == 0
    assert (tmp_path / "runs" / "via-run" / "openrig" / "OPENRIG-BRIDGE.json").is_file()


@pytest.mark.parametrize(
    ("runtime", "explicit_flag", "env_var", "env_key"),
    [
        ("opencode", "--opencode-bin", "OPENRIG_OPENCODE_BIN", "OPENRIG_OPENCODE_BIN"),
        ("dsh", "--dsh-bin", "OPENRIG_DSH_BIN", "OPENRIG_DSH_BIN"),
    ],
)
def test_init_explicit_binary_wins_over_env(tmp_path, monkeypatch, runtime, explicit_flag, env_var, env_key):
    explicit = _executable(tmp_path, f"{runtime}-explicit")
    env_bin = _executable(tmp_path, f"{runtime}-env")
    monkeypatch.setenv(env_var, str(env_bin))
    rc, run = _init_lite(
        tmp_path, f"explicit-{runtime}", "--runtime", runtime, explicit_flag, str(explicit),
    )
    assert rc == 0
    bridge = json.loads((run / "openrig" / "OPENRIG-BRIDGE.json").read_text())
    assert bridge["runtimeEnv"][env_key] == str(explicit.resolve())


@pytest.mark.parametrize(
    ("runtime", "flag", "env_var", "env_key", "command"),
    [
        ("opencode", "--opencode-bin", "OPENRIG_OPENCODE_BIN", "OPENRIG_OPENCODE_BIN", "opencode"),
        ("dsh", "--dsh-bin", "OPENRIG_DSH_BIN", "OPENRIG_DSH_BIN", "dsh"),
    ],
)
def test_init_binary_env_path_beats_path_lookup(tmp_path, monkeypatch, runtime, flag, env_var, env_key, command):
    env_bin = _executable(tmp_path, f"{runtime}-env-only")
    monkeypatch.setenv(env_var, str(env_bin))

    def only_env(value):
        assert value == str(env_bin), f"unexpected lookup {value!r}"
        return str(env_bin)

    monkeypatch.setattr(lite.shutil, "which", only_env)
    rc, run = _init_lite(tmp_path, f"env-{runtime}", "--runtime", runtime)
    assert rc == 0
    bridge = json.loads((run / "openrig" / "OPENRIG-BRIDGE.json").read_text())
    assert bridge["runtimeEnv"][env_key] == str(env_bin.resolve())


@pytest.mark.parametrize(
    ("runtime", "env_var", "command"),
    [
        ("opencode", "OPENRIG_OPENCODE_BIN", "opencode"),
        ("dsh", "OPENRIG_DSH_BIN", "dsh"),
    ],
)
def test_init_binary_path_fallback(tmp_path, monkeypatch, runtime, env_var, command):
    monkeypatch.delenv(env_var, raising=False)
    path_bin = _executable(tmp_path, command)

    def path_only(value):
        assert value == command
        return str(path_bin)

    monkeypatch.setattr(lite.shutil, "which", path_only)
    rc, run = _init_lite(tmp_path, f"path-{runtime}", "--runtime", runtime)
    assert rc == 0
    env_key = "OPENRIG_OPENCODE_BIN" if runtime == "opencode" else "OPENRIG_DSH_BIN"
    bridge = json.loads((run / "openrig" / "OPENRIG-BRIDGE.json").read_text())
    assert bridge["runtimeEnv"][env_key] == str(path_bin.resolve())


@pytest.mark.parametrize(
    ("runtime", "env_var", "flag", "env_name"),
    [
        ("opencode", "OPENRIG_OPENCODE_BIN", "--opencode-bin", "OPENRIG_OPENCODE_BIN"),
        ("dsh", "OPENRIG_DSH_BIN", "--dsh-bin", "OPENRIG_DSH_BIN"),
    ],
)
def test_init_binary_missing_returns_named_error(tmp_path, monkeypatch, capsys, runtime, env_var, flag, env_name):
    monkeypatch.delenv(env_var, raising=False)
    monkeypatch.setattr(lite.shutil, "which", lambda _value: None)
    rc, run = _init_lite(tmp_path, f"missing-{runtime}", "--runtime", runtime)
    captured = capsys.readouterr()
    assert rc == 2
    assert "[ERROR]" in captured.err
    assert flag in captured.err and env_name in captured.err
    assert not run.exists()


def test_entry_residuals_use_explicit_product_env(tmp_path, monkeypatch):
    product = tmp_path / "product"
    product.mkdir()
    monkeypatch.setenv("OPENRIG_PRODUCT_REPO", str(product))
    module = _load_entry_residuals_module()
    assert module.PRODUCT == product.resolve()
    assert module.DRIVERS == product.resolve() / "packages" / "daemon" / "test" / "s9-drivers"


def test_entry_residuals_have_no_implicit_product_home(monkeypatch):
    monkeypatch.delenv("OPENRIG_PRODUCT_REPO", raising=False)
    module = _load_entry_residuals_module()
    assert module.PRODUCT is None
    assert module.DRIVERS is None
    assert "OPENRIG_PRODUCT_REPO" in module.needs_product.mark.kwargs["reason"]


def test_preflight_monitor_target_is_optional(tmp_path, monkeypatch):
    import openrig_preflight as pf

    monkeypatch.delenv("OPENRIG_MONITOR_DIR", raising=False)
    assert pf.resolve_monitor_target_file() is None
    monkeypatch.setenv("OPENRIG_MONITOR_DIR", str(tmp_path / "monitor"))
    assert pf.resolve_monitor_target_file() == (tmp_path / "monitor" / "target.json").resolve()

    monkeypatch.setattr(pf, "TARGET_FILE", None)
    args = types.SimpleNamespace(no_monitor=False, run_id="r1", label="", rig="", seat="", job="")
    skipped = pf.register_monitor(args, str(tmp_path / "run"), str(tmp_path / "gov"))
    assert skipped["ok"] is False
    assert skipped["skipped"] == "monitor_dir_unset"
    assert "OPENRIG_MONITOR_DIR" in skipped["reason"]
    assert not (tmp_path / "run").exists()


def test_static_home_path_guard_detects_synthetic_file(tmp_path):
    bad = tmp_path / "scripts" / "bad.py"
    bad.parent.mkdir()
    bad.write_text("HOME = \"" + "/" + "home" + "/bob/project" + "\"\n", encoding="utf-8")
    assert _home_path_hits(tmp_path)


def test_static_home_path_guard_ignores_runs_tree(tmp_path):
    evidence = tmp_path / "tests" / "runs" / "evidence.py"
    evidence.parent.mkdir(parents=True)
    evidence.write_text("P = \"" + "/" + "home" + "/bob/project" + "\"\n", encoding="utf-8")
    assert _home_path_hits(tmp_path) == []


def test_workflow_group_scripts_and_tests_have_no_absolute_home_paths():
    """Guard only person-specific home paths; sibling-relative portability is NEW-1."""
    assert _home_path_hits(Path(__file__).resolve().parents[1]) == []


def test_product_s9_fixture_has_no_machine_home_paths():
    product_env = os.environ.get("OPENRIG_PRODUCT_REPO")
    if not product_env:
        pytest.skip("OPENRIG_PRODUCT_REPO is unset; product fixture hygiene not checked")
    fixture = Path(product_env) / "packages" / "daemon" / "test" / "s9-drivers" / "provision-fixtures.ts"
    assert fixture.is_file()
    assert not _HOME_PATH.search(fixture.read_text(encoding="utf-8"))
