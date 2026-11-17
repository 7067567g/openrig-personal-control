# -*- coding: utf-8 -*-
"""WS-B · 有界 QA→TDO 返工图回归（G2 / M5）。

被测对象只有一个：母版模板
`workflow-group/templates/specialized/openrig-workflow-master/templates/workflow.yaml.tpl`。

三层证据：

1. **静态契约**：逐条断言 D-006（选项 B）的分支专属 QA 形状——
   `qa_opencode.failed → implement_opencode`、`qa_dsh.failed → implement_dsh`，
   两个分支 verdict 都完成后才允许 `qa_join`，`close_round` 只能接 join。
2. **只用既有引擎语言**：分支键必须落在闭合 exit 枚举内，目标必须是已存在的
   静态 step id；不出现任何 v1.1 之后新增的引擎字段/API。
3. **真实 parent parser/validator**：把渲染后的 spec 交给 parent OpenRig 的
   `parseWorkflowSpec` + `WorkflowValidator`（daemon dist，只读导入）跑一遍。
   这等价于 `rig workflow validate` 的语法/图校验层，但不需要 live daemon，
   因此可在任意 checkout 复跑；dist 不存在时明确 SKIP，不伪造 PASS。

live failed-exit 投影（一次真实 `rig workflow project --exit failed` 后的
runner hop trace）是执行面证据，落在
`runs/<run-id>/evidence/dsh/M5-*.json`，不在本单测里重复伪造。

运行：
  python3 -m pytest workflow-group/tests/test_workflow_rework.py -q
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]  # workflow-group/
MASTER = ROOT / "templates" / "specialized" / "openrig-workflow-master"
TEMPLATE = MASTER / "templates" / "workflow.yaml.tpl"

EXIT_ENUM = {"handoff", "waiting", "done", "failed"}
STEP_KEYS = {
    "id",
    "actor_role",
    "objective",
    "allowed_exits",
    "re_present_after_seconds",
    "re_present_max_seconds",
    "next_hop",
    "harness",
    "host",
    "gate",
    "depends_on",
    "acceptance",
}
NEXT_HOP_KEYS = {"mode", "suggested_roles", "on"}
LOOP_GUARD_KEYS = {"max_hops", "spawn_budget"}

# Expected branch ownership. Keep this table explicit: if a future edit moves a
# failed edge, the test should fail loudly instead of blessing the new shape.
BRANCH = {
    "qa_opencode": {"implements": "implement_opencode", "role": "tdo_opencode"},
    "qa_dsh": {"implements": "implement_dsh", "role": "tdo_dsh"},
}


class WorkflowLoader(yaml.SafeLoader):
    """YAML 1.1 loader without the `on/off/yes/no` boolean coercion.

    OpenRig's spec parser is YAML 1.2/JSON-schema for keys, so `next_hop.on`
    is the literal key `on`. PyYAML's SafeLoader is YAML 1.1 and would turn
    that key into ``True``, which is a test-instrument artifact, not a spec
    defect. Removing only the bool resolver keeps every structural assertion
    honest without quoting the key in the shipped template.
    """


WorkflowLoader.yaml_implicit_resolvers = {
    first: [
        (tag, regexp)
        for tag, regexp in resolvers
        if tag != "tag:yaml.org,2002:bool"
    ]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


# --------------------------------------------------------------------- helpers
def render_spec(workflow_id: str = "test-workflow-rework", rig: str = "test-rig") -> str:
    """Render the master template with deterministic stand-in identities."""
    text = TEMPLATE.read_text(encoding="utf-8")
    values = {
        "WORKFLOW_ID": json.dumps(workflow_id),
        "WORKFLOW_ID_RAW": workflow_id,
        "RIG_NAME": json.dumps(rig),
        "RIG_NAME_RAW": rig,
    }
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    assert "{{" not in text, "template still carries an unrendered placeholder"
    return text


def load_spec(**over) -> dict:
    return yaml.load(render_spec(**over), Loader=WorkflowLoader)["workflow"]


def steps_by_id(spec: dict) -> dict[str, dict]:
    return {step["id"]: step for step in spec["steps"]}


def dependency_edges(spec: dict) -> dict[str, set[str]]:
    """Edges implied by depends_on (prerequisite → dependent)."""
    edges: dict[str, set[str]] = {step["id"]: set() for step in spec["steps"]}
    for step in spec["steps"]:
        for dependency in step.get("depends_on", []):
            edges[dependency].add(step["id"])
    return edges


def routing_edges(spec: dict) -> dict[str, set[str]]:
    """Dependency edges UNION branch edges — the validator's successor graph."""
    edges = dependency_edges(spec)
    for step in spec["steps"]:
        for target in (step.get("next_hop", {}).get("on") or {}).values():
            edges.setdefault(step["id"], set()).add(target)
    return edges


