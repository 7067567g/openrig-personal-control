# -*- coding: utf-8 -*-
"""H 盘安全门控的回归测试。

这些测试只用临时目录，不触碰真实 H 盘。覆盖：
1. 未挂载根默认拒绝初始化；
2. 结构化 safe op 可 PASS + 执行；
3. 越界、symlink、系统目录一律 FAIL；
4. FAIL 未审核不得执行；安全审核员必须独立；
5. red 风险还需要独立人工批准；
6. 门控账本不可重复执行/覆盖。
"""

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hdrive_gate as gate  # noqa: E402


@pytest.fixture
def env(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    run = runs / "safety-run"
    run.mkdir(parents=True)
    hroot = tmp_path / "h"
    hroot.mkdir()
    quarantine = hroot / "_quarantine"
    quarantine.mkdir()
    monkeypatch.setattr(gate, "RUNS", runs)
    return {
        "runs": runs,
        "run": run,
        "run_id": "safety-run",
        "root": hroot,
        "quarantine": quarantine,
        "tmp": tmp_path,
    }


def init(env, *, reviewers=None, approvers=None, require_mount=False):
    return gate.init_run(
        env["run_id"],
        str(env["root"]),
        str(env["quarantine"]),
        reviewers or ["safety-a1"],
        approvers if approvers is not None else ["user"],
        require_mount=require_mount,
    )


def propose(env, actions, agent="tdo-a1"):
    p = env["tmp"] / "actions.jsonl"
    p.write_text(
        "\n".join(json.dumps(a, ensure_ascii=False) for a in actions) + "\n",
        encoding="utf-8",
    )
    return gate.propose_file(env["run_id"], str(p), agent)


def gate_one(env, aid):
    results = gate.gate_all(env["run_id"])
    return next(r for r in results if r["action_id"] == aid)


def test_init_requires_mount_by_default(env):
    with pytest.raises(gate.GateError, match="不是挂载点"):
        init(env, require_mount=True)
    cfg = init(env)
    assert cfg["root"] == str(env["root"].resolve())
    assert cfg["safety_reviewers"] == ["safety-a1"]


def test_mkdir_pass_and_execute_once(env):
    init(env)
    dst = env["root"] / "new-dir"
    [aid] = propose(
        env,
        [{"op": "mkdir", "intent": "创建测试目录", "dst": str(dst)}],
    )
    result = gate_one(env, aid)
    assert result["status"] == "PASS"
    assert result["risk"] == "green"

    rec = gate.execute_action(env["run_id"], aid, "tdo-a1")
    assert rec["status"] == "SUCCESS"
    assert dst.is_dir()

    # 账本存在后不得重复执行，防止误重放。
    with pytest.raises(gate.GateError, match="已有执行记录"):
        gate.execute_action(env["run_id"], aid, "tdo-a1")


def test_path_escape_and_system_names_fail(env):
    init(env)
    outside = env["tmp"] / "outside"
    outside.mkdir()
    [aid1, aid2] = propose(
        env,
        [
            {
                "op": "mkdir",
                "intent": "越界测试",
                "dst": str(outside / "x"),
            },
            {
                "op": "mkdir",
                "intent": "系统目录测试",
                "dst": str(env["root"] / "$RECYCLE.BIN" / "x"),
            },
        ],
    )
    r1 = gate_one(env, aid1)
    r2 = gate_one(env, aid2)
    assert r1["status"] == "FAIL" and r1["risk"] == "red"
    assert any(x["code"] == "PATH_OUTSIDE_ROOT" for x in r1["reasons"])
    assert r2["status"] == "FAIL" and r2["risk"] == "red"
    assert any(x["code"] == "SYSTEM_PATH" for x in r2["reasons"])


def test_symlink_path_fails(env):
    init(env)
    outside = env["tmp"] / "outside"
    outside.mkdir()
    link = env["root"] / "link-out"
    link.symlink_to(outside, target_is_directory=True)
    [aid] = propose(
        env,
        [{"op": "mkdir", "intent": "symlink 越界测试", "dst": str(link / "x")}],
    )
    result = gate_one(env, aid)
    assert result["status"] == "FAIL"
    assert any(
        x["code"] in {"SYMLINK_PATH", "PATH_OUTSIDE_ROOT_RESOLVED"}
        for x in result["reasons"]
    )


def test_fail_needs_separate_reviewer_and_red_needs_human(env):
    # 把提出者也放进评审名单，专门验证代码里的自审拒绝，而不是只靠名单过滤。
    init(env, reviewers=["safety-a1", "tdo-a1"])
    [aid] = propose(
        env,
        [
            {
                "op": "exec",
                "intent": "受控例外：执行固定命令",
                "cwd": str(env["root"]),
                "argv": ["/bin/true"],
                "dry_run_evidence": "reports/dry-run-true.txt",
                "rollback": "无状态变更",
            }
        ],
    )
    result = gate_one(env, aid)
    assert result["status"] == "FAIL"
    assert result["risk"] == "red"

    # 未审核不得执行。
    with pytest.raises(gate.GateError, match="没有安全审核员 approve"):
        gate.execute_action(env["run_id"], aid, "tdo-a2")

    # 安全审核员不能是提出者。
    with pytest.raises(gate.GateError, match="不得审核自己"):
        gate.review_action(
            env["run_id"],
            aid,
            "tdo-a1",
            "approve",
            result["action_digest"],
            "提出者不应自审，需要独立审核",
            "no-evidence",
        )

    # 独立安全审核通过，但 red 仍需人工批准。
    review = gate.review_action(
        env["run_id"],
        aid,
        "safety-a1",
        "approve",
        result["action_digest"],
        "命令无参数、无文件路径、无状态变更；dry-run 证据已核对",
        "reports/dry-run-true.txt",
    )
    assert review["verdict"] == "approve"
    with pytest.raises(gate.GateError, match="缺少独立人工批准"):
        gate.execute_action(env["run_id"], aid, "tdo-a2")

    gate.human_approve_action(
        env["run_id"],
        aid,
        "user",
        result["action_digest"],
        "确认这是仅执行 /bin/true 的受控例外，不触碰 H 盘",
    )
    rec = gate.execute_action(env["run_id"], aid, "tdo-a2")
    assert rec["status"] == "SUCCESS"
    assert rec["effect_ok"] is None


def test_reject_blocks_execution(env):
    init(env)
    [aid] = propose(
        env,
        [
            {
                "op": "purge",
                "intent": "删除隔离区测试对象",
                "target": str(env["quarantine"] / "sample"),
                "dry_run_evidence": "reports/purge-list.txt",
            }
        ],
    )
    result = gate_one(env, aid)
    assert result["status"] == "FAIL" and result["risk"] == "red"
    gate.review_action(
        env["run_id"],
        aid,
        "safety-a1",
        "reject",
        result["action_digest"],
        "目标不存在，拒绝无依据删除",
        "reports/purge-list.txt",
    )
    with pytest.raises(gate.GateError, match="没有安全审核员 approve"):
        gate.execute_action(env["run_id"], aid, "tdo-a1")


def test_unknown_op_is_not_executable_even_with_approval(env):
    init(env)
    [aid] = propose(
        env,
        [{"op": "shell", "intent": "不存在的原始命令类型", "argv": ["rm", "-rf", "/"]}],
    )
    result = gate_one(env, aid)
    assert result["status"] == "FAIL"
    assert result["executable"] is False
    with pytest.raises(gate.GateError, match="不可执行"):
        gate.execute_action(env["run_id"], aid, "tdo-a1")


def test_status_counts_pending_review(env):
    init(env)
    [aid] = propose(
        env,
        [{"op": "mkdir", "intent": "待审测试", "dst": str(env["tmp"] / "outside")}],
    )
    gate_one(env, aid)
    data = gate.status_data(env["run_id"])
    assert data["summary"]["actions"] == 1
    assert data["summary"]["gate_fail"] == 1
    assert data["summary"]["safety_pending"] == 1
    assert data["rows"][0]["digest"] == result_digest(env, aid)


def result_digest(env, aid):
    return gate.load_action(env["run_id"], aid)["digest"]


def test_wf_safety_brief_and_delegate_guard(env, monkeypatch):
    """wf.py 必须能独立委派 SAFETY，且门控未初始化时拒绝委派。"""
    import wf  # noqa: E402

    rd = env["run"]
    (rd / "safety").mkdir()
    (rd / "safety" / "config.json").write_text(
        json.dumps({"gate_version": 1}), encoding="utf-8"
    )
    (rd / "PROJECT.md").write_text(
        """<!-- wf-doc
run: safety-run
round: 1
doc: PROJECT
owner: PMO
state: plan-ready
updated: 2026-10-18
-->
# PROJECT
""",
        encoding="utf-8",
    )
    (rd / "STATUS-Round-1.md").write_text(
        """<!-- wf-doc
run: safety-run
round: 1
doc: STATUS
owner: TDO
state: tdo-in-progress
updated: 2026-10-18
-->
# STATUS
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(wf, "RUNS", env["runs"])
    wf._delegate_guards(rd, "safety")  # 不抛
    text = wf.brief_text("safety", env["run_id"], "safety-a1")
    assert "独立安全审核员" in text
    assert "hdrive_gate.py review" in text

    # 未初始化门控的 run 不得委派 SAFETY。
    (rd / "safety" / "config.json").unlink()
    with pytest.raises(SystemExit):
        wf._delegate_guards(rd, "safety")


def test_quarantine_pass_moves_and_verifies(env):
    init(env)
    src = env["root"] / "candidate.tmp"
    src.write_text("demo\n", encoding="utf-8")
    dst = env["quarantine"] / "2026-10-18" / "candidate.tmp"
    dst.parent.mkdir()
    [aid] = propose(
        env,
        [
            {
                "op": "quarantine",
                "intent": "把已确认的临时文件移入隔离区，保留可回滚路径",
                "src": str(src),
                "dst": str(dst),
            }
        ],
    )
    result = gate_one(env, aid)
    assert result["status"] == "PASS", result["reasons"]
    rec = gate.execute_action(env["run_id"], aid, "tdo-a1")
    assert rec["status"] == "SUCCESS"
    assert not src.exists()
    assert dst.read_text(encoding="utf-8") == "demo\n"
