# -*- coding: utf-8 -*-
"""OpenRig teardown archive gate regression (AFC-004)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT.parents[1]
GUARD = WORKSPACE / "deepseek-项目" / "10-openrig-deepseek" / "scripts" / "openrig-teardown.py"
REQUIRED = ("runSnapshot", "sessionSnapshots", "transcriptCapture", "openrigState", "homeSnapshot")

import pytest

pytestmark = pytest.mark.skipif(
    not GUARD.is_file(), reason="10-openrig-deepseek teardown guard is not present in this checkout"
)


def _manifest(root: Path, run_id: str, status: str, *, complete_home: bool) -> Path:
    p = root / "machines" / "m1" / "runs" / run_id / "MANIFEST.json"
    p.parent.mkdir(parents=True)
    required = {k: True for k in REQUIRED}
    if not complete_home:
        required["homeSnapshot"] = False
    data = {
        "archiveStatus": status,
        "runId": run_id,
        "required": required,
        "missing": [] if status == "COMPLETE" else ["homeSnapshot"],
        "files": [{"path": "RECORD.md", "sha256": "x"}] if status == "COMPLETE" else [],
    }
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _marker_script(tmp_path: Path) -> Path:
    p = tmp_path / "mark.py"
    p.write_text("import pathlib,sys\npathlib.Path(sys.argv[1]).write_text('ran')\n", encoding="utf-8")
    return p


def _run(root: Path, run_id: str, *extra: str):
    return subprocess.run(
        [sys.executable, str(GUARD), "--run-id", run_id, "--archive-root", str(root), "--json", *extra],
        capture_output=True,
        text=True,
    )


def test_partial_archive_denies_teardown_and_does_not_execute(tmp_path):
    root = tmp_path / "archive"
    _manifest(root, "r-partial", "PARTIAL", complete_home=False)
    script = _marker_script(tmp_path)
    marker = tmp_path / "ran.txt"
    r = _run(root, "r-partial", "--execute", "--teardown-cmd", f"{sys.executable} {script} {marker}")
    assert r.returncode == 2
    assert not marker.exists()
    data = json.loads(r.stdout)
    assert data["archiveStatus"] == "PARTIAL"
    assert data["exitCode"] is None


def test_complete_archive_allows_teardown_command(tmp_path):
    root = tmp_path / "archive"
    _manifest(root, "r-complete", "COMPLETE", complete_home=True)
    script = _marker_script(tmp_path)
    marker = tmp_path / "ran.txt"
    r = _run(root, "r-complete", "--execute", "--teardown-cmd", f"{sys.executable} {script} {marker}")
    assert r.returncode == 0, r.stdout + r.stderr
    assert marker.exists()
    assert json.loads(r.stdout)["complete"] is True


def test_partial_override_requires_recorded_decision(tmp_path):
    root = tmp_path / "archive"
    _manifest(root, "r-hist", "PARTIAL", complete_home=False)
    script = _marker_script(tmp_path)
    marker = tmp_path / "ran.txt"
    cmd = ["--execute", "--teardown-cmd", f"{sys.executable} {script} {marker}", "--allow-incomplete"]
    denied = _run(root, "r-hist", *cmd)
    assert denied.returncode == 2 and not marker.exists()
    # 外部 openrig-teardown.py 现行契约：--allow-incomplete 必须在归档根
    # 的 ARCHIVE-DECISIONS.md 中记录同一 run 的 D-xxx，不能只传 --decision。
    (root / "ARCHIVE-DECISIONS.md").write_text(
        "| run-id | decision | reason |\n"
        "| --- | --- | --- |\n"
        "| r-hist | D-009 | accepted historical partial archive |\n",
        encoding="utf-8",
    )
    allowed = _run(root, "r-hist", *cmd, "--decision", "D-009")
    assert allowed.returncode == 0, allowed.stdout + allowed.stderr
    assert marker.exists()


def test_complete_preflight_without_execute_is_read_only(tmp_path):
    root = tmp_path / "archive"
    _manifest(root, "r-dry", "COMPLETE", complete_home=True)
    r = _run(root, "r-dry")
    assert r.returncode == 0
    assert json.loads(r.stdout)["dryRun"] is True
