# -*- coding: utf-8 -*-
"""P-S10-03: runtime stdout/stderr spill + bounded proof projection."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import openrig_runtime_output as rt  # noqa: E402

SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "kickoff"
    / "openrig-round1-postrun-20261117"
    / "runtime-output-evidence.schema.s11b.json"
)


def _assert_sidecar_shape(payload: dict) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert set(payload) == set(schema["required"])
    assert payload["kind"] == "runtime-output-evidence"
    assert set(payload["streams"]) == {"stdout", "stderr"}
    for stream in payload["streams"].values():
        assert {"path", "sha256", "bytes", "tail", "truncated"} <= set(stream)
    try:
        import jsonschema
    except ImportError:
        return
    jsonschema.validate(payload, schema)


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_large_streams_spill_full_bytes_and_project_only_hash_path_tail(tmp_path):
    secret = "sk-runtime-output-secret"
    cmd = [
        sys.executable,
        "-c",
        "import sys; sys.stdout.write('O'*200000 + ' token=" + secret + "\\n');"
        "sys.stderr.write('E'*9000)",
    ]

    proc = rt.run_captured(
        cmd,
        env={**os.environ, "OPENRIG_AUTH_BEARER_TOKEN": secret},
        timeout=10,
        run_dir=tmp_path,
        label="large-success",
        capture_id="large-success",
        tail_bytes=1024,
        inline_limit=4096,
    )

    assert proc.returncode == 0
    assert proc.stdout_bytes == 200000 + len(" token=" + secret + "\n")
    assert proc.stdout_truncated is True
    assert proc.stdout_inline_truncated is True
    assert len(proc.stdout.encode("utf-8")) <= 1024
    assert len(proc.stdout_tail.encode("utf-8")) <= 1024
    assert "token=<redacted>" in proc.stdout_tail
    assert secret not in proc.stdout_tail

    stdout_spill = Path(proc.stdout_path)
    stderr_spill = Path(proc.stderr_path)
    sidecar = Path(proc.evidence_path)
    assert stdout_spill.is_file() and stderr_spill.is_file() and sidecar.is_file()
    assert stdout_spill.stat().st_size == proc.stdout_bytes
    assert stderr_spill.stat().st_size == proc.stderr_bytes
    assert hashlib.sha256(stdout_spill.read_bytes()).hexdigest() == proc.stdout_sha256
    assert hashlib.sha256(stderr_spill.read_bytes()).hexdigest() == proc.stderr_sha256
    assert _mode(stdout_spill) == 0o600
    assert _mode(stderr_spill) == 0o600
    assert _mode(sidecar) == 0o600

    sidecar_payload = json.loads(sidecar.read_text(encoding="utf-8"))
    _assert_sidecar_shape(sidecar_payload)
    assert sidecar_payload["kind"] == "runtime-output-evidence"
    assert sidecar_payload["policy"]["name"] == rt.POLICY_NAME
    assert sidecar_payload["policy"]["tailBytes"] == 1024
    assert sidecar_payload["policy"]["inlineLimitBytes"] == 4096
    assert sidecar_payload["streams"]["stdout"]["path"] == str(stdout_spill.resolve())
    assert sidecar_payload["streams"]["stdout"]["bytes"] == proc.stdout_bytes
    assert sidecar_payload["streams"]["stdout"]["truncated"] is True
    assert secret not in sidecar.read_text(encoding="utf-8")
    assert not list(stdout_spill.parent.glob("*.tmp"))

    projection = rt.capture_fields(proc)
    rendered = json.dumps(projection, ensure_ascii=False)
    assert secret not in rendered
    assert "O" * 5000 not in rendered
    assert len(rendered.encode("utf-8")) < 30000
    assert projection["stdoutSha256"] == proc.stdout_sha256
    assert projection["stdoutBytes"] == proc.stdout_bytes
    assert projection["stdoutPath"] == str(stdout_spill.resolve())
    assert projection["stdoutTail"] == proc.stdout_tail
    assert projection["stdoutTruncated"] is True
    assert sidecar_payload["streams"]["stdout"]["tailBytes"] == 1024
    assert projection["stdoutOmittedBytes"] == proc.stdout_bytes - 1024


def test_tail_cut_does_not_split_a_multibyte_codepoint(tmp_path):
    # Emit enough multi-byte characters that the 31-byte tail starts mid-codepoint.
    cmd = [sys.executable, "-c", "import sys; sys.stdout.write('中'*100)"]
    proc = rt.run_captured(
        cmd,
        env=os.environ.copy(),
        timeout=10,
        run_dir=tmp_path,
        label="multibyte",
        capture_id="multibyte",
        tail_bytes=31,
        inline_limit=1024,
    )
    assert proc.returncode == 0
    assert proc.stdout_truncated is True
    assert proc.stdout_tail
    assert "\ufffd" not in proc.stdout_tail
    assert proc.stdout_tail.endswith("中")


def test_timeout_keeps_partial_spill_and_reports_rc124(tmp_path):
    cmd = [
        sys.executable,
        "-c",
        "import sys,time; sys.stdout.write('started\\n'); sys.stdout.flush(); time.sleep(10)",
    ]
    proc = rt.run_captured(
        cmd,
        env=os.environ.copy(),
        timeout=1,
        run_dir=tmp_path,
        label="timeout",
        capture_id="timeout",
    )
    assert proc.returncode == 124
    assert proc.timed_out is True
    assert "started" in proc.stdout_tail
    assert "timeout after 1s" in proc.stderr
    assert Path(proc.stdout_path).is_file()
    assert Path(proc.stdout_path).read_bytes() == b"started\n"
    sidecar = json.loads(Path(proc.evidence_path).read_text(encoding="utf-8"))
    assert sidecar["timedOut"] is True
    assert sidecar["rc"] == 124


def test_materialized_fake_process_gets_same_bounded_contract(tmp_path):
    import subprocess

    raw_out = "out " * 1000 + "token=unknown-shaped-secret"
    raw_err = "err " * 900 + "api_key: another-secret"
    proc = subprocess.CompletedProcess(["rig", "down"], 2, raw_out, raw_err)

    proc = rt.materialize_completed_process(
        proc,
        run_dir=tmp_path,
        label="stop-down",
        redaction_secrets=(),
    )
    fields = rt.capture_fields(proc)
    assert fields["stdoutBytes"] == len(raw_out.encode())
    assert fields["stderrBytes"] == len(raw_err.encode())
    assert len(fields["stdoutTail"].encode()) <= rt.TAIL_BYTES
    assert len(fields["stderrTail"].encode()) <= rt.TAIL_BYTES
    assert "unknown-shaped-secret" not in fields["stdoutTail"]
    assert "another-secret" not in fields["stderrTail"]
    assert "token=<redacted>" in fields["stdoutTail"]
    assert "api_key: <redacted>" in fields["stderrTail"]
    assert Path(fields["evidencePath"]).is_file()
    _assert_sidecar_shape(json.loads(Path(fields["evidencePath"]).read_text(encoding="utf-8")))
    assert hashlib.sha256(Path(fields["stdoutPath"]).read_bytes()).hexdigest() == fields["stdoutSha256"]


def test_read_only_capture_keeps_bounded_metrics_but_leaves_run_tree_untouched(tmp_path):
    proc = rt.run_captured(
        [sys.executable, "-c", "import sys; sys.stdout.write('R'*12000); sys.stderr.write('S'*8000)"],
        env=os.environ.copy(),
        timeout=10,
        run_dir=tmp_path,
        label="status-live",
        capture_id="status-live",
        persist=False,
    )
    assert proc.returncode == 0
    assert proc.stdout_bytes == 12000 and proc.stderr_bytes == 8000
    assert proc.stdout_sha256 and proc.stderr_sha256
    assert proc.stdout_truncated is True and proc.stderr_truncated is True
    assert proc.stdout_path is None and proc.stderr_path is None
    assert proc.evidence_path is None
    assert list(tmp_path.rglob("*")) == [], "read-only capture must not write under the run dir"
    fields = rt.capture_fields(proc)
    assert fields["stdoutSha256"] == proc.stdout_sha256
    assert fields["stdoutBytes"] == 12000
    assert fields["stdoutPath"] is None and fields["evidencePath"] is None
    assert len(fields["stdoutTail"].encode()) <= rt.TAIL_BYTES
