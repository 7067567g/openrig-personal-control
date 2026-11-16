#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""H 盘专项整理的安全门控与执行器（fail-closed）。

设计目标：
1. 每个会改变 H 盘状态的动作用一个显式 action 表示；原始 shell 字符串不能直接执行。
2. 门控自动判定 PASS / FAIL；PASS 可执行，FAIL 必须由独立安全审核员逐条审核。
3. 红色动作在安全审核通过后，还需要独立人工批准；执行器每次只执行一个 action。
4. 所有判定、审核、人工批准、执行结果都写入 run 目录的 safety/ 账本，append-only。

用法见 `python3 scripts/hdrive_gate.py --help` 与
`templates/specialized/h-drive-cleanup/SPEC.md`。

注意：这是工作流门控，不是操作系统沙箱。真正的 H 盘写权限仍应尽量收窄；
任何绕过本执行器直接写 H 盘的行为按 S1 安全事件处理。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parent.parent  # workflow-group/
RUNS = SCRIPT_ROOT / "runs"

GATE_VERSION = 1
SUPPORTED_OPS = {"mkdir", "copy", "move", "quarantine", "purge", "exec"}
MUTATING_OPS = {"mkdir", "copy", "move", "quarantine", "purge", "exec"}
SYSTEM_NAMES = {
    "$recycle.bin",
    "system volume information",
    "$winreagent",
    "recovery",
    "windows",
    "program files",
    "program files (x86)",
    "programdata",
    "perflogs",
    "pagefile.sys",
    "hiberfil.sys",
    "swapfile.sys",
    "found.000",
    "lost+found",
}
# 这些解释器/破坏性程序不允许通过 exec 绕过结构化门控；需要时改写成结构化 op，
# 或走线下人工处置并另开安全决策。
FORBIDDEN_EXEC_BASENAMES = {
    "sh",
    "bash",
    "zsh",
    "dash",
    "ksh",
    "fish",
    "csh",
    "tcsh",
    "python",
    "python3",
    "perl",
    "ruby",
    "node",
    "cmd",
    "cmd.exe",
    "powershell",
    "pwsh",
    "wsl",
    "rm",
    "rmdir",
    "del",
    "erase",
    "rd",
    "format",
    "diskpart",
    "dd",
    "mkfs",
    "mkfs.ext4",
    "mount",
    "umount",
    "shred",
    "wipefs",
    "chmod",
    "chown",
    "icacls",
    "takeown",
    "attrib",
}
BAD_PATH_CHARS_RE = re.compile(r"[*?\[\]\x00-\x1f\x7f]")
DRIVE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


class GateError(Exception):
    """门控拒绝或输入非法。"""

    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


class PathProblem(Exception):
    def __init__(self, code: str, message: str, risk: str = "yellow"):
        super().__init__(message)
        self.code = code
        self.message = message
        self.risk = risk


# --------------------------------------------------------------- common utils
def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def proposal_digest(proposal: dict[str, Any]) -> str:
    return sha256_text(canonical_json(proposal))


def run_dir(run_id: str) -> Path:
    p = RUNS / run_id
    if not p.is_dir():
        raise GateError(f"run 不存在: {p}")
    return p


def safety_dir(run_id: str) -> Path:
    return run_dir(run_id) / "safety"


def config_path(run_id: str) -> Path:
    return safety_dir(run_id) / "config.json"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise GateError(f"文件不存在: {path}")
    except json.JSONDecodeError as exc:
        raise GateError(f"JSON 损坏: {path}: {exc}")


def _write_new_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
    except FileExistsError:
        raise GateError(f"拒绝覆盖已有安全账本: {path}")


