<!-- wf-doc
run: <RUN-ID>
round: <ROUND-N>
doc: PROJECT
owner: PMO
state: pmo-plan
updated: <DATE>
-->

# PROJECT — OpenRig Workflow Master v1.2.0 更新

> 写者：PMO ｜ 主会话只读 §6 ｜ 本文件是控制面权威；OpenRig queue/workflow 是执行面权威。
> 启动前核对见 `workflow-group/kickoff/openrig-master-v12-audit.md`。

## 0. 元信息

| 项 | 值 |
| --- | --- |
| run-id | `<RUN-ID>` |
| 一句话目标 | `<GOAL>` |
| 项目根 | `<PROJECT-ROOT>` |
| 写权限白名单 | `<WRITE-SCOPE>` |
| OpenRig 工作目录 | `runs/<RUN-ID>/openrig/`（由 render_master.py 生成） |
| 隔离 home | `/tmp/openrig-workflow-<RUN-ID>` |
| 默认 rig/workflow | 生成的 rig.yaml / workflow.yaml（唯一名字） |
| 编制 | PMO×1 / TDO×2 / QA×1 |
| 当前轮次 | Round 1 |
| 终止判据 | v1.2.0 核心面闭环；QA PASS；open S1/S2=0；baseline/证据/teardown 完整 |

## 1. 目标与成功判据

- **G1（Bridge v2 / 可搬迁）**：bridge `schemaVersion=2`，bundle 内路径相对且不得逃逸；doctor 兼容 v1 legacy；同 run 同参数渲染到两个不同 output-dir 的 5 个产物逐字节一致；正例/负例测试全绿。
- **G2（有界 QA→TDO 返工）**：`workflow.yaml.tpl` 有显式失败返工边；失败能回到正确 TDO 并再次进入 QA；使用既有 `next_hop.on` + `loop_guards.max_hops`；validate 及一次返工投影有证据。
- **G3（发布完整性）**：`VERSION=1.2.0`；Unreleased 归并入 `## 1.2.0`；`## 1.3 候选` 接住延后项；README/ARCHITECTURE/SPEC/validation 同步；P-004 doctor 清单补齐；v1.2 pre/post baseline 均可复算。
- **G4（质量）**：`pytest workflow-group/tests -q` 全绿；render dry-run/写盘、bridge doctor live/negative、workflow validate/instantiate、teardown 均有 rc+证据。
- **G5（边界）**：不修改 parent OpenRig 源码、不改 KB 正式域、不 push、不删除、不偷扩 v1.3 候选。
- **G6（治理）**：QA 每个判据有 PASS/WARN/FAIL/SKIP；open S1/S2=0；PROJECT §6 无主待办=0；跨轮项有 owner+去向。

**反目标**：

- 不在本 run 实现 SAFETY 执行器、DECISIONS hash-chain、授权→packet 自动核对、queue→STATUS 回填、多项目 registry、成本遥测。
- 不把“图上有边”写成“返工已真实可用”；必须有失败路径投影证据。
- 不用绝对路径哈希声称 bundle 可搬迁。

## 2. 范围

### 2.1 范围内

- `openrig-workflow-master` 的 generator、bridge doctor、workflow 模板、测试、release 元数据与 validation；
- 本 run 四件套、报告、证据；
- 由 `render_master.py` 生成的本 run OpenRig bundle；
- 隔离 OpenRig daemon/rig/workflow 的启动、验证、返工投影与 teardown。

### 2.2 范围外

- `deepseek-项目/10-openrig-deepseek` 源码与 `60-外部仓库/openrig`；
- KB 正式域正文；
- 非本 run 的 daemon/tmux/session；
- 发布/push/删除/权限变更；
- v1.3 候选实现。

### 2.3 假设与依赖

- parent OpenRig 可执行 entry 为 `node /home/dev/Desktop/deepseek/deepseek-项目/10-openrig-deepseek/packages/cli/dist/bin-wrapper.js`；
- OpenCode/DSH bin 使用绝对路径，provider 认证由 runtime 自管；
- 5 seats 在 4 vCPU / 5.8GB 下可启动，实际活跃 agent ≤2；
- 真实模型调用只在最小 smoke 中使用；认证缺失如实 BLOCKED，不写 PASS。

## 3. 指标

