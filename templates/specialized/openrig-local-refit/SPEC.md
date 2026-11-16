# SPEC — OpenRig 本地工作流重整（不接入 OpenRig 自身）

## 0. 分层声明

baseline: composite/refactor-decompose@1.0.0
contracts: research@1.0.0, diff@1.0.0, architecture@1.0.0, optimize@1.0.0, verify@1.0.0

> 本文件是本 run 的**特化规则**，与通用 `WORKFLOW.md` / `roles/*` 冲突时以本文件为准。
> 通用规则仍然有效：文档即接口、单一写者、STATUS 加锁逐条提交、分歧不落地。
>
> **本 run 的硬边界：不启动 OpenRig daemon、不执行 `rig up`、不把 OpenRig 作为本流程的运行底座。**
> 本 run 使用 `workflow-group` 现有本地模式：四件套 + `wf.py` + OpenCode 会话；OpenRig 只作为**被调查/被整改的源码**。

## 1. 任务

对 OpenRig 做一次“先探测、再重整”的本地工作流试点：

1. 探测本机实际运行环境，区分「命令存在」与「命令可用」；
2. 盘点 OpenRig 源码/文档/运行时的真实覆盖面；
3. 产出 OpenRig 本地重整的目录/文件级方案；
4. 在**自有工作副本**中执行 R2 重整，不回写外部上游 clone；
5. 所有结论必须带可复跑命令、退出码或路径证据；禁止把“已安装”当成“可用”。

## 2. 目标工作副本与写权限

| 路径 | 权限 | 用途 |
| --- | --- | --- |
| `workflow-group/templates/specialized/openrig-local-refit/**` | 可写 | 本特化工作流模板 |
| `workflow-group/kickoff/openrig-local-refit*` | 可写 | 启动提示词/目标文件 |
| `workflow-group/runs/<RUN-ID>/**` | 可写 | 四件套、报告、证据 |
| `../deepseek-项目/10-openrig-deepseek/**` | R2 可写 | **自有工作副本**，从上游 clone 后独立管理 |
| `60-外部仓库/openrig/**` | **只读** | 上游参考/证据；不得修改、不得提交、不得 push |
| `workflow-group/roles/**`、`WORKFLOW.md`、`scripts/wf.py` | 只读（主会话例外） | 通用流程；本 run 不改造流程本体 |
| KB 正式域（`00-overview/` 等 8 个目录） | 只读 | 不写正式正文 |

> R2 开始前必须确认 `../deepseek-项目/10-openrig-deepseek/` 存在且是独立仓库/工作副本；不得直接在 `60-外部仓库/openrig` 上改核心源码。

## 3. 全内容覆盖要求（硬）

- **环境探测**：系统、Node、npm、tmux、git、网络、OpenCode、OpenRig、本地工作流工具逐项有结论；每项至少一个可复跑命令。
- **OpenCode 可用性**：必须分别检查：
  - 安装路径和版本；
  - 认证是否存在；
  - `--help` 类静态命令是否正常；
  - `models`、`session list`、`run` 等真实命令是否超时/报错；
  - 配置文件/插件/数据库对启动的影响；
  - 代理、网络、provider 端点的影响；
  - 至少一次最小真实 `opencode run`（或在明确预算/用户不允许时记录未执行）。
- **OpenRig 盘点**：至少覆盖：
  - 顶层目录/关键文档；
  - `package.json`、engines、构建入口；
  - 支持的 runtime 列表与 OpenCode 缺口；
  - daemon / queue / workflow / topology / UI / tests / docs 的目录归属；
  - 可删、可隐藏、必须保留的候选清单。
- **重整方案**：每个拟改动文件/目录必须有「保留/新增/隐藏/后续删除」结论和理由；不允许只给“重构一下”的空话。

## 4. 证据格式（本任务特化）

每条环境结论使用以下格式之一：

```text
[PASS] <检查项> | cmd: <命令> | exit: <码> | evidence: <路径或摘要>
[WARN] <检查项> | cmd: <命令> | exit: <码/超时> | why: <影响> | evidence: <路径或摘要>
[FAIL] <检查项> | cmd: <命令> | exit: <码/超时> | blocker: <阻塞什么> | evidence: <路径或摘要>
[SKIP] <检查项> | why: <未执行原因> | 后续: <补测方式>
```

其他要求：

- 记录命令的**超时**，不能把 20s 超时写成“不可用”或“可用”；要写“超时，待确认”。
- 不打印 API key/token/password/完整 auth 文件；只登记“存在/不存在”。
- 网络检查至少分别测试：默认代理 vs `--noproxy '*'`；GitHub API、raw、npm registry、nodejs.org、OpenCode 端点。
- OpenCode 的 JSON/日志证据只保留类型、错误名、sessionID 前缀；不粘贴完整对话内容。

## 5. 禁止

- 不启动 OpenRig daemon；不运行 `rig up`、`rig workflow`、`rig queue` 作为本 run 的执行面。
- 不修改 `60-外部仓库/openrig/**`；不把 R2 改动写进外部上游 clone。
- 不删除、不移动 OpenRig 源码或当前工作区文件；R2 删除类动作必须先出清单并单独拍板。
- 不把 OpenCode 安装成功 / OpenRig build 成功 / 命令 `--help` 成功写成“运行时可用”。
- 不把带 token 的配置、日志正文、用户对话写入 run 报告。
- 不 `git add -A`；R2 提交只按显式 pathspec，且只在自有工作副本提交。
- 不 push 外部 `origin`。

## 6. 完成定义（DoD）

- R1：
  - `reports/env-probe.md`：环境项 PASS/WARN/FAIL/SKIP 完整，含 OpenCode 安装 vs 真实可用性差异；
  - `reports/openrig-inventory.md`：源码/文档/runtime/功能域全量盘点；
  - `reports/round2-refit-plan.md`：目录/文件级重整方案；
  - `PROJECT.md` §6 有主会话可拍板的结论和风险；
  - ISSUES 无 open S1/S2。
- R2：
  - 自有工作副本存在且与上游来源关系记录清楚；
  - OpenCode-first 的最小改动可构建/可测试（至少 build + targeted test）；
  - 修改清单与回退方式清楚；
  - 未验证项明确列出，不冒充完成。

## 7. 波次建议

- **R1**：环境探测（WS-1）+ OpenRig 盘点（WS-2）+ 特化工作流/模板校验（WS-3）+ 重整方案（WS-4）。
- **R2**：在 `../deepseek-项目/10-openrig-deepseek/` 建自有工作副本，执行最小重整（WS-5）；先在 fake/隔离环境验证，再考虑真实 opencode smoke。
- R2 不默认执行删除、全量 UI 重写或非 OpenCode runtime 清理；这些必须另立决策。
