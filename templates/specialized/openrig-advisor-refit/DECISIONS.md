<!-- wf-doc
run: <RUN-ID>
round: <ROUND-N>
doc: DECISIONS
owner: 主会话
state: open
updated: <DATE>
-->

# DECISIONS — OpenRig Advisor Refit

> 写者：主会话 ｜ 其他角色只读 ｜ 报告是输入，不是第二事实源。

## 0. 记录规则（固定，勿删）

1. 每条决策唯一 ID `D-xxx`，只增不改；翻案新开并写“取代 D-xxx”。
2. 必须含：轮次、决策、选项、理由、影响面、编制、状态。
3. 关闭类决策必须写未处理项 owner/去向/最晚复核点。

## 1. 决策账本

### D-001（Round 1）证据优先与保守收敛

- **决策**：采纳融合台账已裁决的保守版：保留 `safe-cleanup` M3；不强制 M2 清零；不按 25% 硬指标压缩文档；先做退役术语降噪与 issue-sync 降级 pilot。
- **理由**：报告质量比较明确警示激进项；成熟度是证据不是目标。
- **影响面**：WS-1、WS-2。
- **状态**：生效。

### D-002（Round 1）文档降噪的执行口径

- **决策**：`WORKFLOW.md §11` 是退役术语唯一规范入口；角色手册只保留“无主项进 ISSUES/STATUS + 去向闭合”的可操作语义，不再重复历史禁令；新增机检防止回潮。
- **理由**：减少新会话认知噪音，同时不改变收口门禁。
- **影响面**：`WORKFLOW.md`、`roles/*.md`、`AGENTS.md`、`tests/test_doc_noise.py`、基础母版 LOCK。
- **状态**：生效。

### D-003（Round 1）OpenRig 执行与归档边界

- **决策**：本 run 使用隔离 `OPENRIG_HOME`、独立端口和 4-seat rig；若 DSH backend 不可用，seat 运行时退化为 OpenCode并记 SKIP，不伪造 DSH live；必须先产生 COMPLETE 归档再 teardown。
- **理由**：落实报告 P0 双平面闭环与安全归档要求。
- **影响面**：WS-3、WS-5、`reports/openrig-run.md`、archive manifest。
- **状态**：生效。

<!-- wf:verdict
decision: PENDING
rationale: 待本轮实现与 QA 核验
next: TBD
contracts_used: optimize@1.0.0
budget: used=0/2; tokens=0; time=0m
queue_patch: none
open_items: none
notes: template placeholder; replace at closeout
-->

## 2. 编制变更时间线

| 轮次 | PMO | TDO | QA | 变更理由 | 决策 ID |
| --- | --- | --- | --- | --- | --- |
| R1 | 1 | 1 | 1 | 报告驱动内容优化 + OpenRig 双平面 | D-001 |
