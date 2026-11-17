#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for workflow-group/scripts/wf_close_lint.py.

Run with:
    python3 workflow-group/tests/test_wf_close_lint.py

Uses only the Python standard library (unittest/tempfile/zipfile/xml).
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

sys.dont_write_bytecode = True

TEST_PATH = Path(__file__).resolve()
WORKFLOW_GROUP = TEST_PATH.parents[1]
MODULE_PATH = WORKFLOW_GROUP / "scripts" / "wf_close_lint.py"

spec = importlib.util.spec_from_file_location("wf_close_lint", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot import {MODULE_PATH}")
close_lint = importlib.util.module_from_spec(spec)
sys.modules["wf_close_lint"] = close_lint
spec.loader.exec_module(close_lint)


HEADERS = [
    "ID",
    "轮次",
    "类型",
    "标题",
    "描述",
    "严重度",
    "状态",
    "责任角色",
    "来源",
    "建议动作",
    "需主会话决策",
    "关联决策ID",
    "创建时间",
    "更新时间",
]


def _col_name(index: int) -> str:
    result = ""
    n = index + 1
    while n:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result


def write_inline_xlsx(path: Path, rows) -> None:
    """Write a minimal one-sheet xlsx using inline strings only."""
    sheet_rows = []
    for row_index, values in enumerate(rows, start=1):
        cells = []
        for col_index, value in enumerate(values):
            ref = f"{_col_name(col_index)}{row_index}"
            cells.append(
                f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
            )
        sheet_rows.append(f'<row r="{row_index}">' + "".join(cells) + "</row>")

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>" + "".join(sheet_rows) + "</sheetData></worksheet>"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def write_shared_strings_xlsx(path: Path, rows) -> None:
    """Write a minimal xlsx whose text cells use sharedStrings.xml."""
    shared = []
    sheet_rows = []
    for row_index, values in enumerate(rows, start=1):
        cells = []
        for col_index, value in enumerate(values):
            text = str(value)
            try:
                shared_index = shared.index(text)
            except ValueError:
                shared_index = len(shared)
                shared.append(text)
            ref = f"{_col_name(col_index)}{row_index}"
            cells.append(f'<c r="{ref}" t="s"><v>{shared_index}</v></c>')
        sheet_rows.append(f'<row r="{row_index}">' + "".join(cells) + "</row>")

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>" + "".join(sheet_rows) + "</sheetData></worksheet>"
    )
    shared_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'count="{len(shared)}" uniqueCount="{len(shared)}">'
        + "".join(f"<si><t>{escape(text)}</t></si>" for text in shared)
        + "</sst>"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        archive.writestr("xl/sharedStrings.xml", shared_xml)


def workflow_doc(run_id: str, doc: str, state: str, *, omit: str | None = None) -> str:
    fields = {
        "run": run_id,
        "round": "1",
        "doc": doc,
        "owner": "PMO",
        "state": state,
        "updated": "2026-11-11",
    }
    if omit:
        fields.pop(omit, None)
    header = "\n".join(f"{key}: {value}" for key, value in fields.items())
    return f"<!-- wf-doc\n{header}\n-->\n\n"


def project_text(run_id: str, state: str = "closed", *, omit_header_field: str | None = None) -> str:
    return workflow_doc(run_id, "PROJECT", state, omit=omit_header_field) + f"""# PROJECT — {run_id}

## 1. 目标与成功判据

- **G1**：test goal
  - 判据：test evidence

## 6. PMO 上报区

- **本轮结论**：完成。
- **残余风险/承接**：owner=MAIN；去向=runs/{run_id}/reports/final.md；最晚复核轮=R1。
"""


def decisions_text(run_id: str, *, terminal: bool = True) -> str:
    status = "达成" if terminal else "生效"
    return workflow_doc(run_id, "DECISIONS", "closed") + f"""# DECISIONS — {run_id}

## 1. 决策账本

### D-001（Round 1）测试决策

- **决策**：test decision
- **状态**：{status}
"""


