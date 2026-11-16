# -*- coding: utf-8 -*-
"""Packet C · R01 `wf.py archive-gate` 单测（含负向）。

guard 用临时 fake 脚本替代（不得执行真实 teardown，也不得传 --execute）：
  - strict COMPLETE → rc=0 / ok:true
  - PARTIAL → rc=2 / ok:false，透传 archiveStatus + missing
  - manifest not found (guard rc=1) → rc=2 / ok:false
  - guard 文件缺失 → rc=3，明确 guard missing
"""

import argparse
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import wf  # noqa: E402

FAKE_GUARD = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
if "--execute" in args:
    open(os.environ["FAKE_GUARD_MARKER"], "w").write("executed")
mode = os.environ.get("FAKE_GUARD_MODE", "complete")
rid = args[args.index("--run-id") + 1]
if mode == "missing":
    print(json.dumps({"runId": rid, "error": "manifest not found"}))
    sys.exit(1)
if mode == "partial":
    print(json.dumps({"runId": rid, "archiveStatus": "PARTIAL", "complete": False,
                      "missing": ["transcriptCapture"], "missingRequired": []}))
    sys.exit(2)
print(json.dumps({"runId": rid, "archiveStatus": "COMPLETE", "complete": True,
                  "missing": [], "files": 3}))
sys.exit(0)
"""


@pytest.fixture
def guard_env(tmp_path, monkeypatch):
    guard = tmp_path / "fake-guard.py"
    guard.write_text(FAKE_GUARD, encoding="utf-8")
    marker = tmp_path / "executed.marker"
    monkeypatch.setenv("OPENRIG_TEARDOWN_GUARD", str(guard))
    monkeypatch.setenv("FAKE_GUARD_MARKER", str(marker))
    return guard, marker


def _gate(capsys):
    rc = wf.cmd_archive_gate(argparse.Namespace(run_id="t-run", archive_root="", json=True))
    return rc, json.loads(capsys.readouterr().out)


def test_complete_archive_passes(guard_env, monkeypatch, capsys):
    monkeypatch.setenv("FAKE_GUARD_MODE", "complete")
    rc, payload = _gate(capsys)
    assert rc == 0
    assert payload["ok"] is True
    assert payload["archiveStatus"] == "COMPLETE"
    assert payload["gateRc"] == 0


def test_partial_archive_fails_and_passes_through(guard_env, monkeypatch, capsys):
    monkeypatch.setenv("FAKE_GUARD_MODE", "partial")
    rc, payload = _gate(capsys)
    assert rc == 2
    assert payload["ok"] is False
    assert payload["archiveStatus"] == "PARTIAL"
    assert "transcriptCapture" in payload["missing"]


def test_manifest_missing_guard_rc1_maps_to_gate_rc2(guard_env, monkeypatch, capsys):
    monkeypatch.setenv("FAKE_GUARD_MODE", "missing")
    rc, payload = _gate(capsys)
    assert rc == 2
    assert payload["ok"] is False
    assert payload["guardRc"] == 1
    assert payload["error"] == "manifest not found"


def test_missing_guard_is_rc3(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OPENRIG_TEARDOWN_GUARD", str(tmp_path / "no-such-guard.py"))
    rc, payload = _gate(capsys)
    assert rc == 3
    assert payload["ok"] is False
    assert payload["error"] == "guard missing"


def test_guard_is_never_called_with_execute(guard_env, monkeypatch, capsys):
    _guard, marker = guard_env
    monkeypatch.setenv("FAKE_GUARD_MODE", "complete")
    _gate(capsys)
    assert not marker.exists(), "archive-gate must stay dry-run"
