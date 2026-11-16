# -*- coding: utf-8 -*-
"""WS-3 回归用例（R2）· P5 遗留 S-1/S-2/S-3（tdo-b1 独占，R2）。

- **S-1**（R1 已落地，本文件只做轻量回归，防回退）：`append-status --also` 对
  `.gitignore` 命中路径跳过 + 告警，整条提交仍成功（重跑 R1 的 F9 事故口径）。
- **S-2**：`wf.py delegate`/`squad` 的长 send 期间按 `heartbeat_sec` 打印心跳行。
- **S-3**：`new-run`/`new-round` 依 WS 数预填 per-WS 交接小节（模板增补向后兼容）。

隔离保证：全部走 conftest 的临时 git 仓库 + 临时 runs/，不写真实 `runs/`，不联网。
先红后绿证据：把 `scripts/wf.py` + `templates/STATUS-Round-n.md` 暂回 HEAD（未含 S-2/S-3）
  → 本文件相关用例失败（红）；恢复后全绿。命令与输出见 `reports/final.md`。
"""

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import wf  # noqa: E402  （conftest 已注入 scripts/，此处兜底）


# ================================================================ S-3 交接槽
def test_fill_handoff_slots_replaces_between_markers():
    text = (
        "## 交接给 QA\n\n"
        "<!-- wf:handoff-ws:start -->\n  - **WS-1**：\n<!-- wf:handoff-ws:end -->\n"
    )
    out = wf.fill_handoff_slots(text, 3)
    assert "- **WS-1**：" in out
    assert "- **WS-2**：" in out
    assert "- **WS-3**：" in out
    assert "- **WS-4**" not in out
    # 标记保留（幂等可重填），且只有一组 WS 行
    assert out.count("- **WS-1**：") == 1
    assert "<!-- wf:handoff-ws:start -->" in out


def test_fill_handoff_slots_backward_compatible_without_marker():
    text = "## 交接给 QA\n\n- **完成定义对照**：\n  - WS-1：\n"
    assert wf.fill_handoff_slots(text, 2) == text  # 旧模板原样返回，不报错


def test_fill_handoff_slots_min_one():
    text = "<!-- wf:handoff-ws:start -->\n<!-- wf:handoff-ws:end -->"
    out = wf.fill_handoff_slots(text, 0)
    assert "- **WS-1**：" in out and "- **WS-2**" not in out


def test_new_run_prefills_per_ws_handoff_slots(new_run):
    """S-3 判据：new-run（tdo=3）在 STATUS-Round-1 预填 WS-1..WS-3 交接小节。"""
    rd = new_run(run_id="t-s3", tdo=3)
    text = (rd / "STATUS-Round-1.md").read_text(encoding="utf-8")
    for i in (1, 2, 3):
        assert f"- **WS-{i}**：" in text
    assert "- **WS-4**" not in text


def test_new_run_default_tdo_slots(new_run):
    rd = new_run(run_id="t-s3b")  # 夹具默认 tdo=2
    text = (rd / "STATUS-Round-1.md").read_text(encoding="utf-8")
    assert "- **WS-1**：" in text and "- **WS-2**：" in text
    assert "- **WS-3**" not in text


def test_new_run_supports_template_without_slot(tmp_path, wf_env, new_run):
    """向后兼容：自定义模板无交接槽标记时 new-run 不报错、原样保留。"""
    tpl = tmp_path / "tpl"
    shutil.copytree(str(wf.TEMPLATES), str(tpl))
    st = tpl / "STATUS-Round-n.md"
    st.write_text(
        st.read_text(encoding="utf-8")
        .replace("<!-- wf:handoff-ws:start -->\n", "")
        .replace("<!-- wf:handoff-ws:end -->\n", ""),
        encoding="utf-8",
    )
    rd = new_run(run_id="t-s3c", template=str(tpl))
    assert (rd / "STATUS-Round-1.md").exists()


def test_new_round_backfills_slots_from_prior_status(new_run):
    """new-round 依既有 STATUS 里的 WS 数回填交接槽（历史 WS-3 → 第二轮 3 槽）。"""
    import argparse

    rd = new_run(run_id="t-s3d", tdo=1)
    st1 = rd / "STATUS-Round-1.md"
    st1.write_text(
        st1.read_text(encoding="utf-8").replace(
            "<!-- wf:progress:end -->",
            "| 2026-10-14 00:00 | tdo | WS-3 | x | y | 完成 |\n<!-- wf:progress:end -->",
        ),
        encoding="utf-8",
    )
    wf.cmd_new_round(argparse.Namespace(run_id="t-s3d"))
    text = (rd / "STATUS-Round-2.md").read_text(encoding="utf-8")
    assert "- **WS-3**：" in text


def test_new_run_then_doctor_passes(new_run):
    """S-3 冒烟：new-run + doctor PASS（预填未引入占位符/结构错误）。"""
    new_run(run_id="t-s3e", tdo=2)
    assert wf.doctor("t-s3e") == 0


# ================================================================ S-2 心跳
def _fake_api_factory(sleep_sec=0.25, session_id="sid-hb", exc=None):
    """返回假 wf.api：建 session 立即回，message 慢响应后回。"""
    calls = {"message": 0}

    def fake_api(base, method, path, body=None, timeout=120):
        if path == "/session":
            return {"id": session_id}
        if path.endswith("/message"):
            calls["message"] += 1
            if exc is not None:
                raise exc
            time.sleep(sleep_sec)
            return {
                "info": {"cost": 0.0, "tokens": {"total": 1}},
                "parts": [{"type": "text", "text": "ok"}],
            }
        return {}

    fake_api.calls = calls
    return fake_api


