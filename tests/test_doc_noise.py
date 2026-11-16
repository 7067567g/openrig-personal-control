# -*- coding: utf-8 -*-
"""文档降噪回归（G-DOC / G-TEST）。

锁定两类事实：

1. `WORKFLOW.md §11` 是退役术语的唯一规范入口；`roles/*.md` 与 `AGENTS.md` 中
   退役术语出现次数为 0（口径同 `WORKFLOW.md §11`）。
2. 降噪只删重复声明，不删操作语义：不建游离台账、无主项进 ISSUES/STATUS 指针、
   去向必须闭合。

口径：`SO` / `Specialist Office` / `Specialist Officer` / `TERMINAL` /
`执行专员` / `领域专员` / `L1`–`L3`。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / "WORKFLOW.md"
ROLES = ROOT / "roles"
AGENTS = ROOT / "AGENTS.md"


def _token(literal: str) -> re.Pattern[str]:
    """ASCII 词边界：中文/标点相邻仍算命中（`不设SO实体` 不能漏），

    `ISO`、`SOUL`、`L10` 这类更长 token 不误报。
    """
    return re.compile(rf"(?<![A-Za-z0-9_]){re.escape(literal)}(?![A-Za-z0-9_])")


RETIRED_PATTERNS: dict[str, re.Pattern[str]] = {
    "SO": _token("SO"),
    "Specialist Office": re.compile(r"Specialist\s+Office\b"),
    "Specialist Officer": re.compile(r"Specialist\s+Officer\b"),
    "TERMINAL": _token("TERMINAL"),
    "执行专员": re.compile("执行专员"),
    "领域专员": re.compile("领域专员"),
    "L1–L3": re.compile(r"(?<![A-Za-z0-9_])L[123](?![A-Za-z0-9_])"),
}


def _retired_hits(path: Path) -> list[str]:
    hits: list[str] = []
    text = path.read_text(encoding="utf-8")
    for lineno, line in enumerate(text.splitlines(), 1):
        for name, pattern in RETIRED_PATTERNS.items():
            if pattern.search(line):
                hits.append(
                    f"{path.relative_to(ROOT)}:{lineno}: [{name}] {line.strip()[:100]}"
                )
    return hits


def test_roles_and_agents_have_zero_retired_terms():
    """G-DOC：角色手册与 AGENTS.md 不再复述退役术语。"""
    files = sorted(ROLES.glob("*.md")) + [AGENTS]
    assert len(files) >= 7, f"角色手册数量异常：{files}"
    hits = [hit for path in files for hit in _retired_hits(path)]
    assert not hits, (
        "退役术语只允许出现在 WORKFLOW.md §11（术语表单一来源）：\n" + "\n".join(hits)
    )


def test_roles_and_agents_do_not_repeat_retired_banner():
    """角色手册不复述历史禁令本身；规范来源固定为 WORKFLOW.md §11。"""
    offenders = [
        str(path.relative_to(ROOT))
        for path in sorted(ROLES.glob("*.md")) + [AGENTS]
        if "退役术语" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, f"以下文件重复了退役术语声明：{offenders}"


def test_workflow_body_excluding_glossary_has_no_retired_terms():
    """§2 等正文改用通用表述；退役术语字面只允许留在 §11 术语表。"""
    text = WORKFLOW.read_text(encoding="utf-8")
    marker = "## 11. 术语与用字"
    assert marker in text
    body = text.split(marker, 1)[0]
    hits: list[str] = []
    for lineno, line in enumerate(body.splitlines(), 1):
        for name, pattern in RETIRED_PATTERNS.items():
            if pattern.search(line):
                hits.append(f"WORKFLOW.md:{lineno}: [{name}] {line.strip()[:100]}")
    assert not hits, (
        "WORKFLOW.md §11 之前不得出现退役术语字面（§11 是唯一 canonical 术语表）：\n"
        + "\n".join(hits)
    )


def test_workflow_glossary_is_the_single_source():
    """WORKFLOW.md §11 保留退役术语登记，且末节即术语表。"""
    text = WORKFLOW.read_text(encoding="utf-8")
    marker = "## 11. 术语与用字"
    assert marker in text, "WORKFLOW.md 缺少 §11 术语与用字"
    section = text.split(marker, 1)[1]
    assert "唯一来源" in section
    for literal in (
        "SO",
        "Specialist Office",
        "Specialist Officer",
        "执行专员",
        "领域专员",
        "L1/L2/L3",
        "L1–L3",
    ):
        assert literal in section, f"§11 应保留退役术语登记：{literal}"
    assert "已退役" in section


OPERATIONAL_SEMANTICS: dict[str, tuple[str, ...]] = {
    "roles/common-contract.md": ("不收游离台账", "ISSUES", "去向", "最晚复核轮"),
    "roles/PMO.md": ("游离台账", "去向核对", "不新增结构"),
    "roles/TDO.md": ("不建游离台账", "指针", "关闭收口规则"),
    "roles/QA.md": ("不建游离台账", "ISSUES"),
    "roles/delegation-briefs.md": ("游离台账", "指针"),
    "roles/SAFETY.md": ("独立双人控制角色",),
    "AGENTS.md": ("关闭收口规则", "跨轮承接规则", "游离台账"),
}


def test_operational_semantics_are_retained():
    """降噪不得删掉收口语义：不建游离台账 + 无主项指针 + 去向闭合。"""
    missing: list[str] = []
    for rel, phrases in OPERATIONAL_SEMANTICS.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        for phrase in phrases:
            if phrase not in text:
                missing.append(f"{rel} 缺少 {phrase!r}")
    assert not missing, "文档降噪删掉了操作语义：\n" + "\n".join(missing)
