# -*- coding: utf-8 -*-
"""Self-tests for F-01 (fake rig), F-09 (IO ban) and RT-02 pre-parse."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import urllib.request

import pytest

from fake_rig import (
    Call,
    Clock,
    FakeRig,
    IdFactory,
    Step,
    check_launch_options,
    format_dt,
    parse_dt,
    redact_argv,
    sha256_text,
    strip_allow_override,
)
from guards import (
    ExternalIOForbidden,
    FixtureEscape,
    assert_fixture_home,
    is_fixture,
    no_external_io,
)


def make_rig(tmp_path, script, *, clock=None, ids=None) -> FakeRig:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return FakeRig(home, script, clock or Clock(), ids or IdFactory(), tmp_root=tmp_path)


# ---------------------------------------------------------------------------
# capture / exit codes
# ---------------------------------------------------------------------------

def test_capture_records_argv_cwd_and_two_timestamps(tmp_path):
    rig = make_rig(
        tmp_path,
        [Step(argv=("rig", "check", "--run-dir", "r1"), repeat="consumed", rc=0)],
    )
    call = rig.run(("rig", "check", "--run-dir", "r1"), cwd=str(tmp_path / "proj"))
    assert isinstance(call, Call)
    assert call.argv == ("rig", "check", "--run-dir", "r1")
    assert call.cwd == str(tmp_path / "proj")
    assert call.rc == 0
    assert call.startedAt != call.endedAt
    assert parse_dt(call.startedAt) < parse_dt(call.endedAt)
    assert call.provenance == "fixture"
    assert is_fixture(call.to_dict())


def test_stdout_and_stderr_hashes_match_payload(tmp_path):
    rig = make_rig(
        tmp_path,
        [Step(argv=("rig", "status"), repeat="consumed", stdout="out\n", stderr="err\n")],
    )
    call = rig.run(("rig", "status"), cwd=".")
    assert call.stdoutSha256 == hashlib.sha256(b"out\n").hexdigest()
    assert call.stderrSha256 == hashlib.sha256(b"err\n").hexdigest()
    assert call.stdoutSha256 == sha256_text("out\n")


def test_payload_is_sorted_json(tmp_path):
    rig = make_rig(
        tmp_path,
        [Step(argv=("rig", "status"), repeat="consumed", payload={"b": 1, "a": 2})],
    )
    call, parsed = rig.run_json(("rig", "status"), cwd=".")
    assert call.stdout == json.dumps({"a": 2, "b": 1}, sort_keys=True)
    assert parsed == {"a": 2, "b": 1}


def test_unscripted_call_fails_closed_with_rc2(tmp_path):
    rig = make_rig(tmp_path, [])
    call = rig.run(("rig", "up", "spec.yaml"), cwd=".")
    assert call.rc == 2
    assert call.code == "fixture_unscripted_call"
    assert call.phase is None
    assert len(rig.calls) == 1


def test_unscripted_call_never_defaults_to_success(tmp_path):
    rig = make_rig(tmp_path, [Step(argv=("rig", "a"), repeat="consumed")])
    call = rig.run(("rig", "completely", "different"), cwd=".")
    assert call.rc != 0


def test_repeat_consumed_returns_launch_verb_consumed(tmp_path):
    rig = make_rig(tmp_path, [Step(argv=("rig", "up"), repeat="consumed", rc=0)])
    first = rig.run(("rig", "up"), cwd=".")
    second = rig.run(("rig", "up"), cwd=".")
    assert first.rc == 0
    assert second.rc == 2
    assert second.code == "launch_verb_consumed"
    assert [c.code for c in rig.calls] == [None, "launch_verb_consumed"]


def test_repeat_idempotent_replays_without_consuming(tmp_path):
    rig = make_rig(
        tmp_path,
        [Step(argv=("rig", "check"), repeat="idempotent", payload={"ok": True})],
    )
    first = rig.run(("rig", "check"), cwd=".")
    second = rig.run(("rig", "check"), cwd=".")
    assert first.rc == second.rc == 0
    assert second.replayed is True
    assert first.stdout == second.stdout
    assert len(rig.calls) == 2


def test_repeat_unscripted_mode(tmp_path):
    rig = make_rig(tmp_path, [Step(argv=("rig", "check"), repeat="unscripted")])
    rig.run(("rig", "check"), cwd=".")
    second = rig.run(("rig", "check"), cwd=".")
    assert second.rc == 2
    assert second.code == "fixture_unscripted_call"


def test_state_transition_phase_is_recorded(tmp_path):
    rig = make_rig(
        tmp_path,
        [Step(argv=("rig", "up"), repeat="consumed", stateBefore="DAEMON_READY", stateAfter="RIG_READY")],
    )
    call = rig.run(("rig", "up"), cwd=".")
    assert call.phase == "DAEMON_READY->RIG_READY"


def test_calls_are_append_only_in_order(tmp_path):
    rig = make_rig(
        tmp_path,
        [
            Step(argv=("rig", "a"), repeat="consumed"),
            Step(argv=("rig", "b"), repeat="consumed"),
        ],
    )
    rig.run(("rig", "a"), cwd=".")
    rig.run(("rig", "b"), cwd=".")
    assert [c.argv for c in rig.calls] == [("rig", "a"), ("rig", "b")]
    assert len(rig.calls) == 2


# ---------------------------------------------------------------------------
# determinism / ids / clock
# ---------------------------------------------------------------------------

def test_clock_and_ids_are_deterministic():
    def run_once():
        clock = Clock()
        ids = IdFactory()
        return [clock.now() for _ in range(3)], [ids.next() for _ in range(3)]

    assert run_once() == run_once()


def test_clock_advance_and_peek():
    clock = Clock(start="2026-02-03T04:05:06Z", tick_seconds=2)
    assert clock.peek() == "2026-02-03T04:05:06Z"
    assert clock.now() == "2026-02-03T04:05:06Z"
    assert clock.advance(60) == "2026-02-03T04:06:08Z"
    assert format_dt(parse_dt(clock.peek())) == clock.peek()


def test_two_rigs_same_seed_produce_identical_calls(tmp_path):
    script = [Step(argv=("rig", "check"), repeat="consumed", stdout="x")]

    def run_once():
        rig = make_rig(tmp_path, script)
        return rig.run(("rig", "check"), cwd=".").to_dict()

    assert run_once() == run_once()


# ---------------------------------------------------------------------------
# redaction
# ---------------------------------------------------------------------------

def test_step_secret_marks_call_redacted_and_hides_value(tmp_path):
    rig = make_rig(
        tmp_path,
        [Step(argv=("rig", "login", "--token", "s3cr3t"), repeat="consumed", secret=True)],
    )
    call = rig.run(("rig", "login", "--token", "s3cr3t"), cwd=".")
    assert call.redacted is True
    assert "s3cr3t" not in json.dumps(call.to_dict())
    assert call.raw_argv == ("rig", "login", "--token", "s3cr3t")


def test_non_secret_call_is_not_redacted(tmp_path):
    rig = make_rig(tmp_path, [Step(argv=("rig", "status"), repeat="consumed")])
    call = rig.run(("rig", "status"), cwd=".")
    assert call.redacted is False
    assert "***" not in call.argv


def test_redact_argv_handles_env_style_pairs():
    argv, redacted = redact_argv(("rig", "x", "API_KEY=abc", "plain=1"))
    assert redacted is True
    assert argv == ("rig", "x", "API_KEY=***", "plain=1")


# ---------------------------------------------------------------------------
# fixture escape (RT-28)
# ---------------------------------------------------------------------------

def test_refuses_home_with_openrig_sqlite(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "openrig.sqlite").write_bytes(b"not a real db")
    with pytest.raises(FixtureEscape) as excinfo:
        FakeRig(home, [], Clock(), IdFactory(), tmp_root=tmp_path)
    assert excinfo.value.reason == "contains_openrig_sqlite"


def test_refuses_real_openrig_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("OPENRIG_HOME", str(home))
    with pytest.raises(FixtureEscape) as excinfo:
        FakeRig(home, [], Clock(), IdFactory(), tmp_root=tmp_path)
    assert excinfo.value.reason == "real_openrig_home"


def test_refuses_path_outside_tmp_root(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(FixtureEscape) as excinfo:
        FakeRig(outside, [], Clock(), IdFactory(), tmp_root=allowed)
    assert excinfo.value.reason == "outside_tmp_root"


def test_accepts_plain_tmp_path(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    assert assert_fixture_home(home, tmp_root=tmp_path) == home.resolve()


# ---------------------------------------------------------------------------
# F-09 external IO ban
# ---------------------------------------------------------------------------

def test_subprocess_run_is_forbidden():
    with pytest.raises(ExternalIOForbidden):
        subprocess.run(["true"], check=False)


def test_subprocess_popen_is_forbidden():
    with pytest.raises(ExternalIOForbidden):
        subprocess.Popen(["true"])


def test_os_system_is_forbidden():
    with pytest.raises(ExternalIOForbidden):
        os.system("true")


def test_socket_connect_is_forbidden():
    with pytest.raises(ExternalIOForbidden):
        socket.socket().connect(("127.0.0.1", 9))


def test_urlopen_is_forbidden():
    with pytest.raises(ExternalIOForbidden):
        urllib.request.urlopen("http://127.0.0.1:9/")  # noqa: S310


def test_nested_ban_restores_the_outer_ban():
    assert subprocess.run.__name__.startswith("forbidden_")
    with no_external_io():
        pass
    # the inner context restored the outer autouse ban, not the real function
    with pytest.raises(ExternalIOForbidden):
        subprocess.run(["true"], check=False)


def test_fixture_modules_do_not_import_product_code():
    import fake_rig

    source = open(fake_rig.__file__, encoding="utf-8").read()
    assert "openrig_run" not in source
    assert "import wf" not in source


# ---------------------------------------------------------------------------
# RT-02 --allow-direct pre-parse
# ---------------------------------------------------------------------------

def test_allow_direct_before_subcommand_is_stripped_and_audited():
    parsed = strip_allow_override(("rig", "--allow-direct", "up", "spec.yaml"), uid=1000, pid=42)
    assert parsed.argv == ("rig", "up", "spec.yaml")
    assert parsed.allow_override is True
    assert parsed.override_source == "argv"
    assert parsed.audit["event"] == "allow_override"
    assert parsed.audit["verb"] == "up"
    assert parsed.audit["pid"] == 42


def test_allow_direct_after_subcommand_is_not_stripped():
    parsed = strip_allow_override(("rig", "up", "--allow-direct"), uid=1, pid=1)
    assert parsed.argv == ("rig", "up", "--allow-direct")
    assert parsed.allow_override is False
    assert parsed.audit is None


def test_allow_direct_after_double_dash_is_not_stripped():
    parsed = strip_allow_override(("rig", "up", "--", "--allow-direct"), uid=1, pid=1)
    assert parsed.argv == ("rig", "up", "--", "--allow-direct")
    assert parsed.allow_override is False


def test_plain_rig_up_has_no_override_record():
    parsed = strip_allow_override(("rig", "up", "spec.yaml"), uid=1, pid=1)
    assert parsed.allow_override is False
    assert parsed.audit is None


def test_openrig_allow_direct_env_is_recorded():
    parsed = strip_allow_override(("rig", "up"), env={"OPENRIG_ALLOW_DIRECT": "1"}, uid=1, pid=1)
    assert parsed.allow_override is True
    assert parsed.override_source == "env"
    assert parsed.audit["source"] == "env"


def test_step_from_command_uses_shell_splitting():
    step = Step.from_command("rig up spec.yaml --yes", repeat="consumed")
    assert step.argv == ("rig", "up", "spec.yaml", "--yes")


def test_step_rejects_unknown_repeat_mode():
    with pytest.raises(ValueError):
        Step(argv=("rig",), repeat="sometimes")


# ---------------------------------------------------------------------------
# RT-03 / RT-04 option validator (not a scripted rc)
# ---------------------------------------------------------------------------

def test_start_resume_is_an_unknown_option():
    verdict = check_launch_options(("rig", "start", "--run-dir", "r1", "--resume"))
    assert verdict.ok is False
    assert verdict.code == "unknown_option"
    assert "--resume" in verdict.unknown


def test_skip_validate_and_skip_archive_are_unknown_options():
    for option in ("--skip-validate", "--skip-archive"):
        verdict = check_launch_options(("rig", "start", option))
        assert verdict.code == "unknown_option", option


def test_resume_force_is_an_unknown_option():
    verdict = check_launch_options(("rig", "resume", "--run-dir", "r1", "--force"))
    assert verdict.code == "unknown_option"
    assert verdict.verb == "resume"


def test_normal_start_and_resume_options_are_accepted():
    assert check_launch_options(("rig", "start", "--run-dir", "r1", "--json")).ok is True
    assert check_launch_options(("rig", "resume", "--run-dir", "r1", "--fresh", "main", "--reason", "x")).ok is True


def test_unknown_verb_is_reported_separately():
    verdict = check_launch_options(("rig", "frobnicate", "--json"))
    assert verdict.ok is False
    assert verdict.code == "unknown_verb"
