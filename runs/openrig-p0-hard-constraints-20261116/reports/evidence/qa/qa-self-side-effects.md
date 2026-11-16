# QA 自检：本次独立复跑产生的副作用与恢复记录

> 写者：QA（assurance-qa）｜ 时间：2026-11-16
> 目的：QA 的负向用例会真实调用 `openrig_preflight.py --workspace/--run-id` 与 `wf.py baseline`，
> 这两个命令有副作用。以下逐条记录“发生了什么、恢复到什么值、如何证明”。

## 1. KB 根 `AGENTS.md`（仓库内）

- 触发：负向用例 N2 `openrig_preflight.py --json --workspace <KB> --run-id no-such-run-xyz`。
- `openrig_preflight.py:257` 在校验前调用 `inject_agents()`，会把 managed block 的 run-id 改写成
  `no-such-run-xyz`（即使该 run 不存在），随后检查失败返回 rc=1。
- 观察：sha256 `53eed071626762756e480913c1f1f3eb141f6fb0c96142b4b0950012353c8763`
  → `77c0c40594a67b8fbf60c83bdfa2fd42e12f57bf1b3e7232a4c3bad73c987987`。
- 恢复：把 `--run-id no-such-run-xyz` 文本改回 `openrig-p0-hard-constraints-20261116`，
  恢复后 sha256 = `53eed071…c8763`，与 Packet A 证据 `agents.md.sha256.after` 一致。
- 证据：`agents.md.sha256.before` / `agents.md.sha256.after`；`demo-injection-side-effect.txt`
  （同一副作用在 `/tmp` 临时工作区复现，用于证明这是脚本行为而非手工改动）。

## 2. 监控 target.json（仓库外）

- 路径：`/home/a7067567g/下载/deepseek/月月bot/governance-20261110/dashboard/target.json`
- 触发：同一 N2 调用触发 `register_monitor()`，新增 `targets["no-such-run-xyz"]` 并把 `active`
  设为该值，同时 `systemctl --user start yueyue-monitor.service`。
- 恢复：删除该 target、`active` 设回 `openrig-p0-hard-constraints-20261116`；
  恢复后 sha256 = `2944b57d5ba9cc5159d6d3e7fdb19deb66f61220e771fca4ba5c6f2bb65067f5`，
  与 Packet A 证据 `dashboard-target.sha256.after` 完全一致。
- 说明：Packet A 的 `62ee9d57… → 2944b57d…` 变化是 preflight 既有 monitor 注册行为，已在
  `impl_preflight_components/SUMMARY.md` 声明；本次 QA 未引入新的持久变化。

## 3. 基线快照 `reports/evidence/00-baseline.{json,txt}`

- 触发：TASK §5 包含 `wf.py baseline <run> --json`；该 run 无 `.run-meta.json`，字面命令 rc=1，
  加 `--project-root` 后 rc=0 并会重写这两份文件。
- 恢复：QA 在运行前已把原始快照复制到 `pre-qa-00-baseline.json/.txt`；运行后用 `cmp` 证明
  恢复后与原始文件逐字节一致（见 `baseline-with-project-root.txt` 之后的 shell 输出）。
- 因此 `verify-baseline` 的最终证据仍是针对 **pre-QA 的 post-B 快照**（status `44cde8e4…`），
  不是 QA 新建的自证快照。

## 4. 未发生的事项

- 未写 OpenRig 产品仓（HEAD/status/diff 三值与规划基线完全一致，见 `product-baseline.txt`）。
- 未 commit / push / tag；未删除任何既有文件；未改 templates、roles、其它 runs。
- 全量 pytest 使用 `-p no:cacheprovider`，避免在 QA 写权限外新增缓存文件。
- close-strict / verify-render / archive-gate 的正负例均在 `/tmp/opencode/**` 副本上执行，
  未在真实 run 的 `openrig/` 与 `reports/evidence/closeout.json` 上留下测试数据。
