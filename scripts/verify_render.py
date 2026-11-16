#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_render.py — R07/W5: recompute `openrig/render-manifest.json` bytes/sha256.

Usage:
  python3 scripts/verify_render.py --run-dir runs/<run-id> [--strict] [--json]
                                   [--specializations <json>]

Semantics:
  * every `files[*]` entry is re-hashed from `<run-dir>/openrig/<path>`;
  * default: mismatch -> rc=0 with `ok:false` (WARN, no false PASS);
  * `--strict`: mismatch -> rc=1;
  * manifest missing / bad JSON / bad schema -> rc=2 (never pretends to pass).

W5 — recorded run specializations (default `<run-dir>/openrig/render-specializations.json`):

```json
{"schemaVersion":1,"runId":"<run-id>","files":{
  "rig.yaml":{"bytes":123,"sha256":"<64 hex>","reason":"why this run differs"}}}
```

  * a manifest/disk mismatch whose specialization entry matches the disk **bytes and sha256
    exactly** and carries a non-empty `reason` is a legal specialization: the item is reported
    with `specialized:true`, does not count as a mismatch, and `--strict` stays rc=0;
  * a stale specialization (bytes/sha no longer match disk) does **not** rescue the mismatch;
  * an unreadable/invalid specialization file -> rc=2 (fail closed, never silently ignored).

Dependency-free: standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

SPECIALIZATIONS_NAME = "render-specializations.json"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_specializations(path: Path) -> dict:
    """Return {"path","entries","error","present", "runId", "schemaVersion"}."""
    info = {"path": str(path), "entries": {}, "error": None, "present": path.is_file()}
    if not path.is_file():
        return info
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        info["error"] = f"{path.name} is not valid JSON: {exc}"
        return info
    if not isinstance(data, dict) or not isinstance(data.get("files"), dict):
        info["error"] = f"{path.name} must be an object with a `files` object"
        return info
    entries = {k: v for k, v in data["files"].items() if isinstance(v, dict)}
    if len(entries) != len(data["files"]):
        info["error"] = f"{path.name} has non-object entries under `files`"
        return info
    info["entries"] = entries
    info["runId"] = data.get("runId")
    info["schemaVersion"] = data.get("schemaVersion")
    return info


def _specialization_covers(entry: dict | None, raw: bytes, actual_sha: str) -> tuple[bool, str]:
    if not entry:
        return False, "no specialization entry"
    if entry.get("bytes") != len(raw):
        return False, "stale specialization (bytes differ)"
    if entry.get("sha256") != actual_sha:
        return False, "stale specialization (sha256 differs)"
    if not str(entry.get("reason") or "").strip():
        return False, "specialization without reason is not accepted"
    return True, str(entry.get("reason"))


def verify(run_dir: Path, specializations_path: Path | None = None) -> dict:
    manifest_path = run_dir / "openrig" / "render-manifest.json"
    spec_path = specializations_path or (run_dir / "openrig" / SPECIALIZATIONS_NAME)
    result = {
        "ok": False,
        "runId": run_dir.name,
        "runDir": str(run_dir),
        "manifestPath": str(manifest_path),
        "checked": [],
        "mismatches": [],
        "specialized": [],
        "specializations": {
            "path": str(spec_path),
            "present": False,
            "applied": [],
            "stale": [],
        },
        "error": None,
        "rc": 2,
    }
    if not manifest_path.is_file():
        result["error"] = "render-manifest.json missing"
        return result
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"render-manifest.json is not valid JSON: {exc}"
        return result
    if not isinstance(data, dict) or not isinstance(data.get("files"), dict):
        result["error"] = "render-manifest.json missing `files` object"
        return result

    specs = load_specializations(spec_path)
    result["specializations"]["present"] = bool(specs["present"])
    if specs["error"]:
        result["error"] = specs["error"]
        return result
    entries = specs["entries"]
    used: set[str] = set()
    checked_paths: set[str] = set()

    for rel, meta in data["files"].items():
        if not isinstance(meta, dict):
            result["mismatches"].append({"path": rel, "reason": "entry is not an object"})
            continue
        checked_paths.add(rel)
        target = run_dir / "openrig" / rel
        expected_bytes = meta.get("bytes")
        expected_sha = meta.get("sha256")
        item = {
            "path": rel,
            "expectedBytes": expected_bytes,
            "expectedSha256": expected_sha,
            "ok": False,
        }
        if not target.is_file():
            item["reason"] = "file missing"
            result["mismatches"].append(item)
            result["checked"].append(item)
            continue
        raw = target.read_bytes()
        actual_sha = hashlib.sha256(raw).hexdigest()
        item["actualBytes"] = len(raw)
        item["actualSha256"] = actual_sha
        if expected_bytes == len(raw) and expected_sha == actual_sha:
            item["ok"] = True
        else:
            item["reason"] = (
                "bytes mismatch" if expected_bytes != len(raw) else "sha256 mismatch"
            )
            legal, why = _specialization_covers(entries.get(rel), raw, actual_sha)
            if legal:
                used.add(rel)
                item["ok"] = True
                item["specialized"] = True
                item["specializationReason"] = why
                result["specialized"].append(rel)
                result["specializations"]["applied"].append({"path": rel, "reason": why})
            else:
                if rel in entries:
                    item["specializationRejected"] = why
                    result["specializations"]["stale"].append({"path": rel, "reason": why})
                result["mismatches"].append(item)
        result["checked"].append(item)

    for rel in sorted(set(entries) - used):
        if rel in checked_paths:
            continue  # already reported as stale above
        result["specializations"]["stale"].append(
            {"path": rel, "reason": "specialization does not match any manifest entry"}
        )

    result["ok"] = not result["mismatches"]
    result["rc"] = 0
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="verify rendered OpenRig run manifest hashes")
    ap.add_argument("--run-dir", required=True, help="runs/<run-id>")
    ap.add_argument("--strict", action="store_true", help="mismatch -> rc=1 instead of WARN rc=0")
    ap.add_argument(
        "--specializations",
        default="",
        help=(
            "recorded run specializations JSON "
            f"(default <run-dir>/openrig/{SPECIALIZATIONS_NAME})"
        ),
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    run_dir = Path(args.run_dir).expanduser()
    if not run_dir.is_dir():
        payload = {
            "ok": False,
            "runDir": str(run_dir),
            "error": "run dir missing",
            "checked": [],
            "mismatches": [],
            "rc": 2,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else f"[FAIL] run dir missing: {run_dir}")
        return 2

    spec_path = Path(args.specializations).expanduser() if args.specializations else None
    payload = verify(run_dir, spec_path)
    rc = payload["rc"]
    if payload["error"]:
        rc = 2
    elif payload["mismatches"]:
        rc = 1 if args.strict else 0
    payload["rc"] = rc
    payload["strict"] = bool(args.strict)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for rel in payload.get("specialized") or []:
            print(f"[SPEC] {rel}: recorded specialization")
        for item in payload["mismatches"]:
            print(f"WARN [render] {item.get('path')}: {item.get('reason')}")
        for stale in payload["specializations"]["stale"]:
            print(f"WARN [specialization] {stale['path']}: {stale['reason']}")
        print(
            f"RESULT {'PASS' if payload['ok'] else 'MISMATCH'} "
            f"checked={len(payload['checked'])} mismatches={len(payload['mismatches'])} "
            f"specialized={len(payload.get('specialized') or [])} rc={rc}"
        )
        if payload["error"]:
            print(f"ERROR [render] {payload['error']}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
