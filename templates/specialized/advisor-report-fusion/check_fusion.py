#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mechanical checks for advisor-report-fusion claim registers.

This does NOT decide whether a technical claim is true. It only enforces the
handoff contract: unique IDs, allowed enums, source references, and required
fields for dispositions that will be executed or explicitly deferred/rejected.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ALLOWED_TYPES = {"fact", "inference", "recommendation", "risk", "change"}
ALLOWED_EVIDENCE = {"verified", "partial", "stale", "unverified"}
ALLOWED_DISPOSITIONS = {"accept_now", "accept_next", "park", "reject", "already_done"}
ALLOWED_WAVES = {"W0", "W1", "W2", "W3", "none"}
ALLOWED_OWNERS = {"TDO", "PMO", "MAIN", "QA"}
SOURCE_RE = re.compile(r"^(OC|DSH|CMP):[A-Za-z0-9_.§/-]+$")
ID_RE = re.compile(r"^AFC-\d{3}$")


def fail(errors: list[str], msg: str) -> None:
    errors.append(msg)


def check_register(path: Path, require_disposition: bool) -> tuple[list[str], list[dict]]:
    errors: list[str] = []
    rows: list[dict] = []
    if not path.is_file():
        return [f"register not found: {path}"], rows
    seen: set[str] = set()
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            fail(errors, f"line {lineno}: invalid JSON: {exc}")
            continue
        if not isinstance(row, dict):
            fail(errors, f"line {lineno}: row must be an object")
            continue
        rows.append(row)
        rid = str(row.get("id", ""))
        if not ID_RE.fullmatch(rid):
            fail(errors, f"line {lineno}: id must match AFC-NNN, got {rid!r}")
        if rid in seen:
            fail(errors, f"line {lineno}: duplicate id {rid}")
        seen.add(rid)
        if not str(row.get("title", "")).strip():
            fail(errors, f"{rid or 'line '+str(lineno)}: missing title")
        if row.get("claim_type") not in ALLOWED_TYPES:
            fail(errors, f"{rid}: invalid claim_type {row.get('claim_type')!r}")
        sources = row.get("sources")
        if not isinstance(sources, list) or not sources:
            fail(errors, f"{rid}: sources must be a non-empty list")
        else:
            for src in sources:
                if not isinstance(src, str) or not SOURCE_RE.fullmatch(src):
                    fail(errors, f"{rid}: invalid source {src!r}")
        if row.get("evidence_status") not in ALLOWED_EVIDENCE:
            fail(errors, f"{rid}: invalid evidence_status {row.get('evidence_status')!r}")
        disp = row.get("disposition")
        if require_disposition and disp not in ALLOWED_DISPOSITIONS:
            fail(errors, f"{rid}: invalid/missing disposition {disp!r}")
        elif disp is not None and disp not in ALLOWED_DISPOSITIONS:
            fail(errors, f"{rid}: invalid disposition {disp!r}")
        if row.get("wave") not in ALLOWED_WAVES:
            fail(errors, f"{rid}: invalid wave {row.get('wave')!r}")
        if disp in {"accept_now", "accept_next"}:
            if row.get("owner") not in ALLOWED_OWNERS:
                fail(errors, f"{rid}: accept_* requires owner in {sorted(ALLOWED_OWNERS)}")
            if not str(row.get("action", "")).strip():
                fail(errors, f"{rid}: accept_* requires action")
            if not str(row.get("acceptance", "")).strip():
                fail(errors, f"{rid}: accept_* requires acceptance")
        if disp in {"accept_now", "already_done"} and row.get("owner") not in ALLOWED_OWNERS:
            fail(errors, f"{rid}: {disp} requires owner")
        if disp == "reject" and not str(row.get("reject_reason", "")).strip():
            fail(errors, f"{rid}: reject requires reject_reason")
        if disp == "park" and not str(row.get("trigger", "")).strip():
            fail(errors, f"{rid}: park requires trigger")
        if disp == "already_done":
            if not str(row.get("action", "")).strip() and not str(row.get("notes", "")).strip():
                fail(errors, f"{rid}: already_done requires action/evidence note")
    return errors, rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--register", required=True)
    ap.add_argument("--require-disposition", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    errors, rows = check_register(Path(args.register), args.require_disposition)
    summary = {
        "register": args.register,
        "rows": len(rows),
        "accept_now": sum(1 for r in rows if r.get("disposition") == "accept_now"),
        "accept_next": sum(1 for r in rows if r.get("disposition") == "accept_next"),
        "park": sum(1 for r in rows if r.get("disposition") == "park"),
        "reject": sum(1 for r in rows if r.get("disposition") == "reject"),
        "already_done": sum(1 for r in rows if r.get("disposition") == "already_done"),
        "errors": errors,
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"rows={summary['rows']} accept_now={summary['accept_now']} accept_next={summary['accept_next']} park={summary['park']} reject={summary['reject']} already_done={summary['already_done']}")
        for err in errors:
            print(f"[ERROR] {err}", file=sys.stderr)
        if not errors:
            print("[OK] advisor-report-fusion register contract satisfied")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
