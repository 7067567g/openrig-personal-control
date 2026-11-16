# SignalDeck 全量扫描 + 优化 · 启动文档（烧额度版）

> 生成：2026-10-13 ｜ 场景：opencode 额度约 24h 后到期，要最大化转化为可验证成果
> 依赖：`WORKFLOW.md`（流程规范）、`roles/delegation-briefs.md`（委派模板）、`scripts/wf.py`（serve/delegate/squad/ledger/commit）
> 目标文件：`kickoff/signaldeck-audit-goal.txt`（直接喂给 `new-run --goal-file`）

## 0. 先看这里

- 新会话扮演**主会话**：只做「定编制 → 委派 → 收账 → 读 `PROJECT.md` §6 → 写 `DECISIONS.md` → 提交」。
- 主会话**不读** `STATUS-Round-*.md`、不读 `ISSUES.xlsx` 正文；执行、核查全交给 opencode 的 flash 智能体。
- 项目仓是**只改不提交**：每轮结束由主会话用 `wf.py commit` 统一提交，且**永不 push**。

## 1. 粘给新会话的启动提示词

```text
你现在是 workflow-group 的主会话。工作目录：/home/dev/Desktop/deepseek/deepseek-知识库/workflow-group

先读（按顺序）：
1) README.md（30 秒上手）
2) WORKFLOW.md（重点 §2 编制、§3 状态机、§5 锁、§9 opencode 直连、§9.1 真实项目提交）
3) roles/delegation-briefs.md（§5 主会话每轮固定动作）
4) kickoff/signaldeck-full-audit-burn.md（本文件，执行计划）

任务：按本文件 §3 的 run 参数与 §4 的分片弹药表，对 SignalDeck 做全面扫描+优化，
     把 24h 额度尽量转化为「可复现证据 + 已过门禁的修复 + 审计报告」。

硬约束：
- 你不读 STATUS/ISSUES 正文；只读 PROJECT.md §6 上报区来决定下一轮。
- 项目仓只改不提交、不 push；每轮用 wf.py commit 统一提交明确 pathspec。
- 白名单外（其他项目、KB 正式域）只读；不删文件；没有证据的结论不算数。
- 每处修复必须过相关门禁；门禁失败先修或记 ISSUES，不许掩盖。

执行方式：严格按本文件 §5 的 SOP 循环；用 wf.py delegate/squad 发活，用 wf.py ledger 记账；
        用 wf.py doctor 体检；用 wf.py new-round 开下一轮。现在从 §3 的第 1 步开始。
```

## 2. Run 参数（建议直接照抄）

| 项 | 值 |
| --- | --- |
| run-id | `signaldeck-audit-20261013` |
| 项目根 | `/home/dev/Desktop/deepseek/deepseek-项目/10-signaldeck` |
| 项目仓 git root | `/home/dev/Desktop/deepseek/deepseek-项目`（**不是** 10-signaldeck 自身） |
| 写权限白名单 | `10-signaldeck/**`（记入 PROJECT §0） |
| 提交策略 | TDO 只改不提交；每轮 `wf.py commit --repo <项目仓> --run <id> --round N --message '...' -- 10-signaldeck/...`；不 push |
| 模型 | 扫描/修复：默认 `opencode-go/deepseek-v4.1-flash`；深度 QA/收口可 `--model opencode-go/deepseek-v4-pro`（想烧更快就全局换 pro） |
| 并发 | `squad --jobs 6` 起步，稳定后 8；每个执行体绑定唯一 WS |
| 超时 | 单次委派 `--timeout 3600`；服务默认 `--pure`（无插件、冷启快、prompt 小） |
| 时间盒 | T-2h 停止开新轮；T-1h 完成收口提交 |

## 3. 启动步骤（第 1 轮）

```bash
cd /home/dev/Desktop/deepseek/deepseek-知识库/workflow-group

# 1) 建档（目标文件已含全部约束；项目根/白名单写进 PROJECT §0）
python3 scripts/wf.py new-run signaldeck-audit-20261013 \
  --goal-file kickoff/signaldeck-audit-goal.txt \
  --project-root /home/dev/Desktop/deepseek/deepseek-项目/10-signaldeck \
  --scope '10-signaldeck/**' --tdo 8

# 2) 起服务（默认 --pure，自动预热）
python3 scripts/wf.py serve start

# 3) PMO 计划（把审计维度拆成 8-10 片 WS，按文件边界互斥）
python3 scripts/wf.py delegate signaldeck-audit-20261013 --role pmo --timeout 3600

# 4) 主会话不读 PROJECT 正文；确认 PMO 回执后（PROJECT→plan-ready），扇出扫描波
python3 scripts/wf.py squad signaldeck-audit-20261013 \
  --agents 'tdo-a1:WS-1,tdo-a2:WS-2,tdo-a3:WS-3,tdo-a4:WS-4,tdo-a5:WS-5,tdo-a6:WS-6' \
  --timeout 3600 --jobs 6

# 5) 全部回执后 → QA 核查 → PMO 收轮
python3 scripts/wf.py state signaldeck-audit-20261013 STATUS qa-pending
python3 scripts/wf.py delegate signaldeck-audit-20261013 --role qa --timeout 3600
python3 scripts/wf.py delegate signaldeck-audit-20261013 --role pmo --timeout 3600

# 6) 主会话读 PROJECT §6 → 写 DECISIONS.md（本轮决策 + 下一轮编制）
# 7) 提交本轮项目变更（只 add 明确路径；不 push）
python3 scripts/wf.py commit --repo /home/dev/Desktop/deepseek/deepseek-项目 \
  --run signaldeck-audit-20261013 --round 1 --message 'R1 审计扫描' \
  -- 10-signaldeck

# 8) 开下一轮
python3 scripts/wf.py new-round signaldeck-audit-20261013
python3 scripts/wf.py ledger signaldeck-audit-20261013
```