def status_text(
    run_id: str,
    state: str = "qa-done",
    progress_status: str = "完成",
    *,
    omit_header_field: str | None = None,
) -> str:
    return workflow_doc(run_id, "STATUS", state, omit=omit_header_field) + f"""# STATUS · Round 1 — {run_id}

## 进度条目

<!-- wf:progress:start -->
| 时间 | 执行体 | WS | 动作 | 产出/证据 | 状态 |
| --- | --- | --- | --- | --- | --- |
| 2026-11-11 10:00 | tdo-a1 | WS-1 | test | reports/test.txt | {progress_status} |
<!-- wf:progress:end -->
"""


def issue_row(
    issue_id: str = "P-001",
    severity: str = "S3",
    status: str = "已关闭",
    decision_id: str = "D-001",
) -> list:
    return [
        issue_id,
        "1",
        "问题",
        "test issue",
        "test description",
        severity,
        status,
        "PMO",
        "reports/test.txt",
        "test action",
        "否",
        decision_id,
        "2026-11-11 10:00",
        "2026-11-11 10:00",
    ]


class CloseLintTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.runs_root = Path(self.tmp.name) / "runs"
        self.runs_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def make_run(
        self,
        run_id: str,
        *,
        project_state: str = "closed",
        issue_rows=None,
        status_state: str = "qa-done",
        progress_status: str = "完成",
        terminal_decision: bool = True,
    ) -> Path:
        run_dir = self.runs_root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "PROJECT.md").write_text(
            project_text(run_id, project_state), encoding="utf-8"
        )
        (run_dir / "DECISIONS.md").write_text(
            decisions_text(run_id, terminal=terminal_decision), encoding="utf-8"
        )
        (run_dir / "STATUS-Round-1.md").write_text(
            status_text(run_id, status_state, progress_status), encoding="utf-8"
        )
        rows = [HEADERS]
        if issue_rows:
            rows.extend(issue_rows)
        write_inline_xlsx(run_dir / "ISSUES.xlsx", rows)
        return run_dir

    def codes(self, report):
        return [finding.code for finding in report.findings]

    def _add_budget_header(self, path: Path, family: str) -> None:
        text = path.read_text(encoding="utf-8")
        if "doc_budget:" not in text:
            text = text.replace(
                "updated: 2026-11-11\n-->",
                f"updated: 2026-11-11\ndoc_budget: {family}\n-->",
                1,
            )
        path.write_text(text, encoding="utf-8")

    def _make_budget_run(self, run_id: str) -> Path:
        run_dir = self.make_run(run_id)
        (run_dir / ".run-meta.json").write_text(
            json.dumps({"runId": run_id, "docBudgetPolicy": "DOC-BUDGET-v1"}),
            encoding="utf-8",
        )
        self._add_budget_header(run_dir / "PROJECT.md", "project")
        self._add_budget_header(run_dir / "DECISIONS.md", "decision")
        self._add_budget_header(run_dir / "STATUS-Round-1.md", "status")
        return run_dir

    def test_doc_budget_valid_run_is_clean(self) -> None:
        run_dir = self._make_budget_run("budget-clean")
        report = close_lint.lint_run(run_dir)
        budget_codes = [c for c in self.codes(report) if c.startswith("doc_budget") or c.startswith("plan_doc")]
        self.assertEqual([], budget_codes)

    def test_doc_budget_missing_canonical_header_is_warning(self) -> None:
        run_dir = self.make_run("budget-missing-header")
        (run_dir / ".run-meta.json").write_text(
            json.dumps({"runId": "budget-missing-header", "docBudgetPolicy": "DOC-BUDGET-v1"}),
            encoding="utf-8",
        )
        report = close_lint.lint_run(run_dir)
        self.assertIn("doc_budget_missing", self.codes(report))
        self.assertEqual(report.error_count, 0)

    def test_doc_budget_over_cap_is_error(self) -> None:
        run_dir = self._make_budget_run("budget-over")
        with (run_dir / "DECISIONS.md").open("a", encoding="utf-8") as handle:
            handle.write("\n" + "x" * 7000 + "\n")
        report = close_lint.lint_run(run_dir)
        self.assertIn("doc_budget_exceeded", self.codes(report))

    def test_doc_budget_exception_allows_soft_over_cap(self) -> None:
        run_dir = self._make_budget_run("budget-exception")
        with (run_dir / "DECISIONS.md").open("a", encoding="utf-8") as handle:
            handle.write("\nbudget_exception: long audit trail\n" + "x" * 7000 + "\n")
        report = close_lint.lint_run(run_dir)
        self.assertNotIn("doc_budget_exceeded", self.codes(report))
        self.assertIn("doc_budget_exception_used", self.codes(report))

    def test_doc_budget_more_than_two_exceptions_is_error(self) -> None:
        run_dir = self._make_budget_run("budget-too-many-exceptions")
        for rel in ("PROJECT.md", "DECISIONS.md", "STATUS-Round-1.md"):
            with (run_dir / rel).open("a", encoding="utf-8") as handle:
                handle.write("\nbudget_exception: reason\n")
        report = close_lint.lint_run(run_dir)
        self.assertIn("doc_budget_exceptions_exceeded", self.codes(report))

    def test_generated_view_over_4kb_is_error(self) -> None:
        run_dir = self._make_budget_run("budget-generated-view")
        reports = run_dir / "reports"
        reports.mkdir(exist_ok=True)
        (reports / "TREE.json").write_text("{}", encoding="utf-8")
        (reports / "EXECUTION-TREE-X.md").write_text(
            "generated-from: reports/TREE.json\n" + "x" * 5000,
            encoding="utf-8",
        )
        report = close_lint.lint_run(run_dir)
        self.assertIn("generated_view_exceeded", self.codes(report))

    def test_generated_tree_without_header_is_warning(self) -> None:
        run_dir = self._make_budget_run("budget-tree-header")
        reports = run_dir / "reports"
        reports.mkdir(exist_ok=True)
        (reports / "EXECUTION-TREE-Y.md").write_text("# tree\n", encoding="utf-8")
        report = close_lint.lint_run(run_dir)
        self.assertIn("generated_view_header_missing", self.codes(report))
        self.assertEqual(report.error_count, 0)

    def test_plan_doc_bytes_missing_is_error(self) -> None:
        run_dir = self._make_budget_run("budget-plan-missing")
        reports = run_dir / "reports"
        reports.mkdir(exist_ok=True)
        (reports / "00-plan.md").write_text("# plan\n", encoding="utf-8")
        report = close_lint.lint_run(run_dir)
        self.assertIn("plan_doc_bytes_missing", self.codes(report))

    def test_normal_closed_run_is_clean(self) -> None:
        run_dir = self.make_run(
            "normal-run",
            issue_rows=[issue_row("P-001", "S2", "已关闭", "D-001")],
        )
        report = close_lint.lint_run(run_dir)
        self.assertEqual(report.error_count, 0)
        self.assertEqual(report.warning_count, 0, [f.code for f in report.findings])
        self.assertTrue(report.ok)

    def test_closed_run_with_new_issue_is_error(self) -> None:
        run_dir = self.make_run(
            "new-issue-run",
            issue_rows=[issue_row("P-001", "S2", "新建", "")],
        )
        report = close_lint.lint_run(run_dir)
        self.assertGreater(report.error_count, 0)
        self.assertIn("closed_has_active_issue", self.codes(report))

    def test_suspended_s1_s2_without_decision_is_error(self) -> None:
        run_dir = self.make_run(
            "suspended-no-decision",
            issue_rows=[issue_row("R-001", "S2", "挂起", "")],
        )
        report = close_lint.lint_run(run_dir)
        self.assertIn("s1_s2_decision_missing", self.codes(report))

    def test_suspended_s1_s2_with_valid_decision_is_accepted(self) -> None:
        run_dir = self.make_run(
            "suspended-valid-decision",
            issue_rows=[issue_row("R-001", "S2", "挂起", "D-001")],
        )
        report = close_lint.lint_run(run_dir)
        self.assertNotIn("s1_s2_decision_missing", self.codes(report))
        self.assertEqual(report.stats["suspended_s1_s2"], 1)

    def test_closed_run_without_terminal_decision_is_error(self) -> None:
        run_dir = self.make_run("no-terminal-decision", terminal_decision=False)
        report = close_lint.lint_run(run_dir)
        self.assertIn("terminal_decision_missing", self.codes(report))

    def test_status_qa_done_with_in_progress_is_error(self) -> None:
        run_dir = self.make_run(
            "status-conflict",
            status_state="qa-done",
            progress_status="进行中",
        )
        report = close_lint.lint_run(run_dir)
        self.assertIn("status_has_unfinished_rows", self.codes(report))
        self.assertEqual(report.stats["status_conflict_files"], 1)

    def test_missing_files_are_errors(self) -> None:
        run_dir = self.runs_root / "missing-files"
        run_dir.mkdir(parents=True)
        (run_dir / "PROJECT.md").write_text(
            project_text("missing-files", "plan-ready"), encoding="utf-8"
        )
        report = close_lint.lint_run(run_dir)
        missing = [f for f in report.findings if f.code == "required_file_missing"]
        self.assertEqual(len(missing), 3)  # DECISIONS, ISSUES, STATUS

    def test_missing_wf_doc_field_is_warning(self) -> None:
        run_dir = self.make_run("missing-doc-field")
        (run_dir / "STATUS-Round-1.md").write_text(
            status_text("missing-doc-field", omit_header_field="owner"), encoding="utf-8"
        )
        report = close_lint.lint_run(run_dir)
        self.assertIn("wf_doc_fields_missing", self.codes(report))
        self.assertEqual(report.error_count, 0)

    def test_malformed_xlsx_is_error_not_crash(self) -> None:
        run_dir = self.make_run("malformed-xlsx")
        (run_dir / "ISSUES.xlsx").write_bytes(b"not a zip file")
        report = close_lint.lint_run(run_dir)
        self.assertIn("issues_ledger_invalid", self.codes(report))

    def test_shared_strings_xlsx_is_supported(self) -> None:
        run_dir = self.make_run("shared-strings")
        write_shared_strings_xlsx(
            run_dir / "ISSUES.xlsx",
            [
                HEADERS,
                issue_row("R-001", "S2", "挂起", "D-001"),
            ],
        )
        report = close_lint.lint_run(run_dir)
        self.assertNotIn("issues_ledger_invalid", self.codes(report))
        self.assertEqual(report.stats["suspended_s1_s2"], 1)

    def test_acceptance_downgrades_only_matching_error(self) -> None:
        run_dir = self.make_run(
            "acceptance-match",
            issue_rows=[issue_row("P-001", "S2", "新建", "")],
        )
        manifest = Path(self.tmp.name) / "acceptances.json"
        manifest.write_text(
            json.dumps(
                [
                    {
                        "run_id": "acceptance-match",
                        "code": "closed_has_active_issue",
                        "issue_id": "P-001",
                        "decision_id": "D-001",
                        "owner": "MAIN",
                        "destination": "runs/acceptance-match/reports/final.md",
                        "review_round": "R2",
                        "reason": "historical residual accepted",
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            rc = close_lint.main(
                [
                    "--run",
                    "acceptance-match",
                    "--runs-root",
                    str(self.runs_root),
                    "--acceptances",
                    str(manifest),
                    "--json",
                ]
            )
        payload = json.loads(buffer.getvalue())
        self.assertEqual(rc, 0)
        self.assertEqual(payload["summary"]["accepted_errors"], 1)
        self.assertEqual(payload["summary"]["unaccepted_errors"], 0)
        self.assertEqual(payload["summary"]["closed_violation_runs"], 0)

    def test_acceptance_does_not_accept_unmatched_issue(self) -> None:
        self.make_run(
            "acceptance-mismatch",
            issue_rows=[issue_row("P-001", "S2", "新建", "")],
        )
        manifest = Path(self.tmp.name) / "acceptances.json"
        manifest.write_text(
            json.dumps(
                [
                    {
                        "run_id": "acceptance-mismatch",
                        "code": "closed_has_active_issue",
                        "issue_id": "P-999",
                        "decision_id": "D-001",
                        "owner": "MAIN",
                        "destination": "runs/acceptance-mismatch/reports/final.md",
                        "review_round": "R2",
                        "reason": "should not match",
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            rc = close_lint.main(
                [
                    "--run",
                    "acceptance-mismatch",
                    "--runs-root",
                    str(self.runs_root),
                    "--acceptances",
                    str(manifest),
                    "--json",
                ]
            )
        payload = json.loads(buffer.getvalue())
        self.assertEqual(rc, 1)
        self.assertEqual(payload["summary"]["accepted_errors"], 0)
        self.assertEqual(payload["summary"]["unaccepted_errors"], 1)

    def test_invalid_acceptance_manifest_is_error(self) -> None:
        self.make_run("invalid-acceptance")
        manifest = Path(self.tmp.name) / "acceptances.json"
        manifest.write_text(
            json.dumps([{"run_id": "invalid-acceptance"}]),
            encoding="utf-8",
        )
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            rc = close_lint.main(
                [
                    "--run",
                    "invalid-acceptance",
                    "--runs-root",
                    str(self.runs_root),
                    "--acceptances",
                    str(manifest),
                    "--json",
                ]
            )
        payload = json.loads(buffer.getvalue())
        self.assertEqual(rc, 1)
        self.assertIn("errors", payload)

    def test_json_cli_contains_summary(self) -> None:
        self.make_run("json-run")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            rc = close_lint.main(
                ["--all", "--runs-root", str(self.runs_root), "--json"]
            )
        payload = json.loads(buffer.getvalue())
        self.assertEqual(rc, 0)
        self.assertEqual(payload["summary"]["runs_scanned"], 1)
        self.assertEqual(payload["summary"]["closed_runs"], 1)
        self.assertIn("closed_violation_runs", payload["summary"])


class StrictCloseTests(unittest.TestCase):
    """R04: --strict requires FINAL.md + closeout manifest + hash/revision chain."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.runs_root = Path(self.tmp.name) / "runs"
        self.runs_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run_dir(self, run_id="strict-run") -> Path:
        rd = self.runs_root / run_id
        rd.mkdir(parents=True, exist_ok=True)
        return rd

    def _entry(self, rd: Path, rel: str, revision: int = 1, **over):
        raw = (rd / rel).read_bytes()
        entry = {
            "path": rel,
            "bytes": len(raw),
            "sha256": close_lint.hashlib.sha256(raw).hexdigest(),
            "command": "pytest -q",
            "rc": 0,
            "revision": revision,
            "reason": "initial closeout",
        }
        entry.update(over)
        return entry

    def _closeout(self, rd: Path, entries, closed_at=None):
        import datetime as _dt

        ev = rd / "reports" / "evidence"
        ev.mkdir(parents=True, exist_ok=True)
        data = {
            "schemaVersion": 1,
            "runId": rd.name,
            "closedAt": closed_at
            or _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "entries": entries,
        }
        (ev / "closeout.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def codes(self, rd: Path):
        return [f.code for f in close_lint.strict_findings(rd, rd.name)]

    def test_missing_final_is_error(self):
        rd = self._run_dir()
        (rd / "notes.md").write_text("x\n", encoding="utf-8")
        self._closeout(rd, [self._entry(rd, "notes.md")])
        self.assertIn("final_missing", self.codes(rd))

    def test_missing_closeout_is_error(self):
        rd = self._run_dir()
        (rd / "FINAL.md").write_text("final\n", encoding="utf-8")
        self.assertIn("closeout_missing", self.codes(rd))

    def test_sha_mismatch_is_error(self):
        rd = self._run_dir()
        (rd / "FINAL.md").write_text("final\n", encoding="utf-8")
        entry = self._entry(rd, "FINAL.md")
        entry["sha256"] = "0" * 64
        self._closeout(rd, [entry])
        self.assertIn("closeout_hash_mismatch", self.codes(rd))

    def test_revision_chain_backwards_is_error(self):
        rd = self._run_dir()
        (rd / "FINAL.md").write_text("final\n", encoding="utf-8")
        broken = self._entry(rd, "FINAL.md", revision=2)  # revision>1 但没有 replacesSha256
        self._closeout(rd, [broken])
        self.assertIn("revision_chain", self.codes(rd))

    def test_revision_zero_is_error(self):
        rd = self._run_dir()
        (rd / "FINAL.md").write_text("final\n", encoding="utf-8")
        self._closeout(rd, [self._entry(rd, "FINAL.md", revision=0)])
        self.assertIn("revision_invalid", self.codes(rd))

    def test_valid_manifest_passes(self):
        rd = self._run_dir()
        (rd / "FINAL.md").write_text("final\n", encoding="utf-8")
        self._closeout(rd, [self._entry(rd, "FINAL.md")])
        self.assertEqual(self.codes(rd), [])

    def test_final_after_closedat_requires_revision_record(self):
        rd = self._run_dir()
        (rd / "FINAL.md").write_text("final v2\n", encoding="utf-8")
        self._closeout(
            rd, [self._entry(rd, "FINAL.md")], closed_at="2020-01-01T00:00:00+00:00"
        )
        self.assertIn("final_after_closeout", self.codes(rd))
        rev_dir = rd / "reports" / "evidence" / "revisions"
        rev_dir.mkdir(parents=True, exist_ok=True)
        raw = (rd / "FINAL.md").read_bytes()
        (rev_dir / "REV-001.json").write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "path": "FINAL.md",
                    "sha256": close_lint.hashlib.sha256(raw).hexdigest(),
                    "revision": 2,
                    "reason": "post-close final edit recorded",
                }
            ),
            encoding="utf-8",
        )
        self.assertNotIn("final_after_closeout", self.codes(rd))

    def test_cli_strict_flag_surfaces_finding(self):
        self._run_dir("strict-cli")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            rc = close_lint.main(
                ["--run", "strict-cli", "--runs-root", str(self.runs_root), "--strict", "--json"]
            )
        payload = json.loads(buffer.getvalue())
        codes = [f["code"] for f in payload["runs"][0]["findings"]]
        self.assertEqual(rc, 1)
        self.assertIn("final_missing", codes)
        self.assertIn("closeout_missing", codes)

    # ---------------------------------------------------------------- R04b
    def test_reports_final_only_passes(self):
        """R04b：FINAL.md 只放在 reports/ 也算到位。"""
        rd = self._run_dir("strict-reports-final")
        (rd / "reports").mkdir(parents=True, exist_ok=True)
        (rd / "reports" / "FINAL.md").write_text("final in reports\n", encoding="utf-8")
        self._closeout(rd, [self._entry(rd, "reports/FINAL.md")])
        self.assertEqual(self.codes(rd), [])
        self.assertEqual(close_lint.resolve_final(rd), rd / "reports" / "FINAL.md")

    def test_root_final_only_passes(self):
        rd = self._run_dir("strict-root-final")
        (rd / "FINAL.md").write_text("final at root\n", encoding="utf-8")
        self._closeout(rd, [self._entry(rd, "FINAL.md")])
        self.assertEqual(self.codes(rd), [])
        self.assertEqual(close_lint.resolve_final(rd), rd / "FINAL.md")

    def test_both_finals_prefers_reports(self):
        """两者都在 → 以 reports/FINAL.md 为准；根 FINAL.md 的 hash 不参与判定。"""
        rd = self._run_dir("strict-both-final")
        (rd / "reports").mkdir(parents=True, exist_ok=True)
        (rd / "reports" / "FINAL.md").write_text("authoritative\n", encoding="utf-8")
        (rd / "FINAL.md").write_text("stale copy\n", encoding="utf-8")
        self._closeout(rd, [self._entry(rd, "reports/FINAL.md")])
        self.assertEqual(self.codes(rd), [])
        self.assertEqual(close_lint.resolve_final(rd), rd / "reports" / "FINAL.md")

    # ---------------------------------------------------------------- F-3 R04c
    def test_root_only_attestation_when_reports_final_wins_is_error(self):
        """F-3 负向：双 FINAL 内容不同、只 attest 根文件 → closeout_resolved_final_missing。"""
        rd = self._run_dir("strict-both-final-root-only")
        (rd / "reports").mkdir(parents=True, exist_ok=True)
        (rd / "reports" / "FINAL.md").write_text("authoritative\n", encoding="utf-8")
        (rd / "FINAL.md").write_text("stale copy\n", encoding="utf-8")
        self._closeout(rd, [self._entry(rd, "FINAL.md")])
        codes = self.codes(rd)
        self.assertIn("closeout_resolved_final_missing", codes)
        # the root entry itself is valid (file exists, hash matches) — the finding is
        # about coverage of the resolved path, not about the root file.
        self.assertNotIn("closeout_hash_mismatch", codes)

    def test_both_finals_dual_entry_passes(self):
        """F-3 正向（P1 双 entry）：reports/ 与根都 attest → PASS。"""
        rd = self._run_dir("strict-both-final-dual-entry")
        (rd / "reports").mkdir(parents=True, exist_ok=True)
        (rd / "reports" / "FINAL.md").write_text("authoritative\n", encoding="utf-8")
        (rd / "FINAL.md").write_text("stale copy\n", encoding="utf-8")
        self._closeout(
            rd, [self._entry(rd, "reports/FINAL.md"), self._entry(rd, "FINAL.md")]
        )
        self.assertEqual(self.codes(rd), [])

    def test_identical_dual_finals_still_require_resolved_path(self):
        """F-3 显式行为：内容相同也只认解析路径，根-only attest 仍 ERROR。"""
        rd = self._run_dir("strict-both-final-identical")
        (rd / "reports").mkdir(parents=True, exist_ok=True)
        (rd / "reports" / "FINAL.md").write_text("same body\n", encoding="utf-8")
        (rd / "FINAL.md").write_text("same body\n", encoding="utf-8")
        self._closeout(rd, [self._entry(rd, "FINAL.md")])
        self.assertIn("closeout_resolved_final_missing", self.codes(rd))
        self._closeout(
            rd, [self._entry(rd, "reports/FINAL.md"), self._entry(rd, "FINAL.md")]
        )
        self.assertEqual(self.codes(rd), [])

    def test_reports_final_hash_mismatch_is_error(self):
        rd = self._run_dir("strict-reports-final-bad-sha")
        (rd / "reports").mkdir(parents=True, exist_ok=True)
        (rd / "reports" / "FINAL.md").write_text("final\n", encoding="utf-8")
        entry = self._entry(rd, "reports/FINAL.md")
        entry["sha256"] = "0" * 64
        self._closeout(rd, [entry])
        self.assertIn("closeout_hash_mismatch", self.codes(rd))

    def test_reports_final_after_closedat_requires_revision(self):
        rd = self._run_dir("strict-reports-final-late")
        (rd / "reports").mkdir(parents=True, exist_ok=True)
        (rd / "reports" / "FINAL.md").write_text("late final\n", encoding="utf-8")
        self._closeout(
            rd, [self._entry(rd, "reports/FINAL.md")], closed_at="2020-01-01T00:00:00+00:00"
        )
        self.assertIn("final_after_closeout", self.codes(rd))
        rev_dir = rd / "reports" / "evidence" / "revisions"
        rev_dir.mkdir(parents=True, exist_ok=True)
        raw = (rd / "reports" / "FINAL.md").read_bytes()
        (rev_dir / "REV-001.json").write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "path": "reports/FINAL.md",
                    "sha256": close_lint.hashlib.sha256(raw).hexdigest(),
                    "revision": 2,
                    "reason": "post-close reports/FINAL edit recorded",
                }
            ),
            encoding="utf-8",
        )
        self.assertNotIn("final_after_closeout", self.codes(rd))

    def test_both_finals_missing_is_error(self):
        rd = self._run_dir("strict-no-final")
        (rd / "reports").mkdir(parents=True, exist_ok=True)
        (rd / "reports" / "notes.md").write_text("x\n", encoding="utf-8")
        self._closeout(rd, [self._entry(rd, "reports/notes.md")])
        self.assertIn("final_missing", self.codes(rd))
        self.assertIsNone(close_lint.resolve_final(rd))


if __name__ == "__main__":
    unittest.main(verbosity=2)
