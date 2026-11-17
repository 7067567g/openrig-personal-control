# -*- coding: utf-8 -*-
"""F-08 — acceptance-command parsing and tree coverage (QA W5 / FINAL R2).

Accepted shapes::

    <cmd> | expect rc=0
    AT-... | static | <cmd> | expect rc=0
    AT-... | live   | <cmd> | expect rc=2 code=archive_incomplete

Pipes inside ``<cmd>`` are preserved.  Anything else raises ``ShapeError``
with a 1-based line number: a silently skipped row would report a fake 68/68.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable

from guards import fixture_mark

FIXTURE_ID = "F-08"

ROW_RE = re.compile(
    r"^(?:(?P<id>AT-[A-Za-z0-9_.-]+)\s*\|\s*(?P<level>[A-Za-z][A-Za-z0-9_.-]*)\s*\|\s*)?"
    r"(?P<cmd>.+?)\s*\|\s*expect\s+rc=(?P<rc>\d+)"
    r"(?:\s+code=(?P<code>[A-Za-z0-9_.:-]+))?\s*$"
)
EXPECT_RE = re.compile(r"\|\s*expect\b")
REPO_PREFIX = "workflow-group/"


class ShapeError(ValueError):
    def __init__(self, line: int, raw: str, reason: str) -> None:
        self.line = line
        self.raw = raw
        self.reason = reason
        super().__init__(f"line {line}: {reason}: {raw!r}")

    def to_dict(self) -> dict:
        return {"line": self.line, "raw": self.raw, "reason": self.reason}


@dataclass(frozen=True)
class AcceptanceCase:
    line: int
    cmd: str
    expect_rc: int
    expect_code: str | None
    level: str = "unspecified"
    id: str = ""
    raw: str = ""

    def to_dict(self) -> dict:
        return fixture_mark(
            FIXTURE_ID,
            line=self.line,
            id=self.id,
            level=self.level,
            cmd=self.cmd,
            expect_rc=self.expect_rc,
            expect_code=self.expect_code,
        )


def normalize_cmd(cmd: str) -> str:
    """Normalise the two cwd conventions used by BRIEF and the S6 tree."""
    text = cmd.strip()
    if text.startswith(REPO_PREFIX):
        return text[len(REPO_PREFIX) :]
    return text


def parse_one(row: str, line: int) -> AcceptanceCase:
    if not isinstance(row, str):
        raise ShapeError(line, repr(row), "row is not a string")
    match = ROW_RE.match(row.strip())
    if not match:
        raise ShapeError(line, row, "unrecognised acceptance row shape")

    cmd = match.group("cmd").strip()
    if not cmd:
        raise ShapeError(line, row, "empty command")
    if cmd.startswith("AT-"):
        # an AT id without a level must not be silently read as a command
        raise ShapeError(line, row, "AT id present but level segment is missing")
    rc_text = match.group("rc")
    expect_code = match.group("code")
    return AcceptanceCase(
        line=line,
        cmd=normalize_cmd(cmd),
        expect_rc=int(rc_text),
        expect_code=expect_code,
        level=match.group("level") or "unspecified",
        id=match.group("id") or f"cmd-{line:03d}",
        raw=row,
    )


def parse(rows: Iterable[str]) -> list[AcceptanceCase]:
    cases: list[AcceptanceCase] = []
    for line, row in enumerate(rows, start=1):
        cases.append(parse_one(row, line))
    return cases


@dataclass
class TreeReport:
    total: int
    parsed: int
    shapeErrors: list[dict] = field(default_factory=list)
    levelCounts: dict = field(default_factory=dict)
    ok: bool = False
    cases: list[AcceptanceCase] = field(default_factory=list)

    @property
    def unresolved(self) -> int:
        return len(self.shapeErrors)

    def to_dict(self) -> dict:
        return fixture_mark(
            FIXTURE_ID,
            total=self.total,
            parsed=self.parsed,
            unresolved=self.unresolved,
            shapeErrors=list(self.shapeErrors),
            levelCounts=dict(self.levelCounts),
            ok=self.ok,
        )


def verify_tree(tree: dict) -> TreeReport:
    """Recount every ``acceptance_cmds`` row in an EXECUTION-TREE document."""
    nodes = tree.get("nodes") if isinstance(tree, dict) else None
    if not isinstance(nodes, list):
        return TreeReport(
            total=0,
            parsed=0,
            shapeErrors=[{"line": 0, "raw": "", "reason": "tree has no nodes[]"}],
            levelCounts={},
            ok=False,
        )

    rows: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            rows.append("")
            continue
        for row in node.get("acceptance_cmds") or []:
            rows.append(row)

    cases: list[AcceptanceCase] = []
    errors: list[dict] = []
    for line, row in enumerate(rows, start=1):
        try:
            cases.append(parse_one(row, line))
        except ShapeError as exc:
            errors.append(exc.to_dict())

    counts = Counter(case.level for case in cases)
    return TreeReport(
        total=len(rows),
        parsed=len(cases),
        shapeErrors=errors,
        levelCounts=dict(sorted(counts.items())),
        ok=bool(rows) and len(cases) == len(rows) and not errors,
        cases=cases,
    )
