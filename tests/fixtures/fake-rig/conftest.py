# -*- coding: utf-8 -*-
"""Self-contained pytest bootstrap for ``tests/fixtures/fake-rig``.

Does **not** depend on ``tests/conftest.py`` or any repo-level pytest config
(D-S7-04).  Installs the F-09 external-IO ban for every test.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from fake_rig import Clock, IdFactory  # noqa: E402
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
