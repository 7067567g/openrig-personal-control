# WORKFLOW-TAGS — OpenRig 与旧工作流标签化 / 特化收束索引（首轮）

> **非规范**：本文件是标签与分析索引，不是规则、不是第二事实源。与 `WORKFLOW.md` / `roles/` / 具体 `SPEC.md` 冲突时以后者为准。
> 生成依据：本机现有完整运行目录 + OpenRig 状态快照 + 三个 workflow-group 副本；仅做只读盘点，未改动任何 run 记录。
> 机器清单：[`workflow-tags.json`](workflow-tags.json)（多标签、逐 run 可查）。
> **时效声明（2026-10-23 快照）**：本文件是 2026-10-23 快照，不是当前索引；canonical run 数以 `runs/` 目录和 `scripts/doc_consistency.py` 为准；当前 canonical=3、baseline=9、specialized=26。外部/历史快照单独标注，不在本仓校验。
> **交付边界说明**：本副本只随仓库交付 3 个 canonical run（p0/p1/p2 hard-constraints 20261116），因此此处 canonical=3 与 `runs/` 实际目录数一致；原始工作区为 63 个，其余 60 个的证据在 release asset `openrig-personal-evidence-20261116.tar.zst` 内（见 `HISTORY-INDEX.md`）。

## 0. 结论先行

- 共盘点 **103 条 2026-10-23 外部/历史快照 run 记录**（外部快照，不在本仓校验）：canonical 当时 31、OpenRig live snapshot 6、`60-外部仓库/workflow-group` 53、obsidian 本地化副本 13；本仓当前 canonical 数以顶部时效声明为准（2026-11-11 曾为 37；2026-11-15 实测 55；2026-11-16 实测 63，见 `runs/` 与 `scripts/doc_consistency.py --check`）。
- 共盘点 **89 个模板/契约资产**（外部来源为快照口径）：canonical specialized 26、外部 specialized 27、obsidian specialized 13、canonical 冻结原子契约 7、外部契约源本 7、canonical 基准模板 9。
- run 成熟度：M1=26, M2=19, M3=58；模板/契约成熟度：M2=16, M3=69。
- **骨架已冻结**：7 类原子轮型已落到 canonical `templates/contracts/`（`atomic-contract-set@1.0.0`），带 `PLAN-GATE 7/7 + VERDICT + LOCK.json`；复合类型已登记为 9 个 `templates/baseline/*` 基准模板，是新建特化时的重点参考。
- **最完善的领域特化**：KB 审计/修复/消费、物探正确性、分发运维、SignalDeck 实跑、OpenRig 双平面母版、微信产品重设计；详见 §6 的 ✅ 清单。
- **记录缺口已分类处理**：5 个 wechat prompt-run 由 snapshot `RUNS-INDEX.md` 明确定级；8 个 OpenRig 历史 PARTIAL 由 `ARCHIVE-DECISIONS.md` 接受为历史缺口，禁止冒充严格 COMPLETE。缺口事实保留，不再阻塞标准化；新 run 仍按严格规则。

## 1. 盘点范围与标记

### 1.1 来源

| 来源 | 路径 | run 数 | 说明 |
| --- | --- | ---: | --- |
| canonical | `deepseek-知识库/workflow-group/runs/` | 63 | 当前实测（2026-11-16：含 `openrig-p2-closure-20261116`；以顶部声明与 `scripts/doc_consistency.py --check` 为准）；旧工作流主体 + OpenRig 相关 run（2026-10-23 快照时为 31；2026-11-11 曾为 37） |
| OpenRig live snapshot | `50-记录与维护/会话归档/openrig-live-.../snapshots/20261022-214747/runs/` | 6 | 微信桥/月月bot 的 OpenRig 记录；5 条缺控制面四件套 |
| external | `60-外部仓库/workflow-group/runs/` | 53 | gugu 回环流水线、lingshu 研究拆解等本地化工作流 |
| obsidian localization | `obsidian-nutstore-sync-phone-ai-tools/workflow-group/runs/` | 13 | 坚果云插件 1.5.7 线的专项模板族 |

### 1.2 成熟度标记（是否“特化完善”）

| 标记 | 含义 | 判据 |
| --- | --- | --- |
| **M3 ✅** | 可收束 | 模板/契约接口完整；至少 1 条完整 run；输入、产出、门禁、DoD、证据可复用 |
| **M2 ◐** | 有特化，需补强 | 已有模板/run，但缺收轮、缺证据、模板漂移、参数化不足或只有一次试跑 |
| **M1 ○** | 单例/局部特化 | 只有 run 内 SPEC / prompt / workflow，尚无复用模板 |

> 这里的 M3 是“特化完整度”，不自动等于“已进入 canonical 母版”。是否为标准类型还要看 §7 的收束动作。

### 1.3 标签维度（一 workflow 多标签）

| 维度 | 词表 |
| --- | --- |
| `type/` | `type/analyze` `type/architecture` `type/audit` `type/cleanup` `type/decompose` `type/diff` `type/docs` `type/fix` `type/implement` `type/ingest` `type/meta` `type/migrate` `type/ops` `type/orchestrate` `type/plan` `type/postmortem` `type/redesign` `type/refactor` `type/release` `type/research` `type/strategy` `type/sync` `type/verify` |
| `domain/` | `domain/automation` `domain/data` `domain/distribution` `domain/filesystem` `domain/geophysics` `domain/governance` `domain/gugu` `domain/issues` `domain/kb` `domain/lingshu` `domain/methodology` `domain/obsidian-nutstore` `domain/openrig` `domain/product` `domain/project-repo` `domain/security` `domain/wechat-bot` `domain/workflow-engine` `domain/workspace-ops` |
| `shape/` | `shape/archive-first` `shape/bounded-rework` `shape/contract-round` `shape/dogfood` `shape/human-approval` `shape/isolated-env` `shape/live-apply` `shape/long-run` `shape/master-render` `shape/move-only` `shape/no-delete` `shape/no-push` `shape/parallel-wave` `shape/plan-gate` `shape/read-only` `shape/round-loop` `shape/safety-gated` `shape/seat-team` `shape/single-writer` `shape/staging-then-live` `shape/two-plane` `shape/verdict-loop` `shape/write-limited` |
| `evidence/` | `evidence/archive-partial` `evidence/artifact-manifest` `evidence/baseline-hash` `evidence/control-plane-missing` `evidence/file-line` `evidence/full-coverage` `evidence/gate-ledger` `evidence/metric-threshold` `evidence/mutation-test` `evidence/negative-test` `evidence/repro-command` `evidence/rollback` `evidence/source-citation` `evidence/transcript` `evidence/verdict` |
| `risk/` | `risk/cross-repo` `risk/destructive` `risk/long-cycle` `risk/no-vcs` `risk/production` `risk/release` `risk/safety-gated` `risk/secrets` `risk/upstream-sync` |
| `scope/` | `scope/reusable` `scope/domain-reusable` `scope/single-use` `scope/run-bespoke` `scope/atomic-contract` `scope/baseline-reference` |

> `type/` 可多个（一个流程常同时是 audit + verify + fix）；`domain/` 可多个；`shape/`、`evidence/`、`risk/`、`scope/` 是修饰。完整逐 run 标签见 JSON。

## 2. 主记录标签矩阵（2026-10-23 快照：37 条）

### 2.1 旧工作流主体（快照 21 条）