def longest_path(edges: dict[str, set[str]], start: str, goal: str) -> int | None:
    """Longest acyclic path length (edges) from start to goal; None if absent."""
    best: int | None = None
    stack: list[tuple[str, int, tuple[str, ...]]] = [(start, 0, (start,))]
    while stack:
        node, depth, path = stack.pop()
        if node == goal:
            best = depth if best is None else max(best, depth)
            continue
        for nxt in edges.get(node, ()):
            if nxt in path:  # cycle — handled by the rework assertions
                continue
            stack.append((nxt, depth + 1, path + (nxt,)))
    return best


def _daemon_dist() -> Path | None:
    """Locate a parent OpenRig daemon build for the offline parser/validator."""
    candidates = [
        os.environ.get("OPENRIG_DAEMON_DIST"),
        # sibling project checkout declared by this run's PROJECT §2.3
        str(ROOT.parents[1] / "deepseek-项目" / "10-openrig-deepseek" / "packages" / "daemon" / "dist"),
        str(ROOT.parents[1] / "deepseek-项目" / "10-openrig-deepseek" / "packages" / "cli" / "daemon" / "dist"),
        str(ROOT.parents[1] / "60-外部仓库" / "openrig" / "packages" / "daemon" / "dist"),
    ]
    for candidate in candidates:
        if candidate and (Path(candidate) / "domain" / "workflow-validator.js").is_file():
            return Path(candidate)
    return None


def _run_node_script(tmp_path: Path, dist: Path, yaml_text: str, mode: str) -> subprocess.CompletedProcess:
    spec_path = tmp_path / "workflow.yaml"
    spec_path.write_text(yaml_text, encoding="utf-8")
    script = tmp_path / "check.mjs"
    script.write_text(
        f"""
import fs from "node:fs";
import {{ pathToFileURL }} from "node:url";
const base = {json.dumps(str(dist))};
const {{ parseWorkflowSpec }} = await import(pathToFileURL(base + "/domain/workflow-spec-cache.js").href);
const path = {json.dumps(str(spec_path))};
let spec;
try {{
  spec = parseWorkflowSpec(fs.readFileSync(path, "utf8"), path);
}} catch (err) {{
  console.error("PARSE_ERROR " + (err.code ?? "") + " " + err.message);
  process.exit(3);
}}
if ({json.dumps(mode)} === "parse") {{
  console.log(JSON.stringify({{ ok: true, stepCount: spec.steps.length }}));
  process.exit(0);
}}
const {{ WorkflowValidator }} = await import(pathToFileURL(base + "/domain/workflow-validator.js").href);
const result = new WorkflowValidator().validate(spec);
console.log(JSON.stringify(result, null, 2));
process.exit(result.ok ? 0 : 1);
""",
        encoding="utf-8",
    )
    return subprocess.run(
        ["node", str(script)],
        capture_output=True,
        text=True,
        timeout=60,
    )


# ---------------------------------------------------------------- static shape
def test_template_renders_and_parses():
    spec = load_spec()
    assert spec["id"] == "test-workflow-rework"
    assert spec["version"] == 1
    assert spec["target"]["rig"] == "test-rig"
    ids = [step["id"] for step in spec["steps"]]
    assert len(ids) == len(set(ids)) == 7
    assert ids == [
        "plan",
        "implement_opencode",
        "implement_dsh",
        "qa_opencode",
        "qa_dsh",
        "qa_join",
        "close_round",
    ]


def test_branch_specific_qa_replaces_single_qa_gate():
    spec = load_spec()
    steps = steps_by_id(spec)
    assert "qa" not in steps, "single QA step must be replaced by branch-specific QA steps"

    for qa_id, branch in BRANCH.items():
        qa = steps[qa_id]
        impl = steps[branch["implements"]]
        assert qa["actor_role"] == "qa"
        assert impl["actor_role"] == branch["role"]
        assert qa["depends_on"] == [branch["implements"]]
        assert qa["allowed_exits"] == ["handoff", "waiting", "failed"]
        assert qa["next_hop"]["on"] == {"failed": branch["implements"]}

    # Both implementation steps still fan out from `plan`; the QA split must
    # not turn the branches into a chain.
    assert steps["implement_opencode"]["depends_on"] == ["plan"]
    assert steps["implement_dsh"]["depends_on"] == ["plan"]


def test_join_waits_for_both_branch_verdicts():
    spec = load_spec()
    steps = steps_by_id(spec)
    assert set(steps["qa_join"]["depends_on"]) == {"qa_opencode", "qa_dsh"}
    assert steps["close_round"]["depends_on"] == ["qa_join"]
    assert steps["qa_join"]["allowed_exits"] == ["handoff", "waiting", "failed"]
    assert steps["close_round"]["allowed_exits"] == ["done", "failed"]


