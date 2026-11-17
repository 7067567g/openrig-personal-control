# -*- coding: utf-8 -*-
"""F-08 self-tests: QA W5 / FINAL R2 acceptance parsing and 68/68 recount."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from acceptance import AcceptanceCase, ShapeError, normalize_cmd, parse, parse_one, verify_tree
from guards import is_fixture

S6_TREE = (
    Path(__file__).resolve().parents[3]
    / "runs"
    / "openrig-completion-round-20261116"
    / "reports"
    / "EXECUTION-TREE-v2.json"
)


def test_plain_row():
    case = parse_one("python3 -c \"assert 1\" | expect rc=0", 1)
    assert case.cmd == 'python3 -c "assert 1"'
    assert case.expect_rc == 0
    assert case.expect_code is None
    assert case.level == "unspecified"
    assert case.id == "cmd-001"


def test_four_part_row():
    case = parse_one("AT-DESIGN-X-01 | static | python3 -c \"assert 1\" | expect rc=0", 7)
    assert case.id == "AT-DESIGN-X-01"
    assert case.level == "static"
    assert case.cmd == 'python3 -c "assert 1"'
    assert case.line == 7


def test_row_with_code():
    case = parse_one(
        "AT-CERT-02 | live | openrig-run stop --run-dir <fixture> --json | expect rc=2 code=archive_incomplete",
        3,
    )
    assert case.expect_rc == 2
    assert case.expect_code == "archive_incomplete"


def test_pipes_inside_command_are_preserved():
    case = parse_one(
        "AT-COVERAGE-01 | static | python3 gate.py --json | python3 -c 'import json,sys' | expect rc=0",
        1,
    )
    assert case.cmd == "python3 gate.py --json | python3 -c 'import json,sys'"
    assert case.level == "static"


def test_missing_expect_is_a_shape_error_with_line_number():
    with pytest.raises(ShapeError) as excinfo:
        parse_one("AT-X-01 | static | python3 -c 1", 4)
    assert excinfo.value.line == 4
    assert "shape" in excinfo.value.reason


def test_at_id_without_level_is_rejected_not_read_as_command():
    with pytest.raises(ShapeError) as excinfo:
        parse_one("AT-X-01 | python3 -c 1 | expect rc=0", 1)
    assert "level" in excinfo.value.reason


def test_non_numeric_rc_is_rejected():
    with pytest.raises(ShapeError):
        parse_one("AT-X-01 | static | cmd | expect rc=two", 1)


def test_empty_code_is_rejected():
    with pytest.raises(ShapeError):
        parse_one("AT-X-01 | static | cmd | expect rc=2 code=", 1)


def test_trailing_pipe_is_rejected():
    with pytest.raises(ShapeError):
        parse_one("AT-X-01 | static | cmd | expect rc=0 |", 1)


def test_parse_tracks_one_based_lines():
    cases = parse(["cmd-a | expect rc=0", "AT-B | live | cmd-b | expect rc=2 code=x"])
    assert [case.line for case in cases] == [1, 2]
    assert isinstance(cases[0], AcceptanceCase)


def test_normalize_cmd_handles_both_cwd_conventions():
    assert normalize_cmd("workflow-group/tests/redteam -q") == "tests/redteam -q"
    assert normalize_cmd("tests/redteam -q") == "tests/redteam -q"


def test_acceptance_payload_is_marked():
    payload = parse_one("cmd | expect rc=0", 1).to_dict()
    assert is_fixture(payload)
    assert payload["expect_rc"] == 0


def test_verify_tree_recounts_the_s6_tree_68_of_68():
    if not S6_TREE.is_file():
        pytest.skip(f"S6 tree missing on disk: {S6_TREE}")
    tree = json.loads(S6_TREE.read_text(encoding="utf-8"))
    report = verify_tree(tree)
    assert report.total == 68
    assert report.parsed == 68
    assert report.unresolved == 0
    assert report.ok is True
    codes = [case for case in report.cases if case.expect_code]
    assert {case.expect_code for case in codes} == {"archive_incomplete", "continuity_blocked"}


def test_verify_tree_reports_unresolved_rows():
    tree = {
        "nodes": [
            {"acceptance_cmds": ["cmd-a | expect rc=0"]},
            {"acceptance_cmds": ["this row has no expectation"]},
        ]
    }
    report = verify_tree(tree)
    assert report.total == 2
    assert report.parsed == 1
    assert report.unresolved == 1
    assert report.ok is False
    assert report.shapeErrors[0]["line"] == 2


def test_verify_tree_fails_closed_without_nodes():
    report = verify_tree({})
    assert report.ok is False
    assert report.total == 0
    assert report.shapeErrors


def test_verify_tree_counts_levels():
    tree = {
        "nodes": [
            {"acceptance_cmds": ["AT-A | static | cmd | expect rc=0"]},
            {"acceptance_cmds": ["AT-B | live | cmd2 | expect rc=2 code=x"]},
        ]
    }
    report = verify_tree(tree)
    assert report.levelCounts == {"live": 1, "static": 1}
    assert report.ok is True
