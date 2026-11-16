# -*- coding: utf-8 -*-
"""Packet B · R03 `evidence_run.sh` 单测（含负向）。

覆盖 TASK §3.4：
  - `--shell 'printf x; exit 7'` → wrapper rc=7 且文件含 `rc=7`
  - `--shell 'false | tail'` → rc=1（pipefail 生效），stdout/stderr hash 存在
  - stderr 不被吞、`-- <cmd...>` 形式保留真实 rc
"""

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "evidence_run.sh"


def _run(tmp_path, *args, name="out.txt"):
    out = tmp_path / name
    proc = subprocess.run(
        [str(SCRIPT), "--out", str(out), "--label", "test", *args],
        capture_output=True,
        text=True,
    )
    return proc, out, out.read_text(encoding="utf-8")


def test_shell_exit_code_is_preserved(tmp_path):
    proc, out, text = _run(tmp_path, "--shell", "printf x; exit 7")
    assert proc.returncode == 7
    assert out.is_file()
    assert "rc=7" in text
    assert "stdout_sha256=" in text and "stderr_sha256=" in text
    stdout_section = text.split("--- stdout ---", 1)[1].split("--- stderr ---", 1)[0]
    assert stdout_section.strip() == "x"


def test_pipefail_makes_pipeline_fail(tmp_path):
    proc, _out, text = _run(tmp_path, "--shell", "false | tail")
    assert proc.returncode == 1
    assert "rc=1" in text
    assert "bash -o pipefail -c" in text.split("\n", 1)[0]
    assert "stdout_sha256=" in text and "stderr_sha256=" in text


def test_stderr_is_not_swallowed(tmp_path):
    proc, _out, text = _run(tmp_path, "--shell", "echo oops >&2; exit 0")
    assert proc.returncode == 0
    stderr_section = text.split("--- stderr ---", 1)[1]
    assert "oops" in stderr_section


def test_command_form_keeps_real_rc(tmp_path):
    proc, _out, text = _run(tmp_path, "--", "bash", "-c", "echo hi; exit 3")
    assert proc.returncode == 3
    assert "rc=3" in text
    assert "hi" in text


def test_missing_out_is_usage_error(tmp_path):
    proc = subprocess.run(
        [str(SCRIPT), "--label", "test", "--shell", "true"], capture_output=True, text=True
    )
    assert proc.returncode == 2
    assert "--out is required" in proc.stderr
