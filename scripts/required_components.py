#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""required_components.py — workflow-group 必需组件检查（R06）。

用法:
  python3 scripts/required_components.py [--root ROOT] [--json]

供 `openrig_preflight.py` 与 `wf.py doctor` 复用：任一 `required=True` 的组件
不可用即视为失败，且必须给出可执行的安装/修复提示（install_hint）。

返回结构（每项）:
  {id, group, required, ok, detail, install_hint}

组:
  machine  — Python >= 3.12 / openpyxl / pytest
  control  — PROJECT / DECISIONS / STATUS-Round-n / ISSUES.xlsx 模板
  openrig  — render_master.py / tools/openrig_bridge.py / PREFLIGHT.md / ENTRYPOINTS.md
  runtime  — rig CLI / 产品 openrig-teardown.py（required=False，仅告警）
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # workflow-group/

# 统一的依赖安装提示：在 KB 仓库根执行即可。
INSTALL_DEPS_HINT = (
    "workflow-group/.venv/bin/pip install -r workflow-group/requirements-dev.txt"
)
ACTIVATE_HINT = "source workflow-group/.venv/bin/activate"
PYTHON_HINT = (
    "使用 workflow-group/.venv/bin/python（需 Python >= 3.12），"
    "或 python3.12 -m venv workflow-group/.venv 后重装 requirements-dev.txt"
)
OPENRIG_MASTER = Path("templates") / "specialized" / "openrig-workflow-master"
TEARDOWN_GUARD = (
    Path("deepseek-项目") / "10-openrig-deepseek" / "scripts" / "openrig-teardown.py"
)


def _has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _component(
    cid: str,
    group: str,
    ok: bool,
    detail: str,
    install_hint: str = "",
    required: bool = True,
) -> dict:
    return {
        "id": cid,
        "group": group,
        "required": required,
        "ok": bool(ok),
        "detail": detail,
        "install_hint": install_hint,
    }


def _file_component(cid: str, group: str, path: Path, hint: str) -> dict:
    return _component(
        cid,
        group,
        path.is_file(),
        f"{path} {'存在' if path.is_file() else '缺失'}",
        "" if path.is_file() else hint,
    )


def check_components(root: Path | str | None = None) -> list[dict]:
    """检查 workflow-group 运行所需组件；root 为 workflow-group 根目录。"""
    root = Path(root).expanduser().resolve() if root else ROOT
    out: list[dict] = []

    # ---------------- machine ----------------
    py_ok = sys.version_info >= (3, 12)
    out.append(
        _component(
            "machine.python",
            "machine",
            py_ok,
            f"Python {platform.python_version()}（需 >= 3.12）",
            "" if py_ok else PYTHON_HINT,
        )
    )

    openpyxl_ok = _has_module("openpyxl")
    openpyxl_detail = "openpyxl 可用"
    if openpyxl_ok:
        try:
            import openpyxl  # noqa: F401

            openpyxl_detail = f"openpyxl {getattr(openpyxl, '__version__', '?')} 可用"
        except Exception:  # pragma: no cover - 健康环境不会走到
            pass
    else:
        openpyxl_detail = "缺 openpyxl：ISSUES.xlsx 无法读写，仅能走 JSONL 降级"
    out.append(
        _component(
            "machine.openpyxl",
            "machine",
            openpyxl_ok,
            openpyxl_detail,
            "" if openpyxl_ok else f"{ACTIVATE_HINT} 或 {INSTALL_DEPS_HINT}",
        )
    )

    pytest_ok = _has_module("pytest")
    out.append(
        _component(
            "machine.pytest",
            "machine",
            pytest_ok,
            "pytest 可用" if pytest_ok else "缺 pytest：无法运行验收测试",
            "" if pytest_ok else f"{ACTIVATE_HINT} 或 {INSTALL_DEPS_HINT}",
        )
    )

    # ---------------- control ----------------
    tmpl = root / "templates"
    out.append(
        _file_component(
            "control.project",
            "control",
            tmpl / "PROJECT.md",
            "恢复 workflow-group/templates/PROJECT.md（控制面四件套模板）",
        )
    )
    out.append(
        _file_component(
            "control.decisions",
            "control",
            tmpl / "DECISIONS.md",
            "恢复 workflow-group/templates/DECISIONS.md",
        )
    )
    status_tmpl = sorted(tmpl.glob("STATUS-Round-*.md"))
    out.append(
        _component(
            "control.status",
            "control",
            bool(status_tmpl),
            f"{status_tmpl[0]} 存在" if status_tmpl else f"{tmpl}/STATUS-Round-*.md 缺失",
            "" if status_tmpl else "恢复 workflow-group/templates/STATUS-Round-n.md",
        )
    )
    out.append(
        _file_component(
            "control.issues",
            "control",
            tmpl / "ISSUES.xlsx",
            "恢复 workflow-group/templates/ISSUES.xlsx",
        )
    )

    # ---------------- openrig ----------------
    master = root / OPENRIG_MASTER
    out.append(
        _file_component(
            "openrig.render_master",
            "openrig",
            master / "render_master.py",
            f"恢复 {OPENRIG_MASTER}/render_master.py（run 渲染入口）",
        )
    )
    out.append(
        _file_component(
            "openrig.bridge",
            "openrig",
            master / "tools" / "openrig_bridge.py",
            f"恢复 {OPENRIG_MASTER}/tools/openrig_bridge.py",
        )
    )
    out.append(
        _file_component(
            "openrig.preflight",
            "openrig",
            master / "PREFLIGHT.md",
            f"恢复 {OPENRIG_MASTER}/PREFLIGHT.md",
        )
    )
    out.append(
        _file_component(
            "openrig.entrypoints",
            "openrig",
            master / "ENTRYPOINTS.md",
            f"恢复 {OPENRIG_MASTER}/ENTRYPOINTS.md",
        )
    )

    # ---------------- runtime（warn only） ----------------
    rig_path = shutil.which("rig")
    out.append(
        _component(
            "runtime.rig",
            "runtime",
            bool(rig_path),
            f"rig={rig_path}" if rig_path else "PATH 中找不到 rig CLI",
            "" if rig_path else "安装 @openrig-local/cli 并确认 `rig` 在 PATH 中",
            required=False,
        )
    )
    guard = Path(
        os.environ.get("OPENRIG_TEARDOWN_GUARD")
        or (root.parent.parent / TEARDOWN_GUARD)
    )
    out.append(
        _component(
            "runtime.teardown_guard",
            "runtime",
            guard.is_file(),
            f"teardown guard {guard} {'存在' if guard.is_file() else '缺失'}",
            "" if guard.is_file() else "安装产品仓 10-openrig-deepseek 或用 OPENRIG_TEARDOWN_GUARD 指定",
            required=False,
        )
    )

    return out


def failures(components: list[dict]) -> list[dict]:
    """只返回 required 且失败的组件。"""
    return [c for c in components if c.get("required") and not c.get("ok")]


def all_required_ok(components: list[dict]) -> bool:
    return not failures(components)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    comps = check_components(args.root or ROOT)
    ok = all_required_ok(comps)
    if args.json:
        print(json.dumps({"ok": ok, "components": comps}, ensure_ascii=False, indent=2))
    else:
        for c in comps:
            print(f"[{'OK' if c['ok'] else ('FAIL' if c['required'] else 'WARN')}] {c['id']}: {c['detail']}")
            if not c["ok"] and c["install_hint"]:
                print(f"       hint: {c['install_hint']}")
        print(f"结果: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
