# -*- coding: utf-8 -*-
"""RT-28 — a fake must never silently become the real thing.

The fixture home is rejected when it is the real ``$OPENRIG_HOME``, when it
contains ``openrig.sqlite``, or when it is outside the disposable temp root.
The F-09 external-IO ban is also asserted directly.
"""

from __future__ import annotations

import subprocess

import pytest

from fake_rig import Clock, FakeRig, IdFactory, Step
from guards import ExternalIOForbidden, FixtureEscape


def test_rt28_home_with_openrig_sqlite_is_rejected(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "openrig.sqlite").write_bytes(b"not a real db")
    with pytest.raises(FixtureEscape) as excinfo:
        FakeRig(home, [], Clock(), IdFactory(), tmp_root=tmp_path)
    assert excinfo.value.reason == "contains_openrig_sqlite"


def test_rt28_real_openrig_home_is_rejected(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("OPENRIG_HOME", str(home))
    with pytest.raises(FixtureEscape) as excinfo:
        FakeRig(home, [], Clock(), IdFactory(), tmp_root=tmp_path)
    assert excinfo.value.reason == "real_openrig_home"


def test_rt28_home_outside_tmp_root_is_rejected(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(FixtureEscape) as excinfo:
        FakeRig(outside, [], Clock(), IdFactory(), tmp_root=allowed)
    assert excinfo.value.reason == "outside_tmp_root"


def test_rt28_control_plain_tmp_path_runs_the_script(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    rig = FakeRig(
        home,
        [Step(argv=("rig", "status"), repeat="consumed", rc=0)],
        Clock(),
        IdFactory(),
        tmp_root=tmp_path,
    )
    call = rig.run(("rig", "status"), cwd=str(tmp_path))
    assert call.rc == 0
    assert call.provenance == "fixture"
    assert len(rig.calls) == 1


def test_rt28_external_io_ban_is_active_in_this_suite():
    with pytest.raises(ExternalIOForbidden):
        subprocess.run(["true"], check=False)
    with pytest.raises(ExternalIOForbidden):
        __import__("socket").socket().connect(("127.0.0.1", 9))


def test_rt28_control_nested_ban_restores_the_outer_ban():
    assert subprocess.run.__name__.startswith("forbidden_")
    from guards import no_external_io

    with no_external_io():
        pass
    with pytest.raises(ExternalIOForbidden):
        subprocess.run(["true"], check=False)
