# -*- coding: utf-8 -*-
"""S10 N-CER-02 — the certification harness is testable without a live lifecycle.

What is proven here (AT-S10-CER-T-01):
  * the human gate: without `--execute` the harness refuses rc2 `human_gate_required` and
    writes NOTHING (no work dir, no evidence, no logs);
  * isolation: the work dir must be `/tmp/openrig-s10-cert-*` and must not overlap the
    control-plane home; the port comes from the declared 48110..48119 window;
  * first failure is structural: attempts never overwrite each other and a later green
    attempt can never rewrite a failed projection;
  * the archive record is BOUND to a real product MANIFEST.json by sha256 and degrades to
    INCOMPLETE (never a hand-filled COMPLETE) when that manifest is absent;
  * no row can be green without an observation (`not_attempted` is never a pass);
  * the embedded matrix cannot drift from kickoff/CERT-MATRIX.json, and the manifest key
    set cannot drift from the product's REQUIRED_TOP_KEYS.

The fake runner substitutes the PRODUCT, not the harness logic: every row still goes
through the real row functions, the real projection, and the real ledger.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

WG = Path(__file__).resolve().parents[1]
if str(WG / "scripts") not in sys.path:
    sys.path.insert(0, str(WG / "scripts"))
if str(WG / "tests") not in sys.path:
    sys.path.insert(0, str(WG / "tests"))

import openrig_certify as oc  # noqa: E402


# --------------------------------------------------------------------- helpers
def make_ctx(root: Path, *, attempt: str = "A1", port_base: int = 49110) -> dict:
    work = root / "openrig-s10-cert-unit"
    work.mkdir(parents=True, exist_ok=True)
    evidence = root / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    return {
        "workDir": work,
        "home": work / "home",
        "runDir": work / "openrig-s10-cert-unit",
        "workspace": work / "workspace",
        "marker": work / "MARKER.json",
        "archiveRoot": work / "archive",
        "evidenceDir": evidence,
        "attemptId": attempt,
        "attemptDir": evidence / "attempts" / attempt,
        "port": port_base + 1,
        "portCandidates": list(range(port_base, port_base + 10)),
        "launchId": f"cert-{attempt}",
        "rigName": "openrig-s10-cert-unit",
        "workflowId": "openrig-workflow-s10-cert-unit",
        "seatId": "cert.cert",
        "rigBin": "rig",
        "rigBinSource": "test",
        "seatSession": "cert-cert@openrig-s10-cert-unit",
        "seatPod": "cert",
        "seatMember": "cert",
        "nonce": "deadbeefcafe0001",
        "controlHome": oc.CONTROL_HOME,
        "portBase": port_base,
        "portSpan": 10,
    }


class FakeProduct:
    """A stand-in for the product CLI. Writes the artefacts a real run would produce."""

    def __init__(self, ctx: dict, *, fail_row: str | None = None,
                 plan_outcome: bool = True, down_kills_daemon: bool = False,
                 doctor_rc: int = 0, transcript_mode: str = "normal"):
        self.ctx = ctx
        self.transcript_mode = transcript_mode
        self.fail_row = fail_row
        self.plan_outcome = plan_outcome
        self.calls: list[str] = []
        self.ps_running = False
        self.daemon_up = False
        self.workflow_instances = 0
        self.down_kills_daemon = down_kills_daemon
        self.doctor_rc = doctor_rc
        self.status_state_source = "ps"

    # -- helpers ---------------------------------------------------------------
    def _json(self, payload, rc=0, stderr=""):
        return {"rc": rc, "stdout": json.dumps(payload), "stderr": stderr,
                "startedAt": oc.now_iso(), "endedAt": oc.now_iso()}

    def _text(self, text, rc=0, stderr=""):
        return {"rc": rc, "stdout": text, "stderr": stderr,
                "startedAt": oc.now_iso(), "endedAt": oc.now_iso()}

    def _seat_row(self):
        return {"logicalId": "cert", "canonicalSessionName": self.ctx["seatSession"],
                "runtime": "opencode", "startupStatus": "ready",
                "sessionStatus": "running", "resumeTokenPresent": True}

    def _write_manifest(self, run_dir: Path):
        payload = {key: None for key in oc.MANIFEST_REQUIRED_KEYS}
        payload.update({
            "schemaVersion": 1, "manifestId": "mf-1", "runId": "r", "launchId": "l",
            "revision": 1, "runContext": {"openrigHome": str(self.ctx["home"])},
            "envKeys": [], "inputs": [], "steps": [
                {"step": "daemon-start", "cmd": ["rig", "daemon", "start"], "rc": 0,
                 "stdoutSha256": "0" * 64, "startedAt": "t0", "endedAt": "t1"},
                {"step": "up", "cmd": ["rig", "up", "rig.yaml"], "rc": 0,
                 "stdoutSha256": "1" * 64, "startedAt": "t0", "endedAt": "t1"},
            ], "seats": [{"logicalId": "cert"}],
            "workflow": {"instanceId": "wf-cert-1"}, "archive": {"status": "MISSING"},
            "outputs": [], "status": "active",
        })
        path = run_dir / "reports/evidence/manifest/run-manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    # -- dispatch --------------------------------------------------------------
    def __call__(self, argv, *, env=None, cwd=None, timeout=None):
        cmd = " ".join(str(a) for a in argv)
        self.calls.append(cmd)
        row = self.fail_row

        # The seat is real work: by the time anyone reads its transcript, it has acted.
        # fail_row="CERT-02" means the seat never produced the marker.
        if self.fail_row != "CERT-02" and "transcript" in cmd and not self.marker_written():
            nonce = "wrong-nonce" if self.transcript_mode == "nonce_mismatch" else self.ctx["nonce"]
            Path(self.ctx["marker"]).write_text(
                json.dumps({"nonce": nonce, "step": "certify"}), encoding="utf-8")

        if "pgrep" in cmd or "tmux ls" in cmd:
            return self._text("")
        if "openrig_bridge.py" in cmd and "doctor" in cmd:
            if self.doctor_rc == 0:
                return self._text("PASS bridge runId=r rig=r workflow=w schema=2")
            return self._text("FAIL runId bridge=r spec=run", rc=self.doctor_rc)
        if "openrig_certify.py" in cmd:
            # The harness invoking itself for the home-conflict negative must refuse.
            return self._json({"ok": False, "rc": 2, "error": {
                "code": "work_dir_not_isolated",
                "message": "work dir overlaps the control-plane home"}}, rc=2)
        if " up " in f" {cmd} ":
            # A guarded `rig up` carrying an expired ticket.
            return self._text("", rc=2,
                              stderr="entry guard denied 'rig up' (code: entry_guard_expired)")
        if "openrig-run" in cmd or "openrig_run.py" in cmd:
            return self._product(argv, cmd, row)
        if cmd.startswith("openrig package") or "openrig-archive.py" in cmd:
            return self._archive(argv)
        if "daemon start" in cmd:
            self.daemon_up = True
            return self._json({"ok": True, "pid": 4242})
        if "daemon stop" in cmd:
            self.daemon_up = False
            return self._json({"ok": True})
        if "daemon status" in cmd:
            return (self._json({"ok": True, "state": "running"}) if self.daemon_up
                    else self._json({"ok": False, "state": "stopped"}, rc=1))
        if " down " in f" {cmd} ":
            # `rig down` stops the RIG. D-018: the daemon must survive it.
            self.ps_running = False
            if self.down_kills_daemon:
                self.daemon_up = False
            return self._json({"ok": True, "stopped": ["cert"]})
        if "ps --nodes" in cmd:
            if "openrig-s10-certification-20261116" in cmd and self.ctx["rigName"] not in cmd:
                return self._json([{"logicalId": f"s{i}", "startupStatus": "ready"}
                                   for i in range(3)])
            if not self.daemon_up:
                return self._json({"ok": False, "error": {"code": "daemon_unreachable"}},
                                  rc=1, stderr="connection refused")
            rows = [self._seat_row()] if self.ps_running else []
            return self._json(rows)
        if "queue list" in cmd:
            return self._json([{
                "qitemId": "qitem-1", "destinationSession": self.ctx["seatSession"],
                "state": "pending", "pickup": {"state": "unclaimed"},
            }] if self.ps_running else [])
        if "transcript" in cmd:
            if self.transcript_mode == "degraded":
                return self._json({"session": self.ctx["seatSession"], "lines": 400,
                                   "content": "Queue handoff: qitem-1\n[tool] shell\n[tool] write\n",
                                   "ingestHealth": {"state": "degraded", "reason": "capture_empty"}})
            if self.transcript_mode == "empty_degraded":
                return self._json({"session": self.ctx["seatSession"], "lines": 0, "content": "",
                                   "ingestHealth": {"state": "degraded", "reason": "capture_empty"}})
            if self.transcript_mode == "live_no_prompt":
                return self._json({"session": self.ctx["seatSession"], "lines": 400,
                                   "content": "Queue handoff: qitem-1\n[tool] shell\n",
                                   "ingestHealth": {"state": "live", "reason": "capture_fresh"}})
            if getattr(self, "fresh_done", False):
                # A fresh occupant: the old session's context is gone.
                return self._text("assistant: DONE (fresh session, no prior context)\n")
            if not self.marker_written():
                return self._text("")
            base = ("\nuser: write the marker for nonce deadbeefcafe0001 to "
                    "/tmp/.../MARKER.json\nassistant: DONE\n")
            return self._text(base)
        if "workflow list" in cmd:
            return self._json([{"instanceId": "wf-cert-1"}] if self.workflow_instances else [])
        if "workflow" in cmd:
            return self._json({"ok": True})
        if cmd.endswith("--version") or "--version" in cmd:
            return self._text("0.1.4")
        return self._json({"ok": True})

    def marker_written(self) -> bool:
        return Path(self.ctx["marker"]).is_file()

    def _product(self, argv, cmd, fail_row):
        args = [str(a) for a in argv]
        verb = next((a for a in args if a in
                     ("check", "start", "stop", "resume", "status", "next")), "")
        run_dir = Path(args[args.index("--run-dir") + 1]) if "--run-dir" in args else None

        if "start" == verb:
            if run_dir and run_dir.name == "partial-run":
                partial = run_dir / "reports/evidence/manifest/run-manifest.partial.json"
                partial.parent.mkdir(parents=True, exist_ok=True)
                partial.write_text(json.dumps({
                    "partial": True, "status": "failed",
                    "failure": {"step": "up", "rc": 1,
                                "unexecutedSteps": ["wait-ready", "workflow-validate"]},
                }), encoding="utf-8")
                return self._json({"ok": False, "rc": 2,
                                   "error": {"code": "up_failed"}}, rc=2)
            if run_dir and run_dir.name == "port-clash-run":
                return self._json({"ok": False, "error": {
                    "code": "port_collision", "message": "port held by another home"}}, rc=2)
            self.daemon_up = True
            self.ps_running = True
            self.workflow_instances = 1
            launch = Path(self.ctx["home"]) / "entry" / "launch.json"
            launch.parent.mkdir(parents=True, exist_ok=True)
            launch.write_text(json.dumps({"launchId": "launch-fake-1",
                                          "phase": "active", "home": str(self.ctx["home"])}),
                              encoding="utf-8")
            if run_dir:
                self._write_manifest(run_dir)
            return self._json({"ok": True, "rc": 0, "executed": [{"step": "up", "rc": 0}]})
        if "check" == verb:
            return self._json({"ok": True, "rc": 0, "checks": []})
        if "status" == verb:
            if not self.daemon_up:
                return self._json({"ok": False, "rc": 2, "error": {
                    "code": "continuity_state_unavailable",
                    "message": "ps --nodes failed"}}, rc=2)
            return self._json({
                "ok": True, "rc": 0, "decisionStatus": "allow",
                "continuity": {
                    "decisionStatus": "allow", "seats": [],
                    "stateSource": self.status_state_source,
                    "stateBefore": {"daemonState": ("running" if self.status_state_source == "ps"
                                                    else None)},
                },
            })
        if "resume" == verb:
            if "--fresh" in args and "--reason" not in args:
                return self._json({"ok": False, "rc": 2, "error": {
                    "code": "fresh_reason_missing"}}, rc=2)
            if fail_row == "CERT-03":
                return self._json({"ok": False, "rc": 2, "error": {
                    "code": "continuity_blocked",
                    "message": "resume token is unknown"}}, rc=2)
            if "--fresh" in args:
                fresh_ids = [args[i + 1] for i, a in enumerate(args)
                             if a == "--fresh" and i + 1 < len(args)]
                if any(fid != "cert.cert" for fid in fresh_ids):
                    return self._json({"ok": False, "rc": 2, "error": {
                        "code": "continuity_blocked",
                        "message": f"unknown fresh ids {fresh_ids}"}}, rc=2)
                self.fresh_done = True
            self.ps_running = True
            payload = {
                "ok": True, "rc": 0,
                "mutations": [{"step": "daemon-start", "rc": 0},
                              {"step": "up-existing", "rc": 0,
                               "argv": ["rig", "up", "rig.yaml", "--existing"]}],
                "continuity": {"decisionStatus": "allow",
                               "actualOutcomeProvenance": "up-existing-json", "seats": [
                    {"logicalId": "cert.cert", "canonicalSessionName": self.ctx["seatSession"],
                     **({"actualOutcome": ("fresh-primed" if "--fresh" in args else "resumed")}
                        if self.plan_outcome else {})}]},
            }
            return self._json(payload)
        if "stop" == verb:
            archive = (run_dir / "reports/evidence/archive/ARCHIVE-MANIFEST.json") \
                if run_dir else None
            status = ""
            if archive and archive.is_file():
                status = str(json.loads(archive.read_text()).get("status", "")).upper()
            if status != "COMPLETE":
                return self._json({"ok": False, "rc": 2,
                                   "error": {"code": "archive_incomplete"},
                                   "mutations": []}, rc=2)
            self.ps_running = False
            return self._json({"ok": True, "rc": 0,
                               "mutations": [{"step": "rig-down", "rc": 0}]})
        return self._json({"ok": True, "rc": 0})

    def _archive(self, argv):
        args = [str(a) for a in argv]
        root = Path(args[args.index("--archive-root") + 1]) if "--archive-root" in args \
            else self.ctx["archiveRoot"]
        target = root / "machines" / "host" / "runs" / "cert" / "MANIFEST.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({
            "schemaVersion": 1, "runId": "cert", "status": "COMPLETE",
            "completedAt": "2026-11-16T00:00:00Z", "files": {"run": 1},
        }), encoding="utf-8")
        return self._json({"ok": True, "manifest": str(target)})


@pytest.fixture(autouse=True)
def _no_live_residue(monkeypatch):
    """The host may carry a previous attempt's daemon; the residue gate is tested explicitly.

    Without this, every case that reaches preflight would refuse with cert_residue_detected
    for a reason that belongs to the machine, not the case under test.
    """
    # keep the real implementation reachable for the test that exercises it
    oc._stale_cert_processes_real = oc.stale_cert_processes
    monkeypatch.setattr(oc, "stale_cert_processes", lambda *a, **k: [])


@pytest.fixture()
def fake_http(monkeypatch):
    """Kept for tests that want the HTTP double standalone (see run_flow for the flow)."""

    def fake(method, port, path, *, body=None, host="127.0.0.1", timeout=10.0):
        return _fake_http(method, port, path, managed_port=None)

    monkeypatch.setattr(oc, "_http_json", fake)
    return []


def _fake_http(method: str, port: int, path: str, *, managed_port: int | None) -> dict:
    stamp = {"startedAt": oc.now_iso(), "endedAt": oc.now_iso()}
    if path.startswith("/api/compaction"):
        return {"method": method, "path": path, "status": 422,
                "body": {"ok": False, "reason": "runtime_filter"}, "raw": "{}", **stamp}
    if method == "GET":
        return {"method": method, "path": path, "status": 200, "body": {"ok": True},
                "raw": "{}", **stamp}
    if managed_port is None or port == managed_port:
        return {"method": method, "path": path, "status": 403,
                "body": {"ok": False, "error": {
                    "code": "entry_guard_http_denied",
                    "hint": "openrig-run start --run-dir <run-dir>",
                    "cause": "launch record phase is closed"}}, "raw": "{}", **stamp}
    return {"method": method, "path": path, "status": 404,
            "body": {"ok": False, "error": {"code": "seat_not_found"}}, "raw": "{}", **stamp}


def run_flow(root: Path, monkeypatch, *, attempt="A1", fail_row=None, port_base=49110,
             plan_outcome=True, down_kills_daemon=False, doctor_rc=0,
             transcript_mode="normal"):
    ctx = make_ctx(root, attempt=attempt, port_base=port_base)
    product = FakeProduct(ctx, fail_row=fail_row, plan_outcome=plan_outcome,
                          down_kills_daemon=down_kills_daemon, doctor_rc=doctor_rc,
                          transcript_mode=transcript_mode)

    def runner(argv, *, env=None, cwd=None, timeout=None):
        return product(argv, env=env, cwd=cwd, timeout=timeout)

    monkeypatch.setattr(oc, "stale_cert_processes", lambda *a, **k: [])
    monkeypatch.setattr(oc, "_listening", lambda port, host="127.0.0.1": False)
    monkeypatch.setattr(oc, "_http_json",
                        lambda method, port, path, **kw: _fake_http(
                            method, port, path, managed_port=ctx["port"]))
    cert = oc.Certifier(ctx, runner=runner, timeout=5, marker_timeout=1)
    summary = cert.execute()
    return ctx, product, cert, summary


# --------------------------------------------------------------------- the human gate
def test_without_execute_it_refuses_and_writes_nothing(tmp_path, capsys):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    work = tmp_path / "openrig-s10-cert-gate"
    before = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))

    rc = oc.main(["--work-dir", str(work), "--evidence-dir", str(evidence), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert payload["error"]["code"] == oc.CODE_HUMAN_GATE
    assert "--execute" in payload["error"]["hint"]
    assert payload["wrote"] == []
    assert not work.exists(), "the gate must not create the work dir"
    after = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))
    assert before == after, "the human gate must write nothing at all"


def test_gate_prints_the_exact_operator_command(tmp_path, capsys):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    rc = oc.main(["--work-dir", str(tmp_path / "openrig-s10-cert-gate"),
                  "--evidence-dir", str(evidence)])
    out = capsys.readouterr().out
    assert rc == 2
    assert "--execute --json" in out
    assert "CERT-01" in out


# --------------------------------------------------------------------- isolation
@pytest.mark.parametrize("work_name", ["not-cert", "openrig-workflow-x", "s10-cert"])
def test_work_dir_must_be_the_declared_shape(tmp_path, work_name):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    rc = oc.main(["--work-dir", str(tmp_path / work_name), "--evidence-dir", str(evidence),
                  "--execute", "--json"])
    assert rc == 2


def test_work_dir_may_not_overlap_the_control_home(tmp_path):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    control = tmp_path / "openrig-workflow-control"
    (control / "openrig-s10-cert-inside").mkdir(parents=True)
    payload = oc.main(["--work-dir", str(control / "openrig-s10-cert-inside"),
                       "--evidence-dir", str(evidence), "--control-home", str(control),
                       "--execute", "--json"])
    assert payload == 2


def test_preflight_reports_every_problem_before_mutating():
    ctx, problems = oc.preflight(work_dir=Path("relative/dir"),
                                evidence_dir=Path("/nonexistent/evidence"))
    assert ctx is None
    codes = {p["code"] for p in problems}
    assert oc.CODE_WORK_DIR in codes and oc.CODE_EVIDENCE in codes


def test_port_picker_skips_a_busy_port():
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen(1)
        port = busy.getsockname()[1]
        assert oc.pick_port(port, 1) is None
        picked = oc.pick_port(port, 3)
        assert picked in (port + 1, port + 2)


def test_port_exhaustion_is_a_named_refusal(tmp_path, monkeypatch):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    monkeypatch.setattr(oc, "port_is_free", lambda port, host="127.0.0.1": False)
    rc = oc.main(["--work-dir", str(tmp_path / "openrig-s10-cert-gate"),
                  "--evidence-dir", str(evidence), "--execute", "--json"])
    assert rc == 2


# --------------------------------------------------------------------- attempts
def test_existing_attempt_directory_is_refused(tmp_path, monkeypatch, capsys):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    work = tmp_path / "openrig-s10-cert-gate"
    ctx, problems = oc.preflight(work_dir=work, evidence_dir=evidence)
    assert problems == []
    Path(ctx["attemptDir"]).mkdir(parents=True)

    rc = oc.main(["--work-dir", str(work), "--evidence-dir", str(evidence), "--execute",
                  "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert payload["error"]["code"] == oc.CODE_ATTEMPT


def test_first_failure_is_preserved_across_attempts(tmp_path, monkeypatch, capsys):
    """Attempt 2 can be green; the failed projection from attempt 1 stays failed."""
    ctx1, _, _, summary1 = run_flow(tmp_path, monkeypatch, attempt="A1", fail_row="CERT-03")
    assert not summary1["ok"]
    assert summary1["firstFailure"] == "CERT-03"
    projection = json.loads((ctx1["evidenceDir"] / "CERT-03.json").read_text())
    assert projection["pass"] is False
    assert projection["attemptId"] == "A1"

    ctx2, _, _, summary2 = run_flow(tmp_path, monkeypatch, attempt="A2")
    assert summary2["ok"], "the fake product can succeed on the second attempt"
    projection = json.loads((ctx2["evidenceDir"] / "CERT-03.json").read_text())
    assert projection["attemptId"] == "A1", "projection must keep the first attempt"
    assert projection["pass"] is False, "a later green attempt may not rewrite the record"
    attempt2 = json.loads((ctx2["attemptDir"] / "CERT-03.json").read_text())
    assert attempt2["pass"] is True
    ledger = json.loads((ctx2["evidenceDir"] / "CERT-E2E.json").read_text())
    assert [a["attemptId"] for a in ledger["attempts"]] == ["A1", "A2"]
    assert ledger["counts"]["attempts"] == 2


def test_a_failed_row_stops_the_flow_without_greenwashing(tmp_path, monkeypatch):
    ctx, _, _, summary = run_flow(tmp_path, monkeypatch, fail_row="CERT-03")
    later = [r for r in summary["rows"] if r["row"] in ("CERT-04", "CERT-05", "CERT-09")]
    assert later and all(r["notAttempted"] for r in later)
    assert all(r["pass"] is False for r in later), "not attempted is never a pass"
    for r in later:
        assert r["code"] == "not_attempted"


# --------------------------------------------------------------------- rows
def test_embedded_matrix_matches_the_kickoff_matrix():
    kickoff = json.loads(
        (WG / "kickoff/openrig-s10-certification-20261116/CERT-MATRIX.json").read_text())
    assert {r["id"]: r["expect"] for r in kickoff["rows"]} == oc.ROWS
    assert tuple(kickoff["evidence"]["required"]) == oc.EVIDENCE_REQUIRED + ("FINAL.md",)


def test_manifest_key_set_matches_the_product_contract():
    import openrig_manifest as om

    assert tuple(oc.MANIFEST_REQUIRED_KEYS) == tuple(om.REQUIRED_TOP_KEYS)


def test_row_pass_requires_an_exact_expect_match(tmp_path):
    ctx = make_ctx(tmp_path)
    cert = oc.Certifier(ctx, runner=lambda *a, **k: {"rc": 0, "stdout": "", "stderr": ""})
    observed = dict(oc.ROWS["CERT-01"])
    observed["seatReady"] = False
    row = cert._row("CERT-01", scenario="s", observed=observed, commands=[], rc=0)
    assert row["pass"] is False and row["mismatched"] == ["seatReady"]


def test_unattributed_outcomes_are_recorded_as_unknown_not_guessed():
    assert oc._observe_resume(pre="", post="", seat_row={})[0] == "unknown"
    assert oc._observe_fresh(pre="", transcript="anything", seat_row={})[0] == "unknown"
    outcome, basis = oc._observe_resume(pre="line one of the old transcript\nmore",
                                       post="line one of the old transcript\nmore",
                                       seat_row={"canonicalSessionName": "cert@r"})
    assert outcome == "resumed" and "canonical session" in basis


# --------------------------------------------------------------------- archive binding
def test_archive_record_is_bound_by_sha256(tmp_path, monkeypatch):
    ctx, product, cert, summary = run_flow(tmp_path, monkeypatch)
    record_path = Path(ctx["runDir"]) / "reports/evidence/archive/ARCHIVE-MANIFEST.json"
    record = json.loads(record_path.read_text())
    product_manifest = Path(record["manifestPath"])
    assert product_manifest.is_file()
    assert record["status"] == "COMPLETE"
    assert record["manifestSha256"] == oc.sha256_file(product_manifest)
    assert record["archiveRc"] == 0


def test_missing_product_manifest_never_becomes_complete(tmp_path):
    ctx = make_ctx(tmp_path)
    cert = oc.Certifier(ctx, runner=lambda *a, **k: {"rc": 1, "stdout": "{}", "stderr": ""})
    bound = cert._bind_archive({"rc": 1, "stdout": "{}"})
    record = json.loads((Path(ctx["runDir"]) /
                         "reports/evidence/archive/ARCHIVE-MANIFEST.json").read_text())
    assert record["status"] == "INCOMPLETE"
    assert "never hand-filled" in record["reason"]
    assert bound == "unbound"


# --------------------------------------------------------------------- end to end (fake product)
def test_full_flow_records_all_rows_and_the_ledger(tmp_path, monkeypatch):
    ctx, product, cert, summary = run_flow(tmp_path, monkeypatch)
    assert summary["ok"] is True, json.dumps(summary, ensure_ascii=False)[:2000]
    assert summary["firstFailure"] is None
    assert [r["row"] for r in summary["rows"]] == oc.EXECUTION_ORDER
    for row in summary["rows"]:
        assert row["pass"] is True, row
        assert (ctx["evidenceDir"] / f"{row['row']}.json").is_file()
    ledger = json.loads((ctx["evidenceDir"] / "CERT-E2E.json").read_text())
    attempt = ledger["attempts"][0]
    assert attempt["humanGate"]["operatorApproved"] is None
    assert attempt["humanGate"]["approvalSource"] == "not verified by harness"
    assert attempt["humanGate"]["llmMayNotSelfApprove"] is True
    assert attempt["counts"] == {"rows": 10, "passed": 10, "warned": 0, "failed": 0}
    assert ledger["counts"]["attempts"] == 1
    # Every row's evidence carries rc + digests, never a bare claim.
    cert01 = json.loads((ctx["evidenceDir"] / "CERT-01.json").read_text())
    assert cert01["commands"] and all("stdoutSha256" in c for c in cert01["commands"])
    summary_file = json.loads((ctx["attemptDir"] / "summary.json").read_text())
    assert summary_file["evidenceMissing"] == []


def test_resume_row_reports_the_product_refusal_honestly(tmp_path, monkeypatch):
    """The known continuity gap (tokenState vs resumeTokenPresent) must surface as FAIL."""
    ctx, _, _, summary = run_flow(tmp_path, monkeypatch, fail_row="CERT-03")
    cert03 = json.loads((ctx["evidenceDir"] / "CERT-03.json").read_text())
    assert cert03["pass"] is False
    assert cert03["error"]["code"] == "continuity_blocked"
    assert any("continuityRc=2" in n for n in cert03["notes"])


def test_archive_gate_row_requires_a_refusal_before_the_archive(tmp_path, monkeypatch):
    ctx, _, _, summary = run_flow(tmp_path, monkeypatch)
    cert07 = json.loads((ctx["evidenceDir"] / "CERT-07.json").read_text())
    assert cert07["observed"] == {"incompleteRc": 2, "downCalls": 0, "completeRc": 0}
    assert cert07["pass"] is True


def test_no_evidence_is_deleted_by_cleanup(tmp_path, monkeypatch):
    ctx, _, _, _ = run_flow(tmp_path, monkeypatch)
    evidence_files = list(Path(ctx["evidenceDir"]).rglob("*"))
    assert evidence_files, "evidence must survive the run"
    assert Path(ctx["workDir"]).exists(), "the work dir is evidence, not garbage (D-010)"


def test_cert03_fails_closed_when_the_plan_has_no_actual_outcome(tmp_path, monkeypatch):
    """D-016 (3): a harness observation may never stand in for the plan's value.

    The transcript here WOULD support 'resumed'. If the product's CONTINUITY-PLAN has no
    actualOutcome, CERT-03 must still fail rather than borrow that inference.
    """
    ctx, _, _, summary = run_flow(tmp_path, monkeypatch, plan_outcome=False)
    assert summary["ok"] is False
    assert summary["firstFailure"] == "CERT-03"
    cert03 = json.loads((ctx["evidenceDir"] / "CERT-03.json").read_text())
    assert "continuityActualOutcome" in cert03["mismatched"]
    assert cert03["observed"]["continuityActualOutcome"] is None
    notes = " ".join(cert03["notes"])
    assert "diagnosticOnly_harnessObservation" in notes
    assert "resumed" in notes, "the diagnostic observation is still recorded"
    assert cert03["observedBasis"]["continuityActualOutcome"].startswith("CONTINUITY-PLAN")
    assert "no fallback" in cert03["observedBasis"]["continuityActualOutcome"]


def test_cert03_refuses_when_the_daemon_did_not_survive_down(tmp_path, monkeypatch):
    """D-018: resume is certified only while the daemon still runs.

    `rig down` stops the rig and must leave the daemon up, so resume is a recovery
    `up <rig> --existing`. If the daemon does not answer the read-only probe, the row
    stops with a named code and no resume is attempted.
    """
    ctx, product, _, summary = run_flow(tmp_path, monkeypatch, down_kills_daemon=True)

    assert summary["firstFailure"] == "CERT-03"
    cert03 = json.loads((ctx["evidenceDir"] / "CERT-03.json").read_text())
    assert cert03["error"]["code"] == "daemon_stopped_resume_not_certified"
    assert "no-plan" in " ".join(cert03["notes"])
    assert cert03["pass"] is False
    assert not any("openrig_run.py resume" in call for call in product.calls), \
        "a daemon-down resume must not even be attempted"
    assert any(c["label"] == "daemon-state-before-resume" for c in cert03["commands"])
    assert cert03["observed"]["daemonState"] == "unreachable"
    assert cert03["observedBasis"]["daemonStateProvenance"] == "openrig-run status --live --json"
    assert "NOT certified" in " ".join(cert03["notes"])


def test_cert03_records_the_daemon_state_probe_before_resume(tmp_path, monkeypatch):
    """D-019: CERT-03 carries daemonState from a read-only status --live before resume."""
    ctx, _, _, summary = run_flow(tmp_path, monkeypatch)
    assert summary["ok"] is True
    cert03 = json.loads((ctx["evidenceDir"] / "CERT-03.json").read_text())
    assert cert03["observed"]["daemonState"] == "running"
    labels = [c["label"] for c in cert03["commands"]]
    assert labels.index("down") < labels.index("daemon-state-before-resume") \
        < labels.index("resume"), "the probe must sit between down and resume"
    probe = next(c for c in cert03["commands"] if c["label"] == "daemon-state-before-resume")
    assert probe["argv"][1:5] == ["../scripts/openrig_run.py", "status", "--run-dir", probe["argv"][4]] \
        or probe["argv"][2:4] == ["status", "--run-dir"]
    assert "--live" in probe["argv"] and "--json" in probe["argv"]
    assert "daemonState" in cert03["observedBasis"]
    assert cert03["observedBasis"]["daemonStateProvenance"] == "openrig-run status --live --json"
    assert "status --live" in cert03["observedBasis"]["daemonState"]


def test_cert04_records_the_daemon_state_probe_before_fresh(tmp_path, monkeypatch):
    """D-019: the down->fresh cycle carries the same proof."""
    ctx, _, _, summary = run_flow(tmp_path, monkeypatch)
    assert summary["ok"] is True
    cert04 = json.loads((ctx["evidenceDir"] / "CERT-04.json").read_text())
    assert cert04["observed"]["daemonState"] == "running"
    labels = [c["label"] for c in cert04["commands"]]
    assert labels.index("down-before-fresh") < labels.index("daemon-state-before-fresh") \
        < labels.index("resume-fresh-authorized")
    assert "daemonState" in cert04["observedBasis"]
    assert cert04["observedBasis"]["daemonStateProvenance"] == "openrig-run status --live --json"
    assert "status --live" in cert04["observedBasis"]["daemonState"]


def test_cert04_refuses_a_fresh_resume_when_the_daemon_is_gone(tmp_path, monkeypatch):
    ctx, product, _, summary = run_flow(tmp_path, monkeypatch, down_kills_daemon=True)
    assert summary["firstFailure"] == "CERT-03", "CERT-03 refuses first, so CERT-04 never runs"
    cert03 = json.loads((ctx["evidenceDir"] / "CERT-03.json").read_text())
    assert cert03["observed"]["daemonState"] == "unreachable"
    assert cert03["observedBasis"]["daemonStateProvenance"] == "openrig-run status --live --json"


# --------------------------------------------------------------------- bundle layout
# Attempt 1 (2026-11-16T10:35Z) was spent on a bundle the product's own doctor refused:
# bundleDir said "openrig" (so specs resolved to run/openrig/openrig/…) and the run dir
# name did not equal bridge.runId. Both are now asserted against the REAL doctor.
def test_bundle_layout_passes_the_real_doctor(tmp_path):
    """The generator is checked by the product's doctor, not by my own reading of it."""
    import subprocess

    ctx = make_ctx(tmp_path)
    cert = oc.Certifier(ctx, runner=lambda *a, **k: {"rc": 0, "stdout": "", "stderr": ""})
    cert._write_bundle()

    bridge = json.loads((Path(ctx["runDir"]) / "openrig" / "OPENRIG-BRIDGE.json").read_text())
    assert bridge["bundleDir"] == ".", "bridge v2 wants a relative bundleDir == the bridge dir"
    assert Path(ctx["runDir"]).name == bridge["runId"], "doctor A-1: run_dir.name == runId"
    spec = Path(ctx["runDir"]) / "openrig" / bridge["bundleDir"] / bridge["workflowSpec"]
    assert spec.is_file(), f"workflowSpec must resolve inside the bundle: {spec}"

    doctor = oc.doctor_path(Path(ctx["runDir"]))
    assert doctor is not None and doctor.is_file()
    proc = subprocess.run([sys.executable, str(doctor), "doctor", "--run-dir", ctx["runDir"]],
                          capture_output=True, text=True)
    assert proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")
    assert "PASS" in proc.stdout


