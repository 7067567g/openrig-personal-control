#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""openrig_certify.py — S10 operator-gated certification harness (one real minimal E2E).

WHAT THIS IS
------------
One isolated OpenRig rig, one real `opencode` seat, one minimal workflow, driven end to
end through the *product* CLI (`openrig-run` / `rig`). Every CERT row is one phase of that
single run; each row records the exact argv, rc, `error.code`, and stdout/stderr sha256,
and is projected to `reports/certification/CERT-0N.json`.

WHAT THIS IS NOT
----------------
* It is not a stub path. Rows call the real product; where a row cannot be observed
  externally, the row says so in `observedBasis` instead of inventing a boolean.
* It does not decide the certification. It records what happened; QA/MAIN judge it.
* It never runs without `--execute`, and `--execute` is a HUMAN gate: the LLM seat may
  print this command but may not approve it (D-004).

HARD RULES (each has a refusal code)
------------------------------------
  human_gate_required   no --execute -> rc2, zero writes
  work_dir_not_isolated work dir not /tmp/openrig-s10-cert-* or overlaps the control home
  port_exhausted        no free port in 48110..48119
  evidence_dir_unusable evidence root missing / not writable
  attempt_exists        this attempt id already has a directory (no silent overwrite)
  first_failure_preserved  a row already has a FAILED projection; this attempt is kept
                           alongside it and can never turn it green

FIRST FAILURE IS STRUCTURAL
---------------------------
Attempts never overwrite each other: every attempt writes under
`<evidence>/attempts/<attemptId>/`, and the top-level `CERT-0N.json` is a projection of
the FIRST attempt that produced that row. A rerun can add evidence; it cannot rewrite a
green story over a red one (D-005).

Usage
  # refuse + print the operator command (safe, no writes)
  python3 scripts/openrig_certify.py --work-dir /tmp/openrig-s10-cert-<utcstamp> \
      --evidence-dir runs/openrig-s10-certification-20261116/reports/certification

  # the one operator command (human gate)
  python3 scripts/openrig_certify.py --work-dir /tmp/openrig-s10-cert-<utcstamp> \
      --evidence-dir runs/openrig-s10-certification-20261116/reports/certification \
      --execute --json
"""
from __future__ import annotations

import argparse
import hashlib
import shlex
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # workflow-group
KB = ROOT.parent                                    # deepseek-知识库
PROD = KB.parent / "deepseek-项目" / "10-openrig-deepseek"
SCRIPTS = ROOT / "scripts"
RUN_ID = "openrig-s10-certification-20261116"
CONTROL_HOME = Path("/tmp/openrig-workflow-openrig-s10-certification-20261116")
CONTROL_RIG = "openrig-s10-certification-20261116"

SCHEMA = 1

# --- refusal codes (asserted by tests, not just rc) -------------------------------
CODE_HUMAN_GATE = "human_gate_required"
CODE_WORK_DIR = "work_dir_not_isolated"
CODE_PORT = "port_exhausted"
CODE_EVIDENCE = "evidence_dir_unusable"
CODE_ATTEMPT = "attempt_exists"
CODE_FIRST_FAILURE = "first_failure_preserved"
CODE_ROW_FAILED = "cert_row_failed"
CODE_ARCHIVE = "archive_record_unbound"
CODE_RESIDUE = "cert_residue_detected"
CODE_RIG_BIN_WRAPPER = "rig_bin_is_seat_wrapper"
CODE_RIG_BIN_UNRESOLVED = "rig_bin_unresolved"

# Keep in lockstep with openrig_run.ENTRY_VERBS.  The guard treats the first six
# as single-consumption startup verbs and the last five as repeatable continuation
# verbs for the lifetime of the same launch record.
STARTUP_ENTRY_VERBS = (
    "daemon-start",
    "up",
    "restore-apply",
    "workflow-instantiate",
    "workflow-instantiate-lifecycle",
    "workflow-run",
)
CONTINUATION_ENTRY_VERBS = (
    "workflow-route",
    "workflow-resume",
    "workflow-abort",
    "workflow-revision",
    "workflow-project",
)
ENTRY_VERBS = STARTUP_ENTRY_VERBS + CONTINUATION_ENTRY_VERBS

# --- CERT-MATRIX expectations, embedded (tests pin equality with the kickoff file) --
ROWS: dict[str, dict] = {
    "CERT-01": {"rc": 0, "daemonIsolated": True, "seatReady": True,
                "workflowInstantiated": True, "entryQitem": True},
    "CERT-02": {"rc": 0, "markerFile": True, "transcriptHasPrompt": True,
                "transcriptHasResponse": True},
    "CERT-03": {"rc": 0, "upExisting": True, "continuityActualOutcome": "resumed",
                "duplicateInstantiate": False},
    "CERT-04": {"authorizedRc": 0, "authorizedOutcome": "fresh-primed",
                "unauthorizedRc": 2, "mutationBeforeReject": False},
    "CERT-05": {"manifestKeySet": True, "stepReceipts": True,
                "partialOnControlledFailure": True},
    "CERT-06": {"s1MutationRc": 403, "handlerCalls": 0, "readOnlyAllowed": True,
                "s2Allowed": True},
    "CERT-07": {"incompleteRc": 2, "downCalls": 0, "completeRc": 0},
    "CERT-08": {"homeConflictRc": 2, "portConflictRc": 2, "staleLaunchRc": 2,
                "compactNotManagedRc": 2, "orphanReportReadOnly": True},
    "CERT-09": {"archiveStatus": "COMPLETE", "unitInactive": True, "portFree": True,
                "tmuxAbsent": True, "daemonAbsent": True},
    "CERT-10": {"s8s9Matrix": True, "docConsistency": True, "contractLock": True,
                "docBudget": True},
}

EVIDENCE_REQUIRED = (
    "CERT-01.json", "CERT-02.json", "CERT-03.json", "CERT-04.json", "CERT-05.json",
    "CERT-06.json", "CERT-07.json", "CERT-08.json", "CERT-09.json", "CERT-10.json",
)
# NOTE: FINAL.md is required by CERT-MATRIX#evidence.required but is produced at
# close_round (write_scope_map: N-CLOSE-01). CERT-E2E.json records that split instead of
# pretending the harness produced it.

MANIFEST_REQUIRED_KEYS = (
    "schemaVersion", "manifestId", "runId", "launchId", "revision", "runContext",
    "envKeys", "inputs", "steps", "seats", "workflow", "archive", "outputs", "status",
)


# --------------------------------------------------------------------- small helpers
def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def write_json(path: Path, payload: dict) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


DEFAULT_DOCTOR = (ROOT / "templates" / "specialized" / "openrig-workflow-master"
                  / "tools" / "openrig_bridge.py")


def doctor_path(run_dir: Path) -> Path | None:
    """The bundle doctor, resolved the same way `openrig-run check` resolves it."""
    for candidate in (
        Path(run_dir) / "openrig" / "tools" / "openrig_bridge.py",
        Path(run_dir) / "tools" / "openrig_bridge.py",
        DEFAULT_DOCTOR,
    ):
        if candidate.is_file():
            return candidate
    return None


CERT_WORK_PREFIX = "/tmp/openrig-s10-cert-"


SEAT_WRAPPER_HINTS = ("/seat-bin/", "/tmp/openrig-workflow-")


class RigBinRefused(Exception):
    """The rig binary could not be chosen safely. Fail closed, named, with a fix."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def resolve_rig_bin(explicit: str = "") -> tuple[list[str], str]:
    """Pick the rig binary deterministically and say where it came from.

    `shutil.which("rig")` is ambient: inside a seat it resolves to that seat's wrapper
    (`.../run/seat-bin/<hash>/rig`), which carries the seat's own home — and a cert harness
    driving the wrong plane is worse than one that refuses. So a wrapper is never silently
    skipped or fallen back from: the explicit case refuses it by name, and when the only
    candidate is a wrapper the resolver refuses instead of degrading to a bare `rig` (which
    would re-resolve through the same PATH and hit the wrapper at exec time).

    The choice is recorded as `rigBin`/`rigBinSource` in the attempt ledger, so "which
    binary actually ran this attempt" is answered by evidence rather than by an inherited
    PATH.
    """
    if explicit:
        if any(hint in explicit for hint in SEAT_WRAPPER_HINTS):
            raise RigBinRefused(
                CODE_RIG_BIN_WRAPPER,
                f"--rig-bin {explicit!r} is a seat wrapper; a certification harness must not "
                "drive another seat's wrapper/home. Pass the user-level binary, e.g. "
                f"{Path.home() / '.local/bin/rig'}",
            )
        return shlex.split(explicit), "explicit --rig-bin"
    candidates = [shutil.which("rig"), str(Path.home() / ".local" / "bin" / "rig"),
                  "/usr/local/bin/rig", "/usr/bin/rig"]
    rejected: list[str] = []
    for cand in candidates:
        if not cand or not Path(cand).is_file():
            continue
        if any(hint in cand for hint in SEAT_WRAPPER_HINTS):
            rejected.append(cand)
            continue
        return [cand], "path"
    if rejected:
        raise RigBinRefused(
            CODE_RIG_BIN_WRAPPER,
            "every rig binary on this host resolves through a seat/home wrapper "
            f"({', '.join(rejected[:3])}); refusing rather than falling back. Pass "
            f"--rig-bin {Path.home() / '.local/bin/rig'} (or the operator's binary) explicitly.",
        )
    raise RigBinRefused(
        CODE_RIG_BIN_UNRESOLVED,
        "no usable rig binary found on PATH or in the usual locations; pass --rig-bin <path>",
    )


def stale_cert_processes(proc_root: Path = Path("/proc")) -> list[dict]:
    """Live cert-daemon / seat-runner processes left by an earlier attempt (read-only).

    A failed attempt before CERT-07 has no teardown: the product's own rollback only fires
    when the rig never registered, and CERT-09 never runs after a stop-on-first-failure.

    Attribution is by OWNERSHIP, not by text: a process matches only when its environment
    carries OPENRIG_HOME under a cert prefix, or when it is a seat runner whose
    --state-root points there. Matching the raw command line matched an agent that merely
    *mentioned* a cert path in its conversation — a false positive that would have blocked a
    clean attempt (observed while verifying this patch on 2026-11-16).
    """
    out: list[dict] = []
    try:
        entries = list(Path(proc_root).iterdir())
    except OSError:
        return []
    for entry in entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == os.getpid():
            continue
        try:
            argv = [a for a in (entry / "cmdline").read_bytes().decode(
                "utf-8", "replace").split("\0") if a]
        except OSError:
            continue
        if not argv:
            continue
        try:
            env = [kv for kv in (entry / "environ").read_bytes().decode(
                "utf-8", "replace").split("\0") if kv]
        except OSError:
            env = []
        home = next((kv.split("=", 1)[1] for kv in env if kv.startswith("OPENRIG_HOME=")), "")
        reason = None
        if home.startswith(CERT_WORK_PREFIX):
            reason = f"OPENRIG_HOME={home}"
        else:
            for index, token in enumerate(argv):
                if (token == "--state-root" and index + 1 < len(argv)
                        and argv[index + 1].startswith(CERT_WORK_PREFIX)):
                    reason = f"--state-root {argv[index + 1]}"
                    break
        if reason:
            out.append({"pid": pid, "cmd": " ".join(argv)[:300], "reason": reason})
    return out


def canonical_session(pod: str, member: str, rig: str) -> str:
    """`{pod}-{member}@{rig}` — the product's deriveCanonicalSessionName, verbatim.

    packages/daemon/src/domain/session-name.ts: "Pure concatenation — no normalization,
    no heuristics." The harness must not invent a session name: `openrig_run._poll_ready`
    matches `bridge.seatMap` against `ps` rows by `canonicalSessionName`, so a name that
    differs by construction means a permanent wait-ready timeout (attempt 2, 2026-11-16).
    """
    return f"{pod}-{member}@{rig}"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", value.lower()).strip("-") or "cert"


def port_is_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def pick_port(base: int, span: int, *, forbid: tuple[int, ...] = ()) -> int | None:
    for port in range(base, base + span):
        if port in forbid:
            continue
        if port_is_free(port):
            return port
    return None


