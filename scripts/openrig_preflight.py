#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenRig / workflow-group agent preflight.

Usage (agent reads JSON; human can read markdown):
  python3 scripts/openrig_preflight.py --json
  python3 scripts/openrig_preflight.py --run-id X --rig Y --seat a@Y \
    --run-dir .../runs/X --gov-dir .../workspace --job <jobId> --workspace .../workspace --json

It prints the curated preflight, lists reference templates, injects a managed
block into <workspace>/AGENTS.md, and registers the run in the read-only monitor
target file (starting yueyue-monitor.service when available).

Order is fail-closed and side-effect free until the read-only pre-check passes:
`preflight_file` / `required_components` / `run_context` / `run_docs` first; a
required failure returns immediately without touching AGENTS.md, target.json or
systemd. Only then are `inject_agents` and `register_monitor` executed, followed
by the workspace block check.

`ok` is fail-closed: it is true only when every required check passes. `--advisory`
keeps the old "informational" exit code (rc=0) but still reports `ok:false`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import required_components

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "templates" / "specialized" / "openrig-workflow-master" / "PREFLIGHT.md"
# Monitor target resolution, in order of specificity. Nothing machine-specific is
# baked in: an explicit file wins, then a dashboard directory from the
# environment, then a per-user default under $HOME.
_EXPLICIT_TARGET = os.environ.get("YUEYUE_MONITOR_TARGETS") or os.environ.get("OPENRIG_MONITOR_TARGETS")
_DASHBOARD_DIR = os.environ.get("OPENRIG_DASHBOARD") or os.environ.get("YUEYUE_DASHBOARD")
DEFAULT_DASHBOARD = Path(_DASHBOARD_DIR).expanduser() if _DASHBOARD_DIR else None
if _EXPLICIT_TARGET:
    TARGET_FILE = Path(_EXPLICIT_TARGET).expanduser()
    TARGET_FILE_SOURCE = "env:YUEYUE_MONITOR_TARGETS"
elif DEFAULT_DASHBOARD is not None:
    TARGET_FILE = DEFAULT_DASHBOARD / "target.json"
    TARGET_FILE_SOURCE = "env:dashboard"
else:
    TARGET_FILE = Path.home() / ".openrig" / "monitor" / "target.json"
    TARGET_FILE_SOURCE = "default"
MONITOR_URL = os.environ.get("YUEYUE_MONITOR_URL", "http://127.0.0.1:3190")

KNOWN_TEMPLATES = [
    ("双平面母版", "templates/specialized/openrig-workflow-master/", "workflow-group 控制面 + OpenRig 多 seat 执行"),
    ("单用户专项治理", "templates/specialized/yueyue-governance/", "单 seat + 心跳 + staging/live 治理"),
    ("微信桥产品重设计", "templates/specialized/wechat-yueyue-redesign/", "单窗口产品形态/交互重设计"),
    ("fix-wave", "templates/baseline/fix-wave/BASELINE.md", "缺陷票批量修复，先红后绿"),
    ("ops-hardening", "templates/baseline/ops-hardening/BASELINE.md", "分发/调度/入口可靠性加固"),
    ("refactor-decompose", "templates/baseline/refactor-decompose/BASELINE.md", "先归属冻结，再行为不变重整"),
    ("product-redesign-live", "templates/baseline/product-redesign-live/BASELINE.md", "反目标→设计→staging→live/回滚"),
    ("two-plane-orchestration", "templates/baseline/two-plane-orchestration/BASELINE.md", "双权威、隔离 home/port、QA+join+有界回边"),
    ("原子契约", "templates/contracts/", "strategy/research/diff/architecture/optimize/verify/audit"),
]


def templates() -> list[dict]:
    out = []
    for name, rel, why in KNOWN_TEMPLATES:
        p = ROOT / rel
        out.append({"name": name, "path": str(p), "rel": rel, "why": why, "exists": p.exists()})
    return out


def preflight_text() -> str:
    try:
        return PREFLIGHT.read_text(encoding="utf-8")
    except Exception as e:
        return f"# PREFLIGHT MISSING\n{PREFLIGHT}\n{e}"


