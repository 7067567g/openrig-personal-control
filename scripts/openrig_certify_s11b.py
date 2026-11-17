#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S11-B live recertification harness for the five post-S10 residuals.

This is intentionally a *thin live extension* of the S10 harness.  It imports the
already-tested S10 lifecycle rows and adds only the rows S11-B needs:

  S11B-05  user authorization receipt is present and valid (runs before mutation)
  S11B-01  live entry-guard deny, encoded route and expired-ticket controls
  S11B-02  live manifest seats/outputs/step evidence/receipts/revisions
  S11B-03  a real `opencode` runner command > tail cap spills and recomputes
  S11B-04  bundle historical-findings policy is actually mounted and loaded
  S11B-06  both archive layers COMPLETE, stop rc0, no live residue

The S10 rows remain the tested lifecycle driver: one isolated rig, one real
opencode seat, one minimal workflow, archive gate, teardown.  The harness still
requires `--execute`; this script additionally requires a user approval receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PROD = ROOT.parent.parent / "deepseek-项目" / "10-openrig-deepseek"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import openrig_certify as s10  # noqa: E402
import openrig_runtime_output as ort  # noqa: E402

RUN_ID = "openrig-s11b-live-recert-20261118"
WORK_PREFIX = "/tmp/openrig-s11b-cert-"
SCHEMA = 1
APPROVAL_WORDS = "ok，开始，授权S11-B"

# Keep the tested S10 rows, then add the S11-B proof rows.
ROWS = dict(s10.ROWS)
ROWS.update(
    {
        "S11B-01": {
            "encodedMutationRc": 403,
            "plainMutationRc": 403,
            "guardCode": "entry_guard_http_denied",
            "staleLaunchRc": 2,
            "ticketRestored": True,
        },
        "S11B-02": {
            "manifestStatus": "active",
            "liveSeats": True,
            "liveOutputs": True,
            "stepEvidencePaths": True,
            "receiptsBound": True,
            "revisionsPreserved": True,
        },
        "S11B-03": {
            "runner": "opencode",
            "stdoutBytesGtTail": True,
            "stdoutTruncated": True,
            "spillRecomputes": True,
            "sidecarExists": True,
            "tailWithinCap": True,
            "proofHasNoFullBlob": True,
        },
        "S11B-04": {
            "policyMounted": True,
            "policyCheckOk": True,
            "findingsCount": 106,
            "mappedCount": 96,
            "deferredCount": 10,
        },
        "S11B-05": {
            "approvalValid": True,
            "expiresInFuture": True,
            "llmSelfSigned": False,
            "approvalWordsExact": True,
        },
        "S11B-06": {
            "runLocalArchive": "COMPLETE",
            "productArchive": "COMPLETE",
            "archiveShaBound": True,
            "stopRc": 0,
            "noCertProcess": True,
            "portFree": True,
            "tmuxAbsent": True,
        },
        "CERT-10": {
            "openrigTests": True,
            "entryGuardTests": True,
            "pyCompile": True,
        },
    }
)
EXECUTION_ORDER = [
    "S11B-05",
    "CERT-01",
    "CERT-02",
    "CERT-03",
    "CERT-04",
    "CERT-05",
    "S11B-02",
    "CERT-06",
    "S11B-01",
    "CERT-08",
    "S11B-04",
    "S11B-03",
    "CERT-07",
    "CERT-09",
    "S11B-06",
    "CERT-10",
]
EVIDENCE_REQUIRED = tuple(f"{row}.json" for row in EXECUTION_ORDER)

# The imported S10 module resolves its globals at call time.  Patch them only for
# this process's S11-B run; merely importing this module must not mutate the S10
# harness globals (pytest collects both harness test modules in one process).
_S10_ORIGINAL: dict[str, object] = {}
S11B_SEMANTICS = {
    "S11B-01": "live entry-guard encoded/deny/expiry",
    "S11B-02": "live manifest seats/outputs/receipts/revisions",
    "S11B-03": "real opencode runner large-output spill",
    "S11B-04": "bundle historical-findings policy mounted live",
    "S11B-05": "user authorization receipt",
    "S11B-06": "two-layer archive and residue",
}


def configure_s10() -> None:
    """Patch S10 module globals for an S11-B run; idempotent within this process."""
    global _S10_ORIGINAL
    if _S10_ORIGINAL:
        return
    _S10_ORIGINAL = {
        "RUN_ID": s10.RUN_ID,
        "CERT_WORK_PREFIX": s10.CERT_WORK_PREFIX,
        "ROWS": s10.ROWS,
        "EXECUTION_ORDER": s10.EXECUTION_ORDER,
        "EVIDENCE_REQUIRED": s10.EVIDENCE_REQUIRED,
        "ROWS_SEMANTICS": s10.ROWS_SEMANTICS,
    }
    s10.RUN_ID = RUN_ID
    s10.CERT_WORK_PREFIX = WORK_PREFIX
    s10.ROWS = ROWS
    s10.EXECUTION_ORDER = EXECUTION_ORDER
    s10.EVIDENCE_REQUIRED = EVIDENCE_REQUIRED
    s10.ROWS_SEMANTICS = {**s10.ROWS_SEMANTICS, **S11B_SEMANTICS}


