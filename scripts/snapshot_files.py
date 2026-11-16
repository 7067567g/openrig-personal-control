#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only file snapshot for before/after evidence (W4).

Records path/bytes/sha256/mtime for each target so a pre-existing untracked file
can be compared before and after an implementation step. Never writes anything
except the JSON report named by --out.

Usage:
  python3 scripts/snapshot_files.py --out before.json --label before \
      --path workflow-group/AGENTS.md --path /tmp/untracked-dir
  python3 scripts/snapshot_files.py --out after.json --label after --path X --json

Behaviour:
  - A directory is walked recursively (`.git` is skipped); results are sorted.
  - A missing path is recorded with `exists: false` instead of raising.
  - Nothing is truncated: every file gets its own entry.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

SCHEMA = 1
LABELS = ("before", "after")


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts).astimezone().isoformat(timespec="microseconds")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _entry(path: Path, label: str, captured_at: str) -> dict:
    try:
        st = path.stat()
    except OSError:
        return {
            "path": str(path),
            "exists": False,
            "bytes": None,
            "sha256": None,
            "mtime": None,
            "label": label,
            "capturedAt": captured_at,
        }
    if not path.is_file():
        return {
            "path": str(path),
            "exists": False,
            "bytes": None,
            "sha256": None,
            "mtime": None,
            "label": label,
            "capturedAt": captured_at,
            "reason": "not-a-regular-file",
        }
    try:
        digest = _sha256_file(path)
    except OSError:
        # 权限/竞态：记录存在但不伪造 sha256。
        return {
            "path": str(path),
            "exists": True,
            "bytes": st.st_size,
            "sha256": None,
            "mtime": _iso(st.st_mtime),
            "label": label,
            "capturedAt": captured_at,
            "reason": "unreadable",
        }
    return {
        "path": str(path),
        "exists": True,
        "bytes": st.st_size,
        "sha256": digest,
        "mtime": _iso(st.st_mtime),
        "label": label,
        "capturedAt": captured_at,
    }


def _expand(target: str) -> list[Path]:
    p = Path(target).expanduser()
    if not p.exists():
        return [p]
    if p.is_dir():
        files = [
            f
            for f in p.rglob("*")
            if f.is_file() and ".git" not in f.relative_to(p).parts
        ]
        return sorted(files, key=lambda f: str(f))
    return [p]


def snapshot(paths: list[str], label: str) -> dict:
    captured_at = datetime.now().astimezone().isoformat(timespec="seconds")
    entries: list[dict] = []
    seen: set[str] = set()
    for target in paths:
        for file in _expand(target):
            key = str(file)
            if key in seen:
                continue
            seen.add(key)
            entries.append(_entry(file, label, captured_at))
    return {
        "schemaVersion": SCHEMA,
        "label": label,
        "capturedAt": captured_at,
        "roots": list(paths),
        "files": entries,
        "summary": {
            "total": len(entries),
            "present": sum(1 for e in entries if e["exists"]),
            "missing": sum(1 for e in entries if not e["exists"]),
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="read-only file snapshot (before/after)")
    ap.add_argument("--out", required=True, help="JSON report path")
    ap.add_argument("--label", required=True, choices=LABELS)
    ap.add_argument(
        "--path",
        action="append",
        required=True,
        help="file or directory to snapshot (repeatable; directories recurse)",
    )
    ap.add_argument("--json", action="store_true", help="print the whole report to stdout")
    args = ap.parse_args(argv)

    report = snapshot(args.path, args.label)
    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        s = report["summary"]
        print(
            f"[OK] snapshot({report['label']}) -> {out} "
            f"total={s['total']} present={s['present']} missing={s['missing']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
