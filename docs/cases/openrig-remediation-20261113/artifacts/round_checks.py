#!/usr/bin/env python3
"""CHECK-MANIFEST loader.

R4 起，R01–R30 的验收不再在这里写 token 表；行为测试统一来自
tools/sctg/check-manifest.yaml。check_round.py 只消费这份 manifest。
"""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "tools/sctg/check-manifest.yaml"
_DATA = yaml.safe_load(MANIFEST.read_text(encoding="utf-8")) or {}
ROUND_CHECKS = {}
for row in _DATA.get("rounds", []):
    ROUND_CHECKS[row["id"]] = {
        "files": row.get("artifacts", []),
        "tokens": [],
        "commands": [c for c in row.get("behavior_tests", []) if c],
        "needs_main": bool(row.get("manual_checkpoint") or row.get("runs_via") == "external"),
        "manifest": row,
    }
