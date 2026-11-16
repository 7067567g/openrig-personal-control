# SPEC — SignalDeck 完全体重构

## 0. 分层声明

baseline: composite/refactor-decompose@1.0.0
contracts: research@1.0.0, diff@1.0.0, architecture@1.0.0, optimize@1.0.0, verify@1.0.0

> 本文件是本 run 的**特化规则**，与通用 `WORKFLOW.md` / `roles/*` 冲突时以本文件为准。
> 通用规则仍然有效：文档即接口、单一写者、STATUS 加锁逐条提交、分歧不落地。
>
> **本 run 的硬边界**：只重整 `deepseek-项目/10-signaldeck` 与 workflow-group 的本 run 目录；
> 不启动 OpenRig daemon、不碰 `10-openrig-deepseek` 的运行面、不写 KB 正式域、不 push。

## 1. 任务

把 `10-signaldeck` 从「契约核 + 4 个自足 bundle + 复制兜底」推进到「源码可重建、共享靠编译期、边界有门禁、版本可追溯」的完全体：

1. 4 个 runner 都有 `src/` 源树，`runner.cjs` 可由 `build-tools.mjs` 重建；
2. `tool-lib` 被至少 2 个工具实际使用，重复的 params/numbers/files/table 助手删除；
3. 规则链只有一份纯语义核心，前端 worker 与宿主 vm 退化为薄执行器；
4. 轨迹算法只有一份实现，有 oracle + 随机差分测试；
5. Host 运行时拆成 job-store / job-executor / event-bus / tool-lib / log-sink；HTTP 路由表驱动；
6. 前端拆成 domain / platform；widgets 懒加载；
7. `ctx.lib.apiVersion` + 结果版本戳 + `/api/health`；
8. 治理 verifier 进两包 `gate-steps`，全量门禁绿；
9. 所有工具 A/B 产物哈希与基线一致（除有意变更并登记）。

**行为不变原则**：R1–R3 只做清点、映射、架构冻结，不改业务代码；R4–R8 每次改动必须用现有 A/B 或哈希证明行为未变。

## 2. 目标工作副本与写权限

| 路径 | 权限 | 用途 |
| --- | --- | --- |
| `<DS_ROOT>/deepseek-项目/10-signaldeck/**` | 可写 | 被重整的项目仓 |
| `workflow-group/runs/<RUN-ID>/**` | 可写 | 四件套、报告、证据 |
| `workflow-group/templates/specialized/signaldeck-refactor/**` | 可写 | 本特化模板 |
| `workflow-group/roles/**`、`WORKFLOW.md`、`scripts/wf.py` | 只读（主会话例外） | 通用流程；本 run 不改造流程本体 |
| `deepseek-项目/10-openrig-deepseek/**` | 只读 | 参考工作流形状，不作为运行底座 |
| `deepseek-知识库` 正式域（`00-overview/` 等） | 只读 | 不写正式正文 |
| `归档/**`、其他项目目录 | 只读 | 不碰 |

**写权限白名单按 WS 再切**：

- `tdo-a1`：`10-signaldeck/src/tools/**`、`10-signaldeck/src/tool-lib/**`、`10-signaldeck/scripts/build-tools.mjs`、`10-signaldeck/scripts/verify-tool-build.mjs`。
- `tdo-a2`：`10-signaldeck/src/desktop/**`、`10-signaldeck/src/frontend/**`、`10-signaldeck/src/frontend/shared/contracts/**`、`10-signaldeck/tests/**`。
- 两边都需要的文件（`package.json`、gate-steps、交付脚本）：由主会话在 `DECISIONS.md` 指定唯一 owner，另一人只读。

## 3. 全内容覆盖要求（硬）

- **文件级清点**：`10-signaldeck` 下 `src/desktop`、`src/frontend/src`、`src/frontend/shared`、`src/tools`、`tests`、`scripts`、`docs/kb-trial` 逐目录/逐文件给结论；不允许“其他”“杂项”静默吞掉。
- **4 个 runner**：每个 runner 的每个命令、每个导出、每个 `ctx.lib` 调用有归属结论。
- **host bundle**：分片清单、manifest、baseline hash、生成链、消费方逐项核对。
- **前端**：`shared/contracts`、`src/contracts`、`lib`、`state`、`widgets`、`workers`、`components` 的依赖边界逐项核对。
- **门禁**：24 步逐项列出命令、判据、当前结果、是否覆盖新治理。
- **文档**：语义总账、重复账本、变更矩阵、依赖规则必须与代码事实一致；不一致记 ISSUE。

## 4. 证据格式

每条结论使用以下格式之一：

```text
[PASS] <检查项> | cmd: <命令> | exit: <码> | evidence: <路径或摘要>
[WARN] <检查项> | cmd: <命令> | exit: <码> | why: <影响> | evidence: <路径或摘要>
[FAIL] <检查项> | cmd: <命令> | exit: <码> | blocker: <阻塞什么> | evidence: <路径或摘要>
[SKIP] <检查项> | why: <未执行原因> | 后续: <补测方式>
```

附加要求：