def test_only_shipped_engine_language_is_used():
    """D-003: no invented engine fields/APIs — only next_hop.on + max_hops."""
    spec = load_spec()
    for step in spec["steps"]:
        assert set(step) <= STEP_KEYS, f"step {step['id']} carries unknown engine field(s)"
        hop = step.get("next_hop")
        if hop is not None:
            assert set(hop) <= NEXT_HOP_KEYS
            on = hop.get("on") or {}
            assert set(on) <= EXIT_ENUM, "branch keys are the closed exit enum only"
            assert not hop.get("suggested_roles"), "rework must route to a static step, not a role hint"
    assert set(spec["loop_guards"]) <= LOOP_GUARD_KEYS
    assert "retry" not in template_text_lower(), "no ad-hoc retry field may be introduced"
    assert "rework" not in template_text_lower(), "no ad-hoc rework field may be introduced"


def template_text_lower() -> str:
    # Strip explanatory comments so the guard checks YAML keys, not prose.
    lines = [line for line in TEMPLATE.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("#")]
    return "\n".join(lines).lower()


def test_every_branch_target_exists_and_points_back_to_own_tdo():
    spec = load_spec()
    steps = steps_by_id(spec)
    for step in spec["steps"]:
        for exit_kind, target in (step.get("next_hop", {}).get("on") or {}).items():
            assert exit_kind in EXIT_ENUM
            assert target in steps, f"{step['id']} routes {exit_kind} to missing step {target}"
    assert steps["qa_opencode"]["next_hop"]["on"]["failed"] == "implement_opencode"
    assert steps["qa_dsh"]["next_hop"]["on"]["failed"] == "implement_dsh"


# ------------------------------------------------------------------ graph math
def test_failed_edge_closes_the_loop_back_into_the_same_qa():
    spec = load_spec()
    routing = routing_edges(spec)
    deps = dependency_edges(spec)

    for qa_id, branch in BRANCH.items():
        impl = branch["implements"]
        # failed edge QA → TDO ...
        assert impl in routing[qa_id]
        # ... and the dependency edge TDO → QA closes the cycle.
        assert qa_id in deps[impl]
        # A 2-edge cycle per branch: QA --failed--> TDO --handoff--> QA.
        assert qa_id in deps[impl] and impl in routing[qa_id]


def test_join_and_close_are_not_reachable_before_both_verdicts():
    spec = load_spec()
    steps = steps_by_id(spec)
    # qa_join's prerequisites are exactly the two branch QAs; nothing else can
    # advance into closeout early.
    assert set(steps["qa_join"]["depends_on"]) == {"qa_opencode", "qa_dsh"}
    assert set(steps["close_round"]["depends_on"]) == {"qa_join"}
    for step in spec["steps"]:
        if step["id"] not in {"qa_join", "close_round"}:
            assert "close_round" not in (step.get("next_hop", {}).get("on") or {}).values()


def test_max_hops_bounds_base_graph_plus_rework_cycles():
    spec = load_spec()
    deps = dependency_edges(spec)
    base = longest_path(deps, "plan", "close_round")
    assert base == 4, f"base dependency walk changed (got {base}); re-derive the budget"

    max_hops = spec["loop_guards"]["max_hops"]
    assert isinstance(max_hops, int) and max_hops >= 1
    # The dependency walk above is four edges; close_round itself is the fifth
    # routing advance. One full rework of BOTH branches adds two advances per
    # branch. 2026-11-17 hotfix: 5 + 2 + 2 = 9 needs coverage with headroom.
    assert max_hops == 12, "2026-11-17 hotfix binds this template to max_hops: 12"
    assert max_hops >= base + 5, "must cover the close projection and both branch reworks"
    assert max_hops <= 20, "budget grew far beyond the documented rework headroom"


# --------------------------------------------------- real parent parser/validator
@pytest.mark.parametrize("mode", ["parse", "validate"])
def test_parent_openrig_accepts_rendered_spec(tmp_path, mode):
    dist = _daemon_dist()
    if dist is None:
        pytest.skip("parent OpenRig daemon dist not available; live validate captured in evidence/dsh")
    result = _run_node_script(tmp_path, dist, render_spec(), mode)
    assert result.returncode == 0, f"node stderr:\n{result.stderr}\nstdout:\n{result.stdout}"

    payload = json.loads(result.stdout)
    if mode == "parse":
        assert payload == {"ok": True, "stepCount": 7}
        return

    assert payload["ok"] is True, payload
    assert payload["summary"]["stepCount"] == 7
    assert payload["summary"]["entryRole"] == "pmo"
    assert not [issue for issue in payload["issues"] if issue["severity"] == "error"], payload["issues"]


def test_parent_openrig_rejects_invented_engine_field(tmp_path):
    """Negative control: the same parser rejects an invented `retry:` field."""
    dist = _daemon_dist()
    if dist is None:
        pytest.skip("parent OpenRig daemon dist not available")

    broken = render_spec().replace(
        "    - id: qa_opencode\n",
        "    - id: qa_opencode\n      retry: 3\n",
        1,
    )
    assert "retry: 3" in broken
    result = _run_node_script(tmp_path, dist, broken, "parse")
    assert result.returncode != 0, "invented engine field must be rejected"
    assert "retry" in (result.stderr + result.stdout).lower()
