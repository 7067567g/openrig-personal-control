# -*- coding: utf-8 -*-
"""S9 Wave B · entry residuals — real rc for W-S8-10 / W-S8-14 / W-S8-11 / W-S8-05.

Every fixture is built inside pytest `tmp_path` (W-S8-12); no real `rig`, daemon or seat
is invoked, and nothing is written into the repo. The cross-boundary cases call the
product's own drivers so the assertion runs against the shipped guard, not a re-statement
of it:

  AT-S9-ENT-03  openrig_run.py start --dry-run            -> rc 0, phase=closed, dryRun
  AT-S9-ENT-04  entry-guard-driver.ts on that home        -> rc 2, entry_guard_closed
  AT-S9-ENT-02  atomic-token-driver ledger-write-failure  -> rc 2, token_write_failed
  AT-S9-ENT-01  atomic-token-driver 12 processes          -> rc 0, exactly one allowed
  AT-S9-ENT-06  http-admission-driver lifecycle-mutation  -> rc 2, http_denied, 0 handlers
  AT-S9-ENT-07  http-admission-driver read-only           -> rc 0
  AT-S9-ENT-05  json-denial-driver + JSON predicate       -> rc 0
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import openrig_run as orr  # noqa: E402

_PRODUCT_ENV = os.environ.get("OPENRIG_PRODUCT_REPO")
PRODUCT = Path(_PRODUCT_ENV).expanduser().resolve() if _PRODUCT_ENV else None
DRIVERS = PRODUCT / "packages" / "daemon" / "test" / "s9-drivers" if PRODUCT else None
NODE = shutil.which("node")
NPX = shutil.which("npx")

needs_product = pytest.mark.skipif(
    PRODUCT is None or NODE is None or NPX is None or DRIVERS is None or not DRIVERS.is_dir(),
    reason="OPENRIG_PRODUCT_REPO must point at a product checkout with node/npx and "
    "packages/daemon/test/s9-drivers; explicit env is required instead of a machine-local default",
)


def test_product_repo_is_explicit_or_none():
    """Guard the portability contract: no implicit home-directory fallback."""
    if PRODUCT is None:
        assert not _PRODUCT_ENV
    else:
        assert PRODUCT == Path(os.environ["OPENRIG_PRODUCT_REPO"]).expanduser().resolve()


FIXTURE_DOCTOR = '''#!/usr/bin/env python3
import sys
if sys.argv[1:2] != ["doctor"]:
    sys.exit(2)
print("PASS fixture doctor (pytest)")
sys.exit(0)
'''


def _sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_run(tmp_path: Path, run_id: str = "t-run") -> tuple[Path, Path]:
    """A minimal valid run bundle: bridge + matching render manifest + fixture doctor."""
    run = tmp_path / "runs" / run_id
    openrig = run / "openrig"
    (openrig / "tools").mkdir(parents=True)
    home = tmp_path / "home"
    home.mkdir()
    (openrig / "rig.yaml").write_text("rig: t\n", encoding="utf-8")
    (openrig / "workflow.yaml").write_text("workflow: t\n", encoding="utf-8")
    files = {
        rel: {"bytes": len((openrig / rel).read_bytes()), "sha256": _sha(openrig / rel)}
        for rel in ("rig.yaml", "workflow.yaml")
    }
    (openrig / "render-manifest.json").write_text(
        json.dumps({"schemaVersion": 1, "runId": run_id, "files": files}), encoding="utf-8"
    )
    (openrig / "tools" / "openrig_bridge.py").write_text(FIXTURE_DOCTOR, encoding="utf-8")
    bridge = {
        "schemaVersion": 2,
        "runId": run_id,
        "rigName": "t-rig",
        "workflowId": "t-workflow",
        "rigSpec": "rig.yaml",
        "workflowSpec": "workflow.yaml",
        "openrigCli": "rig",
        "openrigHome": str(home),
        "projectRoot": str(tmp_path / "project-root"),
        "daemonPort": 12399,
        "seatMap": {"main": "main@t", "tdo": "tdo@t"},
        "bundleDir": "openrig",
    }
    (openrig / "OPENRIG-BRIDGE.json").write_text(json.dumps(bridge), encoding="utf-8")
    return run, home


def launch(home: Path) -> dict:
    return json.loads((home / "entry" / "launch.json").read_text(encoding="utf-8"))


def driver(*args: str, timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(NPX), "tsx", *args],
        cwd=str(PRODUCT),
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, "OPENRIG_ENTRY_GUARD": "", "OPENRIG_ALLOW_DIRECT": ""},
    )


def last_json(text: str) -> dict:
    lines = [line for line in text.strip().splitlines() if line.strip()]
    assert lines, f"driver produced no output: {text!r}"
    return json.loads(lines[-1])


# ---------------------------------------------------------------- W-S8-14 (dry run)
def test_dry_run_closes_its_ticket(tmp_path):
    run, home = make_run(tmp_path)
    report = orr.run_start(run, dry_run=True)

    assert report["dryRun"] is True
    assert report["ok"] is True
    assert report["rc"] == 0
    assert report["provenance"]["phase"] == "closed"

    record = launch(home)
    assert record["phase"] == "closed"
    assert record["dryRun"] is True
    assert record["closureReason"] == "dry-run: no live action"
    assert record["consumed"] == []
    # No temp file left behind by the atomic writes.
    assert not list((home / "entry").glob("*.tmp"))


def test_dry_run_marks_dryrun_at_write_time(tmp_path):
    """A crash before the close still leaves a record the guard refuses."""
    run, home = make_run(tmp_path)
    bridge, err = orr._load_bridge(run)
    assert err is None

    launch_id = orr.write_entry_records(run, bridge, dry_run=True)
    record = launch(home)
    assert record["launchId"] == launch_id
    assert record["phase"] == "starting"
    assert record["dryRun"] is True


def test_dry_run_close_failure_is_rc2_not_a_silent_success(tmp_path, monkeypatch):
    run, home = make_run(tmp_path)
    monkeypatch.setattr(orr, "close_entry_records", lambda *a, **k: False)

    report = orr.run_start(run, dry_run=True)

    assert report["ok"] is False
    assert report["rc"] == 2
    assert report["error"]["code"] == "entry_guard_close_failed"
    assert report["provenance"]["phase"] == "starting"
    # The ticket is still live on disk — the report must say so rather than pretend.
    assert launch(home)["phase"] == "starting"


def test_non_dry_run_still_activates(tmp_path):
    """Regression: closing is a dry-run property, not a change to a real start."""
    run, home = make_run(tmp_path)
    fake = tmp_path / "fake-rig"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "args = sys.argv[1:]\n"
        "if args[:2] == ['ps', '--nodes']:\n"
        "    print(json.dumps({'nodes': [{'canonicalSessionName': s, 'startupStatus': 'ready'} "
        "for s in ['main@t', 'tdo@t']]}))\n"
        "elif args[:1] == ['workflow']:\n"
        "    print(json.dumps({'ok': True}))\n"
        "else:\n"
        "    print(json.dumps({'ok': True}))\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    bridge_path = run / "openrig" / "OPENRIG-BRIDGE.json"
    bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
    bridge["openrigCli"] = str(fake)
    bridge_path.write_text(json.dumps(bridge), encoding="utf-8")

    report = orr.run_start(run, dry_run=False, timeout=5)

    assert report["ok"] is True, report
    assert launch(home)["phase"] == "active"
    assert launch(home)["dryRun"] is False


def test_cli_dry_run_reports_closed_and_rc0(tmp_path, capsys):
    run, home = make_run(tmp_path)
    rc = orr.main(["start", "--run-dir", str(run), "--dry-run", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["rc"] == 0
    assert payload["provenance"]["phase"] == "closed"
    assert launch(home)["phase"] == "closed"


# ------------------------------------------------------- fixture run-dir resolution
def test_fixture_name_resolves_under_fixture_root(tmp_path, monkeypatch):
    root = tmp_path / "fixtures"
    (root / "FI-99").mkdir(parents=True)
    monkeypatch.setenv(orr.FIXTURE_ROOT_ENV, str(root))
    assert orr.resolve_fixture_run_dir(Path("FI-99")) == root / "FI-99"


def test_fixture_resolution_leaves_real_paths_alone(tmp_path, monkeypatch):
    root = tmp_path / "fixtures"
    root.mkdir()
    monkeypatch.setenv(orr.FIXTURE_ROOT_ENV, str(root))
    # An absolute or existing path is never rewritten, and a non-fixture name is not magic.
    assert orr.resolve_fixture_run_dir(tmp_path / "runs" / "real") == tmp_path / "runs" / "real"
    assert orr.resolve_fixture_run_dir(Path("openrig-workflow-x")) == Path("openrig-workflow-x")
    assert orr.resolve_fixture_run_dir(Path("FI-99")) == Path("FI-99")


def test_s9r01_unset_fixture_root_has_no_shared_default(monkeypatch):
    """S9-R-01: an unset env must NOT fall back to a shared /tmp root (the W-S8-12 shape)."""
    monkeypatch.delenv(orr.FIXTURE_ROOT_ENV, raising=False)
    assert orr.fixture_root() is None
    assert orr.resolve_fixture_run_dir(Path("FI-99")) == Path("FI-99")


def test_missing_fixture_run_dir_names_the_provisioning_command(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv(orr.FIXTURE_ROOT_ENV, str(tmp_path / "fixtures"))
    rc = orr.main(["start", "--run-dir", "FI-77", "--dry-run", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert payload["error"] == "run dir missing"
    assert "provision-fixtures.ts" in payload["hint"]
    assert orr.FIXTURE_ROOT_ENV in payload["hint"], "the hint must name the env that is missing"


def test_missing_fixture_with_unset_env_still_names_the_export(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv(orr.FIXTURE_ROOT_ENV, raising=False)
    rc = orr.main(["resume", "--run-dir", "FI-77", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert "unset" in payload["hint"]


# ------------------------------------------------- cross-boundary: real rc from drivers
@needs_product
def test_guard_refuses_the_dry_run_ticket(tmp_path):
    """AT-S9-ENT-03 then AT-S9-ENT-04, on one home, with the real exit codes."""
    run, home = make_run(tmp_path)

    dry = orr.run_start(run, dry_run=True)
    assert dry["rc"] == 0

    result = driver(
        str(DRIVERS / "entry-guard-driver.ts"),
        "--home",
        str(home),
        "--verb",
        "daemon-start",
        "--json",
    )
    payload = last_json(result.stdout)
    assert result.returncode == 2, result.stderr
    assert payload["code"] == "entry_guard_closed"
    assert payload["allow"] is False
    assert payload["fixtureSeeded"] is False


@needs_product
def test_launch_writer_and_product_guard_agree_on_repeatable_workflow_continuation(tmp_path):
    """S1-2 cross-boundary proof: openrig_run writes the ticket, the real guard reads it.

    A managed seat must be able to call `rig workflow project` more than once under one
    live launch. This is not a restatement of the writer constant: the launched record is
    fed to the product's `checkEntry` three times, and the startup ledger must stay empty.
    """
    run, home = make_run(tmp_path)
    bridge, err = orr._load_bridge(run)
    assert err is None
    launch_id = orr.write_entry_records(run, bridge)

    record = launch(home)
    assert set(record["verbs"]) == set(orr.ENTRY_VERBS)
    assert set(orr.CONTINUATION_ENTRY_VERBS) <= set(record["verbs"])
    assert set(record["verbs"]) - set(orr.STARTUP_ENTRY_VERBS) == set(orr.CONTINUATION_ENTRY_VERBS)

    module_url = (PRODUCT / "packages" / "daemon" / "src" / "entry-guard.ts").as_uri()
    script_path = tmp_path / "check-continuation.ts"
    script_path.write_text(
        f"""
