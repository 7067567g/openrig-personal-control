# -*- coding: utf-8 -*-
"""Self-contained pytest bootstrap for ``tests/fixtures/supervisor``.

Does **not** depend on ``tests/conftest.py`` or repo-level pytest config
(D-S7-04).  Adds this directory and the sibling ``fake-rig`` directory to
``sys.path`` (absolute, derived from ``__file__``) and installs the F-09
external-IO ban for every test.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
FAKE_RIG = HERE.parent / "fake-rig"
for candidate in (HERE, FAKE_RIG):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from fake_rig import Clock, FakeRig, IdFactory, Step  # noqa: E402
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
    """Build a scripted FakeRig under tmp_path."""

    def _make(script, *, clock=None, ids=None) -> FakeRig:
        home = tmp_path / "runner-home"
        home.mkdir(exist_ok=True)
        return FakeRig(home, script, clock or Clock(), ids or IdFactory(), tmp_root=tmp_path)

    return _make


@pytest.fixture
def step():
    """Small helper: build a Step by command line."""
    return Step.from_command
