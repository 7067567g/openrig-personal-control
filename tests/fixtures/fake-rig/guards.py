# -*- coding: utf-8 -*-
"""F-09 — external-IO prohibition and fixture-home validation.

This module is intentionally duplicated (byte-identical) in
``tests/fixtures/fake-rig/guards.py`` and ``tests/fixtures/supervisor/guards.py``
so that either fixture directory is self-contained and no shared
``tests/fixtures/conftest.py`` is needed (D-S7-04).  The two paths are inserted
on ``sys.path`` by their own ``conftest.py``; identical content makes an import
name collision harmless.

Every fixture output must carry ``{"fixture": true, "contractVersion": 1,
"id": "F-xx"}`` (00-plan §4).  ``fixture_mark`` is the single constructor.
"""

from __future__ import annotations

import http.client
import os
import socket
import subprocess
import tempfile
import urllib.request
from contextlib import contextmanager
from pathlib import Path

CONTRACT_VERSION = 1
FIXTURE_ID = "F-09"

BLOCKED_TARGETS = (
    "socket.socket.connect",
    "subprocess.Popen",
    "subprocess.run",
    "os.system",
    "urllib.request.urlopen",
    "http.client.HTTPConnection",
)


class ExternalIOForbidden(RuntimeError):
    """Raised when fixture code attempts network/process external IO."""


class FixtureEscape(RuntimeError):
    """Raised when a fixture points at a real OpenRig home or database."""

    def __init__(self, reason: str, path: object | None = None) -> None:
        self.reason = reason
        self.path = str(path) if path is not None else None
        super().__init__(f"FixtureEscape({reason}): {self.path}")


def fixture_mark(fid: str, **payload: object) -> dict:
    """Build a marked fixture payload."""
    out: dict = {"fixture": True, "contractVersion": CONTRACT_VERSION, "id": fid}
    out.update(payload)
    return out


def is_fixture(payload: object) -> bool:
    """True when *payload* self-identifies as a fixture object."""
    return (
        isinstance(payload, dict)
        and payload.get("fixture") is True
        and payload.get("contractVersion") == CONTRACT_VERSION
        and isinstance(payload.get("id"), str)
    )


def _deny(name: str):
    def _blocked(*_args: object, **_kwargs: object) -> None:
        raise ExternalIOForbidden(f"{name} is forbidden inside fixtures")

    _blocked.__name__ = "forbidden_" + name.replace(".", "_")
    return _blocked


@contextmanager
def no_external_io():
    """Install the F-09 ban for the duration of the block (restores on exit)."""
    patches = (
        (socket.socket, "connect"),
        (subprocess, "Popen"),
        (subprocess, "run"),
        (os, "system"),
        (urllib.request, "urlopen"),
        (http.client, "HTTPConnection"),
    )
    saved = [(obj, attr, getattr(obj, attr)) for obj, attr in patches]
    try:
        for obj, attr in patches:
            setattr(obj, attr, _deny(f"{obj.__name__}.{attr}"))
        yield
    finally:
        for obj, attr, original in reversed(saved):
            setattr(obj, attr, original)


def _resolved(path: object) -> Path:
    candidate = Path(os.fspath(path)).expanduser()
    try:
        return candidate.resolve()
    except OSError:  # pragma: no cover - platform dependent
        return Path(os.path.abspath(str(candidate)))


def assert_fixture_home(path: object, *, tmp_root: object | None = None) -> Path:
    """Validate that *path* is a disposable fixture home.

    Refuses (``FixtureEscape``, never a warning):

    * the real ``$OPENRIG_HOME``;
    * any directory that already contains ``openrig.sqlite``;
    * any path outside the temporary root.
    """
    resolved = _resolved(path)
    real_home = os.environ.get("OPENRIG_HOME")
    if real_home and _resolved(real_home) == resolved:
        raise FixtureEscape("real_openrig_home", resolved)
    if (resolved / "openrig.sqlite").exists():
        raise FixtureEscape("contains_openrig_sqlite", resolved)
    root = _resolved(tmp_root) if tmp_root is not None else _resolved(tempfile.gettempdir())
    if resolved != root and root not in resolved.parents:
        raise FixtureEscape("outside_tmp_root", resolved)
    return resolved


# Backwards-friendly alias used by some tests.
assert_fixture_path = assert_fixture_home