| run | 模板/来源 | 全部标签 | M | 记录点 |
| --- | --- | --- | --- | --- |
| `burn-postmortem-20261014` | `burn-postmortem` | `type/meta` `type/postmortem`<br>`domain/automation` `domain/workflow-engine`<br>`shape/no-push` `shape/round-loop` `shape/write-limited`<br>`evidence/metric-threshold` `evidence/repro-command` `evidence/source-citation`<br>`scope/reusable` | M3 | 成本数据表 + 失败模式 + 至少 3 处规则/代码回写；复盘类样板。 |
| `dist-ops-20261014` | `dist-ops-hardening` | `type/ops` `type/release`<br>`domain/automation` `domain/distribution` `domain/workspace-ops`<br>`shape/no-push` `shape/parallel-wave` `shape/write-limited`<br>`evidence/baseline-hash` `evidence/gate-ledger` `evidence/negative-test` `evidence/rollback`<br>`risk/cross-repo` `risk/no-vcs` `risk/release`<br>`scope/reusable` | M3 | 归档可解回、bundle 可 clone 复验、篡改 1 字节必 FAIL；分发/运维类的强负向门。 |
| `geophysics-correctness-20261014` | `geophysics-correctness` | `type/fix` `type/implement` `type/verify`<br>`domain/geophysics` `domain/project-repo`<br>`shape/no-push` `shape/parallel-wave` `shape/write-limited`<br>`evidence/full-coverage` `evidence/mutation-test` `evidence/negative-test` `evidence/repro-command`<br>`risk/cross-repo`<br>`scope/reusable` | M3 | 矩阵每格给真实 nodeid 或显式 gap；改一行/变异必红，是正确性回归的强特化。 |
| `h-drive-cleanup-20261018` | `h-drive-cleanup` | `type/cleanup` `type/ops`<br>`domain/filesystem` `domain/workspace-ops`<br>`shape/human-approval` `shape/live-apply` `shape/move-only` `shape/no-delete` `shape/safety-gated` `shape/single-writer`<br>`evidence/artifact-manifest` `evidence/gate-ledger` `evidence/negative-test`<br>`risk/destructive` `risk/production`<br>`scope/domain-reusable` | M3 | 两轮 move-only 全盘整理：action digest + 逐条 SAFETY + red 人工批准；POSIX/Windows 双后端已在模板参数化，run 必须固定后端。 |
| `h-drive-od-dismantle-20261018` | `h-drive-cleanup` | `type/cleanup` `type/ops`<br>`domain/filesystem` `domain/workspace-ops`<br>`shape/human-approval` `shape/live-apply` `shape/move-only` `shape/no-delete` `shape/safety-gated` `shape/single-writer`<br>`evidence/artifact-manifest` `evidence/gate-ledger` `evidence/negative-test`<br>`risk/destructive` `risk/production`<br>`scope/domain-reusable` | M3 | OneDrive 弃用目录拆除：action digest + 逐条 SAFETY + red 人工批准；POSIX/Windows 双后端已在模板参数化，run 必须固定后端。 |
| `h-drive-root-layout-20261018` | `h-drive-cleanup` | `type/cleanup` `type/ops`<br>`domain/filesystem` `domain/workspace-ops`<br>`shape/human-approval` `shape/live-apply` `shape/move-only` `shape/no-delete` `shape/safety-gated` `shape/single-writer`<br>`evidence/artifact-manifest` `evidence/gate-ledger` `evidence/negative-test`<br>`risk/destructive` `risk/production`<br>`scope/domain-reusable` | M3 | 根目录分类布局：action digest + 逐条 SAFETY + red 人工批准；POSIX/Windows 双后端已在模板参数化，run 必须固定后端。 |
| `kb-claim-verify-20261014` | `kb-claim-verify` | `type/audit` `type/verify`<br>`domain/kb`<br>`shape/long-run` `shape/parallel-wave` `shape/read-only` `shape/write-limited`<br>`evidence/file-line` `evidence/full-coverage` `evidence/repro-command` `evidence/source-citation`<br>`scope/reusable` | M3 | 全库可核断言逐条核验，结论分一致/不一致/不可核；可复用为“断言审计”类型。 |
| `kb-consume-20261014` | `kb-consume-interface` | `type/implement` `type/verify`<br>`domain/kb` `domain/methodology`<br>`shape/parallel-wave` `shape/single-writer` `shape/write-limited`<br>`evidence/full-coverage` `evidence/metric-threshold` `evidence/negative-test` `evidence/repro-command`<br>`scope/reusable` | M3 | 热文件互斥 + 12 条真实查询复跑 + router/frontmatter 投影反例门；消费接口类型完整。 |
| `kb-debt-20261013` | `kb-debt-burn` | `type/fix` `type/ingest` `type/verify`<br>`domain/kb` `domain/methodology`<br>`shape/long-run` `shape/parallel-wave` `shape/single-writer` `shape/write-limited`<br>`evidence/full-coverage` `evidence/metric-threshold` `evidence/repro-command` `evidence/source-citation`<br>`scope/reusable` | M3 | 唯一预填四件套 + 多 WS 写权限 + 检索可测化；知识欠账清理的完整样板。 |
| `kb-fix-20261014` | `kb-fix-wave` | `type/fix` `type/verify`<br>`domain/kb`<br>`shape/parallel-wave` `shape/single-writer` `shape/write-limited`<br>`evidence/full-coverage` `evidence/gate-ledger` `evidence/negative-test` `evidence/repro-command`<br>`scope/reusable` | M3 | 票驱动“验证→修订→复跑→门禁化”；修复波次应直接复用此闭环。 |
| `kb-method-action-20261014` | `kb-method-action` | `type/implement` `type/ingest` `type/research`<br>`domain/kb` `domain/methodology` `domain/product`<br>`shape/round-loop` `shape/write-limited`<br>`evidence/metric-threshold` `evidence/repro-command` `evidence/source-citation`<br>`scope/reusable` | M3 | 方法论原则 100% 处置 + 可运行原型 + 真实查询日志回写，验证/消费闭环完整。 |
| `master-adoption-20261015` | `(none: run-specific)` | `type/meta` `type/refactor`<br>`domain/governance` `domain/workflow-engine`<br>`shape/no-push` `shape/round-loop` `shape/write-limited`<br>`evidence/baseline-hash` `evidence/repro-command` `evidence/source-citation`<br>`scope/run-bespoke` | M1 | 母版采纳/治理落地；无专用模板，属单例元工作流。 |
| `nutstore-review-20261014` | `nutstore-sync-review` | `type/audit` `type/fix`<br>`domain/obsidian-nutstore` `domain/project-repo`<br>`shape/parallel-wave` `shape/single-writer` `shape/write-limited`<br>`evidence/full-coverage` `evidence/negative-test` `evidence/repro-command`<br>`risk/cross-repo`<br>`scope/reusable` | M3 | 一 WS 一目录/文件边界互斥；426 个 TS/TSX 全盘审查、bug 复现+回归。 |
| `openrig-audit-fix-20261020` | `openrig-workflow-master (v1.0/1.1)` | `type/fix` `type/verify`<br>`domain/openrig` `domain/workflow-engine`<br>`shape/isolated-env` `shape/seat-team` `shape/two-plane` `shape/write-limited`<br>`evidence/archive-partial` `evidence/gate-ledger` `evidence/repro-command` `evidence/transcript`<br>`scope/run-bespoke` | M2 | 混合编排早期修复 run；已 close，但 OpenRig archive 为 PARTIAL（缺 home snapshot）。 |
| `openrig-deepseek-refit-20261018` | `(none: no SPEC)` | `type/plan` `type/research`<br>`domain/openrig` `domain/workflow-engine`<br>`shape/read-only` `shape/write-limited`<br>`evidence/control-plane-missing` `evidence/repro-command` `evidence/source-citation`<br>`scope/run-bespoke` | M1 | OpenRig 早期改版/替代判断；无 SPEC，plan-ready，仅规划级记录。 |
| `openrig-full-verify-20261019` | `openrig-full-verify` | `type/audit` `type/verify`<br>`domain/openrig` `domain/workflow-engine`<br>`shape/isolated-env` `shape/long-run` `shape/read-only` `shape/seat-team`<br>`evidence/archive-partial` `evidence/full-coverage` `evidence/repro-command` `evidence/transcript`<br>`risk/secrets`<br>`scope/reusable` | M2 | README-first/evidence-first 全量检查；run 停在 waiting-main，归档 PARTIAL。 |
| `openrig-local-refit-20261018` | `openrig-local-refit` | `type/migrate` `type/plan` `type/refactor`<br>`domain/openrig` `domain/workflow-engine`<br>`shape/round-loop` `shape/write-limited`<br>`evidence/repro-command` `evidence/source-citation`<br>`scope/reusable` | M2 | 本地模式调查/重整 OpenRig，不启动 daemon；仅到 plan-ready，未收轮。 |
| `openrig-master-selfopt-20261020` | `openrig-workflow-master (v1.0→1.1)` | `type/implement` `type/meta` `type/orchestrate`<br>`domain/openrig` `domain/workflow-engine`<br>`shape/bounded-rework` `shape/dogfood` `shape/isolated-env` `shape/seat-team` `shape/two-plane`<br>`evidence/archive-partial` `evidence/gate-ledger` `evidence/transcript`<br>`scope/run-bespoke` | M2 | 用母版自举产出 v1.1；已 close，但 archive PARTIAL（缺 home snapshot）。 |
| `openrig-master-v12-20261020` | `openrig-master-v12` | `type/fix` `type/meta` `type/release` `type/verify`<br>`domain/openrig` `domain/workflow-engine`<br>`shape/bounded-rework` `shape/dogfood` `shape/isolated-env` `shape/master-render` `shape/seat-team` `shape/two-plane`<br>`evidence/archive-partial` `evidence/artifact-manifest` `evidence/baseline-hash` `evidence/negative-test` `evidence/repro-command`<br>`risk/release` `risk/upstream-sync`<br>`scope/single-use` | M3 | v1.2.0 发布：pre/post baseline、bridge 可搬迁、QA→TDO 有界回边；模板本身是版本专用。 |
| `openrig-next-stage-20261022` | `(none: run-specific)` | `type/architecture` `type/plan` `type/research`<br>`domain/openrig` `domain/product`<br>`shape/read-only` `shape/seat-team` `shape/two-plane`<br>`evidence/file-line` `evidence/source-citation` `evidence/verdict`<br>`scope/run-bespoke` | M1 | 下一阶段目标驱动/main 解耦的产品架构方案；缺 wf-doc 元数据与可复用模板。 |
| `openrig-opencode-dsh-20261018` | `openrig-local-refit` | `type/implement` `type/migrate` `type/refactor`<br>`domain/openrig` `domain/workflow-engine`<br>`shape/round-loop` `shape/write-limited`<br>`evidence/gate-ledger` `evidence/repro-command` `evidence/transcript`<br>`risk/cross-repo`<br>`scope/domain-reusable` | M2 | 收敛 OpenCode + DSH 执行层；等待主会话收口，但 SPEC 与模板精确匹配。 |
| `openrig-seat-isolation-20261023` | `openrig-workflow-master (derived)` | `type/implement` `type/release` `type/verify`<br>`domain/openrig` `domain/workflow-engine`<br>`shape/bounded-rework` `shape/isolated-env` `shape/seat-team` `shape/two-plane`<br>`evidence/repro-command` `evidence/transcript`<br>`risk/release`<br>`scope/run-bespoke` | M1 | 座位负载隔离/资源预算进行中（pmo-plan）；run-local 特化，尚无独立模板。 |
| `openrig-unparsed-bytes-20261020` | `openrig-unparsed-bytes-analysis` | `type/analyze` `type/research`<br>`domain/data` `domain/openrig`<br>`shape/bounded-rework` `shape/isolated-env` `shape/read-only` `shape/seat-team` `shape/two-plane`<br>`evidence/file-line` `evidence/full-coverage` `evidence/gate-ledger` `evidence/repro-command` `evidence/transcript`<br>`scope/domain-reusable` | M3 | 两分支差分取证 + 分支专属 QA + join + 每字段可证伪实验；假设分析强特化。 |
| `ops-reliability-20261014` | `ops-reliability` | `type/fix` `type/ops`<br>`domain/automation` `domain/project-repo` `domain/workspace-ops`<br>`shape/no-push` `shape/parallel-wave` `shape/write-limited`<br>`evidence/gate-ledger` `evidence/negative-test` `evidence/repro-command`<br>`risk/no-vcs`<br>`scope/reusable` | M3 | 在跑自动化 + 日常入口健康；测试先 FAIL 后 PASS，未纳管文件留清单。 |
| `project-freeze-20261014` | `project-freeze-facts` | `type/audit` `type/fix` `type/verify`<br>`domain/project-repo`<br>`shape/no-push` `shape/parallel-wave` `shape/write-limited`<br>`evidence/baseline-hash` `evidence/mutation-test` `evidence/negative-test` `evidence/repro-command`<br>`risk/cross-repo`<br>`scope/reusable` | M3 | 冻结声明红/隐藏差量/契约补测；父仓文件互斥 + 变异抽证。 |
| `role-boundary-audit-20261015` | `(none: run-specific)` | `type/audit` `type/meta`<br>`domain/governance` `domain/workflow-engine`<br>`shape/round-loop` `shape/write-limited`<br>`evidence/repro-command` `evidence/source-citation` `evidence/verdict`<br>`scope/run-bespoke` | M1 | 角色权责体检 + SO 定位 + 变更包/红队；无专用模板。 |
| `signaldeck-audit-20261013` | `(none: no SPEC)` | `type/audit` `type/fix` `type/refactor`<br>`domain/product` `domain/project-repo`<br>`shape/parallel-wave` `shape/round-loop` `shape/write-limited`<br>`evidence/repro-command` `evidence/source-citation`<br>`scope/run-bespoke` | M1 | 6 轮 SignalDeck 全面扫描与优化；历史基线，无 SPEC/模板，不适合直接复用。 |
| `signaldeck-runtime-20261014` | `signaldeck-runtime-verify` | `type/verify`<br>`domain/product` `domain/project-repo`<br>`shape/long-run` `shape/read-only`<br>`evidence/full-coverage` `evidence/metric-threshold` `evidence/repro-command`<br>`scope/reusable` | M3 | 只回答“它真的能跑吗”：22 步门禁逐项 PASS/FAIL/SKIP+耗时+证据。 |
| `so-necessity-research-20261015` | `(none: run-specific)` | `type/meta` `type/research` `type/strategy`<br>`domain/governance` `domain/workflow-engine`<br>`shape/round-loop` `shape/write-limited`<br>`evidence/metric-threshold` `evidence/source-citation` `evidence/verdict`<br>`scope/run-bespoke` | M1 | 以已关闭 run 为实证样本做 SO 三形态对照；研究结论强，但为单例元工作流。 |
| `wf-docs-distill-20261015` | `wf-docs-distill` | `type/docs` `type/meta`<br>`domain/workflow-engine`<br>`shape/no-push` `shape/parallel-wave` `shape/write-limited`<br>`evidence/full-coverage` `evidence/repro-command` `evidence/source-citation`<br>`scope/reusable` | M3 | 从实测结果提炼 EXAMPLE/EVOLUTION，非规范边界写清；元文档提炼类型完整。 |
| `wf-engine-tests-20261014` | `wf-engine-tests` | `type/fix` `type/implement` `type/verify`<br>`domain/automation` `domain/workflow-engine`<br>`shape/no-push` `shape/parallel-wave` `shape/write-limited`<br>`evidence/gate-ledger` `evidence/negative-test` `evidence/repro-command`<br>`scope/reusable` | M3 | wf.py/issues.py/run_queue 测试 + CI 门 + P5 遗留；引擎自测样板。 |