import {{ checkEntry, readConsumedLedger, readLaunchRecord }} from {json.dumps(module_url)};
const home = {json.dumps(str(home))};
const launchId = {json.dumps(launch_id)};
const env = {{ OPENRIG_ENTRY_LAUNCH_ID: launchId }};
const argv = ["workflow", "project", "--instance", "t-workflow", "--current-packet", "q-1"];
const first = checkEntry({{ argv, home, env }});
const second = checkEntry({{ argv, home, env }});
const third = checkEntry({{ argv, home, env }});
const record = readLaunchRecord(home).record;
process.stdout.write(JSON.stringify({{
  first,
  second,
  third,
  ledger: [...readConsumedLedger(home, launchId)],
  consumed: record?.consumed ?? null,
}}) + "\\n");
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        [str(NPX), "tsx", str(script_path)],
        cwd=str(PRODUCT),
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "OPENRIG_ENTRY_GUARD": "", "OPENRIG_ALLOW_DIRECT": ""},
    )
    payload = last_json(result.stdout)
    assert result.returncode == 0, result.stderr
    for key in ("first", "second", "third"):
        assert payload[key]["allow"] is True, payload
        assert payload[key]["verb"] == "workflow-project"
    assert payload["ledger"] == []
    assert payload["consumed"] == []