- 哈希用 `sha256sum`，同时记字节数；A/B 产物哈希必须给命令和对比结果。
- 门禁必须给完整命令、退出码、汇总行（`N PASS / N FAIL / N SKIP`）和日志路径。
- 不把“命令存在”写成“可用”；不把“旧门禁绿”写成“新治理绿”。
- 不贴完整日志正文；只留关键行 + 路径。

## 5. 禁止

- R1–R3 不改业务代码、不改 runner、不改 host bundle。
- 不 push；不 `git add -A`；主会话只按明确 pathspec 提交。
- 不删除/移动文件；删除类动作必须先出清单并由主会话 `D-xxx` 拍板。
- 不写 KB 正式域；不碰 `10-openrig-deepseek` 的运行面；不碰 `归档/**`。
- 不把“重构”当行为变更：任何 C2 行为变化必须单独登记并重跑 A/B。
- 不新开游离台账；残余只进 workflow-group 的 ISSUES/PROJECT §6 或既有 terminal items。

## 6. 完成定义（DoD）

- **G1 清点完整**：`reports/INVENTORY.md` 覆盖 §3 全部目录/文件；每个对象有「保留/迁移/新增/删除候选」结论与证据；无未分类项。
- **G2 基线冻结**：`reports/BASELINE.md` + `BASELINE-pre.sha256` 含 4 runner、host bundle、关键生成物、24 步门禁结果；哈希与字节数齐全。
- **G3 目标结构冻结**：`reports/REFACTOR-MAP.md` 给出 old→new 文件级映射、依赖规则、WS 领地、波次计划；`ROUND-PLAN.md` 通过 PLAN-GATE 7/7。
- **G4 工具可重建**：4/4 runner 可从 `src/` 重建；`verify-tool-build` 绿；`verify-tools-health` 绿；A/B 哈希不变。
- **G5 共享语义单一**：`tool-lib` 被 ≥2 工具使用；规则链单一核心；轨迹算法单一实现；`duplication-ledger` 的 open 项关闭或有 `D-xxx` 接受。
- **G6 Host/前端结构**：runtime 五模块 + HTTP 路由表；frontend domain/platform + lazy widgets；`/api/health` 与结果版本戳可用。
- **G7 最终验收**：全量门禁（旧 24 步 + 新 governance verifier）全绿；所有工具 A/B 与基线一致或有意变更已登记；ISSUES 无 open S1/S2；0 未登记重复。

## 7. 波次计划（计划 8 轮，预算上限 10）

| 轮 | 原子轮型 | 目标 | 主要产出 |
| --- | --- | --- | --- |
| R1 | `research` | 清点 + 基线冻结 | `reports/INVENTORY.md`、`reports/BASELINE.md`、`BASELINE-pre.sha256` |
| R2 | `diff` | old→new 映射 + 领地/波次 | `reports/REFACTOR-MAP.md`、`reports/DIFF-LEDGER.md` |
| R3 | `architecture` | 冻结目标结构/契约/边界 | `reports/ARCH-ASSESSMENT.md`、`reports/CAPABILITY-MAP.md`、`ROUND-PLAN.md` 7/7 |
| R4 | `optimize` | 工具构建链 + quick_tools 试点 | `build-tools.mjs`、`verify-tool-build`、quick_tools `src/` |
| R5 | `optimize` | 其余工具源树 + tool-lib 接入 | 3 runner `src/`、`tool-lib` 实际使用、去重 |
| R6 | `optimize` | 规则链 + 轨迹算法收敛 | `shared/semantics/rule-chain`、`tool-lib/geo` |
| R7 | `optimize` | Host 拆分 + 前端分层 + 观测 | `desktop/runtime/*`、`desktop/http/*`、`frontend/domain+platform`、`/api/health` |
| R8 | `verify` | 独立复跑 + 收口 | `reports/VERIFY-FINAL.md`、`reports/RELEASE-NOTES.md`、`VERDICT: STOP` |

**预算**：`max_rounds: 10`（8 正向 + 2 次补救）。超过 10 轮或 `VERDICT: STOP` 即停；不允许无限循环。

## 8. 并行与领地

- 默认 `TDO×2`：`tdo-a1` 管 tools/tool-lib/build；`tdo-a2` 管 desktop/frontend/contracts/tests。
- 同一文件只能一个 TDO 写；共享文件由主会话在 `ROUND-PLAN.md` 指定唯一 owner，另一人只读。
- 领地冲突时串行，不并发；发现冲突立即 STOP AND RULE，写 ISSUE 升级主会话。
- R4–R7 每个 optimize 轮的目标 ≤3；超过 3 个就拆下一轮，不硬塞。

## 9. 文档与证据落点

- 每轮报告：`runs/<RUN-ID>/reports/<ROUND>-<topic>.md`。
- 每轮证据：`runs/<RUN-ID>/reports/evidence/`。
- 每轮 `ROUND-PLAN.md` 必须含 `contract / produces / gate / budget / NOT-DOING` 五行。
- 每轮结束由主会话写 `reports/VERDICT.md`（CONTINUE | ADJUST | STOP）。
- 关闭时写 `reports/ADOPTION-REPORT.md` 与 `BASELINE-post.sha256`。
