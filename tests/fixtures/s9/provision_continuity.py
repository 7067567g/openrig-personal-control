#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S9 continuity fixtures — FI-04..FI-09 (+FI-05b) for the `resume|status|stop|next` ATs.

Two provisioning paths, one builder:

  * the acceptance matrix names bare ids (`--run-dir FI-05`), so MAIN/QA run this file
    once with `OPENRIG_S9_FIXTURES` pointing at a per-verification directory:
        OPENRIG_S9_FIXTURES=$(mktemp -d) .venv/bin/python tests/fixtures/s9/provision_continuity.py
  * `tests/test_openrig_continuity.py` calls `build_run` into its own `tmp_path`, so the
    pytest cases never share a namespace (W-S8-12) and never depend on the matrix run.

S9-R-01: there is no default root. Unset `OPENRIG_S9_FIXTURES` is an error here too.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

FIXTURE_ROOT_ENV = "OPENRIG_S9_FIXTURES"
ALL_VERBS = [
    "daemon-start",
    "up",
    "restore-apply",
    "workflow-instantiate",
    "workflow-instantiate-lifecycle",
    "workflow-run",
]

# The fake rig: records every call, answers in the shape openrig_run expects, and — for
# `up <rig> --existing` — applies the fixture's "after" observation by replacing the
# state file. That keeps the module honest: the post-resume state is READ, not assumed.
# It locates itself (it sits in the run dir), so no env plumbing leaks into the child.
FAKE_RIG = r'''#!/usr/bin/env python3
"""S9 continuity fixture rig: no daemon, no tmux, no seats. Logs argv, moves the state."""
import json, os, sys
from pathlib import Path

run_dir = Path(__file__).resolve().parent
state_path = run_dir / "openrig" / "continuity-state.json"
after_path = run_dir / "openrig" / "continuity-state.after.json"
log = run_dir / "fake-rig.log"

def record(argv):
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"argv": argv,
                             "env": {k: os.environ.get(k) for k in
                                     ("OPENRIG_HOME", "OPENRIG_PORT")}}) + "\n")

argv = sys.argv[1:]
record(argv)

if argv[:2] == ["daemon", "start"]:
    state = json.loads(state_path.read_text())
    state["daemonState"] = "running"
    state_path.write_text(json.dumps(state))
    print(json.dumps({"ok": True, "pid": 424242}))
    sys.exit(0)

if argv[:1] == ["up"]:
    if "--existing" not in argv:
        print("fixture rig: only `up <rig> --existing` is supported", file=sys.stderr)
        sys.exit(2)
    if after_path.is_file():
        state_path.write_text(after_path.read_text())
    print(json.dumps({"ok": True, "mode": "existing"}))
    sys.exit(0)

if argv[:1] == ["daemon"] and argv[1:2] == ["stop"]:
    print(json.dumps({"ok": True}))
    sys.exit(0)

if argv[:1] == ["down"]:
    state = json.loads(state_path.read_text()) if state_path.is_file() else {"seats": []}
    for seat in state.get("seats", []):
        seat["session"] = "absent"
        seat["activity"] = None
    state["daemonState"] = "stopped"
    state["rigState"] = "absent"
    state_path.write_text(json.dumps(state))
    print(json.dumps({"ok": True}))
    sys.exit(0)

if argv[:1] == ["workflow"]:
    print(json.dumps({"ok": True, "instanceId": "wf-fixture"}))
    sys.exit(0)

print(json.dumps({"ok": True, "argv": argv}))
sys.exit(0)
'''


# ------------------------------------------------------------------ seat helpers
def seat(
    logical_id: str,
    *,
    token=True,
    session="absent",
    activity=None,
    startup="missing",
    actual=None,
    evidence="observed",
    reasons=(),
    node_id=None,
) -> dict:
    return {
        "logicalId": logical_id,
        "canonicalSessionName": f"{logical_id}@fixture",
        "nodeId": node_id or f"node-{logical_id}",
        "restorePolicy": "resume_if_possible",
        "resumeTokenPresent": token,
        "session": session,
        "activity": activity,
        "evidence": evidence,
        "evidenceReasons": list(reasons),
        "startupStatus": startup,
        "actualOutcome": actual,
    }


def build_run(
    root: Path,
    name: str,
    *,
    state: dict,
    after_state: dict | None = None,
    archive: str | None = None,
) -> Path:
    """Create one run bundle under `root/name`. Returns the run dir."""
    run = Path(root) / name
    openrig = run / "openrig"
    (openrig / "tools").mkdir(parents=True, exist_ok=True)
    home = run / "home"
    home.mkdir(exist_ok=True)

    rig = run / "fake-rig"
    rig.write_text(FAKE_RIG, encoding="utf-8")
    rig.chmod(0o755)

    (openrig / "rig.yaml").write_text(f"rig: s9-{name.lower()}\n", encoding="utf-8")
    (openrig / "workflow.yaml").write_text(f"workflow: s9-{name.lower()}\n", encoding="utf-8")

    bridge = {
        "schemaVersion": 2,
        "runId": name,
        "rigName": f"s9-{name.lower()}",
        "workflowId": f"s9-{name.lower()}",
        "rigSpec": "rig.yaml",
        "workflowSpec": "workflow.yaml",
        "openrigCli": str(rig),
        "openrigHome": str(home),
        "projectRoot": str(run / "project-root"),
        "daemonPort": 47998,
        "seatMap": {s["logicalId"]: s["canonicalSessionName"] for s in state["seats"]},
        "bundleDir": "openrig",
        "_fixture": "S9 continuity fixture; not a real run",
    }
    (openrig / "OPENRIG-BRIDGE.json").write_text(json.dumps(bridge, indent=2) + "\n", encoding="utf-8")
    (openrig / "continuity-state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    if after_state is not None:
        (openrig / "continuity-state.after.json").write_text(
            json.dumps(after_state, indent=2) + "\n", encoding="utf-8"
        )
    if archive is not None:
        manifest = run / "reports" / "evidence" / "archive" / "ARCHIVE-MANIFEST.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps({"schemaVersion": 1, "runId": name, "status": archive,
                        "reason": "fixture archive status"}, indent=2) + "\n",
            encoding="utf-8",
        )
    return run


