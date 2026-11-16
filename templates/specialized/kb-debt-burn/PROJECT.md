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
> 特化：本文件已预填 KB 欠账清理的判据/范围/分区；PMO 只需校验、细化与补 §6。

## 0. 元信息

| 项 | 值 |
| --- | --- |
| run-id | `<RUN-ID>` |
| 一句话目标 | `<GOAL>` |
| 项目根 | `<PROJECT-ROOT>`（真实项目 run 必填；跨仓只读引用写这里） |
| 写权限白名单 | `<WRITE-SCOPE>`（TDO 只许改这些路径；违反按事故记 ISSUES） |
| 主会话 | 人/主会话模型 |
| 编制 | PMO×1 / TDO×<TDO-N> / QA×1 |
| 当前轮次 | Round <ROUND-N> |
| 终止判据 | 达成：§1 全部判据通过且无 open S1/S2；终止：连续 2 轮无进展、额度窗口结束或主会话叫停 |

## 1. 目标与成功判据

- **G1 方法论入库**：`_reference/方法论待入库-20260924/` 4 篇 100% 处置；`05-methodology/` 产出 1–2 篇 canonical 正文（frontmatter 完整、`source` 指向来源目录、`applies-to-task: gray-test`、`not-for` 明确），`validate all` 0 FAIL。
  - 判据：4/4 处置表 + 正文文件路径 + `node scripts/kb-validate.mjs validate` 输出。
- **G2 检索可测化**：`scripts/kb-recall-eval.mjs`（+ 单测）可一条命令跑出 57 条金问题的 hit@1/2/3 与未命中清单。
  - 判据：`node --test tests/kb-recall-eval.test.mjs` 通过 + `reports/WS6-eval-baseline.md` 数字。
- **G3 金问题语义抽检**：10 条金问题补「期望答案要点」，人工/Agent 抽检给出通过/不通过。
  - 判据：`00-overview/golden-questions.md` 相关行 + 抽检结论。
- **G4 I-08 样本补评**：12 个样本按 §1 同口径补 E/R 评分并回写评估文档与 `content-review-queue.md` I-08 行。
  - 判据：12/12 有分、有理由、有证据；queue 行状态更新。
- **G5 `_reference` 收口**：12 个未跟踪文件 12/12 定案，`_reference/README.md` 记录与磁盘一致。
  - 判据：处置表 + README 记录；未获用户确认前不删除。

**反目标（明确不做）**：
- 不改项目仓（`../deepseek-项目/**`），不动其他 `_reference/` 子目录；
- 不虚构评测数字与评分；不做无证据的大重构；不删除源素材。

## 2. 范围

### 2.1 范围内（写权限见 SPEC §2）
- `05-methodology/**`（WS-1）
- `scripts/**`、`tests/**`（WS-2）
- `03-web-game/00-overview/**`、`content-review-queue.md`（WS-4）
- `_reference/**`（WS-5，仅根目录 12 文件 + README.md）
- `00-overview/**`（WS-3，R2）
- run 目录 `runs/<RUN-ID>/**`（所有 WS 的报告与进度）

### 2.2 范围外
- KB 其余正式域（`01/02/04/06/99-*`）：只读；
- `../deepseek-项目/**`、`../归档/**`：只读（灰测样本源件按需读取）；
- 生成视图 `00-overview/kb-map.md`、`architecture-map.md` 等：只通过 `kb-generate-views.mjs` 更新。

### 2.3 假设与依赖
- 灰测样本源件在 `../归档/02-内容包与快照/灰测样本源件-20260924/` 可读；
- 本机 node/npm 可用；KB 门禁脚本已入库；
- `_reference` 12 文件的去留涉及删除时必须由主会话升级到用户确认。

## 3. 指标

