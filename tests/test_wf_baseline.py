# -*- coding: utf-8 -*-
"""Packet B · R02 `wf.py baseline / verify-baseline` 单测（含负向）。

覆盖 TASK §3.4：
  - 临时 git 仓库 + 临时 run；baseline→verify=0
  - 改一个文件 → verify=1，打印结构化 diff
  - 本 run 目录内新增文件不触发 verify 失败（排除生效）
  - 旧 run 无 .run-meta.json 时允许 --project-root
"""

import argparse
import json
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
import sys

if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import wf  # noqa: E402


def _make_run(wf_env, run_id="t-base", with_meta=True):
    rd = wf_env.runs / run_id
    (rd / "reports" / "evidence").mkdir(parents=True, exist_ok=True)
    if with_meta:
        (rd / ".run-meta.json").write_text(
            json.dumps(
                {
                    "runId": run_id,
                    "projectRoot": str(wf_env.repo),
                    "scope": "workflow-group/**",
                    "template": "",
                    "createdAt": "2026-11-16T00:00:00+08:00",
                }
            ),
            encoding="utf-8",
        )
    return rd


def _baseline(project_root="", run_id="t-base"):
    return wf.cmd_baseline(
        argparse.Namespace(run_id=run_id, project_root=project_root, json=True)
    )


def _verify(run_id="t-base"):
    return wf.cmd_verify_baseline(argparse.Namespace(run_id=run_id, json=True))


def _json(capsys):
    return json.loads(capsys.readouterr().out)


def test_baseline_then_verify_is_zero(wf_env, capsys):
    rd = _make_run(wf_env)
    assert _baseline() == 0
    summary = _json(capsys)
    assert summary["ok"] is True and summary["statusCount"] >= 0
    assert Path(summary["jsonPath"]).is_file()
    assert Path(summary["txtPath"]).is_file()
    data = json.loads((rd / "reports" / "evidence" / "00-baseline.json").read_text(encoding="utf-8"))
    assert data["schemaVersion"] == 1
    assert data["excludePaths"] == ["workflow-group/runs/t-base"]
    assert set(data["toolVersions"]) == {"python", "pytest", "rig"}
    capsys.readouterr()
    assert _verify() == 0
    payload = _json(capsys)
    assert payload["ok"] is True and payload["mismatches"] == []


def test_verify_detects_modified_file(wf_env, capsys):
    _make_run(wf_env)
    _baseline()
    (wf_env.repo / "README.md").write_text("changed\n", encoding="utf-8")
    capsys.readouterr()
    assert _verify() == 1
    payload = _json(capsys)
    assert payload["ok"] is False
    fields = {m["field"] for m in payload["mismatches"]}
    assert {"statusSha256", "diffSha256"} & fields
    assert any("README.md" in line for line in payload["statusAdded"] + [])
    assert payload["diffStatCurrent"]


def test_new_file_inside_run_dir_does_not_break_baseline(wf_env, capsys):
    rd = _make_run(wf_env, run_id="t-base-noise")
    _baseline(run_id="t-base-noise")
    (rd / "reports" / "notes.md").write_text("self-noise\n", encoding="utf-8")
    (rd / "STATUS-Round-1.md").write_text("# status\n", encoding="utf-8")
    capsys.readouterr()
    assert _verify("t-base-noise") == 0
    assert _json(capsys)["ok"] is True


def test_legacy_run_accepts_explicit_project_root(wf_env, capsys):
    """已有 run 无 .run-meta.json 时必须能用 --project-root 显式传入。"""
    _make_run(wf_env, run_id="t-legacy", with_meta=False)
    assert _baseline(project_root=str(wf_env.repo), run_id="t-legacy") == 0
    capsys.readouterr()
    assert _verify("t-legacy") == 0


def test_missing_project_root_dies(wf_env, capsys):
    _make_run(wf_env, run_id="t-nometa", with_meta=False)
    with pytest.raises(SystemExit):
        _baseline(run_id="t-nometa")
    err = capsys.readouterr().err
    # W3：错误信息必须同时给出两条修复路径
    assert "meta-set" in err
    assert "--project-root" in err


def test_meta_set_backfills_legacy_run(wf_env, capsys):
    """W3：旧 run 无 meta → meta-set 回填 → baseline 可直接跑（无需再传 --project-root）。"""
    _make_run(wf_env, run_id="t-backfill", with_meta=False)
    rc = wf.cmd_meta_set(
        argparse.Namespace(
            run_id="t-backfill",
            project_root=str(wf_env.repo),
            scope="workflow-group/**",
            json=True,
        )
    )
    summary = json.loads(capsys.readouterr().out)
    assert rc == 0 and summary["ok"] is True
    meta = json.loads((wf_env.runs / "t-backfill" / ".run-meta.json").read_text(encoding="utf-8"))
    assert meta["runId"] == "t-backfill"
    assert meta["projectRoot"] == str(wf_env.repo.resolve())
    assert meta["scope"] == "workflow-group/**"
    assert meta["updatedAt"] and meta["createdAt"]

    assert _baseline(run_id="t-backfill") == 0  # 不带 --project-root
    capsys.readouterr()
    assert _verify("t-backfill") == 0


def test_meta_set_preserves_existing_fields(wf_env, capsys):
    """已有 meta 只更新 projectRoot/scope，保留 template/createdAt。"""
    rd = _make_run(wf_env)
    meta_path = rd / ".run-meta.json"
    before = json.loads(meta_path.read_text(encoding="utf-8"))
    before["template"] = "templates/specialized/openrig-workflow-master"
    meta_path.write_text(json.dumps(before), encoding="utf-8")

    wf.cmd_meta_set(
        argparse.Namespace(
            run_id="t-base", project_root=str(wf_env.repo), scope="", json=True
        )
    )
    capsys.readouterr()
    after = json.loads(meta_path.read_text(encoding="utf-8"))
    assert after["template"] == before["template"]
    assert after["createdAt"] == before["createdAt"]
    assert after["scope"] == "workflow-group/**"  # 空 --scope 不覆盖已有值


def test_meta_set_rejects_non_git_root(wf_env, capsys):
    _make_run(wf_env, run_id="t-badroot", with_meta=False)
    plain = wf_env.repo.parent / "not-a-repo"
    plain.mkdir()
    with pytest.raises(SystemExit):
        wf.cmd_meta_set(
            argparse.Namespace(
                run_id="t-badroot", project_root=str(plain), scope="", json=True
            )
        )
    assert "git 仓库" in capsys.readouterr().err
    assert not (wf_env.runs / "t-badroot" / ".run-meta.json").exists()


def test_meta_set_unknown_run_dies(wf_env, capsys):
    with pytest.raises(SystemExit):
        wf.cmd_meta_set(
            argparse.Namespace(
                run_id="no-such-run", project_root=str(wf_env.repo), scope="", json=True
            )
        )
    assert "run 不存在" in capsys.readouterr().err


def test_new_run_writes_run_meta(new_run):
    rd = new_run(run_id="t-meta")
    meta = json.loads((rd / ".run-meta.json").read_text(encoding="utf-8"))
    assert meta["runId"] == "t-meta"
    assert meta["projectRoot"] == "/tmp/proj"
    assert meta["scope"] == "workflow-group/**"
    assert meta["template"]
    assert meta["createdAt"]
