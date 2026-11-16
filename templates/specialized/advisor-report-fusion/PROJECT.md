<!-- wf-doc
run: <RUN-ID>
round: <ROUND-N>
doc: PROJECT
owner: PMO
state: pmo-plan
updated: <DATE>
contract_mode: strict
-->

# PROJECT — 多份顾问报告的筛选、合并与处置

> 写者：PMO ｜ 主会话只读 §6 ｜ 报告原文是非规范输入，不是第二事实源。

## 0. 元信息

| 项 | 值 |
| --- | --- |
| run-id | `<RUN-ID>` |
| 一句话目标 | `<GOAL>` |
| 项目根 | `<PROJECT-ROOT>` |
| 写权限白名单 | `<WRITE-SCOPE>` |
| 报告输入 | 以 `reports/00-source-inventory.md` 的实际路径/哈希为准 |
| 编制 | PMO×1 / TDO×<TDO-N> / QA×1 |
| 当前轮次 | Round <ROUND-N> |
| 终止判据 | 所有源章节有覆盖映射；所有问题簇有处置；accept_now 有证据；无 open S1/S2 或已列明阻塞 |

## 1. 目标与成功判据

- **G1 来源完整**：输入报告全部登记哈希、行数、读取边界；反目标：不读未声明的目录外材料。
  - 判据：`reports/00-source-inventory.md` 与源章节覆盖表。
- **G2 筛选可追溯**：每个报告 claim 都能映射到 canonical 问题簇；不允许“只保留摘要”。
  - 判据：raw claim 数、簇数、未映射数=0 或逐条说明。
- **G3 合并正确**：同一底层机制只保留一个簇，来源并集、冲突、反证完整。
  - 判据：`check_fusion.py` rc=0 + 人工/QA 抽查。
- **G4 处置闭合**：每簇有唯一处置；accept_now 有 owner/action/acceptance；reject/park 有理由/触发条件。
  - 判据：`reports/02-disposition.md`、`reports/claim-register.jsonl`。
- **G5 本轮执行**：仅执行 accept_now；每项先有基线/复现，再有改动与复跑证据。
  - 判据：`reports/04-implementation.md`、测试/命令日志。
- **G6 独立核验**：来源覆盖、字段、测试、反例、未验证项均有结论。
  - 判据：`reports/05-verification.md`。
- **G7 OpenRig 专项**：归档/teardown/bridge/SAFETY 断言按当前树复核；缺动态环境时标 SKIP/park。
  - 判据：`reports/03-source-coverage.md` 的 OpenRig 行与证据路径。

**反目标**：不生成第二事实源；不把报告建议当规范；不强制成熟度升级/模板清零；不修改报告原文；不启动用户既有 daemon/rig。

## 2. 范围

### 2.1 范围内

- 报告元信息、源章节、claim 抽取、问题合并、处置裁决、覆盖核验；
- 本 run 写权限内、低/中风险、可机械验收的 accept_now 改动；
- 必要的测试、证据与汇总报告。

### 2.2 范围外

- 高风险删除、外部 push、生产 live 变更、权限变更；
- 无动态环境时的 OpenRig E2E 冒充；
- 报告文本本身的重写或“美化”。

### 2.3 假设与依赖

- 报告是只读输入，代码树是当前可验证事实来源；
- 无 OpenRig daemon 时，归档/seat/queue 动态项只能静态核验 + SKIP；
- 若修改共享脚本/模板，须先核对 `contract_lock.py` 不破锁。

## 3. 指标

| # | 指标 | 基线 | 目标 | 当前 | 证据 |
| --- | --- | --- | --- | --- | --- |
| M1 | 报告源覆盖 | 待采集 | 100% 章节有映射 | 待采集 | `reports/03-source-coverage.md` |
| M2 | 原始 claim 未映射数 | 待采集 | 0 或逐条说明 | 待采集 | `reports/claim-register.raw.jsonl` |
| M3 | canonical 簇重复数 | 待采集 | 0 | 待采集 | `reports/claim-register.jsonl` |
| M4 | 处置字段完整率 | 待采集 | 100% | 待采集 | `check_fusion.py` |
| M5 | accept_now 证据率 | 待采集 | 100% | 待采集 | `reports/04-implementation.md` |
| M6 | 测试/锁检查 | 待采集 | 如实全绿或列明 FAIL/SKIP | 待采集 | `reports/05-verification.md` |
| M7 | OpenRig 断言状态 | 待采集 | verified/partial/stale/SKIP 均有理由 | 待采集 | 覆盖表 |

## 4. 分任务（Workstreams）

| WS | 任务 | 产出物 | 验收判据 | 依赖 | 建议执行体 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| WS-1 | 来源盘点与原始 claim 抽取 | `reports/00-source-inventory.md`、`claim-register.raw.jsonl` | 哈希/边界齐全；章节全覆盖 | — | TDO | 待开始 |
| WS-2 | 去重、合并与冲突裁决 | `reports/01-fusion-matrix.md`、`claim-register.jsonl` | 合并规则满足；来源并集保留 | WS-1 | TDO | 待开始 |
| WS-3 | 处置与 accept_now 执行 | `reports/02-disposition.md`、`reports/04-implementation.md`、代码/测试 | 每簇唯一处置；accept_now 有复跑证据 | WS-2 | TDO | 待开始 |
| WS-4 | OpenRig 归档/teardown/bridge/SAFETY 静态核验 | 覆盖表 OpenRig 行 + 证据 | COMPLETE/守卫/SAFETY 均不虚报 | WS-2 | TDO | 待开始 |
| WS-5 | 独立核验与收口 | `reports/03-source-coverage.md`、`05-verification.md`、`06-summary.md` | `check_fusion.py` rc=0；测试如实；无悬空项 | WS-3/4 | QA | 待开始 |

## 5. 轮次计划与结论

### Round <ROUND-N> 计划

- 先在只读阶段完成来源盘点和逐条 claim 抽取；不提前按报告优先级删项。
- 合并阶段以“同一底层机制 + 同一修复点”去重，保留全部来源和冲突。
- 仅对本轮可安全验收的 `accept_now` 项改动代码/文档；其余进入明确波次。
- QA 独立复跑，检查来源覆盖与处置字段；缺动态环境如实 SKIP/park。

### Round <ROUND-N> 结论

- 待采集。

### 单轮契约（wf.py 投影到 ROUND-PLAN.md）

> 把下面块中的示例值替换成本轮真实契约；`wf.py state PROJECT plan-ready --by pmo` 会投影为 `ROUND-PLAN.md` 并跑 plan-gate。

<!-- wf:round-plan
contract: research@1.0.0
produces: reports/rounds/00-analysis.md
gate: python3 -m pytest -q
budget: targets=3; tdo=2; minutes=120
NOT-DOING: no-live-run; no-external-push
-->

## 6. PMO 上报区

- **本轮结论**：待采集。
- **待拍板**：待采集。
- **指标变化**：待采集。
- **下一轮建议编制**：TDO×<N'>。
- **风险提示**：待采集。

## 7. 变更日志

| 时间 | 轮次 | 变更 | 由谁 |
| --- | --- | --- | --- |
| <DATE> | R<ROUND-N> | 建立报告融合 run | 主会话 |