def _write_json_atomic(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def load_config(run_id: str) -> dict[str, Any]:
    cfg = _load_json(config_path(run_id))
    if cfg.get("gate_version") != GATE_VERSION:
        raise GateError(
            f"门控配置版本不兼容: {cfg.get('gate_version')} != {GATE_VERSION}"
        )
    return cfg


def action_path(run_id: str, action_id: str) -> Path:
    if not re.fullmatch(r"ACT-\d{4,}", action_id):
        raise GateError(f"action id 非法: {action_id}")
    return safety_dir(run_id) / "actions" / f"{action_id}.json"


def gate_path(run_id: str, action_id: str) -> Path:
    return safety_dir(run_id) / "gates" / f"{action_id}.json"


def review_path(run_id: str, action_id: str) -> Path:
    return safety_dir(run_id) / "reviews" / f"{action_id}.json"


def human_path(run_id: str, action_id: str) -> Path:
    return safety_dir(run_id) / "human-approvals" / f"{action_id}.json"


def execution_path(run_id: str, action_id: str) -> Path:
    return safety_dir(run_id) / "executions" / f"{action_id}.json"


def load_action(run_id: str, action_id: str) -> dict[str, Any]:
    action = _load_json(action_path(run_id, action_id))
    proposal = action.get("proposal")
    if not isinstance(proposal, dict):
        raise GateError(f"{action_id}: 缺少 proposal")
    actual = proposal_digest(proposal)
    if actual != action.get("digest"):
        raise GateError(
            f"{action_id}: action 摘要被篡改（记录={action.get('digest')}，实际={actual}）；停止并登记 S1"
        )
    return action


def load_gate(run_id: str, action_id: str) -> dict[str, Any]:
    result = _load_json(gate_path(run_id, action_id))
    action = load_action(run_id, action_id)
    if result.get("action_digest") != action.get("digest"):
        raise GateError(f"{action_id}: gate 结果与 action 摘要不一致，拒绝继续")
    return result


def load_review(run_id: str, action_id: str) -> dict[str, Any] | None:
    p = review_path(run_id, action_id)
    return _load_json(p) if p.exists() else None


def load_human(run_id: str, action_id: str) -> dict[str, Any] | None:
    p = human_path(run_id, action_id)
    return _load_json(p) if p.exists() else None


def load_execution(run_id: str, action_id: str) -> dict[str, Any] | None:
    p = execution_path(run_id, action_id)
    return _load_json(p) if p.exists() else None


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _check_root_guard(root: Path) -> None:
    if root in {Path("/"), Path("/mnt"), Path("/media"), Path.home()}:
        raise GateError(f"拒绝把危险目录当作 H 盘根: {root}")
    if not root.exists():
        raise GateError(f"H 盘根不存在: {root}")
    if not root.is_dir():
        raise GateError(f"H 盘根不是目录: {root}")


def _check_no_symlink_components(path: Path, root: Path) -> None:
    """拒绝目标路径中任何已存在的符号链接/重解析点组件。"""
    try:
        rel = path.relative_to(root)
    except ValueError:
        raise PathProblem(
            "PATH_OUTSIDE_ROOT", f"路径越出 H 盘根: {path}", risk="red"
        )
    cur = root
    for part in rel.parts:
        cur = cur / part
        if cur.is_symlink():
            raise PathProblem(
                "SYMLINK_PATH", f"路径含符号链接/重解析点: {cur}", risk="red"
            )


def resolve_safe_path(
    raw: Any,
    cfg: dict[str, Any],
    label: str,
    *,
    allow_root: bool = False,
    quarantine_only: bool = False,
) -> Path:
    """把 action 中的路径解析为受限绝对路径；不满足即抛 PathProblem。"""
    if not isinstance(raw, str) or not raw.strip():
        raise PathProblem("PATH_INVALID", f"{label} 必须是非空字符串")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in raw):
        raise PathProblem("PATH_CONTROL_CHAR", f"{label} 含控制字符", risk="red")
    if BAD_PATH_CHARS_RE.search(raw):
        raise PathProblem(
            "PATH_WILDCARD", f"{label} 含通配符或非法字符: {raw}", risk="red"
        )
    if DRIVE_PATH_RE.match(raw):
        raise PathProblem(
            "WINDOWS_DRIVE_PATH",
            f"{label} 请使用已挂载的 POSIX 路径（如 /mnt/h/...），不要直接写盘符: {raw}",
            risk="red",
        )

    root = Path(cfg["root"]).resolve()
    original = Path(raw)
    if not original.is_absolute():
        raise PathProblem("PATH_NOT_ABSOLUTE", f"{label} 必须是绝对路径: {raw}")
    if ".." in original.parts:
        raise PathProblem("PATH_DOTDOT", f"{label} 不允许包含 ..: {raw}", risk="red")

    # 先按未解析路径做词法边界检查，避免 ../ 逃逸；再用 resolve 捕获 symlink 逃逸。
    original_abs = Path(os.path.abspath(raw))
    if not _is_under(original_abs, root) or (
        original_abs == root and not allow_root
    ):
        raise PathProblem(
            "PATH_OUTSIDE_ROOT", f"{label} 越出 H 盘根: {raw}", risk="red"
        )

    rel = original_abs.relative_to(root)
    for part in rel.parts:
        low = part.casefold()
        if low in SYSTEM_NAMES or low.startswith(".trash-"):
            raise PathProblem(
                "SYSTEM_PATH", f"{label} 指向系统/回收目录: {raw}", risk="red"
            )

    _check_no_symlink_components(original_abs, root)
    resolved = original_abs.resolve(strict=False)
    if not _is_under(resolved, root) or (resolved == root and not allow_root):
        raise PathProblem(
            "PATH_OUTSIDE_ROOT_RESOLVED",
            f"{label} 解析后越出 H 盘根: {raw} -> {resolved}",
            risk="red",
        )
    if quarantine_only:
        qroot = Path(cfg["quarantine_root"]).resolve()
        if not _is_under(resolved, qroot) or resolved == qroot:
            raise PathProblem(
                "PATH_NOT_QUARANTINE",
                f"{label} 必须位于隔离区 {qroot} 内（且不能是隔离区根本身）: {resolved}",
                risk="red",
            )
    return resolved


# --------------------------------------------------------------- evaluation
def _problem(
    reasons: list[dict[str, str]], code: str, message: str, risk: str = "yellow"
) -> None:
    reasons.append({"code": code, "message": message, "risk": risk})


def _safe_or_problem(
    reasons: list[dict[str, str]],
    raw: Any,
    cfg: dict[str, Any],
    label: str,
    **kwargs: Any,
) -> Path | None:
    try:
        return resolve_safe_path(raw, cfg, label, **kwargs)
    except PathProblem as exc:
        _problem(reasons, exc.code, exc.message, exc.risk)
        return None


