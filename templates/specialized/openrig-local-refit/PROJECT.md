<!-- wf-doc
run: <RUN-ID>
round: <ROUND-N>
doc: PROJECT
owner: PMO
state: pmo-plan
updated: <DATE>
-->

# PROJECT — OpenRig 本地工作流重整（不接入 OpenRig）

> 写者：PMO ｜ 主会话只读 §6（+ 本文件头状态字段）｜ 其他角色只读本文件 + `SPEC.md`
> 特化：本 run 用现有 workflow-group 本地模式重整 OpenRig；OpenRig 只是被调查/被整改的源码，不是本流程的运行底座。

## 0. 元信息

| 项 | 值 |
| --- | --- |
| run-id | `<RUN-ID>` |
| 一句话目标 | `<GOAL>` |
| 项目根 | 上游只读：`/home/dev/Desktop/deepseek/60-外部仓库/openrig`；R2 自有副本：`/home/dev/Desktop/deepseek/deepseek-项目/10-openrig-deepseek` |
| 写权限白名单 | 本 run 目录、`workflow-group/templates/specialized/openrig-local-refit/**`、`workflow-group/kickoff/openrig-local-refit*`；R2 仅 `deepseek-项目/10-openrig-deepseek/**` |
| 主会话 | 当前会话 |
| 编制 | PMO×1 / TDO×<TDO-N> / QA×1 |
| 当前轮次 | Round <ROUND-N> |
| 终止判据 | 达成：§1 判据通过且无 open S1/S2；终止：R1 环境证据不足、R2 无法在自有副本中安全验证，或用户叫停 |

## 1. 目标与成功判据

- **G1 环境可用性结论**：完成系统/Node/npm/tmux/git/网络/OpenCode/OpenRig/本地工作流工具探测，明确“安装 ≠ 可用”。
  - 判据：`reports/env-probe.md` 包含每项 PASS/WARN/FAIL/SKIP、命令、退出码/超时、证据路径。
- **G2 OpenCode 真实可用性**：对 `--help`、`auth list`、`debug paths`、`models`、`session list`、`run` 分别验证；记录哪些能完成、哪些超时/报错、配置/插件/数据库/代理是否是原因。
  - 判据：至少一次最小 `opencode run` 的真实结果（成功/失败都可），附错误名和 session 前缀，不泄露内容/凭证。
- **G3 OpenRig 盘点**：覆盖顶层目录、关键文档、runtime、daemon/queue/workflow/topology/tests/UI，并给出保留/新增/隐藏/后续删除候选。
  - 判据：`reports/openrig-inventory.md` + 目录表 + runtime 缺口表。
- **G4 重整方案**：形成不接入 OpenRig 的自有工作副本重整方案，按目录/文件列改动和回退方式。
  - 判据：`reports/round2-refit-plan.md`，每条改动有目标、验收、回退、风险。
- **G5 R2 最小验证**：在自有副本中至少完成一条 build 或 targeted test；不得直接用外部 clone 改核心。
  - 判据：构建/测试日志 + 修改清单 + 未验证项。

**反目标（明确不做）**：

- 不以本 run 启动 OpenRig daemon 或 `rig` 命令；
- 不修改 `60-外部仓库/openrig/**`；
- 不删除/移动 OpenRig 源码、不 push、不重写 Web UI；
- 不把“命令存在”当成“环境可用”。

## 2. 范围

### 2.1 范围内

- 本机环境探测，特别是 OpenCode 安装/认证/运行差异。
- OpenRig 上游源码轻量盘点与本地重整方案。
- 特化工作流模板、启动提示词、运行说明。
- R2 在自有工作副本中的最小构建/测试与改动。

### 2.2 范围外

- 不在外部上游 clone 中提交代码。
- 不实现 OpenRig 的完整重写或全量 UI 重设计。
- 不接入 OpenRig daemon/queue/workflow 作为本 run 的运行面。
- 不处理真实业务 run（如 H 盘清理）。

### 2.3 假设与依赖

- `60-外部仓库/openrig` 是只读上游参考；R2 需要先创建 `deepseek-项目/10-openrig-deepseek` 自有副本。
- `opencode` 已安装，但其实际可用性待验证；认证存在不等于 provider 可用。
- 网络代理可能对 GitHub/Node headers 造成 TLS 失败；默认代理与 `--noproxy '*'` 要分别记录。
- 本地工作流使用 Python 3 + openpyxl + pytest；R1 不依赖 OpenRig 运行。

