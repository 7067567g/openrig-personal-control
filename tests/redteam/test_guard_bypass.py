# -*- coding: utf-8 -*-
"""RT-01..RT-04 — lifecycle guard bypass and option-shape bypass.

Every negative asserts rc + code (or a typed violation) and a paired control.
The option parser is a real allow-list parser, not a scripted rc=2.
"""

from __future__ import annotations

from fake_rig import OptionVerdict, check_launch_options, strip_allow_override
from supervisor_sim import authorize_direct, detect_context

from helpers import context


def _rc(verdict: OptionVerdict) -> int:
    """Contract projection: an option rejection is rc=2; acceptance is rc=0."""
    return 0 if verdict.ok else 2


# ---------------------------------------------------------------------------
# RT-01 — S1 managed run: raw lifecycle verbs are denied
# ---------------------------------------------------------------------------

def test_rt01_s1_direct_lifecycle_verb_is_denied(tmp_path):
    ctx = context(tmp_path)
    verdict = detect_context(ctx.run_dir)
    assert verdict.tier == "S1"
    assert verdict.marker is not None

    audit: list[dict] = []
    result = authorize_direct(verdict, "up", audit)
    assert result.ok is False
    assert result.rc == 2
    assert result.code == "lifecycle_not_authorized"
    assert audit == [{"event": "deny_lifecycle_verb", "verb": "up", "tier": "S1"}]


def test_rt01_control_s2_legacy_home_warns_not_denies(tmp_path):
    base = tmp_path / "s2"
    ctx = context(
        base,
        write_marker=False,
        home=base / "openrig-workflow-legacy",
    )
    verdict = detect_context(ctx.run_dir)
    assert verdict.tier == "S2"
    assert verdict.marker is None

    audit: list[dict] = []
    result = authorize_direct(verdict, "up", audit)
    assert result.ok is True
    assert result.rc == 0
    assert result.code is None
    assert result.warning == "legacy_home_warning"
    assert audit == [{"event": "allow_direct_warn", "verb": "up", "tier": "S2"}]


def test_rt01_control_unmanaged_is_not_denied(tmp_path):
    base = tmp_path / "unmanaged"
    ctx = context(base, write_marker=False)
    verdict = detect_context(ctx.run_dir)
    assert verdict.tier == "unmanaged"
    result = authorize_direct(verdict, "up")
    assert result.ok is True
    assert result.rc == 0


# ---------------------------------------------------------------------------
# RT-02 — --allow-direct position: only before the subcommand is stripped
# ---------------------------------------------------------------------------

def test_rt02_allow_direct_before_subcommand_is_stripped_and_audited():
    parsed = strip_allow_override(("rig", "--allow-direct", "up", "spec.yaml"), uid=1000, pid=42)
    assert parsed.argv == ("rig", "up", "spec.yaml")
    assert parsed.allow_override is True
    assert parsed.override_source == "argv"
    assert parsed.audit is not None
    assert parsed.audit["event"] == "allow_override"
    assert parsed.audit["verb"] == "up"


def test_rt02_allow_direct_after_subcommand_is_not_stripped():
    parsed = strip_allow_override(("rig", "up", "--allow-direct"), uid=1, pid=1)
    assert parsed.argv == ("rig", "up", "--allow-direct")
    assert parsed.allow_override is False
    assert parsed.audit is None


def test_rt02_allow_direct_after_double_dash_is_not_stripped():
    parsed = strip_allow_override(("rig", "up", "--", "--allow-direct"), uid=1, pid=1)
    assert parsed.argv == ("rig", "up", "--", "--allow-direct")
    assert parsed.allow_override is False
    assert parsed.audit is None


def test_rt02_control_plain_rig_up_has_no_override_record():
    parsed = strip_allow_override(("rig", "up", "spec.yaml"), uid=1, pid=1)
    assert parsed.argv == ("rig", "up", "spec.yaml")
    assert parsed.allow_override is False
    assert parsed.audit is None


# ---------------------------------------------------------------------------
# RT-03 — start --resume is not a verb
# ---------------------------------------------------------------------------

def test_rt03_start_resume_is_unknown_option():
    verdict = check_launch_options(("rig", "start", "--run-dir", "r1", "--resume"))
    assert _rc(verdict) == 2
    assert verdict.ok is False
    assert verdict.code == "unknown_option"
    assert verdict.verb == "start"
    assert "--resume" in verdict.unknown


def test_rt03_control_plain_start_is_accepted():
    verdict = check_launch_options(("rig", "start", "--run-dir", "r1", "--json"))
    assert _rc(verdict) == 0
    assert verdict.ok is True
    assert verdict.code is None


# ---------------------------------------------------------------------------
# RT-04 — skip/force flags do not exist
# ---------------------------------------------------------------------------

def test_rt04_skip_validate_skip_archive_are_unknown_options():
    for option in ("--skip-validate", "--skip-archive"):
        verdict = check_launch_options(("rig", "start", option))
        assert _rc(verdict) == 2, option
        assert verdict.code == "unknown_option", option
        assert option in verdict.unknown


def test_rt04_resume_force_is_an_unknown_option():
    verdict = check_launch_options(("rig", "resume", "--run-dir", "r1", "--force"))
    assert _rc(verdict) == 2
    assert verdict.code == "unknown_option"
    assert verdict.verb == "resume"


def test_rt04_control_normal_resume_flags_are_accepted():
    verdict = check_launch_options(
        ("rig", "resume", "--run-dir", "r1", "--fresh", "main", "--reason", "x")
    )
    assert _rc(verdict) == 0
    assert verdict.ok is True


def test_rt04_unknown_verb_is_reported_separately():
    verdict = check_launch_options(("rig", "frobnicate", "--json"))
    assert _rc(verdict) == 2
    assert verdict.code == "unknown_verb"