def inject_agents(workspace: str, run_id: str = "", monitor_url: str = MONITOR_URL) -> dict:
    if not workspace:
        return {"ok": False, "reason": "no --workspace"}
    root = Path(workspace).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    f = root / "AGENTS.md"
    old = f.read_text(encoding="utf-8") if f.exists() else ""
    block = f"""<!-- BEGIN OPENRIG-PREFLIGHT (managed) -->
## OpenRig preflight — AI 必须先读

- 必读：`{PREFLIGHT}`
- 工作流规则：`{ROOT / 'WORKFLOW.md'}` §1–§7；角色：`{ROOT / 'roles'}/`
- 选型：先查 `{ROOT / 'templates/baseline/REGISTRY.md'}` 和 `{ROOT / 'templates/contracts/README.md'}`；SPEC §0 必须声明 baseline/contracts。
- 机器可读 preflight：`python3 {ROOT / 'scripts/openrig_preflight.py'} --json --run-id {run_id or '<run-id>'}`
- 硬规则：唯一 rig 名 / 一个写权限一个 owner / 先快照 / 不直改 OpenRig DB / 先归档后 teardown / DONE 后必须 stop watchdog。
- 监控台：`{monitor_url}`（新 run 自动注册 target；只读 sidecar，不写治理状态）。
<!-- END OPENRIG-PREFLIGHT (managed) -->"""
    if re.search(r"<!-- BEGIN OPENRIG-PREFLIGHT \(managed\) -->.*?<!-- END OPENRIG-PREFLIGHT \(managed\) -->", old, re.S):
        new = re.sub(r"<!-- BEGIN OPENRIG-PREFLIGHT \(managed\) -->.*?<!-- END OPENRIG-PREFLIGHT \(managed\) -->", block, old, flags=re.S)
    else:
        new = (old.rstrip() + "\n\n" + block + "\n") if old.strip() else block + "\n"
    f.write_text(new, encoding="utf-8")
    return {"ok": True, "file": str(f), "bytes": len(new)}


def register_monitor(args, run_dir: str, gov_dir: str) -> dict:
    if args.no_monitor:
        return {"ok": False, "skipped": "no-monitor"}
    run_id = args.run_id or (Path(run_dir).name if run_dir else "")
    if not run_id:
        return {"ok": False, "reason": "no --run-id"}
    target = {
        "runId": run_id,
        "label": args.label or run_id,
        "rig": args.rig or "",
        "seat": args.seat or "",
        "job": args.job or "",
        "govDir": str(Path(gov_dir).expanduser().resolve()) if gov_dir else "",
        "runDir": str(Path(run_dir).expanduser().resolve()) if run_dir else "",
    }
    try:
        conf = json.loads(TARGET_FILE.read_text(encoding="utf-8")) if TARGET_FILE.exists() else {}
    except Exception:
        conf = {}
    conf.setdefault("targets", {})
    conf["targets"][run_id] = target
    conf["active"] = run_id
    TARGET_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = TARGET_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(conf, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, TARGET_FILE)
    started = None
    try:
        started = subprocess.run(
            ["systemctl", "--user", "start", "yueyue-monitor.service"],
            capture_output=True, text=True, timeout=10,
        )
    except Exception as e:
        started = type("R", (), {"returncode": 1, "stdout": "", "stderr": str(e)})
    return {
        "ok": started.returncode == 0 if started else False,
        "targetFile": str(TARGET_FILE),
        "targetFileSource": TARGET_FILE_SOURCE,
        "active": run_id,
        "target": target,
        "monitorUrl": MONITOR_URL,
        "service": "yueyue-monitor.service",
        "serviceStartRc": getattr(started, "returncode", None),
        "serviceError": (getattr(started, "stderr", "") or "").strip()[:300],
    }


def _check(cid: str, ok: bool, detail: str, required: bool = True, install_hint: str = "") -> dict:
    item = {"id": cid, "required": required, "ok": bool(ok), "detail": detail}
    if install_hint:
        item["installHint"] = install_hint
    return item