### 2.2 OpenRig 执行面记录（快照 16 条：canonical 10 + snapshot 6）

| run | 模板/来源 | 全部标签 | M | 记录点 |
| --- | --- | --- | --- | --- |
| `wechat-bridge-isolation-20261022` | `(none: prompt+workflow)` | `type/architecture` `type/audit` `type/plan`<br>`domain/automation` `domain/security` `domain/wechat-bot`<br>`shape/read-only` `shape/seat-team` `shape/two-plane`<br>`evidence/control-plane-missing` `evidence/gate-ledger` `evidence/source-citation`<br>`risk/production` `risk/secrets`<br>`scope/run-bespoke` | M1 | 4 个 DSH seat 做桥生命周期/隔离/安全设计；结论 PASS WITH WARNINGS，仅保存在 state snapshot。 |
| `wechat-bridge-p0-20261022` | `(none: prompt+workflow)` | `type/fix` `type/implement` `type/release` `type/verify`<br>`domain/security` `domain/wechat-bot`<br>`shape/live-apply` `shape/seat-team` `shape/staging-then-live` `shape/two-plane`<br>`evidence/control-plane-missing` `evidence/negative-test` `evidence/repro-command` `evidence/rollback`<br>`risk/production` `risk/secrets`<br>`scope/run-bespoke` | M1 | P0 六项 staging 实现→QA→合并→finalize live；60/60 测试与回滚路径；缺 PROJECT/SPEC 控制面。 |
| `wechat-bridge-v3-implement-20261022` | `(none: prompt+workflow)` | `type/implement` `type/release` `type/verify`<br>`domain/product` `domain/wechat-bot`<br>`shape/live-apply` `shape/seat-team` `shape/staging-then-live` `shape/two-plane`<br>`evidence/control-plane-missing` `evidence/gate-ledger` `evidence/repro-command` `evidence/rollback`<br>`risk/production` `risk/release`<br>`scope/run-bespoke` | M1 | 3 实施 seat + MAIN 合并 QA；108/108 测试、live apply、三件套证据；缺控制面文档。 |
| `wechat-bridge-version-plan-20261022` | `(none: prompt+workflow)` | `type/plan` `type/research` `type/sync`<br>`domain/issues` `domain/product` `domain/wechat-bot`<br>`shape/read-only` `shape/seat-team` `shape/two-plane`<br>`evidence/control-plane-missing` `evidence/file-line` `evidence/source-citation`<br>`scope/run-bespoke` | M1 | 最新消息/旧机/文档/状态四源对账 → 冲突取舍 → 363 行可执行计划；缺控制面文档。 |
| `wechat-menu-audit-20261022` | `(none: prompt+workflow)` | `type/redesign` `type/research`<br>`domain/product` `domain/wechat-bot`<br>`shape/read-only` `shape/seat-team` `shape/two-plane`<br>`evidence/control-plane-missing` `evidence/file-line` `evidence/source-citation`<br>`scope/run-bespoke` | M1 | 菜单/排版调研 + 功能冗余清理，不新增功能；产品简化型 OpenRig 取证。 |
| `wechat-yueyue-redesign-20261022` | `wechat-yueyue-redesign` | `type/implement` `type/redesign` `type/release` `type/verify`<br>`domain/product` `domain/wechat-bot`<br>`shape/live-apply` `shape/seat-team` `shape/staging-then-live` `shape/two-plane` `shape/write-limited`<br>`evidence/gate-ledger` `evidence/repro-command` `evidence/rollback`<br>`risk/production` `risk/release`<br>`scope/domain-reusable` | M3 | 单窗口产品反目标 + 4 DSH seat 分析 + MAIN 实现 + 真机切换/回滚；模板与 run 精确匹配。 |

## 3. 外部本地化 / 合同化记录（66 条，按相同标签族折叠）

> 下表中同一行的 run 共享同一组标签与成熟度；这是缩短矩阵的展示方式，**不是覆盖合并**。逐 run 清单与 note 见 JSON；每行已列全 run-id。