def test_negative_fixture_bundles_use_the_same_layout(tmp_path):
    """The controlled-failure / port-clash bundles must pass doctor too, or they would
    fail at precheck instead of at the failure they are meant to prove."""
    import subprocess

    ctx = make_ctx(tmp_path)
    cert = oc.Certifier(ctx, runner=lambda *a, **k: {"rc": 0, "stdout": "", "stderr": ""})
    run_dir = Path(ctx["workDir"]) / "partial-run"
    cert._write_minimal_bundle(run_dir, Path(ctx["workDir"]) / "partial-home", 49115,
                               valid_rig=False)

    bridge = json.loads((run_dir / "openrig" / "OPENRIG-BRIDGE.json").read_text())
    assert bridge["bundleDir"] == "."
    assert run_dir.name == bridge["runId"]
    proc = subprocess.run([sys.executable, str(oc.doctor_path(run_dir)), "doctor",
                          "--run-dir", str(run_dir)], capture_output=True, text=True)
    assert proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")


def test_cert01_fails_fast_when_the_doctor_rejects_the_bundle(tmp_path, monkeypatch):
    """An invalid bundle fails with a named code and consumes no start attempt."""
    ctx, product, _, summary = run_flow(tmp_path, monkeypatch, doctor_rc=1)

    assert summary["firstFailure"] == "CERT-01"
    cert01 = json.loads((ctx["evidenceDir"] / "CERT-01.json").read_text())
    assert cert01["error"]["code"] == "bridge_doctor_failed"
    assert cert01["rc"] == 2
    assert not any("openrig_run.py start" in call for call in product.calls), \
        "the doctor gate must run before start"
    assert any(c["label"] == "bridge-doctor" for c in cert01["commands"])
    assert "must not consume an attempt" in " ".join(cert01["notes"])


