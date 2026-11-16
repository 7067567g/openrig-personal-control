#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WSL 调 Windows move-only 门控的薄包装。

示例：
  python3 scripts/windows/hgate.py status --run-root /mnt/c/Users/Administrator/h-cleanup/<run> --json
  python3 scripts/windows/hgate.py init --run-root /mnt/c/... --root 'H:\\' \
    --storage-root 'H:\\_整理收纳' --pending-root 'H:\\_整理收纳\\90_待确认' \
    --protected-manifest kickoff/h-drive-windows-protected.json \
    --safety-reviewer safety-a1 --human-approver user

只做参数路径转换与 PowerShell 调用；安全逻辑在 hdrive_move_gate.ps1。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # workflow-group/
PS1 = ROOT / "scripts" / "windows" / "hdrive_move_gate.ps1"
POWERSHELL = Path("/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")

PATH_VALUE_FLAGS = {
    "--run-root",
    "--action-file",
    "--batch-file",
    "--protected-manifest",
}
WINDOWS_PATH_VALUE_FLAGS = {
    "--root",
    "--storage-root",
    "--pending-root",
}
FLAG_MAP = {
    "--run-root": "-RunRoot",
    "--root": "-Root",
    "--storage-root": "-StorageRoot",
    "--pending-root": "-PendingRoot",
    "--protected-manifest": "-ProtectedManifest",
    "--safety-reviewer": "-SafetyReviewer",
    "--human-approver": "-HumanApprover",
    "--action-file": "-ActionFile",
    "--batch-file": "-BatchFile",
    "--agent": "-Agent",
    "--action": "-Action",
    "--reviewer": "-Reviewer",
    "--verdict": "-Verdict",
    "--digest": "-Digest",
    "--reason": "-Reason",
    "--evidence": "-Evidence",
    "--approver": "-Approver",
    "--allow-root-storage": "-AllowRootStorage",
    "--json": "-Json",
}


def wsl_to_windows(path: str) -> str:
    """把 WSL 路径转成 Windows 路径；已是 Windows 路径则原样返回。"""
    p = path.strip()
    if len(p) >= 3 and p[1] == ":" and p[2] in "\\/":
        return p
    if not p.startswith("/") and not p.startswith("\\\\"):
        p = str(Path(path).resolve())
    r = subprocess.run(["wslpath", "-w", p], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"wslpath 失败: {p}: {r.stderr.strip()}")
    return r.stdout.strip()


def normalize_args(argv: list[str]) -> list[str]:
    if not argv:
        return argv
    if argv[0].startswith("-"):
        raise SystemExit("第一个参数必须是命令: init|propose|gate|review|human-approve|run|status")
    out: list[str] = ["-Command", argv[0]]
    convert_next = False
    for token in argv[1:]:
        if convert_next:
            out.append(wsl_to_windows(token))
            convert_next = False
            continue
        if token in PATH_VALUE_FLAGS:
            out.append(FLAG_MAP[token])
            convert_next = True
            continue
        if token in WINDOWS_PATH_VALUE_FLAGS:
            out.append(FLAG_MAP[token])
            continue
        if token in FLAG_MAP:
            out.append(FLAG_MAP[token])
            continue
        out.append(token)
    return out


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 2
    if argv[0] in {"-h", "--help"}:
        print(__doc__)
        return 0
    if not POWERSHELL.is_file():
        print(f"[ERROR] PowerShell 不存在: {POWERSHELL}", file=sys.stderr)
        return 2
    if not PS1.is_file():
        print(f"[ERROR] 门控脚本不存在: {PS1}", file=sys.stderr)
        return 2

    ps1_win = wsl_to_windows(str(PS1))
    converted = normalize_args(argv)
    cmd = [
        str(POWERSHELL),
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        ps1_win,
        *converted,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if r.stdout:
        sys.stdout.write(r.stdout)
    if r.stderr:
        sys.stderr.write(r.stderr)
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())
