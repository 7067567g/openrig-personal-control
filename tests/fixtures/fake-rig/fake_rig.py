# -*- coding: utf-8 -*-
"""F-01 — scripted, offline ``rig`` substitute.

Design constraints (00-plan §4 F-01, D-S7-05):

* no subprocess, no socket, no real home/DB, no model call;
* every call is captured with *two* timestamps (HF-105);
* an unscripted call **never** defaults to ``rc=0`` (HF-055);
* repeated calls must be declared explicitly per step;
* every output carries ``fixture: true`` / ``contractVersion: 1`` / ``id``.

The script is a list of :class:`Step` objects matched by exact ``argv``.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Sequence

from guards import assert_fixture_home, fixture_mark

FIXTURE_ID = "F-01"
ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
REDACT_FLAGS = frozenset({"--token", "--password", "--secret", "--api-key", "--auth"})
REPEAT_MODES = ("consumed", "idempotent", "unscripted")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def format_dt(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime(ISO_FORMAT)


def parse_dt(value: str) -> datetime:
    return datetime.strptime(value, ISO_FORMAT).replace(tzinfo=timezone.utc)


class Clock:
    """Deterministic clock; every :meth:`now` call advances by ``tick``."""

    def __init__(self, start: str = "2026-01-01T00:00:00Z", tick_seconds: float = 1.0) -> None:
        self._current = parse_dt(start)
        self._tick = timedelta(seconds=tick_seconds)

    def now_dt(self) -> datetime:
        moment = self._current
        self._current = self._current + self._tick
        return moment

    def now(self) -> str:
        return format_dt(self.now_dt())

    def peek(self) -> str:
        return format_dt(self._current)

    def advance(self, seconds: float) -> str:
        self._current = self._current + timedelta(seconds=seconds)
        return format_dt(self._current)


class IdFactory:
    """Deterministic id generator (no uuid/random)."""

    def __init__(self, prefix: str = "01FIX", width: int = 4) -> None:
        self.prefix = prefix
        self.width = width
        self._next = 0

    def next(self) -> str:
        value = f"{self.prefix}{self._next:0{self.width}d}"
        self._next += 1
        return value


@dataclass(frozen=True)
class Step:
    """One scripted invocation.

    ``repeat`` is required: a second identical call must never be handled
    implicitly (00-plan F-01 invariant 4).

    * ``consumed``   -> second call: ``rc=2, code="launch_verb_consumed"``
    * ``idempotent`` -> second call replays the same result, ``replayed=True``
    * ``unscripted`` -> second call: ``rc=2, code="fixture_unscripted_call"``

    ``payload`` is serialised to stdout as sorted-key JSON.
    """

    argv: tuple[str, ...]
    repeat: str
    rc: int = 0
    stdout: str = ""
    stderr: str = ""
    code: str | None = None
    stateBefore: str | None = None
    stateAfter: str | None = None
    payload: dict | None = field(default=None, compare=False, hash=False)
    secret: bool = False

    def __post_init__(self) -> None:
        if self.repeat not in REPEAT_MODES:
            raise ValueError(f"repeat must be one of {REPEAT_MODES}, got {self.repeat!r}")

    @classmethod
    def from_command(cls, command: str, *, repeat: str, **kwargs: object) -> "Step":
        return cls(tuple(shlex.split(command)), repeat=repeat, **kwargs)

    def matches(self, argv: Sequence[str]) -> bool:
        return tuple(argv) == self.argv


@dataclass(frozen=True)
class Call:
    """Immutable capture record for one fake invocation."""

    argv: tuple[str, ...]
    cwd: str
    startedAt: str
    endedAt: str
    rc: int
    stdoutSha256: str
    stderrSha256: str
    phase: str | None
    redacted: bool
    code: str | None = None
    provenance: str = "fixture"
    replayed: bool = False
    raw_argv: tuple[str, ...] = ()
    stdout: str = ""
    stderr: str = ""

    def to_dict(self) -> dict:
        return fixture_mark(
            FIXTURE_ID,
            argv=list(self.argv),
            cwd=self.cwd,
            startedAt=self.startedAt,
            endedAt=self.endedAt,
            rc=self.rc,
            code=self.code,
            stdoutSha256=self.stdoutSha256,
            stderrSha256=self.stderrSha256,
            phase=self.phase,
            redacted=self.redacted,
            provenance=self.provenance,
            replayed=self.replayed,
        )


def redact_argv(argv: Sequence[str]) -> tuple[tuple[str, ...], bool]:
    """Redact values that look secret (flags or ``KEY=value``)."""
    out: list[str] = []
    redacted = False
    mask_next = False
    for token in argv:
        if mask_next:
            out.append("***")
            mask_next = False
            redacted = True
            continue
        if token in REDACT_FLAGS:
            out.append(token)
            mask_next = True
            continue
        if "=" in token:
            key, _, _value = token.partition("=")
            if key.upper() in {"TOKEN", "PASSWORD", "SECRET", "API_KEY", "APIKEY", "AUTH"}:
                out.append(f"{key}=***")
                redacted = True
                continue
        out.append(token)
    return tuple(out), redacted


class FakeRig:
    """In-process substitute for the real ``rig`` CLI."""

    def __init__(
        self,
        home: Path,
        script: Iterable[Step],
        clock: Clock,
        ids: IdFactory,
        *,
        tmp_root: Path | None = None,
    ) -> None:
        self.home = assert_fixture_home(home, tmp_root=tmp_root)
        self.script: list[Step] = list(script)
        self.clock = clock
        self.ids = ids
        self._available: list[int] = list(range(len(self.script)))
        self._seen: set[int] = set()
        self._calls: list[Call] = []

    # -- capture ---------------------------------------------------------
    @property
    def calls(self) -> list[Call]:
        return self._calls

    def remaining(self) -> list[Step]:
        return [self.script[i] for i in self._available]

    def _find(self, argv: Sequence[str]) -> int | None:
        for index in self._available:
            if self.script[index].matches(argv):
                return index
        # an idempotent/consumed step may still be known but unavailable
        for index, step in enumerate(self.script):
            if step.matches(argv):
                return index
        return None

    def _record(
        self,
        argv: Sequence[str],
        *,
        cwd: str,
        rc: int,
        stdout: str,
        stderr: str,
        code: str | None,
        phase: str | None,
        redacted: bool,
        raw_argv: Sequence[str],
        replayed: bool = False,
    ) -> Call:
        started = self.clock.now()
        ended = self.clock.now()
        call = Call(
            argv=tuple(argv),
            cwd=cwd,
            startedAt=started,
            endedAt=ended,
            rc=rc,
            stdoutSha256=sha256_text(stdout),
            stderrSha256=sha256_text(stderr),
            phase=phase,
            redacted=redacted,
            code=code,
            replayed=replayed,
            raw_argv=tuple(raw_argv),
            stdout=stdout,
            stderr=stderr,
        )
        self._calls.append(call)
        return call

    @staticmethod
    def _phase(step: Step) -> str | None:
        if step.stateBefore is None and step.stateAfter is None:
            return None
        return f"{step.stateBefore or '?'}->{step.stateAfter or '?'}"

    def run(self, argv: Sequence[str], *, cwd: str) -> Call:
        """Execute one scripted call.  Unknown calls fail closed with rc=2."""
        raw_argv = tuple(argv)
        shown_argv, redacted = redact_argv(raw_argv)
        matched = self._find(raw_argv)

        if matched is None:
            return self._record(
                shown_argv,
                cwd=cwd,
                rc=2,
                stdout="",
                stderr="fixture: call is not scripted; default success is forbidden\n",
                code="fixture_unscripted_call",
                phase=None,
                redacted=redacted,
                raw_argv=raw_argv,
            )

        step = self.script[matched]
        if step.repeat == "idempotent" and matched in self._seen:
            return self._replay(step, shown_argv, cwd, redacted, raw_argv)
        if matched not in self._available:
            if step.repeat == "idempotent":
                return self._replay(step, shown_argv, cwd, redacted, raw_argv)
            if step.repeat == "consumed":
                return self._record(
                    shown_argv,
                    cwd=cwd,
                    rc=2,
                    stdout="",
                    stderr="fixture: launch verb already consumed\n",
                    code="launch_verb_consumed",
                    phase=None,
                    redacted=redacted,
                    raw_argv=raw_argv,
                )
            return self._record(
                shown_argv,
                cwd=cwd,
                rc=2,
                stdout="",
                stderr="fixture: repeated call is not scripted\n",
                code="fixture_unscripted_call",
                phase=None,
                redacted=redacted,
                raw_argv=raw_argv,
            )

        if step.repeat != "idempotent":
            self._available.remove(matched)

        self._seen.add(matched)

        if step.payload is not None:
            stdout = json.dumps(step.payload, sort_keys=True)
        else:
            stdout = step.stdout
        if step.secret:
            shown_argv, redacted = redact_argv(raw_argv)
            redacted = True

        return self._record(
            shown_argv,
            cwd=cwd,
            rc=step.rc,
            stdout=stdout,
            stderr=step.stderr,
            code=step.code,
            phase=self._phase(step),
            redacted=redacted,
            raw_argv=raw_argv,
        )

    def _replay(
        self,
        step: Step,
        argv: Sequence[str],
        cwd: str,
        redacted: bool,
        raw_argv: Sequence[str],
    ) -> Call:
        stdout = json.dumps(step.payload, sort_keys=True) if step.payload is not None else step.stdout
        return self._record(
            argv,
            cwd=cwd,
            rc=step.rc,
            stdout=stdout,
            stderr=step.stderr,
            code=step.code,
            phase=self._phase(step),
            redacted=redacted or step.secret,
            raw_argv=raw_argv,
            replayed=True,
        )

    # -- provenance-free helper -----------------------------------------
    def run_json(self, argv: Sequence[str], *, cwd: str) -> tuple[Call, dict | None]:
        call = self.run(argv, cwd=cwd)
        try:
            parsed = json.loads(call.stdout) if call.stdout else None
        except json.JSONDecodeError:
            parsed = None
        return call, parsed


# ---------------------------------------------------------------------------
# F-09/RT-02 companion: ``--allow-direct`` pre-parse (BOUNDARY §5)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LaunchArgv:
    argv: tuple[str, ...]
    allow_override: bool
    override_source: str | None
    audit: dict | None


def strip_allow_override(
    argv: Sequence[str],
    *,
    env: dict | None = None,
    uid: int | None = None,
    pid: int | None = None,
) -> LaunchArgv:
    """Strip ``--allow-direct`` only *before* the subcommand.

    * ``rig --allow-direct up`` -> stripped, audit written
    * ``rig up --allow-direct`` -> untouched (not an override channel)
    * ``rig up -- --allow-direct`` -> untouched (``--`` boundary)
    * ``OPENRIG_ALLOW_DIRECT=1`` -> override recorded, argv untouched
    """
    env = env or {}
    tokens = list(argv)
    kept: list[str] = []
    override = False
    source: str | None = None
    scanning = True
    for index, token in enumerate(tokens):
        if index == 0:  # program name
            kept.append(token)
            continue
        if not scanning:
            kept.append(token)
            continue
        if token == "--":
            scanning = False
            kept.append(token)
            continue
        if token == "--allow-direct":
            override = True
            source = "argv"
            continue
        if token.startswith("-"):
            kept.append(token)
            continue
        scanning = False  # first positional = subcommand
        kept.append(token)

    if env.get("OPENRIG_ALLOW_DIRECT") in {"1", "true", "TRUE", "yes"}:
        override = True
        source = source or "env"

    audit = None
    if override:
        verb = kept[1] if len(kept) > 1 else None
        audit = {
            "event": "allow_override",
            "uid": uid if uid is not None else os.getuid(),
            "pid": pid if pid is not None else os.getpid(),
            "verb": verb,
            "source": source,
            "argvPrefix": kept[:8],
        }
    return LaunchArgv(tuple(kept), override, source, audit)


# ---------------------------------------------------------------------------
# RT-03/RT-04 companion: option validator (CONTRACT §2)
# ---------------------------------------------------------------------------

KNOWN_VERBS = frozenset(
    {"check", "start", "resume", "status", "stop", "next", "up", "down", "daemon", "workflow", "seat"}
)
GLOBAL_OPTIONS = frozenset({"--json", "--allow-direct"})
ALLOWED_OPTIONS = {
    "check": frozenset({"--run-dir", "--strict-render", "--allow-daemon-down"}),
    "start": frozenset({"--run-dir", "--allow-not-ready"}),
    "resume": frozenset({"--run-dir", "--fresh", "--reason"}),
    "status": frozenset({"--run-dir"}),
    "stop": frozenset({"--run-dir"}),
    "next": frozenset({"--run-dir"}),
    "up": frozenset({"--cwd", "--non-interruptive", "--yes", "--existing", "--fresh", "--host"}),
    "down": frozenset(),
    "daemon": frozenset({"--no-kernel", "--port", "--home"}),
    "workflow": frozenset({"--rig", "--root-objective", "--created-by", "--spec"}),
    "seat": frozenset({"--source", "--reason", "--operator", "--dry-run"}),
}


@dataclass(frozen=True)
class OptionVerdict:
    ok: bool
    code: str | None = None
    verb: str | None = None
    unknown: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return fixture_mark(
            FIXTURE_ID,
            ok=self.ok,
            code=self.code,
            verb=self.verb,
            unknown=list(self.unknown),
        )


def check_launch_options(argv: Sequence[str]) -> OptionVerdict:
    """Reject unknown verb/options (``start --resume``, ``--skip-validate``…).

    This is a real parser, not a scripted rc=2: an option must be in the
    verb's allow-list or in ``GLOBAL_OPTIONS``.  ``--allow-direct`` is expected
    to have been stripped by :func:`strip_allow_override` first, but accepting
    it here keeps the two seams composable.
    """
    tokens = list(argv)
    verb: str | None = None
    options: list[str] = []
    for token in tokens[1:]:
        if verb is None and not token.startswith("-") and token in KNOWN_VERBS:
            verb = token
            continue
        if token.startswith("--"):
            options.append(token)

    if verb is None:
        unknown_verb = next((t for t in tokens[1:] if not t.startswith("-")), None)
        return OptionVerdict(False, "unknown_verb", unknown_verb, ())

    allowed = GLOBAL_OPTIONS | ALLOWED_OPTIONS.get(verb, frozenset())
    unknown = tuple(option for option in options if option not in allowed)
    if unknown:
        return OptionVerdict(False, "unknown_option", verb, unknown)
    return OptionVerdict(True, None, verb, ())
