#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""workflow_invariants_probe.py — read-only structural probe for a rendered workflow.yaml (R13).

Usage:
  workflow_invariants_probe.py --run-dir <run-dir> [--workflow <path>] [--json]

Contract (TASK §1 / reports/00-plan.md §2 P1):
  * default workflow path: ``<run-dir>/openrig/workflow.yaml``; ``--workflow`` overrides it;
  * strictly read-only: no daemon call, no ``rig`` call, no subprocess, no file writes;
  * standard library only (no PyYAML) — a small intentional YAML subset:
      - ``steps:`` list items ``- id: <name>`` (quotes optional);
      - ``depends_on:`` block list (``- x``) or flow list (``[a, b]``);
      - ``next_hop:`` -> ``'on':`` / ``on:`` -> ``failed: <target>``;
      - blank lines, full-line ``#`` comments and every other key are ignored.
  * output::

        {schemaVersion, runDir, workflow, ok,
         steps[{id, dependsOn[], nextHopFailed}], duplicateIds[],
         missingDependsOn[], missingNextHopTargets[], unreachable[],
         terminal[], problems[]}

    ``missingDependsOn`` / ``missingNextHopTargets`` hold the *missing target names*
    (deduplicated, file order); ``problems`` carries the ``step->target`` detail.
  * ``ok=false`` iff: duplicate step id, ``depends_on`` points to an unknown step,
    ``next_hop.failed`` points to an unknown step, or no step parsed at all (``no_steps``).
  * ``unreachable`` / ``terminal`` are WARN-only and never flip ``ok``.
  * exit code: ok -> 0, ok=false -> 1, run-dir / workflow missing or unreadable -> 2.

This probe does NOT change the workflow engine and does NOT add ``invariants.checks[]``.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA = 1
WORKFLOW_REL = Path("openrig") / "workflow.yaml"


# ------------------------------------------------------------------ YAML subset
def _strip_line(raw: str) -> str:
    """Normalise line endings and drop full-line comments (inline '#' is left alone)."""
    line = raw.rstrip("\r\n")
    if line.lstrip().startswith("#"):
        return ""
    return line


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _flow_list(value: str) -> list[str] | None:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        return None
    inner = value[1:-1].strip()
    if not inner:
        return []
    return [_unquote(item) for item in inner.split(",") if item.strip()]


def parse_steps(text: str) -> list[dict]:
    """Extract ``steps[]`` from the workflow.yaml subset; keeps file order."""
    lines = text.splitlines()

    steps_indent = None
    start_index = None
    for index, raw in enumerate(lines):
        line = _strip_line(raw)
        if not line.strip():
            continue
        match = re.match(r"^(\s*)steps\s*:\s*$", line)
        if match:
            steps_indent = len(match.group(1))
            start_index = index
            break
    if start_index is None:
        return []

    steps: list[dict] = []
    current: dict | None = None
    list_indent: int | None = None
    key_indent: int | None = None
    mode: str | None = None
    mode_indent = 0

    def apply_step_key(key: str, value: str) -> None:
        nonlocal mode, mode_indent
        if key == "id":
            current["id"] = _unquote(value) or None
            mode = None
        elif key == "depends_on":
            flow = _flow_list(value)
            if flow is not None:
                current["dependsOn"].extend(flow)
                mode = None
            else:
                mode = "depends_on"
                mode_indent = key_indent or 0
        elif key == "next_hop":
            mode = "next_hop"
            mode_indent = key_indent or 0
        else:
            mode = None

    for raw in lines[start_index + 1 :]:
        line = _strip_line(raw)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        content = line.strip()
        # the rendered workflow.yaml uses "steps:\n- id: ..." (items at the key's own
        # indent), so a dashed line at steps_indent still belongs to the section.
        if indent < steps_indent:
            break
        if indent == steps_indent and not content.startswith("-"):
            break

        if content.startswith("- "):
            body = content[2:].strip()
            if list_indent is None:
                list_indent = indent
            if indent == list_indent:
                current = {"id": None, "dependsOn": [], "nextHopFailed": None}
                steps.append(current)
                mode = None
                key_indent = indent + 2
                key, sep, value = body.partition(":")
                if sep:
                    apply_step_key(_unquote(key), value)
                continue
            if mode == "depends_on" and indent >= mode_indent and current is not None:
                current["dependsOn"].append(_unquote(body))
            continue

        key, sep, value = content.partition(":")
        if not sep:
            continue  # continuation line of a scalar (objective, ...)
        key = _unquote(key)
        if current is None:
            continue
        if mode == "depends_on" and indent <= mode_indent and key != "depends_on":
            mode = None
        if key_indent is None:
            key_indent = indent
        if indent == key_indent:
            if mode in ("next_hop", "next_hop_on") and key not in ("next_hop", "failed"):
                mode = None
            apply_step_key(key, value)
            continue
        if mode == "next_hop" and key == "on":
            mode = "next_hop_on"
            mode_indent = indent
            continue
        if mode in ("next_hop", "next_hop_on") and key == "failed":
            current["nextHopFailed"] = _unquote(value) or None
            mode = None
            continue

    return steps