@needs_product
def test_atomic_token_driver_cases():
    concurrency = driver(
        str(DRIVERS / "atomic-token-driver.ts"),
        "--concurrency",
        "12",
        "--fixture",
        "FI-01",
        "--json",
    )
    payload = last_json(concurrency.stdout)
    assert concurrency.returncode == 0, concurrency.stderr
    assert payload["allowed"] == 1
    assert payload["refused"] == 11
    assert payload["refusalCodes"] == ["entry_guard_verb_consumed"]

    write_failure = driver(
        str(DRIVERS / "atomic-token-driver.ts"),
        "--case",
        "ledger-write-failure",
        "--fixture",
        "FI-01b",
        "--json",
    )
    failure = last_json(write_failure.stdout)
    assert write_failure.returncode == 2, write_failure.stderr
    assert failure["code"] == "entry_guard_token_write_failed"


@needs_product
def test_atomic_token_mutation_control_flips():
    """AT-S9-ENT-08: without the claim ledger the same race lets everyone in."""
    result = driver(
        str(DRIVERS / "atomic-token-driver.ts"),
        "--concurrency",
        "12",
        "--fixture",
        "FI-01",
        "--mutation",
        "no-ledger",
        "--json",
    )
    payload = last_json(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["pass"] is True
    assert payload["allowed"] > 1


@needs_product
def test_http_admission_driver_cases():
    deny = driver(
        str(DRIVERS / "http-admission-driver.ts"),
        "--fixture",
        "FI-03",
        "--route",
        "lifecycle-mutation",
        "--json",
    )
    denied = last_json(deny.stdout)
    assert deny.returncode == 2, deny.stderr
    assert denied["status"] == 403
    assert denied["body"]["error"]["code"] == "entry_guard_http_denied"
    assert denied["innerCalls"] == 0

    allow = driver(
        str(DRIVERS / "http-admission-driver.ts"),
        "--fixture",
        "FI-03",
        "--route",
        "read-only",
        "--json",
    )
    allowed = last_json(allow.stdout)
    assert allow.returncode == 0, allow.stderr
    assert allowed["status"] == 200
    assert allowed["innerCalls"] == 1


@needs_product
def test_json_denial_driver_and_its_mutation(tmp_path):
    run, home = make_run(tmp_path)
    assert orr.run_start(run, dry_run=True)["rc"] == 0

    denied = driver(
        str(DRIVERS / "json-denial-driver.ts"),
        "--fixture",
        str(home),
    )
    assert denied.returncode == 0, denied.stderr
    payload = json.loads(denied.stdout.strip())
    assert payload["ok"] is False
    assert payload["error"]["code"] == "entry_guard_closed"
    assert payload["error"]["hint"]

    mutation = driver(
        str(DRIVERS / "json-denial-driver.ts"),
        "--fixture",
        str(home),
        "--mutation",
        "human-text",
    )
    assert mutation.returncode == 0, mutation.stderr
    with pytest.raises(json.JSONDecodeError):
        json.loads(mutation.stdout)