| 族 / 模板 | run-id | 全部标签 | M | 代表记录点 |
| --- | --- | --- | --- | --- |
| `gugu-audit-refactor-v2` | `gugu-c3-a1`<br>`gugu-c4-a1` | `type/audit` `type/refactor` `type/release`<br>`domain/gugu` `domain/project-repo`<br>`shape/no-push` `shape/round-loop` `shape/write-limited`<br>`evidence/baseline-hash` `evidence/full-coverage` `evidence/gate-ledger` `evidence/rollback`<br>`risk/release` `risk/upstream-sync`<br>`scope/domain-reusable` | M1 | gugu 审核/重整/周期收口；仅 plan-ready，尚无执行报告。 |
| `gugu-optimize-round-v2` | `gugu-c3-o1`<br>`gugu-c3-o2`<br>`gugu-c3-o3`<br>`gugu-c4-o1`<br>`gugu-c4-o2`<br>`gugu-c4-o3` | `type/implement` `type/release`<br>`domain/gugu` `domain/project-repo`<br>`shape/no-push` `shape/parallel-wave` `shape/round-loop` `shape/write-limited`<br>`evidence/metric-threshold` `evidence/repro-command` `evidence/rollback`<br>`risk/release` `risk/upstream-sync`<br>`scope/domain-reusable` | M1 | gugu 优化/版本轮；实施≤3目标+版本+发布证据；仅 plan-ready，尚无执行报告。 |
| `gugu-research-round-v2` | `gugu-c3-r1`<br>`gugu-c3-r2`<br>`gugu-c3-r3`<br>`gugu-c4-r1`<br>`gugu-c4-r2`<br>`gugu-c4-r3` | `type/research`<br>`domain/gugu` `domain/project-repo`<br>`shape/no-push` `shape/parallel-wave` `shape/read-only` `shape/round-loop`<br>`evidence/full-coverage` `evidence/repro-command` `evidence/source-citation`<br>`risk/upstream-sync`<br>`scope/domain-reusable` | M1 | gugu 研究轮；只读对标+≤3候选+backlog；仅 plan-ready，尚无执行报告。 |
| `(run-specific)` | `lingshu-code-reorg-20261016` | `type/migrate` `type/refactor`<br>`domain/lingshu` `domain/project-repo`<br>`shape/staging-then-live` `shape/write-limited`<br>`evidence/baseline-hash` `evidence/repro-command` `evidence/rollback`<br>`scope/domain-reusable` | M2 | 复制后全量重整、标准结构、语义不损失；plan-ready。 |
| `(run-specific)` | `lingshu-semantic-chain-20261016` | `type/analyze` `type/decompose` `type/plan`<br>`domain/lingshu` `domain/project-repo`<br>`shape/read-only`<br>`evidence/full-coverage` `evidence/source-citation`<br>`scope/domain-reusable` | M2 | 代码块自然语义/组合链/语义树目录提案；plan-ready。 |
| `gugu-agent-improve` | `gugu-agent-improve-20261016` | `type/implement` `type/plan` `type/research`<br>`domain/gugu` `domain/project-repo`<br>`shape/dogfood` `shape/round-loop` `shape/write-limited`<br>`evidence/full-coverage` `evidence/repro-command` `evidence/source-citation`<br>`risk/upstream-sync`<br>`scope/domain-reusable` | M2 | D/M/X 差距扫描→完善方案→副本实施；waiting-main。 |
| `gugu-audit-refactor` | `gugu-c1-a1` | `type/audit` `type/refactor` `type/release`<br>`domain/gugu` `domain/project-repo`<br>`shape/no-push` `shape/round-loop` `shape/write-limited`<br>`evidence/baseline-hash` `evidence/full-coverage` `evidence/gate-ledger` `evidence/rollback`<br>`risk/release` `risk/upstream-sync`<br>`scope/domain-reusable` | M2 | gugu 审核/重整/周期收口；本轮 SUPERSEDED/部分完成，后续周期覆盖。 |
| `gugu-optimize-round` | `gugu-c1-o1`<br>`gugu-c1-o2`<br>`gugu-c1-o3` | `type/implement` `type/release`<br>`domain/gugu` `domain/project-repo`<br>`shape/no-push` `shape/parallel-wave` `shape/round-loop` `shape/write-limited`<br>`evidence/metric-threshold` `evidence/repro-command` `evidence/rollback`<br>`risk/release` `risk/upstream-sync`<br>`scope/domain-reusable` | M2 | gugu 优化/版本轮；实施≤3目标+版本+发布证据；本轮 SUPERSEDED/部分完成，后续周期覆盖。 |
| `issue-framing` | `lingshu-issue-framing-20261016` | `type/analyze` `type/research`<br>`domain/issues` `domain/lingshu`<br>`shape/parallel-wave` `shape/read-only`<br>`evidence/full-coverage` `evidence/source-citation`<br>`scope/domain-reusable` | M2 | 只收集分析 issue 口径与项目困境，不判真伪；waiting-main。 |
| `issue-framing (derived)` | `lingshu-chain-dredge-20261016` | `type/analyze` `type/decompose` `type/plan`<br>`domain/lingshu` `domain/project-repo`<br>`shape/parallel-wave` `shape/read-only`<br>`evidence/full-coverage` `evidence/source-citation`<br>`scope/domain-reusable` | M2 | 主链疏通目录+可行性+治理建议；plan-ready。 |
| `nutstore-157-rollback-perf` | `nutstore-157-rollback-perf-20261017` | `type/fix` `type/verify`<br>`domain/obsidian-nutstore` `domain/project-repo`<br>`shape/round-loop` `shape/write-limited`<br>`evidence/metric-threshold` `evidence/repro-command` `evidence/rollback`<br>`risk/production`<br>`scope/domain-reusable` | M2 | 1.5.7 基线回退与 1.5.7.1–.4 重核；pmo-plan。 |
| `nutstore-cache-research` | `nutstore-cache-research-20261016` | `type/research`<br>`domain/obsidian-nutstore`<br>`shape/read-only` `shape/round-loop`<br>`evidence/full-coverage` `evidence/source-citation`<br>`scope/domain-reusable` | M2 | 外部方案调研/评分；waiting-main。 |
| `nutstore-cache-review` | `nutstore-cache-review-20261016` | `type/audit` `type/verify`<br>`domain/obsidian-nutstore` `domain/project-repo`<br>`shape/read-only` `shape/single-writer`<br>`evidence/full-coverage` `evidence/repro-command`<br>`scope/domain-reusable` | M2 | 1.5.7 缓存专项重审；plan-ready。 |
| `nutstore-sandbox-refactor` | `nutstore-sandbox-refactor-20261016` | `type/migrate` `type/refactor`<br>`domain/obsidian-nutstore` `domain/project-repo`<br>`shape/archive-first` `shape/staging-then-live` `shape/write-limited`<br>`evidence/baseline-hash` `evidence/full-coverage` `evidence/rollback`<br>`scope/domain-reusable` | M2 | 按分区波次、行为不变；plan-ready，189 报告/144 证据。 |
| `strategy-read` | `lingshu-intent-strategy-20261016` | `type/research` `type/strategy`<br>`domain/lingshu` `domain/product`<br>`shape/parallel-wave` `shape/read-only`<br>`evidence/source-citation` `evidence/verdict`<br>`scope/domain-reusable` | M2 | 回答在做什么/目标/上中下策；waiting-main。 |
| `gugu-audit-refactor` | `gugu-c2-a1` | `type/audit` `type/refactor` `type/release`<br>`domain/gugu` `domain/project-repo`<br>`shape/no-push` `shape/round-loop` `shape/write-limited`<br>`evidence/baseline-hash` `evidence/full-coverage` `evidence/gate-ledger` `evidence/rollback`<br>`risk/release` `risk/upstream-sync`<br>`scope/domain-reusable` | M3 | gugu 审核/重整/周期收口。 |
| `gugu-flow-spec` | `gugu-flow-spec-20261017` | `type/meta` `type/plan`<br>`domain/governance` `domain/workflow-engine`<br>`shape/contract-round` `shape/plan-gate` `shape/write-limited`<br>`evidence/repro-command` `evidence/source-citation` `evidence/verdict`<br>`scope/domain-reusable` | M3 | 锁定 7 类轮型契约、计划门、VERDICT 与回环预算。 |
| `gugu-optimize-round` | `gugu-c2-o1`<br>`gugu-c2-o2`<br>`gugu-c2-o3` | `type/implement` `type/release`<br>`domain/gugu` `domain/project-repo`<br>`shape/no-push` `shape/parallel-wave` `shape/round-loop` `shape/write-limited`<br>`evidence/metric-threshold` `evidence/repro-command` `evidence/rollback`<br>`risk/release` `risk/upstream-sync`<br>`scope/domain-reusable` | M3 | gugu 优化/版本轮；实施≤3目标+版本+发布证据。 |
| `gugu-research-round` | `gugu-c1-r1`<br>`gugu-c1-r2`<br>`gugu-c1-r3`<br>`gugu-c2-r1`<br>`gugu-c2-r2`<br>`gugu-c2-r3` | `type/research`<br>`domain/gugu` `domain/project-repo`<br>`shape/no-push` `shape/parallel-wave` `shape/read-only` `shape/round-loop`<br>`evidence/full-coverage` `evidence/repro-command` `evidence/source-citation`<br>`risk/upstream-sync`<br>`scope/domain-reusable` | M3 | gugu 研究轮；只读对标+≤3候选+backlog。 |
| `gugu-template-specialize` | `gugu-template-specialize-20261017` | `type/meta` `type/refactor`<br>`domain/gugu` `domain/workflow-engine`<br>`shape/contract-round` `shape/verdict-loop` `shape/write-limited`<br>`evidence/baseline-hash` `evidence/negative-test` `evidence/source-citation`<br>`scope/domain-reusable` | M3 | 从 14 轮实测提炼 research/optimize/audit v2 并机械验证。 |
| `issue-sync` | `lingshu-issue-sync-20261016` | `type/sync` `type/verify`<br>`domain/issues` `domain/lingshu`<br>`shape/single-writer` `shape/write-limited`<br>`evidence/negative-test` `evidence/repro-command` `evidence/source-citation`<br>`risk/upstream-sync`<br>`scope/domain-reusable` | M3 | findings→最新版重核→查重→只提交仍成立且可复现项；closed。 |
| `nutstore-1573-refine` | `nutstore-1573-refine-20261017` | `type/fix` `type/release`<br>`domain/obsidian-nutstore` `domain/project-repo`<br>`shape/single-writer` `shape/write-limited`<br>`evidence/negative-test` `evidence/repro-command` `evidence/rollback`<br>`risk/release`<br>`scope/domain-reusable` | M3 | 分块完善与补丁固化；closed，20 份报告/7 份证据。 |
| `nutstore-cache-fix` | `nutstore-cache-fix-20261016` | `type/fix` `type/verify`<br>`domain/obsidian-nutstore` `domain/project-repo`<br>`shape/parallel-wave` `shape/write-limited`<br>`evidence/full-coverage` `evidence/negative-test` `evidence/repro-command`<br>`scope/domain-reusable` | M3 | 按缓存重审结论修复 P1–P8；closed，108 报告/86 证据。 |
| `nutstore-refactor-prep` | `nutstore-refactor-prep-20261016` | `type/decompose` `type/plan`<br>`domain/obsidian-nutstore` `domain/project-repo`<br>`shape/archive-first` `shape/write-limited`<br>`evidence/artifact-manifest` `evidence/baseline-hash` `evidence/full-coverage`<br>`scope/domain-reusable` | M3 | 分区 100% 覆盖+唯一归属+冻结基线+门禁基线；closed。 |
| `nutstore-sandbox-15x-review` | `nutstore-sandbox-15x-review-20261016` | `type/audit` `type/verify`<br>`domain/obsidian-nutstore` `domain/project-repo`<br>`shape/parallel-wave` `shape/read-only`<br>`evidence/full-coverage` `evidence/repro-command`<br>`scope/domain-reusable` | M3 | 分块复核手机发布线；closed。 |
| `nutstore-sandbox-behavior` | `nutstore-sandbox-behavior-20261016` | `type/implement` `type/migrate` `type/verify`<br>`domain/obsidian-nutstore` `domain/project-repo`<br>`shape/staging-then-live` `shape/write-limited`<br>`evidence/negative-test` `evidence/repro-command` `evidence/rollback`<br>`risk/production`<br>`scope/domain-reusable` | M3 | 行为/移植 run；closed，104 报告/92 证据。 |
| `nutstore-sandbox-gates` | `nutstore-sandbox-gates-20261016` | `type/implement` `type/verify`<br>`domain/obsidian-nutstore` `domain/project-repo`<br>`shape/write-limited`<br>`evidence/gate-ledger` `evidence/negative-test` `evidence/repro-command`<br>`scope/domain-reusable` | M3 | 门禁落地；closed，52 报告/47 证据。 |
| `nutstore-tools-daily` | `nutstore-tools-daily-20261016` | `type/fix` `type/implement`<br>`domain/obsidian-nutstore`<br>`shape/round-loop` `shape/write-limited`<br>`evidence/negative-test` `evidence/repro-command`<br>`scope/domain-reusable` | M3 | 日用工具完善与扩展；closed Round 2。 |
| `nutstore-tools-rebuild` | `nutstore-tools-rebuild-20261015` | `type/audit` `type/implement` `type/refactor`<br>`domain/obsidian-nutstore` `domain/project-repo`<br>`shape/parallel-wave` `shape/write-limited`<br>`evidence/full-coverage` `evidence/repro-command` `evidence/rollback`<br>`scope/domain-reusable` | M3 | AI 工具全量审计+本地工具层重整；closed Round 2。 |
| `nutstore-tools-wave1` | `nutstore-tools-wave1-20261015` | `type/fix` `type/verify`<br>`domain/obsidian-nutstore` `domain/security`<br>`shape/single-writer` `shape/write-limited`<br>`evidence/negative-test` `evidence/repro-command`<br>`risk/secrets`<br>`scope/domain-reusable` | M3 | 移动端正确性与安全内联；closed。 |
| `research-decompose` | `lingshu-grill-20261015` | `type/analyze` `type/decompose` `type/research`<br>`domain/lingshu` `domain/project-repo`<br>`shape/parallel-wave` `shape/read-only` `shape/round-loop`<br>`evidence/full-coverage` `evidence/repro-command` `evidence/source-citation` `evidence/verdict`<br>`scope/domain-reusable` | M3 | D/M/X 研究拆解，4 轮 52 份报告；研究对象只读+证据可复现。 |
| `research-decompose (derived)` | `lingshu-asset-decompose-20261016` | `type/analyze` `type/decompose` `type/plan`<br>`domain/lingshu` `domain/project-repo`<br>`shape/read-only`<br>`evidence/artifact-manifest` `evidence/full-coverage` `evidence/source-citation`<br>`scope/domain-reusable` | M3 | 全量拆解→资产索引→语义分块→架构优化；closed。 |
| `round-types/architecture@v1` | `gugu-l1-a1`<br>`gugu-l2-a1` | `type/architecture` `type/audit`<br>`domain/gugu` `domain/project-repo`<br>`shape/contract-round` `shape/plan-gate` `shape/read-only` `shape/verdict-loop`<br>`evidence/artifact-manifest` `evidence/gate-ledger` `evidence/repro-command` `evidence/verdict`<br>`risk/upstream-sync`<br>`scope/domain-reusable` | M3 | 架构/能力地图/完善度；ROUND-PLAN→PLAN-GATE 7/7→VERDICT；契约轮型完整。 |
| `round-types/audit@v1` | `gugu-l1-x1`<br>`gugu-l2-x1` | `type/audit` `type/postmortem` `type/refactor`<br>`domain/gugu` `domain/project-repo`<br>`shape/contract-round` `shape/plan-gate` `shape/verdict-loop` `shape/write-limited`<br>`evidence/artifact-manifest` `evidence/gate-ledger` `evidence/repro-command` `evidence/verdict`<br>`risk/upstream-sync`<br>`scope/domain-reusable` | M3 | 全量审核+机械重整+RETRO；ROUND-PLAN→PLAN-GATE 7/7→VERDICT；契约轮型完整。 |
| `round-types/diff@v1` | `gugu-l1-d1`<br>`gugu-l2-d1` | `type/diff` `type/research`<br>`domain/gugu` `domain/project-repo`<br>`shape/contract-round` `shape/plan-gate` `shape/read-only` `shape/verdict-loop`<br>`evidence/artifact-manifest` `evidence/gate-ledger` `evidence/repro-command` `evidence/verdict`<br>`risk/upstream-sync`<br>`scope/domain-reusable` | M3 | 文件/函数级差异+横向矩阵；ROUND-PLAN→PLAN-GATE 7/7→VERDICT；契约轮型完整。 |
| `round-types/optimize@v1` | `gugu-l1-o1`<br>`gugu-l2-o1` | `type/implement` `type/release`<br>`domain/gugu` `domain/project-repo`<br>`shape/contract-round` `shape/plan-gate` `shape/verdict-loop` `shape/write-limited`<br>`evidence/artifact-manifest` `evidence/gate-ledger` `evidence/repro-command` `evidence/verdict`<br>`risk/upstream-sync`<br>`scope/domain-reusable` | M3 | ≤3目标实施+版本四件套；ROUND-PLAN→PLAN-GATE 7/7→VERDICT；契约轮型完整。 |
| `round-types/research@v1` | `gugu-l1-r1`<br>`gugu-l2-r1` | `type/research`<br>`domain/gugu` `domain/project-repo`<br>`shape/contract-round` `shape/plan-gate` `shape/read-only` `shape/verdict-loop`<br>`evidence/artifact-manifest` `evidence/gate-ledger` `evidence/repro-command` `evidence/verdict`<br>`risk/upstream-sync`<br>`scope/domain-reusable` | M3 | 只读对标/候选/BACKLOG；ROUND-PLAN→PLAN-GATE 7/7→VERDICT；契约轮型完整。 |
| `round-types/strategy@v1` | `gugu-l1-s1`<br>`gugu-l2-s1` | `type/plan` `type/strategy`<br>`domain/gugu` `domain/project-repo`<br>`shape/contract-round` `shape/plan-gate` `shape/read-only` `shape/verdict-loop`<br>`evidence/artifact-manifest` `evidence/gate-ledger` `evidence/repro-command` `evidence/verdict`<br>`risk/upstream-sync`<br>`scope/domain-reusable` | M3 | 方向/取舍/CYCLE-PLAN；ROUND-PLAN→PLAN-GATE 7/7→VERDICT；契约轮型完整。 |
| `round-types/verify@v1` | `gugu-l1-v1`<br>`gugu-l2-v1` | `type/release` `type/verify`<br>`domain/gugu` `domain/project-repo`<br>`shape/contract-round` `shape/plan-gate` `shape/verdict-loop` `shape/write-limited`<br>`evidence/artifact-manifest` `evidence/gate-ledger` `evidence/repro-command` `evidence/verdict`<br>`risk/upstream-sync`<br>`scope/domain-reusable` | M3 | 独立复跑+发布断言；ROUND-PLAN→PLAN-GATE 7/7→VERDICT；契约轮型完整。 |

