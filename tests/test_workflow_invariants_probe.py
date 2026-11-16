# -*- coding: utf-8 -*-
"""Packet P1 · R13 `workflow_invariants_probe.py` 单测（含负向）。

覆盖 TASK §1 / plan §2 P1：
  - 合法 DAG → ok True，terminal 正确，unreachable 空；
  - 重复 step id / depends_on 缺目标 / next_hop.failed 缺目标 → ok False 且 rc=1；
  - unreachable 只进 WARN，不影响 ok；
  - 默认路径缺失 → rc=2；--workflow 覆盖生效；
  - 没有 live 调用：subprocess.run / subprocess.Popen 被换成爆炸桩，调用计数必须为 0。
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import workflow_invariants_probe as probe  # noqa: E402

VALID = """\
workflow:
  id: t
  steps:
  - id: plan
    actor_role: main
    objective: write the plan
    allowed_exits:
    - handoff
  - id: impl
    actor_role: tdo
    objective: build it
    depends_on:
    - plan
  - id: qa
    actor_role: qa
    depends_on:
    - impl
    next_hop:
      'on':
        failed: impl
  - id: close_round
    actor_role: main
    depends_on:
    - qa
  invariants:
    continuation_required: true
"""


def _write(tmp_path: Path, text: str, *, at: Path | None = None) -> Path:
    target = at or (tmp_path / "runs" / "t-run" / "openrig" / "workflow.yaml")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def _run_dir(tmp_path: Path) -> Path:
    run = tmp_path / "runs" / "t-run"
    (run / "openrig").mkdir(parents=True, exist_ok=True)
    return run


def test_valid_dag_is_ok(tmp_path):
    _write(tmp_path, VALID)
    report = probe.probe(_run_dir(tmp_path))
    assert report["ok"] is True
    assert report["rc"] == 0
    assert report["terminal"] == ["close_round"]
    assert report["unreachable"] == []
    assert report["duplicateIds"] == []
    assert report["missingDependsOn"] == []
    assert report["missingNextHopTargets"] == []
    assert report["problems"] == []
    assert [s["id"] for s in report["steps"]] == ["plan", "impl", "qa", "close_round"]
    assert report["steps"][1]["dependsOn"] == ["plan"]
    assert report["steps"][2]["nextHopFailed"] == "impl"


def test_flow_style_depends_on_is_parsed(tmp_path):
    _write(
        tmp_path,
        "workflow:\n  steps:\n  - id: a\n  - id: b\n    depends_on: [a]\n",
    )
    report = probe.probe(_run_dir(tmp_path))
    assert report["steps"][1]["dependsOn"] == ["a"]
    assert report["ok"] is True


def test_duplicate_id_fails(tmp_path):
    text = VALID.replace("- id: qa", "- id: impl")
    _write(tmp_path, text)
    report = probe.probe(_run_dir(tmp_path))
    assert report["ok"] is False and report["rc"] == 1
    assert report["duplicateIds"] == ["impl"]
    assert any(p.startswith("duplicate_id:") for p in report["problems"])


def test_missing_depends_on_target_fails(tmp_path):
    text = VALID.replace("    - plan\n", "    - ghost_step\n")
    _write(tmp_path, text)
    report = probe.probe(_run_dir(tmp_path))
    assert report["ok"] is False and report["rc"] == 1
    assert report["missingDependsOn"] == ["ghost_step"]
    assert "missing_depends_on:impl->ghost_step" in report["problems"]


def test_missing_next_hop_target_fails(tmp_path):
    text = VALID.replace("failed: impl", "failed: nowhere")
    _write(tmp_path, text)
    report = probe.probe(_run_dir(tmp_path))
    assert report["ok"] is False and report["rc"] == 1
    assert report["missingNextHopTargets"] == ["nowhere"]
    assert "missing_next_hop_target:qa->nowhere" in report["problems"]


def test_unreachable_is_warn_only(tmp_path):
    orphan = (
        "  - id: orphan\n"
        "    depends_on:\n"
        "    - orphan\n"
        "    next_hop:\n"
        "      'on':\n"
        "        failed: plan\n"
    )
    # orphan depends on itself (id exists -> no missing target, ok stays true) but no
    # root reaches it; next_hop.failed keeps it out of `terminal`.
    text = VALID.replace("  invariants:", orphan + "  invariants:")
    _write(tmp_path, text)
    report = probe.probe(_run_dir(tmp_path))
    assert report["ok"] is True
    assert report["unreachable"] == ["orphan"]
    assert report["terminal"] == ["close_round"]


def test_no_steps_is_not_ok(tmp_path):
    _write(tmp_path, "workflow:\n  id: t\n  roles:\n    main: {}\n")
    report = probe.probe(_run_dir(tmp_path))
    assert report["ok"] is False
    assert "no_steps" in report["problems"]


def test_missing_workflow_is_rc2(tmp_path):
    run = _run_dir(tmp_path)
    report = probe.probe(run)
    assert report["rc"] == 2 and report["ok"] is False
    assert "workflow file missing" in report["error"]


def test_missing_run_dir_is_rc2(tmp_path):
    report = probe.probe(tmp_path / "nope")
    assert report["rc"] == 2 and report["ok"] is False
    assert "run dir missing" in report["error"]


def test_workflow_override(tmp_path):
    run = _run_dir(tmp_path)
    other = _write(tmp_path, VALID, at=tmp_path / "elsewhere" / "wf.yaml")
    report = probe.probe(run, other)
    assert report["rc"] == 0 and report["ok"] is True
    assert report["workflow"] == str(other)


def test_cli_json_and_rc(tmp_path, capsys):
    _write(tmp_path, VALID)
    rc = probe.main(["--run-dir", str(_run_dir(tmp_path)), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0 and payload["ok"] is True and payload["terminal"] == ["close_round"]

    broken = VALID.replace("failed: impl", "failed: nowhere")
    _write(tmp_path, broken)
    rc = probe.main(["--run-dir", str(_run_dir(tmp_path)), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1 and payload["ok"] is False


def test_probe_makes_no_live_calls(tmp_path, monkeypatch):
    _write(tmp_path, VALID)
    calls = {"run": 0, "popen": 0}

    def boom_run(*args, **kwargs):  # pragma: no cover - must never fire
        calls["run"] += 1
        raise AssertionError("probe must not call subprocess.run")

    def boom_popen(*args, **kwargs):  # pragma: no cover - must never fire
        calls["popen"] += 1
        raise AssertionError("probe must not call subprocess.Popen")

    monkeypatch.setattr(subprocess, "run", boom_run)
    monkeypatch.setattr(subprocess, "Popen", boom_popen)

    run = _run_dir(tmp_path)
    report = probe.probe(run)
    assert report["ok"] is True
    rc = probe.main(["--run-dir", str(run), "--json"])
    assert rc == 0
    assert calls == {"run": 0, "popen": 0}
