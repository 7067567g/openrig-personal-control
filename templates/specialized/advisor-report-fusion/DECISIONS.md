<!-- wf-doc
run: <RUN-ID>
round: <ROUND-N>
doc: DECISIONS
owner: 主会话
state: open
updated: <DATE>
-->

# DECISIONS — 多份顾问报告的筛选、合并与处置

> 写者：主会话 ｜ 其他角色只读 ｜ 未定项留在 `PROJECT.md §6`，不在此预写结论。

## 0. 记录规则（固定，勿删）

1. 每条决策唯一 ID `D-xxx`，只增不改；翻案时新开一条并写“取代 D-xxx”。
2. 必须含：轮次、决策、选项、理由、影响面、编制、状态。
3. 报告是非规范输入；任何采纳必须落到本 run 的 decision + 可验证处置。
4. 关闭类决策必须写未处理项 owner/去向/最晚复核点；未立项的“下一 run”不算有效去向。

## 1. 待决清单（主会话拍板后移入 §2）

- **Q-1 筛选口径**：A. 报告共识优先；B. 证据优先并保留分歧（建议）。
- **Q-2 冲突裁决**：A. 按主报告直接采纳；B. 保守升级、先抽 modifier/plane、成熟度不硬升级（建议）。
- **Q-3 本轮处理范围**：A. 全部 P0/P1 立即改；B. 只做可机械验收的 accept_now，其余排波次（建议）。
- **Q-4 动态 OpenRig**：A. 无环境也宣称通过；B. 缺 daemon 则静态核验 + SKIP/park（建议）。

## 2. 决策账本

### D-001（Round <ROUND-N>）项目初始化与初始编制

- **决策**：立项并启动报告融合流程。
- **选项**：A. 单线程摘要；B. 多 WS 抽取→合并→处置→独立核验。
- **理由**：需要来源可追溯、去重不丢项、处置有证据。
- **影响面**：本 run 报告与 accept_now 改动。
- **编制**：PMO×1 / TDO×<TDO-N> / QA×1。
- **状态**：生效。

## 3. 每轮判词（wf.py 投影到 reports/VERDICT.md）

> 主会话在每轮收口时更新此块；`wf.py state PROJECT waiting-main --by pmo` 会投影为 `reports/VERDICT.md`。

<!-- wf:verdict
decision: CONTINUE
rationale: 待填
next: Round-N+1
contracts_used: research@1.0.0
budget: used=0/3; tokens=unknown; time=0m
queue_patch: none
open_items: none
notes: 待填
-->

## 4. 编制变更时间线

| 轮次 | PMO | TDO | QA | 变更理由 | 决策 ID |
| --- | --- | --- | --- | --- | --- |
| R<ROUND-N> | 1 | <TDO-N> | 1 | 初始立项 | D-001 |