def _stopped(seats: list[dict], *, instance="wf-fixture") -> dict:
    return {
        "daemonState": "stopped",
        "rigState": "stopped",
        "workflowInstanceId": instance,
        "seats": seats,
    }


# ------------------------------------------------------------------ the named fixtures
def provision(root: Path) -> dict:
    """(Re)create every continuity fixture. Deterministic: previous copies are removed."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for name in ("FI-04", "FI-05", "FI-05b", "FI-06", "FI-07", "FI-08", "FI-09"):
        shutil.rmtree(root / name, ignore_errors=True)

    created: dict[str, str] = {}

    # FI-04 — healthy stopped run: `next` (rc0) and `start --resume` (rc2) both use it.
    created["FI-04"] = str(
        build_run(
            root,
            "FI-04",
            state=_stopped([seat("at-main", token=True), seat("at-tdo", token=True)]),
        )
    )

    # FI-05 — one seat has no resume token and no fresh authorization: awaiting-decision,
    # zero mutation, rc2 continuity_blocked.
    created["FI-05"] = str(
        build_run(
            root,
            "FI-05",
            state=_stopped([seat("at-main", token=False), seat("at-tdo", token=True)]),
        )
    )

    # FI-05b — a seat is ALREADY fresh outside the authorized list: mismatch, not repair.
    created["FI-05b"] = str(
        build_run(
            root,
            "FI-05b",
            state=_stopped(
                [
                    seat("at-main", token=True, actual="fresh-primed", session="present",
                         startup="ready"),
                    seat("at-qa", token=False),
                ]
            ),
            after_state=_stopped(
                [
                    seat("at-main", token=True, actual="resumed", session="present",
                         startup="ready"),
                    seat("at-qa", token=False, actual="fresh-primed", session="present",
                         startup="ready"),
                ]
            ),
        )
    )

    # FI-06 — the authorized-fresh path: one seat resumes, one is explicitly primed.
    created["FI-06"] = str(
        build_run(
            root,
            "FI-06",
            state=_stopped(
                [seat("at-main", token=True), seat("at-qa", token=False)]
            ),
            after_state=_stopped(
                [
                    seat("at-main", token=True, actual="resumed", session="present",
                         startup="ready"),
                    seat("at-qa", token=False, actual="fresh-primed", session="present",
                         startup="ready"),
                ]
            ),
        )
    )

    # FI-07 — expected resume, observed fresh: mismatch, partial written, no instantiate.
    created["FI-07"] = str(
        build_run(
            root,
            "FI-07",
            state=_stopped([seat("at-main", token=True)]),
            after_state=_stopped(
                [seat("at-main", token=True, actual="fresh-primed", session="present",
                      startup="ready")]
            ),
        )
    )

    # FI-08 — `status`: a ready-looking seat that still has no decision.
    created["FI-08"] = str(
        build_run(
            root,
            "FI-08",
            state=_stopped(
                [seat("at-main", token=False, session="detached", startup="ready")]
            ),
        )
    )

    # FI-09 — archive gate refuses the teardown.
    created["FI-09"] = str(
        build_run(
            root,
            "FI-09",
            state=_stopped([seat("at-main", token=True, session="present", startup="ready")]),
            archive="INCOMPLETE",
        )
    )
    return created


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in argv
    raw = os.environ.get(FIXTURE_ROOT_ENV, "").strip()
    if not raw:
        message = (
            f"{FIXTURE_ROOT_ENV} is unset: refusing to write fixtures into a shared "
            "location (S9-R-01). Export it to a per-verification directory."
        )
        # Coded like every other refusal in this family, so a machine runner can assert
        # the code instead of matching prose.
        payload = {
            "ok": False,
            "error": {"code": "fixture_root_unset", "message": message,
                      "hint": f"{FIXTURE_ROOT_ENV}=$(mktemp -d) .venv/bin/python tests/fixtures/s9/provision_continuity.py"},
            "rc": 2,
        }
        print(json.dumps(payload, ensure_ascii=False) if as_json else f"[FAIL] {message}")
        return 2
    created = provision(Path(raw))
    if as_json:
        print(json.dumps({"ok": True, "fixtureRoot": raw, "runs": created, "rc": 0}))
    else:
        for name, path in created.items():
            print(f"{name}: {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
