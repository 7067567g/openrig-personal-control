<!-- wf-doc
run: <RUN-ID>
round: <ROUND-N>
doc: PROJECT
owner: PMO
state: pmo-plan
updated: <DATE>
-->

# PROJECT — <PROJECT-NAME>

> 写者：PMO ｜ 主会话只读 §6（+ 本文件头状态字段）｜ 其他角色只读本文件 + `SPEC.md`
> 特化：`baseline: composite/refactor-decompose@1.0.0`；`contracts: research, diff, architecture, optimize, verify`。

## 0. 元信息

| 项 | 值 |
| --- | --- |
| run-id | `<RUN-ID>` |
| 一句话目标 | `<GOAL>` |
| 项目根 | `<PROJECT-ROOT>` |
| 写权限白名单 | `<WRITE-SCOPE>`（按 SPEC §2 的 WS 子域再切；共享文件由主会话指定唯一 owner） |
| 主会话提交范围 | 仅 `10-signaldeck/` 与 `workflow-group/runs/<RUN-ID>/` 的明确 pathspec；不 `git add -A`；不 push |
| 主会话 | 当前会话 |
| 编制 | PMO×1 / TDO×<TDO-N> / QA×1 |
| 当前轮次 | Round <ROUND-N> |
| 终止判据 | 达成：G1–G7 全通过且无 open S1/S2；终止：连续 2 轮无进展、预算 `max_rounds=10` 用尽，或主会话 `VERDICT: STOP` |

## 1. 目标与成功判据

- **G1 清点完整**：`reports/INVENTORY.md` 覆盖 `10-signaldeck` 的 `src/desktop`、`src/frontend/src`、`src/frontend/shared`、`src/tools`、`tests`、`scripts`、`docs/kb-trial`；每个对象有「保留/迁移/新增/删除候选」结论与证据；无未分类项。
- **G2 基线冻结**：`reports/BASELINE.md` + `BASELINE-pre.sha256` 含 4 runner、host bundle、关键生成物、24 步门禁结果；哈希 + 字节数齐全。
- **G3 目标结构冻结**：`reports/REFACTOR-MAP.md` 给出 old→new 文件级映射、依赖规则、WS 领地、波次计划；`ROUND-PLAN.md` 通过 PLAN-GATE 7/7。
- **G4 工具可重建**：4/4 runner 可从 `src/` 重建；`verify-tool-build` 绿；`verify-tools-health` 绿；A/B 哈希不变。
- **G5 共享语义单一**：`tool-lib` 被 ≥2 工具使用；规则链单一核心；轨迹算法单一实现；`duplication-ledger` 的 open 项关闭或有 `D-xxx` 接受。
- **G6 Host/前端结构**：runtime 五模块 + HTTP 路由表；frontend domain/platform + lazy widgets；`/api/health` 与结果版本戳可用。
- **G7 最终验收**：全量门禁（旧 24 步 + 新 governance verifier）全绿；所有工具 A/B 与基线一致或有意变更已登记；ISSUES 无 open S1/S2；0 未登记重复。

**反目标（明确不做）**：

- 不改变业务行为；任何 C2 行为变化必须单独登记并重跑 A/B。
- 不引入通用工作流 DSL / Step 组合子框架；只做标准库 + 薄控制流糖。
- 不重写 UI；不做纯美学重构。
- 不 push；不碰 `10-openrig-deepseek` 运行面；不写 KB 正式域。

## 2. 范围

### 2.1 范围内

- `10-signaldeck` 的源码结构、构建链、依赖边界、共享语义、门禁与观测。
- `workflow-group/runs/<RUN-ID>/` 的报告与证据。
- 本 run 的 specialized 模板。

### 2.2 范围外

- 其他项目（`10-openrig-deepseek`、`20-*`、`30-*`、`40-*`）的代码与数据。
- 发布、push、安装包重签。
- KB 正式正文重写。

### 2.3 假设与依赖

