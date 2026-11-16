#!/usr/bin/env python3
"""Thin adapter: narrow a rendered hybrid bundle to the refit 4-seat contract.

The generic master renderer intentionally emits the 5-role bridge. This
specialized workflow uses only 4 roles (main/pmo/tdo_opencode/qa), so the
bridge seatMap and the manifest bridge hash must be updated together. No
OpenRig source or queue/workflow database is touched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROLE_KEYS = ("main", "pmo", "tdo_opencode", "qa")
RUNTIME_ENV_KEYS = (
    "OPENRIG_OPENCODE_BIN",
    "OPENRIG_OPENCODE_MODEL",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    args = ap.parse_args()
    bundle = Path(args.bundle).expanduser().resolve()
    bridge_path = bundle / "OPENRIG-BRIDGE.json"
    manifest_path = bundle / "render-manifest.json"
    workflow_path = bundle / "workflow.yaml"
    rig_path = bundle / "rig.yaml"
    for path in (bridge_path, manifest_path, workflow_path, rig_path):
        if not path.is_file():
            raise SystemExit(f"missing required artifact: {path}")

    bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
    old_seat_map = bridge.get("seatMap") or {}
    missing = [k for k in ROLE_KEYS if k not in old_seat_map]
    if missing:
        raise SystemExit(f"master bridge missing roles: {missing}")
    bridge["seatMap"] = {k: old_seat_map[k] for k in ROLE_KEYS}
    bridge["runtimeEnv"] = {
        k: v for k, v in (bridge.get("runtimeEnv") or {}).items() if k in RUNTIME_ENV_KEYS
    }
    bridge_text = json.dumps(bridge, indent=2, ensure_ascii=False) + "\n"
    bridge_path.write_text(bridge_text, encoding="utf-8")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = manifest.setdefault("files", {}).setdefault("OPENRIG-BRIDGE.json", {})
    record["bytes"] = len(bridge_text.encode("utf-8"))
    record["sha256"] = sha256_bytes(bridge_text.encode("utf-8"))
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"[OK] narrowed bridge to roles: {', '.join(ROLE_KEYS)}")
    print(f"[OK] bundle: {bundle}")
    print(f"[OK] bridge sha256: {record['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
