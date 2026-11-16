<!-- wf-doc
run: openrig-p0-hard-constraints-20261116
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

### D-004（Round 1）baseline 是点时刻快照，verify 前不得重跑 baseline

- **决策**：`wf.py baseline` 每次执行都重新捕获快照，这是既定语义；本轮保留两份：启动捕获 `impl_baseline_evidence/00-baseline.startup.txt`（“无越界”判据）与 Packet B 验收捕获 `00-baseline.{json,txt}`（verify 的即时对照）。QA 必须在**不重跑 `baseline`** 的前提下执行 `verify-baseline`，预期 rc=1 且 `statusAdded` 恰为 Packet C 的 4 个新文件。
- **背景/选项**：
  - A：把 baseline 改成只写一次的不可变快照（改命令语义，超出本轮范围）；
  - B（采用）：保留点时刻语义，用两份快照和 QA 口径区分“启动基线/即时对照”；
  - C：收口时先重跑 baseline 再 verify（会重置快照，verify 必然 rc=0，属于自证，禁止）。
- **影响面**：R02 的漂移证明以 post-B 快照 + C 的 4 个 `statusAdded` 为准；启动基线单独保存，不覆盖。若未来要“不可变基线”，另开 R02b。
- **状态**：生效

### D-005（Round 1）R07 live render drift 接受为 WARN，不修 manifest / 不重渲染

- **决策**：`verify_render.py` 对 live run 报 4 处 bytes mismatch（`rig.yaml`、`workflow.yaml`、`guidance/team.md`、`OPENRIG-BRIDGE.json`），默认 rc=0/`ok:false`；`--strict` rc=1。本轮按默认 WARN 验收，FINAL 记录该 WARN，不重渲染、不重写 manifest。
- **背景/选项**：
  - A：重渲染覆盖 live 文件（会覆盖运行时规范化结果，可能破坏 live rig，禁止）；
  - B：重写 manifest 匹配现状（伪造消费者证据，使 `--strict` 假绿，禁止）；
  - C（采用）：保持 WARN，语义核对六步/依赖/guards/closure、三 pod/seat、bridge seatMap/runtimeEnv/policy 均完整；把“manifest 与 run 特化 guidance 不同源”列为下轮 S3 候选。
- **影响面**：R07 的机器语义（default WARN / strict ERROR / 坏 manifest rc=2）已由负向测试覆盖；live drift 不阻塞 P0，但记录为已知 WARN。
- **状态**：生效

### D-006（Round 1）P0 收口裁定：达成；P1/P2 不进入本轮

- **决策**：R01–R07 交付完成，R08 每门 ≥1 真负向，QA 判定 PASS-WITH-WARN，MAIN 独立复跑全量 pytest（259 passed）与 TASK §5；接受 W1（close 内解决）与 W2–W5（带 owner/去向/最晚复核轮转下一轮）。本轮终止，状态：达成。R09–R14（P1/P2）明确未实现。
- **背景/选项**：
  - A：把 W2–W5 在本轮一并修掉（会扩大范围并需重跑 QA，P0 收口被拖长）；
  - B（采用）：P0 按既定判据收口，WARN 全部登记承接，下一轮先做 P1 小包；
  - C：忽略 WARN 直接宣称全绿（禁止，等于假门）。
- **影响面**：`reports/FINAL.md` 与根 `FINAL.md` 记录 WARN 处置；PROJECT §8 登记残余风险；下一轮候选 = R04b、W2、W3、W4、W5，P1 收口前不进入 P2。
- **状态**：达成

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