| # | 指标 | 基线 | 目标 | 当前 | 证据来源 | 采集方式 |
| --- | --- | --- | --- | --- | --- | --- |
| M1 | 方法论素材处置率 | 0/4 | 4/4 | 待采集 | `reports/WS1-ingest.md` | 逐文件处置表 |
| M2 | 检索评测工具 | 无 | 有 + 单测通过 | 待采集 | `scripts/kb-recall-eval.mjs` | `node --test` |
| M3 | 金问题 hit@1–2 比例 | 未测 | 有数字 + 未命中清单 | 待采集 | `reports/WS6-eval-baseline.md` | 工具实跑 57 条 |
| M4 | 样本评分覆盖 | 0/12 | 12/12 | 待采集 | 评估文档 §12 样本节 | 逐样本分+理由 |
| M5 | `_reference` 记录一致性 | 矛盾 | 一致 | 待采集 | `_reference/README.md` | 文件清单对照 |
| M6 | 全量门禁 | 绿（改动前） | 绿（改动后） | 待采集 | CI/本地输出 | `validate all` + `genviews --check` + `hygiene` |

## 4. 分任务（Workstreams）

| WS | 任务 | 产出物（路径） | 验收判据 | 依赖 | 建议执行体 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| WS-1 | 4 篇方法论素材裁定 + 正式正文入库 | `05-methodology/<新正文>.md`、`reports/WS1-ingest.md` | 4/4 处置；validate 相关域 0 FAIL | — | TDO | 待开始 |
| WS-2 | 检索评测工具 + 单测 | `scripts/kb-recall-eval.mjs`、`tests/kb-recall-eval.test.mjs`、`reports/WS2-tool.md` | 单测通过；命令可复现 hit 输出 | — | TDO | 待开始 |
| WS-4 | 12 样本 E/R 补评 + I-08 台账回写 | `03-web-game/00-overview/ds-gray-test-samples-evaluation.md`、`content-review-queue.md`、`reports/WS4-samples.md` | 12/12 有分+理由+证据 | — | TDO | 待开始 |
| WS-5 | `_reference` 12 文件去留定案 + 记录修正 | `_reference/README.md`、`reports/WS5-reference.md` | 12/12 有处置；不删源件 | — | TDO | 待开始 |
| WS-8 | 素材与既有正文的重复/冲突取证 | `reports/WS8-crosscheck.md` | 覆盖 4 篇 × 全库相关正文；给出冲突清单 | — | TDO | 待开始 |
| WS-3 | GQ 期望答案要点 + task-router 路由 + 注册表同步 | `00-overview/golden-questions.md`、`00-overview/task-router.md`、生成视图 | validate/GQ/genviews 全绿 | WS-1/WS-8 | TDO | 待开始 |
| WS-6 | 57 条 GQ 实跑基线 + 10 条语义抽检 | `reports/WS6-eval-baseline.md` | 数字可复跑；未命中清单完整 | WS-2 | TDO | 待开始 |

> 详细文件边界与证据格式见 `SPEC.md`；R1 = WS-1/2/4/5/8，R2 = WS-3/6 + 修复片。

## 5. 轮次计划与结论

### Round <ROUND-N> 计划（PMO S1）
- R1 目标：WS-1/2/4/5/8 五路并行完成扫描与处置，产出 5 份报告与各自改动。
- 本轮不做：`00-overview/**` 与评测基线（留给 R2）。

### Round <ROUND-N> 结论（PMO S4）
- 完成：
- 未完成 / 阻塞：
- 下轮候选：WS-3、WS-6、按 ISSUES 开修复片。

## 6. PMO 上报区（唯一给主会话的摘要）

> 主会话只读本区。必须自包含：主会话不读 STATUS/ISSUES 正文也能拍板。
> 没有待拍板项就写"无"；有则必须给全四栏。

- **本轮结论**：<一句话>
- **待拍板**：

| 编号 | 分歧/选项 | 选项 A | 选项 B | PMO 建议 | 最晚决策时点 |
| --- | --- | --- | --- | --- | --- |
| Q-1 | | | | | 本轮结束前 |

- **指标变化**：<M1: 前 → 后>
- **下一轮建议编制**：TDO×<N'>（理由：引用 WORKFLOW §2.1 或 SPEC §7）
- **风险提示**：<1 条最重要风险 + 对应 ISSUES ID>

## 7. 变更日志

| 时间 | 轮次 | 变更 | 由谁 |
| --- | --- | --- | --- |
| <DATE> | R<ROUND-N> | 建档（特化模板 kb-debt-burn） | 主会话 |
