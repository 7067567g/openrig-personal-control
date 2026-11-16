# SPEC — KB 欠账清理（方法论入库 + 检索可测化 + I-08 + _reference 收口）

## 0. 分层声明

baseline: composite/knowledge-pipeline@1.0.0
contracts: research@1.0.0, optimize@1.0.0, verify@1.0.0, audit@1.0.0

> 本文件是本 run 的**特化规则**，与通用 `WORKFLOW.md`/`roles/*` 冲突时以本文件为准。
> 通用规则仍然有效：文档即接口、单一写者、STATUS 加锁逐条提交、分歧不落地。

## 1. 任务

把 KB 的 4 笔欠账在一个 24h 窗口内清掉，并留下一套可复用的检索评测工具：

1. `_reference/方法论待入库-20260924/` 4 篇唯一副本 → `05-methodology/` 正式正文（本仓 README 已承诺）；
2. 检索可测化：`scripts/kb-recall-eval.mjs` + 单测 + 57 条金问题 hit@1/2/3 基线；
3. I-08：12 个样本补 E/R 评分并回写台账；
4. `_reference/` 根目录 12 个未跟踪文件与已提交 README 记录矛盾的收口。

## 2. 写权限分区（一份写权限只给一个 WS）

| WS | 写权限（KB 仓内相对路径） | 只读输入 | 产出物（run 内） | 波次 |
| --- | --- | --- | --- | --- |
| WS-1 | `05-methodology/**` | `_reference/方法论待入库-20260924/**` | 1–2 篇正式正文 + README 阅读顺序 | R1 |
| WS-2 | `scripts/**`、`tests/**` | `00-overview/golden-questions.md` | `scripts/kb-recall-eval.mjs`、`tests/kb-recall-eval.test.mjs` | R1 |
| WS-4 | `03-web-game/00-overview/**`、`content-review-queue.md` | `../归档/02-内容包与快照/灰测样本源件-20260924/**` | 12 样本 E/R 评分一节；I-08 台账行回写 | R1 |
| WS-5 | `_reference/**`（根 12 文件 + `README.md`） | git 历史与现有 README 记录 | 12 文件去留定案 + 记录修正 | R1 |
| WS-8 | 只写 run 目录 | 全库（只读） | `reports/WS8-crosscheck.md`：4 篇素材与现有正文的重复/冲突取证 | R1 |
| WS-3 | `00-overview/**` | WS-1/WS-8 报告 | `task-router.md` 路由行、`golden-questions.md` 10 条期望答案要点、注册表/生成视图同步 | R2 |
| WS-6 | 只写 run 目录 | 全库 | `reports/WS6-eval-baseline.md`：57 条 GQ 实跑 hit 数字 + 10 条语义抽检结论 | R2 |

> 本 run 授权写 KB 正式域（仅限上表白名单），这是对通用契约"不改正式域"的**显式豁免**；白名单之外依旧只读。

## 3. 全内容覆盖要求（硬）

- 每个 WS 必须输出「范围内文件清单 + 逐文件处置」：采用 / 取代 / 桥接 / 不动（附理由）。**不许抽样、不许只挑重点**。
- WS-1 对 4 篇的来源必须 100% 处置；WS-4 对 12 个样本必须 12/12 有分；WS-5 对 12 个文件必须 12/12 有结论。
- 处置表放 `runs/<id>/reports/WS<n>-*.md`，并在 STATUS 进度条目里给路径。

## 4. 证据规范（本任务特化）

| 类型 | 必须给的证据 |
| --- | --- |
| 正式正文 | frontmatter 完整（`id`=路径、`source` 指向 `_reference/方法论待入库-20260924/`、`granularity`、`related-questions`、`applies-to-task: gray-test`、`not-for`）；`node scripts/kb-validate.mjs validate` 相关域 0 FAIL |
| 全文门禁 | `node scripts/kb-validate.mjs all`、`node scripts/kb-generate-views.mjs --check`、`node scripts/kb-validate.mjs hygiene` 的输出摘要 |
| 评测工具 | `node --test tests/kb-recall-eval.test.mjs` 通过；一条命令可复现 hit@1/2/3 与未命中清单 |
| 评分（I-08） | 每个样本 E/R 分 + 一句话理由 + 可复跑证据（文件路径/命令）；口径与 `ds-gray-test-samples-evaluation.md` §1 一致 |
| 文件处置 | 路径 + md5/引用来源 + 处置结论；改 `_reference/README.md` 时保留历次收窄表格式 |

## 5. 禁止

- 不写白名单外任何路径；不动 `../deepseek-项目/**`、不动其他 `_reference/` 子目录。
- **不删除/移动任何源素材**；WS-5 的默认动作是「重新登记 + 修正 README 记录」，回收/删除必须等主会话拿到用户确认后另开决策。
- 不虚构评测数字/评分；未过门禁不得宣称完成。
- 不直接改 `00-overview/` 的生成视图文件（`kb-map.md` 等由脚本生成）。
- 不 `git add -A`；提交统一由主会话按轮做（TDO 只改不提交；STATUS 的逐条提交不受影响）。

## 6. 完成定义（DoD）

- 4/4 素材有处置，`05-methodology/` 有 canonical 正文且 `validate all` 0 FAIL；
- `scripts/kb-recall-eval.mjs` + 单测可用，57 条 GQ 跑出 hit 数字与未命中清单；
- 10 条 GQ 有期望答案要点且抽检结论落 run 报告；
- 12/12 样本有 E/R 评分并回写评估文档与 `content-review-queue.md` I-08 行；
- 12/12 `_reference` 文件定案，README 记录与磁盘一致；
- ISSUES 无 open S1/S2；全量门禁绿；`reports/audit-final.md` 产出。

## 7. 波次建议

- **R1**：WS-1、WS-2、WS-4、WS-5、WS-8 并行（5 路，互不重叠）。
- **R2**：WS-3（应用 WS-1/WS-8 的清单到 `00-overview/`）、WS-6（用 WS-2 的工具跑 57 条基线）；同时按 QA 的 ISSUES 开修复片。
- **R3**：全量门禁 + 修复回归 + 收口报告。