def test_real_precheck_is_green_offline_before_start(tmp_path):
    """`openrig-run check --allow-daemon-down` must already pass on the generated bundle.

    This is the offline gate that attempt 1 did not have: the whole precheck (bridge,
    render, doctor) is exercised without any lifecycle call. Safe with no daemon because
    only `context` and `up` auto-start one; `ps` merely reports it unreachable, which
    `--allow-daemon-down` downgrades to a warning.
    """
    import subprocess

    ctx = make_ctx(tmp_path)
    cert = oc.Certifier(ctx, runner=lambda *a, **k: {"rc": 0, "stdout": "", "stderr": ""})
    cert._write_bundle()

    env = {k: v for k, v in os.environ.items() if not k.startswith("OPENRIG_")}
    env["OPENRIG_HOME"] = str(ctx["home"])
    policy_fixture = WG / "tests" / "fixtures" / "historical-findings-policy.json"
    if policy_fixture.is_file():
        policy_copy = Path(ctx["runDir"]) / "openrig" / "HISTORICAL-FINDINGS-POLICY.json"
        policy_copy.parent.mkdir(parents=True, exist_ok=True)
        policy_copy.write_bytes(policy_fixture.read_bytes())
    proc = subprocess.run(
        [sys.executable, str(WG / "scripts" / "openrig_run.py"), "check",
         "--run-dir", ctx["runDir"], "--allow-daemon-down", "--json"],
        capture_output=True, text=True, env=env, timeout=300)

    payload = json.loads(proc.stdout)
    assert proc.returncode == 0, json.dumps(payload, ensure_ascii=False)[:1500]
    assert payload["ok"] is True
    status = {c["id"]: c["status"] for c in payload["checks"]}
    assert status["bridge"] == "ok"
    assert status["render"] == "ok"
    assert status["doctor"] == "ok", payload["checks"]
    assert status["seats"] in ("warn", "ok")
    assert status["workflow_validate"] in ("skipped", "ok")
    # A precheck must not consume the single-launch authorization.
    assert not (Path(ctx["home"]) / "entry" / "launch.json").exists()


