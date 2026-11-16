# -*- coding: utf-8 -*-
"""Packet A · R06 `required_components.py` 单测（含负向）。

覆盖 TASK §2.5：
  - 正常环境 required 全 ok
  - 临时 root 缺模板 → 对应 required=false
  - 缺 openpyxl 时 detail/install_hint 给出可执行安装提示（monkeypatch 模拟）
"""

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import required_components as rc  # noqa: E402


def _by_id(comps):
    return {c["id"]: c for c in comps}


def test_real_root_required_components_all_ok():
    """正例：真实 workflow-group 根下 required 组件全部可用。"""
    comps = rc.check_components(rc.ROOT)
    assert rc.all_required_ok(comps), rc.failures(comps)
    ids = _by_id(comps)
    assert ids["machine.python"]["ok"] is True
    assert ids["machine.openpyxl"]["ok"] is True
    assert ids["machine.pytest"]["ok"] is True
    assert ids["openrig.preflight"]["ok"] is True
    # runtime 只告警，不参与 required 判定
    assert ids["runtime.rig"]["required"] is False


def test_missing_templates_make_required_components_fail(tmp_path):
    """负向：临时 root 没有模板 → control/openrig required 全部 false 且带 hint。"""
    comps = rc.check_components(tmp_path / "empty-workflow-group")
    bad = {c["id"] for c in rc.failures(comps)}
    assert {"control.project", "control.decisions", "control.status", "control.issues"} <= bad
    assert {"openrig.render_master", "openrig.bridge", "openrig.preflight", "openrig.entrypoints"} <= bad
    for c in rc.failures(comps):
        assert c["ok"] is False
        assert c["install_hint"], f"{c['id']} 缺 install_hint"


def test_missing_openpyxl_detail_and_install_hint(tmp_path, monkeypatch):
    """负向：模拟缺 openpyxl → detail 说明后果，install_hint 可执行。"""
    real = rc._has_module

    def fake_has_module(name):
        return False if name == "openpyxl" else real(name)

    monkeypatch.setattr(rc, "_has_module", fake_has_module)
    comps = _by_id(rc.check_components(rc.ROOT))
    item = comps["machine.openpyxl"]
    assert item["required"] is True
    assert item["ok"] is False
    assert "openpyxl" in item["detail"]
    assert "pip install -r workflow-group/requirements-dev.txt" in item["install_hint"]


def test_component_shape_is_stable():
    for c in rc.check_components(rc.ROOT):
        assert set(c) == {"id", "group", "required", "ok", "detail", "install_hint"}
        assert c["group"] in {"machine", "control", "openrig", "runtime"}
