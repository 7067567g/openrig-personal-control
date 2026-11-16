# -*- coding: utf-8 -*-
"""模板分层回归：冻结原子轮型 + 基准模板 + 基准模板不可直接实例化。"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "templates" / "contracts"
BASELINES = ROOT / "templates" / "baseline"
CONTRACT_TYPES = [
    "strategy",
    "research",
    "diff",
    "architecture",
    "optimize",
    "verify",
    "audit",
]
REQUIRED_CONTRACT_HEADS = [
    "## purpose",
    "## requires",
    "## produces",
    "## mandatory_gates",
    "## hard_boundaries",
    "## budget_defaults",
    "## done",
    "## handoff",
]
REQUIRED_BASELINE_HEADS = [
    "## 1. 主攻方向",
    "## 2. 特点",
    "## 3. 默认管线",
    "## 5. 强制证据与 DoD",
    "## 6. 特化重点参考",
    "## 7. 实例化规则",
]


def test_contract_lock_is_frozen_and_passes():
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "contract_lock.py"), "check"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "atomic-contract-set@" in r.stdout


def test_all_atomic_contracts_exist_with_required_interface():
    assert (CONTRACTS / "VERSION").read_text(encoding="utf-8").strip()
    assert (CONTRACTS / "LOCK.json").is_file()
    for name in CONTRACT_TYPES:
        text = (CONTRACTS / name / "CONTRACT.md").read_text(encoding="utf-8")
        for head in REQUIRED_CONTRACT_HEADS:
            assert head in text, f"{name} 缺 {head}"


def test_baseline_registry_covers_dirs_and_has_required_sections():
    registry = json.loads((BASELINES / "REGISTRY.json").read_text(encoding="utf-8"))
    assert registry["directTemplate"] is False
    assert (
        registry["version"]
        == (BASELINES / "VERSION").read_text(encoding="utf-8").strip()
    )
    ids = {b["id"] for b in registry["baselines"]}
    dirs = {p.name for p in BASELINES.iterdir() if p.is_dir()}
    assert ids == dirs
    assert len(ids) == 9
    for item in registry["baselines"]:
        text = (BASELINES / item["id"] / "BASELINE.md").read_text(encoding="utf-8")
        for head in REQUIRED_BASELINE_HEADS:
            assert head in text, f"{item['id']} 缺 {head}"
        assert item["direction"] in text
        assert item["contracts"]


def test_issue_sync_is_specialized_adapter_not_baseline():
    """G-TPL：issue-sync 只以 specialized adapter 存在，baseline 不再提供该复合类型。"""
    assert not (BASELINES / "issue-sync").exists(), "baseline 不应再包含 issue-sync"
    spec = ROOT / "templates" / "specialized" / "issue-sync" / "SPEC.md"
    assert spec.is_file(), "缺 templates/specialized/issue-sync/SPEC.md"
    text = spec.read_text(encoding="utf-8")
    assert re.search(r"^baseline:\s*none — ", text, re.M), (
        "adapter 的 baseline 应写 none — 理由"
    )
    assert re.search(
        r"^contracts:\s*research@1\.0\.0, verify@1\.0\.0, audit@1\.0\.0$", text, re.M
    )
    registry = json.loads((BASELINES / "REGISTRY.json").read_text(encoding="utf-8"))
    assert "issue-sync" not in {b["id"] for b in registry["baselines"]}


def test_baseline_registry_tracks_base_master_and_preserves_maturity():
    """G-TPL/G-LOCK：注册表 baseMaster 跟随冻结母版版本；safe-cleanup 仍为 M3。"""
    import contract_lock

    registry = json.loads((BASELINES / "REGISTRY.json").read_text(encoding="utf-8"))
    assert registry["baseMaster"] == (
        f"{contract_lock.BASE_MASTER_ID}@{contract_lock.BASE_MASTER_VERSION}"
    )
    maturity = {b["id"]: b["maturity"] for b in registry["baselines"]}
    assert maturity["safe-cleanup"] == "M3"
    assert maturity["fix-wave"] == "M3"


def test_baseline_cannot_be_used_as_run_template(new_run):
    for i, target in enumerate([BASELINES, BASELINES / "fix-wave"]):
        with pytest.raises(SystemExit):
            new_run(run_id=f"t-baseline-reject-{i}", template=str(target))


def test_contracts_cannot_be_used_as_run_template(new_run):
    for i, target in enumerate([CONTRACTS, CONTRACTS / "research"]):
        with pytest.raises(SystemExit):
            new_run(run_id=f"t-contract-reject-{i}", template=str(target))


def test_hdrive_template_has_both_execution_backends_and_no_posix_only_copy():
    base = ROOT / "templates" / "specialized" / "h-drive-cleanup"
    readme = (base / "README.md").read_text(encoding="utf-8")
    spec = (base / "SPEC.md").read_text(encoding="utf-8")
    assert "scripts/hdrive_gate.py" in readme and "scripts/windows/hgate.py" in readme
    assert "### 4.0 执行后端选择" in spec
    assert "scripts/hdrive_gate.py" in spec and "scripts/windows/hgate.py" in spec
    assert "当前版本只接受挂载后的 POSIX 路径" not in spec
    assert "Windows 版应采用 PowerShell move-only 门控" not in readme


def test_specialized_baseline_map_matches_every_spec_section_zero():
    """21+ 领域模板的 SPEC §0 必须与 BASELINE-MAP 逐项一致（P0 回填门）。"""
    specialized = ROOT / "templates" / "specialized"
    map_text = (specialized / "BASELINE-MAP.md").read_text(encoding="utf-8")
    names = {
        p.name
        for p in specialized.iterdir()
        if p.is_dir() and (p / "SPEC.md").is_file()
    }
    rows: dict[str, tuple[str, str]] = {}
    for line in map_text.splitlines():
        if not line.startswith("| `"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        name = cells[0].strip("`")
        base = cells[1].strip("`")
        contracts = cells[2]
        rows[name] = (base, contracts)
    assert names == set(rows), (
        f"SPEC 目录与 BASELINE-MAP 不一致: "
        f"missing_map={sorted(names - set(rows))}, orphan_map={sorted(set(rows) - names)}"
    )
    assert len(names) >= 22
    for name in sorted(names):
        text = (specialized / name / "SPEC.md").read_text(encoding="utf-8")
        b = re.search(r"^baseline:\s*(.+)$", text, re.M)
        c = re.search(r"^contracts:\s*(.+)$", text, re.M)
        assert b, f"{name} 缺 SPEC §0 baseline: 行"
        assert c, f"{name} 缺 SPEC §0 contracts: 行"
        base_raw, contracts_raw = rows[name]
        actual_base = b.group(1).strip()
        assert "`" not in actual_base and "（" not in actual_base, (
            f"{name} baseline 行含说明文字/反引号，应只保留机器可读 id：{actual_base!r}"
        )
        if base_raw.startswith("composite/"):
            assert re.fullmatch(re.escape(base_raw) + r"@\d+\.\d+\.\d+", actual_base), (
                f"{name} baseline 与映射不一致: {actual_base!r}"
            )
        elif base_raw.startswith("none"):
            assert actual_base.startswith("none — "), f"{name} baseline=none 需写理由"
        else:
            assert actual_base == base_raw
        expected_contracts = ", ".join(
            x.strip() + "@1.0.0" for x in contracts_raw.split(",") if x.strip()
        )
        assert c.group(1).strip() == expected_contracts, (
            f"{name} contracts 应为 {expected_contracts!r}，实际 {c.group(1)!r}"
        )
