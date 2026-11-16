# -*- coding: utf-8 -*-
"""Packet D · W5 `wf.py render-specialize` + `verify_render --specializations` 单测。

覆盖 TASK §4 / plan §4.6：
  - 无 specialization：mismatch → 默认 rc0/ok:false
  - exact specialization：rc0/ok:true、item `specialized:true`、--strict 仍 rc0
  - stale specialization（bytes/sha 不符）：仍 mismatch，--strict rc1
  - 无 reason 的 specialization 不被接受
  - specialization 文件坏 JSON → rc2
  - `wf.py render-specialize` 写入/更新条目并保留其它条目；越界路径拒绝
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import verify_render as vr  # noqa: E402
import wf  # noqa: E402

FILES = {"rig.yaml": b"rig: demo\n", "workflow.yaml": b"workflow: demo\n"}


def _make_run(tmp_path: Path) -> Path:
    rd = tmp_path / "runs" / "t-run"
    openrig = rd / "openrig"
    openrig.mkdir(parents=True)
    manifest = {"schemaVersion": 1, "runId": "t-run", "files": {}}
    for rel, raw in FILES.items():
        (openrig / rel).write_bytes(raw)
        manifest["files"][rel] = {
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    (openrig / "render-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return rd


def _specialize(rd: Path, rel: str, *, sha=None, size=None, reason="run needs a different port"):
    p = rd / "openrig" / rel
    raw = p.read_bytes()
    data = {
        "schemaVersion": 1,
        "runId": "t-run",
        "files": {
            rel: {
                "bytes": len(raw) if size is None else size,
                "sha256": hashlib.sha256(raw).hexdigest() if sha is None else sha,
                "reason": reason,
            }
        },
    }
    (rd / "openrig" / "render-specializations.json").write_text(
        json.dumps(data), encoding="utf-8"
    )
    return data


def _run(rd: Path, capsys, *extra):
    rc = vr.main(["--run-dir", str(rd), "--json", *extra])
    return rc, json.loads(capsys.readouterr().out)


def test_no_specialization_is_still_mismatch(tmp_path, capsys):
    rd = _make_run(tmp_path)
    (rd / "openrig" / "rig.yaml").write_bytes(b"rig: changed\n")
    rc, payload = _run(rd, capsys)
    assert rc == 0 and payload["ok"] is False
    assert [m["path"] for m in payload["mismatches"]] == ["rig.yaml"]
    assert payload["specialized"] == []
    assert payload["specializations"]["present"] is False


def test_exact_specialization_is_legal(tmp_path, capsys):
    rd = _make_run(tmp_path)
    (rd / "openrig" / "rig.yaml").write_bytes(b"rig: changed\n")
    _specialize(rd, "rig.yaml")
    rc, payload = _run(rd, capsys)
    assert rc == 0 and payload["ok"] is True
    assert payload["mismatches"] == []
    assert payload["specialized"] == ["rig.yaml"]
    item = next(c for c in payload["checked"] if c["path"] == "rig.yaml")
    assert item["specialized"] is True and item["ok"] is True
    assert payload["specializations"]["applied"][0]["reason"]


def test_exact_specialization_passes_strict(tmp_path, capsys):
    rd = _make_run(tmp_path)
    (rd / "openrig" / "rig.yaml").write_bytes(b"rig: changed\n")
    _specialize(rd, "rig.yaml")
    rc, payload = _run(rd, capsys, "--strict")
    assert rc == 0 and payload["ok"] is True
    assert payload["specializations"]["stale"] == []


def test_stale_specialization_does_not_rescue_mismatch(tmp_path, capsys):
    rd = _make_run(tmp_path)
    (rd / "openrig" / "rig.yaml").write_bytes(b"rig: changed again\n")
    _specialize(rd, "rig.yaml", sha="0" * 64)
    rc, payload = _run(rd, capsys)
    assert rc == 0 and payload["ok"] is False
    assert payload["specialized"] == []
    assert payload["specializations"]["stale"][0]["path"] == "rig.yaml"
    assert "stale" in payload["specializations"]["stale"][0]["reason"]
    rc, payload = _run(rd, capsys, "--strict")
    assert rc == 1 and payload["ok"] is False


def test_specialization_without_reason_is_rejected(tmp_path, capsys):
    rd = _make_run(tmp_path)
    (rd / "openrig" / "rig.yaml").write_bytes(b"rig: changed\n")
    _specialize(rd, "rig.yaml", reason="   ")
    rc, payload = _run(rd, capsys)
    assert payload["ok"] is False and rc == 0
    item = next(c for c in payload["checked"] if c["path"] == "rig.yaml")
    assert "reason" in item["specializationRejected"]


def test_invalid_specializations_file_is_rc2(tmp_path, capsys):
    rd = _make_run(tmp_path)
    (rd / "openrig" / "render-specializations.json").write_text("{oops", encoding="utf-8")
    rc, payload = _run(rd, capsys)
    assert rc == 2 and payload["error"]


def test_explicit_specializations_path(tmp_path, capsys):
    rd = _make_run(tmp_path)
    (rd / "openrig" / "rig.yaml").write_bytes(b"rig: changed\n")
    _specialize(rd, "rig.yaml")
    other = tmp_path / "elsewhere.json"
    (rd / "openrig" / "render-specializations.json").rename(other)
    rc, payload = _run(rd, capsys)
    assert payload["ok"] is False  # default path has no file now
    rc, payload = _run(rd, capsys, "--specializations", str(other))
    assert rc == 0 and payload["ok"] is True and payload["specialized"] == ["rig.yaml"]


# ---------------------------------------------------------------- wf.py side
@pytest.fixture
def run_env(tmp_path, monkeypatch):
    rd = _make_run(tmp_path)
    monkeypatch.setattr(wf, "RUNS", rd.parent)
    return rd


def _specialize_args(rd: Path, path="rig.yaml", reason="run binds port 47978"):
    return argparse.Namespace(
        run_id=rd.name, path=path, reason=reason, json=True
    )


def test_render_specialize_writes_entry(run_env, capsys):
    (run_env / "openrig" / "rig.yaml").write_bytes(b"rig: changed\n")
    assert wf.cmd_render_specialize(_specialize_args(run_env)) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["ok"] is True and summary["path"] == "rig.yaml"
    raw = (run_env / "openrig" / "rig.yaml").read_bytes()
    assert summary["sha256"] == hashlib.sha256(raw).hexdigest()
    assert summary["bytes"] == len(raw)
    data = json.loads(
        (run_env / "openrig" / "render-specializations.json").read_text(encoding="utf-8")
    )
    assert data["schemaVersion"] == 1 and data["runId"] == run_env.name
    assert data["files"]["rig.yaml"]["reason"] == "run binds port 47978"


def test_render_specialize_then_verify_is_green(run_env, capsys):
    (run_env / "openrig" / "rig.yaml").write_bytes(b"rig: changed\n")
    wf.cmd_render_specialize(_specialize_args(run_env))
    capsys.readouterr()
    payload = vr.verify(run_env)
    assert payload["ok"] is True and payload["specialized"] == ["rig.yaml"]


def test_render_specialize_updates_and_preserves_entries(run_env, capsys):
    (run_env / "openrig" / "rig.yaml").write_bytes(b"rig: v1\n")
    wf.cmd_render_specialize(_specialize_args(run_env, "rig.yaml", "first"))
    capsys.readouterr()
    (run_env / "openrig" / "workflow.yaml").write_bytes(b"workflow: v2\n")
    wf.cmd_render_specialize(_specialize_args(run_env, "workflow.yaml", "second"))
    capsys.readouterr()
    (run_env / "openrig" / "rig.yaml").write_bytes(b"rig: v3\n")
    wf.cmd_render_specialize(_specialize_args(run_env, "rig.yaml", "third"))
    capsys.readouterr()
    data = json.loads(
        (run_env / "openrig" / "render-specializations.json").read_text(encoding="utf-8")
    )
    assert set(data["files"]) == {"rig.yaml", "workflow.yaml"}
    assert data["files"]["rig.yaml"]["reason"] == "third"
    assert data["files"]["workflow.yaml"]["reason"] == "second"


def test_render_specialize_rejects_path_escape(run_env, capsys):
    with pytest.raises(SystemExit):
        wf.cmd_render_specialize(_specialize_args(run_env, "../../PROJECT.md"))
    assert "openrig/" in capsys.readouterr().err


def test_render_specialize_rejects_missing_file(run_env, capsys):
    with pytest.raises(SystemExit):
        wf.cmd_render_specialize(_specialize_args(run_env, "nope.yaml"))
    assert "文件不存在" in capsys.readouterr().err


def test_render_specialize_rejects_empty_reason(run_env, capsys):
    with pytest.raises(SystemExit):
        wf.cmd_render_specialize(_specialize_args(run_env, "rig.yaml", "  "))
    assert "--reason" in capsys.readouterr().err