## 3. 指标

| # | 指标 | 基线 | 目标 | 当前 | 证据来源 | 采集方式 |
| --- | --- | --- | --- | --- | --- | --- |
| M1 | 环境检查项覆盖 | 0 | ≥ 20 项，含 OpenCode 真实命令 | 待采集 | `reports/env-probe.md` | 逐项命令 |
| M2 | OpenCode 静态帮助可用率 | 未知 | 记录实际结果 | 待采集 | `reports/env-probe.md` | `--help` |
| M3 | OpenCode 真实运行结论 | 未知 | 至少一条 run 结果/错误证据 | 待采集 | `reports/env-probe.md` | `opencode run` |
| M4 | OpenRig 盘点覆盖率 | 0 | 顶层目录 + runtime + 关键文档 100% | 待采集 | `reports/openrig-inventory.md` | 文件/目录表 |
| M5 | R2 最小验证 | 未开始 | build 或 targeted test 通过 | 待采集 | `reports/round2-verify.md` | 构建日志 |

## 4. 分任务（Workstreams）

| WS | 任务 | 产出物（路径） | 验收判据 | 依赖 | 建议执行体 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| WS-1 | 环境探测（系统/Node/网络/OpenCode/OpenRig/本地 workflow） | `runs/<RUN-ID>/reports/env-probe.md`、`reports/evidence/env-*.txt` | 每项有 PASS/WARN/FAIL/SKIP + 命令 + 证据 | — | TDO-a1 | 待开始 |
| WS-2 | OpenRig 源码/文档/runtime 盘点 | `reports/openrig-inventory.md` | 覆盖顶层目录、runtime、核心模块和关键文档 | — | TDO-a2 | 待开始 |
| WS-3 | 特化工作流模板 + kickoff/run 校验 | `templates/specialized/openrig-local-refit/**`、`kickoff/openrig-local-refit*` | 新 run `doctor` PASS；SPEC/PROJECT/DECISIONS 无未填占位 | — | TDO-a3 | 待开始 |
| WS-4 | 重整方案（目录/文件级） | `reports/round2-refit-plan.md` | 每条改动含保留/新增/隐藏/删除候选 + 回退 | WS-1/WS-2 | TDO-a4 | 待开始 |
| WS-5 | R2 自有副本最小整改与验证（下一轮） | 自有副本 + `reports/round2-verify.md` | build/targeted test 通过；不碰外部 clone | WS-4 | TDO | 待开始 |

## 5. 轮次计划与结论

### Round 1 计划（PMO S1）

- 本轮要达成：环境探测 + OpenRig 盘点 + 特化模板 + 重整方案。
- 本轮不做：不启动 OpenRig、不修改上游、不做 R2 代码重构。

### Round 1 结论（PMO S4）

- 完成：待采集。
- 未完成 / 阻塞：待采集。
- 下轮候选：R2 自有副本建立 + 最小 OpenCode-first 整改。

## 6. PMO 上报区（唯一给主会话的摘要）

- **本轮结论**：待采集。
- **待拍板**：

| 编号 | 分歧/选项 | 选项 A | 选项 B | PMO 建议 | 最晚决策时点 |
| --- | --- | --- | --- | --- | --- |
| Q-1 | R2 自有副本位置 | `deepseek-项目/10-openrig-deepseek`（推荐） | 其他自有路径 | A | R1 结束前 |
| Q-2 | 非 OpenCode runtime 处理 | 暂留、默认隐藏（推荐） | R2 立即删除 | A | R2 开始前 |
| Q-3 | OpenCode provider 不可用时 | 先修环境/换 endpoint（推荐） | 改用 stub/fake 只验适配器 | 依据 WS-1 结论 | R2 开始前 |

- **指标变化**：待采集。
- **下一轮建议编制**：TDO×1（理由：R2 单线程改同一源码，避免并发冲突）。
- **风险提示**：OpenCode 安装存在但真实运行可能不可用；不得把安装成功当成链路可用。

## 7. 变更日志

| 时间 | 轮次 | 变更 | 由谁 |
| --- | --- | --- | --- |
| <DATE> | R<ROUND-N> | 建档（特化模板 openrig-local-refit） | 主会话 |