# --------------------------------------------------------------------- preflight
def preflight(
    *,
    work_dir: Path,
    evidence_dir: Path,
    control_home: Path = CONTROL_HOME,
    port_base: int = 48110,
    port_span: int = 10,
    ignore_cert_residue: bool = False,
    rig_bin: str = "",
) -> tuple[dict | None, list[dict]]:
    """Return (ctx, problems). No writes. Fail-closed and ordered."""
    problems: list[dict] = []

    def bad(code: str, message: str) -> None:
        problems.append({"code": code, "message": message})

    work = Path(work_dir).expanduser()
    if not work.is_absolute():
        bad(CODE_WORK_DIR, f"work dir must be absolute: {work}")
    if not re.match(r"^openrig-s10-cert-", work.name):
        bad(CODE_WORK_DIR, f"work dir basename must start with 'openrig-s10-cert-': {work.name}")
    tmp_root = Path("/tmp").resolve()
    try:
        work.resolve().relative_to(tmp_root)
    except ValueError:
        bad(CODE_WORK_DIR, f"work dir must live under {tmp_root}: {work}")

    try:
        ctrl = Path(control_home).expanduser().resolve()
        w = work.resolve()
        if w == ctrl or ctrl in w.parents or w in ctrl.parents:
            bad(CODE_WORK_DIR, f"work dir overlaps the control-plane home {ctrl}: {w}")
    except OSError:
        pass

    evidence = Path(evidence_dir).expanduser()
    if not evidence.is_absolute():
        evidence = (Path.cwd() / evidence)
    if not evidence.is_dir():
        bad(CODE_EVIDENCE, f"evidence dir does not exist: {evidence}")
    elif not os.access(evidence, os.W_OK):
        bad(CODE_EVIDENCE, f"evidence dir is not writable: {evidence}")

    if problems:
        return None, problems

    if not ignore_cert_residue:
        residue = stale_cert_processes()
        if residue:
            return None, [{
                "code": CODE_RESIDUE,
                "message": (
                    "a previous certification attempt is still alive: "
                    + ", ".join(f"pid {r['pid']} {r['cmd'].split()[0]}" for r in residue[:4])
                    + " — stop it before a new attempt (rig down + rig daemon stop on the cert "
                      "home), or pass --ignore-cert-residue to certify anyway (recorded)"
                ),
                "residue": residue[:8],
            }]

    port = pick_port(port_base, port_span)
    if port is None:
        return None, [{
            "code": CODE_PORT,
            "message": f"no free port in {port_base}..{port_base + port_span - 1}",
        }]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    attempt = f"{stamp}-{_slug(work.name.replace('openrig-s10-cert-', '')) or 'run'}"
    rig_name = f"openrig-s10-cert-{stamp.lower()}"
    seat_pod, seat_member = "cert", "cert"
    try:
        rig_argv, rig_source = resolve_rig_bin(rig_bin)
    except RigBinRefused as exc:
        return None, [{"code": exc.code, "message": exc.message}]
    ctx = {
        "rigBin": " ".join(rig_argv),
        "rigBinSource": rig_source,
        "workDir": work,
        "home": work / "home",
        # The bundle doctor requires run_dir.name == bridge.runId (A-1), so the run
        # directory is named after the run it holds — the same convention the control
        # plane uses. The bundle itself is <run>/openrig and bundleDir is ".".
        "runDir": work / f"openrig-s10-cert-{stamp.lower()}",
        "workspace": work / "workspace",
        "marker": work / "MARKER.json",
        "archiveRoot": work / "archive",
        "evidenceDir": evidence,
        "attemptId": attempt,
        "attemptDir": evidence / "attempts" / attempt,
        "port": port,
        "portCandidates": list(range(port_base, port_base + port_span)),
        "launchId": f"cert-{attempt}",
        "rigName": rig_name,
        "workflowId": f"openrig-workflow-s10-cert-{stamp.lower()}",
        "seatId": f"{seat_pod}.{seat_member}",
        "seatPod": seat_pod,
        "seatMember": seat_member,
        "seatSession": canonical_session(seat_pod, seat_member, rig_name),
        "nonce": sha256_bytes(f"{attempt}:{os.getpid()}:{time.time()}".encode())[:32],
        "controlHome": Path(control_home),
        "portBase": port_base,
        "portSpan": port_span,
    }
    return ctx, []


