# -*- coding: utf-8 -*-
"""Packet A · R05 `openrig_preflight.py` 真检查单测（含负向）。

覆盖 TASK §2.5：
  - 无 --workspace/--run-id → ok:false, rc=1
  - --advisory → ok:false, rc=0
  - 有 workspace 但无 managed block → fail
  - 注入后块存在 + run 目录齐全 → ok:true, rc=0
  - 缺 run docs → fail
"""

import json
import shutil
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import openrig_preflight as pf  # noqa: E402

REAL_ROOT = Path(__file__).resolve().parents[1]
REAL_TEMPLATES = REAL_ROOT / "templates"


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """把 preflight 的 ROOT 指到临时 workflow-group（模板用符号链接保持真实）。"""
    wg = tmp_path / "workflow-group"
    wg.mkdir()
    (wg / "templates").symlink_to(REAL_TEMPLATES, target_is_directory=True)
    (wg / "runs").mkdir()
    monkeypatch.setattr(pf, "ROOT", wg)
    monkeypatch.setattr(pf, "PREFLIGHT", REAL_TEMPLATES / "specialized" / "openrig-workflow-master" / "PREFLIGHT.md")
    monkeypatch.setattr(pf, "TARGET_FILE", tmp_path / "target.json")
    monkeypatch.setattr(pf, "MONITOR_URL", "http://127.0.0.1:0")
    return wg


def _make_run(wg: Path, run_id: str = "t-run") -> Path:
    rd = wg / "runs" / run_id
    rd.mkdir(parents=True)
    (rd / "PROJECT.md").write_text("# PROJECT\n", encoding="utf-8")
    (rd / "DECISIONS.md").write_text("# DECISIONS\n", encoding="utf-8")
    shutil.copyfile(REAL_TEMPLATES / "ISSUES.xlsx", rd / "ISSUES.xlsx")
    (rd / "STATUS-Round-1.md").write_text("# STATUS\n", encoding="utf-8")
    return rd


def _run(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["openrig_preflight.py", *argv])
    return pf.main()


def _payload(capsys):
    return json.loads(capsys.readouterr().out)


def test_no_context_fails_closed(sandbox, monkeypatch, capsys):
    rc = _run(monkeypatch, "--json")
    payload = _payload(capsys)
    assert rc == 1
    assert payload["ok"] is False
    checks = {c["id"]: c for c in payload["checks"]}
    assert checks["workspace_context"]["ok"] is False
    assert checks["run_context"]["ok"] is False
    assert payload["reasons"]


def test_advisory_keeps_rc0_but_not_ok(sandbox, monkeypatch, capsys):
    rc = _run(monkeypatch, "--json", "--advisory")
    payload = _payload(capsys)
    assert rc == 0
    assert payload["ok"] is False
    assert payload["advisory"] is True


def test_workspace_without_managed_block_fails(sandbox):
    """注入是补救，不能替代检查：块缺失时 check 必须 fail。"""
    ws = sandbox / "seat-ws"
    ws.mkdir()
    (ws / "AGENTS.md").write_text("# AGENTS\n\n没有 preflight 块\n", encoding="utf-8")
    chk = pf.check_workspace_context(str(ws), "t-run")
    assert chk["ok"] is False
    assert "managed block" in chk["detail"]


def test_injection_then_all_checks_ok(sandbox, monkeypatch, capsys):
    _make_run(sandbox)
    ws = sandbox / "seat-ws"
    ws.mkdir()
    rc = _run(monkeypatch, "--json", "--no-monitor", "--workspace", str(ws), "--run-id", "t-run")
    payload = _payload(capsys)
    checks = {c["id"]: c for c in payload["checks"]}
    assert rc == 0 and payload["ok"] is True, payload["reasons"]
    assert all(c["ok"] for c in payload["checks"])
    assert checks["workspace_context"]["ok"] is True
    text = (ws / "AGENTS.md").read_text(encoding="utf-8")
    assert "BEGIN OPENRIG-PREFLIGHT" in text and "t-run" in text


def test_missing_run_docs_fails(sandbox, monkeypatch, capsys):
    """W2：run_docs 属 pre-check；失败时不得注入 AGENTS.md。"""
    rd = _make_run(sandbox)
    (rd / "DECISIONS.md").unlink()
    ws = sandbox / "seat-ws"
    ws.mkdir()
    rc = _run(monkeypatch, "--json", "--no-monitor", "--workspace", str(ws), "--run-id", "t-run")
    payload = _payload(capsys)
    checks = {c["id"]: c for c in payload["checks"]}
    assert rc == 1 and payload["ok"] is False
    assert checks["run_docs"]["ok"] is False
    assert "DECISIONS.md" in checks["run_docs"]["detail"]
    # pre-check 失败 → workspace 校验未执行，且零写入
    assert checks["workspace_context"]["ok"] is False
    assert checks["workspace_context"]["skipped"] is True
    assert not (ws / "AGENTS.md").exists()
    assert payload["injectedAgents"] is None
    assert payload["monitor"] is None
    assert payload["precheck"]["ok"] is False
    assert "run_docs" in payload["precheck"]["failed"]


def test_invalid_run_id_leaves_no_side_effects(sandbox, monkeypatch, capsys):
    """W2 负向：不存在的 run-id → rc1，AGENTS.md 字节不变，target.json 不写，不查服务。"""
    ws = sandbox / "seat-ws"
    ws.mkdir()
    agents = ws / "AGENTS.md"
    original = "# AGENTS\n\n用户手写内容，不得被注入改动\n"
    agents.write_text(original, encoding="utf-8")
    before = agents.read_bytes()

    calls: list[str] = []

    def _boom(*a, **kw):  # 任何 subprocess 调用都说明 pre-check 之后仍走了副作用路径
        calls.append("subprocess")
        raise AssertionError(f"pre-check 失败时不得调用 subprocess: {a}")

    monkeypatch.setattr(pf.subprocess, "run", _boom)

    target = pf.TARGET_FILE
    rc = _run(
        monkeypatch,
        "--json",
        "--workspace",
        str(ws),
        "--run-id",
        "no-such-run-xyz",
    )
    payload = _payload(capsys)
    checks = {c["id"]: c for c in payload["checks"]}

    assert rc == 1 and payload["ok"] is False
    assert checks["run_context"]["ok"] is False
    assert agents.read_bytes() == before
    assert not target.exists()
    assert payload["injectedAgents"] is None and payload["monitor"] is None
    assert calls == []


def test_injection_happens_after_precheck(sandbox, monkeypatch, capsys):
    """W2 正例：只有 pre-check 全过才注入 + 注册 monitor。"""
    _make_run(sandbox)
    ws = sandbox / "seat-ws"
    ws.mkdir()
    fired: list[str] = []

    real_inject = pf.inject_agents
    real_monitor = pf.register_monitor

    def spy_inject(*a, **kw):
        fired.append("inject")
        return real_inject(*a, **kw)

    def spy_monitor(*a, **kw):
        fired.append("monitor")
        return {"ok": True, "spy": True}

    monkeypatch.setattr(pf, "inject_agents", spy_inject)
    monkeypatch.setattr(pf, "register_monitor", spy_monitor)

    rc = _run(monkeypatch, "--json", "--workspace", str(ws), "--run-id", "t-run")
    payload = _payload(capsys)
    assert rc == 0 and payload["ok"] is True, payload["reasons"]
    assert payload["precheck"]["ok"] is True
    assert fired == ["inject", "monitor"]
    assert payload["monitor"] == {"ok": True, "spy": True}