def _exec_action_risky(
    reasons: list[dict[str, str]], proposal: dict[str, Any], cfg: dict[str, Any]
) -> bool:
    """返回是否触发不可自动通过的红线。"""
    red = False
    argv = proposal.get("argv")
    if not isinstance(argv, list) or not argv:
        _problem(reasons, "ARGV_INVALID", "exec.argv 必须是非空字符串数组", "red")
        return True

    clean: list[str] = []
    for token in argv:
        if not isinstance(token, str) or not token:
            _problem(reasons, "ARGV_INVALID", "exec.argv 每项必须是非空字符串", "red")
            red = True
            continue
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in token):
            _problem(reasons, "ARGV_CONTROL_CHAR", "exec.argv 含控制字符", "red")
            red = True
        clean.append(token)

    if not clean:
        return True
    basename = Path(clean[0]).name.casefold()
    if basename in FORBIDDEN_EXEC_BASENAMES:
        _problem(
            reasons,
            "FORBIDDEN_EXECUTABLE",
            f"exec 禁止解释器/破坏性程序: {basename}；请改用结构化 op",
            "red",
        )
        red = True

    cwd = _safe_or_problem(
        reasons, proposal.get("cwd", cfg["root"]), cfg, "exec.cwd", allow_root=True
    )
    if cwd is not None and not cwd.is_dir():
        _problem(reasons, "CWD_MISSING", f"exec.cwd 不存在或不是目录: {cwd}", "red")
        red = True

    # 路径参数必须落在 H 盘根内；这里只做保守的静态检查，不能替代安全审核。
    if cwd is not None:
        for token in clean[1:]:
            candidate = token
            if token.startswith("-") and "=" in token:
                candidate = token.split("=", 1)[1]
            if candidate.startswith("-"):
                continue
            if DRIVE_PATH_RE.match(candidate):
                _problem(
                    reasons,
                    "WINDOWS_DRIVE_PATH",
                    f"exec 路径参数必须使用 POSIX 挂载路径: {token}",
                    "red",
                )
                red = True
                continue
            if candidate.startswith("/") or "/" in candidate:
                probe = Path(candidate)
                if not probe.is_absolute():
                    probe = cwd / probe
                try:
                    resolve_safe_path(str(probe), cfg, "exec.argv-path", allow_root=True)
                except PathProblem as exc:
                    _problem(reasons, exc.code, exc.message, exc.risk)
                    red = True
    return red