- Node/npm 可用；`10-signaldeck` 全量门禁可在 Linux 跑通（2026-10-25 实测 24 PASS / 0 FAIL / 0 SKIP）。
- 4 个 runner 当前是自足 bundle，源树不在库内；R4 起需要重建 `src/` 源树。
- `ctx.lib` 白名单是静态门禁；新增成员必须同步 `verify-tools-health`。
- 主会话只读 PROJECT §6 + DECISIONS，不读 STATUS/ISSUES 正文。

## 3. 指标

| # | 指标 | 基线 | 目标 | 当前 | 证据来源 | 采集方式 |
| --- | --- | --- | --- | --- | --- | --- |
| M1 | 清点覆盖率 | 未采集 | 100% 目录/文件有结论 | 待采集 | `reports/INVENTORY.md` | 逐目录表 |
| M2 | 基线哈希数 | 0 | 4 runner + host + 2 生成物 = 7+ | 待采集 | `BASELINE-pre.sha256` | `sha256sum` |
| M3 | 映射覆盖率 | 0 | 每个待迁移文件有 old→new | 待采集 | `reports/REFACTOR-MAP.md` | 文件级表 |
| M4 | runner 可重建 | 0/4 | 4/4 | 待采集 | `verify-tool-build` | 重建 + cmp |
| M5 | 共享语义去重 | 4 组重复 | open 项 0 或已接受 | 待采集 | `duplication-ledger` | 台账核对 |
| M6 | 全量门禁 | 24 PASS | 24+ PASS / 0 FAIL | 待采集 | `reports/VERIFY-FINAL.md` | `bash tests/run-linux.sh` |

## 4. 分任务（Workstreams，R1 示例；PMO 每轮按 ROUND-PLAN 重写）

| WS | 任务 | 产出物（路径） | 验收判据 | 依赖 | 建议执行体 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| WS-1 | 工具/runner 清点与基线 | `reports/INVENTORY.md`、`reports/BASELINE.md`、`BASELINE-pre.sha256` | 覆盖 4 runner + tool-lib + scripts；哈希/字节数齐全 | — | tdo-a1 | 待开始 |
| WS-2 | host/前端/契约/门禁清点 | `reports/INVENTORY.md` 的 host/frontend 段、`reports/GATE-BASELINE.md` | 覆盖 desktop/frontend/shared/tests；24 步逐项结果 | — | tdo-a2 | 待开始 |

## 5. 轮次计划与结论

### Round <ROUND-N> 计划（PMO S1）

- 本轮要达成：G1 + G2（清点 + 基线冻结）。
- 本轮不做：不改任何业务代码、不改 runner、不改 host bundle、不引入新抽象。
- TDO 编制：2（tdo-a1 工具侧 / tdo-a2 host+前端侧）。

### Round <ROUND-N> 结论（PMO S4）

- 完成：待采集。
- 未完成 / 阻塞：待采集。
- 下轮候选：R2 diff（old→new 映射）。

## 6. PMO 上报区（唯一给主会话的摘要）

- **本轮结论**：待采集。
- **待拍板**：

| 编号 | 分歧/选项 | 选项 A | 选项 B | PMO 建议 | 最晚决策时点 |
| --- | --- | --- | --- | --- | --- |
| Q-1 | 共享文件（package.json / gate-steps / 交付脚本）谁写 | 主会话指定唯一 owner（推荐） | 两 TDO 串行 | A | R1 结束前 |
| Q-2 | 是否把新 verifier 加进 gate-steps | R4 前加（推荐） | R8 前加 | A | R3 结束前 |
| Q-3 | runner 源树重建方式 | 按注释 banner 机械拆模块（推荐） | 先整文件搬迁再拆 | A | R4 开始前 |

- **指标变化**：待采集。
- **下一轮建议编制**：TDO×2（理由：工具侧与 host/frontend 侧文件领地可切分）。
- **风险提示**：runner 源树不在库内，R4 重建可能发现手改无法机械还原；先以行为 parity 为准，不追求字节 parity。

## 7. 变更日志

| 时间 | 轮次 | 变更 | 由谁 |
| --- | --- | --- | --- |
| <DATE> | R<ROUND-N> | 建档（特化模板 signaldeck-refactor） | 主会话 |