def test_cert03_refuses_when_status_read_a_fixture_state(tmp_path, monkeypatch):
    """QA R-003: a continuity plan is not proof of live reachability.

    `load_observed_state` prefers a local fixture `continuity-state.json`, so a stale file
    would make `status` return a plan (stateSource='fixture') while the daemon is dead. The
    probe must refuse that: only stateSource=='ps' + stateBefore.daemonState=='running'
    counts as running.
    """
    ctx = make_ctx(tmp_path)
    product = FakeProduct(ctx, down_kills_daemon=False)
    product.status_state_source = "fixture"
    # The real trigger: a local fixture state that load_observed_state prefers over `ps`.
    cert = oc.Certifier(ctx, runner=product)
    cert._write_bundle()
    (Path(ctx["runDir"]) / "openrig" / "continuity-state.json").write_text(
        json.dumps({"daemonState": "running", "seats": []}), encoding="utf-8")

    monkeypatch.setattr(oc, "stale_cert_processes", lambda *a, **k: [])
    monkeypatch.setattr(oc, "_listening", lambda port, host="127.0.0.1": False)
    monkeypatch.setattr(oc, "_http_json",
                        lambda method, port, path, **kw: _fake_http(
                            method, port, path, managed_port=ctx["port"]))
    cert = oc.Certifier(ctx, runner=product, timeout=5, marker_timeout=1)
    summary = cert.execute()

    assert summary["firstFailure"] == "CERT-03"
    cert03 = json.loads((ctx["evidenceDir"] / "CERT-03.json").read_text())
    assert cert03["error"]["code"] == "daemon_state_not_live"
    assert cert03["observed"]["daemonState"] == "unreachable"
    assert "stateSource" in cert03["observedBasis"]["daemonState"]
    assert "state-source-not-ps" in " ".join(cert03["notes"])
    assert not any("openrig_run.py resume" in call for call in product.calls)