# ------------------------------------------------------------------ analysis
def analyze(text: str) -> dict:
    steps = parse_steps(text)
    ordered_ids: list[str] = []
    for step in steps:
        step_id = step.get("id")
        if step_id and step_id not in ordered_ids:
            ordered_ids.append(step_id)
    id_set = set(ordered_ids)

    duplicate_ids: list[str] = []
    seen: set[str] = set()
    for step in steps:
        step_id = step.get("id")
        if not step_id:
            continue
        if step_id in seen and step_id not in duplicate_ids:
            duplicate_ids.append(step_id)
        seen.add(step_id)

    problems: list[str] = []
    missing_depends: list[str] = []
    missing_next: list[str] = []
    for step in steps:
        step_id = step.get("id") or "<no-id>"
        for dep in step["dependsOn"]:
            if dep not in id_set:
                if dep not in missing_depends:
                    missing_depends.append(dep)
                problems.append(f"missing_depends_on:{step_id}->{dep}")
        target = step.get("nextHopFailed")
        if target and target not in id_set:
            if target not in missing_next:
                missing_next.append(target)
            problems.append(f"missing_next_hop_target:{step_id}->{target}")

    for step_id in duplicate_ids:
        problems.append(f"duplicate_id:{step_id}")
    if not steps:
        problems.append("no_steps")

    # reachability: forward edges depends_on(dependency -> dependent) + next_hop.failed(source -> target)
    successors: dict[str, list[str]] = {step_id: [] for step_id in ordered_ids}
    for step in steps:
        step_id = step.get("id")
        if not step_id:
            continue
        for dep in step["dependsOn"]:
            if dep in successors:
                successors[dep].append(step_id)
        target = step.get("nextHopFailed")
        if target in successors:
            successors[step_id].append(target)

    roots = [step["id"] for step in steps if step.get("id") and not step["dependsOn"]]
    visited: set[str] = set()
    queue = list(dict.fromkeys(roots))
    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)
        for nxt in successors.get(node, []):
            if nxt not in visited:
                queue.append(nxt)
    unreachable = [step_id for step_id in ordered_ids if step_id not in visited]

    depended_on = {
        dep for step in steps for dep in step["dependsOn"] if dep in id_set
    }
    terminal = [
        step_id
        for step_id in ordered_ids
        if step_id not in depended_on
        and not any(
            step.get("id") == step_id and step.get("nextHopFailed") for step in steps
        )
    ]

    ok = not (duplicate_ids or missing_depends or missing_next or not steps)

    return {
        "schemaVersion": SCHEMA,
        "ok": ok,
        "steps": [
            {
                "id": step.get("id"),
                "dependsOn": list(step["dependsOn"]),
                "nextHopFailed": step.get("nextHopFailed"),
            }
            for step in steps
        ],
        "duplicateIds": duplicate_ids,
        "missingDependsOn": missing_depends,
        "missingNextHopTargets": missing_next,
        "unreachable": unreachable,
        "terminal": terminal,
        "problems": problems,
    }


# ------------------------------------------------------------------ cli
def probe(run_dir: Path, workflow: Path | None = None) -> dict:
    path = workflow if workflow is not None else run_dir / WORKFLOW_REL
    report: dict = {
        "schemaVersion": SCHEMA,
        "runDir": str(run_dir),
        "workflow": str(path),
        "ok": False,
        "steps": [],
        "duplicateIds": [],
        "missingDependsOn": [],
        "missingNextHopTargets": [],
        "unreachable": [],
        "terminal": [],
        "problems": [],
    }
    if not run_dir.is_dir():
        report["error"] = f"run dir missing: {run_dir}"
        report["rc"] = 2
        return report
    if not path.is_file():
        report["error"] = f"workflow file missing: {path}"
        report["rc"] = 2
        return report
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:  # noqa: BLE001
        report["error"] = f"workflow file unreadable: {path}: {exc}"
        report["rc"] = 2
        return report

    report.update(analyze(text))
    report["rc"] = 0 if report["ok"] else 1
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="read-only structural invariants probe for a rendered workflow.yaml (R13)"
    )
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--workflow", default=None, help="override <run-dir>/openrig/workflow.yaml")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir).expanduser()
    workflow = Path(args.workflow).expanduser() if args.workflow else None
    report = probe(run_dir, workflow)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"workflow: {report['workflow']}")
        if report.get("error"):
            print(f"[FAIL] {report['error']}")
        else:
            print(f"steps: {', '.join(s['id'] or '<no-id>' for s in report['steps']) or '(none)'}")
            print(f"terminal: {', '.join(report['terminal']) or '(none)'}")
            if report["unreachable"]:
                print(f"[WARN] unreachable: {', '.join(report['unreachable'])}")
            for problem in report["problems"]:
                print(f"[PROBLEM] {problem}")
        print(f"RESULT {'OK' if report['ok'] else 'FAIL'} rc={report['rc']}")
    return report["rc"]


if __name__ == "__main__":
    sys.exit(main())
