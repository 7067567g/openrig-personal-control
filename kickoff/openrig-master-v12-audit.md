# OpenRig Workflow Master v1.1 → v1.2：核对与核心计划

> 核对时间：2026-10-20 05:56 CST
> 核对对象：`workflow-group/templates/specialized/openrig-workflow-master`（母版）及其全部关联模板、测试、验证、run、kickoff；另核对 `deepseek-项目/10-openrig-deepseek` 与 `60-外部仓库/openrig` 的边界。
> 本文件是启动前事实摘要，不替代 run 内 `PROJECT.md` / `DECISIONS.md`。

## 1. 现行事实

| 项 | 事实 | 证据 |
| --- | --- | --- |
| 母版版本 | `VERSION=1.1.0`，但工作树已含 audit-fix 的 Unreleased 改动（doctor 假 PASS 硬化、OpenCode v2 fail-closed、baseline 元数据） | `VERSION`、`CHANGELOG.md` |
| 全仓测试 | `cd workflow-group && python3 -m pytest tests -q` → **115 passed** | 2026-10-20 核对输出 |
| 母版基线 | `sha256sum -c BASELINE-post.sha256` → **35/35 OK** | 母版根目录实测 |
| 最近 workflow 收口 | `openrig-audit-fix-20261020`: QA_PASS，open S1/S2=0，doctor PASS | `runs/openrig-audit-fix-20261020/` |
| Parent project OpenRig 副本 | `deepseek-项目/10-openrig-deepseek` HEAD `f62c3af`，分支 `feat/opencode-dsh-runner`，工作区 clean；上游只读 clone `60-外部仓库/openrig` 不可改 | `git status --branch` |
| OpenRig fork 全量检查 | OpenCode+DSH 代码、真实 5-seat E2E、resume、workflow 均 PASS；daemon/CLI 余项为 upstream 环境/路径问题（S3） | `runs/openrig-full-verify-20261019/reports/FULL-CHECK.md` |
| 执行面能力 | OpenRig workflow 支持 `next_hop.on` 分支边与 `loop_guards.max_hops`；canonical 例子 `branched-remediation.yaml` 已用失败分支形成有界返工环 | parent project 源码与 built-in spec |
| 执行面限制 | 单个 workflow 实例仍是单 active frontier；失败分支只能映射到静态 step id，不能按 QA 报告内容动态选择 TDO | parent project `workflow-types.ts` / `workflow-validator.ts` |
| 基线缺口 | v1.0 无 pre baseline；v1.1 只有 post baseline；本轮需建立 v1.2 pre/post | `BASELINE-post.sha256` 头 |

## 2. v1.1 遗留候选与处置

| 候选 | 影响 | v1.2 处置 |
| --- | --- | --- |
| bridge/bundle 路径相对化，bundle 可整体搬迁 | 高，跨 output-dir 清单/桥接不可比 | **纳入核心**：bridge schema v2 |
| workflow graph 缺 QA→TDO 返工边 | 高，QA 失败只能靠聊天/手工 resume | **纳入核心**：有界返工环 + validate/instantiate 证据 |
| 未跟踪母版缺 pre/post baseline | 高，发布不可复算 | **纳入核心**：v1.2 pre/post baseline + validation |
| P-004：doctor 清单漏 runId/bundleDir/openrigCli | 中，文档与实现漂移 | **纳入核心**：文档补齐 |
| DECISIONS 缺写入审计 / 单一写者强制 | 中高，控制面治理 | **v1.3**：先冻结契约，避免与本轮产品改动混写 |
| 授权存在 ≠ packet 创建 | 中高，执行面治理 | **v1.3**：需 queue/workflow 真实查询契约 |
| SAFETY pod/fragment + gated actions 执行器 | 高，但面积大且安全关键 | **v1.3**：v1.2 只保留契约并删除“v1.2 实现”的错误承诺 |
| queue → STATUS 可审计只读回填 | 中 | **v1.3** |
| 多项目 run registry + secret-free bridge refs | 中 | **v1.3** |
| 自动成本/延迟采集；Tier B generator self-check | 中低 | **v1.3** |

