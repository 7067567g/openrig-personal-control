<!-- wf-doc
run: <RUN-ID>
round: <ROUND-N>
doc: DECISIONS
owner: 主会话
state: open
updated: <DATE>
-->

# DECISIONS — <PROJECT-NAME>

> 写者：主会话 ｜ 其他角色只读。
> 只记**已确认**决策；未定的留在 `PROJECT.md` §6 待拍板，不在此处预写。

## 0. 记录规则（固定，勿删）

1. 每条决策有唯一 ID `D-xxx`，按时间顺序只增不改；被翻案时新开一条并写"取代 D-xxx"。
2. 每条必须含：轮次、决策、背景/选项、理由、影响面、编制、状态。
3. **编制（子智能体数量）每轮在此重定**，并同步更新 §2 时间线。
4. 终止/达成的最终决定也必须是一条 `D-xxx`（状态：终止/达成）。
5. **关闭收口 + 跨轮承接**：关闭/终止类 `D-xxx` 必须写明资产去向；跨轮/跨 run 承接项必须写 owner + 去向 + 最晚复核轮（未立项的“下一 run”不算有效去向）。已知游离项无 owner/去向时，必须有主会话在此处显式接受，否则不得关闭。

## 1. 决策账本

### D-001（Round <ROUND-N>）项目初始化与初始编制

- **决策**：立项；启动 PMO→TDO→QA 循环；初始编制 `PMO×1 / TDO×<TDO-N> / QA×1`；采用 `composite/refactor-decompose@1.0.0` 与 `research, diff, architecture, optimize, verify` 五类原子轮型。
- **背景/选项**：
  - A：先小编制探路（TDO×1）
  - B：按工具侧 / host+前端侧两条互斥领地并行（TDO×2）
- **理由**：SignalDeck 的文件领地可以按 `src/tools` 与 `src/desktop+src/frontend` 切开；R1–R3 只读清点，适合两路并行；R4 起根据生成物共享情况降为 TDO×1。
- **影响面**：R1–R8 的 WS 划分与 `ROUND-PLAN.md`。
- **编制**：PMO×1 / TDO×<TDO-N> / QA×1
- **状态**：生效

## 2. 编制变更时间线

| 轮次 | PMO | TDO | QA | 变更理由 | 决策 ID |
| --- | --- | --- | --- | --- | --- |
| R<ROUND-N> | 1 | <TDO-N> | 1 | 初始立项：工具侧 + host/前端侧两路互斥 | D-001 |