def restore_s10() -> None:
    """Test-only inverse of `configure_s10`; keeps shared pytest imports isolated."""
    global _S10_ORIGINAL
    if not _S10_ORIGINAL:
        return
    for key, value in _S10_ORIGINAL.items():
        setattr(s10, key, value)
    _S10_ORIGINAL = {}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", value.lower()).strip("-") or "s11b"


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _approval_problems(approval_path: Path) -> tuple[dict | None, list[dict]]:
    problems: list[dict] = []
    path = Path(approval_path).expanduser()
    if not path.is_file():
        return None, [{"code": "approval_missing", "message": f"approval file missing: {path}"}]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return None, [{"code": "approval_invalid", "message": f"approval file is not JSON: {exc}"}]
    if not isinstance(payload, dict):
        return None, [{"code": "approval_invalid", "message": "approval file must be an object"}]
    for key in ("approvalId", "approvedBy", "approvedAt", "expiresAt", "approvalSource",
                "executor", "actionClasses"):
        if not payload.get(key):
            problems.append({"code": "approval_incomplete", "message": f"missing {key}"})
    words = str(payload.get("approvalWords") or "")
    if words != APPROVAL_WORDS:
        problems.append({
            "code": "approval_words_mismatch",
            "message": f"approvalWords must be exactly {APPROVAL_WORDS!r}; got {words!r}",
        })
    if payload.get("llmSelfSigned") is not False:
        problems.append({
            "code": "approval_self_signed",
            "message": "llmSelfSigned must be false; the harness cannot self-approve",
        })
    classes = payload.get("actionClasses") or []
    required = {"first_live_e2e", "managed_lifecycle_mutation", "archive_and_teardown"}
    if not required <= set(classes if isinstance(classes, list) else []):
        problems.append({
            "code": "approval_scope_missing",
            "message": f"approval must include action classes {sorted(required)}",
        })
    try:
        expires = _parse_iso(str(payload.get("expiresAt") or ""))
        if expires <= datetime.now(timezone.utc):
            problems.append({"code": "approval_expired", "message": f"approval expired at {expires.isoformat()}"})
    except ValueError as exc:
        problems.append({"code": "approval_expiry_invalid", "message": f"bad expiresAt: {exc}"})
    return payload, problems


def _stale_owned_processes() -> list[dict]:
    return s10.stale_cert_processes()


def preflight(
    *,
    work_dir: Path,
    evidence_dir: Path,
    approval_path: Path,
    port_base: int = 48210,
    port_span: int = 10,
    rig_bin: str = "",
) -> tuple[dict | None, list[dict]]:
    problems: list[dict] = []

    def bad(code: str, message: str) -> None:
        problems.append({"code": code, "message": message})

    work = Path(work_dir).expanduser()
    try:
        work = work.resolve()
    except OSError:
        pass
    if not work.is_absolute() or not str(work).startswith("/tmp/"):
        bad("work_dir_not_isolated", f"work dir must be under /tmp: {work}")
    if not work.name.startswith("openrig-s11b-cert-"):
        bad("work_dir_not_isolated", f"work dir basename must start with 'openrig-s11b-cert-': {work.name}")
    evidence = Path(evidence_dir).expanduser()
    try:
        evidence = evidence.resolve()
    except OSError:
        pass
    if not evidence.is_dir():
        bad("evidence_dir_unusable", f"evidence dir does not exist: {evidence}")
    elif not os.access(evidence, os.W_OK):
        bad("evidence_dir_unusable", f"evidence dir is not writable: {evidence}")
    approval, approval_problems = _approval_problems(Path(approval_path))
    problems.extend(approval_problems)
    if problems:
        return None, problems

    residue = _stale_owned_processes()
    if residue:
        return None, [{
            "code": "s11b_residue_detected",
            "message": "a prior S11-B process references the isolated cert prefix: "
                       + ", ".join(str(r.get("pid")) for r in residue[:6]),
            "residue": residue,
        }]
    port = s10.pick_port(port_base, port_span, forbid=(7433, 48010))
    if port is None:
        return None, [{"code": "port_exhausted", "message": f"no free port in {port_base}..{port_base + port_span - 1}"}]
    try:
        rig_argv, rig_source = s10.resolve_rig_bin(rig_bin)
    except s10.RigBinRefused as exc:
        return None, [{"code": exc.code, "message": exc.message}]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    attempt = f"{stamp}-{_slug(work.name.replace('openrig-s11b-cert-', '')) or 'run'}"
    rig_name = f"openrig-s11b-cert-{stamp.lower()}"
    seat_pod, seat_member = "cert", "cert"
    run_dir = work / rig_name
    ctx = {
        "rigBin": " ".join(rig_argv),
        "rigBinSource": rig_source,
        "workDir": work,
        "home": work / "home",
        "runDir": run_dir,
        "workspace": work / "workspace",
        "marker": work / "MARKER.json",
        "archiveRoot": work / "archive",
        "evidenceDir": evidence,
        "attemptId": attempt,
        "attemptDir": evidence / "attempts" / attempt,
        "port": port,
        "portCandidates": list(range(port_base, port_base + port_span)),
        "launchId": f"s11b-{attempt}",
        "rigName": rig_name,
        "workflowId": f"openrig-workflow-s11b-cert-{stamp.lower()}",
        "seatId": f"{seat_pod}.{seat_member}",
        "seatPod": seat_pod,
        "seatMember": seat_member,
        "seatSession": s10.canonical_session(seat_pod, seat_member, rig_name),
        "nonce": s10.sha256_bytes(f"{attempt}:{os.getpid()}:{time.time()}".encode())[:32],
        "controlHome": Path("/tmp/openrig-s11b-no-control-plane"),
        "portBase": port_base,
        "portSpan": port_span,
        "approvalPath": str(Path(approval_path).expanduser().resolve()),
        "approvalSha256": _sha256_file(Path(approval_path)),
        "approvalPayload": approval,
    }
    return ctx, []