def test_run_one_delegation_emits_heartbeat_on_slow_send(new_run, monkeypatch, capsys):
    """S-2 判据：单条 send 慢响应期间出现心跳行（此前仅返回时记账）。"""
    new_run(run_id="t-s2")
    monkeypatch.setattr(
        wf, "api", _fake_api_factory(sleep_sec=0.3, session_id="sid-hb")
    )
    res = wf.run_one_delegation(
        "t-s2",
        "tdo",
        "tdo-a1",
        "WS-1",
        "deepseek/deepseek-flash",
        "minimal",
        "http://127.0.0.1:1",
        30,
        heartbeat=0.05,
    )
    out = capsys.readouterr().out
    assert "[HEARTBEAT]" in out
    assert "sid-hb" in out
    assert "已等待" in out
    assert res["sid"] == "sid-hb" and res["text"] == "ok"


def test_run_one_delegation_fast_send_no_heartbeat(new_run, monkeypatch, capsys):
    new_run(run_id="t-s2b")
    monkeypatch.setattr(wf, "api", _fake_api_factory(sleep_sec=0.0))
    wf.run_one_delegation(
        "t-s2b",
        "tdo",
        "tdo-a1",
        "WS-1",
        "deepseek/deepseek-flash",
        "minimal",
        "http://127.0.0.1:1",
        30,
        heartbeat=0.05,
    )
    assert "[HEARTBEAT]" not in capsys.readouterr().out


def test_run_one_delegation_error_propagates(new_run, monkeypatch):
    """心跳封装不得吞掉 API 错误：die() 的 SystemExit 应在主线程抛回。"""
    new_run(run_id="t-s2c")
    monkeypatch.setattr(wf, "api", _fake_api_factory(exc=SystemExit(1)))
    with pytest.raises(SystemExit):
        wf.run_one_delegation(
            "t-s2c",
            "tdo",
            "tdo-a1",
            "WS-1",
            "deepseek/deepseek-flash",
            "minimal",
            "http://127.0.0.1:1",
            30,
            heartbeat=0.05,
        )


def test_delegate_cmd_passes_heartbeat_arg(new_run, monkeypatch, capsys):
    """cmd_delegate 端到端：给 --heartbeat 后慢 send 打心跳、归档回执。"""
    import argparse

    rd = new_run(run_id="t-s2d")
    wf.write_header_field(rd / "PROJECT.md", "state", "plan-ready")
    monkeypatch.setattr(wf, "api", _fake_api_factory(sleep_sec=0.3, session_id="sid-d"))
    # 不起真实 opencode 服务：CI runner 没有 opencode CLI
    monkeypatch.setattr(wf, "_resolve_base", lambda server, port: "http://127.0.0.1:1")
    args = argparse.Namespace(
        run_id="t-s2d",
        role="tdo",
        name="tdo-a1",
        ws="WS-1",
        model="deepseek/deepseek-flash",
        oc_agent="minimal",
        backend="v1-http",
        server="",
        port=0,
        timeout=30,
        heartbeat=0.05,
        dry_run=False,
        force=False,
    )
    wf.cmd_delegate(args)
    out = capsys.readouterr().out
    assert "[HEARTBEAT]" in out
    assert "委派完成" in out
    assert (rd / "delegations").exists()


def test_squad_emits_heartbeat(new_run, monkeypatch, capsys):
    """squad 扇出：每个执行体的慢 send 都可见心跳行。"""
    import argparse

    rd = new_run(run_id="t-s2e")
    wf.write_header_field(rd / "PROJECT.md", "state", "plan-ready")
    monkeypatch.setattr(
        wf, "api", _fake_api_factory(sleep_sec=0.3, session_id="sid-sq")
    )
    monkeypatch.setattr(wf, "_resolve_base", lambda server, port: "http://127.0.0.1:1")
    monkeypatch.setattr(
        wf, "_log_delegation", lambda *a, **k: Path("/tmp/opencode/receipt.md")
    )
    args = argparse.Namespace(
        run_id="t-s2e",
        role="tdo",
        agents="tdo-a1:WS-1,tdo-a2:WS-2",
        model="deepseek/deepseek-flash",
        oc_agent="minimal",
        backend="v1-http",
        server="",
        port=0,
        timeout=30,
        heartbeat=0.05,
        jobs=2,
        dry_run=False,
        force=False,
    )
    wf.cmd_squad(args)
    out = capsys.readouterr().out
    assert out.count("[HEARTBEAT]") >= 2  # 两个并发 send 各自心跳
    assert "squad 汇总" in out


# ================================================================ S-1 回归
def test_s1_gitignore_filter_still_applies(new_run):
    """S-1 防回退：git_commit 跳过 gitignore 命中路径，其余照常提交。"""
    rd = new_run(run_id="t-s1")
    ignored = rd / "noise.log"
    ignored.write_text("噪声\n", encoding="utf-8")
    tracked = rd / "note.md"
    tracked.write_text("入库\n", encoding="utf-8")
    # 用新提交确保工作区有变更可提交
    (rd / "STATUS-Round-1.md").write_text(
        (rd / "STATUS-Round-1.md").read_text(encoding="utf-8") + "\n<!-- s1 -->\n",
        encoding="utf-8",
    )
    ok, info = wf.git_commit([rd / "STATUS-Round-1.md", ignored, tracked], "t: s1")
    assert ok, info
    shown = subprocess.run(
        ["git", "-C", str(wf.REPO), "show", "--name-only", "--pretty=format:", "HEAD"],
        capture_output=True,
        text=True,
    ).stdout
    assert "note.md" in shown and "noise.log" not in shown