## 4. 特化模板/契约成熟度

### 4.1 canonical `templates/specialized/`（26 个）

| 模板 | M | 强特化点 | 缺口 / 收束前要做 |
| --- | --- | --- | --- |
| `burn-postmortem` | M3 | 成本数据表+失败模式+≥3回写；可复用复盘型 | 无 validation 目录；run SPEC 只是路径参数化。 |
| `dist-ops-hardening` | M3 | 可解回归档/bundle clone/篡改反例 | 根工作区部分无 git，需每个 run 自留清单。 |
| `geophysics-correctness` | M3 | 全内容矩阵+变异必红+显式 gap | 强依赖项目测试入口/数据。 |
| `h-drive-cleanup` | M3 | SAFETY+digest+move-only 强门控；POSIX/Windows 双后端已参数化 | 两后端路径/op 集合不同，run 实例化时必须先在 DECISIONS 固定后端。 |
| `kb-claim-verify` | M3 | 全库可核断言+三态结论 | 长跑；需预算/分批策略参数化。 |
| `kb-consume-interface` | M3 | 热文件互斥+真实查询+投影反例 | 指标依赖 KB 检索基线。 |
| `kb-debt-burn` | M3 | 预填四件套+多 WS 写权限+检索可测化 | 正式域豁免需逐 run 拍板。 |
| `kb-fix-wave` | M3 | 票驱动验证→修订→复跑→门禁化 | 票源质量决定上限。 |
| `kb-method-action` | M3 | 方法论 100% 处置+原型+消费回写 | 领域较窄。 |
| `nutstore-sync-review` | M3 | 一 WS 一目录 + 426 文件全审+回归 | 目标仓/依赖环境重。 |
| `openrig-full-verify` | M2 | README-first 全量 5-seat/E2E/resume | 主 run 停在 waiting-main，模板尚无 PASS 收口证据。 |
| `openrig-local-refit` | M2 | 明确 local-only，不得冒充 E2E | 代表性 run 仍在 plan-ready/waiting-main。 |
| `openrig-master-v12` | M3 | bridge 可搬迁+有界回边+pre/post baseline | 版本专用、单次 release 模板，需抽成通用 master-upgrade。 |
| `openrig-unparsed-bytes-analysis` | M3 | 两分支差分+双 QA+join+逐字段可证伪 | 领域专用执行面模板。 |
| `openrig-workflow-master` | M3 | 双平面权威+隔离 home+渲染/验收/归档契约 | SAFETY 执行器仍是契约；历史 archive 多为 PARTIAL。 |
| `ops-reliability` | M3 | 在跑自动化/入口健康+FAIL→PASS | 部分目标无版本控制，需留 diff 清单。 |
| `project-freeze-facts` | M3 | 冻结声明红+隐藏差量+契约补测 | 父仓/文件面重，需精确白名单。 |
| `signaldeck-runtime-verify` | M3 | 问题先行+22 步逐项证据 | 项目专用。 |
| `wechat-yueyue-redesign` | M3 | 产品反目标+4 seat+live cutover/rollback | 当前仅 1 个完整 run；缺更多真机边界证据。 |
| `wf-docs-distill` | M3 | 从实测提炼非规范文档+覆盖硬要求 | 元文档型，适用面窄。 |
| `wf-engine-tests` | M3 | 引擎/读写/调度器测试+CI+P5 遗留 | 依赖本地 Python/CI 环境。 |
| `advisor-report-fusion` | M3 | 多报告来源盘点→去重合并→处置→证据核验 | 依赖报告来源质量，融合判据需按 run 固定。 |
| `issue-sync` | M3 | 最新版重核→查重→只提交仍成立 issue | specialized adapter，无独立 baseline。 |
| `openrig-advisor-refit` | M3 | 报告驱动内容降噪 + OpenRig 双平面执行与 COMPLETE 归档 | run 专用，模板通用性待抽。 |
| `signaldeck-refactor` | M2 | 清点/唯一归属/冻结基线→源码重建与行为不变门禁 | 实施中，证据尚在收轮。 |
| `yueyue-governance` | M2 | 微信桥单用户可靠性：运行态/消息/数据/控制门禁 | 新模板，需更多真机边界证据。 |