| # | 指标 | 目标 | 当前 | 证据 |
| --- | --- | --- | --- | --- |
| M1 | 测试 | 全仓 pytest rc=0 | 待采集 | pytest 日志 |
| M2 | bridge v2 | schema=2 + 相对路径 + 逃逸拒绝 | 待采集 | doctor 正/负例 |
| M3 | 跨目录产物 | 5/5 逐字节一致 | 待采集 | 两目录 sha256 |
| M4 | v1 legacy | doctor 仍可读 | 待采集 | legacy bridge 探针 |
| M5 | 返工边 | validate rc=0 + 失败投影到 TDO | 待采集 | workflow validate/show/project |
| M6 | release | VERSION=1.2.0 + CHANGELOG 双小节 | 待采集 | 文件 + grep |
| M7 | baseline | pre/post 存在，post 全量 rc=0 | 待采集 | sha256sum -c |
| M8 | E2E | rig up 5/5 ready；validate/instantiate | 待采集 | ps/workflow JSON |
| M9 | QA | 判据 100% 有结论；open S1/S2=0 | 待采集 | QA 报告 |
| M10 | 清理 | 本 run 0 残留 | 待采集 | teardown 证据 |

## 4. 分任务（Workstreams）

> WS-A 与 WS-B 文件面互斥，可并行；MAIN 的 release 元数据必须在两者 QA PASS 后串行收口。

| WS | 任务 | 产出物 | 验收判据 | 依赖 | 执行体 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| WS-A | Bridge v2 / bundle 可搬迁 | `render_master.py`、`tools/openrig_bridge.py`、`tests/test_render_master_portability.py`、`tests/test_openrig_bridge_doctor.py` | schema=2；相对路径；跨目录 5/5 一致；v1 legacy 兼容；负例指名字段 | — | TDO-OC | 待开始 |
| WS-B | 有界 QA→TDO 返工 + baseline 工具 | `templates/workflow.yaml.tpl`、`tests/test_workflow_rework.py`、可选 `tools/master_baseline.py`、`tests/test_master_release.py` | validate rc=0；失败投影回正确 TDO 并再入 QA；max_hops 可复核；不新增引擎 API | — | TDO-DSH | 待开始 |
| WS-C | Release 元数据与 baseline 收口 | `VERSION`、`CHANGELOG.md`、`README.md`、`ARCHITECTURE.md`、`SPEC.md`、`BASELINE-pre.sha256`、`BASELINE-post.sha256`、`validation/v1.2.0/**` | v1.2.0 + 1.3 候选；pre/post 可复算；文档与实现一致；P-004 修复 | WS-A + WS-B QA PASS | MAIN | 待开始 |
| QA-JOIN | 独立验收 | `QA-REPORT.md`、ISSUES、evidence | M1–M10 逐项结论；open S1/S2=0 | WS-A + WS-B | QA | 待开始 |

### 4.1 证据契约

1. 每个 packet 必有：qitem id、workflow step id、session id（脱敏）、transcript/抓取指针。
2. 每个改动有：改前/改后 sha256、可复跑命令、rc、原始输出。
3. 每个修复有反证：修复前 fail/bug 输出 + 修复后 pass 输出。
4. 写入 `runs/<RUN-ID>/evidence/{oc,dsh,qa,main}/`，不得贴 secret。

### 4.2 工作包 brief 要点

- **WS-A**：不改 workflow.yaml.tpl、不改 release 文档、不写 baseline；v2 路径解析必须在 `--run-dir` 内，拒绝 `../` 与绝对路径逃逸；v1 bridge 只读兼容，不静默改写。
- **WS-B**：不新增 OpenRig 引擎字段；先读 parent 的 `workflow-types.ts`、`workflow-validator.ts`、`branched-remediation.yaml`；返工形态有歧义时进 PROJECT §6，不自选。
- **TDO 共同**：不改 `PROJECT.md`/`DECISIONS.md`/`ISSUES.xlsx`/`VERSION`/`CHANGELOG.md`/release 文档；`--also` 只带本 run 产物。
- **QA**：独立复跑，不采信交接 note 数字；QA 初检若因返工边设计不成立，登记 S1/S2。

## 5. 轮次计划与结论

### Round 1 计划

- PMO 复核本预填计划，确认 G1–G6、文件面与返工设计选项；必要时更新 §4/§5。
- WS-A/WS-B 并行执行；活跃 agent ≤2；互不改文件。
- QA 联检后由 MAIN 统一 release 收口与 baseline；不得在 QA 前写最终 baseline。
- 最后执行真实 E2E 的 validate/instantiate/失败返工投影/teardown。

### Round 1 结论

- 待采集。

## 6. PMO 上报区

- **本轮结论**：待采集。
- **待拍板**：返工图形态若存在两个合法方案，按“选项 A / 选项 B / PMO 建议 / 最晚决策时点”上报。
- **指标变化**：待采集。
- **下一轮建议编制**：待采集。
- **风险提示**：待采集。

## 7. 变更日志

| 时间 | 轮次 | 变更 | 由谁 |
| --- | --- | --- | --- |
| <DATE> | R1 | 从 openrig-master-v12 模板实例化；预填 v1.2 核心计划 | 主会话 |
