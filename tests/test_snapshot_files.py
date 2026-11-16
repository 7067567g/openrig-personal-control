# -*- coding: utf-8 -*-
"""Packet A · W4 `snapshot_files.py` 单测（含负向）。

覆盖 TASK §1 / plan §5：
  - 临时 untracked 文件 before/after 两次均记录且 sha256 可区分
  - 缺失文件 → exists:false，不抛异常
  - 目录递归、去重、只读（除 --out 外不产生文件）
"""

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import snapshot_files as snap  # noqa: E402


def _read(out: Path) -> dict:
    return json.loads(out.read_text(encoding="utf-8"))


def test_before_after_same_file_tracks_hash_change(tmp_path):
    target = tmp_path / "untracked.txt"
    target.write_text("v1\n", encoding="utf-8")
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"

    assert snap.main(["--out", str(before), "--label", "before", "--path", str(target)]) == 0
    target.write_text("v2 changed\n", encoding="utf-8")
    assert snap.main(["--out", str(after), "--label", "after", "--path", str(target)]) == 0

    b = _read(before)["files"][0]
    a = _read(after)["files"][0]
    assert b["exists"] is True and a["exists"] is True
    assert b["label"] == "before" and a["label"] == "after"
    assert b["sha256"] != a["sha256"]
    assert b["bytes"] == 3 and a["bytes"] == len("v2 changed\n".encode())
    assert b["capturedAt"] and b["mtime"]


def test_missing_file_is_recorded_not_raised(tmp_path):
    out = tmp_path / "snap.json"
    missing = tmp_path / "nope.txt"
    assert snap.main(["--out", str(out), "--label", "before", "--path", str(missing)]) == 0
    report = _read(out)
    entry = report["files"][0]
    assert entry["exists"] is False
    assert entry["sha256"] is None and entry["bytes"] is None
    assert entry["label"] == "before"
    assert report["summary"] == {"total": 1, "present": 0, "missing": 1}


def test_directory_is_recursive_and_deduplicated(tmp_path):
    d = tmp_path / "tree"
    (d / "sub").mkdir(parents=True)
    (d / "a.txt").write_text("a", encoding="utf-8")
    (d / "sub" / "b.txt").write_text("b", encoding="utf-8")
    (d / ".git").mkdir()
    (d / ".git" / "HEAD").write_text("ref\n", encoding="utf-8")
    out = tmp_path / "snap.json"

    assert snap.main(["--out", str(out), "--label", "after", "--path", str(d)]) == 0
    paths = [Path(e["path"]).name for e in _read(out)["files"]]
    assert paths == ["a.txt", "b.txt"]  # .git 跳过，顺序稳定

    # 同一文件被目录与显式路径同时指定 → 只记一次
    assert (
        snap.main(
            ["--out", str(out), "--label", "after", "--path", str(d), "--path", str(d / "a.txt")]
        )
        == 0
    )
    assert len(_read(out)["files"]) == 2


def test_snapshot_is_readonly_regarding_targets(tmp_path):
    target = tmp_path / "keep.txt"
    target.write_text("keep\n", encoding="utf-8")
    before = target.read_bytes()
    out = tmp_path / "snap.json"
    assert snap.main(["--out", str(out), "--label", "before", "--path", str(target)]) == 0
    assert target.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["keep.txt", "snap.json"]


def test_label_must_be_before_or_after(tmp_path):
    with pytest.raises(SystemExit):
        snap.main(["--out", str(tmp_path / "x.json"), "--label", "middle", "--path", "."])