# --------------------------------------------------------------------- the certifier
class Certifier:
    """Drives the CERT rows. `runner` is injectable so the flow is testable offline."""

    def __init__(self, ctx: dict, *, runner=None, timeout: int = 300, marker_timeout: int = 240,
                 teardown_timeout: int = 120):
        self.ctx = ctx
        self.timeout = timeout
        self.marker_timeout = marker_timeout
        self.teardown_timeout = teardown_timeout
        self._seq = 0
        self.rows: list[dict] = []
        self.failureTeardown: dict | None = None
        self.harness_path = str(Path(__file__).resolve())
        self.harness_sha256 = sha256_file(Path(__file__))
        self.tests_path = str((Path(__file__).resolve().parent.parent /
                               "tests" / "test_openrig_certify.py"))
        self.tests_sha256 = sha256_file(Path(self.tests_path))
        self.started_at = now_iso()
        self.runner = runner or self._subprocess
        self.log_dir = ctx["attemptDir"] / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    # -- command execution ------------------------------------------------------
    def _subprocess(self, argv: list[str], *, env: dict | None = None,
                    cwd: Path | None = None, timeout: int | None = None) -> dict:
        t0 = now_iso()
        try:
            proc = subprocess.run(
                argv, capture_output=True, text=True, env=env, cwd=str(cwd) if cwd else None,
                timeout=timeout or self.timeout,
            )
            rc, out, err = proc.returncode, proc.stdout or "", proc.stderr or ""
        except subprocess.TimeoutExpired as exc:
            rc = 124
            out = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", "replace")
            err = (exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", "replace"))
            err = (err + f"\ntimeout after {timeout or self.timeout}s").strip()
        except (OSError, ValueError) as exc:
            rc, out, err = 126, "", f"could not run {argv!r}: {exc}"
        return {"rc": rc, "stdout": out, "stderr": err, "startedAt": t0, "endedAt": now_iso()}

    def run(self, label: str, argv: list[str], *, env: dict | None = None,
            cwd: Path | None = None, timeout: int | None = None) -> dict:
        """Run one command, persist both streams, return the result + digests."""
        self._seq += 1
        result = self.runner(argv, env=env, cwd=cwd, timeout=timeout)
        out_path = self.log_dir / f"{self._seq:02d}-{_slug(label)}.out"
        err_path = self.log_dir / f"{self._seq:02d}-{_slug(label)}.err"
        out_path.write_text(result.get("stdout") or "", encoding="utf-8")
        err_path.write_text(result.get("stderr") or "", encoding="utf-8")
        return {
            "label": label,
            "argv": list(argv),
            "rc": int(result.get("rc") or 0),
            "stdoutSha256": sha256_bytes((result.get("stdout") or "").encode()),
            "stderrSha256": sha256_bytes((result.get("stderr") or "").encode()),
            "stdoutBytes": len((result.get("stdout") or "").encode()),
            "stderrTail": (result.get("stderr") or "").strip().splitlines()[-5:],
            "stdout": result.get("stdout") or "",
            "startedAt": result.get("startedAt") or now_iso(),
            "endedAt": result.get("endedAt") or now_iso(),
            "log": f"logs/{out_path.name}",
            "errLog": f"logs/{err_path.name}",
        }

    # -- environment for product calls ------------------------------------------
    def env(self, *, launch_id: str | None = None) -> dict:
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("OPENRIG_") and not k.startswith("RIGGED_")}
        env["OPENRIG_HOME"] = str(self.ctx["home"])
        env["OPENRIG_PORT"] = str(self.ctx["port"])
        if launch_id:
            env["OPENRIG_ENTRY_LAUNCH_ID"] = launch_id
        return env

    def control_env(self) -> dict:
        """Environment for observing the CONTROL plane, never the cert home.

        P-026: the first v30 attempt ran `rig ps` with the harness process env, so the
        CLI looked for the default daemon instead of the control daemon at port 48010.
        That made a healthy 3/3 control rig look like `Daemon not running`.
        """
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("OPENRIG_") and not k.startswith("RIGGED_")}
        env["OPENRIG_HOME"] = str(CONTROL_HOME)
        env["OPENRIG_PORT"] = "48010"
        env["OPENRIG_URL"] = "http://127.0.0.1:48010"
        return env

    def cli(self) -> list[str]:
        return [sys.executable, str(SCRIPTS / "openrig_run.py")]

    def rig(self) -> list[str]:
        """The pinned rig binary from ctx — never an ambient OPENRIG_RIG_BIN.

        A seat's environment carries OPENRIG_RIG_BIN pointing at that seat's wrapper; a
        harness started from such a shell would run `rig down` / `rig daemon stop` through
        the WRONG wrapper (observed while verifying this patch). The binary is resolved once
        at preflight (`--rig-bin`, else PATH) and carried in ctx.
        """
        return shlex.split(str(self.ctx.get("rigBin") or "rig"))

    # -- row plumbing -----------------------------------------------------------
    def _row(self, cid: str, *, scenario: str, observed: dict, commands: list[dict],
             rc: int, code: str | None = None, notes: list[str] | None = None,
             basis: dict | None = None, warn: bool = False,
             deviation: str = "", hard_fail: bool = False,
             fail_label: str = "") -> dict:
        expect = ROWS[cid]
        mismatched = [k for k, v in expect.items() if observed.get(k) != v]
        row = {
            "schemaVersion": SCHEMA,
            "row": cid,
            "scenario": scenario,
            "runId": RUN_ID,
            "attemptId": self.ctx["attemptId"],
            "launchId": self.ctx["launchId"],
            "capturedAt": now_iso(),
            "expect": expect,
            "observed": observed,
            "mismatched": mismatched,
            "pass": not mismatched,
            "warn": bool(warn),
            "acceptedDeviation": deviation or None,
            "rc": rc,
            "error": {"code": code} if code else None,
            "commands": [{k: c[k] for k in ("label", "argv", "rc", "stdoutSha256",
                                            "stderrSha256", "stdoutBytes", "stderrTail",
                                            "startedAt", "endedAt", "log", "errLog")}
                         for c in commands],
            "observedBasis": basis or {},
            "notes": notes or [],
        }
        if hard_fail:
            row["pass"] = False
            if fail_label and fail_label not in row["mismatched"]:
                row["mismatched"].append(fail_label)
        self.rows.append(row)
        return row

    def _not_attempted(self, cid: str, reason: str, *, blocked_by: str) -> dict:
        row = {
            "schemaVersion": SCHEMA,
            "row": cid,
            "scenario": ROWS_SEMANTICS.get(cid, ""),
            "attemptId": self.ctx["attemptId"],
            "launchId": self.ctx["launchId"],
            "capturedAt": now_iso(),
            "expect": ROWS[cid],
            "observed": {},
            "mismatched": sorted(ROWS[cid]),
            "pass": False,
            "notAttempted": True,
            "blockedBy": blocked_by,
            "rc": None,
            "error": {"code": "not_attempted", "message": reason},
            "commands": [],
        }
        self.rows.append(row)
        return row

    def teardown_after_failure(self, *, failed_row: str) -> list[dict]:
        """Salvage teardown after a failure that never reached CERT-07.

        CERT-09 remains the *certified* cleanup row; this only stops the leak. Scoped twice:
        the rig name must carry the cert prefix and the home must live inside this attempt's
        work dir, so the control-plane rig/home can never match. Bounded (teardown_timeout),
        recorded in the attempt dir, and a run is never called clean while residue remains.
        Evidence is never deleted; no `rm -rf`.
        """
        ctx = self.ctx
        if not str(ctx["rigName"]).startswith("openrig-s10-cert-"):
            return []
        home = Path(ctx["home"]).resolve()
        if Path(ctx["workDir"]).resolve() not in home.parents:
            return []
        done: list[dict] = []
        # Look before acting: when CERT-07's own stop already tore the rig down, nothing of
        # this attempt is live and a second `rig down` would only record a meaningless rc.
        # Attempt 10 failed at the archive bind BEFORE its stop, so this path must still act.
        pre_stale = stale_cert_processes() if failed_row == "CERT-07" else [{"pid": -1, "cmd": "pre-CERT-07 failure"}]
        pre_tmux = self.run("teardown-tmux-probe",
                            ["bash", "-lc", "tmux ls -F '#{session_name}' 2>/dev/null || true"],
                            env=os.environ.copy(), timeout=self.teardown_timeout)
        pre_sessions = [ln.strip() for ln in (pre_tmux.get("stdout") or "").splitlines()
                        if ctx["seatSession"] in ln or ctx["rigName"] in ln]
        pre_port = (not port_is_free(ctx["port"])) if failed_row == "CERT-07" else False
        if not pre_stale and not pre_sessions and not pre_port:
            payload = {
                "schemaVersion": SCHEMA, "attemptId": ctx["attemptId"],
                "failedRow": failed_row, "capturedAt": now_iso(),
                "mutations": [],
                "residue": {"staleProcesses": [], "tmuxSessions": [], "portInUse": False},
                "residueRemaining": False, "clean": True,
                "note": ("nothing of this attempt was live when salvage ran (the stop had "
                         "already torn it down); no rig down issued. CERT-09 remains the "
                         "certified cleanup row."),
            }
            write_json(Path(ctx["attemptDir"]) / "teardown.json", payload)
            self.failureTeardown = payload
            return []
        down = self.run("teardown-down", [*self.rig(), "down", ctx["rigName"], "--json"],
                        env=self.env(), timeout=self.teardown_timeout)
        done.append({"step": "rig-down", "rc": down["rc"], "argv": down["argv"],
                     "stdoutSha256": down["stdoutSha256"], "log": down["log"]})
        stop = self.run("teardown-daemon-stop", [*self.rig(), "daemon", "stop"],
                        env=self.env(), timeout=self.teardown_timeout)
        done.append({"step": "daemon-stop", "rc": stop["rc"], "argv": stop["argv"],
                     "stdoutSha256": stop["stdoutSha256"], "log": stop["log"]})
        tmux = self.run("teardown-tmux-check",
                        ["bash", "-lc", "tmux ls -F '#{session_name}' 2>/dev/null || true"],
                        env=os.environ.copy(), timeout=self.teardown_timeout)
        sessions = [ln.strip() for ln in (tmux.get("stdout") or "").splitlines()
                    if ctx["seatSession"] in ln or ctx["rigName"] in ln]
        # Bounded wait: a killed seat takes a moment to release its port/process.
        residue: dict = {}
        for _ in range(6):
            stale = stale_cert_processes()
            port_busy = not port_is_free(ctx["port"])
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
            "capturedAt": now_iso(),
            "mutations": done,
            "tmuxCheck": {"argv": tmux["argv"], "rc": tmux["rc"],
                          "stdoutSha256": tmux["stdoutSha256"], "log": tmux["log"]},
            "residue": residue,
            "residueRemaining": not clean,
            "clean": clean,
            "note": ("salvage teardown after a pre-CERT-07 failure; CERT-09 remains the "
                     "certified cleanup row. Evidence retained, no rm -rf."),
        }
        write_json(Path(ctx["attemptDir"]) / "teardown.json", payload)
        self.failureTeardown = payload
        return done

    def fail_and_stop(self, cid: str, reason: str) -> list[dict]:
        """Every row after the first failure is recorded as not_attempted."""
        later = [r for r in EXECUTION_ORDER[EXECUTION_ORDER.index(cid) + 1:]]
        for row_id in later:
            self._not_attempted(row_id, reason, blocked_by=cid)
        return self.rows

    # -- the flow ---------------------------------------------------------------
    def execute(self) -> dict:
        # Execution order is NOT the row numbering: CERT-06/08 need the daemon listening
        # (the L3 probe closes the ticket, the negatives need a held port), while CERT-07 is
        # the teardown. The row ids stay 01..10; `executionOrder` in the ledger records this.
        steps = [
            ("CERT-01", self.cert_01_start),
            ("CERT-02", self.cert_02_prompt),
            ("CERT-03", self.cert_03_resume),
            ("CERT-04", self.cert_04_fresh),
            ("CERT-05", self.cert_05_manifest),
            ("CERT-06", self.cert_06_http),
            ("CERT-08", self.cert_08_negatives),
            ("CERT-07", self.cert_07_archive_gate),
            ("CERT-09", self.cert_09_cleanup),
            ("CERT-10", self.cert_10_static),
        ]
        error: dict | None = None
        try:
            for cid, fn in steps:
                row = fn()
                self._project(row)
                if not row.get("pass") and not row.get("warn"):
                    self.fail_and_stop(cid, f"stopped after {cid} (first failure preserved)")
                    # Any failed row can leave a live daemon/seat. CERT-07 itself can fail
                    # before its stop step (P-023), so salvage runs for every failed row.
                    self.teardown_after_failure(failed_row=cid)
                    break
        except Exception as exc:  # noqa: BLE001 - the operator needs evidence, not a traceback
            error = {"code": "harness_exception",
                     "message": f"{type(exc).__name__}: {exc}"}
            self.teardown_after_failure(failed_row="exception")
        summary = self._finish()
        if error:
            summary["error"] = error
            summary["ok"] = False
            summary["rc"] = 1
            write_json(Path(self.ctx["attemptDir"]) / "summary.json", summary)
        return summary

    # -- CERT-01: real start ----------------------------------------------------
    def cert_01_start(self) -> dict:
        ctx = self.ctx
        self._write_bundle()
        cmds = []
        # A bundle the product's own doctor rejects must fail HERE, with a named code,
        # instead of consuming a start attempt (attempt 1 of 2026-11-16T10:35Z was spent on
        # a bridge whose bundleDir/runId the doctor refused).
        doctor = doctor_path(Path(ctx["runDir"]))
        if doctor is None:
            return self._row(
                "CERT-01", scenario="real start",
                observed={"rc": 2, "daemonIsolated": False, "seatReady": False,
                          "workflowInstantiated": False, "entryQitem": False},
                commands=cmds, rc=2, code="bridge_doctor_missing",
                notes=["no openrig_bridge.py found in the bundle, the run dir, or the template"],
            )
        pre = self.run("bridge-doctor", [sys.executable, str(doctor), "doctor",
                                         "--run-dir", str(ctx["runDir"])],
                       env=self.env(), cwd=ROOT)
        cmds.append(pre)
        if pre["rc"] != 0:
            return self._row(
                "CERT-01", scenario="real start",
                observed={"rc": 2, "daemonIsolated": False, "seatReady": False,
                          "workflowInstantiated": False, "entryQitem": False},
                commands=cmds, rc=2, code="bridge_doctor_failed",
                notes=[f"bundle doctor rc={pre['rc']} tool={doctor}",
                       "no start was attempted: an invalid bundle must not consume an attempt",
                       f"doctor stderr tail={pre['stderrTail']}"],
                basis={"rc": "preflight doctor refusal (before any lifecycle call)"},
            )
        check = self.run("check", [*self.cli(), "check", "--run-dir", str(ctx["runDir"]),
                                   "--allow-daemon-down", "--json"], env=self.env(), cwd=ROOT)
        cmds.append(check)
        start = self.run("start", [*self.cli(), "start", "--run-dir", str(ctx["runDir"]),
                                   "--json", "--timeout", str(self.timeout)],
                         env=self.env(), cwd=ROOT, timeout=self.timeout + 60)
        cmds.append(start)
        ps = self.run("ps", [*self.rig(), "ps", "--nodes", "--rig", ctx["rigName"], "--json"],
                      env=self.env())
        cmds.append(ps)
        nodes = _json_or(ps["stdout"], default=[])
        seats = [r for r in _rows_of(nodes) if r.get("canonicalSessionName") == ctx["seatSession"]]
        seat_ready = bool(seats) and str(seats[0].get("startupStatus")) == "ready"
        manifest = _read_json(ctx["runDir"] / "reports/evidence/manifest/run-manifest.json") or {}
        instance = str((manifest.get("workflow") or {}).get("instanceId") or "")
        qitems = _rows_of(_json_or(
            self.run("queue", [*self.rig(), "queue", "list", "--destination", ctx["seatSession"],
                               "--json"], env=self.env())["stdout"], default=[]))
        entry = [q for q in qitems
                 if q.get("state") in ("pending", "in-progress", "blocked")
                 or q.get("pickup")]
        ctx["instanceId"] = instance
        observed = {
            "rc": start["rc"],
            "daemonIsolated": Path(str((manifest.get("runContext") or {}).get("openrigHome")
                                       or ctx["home"])).resolve() == Path(ctx["home"]).resolve(),
            "seatReady": seat_ready,
            "workflowInstantiated": bool(instance),
            "entryQitem": bool(entry),
            # R-006/P-006: a name mismatch is a harness false negative, and the row must say
            # so by itself. Attempt 2's ps log already showed startupStatus=ready for the
            # real seat while seatReady came out false; nobody should have to open 04-ps.out
            # to learn that.
            "seatRowsSeen": [
                {"canonicalSessionName": r.get("canonicalSessionName"),
                 "startupStatus": r.get("startupStatus")}
                for r in _rows_of(nodes)[:8]
            ],
            "expectedSeatSession": ctx["seatSession"],
        }
        code = _error_code(start)
        return self._row(
            "CERT-01", scenario="real start", observed=observed, commands=cmds,
            rc=start["rc"], code=code,
            notes=[
                f"home={ctx['home']} port={ctx['port']} rig={ctx['rigName']}",
                f"workflow instance={instance or '<none>'}",
                f"entry qitems={len(entry)}",
                f"expected seat={ctx['seatSession']!r} "
                f"seen={[r.get('canonicalSessionName') for r in _rows_of(nodes)][:8]}",
                ("a seat that reports startupStatus=ready under a different canonical name is "
                 "a harness false negative, not a product failure (attempt 2)"),
            ],
            basis={"daemonIsolated": "run-manifest.runContext.openrigHome (written by the real start)",
                   "seatReady": "rig ps --nodes row startupStatus==ready for the cert seat",
                   "workflowInstantiated": "run-manifest.workflow.instanceId non-empty",
                   "entryQitem": "rig queue list --destination <seat> returns a live obligation"},
        )

    def _write_bundle(self) -> dict:
        """Render the minimal one-seat bundle inside the isolated work dir (no product write)."""
        ctx = self.ctx
        run_dir = Path(ctx["runDir"])
        bundle = run_dir / "openrig"
        (bundle / "agents" / "cert").mkdir(parents=True, exist_ok=True)
        (run_dir / "reports" / "evidence" / "manifest").mkdir(parents=True, exist_ok=True)
        (Path(ctx["workspace"])).mkdir(parents=True, exist_ok=True)
        marker = ctx["marker"]
        seat_pod = ctx.get("seatPod", "cert")
        seat_member = ctx.get("seatMember", "cert")
        seat_session = canonical_session(seat_pod, seat_member, ctx["rigName"])
        # One derivation, no second opinion: the bridge seatMap, the workflow target and
        # the harness's own transcript/cleanup lookups all use this exact string.
        ctx["seatSession"] = seat_session
        (Path(ctx["workspace"]) / "AGENTS.md").write_text(
            "# S10 certification seat\n\n"
            "When you receive a workflow step, do exactly what it asks and reply with one line.\n"
            f"If it asks for a marker, write the JSON to {marker} (absolute path) and echo DONE.\n",
            encoding="utf-8",
        )
        (bundle / "agents" / "cert" / "agent.yaml").write_text(
            "name: openrig-s10-cert-worker\nversion: '1.0.0'\n"
            "description: S10 certification worker.\n"
            "resources:\n  skills: []\nprofiles:\n  default:\n    uses:\n      skills: []\n"
            "startup:\n  files: []\n  actions: []\n", encoding="utf-8")
        (bundle / "rig.yaml").write_text(
            "version: '0.2'\n"
            f"name: {ctx['rigName']}\n"
            "summary: 'S10 certification: one real opencode seat, one minimal workflow step.'\n"
            f"pods:\n- id: {seat_pod}\n  label: Certification\n  members:\n"
            f"  - id: {seat_member}\n    agent_ref: local:./agents/cert\n    profile: default\n"
            "    runtime: opencode\n    role: cert\n"
            f"    cwd: \"{ctx['workspace']}\"\n    model: \"deepseek/deepseek-flash\"\n"
            "  edges: []\nedges: []\n"
            "startup:\n  files:\n  - path: guidance/cert.md\n"
            "    delivery_hint: guidance_merge\n    required: true\n", encoding="utf-8")
        guidance = bundle / "guidance"
        guidance.mkdir(parents=True, exist_ok=True)
        (guidance / "cert.md").write_text(
            "# S10 certification seat\n\n"
            "This seat exists only to prove the managed lifecycle. For each workflow step:\n\n"
            "1. do exactly the step objective;\n"
            "2. if it asks for a marker, write the JSON object to the ABSOLUTE path it names;\n"
            "3. reply with one line: DONE <what you wrote>.\n", encoding="utf-8")
        (bundle / "workflow.yaml").write_text(
            "# S10 certification: one seat, one step.\n"
            "workflow:\n"
            f"  id: {ctx['workflowId']}\n"
            "  version: 1\n"
            "  objective: >\n"
            "    Prove one real managed lifecycle step end to end for the S10 certification.\n"
            "  target:\n"
            f"    rig: {ctx['rigName']}\n"
            "  entry:\n    role: cert\n"
            "  exception_routing:\n    orchestrator_role: cert\n"
            "  coordination_terminal_turn_rule: hot_potato\n"
            "  roles:\n"
            f"    {seat_member}:\n      preferred_targets: [{seat_session}]\n"
            "  steps:\n    - id: certify\n      actor_role: cert\n      objective: >\n"
            f"        {_marker_objective(ctx)}\n"
            "      allowed_exits: [done, failed]\n"
            "  invariants:\n    continuation_required: true\n    preserve_lineage: true\n"
            "    closure_required: true\n    allowed_exits: [done, failed]\n"
            "  loop_guards:\n    max_hops: 2\n    spawn_budget: 0\n"
            "  closure:\n    success: marker written\n    degraded: not attempted\n"
            "    failed: marker missing\n", encoding="utf-8")
        files = {}
        for rel in ("rig.yaml", "workflow.yaml", "agents/cert/agent.yaml"):
            p = bundle / rel
            files[rel] = {"bytes": p.stat().st_size, "sha256": sha256_file(p)}
        write_json(bundle / "render-manifest.json", {
            "schemaVersion": 1, "runId": ctx["rigName"], "files": files,
        })
        write_json(bundle / "OPENRIG-BRIDGE.json", {
            "schemaVersion": 2,
            "runId": ctx["rigName"],
            "projectRoot": str(ctx["workspace"]),
            # bridge v2: relative bundleDir resolving to the directory the bridge lives in.
            "bundleDir": ".",
            "rigName": ctx["rigName"],
            "workflowId": ctx["workflowId"],
            "rigSpec": "rig.yaml",
            "workflowSpec": "workflow.yaml",
            "openrigCli": self.rig()[0],
            "openrigHome": str(ctx["home"]),
            "daemonPort": ctx["port"],
            "seatMap": {seat_member: seat_session},
            "runtimeEnv": {
                "OPENRIG_OPENCODE_BIN": os.environ.get("OPENRIG_OPENCODE_BIN", "opencode"),
                "OPENRIG_OPENCODE_MODEL": "deepseek/deepseek-flash",
            },
            "policy": {
                "mode": "managed-isolated", "maxActiveAgents": 1, "maxHops": 2,
                "preferResume": True, "safetyMode": "on-demand",
                "allowSourceChanges": False,
            },
            "_certification": {"runId": RUN_ID, "attemptId": ctx["attemptId"]},
        })
        return {"runDir": str(run_dir), "home": str(ctx["home"])}

    # -- CERT-02: real prompt + marker ------------------------------------------
    def cert_02_prompt(self) -> dict:
        ctx = self.ctx
        cmds = []
        before = self.run("transcript-before", [*self.rig(), "transcript", ctx["seatSession"],
                                                "--tail", "400", "--json"], env=self.env())
        cmds.append(before)
        marker_text = ""
        deadline = time.time() + self.marker_timeout
        waited = 0.0
        while time.time() < deadline:
            if Path(ctx["marker"]).is_file():
                marker_text = Path(ctx["marker"]).read_text(encoding="utf-8").strip()
                break
            waited = time.time() - (deadline - self.marker_timeout)
            time.sleep(3)
        after = self.run("transcript-after", [*self.rig(), "transcript", ctx["seatSession"],
                                              "--tail", "400", "--json"], env=self.env())
        cmds.append(after)
        blob = (after.get("stdout") or "") + (before.get("stdout") or "")
        has_prompt = _prompt_in(blob, ctx)
        marker = None
        try:
            marker = json.loads(marker_text) if marker_text else None
        except json.JSONDecodeError:
            marker = {"_unparsable": marker_text[:200]}
        observed = {
            "rc": 0 if marker is not None else 1,
            "markerFile": marker is not None,
            "transcriptHasPrompt": has_prompt,
            "transcriptHasResponse": bool(marker) and ("DONE" in blob or "done" in blob),
        }
        nonce_ok = isinstance(marker, dict) and marker.get("nonce") == ctx["nonce"]
        handoff = ("Queue handoff" in blob) or ("qitem-" in blob)
        activity = "[tool]" in blob
        capture_degraded = _capture_degraded(after.get("stdout") or "") or _capture_degraded(
            before.get("stdout") or "")
        if nonce_ok:
            ctx["markerNonceSeen"] = ctx["nonce"]
        transcript_text = observed["transcriptHasPrompt"] and observed["transcriptHasResponse"]
        warn = bool(observed["markerFile"] and nonce_ok and (handoff or activity)
                    and capture_degraded and not transcript_text)
        code = None if observed["markerFile"] else "marker_missing"
        return self._row(
            "CERT-02", scenario="real prompt and marker", observed=observed, commands=cmds,
            rc=observed["rc"], code=code, warn=warn,
            hard_fail=bool(marker is not None and not nonce_ok),
            fail_label="markerNonce",
            deviation=("transcript text capture degraded; prompt execution is proven by the "
                       "marker nonce/objective + qitem handoff/tool activity; transcript "
                       "capture is NOT certified (P-013)") if warn else "",
            notes=[f"marker={ctx['marker']}", f"waited≈{waited:.0f}s",
                   f"markerBody={json.dumps(marker, ensure_ascii=False)[:400] if marker else '<absent>'}"],
            basis={"markerFile": "the seat wrote the absolute marker path named in the step objective",
                   "transcriptHasPrompt": "rig transcript contains the marker nonce/step text",
                   "transcriptHasResponse": "rig transcript contains the seat's DONE reply",
                   "warn": "nonce matches objective and handoff/tool activity is visible, but "
                           "the tmux transcript carries no objective/DONE text; transcript "
                           "capture is degraded and is NOT certified (P-013)"},
        )

    # -- CERT-03: real resume ---------------------------------------------------
    def cert_03_resume(self) -> dict:
        ctx = self.ctx
        cmds = []
        instances_before = len(_rows_of(_json_or(
            self.run("workflow-list-pre", [*self.rig(), "workflow", "list", "--json"],
                     env=self.env())["stdout"], default=[])))
        before_transcript = self.run("transcript-pre-stop",
                                     [*self.rig(), "transcript", ctx["seatSession"],
                                      "--tail", "60", "--json"], env=self.env())
        cmds.append(before_transcript)
        down = self.run("down", [*self.rig(), "down", ctx["rigName"], "--json"], env=self.env())
        cmds.append(down)
        # D-018/D-019: `rig down` must leave the DAEMON running; resume is certified only in
        # that shape (recovery `up <rig> --existing`). A read-only `status --live` proves it
        # immediately before resume, and a daemon that does not answer stops the row instead
        # of drifting into the uncertified "daemon-stopped" scenario.
        probe, daemon_state, probe_info = self._probe_daemon_state(
            Path(ctx["runDir"]), "daemon-state-before-resume")
        cmds.append(probe)
        ctx["daemonStateBeforeResume"] = daemon_state
        if daemon_state != "running":
            return self._row(
                "CERT-03", scenario="real resume",
                observed={"rc": 2, "upExisting": False, "continuityActualOutcome": None,
                          "duplicateInstantiate": False, "daemonState": daemon_state},
                commands=cmds, rc=2, code=probe_info["refusalCode"],
                notes=[f"daemon not proven live after `rig down`: reason={probe_info['reason']!r} "
                       f"stateSource={probe_info['stateSource']!r} "
                       f"daemonState={probe_info['daemonState']!r} statusRc={probe['rc']} "
                       f"statusError={probe_info['statusErrorCode']!r}",
                       "daemon-stopped resume is explicitly NOT certified this round (D-018)",
                       "resume was NOT attempted: no recovery up --existing ran"],
                basis={"daemonState":
                       "read-only `openrig-run status --live --json` immediately before "
                       "resume; requires plan.stateSource=='ps' AND "
                       "plan.stateBefore.daemonState=='running' (a fixture stateSource is "
                       "refused, QA R-003), `continuity_state_unavailable` means the daemon "
                       "did not answer (D-019)",
                       "daemonStateProvenance": "openrig-run status --live --json"},
            )
        resume = self.run("resume", [*self.cli(), "resume", "--run-dir", str(ctx["runDir"]),
                                     "--live", "--json", "--timeout", str(self.timeout)],
                          env=self.env(), cwd=ROOT, timeout=self.timeout + 60)
        cmds.append(resume)
        payload = _json_or(resume["stdout"], default={}) or {}
        after_transcript = self.run("transcript-post-resume",
                                    [*self.rig(), "transcript", ctx["seatSession"],
                                     "--tail", "60", "--json"], env=self.env())
        cmds.append(after_transcript)
        instances_after = len(_rows_of(_json_or(
            self.run("workflow-list-post", [*self.rig(), "workflow", "list", "--json"],
                     env=self.env())["stdout"], default=[])))
        plan = payload.get("continuity") or {}
        seats = plan.get("seats") or []
        mutations = payload.get("mutations") or []
        up_argv = next((m.get("argv") for m in mutations if m.get("step") == "up-existing"), []) or []
        companion, companion_basis = _observe_resume(
            pre=before_transcript.get("stdout") or "",
            post=after_transcript.get("stdout") or "",
            seat_row=seats[0] if seats else {},
        )
        # N-CT-02: the product now reports the restore's own per-node status
        # (`up --existing --json`), so that value is the certified one; the harness's
        # own before/after observation is kept as an independent cross-check.
        # D-016 (3): the certified value IS CONTINUITY-PLAN's actualOutcome. No fallback:
        # if the plan carries none the row fails closed, rather than letting a harness-side
        # inference (session identity, transcript, nodeId) stand in for the product's own
        # restore verdict.
        seat_row = next(
            (s for s in seats if s.get("canonicalSessionName") == ctx["seatSession"]), None)
        if seat_row is None and seats:
            seat_row = seats[0]
        product_outcome = (seat_row or {}).get("actualOutcome")
        observed = {
            "rc": resume["rc"],
            "upExisting": any("--existing" in str(a) for a in up_argv) or bool(
                next((m for m in mutations if m.get("step") == "up-existing"), None)),
            "continuityActualOutcome": product_outcome,
            "duplicateInstantiate": instances_after > instances_before,
            "daemonState": daemon_state,
        }
        return self._row(
            "CERT-03", scenario="real resume", observed=observed, commands=cmds,
            rc=resume["rc"], code=_error_code(resume),
            notes=[
                f"continuityRc={resume['rc']} decision={plan.get('decisionStatus')!r}",
                f"planLevelActualOutcome={[s.get('actualOutcome') for s in seats]}",
                f"planOutcomeProvenance={plan.get('actualOutcomeProvenance')!r} "
                f"missing={plan.get('actualOutcomeMissing') or []}",
                f"daemonState={daemon_state} (reason={probe_info['reason']!r} "
                f"stateSource={probe_info['stateSource']!r} probe rc={probe['rc']})",
                f"diagnosticOnly_harnessObservation={companion!r} ({companion_basis}) "
                "- never used as the asserted value (D-016)",
            ],
            basis={"continuityActualOutcome": (
                       "CONTINUITY-PLAN seats[].actualOutcome, sourced from "
                       "`up --existing --json` nodes[].status; no fallback (D-016)"),
                   "daemonState":
                       "read-only `openrig-run status --live --json` immediately before "
                       "resume; requires plan.stateSource=='ps' AND "
                       "plan.stateBefore.daemonState=='running' (fixture stateSource is "
                       "refused, QA R-003)",
                   "daemonStateProvenance": "openrig-run status --live --json",
                   "upExisting": "resume report mutations contain step 'up-existing' (rig up --existing)",
                   "duplicateInstantiate": "no workflow-instantiate mutation on resume"},
        )

    # -- CERT-04: explicit fresh + unauthorized fresh ---------------------------
    def cert_04_fresh(self) -> dict:
        ctx = self.ctx
        cmds = []
        state_before = _state_fingerprint(self)
        unauth = self.run("resume-fresh-no-reason",
                          [*self.cli(), "resume", "--run-dir", str(ctx["runDir"]),
                           "--fresh", ctx["seatId"], "--live", "--json"],
                          env=self.env(), cwd=ROOT)
        cmds.append(unauth)
        state_after = _state_fingerprint(self)
        cmds.append(self.run("down-before-fresh", [*self.rig(), "down", ctx["rigName"], "--json"],
                             env=self.env()))
        # D-019: the same read-only proof immediately before the down->fresh resume.
        probe, daemon_state, probe_info = self._probe_daemon_state(
            Path(ctx["runDir"]), "daemon-state-before-fresh")
        cmds.append(probe)
        ctx["daemonStateBeforeFresh"] = daemon_state
        if daemon_state != "running":
            return self._row(
                "CERT-04", scenario="explicit fresh and unauthorized fresh",
                observed={"authorizedRc": 2, "authorizedOutcome": None,
                          "unauthorizedRc": unauth["rc"],
                          "mutationBeforeReject": state_before != state_after,
                          "daemonState": daemon_state},
                commands=cmds, rc=2, code=probe_info["refusalCode"],
                notes=[f"daemon not proven live after `rig down`: reason={probe_info['reason']!r} "
                       f"stateSource={probe_info['stateSource']!r} "
                       f"daemonState={probe_info['daemonState']!r} statusRc={probe['rc']} "
                       f"statusError={probe_info['statusErrorCode']!r}",
                       "daemon-stopped fresh is explicitly NOT certified this round (D-018)",
                       "the authorized fresh resume was NOT attempted"],
                basis={"daemonState":
                       "read-only `openrig-run status --live --json` immediately before the "
                       "down->fresh resume; requires plan.stateSource=='ps' AND "
                       "plan.stateBefore.daemonState=='running' (fixture stateSource is "
                       "refused, QA R-003)",
                       "daemonStateProvenance": "openrig-run status --live --json"},
            )
        auth = self.run("resume-fresh-authorized",
                        [*self.cli(), "resume", "--run-dir", str(ctx["runDir"]),
                         "--fresh", ctx["seatId"], "--reason",
                         "S10 certification: operator-authorized fresh after a deliberate teardown",
                         "--live", "--json", "--timeout", str(self.timeout)],
                        env=self.env(), cwd=ROOT, timeout=self.timeout + 60)
        cmds.append(auth)
        transcript = self.run("transcript-after-fresh",
                              [*self.rig(), "transcript", ctx["seatSession"], "--tail", "80", "--json"],
                              env=self.env())
        cmds.append(transcript)
        payload = _json_or(auth["stdout"], default={}) or {}
        plan = payload.get("continuity") or {}
        seat = (plan.get("seats") or [{}])[0]
        companion, companion_basis = _observe_fresh(pre=ctx.get("markerNonceSeen", ""),
                                                     transcript=transcript.get("stdout") or "",
                                                     seat_row=seat)
        # D-016 (3): plan value only; a harness inference never substitutes for it.
        product_outcome = seat.get("actualOutcome")
        observed = {
            "authorizedRc": auth["rc"],
            "authorizedOutcome": product_outcome,
            "unauthorizedRc": unauth["rc"],
            "mutationBeforeReject": state_before != state_after,
            "daemonState": daemon_state,
        }
        code = _error_code(unauth) if unauth["rc"] == 2 else _error_code(auth)
        return self._row(
            "CERT-04", scenario="explicit fresh and unauthorized fresh", observed=observed,
            commands=cmds, rc=auth["rc"], code=code,
            notes=[f"unauthorizedCode={_error_code(unauth)!r}",
                   f"authorizedPlanDecision={plan.get('decisionStatus')!r}",
                   f"planOutcomeProvenance={plan.get('actualOutcomeProvenance')!r} "
                   f"missing={plan.get('actualOutcomeMissing') or []}",
                   f"daemonState={daemon_state} (reason={probe_info['reason']!r} "
                   f"stateSource={probe_info['stateSource']!r} probe rc={probe['rc']})",
                   f"diagnosticOnly_harnessObservation={companion!r} ({companion_basis}) "
                   "- never used as the asserted value (D-016)"],
            basis={"authorizedOutcome": (
                       "CONTINUITY-PLAN seats[].actualOutcome, sourced from "
                       "`up --existing --json` nodes[].status; no fallback (D-016)"),
                   "daemonState":
                       "read-only `openrig-run status --live --json` immediately before the "
                       "down->fresh resume; requires plan.stateSource=='ps' AND "
                       "plan.stateBefore.daemonState=='running' (fixture stateSource is "
                       "refused, QA R-003)",
                   "daemonStateProvenance": "openrig-run status --live --json",
                   "mutationBeforeReject": "ps/transcript fingerprint unchanged across the refusal",
                   "unauthorizedRc": "fresh without --reason must be rc2 fresh_reason_missing"},
        )

    # -- D-018/D-019: the daemon must still be running before a resume --------
    def _probe_daemon_state(self, run_dir: Path, label: str) -> tuple[dict, str, dict]:
        """Read-only `openrig-run status --live --json` immediately before a resume.

        Why the continuity plan is the signal: `status` only builds one after
        `ps --nodes` answered live, so a plan object proves the daemon is reachable. A
        daemon that is down yields `continuity_state_unavailable` instead. Nothing here
        probes a mutation, and the command is the one D-019 names.
        """
        res = self.run(label, [*self.cli(), "status", "--run-dir", str(run_dir),
                               "--live", "--json"], env=self.env(), cwd=ROOT,
                       timeout=self.timeout)
        payload = _json_or(res["stdout"], default=None)
        plan = payload.get("continuity") if isinstance(payload, dict) else None
        plan = plan if isinstance(plan, dict) else {}
        # QA R-003: a continuity object alone proves nothing — `load_observed_state`
        # prefers a local fixture `continuity-state.json` (stateSource=="fixture"), so a
        # stale file would report a plan even with the daemon dead. The plan must say the
        # state came from `ps`, and the live branch must have set daemonState=running
        # because ps answered. Anything less is `unreachable`, and the row fails closed.
        live_proven = (plan.get("stateSource") == "ps"
                       and (plan.get("stateBefore") or {}).get("daemonState") == "running")
        state = "running" if live_proven else "unreachable"
        payload_error = ((payload or {}).get("error") or {}).get("code") \
            if isinstance(payload, dict) else None
        if live_proven:
            reason, refusal = "live-proven", None
        elif not plan:
            # No plan at all: the daemon did not answer (or the bridge is unusable).
            reason, refusal = "no-plan", "daemon_stopped_resume_not_certified"
        else:
            # A plan exists but it did not come from a live `ps` (a local fixture
            # continuity-state.json wins in load_observed_state), or its daemonState is not
            # running. Either way the daemon is NOT proven live.
            reason = ("state-source-not-ps" if plan.get("stateSource") != "ps"
                      else "daemon-state-not-running")
            refusal = "daemon_state_not_live"
        return res, state, {
            "refusalCode": refusal,
            "reason": reason,
            "stateSource": plan.get("stateSource"),
            "daemonState": (plan.get("stateBefore") or {}).get("daemonState"),
            "statusErrorCode": payload_error,
            "rc": res["rc"],
        }

    # -- CERT-05: manifest + partial -------------------------------------------
    def cert_05_manifest(self) -> dict:
        ctx = self.ctx
        cmds = []
        manifest_path = Path(ctx["runDir"]) / "reports/evidence/manifest/run-manifest.json"
        manifest = _read_json(manifest_path) or {}
        missing = [k for k in MANIFEST_REQUIRED_KEYS if k not in manifest]
        steps = manifest.get("steps") or []
        receipts = bool(steps) and all(
            (s.get("cmd") or s.get("argv")) and s.get("rc") is not None
            and s.get("stdoutSha256") for s in steps)
        # Controlled failure: a SECOND run dir, own home, own port that cannot come up.
        partial_dir = Path(ctx["workDir"]) / "partial-run"
        partial_home = Path(ctx["workDir"]) / "partial-home"
        port2 = pick_port(ctx["portBase"] + 5, 5) or (ctx["portBase"] + 9)
        self._write_minimal_bundle(partial_dir, partial_home, port2, valid_rig=False)
        fail = self.run("controlled-failure-start",
                        [*self.cli(), "start", "--run-dir", str(partial_dir), "--json"],
                        env={**self.env(), "OPENRIG_HOME": str(partial_home),
                             "OPENRIG_PORT": str(port2)},
                        cwd=ROOT, timeout=self.timeout + 60)
        cmds.append(fail)
        partial_path = partial_dir / "reports/evidence/manifest/run-manifest.partial.json"
        partial = _read_json(partial_path) or {}
        partial_ok = bool(partial) and bool(partial.get("failure") or partial.get("partial"))
        observed = {
            "manifestKeySet": not missing,
            "stepReceipts": receipts,
            "partialOnControlledFailure": partial_ok and fail["rc"] != 0,
        }
        return self._row(
            "CERT-05", scenario="manifest and partial evidence", observed=observed, commands=cmds,
            rc=0 if all(observed.values()) else 1,
            code=None if all(observed.values()) else "manifest_evidence_incomplete",
            notes=[f"manifest={manifest_path}", f"missingKeys={missing}",
                   f"steps={len(steps)} partialRc={fail['rc']}",
                   f"partial={partial_path}",
                   "FINAL.md is a close_round artifact (N-CLOSE-01), not produced here"],
            basis={"manifestKeySet": "run-manifest.json carries all 14 REQUIRED_TOP_KEYS",
                   "stepReceipts": "every steps[] entry has cmd/argv+rc+stdoutSha256 "
                                    "(real product uses cmd; argv kept as fallback)",
                   "partialOnControlledFailure": "a deliberately invalid second start wrote "
                                                 "run-manifest.partial.json with failure detail"},
        )

    def _write_minimal_bundle(self, run_dir: Path, home: Path, port: int, *, valid_rig: bool) -> None:
        bundle = run_dir / "openrig"
        (bundle / "agents" / "cert").mkdir(parents=True, exist_ok=True)
        (home / "entry").mkdir(parents=True, exist_ok=True)
        if valid_rig:
            members = ("  - id: cert\n    agent_ref: local:./agents/cert\n    profile: default\n"
                       "    runtime: opencode\n    role: cert\n")
        else:
            # A rig spec that cannot come up: the up step must fail for a real reason.
            members = ("  - id: cert\n    agent_ref: local:./agents/does-not-exist\n"
                       "    profile: default\n    runtime: opencode\n    role: cert\n")
        (bundle / "rig.yaml").write_text(
            "version: '0.2'\n"
            f"name: {run_dir.name}\nsummary: 'S10 controlled-failure fixture (real CLI, failing spec).'\n"
            f"pods:\n- id: cert\n  label: Certification\n  members:\n{members}  edges: []\nedges: []\n",
            encoding="utf-8")
        (bundle / "workflow.yaml").write_text(
            "workflow:\n"
            f"  id: {run_dir.name}\n  version: 1\n  objective: 'controlled failure'\n"
            f"  target:\n    rig: {run_dir.name}\n"
            "  entry:\n    role: cert\n  exception_routing:\n    orchestrator_role: cert\n"
            f"  roles:\n    cert:\n      preferred_targets: "
            f"[{canonical_session('cert', 'cert', run_dir.name)}]\n"
            "  steps:\n    - id: only\n      actor_role: cert\n      objective: 'noop'\n"
            "      allowed_exits: [done, failed]\n"
            "  invariants:\n    allowed_exits: [done, failed]\n",
            encoding="utf-8")
        (bundle / "agents" / "cert" / "agent.yaml").write_text(
            "name: cert\nversion: '1.0.0'\nresources:\n  skills: []\n"
            "profiles:\n  default:\n    uses:\n      skills: []\nstartup:\n  files: []\n  actions: []\n",
            encoding="utf-8")
        files = {rel: {"bytes": (bundle / rel).stat().st_size,
                       "sha256": sha256_file(bundle / rel)}
                 for rel in ("rig.yaml", "workflow.yaml", "agents/cert/agent.yaml")}
        write_json(bundle / "render-manifest.json",
                   {"schemaVersion": 1, "runId": run_dir.name, "files": files})
        write_json(bundle / "OPENRIG-BRIDGE.json", {
            "schemaVersion": 2, "runId": run_dir.name, "projectRoot": str(run_dir),
            "bundleDir": ".", "rigName": run_dir.name, "workflowId": run_dir.name,
            "rigSpec": "rig.yaml", "workflowSpec": "workflow.yaml",
            "openrigCli": self.rig()[0], "openrigHome": str(home), "daemonPort": port,
            "seatMap": {"cert": canonical_session("cert", "cert", run_dir.name)},
            "runtimeEnv": {"OPENRIG_OPENCODE_MODEL": "deepseek/deepseek-flash"},
            "policy": {"mode": "managed-isolated", "maxActiveAgents": 1,
                       "maxHops": 2, "preferResume": True, "safetyMode": "on-demand",
                       "allowSourceChanges": False},
            "_certification": {"runId": RUN_ID, "role": "controlled-failure"},
        })

    # -- CERT-06: direct L3 HTTP denial ----------------------------------------
    def cert_06_http(self) -> dict:
        ctx = self.ctx
        cmds = []
        launch_path = Path(ctx["home"]) / "entry" / "launch.json"
        try:
            original_phase = str(json.loads(launch_path.read_text(encoding="utf-8")).get("phase") or "active")
        except Exception:  # noqa: BLE001
            original_phase = "active"
        closed = self._close_ticket()
        cmds.append(closed)
        if closed["rc"] != 0:
            return self._row(
                "CERT-06", scenario="direct L3 HTTP denial",
                observed={"s1MutationRc": None, "handlerCalls": None,
                          "readOnlyAllowed": None, "s2Allowed": None},
                commands=cmds, rc=2, code="ticket_close_failed",
                notes=[f"close-ticket rc={closed['rc']}; the launch record was not closed in place",
                       "the L3 probe was not attempted, so this is NOT a guard failure"],
                basis={"s1MutationRc": "not attempted: launch ticket close failed first"})
        s1 = _http_json("POST", ctx["port"], "/api/seat/launch/cert")
        cmds.append(self._http_cmd("s1-mutation", s1))
        ro = _http_json("GET", ctx["port"], "/api/ps")
        cmds.append(self._http_cmd("read-only", ro))

        # P-024: restore the live ticket immediately after the probe and verify it, so a
        # failure is reported here (ticket_restore_failed), not on CERT-07.
        phase_restored = _restore_launch_phase(launch_path, original_phase)
        try:
            restored_phase = str(json.loads(launch_path.read_text(encoding="utf-8")).get("phase") or "")
        except Exception:  # noqa: BLE001
            restored_phase = ""
        denied = (s1["status"] == 403
                  and str((s1.get("body") or {}).get("error", {}).get("code")) == "entry_guard_http_denied")
        handler_calls = 0 if denied else 1
        if not phase_restored:
            return self._row(
                "CERT-06", scenario="direct L3 HTTP denial",
                observed={"s1MutationRc": s1["status"], "handlerCalls": handler_calls,
                          "readOnlyAllowed": ro["status"] == 200, "s2Allowed": None,
                          "ticketPhaseRestored": False},
                commands=cmds, rc=2, code="ticket_restore_failed",
                notes=[f"original phase={original_phase!r}; after probe={restored_phase!r}",
                       "the live ticket stayed closed; CERT-07 would be poisoned, so the "
                       "failure is reported here by name"],
                basis={"ticketPhaseRestored": "re-read launch.json immediately after the probe"})
        s2_port = pick_port(ctx["portBase"] + 7, 2) or (ctx["portBase"] + 9)
        s2_home = Path(ctx["workDir"]) / "s2-home"
        (s2_home / "entry").mkdir(parents=True, exist_ok=True)
        daemon2 = self.run("s2-daemon-start",
                           [*self.rig(), "daemon", "start", "--no-kernel", "--port", str(s2_port)],
                           env={**self.env(), "OPENRIG_HOME": str(s2_home),
                                "OPENRIG_PORT": str(s2_port)},
                           timeout=self.timeout)
        cmds.append(daemon2)
        s2 = _http_json("POST", s2_port, "/api/seat/launch/cert")
        cmds.append(self._http_cmd("s2-mutation", s2, home=str(s2_home), port=s2_port))
        s2_allowed = not (s2["status"] == 403
                          and str((s2.get("body") or {}).get("error", {}).get("code"))
                          == "entry_guard_http_denied")
        self.run("s2-daemon-stop", [*self.rig(), "daemon", "stop"],
                 env={**self.env(), "OPENRIG_HOME": str(s2_home), "OPENRIG_PORT": str(s2_port)})
        observed = {
            "s1MutationRc": s1["status"],
            "handlerCalls": handler_calls,
            "readOnlyAllowed": ro["status"] == 200,
            "s2Allowed": s2_allowed,
            "ticketPhaseRestored": True,
        }
        return self._row(
            "CERT-06", scenario="direct L3 HTTP denial", observed=observed, commands=cmds,
            rc=0 if all([s1["status"] == 403, ro["status"] == 200, s2_allowed]) else 1,
            code=None if denied else "http_deny_missing",
            notes=[f"deniedBody={json.dumps(s1.get('body'), ensure_ascii=False)[:300]}",
                   f"s2Home={s2_home} s2Status={s2['status']}",
                   "handlerCalls is 0 only when the response carries the guard's deny body "
                   "(status 403 + entry_guard_http_denied + openrig-run hint); the route's own "
                   "handler never emits that body"],
            basis={"s1MutationRc": "real daemon; live ticket closed ONLY for the L3 probe, "
                                   "POST /api/seat/launch/cert, then original phase restored "
                                   "and read-back verified (ticketPhaseRestored)",
                   "handlerCalls": "deny-body signature (see note)",
                   "readOnlyAllowed": "GET /api/ps on the same denying daemon",
                   "s2Allowed": "second real daemon whose OPENRIG_HOME is run-shaped, not managed"},
        )

    def _close_ticket(self) -> dict:
        """Close the live launch record in place: the state a daemon still holds after expiry."""
        ctx = self.ctx
        sys.path.insert(0, str(SCRIPTS))
        import openrig_run as orr  # local import: the product's own close path

        path = Path(ctx["home"]) / "entry" / "launch.json"
        try:
            launch_id = str(json.loads(path.read_text(encoding="utf-8")).get("launchId") or "")
        except Exception:  # noqa: BLE001
            launch_id = ""
        if not launch_id:
            return {
                "label": "close-ticket", "argv": ["openrig_run.close_entry_records", str(path)],
                "rc": 1, "stdoutSha256": sha256_bytes(b"failed"), "stderrSha256": sha256_bytes(b""),
                "stdoutBytes": 6, "stderrTail": [], "log": "logs/close-ticket.out",
                "errLog": "logs/close-ticket.err",
                "note": "no launchId in the live launch record",
            }
        ok = orr.close_entry_records(Path(ctx["home"]), launch_id,
                                     "S10 certification: deliberate ticket close for the L3 probe")
        try:
            phase = str(json.loads(path.read_text(encoding="utf-8")).get("phase") or "")
        except Exception:  # noqa: BLE001
            phase = ""
        ok = bool(ok) and phase == "closed"
        return {
            "label": "close-ticket", "argv": ["openrig_run.close_entry_records", str(path)],
            "rc": 0 if ok else 1, "stdoutSha256": sha256_bytes(b"closed" if ok else b"failed"),
            "note": f"launchId={launch_id} phase={phase!r} (closed required)",
            "stderrSha256": sha256_bytes(b""), "stdoutBytes": 6,
            "stderrTail": [], "startedAt": now_iso(), "endedAt": now_iso(),
            "log": "logs/ticket-close.txt", "errLog": "logs/ticket-close.err",
            "stdout": "closed" if ok else "failed",
        }

    def _http_cmd(self, label: str, result: dict, *, home: str | None = None,
                  port: int | None = None) -> dict:
        blob = json.dumps({k: v for k, v in result.items() if k != "raw"}, ensure_ascii=False)
        return {
            "label": label,
            "argv": ["http", result.get("method", "?"), f"{home or self.ctx['home']}",
                     f"port={port or self.ctx['port']}", result.get("path", "?")],
            "rc": 0, "stdoutSha256": sha256_bytes(blob.encode()),
            "stderrSha256": sha256_bytes(b""), "stdoutBytes": len(blob.encode()),
            "stderrTail": [], "startedAt": result.get("startedAt") or now_iso(),
            "endedAt": result.get("endedAt") or now_iso(),
            "log": f"logs/{_slug(label)}.http.json", "errLog": "-",
            "stdout": blob,
        }

    # -- CERT-07: archive gate before stop ------------------------------------
    def cert_07_archive_gate(self) -> dict:
        ctx = self.ctx
        cmds = []
        stop1 = self.run("stop-archive-missing",
                         [*self.cli(), "stop", "--run-dir", str(ctx["runDir"]), "--live", "--json"],
                         env=self.env(), cwd=ROOT, timeout=self.timeout)
        cmds.append(stop1)
        mutations = (_json_or(stop1["stdout"], default={}) or {}).get("mutations") or []
        ps_alive = self.run("ps-after-refused-stop",
                            [*self.rig(), "ps", "--nodes", "--rig", ctx["rigName"], "--json"],
                            env=self.env())
        cmds.append(ps_alive)
        seats = _rows_of(_json_or(ps_alive["stdout"], default=[]))
        down_calls = 0 if not mutations else len([m for m in mutations if m.get("step") == "rig-down"])
        archive = self.run("archive", [sys.executable,
                                       str(PROD / "scripts" / "openrig-archive.py"),
                                       "--run-dir", str(ctx["runDir"]),
                                       "--openrig-home", str(ctx["home"]),
                                       "--archive-root", str(ctx["archiveRoot"]),
                                       "--json"],
                           env=self.env(), cwd=PROD, timeout=self.timeout)
        cmds.append(archive)
        record = self._bind_archive(archive)
        stop2 = self.run("stop-archive-complete",
                         [*self.cli(), "stop", "--run-dir", str(ctx["runDir"]), "--live", "--json"],
                         env=self.env(), cwd=ROOT, timeout=self.timeout)
        cmds.append(stop2)
        observed = {
            "incompleteRc": stop1["rc"],
            "downCalls": down_calls,
            "completeRc": stop2["rc"],
        }
        return self._row(
            "CERT-07", scenario="archive gate before stop", observed=observed, commands=cmds,
            rc=0 if all([stop1["rc"] == 2, down_calls == 0, stop2["rc"] == 0]) else 1,
            code=_error_code(stop1) if stop1["rc"] != 2 else (
                None if stop2["rc"] == 0 else _error_code(stop2)),
            notes=[f"seatsStillSoAfterRefusal={len([s for s in seats if s.get('startupStatus')])}",
                   f"archiveRecord={record}",
                   "the run-local ARCHIVE-MANIFEST.json binds the REAL product archive "
                   "MANIFEST.json by sha256 (D-011); it is never hand-filled"],
            basis={"incompleteRc": "openrig-run stop before any archive -> rc2 archive_incomplete",
                   "downCalls": "refusal returns mutations=[] (no rig-down ran)",
                   "completeRc": "the same stop after the product archive wrote MANIFEST.json"},
        )

    def _bind_archive(self, archive_cmd: dict) -> str:
        ctx = self.ctx
        payload = _json_or(archive_cmd["stdout"], default={}) or {}
        manifest_path = None
        for key in ("manifest", "manifestPath", "manifest_path"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                manifest_path = Path(value)
                break
        if manifest_path is None:
            blob = json.dumps(payload)
            m = re.search(r'("[^"]*MANIFEST\.json")', blob)
            if m:
                manifest_path = Path(json.loads(m.group(1)))
        if manifest_path is None or not manifest_path.is_file():
            manifest_path = _find_archive_manifest(Path(ctx["archiveRoot"]))
        if manifest_path is None or not manifest_path.is_file():
            write_json(Path(ctx["runDir"]) / "reports/evidence/archive/ARCHIVE-MANIFEST.json", {
                "schemaVersion": 1, "runId": ctx["rigName"], "status": "INCOMPLETE",
                "reason": "product archive MANIFEST.json not found; never hand-filled COMPLETE",
                "archiveRc": archive_cmd["rc"],
            })
            return "unbound" if archive_cmd["rc"] != 0 else "manifest-not-found"
        product = _read_json(manifest_path) or {}
        status = str(product.get("archiveStatus") or product.get("status") or "").upper()
        if not status:
            listing = product.get("files") or product.get("artifacts") or {}
            status = "COMPLETE" if listing and product.get("completedAt") else "INCOMPLETE"
        write_json(Path(ctx["runDir"]) / "reports/evidence/archive/ARCHIVE-MANIFEST.json", {
            "schemaVersion": 1,
            "runId": ctx["rigName"],
            "status": status,
            "reason": "bound from the product archive manifest",
            "manifestPath": str(manifest_path),
            "manifestSha256": sha256_file(manifest_path),
            "archiveRc": archive_cmd["rc"],
            "boundAt": now_iso(),
        })
        return f"{status} sha256={sha256_file(manifest_path)[:16]}…"

    # -- CERT-08: negative controls -------------------------------------------
    def cert_08_negatives(self) -> dict:
        ctx = self.ctx
        cmds = []
        # (a) home conflict — the real preflight, in-process, against the control-plane
        # home. No child E2E is spawned: a negative probe must never be able to mutate.
        probe_dir = Path(ctx["controlHome"]) / "openrig-s10-cert-negative-probe"
        _, problems = preflight(work_dir=probe_dir, evidence_dir=Path(ctx["evidenceDir"]),
                                control_home=Path(ctx["controlHome"]))
        home_conflict = any(p["code"] == CODE_WORK_DIR for p in problems)
        cmds.append({
            "label": "home-conflict-preflight",
            "argv": ["preflight", "--work-dir", str(probe_dir),
                     "--control-home", str(ctx["controlHome"])],
            "rc": 2 if home_conflict else 0,
            "stdoutSha256": sha256_bytes(json.dumps(problems).encode()),
            "stderrSha256": sha256_bytes(b""), "stdoutBytes": 0, "stderrTail": [],
            "startedAt": now_iso(), "endedAt": now_iso(),
            "log": "inline://preflight", "errLog": "-",
        })
        # (b) port conflict — a real start whose port is held by the main daemon.
        clash_dir = Path(ctx["workDir"]) / "port-clash-run"
        clash_home = Path(ctx["workDir"]) / "port-clash-home"
        self._write_minimal_bundle(clash_dir, clash_home, ctx["port"], valid_rig=True)
        clash = self.run("port-conflict",
                         [*self.cli(), "start", "--run-dir", str(clash_dir), "--json"],
                         env={**self.env(), "OPENRIG_HOME": str(clash_home),
                              "OPENRIG_PORT": str(ctx["port"])},
                         cwd=ROOT, timeout=self.timeout)
        cmds.append(clash)
        # (c) stale launch — a real `rig up` carrying an expired ticket.
        stale = self._stale_launch_probe()
        cmds.append(stale)
        # (d) compaction — opencode can never claim a managed compaction.
        compact = self._compact_probe()
        cmds.append(compact["cmd"])
        # (e) orphan reporting is read-only.
        sys.path.insert(0, str(SCRIPTS))
        import openrig_gate as og  # noqa: E402  (product gate, read-only use)

        victim = {"seats": [{"logicalId": "cert", "canonicalSessionName": ctx["seatSession"],
                             "session": "present"}]}
        snap = json.dumps(victim, sort_keys=True)
        report = og.orphan_report(victim)
        orphan_read_only = (json.dumps(victim, sort_keys=True) == snap
                            and report.get("action", "").startswith("reported only"))
        observed = {
            "homeConflictRc": 2 if home_conflict else 0,
            "portConflictRc": clash["rc"],
            "staleLaunchRc": stale["rc"],
            "compactNotManagedRc": compact["rc"],
            "orphanReportReadOnly": orphan_read_only,
        }
        return self._row(
            "CERT-08", scenario="negative controls", observed=observed, commands=cmds,
            rc=0 if all([home_conflict, clash["rc"] == 2, stale["rc"] == 2,
                         compact["rc"] == 2, orphan_read_only]) else 1,
            code=None,
            notes=[f"homeConflictRefused={home_conflict}",
                   f"homeConflictProblems={[p['code'] for p in problems]}",
                   f"portConflictCode={_error_code(clash)!r}",
                   f"staleLaunchCode={stale.get('codeSeen')!r}",
                   f"compactBasis={compact['basis']}"],
            basis={"homeConflictRc": "harness preflight refuses the control-plane home (rc2)",
                   "portConflictRc": "real start on a held port -> port_collision",
                   "staleLaunchRc": "real rig up with an expired launch record -> entry_guard_expired",
                   "compactNotManagedRc": compact["basis"],
                   "orphanReportReadOnly": "openrig_gate.orphan_report mutates nothing it was given"},
        )

    def _stale_launch_probe(self) -> dict:
        ctx = self.ctx
        home = Path(ctx["workDir"]) / "stale-home"
        (home / "entry").mkdir(parents=True, exist_ok=True)
        write_json(home / "entry" / "managed-run.json", {"schemaVersion": 1, "runId": "stale"})
        launch_id = "launch-expired-cert"
        write_json(home / "entry" / "launch.json", {
            "schemaVersion": 1, "launchId": launch_id, "home": str(home),
            "runId": "stale", "phase": "starting",
            "expiresAt": "2000-01-01T00:00:00Z",
            "verbs": list(ENTRY_VERBS), "consumed": [],
        })
        rig_yaml = Path(ctx["workDir"]) / "stale-rig.yaml"
        rig_yaml.write_text("version: '0.2'\nname: stale\npods: []\nedges: []\n", encoding="utf-8")
        res = self.run("stale-launch",
                       [*self.rig(), "up", str(rig_yaml), "--yes"],
                       env={**self.env(), "OPENRIG_HOME": str(home),
                            "OPENRIG_ENTRY_LAUNCH_ID": launch_id},
                       timeout=self.timeout)
        blob = (res.get("stdout") or "") + (res.get("stderr") or "")
        res["codeSeen"] = "entry_guard_expired" if "entry_guard_expired" in blob else None
        return res

    def _compact_probe(self) -> dict:
        ctx = self.ctx
        body = json.dumps({"session": ctx["seatSession"]}).encode()
        result = _http_json("POST", ctx["port"], "/api/compaction/trigger", body=body)
        sys.path.insert(0, str(SCRIPTS))
        import openrig_gate as og  # noqa: E402

        verdict = og.compact_verdict("opencode", requested=True)
        # CLI convention: a refusal (ok=False) is rc2. The HTTP surface answers 422
        # runtime_filter for the same refusal; both are recorded so neither is inferred.
        rc = 0 if verdict["ok"] else 2
        cmd = self._http_cmd("compact-trigger", result)
        cmd["rc"] = rc
        return {"rc": rc, "cmd": cmd,
                "basis": f"gate.compact_verdict ok={verdict['ok']} code={verdict['code']!r} "
                         f"+ http {result['status']} {json.dumps(result.get('body'), ensure_ascii=False)[:120]}"}

    # -- CERT-09: cleanup ------------------------------------------------------
    def cert_09_cleanup(self) -> dict:
        ctx = self.ctx
        cmds = []
        archive = _read_json(Path(ctx["runDir"]) / "reports/evidence/archive/ARCHIVE-MANIFEST.json") or {}
        daemon = self.run("daemon-status", [*self.rig(), "daemon", "status"], env=self.env())
        cmds.append(daemon)
        unit_inactive = daemon["rc"] != 0 or not _listening(ctx["port"])
        ports_free = all(port_is_free(p) for p in
                         {ctx["port"], ctx["portBase"] + 5, ctx["portBase"] + 7})
        tmux = self.run("tmux-list", ["bash", "-lc",
                                      "tmux ls -F '#{session_name}' 2>/dev/null || true"],
                        env=os.environ.copy())
        cmds.append(tmux)
        tmux_absent = not any(ctx["rigName"] in line or ctx["seatSession"].split("@")[0] in line
                              for line in (tmux.get("stdout") or "").splitlines())
        pgrep = self.run("pgrep-home", ["bash", "-lc",
                                        f"pgrep -af {json.dumps(str(ctx['home']))} || true"],
                         env=os.environ.copy())
        cmds.append(pgrep)
        # `pgrep -af` matches its own wrapper's command line; the wrapper is not a daemon.
        strays = [ln for ln in (pgrep.get("stdout") or "").splitlines()
                  if "pgrep -af" not in ln and ln.strip()]
        daemon_absent = not strays
        control = self.run("control-rig-intact",
                           [*self.rig(), "ps", "--nodes", "--rig", CONTROL_RIG, "--json"],
                           env=self.control_env())
        cmds.append(control)
        control_rows = _rows_of(_json_or(control["stdout"], default=[]))
        control_ok = len(control_rows) >= 3
        observed = {
            "archiveStatus": str(archive.get("status") or "MISSING").upper(),
            "unitInactive": bool(unit_inactive),
            "portFree": bool(ports_free),
            "tmuxAbsent": bool(tmux_absent),
            "daemonAbsent": bool(daemon_absent),
        }
        return self._row(
            "CERT-09", scenario="cleanup", observed=observed, commands=cmds,
            rc=0 if (observed["archiveStatus"] == "COMPLETE" and all(
                [unit_inactive, ports_free, tmux_absent, daemon_absent, control_ok])) else 1,
            code=None if control_ok else "control_rig_affected",
            hard_fail=not control_ok, fail_label="controlRigIntact",
            notes=[f"controlPlaneSeats={len(control_rows)}; controlHome={CONTROL_HOME}; controlPort=48010",
                   "no rm -rf of the cert home/DB/transcript: cleanup means no LIVE residue (D-010)"],
            basis={"archiveStatus": "run-local ARCHIVE-MANIFEST.json bound to the product manifest",
                   "unitInactive": "rig daemon status is down and the port does not answer",
                   "portFree": "bind probe on every port this attempt used",
                   "tmuxAbsent": "no tmux session names the cert rig/seat",
                   "daemonAbsent": "no process command line references the cert home"},
        )

    # -- CERT-10: static regression -------------------------------------------
    def cert_10_static(self) -> dict:
        cmds = []
        s8s9 = self.run("reg-s8s9-matrix",
                        [sys.executable,
                         str(ROOT / "runs/openrig-s9-wave-b-20261116/reports/tools/matrix_run_s9.py"),
                         "--only", "AT-S9-ENT-06,AT-S9-ENT-07,AT-S9-IO-01,AT-S9-IO-02,"
                                   "AT-S9-GATE-02,AT-S9-GATE-03,AT-S9-CT-10"],
                        cwd=ROOT, timeout=1800)
        cmds.append(s8s9)
        docs = self.run("reg-doc-consistency",
                        ["bash", "-lc",
                         "out=$(python3 scripts/doc_consistency.py --check 2>&1 || true); echo \"$out\"; "
                         "! echo \"$out\" | grep '^ERROR' | grep -v 'tags-count'"],
                        cwd=ROOT)
        cmds.append(docs)
        lock = self.run("reg-contract-lock",
                        [sys.executable, str(ROOT / "scripts/contract_lock.py"), "check"], cwd=ROOT)
        cmds.append(lock)
        budget = self.run("reg-doc-budget",
                          [sys.executable,
                           str(ROOT / f"runs/{RUN_ID}/reports/tools/check_tree_s10.py"), "--budget"],
                          cwd=ROOT)
        cmds.append(budget)
        observed = {
            "s8s9Matrix": s8s9["rc"] == 0,
            "docConsistency": docs["rc"] == 0,
            "contractLock": lock["rc"] == 0,
            "docBudget": budget["rc"] == 0,
        }
        return self._row(
            "CERT-10", scenario="S8/S9 regression and docs", observed=observed, commands=cmds,
            rc=0 if all(observed.values()) else 1,
            code=None if all(observed.values()) else "regression_failed",
            notes=["doc_consistency tolerates the pre-existing tags-count baseline error only"],
        )

    # -- evidence projection / finish ----------------------------------------
    def _project(self, row: dict) -> None:
        evidence = Path(self.ctx["evidenceDir"])
        attempt_file = Path(self.ctx["attemptDir"]) / f"{row['row']}.json"
        write_json(attempt_file, row)
        projection = evidence / f"{row['row']}.json"
        if projection.exists():
            existing = _read_json(projection) or {}
            row["projection"] = {
                "keptFirstAttempt": existing.get("attemptId"),
                "keptFirstPass": existing.get("pass"),
                "thisAttemptPass": row.get("pass"),
                "overwritten": False,
            }
        else:
            write_json(projection, row)
            row["projection"] = {"createdBy": row["attemptId"], "overwritten": False}

    def _finish(self) -> dict:
        ctx = self.ctx
        evidence = Path(ctx["evidenceDir"])
        ledger_path = evidence / "CERT-E2E.json"
        ledger = _read_json(ledger_path) or {
            "schemaVersion": SCHEMA, "runId": RUN_ID,
            "evidenceRoot": str(evidence),
            "required": list(EVIDENCE_REQUIRED),
            "runtimeBoundary": {
                "certifiedRuntime": "opencode", "model": "deepseek/deepseek-flash",
                "seats": 1, "workflowSteps": 1,
                "notCertified": ["claude-code", "codex", "dsh", "kernel", "remote-host",
                                 "multi-seat-concurrency"],
            },
            "attempts": [],
            "notes": [
                "CERT-0N.json at the evidence root is a projection of the FIRST attempt that "
                "produced that row; later attempts are kept under attempts/<attemptId>/ and can "
                "never overwrite a failed projection.",
                "reports/certification/FINAL.md is produced at close_round (N-CLOSE-01), not here.",
            ],
        }
        attempts = ledger.setdefault("attempts", [])
        rows = [r for r in self.rows]
        warned = [r for r in rows if r.get("warn") and not r.get("pass")]
        failed = [r for r in rows if not r.get("pass") and not r.get("warn")]
        attempts.append({
            "attemptId": ctx["attemptId"],
            "launchId": ctx["launchId"],
            "workDir": str(ctx["workDir"]),
            "home": str(ctx["home"]),
            "port": ctx["port"],
            "rigName": ctx["rigName"],
            "rigBin": ctx.get("rigBin"),
            "rigBinSource": ctx.get("rigBinSource"),
            "harnessPath": self.harness_path,
            "harnessSha256": self.harness_sha256,
            "harnessTestsPath": self.tests_path,
            "harnessTestsSha256": self.tests_sha256,
            "startedAt": self.started_at,
            "endedAt": now_iso(),
            "rows": {r["row"]: {"pass": r.get("pass"), "rc": r.get("rc"),
                                "code": (r.get("error") or {}).get("code"),
                                "notAttempted": bool(r.get("notAttempted"))}
                     for r in rows},
            "counts": {"rows": len(rows),
                       "passed": sum(1 for r in rows if r.get("pass")),
                       "warned": len(warned), "failed": len(failed)},
            "executionOrder": list(EXECUTION_ORDER),
            "warnRows": [r["row"] for r in warned],
            "failureTeardown": self.failureTeardown,
            "firstFailure": (failed[0]["row"] if failed else None),
            "humanGate": {
                "executeFlag": "--execute",
                "operatorApproved": None,
                "approvalSource": "not verified by harness",
                "executorSession": os.environ.get("OPENRIG_SESSION_NAME"),
                "llmMayNotSelfApprove": True,
            },
        })
        ledger["projections"] = {
            r["row"]: {"attemptId": (r.get("projection") or {}).get("keptFirstAttempt")
                       or (r.get("projection") or {}).get("createdBy"),
                       "pass": (r.get("projection") or {}).get("keptFirstPass")
                       if "keptFirstPass" in (r.get("projection") or {}) else r.get("pass")}
            for r in rows
        }
        ledger["counts"] = {
            "attempts": len(attempts),
            "rowsThisAttempt": len(rows),
            "passedThisAttempt": sum(1 for r in rows if r.get("pass")),
            "warnedThisAttempt": len(warned),
            "failedThisAttempt": len(failed),
        }
        ledger["updatedAt"] = now_iso()
        write_json(ledger_path, ledger)
        missing = [n for n in EVIDENCE_REQUIRED if not (evidence / n).is_file()]
        summary = {
            "schemaVersion": SCHEMA,
            "runId": RUN_ID,
            "attemptId": ctx["attemptId"],
            "ok": not failed,
            "status": "pass-with-warn" if (not failed and warned) else ("pass" if not failed else "fail"),
            "warnings": [r["row"] for r in warned],
            "warnRows": [r["row"] for r in warned],
            "passWithWarn": bool(not failed and warned),
            "rc": 0 if not failed else 1,
            "workDir": str(ctx["workDir"]),
            "home": str(ctx["home"]),
            "port": ctx["port"],
            "rigName": ctx["rigName"],
            "harnessPath": self.harness_path,
            "harnessSha256": self.harness_sha256,
            "harnessTestsPath": self.tests_path,
            "harnessTestsSha256": self.tests_sha256,
            "rows": [{k: r.get(k) for k in ("row", "pass", "warn", "rc", "notAttempted", "mismatched")}
                     | {"code": (r.get("error") or {}).get("code")} for r in rows],
            "firstFailure": failed[0]["row"] if failed else None,
            "failureTeardown": self.failureTeardown,
            "residueRemaining": (bool((self.failureTeardown or {}).get("residueRemaining"))
                                 if self.failureTeardown else bool(failed)),
            "clean": (not bool((self.failureTeardown or {}).get("residueRemaining"))
                      if self.failureTeardown else not bool(failed)),
            "evidenceMissing": missing,
            "ledger": str(ledger_path),
            "capturedAt": now_iso(),
        }
        write_json(Path(ctx["attemptDir"]) / "summary.json", summary)
        return summary


ROWS_SEMANTICS = {
    "CERT-01": "real start", "CERT-02": "real prompt and marker", "CERT-03": "real resume",
    "CERT-04": "explicit fresh and unauthorized fresh",
    "CERT-05": "manifest and partial evidence", "CERT-06": "direct L3 HTTP denial",
    "CERT-07": "archive gate before stop", "CERT-08": "negative controls",
    "CERT-09": "cleanup", "CERT-10": "S8/S9 regression and docs",
}
EXECUTION_ORDER = ["CERT-01", "CERT-02", "CERT-03", "CERT-04", "CERT-05",
                   "CERT-06", "CERT-08", "CERT-07", "CERT-09", "CERT-10"]


# --------------------------------------------------------------------- observation helpers
def _marker_objective(ctx: dict) -> str:
    return (
        "Write the JSON object {\\\"nonce\\\": \\\"" + ctx["nonce"] + "\\\", "
        "\\\"step\\\": \\\"certify\\\"} to the ABSOLUTE path "
        + str(ctx["marker"]) + " and then reply with one line: DONE. "
        "Do nothing else. This marker is the proof that a real prompt executed."
    )


def _rows_of(payload) -> list[dict]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("nodes", "rows", "qitems", "items", "workflows", "instances"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def _json_or(text: str, *, default):
    try:
        return json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return default


def _read_json(path: Path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _error_code(cmd: dict) -> str | None:
    payload = _json_or(cmd.get("stdout") or "", default=None)
    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, dict) and err.get("code"):
            return str(err["code"])
        if isinstance(err, str) and err:
            return err
    blob = (cmd.get("stderr") or "") + (cmd.get("stdout") or "")
    for code in ("entry_guard_expired", "entry_guard_denied", "port_collision",
                 "archive_incomplete", "fresh_reason_missing", "continuity_blocked",
                 "continuity_mismatch", "human_gate_required", "work_dir_not_isolated"):
        if code in blob:
            return code
    return None


def _restore_launch_phase(path: Path, phase: str) -> bool:
    """P-024: restore a probe-mutated launch phase and verify the read-back."""
    try:
        record = json.loads(Path(path).read_text(encoding="utf-8"))
        record["phase"] = phase
        write_json(Path(path), record)
        after = str(json.loads(Path(path).read_text(encoding="utf-8")).get("phase") or "")
        return after == phase
    except Exception:  # noqa: BLE001
        return False


def _capture_degraded(stdout: str) -> bool:
    """True only when the transcript itself reports ingest degradation (P-013)."""
    try:
        data = json.loads(stdout or "")
    except Exception:  # noqa: BLE001
        data = None
    if isinstance(data, dict):
        health = data.get("ingestHealth") or {}
        if isinstance(health, dict) and str(health.get("state")) == "degraded":
            return True
    return "capture_empty" in (stdout or "")


def _prompt_in(blob: str, ctx: dict) -> bool:
    if ctx["nonce"] in blob:
        return True
    return "certification" in blob.lower() and "marker" in blob.lower()


def _observe_resume(*, pre: str, post: str, seat_row: dict) -> tuple[str, str]:
    """Observe 'resumed' from real artefacts instead of a product field that does not exist.

    resumed  = the pre-stop transcript content survives in the post-resume transcript AND
               the seat row is still the same canonical session.
    fresh    = the transcript no longer carries the pre-stop content (a new session).
    unknown  = neither signal is decisive; the caller records it rather than guessing.
    """
    seat = (seat_row or {}).get("canonicalSessionName")
    probe = _transcript_probe(pre)
    if probe and probe in post:
        return "resumed", (
            "pre-stop transcript content is still present after resume, and the seat row "
            f"({seat or 'n/a'}) is the same canonical session")
    if probe and not post.strip():
        return "fresh-primed", "post-resume transcript is empty: the session did not continue"
    return "unknown", "no decisive transcript continuity signal"


def _observe_fresh(*, pre: str, transcript: str, seat_row: dict) -> tuple[str, str]:
    if not pre:
        return "unknown", "no pre-stop transcript probe recorded"
    if pre not in transcript and transcript.strip():
        return "fresh-primed", (
            "the new session's transcript does not contain the pre-stop marker prompt: "
            "a fresh occupant, as authorized")
    if pre in transcript:
        return "resumed", "the pre-stop content survived a request that asked for a fresh seat"
    return "unknown", "transcript empty or unreadable after the authorized fresh"


def _transcript_probe(blob: str) -> str:
    """A stable line from the transcript that proves continuity (never a timestamp)."""
    for line in reversed([ln for ln in (blob or "").splitlines() if ln.strip()]):
        if len(line.strip()) >= 16 and not re.match(r"^\s*[{}\[\]]\s*$", line):
            return line.strip()[:120]
    return ""


def _state_fingerprint(cert: "Certifier") -> str:
    """A cheap 'did anything change' fingerprint for the unauthorized-fresh refusal."""
    ctx = cert.ctx
    ps = cert.run("ps-fingerprint", [*cert.rig(), "ps", "--nodes", "--rig", ctx["rigName"],
                                     "--json"], env=cert.env())
    return sha256_bytes((ps.get("stdout") or "").encode())


def _listening(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def _find_archive_manifest(root: Path) -> Path | None:
    if not Path(root).exists():
        return None
    for path in sorted(Path(root).rglob("MANIFEST.json")):
        return path
    return None


def _http_json(method: str, port: int, path: str, *, body: bytes | None = None,
               host: str = "127.0.0.1", timeout: float = 10.0) -> dict:
    started = now_iso()
    url = f"http://{host}:{port}{path}"
    request = urllib.request.Request(url, method=method, data=body)
    if body is not None:
        request.add_header("content-type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
            status = response.status
    except urllib.error.HTTPError as exc:  # 4xx/5xx are answers, not transport failures
        raw = exc.read().decode("utf-8", "replace")
        status = exc.code
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raw, status = f'{{"transportError": {json.dumps(str(exc))}}}', 0
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"raw": raw[:2000]}
    return {"method": method, "path": path, "status": status, "body": parsed,
            "raw": raw, "startedAt": started, "endedAt": now_iso()}


# --------------------------------------------------------------------- CLI
def _print_plan(ctx: dict | None, args) -> None:
    print("This harness performs REAL lifecycle mutations (daemon, rig, seat, archive).")
    print("It refuses to run without --execute; approval is an operator decision (D-004).")
    print("")
    print("Operator command:")
    print(f"  {sys.executable} scripts/openrig_certify.py --work-dir {args.work_dir} "
          f"--evidence-dir {args.evidence_dir} --execute --json")
    print("")
    print("Rows in execution order: " + ", ".join(EXECUTION_ORDER))
    if ctx:
        print(f"Would use home={ctx['home']} port={ctx['port']} "
              f"attempt={ctx['attemptId']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="S10 operator-gated certification harness (one real minimal E2E)")
    ap.add_argument("--work-dir", required=True,
                    help="isolated /tmp/openrig-s10-cert-* work dir")
    ap.add_argument("--evidence-dir", required=True,
                    help="run evidence root (reports/certification)")
    ap.add_argument("--execute", action="store_true",
                    help="HUMAN gate: actually run the lifecycle. Without it: rc2, no writes.")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--marker-timeout", type=int, default=240)
    ap.add_argument("--port-base", type=int, default=48110)
    ap.add_argument("--port-span", type=int, default=10)
    ap.add_argument("--control-home", default=str(CONTROL_HOME))
    ap.add_argument("--rig-bin", default="",
                    help="rig binary to pin for this attempt (default: PATH); the ambient "
                         "OPENRIG_RIG_BIN is deliberately ignored")
    ap.add_argument("--ignore-cert-residue", action="store_true",
                    help="certify even if a previous attempt's daemon/seat is still alive "
                         "(recorded; the clean path refuses instead)")
    args = ap.parse_args(argv)

    ctx, problems = preflight(
        work_dir=Path(args.work_dir),
        evidence_dir=Path(args.evidence_dir),
        control_home=Path(args.control_home),
        port_base=args.port_base,
        port_span=args.port_span,
        ignore_cert_residue=args.ignore_cert_residue,
        rig_bin=args.rig_bin,
    )

    if not args.execute:
        payload = {
            "schemaVersion": SCHEMA, "runId": RUN_ID, "ok": False, "rc": 2,
            "error": {"code": CODE_HUMAN_GATE,
                      "message": "--execute is required; the human gate was not opened",
                      "hint": f"{sys.executable} scripts/openrig_certify.py --work-dir {args.work_dir} "
                              f"--evidence-dir {args.evidence_dir} --execute --json"},
            "preflight": {"problems": problems,
                          "workDir": str(args.work_dir),
                          "port": (ctx or {}).get("port"),
                          "attemptId": (ctx or {}).get("attemptId")},
            "wrote": [],
            "capturedAt": now_iso(),
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            _print_plan(ctx, args)
        return 2

    if problems:
        payload = {
            "schemaVersion": SCHEMA, "runId": RUN_ID, "ok": False, "rc": 2,
            "error": {"code": problems[0]["code"], "message": problems[0]["message"]},
            "problems": problems, "wrote": [], "capturedAt": now_iso(),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json
              else f"[REFUSED] {problems[0]['code']}: {problems[0]['message']}")
        return 2

    attempt_dir = Path(ctx["attemptDir"])
    if attempt_dir.exists():
        payload = {
            "schemaVersion": SCHEMA, "runId": RUN_ID, "ok": False, "rc": 2,
            "error": {"code": CODE_ATTEMPT,
                      "message": f"attempt directory already exists: {attempt_dir}",
                      "hint": "a new attempt must get a new --work-dir; attempts are never overwritten"},
            "capturedAt": now_iso(),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json
              else f"[REFUSED] {CODE_ATTEMPT}: {attempt_dir}")
        return 2

    cert = Certifier(ctx, timeout=args.timeout, marker_timeout=args.marker_timeout)
    summary = cert.execute()
    print(json.dumps(summary, ensure_ascii=False, indent=2) if args.json
          else f"[{'PASS' if summary['ok'] else 'FAIL'}] rows={summary['counts'] if 'counts' in summary else ''} "
               f"firstFailure={summary.get('firstFailure')}")
    return int(summary["rc"])


if __name__ == "__main__":
    sys.exit(main())
