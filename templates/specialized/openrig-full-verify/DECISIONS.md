<!-- wf-doc
run: <RUN-ID>
round: <ROUND-N>
doc: DECISIONS
owner: 主会话
state: open
updated: <DATE>
-->

# DECISIONS — OpenRig 调整后全量检查

## 0. 记录规则

1. 每条决策唯一 ID，按时间只增不改。
2. 检查 run 默认不改源码；修复需另拍 D-xxx。
3. 证据优先于“命令看起来成功”。

## 1. 决策账本

### D-001（Round <ROUND-N>）检查 run：只验证，不修源码

- **决策**：本 run 对最终 HEAD 做只读全量检查；发现缺陷登记 ISSUE，修复动作另开决策。
- **理由**：避免“一边检查一边改”污染验收基线。
- **影响面**：测试失败作为结果保留，不随手修。
- **编制**：PMO×1 / TDO×<TDO-N> / QA×1
- **状态**：生效

### D-002（Round <ROUND-N>）隔离 E2E 环境

- **决策**：真实 daemon/rig 使用 `/tmp/openrig-full-verify-*`、独立端口和独立 tmux；不碰用户已有 dsh web/OpenRig。
- **理由**：保护用户运行中的服务和会话。
- **影响面**：E2E 结束后必须 down/stop/清理；证据保留在 run 目录。
- **状态**：生效

## 2. 待决清单

| 编号 | 待决问题 | 选项 A | 选项 B | 主会话拍板 | 状态 |
| --- | --- | --- | --- | --- | --- |
| Q-1 | 发现 FAIL 时是否立即修 | 先登记，主会话另拍（推荐） | 当场修 | — | 待决 |

## 3. 编制变更时间线

| 轮次 | PMO | TDO | QA | 变更理由 | 决策 ID |
| --- | --- | --- | --- | --- | --- |
| R<ROUND-N> | 1 | <TDO-N> | 1 | 初始立项 | D-001 |
