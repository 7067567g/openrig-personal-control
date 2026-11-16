# POST-CLOSE-FIX — openrig-run pre-launch daemon-down semantics

- 发现：`openrig_run.py check --allow-daemon-down` 在真实 daemon/home 已停时仍先调用
  `rig workflow validate`，导致降级后仍被 live 依赖阻塞。
- 修复：check 现在先探测 `rig ps`；daemon down 时把 `seats` 标 WARN/FAIL，
  `workflow_validate` 标 `skipped`，把 validate 留到 `start` 的 daemon-up 之后。
- 验证：
  - `pytest tests/test_openrig_run.py -q` → 13 passed
  - full pytest → 310 passed
  - live daemon-down：`check --allow-daemon-down --json` → `ok:true`，checks =
    bridge ok / render ok / doctor ok / seats warn / workflow_validate skipped
  - `start --dry-run` 仍返回 5 步计划且 `executed=[]`
- 未重跑 P1 live acceptance；这是 post-close 修复，不改变 P1 的已归档证据。
