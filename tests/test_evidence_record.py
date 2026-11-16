# -*- coding: utf-8 -*-
"""Packet C · R04 `wf.py evidence-record` 单测（含 revision 通道）。

  - record 自动算 bytes/sha256，默认 revision=1 / reason="initial closeout"
  - 二次 revision 替换同 path entry，保留 replacesSha256
  - revision 不递增时拒绝
  - 产出的 closeout.json 能通过 wf_close_lint --strict
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import wf  # noqa: E402
import wf_close_lint  # noqa: E402


def _record(rd, path="FINAL.md", **over):
    args = dict(
        run_id=rd.name,
        path=path,
        command="pytest -q",
        rc=0,
        revision=None,
        reason="initial closeout",
        json=True,
    )
    args.update(over)
    return wf.cmd_evidence_record(argparse.Namespace(**args))


def _run_dir(wf_env, run_id="t-record"):
    rd = wf_env.runs / run_id
    rd.mkdir(parents=True)
    (rd / "FINAL.md").write_text("final\n", encoding="utf-8")
    return rd


def _closeout(rd):
    return json.loads(
        (rd / "reports" / "evidence" / "closeout.json").read_text(encoding="utf-8")
    )


def test_record_computes_bytes_and_sha(wf_env, capsys):
    rd = _run_dir(wf_env)
    assert _record(rd) == 0
    payload = json.loads(capsys.readouterr().out)
    entry = payload["entry"]
    assert entry["bytes"] == len(b"final\n")
    assert entry["sha256"] == hashlib.sha256(b"final\n").hexdigest()
    assert entry["revision"] == 1
    assert entry["reason"] == "initial closeout"
    data = _closeout(rd)
    assert data["schemaVersion"] == 1
    assert data["entries"][0]["path"] == "FINAL.md"


def test_second_revision_keeps_replaces_sha(wf_env, capsys):
    rd = _run_dir(wf_env)
    _record(rd)
    first = _closeout(rd)["entries"][0]
    (rd / "FINAL.md").write_text("final v2\n", encoding="utf-8")
    capsys.readouterr()
    assert _record(rd, revision=2, reason="FINAL 修订") == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["replaced"] is True
    second = _closeout(rd)["entries"][0]
    assert second["revision"] == 2
    assert second["replacesSha256"] == first["sha256"]
    assert second["sha256"] == hashlib.sha256(b"final v2\n").hexdigest()


def test_revision_must_increase(wf_env, capsys):
    rd = _run_dir(wf_env)
    _record(rd)
    capsys.readouterr()
    with pytest.raises(SystemExit):
        _record(rd, revision=1, reason="same revision")


def test_missing_evidence_file_dies(wf_env):
    rd = _run_dir(wf_env)
    with pytest.raises(SystemExit):
        _record(rd, path="reports/nope.md")


def test_recorded_closeout_passes_strict_lint(wf_env, capsys):
    rd = _run_dir(wf_env)
    _record(rd)
    capsys.readouterr()
    findings = wf_close_lint.strict_findings(rd, rd.name)
    assert [f.code for f in findings if f.level == "ERROR"] == []
