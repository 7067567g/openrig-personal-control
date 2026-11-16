# -*- coding: utf-8 -*-
"""advisor-report-fusion 台账机械门回归。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / "templates" / "specialized" / "advisor-report-fusion" / "check_fusion.py"


def _run(path: Path):
    return subprocess.run(
        [sys.executable, str(CHECK), "--register", str(path), "--require-disposition", "--json"],
        capture_output=True,
        text=True,
    )


def _row(**over):
    row = {
        "id": "AFC-001",
        "title": "machine-checked issue",
        "claim_type": "fact",
        "sources": ["OC:S2-P0-1"],
        "evidence_status": "verified",
        "disposition": "accept_next",
        "wave": "W1",
        "owner": "TDO",
        "action": "do a bounded thing",
        "acceptance": "pytest -q",
    }
    row.update(over)
    return row


def test_check_fusion_accepts_complete_register(tmp_path):
    p = tmp_path / "ok.jsonl"
    p.write_text(json.dumps(_row(), ensure_ascii=False) + "\n", encoding="utf-8")
    r = _run(p)
    assert r.returncode == 0, r.stdout + r.stderr
    data = json.loads(r.stdout)
    assert data["rows"] == 1 and data["accept_next"] == 1 and not data["errors"]


def test_check_fusion_rejects_accept_without_acceptance_or_owner(tmp_path):
    p = tmp_path / "bad.jsonl"
    p.write_text(
        json.dumps(_row(owner="", acceptance=""), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    r = _run(p)
    assert r.returncode == 1
    data = json.loads(r.stdout)
    blob = "\n".join(data["errors"])
    assert "requires owner" in blob
    assert "requires acceptance" in blob


def test_check_fusion_rejects_duplicate_id_and_bad_source(tmp_path):
    p = tmp_path / "dup.jsonl"
    p.write_text(
        "\n".join(
            [
                json.dumps(_row(sources=["OC:S2-P0-1"]), ensure_ascii=False),
                json.dumps(_row(disposition="reject", reject_reason="no"), ensure_ascii=False),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    r = _run(p)
    assert r.returncode == 1
    assert "duplicate id AFC-001" in "\n".join(json.loads(r.stdout)["errors"])