### 4.2 canonical 冻结原子轮型（7 个，`atomic-contract-set@1.0.0`）

| 契约 | M | 强特化点 | 缺口 / 收束前要做 |
| --- | --- | --- | --- |
| `contracts/strategy@1.0.0` | M3 | canonical 冻结原子轮型：输入/必产/强制门/预算/完成定义/交接；PLAN-GATE + VERDICT | 领域 adapter 仍需把 produces 映射到具体路径并声明额外门 |
| `contracts/research@1.0.0` | M3 | canonical 冻结原子轮型：输入/必产/强制门/预算/完成定义/交接；PLAN-GATE + VERDICT | 领域 adapter 仍需把 produces 映射到具体路径并声明额外门 |
| `contracts/diff@1.0.0` | M3 | canonical 冻结原子轮型：输入/必产/强制门/预算/完成定义/交接；PLAN-GATE + VERDICT | 领域 adapter 仍需把 produces 映射到具体路径并声明额外门 |
| `contracts/architecture@1.0.0` | M3 | canonical 冻结原子轮型：输入/必产/强制门/预算/完成定义/交接；PLAN-GATE + VERDICT | 领域 adapter 仍需把 produces 映射到具体路径并声明额外门 |
| `contracts/optimize@1.0.0` | M3 | canonical 冻结原子轮型：输入/必产/强制门/预算/完成定义/交接；PLAN-GATE + VERDICT | 领域 adapter 仍需把 produces 映射到具体路径并声明额外门 |
| `contracts/verify@1.0.0` | M3 | canonical 冻结原子轮型：输入/必产/强制门/预算/完成定义/交接；PLAN-GATE + VERDICT | 领域 adapter 仍需把 produces 映射到具体路径并声明额外门 |
| `contracts/audit@1.0.0` | M3 | canonical 冻结原子轮型：输入/必产/强制门/预算/完成定义/交接；PLAN-GATE + VERDICT | 领域 adapter 仍需把 produces 映射到具体路径并声明额外门 |

> 冻结入口：`templates/contracts/README.md`；核验：`python3 scripts/contract_lock.py check`。外部 `round-types/*` 保留为来源证据，不再作为标准入口。

### 4.3 canonical 基准模板（9 个复合类型重点参考）

| 基准模板 | M | 主攻方向 | 关键特点 | 默认原子契约 |
| --- | --- | --- | --- | --- |
| `baseline/fix-wave@1.0.0` | M3 | 把已有审计票源/缺陷清单变成批量、可回归、可门禁化的修复成果，而不是“改完文件就算完成”。 | 每条票必须先有失败/复现证据，再修订，再复跑，最后进入门禁。 一 WS 一域/一文件边界；全内容覆盖，不抽样。 | audit@1.0.0, optimize@1.0.0, verify@1.0.0 |
| `baseline/refactor-decompose@1.0.0` | M2 | 在代码仓/文档集/资产的结构重整前，先完成 100% 清点、唯一归属、冻结基线与门禁基线，再按波次保持行为不变地执行。 | 清点覆盖 100%，每个对象有唯一归属；不允许“未分类”被静默吞掉。 先冻结接口/行为/门禁基线，再 refactor；old→new 映射可机械核验。 | research@1.0.0, diff@1.0.0, architecture@1.0.0, optimize@1.0.0, verify@1.0.0 |
| `baseline/ops-hardening@1.0.0` | M3 | 提高分发、同步、调度和日常入口的可靠性：先证明能恢复、能 clone、能解回，再证明改动不会破坏现有入口。 | 先做只读健康报告，再做写修复；多仓/无版本控制路径必须留文件清单和 diff 摘要。 恢复性优先：归档可解回、bundle 可 clone 复验、篡改/缺失反例必须 FAIL。 | audit@1.0.0, optimize@1.0.0, verify@1.0.0 |
| `baseline/safe-cleanup@1.0.0` | M3 | 对真实文件系统做可回滚整理/迁移：默认拒绝、move-only、一次一个 action、独立 SAFETY 逐条审核、red 人工批准。 | 动作必须结构化（mkdir/move; Windows 仅此二类），禁止 shell 通配符、delete、copy、exec、purge 作为默认路径。 每个 action 绑定 digest；改动即失效，必须重新 propose。 | audit@1.0.0, optimize@1.0.0, verify@1.0.0 |
| `baseline/knowledge-pipeline@1.0.0` | M3 | 把知识从来源整理到 canonical，再到可检索、可度量、可被真实任务消费，并把实战反馈回写知识库。 | 来源→canonical→视图/检索→消费日志是一条链，不能用“文档已写”代替“已被消费”。 全内容覆盖：每篇/每条待入库材料有采用/取代/桥接/不动的处置。 | research@1.0.0, optimize@1.0.0, verify@1.0.0, audit@1.0.0 |
| `baseline/two-plane-orchestration@1.0.0` | M3 | 把目标、决策、验收和证据留在 workflow-group，把 seat、queue、workflow、transcript 和恢复状态交给 OpenRig；两边通过 bridge/证据指针同步。 | 双权威：控制面管目标/决策/验收，执行面管实时执行状态；不允许一边冒充另一边。 每个 run 独立 OPENRIG_HOME/端口/rig 名；默认 managed isolated，不碰 live daemon。 | strategy@1.0.0, research@1.0.0, architecture@1.0.0, optimize@1.0.0, verify@1.0.0, audit@1.0.0 |
| `baseline/postmortem-meta-governance@1.0.0` | M2 | 从完整运行记录、失败模式和角色冲突中提炼可执行规则、文档或模板改动，并验证回写有效。 | 数据先行：成本/轮次/失败率/开放项必须有可复核表或来源。 失败模式要能回到具体日志/文件/行，改进要有观察出处→改动文件/位置→改法。 | audit@1.0.0, strategy@1.0.0, optimize@1.0.0, verify@1.0.0 |
| `baseline/product-redesign-live@1.0.0` | M2 | 在单窗口/多端产品上先做反目标与信息架构判断，再多 seat 评审、实现、staging QA，最后安全地应用到 live 并可回滚。 | 先写“不该补/反目标”，防止功能齐全变成复杂；菜单/状态/长回复是产品约束而非实现细节。 研究/设计/QA 由独立 seat 或角色完成，MAIN 负责整合与 live 决策。 | research@1.0.0, architecture@1.0.0, optimize@1.0.0, verify@1.0.0 |
| `baseline/hypothesis-analysis@1.0.0` | M3 | 面对未知数据/字节/语义，不做“猜语义”，而是建立逐字段/逐项的假设矩阵、置信度与可证伪实验，并通过双分支 QA 汇合。 | 事实/推断/建议严格分层；不得把观察结构直接写成固件语义。 每个未解析项必须有偏移/长度/样本/候选含义/支持与反证/置信度/区分实验。 | research@1.0.0, verify@1.0.0, audit@1.0.0 |

> 基准模板不是 run 模板：`wf.py new-run --template templates/baseline/*` 或 `templates/contracts/*` 会被拒绝；领域 SPEC §0 用 `baseline: composite/<name>@1.0.0` + `contracts:` 引用。注册表见 `templates/baseline/REGISTRY.md` / `REGISTRY.json`。

### 4.4 外部 / obsidian 领域特化（M3 重点，M2 留作候选）

| 模板 | 来源 | M | 强特化点 | 缺口 |
| --- | --- | --- | --- | --- |
| `burn-postmortem` | external-workflow-group | M3 | 继承母版 | 本副本无新 run 证据，回指 canonical |
| `dist-ops-hardening` | external-workflow-group | M3 | 继承母版 | 本副本无新 run 证据，回指 canonical |
| `geophysics-correctness` | external-workflow-group | M3 | 继承母版 | 本副本无新 run 证据，回指 canonical |
| `gugu-audit-refactor-v2` | external-workflow-group | M3 | 旧发现闭环+处置分类+机械重整+发布断言+backlog | c2 完成；c3/c4 记录未执行 |
| `gugu-flow-spec` | external-workflow-group | M3 | 7 类轮型+计划门+VERDICT 锁定 | 单例但接口稳定 |
| `gugu-optimize-round-v2` | external-workflow-group | M3 | 写权限探针+接线门+版本阶梯+发布+预算 | c2 四次版本完成 |
| `gugu-research-round-v2` | external-workflow-group | M3 | 承接去重+跨周期 backlog+预算+证据 schema | c1/c2 多轮完成 |
| `gugu-template-specialize` | external-workflow-group | M3 | 从实测提炼 v2+机械验证 | 元模板单例 |
| `issue-sync` | external-workflow-group | M3 | 版本重核+查重+只提交仍成立项 | 依赖上游最新版本 |
| `kb-claim-verify` | external-workflow-group | M3 | 继承母版 | 本副本无新 run 证据，回指 canonical |
| `kb-consume-interface` | external-workflow-group | M3 | 继承母版 | 本副本无新 run 证据，回指 canonical |
| `kb-debt-burn` | external-workflow-group | M3 | 继承母版 | 本副本无新 run 证据，回指 canonical |
| `kb-fix-wave` | external-workflow-group | M3 | 继承母版 | 本副本无新 run 证据，回指 canonical |
| `kb-method-action` | external-workflow-group | M3 | 继承母版 | 本副本无新 run 证据，回指 canonical |
| `nutstore-sync-review` | external-workflow-group | M3 | 继承母版 | 本副本无新 run 证据，回指 canonical |
| `ops-reliability` | external-workflow-group | M3 | 继承母版 | 本副本无新 run 证据，回指 canonical |
| `project-freeze-facts` | external-workflow-group | M3 | 继承母版 | 本副本无新 run 证据，回指 canonical |
| `research-decompose` | external-workflow-group | M3 | D/M/X+覆盖门/可执行门/证据门+E1–E11 | 领域广；具体证据格式需适配 |
| `signaldeck-runtime-verify` | external-workflow-group | M3 | 继承母版 | 本副本无新 run 证据，回指 canonical |
| `wf-docs-distill` | external-workflow-group | M3 | 继承母版 | 本副本无新 run 证据，回指 canonical |
| `wf-engine-tests` | external-workflow-group | M3 | 继承母版 | 本副本无新 run 证据，回指 canonical |
| `nutstore-1573-refine` | obsidian-localization | M3 | 分块完善+补丁固化 | 已 closed |
| `nutstore-cache-fix` | obsidian-localization | M3 | 缓存修复+回归 | 108 报告/86 证据 |
| `nutstore-refactor-prep` | obsidian-localization | M3 | 100% 归属+冻结基线+门禁基线 | 已 closed |
| `nutstore-sandbox-15x-review` | obsidian-localization | M3 | 分块复核 | 已 closed |
| `nutstore-sandbox-behavior` | obsidian-localization | M3 | 行为/移植 | 104 报告/92 证据 |
| `nutstore-sandbox-gates` | obsidian-localization | M3 | 门禁落地 | 52 报告/47 证据 |
| `nutstore-tools-daily` | obsidian-localization | M3 | 日用工具扩展 | 已 closed |
| `nutstore-tools-rebuild` | obsidian-localization | M3 | 全量审计+工具层重整 | 已 closed |
| `nutstore-tools-wave1` | obsidian-localization | M3 | 移动端正确性/安全内联 | 已 closed |

