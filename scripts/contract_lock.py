#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""冻结原子轮型清单的生成与核验。

用法：
  python3 scripts/contract_lock.py check      # 核验 LOCK.json 与当前文件一致（rc 0/1）
  python3 scripts/contract_lock.py write --force
                                             # 明确重新冻结后写 LOCK.json

冻结对象：
1. 基础母版：WORKFLOW.md、roles/common-contract.md、四件套母版等；
2. LOCK.json 记录的 contract-set 版本；
3. templates/contracts/**/*.md 与 VERSION。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "templates" / "contracts"
LOCK = CONTRACTS / "LOCK.json"
VERSION_FILE = CONTRACTS / "VERSION"

BASE_MASTER_ID = "workflow-group-base"
BASE_MASTER_VERSION = "1.2.1"
BASE_MASTER_FILES = [
    "WORKFLOW.md",
    "roles/common-contract.md",
    "roles/MAIN.md",
    "roles/PMO.md",
    "roles/TDO.md",
    "roles/QA.md",
    "roles/SAFETY.md",
    "templates/PROJECT.md",
    "templates/DECISIONS.md",
    "templates/STATUS-Round-n.md",
    "templates/ISSUES.xlsx",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_version() -> str:
    if not VERSION_FILE.is_file():
        raise SystemExit(f"[ERROR] 缺版本文件: {VERSION_FILE}")
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not version:
        raise SystemExit("[ERROR] templates/contracts/VERSION 为空")
    return version


def expected_lock() -> dict:
    version = read_version()
    missing = [rel for rel in BASE_MASTER_FILES if not (ROOT / rel).is_file()]
    if missing:
        raise SystemExit(f"[ERROR] 基础母版文件缺失: {missing}")
    contract_files = sorted(
        str(p.relative_to(CONTRACTS))
        for p in CONTRACTS.rglob("*")
        if p.is_file()
        and p.name != "LOCK.json"
        and (p.suffix == ".md" or p.name == "VERSION")
    )
    return {
        "lockVersion": 1,
        "baseMaster": {
            "id": BASE_MASTER_ID,
            "version": BASE_MASTER_VERSION,
            "files": {rel: sha256_file(ROOT / rel) for rel in BASE_MASTER_FILES},
        },
        "contractSet": {
            "version": version,
            "files": {rel: sha256_file(CONTRACTS / rel) for rel in contract_files},
        },
    }


def diff_lock(expected: dict, actual: dict) -> list[str]:
    problems: list[str] = []
    if actual.get("lockVersion") != expected.get("lockVersion"):
        problems.append(
            f"lockVersion: {actual.get('lockVersion')!r} != {expected.get('lockVersion')!r}"
        )
    for section in ("baseMaster", "contractSet"):
        exp = expected[section]
        act = actual.get(section, {})
        for key in ("id", "version"):
            if key in exp and act.get(key) != exp[key]:
                problems.append(f"{section}.{key}: {act.get(key)!r} != {exp[key]!r}")
        exp_files = exp["files"]
        act_files = act.get("files", {})
        only_actual = sorted(set(act_files) - set(exp_files))
        only_expected = sorted(set(exp_files) - set(act_files))
        if only_actual:
            problems.append(f"{section}: LOCK 多出 {only_actual}")
        if only_expected:
            problems.append(f"{section}: LOCK 缺少 {only_expected}")
        for rel in sorted(set(exp_files) & set(act_files)):
            if exp_files[rel] != act_files[rel]:
                problems.append(f"{section}.{rel}: hash drift")
    return problems


def cmd_check() -> int:
    if not LOCK.is_file():
        print(
            f"[ERROR] 缺冻结清单: {LOCK}（运行 write --force 首次生成）",
            file=sys.stderr,
        )
        return 1
    try:
        actual = json.loads(LOCK.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[ERROR] LOCK.json 损坏: {exc}", file=sys.stderr)
        return 1
    expected = expected_lock()
    problems = diff_lock(expected, actual)
    if problems:
        print("[FAIL] 原子轮型/基础母版已漂移，必须按 BASE-MASTER.md §4 重新冻结：")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(
        f"[OK] 冻结一致：{BASE_MASTER_ID}@{BASE_MASTER_VERSION} + "
        f"atomic-contract-set@{expected['contractSet']['version']} "
        f"({len(expected['contractSet']['files'])} files)"
    )
    return 0


def cmd_write(force: bool) -> int:
    if LOCK.exists() and not force:
        print(
            f"[ERROR] {LOCK} 已存在；冻结变更必须显式加 --force，并先更新 VERSION。",
            file=sys.stderr,
        )
        return 1
    data = expected_lock()
    LOCK.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"[OK] 写入 {LOCK}: {BASE_MASTER_ID}@{BASE_MASTER_VERSION}, "
        f"contract-set@{data['contractSet']['version']}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="冻结原子轮型锁")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="核验 LOCK.json")
    w = sub.add_parser("write", help="重新生成 LOCK.json")
    w.add_argument("--force", action="store_true", help="覆盖已有 LOCK.json")
    args = p.parse_args(argv)
    if args.cmd == "check":
        return cmd_check()
    if args.cmd == "write":
        return cmd_write(args.force)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
