<!-- wf-doc
run: openrig-p1-hard-constraints-20261116
round: 1
doc: DECISIONS
owner: 主会话
state: open
updated: 2026-11-16
-->

# DECISIONS — OpenRig 混合编排母版实例

## 0. 记录规则

1. 每条决策唯一 ID，按时间只增不改。
2. 目标、删除、发布、预算、权限、跨 run 边界必须由本账本记录。
3. 执行状态由 OpenRig queue/workflow 负责，不在本文件抄写实时状态。
4. 任何“跳过 OpenRig 直接做”的降级必须单独决策并标注原因。

## 1. 决策账本

### D-001（Round 1）双平面权威

- **决策**：workflow-group 控制面负责目标/决策/验收；OpenRig 执行面负责 seat/queue/workflow/transcript；`OPENRIG-BRIDGE.json` 是唯一映射。
- **背景/选项**：
  - A：把 queue 当项目账本，容易丢失决策和验收；
  - B：两边各存一份全量状态，容易漂移；
  - C（采用）：各管一类事实，证据路径相互指向。
- **影响面**：所有 WS 必须引用 bridge；禁止双写全量状态。
- **状态**：生效

### D-002（Round 1）每 run 生成唯一 rig/workflow spec

- **决策**：由 `render_master.py` 生成唯一 rig 名、workflow id、cwd、seat map 和 bridge；同一台机器可并行多个 run，不共享 namespace。
- **影响面**：不直接复用示例 rig/workflow 名字；生成物进 run 目录。
- **状态**：生效

### D-003（Round 1）默认隔离运行

- **决策**：默认 managed isolated：独立 `OPENRIG_HOME`、端口、tmux；attached 模式需主会话显式批准。
- **理由**：避免跨项目 queue/session 污染，便于清理与复现。
- **状态**：生效

### D-004（Round 1）live run 的 render 漂移：不重渲染，close 记录特化

- **背景**：`verify_render` 显示 `rig.yaml` / `workflow.yaml` / `guidance/team.md` / `OPENRIG-BRIDGE.json`
  与 `render-manifest.json` 不符。MAIN 独立复核（`reports/evidence/main-verify-decisions.txt`）：
  manifest 无损坏（同参重渲染逐字节复现 manifest）；4 个文件在渲染后 26s（00:47:58）被整体替换为
  3-seat 版（去掉 pmo/dsh、`maxActiveAgents` 2→1、`maxHops` 10→12），与 `SPEC.md` §9 一致；
  同类漂移在 p0、token-r1 两个历史 run 上完全同构。
- **选项**：
  - A（采用）：不重渲染；`close_round` 用 `wf.py render-specialize` 为 4 文件登记 exact specialization，
    reason 显式写明「launch-path 渲染后 3-seat 特化，意图见 SPEC §9，close 时补记」；随后 `verify_render`
    应显示 `ok:true` + `specialized:true`。
  - B：重渲染 live run —— 会在运行中改 seat 图（新增 pmo/dsh），破坏当前 seat/queue 绑定。**否决**。
  - C：保持 mismatch 不登记 —— 每个 run 长期带红门，读者会习惯性忽略真漂移。**否决**。
- **影响面**：W5 机制首次用于真实 run；产品侧缺口（launch path 不调用 render-specialize）转入后续票，不在本轮修。
- **状态**：生效（执行时点＝`close_round`）

### D-005（Round 1）母版 BASELINE-post 陈旧：只报告，不刷新

- **背景**：`sha256sum -c BASELINE-post.sha256` = 35 OK / 3 FAILED（`ENTRYPOINTS.md`、`README.md`、`SPEC.md`）。
  `README.md`/`SPEC.md` 的 mtime 为 2026-10-23，早于本 run；`ENTRYPOINTS.md` 的改动是 R12 要求。
- **选项**：A（采用）只报告 + 进后续版本票；B 本轮刷新快照 —— 属于 VERSION/CHANGELOG 升版，超出 TASK §0 白名单。**否决 B**。
- **影响面**：母版快照可信度下降，已知且记录；不得据此宣称母版内容与快照一致。
- **状态**：生效

### D-006（Round 1）Packet A/B 无 before-hash：接受为已声明限制

- **背景**：`workflow-group/scripts/**` 与多数 `tests/**` 在 KB 仓是 untracked（无 HEAD blob），A 起手时无副本，
  无法重建 pre-A 字节；A 的 baseline 刷新发生在编辑之后，属自重基线。
- **决策**：接受 `changed-files.txt` 的 `not-captured` 记录，不补造 before 哈希；A 的 scope 以 mtime 白名单扫描
  + 逐文件 after sha256 + 负向输出证明。刷新后的 `00-baseline.txt` **只能作 B/C/D/QA 的前向参考**，不得当作 A 的
  留痕证据；原始文件保留为 `00-baseline.original.txt`。
- **影响面**：QA/close 不得把 A 的 scope 结论写成「内容哈希级证明」；W4 `snapshot_files.py` 从 B 起提供真 before/after。
- **状态**：生效

### D-007（Round 1）close-lint 在 close 前失败是预期行为

- **背景**：`wf_close_lint --strict` 现返回 rc=1，错误仅 `final_missing` + `closeout_missing`，且提示已含
  `reports/FINAL.md 或根 FINAL.md`（R04b 生效）。
- **决策**：保留该失败；`close_round` 写 FINAL/closeout 后重跑，变绿才算收轮。不得临时放宽检查。
- **状态**：生效

### D-008（Round 1）QA F-1（S2，空 STATUS/ISSUES）的收轮处置

- **背景**：`STATUS-Round-1.md` 收轮前仍是空模板，`ISSUES.xlsx` 为空；QA 无法从文档面核对进度。
- **选项**：
  - A（采用）：用 `wf.py append-status --no-commit` 补 6 条包级进度（plan、A–D、qa_final）并手写交接段；
    `ISSUES.xlsx` 保持为空，理由是**本轮没有开放缺陷工单**——QA 的 6 条发现均为有 owner 的 WARN/风险，
    已落 `QA-VERDICT.md` §6 与证据目录，不为凑格式而制单。
  - B：把 6 条 WARN 全部登记为 ISSUE —— 会把"风险记录"混同"缺陷工单"，且无实际修复排期。**否决**。
- **影响面**：STATUS 与证据目录成为本轮文档面事实；ISSUES 为空的含义被显式记录，避免后人误读为漏填。
- **状态**：生效

## 2. 待决清单

| 编号 | 待决问题 | 选项 A | 选项 B | 主会话拍板 | 状态 |
| --- | --- | --- | --- | --- | --- |
| Q-1 | 两个 TDO 分支并行还是串行 | 预算允许时并行（推荐） | 始终串行 | — | 待决 |
| Q-2 | SAFETY 是否强制 | 仅高风险动作强制（推荐） | 所有 run 强制 | — | 待决 |
| Q-3 | 失败后 fresh 还是 resume | 优先 resume，明确 fresh 需 DECISION（推荐） | 一律 fresh | — | 待决 |

## 3. 编制变更时间线

| 轮次 | PMO | TDO | QA | 变更理由 | 决策 ID |
| --- | --- | --- | --- | --- | --- |
| R1 | 1 | 1 | 1 | 初始立项 | D-001 |