## 3. v1.2 核心计划（建议 release 定义）

**主题：可搬迁、可返工、可复算的可发布母版。**

### G1 Bridge v2 / bundle 可搬迁

- `OPENRIG-BRIDGE.json` 升 `schemaVersion: 2`，bundle 内路径改为相对路径（`bundleDir: "."`、`rigSpec: "rig.yaml"`、`workflowSpec: "workflow.yaml"`）。
- `doctor` 兼容读取 v1 legacy absolute-path bridge；v2 强制相对路径且拒绝逃逸 bundle。
- 同一 run、同一输入渲染到两个 output-dir，5 个生成产物逐字节一致（`renderedAt` 仅在 manifest，不参与产物身份）。
- 新增正/负例测试：合法 v2、路径逃逸、旧 v1 读取、跨目录一致性。

### G2 有界 QA→TDO 返工

- 在 `workflow.yaml.tpl` 增加显式失败分支，使 QA 失败可回到正确 TDO 并再次进入 QA。
- 必须用 `next_hop.on` + `loop_guards.max_hops` 的既有引擎语义，不新增未实现的引擎 API。
- 推荐先由 PMO 在 D-xxx 中二选一：**分支专属 QA**（`qa_oc.failed→implement_opencode`、`qa_dsh.failed→implement_dsh`）或 **单 QA + PMO 返工分派**；验收看“失败路径确实回到对应 TDO 且能再次 QA”，不只看图上有边。
- 证据：`rig workflow validate --json`、instantiate、失败 exit 投影/返工 frontier、`max_hops` 触顶语义。

### G3 发布完整性

- 建 `BASELINE-pre.sha256`（动代码前）与最终 `BASELINE-post.sha256`（收口后）。
- `VERSION=1.2.0`；把当前 Unreleased audit-fix 归并到 `## 1.2.0`；`README.md`/`ARCHITECTURE.md`/`SPEC.md` 与实现同步；新增 `validation/v1.2.0/RELEASE.md`。
- P-004 修复：doctor 清单补 `runId`、`bundleDir`、`openrigCli` 三项。
- `CHANGELOG.md` 同时保留 `## 1.3 候选`，接住本轮明确延后的候选。

### G4 验证与收口

- `pytest workflow-group/tests -q` 全绿；新增测试覆盖 G1/G2。
- render dry-run/写盘、bridge doctor live/negative、workflow validate/instantiate、一次返工投影、teardown 无残留。
- QA 逐条 PASS/WARN/FAIL/SKIP；open S1/S2=0；无未 owner 的待办。
- 不修改 parent OpenRig 源码；如必须改，单独 D-xxx + 独立 run，不在本轮顺手做。

## 4. 明确非目标

- 不实现 SAFETY 执行引擎；不声称已实现。
- 不实现 DECISIONS hash-chain/单一写者强制；不实现授权→packet 自动核对。
- 不做 queue→STATUS 双写/回填、多项目 registry、成本遥测。
- 不重写 OpenRig daemon/CLI/TUI/UI，不删除任何 runtime adapter，不 push。
- 不修改 `60-外部仓库/openrig`；默认不修改 `deepseek-项目/10-openrig-deepseek`。

## 5. 工作流编制

- run-id：`openrig-master-v12-20261020`
- 模板：`workflow-group/templates/specialized/openrig-master-v12`
- 控制面：workflow-group 四件套
- 执行面：managed isolated OpenRig 5-seat rig（`openrig-openrig-master-v12-20261020`）
- 编制：PMO×1 / TDO×2 / QA×1
- 拆分：TDO-OC 负责 generator/bridge/tests；TDO-DSH 负责 workflow rework/baseline 工具/定向测试；MAIN 负责 release docs/baseline 收口；QA 独立复核。文件面不重叠。