def test_operator_command_uses_the_pinned_interpreter(tmp_path, capsys):
    """R-004: the printed gate command must not contradict the run's .venv 3.12 pin."""
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    rc = oc.main(["--work-dir", str(tmp_path / "openrig-s10-cert-gate"),
                  "--evidence-dir", str(evidence)])
    out = capsys.readouterr().out
    assert rc == 2
    assert sys.executable in out, "the hint must print the interpreter running the harness"
    assert "python3 scripts/openrig_certify.py" not in out


# --------------------------------------------------------------------- seat naming
# attempt 2 sat in wait-ready for 600s because bridge.seatMap said
# `cert-<stamp>@<rig>` while the product derives `{pod}-{member}@{rig}`
# (session-name.ts#deriveCanonicalSessionName, "pure concatenation").
def test_bridge_seatmap_is_the_canonical_session_name(tmp_path):
    import yaml

    ctx = make_ctx(tmp_path)
    cert = oc.Certifier(ctx, runner=lambda *a, **k: {"rc": 0, "stdout": "", "stderr": ""})
    cert._write_bundle()

    rig = yaml.safe_load((Path(ctx["runDir"]) / "openrig" / "rig.yaml").read_text())
    pod = rig["pods"][0]
    member = pod["members"][0]
    expected = f"{pod['id']}-{member['id']}@{rig['name']}"
    bridge = json.loads((Path(ctx["runDir"]) / "openrig" / "OPENRIG-BRIDGE.json").read_text())

    assert bridge["seatMap"] == {member["id"]: expected}
    assert ctx["seatSession"] == expected, "the harness must look up the same name it wrote"
    assert bridge["rigName"] == rig["name"]

    workflow = yaml.safe_load((Path(ctx["runDir"]) / "openrig" / "workflow.yaml").read_text())
    roles = workflow["workflow"]["roles"]
    assert roles[member["id"]]["preferred_targets"] == [expected]