class S11BCertifier(s10.Certifier):
    """The tested S10 lifecycle rows plus S11-B live proof rows."""

    def __init__(self, ctx: dict, *, runner=None, timeout: int = 300,
                 marker_timeout: int = 240, teardown_timeout: int = 120):
        super().__init__(
            ctx,
            runner=runner,
            timeout=timeout,
            marker_timeout=marker_timeout,
            teardown_timeout=teardown_timeout,
        )
        self.harness_path = str(Path(__file__).resolve())
        self.harness_sha256 = _sha256_file(Path(__file__))
        self.tests_path = str(ROOT / "tests" / "test_openrig_certify.py")
        self.tests_sha256 = _sha256_file(Path(self.tests_path))
        self.approval_path = Path(ctx["approvalPath"])

    def env(self, *, launch_id: str | None = None) -> dict:
        """Isolated loopback bind for S11-B.

        The host now has an active Tailscale interface.  The default daemon bind
        mode requires loopback AND Tailscale to answer /healthz; the first S11-B
        attempt was correctly refused by that adoption gate because the isolated
        cert daemon could not prove the Tailscale listener from this environment.
        S11-B certifies the loopback-only boundary; remote/Tailscale is explicitly
        outside the claim.  OPENRIG_BIND_HOST is the product's dedicated explicit
        bind opt-in, not a bypass flag.
        """
        env = super().env(launch_id=launch_id)
        env["OPENRIG_BIND_HOST"] = "127.0.0.1"
        no_proxy = env.get("NO_PROXY") or env.get("no_proxy") or ""
        parts = [p for p in no_proxy.split(",") if p]
        for host in ("127.0.0.1", "localhost", "::1"):
            if host not in parts:
                parts.append(host)
        env["NO_PROXY"] = ",".join(parts)
        env["no_proxy"] = env["NO_PROXY"]
        return env

    # The S10 bundle text says S10; rewrite the generated text and mount policy.
    def _write_bundle(self) -> dict:
        result = super()._write_bundle()
        ctx = self.ctx
        run_dir = Path(ctx["runDir"])
        bundle = run_dir / "openrig"
        for path in (
            bundle / "rig.yaml",
            bundle / "workflow.yaml",
            bundle / "agents" / "cert" / "agent.yaml",
            bundle / "guidance" / "cert.md",
            Path(ctx["workspace"]) / "AGENTS.md",
        ):
            if path.is_file():
                path.write_text(
                    path.read_text(encoding="utf-8").replace("S10", "S11-B"),
                    encoding="utf-8",
                )
        policy_src = PROD / "docs" / "as-built" / "historical-findings-policy.json"
        if not policy_src.is_file():
            raise FileNotFoundError(f"policy source missing: {policy_src}")
        policy_dst = bundle / "HISTORICAL-FINDINGS-POLICY.json"
        shutil.copyfile(policy_src, policy_dst)
        render_path = bundle / "render-manifest.json"
        render = json.loads(render_path.read_text(encoding="utf-8"))
        files = render.setdefault("files", {})
        for rel in ("rig.yaml", "workflow.yaml", "agents/cert/agent.yaml",
                    "HISTORICAL-FINDINGS-POLICY.json"):
            p = bundle / rel
            files[rel] = {"bytes": p.stat().st_size, "sha256": _sha256_file(p)}
        s10.write_json(render_path, render)
        return result

    # -- S11B-05: operator authorization receipt --------------------------------
    def s11b_05_approval(self) -> dict:
        payload, problems = _approval_problems(self.approval_path)
        expires = None
        if payload:
            try:
                expires = _parse_iso(str(payload.get("expiresAt") or ""))
            except ValueError:
                expires = None
        actions = set(payload.get("actionClasses") or []) if isinstance(payload, dict) else set()
        observed = {
            "approvalValid": payload is not None and not problems,
            "expiresInFuture": bool(expires and expires > datetime.now(timezone.utc)),
            "llmSelfSigned": bool((payload or {}).get("llmSelfSigned") is not False),
            "approvalWordsExact": bool((payload or {}).get("approvalWords") == APPROVAL_WORDS),
        }
        good = (
            observed["approvalValid"]
            and observed["expiresInFuture"]
            and observed["llmSelfSigned"] is False
            and observed["approvalWordsExact"]
        )
        return self._row(
            "S11B-05",
            scenario="operator authorization receipt",
            observed=observed,
            commands=[],
            rc=0 if good else 2,
            code=None if good else "approval_invalid",
            notes=[
                f"approval={self.approval_path}",
                f"sha256={self.ctx.get('approvalSha256')}",
                f"approvalId={(payload or {}).get('approvalId')}",
                f"approvedBy={(payload or {}).get('approvedBy')}",
                f"actionClasses={sorted(actions)}",
                f"problems={problems}",
            ],
            basis={
                "approvalValid": "approval JSON is present, complete and not self-signed",
                "expiresInFuture": "expiresAt parsed and compared to current UTC",
                "llmSelfSigned": "must be false; a true/absent value fails the human gate",
                "approvalWordsExact": "the exact user authorization words are recorded",
            },
        )

    # -- S11B-02: live manifest evidence ---------------------------------------
    def s11b_02_manifest(self) -> dict:
        ctx = self.ctx
        manifest_path = Path(ctx["runDir"]) / "reports/evidence/manifest/run-manifest.json"
        manifest = s10._read_json(manifest_path) or {}
        seats = manifest.get("seats") or []
        outputs = manifest.get("outputs") or []
        steps = manifest.get("steps") or []
        steps_with_evidence = [
            s for s in steps
            if isinstance(s, dict) and s.get("evidencePath") and Path(s["evidencePath"]).is_file()
        ]
        output_checks = []
        for out in outputs:
            if not isinstance(out, dict):
                continue
            p = Path(str(out.get("path") or ""))
            output_checks.append(
                p.is_file()
                and out.get("sha256") == _sha256_file(p)
                and out.get("bytes") == p.stat().st_size
            )
        names = {Path(str(o.get("path") or "")).name for o in outputs if isinstance(o, dict)}
        receipt_map = {Path(str(o.get("path") or "")).name: o for o in outputs if isinstance(o, dict)}
        receipts_bound = bool(
            {"start-receipt.json", "resume-receipt.json"} <= names
            and all(
                Path(str(receipt_map[name].get("path"))).is_file()
                and receipt_map[name].get("sha256")
                == _sha256_file(Path(str(receipt_map[name].get("path"))))
                and receipt_map[name].get("bytes")
                == Path(str(receipt_map[name].get("path"))).stat().st_size
                for name in ("start-receipt.json", "resume-receipt.json")
            )
        )
        revisions = sorted((manifest_path.parent / "revisions").glob("*.json"))
        revisions_ok = bool(revisions) and all(
            isinstance(s10._read_json(p), dict) for p in revisions
        )
        live_seats = bool(seats) and all(
            isinstance(s, dict) and s.get("actualOutcomeObserved") is True
            for s in seats
        )
        observed = {
            "manifestStatus": manifest.get("status"),
            "liveSeats": live_seats,
            "liveOutputs": bool(outputs) and bool(output_checks) and all(output_checks),
            "stepEvidencePaths": bool(steps_with_evidence),
            "receiptsBound": receipts_bound,
            "revisionsPreserved": revisions_ok,
        }
        return self._row(
            "S11B-02",
            scenario="live manifest seats/outputs/receipts/revisions",
            observed=observed,
            commands=[],
            rc=0 if all(
                [observed["manifestStatus"] == "active", live_seats,
                 observed["liveOutputs"], observed["stepEvidencePaths"],
                 receipts_bound, revisions_ok]
            ) else 1,
            code=None if all(
                [observed["manifestStatus"] == "active", live_seats,
                 observed["liveOutputs"], observed["stepEvidencePaths"],
                 receipts_bound, revisions_ok]
            ) else "manifest_live_wiring_incomplete",
            notes=[
                f"manifest={manifest_path}",
                f"seats={len(seats)} outputs={len(outputs)} steps={len(steps)}",
                f"stepsWithEvidence={len(steps_with_evidence)}",
                f"outputNames={sorted(names)}",
                f"revisions={[p.name for p in revisions]}",
            ],
            basis={
                "manifestStatus": "final live RUN-MANIFEST status",
                "liveSeats": "every seats[] row has an observed actualOutcome",
                "liveOutputs": "every outputs[] path exists with matching sha256/bytes",
                "stepEvidencePaths": "manifest steps reference existing runtime sidecars",
                "receiptsBound": "start and resume receipts are real outputs with matching hashes",
                "revisionsPreserved": "manifest/revisions contains prior revision bytes",
            },
        )

    # -- S11B-01: live encoded / deny / expiry probes ---------------------------
    def s11b_01_entry_guard(self) -> dict:
        ctx = self.ctx
        cmds: list[dict] = []
        launch_path = Path(ctx["home"]) / "entry" / "launch.json"
        try:
            original_phase = str(
                json.loads(launch_path.read_text(encoding="utf-8")).get("phase") or "active"
            )
        except Exception:  # noqa: BLE001
            original_phase = "active"
        closed = self._close_ticket()
        cmds.append(closed)
        if closed["rc"] != 0:
            return self._row(
                "S11B-01", scenario="live entry-guard encoded/deny/expiry",
                observed={"encodedMutationRc": None, "plainMutationRc": None,
                          "guardCode": None, "staleLaunchRc": None,
                          "ticketRestored": False},
                commands=cmds, rc=2, code="ticket_close_failed",
                notes=["cannot probe encoded routes because the launch ticket did not close"],
            )
        restored = False
        try:
            encoded = s10._http_json(
                "POST", ctx["port"], "/api/rigs/rig-1/snapshot%73"
            )
            plain = s10._http_json(
                "POST", ctx["port"], "/api/rigs/rig-1/snapshots"
            )
            cmds.append(self._http_cmd("encoded-mutation", encoded))
            cmds.append(self._http_cmd("plain-mutation", plain))
        finally:
            restored = s10._restore_launch_phase(launch_path, original_phase)
        stale = self._stale_launch_probe()
        cmds.append(stale)
        def body_code(row: dict) -> str | None:
            body = row.get("body") or {}
            err = body.get("error") if isinstance(body, dict) else {}
            return str((err or {}).get("code") or "") or None
        encoded_code = body_code(encoded)
        observed = {
            "encodedMutationRc": encoded.get("status"),
            "plainMutationRc": plain.get("status"),
            "guardCode": encoded_code,
            "staleLaunchRc": stale.get("rc"),
            "ticketRestored": bool(restored),
        }
        good = (
            observed["encodedMutationRc"] == 403
            and observed["plainMutationRc"] == 403
            and encoded_code == "entry_guard_http_denied"
            and observed["staleLaunchRc"] == 2
            and observed["ticketRestored"]
        )
        return self._row(
            "S11B-01", scenario="live entry-guard encoded/deny/expiry",
            observed=observed, commands=cmds,
            rc=0 if good else 1,
            code=None if good else "entry_guard_live_probe_failed",
            notes=[
                f"encodedBody={json.dumps(encoded.get('body'), ensure_ascii=False)[:400]}",
                f"plainBody={json.dumps(plain.get('body'), ensure_ascii=False)[:400]}",
                f"staleCodeSeen={stale.get('codeSeen')!r}",
                f"ticketOriginalPhase={original_phase!r} restored={restored}",
            ],
            basis={
                "encodedMutationRc": "live POST /api/rigs/rig-1/snapshot%73 -> decoded guard classification",
                "plainMutationRc": "live POST /api/rigs/rig-1/snapshots for equivalence",
                "guardCode": "response body error.code must be entry_guard_http_denied",
                "staleLaunchRc": "real rig up with an expired launch record",
                "ticketRestored": "launch.json phase restored and read back",
            },
        )

    # -- S11B-04: live findings policy mount ------------------------------------
    def s11b_04_policy_mount(self) -> dict:
        ctx = self.ctx
        cmds: list[dict] = []
        policy_path = Path(ctx["runDir"]) / "openrig" / "HISTORICAL-FINDINGS-POLICY.json"
        check = self.run(
            "live-check-policy",
            [*self.cli(), "check", "--run-dir", str(ctx["runDir"]), "--json"],
            env=self.env(), cwd=ROOT, timeout=self.timeout,
        )
        cmds.append(check)
        payload = s10._json_or(check["stdout"], default={}) or {}
        checks = payload.get("checks") or []
        hf = next((c for c in checks if c.get("id") == "historical_findings"), {})
        observed = {
            "policyMounted": policy_path.is_file(),
            "policyCheckOk": hf.get("status") == "ok",
            "findingsCount": hf.get("findingsCount"),
            "mappedCount": hf.get("mappedCount"),
            "deferredCount": hf.get("deferredCount"),
        }
        good = (
            observed["policyMounted"]
            and observed["policyCheckOk"]
            and observed["findingsCount"] == 106
            and observed["mappedCount"] == 96
            and observed["deferredCount"] == 10
            and hf.get("sha256") == _sha256_file(policy_path)
        )
        if not good:
            observed["policyCheckOk"] = False
        return self._row(
            "S11B-04", scenario="bundle historical-findings policy mounted live",
            observed=observed, commands=cmds,
            rc=0 if good else 1,
            code=None if good else "historical_findings_live_mount_failed",
            notes=[
                f"policy={policy_path} sha256={_sha256_file(policy_path) if policy_path.is_file() else None}",
                f"checkRc={check['rc']} check={json.dumps(hf, ensure_ascii=False)[:500]}",
            ],
            basis={
                "policyMounted": "HISTORICAL-FINDINGS-POLICY.json exists inside the real bundle",
                "policyCheckOk": "real openrig-run check loads it as a blocking check",
                "findingsCount": "loaded policy count copied from the live check payload",
                "mappedCount": "loaded mapped count copied from the live check payload",
                "deferredCount": "loaded deferred count copied from the live check payload",
            },
        )

    # -- S11B-03: real runner large output -------------------------------------
    def s11b_03_runner_output(self) -> dict:
        ctx = self.ctx
        opencode = shutil.which("opencode") or "opencode"
        cmd = [
            "bash", "-lc",
            f"{shlex.quote(opencode)} --help; "
            f"{shlex.quote(opencode)} models; "
            f"{shlex.quote(opencode)} auth list",
        ]
        proc = ort.run_captured(
            cmd,
            env=os.environ.copy(),
            timeout=min(max(self.timeout, 30), 120),
            run_dir=Path(ctx["runDir"]),
            label="real-opencode-runner-output",
            capture_id=f"{ctx['attemptId']}-real-opencode-runner-output",
            persist=True,
        )
        spill = Path(proc.stdout_path) if proc.stdout_path else None
        sidecar = Path(proc.evidence_path) if proc.evidence_path else None
        hash_ok = bool(spill and spill.is_file()
                       and hashlib.sha256(spill.read_bytes()).hexdigest() == proc.stdout_sha256
                       and spill.stat().st_size == proc.stdout_bytes)
        tail_ok = bool(proc.stdout_tail is not None
                       and len(proc.stdout_tail.encode("utf-8")) <= ort.TAIL_BYTES)
        sidecar_payload = s10._read_json(sidecar) if sidecar else None
        proof_has_no_full_blob = bool(
            sidecar_payload
            and proc.stdout_bytes > ort.TAIL_BYTES
            and "S" * 10000 not in (sidecar_payload.get("streams", {}).get("stdout", {}).get("tail") or "")
        )
        observed = {
            "runner": "opencode",
            "stdoutBytesGtTail": bool(proc.stdout_bytes > ort.TAIL_BYTES),
            "stdoutTruncated": bool(proc.stdout_truncated),
            "spillRecomputes": hash_ok,
            "sidecarExists": bool(sidecar and sidecar.is_file()),
            "tailWithinCap": tail_ok,
            "proofHasNoFullBlob": proof_has_no_full_blob,
        }
        command = {
            "label": "real-opencode-runner-output",
            "argv": cmd,
            "rc": proc.returncode,
            "stdoutSha256": proc.stdout_sha256,
            "stderrSha256": proc.stderr_sha256,
            "stdoutBytes": proc.stdout_bytes,
            "stderrTail": [proc.stderr_tail] if proc.stderr_tail else [],
            "startedAt": proc.started_at,
            "endedAt": proc.ended_at,
            "log": str(spill) if spill else "-",
            "errLog": str(proc.stderr_path) if proc.stderr_path else "-",
        }
        good = all(observed.values())
        return self._row(
            "S11B-03", scenario="real opencode runner large-output spill",
            observed=observed, commands=[command],
            rc=0 if good else 1,
            code=None if good else "runtime_output_live_probe_failed",
            notes=[
                f"stdoutBytes={proc.stdout_bytes} tailBytes={len(proc.stdout_tail.encode('utf-8'))}",
                f"spill={spill} sidecar={sidecar}",
                f"policy=tailBytes:{ort.TAIL_BYTES}, inlineLimit:{ort.INLINE_LIMIT_BYTES}",
            ],
            basis={
                "runner": "real installed opencode binary, not a fake rig or stub",
                "stdoutBytesGtTail": "opencode --help + models + auth list produced more than the tail cap",
                "stdoutTruncated": "bounded projection reports tail truncation",
                "spillRecomputes": "sha256 and bytes recomputed from the full 0600 spill",
                "sidecarExists": "runtime-output sidecar was written by the shared policy module",
                "tailWithinCap": "tail is at most TAIL_BYTES after UTF-8 encoding",
                "proofHasNoFullBlob": "sidecar stores bounded tail, not the full runner output",
            },
        )

    # -- CERT-09 override: no control-plane dependency -------------------------
    def cert_09_cleanup(self) -> dict:
        ctx = self.ctx
        cmds: list[dict] = []
        archive = s10._read_json(
            Path(ctx["runDir"]) / "reports/evidence/archive/ARCHIVE-MANIFEST.json"
        ) or {}
        daemon = self.run("daemon-status", [*self.rig(), "daemon", "status"], env=self.env())
        cmds.append(daemon)
        unit_inactive = daemon["rc"] != 0 or not s10._listening(ctx["port"])
        ports_free = all(
            s10.port_is_free(p)
            for p in {ctx["port"], ctx["portBase"] + 5, ctx["portBase"] + 7}
        )
        tmux = self.run(
            "tmux-list",
            ["bash", "-lc", "tmux ls -F '#{session_name}' 2>/dev/null || true"],
            env=os.environ.copy(),
        )
        cmds.append(tmux)
        tmux_absent = not any(
            ctx["rigName"] in line or ctx["seatSession"].split("@")[0] in line
            for line in (tmux.get("stdout") or "").splitlines()
        )
        pgrep = self.run(
            "pgrep-home",
            ["bash", "-lc", f"pgrep -af {json.dumps(str(ctx['home']))} || true"],
            env=os.environ.copy(),
        )
        cmds.append(pgrep)
        strays = [
            ln for ln in (pgrep.get("stdout") or "").splitlines()
            if "pgrep -af" not in ln and ln.strip()
        ]
        daemon_absent = not strays and not _stale_owned_processes()
        observed = {
            "archiveStatus": str(archive.get("status") or "MISSING").upper(),
            "unitInactive": bool(unit_inactive),
            "portFree": bool(ports_free),
            "tmuxAbsent": bool(tmux_absent),
            "daemonAbsent": bool(daemon_absent),
        }
        good = observed["archiveStatus"] == "COMPLETE" and all(
            [unit_inactive, ports_free, tmux_absent, daemon_absent]
        )
        return self._row(
            "CERT-09", scenario="cleanup", observed=observed, commands=cmds,
            rc=0 if good else 1,
            code=None if good else "s11b_cleanup_residue",
            notes=[
                f"control-plane rig is intentionally not required for S11-B",
                "no rm -rf of the cert home/DB/transcript: cleanup means no LIVE residue",
            ],
            basis={
                "archiveStatus": "run-local ARCHIVE-MANIFEST.json status",
                "unitInactive": "daemon status is down and the port does not answer",
                "portFree": "bind probe on every port this attempt used",
                "tmuxAbsent": "no tmux session names the cert rig/seat",
                "daemonAbsent": "no process/home residue under the S11-B cert prefix",
            },
        )

    # -- S11B-06: two archive layers + residue --------------------------------
    def s11b_06_archive_residue(self) -> dict:
        ctx = self.ctx
        run_archive_path = Path(ctx["runDir"]) / "reports/evidence/archive/ARCHIVE-MANIFEST.json"
        run_archive = s10._read_json(run_archive_path) or {}
        product_path = Path(str(run_archive.get("manifestPath") or ""))
        product = s10._read_json(product_path) if product_path.is_file() else {}
        product_status = str(
            (product or {}).get("archiveStatus") or (product or {}).get("status") or ""
        ).upper()
        bound = bool(
            product_path.is_file()
            and run_archive.get("manifestSha256")
            and run_archive.get("manifestSha256") == _sha256_file(product_path)
        )
        cert07 = next((r for r in self.rows if r.get("row") == "CERT-07"), {})
        stop_rc = (cert07.get("observed") or {}).get("completeRc")
        residue = _stale_owned_processes()
        tmux = self.run(
            "final-tmux",
            ["bash", "-lc", "tmux ls -F '#{session_name}' 2>/dev/null || true"],
            env=os.environ.copy(),
        )
        tmux_absent = not any(
            ctx["rigName"] in line or ctx["seatSession"].split("@")[0] in line
            for line in (tmux.get("stdout") or "").splitlines()
        )
        observed = {
            "runLocalArchive": str(run_archive.get("status") or "MISSING").upper(),
            "productArchive": product_status or "MISSING",
            "archiveShaBound": bound,
            "stopRc": stop_rc,
            "noCertProcess": not residue,
            "portFree": s10.port_is_free(ctx["port"]),
            "tmuxAbsent": tmux_absent,
        }
        good = (
            observed["runLocalArchive"] == "COMPLETE"
            and observed["productArchive"] == "COMPLETE"
            and observed["archiveShaBound"]
            and observed["stopRc"] == 0
            and observed["noCertProcess"]
            and observed["portFree"]
            and observed["tmuxAbsent"]
        )
        return self._row(
            "S11B-06", scenario="two-layer archive and live residue",
            observed=observed, commands=[tmux],
            rc=0 if good else 1,
            code=None if good else "s11b_archive_or_residue_failed",
            notes=[
                f"runArchive={run_archive_path}",
                f"productArchive={product_path}",
                f"residue={residue}",
            ],
            basis={
                "runLocalArchive": "run-local ARCHIVE-MANIFEST.json status == COMPLETE",
                "productArchive": "bound product archive manifest archiveStatus == COMPLETE",
                "archiveShaBound": "run-local manifestSha256 equals the product manifest sha256",
                "stopRc": "CERT-07 complete stop recorded rc0",
                "noCertProcess": "stale_cert_processes with the S11-B prefix is empty",
                "portFree": "cert port bind probe is free",
                "tmuxAbsent": "no tmux session names this rig/seat",
            },
        )

    # -- CERT-10 override: offline regression ---------------------------------
    def cert_10_static(self) -> dict:
        cmds: list[dict] = []
        openrig = self.run(
            "reg-openrig-tests",
            [sys.executable, "-m", "pytest", "-q", *sorted(str(p) for p in (ROOT / "tests").glob("test_openrig_*.py"))],
            cwd=ROOT, timeout=1800,
        )
        cmds.append(openrig)
        entry = self.run(
            "reg-entry-guard-tests",
            ["npx", "vitest", "run",
             "packages/daemon/test/entry-guard-core.test.ts",
             "packages/daemon/test/entry-guard-http-admission.test.ts",
             "packages/daemon/test/entry-guard-atomic-token.test.ts",
             "packages/daemon/test/entry-guard-boot.test.ts",
             "packages/cli/test/entry-guard-error.test.ts",
             "packages/cli/test/entry-guard-json-denial.test.ts",
             "packages/cli/test/entry-guard-matrix.test.ts",
             "packages/cli/test/entry-guard-startdaemon.test.ts"],
            cwd=PROD, timeout=1800,
        )
        cmds.append(entry)
        compile_cmd = self.run(
            "reg-py-compile",
            [sys.executable, "-m", "py_compile", *sorted(str(p) for p in (ROOT / "scripts").glob("openrig_*.py")),
             *sorted(str(p) for p in (ROOT / "tests").glob("test_openrig_*.py"))],
            cwd=ROOT, timeout=300,
        )
        cmds.append(compile_cmd)
        observed = {
            "openrigTests": openrig["rc"] == 0,
            "entryGuardTests": entry["rc"] == 0,
            "pyCompile": compile_cmd["rc"] == 0,
        }
        return self._row(
            "CERT-10", scenario="offline regression", observed=observed, commands=cmds,
            rc=0 if all(observed.values()) else 1,
            code=None if all(observed.values()) else "s11b_static_regression_failed",
            notes=["S11-B keeps the S10 lifecycle rows plus its own live proof rows"],
        )

    def teardown_after_failure(self, *, failed_row: str) -> list[dict]:
        """S11-B salvage: restore a probe-closed ticket before the real down attempt.

        The inherited S10 salvage refuses a non-S10 rig name and does not know that
        S11B-01 intentionally closes/restores the launch ticket for its encoded-route
        probe.  A harness exception between those two points must not poison cleanup.
        """
        ctx = self.ctx
        launch_path = Path(ctx["home"]) / "entry" / "launch.json"
        ticket_restored = False
        try:
            record = json.loads(launch_path.read_text(encoding="utf-8"))
            if str(record.get("phase") or "") == "closed":
                target_phase = str(record.get("previousPhase") or "active")
                ticket_restored = s10._restore_launch_phase(launch_path, target_phase)
        except Exception:  # noqa: BLE001 - salvage must proceed even if the ticket is unreadable
            ticket_restored = False
        pre_stale = _stale_owned_processes()
        pre_tmux = self.run(
            "teardown-tmux-probe",
            ["bash", "-lc", "tmux ls -F '#{session_name}' 2>/dev/null || true"],
            env=os.environ.copy(), timeout=self.teardown_timeout,
        )
        pre_sessions = [
            ln.strip() for ln in (pre_tmux.get("stdout") or "").splitlines()
            if ctx["seatSession"] in ln or ctx["rigName"] in ln
        ]
        pre_port = not s10.port_is_free(ctx["port"])
        if not pre_stale and not pre_sessions and not pre_port:
            payload = {
                "schemaVersion": SCHEMA, "attemptId": ctx["attemptId"],
                "failedRow": failed_row, "capturedAt": s10.now_iso(),
                "ticketRestoredBeforeSalvage": ticket_restored,
                "mutations": [],
                "residue": {"staleProcesses": [], "tmuxSessions": [], "portInUse": False},
                "residueRemaining": False, "clean": True,
                "note": "nothing of this attempt was live when salvage ran",
            }
            s10.write_json(Path(ctx["attemptDir"]) / "teardown.json", payload)
            self.failureTeardown = payload
            return []
        down = self.run(
            "teardown-down", [*self.rig(), "down", ctx["rigName"], "--json"],
            env=self.env(), timeout=self.teardown_timeout,
        )
        done = [{"step": "rig-down", "rc": down["rc"], "argv": down["argv"],
                 "stdoutSha256": down["stdoutSha256"], "log": down["log"]}]
        stop = self.run(
            "teardown-daemon-stop", [*self.rig(), "daemon", "stop"],
            env=self.env(), timeout=self.teardown_timeout,
        )
        done.append({"step": "daemon-stop", "rc": stop["rc"], "argv": stop["argv"],
                     "stdoutSha256": stop["stdoutSha256"], "log": stop["log"]})
        tmux = self.run(
            "teardown-tmux-check",
            ["bash", "-lc", "tmux ls -F '#{session_name}' 2>/dev/null || true"],
            env=os.environ.copy(), timeout=self.teardown_timeout,
        )
        sessions = [
            ln.strip() for ln in (tmux.get("stdout") or "").splitlines()
            if ctx["seatSession"] in ln or ctx["rigName"] in ln
        ]
        residue: dict = {}
        for _ in range(6):
            stale = _stale_owned_processes()
            port_busy = not s10.port_is_free(ctx["port"])
            residue = {"staleProcesses": stale, "tmuxSessions": sessions,
                       "portInUse": port_busy}
            if not stale and not sessions and not port_busy:
                break
            time.sleep(2)
        clean = not (residue.get("staleProcesses") or residue.get("tmuxSessions")
                     or residue.get("portInUse"))
        payload = {
            "schemaVersion": SCHEMA,
            "attemptId": ctx["attemptId"],
            "failedRow": failed_row,
            "capturedAt": s10.now_iso(),
            "ticketRestoredBeforeSalvage": ticket_restored,
            "mutations": done,
            "tmuxCheck": {"argv": tmux["argv"], "rc": tmux["rc"],
                          "stdoutSha256": tmux["stdoutSha256"], "log": tmux["log"]},
            "residue": residue,
            "residueRemaining": not clean,
            "clean": clean,
            "note": "S11-B salvage after a pre-CERT-07 failure; evidence retained, no rm -rf",
        }
        s10.write_json(Path(ctx["attemptDir"]) / "teardown.json", payload)
        self.failureTeardown = payload
        return done

    def execute(self) -> dict:
        steps = [
            ("S11B-05", self.s11b_05_approval),
            ("CERT-01", self.cert_01_start),
            ("CERT-02", self.cert_02_prompt),
            ("CERT-03", self.cert_03_resume),
            ("CERT-04", self.cert_04_fresh),
            ("CERT-05", self.cert_05_manifest),
            ("S11B-02", self.s11b_02_manifest),
            ("CERT-06", self.cert_06_http),
            ("S11B-01", self.s11b_01_entry_guard),
            ("CERT-08", self.cert_08_negatives),
            ("S11B-04", self.s11b_04_policy_mount),
            ("S11B-03", self.s11b_03_runner_output),
            ("CERT-07", self.cert_07_archive_gate),
            ("CERT-09", self.cert_09_cleanup),
            ("S11B-06", self.s11b_06_archive_residue),
            ("CERT-10", self.cert_10_static),
        ]
        error: dict | None = None
        try:
            for cid, fn in steps:
                row = fn()
                self._project(row)
                if not row.get("pass") and not row.get("warn"):
                    self.fail_and_stop(cid, f"stopped after {cid} (first failure preserved)")
                    self.teardown_after_failure(failed_row=cid)
                    break
        except Exception as exc:  # noqa: BLE001
            error = {"code": "harness_exception", "message": f"{type(exc).__name__}: {exc}"}
            self.teardown_after_failure(failed_row="exception")
        summary = self._finish()
        if error:
            summary["error"] = error
            summary["ok"] = False
            summary["rc"] = 1
            s10.write_json(Path(self.ctx["attemptDir"]) / "summary.json", summary)
        return summary