def evaluate_action(action: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """生成可复现的门控结论；只做静态/只读检查，不改变 H 盘。"""
    proposal = action.get("proposal") or {}
    op = proposal.get("op")
    intent = proposal.get("intent")
    reasons: list[dict[str, str]] = []
    red = False
    executable = True

    if not isinstance(intent, str) or not intent.strip():
        _problem(reasons, "INTENT_MISSING", "action.intent 不能为空")

    if op not in SUPPORTED_OPS:
        _problem(
            reasons,
            "UNKNOWN_OP",
            f"未知 op={op!r}；只允许 {sorted(SUPPORTED_OPS)}",
            "red",
        )
        executable = False
    elif op == "mkdir":
        dst = _safe_or_problem(reasons, proposal.get("dst"), cfg, "dst")
        if dst is not None:
            if dst.exists():
                _problem(reasons, "DEST_EXISTS", f"目标已存在: {dst}")
            if not dst.parent.is_dir():
                _problem(reasons, "PARENT_MISSING", f"目标父目录不存在: {dst.parent}")
    elif op in {"copy", "move", "quarantine"}:
        src = _safe_or_problem(reasons, proposal.get("src"), cfg, "src")
        dst = _safe_or_problem(
            reasons,
            proposal.get("dst"),
            cfg,
            "dst",
            quarantine_only=(op == "quarantine"),
        )
        if src is not None and dst is not None:
            if src == dst:
                _problem(reasons, "SAME_SRC_DST", "src 与 dst 不能相同", "red")
            if not src.exists():
                _problem(reasons, "SRC_MISSING", f"源不存在: {src}")
            if dst.exists():
                _problem(reasons, "DEST_EXISTS", f"目标已存在: {dst}")
            if not dst.parent.is_dir():
                _problem(reasons, "PARENT_MISSING", f"目标父目录不存在: {dst.parent}")
            if op in {"move", "quarantine"} and src.exists() and dst.parent.is_dir():
                try:
                    if src.stat().st_dev != dst.parent.stat().st_dev:
                        _problem(
                            reasons,
                            "CROSS_DEVICE_MOVE",
                            "move/quarantine 跨文件系统会退化为复制+删除，拒绝自动执行",
                            "red",
                        )
                except OSError as exc:
                    _problem(reasons, "STAT_FAILED", f"无法读取文件系统信息: {exc}")
    elif op == "purge":
        target = _safe_or_problem(
            reasons, proposal.get("target"), cfg, "target", quarantine_only=True
        )
        if target is not None and not target.exists():
            _problem(reasons, "TARGET_MISSING", f"待清理目标不存在: {target}")
        if not proposal.get("dry_run_evidence"):
            _problem(
                reasons,
                "DRY_RUN_EVIDENCE_MISSING",
                "purge 必须先有 dry-run/清单证据（dry_run_evidence）",
                "red",
            )
        _problem(
            reasons,
            "DUAL_APPROVAL_REQUIRED",
            "purge 永久删除，必须逐条安全审核 + 独立人工批准",
            "red",
        )
        red = True
    elif op == "exec":
        if _exec_action_risky(reasons, proposal, cfg):
            red = True
        if not proposal.get("dry_run_evidence"):
            _problem(
                reasons,
                "DRY_RUN_EVIDENCE_MISSING",
                "exec 必须先有 dry-run 证据（dry_run_evidence）",
                "red",
            )
            red = True
        if not isinstance(proposal.get("rollback"), str) or not proposal[
            "rollback"
        ].strip():
            _problem(
                reasons,
                "ROLLBACK_MISSING",
                "exec 必须写清回滚/恢复方案（rollback）",
                "red",
            )
            red = True
        _problem(
            reasons,
            "GATE_REVIEW_REQUIRED",
            "exec 永不由门控自动放行，必须逐条安全审核 + 独立人工批准",
            "red",
        )
        red = True

    if any(r.get("risk") == "red" for r in reasons):
        red = True
    status = "PASS" if not reasons else "FAIL"
    risk = "green" if status == "PASS" else ("red" if red else "yellow")
    return {
        "action_id": action["id"],
        "action_digest": action["digest"],
        "gate_version": GATE_VERSION,
        "status": status,
        "risk": risk,
        "executable": bool(executable),
        "review_required": status == "FAIL",
        "reasons": reasons,
        "evaluated_at": now_str(),
    }


# --------------------------------------------------------------- commands
def init_run(
    run_id: str,
    root: str,
    quarantine_root: str,
    safety_reviewers: list[str],
    human_approvers: list[str] | None = None,
    *,
    require_mount: bool = True,
) -> dict[str, Any]:
    rd = run_dir(run_id)
    cfg_file = config_path(run_id)
    if cfg_file.exists():
        raise GateError(f"安全门控已初始化，拒绝覆盖: {cfg_file}")

    root_p = Path(root).expanduser()
    if not root_p.is_absolute():
        raise GateError("--root 必须是绝对路径")
    root_p = root_p.resolve(strict=False)
    _check_root_guard(root_p)
    if require_mount and not os.path.ismount(root_p):
        raise GateError(
            f"根路径不是挂载点: {root_p}；H 盘未挂载时不得初始化门控（用 --no-require-mount 仅限测试）"
        )

    qroot_p = Path(quarantine_root).expanduser()
    if not qroot_p.is_absolute():
        raise GateError("--quarantine-root 必须是绝对路径")
    qroot_p = qroot_p.resolve(strict=False)
    if not _is_under(qroot_p, root_p) or qroot_p == root_p:
        raise GateError(f"隔离区必须位于 H 盘根内且不能等于根: {qroot_p}")

    reviewers = sorted({x.strip() for x in safety_reviewers if x.strip()})
    if not reviewers:
        raise GateError("必须指定至少一个独立安全审核员")
    approvers = sorted({x.strip() for x in (human_approvers or []) if x.strip()})
    overlap = set(reviewers) & set(approvers)
    if overlap:
        raise GateError(f"安全审核员与人工批准人必须分离: {sorted(overlap)}")

    cfg = {
        "gate_version": GATE_VERSION,
        "run": run_id,
        "root": str(root_p),
        "quarantine_root": str(qroot_p),
        "safety_reviewers": reviewers,
        "human_approvers": approvers,
        "require_mount": bool(require_mount),
        "created_at": now_str(),
        "notes": "H 盘专项整理专用安全门控；fail-closed；未审核 FAIL 不得执行。",
    }
    sd = safety_dir(run_id)
    for sub in ("actions", "gates", "reviews", "human-approvals", "executions"):
        (sd / sub).mkdir(parents=True, exist_ok=True)
    _write_new_json(cfg_file, cfg)
    return cfg


def _validate_proposal_shape(item: Any, idx: int) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise GateError(f"第 {idx} 行动作不是 JSON object")
    forbidden_meta = {"id", "requested_by", "created_at", "digest"}
    leaked = forbidden_meta & set(item)
    if leaked:
        raise GateError(f"第 {idx} 行不允许自带元字段: {sorted(leaked)}")
    op = item.get("op")
    if not isinstance(op, str) or not op.strip():
        raise GateError(f"第 {idx} 行缺少 op")
    intent = item.get("intent")
    if not isinstance(intent, str) or not intent.strip():
        raise GateError(f"第 {idx} 行缺少 intent")
    return item


def propose_file(run_id: str, file_path: str, agent: str) -> list[str]:
    cfg = load_config(run_id)
    del cfg  # 只用于确认门控已初始化
    if not agent.strip():
        raise GateError("--agent 不能为空")
    p = Path(file_path)
    if not p.is_absolute():
        p = Path.cwd() / p
    if not p.is_file():
        raise GateError(f"动作清单不存在: {p}")

    proposals: list[dict[str, Any]] = []
    for idx, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise GateError(f"第 {idx} 行不是合法 JSON: {exc}")
        proposals.append(_validate_proposal_shape(item, idx))
    if not proposals:
        raise GateError("动作清单为空")
    if len(proposals) > 10000:
        raise GateError("单次 propose 最多 10000 个 action；请拆批")

    actions_dir = safety_dir(run_id) / "actions"
    existing = []
    for f in actions_dir.glob("ACT-*.json"):
        m = re.fullmatch(r"ACT-(\d+)\.json", f.name)
        if m:
            existing.append(int(m.group(1)))
    next_num = max(existing, default=0) + 1

    ids: list[str] = []
    # 先落临时文件，全部成功后再原子改名，避免半批写入。
    pending: list[tuple[Path, Path]] = []
    try:
        for offset, proposal in enumerate(proposals):
            aid = f"ACT-{next_num + offset:04d}"
            action = {
                "id": aid,
                "requested_by": agent.strip(),
                "created_at": now_str(),
                "proposal": proposal,
                "digest": proposal_digest(proposal),
            }
            final = action_path(run_id, aid)
            tmp = final.with_name(f".{final.name}.{os.getpid()}.tmp")
            tmp.write_text(
                json.dumps(action, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            pending.append((tmp, final))
            ids.append(aid)
        for tmp, final in pending:
            # link 是 O_EXCL 语义：并发 propose 撞到同一 ID 时失败而不是覆盖。
            os.link(tmp, final)
            tmp.unlink()
    except Exception:
        for tmp, _ in pending:
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass
        raise
    return ids


def gate_all(run_id: str) -> list[dict[str, Any]]:
    cfg = load_config(run_id)
    results: list[dict[str, Any]] = []
    for f in sorted((safety_dir(run_id) / "actions").glob("ACT-*.json")):
        aid = f.stem
        action = load_action(run_id, aid)
        gp = gate_path(run_id, aid)
        if gp.exists():
            results.append(load_gate(run_id, aid))
            continue
        result = evaluate_action(action, cfg)
        _write_new_json(gp, result)
        results.append(result)
    return results


def review_action(
    run_id: str,
    action_id: str,
    reviewer: str,
    verdict: str,
    digest: str,
    reason: str,
    evidence: str,
) -> dict[str, Any]:
    cfg = load_config(run_id)
    reviewer = reviewer.strip()
    if reviewer not in cfg.get("safety_reviewers", []):
        raise GateError(f"{reviewer} 不在本 run 的安全审核员名单")
    if verdict not in {"approve", "reject"}:
        raise GateError("verdict 只允许 approve/reject")
    if len(reason.strip()) < 8:
        raise GateError("审核理由至少 8 个字符，写清依据")
    if len(evidence.strip()) < 3:
        raise GateError("审核证据不能为空（路径/命令/截图说明/dry-run 报告）")

    action = load_action(run_id, action_id)
    if reviewer == action.get("requested_by"):
        raise GateError("安全审核员不得审核自己提出的 action")
    gate = load_gate(run_id, action_id)
    if gate.get("status") != "FAIL":
        raise GateError(
            f"{action_id}: gate 状态为 {gate.get('status')}，只有 FAIL 才交安全审核"
        )
    if gate.get("action_digest") != action.get("digest"):
        raise GateError(f"{action_id}: gate 摘要不匹配")
    if digest.strip() != action.get("digest"):
        raise GateError(
            f"{action_id}: 你提交的 digest 与当前 action 不一致；请重新读取后再审"
        )
    if review_path(run_id, action_id).exists():
        raise GateError(f"{action_id}: 已有安全审核记录；每条 action 只允许一次终审")

    rec = {
        "action_id": action_id,
        "action_digest": action["digest"],
        "reviewer": reviewer,
        "verdict": verdict,
        "reason": reason.strip(),
        "evidence": evidence.strip(),
        "reviewed_at": now_str(),
        "gate_risk": gate.get("risk"),
        "gate_reasons": gate.get("reasons", []),
    }
    _write_new_json(review_path(run_id, action_id), rec)
    return rec


def human_approve_action(
    run_id: str,
    action_id: str,
    approver: str,
    digest: str,
    reason: str,
) -> dict[str, Any]:
    cfg = load_config(run_id)
    approver = approver.strip()
    if approver not in cfg.get("human_approvers", []):
        raise GateError(f"{approver} 不在本 run 的人工批准人名单")
    if len(reason.strip()) < 8:
        raise GateError("人工批准理由至少 8 个字符")

    action = load_action(run_id, action_id)
    gate = load_gate(run_id, action_id)
    review = load_review(run_id, action_id)
    if gate.get("risk") != "red":
        raise GateError(f"{action_id}: 只有 red 风险动作需要人工批准")
    if not review or review.get("verdict") != "approve":
        raise GateError(f"{action_id}: 必须先有安全审核员 approve")
    if review.get("action_digest") != action.get("digest"):
        raise GateError(f"{action_id}: 安全审核摘要与 action 不一致")
    if review.get("reviewer") == approver:
        raise GateError("人工批准人不得与安全审核员为同一身份")
    if approver == action.get("requested_by"):
        raise GateError("人工批准人不得是 action 提出者")
    if digest.strip() != action.get("digest"):
        raise GateError(f"{action_id}: 人工批准 digest 不匹配")
    if human_path(run_id, action_id).exists():
        raise GateError(f"{action_id}: 已有人工批准记录")

    rec = {
        "action_id": action_id,
        "action_digest": action["digest"],
        "approver": approver,
        "reason": reason.strip(),
        "approved_at": now_str(),
        "safety_reviewer": review.get("reviewer"),
    }
    _write_new_json(human_path(run_id, action_id), rec)
    return rec


def _precondition_check(
    run_id: str, action: dict[str, Any], cfg: dict[str, Any]
) -> list[str]:
    """执行前再检查一次，防止审核后文件系统变化。返回问题列表。"""
    problems: list[str] = []
    proposal = action["proposal"]
    op = proposal.get("op")
    try:
        if op == "mkdir":
            dst = resolve_safe_path(proposal.get("dst"), cfg, "dst")
            if dst.exists():
                problems.append(f"目标已存在: {dst}")
            if not dst.parent.is_dir():
                problems.append(f"父目录不存在: {dst.parent}")
        elif op in {"copy", "move", "quarantine"}:
            src = resolve_safe_path(proposal.get("src"), cfg, "src")
            dst = resolve_safe_path(
                proposal.get("dst"),
                cfg,
                "dst",
                quarantine_only=(op == "quarantine"),
            )
            if not src.exists():
                problems.append(f"源不存在: {src}")
            if dst.exists():
                problems.append(f"目标已存在: {dst}")
            if not dst.parent.is_dir():
                problems.append(f"父目录不存在: {dst.parent}")
        elif op == "purge":
            target = resolve_safe_path(
                proposal.get("target"), cfg, "target", quarantine_only=True
            )
            if not target.exists():
                problems.append(f"待清理目标不存在: {target}")
        elif op == "exec":
            cwd = resolve_safe_path(
                proposal.get("cwd", cfg["root"]), cfg, "exec.cwd", allow_root=True
            )
            if not cwd.is_dir():
                problems.append(f"cwd 不存在: {cwd}")
        else:
            problems.append(f"不支持执行 op={op!r}")
    except PathProblem as exc:
        problems.append(f"{exc.code}: {exc.message}")
    return problems


def _build_command(
    action: dict[str, Any], cfg: dict[str, Any]
) -> tuple[list[str], Path]:
    proposal = action["proposal"]
    op = proposal["op"]
    cwd = Path(cfg["root"])
    if op == "mkdir":
        dst = resolve_safe_path(proposal.get("dst"), cfg, "dst")
        return ["mkdir", "--", str(dst)], cwd
    if op == "copy":
        src = resolve_safe_path(proposal.get("src"), cfg, "src")
        dst = resolve_safe_path(proposal.get("dst"), cfg, "dst")
        return ["cp", "-a", "-n", "--", str(src), str(dst)], cwd
    if op in {"move", "quarantine"}:
        src = resolve_safe_path(proposal.get("src"), cfg, "src")
        dst = resolve_safe_path(
            proposal.get("dst"), cfg, "dst", quarantine_only=(op == "quarantine")
        )
        return ["mv", "-n", "--", str(src), str(dst)], cwd
    if op == "purge":
        target = resolve_safe_path(
            proposal.get("target"), cfg, "target", quarantine_only=True
        )
        return ["rm", "-r", "--", str(target)], cwd
    if op == "exec":
        cwd = resolve_safe_path(
            proposal.get("cwd", cfg["root"]), cfg, "exec.cwd", allow_root=True
        )
        argv = proposal.get("argv")
        if not isinstance(argv, list) or not argv:
            raise GateError("exec.argv 非法")
        if not all(isinstance(x, str) and x for x in argv):
            raise GateError("exec.argv 每项必须是非空字符串")
        return list(argv), cwd
    raise GateError(f"不支持执行 op={op!r}")


def _effect_ok(action: dict[str, Any], cfg: dict[str, Any]) -> bool | None:
    proposal = action["proposal"]
    op = proposal["op"]
    if op == "mkdir":
        return resolve_safe_path(proposal.get("dst"), cfg, "dst").is_dir()
    if op == "copy":
        return resolve_safe_path(proposal.get("dst"), cfg, "dst").exists()
    if op in {"move", "quarantine"}:
        src = resolve_safe_path(proposal.get("src"), cfg, "src")
        dst = resolve_safe_path(
            proposal.get("dst"), cfg, "dst", quarantine_only=(op == "quarantine")
        )
        return (not src.exists()) and dst.exists()
    if op == "purge":
        return not resolve_safe_path(
            proposal.get("target"), cfg, "target", quarantine_only=True
        ).exists()
    if op == "exec":
        return None  # 任意命令的最终效果由安全审核/QA 证据核验
    return False


def execute_action(run_id: str, action_id: str, agent: str) -> dict[str, Any]:
    cfg = load_config(run_id)
    agent = agent.strip()
    if not agent:
        raise GateError("--agent 不能为空")
    if agent in cfg.get("safety_reviewers", []):
        raise GateError("安全审核员不得执行 action")
    if agent in cfg.get("human_approvers", []):
        raise GateError("人工批准人不得执行 action")
    if cfg.get("require_mount") and not os.path.ismount(cfg["root"]):
        raise GateError("H 盘根当前不是挂载点，拒绝执行")

    action = load_action(run_id, action_id)
    if execution_path(run_id, action_id).exists():
        raise GateError(f"{action_id}: 已有执行记录，拒绝重复执行")
    gate = load_gate(run_id, action_id)
    if gate.get("action_digest") != action.get("digest"):
        raise GateError(f"{action_id}: gate 摘要不匹配")
    if not gate.get("executable", False):
        raise GateError(f"{action_id}: 门控标记为不可执行（executable=false）")

    review = load_review(run_id, action_id)
    human = load_human(run_id, action_id)
    if gate.get("status") == "PASS":
        if gate.get("risk") != "green":
            raise GateError(f"{action_id}: PASS action 的风险级别异常")
    elif gate.get("status") == "FAIL":
        if not review or review.get("verdict") != "approve":
            raise GateError(f"{action_id}: 门控未通过且没有安全审核员 approve，拒绝执行")
        if review.get("action_digest") != action.get("digest"):
            raise GateError(f"{action_id}: 安全审核摘要不匹配")
        if review.get("reviewer") == action.get("requested_by"):
            raise GateError(f"{action_id}: 安全审核员与提出者相同，拒绝执行")
        if gate.get("risk") == "red":
            if not human:
                raise GateError(f"{action_id}: red 风险动作缺少独立人工批准，拒绝执行")
            if human.get("action_digest") != action.get("digest"):
                raise GateError(f"{action_id}: 人工批准摘要不匹配")
            if human.get("approver") in {review.get("reviewer"), action.get("requested_by")}:
                raise GateError(f"{action_id}: 人工批准人与其他角色未分离，拒绝执行")
        elif gate.get("risk") != "yellow":
            raise GateError(f"{action_id}: 未知风险级别 {gate.get('risk')!r}")
    else:
        raise GateError(f"{action_id}: 未知 gate 状态 {gate.get('status')!r}")

    problems = _precondition_check(run_id, action, cfg)
    if problems:
        rec = {
            "action_id": action_id,
            "action_digest": action["digest"],
            "agent": agent,
            "status": "BLOCKED_PRECHECK",
            "problems": problems,
            "at": now_str(),
        }
        _write_new_json(execution_path(run_id, action_id), rec)
        raise GateError(f"{action_id}: 执行前复核失败: {'; '.join(problems)}")

    command, cwd = _build_command(action, cfg)
    rec = {
        "action_id": action_id,
        "action_digest": action["digest"],
        "agent": agent,
        "status": "RUNNING",
        "command_argv": command,
        "cwd": str(cwd),
        "started_at": now_str(),
        "gate_status": gate.get("status"),
        "risk": gate.get("risk"),
        "safety_reviewer": (review or {}).get("reviewer"),
        "human_approver": (human or {}).get("approver"),
    }
    _write_new_json(execution_path(run_id, action_id), rec)

    try:
        proc = subprocess.run(
            command,
            cwd=str(cwd),
            shell=False,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=3600,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        returncode = proc.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else "命令超时（3600s）"
        returncode = 124
    except Exception as exc:  # noqa: BLE001
        stdout = ""
        stderr = f"执行器异常: {exc}"
        returncode = 125

    effect_ok = _effect_ok(action, cfg) if returncode == 0 else None
    if returncode != 0:
        status = "FAILED"
    elif effect_ok is False:
        status = "EFFECT_MISMATCH"
    else:
        status = "SUCCESS"

    rec.update(
        {
            "status": status,
            "returncode": returncode,
            "finished_at": now_str(),
            "effect_ok": effect_ok,
            "stdout_sha256": sha256_text(stdout),
            "stderr_sha256": sha256_text(stderr),
            "stdout_preview": stdout[-8000:],
            "stderr_preview": stderr[-8000:],
        }
    )
    _write_json_atomic(execution_path(run_id, action_id), rec)
    return rec


def status_data(run_id: str) -> dict[str, Any]:
    cfg = load_config(run_id)
    rows: list[dict[str, Any]] = []
    for f in sorted((safety_dir(run_id) / "actions").glob("ACT-*.json")):
        aid = f.stem
        action = load_action(run_id, aid)
        gate = load_gate(run_id, aid) if gate_path(run_id, aid).exists() else None
        review = load_review(run_id, aid)
        human = load_human(run_id, aid)
        execution = load_execution(run_id, aid)
        rows.append(
            {
                "action_id": aid,
                "digest": action["digest"],
                "requested_by": action.get("requested_by"),
                "op": (action.get("proposal") or {}).get("op"),
                "gate": (gate or {}).get("status", "UNGATED"),
                "risk": (gate or {}).get("risk"),
                "review": (review or {}).get("verdict", "PENDING" if gate and gate.get("status") == "FAIL" else "-"),
                "human": (human or {}).get("approver", "PENDING" if (gate or {}).get("risk") == "red" and review and review.get("verdict") == "approve" else "-"),
                "execution": (execution or {}).get("status", "-"),
                "reasons": (gate or {}).get("reasons", []),
            }
        )
    summary = {
        "actions": len(rows),
        "gate_pass": sum(1 for r in rows if r["gate"] == "PASS"),
        "gate_fail": sum(1 for r in rows if r["gate"] == "FAIL"),
        "ungated": sum(1 for r in rows if r["gate"] == "UNGATED"),
        "safety_pending": sum(
            1 for r in rows if r["gate"] == "FAIL" and r["review"] == "PENDING"
        ),
        "safety_reject": sum(1 for r in rows if r["review"] == "reject"),
        "executed_ok": sum(1 for r in rows if r["execution"] == "SUCCESS"),
        "executed_bad": sum(
            1 for r in rows if r["execution"] in {"FAILED", "EFFECT_MISMATCH", "BLOCKED_PRECHECK"}
        ),
        "running": sum(1 for r in rows if r["execution"] == "RUNNING"),
    }
    return {"run": run_id, "config": cfg, "summary": summary, "rows": rows}


# --------------------------------------------------------------- CLI
def _print_status(data: dict[str, Any], as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
        return
    cfg = data["config"]
    s = data["summary"]
    print(f"== hdrive gate: {data['run']} ==")
    print(f"root: {cfg['root']}")
    print(f"quarantine: {cfg['quarantine_root']}")
    print(f"safety reviewers: {', '.join(cfg.get('safety_reviewers', []))}")
    print(f"human approvers: {', '.join(cfg.get('human_approvers', [])) or '(未配置)'}")
    print(
        "actions={actions} gate_pass={gate_pass} gate_fail={gate_fail} ungated={ungated} "
        "safety_pending={safety_pending} safety_reject={safety_reject} "
        "executed_ok={executed_ok} executed_bad={executed_bad} running={running}".format(
            **s
        )
    )
    pending = [
        r for r in data["rows"] if r["gate"] == "FAIL" and r["review"] == "PENDING"
    ]
    if pending:
        print("\n[PENDING SAFETY REVIEW]")
        for r in pending:
            codes = ",".join(x.get("code", "?") for x in r.get("reasons", []))
            print(
                f"  {r['action_id']}  risk={r['risk']}  op={r['op']}  "
                f"digest={r['digest']}  reasons={codes}"
            )
    if s["safety_pending"]:
        print("\n门控状态为 BLOCKED：仍有未完成逐条安全审核的 FAIL action。")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="H 盘整理安全门控（fail-closed）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="初始化 run 级安全门控配置")
    p.add_argument("--run", required=True)
    p.add_argument("--root", required=True)
    p.add_argument("--quarantine-root", required=True)
    p.add_argument("--safety-reviewer", action="append", default=[])
    p.add_argument("--human-approver", action="append", default=[])
    p.add_argument(
        "--no-require-mount",
        dest="require_mount",
        action="store_false",
        help="仅测试用：允许根不是挂载点",
    )
    p.set_defaults(require_mount=True)

    p = sub.add_parser("propose", help="提交一批 action（JSONL）")
    p.add_argument("--run", required=True)
    p.add_argument("--file", required=True)
    p.add_argument("--agent", required=True)

    p = sub.add_parser("gate", help="对所有未门控 action 生成 PASS/FAIL 结论")
    p.add_argument("--run", required=True)

    p = sub.add_parser("pending", help="列出待逐条安全审核的 action")
    p.add_argument("--run", required=True)

    p = sub.add_parser("review", help="安全审核员逐条审核一个 FAIL action")
    p.add_argument("--run", required=True)
    p.add_argument("--action", required=True)
    p.add_argument("--reviewer", required=True)
    p.add_argument("--verdict", required=True, choices=["approve", "reject"])
    p.add_argument("--digest", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--evidence", required=True)

    p = sub.add_parser("human-approve", help="人工批准一个 red 风险 action")
    p.add_argument("--run", required=True)
    p.add_argument("--action", required=True)
    p.add_argument("--approver", required=True)
    p.add_argument("--digest", required=True)
    p.add_argument("--reason", required=True)

    p = sub.add_parser("run", help="执行一个已放行 action（一次只执行一个）")
    p.add_argument("--run", required=True)
    p.add_argument("--action", required=True)
    p.add_argument("--agent", required=True)

    p = sub.add_parser("status", help="查看门控与执行账本状态")
    p.add_argument("--run", required=True)
    p.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "init":
            cfg = init_run(
                args.run,
                args.root,
                args.quarantine_root,
                args.safety_reviewer,
                args.human_approver,
                require_mount=args.require_mount,
            )
            print(f"[OK] 安全门控已初始化: {config_path(args.run)}")
            print(f"     root={cfg['root']}")
            print(f"     quarantine={cfg['quarantine_root']}")
        elif args.cmd == "propose":
            ids = propose_file(args.run, args.file, args.agent)
            print(f"[OK] 已登记 {len(ids)} 个 action: {', '.join(ids)}")
            print(f"下一步: python3 scripts/hdrive_gate.py gate --run {args.run}")
        elif args.cmd == "gate":
            results = gate_all(args.run)
            passed = sum(1 for r in results if r["status"] == "PASS")
            failed = sum(1 for r in results if r["status"] == "FAIL")
            print(f"[OK] 门控完成: PASS={passed} FAIL={failed}")
            for r in results:
                codes = ",".join(x["code"] for x in r["reasons"]) or "-"
                print(
                    f"  {r['action_id']}  {r['status']}  risk={r['risk']}  "
                    f"digest={r['action_digest']}  reasons={codes}"
                )
            if failed:
                print("FAIL action 必须由安全审核员逐条 review；未审核不得执行。")
        elif args.cmd == "pending":
            data = status_data(args.run)
            pending = [
                r for r in data["rows"] if r["gate"] == "FAIL" and r["review"] == "PENDING"
            ]
            if not pending:
                print("(无待审 action)")
            for r in pending:
                codes = ",".join(x["code"] for x in r.get("reasons", []))
                print(
                    f"{r['action_id']}  risk={r['risk']}  op={r['op']}  "
                    f"digest={r['digest']}  reasons={codes}"
                )
        elif args.cmd == "review":
            rec = review_action(
                args.run,
                args.action,
                args.reviewer,
                args.verdict,
                args.digest,
                args.reason,
                args.evidence,
            )
            print(f"[OK] 安全审核已记录: {rec['action_id']} {rec['verdict']}")
        elif args.cmd == "human-approve":
            rec = human_approve_action(
                args.run, args.action, args.approver, args.digest, args.reason
            )
            print(f"[OK] 人工批准已记录: {rec['action_id']}")
        elif args.cmd == "run":
            rec = execute_action(args.run, args.action, args.agent)
            print(
                f"[{rec['status']}] {rec['action_id']} returncode={rec.get('returncode')} "
                f"effect_ok={rec.get('effect_ok')}"
            )
            if rec["status"] != "SUCCESS":
                return 4
        elif args.cmd == "status":
            _print_status(status_data(args.run), args.json)
        return 0
    except GateError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return exc.code
    except KeyboardInterrupt:
        print("[ABORT] 用户中断；已写入的账本不会回滚。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
