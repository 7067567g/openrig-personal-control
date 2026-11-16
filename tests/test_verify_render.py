# -*- coding: utf-8 -*-
"""Packet C · R07 `verify_render.py` 单测（含负向）。

  - 未改 → rc=0 / ok:true
  - 改一字节 → 默认 rc=0 / ok:false；--strict → rc=1
  - manifest 缺失 / 坏 JSON → rc=2，不假装通过
"""

import hashlib
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import verify_render  # noqa: E402


def _make_run(tmp_path, name="manifest"):
    rd = tmp_path / "runs" / "t-run"
    (rd / "openrig" / "agents").mkdir(parents=True)
    files = {
        "rig.yaml": b"rig: demo\n",
        "agents/worker/agent.yaml": b"id: worker\n",
    }
    for rel, raw in files.items():
        target = rd / "openrig" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    manifest = {
        "schemaVersion": 1,
        "runId": "t-run",
        "files": {
            rel: {
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
            for rel, raw in files.items()
        },
    }
    (rd / "openrig" / "render-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return rd


def _run(rd, capsys, *extra):
    rc = verify_render.main(["--run-dir", str(rd), "--json", *extra])
    return rc, json.loads(capsys.readouterr().out)


def test_unchanged_manifest_passes(tmp_path, capsys):
    rd = _make_run(tmp_path)
    rc, payload = _run(rd, capsys)
    assert rc == 0
    assert payload["ok"] is True
    assert len(payload["checked"]) == 2


def test_one_byte_change_is_warn_by_default_strict_fails(tmp_path, capsys):
    rd = _make_run(tmp_path)
    (rd / "openrig" / "rig.yaml").write_bytes(b"rig: demO\n")
    rc, payload = _run(rd, capsys)
    assert rc == 0
    assert payload["ok"] is False
    assert payload["mismatches"][0]["path"] == "rig.yaml"

    rc, payload = _run(rd, capsys, "--strict")
    assert rc == 1
    assert payload["ok"] is False


def test_missing_manifest_is_rc2(tmp_path, capsys):
    rd = _make_run(tmp_path)
    (rd / "openrig" / "render-manifest.json").unlink()
    rc, payload = _run(rd, capsys)
    assert rc == 2
    assert payload["ok"] is False
    assert "missing" in payload["error"]


def test_bad_json_is_rc2(tmp_path, capsys):
    rd = _make_run(tmp_path)
    (rd / "openrig" / "render-manifest.json").write_text("{not json", encoding="utf-8")
    rc, payload = _run(rd, capsys)
    assert rc == 2
    assert payload["ok"] is False
    assert "not valid JSON" in payload["error"]


def test_missing_listed_file_is_mismatch(tmp_path, capsys):
    rd = _make_run(tmp_path)
    (rd / "openrig" / "rig.yaml").unlink()
    rc, payload = _run(rd, capsys, "--strict")
    assert rc == 1
    assert any(m.get("reason") == "file missing" for m in payload["mismatches"])
