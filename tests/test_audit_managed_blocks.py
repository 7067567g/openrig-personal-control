# -*- coding: utf-8 -*-
"""Packet B · R10 `audit_managed_blocks.py` 单测（含负向）。

覆盖 TASK §2 / plan §4.3：
  - 临时文件含 2 个块 → JSON 正确（id/startLine/endLine/kind/ownerRig）
  - 无块 → summary.blocks == 0，rc0
  - orphan managed block → 默认 rc0；--strict rc1
  - preflight 块不算 orphan；`rig:<name>` 前缀可推断 ownerRig
  - 未闭合块 → 告警，--strict rc1
"""

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import audit_managed_blocks as am  # noqa: E402

BEGIN = "<!-- BEGIN OpenRig MANAGED BLOCK: {} -->"
END = "<!-- END OpenRig MANAGED BLOCK: {} -->"


def _write(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def test_two_blocks_reported_with_lines(tmp_path, capsys):
    body = "\n".join(
        [
            "# doc",  # 1
            BEGIN.format("CULTURE-default.md"),  # 2
            "body a",  # 3
            END.format("CULTURE-default.md"),  # 4
            "",  # 5
            BEGIN.format("rig:alpha/team.md"),  # 6
            "body b",  # 7
            END.format("rig:alpha/team.md"),  # 8
        ]
    )
    f = _write(tmp_path, "AGENTS.md", body)
    rc = am.main(["--path", str(f), "--json"])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    blocks = report["files"][0]["blocks"]
    assert [(b["id"], b["startLine"], b["endLine"]) for b in blocks] == [
        ("CULTURE-default.md", 2, 4),
        ("rig:alpha/team.md", 6, 8),
    ]
    assert [b["kind"] for b in blocks] == ["managed", "managed"]
    assert [b["ownerRig"] for b in blocks] == [None, "alpha"]
    assert report["summary"]["blocks"] == 2
    assert report["summary"]["orphanManaged"] == 1


def test_no_blocks_summary_is_zero(tmp_path, capsys):
    f = _write(tmp_path, "plain.md", "# nothing managed here\n\ntext\n")
    rc = am.main(["--path", str(f), "--json"])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["summary"]["blocks"] == 0
    assert report["summary"]["files"] == 1
    assert report["summary"]["filesWithBlocks"] == 0
    assert report["summary"]["orphanManaged"] == 0
    assert report["files"][0]["blocks"] == []


def test_orphan_default_rc0_strict_rc1(tmp_path, capsys):
    f = _write(tmp_path, "AGENTS.md", f"{BEGIN.format('no-owner.md')}\nx\n{END.format('no-owner.md')}\n")
    assert am.main(["--path", str(f), "--json"]) == 0
    capsys.readouterr()
    assert am.main(["--path", str(f), "--strict", "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["strict"]["enabled"] is True
    assert len(report["strict"]["failures"]) == 1
    assert "no ownerRig" in report["strict"]["failures"][0]


def test_strict_passes_for_owned_blocks(tmp_path, capsys):
    body = "\n".join(
        [
            BEGIN.format("rig:alpha/team.md"),
            "x",
            END.format("rig:alpha/team.md"),
            BEGIN.format("rig:beta-culture"),
            "y",
            END.format("rig:beta-culture"),
        ]
    )
    f = _write(tmp_path, "AGENTS.md", body)
    assert am.main(["--path", str(f), "--strict", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert [b["ownerRig"] for b in report["files"][0]["blocks"]] == ["alpha", "beta-culture"]
    assert report["strict"]["failures"] == []


def test_preflight_block_is_not_an_orphan(tmp_path, capsys):
    body = "\n".join(
        [
            "<!-- BEGIN OPENRIG-PREFLIGHT (managed) -->",
            "preflight",
            "<!-- END OPENRIG-PREFLIGHT (managed) -->",
        ]
    )
    f = _write(tmp_path, "AGENTS.md", body)
    assert am.main(["--path", str(f), "--strict", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    block = report["files"][0]["blocks"][0]
    assert block["kind"] == "preflight"
    assert report["summary"]["orphanManaged"] == 0


def test_unterminated_block_warns_and_fails_strict(tmp_path, capsys):
    f = _write(tmp_path, "AGENTS.md", f"{BEGIN.format('rig:alpha/x')}\nno end\n")
    assert am.main(["--path", str(f), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    block = report["files"][0]["blocks"][0]
    assert block["endLine"] is None
    assert block["warning"] == "unterminated-block"
    assert report["summary"]["unterminated"] == 1
    assert am.main(["--path", str(f), "--strict"]) == 1


def test_directory_is_recursive_and_deduplicated(tmp_path, capsys):
    d = tmp_path / "tree"
    (d / "sub").mkdir(parents=True)
    _write(d, "a.md", f"{BEGIN.format('rig:alpha/a')}\n1\n{END.format('rig:alpha/a')}\n")
    _write(d / "sub", "b.md", f"{BEGIN.format('rig:alpha/b')}\n2\n{END.format('rig:alpha/b')}\n")
    _write(d / "sub", "plain.md", "nothing\n")
    rc = am.main(["--path", str(d), "--path", str(d / "a.md"), "--json"])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["summary"]["files"] == 3
    assert report["summary"]["filesWithBlocks"] == 2
    assert report["summary"]["blocks"] == 2


def test_legacy_rigged_namespace_is_reported(tmp_path, capsys):
    f = _write(
        tmp_path,
        "AGENTS.md",
        "<!-- BEGIN RIGGED MANAGED BLOCK: rig:alpha/old.md -->\nx\n"
        "<!-- END RIGGED MANAGED BLOCK: rig:alpha/old.md -->\n",
    )
    am.main(["--path", str(f), "--json"])
    block = json.loads(capsys.readouterr().out)["files"][0]["blocks"][0]
    assert block["kind"] == "managed"
    assert block["ownerRig"] == "alpha"
    assert block["warning"] == "legacy-rigged-namespace"
