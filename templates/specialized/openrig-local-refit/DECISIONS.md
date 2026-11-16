<!-- wf-doc
run: <RUN-ID>
round: <ROUND-N>
doc: DECISIONS
owner: 主会话
state: open
updated: <DATE>
-->

# DECISIONS — OpenRig 本地工作流重整

## 0. 记录规则（固定，勿删）

1. 每条决策有唯一 ID `D-xxx`，按时间顺序只增不改；被翻案时新开一条并写“取代 D-xxx”。
2. 每条必须含：轮次、决策、背景/选项、理由、影响面、编制、状态。
3. 编制每轮在此重定，并同步更新 §3 时间线。
4. 终止/达成的最终决定也必须是一条 `D-xxx`。
5. 删除类动作必须单独决策，不得藏在普通重构里。

## 1. 决策账本

### D-001（Round <ROUND-N>）项目初始化与本地模式

- **决策**：用 workflow-group 本地模式（四件套 + wf.py + OpenCode 会话）重整 OpenRig；不启动 OpenRig daemon，不接入 OpenRig runtime。
- **背景/选项**：
  - A：先接 OpenRig 再改造，闭环快但会把被改造对象当成运行底座，环境噪声大。
  - B：先用本地工作流把 OpenRig 当源码调查/重整，证据链更干净。
- **理由**：当前要验证的是“OpenRig 能否被改造”，不是“OpenRig 现在能否跑”；先把环境与源码事实查清。
- **影响面**：R1 只产出报告和模板；R2 才在自有副本改动代码。
- **编制**：PMO×1 / TDO×<TDO-N> / QA×1
- **状态**：生效

## 2. 待决清单（拍完挪进 §1，不在这里写结论）

| 编号 | 待决问题 | 选项 A | 选项 B | 主会话拍板 | 状态 |
| --- | --- | --- | --- | --- | --- |
| Q-1 | R2 自有工作副本位置 | `deepseek-项目/10-openrig-deepseek`（推荐） | 其他自有路径 | — | 待决 |
| Q-2 | 非 OpenCode runtime 的处理顺序 | 先保留、默认隐藏（推荐） | R2 立即删除 | — | 待决 |
| Q-3 | OpenCode provider 不可用时 | 先修环境/换 endpoint（推荐） | 用 fake/stub 先验适配器 | — | 待决 |
| Q-4 | 是否把 OpenRig 的文档/UI 纳入 R2 重构 | 暂不，先做 runtime/queue 最小竖切（推荐） | 同轮做文档/UI | — | 待决 |

## 3. 编制变更时间线

| 轮次 | PMO | TDO | QA | 变更理由 | 决策 ID |
| --- | --- | --- | --- | --- | --- |
| R<ROUND-N> | 1 | <TDO-N> | 1 | 初始立项 | D-001 |
