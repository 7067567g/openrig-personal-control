<!-- wf-doc
run: <RUN-ID>
round: Round 1
doc: PROJECT
owner: PMO
state: pmo-plan
updated: 2026-11-10
-->

# PROJECT — 月月bot 微信桥单用户可靠性专项治理

## 0. 元信息

| 项 | 值 |
| --- | --- |
| run-id | `<RUN-ID>` |
| 一句话目标 | 在不牺牲单用户日常便利性的前提下，完成微信桥运行态、消息可靠性、数据完整性、控制语义、资源运维与工程化专项治理 |
| 项目根 | `<DS_ROOT>/月月bot` |
| 线上运行目录 | `<DS_ROOT>/月月bot/wechat-bridge-v2` |
| 治理工作区 | `<DS_ROOT>/月月bot/governance-20261110` |
| 写权限白名单 | `governance-20261110/**`；`wechat-bridge-v2/**`（仅 staging 验证通过后由主控应用）；`~/.config/systemd/user/dsh-*` |
| 执行面 | OpenRig 单 DSH seat + daemon-native watchdog 心跳 |
| 终止判据 | `reports/FINAL.md` 覆盖 G1–G7 且全部通过，或出现不可自行解决的硬外部阻塞并登记 |

## 1. 目标与成功判据

完整判据见 `SPEC.md §3`（G1–G7）。摘要：

- G1 运行态：3080 单实例、systemd 健康、无重启风暴；
- G2 消息可靠性：游标/去重/drain；
- G3 数据完整性：多图/outbox/TaskStore/UTF-8/headless/原子写；
- G4 控制语义：超时 cancel、steer/cancel 真值；
- G5 资源与运维：日志轮转、保留、备份、流式上限；
- G6 工程化：版本单一来源、文档一致、git/CI/包瘦身；
- G7 验收：156+4 基线、新增回归、真实 E2E、短 soak、FINAL 映射。

## 2. 范围

### 2.1 范围内

- 月月bot 微信桥 `wechat-bridge-v2` 的运行态、消息、媒体、交付、会话、日志、备份、版本与文档；
- 本地 systemd 用户服务与部署脚本；
- 可复跑测试与验收证据。

### 2.2 范围外

- 多用户 ACL、跨用户隔离、审批流、路径安全沙箱、远程鉴权；
- 微信协议本身、iLink 登录细节；
- 人格/对话风格改写、新功能扩展、Web 控制台、群聊。

## 3. 指标

| # | 指标 | 基线 | 目标 | 证据 |
| --- | --- | --- | --- | --- |
| M1 | Node 用例 | 156 pass | ≥156 pass，新增回归全绿 | `npm test` 输出 |
| M2 | Python 用例 | 4 pass | ≥4 pass | `test/test_progress.py` |
| M3 | 消息重放重复执行 | 未测 | 0 次 | 重放测试 |
| M4 | 12 图落盘 | 1–3 个 | 12 个唯一文件 | 多图测试 |
| M5 | 55 任务入队 | 丢 5 个 | 0 丢失 | TaskStore 测试 |
| M6 | 3080 重启风暴 | NRestarts 持续增长 | 不再增长 | systemctl 输出 |
| M7 | 日志增长 | 无轮转 | 有轮转/上限 | 轮转证据 |
| M8 | 备份恢复 | 无自动 | 每日备份 + 恢复演练 | 恢复日志 |
| M9 | 包体 | 21.6MB tarball | ≤10MB 且无 .build/.bak | `npm pack --dry-run` |
| M10 | soak | 未做 | ≥2h 或 ≥30 轮，0 丢失/0 重复 | soak 报告 |

## 4. 分任务

| WS | 任务 | 产出物 | 验收 | 执行体 |
| --- | --- | --- | --- | --- |
| WS-0 | 基线、快照、staging | `evidence/ws0/**` | sha256 清单可复算 | gov-seat |
| WS-1 | 运行态与部署 | `evidence/ws1/**` | M6 + systemd 健康 | gov-seat |
| WS-2 | 消息可靠性 | `evidence/ws2/**` + 代码 | M3 + drain 测试 | gov-seat |
| WS-3 | 数据完整性 | `evidence/ws3/**` + 代码 | M4/M5 + 相关测试 | gov-seat |
| WS-4 | 控制语义 | `evidence/ws4/**` + 代码 | cancel/steer 测试 | gov-seat |
| WS-5 | 资源与运维 | `evidence/ws5/**` + 脚本 | M7/M8 + 超时测试 | gov-seat |
| WS-6 | 工程化 | `evidence/ws6/**` + 文档 | M9 + 一致性检查 | gov-seat |
| WS-7 | 独立验收 | `evidence/ws7/**` | 独立复跑 + 反例 | gov-seat |
| WS-8 | 主控收口 | `reports/FINAL.md` | G1–G7 映射完整 | gov-seat |

## 5. 轮次计划与结论

- Round 1：WS-0/WS-1/WS-2 基线与运行态、消息可靠性；
- Round 2：WS-3/WS-4 数据完整性与控制语义；
- Round 3：WS-5/WS-6 资源运维与工程化；
- Round 4：WS-7/WS-8 独立验收、E2E、soak、FINAL。
- 心跳每 600 秒唤醒一次，seat 自行推进；不等待主会话逐轮拍板。

## 6. 上报区

- **本轮结论**：等待 PMO 计划收敛。
- **待拍板**：无（SPEC §1 已授权单用户范围内的取舍）。
- **风险提示**：不得以“单用户”为由跳过数据可靠性；只排除安全/多用户/便利性代价项。