## 4. 分片弹药表（R1 扫描波，PMO 可增删但要保持文件边界互斥）

| WS | 范围 | 现成抓手 | 建议产出 |
| --- | --- | --- | --- |
| WS-1 | `src/frontend/src/{state,api,hooks,lib,workers}` 架构与 TS 类型 | `npm run check`（tsc+eslint） | 类型漏洞/死代码/状态边界清单 |
| WS-2 | `src/frontend/src/{components,widgets,styles}` UI/UX/可访问性 | 组件树、样式文件 | 交互缺陷/键盘可达性/空态清单 |
| WS-3 | `src/desktop/src/{server,shared}` + 契约链 | `verify-contract-parity`、`verify-host-build`、`build:host` | 契约漂移/镜像不一致/宿主漏洞 |
| WS-4 | `src/tools/**` 4 个工具 + `src/plugins` | `verify-tools-health`、`verify-async-tools` | 工具契约/异常路径/输入校验清单 |
| WS-5 | `tests/**`（22 步门禁 + 23 脚本） | `bash tests/run-linux.sh`、`verify-windows-gate-parity` | 覆盖盲区/可重复性/对等性差距 |
| WS-6 | 打包/交付/路径 | `scripts/*.ps1`、`交付包/`、环境变量化提交 | 硬编码路径/可移植性/包内容清单 |
| WS-7 | 安全边界 | KB `signaldeck-security-boundary.md` 对照 | Host/Origin/Token/文件访问复核 |
| WS-8 | 文档一致性 | `README.md`、`docs/`、KB SignalDeck 五篇 | 文档-代码-KB 三方矛盾清单 |
| WS-9 | 性能与资源 | 启动路径、包体、worker、渲染热路径 | 可量化瓶颈 + 测量方法 |
| WS-10 | 物探工具正确性 | `verify-knife7-ab`、`verify-stdtrack-ab`、样例数据 | 边界用例/数值正确性清单 |

后续波次（由 PMO 按 ISSUES 定，不要提前锁死）：

- **R2 深挖波**：对 R1 的 S2+ 问题做交叉复核与最小复现（4-6 片）。
- **R3 修复波**：按 ISSUES S2+ 分片修复，每片独立文件边界，修完跑该片相关门禁。
- **R4 回归波**：全量 `bash tests/run-linux.sh` + `npm run check` + `npm run build` + 关键 verification；负例/并发/错误路径。
- **R5 优化波**：性能/体积/体验/文档同步（只做有测量数据支撑的项）。
- **R6 收口**：QA 终检（S1/S2 清零）→ 全量门禁绿 → `reports/audit-final.md` → PMO 报告 → DECISIONS 关闭。

## 5. 每轮 SOP（主会话固定动作）

1. 收齐回执（缺谁补发；不读正文）。
2. `python3 scripts/wf.py doctor <run>`，有 ERROR 先让对应角色修。
3. `state <run> STATUS qa-pending` → 委派 QA。
4. 委派 PMO 收轮（PROJECT→waiting-main）。
5. 读 `PROJECT.md` §6 → 写 `DECISIONS.md`（本轮决策 + 分歧裁决 + 下一轮编制 N'）。
6. `wf.py commit`（只 add 白名单内明确路径）。
7. 到达目标 → 收口清单（§7）；否则 `new-round` → 回第 1 步。

## 6. 烧额度节奏与熔断

| 指标 | 建议 |
| --- | --- |
| 并行 TDO | 6 起步；ledger 显示排队/等待多就提到 8-10 |
| 单轮墙钟 | 20–40 分钟（受最慢 TDO 决定） |
| 目标吞吐 | 8–12 轮/天；每轮至少产出 1 份报告 + N 条 ISSUES + 1 批修复 |
| 熔断 | 连续 2 轮零新发现且全量门禁绿 → 收口；门禁连续失败 2 次且 1 轮内无定位 → 停该片并升级 |
| 时间 | T-2h 停新轮；T-1h 完成报告与最终提交 |

## 7. 收口产物清单

- `runs/<run-id>/reports/audit-final.md`：维度覆盖、发现统计、修复清单、未决项、证据索引
- `runs/<run-id>/ISSUES.xlsx`：全量问题/风险/变更（S1/S2 清零或有明确挂起理由）
- `runs/<run-id>/DECISIONS.md`：每轮决策与编制变更
- `runs/<run-id>/DELEGATIONS.md` + `wf.py ledger`：额度消耗账本
- 项目仓每轮 commit 列表（未 push；是否 push 由人确认）

## 8. 已知坑（照做就行）

1. **会话创建冷启动**：非 pure 首建约 28s；`serve start` 默认 `--pure` 并自动预热，别关。
2. **项目仓很脏**：已有他人未提交改动（`src/desktop/package-lock.json` 等）→ 只用 `wf.py commit` 的明确 pathspec，绝不 `git add -A`。
3. **opencode 权限**：`git push = ask`，无人值守会挂；本计划禁止 push。
4. **并发抢片**：`squad` 强制每片唯一 WS；PMO 拆片必须文件边界互斥。
5. **STATUS 单文件**：并发写靠锁 + 逐条提交；如果某个 TDO 报锁竞争，等一轮即可，不要绕过锁。
6. **额度到期**：`ledger` 看消耗速度；快到期时优先把 R4/R6 做扎实，而不是开新扫描。