M2 的本地化模板（需要更多 run 证据或参数化）包括：`gugu-agent-improve`、`gugu-audit-refactor`、`gugu-optimize-round`、`gugu-research-round`、`issue-framing`、`nutstore-157-rollback-perf`、`nutstore-cache-research`、`nutstore-cache-review`、`nutstore-sandbox-refactor`、`strategy-read`。完整清单见 JSON。

## 5. 横向比对：这些工作流到底差在哪

| 工作流族 | 控制面 | 执行面 | 写边界 / 风险 | 证据强项 | 主要缺口 | 收束方向 |
| --- | --- | --- | --- | --- | --- | --- |
| 旧 KB 审计/修复/消费 | 四件套 + SPEC 写权限分区 + 全内容要求 | 主会话 + 并行 TDO 波次 | 通常 run 内只写；不 push；写前精确到文件/域 | 逐篇/逐票/逐查询复跑；指标阈值；门禁化 | 领域专用，多个单例（如 method-action） | 知识流水线 + fix-wave 组合 |
| Gugu 契约轮型 | ROUND-PLAN + PLAN-GATE 7/7 + VERDICT | 主会话 + TDO 波次 | 每轮只读/限写分明；不 push upstream | 必产文件 schema + 仓库 path:line + 真值门 | 契约依赖本地 gugu-pipeline；跨域迁移未抽象 | 7 类原子轮型 → canonical contract 层 |
| Research Decompose (D/M/X) | 输入包 + 三阶段合同 + 覆盖/可执行/证据门 | 多透镜/多 WS 并行 | 对象默认只读；“执行轮”另写 run 副本 | 100% 覆盖 + 可证伪 + E1–E11 异常簿 | 证据格式领域化；执行轮易默认跳过 | 通用 research 类型 + domain adapter |
| Obsidian 分区/冻结/重构 | 分区表 + 唯一归属 + 冻结基线 + 门禁基线 | 并行 TDO / 分波次 | 行为不变；门禁不低于基线；不 push | 100% 归属、基线 hash、回滚、负向测试 | 部分代表 run 停在 plan-ready；模板很重 | refactor/decompose 复合类型 |
| H 盘 safe cleanup | 四件套 + 独立 SAFETY | 单 TDO + POSIX/Windows 双门控后端 | move-only / 不删除 / 一次一个 action / red 人工批准 | action digest + gate ledger + 前后清单 | 两后端路径/op 不同，run 内必须固定后端 | safe-cleanup 基准模板 + OS adapter |
| 微信 OpenRig 产品线 | USER-REQUEST + STATUS；部分缺 PROJECT/SPEC | 3–4 DSH seats + MAIN | staging→QA→live；生产桥；回滚脚本 | 测试输出 + finalize 日志 + live 状态 + transcript | 5/6 snapshot run 缺控制面；无统一模板 | product-redesign-live + live-apply 修饰 |
| OpenRig 双平面母版 | workflow-group 四件套 + bridge + DECISIONS | OpenRig rig/workflow/queue/seats/transcript | 隔离 home/port；不改 queue DB；先归档再 teardown | bridge 校验 + workflow trace + transcript + baseline | 正式归档全部 PARTIAL；SAFETY 执行器未实现 | two-plane orchestration 标准类型 |
| 元工作流/治理/复盘 | run 内 SPEC 或专题报告 | 主会话 + 多角色/红队 | 通常只写 run 或母版；不 push | 证据引用、红队、回写清单 | 单例多，缺统一元接口 | meta/postmortem 类型 + 统一回写门 |
| 分发/运维/入口健康 | 四件套 + 写权限到脚本/目录 | 并行三路 + 单写者收口 | 部分路径无 git；必须留 diff 清单；不 push | 可解回归档、bundle clone、篡改反例、FAIL→PASS | 目标环境分散、可移植性靠手工 | ops-hardening 类型 |
| 数据假设分析 | PROJECT/SPEC + OpenRig workflow DAG | 双分支 TDO + 分支 QA + join | 原数据只读；结论区分事实/假设 | 每字段偏移+证据+置信度+可证伪实验 | 模板只覆盖 0x903 类场景 | hypothesis-analysis 类型 |

## 6. 好特化点台账（可直接复用）

| 标记 | 特化点 | 出处 | 为什么值得收束 |
| --- | --- | --- | --- |
| ✅ | **frozen-round-contracts** | templates/contracts/{VERSION,BASE-MASTER,README,LOCK.json} + 7 个 CONTRACT.md + _shared/{PLAN-GATE,VERDICT}.md | 原子轮型已从来源副本冻结为 canonical 接口；LOCK.json 锁基础母版与契约 hash，每轮先 7/7 计划门，后写 VERDICT，把一次性 SPEC 变成可组合标准轮型。 |
| ✅ | **composite-baseline-registry** | templates/baseline/REGISTRY.{md,json} + 9 个 BASELINE.md | 复合类型成为独立“基准模板”类：主攻方向/特点/默认管线/强制证据/重点参考/成熟度一处登记；领域 SPEC 用 baseline+contracts 双引用，不能直接实例化。 |
| ✅ | **research-decompose-dmx** | 60-外部仓库/workflow-group/templates/specialized/research-decompose/SPEC.md；runs/lingshu-grill-20261015 | D 发散→M 落实→X 执行 + 覆盖门/可执行门/证据门 + E1–E11 异常簿，适合把模糊主题拆成可执行取证面。 |
| ✅ | **ticket-fix-gate** | templates/specialized/kb-fix-wave/SPEC.md；runs/kb-fix-20261014 | 每条票强制“验证命令→修订→复跑→门禁化”，修复不会停在改文件。 |
| ✅ | **full-coverage-ledger** | kb-claim-verify, geophysics-correctness, nutstore-refactor-prep | 每篇/每格/每个文件有结论与唯一归属；空白必须显式标 gap，不许抽样交差。 |
| ✅ | **negative-mutation-proof** | dist-ops-hardening, geophysics-correctness, project-freeze-facts | 反例/变异必须点红，否则判假守卫。 |
| ✅ | **two-plane-authority** | templates/specialized/openrig-workflow-master/SPEC.md §2/§5 | 控制面管目标/决策/验收，执行面管 seat/queue/workflow/transcript，两边用 bridge/evidence 指针同步，不互相冒充。 |
| ✅ | **branch-qa-join-bounded-rework** | openrig-workflow-master/templates/workflow.yaml.tpl；runs/openrig-master-v12-20261020；runs/openrig-unparsed-bytes-20261020 | 每分支独立 QA + join；failed 走静态回边，max_hops 限界，图有返工边而非靠人记。 |
| ✅ | **action-digest-safety** | templates/specialized/h-drive-cleanup/SPEC.md；scripts/windows/hgate.py；3 个 H 盘 run | action digest + 一次一个 + 独立 SAFETY 逐条审 + red 人工批准 + move-only/不删除 + 失败即停。 |
| ✅ | **staging-qa-live-rollback** | snapshot runs wechat-bridge-p0/v3；wechat-yueyue-redesign | staging 实现→QA→统一合并→finalize live→快照/回滚/通知/证据；把“改代码”和“动生产”分开。 |
| ✅ | **freeze-partition-gates** | obsidian-nutstore-sync-phone-ai-tools/workflow-group/templates/specialized/nutstore-refactor-prep；runs/nutstore-refactor-prep-20261016 | 100% 覆盖 + 唯一归属 + 冻结基线 + 门禁基线，再按波次重构。 |
| ✅ | **source-conflict-reconcile** | snapshot runs wechat-bridge-version-plan-20261022 | 多来源先盘点→冲突表→显式取舍→完整计划；冲突不藏在结论里。 |
| ✅ | **anti-feature-product-pass** | snapshot runs wechat-menu-audit-20261022；wechat-yueyue-redesign-20261022 | 先写反目标和“不该补”，再做 UX/菜单；防止功能齐全变复杂。 |
| ✅ | **postmortem-data-writeback** | templates/specialized/burn-postmortem/SPEC.md；runs/burn-postmortem-20261014 | 固定数据表 + 失败模式 + 至少 3 处规则/代码回写，复盘必须改变流程。 |
| ✅ | **archive-before-teardown** | 10-openrig-deepseek/var/openrig-archive/MANDATORY.md；scripts/openrig-archive.py | archiveStatus=COMPLETE 前不得 rig down/daemon stop；强制 control snapshot/session/transcript/state/home。 |
| ✅ | **environment-stated-green** | openrig-workflow-master/CHANGELOG.md 1.2.0；runs/openrig-master-v12-20261020 | pytest 全绿必须连环境陈述（缺 rig/node 的通过数不同），禁止只写“全绿”。 |
| ✅ | **issue-version-anchor-dedup** | 60-外部仓库/workflow-group/templates/specialized/issue-sync/SPEC.md；runs/lingshu-issue-sync-20261016 | 既有 findings 先对最新版重核，再查重，只提交仍成立/可复现/非重复项，带版本锚。 |