def test_minimal_bundle_seatmap_is_canonical_too(tmp_path):
    import yaml

    ctx = make_ctx(tmp_path)
    cert = oc.Certifier(ctx, runner=lambda *a, **k: {"rc": 0, "stdout": "", "stderr": ""})
    run_dir = Path(ctx["workDir"]) / "partial-run"
    cert._write_minimal_bundle(run_dir, Path(ctx["workDir"]) / "partial-home", 49115,
                               valid_rig=True)
    rig = yaml.safe_load((run_dir / "openrig" / "rig.yaml").read_text())
    pod = rig["pods"][0]
    member = pod["members"][0]
    bridge = json.loads((run_dir / "openrig" / "OPENRIG-BRIDGE.json").read_text())

    assert bridge["seatMap"] == {member["id"]: f"{pod['id']}-{member['id']}@{rig['name']}"}


# ------------------------------------------------- attempt-2 cleanup residue
def test_preflight_refuses_to_inherit_a_previous_attempt(tmp_path, monkeypatch):
    """QA cleanup flag: a failed attempt leaves daemon/seat alive; the next must not inherit."""
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    monkeypatch.setattr(oc, "stale_cert_processes", lambda *a, **k: [
        {"pid": 4242, "cmd": "/tmp/openrig-s10-cert-A/home ... daemon"},
        {"pid": 4243, "cmd": "node ... cli-agent-runner.js --session-name cert-cert@..."},
    ])
    rc = oc.main(["--work-dir", str(tmp_path / "openrig-s10-cert-next"),
                  "--evidence-dir", str(evidence), "--execute", "--json"])
    assert rc == 2
    _, problems = oc.preflight(work_dir=tmp_path / "openrig-s10-cert-next",
                               evidence_dir=evidence)
    assert problems and problems[0]["code"] == oc.CODE_RESIDUE
    assert "pid 4242" in problems[0]["message"]


def test_failure_path_teardown_stops_the_cert_daemon_and_is_recorded(tmp_path, monkeypatch):
    """A failure before CERT-07 must not leak a live daemon/seat (attempt 2 did)."""
    ctx, product, cert, summary = run_flow(tmp_path, monkeypatch, fail_row="CERT-02")

    assert summary["firstFailure"] == "CERT-02"
    teardown = summary["failureTeardown"]
    assert teardown and teardown["failedRow"] == "CERT-02"
    steps = [m["step"] for m in teardown["mutations"]]
    assert steps == ["rig-down", "daemon-stop"]
    assert any(f"down {ctx['rigName']}" in call for call in product.calls)
    assert any("daemon stop" in call for call in product.calls)
    ledger = json.loads((ctx["evidenceDir"] / "CERT-E2E.json").read_text())
    assert ledger["attempts"][0]["failureTeardown"]["failedRow"] == "CERT-02"


def test_failure_path_teardown_never_targets_the_control_rig(tmp_path, monkeypatch):
    ctx = make_ctx(tmp_path)
    cert = oc.Certifier(ctx, runner=lambda *a, **k: {"rc": 0, "stdout": "", "stderr": ""})
    cert.ctx["rigName"] = oc.CONTROL_RIG
    assert cert.teardown_after_failure(failed_row="CERT-02") == []



def test_control_plane_probe_uses_the_control_home_not_the_cert_home(tmp_path):
    """P-026: a harness-env `rig ps` looked for the default daemon, not port 48010."""
    ctx = make_ctx(tmp_path)
    cert = oc.Certifier(ctx, runner=lambda *a, **k: {"rc": 0, "stdout": "", "stderr": ""})
    env = cert.control_env()
    assert env["OPENRIG_HOME"] == str(oc.CONTROL_HOME)
    assert env["OPENRIG_PORT"] == "48010"
    assert env["OPENRIG_URL"] == "http://127.0.0.1:48010"
    assert env["OPENRIG_HOME"] != str(ctx["home"])

def test_rig_bin_ignores_env_and_rejects_a_seat_wrapper(tmp_path, monkeypatch):
    """A seat's wrapper must never become the cert harness's rig binary."""
    ctx = make_ctx(tmp_path)
    cert = oc.Certifier(ctx, runner=lambda *a, **k: {"rc": 0, "stdout": "", "stderr": ""})
    monkeypatch.setenv("OPENRIG_RIG_BIN", "/tmp/openrig-workflow-x/seat-bin/rig")
    assert cert.rig() == ["rig"], "the ambient OPENRIG_RIG_BIN must not be read"

    wrapper = tmp_path / "seat-bin" / "hash" / "rig"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text("#!/bin/sh\n", encoding="utf-8")
    wrapper.chmod(0o755)

    # an operator pointing at a seat wrapper is refused by name, not silently rerouted
    with pytest.raises(oc.RigBinRefused) as exc:
        oc.resolve_rig_bin(str(wrapper))
    assert exc.value.code == oc.CODE_RIG_BIN_WRAPPER
    assert "must not drive another seat" in exc.value.message

    # and when the ONLY candidate is a wrapper, there is no silent fallback to a bare name
    monkeypatch.setattr(oc.shutil, "which", lambda name: str(wrapper))
    monkeypatch.setattr(oc.Path, "home", classmethod(lambda cls: tmp_path))
    with pytest.raises(oc.RigBinRefused) as exc:
        oc.resolve_rig_bin()
    assert exc.value.code == oc.CODE_RIG_BIN_WRAPPER
    assert "--rig-bin" in exc.value.message, "the refusal must name the fix"

    explicit, source = oc.resolve_rig_bin("/opt/rig/bin/rig")
    assert explicit == ["/opt/rig/bin/rig"] and source.startswith("explicit")


def test_residue_detection_is_by_ownership_not_by_text(tmp_path, monkeypatch):
    """An agent that merely mentions a cert path is not residue.

    Regression: the first detector grepped command lines for the prefix and matched my own
    seat, whose conversation quoted a cert path — it would have refused a clean attempt.
    """
    proc_root = tmp_path / "proc"
    (proc_root / "101").mkdir(parents=True)     # a leaked cert daemon: owns a cert home
    (proc_root / "101" / "cmdline").write_bytes(
        b"/usr/bin/node\0/path/daemon.js\0--port\048110\0")
    (proc_root / "101" / "environ").write_bytes(
        b"OPENRIG_HOME=/tmp/openrig-s10-cert-OLDA/home\0PATH=/usr/bin\0")
    (proc_root / "102").mkdir()                 # an agent quoting the path in its argv
    (proc_root / "102" / "cmdline").write_bytes(
        b"/usr/bin/opencode\0run\0--note\0/tmp/openrig-s10-cert-OLDA/run/MARKER.json\0")
    (proc_root / "102" / "environ").write_bytes(
        b"OPENRIG_HOME=/tmp/openrig-workflow-control/home\0")
    (proc_root / "103").mkdir()                 # a cert seat runner via --state-root
    (proc_root / "103" / "cmdline").write_bytes(
        b"node\0cli-agent-runner.js\0--state-root\0/tmp/openrig-s10-cert-OLDA/home/state/opencode\0")
    (proc_root / "103" / "environ").write_bytes(b"PATH=/usr/bin\0")

    found = {p["pid"]: p["reason"] for p in oc._stale_cert_processes_real(proc_root)}
    assert set(found) == {101, 103}, found
    assert found[101].startswith("OPENRIG_HOME=")
    assert found[103].startswith("--state-root")


def test_preflight_refuses_a_seat_wrapper_rig_bin(tmp_path):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    rc = oc.main(["--work-dir", str(tmp_path / "openrig-s10-cert-gate"),
                  "--evidence-dir", str(evidence), "--execute", "--json",
                  "--rig-bin", "/tmp/openrig-workflow-x/run/seat-bin/deadbeef/rig"])
    assert rc == 2