def check_preflight_file() -> dict:
    exists = PREFLIGHT.is_file()
    return _check(
        "preflight_file",
        exists,
        f"{PREFLIGHT} {'存在' if exists else '缺失'}",
        install_hint="" if exists else "恢复 templates/specialized/openrig-workflow-master/PREFLIGHT.md",
    )


def check_required_components() -> dict:
    comps = required_components.check_components(ROOT)
    bad = required_components.failures(comps)
    if not bad:
        return _check("required_components", True, f"{len(comps)} 个组件全部满足 required")
    detail = "；".join(f"{c['id']}: {c['detail']}" for c in bad)
    hint = next((c["install_hint"] for c in bad if c.get("install_hint")), "")
    return _check("required_components", False, detail, install_hint=hint)


def check_workspace_context(workspace: str, run_id: str) -> dict:
    if not workspace:
        return _check(
            "workspace_context",
            False,
            "缺 --workspace，无法确认 seat 工作区已注入 preflight",
            install_hint="加 --workspace <seat 工作区>（脚本会注入 managed block 后重读校验）",
        )
    f = Path(workspace).expanduser() / "AGENTS.md"
    if not f.is_file():
        return _check("workspace_context", False, f"{f} 不存在")
    text = f.read_text(encoding="utf-8", errors="replace")
    m = re.search(
        r"<!-- BEGIN OPENRIG-PREFLIGHT \(managed\) -->(.*?)<!-- END OPENRIG-PREFLIGHT \(managed\) -->",
        text,
        re.S,
    )
    if not m:
        return _check("workspace_context", False, f"{f} 缺 OPENRIG-PREFLIGHT managed block")
    block = m.group(1)
    if run_id and run_id not in block:
        return _check(
            "workspace_context",
            False,
            f"{f} 的 managed block 未包含 run-id {run_id}",
        )
    return _check("workspace_context", True, f"{f} 已含 run-id {run_id or '<any>'} 的 managed block")


def _resolve_run_dir(run_dir: str) -> Path | None:
    if not run_dir:
        return None
    p = Path(run_dir).expanduser()
    if not p.is_absolute() and not p.exists() and (ROOT / p).exists():
        p = ROOT / p
    return p


def check_run_context(run_id: str) -> dict:
    if not run_id:
        return _check(
            "run_context",
            False,
            "缺 --run-id",
            install_hint="加 --run-id <run-id>（对应 runs/<run-id> 必须存在）",
        )
    rd = ROOT / "runs" / run_id
    if not rd.is_dir():
        return _check("run_context", False, f"runs/{run_id} 不存在")
    return _check("run_context", True, f"runs/{run_id} 存在")


def check_run_docs(run_dir: str) -> dict:
    rd = _resolve_run_dir(run_dir)
    if rd is None:
        return _check("run_docs", False, "缺 run 目录，无法检查四件套")
    missing = [n for n in ("PROJECT.md", "DECISIONS.md", "ISSUES.xlsx") if not (rd / n).is_file()]
    if not list(rd.glob("STATUS-Round-*.md")):
        missing.append("STATUS-Round-*.md")
    if missing:
        return _check("run_docs", False, f"{rd} 缺: {', '.join(missing)}")
    return _check("run_docs", True, f"{rd} 四件套齐全")


def _skipped_workspace_check(workspace: str, run_id: str, reason: str) -> dict:
    """pre-check 失败时 workspace 校验未执行；显式标记，避免看起来像已通过。"""
    item = _check(
        "workspace_context",
        False,
        f"{reason}；未注入 AGENTS.md、未做 workspace 校验",
        install_hint="修复上面的 required 检查后重跑（有 --workspace 时脚本会注入并校验）",
    )
    item["skipped"] = True
    return item


def run_precheck(run_id: str, run_dir: str) -> list[dict]:
    """无副作用检查：只读磁盘，不写 AGENTS.md、不写 monitor target、不起服务。"""
    return [
        check_preflight_file(),
        check_required_components(),
        check_run_context(run_id),
        check_run_docs(run_dir),
    ]