## 7. 向“标准工作流特化类型”收束的候选

### 7.1 两层 + 修饰词模型

- **原子轮型（atomic）**：可单轮执行、有稳定输入/产出/门禁的最小类型；已在 `templates/contracts/` 冻结，含 7 个 contract + PLAN-GATE + VERDICT + LOCK。
- **基准模板（composite baseline）**：复合类型的重点参考；在 `templates/baseline/` 登记主攻方向、特点、默认管线、证据与领域参考，共 9 个。
- **领域特化（specialized）**：真正实例化的 run 模板；由 domain adapter + baseline/contracts 引用构成。
- **修饰词（modifier）**：不单独成为类型，只改变风险/执行方式，如 `read-only`、`live-apply`、`safety-gated`、`two-plane`、`parallel-wave`、`full-coverage`。

| 候选类型 | 层 | 可映射的现有资产 | M | 说明 |
| --- | --- | --- | --- | --- |
| `atomic/strategy` | atomic | templates/contracts/strategy@1.0.0; baseline/composite/postmortem-meta-governance; lingshu-intent-strategy | M3 | 方向/取舍/≤3 目标；产出 CYCLE-PLAN/TRADEOFF/VERDICT。 |
| `atomic/research` | atomic | templates/contracts/research@1.0.0; gugu-research-round-v2; research-decompose D 轮 | M3 | 只读取证/对标/候选；产出 CANDIDATES/BACKLOG/证据。 |
| `atomic/diff` | atomic | templates/contracts/diff@1.0.0; geophysics matrices; wechat version conflict | M3 | 文件/函数/多项目横向矩阵，统一口径+path:line。 |
| `atomic/architecture` | atomic | templates/contracts/architecture@1.0.0; gugu-l*-a1; openrig-next-stage; wechat isolation | M3 | 边界/耦合/扩展点/能力地图，不直接改代码。 |
| `atomic/implement` | atomic | templates/contracts/optimize@1.0.0; gugu-optimize-round-v2; wechat p0/v3; openrig seat-isolation | M3 | ≤3 目标、先红后绿、接线、版本；写边界与 QA 成对。 |
| `atomic/verify` | atomic | templates/contracts/verify@1.0.0; signaldeck-runtime-verify; openrig-full-verify | M3 | 独立复跑与发布断言；只读复核，未验证必须显式写。 |
| `atomic/audit` | atomic | templates/contracts/audit@1.0.0; kb-claim-verify; nutstore-review; openrig-master-v12 | M3 | 全量审核 + 发现逐条处置 + RETRO/CLOSEOUT。 |
| `composite/fix-wave` | composite | templates/baseline/fix-wave; kb-fix-wave; nutstore-cache-fix; tools-wave1 | M3 | audit 票源 → verify/fix → 复跑 → 门禁化。 |
| `composite/refactor-decompose` | composite | templates/baseline/refactor-decompose; research-decompose; nutstore-sandbox-refactor; lingshu-code-reorg | M2 | 清点/唯一归属/冻结基线 → 分区波次 → 行为不变；部分代表 run 未收口。 |
| `composite/ops-hardening` | composite | templates/baseline/ops-hardening; dist-ops-hardening; ops-reliability | M3 | 多仓/无版本控制/入口健康；恢复性与负向测试必须成对。 |
| `composite/safe-cleanup` | composite | templates/baseline/safe-cleanup; h-drive-cleanup; scripts/windows/hgate.py | M3 | 高破坏风险 move-only；action digest + SAFETY + 人工批准 + POSIX/Windows 双后端；默认不删除。 |
| `composite/knowledge-pipeline` | composite | templates/baseline/knowledge-pipeline; kb-debt-burn; kb-consume-interface; kb-method-action | M3 | 入库/检索/方法消费同一闭环，指标与真实查询日志不可少。 |
| `composite/two-plane-orchestration` | composite | templates/baseline/two-plane-orchestration; openrig-workflow-master@1.2.0; openrig-master-v12 | M3 | workflow-group 控制面 + OpenRig 执行面；隔离 home/port、bridge、seat、workflow、archive。 |
| `composite/postmortem-meta-governance` | composite | templates/baseline/postmortem-meta-governance; burn-postmortem; wf-docs-distill; role-boundary-audit | M2 | 复盘/角色/规则/文档提炼；多数是单例，需统一元工作流接口。 |
| `composite/product-redesign-live` | composite | templates/baseline/product-redesign-live; wechat-yueyue-redesign; wechat p0/v3 | M2 | 反目标→多 seat 研究/设计→实现→live cutover/rollback；仅 1 个 run 有模板。 |
| `composite/issue-sync` | composite | templates/baseline/issue-sync; issue-framing; issue-sync; lingshu issue runs | M2 | 收集口径/困境 → 版本重核 → 查重 → 提交；需要上游版本锚与去重证据。 |
| `composite/hypothesis-analysis` | composite | templates/baseline/hypothesis-analysis; openrig-unparsed-bytes-analysis | M3 | 字段假设矩阵+置信度+可证伪实验；分支 QA+join，只读原数据。 |

### 7.2 建议的收束顺序

1. **原子轮型冻结：已落地**。`templates/contracts/VERSION=1.0.0`、`LOCK.json`、7 个 CONTRACT、PLAN-GATE/VERDICT、`contract_lock.py check` 与回归测试已存在。
2. **复合类型基准模板：已落地**。9 个 `templates/baseline/<name>/BASELINE.md` 与 `REGISTRY.{md,json}` 已登记；工作流入口见 `WORKFLOW.md §4.3`。
3. **领域模板降为 adapter：映射已登记，SPEC 回填进行中**。`templates/specialized/BASELINE-MAP.md` 已把现有 26 个模板映射到 baseline/contracts；模板三层关系已在 `templates/specialized/README.md` 固定，新模板强制 §0 两行声明。
4. **机器可读元数据：下一步**。在 `wf-doc` 头或 sidecar 增加 run 级 `tags/primary_type/maturity/template_source`，并用 conformance test 检查词表、run 覆盖和 M3 证据。
5. **剩余领域缺口：按 baseline 收敛**。OBS/OpenRig/微信等 M2 基准模板继续用真实 run 补证据；OpenRig archive 只允许严格 COMPLETE 的新 run 充当标准样例。

## 8. 当前缺口 / 未决

- 已处理 1：6 个 wechat OpenRig snapshot run 已由 `snapshots/20261022-214747/runs/RUNS-INDEX.md` 分类；5 个明确标为 prompt-run 档案，唯一完整控制面为 wechat-yueyue-redesign。缺口事实保留，不再冒充完整四件套。
- 已处理 2：8 个 OpenRig 历史 PARTIAL run 已由 `var/openrig-archive/ARCHIVE-DECISIONS.md` 接受为历史缺口，明确不可冒充严格 COMPLETE；新 run 仍要求先 COMPLETE 再 teardown。
- 已处理 3：`h-drive-cleanup` 模板已参数化 POSIX/Windows 双后端，README/SPEC 明确后端选择、op 集合、run-root 与命令映射；3 个 run 与模板同步可标 M3。
- 已处理 4：模板三层关系已定：`templates/contracts` 为 canonical 冻结原子轮型，`templates/baseline` 为复合类型基准模板，`templates/specialized` 为领域 adapter；外部同名模板按 source 区分，不得直接覆盖 canonical。
- 已处理 5：原子轮型与基准模板已有 `contract_lock.py check`、`tests/test_template_layers.py` 与 `REGISTRY.json` 校验；`wf.py new-run` 拒绝直接实例化 baseline/contracts。
- 仍存在：标签仍是首轮人工/规则归类，run 级 tags 尚未写入 `wf-doc`；插件读取器尚未实现。
- 仍存在：`templates/specialized/BASELINE-MAP.md` 已登记现有 26 个领域模板的 baseline/contracts 映射；但旧模板 `SPEC.md §0` 尚未批量回填，新模板起强制两行声明。

## 9. 复算方式

```bash
cd deepseek-知识库/workflow-group
# 1) 读取机器清单
python3 - <<'PY'
import json; d=json.load(open("workflow-tags.json")); print(len(d["runs"]), len(d["templates"]))
PY

# 2) 核验冻结原子轮型与基础母版 hash
python3 scripts/contract_lock.py check

# 3) 核验模板分层（contracts + baseline + 拒绝直接实例化）
python3 -m pytest tests/test_template_layers.py -q

# 4) 重算 canonical 领域模板与 run SPEC 的精确 hash 匹配
python3 - <<'PY'
from pathlib import Path; import hashlib
h=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
tpl={p.name:h(p/"SPEC.md") for p in Path("templates/specialized").iterdir() if (p/"SPEC.md").exists()}
runs={d.name:h(d/"SPEC.md") for d in Path("runs").iterdir() if (d/"SPEC.md").exists()}
print(sum(1 for v in tpl.values() if v in runs.values()), "/", len(tpl))
PY
```

> 说明：canonical 领域模板当前为 26 个；精确 hash 匹配数由 `scripts/doc_consistency.py --check` 的目录/计数校验与 `tests/test_template_layers.py` 的 SPEC §0 校验共同维护，不在本快照手写。冻结原子契约与基准模板不属于领域 `SPEC.md` 同一层级，分别由 `contract_lock.py` 与 `tests/test_template_layers.py` 校验。
