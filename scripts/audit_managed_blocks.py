#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only audit of OpenRig managed blocks (R10).

Enumerates `<!-- BEGIN OpenRig MANAGED BLOCK: <id> -->` … `<!-- END … -->` pairs so
that blocks with no inferable owner rig become visible instead of silently drifting.
This tool never edits a file and never touches the OpenRig product code or the block
namespace; it only reports.

Usage:
  python3 scripts/audit_managed_blocks.py --path AGENTS.md --json
  python3 scripts/audit_managed_blocks.py --path . --path CLAUDE.md --strict --json

Kinds:
  preflight  legacy `<!-- BEGIN OPENRIG-PREFLIGHT (managed) -->` seat-workspace block
  managed    `OpenRig MANAGED BLOCK: <id>` (also accepted: legacy `RIGGED MANAGED BLOCK:`)
  unknown    any other `BEGIN … MANAGED BLOCK …` marker (namespace not recognised)

ownerRig inference (from the block id only, no guessing by path):
  `rig:<rigName>`, `rig:<rigName>/…`, `rig:<rigName>::…`  → `<rigName>`
  anything else                                            → null  (an orphan)

Exit codes:
  0  default (read-only report; orphans are data, not a failure)
  1  `--strict` and at least one non-preflight block has ownerRig == null,
     or any managed block is unterminated
  2  usage error / unreadable input
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA = 1

BEGIN_RE = re.compile(r"<!--\s*BEGIN\s+(?P<marker>[^>]*?)\s*-->")
END_RE = re.compile(r"<!--\s*END\s+(?P<marker>[^>]*?)\s*-->")
ID_RE = re.compile(r"MANAGED\s+BLOCK:\s*(?P<id>[^\s>]+)\s*$")
OWNER_RE = re.compile(r"^rig:(?P<rig>[A-Za-z0-9][A-Za-z0-9._-]*)(?:[/:]{1,2}.*)?$")
LEGACY_PREFIX = "RIGGED MANAGED BLOCK:"


def _classify(marker: str) -> tuple[str, str | None, str | None]:
    """Return (kind, blockId, warning-or-None) for a BEGIN marker body."""
    norm = marker.strip()
    if "OPENRIG-PREFLIGHT" in norm.upper():
        return "preflight", "OPENRIG-PREFLIGHT", None
    m = ID_RE.search(norm)
    if m:
        block_id = m.group("id")
        warning = None
        if norm.startswith(LEGACY_PREFIX):
            warning = "legacy-rigged-namespace"
        return "managed", block_id, warning
    if "MANAGED BLOCK" in norm.upper():
        return "unknown", norm, "unrecognised-managed-block-namespace"
    return "unknown", norm, "unrecognised-managed-block-namespace"


def _owner(block_id: str) -> str | None:
    m = OWNER_RE.match(block_id)
    return m.group("rig") if m else None


def audit_text(text: str) -> list[dict]:
    """Pair BEGIN/END markers in one document; report unterminated blocks too."""
    lines = text.splitlines()
    blocks: list[dict] = []
    open_block: dict | None = None
    end_markers: list[tuple[int, str]] = []
    for idx, line in enumerate(lines, start=1):
        for m in BEGIN_RE.finditer(line):
            if open_block is not None:
                open_block["warning"] = open_block["warning"] or "unterminated-block"
                blocks.append(open_block)  # previous never closed
                open_block = None
            kind, block_id, warning = _classify(m.group("marker"))
            open_block = {
                "id": block_id,
                "startLine": idx,
                "endLine": None,
                "kind": kind,
                "ownerRig": _owner(block_id),
                "warning": warning,
            }
        for m in END_RE.finditer(line):
            end_markers.append((idx, m.group("marker")))
            if open_block is None:
                blocks.append(
                    {
                        "id": m.group("marker").strip(),
                        "startLine": None,
                        "endLine": idx,
                        "kind": "unknown",
                        "ownerRig": None,
                        "warning": "end-without-begin",
                    }
                )
                continue
            open_block["endLine"] = idx
            blocks.append(open_block)
            open_block = None
    if open_block is not None:
        open_block["warning"] = open_block["warning"] or "unterminated-block"
        blocks.append(open_block)
    return blocks


