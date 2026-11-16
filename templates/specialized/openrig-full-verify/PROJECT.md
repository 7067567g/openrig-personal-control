<!-- wf-doc
run: <RUN-ID>
round: <ROUND-N>
doc: PROJECT
owner: PMO
state: pmo-plan
updated: <DATE>
-->

# PROJECT — OpenRig 调整后全量检查

> 写者：PMO ｜ 主会话只读 §6 ｜ 本 run 是检查 run，默认不改源码。

## 0. 元信息

| 项 | 值 |
| --- | --- |
| run-id | `<RUN-ID>` |
| 一句话目标 | `<GOAL>` |
| 被检查仓库 | `/home/dev/Desktop/deepseek/deepseek-项目/10-openrig-deepseek` |
| 上游只读 | `/home/dev/Desktop/deepseek/60-外部仓库/openrig` |
| 写权限白名单 | `workflow-group/runs/<RUN-ID>/**`、`workflow-group/templates/specialized/openrig-full-verify/**`、`workflow-group/kickoff/openrig-full-verify*`、`/tmp/openrig-full-verify-*` |
| 源码权限 | 默认只读；发现缺陷只登记 ISSUE，不直接修 |
| 编制 | PMO×1 / TDO×<TDO-N> / QA×1 |
| 当前轮次 | Round <ROUND-N> |
| 终止判据 | 所有检查项 PASS，或 FAIL/WARN 均有证据、影响面和下一步；doctor PASS |

## 1. 目标与成功判据

- **G1 仓库/静态**：workspace build、lint/typecheck、docs/context/skill mirror 检查全部有结果。
  - 判据：命令 + exit + 日志证据。
- **G2 全量测试**：仓库级测试与 daemon/cli/tui/ui 四包测试完整执行；不得用定向测试冒充全量。
  - 判据：测试汇总（文件数/用例数/退出码）与日志。
- **G3 新特性回归**：OpenCode/DSH runner、input、adapter、resume metadata、native skill path 的定向测试 PASS。
- **G4 真实 E2E**：5 seats all ready；OC/DSH 真实任务、envelope、同一 runner 续会话通过；启动不自动耗模型。
- **G5 跨重启 resume**：rig down 捕获 token；rig up --existing 两个 TDO resumed，后续同 session id。
- **G6 Workflow/spec**：workflow validate 与 rig spec plan 通过；workflow instantiate/compile 至少一项有明确结果。
- **G7 卫生**：外部 clone 干净；仓库无 secret；无残留 daemon/tmux/runner；AGENTS.md 不留在仓库。
- **G8 报告**：`reports/FULL-CHECK.md` 完整，ISSUES 无 open S1/S2 或如实登记。

## 2. 范围

### 2.1 范围内

- 只读检查自有 OpenRig 仓库与提交 `b8bdbdf` / `c36c8d9` 之后的最终 HEAD。
- 所有 build/test/e2e/安全/卫生检查。
- 隔离 `/tmp` 环境中的真实运行验证。

### 2.2 范围外

- 不修代码、不提交源码、不改全局配置；
- 不删除旧 runtime；
- 不跑生产业务/H 盘任务；
- 不 push。

### 2.3 假设与依赖

- Node24 + OpenCode 1.19.3 + DSH 0.2.1-rc.2 可用；
- 本机 4 vCPU / 5.8GB，重测试必须串行；
- 先停止上次 run 的 daemon/rig，再开始全量检查；
- 全量测试可能耗时较长，允许后台执行但必须等到终态。

## 3. 指标

| # | 指标 | 基线 | 目标 | 当前 | 证据 |
| --- | --- | --- | --- | --- | --- |
| M1 | 仓库完整性 | 未检查 | clean + upstream untouched | 待采集 | `reports/evidence/repo-state.txt` |
| M2 | build | 未检查 | all workspaces PASS | 待采集 | `reports/evidence/build.txt` |
| M3 | lint/typecheck | 未检查 | all packages PASS | 待采集 | `reports/evidence/lint.txt` |
| M4 | 仓库级测试 | 未检查 | `test:repo` PASS | 待采集 | `reports/evidence/test-repo.txt` |
| M5 | daemon 全量 | 未检查 | 完整终态 | 待采集 | `reports/evidence/test-daemon.txt` |
| M6 | cli/tui/ui 全量 | 未检查 | 完整终态 | 待采集 | `reports/evidence/test-cli-tui-ui.txt` |
| M7 | 新特性定向 | 未检查 | 全部 PASS | 待采集 | `reports/evidence/test-feature.txt` |
| M8 | 真实 E2E | 未检查 | 5 ready + OC/DSH task | 待采集 | `reports/evidence/e2e-*.txt` |
| M9 | 跨重启 resume | 未检查 | 两 TDO resumed | 待采集 | `reports/evidence/resume-*.txt` |
| M10 | workflow/spec | 未检查 | validate/instantiate 有结论 | 待采集 | `reports/evidence/spec-*.txt` |
| M11 | 卫生 | 未检查 | 无残留/无 secret | 待采集 | `reports/evidence/hygiene.txt` |

## 4. 分任务（Workstreams）

| WS | 任务 | 产出物 | 验收判据 | 依赖 | 执行体 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| WS-1 | 仓库/静态/构建 | evidence/repo-state、build、lint | clean + PASS | — | TDO | 待开始 |
| WS-2 | 仓库级 + 四包全量测试 | evidence/test-* | 全部终态有汇总 | WS-1 | TDO | 待开始 |
| WS-3 | 新特性定向回归 | evidence/test-feature | 全 PASS | WS-2 | TDO | 待开始 |
| WS-4 | 真实 rig E2E | evidence/e2e-* | 5 ready + OC/DSH task/envelope/resume | WS-3 | TDO | 待开始 |
| WS-5 | 跨重启 resume + workflow/spec | evidence/resume-*、spec-* | TDOs resumed + validate ok | WS-4 | TDO | 待开始 |
| WS-6 | 卫生/QA/报告 | FULL-CHECK.md、hygiene | doctor PASS、无残留 | WS-5 | TDO/QA | 待开始 |

## 5. 轮次计划与结论

### Round 1 计划

- 先静态和全量测试，再真实 E2E；发现问题只登记。
- 本轮结束时输出 `reports/FULL-CHECK.md` 与完整证据。

### Round 1 结论

- 待采集。

## 6. PMO 上报区

- **本轮结论**：待采集。
- **待拍板**：待采集。
- **指标变化**：待采集。
- **风险提示**：待采集。

## 7. 变更日志

| 时间 | 轮次 | 变更 | 由谁 |
| --- | --- | --- | --- |
| <DATE> | R1 | 建立全量检查 run | 主会话 |
