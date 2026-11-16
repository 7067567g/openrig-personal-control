# BASELINE-MAP — 领域特化 → 基准模板/原子契约登记

> 本表把现有 26 个 canonical 领域特化登记到 `templates/baseline/` 的复合类型和 `templates/contracts/` 的原子轮型。
> 2026-10-23 新增 `advisor-report-fusion` 与 `openrig-advisor-refit`，并把 `issue-sync` 从 baseline 降级为 specialized adapter；后续补充 `signaldeck-refactor`、`yueyue-governance`，当前为 26。本表与 `templates/specialized/*/` 的一一对应及 canonical 计数由 `scripts/doc_consistency.py --check` 校验（不再手写维护陈旧计数）。
> 目的：在工作流里把基准模板登记为**特化重点参考**；新建/大改 `/SPEC.md` 时仍需把对应 `baseline:` / `contracts:` 写进 §0。
> 旧 run 的历史 `SPEC.md` 不改；本表是**回填映射**，不是对旧 run 的追溯改写。

| 领域特化 | baseline | contracts | 映射理由 |
| --- | --- | --- | --- |
| `burn-postmortem` | `composite/postmortem-meta-governance` | audit, strategy, optimize, verify | 复盘数据→规则/模板回写→验证 |
| `dist-ops-hardening` | `composite/ops-hardening` | audit, optimize, verify | 分发/同步/运维恢复性与负向门 |
| `geophysics-correctness` | `composite/fix-wave` | audit, optimize, verify | 正确性回归/契约补测/变异门 |
| `h-drive-cleanup` | `composite/safe-cleanup` | audit, optimize, verify | move-only 门控 + 独立 SAFETY + live 整理 |
| `issue-sync` | `none`（specialized adapter，原 `composite/issue-sync` 已降级） | research, verify, audit | 最新版本重核→查重→只提交仍成立 issue（M2 沿用，2026-10-23 降级） |
| `kb-claim-verify` | `none`（直接原子组合） | audit, verify | 只读断言核验，无需复合模板 |
| `kb-consume-interface` | `composite/knowledge-pipeline` | research, optimize, verify, audit | 检索接口/指标/投影门禁/消费闭环 |
| `kb-debt-burn` | `composite/knowledge-pipeline` | research, optimize, verify, audit | 入库/检索可测化/欠账收口 |
| `kb-fix-wave` | `composite/fix-wave` | audit, optimize, verify | 票驱动验证→修订→复跑→门禁化 |
| `kb-method-action` | `composite/knowledge-pipeline` | research, optimize, verify | 方法论消费+原型+真实查询回写 |
| `nutstore-sync-review` | `composite/fix-wave` | audit, optimize, verify | 全盘审查→bug 修复→回归 |
| `openrig-full-verify` | `none`（直接原子组合） | verify, audit | 只读全量验证/检查 |
| `openrig-local-refit` | `composite/refactor-decompose` | research, diff, architecture, optimize, verify | 探测→重构方案→本地重整 |
| `openrig-master-v12` | `composite/two-plane-orchestration` | strategy, architecture, optimize, verify, audit | 双平面母版版本更新与发布 |
| `openrig-unparsed-bytes-analysis` | `composite/hypothesis-analysis` | research, verify, audit | 假设矩阵/分支 QA/join |
| `openrig-workflow-master` | `composite/two-plane-orchestration` | strategy, research, architecture, optimize, verify, audit | 双平面母版，不是 run 模板 |
| `ops-reliability` | `composite/ops-hardening` | audit, optimize, verify | 在跑自动化/入口可靠性 |
| `project-freeze-facts` | `composite/fix-wave` | audit, optimize, verify | 冻结声明红→修复→契约补测/门禁 |
| `signaldeck-runtime-verify` | `none`（直接原子组合） | verify | 单问题实跑验证 |
| `wechat-yueyue-redesign` | `composite/product-redesign-live` | research, architecture, optimize, verify | 反目标→多 seat 设计→实现→live/回滚 |
| `wf-docs-distill` | `composite/postmortem-meta-governance` | audit, strategy, optimize, verify | 实测→非规范文档提炼/边界控制 |
| `wf-engine-tests` | `composite/fix-wave` | audit, optimize, verify | 测试/CI/P5 遗留修复与回归 |
| `advisor-report-fusion` | `composite/postmortem-meta-governance` | audit, strategy, optimize, verify | 多报告来源盘点→去重合并→处置→证据核验 |
| `openrig-advisor-refit` | `composite/two-plane-orchestration` | strategy, architecture, optimize, verify, audit | 报告驱动的 workflow 内容降噪/模板收敛 + OpenRig 双平面执行与 COMPLETE 归档 |
| `signaldeck-refactor` | `composite/refactor-decompose` | research, diff, architecture, optimize, verify | 清点/唯一归属/冻结基线→源码重建与共享边界→行为不变门禁 |
| `yueyue-governance` | `composite/fix-wave` | audit, optimize, verify | 微信桥单用户可靠性治理→修复→复跑/回滚证据 |

## 使用规则

1. 本表是**当前 26 个领域模板的登记**；新增模板必须在本表补一行，否则 `doc_consistency.py --check` 会报 ERROR。
2. `baseline: none` 不是“无类型”：它表示该任务只由原子契约组合即可，并在 `SPEC.md §0` 写 `baseline: none + 理由`。
3. 映射不是排他的：一个领域模板可以用一个 baseline 为主，额外加其它原子契约；加契约不能删 baseline 的强制证据。
4. 旧 run 的 `SPEC.md` 保持原样；本表只用于新 run/模板改版的选型与回填。
