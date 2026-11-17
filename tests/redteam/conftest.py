# -*- coding: utf-8 -*-
"""Self-contained pytest bootstrap for ``tests/redteam``.

Inserts the two fixture directories on ``sys.path`` by absolute path
(00-plan §3.2) and installs the F-09 external-IO ban for every test.
Does **not** modify or import product code.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
WORKFLOW_GROUP = HERE.parents[1]
for candidate in (
    WORKFLOW_GROUP / "tests" / "fixtures" / "supervisor",
    WORKFLOW_GROUP / "tests" / "fixtures" / "fake-rig",
    HERE,
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from fake_rig import Clock, FakeRig, IdFactory  # noqa: E402
from guards import no_external_io  # noqa: E402


@pytest.fixture(autouse=True)
def _forbid_external_io():
    with no_external_io():
        yield


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def ids() -> IdFactory:
    return IdFactory()


@pytest.fixture
def make_runner(tmp_path):
    """Build a scripted FakeRig under ``tmp_path``."""

    def _make(script, *, home=None, clock=None, ids=None) -> FakeRig:
        target = Path(home) if home is not None else tmp_path / "runner-home"
        target.mkdir(parents=True, exist_ok=True)
        return FakeRig(target, script, clock or Clock(), ids or IdFactory(), tmp_root=tmp_path)

    return _make