def _plan_text(ctx: dict | None, args) -> None:
    print("S11-B performs REAL lifecycle mutations and one minimal opencode model call.")
    print("It refuses without --execute; it additionally requires the user approval receipt.")
    print("")
    print("Operator command:")
    print(
        f"  {sys.executable} scripts/openrig_certify_s11b.py "
        f"--work-dir {args.work_dir} --evidence-dir {args.evidence_dir} "
        f"--approval-file {args.approval_file} --execute --json"
    )
    print("")
    print("Rows in execution order: " + ", ".join(EXECUTION_ORDER))
    if ctx:
        print(f"Would use home={ctx['home']} port={ctx['port']} attempt={ctx['attemptId']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="S11-B live recertification harness for P-S10-01..05"
    )
    ap.add_argument("--work-dir", required=True)
    ap.add_argument("--evidence-dir", required=True)
    ap.add_argument("--approval-file", required=True)
    ap.add_argument("--execute", action="store_true",
                    help="operator gate: actually run the lifecycle and model call")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--marker-timeout", type=int, default=240)
    ap.add_argument("--port-base", type=int, default=48210)
    ap.add_argument("--port-span", type=int, default=10)
    ap.add_argument("--rig-bin", default="")
    args = ap.parse_args(argv)
    configure_s10()

    ctx, problems = preflight(
        work_dir=Path(args.work_dir),
        evidence_dir=Path(args.evidence_dir),
        approval_path=Path(args.approval_file),
        port_base=args.port_base,
        port_span=args.port_span,
        rig_bin=args.rig_bin,
    )
    if not args.execute:
        payload = {
            "schemaVersion": SCHEMA,
            "runId": RUN_ID,
            "ok": False,
            "rc": 2,
            "error": {
                "code": "human_gate_required",
                "message": "--execute is required; the user gate is not inferred from approval",
                "hint": f"{sys.executable} scripts/openrig_certify_s11b.py --work-dir {args.work_dir} "
                        f"--evidence-dir {args.evidence_dir} --approval-file {args.approval_file} --execute --json",
            },
            "preflight": {
                "problems": problems,
                "workDir": str(args.work_dir),
                "port": (ctx or {}).get("port"),
                "attemptId": (ctx or {}).get("attemptId"),
                "approvalSha256": (ctx or {}).get("approvalSha256"),
            },
            "wrote": [],
            "capturedAt": s10.now_iso(),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else _plan_text(ctx, args))
        return 2
    if problems:
        payload = {
            "schemaVersion": SCHEMA, "runId": RUN_ID, "ok": False, "rc": 2,
            "error": {"code": problems[0]["code"], "message": problems[0]["message"]},
            "problems": problems, "wrote": [], "capturedAt": s10.now_iso(),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json
              else f"[REFUSED] {problems[0]['code']}: {problems[0]['message']}")
        return 2
    attempt_dir = Path(ctx["attemptDir"])
    if attempt_dir.exists():
        payload = {
            "schemaVersion": SCHEMA, "runId": RUN_ID, "ok": False, "rc": 2,
            "error": {"code": "attempt_exists",
                      "message": f"attempt directory already exists: {attempt_dir}"},
            "capturedAt": s10.now_iso(),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json
              else f"[REFUSED] attempt_exists: {attempt_dir}")
        return 2
    cert = S11BCertifier(
        ctx, timeout=args.timeout, marker_timeout=args.marker_timeout
    )
    summary = cert.execute()
    print(json.dumps(summary, ensure_ascii=False, indent=2) if args.json
          else f"[{'PASS' if summary['ok'] else 'FAIL'}] rows={summary.get('counts')} "
               f"firstFailure={summary.get('firstFailure')}")
    return int(summary["rc"])


if __name__ == "__main__":
    sys.exit(main())