def run_checks(workspace: str, run_id: str, run_dir: str) -> list[dict]:
    """完整检查（含 workspace）；副作用由 main() 在 pre-check 之后决定是否执行。"""
    return run_precheck(run_id, run_dir) + [check_workspace_context(workspace, run_id)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default="")
    ap.add_argument("--rig", default="")
    ap.add_argument("--seat", default="")
    ap.add_argument("--job", default="")
    ap.add_argument("--run-dir", default="")
    ap.add_argument("--gov-dir", default="")
    ap.add_argument("--workspace", default="", help="inject managed AGENTS.md block here")
    ap.add_argument("--label", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--full", action="store_true", help="include full preflight text in JSON")
    ap.add_argument("--no-monitor", action="store_true")
    ap.add_argument(
        "--advisory",
        action="store_true",
        help="informational mode: keep rc=0 even when ok=false (never fakes ok:true)",
    )
    args = ap.parse_args()

    run_dir = args.run_dir or (str(ROOT / "runs" / args.run_id) if args.run_id else "")
    gov_dir = args.gov_dir or args.workspace
    text = preflight_text()
    # W2：先跑无副作用 pre-check；失败立即返回，绝不注入 AGENTS.md / 写 target.json / 起服务。
    precheck = run_precheck(args.run_id, run_dir)
    precheck_ok = all(c["ok"] for c in precheck if c["required"])
    failed_ids = [c["id"] for c in precheck if c["required"] and not c["ok"]]
    injected = None
    monitor = None
    if precheck_ok:
        injected = inject_agents(args.workspace, args.run_id, MONITOR_URL) if args.workspace else None
        monitor = register_monitor(args, run_dir, gov_dir) if (run_dir or args.no_monitor) else None
        checks = precheck + [check_workspace_context(args.workspace, args.run_id)]
    else:
        checks = precheck + [
            _skipped_workspace_check(
                args.workspace, args.run_id, f"pre-check 失败（{', '.join(failed_ids)}）"
            )
        ]
    ok = all(c["ok"] for c in checks if c["required"])
    reasons = [f"{c['id']}: {c['detail']}" for c in checks if c["required"] and not c["ok"]]
    payload = {
        "ok": ok,
        "advisory": bool(args.advisory),
        "checks": checks,
        "reasons": reasons,
        "role": "openrig-agent-preflight",
        "runId": args.run_id,
        "rig": args.rig,
        "seat": args.seat,
        "job": args.job,
        "preflightPath": str(PREFLIGHT),
        "workflowPath": str(ROOT / "WORKFLOW.md"),
        "rolesPath": str(ROOT / "roles"),
        "docsContract": ["PROJECT.md", "DECISIONS.md", "STATUS-Round-n.md", "ISSUES.xlsx"],
        "templates": templates(),
        "injectedAgents": injected,
        "monitor": monitor,
        "precheck": {"ok": precheck_ok, "failed": failed_ids},
        "mandatory": [
            "SPEC.md §0 must declare baseline + contracts",
            "unique rig name / unique workflow id / isolated OPENRIG_HOME",
            "one writer per write scope; no concurrent edits on same file",
            "snapshot and rollback before changing live",
            "do not modify OpenRig SQLite or queue tables directly",
            "workflow progress only through rig workflow project",
            "archive before rig down / daemon stop",
            "write DONE/BLOCKED and stop watchdog when terminal",
        ],
    }
    if args.full:
        payload["preflight"] = text

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(text)
        print("\n## Preflight checks")
        for c in checks:
            mark = "OK" if c["ok"] else ("FAIL" if c["required"] else "WARN")
            print(f"- [{mark}] {c['id']}: {c['detail']}")
            if not c["ok"] and c.get("installHint"):
                print(f"  hint: {c['installHint']}")
        print(f"\n结果: {'PASS' if ok else 'FAIL'} (ok={str(ok).lower()}, reasons={len(reasons)})")
        print("\n## Templates")
        for t in payload["templates"]:
            mark = "OK" if t["exists"] else "MISSING"
            print(f"- [{mark}] {t['name']}: {t['path']}\n  {t['why']}")
        if injected:
            print(f"\nAGENTS injected: {injected.get('file')}")
        if monitor:
            print(f"\nMonitor: {monitor.get('monitorUrl')} active={monitor.get('active')} rc={monitor.get('serviceStartRc')}")
    if args.advisory:
        return 0
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