def test_attempt_ledger_records_which_binary_ran(tmp_path, monkeypatch):
    ctx, _, _, _ = run_flow(tmp_path, monkeypatch)
    ledger = json.loads((ctx["evidenceDir"] / "CERT-E2E.json").read_text())
    attempt = ledger["attempts"][0]
    assert attempt["rigBin"] == ctx["rigBin"]
    assert attempt["rigBinSource"] == ctx["rigBinSource"]


def test_warn_row_continues_and_marks_pass_with_warn(tmp_path, monkeypatch):
    """P-013: a degraded transcript is a WARN row, not a stop; later rows still run."""
    ctx, _, _, summary = run_flow(tmp_path, monkeypatch, transcript_mode="degraded")
    cert02 = json.loads((ctx["attemptDir"] / "CERT-02.json").read_text())
    assert cert02["pass"] is False and cert02["warn"] is True
    assert cert02["observed"]["transcriptHasPrompt"] is False
    later = [r for r in summary["rows"] if r["row"] == "CERT-03"]
    assert later and not later[0].get("notAttempted"), "the flow must continue past a WARN"
    assert summary["status"] == "pass-with-warn"
    assert summary["ok"] is True, "a WARN row is not a failure"


@pytest.mark.parametrize("mode,warn_expected", [
    ("nonce_mismatch", False),
    ("empty_degraded", False),
    ("live_no_prompt", False),
])
def test_cert02_warn_requires_nonce_and_handoff_and_degraded_capture(tmp_path, monkeypatch, mode, warn_expected):
    ctx, _, _, summary = run_flow(tmp_path, monkeypatch, transcript_mode=mode)
    cert02 = json.loads((ctx["attemptDir"] / "CERT-02.json").read_text())
    assert cert02["pass"] is False
    assert cert02["warn"] is warn_expected
    assert cert02["observed"]["transcriptHasPrompt"] in (True, False)


def test_warn_then_later_failure_is_overall_fail(tmp_path, monkeypatch):
    ctx, _, _, summary = run_flow(tmp_path, monkeypatch, transcript_mode="degraded",
                                  fail_row="CERT-03")
    cert02 = json.loads((ctx["attemptDir"] / "CERT-02.json").read_text())
    assert cert02["warn"] is True and cert02["pass"] is False
    assert summary["ok"] is False
    assert summary["status"] == "fail"
    assert summary["firstFailure"] == "CERT-03"


def test_fresh_uses_the_product_logical_id(tmp_path, monkeypatch):
    """CERT-04 --fresh must name the pod.member logical id, not the bare member."""
    ctx, product, _, summary = run_flow(tmp_path, monkeypatch)
    assert summary["ok"] is True
    assert any("--fresh cert.cert" in c for c in product.calls), product.calls


def test_ledger_does_not_claim_operator_approval(tmp_path, monkeypatch):
    ctx, _, _, _ = run_flow(tmp_path, monkeypatch)
    ledger = json.loads((ctx["evidenceDir"] / "CERT-E2E.json").read_text())
    gate = ledger["attempts"][-1]["humanGate"]
    assert gate["operatorApproved"] is None, "the harness must not attest approval it cannot see"
    assert gate["approvalSource"] == "not verified by harness"
    assert "executorSession" in gate


def test_ledger_records_loaded_harness_and_tests_sha(tmp_path, monkeypatch):
    ctx, _, _, summary = run_flow(tmp_path, monkeypatch)
    assert summary["harnessSha256"] == oc.sha256_file(Path(oc.__file__).resolve())
    assert summary["harnessTestsSha256"] == oc.sha256_file(
        Path(oc.__file__).resolve().parent.parent / "tests" / "test_openrig_certify.py")
    ledger = json.loads((ctx["evidenceDir"] / "CERT-E2E.json").read_text())
    attempt = ledger["attempts"][-1]
    assert attempt["harnessSha256"] == summary["harnessSha256"]
    assert attempt["harnessTestsSha256"] == summary["harnessTestsSha256"]
    assert attempt["harnessTestsPath"].endswith("test_openrig_certify.py")


def test_close_ticket_uses_the_live_launch_record_id(tmp_path, monkeypatch):
    import openrig_run as orr
    ctx = make_ctx(tmp_path)
    home = Path(ctx["home"])
    (home / "entry").mkdir(parents=True)
    (home / "entry" / "launch.json").write_text(json.dumps({"launchId": "launch-live-1"}))
    seen = {}
    def fake_close(h, lid, reason):
        seen.update(home=h, launch_id=lid)
        (Path(h) / "entry" / "launch.json").write_text(json.dumps({"launchId": lid, "phase": "closed"}))
        return True
    monkeypatch.setattr(orr, "close_entry_records", fake_close)
    cert = oc.Certifier(ctx, runner=lambda *a, **k: {"rc": 0, "stdout": "", "stderr": ""})
    row = cert._close_ticket()
    assert row["rc"] == 0
    assert seen["launch_id"] == "launch-live-1", "must use the live record id, not ctx.launchId"


def test_close_ticket_requires_closed_phase(tmp_path, monkeypatch):
    import openrig_run as orr
    ctx = make_ctx(tmp_path)
    home = Path(ctx["home"])
    (home / "entry").mkdir(parents=True)
    (home / "entry" / "launch.json").write_text(json.dumps({"launchId": "launch-live-1", "phase": "active"}))
    monkeypatch.setattr(orr, "close_entry_records", lambda h, lid, reason: True)
    cert = oc.Certifier(ctx, runner=lambda *a, **k: {"rc": 0, "stdout": "", "stderr": ""})
    row = cert._close_ticket()
    assert row["rc"] == 1, "a true return with phase=active is not a closed ticket"


# ------------------------------------------------- P-023: CERT-07 must still salvage
def test_cert07_failure_runs_salvage(tmp_path, monkeypatch):
    """Attempt 10: CERT-07 failed at the archive bind, salvage was skipped, rig stayed live."""
    ctx = make_ctx(tmp_path)
    monkeypatch.setattr(oc, "stale_cert_processes", lambda *a, **k: [])
    cert = oc.Certifier(ctx, runner=lambda *a, **k: {"rc": 0, "stdout": "", "stderr": ""})
    calls: list[str] = []

    def fake_teardown(*, failed_row):
        calls.append(failed_row)
        cert.failureTeardown = {"failedRow": failed_row, "residueRemaining": False,
                                "clean": True, "mutations": []}
        return []

    monkeypatch.setattr(cert, "teardown_after_failure", fake_teardown)
    monkeypatch.setattr(cert, "_project", lambda row: None)   # hand-built rows, no evidence files
    def ok_row(cid):
        return {"row": cid, "pass": True, "warn": False, "rc": 0, "mismatched": []}

    for name, cid in (("cert_01_start", "CERT-01"), ("cert_02_prompt", "CERT-02"),
                      ("cert_03_resume", "CERT-03"), ("cert_04_fresh", "CERT-04"),
                      ("cert_05_manifest", "CERT-05"), ("cert_06_http", "CERT-06"),
                      ("cert_08_negatives", "CERT-08")):
        monkeypatch.setattr(cert, name, lambda cid=cid: ok_row(cid))
    monkeypatch.setattr(cert, "cert_07_archive_gate", lambda: {
        "row": "CERT-07", "pass": False, "warn": False, "rc": 2, "mismatched": [],
        "error": {"code": "archive_incomplete"}})
    cert.execute()

    assert "CERT-07" in calls, "a CERT-07 failure must still run salvage"


def test_salvage_skips_rig_down_when_nothing_is_live(tmp_path, monkeypatch):
    """When the stop already tore down, record that instead of downing a second time."""
    ctx = make_ctx(tmp_path)
    calls: list[str] = []
    cert = oc.Certifier(ctx, runner=lambda argv, **k: (
        calls.append(" ".join(map(str, argv))) or {"rc": 0, "stdout": "", "stderr": ""}))
    monkeypatch.setattr(oc, "stale_cert_processes", lambda *a, **k: [])
    monkeypatch.setattr(oc, "port_is_free", lambda *a, **k: True)

    done = cert.teardown_after_failure(failed_row="CERT-07")

    assert done == []
    assert not any(" down " in f" {c} " for c in calls), calls
    payload = json.loads((Path(ctx["attemptDir"]) / "teardown.json").read_text())
    assert payload["clean"] is True and payload["mutations"] == []
    assert "already torn it down" in payload["note"]