def _expand(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()
    for target in paths:
        p = Path(target).expanduser()
        if p.is_dir():
            candidates = sorted(
                f
                for f in p.rglob("*")
                if f.is_file() and ".git" not in f.relative_to(p).parts
            )
        else:
            candidates = [p]
        for c in candidates:
            key = str(c)
            if key not in seen:
                seen.add(key)
                out.append(c)
    return out


def audit(paths: list[str]) -> dict:
    files: list[dict] = []
    errors: list[dict] = []
    for path in _expand(paths):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            errors.append({"path": str(path), "error": str(exc)})
            continue
        blocks = audit_text(text)
        files.append(
            {
                "path": str(path),
                "bytes": len(text.encode("utf-8")),
                "blocks": blocks,
            }
        )
    by_kind: dict[str, int] = {}
    total = 0
    orphans = 0
    warnings = 0
    unterminated = 0
    for f in files:
        for b in f["blocks"]:
            total += 1
            by_kind[b["kind"]] = by_kind.get(b["kind"], 0) + 1
            if b["kind"] != "preflight" and b["ownerRig"] is None:
                orphans += 1
            if b["warning"]:
                warnings += 1
            if b["endLine"] is None or b["startLine"] is None:
                unterminated += 1
    summary = {
        "files": len(files),
        "filesWithBlocks": sum(1 for f in files if f["blocks"]),
        "blocks": total,
        "byKind": by_kind,
        "orphanManaged": orphans,
        "warnings": warnings,
        "unterminated": unterminated,
        "errors": len(errors),
    }
    return {
        "schemaVersion": SCHEMA,
        "paths": list(paths),
        "files": files,
        "errors": errors,
        "summary": summary,
    }


def strict_failures(report: dict) -> list[str]:
    reasons: list[str] = []
    for f in report["files"]:
        for b in f["blocks"]:
            if b["kind"] != "preflight" and b["ownerRig"] is None:
                reasons.append(
                    f"{f['path']}:{b['startLine']} managed block '{b['id']}' has no ownerRig"
                )
            if b["endLine"] is None or b["startLine"] is None:
                reasons.append(
                    f"{f['path']}:{b['startLine'] or b['endLine']} managed block "
                    f"'{b['id']}' is unterminated"
                )
    return reasons


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="read-only OpenRig managed block audit")
    ap.add_argument(
        "--path",
        action="append",
        required=True,
        help="file or directory to audit (repeatable; directories recurse)",
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="rc=1 when a non-preflight managed block has no ownerRig or is unterminated",
    )
    ap.add_argument("--json", action="store_true", help="print the full JSON report")
    args = ap.parse_args(argv)

    report = audit(args.path)
    failures = strict_failures(report) if args.strict else []
    report["strict"] = {"enabled": bool(args.strict), "failures": failures}

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        s = report["summary"]
        print(
            f"files={s['files']} blocks={s['blocks']} byKind={s['byKind']} "
            f"orphanManaged={s['orphanManaged']} warnings={s['warnings']} "
            f"unterminated={s['unterminated']}"
        )
        for f in report["files"]:
            for b in f["blocks"]:
                mark = "WARN" if b["warning"] or b["ownerRig"] is None else "OK"
                print(
                    f"- [{mark}] {f['path']}:{b['startLine']}-{b['endLine']} "
                    f"{b['kind']} id={b['id']} ownerRig={b['ownerRig']}"
                    + (f" warning={b['warning']}" if b["warning"] else "")
                )
        for reason in failures:
            print(f"[STRICT] {reason}")

    if report["summary"]["errors"]:
        return 2
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
