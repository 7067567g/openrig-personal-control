# -*- coding: utf-8 -*-
"""Shared builders for the red-team suite.

All builders write only under the caller's ``tmp_path``.  No product code is
imported and no live process/socket is touched (the conftest ban applies).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from fake_rig import Clock, FakeRig, IdFactory, Step
from observation import Sources, evaluate
from supervisor_sim import Context, SeatStatus, SupervisorSim, make_context

OBJECTIVE = "fixture objective"
CREATED_BY = "fixture@fixture"


def seats(*ids: str, token: bool | str = True, session: str = "present", node: str = "node-1"):
    """Build ready seats with a clean oracle observation unless overridden."""
    observation = evaluate(
        Sources(session=session, hook_present=True, hook_activity="working")
    )
    return tuple(
        SeatStatus(
            logicalId=seat_id,
            canonicalSessionName=f"sess-{seat_id}",
            nodeId=node,
            observation=observation,
            resumeTokenPresent=token,
        )
        for seat_id in ids
    )


def context(base, *, seat_list=None, **flags) -> Context:
    """Create a disposable run context under ``base`` (a tmp_path child)."""
    base = Path(base)
    if seat_list is None:
        seat_list = seats("main")
    return make_context(base / "run", seats=seat_list, tmp_root=base, **flags)


def build(ctx: Context, script=(), *, base=None, clock=None, ids=None) -> SupervisorSim:
    """Build a SupervisorSim over a scripted FakeRig under the same tmp root."""
    clock = clock or Clock()
    ids = ids or IdFactory()
    root = Path(base) if base is not None else Path(ctx.run_dir).parent
    runner = FakeRig(Path(ctx.home), list(script), clock, ids, tmp_root=root)
    return SupervisorSim(ctx, runner=runner, clock=clock, ids=ids)


def start_steps(ctx: Context) -> list[Step]:
    """The canonical five-command start script (daemon already absent)."""
    return [
        Step(
            argv=("rig", "daemon", "start", "--no-kernel", "--port", str(ctx.port)),
            repeat="consumed",
        ),
        Step(
            argv=(
                "rig",
                "up",
                str(ctx.rig_spec),
                "--cwd",
                str(ctx.project),
                "--yes",
            ),
            repeat="consumed",
        ),
        Step(argv=("rig", "workflow", "validate", "--rig", ctx.rig_name), repeat="consumed"),
        Step(
            argv=(
                "rig",
                "workflow",
                "instantiate",
                "--root-objective",
                OBJECTIVE,
                "--created-by",
                CREATED_BY,
                "--rig",
                ctx.rig_name,
            ),
            repeat="consumed",
        ),
    ]


def up_existing(ctx: Context, *, rc: int = 0, code: str | None = None) -> Step:
    return Step(
        argv=("rig", "up", ctx.rig_name, "--existing"),
        repeat="consumed",
        rc=rc,
        code=code,
    )


def down(ctx: Context) -> Step:
    return Step(argv=("rig", "down", ctx.rig_name), repeat="consumed")


def complete_manifest() -> dict:
    return {
        "archiveStatus": "COMPLETE",
        "dshSession": None,
        "sessions": ["main", "tdo"],
        "required": {"tasks": True, "research": True, "report": True, "sessions": True, "dsh": False},
        "items": {"tasks": True, "research": True, "report": True, "sessions": True, "dsh": False},
    }


def with_flag(ctx: Context, **changes) -> Context:
    return replace(ctx, **changes)
