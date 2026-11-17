# -*- coding: utf-8 -*-
"""2026-11-17 hotfix regression: hop budget + no implicit non-interruptive.

This test targets the live KB template copy, not a historical snapshot.  It is
deliberately offline: render_master writes only to tmp_path and no rig command
is executed.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "templates" / "specialized" / "openrig-workflow-master"


def test_workflow_template_declares_hotfix_hop_budget():
    text = (MASTER / "templates" / "workflow.yaml.tpl").read_text(encoding="utf-8")
    assert re.search(r"^\s*max_hops:\s*12\s*$", text, re.MULTILINE), "KB template is not on the 12-hop hotfix"
    assert "5 + 2 + 2 = 9" in text


def test_renderer_metadata_and_next_commands(tmp_path: Path):
    out = tmp_path / "openrig"
    proc = subprocess.run(
        [
            sys.executable,
            str(MASTER / "render_master.py"),
            "--run-id",
            "hotfix-regression",
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(out),
            "--json",
        ],
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(proc.stdout)
    bridge = json.loads((out / "OPENRIG-BRIDGE.json").read_text(encoding="utf-8"))

    assert bridge["policy"]["maxHops"] == 12
    assert bridge["policyEnforcement"] == {
        "safetyMode": "contract-only-unenforced",
        "allowSourceChanges": "advisory-unenforced",
        "maxActiveAgents": "advisory-unenforced",
        "note": "These fields are not runtime gates in OpenRig v1.2; see SAFETY-ENFORCEMENT.md.",
    }
    commands = "\n".join(report["nextCommands"])
    assert "--non-interruptive" not in commands, "nextCommands must not accept full-bypass notices for the operator"


def test_docs_point_at_managed_supervisor():
    for name in ("README.md", "PREFLIGHT.md", "ENTRYPOINTS.md"):
        text = (MASTER / name).read_text(encoding="utf-8")
        assert "openrig_run.py start" in text, f"{name} lost the managed supervisor entry"


def test_lite_entry_does_not_inject_non_interruptive():
    source = (ROOT / "scripts" / "openrig_lite.py").read_text(encoding="utf-8")
    assert '"--non-interruptive"' not in source