def test_restore_launch_phase_success_and_failure(tmp_path, monkeypatch):
    ctx = make_ctx(tmp_path)
    path = Path(ctx["home"]) / "entry" / "launch.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"launchId": "launch-1", "phase": "closed"}))
    assert oc._restore_launch_phase(path, "active") is True
    assert json.loads(path.read_text())["phase"] == "active"

    def boom(*a, **k):
        raise OSError("write failed")
    monkeypatch.setattr(oc, "write_json", boom)
    assert oc._restore_launch_phase(path, "active") is False


# --------------------------------------------------- P-024: the restore-failure path
def test_cert06_reports_ticket_restore_failed_without_a_name_error(tmp_path, monkeypatch):
    """QA P-024: the false path used handler_calls before it was assigned -> NameError.

    The row must carry the named code (not a harness_exception), and the failure must land on
    CERT-06 rather than poisoning CERT-07.
    """
    ctx = make_ctx(tmp_path)
    entry = Path(ctx["home"]) / "entry"
    entry.mkdir(parents=True)
    record = {"schemaVersion": 1, "launchId": "launch-cert", "home": str(ctx["home"]),
              "runId": "r", "phase": "active", "expiresAt": "2999-01-01T00:00:00Z",
              "verbs": [], "consumed": []}
    (entry / "launch.json").write_text(json.dumps(record), encoding="utf-8")

    cert = oc.Certifier(ctx, runner=lambda *a, **k: {"rc": 0, "stdout": "", "stderr": ""})
    def fake_close():
        # the close marks the record closed; original_phase was captured BEFORE this
        (entry / "launch.json").write_text(json.dumps({**record, "phase": "closed"}),
                                           encoding="utf-8")
        return {"label": "close-ticket", "argv": ["x"], "rc": 0, "stdoutSha256": "0" * 64,
                "stderrSha256": "0" * 64, "stdoutBytes": 1, "stderrTail": [],
                "startedAt": oc.now_iso(), "endedAt": oc.now_iso(), "log": "-", "errLog": "-"}

    monkeypatch.setattr(cert, "_close_ticket", fake_close)
    # the product's close does not touch our file, and the restore write is a no-op:
    # the read-back therefore still sees 'active' vs the expected 'starting' -> mismatch
    monkeypatch.setattr(oc, "write_json", lambda *a, **k: Path(a[0]))
    monkeypatch.setattr(oc, "_http_json", lambda m, p, path, **kw: {
        "method": m, "path": path, "status": 403 if m == "POST" else 200,
        "body": {"error": {"code": "entry_guard_http_denied", "hint": "openrig-run start"}}
        if m == "POST" else {"ok": True},
        "raw": "{}", "startedAt": oc.now_iso(), "endedAt": oc.now_iso()})
    row = cert.cert_06_http()

    assert row["error"]["code"] == "ticket_restore_failed", row.get("error")
    assert row["pass"] is False
    assert isinstance(row["observed"]["handlerCalls"], int), "no NameError on the false path"


def test_cert06_restores_the_ticket_phase_on_success(tmp_path, monkeypatch):
    """The close is probe-only: after the probe the record must be back to its own phase."""
    ctx = make_ctx(tmp_path)
    entry = Path(ctx["home"]) / "entry"
    entry.mkdir(parents=True)
    record = {"schemaVersion": 1, "launchId": "launch-cert", "home": str(ctx["home"]),
              "runId": "r", "phase": "active", "expiresAt": "2999-01-01T00:00:00Z",
              "verbs": [], "consumed": []}
    (entry / "launch.json").write_text(json.dumps(record), encoding="utf-8")

    cert = oc.Certifier(ctx, runner=lambda *a, **k: {"rc": 0, "stdout": "", "stderr": ""})

    def fake_close():
        (entry / "launch.json").write_text(json.dumps({**record, "phase": "closed"}),
                                           encoding="utf-8")
        return {"label": "close-ticket", "argv": ["x"], "rc": 0, "stdoutSha256": "0" * 64,
                "stderrSha256": "0" * 64, "stdoutBytes": 1, "stderrTail": [],
                "startedAt": oc.now_iso(), "endedAt": oc.now_iso(), "log": "-", "errLog": "-"}

    monkeypatch.setattr(cert, "_close_ticket", fake_close)
    monkeypatch.setattr(oc, "_http_json", lambda m, p, path, **kw: {
        "method": m, "path": path, "status": 403 if m == "POST" else 200,
        "body": {"error": {"code": "entry_guard_http_denied", "hint": "openrig-run start"}}
        if m == "POST" else {"ok": True},
        "raw": "{}", "startedAt": oc.now_iso(), "endedAt": oc.now_iso()})

    row = cert.cert_06_http()

    assert row["observed"]["ticketPhaseRestored"] is True, row["observed"]
    assert json.loads((entry / "launch.json").read_text())["phase"] == "active"


def test_cert06_reports_ticket_restore_failed(tmp_path, monkeypatch):
    ctx = make_ctx(tmp_path)
    launch = Path(ctx["home"]) / "entry" / "launch.json"
    launch.parent.mkdir(parents=True)
    launch.write_text(json.dumps({"launchId": "launch-1", "phase": "active"}))
    cert = oc.Certifier(ctx, runner=lambda *a, **k: {"rc": 0, "stdout": "", "stderr": ""})

    monkeypatch.setattr(cert, "_close_ticket", lambda: {
        "rc": 0, "label": "close-ticket", "argv": [], "stdoutSha256": "0" * 64,
        "stderrSha256": "0" * 64, "stdoutBytes": 6, "stderrTail": [],
        "startedAt": "t0", "endedAt": "t1", "log": "l", "errLog": "e"})
    monkeypatch.setattr(oc, "_restore_launch_phase", lambda path, phase: False)
    monkeypatch.setattr(oc, "_http_json", lambda method, port, path, **kw: {
        "method": method, "path": path, "status": 403 if method == "POST" else 200,
        "body": {"error": {"code": "entry_guard_http_denied"}}, "raw": "{}"})
    monkeypatch.setattr(cert, "run", lambda *a, **k: {
        "rc": 0, "stdout": "{}", "stderr": "", "argv": [], "stdoutSha256": "0" * 64,
        "stderrSha256": "0" * 64, "stdoutBytes": 2, "stderrTail": [], "log": "l"})
    monkeypatch.setattr(oc, "pick_port", lambda *a, **k: 49999)

    row = cert.cert_06_http()
    assert row["error"]["code"] == "ticket_restore_failed"
    assert row["observed"]["ticketPhaseRestored"] is False


# --------------------------------------------------------------------- launch verbs
def test_cert_launch_record_authorizes_startup_and_repeatable_continuation_verbs(tmp_path):
    """The cert writer must be in lockstep with openrig_run's 11-verb ticket.

    A managed cert seat closes workflow steps with `rig workflow project` and may
    route/resume/abort/revise repeatedly under the same live launch record.  The
    cert harness has its own launch-record writer (`_stale_launch_probe`); pin its
    written bytes to the same authorization set as the product supervisor.
    """
    import openrig_run as orr

    ctx = make_ctx(tmp_path)
    cert = oc.Certifier(
        ctx,
        runner=lambda argv, *, env=None, cwd=None, timeout=None: {
            "rc": 0,
            "stdout": "entry guard denied (code: entry_guard_expired)\n",
            "stderr": "",
            "startedAt": oc.now_iso(),
            "endedAt": oc.now_iso(),
        },
    )
    probe = cert._stale_launch_probe()
    record = json.loads(
        (Path(ctx["workDir"]) / "stale-home" / "entry" / "launch.json").read_text(
            encoding="utf-8"
        )
    )

    assert probe["codeSeen"] == "entry_guard_expired"
    assert oc.STARTUP_ENTRY_VERBS == orr.STARTUP_ENTRY_VERBS
    assert oc.CONTINUATION_ENTRY_VERBS == orr.CONTINUATION_ENTRY_VERBS
    assert oc.ENTRY_VERBS == orr.ENTRY_VERBS
    assert len(record["verbs"]) == 11
    assert set(record["verbs"]) == set(orr.STARTUP_ENTRY_VERBS + orr.CONTINUATION_ENTRY_VERBS)
    assert set(oc.STARTUP_ENTRY_VERBS) <= set(record["verbs"])
    assert set(oc.CONTINUATION_ENTRY_VERBS) <= set(record["verbs"])
    assert "workflow-project" in record["verbs"]
